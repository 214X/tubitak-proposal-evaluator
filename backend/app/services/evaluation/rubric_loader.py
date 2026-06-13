from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.services.evaluation.models import EvaluationRubric

_CACHED_RUBRIC: EvaluationRubric | None = None
_CACHED_MTIME_NS: int | None = None


def rubric_path() -> Path:
    return Path(__file__).resolve().parents[3] / settings.evaluation_rubric_path


def load_default_rubric() -> EvaluationRubric:
    global _CACHED_MTIME_NS, _CACHED_RUBRIC

    path = rubric_path()
    current_mtime_ns = path.stat().st_mtime_ns
    if _CACHED_RUBRIC is not None and _CACHED_MTIME_NS == current_mtime_ns:
        return _CACHED_RUBRIC

    payload = json.loads(path.read_text(encoding="utf-8"))
    _CACHED_RUBRIC = EvaluationRubric.model_validate(payload)
    _CACHED_MTIME_NS = current_mtime_ns
    return _CACHED_RUBRIC
