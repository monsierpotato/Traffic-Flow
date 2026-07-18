"""End-to-end YOLO/ByteTrack/TrafficFlow counting benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from benchmark.counting_eval import run as run_counting_eval
from benchmark.tracking_eval import (
    TRACKING_CLASS_ID,
    _evaluate_trackeval,
    _write_gt_sequence,
    _xyxy_to_xywh,
)
from tfengine.core_ai import YoloByteTrackDetector
from worker.pipeline.detection_filter import filter_detections_for_tracking
from worker.pipeline.tracker import LocalTracker
from worker.services.counting_service import CountingState


NOMINAL_FPS = 25.0
VARIANTS = ["bytetrack", "trafficflow_production"]


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _selected_sequences(split: dict, bucket: str, explicit: str | None, max_sequences: int) -> list[str]:
    if explicit:
        sequence_ids = [item.strip() for item in explicit.split(",") if item.strip()]
    else:
        sequence_ids = list(split["splits"].get(bucket, []))
    if max_sequences > 0:
        sequence_ids = sequence_ids[:max_sequences]
    return sequence_ids


def _frame_numbers(meta: dict, max_frames: int = 0) -> list[int]:
    first = int(meta.get("frame_num_min") or 1)
    last = int(meta.get("frame_num_max") or first)
    numbers = list(range(first, last + 1))
    if max_frames > 0:
        numbers = numbers[:max_frames]
    return numbers


def _image_path(meta: dict, frame_num: int) -> Path:
    return Path(meta["image_dir"]) / f"img{frame_num:05d}.jpg"


def _lane_direction(lanes: list[dict], lane_id: str) -> str:
    for lane in lanes:
        if lane.get("lane_id") == lane_id:
            return str(lane.get("direction_name") or lane_id)
    return lane_id


def _counter_keys(counter: CountingState) -> set[tuple[str, str, int]]:
    keys = set()
    for lane_id, class_map in counter.counters.items():
        for class_name, track_ids in class_map.items():
            for track_id in track_ids:
                keys.add((lane_id, class_name, int(track_id)))
    return keys


def _extract_new_count_events(
    *,
    counter: CountingState,
    previous_keys: set[tuple[str, str, int]],
    sequence_id: str,
    frame_num: int,
    lanes: list[dict],
    variant: str,
) -> list[dict]:
    events = []
    for lane_id, class_name, track_id in sorted(_counter_keys(counter) - previous_keys):
        anchor = None
        debug_track = counter.get_debug_snapshot().get("tracks", {}).get(str(track_id), {})
        if debug_track:
            anchor = debug_track.get("anchor")
        events.append(
            {
                "schema_version": 1,
                "video_id": sequence_id,
                "pred_track_id": track_id,
                "class_name": class_name,
                "lane_id": lane_id,
                "direction": _lane_direction(lanes, lane_id),
                "crossing_frame": frame_num,
                "crossing_time_s": round(frame_num / NOMINAL_FPS, 3),
                "crossing_point": anchor or [],
                "coordinate_space": "source_frame",
                "anchor": "bottom_center",
                "prediction_source": variant,
            }
        )
    return events


def _detections_to_dicts(detections: list[Any], sequence_id: str, frame_num: int) -> list[dict]:
    rows = []
    for det in detections:
        rows.append(
            {
                "schema_version": 1,
                "video_id": sequence_id,
                "frame_num": frame_num,
                "track_id": int(det.track_id),
                "class_id": int(det.class_id),
                "class_name": det.class_name,
                "confidence": round(float(det.confidence), 6),
                "bbox_xyxy": [round(float(v), 3) for v in det.bbox_xyxy],
                "coordinate_space": "source_frame",
                "source": "ultralytics_yolo_bytetrack",
            }
        )
    return rows


def _track_rows_for_mot(frame_num: int, tracks: list[dict]) -> list[str]:
    rows = []
    for track in tracks:
        bbox = track.get("bbox_xyxy") or []
        if len(bbox) != 4:
            continue
        x, y, w, h = _xyxy_to_xywh(bbox)
        rows.append(
            f"{frame_num},{int(track['track_id'])},{x:.3f},{y:.3f},{w:.3f},{h:.3f},"
            f"{float(track.get('confidence', 1.0)):.6f},{TRACKING_CLASS_ID},1"
        )
    return rows


def _production_tracks(raw_detections: list[dict], tracker: LocalTracker, frame_num: int) -> list[dict]:
    outputs = tracker.update(raw_detections, timestamp=frame_num / NOMINAL_FPS)
    rows = []
    for item in outputs:
        rows.append(
            {
                "track_id": item.track_id,
                "bbox_xyxy": [round(float(v), 3) for v in item.bbox_xyxy],
                "class_name": item.class_name,
                "confidence": round(float(item.confidence), 6),
                "kalman_velocity": [round(float(v), 6) for v in item.kalman_velocity],
                "is_lost": item.is_lost,
                "lost_frames": item.lost_frames,
                "hits": item.hits,
                "confirmed": item.confirmed,
            }
        )
    return rows


def _active_for_tracking(tracks: list[dict]) -> list[dict]:
    return [
        track
        for track in tracks
        if track.get("confirmed", True) and not track.get("is_lost", False) and int(track.get("lost_frames", 0) or 0) == 0
    ]


def _run_sequence(
    *,
    sequence_id: str,
    meta: dict,
    lanes: list[dict],
    detector: YoloByteTrackDetector,
    frame_numbers: list[int],
    zone_padding_px: float,
) -> dict[str, Any]:
    state = {
        "bytetrack": {
            "counter": CountingState(lanes),
            "count_keys": set(),
            "detections": [],
            "tracks": [],
            "events": [],
            "mot_rows": [],
        },
        "trafficflow_production": {
            "tracker": LocalTracker(match_threshold=0.3, track_buffer=8, min_hits=1, max_lost_seconds=0.7),
            "counter": CountingState(lanes),
            "count_keys": set(),
            "detections": [],
            "tracks": [],
            "events": [],
            "mot_rows": [],
        },
    }
    timings = []

    for frame_num in frame_numbers:
        frame_path = _image_path(meta, frame_num)
        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue

        infer_t0 = time.perf_counter()
        raw = _detections_to_dicts(detector.detect_and_track(frame), sequence_id, frame_num)
        timings.append(
            {
                "sequence_id": sequence_id,
                "frame_num": frame_num,
                "stage": "yolo_bytetrack",
                "elapsed_ms": round((time.perf_counter() - infer_t0) * 1000.0, 3),
                "detections": len(raw),
            }
        )
        filtered = filter_detections_for_tracking(raw, lanes, zone_padding_px)

        byte_tracks = [
            {
                "track_id": det["track_id"],
                "bbox_xyxy": det["bbox_xyxy"],
                "class_name": det["class_name"],
                "confidence": det["confidence"],
                "confirmed": True,
                "is_lost": False,
                "lost_frames": 0,
            }
            for det in filtered
        ]
        state["bytetrack"]["detections"].extend(raw)
        state["bytetrack"]["tracks"].extend({"schema_version": 1, "video_id": sequence_id, "frame_num": frame_num, **track} for track in byte_tracks)
        state["bytetrack"]["mot_rows"].extend(_track_rows_for_mot(frame_num, byte_tracks))
        previous = state["bytetrack"]["count_keys"]
        state["bytetrack"]["counter"].process_detections(byte_tracks)
        state["bytetrack"]["events"].extend(
            _extract_new_count_events(
                counter=state["bytetrack"]["counter"],
                previous_keys=previous,
                sequence_id=sequence_id,
                frame_num=frame_num,
                lanes=lanes,
                variant="bytetrack",
            )
        )
        state["bytetrack"]["count_keys"] = _counter_keys(state["bytetrack"]["counter"])

        prod_t0 = time.perf_counter()
        prod_tracks = _production_tracks(filtered, state["trafficflow_production"]["tracker"], frame_num)
        timings.append(
            {
                "sequence_id": sequence_id,
                "frame_num": frame_num,
                "stage": "trafficflow_local_tracker",
                "elapsed_ms": round((time.perf_counter() - prod_t0) * 1000.0, 3),
                "detections": len(filtered),
            }
        )
        prod_active = _active_for_tracking(prod_tracks)
        state["trafficflow_production"]["detections"].extend(raw)
        state["trafficflow_production"]["tracks"].extend(
            {"schema_version": 1, "video_id": sequence_id, "frame_num": frame_num, **track}
            for track in prod_tracks
        )
        state["trafficflow_production"]["mot_rows"].extend(_track_rows_for_mot(frame_num, prod_active))
        previous = state["trafficflow_production"]["count_keys"]
        state["trafficflow_production"]["counter"].process_detections(prod_tracks)
        state["trafficflow_production"]["counter"].prune_inactive_tracks(
            {int(track["track_id"]) for track in prod_tracks if not track.get("is_lost")}
        )
        state["trafficflow_production"]["events"].extend(
            _extract_new_count_events(
                counter=state["trafficflow_production"]["counter"],
                previous_keys=previous,
                sequence_id=sequence_id,
                frame_num=frame_num,
                lanes=lanes,
                variant="trafficflow_production",
            )
        )
        state["trafficflow_production"]["count_keys"] = _counter_keys(state["trafficflow_production"]["counter"])

    return {"variants": state, "timings": timings}


def _write_variant_sequence(output: Path, variant: str, sequence_id: str, result: dict[str, Any]) -> None:
    _write_jsonl(output / variant / "raw_detections" / f"{sequence_id}.jsonl", result["detections"])
    _write_jsonl(output / variant / "raw_tracks" / f"{sequence_id}.jsonl", result["tracks"])
    _write_jsonl(output / variant / "raw_counting_events" / f"{sequence_id}.jsonl", result["events"])


def _write_mot_sequence(output: Path, variant: str, sequence_id: str, rows: list[str]) -> None:
    path = output / "trackeval_mot" / "trackers" / variant / "data" / f"{sequence_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def _tracking_summary_from_result(result: dict, variant: str, bucket: str, run_id: str) -> dict:
    combined = result["MotChallenge2DBox"][variant]["COMBINED_SEQ"]["pedestrian"]
    hota = combined["HOTA"]
    clear = combined["CLEAR"]
    identity = combined["Identity"]
    return {
        "run_id": run_id,
        "bucket": bucket,
        "variant": variant,
        "input_source": "end_to_end_yolo_bytetrack",
        "hota": round(float(hota["HOTA"].mean()), 6),
        "deta": round(float(hota["DetA"].mean()), 6),
        "assa": round(float(hota["AssA"].mean()), 6),
        "idf1": round(float(identity["IDF1"]), 6),
        "mota": round(float(clear["MOTA"]), 6),
        "motp": round(float(clear["MOTP"]), 6),
        "id_switches": int(clear["IDSW"]),
        "fragmentations": int(clear["Frag"]),
    }


def _merge_counting_summaries(output: Path, variants: list[str]) -> list[dict]:
    rows = []
    for variant in variants:
        path = output / variant / "counting_eval" / "counting_summary.csv"
        if not path.exists():
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows.append({"variant": variant, **row})
    return rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    split = json.loads(args.split_file.read_text(encoding="utf-8"))
    output = args.output_dir
    if output.exists() and any(output.iterdir()) and not args.allow_existing_output:
        raise FileExistsError(f"Output directory already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    sequence_ids = _selected_sequences(split, args.bucket, args.sequences, args.max_sequences)
    metadata = split["selected_sequence_metadata"]
    detector_kwargs = {
        "model_path": str(args.model),
        "confidence": args.confidence,
        "device": args.device,
        "imgsz": args.imgsz,
        "half": args.half and args.device != "cpu",
        "class_ids": [2, 5, 7],
    }
    timing_rows = []
    conversion_rows = []
    seq_info: dict[str, int] = {}
    root = output / "trackeval_mot"
    filtered_gt_events_dir = output / "gt_events"

    for sequence_id in sequence_ids:
        meta = metadata[sequence_id]
        geometry = json.loads((args.geometry_dir / f"{sequence_id}.json").read_text(encoding="utf-8"))
        lanes = geometry.get("lanes") or []
        frame_numbers = _frame_numbers(meta, args.max_frames_per_sequence)
        max_frame_num = max(frame_numbers) if frame_numbers else 0
        gt_events = [
            event
            for event in _read_jsonl(args.gt_events_dir / f"{sequence_id}.jsonl")
            if not max_frame_num or int(event.get("crossing_frame", 0)) <= max_frame_num
        ]
        _write_jsonl(filtered_gt_events_dir / f"{sequence_id}.jsonl", gt_events)
        detector = YoloByteTrackDetector(**detector_kwargs)
        seq_result = _run_sequence(
            sequence_id=sequence_id,
            meta=meta,
            lanes=lanes,
            detector=detector,
            frame_numbers=frame_numbers,
            zone_padding_px=args.zone_padding_px,
        )
        timing_rows.extend(seq_result["timings"])
        seq_info[sequence_id] = _write_gt_sequence(root, sequence_id, meta, args.max_frames_per_sequence)
        for variant in VARIANTS:
            result = seq_result["variants"][variant]
            _write_variant_sequence(output, variant, sequence_id, result)
            _write_mot_sequence(output, variant, sequence_id, result["mot_rows"])
            conversion_rows.append(
                {
                    "run_id": output.name,
                    "bucket": args.bucket,
                    "sequence_id": sequence_id,
                    "variant": variant,
                    "frames": len(frame_numbers),
                    "raw_detections": len(result["detections"]),
                    "raw_tracks": len(result["tracks"]),
                    "raw_counting_events": len(result["events"]),
                }
            )

    tracking_status = {"status": "pass", "error": ""}
    try:
        trackeval_result = _evaluate_trackeval(root, VARIANTS, seq_info)
        tracking_summary = [
            _tracking_summary_from_result(trackeval_result, variant, args.bucket, output.name)
            for variant in VARIANTS
        ]
    except ModuleNotFoundError as exc:
        tracking_status = {
            "status": "skipped",
            "error": f"{exc}. Run TrackEval on the generated trackeval_mot/ artifacts from an environment with trackeval installed.",
        }
        tracking_summary = []
    _write_csv(
        output / "tracking_summary.csv",
        tracking_summary,
        ["run_id", "bucket", "variant", "input_source", "hota", "deta", "assa", "idf1", "mota", "motp", "id_switches", "fragmentations"],
    )
    _write_json(output / "tracking_status.json", tracking_status)
    _write_csv(
        output / "conversion_audit.csv",
        conversion_rows,
        ["run_id", "bucket", "sequence_id", "variant", "frames", "raw_detections", "raw_tracks", "raw_counting_events"],
    )
    _write_csv(
        output / "stage_timings.csv",
        timing_rows,
        ["sequence_id", "frame_num", "stage", "elapsed_ms", "detections"],
    )

    counting_outputs = {}
    for variant in VARIANTS:
        counting_args = argparse.Namespace(
            split_file=args.split_file,
            buckets=args.bucket,
            sequences=",".join(sequence_ids),
            gt_events_dir=filtered_gt_events_dir,
            pred_events_dir=output / variant / "raw_counting_events",
            prediction_source=f"end_to_end_{variant}",
            tolerance_frames=args.tolerance_frames,
            output_dir=output / variant / "counting_eval",
            reports_dir=None,
            allow_existing_output=True,
        )
        counting_outputs[variant] = run_counting_eval(counting_args)

    counting_summary = _merge_counting_summaries(output, VARIANTS)
    if counting_summary:
        _write_csv(
            output / "counting_summary.csv",
            counting_summary,
            ["variant", *[key for key in counting_summary[0].keys() if key != "variant"]],
        )

    manifest = {
        "schema_version": 1,
        "created_at": _now(),
        "run_id": output.name,
        "bucket": args.bucket,
        "sequences": sequence_ids,
        "model": str(args.model).replace("\\", "/"),
        "imgsz": args.imgsz,
        "confidence": args.confidence,
        "device": args.device,
        "half": args.half and args.device != "cpu",
        "geometry_dir": str(args.geometry_dir).replace("\\", "/"),
        "variants": {
            "bytetrack": "Ultralytics YOLO model.track with bytetrack.yaml, lane/class filter, CountingState",
            "trafficflow_production": "Ultralytics YOLO model.track with bytetrack.yaml, lane/class filter, LocalTracker Kalman, CountingState",
        },
        "artifacts": {
            "tracking_summary": "tracking_summary.csv",
            "tracking_status": "tracking_status.json",
            "counting_summary": "counting_summary.csv",
            "conversion_audit": "conversion_audit.csv",
            "stage_timings": "stage_timings.csv",
            "variant_outputs": "<variant>/raw_detections, <variant>/raw_tracks, <variant>/raw_counting_events",
        },
    }
    _write_json(output / "manifest.json", manifest)
    return {
        "output_dir": str(output).replace("\\", "/"),
        "tracking_status": tracking_status,
        "tracking_summary": tracking_summary,
        "counting_summary": [
            row for row in counting_summary
            if row.get("scope_type") == "overall"
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-file", type=Path, default=Path("benchmark/splits/ua_detrac_split_v1.json"))
    parser.add_argument("--bucket", choices=["smoke_test", "development", "held_out_test"], default="smoke_test")
    parser.add_argument("--sequences")
    parser.add_argument("--max-sequences", type=int, default=0)
    parser.add_argument("--max-frames-per-sequence", type=int, default=0)
    parser.add_argument("--model", type=Path, default=Path("models/yolov8m.pt"))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--device", default="0")
    parser.add_argument("--half", action="store_true")
    parser.add_argument("--geometry-dir", type=Path, default=Path("benchmark/configs/geometry_manual"))
    parser.add_argument("--gt-events-dir", type=Path, default=Path("benchmark/ground_truth/derived_events"))
    parser.add_argument("--zone-padding-px", type=float, default=12.0)
    parser.add_argument("--tolerance-frames", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
