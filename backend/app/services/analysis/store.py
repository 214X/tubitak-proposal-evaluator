from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from app.services.analysis.models import AnalysisState
from app.services.upload.service import ensure_upload_storage, session_dir, validate_session_id

ANALYSIS_DIR_NAME = "analysis"
ANALYSIS_STATE_FILE_NAME = "analysis_state.json"
STORE_LOCK = Lock()


def analysis_dir(session_id: str) -> Path:
    validate_session_id(session_id)
    return session_dir(session_id) / ANALYSIS_DIR_NAME


def analysis_state_path(session_id: str) -> Path:
    return analysis_dir(session_id) / ANALYSIS_STATE_FILE_NAME


def ensure_analysis_dir(session_id: str) -> Path:
    ensure_upload_storage()
    current_analysis_dir = analysis_dir(session_id)
    current_analysis_dir.mkdir(parents=True, exist_ok=True)
    return current_analysis_dir


def read_analysis_state(session_id: str) -> AnalysisState | None:
    current_state_path = analysis_state_path(session_id)

    with STORE_LOCK:
        if not current_state_path.exists():
            return None

        payload = json.loads(current_state_path.read_text(encoding="utf-8"))

    return AnalysisState.model_validate(payload)


def write_analysis_state(state: AnalysisState) -> AnalysisState:
    current_analysis_dir = ensure_analysis_dir(state.session_id)
    current_state_path = current_analysis_dir / ANALYSIS_STATE_FILE_NAME

    with STORE_LOCK:
        current_state_path.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    return state
