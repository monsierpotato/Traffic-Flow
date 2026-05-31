from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from trafficflow.core_ai import YoloByteTrackDetector
from trafficflow.counting.methods import TrackObservation, build_counter
from trafficflow.geometry import bbox_bottom_center


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TrafficFlow manual geometry counting engine.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--model", default="models/yolov8n.pt")
    parser.add_argument("--device", default=None)
    parser.add_argument("--conf", default=0.25, type=float)
    parser.add_argument("--max-frames", type=int, help="Stop after this many frames for smoke tests.")
    parser.add_argument("--output-video", type=Path)
    parser.add_argument("--output-jsonl", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    detector = YoloByteTrackDetector(args.model, confidence=args.conf, device=args.device)

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {args.video}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    config = _scale_config_to_video(config, width, height)
    counter = build_counter(config)

    writer = None
    if args.output_video:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        args.output_video.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(args.output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    jsonl_handle = None
    if args.output_jsonl:
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        jsonl_handle = args.output_jsonl.open("w", encoding="utf-8")

    frame_index = 0
    try:
        while True:
            if args.max_frames is not None and frame_index >= args.max_frames:
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
            _draw_overlay(frame, config, detections, observations, events, counter.counts)
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

    print(json.dumps({"frames": frame_index, "counts": counter.counts}, indent=2, ensure_ascii=False))
    return 0


def _scale_config_to_video(config: dict, video_width: int, video_height: int) -> dict:
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


def _draw_overlay(frame, config: dict, detections, observations, events, counts) -> None:
    for lane in config.get("lanes", []):
        if lane.get("valid_zone"):
            pts = [tuple(map(int, p)) for p in lane["valid_zone"]]
            for a, b in zip(pts, pts[1:] + pts[:1]):
                cv2.line(frame, a, b, (0, 180, 255), 2)
        line = [tuple(map(int, p)) for p in lane["counting_line"]]
        cv2.line(frame, line[0], line[1], (0, 0, 255), 2)
        if lane.get("direction"):
            direction = [tuple(map(int, p)) for p in lane["direction"]]
            cv2.arrowedLine(frame, direction[0], direction[1], (255, 80, 0), 2, tipLength=0.25)
        label = f"{lane['lane_id']}: {sum(counts.get(lane['lane_id'], {}).values())}"
        cv2.putText(frame, label, line[0], cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    for detection, observation in zip(detections, observations):
        x1, y1, x2, y2 = [int(v) for v in detection.bbox_xyxy]
        point = tuple(int(v) for v in observation.point)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 220, 40), 2)
        cv2.circle(frame, point, 4, (255, 255, 0), -1)
        cv2.putText(frame, f"{detection.class_name} #{detection.track_id}", (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 220, 40), 1)

    for event in events:
        point = tuple(int(v) for v in event.point)
        cv2.circle(frame, point, 10, (0, 0, 255), 2)


if __name__ == "__main__":
    raise SystemExit(main())
