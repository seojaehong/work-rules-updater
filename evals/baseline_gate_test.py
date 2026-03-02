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
        missing = []
        if not BASELINE_FILE.exists():
            missing.append(str(BASELINE_FILE))
        if not CROSSWALK_FILE.exists():
            missing.append(str(CROSSWALK_FILE))
        if missing:
            raise AssertionError(
                f"필수 기준선 파일 누락 (CI에서 Skip 방지): {', '.join(missing)}"
            )

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


class OverridePrecedenceTest(unittest.TestCase):
    """override가 global standard_map을 덮어쓰는지 검증."""

    def test_override_replaces_global_entry(self):
        """override articles가 global 동일 key를 대체해야 한다."""
        import tempfile

        from src.matching.matcher import RulesMatcher

        override = {
            "articles": {
                "93": {
                    "title": "테스트 override 조항",
                    "aliases": ["테스트 override"],
                    "law": "근로기준법",
                    "articles": ["제999조"],
                    "source": "테스트",
                }
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(override, f, ensure_ascii=False)
            tmp_path = f.name

        try:
            matcher = RulesMatcher(override_path=tmp_path)
            entry = matcher.standard_article_map.get("93")
            self.assertIsNotNone(entry, "key 93이 standard_article_map에 없음")
            self.assertEqual(
                entry["title"],
                "테스트 override 조항",
                "override가 global을 대체하지 못함",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
