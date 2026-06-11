"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { UploadState } from "../../upload-panel/UploadPanel";
import { UploadPanel } from "../../upload-panel/UploadPanel";
import { EvaluationProgressFlow, type EvaluationStep } from "../../analysis/evaluation-progress-flow/EvaluationProgressFlow";
import { SudokuBoard } from "./SudokuBoard";
import {
  fetchCurrentAnalysis,
  fetchCurrentEvaluation,
  startCurrentAnalysis,
  startCurrentEvaluation,
  type AnalysisState,
  type EvaluationState,
  type StageTiming
} from "../../../lib/analysis";
import styles from "./evaluation-workspace.module.css";

type EvaluationWorkspaceProps = Readonly<{
  apiBaseUrl: string;
}>;

const POLLING_INTERVAL_MS = 2500;
const TIMER_INTERVAL_MS = 1000;

export function EvaluationWorkspace({ apiBaseUrl }: EvaluationWorkspaceProps) {
  const [sessionId, setSessionId] = useState("");
  const [uploadState, setUploadState] = useState<UploadState | null>(null);
  const [analysisState, setAnalysisState] = useState<AnalysisState | null>(null);
  const [evaluationState, setEvaluationState] = useState<EvaluationState | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [isFlowActive, setIsFlowActive] = useState(false);
  const [isSudokuEngaged, setIsSudokuEngaged] = useState(false);
  const [isPinnedToBottom, setIsPinnedToBottom] = useState(true);
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null);
  const previousVisibleStepCountRef = useRef(0);

  const uploadRevision = uploadState?.uploaded_at ?? null;

  // Reset states when sessionId or uploaded file changes
  useEffect(() => {
    setAnalysisState(null);
    setEvaluationState(null);
    setError("");
    setIsStarting(false);
    setIsFlowActive(false);
  }, [sessionId, uploadRevision]);

  // Initial load of states
  useEffect(() => {
    if (!sessionId) return;

    let isCancelled = false;

    async function loadInitialStates() {
      try {
        const [analysis, evaluation] = await Promise.all([
          fetchCurrentAnalysis(apiBaseUrl, sessionId).catch(() => null),
          fetchCurrentEvaluation(apiBaseUrl, sessionId).catch(() => null),
        ]);

        if (isCancelled) return;

        if (analysis) {
          setAnalysisState(analysis);
          // If analysis is already running, activate flow state
          if (isAnalysisRunning(analysis.status)) {
            setIsFlowActive(true);
          }
        }
        if (evaluation) {
          setEvaluationState(evaluation);
          if (isEvaluationRunning(evaluation.status)) {
            setIsFlowActive(true);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof Error ? err.message : "Oturum durumu yüklenemedi.");
        }
      }
    }

    void loadInitialStates();

    return () => {
      isCancelled = true;
    };
  }, [apiBaseUrl, sessionId, uploadRevision]);

  // Polling loop for Analysis
  useEffect(() => {
    if (!sessionId || !analysisState || !isAnalysisRunning(analysisState.status)) {
      return;
    }

    let isCancelled = false;
    const intervalId = window.setInterval(async () => {
      try {
        const nextState = await fetchCurrentAnalysis(apiBaseUrl, sessionId);
        if (isCancelled) return;

        setAnalysisState(nextState);

        // If completed, check if we need to auto-trigger evaluation
        if (nextState.status === "completed") {
          window.clearInterval(intervalId);
          if (isFlowActive) {
            // Auto trigger evaluation
            void autoTriggerEvaluation();
          }
        } else if (nextState.status === "failed") {
          window.clearInterval(intervalId);
          setIsFlowActive(false);
          setError(nextState.error ?? "Belge analizi başarısız oldu.");
        }
      } catch (err) {
        if (isCancelled) return;
        setError(err instanceof Error ? err.message : "Analiz durumu güncellenemedi.");
      }
    }, POLLING_INTERVAL_MS);

    return () => {
      isCancelled = false;
      window.clearInterval(intervalId);
    };
  }, [analysisState, apiBaseUrl, sessionId, isFlowActive]);

  // Polling loop for Evaluation
  useEffect(() => {
    if (!sessionId || !evaluationState || !isEvaluationRunning(evaluationState.status)) {
      return;
    }

    let isCancelled = false;
    const intervalId = window.setInterval(async () => {
      try {
        const nextState = await fetchCurrentEvaluation(apiBaseUrl, sessionId);
        if (isCancelled) return;

        setEvaluationState(nextState);

        if (nextState.status === "completed" || nextState.status === "failed") {
          window.clearInterval(intervalId);
          setIsFlowActive(false);
          if (nextState.status === "failed") {
            setError(nextState.error ?? "Değerlendirme başarısız oldu.");
          }
        }
      } catch (err) {
        if (isCancelled) return;
        setError(err instanceof Error ? err.message : "Değerlendirme durumu güncellenemedi.");
      }
    }, POLLING_INTERVAL_MS);

    return () => {
      isCancelled = false;
      window.clearInterval(intervalId);
    };
  }, [evaluationState, apiBaseUrl, sessionId]);

  // Live Timer tick
  const anyTimerRunning = useMemo(() => {
    const isAnalysing = analysisState ? isAnalysisRunning(analysisState.status) : false;
    const isEvaluating = evaluationState ? isEvaluationRunning(evaluationState.status) : false;
    return isAnalysing || isEvaluating;
  }, [analysisState, evaluationState]);

  useEffect(() => {
    if (!anyTimerRunning) return;

    const intervalId = window.setInterval(() => {
      setNow(Date.now());
    }, TIMER_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [anyTimerRunning]);

  // Sequential evaluation trigger helper
  async function autoTriggerEvaluation() {
    setIsStarting(true);
    setError("");
    try {
      const nextState = await startCurrentEvaluation(apiBaseUrl, sessionId);
      setEvaluationState(nextState);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Değerlendirme başlatılamadı.");
      setIsFlowActive(false);
    } finally {
      setIsStarting(false);
    }
  }

  // Handle manual/combined start
  async function handleStartWorkflow() {
    setIsStarting(true);
    setError("");
    setIsFlowActive(true);

    try {
      // 1. If analysis is not completed yet, start analysis
      if (!analysisState || analysisState.status === "idle" || analysisState.status === "failed") {
        const nextAnalysis = await startCurrentAnalysis(apiBaseUrl, sessionId);
        setAnalysisState(nextAnalysis);
      } 
      // 2. If analysis is already completed but evaluation is not, start evaluation directly
      else if (analysisState.status === "completed" && (!evaluationState || evaluationState.status === "idle" || evaluationState.status === "failed")) {
        const nextEval = await startCurrentEvaluation(apiBaseUrl, sessionId);
        setEvaluationState(nextEval);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "İşlem başlatılamadı.");
      setIsFlowActive(false);
    } finally {
      setIsStarting(false);
    }
  }

  // Map analysisState & evaluationState to the 6 Steps list
  const steps: EvaluationStep[] = useMemo(() => {
    const defaultSteps: EvaluationStep[] = [
      {
        id: "extraction",
        runningTitle: "Belge içeriği çıkarılıyor",
        completedTitle: "Belge içeriği çıkarıldı",
        status: "pending",
        durationMs: 0,
      },
      {
        id: "parsing",
        runningTitle: "Belge yapısı ayrıştırılıyor",
        completedTitle: "Belge yapısı ayrıştırıldı",
        status: "pending",
        durationMs: 0,
      },
      {
        id: "chunking",
        runningTitle: "Chunklar oluşturuluyor",
        completedTitle: "Chunklar oluşturuldu",
        status: "pending",
        durationMs: 0,
      },
      {
        id: "embedding",
        runningTitle: "Vektörel temsiller oluşturuluyor",
        completedTitle: "Vektörel temsiller oluşturuldu",
        status: "pending",
        durationMs: 0,
      },
      {
        id: "evaluating",
        runningTitle: "Proje değerlendiriliyor",
        completedTitle: "Proje değerlendirildi",
        status: "pending",
        durationMs: 0,
      },
      {
        id: "aggregating",
        runningTitle: "Nihai rapor hazırlanıyor",
        completedTitle: "Nihai rapor hazırlandı",
        status: "pending",
        durationMs: 0,
      },
    ];

    if (!analysisState) return defaultSteps;

    const getDuration = (timing: StageTiming | null) => {
      if (!timing || !timing.started_at) return 0;
      const start = new Date(timing.started_at).getTime();
      const end = timing.completed_at ? new Date(timing.completed_at).getTime() : now;
      return Math.max(0, end - start);
    };

    // Step 1: Extraction
    if (analysisState.status === "extracting" || (analysisState.status === "queued" && analysisState.current_step === "extractor")) {
      defaultSteps[0].status = "running";
      defaultSteps[0].durationMs = getDuration(analysisState.extraction_timing);
    } else if (
      analysisState.extraction_output ||
      ["parsing", "chunking", "embedding", "completed"].includes(analysisState.status)
    ) {
      defaultSteps[0].status = "completed";
      defaultSteps[0].durationMs = getDuration(analysisState.extraction_timing);
    } else if (analysisState.status === "failed" && !analysisState.extraction_output) {
      defaultSteps[0].status = "failed";
      defaultSteps[0].durationMs = getDuration(analysisState.extraction_timing);
    }

    // Step 2: Parsing
    if (defaultSteps[0].status === "completed") {
      if (analysisState.status === "parsing" || (analysisState.status === "queued" && analysisState.current_step === "parser")) {
        defaultSteps[1].status = "running";
        defaultSteps[1].durationMs = getDuration(analysisState.parser_timing);
      } else if (
        analysisState.parser_output ||
        ["chunking", "embedding", "completed"].includes(analysisState.status)
      ) {
        defaultSteps[1].status = "completed";
        defaultSteps[1].durationMs = getDuration(analysisState.parser_timing);
      } else if (analysisState.status === "failed" && !analysisState.parser_output) {
        defaultSteps[1].status = "failed";
        defaultSteps[1].durationMs = getDuration(analysisState.parser_timing);
      }
    }

    // Step 3: Chunking
    if (defaultSteps[1].status === "completed") {
      if (analysisState.status === "chunking" || (analysisState.status === "queued" && analysisState.current_step === "chunker")) {
        defaultSteps[2].status = "running";
        defaultSteps[2].durationMs = getDuration(analysisState.chunking_timing);
      } else if (
        analysisState.chunk_output ||
        ["embedding", "completed"].includes(analysisState.status)
      ) {
        defaultSteps[2].status = "completed";
        defaultSteps[2].durationMs = getDuration(analysisState.chunking_timing);
      } else if (analysisState.status === "failed" && !analysisState.chunk_output) {
        defaultSteps[2].status = "failed";
        defaultSteps[2].durationMs = getDuration(analysisState.chunking_timing);
      }
    }

    // Step 4: Embedding
    if (defaultSteps[2].status === "completed") {
      if (analysisState.status === "embedding" || (analysisState.status === "queued" && analysisState.current_step === "embedder")) {
        defaultSteps[3].status = "running";
        defaultSteps[3].durationMs = getDuration(analysisState.embedding_timing);
      } else if (analysisState.embedding_output || analysisState.status === "completed") {
        defaultSteps[3].status = "completed";
        defaultSteps[3].durationMs = getDuration(analysisState.embedding_timing);
      } else if (analysisState.status === "failed" && !analysisState.embedding_output) {
        defaultSteps[3].status = "failed";
        defaultSteps[3].durationMs = getDuration(analysisState.embedding_timing);
      }
    }

    // Step 5: Scoring Evaluation
    if (defaultSteps[3].status === "completed" && evaluationState) {
      const start = evaluationState.started_at ? new Date(evaluationState.started_at).getTime() : 0;
      const completed = evaluationState.completed_at ? new Date(evaluationState.completed_at).getTime() : 0;

      if (["queued", "retrieving", "evaluating"].includes(evaluationState.status)) {
        defaultSteps[4].status = "running";
        defaultSteps[4].durationMs = start ? Math.max(0, now - start) : 0;
      } else if (["aggregating", "completed"].includes(evaluationState.status)) {
        defaultSteps[4].status = "completed";
        if (evaluationState.status === "completed") {
          defaultSteps[4].durationMs = (start && completed) ? Math.max(0, (completed - start) * 0.85) : 0;
        } else {
          const update = evaluationState.updated_at ? new Date(evaluationState.updated_at).getTime() : now;
          defaultSteps[4].durationMs = start ? Math.max(0, update - start) : 0;
        }
      } else if (evaluationState.status === "failed") {
        defaultSteps[4].status = "failed";
        const update = evaluationState.updated_at ? new Date(evaluationState.updated_at).getTime() : now;
        defaultSteps[4].durationMs = start ? Math.max(0, update - start) : 0;
      }
    }

    // Step 6: Aggregating / Report Compile
    if (defaultSteps[4].status === "completed" && evaluationState) {
      const start = evaluationState.started_at ? new Date(evaluationState.started_at).getTime() : 0;
      const completed = evaluationState.completed_at ? new Date(evaluationState.completed_at).getTime() : 0;
      const step5Dur = defaultSteps[4].durationMs || 0;

      if (evaluationState.status === "aggregating") {
        defaultSteps[5].status = "running";
        defaultSteps[5].durationMs = start ? Math.max(0, now - (start + step5Dur)) : 0;
      } else if (evaluationState.status === "completed") {
        defaultSteps[5].status = "completed";
        defaultSteps[5].durationMs = (start && completed) ? Math.max(0, (completed - start) - step5Dur) : 0;
      } else if (evaluationState.status === "failed") {
        defaultSteps[5].status = "failed";
        const update = evaluationState.updated_at ? new Date(evaluationState.updated_at).getTime() : now;
        defaultSteps[5].durationMs = start ? Math.max(0, update - (start + step5Dur)) : 0;
      }
    }

    return defaultSteps;
  }, [analysisState, evaluationState, now]);

  // Button disabled logic
  const isWorkflowBusy = isStarting || anyTimerRunning;
  const hasFile = Boolean(uploadState);
  
  // Decide whether to show timeline or start card
  // Show timeline if analysis has started or is completed, or if evaluation is running/completed.
  const hasStartedWorkflow = Boolean(
    analysisState && analysisState.status !== "idle"
  );
  const visibleStepCount = steps.filter((step) => step.status !== "pending").length;
  const totalWorkflowDurationMs = useMemo(() => {
    const analysisStart = analysisState?.started_at
      ? new Date(analysisState.started_at).getTime()
      : 0;

    if (!analysisStart) {
      return 0;
    }

    const workflowEnd = evaluationState?.completed_at
      ? new Date(evaluationState.completed_at).getTime()
      : evaluationState?.updated_at
        ? new Date(evaluationState.updated_at).getTime()
        : analysisState?.updated_at
          ? new Date(analysisState.updated_at).getTime()
          : now;

    return Math.max(0, workflowEnd - analysisStart);
  }, [analysisState, evaluationState, now]);

  useEffect(() => {
    function updatePinnedState() {
      const isNearBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 180;
      setIsPinnedToBottom(isNearBottom);
    }

    updatePinnedState();
    window.addEventListener("scroll", updatePinnedState, { passive: true });
    window.addEventListener("resize", updatePinnedState);

    return () => {
      window.removeEventListener("scroll", updatePinnedState);
      window.removeEventListener("resize", updatePinnedState);
    };
  }, []);

  useEffect(() => {
    if (!hasStartedWorkflow) {
      setIsSudokuEngaged(false);
      previousVisibleStepCountRef.current = 0;
      return;
    }

    const previousVisibleStepCount = previousVisibleStepCountRef.current;
    const hasNewVisibleNode = visibleStepCount > previousVisibleStepCount;
    previousVisibleStepCountRef.current = visibleStepCount;

    if (!hasNewVisibleNode || !isPinnedToBottom) {
      return;
    }

    bottomAnchorRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [hasStartedWorkflow, isPinnedToBottom, visibleStepCount]);

  return (
    <div className={styles.grid}>
      <div className={styles.uploadWrapper}>
        <UploadPanel
          apiBaseUrl={apiBaseUrl}
          onSessionReady={setSessionId}
          onUploadStateChange={setUploadState}
        />
      </div>

      <div className={styles.workspaceMain}>
        {error ? <p className={styles.errorText}>{error}</p> : null}

        {sessionId && hasFile ? (
          <>
            {/* If workflow hasn't started yet, show the prominent start card */}
            {!hasStartedWorkflow ? (
              <div className={styles.startCard}>
                <div className={styles.startIcon} aria-hidden="true">
                  <StartFlowIcon />
                </div>
                <h3 className={styles.startTitle}>Değerlendirmeyi Başlatın</h3>
                <p className={styles.startDescription}>
                  Yüklediğiniz <strong>{uploadState?.file_name}</strong> belgesi analiz edilmeye ve 
                  TÜBİTAK rubriğine göre değerlendirilmeye hazır.
                </p>
                <button
                  type="button"
                  className={styles.startButton}
                  onClick={() => void handleStartWorkflow()}
                  disabled={isWorkflowBusy}
                >
                  {isWorkflowBusy ? "Başlatılıyor..." : "Değerlendirmeyi Başlat"}
                </button>
              </div>
            ) : (
              <>
                {/* If analysis is completed, but evaluation hasn't started yet and isn't busy, we can show a start button at the top */}
                {analysisState?.status === "completed" && 
                 (!evaluationState || evaluationState.status === "idle" || evaluationState.status === "failed") && 
                 !isWorkflowBusy && (
                  <div className={styles.startCard} style={{ padding: "24px", gap: "12px" }}>
                    <p className={styles.startDescription} style={{ fontSize: "13.5px" }}>
                      Belge analiz adımları tamamlandı. Kriter bazlı değerlendirme sürecini başlatın.
                    </p>
                    <button
                      type="button"
                      className={styles.startButton}
                      style={{ maxWidth: "240px", minHeight: "44px", fontSize: "14px" }}
                      onClick={() => void handleStartWorkflow()}
                    >
                      Değerlendirmeyi Başlat
                    </button>
                  </div>
                )}

                <SudokuBoard onEngagementChange={setIsSudokuEngaged} />

                <EvaluationProgressFlow
                  steps={steps}
                  sessionId={sessionId}
                  finalReport={evaluationState?.final_report ?? null}
                  error={error}
                  totalDurationMs={totalWorkflowDurationMs}
                />
              </>
            )}
          </>
        ) : sessionId ? (
          <div className={styles.startCard} style={{ opacity: 0.8 }}>
            <p className={styles.startDescription}>
              Değerlendirme sürecini başlatmak için sol panelden bir dosya (.pdf, .doc, .docx) seçip yükleyin.
            </p>
          </div>
        ) : null}

        <div ref={bottomAnchorRef} />
      </div>
    </div>
  );
}

function isAnalysisRunning(status: AnalysisState["status"]): boolean {
  return ["queued", "extracting", "parsing", "chunking", "embedding"].includes(status);
}

function isEvaluationRunning(status: EvaluationState["status"]): boolean {
  return ["queued", "retrieving", "evaluating", "aggregating"].includes(status);
}

function StartFlowIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
      <path d="M4 7.5h10" />
      <path d="M4 12h16" />
      <path d="M4 16.5h9" />
      <path d="m14 7.5 3-3 3 3" />
      <path d="m14 16.5 3 3 3-3" />
    </svg>
  );
}
