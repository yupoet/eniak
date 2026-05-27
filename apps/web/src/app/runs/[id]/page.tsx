import { notFound } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getRunServer } from "@/lib/server-api";
import { StatusPill } from "@/components/StatusPill";
import { EvidenceCardItem } from "@/components/EvidenceCardItem";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function RunDetailPage({ params }: Props) {
  const { id } = await params;
  let detail: Awaited<ReturnType<typeof getRunServer>>;
  try {
    detail = await getRunServer(id);
  } catch {
    notFound();
  }

  const chapter = detail.chapters[0];
  const cardById = Object.fromEntries(detail.evidence_cards.map((c) => [c.id, c]));
  const renderedBody = chapter
    ? annotateCitations(stripLeadingH1(chapter.body_markdown), cardById)
    : "";

  return (
    <div className="space-y-10">
      <section>
        <Link href="/" className="text-sm text-ink-400 hover:text-ink-900">
          ← Back to runs
        </Link>
        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-900">
            {detail.topic}
          </h1>
          <StatusPill status={detail.status} />
        </div>
        <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 text-xs">
          <Stat label="Model" value={detail.model ?? "—"} />
          <Stat label="Provider" value={detail.provider ?? "—"} />
          <Stat label="Tokens" value={detail.cost.total_tokens.toLocaleString()} />
          <Stat
            label="Cost (USD)"
            value={detail.cost.cost_usd ? `$${detail.cost.cost_usd.toFixed(5)}` : "$0"}
          />
        </dl>
        {detail.error && (
          <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {detail.error}
          </p>
        )}
      </section>

      <section>
        <h2 className="font-display text-xl font-semibold tracking-tight mb-3">
          Evidence cards
        </h2>
        <div className="grid sm:grid-cols-2 gap-3">
          {detail.evidence_cards.map((card) => (
            <EvidenceCardItem key={card.id} card={card} runId={detail.id} />
          ))}
        </div>
      </section>

      {detail.contradictions.length > 0 && (
        <section>
          <h2 className="font-display text-xl font-semibold tracking-tight mb-3">
            Contradictions detected
          </h2>
          <ul className="space-y-2">
            {detail.contradictions.map((c) => (
              <li
                key={c.id}
                className="rounded-md border border-amber-200 bg-amber-50/60 px-4 py-3 text-sm"
              >
                <p className="text-ink-900">
                  <span className="font-mono text-xs text-amber-800 mr-2">
                    severity {(c.severity ?? 0).toFixed(2)}
                  </span>
                  {c.rationale ?? "(no rationale)"}
                </p>
                <p className="text-xs text-ink-400 font-mono mt-1">
                  claim {c.claim_a_id.slice(0, 8)} ↔ {c.claim_b_id.slice(0, 8)}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {chapter && (
        <section>
          <h2 className="font-display text-xl font-semibold tracking-tight mb-3">
            Chapter draft
          </h2>
          <article className="rounded-lg border border-ink-200/70 bg-paper shadow-card px-7 py-7">
            <h3 className="font-display text-2xl font-semibold tracking-tight mb-4">
              {chapter.title}
            </h3>
            <div className="prose-eniak">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Render bare card refs ourselves; ReactMarkdown will pass others through.
                }}
              >
                {renderedBody}
              </ReactMarkdown>
            </div>
            <div className="mt-6 pt-4 border-t border-ink-200/70 flex items-center gap-3 text-xs text-ink-400">
              <span>review state: {chapter.review_state}</span>
              <a
                className="text-accent hover:text-accent-deep underline underline-offset-2"
                href={`/api/runs/${detail.id}/chapter.md`}
              >
                Download Markdown
              </a>
            </div>
          </article>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="uppercase tracking-wide text-ink-400">{label}</dt>
      <dd className="font-mono text-ink-900 mt-0.5">{value}</dd>
    </div>
  );
}

function stripLeadingH1(body: string): string {
  return body.startsWith("# ") ? body.split("\n").slice(1).join("\n").trim() : body;
}

// Convert raw [card:<id>] references into clickable anchor links to the card list.
function annotateCitations(
  body: string,
  cardById: Record<string, { id: string }>,
): string {
  return body.replace(/\[card:([0-9a-fA-F\-]+)\]/g, (_, id) => {
    if (!(id in cardById)) return `\`[card:${id.slice(0, 6)}…]\``;
    return `[\`#${id.slice(0, 6)}\`](#card-${id})`;
  });
}
