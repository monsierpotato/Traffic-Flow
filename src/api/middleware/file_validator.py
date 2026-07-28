import os
from fastapi import UploadFile, HTTPException, status
from shared.config import settings

def validate_video_file(file: UploadFile) -> UploadFile:
    """Validates the uploaded file size, extension and mime type."""
    # 1. Validate Extension
    filename = file.filename
    if not filename or "\x00" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A safe video filename is required.",
        )
    # The original filename is metadata only; never allow path components to
    # influence a storage key or temporary path.
    file.filename = os.path.basename(filename)
    filename = file.filename
    _, ext = os.path.splitext(filename.lower())
    if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension {ext}. Allowed extensions: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}"
        )

    # 2. Validate Size (read a chunk or check Content-Length if available)
    # Check if we can get size via content-length
    content_length = file.headers.get("content-length")
    if content_length:
        size_mb = int(content_length) / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File is too large ({size_mb:.2f}MB). Max allowed size is {settings.MAX_FILE_SIZE_MB}MB."
            )

    # Alternatively, read file data in chunks to prevent memory blowup and check size
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    chunk_size = 1024 * 1024  # 1MB
    size = 0
    # We read first chunk to validate magic bytes (MIME type)
    first_chunk = file.file.read(chunk_size)
    size += len(first_chunk)
    
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
        # Keep local development usable when libmagic is unavailable, but do
        # not silently accept an unknown type as MP4.
        import mimetypes
        mime, _ = mimetypes.guess_type(filename)
        if mime is None:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Could not verify the uploaded video media type.",
            )

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

    # Verify rest of the size
    while True:
        chunk = file.file.read(chunk_size)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
            )

    # Reset file pointer so it can be read again for saving
    file.file.seek(0)
    return file
