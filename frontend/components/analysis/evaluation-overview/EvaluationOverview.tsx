"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  type AnalysisState,
  type EvaluationState,
  fetchCurrentEvaluation,
  startCurrentEvaluation,
} from "../../../lib/analysis";
import type { UploadState } from "../../upload-panel/UploadPanel";
import styles from "./evaluation-overview.module.css";

type EvaluationOverviewProps = Readonly<{
  apiBaseUrl: string;
  sessionId: string;
  analysisState: AnalysisState | null;
  uploadState?: UploadState | null;
  compact?: boolean;
}>;

const POLLING_INTERVAL_MS = 2500;

const STAGES = [
  {
    key: "queued",
    label: "Hazırlık",
    description: "Evaluation kuyruğa alındı ve rubric yükleniyor.",
  },
  {
    key: "retrieving",
    label: "Kanıt Toplama",
    description: "Her kriter için olumlu ve olumsuz chunklar aranıyor.",
  },
  {
    key: "evaluating",
    label: "Kriter Skorlama",
    description: "Aya Expanse 8B seçilen kanıtlarla kriterleri puanlıyor.",
  },
  {
    key: "aggregating",
    label: "Raporlama",
    description: "Ağırlıklı skorlar ve nihai rapor birleştiriliyor.",
  },
  {
    key: "completed",
    label: "Tamamlandı",
    description: "Evaluation raporu incelenmeye hazır.",
  },
] as const;

