import logging
import os
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

import time
import json
import tempfile
import urllib.request
import cv2
import numpy as np
from celery import Celery
from shared.config import settings
from shared.r2_client import r2_client
from worker.pipeline.ai_client import InferenceClient
from worker.pipeline.local_client import LocalInferenceClient
from worker.pipeline.processor import FrameProcessor, FrameTransform
from worker.pipeline.tracker import LocalTracker
from worker.pipeline.renderer import FrameRenderer
from worker.pipeline.profiler import PipelineProfiler, BenchmarkResult
from worker.pipeline.reporter import write_summary_csv, write_json, write_markdown
from worker.services.counting_service import CountingState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

celery_app = Celery("trafficflow", broker=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    task_default_queue=settings.CELERY_QUEUE_NAME,
)


# ---------------------------------------------------------------------------
# Callback helper
# ---------------------------------------------------------------------------

def _send_callback(url: str, payload: dict):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="PUT",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            logger.info(f"Callback {resp.status}")
    except Exception as e:
        logger.error(f"Callback failed: {e}")


# ---------------------------------------------------------------------------
# Video download
# ---------------------------------------------------------------------------

def _iter_lane_points(lanes: list):
    for lane in lanes:
        lane_id = lane.get("lane_id", "unknown")
        for key in ("valid_zone", "counting_line", "direction"):
            for point in lane.get(key, []) or []:
                if len(point) >= 2:
                    yield lane_id, key, float(point[0]), float(point[1])


def _warn_points_outside_processing_bounds(lanes: list, width: int, height: int, label: str):
    outside = []
    for lane_id, key, x, y in _iter_lane_points(lanes):
        if x < 0 or y < 0 or x > width or y > height:
            outside.append((lane_id, key, round(x, 1), round(y, 1)))
            if len(outside) >= 5:
                break
    if outside:
        logger.warning(
            "%s has lane points outside processing frame %sx%s: %s",
            label, width, height, outside,
        )


def _download_video_to_path(url: str, destination_path: str) -> float:
    import requests
    logger.info(f"Downloading video: {url}")
    start = time.perf_counter()
    with requests.Session() as s:
        resp = s.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        with open(destination_path, "wb") as fp:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fp.write(chunk)
    return (time.perf_counter() - start) * 1000.0



# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_app.task(name="trafficflow.process_video")
def process_video(task_id: str, video_url: str, lane_config: dict, callback_url: str):
    temp_video_path = None
    temp_out_path = None
    ai_client: InferenceClient = None
    out_video = None
    task_start = time.perf_counter()
    profiler = PipelineProfiler()

    try:
        _send_callback(callback_url, {
            "status": "processing", "progress": 5,
            "stage": "downloading", "stage_detail": "Downloading working video",
        })

        # --- Download ---
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_video_path = f.name
        f.close()
        download_ms = _download_video_to_path(video_url, temp_video_path)
        _send_callback(callback_url, {
            "status": "processing", "progress": 10,
            "stage": "opening_video", "stage_detail": "Opening video stream",
        })

        cap = cv2.VideoCapture(temp_video_path)
        if not cap.isOpened():
            raise ValueError("Cannot open downloaded video")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Video: {total_frames} frames, {fps:.1f} FPS, {width}x{height}")

        # --- Parse lane config ---
        processing_roi = lane_config.get("processing_roi") or lane_config.get("annotation_roi")
        has_crop = bool(processing_roi)
        use_detection_crop = has_crop and settings.ROI_MODE == "roi_crop"
        if use_detection_crop:
            cx = int(processing_roi.get("x", 0)); cy = int(processing_roi.get("y", 0))
            cw = int(processing_roi.get("width", 0)); ch = int(processing_roi.get("height", 0))
            crop_rect = (cx, cy, min(width, cx + cw), min(height, cy + ch))
            out_w = crop_rect[2] - crop_rect[0]
            out_h = crop_rect[3] - crop_rect[1]
            if out_w <= 0 or out_h <= 0:
                raise ValueError(f"Invalid processing ROI after clipping: {crop_rect}")
            logger.info("Processing ROI: x=%s y=%s w=%s h=%s", crop_rect[0], crop_rect[1], out_w, out_h)
        else:
            crop_rect = None
            out_w, out_h = width, height

        lanes_source = lane_config.get("lanes", [])
        if not lanes_source:
            raise ValueError("No lanes in lane_config")

        # Polygon mask (source → cropped coords)
        poly_pts = lane_config.get("roi_polygon", [])
        poly_mask = None
        if poly_pts and len(poly_pts) >= 3 and use_detection_crop:
            src = np.array(poly_pts, dtype=np.float32).reshape(-1, 2)
            poly_mask = (src - [crop_rect[0], crop_rect[1]]).astype(np.int32)
            outside_poly = [tuple(map(float, p)) for p in poly_mask if p[0] < 0 or p[1] < 0 or p[0] > out_w or p[1] > out_h]
            if outside_poly:
                logger.warning("roi_polygon has points outside processing ROI after shift: %s", outside_poly[:5])

        # --- Init pipeline stages ---
        processor = FrameProcessor(
            roi_input_size=settings.ROI_INPUT_SIZE,
            roi_mode=settings.ROI_MODE,
            enable_stabilization=settings.AI_ENABLE_STABILIZATION,
        )
        # Use local YOLO when AI_LOCAL=true, otherwise Modal GPU
        if os.environ.get("AI_LOCAL", "").lower() in ("1", "true", "yes") or settings.AI_LOCAL:
            logger.info(f"Using LOCAL YOLO GPU inference | model={settings.AI_MODEL_PATH} imgsz={settings.AI_IMGSZ} half={settings.AI_HALF}")
            ai_client = LocalInferenceClient(max_workers=1)
        else:
            ai_client = InferenceClient(
                base_url=settings.AI_SERVING_URL,
                max_workers=2,
                request_timeout=30,
            )
        tracker = LocalTracker(
            match_threshold=settings.TRACK_MATCH_THRESHOLD,
            track_buffer=settings.TRACK_BUFFER,
        )
        counter = CountingState(lanes)
        renderer = FrameRenderer(lanes, settings_obj=settings)

        # Stabilisation reference frame
        if settings.AI_ENABLE_STABILIZATION:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, ref = cap.read()
            if ok:
                processor.set_reference_frame(ref)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        session_id = ai_client.create_session()
        _send_callback(callback_url, {
            "status": "processing", "progress": 15,
            "stage": "inferencing", "stage_detail": "Running detection and tracking",
        })

        profiler.start_resource_sampler()

        # --- Output video ---
        f_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_out_path = f_out.name; f_out.close()
        fourcc = cv2.VideoWriter_fourcc(*"vp90")
        out_video = cv2.VideoWriter(temp_out_path, fourcc, fps, (out_w, out_h))

        # --- Process frames ---
        frame_idx = 0
        processed = 0
        last_progress = 15
        last_detections = []
        frame_skip = settings.AI_FRAME_SKIP
        pending_future = None
        pending_submitted_at = None
        pending_frame_idx = None
        prev_transform: Optional[FrameTransform] = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            profiler.start_frame(frame_idx)

            # --- Stabilize → crop → mask → letterbox → encode ---
            with profiler.timer("preprocess", frame_idx):
                cropped, ai_frame, transform = processor.process_for_ai(
                    frame, crop_rect, poly_mask,
                )

            # --- Frame-skip logic ---
            if frame_idx % frame_skip == 0:
                # Collect previous result
                if pending_future is not None and prev_transform is not None:
                    try:
                        raw = pending_future.result(timeout=30)
                        if pending_submitted_at is not None and pending_frame_idx is not None:
                            profiler.record_stage(
                                "inference",
                                pending_frame_idx,
                                (time.perf_counter() - pending_submitted_at) * 1000.0,
                            )
                        # Remap bbox from AI space → crop space
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
                        logger.warning(f"Detect failed: {e}")

                prev_transform = transform

                jpeg = processor.encode_jpeg(ai_frame)
                if jpeg is None:
                    frame_idx += 1
                    continue

                # Submit next frame
                pending_submitted_at = time.perf_counter()
                pending_frame_idx = frame_idx
                pending_future = ai_client.submit_frame(jpeg)
                detections = last_detections
            else:
                detections = last_detections

            # --- Draw ---
            with profiler.timer("overlay", frame_idx):
                renderer.draw(cropped, detections)
            if out_video is not None:
                with profiler.timer("encode", frame_idx):
                    out_video.write(cropped)

            profiler.end_frame(frame_idx)

            # --- Progress ---
            progress = 15 + int((frame_idx / max(total_frames, 1)) * 80)
            progress = min(progress, 95)
            if progress - last_progress >= 5:
                _send_callback(callback_url, {
                    "status": "processing", "progress": progress,
                    "stage": "inferencing",
                    "stage_detail": f"frame {frame_idx}/{total_frames}",
                })
                last_progress = progress
                logger.info(
                    f"Progress: {progress}% | frame {frame_idx}/{total_frames} | "
                    f"counted: {counter.get_total_count()}"
                )
            frame_idx += 1

        cap.release()
        if out_video is not None:
            out_video.release()
        if pending_future is not None:
            try:
                raw = pending_future.result(timeout=30)
                if pending_submitted_at is not None and pending_frame_idx is not None:
                    profiler.record_stage(
                        "inference",
                        pending_frame_idx,
                        (time.perf_counter() - pending_submitted_at) * 1000.0,
                    )
                if prev_transform is not None:
                    for det in raw:
                        b = det.get("bbox_xyxy")
                        if b and len(b) == 4:
                            det["bbox_xyxy"] = prev_transform.bbox_ai_to_crop(b)
                enriched = _track_to_dicts(tracker.update(raw))
                counter.process_detections(enriched)
            except Exception:
                pass

        ai_client.delete_session()
        ai_client.shutdown()
        profiler.stop_resource_sampler()
        logger.info(f"Done: {processed} AI frames, {counter.get_total_count()} vehicles")

        _send_callback(callback_url, {
            "status": "processing", "progress": 96,
            "stage": "rendering", "stage_detail": "Finalizing output artifacts",
        })

        # --- Save benchmark report ---
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

        bresult = BenchmarkResult(
            task_id=task_id,
            model_path=settings.AI_MODEL_PATH,
            device="cuda:0" if settings.AI_DEVICE != "cpu" else "cpu",
            imgsz=settings.AI_IMGSZ,
            half=settings.AI_HALF,
            frame_skip=settings.AI_FRAME_SKIP,
            video_resolution=f"{width}x{height}",
            video_fps=fps,
            total_frames=total_frames,
            processed_frames=processed,
            total_ms=total_ms,
            download_ms=download_ms,
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

        from pathlib import Path
        report_dir = Path("benchmark/reports")
        try:
            write_summary_csv([bresult], report_dir / "summary.csv")
            write_json([bresult], report_dir / "summary.json")
            write_markdown([bresult], report_dir / "summary.md")
            logger.info(f"Benchmark report saved to {report_dir}")
        except Exception as e:
            logger.error(f"Benchmark save failed: {e}")

        # --- Upload result ---
        statistics = counter.get_statistics()
        diagnostics = counter.get_diagnostics()
        result_url = None
        if temp_out_path and os.path.exists(temp_out_path):
            try:
                _send_callback(callback_url, {
                    "status": "processing", "progress": 98,
                    "stage": "uploading_result", "stage_detail": "Uploading rendered result video",
                })
                result_url = r2_client.upload_path(temp_out_path, f"results/{task_id}.mp4", "video/mp4")
            except Exception as e:
                logger.error(f"Upload failed: {e}")

        _send_callback(callback_url, {
            "status": "completed",
            "progress": 100,
            "stage": "completed",
            "stage_detail": "Processing completed",
            "result_video_url": result_url,
            "events_url": None,
            "statistics": statistics,
            "lane_volume_total": diagnostics["lane_volume_total"],
            "global_unique_count": diagnostics["global_unique_count"],
            "multi_lane_track_count": diagnostics["multi_lane_track_count"],
            "multi_lane_tracks": diagnostics["multi_lane_tracks"],
        })
        logger.info(f"Task {task_id} completed")
        return {"status": "completed", "task_id": task_id}

    except Exception as e:
        logger.error(f"Task {task_id} FAILED: {e}", exc_info=True)
        if ai_client:
            ai_client.delete_session()
            ai_client.shutdown()
            _send_callback(callback_url, {
                "status": "failed", "progress": 0, "error_message": str(e),
                "stage": "failed", "stage_detail": str(e),
            })
        return {"status": "failed", "task_id": task_id, "error": str(e)}

    finally:
        for p in (temp_video_path, temp_out_path):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


def _track_to_dicts(track_outputs) -> list:
    """Convert LocalTracker's TrackOutput list to flat dicts for CountingState."""
    return [
        {
            "track_id": t.track_id,
            "class_name": t.class_name,
            "bbox_xyxy": t.bbox_xyxy,
            "kalman_velocity": t.kalman_velocity,
            "lost_frames": t.lost_frames,
        }
        for t in track_outputs
    ]
