/**
 * Shared types between the browser bundle and server-only modules.
 * Pure type declarations — no runtime code, so safe to import from either side.
 */

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
