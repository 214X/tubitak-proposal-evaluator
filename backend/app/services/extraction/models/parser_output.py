from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

ParserStreamItemType = Literal["text", "table", "picture", "group", "key_value", "form_item", "unknown"]
HeadingNodeType = Literal["section_heading", "table_heading", "numbered_heading"]


class ParserStreamItem(BaseModel):
    ref: str                                  # canonical Docling reference such as #/texts/12
    order: int                                # stable reading order derived directly from body.children traversal
    item_type: ParserStreamItemType           # normalized top-level item type derived from the referenced collection
    label: str | None = None                  # Docling label such as section_header, text, list_item or table
    page_start: int | None = None             # first page where this item appears, when available
    page_end: int | None = None               # last page where this item appears, when available
    content: Any | None = None                # text content, table payload or other raw item content


class HeadingHierarchyNode(BaseModel):
    id: str                                   # stable parser-generated heading identifier
    ref: str                                  # source stream reference for the heading item
    node_type: HeadingNodeType                # semantic heading category inferred by the parser
    code: str                                 # parsed heading code such as A.2, A.2.1, M013 or 1.1
    title: str | None = None                  # human-readable title when the heading line contains one
    full_text: str                            # full heading text exactly as carried by the parser stream
    level: int                                # absolute hierarchy depth produced by parser stack logic
    parent_id: str | None = None              # parent heading identifier when this heading is nested
    page_start: int | None = None             # first page where this heading appears
    page_end: int | None = None               # last page currently covered by this heading subtree
    stream_order: int                         # original stream position for deterministic ordering
    path: list[str]                           # heading path from root to this node
    content_refs: list[str]                   # stream item refs attached directly under this heading
    children: list["HeadingHierarchyNode"]    # nested heading nodes inferred from heading order and codes


class ParserOutput(BaseModel):
    document: dict[str, Any]                  # lightweight document metadata copied from extraction output
    docling_output: dict[str, Any]            # raw Docling output kept for debugging and UI inspection
    content_stream: list[ParserStreamItem]    # ordered parser stream resolved from Docling body.children references
    heading_hierarchy: list[HeadingHierarchyNode]  # semantic heading tree inferred from the ordered parser stream
