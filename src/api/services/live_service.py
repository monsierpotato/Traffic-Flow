
from __future__ import annotations

import json
import logging
import os
import subprocess
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
from worker.pipeline.detection_filter import filter_detections_for_tracking
from worker.pipeline.tracker import LocalTracker
from worker.services.counting_service import CountingState

logger = logging.getLogger(__name__)


def _normalize_even_crop_rect(
    crop_rect: tuple[int, int, int, int], source_width: int, source_height: int,
) -> Optional[tuple[int, int, int, int]]:
    """Clip a source crop and make its output dimensions FFmpeg-safe."""
    x1, y1, x2, y2 = (int(v) for v in crop_rect)
    x1 = max(0, min(source_width, x1))
    y1 = max(0, min(source_height, y1))
    x2 = max(x1, min(source_width, x2))
    y2 = max(y1, min(source_height, y2))
    crop_w = ((x2 - x1) // 2) * 2
    crop_h = ((y2 - y1) // 2) * 2
    if crop_w < 2 or crop_h < 2:
        return None
    return x1, y1, x1 + crop_w, y1 + crop_h


@dataclass
class LiveFrameItem:
    frame: np.ndarray
    captured_at: float
    seq: int
    interarrival_ms: float = 0.0


class FramePacer:
    def __init__(self, fps: float) -> None:
        self.period = 1.0 / max(float(fps), 1.0)
        self.next_emit = time.monotonic()

    def wait(self) -> None:
        now = time.monotonic()
        if now - self.next_emit > 0.5:
            self.next_emit = now
        delay = self.next_emit - now
        if delay > 0:
            time.sleep(delay)
        self.next_emit += self.period


class OpenCvFrameReader:
    def __init__(self, source_url: str):
        self.source_url = source_url
        self.cap = None
        self.width = 0
        self.height = 0
        self.fps = 25.0
        self.frames_read = 0

    def open(self) -> None:
        self.cap = cv2.VideoCapture(self.source_url)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open live source with OpenCV")
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0

    def read(self, timeout: float = 1.0):
        if self.cap is None:
            return False, None
        ok, frame = self.cap.read()
        if ok and frame is not None:
            self.frames_read += 1
        return ok, frame

    def read_item(self, timeout: float = 1.0):
        ok, frame = self.read(timeout=timeout)
        if not ok or frame is None:
            return False, None
        return True, LiveFrameItem(frame=frame, captured_at=time.monotonic(), seq=self.frames_read)

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class FfmpegLatestFrameReader:
    def __init__(self, source_url: str, crop_rect: Optional[tuple[int, int, int, int]] = None):
        self.source_url = source_url
        self.crop_rect = crop_rect
        self.width = 0
        self.height = 0
        self.source_width = 0
        self.source_height = 0
        self.fps = 25.0
        self.frames_read = 0
        self.cropped_in_reader = False
        self._proc = None
        self._thread = None
        self._stop = threading.Event()
        self._cond = threading.Condition()
        self._latest_frame = None
        self._latest_timestamp = 0.0
        self._latest_interarrival_ms = 0.0
        self._latest_seq = 0
        self._last_delivered_seq = 0
        self._last_error = None

    def open(self) -> None:
        self.source_width, self.source_height, self.fps = _probe_live_source(self.source_url)
        self.width, self.height = self.source_width, self.source_height
        vf = []
        if self.crop_rect:
            normalized_crop = _normalize_even_crop_rect(self.crop_rect, self.source_width, self.source_height)
            if normalized_crop:
                crop_x, crop_y, x2, y2 = normalized_crop
                crop_w, crop_h = x2 - crop_x, y2 - crop_y
                # `exact=1` prevents FFmpeg silently changing a crop on YUV
                # sources; the raw-frame byte count must stay deterministic.
                vf.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}:exact=1")
                self.width, self.height = crop_w, crop_h
                self.crop_rect = normalized_crop
                self.cropped_in_reader = True
        if settings.LIVE_FFMPEG_OUTPUT_FPS and settings.LIVE_FFMPEG_OUTPUT_FPS > 0:
            vf.append(f"fps={settings.LIVE_FFMPEG_OUTPUT_FPS}")
        pacing_fps = float(settings.LIVE_FFMPEG_OUTPUT_FPS or self.fps or 30.0)
        frame_size = self.width * self.height * 3
        logger.info(
            "Live FFmpeg ingest: source_resolution=%sx%s crop_rect=%s "
            "ffmpeg_output=%sx%s expected_frame_bytes=%s realtime_pacing=%s pacing_fps=%.2f",
            self.source_width, self.source_height, self.crop_rect if self.cropped_in_reader else None,
            self.width, self.height, frame_size, settings.LIVE_FFMPEG_REALTIME_PACING, pacing_fps,
        )
        cmd = [
            settings.LIVE_FFMPEG_BIN,
            "-hide_banner",
            "-loglevel", settings.LIVE_FFMPEG_LOGLEVEL,
            "-nostdin",
            "-fflags", "nobuffer+discardcorrupt",
            "-flags", "low_delay",
            "-rw_timeout", str(settings.LIVE_FFMPEG_RW_TIMEOUT_US),
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "2",
            "-live_start_index", "-1",
        ]
        if settings.LIVE_FFMPEG_REALTIME_PACING:
            cmd.append("-re")
        cmd.extend([
            "-i", self.source_url,
            "-an",
            "-sn",
            "-dn",
        ])
        if vf:
            cmd.extend(["-vf", ",".join(vf)])
        cmd.extend([
            "-pix_fmt", "bgr24",
            "-f", "rawvideo",
            "pipe:1",
        ])
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self._thread = threading.Thread(target=self._reader_loop, args=(frame_size, pacing_fps), daemon=True)
        self._thread.start()
        deadline = time.time() + 10.0
        while time.time() < deadline:
            ok, item = self.read_item(timeout=0.5)
            if ok and item is not None:
                return
            if self._proc.poll() is not None:
                break
        self.release()
        raise RuntimeError(
            f"Could not read first frame with FFmpeg for {self.source_url} (stderr suppressed)."
        )

    def read(self, timeout: float = 1.0):
        ok, item = self.read_item(timeout=timeout)
        if not ok or item is None:
            return False, None
        return True, item.frame

    def read_item(self, timeout: float = 1.0):
        deadline = time.time() + timeout
        with self._cond:
            while self._latest_seq == self._last_delivered_seq and not self._stop.is_set():
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False, None
                self._cond.wait(timeout=remaining)
            if self._latest_frame is None:
                return False, None
            self._last_delivered_seq = self._latest_seq
            # Reader and consumer run on separate threads.  Hand out an owned
            # ndarray so downstream preprocessing/rendering cannot mutate the
            # producer's latest frame.
            return True, LiveFrameItem(
                frame=self._latest_frame.copy(),
                captured_at=self._latest_timestamp,
                seq=self._latest_seq,
                interarrival_ms=self._latest_interarrival_ms,
            )

    def release(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def _reader_loop(self, frame_size: int, pacing_fps: float) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        pacer = FramePacer(pacing_fps) if settings.LIVE_FFMPEG_REALTIME_PACING else None
        last_capture_ts: Optional[float] = None
        while not self._stop.is_set():
            raw = self._read_exact(frame_size)
            if raw is None:
                break
            if len(raw) != frame_size:
                continue
            if pacer:
                pacer.wait()
            captured_at = time.monotonic()
            interarrival_ms = (
                (captured_at - last_capture_ts) * 1000.0 if last_capture_ts is not None else 0.0
            )
            last_capture_ts = captured_at
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((self.height, self.width, 3)).copy()
            with self._cond:
                self.frames_read += 1
                self._latest_seq += 1
                self._latest_frame = frame
                self._latest_timestamp = captured_at
                self._latest_interarrival_ms = interarrival_ms
                self._cond.notify_all()
        self._stop.set()
        with self._cond:
            self._cond.notify_all()

    def _read_exact(self, size: int) -> Optional[bytes]:
        """Read one complete raw BGR frame; pipe reads may be short."""
        if size <= 0 or self._proc is None or self._proc.stdout is None:
            return None
        buffer = bytearray(size)
        view = memoryview(buffer)
        offset = 0
        while offset < size and not self._stop.is_set():
            count = self._proc.stdout.readinto(view[offset:])
            if not count:
                return None
            offset += count
        return bytes(buffer) if offset == size else None

    def _read_stderr_tail(self) -> str:
        try:
            if self._proc and self._proc.stderr:
                data = self._proc.stderr.read(4096)
                return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""
        return ""


def _probe_live_source(source_url: str) -> tuple[int, int, float]:
    cmd = [
        settings.LIVE_FFPROBE_BIN,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate",
        "-of", "json",
        source_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.LIVE_FFPROBE_TIMEOUT_S)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        raise RuntimeError("ffprobe found no video stream")
    stream = streams[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid probed stream size: {width}x{height}")
    fps = _parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
    return width, height, fps or 25.0

def _parse_fps(raw: str | None) -> float:
    if not raw or raw == "0/0":
        return 0.0
    if "/" in raw:
        num, den = raw.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    return float(raw)


def _open_live_reader(source_url: str, crop_rect: Optional[tuple[int, int, int, int]] = None):
    prefer = os.environ.get("LIVE_FRAME_READER", settings.LIVE_READER_BACKEND).lower()
    if prefer in ("auto", "ffmpeg"):
        try:
            reader = FfmpegLatestFrameReader(source_url, crop_rect=crop_rect)
            reader.open()
            logger.info(
                "Live source opened with FFmpeg latest-frame reader: output=%sx%s cropped=%s",
                reader.width,
                reader.height,
                reader.cropped_in_reader,
            )
            return reader
        except Exception as exc:
            if prefer == "ffmpeg":
                raise
            logger.warning("FFmpeg live reader failed, falling back to OpenCV: %s", exc)
    reader = OpenCvFrameReader(source_url)
    reader.open()
    logger.info("Live source opened with OpenCV reader")
    return reader


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
    perf: dict = field(default_factory=dict)
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
            "perf": self.perf,
            "latest_frame_seq": self.latest_frame_seq,
            "model_name": self.model_name,
            "roi_mode": self.roi_mode,
            "ai_imgsz": self.ai_imgsz,
        }


class LiveSessionManager:
    def __init__(self):
        self._sessions: Dict[str, LiveSessionState] = {}
        self._lock = threading.Lock()

    def create(self, source_url: str, lane_config: Optional[dict], frame_skip: int = 1) -> LiveSessionState:
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
            requested_roi_mode = lane_config.get("roi_mode") or os.environ.get("LIVE_ROI_MODE") or settings.ROI_MODE
            processing_roi = lane_config.get("crop_rect_padded") or lane_config.get("processing_roi") or lane_config.get("annotation_roi")
            source_width = 0
            source_height = 0
            source_fps = 25.0
            try:
                source_width, source_height, source_fps = _probe_live_source(session.source_url)
            except Exception as exc:
                logger.warning("Could not probe live source before open; disabling FFmpeg crop-in-reader: %s", exc)

            width = source_width
            height = source_height
            has_crop = bool(processing_roi)
            use_detection_crop = has_crop and requested_roi_mode in ("crop_rect", "roi_crop") and width > 0 and height > 0
            if use_detection_crop:
                cx = int(float(processing_roi.get("x", 0))); cy = int(float(processing_roi.get("y", 0)))
                cw = int(float(processing_roi.get("width", width))); ch = int(float(processing_roi.get("height", height)))
                crop_rect = _normalize_even_crop_rect((cx, cy, cx + cw, cy + ch), width, height)
                if crop_rect is None:
                    logger.warning("Invalid live crop rect %s; falling back to full_frame", crop_rect)
                    out_w, out_h = width, height
                    use_detection_crop = False
                else:
                    out_w = crop_rect[2] - crop_rect[0]
                    out_h = crop_rect[3] - crop_rect[1]
            else:
                crop_rect = None
                out_w, out_h = width, height
            live_roi_mode = requested_roi_mode if use_detection_crop else "full_frame"

            cap = _open_live_reader(session.source_url, crop_rect if use_detection_crop else None)
            reader_cropped = bool(getattr(cap, "cropped_in_reader", False))
            if width <= 0 or height <= 0:
                width = int(getattr(cap, "source_width", 0) or cap.width or 0)
                height = int(getattr(cap, "source_height", 0) or cap.height or 0)
                out_w, out_h = int(cap.width or width), int(cap.height or height)
            source_fps = cap.fps or source_fps
            logger.info(
                "Live source opened: session=%s source=%s source=%sx%s output=%sx%s @ %.2f crop_in_reader=%s",
                session.session_id,
                session.source_url,
                width,
                height,
                int(cap.width or out_w),
                int(cap.height or out_h),
                source_fps,
                reader_cropped,
            )

            lanes_source = lane_config.get("lanes", [])
            geometry_space = lane_config.get("geometry_space")
            if geometry_space is None:
                geometry_space = "crop_local" if (lane_config.get("crop_rect_padded") or lane_config.get("processing_width")) else "source_frame"
                logger.warning(
                    "Live config has no geometry_space; inferred %s for backward compatibility: session=%s",
                    geometry_space, session.session_id,
                )
            if geometry_space not in {"source_frame", "crop_local"}:
                raise ValueError(f"Unsupported geometry coordinate space: {geometry_space}")
            lanes_processing = lanes_source
            if use_detection_crop and lanes_source and geometry_space == "source_frame":
                lanes_processing = FrameTransform(
                    full_w=width, full_h=height,
                    crop_w=out_w, crop_h=out_h,
                    ai_w=settings.ROI_INPUT_SIZE, ai_h=settings.ROI_INPUT_SIZE,
                    offset_x=crop_rect[0], offset_y=crop_rect[1],
                ).shift_lanes_to_crop(lanes_source)

            poly_mask = None
            poly_pts = lane_config.get("roi_polygon", [])
            if poly_pts and len(poly_pts) >= 3 and use_detection_crop and requested_roi_mode == "roi_crop":
                src = np.array(poly_pts, dtype=np.float32).reshape(-1, 2)
                if geometry_space == "crop_local":
                    poly_mask = src.astype(np.int32)
                else:
                    poly_mask = (src - [crop_rect[0], crop_rect[1]]).astype(np.int32)

            if lanes_processing:
                sample = (lanes_source[0].get("valid_zone") or [[None, None]])[0]
                normalized = (lanes_processing[0].get("valid_zone") or [[None, None]])[0]
                logger.info(
                    "Live geometry normalized: session=%s geometry_space=%s processing_size=%sx%s "
                    "lane_1.point_before=%s lane_1.point_after=%s",
                    session.session_id, geometry_space, out_w, out_h, sample, normalized,
                )

            processor = FrameProcessor(
                roi_input_size=settings.ROI_INPUT_SIZE,
                roi_mode=live_roi_mode,
                enable_stabilization=False,
            )
            renderer = FrameRenderer(lanes_processing or [], settings_obj=settings)
            tracker = LocalTracker(
                match_threshold=settings.TRACK_MATCH_THRESHOLD,
                track_buffer=settings.TRACK_BUFFER,
                min_hits=settings.LIVE_TRACK_MIN_HITS,
                max_lost_seconds=settings.LIVE_TRACK_MAX_LOST_SECONDS,
            )
            counter = CountingState(lanes_processing) if lanes_processing else None
            session.counts = _empty_counts(lanes_processing or [])
            if settings.AI_LOCAL or settings.AI_SERVING_URL == "local":
                ai_client = LocalInferenceClient(max_workers=1, imgsz=settings.ROI_INPUT_SIZE)
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

            last_tracking_ts = None
            reconnect_attempts = 0
            last_tick = time.time()
            last_processed = 0
            frame_idx = 0
            session.model_name = settings.AI_MODEL_PATH
            session.roi_mode = live_roi_mode
            session.ai_imgsz = settings.AI_IMGSZ
            session.status = "running"

            def reset_runtime_state(reason: str) -> None:
                nonlocal counter, last_tracking_ts
                logger.warning("Resetting live runtime state: session=%s reason=%s", session.session_id, reason)
                tracker.reset()
                counter = CountingState(lanes_processing) if lanes_processing else None
                session.counts = _empty_counts(lanes_processing or [])
                session.lane_volume_total = 0
                session.global_unique_count = 0
                session.multi_lane_track_count = 0
                session.multi_lane_tracks = []
                session.latest_tracks = []
                session.latest_debug = {}
                last_tracking_ts = None

            def process_frame(item: LiveFrameItem, reader_wait_ms: float) -> None:
                nonlocal last_tick, last_processed, last_tracking_ts, reader_cropped
                frame_timestamp = item.captured_at or time.monotonic()
                frame_age_ms = max(0.0, (time.monotonic() - frame_timestamp) * 1000.0)
                if frame_age_ms > settings.LIVE_MAX_FRAME_AGE_SECONDS * 1000.0:
                    session.frames_dropped += 1
                    session.perf = {
                        **session.perf,
                        "frame_age_ms": round(frame_age_ms, 1),
                        "dropped_reason": "stale_frame",
                    }
                    return

                preprocess_start = time.perf_counter()
                active_crop_rect = None if reader_cropped else crop_rect
                cropped, ai_frame, transform = processor.process_for_ai(item.frame, active_crop_rect, poly_mask)
                preprocess_ms = (time.perf_counter() - preprocess_start) * 1000.0

                infer_submit_ts = time.perf_counter()
                if hasattr(ai_client, "submit_frame_array"):
                    future = ai_client.submit_frame_array(ai_frame)
                else:
                    jpeg = processor.encode_jpeg(ai_frame)
                    if not jpeg:
                        session.frames_dropped += 1
                        session.perf = {**session.perf, "dropped_reason": "jpeg_encode_failed"}
                        return
                    future = ai_client.submit_frame(jpeg)
                raw = future.result(timeout=30)
                infer_wall_ms = (time.perf_counter() - infer_submit_ts) * 1000.0

                track_start = time.perf_counter()
                for det in raw:
                    bbox = det.get("bbox_xyxy")
                    if bbox and len(bbox) == 4:
                        det["bbox_xyxy"] = transform.bbox_ai_to_crop(bbox)
                filtered_raw = filter_detections_for_tracking(
                    raw,
                    lanes_processing or [],
                    settings.TRACK_FILTER_ZONE_PADDING_PX,
                )
                if (
                    last_tracking_ts is not None
                    and frame_timestamp - last_tracking_ts > settings.LIVE_TRACK_RESET_GAP_SECONDS
                ):
                    reset_runtime_state(f"input_gap_{frame_timestamp - last_tracking_ts:.2f}s")
                tracked_outputs = tracker.update(filtered_raw, timestamp=frame_timestamp)
                last_tracking_ts = frame_timestamp
                enriched = [
                    {
                        "track_id": t.track_id,
                        "bbox_xyxy": t.bbox_xyxy,
                        "class_name": t.class_name,
                        "confidence": t.confidence,
                        "kalman_velocity": t.kalman_velocity,
                        "is_lost": t.is_lost,
                        "lost_frames": t.lost_frames,
                        "hits": t.hits,
                        "confirmed": t.confirmed,
                        "last_seen_age_ms": round(t.last_seen_age_s * 1000.0, 1),
                    }
                    for t in tracked_outputs
                ]
                track_ms = (time.perf_counter() - track_start) * 1000.0

                if counter:
                    counter.process_detections(enriched)
                    counter.prune_inactive_tracks({t.track_id for t in tracked_outputs})
                    session.counts = _counts_map(counter, lanes_processing or [])
                    diagnostics = counter.get_diagnostics()
                    session.lane_volume_total = diagnostics["lane_volume_total"]
                    session.global_unique_count = diagnostics["global_unique_count"]
                    session.multi_lane_track_count = diagnostics["multi_lane_track_count"]
                    session.multi_lane_tracks = diagnostics["multi_lane_tracks"]
                    session.latest_debug = counter.get_debug_snapshot()
                session.latest_tracks = enriched

                render_start = time.perf_counter()
                annotated = renderer.draw(
                    cropped.copy(),
                    enriched,
                    session.latest_debug if settings.RENDER_DEBUG else None,
                )
                render_ms = (time.perf_counter() - render_start) * 1000.0

                jpeg_start = time.perf_counter()
                ok, frame_jpeg = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                jpeg_ms = (time.perf_counter() - jpeg_start) * 1000.0
                publish_ms = render_ms + jpeg_ms
                if ok:
                    session.latest_frame_jpeg = frame_jpeg.tobytes()
                    session.latest_frame_seq += 1
                session.frames_processed += 1
                session.perf = {
                    **session.perf,
                    "reader_wait_ms": round(reader_wait_ms, 1),
                    "frame_interarrival_ms": round(item.interarrival_ms, 1),
                    "frame_age_ms": round(frame_age_ms, 1),
                    "preprocess_ms": round(preprocess_ms, 1),
                    "infer_ms": round(infer_wall_ms, 1),
                    "infer_wall_ms": round(infer_wall_ms, 1),
                    "infer_model_ms": round(infer_wall_ms, 1),
                    "future_done_wait_ms": 0.0,
                    "loop_idle_ms": round(reader_wait_ms, 1),
                    "track_ms": round(track_ms, 1),
                    "raw_det": len(raw),
                    "kept_det": len(filtered_raw),
                    "active_tracks": tracker.active_count,
                    "lost_tracks": tracker.lost_count,
                    "render_ms": round(render_ms, 1),
                    "jpeg_ms": round(jpeg_ms, 1),
                    "publish_ms": round(publish_ms, 1),
                    "reader_cropped": reader_cropped,
                    "reader_output": [int(cap.width or 0), int(cap.height or 0)],
                    "queued_frames": 0,
                }
                now = time.time()
                if now - last_tick >= 2.0:
                    session.fps = (session.frames_processed - last_processed) / (now - last_tick)
                    last_processed = session.frames_processed
                    last_tick = now
                    logger.info(
                        "Live session tick: session=%s status=%s read=%s processed=%s dropped=%s "
                        "fps=%.2f reader_wait_ms=%s frame_age_ms=%s infer_wall_ms=%s total=%s",
                        session.session_id,
                        session.status,
                        session.frames_read,
                        session.frames_processed,
                        session.frames_dropped,
                        session.fps,
                        session.perf.get("reader_wait_ms"),
                        session.perf.get("frame_age_ms"),
                        session.perf.get("infer_wall_ms"),
                        session.lane_volume_total,
                    )
                session.updated_at = now

            while not session.stop_event.is_set():
                wait_start = time.perf_counter()
                if hasattr(cap, "read_item"):
                    ok, item = cap.read_item(timeout=0.1)
                else:
                    ok, frame = cap.read(timeout=0.1)
                    item = LiveFrameItem(frame=frame, captured_at=time.monotonic(), seq=frame_idx) if ok else None
                reader_wait_ms = (time.perf_counter() - wait_start) * 1000.0
                if not ok or item is None:
                    if getattr(cap, "_stop", None) is not None and cap._stop.is_set():
                        if reconnect_attempts >= settings.LIVE_RECONNECT_ATTEMPTS:
                            session.last_error = "Stream ended after FFmpeg reconnect attempts"
                            break
                        reconnect_attempts += 1
                        logger.warning(
                            "Restarting FFmpeg live reader after ingest failure: session=%s attempt=%s/%s",
                            session.session_id, reconnect_attempts, settings.LIVE_RECONNECT_ATTEMPTS,
                        )
                        cap.release()
                        if settings.LIVE_RECONNECT_DELAY_SECONDS:
                            session.stop_event.wait(settings.LIVE_RECONNECT_DELAY_SECONDS)
                        if session.stop_event.is_set():
                            break
                        replacement = _open_live_reader(session.source_url, crop_rect if use_detection_crop else None)
                        replacement_size = (int(replacement.width or 0), int(replacement.height or 0))
                        expected_size = (int(out_w), int(out_h))
                        if replacement_size != expected_size:
                            replacement.release()
                            raise RuntimeError(
                                f"Live source dimensions changed from {expected_size} to {replacement_size}; "
                                "restart with revalidated geometry"
                            )
                        cap = replacement
                        reader_cropped = bool(getattr(cap, "cropped_in_reader", False))
                        reset_runtime_state("ffmpeg_reconnect")
                        continue
                    continue
                reconnect_attempts = 0
                session.frames_read = max(session.frames_read + 1, getattr(cap, "frames_read", session.frames_read + 1))

                if frame_idx % frame_skip == 0:
                    process_frame(item, reader_wait_ms)
                else:
                    session.frames_dropped += 1
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


def _empty_counts(lanes: list) -> Dict[str, Dict[str, int]]:
    return {
        lane.get("lane_id", f"lane_{index + 1}"): {
            class_name: 0 for class_name in lane.get("class_allowed") or ["car", "bus", "truck", "motorcycle"]
        }
        for index, lane in enumerate(lanes)
    }


def _counts_map(counter: CountingState, lanes: list) -> Dict[str, Dict[str, int]]:
    counts = _empty_counts(lanes)
    for stat in counter.get_statistics():
        lane_id = stat["lane_id"]
        vehicle_type = stat["vehicle_type"]
        if vehicle_type == "total":
            counts.setdefault(lane_id, counts.get(lane_id, {}))
            continue
        counts.setdefault(lane_id, {})[vehicle_type] = stat["count"]
    return counts


live_manager = LiveSessionManager()


