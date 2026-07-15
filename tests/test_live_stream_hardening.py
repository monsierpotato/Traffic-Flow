import os

# `shared.config.settings` is intentionally a process singleton.  Set the
# repository's test values before importing the live service so this focused
# test can also run before the broader API integration module.
os.environ.setdefault("MONGODB_DB_NAME", "trafficflow_test")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("R2_ACCOUNT_ID", "placeholder_account_id")
os.environ.setdefault("R2_ACCESS_KEY_ID", "placeholder_access_key")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "placeholder_secret_key")
os.environ.setdefault("R2_BUCKET_NAME", "trafficflow")
os.environ.setdefault("R2_PUBLIC_URL", "http://localhost:8000/static/previews")
os.environ.setdefault("AI_SERVING_URL", "https://example.com")

import time

from api.services.live_service import FfmpegLatestFrameReader, FramePacer, _normalize_even_crop_rect
from worker.pipeline.tracker import LocalTracker


class _ShortReadPipe:
    def __init__(self, payload: bytes, chunk_size: int):
        self.payload = payload
        self.chunk_size = chunk_size
        self.offset = 0

    def readinto(self, view):
        if self.offset >= len(self.payload):
            return 0
        size = min(len(view), self.chunk_size, len(self.payload) - self.offset)
        view[:size] = self.payload[self.offset:self.offset + size]
        self.offset += size
        return size


class _Process:
    def __init__(self, stdout):
        self.stdout = stdout


def test_raw_reader_joins_short_pipe_reads_into_one_frame():
    reader = FfmpegLatestFrameReader("unused")
    reader._proc = _Process(_ShortReadPipe(b"abcdefgh", chunk_size=3))

    assert reader._read_exact(8) == b"abcdefgh"


def test_crop_is_clipped_and_forced_to_even_dimensions():
    assert _normalize_even_crop_rect((3, 5, 100, 80), 1920, 1080) == (3, 5, 99, 79)
    assert _normalize_even_crop_rect((0, 0, 1, 10), 1920, 1080) is None


def test_frame_pacer_resets_after_network_stall_without_playback_catchup():
    pacer = FramePacer(2.0)
    pacer.next_emit = time.monotonic() - 1.0

    started = time.monotonic()
    pacer.wait()

    assert time.monotonic() - started < 0.05
    assert pacer.next_emit > time.monotonic()


def test_live_tracker_matches_large_motion_by_predicted_distance():
    tracker = LocalTracker(match_threshold=0.3, track_buffer=8, max_lost_seconds=0.7)
    first = tracker.update([{"bbox_xyxy": [0, 0, 50, 50], "class_name": "car"}], timestamp=10.0)
    second = tracker.update([{"bbox_xyxy": [100, 0, 150, 50], "class_name": "car"}], timestamp=10.1)

    assert first[0].track_id == second[0].track_id
    assert second[0].hits == 2


def test_live_tracker_expires_lost_track_by_elapsed_time():
    tracker = LocalTracker(track_buffer=99, max_lost_seconds=0.7)
    tracker.update([{"bbox_xyxy": [0, 0, 50, 50], "class_name": "car"}], timestamp=10.0)

    assert tracker.update([], timestamp=10.8) == []
