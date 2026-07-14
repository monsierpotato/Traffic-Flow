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
    # 1. Verify that the video/task document exists
    task = await db.tasks.find_one({"video_id": payload.video_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No upload session found for video_id {payload.video_id}"
        )

    if not payload.lanes:
        raise HTTPException(status_code=400, detail="Must provide at least one lane.")

    # 3. Save Lane Config to MongoDB
    # We save exactly what the frontend passed (the advanced JSON schema)
    lane_config_doc = payload.model_dump()
    lane_config_doc["task_id"] = task["task_id"]
    lane_config_doc["created_at"] = datetime.utcnow()

    # Upsert lane config by video_id
    await db.lane_configs.update_one(
        {"video_id": payload.video_id},
        {"$set": lane_config_doc},
        upsert=True
    )

    # 4. Update task status to "configured"
    await db.tasks.update_one(
        {"video_id": payload.video_id},
        {
            "$set": {
                "status": "configured",
                "updated_at": datetime.utcnow()
            }
        }
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
