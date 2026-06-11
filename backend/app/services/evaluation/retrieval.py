from __future__ import annotations

from app.services.embedding.models import EmbeddingSearchRequest, EmbeddingSearchResult
from app.services.embedding.service import search_current_embeddings
from app.services.evaluation.models import CriterionEvidence, EvidenceChunk, EvaluationCriterion


def retrieve_evidence_for_criterion(
    session_id: str,
    criterion: EvaluationCriterion,
) -> CriterionEvidence:
    supporting = _search_many_queries(
        session_id=session_id,
        queries=criterion.positive_queries,
        top_k=criterion.evidence_top_k,
        chunk_types=criterion.allowed_chunk_types,
    )
    contradicting = _search_many_queries(
        session_id=session_id,
        queries=criterion.negative_queries,
        top_k=criterion.evidence_top_k,
        chunk_types=criterion.allowed_chunk_types,
    )

    return CriterionEvidence(
        criterion_id=criterion.criterion_id,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
    )


def _search_many_queries(
    session_id: str,
    queries: list[str],
    top_k: int,
    chunk_types: list[str],
) -> list[EvidenceChunk]:
    if not queries:
        return []

    deduped: dict[str, EvidenceChunk] = {}
    for query in queries:
        response = search_current_embeddings(
            session_id,
            EmbeddingSearchRequest(
                query=query,
                top_k=top_k,
                chunk_types=chunk_types,
            ),
        )
        for result in response.results:
            candidate = _to_evidence_chunk(result)
            existing = deduped.get(candidate.chunk_id)
            if existing is None or candidate.similarity_score > existing.similarity_score:
                deduped[candidate.chunk_id] = candidate

    return sorted(
        deduped.values(),
        key=lambda item: item.similarity_score,
        reverse=True,
    )[:top_k]


def _to_evidence_chunk(result: EmbeddingSearchResult) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=result.chunk_id,
        chunk_type=result.chunk_type,
        heading_path_titles=result.heading_path_titles,
        page_start=result.page_start,
        page_end=result.page_end,
        text_for_embedding=result.text_for_embedding,
        similarity_score=result.similarity_score,
    )
