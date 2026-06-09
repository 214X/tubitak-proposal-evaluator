"use client";

import { useState } from "react";

import type { UploadState } from "../../upload-panel/UploadPanel";
import { UploadPanel } from "../../upload-panel/UploadPanel";
import { AnalysisDashboard } from "../../analysis/analysis-dashboard/AnalysisDashboard";
import styles from "./debug-flow-workspace.module.css";

type DebugFlowWorkspaceProps = Readonly<{
  apiBaseUrl: string;
}>;

export function DebugFlowWorkspace({ apiBaseUrl }: DebugFlowWorkspaceProps) {
  const [sessionId, setSessionId] = useState("");
  const [uploadState, setUploadState] = useState<UploadState | null>(null);

  return (
    <div className={styles.grid}>
      <UploadPanel
        apiBaseUrl={apiBaseUrl}
        onSessionReady={setSessionId}
        onUploadStateChange={setUploadState}
      />

      {sessionId ? (
        <AnalysisDashboard
          apiBaseUrl={apiBaseUrl}
          sessionId={sessionId}
          uploadState={uploadState}
        />
      ) : null}
    </div>
  );
}
