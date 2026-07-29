"""Helpers for keeping provider credentials and signed URLs out of responses."""

from __future__ import annotations

import re


_URL_WITH_USERINFO = re.compile(
    r"(?i)\b(?P<scheme>https?|rtsp|redis|rediss|mongodb(?:\+srv)?|s3)://[^\s/@]+(?::[^\s/@]*)?@"
)
_SIGNED_QUERY = re.compile(
    r"(?i)([?&](?:signature|sig|token|key|oauth_token|x-amz-[^=]+)=)[^&\s]+"
)
_PLAIN_SECRET = re.compile(
    r"(?i)\b(password|passwd|secret|access_token|api_key|token)=([^\s,;]+)"
)


def safe_error_message(error: BaseException, *, limit: int = 500) -> str:
    """Return a useful bounded error without leaking connection credentials."""
    detail = str(error).strip() or error.__class__.__name__
    detail = _URL_WITH_USERINFO.sub(r"\g<scheme>://<redacted>@", detail)
    detail = _SIGNED_QUERY.sub(r"\1<redacted>", detail)
    detail = _PLAIN_SECRET.sub(r"\1=<redacted>", detail)
    return detail[:limit]


def redact_url_credentials(url: str) -> str:
    """Remove userinfo from a URL while preserving the playable URL shape."""
    return _URL_WITH_USERINFO.sub(r"\g<scheme>://", url or "", count=1)
