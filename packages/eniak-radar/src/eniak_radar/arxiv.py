"""arXiv provider.

Queries ``export.arxiv.org/api/query`` (Atom XML). No API key required, but
arXiv asks consumers to keep request rate <= 1 every 3 seconds.

References:
- https://info.arxiv.org/help/api/user-manual.html
- The Atom feed uses the schema in ``http://arxiv.org/schemas/atom``.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Final

import httpx
from lxml import etree

from eniak_radar.base import SourceCandidate

logger = logging.getLogger(__name__)

ARXIV_API: Final[str] = "http://export.arxiv.org/api/query"
NS: Final[dict[str, str]] = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}
_ARXIV_ID_RE = re.compile(r"abs/([0-9]+\.[0-9]+(?:v[0-9]+)?)")


def _parse_atom(xml_bytes: bytes) -> list[SourceCandidate]:
    root = etree.fromstring(xml_bytes)
    candidates: list[SourceCandidate] = []
    for entry in root.findall("atom:entry", NS):
        title = (entry.findtext("atom:title", default="", namespaces=NS) or "").strip()
        if not title:
            continue
        summary = (entry.findtext("atom:summary", default="", namespaces=NS) or "").strip()
        id_url = (entry.findtext("atom:id", default="", namespaces=NS) or "").strip()
        arxiv_id = None
        m = _ARXIV_ID_RE.search(id_url)
        if m:
            arxiv_id = m.group(1)
        authors = [
            (a.findtext("atom:name", default="", namespaces=NS) or "").strip()
            for a in entry.findall("atom:author", NS)
        ]
        authors = [a for a in authors if a]
        published = entry.findtext("atom:published", default=None, namespaces=NS)
        published_at = None
        if published:
            try:
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                pass
        pdf_url = None
        for link in entry.findall("atom:link", NS):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        primary_cat = entry.find("arxiv:primary_category", NS)
        venue = primary_cat.get("term") if primary_cat is not None else "arXiv"

        candidates.append(
            SourceCandidate(
                title=re.sub(r"\s+", " ", title),
                authors=authors,
                venue=f"arXiv ({venue})" if venue else "arXiv",
                url=id_url,
                excerpt=re.sub(r"\s+", " ", summary),
                source_kind="arxiv",
                arxiv_id=arxiv_id,
                pdf_url=pdf_url,
                published_at=published_at,
            )
        )
    return candidates


class ArxivRadar:
    name = "arxiv"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        request_timeout: float = 30.0,
        sort_by: str = "relevance",
        max_retries: int = 2,
    ) -> None:
        self._client = client
        self._timeout = request_timeout
        self._sort_by = sort_by
        self._max_retries = max_retries

    async def scan(self, topic: str, *, limit: int = 5) -> list[SourceCandidate]:
        params = {
            "search_query": f"all:{topic}",
            "start": "0",
            "max_results": str(max(1, min(limit, 25))),
            "sortBy": self._sort_by,
            "sortOrder": "descending",
        }
        owns_client = False
        client = self._client
        if client is None:
            client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": "ENIAK/0.0.1 (mailto:opensource@eniak.org)"},
            )
            owns_client = True
        try:
            data = await self._fetch_with_backoff(client, params)
        finally:
            if owns_client:
                await client.aclose()
        if not data:
            return []
        results = _parse_atom(data)
        logger.info("arxiv.scan", extra={"topic": topic[:80], "results": len(results)})
        n = max(len(results), 1)
        return [
            SourceCandidate(**{**c.__dict__, "relevance": round(1.0 - (i / n), 4)})
            for i, c in enumerate(results)
        ]

    async def _fetch_with_backoff(
        self, client: httpx.AsyncClient, params: dict[str, str]
    ) -> bytes | None:
        # arXiv asks for <= 1 request / 3s; honour 429 with exponential backoff.
        import asyncio

        delay = 3.0
        for attempt in range(self._max_retries + 1):
            try:
                response = await client.get(ARXIV_API, params=params)
            except httpx.HTTPError as exc:
                logger.warning("arxiv.network_error", extra={"err": str(exc)[:120]})
                if attempt >= self._max_retries:
                    return None
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if response.status_code == 429:
                if attempt >= self._max_retries:
                    logger.warning("arxiv.rate_limit_persisted")
                    return None
                await asyncio.sleep(delay)
                delay *= 2
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning(
                    "arxiv.http_error",
                    extra={"status": response.status_code, "body": response.text[:120]},
                )
                return None
            return response.content
        return None
