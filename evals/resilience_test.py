#!/usr/bin/env python
"""Resilience checks for API/CLI error handling."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class _FakeHtmlResponse:
    status_code = 200
    headers = {"content-type": "text/html"}
    text = "<!DOCTYPE html><html><script>window.location.assign('/x')</script></html>"
    content = text.encode("utf-8")

    def raise_for_status(self):
        return None


class ResilienceTest(unittest.TestCase):
    def test_law_client_handles_html_challenge(self):
        import src.ingestion.law_client as law_client_module

        original_get = law_client_module.requests.get
        law_client_module.requests.get = lambda *args, **kwargs: _FakeHtmlResponse()
        try:
            client = law_client_module.LawAPIClient()
            results = client.search_law("근로기준법")
            self.assertEqual(results, [])
            self.assertTrue(client._last_search_error)
            self.assertIn("HTML", client._last_search_error)
        finally:
            law_client_module.requests.get = original_get

    def test_matcher_generates_fallback_on_api_failure(self):
        import src.ingestion.law_client as law_client_module
        from src.matching.matcher import RulesMatcher

        original_client = law_client_module.LawAPIClient

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                self.last_check_report = {
                    "status": "degraded",
                    "had_errors": True,
                    "errors": [
                        {
                            "law_name": "근로기준법",
                            "stage": "search_law",
                            "error": "HTML challenge",
                        }
                    ],
                }

            def check_amendments(self, *args, **kwargs):
                return []

        law_client_module.LawAPIClient = _FakeClient
        try:
            matcher = RulesMatcher()
            matches = matcher.find_matches(
                rule_articles=[
                    {
                        "number": "12",
                        "title": "근로조건",
                        "content": "근로기준법 제43조의2를 준수한다.",
                        "law_references": [
                            {
                                "law": "근로기준법",
                                "article": "제43조의2",
                                "reference": "제43조의2",
                            }
                        ],
                    }
                ],
                amendments=None,
            )
            self.assertTrue(matches)
            self.assertTrue(all(match.get("match_type") == "fallback" for match in matches))
            self.assertEqual(matcher.last_report.get("status"), "degraded")
        finally:
            law_client_module.LawAPIClient = original_client

    def test_cli_no_unicodeencodeerror_on_cp949(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp949"
        env["PYTHONUTF8"] = "0"

        process = subprocess.run(
            [sys.executable, "main.py", "parse-rules", "data/company_rules/없는파일.docx"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(process.returncode, 0)
        combined = (process.stdout or "") + "\n" + (process.stderr or "")
        self.assertNotIn("UnicodeEncodeError", combined)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ResilienceTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
