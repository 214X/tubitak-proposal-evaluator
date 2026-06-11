from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock, Thread

from fastapi import HTTPException, status

from app.services.analysis.service import get_current_analysis_state
from app.services.evaluation.models import (
    CriterionEvidence,
    CriterionEvaluationResult,
    EvaluationCriterion,
    EvaluationReport,
    EvaluationState,
    EvidenceChunk,
    EvidenceNarrative,
)
from app.services.evaluation.provider import get_judge_provider
from app.services.evaluation.retrieval import retrieve_evidence_for_criterion
from app.services.evaluation.rubric_loader import load_default_rubric
from app.services.evaluation.store import read_evaluation_state, write_evaluation_state
from app.services.upload.service import get_session_upload, validate_session_id

RUNNER_LOCK = Lock()
ACTIVE_RUNNERS: dict[str, Thread] = {}


class SessionSupersededError(RuntimeError):
    """Raised when evaluation is no longer operating on the active upload."""


def get_current_evaluation_state(session_id: str) -> EvaluationState:
    validate_session_id(session_id)
    saved_state = read_evaluation_state(session_id)
    if saved_state is not None:
        return saved_state

    rubric = load_default_rubric()
    return EvaluationState(
        session_id=session_id,
        status="idle",
        current_step="none",
        rubric_id=rubric.rubric_id,
        rubric_version=rubric.version,
        active_criterion_id=None,
        active_criterion_title=None,
        started_at=None,
        completed_at=None,
        updated_at=None,
        error=None,
        criterion_results=[],
        final_report=None,
    )


def start_current_evaluation(session_id: str) -> EvaluationState:
    validate_session_id(session_id)
    analysis_state = get_current_analysis_state(session_id)
    upload = get_session_upload(session_id)
    if analysis_state.status != "completed" or analysis_state.embedding_output is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation can start only after analysis and embeddings are completed.",
        )

    rubric = load_default_rubric()
    with RUNNER_LOCK:
        active_runner = ACTIVE_RUNNERS.get(session_id)
        if active_runner is not None and active_runner.is_alive():
            return get_current_evaluation_state(session_id)

        queued_state = EvaluationState(
            session_id=session_id,
            status="queued",
            current_step="none",
            rubric_id=rubric.rubric_id,
            rubric_version=rubric.version,
            active_criterion_id=None,
            active_criterion_title=None,
            started_at=_timestamp_now(),
            completed_at=None,
            updated_at=_timestamp_now(),
            error=None,
            criterion_results=[],
            final_report=None,
        )
        write_evaluation_state(queued_state)

        runner = Thread(
            target=_run_evaluation_pipeline,
            args=(session_id, upload.uploaded_at, analysis_state.started_at),
            name=f"evaluation-{session_id}",
            daemon=True,
        )
        ACTIVE_RUNNERS[session_id] = runner
        runner.start()

    return queued_state


def _run_evaluation_pipeline(
    session_id: str,
    expected_uploaded_at: str,
    expected_analysis_started_at: str | None,
) -> None:
    rubric = load_default_rubric()
    provider = get_judge_provider()
    results: list[CriterionEvaluationResult] = []
    try:
        _assert_evaluation_context_is_current(
            session_id,
            expected_uploaded_at,
            expected_analysis_started_at,
        )
        analysis_state = get_current_analysis_state(session_id)
        if analysis_state.status != "completed" or analysis_state.embedding_output is None:
            raise RuntimeError("Analysis and embeddings must be completed before evaluation.")

        for criterion in rubric.criteria:
            _assert_evaluation_context_is_current(
                session_id,
                expected_uploaded_at,
                expected_analysis_started_at,
            )
            _persist_state(
                _build_state(
                    session_id=session_id,
                    status="retrieving",
                    current_step="retriever",
                    rubric_id=rubric.rubric_id,
                    rubric_version=rubric.version,
                    results=results,
                    active_criterion=criterion,
                    final_report=None,
                    error=None,
                )
            )
            evidence = retrieve_evidence_for_criterion(session_id, criterion)

            if _total_evidence_count(evidence) < criterion.minimum_evidence_count:
                results.append(_build_insufficient_result(criterion, evidence))
                continue

            _assert_evaluation_context_is_current(
                session_id,
                expected_uploaded_at,
                expected_analysis_started_at,
            )
            _persist_state(
                _build_state(
                    session_id=session_id,
                    status="evaluating",
                    current_step="judge",
                    rubric_id=rubric.rubric_id,
                    rubric_version=rubric.version,
                    results=results,
                    active_criterion=criterion,
                    final_report=None,
                    error=None,
                )
            )
            results.append(provider.evaluate_criterion(criterion, evidence))

        _assert_evaluation_context_is_current(
            session_id,
            expected_uploaded_at,
            expected_analysis_started_at,
        )
        _persist_state(
            _build_state(
                session_id=session_id,
                status="aggregating",
                current_step="aggregator",
                rubric_id=rubric.rubric_id,
                rubric_version=rubric.version,
                results=results,
                active_criterion=None,
                final_report=None,
                error=None,
            )
        )
        _assert_evaluation_context_is_current(
            session_id,
            expected_uploaded_at,
            expected_analysis_started_at,
        )
        final_report = _aggregate_results(session_id, rubric.rubric_id, rubric.version, rubric.criteria, results)
        _assert_evaluation_context_is_current(
            session_id,
            expected_uploaded_at,
            expected_analysis_started_at,
        )
        _persist_state(
            _build_state(
                session_id=session_id,
                status="completed",
                current_step="done",
                rubric_id=rubric.rubric_id,
                rubric_version=rubric.version,
                results=results,
                active_criterion=None,
                final_report=final_report,
                error=None,
            )
        )
    except Exception as exc:
        if isinstance(exc, SessionSupersededError) or not _is_evaluation_context_current(
            session_id,
            expected_uploaded_at,
            expected_analysis_started_at,
        ):
            return

        _persist_state(
            _build_state(
                session_id=session_id,
                status="failed",
                current_step="done",
                rubric_id=rubric.rubric_id,
                rubric_version=rubric.version,
                results=results,
                active_criterion=None,
                final_report=None,
                error=str(exc),
            )
        )
    finally:
        with RUNNER_LOCK:
            ACTIVE_RUNNERS.pop(session_id, None)


