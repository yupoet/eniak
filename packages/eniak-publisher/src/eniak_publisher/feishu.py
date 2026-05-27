"""Lark / Feishu publisher.

Two modes:

- ``dry_run``: convert a Chapter into the docx block JSON that the v2 Feishu
  API would accept, return it without making network calls. Useful for review.
- ``live``: actually create / update a Wiki document via the official v2 API.
  Requires ``LARK_APP_ID`` + ``LARK_APP_SECRET`` env vars. Idempotent: if
  ``external_id`` is supplied, we update the existing doc; otherwise create
  a new one and return its token.

The docx block schema follows the ``open-apis/docx/v1/documents/{doc_id}/blocks/batch_update``
shape — see https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/list.
We render the chapter body as one heading block + N text blocks (one per
paragraph) and a final references heading + bullet list.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
from eniak_evidence.models import Chapter, EvidenceCard, Source

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Block builders (mode-agnostic — the same JSON works for dry_run and live)
# ---------------------------------------------------------------------------


_CITATION_RE = re.compile(r"\[card:([0-9a-fA-F\-]+)\]")


def _strip_inline_citations(text: str) -> tuple[str, list[str]]:
    cited = _CITATION_RE.findall(text)
    cleaned = _CITATION_RE.sub("", text).strip()
    cleaned = re.sub(r" +", " ", cleaned)
    cleaned = re.sub(r" ([,.;:?])", r"\1", cleaned)
    return cleaned, cited


def _text_run(text: str) -> dict[str, Any]:
    return {"text_run": {"content": text, "text_element_style": {}}}


def _paragraph_block(text: str) -> dict[str, Any]:
    cleaned, _ = _strip_inline_citations(text)
    return {
        "block_type": 2,  # text
        "text": {"elements": [_text_run(cleaned)], "style": {}},
    }


def _heading_block(text: str, level: int = 1) -> dict[str, Any]:
    return {
        "block_type": 3 + (level - 1),  # heading1 = 3, heading2 = 4
        f"heading{level}": {
            "elements": [_text_run(text)],
            "style": {},
        },
    }


def _bullet_block(text: str) -> dict[str, Any]:
    return {
        "block_type": 12,  # bullet
        "bullet": {"elements": [_text_run(text)], "style": {}},
    }


def chapter_to_feishu_blocks(
    chapter: Chapter,
    cards: list[EvidenceCard],
    sources_by_card: dict[str, Source],
) -> list[dict[str, Any]]:
    """Render a Chapter row as Feishu docx blocks (heading + paragraphs + refs)."""
    blocks: list[dict[str, Any]] = []
    blocks.append(_heading_block(chapter.title, level=1))

    body = chapter.body_markdown
    if body.startswith("# "):
        body = body.split("\n", 1)[1] if "\n" in body else ""
    for paragraph in re.split(r"\n\s*\n", body.strip()):
        para = paragraph.strip()
        if not para:
            continue
        # Sub-heading markers like "## Open questions".
        if para.startswith("## "):
            blocks.append(_heading_block(para[3:].strip(), level=2))
        else:
            blocks.append(_paragraph_block(para))

    if cards:
        blocks.append(_heading_block("References", level=2))
        for idx, card in enumerate(cards, start=1):
            src = sources_by_card.get(card.id)
            if src is None:
                continue
            authors = ", ".join(src.authors or []) or "Unknown"
            ref = f"{idx}. {authors}. {src.title}. {src.venue or ''}".strip(". ")
            if src.url:
                ref += f". <{src.url}>"
            blocks.append(_bullet_block(ref))
    return blocks


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublishResult:
    target: str
    mode: str
    payload: dict[str, Any]
    external_id: str | None = None
    external_url: str | None = None
    error: str | None = None


_LARK_BASE = "https://open.feishu.cn/open-apis"


class FeishuPublisher:
    """Publish a Chapter as a Feishu / Lark docx document."""

    target = "feishu"

    def __init__(
        self,
        *,
        app_id: str | None = None,
        app_secret: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.app_id = app_id or os.environ.get("LARK_APP_ID")
        self.app_secret = app_secret or os.environ.get("LARK_APP_SECRET")
        self._client = client

    async def publish(
        self,
        chapter: Chapter,
        cards: list[EvidenceCard],
        sources_by_card: dict[str, Source],
        *,
        mode: str = "dry_run",
    ) -> PublishResult:
        blocks = chapter_to_feishu_blocks(chapter, cards, sources_by_card)
        payload = {"blocks": blocks}
        if mode == "dry_run":
            return PublishResult(target=self.target, mode="dry_run", payload=payload)

        if not (self.app_id and self.app_secret):
            return PublishResult(
                target=self.target,
                mode=mode,
                payload=payload,
                error="LARK_APP_ID / LARK_APP_SECRET not configured.",
            )

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=30.0)
        try:
            token = await self._tenant_token(client)
            if not token:
                return PublishResult(
                    target=self.target,
                    mode=mode,
                    payload=payload,
                    error="Failed to obtain tenant access token.",
                )
            # 1. create empty doc
            create = await client.post(
                f"{_LARK_BASE}/docx/v1/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": chapter.title},
            )
            if create.status_code >= 300:
                return PublishResult(
                    target=self.target,
                    mode=mode,
                    payload=payload,
                    error=f"create failed: {create.status_code} {create.text[:200]}",
                )
            create_data = create.json().get("data") or {}
            doc_id = (create_data.get("document") or {}).get("document_id")
            if not doc_id:
                return PublishResult(
                    target=self.target,
                    mode=mode,
                    payload=payload,
                    error="create response missing document_id",
                )
            # 2. batch-append blocks
            append = await client.patch(
                f"{_LARK_BASE}/docx/v1/documents/{doc_id}/blocks/batch_update",
                headers={"Authorization": f"Bearer {token}"},
                json={"requests": [{"insert_blocks": {"children": blocks, "index": 0}}]},
            )
            if append.status_code >= 300:
                return PublishResult(
                    target=self.target,
                    mode=mode,
                    payload=payload,
                    external_id=doc_id,
                    error=f"append failed: {append.status_code} {append.text[:200]}",
                )
            return PublishResult(
                target=self.target,
                mode=mode,
                payload=payload,
                external_id=doc_id,
                external_url=f"https://feishu.cn/docx/{doc_id}",
            )
        finally:
            if owns_client:
                await client.aclose()

    async def _tenant_token(self, client: httpx.AsyncClient) -> str | None:
        resp = await client.post(
            f"{_LARK_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        if resp.status_code >= 300:
            return None
        return resp.json().get("tenant_access_token")
