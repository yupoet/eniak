"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from eniak_evidence import Base, dispose_engine, init_engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from eniak_api.config import Settings, get_settings
from eniak_api.routers import meta, runs

logger = structlog.get_logger(__name__)


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
            if settings.eniak_env == "production"
            else structlog.dev.ConsoleRenderer(),
        ],
        cache_logger_on_first_use=True,
    )


async def _ensure_schema_or_verify(database_url: str) -> None:
    """For SQLite: create tables (dev convenience).
    For Postgres: assume Alembic has migrated; just verify the schema is there.
    """
    from eniak_evidence.db import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        if database_url.startswith("sqlite"):
            await conn.run_sync(Base.metadata.create_all)
        # Pre-flight a single round-trip so a misconfigured DB fails the boot
        # rather than the first request.
        await conn.execute(text("SELECT 1"))


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    if "sqlite" in settings.database_url:
        sqlite_dir = os.path.dirname(settings.database_url.split("///")[-1])
        if sqlite_dir:
            os.makedirs(sqlite_dir, exist_ok=True)
    init_engine(settings.database_url)
    await _ensure_schema_or_verify(settings.database_url)
    logger.info(
        "eniak.api.boot",
        env=settings.eniak_env,
        db=_safe_db_url(settings.database_url),
    )
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("eniak.api.shutdown")


def _safe_db_url(url: str) -> str:
    if "@" in url:
        scheme, rest = url.split("://", 1)
        _, host = rest.split("@", 1)
        return f"{scheme}://***@{host}"
    return url


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings)

    app = FastAPI(
        title="ENIAK API",
        description="Evidence-Native Intelligent Academic Kernel",
        version="0.0.1",
        lifespan=_lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(meta.router)
    app.include_router(runs.router)

    return app


__all__ = ["create_app", "_safe_db_url"]


# Convenience for `uvicorn eniak_api.app:app`
app = create_app()
