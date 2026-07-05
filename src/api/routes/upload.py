import uuid
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request, status
from lib.database import get_database
from lib.r2_client import r2_client
from api.middleware.file_validator import validate_video_file
from api.services.video_service import extract_first_frame
from api.schemas.upload import UploadResponse

router = APIRouter()

@router.post("/video", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    request: Request,
    file: UploadFile = Depends(validate_video_file),
    db = Depends(get_database)
):
    """Uploads video file, extracts first frame, saves both to Cloudflare R2,
    and initializes a task document in MongoDB.
    """
    video_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    
    try:
        # 1. Read file bytes
        video_bytes = await file.read()
        
        # 2. Upload video to R2
        video_key = f"uploads/{video_id}.mp4"
        video_url = r2_client.upload_file(
            file_content=video_bytes,
            key=video_key,
            content_type=file.content_type or "video/mp4"
        )
        
        # 3. Extract preview frame
        try:
            preview_bytes = extract_first_frame(video_bytes)
        except Exception as e:
            # Clean up uploaded video if extraction fails
            r2_client.delete_file(video_key)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Could not extract preview frame from video: {str(e)}"
            )
            
        # 4. Upload preview frame to R2
        preview_key = f"previews/{video_id}.jpg"
        r2_client.upload_file(
            file_content=preview_bytes,
            key=preview_key,
            content_type="image/jpeg"
        )

        # 5. Also save preview locally for frontend display
        local_preview_dir = Path("storage/previews")
        local_preview_dir.mkdir(parents=True, exist_ok=True)
        local_preview_path = local_preview_dir / f"{video_id}.jpg"
        local_preview_path.write_bytes(preview_bytes)

        # Build local preview URL that works via /static/ mount
        base_url = str(request.base_url).rstrip("/")
        local_preview_url = f"{base_url}/static/previews/{video_id}.jpg"
        
        # 6. Create Task document in MongoDB
        now = datetime.utcnow()
        from backend.config import settings
        expires_at = now + timedelta(days=settings.RETENTION_DAYS)
        
        task_doc = {
            "task_id": task_id,
            "video_id": video_id,
            "status": "uploaded",
            "progress": 0,
            "video_url": video_url,
            "preview_url": local_preview_url,
            "result_video_url": None,
            "events_url": None,
            "error_message": None,
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at
        }
        
        await db.tasks.insert_one(task_doc)
        
        return UploadResponse(
            video_id=video_id,
            preview_url=local_preview_url,
            message="Video uploaded and preview generated successfully."
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while uploading: {str(e)}"
        )

