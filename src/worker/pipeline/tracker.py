import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging
import time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IoU helper
# ---------------------------------------------------------------------------

def _iou_xyxy(a: List[float], b: List[float]) -> float:
    x1 = max(a[0], b[0]); y1 = max(a[1], b[1])
    x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _valid_bbox_xyxy(bbox: List[float]) -> bool:
    if not bbox or len(bbox) != 4:
        return False
    try:
        x1, y1, x2, y2 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return False
    return np.isfinite([x1, y1, x2, y2]).all() and x2 > x1 and y2 > y1


# ---------------------------------------------------------------------------
# Single-track Kalman filter
# ---------------------------------------------------------------------------

class _TrackKF:
    """8-state Kalman (cx, cy, w, h, vx, vy, vw, vh) → measure (cx, cy, w, h)."""

    def __init__(self, bbox_xyxy: List[float]):
        x1, y1, x2, y2 = bbox_xyxy
        cx = (x1 + x2) * 0.5; cy = (y1 + y2) * 0.5
        w = x2 - x1; h = y2 - y1

        kf = cv2.KalmanFilter(8, 4)
        kf.measurementMatrix = np.array([
            [1,0,0,0,0,0,0,0],
            [0,1,0,0,0,0,0,0],
            [0,0,1,0,0,0,0,0],
            [0,0,0,1,0,0,0,0],
        ], np.float32)
        kf.transitionMatrix = np.array([
            [1,0,0,0,1,0,0,0],
            [0,1,0,0,0,1,0,0],
            [0,0,1,0,0,0,1,0],
            [0,0,0,1,0,0,0,1],
            [0,0,0,0,1,0,0,0],
            [0,0,0,0,0,1,0,0],
            [0,0,0,0,0,0,1,0],
            [0,0,0,0,0,0,0,1],
        ], np.float32)
        kf.processNoiseCov = np.diag([0.01, 0.01, 0.01, 0.01, 1.0, 1.0, 1.0, 1.0]).astype(np.float32)
        kf.measurementNoiseCov = np.diag([0.5, 0.5, 0.1, 0.1]).astype(np.float32)
        kf.errorCovPost = np.diag([1.0, 1.0, 1.0, 1.0, 10.0, 10.0, 10.0, 10.0]).astype(np.float32)
        kf.statePost = np.array([cx, cy, w, h, 0, 0, 0, 0], np.float32)

        self.kf = kf
        self.lost_frames = 0
        self.age = 1
        # Store the last predicted state separately (statePre after predict)
        self._predicted_state = np.array([cx, cy, w, h, 0, 0, 0, 0], np.float32)

    def predict(self, dt: float = 1.0) -> np.ndarray:
        dt = max(1.0 / 60.0, min(float(dt), 0.5))
        self.kf.transitionMatrix[0, 4] = dt
        self.kf.transitionMatrix[1, 5] = dt
        self.kf.transitionMatrix[2, 6] = dt
        self.kf.transitionMatrix[3, 7] = dt
        self._predicted_state = self.kf.predict()
        self.age += 1
        return self._predicted_state

    def correct(self, bbox_xyxy: List[float]):
        x1, y1, x2, y2 = bbox_xyxy
        cx = (x1 + x2) * 0.5; cy = (y1 + y2) * 0.5
        w = x2 - x1; h = y2 - y1
        measurement = np.array([[cx], [cy], [w], [h]], dtype=np.float32)
        self.kf.correct(measurement)
        self._predicted_state = self.kf.statePost.copy()
        self.lost_frames = 0
        self.age += 1

    @property
    def state(self) -> np.ndarray:
        return self.kf.statePost.flatten()

    @property
    def velocity(self) -> Tuple[float, float]:
        s = self.kf.statePost.flatten()
        return (float(s[4]), float(s[5]))

    def predicted_xyxy(self) -> List[float]:
        s = self._predicted_state.flatten()
        cx, cy, w, h = float(s[0]), float(s[1]), float(s[2]), float(s[3])
        return [cx - w * 0.5, cy - h * 0.5, cx + w * 0.5, cy + h * 0.5]


