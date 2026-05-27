import type { RunStatus } from "@/lib/api";

const PALETTE: Record<RunStatus, { bg: string; text: string; label: string }> = {
  pending: { bg: "bg-ink-100", text: "text-ink-600", label: "Pending" },
  running: { bg: "bg-amber-100", text: "text-amber-800", label: "Running" },
  succeeded: { bg: "bg-emerald-100", text: "text-emerald-800", label: "Succeeded" },
  failed: { bg: "bg-red-100", text: "text-red-800", label: "Failed" },
  cancelled: { bg: "bg-ink-100", text: "text-ink-600", label: "Cancelled" },
};

export function StatusPill({ status }: { status: RunStatus }) {
  const p = PALETTE[status] ?? PALETTE.pending;
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full ${p.bg} ${p.text}
                  px-2.5 py-1 text-xs font-medium`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {p.label}
    </span>
  );
}
