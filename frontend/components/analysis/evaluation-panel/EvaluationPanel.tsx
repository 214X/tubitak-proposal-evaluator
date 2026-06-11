"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type CriterionEvaluationResult,
  type EvidenceNarrative,
  type EvaluationState,
  fetchCurrentEvaluation,
} from "../../../lib/analysis";
import { readSessionId, subscribeToSessionIdChange } from "../../../lib/session";
import styles from "./evaluation-panel.module.css";

type EvaluationReportViewerProps = Readonly<{
  apiBaseUrl: string;
  initialSessionId?: string | null;
}>;

const POLLING_INTERVAL_MS = 2500;

export function EvaluationReportViewer({
  apiBaseUrl,
  initialSessionId = null,
}: EvaluationReportViewerProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [evaluationState, setEvaluationState] = useState<EvaluationState | null>(null);
  const [error, setError] = useState("");
  const [selectedCriterionId, setSelectedCriterionId] = useState<string | null>(null);

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
      setSelectedCriterionId(null);

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

  const criteria = evaluationState?.criterion_results ?? [];

  useEffect(() => {
    if (!criteria.length) {
      setSelectedCriterionId(null);
      return;
    }

    setSelectedCriterionId((current) =>
      current && criteria.some((criterion) => criterion.criterion_id === current)
        ? current
        : criteria[0]?.criterion_id ?? null,
    );
  }, [criteria]);

  const selectedCriterion = useMemo(
    () =>
      criteria.find((criterion) => criterion.criterion_id === selectedCriterionId) ??
      criteria[0] ??
      null,
    [criteria, selectedCriterionId],
  );

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>DEĞERLENDİRME RAPORU</p>
          <h2 className={styles.title}>Kriter Bazlı Evaluation Raporu</h2>
          <p className={styles.description}>
            Seçilen kriter için lehte ve aleyhte kanıtlar, bu kanıtların neden önemli
            olduğu ve nihai puana etkisi bu ekranda birlikte incelenir.
          </p>
        </div>
        {sessionId ? <p className={styles.session}>Oturum: {sessionId}</p> : null}
      </div>

      {error ? <p className={styles.errorText}>{error}</p> : null}

      <div className={styles.statusCard}>
        <div className={styles.statusRow}>
          <span className={styles.statusLabel}>Durum</span>
          <span className={styles.statusValue}>{getStatusLabel(evaluationState)}</span>
        </div>
        <div className={styles.statusRow}>
          <span className={styles.statusLabel}>Aktif Kriter</span>
          <span className={styles.statusValue}>
            {evaluationState?.active_criterion_title ?? "Henüz başlamadı"}
          </span>
        </div>
        {evaluationState?.final_report ? (
          <div className={styles.scoreSummary}>
            <p className={styles.scoreValue}>
              {evaluationState.final_report.total_weighted_score}/
              {evaluationState.final_report.max_possible_weighted_score}
            </p>
            <p className={styles.scoreMeta}>
              {evaluationState.final_report.scored_criteria_count} kriter skorlandı
            </p>
          </div>
        ) : null}
      </div>

      {criteria.length ? (
        <div className={styles.workspace}>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Kategori</th>
                  <th>Kriter</th>
                  <th>Skor</th>
                  <th>Ağırlık</th>
                  <th>Ağırlıklı</th>
                  <th>Güven</th>
                  <th>Durum</th>
                </tr>
              </thead>
              <tbody>
                {criteria.map((criterion) => (
                  <tr
                    key={criterion.criterion_id}
                    className={
                      criterion.criterion_id === selectedCriterion?.criterion_id
                        ? styles.activeRow
                        : undefined
                    }
                    onClick={() => setSelectedCriterionId(criterion.criterion_id)}
                  >
                    <td>{criterion.category}</td>
                    <td>{criterion.title}</td>
                    <td>{criterion.score ?? "-"}</td>
                    <td>{criterion.weight}</td>
                    <td>{criterion.weighted_score ?? "-"}</td>
                    <td>{criterion.confidence.toFixed(2)}</td>
                    <td>{getDecisionLabel(criterion.decision_status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedCriterion ? <CriterionDetail criterion={selectedCriterion} /> : null}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <p>Henüz criterion sonucu oluşmadı.</p>
          <p>Evaluation tamamlandığında ayrıntılı kriter raporu burada açılacak.</p>
        </div>
      )}

      {evaluationState?.final_report ? (
        <div className={styles.report}>
          <div>
            <p className={styles.reportTitle}>Nihai Değerlendirme</p>
            <p className={styles.reportText}>{evaluationState.final_report.final_summary}</p>
          </div>
          <div className={styles.reportColumns}>
            <div>
              <p className={styles.reportListTitle}>Güçlü Yönler</p>
              <ul className={styles.reportList}>
                {evaluationState.final_report.strengths.length ? (
                  evaluationState.final_report.strengths.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))
                ) : (
                  <li>Belirgin güçlü alan çıkarılamadı.</li>
                )}
              </ul>
            </div>
            <div>
              <p className={styles.reportListTitle}>Zayıf Yönler</p>
              <ul className={styles.reportList}>
                {evaluationState.final_report.weaknesses.length ? (
                  evaluationState.final_report.weaknesses.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))
                ) : (
                  <li>Belirgin zayıf alan çıkarılamadı.</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function CriterionDetail({
  criterion,
}: Readonly<{
  criterion: CriterionEvaluationResult;
}>) {
  return (
    <section className={styles.detailCard}>
      <div className={styles.detailHeader}>
        <div>
          <p className={styles.detailCategory}>{criterion.category}</p>
          <h3 className={styles.detailTitle}>{criterion.title}</h3>
        </div>
        <div className={styles.detailScoreBlock}>
          <span className={styles.detailScore}>{criterion.score ?? "-"}</span>
          <span className={styles.detailScoreMeta}>weight {criterion.weight}</span>
        </div>
      </div>

      <p className={styles.justification}>{criterion.justification}</p>

      <div className={styles.metaGrid}>
        <MetaList title="Eksik Bilgiler" items={criterion.missing_information} />
        <MetaList title="Risk İşaretleri" items={criterion.red_flags} />
      </div>

      <div className={styles.evidenceColumns}>
        <EvidenceList
          title="Lehte Kanıtlar"
          tone="positive"
          notes={criterion.supporting_evidence_notes ?? []}
        />
        <EvidenceList
          title="Aleyhte Kanıtlar"
          tone="negative"
          notes={criterion.contradicting_evidence_notes ?? []}
        />
      </div>
    </section>
  );
}

function EvidenceList({
  title,
  tone,
  notes,
}: Readonly<{
  title: string;
  tone: "positive" | "negative";
  notes: EvidenceNarrative[];
}>) {
  return (
    <div className={styles.evidenceGroup}>
      <p className={styles.evidenceTitle}>{title}</p>
      {notes.length ? (
        <div className={styles.evidenceList}>
          {notes.map((item) => (
            <article
              key={`${title}-${item.chunk_id}`}
              className={tone === "positive" ? styles.positiveCard : styles.negativeCard}
            >
              <p className={styles.evidencePath}>{item.location_summary}</p>
              <p className={styles.evidenceText}>{item.evidence_text}</p>
              <p className={styles.evidenceReason}>{item.why_it_matters}</p>
              <p className={styles.evidenceChunkId}>Kaynak chunk: {item.chunk_id}</p>
            </article>
          ))}
        </div>
      ) : (
        <p className={styles.emptyEvidence}>Kanıt bulunamadı.</p>
      )}
    </div>
  );
}

function MetaList({
  title,
  items,
}: Readonly<{
  title: string;
  items: string[];
}>) {
  return (
    <div className={styles.metaCard}>
      <p className={styles.metaTitle}>{title}</p>
      <ul className={styles.metaList}>
        {items.length ? items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>) : <li>Yok</li>}
      </ul>
    </div>
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
