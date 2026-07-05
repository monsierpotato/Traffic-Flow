from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from tfengine.geometry import Point, Segment


@dataclass(frozen=True)
class LaneConfig:
    lane_id: str
    counting_line: Segment
    valid_zone: Optional[List[Point]] = None
    direction: Optional[Segment] = None
    segment_ratio: Optional[Tuple[float, float]] = None
    class_allowed: Optional[List[str]] = None


@dataclass(frozen=True)
class CounterSettings:
    movement_threshold_px: float = 5.0
    cooldown_frames: int = 12
    cooldown_distance_px: float = 32.0
    zone_policy: str = "flexible"


@dataclass(frozen=True)
class CounterConfig:
    method: str
    lanes: List[LaneConfig]
    settings: CounterSettings


def _point(raw: Any) -> Point:
    return (float(raw[0]), float(raw[1]))


def _segment(raw: Any) -> Segment:
    return (_point(raw[0]), _point(raw[1]))


def parse_counter_config(raw: Dict[str, Any]) -> CounterConfig:
    settings_raw = raw.get("settings", {})
    settings = CounterSettings(
        movement_threshold_px=float(settings_raw.get("movement_threshold_px", 5.0)),
        cooldown_frames=int(settings_raw.get("cooldown_frames", 12)),
        cooldown_distance_px=float(settings_raw.get("cooldown_distance_px", 32.0)),
        zone_policy=str(settings_raw.get("zone_policy", "flexible")),
    )

    lanes = []
    for lane in raw.get("lanes", []):
        lanes.append(
            LaneConfig(
                lane_id=str(lane["lane_id"]),
                counting_line=_segment(lane["counting_line"]),
                valid_zone=[_point(p) for p in lane["valid_zone"]] if lane.get("valid_zone") else None,
                direction=_segment(lane["direction"]) if lane.get("direction") else None,
                segment_ratio=tuple(lane["segment_ratio"]) if lane.get("segment_ratio") else None,
                class_allowed=list(lane.get("class_allowed", [])) or None,
            )
        )

    return CounterConfig(method=str(raw["method"]), lanes=lanes, settings=settings)
