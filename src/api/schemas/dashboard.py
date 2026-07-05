from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class RecentTask(BaseModel):
    task_id: str
    status: str
    progress: int
    created_at: datetime

class DashboardStatsResponse(BaseModel):
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    processing_tasks: int
    recent_tasks: List[RecentTask]
    vehicle_totals_by_type: Dict[str, int]
