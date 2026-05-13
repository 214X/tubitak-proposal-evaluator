from pydantic import BaseModel


class UploadSessionResponse(BaseModel):
    session_id: str
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_at: str
