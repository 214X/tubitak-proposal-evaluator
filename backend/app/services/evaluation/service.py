from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock, Thread

from fastapi import HTTPException, status

from app.services.analysis.service import get_current_analysis_state
from app.services.evaluation.models import (
    CriterionEvidence,
    CriterionEvaluationResult,
    EvaluationCriterion,
    EvaluationMainDimension,
    EvaluationReport,
    EvaluationRubric,
    EvaluationState,
    EvidenceChunk,
    EvidenceNarrative,
    MainDimensionScore,
    RubricTableEntry,
)
from app.services.evaluation.provider import get_judge_provider
from app.services.evaluation.retrieval import retrieve_evidence_for_subcriterion
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
        active_subcriterion_id=None,
        active_subcriterion_title=None,
        active_main_dimension_id=None,
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
            active_subcriterion_id=None,
            active_subcriterion_title=None,
            active_main_dimension_id=None,
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

        for subcriterion in rubric.subcriteria:
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
                    active_subcriterion=subcriterion,
                    final_report=None,
                    error=None,
                )
            )
            evidence = retrieve_evidence_for_subcriterion(session_id, subcriterion)

            if evidence.coverage_status == "missing" or _total_evidence_count(evidence) < subcriterion.minimum_evidence_count:
                results.append(_build_insufficient_result(subcriterion, evidence))
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
                    active_subcriterion=subcriterion,
                    final_report=None,
                    error=None,
                )
            )
            results.append(provider.evaluate_criterion(subcriterion, evidence))

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
                active_subcriterion=None,
                final_report=None,
                error=None,
            )
        )

        final_report = _aggregate_results(
            session_id=session_id,
            rubric=rubric,
            results=results,
        )

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
                active_subcriterion=None,
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
                active_subcriterion=None,
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
        main_dimension_id=criterion.main_dimension_id,
        category=criterion.category,
        title=criterion.title,
        score=None,
        claim_strength=None,
        evidence_quality=None,
        weight=criterion.weight,
        weighted_score=None,
        confidence=0.0,
        decision_status="insufficient_evidence",
        justification="Kriteri puanlamak için yeterli kanıt bulunamadı.",
        criterion_explanation=(
            "Gerekli bölüm eşleşmeleri veya yeterli section-first kanıt bulunamadığı için "
            "kriter değerlendirmesi başlatılmadı."
        ),
        short_assessment="Section-first coverage yetersiz.",
        coverage_status=evidence.coverage_status,
        coverage_notes=evidence.coverage_notes,
        primary_section_chunks=evidence.primary_section_chunks,
        semantic_support_chunks=evidence.semantic_support_chunks,
        fallback_context_chunks=evidence.fallback_context_chunks,
        supporting_chunk_ids=[item.chunk_id for item in evidence.supporting_evidence],
        contradicting_chunk_ids=[item.chunk_id for item in evidence.contradicting_evidence],
        missing_information=_dedupe_strings([criterion.description, *evidence.coverage_notes]),
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
    rubric: EvaluationRubric,
    results: list[CriterionEvaluationResult],
) -> EvaluationReport:
    rubric_table = _build_rubric_table(rubric)
    main_scores = _build_main_scores(rubric.main_dimensions, rubric.subcriteria, results)
    overall_score = _compute_overall_score(main_scores)

    total_weight = sum(item.weight for item in rubric.subcriteria)
    total_weighted_score = sum(item.weighted_score or 0.0 for item in results)
    max_possible_weighted_score = sum(item.weight * item.score_max for item in rubric.subcriteria)
    scored_criteria_count = sum(1 for item in results if item.score is not None)

    major_strengths = _build_major_strengths(results)
    major_weaknesses = _build_major_weaknesses(results)
    critical_missing_information = _build_critical_missing_information(results, main_scores)
    red_flags = _build_red_flags(results)

    return EvaluationReport(
        session_id=session_id,
        rubric_id=rubric.rubric_id,
        rubric_version=rubric.version,
        overall_score=overall_score,
        main_scores=main_scores,
        subcriteria_results=results,
        rubric_table=rubric_table,
        major_strengths=major_strengths,
        major_weaknesses=major_weaknesses,
        critical_missing_information=critical_missing_information,
        red_flags=red_flags,
        total_weight=total_weight,
        total_weighted_score=round(total_weighted_score, 2),
        max_possible_weighted_score=float(max_possible_weighted_score),
        scored_criteria_count=scored_criteria_count,
        criterion_results=results,
        strengths=major_strengths,
        weaknesses=major_weaknesses,
        final_summary=_build_final_summary(overall_score, main_scores, results),
    )


