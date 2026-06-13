"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type AnalysisState,
  type EvaluationState,
  type StageTiming,
  type UploadState,
  fetchCurrentEvaluation,
  fetchCurrentAnalysis,
  startCurrentAnalysis,
  startCurrentAnalysisUntilChunking,
} from "../../../lib/analysis";
import styles from "./analysis-dashboard.module.css";
import { AnalyzeButton } from "../analyze-button/AnalyzeButton";
import { AnalysisStageCard } from "../analysis-stage-card/AnalysisStageCard";

type AnalysisDashboardProps = Readonly<{
  apiBaseUrl: string;
  sessionId: string;
  uploadState: UploadState | null;
  startMode?: "full" | "chunk_only";
}>;

const POLLING_INTERVAL_MS = 2500;
const TIMER_INTERVAL_MS = 1000;

export function AnalysisDashboard({
  apiBaseUrl,
  sessionId,
  uploadState,
  startMode = "full",
}: AnalysisDashboardProps) {
  const [analysisState, setAnalysisState] = useState<AnalysisState | null>(null);
  const [evaluationState, setEvaluationState] = useState<EvaluationState | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const uploadRevision = uploadState?.uploaded_at ?? null;

  useEffect(() => {
    setAnalysisState(null);
    setEvaluationState(null);
    setError("");
    setIsStarting(false);
  }, [sessionId, uploadRevision]);

  useEffect(() => {
    let isCancelled = false;

    async function loadCurrentState() {
      try {
        const nextState = await fetchCurrentAnalysis(apiBaseUrl, sessionId);
        if (!isCancelled) {
          setAnalysisState(nextState);
          setError("");
        }
      } catch (currentError) {
        if (!isCancelled) {
          setError(
            currentError instanceof Error
              ? currentError.message
              : "Analiz durumu yüklenemedi.",
          );
        }
      }
    }

    void loadCurrentState();

    return () => {
      isCancelled = true;
    };
  }, [apiBaseUrl, sessionId, uploadRevision]);

  useEffect(() => {
    if (!analysisState || !isRunningState(analysisState.status)) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void fetchCurrentAnalysis(apiBaseUrl, sessionId)
        .then((nextState) => {
          setAnalysisState(nextState);
          setError("");
        })
        .catch((currentError) => {
          setError(
            currentError instanceof Error
              ? currentError.message
              : "Analiz durumu güncellenemedi.",
          );
        });
    }, POLLING_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [analysisState, apiBaseUrl, sessionId, uploadRevision]);

  useEffect(() => {
    let isCancelled = false;

    async function loadCurrentEvaluation() {
      try {
        const nextState = await fetchCurrentEvaluation(apiBaseUrl, sessionId);
        if (!isCancelled) {
          setEvaluationState(nextState);
        }
      } catch {
        if (!isCancelled) {
          setEvaluationState(null);
        }
      }
    }

    void loadCurrentEvaluation();

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
        })
        .catch(() => undefined);
    }, POLLING_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [analysisState, apiBaseUrl, evaluationState, sessionId, uploadRevision]);

  const anyTimerRunning = useMemo(
    () =>
      Boolean(
        isAnalysisRunning(analysisState) ||
          isEvaluationRunning(evaluationState?.status ?? "idle"),
      ),
    [analysisState, evaluationState],
  );

  useEffect(() => {
    if (!anyTimerRunning) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setNow(Date.now());
    }, TIMER_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [anyTimerRunning]);

  const canStart = Boolean(uploadState && sessionId) && !isStarting && !isAnalysisRunning(analysisState);
  const shouldShowCards = Boolean(
    analysisState &&
      analysisState.status !== "idle" &&
      (analysisState.file_name || analysisState.error || analysisState.started_at),
  );

  async function handleStartAnalysis() {
    setIsStarting(true);
    setError("");

    try {
      const nextState =
        startMode === "chunk_only"
          ? await startCurrentAnalysisUntilChunking(apiBaseUrl, sessionId)
          : await startCurrentAnalysis(apiBaseUrl, sessionId);
      setAnalysisState(nextState);
    } catch (currentError) {
      setError(
        currentError instanceof Error ? currentError.message : "Analiz başlatılamadı.",
      );
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <div>
          <p className={styles.eyebrow}>ANALİZ AKIŞI</p>
          <h2 className={styles.title}>Belge işleme durumunu izle</h2>
          <p className={styles.description}>
            Ağır önizlemeler ayrı sayfalara taşındı. Bu panel artık yalnızca akış durumu,
            sayaçlar ve ilgili sayfa linklerini gösterir.
          </p>
        </div>
      </div>

      <AnalyzeButton
        disabled={!canStart}
        isBusy={isStarting || isAnalysisRunning(analysisState)}
        onClick={() => void handleStartAnalysis()}
        mode={startMode}
        helperText={
          uploadState
            ? undefined
            : "Analizi başlatmak için önce bu oturuma bir dosya yükleyin."
        }
      />

      {error ? <p className={styles.errorText}>{error}</p> : null}

      {shouldShowCards ? (
        <div className={styles.cards}>
          <AnalysisStageCard
            title="Extraction Output"
            description={getExtractionDescription(analysisState)}
            tone={getExtractionTone(analysisState)}
            details={
              <StageSummary
                now={now}
                timing={analysisState?.extraction_timing ?? null}
                completedLabel="Extraction output aşaması tamamlandı."
                runningLabel="Extraction output hazırlanıyor."
                waitingLabel="Extraction output henüz başlamadı."
                completedMeta={getExtractionMeta(analysisState)}
              />
            }
            action={
              analysisState?.extraction_output ? (
                <ViewerLink
                  href={`/debug-flow/extraction-view?sessionId=${encodeURIComponent(sessionId)}`}
                  label="Extraction Sayfasını Aç"
                />
              ) : null
            }
          />

          <AnalysisStageCard
            title="Parser Output"
            description={getParserOutputDescription(analysisState)}
            tone={getParserTone(analysisState)}
            details={
              <StageSummary
                now={now}
                timing={analysisState?.parser_timing ?? null}
                completedLabel="Parser output aşaması tamamlandı."
                runningLabel="Parser output hazırlanıyor."
                waitingLabel="Parser output henüz başlamadı."
                completedMeta={getParserMeta(analysisState)}
              />
            }
            action={
              analysisState?.parser_output ? (
                <ViewerLink
                  href={`/debug-flow/parser-output-view?sessionId=${encodeURIComponent(sessionId)}`}
                  label="Parser Sayfasını Aç"
                />
              ) : null
            }
          />

          <AnalysisStageCard
            title="Belge Görünümü ve Hiyerarşisi"
            description={getHierarchyDescription(analysisState)}
            tone={getParserTone(analysisState)}
            details={
              <StageSummary
                now={now}
                timing={analysisState?.parser_timing ?? null}
                completedLabel="Belge görünümü ve hiyerarşi hazır."
                runningLabel="Belge görünümü ve hiyerarşi hazırlanıyor."
                waitingLabel="Belge görünümü parser tamamlanınca açılacak."
                completedMeta={getHierarchyMeta(analysisState)}
              />
            }
            action={
              analysisState?.parser_output ? (
                <ViewerLink
                  href={`/debug-flow/parser-view?sessionId=${encodeURIComponent(sessionId)}`}
                  label="Belge Sayfasını Aç"
                />
              ) : null
            }
          />

          <AnalysisStageCard
            title="Chunking Görünümü"
            description={getChunkDescription(analysisState)}
            tone={getChunkTone(analysisState)}
            details={
              <StageSummary
                now={now}
                timing={analysisState?.chunking_timing ?? null}
                completedLabel="Chunking aşaması tamamlandı."
                runningLabel="Chunklar üretiliyor."
                waitingLabel="Chunking parser tamamlandıktan sonra başlayacak."
                completedMeta={getChunkMeta(analysisState)}
              />
            }
            action={
              analysisState?.chunk_output ? (
                <ViewerLink
                  href={`/debug-flow/chunk-view?sessionId=${encodeURIComponent(sessionId)}`}
                  label="Chunk Sayfasını Aç"
                />
              ) : null
            }
          />

          <AnalysisStageCard
            title="Embedding Search"
            description={getEmbeddingDescription(analysisState)}
            tone={getEmbeddingTone(analysisState)}
            details={
              <StageSummary
                now={now}
                timing={analysisState?.embedding_timing ?? null}
                completedLabel="Embedding arama altyapısı hazır."
                runningLabel="Embedding vektörleri hazırlanıyor."
                waitingLabel="Embedding chunking tamamlandıktan sonra başlayacak."
                completedMeta={getEmbeddingMeta(analysisState)}
              />
            }
            action={
              analysisState?.embedding_output ? (
                <ViewerLink
                  href={`/debug-flow/embedding-view?sessionId=${encodeURIComponent(sessionId)}`}
                  label="Embedding Sayfasını Aç"
                />
              ) : null
            }
          />

          <AnalysisStageCard
            title="Evaluation Report"
            description={getEvaluationDescription(evaluationState, analysisState)}
            tone={getEvaluationTone(evaluationState, analysisState)}
            details={
              <EvaluationSummary
                now={now}
                evaluationState={evaluationState}
                analysisState={analysisState}
              />
            }
            action={
              <ViewerLink
                href={
                  evaluationState?.status === "completed"
                    ? `/evaluation/report?sessionId=${encodeURIComponent(sessionId)}`
                    : `/evaluation`
                }
                label={
                  evaluationState?.status === "completed"
                    ? "Rapor Sayfasını Aç"
                    : "Evaluation Sayfasını Aç"
                }
              />
            }
          />
        </div>
      ) : null}
    </section>
  );
}

