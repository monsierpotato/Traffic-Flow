from pydantic import BaseModel

class UploadResponse(BaseModel):
    video_id: str
    preview_url: str
    message: str
