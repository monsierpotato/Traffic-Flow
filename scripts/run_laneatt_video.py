import argparse
import csv
import json
import sys
import time
import warnings
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml

from lane_schema import Lane, LaneFrameResult, RuntimeInfo
from visualize_overlay import draw_lanes


def add_repo_to_path(repo_path):
    repo_path = Path(repo_path).resolve()
    if str(repo_path) not in sys.path:
        sys.path.insert(0, str(repo_path))


def percentile(values, q):
    return float(np.percentile(values, q)) if values else 0.0


def load_config(config_path):
    settings = {
        "backbone": "resnet18",
        "S": 72,
        "topk_anchors": 1000,
        "anchors_freq_path": "data/tusimple_anchors_freq.pt",
        "img_h": 360,
        "img_w": 640,
        "normalize": False,
        "conf_threshold": 0.2,
        "nms_thres": 45.0,
        "nms_topk": 5,
    }

    if not config_path:
        return settings

    config_path = Path(config_path)
    if not config_path.exists():
        return settings

    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)

    model_params = cfg.get("model", {}).get("parameters", {})
    dataset_params = cfg.get("datasets", {}).get("test", {}).get("parameters", {})
    test_params = cfg.get("test_parameters", {})
    img_size = dataset_params.get("img_size", [settings["img_h"], settings["img_w"]])

    settings.update(
        {
            "backbone": model_params.get("backbone", settings["backbone"]),
            "S": model_params.get("S", settings["S"]),
            "topk_anchors": model_params.get("topk_anchors", settings["topk_anchors"]),
            "anchors_freq_path": model_params.get("anchors_freq_path", settings["anchors_freq_path"]),
            "img_h": model_params.get("img_h", img_size[0]),
            "img_w": model_params.get("img_w", img_size[1]),
            "normalize": dataset_params.get("normalize", settings["normalize"]),
            "conf_threshold": test_params.get("conf_threshold", settings["conf_threshold"]),
            "nms_thres": test_params.get("nms_thres", settings["nms_thres"]),
            "nms_topk": test_params.get("nms_topk", settings["nms_topk"]),
        }
    )
    return settings


class LaneATTVideoRunner:
    def __init__(self, repo_path, weight_path, config_path=None, device="cuda", conf_threshold=None):
        self.repo_path = Path(repo_path).resolve()
        add_repo_to_path(self.repo_path)
        from lib.models.laneatt import LaneATT

        self.settings = load_config(config_path)
        if conf_threshold is not None:
            self.settings["conf_threshold"] = conf_threshold

        anchors_freq_path = Path(self.settings["anchors_freq_path"])
        if not anchors_freq_path.is_absolute():
            anchors_freq_path = self.repo_path / anchors_freq_path

        self.input_h = int(self.settings["img_h"])
        self.input_w = int(self.settings["img_w"])
        self.normalize = bool(self.settings["normalize"])
        self.conf_threshold = float(self.settings["conf_threshold"])
        self.nms_thres = float(self.settings["nms_thres"])
        self.nms_topk = int(self.settings["nms_topk"])
        self.device = torch.device(device if device == "cuda" and torch.cuda.is_available() else "cpu")

        warnings.filterwarnings("ignore", category=UserWarning, module="torchvision.models._utils")
        self.model = LaneATT(
            backbone=self.settings["backbone"],
            pretrained_backbone=False,
            S=int(self.settings["S"]),
            topk_anchors=int(self.settings["topk_anchors"]),
            anchors_freq_path=str(anchors_freq_path),
            img_h=self.input_h,
            img_w=self.input_w,
        ).to(self.device)

        checkpoint = torch.load(weight_path, map_location="cpu")
        state_dict = checkpoint["model"] if isinstance(checkpoint, dict) and "model" in checkpoint else checkpoint
        state_dict = {key[7:] if key.startswith("module.") else key: value for key, value in state_dict.items()}
        load_result = self.model.load_state_dict(state_dict, strict=False)
        if load_result.missing_keys or load_result.unexpected_keys:
            raise RuntimeError(
                "Checkpoint does not match the LaneATT model. "
                f"Missing keys: {load_result.missing_keys[:5]}, "
                f"unexpected keys: {load_result.unexpected_keys[:5]}"
            )
        self.model.eval()

    def infer(self, frame, video_id, frame_id):
        image_height, image_width = frame.shape[:2]

        preprocess_start = time.perf_counter()
        tensor = self._preprocess(frame)
        preprocess_ms = (time.perf_counter() - preprocess_start) * 1000.0

        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        inference_start = time.perf_counter()
        with torch.no_grad():
            proposals = self.model(
                tensor,
                conf_threshold=self.conf_threshold,
                nms_thres=self.nms_thres,
                nms_topk=self.nms_topk,
            )
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        inference_ms = (time.perf_counter() - inference_start) * 1000.0

        postprocess_start = time.perf_counter()
        lanes = self._decode_lanes(proposals, image_width, image_height)
        postprocess_ms = (time.perf_counter() - postprocess_start) * 1000.0
        total_ms = preprocess_ms + inference_ms + postprocess_ms

        return LaneFrameResult(
            video_id=video_id,
            frame_id=frame_id,
            method="LaneATT-ResNet18-TuSimple",
            lanes=lanes,
            runtime=RuntimeInfo(
                preprocess_ms=preprocess_ms,
                inference_ms=inference_ms,
                postprocess_ms=postprocess_ms,
                total_ms=total_ms,
                fps=1000.0 / total_ms if total_ms > 0 else 0.0,
            ),
            meta={
                "image_width": image_width,
                "image_height": image_height,
                "input_width": self.input_w,
                "input_height": self.input_h,
                "device": self.device.type,
                "confidence_threshold": self.conf_threshold,
                "nms_threshold": self.nms_thres,
                "nms_topk": self.nms_topk,
            },
        )

    def _preprocess(self, frame):
        resized = cv2.resize(frame, (self.input_w, self.input_h), interpolation=cv2.INTER_LINEAR)
        image = resized.astype(np.float32) / 255.0
        chw = np.transpose(image, (2, 0, 1))
        tensor = torch.from_numpy(np.ascontiguousarray(chw)).unsqueeze(0).to(self.device)
        return tensor

    def _decode_lanes(self, proposals, image_width, image_height):
        decoded = self.model.decode(proposals, as_lanes=True)[0]
        lanes = []
        for lane_obj in decoded:
            points_norm = lane_obj.points
            if len(points_norm) < 2:
                continue
            points = [
                (
                    int(round(float(x) * (image_width - 1))),
                    int(round(float(y) * (image_height - 1))),
                )
                for x, y in points_norm
                if 0.0 <= float(x) <= 1.0 and 0.0 <= float(y) <= 1.0
            ]
            if len(points) < 2:
                continue
            confidence = lane_obj.metadata.get("conf")
            if hasattr(confidence, "item"):
                confidence = float(confidence.item())
            elif confidence is not None:
                confidence = float(confidence)
            lanes.append(
                {
                    "confidence": confidence,
                    "points": points,
                    "sort_x": float(np.mean([p[0] for p in points])),
                }
            )

        lanes.sort(key=lambda item: item["sort_x"])
        return [
            Lane(lane_id=index + 1, confidence=item["confidence"], points=item["points"])
            for index, item in enumerate(lanes)
        ]


