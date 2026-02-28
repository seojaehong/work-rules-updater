"""Compatibility wrapper for moved xlsx writer module."""

from src.outputs.xlsx_output import XlsxComparisonWriter


class ComparisonTableGenerator(XlsxComparisonWriter):
    """Backward-compatible class alias."""
