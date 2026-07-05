from fastapi import APIRouter, Depends
from lib.database import get_database
from api.schemas.dashboard import DashboardStatsResponse, RecentTask

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(db = Depends(get_database)):
    """Aggregates metrics for the frontend control dashboard."""
    # 1. Counts of tasks by status
    total_tasks = await db.tasks.count_documents({})
    completed_tasks = await db.tasks.count_documents({"status": "completed"})
    failed_tasks = await db.tasks.count_documents({"status": "failed"})
    
    # "processing" states: pending + processing
    processing_tasks = await db.tasks.count_documents({"status": {"$in": ["pending", "processing"]}})

    # 2. Fetch 10 most recent tasks
    cursor = db.tasks.find({}).sort("created_at", -1).limit(10)
    recent_tasks_docs = await cursor.to_list(length=10)
    
    recent_tasks = [
        RecentTask(
            task_id=task["task_id"],
            status=task["status"],
            progress=task["progress"],
            created_at=task["created_at"]
        )
        for task in recent_tasks_docs
    ]

    # 3. Aggregate vehicle counts across all statistics by type
    pipeline = [
        {
            "$group": {
                "_id": "$vehicle_type",
                "total_count": {"$sum": "$count"}
            }
        }
    ]
    cursor_aggr = db.traffic_statistics.aggregate(pipeline)
    aggr_results = await cursor_aggr.to_list(length=100)

    vehicle_totals = {}
    for result in aggr_results:
        v_type = result["_id"]
        total_count = result["total_count"]
        if v_type:
            vehicle_totals[v_type] = total_count

    return DashboardStatsResponse(
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        failed_tasks=failed_tasks,
        processing_tasks=processing_tasks,
        recent_tasks=recent_tasks,
        vehicle_totals_by_type=vehicle_totals
    )
