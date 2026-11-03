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
    # ÖNEMLI: Alan sırası bilinçlidir. Önce niteliksel analiz (assessment, bulgular,
    # eksikler) üretilir; SONRA bu analize dayanan ayrık (1-5) puan eksenleri gelir.
    # Böylece model sayıyı gerekçeden önce vermez (anchor/mod-çöküşü kırılır). Nihai
    # 0-100 skor modelden ALINMAZ; bu eksenlerden provider'da deterministik türetilir.
    return {
        "type": "object",
        "properties": {
            "short_assessment": {"type": "string"},
            "justification": {"type": "string"},
            "positive_findings": {"type": "array", "items": finding_schema},
            "negative_findings": {"type": "array", "items": finding_schema},
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
            "claim_strength": {"type": "integer", "minimum": 1, "maximum": 5},
            "evidence_quality": {"type": "integer", "minimum": 1, "maximum": 5},
            "gap_severity": {"type": "integer", "minimum": 1, "maximum": 5},
            "score_rationale": {"type": "string"},
            "decision_status": {
                "type": "string",
                "enum": ["scored", "insufficient_evidence"],
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": [
            "short_assessment",
            "justification",
            "positive_findings",
            "negative_findings",
            "evidence_items",
            "claim_strength",
            "evidence_quality",
            "gap_severity",
            "score_rationale",
            "decision_status",
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
        "Kanıt zayıfsa veya eksikse bunu açıkça belirt. "
        "Önce niteliksel analizini (değerlendirme, bulgular, eksikler) yaz; SONRA puan "
        "eksenlerini (claim_strength, evidence_quality, gap_severity) bu analizine göre 1-5 arası ver. "
        "Bir kanıta atıf yaparken yalnızca kanıt numarasını (ref) kullan. "
        "Tüm metinleri Türkçe üret. JSON dışında hiçbir çıktı verme."
    )


def _build_user_prompt(
    criterion: EvaluationCriterion,
    evidence: CriterionEvidence,
    ranked: list[EvidenceChunk],
) -> str:
    schema = {
        "short_assessment": (
            "Bu önerinin kriteri ne ölçüde karşıladığını, kanıttan somut bir ayrıntıya "
            "(sayı, bölüm adı veya terim) dayanarak 1-2 cümlede söyle."
        ),
        "justification": (
            "Değerlendirmenin gerekçesini, hangi kanıtın iddiayı ne kadar desteklediğine atıfla 1-2 cümlede açıkla."
        ),
        "positive_findings": [
            {
                "summary": "Türkçe bulgu özeti",
                "reason": (
                    "Bu bulgunun kriteri NEDEN güçlendirdiğini açıkla: kanıttaki somut ayrıntıyı "
                    "(sayı, bölüm adı, terim) AKTAR, kriterin ne istediğiyle ilişkilendir ve bunun "
                    "değerlendirmeye etkisini söyle. 2-3 cümle, dolu ve açıklayıcı."
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
                    "Bu bulgunun kriteri NEDEN zayıflattığını açıkla: eksik/yetersiz olan somut ayrıntıyı "
                    "(hangi sayı, bölüm, kanıt eksik) AKTAR, kriterin ne istediğiyle ilişkilendir ve bunun "
                    "değerlendirmeye etkisini söyle. 2-3 cümle, dolu ve açıklayıcı."
                ),
                "quote": (
                    "Bu bulgunun dayandığı kanıttan BİREBİR kopyalanmış kısa ifade; "
                    "ref ile gösterdiğin [K#] kanıtının metnindeki kelimeleri DEĞİŞTİRME, parafraz ETME."
                ),
                "ref": "kanıt numarası (tam sayı)",
            }
        ],
        "evidence_items": [
            {
                "ref": "kanıt numarası (tam sayı)",
                "evidence_type": "positive | negative | context",
                "verbatim_excerpt": "Kısa, birebir veya çok yakın alıntı",
                "why_it_matters": "Türkçe açıklama",
            }
        ],
        "claim_strength": (
            "Yukarıdaki analizine göre iddianın gücü (1-5 TAM SAYI): "
            "5=çok net, iddialı ve kritere tam oturan iddia · 4=güçlü ama küçük boşluklar · "
            "3=makul ama kısmi · 2=zayıf/belirsiz · 1=iddia yok denecek kadar zayıf. "
            "Her kriter için bağımsız ve dürüst seç; otomatik 4-5 verme."
        ),
        "evidence_quality": (
            "Kanıtın somutluğu/doğrulanabilirliği (1-5 TAM SAYI): "
            "5=birden çok sayısal/doğrulanabilir veri (rakam, tablo, ölçüt) · 4=somut ama sınırlı · "
            "3=kısmen somut · 2=çoğunlukla genel ifade · 1=neredeyse hiç somut kanıt yok. "
            "Belgede bu kritere dair sayısal/somut veri yoksa 3'ten yukarı VERME."
        ),
        "gap_severity": (
            "Listelediğin zayıflık ve eksiklerin CİDDİYETİ (1-5 TAM SAYI): "
            "1=kayda değer eksik yok · 3=belirgin boşluklar var · 5=kritik eksikler skoru ciddi düşürmeli. "
            "negative_findings ile tutarlı olmalı."
        ),
        "score_rationale": (
            "Yukarıda verdiğin claim_strength, evidence_quality ve gap_severity değerlerine DAYANARAK "
            "bu kriterin neden bu düzeyde değerlendirildiğini 2-3 cümlede açıkla: iddianın gücü, kanıtın "
            "somutluğu ve eksiklerin etkisi nasıl birleşiyor? Kanıttan somut bir ayrıntıya değin; "
            "okuyucu puanın gerekçesini buradan net anlamalı."
        ),
        "decision_status": "scored | insufficient_evidence",
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
        "Puanlama yöntemi (KATI değerlendir; hakemler cömert değildir):\n"
        "- Nihai 0-100 skoru SEN vermezsin; o, senin verdiğin 1-5 eksenlerinden otomatik hesaplanır.\n"
        "- Bu yüzden eksenleri (claim_strength, evidence_quality, gap_severity) dürüst ve KRİTERE ÖZGÜ ver; "
        "her kritere refleksle aynı değeri (örn. hep 4-5) verme. Farklı kriterler farklı değerler almalı.\n"
        "- Çoğu gerçek öneride evidence_quality ve claim_strength 2-4 bandındadır; 5 yalnızca istisnai, "
        "somut sayısal kanıtla desteklenen durumlar içindir.\n\n"
        "Görev:\n"
        "- Önce başvuru sahibinin bu kriter için ne iddia ettiğini kanıtlardan çıkar.\n"
        "- ÖNCE zayıflıkları, boşlukları ve eksikleri belirle; bunların TAMAMINI negative_findings "
        "olarak çıkar (eksik bir bilgi de bir zayıflıktır). Eksenleri SONRA, bu analizine dayanarak ver. "
        "Zayıflık varsa gap_severity'yi yükselt.\n"
        "- Sonra iddiayı destekleyen kanıtın ne kadar güçlü olduğunu değerlendir.\n"
        "- Bir konu belgede gerçekten ele alınmamışsa bunu bir zayıflık say (gap_severity'ye yansıt). "
        "Ancak konu yalnızca farklı bir başlık adı veya bölüm numarası altında işlenmişse "
        "bunu eksiklik sayma; içerik mevcutsa normal değerlendir.\n"
        "- claim_strength, evidence_quality ve gap_severity'yi 1-5 TAM SAYI olarak, yukarıdaki "
        "seviye tanımlarına göre ver; SONRA score_rationale'da bu üç değere dayanarak puanın "
        "gerekçesini açıkça anlat.\n"
        "- Kanıt destekliyorsa en az 3, en fazla 6 olumlu ve 3-6 zayıflatan bulgu çıkar; "
        "ancak kanıtta gerçekten karşılığı olmayan bulgu UYDURMA. Kanıt sınırlıysa daha az bulgu çıkar. "
        "Çıkardığın olumlu ve zayıflatan bulguların dengesi nihai puana da yansır; bu yüzden her iki tarafı "
        "da dürüst ve eksiksiz çıkar.\n"
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
