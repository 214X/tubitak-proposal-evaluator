from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock, Thread

from app.services.analysis.models import AnalysisState
from app.services.analysis.models import StageTiming
from app.services.analysis.store import read_analysis_state, write_analysis_state
from app.services.chunking.models import ChunkOutput
from app.services.chunking.service import build_chunk_output_from_parser
from app.services.embedding.models import EmbeddingOutput
from app.services.embedding.service import build_embeddings_for_chunk_output
from app.services.embedding.store import clear_session_embeddings
from app.services.evaluation.store import clear_evaluation_state
from app.services.extraction.docling_extractor import extract_pdf_with_docling
from app.services.extraction.models import ExtractionOutput
from app.services.extraction.models import ParserOutput
from app.services.extraction.parser import parse_docling_content_stream, parse_heading_hierarchy
from app.services.upload.service import get_session_upload, get_session_upload_path, validate_session_id

RUNNER_LOCK = Lock()
ACTIVE_RUNNERS: dict[str, Thread] = {}


class SessionSupersededError(RuntimeError):
    """Raised when a session is reset or a new file replaces the active upload."""


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
        extraction_timing=None,
        parser_timing=None,
        chunking_timing=None,
        embedding_timing=None,
        extraction_output=None,
        parser_output=None,
        chunk_output=None,
        embedding_output=None,
    )


def start_current_analysis(session_id: str) -> AnalysisState:
    # Ensure an uploaded file exists before starting background work.
    upload = get_session_upload(session_id)
    get_session_upload_path(session_id)

    with RUNNER_LOCK:
        active_runner = ACTIVE_RUNNERS.get(session_id)
        if active_runner is not None and active_runner.is_alive():
            return get_current_analysis_state(session_id)

        clear_evaluation_state(session_id)
        clear_session_embeddings(session_id)
        queued_state = AnalysisState(
            session_id=session_id,
            status="queued",
            current_step="none",
            file_name=upload.file_name,
            started_at=_timestamp_now(),
            updated_at=_timestamp_now(),
            error=None,
            extraction_timing=None,
            parser_timing=None,
            chunking_timing=None,
            embedding_timing=None,
            extraction_output=None,
            parser_output=None,
            chunk_output=None,
            embedding_output=None,
        )
        write_analysis_state(queued_state)

        runner = Thread(
            target=_run_analysis_pipeline,
            args=(session_id, upload.uploaded_at),
            name=f"analysis-{session_id}",
            daemon=True,
        )
        ACTIVE_RUNNERS[session_id] = runner
        runner.start()

    return queued_state


