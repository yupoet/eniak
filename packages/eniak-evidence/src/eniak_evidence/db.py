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
    """Initialise the global async engine. Idempotent for the same URL.

    Adjusts driver kwargs per backend:
    - SQLite (aiosqlite) needs ``check_same_thread=False``.
    - asyncpg behind a transaction-mode pooler (Supabase / PgBouncer) must
      disable prepared-statement caching, otherwise reused connections see
      "prepared statement already exists" errors after the first request.
    """
    global _engine, _sessionmaker
    if _engine is not None:
        return _engine

    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {
        "echo": kwargs.pop("echo", False),
        "future": True,
    }

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif "+asyncpg" in database_url:
        # Required for any PgBouncer transaction-pooled endpoint.
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
        # Each container request gets a fresh checkout — keep the pool small
        # and recycle so we never starve the pooler's shared connection slots.
        engine_kwargs.setdefault("pool_size", 5)
        engine_kwargs.setdefault("max_overflow", 5)
        engine_kwargs.setdefault("pool_pre_ping", True)
        engine_kwargs.setdefault("pool_recycle", 1800)

    _engine = create_async_engine(
        database_url,
        connect_args=connect_args,
        **engine_kwargs,
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
