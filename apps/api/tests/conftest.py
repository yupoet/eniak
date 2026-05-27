"""Pytest fixtures: in-memory SQLite + dry-run with a fake LLM."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from eniak_evidence import dispose_engine, init_engine
from eniak_evidence.db import Base, get_engine
from eniak_writer.llm import LLMResponse


class FakeLLM:
    """Deterministic stand-in for Kimi during tests.

    Returns a JSON evidence card for the extraction step and a citation-faithful
    markdown chapter for the draft step.
    """

    default_model = "test/fake-llm"
    provider = "test"

    def __init__(self) -> None:
        self.calls: list[dict] = []

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
            # Chapter draft — extract the card IDs from the prompt and cite them.
            import re

            ids = re.findall(r"id=([0-9a-fA-F\-]+)", prompt)
            citations = " ".join(f"[card:{i}]" for i in ids) or "[card:unknown]"
            content = (
                "# Test Chapter\n\n"
                "Evidence-native research pipelines anchor every claim to a source. "
                f"{citations}\n\n## Open questions\n\n- How do we measure citation faithfulness at scale?\n"
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


@pytest_asyncio.fixture
async def client(engine, monkeypatch, fake_llm) -> AsyncIterator[AsyncClient]:
    """ASGI test client with the LLM monkey-patched to FakeLLM."""
    from eniak_api.app import create_app
    from eniak_api.routers import runs as runs_router

    monkeypatch.setattr(runs_router, "_build_llm", lambda: fake_llm)

    app = create_app()
    # Replace lifespan-initialised engine with our test engine.
    app.router.lifespan_context = _noop_lifespan
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


from contextlib import asynccontextmanager


@asynccontextmanager
async def _noop_lifespan(app):
    yield


# Silence "asyncio event loop is closed" noise from aiosqlite on teardown.
asyncio.get_event_loop_policy()
