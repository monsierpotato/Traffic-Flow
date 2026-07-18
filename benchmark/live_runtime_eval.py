"""Live/HLS runtime and stability benchmark for TrafficFlow Phase 08."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PERF_FIELDS = [
    "reader_wait_ms",
    "frame_interarrival_ms",
    "frame_age_ms",
    "preprocess_ms",
    "infer_wall_ms",
    "track_ms",
    "render_ms",
    "jpeg_ms",
    "publish_ms",
    "loop_idle_ms",
]


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _percentile(values: Iterable[float], q: float) -> float:
    clean = sorted(float(v) for v in values if v not in (None, "") and not math.isnan(float(v)))
    if not clean:
        return 0.0
    if len(clean) == 1:
        return clean[0]
    idx = (len(clean) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return clean[lo]
    return clean[lo] + (clean[hi] - clean[lo]) * (idx - lo)


def _avg(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if v not in (None, "") and not math.isnan(float(v))]
    return sum(vals) / len(vals) if vals else 0.0


def _http_json(method: str, url: str, body: dict | None = None, timeout: float = 30.0) -> dict:
    payload = None
    headers = {}
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc


def _http_frame(url: str, timeout: float = 10.0) -> dict:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            return {
                "frame_fetch_status": response.status,
                "frame_fetch_bytes": len(payload),
                "frame_fetch_content_type": response.headers.get("content-type", ""),
                "frame_fetch_seq": response.headers.get("x-live-frame-seq", ""),
                "frame_fetch_error": "",
            }
    except HTTPError as exc:
        return {
            "frame_fetch_status": exc.code,
            "frame_fetch_bytes": 0,
            "frame_fetch_content_type": "",
            "frame_fetch_seq": "",
            "frame_fetch_error": exc.read().decode("utf-8", errors="replace")[:240],
        }
    except Exception as exc:
        return {
            "frame_fetch_status": 0,
            "frame_fetch_bytes": 0,
            "frame_fetch_content_type": "",
            "frame_fetch_seq": "",
            "frame_fetch_error": str(exc)[:240],
        }


def _parse_percent(raw: str) -> float:
    try:
        return float(str(raw).strip().rstrip("%"))
    except (TypeError, ValueError):
        return 0.0


def _parse_size_mb(raw: str) -> float:
    text = str(raw).strip()
    if not text:
        return 0.0
    first = text.split("/")[0].strip().replace(" ", "")
    units = [
        ("GiB", 1024.0),
        ("MiB", 1.0),
        ("KiB", 1.0 / 1024.0),
        ("GB", 1000.0),
        ("MB", 1.0),
        ("KB", 1.0 / 1000.0),
        ("B", 1.0 / (1000.0 * 1000.0)),
    ]
    for suffix, factor in units:
        if first.endswith(suffix):
            try:
                return float(first[: -len(suffix)]) * factor
            except ValueError:
                return 0.0
    try:
        return float(first)
    except ValueError:
        return 0.0


def _nvidia_smi() -> dict:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            return {}
        parts = [part.strip() for part in result.stdout.strip().split(",")]
        if len(parts) < 3:
            return {}
        return {
            "gpu_util_pct": float(parts[0]),
            "vram_used_mb": float(parts[1]),
            "vram_total_mb": float(parts[2]),
        }
    except Exception:
        return {}


def _host_resources() -> dict:
    data = {}
    try:
        import psutil

        data["host_cpu_pct"] = float(psutil.cpu_percent(interval=0.05))
        mem = psutil.virtual_memory()
        data["host_ram_used_mb"] = round(mem.used / (1024 * 1024), 3)
    except Exception:
        data["host_cpu_pct"] = 0.0
        data["host_ram_used_mb"] = 0.0
    data.update(_nvidia_smi())
    return data


def _docker_stats(container: str) -> dict:
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", container],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if result.returncode != 0 or not line:
            return {}
        row = json.loads(line)
        return {
            "api_container_cpu_pct": _parse_percent(row.get("CPUPerc", "")),
            "api_container_mem_used_mb": round(_parse_size_mb(row.get("MemUsage", "")), 3),
            "api_container_mem_pct": _parse_percent(row.get("MemPerc", "")),
            "api_container_pids": int(row.get("PIDs", 0) or 0),
        }
    except Exception:
        return {}


def _resource_sample(container: str) -> dict:
    row = _host_resources()
    row.update(_docker_stats(container))
    return row


def _flatten_status(row: dict) -> dict:
    perf = row.get("perf") or {}
    flat = {
        "status": row.get("status", ""),
        "uptime_s": row.get("uptime_s", 0),
        "frames_read": row.get("frames_read", 0),
        "frames_processed": row.get("frames_processed", 0),
        "frames_dropped": row.get("frames_dropped", 0),
        "snapshot_fps": row.get("fps", 0),
        "latest_frame_seq": row.get("latest_frame_seq", 0),
        "lane_volume_total": row.get("lane_volume_total", 0),
        "global_unique_count": row.get("global_unique_count", 0),
        "latest_track_count": len(row.get("latest_tracks") or []),
        "last_error": row.get("last_error") or "",
        "model_name": row.get("model_name") or "",
        "roi_mode": row.get("roi_mode") or "",
        "ai_imgsz": row.get("ai_imgsz") or 0,
    }
    for field in PERF_FIELDS:
        flat[field] = perf.get(field, "")
    flat["raw_det"] = perf.get("raw_det", "")
    flat["kept_det"] = perf.get("kept_det", "")
    flat["active_tracks"] = perf.get("active_tracks", "")
    flat["lost_tracks"] = perf.get("lost_tracks", "")
    flat["dropped_reason"] = perf.get("dropped_reason", "")
    flat["reader_cropped"] = perf.get("reader_cropped", "")
    flat["reader_output"] = json.dumps(perf.get("reader_output", []), ensure_ascii=False)
    return flat


def _add_deltas(rows: list[dict]) -> None:
    previous = None
    for row in rows:
        if previous is None:
            row.update(
                {
                    "sample_dt_s": 0.0,
                    "read_fps_sample": 0.0,
                    "processed_fps_sample": 0.0,
                    "published_fps_sample": 0.0,
                    "dropped_delta": 0,
                    "processed_delta": 0,
                    "published_delta": 0,
                }
            )
        else:
            dt = max(0.001, float(row["elapsed_s"]) - float(previous["elapsed_s"]))
            processed_delta = int(row["frames_processed"]) - int(previous["frames_processed"])
            read_delta = int(row["frames_read"]) - int(previous["frames_read"])
            published_delta = int(row["latest_frame_seq"]) - int(previous["latest_frame_seq"])
            dropped_delta = int(row["frames_dropped"]) - int(previous["frames_dropped"])
            row.update(
                {
                    "sample_dt_s": round(dt, 3),
                    "read_fps_sample": round(read_delta / dt, 3),
                    "processed_fps_sample": round(processed_delta / dt, 3),
                    "published_fps_sample": round(published_delta / dt, 3),
                    "dropped_delta": dropped_delta,
                    "processed_delta": processed_delta,
                    "published_delta": published_delta,
                }
            )
        previous = dict(row)


def _stall_metrics(rows: list[dict], warmup_s: float, threshold_s: float) -> dict:
    active_stall_s = 0.0
    total_stall_s = 0.0
    stall_count = 0
    in_stall = False
    for row in rows:
        if float(row["elapsed_s"]) < warmup_s:
            continue
        if row.get("status") != "running":
            continue
        dt = float(row.get("sample_dt_s") or 0.0)
        no_progress = int(row.get("processed_delta") or 0) <= 0
        if no_progress:
            active_stall_s += dt
            if active_stall_s >= threshold_s:
                if not in_stall:
                    stall_count += 1
                    in_stall = True
                total_stall_s += dt
        else:
            active_stall_s = 0.0
            in_stall = False
    duration_h = max(1e-9, (max((float(row["elapsed_s"]) for row in rows), default=0.0) - warmup_s) / 3600.0)
    return {
        "stall_count": stall_count,
        "stall_count_per_hour": round(stall_count / duration_h, 3),
        "total_stall_duration_s": round(total_stall_s, 3),
    }


def _filtered_api_logs(container: str, since_ts: float) -> dict:
    try:
        result = subprocess.run(
            ["docker", "logs", "--since", _utc_iso(since_ts), container],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        text = "\n".join(part for part in [result.stdout, result.stderr] if part)
    except Exception as exc:
        return {"error": str(exc), "lines": []}
    interesting = []
    for line in text.splitlines():
        lower = line.lower()
        if any(term in lower for term in ["reconnect", "reset", "input_gap", "last_error", "failed", "stale_frame"]):
            interesting.append(line[-1000:])
    return {"error": "", "lines": interesting[-300:]}


def _summarize(
    *,
    args: argparse.Namespace,
    run_id: str,
    source_info: dict,
    initial_session: dict,
    final_session: dict,
    timeseries: list[dict],
    resources: list[dict],
    api_log_signals: dict,
    started_at: float,
    ended_at: float,
) -> dict:
    steady = [row for row in timeseries if float(row["elapsed_s"]) >= args.warmup_s and row.get("status") == "running"]
    stat_rows = steady or timeseries
    first_inferred = next((row for row in timeseries if int(row.get("frames_processed") or 0) > 0), None)
    final_read = int(final_session.get("frames_read") or 0)
    final_processed = int(final_session.get("frames_processed") or 0)
    final_dropped = int(final_session.get("frames_dropped") or 0)
    duration_s = max(0.001, ended_at - started_at)
    stall = _stall_metrics(timeseries, args.warmup_s, args.stall_threshold_s)
    reconnect_lines = [line for line in api_log_signals.get("lines", []) if "reconnect" in line.lower()]
    reset_lines = [line for line in api_log_signals.get("lines", []) if "reset" in line.lower() or "input_gap" in line.lower()]
    status_errors = [row for row in timeseries if row.get("last_error")]
    summary = {
        "run_id": run_id,
        "created_at": _now_iso(),
        "source_url": args.source_url,
        "source_type": source_info.get("source_type", ""),
        "source_width": source_info.get("width", 0),
        "source_height": source_info.get("height", 0),
        "source_fps": source_info.get("fps", 0),
        "session_id": initial_session.get("session_id", ""),
        "requested_duration_s": args.duration_s,
        "actual_duration_s": round(duration_s, 3),
        "warmup_s": args.warmup_s,
        "sample_interval_s": args.sample_interval_s,
        "frame_skip": args.frame_skip,
        "status_final": final_session.get("status", ""),
        "session_error_count": len(status_errors),
        "last_error": final_session.get("last_error") or "",
        "frames_read": final_read,
        "frames_processed": final_processed,
        "frames_dropped": final_dropped,
        "processed_fps_overall": round(final_processed / duration_s, 3),
        "published_fps_overall": round(int(final_session.get("latest_frame_seq") or 0) / duration_s, 3),
        "dropped_frame_ratio": round(final_dropped / max(1, final_read), 6),
        "stale_frame_sample_ratio": round(
            sum(1 for row in stat_rows if row.get("dropped_reason") == "stale_frame") / max(1, len(stat_rows)),
            6,
        ),
        "time_to_first_inferred_frame_s": round(float(first_inferred["elapsed_s"]), 3) if first_inferred else 0.0,
        "reconnect_count_from_logs": len(reconnect_lines),
        "reconnect_duration_s": 0.0,
        "unexpected_tracker_reset_count_from_logs": len(reset_lines),
        **stall,
        "gpu_util_avg_pct": round(_avg(row.get("gpu_util_pct", 0) for row in resources), 3),
        "gpu_util_p95_pct": round(_percentile((row.get("gpu_util_pct", 0) for row in resources), 0.95), 3),
        "vram_peak_mb": round(max((float(row.get("vram_used_mb") or 0) for row in resources), default=0.0), 3),
        "host_ram_start_mb": round(float(resources[0].get("host_ram_used_mb") or 0), 3) if resources else 0.0,
        "host_ram_end_mb": round(float(resources[-1].get("host_ram_used_mb") or 0), 3) if resources else 0.0,
        "api_container_mem_start_mb": round(float(resources[0].get("api_container_mem_used_mb") or 0), 3) if resources else 0.0,
        "api_container_mem_end_mb": round(float(resources[-1].get("api_container_mem_used_mb") or 0), 3) if resources else 0.0,
        "api_container_mem_peak_mb": round(max((float(row.get("api_container_mem_used_mb") or 0) for row in resources), default=0.0), 3),
        "lane_volume_total": final_session.get("lane_volume_total", 0),
        "global_unique_count": final_session.get("global_unique_count", 0),
        "model_name": final_session.get("model_name", ""),
        "roi_mode": final_session.get("roi_mode", ""),
        "ai_imgsz": final_session.get("ai_imgsz", 0),
    }
    for field in ["processed_fps_sample", "published_fps_sample", *PERF_FIELDS]:
        summary[f"{field}_p50"] = round(_percentile((row.get(field, 0) for row in stat_rows), 0.50), 3)
        summary[f"{field}_p95"] = round(_percentile((row.get(field, 0) for row in stat_rows), 0.95), 3)
        summary[f"{field}_p99"] = round(_percentile((row.get(field, 0) for row in stat_rows), 0.99), 3)
        summary[f"{field}_max"] = round(max((float(row.get(field) or 0) for row in stat_rows), default=0.0), 3)
    return summary


def _write_report(path: Path, summary: dict, output_dir: Path) -> None:
    lines = [
        "# Phase 08 Live/HLS Runtime Benchmark",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- Source type: `{summary['source_type']}`",
        f"- Source: `{summary['source_width']}x{summary['source_height']} @ {summary['source_fps']} FPS`",
        f"- Duration: `{summary['actual_duration_s']}` seconds, warmup `{summary['warmup_s']}` seconds",
        f"- Model/runtime: `{summary['model_name']}`, imgsz `{summary['ai_imgsz']}`, ROI mode `{summary['roi_mode']}`",
        "",
        "## Scope",
        "",
        "This phase measures live runtime and stability only. No live GT was available, so count totals are operational outputs, not accuracy metrics.",
        "",
        "Ownership wording: the candidate led bottleneck analysis and AI-runtime validation; live-platform integration remains shared team work.",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Processed FPS overall | {summary['processed_fps_overall']} |",
        f"| Published FPS overall | {summary['published_fps_overall']} |",
        f"| Processed FPS p50/p95/p99 | {summary['processed_fps_sample_p50']} / {summary['processed_fps_sample_p95']} / {summary['processed_fps_sample_p99']} |",
        f"| Published FPS p50/p95/p99 | {summary['published_fps_sample_p50']} / {summary['published_fps_sample_p95']} / {summary['published_fps_sample_p99']} |",
        f"| Frame interarrival p50/p95/p99 ms | {summary['frame_interarrival_ms_p50']} / {summary['frame_interarrival_ms_p95']} / {summary['frame_interarrival_ms_p99']} |",
        f"| Frame age p50/p95/p99 ms | {summary['frame_age_ms_p50']} / {summary['frame_age_ms_p95']} / {summary['frame_age_ms_p99']} |",
        f"| Inference wall p50/p95/p99 ms | {summary['infer_wall_ms_p50']} / {summary['infer_wall_ms_p95']} / {summary['infer_wall_ms_p99']} |",
        f"| Dropped-frame ratio | {summary['dropped_frame_ratio']} |",
        f"| Stale-frame sample ratio | {summary['stale_frame_sample_ratio']} |",
        f"| Time to first inferred frame s | {summary['time_to_first_inferred_frame_s']} |",
        f"| Reconnect count from logs | {summary['reconnect_count_from_logs']} |",
        f"| Stall count/hour | {summary['stall_count_per_hour']} |",
        f"| Total stall duration s | {summary['total_stall_duration_s']} |",
        f"| Session error count | {summary['session_error_count']} |",
        f"| Unexpected tracker reset count from logs | {summary['unexpected_tracker_reset_count_from_logs']} |",
        f"| GPU util avg/p95 % | {summary['gpu_util_avg_pct']} / {summary['gpu_util_p95_pct']} |",
        f"| VRAM peak MB | {summary['vram_peak_mb']} |",
        f"| API container RAM start/end/peak MB | {summary['api_container_mem_start_mb']} / {summary['api_container_mem_end_mb']} / {summary['api_container_mem_peak_mb']} |",
        f"| Operational lane volume total | {summary['lane_volume_total']} |",
        "",
        "## Artifacts",
        "",
        "- `benchmark/reports/live_runtime_timeseries.csv`",
        "- `benchmark/reports/live_resource_timeseries.csv`",
        f"- Run manifest: `{output_dir.as_posix()}/manifest.json`",
        f"- Run summary: `{output_dir.as_posix()}/live_runtime_summary.json`",
        f"- API log signal extract: `{output_dir.as_posix()}/api_log_signals.txt`",
        "",
        "## Gate",
        "",
        "Phase 08 report is complete. Per plan, stop before Phase 09 ablations.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    run_id = args.output_dir.name
    output = args.output_dir
    if output.exists() and any(output.iterdir()) and not args.allow_existing_output:
        raise FileExistsError(f"Output directory already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.config_file.read_text(encoding="utf-8"))
    base = args.api_base.rstrip("/")
    started_at = time.time()
    session_id = ""
    timeseries: list[dict] = []
    resources: list[dict] = []
    source_info: dict[str, Any] = {}
    initial_session: dict[str, Any] = {}
    final_session: dict[str, Any] = {}
    api_log_signals: dict[str, Any] = {"error": "", "lines": []}

    try:
        source_info = _http_json("POST", f"{base}/live/resolve", {"url": args.source_url}, timeout=args.resolve_timeout_s)
        validation = _http_json("POST", f"{base}/live/validate-config", {"lane_config": config}, timeout=30)
        if not validation.get("valid"):
            raise RuntimeError(f"Live config is invalid: {validation.get('errors')}")
        initial_session = _http_json(
            "POST",
            f"{base}/live/sessions",
            {
                "source_url": source_info.get("source_url") or source_info.get("resolved_url") or args.source_url,
                "lane_config": config,
                "frame_skip": args.frame_skip,
            },
            timeout=60,
        )
        session_id = str(initial_session["session_id"])
        end_at = started_at + args.duration_s
        sample_index = 0
        while time.time() < end_at:
            sample_started = time.time()
            status = _http_json("GET", f"{base}/live/sessions/{session_id}", timeout=30)
            frame = _http_frame(f"{base}/live/sessions/{session_id}/frame", timeout=10)
            flat = _flatten_status(status)
            flat.update(frame)
            flat.update(
                {
                    "run_id": run_id,
                    "sample_index": sample_index,
                    "timestamp": round(sample_started, 3),
                    "elapsed_s": round(sample_started - started_at, 3),
                    "phase": "warmup" if sample_started - started_at < args.warmup_s else "steady_state",
                }
            )
            timeseries.append(flat)
            resource = _resource_sample(args.api_container)
            resource.update(
                {
                    "run_id": run_id,
                    "sample_index": sample_index,
                    "timestamp": round(time.time(), 3),
                    "elapsed_s": round(time.time() - started_at, 3),
                    "phase": flat["phase"],
                }
            )
            resources.append(resource)
            final_session = status
            sample_index += 1
            if status.get("status") in {"failed", "ended", "stopped"}:
                break
            sleep_for = args.sample_interval_s - (time.time() - sample_started)
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        ended_at = time.time()
        if session_id:
            try:
                final_session = _http_json("GET", f"{base}/live/sessions/{session_id}", timeout=30)
            except Exception:
                pass
            try:
                _http_json("DELETE", f"{base}/live/sessions/{session_id}/remove", timeout=30)
            except Exception:
                try:
                    _http_json("DELETE", f"{base}/live/sessions/{session_id}", timeout=30)
                except Exception:
                    pass
        api_log_signals = _filtered_api_logs(args.api_container, started_at)

    _add_deltas(timeseries)
    summary = _summarize(
        args=args,
        run_id=run_id,
        source_info=source_info,
        initial_session=initial_session,
        final_session=final_session or initial_session,
        timeseries=timeseries,
        resources=resources,
        api_log_signals=api_log_signals,
        started_at=started_at,
        ended_at=ended_at,
    )
    status_fields = [
        "run_id", "sample_index", "timestamp", "elapsed_s", "phase", "status", "uptime_s",
        "frames_read", "frames_processed", "frames_dropped", "snapshot_fps",
        "latest_frame_seq", "lane_volume_total", "global_unique_count",
        "latest_track_count", "last_error", "model_name", "roi_mode", "ai_imgsz",
        *PERF_FIELDS, "raw_det", "kept_det", "active_tracks", "lost_tracks",
        "dropped_reason", "reader_cropped", "reader_output", "frame_fetch_status",
        "frame_fetch_bytes", "frame_fetch_content_type", "frame_fetch_seq",
        "frame_fetch_error", "sample_dt_s", "read_fps_sample",
        "processed_fps_sample", "published_fps_sample", "dropped_delta",
        "processed_delta", "published_delta",
    ]
    resource_fields = [
        "run_id", "sample_index", "timestamp", "elapsed_s", "phase", "gpu_util_pct",
        "vram_used_mb", "vram_total_mb", "host_cpu_pct", "host_ram_used_mb",
        "api_container_cpu_pct", "api_container_mem_used_mb", "api_container_mem_pct",
        "api_container_pids",
    ]
    _write_csv(output / "live_runtime_timeseries.csv", timeseries, status_fields)
    _write_csv(output / "live_resource_timeseries.csv", resources, resource_fields)
    _write_json(output / "live_runtime_summary.json", summary)
    _write_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "created_at": _now_iso(),
            "run_id": run_id,
            "source_url": args.source_url,
            "resolved_source_type": source_info.get("source_type", ""),
            "resolved_width": source_info.get("width", 0),
            "resolved_height": source_info.get("height", 0),
            "resolved_fps": source_info.get("fps", 0),
            "config_file": str(args.config_file).replace("\\", "/"),
            "duration_s": args.duration_s,
            "warmup_s": args.warmup_s,
            "sample_interval_s": args.sample_interval_s,
            "frame_skip": args.frame_skip,
            "api_base": args.api_base,
            "session_id": session_id,
            "artifacts": {
                "timeseries": "live_runtime_timeseries.csv",
                "resource_timeseries": "live_resource_timeseries.csv",
                "summary": "live_runtime_summary.json",
                "api_log_signals": "api_log_signals.txt",
            },
        },
    )
    (output / "api_log_signals.txt").write_text("\n".join(api_log_signals.get("lines", [])), encoding="utf-8")

    if args.reports_dir:
        _write_csv(args.reports_dir / "live_runtime_timeseries.csv", timeseries, status_fields)
        _write_csv(args.reports_dir / "live_resource_timeseries.csv", resources, resource_fields)
        _write_report(args.reports_dir / "live_runtime_report.md", summary, output)
    if args.docs_report:
        _write_report(args.docs_report, summary, output)
    if args.portfolio_report:
        _write_report(args.portfolio_report, summary, output)
    if args.wiki_report:
        _write_report(args.wiki_report, summary, output)
    return {"output_dir": str(output).replace("\\", "/"), "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=1800.0)
    parser.add_argument("--warmup-s", type=float, default=60.0)
    parser.add_argument("--sample-interval-s", type=float, default=5.0)
    parser.add_argument("--stall-threshold-s", type=float, default=15.0)
    parser.add_argument("--frame-skip", type=int, default=1)
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--api-container", default="trafficflow-api-1")
    parser.add_argument("--resolve-timeout-s", type=float, default=60.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, default=Path("benchmark/reports"))
    parser.add_argument("--docs-report", type=Path, default=Path("docs/reports/phase-08-live-runtime.md"))
    parser.add_argument("--portfolio-report", type=Path, default=Path("docs/portfolio/runtime-optimization-case-study.md"))
    parser.add_argument("--wiki-report", type=Path, default=Path("docs/wiki/ai-workflow/phase-08-live-runtime.md"))
    parser.add_argument("--allow-existing-output", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
