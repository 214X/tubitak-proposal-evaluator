from __future__ import annotations

import json

from app.core.config import settings
from app.services.evaluation.models import CriterionEvidence, EvaluationCriterion, EvidenceChunk
from app.services.evaluation.retrieval import build_ranked_evidence


def build_judge_messages(
    criterion: EvaluationCriterion,
    evidence: CriterionEvidence,
) -> tuple[list[dict[str, str]], dict[int, str]]:
    """Hakem mesajlarını ve 1 tabanlı index -> chunk_id eşlemesini birlikte döndürür.

    Model artık uzun chunk_id'leri kopyalamak yerine yalnızca küçük tam sayı (ref)
    üretir. Eşleme bu fonksiyonda üretilir ki prompt'taki numara ile çözümleme
    tek kaynaktan gelsin.
    """
    ranked = build_ranked_evidence(evidence, limit=settings.judge_evidence_limit)
    index_to_chunk_id = {index: chunk.chunk_id for index, chunk in enumerate(ranked, start=1)}
    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": _build_user_prompt(criterion, evidence, ranked)},
    ]
    return messages, index_to_chunk_id


def build_json_retry_message() -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "Önceki yanıt geçerli JSON değildi veya istenen şemaya uymadı. "
            "Aynı değerlendirmeyi tekrar yap. "
            "Sadece geçerli JSON döndür. Markdown, açıklama veya kod bloğu ekleme."
        ),
    }


def build_judge_format_schema() -> dict:
    """Ollama structured outputs için JSON Schema.

    Model bu şemaya bağlı üretim yapar; geçersiz JSON, eksik alan, null skor veya
    'failed' gibi durumlar fiziksel olarak üretilemez. Atıflar tam sayı ref'tir.
    """
    finding_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "reason": {"type": "string"},
            "quote": {"type": "string"},
            "ref": {"type": "integer"},
        },
        "required": ["summary", "reason", "quote", "ref"],
    }
    return {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "claim_strength": {"type": "integer", "minimum": 0, "maximum": 100},
            "evidence_quality": {"type": "integer", "minimum": 0, "maximum": 100},
            "decision_status": {
                "type": "string",
                "enum": ["scored", "insufficient_evidence"],
            },
            "short_assessment": {"type": "string"},
            "justification": {"type": "string"},
            "positive_findings": {"type": "array", "items": finding_schema},
            "negative_findings": {"type": "array", "items": finding_schema},
            "missing_information": {"type": "array", "items": {"type": "string"}},
            "red_flags": {"type": "array", "items": {"type": "string"}},
            "evidence_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "integer"},
                        "evidence_type": {
                            "type": "string",
                            "enum": ["positive", "negative", "context"],
                        },
                        "verbatim_excerpt": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                    },
                    "required": ["ref", "evidence_type", "verbatim_excerpt", "why_it_matters"],
                },
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": [
            "score",
            "claim_strength",
            "evidence_quality",
            "decision_status",
            "short_assessment",
            "justification",
            "positive_findings",
            "negative_findings",
            "evidence_items",
            "confidence",
        ],
    }


def _build_system_prompt() -> str:
    return (
        "Sen proje önerilerini değerlendiren bir hakem yardımcısısın. "
        "Yalnızca sana verilen kanıtlara dayanarak karar ver. "
        "Dış bilgi veya genel kültür kullanma; kanıtta olmayan hiçbir şeyi uydurma. "
        "Değerlendirdiğin proje yalnızca aşağıdaki kanıtlarda anlatılan projedir; "
        "başka bir proje hayal etme. "
        "Başvuru sahibinin iddiasını ve bunu destekleyen kanıt gücünü ayrı değerlendir. "
        "Kanıt zayıfsa veya eksikse bunu açıkça belirt ve puanı buna göre düşür. "
        "Tüm puan alanlarını 0 ile 100 arasında ver. "
        "Bir kanıta atıf yaparken yalnızca kanıt numarasını (ref) kullan. "
        "Tüm metinleri Türkçe üret. JSON dışında hiçbir çıktı verme."
    )


