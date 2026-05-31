import argparse
import csv
import json
import math
from pathlib import Path

import cv2
import numpy as np

from visualize_overlay import draw_lanes


def load_tusimple_records(label_path):
    records = []
    with Path(label_path).open("r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        return records
    for line in text.splitlines():
        records.append(json.loads(line))
    return records


def gt_lane_points(lane_xs, h_samples):
    return [(int(x), int(y)) for x, y in zip(lane_xs, h_samples) if int(x) >= 0]


def lane_to_tusimple_xs(lane, h_samples):
    points = sorted(lane.points, key=lambda p: p[1])
    if len(points) < 2:
        return [-2 for _ in h_samples]

    ys = np.array([p[1] for p in points], dtype=np.float32)
    xs = np.array([p[0] for p in points], dtype=np.float32)
    result = []
    for y in h_samples:
        if y < ys.min() or y > ys.max():
            result.append(-2)
        else:
            result.append(int(round(float(np.interp(y, ys, xs)))))
    return result


def lane_distance(gt_lane, pred_lane, h_samples):
    distances = []
    for gx, px, _y in zip(gt_lane, pred_lane, h_samples):
        if int(gx) >= 0 and int(px) >= 0:
            distances.append(abs(int(gx) - int(px)))
    return float(np.mean(distances)) if distances else math.inf


def evaluate_record(gt_record, pred_record, match_threshold_px=40.0):
    h_samples = gt_record["h_samples"]
    gt_lanes = gt_record.get("lanes", [])
    pred_lanes = pred_record.get("lanes", [])

    available = set(range(len(pred_lanes)))
    matched_distances = []
    tp = 0
    for gt_lane in gt_lanes:
        best_idx = None
        best_distance = math.inf
        for idx in available:
            distance = lane_distance(gt_lane, pred_lanes[idx], h_samples)
            if distance < best_distance:
                best_idx = idx
                best_distance = distance
        if best_idx is not None and best_distance <= match_threshold_px:
            available.remove(best_idx)
            matched_distances.append(best_distance)
            tp += 1

    fp = len(pred_lanes) - tp
    fn = len(gt_lanes) - tp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "gt_lanes": len(gt_lanes),
        "pred_lanes": len(pred_lanes),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_lane_distance_px": float(np.mean(matched_distances)) if matched_distances else math.inf,
        "lane_count_mae": abs(len(pred_lanes) - len(gt_lanes)),
    }


def build_runner(args):
    if args.method == "polylanenet":
        from run_polylanenet_video import PolyLaneNetVideoRunner

        return PolyLaneNetVideoRunner(
            repo_path=args.repo,
            weight_path=args.weights,
            config_path=args.config,
            device=args.device,
            conf_threshold=args.conf_threshold,
        )

    if args.method == "laneatt":
        from run_laneatt_video import LaneATTVideoRunner

        return LaneATTVideoRunner(
            repo_path=args.repo,
            weight_path=args.weights,
            config_path=args.config,
            device=args.device,
            conf_threshold=args.conf_threshold,
        )

    if args.method == "ufld":
        from run_ufld_video import UFLDVideoRunner

        return UFLDVideoRunner(
            repo_path=args.repo,
            weight_path=args.weights,
            dataset=args.dataset,
            backbone=args.backbone,
            device=args.device,
        )

    raise ValueError(f"Unsupported method: {args.method}")


