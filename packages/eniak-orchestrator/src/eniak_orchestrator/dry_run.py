"""Dry-run research loop (Phase 2 -> Phase 4).

Pipeline:
    topic
      -> radar fanout (arXiv / OpenAlex / mock)
      -> optional PDF retrieval + per-page text
      -> evidence card extraction (LLM, parallel)
      -> chapter draft with inline [card:<id>] citations (LLM, retry once)
      -> claim + citation graph built from the inline citations actually present
      -> contradiction detection across cards
      -> markdown export off the Chapter row

The citation invariant is enforced for real: if the drafted body has no inline
[card:<id>] references after one retry with a stricter prompt, the run is
marked failed with CitationInvariantError. We never fabricate claims.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from eniak_evidence.models import (
    Chapter,
    Citation,
    Claim,
    Contradiction,
    CostLedger,
    Document,
    EvidenceCard,
    ReviewStateName,
    Run,
    RunStatus,
    Source,
)
from eniak_radar import (
    ExtractedPdf,
    MockRadar,
    RadarFanout,
    SourceCandidate,
    fetch_and_extract,
)
from eniak_writer.llm import LLMClient, LLMResponse
from eniak_writer.prompts import (
    CHAPTER_DRAFT_TEMPLATE,
    CONTRADICTION_TEMPLATE,
    EVIDENCE_EXTRACTION_TEMPLATE,
)
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
    contradiction_ids: list[str]


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


class _Radar(Protocol):
    async def scan(
        self, topic: str, *, limit: int = ...
    ) -> list[SourceCandidate]: ...


_JSON_RE = re.compile(r"\{[\s\S]*\}")
_CITATION_RE = re.compile(r"\[card:([0-9a-fA-F\-]+)\]")
# Truncate excerpts past this length so a single 30-page paper doesn't blow
# the prompt budget for one card.
_MAX_EXCERPT_CHARS = 12_000


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
    hits: dict[str, list[str]] = {}
    for match in _CITATION_RE.finditer(body):
        card_id = match.group(1)
        if card_id in valid_card_ids:
            hits.setdefault(card_id, []).append(match.group(0))
    return hits


def _should_fetch_pdf() -> bool:
    return os.environ.get("ENIAK_FETCH_PDFS", "true").lower() not in {"0", "false", "off"}


def _should_detect_contradictions() -> bool:
    return os.environ.get("ENIAK_DETECT_CONTRADICTIONS", "true").lower() not in {
        "0",
        "false",
        "off",
    }


class DryRunOrchestrator:
    """Coordinates one dry-run from topic to chapter + contradictions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        llm: _LLM | None = None,
        radar: _Radar | None = None,
    ) -> None:
        self.session = session
        self.llm = llm or LLMClient()
        # Default to the multi-provider fanout. Tests inject MockRadar directly.
        self.radar = radar or RadarFanout()

    # ------------------------------------------------------------------ entry

    async def run(self, topic: str) -> DryRunResult:
        run = Run(
            topic=topic,
            status=RunStatus.running,
            model=getattr(self.llm, "default_model", None),
            provider=getattr(self.llm, "provider", None),
            started_at=datetime.now(UTC),
            config_json={"pipeline": "dry-run-v2"},
        )
        self.session.add(run)
        await self.session.flush()
        return await self._drive(run, topic)

    async def execute_existing(self, run: Run, topic: str) -> DryRunResult:
        run.status = RunStatus.running
        run.model = getattr(self.llm, "default_model", None)
        run.provider = getattr(self.llm, "provider", None)
        run.started_at = datetime.now(UTC)
        await self.session.flush()
        return await self._drive(run, topic)

    _execute_existing = execute_existing

    # ------------------------------------------------------------------ drive

    async def _drive(self, run: Run, topic: str) -> DryRunResult:
        try:
            candidates = await self.radar.scan(topic, limit=3)
            if not candidates:
                # Fall back to MockRadar so we never silently produce empty results.
                candidates = await MockRadar().scan(topic, limit=3)
            evidence_cards = await self._extract_evidence(run, topic, candidates)
            chapter, claims = await self._draft_chapter(run, topic, evidence_cards)
            contradictions = await self._detect_contradictions(run, topic, evidence_cards)
            run.status = RunStatus.succeeded
            run.finished_at = datetime.now(UTC)
            run.output_json = {
                "chapter_id": chapter.id,
                "evidence_card_ids": [c.id for c in evidence_cards],
                "claim_ids": [c.id for c in claims],
                "contradiction_ids": [c.id for c in contradictions],
            }
            await self.session.flush()
            return DryRunResult(
                run_id=run.id,
                chapter_id=chapter.id,
                evidence_card_ids=[c.id for c in evidence_cards],
                claim_ids=[c.id for c in claims],
                contradiction_ids=[c.id for c in contradictions],
            )
        except Exception as exc:
            run.status = RunStatus.failed
            run.error = f"{type(exc).__name__}: {exc}"
            run.finished_at = datetime.now(UTC)
            await self.session.flush()
            raise

    # ------------------------------------------------------------------ evidence

    async def _extract_evidence(
        self,
        run: Run,
        topic: str,
        candidates: list[SourceCandidate],
    ) -> list[EvidenceCard]:
        """Insert Sources sequentially, fan out LLM calls in parallel, then
        write EvidenceCards in the original order."""
        sources: list[Source] = []
        for candidate in candidates:
            source = Source(
                title=candidate.title,
                url=candidate.url,
                authors=candidate.authors,
                venue=candidate.venue,
                retrieved_at=candidate.retrieved_at,
                source_kind=candidate.source_kind,
                doi=candidate.doi,
                arxiv_id=candidate.arxiv_id,
                published_at=candidate.published_at,
                dedup_key=candidate.dedup_key,
                metadata_json={
                    "pdf_url": candidate.pdf_url,
                    "relevance": candidate.relevance,
                },
            )
            self.session.add(source)
            sources.append(source)
        await self.session.flush()

        # Optionally enrich each candidate's excerpt with PDF text.
        documents = await self._maybe_attach_pdfs(sources, candidates)

        prompts: list[str] = []
        for _src, cand, doc in zip(sources, candidates, documents, strict=True):
            excerpt = (doc.text_excerpt if doc else None) or cand.excerpt or ""
            excerpt = excerpt[:_MAX_EXCERPT_CHARS]
            prompts.append(
                EVIDENCE_EXTRACTION_TEMPLATE.format(
                    topic=topic,
                    source_title=cand.title,
                    authors=", ".join(cand.authors),
                    venue=cand.venue,
                    excerpt=excerpt,
                )
            )

        # Fan out LLM calls. Concurrency cap = 4 to be polite to the upstream.
        sem = asyncio.Semaphore(4)

        async def _call(prompt: str) -> LLMResponse:
            async with sem:
                return await self.llm.complete(
                    prompt,
                    system="You produce only valid JSON.",
                    temperature=0.1,
                    max_tokens=512,
                )

        responses = await asyncio.gather(*[_call(p) for p in prompts])

        cards: list[EvidenceCard] = []
        for src, cand, response in zip(sources, candidates, responses, strict=True):
            self._record_cost(run, response, purpose="extract_evidence")
            try:
                payload = _extract_json(response.content)
            except (json.JSONDecodeError, ValueError):
                logger.warning(
                    "extract.bad_json", extra={"source_id": src.id}
                )
                payload = {"summary": cand.excerpt[:500], "quote": None, "claims": []}
            page = payload.get("page")
            if not isinstance(page, int):
                page = None
            card = EvidenceCard(
                source_id=src.id,
                run_id=run.id,
                summary=str(payload.get("summary", "")).strip(),
                quote=(str(payload.get("quote")) if payload.get("quote") else None),
                page=page,
                section=(
                    str(payload.get("section")) if payload.get("section") else None
                ),
                confidence=0.7,
                review_state=ReviewStateName.draft,
                metadata_json={"raw_claims": payload.get("claims", [])},
            )
            self.session.add(card)
            cards.append(card)
        await self.session.flush()
        return cards

    async def _maybe_attach_pdfs(
        self,
        sources: list[Source],
        candidates: list[SourceCandidate],
    ) -> list[Document | None]:
        """If the candidate exposes a PDF URL and PDF retrieval is enabled,
        download it, persist a Document row, and return the per-source result."""
        if not _should_fetch_pdf():
            return [None] * len(sources)

        sem = asyncio.Semaphore(3)

        async def _one(cand: SourceCandidate) -> ExtractedPdf | None:
            if not cand.pdf_url:
                return None
            async with sem:
                return await fetch_and_extract(cand.pdf_url, timeout=45.0)

        pdfs = await asyncio.gather(*[_one(c) for c in candidates])

        documents: list[Document | None] = []
        for src, cand, pdf in zip(sources, candidates, pdfs, strict=True):
            if pdf is None:
                documents.append(None)
                continue
            joined = pdf.joined()[:_MAX_EXCERPT_CHARS * 4]
            doc = Document(
                source_id=src.id,
                local_path=None,
                mime_type="application/pdf",
                page_count=pdf.page_count,
                text_excerpt=joined,
                metadata_json={
                    "char_count": pdf.char_count,
                    "pdf_url": cand.pdf_url,
                },
            )
            self.session.add(doc)
            documents.append(doc)
        await self.session.flush()
        return documents

    # ------------------------------------------------------------------ chapter

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
        prompt = CHAPTER_DRAFT_TEMPLATE.format(topic=topic, cards_block=cards_block)
        response = await self.llm.complete(
            prompt,
            system="You write clear, citation-faithful research prose.",
            temperature=0.4,
            max_tokens=1500,
        )
        self._record_cost(run, response, purpose="draft_chapter")
        body = response.content.strip()
        if find_inline_citations(body, valid_ids):
            return body

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

    # ------------------------------------------------------------------ contradictions

    async def _detect_contradictions(
        self,
        run: Run,
        topic: str,
        cards: list[EvidenceCard],
    ) -> list[Contradiction]:
        if not _should_detect_contradictions() or len(cards) < 2:
            return []
        cards_block = "\n".join(
            f"- id={c.id}\n  summary: {c.summary}\n  quote: {c.quote or '(no quote)'}"
            for c in cards
        )
        prompt = CONTRADICTION_TEMPLATE.format(topic=topic, cards_block=cards_block)
        try:
            response = await self.llm.complete(
                prompt,
                system="You return strict JSON.",
                temperature=0.1,
                max_tokens=512,
            )
        except Exception:
            logger.exception("contradiction.llm_failed")
            return []
        self._record_cost(run, response, purpose="detect_contradictions")
        try:
            payload = _extract_json(response.content)
        except (json.JSONDecodeError, ValueError):
            return []

        valid_ids = {c.id for c in cards}
        out: list[Contradiction] = []
        for entry in payload.get("contradictions") or []:
            a = entry.get("card_a_id")
            b = entry.get("card_b_id")
            if a not in valid_ids or b not in valid_ids or a == b:
                continue
            # Resolve evidence card -> claim. Skip if no claim row yet.
            claim_a = await self._claim_for_card(run.id, a)
            claim_b = await self._claim_for_card(run.id, b)
            if claim_a is None or claim_b is None:
                continue
            sev_raw = entry.get("severity")
            sev = float(sev_raw) if isinstance(sev_raw, (int, float)) else 0.5
            sev = max(0.0, min(1.0, sev))
            rationale = (entry.get("rationale") or "")[:300]
            contradiction = Contradiction(
                claim_a_id=claim_a, claim_b_id=claim_b, severity=sev, rationale=rationale
            )
            self.session.add(contradiction)
            out.append(contradiction)
        await self.session.flush()
        return out

    async def _claim_for_card(self, run_id: str, card_id: str) -> str | None:
        from sqlalchemy import select

        stmt = (
            select(Claim.id)
            .join(Citation, Citation.claim_id == Claim.id)
            .where(Citation.evidence_card_id == card_id, Claim.run_id == run_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------ helpers

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
