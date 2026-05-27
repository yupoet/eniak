"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

export function BookForm() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [chapterCount, setChapterCount] = useState(3);
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
        const res = await fetch("/api/books", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ topic: trimmed, chapter_count: chapterCount }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.error ?? `${res.status} ${res.statusText}`);
        }
        const book = await res.json();
        setTopic("");
        router.push(`/books/${book.id}`);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <label className="block text-sm text-ink-600">
        Book topic
        <textarea
          className="mt-1.5 block w-full rounded-md border border-ink-200 bg-paper px-3 py-2.5
                     font-display text-base text-ink-900 placeholder:text-ink-400
                     focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent"
          rows={3}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. structural integrity of citation graphs in long-form research writing"
          disabled={pending}
        />
      </label>
      <div className="flex items-center gap-3">
        <label className="text-sm text-ink-600 inline-flex items-center gap-2">
          Chapters
          <input
            type="number"
            min={1}
            max={8}
            value={chapterCount}
            onChange={(e) => setChapterCount(Number(e.target.value))}
            className="w-16 rounded-md border border-ink-200 bg-paper px-2 py-1 font-mono text-sm"
            disabled={pending}
          />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="inline-flex items-center gap-2 rounded-md bg-accent text-white
                     px-4 py-2 text-sm font-medium shadow-sticky hover:bg-accent-deep
                     disabled:bg-ink-400 disabled:shadow-none transition-colors"
        >
          {pending ? "Planning…" : "Plan + draft book →"}
        </button>
        <span className="text-xs text-ink-400">
          Takes ~{chapterCount * 90}s. Returns immediately with book id.
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
