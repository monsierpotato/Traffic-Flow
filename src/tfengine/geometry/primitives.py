from __future__ import annotations

from math import hypot
from typing import Sequence, Tuple

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


def bbox_bottom_center(bbox_xyxy: Sequence[float]) -> Point:
    x1, _y1, x2, y2 = bbox_xyxy
    return ((float(x1) + float(x2)) / 2.0, float(y2))


def distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])
