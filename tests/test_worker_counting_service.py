from worker.services.counting_service import CountingState


def _lane():
    return {
        "lane_id": "lane_1",
        "valid_zone": [[0, 0], [100, 0], [100, 100], [0, 100]],
        "counting_line": [[0, 50], [100, 50]],
        "direction": [[50, 10], [50, 90]],
        "class_allowed": ["car", "motorcycle"],
    }


def _det(track_id, bbox, cls="car", lost=0, is_lost=False):
    return {
        "track_id": track_id,
        "bbox_xyxy": bbox,
        "class_name": cls,
        "confidence": 0.9,
        "kalman_velocity": (0, 10),
        "lost_frames": lost,
        "is_lost": is_lost,
    }


def test_bottom_center_crossing_counts_after_lane_lock():
    state = CountingState([_lane()])
    # bottom-center moves from y=35 to y=65, crossing y=50 after lane lock/min age.
    for bbox in ([40, 10, 60, 35], [40, 15, 60, 45], [40, 25, 60, 55], [40, 35, 60, 65]):
        state.process_detections([_det(1, bbox)])
    assert state.get_total_count() == 1
    assert state.get_statistics()[0]["vehicle_type"] == "car"


def test_lost_tracks_are_not_counted():
    state = CountingState([_lane()])
    for bbox in ([40, 10, 60, 35], [40, 15, 60, 45], [40, 25, 60, 55], [40, 35, 60, 65]):
        state.process_detections([_det(2, bbox, lost=1, is_lost=True)])
    assert state.get_total_count() == 0


def test_wrong_direction_is_not_counted():
    state = CountingState([_lane()])
    # Moves upward across the line while lane direction points downward.
    for bbox in ([40, 60, 60, 80], [40, 45, 60, 65], [40, 35, 60, 55], [40, 20, 60, 40]):
        state.process_detections([_det(3, bbox)])
    assert state.get_total_count() == 0
