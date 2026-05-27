import { listRuns } from "@/lib/api";
import { RunForm } from "@/components/RunForm";
import { RunList } from "@/components/RunList";

export const runtime = "edge";
export const dynamic = "force-dynamic";

export default async function HomePage() {
  let runs: Awaited<ReturnType<typeof listRuns>> = [];
  let apiError: string | null = null;
  try {
    runs = await listRuns();
  } catch (err) {
    apiError = err instanceof Error ? err.message : String(err);
  }

  return (
    <div className="space-y-12">
      <section>
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink-900">
          Start a research run
        </h1>
        <p className="mt-3 max-w-2xl text-ink-600 leading-relaxed">
          Give ENIAK a research topic. The dry-run loop fans out to a mock radar,
          extracts evidence cards through the model, and returns a citation-faithful
          chapter draft. Every claim points back to a source, and every call lands
          on the cost ledger.
        </p>
        <div className="mt-6 max-w-2xl">
          <RunForm />
        </div>
        {apiError && (
          <p className="mt-4 max-w-2xl rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <strong className="font-semibold">API unreachable.</strong> {apiError}
          </p>
        )}
      </section>

      <section>
        <header className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl font-semibold tracking-tight">
            Recent runs
          </h2>
          <span className="text-xs text-ink-400">
            {runs.length} run{runs.length === 1 ? "" : "s"}
          </span>
        </header>
        <div className="mt-4">
          <RunList runs={runs} />
        </div>
      </section>
    </div>
  );
}
