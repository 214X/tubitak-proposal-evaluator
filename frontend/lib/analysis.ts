"use client";

export type UploadState = {
  session_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
};

export type StageTiming = {
  started_at: string | null;
  completed_at: string | null;
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

export type ParserGanttTask = {
  label: string;
  start_week: number;
  end_week: number;
  months: string;
};

export type ParserGanttWorkPackage = {
  label: string;
  tasks: ParserGanttTask[];
};

export type ParserGanttChartContent = {
  type: "gantt_chart";
  title: string;
  months: string[];
  week_count: number;
  work_packages: ParserGanttWorkPackage[];
  image_uri?: string;
};

export type HeadingHierarchyNode = {
  id: string;
  ref: string;
  node_type: "section_heading" | "table_heading" | "numbered_heading";
  code: string;
  display_code: string | null;
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
  work_package_id: string | null;
  work_package_no: string | null;
  work_package_code: string | null;
  work_package_title: string | null;
  work_package_date_range: string | null;
  work_package_duration_text: string | null;
  work_package_organizations: string[];
  work_package_section_no: string | null;
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
  work_package_id: string | null;
  work_package_no: string | null;
  work_package_code: string | null;
  work_package_title: string | null;
  work_package_date_range: string | null;
  work_package_duration_text: string | null;
  work_package_organizations: string[];
  work_package_section_no: string | null;
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
  work_package_id: string | null;
  work_package_no: string | null;
  work_package_code: string | null;
  work_package_title: string | null;
  work_package_date_range: string | null;
  work_package_duration_text: string | null;
  work_package_organizations: string[];
  work_package_section_no: string | null;
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
  work_package_id: string | null;
  work_package_no: string | null;
  work_package_code: string | null;
  work_package_title: string | null;
  work_package_date_range: string | null;
  work_package_duration_text: string | null;
  work_package_organizations: string[];
  work_package_section_no: string | null;
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
  work_package_id: string | null;
  work_package_no: string | null;
  work_package_code: string | null;
  work_package_title: string | null;
  work_package_date_range: string | null;
  work_package_duration_text: string | null;
  work_package_organizations: string[];
  work_package_section_no: string | null;
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

export type EvidenceChunk = {
  chunk_id: string;
  chunk_type: "qa" | "narrative" | "table" | "list";
  heading_path_ids?: string[];
  heading_path_titles: string[];
  page_start: number | null;
  page_end: number | null;
  text_for_embedding: string;
  similarity_score: number;
};

export type EvidenceNarrative = {
  chunk_id: string;
  location_summary: string;
  evidence_text: string;
  why_it_matters: string;
};

export type CriterionEvaluationResult = {
  criterion_id: string;
  main_dimension_id: string | null;
  category: string | null;
  title: string;
  score: number | null;
  claim_strength: number | null;
  evidence_quality: number | null;
  weight: number;
  weighted_score: number | null;
  confidence: number;
  decision_status: "scored" | "insufficient_evidence" | "conflicting_evidence" | "failed";
  criterion_explanation: string;
  short_assessment: string;
  justification: string;
  positive_findings: Array<{
    summary: string;
    why_positive: string | null;
    why_negative: string | null;
    chunk_id: string;
  }>;
  negative_findings: Array<{
    summary: string;
    why_positive: string | null;
    why_negative: string | null;
    chunk_id: string;
  }>;
  supporting_chunk_ids: string[];
  contradicting_chunk_ids: string[];
  missing_information: string[];
  red_flags: string[];
  evidence_items: Array<{
    evidence_type: "positive" | "negative" | "context";
    chunk_id: string;
    verbatim_excerpt: string;
    heading_path: string[];
    page_start: number | null;
    page_end: number | null;
    why_it_matters: string;
  }>;
  primary_section_chunks: EvidenceChunk[];
  semantic_support_chunks: EvidenceChunk[];
  fallback_context_chunks: EvidenceChunk[];
  coverage_status: "complete" | "covered" | "partial" | "missing" | "unknown";
  coverage_notes: string[];
  supporting_evidence: EvidenceChunk[];
  contradicting_evidence: EvidenceChunk[];
  supporting_evidence_notes: EvidenceNarrative[];
  contradicting_evidence_notes: EvidenceNarrative[];
};

export type EvaluationReport = {
  session_id: string;
  rubric_id: string;
  rubric_version: string;
  overall_score: number | null;
  main_scores: Array<{
    main_dimension_id: string;
    title: string;
    weight: number;
    score: number | null;
    weighted_score: number | null;
    subcriteria_count: number;
    scored_subcriteria_count: number;
    summary: string;
  }>;
  rubric_table: Array<{
    main_dimension_title: string;
    criterion_id: string;
    main_dimension_id: string;
    criterion_title: string;
    description: string;
    weight: number;
    source_sections: string[];
    ui_label: string;
    score_min: number;
    score_max: number;
    ui_explanation: string;
  }>;
  subcriteria_results: CriterionEvaluationResult[];
  major_strengths: string[];
  major_weaknesses: string[];
  critical_missing_information: string[];
  red_flags: string[];
  total_weight: number | null;
  total_weighted_score: number | null;
  max_possible_weighted_score: number | null;
  scored_criteria_count: number | null;
  criterion_results: CriterionEvaluationResult[];
  strengths: string[];
  weaknesses: string[];
  final_summary: string;
};

export type EvaluationState = {
  session_id: string;
  status:
    | "idle"
    | "queued"
    | "retrieving"
    | "evaluating"
    | "aggregating"
    | "completed"
    | "failed";
  current_step: "none" | "retriever" | "judge" | "aggregator" | "done";
  rubric_id: string | null;
  rubric_version: string | null;
  active_criterion_id: string | null;
  active_criterion_title: string | null;
  active_subcriterion_id: string | null;
  active_subcriterion_title: string | null;
  active_main_dimension_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
  error: string | null;
  overall_score: number | null;
  main_scores: EvaluationReport["main_scores"];
  rubric_table: EvaluationReport["rubric_table"];
  subcriteria_results: CriterionEvaluationResult[];
  major_strengths: string[];
  major_weaknesses: string[];
  critical_missing_information: string[];
  red_flags: string[];
  criterion_results: CriterionEvaluationResult[];
  final_report: EvaluationReport | null;
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
  extraction_timing: StageTiming | null;
  parser_timing: StageTiming | null;
  chunking_timing: StageTiming | null;
  embedding_timing: StageTiming | null;
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

export async function startCurrentAnalysisUntilChunking(apiBaseUrl: string, sessionId: string) {
  const response = await fetch(`${apiBaseUrl}/api/analysis/current/start-until-chunking`, {
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

export async function fetchCurrentEvaluation(apiBaseUrl: string, sessionId: string) {
  const response = await fetch(`${apiBaseUrl}/api/evaluation/current`, {
    headers: {
      "X-Session-Id": sessionId,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Evaluation durumu alınamadı (Durum: ${response.status}).`);
  }

  return (await response.json()) as EvaluationState;
}

export async function startCurrentEvaluation(apiBaseUrl: string, sessionId: string) {
  const response = await fetch(`${apiBaseUrl}/api/evaluation/current/start`, {
    method: "POST",
    headers: {
      "X-Session-Id": sessionId,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Evaluation başlatılamadı (Durum: ${response.status}).`);
  }

  return (await response.json()) as EvaluationState;
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