def _build_insufficient_result(
    criterion: EvaluationCriterion,
    evidence: CriterionEvidence,
) -> CriterionEvaluationResult:
    return CriterionEvaluationResult(
        criterion_id=criterion.criterion_id,
        category=criterion.category,
        title=criterion.title,
        score=None,
        weight=criterion.weight,
        weighted_score=None,
        confidence=0.0,
        decision_status="insufficient_evidence",
        justification="Kriteri puanlamak için yeterli kanıt bulunamadı.",
        supporting_chunk_ids=[item.chunk_id for item in evidence.supporting_evidence],
        contradicting_chunk_ids=[item.chunk_id for item in evidence.contradicting_evidence],
        missing_information=[criterion.description],
        red_flags=[],
        supporting_evidence=evidence.supporting_evidence,
        contradicting_evidence=evidence.contradicting_evidence,
        supporting_evidence_notes=_build_fallback_evidence_notes(
            evidence.supporting_evidence,
            positive=True,
        ),
        contradicting_evidence_notes=_build_fallback_evidence_notes(
            evidence.contradicting_evidence,
            positive=False,
        ),
    )


def _aggregate_results(
    session_id: str,
    rubric_id: str,
    rubric_version: str,
    criteria: list[EvaluationCriterion],
    results: list[CriterionEvaluationResult],
) -> EvaluationReport:
    scored_results = [item for item in results if item.weighted_score is not None]
    total_weight = sum(item.weight for item in criteria)
    total_weighted_score = sum(item.weighted_score or 0 for item in results)
    max_possible_weighted_score = sum(item.weight * max(item.allowed_scores) for item in criteria)

    strengths = [
        f"{item.title}: {item.justification}"
        for item in scored_results
        if item.score is not None and item.score > 0
    ][:3]
    weaknesses = [
        f"{item.title}: {item.justification}"
        for item in results
        if item.score == -1 or item.decision_status != "scored"
    ][:3]

    return EvaluationReport(
        session_id=session_id,
        rubric_id=rubric_id,
        rubric_version=rubric_version,
        total_weight=total_weight,
        total_weighted_score=total_weighted_score,
        max_possible_weighted_score=max_possible_weighted_score,
        scored_criteria_count=len(scored_results),
        criterion_results=results,
        strengths=strengths,
        weaknesses=weaknesses,
        final_summary=_build_final_summary(total_weighted_score, max_possible_weighted_score, results),
    )


