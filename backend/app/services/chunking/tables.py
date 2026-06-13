from __future__ import annotations

from typing import Any


def extract_table_title(payload: Any) -> str | None:
    if _is_gantt_chart_payload(payload):
        title = payload.get("title")
        return title if isinstance(title, str) else "İş Zaman Çubuk Grafiği"

    # Some tables start with a merged caption row before the real header row.
    # We treat that first row as a table title only when the shape strongly
    # suggests a single logical label followed by a separate multi-column header.
    normalized_grid = _extract_normalized_grid(payload)
    if not normalized_grid:
        return None

    if _has_leading_title_row(normalized_grid):
        first_row_values = [value for value in normalized_grid[0] if value]
        return first_row_values[0] if first_row_values else None

    return None


def extract_table_columns(payload: Any) -> list[str]:
    if _is_gantt_chart_payload(payload):
        return [
            "İş Paketi",
            "Görev",
            "Başlangıç Haftası",
            "Bitiş Haftası",
            "Ay Aralığı",
        ]

    # Prefer the first detected grid row as headers. When only row dictionaries
    # are available, use their keys as column names in source order.
    normalized_grid = _extract_normalized_grid(payload)
    if normalized_grid:
        if _has_leading_title_row(normalized_grid):
            return normalized_grid[1] if len(normalized_grid) > 1 else []
        return normalized_grid[0]

    rows = _extract_row_dicts(payload)
    if rows:
        return [str(key) for key in rows[0].keys()]

    return []


def extract_table_rows(payload: Any) -> list[list[str]]:
    if _is_gantt_chart_payload(payload):
        rows: list[list[str]] = []
        for work_package in payload.get("work_packages", []):
            if not isinstance(work_package, dict):
                continue
            work_package_label = normalize_table_cell(work_package.get("label"))
            tasks = work_package.get("tasks")
            if not isinstance(tasks, list):
                continue
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                rows.append(
                    [
                        work_package_label,
                        normalize_table_cell(task.get("label")),
                        normalize_table_cell(task.get("start_week")),
                        normalize_table_cell(task.get("end_week")),
                        normalize_table_cell(task.get("months")),
                    ]
                )
        return rows

    # Table row extraction mirrors column extraction so both paths stay
    # structurally aligned even when Docling emits slightly different payload
    # shapes across documents.
    normalized_grid = _extract_normalized_grid(payload)
    if normalized_grid:
        if _has_leading_title_row(normalized_grid):
            return normalized_grid[2:] if len(normalized_grid) > 2 else []
        if len(normalized_grid) == 1:
            return normalized_grid
        return normalized_grid[1:]

    rows = _extract_row_dicts(payload)
    if rows:
        columns = [str(key) for key in rows[0].keys()]
        return [
            [normalize_table_cell(row.get(column)) for column in columns]
            for row in rows
        ]

    return []


def normalize_table_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split()).strip()
    if isinstance(value, dict):
        text_value = value.get("text")
        if isinstance(text_value, str):
            return " ".join(text_value.split()).strip()
        for key in ("label", "value", "content"):
            fallback_value = value.get(key)
            if isinstance(fallback_value, str):
                return " ".join(fallback_value.split()).strip()
        return ""
    return str(value)


def _extract_normalized_grid(payload: Any) -> list[list[str]]:
    table_grid = _find_first_list_of_lists(payload)
    if not table_grid:
        return []

    normalized_grid = [
        [normalize_table_cell(cell) for cell in row]
        for row in table_grid
        if isinstance(row, list)
    ]
    return [row for row in normalized_grid if any(row)]


def _has_leading_title_row(normalized_grid: list[list[str]]) -> bool:
    # Generic rule:
    # - first row has exactly one non-empty cell
    # - second row exists and has multiple populated cells
    # This matches merged caption rows while leaving ordinary headers alone.
    if len(normalized_grid) < 2:
        return False

    first_row_non_empty = [value for value in normalized_grid[0] if value]
    second_row_non_empty = [value for value in normalized_grid[1] if value]

    if len(first_row_non_empty) != 1:
        return False
    if len(second_row_non_empty) < 2:
        return False

    return True


def _find_first_list_of_lists(payload: Any) -> list[list[Any]] | None:
    if isinstance(payload, list) and payload and all(isinstance(entry, list) for entry in payload):
        return payload

    if isinstance(payload, dict):
        for value in payload.values():
            found = _find_first_list_of_lists(value)
            if found is not None:
                return found

    if isinstance(payload, list):
        for value in payload:
            found = _find_first_list_of_lists(value)
            if found is not None:
                return found

    return None


def _extract_row_dicts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list) and payload and all(isinstance(entry, dict) for entry in payload):
        return [entry for entry in payload if isinstance(entry, dict)]

    if isinstance(payload, dict):
        for value in payload.values():
            rows = _extract_row_dicts(value)
            if rows:
                return rows

    if isinstance(payload, list):
        for value in payload:
            rows = _extract_row_dicts(value)
            if rows:
                return rows

    return []


def _is_gantt_chart_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("type") == "gantt_chart"
