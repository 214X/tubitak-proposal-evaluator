"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type CriterionEvaluationResult,
  type EvaluationState,
  fetchCurrentEvaluation,
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

const POLLING_INTERVAL_MS = 2500;

export function EvaluationReportViewer({
  apiBaseUrl,
  initialSessionId = null,
}: EvaluationReportViewerProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [evaluationState, setEvaluationState] = useState<EvaluationState | null>(null);
  const [error, setError] = useState("");

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

  const dimensions = useMemo(() => buildReportDimensions(evaluationState), [evaluationState]);
  const reportAvailable = Boolean(
    evaluationState?.subcriteria_results.length ||
      evaluationState?.main_scores.length ||
      evaluationState?.rubric_table.length,
  );

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.headerCopy}>
          <p className={styles.eyebrow}>DEĞERLENDİRME RAPORU</p>
          <h2 className={styles.title}>TÜBİTAK Uyumlu Kriter ve Kanıt Raporu</h2>
          <p className={styles.description}>
            Bu ekran genel skoru, ana boyut skorlarını, rubric açıklamalarını ve her alt
            kriter için iddia-kanıt ilişkisini öğretici biçimde gösterir.
          </p>
        </div>
        <div className={styles.headerMeta}>
          {sessionId ? <p className={styles.session}>Oturum: {sessionId}</p> : null}
          <div className={styles.statusBadge}>{getStatusLabel(evaluationState)}</div>
        </div>
      </div>

      {error ? <p className={styles.errorText}>{error}</p> : null}

      <section className={styles.heroCard}>
        <div className={styles.heroScore}>
          <p className={styles.heroLabel}>Genel Skor</p>
          <p className={styles.heroValue}>{formatScore(evaluationState?.overall_score, 100)}</p>
          <p className={styles.heroMeta}>
            {evaluationState?.active_subcriterion_title
              ? `Son işlenen alt kriter: ${evaluationState.active_subcriterion_title}`
              : "Alt kriter bazlı matematiksel agregasyon"}
          </p>
        </div>

        <div className={styles.heroInsights}>
          <InfoList
            title="Öne Çıkan Güçlü Alanlar"
            items={evaluationState?.major_strengths ?? []}
            emptyText="Belirgin güçlü alan henüz çıkarılamadı."
          />
          <InfoList
            title="Önemli Zayıflıklar"
            items={evaluationState?.major_weaknesses ?? []}
            emptyText="Belirgin zayıf alan henüz çıkarılamadı."
          />
        </div>
      </section>

      <section className={styles.mainScoreSection}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>Ana Boyut Skorları</h3>
          <p className={styles.sectionDescription}>
            Ana skorlar alt kriter puanlarının ağırlıklı ortalamasından hesaplanır.
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
              <p className={styles.scoreCardMeta}>
                {item.scored_subcriteria_count}/{item.subcriteria_count} alt kriter puanlandı
              </p>
              <p className={styles.scoreCardSummary}>{item.summary}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.supportSection}>
        <InfoPanel
          title="Kritik Eksik Bilgiler"
          tone="warning"
          items={evaluationState?.critical_missing_information ?? []}
          emptyText="Kritik eksik bilgi listelenmedi."
        />
        <InfoPanel
          title="Risk İşaretleri"
          tone="danger"
          items={evaluationState?.red_flags ?? []}
          emptyText="Belirgin risk işareti listelenmedi."
        />
      </section>

      <section className={styles.tableSection}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>Rubric Açıklama Tablosu</h3>
          <p className={styles.sectionDescription}>
            Alt kriterlerin neden önemli olduğu ve hangi bölüm kaynaklarına baktığı bu tabloyla
            özetlenir.
          </p>
        </div>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Ana Boyut</th>
                <th>Alt Kriter</th>
                <th>Ağırlık</th>
                <th>Kaynak Bölümler</th>
                <th>Açıklama</th>
              </tr>
            </thead>
            <tbody>
              {(evaluationState?.rubric_table ?? []).map((item) => (
                <tr key={item.criterion_id}>
                  <td>
                    <strong>{item.main_dimension_id}</strong>
                    <span className={styles.tableSubtext}>{item.main_dimension_title}</span>
                  </td>
                  <td>
                    <strong>{item.ui_label || item.criterion_id}</strong>
                    <span className={styles.tableSubtext}>{item.criterion_title}</span>
                  </td>
                  <td>%{item.weight}</td>
                  <td>{item.source_sections.map(formatSourceSectionLabel).join(", ")}</td>
                  <td>{item.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {reportAvailable ? (
        <section className={styles.accordionSection}>
          <div className={styles.sectionHeader}>
            <h3 className={styles.sectionTitle}>Ana Boyut İncelemesi</h3>
            <p className={styles.sectionDescription}>
              Her accordion içinde alt kriterler, bulgular ve birebir kanıt alıntıları yer alır.
            </p>
          </div>

          <div className={styles.accordionList}>
            {dimensions.map((dimension, index) => (
              <details
                key={dimension.id}
                className={styles.dimensionAccordion}
                open={index === 0}
              >
                <summary className={styles.dimensionSummary}>
                  <div>
                    <p className={styles.dimensionEyebrow}>
                      {dimension.id} Boyutu · %{dimension.weight}
                    </p>
                    <h4 className={styles.dimensionTitle}>{dimension.title}</h4>
                    <p className={styles.dimensionText}>{dimension.summary}</p>
                  </div>
                  <div className={styles.dimensionScoreBlock}>
                    <span className={styles.dimensionScore}>
                      {formatScore(dimension.score, 100)}
                    </span>
                    <span className={styles.dimensionScoreMeta}>
                      Ağırlıklı katkı {formatWeightedContribution(dimension.weightedScore)}
                    </span>
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
    return "A.4.1 > Ekonomik ve Ulusal Kazanımlar";
  }

  if (
    normalized ===
    "Projenin sağlayabileceği ulusal kazanımları, aşağıdaki başlıklardan ilgili gördüklerinizi dikkate alarak belirtiniz."
  ) {
    return "C.3 > Ürün Satışı ve Ticarileşme Öngörüleri > 2.7 Ulusal Kazanımlar";
  }

  return normalized;
}

function SubcriterionCard({
  criterion,
}: Readonly<{
  criterion: CriterionEvaluationResult;
}>) {
  return (
    <article className={styles.subcriterionCard}>
      <div className={styles.subcriterionHeader}>
        <div>
          <p className={styles.subcriterionEyebrow}>
            {criterion.main_dimension_id ?? criterion.category ?? "?"} · {criterion.criterion_id}
          </p>
          <h5 className={styles.subcriterionTitle}>{criterion.title}</h5>
          <p className={styles.subcriterionText}>
            {criterion.criterion_explanation || criterion.justification || "Açıklama bulunamadı."}
          </p>
        </div>
        <div className={styles.metricPillGrid}>
          <MetricPill label="Skor" value={formatScore(criterion.score, 5)} accent />
          <MetricPill
            label="İddia Gücü"
            value={formatScore(criterion.claim_strength, 5)}
          />
          <MetricPill
            label="Kanıt Kalitesi"
            value={formatScore(criterion.evidence_quality, 5)}
          />
          <MetricPill
            label="Güven"
            value={criterion.confidence.toFixed(2)}
          />
        </div>
      </div>

      <div className={styles.subcriterionMetaRow}>
        <span className={styles.statusChip}>{getDecisionLabel(criterion.decision_status)}</span>
        <span className={styles.metaChip}>Ağırlık %{criterion.weight}</span>
        <span className={styles.metaChip}>
          Coverage: {criterion.coverage_status}
        </span>
      </div>

      <div className={styles.narrativeGrid}>
        <InfoPanel
          title="Olumlu Bulgular"
          tone="positive"
          items={criterion.positive_findings.map((item) => item.summary)}
          emptyText="Olumlu bulgu çıkarılmadı."
        />
        <InfoPanel
          title="Zayıflatan Bulgular"
          tone="danger"
          items={criterion.negative_findings.map((item) => item.summary)}
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

      {criterion.coverage_notes.length ? (
        <div className={styles.coverageCard}>
          <p className={styles.coverageTitle}>Coverage Notları</p>
          <ul className={styles.inlineList}>
            {criterion.coverage_notes.map((item, index) => (
              <li key={`${criterion.criterion_id}-coverage-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className={styles.evidenceSection}>
        <div className={styles.sectionHeaderCompact}>
          <h6 className={styles.evidenceSectionTitle}>Kanıt Kartları</h6>
          <p className={styles.evidenceSectionText}>
            Alıntılar doğrudan kullanılan chunk’lardan gelir; her kart neden önemli olduğunu da
            açıklar.
          </p>
        </div>
        {criterion.evidence_items.length ? (
          <div className={styles.evidenceGrid}>
            {criterion.evidence_items.map((item) => (
              <EvidenceCard key={`${criterion.criterion_id}-${item.chunk_id}-${item.evidence_type}`} item={item} />
            ))}
          </div>
        ) : (
          <p className={styles.emptyEvidence}>Kanıt kartı bulunamadı.</p>
        )}
      </div>
    </article>
  );
}

function EvidenceCard({
  item,
}: Readonly<{
  item: CriterionEvaluationResult["evidence_items"][number];
}>) {
  return (
    <article className={`${styles.evidenceCard} ${styles[`evidenceCard${capitalize(item.evidence_type)}`]}`}>
      <div className={styles.evidenceCardTop}>
        <span className={styles.evidenceType}>{getEvidenceTypeLabel(item.evidence_type)}</span>
        <span className={styles.evidenceChunk}>Chunk {item.chunk_id}</span>
      </div>
      <p className={styles.evidenceLocation}>
        {formatEvidenceLocation(item.heading_path, item.page_start, item.page_end)}
      </p>
      <blockquote className={styles.evidenceQuote}>{item.verbatim_excerpt}</blockquote>
      <p className={styles.evidenceWhy}>{item.why_it_matters}</p>
    </article>
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
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className={styles.infoPanelEmpty}>{emptyText}</p>
      )}
    </div>
  );
}

function InfoList({
  title,
  items,
  emptyText,
}: Readonly<{
  title: string;
  items: string[];
  emptyText: string;
}>) {
  return (
    <div className={styles.heroList}>
      <p className={styles.heroListTitle}>{title}</p>
      {items.length ? (
        <ul className={styles.inlineList}>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
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

  return evaluationState.main_scores.map((item) => ({
    id: item.main_dimension_id,
    title: item.title,
    weight: item.weight,
    score: item.score,
    weightedScore: item.weighted_score,
    summary: item.summary,
    subcriteria: subcriteriaByDimension.get(item.main_dimension_id) ?? [],
  })).concat(
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

function isEvaluationRunning(status: EvaluationState["status"]) {
  return (
    status === "queued" ||
    status === "retrieving" ||
    status === "evaluating" ||
    status === "aggregating"
  );
}

function getStatusLabel(evaluationState: EvaluationState | null) {
  if (!evaluationState) {
    return "Yükleniyor";
  }
  if (evaluationState.status === "completed") {
    return "Tamamlandı";
  }
  if (evaluationState.status === "failed") {
    return evaluationState.error ?? "Başarısız";
  }
  if (evaluationState.status === "idle") {
    return "Hazır";
  }
  return `Çalışıyor: ${evaluationState.status}`;
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

function getEvidenceTypeLabel(type: CriterionEvaluationResult["evidence_items"][number]["evidence_type"]) {
  if (type === "positive") {
    return "Destekleyici Kanıt";
  }
  if (type === "negative") {
    return "Zayıflatan Kanıt";
  }
  return "Bağlam";
}

function formatScore(value: number | null | undefined, scale: number) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value.toFixed(scale === 5 ? 1 : 2)}/${scale}`;
}

function formatWeightedContribution(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value.toFixed(2)} puan`;
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

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
