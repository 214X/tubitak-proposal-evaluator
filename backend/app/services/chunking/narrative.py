from __future__ import annotations

import re

from app.services.extraction.models import ParserStreamItem

MIN_CHUNK_LENGTH = 300
TARGET_CHUNK_LENGTH = 1400
MAX_CHUNK_LENGTH = 1800
OVERLAP_MAX_CHARS = 180
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def split_narrative_blocks(
    blocks: list[tuple[ParserStreamItem, str]],
) -> list[tuple[list[ParserStreamItem], str]]:
    # Narrative splitting now prefers section coherence over parser-block
    # granularity. We first aggregate consecutive narrative paragraphs within a
    # heading into larger semantic spans, then split only when the combined
    # text becomes too large.
    if not blocks:
        return []

    merged_blocks = _group_blocks_into_chunks(blocks)
    split_blocks: list[tuple[list[ParserStreamItem], str]] = []

    for items, text in merged_blocks:
        if len(text) <= MAX_CHUNK_LENGTH:
            split_blocks.append((items, text))
            continue

        split_parts = _split_long_text(text)
        for part in split_parts:
            split_blocks.append((items, part))

    return split_blocks


def _group_blocks_into_chunks(
    blocks: list[tuple[ParserStreamItem, str]],
) -> list[tuple[list[ParserStreamItem], str]]:
    grouped: list[tuple[list[ParserStreamItem], str]] = []
    current_items: list[ParserStreamItem] = []
    current_parts: list[str] = []
    current_length = 0

    for item, text in blocks:
        if not current_parts:
            current_items = [item]
            current_parts = [text]
            current_length = len(text)
            continue

        candidate_length = current_length + len(text) + 2
        if candidate_length <= TARGET_CHUNK_LENGTH or current_length < MIN_CHUNK_LENGTH:
            current_items.append(item)
            current_parts.append(text)
            current_length = candidate_length
            continue

        grouped.append((current_items, "\n\n".join(current_parts).strip()))
        current_items = [item]
        current_parts = [text]
        current_length = len(text)

    if current_parts:
        grouped.append((current_items, "\n\n".join(current_parts).strip()))

    return grouped


def _split_long_text(text: str) -> list[str]:
    # Split only when a merged narrative body becomes too large for retrieval.
    # We preserve some trailing context as overlap so adjacent parts do not
    # lose continuity around the split boundary.
    parts: list[str] = []
    remaining = text.strip()

    while len(remaining) > MAX_CHUNK_LENGTH:
        split_at = _find_split_boundary(remaining)
        if split_at <= 0:
            split_at = MAX_CHUNK_LENGTH

        current = remaining[:split_at].strip()
        if current:
            parts.append(current)
        overlap = _extract_overlap_suffix(current)
        remaining = remaining[split_at:].strip()
        if overlap and remaining:
            remaining = f"{overlap} {remaining}".strip()

    if remaining:
        parts.append(remaining)

    return parts


def _find_split_boundary(text: str) -> int:
    candidate_region = text[:MAX_CHUNK_LENGTH]

    for delimiter in ("\n\n", ". ", "! ", "? ", "; ", ": "):
        index = candidate_region.rfind(delimiter)
        if index >= MIN_CHUNK_LENGTH:
            return index + len(delimiter)

    return candidate_region.rfind(" ")


def _extract_overlap_suffix(text: str) -> str:
    if len(text) <= OVERLAP_MAX_CHARS:
        return text

    sentences = [segment.strip() for segment in SENTENCE_SPLIT_PATTERN.split(text) if segment.strip()]
    if sentences:
        last_sentence = sentences[-1]
        if 40 <= len(last_sentence) <= OVERLAP_MAX_CHARS:
            return last_sentence

    suffix = text[-OVERLAP_MAX_CHARS:].strip()
    first_space = suffix.find(" ")
    if first_space > 0:
        suffix = suffix[first_space + 1 :].strip()
    return suffix
