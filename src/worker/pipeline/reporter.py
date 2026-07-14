"""Benchmark reporter — exports results as CSV, JSON, and Markdown report."""

import csv
import json
from pathlib import Path
from typing import List
from worker.pipeline.profiler import BenchmarkResult, FrameTiming


def write_csv(results: List[BenchmarkResult], path: Path) -> Path:
    """Write per-frame timing CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_id", "frame_idx", "decode_ms", "preprocess_ms",
            "inference_ms", "tracking_ms", "counting_ms",
            "overlay_ms", "encode_ms", "total_frame_ms",
        ])
        for r in results:
            for ft in r.frame_timings:
                writer.writerow([
                    r.task_id, ft.frame_idx,
                    round(ft.decode_ms, 3), round(ft.preprocess_ms, 3),
                    round(ft.inference_ms, 3), round(ft.tracking_ms, 3),
                    round(ft.counting_ms, 3), round(ft.overlay_ms, 3),
                    round(ft.encode_ms, 3), round(ft.total_frame_ms, 3),
                ])
    return path


def write_summary_csv(results: List[BenchmarkResult], path: Path) -> Path:
    """Write one-row-per-run summary CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_id", "model", "device", "imgsz", "half", "frame_skip",
            "video_resolution", "video_fps", "total_frames", "processed_frames",
            "total_sec", "effective_fps", "realtime_factor",
            "download_sec", "upload_sec",
            "decode_avg_ms", "decode_p95_ms",
            "preprocess_avg_ms", "preprocess_p95_ms",
            "inference_avg_ms", "inference_p95_ms",
            "tracking_avg_ms", "tracking_p95_ms",
            "counting_avg_ms", "counting_p95_ms",
            "overlay_avg_ms", "overlay_p95_ms",
            "encode_avg_ms", "encode_p95_ms",
            "gpu_util_avg_pct", "vram_peak_mb",
            "cpu_avg_pct", "ram_peak_mb",
            "lane_volume_total", "global_unique_count", "multi_lane_track_count",
        ])
        for r in results:
            d = r.to_dict()
            s = d["stages"]
            res = d["resource"]
            writer.writerow([
                r.task_id, r.model_path, r.device, r.imgsz, r.half, r.frame_skip,
                r.video_resolution, r.video_fps, r.total_frames, r.processed_frames,
                d["total_sec"], d["effective_fps"], d["realtime_factor"],
                d["download_sec"], d["upload_sec"],
                s.get("decode", {}).get("avg_ms", 0), s.get("decode", {}).get("p95_ms", 0),
                s.get("preprocess", {}).get("avg_ms", 0), s.get("preprocess", {}).get("p95_ms", 0),
                s.get("inference", {}).get("avg_ms", 0), s.get("inference", {}).get("p95_ms", 0),
                s.get("tracking", {}).get("avg_ms", 0), s.get("tracking", {}).get("p95_ms", 0),
                s.get("counting", {}).get("avg_ms", 0), s.get("counting", {}).get("p95_ms", 0),
                s.get("overlay", {}).get("avg_ms", 0), s.get("overlay", {}).get("p95_ms", 0),
                s.get("encode", {}).get("avg_ms", 0), s.get("encode", {}).get("p95_ms", 0),
                res["gpu_util_avg_pct"], res["vram_peak_mb"],
                res["cpu_avg_pct"], res["ram_peak_mb"],
                d.get("lane_volume_total", 0),
                d.get("global_unique_count", 0),
                d.get("multi_lane_track_count", 0),
            ])
    return path


def write_json(results: List[BenchmarkResult], path: Path) -> Path:
    """Write full results as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in results], f, indent=2, ensure_ascii=False)
    return path


def write_markdown(
    results: List[BenchmarkResult], path: Path,
    comparisons: dict | None = None,
) -> Path:
    """Write human-readable markdown report.

    Args:
        comparisons: {task_id: ComparisonReport} from ground_truth.compare_counts().
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# TrafficFlow Benchmark Report",
        "",
        f"Generated: {_now()}",
        f"Runs: {len(results)}",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| # | Model | Device | imgsz | Half | Frames | Time (s) | FPS | Real-time | Lane Volume | Unique | Multi-Lane | GPU% | VRAM (MB) |",
        "|---|-------|--------|-------|------|--------|----------|-----|-----------|-------------|--------|------------|------|-----------|",
    ]
    for i, r in enumerate(results, 1):
        d = r.to_dict()
        res = d["resource"]
        lines.append(
            f"| {i} | {r.model_path} | {r.device} | {r.imgsz} | {r.half} | "
            f"{r.processed_frames}/{r.total_frames} | {d['total_sec']} | "
            f"{d['effective_fps']} | {d['realtime_factor']}x | "
            f"{d.get('lane_volume_total', 0)} | {d.get('global_unique_count', 0)} | "
            f"{d.get('multi_lane_track_count', 0)} | "
            f"{res['gpu_util_avg_pct']} | {res['vram_peak_mb']} |"
        )

    lines += [
        "",
        "## Stage Breakdown (avg ms / p95 ms)",
        "",
        "| # | decode | preprocess | inference | tracking | counting | overlay | encode |",
        "|---|--------|------------|-----------|----------|----------|---------|--------|",
    ]
    for i, r in enumerate(results, 1):
        d = r.to_dict()
        s = d["stages"]
        def _cell(name):
            a = s.get(name, {}).get("avg_ms", "-")
            p = s.get(name, {}).get("p95_ms", "-")
            return f"{a} / {p}"
        lines.append(
            f"| {i} | {_cell('decode')} | {_cell('preprocess')} | "
            f"{_cell('inference')} | {_cell('tracking')} | "
            f"{_cell('counting')} | {_cell('overlay')} | {_cell('encode')} |"
        )

    lines += [
        "",
        "## Resource Usage",
        "",
        "| # | GPU Util Avg | VRAM Peak | CPU Avg | RAM Peak |",
        "|---|-------------|-----------|---------|----------|",
    ]
    for i, r in enumerate(results, 1):
        res = r.to_dict()["resource"]
        lines.append(
            f"| {i} | {res['gpu_util_avg_pct']}% | {res['vram_peak_mb']} MB | "
            f"{res['cpu_avg_pct']}% | {res['ram_peak_mb']} MB |"
        )

    if comparisons:
        lines += [
            "",
            "## Ground Truth Accuracy",
            "",
            "| # | Task | Expected | Predicted | Abs Error | Error % | MAE |",
            "|---|------|----------|-----------|-----------|---------|-----|",
        ]
        for i, r in enumerate(results, 1):
            comp = comparisons.get(r.task_id)
            if comp is None:
                continue
            lines.append(
                f"| {i} | {r.task_id} | {comp.total_expected} | "
                f"{comp.total_predicted} | {comp.total_abs_error} | "
                f"{comp.total_error_pct}% | {comp.mae_per_lane} |"
            )

        for i, r in enumerate(results, 1):
            comp = comparisons.get(r.task_id)
            if comp is None or not comp.errors:
                continue
            lines += [
                "",
                f"### {r.task_id} — Per Lane-Class",
                "",
                "| Lane | Class | Expected | Predicted | Abs Error | Error % |",
                "|------|-------|----------|-----------|-----------|---------|",
            ]
            for e in comp.errors:
                lines.append(
                    f"| {e.lane_id} | {e.class_name} | {e.expected} | "
                    f"{e.predicted} | {e.abs_error} | {e.error_pct}% |"
                )

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")
