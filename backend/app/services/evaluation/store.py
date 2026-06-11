from __future__ import annotations

import json
import shutil
from pathlib import Path
from threading import Lock

from app.services.evaluation.models import EvaluationState
from app.services.upload.service import ensure_upload_storage, session_dir, validate_session_id

EVALUATION_DIR_NAME = "evaluation"
EVALUATION_STATE_FILE_NAME = "evaluation_state.json"
STORE_LOCK = Lock()


def evaluation_dir(session_id: str) -> Path:
    validate_session_id(session_id)
    return session_dir(session_id) / EVALUATION_DIR_NAME


def evaluation_state_path(session_id: str) -> Path:
    return evaluation_dir(session_id) / EVALUATION_STATE_FILE_NAME


def ensure_evaluation_dir(session_id: str) -> Path:
    ensure_upload_storage()
    current_evaluation_dir = evaluation_dir(session_id)
    current_evaluation_dir.mkdir(parents=True, exist_ok=True)
    return current_evaluation_dir


def read_evaluation_state(session_id: str) -> EvaluationState | None:
    current_state_path = evaluation_state_path(session_id)

    with STORE_LOCK:
        if not current_state_path.exists():
            return None

        payload = json.loads(current_state_path.read_text(encoding="utf-8"))

    return EvaluationState.model_validate(payload)


def write_evaluation_state(state: EvaluationState) -> EvaluationState:
    current_evaluation_dir = ensure_evaluation_dir(state.session_id)
    current_state_path = current_evaluation_dir / EVALUATION_STATE_FILE_NAME

    with STORE_LOCK:
        current_state_path.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    return state


def clear_evaluation_state(session_id: str) -> None:
    current_evaluation_dir = evaluation_dir(session_id)

    with STORE_LOCK:
        if current_evaluation_dir.exists():
            shutil.rmtree(current_evaluation_dir, ignore_errors=True)
