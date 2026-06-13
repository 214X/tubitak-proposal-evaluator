from __future__ import annotations

import re
from typing import Any

from app.services.chunking.classifiers import (
    is_list_block,
    is_qa_candidate,
    is_table_block,
)
from app.services.chunking.embedding_text import (
    build_list_embedding_text,
    build_narrative_embedding_text,
    build_qa_embedding_text,
    build_table_embedding_text,
)
from app.services.chunking.models import (
    ChunkOutput,
    ListChunk,
    NarrativeChunk,
    QAChunk,
    SectionContainer,
    TableChunk,
)
from app.services.chunking.narrative import split_narrative_blocks
from app.services.chunking.sections import build_section_containers
from app.services.chunking.tables import (
    extract_table_columns,
    extract_table_rows,
    extract_table_title,
)
from app.services.extraction.models import HeadingHierarchyNode, ParserStreamItem

PAGE_MARKER_PATTERN = re.compile(r"^\d+\s*/\s*\d+$")
LONG_NUMERIC_ID_PATTERN = re.compile(r"^\d{5,}$")
NUMERIC_ID_WITH_PAGE_PATTERN = re.compile(r"^\d{5,}\s+\d+\s*/\s*\d+$")
PLACEHOLDER_TEXTS = {
    "picture",
    "image",
    "figure",
}


def build_chunk_output(
    document_id: str,
    content_stream: list[ParserStreamItem],
    heading_hierarchy: list[HeadingHierarchyNode],
) -> ChunkOutput:
    # Chunk output is built in two phases:
    # 1. derive leaf-based section containers from the parser hierarchy,
    # 2. turn each section's ordered stream items into typed chunk objects.
    sections = build_section_containers(content_stream, heading_hierarchy)
    item_by_ref = {item.ref: item for item in content_stream}
    chunks: list[QAChunk | NarrativeChunk | TableChunk | ListChunk] = []

    for section in sections:
        section_items = [
            item_by_ref[ref]
            for ref in section.content_refs
            if ref in item_by_ref
        ]

        order_in_section = 1

        if is_qa_candidate(section.leaf_heading, section_items):
            qa_chunk = _build_qa_chunk(document_id, section, section_items, order_in_section)
            if qa_chunk is not None:
                chunks.append(qa_chunk)
                order_in_section += 1

        for item in section_items:
            if is_table_block(item):
                chunks.append(_build_table_chunk(document_id, section, item, order_in_section))
                order_in_section += 1
                continue

            if is_list_block(item):
                list_chunk = _build_list_chunk(document_id, section, item, order_in_section)
                if list_chunk is not None:
                    chunks.append(list_chunk)
                    order_in_section += 1
                continue

        narrative_chunks = _build_narrative_chunks(
            document_id=document_id,
            section=section,
            items=section_items,
            starting_order=order_in_section,
        )
        chunks.extend(narrative_chunks)

    return ChunkOutput(
        document_id=document_id,
        sections=sections,
        chunks=chunks,
    )


