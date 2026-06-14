"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import {
  type CriterionEvaluationResult,
  type EvaluationState,
  type EvidenceChunk,
  fetchCurrentEvaluation,
  reportPdfDownloadUrl,
} from "../../../lib/analysis";
import { readSessionId, subscribeToSessionIdChange } from "../../../lib/session";
import styles from "./evaluation-panel.module.css";

type EvaluationReportViewerProps = Readonly<{
  apiBaseUrl: string;
  initialSessionId?: string | null;
}>;

type ReportDimension = {
  id: string;
  title: string;
  weight: number;
  score: number | null;
  weightedScore: number | null;
  summary: string;
  subcriteria: CriterionEvaluationResult[];
};

type RubricEntry = EvaluationState["rubric_table"][number];

type RubricGroup = {
  mainDimensionId: string;
  mainDimensionTitle: string;
  items: RubricEntry[];
};

const POLLING_INTERVAL_MS = 2500;

export function EvaluationReportViewer({
  apiBaseUrl,
  initialSessionId = null,
}: EvaluationReportViewerProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [evaluationState, setEvaluationState] = useState<EvaluationState | null>(null);
  const [error, setError] = useState("");
  const [isRubricOpen, setIsRubricOpen] = useState(false);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    let isCancelled = false;

    async function loadState(resolvedSessionId: string) {
      try {
        const nextState = await fetchCurrentEvaluation(apiBaseUrl, resolvedSessionId);
        if (!isCancelled) {
          setEvaluationState(nextState);
          setError("");
        }
      } catch (currentError) {
        if (!isCancelled) {
          setError(
            currentError instanceof Error
              ? currentError.message
              : "Evaluation raporu yüklenemedi.",
          );
        }
      }
    }

    function loadForSession(nextSessionId: string | null) {
      setSessionId(nextSessionId);
      setEvaluationState(null);
      setIsRubricOpen(false);

      if (!nextSessionId) {
        setError("Aktif bir evaluation oturumu bulunamadı.");
        return;
      }

      void loadState(nextSessionId);
    }

    loadForSession(initialSessionId ?? readSessionId());

    if (initialSessionId) {
      return () => {
        isCancelled = true;
      };
    }

    const unsubscribe = subscribeToSessionIdChange((nextSessionId) => {
      if (!isCancelled) {
        loadForSession(nextSessionId);
      }
    });

    return () => {
      isCancelled = true;
      unsubscribe();
    };
  }, [apiBaseUrl, initialSessionId]);

  useEffect(() => {
    if (!sessionId || !evaluationState || !isEvaluationRunning(evaluationState.status)) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void fetchCurrentEvaluation(apiBaseUrl, sessionId)
        .then((nextState) => {
          setEvaluationState(nextState);
          setError("");
        })
        .catch((currentError) => {
          setError(
            currentError instanceof Error
              ? currentError.message
              : "Evaluation raporu güncellenemedi.",
          );
        });
    }, POLLING_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [apiBaseUrl, evaluationState, sessionId]);

  useEffect(() => {
    if (!isRubricOpen || !isClient) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsRubricOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isClient, isRubricOpen]);

  const dimensions = useMemo(() => buildReportDimensions(evaluationState), [evaluationState]);
  const rubricGroups = useMemo(
    () => buildRubricGroups(evaluationState?.rubric_table ?? []),
    [evaluationState],
  );
  const evidenceCount = useMemo(() => countEvidenceItems(evaluationState), [evaluationState]);
  const reportAvailable = Boolean(
    evaluationState?.subcriteria_results.length ||
      evaluationState?.main_scores.length ||
      evaluationState?.rubric_table.length,
  );
  const rubricModal = isRubricOpen ? (
    <div
      className={styles.rubricModalBackdrop}
      onClick={() => setIsRubricOpen(false)}
      role="presentation"
    >
      <div
        className={styles.rubricModal}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Rubric açıklama paneli"
      >
        <div className={styles.rubricModalHeader}>
          <div>
            <p className={styles.rubricSummaryEyebrow}>RUBRIC DETAYI</p>
            <h4 className={styles.rubricModalTitle}>Değerlendirme Kriterleri</h4>
          </div>
          <button
            type="button"
            className={styles.rubricCloseButton}
            onClick={() => setIsRubricOpen(false)}
          >
            Kapat
          </button>
        </div>

        <div className={styles.rubricMainGrid}>
          {rubricGroups.map((group) => (
            <article key={`${group.mainDimensionId}-overview`} className={styles.rubricMainCard}>
              <span className={styles.rubricGroupId}>{group.mainDimensionId}</span>
              <div>
                <h5 className={styles.rubricGroupTitle}>{group.mainDimensionTitle}</h5>
                <p className={styles.rubricGroupMeta}>{group.items.length} alt kriter</p>
              </div>
            </article>
          ))}
        </div>

        <div className={styles.rubricGroupList}>
          {rubricGroups.map((group) => (
            <article key={group.mainDimensionId} className={styles.rubricGroupCard}>
              <div className={styles.rubricGroupHeader}>
                <span className={styles.rubricGroupId}>{group.mainDimensionId}</span>
                <div>
                  <h5 className={styles.rubricGroupTitle}>{group.mainDimensionTitle}</h5>
                  <p className={styles.rubricGroupMeta}>Ana kriter · {group.items.length} alt kriter</p>
                </div>
              </div>

              <p className={styles.rubricSubcriteriaLabel}>Alt kriterler</p>
              <div className={styles.rubricItemList}>
                {group.items.map((item) => (
                  <article key={item.criterion_id} className={styles.rubricItemCard}>
                    <div className={styles.rubricItemTop}>
                      <div>
                        <p className={styles.rubricItemEyebrow}>
                          {item.ui_label || item.criterion_id}
                        </p>
                        <h6 className={styles.rubricItemTitle}>{item.criterion_title}</h6>
                      </div>
                      <span className={styles.rubricRangePill}>
                        {item.score_min}-{item.score_max} puan
                      </span>
                    </div>
                    <p className={styles.rubricItemDescription}>{item.description}</p>
                    <p className={styles.rubricItemExplanation}>{item.ui_explanation}</p>
                    <div className={styles.rubricSectionChipWrap}>
                      {item.source_sections.map((section) => (
                        <span
                          key={`${item.criterion_id}-${section}`}
                          className={styles.rubricSectionChip}
                        >
                          {formatSourceSectionLabel(section)}
                        </span>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </article>
          ))}
        </div>

        <div className={styles.scoreScaleCard}>
          <div className={styles.scoreScaleHeader}>
            <h5 className={styles.scoreScaleTitle}>Puanlama ölçeği</h5>
            <p className={styles.scoreScaleText}>
              Alt kriterler doğrudan 0-100 arası puanlanır. Ana boyut skoru bu alt
              kriterlerin eşit ağırlıklı ortalamasıdır. Genel skor ise ana boyut
              yüzdelerinin ağırlıklı birleşimidir.
            </p>
          </div>
          <div className={styles.scoreScaleGrid}>
            <ScalePill label="0-19" text="Kanıt yok veya iddia ikna edici değil." />
            <ScalePill label="20-39" text="Zayıf, eksik veya çok sınırlı kanıt." />
            <ScalePill label="40-59" text="Orta düzey, kısmen ikna edici." />
            <ScalePill label="60-79" text="Güçlü ama bazı boşluklar içeriyor." />
            <ScalePill label="80-100" text="Çok güçlü, açık ve iyi kanıtlanmış." />
          </div>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <section className={styles.panel}>
      {error ? <p className={styles.errorText}>{error}</p> : null}

      <section className={styles.heroCard}>
        <div className={styles.heroScore}>
          <p className={styles.heroLabel}>Genel Skor</p>
          <p className={styles.heroValue}>{formatScore(evaluationState?.overall_score, 100)}</p>
        </div>
        <div className={styles.heroEvidence}>
          <span className={styles.heroEvidenceLabel}>Belge Kanıtı</span>
          <strong className={styles.heroEvidenceValue}>
            {evidenceCount === null ? "-" : evidenceCount}
          </strong>
          <span className={styles.heroEvidenceText}>kanıt</span>
        </div>
        {evaluationState?.final_report && sessionId ? (
          <a
            className={styles.heroDownloadButton}
            href={reportPdfDownloadUrl(apiBaseUrl, sessionId)}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span aria-hidden="true">⬇</span> PDF İndir
          </a>
        ) : null}
      </section>

      <section className={styles.mainScoreSection}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>Ana Boyut Skorları</h3>
          <p className={styles.sectionDescription}>
            Ana skorlar alt kriter puanlarının eşit ağırlıklı ortalamasından hesaplanır.
            Genel skorda ise sadece ana boyut yüzdeleri uygulanır.
          </p>
        </div>
        <div className={styles.scoreGrid}>
          {(evaluationState?.main_scores ?? []).map((item) => (
            <article key={item.main_dimension_id} className={styles.scoreCard}>
              <div className={styles.scoreCardTop}>
                <span className={styles.scoreCardId}>{item.main_dimension_id}</span>
                <span className={styles.scoreCardWeight}>Ağırlık %{item.weight}</span>
              </div>
              <h4 className={styles.scoreCardTitle}>{item.title}</h4>
              <p className={styles.scoreCardValue}>{formatScore(item.score, 100)}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.tableSection}>
        <div className={styles.rubricSummaryCopy}>
          <h3 className={styles.sectionTitle}>Rubric Detayı</h3>
          <p className={styles.sectionDescription}>
            Puan aralıkları ve kaynak bölüm eşleştirmeleri.
          </p>
        </div>
        <button
          type="button"
          className={styles.rubricButton}
          onClick={() => setIsRubricOpen(true)}
        >
          İncele
        </button>
      </section>

      {isClient && rubricModal ? createPortal(rubricModal, document.body) : null}

      {reportAvailable ? (
        <section className={styles.accordionSection}>
          <div className={styles.sectionHeader}>
            <h3 className={styles.sectionTitle}>Ana Boyut İncelemesi</h3>
            <p className={styles.sectionDescription}>
              Her ana boyut altında kriterin beklentisi, bu projedeki değerlendirme,
              bulgular ve belge kanıtları birlikte sunulur.
            </p>
          </div>

          <div className={styles.accordionList}>
            {dimensions.map((dimension) => (
              <details key={dimension.id} className={styles.dimensionAccordion}>
                <summary className={styles.dimensionSummary}>
                  <div className={styles.dimensionSummaryCopy}>
                    <p className={styles.dimensionEyebrow}>
                      {dimension.id} Boyutu · %{dimension.weight}
                    </p>
                    <h4 className={styles.dimensionTitle}>{dimension.title}</h4>
                    <p className={styles.dimensionText}>{dimension.summary}</p>
                  </div>
                  <div className={styles.dimensionSummaryAside}>
                    <div className={styles.dimensionScoreBlock}>
                      <span className={styles.dimensionScore}>
                        {formatScore(dimension.score, 100)}
                      </span>
                      <span className={styles.dimensionScoreMeta}>
                        Ağırlıklı katkı {formatWeightedContribution(dimension.weightedScore)}
                      </span>
                    </div>
                    <span className={styles.expandHint}>Detayı aç</span>
                  </div>
                </summary>

                <div className={styles.subcriterionList}>
                  {dimension.subcriteria.map((criterion) => (
                    <SubcriterionCard key={criterion.criterion_id} criterion={criterion} />
                  ))}
                </div>
              </details>
            ))}
          </div>
        </section>
      ) : (
        <div className={styles.emptyState}>
          <p>Henüz gösterilecek rapor verisi oluşmadı.</p>
          <p>Evaluation tamamlandığında tüm ana boyutlar ve alt kriter kartları burada açılacak.</p>
        </div>
      )}
    </section>
  );
}

function formatSourceSectionLabel(section: string) {
  const normalized = section.trim();

  const sectionLabels: Record<string, string> = {
    "A.2": "A.2 > Kuruluş Bilgileri",
    "A.3": "A.3 > Proje Kısa Tanıtımı",
    "B.1": "B.1 > Çağrı Konusuyla İlişki ve Hedefler",
    "B.2": "B.2 > Projenin Teknoloji Düzeyi",
    "B.3": "B.3 > Somut / Ölçülebilir Hedefler ve Çözüm Yaklaşımı",
    "B.4": "B.4 > Projenin Yenilikçi Yönleri",
    "C.1": "C.1 > İş Planı",
    "C.2": "C.2 > Proje Yönetimi ve Organizasyonu",
    "C.3": "C.3 > Kuruluş Altyapısı",
    "D.1": "D.1 > Ekonomik Öngörüler",
    "D.2": "D.2 > Ulusal Kazanımlar",
    E: "E > Risk ve Finansman Yapısı",
    F: "F > Proje Bütçesi",
  };

  if (normalized in sectionLabels) {
    return sectionLabels[normalized] ?? normalized;
  }

  if (normalized === "ÜRÜN SATIŞI VE TİCARİLEŞME ÖNGÖRÜLERİ") {
    return "C.3 > Ürün Satışı ve Ticarileşme Öngörüleri";
  }

  if (normalized === "PAZAR FIRSATI") {
    return "C.3 > Pazar Fırsatı";
  }

  if (normalized === "KAYNAK YÖNETİMİ") {
    return "C.3 > Kaynak Yönetimi";
  }

  if (normalized === "Ekonomik ve Ulusal Kazanımlar") {
    return "A.3 > Proje Kısa Tanıtımı > Ekonomik ve Ulusal Kazanımlar";
  }

  if (
    normalized ===
    "Projenin sağlayabileceği ulusal kazanımları, aşağıdaki başlıklardan ilgili gördüklerinizi dikkate alarak belirtiniz."
  ) {
    return "D.2 > Ulusal Kazanımlar";
  }

  return normalized;
}

function formatUserFacingText(value: string) {
  return value
    .replaceAll("Judge response did not match schema", "Judge yanıtı beklenen şemaya uymadı")
    .replaceAll("Judge response could not be parsed.", "Judge yanıtı ayrıştırılamadı.")
    .replaceAll("Field required", "Alan zorunlu")
    .replaceAll("For further information visit", "Ayrıntı için ziyaret edin")
    .replaceAll("validation errors for CriterionJudgeResponse", "CriterionJudgeResponse için doğrulama hataları")
    .replaceAll("input_value", "gelen_deger")
    .replaceAll("input_type", "gelen_tip");
}

function SubcriterionCard({
  criterion,
}: Readonly<{
  criterion: CriterionEvaluationResult;
}>) {
  const evidenceByChunkId = buildCriterionEvidenceMap(criterion);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  useEffect(() => {
    if (!isDetailOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsDetailOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isDetailOpen]);

  return (
    <article className={styles.subcriterionAccordion}>
      <button
        type="button"
        className={styles.subcriterionSummary}
        onClick={() => setIsDetailOpen(true)}
        aria-haspopup="dialog"
      >
        <div>
          <p className={styles.subcriterionEyebrow}>
            {criterion.main_dimension_id ?? criterion.category ?? "?"} · {criterion.criterion_id}
          </p>
          <h5 className={styles.subcriterionTitle}>{criterion.title}</h5>
          <p className={styles.subcriterionText}>
            {formatUserFacingText(
              criterion.short_assessment || criterion.justification || "Kısa değerlendirme bulunamadı.",
            )}
          </p>
        </div>
        <div className={styles.subcriterionSummaryAside}>
          <div className={styles.metricPillGrid}>
            <MetricPill label="Skor" value={formatScore(criterion.score, 100)} accent />
            <MetricPill label="Kanıt Durumu" value={getCoverageStatusLabel(criterion.coverage_status)} />
            <MetricPill label="Güven" value={formatConfidence(criterion.confidence)} />
          </div>
          <span className={styles.expandHint}>Alt kriteri aç</span>
        </div>
      </button>

      {isDetailOpen
        ? createPortal(
            <div
              className={styles.criterionModalBackdrop}
              onClick={() => setIsDetailOpen(false)}
              role="presentation"
            >
              <div
                className={styles.criterionModal}
                onClick={(event) => event.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-label={`${criterion.title} detayı`}
              >
                <div className={styles.criterionModalHeader}>
                  <div className={styles.criterionModalTitleWrap}>
                    <p className={styles.subcriterionEyebrow}>
                      {criterion.main_dimension_id ?? criterion.category ?? "?"} · {criterion.criterion_id}
                    </p>
                    <h5 className={styles.criterionModalTitle}>{criterion.title}</h5>
                  </div>
                  <button
                    type="button"
                    className={styles.criterionCloseButton}
                    onClick={() => setIsDetailOpen(false)}
                  >
                    Kapat
                  </button>
                </div>

                <article className={styles.subcriterionCard}>
        <div className={styles.subcriterionMetaRow}>
          <span className={styles.statusChip}>{getDecisionLabel(criterion.decision_status)}</span>
          {criterion.is_salvaged ? (
            <span
              className={styles.salvageChip}
              title="Model bu kriter için kullanılabilir bir yanıt üretemedi; kriter eldeki kanıtlardan otomatik tamamlandı."
            >
              ⓘ Otomatik tamamlandı
            </span>
          ) : null}
          <span className={styles.metaChip}>Alt kriter etkisi: eşit</span>
          <span className={styles.metaChip}>Kapsama: {getCoverageStatusLabel(criterion.coverage_status)}</span>
        </div>

        <div className={styles.explanationCard}>
          <p className={styles.explanationLabel}>Değerlendirme</p>
          <div className={styles.explanationGrid}>
            <div className={styles.explanationBlock}>
              <p className={styles.explanationSubLabel}>Kriterin beklentisi</p>
              <p className={styles.explanationBody}>
                {formatUserFacingText(
                  criterion.criterion_explanation || criterion.justification || "Açıklama bulunamadı.",
                )}
              </p>
            </div>
            <div className={styles.explanationBlock}>
              <p className={styles.explanationSubLabel}>Bu projedeki değerlendirme</p>
              <p className={styles.explanationBody}>
                {formatUserFacingText(criterion.short_assessment || "Kısa değerlendirme bulunamadı.")}
              </p>
            </div>
          </div>
          <div className={styles.assessmentMetrics}>
            <MetricPill label="İddia Gücü" value={formatScore(criterion.claim_strength, 100)} />
            <MetricPill label="Kanıt Kalitesi" value={formatScore(criterion.evidence_quality, 100)} />
          </div>
        </div>

        <section className={styles.findingsSection}>
          <div className={styles.sectionHeaderCompact}>
            <h6 className={styles.evidenceSectionTitle}>Bulgular</h6>
            <p className={styles.evidenceSectionText}>
              Modelin vardığı sonucu destekleyen, zayıflatan veya tamamlanması gereken noktalar.
            </p>
          </div>
          <div className={styles.narrativeGrid}>
            <FindingPanel
              title="Olumlu Bulgular"
              tone="positive"
              items={criterion.positive_findings}
              evidenceByChunkId={evidenceByChunkId}
              emptyText="Olumlu bulgu çıkarılmadı."
            />
            <FindingPanel
              title="Zayıflatan Bulgular"
              tone="danger"
              items={criterion.negative_findings}
              evidenceByChunkId={evidenceByChunkId}
              emptyText="Zayıflatan bulgu çıkarılmadı."
            />
          </div>

          <div className={styles.narrativeGrid}>
            <InfoPanel
              title="Eksik Bilgiler"
              tone="warning"
              items={criterion.missing_information}
              emptyText="Eksik bilgi işaretlenmedi."
            />
            <InfoPanel
              title="Risk İşaretleri"
              tone="danger"
              items={criterion.red_flags}
              emptyText="Risk işareti yok."
            />
          </div>
        </section>

        {criterion.coverage_notes.length ? (
          <div className={styles.coverageCard}>
            <p className={styles.coverageTitle}>Kapsama Notları</p>
            <ul className={styles.inlineList}>
              {criterion.coverage_notes.map((item, index) => (
                <li key={`${criterion.criterion_id}-coverage-${index}`}>{formatUserFacingText(item)}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className={styles.evidenceSection}>
          <div className={styles.sectionHeaderCompact}>
            <h6 className={styles.evidenceSectionTitle}>Kanıt Kartları</h6>
            <p className={styles.evidenceSectionText}>
              Her kartta belge kaynağı, doğrudan alıntı ve bu alıntının değerlendirmeye etkisi yer alır.
            </p>
          </div>
          {criterion.evidence_items.length ? (
            <div className={styles.evidenceGrid}>
              {criterion.evidence_items.map((item) => (
                <EvidenceCard
                  key={`${criterion.criterion_id}-${item.chunk_id}-${item.evidence_type}`}
                  item={item}
                />
              ))}
            </div>
          ) : (
            <p className={styles.emptyEvidence}>Kanıt kartı bulunamadı.</p>
          )}
        </div>

        <ReviewedEvidenceSection criterion={criterion} />
                </article>
              </div>
            </div>,
            document.body,
          )
        : null}
    </article>
  );
}

function ReviewedEvidenceSection({
  criterion,
}: Readonly<{ criterion: CriterionEvaluationResult }>) {
  const reviewed = useMemo(() => collectReviewedEvidence(criterion), [criterion]);
  if (!reviewed.length) {
    return null;
  }
  return (
    <div className={styles.reviewedSection}>
      <div className={styles.sectionHeaderCompact}>
        <h6 className={styles.evidenceSectionTitle}>İncelenen Kanıtlar ({reviewed.length})</h6>
        <p className={styles.evidenceSectionText}>
          Bu kriter için belgeden getirilen tüm kanıtlar. Modelin doğrudan atıf yaptıkları
          işaretlidir; geri kalanlar bağlam olarak incelenmiştir.
        </p>
      </div>
      <ul className={styles.reviewedList}>
        {reviewed.map((entry) => (
          <li key={entry.chunk.chunk_id} className={styles.reviewedItem}>
            <div className={styles.reviewedItemTop}>
              <span className={styles.reviewedTypeBadge}>
                {getChunkTypeLabel(entry.chunk.chunk_type)}
              </span>
              {entry.cited ? (
                <span className={styles.reviewedCitedBadge}>✓ Modelce kullanıldı</span>
              ) : (
                <span className={styles.reviewedContextBadge}>Bağlam</span>
              )}
            </div>
            <p className={styles.reviewedLocation}>
              {formatEvidenceLocation(
                entry.chunk.heading_path_titles,
                entry.chunk.page_start,
                entry.chunk.page_end,
              )}
            </p>
            <p className={styles.reviewedText}>
              {clampText(formatUserFacingText(entry.chunk.text_for_embedding), 240)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EvidenceCard({
  item,
}: Readonly<{
  item: CriterionEvaluationResult["evidence_items"][number];
}>) {
  return (
    <article
      className={`${styles.evidenceCard} ${styles[`evidenceCard${capitalize(item.evidence_type)}`]}`}
    >
      <div className={styles.evidenceSummary}>
        <div>
          <span className={styles.evidenceType}>{getEvidenceTypeLabel(item.evidence_type)}</span>
          <p className={styles.evidenceLocationCompact}>
            {formatCompactLocation(item.heading_path)}
          </p>
        </div>
      </div>
      <div className={styles.evidenceBody}>
        <div className={styles.evidenceField}>
          <p className={styles.evidenceFieldLabel}>Kaynak</p>
          <p className={styles.evidenceLocation}>
            {formatEvidenceLocation(item.heading_path, item.page_start, item.page_end)}
          </p>
        </div>
        <div className={styles.evidenceField}>
          <p className={styles.evidenceFieldLabel}>Belgeden alıntı</p>
          <blockquote className={styles.evidenceQuote}>
            {formatUserFacingText(item.verbatim_excerpt)}
          </blockquote>
        </div>
        <div className={styles.evidenceField}>
          <p className={styles.evidenceFieldLabel}>Değerlendirmeye etkisi</p>
          <p className={styles.evidenceWhy}>{formatUserFacingText(item.why_it_matters)}</p>
        </div>
      </div>
    </article>
  );
}

function FindingPanel({
  title,
  items,
  emptyText,
  tone,
  evidenceByChunkId,
}: Readonly<{
  title: string;
  items: CriterionEvaluationResult["positive_findings"] | CriterionEvaluationResult["negative_findings"];
  emptyText: string;
  tone: "positive" | "warning" | "danger";
  evidenceByChunkId: Map<string, CriterionEvaluationResult["evidence_items"][number]>;
}>) {
  return (
    <div className={`${styles.infoPanel} ${styles[`infoPanel${capitalize(tone)}`]}`}>
      <p className={styles.infoPanelTitle}>{title}</p>
      {items.length ? (
        <div className={styles.findingList}>
          {items.map((item, index) => {
            const evidence = evidenceByChunkId.get(item.chunk_id);
            const reason = item.why_positive ?? item.why_negative ?? null;
            const quote = item.quote ?? evidence?.verbatim_excerpt ?? null;
            return (
              <article key={`${title}-${index}-${item.chunk_id}`} className={styles.findingCard}>
                {evidence ? (
                  <p className={styles.findingLocation}>
                    {formatCompactLocation(evidence.heading_path)}
                  </p>
                ) : null}
                <p className={styles.findingText}>{formatUserFacingText(item.summary)}</p>
                {reason ? (
                  <p className={styles.findingReason}>{formatUserFacingText(reason)}</p>
                ) : null}
                {quote ? (
                  <blockquote className={styles.findingQuote}>
                    {clampText(formatUserFacingText(quote), 180)}
                  </blockquote>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : (
        <p className={styles.infoPanelEmpty}>{emptyText}</p>
      )}
    </div>
  );
}

function InfoPanel({
  title,
  items,
  emptyText,
  tone,
}: Readonly<{
  title: string;
  items: string[];
  emptyText: string;
  tone: "positive" | "warning" | "danger";
}>) {
  return (
    <div className={`${styles.infoPanel} ${styles[`infoPanel${capitalize(tone)}`]}`}>
      <p className={styles.infoPanelTitle}>{title}</p>
      {items.length ? (
        <ul className={styles.inlineList}>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{formatUserFacingText(item)}</li>
          ))}
        </ul>
      ) : (
        <p className={styles.infoPanelEmpty}>{emptyText}</p>
      )}
    </div>
  );
}

function MetricPill({
  label,
  value,
  accent = false,
}: Readonly<{
  label: string;
  value: string;
  accent?: boolean;
}>) {
  return (
    <div className={`${styles.metricPill} ${accent ? styles.metricPillAccent : ""}`}>
      <span className={styles.metricLabel}>{label}</span>
      <span className={styles.metricValue}>{value}</span>
    </div>
  );
}

function ScalePill({
  label,
  text,
}: Readonly<{
  label: string;
  text: string;
}>) {
  return (
    <div className={styles.scalePill}>
      <span className={styles.scalePillLabel}>{label}</span>
      <p className={styles.scalePillText}>{text}</p>
    </div>
  );
}

function buildReportDimensions(evaluationState: EvaluationState | null): ReportDimension[] {
  if (!evaluationState) {
    return [];
  }

  const titleByDimension = new Map(
    evaluationState.main_scores.map((item) => [item.main_dimension_id, item.title]),
  );

  const subcriteriaByDimension = new Map<string, CriterionEvaluationResult[]>();
  for (const item of evaluationState.subcriteria_results) {
    const key = item.main_dimension_id ?? item.category ?? "unknown";
    const current = subcriteriaByDimension.get(key) ?? [];
    current.push(item);
    subcriteriaByDimension.set(key, current);
  }

  return evaluationState.main_scores
    .map((item) => ({
      id: item.main_dimension_id,
      title: item.title,
      weight: item.weight,
      score: item.score,
      weightedScore: item.weighted_score,
      summary: item.summary,
      subcriteria: subcriteriaByDimension.get(item.main_dimension_id) ?? [],
    }))
    .concat(
      [...subcriteriaByDimension.entries()]
        .filter(([dimensionId]) => !titleByDimension.has(dimensionId))
        .map(([dimensionId, subcriteria]) => ({
          id: dimensionId,
          title: dimensionId,
          weight: 0,
          score: null,
          weightedScore: null,
          summary: "Bu boyut için henüz hesaplanmış skor özeti bulunamadı.",
          subcriteria,
        })),
    );
}

function buildRubricGroups(entries: EvaluationState["rubric_table"]): RubricGroup[] {
  const grouped = new Map<string, RubricGroup>();

  entries.forEach((item) => {
    const current = grouped.get(item.main_dimension_id);
    if (current) {
      current.items.push(item);
      return;
    }

    grouped.set(item.main_dimension_id, {
      mainDimensionId: item.main_dimension_id,
      mainDimensionTitle: item.main_dimension_title,
      items: [item],
    });
  });

  return Array.from(grouped.values());
}

function buildCriterionEvidenceMap(criterion: CriterionEvaluationResult) {
  return new Map(criterion.evidence_items.map((item) => [item.chunk_id, item]));
}

function countEvidenceItems(evaluationState: EvaluationState | null) {
  if (!evaluationState) {
    return null;
  }

  return evaluationState.subcriteria_results.reduce(
    (total, item) => total + item.evidence_items.length,
    0,
  );
}

function isEvaluationRunning(status: EvaluationState["status"]) {
  return (
    status === "queued" ||
    status === "retrieving" ||
    status === "evaluating" ||
    status === "aggregating"
  );
}

function getDecisionLabel(status: CriterionEvaluationResult["decision_status"]) {
  if (status === "scored") {
    return "Puanlandı";
  }
  if (status === "insufficient_evidence") {
    return "Kanıt yetersiz";
  }
  if (status === "conflicting_evidence") {
    return "Kanıt çelişkili";
  }
  return "Başarısız";
}

function getCoverageStatusLabel(status: CriterionEvaluationResult["coverage_status"]) {
  if (status === "complete") {
    return "Tam";
  }
  if (status === "covered") {
    return "Karşılandı";
  }
  if (status === "partial") {
    return "Kısmi";
  }
  if (status === "missing") {
    return "Eksik";
  }
  return "Bilinmiyor";
}

function getEvidenceTypeLabel(
  type: CriterionEvaluationResult["evidence_items"][number]["evidence_type"],
) {
  if (type === "positive") {
    return "Destekleyici Kanıt";
  }
  if (type === "negative") {
    return "Zayıflatan Kanıt";
  }
  return "Bağlam";
}

function getChunkTypeLabel(type: EvidenceChunk["chunk_type"]) {
  switch (type) {
    case "table":
      return "📊 Tablo";
    case "list":
      return "• Liste";
    case "qa":
      return "❓ Soru-Cevap";
    default:
      return "¶ Anlatı";
  }
}

type ReviewedEvidenceEntry = { chunk: EvidenceChunk; cited: boolean };

function collectReviewedEvidence(
  criterion: CriterionEvaluationResult,
): ReviewedEvidenceEntry[] {
  const citedIds = new Set<string>([
    ...criterion.evidence_items.map((item) => item.chunk_id),
    ...criterion.positive_findings.map((item) => item.chunk_id),
    ...criterion.negative_findings.map((item) => item.chunk_id),
  ]);
  // Tier önceliği primary > semantic > fallback; aynı chunk yalnızca bir kez gösterilir.
  const ordered: EvidenceChunk[] = [
    ...criterion.primary_section_chunks,
    ...criterion.semantic_support_chunks,
    ...criterion.fallback_context_chunks,
  ];
  const seen = new Set<string>();
  const entries: ReviewedEvidenceEntry[] = [];
  for (const chunk of ordered) {
    if (seen.has(chunk.chunk_id)) {
      continue;
    }
    seen.add(chunk.chunk_id);
    entries.push({ chunk, cited: citedIds.has(chunk.chunk_id) });
  }
  return entries;
}

function formatScore(value: number | null | undefined, scale: number) {
  if (value === null || value === undefined) {
    return "-";
  }
  const rendered = Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
  return `${rendered}/${scale}`;
}

function formatWeightedContribution(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  const rendered = Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
  return `${rendered} puan`;
}

function formatConfidence(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${Math.round(value * 100)}%`;
}

function formatEvidenceLocation(
  headingPath: string[],
  pageStart: number | null,
  pageEnd: number | null,
) {
  const headingText = headingPath.length ? headingPath.join(" > ") : "Belirsiz bölüm";
  if (pageStart === null && pageEnd === null) {
    return headingText;
  }
  if (pageStart === pageEnd) {
    return `${headingText} · Sayfa ${pageStart}`;
  }
  return `${headingText} · Sayfa ${pageStart}-${pageEnd}`;
}

function formatCompactLocation(headingPath: string[]) {
  if (!headingPath.length) {
    return "Belirsiz bölüm";
  }

  const tail = headingPath.slice(-2);
  return tail.join(" · ");
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function clampText(value: string, max: number) {
  const collapsed = value.trim();
  if (collapsed.length <= max) {
    return collapsed;
  }
  return `${collapsed.slice(0, max).trimEnd()}…`;
}
