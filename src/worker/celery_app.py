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
from lib.config import settings
from lib.r2_client import r2_client
from worker.pipeline.ai_client import InferenceClient
from worker.pipeline.processor import FrameProcessor
from worker.pipeline.tracker import LocalTracker
from worker.pipeline.renderer import FrameRenderer
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
    task_default_queue="trafficflow_queue",
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

def _download_video(url: str) -> bytes:
    import requests
    logger.info(f"Downloading video: {url}")
    with requests.Session() as s:
        resp = s.get(url, timeout=120)
        resp.raise_for_status()
        return resp.content


def _bbox_scale(detections: list, orig_w, orig_h, ai_w, ai_h):
    """Scale bbox from AI resize space back to cropped frame space."""
    sx = orig_w / ai_w if ai_w != orig_w else 1.0
    sy = orig_h / ai_h if ai_h != orig_h else 1.0
    if sx == 1.0 and sy == 1.0:
        return detections
    for det in detections:
        b = det.get("bbox_xyxy")
        if b and len(b) == 4:
            det["bbox_xyxy"] = [b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy]
    return detections


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_app.task(name="trafficflow.process_video")
def process_video(task_id: str, video_url: str, lane_config: dict, callback_url: str):
    temp_video_path = None
    temp_out_path = None
    ai_client: InferenceClient = None
    out_video = None

    try:
        _send_callback(callback_url, {"status": "processing", "progress": 5})

        # --- Download ---
        video_bytes = _download_video(video_url)
        _send_callback(callback_url, {"status": "processing", "progress": 10})

        # --- Temp file for OpenCV ---
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_video_path = f.name
        f.write(video_bytes); f.close()
        del video_bytes

        cap = cv2.VideoCapture(temp_video_path)
        if not cap.isOpened():
            raise ValueError("Cannot open downloaded video")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Video: {total_frames} frames, {fps:.1f} FPS, {width}x{height}")

        # --- Parse lane config ---
        roi = lane_config.get("annotation_roi")
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
            raise ValueError("No lanes in lane_config")

        # Polygon mask (source → cropped coords)
        poly_pts = lane_config.get("roi_polygon", [])
        poly_mask = None
        if poly_pts and len(poly_pts) >= 3 and has_crop:
            src = np.array(poly_pts, dtype=np.float32).reshape(-1, 2)
            poly_mask = (src - [crop_rect[0], crop_rect[1]]).astype(np.int32)

        # --- Init pipeline stages ---
        processor = FrameProcessor(
            ai_resize_dim=settings.AI_RESIZE_DIM,
            enable_stabilization=settings.AI_ENABLE_STABILIZATION,
        )
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
        _send_callback(callback_url, {"status": "processing", "progress": 15})

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
        prev = {"orig_w": 0, "orig_h": 0, "ai_w": 0, "ai_h": 0}

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # --- Stabilize → crop → mask → resize → encode ---
            cropped, ai_frame, orig_w, orig_h, ai_w, ai_h = processor.process_for_ai(
                frame, crop_rect, poly_mask,
            )

            # --- Frame-skip logic ---
            if frame_idx % frame_skip == 0:
                # Collect previous result
                if pending_future is not None:
                    try:
                        raw = pending_future.result(timeout=30)
                        dets = _bbox_scale(raw, prev["orig_w"], prev["orig_h"],
                                           prev["ai_w"], prev["ai_h"])
                        # Enrich with Kalman tracking (local)
                        enriched = _track_to_dicts(tracker.update(dets))
                        counter.process_detections(enriched)
                        processed += 1
                        last_detections = enriched
                    except Exception as e:
                        logger.warning(f"Detect failed: {e}")

                prev["orig_w"], prev["orig_h"] = orig_w, orig_h
                prev["ai_w"], prev["ai_h"] = ai_w, ai_h

                jpeg = processor.encode_jpeg(ai_frame)
                if jpeg is None:
                    frame_idx += 1
                    continue

                # Submit next frame
                pending_future = ai_client.submit_frame(jpeg)
                detections = last_detections
            else:
                detections = last_detections

            # --- Draw ---
            renderer.draw(cropped, detections)
            if out_video is not None:
                out_video.write(cropped)

            # --- Progress ---
            progress = 15 + int((frame_idx / max(total_frames, 1)) * 80)
            progress = min(progress, 95)
            if progress - last_progress >= 5:
                _send_callback(callback_url, {
                    "status": "processing", "progress": progress,
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
                dets = _bbox_scale(raw, prev["orig_w"], prev["orig_h"],
                                   prev["ai_w"], prev["ai_h"])
                enriched = _track_to_dicts(tracker.update(dets))
                counter.process_detections(enriched)
            except Exception:
                pass

        ai_client.delete_session()
        ai_client.shutdown()
        logger.info(f"Done: {processed} AI frames, {counter.get_total_count()} vehicles")

        # --- Upload result ---
        statistics = counter.get_statistics()
        result_url = None
        if temp_out_path and os.path.exists(temp_out_path):
            with open(temp_out_path, "rb") as fp:
                video_data = fp.read()
            try:
                result_url = r2_client.upload_file(video_data, f"results/{task_id}.mp4", "video/mp4")
            except Exception as e:
                logger.error(f"Upload failed: {e}")

        _send_callback(callback_url, {
            "status": "completed",
            "progress": 100,
            "result_video_url": result_url,
            "events_url": None,
            "statistics": statistics,
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
