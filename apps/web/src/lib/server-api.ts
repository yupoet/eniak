/**
 * Server-only helpers for talking to the FastAPI backend.
 *
 * Hosting context:
 * - eniak-web runs as a Cloudflare Worker behind www.eniak.org.
 * - api.eniak.org is ALSO a Cloudflare Worker (eniak-api-proxy) in the same
 *   account. A Worker fetching its own zone via the public hostname can hit
 *   Cloudflare's "direct IP / loopback" interlock (error 1003) intermittently
 *   depending on which edge POP handles the request.
 * - Going direct to Railway side-steps that loopback entirely. The Railway
 *   service is reachable at https://eniak-api-production.up.railway.app and
 *   accepts requests with its own Host header — no proxy rewrite needed.
 *
 * Resolution order:
 *   1. ENIAK_INTERNAL_API_BASE  ← preferred; set on the Worker to the Railway URL
 *   2. NEXT_PUBLIC_API_BASE     ← fallback used in local dev
 *   3. http://localhost:8000    ← last-resort default
 */
import "server-only";

import type {
  RunDetail,
  RunSummary,
} from "./api-types";

function readEnv(name: string): string | undefined {
  // Cloudflare Workers expose bindings/secrets via the request-scoped env object.
  // Read at call time so we don't capture an empty process.env at module load.
  const fromProcess = typeof process !== "undefined" ? process.env?.[name] : undefined;
  if (fromProcess) return fromProcess;
  return undefined;
}

function apiBase(): string {
  return (
    readEnv("ENIAK_INTERNAL_API_BASE") ??
    readEnv("NEXT_PUBLIC_API_BASE") ??
    "http://localhost:8000"
  );
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
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
  const apiKey = readEnv("ENIAK_API_KEY") ?? "";
  if (!apiKey) {
    throw new Error("ENIAK_API_KEY is not configured on the frontend Worker.");
  }
  return request<RunSummary>("/runs", {
    method: "POST",
    body: JSON.stringify({ topic }),
    headers: { Authorization: `Bearer ${apiKey}` },
  });
}

export async function getChapterMarkdownServer(runId: string): Promise<string> {
  const res = await request<{ markdown: string }>(`/runs/${runId}/chapter.md`);
  return res.markdown;
}
