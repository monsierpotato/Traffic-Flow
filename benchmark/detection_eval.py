"""Detection-only benchmark for UA-DETRAC selected sequences."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmark.detrac_parser import parse_detrac_xml


CLASS_NAMES = ["car", "bus", "truck"]
COCO_CLASS_IDS = [2, 5, 7]
COCO_TO_TRAFFICFLOW = {"car": "car", "bus": "bus", "truck": "truck"}
IOU_THRESHOLDS = [round(0.5 + i * 0.05, 2) for i in range(10)]


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


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[int(index)]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _selected_sequences(split: dict, bucket: str, explicit: str | None, max_sequences: int) -> list[str]:
    if explicit:
        sequence_ids = [item.strip() for item in explicit.split(",") if item.strip()]
    else:
        sequence_ids = list(split["splits"].get(bucket, []))
    if max_sequences > 0:
        sequence_ids = sequence_ids[:max_sequences]
    return sequence_ids


def _gt_by_frame(xml_path: Path) -> dict[int, list[dict]]:
    rows: dict[int, list[dict]] = defaultdict(list)
    for track_id, track in parse_detrac_xml(xml_path).items():
        if track.class_name not in CLASS_NAMES:
            continue
        for frame_num, bbox in track.frames.items():
            rows[frame_num].append(
                {
                    "track_id": track_id,
                    "class_name": track.class_name,
                    "bbox_xyxy": tuple(float(v) for v in bbox),
                }
            )
    return rows


def _frame_numbers(meta: dict, stride: int, max_frames: int) -> list[int]:
    first = int(meta.get("frame_num_min") or 1)
    last = int(meta.get("frame_num_max") or first)
    numbers = list(range(first, last + 1, max(1, stride)))
    if max_frames > 0:
        numbers = numbers[:max_frames]
    return numbers


def _image_path(meta: dict, frame_num: int) -> Path:
    return Path(meta["image_dir"]) / f"img{frame_num:05d}.jpg"


def _predict_frame(model: Any, image_path: Path, args: argparse.Namespace) -> tuple[list[dict], float]:
    start = time.perf_counter()
    results = model.predict(
        source=str(image_path),
        conf=args.confidence_floor,
        imgsz=args.imgsz,
        device=args.device,
        classes=COCO_CLASS_IDS,
        verbose=False,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    detections = []
    if not results:
        return detections, elapsed_ms
    result = results[0]
    if result.boxes is None:
        return detections, elapsed_ms
    names = result.names
    boxes = result.boxes.xyxy.cpu().tolist()
    class_ids = result.boxes.cls.cpu().tolist()
    confidences = result.boxes.conf.cpu().tolist()
    for bbox, class_id, conf in zip(boxes, class_ids, confidences):
        class_name = COCO_TO_TRAFFICFLOW.get(str(names.get(int(class_id), class_id)))
        if class_name not in CLASS_NAMES:
            continue
        detections.append(
            {
                "class_name": class_name,
                "confidence": float(conf),
                "bbox_xyxy": tuple(float(v) for v in bbox),
            }
        )
    return detections, elapsed_ms


def _ap_for_class(
    predictions: list[dict],
    gt_by_key: dict[tuple[str, int], list[dict]],
    class_name: str,
    iou_threshold: float,
) -> tuple[float | None, int]:
    class_predictions = [p for p in predictions if p["class_name"] == class_name]
    class_predictions.sort(key=lambda item: item["confidence"], reverse=True)
    total_gt = sum(
        1
        for gt_rows in gt_by_key.values()
        for gt in gt_rows
        if gt["class_name"] == class_name
    )
    if total_gt == 0:
        return None, 0

    matched: set[tuple[str, int, int]] = set()
    tp = []
    fp = []
    for pred in class_predictions:
        key = (pred["sequence_id"], pred["frame_num"])
        candidates = [gt for gt in gt_by_key.get(key, []) if gt["class_name"] == class_name]
        best_index = -1
        best_iou = 0.0
        for index, gt in enumerate(candidates):
            match_key = (key[0], key[1], index)
            if match_key in matched:
                continue
            iou = _iou(pred["bbox_xyxy"], gt["bbox_xyxy"])
            if iou > best_iou:
                best_iou = iou
                best_index = index
        if best_index >= 0 and best_iou >= iou_threshold:
            matched.add((key[0], key[1], best_index))
            tp.append(1)
            fp.append(0)
        else:
            tp.append(0)
            fp.append(1)

    if not tp:
        return 0.0, total_gt

    cum_tp = []
    cum_fp = []
    running_tp = 0
    running_fp = 0
    for t, f in zip(tp, fp):
        running_tp += t
        running_fp += f
        cum_tp.append(running_tp)
        cum_fp.append(running_fp)
    recalls = [value / total_gt for value in cum_tp]
    precisions = [cum_tp[i] / max(cum_tp[i] + cum_fp[i], 1) for i in range(len(cum_tp))]

    ap = 0.0
    for recall_target in [i / 100 for i in range(101)]:
        candidates = [p for r, p in zip(recalls, precisions) if r >= recall_target]
        ap += max(candidates) if candidates else 0.0
    return ap / 101.0, total_gt


def _operating_metrics(
    predictions: list[dict],
    gt_by_key: dict[tuple[str, int], list[dict]],
    threshold: float,
    iou_threshold: float,
    frame_count: int,
) -> dict[str, Any]:
    filtered = [p for p in predictions if p["confidence"] >= threshold]
    per_class = {}
    total_tp = total_fp = total_fn = 0
    for class_name in CLASS_NAMES:
        class_predictions = [p for p in filtered if p["class_name"] == class_name]
        class_predictions.sort(key=lambda item: item["confidence"], reverse=True)
        matched: set[tuple[str, int, int]] = set()
        tp = fp = 0
        total_gt = sum(
            1
            for gt_rows in gt_by_key.values()
            for gt in gt_rows
            if gt["class_name"] == class_name
        )
        for pred in class_predictions:
            key = (pred["sequence_id"], pred["frame_num"])
            candidates = [gt for gt in gt_by_key.get(key, []) if gt["class_name"] == class_name]
            best_index = -1
            best_iou = 0.0
            for index, gt in enumerate(candidates):
                match_key = (key[0], key[1], index)
                if match_key in matched:
                    continue
                iou = _iou(pred["bbox_xyxy"], gt["bbox_xyxy"])
                if iou > best_iou:
                    best_iou = iou
                    best_index = index
            if best_index >= 0 and best_iou >= iou_threshold:
                matched.add((key[0], key[1], best_index))
                tp += 1
            else:
                fp += 1
        fn = total_gt - tp
        total_tp += tp
        total_fp += fp
        total_fn += fn
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / total_gt if total_gt else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[class_name] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "gt": total_gt,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positives_per_frame": total_fp / frame_count if frame_count else 0.0,
        "false_negatives_per_frame": total_fn / frame_count if frame_count else 0.0,
        "per_class": per_class,
    }


def _summarize(
    predictions: list[dict],
    gt_by_key: dict[tuple[str, int], list[dict]],
    latencies_ms: list[float],
    frame_count: int,
    args: argparse.Namespace,
    model_path: Path,
    run_id: str,
    bucket: str,
) -> dict[str, Any]:
    ap50_by_class = {}
    ap5095_by_class = {}
    for class_name in CLASS_NAMES:
        ap50, _ = _ap_for_class(predictions, gt_by_key, class_name, 0.5)
        ap50_by_class[class_name] = ap50
        aps = []
        for threshold in IOU_THRESHOLDS:
            ap, _ = _ap_for_class(predictions, gt_by_key, class_name, threshold)
            if ap is not None:
                aps.append(ap)
        ap5095_by_class[class_name] = statistics.mean(aps) if aps else None

    valid_ap50 = [value for value in ap50_by_class.values() if value is not None]
    valid_ap5095 = [value for value in ap5095_by_class.values() if value is not None]
    operating = _operating_metrics(
        predictions,
        gt_by_key,
        args.operating_threshold,
        args.iou_threshold,
        frame_count,
    )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "bucket": bucket,
        "model_path": str(model_path).replace("\\", "/"),
        "imgsz": args.imgsz,
        "device": args.device,
        "frame_stride": args.frame_stride,
        "max_frames_per_sequence": args.max_frames_per_sequence,
        "sampled_frames": frame_count,
        "confidence_floor": args.confidence_floor,
        "operating_threshold": args.operating_threshold,
        "iou_threshold": args.iou_threshold,
        "precision": operating["precision"],
        "recall": operating["recall"],
        "f1": operating["f1"],
        "ap50": statistics.mean(valid_ap50) if valid_ap50 else 0.0,
        "ap50_95": statistics.mean(valid_ap5095) if valid_ap5095 else 0.0,
        "per_class_ap50": ap50_by_class,
        "per_class_ap50_95": ap5095_by_class,
        "per_class_operating": operating["per_class"],
        "false_positives_per_frame": operating["false_positives_per_frame"],
        "false_negatives_per_frame": operating["false_negatives_per_frame"],
        "latency_ms_p50": _percentile(latencies_ms, 0.50),
        "latency_ms_p95": _percentile(latencies_ms, 0.95),
        "latency_ms_mean": statistics.mean(latencies_ms) if latencies_ms else 0.0,
        "peak_vram_mb": _peak_vram_mb(),
        "software": {"python": platform.python_version(), "platform": platform.platform()},
        "created_at": _now(),
    }


def _peak_vram_mb() -> int:
    try:
        import torch

        if torch.cuda.is_available():
            return int(torch.cuda.max_memory_allocated() / (1024 * 1024))
    except Exception:
        return 0
    return 0


def evaluate_model(model_path: Path, split: dict, bucket: str, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    from ultralytics import YOLO

    sequence_ids = _selected_sequences(split, bucket, args.sequences, args.max_sequences)
    metadata = split["selected_sequence_metadata"]
    run_id = f"{output_dir.name}-{bucket}-{model_path.stem}"
    model_output = output_dir / bucket / model_path.stem
    model_output.mkdir(parents=True, exist_ok=True)

    model = YOLO(str(model_path))
    gt_by_key: dict[tuple[str, int], list[dict]] = {}
    predictions: list[dict] = []
    latency_rows = []
    latencies_ms = []
    sampled_frames = 0

    warmup_meta = metadata[sequence_ids[0]]
    warmup_frame = _image_path(warmup_meta, int(warmup_meta.get("frame_num_min") or 1))
    for _ in range(max(0, args.warmup_frames)):
        _predict_frame(model, warmup_frame, args)

    for sequence_id in sequence_ids:
        meta = metadata[sequence_id]
        gt_rows = _gt_by_frame(Path(meta["xml_path"]))
        frame_numbers = _frame_numbers(meta, args.frame_stride, args.max_frames_per_sequence)
        for frame_num in frame_numbers:
            image_path = _image_path(meta, frame_num)
            if not image_path.exists():
                continue
            key = (sequence_id, frame_num)
            gt_by_key[key] = gt_rows.get(frame_num, [])
            detections, elapsed_ms = _predict_frame(model, image_path, args)
            sampled_frames += 1
            latencies_ms.append(elapsed_ms)
            latency_rows.append(
                {
                    "run_id": run_id,
                    "bucket": bucket,
                    "model": model_path.name,
                    "sequence_id": sequence_id,
                    "frame_num": frame_num,
                    "elapsed_ms": round(elapsed_ms, 3),
                }
            )
            for index, detection in enumerate(detections):
                row = {
                    "schema_version": 1,
                    "run_id": run_id,
                    "bucket": bucket,
                    "model": model_path.name,
                    "sequence_id": sequence_id,
                    "frame_num": frame_num,
                    "detection_index": index,
                    "class_name": detection["class_name"],
                    "confidence": round(detection["confidence"], 6),
                    "bbox_xyxy": [round(v, 3) for v in detection["bbox_xyxy"]],
                }
                predictions.append(row)

    summary = _summarize(predictions, gt_by_key, latencies_ms, sampled_frames, args, model_path, run_id, bucket)
    _write_jsonl(model_output / "predictions.jsonl", predictions)
    _write_csv(
        model_output / "latency.csv",
        latency_rows,
        ["run_id", "bucket", "model", "sequence_id", "frame_num", "elapsed_ms"],
    )
    _write_json(model_output / "summary.json", summary)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    split = json.loads(args.split_file.read_text(encoding="utf-8"))
    output_dir = args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()) and not args.allow_existing_output:
        raise FileExistsError(f"Output directory already exists and is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    models = [Path(item.strip()) for item in args.models.split(",") if item.strip()]
    buckets = [item.strip() for item in args.buckets.split(",") if item.strip()]
    rows = []
    summaries = []
    for bucket in buckets:
        for model_path in models:
            if not model_path.exists():
                raise FileNotFoundError(model_path)
            summary = evaluate_model(model_path, split, bucket, args, output_dir)
            summaries.append(summary)
            rows.append(
                {
                    "run_id": summary["run_id"],
                    "bucket": bucket,
                    "model": model_path.name,
                    "imgsz": summary["imgsz"],
                    "precision": round(summary["precision"], 6),
                    "recall": round(summary["recall"], 6),
                    "f1": round(summary["f1"], 6),
                    "ap50": round(summary["ap50"], 6),
                    "ap50_95": round(summary["ap50_95"], 6),
                    "false_positives_per_frame": round(summary["false_positives_per_frame"], 6),
                    "false_negatives_per_frame": round(summary["false_negatives_per_frame"], 6),
                    "latency_ms_p50": round(summary["latency_ms_p50"], 3),
                    "latency_ms_p95": round(summary["latency_ms_p95"], 3),
                    "peak_vram_mb": summary["peak_vram_mb"],
                    "sampled_frames": summary["sampled_frames"],
                }
            )
    _write_json(output_dir / "manifest.json", {"schema_version": 1, "created_at": _now(), "summaries": summaries})
    _write_csv(
        output_dir / "summary.csv",
        rows,
        [
            "run_id",
            "bucket",
            "model",
            "imgsz",
            "precision",
            "recall",
            "f1",
            "ap50",
            "ap50_95",
            "false_positives_per_frame",
            "false_negatives_per_frame",
            "latency_ms_p50",
            "latency_ms_p95",
            "peak_vram_mb",
            "sampled_frames",
        ],
    )
    return {"output_dir": str(output_dir).replace("\\", "/"), "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-file", type=Path, default=Path("benchmark/splits/ua_detrac_split_v1.json"))
    parser.add_argument("--buckets", default="development")
    parser.add_argument("--sequences")
    parser.add_argument("--models", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--confidence-floor", type=float, default=0.001)
    parser.add_argument("--operating-threshold", type=float, default=0.4)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--frame-stride", type=int, default=100)
    parser.add_argument("--max-frames-per-sequence", type=int, default=0)
    parser.add_argument("--max-sequences", type=int, default=0)
    parser.add_argument("--warmup-frames", type=int, default=3)
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
