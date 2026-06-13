from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services.chunking.models import SectionContainer
from app.services.chunking.tables import extract_table_columns, extract_table_rows
from app.services.extraction.models import HeadingHierarchyNode, ParserStreamItem

WORK_PACKAGE_ROOT_TITLE = "İş Paketleri Listesi"
WORK_PACKAGE_NO_KEY = "is paketi sıra no"
WORK_PACKAGE_TITLE_KEY = "is paketi adı"
WORK_PACKAGE_DATE_KEY = "baslama-bitis tarihi ve suresi"
WORK_PACKAGE_ORG_KEY = "ilgili kuruluslar"
WORK_PACKAGE_CODE_PATTERN = re.compile(r"iş paketi kodu[:\s]*(\d+)", re.IGNORECASE)
WORK_PACKAGE_DATE_RANGE_PATTERN = re.compile(
    r"^(?P<date_range>\d{2}\.\d{2}\.\d{4}\s*-\s*\d{2}\.\d{2}\.\d{4})(?:\s+(?P<duration>.+))?$"
)
WORK_PACKAGE_SECTION_PATTERN = re.compile(r"^(?P<number>[1-4])\s*-\s*(?P<title>.+)$")


def build_section_containers(
    content_stream: list[ParserStreamItem],
    heading_hierarchy: list[HeadingHierarchyNode],
) -> list[SectionContainer]:
    flattened_nodes = _flatten_heading_tree(heading_hierarchy)
    node_index = _build_heading_node_index(flattened_nodes)
    item_order_by_ref = {item.ref: item.order for item in content_stream}
    item_by_order = {item.order: item for item in content_stream}

    sections: list[SectionContainer] = []

    for node in heading_hierarchy:
        sections.extend(
            _collect_sections_for_node(
                node=node,
                node_index=node_index,
                item_order_by_ref=item_order_by_ref,
                item_by_order=item_by_order,
            )
        )

    return sections


def _collect_sections_for_node(
    node: HeadingHierarchyNode,
    node_index: dict[str, HeadingHierarchyNode],
    item_order_by_ref: dict[str, int],
    item_by_order: dict[int, ParserStreamItem],
) -> list[SectionContainer]:
    if _is_work_package_root(node):
        return _build_work_package_sections(
            root=node,
            node_index=node_index,
            item_order_by_ref=item_order_by_ref,
            item_by_order=item_by_order,
        )

    if not node.children:
        return [_build_generic_section(node, node_index)]

    sections: list[SectionContainer] = []
    for child in node.children:
        sections.extend(
            _collect_sections_for_node(
                node=child,
                node_index=node_index,
                item_order_by_ref=item_order_by_ref,
                item_by_order=item_by_order,
            )
        )

    return sections


def _build_generic_section(
    node: HeadingHierarchyNode,
    node_index: dict[str, HeadingHierarchyNode],
) -> SectionContainer:
    return SectionContainer(
        id=node.id,
        heading_path_ids=list(node.path),
        heading_path_titles=_resolve_heading_path_titles(node, node_index),
        leaf_heading=_resolve_leaf_heading(node),
        page_start=node.page_start,
        page_end=node.page_end,
        content_refs=_collect_section_content_refs(node),
    )


