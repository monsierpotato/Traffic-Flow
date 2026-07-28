import logging
import hmac
import uuid
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import redis
from shared.config import settings
from shared import database
from shared.r2_client import r2_client
from api.routes.router import v1_router
from api.services import cleanup_service
from api.security import is_callback_path, is_protected_path
from api.middleware.rate_limiter import check_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _scheduled_cleanup() -> None:
    """Stable scheduler entrypoint; keeps the service dependency patchable in tests."""
    await cleanup_service.run_data_cleanup()
    await cleanup_service.cleanup_expired_chunk_sessions()
    await cleanup_service.reconcile_stale_tasks()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    if settings.API_AUTH_REQUIRED and not settings.API_AUTH_TOKEN:
        raise RuntimeError("API_AUTH_REQUIRED is enabled but API_AUTH_TOKEN is empty")
    if settings.APP_ENV.lower() in {"prod", "production"}:
        required = {
            "API_AUTH_REQUIRED": settings.API_AUTH_REQUIRED,
            "API_AUTH_TOKEN": bool(settings.API_AUTH_TOKEN),
            "CALLBACK_TOKEN": bool(settings.CALLBACK_TOKEN),
            "MONGODB_LOCAL_FALLBACK=false": not settings.MONGODB_LOCAL_FALLBACK,
            "R2_URL_MODE=presigned": settings.R2_URL_MODE == "presigned",
            "RATE_LIMIT_ENABLED": settings.RATE_LIMIT_ENABLED,
            "API_DOCS_ENABLED=false": not settings.API_DOCS_ENABLED,
            "LIVE_BLOCK_PRIVATE_NETWORKS": settings.LIVE_BLOCK_PRIVATE_NETWORKS,
        }
        invalid = [name for name, valid in required.items() if not valid]
        if invalid:
            raise RuntimeError(f"Unsafe production configuration: {', '.join(invalid)}")
        if not settings.CALLBACK_HOST or any(host in settings.CALLBACK_HOST.lower() for host in ("127.0.0.1", "localhost")):
            raise RuntimeError("CALLBACK_HOST must be a reachable service URL in production")
    await database.connect_to_mongo()
    
    # Start the data cleanup background scheduler
    # Runs the cleanup job once every hour
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_cleanup,
        "interval",
        minutes=10,
        id="data_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    app.state.cleanup_scheduler = scheduler
    logger.info("Data cleanup background scheduler started.")

    try:
        yield
    finally:
        # --- Shutdown ---
        if scheduler.running:
            scheduler.shutdown(wait=False)
        logger.info("Data cleanup background scheduler stopped.")
        await database.close_mongo_connection()

def create_app() -> FastAPI:
    docs_url = "/docs" if settings.API_DOCS_ENABLED else None
    redoc_url = "/redoc" if settings.API_DOCS_ENABLED else None
    openapi_url = "/openapi.json" if settings.API_DOCS_ENABLED else None
    app = FastAPI(
        title="TrafficFlow Backend API",
        description="FastAPI Backend for video upload, lane config, and vehicle count queuing",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
    )

    # Never expose the entire storage directory. Private assets are served by
    # authenticated, key-scoped endpoints in the upload router.
    storage_dir = Path(settings.STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Private storage directory initialized without a public static mount")

    # Include V1 API Router
    app.include_router(v1_router, prefix="/api/v1")

    # Frontend compatibility routes (maps /videos/*, /tasks/* to API)
    from api.routes.frontend_compat import router as compat_router
    from api.routes.live import router as live_router
    app.include_router(compat_router)
    app.include_router(live_router, prefix="/live", tags=["Live Compat"])

    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "service": "trafficflow-api"}

    @app.get("/ready", tags=["System"])
    async def ready():
        if database.db_instance.db is None:
            return JSONResponse(status_code=503, content={"status": "not_ready", "database": "disconnected"})
        queue_ready = False
        redis_client = None
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
                socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            )
            redis_client.ping()
            queue_ready = True
        except Exception:
            logger.warning("Redis queue is not ready at %s", settings.REDIS_URL)
        finally:
            if redis_client is not None:
                redis_client.close()
        payload = {
            "status": "ready" if queue_ready else "degraded",
            "database": "local_json" if database.db_instance.using_local_fallback else "mongodb",
            "queue": {"url": settings.REDIS_URL, "status": "ready" if queue_ready else "blocked"},
            "storage": r2_client.health_summary(),
        }
        return payload if queue_ready else JSONResponse(status_code=503, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            "request_validation_failed request_id=%s method=%s path=%s error_count=%s",
            getattr(request.state, "request_id", "unknown"),
            request.method,
            request.url.path,
            len(exc.errors()),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.middleware("http")
    async def log_requests(request, call_next):
        started_at = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        protected_path = is_protected_path(request.url.path) or (
            settings.API_AUTH_REQUIRED and request.url.path in {"/docs", "/redoc", "/openapi.json"}
        )
        public_path = request.url.path in {"/health", "/ready"}
        if not public_path:
            rate_limited = await check_request(request)
            if rate_limited is not None:
                rate_limited.headers["X-Request-ID"] = request_id
                return rate_limited
        if settings.API_AUTH_REQUIRED and protected_path and not public_path:
            supplied = request.headers.get("authorization", "")
            expected = f"Bearer {settings.API_AUTH_TOKEN}"
            callback_authenticated = False
            if is_callback_path(request.url.path) and settings.CALLBACK_TOKEN:
                callback_authenticated = hmac.compare_digest(supplied, f"Bearer {settings.CALLBACK_TOKEN}")
            api_authenticated = bool(settings.API_AUTH_TOKEN) and hmac.compare_digest(supplied, expected)
            if not (callback_authenticated or (api_authenticated and not is_callback_path(request.url.path))):
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required", "request_id": request_id},
                )
                response.headers["X-Request-ID"] = request_id
                return response

        logger.info(
            "request_started request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path == "/videos" or request.url.path.startswith(("/videos/", "/tasks", "/video/")):
            response.headers.setdefault("Deprecation", "true")
            response.headers.setdefault("X-API-Canonical", "/api/v1")
        if settings.APP_ENV.lower() in {"prod", "production"}:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        logger.info(
            "request_finished request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started_at) * 1000,
        )
        return response

    # Serve built frontend static files
    frontend_dist_dir = Path("frontend/dist")
    if frontend_dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist_dir), html=True), name="frontend")
        logger.info("Mounted frontend dist directory at '/'")
    else:
        logger.warning(f"Frontend dist directory not found at {frontend_dist_dir}. Frontend will not be served via FastAPI.")

    return app
