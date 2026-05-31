from __future__ import annotations

from trafficflow.geometry import bbox_bottom_center, segments_intersect


def test_bbox_bottom_center() -> None:
    assert bbox_bottom_center((10, 20, 30, 50)) == (20.0, 50.0)


def test_segments_intersect() -> None:
    assert segments_intersect(((0, 0), (10, 10)), ((0, 10), (10, 0)))
    assert not segments_intersect(((0, 0), (1, 0)), ((0, 2), (1, 2)))
