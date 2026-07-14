import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # MongoDB configurations
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/")
    MONGODB_DB_NAME: str = Field(default="trafficflow")
    MONGODB_LOCAL_FALLBACK: bool = Field(default=True)
    LOCAL_DB_PATH: str = Field(default="storage/local_db.json")
    YTDLP_COOKIES_FILE: str = Field(default="")
    YTDLP_JS_RUNTIME: str = Field(default="")
    YTDLP_REMOTE_COMPONENTS: str = Field(default="")

    # Cloudflare R2 configurations
    R2_ACCOUNT_ID: str = Field(default="placeholder_account_id")
    R2_ACCESS_KEY_ID: str = Field(default="placeholder_access_key")
    R2_SECRET_ACCESS_KEY: str = Field(default="placeholder_secret_key")
    R2_BUCKET_NAME: str = Field(default="trafficflow")
    R2_PUBLIC_URL: str = Field(default="http://localhost:8000/static/previews")

    # Redis/Celery configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_QUEUE_NAME: str = Field(default="trafficflow_queue")

    # Validation rules
    MAX_FILE_SIZE_MB: int = Field(default=2048)
    ALLOWED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    RETENTION_DAYS: int = Field(default=3)

    # Video normalization (4K → 1080p working copy)
    VIDEO_MAX_WIDTH: int = Field(default=1920)
    VIDEO_MAX_HEIGHT: int = Field(default=1080)
    VIDEO_MAX_FPS: int = Field(default=30)
    VIDEO_NORMALIZE_ENABLED: bool = Field(default=True)
    VIDEO_TRANSCODE_PRESET: str = Field(default="veryfast")  # ffmpeg preset: ultrafast/veryfast/fast/medium
    VIDEO_TRANSCODE_CRF: int = Field(default=20)
    STORE_ORIGINAL_VIDEO: bool = Field(default=False)

    # AI Serving (Local GPU / Modal GPU) configuration
    AI_LOCAL: bool = Field(default=False)
    AI_SERVING_URL: str = Field(default="https://tienpm205--trafficflow-inference-fastapi-app.modal.run")
    AI_MODEL_PATH: str = Field(default="models/yolov8n.pt")
    AI_DEVICE: str = Field(default="0")
    AI_IMGSZ: int = Field(default=640)
    AI_HALF: bool = Field(default=True)
    AI_CLASS_IDS: str = Field(default="2,3,5,7")
    AI_CLASS_NAME_MAP: str = Field(default="")
    AI_CONFIDENCE: float = Field(default=0.1)
    AI_FRAME_SKIP: int = Field(default=2)  # Process every Nth frame (max 3)
    AI_RESIZE_DIM: int = Field(default=640)  # Resize longest side to this px before inference
    AI_ENABLE_STABILIZATION: bool = Field(default=False)

    # ROI crop configuration
    ROI_MODE: str = Field(default="roi_crop")  # roi_crop | roi_mask | full_frame
    ROI_INPUT_SIZE: int = Field(default=640)  # Target square size for letterbox pad

    # Local tracker (Kalman filter) configuration
    TRACK_MATCH_THRESHOLD: float = Field(default=0.5, description="IoU threshold for matching detections to tracks")
    TRACK_BUFFER: int = Field(default=30, description="Max frames to keep a lost track alive via Kalman prediction")

# Global settings instance
settings = Settings()
