"""Dry-run research loop.

Pipeline:
    topic
      -> mock radar scan
      -> evidence card extraction (Kimi via LiteLLM)
      -> claim + citation graph build
      -> chapter draft (Kimi via LiteLLM)
      -> markdown output persisted on the Chapter row

Persists Run / Source / EvidenceCard / Claim / Citation / Chapter / CostLedger.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

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

logger = logging.getLogger(__name__)


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


def _extract_json(text: str) -> dict:
    """Tolerate a model that wraps JSON in ```json ... ``` fences."""
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fenced:
        return json.loads(fenced.group(1))
    match = _JSON_RE.search(text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON object found in model output: {text[:200]!r}")


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
            started_at=datetime.now(timezone.utc),
            config_json={"pipeline": "dry-run-v1"},
        )
        self.session.add(run)
        await self.session.flush()
        return await self._drive(run, topic)

    async def _execute_existing(self, run: Run, topic: str) -> DryRunResult:
        """Drive the pipeline against a pre-persisted Run (used by the API's background task)."""
        run.status = RunStatus.running
        run.model = getattr(self.llm, "default_model", None)
        run.provider = getattr(self.llm, "provider", None)
        run.started_at = datetime.now(timezone.utc)
        await self.session.flush()
        return await self._drive(run, topic)

    async def _drive(self, run: Run, topic: str) -> DryRunResult:
        try:
            candidates = await self.radar.scan(topic)
            evidence_cards = await self._extract_evidence(run, topic, candidates)
            chapter, claims = await self._draft_chapter(run, topic, evidence_cards)
            run.status = RunStatus.succeeded
            run.finished_at = datetime.now(timezone.utc)
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
            run.finished_at = datetime.now(timezone.utc)
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
        prompt = CHAPTER_DRAFT_TEMPLATE.format(topic=topic, cards_block=cards_block)
        response = await self.llm.complete(
            prompt,
            system="You write clear, citation-faithful research prose.",
            temperature=0.4,
            max_tokens=1500,
        )
        self._record_cost(run, response, purpose="draft_chapter")
        body = response.content.strip()
        title = self._extract_title(body) or f"Notes on {topic[:60]}"

        chapter = Chapter(
            run_id=run.id,
            title=title,
            body_markdown=body,
            review_state=ReviewStateName.draft,
        )
        self.session.add(chapter)
        await self.session.flush()

        # Build Claim rows by harvesting cited card IDs from the body.
        claims = await self._materialise_claims(run, chapter, body, cards)
        return chapter, claims

    async def _materialise_claims(
        self,
        run: Run,
        chapter: Chapter,
        body: str,
        cards: list[EvidenceCard],
    ) -> list[Claim]:
        card_by_id = {c.id: c for c in cards}
        cited: dict[str, list[str]] = {}
        for match in re.finditer(r"\[card:([0-9a-fA-F\-]+)\]", body):
            card_id = match.group(1)
            if card_id in card_by_id:
                cited.setdefault(card_id, []).append(match.group(0))

        claims: list[Claim] = []
        if not cited:
            # Cite-all fallback so the citation invariant holds even if the
            # model forgot the inline syntax (still useful for the dry-run loop).
            for card_id in card_by_id:
                cited[card_id] = []

        for card_id, _locators in cited.items():
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
            citation = Citation(
                claim_id=claim.id,
                evidence_card_id=card.id,
                locator=f"chapter:{chapter.id}",
                relation="supports",
            )
            self.session.add(citation)
            claims.append(claim)
        await self.session.flush()
        return claims

    @staticmethod
    def _extract_title(body: str) -> str | None:
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return None

    def _record_cost(self, run: Run, response: LLMResponse, *, purpose: str) -> None:
        entry = CostLedger(
            run_id=run.id,
            model=response.model,
            provider=response.provider,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            cost_usd=response.cost_usd,
            purpose=purpose,
        )
        self.session.add(entry)
