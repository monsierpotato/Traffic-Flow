"""Route-level tests for the source-id handoff into the live runtime."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from api.routes import live
from api.services.youtube_resolver import ResolvedMedia


def _valid_lane_config() -> dict:
    return {
        "resolution": {"width": 100, "height": 100},
        "processing_roi": {"x": 0, "y": 0, "width": 100, "height": 100},
        "roi_polygon": [[0, 0], [99, 0], [99, 99]],
        "lanes": [{
            "lane_id": "lane_1",
            "valid_zone": [[0, 0], [99, 0], [99, 99]],
            "counting_line": [[10, 50], [90, 50]],
            "direction": [[10, 40], [10, 60]],
        }],
    }


def test_create_session_uses_server_side_resolved_url(monkeypatch) -> None:
    captured: dict = {}
    source = {
        "source_id": "source-1",
        "original_url": "https://www.youtube.com/live/example",
        "resolved_url": "https://manifest.googlevideo.com/video.m3u8?sig=secret",
        "resolved_expires_at": None,
    }

    class FakeManager:
        def list(self):
            return []

        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(snapshot=lambda: {"status": "starting"})

    monkeypatch.setattr(live, "live_manager", FakeManager())
    monkeypatch.setattr(live, "_get_source", lambda source_id: source)

    response = asyncio.run(live.create_live_session(
        live.LiveSessionCreate(
            source_url=source["original_url"],
            source_id=source["source_id"],
            lane_config=_valid_lane_config(),
        )
    ))

    assert response["status"] == "starting"
    assert captured["source_url"] == source["resolved_url"]
    assert captured["source_origin_url"] == source["original_url"]


def test_create_session_resolves_legacy_youtube_page_url(monkeypatch) -> None:
    captured: dict = {}

    class FakeManager:
        def list(self):
            return []

        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(snapshot=lambda: {"status": "starting"})

    monkeypatch.setattr(live, "live_manager", FakeManager())
    monkeypatch.setattr(
        live,
        "_resolve_media",
        lambda url: ResolvedMedia("https://manifest.googlevideo.com/video.m3u8?sig=secret", 9999),
    )

    async def resolve_inline(function, *args):
        return function(*args)

    monkeypatch.setattr(live.asyncio, "to_thread", resolve_inline)

    original = "https://youtu.be/example"
    asyncio.run(live.create_live_session(
        live.LiveSessionCreate(source_url=original, lane_config=_valid_lane_config())
    ))

    assert captured["source_origin_url"] == original
    assert captured["source_url"].startswith("https://manifest.googlevideo.com/")
