import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import redis
from shared.config import settings
from shared import database
from api.routes.router import v1_router
from api.services import cleanup_service
from api.services.live_service import live_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _scheduled_cleanup() -> None:
    """Stable scheduler entrypoint; keeps the service dependency patchable in tests."""
    await cleanup_service.run_data_cleanup()
    removed_sessions = live_manager.cleanup_stale()
    if removed_sessions:
        logger.info("Removed %s stale live sessions.", removed_sessions)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    await database.connect_to_mongo()
    
    # Start the data cleanup background scheduler
    # Runs the cleanup job once every hour
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_cleanup,
        "interval",
        hours=1,
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
    app = FastAPI(
        title="TrafficFlow Backend API",
        description="FastAPI Backend for video upload, lane config, and vehicle count queuing",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files for local storage mockup (R2 mock)
    # If the local storage mock is enabled, we serve it under /static
    storage_dir = Path(settings.STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(storage_dir)), name="static")
    logger.info("Mounted static directory 'storage' at '/static'")

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
            # Never log or return the broker URL: managed Redis URLs commonly
            # contain a password in the authority component.
            logger.warning("Redis queue is not ready")
        finally:
            if redis_client is not None:
                redis_client.close()
        worker_ready = True
        worker_reason = None
        worker_mode = "remote" if not settings.AI_LOCAL else "local"
        if settings.AI_LOCAL:
            model_path = Path(settings.resolved_model_path())
            if not model_path.is_file():
                worker_ready = False
                worker_reason = "model_missing"
            else:
                try:
                    import torch  # noqa: F401
                    import ultralytics  # noqa: F401
                except Exception:
                    worker_ready = False
                    worker_reason = "local_inference_unavailable"

            # The worker factory deliberately falls back to remote serving for
            # these deployment conditions. Reflect that same contract in
            # readiness instead of reporting a false hard block.
            if not worker_ready and settings.AI_SERVING_URL and settings.AI_SERVING_URL != "local":
                worker_ready = True
                worker_mode = "remote_fallback"

        worker_status = "ready" if queue_ready and worker_ready else "blocked"
        production_env = settings.APP_ENV.lower() in {"production", "prod"}
        callback_auth_ready = not production_env or bool(settings.CALLBACK_TOKEN)
        payload = {
            "status": "ready" if queue_ready and worker_ready and callback_auth_ready else "degraded",
            "database": "local_json" if database.db_instance.using_local_fallback else "mongodb",
            "queue": {
                "configured": bool(settings.REDIS_URL),
                "status": "ready" if queue_ready else "blocked",
            },
            "worker": {"status": worker_status, "mode": worker_mode, "reason": worker_reason},
            "security": {
                "callback_auth": "ready" if callback_auth_ready else "blocked",
                "reason": None if callback_auth_ready else "callback_token_missing",
            },
        }
        return payload if queue_ready and worker_ready and callback_auth_ready else JSONResponse(status_code=503, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            "Validation error on %s %s: %s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.middleware("http")
    async def log_requests(request, call_next):
        logger.info("Incoming request: %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response

    # Serve built frontend static files
    frontend_dist_dir = Path("frontend/dist")
    if frontend_dist_dir.exists():
        frontend_index = frontend_dist_dir / "index.html"

        @app.get("/", include_in_schema=False)
        async def frontend_index_response():
            # Returning the small shell as HTML avoids a Starlette
            # FileResponse/ASGITransport deadlock while preserving the normal
            # static mount for hashed JS/CSS assets and browser navigation.
            if not frontend_index.is_file():
                return HTMLResponse("Frontend build is not available.", status_code=404)
            return HTMLResponse(frontend_index.read_text(encoding="utf-8"))

        app.mount("/", StaticFiles(directory=str(frontend_dist_dir), html=True), name="frontend")
        logger.info("Mounted frontend dist directory at '/'")
    else:
        logger.warning(f"Frontend dist directory not found at {frontend_dist_dir}. Frontend will not be served via FastAPI.")

    return app
