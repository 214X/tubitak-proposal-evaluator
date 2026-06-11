"use client";

import { useEffect, useState } from "react";

import type { UploadState } from "../../upload-panel/UploadPanel";
import { UploadPanel } from "../../upload-panel/UploadPanel";
import { EvaluationOverview } from "../../analysis/evaluation-overview/EvaluationOverview";
import { fetchCurrentAnalysis, type AnalysisState } from "../../../lib/analysis";
import styles from "./evaluation-workspace.module.css";

type EvaluationWorkspaceProps = Readonly<{
  apiBaseUrl: string;
}>;

const ANALYSIS_POLLING_INTERVAL_MS = 2500;

export function EvaluationWorkspace({ apiBaseUrl }: EvaluationWorkspaceProps) {
  const [sessionId, setSessionId] = useState("");
  const [uploadState, setUploadState] = useState<UploadState | null>(null);
  const [analysisState, setAnalysisState] = useState<AnalysisState | null>(null);
  const uploadRevision = uploadState?.uploaded_at ?? null;

  useEffect(() => {
    setAnalysisState(null);
  }, [sessionId, uploadRevision]);

  useEffect(() => {
    if (!sessionId) {
      setAnalysisState(null);
      return;
    }

    let cancelled = false;
    let intervalId: number | null = null;

    async function loadAnalysisState() {
      try {
        const nextState = await fetchCurrentAnalysis(apiBaseUrl, sessionId);
        if (cancelled) {
          return;
        }

        setAnalysisState(nextState);

        if (nextState.status === "completed" || nextState.status === "failed") {
          if (intervalId !== null) {
            window.clearInterval(intervalId);
            intervalId = null;
          }
        } else if (intervalId === null) {
          intervalId = window.setInterval(() => {
            void loadAnalysisState();
          }, ANALYSIS_POLLING_INTERVAL_MS);
        }
      } catch {
        if (!cancelled) {
          setAnalysisState(null);
        }
      }
    }

    void loadAnalysisState();

    return () => {
      cancelled = true;
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
    };
  }, [apiBaseUrl, sessionId, uploadRevision]);

  return (
    <div className={styles.grid}>
      <UploadPanel
        apiBaseUrl={apiBaseUrl}
        onSessionReady={setSessionId}
        onUploadStateChange={setUploadState}
      />

      {sessionId ? (
        <EvaluationOverview
          apiBaseUrl={apiBaseUrl}
          sessionId={sessionId}
          analysisState={analysisState}
          uploadState={uploadState}
        />
      ) : null}
    </div>
  );
}
