"""PDF retrieval + text extraction (Phase 4).

Downloads a PDF over HTTPS, extracts per-page text, returns a dataclass.
Keeps memory bounded by streaming chunks into a BytesIO buffer that pypdf
can read from.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import httpx
from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractedPdf:
    pages: list[str]
    char_count: int
    page_count: int

    def joined(self) -> str:
        return "\n\n".join(f"[page {i + 1}]\n{p}" for i, p in enumerate(self.pages))


async def fetch_and_extract(
    pdf_url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 60.0,
    max_bytes: int = 25 * 1024 * 1024,
) -> ExtractedPdf | None:
    """Download a PDF and return its per-page text.

    Returns ``None`` on any failure (network, oversize, encrypted, parser error)
    so callers can fall back to the abstract excerpt without crashing the run.
    """
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "ENIAK/0.0.1 (mailto:opensource@eniak.org)"},
        )
    try:
        response = await client.get(pdf_url)
    except httpx.HTTPError as exc:
        logger.warning("pdf.network_error", extra={"url": pdf_url, "err": str(exc)[:120]})
        if owns_client:
            await client.aclose()
        return None

    try:
        if response.status_code != 200:
            logger.warning(
                "pdf.bad_status",
                extra={"url": pdf_url, "status": response.status_code},
            )
            return None
        body = response.content
        if len(body) > max_bytes:
            logger.warning(
                "pdf.too_large",
                extra={"url": pdf_url, "bytes": len(body), "max": max_bytes},
            )
            return None
        try:
            reader = PdfReader(io.BytesIO(body))
            if reader.is_encrypted:
                return None
            pages: list[str] = []
            for page in reader.pages:
                try:
                    pages.append((page.extract_text() or "").strip())
                except Exception:
                    pages.append("")
            joined_chars = sum(len(p) for p in pages)
            return ExtractedPdf(pages=pages, char_count=joined_chars, page_count=len(pages))
        except Exception as exc:
            logger.warning(
                "pdf.parse_error", extra={"url": pdf_url, "err": str(exc)[:120]}
            )
            return None
    finally:
        if owns_client:
            await client.aclose()
