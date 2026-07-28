import logging
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
from api.routes.router import v1_router
from api.services import cleanup_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _scheduled_cleanup() -> None:
    """Stable scheduler entrypoint; keeps the service dependency patchable in tests."""
    await cleanup_service.run_data_cleanup()


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
            logger.warning("Redis queue is not ready at %s", settings.REDIS_URL)
        finally:
            if redis_client is not None:
                redis_client.close()
        payload = {
            "status": "ready" if queue_ready else "degraded",
            "database": "local_json" if database.db_instance.using_local_fallback else "mongodb",
            "queue": {"url": settings.REDIS_URL, "status": "ready" if queue_ready else "blocked"},
        }
        return payload if queue_ready else JSONResponse(status_code=503, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.error(f"Validation error on {request.method} {request.url}")
        logger.error(f"Validation details: {exc.errors()}")
        try:
            body = await request.body()
            logger.error(f"Request body: {body.decode('utf-8', errors='replace')[:2000]}")
        except Exception:
            pass
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.middleware("http")
    async def log_requests(request, call_next):
        logger.info(f"Incoming request: {request.method} {request.url}")
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response

    # Serve built frontend static files
    frontend_dist_dir = Path("frontend/dist")
    if frontend_dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist_dir), html=True), name="frontend")
        logger.info("Mounted frontend dist directory at '/'")
    else:
        logger.warning(f"Frontend dist directory not found at {frontend_dist_dir}. Frontend will not be served via FastAPI.")

    return app
