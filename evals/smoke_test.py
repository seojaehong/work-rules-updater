#!/usr/bin/env python
"""Basic smoke test for local and CI validation."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _fail(message: str) -> int:
    print(f"[SMOKE][FAIL] {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        # Core module import smoke checks.
        import main as _cli_main  # noqa: F401
        from src.law_api.parser import LawXMLParser
        from src.rules.matcher import RulesMatcher
        from src.rules.updater import RulesUpdater
    except Exception as exc:  # pragma: no cover - smoke guard
        traceback.print_exc()
        return _fail(f"module import failed: {exc}")

    sample_xml = """
    <법령정보>
      <법령명_한글>근로기준법</법령명_한글>
      <법령ID>LAW-12345</법령ID>
      <공포일자>20260101</공포일자>
      <시행일자>20260115</시행일자>
      <조문시행일자문자열>2026-01-15: 제1조, 제2조</조문시행일자문자열>
      <조문단위>
        <조문번호>1</조문번호>
        <조문제목>목적</조문제목>
        <조문내용>이 법은 근로조건의 기준을 정함을 목적으로 한다.</조문내용>
      </조문단위>
    </법령정보>
    """.strip()

    parser = LawXMLParser()
    law_data = parser.parse_law_detail(sample_xml.encode("utf-8"))
    if not law_data:
        return _fail("XML parser returned no data")
    if law_data.get("law_name") != "근로기준법":
        return _fail(f"unexpected law name: {law_data.get('law_name')!r}")
    if len(law_data.get("articles", [])) != 1:
        return _fail("expected exactly one parsed article")
    if not isinstance(law_data.get("changed_articles"), list):
        return _fail("changed_articles must be a list")

    rule_articles = [
        {
            "number": "1",
            "title": "근로조건",
            "content": "근로기준법 제1조를 따른다.",
            "law_references": [{"law": "근로기준법", "article": "제1조"}],
        }
    ]
    amendments = [
        {
            "law_name": "근로기준법",
            "effective_date": "2026-01-15",
            "changed_articles": ["제1조"],
        }
    ]

    matcher = RulesMatcher()
    matches = matcher.find_matches(rule_articles=rule_articles, amendments=amendments)
    if not matches:
        return _fail("matcher returned no matches")

    updater = RulesUpdater()
    drafts = updater.generate_draft(matches=matches, original_articles=rule_articles)
    if not drafts:
        return _fail("updater returned no drafts")

    print("[SMOKE][PASS] imports, parser, matcher, and updater checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
