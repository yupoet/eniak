"""OpenAlex provider.

OpenAlex is a free scholarly database. No key needed but they ask consumers
to identify themselves via the ``mailto`` query parameter for higher rate
limits, so set ``ENIAK_OPENALEX_MAILTO=you@example.org`` if you can.

We hit ``https://api.openalex.org/works`` with a simple ``search`` param.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx

from eniak_radar.base import SourceCandidate

logger = logging.getLogger(__name__)

OPENALEX_API = "https://api.openalex.org/works"


def _parse_openalex(items: list[dict]) -> list[SourceCandidate]:
    out: list[SourceCandidate] = []
    for w in items:
        title = (w.get("title") or "").strip()
        if not title:
            continue
        doi = w.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/") :]
        abstract = ""
        inv = w.get("abstract_inverted_index") or {}
        if inv:
            # OpenAlex returns inverted index — reconstruct.
            positions: list[tuple[int, str]] = []
            for word, idxs in inv.items():
                for i in idxs:
                    positions.append((i, word))
            positions.sort()
            abstract = " ".join(w for _, w in positions)
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in w.get("authorships") or []
        ]
        authors = [a for a in authors if a]
        venue = ((w.get("primary_location") or {}).get("source") or {}).get(
            "display_name"
        ) or w.get("type") or "OpenAlex"
        url = w.get("primary_location", {}).get("landing_page_url") or w.get("id") or ""
        pdf_url = w.get("primary_location", {}).get("pdf_url")
        published_at = None
        if pub := w.get("publication_date"):
            try:
                published_at = datetime.fromisoformat(pub)
            except ValueError:
                pass

        out.append(
            SourceCandidate(
                title=title,
                authors=authors,
                venue=venue,
                url=url,
                excerpt=abstract[:2000],
                source_kind="openalex",
                doi=doi,
                pdf_url=pdf_url,
                published_at=published_at,
            )
        )
    return out


class OpenAlexRadar:
    name = "openalex"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        request_timeout: float = 30.0,
        mailto: str | None = None,
    ) -> None:
        self._client = client
        self._timeout = request_timeout
        self._mailto = mailto or os.environ.get("ENIAK_OPENALEX_MAILTO")

    async def scan(self, topic: str, *, limit: int = 5) -> list[SourceCandidate]:
        params: dict[str, str] = {
            "search": topic,
            "per-page": str(max(1, min(limit, 25))),
            "sort": "relevance_score:desc",
        }
        if self._mailto:
            params["mailto"] = self._mailto
        owns_client = False
        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout, follow_redirects=True)
            owns_client = True
        try:
            response = await client.get(OPENALEX_API, params=params)
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                await client.aclose()
        results = _parse_openalex(payload.get("results", []))
        logger.info(
            "openalex.scan", extra={"topic": topic[:80], "results": len(results)}
        )
        n = max(len(results), 1)
        return [
            SourceCandidate(**{**c.__dict__, "relevance": round(1.0 - (i / n), 4)})
            for i, c in enumerate(results)
        ]