function StageSummary({
  now,
  timing,
  completedLabel,
  runningLabel,
  waitingLabel,
  completedMeta,
}: Readonly<{
  now: number;
  timing: StageTiming | null;
  completedLabel: string;
  runningLabel: string;
  waitingLabel: string;
  completedMeta?: string | null;
}>) {
  const duration = getTimingDuration(timing, now);

  if (!timing?.started_at) {
    return (
      <div className={styles.summaryBlock}>
        <p className={styles.summaryPrimary}>{waitingLabel}</p>
      </div>
    );
  }

  if (!timing.completed_at) {
    return (
      <div className={styles.summaryBlock}>
        <p className={styles.summaryPrimary}>{runningLabel}</p>
        <div className={styles.summaryGrid}>
          <SummaryItem label="Sayaç" value={duration ? formatDuration(duration) : "-"} />
          <SummaryItem label="Başladı" value={formatDateTime(timing.started_at)} />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.summaryBlock}>
      <p className={styles.summaryPrimary}>{completedLabel}</p>
      <div className={styles.summaryGrid}>
        <SummaryItem label="Süre" value={duration ? formatDuration(duration) : "-"} />
        <SummaryItem label="Tamamlandı" value={formatDateTime(timing.completed_at)} />
        {completedMeta ? <SummaryItem label="Özet" value={completedMeta} /> : null}
      </div>
    </div>
  );
}

