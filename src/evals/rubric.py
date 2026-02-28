"""Rubric evaluator for match quality smoke checks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


class RubricRunner:
    """Compute quality metrics and pass/fail status."""

    def __init__(self, direct_ratio_threshold: float = 0.5):
        self.direct_ratio_threshold = direct_ratio_threshold

    def evaluate(
        self,
        matches: list[dict],
        rule_articles: Optional[list[dict]] = None,
        checks: Optional[list[dict]] = None,
    ) -> dict:
        total_matches = len(matches)
        direct_matches = sum(1 for match in matches if match.get("match_type") == "direct")
        topic_matches = sum(1 for match in matches if match.get("match_type") == "topic")
        direct_ratio = (direct_matches / total_matches) if total_matches else 0.0

        reference_coverage = 0.0
        if rule_articles:
            with_refs = sum(1 for article in rule_articles if article.get("law_references"))
            reference_coverage = with_refs / len(rule_articles) if rule_articles else 0.0

        failures = []
        if total_matches == 0:
            failures.append("no_matches")
        if direct_ratio < self.direct_ratio_threshold:
            failures.append(
                f"direct_match_ratio_below_threshold({direct_ratio:.2f} < {self.direct_ratio_threshold:.2f})"
            )

        passed_checks = []
        for check in checks or []:
            if check.get("passed"):
                passed_checks.append(check.get("name", "unnamed_check"))
            else:
                failures.append(check.get("name", "unnamed_check"))

        status = "passed" if not failures else "failed"
        return {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "metrics": {
                "total_matches": total_matches,
                "direct_matches": direct_matches,
                "topic_matches": topic_matches,
                "direct_match_ratio": round(direct_ratio, 4),
                "reference_coverage_ratio": round(reference_coverage, 4),
            },
            "checks": checks or [],
            "passed_checks": passed_checks,
            "failures": failures,
        }
