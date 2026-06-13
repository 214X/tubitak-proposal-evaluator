from __future__ import annotations

import re
from typing import Any

from app.services.extraction.models import ParserStreamItem

QUESTION_HEADING_PATTERN = re.compile(
    r"\b(kaç|hangi|hangisi|nedir|ne kadar|var mı|uygun mu|belirtiniz|giriniz|yazınız)\b",
    re.IGNORECASE,
)
ANSWER_LIKE_PATTERN = re.compile(
    r"\b(evet|hayır|var|yok|uygun|uygun değil|seçilmiştir|seçilmiştir|arası|yıl|ay)\b",
    re.IGNORECASE,
)


def looks_like_question_heading(text: str | None) -> bool:
    # We keep question-heading detection intentionally simple in V1. The goal
    # is not perfect linguistic understanding; it is to catch obvious form-like
    # headings and let uncertain cases fall back to narrative handling.
    if not text:
        return False

    normalized = " ".join(text.split()).strip()
    if not normalized:
        return False
    if normalized.endswith("?"):
        return True
    return bool(QUESTION_HEADING_PATTERN.search(normalized))


def is_qa_candidate(
    leaf_heading: str,
    items: list[ParserStreamItem],
) -> bool:
    # A section becomes a QA candidate only when the heading itself looks like
    # a question and the attached content resembles a short answer-style block.
    # When the signal is weak, we intentionally return False and let later
    # stages treat the content as narrative or mixed material instead.
    if not looks_like_question_heading(leaf_heading):
        return False
    if not items:
        return False

    for item in items:
        if is_table_block(item) or is_list_block(item):
            continue
        if item.item_type == "form_item":
            return True

        text = _extract_text_like_content(item)
        if not text:
            continue

        normalized = " ".join(text.split()).strip()
        if not normalized:
            continue
        if len(normalized) <= 120:
            return True
        if ANSWER_LIKE_PATTERN.search(normalized):
            return True

    return False


def is_table_block(item: ParserStreamItem) -> bool:
    # Parser stream items already normalize table references, so heuristics are
    # intentionally lightweight here.
    if item.item_type == "table":
        return True
    if item.item_type == "picture" and isinstance(item.content, dict):
        return item.content.get("type") == "gantt_chart"
    return item.label == "table"


def is_list_block(item: ParserStreamItem) -> bool:
    # Lists can arrive either as normalized group items with list payloads or
    # as text nodes whose labels still indicate a list-origin line.
    if item.item_type == "group" and isinstance(item.content, dict):
        return item.content.get("type") == "list"
    return item.label == "list_item"


def _extract_text_like_content(item: ParserStreamItem) -> str | None:
    if isinstance(item.content, str):
        return item.content

    if isinstance(item.content, dict):
        for key in ("text", "value", "content", "label"):
            value = item.content.get(key)
            if isinstance(value, str):
                return value

        list_items = item.content.get("items")
        if isinstance(list_items, list):
            rendered_items = [entry for entry in list_items if isinstance(entry, str)]
            if rendered_items:
                return "\n".join(rendered_items)

    return _stringify_scalar(item.content)


def _stringify_scalar(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return str(value)
    return None
