from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


Point = Tuple[int, int]


@dataclass
class RuntimeInfo:
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    postprocess_ms: float = 0.0
    total_ms: float = 0.0
    fps: float = 0.0


@dataclass
class Lane:
    lane_id: int
    points: List[Point]
    confidence: Optional[float] = None
    type: str = "polyline"


@dataclass
class LaneFrameResult:
    video_id: str
    frame_id: int
    method: str
    lanes: List[Lane] = field(default_factory=list)
    runtime: RuntimeInfo = field(default_factory=RuntimeInfo)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
