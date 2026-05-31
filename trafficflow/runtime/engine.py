from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2

from trafficflow.core_ai import YoloByteTrackDetector
from trafficflow.counting.methods import TrackObservation, build_counter
from trafficflow.geometry import bbox_bottom_center
from trafficflow.pipeline.overlay import draw_counting_overlay


@dataclass(frozen=True)
class VideoCountingRequest:
    video_path: Path
    config_path: Path
    model_path: str = "models/yolov8n.pt"
    device: Optional[str] = None
    confidence: float = 0.25
    max_frames: Optional[int] = None
    output_video_path: Optional[Path] = None
    output_jsonl_path: Optional[Path] = None
    draw_overlay: bool = True


@dataclass(frozen=True)
class VideoCountingResult:
    frames: int
    counts: dict

    def to_dict(self) -> dict:
        return {"frames": self.frames, "counts": self.counts}


class TrafficFlowEngine:
    def process_video(self, request: VideoCountingRequest) -> VideoCountingResult:
        config = json.loads(request.config_path.read_text(encoding="utf-8"))
        detector = YoloByteTrackDetector(
            request.model_path,
            confidence=request.confidence,
            device=request.device,
        )

        cap = cv2.VideoCapture(str(request.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {request.video_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        config = scale_config_to_video(config, width, height)
        counter = build_counter(config)

        writer = None
        if request.output_video_path:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            request.output_video_path.parent.mkdir(parents=True, exist_ok=True)
            writer = cv2.VideoWriter(
                str(request.output_video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (width, height),
            )

        jsonl_handle = None
        if request.output_jsonl_path:
            request.output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            jsonl_handle = request.output_jsonl_path.open("w", encoding="utf-8")

        frame_index = 0
        try:
            while True:
                if request.max_frames is not None and frame_index >= request.max_frames:
                    break
                ok, frame = cap.read()
                if not ok:
                    break

                detections = detector.detect_and_track(frame)
                observations = [
                    TrackObservation(
                        track_id=d.track_id,
                        class_name=d.class_name,
                        bbox_xyxy=d.bbox_xyxy,
                        point=bbox_bottom_center(d.bbox_xyxy),
                    )
                    for d in detections
                ]
                events = counter.update(observations, frame_index)

                if request.draw_overlay:
                    draw_counting_overlay(frame, config, detections, observations, events, counter.counts)
                if jsonl_handle:
                    for event in events:
                        jsonl_handle.write(json.dumps(event.__dict__, ensure_ascii=False) + "\n")
                if writer:
                    writer.write(frame)

                frame_index += 1
        finally:
            cap.release()
            if writer:
                writer.release()
            if jsonl_handle:
                jsonl_handle.close()

        return VideoCountingResult(frames=frame_index, counts=counter.counts)


def scale_config_to_video(config: dict, video_width: int, video_height: int) -> dict:
    resolution = config.get("resolution")
    if not resolution:
        return config

    config_width = int(resolution.get("width", video_width))
    config_height = int(resolution.get("height", video_height))
    if (config_width, config_height) == (video_width, video_height):
        return config
    if config_width <= 0 or config_height <= 0:
        raise ValueError(f"Invalid config resolution: {resolution}")

    scale_x = video_width / config_width
    scale_y = video_height / config_height
    print(
        f"Scaling config geometry from {config_width}x{config_height} "
        f"to {video_width}x{video_height} (x={scale_x:.4f}, y={scale_y:.4f})"
    )

    scaled = json.loads(json.dumps(config))
    scaled["resolution"] = {"width": video_width, "height": video_height}
    for lane in scaled.get("lanes", []):
        for key in ("valid_zone", "counting_line", "direction"):
            if lane.get(key):
                lane[key] = [[point[0] * scale_x, point[1] * scale_y] for point in lane[key]]
    return scaled
