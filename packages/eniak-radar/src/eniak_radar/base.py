"""Provider base + shared SourceCandidate.

A radar provider takes a topic string and returns a list of SourceCandidate
records. Implementations live in sibling modules (``mock``, ``arxiv``,
``openalex``, ...). The registry in ``eniak_radar.registry`` chooses which
ones run based on env config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class SourceCandidate:
    """A normalised source descriptor.

    Fields are deliberately optional so providers don't have to fill what
    they don't know. Dedup happens on ``dedup_key`` (DOI > arXiv id > URL).
    """

    title: str
    authors: list[str]
    venue: str
    url: str
    excerpt: str
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_kind: str = "unknown"
    arxiv_id: str | None = None
    doi: str | None = None
    pdf_url: str | None = None
    published_at: datetime | None = None
    relevance: float | None = None  # 0..1, provider's own ranking
    extra: dict | None = None

    @property
    def dedup_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower().strip('/')}"
        if self.arxiv_id:
            return f"arxiv:{self.arxiv_id}"
        return f"url:{self.url}"


class RadarProvider(Protocol):
    """Async provider interface. Implementations return up to ``limit`` results."""

    name: str

    async def scan(self, topic: str, *, limit: int = 5) -> list[SourceCandidate]: ...
