from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from shared.database import get_database
from api.schemas.lane import LaneConfigRequest, LaneConfigResponse

router = APIRouter()

@router.post("/config", response_model=LaneConfigResponse, status_code=status.HTTP_200_OK)
async def configure_lanes(
    payload: LaneConfigRequest,
    db = Depends(get_database)
):
    """Saves ROI and Lane configurations for a video."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not connected")
    # 1. Verify that the video/task document exists
    task = await db.tasks.find_one({"video_id": payload.video_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No upload session found for video_id {payload.video_id}"
        )

    task_id = task.get("task_id")
    if not task_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload session has no canonical task_id and cannot be configured.",
        )
    if task.get("status") not in {"uploaded", "configured"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lane configuration cannot be changed while task is {task.get('status', 'unknown')}.",
        )

    if not payload.lanes:
        raise HTTPException(status_code=400, detail="Must provide at least one lane.")

    # 3. Save Lane Config to MongoDB
    # We save exactly what the frontend passed (the advanced JSON schema)
    lane_config_doc = payload.model_dump()
    lane_config_doc["task_id"] = task_id
    lane_config_doc["created_at"] = datetime.utcnow()

    # Upsert lane config by video_id
    await db.lane_configs.update_one(
        {"video_id": payload.video_id},
        {"$set": lane_config_doc},
        upsert=True
    )

    # 4. Update task status to "configured" without reverting a task that was
    # claimed by the worker while the config write was in flight.
    claim = await db.tasks.update_one(
        {"task_id": task_id, "status": {"$in": ["uploaded", "configured"]}},
        {
            "$set": {
                "status": "configured",
                "updated_at": datetime.utcnow()
            }
        }
    )
    if getattr(claim, "matched_count", None) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task changed while lane configuration was being saved; refresh and retry.",
        )

    return LaneConfigResponse(
        video_id=payload.video_id,
        lane_count=len(payload.lanes),
        message="Lane configuration saved and task is ready to process."
    )

@router.get("/config/{video_id}", response_model=LaneConfigRequest, status_code=status.HTTP_200_OK)
async def get_lane_config(
    video_id: str,
    db = Depends(get_database)
):
    """Retrieves the Lane configurations for a video (accepts video_id or task_id)."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not connected")
    lane_config = await db.lane_configs.find_one({
        "$or": [
            {"video_id": video_id},
            {"task_id": video_id}
        ]
    })
    if not lane_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lane configuration not found for video_id or task_id {video_id}"
        )
    return lane_config