def _run_analysis_pipeline(session_id: str, expected_uploaded_at: str) -> None:
    extraction_output: ExtractionOutput | None = None
    parser_output: ParserOutput | None = None
    chunk_output: ChunkOutput | None = None
    embedding_output: EmbeddingOutput | None = None
    try:
        _assert_session_upload_is_current(session_id, expected_uploaded_at)
        upload = get_session_upload(session_id)
        file_path = get_session_upload_path(session_id)

        _assert_session_upload_is_current(session_id, expected_uploaded_at)
        _persist_state(
            AnalysisState(
                session_id=session_id,
                status="extracting",
                current_step="extractor",
                file_name=upload.file_name,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=None,
                extraction_timing=_start_stage(session_id, "extraction_timing"),
                parser_timing=_carry_stage_timing(session_id, "parser_timing"),
                chunking_timing=_carry_stage_timing(session_id, "chunking_timing"),
                embedding_timing=_carry_stage_timing(session_id, "embedding_timing"),
                extraction_output=None,
                parser_output=None,
                chunk_output=None,
                embedding_output=None,
            )
        )

        extraction_output = extract_pdf_with_docling(file_path)

        _assert_session_upload_is_current(session_id, expected_uploaded_at)
        _persist_state(
            AnalysisState(
                session_id=session_id,
                status="parsing",
                current_step="parser",
                file_name=upload.file_name,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=None,
                extraction_timing=_complete_stage(session_id, "extraction_timing"),
                parser_timing=_start_stage(session_id, "parser_timing"),
                chunking_timing=_carry_stage_timing(session_id, "chunking_timing"),
                embedding_timing=_carry_stage_timing(session_id, "embedding_timing"),
                extraction_output=extraction_output,
                parser_output=None,
                chunk_output=None,
                embedding_output=None,
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
                status="chunking",
                current_step="chunker",
                file_name=upload.file_name,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=None,
                extraction_timing=_carry_stage_timing(session_id, "extraction_timing"),
                parser_timing=_complete_stage(session_id, "parser_timing"),
                chunking_timing=_start_stage(session_id, "chunking_timing"),
                embedding_timing=_carry_stage_timing(session_id, "embedding_timing"),
                extraction_output=extraction_output,
                parser_output=parser_output,
                chunk_output=None,
                embedding_output=None,
            )
        )

        chunk_output = build_chunk_output_from_parser(parser_output)

        _assert_session_upload_is_current(session_id, expected_uploaded_at)
        _persist_state(
            AnalysisState(
                session_id=session_id,
                status="embedding",
                current_step="embedder",
                file_name=upload.file_name,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=None,
                extraction_timing=_carry_stage_timing(session_id, "extraction_timing"),
                parser_timing=_carry_stage_timing(session_id, "parser_timing"),
                chunking_timing=_complete_stage(session_id, "chunking_timing"),
                embedding_timing=_start_stage(session_id, "embedding_timing"),
                extraction_output=extraction_output,
                parser_output=parser_output,
                chunk_output=chunk_output,
                embedding_output=None,
            )
        )

        _assert_session_upload_is_current(session_id, expected_uploaded_at)
        embedding_output = build_embeddings_for_chunk_output(
            session_id,
            chunk_output,
            before_store=lambda: _assert_session_upload_is_current(session_id, expected_uploaded_at),
        )

        _assert_session_upload_is_current(session_id, expected_uploaded_at)
        _persist_state(
            AnalysisState(
                session_id=session_id,
                status="completed",
                current_step="done",
                file_name=upload.file_name,
                started_at=_existing_started_at(session_id),
                updated_at=_timestamp_now(),
                error=None,
                extraction_timing=_carry_stage_timing(session_id, "extraction_timing"),
                parser_timing=_carry_stage_timing(session_id, "parser_timing"),
                chunking_timing=_carry_stage_timing(session_id, "chunking_timing"),
                embedding_timing=_complete_stage(session_id, "embedding_timing"),
                extraction_output=extraction_output,
                parser_output=parser_output,
                chunk_output=chunk_output,
                embedding_output=embedding_output,
            )
        )
        _start_followup_evaluation(session_id, expected_uploaded_at)
    except Exception as error:
        if isinstance(error, SessionSupersededError) or not _is_session_upload_current(
            session_id,
            expected_uploaded_at,
        ):
            return

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
                extraction_timing=_carry_stage_timing(session_id, "extraction_timing"),
                parser_timing=_carry_stage_timing(session_id, "parser_timing"),
                chunking_timing=_carry_stage_timing(session_id, "chunking_timing"),
                embedding_timing=_carry_stage_timing(session_id, "embedding_timing"),
                extraction_output=extraction_output,
                parser_output=parser_output,
                chunk_output=chunk_output,
                embedding_output=embedding_output,
            )
        )
    finally:
        with RUNNER_LOCK:
            ACTIVE_RUNNERS.pop(session_id, None)


def _persist_state(state: AnalysisState) -> AnalysisState:
    return write_analysis_state(state)


def _carry_stage_timing(
    session_id: str,
    field_name: str,
) -> StageTiming | None:
    existing_state = read_analysis_state(session_id)
    if existing_state is None:
        return None

    stage_timing = getattr(existing_state, field_name, None)
    return stage_timing.model_copy(deep=True) if stage_timing else None


def _start_stage(session_id: str, field_name: str) -> StageTiming:
    current = _carry_stage_timing(session_id, field_name)
    if current and current.started_at:
        return current

    return StageTiming(started_at=_timestamp_now(), completed_at=current.completed_at if current else None)


def _complete_stage(session_id: str, field_name: str) -> StageTiming:
    current = _carry_stage_timing(session_id, field_name) or StageTiming(started_at=_timestamp_now())
    if current.completed_at:
        return current

    return StageTiming(started_at=current.started_at, completed_at=_timestamp_now())


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


def _assert_session_upload_is_current(session_id: str, expected_uploaded_at: str) -> None:
    upload = _try_get_upload(session_id)
    if upload is None or upload.uploaded_at != expected_uploaded_at:
        raise SessionSupersededError(
            "The active upload changed while the analysis pipeline was running.",
        )


def _is_session_upload_current(session_id: str, expected_uploaded_at: str) -> bool:
    upload = _try_get_upload(session_id)
    return upload is not None and upload.uploaded_at == expected_uploaded_at


def _start_followup_evaluation(session_id: str, expected_uploaded_at: str) -> None:
    if not _is_session_upload_current(session_id, expected_uploaded_at):
        return

    try:
        from app.services.evaluation.service import start_current_evaluation

        start_current_evaluation(session_id)
    except Exception:
        return
