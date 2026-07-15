from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


# Canonical COCO vehicle classes used by TrafficFlow
COCO_VEHICLE_NAMES = {"car", "motorcycle", "bus", "truck"}
COCO_VEHICLE_IDS = [2, 3, 5, 7]  # COCO: 2=car, 3=motorcycle, 5=bus, 7=truck

# Aliases (legacy configs may use "motorbike" → map to motorcycle)
_CLASS_ALIASES = {"motorbike": "motorcycle"}


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
        confidence: float = 0.1,
        device: Optional[str] = None,
        imgsz: int = 640,
        half: bool = False,
        class_ids: Optional[Sequence[int]] = None,
        class_name_map: Optional[dict[int, str]] = None,
    ):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'ultralytics'. Install it to run Phase B: "
                "python -m pip install ultralytics"
            ) from exc

        self.model = YOLO(model_path)
        if classes is not None:
            self.classes = {_CLASS_ALIASES.get(c, c) for c in classes} & COCO_VEHICLE_NAMES
        else:
            self.classes = set(COCO_VEHICLE_NAMES)
        self.confidence = confidence
        self.device = device
        self.imgsz = imgsz
        self.half = half
        self.class_ids = list(class_ids) if class_ids else COCO_VEHICLE_IDS
        self.class_name_map = class_name_map or {}
        # Apply half precision on model itself (newer ultralytics API)
        if self.half and self.device and self.device != "cpu":
            try:
                self.model.model.half()
            except Exception:
                pass

    def detect_and_track(self, frame) -> List[Detection]:
        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=self.confidence,
            device=self.device,
            classes=self.class_ids,
            imgsz=self.imgsz,
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
            class_name = self.class_name_map.get(class_id_int, str(names.get(class_id_int, class_id_int)))
            class_name = _CLASS_ALIASES.get(class_name, class_name)
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
