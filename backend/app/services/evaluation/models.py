from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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


class EvaluationCriterion(BaseModel):
    criterion_id: str
    category: str
    title: str
    description: str
    weight: int = Field(ge=1)
    allowed_scores: list[int] = Field(min_length=1)
    allowed_chunk_types: list[ChunkType] = Field(default_factory=list)
    positive_queries: list[str] = Field(default_factory=list)
    negative_queries: list[str] = Field(default_factory=list)
    evidence_top_k: int = Field(default=5, ge=1, le=10)
    minimum_evidence_count: int = Field(default=1, ge=0, le=10)
    decision_rule: CriterionDecisionRule = "support_vs_contradiction"


class EvaluationRubric(BaseModel):
    rubric_id: str
    version: str
    program_codes: list[str] = Field(default_factory=list)
    criteria: list[EvaluationCriterion] = Field(default_factory=list)


class EvidenceChunk(BaseModel):
    chunk_id: str
    chunk_type: ChunkType
    heading_path_titles: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    text_for_embedding: str
    similarity_score: float = Field(ge=0.0)


class CriterionEvidence(BaseModel):
    criterion_id: str
    supporting_evidence: list[EvidenceChunk] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceChunk] = Field(default_factory=list)


class EvidenceNarrative(BaseModel):
    chunk_id: str
    location_summary: str
    evidence_text: str
    why_it_matters: str


class CriterionJudgeResponse(BaseModel):
    score: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    decision_status: CriterionDecisionStatus
    justification: str
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    contradicting_chunk_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    supporting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)
    contradicting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)


class CriterionEvaluationResult(BaseModel):
    criterion_id: str
    category: str
    title: str
    score: int | None = None
    weight: int = Field(ge=1)
    weighted_score: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    decision_status: CriterionDecisionStatus
    justification: str
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    contradicting_chunk_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    supporting_evidence: list[EvidenceChunk] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceChunk] = Field(default_factory=list)
    supporting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)
    contradicting_evidence_notes: list[EvidenceNarrative] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    session_id: str
    rubric_id: str
    rubric_version: str
    total_weight: int
    total_weighted_score: int
    max_possible_weighted_score: int
    scored_criteria_count: int
    criterion_results: list[CriterionEvaluationResult] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    final_summary: str


class EvaluationState(BaseModel):
    session_id: str
    status: EvaluationStatus
    current_step: EvaluationStep
    rubric_id: str | None = None
    rubric_version: str | None = None
    active_criterion_id: str | None = None
    active_criterion_title: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None
    error: str | None = None
    criterion_results: list[CriterionEvaluationResult] = Field(default_factory=list)
    final_report: EvaluationReport | None = None
