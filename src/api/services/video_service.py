import os
import json
import tempfile
import subprocess
import logging
import time
from pathlib import Path
from typing import Tuple
from dataclasses import dataclass
import cv2

from shared.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VideoMeta:
    width: int
    height: int
    fps: float
    duration_s: float = 0.0
    size_bytes: int = 0
    codec: str = ""
    pix_fmt: str = ""
    color_range: str = ""
    color_space: str = ""
    color_transfer: str = ""
    color_primaries: str = ""


def _ffprobe_stream_meta(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=codec_name,pix_fmt,color_range,color_space,color_transfer,color_primaries",
        "-of", "json",
        path,
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        streams = json.loads(result.stdout or "{}").get("streams", [])
        return streams[0] if streams else {}
    except Exception as exc:
        logger.debug("ffprobe stream metadata unavailable for %s: %s", path, exc)
        return {}


def _get_video_meta(path: str) -> VideoMeta:
    cap = cv2.VideoCapture(path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    size = os.path.getsize(path)
    duration = nframes / fps if fps > 0 else 0.0
    stream = _ffprobe_stream_meta(path)
    return VideoMeta(
        width=w,
        height=h,
        fps=fps,
        duration_s=duration,
        size_bytes=size,
        codec=stream.get("codec_name", ""),
        pix_fmt=stream.get("pix_fmt", ""),
        color_range=stream.get("color_range", ""),
        color_space=stream.get("color_space", ""),
        color_transfer=stream.get("color_transfer", ""),
        color_primaries=stream.get("color_primaries", ""),
    )


def normalize_video_path(input_path: str | Path) -> Tuple[str, VideoMeta, VideoMeta, float, bool]:
    """Transcode video to a working-copy path without loading the file into RAM.

    Returns (working_path, original_meta, working_meta, transcode_ms, owns_working_path).
    If no transcode is needed, working_path is input_path and owns_working_path is False.
    """
    t0 = time.perf_counter()
    input_path = str(input_path)
    temp_out_name = None

    try:
        orig_meta = _get_video_meta(input_path)

        # Skip transcode if within limits
        needs_transcode = (
            orig_meta.width > settings.VIDEO_MAX_WIDTH or
            orig_meta.height > settings.VIDEO_MAX_HEIGHT or
            orig_meta.fps > settings.VIDEO_MAX_FPS
        )
        if not needs_transcode or not settings.VIDEO_NORMALIZE_ENABLED:
            transcode_ms = (time.perf_counter() - t0) * 1000.0
            return input_path, orig_meta, orig_meta, transcode_ms, False

        temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_out_name = temp_out.name
        temp_out.close()

        vf = (
            f"fps={settings.VIDEO_MAX_FPS},"
            f"scale='min({settings.VIDEO_MAX_WIDTH},iw)':'min({settings.VIDEO_MAX_HEIGHT},ih)'"
            ":force_original_aspect_ratio=decrease:force_divisible_by=2"
        )

        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", settings.VIDEO_TRANSCODE_PRESET,
            "-crf", str(settings.VIDEO_TRANSCODE_CRF),
            "-pix_fmt", "yuv420p",
            "-colorspace", "bt709",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-color_range", "tv",
            "-movflags", "+faststart",
            "-an",  # strip audio
            temp_out_name,
        ]
        logger.info("Normalizing video with ffmpeg filter: %s", vf)
        subprocess.run(cmd, check=True, timeout=300, capture_output=True, text=True)

        working_meta = _get_video_meta(temp_out_name)
        transcode_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            f"Normalized: {orig_meta.width}x{orig_meta.height} @ {orig_meta.fps:.1f}fps "
            f"({orig_meta.size_bytes / 1e6:.1f}MB) → "
            f"{working_meta.width}x{working_meta.height} @ {working_meta.fps:.1f}fps "
            f"({working_meta.size_bytes / 1e6:.1f}MB) in {transcode_ms:.0f}ms | "
            f"color {orig_meta.color_space}/{orig_meta.color_transfer}/{orig_meta.color_range} → "
            f"{working_meta.color_space}/{working_meta.color_transfer}/{working_meta.color_range}"
        )
        return temp_out_name, orig_meta, working_meta, transcode_ms, True

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg transcode failed: {e}")
        if getattr(e, "stderr", None):
            logger.error("FFmpeg stderr: %s", e.stderr)
        # Fallback: return original
        transcode_ms = (time.perf_counter() - t0) * 1000.0
        if temp_out_name and os.path.exists(temp_out_name):
            try:
                os.unlink(temp_out_name)
            except Exception:
                pass
        return input_path, orig_meta, orig_meta, transcode_ms, False


