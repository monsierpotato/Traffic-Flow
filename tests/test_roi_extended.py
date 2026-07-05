from __future__ import annotations

import pytest

from tfengine.geometry.roi import (
    AnnotationRoi,
    ImageSize,
    cropped_display_point_to_source,
    cropped_display_points_to_source,
    display_point_to_source,
)


def test_image_size_positive() -> None:
    size = ImageSize(width=1920, height=1080)
    assert size.width == 1920
    assert size.height == 1080


def test_image_size_zero_width_raises() -> None:
    with pytest.raises(ValueError, match="Image dimensions must be positive"):
        ImageSize(width=0, height=1080)


def test_image_size_zero_height_raises() -> None:
    with pytest.raises(ValueError, match="Image dimensions must be positive"):
        ImageSize(width=1920, height=0)


def test_image_size_negative_width_raises() -> None:
    with pytest.raises(ValueError, match="Image dimensions must be positive"):
        ImageSize(width=-1, height=1080)


def test_annotation_roi_positive() -> None:
    roi = AnnotationRoi(x=100, y=200, width=800, height=600)
    assert roi.x == 100
    assert roi.y == 200
    assert roi.width == 800
    assert roi.height == 600


def test_annotation_roi_zero_width_raises() -> None:
    with pytest.raises(ValueError, match="ROI dimensions must be positive"):
        AnnotationRoi(x=0, y=0, width=0, height=600)


def test_annotation_roi_negative_height_raises() -> None:
    with pytest.raises(ValueError, match="ROI dimensions must be positive"):
        AnnotationRoi(x=0, y=0, width=800, height=-1)


def test_display_point_to_source_no_scale_change() -> None:
    point = display_point_to_source(
        (100, 200),
        display_size=ImageSize(width=1920, height=1080),
        source_size=ImageSize(width=1920, height=1080),
    )
    assert point == (100, 200)


def test_display_point_to_source_downscale() -> None:
    point = display_point_to_source(
        (100, 100),
        display_size=ImageSize(width=1920, height=1080),
        source_size=ImageSize(width=640, height=360),
    )
    assert point == pytest.approx((33.33, 33.33), rel=0.01)


def test_cropped_display_point_to_source_no_scale() -> None:
    point = cropped_display_point_to_source(
        (100, 50),
        display_size=ImageSize(width=900, height=400),
        roi=AnnotationRoi(x=400, y=300, width=900, height=400),
    )
    assert point == (500, 350)


def test_cropped_display_point_to_source_origin_only() -> None:
    point = cropped_display_point_to_source(
        (0, 0),
        display_size=ImageSize(width=900, height=400),
        roi=AnnotationRoi(x=400, y=300, width=900, height=400),
    )
    assert point == (400, 300)


def test_cropped_display_points_to_source_empty() -> None:
    points = cropped_display_points_to_source(
        [],
        display_size=ImageSize(width=900, height=400),
        roi=AnnotationRoi(x=400, y=300, width=900, height=400),
    )
    assert points == []


def test_cropped_display_points_to_source_single() -> None:
    points = cropped_display_points_to_source(
        [(0, 0)],
        display_size=ImageSize(width=900, height=400),
        roi=AnnotationRoi(x=400, y=300, width=900, height=400),
    )
    assert points == [(400, 300)]