function EvaluationSummary({
  now,
  evaluationState,
  analysisState,
}: Readonly<{
  now: number;
  evaluationState: EvaluationState | null;
  analysisState: AnalysisState | null;
}>) {
  if (!analysisState?.embedding_output) {
    return (
      <div className={styles.summaryBlock}>
        <p className={styles.summaryPrimary}>
          Evaluation için önce analysis ve embedding tamamlanmalı.
        </p>
      </div>
    );
  }

  if (!evaluationState || !evaluationState.started_at) {
    return (
      <div className={styles.summaryBlock}>
        <p className={styles.summaryPrimary}>Evaluation henüz başlamadı.</p>
      </div>
    );
  }

  const duration = getDurationMs(
    evaluationState.started_at,
    evaluationState.completed_at,
    now,
  );

  return (
    <div className={styles.summaryBlock}>
      <p className={styles.summaryPrimary}>{getEvaluationStatusLine(evaluationState)}</p>
      <div className={styles.summaryGrid}>
        <SummaryItem
          label={evaluationState.completed_at ? "Süre" : "Sayaç"}
          value={duration ? formatDuration(duration) : "-"}
        />
        <SummaryItem
          label={evaluationState.completed_at ? "Tamamlandı" : "Başladı"}
          value={formatDateTime(evaluationState.completed_at ?? evaluationState.started_at)}
        />
        {evaluationState.final_report ? (
          <SummaryItem
            label="Skor"
            value={`${evaluationState.final_report.total_weighted_score}/${evaluationState.final_report.max_possible_weighted_score}`}
          />
        ) : evaluationState.active_criterion_title ? (
          <SummaryItem label="Aktif Kriter" value={evaluationState.active_criterion_title} />
        ) : null}
      </div>
    </div>
  );
}

