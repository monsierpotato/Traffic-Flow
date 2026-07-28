"""Safe, testable resolution of YouTube page URLs into short-lived media URLs.

The live pipeline intentionally consumes media URLs rather than YouTube metadata.
This module keeps the provider-specific work out of the HTTP route and makes it
possible for the live session to refresh a URL after a signed URL expires.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from shared.config import settings


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


class SourceResolutionError(RuntimeError):
    """Raised when a source cannot be converted into a playable media URL."""

    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ResolvedMedia:
    url: str
    expires_at: Optional[float] = None

    @property
    def source_type(self) -> str:
        return "youtube_hls" if ".m3u8" in self.url.lower() else "youtube_media"


def is_youtube_url(url: str) -> bool:
    """Return true only for an actual supported YouTube hostname."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    return parsed.scheme in {"http", "https"} and host in YOUTUBE_HOSTS


def redact_process_detail(detail: str) -> str:
    detail = re.sub(r"https?://\S+", "<redacted-url>", detail or "")
    detail = re.sub(r"(?i)(signature|token|key|oauth_token)=[^&\s]+", r"\1=<redacted>", detail)
    return detail.strip()[-600:]


def _expiration_from_url(url: str) -> Optional[float]:
    """Read YouTube's signed `expire` query parameter when present."""
    try:
        values = parse_qs(urlparse(url).query).get("expire") or []
        if values and float(values[0]) > 0:
            return float(values[0])
    except (TypeError, ValueError):
        pass
    return None


def media_url_needs_refresh(expires_at: Optional[float], now: Optional[float] = None) -> bool:
    if expires_at is None:
        return False
    current = time.time() if now is None else now
    return expires_at - current <= settings.YTDLP_REFRESH_MARGIN_SECONDS


def _temporary_cookies_file(source_path: str) -> tuple[str, bool]:
    """Copy cookies to a private temp file and return (path, owned_by_us)."""
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise SourceResolutionError("Configured YouTube cookies file is missing", status_code=422)
    fd, target = tempfile.mkstemp(prefix="trafficflow-yt-", suffix=".cookies")
    os.close(fd)
    os.chmod(target, 0o600)
    try:
        Path(target).write_bytes(source.read_bytes())
    except Exception as exc:
        try:
            os.unlink(target)
        except OSError:
            pass
        raise SourceResolutionError("Could not prepare YouTube cookies file", status_code=500) from exc
    return target, True


def resolve_youtube_url(url: str) -> ResolvedMedia:
    """Resolve a YouTube page URL without persisting or returning credentials."""
    if not is_youtube_url(url):
        raise SourceResolutionError("Only supported YouTube page URLs can be resolved", status_code=422)

    options: list[str] = []
    temporary_cookie_path: Optional[str] = None
    if settings.YTDLP_COOKIES_FILE:
        temporary_cookie_path, _ = _temporary_cookies_file(settings.YTDLP_COOKIES_FILE)
        options.extend(["--cookies", temporary_cookie_path])
    if settings.YTDLP_JS_RUNTIME:
        options.extend(["--js-runtimes", settings.YTDLP_JS_RUNTIME])
    if settings.YTDLP_REMOTE_COMPONENTS:
        options.extend(["--remote-components", settings.YTDLP_REMOTE_COMPONENTS])

    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        *options,
        "--no-warnings",
        "--no-playlist",
        "--get-url",
        "-f",
        "best[protocol^=m3u8]/best",
        url,
    ]
    try:
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=settings.YTDLP_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise SourceResolutionError("yt-dlp is not installed in the API environment", status_code=500) from exc
        except subprocess.TimeoutExpired as exc:
            raise SourceResolutionError("YouTube source resolution timed out", status_code=504) from exc
        except subprocess.CalledProcessError as exc:
            detail = redact_process_detail(exc.stderr or exc.stdout or "yt-dlp failed")
            raise SourceResolutionError(
                f"Could not resolve YouTube URL with yt-dlp: {detail or 'provider rejected the source'}",
                status_code=422,
            ) from exc
    finally:
        if temporary_cookie_path:
            try:
                os.unlink(temporary_cookie_path)
            except OSError:
                pass

    urls = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not urls:
        raise SourceResolutionError("yt-dlp did not return a playable media URL", status_code=422)
    media_url = urls[0]
    return ResolvedMedia(url=media_url, expires_at=_expiration_from_url(media_url))


def validate_direct_source_url(url: str) -> None:
    """Reject malformed sources and obvious private-network SSRF targets."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https", "rtsp"} or not parsed.hostname:
        raise SourceResolutionError("Source URL must use http, https, or rtsp", status_code=422)
    if not settings.LIVE_BLOCK_PRIVATE_HOSTS or settings.APP_ENV.lower() not in {"production", "prod"}:
        return
    host = parsed.hostname
    try:
        addresses = {host}
        addresses.update(info[4][0] for info in socket.getaddrinfo(host, None))
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                continue
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise SourceResolutionError("Private or local source hosts are not allowed", status_code=422)
    except socket.gaierror as exc:
        raise SourceResolutionError("Source hostname could not be resolved", status_code=422) from exc
