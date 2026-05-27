"""Async SQLAlchemy engine + session factory.

We support both Postgres (production via Supabase) and SQLite (local dev).
Driver selection happens at engine creation time based on the URL scheme.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Declarative base for all ENIAK ORM models."""


def init_engine(database_url: str, **kwargs: Any) -> AsyncEngine:
    """Initialise the global async engine. Idempotent for the same URL."""
    global _engine, _sessionmaker
    if _engine is not None:
        return _engine
    # SQLite needs check_same_thread=False; the async driver handles it.
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    _engine = create_async_engine(
        database_url,
        echo=kwargs.pop("echo", False),
        future=True,
        connect_args=connect_args,
        **kwargs,
    )
    _sessionmaker = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Engine not initialised. Call init_engine() first.")
    return _engine


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a new session in a transaction. Commits on success, rolls back on error."""
    if _sessionmaker is None:
        raise RuntimeError("Engine not initialised. Call init_engine() first.")
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close the engine on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
