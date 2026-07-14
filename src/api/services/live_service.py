
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import cv2
import numpy as np

from shared.config import settings
from worker.pipeline.ai_client import InferenceClient
from worker.pipeline.local_client import LocalInferenceClient
from worker.pipeline.processor import FrameProcessor, FrameTransform
from worker.pipeline.renderer import FrameRenderer
from worker.pipeline.tracker import LocalTracker
from worker.services.counting_service import CountingState

logger = logging.getLogger(__name__)


@dataclass
class LiveSessionState:
    session_id: str
    source_url: str
    status: str = "starting"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    frames_read: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    fps: float = 0.0
    last_error: Optional[str] = None
    counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    lane_volume_total: int = 0
    global_unique_count: int = 0
    multi_lane_track_count: int = 0
    multi_lane_tracks: list = field(default_factory=list)
    latest_tracks: list = field(default_factory=list)
    latest_debug: dict = field(default_factory=dict)
    model_name: str = ""
    roi_mode: str = ""
    ai_imgsz: int = 0
    latest_frame_jpeg: Optional[bytes] = field(default=None, repr=False)
    latest_frame_seq: int = 0
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    thread: Optional[threading.Thread] = field(default=None, repr=False)

    def snapshot(self) -> dict:
        return {
            "session_id": self.session_id,
            "source_url": self.source_url,
            "status": self.status,
            "uptime_s": round(time.time() - self.created_at, 1),
            "frames_read": self.frames_read,
            "frames_processed": self.frames_processed,
            "frames_dropped": self.frames_dropped,
            "fps": round(self.fps, 2),
            "last_error": self.last_error,
            "counts": self.counts,
            "lane_volume_total": self.lane_volume_total,
            "global_unique_count": self.global_unique_count,
            "multi_lane_track_count": self.multi_lane_track_count,
            "multi_lane_tracks": self.multi_lane_tracks,
            "latest_tracks": self.latest_tracks[-20:],
            "latest_debug": self.latest_debug,
            "latest_frame_seq": self.latest_frame_seq,
            "model_name": self.model_name,
            "roi_mode": self.roi_mode,
            "ai_imgsz": self.ai_imgsz,
        }


