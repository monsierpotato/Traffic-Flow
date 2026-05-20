import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import scipy.special
import torch
import torchvision.transforms as transforms
from PIL import Image

from lane_schema import Lane, LaneFrameResult, RuntimeInfo
from visualize_overlay import draw_lanes


def add_repo_to_path(repo_path):
    repo_path = Path(repo_path).resolve()
    if str(repo_path) not in sys.path:
        sys.path.insert(0, str(repo_path))


def percentile(values, q):
    return float(np.percentile(values, q)) if values else 0.0


class UFLDVideoRunner:
    def __init__(self, repo_path, weight_path, dataset="Tusimple", backbone="18", device="cpu"):
        add_repo_to_path(repo_path)
        from data.constant import culane_row_anchor, tusimple_row_anchor
        from model.model import parsingNet

        self.dataset = dataset
        self.device = torch.device(device if device == "cuda" and torch.cuda.is_available() else "cpu")

        if dataset == "Tusimple":
            self.griding_num = 100
            self.cls_num_per_lane = 56
            self.row_anchor = tusimple_row_anchor
        elif dataset == "CULane":
            self.griding_num = 200
            self.cls_num_per_lane = 18
            self.row_anchor = culane_row_anchor
        else:
            raise ValueError(f"Unsupported dataset: {dataset}")

        self.model = parsingNet(
            pretrained=False,
            backbone=backbone,
            cls_dim=(self.griding_num + 1, self.cls_num_per_lane, 4),
            use_aux=False,
        ).to(self.device)

        state = torch.load(weight_path, map_location="cpu")
        state_dict = state["model"] if isinstance(state, dict) and "model" in state else state
        compatible_state_dict = {
            key[7:] if key.startswith("module.") else key: value for key, value in state_dict.items()
        }
        self.model.load_state_dict(compatible_state_dict, strict=False)
        self.model.eval()

        self.transform = transforms.Compose(
            [
                transforms.Resize((288, 800)),
                transforms.ToTensor(),
                transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
            ]
        )

    def infer(self, frame, video_id, frame_id):
        image_height, image_width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = self.transform(Image.fromarray(rgb)).unsqueeze(0).to(self.device)

        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        start = time.perf_counter()
        with torch.no_grad():
            output = self.model(tensor)
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        inference_ms = (time.perf_counter() - start) * 1000.0

        lanes = self._decode_lanes(output, image_width, image_height)
        return LaneFrameResult(
            video_id=video_id,
            frame_id=frame_id,
            method="UFLD-Tusimple-Res18" if self.dataset == "Tusimple" else "UFLD-CULane-Res18",
            lanes=lanes,
            runtime=RuntimeInfo(inference_ms=inference_ms, total_ms=inference_ms),
            meta={"image_width": image_width, "image_height": image_height},
        )

    def _decode_lanes(self, output, image_width, image_height):
        col_sample = np.linspace(0, 800 - 1, self.griding_num)
        col_sample_w = col_sample[1] - col_sample[0]

        out_j = output[0].detach().cpu().numpy()
        out_j = out_j[:, ::-1, :]
        prob = scipy.special.softmax(out_j[:-1, :, :], axis=0)
        idx = np.arange(self.griding_num) + 1
        idx = idx.reshape(-1, 1, 1)
        loc = np.sum(prob * idx, axis=0)
        out_j = np.argmax(out_j, axis=0)
        loc[out_j == self.griding_num] = 0
        decoded = loc

        lanes = []
        for lane_index in range(decoded.shape[1]):
            if np.sum(decoded[:, lane_index] != 0) <= 2:
                continue

            points = []
            for anchor_index in range(decoded.shape[0]):
                if decoded[anchor_index, lane_index] <= 0:
                    continue
                x = int(decoded[anchor_index, lane_index] * col_sample_w * image_width / 800) - 1
                y = int(image_height * (self.row_anchor[self.cls_num_per_lane - 1 - anchor_index] / 288)) - 1
                if 0 <= x < image_width and 0 <= y < image_height:
                    points.append((x, y))

            if len(points) > 1:
                lanes.append(Lane(lane_id=len(lanes) + 1, confidence=None, points=points))
        return lanes


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

    latencies = []
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
            total_ms = result.runtime.total_ms
            if frame_id >= warmup:
                latencies.append(total_ms)

            draw_lanes(frame, [lane.__dict__ for lane in result.lanes])
            writer.write(frame)
            jsonl.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
            frame_id += 1

    cap.release()
    writer.release()

    avg_ms = sum(latencies) / max(len(latencies), 1)
    bench_fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer_csv = csv.writer(f)
        writer_csv.writerow(
            ["method", "video", "frames", "avg_latency_ms", "p50_latency_ms", "p95_latency_ms", "fps"]
        )
        writer_csv.writerow(
            [
                "UFLD-Tusimple-Res18",
                str(video_path),
                len(latencies),
                round(avg_ms, 3),
                round(percentile(latencies, 50), 3),
                round(percentile(latencies, 95), 3),
                round(bench_fps, 2),
            ]
        )

    print(f"{video_path.name}: frames={frame_id}, measured={len(latencies)}, avg={avg_ms:.2f}ms, fps={bench_fps:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Run UFLD inference on one video.")
    parser.add_argument("--repo", default="repos/UFLD", help="Path to UFLD repo.")
    parser.add_argument("--weights", required=True, help="Path to UFLD .pth weight.")
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--output-video", required=True, help="Overlay video path.")
    parser.add_argument("--output-csv", required=True, help="FPS CSV path.")
    parser.add_argument("--output-jsonl", required=True, help="Lane schema JSONL path.")
    parser.add_argument("--dataset", default="Tusimple", choices=["Tusimple", "CULane"])
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    runner = UFLDVideoRunner(
        repo_path=args.repo,
        weight_path=args.weights,
        dataset=args.dataset,
        device=args.device,
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
