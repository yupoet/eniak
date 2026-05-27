"""Book builder orchestrator.

Pipeline:
    topic
      -> LLM generates Book outline (3-5 chapters with themes)
      -> For each chapter (sequentially, to avoid stampeding the LLM and Radar):
           - Build a chapter-specific sub-topic (book topic + chapter theme)
           - Run DryRunOrchestrator
           - Persist the Chapter row under the Book with order_index
      -> Mark Book status = ready_for_review

We intentionally serialise chapters: arXiv has request rate limits and the
LLM is the bottleneck. Parallel chapter generation didn't pay off in
back-of-envelope testing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from eniak_evidence.models import (
    Book,
    Chapter,
    Run,
    RunStatus,
)
from eniak_writer.llm import LLMClient
from eniak_writer.prompts import BOOK_OUTLINE_TEMPLATE
from sqlalchemy.ext.asyncio import AsyncSession

from eniak_orchestrator.dry_run import (
    DryRunOrchestrator,
    _extract_json,  # noqa: PLC2701
)

logger = logging.getLogger(__name__)


@dataclass
class BookOutline:
    title: str
    subtitle: str | None
    chapters: list[dict]  # [{title, themes: [str, ...]}]


@dataclass
class BookResult:
    book_id: str
    chapter_ids: list[str]
    run_ids: list[str]
    failed_chapter_titles: list[str]


class BookOrchestrator:
    """Plan a book outline, then execute the dry-run loop per chapter."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        llm: LLMClient | None = None,
        chapter_orchestrator_factory=None,
    ) -> None:
        self.session = session
        self.llm = llm or LLMClient()
        self._chapter_factory = chapter_orchestrator_factory or DryRunOrchestrator

    async def plan_outline(self, topic: str) -> BookOutline:
        prompt = BOOK_OUTLINE_TEMPLATE.format(topic=topic)
        response = await self.llm.complete(
            prompt,
            system="You return strict JSON.",
            temperature=0.3,
            max_tokens=800,
        )
        try:
            payload = _extract_json(response.content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Outline LLM produced no JSON: {exc}") from exc

        raw_chapters = payload.get("chapters") or []
        chapters = []
        for entry in raw_chapters:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            themes = [t for t in (entry.get("themes") or []) if isinstance(t, str)]
            chapters.append({"title": title, "themes": themes})
        if not chapters:
            raise RuntimeError("Outline LLM produced no chapters")

        return BookOutline(
            title=(payload.get("title") or topic)[:512],
            subtitle=(payload.get("subtitle") or None),
            chapters=chapters,
        )

    async def build(
        self,
        topic: str,
        *,
        chapter_count: int = 3,
        outline: BookOutline | None = None,
        book: Book | None = None,
    ) -> BookResult:
        """Generate chapters under ``book``. If ``book`` is None, create one."""
        outline = outline or await self.plan_outline(topic)
        outline.chapters = outline.chapters[:chapter_count]

        if book is None:
            book = Book(
                title=outline.title,
                subtitle=outline.subtitle,
                topic=topic,
                status="generating",
                metadata_json={"outline": {"chapters": outline.chapters}},
            )
            self.session.add(book)
            await self.session.flush()
        else:
            book.status = "generating"
            book.metadata_json = {"outline": {"chapters": outline.chapters}}
            await self.session.flush()

        chapter_ids: list[str] = []
        run_ids: list[str] = []
        failures: list[str] = []

        for idx, ch in enumerate(outline.chapters):
            chapter_topic = self._compose_subtopic(topic, ch)
            try:
                run = Run(
                    topic=chapter_topic,
                    status=RunStatus.running,
                    model=getattr(self.llm, "default_model", None),
                    provider=getattr(self.llm, "provider", None),
                    started_at=datetime.now(UTC),
                    config_json={"pipeline": "book", "book_id": book.id, "chapter_idx": idx},
                )
                self.session.add(run)
                await self.session.flush()
                run_ids.append(run.id)

                orchestrator = self._chapter_factory(self.session, llm=self.llm)
                result = await orchestrator.execute_existing(run, chapter_topic)
                # Re-fetch the Chapter the orchestrator just created.
                from sqlalchemy import select

                ch_stmt = (
                    select(Chapter)
                    .where(Chapter.id == result.chapter_id)
                )
                chapter = (await self.session.execute(ch_stmt)).scalar_one()
                chapter.book_id = book.id
                chapter.order_index = idx
                if not chapter.title or chapter.title == f"Notes on {chapter_topic[:60]}":
                    chapter.title = ch["title"]
                await self.session.flush()
                chapter_ids.append(chapter.id)
            except Exception:
                logger.exception(
                    "book.chapter_failed",
                    extra={"book_id": book.id, "chapter_idx": idx, "title": ch["title"]},
                )
                failures.append(ch["title"])

        if not chapter_ids:
            book.status = "failed"
            await self.session.flush()
            return BookResult(
                book_id=book.id,
                chapter_ids=[],
                run_ids=run_ids,
                failed_chapter_titles=failures,
            )

        book.status = "ready_for_review"
        await self.session.flush()
        return BookResult(
            book_id=book.id,
            chapter_ids=chapter_ids,
            run_ids=run_ids,
            failed_chapter_titles=failures,
        )

    @staticmethod
    def _compose_subtopic(book_topic: str, chapter_entry: dict) -> str:
        themes = chapter_entry.get("themes") or []
        theme_str = "; ".join(themes[:3]) if themes else ""
        suffix = f" ({theme_str})" if theme_str else ""
        return f"{book_topic} — {chapter_entry['title']}{suffix}"
