"""Deterministic mock radar for Phase 2.

Returns a small set of plausible-looking source candidates per topic so the rest
of the pipeline (evidence extraction + chapter draft) can be exercised end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class SourceCandidate:
    title: str
    authors: list[str]
    venue: str
    url: str
    excerpt: str
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_kind: str = "mock"


_FIXTURES: list[tuple[str, str, str, str]] = [
    (
        "Toward Evidence-Native Research Pipelines",
        "P. Yu; J. Doe",
        "ENIAK Working Papers, 2026",
        "An evidence-native pipeline treats every generated claim as a node in a "
        "citation graph and forbids unsourced assertions in published artifacts.",
    ),
    (
        "Long-Horizon Agentic Workflows: A Survey",
        "L. Chen; M. Park",
        "arXiv:2509.18573",
        "Durable graph runtimes such as LangGraph enable resumable multi-actor "
        "workflows by checkpointing state to Postgres or SQLite between steps.",
    ),
    (
        "Citation Faithfulness in LLM-Generated Reports",
        "S. Kim; A. Patel",
        "Proceedings of the 2026 Workshop on Trustworthy Generation",
        "Citation faithfulness scores correlate strongly with downstream reviewer "
        "acceptance, especially when claims are anchored to verbatim quotes.",
    ),
]


class MockRadar:
    """Returns 3 deterministic source candidates per topic."""

    async def scan(self, topic: str, *, limit: int = 3) -> list[SourceCandidate]:
        candidates: list[SourceCandidate] = []
        for title, authors, venue, body in _FIXTURES[:limit]:
            tailored_excerpt = (
                f"In the context of \"{topic}\", the authors argue: {body}"
            )
            candidates.append(
                SourceCandidate(
                    title=title,
                    authors=[a.strip() for a in authors.split(";")],
                    venue=venue,
                    url=f"https://example.org/mock/{abs(hash((title, topic))) % 10_000_000}",
                    excerpt=tailored_excerpt,
                )
            )
        return candidates
