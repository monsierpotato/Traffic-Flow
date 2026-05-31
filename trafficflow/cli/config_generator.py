from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import cv2

Point = Tuple[int, int]

METHODS = {
    "1": "counting_line_per_lane",
    "2": "global_segment",
    "3": "short_lane_zone",
    "4": "counting_gate",
}


class ConfigSession:
    def __init__(self, frame, output_path: Path, camera_id: str, display_max_size: int):
        self.frame = frame
        self.display_frame, self.display_scale = _make_display_frame(frame, display_max_size)
        self.output_path = output_path
        self.camera_id = camera_id
        self.method_key = "1"
        self.points: List[Point] = []
        self.lanes = []
        self.ready_to_finalize = False
        self.needs_final_render = False
        self.message = "Press 1-4 to choose method. Click points, Enter saves."

    @property
    def method(self) -> str:
        return METHODS[self.method_key]

    def on_mouse(self, event, x, y, _flags, _param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        self.points.append(self._to_source_point(x, y))
        required = self._required_points()
        if len(self.points) >= required:
            self.ready_to_finalize = True
            self.needs_final_render = True
            self.message = "Points complete. Enter lane info in terminal."
        else:
            self.message = f"Clicked {len(self.points)}/{required} points."

    def set_method(self, key: str) -> None:
        self.method_key = key
        self.points.clear()
        self.ready_to_finalize = False
        self.needs_final_render = False
        self.message = f"Method: {self.method}. Existing lanes: {len(self.lanes)}"

    def finalize_if_ready(self) -> None:
        if not self.ready_to_finalize or self.needs_final_render:
            return
        if len(self.points) < self._required_points():
            return
        if self.method_key == "1":
            self._add_line_lane()
        elif self.method_key == "2":
            self._add_global_segments()
        elif self.method_key == "3":
            self._add_zone_lane(with_direction=False)
        elif self.method_key == "4":
            self._add_zone_lane(with_direction=True)

    def _required_points(self) -> int:
        if self.method_key in {"1", "2"}:
            return 2
        if self.method_key == "3":
            return 6
        if self.method_key == "4":
            return 8
        raise ValueError(f"Unknown method key: {self.method_key}")

    def _lane_id(self) -> str:
        value = input("Lane id? ").strip()
        return value or f"lane_{len(self.lanes) + 1}"

    def _add_line_lane(self) -> None:
        self.lanes.append(
            {
                "lane_id": self._lane_id(),
                "counting_line": [list(self.points[0]), list(self.points[1])],
                "class_allowed": ["car", "bus", "truck", "motorcycle"],
            }
        )
        self.points.clear()
        self.ready_to_finalize = False
        self.needs_final_render = False
        self.message = f"Added lane. Total lanes: {len(self.lanes)}"

    def _add_global_segments(self) -> None:
        lane_count = int(input("How many parallel lanes? ").strip())
        start, end = self.points
        self.lanes.clear()
        for index in range(lane_count):
            ratio_start = index / lane_count
            ratio_end = (index + 1) / lane_count
            p1 = _interpolate(start, end, ratio_start)
            p2 = _interpolate(start, end, ratio_end)
            self.lanes.append(
                {
                    "lane_id": f"lane_{index + 1}",
                    "counting_line": [list(p1), list(p2)],
                    "segment_ratio": [ratio_start, ratio_end],
                    "class_allowed": ["car", "bus", "truck", "motorcycle"],
                }
            )
        self.points.clear()
        self.ready_to_finalize = False
        self.needs_final_render = False
        self.message = f"Created {lane_count} global segments. Press Enter to save."

    def _add_zone_lane(self, with_direction: bool) -> None:
        polygon = self.points[:4]
        line = self.points[4:6]
        direction = self.points[6:8] if with_direction else None
        lane = {
            "lane_id": self._lane_id(),
            "valid_zone": [list(p) for p in polygon],
            "counting_line": [list(line[0]), list(line[1])],
            "class_allowed": ["car", "bus", "truck", "motorcycle"],
        }
        if direction:
            lane["direction"] = [list(direction[0]), list(direction[1])]
        self.lanes.append(lane)
        self.points.clear()
        self.ready_to_finalize = False
        self.needs_final_render = False
        self.message = f"Added zone lane. Total lanes: {len(self.lanes)}"

    def render(self):
        canvas = self.display_frame.copy()
        for lane in self.lanes:
            _draw_lane(canvas, _scale_lane(lane, self.display_scale))
        _draw_pending(canvas, [_scale_point(point, self.display_scale) for point in self.points], self.method_key)
        cv2.putText(canvas, self.message, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 240, 255), 2)
        cv2.putText(canvas, f"Method {self.method_key}: {self.method}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 240, 255), 2)
        return canvas

    def save(self) -> None:
        height, width = self.frame.shape[:2]
        payload = {
            "version": 1,
            "camera_id": self.camera_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "resolution": {"width": width, "height": height},
            "method": self.method,
            "settings": {
                "movement_threshold_px": 5,
                "cooldown_frames": 12,
                "cooldown_distance_px": 32,
                "zone_policy": "flexible",
            },
            "lanes": self.lanes,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _to_source_point(self, x: int, y: int) -> Point:
        return (round(x / self.display_scale), round(y / self.display_scale))


def _interpolate(start: Point, end: Point, ratio: float) -> Point:
    return (round(start[0] + (end[0] - start[0]) * ratio), round(start[1] + (end[1] - start[1]) * ratio))


def _make_display_frame(frame, display_max_size: int):
    height, width = frame.shape[:2]
    if display_max_size <= 0:
        return frame, 1.0
    scale = min(display_max_size / width, display_max_size / height, 1.0)
    if scale >= 1.0:
        return frame, 1.0
    return cv2.resize(frame, (round(width * scale), round(height * scale))), scale


def _scale_point(point: Point, scale: float) -> Point:
    return (round(point[0] * scale), round(point[1] * scale))


def _scale_lane(lane: dict, scale: float) -> dict:
    scaled = dict(lane)
    for key in ("valid_zone", "counting_line", "direction"):
        if lane.get(key):
            scaled[key] = [list(_scale_point(tuple(point), scale)) for point in lane[key]]
    return scaled


def _draw_lane(canvas, lane: dict) -> None:
    if lane.get("valid_zone"):
        pts = [tuple(p) for p in lane["valid_zone"]]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            cv2.line(canvas, a, b, (0, 180, 255), 2)
    line = [tuple(p) for p in lane["counting_line"]]
    cv2.line(canvas, line[0], line[1], (0, 0, 255), 2)
    if lane.get("direction"):
        direction = [tuple(p) for p in lane["direction"]]
        cv2.arrowedLine(canvas, direction[0], direction[1], (255, 80, 0), 2, tipLength=0.25)
    cv2.putText(canvas, lane["lane_id"], line[0], cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def _draw_pending(canvas, points: List[Point], method_key: str) -> None:
    for point in points:
        cv2.circle(canvas, point, 4, (0, 255, 0), -1)
    if method_key in {"3", "4"} and len(points) <= 4:
        for a, b in zip(points, points[1:]):
            cv2.line(canvas, a, b, (0, 180, 255), 1)
    else:
        for a, b in zip(points, points[1:]):
            cv2.line(canvas, a, b, (0, 255, 0), 1)


def read_frame(video_path: Path, frame_index: int):
    cap = cv2.VideoCapture(str(video_path))
    if frame_index > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Could not read frame {frame_index} from {video_path}")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive manual geometry config generator.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output", default=Path("configs/manual_counting.json"), type=Path)
    parser.add_argument("--camera-id", default="camera_01")
    parser.add_argument("--frame-index", default=0, type=int, help="Video frame to use as the drawing background.")
    parser.add_argument("--display-max-size", default=1280, type=int, help="Resize preview so its longest side fits this size; saved coordinates remain in source resolution.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = ConfigSession(read_frame(args.video, args.frame_index), args.output, args.camera_id, args.display_max_size)
    window = "TrafficFlow Configurator"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, session.on_mouse)

    while True:
        final_render_pending = session.ready_to_finalize and session.needs_final_render
        cv2.imshow(window, session.render())
        key = cv2.waitKey(30) & 0xFF
        if final_render_pending:
            session.needs_final_render = False
        session.finalize_if_ready()
        if key in (13, 10):
            session.save()
            print(f"Saved config: {args.output}")
            break
        if key == 27:
            break
        char = chr(key) if key < 128 else ""
        if char in METHODS:
            session.set_method(char)
        elif char in {"r", "R"}:
            session.points.clear()
            session.ready_to_finalize = False
            session.needs_final_render = False
            session.message = "Cleared pending points."

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
