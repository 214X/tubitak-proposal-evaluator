from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, model_validator

from app.services.chunking.models import ChunkType

EvaluationStatus = Literal[
    "idle",
    "queued",
    "retrieving",
    "evaluating",
    "aggregating",
    "completed",
    "failed",
]
EvaluationStep = Literal["none", "retriever", "judge", "aggregator", "done"]
CriterionDecisionStatus = Literal[
    "scored",
    "insufficient_evidence",
    "conflicting_evidence",
    "failed",
]
CriterionDecisionRule = Literal["support_vs_contradiction"]
EvidenceCoverageStatus = Literal["complete", "covered", "partial", "missing", "unknown"]
EvidenceItemType = Literal["positive", "negative", "context"]


class EvaluationMainDimension(BaseModel):
    dimension_id: str
    title: str
    description: str
    weight: int = Field(ge=1, le=100)
    ui_label: str
    ui_explanation: str


MainDimension = EvaluationMainDimension


class EvaluationCriterion(BaseModel):
    criterion_id: str
    main_dimension_id: str
    title: str
    description: str
    question: str
    weight: int = Field(ge=1)
    score_min: int = Field(default=0, ge=0, le=5)
    score_max: int = Field(default=5, ge=0, le=5)
    source_sections: list[str] = Field(default_factory=list, min_length=1)
    required_sections: list[str] = Field(default_factory=list, min_length=1)
    fallback_sections: list[str] = Field(default_factory=list)
    semantic_queries: list[str] = Field(default_factory=list, min_length=1)
    ui_label: str
    ui_explanation: str
    allowed_chunk_types: list[ChunkType] = Field(
        default_factory=lambda: ["qa", "narrative", "table", "list"]
    )
    evidence_top_k: int = Field(default=5, ge=1, le=10)
    minimum_evidence_count: int = Field(default=1, ge=0, le=10)
    decision_rule: CriterionDecisionRule = "support_vs_contradiction"
    category: str | None = None
    allowed_scores: list[int] = Field(default_factory=list)
    positive_queries: list[str] = Field(default_factory=list)
    negative_queries: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def apply_compatibility_defaults(self) -> "EvaluationCriterion":
        if not self.category:
            self.category = self.main_dimension_id
        if not self.allowed_scores:
            self.allowed_scores = list(range(self.score_min, self.score_max + 1))
        if not self.positive_queries:
            self.positive_queries = list(self.semantic_queries)
        return self


SubCriterion = EvaluationCriterion


class EvaluationRubric(BaseModel):
    rubric_id: str
    version: str
    program_codes: list[str] = Field(default_factory=list)
    main_dimensions: list[EvaluationMainDimension] = Field(default_factory=list)
    subcriteria: list[EvaluationCriterion] = Field(default_factory=list)

    @property
    def criteria(self) -> list[EvaluationCriterion]:
        # Keep the legacy accessor available until retrieval/service layers are
        # migrated to the new main_dimensions/subcriteria contract.
        return self.subcriteria


class EvidenceChunk(BaseModel):
    chunk_id: str
    chunk_type: ChunkType
    heading_path_ids: list[str] = Field(default_factory=list)
    heading_path_titles: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    text_for_embedding: str
    similarity_score: float = Field(ge=0.0)


class EvidenceItem(BaseModel):
    chunk_id: str
    evidence_type: EvidenceItemType
    verbatim_excerpt: str
    heading_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    why_it_matters: str


class CriterionFinding(BaseModel):
    summary: str
    why_positive: str | None = None
    why_negative: str | None = None
    chunk_id: str

    @model_validator(mode="after")
    def validate_reason_direction(self) -> "CriterionFinding":
        if not self.why_positive and not self.why_negative:
            raise ValueError("A finding must explain either a positive or negative direction.")
        return self


class EvidenceNarrative(BaseModel):
    chunk_id: str
    location_summary: str
    evidence_text: str
    why_it_matters: str