def run_video(runner, video_path, output_video, output_csv, output_jsonl, warmup=5, max_frames=None):
    video_path = Path(video_path)
    output_video = Path(output_video)
    output_csv = Path(output_csv)
    output_jsonl = Path(output_jsonl)
    output_video.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open video writer: {output_video}")

    latencies = []
    inference_latencies = []
    frame_id = 0
    video_id = video_path.stem

    with output_jsonl.open("w", encoding="utf-8") as jsonl:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if max_frames is not None and frame_id >= max_frames:
                break

            result = runner.infer(frame, video_id=video_id, frame_id=frame_id)
            if frame_id >= warmup:
                latencies.append(result.runtime.total_ms)
                inference_latencies.append(result.runtime.inference_ms)

            frame = draw_lanes(frame, [lane.__dict__ for lane in result.lanes])
            writer.write(np.ascontiguousarray(frame))
            jsonl.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
            frame_id += 1

    cap.release()
    writer.release()
    output_video_size = output_video.stat().st_size if output_video.exists() else 0

    avg_total_ms = sum(latencies) / max(len(latencies), 1)
    avg_inference_ms = sum(inference_latencies) / max(len(inference_latencies), 1)
    bench_fps = 1000.0 / avg_total_ms if avg_total_ms > 0 else 0.0
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer_csv = csv.writer(f)
        writer_csv.writerow(
            [
                "method",
                "video",
                "frames",
                "avg_latency_ms",
                "avg_inference_ms",
                "p50_latency_ms",
                "p95_latency_ms",
                "fps",
            ]
        )
        writer_csv.writerow(
            [
                "LaneATT-ResNet18-TuSimple",
                str(video_path),
                len(latencies),
                round(avg_total_ms, 3),
                round(avg_inference_ms, 3),
                round(percentile(latencies, 50), 3),
                round(percentile(latencies, 95), 3),
                round(bench_fps, 2),
            ]
        )

    print(
        f"{video_path.name}: frames={frame_id}, measured={len(latencies)}, "
        f"avg={avg_total_ms:.2f}ms, infer={avg_inference_ms:.2f}ms, "
        f"fps={bench_fps:.2f}, video_bytes={output_video_size}"
    )


def main():
    parser = argparse.ArgumentParser(description="Run LaneATT inference on one video.")
    parser.add_argument("--repo", default="repos/LaneATT", help="Path to LaneATT repo.")
    parser.add_argument("--weights", required=True, help="Path to LaneATT .pt checkpoint.")
    parser.add_argument(
        "--config",
        default="weights/laneatt/extracted/experiments/laneatt_r18_tusimple/config.yaml",
        help="LaneATT YAML config. Used for model and test parameters.",
    )
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--output-video", required=True, help="Overlay video path.")
    parser.add_argument("--output-csv", required=True, help="FPS CSV path.")
    parser.add_argument("--output-jsonl", required=True, help="Lane schema JSONL path.")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--conf-threshold", type=float, default=None)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    runner = LaneATTVideoRunner(
        repo_path=args.repo,
        weight_path=args.weights,
        config_path=args.config,
        device=args.device,
        conf_threshold=args.conf_threshold,
    )
    run_video(
        runner=runner,
        video_path=args.video,
        output_video=args.output_video,
        output_csv=args.output_csv,
        output_jsonl=args.output_jsonl,
        warmup=args.warmup,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
