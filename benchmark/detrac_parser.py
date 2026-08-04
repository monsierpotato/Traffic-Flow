"""UA-DETRAC XML annotation parser — extract vehicle tracks and compute ground truth counts.

UA-DETRAC annotation format (per sequence, e.g. MVI_20011.xml):
    <frame num="1">
      <target_list>
        <target id="1">
          <box left="x" top="y" width="w" height="h"/>
          <attribute vehicle_type="car" .../>
        </target>
      </target_list>
    </frame>

Class mapping (DETRAC → TrafficFlow):
    car      → car
    bus      → bus
    van      → truck (closest match)
    others   → skip
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import json


DETRAC_CLASS_MAP = {
    "car": "car",
    "bus": "bus",
    "van": "truck",
    "others": None,
}


@dataclass
class Tracklet:
    track_id: int
    class_name: str
    frames: Dict[int, Tuple[float, float, float, float]] = field(default_factory=dict)


def parse_detrac_xml(xml_path: Path) -> Dict[int, Tracklet]:
    """Parse UA-DETRAC XML → {track_id: Tracklet}.

    Returns tracklets with per-frame bbox (x1,y1,x2,y2) in pixel coords.
    """
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    tracklets: Dict[int, Tracklet] = {}

    for frame_elem in root.findall("frame"):
        frame_num = int(frame_elem.get("num", 0))
        target_list = frame_elem.find("target_list")
        if target_list is None:
            continue

        for target in target_list.findall("target"):
            tid = int(target.get("id", 0))
            box = target.find("box")
            if box is None:
                continue
            left = float(box.get("left", 0))
            top = float(box.get("top", 0))
            w = float(box.get("width", 0))
            h = float(box.get("height", 0))

            attr = target.find("attribute")
            vehicle_type = attr.get("vehicle_type", "others") if attr is not None else "others"

            tf_class = DETRAC_CLASS_MAP.get(vehicle_type)
            if tf_class is None:
                continue

            if tid not in tracklets:
                tracklets[tid] = Tracklet(track_id=tid, class_name=tf_class)

            x2, y2 = left + w, top + h
            tracklets[tid].frames[frame_num] = (left, top, x2, y2)

    return tracklets


def bbox_bottom_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


def segments_intersect(
    a: Tuple[float, float], b: Tuple[float, float],
    c: Tuple[float, float], d: Tuple[float, float],
) -> bool:
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) > (q[1] - p[1]) * (r[0] - p[0])
    return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)


def compute_ground_truth_counts(
    tracklets: Dict[int, Tracklet],
    lanes_config: List[dict],
) -> List[dict]:
    """Derive expected per-lane-per-class counts from DETRAC annotation.

    For each track, checks if its centroid crosses the counting line
    between consecutive annotated frames. Uses full frame-rate annotation
    to avoid frame-skip errors.

    Args:
        tracklets: From parse_detrac_xml().
        lanes_config: Lane config list with counting_line, class_allowed.

    Returns:
        List of {lane_id, vehicle_type, expected_count} rows.
    """
    results = []

    for lane in lanes_config:
        lid = lane["lane_id"]
        counting_line = lane.get("counting_line", [])
        if len(counting_line) != 2:
            continue
        line_pt1 = (counting_line[0][0], counting_line[0][1])
        line_pt2 = (counting_line[1][0], counting_line[1][1])

        allowed_classes = set(lane.get("class_allowed", []))
        if not allowed_classes:
            allowed_classes = {"car", "motorcycle", "bus", "truck"}

        # Count per class
        class_count: Dict[str, Set[int]] = {}

        for tid, track in tracklets.items():
            if track.class_name not in allowed_classes:
                continue

            frames = sorted(track.frames.keys())
            if len(frames) < 2:
                continue

            crossed = False
            for i in range(len(frames) - 1):
                f_prev = frames[i]
                f_curr = frames[i + 1]
                # Skip if frames aren't consecutive
                if f_curr - f_prev > 5:
                    continue

                center_prev = bbox_bottom_center(track.frames[f_prev])
                center_curr = bbox_bottom_center(track.frames[f_curr])

                if center_prev == center_curr:
                    continue

                if segments_intersect(center_prev, center_curr, line_pt1, line_pt2):
                    crossed = True
                    break

            if crossed:
                cls = track.class_name
                if cls not in class_count:
                    class_count[cls] = set()
                class_count[cls].add(tid)

        for cls_name, ids in class_count.items():
            results.append({
                "lane_id": lid,
                "vehicle_type": cls_name,
                "expected_count": len(ids),
            })

    return results


def generate_detrac_ground_truth(
    xml_dir: Path,
    sequences: List[str],
    lanes_config: List[dict],
    output_csv: Path,
):
    """Batch process DETRAC sequences → ground truth CSV.

    Args:
        xml_dir: Directory containing MVI_*.xml files.
        sequences: List of sequence names (e.g. ["MVI_20011", "MVI_20012"]).
        lanes_config: Lane config for counting lines.
        output_csv: Output CSV path.
    """
    rows = []
    for seq in sequences:
        xml_path = xml_dir / f"{seq}.xml"
        if not xml_path.exists():
            print(f"  SKIP: {xml_path} not found")
            continue

        tracklets = parse_detrac_xml(xml_path)
        counts = compute_ground_truth_counts(tracklets, lanes_config)

        for c in counts:
            rows.append({
                "video_id": seq,
                "lane_id": c["lane_id"],
                "class_name": c["vehicle_type"],
                "expected_count": c["expected_count"],
            })

        total = sum(c["expected_count"] for c in counts)
        print(f"  {seq}: {len(tracklets)} tracks, {total} expected crossings")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "lane_id", "class_name", "expected_count"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows → {output_csv}")
    return rows
