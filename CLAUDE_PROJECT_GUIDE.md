# TUBITAK Proposal Evaluator - Uctan Uca Proje Rehberi

Bu dosya, projeyi baska bir LLM'e, ozellikle Claude'a, hizli ama eksiksiz sekilde anlatmak icin hazirlandi. Amac yalnizca dosya agacini ozetlemek degil; sistemin gercekte nasil calistigini, hangi adimlarda hangi verinin uretildigini, hangi sinirlarin ve teknik kararlarin oldugunu netlestirmektir.

## 1. Projenin ne oldugu

Bu repo, TUBITAK 1501/1507 tarzindaki proje onerilerini AI destekli olarak inceleyen bir uygulamadir.

Sistem temel olarak su zinciri izler:

1. Kullanici belgeyi yukler.
2. Backend belgeyi session bazli saklar.
3. Belge extraction asamasindan gecer.
4. Extraction cikisi parser tarafinda duzenli bir icerik akisina ve baslik hiyerarsisine donusturulur.
5. Bu yapi chunking ile anlamli metin parcaciklarina ayrilir.
6. Chunk'lar embedding vektorlerine cevrilir ve Chroma'ya yazilir.
7. Degerlendirme rubric'indeki her alt kriter icin once kanit retrieval yapilir.
8. Sonra yerel Ollama modeli bu kanitlarla kriter bazli puanlama yapar.
9. En sonda ana boyut skorlarina ve genel rapora agregasyon yapilir.
10. Frontend tum bu sureci canli olarak izler ve son raporu gosterir.

Bu nedenle proje sadece "dokuman yukle ve puan ver" degildir. Icinde session yonetimi, background pipeline, retrieval tabanli evidence toplama, local embedding store ve local judge model kullanan cok asamali bir analiz sistemi vardir.

## 2. Teknoloji yigini

### Backend

- Framework: FastAPI
- Runtime: Python
- API server: Uvicorn
- Veri dogrulama: Pydantic v2
- PDF extraction: Docling
- Embedding modeli: `BAAI/bge-m3`
- Embedding inference: `transformers` + `torch`
- Vector store: ChromaDB persistent storage
- Judge modeli: Ollama uzerinden `aya-expanse:8b`

### Frontend

- Framework: Next.js 15
- UI runtime: React 19
- Dil: TypeScript
- API ile iletisim: dogrudan `fetch`

### Gelistirme yardimcilari

- Root `Makefile`
- Orkestrasyon script'i: `scripts/run_dev.py`

## 3. Repo yapisi

Yuksek seviyede repo 3 ana bolume ayriliyor:

- `backend/`: FastAPI uygulamasi ve tum analiz/degerlendirme mantigi
- `frontend/`: Next.js istemci uygulamasi
- `scripts/`: gelistirme ve servis baslatma yardimcilari

En kritik klasorler:

- `backend/app/api/routes/`: HTTP endpoint'leri
- `backend/app/services/upload/`: oturum bazli dosya yukleme ve temizleme
- `backend/app/services/extraction/`: Docling extraction ve parser
- `backend/app/services/chunking/`: section ve chunk uretimi
- `backend/app/services/embedding/`: embedding uretimi ve Chroma store
- `backend/app/services/evaluation/`: retrieval, prompt, judge, aggregation
- `backend/app/services/analysis/`: extraction -> parser -> chunking -> embedding pipeline orkestrasyonu
- `frontend/components/upload-panel/`: yukleme paneli
- `frontend/components/analysis/`: analiz ve rapor ekranlari
- `frontend/components/pages/evaluation/`: ana degerlendirme deneyimi
- `frontend/components/pages/debug-flow/`: debug odakli analiz izleme deneyimi

## 4. Calistirma sekli

Root `README.md` ve `Makefile`'a gore tipik akış su:

- `make setup`
  - backend icin `.venv` olusturur
  - Python bagimliliklarini kurar
  - frontend `npm install` yapar
  - Ollama modelini yoksa ceker
- `make warmup`
  - `BAAI/bge-m3` modelini onceden cache'ler
- `make backend`
  - FastAPI backend'i baslatir
- `make frontend`
  - Next.js frontend'i baslatir
- `make run`
  - backend ve frontend'i birlikte baslatir
- `make check`
  - import guvenlik kontrollerini ve smoke test'i calistirir

Bu komutlarin gercek is mantigi `scripts/run_dev.py` icindedir.

