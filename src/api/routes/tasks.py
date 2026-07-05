from datetime import datetime
import asyncio
import urllib.request
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from lib.database import get_database, db_instance
from lib.config import settings
from worker.celery_app import celery_app
from lib.r2_client import r2_client
from api.services.video_service import crop_video
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


async def find_task(db, identifier: str):
    """Find a task by task_id or video_id."""
    task = await db.tasks.find_one({"task_id": identifier})
    if not task:
        task = await db.tasks.find_one({"video_id": identifier})
    return task

# Removed background_crop_and_enqueue

@router.post("/process", response_model=TaskCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def process_task(
    payload: TaskCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db = Depends(get_database)
):
    """Triggers the video processing task, crops video, and enqueues it in Celery."""
    task = await db.tasks.find_one({"video_id": payload.video_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task or video session not found for video_id {payload.video_id}"
        )

    TERMINAL_STATUSES = {"completed", "failed", "archived"}
    PROCESSING_STATUSES = {"pending", "processing"}

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

    base_url = str(request.base_url)
    callback_url = f"{base_url.rstrip('/')}/api/v1/tasks/progress/{task_id}"

    await db.tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                "status": "pending",
                "progress": 0,
                "updated_at": datetime.utcnow()
            }
        }
    )

    serializable_config = {
        "version": lane_config.get("version", 1),
        "camera_id": lane_config.get("camera_id"),
        "resolution": lane_config.get("resolution"),
        "roi_polygon": lane_config.get("roi_polygon"),
        "annotation_roi": lane_config.get("annotation_roi"),
        "method": lane_config.get("method", "counting_gate"),
        "settings": lane_config.get("settings"),
        "lanes": lane_config.get("lanes", []),
        "video_id": lane_config.get("video_id")
    }
    
    # Directly enqueue task with original video URL and config
    celery_app.send_task(
        "trafficflow.process_video",
        args=[task_id, task["video_url"], serializable_config, callback_url],
        task_id=task_id,
        queue="trafficflow_queue"
    )

    return TaskCreateResponse(
        task_id=task_id,
        status="pending",
        message="Task is being cropped and queued for processing."
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
        created_at=task["created_at"],
        updated_at=task["updated_at"],
        error_message=task.get("error_message")
    )

@router.put("/progress/{task_id}", status_code=status.HTTP_200_OK)
async def task_progress_callback(
    task_id: str,
    payload: TaskProgressCallback,
    db = Depends(get_database)
):
    """Endpoint for Worker to report progress updates, failures, or completion."""
    task = await db.tasks.find_one({"task_id": task_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found."
        )

    update_fields = {
        "status": payload.status,
        "progress": payload.progress,
        "updated_at": datetime.utcnow()
    }

    if payload.error_message:
        update_fields["error_message"] = payload.error_message

    if payload.status == "completed":
        update_fields["result_video_url"] = payload.result_video_url
        update_fields["events_url"] = payload.events_url

        # Insert stats to DB if provided
        if payload.statistics:
            # Clear previous stats for this task if any
            await db.traffic_statistics.delete_many({"task_id": task_id})
            
            # Prepare statistic records
            stat_docs = []
            for stat in payload.statistics:
                stat_docs.append({
                    "task_id": task_id,
                    "lane_id": stat.lane_id,
                    "vehicle_type": stat.vehicle_type,
                    "count": stat.count,
                    "direction": stat.direction,
                    "created_at": datetime.utcnow()
                })
            
            if stat_docs:
                await db.traffic_statistics.insert_many(stat_docs)

    # Perform task document update
    await db.tasks.update_one(
        {"task_id": task_id},
        {"$set": update_fields}
    )

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
        total_vehicles=total_vehicles,
        processing_time_seconds=proc_time,
        lane_config=lane_config
    )
