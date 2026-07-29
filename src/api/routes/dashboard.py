from fastapi import APIRouter, Depends
from datetime import datetime
from api.dependencies import require_database
from api.schemas.dashboard import DashboardStatsResponse, RecentTask

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(db = Depends(require_database)):
    """Aggregates metrics for the frontend control dashboard."""
    # 1. Counts of tasks by status
    total_tasks = await db.tasks.count_documents({})
    completed_tasks = await db.tasks.count_documents({"status": {"$in": ["completed", "succeeded"]}})
    failed_tasks = await db.tasks.count_documents({"status": "failed"})
    
    # Include the states exposed by both the canonical task API and the
    # compatibility adapter. A configured task is not running yet, but it is
    # still active work from the operator's point of view.
    processing_tasks = await db.tasks.count_documents({"status": {"$in": ["configured", "queued", "pending", "processing"]}})

    # 2. Fetch 10 most recent tasks
    cursor = db.tasks.find({}).sort("created_at", -1).limit(10)
    recent_tasks_docs = await cursor.to_list(length=10)
    
    recent_tasks = []
    for task in recent_tasks_docs:
        task_id = task.get("task_id") or task.get("video_id")
        if not task_id:
            continue
        recent_tasks.append(
            RecentTask(
                task_id=task_id,
                status=task.get("status") or "unknown",
                progress=int(task.get("progress") or 0),
                created_at=task.get("created_at") or task.get("updated_at") or datetime.utcnow(),
            )
        )

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
        v_type = result.get("_id")
        total_count = int(result.get("total_count") or 0)
        # Some legacy worker payloads stored a summary row as vehicle_type
        # ``total``. It is not a vehicle class and must not leak into the
        # class breakdown shown by the dashboard.
        if v_type and str(v_type).lower() not in {"total", "all"} and total_count > 0:
            vehicle_totals[v_type] = total_count

    return DashboardStatsResponse(
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        failed_tasks=failed_tasks,
        processing_tasks=processing_tasks,
        recent_tasks=recent_tasks,
        vehicle_totals_by_type=vehicle_totals
    )
