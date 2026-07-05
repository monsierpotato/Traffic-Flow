from __future__ import annotations

from .primitives import Point, Segment

EPSILON = 1e-9


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    return (
        min(a[0], c[0]) - EPSILON <= b[0] <= max(a[0], c[0]) + EPSILON
        and min(a[1], c[1]) - EPSILON <= b[1] <= max(a[1], c[1]) + EPSILON
    )


def segments_intersect(first: Segment, second: Segment) -> bool:
    a, b = first
    c, d = second
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    if abs(o1) <= EPSILON and _on_segment(a, c, b):
        return True
    if abs(o2) <= EPSILON and _on_segment(a, d, b):
        return True
    if abs(o3) <= EPSILON and _on_segment(c, a, d):
        return True
    if abs(o4) <= EPSILON and _on_segment(c, b, d):
        return True
    return False
