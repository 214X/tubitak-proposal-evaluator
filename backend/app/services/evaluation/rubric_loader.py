from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.services.evaluation.models import EvaluationRubric


def rubric_path() -> Path:
    return Path(__file__).resolve().parents[3] / settings.evaluation_rubric_path


@lru_cache(maxsize=1)
def load_default_rubric() -> EvaluationRubric:
    payload = json.loads(rubric_path().read_text(encoding="utf-8"))
    return EvaluationRubric.model_validate(payload)
