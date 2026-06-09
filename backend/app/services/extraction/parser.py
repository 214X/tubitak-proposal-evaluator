from __future__ import annotations

import re
from typing import Any

from app.services.extraction.models.parser_output import (
    HeadingHierarchyNode,
    ParserStreamItem,
    ParserStreamItemType,
)

ALLOWED_HEADING_LABELS = {"section_header", "list_item", "page_header"}
ALPHA_HEADING_PATTERN = re.compile(
    r"^(?P<code>[A-ZÇĞİÖŞÜ]\.(?:\d+(?:\.\d+)*)?)(?:\s*-\s*(?P<title>.+))?$"
)
ALPHA_HEADING_DOTTED_PATTERN = re.compile(
    r"^(?P<code>[A-ZÇĞİÖŞÜ]\.(?:\d+(?:\.\d+)*)\.)\s*(?P<title>.*)$"
)
TABLE_HEADING_PATTERN = re.compile(r"^(?P<code>M\d{3})(?:\s*-\s*(?P<title>.+))?$")
NUMBERED_HEADING_PATTERN = re.compile(
    r"^(?P<code>\d+(?:\.\d+)*)(?:\s*[-.)]\s*(?P<title>.+)|\.\s*(?P<title_dotted>.*))$"
)
NUMBERED_LINE_PATTERN = re.compile(r"^(?P<number>\d+)\s*-\s+")


def parse_docling_content_stream(docling_output: dict[str, Any]) -> list[ParserStreamItem]:
    # Convert Docling's body.children sequence into a flat, ordered parser stream.
    #
    # Why this model exists:
    # - Docling already gives us a strong reading order through body.children.
    # - The same document does not necessarily expose useful semantic
    #   parent-child relationships through per-item children fields.
    # - Our next parser stages will build real heading hierarchy from sequence,
    #   not from Docling's sparse child links.
    #
    # So this function intentionally returns a flat list instead of a tree.
    # Every stream item keeps the information later stages need:
    # - stable order,
    # - reference back to the original Docling item,
    # - normalized type,
    # - Docling label,
    # - page span,
    # - content payload.
    body = docling_output.get("body", {})
    body_children = body.get("children", [])
    content_stream: list[ParserStreamItem] = []
    next_order = 1

    for child in body_children:
        ref = _extract_reference(child)
        if not ref:
            continue

        item = _resolve_reference(docling_output, ref)
        item_type = _resolve_stream_item_type(ref)
        label = _normalize_label(item.get("label"))
        page_start, page_end = _extract_page_range(item)
        previous_text = (
            content_stream[-1].content
            if content_stream
            and content_stream[-1].item_type == "text"
            and isinstance(content_stream[-1].content, str)
            else None
        )

        if item_type == "group" and label == "list":
            list_items = _extract_list_group_items(item, docling_output)
            expanded_stream_items = _expand_sequential_numbered_list_group(
                ref=ref,
                page_start=page_start,
                page_end=page_end,
                items=list_items,
                previous_text=previous_text,
                start_order=next_order,
            )

            if expanded_stream_items is not None:
                content_stream.extend(expanded_stream_items)
                next_order += len(expanded_stream_items)
                continue

            content_stream.append(
                ParserStreamItem(
                    ref=ref,
                    order=next_order,
                    item_type=item_type,
                    label=label,
                    page_start=page_start,
                    page_end=page_end,
                    content={
                        "type": "list",
                        "items": list_items,
                    },
                )
            )
            next_order += 1
            continue

        content = _extract_stream_item_content(item, item_type, docling_output)

        content_stream.append(
            ParserStreamItem(
                ref=ref,
                order=next_order,
                item_type=item_type,
                label=label,
                page_start=page_start,
                page_end=page_end,
                content=content,
            )
        )
        next_order += 1

    return content_stream


