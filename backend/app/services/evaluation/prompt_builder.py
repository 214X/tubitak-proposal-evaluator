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


def _build_system_prompt() -> str:
    return (
        "Sen proje önerilerini değerlendiren bir hakem yardımcısısın. "
        "Yalnızca verilen kanıtlara dayanarak karar ver. "
        "Dış bilgi kullanma. Eksik bilgileri uydurma. "
        "Olumsuz veya çelişen kanıtları açıkça hesaba kat. "
        "Tüm çıktı alanlarını Türkçe üret. "
        "Sadece geçerli JSON döndür."
    )


def _build_user_prompt(
    criterion: EvaluationCriterion,
    evidence: CriterionEvidence,
) -> str:
    supporting_lines = _format_evidence_block(evidence.supporting_evidence)
    contradicting_lines = _format_evidence_block(evidence.contradicting_evidence)
    schema = {
        "score": "3 or -1 or null",
        "confidence": "0.0 ile 1.0 arasında sayı",
        "decision_status": "scored | insufficient_evidence | conflicting_evidence",
        "justification": "Türkçe kısa gerekçe",
        "supporting_chunk_ids": ["string"],
        "contradicting_chunk_ids": ["string"],
        "missing_information": ["Türkçe eksik bilgi"],
        "red_flags": ["Türkçe risk işareti"],
        "supporting_evidence_notes": [
            {
                "chunk_id": "string",
                "location_summary": "Belgenin hiyerarşik konumunu Türkçe özetle",
                "evidence_text": "Bu kanıtın metin içeriğini kısa ve anlaşılır biçimde Türkçe aktar",
                "why_it_matters": "Bu içeriğin neden lehte kanıt olduğunu Türkçe açıkla",
            }
        ],
        "contradicting_evidence_notes": [
            {
                "chunk_id": "string",
                "location_summary": "Belgenin hiyerarşik konumunu Türkçe özetle",
                "evidence_text": "Bu kanıtın metin içeriğini kısa ve anlaşılır biçimde Türkçe aktar",
                "why_it_matters": "Bu içeriğin neden aleyhte kanıt olduğunu Türkçe açıkla",
            }
        ],
    }
    return (
        f"Kriter:\n"
        f"- id: {criterion.criterion_id}\n"
        f"- kategori: {criterion.category}\n"
        f"- başlık: {criterion.title}\n"
        f"- açıklama: {criterion.description}\n"
        f"- izinli_skorlar: {criterion.allowed_scores}\n"
        f"- ağırlık: {criterion.weight}\n\n"
        f"Lehte kanıtlar:\n{supporting_lines}\n\n"
        f"Aleyhte kanıtlar:\n{contradicting_lines}\n\n"
        "Talimatlar:\n"
        "- Kararını yalnızca yukarıdaki kanıtlara dayandır.\n"
        "- Aleyhte kanıtlar açık biçimde daha güçlü ise skor -1 ver.\n"
        "- Lehte kanıtlar yeterliyse ve ciddi bir çelişki yoksa skor 3 ver.\n"
        "- Kanıt yetersizse decision_status alanını insufficient_evidence yap ve score alanını null ver.\n"
        "- Güçlü bir çelişki çözülemiyorsa decision_status alanını conflicting_evidence yap.\n"
        "- Sadece yukarıda verilen chunk id'lerini kullan.\n"
        "- justification, missing_information, red_flags ve kanıt notlarının tamamı Türkçe olsun.\n"
        "- supporting_evidence_notes ve contradicting_evidence_notes alanlarında yalnızca gerçekten kullandığın kanıtları özetle.\n"
        "- evidence_text alanında ham chunk metnini aynen kopyalama; belge içeriğini kısa, doğal ve anlaşılır Türkçe ile özetle.\n"
        "- why_it_matters alanında bu kanıtın neden ilgili kritere etki ettiğini açıkla.\n\n"
        f"Bu tam JSON şemasına uyarak cevap ver:\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )


def _format_evidence_block(evidence_items) -> str:
    if not evidence_items:
        return "- none"

    lines: list[str] = []
    for index, item in enumerate(evidence_items, start=1):
        heading_path = " > ".join(item.heading_path_titles) if item.heading_path_titles else "Belirsiz başlık"
        page_text = _format_page_range(item.page_start, item.page_end)
        lines.append(
            f"{index}. [chunk_id={item.chunk_id}] [type={item.chunk_type}] [path={heading_path}] "
            f"[pages={page_text}] [similarity={item.similarity_score:.4f}] {item.text_for_embedding}"
        )
    return "\n".join(lines)


def _format_page_range(page_start: int | None, page_end: int | None) -> str:
    if page_start is None and page_end is None:
        return "n/a"
    if page_start == page_end:
        return str(page_start)
    return f"{page_start}-{page_end}"
