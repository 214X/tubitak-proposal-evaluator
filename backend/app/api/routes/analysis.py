from fastapi import APIRouter, Header, status

from app.services.analysis.models import AnalysisState
from app.services.analysis.service import (
    get_current_analysis_state,
    start_current_analysis,
    start_current_analysis_until_chunking,
)

router = APIRouter()


@router.post("/current/start", response_model=AnalysisState, status_code=status.HTTP_202_ACCEPTED)
def start_analysis_for_current_upload(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> AnalysisState:
    return start_current_analysis(x_session_id)


@router.post("/current/start-until-chunking", response_model=AnalysisState, status_code=status.HTTP_202_ACCEPTED)
def start_analysis_until_chunking_for_current_upload(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> AnalysisState:
    return start_current_analysis_until_chunking(x_session_id)


@router.get("/current", response_model=AnalysisState)
def read_current_analysis(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> AnalysisState:
    return get_current_analysis_state(x_session_id)
