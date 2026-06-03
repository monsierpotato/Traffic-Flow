from trafficflow.geometry.roi import (
    AnnotationRoi,
    ImageSize,
    cropped_display_point_to_source,
    cropped_display_points_to_source,
    display_point_to_source,
)


def test_display_point_to_source_scales_full_frame_coordinates():
    point = display_point_to_source(
        (400, 225),
        display_size=ImageSize(width=800, height=450),
        source_size=ImageSize(width=1920, height=1080),
    )

    assert point == (960, 540)


def test_cropped_display_point_to_source_offsets_by_roi_origin():
    point = cropped_display_point_to_source(
        (120, 80),
        display_size=ImageSize(width=900, height=400),
        roi=AnnotationRoi(x=400, y=300, width=900, height=400),
    )

    assert point == (520, 380)


def test_cropped_display_point_to_source_scales_resized_crop():
    point = cropped_display_point_to_source(
        (450, 200),
        display_size=ImageSize(width=900, height=400),
        roi=AnnotationRoi(x=400, y=300, width=1800, height=800),
    )

    assert point == (1300, 700)


def test_cropped_display_points_to_source_converts_multiple_points():
    points = cropped_display_points_to_source(
        [(0, 0), (450, 200)],
        display_size=ImageSize(width=900, height=400),
        roi=AnnotationRoi(x=400, y=300, width=900, height=400),
    )

    assert points == [(400, 300), (850, 500)]
