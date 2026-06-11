from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request

from app.core.config import settings
from app.services.evaluation.models import (
    CriterionEvidence,
    CriterionEvaluationResult,
    CriterionJudgeResponse,
    EvidenceChunk,
    EvidenceNarrative,
    EvaluationCriterion,
)
from app.services.evaluation.prompt_builder import build_judge_messages


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
        payload = {
            "model": self.model_name,
            "messages": build_judge_messages(criterion, evidence),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        }
        raw_content = self._send_chat_request(payload)
        parsed = self._parse_content(raw_content)
        return CriterionEvaluationResult(
            criterion_id=criterion.criterion_id,
            category=criterion.category,
            title=criterion.title,
            score=parsed.score,
            weight=criterion.weight,
            weighted_score=parsed.score * criterion.weight if parsed.score is not None else None,
            confidence=parsed.confidence,
            decision_status=parsed.decision_status,
            justification=parsed.justification,
            supporting_chunk_ids=parsed.supporting_chunk_ids,
            contradicting_chunk_ids=parsed.contradicting_chunk_ids,
            missing_information=parsed.missing_information,
            red_flags=parsed.red_flags,
            supporting_evidence=evidence.supporting_evidence,
            contradicting_evidence=evidence.contradicting_evidence,
            supporting_evidence_notes=self._merge_evidence_notes(
                parsed.supporting_evidence_notes,
                evidence.supporting_evidence,
                positive=True,
            ),
            contradicting_evidence_notes=self._merge_evidence_notes(
                parsed.contradicting_evidence_notes,
                evidence.contradicting_evidence,
                positive=False,
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
                f"Ollama request failed. Ensure Ollama is running at {self.base_url} "
                f"and model '{self.model_name}' is available."
            ) from exc

        message = payload.get("message", {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned an empty response.")
        return content

    def _parse_content(self, raw_content: str) -> CriterionJudgeResponse:
        try:
            return CriterionJudgeResponse.model_validate(json.loads(raw_content))
        except json.JSONDecodeError:
            start = raw_content.find("{")
            end = raw_content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise RuntimeError("Ollama response could not be parsed as JSON.")
            return CriterionJudgeResponse.model_validate(json.loads(raw_content[start : end + 1]))

    def _merge_evidence_notes(
        self,
        notes: list[EvidenceNarrative],
        evidence_items: list[EvidenceChunk],
        *,
        positive: bool,
    ) -> list[EvidenceNarrative]:
        by_chunk_id = {item.chunk_id: item for item in evidence_items}
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
                        "Bu bölüm kriter lehine yorumlanabilecek içerik içeriyor."
                        if positive
                        else "Bu bölüm kriter aleyhine yorumlanabilecek içerik içeriyor."
                    ),
                )
            )

        return merged

    def _format_location(self, item: EvidenceChunk) -> str:
        heading_path = " > ".join(item.heading_path_titles) if item.heading_path_titles else "Belirsiz bölüm"
        if item.page_start is None and item.page_end is None:
            return f"Belgede '{heading_path}' bölümünde."
        if item.page_start == item.page_end:
            return f"Belgenin '{heading_path}' bölümünde, {item.page_start}. sayfada."
        return f"Belgenin '{heading_path}' bölümünde, {item.page_start}-{item.page_end}. sayfalar arasında."

    def _summarize_chunk_text(self, text: str) -> str:
        collapsed = " ".join(text.split())
        if len(collapsed) <= 280:
            return collapsed
        return f"{collapsed[:277].rstrip()}..."


def get_judge_provider() -> OllamaAyaProvider:
    return OllamaAyaProvider()
