from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


Point = Annotated[List[float], Field(min_length=2, max_length=2)]


class Resolution(BaseModel):
    width: int = Field(..., gt=0, le=16384)
    height: int = Field(..., gt=0, le=16384)


class ProcessingROI(BaseModel):
    type: str = Field(..., min_length=1, max_length=50)
    x: float = Field(..., ge=0)
    y: float = Field(..., ge=0)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    purpose: str = Field(..., min_length=1, max_length=100)


class Settings(BaseModel):
    movement_threshold_px: float = Field(..., ge=0, le=10000)
    cooldown_frames: int = Field(..., ge=0, le=100000)
    cooldown_distance_px: float = Field(..., ge=0, le=10000)
    zone_policy: str = Field(..., min_length=1, max_length=50)


class AdvancedLane(BaseModel):
    lane_id: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    name: Optional[str] = Field(default=None, max_length=200)
    valid_zone: List[Point] = Field(..., min_length=3, max_length=100)
    counting_line: List[Point] = Field(..., min_length=2, max_length=2)
    direction: List[Point] = Field(..., min_length=2, max_length=2)
    class_allowed: List[str] = Field(..., min_length=1, max_length=32)


class LaneConfigRequest(BaseModel):
    video_id: str = Field(..., min_length=1, max_length=200)
    version: int = Field(default=1, ge=1, le=100)
    camera_id: str = Field(..., min_length=1, max_length=200)
    resolution: Resolution
    roi_polygon: List[Point] = Field(..., min_length=3, max_length=200)
    processing_roi: Optional[ProcessingROI] = None
    annotation_roi: Optional[ProcessingROI] = None
    geometry_space: Optional[Literal["source_frame", "crop_local"]] = None
    method: str = Field(default="counting_gate", min_length=1, max_length=100)
    settings: Settings
    lanes: List[AdvancedLane] = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_geometry(self):
        if not (self.processing_roi or self.annotation_roi):
            raise ValueError("processing_roi or annotation_roi is required")
        lane_ids = [lane.lane_id for lane in self.lanes]
        if len(lane_ids) != len(set(lane_ids)):
            raise ValueError("lane_id values must be unique")

        if self.geometry_space == "crop_local":
            roi = self.processing_roi or self.annotation_roi
            bounds = (roi.width, roi.height) if roi else (self.resolution.width, self.resolution.height)
        else:
            bounds = (self.resolution.width, self.resolution.height)

        def check_points(label: str, points: list[Point]) -> None:
            for point in points:
                if point[0] > bounds[0] or point[1] > bounds[1]:
                    raise ValueError(f"{label} contains a point outside configured bounds")

        check_points("roi_polygon", self.roi_polygon)
        for lane in self.lanes:
            check_points(f"lane {lane.lane_id}.valid_zone", lane.valid_zone)
            check_points(f"lane {lane.lane_id}.counting_line", lane.counting_line)
            check_points(f"lane {lane.lane_id}.direction", lane.direction)
        return self


class LaneConfigResponse(BaseModel):
    video_id: str
    lane_count: int
    message: str
