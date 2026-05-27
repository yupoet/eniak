/**
 * Server-only helpers for talking to the FastAPI backend.
 *
 * eniak-web runs as a Cloudflare Worker. We talk to Railway directly via
 * ``ENIAK_INTERNAL_API_BASE`` to avoid the api.eniak.org Worker-to-Worker
 * loopback (which intermittently 1003s on some edge POPs).
 */
import "server-only";

import type {
  BookDetail,
  BookSummary,
  PublishRecord,
  ReviewState,
  RunDetail,
  RunSummary,
} from "./api-types";

function readEnv(name: string): string | undefined {
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

function requireApiKey(): string {
  const apiKey = readEnv("ENIAK_API_KEY") ?? "";
  if (!apiKey) {
    throw new Error("ENIAK_API_KEY is not configured on the frontend Worker.");
  }
  return apiKey;
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

async function requestText(path: string, init: RequestInit = {}): Promise<string> {
  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: { ...(init.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.text();
}

// --- runs ---

export function listRunsServer(): Promise<RunSummary[]> {
  return request<RunSummary[]>("/runs?limit=50");
}

export function getRunServer(id: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${id}`);
}

export async function createRunServer(topic: string): Promise<RunSummary> {
  return request<RunSummary>("/runs", {
    method: "POST",
    body: JSON.stringify({ topic }),
    headers: { Authorization: `Bearer ${requireApiKey()}` },
  });
}

export async function getChapterMarkdownServer(runId: string): Promise<string> {
  const res = await request<{ markdown: string }>(`/runs/${runId}/chapter.md`);
  return res.markdown;
}

// --- books ---

export function listBooksServer(): Promise<BookSummary[]> {
  return request<BookSummary[]>("/books?limit=50");
}

export function getBookServer(id: string): Promise<BookDetail> {
  return request<BookDetail>(`/books/${id}`);
}

export async function createBookServer(
  topic: string,
  chapterCount = 3,
): Promise<BookSummary> {
  return request<BookSummary>("/books", {
    method: "POST",
    body: JSON.stringify({ topic, chapter_count: chapterCount }),
    headers: { Authorization: `Bearer ${requireApiKey()}` },
  });
}

export function listPublishesServer(bookId: string): Promise<PublishRecord[]> {
  return request<PublishRecord[]>(`/books/${bookId}/publish?limit=50`);
}

export async function publishChapterServer(
  bookId: string,
  chapterId: string,
  target: "markdown" | "feishu",
  mode: "dry_run" | "live",
): Promise<PublishRecord> {
  return request<PublishRecord>(
    `/books/${bookId}/publish/${chapterId}`,
    {
      method: "POST",
      body: JSON.stringify({ target, mode }),
      headers: { Authorization: `Bearer ${requireApiKey()}` },
    },
  );
}

// --- review state machine ---

export async function updateCardServer(
  runId: string,
  cardId: string,
  reviewState: ReviewState,
) {
  return request(`/runs/${runId}/cards/${cardId}`, {
    method: "PATCH",
    body: JSON.stringify({ review_state: reviewState }),
    headers: { Authorization: `Bearer ${requireApiKey()}` },
  });
}

export async function updateChapterServer(
  chapterId: string,
  reviewState: ReviewState,
) {
  return request(`/chapters/${chapterId}`, {
    method: "PATCH",
    body: JSON.stringify({ review_state: reviewState }),
    headers: { Authorization: `Bearer ${requireApiKey()}` },
  });
}
