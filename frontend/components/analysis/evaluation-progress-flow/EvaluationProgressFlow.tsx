"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import styles from "./evaluation-progress-flow.module.css";
export type EvaluationStep = {
  id: string;
  runningTitle: string;
  completedTitle: string;
  status: "pending" | "running" | "completed" | "failed";
  durationMs?: number;
};

// Types matching current evaluation report
type EvaluationReport = {
  session_id: string;
  total_weighted_score: number;
  max_possible_weighted_score: number;
  final_summary: string;
};

type EvaluationProgressFlowProps = {
  steps: EvaluationStep[];
  sessionId: string;
  finalReport: EvaluationReport | null;
  error?: string | null;
  totalDurationMs?: number;
};

// Running timer format: 00:00
export function formatRunningDuration(durationMs?: number): string {
  if (durationMs === undefined) return "00:00";
  const totalSeconds = Math.floor(durationMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  
  const pad = (num: number) => String(num).padStart(2, "0");
  return `${pad(minutes)}:${pad(seconds)}`;
}

// Completed step format: x dakika y saniye (empty if < 1s)
export function formatCompletedDuration(durationMs?: number): string {
  if (durationMs === undefined || durationMs < 1000) {
    return "";
  }
  const totalSeconds = Math.floor(durationMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes > 0) {
    if (seconds > 0) {
      return `${minutes} dakika ${seconds} saniye`;
    }
    return `${minutes} dakika`;
  }
  return `${seconds} saniye`;
}

export function EvaluationProgressFlow({
  steps,
  sessionId,
  finalReport,
  error = null,
  totalDurationMs = 0,
}: EvaluationProgressFlowProps) {
  // Filter steps to only show non-pending nodes (completed, running, failed)
  const visibleSteps = useMemo(() => {
    const list: EvaluationStep[] = [];
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      if (step.status !== "pending") {
        list.push(step);
      } else {
        break;
      }
    }
    return list;
  }, [steps]);

  // Circle nodes are steps 1 to 5 (index 0 to 4)
  const circleSteps = visibleSteps.filter((_, idx) => idx < 5);
  
  // Rectangle final step is index 5
  const finalStep = visibleSteps[5] || null;

  const reportHref = `/evaluation/report?sessionId=${encodeURIComponent(sessionId)}`;

  return (
    <div className={styles.flowContainer}>
      <div className={styles.timeline}>
        {circleSteps.map((step, index) => {
          const isLastCircle = index === circleSteps.length - 1;
          const isNextAvailable = visibleSteps.length > index + 1;
          
          let nodeClass = styles.activeNode;
          if (step.status === "completed") {
            nodeClass = styles.completedNode;
          } else if (step.status === "failed") {
            nodeClass = styles.failedNode;
          }

          const isCompleted = step.status === "completed";
          const isRunning = step.status === "running";
          const durationStr = isCompleted 
            ? formatCompletedDuration(step.durationMs) 
            : isRunning 
              ? formatRunningDuration(step.durationMs) 
              : "";

          return (
            <React.Fragment key={step.id}>
              {/* Connector line leading to this step, if not the first step */}
              {index > 0 && (
                <div 
                  className={`${styles.connectorLine} ${
                    step.status === "running" ? styles.animateLine : ""
                  }`} 
                />
              )}

              {/* Step Node */}
              <div className={`${styles.stepNode} ${nodeClass}`}>
                <div className={styles.nodeCircle}>
                  <div className={styles.nodeContent}>
                    <span className={styles.nodeText}>
                      {step.status === "completed" ? step.completedTitle : step.runningTitle}
                    </span>
                    {durationStr && (
                      <span className={styles.nodeDuration}>
                        {durationStr}
                      </span>
                    )}
                  </div>

                  {/* SVG Spinning overlay for active steps */}
                  {step.status === "running" && (
                    <div className={styles.spinnerOverlay}>
                      <svg className={styles.spinnerSvg} viewBox="0 0 100 100">
                        <circle
                          cx="50"
                          cy="50"
                          r="46"
                          stroke="var(--accent)"
                          strokeWidth="3.5"
                          fill="none"
                        />
                      </svg>
                    </div>
                  )}
                </div>
              </div>

              {/* Connector line leading from the last circle to the final step/card if it exists */}
              {isLastCircle && isNextAvailable && (
                <div 
                  className={`${styles.connectorLine} ${
                    finalStep?.status === "running" ? styles.animateLine : ""
                  }`} 
                />
              )}
            </React.Fragment>
          );
        })}

        {/* Final Rectangular Step / Card (Step 6) */}
        {finalStep && (
          <div className={styles.resultWrapper}>
            {finalStep.status === "running" ? (
              <div className={`${styles.resultCard} ${styles.activeCard}`}>
                <h3 className={styles.resultTitle}>{finalStep.runningTitle}</h3>
                <span className={styles.nodeDuration}>
                  {formatRunningDuration(finalStep.durationMs)}
                </span>
              </div>
            ) : finalStep.status === "completed" ? (
              <div className={`${styles.resultCard} ${styles.completedCard}`}>
                <h3 className={styles.resultTitle}>Proje değerlendirmesi tamamlandı</h3>
                
                {finalReport && (
                  <>
                    <div className={styles.resultScoreBox}>
                      <span className={styles.resultScoreLabel}>ALINAN PUAN</span>
                      <div className={styles.resultScoreContainer}>
                        <span className={styles.resultScoreBig}>
                          {finalReport.total_weighted_score}
                        </span>
                        <span className={styles.resultScoreDivider}>
                          /{finalReport.max_possible_weighted_score}
                        </span>
                      </div>
                    </div>

                    <p className={styles.resultSummary}>
                      {finalReport.final_summary}
                    </p>
                  </>
                )}

                <Link 
                  href={reportHref} 
                  target="_blank" 
                  rel="noreferrer" 
                  className={styles.actionButton}
                >
                  Raporu İncele
                </Link>

                {formatCompletedDuration(totalDurationMs) && (
                  <span className={styles.resultMetaTime}>
                    Toplam Süre: {formatCompletedDuration(totalDurationMs)}
                  </span>
                )}
              </div>
            ) : (
              <div className={`${styles.resultCard} ${styles.failedCard}`} style={{ border: "1px solid #d73a49" }}>
                <h3 className={styles.resultTitle} style={{ color: "#d73a49" }}>
                  Değerlendirme Başarısız
                </h3>
                <p className={styles.resultSummary}>
                  {error || "Rapor hazırlama aşamasında bir hata ile karşılaşıldı."}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
