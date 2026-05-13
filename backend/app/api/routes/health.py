from fastapi import APIRouter

from app.services.health.schemas import HealthResponse
from app.services.health.service import get_health_status

router = APIRouter()


@router.get("", response_model=HealthResponse)
def read_health() -> HealthResponse:
    return get_health_status()
