/**
 * Browser-safe client. POST goes through the Next.js route handler at /api/runs
 * so the secret never lands in the browser bundle.
 */
import type { RunSummary } from "./api-types";

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function createRun(topic: string): Promise<RunSummary> {
  return postJson<RunSummary>("/api/runs", { topic });
}

export type {
  Chapter,
  CostSummary,
  EvidenceCard,
  ReviewState,
  RunDetail,
  RunStatus,
  RunSummary,
} from "./api-types";