### `scripts/run_dev.py` ne yapiyor?

Bu script sadece servis acmiyor; ayni zamanda calisma ortamini garanti altina aliyor:

- backend `.venv` var mi kontrol ediyor
- frontend `node_modules` var mi kontrol ediyor
- `backend/app/services/*/__init__.py` dosyalarinin side-effect free olmasini zorluyor
- backend import smoke test'i calistiriyor
- gerekiyorsa Ollama server'i otomatik aciyor
- cikista actigi Ollama process'ini kapatiyor
- `run` modunda backend ve frontend'i paralel process olarak ayakta tutuyor

Bu import guard onemli cunku proje servis katmaninda circular import benzeri sorunlari erken yakalamayi hedefliyor.

## 5. Konfigurasyon

Temel ayarlar `backend/app/core/config.py` icinde.

En kritik ayarlar:

- API prefix: `/api`
- upload storage: `backend/runtime/uploads` altinda
- embedding store: `backend/runtime/embedding/chroma`
- embedding model cache: `backend/cache/embedding/model-cache`
- embedding modeli: `BAAI/bge-m3`
- judge modeli: `aya-expanse:8b`
- Ollama base URL: `http://127.0.0.1:11434`
- session timeout: `120` saniye
- izinli frontend origin'leri:
  - `localhost:3000`
  - `127.0.0.1:3000`
  - `localhost:3001`
  - `127.0.0.1:3001`
  - ayrica Cloudflare tunnel regex'i

Frontend tarafinda API tabani:

- public base URL: `NEXT_PUBLIC_API_BASE_URL`
- internal SSR base URL: `INTERNAL_API_BASE_URL` veya `API_PROXY_TARGET`
- fallback backend URL: `http://127.0.0.1:8000`

Next.js rewrites ile `/api/*` istekleri backend'e proxylenir.

## 6. Sistem mimarisi

Mantik iki ana eksende ayriliyor:

1. HTTP/API katmani
2. Service/orchestration katmani

### API katmani

`backend/app/api/router.py` su route gruplarini baglar:

- `/api/uploads`
- `/api/extraction`
- `/api/chunking`
- `/api/embedding`
- `/api/evaluation`
- `/api/analysis`
- `/api/health`

### Service katmani

Service katmaninda iki farkli calisma tipi var:

- Senkron utility/service fonksiyonlari
- Background thread ile calisan uzun analiz/degerlendirme pipeline'lari

En kritik iki orchestration servisi:

- `analysis.service`: extraction -> parsing -> chunking -> embedding
- `evaluation.service`: retrieval -> judge -> aggregation

## 7. Session modeli

Sistemin merkezinde `session_id` vardir. Neredeyse tum backend operasyonlari session bazlidir.

### Frontend session davranisi

`frontend/lib/session.ts`:

- session id'yi `localStorage` ve `sessionStorage` icinde saklar
- yoksa yeni bir UUID tabanli id uretir
- tablar arasi degisiklikleri event ile yayar

### Backend session davranisi

`backend/app/services/upload/service.py`:

- session id regex ile validate edilir
- her session icin ayri klasor olusturulur
- `metadata.json` ile dosya bilgisi tutulur
- `last_seen_at` ile heartbeat tabanli yasam suresi yonetilir
- timeout gecince eski session klasorleri silinir

### Session timeout

Timeout su anda `120` saniye. Frontend, `UploadPanel` icinde her 30 saniyede heartbeat atarak aktif session'i yasatir.

## 8. Dosya yukleme akisi

Upload akisi `UploadPanel` ve `/api/uploads` endpoint'leri etrafinda kurulu.

### Desteklenen uzantilar

Upload validation tarafinda su uzantilar kabul ediliyor:

- `.pdf`
- `.doc`
- `.docx`

### Kritik sinirlama

Kodun mevcut haliyle extraction pipeline fiilen PDF odaklidir.

- `upload.service` PDF/DOC/DOCX kabul eder.
- Ama `extraction.service` sadece PDF icin extraction output uretir.
- `analysis.service` de dogrudan `extract_pdf_with_docling(...)` cagirir.

Yani:

- UI seviyesinde Word dosyasi yuklenebilir.
- Ancak extraction/analysis tarafinda akisin tam desteklendigi format PDF'dir.
- Claude bu projeyi anlatirken "Word upload var" ile "Word pipeline tam destekli" durumlarini karistirmamali.

