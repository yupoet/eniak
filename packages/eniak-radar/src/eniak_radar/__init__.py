"""ENIAK radar — source candidate generation + PDF retrieval."""

from eniak_radar.arxiv import ArxivRadar
from eniak_radar.base import RadarProvider, SourceCandidate
from eniak_radar.mock import MockRadar
from eniak_radar.openalex import OpenAlexRadar
from eniak_radar.pdf import ExtractedPdf, fetch_and_extract
from eniak_radar.registry import RadarFanout, build_default_providers

__all__ = [
    "ArxivRadar",
    "ExtractedPdf",
    "MockRadar",
    "OpenAlexRadar",
    "RadarFanout",
    "RadarProvider",
    "SourceCandidate",
    "build_default_providers",
    "fetch_and_extract",
]
