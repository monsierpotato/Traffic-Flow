import asyncio

import httpx
import pytest
from fastapi import HTTPException

from api.app import create_app
from api.routes.live import _is_youtube_url
from api.security import validate_external_url
from shared.config import settings


def run(coro):
    return asyncio.run(coro)


def test_auth_covers_compatibility_and_asset_boundaries(monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "test-token")

    async def request():
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return [
                await client.get(path)
                for path in (
                    "/videos/demo/preview",
                    "/tasks/demo",
                    "/video/chunk",
                    "/static/local_db.json",
                    "/api/v1/upload/assets/results/demo.mp4",
                )
            ]

    assert [response.status_code for response in run(request())] == [401] * 5


def test_private_source_networks_are_rejected():
    with pytest.raises(HTTPException):
        validate_external_url("http://127.0.0.1:8000/internal")
    with pytest.raises(HTTPException):
        validate_external_url("file:///etc/passwd")


def test_youtube_host_matching_is_exact():
    assert _is_youtube_url("https://www.youtube.com/watch?v=demo")
    assert _is_youtube_url("https://youtu.be/demo")
    assert not _is_youtube_url("https://evil-youtube.com/watch?v=demo")
