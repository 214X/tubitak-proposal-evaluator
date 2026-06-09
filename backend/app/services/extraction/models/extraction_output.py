from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ExtractionDocument(BaseModel):
    file_name: str                  # original uploaded file name
    page_count: int                 # total number of pages detected in the source document


class ExtractionOutput(BaseModel):
    document: ExtractionDocument    # lightweight metadata for the extracted source document
    docling_output: dict[str, Any]  # raw Docling document dump returned directly for the current extraction stage
