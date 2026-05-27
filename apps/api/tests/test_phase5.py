"""Tests for Phase 5: book builder, publishers, review state machine."""

from __future__ import annotations

import pytest
from eniak_evidence import (
    Book,
    Chapter,
    EvidenceCard,
    ReviewStateName,
    Run,
    RunStatus,
    Source,
    get_session,
)
from eniak_orchestrator import BookOrchestrator, DryRunOrchestrator
from eniak_publisher import FeishuPublisher, chapter_to_feishu_blocks
from eniak_radar import MockRadar

# -----------------------------------------------------------------------------
# Book orchestrator
# -----------------------------------------------------------------------------


class FakeLLMForBooks:
    """LLM that returns an outline for outline prompts and citation-faithful
    chapters for draft prompts."""

    default_model = "test/fake"
    provider = "test"

    def __init__(self, chapter_count: int = 2) -> None:
        self.chapter_count = chapter_count
        self._draft_calls: dict[str, int] = {}
        self.outline_calls = 0

    async def complete(  # noqa: PLR0913
        self,
        prompt: str,
        *,
        system=None,
        model=None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ):
        from eniak_writer.llm import LLMResponse

        if "Plan a book outline" in prompt:
            self.outline_calls += 1
            chapters = [
                {"title": f"Chapter {i + 1}", "themes": ["theme a", "theme b"]}
                for i in range(self.chapter_count)
            ]
            content = (
                '{"title": "Test Book", "subtitle": "Subtitle", '
                f'"chapters": {chapters!s}}}'.replace("'", '"')
            )
        elif "Return exactly one JSON object" in prompt:
            content = (
                '{"summary": "Sample summary.", "quote": "verbatim quote", '
                '"page": null, "section": null, "claims": ["c1"]}'
            )
        elif "Cards:" in prompt and "contradictions" in prompt:
            content = '{"contradictions": []}'
        else:
            # Chapter draft path. Always cite all card IDs.
            import re

            ids = re.findall(r"id=([0-9a-fA-F\-]+)", prompt)
            cites = " ".join(f"[card:{i}]" for i in ids) or "[card:none]"
            content = (
                "# Drafted Chapter\n\n"
                f"Body with citations. {cites}\n\n"
                "## Open questions\n\n- q?\n"
            )
        return LLMResponse(
            content=content,
            model=self.default_model,
            provider=self.provider,
            prompt_tokens=100,
            completion_tokens=60,
            total_tokens=160,
            cost_usd=0.0001,
            raw={},
        )


@pytest.mark.asyncio
async def test_book_orchestrator_creates_chapters(engine) -> None:
    fake = FakeLLMForBooks(chapter_count=2)

    def factory(session, *, llm=None):
        return DryRunOrchestrator(session, llm=llm, radar=MockRadar())

    async with get_session() as session:
        book_orch = BookOrchestrator(
            session, llm=fake, chapter_orchestrator_factory=factory
        )
        result = await book_orch.build("evidence-native research", chapter_count=2)

    assert result.book_id
    assert len(result.chapter_ids) == 2
    assert not result.failed_chapter_titles

    async with get_session() as session:
        book = await session.get(Book, result.book_id)
        assert book is not None
        assert book.status == "ready_for_review"
        assert book.title == "Test Book"


# -----------------------------------------------------------------------------
# Feishu publisher (dry-run)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feishu_dry_run_returns_block_json(engine) -> None:
    async with get_session() as session:
        source = Source(title="S1", authors=["A. B."], venue="ENIAK Lab", source_kind="mock")
        session.add(source)
        await session.flush()
        run = Run(topic="t", status=RunStatus.succeeded)
        session.add(run)
        await session.flush()
        card = EvidenceCard(
            source_id=source.id, run_id=run.id, summary="Sample summary.",
        )
        session.add(card)
        await session.flush()
        chapter = Chapter(
            title="Hello",
            run_id=run.id,
            body_markdown=(
                f"# Hello\n\nFirst paragraph cites [card:{card.id}].\n\n"
                "## Open questions\n\n- one\n"
            ),
            review_state=ReviewStateName.approved,
        )
        session.add(chapter)
        await session.flush()

        result = await FeishuPublisher().publish(
            chapter, [card], {card.id: source}, mode="dry_run"
        )

    assert result.mode == "dry_run"
    assert result.error is None
    assert result.external_id is None
    blocks = result.payload["blocks"]
    assert blocks, "must emit at least the heading block"
    # The first block should be the heading1.
    assert blocks[0]["block_type"] == 3
    # Inline [card:...] markers must be stripped before going to Feishu.
    para = next(b for b in blocks if b["block_type"] == 2)
    text = para["text"]["elements"][0]["text_run"]["content"]
    assert "[card:" not in text
    # References section + bullet present.
    assert any(b["block_type"] == 4 for b in blocks), "must include References heading"
    assert any(b["block_type"] == 12 for b in blocks), "must include reference bullets"


def test_feishu_block_builder_strips_citations() -> None:
    # Minimal in-memory fixture so the test doesn't need DB session.
    class Stub:
        pass

    chapter = Stub()
    chapter.title = "T"
    chapter.body_markdown = "# T\n\nClaim [card:abc-1] and [card:def-2].\n\n## Open\n\n- q\n"
    source = Stub()
    source.title = "src"
    source.authors = ["A"]
    source.venue = "V"
    source.url = "https://example.com/x"
    card = Stub()
    card.id = "abc-1"
    card.source = source
    blocks = chapter_to_feishu_blocks(chapter, [card], {card.id: source})
    body_block = next(b for b in blocks if b["block_type"] == 2)
    text = body_block["text"]["elements"][0]["text_run"]["content"]
    assert "[card:" not in text


# -----------------------------------------------------------------------------
# Review state machine endpoints
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_state_transitions(client) -> None:
    # First create a run via the API so a chapter exists.
    res = await client.post(
        "/runs",
        json={"topic": "review transitions"},
        headers={"Authorization": "Bearer test-key-1"},
    )
    assert res.status_code == 202
    run_id = res.json()["id"]
    # Wait for background task by polling.
    import asyncio

    for _ in range(40):
        d = await client.get(f"/runs/{run_id}")
        if d.json()["status"] == "succeeded":
            break
        await asyncio.sleep(0.05)
    detail = (await client.get(f"/runs/{run_id}")).json()
    assert detail["status"] == "succeeded"
    chapter_id = detail["chapters"][0]["id"]
    card_id = detail["evidence_cards"][0]["id"]

    # Legal: draft -> in_review
    r = await client.patch(
        f"/runs/{run_id}/cards/{card_id}",
        json={"review_state": "in_review"},
        headers={"Authorization": "Bearer test-key-1"},
    )
    assert r.status_code == 200
    assert r.json()["review_state"] == "in_review"

    # Illegal: in_review -> published (must go through approved first)
    r = await client.patch(
        f"/runs/{run_id}/cards/{card_id}",
        json={"review_state": "published"},
        headers={"Authorization": "Bearer test-key-1"},
    )
    assert r.status_code == 409

    # Legal chapter: draft -> in_review -> approved
    r = await client.patch(
        f"/chapters/{chapter_id}",
        json={"review_state": "in_review"},
        headers={"Authorization": "Bearer test-key-1"},
    )
    assert r.status_code == 200
    r = await client.patch(
        f"/chapters/{chapter_id}",
        json={"review_state": "approved"},
        headers={"Authorization": "Bearer test-key-1"},
    )
    assert r.status_code == 200
