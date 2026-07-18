"""Unified benchmark runner for frozen TrafficFlow benchmark artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark.detrac_parser import parse_detrac_xml


DEFAULT_PROTOCOL = Path("benchmark/configs/benchmark_protocol_v1.yaml")
DEFAULT_SPLIT = Path("benchmark/splits/ua_detrac_split_v1.json")
DEFAULT_GEOMETRY_DIR = Path("benchmark/configs/geometry")
DEFAULT_CLASS_MAPPING = Path("benchmark/configs/class_mapping_v1.yaml")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _git_commit() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
    except Exception:
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _load_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"').strip("'")
        if value.lower() in {"true", "false"}:
            parsed: Any = value.lower() == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        data[key.strip()] = parsed
    return data


def _copy_snapshot(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _select_sequences(split: dict, bucket: str, explicit: str | None, max_sequences: int) -> list[str]:
    if explicit:
        sequence_ids = [item.strip() for item in explicit.split(",") if item.strip()]
    else:
        sequence_ids = list(split["splits"].get(bucket, []))
    if max_sequences > 0:
        sequence_ids = sequence_ids[:max_sequences]
    return sequence_ids


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _gt_smoke_raw_outputs(sequence_id: str, xml_path: Path, max_frames: int) -> tuple[list[dict], list[dict]]:
    detections = []
    tracks = []
    tracklets = parse_detrac_xml(xml_path)
    for track_id, track in sorted(tracklets.items()):
        for frame_num, bbox in sorted(track.frames.items()):
            if max_frames > 0 and frame_num > max_frames:
                continue
            row = {
                "schema_version": 1,
                "video_id": sequence_id,
                "frame_num": frame_num,
                "gt_track_id": track_id,
                "class_name": track.class_name,
                "bbox_xyxy": [round(v, 3) for v in bbox],
                "coordinate_space": "source_frame",
                "source": "ua_detrac_gt_smoke_backend",
            }
            detections.append(row)
            tracks.append(dict(row, track_id=track_id))
    return detections, tracks


def run(args: argparse.Namespace) -> dict:
    started_at = _now()
    t0 = time.perf_counter()
    output = args.output
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    split = json.loads(args.split_file.read_text(encoding="utf-8"))
    protocol_text = args.protocol.read_text(encoding="utf-8")
    if "run_manifest_required: true" not in protocol_text:
        raise ValueError("Protocol does not require run manifests")
    run_config = _load_simple_yaml(args.config)
    model_path = args.model
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    sequence_ids = _select_sequences(split, args.split, args.sequences, args.max_sequences)
    if not sequence_ids:
        raise ValueError(f"No sequences selected for split={args.split}")

    metadata = split["selected_sequence_metadata"]
    run_id = output.name
    raw_detection_dir = output / "raw_detections"
    raw_track_dir = output / "raw_tracks"
    raw_event_dir = output / "raw_counting_events"
    timing_rows = []
    summary_rows = []
    geometry_versions = {}
    sequence_summaries = []

    for sequence_id in sequence_ids:
        if sequence_id not in metadata:
            raise ValueError(f"Sequence is not in selected metadata: {sequence_id}")
        meta = metadata[sequence_id]
        geometry_path = args.geometry_dir / f"{sequence_id}.json"
        if not geometry_path.exists():
            raise FileNotFoundError(f"Geometry not found: {geometry_path}")
        geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
        geometry_versions[sequence_id] = geometry["geometry_version"]

        seq_t0 = time.perf_counter()
        raw_detections, raw_tracks = _gt_smoke_raw_outputs(sequence_id, Path(meta["xml_path"]), args.max_frames)
        timing_rows.append({"sequence_id": sequence_id, "stage": "load_gt_tracks", "elapsed_ms": round((time.perf_counter() - seq_t0) * 1000, 3)})

        event_t0 = time.perf_counter()
        source_events = _load_jsonl(args.derived_events_dir / f"{sequence_id}.jsonl")
        if args.max_frames > 0:
            source_events = [event for event in source_events if int(event["crossing_frame"]) <= args.max_frames]
        timing_rows.append({"sequence_id": sequence_id, "stage": "load_counting_events", "elapsed_ms": round((time.perf_counter() - event_t0) * 1000, 3)})

        _write_jsonl(raw_detection_dir / f"{sequence_id}.jsonl", raw_detections)
        _write_jsonl(raw_track_dir / f"{sequence_id}.jsonl", raw_tracks)
        _write_jsonl(raw_event_dir / f"{sequence_id}.jsonl", source_events)

        class_counts: dict[str, int] = {}
        for event in source_events:
            class_counts[event["class_name"]] = class_counts.get(event["class_name"], 0) + 1
        summary_rows.append(
            {
                "run_id": run_id,
                "sequence_id": sequence_id,
                "backend": args.backend,
                "raw_detection_rows": len(raw_detections),
                "raw_track_rows": len(raw_tracks),
                "raw_counting_events": len(source_events),
            }
        )
        sequence_summaries.append(
            {
                "sequence_id": sequence_id,
                "geometry_version": geometry["geometry_version"],
                "raw_detection_rows": len(raw_detections),
                "raw_track_rows": len(raw_tracks),
                "raw_counting_events": len(source_events),
                "class_counts": class_counts,
            }
        )

    snapshot_dir = output / "config_snapshot"
    _copy_snapshot(args.protocol, snapshot_dir / args.protocol.name)
    _copy_snapshot(args.split_file, snapshot_dir / args.split_file.name)
    _copy_snapshot(DEFAULT_CLASS_MAPPING, snapshot_dir / DEFAULT_CLASS_MAPPING.name)
    _copy_snapshot(args.config, snapshot_dir / args.config.name)
    for sequence_id in sequence_ids:
        _copy_snapshot(args.geometry_dir / f"{sequence_id}.json", snapshot_dir / "geometry" / f"{sequence_id}.json")

    resource_rows = [
        {
            "timestamp": _now(),
            "gpu_util_pct": 0,
            "vram_used_mb": 0,
            "vram_total_mb": 0,
            "cpu_pct": 0,
            "ram_used_mb": 0,
            "source": "phase03_smoke_backend_placeholder",
        }
    ]
    _write_csv(output / "stage_timings.csv", timing_rows, ["sequence_id", "stage", "elapsed_ms"])
    _write_csv(
        output / "resource_samples.csv",
        resource_rows,
        ["timestamp", "gpu_util_pct", "vram_used_mb", "vram_total_mb", "cpu_pct", "ram_used_mb", "source"],
    )
    _write_csv(
        output / "summary.csv",
        summary_rows,
        ["run_id", "sequence_id", "backend", "raw_detection_rows", "raw_track_rows", "raw_counting_events"],
    )

    completed_at = _now()
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "git_commit": _git_commit(),
        "dataset_split": split["split_version"],
        "split_bucket": args.split,
        "protocol_version": 1,
        "protocol_path": str(args.protocol).replace("\\", "/"),
        "split_file": str(args.split_file).replace("\\", "/"),
        "model_path": str(model_path).replace("\\", "/"),
        "model_sha256": _sha256(model_path),
        "imgsz": int(run_config.get("imgsz", args.imgsz)),
        "confidence": float(run_config.get("confidence", args.confidence)),
        "iou": float(run_config.get("iou", args.iou)),
        "tracker_config": str(run_config.get("tracker_config", "benchmark/configs/tracker/default")),
        "counting_config": str(run_config.get("counting_config", "benchmark/configs/benchmark_protocol_v1.yaml")),
        "geometry_versions": geometry_versions,
        "device": str(run_config.get("device", "cpu")),
        "gpu": str(run_config.get("gpu", "not_collected_in_smoke_backend")),
        "backend": args.backend,
        "sequences": sequence_ids,
        "software": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "artifacts": {
            "raw_detections": "raw_detections/",
            "raw_tracks": "raw_tracks/",
            "raw_counting_events": "raw_counting_events/",
            "stage_timings": "stage_timings.csv",
            "resource_samples": "resource_samples.csv",
            "config_snapshot": "config_snapshot/",
            "summary_json": "summary.json",
            "summary_csv": "summary.csv",
            "summary_markdown": "summary.md",
        },
        "started_at": started_at,
        "completed_at": completed_at,
    }
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "backend": args.backend,
        "split_bucket": args.split,
        "sequence_count": len(sequence_ids),
        "total_raw_detection_rows": sum(item["raw_detection_rows"] for item in sequence_summaries),
        "total_raw_track_rows": sum(item["raw_track_rows"] for item in sequence_summaries),
        "total_raw_counting_events": sum(item["raw_counting_events"] for item in sequence_summaries),
        "elapsed_ms": elapsed_ms,
        "sequences": sequence_summaries,
    }
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "summary.json", summary)
    (output / "summary.md").write_text(_format_summary_md(manifest, summary), encoding="utf-8")
    return summary


def _format_summary_md(manifest: dict, summary: dict) -> str:
    lines = [
        f"# Benchmark Run {manifest['run_id']}",
        "",
        f"- Backend: `{manifest['backend']}`",
        f"- Split: `{manifest['split_bucket']}`",
        f"- Sequences: {summary['sequence_count']}",
        f"- Raw detections: {summary['total_raw_detection_rows']}",
        f"- Raw tracks: {summary['total_raw_track_rows']}",
        f"- Raw counting events: {summary['total_raw_counting_events']}",
        "",
        "| Sequence | Geometry | Raw detections | Raw tracks | Raw events |",
        "|---|---|---:|---:|---:|",
    ]
    for item in summary["sequences"]:
        lines.append(
            f"| {item['sequence_id']} | {item['geometry_version']} | "
            f"{item['raw_detection_rows']} | {item['raw_track_rows']} | {item['raw_counting_events']} |"
        )
    lines.append("")
    lines.append("This Phase 03 smoke run validates runner, manifest, and artifact plumbing. Model scoring starts in Phase 04.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="TrafficFlow unified benchmark runner")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--split", default="smoke_test", help="Split bucket to run")
    parser.add_argument("--sequences", help="Optional comma-separated sequence override")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--tracker-config", default="")
    parser.add_argument("--counting-config", default="")
    parser.add_argument("--geometry-dir", type=Path, default=DEFAULT_GEOMETRY_DIR)
    parser.add_argument("--derived-events-dir", type=Path, default=Path("benchmark/ground_truth/derived_events"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-sequences", type=int, default=0)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument(
        "--backend",
        choices=["derived_gt_smoke"],
        default="derived_gt_smoke",
        help="Phase 03 validates runner plumbing with GT-backed smoke output.",
    )
    args = parser.parse_args()
    summary = run(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
