from __future__ import annotations

import subprocess
import sys
import time
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from api.services.live_service import live_manager
from shared.config import settings

router = APIRouter()

LIVE_PREVIEW_DIR = Path("storage/live_previews")
LIVE_SOURCES: Dict[str, dict] = {}


class LiveSessionCreate(BaseModel):
    source_url: str = Field(..., min_length=3)
    lane_config: Optional[Dict[str, Any]] = None
    frame_skip: int = Field(default=2, ge=1, le=10)


class LiveSourceResolve(BaseModel):
    url: str = Field(..., min_length=3)


class LiveConfigValidate(BaseModel):
    lane_config: Dict[str, Any]


def _is_youtube_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "youtube.com" in host or "youtu.be" in host


def _source_type(url: str, original_url: str) -> str:
    if _is_youtube_url(original_url):
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


def _resolve_youtube_url(url: str) -> str:
    yt_dlp_options = []
    if settings.YTDLP_COOKIES_FILE:
        yt_dlp_options.extend(["--cookies", _writable_cookies_file(settings.YTDLP_COOKIES_FILE)])
    if settings.YTDLP_JS_RUNTIME:
        yt_dlp_options.extend(["--js-runtimes", settings.YTDLP_JS_RUNTIME])
    if settings.YTDLP_REMOTE_COMPONENTS:
        yt_dlp_options.extend(["--remote-components", settings.YTDLP_REMOTE_COMPONENTS])
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        *yt_dlp_options,
        "--no-playlist",
        "--get-url",
        "-f",
        "best[protocol^=m3u8]/best",
        url,
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=45)
    except FileNotFoundError as exc:
        raise HTTPException(500, "yt-dlp is not installed in the API container/environment") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()[-1200:]
        raise HTTPException(422, f"Could not resolve YouTube URL with yt-dlp: {detail}") from exc
    urls = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not urls:
        raise HTTPException(422, "yt-dlp did not return a playable media URL")
    return urls[0]


def _writable_cookies_file(source_path: str) -> str:
    source = Path(source_path)
    if not source.exists():
        raise HTTPException(422, f"Configured YouTube cookies file is missing: {source_path}")
    LIVE_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    target = LIVE_PREVIEW_DIR / "yt_dlp_cookies.txt"
    try:
        shutil.copyfile(source, target)
    except Exception as exc:
        raise HTTPException(500, f"Could not prepare writable YouTube cookies file: {exc}") from exc
    return str(target)


def _capture_snapshot(source_url: str, source_id: str) -> dict:
    LIVE_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(source_url)
    try:
        if not cap.isOpened():
            raise HTTPException(422, "OpenCV could not open this source URL from the backend container")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame = None
        ok = False
        for _ in range(30):
            ok, candidate = cap.read()
            if ok and candidate is not None:
                frame = candidate
                break
        if frame is None:
            raise HTTPException(422, "Source opened but no video frame could be read")
        height, width = frame.shape[:2]
        preview_path = LIVE_PREVIEW_DIR / f"{source_id}.jpg"
        success = cv2.imwrite(str(preview_path), frame)
        if not success:
            raise HTTPException(500, "Could not write live source preview frame")
        return {
            "width": width,
            "height": height,
            "fps": round(fps, 3),
            "preview_path": str(preview_path),
            "preview_url": f"/live/sources/{source_id}/preview",
        }
    finally:
        cap.release()


def _validate_lane_config(config: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    resolution = config.get("resolution") or {}
    width = int(resolution.get("width") or 0)
    height = int(resolution.get("height") or 0)
    if width <= 0 or height <= 0:
        errors.append("resolution.width and resolution.height are required")
    if not (config.get("processing_roi") or config.get("annotation_roi")):
        errors.append("processing_roi or annotation_roi is required")
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
    if width > 0 and height > 0:
        for label, points in [("roi_polygon", roi_polygon)]:
            for point in points:
                if len(point) >= 2 and not (0 <= point[0] <= width and 0 <= point[1] <= height):
                    errors.append(f"{label}: point {point} is outside source resolution")
                    break
    return not errors, errors


@router.post("/resolve")
async def resolve_live_source(payload: LiveSourceResolve):
    original_url = payload.url.strip()
    resolved_url = _resolve_youtube_url(original_url) if _is_youtube_url(original_url) else original_url
    source_id = str(uuid.uuid4())
    snapshot = _capture_snapshot(resolved_url, source_id)
    source = {
        "source_id": source_id,
        "original_url": original_url,
        "resolved_url": resolved_url,
        "source_url": resolved_url,
        "source_type": _source_type(resolved_url, original_url),
        "created_at": time.time(),
        **snapshot,
    }
    LIVE_SOURCES[source_id] = source
    return {k: v for k, v in source.items() if k != "preview_path"}


@router.post("/sources/{source_id}/snapshot")
async def refresh_live_snapshot(source_id: str):
    source = LIVE_SOURCES.get(source_id)
    if not source:
        raise HTTPException(404, "Live source not found")
    snapshot = _capture_snapshot(source["resolved_url"], source_id)
    source.update(snapshot)
    source["updated_at"] = time.time()
    return {k: v for k, v in source.items() if k != "preview_path"}


@router.get("/sources/{source_id}/preview")
async def get_live_preview(source_id: str):
    source = LIVE_SOURCES.get(source_id)
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
    session = live_manager.create(
        source_url=payload.source_url,
        lane_config=payload.lane_config,
        frame_skip=payload.frame_skip,
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
