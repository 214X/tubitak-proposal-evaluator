from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.evaluation.models import (
    CriterionEvaluationResult,
    EvaluationReport,
    EvidenceChunk,
)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_CHUNK_TYPE_LABELS = {
    "table": "Tablo",
    "list": "Liste",
    "qa": "Soru-Cevap",
    "narrative": "Anlatı",
}
_EVIDENCE_TYPE_LABELS = {
    "positive": "Destekleyici Kanıt",
    "negative": "Zayıflatan Kanıt",
    "context": "Bağlam",
}


def _build_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["score"] = _format_score
    env.filters["chunk_type_label"] = lambda value: _CHUNK_TYPE_LABELS.get(value, "Anlatı")
    env.filters["evidence_type_label"] = lambda value: _EVIDENCE_TYPE_LABELS.get(value, "Bağlam")
    env.filters["location"] = _format_location
    env.filters["finding_reason"] = _finding_reason
    return env


def render_report_pdf(report: EvaluationReport) -> bytes:
    """EvaluationReport'u UI'a benzer bir PDF'e çevirir (download + mail için tek kaynak)."""
    # Geç import: weasyprint native bağımlılıkları yükler; modül seviyesinde tutmak
    # diğer servislerin import süresini gereksiz uzatır.
    from weasyprint import HTML

    context = _build_context(report)
    template = _build_environment().get_template("report.html")
    html_string = template.render(**context)
    return HTML(string=html_string, base_url=str(_TEMPLATES_DIR)).write_pdf()


def _build_context(report: EvaluationReport) -> dict[str, Any]:
    results = report.subcriteria_results or report.criterion_results
    evidence_count = sum(len(item.evidence_items) for item in results)
    css_text = (_TEMPLATES_DIR / "report.css").read_text(encoding="utf-8")
    return {
        "report": report,
        "results": results,
        "evidence_count": evidence_count,
        "css_text": css_text,
        "reviewed_for": _reviewed_evidence_for,
    }


def _reviewed_evidence_for(
    criterion: CriterionEvaluationResult,
) -> list[dict[str, Any]]:
    cited_ids: set[str] = set()
    cited_ids.update(item.chunk_id for item in criterion.evidence_items)
    cited_ids.update(item.chunk_id for item in criterion.positive_findings)
    cited_ids.update(item.chunk_id for item in criterion.negative_findings)

    ordered: list[EvidenceChunk] = [
        *criterion.primary_section_chunks,
        *criterion.semantic_support_chunks,
        *criterion.fallback_context_chunks,
    ]
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for chunk in ordered:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        entries.append(
            {
                "chunk": chunk,
                "cited": chunk.chunk_id in cited_ids,
                "text": _clamp(" ".join(chunk.text_for_embedding.split()), 320),
            }
        )
    return entries


def _finding_reason(finding: Any) -> str | None:
    return getattr(finding, "why_positive", None) or getattr(finding, "why_negative", None)


def _format_score(value: float | None, scale: int = 100) -> str:
    if value is None:
        return "-"
    rendered = f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"
    return f"{rendered}/{scale}"


def _format_location(
    heading_path: list[str] | None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> str:
    heading = " > ".join(heading_path) if heading_path else "Belirsiz bölüm"
    if page_start is None and page_end is None:
        return f"{heading}"
    if page_start == page_end:
        return f"{heading} · s.{page_start}"
    return f"{heading} · s.{page_start}-{page_end}"


def _clamp(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 1].rstrip()}…"
