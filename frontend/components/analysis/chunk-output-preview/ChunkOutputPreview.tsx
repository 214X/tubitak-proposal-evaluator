"use client";

import type { ChunkOutput } from "../../../lib/analysis";
import styles from "./chunk-output-preview.module.css";

type ChunkOutputPreviewProps = Readonly<{
  chunkOutput: ChunkOutput | null;
  isLoading: boolean;
  error: string;
}>;

export function ChunkOutputPreview({
  chunkOutput,
  isLoading,
  error,
}: ChunkOutputPreviewProps) {
  if (isLoading) {
    return (
      <div className={styles.loadingPreview}>
        <div className={styles.loadingLine} />
        <div className={styles.loadingLineShort} />
        <div className={styles.loadingBlock} />
      </div>
    );
  }

  if (error) {
    return <p className={styles.errorText}>{error}</p>;
  }

  if (!chunkOutput) {
    return (
      <div className={styles.loadingPreview}>
        <div className={styles.loadingLine} />
        <div className={styles.loadingLineShort} />
        <div className={styles.loadingBlock} />
      </div>
    );
  }

  const previewChunks = chunkOutput.chunks.slice(0, 4);

  return (
    <div className={styles.preview}>
      <div className={styles.metaRow}>
        <span>{chunkOutput.sections.length} section</span>
        <span>{chunkOutput.chunks.length} chunk</span>
      </div>

      <div className={styles.chunkList}>
        {previewChunks.map((chunk) => (
          <article key={chunk.chunk_id} className={styles.chunkCard}>
            <div className={styles.chunkHeader}>
              <span className={styles.chunkType}>{chunk.chunk_type}</span>
              <span className={styles.chunkOrder}>#{chunk.order_in_section}</span>
            </div>
            <p className={styles.chunkPath}>{chunk.heading_path_titles.join(" > ")}</p>
            <p className={styles.chunkSnippet}>{getChunkSnippet(chunk)}</p>
          </article>
        ))}
      </div>
    </div>
  );
}

function getChunkSnippet(chunk: ChunkOutput["chunks"][number]) {
  switch (chunk.chunk_type) {
    case "qa":
      return chunk.answer
        ? `Cevap: ${chunk.answer}`
        : chunk.guidance ?? chunk.question;
    case "table":
      return chunk.table_title
        ? `${chunk.table_title} • ${chunk.table_rows.length} satır`
        : `${chunk.table_rows.length} satırlık tablo`;
    case "list":
      return `${chunk.items.length} maddelik liste`;
    case "narrative":
      return chunk.text.slice(0, 140);
    default:
      return "";
  }
}
