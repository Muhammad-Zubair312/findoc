import type {
  AuthResponse,
  User,
  Document,
  DocumentRaw,
  DocumentStatus,
  TreeNode,
  Conversation,
  ConversationSummary,
  Message,
  Citation,
  RetrievalStrategy,
  EvalSummary,
  EvalDataPoint,
  FailureCase,
  FailureCaseRaw,
  QueryTypeAccuracy,
  PaginatedResponse,
  FilingType,
} from "@/lib/types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Backend's ingest_status has 7 values; the UI only distinguishes 3 states.
const INGEST_STATUS_TO_DOCUMENT_STATUS: Record<DocumentRaw["ingest_status"], DocumentStatus> = {
  pending: "processing",
  parsing: "processing",
  tree_building: "processing",
  embedding: "processing",
  ready: "indexed",
  failed: "failed",
  deleted: "failed",
};

function mapDocument(raw: DocumentRaw): Document {
  return {
    id: raw.id,
    name: raw.filename,
    ticker: raw.ticker,
    filer_name: raw.filer_name ?? "Unknown filer",
    filing_type: raw.filing_type,
    filing_date: raw.filing_date ?? raw.created_at,
    page_count: raw.page_count,
    node_count: raw.tree?.node_count,
    status: INGEST_STATUS_TO_DOCUMENT_STATUS[raw.ingest_status],
    ingest_error: raw.ingest_error,
    file_size_bytes: undefined,
    ingested_at: raw.tree?.ingested_at ?? null,
    created_at: raw.created_at,
  };
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: "Unknown error" }));
      const err = new Error(body.detail ?? res.statusText) as Error & {
        status: number;
      };
      (err as Error & { status: number }).status = res.status;
      throw err;
    }

    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  }

  // ─── Auth ─────────────────────────────────────────────────────────────────

  async login(email: string, password: string): Promise<AuthResponse> {
    return this.request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async register(
    email: string,
    password: string,
    full_name: string
  ): Promise<AuthResponse> {
    return this.request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    });
  }

  async logout(): Promise<void> {
    return this.request<void>("/auth/logout", { method: "POST" });
  }

  async getMe(): Promise<User> {
    return this.request<User>("/auth/me");
  }

  async refreshToken(): Promise<AuthResponse> {
    return this.request<AuthResponse>("/auth/refresh", { method: "POST" });
  }

  // ─── Documents ────────────────────────────────────────────────────────────

  async listDocuments(params?: {
    filing_type?: FilingType | "all";
    sort?: "date_desc" | "date_asc" | "name";
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Document>> {
    const qs = new URLSearchParams();
    if (params?.filing_type && params.filing_type !== "all")
      qs.set("filing_type", params.filing_type);
    if (params?.sort) qs.set("sort", params.sort);
    if (params?.search) qs.set("search", params.search);
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const raw = await this.request<{
      items: DocumentRaw[];
      total: number;
      page: number;
      page_size: number;
    }>(`/documents?${qs.toString()}`);
    return { ...raw, items: raw.items.map(mapDocument) };
  }

  async getDocument(id: string): Promise<Document> {
    const raw = await this.request<DocumentRaw>(`/documents/${id}`);
    return mapDocument(raw);
  }

  async deleteDocument(id: string): Promise<void> {
    return this.request<void>(`/documents/${id}`, { method: "DELETE" });
  }

  async reingestDocument(id: string): Promise<void> {
    return this.request<void>(`/documents/${id}/reingest`, { method: "POST" });
  }

  async getDocumentTree(id: string): Promise<TreeNode[]> {
    return this.request<TreeNode[]>(`/documents/${id}/tree`);
  }

  async loadSampleDocument(): Promise<Document> {
    return this.request<Document>("/documents/sample", { method: "POST" });
  }

  async uploadDocument(file: File): Promise<{ document_id: string }> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${this.baseUrl}/documents/upload`, {
      method: "POST",
      credentials: "include",
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(body.detail ?? res.statusText);
    }
    return res.json();
  }

  async fetchFromEdgar(params: {
    ticker: string;
    form_type: string;
    year: number;
  }): Promise<{ document_id: string }> {
    return this.request<{ document_id: string }>("/documents/fetch-edgar", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  // ─── Conversations ────────────────────────────────────────────────────────

  async listConversations(limit = 20): Promise<Conversation[]> {
    return this.request<Conversation[]>(`/conversations?limit=${limit}`);
  }

  async getConversation(id: string): Promise<Conversation> {
    return this.request<Conversation>(`/conversations/${id}`);
  }

  async createConversation(document_ids: string[]): Promise<ConversationSummary> {
    return this.request<ConversationSummary>("/conversations", {
      method: "POST",
      body: JSON.stringify({ document_ids }),
    });
  }

  async deleteConversation(id: string): Promise<void> {
    return this.request<void>(`/conversations/${id}`, { method: "DELETE" });
  }

  async getMessages(conversation_id: string): Promise<Message[]> {
    // No dedicated GET /conversations/{id}/messages endpoint exists — the
    // backend only returns messages nested inside the full conversation
    // (ConversationDetail). citations_json/feedback/strategy_predicted don't
    // match the Message shape 1:1, so map them explicitly rather than
    // casting.
    const conversation = await this.request<{
      messages: Array<{
        id: string;
        role: "user" | "assistant";
        content: string;
        strategy_used: RetrievalStrategy | null;
        faithfulness_score: number | null;
        latency_ms: number | null;
        cost_usd: number | null;
        citations_json: Citation[] | null;
        reasoning_trace: string | null;
        created_at: string;
      }>;
    }>(`/conversations/${conversation_id}`);

    return conversation.messages.map((m) => ({
      id: m.id,
      conversation_id,
      role: m.role,
      content: m.content,
      citations: m.citations_json ?? [],
      strategy_used: m.strategy_used,
      strategy_predicted: null,
      reasoning_trace: m.reasoning_trace,
      faithfulness_score: m.faithfulness_score,
      latency_ms: m.latency_ms,
      cost_usd: m.cost_usd,
      feedback: null,
      created_at: m.created_at,
    }));
  }

  // ─── Feedback ─────────────────────────────────────────────────────────────

  async submitFeedback(
    message_id: string,
    feedback: "up" | "down"
  ): Promise<void> {
    return this.request<void>(`/messages/${message_id}/feedback`, {
      method: "POST",
      body: JSON.stringify({ feedback }),
    });
  }

  // ─── Eval / Dashboard ─────────────────────────────────────────────────────

  async getEvalSummary(): Promise<EvalSummary> {
    return this.request<EvalSummary>("/eval/summary");
  }

  async getEvalHistory(days = 30): Promise<EvalDataPoint[]> {
    return this.request<EvalDataPoint[]>(`/eval/history?days=${days}`);
  }

  async getEvalFailures(limit = 10): Promise<FailureCase[]> {
    const raw = await this.request<FailureCaseRaw[]>(`/eval/failures?limit=${limit}`);
    return raw.map((f) => ({
      id: f.question_id,
      question: f.question_text,
      predicted_answer: f.predicted_answer,
      gold_answer: f.gold_answer,
      strategy_used: f.strategy_used,
      faithfulness_score: f.score,
      retrieved_sections: [],
      reasoning_trace: null,
      grader_explanation: null,
      run_date: f.run_date,
    }));
  }

  async getQueryTypeAccuracy(): Promise<QueryTypeAccuracy[]> {
    return this.request<QueryTypeAccuracy[]>("/eval/query-types");
  }

  async runEval(): Promise<{ run_id: string }> {
    return this.request<{ run_id: string }>("/eval/run", { 
        method: "POST",
        body: JSON.stringify({})
    });
}
}

export const api = new ApiClient(API_URL);
export default api;
