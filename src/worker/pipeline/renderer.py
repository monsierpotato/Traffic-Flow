"""Draw annotation overlays on video frames."""

from typing import List, Optional
import cv2
import numpy as np
from shared.config import settings
from worker.services.counting_service import bbox_bottom_center, point_in_polygon
from worker.pipeline.tracker import TrackOutput


class FrameRenderer:
    """Draws lane geometry + detection tracks onto a frame."""

    def __init__(self, lanes: List[dict], settings_obj=settings):
        self.lanes = lanes
        self.settings = settings_obj

    def draw(self, frame: np.ndarray, detections: List[dict], debug: dict | None = None) -> np.ndarray:
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
            if not det.get("confirmed", True):
                continue
            if det.get("is_lost") and not self.settings.RENDER_SHOW_LOST:
                continue
            x1, y1, x2, y2 = map(int, bbox)
            track_id = det.get("track_id", "")
            cls_name = det.get("class_name", "")

            anchor = bbox_bottom_center(bbox)
            in_any_zone = self._in_any_zone(anchor)
            if not in_any_zone and not self.settings.RENDER_SHOW_OUT_OF_ZONE:
                continue

            if in_any_zone:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{cls_name} {track_id}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.circle(frame, (int(anchor[0]), int(anchor[1])), 5, (0, 0, 255), -1)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (150, 150, 150), 1)
                cv2.putText(frame, f"{cls_name} {track_id}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        if debug:
            self._draw_debug(frame, debug)
        return frame

    def _in_any_zone(self, anchor) -> bool:
        for lane in self.lanes:
            zone = lane.get("valid_zone", [])
            if zone and point_in_polygon(anchor[0], anchor[1], zone):
                return True
        return False

    def _draw_debug(self, frame: np.ndarray, debug: dict) -> None:
        tracks = debug.get("tracks", {})
        for tid, info in tracks.items():
            history = info.get("history", [])
            pts = [(int(x), int(y)) for x, y in history]
            for a, b in zip(pts, pts[1:]):
                cv2.line(frame, a, b, (0, 255, 255), 2)
            if pts:
                lane = info.get("lane_locked") or info.get("lane_candidate") or "no_lane"
                cv2.circle(frame, pts[-1], 6, (0, 255, 255), -1)
                cv2.putText(frame, f"anchor {tid} {lane}", (pts[-1][0] + 6, pts[-1][1] + 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        for event in debug.get("events", [])[-8:]:
            anchor = event.get("anchor") or []
            if len(anchor) == 2:
                p = (int(anchor[0]), int(anchor[1]))
                cv2.circle(frame, p, 14, (0, 0, 255), 3)
                cv2.putText(frame, f"COUNT {event.get('class_name')} {event.get('lane_id')}",
                            (p[0] + 12, p[1] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