def _build_qa_chunk(
    document_id: str,
    section: SectionContainer,
    items: list[ParserStreamItem],
    order_in_section: int,
) -> QAChunk | None:
    # V1 QA extraction is intentionally conservative. We always use the leaf
    # heading as the canonical question and then mine short text-like blocks
    # for optional guidance and answer values.
    text_items = [
        item
        for item in items
        if not is_table_block(item) and not is_list_block(item)
    ]
    if not text_items:
        return None

    guidance: str | None = None
    answer: str | None = None

    for item in text_items:
        text = _extract_text_like_content(item)
        if not text:
            continue

        normalized = _normalize_whitespace(text)
        if not normalized:
            continue

        if guidance is None and len(normalized) > 120:
            guidance = normalized
            continue

        if answer is None and len(normalized) <= 120:
            answer = normalized
            continue

    if guidance is None and len(text_items) >= 2:
        first_text = _extract_text_like_content(text_items[0])
        if first_text:
            guidance = _normalize_whitespace(first_text)

    chunk = QAChunk(
        chunk_id=_build_chunk_id(document_id, section, "qa", order_in_section),
        document_id=document_id,
        section_id=section.id,
        heading_path_ids=section.heading_path_ids,
        heading_path_titles=section.heading_path_titles,
        page_start=section.page_start,
        page_end=section.page_end,
        order_in_section=order_in_section,
        text_for_embedding="",
        work_package_id=section.work_package_id,
        work_package_no=section.work_package_no,
        work_package_code=section.work_package_code,
        work_package_title=section.work_package_title,
        work_package_date_range=section.work_package_date_range,
        work_package_duration_text=section.work_package_duration_text,
        work_package_organizations=section.work_package_organizations,
        work_package_section_no=section.work_package_section_no,
        question=section.leaf_heading,
        guidance=guidance,
        answer=answer,
    )
    chunk.text_for_embedding = build_qa_embedding_text(chunk)
    return chunk


def _build_table_chunk(
    document_id: str,
    section: SectionContainer,
    item: ParserStreamItem,
    order_in_section: int,
) -> TableChunk:
    # Table payloads can vary slightly across parser sources, so extraction is
    # shape-tolerant and falls back to line-based content when structure is
    # incomplete.
    table_title = extract_table_title(item.content)
    table_columns = extract_table_columns(item.content)
    table_rows = extract_table_rows(item.content)
    chunk = TableChunk(
        chunk_id=_build_chunk_id(document_id, section, "table", order_in_section),
        document_id=document_id,
        section_id=section.id,
        heading_path_ids=section.heading_path_ids,
        heading_path_titles=section.heading_path_titles,
        page_start=item.page_start or section.page_start,
        page_end=item.page_end or section.page_end,
        order_in_section=order_in_section,
        text_for_embedding="",
        work_package_id=section.work_package_id,
        work_package_no=section.work_package_no,
        work_package_code=section.work_package_code,
        work_package_title=section.work_package_title,
        work_package_date_range=section.work_package_date_range,
        work_package_duration_text=section.work_package_duration_text,
        work_package_organizations=section.work_package_organizations,
        work_package_section_no=section.work_package_section_no,
        table_title=table_title,
        table_columns=table_columns,
        table_rows=table_rows,
    )
    chunk.text_for_embedding = build_table_embedding_text(chunk)
    return chunk


def _build_list_chunk(
    document_id: str,
    section: SectionContainer,
    item: ParserStreamItem,
    order_in_section: int,
) -> ListChunk | None:
    items = _extract_list_items(item)
    if not items:
        return None

    chunk = ListChunk(
        chunk_id=_build_chunk_id(document_id, section, "list", order_in_section),
        document_id=document_id,
        section_id=section.id,
        heading_path_ids=section.heading_path_ids,
        heading_path_titles=section.heading_path_titles,
        page_start=item.page_start or section.page_start,
        page_end=item.page_end or section.page_end,
        order_in_section=order_in_section,
        text_for_embedding="",
        work_package_id=section.work_package_id,
        work_package_no=section.work_package_no,
        work_package_code=section.work_package_code,
        work_package_title=section.work_package_title,
        work_package_date_range=section.work_package_date_range,
        work_package_duration_text=section.work_package_duration_text,
        work_package_organizations=section.work_package_organizations,
        work_package_section_no=section.work_package_section_no,
        items=items,
    )
    chunk.text_for_embedding = build_list_embedding_text(chunk)
    return chunk


