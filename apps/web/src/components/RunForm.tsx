"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/api";

export function RunForm() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = topic.trim();
    if (trimmed.length < 3) {
      setError("Give it at least three characters.");
      return;
    }
    startTransition(async () => {
      try {
        const run = await createRun(trimmed);
        setTopic("");
        router.push(`/runs/${run.id}`);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <label className="block text-sm text-ink-600">
        Research topic
        <textarea
          className="mt-1.5 block w-full rounded-md border border-ink-200 bg-paper px-3 py-2.5
                     font-display text-base text-ink-900 placeholder:text-ink-400
                     focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent"
          rows={3}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. citation faithfulness in LLM-generated reports"
          disabled={pending}
        />
      </label>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="inline-flex items-center gap-2 rounded-md bg-accent text-white
                     px-4 py-2 text-sm font-medium shadow-sticky hover:bg-accent-deep
                     disabled:bg-ink-400 disabled:shadow-none transition-colors"
        >
          {pending ? "Running…" : "Run dry-run loop →"}
        </button>
        <span className="text-xs text-ink-400">
          Hits Kimi/Qwen 1x for extraction per source + 1x for draft. ~30-90s.
        </span>
      </div>
      {error && (
        <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </p>
      )}
    </form>
  );
}
