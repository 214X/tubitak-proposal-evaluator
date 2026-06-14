from fastapi import APIRouter, Header, HTTPException, Query, Response, status

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


@router.get("/current/report.pdf")
def download_current_report_pdf(
    session_id: str = Query(..., alias="session_id"),
) -> Response:
    """Tamamlanmış değerlendirme raporunu UI'a benzer bir PDF olarak indirir.

    session_id query parametresiyle alınır; doğrudan URL/indirme bağlantısı (özel header
    gönderemeyen <a>/window.open) bu uçtan PDF çekebilsin diye.
    """
    state = get_current_evaluation_state(session_id)
    if state.final_report is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rapor henüz hazır değil. Değerlendirmenin tamamlanmasını bekleyin.",
        )

    from app.services.reporting.pdf_renderer import render_report_pdf

    pdf_bytes = render_report_pdf(state.final_report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="degerlendirme-raporu.pdf"',
        },
    )
