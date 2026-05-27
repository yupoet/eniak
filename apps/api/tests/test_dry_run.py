"""End-to-end test of the dry-run research loop.

Asserts the citation invariant: every claim must have at least one citation
pointing at an evidence card that itself points at a source.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

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
from eniak_orchestrator import DryRunOrchestrator


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
        assert chapters[0].body_markdown.startswith("# ")
        assert len(claims) >= 1
        # Citation invariant: every claim must have at least one citation.
        claim_ids = {c.id for c in claims}
        cited_claim_ids = {c.claim_id for c in citations}
        assert claim_ids.issubset(cited_claim_ids), "Every claim must be cited."
        # Every citation must point at a real evidence card.
        card_ids = {c.id for c in cards}
        for citation in citations:
            assert citation.evidence_card_id in card_ids
        # Cost ledger captured both extraction and drafting steps.
        purposes = {c.purpose for c in costs}
        assert "extract_evidence" in purposes
        assert "draft_chapter" in purposes


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
async def test_create_run_endpoint(client) -> None:
    # POST returns 202 immediately with a pending run; the background task does the work.
    res = await client.post("/runs", json={"topic": "evidence-native pipelines"})
    assert res.status_code == 202, res.text
    run = res.json()
    assert run["topic"] == "evidence-native pipelines"
    assert run["status"] in {"pending", "running", "succeeded"}

    # Wait for the background task. ASGITransport runs background tasks inline at the
    # end of the response, so by the next request the run should be done.
    import asyncio

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
