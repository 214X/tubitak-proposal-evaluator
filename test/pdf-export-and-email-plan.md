# PDF Rapor İndirme + Mail Bildirim Sistemi — Entegre Plan

## Çalıştırma sırası ve bağımlılık

> **ÖNEMLİ:** Bu plan, `plans/report-enrichment.md` planından **SONRA** çalıştırılacaktır.
> PDF çıktısı ve maille gönderilen rapor, o plandaki zenginleştirmeleri **de içermek
> zorundadır**: bulgu `quote` alanları, "İncelenen Kanıtlar" bölümü ve keskinleştirilmiş
> `missing_information`. PDF template'i bu alanları render etmelidir.

## Amaç

İki özelliği **tek bir entegre PDF üreteci** etrafında birlikte ekliyoruz:

1. **PDF İndir butonu** — Rapor ekranında "Belge Kanıtı" sayısının **sağında** yeni buton.
   Tıklayınca UI'mıza **çok benzeyen**, raporun **içerdiği her şeyi** kapsayan bir PDF üretip
   indirir.
2. **Mail bildirim sistemi** — Kullanıcı değerlendirmeyi başlatmadan önce o ekranda mail
   adresi girer. Değerlendirme tamamlandığı anda, **sekme kapalı olsa bile**, o adrese
   rapor (PDF ekli) gönderilir.

## Temel mimari karar: TEK sunucu-taraflı PDF üreteci

İki özelliğin ortak çekirdeği budur.

- **Neden sunucu tarafı:** Mail, kullanıcı sekmeyi kapatsa bile gönderilmeli. Yani PDF
  tarayıcı olmadan, sunucuda headless üretilebilmeli. Download butonu ile mailin ekindeki
  PDF'in **birebir aynı** olması için ikisi de **tek üreteci** paylaşmalı (drift olmaz).
- **Motor seçimi:** **WeasyPrint** (saf-Python, offline çalışır, iyi CSS desteği). Projenin
  offline/yerel doğasına uyar (torch/docling zaten ağır; Chromium eklemekten kaçınılır).
  - *Alternatif (daha yüksek sadakat, daha ağır):* Playwright + headless Chromium ile
    gerçek Next.js print route'unu render etmek pixel-perfect benzerlik verir ama Chromium
    bağımlılığı + frontend'in çalışıyor olması + session auth gerektirir. WeasyPrint sadakati
    yetersiz kalırsa fallback olarak değerlendirilir.
- **Veri kaynağı:** `EvaluationState.final_report` — UI'ın okuduğu **aynı** veri. Bu, PDF'in
  "her şeyi içerdiği" garantisini yapısal olarak sağlar (ayrı bir veri yolu yok).

---

## Backend Değişiklikleri

### 1. Bağımlılıklar (`backend/requirements.txt`)
- `weasyprint` (HTML+CSS → PDF)
- `jinja2` (HTML template)
- Mail için ek bağımlılık **yok** — stdlib `smtplib` + `email.message` yeterli.

