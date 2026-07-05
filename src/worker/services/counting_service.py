import math
import logging
from typing import List, Dict, Tuple, Set
from collections import defaultdict

logger = logging.getLogger(__name__)

COS_THRESHOLD = 0.3


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def point_in_polygon(px: float, py: float, polygon: List[List[float]]) -> bool:
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def bbox_center(bbox_xyxy: List[float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox_xyxy
    return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)


def ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def segments_intersect(A: Tuple[float, float], B: Tuple[float, float],
                       C: Tuple[float, float], D: Tuple[float, float]) -> bool:
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


def bbox_intersects_polygon(bbox_xyxy: List[float], polygon: List[List[float]]) -> bool:
    x1, y1, x2, y2 = bbox_xyxy
    for px, py in polygon:
        if x1 <= px <= x2 and y1 <= py <= y2:
            return True
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    for cx, cy in corners:
        if point_in_polygon(cx, cy, polygon):
            return True
    n = len(polygon)
    for i in range(n):
        p_start = (polygon[i][0], polygon[i][1])
        p_end = (polygon[(i + 1) % n][0], polygon[(i + 1) % n][1])
        for j in range(4):
            b_start = corners[j]
            b_end = corners[(j + 1) % 4]
            if segments_intersect(p_start, p_end, b_start, b_end):
                return True
    return False


# ---------------------------------------------------------------------------
# Direction filter — uses velocity from tracker's Kalman filter
# ---------------------------------------------------------------------------

class DirectionFilter:
    """Checks whether a track's Kalman velocity aligns with the lane direction."""

    def __init__(self, direction: List[List[float]]):
        if direction and len(direction) == 2:
            self.dir_vec = (direction[1][0] - direction[0][0],
                            direction[1][1] - direction[0][1])
        else:
            self.dir_vec = (0, 0)

    def is_aligned(self, velocity: Tuple[float, float]) -> bool:
        if self.dir_vec == (0, 0):
            return True
        dot = velocity[0] * self.dir_vec[0] + velocity[1] * self.dir_vec[1]
        v_mag = math.sqrt(velocity[0] ** 2 + velocity[1] ** 2)
        d_mag = math.sqrt(self.dir_vec[0] ** 2 + self.dir_vec[1] ** 2)
        if v_mag > 0 and d_mag > 0:
            return (dot / (v_mag * d_mag)) >= COS_THRESHOLD
        return True


# ---------------------------------------------------------------------------
# Line crossing detector
# ---------------------------------------------------------------------------

class LineCrossingDetector:
    """Detects when a track crosses a counting line. Direction filtered by
    Kalman velocity from the tracker, not raw frame-to-frame delta."""

    def __init__(self, counting_line: List[List[float]], direction: List[List[float]]):
        self.line_start = (counting_line[0][0], counting_line[0][1])
        self.line_end = (counting_line[1][0], counting_line[1][1])
        self.dir_filter = DirectionFilter(direction)
        self._crossed_ids: Set[int] = set()

    def check_crossing(self, track_id: int,
                       last_center: Tuple[float, float],
                       center: Tuple[float, float],
                       velocity: Tuple[float, float]) -> bool:
        if track_id in self._crossed_ids:
            return False
        if last_center == center:
            return False
        if not segments_intersect(last_center, center, self.line_start, self.line_end):
            return False
        if not self.dir_filter.is_aligned(velocity):
            return False
        self._crossed_ids.add(track_id)
        return True

    @property
    def crossed_count(self) -> int:
        return len(self._crossed_ids)


# ---------------------------------------------------------------------------
# Counting State — aggregates counts per lane
# ---------------------------------------------------------------------------

class CountingState:
    """Per-lane counter driven by Kalman-enriched detections from LocalTracker.

    Expects detection dicts with:
        - track_id: int
        - class_name: str
        - bbox_xyxy: [x1, y1, x2, y2]
        - kalman_velocity: (dx, dy)   ← from LocalTracker
        - lost_frames: int            ← 0 = visible, >0 = predicted (lost)
    """

    def __init__(self, lanes: List[dict]):
        self.lanes = lanes
        self.detectors: Dict[str, LineCrossingDetector] = {}
        self.counters: Dict[str, Dict[str, Set[int]]] = {}
        self._last_center: Dict[int, Tuple[float, float]] = {}
        self._assigned_lane: Dict[int, str] = {}

        for lane in lanes:
            lid = lane["lane_id"]
            self.detectors[lid] = LineCrossingDetector(
                counting_line=lane["counting_line"],
                direction=lane.get("direction", [[0, 0], [0, 1]]),
            )
            self.counters[lid] = defaultdict(set)

    def process_detections(self, detections: List[dict]):
        import cv2
        import numpy as np

        for det in detections:
            tid = det.get("track_id")
            if tid is None:
                continue
            tid = int(tid)

            bbox = det.get("bbox_xyxy", [])
            if len(bbox) != 4:
                continue

            cls_name = det.get("class_name", "unknown")
            velocity = det.get("kalman_velocity", (0, 0))
            lost = det.get("lost_frames", 0)

            center = bbox_center(bbox)

            # --- Find best lane ---
            best = None
            x1, y1, x2, y2 = map(int, bbox)
            if x2 > x1 and y2 > y1:
                max_area = 0.0
                for lane in self.lanes:
                    poly = lane.get("valid_zone", [])
                    if not poly:
                        continue
                    shifted = [[int(px) - x1, int(py) - y1] for px, py in poly]
                    mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
                    cv2.fillPoly(mask, [np.array(shifted, np.int32)], 1)
                    area = float(np.sum(mask))
                    if area > max_area:
                        max_area = area
                        best = lane["lane_id"]

            if best is not None:
                self._assigned_lane[tid] = best
            else:
                best = self._assigned_lane.get(tid)

            last_center = self._last_center.get(tid)
            self._last_center[tid] = center

            if last_center is None or best is None:
                continue

            # --- Check class filter ---
            lane_cfg = next((l for l in self.lanes if l["lane_id"] == best), None)
            if lane_cfg is None:
                continue
            allowed = lane_cfg.get("class_allowed", [])
            if allowed and cls_name not in allowed:
                continue

            # --- Count crossing ---
            detector = self.detectors[best]
            if detector.check_crossing(tid, last_center, center, velocity):
                self.counters[best][cls_name].add(tid)
                logger.debug(f"Counted: track_id={tid}, class={cls_name}, lane={best}"
                             f"{' (lost+predicted)' if lost else ''}")

    def get_statistics(self) -> List[dict]:
        stats = []
        for lane in self.lanes:
            lid = lane["lane_id"]
            type_map = self.counters.get(lid, {})
            if not type_map:
                stats.append({
                    "lane_id": lid, "vehicle_type": "total",
                    "count": 0, "direction": "both",
                })
                continue
            for vtype, ids in type_map.items():
                stats.append({
                    "lane_id": lid, "vehicle_type": vtype,
                    "count": len(ids), "direction": "both",
                })
        return stats

    def get_total_count(self) -> int:
        total = 0
        for type_map in self.counters.values():
            for ids in type_map.values():
                total += len(ids)
        return total
