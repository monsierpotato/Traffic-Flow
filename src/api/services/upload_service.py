import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, status

from api.services.video_service import extract_first_frame_path, normalize_video_path, VideoMeta
from shared.config import settings
from shared.r2_client import r2_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadedVideo:
    video_id: str
    task_id: str
    preview_url: str
    task_doc: dict
    original_meta: VideoMeta
    working_meta: VideoMeta


def _meta_resolution(meta: VideoMeta) -> str:
    return f"{meta.width}x{meta.height}"


def _mb(size_bytes: int) -> float:
    return round(size_bytes / 1e6, 2)


def _color_meta(meta: VideoMeta) -> dict:
    return {
        "codec": meta.codec,
        "pix_fmt": meta.pix_fmt,
        "color_range": meta.color_range,
        "color_space": meta.color_space,
        "color_transfer": meta.color_transfer,
        "color_primaries": meta.color_primaries,
    }


def _save_local_preview(video_id: str, preview_bytes: bytes, request: Request) -> str:
    local_preview_dir = Path("storage/previews")
    local_preview_dir.mkdir(parents=True, exist_ok=True)
    (local_preview_dir / f"{video_id}.jpg").write_bytes(preview_bytes)
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/static/previews/{video_id}.jpg"


def _task_document(
    *,
    video_id: str,
    task_id: str,
    video_url: str,
    working_video_url: str,
    preview_url: str,
    original_meta: VideoMeta,
    working_meta: VideoMeta,
    transcode_ms: float,
    stored_original: bool,
    original_video_url: Optional[str],
    original_video_key: Optional[str],
    working_video_key: str,
) -> dict:
    now = datetime.utcnow()
    expires_at = now + timedelta(days=settings.RETENTION_DAYS)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "uploaded",
        "progress": 0,
        "stage": "uploaded",
        "stage_detail": "Upload stored and preview generated",
        "video_url": video_url,
        "working_video_url": working_video_url,
        "original_video_url": original_video_url,
        "preview_url": preview_url,
        "result_video_url": None,
        "events_url": None,
        "error_message": None,
        "stored_original_video": stored_original,
        "original_video_key": original_video_key,
        "working_video_key": working_video_key,
        "preview_key": f"previews/{video_id}.jpg",
        "original_resolution": _meta_resolution(original_meta),
        "original_fps": original_meta.fps,
        "original_size_mb": _mb(original_meta.size_bytes),
        "original_video_meta": _color_meta(original_meta),
        "working_resolution": _meta_resolution(working_meta),
        "working_fps": working_meta.fps,
        "working_size_mb": _mb(working_meta.size_bytes),
        "working_video_meta": _color_meta(working_meta),
        "transcode_ms": round(transcode_ms, 0),
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_at,
    }


async def create_uploaded_video_task_from_path(
    *,
    request: Request,
    db,
    video_path: str | Path,
    content_type: str = "video/mp4",
) -> UploadedVideo:
    video_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    uploaded_keys = []
    working_path = None
    owns_working_path = False

    try:
        working_path, original_meta, working_meta, transcode_ms, owns_working_path = normalize_video_path(video_path)

        stored_original = bool(settings.STORE_ORIGINAL_VIDEO)
        working_key = f"uploads/{video_id}_1080p.mp4"

        if stored_original:
            original_key = f"uploads/{video_id}.mp4"
            original_url = r2_client.upload_path(video_path, original_key, content_type or "video/mp4")
            uploaded_keys.append(original_key)
            working_url = r2_client.upload_path(working_path, working_key, "video/mp4")
            uploaded_keys.append(working_key)
            video_url = original_url
            original_video_url = original_url
            original_video_key = original_key
        else:
            working_key = f"uploads/{video_id}.mp4"
            working_url = r2_client.upload_path(working_path, working_key, "video/mp4")
            uploaded_keys.append(working_key)
            video_url = working_url
            original_video_url = None
            original_video_key = None

        try:
            preview_bytes = extract_first_frame_path(working_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Could not extract preview frame from video: {exc}",
            ) from exc

        preview_key = f"previews/{video_id}.jpg"
        r2_client.upload_file(preview_bytes, preview_key, "image/jpeg")
        uploaded_keys.append(preview_key)
        preview_url = _save_local_preview(video_id, preview_bytes, request)

        task_doc = _task_document(
            video_id=video_id,
            task_id=task_id,
            video_url=video_url,
            working_video_url=working_url,
            preview_url=preview_url,
            original_meta=original_meta,
            working_meta=working_meta,
            transcode_ms=transcode_ms,
            stored_original=stored_original,
            original_video_url=original_video_url,
            original_video_key=original_video_key,
            working_video_key=working_key,
        )
        await db.tasks.insert_one(task_doc)

        logger.info(
            "Uploaded video %s | store_original=%s | original=%s %.2fMB | working=%s %.2fMB",
            video_id,
            stored_original,
            _meta_resolution(original_meta),
            _mb(original_meta.size_bytes),
            _meta_resolution(working_meta),
            _mb(working_meta.size_bytes),
        )

        return UploadedVideo(
            video_id=video_id,
            task_id=task_id,
            preview_url=preview_url,
            task_doc=task_doc,
            original_meta=original_meta,
            working_meta=working_meta,
        )
    except HTTPException:
        for key in uploaded_keys:
            try:
                r2_client.delete_file(key)
            except Exception:
                logger.warning("Could not delete uploaded key after failure: %s", key)
        raise
    except Exception as exc:
        for key in uploaded_keys:
            try:
                r2_client.delete_file(key)
            except Exception:
                logger.warning("Could not delete uploaded key after failure: %s", key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while uploading: {exc}",
        ) from exc
    finally:
        if owns_working_path and working_path and os.path.exists(working_path):
            try:
                os.unlink(working_path)
            except Exception:
                logger.warning("Could not delete temp working video: %s", working_path)


async def create_uploaded_video_task(
    *,
    request: Request,
    db,
    video_bytes: bytes,
    content_type: str = "video/mp4",
) -> UploadedVideo:
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    try:
        temp_video.write(video_bytes)
        temp_video.close()
        return await create_uploaded_video_task_from_path(
            request=request,
            db=db,
            video_path=temp_video.name,
            content_type=content_type,
        )
    finally:
        if os.path.exists(temp_video.name):
            try:
                os.unlink(temp_video.name)
            except Exception:
                logger.warning("Could not delete temp upload video: %s", temp_video.name)
