"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type AnalysisState,
  type ChunkOutput,
  type SectionContainer,
  fetchCurrentAnalysis,
} from "../../../lib/analysis";
import { readSessionId } from "../../../lib/session";
import styles from "./chunk-document-viewer.module.css";

type ChunkDocumentViewerProps = Readonly<{
  apiBaseUrl: string;
  initialSessionId?: string | null;
}>;

export function ChunkDocumentViewer({
  apiBaseUrl,
  initialSessionId = null,
}: ChunkDocumentViewerProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [analysisState, setAnalysisState] = useState<AnalysisState | null>(null);
  const [chunkOutput, setChunkOutput] = useState<ChunkOutput | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const nextSessionId = initialSessionId ?? readSessionId();
    setSessionId(nextSessionId);

    if (!nextSessionId) {
      setError("Aktif bir oturum bulunamadı.");
      return;
    }

    let cancelled = false;
    void fetchCurrentAnalysis(apiBaseUrl, nextSessionId)
      .then((nextState) => {
        if (!cancelled) {
          setAnalysisState(nextState);
          setChunkOutput(nextState.chunk_output);
          setError("");
        }
      })
      .catch((currentError) => {
        if (!cancelled) {
          setError(
            currentError instanceof Error
              ? currentError.message
              : "Chunk çıktısı yüklenemedi.",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, initialSessionId]);

  const sectionsById = useMemo(() => {
    if (!chunkOutput) {
      return new Map<string, SectionContainer>();
    }

    return new Map(chunkOutput.sections.map((section) => [section.id, section]));
  }, [chunkOutput]);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Chunk Viewer</p>
          <h1 className={styles.title}>Chunk Görünümü</h1>
        </div>
        {sessionId ? <p className={styles.session}>Session: {sessionId}</p> : null}
      </header>

      {error ? <p className={styles.error}>{error}</p> : null}

      <section className={styles.canvas}>
        {chunkOutput ? (
          <article className={styles.document}>
            <div className={styles.documentHeader}>
              <p className={styles.documentMetaLabel}>Hazırlanan chunk görünümü</p>
              <h2 className={styles.documentTitle}>{chunkOutput.document_id}</h2>
              <p className={styles.documentMeta}>
                {chunkOutput.sections.length} section • {chunkOutput.chunks.length} chunk
                {analysisState?.updated_at ? ` • ${formatUpdatedAt(analysisState.updated_at)}` : ""}
              </p>
            </div>

            <div className={styles.documentBody}>
              {chunkOutput.chunks.map((chunk) => (
                <ChunkCard
                  key={chunk.chunk_id}
                  chunk={chunk}
                  section={sectionsById.get(chunk.section_id) ?? null}
                />
              ))}
            </div>
          </article>
        ) : (
          <div className={styles.emptyState}>
            <div className={styles.emptyLine} />
            <div className={styles.emptyLineLong} />
            <div className={styles.emptySheet} />
          </div>
        )}
      </section>
    </main>
  );
}

function formatUpdatedAt(updatedAt: string) {
  const date = new Date(updatedAt);
  if (Number.isNaN(date.getTime())) {
    return "güncelleme zamanı bilinmiyor";
  }

  return `son güncelleme ${date.toLocaleString("tr-TR")}`;
}

function ChunkCard({
  chunk,
  section,
}: Readonly<{
  chunk: ChunkOutput["chunks"][number];
  section: SectionContainer | null;
}>) {
  return (
    <section className={styles.chunkCard} data-type={chunk.chunk_type}>
      <div className={styles.chunkHeader}>
        <div className={styles.chunkMetaBlock}>
          <p className={styles.chunkType}>{chunk.chunk_type}</p>
          <h3 className={styles.chunkTitle}>
            {section?.leaf_heading ?? chunk.heading_path_titles.at(-1) ?? chunk.section_id}
          </h3>
          <p className={styles.chunkPath}>{chunk.heading_path_titles.join(" > ")}</p>
        </div>

        <div className={styles.chunkMetaSide}>
          <p className={styles.chunkOrder}>Sıra {chunk.order_in_section}</p>
          <p className={styles.chunkPage}>
            Sayfa {chunk.page_start ?? "?"}
            {chunk.page_end && chunk.page_end !== chunk.page_start ? ` - ${chunk.page_end}` : ""}
          </p>
        </div>
      </div>

      <div className={styles.chunkBody}>{renderChunkBody(chunk)}</div>
    </section>
  );
}

function renderChunkBody(chunk: ChunkOutput["chunks"][number]) {
  switch (chunk.chunk_type) {
    case "qa":
      return (
        <div className={styles.qaBlock}>
          <div className={styles.fieldBlock}>
            <p className={styles.fieldLabel}>Soru</p>
            <p className={styles.fieldValue}>{chunk.question}</p>
          </div>
          {chunk.guidance ? (
            <div className={styles.fieldBlock}>
              <p className={styles.fieldLabel}>Açıklama</p>
              <p className={styles.fieldValue}>{chunk.guidance}</p>
            </div>
          ) : null}
          {chunk.answer ? (
            <div className={styles.fieldBlock}>
              <p className={styles.fieldLabel}>Cevap</p>
              <p className={styles.answerPill}>{chunk.answer}</p>
            </div>
          ) : null}
        </div>
      );
    case "narrative":
      return <p className={styles.paragraph}>{chunk.text}</p>;
    case "list":
      return (
        <ul className={styles.list}>
          {chunk.items.map((item) => (
            <li key={`${chunk.chunk_id}-${item.slice(0, 24)}`} className={styles.listItem}>
              {item}
            </li>
          ))}
        </ul>
      );
    case "table":
      return <TableChunkBody chunk={chunk} />;
    default:
      return null;
  }
}

function TableChunkBody({
  chunk,
}: Readonly<{
  chunk: Extract<ChunkOutput["chunks"][number], { chunk_type: "table" }>;
}>) {
  const [isNormalizedVisible, setIsNormalizedVisible] = useState(false);
  const embeddingLines = chunk.text_for_embedding
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <div className={styles.tablePanel}>
      <div className={styles.embeddingPanel}>
        <p className={styles.fieldLabel}>Text For Embedding</p>
        <div className={styles.embeddingText}>
          {embeddingLines.map((line, index) => (
            <p
              key={`${chunk.chunk_id}-embedding-line-${index}`}
              className={index === 0 ? styles.embeddingHeading : styles.embeddingRow}
            >
              {line}
            </p>
          ))}
        </div>
      </div>

      <button
        type="button"
        className={styles.toggleButton}
        onClick={() => setIsNormalizedVisible((current) => !current)}
      >
        {isNormalizedVisible ? "Normalize Tabloyu Gizle" : "Normalize Tabloyu Göster"}
      </button>

      {isNormalizedVisible ? (
        <div className={styles.normalizedPanel}>
          {chunk.table_title ? <p className={styles.tableTitle}>{chunk.table_title}</p> : null}
          {looksLikeFormTable(chunk.table_columns, chunk.table_rows) ? (
            <FormTablePreview chunk={chunk} />
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                {chunk.table_columns.length ? (
                  <thead>
                    <tr>
                      {chunk.table_columns.map((column, columnIndex) => (
                        <th key={`${chunk.chunk_id}-column-${columnIndex}`}>{column}</th>
                      ))}
                    </tr>
                  </thead>
                ) : null}
                <tbody>
                  {chunk.table_rows.map((row, rowIndex) => (
                    <tr key={`${chunk.chunk_id}-row-${rowIndex}`}>
                      {row.map((cell, cellIndex) => (
                        <td key={`${chunk.chunk_id}-cell-${rowIndex}-${cellIndex}`}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function FormTablePreview({
  chunk,
}: Readonly<{
  chunk: Extract<ChunkOutput["chunks"][number], { chunk_type: "table" }>;
}>) {
  const fieldRows = [chunk.table_columns, ...chunk.table_rows]
    .map((row) => compressTableRow(row))
    .filter((row) => row.length > 0);

  return (
    <div className={styles.formTable}>
      {fieldRows.map((row, rowIndex) => (
        <div key={`${chunk.chunk_id}-form-row-${rowIndex}`} className={styles.formRow}>
          {renderFieldPairs(row).map((field, fieldIndex) => (
            <div key={`${chunk.chunk_id}-field-${rowIndex}-${fieldIndex}`} className={styles.formField}>
              <p className={styles.formLabel}>{field.label}</p>
              <p className={styles.formValue}>{field.value}</p>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function looksLikeFormTable(columns: string[], rows: string[][]) {
  const compressedColumns = compressTableRow(columns);
  const compressedRows = rows.map((row) => compressTableRow(row)).filter((row) => row.length > 0);

  if (!compressedColumns.length || !compressedRows.length) {
    return false;
  }

  if (![2, 4].includes(compressedColumns.length)) {
    return false;
  }

  const evenRows = compressedRows.filter((row) => [2, 4].includes(row.length)).length;
  if (evenRows < Math.max(1, Math.floor(compressedRows.length / 2))) {
    return false;
  }

  return new Set(compressedColumns).size < compressedColumns.length || compressedColumns.length === 2;
}

function compressTableRow(row: string[]) {
  const compressed: string[] = [];

  for (const value of row) {
    const normalized = value.trim();
    if (!normalized) {
      continue;
    }
    if (compressed.at(-1) === normalized) {
      continue;
    }
    compressed.push(normalized);
  }

  return compressed;
}

function renderFieldPairs(row: string[]) {
  if (row.length === 1) {
    return [{ label: row[0], value: "" }];
  }

  const fields: Array<{ label: string; value: string }> = [];

  if (row.length % 2 === 0) {
    for (let index = 0; index < row.length; index += 2) {
      fields.push({
        label: row[index] ?? "",
        value: row[index + 1] ?? "",
      });
    }
    return fields;
  }

  return row.map((value) => ({ label: value, value: "" }));
}
