/**
 * Shared types between the browser bundle and server-only modules.
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

export type BookStatus = "draft" | "generating" | "ready_for_review" | "published" | "failed";

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

export interface Contradiction {
  id: string;
  claim_a_id: string;
  claim_b_id: string;
  severity: number | null;
  rationale: string | null;
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
  contradictions: Contradiction[];
  cost: CostSummary;
}

export interface BookSummary {
  id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  topic: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BookDetail extends BookSummary {
  chapters: Chapter[];
  cost: CostSummary;
}

export interface PublishRecord {
  id: string;
  book_id: string | null;
  chapter_id: string | null;
  target: "markdown" | "feishu";
  mode: "dry_run" | "live";
  external_id: string | null;
  external_url: string | null;
  version: number;
  payload_json: unknown;
  error: string | null;
  created_at: string;
}