export function EvaluationOverview({
  apiBaseUrl,
  sessionId,
  analysisState,
  uploadState = null,
  compact = false,
}: EvaluationOverviewProps) {
  const [evaluationState, setEvaluationState] = useState<EvaluationState | null>(null);
  const [error, setError] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const uploadRevision = uploadState?.uploaded_at ?? null;

  useEffect(() => {
    setEvaluationState(null);
    setError("");
    setIsStarting(false);
  }, [sessionId, uploadRevision]);

  useEffect(() => {
    let isCancelled = false;

    async function loadState() {
      try {
        const nextState = await fetchCurrentEvaluation(apiBaseUrl, sessionId);
        if (!isCancelled) {
          setEvaluationState(nextState);
          setError("");
        }
      } catch (currentError) {
        if (!isCancelled) {
          setError(
            currentError instanceof Error
              ? currentError.message
              : "Evaluation durumu yüklenemedi.",
          );
        }
      }
    }

    void loadState();

    return () => {
      isCancelled = true;
    };
  }, [apiBaseUrl, sessionId, uploadRevision]);

  useEffect(() => {
    if (
      !analysisState ||
      (!isEvaluationRunning(evaluationState?.status ?? "idle") &&
        !(
          analysisState.embedding_output &&
          evaluationState?.status !== "completed" &&
          evaluationState?.status !== "failed"
        ))
    ) {
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
              : "Evaluation durumu güncellenemedi.",
          );
        });
    }, POLLING_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [analysisState, apiBaseUrl, evaluationState, sessionId, uploadRevision]);

  const canStartEvaluation = Boolean(
    analysisState?.status === "completed" &&
      analysisState.embedding_output &&
      !isStarting &&
      !isEvaluationRunning(evaluationState?.status ?? "idle"),
  );

  const progressIndex = useMemo(() => getProgressIndex(evaluationState?.status ?? "idle"), [evaluationState]);
  const progressRatio = useMemo(() => (progressIndex <= 0 ? 0 : progressIndex / (STAGES.length - 1)), [progressIndex]);
  const reportHref = `/evaluation/report?sessionId=${encodeURIComponent(sessionId)}`;

  async function handleStartEvaluation() {
    setIsStarting(true);
    setError("");

    try {
      const nextState = await startCurrentEvaluation(apiBaseUrl, sessionId);
      setEvaluationState(nextState);
    } catch (currentError) {
      setError(
        currentError instanceof Error ? currentError.message : "Evaluation başlatılamadı.",
      );
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <section className={`${styles.panel} ${compact ? styles.compactPanel : ""}`}>
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>EVALUATION WORKFLOW</p>
          <h2 className={styles.title}>
            {compact ? "Evaluation Durumu" : "Evidence-backed criterion scoring"}
          </h2>
          <p className={styles.description}>
            {compact
              ? "Rapor sayfasına gitmeden önce evaluation ilerleyişini ve aşama durumunu izleyin."
              : "Her kriter için toplanan kanıtlar ayrı ayrı tartılır, negatif sinyaller özellikle izlenir ve nihai skor buna göre üretilir."}
          </p>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.startButton}
            onClick={() => void handleStartEvaluation()}
            disabled={!canStartEvaluation}
          >
            {isStarting || isEvaluationRunning(evaluationState?.status ?? "idle")
              ? "Evaluation Çalışıyor"
              : analysisState?.embedding_output
                ? "Evaluation Yeniden Başlat"
                : "Evaluation Başlat"}
          </button>
          {evaluationState?.status === "completed" ? (
            <Link href={reportHref} target="_blank" rel="noreferrer" className={styles.reportButton}>
              Raporu Gör
            </Link>
          ) : null}
        </div>
      </div>

      {!analysisState?.embedding_output ? (
        <p className={styles.helperText}>
          Evaluation başlatmak için analysis akışının embedding adımıyla birlikte tamamlanmış olması gerekir.
        </p>
      ) : null}

      {error ? <p className={styles.errorText}>{error}</p> : null}

      <div className={styles.statusGrid}>
        <div className={styles.statusCard}>
          <span className={styles.statusLabel}>Durum</span>
          <strong className={styles.statusValue}>{getStatusLabel(evaluationState)}</strong>
        </div>
        <div className={styles.statusCard}>
          <span className={styles.statusLabel}>Aktif Kriter</span>
          <strong className={styles.statusValue}>
            {evaluationState?.active_criterion_title ?? "Henüz başlamadı"}
          </strong>
        </div>
        <div className={styles.statusCard}>
          <span className={styles.statusLabel}>Rubric</span>
          <strong className={styles.statusValue}>
            {evaluationState?.rubric_id ?? "tubitak-default"} • Aya Expanse 8B
          </strong>
        </div>
      </div>

      <section className={styles.progressPanel}>
        <div className={styles.progressHeader}>
          <div>
            <p className={styles.progressEyebrow}>İlerleme Aşamaları</p>
            <h3 className={styles.progressTitle}>{getActiveStageLabel(evaluationState?.status ?? "idle")}</h3>
          </div>
          <p className={styles.progressDescription}>
            {getActiveStageDescription(evaluationState?.status ?? "idle", evaluationState?.active_criterion_title)}
          </p>
        </div>

        <div className={styles.progressTrack}>
          <div
            className={styles.progressFill}
            style={{ width: `${Math.min(100, Math.max(0, progressRatio * 100))}%` }}
          />
        </div>

        <div className={styles.stageGrid}>
          {STAGES.map((stage, index) => {
            const state = getStageState(index, progressIndex, evaluationState?.status ?? "idle");
            return (
              <article key={stage.key} className={styles.stageCard} data-state={state}>
                <div className={styles.stageNumber}>{index + 1}</div>
                <div>
                  <p className={styles.stageLabel}>{stage.label}</p>
                  <p className={styles.stageDescription}>{stage.description}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {evaluationState?.final_report ? (
        <section className={styles.summaryCard}>
          <div>
            <p className={styles.summaryEyebrow}>Hazır Rapor Özeti</p>
            <p className={styles.summaryText}>{evaluationState.final_report.final_summary}</p>
          </div>
          <div className={styles.summaryScore}>
            <strong>
              {evaluationState.final_report.total_weighted_score}/
              {evaluationState.final_report.max_possible_weighted_score}
            </strong>
            <span>{evaluationState.final_report.scored_criteria_count} kriter skorlandı</span>
          </div>
        </section>
      ) : null}
    </section>
  );
}

function isEvaluationRunning(status: EvaluationState["status"]) {
  return status === "queued" || status === "retrieving" || status === "evaluating" || status === "aggregating";
}

function getProgressIndex(status: EvaluationState["status"]) {
  switch (status) {
    case "queued":
      return 0;
    case "retrieving":
      return 1;
    case "evaluating":
      return 2;
    case "aggregating":
      return 3;
    case "completed":
      return 4;
    default:
      return 0;
  }
}

function getStageState(index: number, progressIndex: number, status: EvaluationState["status"]) {
  if (status === "failed") {
    return "error";
  }
  if (index < progressIndex) {
    return "complete";
  }
  if (index === progressIndex && status !== "idle") {
    return "active";
  }
  return "waiting";
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

function getActiveStageLabel(status: EvaluationState["status"]) {
  if (status === "idle") {
    return "Evaluation başlamadı";
  }
  if (status === "failed") {
    return "Evaluation hata verdi";
  }
  return STAGES[getProgressIndex(status)]?.label ?? "Hazırlık";
}

function getActiveStageDescription(status: EvaluationState["status"], activeCriterionTitle: string | null | undefined) {
  if (status === "idle") {
    return "Analysis tamamlandığında evaluation başlatılabilir.";
  }
  if (status === "failed") {
    return "Akış bir hata ile durdu. Backend hata mesajı durum kartında görüntülenir.";
  }
  const baseDescription = STAGES[getProgressIndex(status)]?.description ?? "";
  if (status === "retrieving" || status === "evaluating") {
    return activeCriterionTitle ? `${baseDescription} Aktif kriter: ${activeCriterionTitle}.` : baseDescription;
  }
  return baseDescription;
}
