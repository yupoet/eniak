import Link from "next/link";
import type { RunSummary } from "@/lib/api";
import { StatusPill } from "./StatusPill";

interface Props {
  runs: RunSummary[];
}

export function RunList({ runs }: Props) {
  if (runs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-200 bg-paper px-6 py-12 text-center">
        <p className="text-ink-600">No runs yet.</p>
        <p className="text-sm text-ink-400 mt-1">
          Submit a topic above to start your first evidence-native draft.
        </p>
      </div>
    );
  }
  return (
    <ul className="divide-y divide-ink-200/70 rounded-lg border border-ink-200/70 bg-paper shadow-card overflow-hidden">
      {runs.map((run) => (
        <li key={run.id}>
          <Link
            href={`/runs/${run.id}`}
            className="block px-5 py-4 hover:bg-ink-100/50 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-display text-base text-ink-900 truncate">
                  {run.topic}
                </p>
                <p className="text-xs text-ink-400 mt-1 font-mono">
                  {run.model ?? "no model"} · {formatTime(run.created_at)}
                </p>
              </div>
              <StatusPill status={run.status} />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
