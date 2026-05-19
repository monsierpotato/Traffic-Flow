import argparse
from pathlib import Path

import cv2


def extract_frames(video_path, output_dir, step=30, max_frames=None, image_ext="jpg"):
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    frame_id = 0
    saved_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_id % step == 0:
            out_path = output_dir / f"frame_{saved_id:05d}.{image_ext}"
            cv2.imwrite(str(out_path), frame)
            saved_id += 1

        frame_id += 1
        if max_frames is not None and frame_id >= max_frames:
            break

    cap.release()
    print(f"Saved {saved_id} frames to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Extract sampled frames from a video.")
    parser.add_argument("video_path", help="Input video path.")
    parser.add_argument("output_dir", help="Directory for extracted frames.")
    parser.add_argument("--step", type=int, default=30, help="Save every Nth frame.")
    parser.add_argument("--max-frames", type=int, default=None, help="Stop after reading this many frames.")
    parser.add_argument("--image-ext", default="jpg", choices=["jpg", "png"], help="Output image extension.")
    args = parser.parse_args()

    extract_frames(
        video_path=args.video_path,
        output_dir=args.output_dir,
        step=args.step,
        max_frames=args.max_frames,
        image_ext=args.image_ext,
    )


if __name__ == "__main__":
    main()
