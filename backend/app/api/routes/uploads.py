from fastapi import APIRouter, File, Header, Response, UploadFile, status

from app.services.upload.schemas import UploadSessionResponse
from app.services.upload.service import (
    clear_session_upload,
    get_session_upload,
    save_upload,
    touch_session_upload,
)

router = APIRouter()


@router.post("", response_model=UploadSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_upload(
    file: UploadFile = File(...),
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> UploadSessionResponse:
    return await save_upload(session_id=x_session_id, upload=file)


@router.get("/current", response_model=UploadSessionResponse)
def read_current_upload(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> UploadSessionResponse:
    return get_session_upload(x_session_id)


@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_upload(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> Response:
    clear_session_upload(x_session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/current/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat_current_upload(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> Response:
    touch_session_upload(x_session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
