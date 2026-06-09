from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.services.extraction.models import ExtractionOutput, ParserOutput

AnalysisStatus = Literal["idle", "queued", "extracting", "parsing", "completed", "failed"]
AnalysisStep = Literal["none", "extractor", "parser", "done"]


class AnalysisState(BaseModel):
    session_id: str                              # session that owns this analysis lifecycle
    status: AnalysisStatus                       # current overall job status
    current_step: AnalysisStep                  # currently active analysis step
    file_name: str | None = None                # uploaded source file name when available
    started_at: str | None = None               # first timestamp when analysis run started
    updated_at: str | None = None               # latest state mutation timestamp
    error: str | None = None                    # human-readable error message when status == failed
    extraction_output: ExtractionOutput | None = None  # completed extraction artifact when available
    parser_output: ParserOutput | None = None          # completed parser artifact when available