### Upload endpoint'leri

- `POST /api/uploads`
  - `X-Session-Id` header zorunlu
  - dosyayi session klasorune kaydeder
  - onceki session dosyasini ve embeddinglerini temizler
- `GET /api/uploads/current`
  - aktif session dosya metadata'sini doner
- `DELETE /api/uploads/current`
  - dosyayi ve session'a bagli embeddingleri temizler
- `POST /api/uploads/current/heartbeat`
  - session timeout'u ileri tasir
- `GET /api/uploads/current/content`
  - yuklenen dosyanin icerigini sunar
  - PDF ise inline gostermeye calisir

## 9. Backend ana lifecycle

FastAPI app'i `backend/app/main.py` icinde kurulur.

Startup'ta iki sey garanti edilir:

- upload storage klasoru olusturulur
- embedding store klasoru olusturulur

Bu, runtime dizinlerinin ilk istekte degil uygulama acilisinda hazir olmasini saglar.

## 10. Analysis pipeline: extraction -> parser -> chunking -> embedding

Bu proje mantiginin merkezidir.

### Nasil baslar?

`POST /api/analysis/current/start`

veya

`POST /api/analysis/current/start-until-chunking`

ile baslatilir.

Ilk endpoint tam pipeline'i calistirir.
Ikinci endpoint embedding'e kadar gitmez; chunking tamamlandiginda durur. Bu daha cok debug amaclidir.

### Analysis state modeli

Analysis state `AnalysisState` olarak saklanir. Durumlar:

- `idle`
- `queued`
- `extracting`
- `parsing`
- `chunking`
- `embedding`
- `completed`
- `failed`

Ayrica her stage icin zaman bilgisi vardir:

- `extraction_timing`
- `parser_timing`
- `chunking_timing`
- `embedding_timing`

State dosya bazli olarak session klasorunde tutulur:

- `runtime/uploads/<session_id>/analysis/analysis_state.json`

### Analysis neden background thread ile calisiyor?

Pipeline agir oldugu icin HTTP request icinde bloklanmiyor. `analysis.service` her session icin background `Thread` baslatir ve durum dosyasini asama asama gunceller. Frontend de bu state'i poll ederek UI'yi gunceller.

### Session superseded mantigi

Analysis basladiktan sonra kullanici ayni session'da yeni dosya yuklerse, eski thread yanlis dosyayi islemeye devam etmesin diye `uploaded_at` kontrolu yapilir.

Bu mekanizma:

- aktif upload degistiyse thread sonucunu yok sayar
- stale pipeline sonucunun yeni dosyanin ustune yazilmasini onler

Bu, projede teknik olarak en onemli guvenlik mantiklarindan biridir.

## 11. Extraction asamasi

Extraction `backend/app/services/extraction/docling_extractor.py` icinde.

### Ne yapar?

- PDF'i Docling ile parse eder
- ham Docling cikisini `docling_output` olarak dondurur
- dokumana ait hafif metadata da ekler
  - `file_name`
  - `page_count`

### Docling ayarlari

Pipeline kasitli olarak sunlara ayarlanmis:

- OCR kapali
- table structure acik
- formula enrichment kapali
- backend text zorunlu
- picture image generation acik
- page image generation kapali

Bu secimlerden anlasilan su:

- hedef belge secilebilir metin iceren PDF'ler
- tablolar first-class vatandas
- proje takvimi gibi gorsel is paketleri parser tarafinda normalize edilmek isteniyor

### Extraction endpoint'leri

- `POST /api/extraction/current/extraction-output`
  - mevcut upload icin extraction cikisini verir
- `POST /api/extraction/current/parser-output`
  - extraction sonrasinda parser cikisini verir

Not: extraction endpoint'leri stateful bir cache kullanmiyor; gerekli veriyi session dosyasindan okuyup uretir.

## 12. Parser asamasi

Parser `backend/app/services/extraction/parser.py` icinde.

Bu katman cok onemli cunku Docling'in ham cikisini proje-ozel semantik yapiya ceviriyor.

### Parser ne uretir?

Iki temel artefakt:

1. `content_stream`
2. `heading_hierarchy`

### `content_stream`

Bu, belgeyi duz ama sirali bir olay akisi gibi temsil eder.

Item tipleri:

- `text`
- `table`
- `picture`
- `group`
- `key_value`
- `form_item`
- `unknown`

Her item su bilgileri tasir:

