import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request, status, Form
from shared.database import get_database
from api.middleware.file_validator import validate_video_file
from api.services.upload_service import create_uploaded_video_task_from_path
from api.schemas.upload import UploadResponse

router = APIRouter()

# --- Chunked upload ---

CHUNK_DIR = Path("storage/chunks")


async def _save_upload_to_temp(file: UploadFile) -> str:
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "video.mp4").suffix or ".mp4")
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            temp_file.write(chunk)
        temp_file.close()
        return temp_file.name
    except Exception:
        temp_file.close()
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        raise


@router.post("/video/chunk")
async def upload_chunk(
    request: Request,
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    filename: str = Form(...),
    file: UploadFile = File(...),
):
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    upload_dir = CHUNK_DIR / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    chunk_path = upload_dir / f"{chunk_index:06d}"
    chunk_bytes = await file.read()
    chunk_path.write_bytes(chunk_bytes)

    # Save metadata on first chunk
    meta_path = upload_dir / "meta.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps({
            "filename": filename,
            "total_chunks": total_chunks,
            "created_at": datetime.utcnow().isoformat(),
        }))

    return {"upload_id": upload_id, "chunk": chunk_index, "status": "ok"}


@router.post("/video/chunk/{upload_id}/complete")
async def complete_chunked_upload(request: Request, upload_id: str, db=Depends(get_database)):
    upload_dir = CHUNK_DIR / upload_id
    if not upload_dir.exists():
        raise HTTPException(404, "Upload session not found")

    meta_path = upload_dir / "meta.json"
    if not meta_path.exists():
        raise HTTPException(400, "Missing metadata")

    meta = json.loads(meta_path.read_text())
    total_chunks = meta["total_chunks"]
    filename = meta.get("filename", "video.mp4")

    # Reassemble
    chunks = sorted(upload_dir.glob("*"))
    chunks = [c for c in chunks if c.name.isdigit()]
    if len(chunks) != total_chunks:
        raise HTTPException(400, f"Missing chunks: {len(chunks)}/{total_chunks}")

    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix or ".mp4")
    temp_path = temp_video.name
    try:
        for chunk in chunks:
            with chunk.open("rb") as fp:
                while True:
                    data = fp.read(1024 * 1024)
                    if not data:
                        break
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
    db = Depends(get_database)
):
    """Uploads video file, extracts first frame, saves both to Cloudflare R2,
    and initializes a task document in MongoDB.
    """
    try:
        temp_path = await _save_upload_to_temp(file)
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

