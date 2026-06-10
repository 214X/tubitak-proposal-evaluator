from __future__ import annotations

from app.services.chunking.models import ListChunk, NarrativeChunk, QAChunk, TableChunk


def build_qa_embedding_text(chunk: QAChunk) -> str:
    # QA chunks should preserve the hierarchy context and clearly separate the
    # question from optional guidance and the selected answer.
    lines = [_render_heading_path(chunk.heading_path_titles)]
    lines.append(f"Soru: {chunk.question}")

    if chunk.guidance:
        lines.append(f"Açıklama: {chunk.guidance}")
    if chunk.answer:
        lines.append(f"Cevap: {chunk.answer}")

    return "\n".join(lines).strip()


def build_narrative_embedding_text(chunk: NarrativeChunk) -> str:
    # Narrative chunks mainly need hierarchy context plus the normalized body
    # text. Split metadata stays in the model, not in the embedding text.
    lines = [_render_heading_path(chunk.heading_path_titles), chunk.text]
    return "\n".join(line for line in lines if line).strip()


def build_table_embedding_text(chunk: TableChunk) -> str:
    # Tables are rendered into row-wise key-value text so embeddings capture
    # semantic relationships between columns without leaking layout metadata.
    lines = [_render_heading_path(chunk.heading_path_titles)]

    if chunk.table_title:
        lines.append(f"Tablo: {chunk.table_title}")

    for block in _build_table_blocks(chunk.table_columns, chunk.table_rows):
        if block["kind"] == "matrix":
            if block.get("title"):
                lines.append(block["title"])
            headers = block["headers"]
            for row in block["rows"]:
                rendered_row = _render_table_row(headers, row)
                if rendered_row:
                    lines.append(rendered_row)
            continue

        if block.get("title"):
            lines.append(block["title"])
        for row in block["rows"]:
            rendered_row = _render_form_table_row(row)
            if rendered_row:
                lines.append(rendered_row)

    return "\n".join(line for line in lines if line).strip()


def build_list_embedding_text(chunk: ListChunk) -> str:
    # Lists should stay easy to read for retrieval, so we keep the hierarchy
    # prefix and render each item as its own bullet-style line.
    lines = [_render_heading_path(chunk.heading_path_titles)]
    lines.extend(f"- {item}" for item in chunk.items if item)
    return "\n".join(line for line in lines if line).strip()


def _render_heading_path(heading_path_titles: list[str]) -> str:
    return " > ".join(title for title in heading_path_titles if title).strip()


def _render_table_row(columns: list[str], row: list[str]) -> str:
    if not row:
        return ""

    if columns and len(columns) == len(row):
        return " | ".join(
            f"{column}: {value}".strip()
            for column, value in zip(columns, row, strict=False)
            if column or value
        )

    return " | ".join(value for value in row if value)


def _looks_like_form_table(columns: list[str], rows: list[list[str]]) -> bool:
    compressed_columns = _compress_table_row(columns)
    compressed_rows = [
        _compress_table_row(row)
        for row in rows
        if any(cell for cell in row)
    ]

    if not compressed_columns or not compressed_rows:
        return False

    if len(compressed_columns) not in {2, 4}:
        return False

    even_row_count = sum(1 for row in compressed_rows if len(row) in {2, 4})
    if even_row_count < max(1, len(compressed_rows) // 2):
        return False

    if len(set(compressed_columns)) < len(compressed_columns):
        return True

    # Two-column tables whose first row already looks like a field/value pair
    # are better embedded as form data than as a generic matrix.
    return len(compressed_columns) == 2


def _build_table_blocks(columns: list[str], rows: list[list[str]]):
    compressed_columns = _compress_table_row(columns)
    compressed_rows = [
        _compress_table_row(row)
        for row in rows
        if any(cell.strip() for cell in row)
    ]

    if not compressed_columns:
        return []

    blocks: list[dict[str, object]] = []

    if _looks_like_form_table(columns, rows):
        current_form_rows: list[list[str]] = [compressed_columns]
        index = 0

        while index < len(compressed_rows):
            row = compressed_rows[index]

            if _is_section_break_row(row):
                if current_form_rows:
                    blocks.append({
                        "kind": "form",
                        "title": None,
                        "rows": current_form_rows,
                    })
                    current_form_rows = []

                section_title = row[0]
                header_row = compressed_rows[index + 1] if index + 1 < len(compressed_rows) else []
                data_rows: list[list[str]] = []
                lookahead = index + 2

                while lookahead < len(compressed_rows):
                    candidate = compressed_rows[lookahead]
                    if _is_section_break_row(candidate):
                        break
                    if header_row and len(candidate) == len(header_row):
                        data_rows.append(candidate)
                        lookahead += 1
                        continue
                    break

                if header_row and data_rows and _looks_like_matrix_header(header_row, data_rows[0]):
                    blocks.append({
                        "kind": "matrix",
                        "title": section_title,
                        "headers": header_row,
                        "rows": data_rows,
                    })
                    index = lookahead
                    continue

                blocks.append({
                    "kind": "form",
                    "title": section_title,
                    "rows": [header_row] if header_row else [],
                })
                index += 2
                continue

            current_form_rows.append(row)
            index += 1

        if current_form_rows:
            blocks.append({
                "kind": "form",
                "title": None,
                "rows": current_form_rows,
            })

        return blocks

    return [{
        "kind": "matrix",
        "title": None,
        "headers": compressed_columns,
        "rows": compressed_rows,
    }]


def _is_section_break_row(row: list[str]) -> bool:
    return len(row) == 1


def _looks_like_matrix_header(header_row: list[str], first_data_row: list[str]) -> bool:
    if len(header_row) < 2 or len(header_row) != len(first_data_row):
        return False
    if not any(_looks_like_numericish(cell) for cell in first_data_row[1:]):
        return False
    return True


def _looks_like_numericish(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    allowed = set("0123456789.,/%- ")
    return all(char in allowed for char in stripped)


def _render_form_table_row(row: list[str]) -> str:
    compressed_row = _compress_table_row(row)
    if not compressed_row:
        return ""

    if len(compressed_row) == 1:
        return compressed_row[0]

    if len(compressed_row) % 2 == 0:
        parts: list[str] = []
        for index in range(0, len(compressed_row), 2):
            label = compressed_row[index]
            value = compressed_row[index + 1]
            if not label and not value:
                continue
            parts.append(f"{label}: {value}".strip())
        return " | ".join(parts)

    return " | ".join(value for value in compressed_row if value)


def _compress_table_row(row: list[str]) -> list[str]:
    compressed: list[str] = []

    for value in row:
        normalized = value.strip()
        if not normalized:
            continue
        if compressed and compressed[-1] == normalized:
            continue
        compressed.append(normalized)

    return compressed
