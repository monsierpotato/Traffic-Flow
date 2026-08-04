from worker.pipeline.detection_filter import filter_detections_for_tracking


def test_filter_keeps_detection_by_bottom_center_lane_and_class():
    lanes = [{
        "lane_id": "lane_1",
        "valid_zone": [[0, 50], [100, 50], [100, 100], [0, 100]],
        "class_allowed": ["car"],
    }]
    detections = [
        {"bbox_xyxy": [10, 0, 30, 60], "class_name": "car"},
        {"bbox_xyxy": [10, 0, 30, 40], "class_name": "car"},
        {"bbox_xyxy": [10, 0, 30, 60], "class_name": "person"},
    ]

    kept = filter_detections_for_tracking(detections, lanes)

    assert kept == [detections[0]]


def test_filter_allows_configurable_zone_padding():
    lanes = [{
        "lane_id": "lane_1",
        "valid_zone": [[10, 10], [20, 10], [20, 20], [10, 20]],
        "class_allowed": ["motorcycle"],
    }]
    detection = {"bbox_xyxy": [8, 0, 12, 9], "class_name": "motorcycle"}

    assert filter_detections_for_tracking([detection], lanes, padding_px=0) == []
    assert filter_detections_for_tracking([detection], lanes, padding_px=5) == [detection]
