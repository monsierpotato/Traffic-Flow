import argparse
import json
from pathlib import Path

import cv2


LANE_COLORS = [
    (64, 220, 255),
    (80, 220, 120),
    (255, 180, 70),
    (220, 120, 255),
    (255, 100, 100),
]


def draw_lanes(frame, lanes, thickness=3):
    for index, lane in enumerate(lanes):
        points = lane.get("points", [])
        if len(points) < 2:
            continue

        color = LANE_COLORS[index % len(LANE_COLORS)]
        for start, end in zip(points[:-1], points[1:]):
            cv2.line(frame, tuple(start), tuple(end), color, thickness, cv2.LINE_AA)

        label = str(lane.get("lane_id", index + 1))
        cv2.putText(
            frame,
            label,
            tuple(points[0]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
    return frame


def overlay_image(image_path, lane_json_path, output_path):
    image_path = Path(image_path)
    lane_json_path = Path(lane_json_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame = cv2.imread(str(image_path))
    if frame is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    lane_result = json.loads(lane_json_path.read_text(encoding="utf-8"))
    frame = draw_lanes(frame, lane_result.get("lanes", []))
    cv2.imwrite(str(output_path), frame)
    print(f"Wrote {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Draw lane schema JSON on one image.")
    parser.add_argument("--image", required=True, help="Input image path.")
    parser.add_argument("--lanes", required=True, help="Lane JSON path.")
    parser.add_argument("--output", required=True, help="Output image path.")
    args = parser.parse_args()
    overlay_image(args.image, args.lanes, args.output)


if __name__ == "__main__":
    main()
