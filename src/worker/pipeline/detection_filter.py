"""Detection filters used before local tracking."""

from __future__ import annotations

from typing import Iterable, List, Sequence

import cv2
import numpy as np

from worker.services.counting_service import bbox_bottom_center, point_in_polygon


def _padded_polygon(points: Sequence[Sequence[float]], padding_px: float) -> list[list[float]]:
    if not points or padding_px <= 0 or len(points) < 3:
        return [[float(p[0]), float(p[1])] for p in points]
    poly = np.array(points, dtype=np.float32)
    centroid = poly.mean(axis=0)
    vectors = poly - centroid
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    lengths[lengths == 0] = 1.0
    expanded = poly + vectors / lengths * float(padding_px)
    hull = cv2.convexHull(expanded.astype(np.float32)).reshape(-1, 2)
    return [[float(x), float(y)] for x, y in hull]


def filter_detections_for_tracking(detections: Iterable[dict], lanes: list[dict], padding_px: float = 0.0) -> list[dict]:
    """Keep only detections whose bottom-center anchor belongs to a lane zone/class."""
    if not lanes:
        return list(detections)

    lane_filters = []
    for lane in lanes:
        zone = lane.get("valid_zone") or []
        if len(zone) < 3:
            continue
        lane_filters.append({
            "zone": _padded_polygon(zone, padding_px),
            "allowed": set(lane.get("class_allowed") or []),
        })
    if not lane_filters:
        return list(detections)

    kept: List[dict] = []
    for det in detections:
        bbox = det.get("bbox_xyxy") or []
        if len(bbox) != 4:
            continue
        anchor = bbox_bottom_center(bbox)
        class_name = det.get("class_name")
        for lane_filter in lane_filters:
            if not point_in_polygon(anchor[0], anchor[1], lane_filter["zone"]):
                continue
            allowed = lane_filter["allowed"]
            if allowed and class_name not in allowed:
                continue
            kept.append(det)
            break
    return kept
