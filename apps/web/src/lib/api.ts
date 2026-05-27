// Client + server helpers for talking to the FastAPI backend.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type RunStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type ReviewState =
  | "draft"
  | "in_review"
  | "approved"
  | "published"
  | "rejected";

export interface RunSummary {
  id: string;
  topic: string;
  status: RunStatus;
  model: string | null;
  provider: string | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceCard {
  id: string;
  source_id: string;
  run_id: string | null;
  summary: string;
  quote: string | null;
  page: number | null;
  section: string | null;
  confidence: number | null;
  review_state: ReviewState;
  created_at: string;
}

export interface Chapter {
  id: string;
  title: string;
  body_markdown: string;
  order_index: number;
  review_state: ReviewState;
  run_id: string | null;
  book_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CostSummary {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
}

export interface RunDetail extends RunSummary {
  evidence_cards: EvidenceCard[];
  chapters: Chapter[];
  cost: CostSummary;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function listRuns(): Promise<RunSummary[]> {
  return request<RunSummary[]>("/runs?limit=50");
}

export async function getRun(id: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${id}`);
}

export async function createRun(topic: string): Promise<RunSummary> {
  return request<RunSummary>("/runs", {
    method: "POST",
    body: JSON.stringify({ topic }),
  });
}

export async function getChapterMarkdown(runId: string): Promise<string> {
  const res = await request<{ markdown: string }>(`/runs/${runId}/chapter.md`);
  return res.markdown;
}
