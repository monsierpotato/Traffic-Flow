from importlib import import_module

from .primitives import Point, Segment, bbox_bottom_center, distance
from .intersection import segments_intersect
from .direction import dot_direction, vector

__all__ = [
    "Point",
    "Segment",
    "bbox_bottom_center",
    "distance",
    "segments_intersect",
    "point_in_polygon",
    "segment_midpoint_in_polygon",
    "dot_direction",
    "vector",
]


def __getattr__(name: str):
    if name in {"point_in_polygon", "segment_midpoint_in_polygon"}:
        polygon = import_module(f"{__name__}.polygon")
        return getattr(polygon, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
