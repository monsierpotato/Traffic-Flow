import io

import pytest
from fastapi import UploadFile
from fastapi import HTTPException
from starlette.datastructures import Headers

from api.middleware.file_validator import validate_video_file
from api.services import video_service
from shared.config import settings


class _CountingBytesIO(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1):
        self.read_sizes.append(size)
        return super().read(size)


def _upload(stream: io.BytesIO) -> UploadFile:
    return UploadFile(
        file=stream,
        filename="sample.mp4",
        headers=Headers({"content-type": "video/mp4"}),
    )


def test_validator_checks_size_without_scanning_entire_upload():
    stream = _CountingBytesIO(b"\x00\x00\x00\x18ftypmp42" + b"x" * (2 * 1024 * 1024))

    validate_video_file(_upload(stream))

    assert stream.tell() == 0
    assert stream.read_sizes == [1024 * 1024]


def test_validator_rejects_oversized_upload_before_reading_payload(monkeypatch):
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    stream = _CountingBytesIO(b"x" * (1024 * 1024 + 1))

    with pytest.raises(HTTPException) as error:
        validate_video_file(_upload(stream))

    assert error.value.status_code == 413
    assert stream.read_sizes == []


def test_video_metadata_uses_ffprobe_fields_without_opening_opencv(tmp_path, monkeypatch):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    monkeypatch.setattr(video_service, "_ffprobe_stream_meta", lambda _path: {
        "width": 1920,
        "height": 1080,
        "avg_frame_rate": "30000/1001",
        "nb_frames": "300",
        "duration": "10.01",
        "codec_name": "h264",
        "pix_fmt": "yuv420p",
    })
    monkeypatch.setattr(
        video_service,
        "_opencv_video_meta",
        lambda _path: pytest.fail("OpenCV metadata fallback should not run"),
    )

    meta = video_service._get_video_meta(str(video_path))

    assert (meta.width, meta.height) == (1920, 1080)
    assert meta.fps == pytest.approx(30000 / 1001)
    assert meta.duration_s == pytest.approx(10.01)
    assert meta.codec == "h264"
