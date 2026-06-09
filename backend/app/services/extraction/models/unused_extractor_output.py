from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator

# This file is intentionally kept as an unused snapshot of the earlier
# normalized block-based extractor response. It is not part of the active
# runtime path anymore, but it may still be useful as reference while the
# parser/final structured output design is evolving.

ExtractorBlockType = Literal["text", "table"]


class ExtractorDocument(BaseModel):
    file_name: str                      # original uploaded file name
    page_count: int                     # total number of pages detected in the source document


class ExtractorBlock(BaseModel):
    id: str                             # stable internal identifier for the extracted block
    type: ExtractorBlockType            # plain text block || Docling table block
    label: str                          # original Docling label such as section_header or table
    order: int                          # preserves the original block order from Docling body traversal
    page_start: int                     # first page covered by this block
    page_end: int                       # last page covered by this block
    text: str | None = None             # normalized text content for text blocks
    table: dict[str, Any] | None = None # Docling-native table payload for table blocks

    @model_validator(mode="after")
    def validate_content_shape(self) -> ExtractorBlock:
        # Keep each block aligned with its declared content type.
        if self.type == "text":
            if not self.text:
                raise ValueError("Text blocks must include text.")
            if self.table is not None:
                raise ValueError("Text blocks cannot include table content.")

        if self.type == "table":
            if self.table is None:
                raise ValueError("Table blocks must include table content.")
            if self.text is not None:
                raise ValueError("Table blocks cannot include text content.")

        return self


class ExtractorPage(BaseModel):
    page: int                           # 1-based page number from the source document
    blocks: list[ExtractorBlock]        # ordered list of extracted blocks for this page


class ExtractorOutput(BaseModel):
    document: ExtractorDocument         # basic metadata about the extracted source document
    pages: list[ExtractorPage]          # ordered page list produced by the Docling extractor stage
    docling_output: dict[str, Any]      # raw Docling document dump kept for test and inspection purposes
