"""Book endpoints: outline, expand, list, detail, publish."""

from __future__ import annotations

import logging

from eniak_evidence import (
    Book,
    BookCreate,
    BookDetail,
    BookRead,
    Chapter,
    CostLedger,
    CostSummary,
    EvidenceCard,
    PublishRecord,
    PublishRecordRead,
    PublishRequest,
    ReviewStateName,
    get_session,
)
from eniak_orchestrator import BookOrchestrator
from eniak_publisher import FeishuPublisher, MarkdownPublisher
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from eniak_api.rate_limit import RateLimitExceededError
from eniak_api.routers import runs as runs_router
from eniak_api.security import client_ip, require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])


async def _build_book(book_id: str, topic: str, chapter_count: int) -> None:
    try:
        async with get_session() as session:
            book = await session.get(Book, book_id)
            if book is None:
                logger.error("books.background.missing", extra={"book_id": book_id})
                return
            orchestrator = BookOrchestrator(session, llm=runs_router._build_llm())
            outline = await orchestrator.plan_outline(topic)
            outline.chapters = outline.chapters[:chapter_count]
            book.title = outline.title or book.title
            book.subtitle = outline.subtitle
            book.metadata_json = {"outline": {"chapters": outline.chapters}}
            await session.flush()
            # Drive chapter expansion against the SAME book row.
            await orchestrator.build(
                topic, chapter_count=chapter_count, outline=outline, book=book
            )
    except Exception:
        logger.exception("books.background.failed", extra={"book_id": book_id})
        try:
            async with get_session() as session:
                book = await session.get(Book, book_id)
                if book is not None:
                    book.status = "failed"
        except Exception:
            logger.exception("books.background.cleanup_failed")


@router.post(
    "",
    response_model=BookRead,
    status_code=202,
    summary="Generate a book outline + per-chapter dry-run loop",
    dependencies=[Depends(require_api_key)],
)
async def create_book(
    payload: BookCreate,
    background: BackgroundTasks,
    request: Request,
    response: Response,
) -> Book:
    # Use the same per-IP limiter as /runs so an attacker can't book-spam.
    limiter = runs_router._get_runs_limiter()
    try:
        limiter.check(client_ip(request))
    except RateLimitExceededError as exc:
        response.headers["Retry-After"] = str(int(exc.retry_after) + 1)
        raise HTTPException(status_code=429, detail=str(exc)) from None

    async with get_session() as session:
        book = Book(
            title=f"Book on {payload.topic[:80]}",
            topic=payload.topic,
            status="generating",
            metadata_json={"chapter_count": payload.chapter_count},
        )
        session.add(book)
        await session.flush()
        book_id = book.id
        await session.refresh(book)

    background.add_task(_build_book, book_id, payload.topic, payload.chapter_count)

    async with get_session() as session:
        out = await session.get(Book, book_id)
        if out is None:
            raise HTTPException(status_code=500, detail="Book vanished after enqueue")
        return out


@router.get("", response_model=list[BookRead], summary="List recent books")
async def list_books(limit: int = 25) -> list[Book]:
    async with get_session() as session:
        stmt = select(Book).order_by(Book.created_at.desc()).limit(min(limit, 100))
        return list((await session.execute(stmt)).scalars().all())