def run_dataset(args):
    dataset_root = Path(args.dataset_root)
    output_dir = Path(args.output_dir)
    overlay_dir = output_dir / "overlays"
    output_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    records = load_tusimple_records(args.label)
    runner = build_runner(args)
    if records and args.warmup_runs > 0:
        warmup_image = cv2.imread(str(dataset_root / records[0]["raw_file"]))
        if warmup_image is None:
            raise FileNotFoundError(f"Cannot read image: {dataset_root / records[0]['raw_file']}")
        for _ in range(args.warmup_runs):
            runner.infer(warmup_image, video_id=dataset_root.name, frame_id=-1)

    predictions_path = output_dir / f"{args.method}_tusimple_predictions.jsonl"
    metrics_path = output_dir / f"{args.method}_tusimple_metrics.csv"
    summary_path = output_dir / f"{args.method}_tusimple_summary.md"

    rows = []
    fps_values = []
    with predictions_path.open("w", encoding="utf-8") as pred_file:
        for index, record in enumerate(records):
            raw_file = record["raw_file"]
            image_path = dataset_root / raw_file
            image = cv2.imread(str(image_path))
            if image is None:
                raise FileNotFoundError(f"Cannot read image: {image_path}")

            result = runner.infer(image, video_id=dataset_root.name, frame_id=index)
            pred_lanes = [lane_to_tusimple_xs(lane, record["h_samples"]) for lane in result.lanes]
            pred_record = {
                "raw_file": raw_file,
                "lanes": pred_lanes,
                "h_samples": record["h_samples"],
                "run_time": int(round(result.runtime.total_ms)),
            }
            pred_file.write(json.dumps(pred_record, ensure_ascii=False) + "\n")

            metric = evaluate_record(record, pred_record, match_threshold_px=args.match_threshold_px)
            fps_values.append(result.runtime.fps)
            rows.append(
                {
                    "sample": index,
                    "raw_file": raw_file,
                    **metric,
                    "preprocess_ms": result.runtime.preprocess_ms,
                    "inference_ms": result.runtime.inference_ms,
                    "postprocess_ms": result.runtime.postprocess_ms,
                    "total_ms": result.runtime.total_ms,
                    "fps": result.runtime.fps,
                }
            )

            overlay = draw_lanes(image.copy(), [lane.__dict__ for lane in result.lanes])
            cv2.imwrite(str(overlay_dir / f"{index:04d}_{Path(raw_file).stem}.jpg"), overlay)

    with metrics_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    finite_distances = [row["mean_lane_distance_px"] for row in rows if math.isfinite(row["mean_lane_distance_px"])]
    summary = {
        "samples": len(rows),
        "avg_precision": float(np.mean([row["precision"] for row in rows])) if rows else 0.0,
        "avg_recall": float(np.mean([row["recall"] for row in rows])) if rows else 0.0,
        "avg_f1": float(np.mean([row["f1"] for row in rows])) if rows else 0.0,
        "avg_lane_count_mae": float(np.mean([row["lane_count_mae"] for row in rows])) if rows else 0.0,
        "avg_mean_lane_distance_px": float(np.mean(finite_distances)) if finite_distances else math.inf,
        "avg_fps": float(np.mean(fps_values)) if fps_values else 0.0,
    }
    summary_path.write_text(
        "\n".join(
            [
                f"# {args.method} TuSimple Dataset Summary",
                "",
                f"- Dataset root: `{dataset_root}`",
                f"- Label file: `{Path(args.label)}`",
                f"- Samples: {summary['samples']}",
                f"- Average precision: {summary['avg_precision']:.4f}",
                f"- Average recall: {summary['avg_recall']:.4f}",
                f"- Average F1: {summary['avg_f1']:.4f}",
                f"- Average lane count MAE: {summary['avg_lane_count_mae']:.4f}",
                f"- Average matched lane distance: {summary['avg_mean_lane_distance_px']:.2f} px",
                f"- Average FPS: {summary['avg_fps']:.2f}",
                "",
                f"Predictions: `{predictions_path.name}`",
                f"Metrics: `{metrics_path.name}`",
                "Overlays: `overlays/`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"{args.method}: samples={summary['samples']}, "
        f"f1={summary['avg_f1']:.4f}, fps={summary['avg_fps']:.2f}, "
        f"metrics={metrics_path}"
    )


def main():
    parser = argparse.ArgumentParser(description="Run a lane model on a TuSimple-format label file.")
    parser.add_argument("--method", choices=["polylanenet", "laneatt", "ufld"], required=True)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--config", default=None)
    parser.add_argument("--dataset", default="Tusimple", choices=["Tusimple", "CULane"])
    parser.add_argument("--backbone", default="18")
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--conf-threshold", type=float, default=None)
    parser.add_argument("--match-threshold-px", type=float, default=40.0)
    parser.add_argument("--warmup-runs", type=int, default=3)
    args = parser.parse_args()
    run_dataset(args)


if __name__ == "__main__":
    main()
