from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class ImageSize:
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Image dimensions must be positive.")


@dataclass(frozen=True)
class AnnotationRoi:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ROI dimensions must be positive.")


def display_point_to_source(
    display_point: Point,
    *,
    display_size: ImageSize,
    source_size: ImageSize,
) -> Point:
    """Convert a point from rendered image coordinates to source image coordinates."""
    scale_x = source_size.width / display_size.width
    scale_y = source_size.height / display_size.height
    return (display_point[0] * scale_x, display_point[1] * scale_y)


def cropped_display_point_to_source(
    display_point: Point,
    *,
    display_size: ImageSize,
    roi: AnnotationRoi,
) -> Point:
    """Convert a point drawn on a rendered crop back to full-frame source coordinates."""
    crop_point = display_point_to_source(
        display_point,
        display_size=display_size,
        source_size=ImageSize(width=roi.width, height=roi.height),
    )
    return (roi.x + crop_point[0], roi.y + crop_point[1])


def cropped_display_points_to_source(
    display_points: Iterable[Point],
    *,
    display_size: ImageSize,
    roi: AnnotationRoi,
) -> List[Point]:
    return [
        cropped_display_point_to_source(point, display_size=display_size, roi=roi)
        for point in display_points
    ]
