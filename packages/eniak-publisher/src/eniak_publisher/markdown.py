"""Markdown export adapter.

The first publisher per review recommendation: zero auth, validates the contract,
makes Lark/PDF adapters drop-in replacements later.
"""

from __future__ import annotations

from dataclasses import dataclass

from eniak_evidence.models import Chapter, EvidenceCard, Source


@dataclass(frozen=True)
class MarkdownPayload:
    title: str
    body: str
    references: str

    def render(self) -> str:
        return f"# {self.title}\n\n{self.body}\n\n## References\n\n{self.references}\n"


class MarkdownPublisher:
    """Render a Chapter + its EvidenceCards + Sources as a single Markdown doc."""

    def publish(
        self,
        chapter: Chapter,
        cards: list[EvidenceCard],
        sources_by_card: dict[str, Source],
    ) -> MarkdownPayload:
        references_lines: list[str] = []
        for idx, card in enumerate(cards, start=1):
            src = sources_by_card.get(card.id)
            if src is None:
                continue
            authors = ", ".join(src.authors or []) or "Unknown"
            line = f"{idx}. {authors}. *{src.title}*. {src.venue or ''}".strip().rstrip(".")
            if src.url:
                line += f". <{src.url}>"
            references_lines.append(line)
        body = chapter.body_markdown
        # Strip the H1 from the body if the chapter already carries one.
        if body.startswith("# "):
            _, _, body = body.partition("\n")
            body = body.lstrip()
        return MarkdownPayload(
            title=chapter.title,
            body=body,
            references="\n".join(references_lines),
        )
