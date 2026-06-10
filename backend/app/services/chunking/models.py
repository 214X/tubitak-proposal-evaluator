from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ChunkType = Literal["qa", "narrative", "table", "list"]


class SectionContainer(BaseModel):
    id: str                                      # stable parser-generated section identifier, usually derived from the leaf heading
    heading_path_ids: list[str]                  # heading codes from root to the leaf section such as ["2", "2.1"]
    heading_path_titles: list[str]               # human-readable heading titles from root to the leaf section
    leaf_heading: str                            # final heading title that directly owns the section content
    page_start: int | None = None                # first page covered by the leaf section
    page_end: int | None = None                  # last page covered by the leaf section
    content_refs: list[str]                      # parser stream refs attached directly to this leaf section


class BaseChunk(BaseModel):
    chunk_id: str                                # stable chunk identifier such as doc1::2.1::narrative::1
    document_id: str                             # source document identifier used across the chunk set
    section_id: str                              # owning leaf section identifier
    heading_path_ids: list[str]                  # heading codes from root to the owning section
    heading_path_titles: list[str]               # human-readable heading titles from root to the owning section
    chunk_type: ChunkType                        # normalized chunk category used by downstream analysis
    page_start: int | None = None                # first page where this chunk appears
    page_end: int | None = None                  # last page where this chunk appears
    order_in_section: int                        # deterministic order within the owning section
    text_for_embedding: str                      # normalized, human-readable text representation used for embeddings


class QAChunk(BaseChunk):
    chunk_type: Literal["qa"] = "qa"
    question: str                                # normalized question text resolved from the leaf heading or form label
    guidance: str | None = None                  # optional helper text or instructions shown with the question
    answer: str | None = None                    # selected or extracted answer value


class NarrativeChunk(BaseChunk):
    chunk_type: Literal["narrative"] = "narrative"
    text: str                                    # raw narrative text carried by this chunk after normalization
    part_index: int | None = None                # 1-based part number when a long narrative is split into multiple chunks
    part_count: int | None = None                # total number of parts for the split narrative group


class TableChunk(BaseChunk):
    chunk_type: Literal["table"] = "table"
    table_title: str | None = None               # optional title resolved from nearby heading or caption text
    table_columns: list[str]                     # normalized header row values
    table_rows: list[list[str]]                  # normalized row-major cell values


class ListChunk(BaseChunk):
    chunk_type: Literal["list"] = "list"
    items: list[str]                             # normalized list items preserved in reading order


class ChunkOutput(BaseModel):
    document_id: str                             # source document identifier for the entire chunk output
    sections: list[SectionContainer]             # leaf-heading containers used as chunk grouping context
    chunks: list[QAChunk | NarrativeChunk | TableChunk | ListChunk]  # final chunk set ready for embedding and analysis
