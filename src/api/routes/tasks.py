from datetime import datetime
import os
import logging
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from shared.database import get_database
from shared.config import settings
from worker.celery_app import celery_app
from api.schemas.task import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskStatusResponse,
    TaskProgressCallback,
    TaskResultResponse,
    LaneStatistics
)

router = APIRouter()
logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "failed", "archived"}
PROCESSING_STATUSES = {"pending", "processing"}
ALLOWED_STATUS_TRANSITIONS = {
    "configured": {"pending", "failed"},
    "pending": {"pending", "processing", "failed"},
    "processing": {"processing", "completed", "failed"},
    "completed": {"completed"},
    "failed": {"failed"},
    "archived": {"archived"},
}


async def find_task(db, identifier: str):
    """Find a task by task_id or video_id."""
    task = await db.tasks.find_one({"task_id": identifier})
    if not task:
        task = await db.tasks.find_one({"video_id": identifier})
    return task


def _public_lane_config(lane_config: dict | None) -> dict | None:
    """Return a JSON-safe read snapshot without Mongo-only metadata."""
    if not lane_config:
        return None
    return {
        key: value
        for key, value in lane_config.items()
        if key not in {"_id", "created_at", "updated_at"}
    }

# Removed background_crop_and_enqueue

@router.post("/process", response_model=TaskCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def process_task(
    payload: TaskCreateRequest,
    request: Request,
    db = Depends(get_database)
):
    """Validate the configured task and enqueue it in Celery."""
    task = await db.tasks.find_one({"video_id": payload.video_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task or video session not found for video_id {payload.video_id}"
        )

    if task["status"] == "uploaded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lane configuration is required before processing. Please configure lanes first."
        )

    if task["status"] in PROCESSING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is already {task['status']}. Wait for it to complete."
        )

    if task["status"] in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task has already {task['status']}. Create a new upload to process again."
        )

    task_id = task["task_id"]

    lane_config = await db.lane_configs.find_one({"task_id": task_id})
    if not lane_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No lane configuration found. Please post config first."
        )

    # Keep callbacks explicit for the native worker; fallback to the request URL.
    callback_host = getattr(settings, "CALLBACK_HOST", None) or os.environ.get("CALLBACK_HOST", "")
    if callback_host:
        callback_url = f"{callback_host.rstrip('/')}/api/v1/tasks/progress/{task_id}"
    else:
        base_url = str(request.base_url)
        callback_url = f"{base_url.rstrip('/')}/api/v1/tasks/progress/{task_id}"

    claim = await db.tasks.update_one(
        {"task_id": task_id, "status": "configured"},
        {
            "$set": {
                "status": "pending",
                "progress": 0,
                "stage": "queued",
                "stage_detail": "Waiting for worker capacity",
                "updated_at": datetime.utcnow()
            }
        }
    )
    if getattr(claim, "matched_count", None) == 0:
        current = await db.tasks.find_one({"task_id": task_id})
        current_status = current.get("status") if current else "unknown"
        if current_status in PROCESSING_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task is already {current_status}. Wait for it to complete.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task was changed by another request. Refresh the task and try again.",
        )

    geometry_space = lane_config.get("geometry_space")
    if geometry_space is None:
        geometry_space = (
            "crop_local"
            if lane_config.get("crop_rect_padded") or lane_config.get("processing_width")
            else "source_frame"
        )

    serializable_config = {
        "version": lane_config.get("version", 1),
        "camera_id": lane_config.get("camera_id"),
        "resolution": lane_config.get("resolution"),
        "roi_polygon": lane_config.get("roi_polygon"),
        "processing_roi": lane_config.get("processing_roi"),
        "annotation_roi": lane_config.get("annotation_roi"),
        "crop_rect_padded": lane_config.get("crop_rect_padded"),
        "processing_width": lane_config.get("processing_width"),
        "processing_height": lane_config.get("processing_height"),
        "geometry_space": geometry_space,
        "method": lane_config.get("method", "counting_gate"),
        "settings": lane_config.get("settings"),
        "lanes": lane_config.get("lanes", []),
        "video_id": lane_config.get("video_id"),
        "task_id": lane_config.get("task_id"),
    }
    # Strip non-serializable MongoDB fields
    for k in ("_id", "created_at", "updated_at"):
        serializable_config.pop(k, None)
    
    # Directly enqueue task with original video URL and config
    # Use working (1080p) copy for processing; fallback to original
    process_video_url = task.get("working_video_url") or task["video_url"]

    try:
        celery_app.send_task(
            "trafficflow.process_video",
            args=[task_id, process_video_url, serializable_config, callback_url],
            task_id=task_id,
            queue=settings.CELERY_QUEUE_NAME,
        )
    except Exception as exc:
        logger.exception("Could not enqueue task %s", task_id)
        await db.tasks.update_one(
            {"task_id": task_id, "status": "pending"},
            {
                "$set": {
                    "status": "failed",
                    "progress": 0,
                    "stage": "queue_unavailable",
                    "stage_detail": "Redis/Celery worker is unavailable",
                    "error_message": f"Worker queue unavailable: {exc.__class__.__name__}",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker queue unavailable. Start native Redis and the Celery worker, then retry with a new upload.",
        ) from exc

    return TaskCreateResponse(
        task_id=task_id,
        status="pending",
        message="Task queued for processing."
    )

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    db = Depends(get_database)
):
    """Retrieves the current status and progress of a task."""
    task = await find_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found."
        )

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress"],
        stage=task.get("stage"),
        stage_detail=task.get("stage_detail"),
        created_at=task["created_at"],
        updated_at=task["updated_at"],
        error_message=task.get("error_message")
    )

