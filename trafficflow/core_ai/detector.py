from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class Detection:
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


class YoloByteTrackDetector:
    def __init__(
        self,
        model_path: str,
        classes: Optional[Sequence[str]] = None,
        confidence: float = 0.25,
        device: Optional[str] = None,
    ):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'ultralytics'. Install it to run Phase B: "
                "python -m pip install ultralytics"
            ) from exc

        self.model = YOLO(model_path)
        self.classes = set(classes or ["car", "bus", "truck", "motorcycle", "motorbike"])
        self.confidence = confidence
        self.device = device

    def detect_and_track(self, frame) -> List[Detection]:
        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )
        if not results:
            return []

        result = results[0]
        if result.boxes is None or result.boxes.id is None:
            return []

        names = result.names
        boxes = result.boxes.xyxy.cpu().tolist()
        ids = result.boxes.id.cpu().tolist()
        class_ids = result.boxes.cls.cpu().tolist()
        confidences = result.boxes.conf.cpu().tolist()

        detections: List[Detection] = []
        for bbox, track_id, class_id, conf in zip(boxes, ids, class_ids, confidences):
            class_id_int = int(class_id)
            class_name = str(names.get(class_id_int, class_id_int))
            if class_name not in self.classes:
                continue
            detections.append(
                Detection(
                    track_id=int(track_id),
                    class_id=class_id_int,
                    class_name=class_name,
                    confidence=float(conf),
                    bbox_xyxy=tuple(float(v) for v in bbox),
                )
            )
        return detections
