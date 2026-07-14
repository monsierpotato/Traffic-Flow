"""Benchmark profiler — collects per-stage timing and resource metrics."""

import time
import threading
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

import logging

logger = logging.getLogger(__name__)


@dataclass
class FrameTiming:
    frame_idx: int
    decode_ms: float = 0.0
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    tracking_ms: float = 0.0
    counting_ms: float = 0.0
    overlay_ms: float = 0.0
    encode_ms: float = 0.0
    total_frame_ms: float = 0.0


@dataclass
class StageStats:
    name: str
    total_ms: float = 0.0
    count: int = 0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0


@dataclass
class ResourceSample:
    timestamp: float
    gpu_util_pct: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    cpu_pct: float = 0.0
    ram_used_mb: float = 0.0


@dataclass
class BenchmarkResult:
    task_id: str
    model_path: str
    device: str
    imgsz: int
    half: bool
    frame_skip: int
    video_resolution: str
    video_fps: float
    total_frames: int
    processed_frames: int
    video_id: str = ""
    total_ms: float = 0.0
    download_ms: float = 0.0
    upload_ms: float = 0.0
    counts: dict = field(default_factory=dict)
    lane_volume_total: int = 0
    global_unique_count: int = 0
    multi_lane_track_count: int = 0
    multi_lane_tracks: List[dict] = field(default_factory=list)
    frame_timings: List[FrameTiming] = field(default_factory=list)
    stage_stats: Dict[str, StageStats] = field(default_factory=dict)
    resource_samples: List[ResourceSample] = field(default_factory=list)

    @property
    def effective_fps(self) -> float:
        if self.total_ms <= 0:
            return 0.0
        return self.processed_frames / (self.total_ms / 1000.0)

    @property
    def realtime_factor(self) -> float:
        if self.total_ms <= 0 or self.video_fps <= 0:
            return 0.0
        video_duration_s = self.total_frames / self.video_fps
        process_s = self.total_ms / 1000.0
        return video_duration_s / process_s if process_s > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "model_path": self.model_path,
            "device": self.device,
            "imgsz": self.imgsz,
            "half": self.half,
            "frame_skip": self.frame_skip,
            "video_id": self.video_id,
            "video_resolution": self.video_resolution,
            "video_fps": self.video_fps,
            "total_frames": self.total_frames,
            "processed_frames": self.processed_frames,
            "total_sec": round(self.total_ms / 1000.0, 3),
            "effective_fps": round(self.effective_fps, 2),
            "realtime_factor": round(self.realtime_factor, 2),
            "download_sec": round(self.download_ms / 1000.0, 3),
            "upload_sec": round(self.upload_ms / 1000.0, 3),
            "stages": {
                name: {
                    "avg_ms": round(s.avg_ms, 3),
                    "p50_ms": round(s.p50_ms, 3),
                    "p95_ms": round(s.p95_ms, 3),
                    "p99_ms": round(s.p99_ms, 3),
                    "min_ms": round(s.min_ms, 3),
                    "max_ms": round(s.max_ms, 3),
                    "count": s.count,
                    "total_sec": round(s.total_ms / 1000.0, 3),
                }
                for name, s in self.stage_stats.items()
            },
            "resource": {
                "gpu_util_avg_pct": _safe_avg([s.gpu_util_pct for s in self.resource_samples]),
                "vram_peak_mb": max((s.vram_used_mb for s in self.resource_samples), default=0),
                "cpu_avg_pct": _safe_avg([s.cpu_pct for s in self.resource_samples]),
                "ram_peak_mb": max((s.ram_used_mb for s in self.resource_samples), default=0),
            },
            "counts": self.counts,
            "lane_volume_total": self.lane_volume_total,
            "global_unique_count": self.global_unique_count,
            "multi_lane_track_count": self.multi_lane_track_count,
            "multi_lane_tracks": self.multi_lane_tracks,
        }


