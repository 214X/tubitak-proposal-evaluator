from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock, Thread

from app.services.analysis.models import AnalysisState
from app.services.analysis.store import read_analysis_state, write_analysis_state
from app.services.extraction.docling_extractor import extract_pdf_with_docling
from app.services.extraction.models import ExtractionOutput
from app.services.extraction.models import ParserOutput
from app.services.extraction.parser import parse_docling_content_stream, parse_heading_hierarchy
from app.services.upload.service import get_session_upload, get_session_upload_path, validate_session_id

RUNNER_LOCK = Lock()
ACTIVE_RUNNERS: dict[str, Thread] = {}


def get_current_analysis_state(session_id: str) -> AnalysisState:
    # Return persisted analysis state when available. If this session has not
    # started analysis yet, expose a stable idle state so the frontend can
    # render without special-case null handling.
    validate_session_id(session_id)
    saved_state = read_analysis_state(session_id)
    if saved_state is not None:
        return saved_state

    upload = _try_get_upload(session_id)
    return AnalysisState(
        session_id=session_id,
        status="idle",
        current_step="none",
        file_name=upload.file_name if upload else None,
        started_at=None,
        updated_at=None,
        error=None,
        extraction_output=None,
        parser_output=None,
    )


def start_current_analysis(session_id: str) -> AnalysisState:
    # Ensure an uploaded file exists before starting background work.
    upload = get_session_upload(session_id)
    get_session_upload_path(session_id)

    with RUNNER_LOCK:
        active_runner = ACTIVE_RUNNERS.get(session_id)
        if active_runner is not None and active_runner.is_alive():
            return get_current_analysis_state(session_id)

        queued_state = AnalysisState(
            session_id=session_id,
            status="queued",
            current_step="none",
            file_name=upload.file_name,
            started_at=_timestamp_now(),
            updated_at=_timestamp_now(),
            error=None,
            extraction_output=None,
            parser_output=None,
        )
        write_analysis_state(queued_state)

        runner = Thread(
            target=_run_analysis_pipeline,
            args=(session_id,),
            name=f"analysis-{session_id}",
            daemon=True,
        )
        ACTIVE_RUNNERS[session_id] = runner
        runner.start()

    return queued_state


def _run_analysis_pipeline(session_id: str) -> None:
    extraction_output: ExtractionOutput | None = None
    try:
        upload = get_session_upload(session_id)
        file_path = get_session_upload_path(session_id)

        _persist_state(
            AnalysisState(
                session_id=session_id,
                status="extracting",
                current_step="extractor",
                file_name=upload.file_name,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=None,
                extraction_output=None,
                parser_output=None,
            )
        )

        extraction_output = extract_pdf_with_docling(file_path)

        _persist_state(
            AnalysisState(
                session_id=session_id,
                status="parsing",
                current_step="parser",
                file_name=upload.file_name,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=None,
                extraction_output=extraction_output,
                parser_output=None,
            )
        )

        content_stream = parse_docling_content_stream(extraction_output.docling_output)
        heading_hierarchy = parse_heading_hierarchy(content_stream)
        parser_output = ParserOutput(
            document=extraction_output.document.model_dump(),
            docling_output=extraction_output.docling_output,
            content_stream=content_stream,
            heading_hierarchy=heading_hierarchy,
        )

        _persist_state(
            AnalysisState(
                session_id=session_id,
                status="completed",
                current_step="done",
                file_name=upload.file_name,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=None,
                extraction_output=extraction_output,
                parser_output=parser_output,
            )
        )
    except Exception as error:
        upload = _try_get_upload(session_id)
        _persist_state(
            AnalysisState(
                session_id=session_id,
                status="failed",
                current_step="done",
                file_name=upload.file_name if upload else None,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=str(error),
                extraction_output=extraction_output,
                parser_output=None,
            )
        )
    finally:
        with RUNNER_LOCK:
            ACTIVE_RUNNERS.pop(session_id, None)


def _persist_state(state: AnalysisState) -> AnalysisState:
    return write_analysis_state(state)


def _existing_started_at(session_id: str) -> str:
    existing_state = read_analysis_state(session_id)
    return existing_state.started_at or _timestamp_now() if existing_state else _timestamp_now()


def _timestamp_now() -> str:
    return datetime.now(UTC).isoformat()


def _try_get_upload(session_id: str):
    try:
        return get_session_upload(session_id)
    except Exception:
        return None
