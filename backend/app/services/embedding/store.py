from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

import chromadb

from app.core.config import settings
from app.services.embedding.models import EmbeddingRecord

STORE_LOCK = Lock()


def embedding_storage_path() -> Path:
    return Path(__file__).resolve().parents[3] / settings.embedding_storage_dir


def ensure_embedding_store() -> None:
    embedding_storage_path().mkdir(parents=True, exist_ok=True)


def replace_session_embeddings(
    session_id: str,
    records: list[EmbeddingRecord],
) -> None:
    ensure_embedding_store()

    with STORE_LOCK:
        client = _get_client()
        collection_name = _collection_name(session_id)
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        if records:
            collection.add(
                ids=[record.chunk_id for record in records],
                documents=[record.text_for_embedding for record in records],
                embeddings=[record.embedding for record in records],
                metadatas=[_build_metadata(record) for record in records],
            )


def clear_session_embeddings(session_id: str) -> None:
    ensure_embedding_store()

    with STORE_LOCK:
        client = _get_client()
        try:
            client.delete_collection(_collection_name(session_id))
        except Exception:
            pass


def query_embeddings(
    session_id: str,
    query_embedding: list[float],
    top_k: int,
    chunk_types: list[str] | None = None,
) -> dict:
    ensure_embedding_store()
    with STORE_LOCK:
        collection = _get_client().get_collection(_collection_name(session_id))
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=_build_where_filter(chunk_types),
            include=["documents", "metadatas", "distances"],
        )


def _get_client():
    return chromadb.PersistentClient(path=str(embedding_storage_path()))


def _collection_name(session_id: str) -> str:
    return f"session_{session_id}"


def _build_where_filter(chunk_types: list[str] | None):
    if not chunk_types:
        return None
    return {"chunk_type": {"$in": chunk_types}}


def _build_metadata(record: EmbeddingRecord) -> dict[str, str | int]:
    metadata: dict[str, str | int] = {
        "document_id": record.document_id,
        "section_id": record.section_id,
        "chunk_type": record.chunk_type,
        "heading_path_titles_json": json.dumps(
            record.heading_path_titles,
            ensure_ascii=False,
        ),
    }
    if record.page_start is not None:
        metadata["page_start"] = record.page_start
    if record.page_end is not None:
        metadata["page_end"] = record.page_end
    return metadata
