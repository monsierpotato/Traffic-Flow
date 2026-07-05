"""Draw annotation overlays on video frames."""

from typing import List, Optional
import cv2
import numpy as np
from worker.services.counting_service import (
    bbox_intersects_polygon, bbox_center,
)
from worker.pipeline.tracker import TrackOutput


class FrameRenderer:
    """Draws lane geometry + detection tracks onto a frame."""

    def __init__(self, lanes: List[dict]):
        self.lanes = lanes

    def draw(self, frame: np.ndarray, detections: List[dict]) -> np.ndarray:
        """Mutate ``frame`` in-place with overlays (returns it for chaining)."""
        for lane in self.lanes:
            zone = lane.get("valid_zone", [])
            line_ = lane.get("counting_line", [])

            if len(zone) > 2:
                pts = np.array(zone, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], isClosed=True,
                              color=(255, 0, 0), thickness=2)

            if len(line_) == 2:
                p1 = (int(line_[0][0]), int(line_[0][1]))
                p2 = (int(line_[1][0]), int(line_[1][1]))
                cv2.line(frame, p1, p2, (0, 0, 255), thickness=2)

        for det in detections:
            bbox = det.get("bbox_xyxy")
            if not bbox or len(bbox) != 4:
                continue
            x1, y1, x2, y2 = map(int, bbox)
            track_id = det.get("track_id", "")
            cls_name = det.get("class_name", "")

            in_any_zone = self._in_any_zone(bbox)

            if in_any_zone:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{cls_name} {track_id}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (150, 150, 150), 1)
                cv2.putText(frame, f"{cls_name} {track_id}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        return frame

    def _in_any_zone(self, bbox: List[float]) -> bool:
        for lane in self.lanes:
            zone = lane.get("valid_zone", [])
            if zone and bbox_intersects_polygon(bbox, zone):
                return True
        return False
