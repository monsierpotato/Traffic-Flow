from __future__ import annotations

import time
import uuid
import asyncio
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from api.services.live_service import live_manager
from api.services.youtube_resolver import (
    ResolvedMedia,
    SourceResolutionError,
    is_youtube_url,
    media_url_needs_refresh,
    redact_process_detail,
    resolve_youtube_url,
    validate_direct_source_url,
)
from shared.config import settings

router = APIRouter()

LIVE_PREVIEW_DIR = Path(settings.STORAGE_DIR) / "live_previews"
LIVE_SOURCES: Dict[str, dict] = {}
LIVE_SOURCES_LOCK = threading.Lock()


class LiveSessionCreate(BaseModel):
    source_url: str = Field(..., min_length=3)
    source_id: Optional[str] = Field(default=None, min_length=1)
    lane_config: Optional[Dict[str, Any]] = None
    frame_skip: int = Field(default=1, ge=1, le=10)


class LiveSourceResolve(BaseModel):
    url: str = Field(..., min_length=3)


class LiveConfigValidate(BaseModel):
    lane_config: Dict[str, Any]


def _raise_resolution_error(exc: SourceResolutionError) -> None:
    raise HTTPException(exc.status_code, str(exc)) from exc


def _prune_sources() -> None:
    cutoff = time.time() - settings.LIVE_SOURCE_TTL_SECONDS
    expired: list[dict] = []
    with LIVE_SOURCES_LOCK:
        for source_id, source in list(LIVE_SOURCES.items()):
            if source.get("updated_at", source.get("created_at", 0)) < cutoff:
                expired.append(LIVE_SOURCES.pop(source_id))
    for source in expired:
        preview_path = source.get("preview_path")
        if preview_path:
            try:
                Path(preview_path).unlink(missing_ok=True)
            except OSError:
                pass


def _get_source(source_id: str) -> Optional[dict]:
    _prune_sources()
    with LIVE_SOURCES_LOCK:
        return LIVE_SOURCES.get(source_id)


def _public_source(source: dict) -> dict:
    """Never expose a signed YouTube media URL or a filesystem path."""
    public = {key: value for key, value in source.items() if key not in {"preview_path", "resolved_url"}}
    if is_youtube_url(source["original_url"]):
        public["source_url"] = source["original_url"]
    else:
        public["source_url"] = source["resolved_url"]
    return public


def _validate_source_input(url: str) -> None:
    if is_youtube_url(url):
        return
    try:
        validate_direct_source_url(url)
    except SourceResolutionError as exc:
        _raise_resolution_error(exc)


def _resolve_media(url: str) -> ResolvedMedia:
    _validate_source_input(url)
    if is_youtube_url(url):
        try:
            return resolve_youtube_url(url)
        except SourceResolutionError as exc:
            _raise_resolution_error(exc)
    return ResolvedMedia(url=url)


async def _refresh_source(source: dict, *, capture: bool = False) -> dict:
    media = await asyncio.to_thread(_resolve_media, source["original_url"])
    source.update(
        {
            "resolved_url": media.url,
            "source_type": _source_type(media.url, source["original_url"]),
            "resolved_expires_at": media.expires_at,
            "updated_at": time.time(),
        }
    )
    if capture:
        snapshot = await asyncio.to_thread(_capture_snapshot, media.url, source["source_id"])
        source.update(snapshot)
    return source


def _source_type(url: str, original_url: str) -> str:
    if is_youtube_url(original_url):
        return "youtube_hls" if ".m3u8" in url else "youtube_media"
    parsed = urlparse(url)
    path = parsed.path.lower()
    if parsed.scheme == "rtsp":
        return "rtsp"
    if path.endswith(".m3u8"):
        return "hls"
    if "mjpeg" in path or "mjpg" in path:
        return "mjpeg"
    if path.endswith((".mp4", ".avi", ".mov", ".mkv", ".webm")):
        return "video_file"
    return "direct_stream"


