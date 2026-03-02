#!/usr/bin/env python
"""Baseline gate test: 대원산업 오프라인 기준선 검증.

통과조건:
  - unmatched_article_count == 0
  - fallback == 0
  - degraded == false
"""

from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BASELINE_FILE = REPO_ROOT / "data" / "offline" / "daewon_amendments_baseline_20260302.json"
CROSSWALK_FILE = REPO_ROOT / "output" / "대원산업" / "취업규칙(2024.11.개정)_조항크로스워크_20260226_213847.json"


def _load_rule_articles() -> list[dict]:
    cw = json.loads(CROSSWALK_FILE.read_text(encoding="utf-8"))
    articles = []
    for row in cw["rows"]:
        num = row["company_article"].replace("제", "").replace("조", "").strip()
        articles.append(
            {
                "number": num,
                "title": row["company_title"],
                "content": row.get("company_snippet", "")[:200],
                "law_references": [],
                "uid": f"daewon_{num}",
            }
        )
    return articles


def _load_amendments() -> list[dict]:
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return baseline["amendments"]


class BaselineGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BASELINE_FILE.exists() or not CROSSWALK_FILE.exists():
            raise unittest.SkipTest("baseline or crosswalk file missing")

        from src.matching.matcher import RulesMatcher

        cls.rule_articles = _load_rule_articles()
        cls.amendments = _load_amendments()
        cls.matcher = RulesMatcher()
        cls.matches = cls.matcher.find_matches(
            cls.rule_articles, amendments=cls.amendments
        )
        cls.report = cls.matcher.last_report
        cls.matched_uids = {m.get("rule_uid", "") for m in cls.matches}
        cls.unmatched = [
            a for a in cls.rule_articles if a["uid"] not in cls.matched_uids
        ]
        cls.type_counts = Counter(
            m.get("match_type", "unknown") for m in cls.matches
        )

    def test_no_unmatched_articles(self):
        """모든 조문이 매칭되어야 한다."""
        self.assertEqual(
            len(self.unmatched),
            0,
            f"미매칭 {len(self.unmatched)}건: "
            + ", ".join(f"제{a['number']}조 {a['title']}" for a in self.unmatched),
        )

    def test_no_fallback_matches(self):
        """fallback 매칭이 없어야 한다 (API 정상 시나리오)."""
        fallback_count = self.type_counts.get("fallback", 0)
        self.assertEqual(fallback_count, 0, f"fallback 매칭 {fallback_count}건 발생")

    def test_not_degraded(self):
        """degraded 상태가 아니어야 한다."""
        status = self.report.get("status", "")
        self.assertNotEqual(status, "degraded", "매칭 결과가 degraded 상태")

    def test_no_topic_matches(self):
        """topic 매칭(저정밀)이 없어야 한다."""
        topic_count = self.type_counts.get("topic", 0)
        self.assertEqual(topic_count, 0, f"topic 매칭 {topic_count}건 발생")

    def test_match_count_minimum(self):
        """최소 매칭 수 보장 (조문 수 이상)."""
        self.assertGreaterEqual(
            len(self.matches),
            len(self.rule_articles),
            f"매칭 수({len(self.matches)})가 조문 수({len(self.rule_articles)})보다 적음",
        )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
