from __future__ import annotations

from math import isfinite
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, FiniteFloat, field_validator, model_validator


Point = List[FiniteFloat]


def _validate_points(points: list[list[float]], *, name: str, minimum: int, exact: int | None = None) -> list[list[float]]:
    expected = f"exactly {exact}" if exact is not None else f"at least {minimum}"
    if (exact is not None and len(points) != exact) or (exact is None and len(points) < minimum):
        raise ValueError(f"{name} must contain {expected} points")
    for point in points:
        if len(point) != 2 or not all(isfinite(float(value)) for value in point):
            raise ValueError(f"{name} points must contain two finite coordinates")
    return points


def _validate_geometry_bounds(points: list[list[float]], width: float, height: float, name: str) -> None:
    for point in points:
        if not (0 <= point[0] <= width and 0 <= point[1] <= height):
            raise ValueError(f"{name} point {point} is outside {width:g}x{height:g} bounds")


class Resolution(BaseModel):
    width: int = Field(..., gt=0, le=32768)
    height: int = Field(..., gt=0, le=32768)


class ProcessingROI(BaseModel):
    type: str = Field(..., min_length=1, max_length=40)
    x: FiniteFloat = Field(..., ge=0)
    y: FiniteFloat = Field(..., ge=0)
    width: FiniteFloat = Field(..., gt=0)
    height: FiniteFloat = Field(..., gt=0)
    purpose: str = Field(..., min_length=1, max_length=80)


class Settings(BaseModel):
    movement_threshold_px: FiniteFloat = Field(..., ge=0, le=10000)
    cooldown_frames: int = Field(..., ge=0, le=100000)
    cooldown_distance_px: FiniteFloat = Field(..., ge=0, le=100000)
    zone_policy: Literal["strict", "flexible"]


class AdvancedLane(BaseModel):
    lane_id: str = Field(..., min_length=1, max_length=100)
    valid_zone: list[Point]
    counting_line: list[Point]
    direction: list[Point]
    class_allowed: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("lane_id")
    @classmethod
    def lane_id_must_be_safe(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("lane_id must not be empty")
        return value

    @field_validator("valid_zone")
    @classmethod
    def validate_zone(cls, value: list[Point]) -> list[Point]:
        return _validate_points(value, name="valid_zone", minimum=3)

    @field_validator("counting_line", "direction")
    @classmethod
    def validate_segments(cls, value: list[Point], info) -> list[Point]:
        return _validate_points(value, name=info.field_name, minimum=2, exact=2)

    @field_validator("class_allowed")
    @classmethod
    def validate_classes(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip().lower() for item in value if item and item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("class_allowed must not contain duplicates")
        return cleaned

    @model_validator(mode="after")
    def reject_degenerate_geometry(self) -> "AdvancedLane":
        if self.counting_line[0] == self.counting_line[1]:
            raise ValueError("counting_line must have non-zero length")
        if self.direction[0] == self.direction[1]:
            raise ValueError("direction must have non-zero length")
        return self


class LaneConfigRequest(BaseModel):
    video_id: str = Field(..., min_length=1, max_length=100)
    version: int = Field(default=1, ge=1)
    camera_id: str = Field(..., min_length=1, max_length=200)
    resolution: Resolution
    roi_polygon: list[Point]
    processing_roi: Optional[ProcessingROI] = None
    annotation_roi: Optional[ProcessingROI] = None
    geometry_space: Optional[Literal["source_frame", "crop_local"]] = None
    method: str = Field(default="counting_gate", min_length=1, max_length=60)
    settings: Settings
    lanes: list[AdvancedLane] = Field(..., min_length=1, max_length=64)

    @field_validator("roi_polygon")
    @classmethod
    def validate_roi_polygon(cls, value: list[Point]) -> list[Point]:
        return _validate_points(value, name="roi_polygon", minimum=3)

    @model_validator(mode="after")
    def validate_geometry(self) -> "LaneConfigRequest":
        if not self.processing_roi and not self.annotation_roi:
            raise ValueError("processing_roi or annotation_roi is required")

        roi = self.processing_roi or self.annotation_roi
        assert roi is not None
        if roi.x + roi.width > self.resolution.width or roi.y + roi.height > self.resolution.height:
            raise ValueError("processing ROI exceeds the source resolution")

        if self.geometry_space == "crop_local":
            geometry_width, geometry_height = roi.width, roi.height
        else:
            geometry_width, geometry_height = self.resolution.width, self.resolution.height

        _validate_geometry_bounds(self.roi_polygon, self.resolution.width, self.resolution.height, "roi_polygon")
        for index, lane in enumerate(self.lanes, start=1):
            _validate_geometry_bounds(lane.valid_zone, geometry_width, geometry_height, f"lane {index}.valid_zone")
            _validate_geometry_bounds(lane.counting_line, geometry_width, geometry_height, f"lane {index}.counting_line")
            _validate_geometry_bounds(lane.direction, geometry_width, geometry_height, f"lane {index}.direction")

        lane_ids = [lane.lane_id for lane in self.lanes]
        if len(lane_ids) != len(set(lane_ids)):
            raise ValueError("lane_id values must be unique")
        return self


class LaneConfigResponse(BaseModel):
    video_id: str
    lane_count: int
    message: str
