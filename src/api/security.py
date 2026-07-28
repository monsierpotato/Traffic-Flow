"""Security boundaries shared by HTTP routes and worker-side URL ingestion."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status

from shared.config import settings


PUBLIC_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}


def is_callback_path(path: str) -> bool:
    return path.startswith("/api/v1/tasks/progress/")


def is_protected_path(path: str) -> bool:
    if path.startswith(("/api/", "/live")):
        return True
    if path == "/videos" or path.startswith("/videos/"):
        return True
    if path == "/tasks" or path.startswith("/tasks/"):
        return True
    if path == "/video" or path.startswith("/video/"):
        return True
    if path == "/static" or path.startswith("/static/"):
        return True
    return False


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _validate_host(hostname: str) -> None:
    try:
        if not _is_public_ip(hostname):
            raise ValueError("private IP")
        return
    except ValueError:
        # Hostnames are resolved before the connection is opened. Reject the
        # request if any resolved address points at a non-public network.
        pass

    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise HTTPException(status_code=422, detail="Source host could not be resolved") from exc
    if not addresses or any(not _is_public_ip(address) for address in addresses):
        raise HTTPException(status_code=422, detail="Private or local source networks are not allowed")


def validate_external_url(raw_url: str, *, allow_youtube: bool = False) -> str:
    """Validate a user-controlled media URL before any subprocess/network call."""
    url = raw_url.strip()
    parsed = urlparse(url)
    allowed_schemes = {item.strip().lower() for item in settings.LIVE_ALLOWED_SCHEMES.split(",") if item.strip()}
    if parsed.scheme.lower() not in allowed_schemes:
        raise HTTPException(status_code=422, detail="Unsupported source URL scheme")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Source URL credentials are not accepted")
    if not parsed.hostname:
        raise HTTPException(status_code=422, detail="Source URL must include a host")
    if settings.LIVE_BLOCK_PRIVATE_NETWORKS:
        _validate_host(parsed.hostname)
    return url


def is_exact_youtube_host(hostname: str | None) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return host == "youtube.com" or host.endswith(".youtube.com") or host == "youtu.be"


def require_database(db):
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready",
        )
    return db


def client_identity(request: Request) -> str:
    """Use a stable low-cardinality key for shared rate limiting."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")
