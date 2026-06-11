from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.services.embedding.store import clear_session_embeddings
from app.services.upload.schemas import UploadSessionResponse

SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
METADATA_FILE_NAME = "metadata.json"
lock = Lock()


def ensure_upload_storage() -> None:
    storage_dir().mkdir(parents=True, exist_ok=True)


def storage_dir() -> Path:
    return Path(__file__).resolve().parents[3] / settings.upload_storage_dir


def session_dir(session_id: str) -> Path:
    validate_session_id(session_id)
    return storage_dir() / session_id


def metadata_path(session_id: str) -> Path:
    return session_dir(session_id) / METADATA_FILE_NAME


def timestamp_now() -> str:
    return datetime.now(UTC).isoformat()


def read_metadata_payload(current_metadata_path: Path) -> dict[str, str | int]:
    return json.loads(current_metadata_path.read_text(encoding="utf-8"))


def write_metadata_payload(current_metadata_path: Path, payload: dict[str, str | int]) -> None:
    current_metadata_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def metadata_to_response(payload: dict[str, str | int]) -> UploadSessionResponse:
    return UploadSessionResponse.model_validate(
        {
            "session_id": payload["session_id"],
            "file_name": payload["file_name"],
            "content_type": payload["content_type"],
            "size_bytes": payload["size_bytes"],
            "uploaded_at": payload["uploaded_at"],
        }
    )


def prune_expired_sessions() -> None:
    ensure_upload_storage()
    now = datetime.now(UTC)

    for current_session_dir in storage_dir().iterdir():
        if not current_session_dir.is_dir():
            continue

        current_metadata_path = current_session_dir / METADATA_FILE_NAME
        if not current_metadata_path.exists():
            shutil.rmtree(current_session_dir, ignore_errors=True)
            continue

        try:
            payload = read_metadata_payload(current_metadata_path)
            last_seen_at = datetime.fromisoformat(str(payload["last_seen_at"]))
        except (KeyError, ValueError, json.JSONDecodeError):
            shutil.rmtree(current_session_dir, ignore_errors=True)
            continue

        session_age_seconds = (now - last_seen_at).total_seconds()
        if session_age_seconds > settings.upload_session_timeout_seconds:
            shutil.rmtree(current_session_dir, ignore_errors=True)


def validate_session_id(session_id: str) -> None:
    if not SESSION_PATTERN.match(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session id.",
        )


def validate_file_name(file_name: str | None) -> str:
    if not file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file name is required.",
        )

    sanitized_name = Path(file_name).name
    extension = Path(sanitized_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOC, and DOCX files are supported.",
        )

    return sanitized_name


async def save_upload(session_id: str, upload: UploadFile) -> UploadSessionResponse:
    ensure_upload_storage()
    file_name = validate_file_name(upload.filename)
    uploaded_at = timestamp_now()
    current_session_dir = session_dir(session_id)
    file_path = current_session_dir / file_name
    file_bytes = await upload.read()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    metadata_payload = {
        "session_id": session_id,
        "file_name": file_name,
        "content_type": upload.content_type or "application/octet-stream",
        "size_bytes": len(file_bytes),
        "uploaded_at": uploaded_at,
        "last_seen_at": uploaded_at,
    }

    with lock:
        prune_expired_sessions()
        if current_session_dir.exists():
            shutil.rmtree(current_session_dir)
        clear_session_embeddings(session_id)

        current_session_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(file_bytes)
        write_metadata_payload(metadata_path(session_id), metadata_payload)

    await upload.close()
    return metadata_to_response(metadata_payload)


def get_session_upload(session_id: str) -> UploadSessionResponse:
    current_metadata_path = metadata_path(session_id)

    with lock:
        prune_expired_sessions()
        if not current_metadata_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No uploaded file found for this session.",
            )
        payload = read_metadata_payload(current_metadata_path)

    return metadata_to_response(payload)


def get_session_upload_path(session_id: str) -> Path:
    current_metadata_path = metadata_path(session_id)

    with lock:
        prune_expired_sessions()
        if not current_metadata_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No uploaded file found for this session.",
            )

        payload = read_metadata_payload(current_metadata_path)
        file_name = str(payload.get("file_name", ""))
        file_path = session_dir(session_id) / file_name

        if not file_name or not file_path.exists() or not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Uploaded file could not be found for this session.",
            )

    return file_path


def touch_session_upload(session_id: str) -> None:
    current_metadata_path = metadata_path(session_id)

    with lock:
        prune_expired_sessions()
        if not current_metadata_path.exists():
            return

        payload = read_metadata_payload(current_metadata_path)
        payload["last_seen_at"] = timestamp_now()
        write_metadata_payload(current_metadata_path, payload)


def clear_session_upload(session_id: str) -> None:
    current_session_dir = session_dir(session_id)

    with lock:
        prune_expired_sessions()
        if current_session_dir.exists():
            shutil.rmtree(current_session_dir)
        clear_session_embeddings(session_id)
