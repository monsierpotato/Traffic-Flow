from __future__ import annotations

import json

import cv2

from trafficflow.core_ai.detector import Detection
from trafficflow.runtime import engine
from trafficflow.runtime.engine import TrafficFlowEngine, VideoCountingRequest, VideoCountingResult


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


def _black_frame(*, width: int, height: int):
    import numpy as np

    return np.zeros((height, width, 3), dtype=np.uint8)
