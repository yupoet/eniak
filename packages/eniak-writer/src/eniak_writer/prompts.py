"""Prompt templates used by the dry-run loop.

Each template is content-hashed so a Run can record the exact prompt version it used.
Templates are written in English; the model decides output language based on topic.
"""

from __future__ import annotations

import hashlib


def hash_template(template: str) -> str:
    return hashlib.sha256(template.encode("utf-8")).hexdigest()[:16]


EVIDENCE_EXTRACTION_TEMPLATE = """\
You are an evidence extraction assistant for an academic research kernel.

Topic: {topic}

Source title: {source_title}
Source authors: {authors}
Source venue: {venue}
Source excerpt:
\"\"\"
{excerpt}
\"\"\"

Return exactly one JSON object with these keys:
- "summary": one-paragraph factual summary of what this source says about the topic.
- "quote": a verbatim sentence from the excerpt that best supports the summary (≤300 chars).
- "claims": an array of 1-3 short claim statements that this source supports, each ≤200 chars.

JSON only. No prose, no markdown fences.
"""


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
