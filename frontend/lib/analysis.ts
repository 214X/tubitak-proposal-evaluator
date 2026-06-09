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

export type AnalysisState = {
  session_id: string;
  status: "idle" | "queued" | "extracting" | "parsing" | "completed" | "failed";
  current_step: "none" | "extractor" | "parser" | "done";
  file_name: string | null;
  started_at: string | null;
  updated_at: string | null;
  error: string | null;
  extraction_output: ExtractionOutput | null;
  parser_output: ParserOutput | null;
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
