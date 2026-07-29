import json
import os
import re
import tempfile
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request, status, Form
from api.dependencies import require_database
from api.middleware.file_validator import validate_video_file
from api.services.upload_service import create_uploaded_video_task_from_path, save_upload_to_temp
from api.schemas.upload import UploadResponse
from shared.config import settings

router = APIRouter()

# --- Chunked upload ---

CHUNK_DIR = Path(settings.STORAGE_DIR) / "chunks"
MAX_CHUNK_COUNT = 10_000


def _validate_upload_id(upload_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload_id")


def _validate_chunk_request(upload_id: str, chunk_index: int, total_chunks: int, filename: str) -> None:
    _validate_upload_id(upload_id)
    if total_chunks < 1 or total_chunks > MAX_CHUNK_COUNT:
        raise HTTPException(status_code=400, detail=f"total_chunks must be between 1 and {MAX_CHUNK_COUNT}")
    if chunk_index < 0 or chunk_index >= total_chunks:
        raise HTTPException(status_code=400, detail="chunk_index must be within total_chunks")
    extension = Path(filename or "").suffix.lower()
    if extension not in settings.ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension {extension}. Allowed extensions: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}",
        )


@router.post("/video/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    filename: str = Form(...),
    file: UploadFile = File(...),
):
    _validate_chunk_request(upload_id, chunk_index, total_chunks, filename)
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    upload_dir = CHUNK_DIR / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    meta_path = upload_dir / "meta.json"
    if meta_path.exists():
        try:
            existing_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Upload metadata is invalid") from exc
        if existing_meta.get("total_chunks") != total_chunks or existing_meta.get("filename") != filename:
            raise HTTPException(status_code=409, detail="Chunk metadata does not match the upload session")

    chunk_path = upload_dir / f"{chunk_index:06d}"
    temporary_chunk_path = upload_dir / f".{chunk_index:06d}.tmp"
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    size = 0
    try:
        with temporary_chunk_path.open("wb") as target:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Chunk exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB",
                    )
                target.write(chunk)
        os.replace(temporary_chunk_path, chunk_path)
    except Exception:
        if temporary_chunk_path.exists():
            temporary_chunk_path.unlink()
        raise

    # Save metadata on first chunk
    if not meta_path.exists():
        metadata = json.dumps({
            "filename": filename,
            "total_chunks": total_chunks,
            "created_at": datetime.utcnow().isoformat(),
        })
        temporary_meta_path = upload_dir / ".meta.json.tmp"
        temporary_meta_path.write_text(metadata, encoding="utf-8")
        os.replace(temporary_meta_path, meta_path)

    return {"upload_id": upload_id, "chunk": chunk_index, "status": "ok"}


@router.post("/video/chunk/{upload_id}/complete")
async def complete_chunked_upload(
    upload_id: str,
    request: Request,
    db=Depends(require_database),
):
    _validate_upload_id(upload_id)
    upload_dir = CHUNK_DIR / upload_id
    if not upload_dir.exists():
        raise HTTPException(404, "Upload session not found")

    meta_path = upload_dir / "meta.json"
    if not meta_path.exists():
        raise HTTPException(400, "Missing metadata")

    meta = json.loads(meta_path.read_text())
    total_chunks = meta["total_chunks"]
    filename = meta.get("filename", "video.mp4")
    _validate_chunk_request(upload_id, 0, total_chunks, filename)

    # Reassemble
    expected_names = {f"{index:06d}" for index in range(total_chunks)}
    chunk_files = {path.name: path for path in upload_dir.iterdir() if path.name.isdigit()}
    missing = sorted(expected_names - chunk_files.keys())
    unexpected = sorted(chunk_files.keys() - expected_names)
    if missing or unexpected:
        detail = f"Missing chunks: {len(missing)}; unexpected chunks: {len(unexpected)}"
        raise HTTPException(400, detail)
    chunks = [chunk_files[name] for name in sorted(expected_names)]

    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix or ".mp4")
    temp_path = temp_video.name
    try:
        total_size = 0
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        for chunk in chunks:
            with chunk.open("rb") as fp:
                while True:
                    data = fp.read(1024 * 1024)
                    if not data:
                        break
                    total_size += len(data)
                    if total_size > max_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Combined upload exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB",
                        )
                    temp_video.write(data)
        temp_video.close()

        uploaded = await create_uploaded_video_task_from_path(
            request=request,
            db=db,
            video_path=temp_path,
            content_type="video/mp4",
        )
    finally:
        temp_video.close()
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)

    return UploadResponse(
        video_id=uploaded.video_id,
        preview_url=uploaded.preview_url,
        message=f"Video uploaded (normalized {uploaded.working_meta.width}x{uploaded.working_meta.height}) and preview generated successfully.",
    )


# --- Original single-file upload ---

@router.post("/video", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    request: Request,
    file: UploadFile = Depends(validate_video_file),
    db = Depends(require_database)
):
    """Uploads video file, extracts first frame, saves both to Cloudflare R2,
    and initializes a task document in MongoDB.
    """
    try:
        temp_path = await save_upload_to_temp(file)
        try:
            uploaded = await create_uploaded_video_task_from_path(
                request=request,
                db=db,
                video_path=temp_path,
                content_type=file.content_type or "video/mp4",
            )
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        
        return UploadResponse(
            video_id=uploaded.video_id,
            preview_url=uploaded.preview_url,
            message=f"Video uploaded (normalized {uploaded.working_meta.width}x{uploaded.working_meta.height}) and preview generated successfully."
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while uploading: {str(e)}"
        )
