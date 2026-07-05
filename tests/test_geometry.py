from __future__ import annotations

from tfengine.geometry import (
    bbox_bottom_center,
    distance,
    dot_direction,
    point_in_polygon,
    segment_midpoint_in_polygon,
    segments_intersect,
    vector,
)


def test_bbox_bottom_center() -> None:
    assert bbox_bottom_center((10, 20, 30, 50)) == (20.0, 50.0)


def test_bbox_bottom_center_zero_width() -> None:
    assert bbox_bottom_center((10, 20, 10, 50)) == (10.0, 50.0)


def test_bbox_bottom_center_negative_coords() -> None:
    assert bbox_bottom_center((-10, -20, 10, 0)) == (0.0, 0.0)


def test_bbox_bottom_center_float_input() -> None:
    assert bbox_bottom_center((1.5, 2.5, 4.5, 10.5)) == (3.0, 10.5)


def test_distance() -> None:
    assert distance((0, 0), (3, 4)) == 5.0


def test_distance_zero() -> None:
    assert distance((5, 5), (5, 5)) == 0.0


def test_distance_negative() -> None:
    assert distance((-1, -1), (2, 3)) == 5.0


def test_segments_intersect() -> None:
    assert segments_intersect(((0, 0), (10, 10)), ((0, 10), (10, 0)))
    assert not segments_intersect(((0, 0), (1, 0)), ((0, 2), (1, 2)))


def test_segments_intersect_at_endpoint() -> None:
    assert segments_intersect(((0, 0), (5, 5)), ((5, 5), (10, 0)))


def test_segments_intersect_collinear_overlap() -> None:
    assert segments_intersect(((0, 0), (5, 5)), ((2, 2), (8, 8)))


def test_segments_intersect_collinear_no_overlap() -> None:
    assert not segments_intersect(((0, 0), (2, 2)), ((5, 5), (8, 8)))


def test_segments_intersect_touching_at_endpoint() -> None:
    assert segments_intersect(((0, 0), (5, 0)), ((5, 0), (10, 0)))


def test_segments_intersect_parallel_vertical() -> None:
    assert not segments_intersect(((0, 0), (0, 5)), ((2, 0), (2, 5)))


def test_vector() -> None:
    assert vector(((0, 0), (3, 4))) == (3, 4)


def test_vector_negative() -> None:
    assert vector(((5, 5), (2, 1))) == (-3, -4)


def test_dot_direction_aligned() -> None:
    result = dot_direction(((0, 0), (5, 0)), ((0, 0), (1, 0)))
    assert result > 0


def test_dot_direction_opposite() -> None:
    result = dot_direction(((0, 0), (5, 0)), ((1, 0), (0, 0)))
    assert result < 0


def test_dot_direction_perpendicular() -> None:
    result = dot_direction(((0, 0), (5, 0)), ((0, 0), (0, 5)))
    assert result == 0


def test_point_in_polygon_inside() -> None:
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 5), polygon) is True


def test_point_in_polygon_outside() -> None:
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((15, 15), polygon) is False


def test_point_in_polygon_on_edge() -> None:
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 0), polygon) is True


def test_point_in_polygon_include_edge_false() -> None:
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 0), polygon, include_edge=False) is False


def test_point_in_polygon_triangle() -> None:
    polygon = [(0, 0), (10, 0), (5, 10)]
    assert point_in_polygon((5, 5), polygon) is True
    assert point_in_polygon((5, -1), polygon) is False


def test_segment_midpoint_in_polygon() -> None:
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert segment_midpoint_in_polygon(((0, 0), (10, 10)), polygon) is True


def test_segment_midpoint_outside_polygon() -> None:
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert segment_midpoint_in_polygon(((20, 20), (30, 30)), polygon) is False
