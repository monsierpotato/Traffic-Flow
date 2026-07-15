import math
import logging
from typing import List, Dict, Tuple, Set
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

COS_THRESHOLD = 0.35
LANE_LOCK_FRAMES = 3
MIN_TRACK_AGE_FRAMES = 4
DIRECTION_WINDOW_FRAMES = 6
SMOOTHING_ALPHA = 0.35


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


def bbox_bottom_center(bbox_xyxy: List[float]) -> Tuple[float, float]:
    x1, _y1, x2, y2 = bbox_xyxy
    return ((x1 + x2) * 0.5, y2)


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

    def is_movement_aligned(self, start: Tuple[float, float], end: Tuple[float, float]) -> bool:
        return self.is_aligned((end[0] - start[0], end[1] - start[1]))


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
                       direction_start: Tuple[float, float]) -> bool:
        if track_id in self._crossed_ids:
            return False
        if last_center == center:
            return False
        if not segments_intersect(last_center, center, self.line_start, self.line_end):
            return False
        if not self.dir_filter.is_movement_aligned(direction_start, center):
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
        self.global_counted_ids: Set[int] = set()
        self.track_counted_lanes: Dict[int, Set[str]] = defaultdict(set)
        self._last_center: Dict[int, Tuple[float, float]] = {}
        self._assigned_lane: Dict[int, str] = {}
        self._lane_candidate: Dict[int, str] = {}
        self._lane_candidate_frames: Dict[int, int] = defaultdict(int)
        self._track_age: Dict[int, int] = defaultdict(int)
        self._anchor_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=DIRECTION_WINDOW_FRAMES))
        self._smoothed_anchor: Dict[int, Tuple[float, float]] = {}
        self._last_count_events: deque = deque(maxlen=30)

        for lane in lanes:
            lid = lane["lane_id"]
            self.detectors[lid] = LineCrossingDetector(
                counting_line=lane["counting_line"],
                direction=lane.get("direction", [[0, 0], [0, 1]]),
            )
            self.counters[lid] = defaultdict(set)

    def process_detections(self, detections: List[dict]):
        for det in detections:
            tid = det.get("track_id")
            if tid is None:
                continue
            tid = int(tid)

            bbox = det.get("bbox_xyxy", [])
            if len(bbox) != 4:
                continue
            try:
                x1, y1, x2, y2 = [float(v) for v in bbox]
            except (TypeError, ValueError):
                continue
            if x2 <= x1 or y2 <= y1:
                continue

            cls_name = det.get("class_name", "unknown")
            if not det.get("confirmed", True):
                continue
            lost = det.get("lost_frames", 0)
            is_lost = bool(det.get("is_lost", False)) or int(lost or 0) > 0
            if is_lost:
                continue

            center = bbox_bottom_center(bbox)
            previous_smooth = self._smoothed_anchor.get(tid)
            if previous_smooth is None:
                smooth_center = center
            else:
                smooth_center = (
                    previous_smooth[0] * (1.0 - SMOOTHING_ALPHA) + center[0] * SMOOTHING_ALPHA,
                    previous_smooth[1] * (1.0 - SMOOTHING_ALPHA) + center[1] * SMOOTHING_ALPHA,
                )
            self._smoothed_anchor[tid] = smooth_center
            self._track_age[tid] += 1
            self._anchor_history[tid].append(smooth_center)

            # --- Find/lock lane by smoothed bottom-center anchor ---
            observed_lane = None
            for lane in self.lanes:
                poly = lane.get("valid_zone", [])
                if poly and point_in_polygon(smooth_center[0], smooth_center[1], poly):
                    observed_lane = lane["lane_id"]
                    break

            if observed_lane is not None:
                if self._lane_candidate.get(tid) == observed_lane:
                    self._lane_candidate_frames[tid] += 1
                else:
                    self._lane_candidate[tid] = observed_lane
                    self._lane_candidate_frames[tid] = 1
                if self._lane_candidate_frames[tid] >= LANE_LOCK_FRAMES:
                    self._assigned_lane[tid] = observed_lane

            best = self._assigned_lane.get(tid)

            last_center = self._last_center.get(tid)
            self._last_center[tid] = smooth_center

            if last_center is None or best is None:
                continue
            if self._track_age[tid] < MIN_TRACK_AGE_FRAMES:
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
            history = self._anchor_history.get(tid)
            direction_start = history[0] if history else last_center
            if detector.check_crossing(tid, last_center, smooth_center, direction_start):
                self.counters[best][cls_name].add(tid)
                self.global_counted_ids.add(tid)
                self.track_counted_lanes[tid].add(best)
                self._last_count_events.append({
                    "track_id": tid,
                    "lane_id": best,
                    "class_name": cls_name,
                    "anchor": [round(smooth_center[0], 2), round(smooth_center[1], 2)],
                })
                logger.debug(f"Counted: track_id={tid}, class={cls_name}, lane={best}"
                             f"{' (lost+predicted)' if lost else ''}")

    def prune_inactive_tracks(self, active_track_ids: Set[int]) -> None:
        """Discard transient debug/lane state once a tracker removes an ID.

        Counted-ID sets remain intact, so historical totals and diagnostics do
        not change.  This prevents debug overlays from growing for a whole live
        session.
        """
        for tid in set(self._smoothed_anchor) - active_track_ids:
            self._last_center.pop(tid, None)
            self._assigned_lane.pop(tid, None)
            self._lane_candidate.pop(tid, None)
            self._lane_candidate_frames.pop(tid, None)
            self._track_age.pop(tid, None)
            self._anchor_history.pop(tid, None)
            self._smoothed_anchor.pop(tid, None)

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


# Backward-compatible metric helpers attached to CountingState after class definition.
def _counting_get_global_unique_count(self) -> int:
    return len(self.global_counted_ids)


def _counting_get_multi_lane_tracks(self) -> List[dict]:
    return [
        {"track_id": tid, "lanes": sorted(lanes)}
        for tid, lanes in sorted(self.track_counted_lanes.items())
        if len(lanes) > 1
    ]


def _counting_get_diagnostics(self) -> dict:
    lane_volume_total = self.get_total_count()
    global_unique_count = self.get_global_unique_count()
    multi_lane_tracks = self.get_multi_lane_tracks()
    return {
        "lane_volume_total": lane_volume_total,
        "global_unique_count": global_unique_count,
        "multi_lane_track_count": len(multi_lane_tracks),
        "multi_lane_tracks": multi_lane_tracks,
        "double_count_delta": lane_volume_total - global_unique_count,
    }


def _counting_get_debug_snapshot(self) -> dict:
    tracks = {}
    for tid, anchor in self._smoothed_anchor.items():
        history = self._anchor_history.get(tid, [])
        tracks[str(tid)] = {
            "anchor": [round(anchor[0], 2), round(anchor[1], 2)],
            "history": [[round(p[0], 2), round(p[1], 2)] for p in list(history)],
            "lane_candidate": self._lane_candidate.get(tid),
            "lane_candidate_frames": self._lane_candidate_frames.get(tid, 0),
            "lane_locked": self._assigned_lane.get(tid),
            "track_age": self._track_age.get(tid, 0),
            "counted_lanes": sorted(self.track_counted_lanes.get(tid, set())),
        }
    return {"tracks": tracks, "events": list(self._last_count_events)}


CountingState.get_global_unique_count = _counting_get_global_unique_count
CountingState.get_multi_lane_tracks = _counting_get_multi_lane_tracks
CountingState.get_diagnostics = _counting_get_diagnostics
CountingState.get_debug_snapshot = _counting_get_debug_snapshot