class CriterionEvidence(BaseModel):
    criterion_id: str
    main_dimension_id: str | None = None
    primary_section_chunks: list[EvidenceChunk] = Field(default_factory=list)
    semantic_support_chunks: list[EvidenceChunk] = Field(default_factory=list)
    fallback_context_chunks: list[EvidenceChunk] = Field(default_factory=list)
    coverage_status: EvidenceCoverageStatus = "unknown"
    coverage_notes: list[str] = Field(default_factory=list)
    supporting_evidence: list[EvidenceChunk] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceChunk] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_evidence_payload(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        primary = normalized.get("primary_section_chunks") or []
        semantic = normalized.get("semantic_support_chunks")
        fallback = normalized.get("fallback_context_chunks")
        supporting = normalized.get("supporting_evidence") or []
        contradicting = normalized.get("contradicting_evidence") or []

        if semantic is None:
            normalized["semantic_support_chunks"] = supporting
        if fallback is None:
            normalized["fallback_context_chunks"] = contradicting
        if "primary_section_chunks" not in normalized:
            normalized["primary_section_chunks"] = primary
        if "coverage_status" not in normalized:
            total = len(primary) + len(normalized["semantic_support_chunks"]) + len(normalized["fallback_context_chunks"])
            normalized["coverage_status"] = "covered" if total else "missing"
        if "coverage_notes" not in normalized:
            normalized["coverage_notes"] = []
        return normalized

    @model_validator(mode="after")
    def apply_legacy_evidence_views(self) -> "CriterionEvidence":
        if not self.supporting_evidence:
            self.supporting_evidence = list(self.semantic_support_chunks)
        if not self.contradicting_evidence:
            self.contradicting_evidence = list(self.fallback_context_chunks)
        return self


class CriterionJudgeResponse(BaseModel):
    criterion_id: str = ""
    main_dimension_id: str | None = None
    title: str = ""
    score: float | None = Field(default=None, ge=0.0, le=5.0)
    claim_strength: float | None = Field(default=None, ge=0.0, le=5.0)
    evidence_quality: float | None = Field(default=None, ge=0.0, le=5.0)
    confidence: float = Field(ge=0.0, le=1.0)
    decision_status: CriterionDecisionStatus
    criterion_explanation: str = ""
    short_assessment: str = ""
    justification: str = ""
    positive_findings: list[CriterionFinding] = Field(default_factory=list)
    negative_findings: list[CriterionFinding] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    contradicting_chunk_ids: list[str] = Field(default_factory=list)
    supporting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)
    contradicting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_judge_payload(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        justification = str(normalized.get("justification") or "").strip()
        normalized.setdefault("criterion_explanation", justification)
        normalized.setdefault("short_assessment", justification)

        if "positive_findings" not in normalized:
            normalized["positive_findings"] = [
                {
                    "summary": _payload_get(item, "evidence_text") or _payload_get(item, "why_it_matters") or "",
                    "why_positive": _payload_get(item, "why_it_matters") or "",
                    "chunk_id": _payload_get(item, "chunk_id", ""),
                }
                for item in normalized.get("supporting_evidence_notes", [])
            ]
        if "negative_findings" not in normalized:
            normalized["negative_findings"] = [
                {
                    "summary": _payload_get(item, "evidence_text") or _payload_get(item, "why_it_matters") or "",
                    "why_negative": _payload_get(item, "why_it_matters") or "",
                    "chunk_id": _payload_get(item, "chunk_id", ""),
                }
                for item in normalized.get("contradicting_evidence_notes", [])
            ]
        if "evidence_items" not in normalized:
            evidence_items: list[dict[str, Any]] = []
            for item in normalized.get("supporting_evidence_notes", []):
                evidence_items.append(
                    {
                        "chunk_id": _payload_get(item, "chunk_id", ""),
                        "evidence_type": "positive",
                        "verbatim_excerpt": _payload_get(item, "evidence_text") or "",
                        "heading_path": [],
                        "page_start": None,
                        "page_end": None,
                        "why_it_matters": _payload_get(item, "why_it_matters") or "",
                    }
                )
            for item in normalized.get("contradicting_evidence_notes", []):
                evidence_items.append(
                    {
                        "chunk_id": _payload_get(item, "chunk_id", ""),
                        "evidence_type": "negative",
                        "verbatim_excerpt": _payload_get(item, "evidence_text") or "",
                        "heading_path": [],
                        "page_start": None,
                        "page_end": None,
                        "why_it_matters": _payload_get(item, "why_it_matters") or "",
                    }
                )
            normalized["evidence_items"] = evidence_items
        return normalized

    @model_validator(mode="after")
    def apply_legacy_judge_views(self) -> "CriterionJudgeResponse":
        if not self.justification:
            self.justification = self.short_assessment or self.criterion_explanation
        if not self.supporting_chunk_ids:
            self.supporting_chunk_ids = [
                item.chunk_id for item in self.evidence_items if item.evidence_type == "positive"
            ]
        if not self.contradicting_chunk_ids:
            self.contradicting_chunk_ids = [
                item.chunk_id for item in self.evidence_items if item.evidence_type == "negative"
            ]
        if not self.supporting_evidence_notes:
            self.supporting_evidence_notes = [
                EvidenceNarrative(
                    chunk_id=item.chunk_id,
                    location_summary=_format_heading_location(item.heading_path, item.page_start, item.page_end),
                    evidence_text=item.verbatim_excerpt,
                    why_it_matters=item.why_it_matters,
                )
                for item in self.evidence_items
                if item.evidence_type == "positive"
            ]
        if not self.contradicting_evidence_notes:
            self.contradicting_evidence_notes = [
                EvidenceNarrative(
                    chunk_id=item.chunk_id,
                    location_summary=_format_heading_location(item.heading_path, item.page_start, item.page_end),
                    evidence_text=item.verbatim_excerpt,
                    why_it_matters=item.why_it_matters,
                )
                for item in self.evidence_items
                if item.evidence_type == "negative"
            ]
        return self


class CriterionEvaluationResult(BaseModel):
    criterion_id: str
    main_dimension_id: str | None = None
    category: str | None = None
    title: str
    score: float | None = Field(default=None, ge=0.0, le=5.0)
    claim_strength: float | None = Field(default=None, ge=0.0, le=5.0)
    evidence_quality: float | None = Field(default=None, ge=0.0, le=5.0)
    weight: int = Field(ge=1)
    weighted_score: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    decision_status: CriterionDecisionStatus
    criterion_explanation: str = ""
    short_assessment: str = ""
    justification: str = ""
    positive_findings: list[CriterionFinding] = Field(default_factory=list)
    negative_findings: list[CriterionFinding] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    primary_section_chunks: list[EvidenceChunk] = Field(default_factory=list)
    semantic_support_chunks: list[EvidenceChunk] = Field(default_factory=list)
    fallback_context_chunks: list[EvidenceChunk] = Field(default_factory=list)
    coverage_status: EvidenceCoverageStatus = "unknown"
    coverage_notes: list[str] = Field(default_factory=list)
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    contradicting_chunk_ids: list[str] = Field(default_factory=list)
    supporting_evidence: list[EvidenceChunk] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceChunk] = Field(default_factory=list)
    supporting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)
    contradicting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_result_payload(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        normalized.setdefault("main_dimension_id", normalized.get("category"))

        justification = str(normalized.get("justification") or "").strip()
        normalized.setdefault("criterion_explanation", justification)
        normalized.setdefault("short_assessment", justification)

        if "positive_findings" not in normalized:
            normalized["positive_findings"] = [
                {
                    "summary": _payload_get(item, "evidence_text") or _payload_get(item, "why_it_matters") or "",
                    "why_positive": _payload_get(item, "why_it_matters") or "",
                    "chunk_id": _payload_get(item, "chunk_id", ""),
                }
                for item in normalized.get("supporting_evidence_notes", [])
            ]
        if "negative_findings" not in normalized:
            normalized["negative_findings"] = [
                {
                    "summary": _payload_get(item, "evidence_text") or _payload_get(item, "why_it_matters") or "",
                    "why_negative": _payload_get(item, "why_it_matters") or "",
                    "chunk_id": _payload_get(item, "chunk_id", ""),
                }
                for item in normalized.get("contradicting_evidence_notes", [])
            ]

        if "semantic_support_chunks" not in normalized:
            normalized["semantic_support_chunks"] = normalized.get("supporting_evidence", [])
        if "fallback_context_chunks" not in normalized:
            normalized["fallback_context_chunks"] = normalized.get("contradicting_evidence", [])
        normalized.setdefault("primary_section_chunks", [])

        if "coverage_status" not in normalized:
            total = (
                len(normalized.get("primary_section_chunks", []))
                + len(normalized.get("semantic_support_chunks", []))
                + len(normalized.get("fallback_context_chunks", []))
            )
            normalized["coverage_status"] = "covered" if total else "missing"
        normalized.setdefault("coverage_notes", [])

        if "evidence_items" not in normalized:
            evidence_items: list[dict[str, Any]] = []
            for item in normalized.get("supporting_evidence_notes", []):
                evidence_items.append(
                    {
                        "chunk_id": _payload_get(item, "chunk_id", ""),
                        "evidence_type": "positive",
                        "verbatim_excerpt": _payload_get(item, "evidence_text") or "",
                        "heading_path": [],
                        "page_start": None,
                        "page_end": None,
                        "why_it_matters": _payload_get(item, "why_it_matters") or "",
                    }
                )
            for item in normalized.get("contradicting_evidence_notes", []):
                evidence_items.append(
                    {
                        "chunk_id": _payload_get(item, "chunk_id", ""),
                        "evidence_type": "negative",
                        "verbatim_excerpt": _payload_get(item, "evidence_text") or "",
                        "heading_path": [],
                        "page_start": None,
                        "page_end": None,
                        "why_it_matters": _payload_get(item, "why_it_matters") or "",
                    }
                )
            normalized["evidence_items"] = evidence_items
        return normalized

    @model_validator(mode="after")
    def apply_legacy_result_views(self) -> "CriterionEvaluationResult":
        if not self.category:
            self.category = self.main_dimension_id
        if not self.justification:
            self.justification = self.short_assessment or self.criterion_explanation
        if not self.supporting_chunk_ids:
            self.supporting_chunk_ids = [
                item.chunk_id for item in self.evidence_items if item.evidence_type == "positive"
            ]
        if not self.contradicting_chunk_ids:
            self.contradicting_chunk_ids = [
                item.chunk_id for item in self.evidence_items if item.evidence_type == "negative"
            ]
        if not self.supporting_evidence:
            self.supporting_evidence = list(self.semantic_support_chunks)
        if not self.contradicting_evidence:
            self.contradicting_evidence = list(self.fallback_context_chunks)
        if not self.supporting_evidence_notes:
            self.supporting_evidence_notes = [
                EvidenceNarrative(
                    chunk_id=item.chunk_id,
                    location_summary=_format_heading_location(item.heading_path, item.page_start, item.page_end),
                    evidence_text=item.verbatim_excerpt,
                    why_it_matters=item.why_it_matters,
                )
                for item in self.evidence_items
                if item.evidence_type == "positive"
            ]
        if not self.contradicting_evidence_notes:
            self.contradicting_evidence_notes = [
                EvidenceNarrative(
                    chunk_id=item.chunk_id,
                    location_summary=_format_heading_location(item.heading_path, item.page_start, item.page_end),
                    evidence_text=item.verbatim_excerpt,
                    why_it_matters=item.why_it_matters,
                )
                for item in self.evidence_items
                if item.evidence_type == "negative"
            ]
        return self


class MainDimensionScore(BaseModel):
    main_dimension_id: str
    title: str
    weight: int = Field(ge=1, le=100)
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    weighted_score: float | None = None
    subcriteria_count: int = Field(default=0, ge=0)
    scored_subcriteria_count: int = Field(default=0, ge=0)
    summary: str = ""


class RubricTableEntry(BaseModel):
    main_dimension_title: str
    criterion_id: str
    main_dimension_id: str
    criterion_title: str
    description: str
    weight: int = Field(ge=1)
    source_sections: list[str] = Field(default_factory=list)
    ui_label: str = ""
    score_min: int = Field(default=0, ge=0, le=5)
    score_max: int = Field(default=5, ge=0, le=5)
    ui_explanation: str = ""


class EvaluationReport(BaseModel):
    session_id: str
    rubric_id: str
    rubric_version: str
    overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    main_scores: list[MainDimensionScore] = Field(default_factory=list)
    subcriteria_results: list[CriterionEvaluationResult] = Field(default_factory=list)
    rubric_table: list[RubricTableEntry] = Field(default_factory=list)
    major_strengths: list[str] = Field(default_factory=list)
    major_weaknesses: list[str] = Field(default_factory=list)
    critical_missing_information: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    total_weight: int | None = None
    total_weighted_score: float | None = None
    max_possible_weighted_score: float | None = None
    scored_criteria_count: int | None = None
    criterion_results: list[CriterionEvaluationResult] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    final_summary: str = ""

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_report_payload(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        criterion_results = normalized.get("criterion_results", [])
        normalized.setdefault("subcriteria_results", criterion_results)
        normalized.setdefault("major_strengths", normalized.get("strengths", []))
        normalized.setdefault("major_weaknesses", normalized.get("weaknesses", []))

        if "critical_missing_information" not in normalized:
            missing: list[str] = []
            for item in criterion_results:
                for missing_item in item.get("missing_information", []):
                    if missing_item not in missing:
                        missing.append(missing_item)
            normalized["critical_missing_information"] = missing[:5]

        if "red_flags" not in normalized:
            flags: list[str] = []
            for item in criterion_results:
                for flag in item.get("red_flags", []):
                    if flag not in flags:
                        flags.append(flag)
            normalized["red_flags"] = flags[:5]

        if "overall_score" not in normalized:
            total = normalized.get("total_weighted_score")
            maximum = normalized.get("max_possible_weighted_score")
            if isinstance(total, (int, float)) and isinstance(maximum, (int, float)) and maximum > 0:
                normalized["overall_score"] = round((float(total) / float(maximum)) * 100, 2)
            else:
                normalized["overall_score"] = None

        normalized.setdefault("main_scores", [])
        normalized.setdefault("rubric_table", [])
        return normalized

    @model_validator(mode="after")
    def apply_legacy_report_views(self) -> "EvaluationReport":
        if not self.criterion_results:
            self.criterion_results = list(self.subcriteria_results)
        if not self.strengths:
            self.strengths = list(self.major_strengths)
        if not self.weaknesses:
            self.weaknesses = list(self.major_weaknesses)
        return self


class EvaluationState(BaseModel):
    session_id: str
    status: EvaluationStatus
    current_step: EvaluationStep
    rubric_id: str | None = None
    rubric_version: str | None = None
    active_criterion_id: str | None = None
    active_criterion_title: str | None = None
    active_subcriterion_id: str | None = None
    active_subcriterion_title: str | None = None
    active_main_dimension_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None
    error: str | None = None
    criterion_results: list[CriterionEvaluationResult] = Field(default_factory=list)
    final_report: EvaluationReport | None = None

    @computed_field
    def subcriteria_results(self) -> list[CriterionEvaluationResult]:
        if self.final_report is not None:
            return self.final_report.subcriteria_results
        return self.criterion_results

    @computed_field
    def overall_score(self) -> float | None:
        return self.final_report.overall_score if self.final_report is not None else None

    @computed_field
    def main_scores(self) -> list[MainDimensionScore]:
        return self.final_report.main_scores if self.final_report is not None else []

    @computed_field
    def rubric_table(self) -> list[RubricTableEntry]:
        return self.final_report.rubric_table if self.final_report is not None else []

    @computed_field
    def major_strengths(self) -> list[str]:
        return self.final_report.major_strengths if self.final_report is not None else []

    @computed_field
    def major_weaknesses(self) -> list[str]:
        return self.final_report.major_weaknesses if self.final_report is not None else []

    @computed_field
    def critical_missing_information(self) -> list[str]:
        if self.final_report is not None:
            return self.final_report.critical_missing_information

        missing: list[str] = []
        for item in self.criterion_results:
            for missing_item in item.missing_information:
                if missing_item not in missing:
                    missing.append(missing_item)
        return missing

    @computed_field
    def red_flags(self) -> list[str]:
        if self.final_report is not None:
            return self.final_report.red_flags

        flags: list[str] = []
        for item in self.criterion_results:
            for flag in item.red_flags:
                if flag not in flags:
                    flags.append(flag)
        return flags


def _format_heading_location(
    heading_path: list[str],
    page_start: int | None,
    page_end: int | None,
) -> str:
    heading_text = " > ".join(heading_path) if heading_path else "Belirsiz bölüm"
    if page_start is None and page_end is None:
        return f"Belgede '{heading_text}' bölümünde."
    if page_start == page_end:
        return f"Belgenin '{heading_text}' bölümünde, {page_start}. sayfada."
    return f"Belgenin '{heading_text}' bölümünde, {page_start}-{page_end}. sayfalar arasında."


def _payload_get(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)
