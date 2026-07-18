"""Uploaded-video runtime benchmark for the full TrafficFlow AI path.

This runner measures decode -> preprocess -> inference -> tracking -> counting
-> render -> encode on local video files. UA-DETRAC image sequences are converted
to benchmark-local MP4 files when a sequence video is not already present.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import cv2

from tfengine.core_ai import YoloByteTrackDetector
from worker.pipeline.detection_filter import filter_detections_for_tracking
from worker.pipeline.processor import FrameProcessor
from worker.pipeline.profiler import PipelineProfiler
from worker.pipeline.renderer import FrameRenderer
from worker.pipeline.tracker import LocalTracker
from worker.services.counting_service import CountingState


NOMINAL_FPS = 25.0
STAGES = ["decode", "preprocess", "inference", "tracking", "counting", "render", "encode", "total"]
VARIANTS = {"bytetrack", "trafficflow_production"}


@dataclass(frozen=True)
class Workload:
    workload_id: str
    bucket: str
    sequence_id: str
    kind: str
    target_resolution: str = "native"


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _percentile(values: Iterable[float], q: float) -> float:
    clean = sorted(float(v) for v in values if v is not None and not math.isnan(float(v)))
    if not clean:
        return 0.0
    if len(clean) == 1:
        return clean[0]
    idx = (len(clean) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return clean[lo]
    return clean[lo] + (clean[hi] - clean[lo]) * (idx - lo)


def _avg(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return sum(vals) / len(vals) if vals else 0.0


def _parse_variants(raw: str) -> list[str]:
    variants = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(variants) - VARIANTS)
    if unknown:
        raise ValueError(f"Unknown variant(s): {', '.join(unknown)}")
    return variants


def _selected_workloads(split: dict, args: argparse.Namespace) -> list[Workload]:
    if args.workloads:
        workloads = []
        for item in args.workloads.split(","):
            parts = [part.strip() for part in item.split(":") if part.strip()]
            if len(parts) == 2:
                workloads.append(Workload(workload_id=f"{parts[0]}_{parts[1]}", kind=parts[0], bucket=args.bucket, sequence_id=parts[1]))
            elif len(parts) == 3:
                workloads.append(Workload(workload_id=f"{parts[0]}_{parts[2]}", kind=parts[0], bucket=parts[1], sequence_id=parts[2]))
            else:
                raise ValueError("Workloads must be '<kind>:<sequence>' or '<kind>:<bucket>:<sequence>'")
        return workloads

    sequence_ids = list(split["splits"].get(args.bucket, []))
    if args.sequences:
        sequence_ids = [item.strip() for item in args.sequences.split(",") if item.strip()]
    if args.max_sequences > 0:
        sequence_ids = sequence_ids[: args.max_sequences]
    return [
        Workload(
            workload_id=f"{args.bucket}_{sequence_id}",
            kind=_classify_duration_kind(float(split["selected_sequence_metadata"][sequence_id]["frame_count_xml"]) / NOMINAL_FPS),
            bucket=args.bucket,
            sequence_id=sequence_id,
        )
        for sequence_id in sequence_ids
    ]


def _classify_duration_kind(duration_s: float) -> str:
    if duration_s < 120:
        return "short"
    if duration_s < 600:
        return "medium"
    return "long"


def _image_path(meta: dict, frame_num: int) -> Path:
    return Path(meta["image_dir"]) / f"img{frame_num:05d}.jpg"


def _frame_numbers(meta: dict, max_frames: int = 0) -> list[int]:
    first = int(meta.get("frame_num_min") or 1)
    last = int(meta.get("frame_num_max") or first)
    numbers = list(range(first, last + 1))
    if max_frames > 0:
        return numbers[:max_frames]
    return numbers


def _create_video_from_sequence(
    *,
    meta: dict,
    output_path: Path,
    fps: float,
    max_frames: int,
) -> dict[str, Any]:
    frame_numbers = _frame_numbers(meta, max_frames)
    if not frame_numbers:
        raise ValueError(f"No frames available for {meta.get('sequence_id')}")
    first_frame = cv2.imread(str(_image_path(meta, frame_numbers[0])))
    if first_frame is None:
        raise RuntimeError(f"Could not read first frame for {meta.get('sequence_id')}")
    height, width = first_frame.shape[:2]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not create input video: {output_path}")
    written = 0
    for frame_num in frame_numbers:
        frame = first_frame if written == 0 else cv2.imread(str(_image_path(meta, frame_num)))
        if frame is None:
            continue
        writer.write(frame)
        written += 1
    writer.release()
    return {
        "video_path": str(output_path).replace("\\", "/"),
        "generated": True,
        "frames_written": written,
        "fps": fps,
        "width": width,
        "height": height,
    }


def _resolve_input_video(args: argparse.Namespace, output: Path, workload: Workload, meta: dict) -> tuple[Path, dict[str, Any]]:
    candidate = args.video_dir / f"{workload.sequence_id}.mp4"
    if candidate.exists():
        return candidate, {"video_path": str(candidate).replace("\\", "/"), "generated": False}
    generated = output / "input_videos" / f"{workload.sequence_id}.mp4"
    info = _create_video_from_sequence(
        meta=meta,
        output_path=generated,
        fps=float(args.nominal_fps),
        max_frames=args.max_frames_per_sequence,
    )
    return generated, info


def _detections_to_dicts(detections: list[Any], transform: Any) -> list[dict]:
    rows = []
    for det in detections:
        rows.append(
            {
                "track_id": int(det.track_id),
                "class_id": int(det.class_id),
                "class_name": det.class_name,
                "confidence": round(float(det.confidence), 6),
                "bbox_xyxy": [round(float(v), 3) for v in transform.bbox_ai_to_crop(list(det.bbox_xyxy))],
                "confirmed": True,
                "is_lost": False,
                "lost_frames": 0,
            }
        )
    return rows


def _production_tracks(raw_detections: list[dict], tracker: LocalTracker, frame_idx: int, fps: float) -> list[dict]:
    outputs = tracker.update(raw_detections, timestamp=frame_idx / fps if fps > 0 else None)
    return [
        {
            "track_id": item.track_id,
            "bbox_xyxy": [round(float(v), 3) for v in item.bbox_xyxy],
            "class_name": item.class_name,
            "confidence": round(float(item.confidence), 6),
            "kalman_velocity": [round(float(v), 6) for v in item.kalman_velocity],
            "confirmed": item.confirmed,
            "is_lost": item.is_lost,
            "lost_frames": item.lost_frames,
        }
        for item in outputs
    ]


def _active_track_ids(tracks: list[dict]) -> set[int]:
    return {int(track["track_id"]) for track in tracks if not track.get("is_lost") and int(track.get("lost_frames", 0) or 0) == 0}


def _counts_snapshot(counter: CountingState) -> dict[str, dict[str, int]]:
    return {
        lane_id: {class_name: len(track_ids) for class_name, track_ids in class_map.items()}
        for lane_id, class_map in counter.counters.items()
    }


def _open_writer(path: Path, fps: float, width: int, height: int) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    for codec in ("mp4v", "avc1", "XVID", "MJPG"):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, (width, height))
        if writer.isOpened():
            return writer
        writer.release()
    raise RuntimeError(f"Could not create overlay video: {path}")


def _run_one(
    *,
    args: argparse.Namespace,
    output: Path,
    workload: Workload,
    meta: dict,
    lanes: list[dict],
    video_path: Path,
    variant: str,
) -> tuple[dict[str, Any], list[dict], list[dict]]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open input video: {video_path}")

    input_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or int(meta.get("frame_count_xml") or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or args.nominal_fps)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_limit = input_frames
    if args.max_frames_per_sequence > 0:
        frame_limit = min(frame_limit, args.max_frames_per_sequence)

    detector = YoloByteTrackDetector(
        model_path=str(args.model),
        confidence=args.confidence,
        device=args.device,
        imgsz=args.imgsz,
        half=args.half and args.device != "cpu",
        class_ids=[2, 5, 7],
    )
    processor = FrameProcessor(roi_input_size=args.imgsz, roi_mode="full_frame", enable_stabilization=False)
    tracker = LocalTracker(match_threshold=0.3, track_buffer=8, min_hits=1, max_lost_seconds=0.7)
    counter = CountingState(lanes)
    renderer = FrameRenderer(lanes)
    profiler = PipelineProfiler(sample_interval_s=args.resource_sample_interval_s)

    overlay_path = output / "overlays" / variant / f"{workload.workload_id}.mp4"
    writer = _open_writer(overlay_path, fps, width, height)
    stage_rows: list[dict] = []

    profiler.start_resource_sampler()
    t_run0 = time.perf_counter()
    processed = 0
    try:
        while processed < frame_limit:
            frame_t0 = time.perf_counter()
            t0 = time.perf_counter()
            ok, frame = cap.read()
            decode_ms = (time.perf_counter() - t0) * 1000.0
            if not ok or frame is None:
                break

            t0 = time.perf_counter()
            cropped, ai_frame, transform = processor.process_for_ai(frame, None, None)
            preprocess_ms = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            raw = _detections_to_dicts(detector.detect_and_track(ai_frame), transform)
            inference_ms = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            filtered = filter_detections_for_tracking(raw, lanes, args.zone_padding_px)
            if variant == "trafficflow_production":
                tracks = _production_tracks(filtered, tracker, processed, fps)
            else:
                tracks = filtered
            tracking_ms = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            counter.process_detections(tracks)
            if variant == "trafficflow_production":
                counter.prune_inactive_tracks(_active_track_ids(tracks))
            counting_ms = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            rendered = renderer.draw(cropped.copy(), tracks, counter.get_debug_snapshot() if args.render_debug else None)
            render_ms = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            writer.write(rendered)
            encode_ms = (time.perf_counter() - t0) * 1000.0
            total_ms = (time.perf_counter() - frame_t0) * 1000.0

            phase = "warmup" if processed < args.warmup_frames else "steady_state"
            stage_rows.append(
                {
                    "run_id": output.name,
                    "workload_id": workload.workload_id,
                    "bucket": workload.bucket,
                    "sequence_id": workload.sequence_id,
                    "variant": variant,
                    "frame_index": processed,
                    "frame_num": processed + 1,
                    "phase": phase,
                    "decode_ms": round(decode_ms, 3),
                    "preprocess_ms": round(preprocess_ms, 3),
                    "inference_ms": round(inference_ms, 3),
                    "tracking_ms": round(tracking_ms, 3),
                    "counting_ms": round(counting_ms, 3),
                    "render_ms": round(render_ms, 3),
                    "encode_ms": round(encode_ms, 3),
                    "total_ms": round(total_ms, 3),
                    "raw_detections": len(raw),
                    "filtered_tracks": len(tracks),
                }
            )
            processed += 1
    finally:
        total_processing_s = time.perf_counter() - t_run0
        profiler.stop_resource_sampler()
        writer.release()
        cap.release()

    resource_rows = [
        {
            "run_id": output.name,
            "workload_id": workload.workload_id,
            "bucket": workload.bucket,
            "sequence_id": workload.sequence_id,
            "variant": variant,
            "sample_index": idx,
            "timestamp": round(sample.timestamp, 3),
            "elapsed_s": round(sample.timestamp - profiler.resource_samples[0].timestamp, 3) if profiler.resource_samples else 0.0,
            "gpu_util_pct": round(sample.gpu_util_pct, 3),
            "vram_used_mb": round(sample.vram_used_mb, 3),
            "vram_total_mb": round(sample.vram_total_mb, 3),
            "cpu_pct": round(sample.cpu_pct, 3),
            "ram_used_mb": round(sample.ram_used_mb, 3),
        }
        for idx, sample in enumerate(profiler.resource_samples)
    ]

    steady_rows = [row for row in stage_rows if row["phase"] == "steady_state"]
    stat_rows = steady_rows or stage_rows
    source_duration_s = processed / fps if fps > 0 else 0.0
    summary = {
        "run_id": output.name,
        "workload_id": workload.workload_id,
        "bucket": workload.bucket,
        "sequence_id": workload.sequence_id,
        "variant": variant,
        "workload_kind": workload.kind,
        "input_video_path": str(video_path).replace("\\", "/"),
        "input_resolution": f"{width}x{height}",
        "input_fps": round(fps, 3),
        "input_frame_count": input_frames,
        "processed_frames": processed,
        "warmup_frames": min(args.warmup_frames, processed),
        "steady_state_frames": max(0, processed - args.warmup_frames),
        "source_duration_s": round(source_duration_s, 3),
        "processing_seconds": round(total_processing_s, 3),
        "processed_fps": round(processed / total_processing_s, 3) if total_processing_s > 0 else 0.0,
        "realtime_factor": round(source_duration_s / total_processing_s, 3) if total_processing_s > 0 else 0.0,
        "model": str(args.model).replace("\\", "/"),
        "imgsz": args.imgsz,
        "device": args.device,
        "half": bool(args.half and args.device != "cpu"),
        "overlay_video": str(overlay_path).replace("\\", "/"),
        "lane_volume_total": counter.get_total_count(),
        "global_unique_count": counter.get_global_unique_count(),
        "counts": _counts_snapshot(counter),
        "resource_samples": len(resource_rows),
        "gpu_util_avg_pct": round(_avg(row["gpu_util_pct"] for row in resource_rows), 3),
        "gpu_util_p95_pct": round(_percentile((row["gpu_util_pct"] for row in resource_rows), 0.95), 3),
        "vram_peak_mb": round(max((row["vram_used_mb"] for row in resource_rows), default=0.0), 3),
        "cpu_util_avg_pct": round(_avg(row["cpu_pct"] for row in resource_rows), 3),
        "cpu_util_p95_pct": round(_percentile((row["cpu_pct"] for row in resource_rows), 0.95), 3),
        "ram_peak_mb": round(max((row["ram_used_mb"] for row in resource_rows), default=0.0), 3),
    }
    for stage in STAGES:
        key = f"{stage}_ms"
        summary[f"{stage}_p50_ms"] = round(_percentile((row[key] for row in stat_rows), 0.50), 3)
        summary[f"{stage}_p95_ms"] = round(_percentile((row[key] for row in stat_rows), 0.95), 3)

    manifest = {
        "schema_version": 1,
        "created_at": _now(),
        "run_id": output.name,
        "workload": workload.__dict__,
        "variant": variant,
        "model": summary["model"],
        "imgsz": args.imgsz,
        "device": args.device,
        "confidence": args.confidence,
        "half": summary["half"],
        "geometry_file": str(args.geometry_dir / f"{workload.sequence_id}.json").replace("\\", "/"),
        "input": {
            "video_path": summary["input_video_path"],
            "resolution": summary["input_resolution"],
            "fps": summary["input_fps"],
            "frame_count": summary["input_frame_count"],
            "source_duration_s": summary["source_duration_s"],
        },
        "warmup": {
            "warmup_frames": summary["warmup_frames"],
            "steady_state_frames": summary["steady_state_frames"],
            "latency_percentiles": "computed on steady_state rows when present, otherwise all rows",
        },
        "artifacts": {
            "overlay_video": summary["overlay_video"],
            "stage_latency": "stage_latency.csv",
            "resource_usage": "resource_usage.csv",
            "batch_runtime_summary": "batch_runtime_summary.csv",
        },
    }
    _write_json(output / "manifests" / f"{workload.workload_id}_{variant}.json", manifest)
    return summary, stage_rows, resource_rows


def _write_markdown_report(path: Path, summary_rows: list[dict], run_manifest: dict[str, Any]) -> None:
    lines = [
        "# Phase 07 Uploaded-Video Runtime Benchmark",
        "",
        f"- Run ID: `{run_manifest['run_id']}`",
        f"- Created: `{run_manifest['created_at']}`",
        f"- Model: `{run_manifest['model']}`",
        f"- Geometry: `{run_manifest['geometry_dir']}`",
        f"- Variants: `{', '.join(run_manifest['variants'])}`",
        f"- Warmup policy: first `{run_manifest['warmup_frames']}` frames per result are marked `warmup`; latency p50/p95 below use steady-state rows.",
        "",
        "## Results",
        "",
        "| Workload | Variant | Input | Frames | FPS | RTF | Infer p95 ms | Total p95 ms | GPU avg/p95 % | VRAM peak MB | CPU avg/p95 % | RAM peak MB |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            "| {workload_id} | {variant} | {input_resolution} @ {input_fps} fps | {processed_frames} | "
            "{processed_fps} | {realtime_factor} | {inference_p95_ms} | {total_p95_ms} | "
            "{gpu_util_avg_pct}/{gpu_util_p95_pct} | {vram_peak_mb} | {cpu_util_avg_pct}/{cpu_util_p95_pct} | {ram_peak_mb} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Scope Notes",
            "",
            "- FPS is measured over the full local uploaded-video AI path: decode, full-frame resize/letterbox, YOLO/ByteTrack inference, lane/class filter, optional TrafficFlow `LocalTracker`, counting, overlay render, and output-video encode.",
            "- UA-DETRAC local benchmark videos are 960x540. No benchmark-safe 1080p upload input or 3-5 minute/10+ minute source video was present in the frozen split, so this run reports available short/extended-short inputs only.",
            "- `bytetrack` means Ultralytics YOLO `model.track(..., tracker=\"bytetrack.yaml\")` plus lane filter/counting. `trafficflow_production` adds TrafficFlow `LocalTracker` after ByteTrack detections, matching the current upload path candidate measured earlier.",
            "",
            "## Artifacts",
            "",
            "- `benchmark/reports/batch_runtime_summary.csv`",
            "- `benchmark/reports/stage_latency.csv`",
            "- `benchmark/reports/resource_usage.csv`",
            f"- Run manifests: `{run_manifest['output_dir']}/manifests/`",
            f"- Overlay videos: `{run_manifest['output_dir']}/overlays/`",
            "",
            "## Gate",
            "",
            "Phase 07 report is complete. Per plan, stop before Phase 08 live/HLS soak unless the user confirms a stable live source and duration.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    split = json.loads(args.split_file.read_text(encoding="utf-8"))
    output = args.output_dir
    if output.exists() and any(output.iterdir()) and not args.allow_existing_output:
        raise FileExistsError(f"Output directory already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    variants = _parse_variants(args.variants)
    workloads = _selected_workloads(split, args)
    metadata = split["selected_sequence_metadata"]
    summary_rows: list[dict] = []
    stage_rows: list[dict] = []
    resource_rows: list[dict] = []
    input_videos = []

    for workload in workloads:
        meta = metadata[workload.sequence_id]
        video_path, input_info = _resolve_input_video(args, output, workload, meta)
        input_videos.append({"workload_id": workload.workload_id, "sequence_id": workload.sequence_id, **input_info})
        geometry = json.loads((args.geometry_dir / f"{workload.sequence_id}.json").read_text(encoding="utf-8"))
        lanes = geometry.get("lanes") or []
        if not lanes:
            raise ValueError(f"No lanes in geometry for {workload.sequence_id}")
        for variant in variants:
            summary, stage, resources = _run_one(
                args=args,
                output=output,
                workload=workload,
                meta=meta,
                lanes=lanes,
                video_path=video_path,
                variant=variant,
            )
            summary_rows.append(summary)
            stage_rows.extend(stage)
            resource_rows.extend(resources)

    summary_fields = [
        "run_id", "workload_id", "bucket", "sequence_id", "variant", "workload_kind",
        "input_video_path", "input_resolution", "input_fps", "input_frame_count",
        "processed_frames", "warmup_frames", "steady_state_frames", "source_duration_s",
        "processing_seconds", "processed_fps", "realtime_factor", "model", "imgsz",
        "device", "half", "overlay_video", "lane_volume_total", "global_unique_count",
        "resource_samples", "gpu_util_avg_pct", "gpu_util_p95_pct", "vram_peak_mb",
        "cpu_util_avg_pct", "cpu_util_p95_pct", "ram_peak_mb",
    ]
    for stage in STAGES:
        summary_fields.extend([f"{stage}_p50_ms", f"{stage}_p95_ms"])
    stage_fields = [
        "run_id", "workload_id", "bucket", "sequence_id", "variant", "frame_index",
        "frame_num", "phase", "decode_ms", "preprocess_ms", "inference_ms",
        "tracking_ms", "counting_ms", "render_ms", "encode_ms", "total_ms",
        "raw_detections", "filtered_tracks",
    ]
    resource_fields = [
        "run_id", "workload_id", "bucket", "sequence_id", "variant", "sample_index",
        "timestamp", "elapsed_s", "gpu_util_pct", "vram_used_mb", "vram_total_mb",
        "cpu_pct", "ram_used_mb",
    ]

    _write_csv(output / "batch_runtime_summary.csv", summary_rows, summary_fields)
    _write_csv(output / "stage_latency.csv", stage_rows, stage_fields)
    _write_csv(output / "resource_usage.csv", resource_rows, resource_fields)
    reports_dir = args.reports_dir
    if reports_dir:
        _write_csv(reports_dir / "batch_runtime_summary.csv", summary_rows, summary_fields)
        _write_csv(reports_dir / "stage_latency.csv", stage_rows, stage_fields)
        _write_csv(reports_dir / "resource_usage.csv", resource_rows, resource_fields)

    run_manifest = {
        "schema_version": 1,
        "created_at": _now(),
        "run_id": output.name,
        "output_dir": str(output).replace("\\", "/"),
        "split_file": str(args.split_file).replace("\\", "/"),
        "geometry_dir": str(args.geometry_dir).replace("\\", "/"),
        "model": str(args.model).replace("\\", "/"),
        "imgsz": args.imgsz,
        "confidence": args.confidence,
        "device": args.device,
        "half": args.half and args.device != "cpu",
        "variants": variants,
        "warmup_frames": args.warmup_frames,
        "resource_sample_interval_s": args.resource_sample_interval_s,
        "workloads": [workload.__dict__ for workload in workloads],
        "input_videos": input_videos,
        "artifacts": {
            "batch_runtime_summary": "batch_runtime_summary.csv",
            "stage_latency": "stage_latency.csv",
            "resource_usage": "resource_usage.csv",
            "per_result_manifests": "manifests/",
            "overlay_videos": "overlays/",
        },
    }
    _write_json(output / "manifest.json", run_manifest)

    report_targets = [output / "batch_runtime_report.md"]
    if reports_dir:
        report_targets.append(reports_dir / "batch_runtime_report.md")
    if args.docs_report:
        report_targets.append(args.docs_report)
    if args.wiki_report:
        report_targets.append(args.wiki_report)
    for target in report_targets:
        _write_markdown_report(target, summary_rows, run_manifest)

    return {
        "output_dir": str(output).replace("\\", "/"),
        "summary_rows": len(summary_rows),
        "stage_rows": len(stage_rows),
        "resource_rows": len(resource_rows),
        "reports": [str(path).replace("\\", "/") for path in report_targets],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-file", type=Path, default=Path("benchmark/splits/ua_detrac_split_v1.json"))
    parser.add_argument("--bucket", choices=["smoke_test", "development", "held_out_test"], default="development")
    parser.add_argument("--sequences", help="Comma-separated sequence IDs from the selected split metadata.")
    parser.add_argument("--workloads", help="Comma-separated '<kind>:<sequence>' or '<kind>:<bucket>:<sequence>' workload specs.")
    parser.add_argument("--max-sequences", type=int, default=0)
    parser.add_argument("--max-frames-per-sequence", type=int, default=0)
    parser.add_argument("--video-dir", type=Path, default=Path("benchmark/detrac/videos"))
    parser.add_argument("--nominal-fps", type=float, default=NOMINAL_FPS)
    parser.add_argument("--model", type=Path, default=Path("models/yolov8m.pt"))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--device", default="0")
    parser.add_argument("--half", action="store_true")
    parser.add_argument("--variants", default="trafficflow_production")
    parser.add_argument("--geometry-dir", type=Path, default=Path("benchmark/configs/geometry_manual"))
    parser.add_argument("--zone-padding-px", type=float, default=12.0)
    parser.add_argument("--warmup-frames", type=int, default=10)
    parser.add_argument("--resource-sample-interval-s", type=float, default=1.0)
    parser.add_argument("--render-debug", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, default=Path("benchmark/reports"))
    parser.add_argument("--docs-report", type=Path, default=Path("docs/reports/phase-07-upload-runtime.md"))
    parser.add_argument("--wiki-report", type=Path, default=Path("docs/wiki/ai-workflow/phase-07-upload-runtime.md"))
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
