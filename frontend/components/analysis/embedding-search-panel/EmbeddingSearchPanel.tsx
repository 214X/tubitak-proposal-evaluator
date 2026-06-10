"use client";

import { useMemo, useState } from "react";

import {
  type ChunkOutput,
  type EmbeddingOutput,
  type EmbeddingSearchResponse,
  searchCurrentEmbeddings,
} from "../../../lib/analysis";
import styles from "./embedding-search-panel.module.css";

type ChunkType = ChunkOutput["chunks"][number]["chunk_type"];

const CHUNK_TYPE_OPTIONS: Array<{ value: ChunkType; label: string }> = [
  { value: "qa", label: "QA" },
  { value: "narrative", label: "Narrative" },
  { value: "table", label: "Table" },
  { value: "list", label: "List" },
];

type EmbeddingSearchPanelProps = Readonly<{
  apiBaseUrl: string;
  sessionId: string;
  chunkOutput: ChunkOutput;
  embeddingOutput: EmbeddingOutput | null;
  analysisStatus:
    | "idle"
    | "queued"
    | "extracting"
    | "parsing"
    | "chunking"
    | "embedding"
    | "completed"
    | "failed";
}>;

export function EmbeddingSearchPanel({
  apiBaseUrl,
  sessionId,
  chunkOutput,
  embeddingOutput,
  analysisStatus,
}: EmbeddingSearchPanelProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState("5");
  const [selectedChunkTypes, setSelectedChunkTypes] = useState<ChunkType[]>([]);
  const [searchResponse, setSearchResponse] = useState<EmbeddingSearchResponse | null>(null);
  const [error, setError] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  const availableChunkTypes = useMemo(
    () => new Set(chunkOutput.chunks.map((chunk) => chunk.chunk_type)),
    [chunkOutput.chunks],
  );

  const canSearch = Boolean(embeddingOutput) && !isSearching;
  const statusText = getStatusText(analysisStatus, embeddingOutput);

  async function handleSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setError("Arama sorgusu boş bırakılamaz.");
      return;
    }
    if (!embeddingOutput) {
      setError("Embedding çıktısı hazır değil.");
      return;
    }

    setIsSearching(true);
    setError("");

    try {
      const response = await searchCurrentEmbeddings(apiBaseUrl, sessionId, {
        query: trimmedQuery,
        top_k: Number.parseInt(topK, 10) || 5,
        chunk_types: selectedChunkTypes,
      });
      setSearchResponse(response);
    } catch (currentError) {
      setError(
        currentError instanceof Error
          ? currentError.message
          : "Embedding araması tamamlanamadı.",
      );
    } finally {
      setIsSearching(false);
    }
  }

  function toggleChunkType(chunkType: ChunkType) {
    setSelectedChunkTypes((current) =>
      current.includes(chunkType)
        ? current.filter((value) => value !== chunkType)
        : [...current, chunkType],
    );
  }

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Embedding Search</p>
          <h2 className={styles.title}>Semantic Retrieval Debug</h2>
        </div>
        <div className={styles.summary}>
          <p className={styles.summaryLine}>{statusText}</p>
          {embeddingOutput ? (
            <p className={styles.summaryLine}>
              {embeddingOutput.model_name} • {embeddingOutput.vector_dimensions} boyut •{" "}
              {embeddingOutput.chunk_count} chunk
            </p>
          ) : null}
        </div>
      </div>

      <form className={styles.form} onSubmit={(event) => void handleSearch(event)}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>Sorgu</span>
          <textarea
            className={styles.queryInput}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Örn. bütçe kalemleri, iş-zaman planı, proje çıktıları..."
            rows={4}
            disabled={!canSearch}
          />
        </label>

        <div className={styles.controls}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Top K</span>
            <select
              className={styles.select}
              value={topK}
              onChange={(event) => setTopK(event.target.value)}
              disabled={!canSearch}
            >
              <option value="3">3</option>
              <option value="5">5</option>
              <option value="8">8</option>
              <option value="10">10</option>
            </select>
          </label>

          <div className={styles.field}>
            <span className={styles.fieldLabel}>Chunk Filters</span>
            <div className={styles.filterRow}>
              {CHUNK_TYPE_OPTIONS.filter((option) => availableChunkTypes.has(option.value)).map(
                (option) => (
                  <label key={option.value} className={styles.checkboxLabel}>
                    <input
                      type="checkbox"
                      checked={selectedChunkTypes.includes(option.value)}
                      onChange={() => toggleChunkType(option.value)}
                      disabled={!canSearch}
                    />
                    <span>{option.label}</span>
                  </label>
                ),
              )}
            </div>
          </div>

          <button type="submit" className={styles.searchButton} disabled={!canSearch}>
            {isSearching ? "Aranıyor..." : "Search Embeddings"}
          </button>
        </div>
      </form>

      {error ? <p className={styles.error}>{error}</p> : null}

      {searchResponse ? (
        <div className={styles.results}>
          <div className={styles.resultsHeader}>
            <p className={styles.resultsTitle}>
              {searchResponse.results.length} sonuç • sorgu: {searchResponse.query}
            </p>
          </div>

          {searchResponse.results.length ? (
            <div className={styles.resultList}>
              {searchResponse.results.map((result, index) => (
                <article key={`${result.chunk_id}-${index}`} className={styles.resultCard}>
                  <div className={styles.resultMeta}>
                    <p className={styles.resultType}>{result.chunk_type}</p>
                    <p className={styles.resultScore}>{result.similarity_score.toFixed(4)}</p>
                  </div>
                  <p className={styles.resultPath}>{result.heading_path_titles.join(" > ")}</p>
                  <p className={styles.resultChunkId}>{result.chunk_id}</p>
                  <p className={styles.resultText}>{result.text_for_embedding}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className={styles.empty}>Filtrelere uygun sonuç bulunamadı.</p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function getStatusText(
  analysisStatus: EmbeddingSearchPanelProps["analysisStatus"],
  embeddingOutput: EmbeddingOutput | null,
) {
  if (embeddingOutput) {
    return `Embedding hazır • ${new Date(embeddingOutput.embedded_at).toLocaleString("tr-TR")}`;
  }
  if (analysisStatus === "embedding") {
    return "Chunklar embed ediliyor.";
  }
  if (analysisStatus === "failed") {
    return "Embedding akışı hata ile sonlandı.";
  }
  return "Embedding çıktısı henüz hazır değil.";
}
