import type { EvidenceCard } from "@/lib/api";

export function EvidenceCardItem({ card }: { card: EvidenceCard }) {
  return (
    <article
      id={`card-${card.id}`}
      className="rounded-lg border border-ink-200/70 bg-paper shadow-card px-5 py-4 flex flex-col gap-2"
    >
      <header className="flex items-center justify-between text-[0.7rem] text-ink-400 font-mono">
        <span>#{card.id.slice(0, 8)}</span>
        <span>{card.review_state}</span>
      </header>
      <p className="text-sm text-ink-900 leading-relaxed">{card.summary}</p>
      {card.quote && (
        <blockquote className="text-sm italic text-ink-600 border-l-2 border-accent-soft pl-3">
          “{card.quote}”
        </blockquote>
      )}
      <footer className="text-[0.7rem] text-ink-400 font-mono mt-auto pt-2">
        confidence: {card.confidence?.toFixed(2) ?? "—"}
      </footer>
    </article>
  );
}
