from fastapi import APIRouter, Header, status

from app.services.evaluation.models import EvaluationState
from app.services.evaluation.service import (
    get_current_evaluation_state,
    start_current_evaluation,
)

router = APIRouter()


@router.post("/current/start", response_model=EvaluationState, status_code=status.HTTP_202_ACCEPTED)
def start_evaluation_for_current_session(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> EvaluationState:
    return start_current_evaluation(x_session_id)


@router.get("/current", response_model=EvaluationState)
def read_current_evaluation(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> EvaluationState:
    return get_current_evaluation_state(x_session_id)
