# UI Mükemmelleştirme Planı

## Amaç

UI'ı kusursuz ve tutarlı hale getirmek. Beş somut problem ele alınır:

1. Koyu temada uyumsuz kalan kısımlar — hiç uyumsuz yer kalmamalı.
2. Rapor ekranı, projenin diğer ekranlarıyla aynı hissiyatı vermiyor — aynı his + en kullanıcı dostu hale.
3. Alt kriter detay modali kullanıcı dostu değil — en anlaşılır, en kullanıcı dostu hale.
4. Rubrik modali de aynı şekilde kötü — aynı iyileştirme.
5. Home hero kaydırma işareti (scroll cue) sayfa en tepedeyken görünmeli; işaretin **alt kısmı** sayfaya girildiğinde alt sınır olmalı (kayma olmamalı).

> **NOT:** Rapor ekranında görsel değişiklik yapıldıktan sonra, PDF çıktısında (bkz.
> `test/pdf-export-and-email-plan.md` → `report.html` / `report.css`) güncellenmesi gereken
> bir şey varsa o da senkron edilmelidir. PDF template'i rapor ekranını taklit ettiği için
> kartların/renklerin/bölüm düzeninin değişmesi PDF'i de etkiler.

## Tasarım sistemi temeli (referans)

Tema tokenları `components/layout/app-shell/app-shell.module.css`'te tanımlı:
`--app-bg, --app-text, --app-muted, --app-panel, --app-panel-strong, --app-panel-border,
--app-shadow, --accent, --accent-strong, --accent-soft, --accent-soft-strong,
--surface-tint, --surface-muted, --button-bg, --button-bg-hover, --button-text`.

Koyu tema `.themeDark` sınıfıyla bu tokenları override eder. **Kural:** Hiçbir bileşen renk
sabiti (hex/white/black) kullanmamalı; her renk bu tokenlardan türemeli. Tema bozulmalarının
kök nedeni bu kurala uyulmamasıdır.

---

## Problem 1 — Koyu tema tutarsızlığı (tam denetim + düzeltme)

### Kök nedenler (kanıtlı)
`components/analysis/evaluation-panel/evaluation-panel.module.css`:
- Satır 13-20: `--report-green/amber/red/blue` ve `-soft` varyantları **sabit açık-mod**
  değerleri (örn. `#edf7ef`, `#fff7e4`). Koyu modda status pill/badge zeminleri beyaza yakın
  kalıyor → metin okunmuyor, kart dışına taşan parlak lekeler.
- Satır 187, 365, 539, 571, 652: `background: #ffffff` — kartlar koyu modda **zorla beyaz**.
- Benzer sabitler diğer modül CSS'lerinde de olabilir.

### Yapılacaklar
1. **Tam denetim:** Tüm `components/**/*.module.css` taranır; her sabit renk (`#hex`,
   `white`, `black`, ham `rgba(...)` zeminler) listelenir.
   - Komut referansı: `grep -rnE "#[0-9a-fA-F]{3,6}|: ?white|: ?black"` → çıktı bir denetim
     tablosuna dönüştürülür (dosya, satır, mevcut değer, eşleneceği token).
2. **Token'a bağla:** Her yüzey/sınır/metin sabiti uygun token ile değiştirilir
   (`#ffffff` → `var(--app-panel)`, sınırlar → `var(--app-panel-border)`, ikincil metin →
   `var(--app-muted)`, gölgeler → `var(--app-shadow)`).
3. **Semantik durum renkleri (yeşil/amber/kırmızı/mavi):** `--report-*` tokenları **tema-bilinçli**
   yapılır. İki yol:
   - (a) Bu tokenları `app-shell.module.css`'in hem açık hem `.themeDark` bloğuna taşı (tek
     kaynak), VEYA
   - (b) evaluation-panel CSS'inde `:global(.themeDark)` seçicisiyle koyu varyantlarını
     override et. (Soft zeminler koyu modda `color-mix(... var(--app-panel))` ile koyulaştırılır,
     metin tonu açılır.)
4. **Görsel doğrulama:** Tema toggle ile her ekran açık↔koyu çevrilir; beyaz leke / okunmayan
   metin / kaybolan sınır kalmamalı.

**Kapsam:** evaluation-panel + evaluation-report-page öncelikli; ardından tüm `components/`
(analysis dashboard, chunk/parser viewer, upload-panel, sidebar, homepage) denetimden geçer.

---

## Problem 2 — Rapor ekranı: aynı hissiyat + en kullanıcı dostu

