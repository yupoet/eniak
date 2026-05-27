"""ENIAK radar — source candidate generation.

Phase 2 ships only a mock provider so the dry-run loop is testable without
external API keys. Real providers land in Phase 3.
"""

from eniak_radar.mock import MockRadar, SourceCandidate

__all__ = ["MockRadar", "SourceCandidate"]
