"""Run-related endpoints: create a dry-run, list runs, get run detail."""

from __future__ import annotations

import logging

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from eniak_evidence import (
    Chapter,
    CostLedger,
    CostSummary,
    EvidenceCard,
    Run,
    RunCreate,
    RunDetail,
    RunRead,
    RunStatus,
    get_session,
)
from eniak_orchestrator import DryRunOrchestrator
from eniak_writer.llm import LLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


async def _execute_run(run_id: str, topic: str) -> None:
    """Background worker: drives the dry-run loop on an already-persisted Run row.

    Uses its own session so the request handler can return immediately. Failures
    are stamped onto the run.status / run.error fields so the UI can poll.
    """
    try:
        async with get_session() as session:
            run = await session.get(Run, run_id)
            if run is None:
                logger.error("background.run.missing", extra={"run_id": run_id})
                return
            orchestrator = DryRunOrchestrator(session, llm=_build_llm())
            # Orchestrator will create its OWN run if you call .run(topic) — we
            # already have one, so seed it and let the orchestrator extend it.
            await orchestrator._execute_existing(run, topic)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        logger.exception("background.run.failed", extra={"run_id": run_id})
        # Stamp the failure separately so it survives the rollback above.
        try:
            async with get_session() as session:
                run = await session.get(Run, run_id)
                if run is not None and run.status != RunStatus.failed:
                    run.status = RunStatus.failed
                    run.error = run.error or "background worker crashed"
                    run.finished_at = datetime.now(timezone.utc)
        except Exception:
            logger.exception("background.run.cleanup_failed", extra={"run_id": run_id})


@router.post("", response_model=RunRead, status_code=202, summary="Start a dry-run research loop")
async def create_run(payload: RunCreate, background: BackgroundTasks) -> Run:
    async with get_session() as session:
        run = Run(
            topic=payload.topic,
            status=RunStatus.pending,
            config_json={"pipeline": "dry-run-v1"},
        )
        session.add(run)
        await session.flush()
        run_id = run.id
        # Return a fresh copy after the session commits.
        await session.refresh(run)

    background.add_task(_execute_run, run_id, payload.topic)

    async with get_session() as session:
        out = await session.get(Run, run_id)
        if out is None:
            raise HTTPException(status_code=500, detail="Run vanished after enqueue")
        return out


@router.get("", response_model=list[RunRead], summary="List recent runs")
async def list_runs(limit: int = 25) -> list[Run]:
    async with get_session() as session:
        stmt = select(Run).order_by(Run.created_at.desc()).limit(min(limit, 100))
        result = await session.execute(stmt)
        return list(result.scalars().all())


@router.get("/{run_id}", response_model=RunDetail, summary="Run detail with evidence + chapters + cost")
async def get_run(run_id: str) -> RunDetail:
    async with get_session() as session:
        stmt = (
            select(Run)
            .where(Run.id == run_id)
            .options(
                selectinload(Run.evidence_cards),
                selectinload(Run.chapters),
            )
        )
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        cost_stmt = select(
            func.coalesce(func.sum(CostLedger.prompt_tokens), 0),
            func.coalesce(func.sum(CostLedger.completion_tokens), 0),
            func.coalesce(func.sum(CostLedger.total_tokens), 0),
            func.coalesce(func.sum(CostLedger.cost_usd), 0.0),
        ).where(CostLedger.run_id == run_id)
        prompt_tok, completion_tok, total_tok, cost_usd = (
            await session.execute(cost_stmt)
        ).one()
        cost = CostSummary(
            prompt_tokens=int(prompt_tok),
            completion_tokens=int(completion_tok),
            total_tokens=int(total_tok),
            cost_usd=float(cost_usd),
        )

        return RunDetail.model_validate(
            {
                **{c.key: getattr(run, c.key) for c in Run.__table__.columns},
                "evidence_cards": run.evidence_cards,
                "chapters": run.chapters,
                "cost": cost,
            }
        )


@router.get("/{run_id}/chapter.md", summary="Markdown export of the first chapter")
async def get_run_chapter_markdown(run_id: str) -> dict[str, str]:
    from eniak_publisher import MarkdownPublisher

    async with get_session() as session:
        stmt = (
            select(Chapter)
            .where(Chapter.run_id == run_id)
            .order_by(Chapter.order_index)
            .limit(1)
        )
        chapter = (await session.execute(stmt)).scalar_one_or_none()
        if chapter is None:
            raise HTTPException(status_code=404, detail="No chapter for this run")
        cards_stmt = (
            select(EvidenceCard)
            .where(EvidenceCard.run_id == run_id)
            .options(selectinload(EvidenceCard.source))
        )
        cards = list((await session.execute(cards_stmt)).scalars().all())
        sources_by_card = {c.id: c.source for c in cards if c.source is not None}
        payload = MarkdownPublisher().publish(chapter, cards, sources_by_card)
        return {"markdown": payload.render()}


def _build_llm() -> LLMClient:
    from eniak_api.config import get_settings

    s = get_settings()
    return LLMClient(
        default_model=s.eniak_default_model,
        api_key=s.llm_api_key,
        base_url=s.llm_base_url,
    )
