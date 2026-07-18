"""Benchmark runner — direct inference (no Celery/R2), multi-preset matrix.

Usage:
    python -m benchmark.run_benchmark --preset optimized-a-yolov8n-fp16-640
    python -m benchmark.run_benchmark --all
    python -m benchmark.run_benchmark --list
"""

import argparse
import json
import sys
import time
import tempfile
import os
from pathlib import Path

# Ensure src is on path
_src = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_src))

import cv2
import numpy as np
from shared.config import settings
from worker.pipeline.processor import FrameProcessor, FrameTransform
from worker.pipeline.local_client import LocalInferenceClient
from worker.pipeline.tracker import LocalTracker
from worker.pipeline.renderer import FrameRenderer
from worker.pipeline.profiler import PipelineProfiler, BenchmarkResult
from worker.pipeline.reporter import write_summary_csv, write_json, write_markdown
from worker.pipeline.ground_truth import load_ground_truth, compare_counts
from worker.services.counting_service import CountingState

PRESETS_PATH = Path(__file__).resolve().parent / "presets.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
GROUND_TRUTH_PATH = Path(__file__).resolve().parent / "ground_truth" / "counts_summary.csv"


def load_presets():
    with open(PRESETS_PATH) as f:
        return json.load(f)


def list_presets():
    data = load_presets()
    for p in data["presets"]:
        print(f"  {p['name']} — {p['description']}")


def _track_to_dicts(track_outputs) -> list:
    return [
        {
            "track_id": t.track_id, "class_name": t.class_name,
            "bbox_xyxy": t.bbox_xyxy,
            "kalman_velocity": t.kalman_velocity,
            "lost_frames": t.lost_frames,
        }
        for t in track_outputs
    ]


