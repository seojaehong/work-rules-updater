"""Ingestion layer modules."""

from src.ingestion.law_client import LawAPIClient
from src.ingestion.law_diff import LawDiff
from src.ingestion.law_parser import LawXMLParser
from src.ingestion.law_reference import (
    extract_law_references,
    normalize_article_reference,
    normalize_law_name,
)
from src.ingestion.rules_parser import WorkRulesParser

__all__ = [
    "LawAPIClient",
    "LawDiff",
    "LawXMLParser",
    "WorkRulesParser",
    "extract_law_references",
    "normalize_article_reference",
    "normalize_law_name",
]
