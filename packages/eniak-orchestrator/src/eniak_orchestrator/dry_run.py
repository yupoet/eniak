"""Dry-run research loop.

Pipeline:
    topic
      -> mock radar scan
      -> evidence card extraction (LLM)
      -> chapter draft with inline [card:<id>] citations (LLM, retry once if missing)
      -> claim + citation graph built from the inline citations actually present
      -> markdown export off the Chapter row

The citation invariant is enforced for real: if the drafted body has no inline
[card:<id>] references after one retry with a stricter prompt, the run is
marked failed with a clear error. We never fabricate claims to make the schema
look populated.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from eniak_evidence.models import (
    Chapter,
    Citation,
    Claim,
    CostLedger,
    EvidenceCard,
    ReviewStateName,
    Run,
    RunStatus,
    Source,
)
from eniak_radar import MockRadar, SourceCandidate
from eniak_writer.llm import LLMClient, LLMResponse
from eniak_writer.prompts import CHAPTER_DRAFT_TEMPLATE, EVIDENCE_EXTRACTION_TEMPLATE
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CitationInvariantError(RuntimeError):
    """Raised when the chapter draft has no inline [card:<id>] citations
    even after a retry with a stricter prompt."""


@dataclass
class DryRunResult:
    run_id: str
    chapter_id: str
    evidence_card_ids: list[str]
    claim_ids: list[str]


class _LLM(Protocol):
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = ...,
        model: str | None = ...,
        temperature: float = ...,
        max_tokens: int = ...,
    ) -> LLMResponse: ...


_JSON_RE = re.compile(r"\{[\s\S]*\}")
_CITATION_RE = re.compile(r"\[card:([0-9a-fA-F\-]+)\]")


def _extract_json(text: str) -> dict:
    """Tolerate a model that wraps JSON in ```json ... ``` fences."""
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fenced:
        return json.loads(fenced.group(1))
    match = _JSON_RE.search(text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON object found in model output: {text[:200]!r}")


def find_inline_citations(body: str, valid_card_ids: set[str]) -> dict[str, list[str]]:
    """Return {card_id: [verbatim refs]} for every inline [card:<id>] in body
    that resolves to a known card.
    """
    hits: dict[str, list[str]] = {}
    for match in _CITATION_RE.finditer(body):
        card_id = match.group(1)
        if card_id in valid_card_ids:
            hits.setdefault(card_id, []).append(match.group(0))
    return hits


class DryRunOrchestrator:
    """Coordinates one dry-run from topic to chapter."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        llm: _LLM | None = None,
        radar: MockRadar | None = None,
    ) -> None:
        self.session = session
        self.llm = llm or LLMClient()
        self.radar = radar or MockRadar()

    async def run(self, topic: str) -> DryRunResult:
        run = Run(
            topic=topic,
            status=RunStatus.running,
            model=getattr(self.llm, "default_model", None),
            provider=getattr(self.llm, "provider", None),
            started_at=datetime.now(UTC),
            config_json={"pipeline": "dry-run-v1"},
        )
        self.session.add(run)
        await self.session.flush()
        return await self._drive(run, topic)

    async def execute_existing(self, run: Run, topic: str) -> DryRunResult:
        """Drive the pipeline against a pre-persisted Run (background worker entrypoint)."""
        run.status = RunStatus.running
        run.model = getattr(self.llm, "default_model", None)
        run.provider = getattr(self.llm, "provider", None)
        run.started_at = datetime.now(UTC)
        await self.session.flush()
        return await self._drive(run, topic)

    # Backwards-compatible alias for any callers that imported the old name.
    _execute_existing = execute_existing

    async def _drive(self, run: Run, topic: str) -> DryRunResult:
        try:
            candidates = await self.radar.scan(topic)
            evidence_cards = await self._extract_evidence(run, topic, candidates)
            chapter, claims = await self._draft_chapter(run, topic, evidence_cards)
            run.status = RunStatus.succeeded
            run.finished_at = datetime.now(UTC)
            run.output_json = {
                "chapter_id": chapter.id,
                "evidence_card_ids": [c.id for c in evidence_cards],
                "claim_ids": [c.id for c in claims],
            }
            await self.session.flush()
            return DryRunResult(
                run_id=run.id,
                chapter_id=chapter.id,
                evidence_card_ids=[c.id for c in evidence_cards],
                claim_ids=[c.id for c in claims],
            )
        except Exception as exc:
            run.status = RunStatus.failed
            run.error = f"{type(exc).__name__}: {exc}"
            run.finished_at = datetime.now(UTC)
            await self.session.flush()
            raise

    async def _extract_evidence(
        self,
        run: Run,
        topic: str,
        candidates: list[SourceCandidate],
    ) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        for candidate in candidates:
            source = Source(
                title=candidate.title,
                url=candidate.url,
                authors=candidate.authors,
                venue=candidate.venue,
                retrieved_at=candidate.retrieved_at,
                source_kind=candidate.source_kind,
            )
            self.session.add(source)
            await self.session.flush()

            prompt = EVIDENCE_EXTRACTION_TEMPLATE.format(
                topic=topic,
                source_title=candidate.title,
                authors=", ".join(candidate.authors),
                venue=candidate.venue,
                excerpt=candidate.excerpt,
            )
            response = await self.llm.complete(
                prompt,
                system="You produce only valid JSON.",
                temperature=0.1,
                max_tokens=512,
            )
            self._record_cost(run, response, purpose="extract_evidence")
            payload = _extract_json(response.content)

            card = EvidenceCard(
                source_id=source.id,
                run_id=run.id,
                summary=str(payload.get("summary", "")).strip(),
                quote=(str(payload.get("quote")) if payload.get("quote") else None),
                confidence=0.7,
                review_state=ReviewStateName.draft,
                metadata_json={"raw_claims": payload.get("claims", [])},
            )
            self.session.add(card)
            await self.session.flush()
            cards.append(card)
        return cards

    async def _draft_chapter(
        self,
        run: Run,
        topic: str,
        cards: list[EvidenceCard],
    ) -> tuple[Chapter, list[Claim]]:
        cards_block = "\n".join(
            f"- id={c.id}\n  summary: {c.summary}\n  quote: {c.quote or '(no quote)'}"
            for c in cards
        )
        valid_ids = {c.id for c in cards}

        body = await self._draft_with_citations(run, topic, cards_block, valid_ids)

        title = self._extract_title(body) or f"Notes on {topic[:60]}"
        chapter = Chapter(
            run_id=run.id,
            title=title,
            body_markdown=body,
            review_state=ReviewStateName.draft,
        )
        self.session.add(chapter)
        await self.session.flush()

        claims = await self._materialise_claims(run, chapter, body, cards)
        return chapter, claims

    async def _draft_with_citations(
        self,
        run: Run,
        topic: str,
        cards_block: str,
        valid_ids: set[str],
    ) -> str:
        """Ask the model to draft. If it forgot the inline [card:<id>] markers,
        retry once with a stricter prompt. Fail loud after the retry.
        """
        prompt = CHAPTER_DRAFT_TEMPLATE.format(topic=topic, cards_block=cards_block)
        response = await self.llm.complete(
            prompt,
            system="You write clear, citation-faithful research prose.",
            temperature=0.4,
            max_tokens=1500,
        )
        self._record_cost(run, response, purpose="draft_chapter")
        body = response.content.strip()
        hits = find_inline_citations(body, valid_ids)
        if hits:
            return body

        # Retry once with a stricter system prompt.
        logger.warning("draft.no_inline_citations.retrying", extra={"run_id": run.id})
        retry_prompt = (
            "Your previous response was rejected because it contained no inline "
            "citations of the form [card:<id>]. Rewrite the chapter so that EVERY "
            "factual paragraph carries at least one [card:<id>] from the list "
            "below. Do not invent IDs.\n\n"
        ) + prompt
        retry_response = await self.llm.complete(
            retry_prompt,
            system=(
                "Strict citation mode. Every factual sentence must end with one or "
                "more [card:<id>] references using ONLY the supplied IDs."
            ),
            temperature=0.2,
            max_tokens=1500,
        )
        self._record_cost(run, retry_response, purpose="draft_chapter_retry")
        body = retry_response.content.strip()
        if not find_inline_citations(body, valid_ids):
            raise CitationInvariantError(
                "Model produced no inline [card:<id>] references after one retry; "
                "refusing to fabricate citations."
            )
        return body

    async def _materialise_claims(
        self,
        run: Run,
        chapter: Chapter,
        body: str,
        cards: list[EvidenceCard],
    ) -> list[Claim]:
        card_by_id = {c.id: c for c in cards}
        cited = find_inline_citations(body, set(card_by_id))
        if not cited:
            # _draft_with_citations should have already raised; this is belt-and-braces.
            raise CitationInvariantError("Chapter body has no resolvable inline citations.")

        claims: list[Claim] = []
        for card_id, locators in cited.items():
            card = card_by_id[card_id]
            claim = Claim(
                run_id=run.id,
                chapter_id=chapter.id,
                statement=card.summary[:500],
                polarity="positive",
                confidence=card.confidence,
            )
            self.session.add(claim)
            await self.session.flush()
            self.session.add(
                Citation(
                    claim_id=claim.id,
                    evidence_card_id=card.id,
                    locator=f"chapter:{chapter.id}#{locators[0]}",
                    relation="supports",
                )
            )
            claims.append(claim)
        await self.session.flush()
        return claims

    @staticmethod
    def _extract_title(body: str) -> str | None:
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return None

    def _record_cost(self, run: Run, response: LLMResponse, *, purpose: str) -> None:
        self.session.add(
            CostLedger(
                run_id=run.id,
                model=response.model,
                provider=response.provider,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                cost_usd=response.cost_usd,
                purpose=purpose,
            )
        )
