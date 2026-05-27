"""Review state machine endpoints.

Routes:
- PATCH /runs/{run_id}/cards/{card_id}  — accept/reject/annotate an EvidenceCard
- PATCH /chapters/{chapter_id}          — move a Chapter through the state machine

States: draft -> in_review -> approved -> published (terminal)
                                 \\-> rejected (terminal)
"""

from __future__ import annotations

from eniak_evidence import (
    Chapter,
    ChapterRead,
    ChapterUpdate,
    EvidenceCard,
    EvidenceCardRead,
    EvidenceCardUpdate,
    ReviewStateName,
    get_session,
)
from fastapi import APIRouter, Depends, HTTPException

from eniak_api.security import require_api_key

router = APIRouter(tags=["review"])


_ALLOWED_TRANSITIONS: dict[ReviewStateName, set[ReviewStateName]] = {
    ReviewStateName.draft: {ReviewStateName.in_review, ReviewStateName.rejected},
    ReviewStateName.in_review: {
        ReviewStateName.approved,
        ReviewStateName.rejected,
        ReviewStateName.draft,
    },
    ReviewStateName.approved: {ReviewStateName.published, ReviewStateName.in_review},
    ReviewStateName.published: set(),  # terminal
    ReviewStateName.rejected: {ReviewStateName.draft},
}


def _transition(current: ReviewStateName, target: ReviewStateName) -> None:
    if current == target:
        return
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Illegal state transition: {current.value} → {target.value}",
        )


@router.patch(
    "/runs/{run_id}/cards/{card_id}",
    response_model=EvidenceCardRead,
    dependencies=[Depends(require_api_key)],
    summary="Move an evidence card through the review state machine",
)
async def update_card(
    run_id: str,
    card_id: str,
    payload: EvidenceCardUpdate,
) -> EvidenceCard:
    async with get_session() as session:
        card = await session.get(EvidenceCard, card_id)
        if card is None or card.run_id != run_id:
            raise HTTPException(status_code=404, detail="Evidence card not found")
        if payload.review_state is not None:
            _transition(card.review_state, payload.review_state)
            card.review_state = payload.review_state
        if payload.annotation is not None:
            meta = dict(card.metadata_json or {})
            meta["annotation"] = payload.annotation
            card.metadata_json = meta
        await session.flush()
        await session.refresh(card)
        return card


@router.patch(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    dependencies=[Depends(require_api_key)],
    summary="Update / advance a chapter (title, body, review state)",
)
async def update_chapter(chapter_id: str, payload: ChapterUpdate) -> Chapter:
    async with get_session() as session:
        chapter = await session.get(Chapter, chapter_id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="Chapter not found")
        if payload.review_state is not None:
            _transition(chapter.review_state, payload.review_state)
            chapter.review_state = payload.review_state
        if payload.title is not None:
            chapter.title = payload.title.strip()[:1024]
        if payload.body_markdown is not None:
            chapter.body_markdown = payload.body_markdown
        await session.flush()
        await session.refresh(chapter)
        return chapter
