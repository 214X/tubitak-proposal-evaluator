from __future__ import annotations

from app.services.chunking.models import SectionContainer
from app.services.extraction.models import HeadingHierarchyNode, ParserStreamItem


def build_section_containers(
    content_stream: list[ParserStreamItem],
    heading_hierarchy: list[HeadingHierarchyNode],
) -> list[SectionContainer]:
    # Section containers are built from leaf headings because they represent
    # the smallest stable document regions that can own chunk candidates.
    #
    # The content stream is accepted as an explicit input even though the
    # current section model is driven by heading content_refs. This keeps the
    # public API aligned with the parser outputs and gives us a natural place
    # to tighten validation later if needed.
    _ = content_stream

    flattened_nodes = _flatten_heading_tree(heading_hierarchy)
    leaf_nodes = _collect_leaf_nodes(flattened_nodes)
    node_index = _build_heading_node_index(flattened_nodes)

    section_containers: list[SectionContainer] = []

    for leaf_node in leaf_nodes:
        heading_path_titles = _resolve_heading_path_titles(leaf_node, node_index)
        section_containers.append(
            SectionContainer(
                id=leaf_node.id,
                heading_path_ids=list(leaf_node.path),
                heading_path_titles=heading_path_titles,
                leaf_heading=_resolve_leaf_heading(leaf_node),
                page_start=leaf_node.page_start,
                page_end=leaf_node.page_end,
                content_refs=_collect_section_content_refs(leaf_node),
            )
        )

    return section_containers


def _flatten_heading_tree(nodes: list[HeadingHierarchyNode]) -> list[HeadingHierarchyNode]:
    # Keep a deterministic preorder traversal so later stages see sections in
    # the same order as the original parsed document.
    flattened: list[HeadingHierarchyNode] = []

    for node in nodes:
        flattened.append(node)
        flattened.extend(_flatten_heading_tree(node.children))

    return flattened


def _collect_leaf_nodes(nodes: list[HeadingHierarchyNode]) -> list[HeadingHierarchyNode]:
    # Only leaf headings become section containers in V1. Non-leaf nodes keep
    # organizing context but do not directly own final chunks.
    return [node for node in nodes if not node.children]


def _build_heading_node_index(
    nodes: list[HeadingHierarchyNode],
) -> dict[str, HeadingHierarchyNode]:
    # Heading codes are not globally unique in the document, especially for
    # repeated numbered subsections such as 1, 2, 3 under different parents.
    # We therefore index real nodes by unique parser ids and resolve path
    # titles through ancestry, not through a global code->title dictionary.
    return {node.id: node for node in nodes}

def _resolve_heading_path_titles(
    node: HeadingHierarchyNode,
    node_index: dict[str, HeadingHierarchyNode],
) -> list[str]:
    # Resolve path titles from the node's real parent chain. This avoids title
    # corruption when the same heading code appears in multiple unrelated
    # branches of the document tree.
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
    # Leaf sections own the parser refs attached directly under that heading.
    # We preserve source order and remove accidental duplicates defensively.
    seen_refs: set[str] = set()
    ordered_refs: list[str] = []

    for ref in node.content_refs:
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        ordered_refs.append(ref)

    return ordered_refs
