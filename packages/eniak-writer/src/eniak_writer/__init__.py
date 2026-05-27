"""ENIAK writer — turns evidence into chapters."""

from eniak_writer.llm import LLMClient, LLMResponse
from eniak_writer.prompts import (
    CHAPTER_DRAFT_TEMPLATE,
    EVIDENCE_EXTRACTION_TEMPLATE,
    hash_template,
)

__all__ = [
    "CHAPTER_DRAFT_TEMPLATE",
    "EVIDENCE_EXTRACTION_TEMPLATE",
    "LLMClient",
    "LLMResponse",
    "hash_template",
]
