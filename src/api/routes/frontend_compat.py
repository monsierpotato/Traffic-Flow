"""Compatibility routes matching frontend's expected API endpoints."""

import logging
import os
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, Response

from shared.database import get_database
from shared.config import settings
from api.middleware.file_validator import validate_video_file
from api.services.upload_service import create_uploaded_video_task_from_path, save_upload_to_temp
from api.schemas.task import TaskCreateRequest
from api.routes.tasks import process_task, get_task_status, get_task_result
from shared.r2_client import r2_client
from api.security import require_database

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/videos")
async def compat_upload(request: Request, file: UploadFile = File(...)):
    file = validate_video_file(file)
    db = require_database(get_database())

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
    preview = Path(settings.STORAGE_DIR) / "previews" / f"{task_id}.jpg"
    if preview.exists():
        return FileResponse(str(preview), media_type="image/jpeg")
    try:
        return Response(content=r2_client.download_file(f"previews/{task_id}.jpg"), media_type="image/jpeg")
    except Exception as exc:
        raise HTTPException(404, "Preview not found") from exc


@router.post("/tasks")
async def compat_submit(request: Request, payload: dict):
    video_id = payload.get("task_id") or payload.get("video_id", "")
    lane_config = payload.get("lane_config")

    if not video_id:
        raise HTTPException(400, "task_id or video_id required")
    db = require_database(get_database())

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
        req = TaskCreateRequest(video_id=video_id)
        resp = await process_task(req, request, db=db)
        return {"task_id": resp.task_id, "status": resp.status, "progress": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Compatibility task submission failed for video %s", video_id)
        raise HTTPException(500, "Process failed") from e


@router.get("/tasks/{task_id}")
async def compat_status(task_id: str):
    from shared.database import get_database
    db = require_database(get_database())
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
            "events_url": resp.events_url,
            "total_frames": 0,
            "frames": 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Compatibility result lookup failed for task %s", task_id)
        raise HTTPException(500, "Result lookup failed") from e
