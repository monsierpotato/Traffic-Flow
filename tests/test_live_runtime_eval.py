import pytest

from benchmark.live_runtime_eval import _parse_size_mb, _percentile, _stall_metrics


def test_percentile_interpolates_values():
    assert _percentile([1, 2, 3, 4], 0.5) == 2.5
    assert _percentile([10, 20, 30], 0.95) == pytest.approx(29)


def test_parse_size_mb_handles_docker_units():
    assert _parse_size_mb("512MiB / 15.6GiB") == 512
    assert _parse_size_mb("1.5GiB / 15.6GiB") == 1536
    assert _parse_size_mb("250MB / 16GB") == 250


def test_stall_metrics_counts_consecutive_no_progress_after_threshold():
    rows = [
        {"elapsed_s": 60, "status": "running", "sample_dt_s": 0, "processed_delta": 1},
        {"elapsed_s": 65, "status": "running", "sample_dt_s": 5, "processed_delta": 0},
        {"elapsed_s": 70, "status": "running", "sample_dt_s": 5, "processed_delta": 0},
        {"elapsed_s": 75, "status": "running", "sample_dt_s": 5, "processed_delta": 0},
        {"elapsed_s": 80, "status": "running", "sample_dt_s": 5, "processed_delta": 2},
    ]

    metrics = _stall_metrics(rows, warmup_s=60, threshold_s=15)

    assert metrics["stall_count"] == 1
    assert metrics["total_stall_duration_s"] == 5
