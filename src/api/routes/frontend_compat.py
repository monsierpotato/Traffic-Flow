"""Compatibility routes matching frontend's expected API endpoints."""

import logging
import os
import tempfile
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse

from shared.database import get_database
from api.middleware.file_validator import validate_video_file
from api.services.upload_service import create_uploaded_video_task_from_path
from api.schemas.task import TaskCreateRequest
from api.routes.tasks import process_task, get_task_status, get_task_result

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.post("/videos")
async def compat_upload(request: Request, file: UploadFile = File(...)):
    file = validate_video_file(file)
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database not connected")

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

    return {
        "task_id": uploaded.video_id,
        "video_id": uploaded.video_id,
        "status": "uploaded",
        "preview_url": uploaded.preview_url,
        "working_video_url": uploaded.task_doc["working_video_url"],
        "original_resolution": uploaded.task_doc["original_resolution"],
        "working_resolution": uploaded.task_doc["working_resolution"],
    }


@router.get("/videos/{task_id}/preview")
async def compat_preview(task_id: str):
    preview = Path("storage/previews") / f"{task_id}.jpg"
    if preview.exists():
        return FileResponse(str(preview), media_type="image/jpeg")
    raise HTTPException(404, "Preview not found")


@router.post("/tasks")
async def compat_submit(request: Request, payload: dict):
    import traceback
    video_id = payload.get("task_id") or payload.get("video_id", "")
    lane_config = payload.get("lane_config")

    if not video_id:
        raise HTTPException(400, "task_id or video_id required")
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database not connected")

    # Check if task exists
    task = await db.tasks.find_one({"video_id": video_id})
    if not task:
        raise HTTPException(404, f"No upload session found for {video_id}")

    task_id = task["task_id"]

    # Save lane config if provided by frontend
    if lane_config:
        cfg = dict(lane_config)
        cfg["video_id"] = video_id
        cfg["task_id"] = task_id
        cfg["created_at"] = datetime.utcnow()
        await db.lane_configs.update_one(
            {"video_id": video_id},
            {"$set": cfg},
            upsert=True,
        )
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "configured", "updated_at": datetime.utcnow()}},
        )

    try:
        from fastapi import BackgroundTasks
        req = TaskCreateRequest(video_id=video_id)
        resp = await process_task(req, request, background_tasks=BackgroundTasks(), db=db)
        return {"task_id": resp.task_id, "status": resp.status, "progress": 0}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Process failed: {e}")


@router.get("/tasks/{task_id}")
async def compat_status(task_id: str):
    from shared.database import get_database
    db = get_database()
    resp = await get_task_status(task_id, db=db)
    return {
        "task_id": resp.task_id,
        "status": resp.status,
        "progress": resp.progress,
        "stage": resp.stage,
        "stage_detail": resp.stage_detail,
    }


@router.get("/tasks/{task_id}/result")
async def compat_result(task_id: str):
    import traceback
    from shared.database import get_database
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database not connected")
    try:
        resp = await get_task_result(task_id, db=db)

        # Build counts: lane_id -> {vehicle_type: count}
        counts = {}
        for s in resp.statistics:
            lane_id = s.lane_id
            if lane_id not in counts:
                counts[lane_id] = {}
            # LaneStatistics has counts dict: {"car": 5, "bus": 2}
            for vt, cnt in (s.counts or {}).items():
                counts[lane_id][vt] = counts[lane_id].get(vt, 0) + cnt

        return {
            "task_id": resp.task_id,
            "status": resp.status,
            "counts": counts,
            "total_count": resp.total_vehicles,
            "lane_volume_total": resp.lane_volume_total,
            "global_unique_count": resp.global_unique_count,
            "multi_lane_track_count": resp.multi_lane_track_count,
            "multi_lane_tracks": resp.multi_lane_tracks,
            "outputs": {"video_path": resp.result_video_url},
            "total_frames": 0,
            "frames": 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(tb)
        raise HTTPException(500, f"Result failed: {e}")