def _capture_snapshot(source_url: str, source_id: str) -> dict:
    LIVE_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    import subprocess

    command = [
        settings.LIVE_FFMPEG_BIN,
        "-hide_banner",
        "-loglevel", settings.LIVE_FFMPEG_LOGLEVEL,
        "-nostdin",
        "-rw_timeout", str(settings.LIVE_FFMPEG_RW_TIMEOUT_US),
        "-i", source_url,
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=settings.LIVE_PREVIEW_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise HTTPException(500, "FFmpeg is not installed in the API environment") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "Timed out while capturing the live source preview") from exc
    except subprocess.CalledProcessError as exc:
        detail = redact_process_detail((exc.stderr or b"").decode("utf-8", errors="ignore"))
        raise HTTPException(422, f"Could not capture a frame from the live source: {detail}") from exc
    frame = cv2.imdecode(np.frombuffer(result.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(422, "Source opened but no video frame could be decoded")
    height, width = frame.shape[:2]
    preview_path = LIVE_PREVIEW_DIR / f"{source_id}.jpg"
    if not cv2.imwrite(str(preview_path), frame):
        raise HTTPException(500, "Could not write live source preview frame")
    return {
        "width": width,
        "height": height,
        "fps": 0.0,
        "preview_path": str(preview_path),
        "preview_url": f"/live/sources/{source_id}/preview",
    }


def _validate_lane_config(config: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    resolution = config.get("resolution") or {}
    width = int(resolution.get("width") or 0)
    height = int(resolution.get("height") or 0)
    if width <= 0 or height <= 0:
        errors.append("resolution.width and resolution.height are required")
    if not (config.get("processing_roi") or config.get("annotation_roi")):
        errors.append("processing_roi or annotation_roi is required")
    geometry_space = config.get("geometry_space")
    if geometry_space is not None and geometry_space not in {"source_frame", "crop_local"}:
        errors.append("geometry_space must be source_frame or crop_local")
    # Existing saved configs with a padded crop already store lane points in
    # crop-local space.  Preserve that convention until clients explicitly
    # include geometry_space.
    if geometry_space is None:
        geometry_space = "crop_local" if (config.get("crop_rect_padded") or config.get("processing_width")) else "source_frame"
    roi_polygon = config.get("roi_polygon") or []
    if len(roi_polygon) < 3:
        errors.append("roi_polygon must contain at least 3 points")
    lanes = config.get("lanes") or []
    if not lanes:
        errors.append("at least one lane is required")
    for index, lane in enumerate(lanes, start=1):
        prefix = f"lane {index}"
        if len(lane.get("valid_zone") or []) < 3:
            errors.append(f"{prefix}: valid_zone must contain at least 3 points")
        if len(lane.get("counting_line") or []) != 2:
            errors.append(f"{prefix}: counting_line must contain exactly 2 points")
        if len(lane.get("direction") or []) != 2:
            errors.append(f"{prefix}: direction must contain exactly 2 points")
    if geometry_space == "source_frame":
        coordinate_width, coordinate_height = width, height
    else:
        crop = config.get("crop_rect_padded") or config.get("processing_roi") or config.get("annotation_roi") or {}
        coordinate_width = int(config.get("processing_width") or crop.get("width") or 0)
        coordinate_height = int(config.get("processing_height") or crop.get("height") or 0)
    if coordinate_width > 0 and coordinate_height > 0:
        all_geometry = [("roi_polygon", roi_polygon)]
        for index, lane in enumerate(lanes, start=1):
            all_geometry.extend([
                (f"lane {index}.valid_zone", lane.get("valid_zone") or []),
                (f"lane {index}.counting_line", lane.get("counting_line") or []),
                (f"lane {index}.direction", lane.get("direction") or []),
            ])
        for label, points in all_geometry:
            for point in points:
                if len(point) >= 2 and not (0 <= point[0] < coordinate_width and 0 <= point[1] < coordinate_height):
                    errors.append(f"{label}: point {point} is outside {geometry_space} bounds")
                    break
    return not errors, errors


@router.post("/resolve")
async def resolve_live_source(payload: LiveSourceResolve):
    original_url = payload.url.strip()
    if not original_url:
        raise HTTPException(422, "Source URL is required")
    media = await asyncio.to_thread(_resolve_media, original_url)
    source_id = str(uuid.uuid4())
    snapshot = await asyncio.to_thread(_capture_snapshot, media.url, source_id)
    source = {
        "source_id": source_id,
        "original_url": original_url,
        "resolved_url": media.url,
        "source_url": original_url if is_youtube_url(original_url) else media.url,
        "source_type": _source_type(media.url, original_url),
        "resolved_expires_at": media.expires_at,
        "created_at": time.time(),
        "updated_at": time.time(),
        **snapshot,
    }
    _prune_sources()
    with LIVE_SOURCES_LOCK:
        LIVE_SOURCES[source_id] = source
    return _public_source(source)


@router.post("/sources/{source_id}/snapshot")
async def refresh_live_snapshot(source_id: str):
    source = _get_source(source_id)
    if not source:
        raise HTTPException(404, "Live source not found")
    await _refresh_source(source, capture=True)
    return _public_source(source)


@router.get("/sources/{source_id}/preview")
async def get_live_preview(source_id: str):
    source = _get_source(source_id)
    if not source:
        raise HTTPException(404, "Live source not found")
    preview_path = Path(source["preview_path"])
    if not preview_path.exists():
        raise HTTPException(404, "Live preview not found")
    return FileResponse(str(preview_path), media_type="image/jpeg")


@router.post("/validate-config")
async def validate_live_config(payload: LiveConfigValidate):
    valid, errors = _validate_lane_config(payload.lane_config)
    return {"valid": valid, "errors": errors}


@router.post('/sessions')
async def create_live_session(payload: LiveSessionCreate):
    valid, errors = _validate_lane_config(payload.lane_config or {})
    if not valid:
        raise HTTPException(422, {"message": "Valid lane_config is required before live counting", "errors": errors})
    active_sessions = [
        session for session in live_manager.list()
        if session.status in {"starting", "running", "stopping"}
    ]
    if len(active_sessions) >= settings.LIVE_MAX_SESSIONS:
        raise HTTPException(429, "Maximum number of concurrent live sessions reached")

    source = _get_source(payload.source_id) if payload.source_id else None
    source_origin_url = None
    if source:
        source_origin_url = source["original_url"] if is_youtube_url(source["original_url"]) else None
        if source_origin_url:
            if media_url_needs_refresh(source.get("resolved_expires_at")):
                await _refresh_source(source)
        source_url = source["resolved_url"]
        source_expires_at = source.get("resolved_expires_at")
    else:
        # Backward-compatible clients may still send a URL instead of source_id.
        # YouTube page URLs are resolved here so starting a session never passes
        # a page URL into FFmpeg.
        media = await asyncio.to_thread(_resolve_media, payload.source_url)
        source_url = media.url
        source_origin_url = payload.source_url if is_youtube_url(payload.source_url) else None
        source_expires_at = media.expires_at

    session = live_manager.create(
        source_url=source_url,
        lane_config=payload.lane_config,
        frame_skip=payload.frame_skip,
        source_origin_url=source_origin_url,
        source_expires_at=source_expires_at,
    )
    return session.snapshot()


@router.get('/sessions')
async def list_live_sessions():
    return {"sessions": [session.snapshot() for session in live_manager.list()]}


@router.get('/sessions/{session_id}')
async def get_live_session(session_id: str):
    session = live_manager.get(session_id)
    if not session:
        raise HTTPException(404, 'Live session not found')
    return session.snapshot()


@router.get('/sessions/{session_id}/frame')
async def get_live_session_frame(session_id: str):
    session = live_manager.get(session_id)
    if not session:
        raise HTTPException(404, 'Live session not found')
    if not session.latest_frame_jpeg:
        raise HTTPException(404, 'Live frame not ready')
    return Response(
        content=session.latest_frame_jpeg,
        media_type='image/jpeg',
        headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'X-Live-Frame-Seq': str(session.latest_frame_seq),
        },
    )


@router.get('/sessions/{session_id}/stream')
async def stream_live_session_frames(session_id: str):
    session = live_manager.get(session_id)
    if not session:
        raise HTTPException(404, 'Live session not found')

    async def frame_generator():
        last_seq = -1
        idle_ticks = 0
        while True:
            current = live_manager.get(session_id)
            if not current:
                break
            if current.latest_frame_jpeg and current.latest_frame_seq != last_seq:
                last_seq = current.latest_frame_seq
                idle_ticks = 0
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Cache-Control: no-store\r\n\r\n'
                    + current.latest_frame_jpeg
                    + b'\r\n'
                )
            else:
                idle_ticks += 1
            if current.status in {'stopped', 'failed', 'ended'} and idle_ticks > 20:
                break
            await asyncio.sleep(0.1)

    return StreamingResponse(
        frame_generator(),
        media_type='multipart/x-mixed-replace; boundary=frame',
        headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'},
    )


@router.delete('/sessions/{session_id}')
async def stop_live_session(session_id: str):
    if not live_manager.stop(session_id):
        raise HTTPException(404, 'Live session not found')
    return {'session_id': session_id, 'status': 'stopping'}


@router.delete('/sessions/{session_id}/remove')
async def remove_live_session(session_id: str):
    if not live_manager.remove(session_id):
        raise HTTPException(404, 'Live session not found')
    return {'session_id': session_id, 'status': 'removed'}
