from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a short Phase B smoke test over Danang videos.")
    parser.add_argument("--data-dir", default=Path("data/raw/danang"), type=Path)
    parser.add_argument("--config", default=Path("configs/danang/cau_rong_manual.json"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/danang/smoke"), type=Path)
    parser.add_argument("--model", default=Path("models/yolov8n.pt"), type=Path)
    parser.add_argument("--max-frames", default=120, type=int)
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for index, video in enumerate(sorted(args.data_dir.glob("*.mp4")), 1):
        jsonl = args.output_dir / f"video_{index:02d}_events.jsonl"
        command = [
            sys.executable,
            "-m",
            "trafficflow.cli.run_counting",
            "--video",
            str(video),
            "--config",
            str(args.config),
            "--model",
            str(args.model),
            "--device",
            args.device,
            "--max-frames",
            str(args.max_frames),
            "--output-jsonl",
            str(jsonl),
        ]
        result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True)
        item = {
            "video": video.name,
            "returncode": result.returncode,
            "events_bytes": jsonl.stat().st_size if jsonl.exists() else None,
            "stdout_tail": result.stdout.splitlines()[-8:],
            "stderr_tail": result.stderr.splitlines()[-8:],
        }
        summary.append(item)
        print(json.dumps(item, ensure_ascii=False))
        if result.returncode != 0:
            break

    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary[-1]["returncode"] if summary else 0


if __name__ == "__main__":
    raise SystemExit(main())
