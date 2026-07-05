from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from tfengine.geometry import (
    Point,
    Segment,
    distance,
    dot_direction,
    point_in_polygon,
    segment_midpoint_in_polygon,
    segments_intersect,
)

from .config import CounterConfig, LaneConfig, parse_counter_config


@dataclass(frozen=True)
class TrackObservation:
    track_id: int
    class_name: str
    bbox_xyxy: Tuple[float, float, float, float]
    point: Point


@dataclass(frozen=True)
class CounterEvent:
    frame_index: int
    track_id: int
    lane_id: str
    class_name: str
    point: Point


class TrafficCounter:
    def __init__(self, config: CounterConfig):
        self.config = config
        self.previous_points: Dict[int, Point] = {}
        self.counted_ids: Dict[str, Set[int]] = {lane.lane_id: set() for lane in config.lanes}
        self.counts: Dict[str, Dict[str, int]] = {lane.lane_id: {} for lane in config.lanes}
        self.recent_crossings: Dict[str, List[Tuple[int, Point]]] = {lane.lane_id: [] for lane in config.lanes}

    def update(self, observations: Iterable[TrackObservation], frame_index: int) -> List[CounterEvent]:
        events: List[CounterEvent] = []
        for observation in observations:
            previous = self.previous_points.get(observation.track_id)
            current = observation.point
            self.previous_points[observation.track_id] = current
            if previous is None:
                continue

            movement = (previous, current)
            if distance(previous, current) < self.config.settings.movement_threshold_px:
                continue

            for lane in self.config.lanes:
                if observation.track_id in self.counted_ids[lane.lane_id]:
                    continue
                if not self._passes_lane_filters(lane, observation.class_name, movement, current):
                    continue
                if self._inside_cooldown(lane, frame_index, current):
                    continue

                self.counted_ids[lane.lane_id].add(observation.track_id)
                self.counts[lane.lane_id][observation.class_name] = (
                    self.counts[lane.lane_id].get(observation.class_name, 0) + 1
                )
                self.recent_crossings[lane.lane_id].append((frame_index, current))
                events.append(
                    CounterEvent(
                        frame_index=frame_index,
                        track_id=observation.track_id,
                        lane_id=lane.lane_id,
                        class_name=observation.class_name,
                        point=current,
                    )
                )
        self._prune_cooldowns(frame_index)
        return events

    def _passes_lane_filters(
        self,
        lane: LaneConfig,
        class_name: str,
        movement: Segment,
        current: Point,
    ) -> bool:
        if lane.class_allowed and class_name not in lane.class_allowed:
            return False
        if not segments_intersect(movement, lane.counting_line):
            return False
        if lane.valid_zone and not self._passes_zone(lane, movement, current):
            return False
        if lane.direction and dot_direction(movement, lane.direction) <= 0:
            return False
        return True

    def _passes_zone(self, lane: LaneConfig, movement: Segment, current: Point) -> bool:
        assert lane.valid_zone is not None
        if self.config.settings.zone_policy == "strict":
            return point_in_polygon(current, lane.valid_zone)
        return point_in_polygon(current, lane.valid_zone) or segment_midpoint_in_polygon(movement, lane.valid_zone)

    def _inside_cooldown(self, lane: LaneConfig, frame_index: int, point: Point) -> bool:
        for previous_frame, previous_point in self.recent_crossings[lane.lane_id]:
            if frame_index - previous_frame <= self.config.settings.cooldown_frames:
                if distance(previous_point, point) <= self.config.settings.cooldown_distance_px:
                    return True
        return False

    def _prune_cooldowns(self, frame_index: int) -> None:
        keep_after = frame_index - self.config.settings.cooldown_frames
        for lane_id, crossings in self.recent_crossings.items():
            self.recent_crossings[lane_id] = [(idx, point) for idx, point in crossings if idx >= keep_after]


def build_counter(raw_config: dict) -> TrafficCounter:
    return TrafficCounter(parse_counter_config(raw_config))
