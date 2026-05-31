from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract resized preview frames from videos.")
    parser.add_argument("--data-dir", default=Path("data/raw/danang"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/debug/preview_frames"), type=Path)
    parser.add_argument("--frame-ratio", default=0.5, type=float)
    parser.add_argument("--max-size", default=1280, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for index, video in enumerate(sorted(args.data_dir.glob("*.mp4")), 1):
        cap = cv2.VideoCapture(str(video))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_index = max(0, min(total - 1, round(total * args.frame_ratio)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            print(f"Skipped unreadable video: {video}")
            continue

        height, width = frame.shape[:2]
        scale = min(args.max_size / width, args.max_size / height, 1.0)
        if scale < 1.0:
            frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
        output = args.output_dir / f"video_{index:02d}.jpg"
        cv2.imwrite(str(output), frame)
        print(f"{output}: {video.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
