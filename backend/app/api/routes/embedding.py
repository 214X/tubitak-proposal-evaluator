from fastapi import APIRouter, Header

from app.services.embedding.models import (
    EmbeddingOutput,
    EmbeddingSearchRequest,
    EmbeddingSearchResponse,
)
from app.services.embedding.service import (
    get_current_embedding_output,
    search_current_embeddings,
)

router = APIRouter()


@router.get("/current", response_model=EmbeddingOutput)
def read_current_embedding(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> EmbeddingOutput:
    return get_current_embedding_output(x_session_id)


@router.post("/current/search", response_model=EmbeddingSearchResponse)
def search_embedding_for_current_session(
    request: EmbeddingSearchRequest,
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> EmbeddingSearchResponse:
    return search_current_embeddings(x_session_id, request)