@router.put("/progress/{task_id}", status_code=status.HTTP_200_OK)
async def task_progress_callback(
    task_id: str,
    payload: TaskProgressCallback,
    request: Request,
    db = Depends(get_database)
):
    """Endpoint for Worker to report progress updates, failures, or completion."""
    if settings.CALLBACK_TOKEN:
        supplied = request.headers.get("authorization", "")
        if supplied != f"Bearer {settings.CALLBACK_TOKEN}":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid callback token")
    task = await db.tasks.find_one({"task_id": task_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found."
        )

    current_status = task.get("status", "")
    allowed_statuses = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid task status transition: {current_status} -> {payload.status}",
        )
    current_progress = int(task.get("progress", 0) or 0)
    if payload.progress < current_progress and payload.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task progress cannot move backwards.",
        )

    update_fields = {
        "status": payload.status,
        "progress": payload.progress,
        "stage": payload.stage,
        "stage_detail": payload.stage_detail,
        "updated_at": datetime.utcnow()
    }

    if payload.error_message:
        update_fields["error_message"] = payload.error_message

    if payload.status == "completed":
        update_fields["result_video_url"] = payload.result_video_url
        update_fields["events_url"] = payload.events_url
        update_fields["lane_volume_total"] = payload.lane_volume_total
        update_fields["global_unique_count"] = payload.global_unique_count
        update_fields["multi_lane_track_count"] = payload.multi_lane_track_count
        update_fields["multi_lane_tracks"] = payload.multi_lane_tracks

    # Keep the read/validate/update sequence safe against two workers racing
    # to report progress. MongoDB and the local fallback both support these
    # comparison operators.
    update_query = {"task_id": task_id, "status": current_status}
    if payload.status != "failed":
        update_query["progress"] = {"$lte": current_progress if payload.progress < current_progress else payload.progress}
    update_result = await db.tasks.update_one(
        update_query,
        {"$set": update_fields}
    )
    if getattr(update_result, "matched_count", None) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task changed while progress was being reported; retry the callback.",
        )

    if payload.status == "completed" and payload.statistics:
        await db.traffic_statistics.delete_many({"task_id": task_id})
        stat_docs = [
            {
                "task_id": task_id,
                "lane_id": stat.lane_id,
                "vehicle_type": stat.vehicle_type,
                "count": stat.count,
                "direction": stat.direction,
                "created_at": datetime.utcnow(),
            }
            for stat in payload.statistics
        ]
        if stat_docs:
            await db.traffic_statistics.insert_many(stat_docs)

    return {"status": "success", "message": "Task progress updated successfully."}

@router.get("/result/{task_id}", response_model=TaskResultResponse)
async def get_task_result(
    task_id: str,
    db = Depends(get_database)
):
    """Retrieves final video result URL, log file URL, and aggregated statistics."""
    task = await find_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found."
        )

    actual_task_id = task["task_id"]

    if task["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is in status '{task['status']}' and has not completed yet."
        )

    # Fetch Lane config to get lane names mapping
    lane_config = await db.lane_configs.find_one({
        "$or": [{"task_id": actual_task_id}, {"video_id": task.get("video_id")}]
    })
    lane_names = {}
    if lane_config:
        for lane in lane_config.get("lanes", []):
            lane_names[lane["lane_id"]] = lane.get("name", lane["lane_id"])

    # Fetch and aggregate statistics
    cursor = db.traffic_statistics.find({"task_id": actual_task_id})
    stats_list = await cursor.to_list(length=1000)

    # Aggregate vehicle counts by lane
    # Structure: lane_id -> { vehicle_type -> total_count }
    aggregated: Dict[str, Dict[str, int]] = {}
    for stat in stats_list:
        lane_id = stat["lane_id"]
        v_type = stat["vehicle_type"]
        cnt = stat["count"]
        
        if lane_id not in aggregated:
            aggregated[lane_id] = {}
        
        aggregated[lane_id][v_type] = aggregated[lane_id].get(v_type, 0) + cnt

    # Format result response statistics
    result_statistics: List[LaneStatistics] = []
    total_vehicles = 0
    
    for lane_id, counts_map in aggregated.items():
        lane_name = lane_names.get(lane_id, f"Lane {lane_id}")
        lane_total = sum(counts_map.values())
        total_vehicles += lane_total
        
        result_statistics.append(
            LaneStatistics(
                lane_id=lane_id,
                lane_name=lane_name,
                counts=counts_map,
                total=lane_total
            )
        )

    # Calculate processing time from created_at and updated_at
    proc_time = None
    if task.get("created_at") and task.get("updated_at"):
        proc_time = (task["updated_at"] - task["created_at"]).total_seconds()

    return TaskResultResponse(
        task_id=task["task_id"],
        status=task["status"],
        result_video_url=task.get("result_video_url"),
        events_url=task.get("events_url"),
        statistics=result_statistics,
        total_vehicles=task.get("global_unique_count") or total_vehicles,
        lane_volume_total=task.get("lane_volume_total") or total_vehicles,
        global_unique_count=task.get("global_unique_count") or total_vehicles,
        multi_lane_track_count=task.get("multi_lane_track_count") or 0,
        multi_lane_tracks=task.get("multi_lane_tracks") or [],
        processing_time_seconds=proc_time,
        lane_config=_public_lane_config(lane_config)
    )
