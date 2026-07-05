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

    # Cloudflare R2 configurations
    R2_ACCOUNT_ID: str = Field(default="placeholder_account_id")
    R2_ACCESS_KEY_ID: str = Field(default="placeholder_access_key")
    R2_SECRET_ACCESS_KEY: str = Field(default="placeholder_secret_key")
    R2_BUCKET_NAME: str = Field(default="trafficflow")
    R2_PUBLIC_URL: str = Field(default="http://localhost:8000/static/previews")

    # Redis/Celery configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Validation rules
    MAX_FILE_SIZE_MB: int = Field(default=50)
    ALLOWED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".avi", ".mov", ".mkv", ".webm"]

    # Data retention settings
    RETENTION_DAYS: int = Field(default=3)

    # AI Serving (Modal GPU) configuration
    AI_SERVING_URL: str = Field(default="https://tienpm205--trafficflow-inference-fastapi-app.modal.run")
    AI_FRAME_SKIP: int = Field(default=2)  # Process every Nth frame (max 3)
    AI_RESIZE_DIM: int = Field(default=640)  # Resize longest side to this px before Modal
    AI_ENABLE_STABILIZATION: bool = Field(default=True)

    # Local tracker (Kalman filter) configuration
    TRACK_MATCH_THRESHOLD: float = Field(default=0.5, description="IoU threshold for matching detections to tracks")
    TRACK_BUFFER: int = Field(default=30, description="Max frames to keep a lost track alive via Kalman prediction")

# Global settings instance
settings = Settings()
