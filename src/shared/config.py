from typing import List, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

from shared.runtime_paths import resolve_model_path

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
    MONGODB_TLS: bool = Field(default=False)
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = Field(default=1500, ge=100, le=120000)
    MONGODB_CONNECT_TIMEOUT_MS: int = Field(default=1500, ge=100, le=120000)
    MONGODB_STRICT_INDEXES: bool = Field(default=True)
    LOCAL_DB_PATH: str = Field(default="storage/local_db.json")
    APP_ENV: str = Field(default="local")
    CORS_ORIGINS: str = Field(default="http://127.0.0.1:8080")
    CALLBACK_HOST: str = Field(default="")
    CALLBACK_TOKEN: str = Field(default="")
    CALLBACK_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0, le=120)
    CALLBACK_RETRY_ATTEMPTS: int = Field(default=4, ge=0, le=10)
    CALLBACK_RETRY_BACKOFF_SECONDS: float = Field(default=1.0, ge=0, le=30)
    # Pilot deployments can enable a single service token at the API edge.
    # Full user/RBAC authentication remains a separate product layer.
    API_AUTH_REQUIRED: bool = Field(default=False)
    API_AUTH_TOKEN: str = Field(default="")
    API_DOCS_ENABLED: bool = Field(default=True)
    RATE_LIMIT_ENABLED: bool = Field(default=False)
    RATE_LIMIT_REQUESTS: int = Field(default=120, ge=1, le=100000)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
    TASK_STALE_TIMEOUT_SECONDS: int = Field(default=3600, ge=60, le=604800)
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
    LIVE_MAX_SESSIONS: int = Field(default=4, ge=1, le=1000)
    LIVE_MAX_SESSIONS_PER_CLIENT: int = Field(default=2, ge=1, le=100)
    LIVE_SESSION_TTL_SECONDS: int = Field(default=86400, ge=60, le=604800)
    LIVE_ALLOWED_SCHEMES: str = Field(default="http,https,rtsp")
    LIVE_BLOCK_PRIVATE_NETWORKS: bool = Field(default=True)

    # Cloudflare R2 configurations
    R2_ACCOUNT_ID: str = Field(default="placeholder_account_id")
    R2_ACCESS_KEY_ID: str = Field(default="placeholder_access_key")
    R2_SECRET_ACCESS_KEY: str = Field(default="placeholder_secret_key")
    R2_BUCKET_NAME: str = Field(default="trafficflow")
    R2_PUBLIC_URL: str = Field(default="http://localhost:8000/api/v1/upload/assets")
    R2_URL_MODE: Literal["public", "presigned"] = Field(default="public")
    R2_PRESIGNED_URL_TTL_SECONDS: int = Field(default=3600, ge=60, le=604800)

    # Redis/Celery configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_CONNECT_TIMEOUT_SECONDS: float = Field(default=0.5, gt=0, le=30)
    CELERY_QUEUE_NAME: str = Field(default="trafficflow_queue")
    CELERY_VISIBILITY_TIMEOUT_SECONDS: int = Field(default=7200, ge=60, le=604800)

    # Validation rules
    MAX_FILE_SIZE_MB: int = Field(default=2048)
    MAX_CHUNK_SIZE_MB: int = Field(default=64, ge=1, le=2048)
    CHUNK_SESSION_TTL_SECONDS: int = Field(default=86400, ge=300, le=604800)
    ALLOWED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    RETENTION_DAYS: int = Field(default=3)
    STORAGE_DIR: str = Field(default="storage")

    # Video normalization (4K → 1080p working copy)
    VIDEO_MAX_WIDTH: int = Field(default=1920)
    VIDEO_MAX_HEIGHT: int = Field(default=1080)
    VIDEO_MAX_FPS: int = Field(default=30)
    VIDEO_NORMALIZE_ENABLED: bool = Field(default=True)
    VIDEO_TRANSCODE_PRESET: str = Field(default="veryfast")  # ffmpeg preset: ultrafast/veryfast/fast/medium
    VIDEO_TRANSCODE_CRF: int = Field(default=20)
    STORE_ORIGINAL_VIDEO: bool = Field(default=False)

    # Local inference is the supported default; remote serving remains an
    # explicit compatibility fallback for deployments that set AI_LOCAL=false.
    AI_LOCAL: bool = Field(default=True)
    AI_SERVING_URL: str = Field(default="https://tienpm205--trafficflow-inference-fastapi-app.modal.run")
    AI_SERVING_TOKEN: str = Field(default="")
    AI_MODEL_DIR: str = Field(default="inference/models")
    AI_MODEL_PATH: str = Field(default="yolov8n.pt")
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

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def resolved_model_path(self) -> str:
        return resolve_model_path(self.AI_MODEL_PATH, self.AI_MODEL_DIR)

# Global settings instance
settings = Settings()
