from __future__ import annotations

from .primitives import Point, Segment


def vector(segment: Segment) -> Point:
    (x1, y1), (x2, y2) = segment
    return (x2 - x1, y2 - y1)


def dot_direction(movement: Segment, direction: Segment) -> float:
    mx, my = vector(movement)
    dx, dy = vector(direction)
    return mx * dx + my * dy
