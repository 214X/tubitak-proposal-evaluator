"use client";

export type UploadState = {
  session_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
};

export type ExtractionOutput = {
  document: {
    file_name: string;
    page_count: number;
  };
  docling_output: Record<string, unknown>;
};

export type ParserStreamItem = {
  ref: string;
  order: number;
  item_type: "text" | "table" | "picture" | "group" | "key_value" | "form_item" | "unknown";
  label: string | null;
  page_start: number | null;
  page_end: number | null;
  content: unknown;
};

export type ParserListContent = {
  type: "list";
  items: string[];
};

export type HeadingHierarchyNode = {
  id: string;
  ref: string;
  node_type: "section_heading" | "table_heading" | "numbered_heading";
  code: string;
  title: string | null;
  full_text: string;
  level: number;
  parent_id: string | null;
  page_start: number | null;
  page_end: number | null;
  stream_order: number;
  path: string[];
  content_refs: string[];
  children: HeadingHierarchyNode[];
};

export type ParserOutput = {
  document: {
    file_name: string;
    page_count: number;
  };
  docling_output: Record<string, unknown>;
  content_stream: ParserStreamItem[];
  heading_hierarchy: HeadingHierarchyNode[];
};

export type SectionContainer = {
  id: string;
  heading_path_ids: string[];
  heading_path_titles: string[];
  leaf_heading: string;
  page_start: number | null;
  page_end: number | null;
  content_refs: string[];
};

export type QAChunk = {
  chunk_id: string;
  document_id: string;
  section_id: string;
  heading_path_ids: string[];
  heading_path_titles: string[];
  chunk_type: "qa";
  page_start: number | null;
  page_end: number | null;
  order_in_section: number;
  text_for_embedding: string;
  question: string;
  guidance: string | null;
  answer: string | null;
};

export type NarrativeChunk = {
  chunk_id: string;
  document_id: string;
  section_id: string;
  heading_path_ids: string[];
  heading_path_titles: string[];
  chunk_type: "narrative";
  page_start: number | null;
  page_end: number | null;
  order_in_section: number;
  text_for_embedding: string;
  text: string;
  part_index: number | null;
  part_count: number | null;
};

export type TableChunk = {
  chunk_id: string;
  document_id: string;
  section_id: string;
  heading_path_ids: string[];
  heading_path_titles: string[];
  chunk_type: "table";
  page_start: number | null;
  page_end: number | null;
  order_in_section: number;
  text_for_embedding: string;
  table_title: string | null;
  table_columns: string[];
  table_rows: string[][];
};

export type ListChunk = {
  chunk_id: string;
  document_id: string;
  section_id: string;
  heading_path_ids: string[];
  heading_path_titles: string[];
  chunk_type: "list";
  page_start: number | null;
  page_end: number | null;
  order_in_section: number;
  text_for_embedding: string;
  items: string[];
};

export type ChunkOutput = {
  document_id: string;
  sections: SectionContainer[];
  chunks: Array<QAChunk | NarrativeChunk | TableChunk | ListChunk>;
};

export type EmbeddingOutput = {
  session_id: string;
  document_id: string;
  provider_name: "bge_m3";
  model_name: string;
  vector_dimensions: number;
  chunk_count: number;
  embedded_at: string;
};

export type EmbeddingSearchResult = {
  chunk_id: string;
  document_id: string;
  section_id: string;
  chunk_type: "qa" | "narrative" | "table" | "list";
  heading_path_titles: string[];
  page_start: number | null;
  page_end: number | null;
  text_for_embedding: string;
  similarity_score: number;
};

export type EmbeddingSearchResponse = {
  session_id: string;
  query: string;
  provider_name: "bge_m3";
  model_name: string;
  vector_dimensions: number;
  top_k: number;
  results: EmbeddingSearchResult[];
};

export type AnalysisState = {
  session_id: string;
  status:
    | "idle"
    | "queued"
    | "extracting"
    | "parsing"
    | "chunking"
    | "embedding"
    | "completed"
    | "failed";
  current_step: "none" | "extractor" | "parser" | "chunker" | "embedder" | "done";
  file_name: string | null;
  started_at: string | null;
  updated_at: string | null;
  error: string | null;
  extraction_output: ExtractionOutput | null;
  parser_output: ParserOutput | null;
  chunk_output: ChunkOutput | null;
  embedding_output: EmbeddingOutput | null;
};

export async function fetchCurrentAnalysis(apiBaseUrl: string, sessionId: string) {
  const response = await fetch(`${apiBaseUrl}/api/analysis/current`, {
    headers: {
      "X-Session-Id": sessionId,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Analiz durumu alınamadı (Durum: ${response.status}).`);
  }

  return (await response.json()) as AnalysisState;
}

export async function startCurrentAnalysis(apiBaseUrl: string, sessionId: string) {
  const response = await fetch(`${apiBaseUrl}/api/analysis/current/start`, {
    method: "POST",
    headers: {
      "X-Session-Id": sessionId,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Analiz başlatılamadı (Durum: ${response.status}).`);
  }

  return (await response.json()) as AnalysisState;
}

export async function fetchCurrentChunkOutput(apiBaseUrl: string, sessionId: string) {
  const response = await fetch(`${apiBaseUrl}/api/chunking/current/chunk-output`, {
    method: "POST",
    headers: {
      "X-Session-Id": sessionId,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Chunk çıktısı alınamadı (Durum: ${response.status}).`);
  }

  return (await response.json()) as ChunkOutput;
}

export async function fetchCurrentEmbedding(apiBaseUrl: string, sessionId: string) {
  const response = await fetch(`${apiBaseUrl}/api/embedding/current`, {
    headers: {
      "X-Session-Id": sessionId,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Embedding çıktısı alınamadı (Durum: ${response.status}).`);
  }

  return (await response.json()) as EmbeddingOutput;
}

export async function searchCurrentEmbeddings(
  apiBaseUrl: string,
  sessionId: string,
  payload: {
    query: string;
    top_k: number;
    chunk_types: Array<"qa" | "narrative" | "table" | "list">;
  },
) {
  const response = await fetch(`${apiBaseUrl}/api/embedding/current/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": sessionId,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(
      errorPayload?.detail ?? `Embedding araması yapılamadı (Durum: ${response.status}).`,
    );
  }

  return (await response.json()) as EmbeddingSearchResponse;
}
