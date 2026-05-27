"use client";

import { useState, useTransition } from "react";
import type { EvidenceCard, ReviewState } from "@/lib/api-types";

const NEXT_STATES: Record<ReviewState, ReviewState[]> = {
  draft: ["in_review", "rejected"],
  in_review: ["approved", "rejected", "draft"],
  approved: ["in_review"],
  published: [],
  rejected: ["draft"],
};

const LABEL: Record<ReviewState, string> = {
  draft: "draft",
  in_review: "in review",
  approved: "approved",
  published: "published",
  rejected: "rejected",
};

export function EvidenceCardItem({
  card,
  runId,
}: {
  card: EvidenceCard;
  runId: string;
}) {
  const [state, setState] = useState<ReviewState>(card.review_state);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function transition(target: ReviewState) {
    setError(null);
    startTransition(async () => {
      try {
        const res = await fetch(`/api/runs/${runId}/cards/${card.id}`, {
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

  return (
    <article
      id={`card-${card.id}`}
      className="rounded-lg border border-ink-200/70 bg-paper shadow-card px-5 py-4 flex flex-col gap-2"
    >
      <header className="flex items-center justify-between text-[0.7rem] text-ink-400 font-mono">
        <span>#{card.id.slice(0, 8)}</span>
        <span className="text-ink-600">{LABEL[state]}</span>
      </header>
      <p className="text-sm text-ink-900 leading-relaxed">{card.summary}</p>
      {card.quote && (
        <blockquote className="text-sm italic text-ink-600 border-l-2 border-accent-soft pl-3">
          “{card.quote}”
          {card.page != null && (
            <span className="block text-[0.7rem] text-ink-400 font-mono mt-1">
              p. {card.page}
              {card.section ? ` · ${card.section}` : ""}
            </span>
          )}
        </blockquote>
      )}
      <footer className="text-[0.7rem] text-ink-400 font-mono mt-auto pt-2 space-y-1.5">
        <div>confidence: {card.confidence?.toFixed(2) ?? "—"}</div>
        <div className="flex flex-wrap gap-1">
          {NEXT_STATES[state].map((target) => (
            <button
              key={target}
              type="button"
              onClick={() => transition(target)}
              disabled={pending}
              className="rounded border border-ink-200 bg-paper px-1.5 py-0.5 text-[0.65rem] text-ink-600 hover:bg-ink-100/50 disabled:opacity-50 font-mono"
            >
              {LABEL[target]}
            </button>
          ))}
        </div>
        {error && <p className="text-red-700">{error}</p>}
      </footer>
    </article>
  );
}
