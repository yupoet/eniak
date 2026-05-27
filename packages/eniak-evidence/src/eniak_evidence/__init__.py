"""ENIAK evidence domain core.

Source of truth for sources, documents, claims, citations, and the
run/prompt/review/cost ledger that surrounds them.
"""

from eniak_evidence.db import Base, dispose_engine, get_engine, get_session, init_engine
from eniak_evidence.models import (
    Book,
    Chapter,
    Citation,
    Claim,
    Contradiction,
    CostLedger,
    Document,
    EvidenceCard,
    PromptTemplate,
    ReviewState,
    ReviewStateName,
    Run,
    RunStatus,
    Source,
)
from eniak_evidence.schemas import (
    ChapterRead,
    ChapterUpdate,
    ClaimRead,
    CostSummary,
    EvidenceCardRead,
    RunCreate,
    RunDetail,
    RunRead,
    SourceRead,
)

__all__ = [
    "Base",
    "Book",
    "Chapter",
    "ChapterRead",
    "ChapterUpdate",
    "Citation",
    "Claim",
    "ClaimRead",
    "Contradiction",
    "CostLedger",
    "CostSummary",
    "Document",
    "EvidenceCard",
    "EvidenceCardRead",
    "PromptTemplate",
    "ReviewState",
    "ReviewStateName",
    "Run",
    "RunCreate",
    "RunDetail",
    "RunRead",
    "RunStatus",
    "Source",
    "SourceRead",
    "dispose_engine",
    "get_engine",
    "get_session",
    "init_engine",
]
