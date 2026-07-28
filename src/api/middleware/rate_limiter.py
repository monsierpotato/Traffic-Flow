"""Redis-backed request limiting shared by all API replicas."""

from __future__ import annotations

import asyncio
import time

import redis
from fastapi import Request
from fastapi.responses import JSONResponse

from api.security import client_identity
from shared.config import settings


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            decode_responses=True,
        )
    return _client


def _check(identity: str) -> tuple[bool, int]:
    window = int(time.time() // settings.RATE_LIMIT_WINDOW_SECONDS)
    key = f"trafficflow:ratelimit:{window}:{identity}"
    client = _get_client()
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS + 1)
    return count <= settings.RATE_LIMIT_REQUESTS, max(0, settings.RATE_LIMIT_REQUESTS - count)


async def check_request(request: Request):
    if not settings.RATE_LIMIT_ENABLED:
        return None
    try:
        allowed, remaining = await asyncio.to_thread(_check, client_identity(request))
    except Exception:
        # Fail closed in production; a missing limiter must never silently
        # remove an abuse-control boundary.
        if settings.APP_ENV.lower() in {"prod", "production"}:
            return JSONResponse(status_code=503, content={"detail": "Rate limiter unavailable"})
        return None
    if not allowed:
        response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        response.headers["Retry-After"] = str(settings.RATE_LIMIT_WINDOW_SECONDS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
    return None
