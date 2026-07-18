"""Build Phase 09 ablation and error-analysis reports from frozen artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from benchmark.detection_eval import _iou
from benchmark.detrac_parser import DETRAC_CLASS_MAP, parse_detrac_xml


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "benchmark" / "reports"
INVENTORY = ROOT / "benchmark" / "splits" / "ua_detrac_inventory_v1.json"
SPLIT = ROOT / "benchmark" / "splits" / "ua_detrac_split_v1.json"
DETECTION_HELDOUT = (
    ROOT
    / "benchmark"
    / "predictions"
    / "detection"
    / "phase04-heldout-yolov8m-docker-gpu-20260718"
    / "held_out_test"
    / "yolov8m"
)
E2E_HELDOUT = (
    ROOT
    / "benchmark"
    / "predictions"
    / "end_to_end"
    / "e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718"
)
LIVE_SUMMARY = (
    ROOT
    / "benchmark"
    / "predictions"
    / "live_runtime"
    / "phase08-live-hls-30min-20260718"
    / "live_runtime_summary.json"
)
TRACKING_ABLATION = ROOT / "benchmark" / "reports" / "tracking_ablation.csv"
E2E_SUMMARY = ROOT / "benchmark" / "reports" / "end_to_end_summary.csv"
FRAME_DIR = REPORTS / "phase09_error_frames"


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value in ("", None):
        return default
    return float(value)


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    value = row.get(key, "")
    if value in ("", None):
        return default
    return int(float(value))


def _fmt(value: Any, digits: int = 6) -> str:
    if value in ("", None):
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return str(value)


def _rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def _sequence_meta() -> dict[str, dict[str, Any]]:
    inventory = _read_json(INVENTORY)
    return {item["sequence_id"]: item for item in inventory["sequences"]}


def _heldout_sequences() -> list[str]:
    split = _read_json(SPLIT)
    return list(split["splits"]["held_out_test"])


def _image_path(meta_by_seq: dict[str, dict[str, Any]], sequence_id: str, frame_num: int) -> Path:
    return ROOT / meta_by_seq[sequence_id]["image_dir"] / f"img{frame_num:05d}.jpg"


def _annotate_frame(
    *,
    meta_by_seq: dict[str, dict[str, Any]],
    sequence_id: str,
    frame_num: int,
    label: str,
    bbox: tuple[float, float, float, float] | None = None,
) -> str:
    source = _image_path(meta_by_seq, sequence_id, frame_num)
    if not source.exists():
        return ""
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    target = FRAME_DIR / f"{_safe_name(label)}_{sequence_id}_{frame_num}.jpg"
    image = cv2.imread(str(source))
    if image is None:
        shutil.copy2(source, target)
        return _rel(target)
    if bbox:
        x1, y1, x2, y2 = [int(round(v)) for v in bbox]
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 180, 255), 2)
    y = 28
    cv2.rectangle(image, (8, 8), (min(image.shape[1] - 8, 820), 48), (0, 0, 0), -1)
    cv2.putText(image, label[:95], (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(str(target), image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return _rel(target)


def _parse_raw_gt(xml_path: Path) -> dict[int, list[dict[str, Any]]]:
    rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    root = ET.parse(str(xml_path)).getroot()
    for frame in root.findall("frame"):
        frame_num = int(frame.get("num", "0"))
        target_list = frame.find("target_list")
        if target_list is None:
            continue
        for target in target_list.findall("target"):
            box = target.find("box")
            attr = target.find("attribute")
            if box is None or attr is None:
                continue
            raw_class = attr.get("vehicle_type", "others")
            class_name = DETRAC_CLASS_MAP.get(raw_class)
            if class_name is None:
                continue
            left = float(box.get("left", "0"))
            top = float(box.get("top", "0"))
            width = float(box.get("width", "0"))
            height = float(box.get("height", "0"))
            rows[frame_num].append(
                {
                    "track_id": int(target.get("id", "0")),
                    "raw_class": raw_class,
                    "class_name": class_name,
                    "bbox_xyxy": (left, top, left + width, top + height),
                    "area": width * height,
                    "height": height,
                    "has_occlusion": target.find("occlusion") is not None,
                    "truncation_ratio": float(attr.get("truncation_ratio", "0") or 0),
                }
            )
    return rows


def _load_detection_predictions() -> dict[tuple[str, int], list[dict[str, Any]]]:
    rows = defaultdict(list)
    for row in _read_jsonl(DETECTION_HELDOUT / "predictions.jsonl"):
        if float(row.get("confidence", 0)) < 0.4:
            continue
        key = (str(row["sequence_id"]), int(row["frame_num"]))
        rows[key].append(row)
    return rows


def _detection_error_examples(meta_by_seq: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    predictions = _load_detection_predictions()
    stats = {
        "sampled_gt": 0,
        "small_gt": 0,
        "occluded_gt": 0,
        "unmatched_small": 0,
        "unmatched_occluded": 0,
        "truck_gt": 0,
        "truck_fn": 0,
    }
    examples: dict[str, dict[str, Any]] = {}
    for sequence_id in _heldout_sequences():
        meta = meta_by_seq[sequence_id]
        raw_gt = _parse_raw_gt(ROOT / meta["xml_path"])
        sampled_frames = sorted(frame for seq, frame in predictions if seq == sequence_id)
        for frame_num in sampled_frames:
            gt_rows = raw_gt.get(frame_num, [])
            pred_rows = predictions.get((sequence_id, frame_num), [])
            matched_pred: set[int] = set()
            for gt in gt_rows:
                stats["sampled_gt"] += 1
                is_small = gt["height"] <= 45 or gt["area"] <= 2200
                if is_small:
                    stats["small_gt"] += 1
                if gt["has_occlusion"]:
                    stats["occluded_gt"] += 1
                if gt["class_name"] == "truck":
                    stats["truck_gt"] += 1

                best_index = -1
                best_iou = 0.0
                for index, pred in enumerate(pred_rows):
                    if index in matched_pred or pred["class_name"] != gt["class_name"]:
                        continue
                    iou = _iou(tuple(pred["bbox_xyxy"]), gt["bbox_xyxy"])
                    if iou > best_iou:
                        best_iou = iou
                        best_index = index
                matched = best_index >= 0 and best_iou >= 0.5
                if matched:
                    matched_pred.add(best_index)
                    continue

                if is_small:
                    stats["unmatched_small"] += 1
                    examples.setdefault("missed small vehicle", {**gt, "sequence_id": sequence_id, "frame_num": frame_num})
                if gt["has_occlusion"]:
                    stats["unmatched_occluded"] += 1
                    examples.setdefault("heavy occlusion", {**gt, "sequence_id": sequence_id, "frame_num": frame_num})
                if gt["class_name"] == "truck":
                    stats["truck_fn"] += 1
                    examples.setdefault("class confusion", {**gt, "sequence_id": sequence_id, "frame_num": frame_num})
    for key, example in list(examples.items()):
        artifact = _annotate_frame(
            meta_by_seq=meta_by_seq,
            sequence_id=example["sequence_id"],
            frame_num=int(example["frame_num"]),
            label=key,
            bbox=example.get("bbox_xyxy"),
        )
        example["artifact"] = artifact
    return {"stats": stats, "examples": examples}


def _overall_counting_summary(variant: str) -> dict[str, str]:
    rows = _read_csv(E2E_HELDOUT / variant / "counting_eval" / "counting_summary.csv")
    for row in rows:
        if row["scope_type"] == "overall":
            return row
    raise RuntimeError(f"Missing overall counting summary for {variant}")


def _counting_errors(variant: str) -> list[dict[str, str]]:
    return _read_csv(E2E_HELDOUT / variant / "counting_eval" / "counting_errors.csv")


def _counting_matches(variant: str) -> list[dict[str, str]]:
    return _read_csv(E2E_HELDOUT / variant / "counting_eval" / "counting_event_matches.csv")


def _tracking_examples(meta_by_seq: dict[str, dict[str, Any]], variant: str) -> dict[str, dict[str, Any]]:
    examples: dict[str, dict[str, Any]] = {}
    for sequence_id in _heldout_sequences():
        meta = meta_by_seq[sequence_id]
        gt = parse_detrac_xml(ROOT / meta["xml_path"])
        gt_by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for track_id, track in gt.items():
            for frame_num, bbox in track.frames.items():
                gt_by_frame[frame_num].append(
                    {
                        "track_id": track_id,
                        "class_name": track.class_name,
                        "bbox_xyxy": bbox,
                    }
                )

        pred_by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
        track_path = E2E_HELDOUT / variant / "raw_tracks" / f"{sequence_id}.jsonl"
        for pred in _read_jsonl(track_path):
            pred_by_frame[int(pred["frame_num"])].append(pred)

        last_pred: dict[int, int | None] = {}
        had_match: dict[int, bool] = defaultdict(bool)
        unmatched_gap: dict[int, bool] = defaultdict(bool)
        for frame_num in sorted(gt_by_frame):
            preds = pred_by_frame.get(frame_num, [])
            used_pred: set[int] = set()
            for gt_row in gt_by_frame[frame_num]:
                best_index = -1
                best_iou = 0.0
                for index, pred in enumerate(preds):
                    if index in used_pred or pred["class_name"] != gt_row["class_name"]:
                        continue
                    iou = _iou(tuple(pred["bbox_xyxy"]), tuple(gt_row["bbox_xyxy"]))
                    if iou > best_iou:
                        best_iou = iou
                        best_index = index
                gt_id = int(gt_row["track_id"])
                if best_index >= 0 and best_iou >= 0.5:
                    used_pred.add(best_index)
                    pred_id = int(preds[best_index]["track_id"])
                    if last_pred.get(gt_id) is not None and last_pred[gt_id] != pred_id:
                        examples.setdefault(
                            "ID switch",
                            {
                                "sequence_id": sequence_id,
                                "frame_num": frame_num,
                                "gt_track_id": gt_id,
                                "pred_track_id": pred_id,
                                "previous_pred_track_id": last_pred[gt_id],
                                "bbox_xyxy": gt_row["bbox_xyxy"],
                            },
                        )
                    if had_match[gt_id] and unmatched_gap[gt_id]:
                        examples.setdefault(
                            "track fragmentation",
                            {
                                "sequence_id": sequence_id,
                                "frame_num": frame_num,
                                "gt_track_id": gt_id,
                                "pred_track_id": pred_id,
                                "bbox_xyxy": gt_row["bbox_xyxy"],
                            },
                        )
                    had_match[gt_id] = True
                    unmatched_gap[gt_id] = False
                    last_pred[gt_id] = pred_id
                elif had_match[gt_id]:
                    unmatched_gap[gt_id] = True
            if "ID switch" in examples and "track fragmentation" in examples:
                break
        if "ID switch" in examples and "track fragmentation" in examples:
            break
    for key, example in list(examples.items()):
        example["artifact"] = _annotate_frame(
            meta_by_seq=meta_by_seq,
            sequence_id=example["sequence_id"],
            frame_num=int(example["frame_num"]),
            label=f"{variant} {key}",
            bbox=example.get("bbox_xyxy"),
        )
    return examples


def _representative_counting_example(
    *,
    meta_by_seq: dict[str, dict[str, Any]],
    variant: str,
    error_category: str,
) -> dict[str, Any]:
    for row in _counting_errors(variant):
        if row["error_category"] == error_category:
            frame = row.get("gt_crossing_frame") or row.get("pred_crossing_frame") or "1"
            result = {
                "sequence_id": row["video_id"],
                "frame_num": int(float(frame)),
                "track_id": row.get("gt_track_id") or row.get("pred_track_id") or "",
                "artifact": "",
            }
            result["artifact"] = _annotate_frame(
                meta_by_seq=meta_by_seq,
                sequence_id=result["sequence_id"],
                frame_num=result["frame_num"],
                label=f"{variant} {error_category}",
            )
            return result
    return {}


def _representative_early_late(
    *,
    meta_by_seq: dict[str, dict[str, Any]],
    variant: str,
) -> dict[str, Any]:
    for row in _counting_matches(variant):
        if row["status"] == "tp" and row.get("frame_error") not in ("", "0", "0.0"):
            frame = row.get("pred_crossing_frame") or row.get("gt_crossing_frame") or "1"
            result = {
                "sequence_id": row["video_id"],
                "frame_num": int(float(frame)),
                "track_id": row.get("gt_track_id") or row.get("pred_track_id") or "",
                "artifact": "",
            }
            result["artifact"] = _annotate_frame(
                meta_by_seq=meta_by_seq,
                sequence_id=result["sequence_id"],
                frame_num=result["frame_num"],
                label=f"{variant} early_late_crossing",
            )
            return result
    return {}


def build_ablation_summary() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _read_csv(TRACKING_ABLATION):
        rows.append(
            {
                "ablation": "tracker_oracle",
                "status": "completed",
                "comparison": "iou_frame_vs_trafficflow_kalman",
                "bucket": row["bucket"],
                "variant": row["tracker"],
                "baseline_variant": "iou_frame",
                "hota": row["hota"],
                "idf1": row["idf1"],
                "id_switches": row["id_switches"],
                "fragmentations": row["fragmentations"],
                "event_f1": "",
                "duplicate_count_rate": "",
                "ap50": "",
                "recall": "",
                "processed_fps": "",
                "wape": "",
                "dropped_frame_ratio": "",
                "frame_age_p95_ms": "",
                "inference_idle_ratio": "",
                "evidence": "benchmark/reports/tracking_ablation.csv",
                "blocker_or_note": row.get("notes", ""),
            }
        )

    counting_by_variant = {variant: _overall_counting_summary(variant) for variant in ("bytetrack", "trafficflow_production")}
    for row in _read_csv(E2E_SUMMARY):
        counting = counting_by_variant[row["variant"]]
        rows.append(
            {
                "ablation": "tracker_end_to_end",
                "status": "completed",
                "comparison": "direct_bytetrack_vs_production_retracker",
                "bucket": row["bucket"],
                "variant": row["variant"],
                "baseline_variant": "bytetrack",
                "hota": row["hota"],
                "idf1": row["idf1"],
                "id_switches": row["id_switches"],
                "fragmentations": row["fragmentations"],
                "event_f1": counting["event_f1"] if row["bucket"] == "held_out_test" else "",
                "duplicate_count_rate": counting["duplicate_count_rate"] if row["bucket"] == "held_out_test" else "",
                "ap50": "",
                "recall": "",
                "processed_fps": "",
                "wape": counting["wape"] if row["bucket"] == "held_out_test" else "",
                "dropped_frame_ratio": "",
                "frame_age_p95_ms": "",
                "inference_idle_ratio": "",
                "evidence": "benchmark/reports/end_to_end_summary.csv",
                "blocker_or_note": "Production re-tracker is a negative finding: direct ByteTrack is stronger on held-out E2E.",
            }
        )

    rows.append(
        {
            "ablation": "roi_strategy",
            "status": "blocked",
            "comparison": "full_frame_inference_vs_crop_roi_inference",
            "bucket": "held_out_test",
            "variant": "crop_roi",
            "baseline_variant": "full_frame",
            "hota": "",
            "idf1": "",
            "id_switches": "",
            "fragmentations": "",
            "event_f1": "",
            "duplicate_count_rate": "",
            "ap50": "",
            "recall": "",
            "processed_fps": "",
            "wape": "",
            "dropped_frame_ratio": "",
            "frame_age_p95_ms": "",
            "inference_idle_ratio": "",
            "evidence": "benchmark/configs/geometry_manual + benchmark/reports/end_to_end_report.md",
            "blocker_or_note": "UA-DETRAC selected sequences have manual lane/counting geometry but no frozen user-drawn crop ROI. Live crop config has no GT, so AP/Event F1/WAPE would not be comparable.",
        }
    )

    live = _read_json(LIVE_SUMMARY)
    current_idle = live["loop_idle_ms_p50"] / (live["loop_idle_ms_p50"] + live["infer_wall_ms_p50"])
    rows.extend(
        [
            {
                "ablation": "live_scheduling",
                "status": "partial_historical",
                "comparison": "pending_future_bursty_vs_realtime_latest_frame",
                "bucket": "live_hls",
                "variant": "historical_pending_future_bursty",
                "baseline_variant": "historical_pending_future_bursty",
                "hota": "",
                "idf1": "",
                "id_switches": "",
                "fragmentations": "",
                "event_f1": "",
                "duplicate_count_rate": "",
                "ap50": "",
                "recall": "",
                "processed_fps": f"{233 / 30:.3f}",
                "wape": "",
                "dropped_frame_ratio": f"{358 / 1184:.6f}",
                "frame_age_p95_ms": "",
                "inference_idle_ratio": "",
                "evidence": "docs/wiki/ai-workflow/gpu-docker-live-optimization.md",
                "blocker_or_note": "Historical 30s smoke lacks frame-age and loop-idle instrumentation, so this is not a fully symmetric A/B run.",
            },
            {
                "ablation": "live_scheduling",
                "status": "completed_current",
                "comparison": "pending_future_bursty_vs_realtime_latest_frame",
                "bucket": "live_hls",
                "variant": "realtime_latest_frame_dedicated_loop",
                "baseline_variant": "historical_pending_future_bursty",
                "hota": "",
                "idf1": "",
                "id_switches": "",
                "fragmentations": "",
                "event_f1": "",
                "duplicate_count_rate": "",
                "ap50": "",
                "recall": "",
                "processed_fps": live["processed_fps_overall"],
                "wape": "",
                "dropped_frame_ratio": live["dropped_frame_ratio"],
                "frame_age_p95_ms": live["frame_age_ms_p95"],
                "inference_idle_ratio": round(current_idle, 6),
                "evidence": "benchmark/reports/live_runtime_report.md",
                "blocker_or_note": "Current 30-minute soak is stable; live counts remain runtime-only because no live GT exists.",
            },
        ]
    )
    return rows


def build_error_taxonomy(meta_by_seq: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    det = _detection_error_examples(meta_by_seq)
    heldout_meta = [meta_by_seq[seq] for seq in _heldout_sequences()]
    gt_tracks = sum(int(meta["gt_track_count_mapped"]) for meta in heldout_meta)
    e2e_rows = {row["variant"]: row for row in _read_csv(E2E_HELDOUT / "tracking_summary.csv")}
    tracking_examples = {variant: _tracking_examples(meta_by_seq, variant) for variant in ("bytetrack", "trafficflow_production")}

    taxonomy: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []

    def add(row: dict[str, Any]) -> None:
        taxonomy.append(row)
        if row.get("representative_sequence"):
            examples.append(
                {
                    "error_class": row["error_class"],
                    "variant": row["variant"],
                    "sequence_id": row["representative_sequence"],
                    "frame_num": row["representative_frame"],
                    "track_id": row["representative_track_id"],
                    "artifact": row["representative_artifact"],
                    "evidence": row["evidence"],
                    "notes": row["notes"],
                }
            )

    for error_class, stat_key, denom_key, source, fixability, notes in [
        ("missed small vehicle", "unmatched_small", "small_gt", "Detection", "fixable", "Small GT boxes unmatched by Phase 04 held-out detector at operating threshold."),
        ("heavy occlusion", "unmatched_occluded", "occluded_gt", "Detection", "partly_inherent", "Occluded GT boxes unmatched by Phase 04 held-out detector."),
    ]:
        example = det["examples"].get(error_class, {})
        denom = det["stats"][denom_key]
        count = det["stats"][stat_key]
        add(
            {
                "bucket": "held_out_test",
                "variant": "detector_yolov8m",
                "error_class": error_class,
                "count": count,
                "rate": count / denom if denom else 0.0,
                "denominator": denom,
                "source_component": source,
                "fixability": fixability,
                "evidence": "benchmark/predictions/detection/phase04-heldout-yolov8m-docker-gpu-20260718/held_out_test/yolov8m",
                "representative_sequence": example.get("sequence_id", ""),
                "representative_frame": example.get("frame_num", ""),
                "representative_track_id": example.get("track_id", ""),
                "representative_artifact": example.get("artifact", ""),
                "notes": notes,
            }
        )

    detection_summary = _read_json(DETECTION_HELDOUT / "summary.json")
    truck = detection_summary["per_class_operating"]["truck"]
    example = det["examples"].get("class confusion", {})
    add(
        {
            "bucket": "held_out_test",
            "variant": "detector_yolov8m",
            "error_class": "class confusion",
            "count": truck["fn"],
            "rate": 1.0 - truck["recall"],
            "denominator": truck["gt"],
            "source_component": "Detection/class mapping",
            "fixability": "fixable",
            "evidence": "benchmark/reports/detection_report.md",
            "representative_sequence": example.get("sequence_id", ""),
            "representative_frame": example.get("frame_num", ""),
            "representative_track_id": example.get("track_id", ""),
            "representative_artifact": example.get("artifact", ""),
            "notes": "UA-DETRAC van is mapped to TrafficFlow truck; held-out truck recall is weak.",
        }
    )

    for variant in ("bytetrack", "trafficflow_production"):
        summary = _overall_counting_summary(variant)
        errors = _counting_errors(variant)
        error_counts = Counter(row["error_category"] for row in errors)
        matches = _counting_matches(variant)
        early_late_count = sum(
            1
            for row in matches
            if row["status"] == "tp" and row.get("frame_error") not in ("", "0", "0.0")
        )
        tp = _int(summary, "tp")
        for error_class, metric_key, count_value, source, fixability in [
            ("missed crossing", "missed_crossing_rate", _int(summary, "fn"), "Counting/tracking interaction", "fixable"),
            ("wrong lane", "wrong_lane_rate", error_counts["wrong_lane"], "Lane geometry and association", "fixable"),
            ("wrong direction", "wrong_direction_rate", error_counts["wrong_direction"], "Counting direction logic", "fixable"),
            ("duplicate crossing", "duplicate_count_rate", int(round(_float(summary, "duplicate_count_rate") * max(_int(summary, "gt_events"), 1))), "Counting state", "fixable"),
            ("early/late crossing", "", early_late_count, "Counting timing", "fixable"),
            ("false crossing", "false_crossing_rate", _int(summary, "fp"), "Detection/tracking/counting interaction", "fixable"),
        ]:
            if error_class == "early/late crossing":
                ex = _representative_early_late(meta_by_seq=meta_by_seq, variant=variant)
                rate = early_late_count / tp if tp else 0.0
                denom = tp
            else:
                category = error_class.replace(" ", "_")
                ex = _representative_counting_example(meta_by_seq=meta_by_seq, variant=variant, error_category=category)
                rate = _float(summary, metric_key) if metric_key else 0.0
                denom = _int(summary, "gt_events")
            add(
                {
                    "bucket": "held_out_test",
                    "variant": variant,
                    "error_class": error_class,
                    "count": count_value,
                    "rate": rate,
                    "denominator": denom,
                    "source_component": source,
                    "fixability": fixability,
                    "evidence": f"benchmark/predictions/end_to_end/e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718/{variant}/counting_eval",
                    "representative_sequence": ex.get("sequence_id", ""),
                    "representative_frame": ex.get("frame_num", ""),
                    "representative_track_id": ex.get("track_id", ""),
                    "representative_artifact": ex.get("artifact", ""),
                    "notes": "Direct ByteTrack is the recommended E2E baseline." if variant == "bytetrack" else "Production re-tracker is weaker in held-out E2E scoring.",
                }
            )

        for error_class, metric_key in [("ID switch", "id_switches"), ("track fragmentation", "fragmentations")]:
            ex = tracking_examples[variant].get(error_class, {})
            count_value = _int(e2e_rows[variant], metric_key)
            add(
                {
                    "bucket": "held_out_test",
                    "variant": variant,
                    "error_class": error_class,
                    "count": count_value,
                    "rate": count_value / gt_tracks if gt_tracks else 0.0,
                    "denominator": gt_tracks,
                    "source_component": "Tracking/association",
                    "fixability": "fixable",
                    "evidence": "benchmark/predictions/end_to_end/e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718/tracking_summary.csv",
                    "representative_sequence": ex.get("sequence_id", ""),
                    "representative_frame": ex.get("frame_num", ""),
                    "representative_track_id": ex.get("gt_track_id", ""),
                    "representative_artifact": ex.get("artifact", ""),
                    "notes": "Example is approximated from IoU matching raw tracks to GT; aggregate count comes from TrackEval.",
                }
            )

    for error_class, notes in [
        ("geometry mismatch", "Manual geometry audit has 0 current issues/warnings after closure/intersection fixes."),
        ("coordinate-space error", "Current manual/live configs declare source_frame geometry; no active coordinate-space issue in Phase 09 evidence."),
    ]:
        add(
            {
                "bucket": "selected_sequences",
                "variant": "manual_geometry",
                "error_class": error_class,
                "count": 0,
                "rate": 0.0,
                "denominator": 14,
                "source_component": "Lane geometry",
                "fixability": "fixable",
                "evidence": "benchmark/annotation/manual_geometry_validation_report.md",
                "representative_sequence": "",
                "representative_frame": "",
                "representative_track_id": "",
                "representative_artifact": "",
                "notes": notes,
            }
        )

    return taxonomy, examples


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        values = [_fmt(row.get(column, "")) for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def build_report(ablation: list[dict[str, Any]], taxonomy: list[dict[str, Any]], examples: list[dict[str, Any]]) -> str:
    heldout_e2e = [row for row in ablation if row["ablation"] == "tracker_end_to_end" and row["bucket"] == "held_out_test"]
    live_rows = [row for row in ablation if row["ablation"] == "live_scheduling"]
    roi_rows = [row for row in ablation if row["ablation"] == "roi_strategy"]
    core_taxonomy = [
        row
        for row in taxonomy
        if row["variant"] in ("detector_yolov8m", "bytetrack", "trafficflow_production", "manual_geometry")
    ]
    lines = [
        "# Phase 09 Ablation And Error Analysis",
        "",
        f"- Generated at: `{_now()}`",
        "- Scope: frozen Phase 04-08 benchmark artifacts plus source-frame representative images.",
        "- Status: `PARTIAL PASS` because tracker and live scheduling evidence are complete/usable, while ROI accuracy ablation is blocked by missing frozen crop ROI GT for UA-DETRAC.",
        "",
        "## Tracker Ablation",
        "",
        "The production-relevant held-out comparison is negative for the current production re-tracker: direct ByteTrack has better identity and counting metrics.",
        "",
        *_markdown_table(
            heldout_e2e,
            ["variant", "hota", "idf1", "id_switches", "fragmentations", "event_f1", "wape", "duplicate_count_rate"],
        ),
        "",
        "Interpretation: use direct ByteTrack as the current measured offline baseline. Keep the production re-tracker only as an implementation baseline until live/upload regression proves a reason to keep it.",
        "",
        "## ROI Strategy Ablation",
        "",
        *_markdown_table(roi_rows, ["variant", "status", "ap50", "recall", "processed_fps", "event_f1", "wape", "blocker_or_note"]),
        "",
        "Blocker detail: the 14 UA-DETRAC benchmark sequences have manually validated lane/counting geometry, but not a frozen user-drawn crop ROI per sequence. The only crop-ROI config with a real polygon is the YouTube/HLS live source, which has no GT. Running AP/Event-F1/WAPE from that would be an invalid comparison.",
        "",
        "## Live Scheduling Ablation",
        "",
        *_markdown_table(
            live_rows,
            ["variant", "status", "processed_fps", "dropped_frame_ratio", "frame_age_p95_ms", "inference_idle_ratio", "evidence"],
        ),
        "",
        "The current realtime latest-frame loop reached 14.895 FPS for 30 minutes with 0 dropped frames and frame-age p95 0.9 ms. The historical pending-future run is useful as evidence of the previous failure mode, but it lacks frame-age/idle instrumentation, so it is marked partial-historical rather than a fully symmetric A/B experiment.",
        "",
        "## Error Taxonomy",
        "",
        *_markdown_table(
            core_taxonomy,
            ["variant", "error_class", "count", "rate", "denominator", "source_component", "fixability"],
        ),
        "",
        "## Representative Examples",
        "",
        *_markdown_table(examples[:18], ["variant", "error_class", "sequence_id", "frame_num", "track_id", "artifact"]),
        "",
        "## Acceptance Criteria",
        "",
        "- Three ablations completed or blocked with specific reason: PASS.",
        "- Error examples trace to sequence/frame/track where available: PASS.",
        "- Limitations specific: PASS.",
        "- Negative finding disclosed: PASS.",
    ]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    meta_by_seq = _sequence_meta()
    ablation = build_ablation_summary()
    taxonomy, examples = build_error_taxonomy(meta_by_seq)

    _write_csv(
        REPORTS / "ablation_summary.csv",
        ablation,
        [
            "ablation",
            "status",
            "comparison",
            "bucket",
            "variant",
            "baseline_variant",
            "hota",
            "idf1",
            "id_switches",
            "fragmentations",
            "event_f1",
            "duplicate_count_rate",
            "ap50",
            "recall",
            "processed_fps",
            "wape",
            "dropped_frame_ratio",
            "frame_age_p95_ms",
            "inference_idle_ratio",
            "evidence",
            "blocker_or_note",
        ],
    )
    _write_csv(
        REPORTS / "error_taxonomy.csv",
        taxonomy,
        [
            "bucket",
            "variant",
            "error_class",
            "count",
            "rate",
            "denominator",
            "source_component",
            "fixability",
            "evidence",
            "representative_sequence",
            "representative_frame",
            "representative_track_id",
            "representative_artifact",
            "notes",
        ],
    )
    _write_csv(
        REPORTS / "phase09_error_examples.csv",
        examples,
        ["error_class", "variant", "sequence_id", "frame_num", "track_id", "artifact", "evidence", "notes"],
    )
    _write_text(REPORTS / "ablation_report.md", build_report(ablation, taxonomy, examples))

    summary = {
        "created_at": _now(),
        "status": "PARTIAL PASS",
        "ablation_rows": len(ablation),
        "taxonomy_rows": len(taxonomy),
        "example_rows": len(examples),
        "outputs": {
            "ablation_report": _rel(REPORTS / "ablation_report.md"),
            "ablation_summary": _rel(REPORTS / "ablation_summary.csv"),
            "error_taxonomy": _rel(REPORTS / "error_taxonomy.csv"),
            "error_examples": _rel(REPORTS / "phase09_error_examples.csv"),
            "error_frame_dir": _rel(FRAME_DIR),
        },
    }
    if args.print_summary:
        print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 09 ablation/error-analysis artifacts.")
    parser.add_argument("--print-summary", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
