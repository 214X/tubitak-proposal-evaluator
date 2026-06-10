from fastapi import APIRouter

from app.api.routes.analysis import router as analysis_router
from app.api.routes.chunking import router as chunking_router
from app.api.routes.embedding import router as embedding_router
from app.api.routes.extraction import router as extraction_router
from app.api.routes.health import router as health_router
from app.api.routes.uploads import router as uploads_router

api_router = APIRouter()
api_router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
api_router.include_router(chunking_router, prefix="/chunking", tags=["chunking"])
api_router.include_router(embedding_router, prefix="/embedding", tags=["embedding"])
api_router.include_router(extraction_router, prefix="/extraction", tags=["extraction"])
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(uploads_router, prefix="/uploads", tags=["uploads"])
