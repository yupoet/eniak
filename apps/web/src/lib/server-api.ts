/**
 * Server-only helpers for talking to the FastAPI backend.
 *
 * Read endpoints don't need auth; ``createRunServer`` does, so it injects the
 * ``ENIAK_API_KEY`` env var (set as a Worker secret in production) so the key
 * never lands in the browser.
 */
import "server-only";

import type {
  RunDetail,
  RunSummary,
} from "./api-types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const API_KEY = process.env.ENIAK_API_KEY ?? "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
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

export function listRunsServer(): Promise<RunSummary[]> {
  return request<RunSummary[]>("/runs?limit=50");
}

export function getRunServer(id: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${id}`);
}

export async function createRunServer(topic: string): Promise<RunSummary> {
  if (!API_KEY) {
    throw new Error("ENIAK_API_KEY is not configured on the frontend Worker.");
  }
  return request<RunSummary>("/runs", {
    method: "POST",
    body: JSON.stringify({ topic }),
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
}

export async function getChapterMarkdownServer(runId: string): Promise<string> {
  const res = await request<{ markdown: string }>(`/runs/${runId}/chapter.md`);
  return res.markdown;
}