def _build_user_prompt(
    criterion: EvaluationCriterion,
    evidence: CriterionEvidence,
    ranked: list[EvidenceChunk],
) -> str:
    schema = {
        "score": "0-100 arası tam sayı",
        "claim_strength": "0-100 arası tam sayı",
        "evidence_quality": "0-100 arası tam sayı",
        "decision_status": "scored | insufficient_evidence",
        "short_assessment": (
            "Bu önerinin kriteri ne ölçüde karşıladığını, kanıttan somut bir ayrıntıya "
            "(sayı, bölüm adı veya terim) dayanarak 1-2 cümlede söyle."
        ),
        "justification": (
            "Skorun gerekçesini, hangi kanıtın iddiayı ne kadar desteklediğine atıfla 1-2 cümlede açıkla."
        ),
        "positive_findings": [
            {
                "summary": "Türkçe bulgu özeti",
                "reason": (
                    "Bu bulgunun kriteri NEDEN güçlendirdiğini açıkla: kanıttaki somut ayrıntıya "
                    "(sayı, bölüm, terim) bağla ve kriterin ne istediğiyle ilişkilendir. 1-2 cümle."
                ),
                "quote": (
                    "Bu bulgunun dayandığı kanıttan BİREBİR kopyalanmış kısa ifade; "
                    "ref ile gösterdiğin [K#] kanıtının metnindeki kelimeleri DEĞİŞTİRME, parafraz ETME."
                ),
                "ref": "kanıt numarası (tam sayı)",
            }
        ],
        "negative_findings": [
            {
                "summary": "Türkçe bulgu özeti",
                "reason": (
                    "Bu bulgunun kriteri NEDEN zayıflattığını açıkla: kanıttaki somut ayrıntıya "
                    "(sayı, bölüm, terim) bağla ve kriterin ne istediğiyle ilişkilendir. 1-2 cümle."
                ),
                "quote": (
                    "Bu bulgunun dayandığı kanıttan BİREBİR kopyalanmış kısa ifade; "
                    "ref ile gösterdiğin [K#] kanıtının metnindeki kelimeleri DEĞİŞTİRME, parafraz ETME."
                ),
                "ref": "kanıt numarası (tam sayı)",
            }
        ],
        "missing_information": [
            "Eksik olan bilgi + bunun kriter açısından neden önemli olduğu + (belgede ilgili "
            "bölüm varsa) nereye eklenmesi gerektiği (örn. 'Kalem bazlı bütçe dayanağı yok; "
            "kriter maliyet-etkinliği sorduğu için bu boşluk skoru düşürüyor; B.2 bütçe bölümüne eklenmeli')."
        ],
        "red_flags": ["Türkçe risk işareti"],
        "evidence_items": [
            {
                "ref": "kanıt numarası (tam sayı)",
                "evidence_type": "positive | negative | context",
                "verbatim_excerpt": "Kısa, birebir veya çok yakın alıntı",
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
        f"- skor_aralığı: {criterion.score_min}-{criterion.score_max}\n\n"
        f"Değerlendirilen proje bağlamı (bağlamı kaybetme, yalnızca bu projeyi değerlendir):\n"
        f"{_build_project_anchor(ranked)}\n\n"
        f"Kapsama durumu: {evidence.coverage_status}\n"
        f"Kapsama notları:\n{_format_note_block(evidence.coverage_notes)}\n\n"
        f"Kanıtlar (atıf yaparken yalnızca [K#] numarasını ref olarak kullan):\n"
        f"{_format_ranked_evidence_block(ranked)}\n\n"
        "Puanlama rehberi (KATI değerlendir; hakemler cömert değildir):\n"
        "- 0-19: İddia yok veya kanıt yok denecek kadar zayıf.\n"
        "- 20-39: İddia var ama ciddi ölçüde eksik, soyut veya kanıtsız.\n"
        "- 40-59: Kısmi iddia ve sınırlı kanıt; ikna gücü düşük. ÇOĞU ÖNERİ BURADADIR.\n"
        "- 60-79: Makul/güçlü iddia ama hâlâ belirgin boşluklar mevcut; iyi öneriler buraya girer.\n"
        "- 80-100: YALNIZCA kusursuz, somut sayısal/doğrulanabilir kanıtla desteklenen istisnai iddia. Nadir kullan.\n"
        "- Kanıtta herhangi bir boşluk, belirsizlik veya doğrulanamayan iddia varsa 70 ÜSTÜ VERME.\n\n"
        "Görev:\n"
        "- Önce başvuru sahibinin bu kriter için ne iddia ettiğini kanıtlardan çıkar.\n"
        "- ÖNCE zayıflıkları, boşlukları ve eksikleri belirle (negative_findings + missing_information); "
        "SONRA bunları yansıtan bir skor ver. Zayıflıkları görmeden skoru yüksek tutma.\n"
        "- Sonra bu iddiayı destekleyen kanıtın ne kadar güçlü olduğunu değerlendir.\n"
        "- Kanıttaki boşlukları, eksikleri ve iddiayı zayıflatan unsurları açıkla.\n"
        "- claim_strength: iddianın ne kadar net ve iddialı olduğu. evidence_quality: bu iddiayı destekleyen "
        "kanıtın somutluğu ve doğrulanabilirliği. İKİSİNİ DE KATI puanla; belgede somut sayı/veri yoksa "
        "evidence_quality için 60 üstü verme.\n"
        "- Bir konu belgede gerçekten ele alınmamışsa bunu puanı düşüren bir zayıflık say. "
        "Ancak konu yalnızca farklı bir başlık adı veya bölüm numarası altında işlenmişse "
        "bunu eksiklik sayma; içerik mevcutsa normal değerlendir.\n"
        "- score, claim_strength ve evidence_quality alanlarını 0-100 aralığında ver.\n"
        "- Kanıt destekliyorsa en az 3, en fazla 6 olumlu ve 3-6 zayıflatan bulgu çıkar; "
        "ancak kanıtta gerçekten karşılığı olmayan bulgu UYDURMA. Kanıt sınırlıysa daha az bulgu çıkar.\n"
        "- Her bulgu için 'quote' alanına, ref ile gösterdiğin kanıtın metninden BİREBİR kısa bir ifade "
        "kopyala (parafraz değil). Birebir alıntı veremiyorsan o bulguyu hiç çıkarma.\n"
        "- Her bulgu ve kanıt için yalnızca yukarıdaki listede gerçekten var olan bir [K#] "
        "numarasını ref olarak kullan; numara uydurma.\n"
        "- evidence_items alanında yalnızca gerçekten kullandığın kanıtları ekle.\n"
        "- JSON dışında hiçbir çıktı verme.\n\n"
        f"Bu tam JSON şemasına uyarak cevap ver:\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )


def _build_project_anchor(ranked: list[EvidenceChunk]) -> str:
    if not ranked:
        return "- (kanıt bulunamadı)"
    top = ranked[0]
    heading = " > ".join(top.heading_path_titles) if top.heading_path_titles else "Belirsiz başlık"
    snippet = " ".join(top.text_for_embedding.split())
    if len(snippet) > 250:
        snippet = f"{snippet[:247].rstrip()}..."
    return f"- Bölüm: {heading}\n- Özet: {snippet}"


def _format_note_block(notes: list[str]) -> str:
    if not notes:
        return "- yok"
    return "\n".join(f"- {item}" for item in notes)


def _format_ranked_evidence_block(ranked: list[EvidenceChunk]) -> str:
    if not ranked:
        return "- yok"

    char_limit = settings.judge_evidence_char_limit
    lines: list[str] = []
    for index, item in enumerate(ranked, start=1):
        heading_path = (
            " > ".join(item.heading_path_titles) if item.heading_path_titles else "Belirsiz başlık"
        )
        page_text = _format_page_range(item.page_start, item.page_end)
        text = " ".join(item.text_for_embedding.split())
        if len(text) > char_limit:
            text = f"{text[: char_limit - 3].rstrip()}..."
        lines.append(
            f"[K{index}] [type={item.chunk_type}] [path={heading_path}] [pages={page_text}]\n{text}"
        )
    return "\n\n".join(lines)


def _format_page_range(page_start: int | None, page_end: int | None) -> str:
    if page_start is None and page_end is None:
        return "n/a"
    if page_start == page_end:
        return str(page_start)
    return f"{page_start}-{page_end}"
