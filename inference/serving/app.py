from __future__ import annotations

import io
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from tfengine.core_ai import Detection, YoloByteTrackDetector


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TrackSession:
    def __init__(self, model_path: str, classes: Optional[list[str]] = None,
                 confidence: float = 0.25, device: Optional[str] = None):
        self.detector = YoloByteTrackDetector(
            model_path=model_path,
            classes=classes,
            confidence=confidence,
            device=device,
        )
        self.last_access = time.monotonic()

    def touch(self) -> None:
        self.last_access = time.monotonic()


class SessionStore:
    def __init__(self, model_path: str, classes: Optional[list[str]] = None,
                 confidence: float = 0.25, device: Optional[str] = None,
                 ttl: float = 600.0, max_sessions: int = 32):
        self.model_path = model_path
        self.classes = classes
        self.confidence = confidence
        self.device = device
        self.ttl = ttl
        self.max_sessions = max_sessions
        self._sessions: Dict[str, TrackSession] = {}

    def get_or_create(self, session_id: Optional[str] = None) -> tuple[str, TrackSession]:
        if session_id and session_id in self._sessions:
            sess = self._sessions[session_id]
            sess.touch()
            return session_id, sess

        if len(self._sessions) >= self.max_sessions:
            self._evict_stale()

        sid = session_id or uuid.uuid4().hex[:16]
        sess = TrackSession(
            model_path=self.model_path,
            classes=self.classes,
            confidence=self.confidence,
            device=self.device,
        )
        self._sessions[sid] = sess
        return sid, sess

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _evict_stale(self) -> None:
        now = time.monotonic()
        stale = [sid for sid, s in self._sessions.items()
                 if now - s.last_access > self.ttl]
        for sid in stale:
            self._sessions.pop(sid, None)


# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    store._sessions.clear()


app = FastAPI(title="TrafficFlow Model Serving", version="0.2.0",
              lifespan=lifespan)

store: SessionStore = None  # type: ignore[assignment]

# Separate model instance for raw (stateless) YOLO inference — no ByteTrack state
_raw_model: Optional[YoloByteTrackDetector] = None


def init_store(model_path: str = "models/yolov8n.pt",
               classes: Optional[list[str]] = None,
               confidence: float = 0.25,
               device: Optional[str] = None,
               ttl: float = 600.0,
               max_sessions: int = 32) -> None:
    global store, _raw_model
    allowed = classes or ["car", "bus", "truck", "motorcycle", "motorbike"]
    store = SessionStore(
        model_path=model_path,
        classes=allowed,
        confidence=confidence,
        device=device,
        ttl=ttl,
        max_sessions=max_sessions,
    )
    # Shared model for stateless raw YOLO inference
    _raw_model = YoloByteTrackDetector(
        model_path=model_path, classes=allowed,
        confidence=confidence, device=device,
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DetectionOut(BaseModel):
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


class DetectResponse(BaseModel):
    session_id: str
    detections: list[DetectionOut]


class SessionCreateResponse(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/session", response_model=SessionCreateResponse)
def create_session():
    sid, _ = store.get_or_create()
    return SessionCreateResponse(session_id=sid)


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    store.remove(session_id)
    return {"status": "deleted"}


@app.post("/detect", response_model=DetectResponse)
async def detect(
    image: UploadFile = File(...),
    session_id: str = Form(""),
    confidence: Optional[float] = Form(None),
):
    if store is None:
        raise HTTPException(503, "Model not initialized")

    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Invalid image data")

    if confidence is not None:
        old_conf = store.confidence
        store.confidence = confidence
        sid, sess = store.get_or_create(session_id or None)
        store.confidence = old_conf
    else:
        sid, sess = store.get_or_create(session_id or None)

    raw = sess.detector.detect_and_track(frame)
    detections = [
        DetectionOut(
            track_id=d.track_id,
            class_id=d.class_id,
            class_name=d.class_name,
            confidence=d.confidence,
            bbox_xyxy=d.bbox_xyxy,
        )
        for d in raw
    ]

    return DetectResponse(session_id=sid, detections=detections)


# ---------------------------------------------------------------------------
# Raw detect endpoint (no ByteTrack — for local-tracker approach)
# ---------------------------------------------------------------------------

class RawDetectionOut(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


class RawDetectResponse(BaseModel):
    detections: list[RawDetectionOut]


@app.post("/detect/raw", response_model=RawDetectResponse)
async def detect_raw(
    image: UploadFile = File(...),
    confidence: Optional[float] = Form(None),
):
    """YOLO only — returns raw detections without ByteTrack tracking.

    The caller (worker) is responsible for tracking via LocalTracker.
    Stateless — no session needed.
    """
    global _raw_model
    if _raw_model is None:
        raise HTTPException(503, "Model not initialized")

    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Invalid image data")

    raw = _raw_model.detect_raw(frame)
    detections = [
        RawDetectionOut(
            class_id=d.class_id,
            class_name=d.class_name,
            confidence=d.confidence,
            bbox_xyxy=d.bbox_xyxy,
        )
        for d in raw
    ]

    return RawDetectResponse(detections=detections)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/yolov8n.pt")
    parser.add_argument("--device", default=None)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--ttl", type=float, default=600.0)
    parser.add_argument("--max-sessions", type=int, default=32)
    args = parser.parse_args()

    init_store(
        model_path=args.model,
        confidence=args.confidence,
        device=args.device,
        ttl=args.ttl,
        max_sessions=args.max_sessions,
    )

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