def _build_final_summary(
    total_weighted_score: int,
    max_possible_weighted_score: int,
    results: list[CriterionEvaluationResult],
) -> str:
    if not results:
        return "Değerlendirme sonucu üretilemedi."

    insufficient_count = sum(1 for item in results if item.decision_status == "insufficient_evidence")
    negative_count = sum(1 for item in results if item.score == -1)
    score_ratio = total_weighted_score / max_possible_weighted_score if max_possible_weighted_score else 0.0

    if insufficient_count == len(results):
        return "Tüm kriterlerde kanıt yetersiz kaldığı için güvenilir bir değerlendirme üretilemedi."
    if negative_count >= max(2, len(results) // 3):
        return (
            f"Toplam skor {total_weighted_score}/{max_possible_weighted_score}. "
            "Olumsuz veya çelişkili kanıtlar baskın olduğu için proje önemli revizyon gerektiriyor."
        )
    if score_ratio >= 0.65:
        return (
            f"Toplam skor {total_weighted_score}/{max_possible_weighted_score}. "
            "Kriterlerin çoğunda destekleyici kanıt bulundu; proje güçlü görünmekle birlikte zayıf noktalar izlenmeli."
        )
    return (
        f"Toplam skor {total_weighted_score}/{max_possible_weighted_score}. "
        "Proje kısmen destekleniyor ancak bazı kriterlerde ek açıklama veya iyileştirme gerekli."
    )


def _build_state(
    session_id: str,
    status,
    current_step,
    rubric_id: str,
    rubric_version: str,
    results: list[CriterionEvaluationResult],
    active_criterion: EvaluationCriterion | None,
    final_report: EvaluationReport | None,
    error: str | None,
) -> EvaluationState:
    return EvaluationState(
        session_id=session_id,
        status=status,
        current_step=current_step,
        rubric_id=rubric_id,
        rubric_version=rubric_version,
        active_criterion_id=active_criterion.criterion_id if active_criterion else None,
        active_criterion_title=active_criterion.title if active_criterion else None,
        started_at=_existing_started_at(session_id),
        completed_at=_existing_completed_at(session_id) if status != "completed" else _timestamp_now(),
        updated_at=_timestamp_now(),
        error=error,
        criterion_results=list(results),
        final_report=final_report,
    )


def _persist_state(state: EvaluationState) -> EvaluationState:
    return write_evaluation_state(state)


def _existing_started_at(session_id: str) -> str:
    existing_state = read_evaluation_state(session_id)
    return existing_state.started_at or _timestamp_now() if existing_state else _timestamp_now()


def _existing_completed_at(session_id: str) -> str | None:
    existing_state = read_evaluation_state(session_id)
    return existing_state.completed_at if existing_state else None


def _assert_session_upload_is_current(session_id: str, expected_uploaded_at: str) -> None:
    upload = _try_get_upload(session_id)
    if upload is None or upload.uploaded_at != expected_uploaded_at:
        raise SessionSupersededError(
            "The active upload changed while the evaluation pipeline was running.",
        )


def _is_session_upload_current(session_id: str, expected_uploaded_at: str) -> bool:
    upload = _try_get_upload(session_id)
    return upload is not None and upload.uploaded_at == expected_uploaded_at


def _assert_evaluation_context_is_current(
    session_id: str,
    expected_uploaded_at: str,
    expected_analysis_started_at: str | None,
) -> None:
    if not _is_evaluation_context_current(
        session_id,
        expected_uploaded_at,
        expected_analysis_started_at,
    ):
        raise SessionSupersededError(
            "The active analysis run changed while the evaluation pipeline was running.",
        )


def _is_evaluation_context_current(
    session_id: str,
    expected_uploaded_at: str,
    expected_analysis_started_at: str | None,
) -> bool:
    if not _is_session_upload_current(session_id, expected_uploaded_at):
        return False

    analysis_state = get_current_analysis_state(session_id)
    return analysis_state.started_at == expected_analysis_started_at


def _try_get_upload(session_id: str):
    try:
        return get_session_upload(session_id)
    except Exception:
        return None


def _total_evidence_count(evidence: CriterionEvidence) -> int:
    return len(evidence.supporting_evidence) + len(evidence.contradicting_evidence)


def _timestamp_now() -> str:
    return datetime.now(UTC).isoformat()


def _build_fallback_evidence_notes(
    evidence_items: list[EvidenceChunk],
    *,
    positive: bool,
) -> list[EvidenceNarrative]:
    notes: list[EvidenceNarrative] = []
    for item in evidence_items:
        heading_path = " > ".join(item.heading_path_titles) if item.heading_path_titles else "Belirsiz bölüm"
        if item.page_start is None and item.page_end is None:
            location = f"Belgede '{heading_path}' bölümünde."
        elif item.page_start == item.page_end:
            location = f"Belgenin '{heading_path}' bölümünde, {item.page_start}. sayfada."
        else:
            location = (
                f"Belgenin '{heading_path}' bölümünde, "
                f"{item.page_start}-{item.page_end}. sayfalar arasında."
            )

        collapsed = " ".join(item.text_for_embedding.split())
        if len(collapsed) > 280:
            collapsed = f"{collapsed[:277].rstrip()}..."

        notes.append(
            EvidenceNarrative(
                chunk_id=item.chunk_id,
                location_summary=location,
                evidence_text=collapsed,
                why_it_matters=(
                    "Bu içerik kriter lehine sinyal üretiyor."
                    if positive
                    else "Bu içerik kriter aleyhine sinyal üretiyor."
                ),
            )
        )
    return notes
