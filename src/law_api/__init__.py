"""Backward compatibility imports for legacy law_api package."""

from src.law_api.client import LawAPIClient
from src.law_api.diff import LawDiff
from src.law_api.parser import LawXMLParser

__all__ = ["LawAPIClient", "LawXMLParser", "LawDiff"]