def _build_work_package_sections(
    root: HeadingHierarchyNode,
    node_index: dict[str, HeadingHierarchyNode],
    item_order_by_ref: dict[str, int],
    item_by_order: dict[int, ParserStreamItem],
) -> list[SectionContainer]:
    root_path_ids = list(root.path)
    root_path_titles = _resolve_heading_path_titles(root, node_index)
    subtree_end_order = _compute_subtree_end_order(root, item_order_by_ref)
    stream_items = _collect_items_between_orders(item_by_order, root.stream_order + 1, subtree_end_order + 1)
    fallback_index = 1
    sections: list[SectionContainer] = []

    current_work_package: dict[str, Any] | None = None
    current_section: dict[str, Any] | None = None

    def flush_current_section() -> None:
        nonlocal current_section
        if current_section is None:
            return

        content_refs = [item.ref for item in current_section["items"]]
        if not content_refs:
            current_section = None
            return

        work_package = current_section["work_package"]
        sections.append(
            SectionContainer(
                id=f"{root.id}::{work_package['id']}::section_{current_section['number']}",
                heading_path_ids=[*root_path_ids, work_package["id"], current_section["number"]],
                heading_path_titles=[
                    *root_path_titles,
                    _render_work_package_heading(work_package),
                    current_section["title"],
                ],
                leaf_heading=current_section["title"],
                page_start=current_section["page_start"],
                page_end=current_section["page_end"],
                content_refs=content_refs,
                work_package_id=work_package["id"],
                work_package_no=work_package.get("no"),
                work_package_code=work_package.get("code"),
                work_package_title=work_package.get("title"),
                work_package_date_range=work_package.get("date_range"),
                work_package_duration_text=work_package.get("duration_text"),
                work_package_organizations=list(work_package.get("organizations", [])),
                work_package_section_no=current_section["number"],
            )
        )
        current_section = None

    def ensure_work_package() -> dict[str, Any]:
        nonlocal current_work_package, fallback_index
        if current_work_package is None:
            current_work_package = _build_fallback_work_package(fallback_index)
            fallback_index += 1
        return current_work_package

    def open_summary_section(work_package: dict[str, Any], item: ParserStreamItem) -> None:
        nonlocal current_section
        flush_current_section()
        current_section = {
            "number": "meta",
            "title": "İş Paketi Özeti",
            "items": [item],
            "page_start": item.page_start or work_package.get("page_start"),
            "page_end": item.page_end or work_package.get("page_end"),
            "work_package": work_package,
        }

    for item in stream_items:
        work_package_header = _extract_work_package_header_from_item(item)
        if work_package_header is not None:
            flush_current_section()
            current_work_package = work_package_header
            open_summary_section(work_package_header, item)
            continue

        section_heading = _extract_work_package_section_heading(item)
        if section_heading is not None:
            flush_current_section()
            work_package = ensure_work_package()
            current_section = {
                "number": section_heading["number"],
                "title": section_heading["title"],
                "items": [],
                "page_start": item.page_start or work_package.get("page_start"),
                "page_end": item.page_end or work_package.get("page_end"),
                "work_package": work_package,
            }
            continue

        if current_section is None:
            work_package = ensure_work_package()
            open_summary_section(work_package, item)
            continue

        current_section["items"].append(item)
        current_section["page_start"] = _min_defined(current_section["page_start"], item.page_start)
        current_section["page_end"] = _max_defined(current_section["page_end"], item.page_end)

    flush_current_section()
    return sections


def _extract_work_package_section_heading(
    item: ParserStreamItem,
) -> dict[str, str] | None:
    if item.item_type != "text" or not isinstance(item.content, str):
        return None

    normalized = " ".join(item.content.split()).strip()
    if not normalized:
        return None

    match = WORK_PACKAGE_SECTION_PATTERN.match(normalized)
    if not match:
        return None

    return {
        "number": match.group("number"),
        "title": match.group("title").strip(),
    }


def _extract_work_package_header_from_item(item: ParserStreamItem) -> dict[str, Any] | None:
    if item.item_type != "table":
        return None

    rows = [extract_table_columns(item.content), *extract_table_rows(item.content)]
    normalized_rows = [
        [cell.strip() for cell in row if isinstance(cell, str) and cell.strip()]
        for row in rows
    ]
    normalized_rows = [row for row in normalized_rows if row]

    if not _looks_like_work_package_header_rows(normalized_rows):
        return None

    key_values: dict[str, str] = {}
    for row in normalized_rows:
        if len(row) < 2:
            continue
        key_values[_normalize_text(row[0])] = row[1]

    no_value = key_values.get(WORK_PACKAGE_NO_KEY)
    title_value = key_values.get(WORK_PACKAGE_TITLE_KEY)
    if not no_value or not title_value:
        return None

    work_package_no = no_value
    work_package_code = None
    code_match = WORK_PACKAGE_CODE_PATTERN.search(no_value)
    if code_match:
        work_package_code = code_match.group(1)
        work_package_no = no_value[: code_match.start()].strip().strip("()")

    work_package_no = work_package_no.strip()
    if work_package_no.endswith("("):
        work_package_no = work_package_no[:-1].strip()

    date_range = None
    duration_text = None
    date_value = key_values.get(WORK_PACKAGE_DATE_KEY)
    if date_value:
        date_match = WORK_PACKAGE_DATE_RANGE_PATTERN.match(date_value)
        if date_match:
            date_range = date_match.group("date_range")
            duration_text = (date_match.group("duration") or "").strip() or None
        else:
            date_range = date_value

    organizations = [
        part.strip()
        for part in re.split(r"[,\n;]+", key_values.get(WORK_PACKAGE_ORG_KEY, ""))
        if part.strip()
    ]

    return {
        "id": f"wp_{_normalize_identifier_token(work_package_no or work_package_code or title_value)}",
        "no": work_package_no or None,
        "code": work_package_code,
        "title": title_value.strip() or None,
        "date_range": date_range,
        "duration_text": duration_text,
        "organizations": organizations,
        "page_start": item.page_start,
        "page_end": item.page_end,
    }


