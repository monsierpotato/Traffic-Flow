from fastapi import APIRouter
from api.routes.upload import router as upload_router
from api.routes.lanes import router as lanes_router
from api.routes.tasks import router as tasks_router
from api.routes.dashboard import router as dashboard_router

v1_router = APIRouter()

# Register sub-routes
v1_router.include_router(upload_router, prefix="/upload", tags=["Upload"])
v1_router.include_router(lanes_router, prefix="/lanes", tags=["Lane Configuration"])
v1_router.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