- kaynak ref
- okuma sirasi
- label
- sayfa araligi
- normalize edilmis icerik

### Parser'in yaptigi onemli isler

- Docling referanslarini cozer
- body.children uzerinden lineer okuma akisi kurar
- footer/page number benzeri gürultuleri atar
- heading adaylarini regex tabanli yakalar
- baslik seviyelerini stack tabanli algoritma ile hiyerarsiye donusturur
- list group'larini normalize eder
- TUBITAK gantt chart benzeri gorsel icerikleri ozel normalize etmeye calisir

### Heading hierarchy neden onemli?

Chunking asamasi section-first calisiyor. Yani belge once anlamli baslik bolumlerine ayriliyor; sonra chunk'lar bu section'larin icinden cikiyor. Bu nedenle parser hiyerarsisi retrieval kalitesini dogrudan etkiliyor.

## 13. Chunking asamasi

Chunking `backend/app/services/chunking/` altinda.

### Chunking'in amaci

Belgede embedding ve retrieval icin kullanilabilecek anlamli parcalar uretmek.

### Uretilen yapi

`ChunkOutput` iki parcadan olusur:

1. `sections`
2. `chunks`

### `sections`

Section'lar leaf heading bazli container'lardir.

Bir section su baglami tasir:

- baslik yolundaki kodlar
- baslik yolundaki basliklar
- leaf heading
- sayfa araligi
- bagli content ref'leri
- varsa work package metadata'si

### Chunk tipleri

Sistem 4 tip chunk uretir:

- `qa`
- `narrative`
- `table`
- `list`

### Chunk builder mantigi

`builders.py` icinde her section icin su sira izlenir:

1. Section QA adayi mi diye bakilir.
2. Icinde table bloklari varsa `table` chunk uretilir.
3. Icinde list bloklari varsa `list` chunk uretilir.
4. Geri kalan text benzeri alanlardan `narrative` chunk'lar uretilir.

### QA chunk mantigi

Oldukca konservatif:

- soru olarak leaf heading kullanilir
- kisa text bloklari cevap gibi davranabilir
- uzun aciklayici bloklar guidance olabilir

### Narrative chunk mantigi

- table ve list olmayan text bloklarindan toplanir
- gürultu metinleri atilir
- uzun metinler `split_narrative_blocks` ile parcali chunk'lara bolunebilir

### Table chunk mantigi

- kolonlar
- satirlar
- olasi tablo basligi

ayristirilir ve embedding'e uygun tekil metin temsil de uretilir.

### List chunk mantigi

- list item'lar sirali saklanir
- embedding icin metinlestirilir

### Chunk endpoint'i

- `POST /api/chunking/current/chunk-output`

Bu endpoint session'daki aktif parser cikisindan chunk output uretir.

## 14. Embedding asamasi

Embedding katmani `backend/app/services/embedding/` altinda.

### Model

Tek embedding provider var:

- provider name: `bge_m3`
- model: `BAAI/bge-m3`

### Model calisma sekli

`provider.py`:

- `transformers` ile tokenizer/model yukler
- cache dizinini kullanir
- `HF_HUB_OFFLINE=1` ve `TRANSFORMERS_OFFLINE=1` ayarlariyla offline mod bekler
- local cache yoksa `make warmup` ile once indirilmesi gerekir

### Embedding olusturma

`build_embeddings_for_chunk_output(...)`:

- tum chunk'larin `text_for_embedding` alanlarini toplar
- modelle vektorlere cevirir
- her chunk icin `EmbeddingRecord` yaratir
- Chroma'daki o session collection'ini silip yeniden yazar

### Chroma store

Her session icin koleksiyon adi:

- `session_<session_id>`

Saklanan metadata:

- `document_id`
- `section_id`
- `chunk_type`
- `heading_path_titles_json`
- `page_start`
- `page_end`

Storage yeri:

- `backend/runtime/embedding/chroma`

### Embedding endpoint'leri

- `GET /api/embedding/current`
  - mevcut embedding output metadata'sini verir
- `POST /api/embedding/current/search`
  - semantic arama yapar

### Embedding search nasil calisiyor?

Arama istegi:

- query
- top_k
- chunk_types

Akis:

1. query embedding'e cevrilir
2. Chroma query calisir
3. cosine mesafe `1 - distance` mantigiyla similarity score'a cevrilir
4. sonuc chunk metadata'si frontend'e doner