def normalize_video(video_bytes: bytes) -> Tuple[bytes, VideoMeta, VideoMeta, float]:
    """Transcode video to working copy (max 1080p, max 30fps, H.264).
    Returns (working_bytes, original_meta, working_meta, transcode_ms).
    If video already ≤1080p and ≤30fps, returns original as-is.
    """
    temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_in.write(video_bytes)
    temp_in.close()
    working_path = None
    owns_working_path = False

    try:
        working_path, orig_meta, working_meta, transcode_ms, owns_working_path = normalize_video_path(temp_in.name)
        with open(working_path, "rb") as f:
            working_bytes = f.read()
        return working_bytes, orig_meta, working_meta, transcode_ms
    finally:
        for p in (temp_in.name, working_path if owns_working_path else None):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


def extract_first_frame_path(video_path: str | Path) -> bytes:
    """Extract the first frame from a video path and return JPEG bytes."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Could not open video file with OpenCV.")

    success, frame = cap.read()
    cap.release()

    if not success or frame is None:
        raise ValueError("Could not read first frame from video.")

    success, jpeg_bytes = cv2.imencode(".jpg", frame)
    if not success:
        raise ValueError("Could not encode frame to JPEG.")

    return jpeg_bytes.tobytes()


def extract_first_frame(video_bytes: bytes) -> bytes:
    """Writes video bytes to a temp file, extracts the first frame using OpenCV,
    and returns the frame encoded as JPEG bytes.
    """
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    try:
        temp_video.write(video_bytes)
        temp_video.close()

        return extract_first_frame_path(temp_video.name)

    except Exception as e:
        logger.error(f"Error extracting first frame: {str(e)}")
        raise e
    finally:
        # Clean up temporary video file
        if os.path.exists(temp_video.name):
            try:
                os.unlink(temp_video.name)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_video.name}: {str(e)}")


def crop_video(video_bytes: bytes, bbox: tuple) -> bytes:
    """
    Crops the video physically using OpenCV based on the bounding box (min_x, min_y, max_x, max_y).
    Returns the cropped video as bytes (mp4 format).
    """
    min_x, min_y, max_x, max_y = [int(v) for v in bbox]
    
    # Write input bytes to temp file
    temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_in.write(video_bytes)
    temp_in.close()

    temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_out_name = temp_out.name
    temp_out.close()

    try:
        cap = cv2.VideoCapture(temp_in.name)
        if not cap.isOpened():
            raise ValueError("Could not open video file with OpenCV for cropping.")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # fallback
            
        width = max_x - min_x
        height = max_y - min_y

        # Use mp4v codec
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_out_name, fourcc, fps, (width, height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Crop the frame
            cropped_frame = frame[min_y:max_y, min_x:max_x]
            out.write(cropped_frame)

        cap.release()
        out.release()

        with open(temp_out_name, "rb") as f:
            out_bytes = f.read()

        return out_bytes
    except Exception as e:
        logger.error(f"Error cropping video: {str(e)}")
        raise e
    finally:
        if os.path.exists(temp_in.name):
            try: os.unlink(temp_in.name)
            except: pass
        if os.path.exists(temp_out_name):
            try: os.unlink(temp_out_name)
            except: pass
