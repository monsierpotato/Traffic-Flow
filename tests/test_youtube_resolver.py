"""Deterministic tests for YouTube source resolution and source hardening."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.services import youtube_resolver
from api.routes.live import _public_source
from shared.config import settings


def test_youtube_hostname_matching_is_exact() -> None:
    assert youtube_resolver.is_youtube_url("https://www.youtube.com/live/abc")
    assert youtube_resolver.is_youtube_url("https://youtu.be/abc")
    assert not youtube_resolver.is_youtube_url("https://evil-youtube.com/live/abc")
    assert not youtube_resolver.is_youtube_url("https://youtube.com.evil.example/live/abc")


def test_media_url_expiration_is_read_and_refresh_margin_is_applied(monkeypatch) -> None:
    url = "https://manifest.googlevideo.com/video.m3u8?expire=1100&sig=secret"
    media = youtube_resolver.ResolvedMedia(url=url, expires_at=youtube_resolver._expiration_from_url(url))

    monkeypatch.setattr(settings, "YTDLP_REFRESH_MARGIN_SECONDS", 120)
    assert media.expires_at == 1100
    assert youtube_resolver.media_url_needs_refresh(media.expires_at, now=1000)
    assert not youtube_resolver.media_url_needs_refresh(media.expires_at, now=900)


def test_resolver_uses_private_cookie_copy_and_removes_it(tmp_path: Path, monkeypatch) -> None:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setattr(settings, "YTDLP_COOKIES_FILE", str(cookies))
    monkeypatch.setattr(settings, "YTDLP_JS_RUNTIME", "")
    monkeypatch.setattr(settings, "YTDLP_REMOTE_COMPONENTS", "")

    captured: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        cookie_index = command.index("--cookies") + 1
        cookie_path = Path(command[cookie_index])
        assert cookie_path.exists()
        assert cookie_path.read_text(encoding="utf-8") == cookies.read_text(encoding="utf-8")
        assert cookie_path.parent != Path(settings.STORAGE_DIR) / "live_previews"
        return SimpleNamespace(stdout="https://manifest.googlevideo.com/video.m3u8?expire=9999", stderr="")

    monkeypatch.setattr(youtube_resolver.subprocess, "run", fake_run)
    media = youtube_resolver.resolve_youtube_url("https://www.youtube.com/live/abc")

    assert media.url.startswith("https://manifest.googlevideo.com/")
    cookie_path = Path(captured["command"][captured["command"].index("--cookies") + 1])
    assert not cookie_path.exists()


def test_resolver_timeout_is_reported_as_gateway_timeout(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=45)

    monkeypatch.setattr(youtube_resolver.subprocess, "run", fake_run)
    with pytest.raises(youtube_resolver.SourceResolutionError) as raised:
        youtube_resolver.resolve_youtube_url("https://youtu.be/abc")
    assert raised.value.status_code == 504


def test_production_blocks_private_direct_sources(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "LIVE_BLOCK_PRIVATE_HOSTS", True)
    with pytest.raises(youtube_resolver.SourceResolutionError):
        youtube_resolver.validate_direct_source_url("http://127.0.0.1:8000/live.m3u8")


def test_local_allows_private_direct_sources_for_development(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "LIVE_BLOCK_PRIVATE_HOSTS", True)
    youtube_resolver.validate_direct_source_url("http://127.0.0.1:8000/live.m3u8")


def test_public_source_hides_signed_url_and_preview_path() -> None:
    source = {
        "source_id": "source",
        "original_url": "https://www.youtube.com/live/example",
        "resolved_url": "https://manifest.googlevideo.com/video.m3u8?sig=secret",
        "source_url": "https://manifest.googlevideo.com/video.m3u8?sig=secret",
        "preview_path": "storage/live_previews/source.jpg",
        "source_type": "youtube_hls",
    }

    public = _public_source(source)

    assert public["source_url"] == source["original_url"]
    assert "resolved_url" not in public
    assert "preview_path" not in public
