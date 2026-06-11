from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Callable

from fastapi import HTTPException, status

from app.services.analysis.store import read_analysis_state
from app.services.chunking.models import ChunkOutput
from app.services.embedding.models import (
    EmbeddingOutput,
    EmbeddingRecord,
    EmbeddingSearchRequest,
    EmbeddingSearchResponse,
    EmbeddingSearchResult,
)
from app.services.embedding.provider import get_embedding_provider
from app.services.embedding.store import query_embeddings, replace_session_embeddings
from app.services.upload.service import validate_session_id


def build_embeddings_for_chunk_output(
    session_id: str,
    chunk_output: ChunkOutput,
    before_store: Callable[[], None] | None = None,
) -> EmbeddingOutput:
    validate_session_id(session_id)
    provider = get_embedding_provider()
    chunk_texts = [chunk.text_for_embedding for chunk in chunk_output.chunks]
    vectors = provider.embed_texts(chunk_texts)

    records = [
        EmbeddingRecord(
            session_id=session_id,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            section_id=chunk.section_id,
            chunk_type=chunk.chunk_type,
            heading_path_titles=chunk.heading_path_titles,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            text_for_embedding=chunk.text_for_embedding,
            embedding=vector,
        )
        for chunk, vector in zip(chunk_output.chunks, vectors, strict=True)
    ]

    embedding_output = EmbeddingOutput(
        session_id=session_id,
        document_id=chunk_output.document_id,
        provider_name=provider.name,
        model_name=provider.model_name,
        vector_dimensions=provider.dimensions,
        chunk_count=len(records),
        embedded_at=_timestamp_now(),
    )

    if before_store is not None:
        before_store()

    replace_session_embeddings(session_id, records)
    return embedding_output


def get_current_embedding_output(session_id: str) -> EmbeddingOutput:
    validate_session_id(session_id)
    analysis_state = read_analysis_state(session_id)
    if analysis_state is None or analysis_state.embedding_output is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No embedding output found for this session.",
        )

    return analysis_state.embedding_output


def search_current_embeddings(
    session_id: str,
    request: EmbeddingSearchRequest,
) -> EmbeddingSearchResponse:
    validate_session_id(session_id)
    embedding_output = get_current_embedding_output(session_id)
    provider = get_embedding_provider(embedding_output.provider_name)
    query = request.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty.",
        )

    query_embedding = provider.embed_texts([query])[0]
    payload = query_embeddings(
        session_id,
        query_embedding=query_embedding,
        top_k=request.top_k,
        chunk_types=[chunk_type for chunk_type in request.chunk_types],
    )

    ids = payload.get("ids", [[]])
    documents = payload.get("documents", [[]])
    metadatas = payload.get("metadatas", [[]])
    distances = payload.get("distances", [[]])

    query_ids = ids[0] if ids else []
    query_documents = documents[0] if documents else []
    query_metadatas = metadatas[0] if metadatas else []
    query_distances = distances[0] if distances else []

    scored_results = [
        EmbeddingSearchResult(
            chunk_id=str(chunk_id),
            document_id=str((metadata or {}).get("document_id", "")),
            section_id=str((metadata or {}).get("section_id", "")),
            chunk_type=str((metadata or {}).get("chunk_type", "narrative")),
            heading_path_titles=_parse_heading_path_titles(metadata),
            page_start=(metadata or {}).get("page_start"),
            page_end=(metadata or {}).get("page_end"),
            text_for_embedding=str(document),
            similarity_score=max(0.0, 1.0 - float(distance)),
        )
        for chunk_id, document, metadata, distance in zip(
            query_ids,
            query_documents,
            query_metadatas,
            query_distances,
            strict=True,
        )
    ]

    return EmbeddingSearchResponse(
        session_id=session_id,
        query=query,
        provider_name=embedding_output.provider_name,
        model_name=embedding_output.model_name,
        vector_dimensions=embedding_output.vector_dimensions,
        top_k=request.top_k,
        results=scored_results,
    )


def _timestamp_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_heading_path_titles(metadata: dict | None) -> list[str]:
    raw_value = (metadata or {}).get("heading_path_titles_json", "[]")
    if not isinstance(raw_value, str):
        return []

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    return [str(item) for item in parsed]
