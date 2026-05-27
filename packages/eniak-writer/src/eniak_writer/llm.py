"""LiteLLM-based async LLM client with cost tracking.

Defaults to Moonshot Kimi (the user's primary provider). Switchable per-call.
Cost is reported back so the caller can persist it to CostLedger.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    """Container for a single LLM completion."""

    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    raw: dict[str, Any]


class LLMClient:
    """Thin async wrapper around litellm.acompletion.

    Default provider/model is read from env at construction. Each call can override.
    """

    def __init__(
        self,
        default_model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: str | None = None,
    ) -> None:
        self.default_model = (
            default_model or os.environ.get("ENIAK_DEFAULT_MODEL") or "qwen3.5-plus"
        )
        # We route via OpenAI-compatible base URLs (Aliyun DashScope, Kimi-Coding).
        # litellm "openai/<model>" path is the safest cross-vendor invocation.
        if "/" not in self.default_model:
            self.default_model = f"openai/{self.default_model}"
        self.provider = provider or self.default_model.split("/", 1)[0]
        self.api_key = (
            api_key
            or os.environ.get("LLM_API_KEY")
            or os.environ.get("KIMI_CODING_API_KEY")
            or os.environ.get("DASHSCOPE_API_KEY")
        )
        self.base_url = (
            base_url
            or os.environ.get("LLM_BASE_URL")
            or "https://coding.dashscope.aliyuncs.com/v1"
        )

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        try:
            import litellm
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "litellm is required for live LLM calls; install via `uv sync`"
            ) from exc

        # Quiet litellm's default verbosity unless ENIAK_LLM_DEBUG is set.
        if not os.environ.get("ENIAK_LLM_DEBUG"):
            litellm.suppress_debug_info = True

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        chosen_model = model or self.default_model
        if "/" not in chosen_model:
            chosen_model = f"openai/{chosen_model}"

        kwargs: dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": self.api_key,
            "api_base": self.base_url,
        }

        logger.info("llm.request", extra={"model": chosen_model})
        response = await litellm.acompletion(**kwargs)
        data = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        usage = data.get("usage") or {}
        content = data["choices"][0]["message"]["content"]
        cost = 0.0
        try:
            cost = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:  # noqa: BLE001
            cost = 0.0

        return LLMResponse(
            content=content,
            model=chosen_model,
            provider=chosen_model.split("/", 1)[0],
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            cost_usd=cost,
            raw=data,
        )
