# Rapor Zenginleştirme Planı (Süre-Nötr Çekirdek)

## Amaç

Kriter değerlendirme raporunu zenginleştirmek:
- **Daha çok kanıt** ve **daha çok açıklama** göster.
- Kullanıcı **nerede, nasıl eksiklik** olduğunu daha net görsün.
- Olumlu/olumsuz **bulgu miktarı artsın**; analiz eksiksiz, her iddia daha çok desteklenmiş olsun.

İki sert kısıt:
1. **Süre çok uzamasın** (sample.pdf şu an ~15 dk; judge yerel `aya-expanse:8b`, sıralı, üretim süresi ≈ çıktı token sayısı).
2. **Halüsinasyon olmasın** — eklenen her şey yapısal olarak kanıta bağlı olmalı.

## Kararlar (bu oturumda netleşti)

- **Kapsam:** Süre-nötr çekirdek = **O1 + O2 + O3 + O4 + O6**.
- **Dışarıda:** O5 (muhakeme/analysis alanı — net token ekler), O7 (rapor yönetici özeti), O8 (paralelleştirme — seri tasarım + tek GPU + canlı ilerleme akışını bozar, gerçek kazanç yok).
- **Doğrulama politikası:** Bir bulgunun alıntısı atıf yaptığı chunk'ta doğrulanamazsa **bulgu düşürülür** (en katı anti-halüsinasyon).

## Çerçeve: denge üçgeni ve net-token argümanı

Miktar↑ + Açıklama↑ doğal olarak token↑ = süre↑ demek. Süre↓ + halüsinasyon↓ ile çelişir. Çözüm iki ayaklı:

1. **Bedava/deterministik miktar** (O1): retrieval'ın zaten getirdiği kanıtı raporda sergile — model üretmiyor, dolayısıyla ne süre ne halüsinasyon maliyeti var.
2. **Yapısal güvenceli model çıktısı** (O2+O3): bulgu sayısını artır ama her bulguyu birebir alıntı + doğrulama ile kanıta bağla; doğrulanmayanı düş.

**Net-token (süre) argümanı:** Önceki adımda `criterion_explanation` modelden alınıp statikleştirildi (rubric `ui_explanation`). Bu, kriter başına tam bir üretilen metin alanını kaldırdı. Bu kazanılan bütçe; O2'nin kısa alıntılarını ve O3'ün birkaç ek bulgusunu **finanse eder**. O4 bu disiplini korur (yeni serbest-metin alanı eklenmez, mevcut açıklamalar 1-2 cümle ile sınırlı kalır). Sonuç: çıktı **daha grounded ve daha çok bulgulu**, net süre **~sabit**.

---

## Detaylı Uygulama

### O2 — Alıntı + doğrulama (halüsinasyon omurgası)

Amaç: her bulgu, dayandığı kanıttan **birebir kopyalanmış** kısa bir alıntı taşısın; backend bu alıntının gerçekten o chunk'ta geçtiğini doğrulasın; geçmiyorsa bulguyu düşür.

**1. Schema** — `prompt_builder.build_judge_format_schema()`, `finding_schema`:
- `quote` alanı ekle: `"quote": {"type": "string"}`; `required`'a `"quote"` ekle.
- Sonuç: `finding_schema` = `summary, reason, quote, ref` (hepsi zorunlu). Model her bulguda alıntı üretmek zorunda.

**2. Prompt** — `prompt_builder._build_user_prompt()` içindeki `schema` dict, `positive_findings`/`negative_findings` örneklerine:
```python
"quote": "Bu bulgunun dayandığı kanıttan BİREBİR kopyalanmış kısa ifade; chunk metnindeki kelimeleri değiştirme, parafraz etme.",
```

**3. Model** — `models.py`, `CriterionFinding`:
- `quote: str | None = None` ekle.
- Mevcut `validate_reason_direction` validator'ı korunur. `quote` opsiyonel default'lu olduğu için geçmiş payload'ları kırmaz (legacy migration validator'ları etkilenmez).