def _build_rubric_table(
    rubric: EvaluationRubric,
) -> list[RubricTableEntry]:
    dimension_title_by_id = {
        item.dimension_id: item.title for item in rubric.main_dimensions
    }
    return [
        RubricTableEntry(
            main_dimension_title=dimension_title_by_id.get(item.main_dimension_id, item.main_dimension_id),
            criterion_id=item.criterion_id,
            main_dimension_id=item.main_dimension_id,
            criterion_title=item.title,
            description=item.description,
            source_sections=list(item.source_sections),
            ui_label=item.ui_label,
            weight=item.weight,
            score_min=item.score_min,
            score_max=item.score_max,
            ui_explanation=item.ui_explanation,
        )
        for item in rubric.subcriteria
    ]


def _build_main_scores(
    main_dimensions: list[EvaluationMainDimension],
    subcriteria: list[EvaluationCriterion],
    results: list[CriterionEvaluationResult],
) -> list[MainDimensionScore]:
    result_by_id = {item.criterion_id: item for item in results}
    main_scores: list[MainDimensionScore] = []

    for dimension in main_dimensions:
        dimension_criteria = [
            item for item in subcriteria if item.main_dimension_id == dimension.dimension_id
        ]
        dimension_results = [
            result_by_id[item.criterion_id]
            for item in dimension_criteria
            if item.criterion_id in result_by_id
        ]
        scored_results = [item for item in dimension_results if item.score is not None]

        weighted_score_sum = sum((item.score or 0.0) * item.weight for item in scored_results)
        scored_weight_sum = sum(item.weight for item in scored_results)
        score = round((weighted_score_sum / scored_weight_sum) * 20, 2) if scored_weight_sum else None
        weighted_score = round((score or 0.0) * (dimension.weight / 100), 2)

        main_scores.append(
            MainDimensionScore(
                main_dimension_id=dimension.dimension_id,
                title=dimension.title,
                weight=dimension.weight,
                score=score,
                weighted_score=weighted_score,
                subcriteria_count=len(dimension_criteria),
                scored_subcriteria_count=len(scored_results),
                summary=_build_main_dimension_summary(
                    dimension=dimension,
                    dimension_results=dimension_results,
                    score=score,
                ),
            )
        )

    return main_scores


def _compute_overall_score(
    main_scores: list[MainDimensionScore],
) -> float | None:
    available_scores = [item for item in main_scores if item.score is not None]
    if not available_scores:
        return None

    total_available_weight = sum(item.weight for item in available_scores)
    if total_available_weight <= 0:
        return None

    weighted_sum = sum((item.score or 0.0) * item.weight for item in available_scores)
    return round(weighted_sum / total_available_weight, 2)


def _build_major_strengths(
    results: list[CriterionEvaluationResult],
) -> list[str]:
    strengths: list[str] = []
    scored_results = sorted(
        [item for item in results if item.score is not None],
        key=lambda item: (item.score or 0.0, item.confidence),
        reverse=True,
    )

    for item in scored_results:
        if (item.score or 0.0) < 3.5:
            continue
        if item.positive_findings:
            strengths.append(f"{item.title}: {item.positive_findings[0].summary}")
        elif item.justification:
            strengths.append(f"{item.title}: {item.justification}")
        if len(strengths) >= 5:
            break

    return strengths


def _build_major_weaknesses(
    results: list[CriterionEvaluationResult],
) -> list[str]:
    weaknesses: list[str] = []
    ordered_results = sorted(
        results,
        key=lambda item: (
            item.score is None,
            item.score if item.score is not None else -1.0,
        ),
    )

    for item in ordered_results:
        include = item.score is None or (item.score or 0.0) <= 2.5 or item.decision_status != "scored"
        if not include:
            continue
        if item.negative_findings:
            weaknesses.append(f"{item.title}: {item.negative_findings[0].summary}")
        elif item.justification:
            weaknesses.append(f"{item.title}: {item.justification}")
        if len(weaknesses) >= 5:
            break

    return weaknesses


