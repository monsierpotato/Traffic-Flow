from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

from .primitives import Point, Segment


def point_in_polygon(point: Point, polygon: Sequence[Point], include_edge: bool = True) -> bool:
    contour = np.asarray(polygon, dtype=np.float32)
    result = cv2.pointPolygonTest(contour, point, False)
    return result >= 0 if include_edge else result > 0


def segment_midpoint_in_polygon(segment: Segment, polygon: Sequence[Point]) -> bool:
    (x1, y1), (x2, y2) = segment
    return point_in_polygon(((x1 + x2) / 2.0, (y1 + y2) / 2.0), polygon)
