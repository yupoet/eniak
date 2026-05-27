"""ENIAK writer — turns evidence into chapters."""

from eniak_writer.llm import LLMClient, LLMResponse
from eniak_writer.prompts import (
    BOOK_OUTLINE_TEMPLATE,
    CHAPTER_DRAFT_TEMPLATE,
    CONTRADICTION_TEMPLATE,
    EVIDENCE_EXTRACTION_TEMPLATE,
    hash_template,
)

__all__ = [
    "BOOK_OUTLINE_TEMPLATE",
    "CHAPTER_DRAFT_TEMPLATE",
    "CONTRADICTION_TEMPLATE",
    "EVIDENCE_EXTRACTION_TEMPLATE",
    "LLMClient",
    "LLMResponse",
    "hash_template",
]