function SummaryItem({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className={styles.summaryItem}>
      <p className={styles.summaryLabel}>{label}</p>
      <p className={styles.summaryValue}>{value}</p>
    </div>
  );
}

function isRunningState(status: AnalysisState["status"]) {
  return (
    status === "queued" ||
    status === "extracting" ||
    status === "parsing" ||
    status === "chunking" ||
    status === "embedding"
  );
}

function isAnalysisRunning(analysisState: AnalysisState | null) {
  return Boolean(analysisState && isRunningState(analysisState.status));
}

function isEvaluationRunning(status: EvaluationState["status"]) {
  return (
    status === "queued" ||
    status === "retrieving" ||
    status === "evaluating" ||
    status === "aggregating"
  );
}

function getExtractionTone(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "idle" as const;
  }
  if (analysisState.extraction_output) {
    return "success" as const;
  }
  if (analysisState.status === "failed") {
    return "error" as const;
  }
  if (analysisState.status === "queued" || analysisState.status === "extracting") {
    return "loading" as const;
  }
  return "waiting" as const;
}

function getParserTone(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "idle" as const;
  }
  if (analysisState.parser_output) {
    return "success" as const;
  }
  if (analysisState.status === "failed") {
    return "error" as const;
  }
  if (analysisState.status === "parsing") {
    return "loading" as const;
  }
  if (analysisState.status === "queued" || analysisState.status === "extracting") {
    return "waiting" as const;
  }
  return "idle" as const;
}

function getChunkTone(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "idle" as const;
  }
  if (analysisState.chunk_output) {
    return "success" as const;
  }
  if (analysisState.status === "failed") {
    return "error" as const;
  }
  if (analysisState.status === "chunking") {
    return "loading" as const;
  }
  if (analysisState.parser_output || analysisState.status === "embedding") {
    return "waiting" as const;
  }
  return "idle" as const;
}

function getEmbeddingTone(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "idle" as const;
  }
  if (analysisState.embedding_output) {
    return "success" as const;
  }
  if (analysisState.status === "failed") {
    return "error" as const;
  }
  if (analysisState.status === "embedding") {
    return "loading" as const;
  }
  if (analysisState.chunk_output) {
    return "waiting" as const;
  }
  return "idle" as const;
}

function getExtractionDescription(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "Extraction output ayrı sayfasında açılacak.";
  }
  if (analysisState.extraction_output) {
    return "Ham extraction çıktısı ayrı sayfada incelenebilir.";
  }
  if (analysisState.status === "failed") {
    return analysisState.error ?? "Extraction aşaması tamamlanamadı.";
  }
  return "Extraction tamamlandığında bu kart yalnızca durum ve süre bilgisini gösterecek.";
}

function getParserOutputDescription(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "Parser output ayrı sayfasında açılacak.";
  }
  if (analysisState.parser_output) {
    return "Ham parser çıktısı ayrı sayfada incelenebilir.";
  }
  if (analysisState.status === "failed") {
    return analysisState.error ?? "Parser aşaması tamamlanamadı.";
  }
  return "Extraction tamamlandıktan sonra parser output hazırlanacak.";
}

function getHierarchyDescription(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "Belge görünümü ve hiyerarşisi ayrı sayfada açılacak.";
  }
  if (analysisState.parser_output) {
    return "Belgenin tam görünümü ile başlık hiyerarşisi aynı sayfada gösterilir.";
  }
  if (analysisState.status === "failed") {
    return analysisState.error ?? "Belge görünümü hazırlanamadı.";
  }
  return "Parser tamamlandıktan sonra belge görünümü ve hiyerarşi hazırlanacak.";
}

function getChunkDescription(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "Chunk görünümü ayrı sayfada açılacak.";
  }
  if (analysisState.chunk_output) {
    return "Chunk listesinin tamamı ayrı sayfada incelenebilir.";
  }
  if (analysisState.status === "failed") {
    return analysisState.error ?? "Chunking aşaması tamamlanamadı.";
  }
  return "Chunking sonuçları hazır olunca ayrı sayfada açılacak.";
}

