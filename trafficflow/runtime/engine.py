from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import cv2

from trafficflow.core_ai import YoloByteTrackDetector
from trafficflow.counting.methods import TrackObservation, build_counter
from trafficflow.geometry import bbox_bottom_center
from trafficflow.pipeline.overlay import draw_counting_overlay

ProgressCallback = Callable[[dict], None]


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
    progress_callback: Optional[ProgressCallback] = None
    progress_interval_percent: float = 5.0


@dataclass(frozen=True)
class VideoCountingResult:
    frames: int
    counts: dict
    total_frames: Optional[int] = None
    status: str = "completed"
    output_video_path: Optional[Path] = None
    output_jsonl_path: Optional[Path] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "frames": self.frames,
            "total_frames": self.total_frames,
            "counts": self.counts,
            "total_count": _total_count(self.counts),
            "outputs": {
                "video_path": str(self.output_video_path) if self.output_video_path else None,
                "events_jsonl_path": str(self.output_jsonl_path) if self.output_jsonl_path else None,
            },
        }


@dataclass(frozen=True)
class VideoCountingProgress:
    status: str
    frame_index: int
    frames_processed: int
    total_frames: Optional[int]
    progress: Optional[float]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "frame_index": self.frame_index,
            "frames_processed": self.frames_processed,
            "total_frames": self.total_frames,
            "progress": self.progress,
        }


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
        total_frames = _effective_total_frames(
            int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
            request.max_frames,
        )
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
        last_reported_progress = -1.0
        _emit_progress(
            request.progress_callback,
            status="started",
            frame_index=0,
            frames_processed=0,
            total_frames=total_frames,
            progress=_progress_percent(0, total_frames),
        )
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
                progress = _progress_percent(frame_index, total_frames)
                if _should_report_progress(progress, last_reported_progress, request.progress_interval_percent):
                    _emit_progress(
                        request.progress_callback,
                        status="processing",
                        frame_index=frame_index - 1,
                        frames_processed=frame_index,
                        total_frames=total_frames,
                        progress=progress,
                    )
                    last_reported_progress = progress if progress is not None else last_reported_progress
        except Exception:
            _emit_progress(
                request.progress_callback,
                status="failed",
                frame_index=max(frame_index - 1, 0),
                frames_processed=frame_index,
                total_frames=total_frames,
                progress=_progress_percent(frame_index, total_frames),
            )
            raise
        finally:
            cap.release()
            if writer:
                writer.release()
            if jsonl_handle:
                jsonl_handle.close()

        _emit_progress(
            request.progress_callback,
            status="completed",
            frame_index=max(frame_index - 1, 0),
            frames_processed=frame_index,
            total_frames=total_frames,
            progress=100.0 if total_frames is not None else None,
        )

        return VideoCountingResult(
            frames=frame_index,
            counts=counter.counts,
            total_frames=total_frames,
            output_video_path=request.output_video_path,
            output_jsonl_path=request.output_jsonl_path,
        )


def _total_count(counts: dict) -> int:
    total = 0
    for class_counts in counts.values():
        total += sum(int(value) for value in class_counts.values())
    return total


def _effective_total_frames(video_total_frames: int, max_frames: Optional[int]) -> Optional[int]:
    if video_total_frames <= 0:
        return max_frames
    if max_frames is None:
        return video_total_frames
    return min(video_total_frames, max_frames)


def _progress_percent(frames_processed: int, total_frames: Optional[int]) -> Optional[float]:
    if not total_frames:
        return None
    return min(100.0, round((frames_processed / total_frames) * 100.0, 2))


def _should_report_progress(
    progress: Optional[float],
    last_reported_progress: float,
    interval_percent: float,
) -> bool:
    if progress is None:
        return False
    if progress >= 100.0:
        return False
    return progress - last_reported_progress >= interval_percent


def _emit_progress(
    callback: Optional[ProgressCallback],
    *,
    status: str,
    frame_index: int,
    frames_processed: int,
    total_frames: Optional[int],
    progress: Optional[float],
) -> None:
    if callback is None:
        return
    callback(
        VideoCountingProgress(
            status=status,
            frame_index=frame_index,
            frames_processed=frames_processed,
            total_frames=total_frames,
            progress=progress,
        ).to_dict()
    )


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
