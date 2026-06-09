"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  type AnalysisState,
  type HeadingHierarchyNode,
  type ParserOutput,
  type UploadState,
  fetchCurrentAnalysis,
  startCurrentAnalysis,
} from "../../../lib/analysis";
import styles from "./analysis-dashboard.module.css";
import { AnalyzeButton } from "../analyze-button/AnalyzeButton";
import { AnalysisStageCard } from "../analysis-stage-card/AnalysisStageCard";

type AnalysisDashboardProps = Readonly<{
  apiBaseUrl: string;
  sessionId: string;
  uploadState: UploadState | null;
}>;

const POLLING_INTERVAL_MS = 2500;

export function AnalysisDashboard({
  apiBaseUrl,
  sessionId,
  uploadState,
}: AnalysisDashboardProps) {
  const [analysisState, setAnalysisState] = useState<AnalysisState | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState("");

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
  }, [apiBaseUrl, sessionId]);

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
  }, [analysisState, apiBaseUrl, sessionId]);

  const canStart = Boolean(uploadState && sessionId) && !isStarting && !isAnalysisRunning(analysisState);
  const shouldShowCards = Boolean(
    analysisState &&
      analysisState.status !== "idle" &&
      (analysisState.file_name || analysisState.error || analysisState.extraction_output),
  );

  const extractionTone = useMemo(() => {
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
  }, [analysisState]);

  const parserTone = useMemo(() => {
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
  }, [analysisState]);

  const hierarchyTone = parserTone;

  async function handleStartAnalysis() {
    setIsStarting(true);
    setError("");

    try {
      const nextState = await startCurrentAnalysis(apiBaseUrl, sessionId);
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
            İşlem arka planda sürer. Sekmeyi kapatsanız bile durmaz; geri geldiğinizde
            son durumu bu panelden görebilirsiniz.
          </p>
        </div>
      </div>

      <AnalyzeButton
        disabled={!canStart}
        isBusy={isStarting || isAnalysisRunning(analysisState)}
        onClick={() => void handleStartAnalysis()}
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
            tone={extractionTone}
            preview={<ExtractionPreview state={analysisState} />}
            action={
              analysisState?.extraction_output ? (
                <ViewerLink
                  href={`/debug-flow/extraction-view?sessionId=${encodeURIComponent(sessionId)}`}
                  label="Yeni Sekmede Aç"
                />
              ) : null
            }
          />

          {analysisState?.status !== "queued" && analysisState?.status !== "extracting" ? (
            <AnalysisStageCard
              title="Parser Output"
              description={getParserOutputDescription(analysisState)}
              tone={parserTone}
              preview={<ParserOutputPreview state={analysisState} />}
              action={
                analysisState?.parser_output ? (
                  <ViewerLink
                    href={`/debug-flow/parser-output-view?sessionId=${encodeURIComponent(sessionId)}`}
                    label="Yeni Sekmede Aç"
                  />
                ) : null
              }
            />
          ) : null}

          {analysisState?.status !== "queued" && analysisState?.status !== "extracting" ? (
            <AnalysisStageCard
              title="Hiyerarşi Görünümü"
              description={getHierarchyDescription(analysisState)}
              tone={hierarchyTone}
              preview={<HierarchyPreview parserOutput={analysisState?.parser_output ?? null} />}
              action={
                analysisState?.parser_output ? (
                  <ViewerLink
                    href={`/debug-flow/parser-view?sessionId=${encodeURIComponent(sessionId)}`}
                    label="Yeni Sekmede Aç"
                  />
                ) : null
              }
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function isRunningState(status: AnalysisState["status"]) {
  return status === "queued" || status === "extracting" || status === "parsing";
}

function isAnalysisRunning(analysisState: AnalysisState | null) {
  return Boolean(analysisState && isRunningState(analysisState.status));
}

function getExtractionDescription(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "Docling çıktısı hazırlandığında burada görüntülenecek.";
  }
  if (analysisState.extraction_output) {
    return "Ham Docling extraction çıktısı pretty formatta önizleniyor.";
  }
  if (analysisState.status === "failed") {
    return analysisState.error ?? "Extraction aşaması tamamlanamadı.";
  }
  return "Docling extraction çıktısı hazırlanıyor. İçerik tamamlanınca kart otomatik güncellenir.";
}

function getParserDescription(analysisState: AnalysisState | null) {
  return getHierarchyDescription(analysisState);
}

function getParserOutputDescription(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "Parser çıktısı hazır olduğunda burada pretty formatta görüntülenecek.";
  }
  if (analysisState.parser_output) {
    return "Content stream ve heading hierarchy dahil ham parser çıktısı pretty formatta önizleniyor.";
  }
  if (analysisState.status === "failed") {
    return analysisState.error ?? "Parser aşaması tamamlanamadı.";
  }
  return "Extraction tamamlandıktan sonra parser çıktısı hazırlanıyor.";
}

function getHierarchyDescription(analysisState: AnalysisState | null) {
  if (!analysisState) {
    return "Hiyerarşi görünümü hazır olduğunda burada belge-benzeri olarak görüntülenecek.";
  }
  if (analysisState.parser_output) {
    return "Belge akışı ve başlık hiyerarşisi belge görünümüne yakın bir önizleme ile sunuluyor.";
  }
  if (analysisState.status === "failed") {
    return analysisState.error ?? "Parser aşaması tamamlanamadı.";
  }
  return "Belge akışı ve hiyerarşi çözülüyor. Hazır olduğunda belge benzeri önizleme açılacak.";
}

function ExtractionPreview({ state }: Readonly<{ state: AnalysisState | null }>) {
  if (!state?.extraction_output) {
    return (
      <div className={styles.loadingPreview}>
        <div className={styles.loadingBar} />
        <div className={styles.loadingBarShort} />
        <div className={styles.loadingBlock} />
      </div>
    );
  }

  return (
    <pre className={styles.jsonPreview}>
      {JSON.stringify(state.extraction_output, null, 2)}
    </pre>
  );
}

function ParserOutputPreview({ state }: Readonly<{ state: AnalysisState | null }>) {
  if (!state?.parser_output) {
    return (
      <div className={styles.loadingPreview}>
        <div className={styles.loadingBar} />
        <div className={styles.loadingBarShort} />
        <div className={styles.loadingBlock} />
      </div>
    );
  }

  return (
    <pre className={styles.jsonPreview}>
      {JSON.stringify(state.parser_output, null, 2)}
    </pre>
  );
}

function HierarchyPreview({ parserOutput }: Readonly<{ parserOutput: ParserOutput | null }>) {
  if (!parserOutput) {
    return (
      <div className={styles.loadingPreview}>
        <div className={styles.documentLine} />
        <div className={styles.documentLineLong} />
        <div className={styles.documentCard} />
      </div>
    );
  }

  return (
    <div className={styles.documentPreview}>
      <div className={styles.documentMeta}>
        <span>{parserOutput.document.file_name}</span>
        <span>{parserOutput.heading_hierarchy.length} kök başlık</span>
      </div>

      <div className={styles.documentSurface}>
        {parserOutput.heading_hierarchy.map((heading) => (
          <HeadingPreview key={heading.id} heading={heading} depth={0} />
        ))}
      </div>
    </div>
  );
}

function HeadingPreview({
  heading,
  depth,
}: Readonly<{ heading: HeadingHierarchyNode; depth: number }>) {
  return (
    <div className={styles.headingPreview} style={{ "--preview-depth": depth } as CSSProperties}>
      <p className={styles.headingCode}>
        {heading.code}
        {heading.title ? ` - ${heading.title}` : ""}
      </p>
      {heading.content_refs.length ? (
        <p className={styles.headingContentMeta}>{heading.content_refs.length} içerik bloğu</p>
      ) : null}
      {heading.children.map((child) => (
        <HeadingPreview key={child.id} heading={child} depth={depth + 1} />
      ))}
    </div>
  );
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
