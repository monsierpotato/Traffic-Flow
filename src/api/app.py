import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from shared.config import settings
from shared.database import connect_to_mongo, close_mongo_connection
from api.routes.router import v1_router
from api.services.cleanup_service import run_data_cleanup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scheduler for the data retention cleanup task
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    await connect_to_mongo()
    
    # Start the data cleanup background scheduler
    # Runs the cleanup job once every hour
    scheduler.add_job(run_data_cleanup, 'interval', hours=1, id='data_cleanup')
    scheduler.start()
    logger.info("Data cleanup background scheduler started.")
    
    yield
    
    # --- Shutdown ---
    scheduler.shutdown()
    logger.info("Data cleanup background scheduler stopped.")
    await close_mongo_connection()

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
        allow_origins=["*"],  # Adjust for production security
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files for local storage mockup (R2 mock)
    # If the local storage mock is enabled, we serve it under /static
    app.mount("/static", StaticFiles(directory="storage"), name="static")
    logger.info("Mounted static directory 'storage' at '/static'")

    # Include V1 API Router
    app.include_router(v1_router, prefix="/api/v1")

    # Frontend compatibility routes (maps /videos/*, /tasks/* to API)
    from api.routes.frontend_compat import router as compat_router
    from api.routes.live import router as live_router
    app.include_router(compat_router)
    app.include_router(live_router, prefix="/live", tags=["Live Compat"])

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
    from pathlib import Path
    frontend_dist_dir = Path("frontend/dist")
    if frontend_dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist_dir), html=True), name="frontend")
        logger.info("Mounted frontend dist directory at '/'")
    else:
        logger.warning(f"Frontend dist directory not found at {frontend_dist_dir}. Frontend will not be served via FastAPI.")

    return app
