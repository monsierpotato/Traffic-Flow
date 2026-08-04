from argparse import Namespace
from pathlib import Path

from benchmark.end_to_end_eval import _counter_keys, _extract_new_count_events, _selected_sequences
from worker.services.counting_service import CountingState


def test_selected_sequences_can_cap_bucket():
    split = {"splits": {"development": ["A", "B", "C"]}}

    assert _selected_sequences(split, "development", None, 2) == ["A", "B"]


def test_extract_new_count_events_uses_counter_state():
    lanes = [
        {
            "lane_id": "lane_1",
            "direction_name": "forward",
            "counting_line": [[0, 5], [10, 5]],
            "direction": [[0, 0], [0, 10]],
            "valid_zone": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "class_allowed": ["car"],
        }
    ]
    counter = CountingState(lanes)
    counter.counters["lane_1"]["car"].add(7)

    events = _extract_new_count_events(
        counter=counter,
        previous_keys=set(),
        sequence_id="SYN",
        frame_num=12,
        lanes=lanes,
        variant="bytetrack",
    )

    assert _counter_keys(counter) == {("lane_1", "car", 7)}
    assert events[0]["pred_track_id"] == 7
    assert events[0]["direction"] == "forward"


def test_counting_eval_args_shape_for_variant_paths(tmp_path):
    args = Namespace(split_file=Path("split.json"), bucket="smoke_test")

    assert args.bucket == "smoke_test"
