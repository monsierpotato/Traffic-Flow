from argparse import Namespace

from benchmark.detection_eval import _operating_metrics, _summarize


def test_operating_metrics_matches_one_prediction_per_gt():
    gt_by_key = {
        ("SYN", 1): [
            {"class_name": "car", "bbox_xyxy": (0, 0, 10, 10)},
            {"class_name": "truck", "bbox_xyxy": (20, 20, 40, 40)},
        ]
    }
    predictions = [
        {"sequence_id": "SYN", "frame_num": 1, "class_name": "car", "confidence": 0.9, "bbox_xyxy": (0, 0, 10, 10)},
        {"sequence_id": "SYN", "frame_num": 1, "class_name": "truck", "confidence": 0.9, "bbox_xyxy": (20, 20, 40, 40)},
        {"sequence_id": "SYN", "frame_num": 1, "class_name": "truck", "confidence": 0.8, "bbox_xyxy": (60, 60, 80, 80)},
    ]

    metrics = _operating_metrics(predictions, gt_by_key, threshold=0.4, iou_threshold=0.5, frame_count=1)

    assert metrics["tp"] == 2
    assert metrics["fp"] == 1
    assert metrics["fn"] == 0
    assert metrics["per_class"]["car"]["recall"] == 1.0
    assert metrics["per_class"]["truck"]["precision"] == 0.5


def test_summarize_reports_per_class_ap():
    gt_by_key = {("SYN", 1): [{"class_name": "car", "bbox_xyxy": (0, 0, 10, 10)}]}
    predictions = [
        {"sequence_id": "SYN", "frame_num": 1, "class_name": "car", "confidence": 0.9, "bbox_xyxy": (0, 0, 10, 10)}
    ]
    args = Namespace(
        imgsz=640,
        device="cpu",
        frame_stride=1,
        max_frames_per_sequence=0,
        confidence_floor=0.001,
        operating_threshold=0.4,
        iou_threshold=0.5,
    )

    summary = _summarize(predictions, gt_by_key, [10.0, 20.0], 1, args, __import__("pathlib").Path("model.pt"), "run", "development")

    assert summary["ap50"] > 0.99
    assert summary["per_class_ap50"]["car"] > 0.99
    assert summary["per_class_ap50"]["bus"] is None
