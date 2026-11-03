from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from app.core.config import settings
from app.services.evaluation.models import (
    CriterionEvidence,
    CriterionEvaluationResult,
    CriterionJudgeResponse,
    EvidenceChunk,
    EvidenceItem,
    EvidenceNarrative,
    EvaluationCriterion,
)
from app.services.evaluation.prompt_builder import (
    build_json_retry_message,
    build_judge_format_schema,
    build_judge_messages,
)
from app.services.evaluation.retrieval import build_ranked_evidence


class OllamaUnavailableError(RuntimeError):
    """Raised when the Ollama service itself cannot be reached (infrastructure failure)."""


@dataclass(frozen=True)
class OllamaAyaProvider:
    base_url: str = settings.ollama_base_url
    model_name: str = settings.ollama_model_name
    timeout_seconds: int = settings.ollama_request_timeout_seconds
    temperature: float = settings.ollama_temperature
    evidence_limit: int = settings.judge_evidence_limit
    uncited_score_cap: float = settings.judge_uncited_score_cap

    def evaluate_criterion(
        self,
        criterion: EvaluationCriterion,
        evidence: CriterionEvidence,
    ) -> CriterionEvaluationResult:
        base_messages, index_to_chunk_id = build_judge_messages(criterion, evidence)
        chunk_by_id = self._build_chunk_lookup(evidence)
        ranked = build_ranked_evidence(evidence, limit=self.evidence_limit)
        format_schema = build_judge_format_schema()
        last_error: Exception | None = None

        for attempt_index in range(2):
            messages = list(base_messages)
            # İlk deneme şema-kısıtlı (constrained) üretim; ikinci deneme eski Ollama
            # sürümlerinde de çalışsın diye düz JSON'a düşer (graceful fallback).
            response_format: Any = format_schema if attempt_index == 0 else "json"
            if attempt_index == 1:
                messages.append(build_json_retry_message())

            try:
                raw_content = self._send_chat_request(messages, response_format)
                raw_payload = self._parse_json_object(raw_content)
                parsed = self._transform_model_output(
                    raw_payload,
                    criterion=criterion,
                    index_to_chunk_id=index_to_chunk_id,
                    chunk_by_id=chunk_by_id,
                )
                parsed = self._apply_uncited_guard(parsed, ranked)
                return self._build_evaluation_result(criterion, evidence, parsed)
            except OllamaUnavailableError as exc:
                # Altyapı erişilemiyorsa kurtarma anlamsızdır; gerçek hata yüzeye çıkmalı.
                raise exc
            except (RuntimeError, ValueError) as exc:
                last_error = exc

        # Model erişilebildi ama kullanılabilir yanıt üretemedi → "failed" yerine
        # eldeki kanıtlardan deterministik, ihtiyatlı bir sonuç kurtar.
        return self._build_salvaged_result(
            criterion=criterion,
            evidence=evidence,
            ranked=ranked,
            error_message=self._localize_error_message(
                str(last_error) if last_error else "Judge response could not be parsed.",
            ),
        )

    # ----------------------------------------------------------------- transport

    def _send_chat_request(self, messages: list[dict[str, str]], response_format: Any) -> str:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "format": response_format,
            "options": {
                "temperature": self.temperature,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url.rstrip('/')}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise OllamaUnavailableError(
                f"Ollama isteği başarısız oldu. Ollama servisinin {self.base_url} "
                f"adresinde çalıştığından ve '{self.model_name}' modelinin yüklü olduğundan emin olun."
            ) from exc

        message = response_payload.get("message", {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama boş bir yanıt döndürdü.")
        return content

    def _parse_json_object(self, raw_content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            start = raw_content.find("{")
            end = raw_content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise RuntimeError("Ollama yanıtı JSON olarak ayrıştırılamadı.")
            parsed = json.loads(raw_content[start : end + 1])
        if not isinstance(parsed, dict):
            raise RuntimeError("Ollama yanıtı beklenen JSON nesnesi değil.")
        return parsed

    # ------------------------------------------------------------- transformation

    def _transform_model_output(
        self,
        raw: dict[str, Any],
        criterion: EvaluationCriterion,
        index_to_chunk_id: dict[int, str],
        chunk_by_id: dict[str, EvidenceChunk],
    ) -> CriterionJudgeResponse:
        """Ref tabanlı model çıktısını chunk_id tabanlı şemaya çevirir.

        Model yalnızca kanıt numarası (ref) üretir; gerçek chunk_id, başlık ve sayfa
        bilgisi buradaki güvenilir eşlemeden gelir. Geçersiz ref'ler düşürülür, yani
        chunk_id halüsinasyonu yapısal olarak imkânsızdır.
        """

        def resolve(ref: Any) -> EvidenceChunk | None:
            index = _coerce_int(ref)
            if index is None:
                return None
            chunk_id = index_to_chunk_id.get(index)
            if chunk_id is None:
                return None
            return chunk_by_id.get(chunk_id)

        positive_findings = self._resolve_findings(raw.get("positive_findings"), resolve, positive=True)
        negative_findings = self._resolve_findings(raw.get("negative_findings"), resolve, positive=False)
        evidence_items = self._resolve_evidence_items(raw.get("evidence_items"), resolve)

        justification = _clean_text(raw.get("justification"))
        short_assessment = _clean_text(raw.get("short_assessment")) or justification
        # Kriter beklentisi sabittir ve projeye özgü değildir; modele ürettirmek yerine
        # rubric'ten doğrudan alınır (token tasarrufu + sapma riskinin önlenmesi).
        criterion_explanation = criterion.ui_explanation or criterion.description

        # Eksenler 1-5 ayrık seviye olarak gelir; _normalize_score_scale bunları 0-100'e
        # ölçekler (1->20 .. 5->100). gap_severity 1-5 ham kalır (skor düşürme faktörü).
        claim_strength = _normalize_score_scale(_coerce_float(raw.get("claim_strength")))
        evidence_quality = _normalize_score_scale(_coerce_float(raw.get("evidence_quality")))
        gap_severity = _coerce_int(raw.get("gap_severity"))
        # Bulgu dengesi (grounded sayılar) skoru deterministik olarak etkiler.
        derived_score = _derive_score(
            claim_strength,
            evidence_quality,
            gap_severity,
            positive_count=len(positive_findings),
            negative_count=len(negative_findings),
        )

        payload = {
            "criterion_id": criterion.criterion_id,
            "main_dimension_id": criterion.main_dimension_id,
            "title": criterion.title,
            "claim_strength": claim_strength,
            "evidence_quality": evidence_quality,
            "confidence": _coerce_confidence(raw.get("confidence")),
            "decision_status": _coerce_decision_status(raw.get("decision_status")),
            "criterion_explanation": criterion_explanation,
            "short_assessment": short_assessment,
            "justification": justification or short_assessment,
            "score_rationale": _clean_text(raw.get("score_rationale")) or justification or short_assessment,
            "positive_findings": positive_findings,
            "negative_findings": negative_findings,
            "missing_information": _clean_text_list(raw.get("missing_information")),
            "red_flags": _clean_text_list(raw.get("red_flags")),
            "evidence_items": evidence_items,
        }
        # Skoru payload'a koymuyoruz: legacy migrate validator'ı [0,5] aralığındaki
        # değerleri ×20 ölçeklerdi ve meşru düşük türetilmiş skorları (örn. 4.8) yanlışça
        # şişirirdi. Bu yüzden doğrulamadan SONRA model_copy ile birebir set ediyoruz.
        parsed = CriterionJudgeResponse.model_validate(payload)
        return parsed.model_copy(update={"score": derived_score})

    def _resolve_findings(
        self,
        raw_findings: Any,
        resolve,
        *,
        positive: bool,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw_findings, list):
            return []
        reason_key = "why_positive" if positive else "why_negative"
        fallback_reason = (
            "Bu kanıt iddiayı destekliyor."
            if positive
            else "Bu kanıt iddiayı zayıflatıyor veya soru işareti oluşturuyor."
        )
        findings: list[dict[str, Any]] = []
        for item in raw_findings:
            if not isinstance(item, dict):
                continue
            chunk = resolve(item.get("ref"))
            if chunk is None:
                continue
            summary = _clean_text(item.get("summary"))
            reason = _clean_text(item.get("reason"))
            if not summary and not reason:
                continue
            # Grounding güvencesi: bulgu, atıf yaptığı kanıttan BİREBİR bir alıntı taşımalı
            # ve bu alıntı gerçekten o chunk'ın metninde geçmeli. Aksi halde bulgu uydurma
            # sayılır ve rapora hiç girmez (en katı anti-halüsinasyon politikası).
            quote = _strip_ref_markers(_clean_text(item.get("quote")))
            if not quote or not _quote_is_grounded(quote, chunk.text_for_embedding):
                continue
            findings.append(
                {
                    "summary": summary or reason,
                    reason_key: reason or fallback_reason,
                    "quote": quote,
                    "chunk_id": chunk.chunk_id,
                }
            )
        return findings

    def _resolve_evidence_items(self, raw_items: Any, resolve) -> list[dict[str, Any]]:
        if not isinstance(raw_items, list):
            return []
        valid_types = {"positive", "negative", "context"}
        items: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            chunk = resolve(item.get("ref"))
            if chunk is None:
                continue
            evidence_type = str(item.get("evidence_type") or "context").strip().lower()
            if evidence_type not in valid_types:
                evidence_type = "context"
            key = (chunk.chunk_id, evidence_type)
            if key in seen:
                continue
            seen.add(key)
            # Kanıt göstergesi: chunk_id ref ile zaten yapısal doğru. Modelin alıntısı
            # chunk'ta doğrulanamıyorsa düşürmek yerine chunk'ın KENDİ metniyle değiştir;
            # böylece gösterilen alıntı her zaman belgeyle birebir kalır.
            excerpt = _strip_ref_markers(_clean_text(item.get("verbatim_excerpt")))
            if not excerpt or not _quote_is_grounded(excerpt, chunk.text_for_embedding):
                excerpt = self._summarize_chunk_text(chunk.text_for_embedding)
            items.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "evidence_type": evidence_type,
                    "verbatim_excerpt": excerpt,
                    "heading_path": list(chunk.heading_path_titles),
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "why_it_matters": _clean_text(item.get("why_it_matters"))
                    or "Bu kanıt kriter değerlendirmesinde kullanıldı.",
                }
            )
        return items

    def _apply_uncited_guard(
        self,
        parsed: CriterionJudgeResponse,
        ranked: list[EvidenceChunk],
    ) -> CriterionJudgeResponse:
        """Model geçerli atıf üretmediyse kanıtı otomatik doldurur ve skoru sınırlar.

        Böylece UI'da hem boş kanıt kartı kalmaz hem de kanıtsız yüksek puan engellenir.
        """
        if parsed.evidence_items:
            return parsed

        autofilled = [
            EvidenceItem(
                chunk_id=chunk.chunk_id,
                evidence_type="context",
                verbatim_excerpt=self._summarize_chunk_text(chunk.text_for_embedding),
                heading_path=list(chunk.heading_path_titles),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                why_it_matters=(
                    "Bu içerik kriterle ilgili en yüksek öncelikli kanıttır; model doğrudan "
                    "atıf üretmediği için otomatik eklendi."
                ),
            )
            for chunk in ranked[:3]
        ]
        notes = [
            EvidenceNarrative(
                chunk_id=item.chunk_id,
                location_summary=self._format_location(None, heading_path=item.heading_path),
                evidence_text=item.verbatim_excerpt,
                why_it_matters=item.why_it_matters,
            )
            for item in autofilled
        ]

        capped_score = parsed.score
        if capped_score is not None and capped_score > self.uncited_score_cap:
            capped_score = self.uncited_score_cap

        missing = list(parsed.missing_information)
        cap_note = "Model değerlendirmeyi belirli bir kanıta bağlayamadı; puan ihtiyatla sınırlandı."
        if cap_note not in missing:
            missing.append(cap_note)

        return parsed.model_copy(
            update={
                "score": capped_score,
                "evidence_items": autofilled,
                "supporting_chunk_ids": [item.chunk_id for item in autofilled],
                "supporting_evidence_notes": notes,
                "missing_information": missing,
            }
        )

    # --------------------------------------------------------------- result build

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
            score_rationale=parsed.score_rationale,
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
            is_salvaged=parsed.is_salvaged,
        )

    def _build_salvaged_result(
        self,
        *,
        criterion: EvaluationCriterion,
        evidence: CriterionEvidence,
        ranked: list[EvidenceChunk],
        error_message: str,
    ) -> CriterionEvaluationResult:
        evidence_items = [
            EvidenceItem(
                chunk_id=chunk.chunk_id,
                evidence_type="context",
                verbatim_excerpt=self._summarize_chunk_text(chunk.text_for_embedding),
                heading_path=list(chunk.heading_path_titles),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                why_it_matters="Model yanıtı kullanılamadığı için bu kanıt otomatik olarak listelendi.",
            )
            for chunk in ranked[:3]
        ]
        notes = [
            EvidenceNarrative(
                chunk_id=item.chunk_id,
                location_summary=self._format_location(None, heading_path=item.heading_path),
                evidence_text=item.verbatim_excerpt,
                why_it_matters=item.why_it_matters,
            )
            for item in evidence_items
        ]
        penalty = 15.0 if evidence.coverage_status == "missing" else 0.0
        salvage_score = max(0.0, round(50.0 - penalty, 2))

        return CriterionEvaluationResult(
            criterion_id=criterion.criterion_id,
            main_dimension_id=criterion.main_dimension_id,
            category=criterion.category,
            title=criterion.title,
            score=salvage_score,
            claim_strength=40.0,
            evidence_quality=40.0,
            weight=criterion.weight,
            weighted_score=salvage_score,
            confidence=0.2,
            decision_status="insufficient_evidence",
            criterion_explanation=criterion.ui_explanation or criterion.description,
            short_assessment="Model yanıtı kullanılamadı; kriter kanıtlardan otomatik tamamlandı.",
            justification=(
                "Geçerli bir model değerlendirmesi alınamadığı için kriter, mevcut kanıtlara "
                "dayanan ihtiyatlı bir taban puanla sonuçlandırıldı."
            ),
            positive_findings=[],
            negative_findings=[],
            missing_information=[criterion.description],
            red_flags=[error_message],
            evidence_items=evidence_items,
            primary_section_chunks=evidence.primary_section_chunks,
            semantic_support_chunks=evidence.semantic_support_chunks,
            fallback_context_chunks=evidence.fallback_context_chunks,
            coverage_status=evidence.coverage_status,
            coverage_notes=evidence.coverage_notes,
            supporting_chunk_ids=[item.chunk_id for item in evidence_items],
            contradicting_chunk_ids=[],
            supporting_evidence=evidence.supporting_evidence,
            contradicting_evidence=evidence.contradicting_evidence,
            supporting_evidence_notes=notes,
            contradicting_evidence_notes=[],
            is_salvaged=True,
        )

    # -------------------------------------------------------------------- helpers

    def _build_chunk_lookup(self, evidence: CriterionEvidence) -> dict[str, EvidenceChunk]:
        lookup: dict[str, EvidenceChunk] = {}
        for chunk in [
            *evidence.primary_section_chunks,
            *evidence.semantic_support_chunks,
            *evidence.fallback_context_chunks,
        ]:
            lookup.setdefault(chunk.chunk_id, chunk)
        return lookup

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


