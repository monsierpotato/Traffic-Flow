"""Local YOLO inference client (GPU auto-detect, fallback CPU)."""

import logging
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, Future
import numpy as np

from shared.config import settings

logger = logging.getLogger(__name__)


def _detect_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            # Override with config if set
            dev = settings.AI_DEVICE
            if dev and dev != "0" and dev != "cpu":
                device = dev if dev.startswith("cuda") else f"cuda:{dev}"
            else:
                device = "cuda:0" if dev != "cpu" else "cpu"
            logger.info(f"GPU detected: {torch.cuda.get_device_name(0)} | device={device}")
            return device
    except Exception:
        pass
    logger.info("No GPU found — using CPU")
    return "cpu"


def _parse_class_ids(raw: str) -> list:
    if not raw:
        return None


def _parse_class_name_map(raw: str) -> dict[int, str]:
    mapping: dict[int, str] = {}
    if not raw:
        return mapping
    for item in raw.split(','):
        if ':' not in item:
            continue
        key, value = item.split(':', 1)
        try:
            mapping[int(key.strip())] = value.strip()
        except ValueError:
            continue
    return mapping
    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except (ValueError, TypeError):
        return None


class LocalInferenceClient:
    """Wraps YOLO + ByteTrack locally with GPU acceleration when available."""

    def __init__(self, model_path: str = None,
                 confidence: float = None, max_workers: int = 1):
        from tfengine.core_ai import YoloByteTrackDetector
        device = _detect_device()
        self._detector = YoloByteTrackDetector(
            model_path=model_path or settings.AI_MODEL_PATH,
            confidence=confidence if confidence is not None else settings.AI_CONFIDENCE,
            device=device,
            imgsz=settings.AI_IMGSZ,
            half=settings.AI_HALF and device != "cpu",
            class_ids=_parse_class_ids(settings.AI_CLASS_IDS),
            class_name_map=_parse_class_name_map(settings.AI_CLASS_NAME_MAP),
        )
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._session_id = "local"

    def create_session(self) -> str:
        return self._session_id

    def delete_session(self):
        pass

    def _detect_one(self, jpeg_bytes: bytes) -> List[dict]:
        import cv2
        arr = np.frombuffer(jpeg_bytes, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return []
        dets = self._detector.detect_and_track(frame)
        return [
            {
                "track_id": d.track_id,
                "class_id": d.class_id,
                "class_name": d.class_name,
                "confidence": d.confidence,
                "bbox_xyxy": list(d.bbox_xyxy),
            }
            for d in dets
        ]

    def submit_frame(self, jpeg_bytes: bytes) -> Future:
        return self._executor.submit(self._detect_one, jpeg_bytes)

    def shutdown(self, wait: bool = False):
        self._executor.shutdown(wait=wait)
