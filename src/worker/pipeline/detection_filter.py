"""Shared detection filtering for live and batch tracking paths."""

from __future__ import annotations

import copy
from collections.abc import Iterable

import cv2
import numpy as np


def _point_in_zone(point: tuple[float, float], zone: Iterable[Iterable[float]], padding: float) -> bool:
    points = list(zone or [])
    if len(points) < 3:
        return True
    polygon = np.asarray(points, dtype=np.float32).reshape((-1, 1, 2))
    if padding > 0:
        center = np.mean(polygon[:, 0, :], axis=0)
        x, y, width, height = cv2.boundingRect(polygon.astype(np.int32))
        scale = 1.0 + (2.0 * padding / max(float(max(width, height)), 1.0))
        polygon = (polygon - center) * scale + center
    return cv2.pointPolygonTest(polygon, point, False) >= 0


def filter_detections_for_tracking(
    detections: list[dict], lanes: list[dict], padding_px: float = 0.0,
) -> list[dict]:
    """Keep detections whose bottom-center anchor is inside a lane zone."""
    zones = [lane.get("valid_zone") for lane in lanes or [] if lane.get("valid_zone")]
    if not zones:
        return detections or []

    filtered: list[dict] = []
    for detection in detections or []:
        bbox = detection.get("bbox_xyxy")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = (float(value) for value in bbox)
        anchor = ((x1 + x2) / 2.0, y2)
        if any(_point_in_zone(anchor, zone, float(padding_px or 0.0)) for zone in zones):
            filtered.append(copy.deepcopy(detection))
    return filtered
