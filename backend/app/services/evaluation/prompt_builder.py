from __future__ import annotations

import json

from app.services.evaluation.models import CriterionEvidence, EvaluationCriterion


def build_judge_messages(
    criterion: EvaluationCriterion,
    evidence: CriterionEvidence,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": _build_user_prompt(criterion, evidence)},
    ]


def build_json_retry_message() -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "Önceki yanıt geçerli JSON değildi veya istenen şemaya uymadı. "
            "Aynı değerlendirmeyi tekrar yap. "
            "Sadece geçerli JSON döndür. Markdown, açıklama veya kod bloğu ekleme."
        ),
    }


def _build_system_prompt() -> str:
    return (
        "Sen proje önerilerini değerlendiren bir hakem yardımcısısın. "
        "Yalnızca verilen kanıtlara dayanarak karar ver. "
        "Dış bilgi kullanma. Eksik bilgileri uydurma. "
        "Başvuru sahibinin iddiasını ve bunu destekleyen kanıt gücünü ayrı değerlendir. "
        "Kanıt zayıfsa veya eksikse bunu açıkça belirt. "
        "0 ile 5 arasında skor ver. "
        "Tüm alanları Türkçe üret. "
        "JSON dışında hiçbir çıktı verme."
    )


def _build_user_prompt(
    criterion: EvaluationCriterion,
    evidence: CriterionEvidence,
) -> str:
    schema = {
        "criterion_id": "string",
        "main_dimension_id": "string",
        "title": "string",
        "score": "0.0-5.0 veya null",
        "claim_strength": "0.0-5.0 veya null",
        "evidence_quality": "0.0-5.0 veya null",
        "decision_status": "scored | insufficient_evidence | failed",
        "criterion_explanation": "Türkçe kısa açıklama",
        "short_assessment": "Türkçe kısa değerlendirme",
        "justification": "Türkçe kısa gerekçe",
        "positive_findings": [
            {
                "summary": "Türkçe bulgu özeti",
                "why_positive": "Bu bulgunun iddiayı neden güçlendirdiği",
                "chunk_id": "string",
            }
        ],
        "negative_findings": [
            {
                "summary": "Türkçe bulgu özeti",
                "why_negative": "Bu bulgunun iddiayı neden zayıflattığı",
                "chunk_id": "string",
            }
        ],
        "missing_information": ["Türkçe eksik bilgi"],
        "red_flags": ["Türkçe risk işareti"],
        "evidence_items": [
            {
                "chunk_id": "string",
                "evidence_type": "positive | negative | context",
                "verbatim_excerpt": "Kısa, birebir veya çok yakın alıntı",
                "heading_path": ["string"],
                "page_start": "integer veya null",
                "page_end": "integer veya null",
                "why_it_matters": "Türkçe açıklama",
            }
        ],
        "confidence": "0.0 ile 1.0 arasında sayı",
    }

    return (
        f"Kriter:\n"
        f"- id: {criterion.criterion_id}\n"
        f"- ana_boyut: {criterion.main_dimension_id}\n"
        f"- başlık: {criterion.title}\n"
        f"- soru: {criterion.question}\n"
        f"- açıklama: {criterion.description}\n"
        f"- ağırlık: {criterion.weight}\n"
        f"- skor_aralığı: {criterion.score_min}-{criterion.score_max}\n\n"
        "Puanlama rehberi:\n"
        "- 0: İddia yok veya kanıt yok denecek kadar zayıf.\n"
        "- 1: İddia var ama ciddi ölçüde eksik, soyut veya kanıtsız.\n"
        "- 2: Kısmi iddia ve sınırlı kanıt var; ikna gücü düşük.\n"
        "- 3: Makul iddia ve orta düzey kanıt var; bazı boşluklar mevcut.\n"
        "- 4: Güçlü iddia ve iyi düzeyde kanıt var; küçük eksikler mevcut.\n"
        "- 5: Çok güçlü, açık ve iyi kanıtlanmış iddia.\n\n"
        f"Coverage durumu: {evidence.coverage_status}\n"
        f"Coverage notları:\n{_format_note_block(evidence.coverage_notes)}\n\n"
        f"Primary section chunks:\n{_format_evidence_block(evidence.primary_section_chunks)}\n\n"
        f"Semantic support chunks:\n{_format_evidence_block(evidence.semantic_support_chunks)}\n\n"
        f"Fallback context chunks:\n{_format_evidence_block(evidence.fallback_context_chunks)}\n\n"
        "Görev:\n"
        "- Önce başvuru sahibinin bu kriter için ne iddia ettiğini çıkar.\n"
        "- Sonra bu iddiayı destekleyen kanıtın ne kadar güçlü olduğunu değerlendir.\n"
        "- Kanıttaki boşlukları, eksikleri ve iddiayı zayıflatan unsurları açıkla.\n"
        "- Score, claim_strength ve evidence_quality alanlarını 0-5 aralığında ver.\n"
        "- Coverage missing veya kanıt çok zayıf ise decision_status alanını insufficient_evidence yap ve skorları null bırakabilirsin.\n"
        "- Sadece verilen chunk_id değerlerini kullan.\n"
        "- evidence_items alanında yalnızca gerçekten kullandığın kanıtları ekle.\n"
        "- evidence_type değeri sadece positive, negative veya context olabilir.\n"
        "- JSON dışında hiçbir çıktı verme.\n\n"
        f"Bu tam JSON şemasına uyarak cevap ver:\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )


def _format_note_block(notes: list[str]) -> str:
    if not notes:
        return "- yok"
    return "\n".join(f"- {item}" for item in notes)


def _format_evidence_block(evidence_items) -> str:
    if not evidence_items:
        return "- none"

    lines: list[str] = []
    for index, item in enumerate(evidence_items, start=1):
        heading_path = " > ".join(item.heading_path_titles) if item.heading_path_titles else "Belirsiz başlık"
        page_text = _format_page_range(item.page_start, item.page_end)
        lines.append(
            f"{index}. [chunk_id={item.chunk_id}] [type={item.chunk_type}] "
            f"[path={heading_path}] [pages={page_text}] [similarity={item.similarity_score:.4f}] "
            f"{item.text_for_embedding}"
        )
    return "\n".join(lines)


def _format_page_range(page_start: int | None, page_end: int | None) -> str:
    if page_start is None and page_end is None:
        return "n/a"
    if page_start == page_end:
        return str(page_start)
    return f"{page_start}-{page_end}"
