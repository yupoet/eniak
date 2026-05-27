"""ORM models for the ENIAK evidence domain.

Design rules (locked in by review B3):
- Run captures prompt+model+seed+provider+cost for every generation.
- EvidenceCard always points to a Source (and optionally a Document/page).
- Claim always points to one or more EvidenceCards via Citation.
- ReviewState is a state machine on Chapter and on EvidenceCard.
- CostLedger entries roll up by Run and (optionally) by Book.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eniak_evidence.db import Base


def _uuid7_str() -> str:
    """UUID7-ish string; falls back to uuid4 if uuid7 isn't available."""
    try:
        from uuid_utils import uuid7

        return str(uuid7())
    except Exception:
        return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class ReviewStateName(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    published = "published"
    rejected = "rejected"


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7_str)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Provenance: Source / Document
# ---------------------------------------------------------------------------


class Source(IdMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048))
    doi: Mapped[str | None] = mapped_column(String(255), index=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(64), index=True)
    authors: Mapped[list[str] | None] = mapped_column(JSON)
    venue: Mapped[str | None] = mapped_column(String(512))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(32), default="unknown")
    dedup_key: Mapped[str | None] = mapped_column(String(255), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    documents: Mapped[list[Document]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    evidence_cards: Mapped[list[EvidenceCard]] = relationship(back_populates="source")


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    local_path: Mapped[str | None] = mapped_column(String(2048))
    mime_type: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer)
    text_excerpt: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    source: Mapped[Source] = relationship(back_populates="documents")


# ---------------------------------------------------------------------------
# Evidence: EvidenceCard / Claim / Citation / Contradiction
# ---------------------------------------------------------------------------


class EvidenceCard(IdMixin, TimestampMixin, Base):
    __tablename__ = "evidence_cards"

    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[float | None] = mapped_column(Float)
    review_state: Mapped[ReviewStateName] = mapped_column(
        Enum(ReviewStateName), default=ReviewStateName.draft, nullable=False
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    source: Mapped[Source] = relationship(back_populates="evidence_cards")
    run: Mapped[Run | None] = relationship(back_populates="evidence_cards")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="evidence_card", cascade="all, delete-orphan"
    )


class Claim(IdMixin, TimestampMixin, Base):
    __tablename__ = "claims"

    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    chapter_id: Mapped[str | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    polarity: Mapped[str] = mapped_column(String(16), default="positive")
    confidence: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    citations: Mapped[list[Citation]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    run: Mapped[Run | None] = relationship(back_populates="claims")
    chapter: Mapped[Chapter | None] = relationship(back_populates="claims")


class Citation(IdMixin, TimestampMixin, Base):
    __tablename__ = "citations"

    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_card_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locator: Mapped[str | None] = mapped_column(String(255))
    relation: Mapped[str] = mapped_column(String(32), default="supports")

    claim: Mapped[Claim] = relationship(back_populates="citations")
    evidence_card: Mapped[EvidenceCard] = relationship(back_populates="citations")


class Contradiction(IdMixin, TimestampMixin, Base):
    __tablename__ = "contradictions"

    claim_a_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    claim_b_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    severity: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Run / Prompt / Cost
# ---------------------------------------------------------------------------


class PromptTemplate(IdMixin, TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(32), default="staging")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Run(IdMixin, TimestampMixin, Base):
    __tablename__ = "runs"

    topic: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.pending, nullable=False
    )
    model: Mapped[str | None] = mapped_column(String(255))
    provider: Mapped[str | None] = mapped_column(String(64))
    seed: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    evidence_cards: Mapped[list[EvidenceCard]] = relationship(back_populates="run")
    claims: Mapped[list[Claim]] = relationship(back_populates="run")
    cost_entries: Mapped[list[CostLedger]] = relationship(back_populates="run")
    chapters: Mapped[list[Chapter]] = relationship(back_populates="run")


class CostLedger(IdMixin, TimestampMixin, Base):
    __tablename__ = "cost_ledger"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    purpose: Mapped[str | None] = mapped_column(String(64))

    run: Mapped[Run] = relationship(back_populates="cost_entries")


# ---------------------------------------------------------------------------
# Writing: Book / Chapter / Section
# ---------------------------------------------------------------------------


class Book(IdMixin, TimestampMixin, Base):
    __tablename__ = "books"

    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )


class Chapter(IdMixin, TimestampMixin, Base):
    __tablename__ = "chapters"

    book_id: Mapped[str | None] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    review_state: Mapped[ReviewStateName] = mapped_column(
        Enum(ReviewStateName), default=ReviewStateName.draft, nullable=False
    )

    book: Mapped[Book | None] = relationship(back_populates="chapters")
    run: Mapped[Run | None] = relationship(back_populates="chapters")
    claims: Mapped[list[Claim]] = relationship(back_populates="chapter")


# Backwards-friendly alias matching the brainstorm naming.
ReviewState = ReviewStateName
