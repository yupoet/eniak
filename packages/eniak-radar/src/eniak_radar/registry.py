"""Provider registry + fanout + dedup.

Resolution order:

1. ``ENIAK_RADAR_PROVIDERS`` env (comma-separated, e.g. ``arxiv,openalex``)
2. Default: ``arxiv,openalex``

If a topic returns zero results from real providers, we fall back to the
mock so the dry-run never silently produces empty output during development.
"""

from __future__ import annotations

import asyncio
import logging
import os

from eniak_radar.arxiv import ArxivRadar
from eniak_radar.base import RadarProvider, SourceCandidate
from eniak_radar.mock import MockRadar
from eniak_radar.openalex import OpenAlexRadar

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type] = {
    "arxiv": ArxivRadar,
    "openalex": OpenAlexRadar,
    "mock": MockRadar,
}


def build_default_providers() -> list[RadarProvider]:
    raw = os.environ.get("ENIAK_RADAR_PROVIDERS", "arxiv,openalex").strip()
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    providers: list[RadarProvider] = []
    for n in names:
        cls = _PROVIDERS.get(n)
        if cls is None:
            logger.warning("radar.unknown_provider", extra={"name": n})
            continue
        providers.append(cls())
    if not providers:
        providers.append(MockRadar())
    return providers


def _dedup_and_rank(
    batches: list[list[SourceCandidate]], limit: int
) -> list[SourceCandidate]:
    """Merge results from multiple providers, dedup by dedup_key, keep best
    relevance per key, return top ``limit`` ordered by relevance desc."""
    seen: dict[str, SourceCandidate] = {}
    for batch in batches:
        for c in batch:
            existing = seen.get(c.dedup_key)
            if existing is None:
                seen[c.dedup_key] = c
                continue
            # Prefer the one with PDF + the higher relevance.
            existing_score = (existing.pdf_url is not None, existing.relevance or 0)
            new_score = (c.pdf_url is not None, c.relevance or 0)
            if new_score > existing_score:
                seen[c.dedup_key] = c
    ranked = sorted(
        seen.values(), key=lambda c: (c.relevance or 0.0), reverse=True
    )
    return ranked[:limit]


class RadarFanout:
    """Runs all configured providers in parallel and returns deduped results."""

    def __init__(self, providers: list[RadarProvider] | None = None) -> None:
        self.providers = providers or build_default_providers()

    async def scan(self, topic: str, *, limit: int = 5) -> list[SourceCandidate]:
        per_provider_limit = max(limit, 5)

        async def _safe_scan(p: RadarProvider) -> list[SourceCandidate]:
            try:
                return await p.scan(topic, limit=per_provider_limit)
            except Exception:
                logger.exception("radar.provider_failed", extra={"provider": p.name})
                return []

        batches = await asyncio.gather(*[_safe_scan(p) for p in self.providers])
        merged = _dedup_and_rank(batches, limit)
        if merged:
            return merged
        # Fall back to mock so the loop never starves on an empty topic.
        logger.warning("radar.empty.falling_back_to_mock", extra={"topic": topic[:80]})
        return await MockRadar().scan(topic, limit=limit)