## 15. Evaluation pipeline

Degerlendirme asamasi `backend/app/services/evaluation/` altindadir.

Bu katman analizden farkli olarak "belgeyi anlamli parcaya ayirmak" degil, "rubric bazli hakem puani uretmek" islemi yapar.

### Evaluation ne zaman baslayabilir?

Sadece su durumda:

- analysis state `completed` olmali
- embedding output hazir olmali

Aksi halde `409 Conflict` doner.

### Evaluation state

Durumlar:

- `idle`
- `queued`
- `retrieving`
- `evaluating`
- `aggregating`
- `completed`
- `failed`

State dosya bazli tutulur:

- `runtime/uploads/<session_id>/evaluation/evaluation_state.json`

### Evaluation akisi

Her alt kriter icin su sira izlenir:

1. Evidence retrieval
2. Judge model evaluation
3. Sonucun normalize edilmesi
4. Tum kriterler bitince aggregation

### Otomatik tetikleme

Full analysis pipeline basarili tamamlaninca backend, follow-up olarak evaluation'i otomatik baslatmayi dener. Yani ideal durumda kullanici ikinci butona basmadan da analiz sonrasi degerlendirme baslayabilir.

## 16. Rubric yapisi

Rubric dosyasi:

- `backend/app/services/evaluation/schemas/tubitak_default.json`

### Mevcut rubric

- `rubric_id`: `tubitak-1501-1507`
- `version`: `v3`
- program kodlari:
  - `1501`
  - `1507`

### Ana boyutlar

3 ana boyut var:

- `A`: Endustriyel Ar-Ge icerigi, teknoloji duzeyi, yenilik
- `B`: Proje plani ve kurulus altyapisi
- `C`: Ekonomik yarar ve ulusal kazanim

### Alt kriter sayisi

Toplam `15` adet `criterion_id` vardir.

### Rubric criterion alanlari

Her alt kriter sunlari tanimlar:

- `criterion_id`
- `main_dimension_id`
- `title`
- `description`
- `question`
- `weight`
- `score_min`, `score_max`
- `source_sections`
- `required_sections`
- `fallback_sections`
- `semantic_queries`
- `ui_label`
- `ui_explanation`
- `allowed_chunk_types`
- `evidence_top_k`
- `minimum_evidence_count`

Bu alanlar retrieval ve judge prompt kalitesini belirler.

## 17. Evidence retrieval mantigi

Retrieval katmani `evaluation/retrieval.py` icinde.

Bu projedeki retrieval, yalnizca semantic search degil; "section-first + semantic support + fallback context" yapisindadir.

### Her kriter icin 3 farkli kanit havuzu

1. `primary_section_chunks`
2. `semantic_support_chunks`
3. `fallback_context_chunks`

### 1. Primary section chunks

Kriterin `source_sections` alanina gore section eslesmesi aranir.

Eslesme mantigi:

- heading code bazli
- heading title bazli
- normalize edilmis metin karsilastirmalari

Bu kisim "belgenin resmi dogru bolumu"nden kanit cekmeyi amaclar.

### 2. Semantic support chunks

Kriterin `semantic_queries` alanlari embedding search ile kosulur.

Bu kisim resmi section'da olmayan ama anlamsal olarak ilgili chunk'lari bulur.

### 3. Fallback context chunks

Eger primary taraf zayifsa:

- `fallback_sections` taranir
- bu da zayifsa kalan uygun chunk'lardan context havuzu uretilir

### Coverage mantigi

`required_sections` uzerinden coverage durumu hesaplanir:

- `complete`
- `partial`
- `missing`

Bu bilgi daha sonra skor cezasina donusur.

### Dedupe mantigi

Ayni chunk birden fazla kaynaktan gelebilir. Sistem chunk id bazli dedupe eder ve en yuksek similarity'yi korur.

## 18. Judge modeli ve prompt yapisi

Judge provider `evaluation/provider.py` icinde.

### Model

- Ollama chat API kullanilir
- model: `aya-expanse:8b`
- `format: "json"` zorlanir
- temperature `0.1`

### Prompt yapisi

`prompt_builder.py` iki mesaj uretir:

- system prompt
- user prompt

System prompt'un ana kisitlari:

- sadece verilen kanitlara dayan
- dis bilgi kullanma
- eksik bilgiyi uydurma
- puanlari 0-100 ver
- Turkce don
- JSON disinda bir sey donme