class StageTimer:
    """Context-manager timer for measuring individual pipeline stages."""

    def __init__(self, collector: "PipelineProfiler", stage_name: str, frame_idx: int = -1):
        self._collector = collector
        self._stage_name = stage_name
        self._frame_idx = frame_idx
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed_ms = (time.perf_counter() - self._start) * 1000.0
        self._collector.record_stage(self._stage_name, self._frame_idx, elapsed_ms)


class PipelineProfiler:
    """Collects per-frame stage timings and periodic resource samples."""

    def __init__(self, sample_interval_s: float = 2.0):
        self.frame_timings: List[FrameTiming] = []
        self.resource_samples: List[ResourceSample] = []
        self._stage_buckets: Dict[str, List[float]] = defaultdict(list)
        self._sample_interval = sample_interval_s
        self._last_sample = 0.0
        self._sampler_thread: Optional[threading.Thread] = None
        self._stop_sampler = threading.Event()
        self._frame_starts: Dict[int, float] = {}

    def start_frame(self, frame_idx: int):
        self._frame_starts[frame_idx] = time.perf_counter()

    def end_frame(self, frame_idx: int):
        start = self._frame_starts.pop(frame_idx, None)
        if start is not None:
            elapsed = (time.perf_counter() - start) * 1000.0
            ft = self._get_or_create_timing(frame_idx)
            ft.total_frame_ms = elapsed

    def record_stage(self, stage_name: str, frame_idx: int, elapsed_ms: float):
        ft = self._get_or_create_timing(frame_idx)
        setattr(ft, f"{stage_name}_ms", getattr(ft, f"{stage_name}_ms", 0.0) + elapsed_ms)
        self._stage_buckets[stage_name].append(elapsed_ms)

    def _get_or_create_timing(self, frame_idx: int) -> FrameTiming:
        while len(self.frame_timings) <= frame_idx:
            self.frame_timings.append(FrameTiming(frame_idx=len(self.frame_timings)))
        ft = self.frame_timings[frame_idx]
        if ft.frame_idx != frame_idx:
            ft = FrameTiming(frame_idx=frame_idx)
            self.frame_timings[frame_idx] = ft
        return ft

    def start_resource_sampler(self):
        self._stop_sampler.clear()
        self._sampler_thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._sampler_thread.start()

    def stop_resource_sampler(self):
        self._stop_sampler.set()
        if self._sampler_thread:
            self._sampler_thread.join(timeout=2.0)

    def _sample_loop(self):
        while not self._stop_sampler.is_set():
            sample = self._collect_resources()
            self.resource_samples.append(sample)
            self._stop_sampler.wait(self._sample_interval)

    def _collect_resources(self) -> ResourceSample:
        gpu_util, vram_used, vram_total = 0.0, 0.0, 0.0
        cpu_pct, ram_used = 0.0, 0.0

        try:
            import subprocess
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            if res.returncode == 0:
                parts = res.stdout.strip().split(",")
                if len(parts) >= 3:
                    gpu_util = float(parts[0].strip())
                    vram_used = float(parts[1].strip())
                    vram_total = float(parts[2].strip())
        except Exception:
            pass

        try:
            import psutil
            cpu_pct = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            ram_used = mem.used / (1024 * 1024)
        except Exception:
            pass

        return ResourceSample(
            timestamp=time.time(),
            gpu_util_pct=gpu_util,
            vram_used_mb=vram_used,
            vram_total_mb=vram_total,
            cpu_pct=cpu_pct,
            ram_used_mb=ram_used,
        )

    def compute_stage_stats(self) -> Dict[str, StageStats]:
        stats = {}
        for name, values in self._stage_buckets.items():
            if not values:
                continue
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            stats[name] = StageStats(
                name=name,
                total_ms=sum(sorted_vals),
                count=n,
                p50_ms=sorted_vals[int(n * 0.50)],
                p95_ms=sorted_vals[int(n * 0.95)],
                p99_ms=sorted_vals[int(n * 0.99)],
                min_ms=min(sorted_vals),
                max_ms=max(sorted_vals),
            )
        return stats

    def timer(self, stage_name: str, frame_idx: int = -1) -> StageTimer:
        return StageTimer(self, stage_name, frame_idx)


def _safe_avg(values: list) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0
