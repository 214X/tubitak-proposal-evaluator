from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from app.services.analysis.service import get_current_analysis_state
from app.services.chunking.models import BaseChunk, ChunkOutput
from app.services.embedding.models import EmbeddingSearchRequest, EmbeddingSearchResult
from app.services.embedding.service import search_current_embeddings
from app.services.evaluation.models import CriterionEvidence, EvidenceChunk, EvaluationCriterion

SECTION_CODE_PATTERN = re.compile(r"^[A-Z](?:\.\d+)*$")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def retrieve_evidence_for_subcriterion(
    session_id: str,
    subcriterion: EvaluationCriterion,
) -> CriterionEvidence:
    chunk_output = _get_current_chunk_output(session_id)
    chunk_index = {chunk.chunk_id: chunk for chunk in chunk_output.chunks}

    primary_section_chunks = get_chunks_by_section(
        session_id=session_id,
        section_patterns=subcriterion.source_sections,
        top_k=subcriterion.evidence_top_k,
        allowed_chunk_types=subcriterion.allowed_chunk_types,
        chunk_output=chunk_output,
    )
    semantic_support_chunks = semantic_search_for_subcriterion(
        session_id=session_id,
        subcriterion=subcriterion,
        chunk_index=chunk_index,
        exclude_chunk_ids={chunk.chunk_id for chunk in primary_section_chunks},
    )
    fallback_context_chunks = get_fallback_context(
        session_id=session_id,
        subcriterion=subcriterion,
        chunk_output=chunk_output,
        exclude_chunk_ids={
            chunk.chunk_id for chunk in [*primary_section_chunks, *semantic_support_chunks]
        },
    )
    coverage_status, coverage_notes = validate_coverage(
        subcriterion=subcriterion,
        primary_chunks=primary_section_chunks,
    )

    supporting_evidence = _dedupe_and_limit_chunks(
        [*primary_section_chunks, *semantic_support_chunks],
        top_k=max(subcriterion.evidence_top_k, len(primary_section_chunks)),
    )
    contradicting_evidence = _dedupe_and_limit_chunks(
        fallback_context_chunks,
        top_k=subcriterion.evidence_top_k,
    )

    return CriterionEvidence(
        criterion_id=subcriterion.criterion_id,
        main_dimension_id=subcriterion.main_dimension_id,
        primary_section_chunks=primary_section_chunks,
        semantic_support_chunks=semantic_support_chunks,
        fallback_context_chunks=fallback_context_chunks,
        coverage_status=coverage_status,
        coverage_notes=coverage_notes,
        supporting_evidence=supporting_evidence,
        contradicting_evidence=contradicting_evidence,
    )


def retrieve_evidence_for_criterion(
    session_id: str,
    criterion: EvaluationCriterion,
) -> CriterionEvidence:
    # Keep the legacy entrypoint for the existing evaluation service.
    return retrieve_evidence_for_subcriterion(session_id, criterion)


def get_chunks_by_section(
    session_id: str,
    section_patterns: list[str],
    top_k: int,
    allowed_chunk_types: list[str] | None = None,
    chunk_output: ChunkOutput | None = None,
) -> list[EvidenceChunk]:
    if not section_patterns:
        return []

    resolved_chunk_output = chunk_output or _get_current_chunk_output(session_id)
    scored_matches: list[tuple[int, EvidenceChunk]] = []

    for chunk in resolved_chunk_output.chunks:
        if allowed_chunk_types and chunk.chunk_type not in allowed_chunk_types:
            continue

        match_score = _best_section_match_score(chunk, section_patterns)
        if match_score <= 0:
            continue

        scored_matches.append((match_score, _chunk_to_evidence_chunk(chunk, similarity_score=1.0)))

    ordered = [item for _, item in sorted(scored_matches, key=lambda pair: pair[0], reverse=True)]
    return _dedupe_and_limit_chunks(ordered, top_k=top_k)