def _looks_like_work_package_header_rows(rows: list[list[str]]) -> bool:
    if len(rows) < 4:
        return False

    keys = {_normalize_text(row[0]) for row in rows if row}
    required = {
        WORK_PACKAGE_NO_KEY,
        WORK_PACKAGE_TITLE_KEY,
        WORK_PACKAGE_DATE_KEY,
        WORK_PACKAGE_ORG_KEY,
    }
    return required.issubset(keys)


def _build_fallback_work_package(index: int) -> dict[str, Any]:
    return {
        "id": f"wp_fallback_{index}",
        "no": str(index),
        "code": None,
        "title": f"İş Paketi {index}",
        "date_range": None,
        "duration_text": None,
        "organizations": [],
        "page_start": None,
        "page_end": None,
    }


def _render_work_package_heading(work_package: dict[str, Any]) -> str:
    no_value = work_package.get("no")
    title_value = work_package.get("title")
    if no_value and title_value:
        return f"İş Paketi {no_value} - {title_value}"
    if title_value:
        return title_value
    if no_value:
        return f"İş Paketi {no_value}"
    return "İş Paketi"


def _collect_items_between_orders(
    item_by_order: dict[int, ParserStreamItem],
    start_order: int,
    end_order_exclusive: int,
) -> list[ParserStreamItem]:
    return [
        item_by_order[order]
        for order in range(start_order, end_order_exclusive)
        if order in item_by_order
    ]


def _compute_subtree_end_order(
    node: HeadingHierarchyNode,
    item_order_by_ref: dict[str, int],
) -> int:
    max_order = node.stream_order

    for ref in node.content_refs:
        max_order = max(max_order, item_order_by_ref.get(ref, max_order))

    for child in node.children:
        max_order = max(max_order, _compute_subtree_end_order(child, item_order_by_ref))

    return max_order


def _flatten_heading_tree(nodes: list[HeadingHierarchyNode]) -> list[HeadingHierarchyNode]:
    flattened: list[HeadingHierarchyNode] = []

    for node in nodes:
        flattened.append(node)
        flattened.extend(_flatten_heading_tree(node.children))

    return flattened


def _build_heading_node_index(
    nodes: list[HeadingHierarchyNode],
) -> dict[str, HeadingHierarchyNode]:
    return {node.id: node for node in nodes}


def _resolve_heading_path_titles(
    node: HeadingHierarchyNode,
    node_index: dict[str, HeadingHierarchyNode],
) -> list[str]:
    titles: list[str] = []
    current_node: HeadingHierarchyNode | None = node

    while current_node is not None:
        titles.append(_resolve_leaf_heading(current_node))
        if not current_node.parent_id:
            current_node = None
            continue
        current_node = node_index.get(current_node.parent_id)

    titles.reverse()
    return titles


def _resolve_leaf_heading(node: HeadingHierarchyNode) -> str:
    if node.title:
        return node.title
    return node.full_text


def _collect_section_content_refs(node: HeadingHierarchyNode) -> list[str]:
    seen_refs: set[str] = set()
    ordered_refs: list[str] = []

    for ref in node.content_refs:
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        ordered_refs.append(ref)

    return ordered_refs


def _is_work_package_root(node: HeadingHierarchyNode) -> bool:
    return _normalize_text(node.title or node.full_text) == _normalize_text(WORK_PACKAGE_ROOT_TITLE)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(without_marks.split()).strip()


def _normalize_identifier_token(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip())
    normalized = normalized.strip("_")
    return normalized or "unknown"


def _min_defined(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _max_defined(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)