def _build_critical_missing_information(
    results: list[CriterionEvaluationResult],
    main_scores: list[MainDimensionScore],
) -> list[str]:
    missing_information: list[str] = []
    for item in results:
        for missing_item in item.missing_information:
            if missing_item not in missing_information:
                missing_information.append(missing_item)

    for dimension_score in main_scores:
        if dimension_score.score is None:
            missing_information.append(
                f"{dimension_score.main_dimension_id} boyutunda skor üretmek için yeterli alt kriter kanıtı yok."
            )

    return missing_information[:10]


def _build_red_flags(
    results: list[CriterionEvaluationResult],
) -> list[str]:
    red_flags: list[str] = []
    for item in results:
        for flag in item.red_flags:
            if flag not in red_flags:
                red_flags.append(flag)
    return red_flags[:10]


def _build_main_dimension_summary(
    dimension: EvaluationMainDimension,
    dimension_results: list[CriterionEvaluationResult],
    score: float | None,
) -> str:
    if not dimension_results:
        return f"{dimension.dimension_id} boyutunda henüz sonuç oluşmadı."
    if score is None:
        return f"{dimension.dimension_id} boyutunda yeterli puanlanmış alt kriter bulunamadı."

    insufficient_count = sum(1 for item in dimension_results if item.score is None)
    if insufficient_count:
        return (
            f"{dimension.dimension_id} boyutu {score}/100 hesaplandı. "
            f"{insufficient_count} alt kriter yetersiz kanıt nedeniyle skora katılamadı."
        )
    return f"{dimension.dimension_id} boyutu {score}/100 olarak hesaplandı."


def _build_final_summary(
    overall_score: float | None,
    main_scores: list[MainDimensionScore],
    results: list[CriterionEvaluationResult],
) -> str:
    if not results:
        return "Değerlendirme sonucu üretilemedi."
    if overall_score is None:
        return "Puanlanmış alt kriter bulunamadığı için genel skor hesaplanamadı."

    insufficient_count = sum(1 for item in results if item.score is None)
    available_dimensions = [item.main_dimension_id for item in main_scores if item.score is not None]
    if insufficient_count:
        return (
            f"Genel skor {overall_score}/100. "
            f"Skor {', '.join(available_dimensions)} boyutlarındaki puanlanmış alt kriterlerden matematiksel olarak üretildi. "
            f"{insufficient_count} alt kriter yetersiz kanıt nedeniyle dışarıda bırakıldı."
        )
    return (
        f"Genel skor {overall_score}/100. "
        "Tüm ana boyut skorları alt kriter puanlarının ağırlıklı ortalaması ile hesaplandı."
    )


def _build_state(
    session_id: str,
    status,
    current_step,
    rubric_id: str,
    rubric_version: str,
    results: list[CriterionEvaluationResult],
    active_subcriterion: EvaluationCriterion | None,
    final_report: EvaluationReport | None,
    error: str | None,
) -> EvaluationState:
    return EvaluationState(
        session_id=session_id,
        status=status,
        current_step=current_step,
        rubric_id=rubric_id,
        rubric_version=rubric_version,
        active_criterion_id=active_subcriterion.criterion_id if active_subcriterion else None,
        active_criterion_title=active_subcriterion.title if active_subcriterion else None,
        active_subcriterion_id=active_subcriterion.criterion_id if active_subcriterion else None,
        active_subcriterion_title=active_subcriterion.title if active_subcriterion else None,
        active_main_dimension_id=active_subcriterion.main_dimension_id if active_subcriterion else None,
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
    unique_chunk_ids = {
        item.chunk_id
        for item in [
            *evidence.primary_section_chunks,
            *evidence.semantic_support_chunks,
            *evidence.fallback_context_chunks,
            *evidence.supporting_evidence,
            *evidence.contradicting_evidence,
        ]
    }
    return len(unique_chunk_ids)


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
                    else "Bu içerik kriteri zayıflatan veya eksik bırakan sinyal üretiyor."
                ),
            )
        )
    return notes


def _dedupe_strings(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped
