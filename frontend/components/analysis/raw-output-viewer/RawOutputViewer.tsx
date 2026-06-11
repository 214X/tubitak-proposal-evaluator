"use client";

import { useEffect, useState } from "react";

import {
  type AnalysisState,
  type ExtractionOutput,
  type ParserOutput,
  fetchCurrentAnalysis,
} from "../../../lib/analysis";
import { readSessionId, subscribeToSessionIdChange } from "../../../lib/session";
import styles from "./raw-output-viewer.module.css";

type RawOutputViewerProps = Readonly<{
  apiBaseUrl: string;
  initialSessionId?: string | null;
  mode: "extraction" | "parser";
}>;

/**
 * Raw output viewer is shared by both extraction and parser debug routes.
 * We keep the component generic so the black-on-white inspection screen
 * stays consistent while only the selected payload changes.
 */
export function RawOutputViewer({
  apiBaseUrl,
  initialSessionId = null,
  mode,
}: RawOutputViewerProps) {
  const [analysisState, setAnalysisState] = useState<AnalysisState | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    function loadForSession(nextSessionId: string | null) {
      setAnalysisState(null);

      if (!nextSessionId) {
        setError("Aktif bir oturum bulunamadı.");
        return;
      }

      void fetchCurrentAnalysis(apiBaseUrl, nextSessionId)
        .then((nextState) => {
          if (!cancelled) {
            setAnalysisState(nextState);
            setError("");
          }
        })
        .catch((currentError) => {
          if (!cancelled) {
            setError(
              currentError instanceof Error
                ? currentError.message
                : mode === "extraction"
                  ? "Extraction sonucu yüklenemedi."
                  : "Parser sonucu yüklenemedi.",
            );
          }
        });
    }

    loadForSession(initialSessionId ?? readSessionId());

    if (initialSessionId) {
      return () => {
        cancelled = true;
      };
    }

    const unsubscribe = subscribeToSessionIdChange((nextSessionId) => {
      if (!cancelled) {
        loadForSession(nextSessionId);
      }
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [apiBaseUrl, initialSessionId, mode]);

  const selectedPayload = getSelectedPayload(analysisState, mode);
  const viewerCopy = getViewerCopy(mode);
  const content = error
    ? error
    : selectedPayload
      ? JSON.stringify(selectedPayload, null, 2)
      : viewerCopy.emptyState;

  return (
    <main className={styles.page}>
      <pre className={styles.pre}>{content}</pre>
    </main>
  );
}

function getSelectedPayload(
  analysisState: AnalysisState | null,
  mode: RawOutputViewerProps["mode"],
): ExtractionOutput | ParserOutput | null {
  if (!analysisState) {
    return null;
  }

  return mode === "extraction"
    ? analysisState.extraction_output
    : analysisState.parser_output;
}

function getViewerCopy(mode: RawOutputViewerProps["mode"]) {
  if (mode === "parser") {
    return {
      emptyState: "Parser çıktısı hazırlanıyor veya henüz üretilmedi.",
    };
  }

  return {
    emptyState: "Extraction çıktısı hazırlanıyor veya henüz üretilmedi.",
  };
}