def run_single(
    preset: dict,
    video_path: str,
    video_id: str,
    lane_config: dict,
    max_frames: int = 0,
    no_overlay: bool = False,
    export_tracks: bool = False,
) -> BenchmarkResult:
    task_start = time.perf_counter()
    profiler = PipelineProfiler()

    # Override settings for this preset
    settings.AI_MODEL_PATH = preset["model_path"]
    settings.AI_IMGSZ = preset["imgsz"]
    settings.AI_HALF = preset["half"]
    settings.AI_CLASS_IDS = ",".join(str(x) for x in preset["class_ids"])
    settings.AI_FRAME_SKIP = preset["frame_skip"]
    settings.AI_CONFIDENCE = preset["confidence"]

    # --- Open video ---
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open: {video_path}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if max_frames > 0:
        total_frames = min(total_frames, max_frames)

    # --- Parse config ---
    roi = lane_config.get("processing_roi") or lane_config.get("annotation_roi")
    has_crop = bool(roi)
    if has_crop:
        cx = int(roi.get("x", 0)); cy = int(roi.get("y", 0))
        cw = int(roi.get("width", 0)); ch = int(roi.get("height", 0))
        crop_rect = (cx, cy, min(width, cx + cw), min(height, cy + ch))
        out_w = crop_rect[2] - crop_rect[0]
        out_h = crop_rect[3] - crop_rect[1]
    else:
        crop_rect = None
        out_w, out_h = width, height

    lanes = lane_config.get("lanes", [])
    if not lanes:
        raise ValueError("No lanes")

    poly_pts = lane_config.get("roi_polygon", [])
    poly_mask = None
    if poly_pts and len(poly_pts) >= 3 and has_crop:
        src = np.array(poly_pts, dtype=np.float32).reshape(-1, 2)
        poly_mask = (src - [crop_rect[0], crop_rect[1]]).astype(np.int32)

    # --- Init pipeline ---
    processor = FrameProcessor(
        roi_input_size=settings.ROI_INPUT_SIZE,
        roi_mode=settings.ROI_MODE,
        enable_stabilization=settings.AI_ENABLE_STABILIZATION,
    )
    ai_client = LocalInferenceClient(max_workers=1)
    tracker = LocalTracker(
        match_threshold=settings.TRACK_MATCH_THRESHOLD,
        track_buffer=settings.TRACK_BUFFER,
    )

    lanes_processing = lanes
    if has_crop:
        transform_init = FrameTransform(
            full_w=width, full_h=height, crop_w=out_w, crop_h=out_h,
            ai_w=settings.ROI_INPUT_SIZE, ai_h=settings.ROI_INPUT_SIZE,
            offset_x=crop_rect[0], offset_y=crop_rect[1],
        )
        lanes_processing = transform_init.shift_lanes_to_crop(lanes)
    counter = CountingState(lanes_processing)
    renderer = FrameRenderer(lanes_processing)

    if settings.AI_ENABLE_STABILIZATION:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, ref = cap.read()
        if ok:
            processor.set_reference_frame(ref)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    profiler.start_resource_sampler()
    session_id = ai_client.create_session()

    # --- Output video (optional) ---
    out_video = None
    out_path = None
    if not no_overlay:
        out_path = REPORTS_DIR / f"{video_id}_{preset['name']}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        for codec in ("avc1", "mp4v", "XVID", "MJPG"):
            fourcc = cv2.VideoWriter_fourcc(*codec)
            out_video = cv2.VideoWriter(str(out_path), fourcc, fps, (out_w, out_h))
            if out_video.isOpened():
                print(f"  Writing overlay video: {out_path} (codec={codec})")
                break
            out_video.release()
            out_video = None
        if out_video is None:
            print(f"  [warn] Could not open VideoWriter for {out_path}; overlay video disabled")

    tracks_file = None
    tracks_path = None
    if export_tracks:
        tracks_path = REPORTS_DIR / f"{video_id}_{preset['name']}_tracks.jsonl"
        tracks_path.parent.mkdir(parents=True, exist_ok=True)
        tracks_file = tracks_path.open("w", encoding="utf-8")
        print(f"  Writing track JSONL: {tracks_path}")

    # --- Process frames ---
    frame_idx = 0
    processed = 0
    last_detections = []
    frame_skip = preset["frame_skip"]
    pending_future = None
    prev_transform = None

    while frame_idx < total_frames:
        ret, frame = cap.read()
        if not ret:
            break
        profiler.start_frame(frame_idx)

        with profiler.timer("preprocess", frame_idx):
            cropped, ai_frame, transform = processor.process_for_ai(
                frame, crop_rect, poly_mask,
            )

        if frame_idx % frame_skip == 0:
            if pending_future is not None and prev_transform is not None:
                try:
                    with profiler.timer("inference", frame_idx):
                        raw = pending_future.result(timeout=90)
                    for det in raw:
                        b = det.get("bbox_xyxy")
                        if b and len(b) == 4:
                            det["bbox_xyxy"] = prev_transform.bbox_ai_to_crop(b)
                    with profiler.timer("tracking", frame_idx):
                        enriched = _track_to_dicts(tracker.update(raw))
                    with profiler.timer("counting", frame_idx):
                        counter.process_detections(enriched)
                    processed += 1
                    last_detections = enriched
                except Exception as e:
                    print(f"  [warn] frame {frame_idx}: {e}")

            prev_transform = transform
            jpeg = processor.encode_jpeg(ai_frame)
            if jpeg is not None:
                pending_future = ai_client.submit_frame(jpeg)
            detections = last_detections
        else:
            detections = last_detections

        if tracks_file is not None:
            tracks_file.write(json.dumps({
                "frame_index": frame_idx,
                "frame_num": frame_idx + 1,
                "video_id": video_id,
                "coordinate_space": "processing_roi" if has_crop else "source_frame",
                "crop_rect": list(crop_rect) if crop_rect else None,
                "detections": detections,
            }, ensure_ascii=False) + "\n")

        with profiler.timer("overlay", frame_idx):
            renderer.draw(cropped, detections)
        if out_video is not None:
            with profiler.timer("encode", frame_idx):
                out_video.write(cropped)

        profiler.end_frame(frame_idx)
        frame_idx += 1

        if frame_idx % 50 == 0:
            print(f"  [{preset['name']}] frame {frame_idx}/{total_frames} | counted: {counter.get_total_count()}")

    cap.release()
    if out_video is not None:
        out_video.release()
    if tracks_file is not None:
        tracks_file.close()
    if pending_future is not None and prev_transform is not None:
        try:
            raw = pending_future.result(timeout=90)
            for det in raw:
                b = det.get("bbox_xyxy")
                if b and len(b) == 4:
                    det["bbox_xyxy"] = prev_transform.bbox_ai_to_crop(b)
            enriched = _track_to_dicts(tracker.update(raw))
            counter.process_detections(enriched)
        except Exception:
            pass

    ai_client.shutdown()
    profiler.stop_resource_sampler()

    total_ms = (time.perf_counter() - task_start) * 1000.0
    stage_stats = profiler.compute_stage_stats()
    diagnostics = counter.get_diagnostics()
    counts_raw = {}
    for s in counter.get_statistics():
        lid = s["lane_id"]
        vtype = s["vehicle_type"]
        if lid not in counts_raw:
            counts_raw[lid] = {}
        counts_raw[lid][vtype] = s["count"]

    return BenchmarkResult(
        task_id=preset["name"],
        model_path=preset["model_path"],
        device="cuda:0" if settings.AI_DEVICE != "cpu" else "cpu",
        imgsz=preset["imgsz"],
        half=preset["half"],
        frame_skip=preset["frame_skip"],
        video_resolution=f"{width}x{height}",
        video_fps=fps,
        total_frames=total_frames,
        processed_frames=processed,
        video_id=video_id,
        total_ms=total_ms,
        download_ms=0.0,
        upload_ms=0.0,
        counts=counts_raw,
        lane_volume_total=diagnostics["lane_volume_total"],
        global_unique_count=diagnostics["global_unique_count"],
        multi_lane_track_count=diagnostics["multi_lane_track_count"],
        multi_lane_tracks=diagnostics["multi_lane_tracks"],
        frame_timings=profiler.frame_timings,
        stage_stats=stage_stats,
        resource_samples=profiler.resource_samples,
    )