_MATCH_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
_LEADING_REF_MARKER_PATTERN = re.compile(r"^\s*(?:\[\s*[Kk]\s*\d+\s*\]\s*)+")


def _strip_ref_markers(value: str) -> str:
    """Modelin alıntıya kopyaladığı baştaki [K#] etiketlerini temizler (kozmetik)."""
    return _LEADING_REF_MARKER_PATTERN.sub("", value).strip()


def _normalize_for_match(value: str) -> str:
    collapsed = " ".join(value.split()).strip().casefold()
    decomposed = unicodedata.normalize("NFKD", collapsed)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _MATCH_NON_ALNUM_PATTERN.sub(" ", without_marks).strip()


def _quote_is_grounded(quote: str, chunk_text: str, threshold: float = 0.85) -> bool:
    """Modelin alıntısının chunk metninde gerçekten geçip geçmediğini doğrular.

    Normalize edildikten sonra önce substring; değilse alıntının chunk içinde bulunan en
    uzun bitişik bloğunun oranı eşiği aşıyorsa grounded sayılır (küçük biçim sapmalarına
    tolerans). Halüsinasyon edilmiş alıntı bu kontrolü geçemez.
    """
    norm_quote = _normalize_for_match(quote)
    norm_chunk = _normalize_for_match(chunk_text)
    if not norm_quote or not norm_chunk:
        return False
    if norm_quote in norm_chunk:
        return True
    matcher = difflib.SequenceMatcher(None, norm_quote, norm_chunk, autojunk=False)
    match = matcher.find_longest_match(0, len(norm_quote), 0, len(norm_chunk))
    return (match.size / len(norm_quote)) >= threshold


