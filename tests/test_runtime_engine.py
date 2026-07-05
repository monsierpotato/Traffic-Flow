from __future__ import annotations

import json

import cv2
import pytest

from tfengine.core_ai.detector import Detection
from tfengine.runtime import engine
from tfengine.runtime.engine import (
    TrafficFlowEngine,
    VideoCountingProgress,
    VideoCountingRequest,
    VideoCountingResult,
    _effective_total_frames,
    _emit_progress,
    _progress_percent,
    _should_report_progress,
    _total_count,
    scale_config_to_video,
)


class FakeDetector:
    def __init__(self, *_args, **_kwargs):
        self.calls = 0

    def detect_and_track(self, _frame):
        self.calls += 1
        y = 8 if self.calls == 1 else 12
        return [
            Detection(
                track_id=1,
                class_id=2,
                class_name="car",
                confidence=0.9,
                bbox_xyxy=(9, y - 2, 11, y),
            )
        ]


# ── VideoCountingResult ──────────────────────────────────────────────


def test_video_counting_result_dict_includes_api_ready_output_fields() -> None:
    result = VideoCountingResult(
        frames=3,
        total_frames=5,
        counts={"lane_1": {"car": 2}, "lane_2": {"bus": 1}},
    )

    assert result.to_dict() == {
        "status": "completed",
        "frames": 3,
        "total_frames": 5,
        "counts": {"lane_1": {"car": 2}, "lane_2": {"bus": 1}},
        "total_count": 3,
        "outputs": {"video_path": None, "events_jsonl_path": None},
    }


def test_video_counting_result_empty_counts() -> None:
    result = VideoCountingResult(frames=0, total_frames=0, counts={})

    d = result.to_dict()
    assert d["total_count"] == 0
    assert d["counts"] == {}


def test_video_counting_result_with_output_paths() -> None:
    result = VideoCountingResult(
        frames=10,
        total_frames=10,
        counts={"lane_1": {"car": 5}},
        output_video_path="out.mp4",
        output_jsonl_path="events.jsonl",
    )

    d = result.to_dict()
    assert d["outputs"]["video_path"] == "out.mp4"
    assert d["outputs"]["events_jsonl_path"] == "events.jsonl"


def test_video_counting_result_custom_status() -> None:
    result = VideoCountingResult(
        frames=5, total_frames=10, counts={}, status="failed"
    )

    assert result.to_dict()["status"] == "failed"


# ── _total_count ─────────────────────────────────────────────────────


def test_total_count_single_lane() -> None:
    assert _total_count({"lane_1": {"car": 5, "bus": 3}}) == 8


def test_total_count_multiple_lanes() -> None:
    assert _total_count({"lane_1": {"car": 2}, "lane_2": {"bus": 3}, "lane_3": {"truck": 1}}) == 6


def test_total_count_empty() -> None:
    assert _total_count({}) == 0


def test_total_count_empty_lanes() -> None:
    assert _total_count({"lane_1": {}, "lane_2": {}}) == 0


# ── _effective_total_frames ──────────────────────────────────────────


def test_effective_total_frames_no_limit() -> None:
    assert _effective_total_frames(100, None) == 100


def test_effective_total_frames_with_limit() -> None:
    assert _effective_total_frames(100, 50) == 50


def test_effective_total_frames_limits_exceeds_video() -> None:
    assert _effective_total_frames(30, 50) == 30


def test_effective_total_frames_zero_video_total() -> None:
    assert _effective_total_frames(0, None) is None


def test_effective_total_frames_zero_video_with_limit() -> None:
    assert _effective_total_frames(0, 10) == 10


# ── _progress_percent ────────────────────────────────────────────────


def test_progress_percent_halfway() -> None:
    assert _progress_percent(50, 100) == 50.0


def test_progress_percent_complete() -> None:
    assert _progress_percent(100, 100) == 100.0


def test_progress_percent_zero_total() -> None:
    assert _progress_percent(50, 0) is None


def test_progress_percent_none_total() -> None:
    assert _progress_percent(50, None) is None


def test_progress_percent_caps_at_100() -> None:
    assert _progress_percent(120, 100) == 100.0


# ── _should_report_progress ──────────────────────────────────────────


def test_should_report_progress_none_progress() -> None:
    assert _should_report_progress(None, 0.0, 5.0) is False


def test_should_report_progress_at_100() -> None:
    assert _should_report_progress(100.0, 0.0, 5.0) is False


def test_should_report_progress_below_interval() -> None:
    assert _should_report_progress(3.0, 0.0, 5.0) is False


def test_should_report_progress_above_interval() -> None:
    assert _should_report_progress(7.0, 0.0, 5.0) is True


def test_should_report_progress_exact_interval() -> None:
    assert _should_report_progress(10.0, 5.0, 5.0) is True


# ── _emit_progress ───────────────────────────────────────────────────


def test_emit_progress_no_callback() -> None:
    _emit_progress(None, status="started", frame_index=0, frames_processed=0, total_frames=100, progress=0.0)


def test_emit_progress_with_callback() -> None:
    collected = []

    _emit_progress(
        collected.append,
        status="started",
        frame_index=0,
        frames_processed=0,
        total_frames=100,
        progress=0.0,
    )

    assert len(collected) == 1
    payload = collected[0]
    assert payload["status"] == "started"
    assert payload["frame_index"] == 0
    assert payload["progress"] == 0.0


# ── scale_config_to_video ────────────────────────────────────────────


def test_scale_config_no_resolution() -> None:
    config = {"method": "counting_line_per_lane", "lanes": []}
    assert scale_config_to_video(config, 1920, 1080) == config


