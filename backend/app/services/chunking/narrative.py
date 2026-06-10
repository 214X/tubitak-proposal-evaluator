from __future__ import annotations

from app.services.extraction.models import ParserStreamItem

MIN_BLOCK_LENGTH = 150
MAX_BLOCK_LENGTH = 700


def split_narrative_blocks(
    blocks: list[tuple[ParserStreamItem, str]],
) -> list[tuple[list[ParserStreamItem], str]]:
    # Narrative splitting works on already normalized text blocks. We first
    # merge undersized neighbors to avoid noisy tiny chunks, then split any
    # remaining oversized block on sentence-like boundaries.
    if not blocks:
        return []

    merged_blocks = _merge_short_blocks(blocks)
    split_blocks: list[tuple[list[ParserStreamItem], str]] = []

    for item, text in merged_blocks:
        if len(text) <= MAX_BLOCK_LENGTH:
            split_blocks.append(([item], text))
            continue

        split_parts = _split_long_text(text)
        for part in split_parts:
            split_blocks.append(([item], part))

    return split_blocks


def _merge_short_blocks(
    blocks: list[tuple[ParserStreamItem, str]],
) -> list[tuple[ParserStreamItem, str]]:
    # Keep merge logic local and predictable: consecutive short blocks are
    # folded into the previous block when possible, otherwise they start a new
    # merged segment.
    merged: list[tuple[ParserStreamItem, str]] = []

    for item, text in blocks:
        if not merged:
            merged.append((item, text))
            continue

        previous_item, previous_text = merged[-1]
        if len(text) < MIN_BLOCK_LENGTH or len(previous_text) < MIN_BLOCK_LENGTH:
            merged[-1] = (previous_item, f"{previous_text}\n\n{text}".strip())
            continue

        merged.append((item, text))

    return merged


def _split_long_text(text: str) -> list[str]:
    # Sentence-aware splitting is intentionally lightweight. We split on
    # paragraph boundaries first, then sentence-like punctuation, and only fall
    # back to a hard cut when no better boundary exists.
    parts: list[str] = []
    remaining = text.strip()

    while len(remaining) > MAX_BLOCK_LENGTH:
        split_at = _find_split_boundary(remaining)
        if split_at <= 0:
            split_at = MAX_BLOCK_LENGTH

        current = remaining[:split_at].strip()
        if current:
            parts.append(current)
        remaining = remaining[split_at:].strip()

    if remaining:
        parts.append(remaining)

    return parts


def _find_split_boundary(text: str) -> int:
    candidate_region = text[:MAX_BLOCK_LENGTH]

    for delimiter in ("\n\n", ". ", "! ", "? ", "; ", ": "):
        index = candidate_region.rfind(delimiter)
        if index >= MIN_BLOCK_LENGTH:
            return index + len(delimiter)

    return candidate_region.rfind(" ")