### Kök neden (kanıtlı)
- `EvaluationReportPage.tsx` standalone `EvaluationTopbar` + kendi hero'sunu kullanıyor;
  diğer ekranların app-shell/sidebar chrome'uyla aynı değil.
- Rapor yüzeyleri sabit beyaz (`#ffffff`) → sıcak panel tokenlarıyla uyuşmuyor.

### Yapılacaklar
1. **Chrome tutarlılığı:** Rapor sayfası, diğer ekranlarla aynı kabuk dilini kullanır
   (aynı arkaplan gradyanı, panel tokenları, gölge, kenar boşluğu ritmi). Topbar kalsa bile
   görsel dil (renk/spacing/typography) app-shell ile hizalanır.
2. **Yüzeyler tokenlaşır:** Tüm kart/blok zeminleri `var(--app-panel)` / `--app-panel-strong`,
   sınırlar `--app-panel-border`, gölgeler `--app-shadow`.
3. **Kullanıcı dostuluğu:**
   - Net görsel hiyerarşi: Genel Skor + Belge Kanıtı hero'su → Ana Boyut kartları → kriter
     listesi sıralaması korunur ama tipografik kontrast ve boşluk iyileştirilir.
   - Skorlar için renk-kodlu, erişilebilir (kontrast AA) durum göstergeleri (semantik
     tokenlardan).
   - Boş/eksik/yükleniyor durumları net.
4. **PDF parite notu:** Bu ekranın yeni düzeni `report.html`/`report.css`'e yansıtılır.

---

## Problem 3 — Alt kriter detay modali (en kullanıcı dostu hale)

### Konum
`EvaluationPanel.tsx` `criterionModal` (~satır 501; tetikleyici buton ~475,
`aria-haspopup="dialog"`), portal ile `document.body`'ye render.

### Sorunlar (UX)
- Yoğun, düz bilgi yığını; tarama zor; bölümleme zayıf; koyu temada yüzey sabitleri kırık.

### Yapılacaklar
1. **Bilgi mimarisi:** Modal içeriği net, etiketli bölümlere ayrılır:
   - Başlık + kriter kodu + skor rozeti (claim/evidence alt göstergeleriyle).
   - "Kriter ne arıyor?" (statik beklenti) → "Bu öneride ne bulundu?" (değerlendirme).
   - Olumlu / olumsuz bulgular (özet + gerekçe + alıntı) — görsel olarak ayrık iki kolon/blok.
   - Eksik bilgi + red flags — uyarı tonunda.
   - Kanıt kartları + "İncelenen Kanıtlar" — tür rozetleri + konum (heading + sayfa).
2. **Okunabilirlik:** Tipografik ölçek, satır yüksekliği, bölüm başlıkları (muted alt-etiket),
   yeterli boşluk. Uzun içerikte modal gövdesi scroll'lanır, başlık+kapat sabit kalır.
3. **Erişilebilirlik & etkileşim:** `Esc` ile kapama, backdrop tıklayınca kapanma, odak
   tuzağı (focus trap), `aria` etiketleri, görünür kapat butonu.
4. **Tema:** Tüm yüzey/sınır/metin tokenlardan; açık↔koyu kusursuz.
5. **Responsive:** Dar ekranda tam genişlik, tek kolon, rahat dokunma hedefleri.

---

## Problem 4 — Rubrik modali (alt kriterle aynı iyileştirme)

### Konum
`EvaluationPanel.tsx` `rubricModal` (~satır 164; "Değerlendirme Kriterleri"), içinde
`dimensionAccordion` (~339) ile boyut→kriter accordion'u.

### Yapılacaklar
- Problem 3'teki ilkelerin aynısı: net bölümleme, okunabilir tipografi, sabit başlık+scroll
  gövde, Esc/backdrop/focus-trap, tokenlı tema, responsive.
- Accordion deneyimi iyileştirilir: açık/kapalı durum görsel olarak net, "Detayı aç" ipucu
  belirgin, her boyutun ağırlık/skoru başlıkta görünür.
- Rubrik tablosu ile modal arasındaki görsel dil birleştirilir (aynı kart/rozet stilleri).

> Problem 3 ve 4 için **ortak, yeniden kullanılabilir modal kabuğu** (backdrop + panel +
> sabit başlık + scroll gövde + kapat + focus-trap + tema) çıkarılması önerilir; iki modal da
> bunu kullanır → tutarlılık + bakım kolaylığı.

---

## Problem 5 — Home hero scroll cue (kayma olmadan görünür)