def parse_heading_hierarchy(content_stream: list[ParserStreamItem]) -> list[HeadingHierarchyNode]:
    # Build the first semantic heading tree from the flat parser stream.
    #
    # Design choice:
    # - We do not rely on Docling item children for hierarchy because they are
    #   sparse and do not reflect the heading structure we need.
    # - Instead, we infer hierarchy from ordered heading candidates in the
    #   stream using heading code patterns plus a stack-based parser.
    #
    # The resulting tree is still an early parser-stage structure:
    # - headings become nodes,
    # - non-heading stream items are attached to the current active heading via
    #   content_refs,
    # - page_end is expanded as more content is attached under a heading.
    root_nodes: list[HeadingHierarchyNode] = []
    stack: list[HeadingHierarchyNode] = []
    heading_index = 0

    for item in content_stream:
        heading_info = _parse_heading_candidate(item)
        if heading_info is None:
            if stack:
                _attach_content_to_active_heading(stack, item)
            continue

        level = _resolve_heading_level(heading_info, stack)

        heading_index += 1
        node = HeadingHierarchyNode(
            id=f"heading_{heading_index}",
            ref=item.ref,
            node_type=heading_info["node_type"],
            code=heading_info["code"],
            title=heading_info["title"],
            full_text=str(item.content or ""),
            level=level,
            parent_id=None,
            page_start=item.page_start,
            page_end=item.page_end,
            stream_order=item.order,
            path=[],
            content_refs=[],
            children=[],
        )

        # Pop headings at the same or deeper level. The remaining stack top, if
        # any, becomes the parent of the new heading.
        while stack and stack[-1].level >= node.level:
            stack.pop()

        if stack:
            parent = stack[-1]
            node.parent_id = parent.id
            node.path = [*parent.path, node.code]
            parent.children.append(node)
            _extend_heading_page_range(parent, item.page_start, item.page_end)
        else:
            node.path = [node.code]
            root_nodes.append(node)

        stack.append(node)

    return root_nodes


def _resolve_reference(docling_output: dict[str, Any], ref: str) -> dict[str, Any]:
    # Resolve references such as #/texts/12 or #/tables/3 against the raw
    # Docling document dump. If a reference cannot be resolved cleanly, we
    # return an empty payload so the caller can still emit a placeholder item.
    try:
        _, collection_name, index_str = ref.split("/", maxsplit=2)
        collection = docling_output.get(collection_name, [])
        return collection[int(index_str)]
    except (ValueError, IndexError, TypeError):
        return {}


def _resolve_stream_item_type(ref: str) -> ParserStreamItemType:
    # Normalize Docling collection names into a compact parser-specific item
    # type set. This keeps downstream logic independent from Docling's exact
    # top-level array names.
    if ref.startswith("#/texts/"):
        return "text"
    if ref.startswith("#/tables/"):
        return "table"
    if ref.startswith("#/pictures/"):
        return "picture"
    if ref.startswith("#/groups/"):
        return "group"
    if ref.startswith("#/key_value_items/"):
        return "key_value"
    if ref.startswith("#/form_items/"):
        return "form_item"
    return "unknown"


def _extract_reference(item: Any) -> str | None:
    # Docling may emit either "cref" or "$ref" depending on the serialization
    # path. We support both so the parser stays robust against minor output
    # format differences.
    if isinstance(item, dict):
        ref = item.get("cref") or item.get("$ref")
        if ref:
            return str(ref)
    return None


def _extract_stream_item_content(
    item: dict[str, Any],
    item_type: ParserStreamItemType,
    docling_output: dict[str, Any],
) -> Any | None:
    # Content is intentionally stored in the most useful shape for each item:
    # - text items expose their text directly,
    # - table items expose Docling's native table data payload,
    # - list groups are normalized into a light-weight structured list model,
    # - all other item types keep their raw item payload for inspection.
    if item_type == "text":
        return item.get("text")
    if item_type == "table":
        return item.get("data")
    if item_type in {"picture", "group", "key_value", "form_item", "unknown"}:
        return item
    return None


def _extract_list_group_items(
    item: dict[str, Any],
    docling_output: dict[str, Any],
) -> list[str]:
    # Docling represents bullet lists as group nodes whose children point to
    # text items. This helper extracts the visible list lines without forcing a
    # semantic decision about whether they should stay a list or be expanded
    # into ordinary text blocks.
    items: list[str] = []

    for child in item.get("children", []):
        ref = _extract_reference(child)
        if not ref or not ref.startswith("#/texts/"):
            continue

        child_item = _resolve_reference(docling_output, ref)
        text = child_item.get("text")
        if isinstance(text, str):
            normalized = text.strip()
            if normalized:
                items.append(normalized)

    return items


