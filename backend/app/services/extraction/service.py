from __future__ import annotations

from fastapi import HTTPException, status

from app.services.extraction.docling_extractor import extract_pdf_with_docling
from app.services.extraction.models import ExtractionOutput, ParserOutput
from app.services.extraction.parser import parse_docling_content_stream, parse_heading_hierarchy
from app.services.upload.service import get_session_upload_path


def get_current_extraction_output(session_id: str) -> ExtractionOutput:
    file_path = get_session_upload_path(session_id)

    if file_path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extraction output is currently only available for PDF files.",
        )

    return extract_pdf_with_docling(file_path)


def get_current_parser_output(session_id: str) -> ParserOutput:
    extraction_output = get_current_extraction_output(session_id)
    content_stream = parse_docling_content_stream(extraction_output.docling_output)
    heading_hierarchy = parse_heading_hierarchy(content_stream)

    return ParserOutput(
        document=extraction_output.document.model_dump(),
        docling_output=extraction_output.docling_output,
        content_stream=content_stream,
        heading_hierarchy=heading_hierarchy,
    )