### Konum
`components/pages/homepage/homepage.module.css`: `.hero { min-height: min(78vh, 860px) }`
(~94), `.scrollCue` (~195, `margin-top: 6px`), `.scrollMouse/.scrollWheel`.

### Sorun
Hero + altındaki scroll cue, ilk görünüm (viewport) yüksekliğini aşabiliyor (860px cap +
üstteki nav/boşluklar). Sonuç: sayfa en tepedeyken cue **fold altında** kalıyor; görmek için
kaymak gerekiyor.

### Hedef
Sayfaya girildiğinde hiç kaymadan: hero ilk viewport'a **tam** sığsın; scroll cue tamamen
görünsün ve cue'nun **alt kenarı** ilk viewport'un alt sınırı olsun.

### Yapılacaklar
1. Hero bölümü ilk ekranı **tam dolduracak** şekilde ayarlanır: sabit `860px` cap yerine
   mevcut viewport yüksekliği esas alınır (`min-height: 100dvh` eksi varsa üst nav yüksekliği;
   `dvh` ile mobil adres-çubuğu kayması da çözülür).
2. Hero, dikey dağıtımı (içerik üstte/ortada, cue altta) flex/grid ile yapar; cue alt kenara
   güvenli boşlukla yaslanır (`padding-bottom` ile), taşma olmaz.
3. İçerik uzunsa taşmayı engellemek için tipografi/boşluk ölçeklenir; cue asla viewport dışına
   itilmez.
4. Doğrulama: farklı ekran yüksekliklerinde (laptop, büyük monitör, mobil) sayfa açılışında
   cue tam görünür ve alt kenarı fold'da.

---

## Dokunulacak / Etkilenen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `components/layout/app-shell/app-shell.module.css` | semantik `--report-*` tokenlarının açık+koyu tanımı (Problem 1, seçenek a) |
| `components/analysis/evaluation-panel/evaluation-panel.module.css` | sabit renkleri tokenlama; koyu override; modal stilleri (P1,3,4) |
| `components/analysis/evaluation-panel/EvaluationPanel.tsx` | modal yapısı/bölümleme; ortak modal kabuğu; erişilebilirlik (P3,4) |
| `components/analysis/evaluation-report-page/EvaluationReportPage.tsx` + `.module.css` | chrome/tema hizalama, kullanıcı dostuluk (P2) |
| (gerekirse) ortak `Modal` bileşeni + CSS | yeniden kullanılabilir modal kabuğu (P3,4) |
| `components/pages/homepage/homepage.module.css` | hero yüksekliği + scroll cue konumu (P5) |
| diğer `components/**/*.module.css` | koyu tema denetiminden geçen sabit renkler (P1) |
| `backend/app/services/reporting/templates/report.html` + `report.css` | rapor düzeni değişirse PDF paritesi (NOT) |

## Değişmeyen / Korunan

- İşlevsel mantık, veri akışı, API'ler — dokunulmaz; değişiklikler yalnızca görsel/CSS ve
  modal yapısı/erişilebilirlik düzeyinde.
- Tema toggle mekanizması (`AppShellContext`, `.themeDark`) korunur; yalnızca eksik tokenlama
  tamamlanır.
- Rapor/PDF içerik alanları korunur; yalnızca sunum hizalanır.

## Doğrulama / Test Adımları

1. **Koyu tema denetimi:** Her ekran açık↔koyu çevrilir; beyaz leke, okunmayan metin, kaybolan
   sınır, kırık badge **kalmamalı**. Denetim tablosundaki her sabit renk giderilmiş olmalı.
2. **Rapor ekranı:** Diğer ekranlarla yan yana karşılaştırma — aynı arkaplan, panel, gölge,
   spacing hissi. Kontrast AA.
3. **Modaller:** Alt kriter + rubrik modali — bölümlenmiş, okunabilir, Esc/backdrop/focus-trap
   çalışıyor, açık+koyu kusursuz, mobilde tek kolon.
4. **Hero cue:** Birden çok viewport yüksekliğinde sayfa açılışında cue tam görünür, alt kenarı
   fold'da, kayma yok (`dvh` ile mobilde de).
5. **Responsive:** Dar/orta/geniş ekranlarda kritik ekranlar bozulmuyor.
6. **PDF paritesi:** Rapor görselleri değiştiyse `report.html`/`report.css` güncellendi mi;
   üretilen PDF yeni rapor düzeniyle tutarlı mı.
7. **Frontend typecheck/build:** `frontend/` tsc + build temiz.