class LiveSessionManager:
    def __init__(self):
        self._sessions: Dict[str, LiveSessionState] = {}
        self._lock = threading.Lock()

    def create(self, source_url: str, lane_config: Optional[dict], frame_skip: int = 2) -> LiveSessionState:
        session = LiveSessionState(session_id=str(uuid.uuid4()), source_url=source_url)
        with self._lock:
            self._sessions[session.session_id] = session
        session.thread = threading.Thread(
            target=self._run_session,
            args=(session, lane_config or {}, max(1, frame_skip)),
            daemon=True,
        )
        session.thread.start()
        return session

    def get(self, session_id: str) -> Optional[LiveSessionState]:
        with self._lock:
            return self._sessions.get(session_id)

    def list(self) -> list[LiveSessionState]:
        with self._lock:
            return list(self._sessions.values())

    def stop(self, session_id: str) -> bool:
        session = self.get(session_id)
        if not session:
            return False
        session.stop_event.set()
        session.status = "stopping"
        session.updated_at = time.time()
        return True

    def remove(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if not session:
            return False
        session.stop_event.set()
        session.status = "stopping"
        session.updated_at = time.time()
        return True

    def _run_session(self, session: LiveSessionState, lane_config: dict, frame_skip: int) -> None:
        cap = None
        ai_client = None
        try:
            cap = cv2.VideoCapture(session.source_url)
            if not cap.isOpened():
                raise RuntimeError("Could not open live source. Use a direct HLS/MJPEG/video URL; YouTube watch URLs need HLS resolving.")

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            logger.info("Live source opened: session=%s source=%s %sx%s @ %.2f", session.session_id, session.source_url, width, height, source_fps)

            processing_roi = lane_config.get("processing_roi") or lane_config.get("annotation_roi")
            has_crop = bool(processing_roi)
            use_detection_crop = has_crop and settings.ROI_MODE == "roi_crop"
            if use_detection_crop:
                cx = int(processing_roi.get("x", 0)); cy = int(processing_roi.get("y", 0))
                cw = int(processing_roi.get("width", width)); ch = int(processing_roi.get("height", height))
                crop_rect = (cx, cy, min(width, cx + cw), min(height, cy + ch))
                out_w = crop_rect[2] - crop_rect[0]
                out_h = crop_rect[3] - crop_rect[1]
            else:
                crop_rect = None
                out_w, out_h = width, height

            lanes_source = lane_config.get("lanes", [])
            lanes_processing = lanes_source
            if use_detection_crop and lanes_source:
                lanes_processing = FrameTransform(
                    full_w=width, full_h=height,
                    crop_w=out_w, crop_h=out_h,
                    ai_w=settings.ROI_INPUT_SIZE, ai_h=settings.ROI_INPUT_SIZE,
                    offset_x=crop_rect[0], offset_y=crop_rect[1],
                ).shift_lanes_to_crop(lanes_source)

            poly_mask = None
            poly_pts = lane_config.get("roi_polygon", [])
            if poly_pts and len(poly_pts) >= 3 and use_detection_crop:
                src = np.array(poly_pts, dtype=np.float32).reshape(-1, 2)
                poly_mask = (src - [crop_rect[0], crop_rect[1]]).astype(np.int32)

            processor = FrameProcessor(
                roi_input_size=settings.ROI_INPUT_SIZE,
                roi_mode=settings.ROI_MODE,
                enable_stabilization=False,
            )
            renderer = FrameRenderer(lanes_processing or [])
            tracker = LocalTracker(match_threshold=settings.TRACK_MATCH_THRESHOLD, track_buffer=settings.TRACK_BUFFER)
            counter = CountingState(lanes_processing) if lanes_processing else None
            if settings.AI_LOCAL or settings.AI_SERVING_URL == "local":
                ai_client = LocalInferenceClient(max_workers=1)
            else:
                ai_client = InferenceClient(base_url=settings.AI_SERVING_URL, max_workers=1, request_timeout=30)
            ai_client.create_session()
            logger.info(
                "Live inference ready: session=%s client=%s frame_skip=%s crop=%s lanes=%s",
                session.session_id,
                ai_client.__class__.__name__,
                frame_skip,
                bool(crop_rect),
                len(lanes_processing or []),
            )

            pending_future = None
            prev_transform = None
            last_tick = time.time()
            last_processed = 0
            frame_idx = 0
            session.model_name = settings.AI_MODEL_PATH
            session.roi_mode = settings.ROI_MODE
            session.ai_imgsz = settings.AI_IMGSZ
            session.status = "running"

            while not session.stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    session.last_error = "Stream ended or frame read failed"
                    break
                session.frames_read += 1

                cropped, ai_frame, transform = processor.process_for_ai(frame, crop_rect, poly_mask)
                if frame_idx % frame_skip == 0:
                    if pending_future is not None and prev_transform is not None and pending_future.done():
                        raw = pending_future.result(timeout=30)
                        for det in raw:
                            bbox = det.get("bbox_xyxy")
                            if bbox and len(bbox) == 4:
                                det["bbox_xyxy"] = prev_transform.bbox_ai_to_crop(bbox)
                        enriched = [
                            {
                                "track_id": t.track_id,
                                "bbox_xyxy": t.bbox_xyxy,
                                "class_name": t.class_name,
                                "confidence": t.confidence,
                                "kalman_velocity": t.kalman_velocity,
                                "is_lost": t.is_lost,
                                "lost_frames": t.lost_frames,
                            }
                            for t in tracker.update(raw)
                        ]
                        if counter:
                            counter.process_detections(enriched)
                            session.counts = _counts_map(counter)
                            diagnostics = counter.get_diagnostics()
                            session.lane_volume_total = diagnostics["lane_volume_total"]
                            session.global_unique_count = diagnostics["global_unique_count"]
                            session.multi_lane_track_count = diagnostics["multi_lane_track_count"]
                            session.multi_lane_tracks = diagnostics["multi_lane_tracks"]
                            session.latest_debug = counter.get_debug_snapshot()
                        session.latest_tracks = enriched
                        annotated = renderer.draw(cropped.copy(), enriched, session.latest_debug)
                        ok, frame_jpeg = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                        if ok:
                            session.latest_frame_jpeg = frame_jpeg.tobytes()
                            session.latest_frame_seq += 1
                        session.frames_processed += 1
                        now = time.time()
                        if now - last_tick >= 2.0:
                            session.fps = (session.frames_processed - last_processed) / (now - last_tick)
                            last_processed = session.frames_processed
                            last_tick = now
                            logger.info(
                                "Live session tick: session=%s status=%s read=%s processed=%s dropped=%s fps=%.2f total=%s",
                                session.session_id,
                                session.status,
                                session.frames_read,
                                session.frames_processed,
                                session.frames_dropped,
                                session.fps,
                                session.lane_volume_total,
                            )
                        session.updated_at = now
                        pending_future = None

                    if pending_future is None:
                        prev_transform = transform
                        jpeg = processor.encode_jpeg(ai_frame)
                        if jpeg:
                            pending_future = ai_client.submit_frame(jpeg)
                    else:
                        session.frames_dropped += 1
                        session.updated_at = time.time()
                frame_idx += 1

            session.status = "stopped" if session.stop_event.is_set() else "ended"
            logger.info(
                "Live session finished: session=%s status=%s read=%s processed=%s dropped=%s total=%s",
                session.session_id,
                session.status,
                session.frames_read,
                session.frames_processed,
                session.frames_dropped,
                session.lane_volume_total,
            )
        except Exception as exc:
            logger.exception("Live session failed: %s", exc)
            session.status = "failed"
            session.last_error = str(exc)
        finally:
            session.updated_at = time.time()
            if cap is not None:
                cap.release()
            if ai_client is not None:
                try:
                    ai_client.shutdown()
                except Exception:
                    pass


def _counts_map(counter: CountingState) -> Dict[str, Dict[str, int]]:
    counts: Dict[str, Dict[str, int]] = {}
    for stat in counter.get_statistics():
        lane_id = stat["lane_id"]
        counts.setdefault(lane_id, {})[stat["vehicle_type"]] = stat["count"]
    return counts


live_manager = LiveSessionManager()
