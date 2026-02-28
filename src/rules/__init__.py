"""Backward compatibility imports for legacy rules package."""

from src.rules.docx_parser import WorkRulesParser
from src.rules.matcher import RulesMatcher
from src.rules.updater import RulesUpdater

__all__ = ["WorkRulesParser", "RulesMatcher", "RulesUpdater"]
