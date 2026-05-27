import Link from "next/link";
import { listBooksServer } from "@/lib/server-api";
import { BookForm } from "@/components/BookForm";

export const dynamic = "force-dynamic";

export default async function BooksPage() {
  let books: Awaited<ReturnType<typeof listBooksServer>> = [];
  let apiError: string | null = null;
  try {
    books = await listBooksServer();
  } catch (err) {
    apiError = err instanceof Error ? err.message : String(err);
  }

  return (
    <div className="space-y-12">
      <section>
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink-900">
          Plan a research book
        </h1>
        <p className="mt-3 max-w-2xl text-ink-600 leading-relaxed">
          Give a single topic. ENIAK generates an outline of 3–5 chapters and
          then drives a dry-run loop per chapter — radar fan-out, evidence
          extraction, citation-faithful draft, contradictions. Review and
          publish to Markdown or Feishu when you&apos;re ready.
        </p>
        <div className="mt-6 max-w-2xl">
          <BookForm />
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
            Recent books
          </h2>
          <span className="text-xs text-ink-400">
            {books.length} book{books.length === 1 ? "" : "s"}
          </span>
        </header>
        {books.length === 0 ? (
          <p className="mt-4 rounded-lg border border-dashed border-ink-200 bg-paper px-6 py-12 text-center text-sm text-ink-400">
            No books yet. Submit a topic above to plan one.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-ink-200/70 rounded-lg border border-ink-200/70 bg-paper shadow-card overflow-hidden">
            {books.map((book) => (
              <li key={book.id}>
                <Link
                  href={`/books/${book.id}`}
                  className="block px-5 py-4 hover:bg-ink-100/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="font-display text-base text-ink-900 truncate">
                        {book.title}
                      </p>
                      <p className="text-xs text-ink-400 mt-1 font-mono">
                        {book.topic ?? "—"} · {new Date(book.created_at).toLocaleString()}
                      </p>
                    </div>
                    <BookStatusPill status={book.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function BookStatusPill({ status }: { status: string }) {
  const palette: Record<string, { bg: string; text: string }> = {
    draft: { bg: "bg-ink-100", text: "text-ink-600" },
    generating: { bg: "bg-amber-100", text: "text-amber-800" },
    ready_for_review: { bg: "bg-emerald-100", text: "text-emerald-800" },
    published: { bg: "bg-accent-soft", text: "text-accent-deep" },
    failed: { bg: "bg-red-100", text: "text-red-800" },
  };
  const p = palette[status] ?? palette.draft;
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full ${p.bg} ${p.text}
                  px-2.5 py-1 text-xs font-medium`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {status.replace(/_/g, " ")}
    </span>
  );
}
