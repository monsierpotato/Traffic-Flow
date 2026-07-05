import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

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

    def predict(self) -> np.ndarray:
        self._predicted_state = self.kf.predict()
        self.age += 1
        return self._predicted_state

    def correct(self, bbox_xyxy: List[float]):
        x1, y1, x2, y2 = bbox_xyxy
        cx = (x1 + x2) * 0.5; cy = (y1 + y2) * 0.5
        w = x2 - x1; h = y2 - y1
        self.kf.correct(np.array([cx, cy, w, h], np.float32))
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


class LocalTracker:
    """Per-track Kalman filter tracker with lost-track prediction.

    Uses detection observations from any source (Modal, local YOLO, etc.)
    and maintains smooth Kalman velocity + lost-track continuity.

    Flow per frame:
    1. Kalman predict all existing tracks forward.
    2. Match new detections to tracks by IoU (greedy).
    3. Matched → correct Kalman with observation. Unmatched detections → new tracks.
    4. Unmatched existing tracks → increment lost_frames.
    5. Tracks with lost_frames > track_buffer → expired.
    6. Return all active + still-predicting lost tracks.
    """

    def __init__(self, match_threshold: float = 0.5, track_buffer: int = 30):
        self.match_threshold = match_threshold
        self.track_buffer = track_buffer

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

    def update(self, detections: List[dict]) -> List[TrackOutput]:
        """Process a frame's detections and return enriched track outputs.

        Each ``detection`` dict must have:
            - bbox_xyxy: [x1, y1, x2, y2]
            - class_name: str
            - confidence: float (optional, default 1.0)

        Returns:
            List of ``TrackOutput`` — one per active + non-expired lost track.
        """
        # --- 1. Kalman predict all existing tracks forward ---
        predicted = {}
        for tid, kf in self._tracks.items():
            st = kf.predict()
            predicted[tid] = kf.predicted_xyxy()

        # --- 2. Build IoU cost matrix between detections and tracks ---
        unmatched_det = list(range(len(detections)))
        unmatched_trk = list(self._tracks.keys())
        matches: List[Tuple[int, int]] = []  # (det_idx, track_id)

        if detections and self._tracks:
            cost = np.zeros((len(detections), len(self._tracks)), dtype=np.float32)
            for i, det in enumerate(detections):
                for j, tid in enumerate(unmatched_trk):
                    cost[i, j] = _iou_xyxy(det["bbox_xyxy"], predicted[tid])

            # Greedy assignment (sorts by IoU descending)
            while True:
                i_flat = int(np.argmax(cost))
                i, j = divmod(i_flat, cost.shape[1])
                iou = cost[i, j]
                if iou < self.match_threshold:
                    break
                matches.append((unmatched_det[i], unmatched_trk[j]))
                cost[i, :] = -1
                cost[:, j] = -1

        # --- 3. Matched → correct; unmatched detections → new tracks ---
        matched_det = set()
        for det_idx, tid in matches:
            matched_det.add(det_idx)
            det = detections[det_idx]
            self._tracks[tid].correct(det["bbox_xyxy"])
            self._metadata[tid]["class_name"] = det.get("class_name", "unknown")
            self._metadata[tid]["confidence"] = det.get("confidence", 1.0)

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
            }
            new_tids.add(tid)
            matched_det.add(i)

        # --- 4. Unmatched existing tracks → increment lost ---
        matched_trk = {tid for _, tid in matches} | new_tids
        for tid, kf in self._tracks.items():
            if tid not in matched_trk:
                kf.lost_frames += 1

        # --- 5. Expire old lost tracks ---
        expired = [tid for tid, kf in self._tracks.items()
                   if kf.lost_frames > self.track_buffer]
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
            ))

        return results