def _findings_balance_factor(positive_count: int, negative_count: int) -> float:
    """Olumlu/zayıflatan bulgu dengesini ölçülü bir skor çarpanına çevirir.

    Asimetriktir: zayıflatan bulgu fazlası daha güçlü ceza (en çok -%12), olumlu fazlası
    küçük ödül (en çok +%6). gap_severity zaten negatifleri kısmen yansıttığından çarpan
    bilinçli olarak ölçülü tutulur; amaç ana türetmeyi bozmadan bulgu dengesini de skora
    yansıtmaktır. Yalnızca grounded (kanıta bağlanmış) bulgular sayılır.
    """
    net = positive_count - negative_count
    if net >= 0:
        adjustment = min(0.06, 0.015 * net)
    else:
        adjustment = max(-0.12, 0.03 * net)
    return 1.0 + adjustment


def _derive_score(
    claim_strength: float | None,
    evidence_quality: float | None,
    gap_severity: int | None,
    positive_count: int = 0,
    negative_count: int = 0,
) -> float | None:
    """Nihai 0-100 skoru, modelin serbest sayısından DEĞİL, ayrık eksenlerden + bulgu
    dengesinden türetir.

    Serbest holistik skor 8B modelde tek bir değere (anchor) çöküyordu. Bunun yerine
    skor, modelin niteliksel analizinden sonra verdiği ayrık eksenlerden hesaplanır:

        taban = (claim_pct x evidence_pct) / 100        # "iddia ancak kanıt kadar değerli"
        skor  = taban x (1 - 0.10 x (gap_severity-1))    # zayıflık ciddiyeti skoru düşürür
                     x bulgu_dengesi_faktörü             # olumlu/zayıflatan bulgu dengesi

    gap_severity 1->faktör 1.0 (ceza yok) ... 5->faktör 0.6. Bulgu dengesi faktörü
    [0.88, 1.06] aralığında ölçülü etki eder. Böylece farklı kriterler belirgin biçimde
    farklı skorlar alır.
    """
    if claim_strength is None or evidence_quality is None:
        return None
    base = claim_strength * evidence_quality / 100.0
    severity = gap_severity if gap_severity is not None and 1 <= gap_severity <= 5 else 2
    factor = 1.0 - 0.10 * (severity - 1)
    balance = _findings_balance_factor(positive_count, negative_count)
    return round(max(0.0, min(100.0, base * factor * balance)), 2)


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coerce_confidence(value: Any) -> float:
    numeric = _coerce_float(value)
    if numeric is None:
        return 0.55
    if numeric > 1.0 and numeric <= 100.0:
        return round(numeric / 100.0, 2)
    if 0.0 <= numeric <= 1.0:
        return numeric
    return 0.55


def _coerce_decision_status(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() in {"scored", "insufficient_evidence"}:
        return value.strip().lower()
    return "scored"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
