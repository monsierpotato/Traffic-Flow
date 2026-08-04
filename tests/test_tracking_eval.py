from benchmark.tracking_eval import IouOnlyTracker, _xyxy_to_xywh


def test_iou_only_tracker_preserves_id_for_overlapping_boxes():
    tracker = IouOnlyTracker(match_threshold=0.3, track_buffer=2)

    first = tracker.update([{"bbox_xyxy": [0, 0, 20, 20], "class_name": "car", "confidence": 1.0}])
    second = tracker.update([{"bbox_xyxy": [2, 0, 22, 20], "class_name": "car", "confidence": 1.0}])

    assert first[0]["track_id"] == second[0]["track_id"]


def test_iou_only_tracker_starts_new_id_for_class_mismatch():
    tracker = IouOnlyTracker(match_threshold=0.3, track_buffer=2)

    first = tracker.update([{"bbox_xyxy": [0, 0, 20, 20], "class_name": "car", "confidence": 1.0}])
    second = tracker.update([{"bbox_xyxy": [0, 0, 20, 20], "class_name": "bus", "confidence": 1.0}])

    assert first[0]["track_id"] != second[0]["track_id"]


def test_xyxy_to_xywh_clamps_negative_size():
    assert _xyxy_to_xywh([10, 20, 25, 45]) == (10.0, 20.0, 15.0, 25.0)
    assert _xyxy_to_xywh([10, 20, 5, 15]) == (10.0, 20.0, 0.0, 0.0)
