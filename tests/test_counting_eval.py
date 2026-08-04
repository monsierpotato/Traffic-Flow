from benchmark.counting_eval import aggregate_metrics, consistency_check, match_events, summarize_scope


def _event(frame, lane="lane_1", cls="car", direction="forward", track_id=1):
    return {
        "video_id": "SYN",
        "lane_id": lane,
        "class_name": cls,
        "direction": direction,
        "crossing_frame": frame,
        "gt_track_id": track_id,
    }


def test_match_events_uses_one_to_one_temporal_matching():
    gt = [_event(100, track_id=1)]
    pred = [_event(102, track_id=1), _event(103, track_id=2)]

    rows = match_events(gt, pred, tolerance_frames=5)

    assert [row["status"] for row in rows].count("tp") == 1
    assert [row["status"] for row in rows].count("fp") == 1
    assert next(row for row in rows if row["status"] == "tp")["frame_error"] == 2
    assert next(row for row in rows if row["status"] == "fp")["error_category"] == "duplicate_count"


def test_match_events_separates_wrong_lane_from_miss():
    gt = [_event(100, lane="lane_1")]
    pred = [_event(101, lane="lane_2")]

    rows = match_events(gt, pred, tolerance_frames=5)

    assert [row["status"] for row in rows].count("fn") == 1
    fp = next(row for row in rows if row["status"] == "fp")
    assert fp["error_category"] == "wrong_lane"


def test_aggregate_summary_reports_wape_and_exact_accuracy():
    gt = [_event(10), _event(20, cls="bus")]
    pred = [_event(10), _event(30), _event(20, cls="bus")]
    matches = match_events(gt, pred, tolerance_frames=1)
    aggregates = aggregate_metrics(gt, pred)

    summary = summarize_scope("run", "development", "overall", "all", matches, aggregates)
    consistency = consistency_check(pred, aggregates)

    assert summary["event_precision"] == 0.666667
    assert summary["event_recall"] == 1.0
    assert summary["wape"] == 0.5
    assert summary["exact_count_accuracy"] == 0.5
    assert consistency["is_consistent"] is True