def test_scale_config_matching_resolution() -> None:
    config = {"resolution": {"width": 640, "height": 480}, "lanes": []}
    assert scale_config_to_video(config, 640, 480) == config


def test_scale_config_scales_geometry() -> None:
    config = {
        "resolution": {"width": 100, "height": 100},
        "lanes": [
            {
                "lane_id": "lane_1",
                "counting_line": [[0, 10], [50, 10]],
                "valid_zone": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "direction": [[50, 0], [50, 100]],
            }
        ],
    }

    scaled = scale_config_to_video(config, 200, 200)

    assert scaled["resolution"] == {"width": 200, "height": 200}
    lane = scaled["lanes"][0]
    assert lane["counting_line"] == [[0.0, 20.0], [100.0, 20.0]]
    assert lane["valid_zone"] == [[0.0, 0.0], [200.0, 0.0], [200.0, 200.0], [0.0, 200.0]]
    assert lane["direction"] == [[100.0, 0.0], [100.0, 200.0]]


def test_scale_config_invalid_resolution() -> None:
    config = {"resolution": {"width": 0, "height": 100}, "lanes": []}
    with pytest.raises(ValueError, match="Invalid config resolution"):
        scale_config_to_video(config, 200, 200)


def test_scale_config_negative_resolution() -> None:
    config = {"resolution": {"width": -100, "height": 100}, "lanes": []}
    with pytest.raises(ValueError, match="Invalid config resolution"):
        scale_config_to_video(config, 200, 200)


# ── process_video ────────────────────────────────────────────────────


def test_process_video_smoke_with_fake_detector(tmp_path, monkeypatch) -> None:
    video_path = tmp_path / "input.mp4"
    config_path = tmp_path / "config.json"
    events_path = tmp_path / "events.jsonl"
    output_video_path = tmp_path / "counted.mp4"

    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10,
        (32, 24),
    )
    assert writer.isOpened()
    for _ in range(2):
        writer.write(_black_frame(width=32, height=24))
    writer.release()

    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "camera_id": "test_camera",
                "resolution": {"width": 32, "height": 24},
                "method": "counting_line_per_lane",
                "settings": {"movement_threshold_px": 1},
                "lanes": [
                    {
                        "lane_id": "lane_1",
                        "counting_line": [[0, 10], [31, 10]],
                        "class_allowed": ["car"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(engine, "YoloByteTrackDetector", FakeDetector)

    progress = []
    result = TrafficFlowEngine().process_video(
        VideoCountingRequest(
            video_path=video_path,
            config_path=config_path,
            max_frames=2,
            output_video_path=output_video_path,
            output_jsonl_path=events_path,
            progress_callback=progress.append,
            progress_interval_percent=1,
        )
    )

    assert result.to_dict()["counts"] == {"lane_1": {"car": 1}}
    assert result.to_dict()["total_count"] == 1
    assert output_video_path.exists()
    assert events_path.read_text(encoding="utf-8").strip()
    assert progress[0]["status"] == "started"
    assert progress[-1]["status"] == "completed"


def test_process_video_no_output_paths(tmp_path, monkeypatch) -> None:
    video_path = tmp_path / "input.mp4"
    config_path = tmp_path / "config.json"

    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (16, 12),
    )
    for _ in range(1):
        writer.write(_black_frame(width=16, height=12))
    writer.release()

    config_path.write_text(
        json.dumps({
            "version": 1, "camera_id": "test_camera",
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1},
            "lanes": [{"lane_id": "lane_1", "counting_line": [[0, 6], [15, 6]], "class_allowed": ["car"]}],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(engine, "YoloByteTrackDetector", FakeDetector)

    result = TrafficFlowEngine().process_video(
        VideoCountingRequest(
            video_path=video_path,
            config_path=config_path,
            max_frames=1,
        )
    )

    assert result.to_dict()["total_count"] == 0
    assert result.frames == 1


def test_process_video_max_frames_zero(tmp_path, monkeypatch) -> None:
    video_path = tmp_path / "input.mp4"
    config_path = tmp_path / "config.json"

    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (16, 12),
    )
    for _ in range(5):
        writer.write(_black_frame(width=16, height=12))
    writer.release()

    config_path.write_text(
        json.dumps({
            "version": 1, "camera_id": "test_camera",
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1},
            "lanes": [{"lane_id": "lane_1", "counting_line": [[0, 6], [15, 6]], "class_allowed": ["car"]}],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(engine, "YoloByteTrackDetector", FakeDetector)

    result = TrafficFlowEngine().process_video(
        VideoCountingRequest(video_path=video_path, config_path=config_path, max_frames=0)
    )

    assert result.frames == 0


def test_process_video_missing_video_raises_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(engine, "YoloByteTrackDetector", FakeDetector)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"method": "counting_line_per_lane", "lanes": []}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Could not open video"):
        TrafficFlowEngine().process_video(
            VideoCountingRequest(
                video_path=tmp_path / "nonexistent.mp4",
                config_path=config_path,
            )
        )


def test_video_counting_progress_to_dict() -> None:
    progress = VideoCountingProgress(
        status="processing", frame_index=42, frames_processed=43, total_frames=100, progress=43.0
    )

    d = progress.to_dict()
    assert d["status"] == "processing"
    assert d["frame_index"] == 42
    assert d["frames_processed"] == 43
    assert d["total_frames"] == 100
    assert d["progress"] == 43.0


def _black_frame(*, width: int, height: int):
    import numpy as np

    return np.zeros((height, width, 3), dtype=np.uint8)
