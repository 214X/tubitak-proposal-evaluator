from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.services.chunking.models import ChunkType

EmbeddingProviderName = Literal["bge_m3"]


class EmbeddingRecord(BaseModel):
    session_id: str
    chunk_id: str
    document_id: str
    section_id: str
    chunk_type: ChunkType
    heading_path_titles: list[str]
    page_start: int | None = None
    page_end: int | None = None
    text_for_embedding: str
    embedding: list[float]


class EmbeddingOutput(BaseModel):
    session_id: str
    document_id: str
    provider_name: EmbeddingProviderName
    model_name: str
    vector_dimensions: int
    chunk_count: int
    embedded_at: str


class EmbeddingSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=25)
    chunk_types: list[ChunkType] = Field(default_factory=list)


class EmbeddingSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    section_id: str
    chunk_type: ChunkType
    heading_path_titles: list[str]
    page_start: int | None = None
    page_end: int | None = None
    text_for_embedding: str
    similarity_score: float


class EmbeddingSearchResponse(BaseModel):
    session_id: str
    query: str
    provider_name: EmbeddingProviderName
    model_name: str
    vector_dimensions: int
    top_k: int
    results: list[EmbeddingSearchResult]
