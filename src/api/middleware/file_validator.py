import os
from fastapi import UploadFile, HTTPException, status
from shared.config import settings

def validate_video_file(file: UploadFile) -> UploadFile:
    """Validates the uploaded file size, extension and mime type."""
    # 1. Validate Extension
    filename = file.filename or ""
    _, ext = os.path.splitext(filename.lower())
    if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension {ext}. Allowed extensions: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}"
        )

    # Starlette's UploadFile is backed by a seekable spool. Check the actual
    # size with a seek instead of scanning the entire file before the route
    # copies it to the processing path.
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    try:
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
    except (AttributeError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not seekable",
        ) from exc

    if size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )
    if size > max_bytes:
        size_mb = size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File is too large ({size_mb:.2f}MB). Max allowed size is {settings.MAX_FILE_SIZE_MB}MB."
        )

    # Read only the first chunk for magic-byte/MIME validation, then restore
    # the cursor so saving starts at byte zero.
    first_chunk = file.file.read(min(1024 * 1024, size))
    if not first_chunk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # Check mime type using python-magic
    try:
        import magic
        mime = magic.from_buffer(first_chunk, mime=True)
    except Exception:
        # Fallback if magic/dll is not found on Windows
        import mimetypes
        mime, _ = mimetypes.guess_type(filename)
        if mime is None:
            mime = "video/mp4" # Default fallback guess

    if not mime.startswith("video/") and mime not in [
        "application/octet-stream",  # Sometimes returned for raw containers like mkv/avi
        "application/x-matroska",
        "video/x-matroska",
        "video/mp4",
        "video/quicktime",
        "video/x-msvideo"
    ]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid MIME type {mime}. The file must be a valid video."
        )

    # Reset file pointer so the route can copy the complete upload.
    file.file.seek(0)
    return file
