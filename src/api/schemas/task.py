from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from api.schemas.lane import LaneConfigRequest

class TaskCreateRequest(BaseModel):
    video_id: str

class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    stage: Optional[str] = None
    stage_detail: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

class VehicleCountDetail(BaseModel):
    lane_id: str
    vehicle_type: str
    count: int
    direction: str

class TaskProgressCallback(BaseModel):
    status: str = Field(..., description="'processing' or 'completed' or 'failed'")
    progress: int = Field(..., description="0-100 progress percentage")
    stage: Optional[str] = None
    stage_detail: Optional[str] = None
    result_video_url: Optional[str] = None
    events_url: Optional[str] = None
    statistics: Optional[List[VehicleCountDetail]] = None
    lane_volume_total: Optional[int] = None
    global_unique_count: Optional[int] = None
    multi_lane_track_count: Optional[int] = None
    multi_lane_tracks: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None

class LaneStatistics(BaseModel):
    lane_id: str
    lane_name: str
    counts: Dict[str, int] = Field(default_factory=dict, description="Counts map: vehicle_type -> count")
    total: int

class TaskResultResponse(BaseModel):
    task_id: str
    status: str
    result_video_url: Optional[str] = None
    events_url: Optional[str] = None
    statistics: List[LaneStatistics]
    total_vehicles: int
    lane_volume_total: int = 0
    global_unique_count: int = 0
    multi_lane_track_count: int = 0
    multi_lane_tracks: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time_seconds: Optional[float] = None
    lane_config: Optional[LaneConfigRequest] = None
