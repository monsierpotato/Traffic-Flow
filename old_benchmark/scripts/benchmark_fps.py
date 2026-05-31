import argparse
import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np

from lane_schema import LaneFrameResult, RuntimeInfo


class LaneModelWrapper:
    def __init__(self, method_name, weight_path=None, device="cuda"):
        self.method_name = method_name
        self.weight_path = weight_path
        self.device = device
        self.model = self.load_model()

    def load_model(self):
        raise NotImplementedError

    def infer(self, frame, frame_id=0, video_id="unknown"):
        raise NotImplementedError


class NoOpLaneModel(LaneModelWrapper):
    def load_model(self):
        return None

    def infer(self, frame, frame_id=0, video_id="unknown"):
        return LaneFrameResult(
            video_id=video_id,
            frame_id=frame_id,
            method=self.method_name,
            lanes=[],
        )


def percentile(values, q):
    return float(np.percentile(values, q)) if values else 0.0


def benchmark_video(model, video_path, output_csv, output_jsonl=None, warmup=10, max_frames=None):
    video_path = Path(video_path)
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if output_jsonl is not None:
        output_jsonl = Path(output_jsonl)
        output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    latencies = []
    frame_id = 0
    measured_frames = 0
    video_id = video_path.stem
    jsonl_file = output_jsonl.open("w", encoding="utf-8") if output_jsonl else None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if max_frames is not None and frame_id >= max_frames:
                break

            start = time.perf_counter()
            result = model.infer(frame, frame_id=frame_id, video_id=video_id)
            end = time.perf_counter()

            total_ms = (end - start) * 1000.0
            if frame_id >= warmup:
                latencies.append(total_ms)
                measured_frames += 1

            result.runtime = RuntimeInfo(
                total_ms=total_ms,
                fps=1000.0 / total_ms if total_ms > 0 else 0.0,
            )
            if jsonl_file:
                jsonl_file.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

            frame_id += 1
    finally:
        cap.release()
        if jsonl_file:
            jsonl_file.close()

    total_ms = sum(latencies)
    avg_ms = total_ms / max(len(latencies), 1)
    fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "method",
                "video",
                "frames",
                "avg_latency_ms",
                "p50_latency_ms",
                "p95_latency_ms",
                "fps",
            ]
        )
        writer.writerow(
            [
                model.method_name,
                str(video_path),
                measured_frames,
                round(avg_ms, 3),
                round(percentile(latencies, 50), 3),
                round(percentile(latencies, 95), 3),
                round(fps, 2),
            ]
        )

    print(f"Method: {model.method_name}")
    print(f"Video: {video_path}")
    print(f"Frames measured: {measured_frames}")
    print(f"Avg latency: {avg_ms:.3f} ms")
    print(f"P95 latency: {percentile(latencies, 95):.3f} ms")
    print(f"FPS: {fps:.2f}")


def build_model(method, weight_path, device):
    if method == "noop":
        return NoOpLaneModel(method_name="noop", weight_path=weight_path, device=device)
    raise ValueError(
        f"Unknown method '{method}'. Add real wrappers in scripts/run_ufld.py, "
        "scripts/run_laneatt.py, or scripts/run_condlanenet.py."
    )


def main():
    parser = argparse.ArgumentParser(description="Benchmark lane model FPS on a video.")
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--method", default="noop", help="Method name. Currently supports: noop.")
    parser.add_argument("--weights", default=None, help="Optional model weight path.")
    parser.add_argument("--device", default="cuda", help="Device string, e.g. cuda or cpu.")
    parser.add_argument("--warmup", type=int, default=10, help="Number of initial frames ignored in metrics.")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional frame limit.")
    parser.add_argument("--output-csv", default=None, help="Output CSV path.")
    parser.add_argument("--output-jsonl", default=None, help="Optional per-frame lane output JSONL.")
    args = parser.parse_args()

    output_csv = args.output_csv or f"benchmark_results/outputs/{args.method}/fps.csv"
    output_jsonl = args.output_jsonl or f"benchmark_results/outputs/{args.method}/lane_outputs.jsonl"
    model = build_model(args.method, args.weights, args.device)
    benchmark_video(
        model=model,
        video_path=args.video,
        output_csv=output_csv,
        output_jsonl=output_jsonl,
        warmup=args.warmup,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
