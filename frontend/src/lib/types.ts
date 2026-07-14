// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

// ─── Documents ────────────────────────────────────────────────────────────────

export type DocumentStatus = "processing" | "indexed" | "failed";
export type FilingType = "10-K" | "10-Q" | "8-K" | "DEF14A" | "OTHER";

export interface Document {
  id: string;
  name: string;
  ticker: string | null;
  filer_name: string;
  filing_type: FilingType;
  filing_date: string;
  page_count: number | null;
  // Not returned by GET /documents (list) — only available via the
  // single-document detail endpoint's nested `tree` summary.
  node_count?: number;
  status: DocumentStatus;
  ingest_error: string | null;
  // No file_size_bytes column exists on the backend yet — always absent.
  file_size_bytes?: number;
  ingested_at: string | null;
  created_at: string;
}

// Raw shape actually returned by GET /documents and GET /documents/{id}
// (backend's DocumentPublic) — field names and ingest_status's value set
// don't match `Document` above, so the API layer maps between them.
export interface DocumentRaw {
  id: string;
  filename: string;
  ticker: string | null;
  filer_name: string | null;
  filing_type: FilingType;
  filing_date: string | null;
  page_count: number | null;
  ingest_status: "pending" | "parsing" | "tree_building" | "embedding" | "ready" | "failed" | "deleted";
  ingest_error: string | null;
  created_at: string;
  updated_at: string;
  tree?: { node_count: number; ingested_at: string } | null;
}

export interface TreeNode {
  id: string;
  document_id: string;
  title: string;
  level: number;
  page_start: number;
  page_end: number;
  content_preview: string;
  children: TreeNode[];
  parent_id: string | null;
}

export interface IngestionProgress {
  document_id: string;
  phase: "parsing" | "tree-build" | "embed-fallback" | "done" | "failed";
  progress: number;
  message: string;
  error?: string;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export type RetrievalStrategy = "vectorless" | "hybrid" | "direct";

export interface Citation {
  id: string;
  node_id: string;
  document_id: string;
  document_name: string;
  section_title: string;
  page_start: number;
  page_end: number;
  excerpt: string;
  full_text: string;
  strategy: RetrievalStrategy;
  relevance_score: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  strategy_used: RetrievalStrategy | null;
  strategy_predicted: RetrievalStrategy | null;
  reasoning_trace: string | null;
  faithfulness_score: number | null;
  latency_ms: number | null;
  cost_usd: number | null;
  feedback: "up" | "down" | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  document_ids: string[];
  message_count: number;
  last_message_at: string;
  created_at: string;
}

// Shape actually returned by POST/GET/PATCH /conversations (backend's
// ConversationPublic) — distinct from `Conversation` above, which doesn't
// match any real endpoint response.
export interface ConversationSummary {
  id: string;
  title: string | null;
  document_ids: string[];
  created_at: string;
  updated_at: string;
}

// ─── WebSocket event types ────────────────────────────────────────────────────

export interface WSEventStart {
  type: "start";
  strategy_predicted: RetrievalStrategy;
  message_id: string;
}


export interface WSEventToken {
  type: "token";
  content: string;
}

export interface WSEventCitations {
  type: "citations";
  citations: Citation[];
}

export interface WSEventGrader {
  type: "grader";
  faithfulness_score: number;
  retry: boolean;
  explanation: string;
}

export interface WSEventEnd {
  type: "end";
  message_id: string;        // ← real DB UUID sent by backend for feedback
  latency_ms: number;
  cost_usd: number;
  strategy_used: RetrievalStrategy;
  reasoning_trace: string;
}


export interface WSEventError {
  type: "error";
  message: string;
}

export type WSEvent =
  | WSEventStart
  | WSEventToken
  | WSEventCitations
  | WSEventGrader
  | WSEventEnd
  | WSEventError;

// ─── Evaluation / Dashboard ───────────────────────────────────────────────────

export interface EvalRunSummary {
  id: string;
  dataset: string;
  run_date: string;
  overall_score: number;
  correct_pct: number | null;
  model_version: string;
  completed_at: string | null;
}

export interface CustomBenchmarkSummary {
  overall_score: number;
  run_date: string;
  total_questions: number;
}

// Matches backend's EvalSummaryResponse exactly (app/api/eval.py).
export interface EvalSummary {
  latest: EvalRunSummary | null;
  delta_overall_score: number | null;
  delta_correct_pct: number | null;
  per_strategy_accuracy: Record<string, number>;
  total_questions: number;
  p50_latency_ms: number | null;
  avg_cost_usd: number;
  custom: CustomBenchmarkSummary | null;
}

export interface EvalDataPoint {
  run_date: string;
  accuracy: number;
  vectorless_pct: number;
  hybrid_pct: number;
  direct_pct: number;
  avg_latency_ms: number;
  avg_cost_usd: number;
}

export interface StrategyDistribution {
  vectorless: number;
  hybrid: number;
  direct: number;
}

export interface QueryTypeAccuracy {
  query_type: "structural" | "cross_doc" | "keyword" | "direct";
  accuracy: number;
  count: number;
}

export interface FailureCase {
  id: string;
  question: string;
  predicted_answer: string;
  gold_answer: string;
  strategy_used: RetrievalStrategy | null;
  faithfulness_score: number;
  retrieved_sections: Citation[];
  // Not stored anywhere on the backend yet (app/db/models.py's
  // EvalQuestionResult has no columns for these) — always absent.
  reasoning_trace: string | null;
  grader_explanation: string | null;
  run_date: string;
}

// Raw shape actually returned by GET /eval/failures (backend's EvalFailure).
export interface FailureCaseRaw {
  question_id: string;
  question_text: string;
  predicted_answer: string;
  gold_answer: string;
  score: number;
  strategy_used: RetrievalStrategy | null;
  latency_ms: number | null;
  retrieved_sections_json: unknown;
  run_date: string;
}

// ─── API ──────────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
  status: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
