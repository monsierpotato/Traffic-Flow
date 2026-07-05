from __future__ import annotations

import argparse
import json
from pathlib import Path

from tfengine.runtime.engine import TrafficFlowEngine, VideoCountingRequest


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
    request = VideoCountingRequest(
        video_path=args.video,
        config_path=args.config,
        model_path=args.model,
        device=args.device,
        confidence=args.conf,
        max_frames=args.max_frames,
        output_video_path=args.output_video,
        output_jsonl_path=args.output_jsonl,
    )
    result = TrafficFlowEngine().process_video(request)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
