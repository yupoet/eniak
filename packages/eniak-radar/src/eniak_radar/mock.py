"""Deterministic mock radar.

Provides repeatable canned source candidates so tests can exercise the full
pipeline without hitting any external API. The real ``SourceCandidate`` lives
in ``eniak_radar.base``; mock re-imports it for backwards compatibility.
"""

from __future__ import annotations

from eniak_radar.base import SourceCandidate

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
    name = "mock"

    async def scan(self, topic: str, *, limit: int = 3) -> list[SourceCandidate]:
        candidates: list[SourceCandidate] = []
        for title, authors, venue, body in _FIXTURES[: max(1, min(limit, len(_FIXTURES)))]:
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
                    source_kind="mock",
                )
            )
        return candidates
