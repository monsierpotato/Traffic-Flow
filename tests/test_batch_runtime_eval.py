from argparse import Namespace

import pytest

from benchmark.batch_runtime_eval import _classify_duration_kind, _parse_variants, _percentile, _selected_workloads


def test_percentile_interpolates_sorted_values():
    assert _percentile([10, 20, 30], 0.5) == 20
    assert _percentile([10, 20, 30], 0.95) == pytest.approx(29)


def test_parse_variants_rejects_unknown_name():
    assert _parse_variants("bytetrack,trafficflow_production") == ["bytetrack", "trafficflow_production"]

    with pytest.raises(ValueError):
        _parse_variants("unknown")


def test_selected_workloads_from_explicit_specs():
    split = {"splits": {}, "selected_sequence_metadata": {}}
    args = Namespace(workloads="short:MVI_20035,extended:development:MVI_40241", bucket="development")

    workloads = _selected_workloads(split, args)

    assert [item.workload_id for item in workloads] == ["short_MVI_20035", "extended_MVI_40241"]
    assert workloads[0].sequence_id == "MVI_20035"
    assert workloads[1].bucket == "development"


def test_selected_workloads_classifies_default_bucket():
    split = {
        "splits": {"development": ["A", "B"]},
        "selected_sequence_metadata": {
            "A": {"frame_count_xml": 800},
            "B": {"frame_count_xml": 5000},
        },
    }
    args = Namespace(workloads=None, bucket="development", sequences=None, max_sequences=1)

    workloads = _selected_workloads(split, args)

    assert len(workloads) == 1
    assert workloads[0].kind == _classify_duration_kind(800 / 25.0)
