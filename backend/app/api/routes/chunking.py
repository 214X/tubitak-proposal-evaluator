from fastapi import APIRouter, Header

from app.services.chunking.models import ChunkOutput
from app.services.chunking.service import get_current_chunk_output

router = APIRouter()


@router.post("/current/chunk-output", response_model=ChunkOutput)
def read_current_chunk_output(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> ChunkOutput:
    return get_current_chunk_output(x_session_id)