def semantic_search_for_subcriterion(
    session_id: str,
    subcriterion: EvaluationCriterion,
    chunk_index: dict[str, BaseChunk] | None = None,
    exclude_chunk_ids: set[str] | None = None,
) -> list[EvidenceChunk]:
    if not subcriterion.semantic_queries:
        return []

    resolved_chunk_index = chunk_index or _build_chunk_index(_get_current_chunk_output(session_id))
    excluded = exclude_chunk_ids or set()
    candidates: list[EvidenceChunk] = []

    for query in subcriterion.semantic_queries:
        response = search_current_embeddings(
            session_id,
            EmbeddingSearchRequest(
                query=query,
                top_k=subcriterion.evidence_top_k,
                chunk_types=subcriterion.allowed_chunk_types,
            ),
        )
        for result in response.results:
            if result.chunk_id in excluded:
                continue
            candidates.append(
                _search_result_to_evidence_chunk(
                    result=result,
                    chunk_index=resolved_chunk_index,
                )
            )

    return _dedupe_and_limit_chunks(candidates, top_k=subcriterion.evidence_top_k)


def get_fallback_context(
    session_id: str,
    subcriterion: EvaluationCriterion,
    chunk_output: ChunkOutput | None = None,
    exclude_chunk_ids: set[str] | None = None,
) -> list[EvidenceChunk]:
    resolved_chunk_output = chunk_output or _get_current_chunk_output(session_id)
    excluded = exclude_chunk_ids or set()

    fallback_sections = subcriterion.fallback_sections or subcriterion.source_sections
    fallback_chunks = get_chunks_by_section(
        session_id=session_id,
        section_patterns=fallback_sections,
        top_k=subcriterion.evidence_top_k,
        allowed_chunk_types=subcriterion.allowed_chunk_types,
        chunk_output=resolved_chunk_output,
    )
    filtered_fallback = [chunk for chunk in fallback_chunks if chunk.chunk_id not in excluded]
    if filtered_fallback:
        return _dedupe_and_limit_chunks(filtered_fallback, top_k=subcriterion.evidence_top_k)

    chunk_candidates = [
        _chunk_to_evidence_chunk(chunk, similarity_score=0.25)
        for chunk in resolved_chunk_output.chunks
        if chunk.chunk_type in subcriterion.allowed_chunk_types
        if chunk.chunk_id not in excluded
    ]
    return _dedupe_and_limit_chunks(chunk_candidates, top_k=subcriterion.evidence_top_k)


def validate_coverage(
    subcriterion: EvaluationCriterion,
    primary_chunks: list[EvidenceChunk],
) -> tuple[str, list[str]]:
    if not subcriterion.required_sections:
        return ("complete", [])

    covered_sections: list[str] = []
    missing_sections: list[str] = []

    for required_section in subcriterion.required_sections:
        if any(_evidence_chunk_matches_section(chunk, required_section) for chunk in primary_chunks):
            covered_sections.append(required_section)
        else:
            missing_sections.append(required_section)

    if not covered_sections:
        return (
            "missing",
            [
                "Zorunlu bölümler için birincil section-first eşleşmesi bulunamadı.",
                f"Eksik zorunlu bölümler: {', '.join(missing_sections)}",
            ],
        )
    if missing_sections:
        return (
            "partial",
            [
                f"Karşılanan zorunlu bölümler: {', '.join(covered_sections)}",
                f"Eksik zorunlu bölümler: {', '.join(missing_sections)}",
            ],
        )
    return (
        "complete",
        [f"Tüm zorunlu bölümler karşılandı: {', '.join(covered_sections)}"],
    )


def _get_current_chunk_output(session_id: str) -> ChunkOutput:
    analysis_state = get_current_analysis_state(session_id)
    if analysis_state.chunk_output is None:
        raise RuntimeError("Chunk output is required before section-first retrieval can run.")
    return analysis_state.chunk_output


def _build_chunk_index(chunk_output: ChunkOutput) -> dict[str, BaseChunk]:
    return {chunk.chunk_id: chunk for chunk in chunk_output.chunks}