def _expand_sequential_numbered_list_group(
    ref: str,
    page_start: int | None,
    page_end: int | None,
    items: list[str],
    previous_text: str | None = None,
    start_order: int = 1,
) -> list[ParserStreamItem] | None:
    # Some Docling list groups are not real bullet lists. They are actually
    # repeated numbered sections with value rows such as:
    #   7 - Proje Ciktisinin Ekonomik Faaliyet Sinifi ...
    #   62.01 - Bilgisayar programlama faaliyetleri
    #   8 - Proje Ciktisinin GTIP KODU
    #   85 - ...
    #
    # We do not classify rows one by one. Instead, we look for a sequential
    # label flow (7, 8, 9, 10 ...) and then treat the rows between two labels
    # as the content of the earlier label. This keeps "85 - ..." as the value
    # of label 8 instead of misclassifying it as another heading.
    #
    # We only apply the rule when we can detect at least two sequential
    # transitions, so ordinary lists do not get rewritten accidentally.
    label_positions = _find_sequential_label_positions(items, previous_text)
    if len(label_positions) < 2:
        return None

    stream_items: list[ParserStreamItem] = []
    next_order = start_order
    item_index = 1

    # If the first label already exists as the previous text item, only emit
    # its value rows from the group itself.
    if previous_text and label_positions[0] > 0:
        leading_value = "\n".join(items[: label_positions[0]]).strip()
        if leading_value:
            stream_items.append(
                ParserStreamItem(
                    ref=f"{ref}#item-{item_index}",
                    order=next_order,
                    item_type="text",
                    label="text",
                    page_start=page_start,
                    page_end=page_end,
                    content=leading_value,
                )
            )
            next_order += 1
            item_index += 1

    for current_pos, next_pos in zip(label_positions, [*label_positions[1:], len(items)]):
        label_text = items[current_pos]
        value_lines = items[current_pos + 1 : next_pos]
        value_text = "\n".join(value_lines).strip()

        stream_items.append(
            ParserStreamItem(
                ref=f"{ref}#item-{item_index}",
                order=next_order,
                item_type="text",
                label="list_item",
                page_start=page_start,
                page_end=page_end,
                content=label_text,
            )
        )
        next_order += 1
        item_index += 1

        if value_text:
            stream_items.append(
                ParserStreamItem(
                    ref=f"{ref}#item-{item_index}",
                    order=next_order,
                    item_type="text",
                    label="text",
                    page_start=page_start,
                    page_end=page_end,
                    content=value_text,
                )
            )
            next_order += 1
            item_index += 1

    return stream_items


def _find_sequential_label_positions(
    items: list[str],
    previous_text: str | None = None,
) -> list[int]:
    numbered_candidates = [
        (index, number)
        for index, item in enumerate(items)
        if (number := _extract_leading_number(item)) is not None
    ]
    if not numbered_candidates:
        return []

    label_positions: list[int] = []
    previous_number = _extract_leading_number(previous_text) if previous_text else None

    if previous_number is not None:
        for index, number in numbered_candidates:
            if number == previous_number + 1:
                label_positions.append(index)
                previous_number = number
        return label_positions

    best_run: list[int] = []
    current_run: list[int] = []
    expected_number: int | None = None

    for index, number in numbered_candidates:
        if expected_number is None or number == expected_number:
            current_run.append(index)
            expected_number = number + 1
        else:
            if len(current_run) > len(best_run):
                best_run = current_run
            current_run = [index]
            expected_number = number + 1

    if len(current_run) > len(best_run):
        best_run = current_run

    return best_run if len(best_run) >= 2 else []


def _extract_leading_number(text: str | None) -> int | None:
    if not text:
        return None

    match = NUMBERED_LINE_PATTERN.match(text.strip())
    if not match:
        return None

    number_text = match.group("number")
    try:
        return int(number_text)
    except ValueError:
        return None


def _is_numbered_row(text: str) -> bool:
    return bool(NUMBERED_LINE_PATTERN.match(text.strip()))


def _normalize_label(label: Any) -> str | None:
    # Docling labels can arrive as plain strings or enum-like objects. This
    # helper keeps the parser stream output consistent.
    if label is None:
        return None
    if hasattr(label, "value"):
        return str(label.value)
    return str(label)


def _extract_page_range(item: dict[str, Any]) -> tuple[int | None, int | None]:
    # Provenance information is the source of truth for page tracking.
    # Even if most current items are single-page, we keep range support so
    # multi-page blocks can pass through the parser stream unchanged.
    prov_entries = item.get("prov", [])
    page_numbers = [
        int(entry["page_no"])
        for entry in prov_entries
        if isinstance(entry, dict) and "page_no" in entry
    ]

    if not page_numbers:
        return None, None

    return min(page_numbers), max(page_numbers)


def _parse_heading_candidate(item: ParserStreamItem) -> dict[str, Any] | None:
    # Parse stream items that look like real semantic headings. This function
    # converts a flat stream item into the normalized data needed by the stack
    # parser above.
    if item.item_type != "text":
        return None
    if item.label not in ALLOWED_HEADING_LABELS:
        return None
    if not isinstance(item.content, str):
        return None

    text = item.content.strip()
    if not text:
        return None

    alpha_match = ALPHA_HEADING_PATTERN.match(text)
    if alpha_match:
        code = alpha_match.group("code").rstrip(".")
        title = _normalize_heading_title(alpha_match.group("title"))
        return {
            "node_type": "section_heading",
            "code": code,
            "title": title,
        }

    alpha_dotted_match = ALPHA_HEADING_DOTTED_PATTERN.match(text)
    if alpha_dotted_match:
        code = alpha_dotted_match.group("code").rstrip(".")
        title = _normalize_heading_title(alpha_dotted_match.group("title"))
        return {
            "node_type": "section_heading",
            "code": code,
            "title": title,
        }

    table_match = TABLE_HEADING_PATTERN.match(text)
    if table_match:
        code = table_match.group("code")
        title = _normalize_heading_title(table_match.group("title"))
        return {
            "node_type": "table_heading",
            "code": code,
            "title": title,
        }

    numbered_match = NUMBERED_HEADING_PATTERN.match(text)
    if numbered_match:
        code = numbered_match.group("code")
        title = _normalize_heading_title(
            numbered_match.group("title") or numbered_match.group("title_dotted")
        )
        return {
            "node_type": "numbered_heading",
            "code": code,
            "title": title,
        }

    return None


def _alpha_heading_level(code: str) -> int:
    # A.2 -> 2
    # A.2.1 -> 3
    # A.2.1.1 -> 4
    return len(code.split("."))


def _resolve_heading_level(heading_info: dict[str, Any], stack: list[HeadingHierarchyNode]) -> int:
    # Convert parsed heading metadata into an absolute stack level.
    #
    # Rules:
    # - alpha headings use their own code depth directly,
    # - numbered/table headings only become deeper when their code explicitly
    #   carries dotted sub-levels (e.g. 1.1, M011.1),
    # - otherwise they stay as siblings under the nearest structural section.
    node_type = heading_info["node_type"]
    code = heading_info["code"]

    if node_type == "section_heading":
        return _alpha_heading_level(code)
    if node_type in {"numbered_heading", "table_heading"}:
        base_level = _nearest_structural_level(stack)
        # 1 / 2 / 3 and M011 / M012 / M013 should stay at the same level.
        # Only explicit dotted extensions such as 1.1 or M011.1 create
        # additional depth under the same family.
        return base_level + 1 + code.count(".")

    return 1


def _nearest_structural_level(stack: list[HeadingHierarchyNode]) -> int:
    for heading in reversed(stack):
        if heading.node_type == "section_heading":
            return heading.level
    return 0


def _normalize_heading_title(title: str | None) -> str | None:
    if title is None:
        return None
    normalized = title.strip()
    return normalized or None


def _attach_content_to_active_heading(stack: list[HeadingHierarchyNode], item: ParserStreamItem) -> None:
    # Attach non-heading content to the currently active semantic heading. This
    # keeps the stream relationship without prematurely transforming content.
    active_heading = stack[-1]
    active_heading.content_refs.append(item.ref)
    _extend_heading_page_range(active_heading, item.page_start, item.page_end)


def _extend_heading_page_range(
    heading: HeadingHierarchyNode,
    page_start: int | None,
    page_end: int | None,
) -> None:
    if page_start is not None:
        heading.page_start = page_start if heading.page_start is None else min(heading.page_start, page_start)
    if page_end is not None:
        heading.page_end = page_end if heading.page_end is None else max(heading.page_end, page_end)
