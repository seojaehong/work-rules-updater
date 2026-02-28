"""Run rubric smoke evaluation for PR gating."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.evals.rubric import RubricRunner
from src.ingestion.law_reference import extract_law_references
from src.matching.matcher import RulesMatcher
from src.outputs.json_output import JsonOutputWriter


def _load_fixture(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _inject_references(rule_articles: list[dict]) -> list[dict]:
    articles = []
    for article in rule_articles:
        enriched = dict(article)
        enriched["law_references"] = extract_law_references(enriched.get("content", ""))
        articles.append(enriched)
    return articles


def main() -> int:
    repo_root = REPO_ROOT
    fixture_path = repo_root / "evals" / "fixtures" / "smoke_cases.json"
    result_path = repo_root / "evals" / "results" / "smoke" / "latest.json"

    fixture = _load_fixture(fixture_path)
    rule_articles = _inject_references(fixture.get("rule_articles", []))
    amendments = fixture.get("amendments", [])

    matcher = RulesMatcher()
    matches = matcher.find_matches(rule_articles=rule_articles, amendments=amendments)

    edge_article = next((a for a in rule_articles if a.get("number") == "93"), {})
    edge_refs = edge_article.get("law_references", [])

    checks = [
        {
            "name": "extract_article_43_2",
            "passed": any(ref.get("article") == "제43조의2" for ref in edge_refs),
            "detail": edge_refs,
        },
        {
            "name": "extract_article_93_item_1",
            "passed": any(
                ref.get("article") == "제93조" and ref.get("item") == "제1호" for ref in edge_refs
            ),
            "detail": edge_refs,
        },
        {
            "name": "direct_match_article_43_2",
            "passed": any(
                match.get("match_type") == "direct" and "제43조의2" in match.get("law_article", "")
                for match in matches
            ),
            "detail": [m for m in matches if m.get("match_type") == "direct"],
        },
        {
            "name": "direct_match_article_93_item_1",
            "passed": any(
                match.get("match_type") == "direct" and "제93조제1호" in match.get("law_article", "")
                for match in matches
            ),
            "detail": [m for m in matches if m.get("match_type") == "direct"],
        },
    ]

    rubric = RubricRunner(direct_ratio_threshold=0.5)
    result = rubric.evaluate(matches=matches, rule_articles=rule_articles, checks=checks)
    result["match_preview"] = matches[:5]
    result["artifact"] = str(result_path)

    JsonOutputWriter().write(result, str(result_path))

    print(f"Smoke result: {result['status']}")
    print(f"Direct match ratio: {result['metrics']['direct_match_ratio']}")
    print(f"Result file: {result_path}")

    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