function getEmbeddingDescription(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "Embedding search ayrı sayfada açılacak.";
  }
  if (analysisState.embedding_output) {
    return "Semantic arama paneli ayrı sayfada kullanılabilir.";
  }
  if (analysisState.status === "failed") {
    return analysisState.error ?? "Embedding aşaması tamamlanamadı.";
  }
  return "Embedding hazır olduğunda arama paneli ayrı sayfada açılacak.";
}

function getEvaluationDescription(
  evaluationState: EvaluationState | null,
  analysisState: AnalysisState | null,
) {
  if (!analysisState?.embedding_output) {
    return "Evaluation için önce analysis ve embedding tamamlanmalı.";
  }
  if (!evaluationState || evaluationState.status === "idle") {
    return "Evaluation kendi sayfasından başlatılır ve rapor ayrı sayfada açılır.";
  }
  if (evaluationState.status === "failed") {
    return evaluationState.error ?? "Evaluation akışı hata ile sonlandı.";
  }
  if (evaluationState.final_report) {
    return "Evaluation raporu hazır. Ayrıntılar rapor sayfasında görüntülenebilir.";
  }
  return getEvaluationStatusLine(evaluationState);
}

function getEvaluationTone(
  evaluationState: EvaluationState | null,
  analysisState: AnalysisState | null,
) {
  if (!analysisState?.embedding_output) {
    return "waiting" as const;
  }
  if (!evaluationState || evaluationState.status === "idle") {
    return "idle" as const;
  }
  if (evaluationState.status === "failed") {
    return "error" as const;
  }
  if (evaluationState.status === "completed") {
    return "success" as const;
  }
  return "loading" as const;
}

function getEvaluationStatusLine(evaluationState: EvaluationState) {
  if (evaluationState.status === "retrieving") {
    return `Kanıt toplanıyor: ${evaluationState.active_criterion_title ?? "kriter seçiliyor"}.`;
  }
  if (evaluationState.status === "evaluating") {
    return `Kriter puanlanıyor: ${evaluationState.active_criterion_title ?? "aktif kriter yok"}.`;
  }
  if (evaluationState.status === "aggregating") {
    return "Toplam skor ve nihai rapor hazırlanıyor.";
  }
  if (evaluationState.status === "queued") {
    return "Evaluation kuyruğa alındı.";
  }
  if (evaluationState.status === "completed") {
    return "Evaluation tamamlandı.";
  }
  return "Evaluation durumu bekleniyor.";
}

function getExtractionMeta(analysisState: AnalysisState | null) {
  if (!analysisState?.extraction_output) {
    return null;
  }

  return `${analysisState.extraction_output.document.page_count} sayfa`;
}

function getParserMeta(analysisState: AnalysisState | null) {
  if (!analysisState?.parser_output) {
    return null;
  }

  return `${analysisState.parser_output.content_stream.length} akış girdisi`;
}

function getHierarchyMeta(analysisState: AnalysisState | null) {
  if (!analysisState?.parser_output) {
    return null;
  }

  return `${analysisState.parser_output.heading_hierarchy.length} kök başlık`;
}

function getChunkMeta(analysisState: AnalysisState | null) {
  if (!analysisState?.chunk_output) {
    return null;
  }

  return `${analysisState.chunk_output.chunks.length} chunk`;
}

function getEmbeddingMeta(analysisState: AnalysisState | null) {
  if (!analysisState?.embedding_output) {
    return null;
  }

  return `${analysisState.embedding_output.chunk_count} chunk • ${analysisState.embedding_output.model_name}`;
}

function getTimingDuration(timing: StageTiming | null, now: number) {
  if (!timing?.started_at) {
    return null;
  }

  return getDurationMs(timing.started_at, timing.completed_at, now);
}

function getDurationMs(startedAt: string | null, completedAt: string | null, now: number) {
  if (!startedAt) {
    return null;
  }

  const startTime = new Date(startedAt).getTime();
  const endTime = completedAt ? new Date(completedAt).getTime() : now;

  if (Number.isNaN(startTime) || Number.isNaN(endTime)) {
    return null;
  }

  return Math.max(0, endTime - startTime);
}

function formatDuration(durationMs: number) {
  const totalSeconds = Math.floor(durationMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  return date.toLocaleString("tr-TR");
}

function ViewerLink({ href, label }: Readonly<{ href: string; label: string }>) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={styles.viewerLink}
    >
      {label}
    </a>
  );
}
