"""Prompt templates used by the orchestrator.

Each template is content-addressed so a Run can record exactly which prompt
version produced its evidence/draft. Bump the version comment when editing.
"""

from __future__ import annotations

import hashlib


def hash_template(template: str) -> str:
    return hashlib.sha256(template.encode("utf-8")).hexdigest()[:16]


# v3 — page-aware extraction
EVIDENCE_EXTRACTION_TEMPLATE = """\
You are an evidence extraction assistant for a research kernel.

Topic: {topic}

Source title: {source_title}
Source authors: {authors}
Source venue: {venue}
Source body (may be the full paper with [page N] markers, or just an abstract):
\"\"\"
{excerpt}
\"\"\"

Return exactly one JSON object with these keys:
- "summary": one-paragraph factual summary of what this source says about the topic.
- "quote": a verbatim sentence from the body that best supports the summary (<=300 chars).
- "page": integer page number of the quote if a [page N] marker is present in the body, else null.
- "section": short label for the section the quote is in (e.g. "Introduction", "Results"), or null.
- "claims": 1-3 short claim statements that this source supports, each <=200 chars.

JSON only, no prose, no markdown fences.
"""


# v1 — chapter draft from N cards
CHAPTER_DRAFT_TEMPLATE = """\
You are writing one chapter of a research brief.

Topic: {topic}

You have N evidence cards. Each card has an ID, a summary, and an optional quote.
You MUST cite every claim with one or more card IDs using the form [card:<id>] inline.
Do NOT invent claims that are not supported by at least one card.

Evidence cards:
{cards_block}

Write a chapter of ~500 words with:
- A short title on the first line, prefixed with "# ".
- 3-5 paragraphs of analysis.
- Inline citations using [card:<id>].
- A final "Open questions" subsection with at least one open question.

Markdown only.
"""


# v1 — book outline
BOOK_OUTLINE_TEMPLATE = """\
You are an editor planning a short research book on a single topic.

Topic: {topic}

Plan a book outline:
- 1 working title
- 3-5 chapters
- For each chapter: a 1-line working title and 2-3 bullet sub-themes

Return strict JSON with this shape:
{{
  "title": "...",
  "subtitle": "...",
  "chapters": [
    {{ "title": "...", "themes": ["...", "..."] }},
    ...
  ]
}}

JSON only, no prose.
"""


# v1 — contradiction detection between evidence cards
CONTRADICTION_TEMPLATE = """\
You are a research integrity reviewer. Given pairs of evidence cards on the
same topic, flag pairs that make contradictory claims about the same fact.

Topic: {topic}

Cards:
{cards_block}

Return strict JSON:
{{
  "contradictions": [
    {{
      "card_a_id": "...",
      "card_b_id": "...",
      "severity": 0.0-1.0,
      "rationale": "<=200 chars"
    }}
  ]
}}

Only include pairs that are actually contradictory. If none, return empty array.
JSON only.
"""
