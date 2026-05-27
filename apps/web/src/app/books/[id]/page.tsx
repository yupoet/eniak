import Link from "next/link";
import { notFound } from "next/navigation";
import { getBookServer } from "@/lib/server-api";
import { ChapterReviewPanel } from "@/components/ChapterReviewPanel";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function BookDetailPage({ params }: Props) {
  const { id } = await params;
  let book: Awaited<ReturnType<typeof getBookServer>>;
  try {
    book = await getBookServer(id);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-10">
      <section>
        <Link href="/books" className="text-sm text-ink-400 hover:text-ink-900">
          ← Back to books
        </Link>
        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-900">
              {book.title}
            </h1>
            {book.subtitle && (
              <p className="mt-1 text-ink-600 italic">{book.subtitle}</p>
            )}
            {book.topic && (
              <p className="mt-1 text-xs text-ink-400 font-mono">topic: {book.topic}</p>
            )}
          </div>
          <span className="rounded-full bg-ink-100 px-2.5 py-1 text-xs font-medium text-ink-600">
            {book.status.replace(/_/g, " ")}
          </span>
        </div>
        <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 text-xs">
          <Stat label="Chapters" value={String(book.chapters.length)} />
          <Stat label="Tokens" value={book.cost.total_tokens.toLocaleString()} />
          <Stat
            label="Cost (USD)"
            value={book.cost.cost_usd ? `$${book.cost.cost_usd.toFixed(5)}` : "$0"}
          />
          <Stat label="Created" value={new Date(book.created_at).toLocaleString()} />
        </dl>
      </section>

      <section className="space-y-10">
        {book.chapters.length === 0 ? (
          <p className="rounded-lg border border-dashed border-ink-200 bg-paper px-6 py-12 text-center text-sm text-ink-400">
            Generating chapters… refresh in a minute.
          </p>
        ) : (
          book.chapters.map((chapter) => (
            <ChapterReviewPanel
              key={chapter.id}
              bookId={book.id}
              chapter={chapter}
            />
          ))
        )}
      </section>
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
