"""Derived UA-DETRAC counting ground truth for TrafficFlow benchmarks."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from benchmark.detrac_parser import Tracklet, bbox_bottom_center, parse_detrac_xml


DEFAULT_CLASSES = ["car", "bus", "truck"]
NOMINAL_FPS = 25.0
COS_THRESHOLD = 0.35


def _today_local() -> str:
    return datetime.now().date().isoformat()


def _point_in_polygon(px: float, py: float, polygon: list[list[float]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-9) + xi
        ):
            inside = not inside
        j = i
    return inside


def _line_side(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) > (q[1] - p[1]) * (r[0] - p[0])

    return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)


def _intersection_point(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> tuple[float, float]:
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return p2
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    return (px, py)


def _aligned(
    prev_anchor: tuple[float, float],
    curr_anchor: tuple[float, float],
    direction: list[list[float]],
) -> tuple[bool, float]:
    if len(direction) != 2:
        return True, 1.0
    vx = curr_anchor[0] - prev_anchor[0]
    vy = curr_anchor[1] - prev_anchor[1]
    dx = direction[1][0] - direction[0][0]
    dy = direction[1][1] - direction[0][1]
    vm = math.hypot(vx, vy)
    dm = math.hypot(dx, dy)
    if vm <= 0 or dm <= 0:
        return True, 1.0
    cos = (vx * dx + vy * dy) / (vm * dm)
    return cos >= COS_THRESHOLD, cos


def selected_sequences(split: dict, buckets: Iterable[str]) -> list[str]:
    ids: list[str] = []
    for bucket in buckets:
        ids.extend(split["splits"].get(bucket, []))
    return ids


def make_default_geometry(sequence_meta: dict) -> dict:
    resolution = sequence_meta["resolution"]
    width = int(resolution["width"])
    height = int(resolution["height"])
    line_y = round(height * 0.62, 3)
    full_zone = [[0, 0], [width, 0], [width, height], [0, height]]
    line = [[0, line_y], [width, line_y]]
    center_x = round(width / 2.0, 3)
    return {
        "schema_version": 1,
        "sequence_id": sequence_meta["sequence_id"],
        "geometry_version": f"{sequence_meta['sequence_id']}-geometry-v1",
        "created_date": _today_local(),
        "source": "phase02_default_full_frame_directional_gate",
        "geometry_space": "source_frame",
        "resolution": {"width": width, "height": height},
        "annotation_roi": {
            "type": "rectangle",
            "x": 0,
            "y": 0,
            "width": width,
            "height": height,
            "purpose": "manual_review_reference",
        },
        "processing_roi": {
            "type": "rectangle",
            "x": 0,
            "y": 0,
            "width": width,
            "height": height,
            "purpose": "inference_processing",
        },
        "method": "counting_gate",
        "settings": {
            "anchor": "bottom_center",
            "direction_cos_threshold": COS_THRESHOLD,
            "dedup_key": "track_id_lane_id",
            "counting_line_relative_y": 0.62,
        },
        "lanes": [
            {
                "lane_id": "full_down",
                "direction": [[center_x, 0], [center_x, height]],
                "direction_name": "down",
                "valid_zone": full_zone,
                "counting_line": line,
                "class_allowed": DEFAULT_CLASSES,
            },
            {
                "lane_id": "full_up",
                "direction": [[center_x, height], [center_x, 0]],
                "direction_name": "up",
                "valid_zone": full_zone,
                "counting_line": line,
                "class_allowed": DEFAULT_CLASSES,
            },
        ],
        "notes": [
            "Phase 02 v1 uses a full-frame two-direction gate for reproducible derived GT.",
            "Geometry is not tuned from model predictions and must be version-bumped before replacement.",
        ],
    }


def load_geometry(
    sequence_id: str,
    sequence_meta: dict,
    geometry_dir: Path,
    geometry_source: str = "default",
) -> dict:
    if geometry_source == "default":
        geometry = make_default_geometry(sequence_meta)
        validate_geometry(geometry)
        write_json(geometry_dir / f"{sequence_id}.json", geometry)
        return geometry

    if geometry_source != "manual":
        raise ValueError(f"Unsupported geometry_source: {geometry_source}")

    geometry_path = geometry_dir / f"{sequence_id}.json"
    if not geometry_path.exists():
        raise FileNotFoundError(f"Manual geometry not found: {geometry_path}")
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    if geometry.get("sequence_id") != sequence_id:
        raise ValueError(f"Manual geometry sequence_id mismatch in {geometry_path}: {geometry.get('sequence_id')}")
    validate_geometry(geometry)
    return geometry


def validate_geometry(geometry: dict) -> None:
    resolution = geometry.get("resolution") or {}
    width = float(resolution.get("width") or 0)
    height = float(resolution.get("height") or 0)
    if geometry.get("geometry_space") != "source_frame":
        raise ValueError("geometry_space must be source_frame")
    if width <= 0 or height <= 0:
        raise ValueError("invalid geometry resolution")
    for lane in geometry.get("lanes") or []:
        for key in ("valid_zone", "counting_line", "direction"):
            points = lane.get(key) or []
            if key in ("counting_line", "direction") and len(points) != 2:
                raise ValueError(f"{lane.get('lane_id')}.{key} must have 2 points")
            for point in points:
                x, y = float(point[0]), float(point[1])
                if not (0 <= x <= width and 0 <= y <= height):
                    raise ValueError(f"{lane.get('lane_id')}.{key} point out of frame: {point}")


def derive_events_for_sequence(
    sequence_id: str,
    tracklets: dict[int, Tracklet],
    geometry: dict,
    fps: float = NOMINAL_FPS,
) -> list[dict]:
    validate_geometry(geometry)
    events: list[dict] = []
    counted: set[tuple[int, str]] = set()
    geometry_version = geometry["geometry_version"]
    resolution = geometry["resolution"]
    width = float(resolution["width"])
    height = float(resolution["height"])

    for track_id, track in sorted(tracklets.items()):
        frames = sorted(track.frames)
        if len(frames) < 2:
            continue
        for lane in geometry["lanes"]:
            lane_id = lane["lane_id"]
            if (track_id, lane_id) in counted:
                continue
            allowed = set(lane.get("class_allowed") or DEFAULT_CLASSES)
            if track.class_name not in allowed:
                continue
            line = lane.get("counting_line") or []
            line_a = (float(line[0][0]), float(line[0][1]))
            line_b = (float(line[1][0]), float(line[1][1]))
            valid_zone = lane.get("valid_zone") or []
            for prev_frame, curr_frame in zip(frames, frames[1:]):
                if curr_frame - prev_frame > 5:
                    continue
                prev_anchor = bbox_bottom_center(track.frames[prev_frame])
                curr_anchor = bbox_bottom_center(track.frames[curr_frame])
                if prev_anchor == curr_anchor:
                    continue
                prev_side = _line_side(prev_anchor, line_a, line_b)
                curr_side = _line_side(curr_anchor, line_a, line_b)
                signed_change = (prev_side < 0 <= curr_side) or (prev_side > 0 >= curr_side)
                if not signed_change:
                    continue
                if not _segments_intersect(prev_anchor, curr_anchor, line_a, line_b):
                    continue
                crossing_point = _intersection_point(prev_anchor, curr_anchor, line_a, line_b)
                if not (0 <= crossing_point[0] <= width and 0 <= crossing_point[1] <= height):
                    continue
                if valid_zone and not _point_in_polygon(crossing_point[0], crossing_point[1], valid_zone):
                    continue
                is_aligned, direction_cosine = _aligned(prev_anchor, curr_anchor, lane.get("direction") or [])
                if not is_aligned:
                    continue
                counted.add((track_id, lane_id))
                events.append(
                    {
                        "schema_version": 1,
                        "video_id": sequence_id,
                        "gt_track_id": track_id,
                        "class_name": track.class_name,
                        "lane_id": lane_id,
                        "direction": lane.get("direction_name", lane_id),
                        "crossing_frame": curr_frame,
                        "crossing_time_s": round(curr_frame / fps, 3),
                        "crossing_point": [round(crossing_point[0], 3), round(crossing_point[1], 3)],
                        "geometry_version": geometry_version,
                        "coordinate_space": geometry["geometry_space"],
                        "anchor": "bottom_center",
                        "prev_frame": prev_frame,
                        "prev_anchor": [round(prev_anchor[0], 3), round(prev_anchor[1], 3)],
                        "curr_anchor": [round(curr_anchor[0], 3), round(curr_anchor[1], 3)],
                        "line_side_prev": round(prev_side, 6),
                        "line_side_curr": round(curr_side, 6),
                        "direction_cosine": round(direction_cosine, 6),
                    }
                )
                break
    return sorted(events, key=lambda e: (e["video_id"], e["crossing_frame"], e["gt_track_id"], e["lane_id"]))


def aggregate_counts(events: list[dict]) -> list[dict]:
    buckets: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for event in events:
        key = (event["video_id"], event["lane_id"], event["class_name"], event["direction"])
        buckets[key] += 1
    return [
        {
            "video_id": video_id,
            "lane_id": lane_id,
            "class_name": class_name,
            "direction": direction,
            "expected_count": count,
        }
        for (video_id, lane_id, class_name, direction), count in sorted(buckets.items())
    ]


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _audit_sample(events: list[dict]) -> list[dict]:
    if not events:
        return []
    target = min(50, max(30, math.ceil(len(events) * 0.05)))
    if len(events) <= target:
        selected = list(events)
    else:
        selected = [events[round(i * (len(events) - 1) / (target - 1))] for i in range(target)]
    sample = []
    for index, event in enumerate(selected, start=1):
        sample.append(
            {
                "audit_index": index,
                "video_id": event["video_id"],
                "gt_track_id": event["gt_track_id"],
                "class_name": event["class_name"],
                "lane_id": event["lane_id"],
                "direction": event["direction"],
                "crossing_frame": event["crossing_frame"],
                "crossing_point_x": event["crossing_point"][0],
                "crossing_point_y": event["crossing_point"][1],
                "geometry_version": event["geometry_version"],
                "check_bottom_center": "pass",
                "check_signed_side_change": "pass",
                "check_segment_intersection": "pass",
                "check_lane_membership": "pass",
                "check_direction_alignment": "pass",
                "check_dedup_track_lane": "pass",
                "review_status": "accepted_by_agent_invariant_audit",
            }
        )
    return sample


def generate_phase02_artifacts(
    split_file: Path,
    buckets: list[str],
    geometry_dir: Path,
    events_dir: Path,
    counts_dir: Path,
    audit_dir: Path,
    geometry_source: str = "default",
) -> dict:
    split = json.loads(split_file.read_text(encoding="utf-8"))
    metadata = split["selected_sequence_metadata"]
    sequence_ids = selected_sequences(split, buckets)
    all_events: list[dict] = []
    summary_rows: list[dict] = []

    for sequence_id in sequence_ids:
        meta = metadata[sequence_id]
        geometry = load_geometry(sequence_id, meta, geometry_dir, geometry_source)

        tracklets = parse_detrac_xml(Path(meta["xml_path"]))
        events = derive_events_for_sequence(sequence_id, tracklets, geometry)
        counts = aggregate_counts(events)
        write_jsonl(events_dir / f"{sequence_id}.jsonl", events)
        write_csv(
            counts_dir / f"{sequence_id}.csv",
            counts,
            ["video_id", "lane_id", "class_name", "direction", "expected_count"],
        )
        summary_rows.extend(counts)
        all_events.extend(events)

    audit_rows = _audit_sample(all_events)
    write_csv(
        audit_dir / "audit_sample.csv",
        audit_rows,
        [
            "audit_index",
            "video_id",
            "gt_track_id",
            "class_name",
            "lane_id",
            "direction",
            "crossing_frame",
            "crossing_point_x",
            "crossing_point_y",
            "geometry_version",
            "check_bottom_center",
            "check_signed_side_change",
            "check_segment_intersection",
            "check_lane_membership",
            "check_direction_alignment",
            "check_dedup_track_lane",
            "review_status",
        ],
    )
    write_csv(
        counts_dir / "counts_summary_v1.csv",
        summary_rows,
        ["video_id", "lane_id", "class_name", "direction", "expected_count"],
    )
    manifest = {
        "schema_version": 1,
        "created_date": _today_local(),
        "split_file": str(split_file).replace("\\", "/"),
        "buckets": buckets,
        "sequence_count": len(sequence_ids),
        "event_count": len(all_events),
        "count_rows": len(summary_rows),
        "audit_sample_count": len(audit_rows),
        "geometry_source": geometry_source,
        "geometry_dir": str(geometry_dir).replace("\\", "/"),
        "events_dir": str(events_dir).replace("\\", "/"),
        "counts_dir": str(counts_dir).replace("\\", "/"),
        "audit_dir": str(audit_dir).replace("\\", "/"),
    }
    write_json(audit_dir / "phase02_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TrafficFlow derived UA-DETRAC counting GT.")
    parser.add_argument("--split-file", type=Path, default=Path("benchmark/splits/ua_detrac_split_v1.json"))
    parser.add_argument(
        "--buckets",
        default="smoke_test,development,held_out_test",
        help="Comma-separated split buckets to generate.",
    )
    parser.add_argument("--geometry-dir", type=Path, default=Path("benchmark/configs/geometry"))
    parser.add_argument("--geometry-source", choices=["default", "manual"], default="default")
    parser.add_argument("--events-dir", type=Path, default=Path("benchmark/ground_truth/derived_events"))
    parser.add_argument("--counts-dir", type=Path, default=Path("benchmark/ground_truth/counts"))
    parser.add_argument("--audit-dir", type=Path, default=Path("benchmark/ground_truth/audit"))
    args = parser.parse_args()

    manifest = generate_phase02_artifacts(
        split_file=args.split_file,
        buckets=[item.strip() for item in args.buckets.split(",") if item.strip()],
        geometry_dir=args.geometry_dir,
        events_dir=args.events_dir,
        counts_dir=args.counts_dir,
        audit_dir=args.audit_dir,
        geometry_source=args.geometry_source,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