def _build_narrative_chunks(
    document_id: str,
    section: SectionContainer,
    items: list[ParserStreamItem],
    starting_order: int,
) -> list[NarrativeChunk]:
    # Narrative chunks are assembled from non-table, non-list text-like items.
    # We also drop short answer-style fragments when the section already
    # qualified as QA so we do not duplicate the obvious answer block.
    narrative_blocks: list[tuple[ParserStreamItem, str]] = []
    qa_section = is_qa_candidate(section.leaf_heading, items)

    for item in items:
        if is_table_block(item) or is_list_block(item):
            continue

        text = _extract_text_like_content(item)
        normalized = _normalize_whitespace(text)
        if not normalized:
            continue
        if _is_noise_text(normalized):
            continue
        if qa_section and len(normalized) <= 120:
            continue

        narrative_blocks.append((item, normalized))

    if not narrative_blocks:
        return []

    split_blocks = split_narrative_blocks(narrative_blocks)
    chunks: list[NarrativeChunk] = []
    total_parts = len(split_blocks)

    for index, (source_items, text) in enumerate(split_blocks, start=1):
        first_item = source_items[0]
        last_item = source_items[-1]
        chunk = NarrativeChunk(
            chunk_id=_build_chunk_id(document_id, section, "narrative", starting_order + index - 1),
            document_id=document_id,
            section_id=section.id,
            heading_path_ids=section.heading_path_ids,
            heading_path_titles=section.heading_path_titles,
            page_start=first_item.page_start or section.page_start,
            page_end=last_item.page_end or section.page_end,
            order_in_section=starting_order + index - 1,
            text_for_embedding="",
            work_package_id=section.work_package_id,
            work_package_no=section.work_package_no,
            work_package_code=section.work_package_code,
            work_package_title=section.work_package_title,
            work_package_date_range=section.work_package_date_range,
            work_package_duration_text=section.work_package_duration_text,
            work_package_organizations=section.work_package_organizations,
            work_package_section_no=section.work_package_section_no,
            text=text,
            part_index=index if total_parts > 1 else None,
            part_count=total_parts if total_parts > 1 else None,
        )
        chunk.text_for_embedding = build_narrative_embedding_text(chunk)
        chunks.append(chunk)

    return chunks


def _build_chunk_id(
    document_id: str,
    section: SectionContainer,
    chunk_type: str,
    order_in_section: int,
) -> str:
    return f"{document_id}::{section.id}::{chunk_type}::{order_in_section}"


def _extract_text_like_content(content: Any) -> str | None:
    if isinstance(content, ParserStreamItem):
        return _extract_text_like_content(content.content)

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        for key in ("text", "value", "content", "label"):
            value = content.get(key)
            if isinstance(value, str):
                return value
        if isinstance(content.get("items"), list):
            parts = [entry for entry in content["items"] if isinstance(entry, str)]
            if parts:
                return "\n".join(parts)

    return None


def _normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split()).strip()


def _extract_list_items(item: ParserStreamItem) -> list[str]:
    if isinstance(item.content, dict):
        raw_items = item.content.get("items")
        if isinstance(raw_items, list):
            return [
                normalized
                for entry in raw_items
                if isinstance(entry, str)
                if (normalized := _normalize_whitespace(entry))
            ]

    text = _extract_text_like_content(item)
    normalized = _normalize_whitespace(text)
    if not normalized:
        return []
    return [normalized]


def _is_noise_text(text: str) -> bool:
    # These filters intentionally target only low-risk parser/layout residue.
    # We avoid semantic heuristics here so short but meaningful values such as
    # "KOBİ (Mikro)" or "11,9 ay" are preserved for later analysis.
    lowered = text.casefold()

    if lowered in PLACEHOLDER_TEXTS:
        return True

    if PAGE_MARKER_PATTERN.fullmatch(text):
        return True

    if LONG_NUMERIC_ID_PATTERN.fullmatch(text):
        return True

    if NUMERIC_ID_WITH_PAGE_PATTERN.fullmatch(text):
        return True

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True

    if len(lines) == 2 and LONG_NUMERIC_ID_PATTERN.fullmatch(lines[0]) and PAGE_MARKER_PATTERN.fullmatch(lines[1]):
        return True

    if all(line.casefold() in PLACEHOLDER_TEXTS for line in lines):
        return True

    return False
