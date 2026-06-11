"use client";

import { useEffect, useState } from "react";

import { type AnalysisState, fetchCurrentAnalysis } from "../../../lib/analysis";
import { readSessionId, subscribeToSessionIdChange } from "../../../lib/session";
import { EmbeddingSearchPanel } from "../embedding-search-panel/EmbeddingSearchPanel";
import styles from "./embedding-search-viewer.module.css";

type EmbeddingSearchViewerProps = Readonly<{
  apiBaseUrl: string;
  initialSessionId?: string | null;
}>;

export function EmbeddingSearchViewer({
  apiBaseUrl,
  initialSessionId = null,
}: EmbeddingSearchViewerProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [analysisState, setAnalysisState] = useState<AnalysisState | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    function loadForSession(nextSessionId: string | null) {
      setSessionId(nextSessionId);
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
                : "Embedding arama sayfası yüklenemedi.",
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
  }, [apiBaseUrl, initialSessionId]);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Embedding Search</p>
          <h1 className={styles.title}>Semantic Retrieval</h1>
        </div>
        {sessionId ? <p className={styles.session}>Session: {sessionId}</p> : null}
      </header>

      {error ? <p className={styles.error}>{error}</p> : null}

      {analysisState?.chunk_output ? (
        <EmbeddingSearchPanel
          apiBaseUrl={apiBaseUrl}
          sessionId={sessionId ?? ""}
          chunkOutput={analysisState.chunk_output}
          embeddingOutput={analysisState.embedding_output}
          analysisStatus={analysisState.status}
        />
      ) : (
        <section className={styles.emptyState}>
          <p className={styles.emptyTitle}>Chunking sonucu henüz hazır değil.</p>
          <p className={styles.emptyText}>
            Embedding search ekranı için önce chunking ve embedding aşamalarının tamamlanması
            gerekir.
          </p>
        </section>
      )}
    </main>
  );
}
