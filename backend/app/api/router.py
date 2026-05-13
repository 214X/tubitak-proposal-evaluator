from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.uploads import router as uploads_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(uploads_router, prefix="/uploads", tags=["uploads"])
