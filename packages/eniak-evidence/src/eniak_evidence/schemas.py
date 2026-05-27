"""Pydantic schemas for API I/O.

Mirrors the ORM models but with the surface a frontend / external caller sees.
Source of truth for TypeScript codegen via `datamodel-code-generator` later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from eniak_evidence.models import ReviewStateName, RunStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- read schemas ---


class SourceRead(ORMModel):
    id: str
    title: str
    url: str | None
    doi: str | None
    arxiv_id: str | None
    authors: list[str] | None
    venue: str | None
    published_at: datetime | None
    retrieved_at: datetime
    source_kind: str


class EvidenceCardRead(ORMModel):
    id: str
    source_id: str
    run_id: str | None
    summary: str
    quote: str | None
    page: int | None
    section: str | None
    confidence: float | None
    review_state: ReviewStateName
    created_at: datetime


class ClaimRead(ORMModel):
    id: str
    statement: str
    polarity: str
    confidence: float | None
    chapter_id: str | None
    run_id: str | None
    created_at: datetime


class ChapterRead(ORMModel):
    id: str
    title: str
    body_markdown: str
    order_index: int
    review_state: ReviewStateName
    run_id: str | None
    book_id: str | None
    created_at: datetime
    updated_at: datetime


class CostSummary(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class RunRead(ORMModel):
    id: str
    topic: str
    status: RunStatus
    model: str | None
    provider: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class RunDetail(RunRead):
    evidence_cards: list[EvidenceCardRead] = Field(default_factory=list)
    chapters: list[ChapterRead] = Field(default_factory=list)
    cost: CostSummary = Field(default_factory=CostSummary)


class RunCreate(BaseModel):
    topic: str = Field(min_length=3, max_length=2000)
    config: dict[str, Any] | None = None


class ChapterUpdate(BaseModel):
    title: str | None = None
    body_markdown: str | None = None
    review_state: ReviewStateName | None = None
