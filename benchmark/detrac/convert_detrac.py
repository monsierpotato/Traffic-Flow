"""One-shot DETRAC preparation: frames→video, lane config, ground truth CSV."""

import cv2
import json
import csv
from pathlib import Path
from typing import List

from benchmark.detrac_parser import parse_detrac_xml, compute_ground_truth_counts

BASE = Path(__file__).parent
IMAGES_DIR = BASE / "ua-detrac-orig" / "DETRAC-Images" / "DETRAC-Images"
XML_DIR = BASE / "ua-detrac-orig" / "DETRAC-Train-Annotations-XML" / "DETRAC-Train-Annotations-XML"
VIDEO_DIR = BASE / "videos"
CONFIG_DIR = BASE / "configs"
GROUND_TRUTH_DIR = Path("benchmark") / "ground_truth"

SEQUENCES = ["MVI_20011", "MVI_20012", "MVI_20035"]
FPS = 25


def build_lane_config(seq: str, w: int, h: int) -> dict:
    """Create a lane config based on sequence characteristics."""
    line_y = int(h * 0.5)

    config = {
        "lanes": [
            {
                "lane_id": "main",
                "counting_line": [[0, line_y], [w, line_y]],
                "class_allowed": ["car", "bus", "truck"],
                "direction": [[w // 2, 0], [w // 2, h]],
                "valid_zone": [[0, 0], [w, 0], [w, h], [0, h]],
            }
        ],
        "roi": None,
        "frame_width": w,
        "frame_height": h,
        "fps": FPS,
    }
    return config


def frames_to_mp4(seq: str) -> Path | None:
    img_dir = IMAGES_DIR / seq
    if not img_dir.exists():
        print(f"  SKIP: {img_dir} not found")
        return None

    frames = sorted(img_dir.glob("*.jpg"))
    if not frames:
        print(f"  SKIP: no frames in {img_dir}")
        return None

    img = cv2.imread(str(frames[0]))
    h, w = img.shape[:2]

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VIDEO_DIR / f"{seq}.mp4"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, FPS, (w, h))

    for fp in frames:
        frame = cv2.imread(str(fp))
        if frame is None:
            continue
        writer.write(frame)

    writer.release()
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"  {seq}: {len(frames)} frames -> {out_path.name} ({size_mb:.1f} MB)")
    return out_path


def make_config(seq: str):
    img_dir = IMAGES_DIR / seq
    frame = sorted(img_dir.glob("*.jpg"))[0]
    img = cv2.imread(str(frame))
    h, w = img.shape[:2]

    config = build_lane_config(seq, w, h)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path = CONFIG_DIR / f"{seq}.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Config -> {config_path}")
    return config, config_path


def make_ground_truth(seq: str, config: dict):
    xml_path = XML_DIR / f"{seq}.xml"
    if not xml_path.exists():
        print(f"  SKIP GT: {xml_path} not found")
        return

    tracklets = parse_detrac_xml(xml_path)
    counts = compute_ground_truth_counts(tracklets, config["lanes"])

    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in counts:
        rows.append({
            "video_id": seq,
            "lane_id": c["lane_id"],
            "class_name": c["vehicle_type"],
            "expected_count": c["expected_count"],
        })

    csv_path = GROUND_TRUTH_DIR / "counts_summary.csv"
    file_exists = csv_path.exists()

    with open(csv_path, "a" if file_exists else "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "lane_id", "class_name", "expected_count"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    total = sum(c["expected_count"] for c in counts)
    classes = {}
    for t in tracklets.values():
        classes[t.class_name] = classes.get(t.class_name, 0) + 1
    print(f"  GT: {len(tracklets)} tracks ({classes}), {total} crossings -> {csv_path}")


def main():
    print("=== DETRAC Conversion Pipeline ===\n")

    for seq in SEQUENCES:
        print(f"[{seq}]")

        mp4_path = frames_to_mp4(seq)
        if mp4_path is None:
            continue

        config, config_path = make_config(seq)
        make_ground_truth(seq, config)
        print()

    print("Done! Run benchmark:")
    for seq in SEQUENCES:
        print(f"  python -m benchmark.run_benchmark --video benchmark/detrac/videos/{seq}.mp4 --config benchmark/detrac/configs/{seq}.json")


if __name__ == "__main__":
    main()
