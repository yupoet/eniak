"use client";

import { useState, useTransition } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Chapter, ReviewState } from "@/lib/api-types";

interface Props {
  bookId: string;
  chapter: Chapter;
}

const STATE_LABELS: Record<ReviewState, string> = {
  draft: "Draft",
  in_review: "In Review",
  approved: "Approved",
  published: "Published",
  rejected: "Rejected",
};

const NEXT_STATE: Record<ReviewState, ReviewState[]> = {
  draft: ["in_review", "rejected"],
  in_review: ["approved", "rejected", "draft"],
  approved: ["published", "in_review"],
  published: [],
  rejected: ["draft"],
};

export function ChapterReviewPanel({ bookId, chapter }: Props) {
  const [state, setState] = useState<ReviewState>(chapter.review_state);
  const [pending, startTransition] = useTransition();
  const [publishResult, setPublishResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const body = chapter.body_markdown.startsWith("# ")
    ? chapter.body_markdown.split("\n").slice(1).join("\n").trim()
    : chapter.body_markdown;

  function transition(target: ReviewState) {
    setError(null);
    startTransition(async () => {
      try {
        const res = await fetch(`/api/chapters/${chapter.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ review_state: target }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.error ?? `${res.status} ${res.statusText}`);
        }
        setState(target);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  function publish(target: "markdown" | "feishu", mode: "dry_run" | "live") {
    setPublishResult(null);
    setError(null);
    startTransition(async () => {
      try {
        const res = await fetch(`/api/books/${bookId}/publish`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chapter_id: chapter.id, target, mode }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.error ?? `${res.status} ${res.statusText}`);
        }
        const data = await res.json();
        setPublishResult(
          data.external_url
            ? `${target}/${mode}: ${data.external_url}`
            : `${target}/${mode} OK — payload ${JSON.stringify(data.payload_json).length} chars`,
        );
        if (data.error) setError(data.error);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  return (
    <article className="rounded-lg border border-ink-200/70 bg-paper shadow-card px-7 py-7">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-display text-2xl font-semibold tracking-tight">
          {chapter.title}
        </h2>
        <span className="rounded-full bg-ink-100 px-2.5 py-1 text-xs font-medium text-ink-600 inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {STATE_LABELS[state]}
        </span>
      </header>
      <p className="text-xs text-ink-400 font-mono mt-1">
        order #{chapter.order_index + 1} · run {chapter.run_id?.slice(0, 8) ?? "—"}
      </p>

      <div className="prose-eniak mt-5">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
      </div>

      <div className="mt-6 pt-4 border-t border-ink-200/70 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-ink-400 mr-1">Review:</span>
          {NEXT_STATE[state].map((target) => (
            <button
              key={target}
              type="button"
              onClick={() => transition(target)}
              disabled={pending}
              className="rounded-md border border-ink-200 bg-paper px-2.5 py-1 text-xs font-medium text-ink-600 hover:bg-ink-100/50 disabled:opacity-50 transition-colors"
            >
              → {STATE_LABELS[target]}
            </button>
          ))}
          {NEXT_STATE[state].length === 0 && (
            <span className="text-xs text-ink-400 italic">terminal state</span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-ink-400 mr-1">Publish:</span>
          <button
            type="button"
            onClick={() => publish("markdown", "dry_run")}
            disabled={pending}
            className="rounded-md border border-ink-200 bg-paper px-2.5 py-1 text-xs font-medium text-ink-600 hover:bg-ink-100/50 disabled:opacity-50 transition-colors"
          >
            Markdown (dry-run)
          </button>
          <button
            type="button"
            onClick={() => publish("feishu", "dry_run")}
            disabled={pending}
            className="rounded-md border border-ink-200 bg-paper px-2.5 py-1 text-xs font-medium text-ink-600 hover:bg-ink-100/50 disabled:opacity-50 transition-colors"
          >
            Feishu (dry-run)
          </button>
          <button
            type="button"
            onClick={() => publish("feishu", "live")}
            disabled={pending || state !== "approved"}
            className="rounded-md border border-accent bg-accent text-white px-2.5 py-1 text-xs font-medium hover:bg-accent-deep disabled:bg-ink-400 disabled:border-ink-400 transition-colors"
            title={state === "approved" ? "Publish live to Feishu" : "Approve chapter first"}
          >
            Feishu (live) →
          </button>
        </div>

        {publishResult && (
          <p className="text-xs text-ink-600 bg-emerald-50 border border-emerald-200 rounded px-3 py-2 font-mono">
            {publishResult}
          </p>
        )}
        {error && (
          <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            {error}
          </p>
        )}
      </div>
    </article>
  );
}