User prompt su verileri verir:

- kriter kimligi
- kriter sorusu ve aciklamasi
- puanlama skalasi
- coverage status
- coverage notes
- primary / semantic / fallback kanit bloklari
- donulmesi gereken JSON schema

### Retry mantigi

Model ilk denemede gecerli JSON donmezse ikinci kez "yalnizca gecerli JSON don" diye retry mesaji eklenir.

### Response sanitize mantigi

Modelin dondugu chunk id'ler disinda olmayan referanslar ayiklanir. Yani judge hallucination ile session'da olmayan bir `chunk_id` yazsa bile sistem bunu filtrelemeye calisir.

Bu cok onemli bir koruma katmanidir.

## 19. Skorlama ve ceza mantigi

Evaluation service'te iki onemli ceza sabiti var:

- `MISSING_COVERAGE_SCORE_PENALTY = 15`
- `PARTIAL_COVERAGE_SCORE_PENALTY = 7`

Yani judge iyi puan vermis olsa bile, zorunlu bolum kapsama eksigi varsa puan asagi cekilir.

Bu mimari tercih su anlama gelir:

- sistem sadece semantic benzerlige bakmiyor
- TUBITAK formunun beklenen resmi section yapisina da uyum ariyor

### Hic kanit yoksa

Kriter icin yeterli kanit yoksa:

- taban / dusuk guvenli sonuc uretilir
- veya model sonucu parse edilemiyorsa fallback result yazilir

Bu nedenle pipeline "her durumda bir sekilde sonuc" vermeye meyillidir; tamamen bos donmemeye calisir.

## 20. Aggregation mantigi

Tum kriterler bitince evaluation service final report uretir.

Rapor tipik olarak sunlari icerir:

- `overall_score`
- `main_scores`
- `subcriteria_results`
- `rubric_table`
- `total_weighted_score`
- `max_possible_weighted_score`
- `scored_criteria_count`
- `final_summary`

Ana boyut skorlarindan genel skor hesaplanir. Frontend rapor ekranlari da bu yapilari kullanir.

## 21. Frontend ekran akisi

Frontend iki ana deneyim sunuyor:

1. Evaluation odakli ana deneyim
2. Debug flow odakli gelistirici deneyimi

### Root route

- `/` -> `/home`'a redirect eder

### Home

- `/home`
- daha cok giris/landing gorevi gorur

### Debug Flow

- `/debug-flow`
- upload + analiz pipeline durum izleme ekrani
- extraction, parser, hierarchy, chunk, embedding sayfalarina link verir

### Evaluation

- `/evaluation`
- kullanicinin belge yukleyip tum analiz/degerlendirme surecini takip ettigi ana ekran

### Evaluation Report

- `/evaluation/report`
- session'a bagli degerlendirme raporunu gosterir
- query param ile `sessionId` da alabilir

## 22. `UploadPanel` davranisi

`frontend/components/upload-panel/UploadPanel.tsx`:

- session id'yi baslatir
- mevcut upload state'i yukler
- heartbeat yollar
- dosya secme/yukleme/silme aksiyonlarini yonetir
- PDF ise mini preview gosterir
- session reset sirasinda backend'deki mevcut upload'i siler ve yeni session id uretir

Bu panel hem debug flow hem de evaluation sayfasinda yeniden kullanilir.

## 23. Debug ekranlari ne ise yariyor?

Debug flow sayfalari pipeline ara ciktilarini incelemek icin var.

Beklenen kullanim:

- upload yap
- analizi baslat
- extraction output'a bak
- parser output ve hierarchy'ye bak
- chunk output'a bak
- embedding search'i test et

Bu sayfalar, retrieval ve parser kalitesini iyilestirmek icin cok degerli.

## 24. Evaluation UI davranisi

`EvaluationWorkspace` analizi ve degerlendirmeyi birlikte yonetir.

Onemli davranislar:

- session ve upload degisirse local state resetlenir
- analysis ve evaluation state'leri periyodik poll edilir
- analysis tamamlandiysa evaluation otomatik tetiklenebilir
- surec ilerlerken adim bazli progress flow gosterilir
- son durumda kullanici rapora yonlendirilebilir veya rapor panelini acabilir

UI tarafinda ayrica "SudokuBoard" gibi bekleme/oyunlasma unsurlari da bulunuyor; bu, uzun surebilen pipeline sirasinda kullaniciyi oyalamak icin dusunulmus gorunuyor.

