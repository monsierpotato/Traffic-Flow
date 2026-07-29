"""Create a worker inference client with one consistent fallback policy."""

from __future__ import annotations

import logging

from shared.config import settings
from worker.pipeline.ai_client import InferenceClient
from worker.pipeline.local_client import LocalInferenceClient

logger = logging.getLogger(__name__)


def build_inference_client(*, max_workers: int = 1, imgsz: int | None = None):
    """Prefer local inference, then use the configured remote service.

    Batch and live processing must make the same decision.  Local model or
    optional dependency failures are expected deployment conditions, so they
    fall back to remote serving when a URL is configured; programming errors
    still surface normally.
    """
    use_local = settings.AI_LOCAL or settings.AI_SERVING_URL == "local"
    if use_local:
        try:
            kwargs = {"max_workers": max_workers}
            if imgsz is not None:
                kwargs["imgsz"] = imgsz
            return LocalInferenceClient(**kwargs)
        except (ImportError, ModuleNotFoundError, FileNotFoundError, OSError) as exc:
            if not settings.AI_SERVING_URL or settings.AI_SERVING_URL == "local":
                raise RuntimeError(
                    "Local inference is unavailable and AI_SERVING_URL is not configured"
                ) from exc
            logger.warning(
                "Local inference unavailable (%s); falling back to remote serving",
                exc.__class__.__name__,
            )

    if not settings.AI_SERVING_URL or settings.AI_SERVING_URL == "local":
        raise RuntimeError("AI_SERVING_URL must be configured when local inference is disabled")
    return InferenceClient(base_url=settings.AI_SERVING_URL, max_workers=max_workers, request_timeout=30)
