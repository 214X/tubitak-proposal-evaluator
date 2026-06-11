from fastapi import APIRouter, File, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.services.upload.schemas import UploadSessionResponse
from app.services.upload.service import (
    clear_session_upload,
    get_session_upload,
    get_session_upload_path,
    save_upload,
    touch_session_upload,
)

router = APIRouter()


def resolve_session_id(
    x_session_id: str | None = None,
    session_id: str | None = None,
) -> str:
    resolved_session_id = x_session_id or session_id

    if not resolved_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A session id is required.",
        )

    return resolved_session_id


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


@router.get("/current/content")
def read_current_upload_content(
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    session_id: str | None = Query(default=None),
) -> FileResponse:
    resolved_session_id = resolve_session_id(x_session_id=x_session_id, session_id=session_id)
    file_path = get_session_upload_path(resolved_session_id)
    media_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else None

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_type,
        content_disposition_type="inline" if media_type == "application/pdf" else "attachment",
    )