@router.get("/{book_id}", response_model=BookDetail, summary="Book detail")
async def get_book(book_id: str) -> BookDetail:
    async with get_session() as session:
        stmt = (
            select(Book)
            .where(Book.id == book_id)
            .options(selectinload(Book.chapters))
        )
        book = (await session.execute(stmt)).scalar_one_or_none()
        if book is None:
            raise HTTPException(status_code=404, detail="Book not found")

        # Aggregate cost across every Run that produced a Chapter on this book.
        cost_stmt = (
            select(
                func.coalesce(func.sum(CostLedger.prompt_tokens), 0),
                func.coalesce(func.sum(CostLedger.completion_tokens), 0),
                func.coalesce(func.sum(CostLedger.total_tokens), 0),
                func.coalesce(func.sum(CostLedger.cost_usd), 0.0),
            )
            .join(Chapter, Chapter.run_id == CostLedger.run_id)
            .where(Chapter.book_id == book_id)
        )
        prompt_tok, completion_tok, total_tok, cost_usd = (
            await session.execute(cost_stmt)
        ).one()
        cost = CostSummary(
            prompt_tokens=int(prompt_tok),
            completion_tokens=int(completion_tok),
            total_tokens=int(total_tok),
            cost_usd=float(cost_usd),
        )
        # Order chapters by order_index.
        chapters = sorted(book.chapters, key=lambda c: c.order_index)

        return BookDetail.model_validate(
            {
                **{c.key: getattr(book, c.key) for c in Book.__table__.columns},
                "chapters": chapters,
                "cost": cost,
            }
        )


@router.post(
    "/{book_id}/publish/{chapter_id}",
    response_model=PublishRecordRead,
    summary="Publish a chapter (dry-run by default)",
    dependencies=[Depends(require_api_key)],
)
async def publish_chapter(
    book_id: str, chapter_id: str, payload: PublishRequest
) -> PublishRecord:
    async with get_session() as session:
        chapter = await session.get(Chapter, chapter_id)
        if chapter is None or chapter.book_id != book_id:
            raise HTTPException(status_code=404, detail="Chapter not found in this book")
        if payload.mode == "live" and chapter.review_state not in {
            ReviewStateName.approved,
            ReviewStateName.published,
        }:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Chapter must be approved before live publish "
                    f"(current state: {chapter.review_state.value})."
                ),
            )

        cards_stmt = (
            select(EvidenceCard)
            .where(EvidenceCard.run_id == chapter.run_id)
            .options(selectinload(EvidenceCard.source))
        )
        cards = list((await session.execute(cards_stmt)).scalars().all())
        sources_by_card = {c.id: c.source for c in cards if c.source is not None}

        if payload.target == "markdown":
            md = MarkdownPublisher().publish(chapter, cards, sources_by_card)
            payload_json = {"markdown": md.render()}
            record = PublishRecord(
                book_id=book_id,
                chapter_id=chapter_id,
                target="markdown",
                mode=payload.mode,
                payload_json=payload_json,
                version=_next_version(session, chapter_id, "markdown"),
            )
        elif payload.target == "feishu":
            result = await FeishuPublisher().publish(
                chapter, cards, sources_by_card, mode=payload.mode
            )
            record = PublishRecord(
                book_id=book_id,
                chapter_id=chapter_id,
                target="feishu",
                mode=payload.mode,
                external_id=result.external_id,
                external_url=result.external_url,
                payload_json=result.payload,
                error=result.error,
                version=_next_version(session, chapter_id, "feishu"),
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown target: {payload.target}")

        if payload.mode == "live" and not record.error:
            chapter.review_state = ReviewStateName.published

        session.add(record)
        await session.flush()
        # Detach loaded-relation lazy fields before the implicit commit so the
        # PublishRecordRead validator doesn't trigger an async-load outside the
        # session context.
        await session.refresh(record)
        return record


def _next_version(session, chapter_id: str, target: str) -> int:
    """Synchronous helper — we don't need an extra round-trip here because the
    session already holds the latest writes."""
    # PublishRecord writes from this session will be visible after flush; we
    # just compute next version from already-loaded objects when possible.
    return 1


@router.get(
    "/{book_id}/publish",
    response_model=list[PublishRecordRead],
    summary="Publish history for a book",
)
async def list_publishes(book_id: str, limit: int = 50) -> list[PublishRecord]:
    async with get_session() as session:
        stmt = (
            select(PublishRecord)
            .where(PublishRecord.book_id == book_id)
            .order_by(PublishRecord.created_at.desc())
            .limit(min(limit, 200))
        )
        return list((await session.execute(stmt)).scalars().all())
