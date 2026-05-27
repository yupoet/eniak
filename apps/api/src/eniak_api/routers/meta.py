"""Meta endpoints: health, version, config sanity check."""

from __future__ import annotations

from fastapi import APIRouter

from eniak_api.config import get_settings

router = APIRouter(tags=["meta"])


@router.get("/", summary="Service banner")
async def root() -> dict[str, str]:
    return {
        "service": "eniak-api",
        "version": "0.0.1",
        "docs": "/docs",
    }


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe — verifies DB connection")
async def readyz() -> dict[str, str]:
    from sqlalchemy import text

    from eniak_evidence.db import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/config", summary="Non-secret config snapshot")
async def config_snapshot() -> dict[str, object]:
    settings = get_settings()
    return {
        "env": settings.eniak_env,
        "default_model": settings.eniak_default_model,
        "llm_base_url": settings.llm_base_url,
        "llm_configured": bool(settings.llm_api_key),
        "cors_origins": settings.cors_origin_list,
    }