**4. Provider doğrulama** — `provider._resolve_findings()`:
- Her item için `quote = _clean_text(item.get("quote"))` oku.
- Atıf yapılan chunk `resolve(item.get("ref"))` ile zaten elde ediliyor.
- **Doğrula:** `_quote_is_grounded(quote, chunk.text_for_embedding)`:
  - Normalize: whitespace collapse + casefold + Türkçe diakritik düşürme (retrieval'daki `_normalize_text` mantığı yeniden kullanılabilir).
  - Önce substring kontrolü (normalize edilmiş alıntı, normalize edilmiş chunk içinde geçiyor mu).
  - Geçmiyorsa `difflib.SequenceMatcher` ile en iyi eşleşen blok oranı **≥ 0.85** ise grounded say (küçük modelin ufak biçim sapmalarına tolerans).
- **Politika (düşür):** `quote` boşsa VEYA grounded değilse → **bulguyu listeye ekleme** (`continue`). Böylece kanıta bağlanamayan iddia rapora hiç girmez.
- Grounded ise finding dict'ine `"quote": quote` ekle.

**5. Evidence_items için tamamlayıcı politika** — `provider._resolve_evidence_items()`:
- Burada chunk_id zaten ref ile yapısal doğru; amaç bulgu değil kanıt göstermek. Bu yüzden **düşürme yerine düzelt:** modelin `verbatim_excerpt`'i chunk'ta doğrulanamıyorsa, excerpt'i chunk'ın **kendi metniyle** (`_summarize_chunk_text`) değiştir. Böylece gösterilen alıntı her zaman gerçek belgeyle birebir olur.

**6. Frontend** — `EvaluationPanel.tsx`, `FindingPanel`:
- `frontend/lib/analysis.ts` finding tipine `quote?: string | null` ekle.
- Bulguda `reason` altında, mevcut `findingQuote` bloğu zaten kırpılmış kanıt alıntısı gösteriyor; artık modelin **doğrulanmış birebir alıntısını** (finding.quote) tercih et, yoksa eski `evidence.verbatim_excerpt`'e düş.

Maliyet: alıntılar kısa → düşük token. Halüsinasyon: doğrulanmayan bulgu rapora **giremez**.

### O3 — Sınırlı bulgu artışı

`prompt_builder._build_user_prompt()` "Görev" bloğundaki bulgu-sayısı dürtüsü:
- Mevcut: "en az 2, en fazla 4 olumlu ve 2-4 zayıflatan bulgu".
- Yeni: **"en az 3, en fazla 6 olumlu ve 3-6 zayıflatan bulgu"**; "UYDURMA" ve "kanıt sınırlıysa daha az" cümleleri korunur.
- Güvenlik: O2 doğrulaması ungrounded bulguları düşürdüğü için 6'ya itmek risksiz — model uydurursa o bulgu zaten elenir, net sonuç "kanıtla desteklenebilen kadar bulgu" olur.

Maliyet: birkaç ek bulgu = ılımlı token; O4 bütçesiyle dengelenir.

### O4 — Token disiplini (süre-nötr koruma)

Bu bir "guard", yeni kod değil:
- `criterion_explanation` zaten statik (önceki adım) → kriter başına bir üretilen alan kalktı; bu bütçe O2+O3'ü finanse eder.
- `short_assessment` ve `justification` prompt tariflerindeki **"1-2 cümle"** sınırları korunur; yeni serbest-metin alanı **eklenmez** (O5 bilinçli dışarıda).
- Plan sırasında token bütçesi izlenir: O3'ün ek bulguları + O2'nin alıntıları, kaldırılan `criterion_explanation` üretiminin kabaca yerini almalı.

### O1 — Deterministik kanıt sergileme (frontend-only, bedava)

`CriterionEvaluationResult` zaten `primary_section_chunks`, `semantic_support_chunks`, `fallback_context_chunks` (her biri `EvidenceChunk`: `chunk_type`, `heading_path_titles`, `page_start/end`, `text_for_embedding`) taşıyor ve bu listeler frontend'e gidiyor. Yani **backend değişikliği gerekmez**.

`EvaluationPanel.tsx` kriter kartında yeni bölüm: **"İncelenen Kanıtlar (N)"**:
- Üç listeyi `chunk_id` ile dedupe + tier sırasıyla (primary > semantic > fallback) birleştir (retrieval'daki `build_ranked_evidence` mantığının frontend karşılığı; basit sıralama yeterli).
- Her kanıt için: **tür rozeti** (📊 Tablo / • Liste / ❓ Soru-Cevap / ¶ Anlatı — `chunk_type`'tan) + heading path + sayfa + kırpılmış `text_for_embedding`.
- Modelin doğrudan atıf yaptığı (evidence_items / finding chunk_id'leri) kanıtları "✓ modelce kullanıldı" rozetiyle işaretle; gerisi "bağlam" olarak görünür.
- `frontend/lib/analysis.ts`: `CriterionEvaluationResult` tipinde bu chunk listelerinin var olduğundan emin ol (yoksa ekle).

Etki: görünür kanıt miktarı katlanır, **sıfır model süresi, sıfır halüsinasyon** (birebir getirilen belge metni). Provenance ("ne nereden geliyor") tür rozeti + heading + sayfa ile keskinleşir.

### O6 — Eksik-bilgi keskinleştirme ("nerede eksik" lever'ı)

`prompt_builder._build_user_prompt()` `schema` dict, `missing_information` tarifi (string listesi kalır, şema değişmez):
- Yeni format: **"Ne eksik + bunun kriter açısından neden önemli olduğu + (belgede ele alınmışsa) hangi bölüme eklenmesi gerektiği."**
- Örn: "Bütçe gerekçelendirmesi yok; kriter maliyet-etkinliği sorduğu için bu boşluk skoru düşürüyor; B.2 bütçe bölümüne kalem bazlı dayanak eklenmeli."
- "Görev" bloğuna kısa dürtü: eksikleri somut ve kriterle bağlı yaz; genel-geçer ifade kullanma.

Maliyet: madde başına ılımlı token; bütçe içinde.

---

## Dokunulacak Dosyalar

| Dosya | Yer | Değişiklik | Maliyet |
|---|---|---|---|
| `prompt_builder.py` | `build_judge_format_schema` `finding_schema` | `quote` alanı + required | — |
| `prompt_builder.py` | `_build_user_prompt` schema dict | findings `quote` tarifi; `missing_information` keskinleştirme | düşük token |
| `prompt_builder.py` | `_build_user_prompt` "Görev" bloğu | bulgu sayısı 2-4 → 3-6; eksik-bilgi dürtüsü | ılımlı token |
| `models.py` | `CriterionFinding` | `quote: str \| None = None` | — |
| `provider.py` | `_resolve_findings` | alıntı oku + doğrula + ungrounded → düşür | sıfır model |
| `provider.py` | `_resolve_evidence_items` | excerpt doğrulanamazsa chunk metniyle değiştir | sıfır model |
| `provider.py` | yeni helper | `_quote_is_grounded` (normalize + substring + difflib ≥0.85) | sıfır model |
| `frontend/lib/analysis.ts` | finding + result tipleri | `quote?`; chunk listelerinin tip varlığı | — |
| `EvaluationPanel.tsx` | `FindingPanel` | doğrulanmış `quote` göster | sıfır |
| `EvaluationPanel.tsx` | kriter kartı | "İncelenen Kanıtlar" bölümü + tür rozetleri | sıfır model |

## Değişmeyen / Korunan Guard'lar

- **Index-tabanlı atıf** (ref→chunk_id; geçersiz ref düşer) — chunk_id halüsinasyonu yapısal imkânsız; korunur.
- **Uncited guard** (evidence_items boşsa top-3 otomatik doldur + skor 65 cap) — korunur; O2 ile çatışmaz.
- **Salvage** ve `_build_salvaged_result` — korunur.
- **Harmanlanmış skor** (`_blend_score` = 0.5×model + 0.5×claim×evidence/100) — korunur.
- **Coverage penalty** (-15 missing) — korunur.
- **Statik `criterion_explanation`** (rubric `ui_explanation`) — korunur.
- `build_judge_format_schema`'nın `required` listesine yalnızca `finding_schema` içine `quote` eklenir; ana şemaya yeni zorunlu alan **eklenmez** (8B modeli halüsinasyona itmemek için).

## Halüsinasyon Garanti Modeli

- **Bulgular:** her bulgu birebir alıntı taşır; alıntı atıf yapılan chunk'ta doğrulanmazsa bulgu **rapora girmez**. → model uyduramaz.
- **Evidence_items:** chunk_id ref ile yapısal doğru; excerpt doğrulanamazsa **gerçek chunk metniyle değiştirilir**. → gösterilen alıntı her zaman belgeyle birebir.
- **İncelenen Kanıtlar (O1):** tamamen retrieval çıktısı; model hiç dokunmaz. → sıfır halüsinasyon.
- **Eksik-bilgi (O6):** model üretir ama kriterle ve belgeyle bağ ister; serbest iddia değil.

## Süre Modeli (neden ~nötr)

- **+** O3 ek bulgular, O2 alıntıları, O6 daha uzun eksik-bilgi → token artışı.
- **−** Statik `criterion_explanation` (üretilmiyor), O5 yok, yeni serbest-metin alanı yok, 1-2 cümle cap'leri.
- **0** O1 ve doğrulama tamamen deterministik (model süresi yok).
- Beklenti: kriter başına çıktı token'ı kabaca sabit; toplam ~15 dk korunur. Plan uygulanırken bir kriterde önce/sonra token ölçülerek doğrulanır.

## Doğrulama Adımları

1. **Backend import/syntax:** `provider.py`, `prompt_builder.py`, `models.py`, `service.py` import OK; `build_judge_format_schema()['properties']['positive_findings']['items']['required']` içinde `quote` var.
2. **Doğrulama birim testi:** `_quote_is_grounded` için pozitif (birebir alıntı), negatif (uydurma alıntı), tolerans (ufak biçim sapması) senaryoları.
3. **Tek kriter uçtan uca:** `aya-expanse:8b` ile bir alt kriter; `evaluation_state.json`'da kontrol: bulgular `quote` taşıyor mu, ungrounded bulgu düşmüş mü, bulgu sayısı kanıt varken 3-6 bandında mı, missing_information kriter-bağı + konum söylüyor mu.
4. **Frontend typecheck:** `frontend/` tsc; yeni `quote` ve "İncelenen Kanıtlar" referansları çözülmeli.
5. **Görsel:** o session'ı panelde aç — doğrulanmış alıntılar, tür rozetleri, "İncelenen Kanıtlar" bölümü, "✓ modelce kullanıldı" işareti görünüyor mu; salvaged/kanıtsız kriter hatasız boş-durum gösteriyor mu.
6. **Süre kontrolü:** bir kriterde değişiklik öncesi/sonrası üretilen token ~aynı bandda mı (esas artış O3'ten, statik açıklama kazancıyla dengeli).