# ---------------------------------------------------------------------------
# LocalTracker
# ---------------------------------------------------------------------------

@dataclass
class TrackOutput:
    track_id: int
    bbox_xyxy: List[float]
    class_name: str
    confidence: float
    kalman_velocity: Tuple[float, float]
    is_lost: bool
    lost_frames: int
    age: int
    hits: int
    confirmed: bool
    last_seen_age_s: float


class LocalTracker:
    """Per-track Kalman filter tracker with lost-track prediction.

    Uses detection observations from any source (Modal, local YOLO, etc.)
    and maintains smooth Kalman velocity + lost-track continuity.

    Flow per frame:
    1. Kalman predict all existing tracks forward.
    2. Match new detections to tracks by class, IoU, and predicted-center distance.
    3. Matched → correct Kalman with observation. Unmatched detections → new tracks.
    4. Unmatched existing tracks → increment lost_frames.
    5. Tracks with lost_frames > track_buffer → expired.
    6. Return all active + still-predicting lost tracks.
    """

    def __init__(
        self,
        match_threshold: float = 0.5,
        track_buffer: int = 30,
        *,
        min_hits: int = 1,
        max_lost_seconds: Optional[float] = None,
    ):
        self.match_threshold = match_threshold
        self.track_buffer = track_buffer
        self.min_hits = max(1, int(min_hits))
        self.max_lost_seconds = max_lost_seconds

        self._tracks: Dict[int, _TrackKF] = {}
        self._metadata: Dict[int, dict] = {}
        self._next_id = 1

    def reset(self):
        self._tracks.clear()
        self._metadata.clear()
        self._next_id = 1

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tracks.values() if t.lost_frames == 0)

    @property
    def lost_count(self) -> int:
        return sum(1 for t in self._tracks.values() if t.lost_frames > 0)

    def update(self, detections: List[dict], *, timestamp: Optional[float] = None) -> List[TrackOutput]:
        """Process a frame's detections and return enriched track outputs.

        Each ``detection`` dict must have:
            - bbox_xyxy: [x1, y1, x2, y2]
            - class_name: str
            - confidence: float (optional, default 1.0)

        Returns:
            List of ``TrackOutput`` — one per active + non-expired lost track.
        """
        detections = [d for d in detections if _valid_bbox_xyxy(d.get("bbox_xyxy"))]
        now = float(timestamp) if timestamp is not None else time.monotonic()
        timestamped = timestamp is not None

        # --- 1. Kalman predict all existing tracks forward ---
        predicted = {}
        for tid, kf in self._tracks.items():
            previous = self._metadata[tid].get("last_update_timestamp")
            dt = (now - previous) if timestamped and previous is not None else 1.0
            kf.predict(dt)
            predicted[tid] = kf.predicted_xyxy()

        # --- 2. Build IoU cost matrix between detections and tracks ---
        unmatched_det = list(range(len(detections)))
        unmatched_trk = list(self._tracks.keys())
        matches: List[Tuple[int, int]] = []  # (det_idx, track_id)

        if detections and self._tracks:
            # Combine overlap and predicted bottom/center proximity.  At live
            # inference rates a vehicle can legitimately have near-zero IoU
            # with its previous box, so IoU alone fragments IDs.
            cost = np.full((len(detections), len(unmatched_trk)), np.inf, dtype=np.float32)
            for i, det in enumerate(detections):
                for j, tid in enumerate(unmatched_trk):
                    if det.get("class_name", "unknown") != self._metadata[tid].get("class_name", "unknown"):
                        continue
                    det_box = det["bbox_xyxy"]
                    trk_box = predicted[tid]
                    iou = _iou_xyxy(det_box, trk_box)
                    det_cx = (det_box[0] + det_box[2]) * 0.5
                    det_cy = (det_box[1] + det_box[3]) * 0.5
                    trk_cx = (trk_box[0] + trk_box[2]) * 0.5
                    trk_cy = (trk_box[1] + trk_box[3]) * 0.5
                    distance = float(np.hypot(det_cx - trk_cx, det_cy - trk_cy))
                    diagonal = float(np.hypot(trk_box[2] - trk_box[0], trk_box[3] - trk_box[1]))
                    gate = max(80.0, 2.5 * diagonal)
                    if iou < self.match_threshold and distance >= gate:
                        continue
                    cost[i, j] = 0.5 * (1.0 - iou) + 0.4 * min(distance / gate, 1.0)

            try:
                from scipy.optimize import linear_sum_assignment
                rows, cols = linear_sum_assignment(cost)
                matches.extend(
                    (unmatched_det[i], unmatched_trk[j])
                    for i, j in zip(rows, cols)
                    if np.isfinite(cost[i, j])
                )
            except (ImportError, ValueError):
                # The CPU-only install does not require SciPy.  Keep a gated
                # greedy fallback there; GPU deployments use Hungarian above.
                candidates = [
                    (float(cost[i, j]), i, j)
                    for i in range(cost.shape[0])
                    for j in range(cost.shape[1])
                    if np.isfinite(cost[i, j])
                ]
                used_det, used_trk = set(), set()
                for _, i, j in sorted(candidates):
                    if i not in used_det and j not in used_trk:
                        matches.append((unmatched_det[i], unmatched_trk[j]))
                        used_det.add(i)
                        used_trk.add(j)

        # --- 3. Matched → correct; unmatched detections → new tracks ---
        matched_det = set()
        for det_idx, tid in matches:
            matched_det.add(det_idx)
            det = detections[det_idx]
            self._tracks[tid].correct(det["bbox_xyxy"])
            self._metadata[tid]["class_name"] = det.get("class_name", "unknown")
            self._metadata[tid]["confidence"] = det.get("confidence", 1.0)
            self._metadata[tid]["hits"] += 1
            self._metadata[tid]["last_update_timestamp"] = now

        new_tids = set()
        for i, det in enumerate(detections):
            if i in matched_det:
                continue
            kf = _TrackKF(det["bbox_xyxy"])
            tid = self._next_id
            self._next_id += 1
            self._tracks[tid] = kf
            self._metadata[tid] = {
                "class_name": det.get("class_name", "unknown"),
                "confidence": det.get("confidence", 1.0),
                "hits": 1,
                "last_update_timestamp": now,
            }
            new_tids.add(tid)
            matched_det.add(i)

        # --- 4. Unmatched existing tracks → increment lost ---
        matched_trk = {tid for _, tid in matches} | new_tids
        for tid, kf in self._tracks.items():
            if tid not in matched_trk:
                kf.lost_frames += 1

        # --- 5. Expire old lost tracks ---
        expired = [
            tid for tid, kf in self._tracks.items()
            if kf.lost_frames > self.track_buffer
            or (
                timestamped and self.max_lost_seconds is not None
                and now - self._metadata[tid]["last_update_timestamp"] > self.max_lost_seconds
            )
        ]
        for tid in expired:
            del self._tracks[tid]
            del self._metadata[tid]

        # --- 6. Build output ---
        results: List[TrackOutput] = []
        for tid, kf in self._tracks.items():
            meta = self._metadata[tid]
            results.append(TrackOutput(
                track_id=tid,
                bbox_xyxy=kf.predicted_xyxy(),
                class_name=meta["class_name"],
                confidence=meta["confidence"],
                kalman_velocity=kf.velocity,
                is_lost=kf.lost_frames > 0,
                lost_frames=kf.lost_frames,
                age=kf.age,
                hits=meta["hits"],
                confirmed=meta["hits"] >= self.min_hits,
                last_seen_age_s=max(0.0, now - meta["last_update_timestamp"]) if timestamped else 0.0,
            ))

        return results