## 25. Evaluation report UI

`EvaluationPanel` / `EvaluationReportViewer` su amaclara hizmet eder:

- aktif session'in evaluation state'ini yukler
- evaluation hala calisiyorsa poll eder
- ana boyut bazli raporu olusturur
- rubric detay modal'i gosterir
- alt kriter bazli guclu/zayif yon ve kanit anlatilarini sunar

Bu ekran, backend'den gelen evaluation state'i neredeyse dogrudan render eder; is mantiginin cogu backend'dedir.

## 26. Persistence modeli

Bu projede klasik bir SQL veritabani yok.

Persistence su yollardan saglaniyor:

### Dosya tabanli state

Session klasoru altinda:

- upload metadata
- fiziksel yuklenen dosya
- analysis state JSON
- evaluation state JSON

### Vector persistence

- ChromaDB persistent client
- disk uzerinde session collection'lari

Bu tasarim gelistirme icin hafif ve pratiktir ama production'da cok kullanicili ortamlarda yeniden dusunulmesi gerekir.

## 27. Eszamanlilik ve lock kullanimi

Projede state corruption riskini azaltmak icin birkac lock var:

- upload tarafinda `Lock`
- analysis store tarafinda `Lock`
- evaluation store tarafinda `Lock`
- embedding store tarafinda `Lock`
- analysis runner registry icin `RUNNER_LOCK`
- evaluation runner registry icin `RUNNER_LOCK`

Ayrica ayni session icin halihazirda calisan thread varsa yeni runner tekrar baslatilmaz.

## 28. API ozet tablosu

### Health

- `GET /api/health`

### Uploads

- `POST /api/uploads`
- `GET /api/uploads/current`
- `DELETE /api/uploads/current`
- `POST /api/uploads/current/heartbeat`
- `GET /api/uploads/current/content`

### Extraction

- `POST /api/extraction/current/extraction-output`
- `POST /api/extraction/current/parser-output`

### Chunking

- `POST /api/chunking/current/chunk-output`

### Embedding

- `GET /api/embedding/current`
- `POST /api/embedding/current/search`

### Analysis

- `POST /api/analysis/current/start`
- `POST /api/analysis/current/start-until-chunking`
- `GET /api/analysis/current`

### Evaluation

- `POST /api/evaluation/current/start`
- `GET /api/evaluation/current`

## 29. Saglik endpoint'i ne ise yariyor?

`/api/health` sadece basit bir "ok" endpoint'i degildir; frontend route'lari bu endpoint'i kullanarak server-side render asamasinda backend'e erisilip erisilmedigini anlamaya calisir.

Debug ve evaluation route'lari sayfa yuklenirken health kontrolu yapar. Basarisiz olursa UI yine acilir ama backend erisimi yokmus gibi davranir.

## 30. Bu projedeki en onemli tasarim kararlari

Claude icin ozetle en onemli tasarim tercihleri sunlar:

### 1. Session-centric mimari

Her sey `session_id` etrafinda doner. Kullanici bazli degil, session bazli state vardir.

### 2. File-based orchestration state

Analysis ve evaluation sonucu DB yerine JSON dosyalarda tutulur.

### 3. Section-first retrieval

Semantic search tek kaynak degil. Rubric section'lari birincil kaynak kabul edilir.

### 4. Local-first AI stack

- local embedding modeli
- local Chroma store
- local Ollama judge modeli

Yani sistem internet bagimliligina degil, local AI runtime'a dayanir.

### 5. Human-debuggable pipeline

Ara ciktilar frontend debug sayfalarinda gorulebilir. Bu, parser/chunking/retrieval iyilestirmesi icin kasitli bir urunlestirme karari gibi duruyor.

## 31. Mevcut sinirlar ve dikkat edilmesi gereken noktalar

Claude'a bunu anlatirken su noktalar mutlaka vurgulanmali:

### 1. DOC/DOCX upload var ama tam pipeline destegi net degil

Upload katmani Word kabul ediyor ama extraction ve analysis kodu PDF merkezli.

### 2. Session timeout kisa

`120` saniye cok agresif. Heartbeat olmazsa state temizlenebilir.

### 3. Production-grade persistence yok

DB yerine dosya sistemi ve Chroma kullaniliyor.

### 4. Background thread modeli process-local

Uvicorn reload veya coklu worker senaryolarinda thread/state mantigi ekstra dikkat ister.

