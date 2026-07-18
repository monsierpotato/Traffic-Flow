"""Tracking benchmark using TrackEval on UA-DETRAC GT detections."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scipy.optimize import linear_sum_assignment

from benchmark.detrac_parser import parse_detrac_xml
from worker.pipeline.tracker import LocalTracker


TRACKING_EVALUATOR = "TrackEval 1.3.0 MotChallenge2DBox"
NOMINAL_FPS = 25.0
TRACKING_CLASS_ID = 1  # TrackEval MotChallenge2DBox evaluates only "pedestrian".


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _xyxy_to_xywh(bbox: tuple[float, float, float, float] | list[float]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = (float(v) for v in bbox)
    return x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)


def _iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def _gt_frames(xml_path: Path) -> dict[int, list[dict]]:
    frames: dict[int, list[dict]] = {}
    for track_id, track in parse_detrac_xml(xml_path).items():
        for frame_num, bbox in track.frames.items():
            frames.setdefault(frame_num, []).append(
                {
                    "track_id": track_id,
                    "class_name": track.class_name,
                    "confidence": 1.0,
                    "bbox_xyxy": [float(v) for v in bbox],
                }
            )
    return frames


def _frame_numbers(meta: dict, max_frames: int = 0) -> list[int]:
    first = int(meta.get("frame_num_min") or 1)
    last = int(meta.get("frame_num_max") or first)
    numbers = list(range(first, last + 1))
    if max_frames > 0:
        numbers = numbers[:max_frames]
    return numbers


class IouOnlyTracker:
    def __init__(self, match_threshold: float = 0.3, track_buffer: int = 8):
        self.match_threshold = match_threshold
        self.track_buffer = track_buffer
        self._tracks: dict[int, dict[str, Any]] = {}
        self._next_id = 1

    def update(self, detections: list[dict]) -> list[dict]:
        track_ids = list(self._tracks)
        matches: list[tuple[int, int]] = []
        if detections and track_ids:
            cost = []
            for det in detections:
                row = []
                for tid in track_ids:
                    track = self._tracks[tid]
                    if det["class_name"] != track["class_name"]:
                        row.append(math.inf)
                        continue
                    iou = _iou(det["bbox_xyxy"], track["bbox_xyxy"])
                    row.append(1.0 - iou if iou >= self.match_threshold else math.inf)
                cost.append(row)
            if any(math.isfinite(value) for row in cost for value in row):
                solved_cost = [[value if math.isfinite(value) else 1_000_000.0 for value in row] for row in cost]
                rows, cols = linear_sum_assignment(solved_cost)
                for row, col in zip(rows, cols):
                    if math.isfinite(cost[row][col]):
                        matches.append((row, track_ids[col]))

        matched_det = {row for row, _ in matches}
        matched_track = {tid for _, tid in matches}
        for row, tid in matches:
            det = detections[row]
            self._tracks[tid].update(
                bbox_xyxy=det["bbox_xyxy"],
                class_name=det["class_name"],
                confidence=det.get("confidence", 1.0),
                lost_frames=0,
            )
        for index, det in enumerate(detections):
            if index in matched_det:
                continue
            tid = self._next_id
            self._next_id += 1
            self._tracks[tid] = {
                "bbox_xyxy": det["bbox_xyxy"],
                "class_name": det["class_name"],
                "confidence": det.get("confidence", 1.0),
                "lost_frames": 0,
            }
            matched_track.add(tid)
        for tid in list(self._tracks):
            if tid not in matched_track:
                self._tracks[tid]["lost_frames"] += 1
                if self._tracks[tid]["lost_frames"] > self.track_buffer:
                    del self._tracks[tid]
        return [
            {
                "track_id": tid,
                "bbox_xyxy": track["bbox_xyxy"],
                "class_name": track["class_name"],
                "confidence": track["confidence"],
            }
            for tid, track in self._tracks.items()
            if track["lost_frames"] == 0
        ]


@dataclass(frozen=True)
class TrackerVariant:
    name: str
    state_model: str
    association_cost_weights: str
    iou_gate: float
    center_distance_gate: str
    class_consistency: bool
    min_hits: int
    track_buffer: int
    max_lost_seconds: float | None
    reset_gap_seconds: float | None


VARIANTS = {
    "iou_frame": TrackerVariant(
        name="iou_frame",
        state_model="frame_based_bbox_memory",
        association_cost_weights="IoU only",
        iou_gate=0.3,
        center_distance_gate="disabled",
        class_consistency=True,
        min_hits=1,
        track_buffer=8,
        max_lost_seconds=None,
        reset_gap_seconds=None,
    ),
    "trafficflow_kalman": TrackerVariant(
        name="trafficflow_kalman",
        state_model="8-state Kalman cx/cy/w/h/vx/vy/vw/vh",
        association_cost_weights="0.5*(1-IoU)+0.4*center_distance_gate",
        iou_gate=0.3,
        center_distance_gate="max(80px, 2.5 * predicted_bbox_diagonal)",
        class_consistency=True,
        min_hits=1,
        track_buffer=8,
        max_lost_seconds=0.7,
        reset_gap_seconds=1.0,
    ),
}


def _selected_sequences(split: dict, bucket: str, explicit: str | None) -> list[str]:
    if explicit:
        return [item.strip() for item in explicit.split(",") if item.strip()]
    return list(split["splits"].get(bucket, []))


def _make_tracker(variant: TrackerVariant) -> Any:
    if variant.name == "iou_frame":
        return IouOnlyTracker(match_threshold=variant.iou_gate, track_buffer=variant.track_buffer)
    if variant.name == "trafficflow_kalman":
        return LocalTracker(
            match_threshold=variant.iou_gate,
            track_buffer=variant.track_buffer,
            min_hits=variant.min_hits,
            max_lost_seconds=variant.max_lost_seconds,
        )
    raise ValueError(f"Unknown tracker variant: {variant.name}")


def _run_tracker_for_sequence(variant: TrackerVariant, meta: dict, max_frames: int) -> tuple[list[str], dict[str, Any]]:
    tracker = _make_tracker(variant)
    gt_frames = _gt_frames(Path(meta["xml_path"]))
    rows = []
    frame_numbers = _frame_numbers(meta, max_frames)
    reset_count = 0
    prev_frame = None
    for frame_num in frame_numbers:
        if (
            variant.reset_gap_seconds is not None
            and prev_frame is not None
            and (frame_num - prev_frame) / NOMINAL_FPS > variant.reset_gap_seconds
            and hasattr(tracker, "reset")
        ):
            tracker.reset()
            reset_count += 1
        detections = gt_frames.get(frame_num, [])
        if variant.name == "trafficflow_kalman":
            outputs = tracker.update(detections, timestamp=frame_num / NOMINAL_FPS)
            active = [item for item in outputs if item.confirmed and not item.is_lost]
            for item in active:
                x, y, w, h = _xyxy_to_xywh(item.bbox_xyxy)
                rows.append(f"{frame_num},{item.track_id},{x:.3f},{y:.3f},{w:.3f},{h:.3f},{item.confidence:.6f},{TRACKING_CLASS_ID},1")
        else:
            outputs = tracker.update(detections)
            for item in outputs:
                x, y, w, h = _xyxy_to_xywh(item["bbox_xyxy"])
                rows.append(f"{frame_num},{item['track_id']},{x:.3f},{y:.3f},{w:.3f},{h:.3f},{item['confidence']:.6f},{TRACKING_CLASS_ID},1")
        prev_frame = frame_num
    return rows, {"frame_count": len(frame_numbers), "reset_count": reset_count}


def _write_gt_sequence(root: Path, sequence_id: str, meta: dict, max_frames: int) -> int:
    rows = []
    gt_frames = _gt_frames(Path(meta["xml_path"]))
    frame_numbers = _frame_numbers(meta, max_frames)
    for frame_num in frame_numbers:
        for det in gt_frames.get(frame_num, []):
            x, y, w, h = _xyxy_to_xywh(det["bbox_xyxy"])
            rows.append(f"{frame_num},{det['track_id']},{x:.3f},{y:.3f},{w:.3f},{h:.3f},1,{TRACKING_CLASS_ID},1")
    gt_path = root / "gt" / sequence_id / "gt" / "gt.txt"
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    gt_path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return len(frame_numbers)


def _write_tracker_sequence(root: Path, tracker_name: str, sequence_id: str, rows: list[str]) -> None:
    path = root / "trackers" / tracker_name / "data" / f"{sequence_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def _evaluate_trackeval(root: Path, tracker_names: list[str], seq_info: dict[str, int]) -> dict:
    import trackeval
    from trackeval.datasets import MotChallenge2DBox
    from trackeval.metrics import CLEAR, HOTA, Identity

    evaluator = trackeval.Evaluator(
        {
            "PRINT_RESULTS": False,
            "PRINT_CONFIG": False,
            "TIME_PROGRESS": False,
            "OUTPUT_SUMMARY": True,
            "OUTPUT_DETAILED": True,
            "PLOT_CURVES": False,
        }
    )
    dataset = MotChallenge2DBox(
        {
            "GT_FOLDER": str(root / "gt"),
            "TRACKERS_FOLDER": str(root / "trackers"),
            "OUTPUT_FOLDER": str(root / "results"),
            "TRACKERS_TO_EVAL": tracker_names,
            "CLASSES_TO_EVAL": ["pedestrian"],
            "BENCHMARK": "MOT17",
            "SPLIT_TO_EVAL": "train",
            "DO_PREPROC": False,
            "SEQ_INFO": seq_info,
            "SKIP_SPLIT_FOL": True,
            "TRACKER_SUB_FOLDER": "data",
            "PRINT_CONFIG": False,
        }
    )
    metrics = [HOTA(), CLEAR({"THRESHOLD": 0.5, "PRINT_CONFIG": False}), Identity({"THRESHOLD": 0.5, "PRINT_CONFIG": False})]
    result, _ = evaluator.evaluate([dataset], metrics, show_progressbar=False)
    return result


def _summary_from_result(result: dict, tracker_name: str, bucket: str, variant: TrackerVariant, run_id: str) -> dict:
    combined = result["MotChallenge2DBox"][tracker_name]["COMBINED_SEQ"]["pedestrian"]
    hota = combined["HOTA"]
    clear = combined["CLEAR"]
    identity = combined["Identity"]
    return {
        "run_id": run_id,
        "bucket": bucket,
        "tracker": tracker_name,
        "evaluator": TRACKING_EVALUATOR,
        "input_source": "ua_detrac_gt_oracle_detections",
        "hota": round(float(hota["HOTA"].mean()), 6),
        "deta": round(float(hota["DetA"].mean()), 6),
        "assa": round(float(hota["AssA"].mean()), 6),
        "loca": round(float(hota["LocA"].mean()), 6),
        "idf1": round(float(identity["IDF1"]), 6),
        "mota": round(float(clear["MOTA"]), 6),
        "motp": round(float(clear["MOTP"]), 6),
        "id_switches": int(clear["IDSW"]),
        "fragmentations": int(clear["Frag"]),
        "mostly_tracked": int(clear["MT"]),
        "mostly_lost": int(clear["ML"]),
        "state_model": variant.state_model,
        "association_cost_weights": variant.association_cost_weights,
        "iou_gate": variant.iou_gate,
        "center_distance_gate": variant.center_distance_gate,
        "class_consistency": variant.class_consistency,
        "min_hits": variant.min_hits,
        "track_buffer": variant.track_buffer,
        "max_lost_seconds": variant.max_lost_seconds if variant.max_lost_seconds is not None else "",
        "reset_gap_seconds": variant.reset_gap_seconds if variant.reset_gap_seconds is not None else "",
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    split = json.loads(args.split_file.read_text(encoding="utf-8"))
    output = args.output_dir
    if output.exists() and any(output.iterdir()) and not args.allow_existing_output:
        raise FileExistsError(f"Output directory already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    bucket = args.bucket
    sequence_ids = _selected_sequences(split, bucket, args.sequences)
    metadata = split["selected_sequence_metadata"]
    variants = [VARIANTS[item.strip()] for item in args.trackers.split(",") if item.strip()]
    seq_info: dict[str, int] = {}
    conversion_rows = []
    root = output / "trackeval_mot"

    for sequence_id in sequence_ids:
        meta = metadata[sequence_id]
        seq_info[sequence_id] = _write_gt_sequence(root, sequence_id, meta, args.max_frames_per_sequence)
        for variant in variants:
            rows, stats = _run_tracker_for_sequence(variant, meta, args.max_frames_per_sequence)
            _write_tracker_sequence(root, variant.name, sequence_id, rows)
            conversion_rows.append(
                {
                    "run_id": output.name,
                    "bucket": bucket,
                    "sequence_id": sequence_id,
                    "tracker": variant.name,
                    "frames": stats["frame_count"],
                    "tracker_rows": len(rows),
                    "reset_count": stats["reset_count"],
                }
            )

    result = _evaluate_trackeval(root, [variant.name for variant in variants], seq_info)
    summary_rows = [
        _summary_from_result(result, variant.name, bucket, variant, output.name)
        for variant in variants
    ]
    _write_csv(
        output / "tracking_summary.csv",
        summary_rows,
        [
            "run_id",
            "bucket",
            "tracker",
            "evaluator",
            "input_source",
            "hota",
            "deta",
            "assa",
            "loca",
            "idf1",
            "mota",
            "motp",
            "id_switches",
            "fragmentations",
            "mostly_tracked",
            "mostly_lost",
            "state_model",
            "association_cost_weights",
            "iou_gate",
            "center_distance_gate",
            "class_consistency",
            "min_hits",
            "track_buffer",
            "max_lost_seconds",
            "reset_gap_seconds",
        ],
    )
    _write_csv(
        output / "conversion_audit.csv",
        conversion_rows,
        ["run_id", "bucket", "sequence_id", "tracker", "frames", "tracker_rows", "reset_count"],
    )
    _write_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "created_at": _now(),
            "bucket": bucket,
            "sequences": sequence_ids,
            "evaluator": TRACKING_EVALUATOR,
            "input_source": "ua_detrac_gt_oracle_detections",
            "vehicle_class_encoding": "all mapped vehicle classes encoded as TrackEval pedestrian class_id=1",
            "trackers": [variant.__dict__ for variant in variants],
            "artifacts": {
                "tracking_summary": "tracking_summary.csv",
                "conversion_audit": "conversion_audit.csv",
                "trackeval_mot": "trackeval_mot/",
            },
        },
    )
    return {"output_dir": str(output).replace("\\", "/"), "summary": summary_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-file", type=Path, default=Path("benchmark/splits/ua_detrac_split_v1.json"))
    parser.add_argument("--bucket", choices=["development", "held_out_test", "smoke_test"], default="development")
    parser.add_argument("--sequences")
    parser.add_argument("--trackers", default="iou_frame,trafficflow_kalman")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-frames-per-sequence", type=int, default=0)
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
