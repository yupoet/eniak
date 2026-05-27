"""Pytest fixtures: in-memory SQLite + dry-run with a fake LLM."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from eniak_evidence import dispose_engine, init_engine
from eniak_evidence.db import Base, get_engine
from eniak_writer.llm import LLMResponse
from httpx import ASGITransport, AsyncClient


class FakeLLM:
    """Deterministic stand-in for the real LLM during tests.

    Toggle ``cite_in_draft`` to model a model that forgets to cite. The
    orchestrator's retry path then takes over.
    """

    default_model = "test/fake-llm"
    provider = "test"

    def __init__(self, *, cite_in_draft: bool = True, cite_on_retry: bool = True) -> None:
        self.calls: list[dict] = []
        self.cite_in_draft = cite_in_draft
        self.cite_on_retry = cite_on_retry
        self._draft_call = 0

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls.append({"prompt": prompt[:200], "system": system, "temperature": temperature})
        if "Return exactly one JSON object" in prompt:
            payload = {
                "summary": "The source argues that evidence-native pipelines reduce hallucination.",
                "quote": "Every claim must be anchored to a source.",
                "claims": ["Evidence-native pipelines reduce hallucination."],
            }
            content = json.dumps(payload)
        else:
            # Chapter draft path.
            self._draft_call += 1
            ids = re.findall(r"id=([0-9a-fA-F\-]+)", prompt)
            this_attempt_cites = (
                self.cite_in_draft if self._draft_call == 1 else self.cite_on_retry
            )
            if this_attempt_cites and ids:
                citations = " ".join(f"[card:{i}]" for i in ids)
                content = (
                    "# Test Chapter\n\n"
                    "Evidence-native research pipelines anchor every claim to a source. "
                    f"{citations}\n\n## Open questions\n\n- "
                    "How do we measure citation faithfulness at scale?\n"
                )
            else:
                # No inline citations.
                content = (
                    "# Test Chapter\n\n"
                    "Some prose without any inline references.\n\n"
                    "## Open questions\n\n- How would citations help?\n"
                )
        return LLMResponse(
            content=content,
            model=self.default_model,
            provider=self.provider,
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            cost_usd=0.0001,
            raw={},
        )


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[None]:
    """Fresh in-memory SQLite per test, schema created via metadata.create_all."""
    init_engine("sqlite+aiosqlite:///:memory:")
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield None
    finally:
        await dispose_engine()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@asynccontextmanager
async def _noop_lifespan(app):
    yield


@pytest_asyncio.fixture
async def client(engine, monkeypatch, fake_llm) -> AsyncIterator[AsyncClient]:
    """ASGI test client with the LLM monkey-patched to FakeLLM and an API key set."""
    from eniak_api.app import create_app
    from eniak_api.config import get_settings
    from eniak_api.routers import runs as runs_router

    # Fresh settings each test so monkeypatched env vars take effect.
    get_settings.cache_clear()
    monkeypatch.setenv("ENIAK_API_KEYS", "test-key-1,test-key-2")
    monkeypatch.setenv("ENIAK_ENV", "development")
    monkeypatch.setenv("ENIAK_RUNS_RATE_LIMIT", "100/minute")
    # Phase 3/4 features off in unit tests so we never hit the network.
    monkeypatch.setenv("ENIAK_FETCH_PDFS", "false")
    monkeypatch.setenv("ENIAK_DETECT_CONTRADICTIONS", "false")
    monkeypatch.setattr(runs_router, "_build_llm", lambda: fake_llm)
    monkeypatch.setattr(runs_router, "_runs_limiter", None)
    # Force the API router to use a Mock radar so we don't hit arxiv/openalex.
    from eniak_radar import MockRadar as _MockRadar

    monkeypatch.setattr(runs_router, "_build_radar", lambda: _MockRadar())

    app = create_app()
    app.router.lifespan_context = _noop_lifespan
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    get_settings.cache_clear()
