from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from tfengine.cli.config_generator import (
    ConfigSession,
    AnnotationRoi,
    parse_annotation_roi,
    validate_annotation_roi,
)
from tfengine.cli.run_counting import parse_args as counting_parse_args


def test_parse_annotation_roi_valid() -> None:
    roi = parse_annotation_roi("100,200,800,600")
    assert roi.x == 100.0
    assert roi.y == 200.0
    assert roi.width == 800.0
    assert roi.height == 600.0


def test_parse_annotation_roi_wrong_part_count() -> None:
    with pytest.raises(Exception):
        parse_annotation_roi("100,200,800")


def test_parse_annotation_roi_non_numeric() -> None:
    with pytest.raises(Exception):
        parse_annotation_roi("abc,def,800,600")


def test_parse_annotation_roi_zero_dimension() -> None:
    with pytest.raises(Exception):
        parse_annotation_roi("100,200,0,600")


def test_validate_annotation_roi_valid() -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    roi = AnnotationRoi(x=100, y=200, width=800, height=600)
    result = validate_annotation_roi(roi, frame)
    assert result == roi


def test_validate_annotation_roi_exceeds_frame() -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    roi = AnnotationRoi(x=100, y=200, width=2000, height=600)
    with pytest.raises(ValueError, match="ROI exceeds frame bounds"):
        validate_annotation_roi(roi, frame)


def test_validate_annotation_roi_negative_origin() -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    roi = AnnotationRoi(x=-10, y=200, width=800, height=600)
    with pytest.raises(ValueError, match="ROI origin must be non-negative"):
        validate_annotation_roi(roi, frame)


def test_config_session_initialization() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    session = ConfigSession(
        frame=frame,
        output_path=Path("test_output.json"),
        camera_id="test_cam",
        display_max_size=640,
    )

    assert session.camera_id == "test_cam"
    assert session.method == "counting_line_per_lane"
    assert session.lanes == []
    assert session.points == []


def test_config_session_method_switching() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    session = ConfigSession(frame, Path("out.json"), "cam", 640)

    assert session.method == "counting_line_per_lane"
    session.set_method("4")
    assert session.method == "counting_gate"
    assert session.points == []


def test_config_session_save_creates_config(tmp_path: Path) -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    output_path = tmp_path / "config.json"
    session = ConfigSession(frame, output_path, "test_cam", 640)
    session.lanes = [
        {
            "lane_id": "lane_1",
            "counting_line": [[0, 10], [20, 10]],
            "class_allowed": ["car"],
        }
    ]
    session.save()

    assert output_path.exists()
    import json

    config = json.loads(output_path.read_text(encoding="utf-8"))
    assert config["camera_id"] == "test_cam"
    assert config["method"] == "counting_line_per_lane"
    assert len(config["lanes"]) == 1
    assert config["lanes"][0]["lane_id"] == "lane_1"
    assert "resolution" in config
    assert config["resolution"]["width"] == 640
    assert config["resolution"]["height"] == 480


def test_counting_parse_args_minimal() -> None:
    import sys

    test_args = ["run_counting", "--video", "test.mp4", "--config", "config.json"]
    old_argv = sys.argv
    try:
        sys.argv = test_args
        args = counting_parse_args()
        assert args.video == Path("test.mp4")
        assert args.config == Path("config.json")
        assert args.model == "models/yolov8n.pt"
        assert args.conf == 0.25
    finally:
        sys.argv = old_argv
