from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request

from app.core.config import settings
from app.services.evaluation.models import (
    CriterionEvidence,
    CriterionEvaluationResult,
    CriterionFinding,
    CriterionJudgeResponse,
    EvidenceChunk,
    EvidenceItem,
    EvidenceNarrative,
    EvaluationCriterion,
)
from app.services.evaluation.prompt_builder import build_json_retry_message, build_judge_messages


@dataclass(frozen=True)
class OllamaAyaProvider:
    base_url: str = settings.ollama_base_url
    model_name: str = settings.ollama_model_name
    timeout_seconds: int = settings.ollama_request_timeout_seconds

    def evaluate_criterion(
        self,
        criterion: EvaluationCriterion,
        evidence: CriterionEvidence,
    ) -> CriterionEvaluationResult:
        base_messages = build_judge_messages(criterion, evidence)
        last_error: Exception | None = None

        for attempt_index in range(2):
            messages = list(base_messages)
            if attempt_index == 1:
                messages.append(build_json_retry_message())

            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                },
            }

            try:
                raw_content = self._send_chat_request(payload)
                parsed = self._parse_content(raw_content)
                sanitized = self._sanitize_response(parsed, criterion, evidence)
                return self._build_evaluation_result(criterion, evidence, sanitized)
            except (RuntimeError, ValueError) as exc:
                last_error = exc

        return self._build_failed_result(
            criterion=criterion,
            evidence=evidence,
            error_message=self._localize_error_message(
                str(last_error) if last_error else "Judge response could not be parsed.",
            ),
        )

    def _send_chat_request(self, payload: dict) -> str:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url.rstrip('/')}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(
                f"Ollama isteği başarısız oldu. Ollama servisinin {self.base_url} "
                f"adresinde çalıştığından ve '{self.model_name}' modelinin yüklü olduğundan emin olun."
            ) from exc

        message = payload.get("message", {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama boş bir yanıt döndürdü.")
        return content

    def _parse_content(self, raw_content: str) -> CriterionJudgeResponse:
        try:
            return CriterionJudgeResponse.model_validate(json.loads(raw_content))
        except json.JSONDecodeError:
            start = raw_content.find("{")
            end = raw_content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise RuntimeError("Ollama yanıtı JSON olarak ayrıştırılamadı.")
            return CriterionJudgeResponse.model_validate(json.loads(raw_content[start : end + 1]))
        except Exception as exc:
            raise RuntimeError(f"Judge yanıtı beklenen şemaya uymadı: {exc}") from exc

    def _sanitize_response(
        self,
        parsed: CriterionJudgeResponse,
        criterion: EvaluationCriterion,
        evidence: CriterionEvidence,
    ) -> CriterionJudgeResponse:
        allowed_chunk_ids = {
            item.chunk_id
            for item in [
                *evidence.primary_section_chunks,
                *evidence.semantic_support_chunks,
                *evidence.fallback_context_chunks,
            ]
        }
        evidence_by_chunk_id = {
            item.chunk_id: item
            for item in [
                *evidence.primary_section_chunks,
                *evidence.semantic_support_chunks,
                *evidence.fallback_context_chunks,
            ]
        }

        evidence_items = [
            item for item in parsed.evidence_items if item.chunk_id in allowed_chunk_ids
        ]
        positive_findings = [
            item for item in parsed.positive_findings if item.chunk_id in allowed_chunk_ids
        ]
        negative_findings = [
            item for item in parsed.negative_findings if item.chunk_id in allowed_chunk_ids
        ]

        supporting_chunk_ids = [
            chunk_id for chunk_id in parsed.supporting_chunk_ids if chunk_id in allowed_chunk_ids
        ]
        contradicting_chunk_ids = [
            chunk_id for chunk_id in parsed.contradicting_chunk_ids if chunk_id in allowed_chunk_ids
        ]

        if not supporting_chunk_ids:
            supporting_chunk_ids = [
                item.chunk_id for item in evidence_items if item.evidence_type == "positive"
            ]
        if not contradicting_chunk_ids:
            contradicting_chunk_ids = [
                item.chunk_id for item in evidence_items if item.evidence_type == "negative"
            ]

        supporting_notes = self._evidence_items_to_notes(
            [item for item in evidence_items if item.evidence_type == "positive"],
            evidence_by_chunk_id,
            fallback_note="Bu kanıt ilgili iddiayı destekliyor.",
        )
        contradicting_notes = self._evidence_items_to_notes(
            [item for item in evidence_items if item.evidence_type == "negative"],
            evidence_by_chunk_id,
            fallback_note="Bu kanıt iddiayı zayıflatıyor veya soru işareti oluşturuyor.",
        )

        return CriterionJudgeResponse(
            criterion_id=parsed.criterion_id or criterion.criterion_id,
            main_dimension_id=parsed.main_dimension_id or criterion.main_dimension_id,
            title=parsed.title or criterion.title,
            score=_normalize_score_scale(parsed.score),
            claim_strength=_normalize_score_scale(parsed.claim_strength),
            evidence_quality=_normalize_score_scale(parsed.evidence_quality),
            confidence=parsed.confidence,
            decision_status=parsed.decision_status,
            criterion_explanation=parsed.criterion_explanation or parsed.justification,
            short_assessment=parsed.short_assessment or parsed.justification,
            justification=parsed.justification or parsed.short_assessment or parsed.criterion_explanation,
            positive_findings=positive_findings,
            negative_findings=negative_findings,
            missing_information=parsed.missing_information,
            red_flags=parsed.red_flags,
            evidence_items=evidence_items,
            supporting_chunk_ids=supporting_chunk_ids,
            contradicting_chunk_ids=contradicting_chunk_ids,
            supporting_evidence_notes=supporting_notes,
            contradicting_evidence_notes=contradicting_notes,
        )

    def _build_evaluation_result(
        self,
        criterion: EvaluationCriterion,
        evidence: CriterionEvidence,
        parsed: CriterionJudgeResponse,
    ) -> CriterionEvaluationResult:
        return CriterionEvaluationResult(
            criterion_id=criterion.criterion_id,
            main_dimension_id=criterion.main_dimension_id,
            category=criterion.category,
            title=criterion.title,
            score=parsed.score,
            claim_strength=parsed.claim_strength,
            evidence_quality=parsed.evidence_quality,
            weight=criterion.weight,
            weighted_score=parsed.score,
            confidence=parsed.confidence,
            decision_status=parsed.decision_status,
            criterion_explanation=parsed.criterion_explanation,
            short_assessment=parsed.short_assessment,
            justification=parsed.justification,
            positive_findings=parsed.positive_findings,
            negative_findings=parsed.negative_findings,
            missing_information=parsed.missing_information,
            red_flags=parsed.red_flags,
            evidence_items=parsed.evidence_items,
            primary_section_chunks=evidence.primary_section_chunks,
            semantic_support_chunks=evidence.semantic_support_chunks,
            fallback_context_chunks=evidence.fallback_context_chunks,
            coverage_status=evidence.coverage_status,
            coverage_notes=evidence.coverage_notes,
            supporting_chunk_ids=parsed.supporting_chunk_ids,
            contradicting_chunk_ids=parsed.contradicting_chunk_ids,
            supporting_evidence=evidence.supporting_evidence,
            contradicting_evidence=evidence.contradicting_evidence,
            supporting_evidence_notes=parsed.supporting_evidence_notes,
            contradicting_evidence_notes=parsed.contradicting_evidence_notes,
        )

    def _build_failed_result(
        self,
        *,
        criterion: EvaluationCriterion,
        evidence: CriterionEvidence,
        error_message: str,
    ) -> CriterionEvaluationResult:
        fallback_evidence_items = self._build_fallback_evidence_items(evidence)
        return CriterionEvaluationResult(
            criterion_id=criterion.criterion_id,
            main_dimension_id=criterion.main_dimension_id,
            category=criterion.category,
            title=criterion.title,
            score=None,
            claim_strength=None,
            evidence_quality=None,
            weight=criterion.weight,
            weighted_score=None,
            confidence=0.0,
            decision_status="failed",
            criterion_explanation="Judge yanıtı güvenilir biçimde üretilemedi.",
            short_assessment="Model yanıtı parse edilemedi.",
            justification="Model yanıtı parse edilemedi.",
            positive_findings=[],
            negative_findings=[],
            missing_information=[criterion.description],
            red_flags=[error_message],
            evidence_items=fallback_evidence_items,
            primary_section_chunks=evidence.primary_section_chunks,
            semantic_support_chunks=evidence.semantic_support_chunks,
            fallback_context_chunks=evidence.fallback_context_chunks,
            coverage_status=evidence.coverage_status,
            coverage_notes=evidence.coverage_notes,
            supporting_chunk_ids=[
                item.chunk_id for item in fallback_evidence_items if item.evidence_type == "positive"
            ],
            contradicting_chunk_ids=[
                item.chunk_id for item in fallback_evidence_items if item.evidence_type == "negative"
            ],
            supporting_evidence=evidence.supporting_evidence,
            contradicting_evidence=evidence.contradicting_evidence,
            supporting_evidence_notes=self._merge_evidence_notes(
                [],
                evidence.supporting_evidence,
                positive=True,
            ),
            contradicting_evidence_notes=self._merge_evidence_notes(
                [],
                evidence.contradicting_evidence,
                positive=False,
            ),
        )

    def _build_fallback_evidence_items(
        self,
        evidence: CriterionEvidence,
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for chunk in evidence.primary_section_chunks + evidence.semantic_support_chunks:
            items.append(
                EvidenceItem(
                    chunk_id=chunk.chunk_id,
                    evidence_type="positive",
                    verbatim_excerpt=self._summarize_chunk_text(chunk.text_for_embedding),
                    heading_path=list(chunk.heading_path_titles),
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    why_it_matters="Bu içerik kriterle ilgili bir iddiayı destekleyebilir.",
                )
            )
        for chunk in evidence.fallback_context_chunks:
            items.append(
                EvidenceItem(
                    chunk_id=chunk.chunk_id,
                    evidence_type="context",
                    verbatim_excerpt=self._summarize_chunk_text(chunk.text_for_embedding),
                    heading_path=list(chunk.heading_path_titles),
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    why_it_matters="Bu içerik bağlam sağlar ancak tek başına güçlü kanıt olmayabilir.",
                )
            )
        return items

    def _localize_error_message(self, message: str) -> str:
        localized = message
        replacements = {
            "Judge response did not match schema": "Judge yanıtı beklenen şemaya uymadı",
            "Judge response could not be parsed.": "Judge yanıtı ayrıştırılamadı.",
            "Ollama response could not be parsed as JSON.": "Ollama yanıtı JSON olarak ayrıştırılamadı.",
            "Ollama returned an empty response.": "Ollama boş bir yanıt döndürdü.",
            "Field required": "Alan zorunlu",
            "For further information visit": "Ayrıntı için ziyaret edin",
            "validation errors for CriterionJudgeResponse": "CriterionJudgeResponse için doğrulama hataları",
            "input_value": "gelen_deger",
            "input_type": "gelen_tip",
        }
        for source, target in replacements.items():
            localized = localized.replace(source, target)
        return localized

    def _evidence_items_to_notes(
        self,
        items: list[EvidenceItem],
        evidence_by_chunk_id: dict[str, EvidenceChunk],
        *,
        fallback_note: str,
    ) -> list[EvidenceNarrative]:
        notes: list[EvidenceNarrative] = []
        for item in items:
            chunk = evidence_by_chunk_id.get(item.chunk_id)
            location = self._format_location(chunk, heading_path=item.heading_path)
            notes.append(
                EvidenceNarrative(
                    chunk_id=item.chunk_id,
                    location_summary=location,
                    evidence_text=item.verbatim_excerpt,
                    why_it_matters=item.why_it_matters or fallback_note,
                )
            )
        return notes

    def _merge_evidence_notes(
        self,
        notes: list[EvidenceNarrative],
        evidence_items: list[EvidenceChunk],
        *,
        positive: bool,
    ) -> list[EvidenceNarrative]:
        merged: list[EvidenceNarrative] = []
        seen: set[str] = set()

        for note in notes:
            merged.append(note)
            seen.add(note.chunk_id)

        for item in evidence_items:
            if item.chunk_id in seen:
                continue
            merged.append(
                EvidenceNarrative(
                    chunk_id=item.chunk_id,
                    location_summary=self._format_location(item),
                    evidence_text=self._summarize_chunk_text(item.text_for_embedding),
                    why_it_matters=(
                        "Bu bölüm ilgili iddiayı destekleyebilecek içerik içeriyor."
                        if positive
                        else "Bu bölüm iddiayı zayıflatabilecek veya belirsizleştirebilecek içerik içeriyor."
                    ),
                )
            )

        return merged

    def _format_location(
        self,
        item: EvidenceChunk | None,
        *,
        heading_path: list[str] | None = None,
    ) -> str:
        resolved_heading_path = (
            heading_path
            if heading_path
            else (item.heading_path_titles if item is not None else [])
        )
        heading_text = " > ".join(resolved_heading_path) if resolved_heading_path else "Belirsiz bölüm"
        page_start = item.page_start if item is not None else None
        page_end = item.page_end if item is not None else None
        if page_start is None and page_end is None:
            return f"Belgede '{heading_text}' bölümünde."
        if page_start == page_end:
            return f"Belgenin '{heading_text}' bölümünde, {page_start}. sayfada."
        return f"Belgenin '{heading_text}' bölümünde, {page_start}-{page_end}. sayfalar arasında."

    def _summarize_chunk_text(self, text: str) -> str:
        collapsed = " ".join(text.split())
        if len(collapsed) <= 280:
            return collapsed
        return f"{collapsed[:277].rstrip()}..."


def get_judge_provider() -> OllamaAyaProvider:
    return OllamaAyaProvider()


def _normalize_score_scale(value: float | None) -> float | None:
    if value is None:
        return None
    if 0.0 <= value <= 5.0:
        return round(value * 20, 2)
    return value