def main():
    parser = argparse.ArgumentParser(description="TrafficFlow Benchmark Runner")
    parser.add_argument("--preset", help="Run a specific preset by name")
    parser.add_argument("--all", action="store_true", help="Run all presets in benchmark_runs")
    parser.add_argument("--list", action="store_true", help="List available presets")
    parser.add_argument("--video", default="scratch/test_gpu.mp4", help="Video path")
    parser.add_argument("--config", help="Lane config JSON path")
    parser.add_argument("--max-frames", type=int, default=100, help="Max frames to process (0=all)")
    parser.add_argument("--no-overlay", action="store_true", help="Skip output video writing")
    parser.add_argument("--export-tracks", action="store_true", help="Write per-frame predicted tracks JSONL")
    args = parser.parse_args()

    if args.list:
        list_presets()
        return

    data = load_presets()
    preset_map = {p["name"]: p for p in data["presets"]}

    # Build run list
    if args.all:
        preset_names = data.get("benchmark_runs", [])
        if not preset_names:
            preset_names = list(preset_map.keys())
    elif args.preset:
        preset_names = [args.preset]
    else:
        print("Specify --preset <name> or --all")
        sys.exit(1)

    # Load lane config
    if args.config:
        with open(args.config) as f:
            lane_config = json.load(f)
    else:
        lane_config = {
            "version": 1, "camera_id": "benchmark",
            "resolution": {"width": 320, "height": 240},
            "roi_polygon": [[0, 0], [320, 0], [320, 240], [0, 240]],
            "processing_roi": {"type": "rectangle", "x": 0, "y": 0, "width": 320, "height": 240, "purpose": "inference_processing"},
            "method": "counting_gate",
            "settings": {"movement_threshold_px": 5, "cooldown_frames": 12, "cooldown_distance_px": 32, "zone_policy": "flexible"},
            "lanes": [{
                "lane_id": "l1", "valid_zone": [[0, 0], [320, 0], [320, 240], [0, 240]],
                "counting_line": [[10, 120], [310, 120]],
                "direction": [[160, 0], [160, 240]],
                "class_allowed": ["car"]
            }],
        }

    video_path = args.video
    if not os.path.exists(video_path):
        print(f"Video not found: {video_path}")
        sys.exit(1)

    video_stem = Path(video_path).stem
    video_id = video_stem.split(".")[0].split("_")[0]
    if video_stem.startswith("MVI_"):
        video_id = video_stem  # e.g. MVI_20011

    results = []
    for name in preset_names:
        preset = preset_map.get(name)
        if not preset:
            print(f"Unknown preset: {name}")
            continue

        print(f"\n{'='*60}")
        print(f"Running: {preset['name']}")
        print(f"  model={preset['model_path']} imgsz={preset['imgsz']} half={preset['half']} "
              f"skip={preset['frame_skip']} frames={args.max_frames}")
        print(f"{'='*60}")

        try:
            result = run_single(
                preset, video_path, video_id, lane_config,
                max_frames=args.max_frames,
                no_overlay=args.no_overlay,
                export_tracks=args.export_tracks,
            )
            results.append(result)
            d = result.to_dict()
            print(f"  Done: {d['total_sec']}s | {d['effective_fps']} FPS | "
                  f"real-time {d['realtime_factor']}x | lane_volume={d['lane_volume_total']} | "
                  f"unique={d['global_unique_count']} | multi_lane={d['multi_lane_track_count']}")

            stages = d["stages"]
            if "inference" in stages:
                print(f"  Inference: avg={stages['inference']['avg_ms']}ms p95={stages['inference']['p95_ms']}ms")
            if "preprocess" in stages:
                print(f"  Preprocess: avg={stages['preprocess']['avg_ms']}ms")
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()

    if results:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        write_summary_csv(results, REPORTS_DIR / "summary.csv")
        write_json(results, REPORTS_DIR / "summary.json")

        gt_rows = load_ground_truth(GROUND_TRUTH_PATH)
        comparisons = {}
        if gt_rows:
            for r in results:
                vid = r.video_id

                predicted_lanes = {}
                for lane_id, classes in r.counts.items():
                    predicted_lanes[lane_id] = dict(classes) if isinstance(classes, dict) else classes

                comp = compare_counts(vid, gt_rows, predicted_lanes, title=r.task_id)
                comparisons[r.task_id] = comp

        write_markdown(results, REPORTS_DIR / "benchmark_report.md", comparisons=comparisons)
        print(f"\nReports saved to {REPORTS_DIR}/")
        print(f"  summary.csv  — per-run summary")
        print(f"  summary.json — full details")
        print(f"  benchmark_report.md — human-readable report")
    else:
        print("No results generated.")


if __name__ == "__main__":
    main()