def _search_result_to_evidence_chunk(
    result: EmbeddingSearchResult,
    chunk_index: dict[str, BaseChunk],
) -> EvidenceChunk:
    chunk = chunk_index.get(result.chunk_id)
    if chunk is not None:
        return _chunk_to_evidence_chunk(chunk, similarity_score=result.similarity_score)

    return EvidenceChunk(
        chunk_id=result.chunk_id,
        chunk_type=result.chunk_type,
        heading_path_ids=[],
        heading_path_titles=result.heading_path_titles,
        page_start=result.page_start,
        page_end=result.page_end,
        text_for_embedding=result.text_for_embedding,
        similarity_score=result.similarity_score,
    )


def _chunk_to_evidence_chunk(chunk: BaseChunk, similarity_score: float) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk.chunk_id,
        chunk_type=chunk.chunk_type,
        heading_path_ids=list(chunk.heading_path_ids),
        heading_path_titles=list(chunk.heading_path_titles),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        text_for_embedding=chunk.text_for_embedding,
        similarity_score=similarity_score,
    )


def _best_section_match_score(chunk: BaseChunk, section_patterns: Iterable[str]) -> int:
    return max((_section_match_score(chunk, pattern) for pattern in section_patterns), default=0)


def _section_match_score(chunk: BaseChunk, section_pattern: str) -> int:
    normalized_pattern = _normalize_text(section_pattern)
    compact_pattern = _compact_token(normalized_pattern)
    pattern_is_code = _is_section_code(section_pattern)

    heading_ids = [_normalize_text(item) for item in chunk.heading_path_ids]
    heading_id_compacts = [_compact_token(item) for item in heading_ids]
    heading_titles = [_normalize_text(item) for item in chunk.heading_path_titles]
    heading_title_compacts = [_compact_token(item) for item in heading_titles]

    if pattern_is_code:
        if compact_pattern in heading_id_compacts:
            return 400
        if any(compact_pattern == _compact_token(token) for token in heading_titles):
            return 300
        if any(compact_pattern in token for token in heading_id_compacts):
            return 250
        if any(compact_pattern in token for token in heading_title_compacts):
            return 200
        return 0

    if any(normalized_pattern == title for title in heading_titles):
        return 220
    if any(normalized_pattern in title for title in heading_titles):
        return 180
    if any(compact_pattern == title for title in heading_title_compacts):
        return 170
    if any(compact_pattern in title for title in heading_title_compacts):
        return 150
    return 0


def _evidence_chunk_matches_section(chunk: EvidenceChunk, section_pattern: str) -> bool:
    normalized_pattern = _normalize_text(section_pattern)
    compact_pattern = _compact_token(normalized_pattern)

    if _is_section_code(section_pattern):
        if compact_pattern in {_compact_token(_normalize_text(item)) for item in chunk.heading_path_ids}:
            return True
        return any(
            compact_pattern in _compact_token(_normalize_text(item))
            for item in chunk.heading_path_titles
        )

    return any(
        normalized_pattern in _normalize_text(title) or compact_pattern in _compact_token(_normalize_text(title))
        for title in chunk.heading_path_titles
    )


def _dedupe_and_limit_chunks(
    chunks: list[EvidenceChunk],
    top_k: int,
) -> list[EvidenceChunk]:
    deduped: dict[str, EvidenceChunk] = {}

    for chunk in chunks:
        existing = deduped.get(chunk.chunk_id)
        if existing is None or chunk.similarity_score > existing.similarity_score:
            deduped[chunk.chunk_id] = chunk

    return sorted(
        deduped.values(),
        key=lambda item: (item.similarity_score, -(item.page_start or 0)),
        reverse=True,
    )[:top_k]


def _normalize_text(value: str) -> str:
    collapsed = " ".join(value.split()).strip().casefold()
    decomposed = unicodedata.normalize("NFKD", collapsed)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return NON_ALNUM_PATTERN.sub(" ", without_marks).strip()


def _compact_token(value: str) -> str:
    return value.replace(" ", "")


def _is_section_code(value: str) -> bool:
    raw = value.strip().upper().rstrip(".")
    return bool(SECTION_CODE_PATTERN.fullmatch(raw))