### 2. PDF üreteç modülü — `app/services/reporting/pdf_renderer.py`
- `render_report_pdf(report: EvaluationReport) -> bytes`
- Jinja2 template: `app/services/reporting/templates/report.html` + `report.css`
  (CSS, `frontend/.../evaluation-panel.module.css`'ten uyarlanır → görsel benzerlik).
- **Template UI ile birebir bölümler (eksiksiz):**
  - Hero: Genel Skor + **Belge Kanıtı sayısı** (UI'daki heroCard).
  - Ana Boyut Skorları kartları (A/B/C, ağırlık + skor).
  - Rubric Detayı tablosu (kriter, ağırlık, kaynak bölümler, puan aralığı).
  - Her alt kriter kartı:
    - Kriterin beklentisi (`criterion_explanation` — statik).
    - Değerlendirme (`short_assessment`) + Gerekçe (`justification`).
    - Skor / `claim_strength` / `evidence_quality` göstergeleri.
    - Olumlu / olumsuz bulgular — özet + reason + **`quote` (enrichment)**.
    - Eksik bilgi (`missing_information` — keskinleştirilmiş) + Red flags.
    - Kanıt kartları (`evidence_items`): tür + heading + sayfa + alıntı.
    - **İncelenen Kanıtlar (enrichment):** tür rozetleri + heading + sayfa.
    - Durum rozetleri: salvaged ("Otomatik tamamlandı"), insufficient_evidence,
      coverage (missing) cezası.
  - Üst bilgi: rubric_id/version, oluşturma tarihi, session özeti.
- Türkçe karakter desteği: WeasyPrint'e Türkçe glyph içeren bir font (örn. DejaVu Sans)
  gömülür; `@font-face` ile template'e bağlanır.

### 3. PDF indirme endpoint'i — `app/api/routes/evaluation.py`
- `GET /api/evaluation/current/report.pdf?session_id=...`
- Akış: `read_evaluation_state(session_id)` → `final_report` yoksa **409** (rapor hazır
  değil). Varsa `render_report_pdf` → `Response(content=bytes, media_type="application/pdf",
  headers={"Content-Disposition": "attachment; filename=degerlendirme-raporu.pdf"})`.

### 4. Mail yapılandırması — `app/core/config.py` (`Settings`)
Env'den okunan alanlar eklenir (frozen dataclass; env okuma yardımcı eklenir):
- `smtp_enabled: bool` (false ise log-only dev modu)
- `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`
- `smtp_from_address`, `smtp_use_tls`
- `app_public_base_url` (mail metninde rapor linki için, opsiyonel)
- `.env.example` eklenir; gerçek kimlik bilgileri **commit edilmez**.

### 5. Mail adresi saklama — `app/services/upload/service.py` (metadata)
- `metadata.json` payload'ına `notification_email: str | None` ve
  `notification_sent_at: str | None` eklenir.
- Yeni endpoint `PUT /api/uploads/current/email` body `{ "email": "..." }`:
  - Backend e-posta format doğrulaması (basit regex / `email.utils.parseaddr`).
  - `write_metadata_payload` ile persist. Değerlendirme başlamadan önce çağrılır.
- `get_notification_email(session_id)` / `mark_notification_sent(session_id)` yardımcıları.

### 6. Mail gönderici + tamamlanma hook'u — `app/services/reporting/email_sender.py`
- `send_report_email(session_id: str, report: EvaluationReport) -> None`:
  - `get_notification_email(session_id)` → yoksa sessizce **çık**.
  - Zaten gönderilmişse (`notification_sent_at` dolu) **çık** (idempotency).
  - `render_report_pdf(report)` → PDF bytes.
  - Türkçe mail oluştur: konu "TÜBİTAK Proje Öneri Değerlendirme Raporunuz Hazır",
    gövde: genel skor + ana boyut özetleri + (varsa) rapor linki; **PDF ek**.
  - `smtplib` (TLS) ile gönder; başarı → `mark_notification_sent`.
  - `smtp_enabled=false` ise gerçek gönderim yerine **logla** (dev).
  - Tüm gövde `try/except` — hata değerlendirmeyi **çökertmemeli**, yalnızca loglanmalı.
- **Hook konumu:** `evaluation/service.py` tamamlanma noktası — `status="completed"` +
  `final_report` persist edildikten **hemen sonra** (~satır 218). Bu kod zaten arka plan
  thread'inde çalıştığı için **sekmeden bağımsızdır**.
  - Guard'lar: yalnızca context güncelse (`_is_evaluation_context_current` — superseded
    session'a mail YOK), mail adresi varsa, daha önce gönderilmemişse.
  - Gönderim ağ I/O'su içerdiği için ayrı bir günlük (daughter) thread'e alınabilir; ama
    izolasyon try/except ile sağlandığından inline da kabul edilebilir.

---

## Frontend Değişiklikleri

### 1. Mail input — değerlendirme başlatmadan önceki ekran
- Konum: `UploadPanel.tsx` (yükleme/başlatma ekranı; analiz→değerlendirme otomatik zincirleniyor,
  bu yüzden mail başlamadan önce alınmalı).
- E-posta alanı (HTML5 email validation + yardımcı metin):
  *"Sonuç çıktığında rapor bu adrese gönderilecek; sekmeyi kapatabilirsiniz."*
- `lib/analysis.ts` yeni helper: `setNotificationEmail(apiBaseUrl, sessionId, email)` →
  `PUT /api/uploads/current/email`. Değerlendirme otomatik başlamadan **önce** persist edilir.
- **Açık karar:** mail **opsiyonel** (boş bırakılırsa mail gönderilmez) olarak planlanmıştır;
  zorunlu yapılmak istenirse start akışına validasyon kapısı eklenir (bkz. Açık Kararlar).

### 2. PDF İndir butonu — rapor ekranı
- Konum: `EvaluationPanel.tsx` hero, `heroEvidence` bloğunun **sağına** (satır ~284 sonrası).
- Buton: "PDF İndir" — `onClick` → `/api/evaluation/current/report.pdf?session_id=...`
  adresini yeni sekmede aç / programatik indir. Rapor `completed` olana dek **disabled**.
- `lib/analysis.ts` helper: `downloadReportPdfUrl(apiBaseUrl, sessionId)` (URL üretir) veya
  fetch+blob indirme. CSS: hero satırına buton stili (`.heroDownloadButton`).
- Aynı bileşen hem canlı panelde hem rapor sayfasında kullanıldığından buton ikisinde de görünür;
  yalnızca `completed` durumunda aktif olur.

---

## Veri Akışı (özet)

**Mail:**
```
Start ekranı → PUT /uploads/current/email → metadata.json(notification_email)
   ↓ (kullanıcı sekmeyi kapatabilir)
BG thread: değerlendirme biter → final_report persist → completion hook
   → context güncel & email var & gönderilmemiş ise:
     render_report_pdf → SMTP gönder → metadata.json(notification_sent_at)
```

**PDF indirme:**
```
Buton → GET /evaluation/current/report.pdf → final_report → render_report_pdf → PDF bytes
```

İki yol **aynı** `render_report_pdf`'i kullanır → indirilen ile maillenen PDF birebir aynı.

---

## Dokunulacak / Eklenecek Dosyalar

| Dosya | Değişiklik |
|---|---|
| `backend/requirements.txt` | weasyprint, jinja2 |
| `backend/app/services/reporting/pdf_renderer.py` | **yeni** — `render_report_pdf` |
| `backend/app/services/reporting/templates/report.html` + `report.css` | **yeni** — UI'a benzer template |
| `backend/app/services/reporting/email_sender.py` | **yeni** — `send_report_email` |
| `backend/app/api/routes/evaluation.py` | **yeni endpoint** `report.pdf` |
| `backend/app/api/routes/uploads.py` | **yeni endpoint** `PUT current/email` |
| `backend/app/services/upload/service.py` | metadata'ya email/sent alanları + yardımcılar |
| `backend/app/services/evaluation/service.py` | tamamlanma hook'u (mail tetikleme) |
| `backend/app/core/config.py` | SMTP ayarları + env okuma |
| `backend/.env.example` | **yeni** — SMTP örnek değerleri |
| `frontend/lib/analysis.ts` | `setNotificationEmail`, PDF indirme helper'ı |
| `frontend/components/upload-panel/UploadPanel.tsx` | mail input alanı |
| `frontend/components/analysis/evaluation-panel/EvaluationPanel.tsx` | PDF İndir butonu |
| `frontend/.../evaluation-panel.module.css` + upload-panel CSS | buton + input stilleri |

## Değişmeyen / Korunan

- Mevcut değerlendirme pipeline'ı, retrieval, scoring, guard'lar — dokunulmaz; mail yalnızca
  tamamlanma sonrası **ek** bir adımdır ve hatası değerlendirmeyi etkilemez.
- `EvaluationState`/`EvaluationReport` şeması değişmez (PDF mevcut alanları okur).
- Session superseded koruması mail tarafında da uygulanır (eski sonuç maillenmez).

## Edge Case'ler ve Güvenlik

- Rapor hazır değilken PDF endpoint → **409**.
- Mail adresi yoksa → mail adımı sessizce atlanır (değerlendirme normal biter).
- Geçersiz e-posta → frontend + backend doğrulaması reddeder.
- Idempotency: `notification_sent_at` ile çift gönderim engellenir.
- Superseded/iptal session → mail gönderilmez.
- SMTP kimlik bilgileri yalnızca env'de; repoya girmez (`.env.example` şablon).
- `smtp_enabled=false` → log-only (geliştirme/test güvenliği).
- WeasyPrint Türkçe glyph: gömülü font ile garanti.
- Mail gönderimi ağ hatası → loglanır, kullanıcı akışı bozulmaz.
- Büyük rapor (15 kriter + İncelenen Kanıtlar) → PDF üretim süresi ölçülür; gerekiyorsa
  download endpoint'i streaming/async response yapılır.

## report-enrichment Bağımlılığının Kapsanması

PDF template'i, önceki plandan gelen şu alanları **mutlaka** render eder:
- Bulgularda `quote` (doğrulanmış birebir alıntı).
- "İncelenen Kanıtlar" bölümü (tür rozetleri + heading + sayfa).
- Keskinleştirilmiş `missing_information` (ne eksik + neden + nereye).

## Açık Kararlar (uygulama öncesi netleştirilecek)

1. **Mail zorunlu mu opsiyonel mi?** Plan opsiyonel varsayar. Zorunlu istenirse start
   akışına validasyon kapısı eklenir.
2. **PDF motoru:** WeasyPrint (varsayılan). Sadakat yetersizse Playwright/Chromium fallback.
3. **SMTP sağlayıcı:** Hangi SMTP (Gmail app-password, kurumsal SMTP, Mailgun/SendGrid SMTP)?
   Config alanları sağlayıcıdan bağımsızdır; yalnızca env değerleri değişir.

## Doğrulama / Test Adımları

1. **Backend import + smoke:** weasyprint kurulu; örnek `EvaluationReport` → `render_report_pdf`
   geçerli PDF bytes üretiyor (magic `%PDF`).
2. **PDF endpoint:** tamamlanmış session → 200 `application/pdf`; tamamlanmamış → 409.
3. **Mail endpoint:** `PUT current/email` geçerli/geçersiz adresleri doğru işliyor;
   metadata.json'a yazılıyor.
4. **Completion hook:** mock/log SMTP modunda, değerlendirme bitince hook tetikleniyor;
   idempotent (ikinci kez göndermiyor); superseded session'da göndermiyor.
5. **Frontend typecheck:** yeni helper'lar + buton + input tip olarak çözülüyor.
6. **Görsel:** üretilen PDF UI'a benziyor ve TÜM bölümleri (hero, ana skorlar, rubric,
   kriter kartları, bulgular+quote, eksikler, kanıtlar, İncelenen Kanıtlar) içeriyor.
7. **Uçtan uca:** sample.pdf yükle → mail gir → değerlendirmeyi başlat → **sekmeyi kapat**
   → bittiğinde maile PDF ekli rapor geldi mi; rapor ekranındaki butonla indirilen PDF
   maildekiyle aynı mı.
