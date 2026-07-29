import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from api.services.video_service import extract_first_frame_path, normalize_video_path, VideoMeta
from shared.config import settings
from shared.r2_client import r2_client

logger = logging.getLogger(__name__)

_UPLOAD_COPY_BUFFER = 8 * 1024 * 1024
_UPLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="trafficflow-upload")


async def _run_blocking(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_UPLOAD_EXECUTOR, partial(fn, *args, **kwargs))


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


def _save_local_preview(video_id: str, preview_bytes: bytes) -> None:
    local_preview_dir = Path(settings.STORAGE_DIR) / "previews"
    local_preview_dir.mkdir(parents=True, exist_ok=True)
    (local_preview_dir / f"{video_id}.jpg").write_bytes(preview_bytes)


def _copy_upload_file(source, destination: str) -> None:
    with open(destination, "wb") as target:
        shutil.copyfileobj(source, target, length=_UPLOAD_COPY_BUFFER)


async def save_upload_to_temp(file: UploadFile) -> str:
    """Copy a validated upload to a processing path without blocking the loop.

    ``UploadFile.read`` would schedule one thread-pool operation per chunk and
    the destination write would still happen on the event-loop thread. A
    single buffered copy in a worker thread keeps both operations off the API
    loop and reduces Python-level per-chunk overhead.
    """
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        await file.seek(0)
        await _run_blocking(_copy_upload_file, file.file, temp_path)
        return temp_path
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


async def _delete_uploaded_keys(keys: list[str]) -> None:
    for key in keys:
        try:
            await _run_blocking(r2_client.delete_file, key)
        except Exception:
            logger.warning("Could not delete uploaded key after failure: %s", key)


async def _unlink_path(path: str | Path | None) -> None:
    if path:
        try:
            await _run_blocking(os.unlink, path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("Could not delete temp path: %s", path)


async def _delete_local_preview(video_id: str) -> None:
    await _unlink_path(Path(settings.STORAGE_DIR) / "previews" / f"{video_id}.jpg")


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
    ingest_ms: float,
    storage_ms: float,
    preview_ms: float,
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
        "ingest_ms": round(ingest_ms, 0),
        "storage_ms": round(storage_ms, 0),
        "preview_ms": round(preview_ms, 0),
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_at,
    }


async def create_uploaded_video_task_from_path(
    *,
    db,
    video_path: str | Path,
    content_type: str = "video/mp4",
) -> UploadedVideo:
    video_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    uploaded_keys = []
    working_path = None
    owns_working_path = False
    ingest_started = time.perf_counter()

    try:
        working_path, original_meta, working_meta, transcode_ms, owns_working_path = await _run_blocking(
            normalize_video_path, video_path
        )

        stored_original = bool(settings.STORE_ORIGINAL_VIDEO)
        working_key = f"uploads/{video_id}_1080p.mp4"
        storage_started = time.perf_counter()

        if stored_original:
            original_key = f"uploads/{video_id}.mp4"
            original_url = await _run_blocking(
                r2_client.upload_path, video_path, original_key, content_type or "video/mp4"
            )
            uploaded_keys.append(original_key)
            working_url = await _run_blocking(
                r2_client.upload_path, working_path, working_key, "video/mp4"
            )
            uploaded_keys.append(working_key)
            video_url = original_url
            original_video_url = original_url
            original_video_key = original_key
        else:
            working_key = f"uploads/{video_id}.mp4"
            working_url = await _run_blocking(
                r2_client.upload_path, working_path, working_key, "video/mp4"
            )
            uploaded_keys.append(working_key)
            video_url = working_url
            original_video_url = None
            original_video_key = None
        storage_ms = (time.perf_counter() - storage_started) * 1000.0

        preview_started = time.perf_counter()
        try:
            preview_bytes = await _run_blocking(extract_first_frame_path, working_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Could not extract a preview frame from the uploaded video.",
            ) from exc

        preview_key = f"previews/{video_id}.jpg"
        preview_url = await _run_blocking(
            r2_client.upload_file, preview_bytes, preview_key, "image/jpeg"
        )
        uploaded_keys.append(preview_key)
        # Keep a local copy for the compatibility route, but return the
        # storage URL so production replicas do not depend on local disk.
        await _run_blocking(_save_local_preview, video_id, preview_bytes)
        preview_ms = (time.perf_counter() - preview_started) * 1000.0

        task_doc = _task_document(
            video_id=video_id,
            task_id=task_id,
            video_url=video_url,
            working_video_url=working_url,
            preview_url=preview_url,
            original_meta=original_meta,
            working_meta=working_meta,
            transcode_ms=transcode_ms,
            ingest_ms=(time.perf_counter() - ingest_started) * 1000.0,
            storage_ms=storage_ms,
            preview_ms=preview_ms,
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
        await _delete_uploaded_keys(uploaded_keys)
        await _delete_local_preview(video_id)
        raise
    except Exception as exc:
        await _delete_uploaded_keys(uploaded_keys)
        await _delete_local_preview(video_id)
        logger.exception("Upload processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while uploading the video.",
        ) from exc
    finally:
        if owns_working_path and working_path and os.path.exists(working_path):
            await _unlink_path(working_path)
