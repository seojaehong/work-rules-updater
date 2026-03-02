#!/usr/bin/env python
"""Diagnostics checks for unmatched article reasoning."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.evals.diagnostics import MatchDiagnostics
from src.matching.matcher import RulesMatcher


class DiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.matcher = RulesMatcher()
        self.diag = MatchDiagnostics(self.matcher)

    def test_law_lookup_failed_code(self):
        report = {
            "status": "degraded",
            "errors": [
                {
                    "law_name": "근로기준법",
                    "stage": "search_law",
                    "error": "HTML challenge",
                }
            ],
        }
        article = {
            "number": "10",
            "title": "임금지급",
            "content": "근로기준법 제43조의2를 따른다.",
            "law_references": [
                {
                    "law": "근로기준법",
                    "article": "제43조의2",
                    "reference": "제43조의2",
                }
            ],
        }

        payload = self.diag.build(
            rule_articles=[article],
            matches=[],
            report=report,
            amendments=[],
            since="2026-01-01",
        )

        self.assertEqual(payload["unmatched_articles"][0]["diagnostic_code"], "LAW_LOOKUP_FAILED")

    def test_referenced_article_not_changed_code(self):
        article = {
            "number": "29",
            "title": "연장·야간 및 휴일근로",
            "content": "근로기준법 제53조를 따른다.",
            "law_references": [
                {
                    "law": "근로기준법",
                    "article": "제53조",
                    "reference": "제53조",
                }
            ],
        }
        amendments = [
            {
                "law_name": "근로기준법",
                "effective_date": "20260101",
                "changed_articles": ["제60조"],
            }
        ]

        payload = self.diag.build(
            rule_articles=[article],
            matches=[],
            report={"status": "ok", "errors": []},
            amendments=amendments,
            since="2026-01-01",
        )

        self.assertEqual(
            payload["unmatched_articles"][0]["diagnostic_code"],
            "REFERENCED_ARTICLE_NOT_CHANGED",
        )

    def test_no_reference_low_similarity_code(self):
        article = {
            "number": "999",
            "title": "복리후생 운영원칙",
            "content": "복리후생 기준을 정한다.",
            "law_references": [],
        }

        payload = self.diag.build(
            rule_articles=[article],
            matches=[],
            report={"status": "ok", "errors": []},
            amendments=[],
            since="2026-01-01",
        )

        self.assertIn(
            payload["unmatched_articles"][0]["diagnostic_code"],
            {"NO_REFERENCE_AND_LOW_SIMILARITY", "CANONICAL_SIMILARITY_BELOW_THRESHOLD"},
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DiagnosticsTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
