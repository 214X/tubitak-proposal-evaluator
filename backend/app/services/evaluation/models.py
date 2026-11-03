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
    score_min: int = Field(default=0, ge=0, le=100)
    score_max: int = Field(default=100, ge=0, le=100)
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
        if self.score_min == 0 and self.score_max == 5:
            self.score_max = 100
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
    quote: str | None = None
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
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    claim_strength: float | None = Field(default=None, ge=0.0, le=100.0)
    evidence_quality: float | None = Field(default=None, ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    decision_status: CriterionDecisionStatus
    criterion_explanation: str = ""
    short_assessment: str = ""
    justification: str = ""
    score_rationale: str = ""
    positive_findings: list[CriterionFinding] = Field(default_factory=list)
    negative_findings: list[CriterionFinding] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    contradicting_chunk_ids: list[str] = Field(default_factory=list)
    supporting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)
    contradicting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)
    is_salvaged: bool = False

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_judge_payload(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        proposal_block = normalized.get("proje_oneri")
        if isinstance(proposal_block, dict):
            normalized = {
                **proposal_block,
                **{key: value for key, value in normalized.items() if key != "proje_oneri"},
            }

        normalized["criterion_id"] = _first_present(
            normalized,
            "criterion_id",
            "kriter_id",
            "alt_kriter_id",
            default="",
        )
        normalized["main_dimension_id"] = _first_present(
            normalized,
            "main_dimension_id",
            "ana_boyut",
            "ana_boyut_id",
            default=None,
        )
        normalized["title"] = _first_present(
            normalized,
            "title",
            "başlık",
            "baslik",
            "kriter",
            default="",
        )
        normalized["score"] = _normalize_legacy_score_value(
            _first_present(normalized, "score", "skor", "puan")
        )
        normalized["claim_strength"] = _normalize_legacy_score_value(
            _first_present(
                normalized,
                "claim_strength",
                "iddia_gucu",
                "iddia_gücü",
                "iddia_puani",
            )
        )
        normalized["evidence_quality"] = _normalize_legacy_score_value(
            _first_present(
                normalized,
                "evidence_quality",
                "kanit_kalitesi",
                "kanıt_kalitesi",
                "kanit_gucu",
                "kanıt_gücü",
            )
        )
        normalized["confidence"] = _normalize_confidence_value(
            _first_present(normalized, "confidence", "guven", "güven")
        )
        normalized["decision_status"] = _normalize_decision_status(
            _first_present(
                normalized,
                "decision_status",
                "karar_durumu",
                "degerlendirme_durumu",
            ),
            has_score=normalized.get("score") is not None,
            has_evidence=bool(normalized.get("evidence_items")),
        )
        justification = str(normalized.get("justification") or "").strip()
        if not justification:
            justification = str(
                _first_present(
                    normalized,
                    "gerekce",
                    "gerekçe",
                    "aciklama",
                    "açıklama",
                    default="",
                )
                or ""
            ).strip()
            normalized["justification"] = justification
        normalized.setdefault("criterion_explanation", justification)
        normalized.setdefault("short_assessment", justification)
        normalized["criterion_explanation"] = _first_present(
            normalized,
            "criterion_explanation",
            "kriter_aciklamasi",
            "kriter_açıklaması",
            default=normalized.get("criterion_explanation", ""),
        )
        normalized["short_assessment"] = _first_present(
            normalized,
            "short_assessment",
            "kisa_degerlendirme",
            "kısa_değerlendirme",
            "ozet",
            "özet",
            default=normalized.get("short_assessment", ""),
        )
        normalized["missing_information"] = _normalize_string_list(
            _first_present(
                normalized,
                "missing_information",
                "eksik_bilgiler",
                "eksik_bilgi",
                default=[],
            )
        )
        normalized["red_flags"] = _normalize_string_list(
            _first_present(
                normalized,
                "red_flags",
                "risk_isaretleri",
                "risk_işaretleri",
                "uyari_isaretleri",
                default=[],
            )
        )

        if "positive_findings" not in normalized:
            normalized["positive_findings"] = _normalize_findings(
                _first_present(
                    normalized,
                    "positive_findings",
                    "olumlu_bulgular",
                    default=normalized.get("supporting_evidence_notes", []),
                ),
                positive=True,
            ) or [
                {
                    "summary": _payload_get(item, "evidence_text") or _payload_get(item, "why_it_matters") or "",
                    "why_positive": _payload_get(item, "why_it_matters") or "",
                    "chunk_id": _payload_get(item, "chunk_id", ""),
                }
                for item in normalized.get("supporting_evidence_notes", [])
            ]
        if "negative_findings" not in normalized:
            normalized["negative_findings"] = _normalize_findings(
                _first_present(
                    normalized,
                    "negative_findings",
                    "zayiflatan_bulgular",
                    "zayıflatan_bulgular",
                    "olumsuz_bulgular",
                    default=normalized.get("contradicting_evidence_notes", []),
                ),
                positive=False,
            ) or [
                {
                    "summary": _payload_get(item, "evidence_text") or _payload_get(item, "why_it_matters") or "",
                    "why_negative": _payload_get(item, "why_it_matters") or "",
                    "chunk_id": _payload_get(item, "chunk_id", ""),
                }
                for item in normalized.get("contradicting_evidence_notes", [])
            ]
        normalized["evidence_items"] = _normalize_evidence_items(
            _first_present(
                normalized,
                "evidence_items",
                "kanit_ogeleri",
                "kanıt_ögeleri",
                default=[],
            )
        )
        if not normalized.get("evidence_items"):
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
        if not self.score_rationale:
            self.score_rationale = self.justification or self.short_assessment
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
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    claim_strength: float | None = Field(default=None, ge=0.0, le=100.0)
    evidence_quality: float | None = Field(default=None, ge=0.0, le=100.0)
    weight: int = Field(ge=1)
    weighted_score: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    decision_status: CriterionDecisionStatus
    criterion_explanation: str = ""
    short_assessment: str = ""
    justification: str = ""
    score_rationale: str = ""
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
    is_salvaged: bool = False

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_result_payload(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        normalized.setdefault("main_dimension_id", normalized.get("category"))
        normalized["score"] = _normalize_legacy_score_value(normalized.get("score"))
        normalized["claim_strength"] = _normalize_legacy_score_value(
            normalized.get("claim_strength")
        )
        normalized["evidence_quality"] = _normalize_legacy_score_value(
            normalized.get("evidence_quality")
        )

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
        if not self.score_rationale:
            self.score_rationale = self.justification or self.short_assessment
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
    score_min: int = Field(default=0, ge=0, le=100)
    score_max: int = Field(default=100, ge=0, le=100)
    ui_explanation: str = ""

    @model_validator(mode="after")
    def apply_legacy_scale(self) -> "RubricTableEntry":
        if self.score_min == 0 and self.score_max == 5:
            self.score_max = 100
        return self


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
        normalized.setdefault("critical_missing_information", [])
        normalized.setdefault("red_flags", [])

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
        return self.final_report.critical_missing_information if self.final_report is not None else []

    @computed_field
    def red_flags(self) -> list[str]:
        return self.final_report.red_flags if self.final_report is not None else []


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


def _normalize_legacy_score_value(value: Any) -> Any:
    if isinstance(value, (int, float)) and 0.0 <= float(value) <= 5.0:
        return round(float(value) * 20, 2)
    return value


def _first_present(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return default


def _normalize_confidence_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1.0 and numeric <= 100.0:
            return round(numeric / 100.0, 2)
        if 0.0 <= numeric <= 1.0:
            return numeric
    return 0.55


def _normalize_decision_status(
    value: Any,
    *,
    has_score: bool,
    has_evidence: bool,
) -> str:
    if isinstance(value, str):
        compact = value.strip().lower()
        status_map = {
            "scored": "scored",
            "puanlandi": "scored",
            "puanlandı": "scored",
            "basarili": "scored",
            "başarılı": "scored",
            "insufficient_evidence": "insufficient_evidence",
            "kanit_yetersiz": "insufficient_evidence",
            "kanıt_yetersiz": "insufficient_evidence",
            "yetersiz_kanit": "insufficient_evidence",
            "yetersiz_kanıt": "insufficient_evidence",
            "failed": "failed",
            "basarisiz": "failed",
            "başarısız": "failed",
            "conflicting_evidence": "conflicting_evidence",
            "celiskili_kanit": "conflicting_evidence",
            "çelişkili_kanıt": "conflicting_evidence",
        }
        if compact in status_map:
            return status_map[compact]
    if has_score:
        return "scored"
    if has_evidence:
        return "insufficient_evidence"
    return "failed"


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _normalize_findings(value: Any, *, positive: bool) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    findings: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            summary = item.strip()
            if not summary:
                continue
            findings.append(
                {
                    "summary": summary,
                    "why_positive" if positive else "why_negative": summary,
                    "chunk_id": "",
                }
            )
            continue

        if not isinstance(item, dict):
            continue

        summary = str(
            _first_present(
                item,
                "summary",
                "ozet",
                "özet",
                "bulgu",
                "metin",
                default="",
            )
            or ""
        ).strip()
        rationale = str(
            _first_present(
                item,
                "why_positive" if positive else "why_negative",
                "neden_olumlu" if positive else "neden_olumsuz",
                "aciklama",
                "açıklama",
                default=summary,
            )
            or ""
        ).strip()
        chunk_id = str(
            _first_present(item, "chunk_id", "parca_id", "parça_id", default="")
            or ""
        ).strip()

        if not summary and not rationale:
            continue

        findings.append(
            {
                "summary": summary or rationale,
                "why_positive" if positive else "why_negative": rationale or summary,
                "chunk_id": chunk_id,
            }
        )
    return findings


def _normalize_evidence_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        evidence_type = str(
            _first_present(
                item,
                "evidence_type",
                "tur",
                "tür",
                default="context",
            )
            or "context"
        ).strip().lower()
        type_map = {
            "positive": "positive",
            "destekleyici": "positive",
            "olumlu": "positive",
            "negative": "negative",
            "zayiflatan": "negative",
            "zayıflatan": "negative",
            "olumsuz": "negative",
            "context": "context",
            "baglam": "context",
            "bağlam": "context",
        }
        items.append(
            {
                "chunk_id": str(
                    _first_present(item, "chunk_id", "parca_id", "parça_id", default="")
                    or ""
                ).strip(),
                "evidence_type": type_map.get(evidence_type, "context"),
                "verbatim_excerpt": str(
                    _first_present(
                        item,
                        "verbatim_excerpt",
                        "dogrudan_alinti",
                        "doğrudan_alıntı",
                        "excerpt",
                        "metin",
                        default="",
                    )
                    or ""
                ).strip(),
                "heading_path": _normalize_string_list(
                    _first_present(item, "heading_path", "konum", "baslik_yolu", default=[])
                ),
                "page_start": _first_present(item, "page_start", "sayfa_baslangic", default=None),
                "page_end": _first_present(item, "page_end", "sayfa_bitis", default=None),
                "why_it_matters": str(
                    _first_present(
                        item,
                        "why_it_matters",
                        "neden_onemli",
                        "neden_önemli",
                        "aciklama",
                        "açıklama",
                        default="",
                    )
                    or ""
                ).strip(),
            }
        )
    return items
