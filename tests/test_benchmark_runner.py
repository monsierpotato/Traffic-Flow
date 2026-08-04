import argparse
import json
from pathlib import Path

import pytest

from benchmark.run import run


def test_runner_refuses_non_empty_output(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "file.txt").write_text("x", encoding="utf-8")
    args = argparse.Namespace(
        protocol=Path("benchmark/configs/benchmark_protocol_v1.yaml"),
        split_file=Path("benchmark/splits/ua_detrac_split_v1.json"),
        split="smoke_test",
        sequences=None,
        model=Path("models/yolo11m.pt"),
        config=Path("benchmark/configs/runs/yolo11m_640.yaml"),
        imgsz=640,
        confidence=0.4,
        iou=0.45,
        geometry_dir=Path("benchmark/configs/geometry"),
        derived_events_dir=Path("benchmark/ground_truth/derived_events"),
        output=output,
        max_sequences=1,
        max_frames=1,
        backend="derived_gt_smoke",
    )

    with pytest.raises(FileExistsError):
        run(args)


def test_phase03_smoke_manifest_has_required_artifacts(tmp_path):
    output = tmp_path / "phase03-smoke-test"
    args = argparse.Namespace(
        protocol=Path("benchmark/configs/benchmark_protocol_v1.yaml"),
        split_file=Path("benchmark/splits/ua_detrac_split_v1.json"),
        split="smoke_test",
        sequences=None,
        model=Path("models/yolo11m.pt"),
        config=Path("benchmark/configs/runs/yolo11m_640.yaml"),
        imgsz=640,
        confidence=0.4,
        iou=0.45,
        geometry_dir=Path("benchmark/configs/geometry"),
        derived_events_dir=Path("benchmark/ground_truth/derived_events"),
        output=output,
        max_sequences=1,
        max_frames=5,
        backend="derived_gt_smoke",
    )

    summary = run(args)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert summary["sequence_count"] == 1
    assert manifest["schema_version"] == 1
    assert manifest["dataset_split"] == "ua_detrac_split_v1"
    assert manifest["geometry_versions"]["MVI_20011"] == "MVI_20011-geometry-v1"
    assert (output / "raw_detections/MVI_20011.jsonl").exists()
    assert (output / "raw_tracks/MVI_20011.jsonl").exists()
    assert (output / "raw_counting_events/MVI_20011.jsonl").exists()
    assert (output / "config_snapshot/benchmark_protocol_v1.yaml").exists()
