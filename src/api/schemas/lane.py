from typing import List, Optional, Any
from pydantic import BaseModel, Field

class Resolution(BaseModel):
    width: int
    height: int

class AnnotationROI(BaseModel):
    type: str
    x: float
    y: float
    width: float
    height: float
    purpose: str

class Settings(BaseModel):
    movement_threshold_px: float
    cooldown_frames: int
    cooldown_distance_px: float
    zone_policy: str

class AdvancedLane(BaseModel):
    lane_id: str
    valid_zone: List[List[float]]
    counting_line: List[List[float]]
    direction: List[List[float]]
    class_allowed: List[str]

class LaneConfigRequest(BaseModel):
    video_id: str
    version: int = 1
    camera_id: str
    resolution: Resolution
    roi_polygon: List[List[float]]
    annotation_roi: AnnotationROI
    method: str = "counting_gate"
    settings: Settings
    lanes: List[AdvancedLane]

class LaneConfigResponse(BaseModel):
    video_id: str
    lane_count: int
    message: str
