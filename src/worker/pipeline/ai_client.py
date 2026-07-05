"""HTTP client for Modal GPU inference service (/v1/detect)."""

import logging
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, Future
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

logger = logging.getLogger(__name__)


def _retry_session(retries=3, backoff=1.0, status_forcelist=(500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries, read=retries, connect=retries,
        backoff_factor=backoff, status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST", "PUT", "DELETE"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


class InferenceClient:
    """Modal GPU inference client with session management + pipelining.

    Uses Modal's /v1/detect endpoint (which runs YOLO + ByteTrack).
    Worker-side LocalTracker strips Modal's track_ids and re-tracks locally
    to gain Kalman velocity + lost-track prediction.

    Pipelining: frame N's HTTP request runs in a background thread while
    the caller prepares frame N+1+skip.
    """

    def __init__(self, base_url: str, max_workers: int = 2, request_timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self._session = _retry_session()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._session_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self) -> str:
        url = f"{self.base_url}/v1/session"
        logger.info(f"Creating AI session: {url}")
        resp = self._session.post(url, timeout=max(self.request_timeout, 60))
        resp.raise_for_status()
        self._session_id = resp.json()["session_id"]
        logger.info(f"AI session created: {self._session_id}")
        return self._session_id

    def delete_session(self):
        if not self._session_id:
            return
        url = f"{self.base_url}/v1/session/{self._session_id}"
        try:
            resp = self._session.delete(url, timeout=30)
            resp.raise_for_status()
            logger.info(f"AI session deleted: {self._session_id}")
        except Exception as e:
            logger.warning(f"Failed to delete session {self._session_id}: {e}")
        self._session_id = None

    # ------------------------------------------------------------------
    # Single-frame detect (blocking — used inside ThreadPoolExecutor)
    # ------------------------------------------------------------------

    def _detect_one(self, jpeg_bytes: bytes) -> List[dict]:
        url = f"{self.base_url}/v1/detect"
        resp = self._session.post(
            url,
            files={"image": ("frame.jpg", jpeg_bytes, "image/jpeg")},
            data={"session_id": self._session_id, "confidence": 0.1},
            timeout=self.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("detections", [])

    # ------------------------------------------------------------------
    # Pipelined submission
    # ------------------------------------------------------------------

    def submit_frame(self, jpeg_bytes: bytes) -> Future:
        return self._executor.submit(self._detect_one, jpeg_bytes)

    def shutdown(self, wait: bool = False):
        self._executor.shutdown(wait=wait)