### 5. Retrieval ve scoring rubric'e sikica bagli

Rubric section adlari ve dokumanin gercek basliklari uyusmazsa kalite hizla dusebilir.

### 6. Embedding modeli offline moda ayarli

Model cache yoksa ilk calisma dogrudan patlayabilir; `make warmup` bu yuzden var.

## 32. Claude bir degisiklik yapacaksa once neyi anlamali?

Eger Claude bu projede gelistirme yapacaksa su sirayla dusunmeli:

1. Degisiklik hangi katmanda?
   - upload
   - extraction
   - parser
   - chunking
   - embedding
   - evaluation
   - frontend
2. Bu degisiklik session state'i etkiliyor mu?
3. Analysis state JSON veya evaluation state JSON sekli degisiyor mu?
4. Retrieval kalitesi section match mantigina bagli mi?
5. Frontend polling davranisi buna uyumlu mu?
6. Yeni davranis debug sayfalarinda gozlenebilir mi?

Bu projede "sadece endpoint'e bir alan eklemek" bile zincirleme olarak:

- Pydantic modelleri
- store katmani
- frontend type'lari
- polling UI'lari
- evaluation rapor render'i

taraflarini etkileyebilir.

## 33. Claude icin hizli zihinsel model

Bu projeyi en kisa dogru sekilde su cumleyle dusunmek faydali:

"Bu repo, TUBITAK proje oneri PDF'lerini session bazli olarak alip once Docling ve custom parser/chunking pipeline'i ile yapilandiriyor, sonra bu chunk'lari local embedding + Chroma ile indeksliyor, en sonda rubric tabanli retrieval ve Ollama judge modeli ile kriter bazli puanlayip frontend'de ilerleme akisi ve nihai rapor olarak sunuyor."

## 34. Claude'a verilecek en pratik kisa ozet

Eger cok kisa bir ozet gerekirse su versiyon kullanilabilir:

> Bu proje FastAPI + Next.js tabanli bir TUBITAK proje oneri degerlendirme sistemi. Kullanici bir belge yukluyor, backend bunu session bazli sakliyor, PDF ise Docling ile extract ediyor, custom parser ile baslik hiyerarsisi ve content stream olusturuyor, chunking ile QA/narrative/table/list chunk'lara ayiriyor, `BAAI/bge-m3` ile embedding uretip Chroma'ya yaziyor. Sonra TUBITAK rubric'indeki her alt kriter icin once section-first ve semantic retrieval ile kanit topluyor, ardindan Ollama'daki `aya-expanse:8b` modeline sadece bu kanitlari verip 0-100 arasi Turkce JSON puanlama yaptiriyor. Sonuc frontend'de analiz adimlari, kanitlar ve nihai rapor olarak gosteriliyor.

## 35. Dosya referanslari

Claude'in once okumasini isteyecegin en kritik dosyalar:

- `README.md`
- `scripts/run_dev.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/api/router.py`
- `backend/app/services/upload/service.py`
- `backend/app/services/analysis/service.py`
- `backend/app/services/extraction/docling_extractor.py`
- `backend/app/services/extraction/parser.py`
- `backend/app/services/chunking/builders.py`
- `backend/app/services/embedding/provider.py`
- `backend/app/services/embedding/service.py`
- `backend/app/services/embedding/store.py`
- `backend/app/services/evaluation/retrieval.py`
- `backend/app/services/evaluation/provider.py`
- `backend/app/services/evaluation/service.py`
- `backend/app/services/evaluation/schemas/tubitak_default.json`
- `frontend/lib/session.ts`
- `frontend/lib/analysis.ts`
- `frontend/components/upload-panel/UploadPanel.tsx`
- `frontend/components/pages/evaluation/EvaluationWorkspace.tsx`
- `frontend/components/analysis/evaluation-panel/EvaluationPanel.tsx`

## 36. Son not

Bu proje AI destekli ama klasik bir "tek prompt -> tek cevap" sistemi degil. Asil degeri, belgeyi once yapisal hale getiren cok asamali pipeline'dan ve retrieval tabanli, rubric'e bagli, evidence-backed degerlendirme mantigindan geliyor.

Bu ayrim anlatilirsa Claude projeyi dogru kavrar; anlatilmazsa sistemi sadece "PDF'i modele verip puan yazdiran bir app" sanabilir, bu da yanlis olur.
