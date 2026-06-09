from fastapi import APIRouter, Header

from app.services.extraction.models import ExtractionOutput, ParserOutput
from app.services.extraction.service import get_current_extraction_output, get_current_parser_output

router = APIRouter()


@router.post("/current/extraction-output", response_model=ExtractionOutput)
def read_current_extraction_output(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> ExtractionOutput:
    return get_current_extraction_output(x_session_id)


@router.post("/current/parser-output", response_model=ParserOutput)
def read_current_parser_output(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> ParserOutput:
    return get_current_parser_output(x_session_id)
