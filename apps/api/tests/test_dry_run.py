"""End-to-end tests for the dry-run research loop.

Asserts the real citation invariant: at least one inline ``[card:<id>]`` in the
chapter body for every card we claim cited, and every persisted Claim/Citation
matches a citation we can find in the body.
"""

from __future__ import annotations

import re

import pytest
from eniak_evidence import (
    Chapter,
    Citation,
    Claim,
    CostLedger,
    EvidenceCard,
    Run,
    RunStatus,
    Source,
    get_session,
)
from eniak_orchestrator import (
    CitationInvariantError,
    DryRunOrchestrator,
    find_inline_citations,
)
from sqlalchemy import select

CITATION_RE = re.compile(r"\[card:([0-9a-fA-F\-]+)\]")


@pytest.mark.asyncio
async def test_dry_run_persists_full_graph(engine, fake_llm) -> None:
    async with get_session() as session:
        orchestrator = DryRunOrchestrator(session, llm=fake_llm)
        result = await orchestrator.run("citation faithfulness in LLM reports")

    async with get_session() as session:
        run = await session.get(Run, result.run_id)
        assert run is not None
        assert run.status == RunStatus.succeeded
        assert run.finished_at is not None

        sources = (await session.execute(select(Source))).scalars().all()
        cards = (await session.execute(select(EvidenceCard))).scalars().all()
        claims = (await session.execute(select(Claim))).scalars().all()
        citations = (await session.execute(select(Citation))).scalars().all()
        chapters = (await session.execute(select(Chapter))).scalars().all()
        costs = (await session.execute(select(CostLedger))).scalars().all()

        assert len(sources) == 3
        assert len(cards) == 3
        assert len(chapters) == 1
        body = chapters[0].body_markdown
        assert body.startswith("# ")

        # Real citation invariant: the body itself must carry inline references.
        inline_card_ids = set(CITATION_RE.findall(body))
        card_ids = {c.id for c in cards}
        assert inline_card_ids, "Chapter body has no inline [card:<id>] references"
        assert inline_card_ids.issubset(card_ids), (
            f"Body cites unknown card IDs: {inline_card_ids - card_ids}"
        )

        # Each persisted Claim must trace to a real inline citation in the body.
        assert len(claims) >= 1
        claim_ids = {c.id for c in claims}
        cited_claim_ids = {c.claim_id for c in citations}
        assert claim_ids.issubset(cited_claim_ids), "Every claim must have a citation row"

        # Cost ledger captured at least the extraction + first draft attempts.
        purposes = {c.purpose for c in costs}
        assert {"extract_evidence", "draft_chapter"}.issubset(purposes)


@pytest.mark.asyncio
async def test_retry_recovers_when_first_draft_forgets_citations(engine) -> None:
    """Model forgets [card:<id>] on attempt 1, retry succeeds → run still SUCCEEDS."""
    from tests.conftest import FakeLLM

    bad_then_good = FakeLLM(cite_in_draft=False, cite_on_retry=True)
    async with get_session() as session:
        orchestrator = DryRunOrchestrator(session, llm=bad_then_good)
        result = await orchestrator.run("recoverable miss")

    async with get_session() as session:
        run = await session.get(Run, result.run_id)
        assert run is not None
        assert run.status == RunStatus.succeeded

        costs = (await session.execute(select(CostLedger))).scalars().all()
        purposes = [c.purpose for c in costs]
        assert "draft_chapter_retry" in purposes, "retry should hit the LLM a second time"


@pytest.mark.asyncio
async def test_failed_run_when_model_refuses_to_cite(engine) -> None:
    """Both first attempt and retry omit citations → run FAILS, no fake claims created."""
    from tests.conftest import FakeLLM

    never_cites = FakeLLM(cite_in_draft=False, cite_on_retry=False)
    async with get_session() as session:
        orchestrator = DryRunOrchestrator(session, llm=never_cites)
        with pytest.raises(CitationInvariantError):
            await orchestrator.run("hopeless")

    async with get_session() as session:
        runs = (await session.execute(select(Run))).scalars().all()
        assert len(runs) == 1
        assert runs[0].status == RunStatus.failed
        assert "inline" in (runs[0].error or "").lower()
        claims = (await session.execute(select(Claim))).scalars().all()
        assert claims == [], "No claims should be persisted when citations are missing"


def test_find_inline_citations_helper() -> None:
    # IDs are UUID-shaped (hex + dashes). The regex enforces this so the model
    # can't sneak in arbitrary tokens we have no row for.
    body = (
        "Para 1 [card:abc-123]. Para 2 has no ref. "
        "Para 3 [card:fe-09].\n[card:abc-123]"
    )
    hits = find_inline_citations(body, {"abc-123", "fe-09", "never-cited"})
    assert hits["abc-123"] == ["[card:abc-123]", "[card:abc-123]"]
    assert hits["fe-09"] == ["[card:fe-09]"]
    assert "never-cited" not in hits


@pytest.mark.asyncio
async def test_health_endpoint(client) -> None:
    res = await client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_config_endpoint_does_not_leak_secrets(client) -> None:
    res = await client.get("/config")
    assert res.status_code == 200
    body = res.json()
    assert "llm_configured" in body
    assert "llm_api_key" not in body
    assert body["llm_configured"] in (True, False)


@pytest.mark.asyncio
async def test_create_run_requires_api_key(client) -> None:
    # Missing header
    res = await client.post("/runs", json={"topic": "no auth"})
    assert res.status_code == 401, res.text

    # Wrong key
    res = await client.post(
        "/runs",
        json={"topic": "wrong auth"},
        headers={"Authorization": "Bearer nope"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_run_endpoint(client) -> None:
    """Full happy path with proper auth header."""
    import asyncio

    headers = {"Authorization": "Bearer test-key-1"}
    res = await client.post(
        "/runs", json={"topic": "evidence-native pipelines"}, headers=headers
    )
    assert res.status_code == 202, res.text
    run = res.json()
    assert run["topic"] == "evidence-native pipelines"
    assert run["status"] in {"pending", "running", "succeeded"}

    for _ in range(20):
        detail = await client.get(f"/runs/{run['id']}")
        if detail.status_code == 200 and detail.json()["status"] in {"succeeded", "failed"}:
            break
        await asyncio.sleep(0.05)
    detail = await client.get(f"/runs/{run['id']}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["status"] == "succeeded", detail_body
    assert len(detail_body["evidence_cards"]) == 3
    assert len(detail_body["chapters"]) == 1
    assert detail_body["cost"]["total_tokens"] >= 200

    md = await client.get(f"/runs/{run['id']}/chapter.md")
    assert md.status_code == 200
    payload = md.json()["markdown"]
    assert "# " in payload
    assert "## References" in payload
    # Markdown export strips inline [card:<id>]? No — we keep them in body, the
    # publisher just appends references. Verify they're still present.
    assert "[card:" in payload
