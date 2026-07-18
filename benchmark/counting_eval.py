"""Counting-event benchmark for derived UA-DETRAC TrafficFlow events."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from scipy.optimize import linear_sum_assignment
except Exception:  # pragma: no cover - exercised only when scipy is unavailable.
    linear_sum_assignment = None


DEFAULT_TOLERANCE_FRAMES = 5
NOMINAL_FPS = 25.0
SUMMARY_FIELDS = [
    "run_id",
    "bucket",
    "scope_type",
    "scope",
    "gt_events",
    "pred_events",
    "tp",
    "fp",
    "fn",
    "event_precision",
    "event_recall",
    "event_f1",
    "missed_crossing_rate",
    "false_crossing_rate",
    "duplicate_count_rate",
    "wrong_lane_rate",
    "wrong_class_rate",
    "wrong_direction_rate",
    "crossing_time_error_median_frames",
    "crossing_time_error_p95_frames",
    "mae",
    "rmse",
    "wape",
    "signed_bias",
    "exact_count_accuracy",
    "within_1_accuracy",
]


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


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


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(ordered[int(index)])
    return float(ordered[lower] * (upper - index) + ordered[upper] * (index - lower))


def _selected_sequences(split: dict, buckets: list[str], explicit: str | None) -> list[tuple[str, str]]:
    if explicit:
        requested = [item.strip() for item in explicit.split(",") if item.strip()]
        bucket_by_sequence = {
            sequence_id: bucket
            for bucket, sequence_ids in split["splits"].items()
            for sequence_id in sequence_ids
        }
        return [(bucket_by_sequence.get(sequence_id, "explicit"), sequence_id) for sequence_id in requested]
    pairs = []
    for bucket in buckets:
        pairs.extend((bucket, sequence_id) for sequence_id in split["splits"].get(bucket, []))
    return pairs


def _event_key(event: dict) -> tuple[str, str, str, str]:
    return (
        str(event["video_id"]),
        str(event["lane_id"]),
        str(event["class_name"]),
        str(event["direction"]),
    )


def _event_id(event: dict, prefix: str) -> str:
    track_id = event.get("pred_track_id", event.get("gt_track_id", "na"))
    return f"{prefix}-{event.get('video_id')}-{event.get('lane_id')}-{event.get('class_name')}-{event.get('direction')}-{track_id}-{event.get('crossing_frame')}"


def _solve_matches(cost: list[list[float]]) -> list[tuple[int, int]]:
    if not cost:
        return []
    if linear_sum_assignment is not None:
        rows, cols = linear_sum_assignment(cost)
        return list(zip([int(row) for row in rows], [int(col) for col in cols]))

    remaining_cols = set(range(len(cost[0])))
    pairs = []
    for row, row_costs in sorted(enumerate(cost), key=lambda item: min(item[1])):
        best_col = min(remaining_cols, key=lambda col: row_costs[col], default=None)
        if best_col is not None:
            pairs.append((row, best_col))
            remaining_cols.remove(best_col)
    return pairs


def match_events(gt_events: list[dict], pred_events: list[dict], tolerance_frames: int) -> list[dict]:
    """One-to-one match events by video/lane/class/direction and crossing time."""
    grouped_gt: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    grouped_pred: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for event in gt_events:
        grouped_gt[_event_key(event)].append(event)
    for event in pred_events:
        grouped_pred[_event_key(event)].append(event)

    rows: list[dict] = []
    matched_gt_ids: set[str] = set()
    matched_pred_ids: set[str] = set()
    all_keys = sorted(set(grouped_gt) | set(grouped_pred))
    for key in all_keys:
        gt_group = sorted(grouped_gt.get(key, []), key=lambda item: (item["crossing_frame"], item.get("gt_track_id", 0)))
        pred_group = sorted(grouped_pred.get(key, []), key=lambda item: (item["crossing_frame"], item.get("pred_track_id", item.get("gt_track_id", 0))))
        if gt_group and pred_group:
            cost = []
            for gt_event in gt_group:
                row = []
                for pred_event in pred_group:
                    frame_error = abs(int(pred_event["crossing_frame"]) - int(gt_event["crossing_frame"]))
                    row.append(float(frame_error) if frame_error <= tolerance_frames else 1_000_000.0)
                cost.append(row)
            for gt_index, pred_index in _solve_matches(cost):
                if cost[gt_index][pred_index] > tolerance_frames:
                    continue
                gt_event = gt_group[gt_index]
                pred_event = pred_group[pred_index]
                gt_id = _event_id(gt_event, "gt")
                pred_id = _event_id(pred_event, "pred")
                matched_gt_ids.add(gt_id)
                matched_pred_ids.add(pred_id)
                frame_error = int(pred_event["crossing_frame"]) - int(gt_event["crossing_frame"])
                rows.append(_match_row("tp", key, gt_event, pred_event, frame_error, "matched"))

        for gt_event in gt_group:
            if _event_id(gt_event, "gt") not in matched_gt_ids:
                rows.append(_match_row("fn", key, gt_event, None, "", "missed_crossing"))
        for pred_event in pred_group:
            if _event_id(pred_event, "pred") not in matched_pred_ids:
                rows.append(_match_row("fp", key, None, pred_event, "", "false_crossing"))

    _classify_fp_errors(rows, gt_events, pred_events, tolerance_frames)
    return sorted(rows, key=lambda row: (row["video_id"], row["gt_crossing_frame"] or row["pred_crossing_frame"], row["status"]))


def _match_row(
    status: str,
    key: tuple[str, str, str, str],
    gt_event: dict | None,
    pred_event: dict | None,
    frame_error: int | str,
    error_category: str,
) -> dict:
    video_id, lane_id, class_name, direction = key
    gt_frame = gt_event.get("crossing_frame") if gt_event else ""
    pred_frame = pred_event.get("crossing_frame") if pred_event else ""
    time_error_s = round(float(frame_error) / NOMINAL_FPS, 3) if isinstance(frame_error, int) else ""
    return {
        "match_id": f"{status}-{video_id}-{lane_id}-{class_name}-{direction}-{gt_frame}-{pred_frame}",
        "status": status,
        "error_category": error_category,
        "video_id": video_id,
        "lane_id": lane_id,
        "class_name": class_name,
        "direction": direction,
        "gt_event_id": _event_id(gt_event, "gt") if gt_event else "",
        "pred_event_id": _event_id(pred_event, "pred") if pred_event else "",
        "gt_track_id": gt_event.get("gt_track_id", "") if gt_event else "",
        "pred_track_id": pred_event.get("pred_track_id", pred_event.get("gt_track_id", "")) if pred_event else "",
        "gt_crossing_frame": gt_frame,
        "pred_crossing_frame": pred_frame,
        "frame_error": frame_error,
        "time_error_s": time_error_s,
    }


def _classify_fp_errors(rows: list[dict], gt_events: list[dict], pred_events: list[dict], tolerance_frames: int) -> None:
    gt_by_video = defaultdict(list)
    pred_by_id = {_event_id(event, "pred"): event for event in pred_events}
    matched_gt_keys = {
        (row["video_id"], row["lane_id"], row["class_name"], row["direction"], row["gt_crossing_frame"])
        for row in rows
        if row["status"] == "tp"
    }
    for event in gt_events:
        gt_by_video[event["video_id"]].append(event)

    for row in rows:
        if row["status"] != "fp":
            continue
        pred_event = pred_by_id.get(row["pred_event_id"])
        if not pred_event:
            continue
        candidates = [
            gt_event
            for gt_event in gt_by_video.get(pred_event["video_id"], [])
            if abs(int(pred_event["crossing_frame"]) - int(gt_event["crossing_frame"])) <= tolerance_frames
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda item: abs(int(pred_event["crossing_frame"]) - int(item["crossing_frame"])))
        best = candidates[0]
        best_key = (
            best["video_id"],
            best["lane_id"],
            best["class_name"],
            best["direction"],
            best["crossing_frame"],
        )
        if (
            best["lane_id"] == pred_event["lane_id"]
            and best["class_name"] == pred_event["class_name"]
            and best["direction"] == pred_event["direction"]
            and best_key in matched_gt_keys
        ):
            row["error_category"] = "duplicate_count"
        elif best["lane_id"] != pred_event["lane_id"]:
            row["error_category"] = "wrong_lane"
        elif best["class_name"] != pred_event["class_name"]:
            row["error_category"] = "wrong_class"
        elif best["direction"] != pred_event["direction"]:
            row["error_category"] = "wrong_direction"


def aggregate_count_rows(events: list[dict]) -> dict[tuple[str, str, str, str], int]:
    counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for event in events:
        counts[_event_key(event)] += 1
    return counts


def aggregate_metrics(gt_events: list[dict], pred_events: list[dict]) -> list[dict]:
    gt_counts = aggregate_count_rows(gt_events)
    pred_counts = aggregate_count_rows(pred_events)
    rows = []
    for video_id, lane_id, class_name, direction in sorted(set(gt_counts) | set(pred_counts)):
        gt_count = gt_counts.get((video_id, lane_id, class_name, direction), 0)
        pred_count = pred_counts.get((video_id, lane_id, class_name, direction), 0)
        signed_error = pred_count - gt_count
        rows.append(
            {
                "video_id": video_id,
                "lane_id": lane_id,
                "class_name": class_name,
                "direction": direction,
                "gt_count": gt_count,
                "pred_count": pred_count,
                "abs_error": abs(signed_error),
                "signed_error": signed_error,
                "exact": int(signed_error == 0),
                "within_1": int(abs(signed_error) <= 1),
            }
        )
    return rows


def summarize_scope(run_id: str, bucket: str, scope_type: str, scope: str, match_rows: list[dict], aggregate_rows: list[dict]) -> dict:
    tp = sum(1 for row in match_rows if row["status"] == "tp")
    fp = sum(1 for row in match_rows if row["status"] == "fp")
    fn = sum(1 for row in match_rows if row["status"] == "fn")
    pred_events = tp + fp
    gt_events = tp + fn
    precision = _safe_div(tp, pred_events)
    recall = _safe_div(tp, gt_events)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    frame_errors = [abs(float(row["frame_error"])) for row in match_rows if row["status"] == "tp"]
    errors = Counter(row["error_category"] for row in match_rows if row["status"] == "fp")
    abs_errors = [float(row["abs_error"]) for row in aggregate_rows]
    signed_errors = [float(row["signed_error"]) for row in aggregate_rows]
    gt_total = sum(float(row["gt_count"]) for row in aggregate_rows)
    unit_count = len(aggregate_rows)
    return {
        "run_id": run_id,
        "bucket": bucket,
        "scope_type": scope_type,
        "scope": scope,
        "gt_events": gt_events,
        "pred_events": pred_events,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "event_precision": round(precision, 6),
        "event_recall": round(recall, 6),
        "event_f1": round(f1, 6),
        "missed_crossing_rate": round(_safe_div(fn, gt_events), 6),
        "false_crossing_rate": round(_safe_div(fp, pred_events), 6),
        "duplicate_count_rate": round(_safe_div(errors["duplicate_count"], pred_events), 6),
        "wrong_lane_rate": round(_safe_div(errors["wrong_lane"], pred_events), 6),
        "wrong_class_rate": round(_safe_div(errors["wrong_class"], pred_events), 6),
        "wrong_direction_rate": round(_safe_div(errors["wrong_direction"], pred_events), 6),
        "crossing_time_error_median_frames": round(_percentile(frame_errors, 0.5), 3),
        "crossing_time_error_p95_frames": round(_percentile(frame_errors, 0.95), 3),
        "mae": round(_safe_div(sum(abs_errors), unit_count), 6),
        "rmse": round(math.sqrt(_safe_div(sum(value * value for value in signed_errors), unit_count)), 6),
        "wape": round(_safe_div(sum(abs_errors), gt_total), 6),
        "signed_bias": round(_safe_div(sum(signed_errors), gt_total), 6),
        "exact_count_accuracy": round(_safe_div(sum(row["exact"] for row in aggregate_rows), unit_count), 6),
        "within_1_accuracy": round(_safe_div(sum(row["within_1"] for row in aggregate_rows), unit_count), 6),
    }


def _filter_events(events: list[dict], field: str, value: str) -> list[dict]:
    return [event for event in events if str(event.get(field)) == value]


def _filter_match_rows(rows: list[dict], field: str, value: str) -> list[dict]:
    return [row for row in rows if str(row.get(field)) == value]


def _filter_aggregate_rows(rows: list[dict], field: str, value: str) -> list[dict]:
    return [row for row in rows if str(row.get(field)) == value]


def make_summary_rows(run_id: str, bucket: str, gt_events: list[dict], pred_events: list[dict], match_rows: list[dict], aggregate_rows: list[dict]) -> list[dict]:
    summaries = [summarize_scope(run_id, bucket, "overall", "all", match_rows, aggregate_rows)]
    for field, scope_type in (("video_id", "video"), ("lane_id", "lane"), ("class_name", "class")):
        values = sorted({str(row[field]) for row in aggregate_rows})
        for value in values:
            summaries.append(
                summarize_scope(
                    run_id,
                    bucket,
                    scope_type,
                    value,
                    _filter_match_rows(match_rows, field if field != "video_id" else "video_id", value),
                    _filter_aggregate_rows(aggregate_rows, field, value),
                )
            )
    return summaries


def consistency_check(pred_events: list[dict], aggregate_rows: list[dict]) -> dict:
    accepted_events = len(pred_events)
    aggregate_total = sum(int(row["pred_count"]) for row in aggregate_rows)
    return {
        "accepted_prediction_events": accepted_events,
        "sum_aggregate_prediction_counts": aggregate_total,
        "is_consistent": accepted_events == aggregate_total,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    split = json.loads(args.split_file.read_text(encoding="utf-8"))
    buckets = [item.strip() for item in args.buckets.split(",") if item.strip()]
    selected = _selected_sequences(split, buckets, args.sequences)
    output = args.output_dir
    if output.exists() and any(output.iterdir()) and not args.allow_existing_output:
        raise FileExistsError(f"Output directory already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    pred_events_all = []
    gt_events_by_bucket: dict[str, list[dict]] = defaultdict(list)
    pred_events_by_bucket: dict[str, list[dict]] = defaultdict(list)
    for bucket, sequence_id in selected:
        gt_events = _read_jsonl(args.gt_events_dir / f"{sequence_id}.jsonl")
        pred_events = _read_jsonl(args.pred_events_dir / f"{sequence_id}.jsonl")
        for index, event in enumerate(pred_events, start=1):
            row = dict(event)
            row["bucket"] = bucket
            row["prediction_event_index"] = index
            row["prediction_source"] = args.prediction_source
            row.setdefault("pred_track_id", row.get("gt_track_id"))
            pred_events_all.append(row)
            pred_events_by_bucket[bucket].append(row)
        gt_events_by_bucket[bucket].extend(gt_events)

    prediction_events_path = output / "events.jsonl"
    _write_jsonl(prediction_events_path, pred_events_all)

    all_summary_rows = []
    all_match_rows = []
    all_error_rows = []
    all_aggregate_rows = []
    consistency = {}
    for bucket in buckets:
        gt_events = gt_events_by_bucket[bucket]
        pred_events = pred_events_by_bucket[bucket]
        match_rows = match_events(gt_events, pred_events, args.tolerance_frames)
        aggregate_rows = aggregate_metrics(gt_events, pred_events)
        bucket_summary_rows = make_summary_rows(output.name, bucket, gt_events, pred_events, match_rows, aggregate_rows)
        all_summary_rows.extend(bucket_summary_rows)
        all_match_rows.extend({"bucket": bucket, **row} for row in match_rows)
        all_error_rows.extend({"bucket": bucket, **row} for row in match_rows if row["status"] != "tp")
        all_aggregate_rows.extend({"bucket": bucket, **row} for row in aggregate_rows)
        consistency[bucket] = consistency_check(pred_events, aggregate_rows)

    _write_csv(output / "counting_event_matches.csv", all_match_rows, ["bucket", *list(_empty_match_row().keys())])
    _write_csv(output / "counting_errors.csv", all_error_rows, ["bucket", *list(_empty_match_row().keys())])
    _write_csv(output / "counting_aggregate_units.csv", all_aggregate_rows, ["bucket", "video_id", "lane_id", "class_name", "direction", "gt_count", "pred_count", "abs_error", "signed_error", "exact", "within_1"])
    _write_csv(output / "counting_summary.csv", all_summary_rows, SUMMARY_FIELDS)
    _write_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "created_at": _now(),
            "run_id": output.name,
            "split_file": str(args.split_file).replace("\\", "/"),
            "buckets": buckets,
            "sequences": [sequence_id for _, sequence_id in selected],
            "gt_events_dir": str(args.gt_events_dir).replace("\\", "/"),
            "pred_events_dir": str(args.pred_events_dir).replace("\\", "/"),
            "prediction_events": "events.jsonl",
            "prediction_source": args.prediction_source,
            "tolerance_frames": args.tolerance_frames,
            "fps": NOMINAL_FPS,
            "consistency": consistency,
        },
    )

    report_paths = {
        "events": prediction_events_path,
        "summary": output / "counting_summary.csv",
        "matches": output / "counting_event_matches.csv",
        "errors": output / "counting_errors.csv",
        "aggregate": output / "counting_aggregate_units.csv",
    }
    if args.reports_dir:
        args.reports_dir.mkdir(parents=True, exist_ok=True)
        for name in ("counting_summary.csv", "counting_event_matches.csv", "counting_errors.csv"):
            shutil.copyfile(output / name, args.reports_dir / name)
            report_paths[name] = args.reports_dir / name

    return {
        "output_dir": str(output).replace("\\", "/"),
        "summary_rows": [row for row in all_summary_rows if row["scope_type"] == "overall"],
        "consistency": consistency,
        "artifacts": {key: str(path).replace("\\", "/") for key, path in report_paths.items()},
    }


def _empty_match_row() -> dict:
    return {
        "match_id": "",
        "status": "",
        "error_category": "",
        "video_id": "",
        "lane_id": "",
        "class_name": "",
        "direction": "",
        "gt_event_id": "",
        "pred_event_id": "",
        "gt_track_id": "",
        "pred_track_id": "",
        "gt_crossing_frame": "",
        "pred_crossing_frame": "",
        "frame_error": "",
        "time_error_s": "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-file", type=Path, default=Path("benchmark/splits/ua_detrac_split_v1.json"))
    parser.add_argument("--buckets", default="development,held_out_test")
    parser.add_argument("--sequences")
    parser.add_argument("--gt-events-dir", type=Path, default=Path("benchmark/ground_truth/derived_events"))
    parser.add_argument("--pred-events-dir", type=Path, required=True)
    parser.add_argument("--prediction-source", default="phase03_derived_gt_smoke_oracle_counting_events")
    parser.add_argument("--tolerance-frames", type=int, default=DEFAULT_TOLERANCE_FRAMES)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, default=Path("benchmark/reports"))
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
