"""Compatibility routes matching frontend's expected API endpoints."""

import logging
import os
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from shared.database import get_database
from shared.config import settings
from api.middleware.file_validator import validate_video_file
from api.services.upload_service import create_uploaded_video_task_from_path, save_upload_to_temp
from api.schemas.task import TaskCreateRequest
from api.schemas.lane import LaneConfigRequest
from api.routes.tasks import find_task, process_task, get_task_status, get_task_result

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/videos")
async def compat_upload(file: UploadFile = File(...)):
    file = validate_video_file(file)
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database not connected")

    temp_path = await save_upload_to_temp(file)
    try:
        uploaded = await create_uploaded_video_task_from_path(
            db=db,
            video_path=temp_path,
            content_type=file.content_type or "video/mp4",
        )
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    return {
        # Keep the resource identifiers distinct. Older clients used video_id
        # as task_id, which made the adapter appear to work while hiding ID
        # mismatches between the API, database, and Celery worker.
        "task_id": uploaded.task_id,
        "video_id": uploaded.video_id,
        "status": "uploaded",
        "preview_url": uploaded.preview_url,
        "working_video_url": uploaded.task_doc["working_video_url"],
        "original_resolution": uploaded.task_doc["original_resolution"],
        "working_resolution": uploaded.task_doc["working_resolution"],
    }


@router.get("/videos/{task_id}/preview")
async def compat_preview(task_id: str):
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database not connected")
    task = await find_task(db, task_id)
    video_id = task.get("video_id") if task else task_id
    preview = Path(settings.STORAGE_DIR) / "previews" / f"{video_id}.jpg"
    if preview.exists():
        return FileResponse(str(preview), media_type="image/jpeg")
    if task and task.get("preview_url"):
        return RedirectResponse(task["preview_url"], status_code=307)
    raise HTTPException(404, "Preview not found")


@router.post("/tasks")
async def compat_submit(request: Request, payload: dict):
    identifier = payload.get("task_id") or payload.get("video_id", "")
    lane_config = payload.get("lane_config")

    if not identifier:
        raise HTTPException(400, "task_id or video_id required")
    db = get_database()
    if db is None:
        raise HTTPException(503, "Database not connected")

    # Check if task exists
    task = await find_task(db, identifier)
    if not task:
        raise HTTPException(404, f"No upload session found for {identifier}")

    task_id = task["task_id"]
    video_id = task["video_id"]

    # Save lane config if provided by frontend
    if lane_config:
        cfg = dict(lane_config)
        cfg["video_id"] = video_id
        try:
            # The compatibility endpoint receives an untyped JSON body, so it
            # must apply the same contract as /api/v1/lanes/config before the
            # document can reach the worker.
            validated_cfg = LaneConfigRequest.model_validate(cfg)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Invalid lane configuration") from exc

        cfg = validated_cfg.model_dump()
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
        req = TaskCreateRequest(video_id=video_id)
        resp = await process_task(req, request, db=db)
        return {"task_id": resp.task_id, "status": resp.status, "progress": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Compatibility task submission failed")
        raise HTTPException(500, "Process failed while submitting the task") from e


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
        logger.exception("Compatibility result lookup failed")
        raise HTTPException(500, "Result could not be loaded") from e
