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

    # Live stream ingest configuration
    LIVE_READER_BACKEND: str = Field(default="auto")  # auto | ffmpeg | opencv
    LIVE_FFMPEG_BIN: str = Field(default="ffmpeg")
    LIVE_FFPROBE_BIN: str = Field(default="ffprobe")
    LIVE_FFMPEG_LOGLEVEL: str = Field(default="warning")
    LIVE_FFPROBE_TIMEOUT_S: int = Field(default=15)
    LIVE_FFMPEG_RW_TIMEOUT_US: int = Field(default=10000000)
    LIVE_FFMPEG_OUTPUT_FPS: int = Field(default=15)
    LIVE_FFMPEG_REALTIME_PACING: bool = Field(default=True)
    LIVE_FRAME_QUEUE_SIZE: int = Field(default=1, ge=1, le=1)
    LIVE_MAX_FRAME_AGE_SECONDS: float = Field(default=0.25, gt=0)
    LIVE_TRACK_MIN_HITS: int = Field(default=3, ge=1)
    LIVE_TRACK_MAX_LOST_SECONDS: float = Field(default=0.7, gt=0)
    LIVE_TRACK_RESET_GAP_SECONDS: float = Field(default=1.0, gt=0)
    LIVE_RECONNECT_ATTEMPTS: int = Field(default=3, ge=0)
    LIVE_RECONNECT_DELAY_SECONDS: float = Field(default=1.0, ge=0)

    # Cloudflare R2 configurations
    R2_ACCOUNT_ID: str = Field(default="placeholder_account_id")
    R2_ACCESS_KEY_ID: str = Field(default="placeholder_access_key")
    R2_SECRET_ACCESS_KEY: str = Field(default="placeholder_secret_key")
    R2_BUCKET_NAME: str = Field(default="trafficflow")
    R2_PUBLIC_URL: str = Field(default="http://localhost:8000/static")

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
    AI_CONFIDENCE: float = Field(default=0.4)
    AI_IOU: float = Field(default=0.45)
    AI_MAX_DET: int = Field(default=100)
    AI_AGNOSTIC_NMS: bool = Field(default=False)
    AI_FRAME_SKIP: int = Field(default=1)  # Process every Nth frame; 0/1 = every frame
    AI_RESIZE_DIM: int = Field(default=640)  # Resize longest side to this px before inference
    AI_ENABLE_STABILIZATION: bool = Field(default=False)

    # ROI crop configuration
    ROI_MODE: str = Field(default="crop_rect")  # crop_rect | roi_crop | roi_mask | full_frame
    ROI_CROP_PADDING: float = Field(default=0.10)
    OUTPUT_FRAME_MODE: str = Field(default="roi")  # roi | full_frame
    ROI_INPUT_SIZE: int = Field(default=640)  # Target square size for letterbox pad

    # Local tracker (Kalman filter) configuration
    TRACK_MATCH_THRESHOLD: float = Field(default=0.3, description="IoU threshold for matching detections to tracks")
    TRACK_BUFFER: int = Field(default=8, description="Max frames to keep a lost track alive via Kalman prediction")
    RENDER_SHOW_LOST: bool = Field(default=False)
    RENDER_SHOW_OUT_OF_ZONE: bool = Field(default=False)
    RENDER_DEBUG: bool = Field(default=False)
    TRACK_FILTER_ZONE_PADDING_PX: float = Field(default=12.0)

# Global settings instance
settings = Settings()
