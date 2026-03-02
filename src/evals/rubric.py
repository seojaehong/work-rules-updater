"""Rubric evaluator for match quality smoke checks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


class RubricRunner:
    """Compute quality metrics, score, and pass/fail status."""

    def __init__(
        self,
        direct_ratio_threshold: float = 0.5,
        canonical_ratio_threshold: float = 0.5,
        topic_fallback_ratio_threshold: float = 0.3,
        min_score: float = 99.0,
    ):
        self.direct_ratio_threshold = direct_ratio_threshold
        self.canonical_ratio_threshold = canonical_ratio_threshold
        self.topic_fallback_ratio_threshold = topic_fallback_ratio_threshold
        self.min_score = min_score

    def evaluate(
        self,
        matches: list[dict],
        rule_articles: Optional[list[dict]] = None,
        checks: Optional[list[dict]] = None,
    ) -> dict:
        total_matches = len(matches)
        match_type_counts = {
            "standard": sum(1 for match in matches if match.get("match_type") == "standard"),
            "direct": sum(1 for match in matches if match.get("match_type") == "direct"),
            "canonical": sum(1 for match in matches if match.get("match_type") == "canonical"),
            "topic": sum(1 for match in matches if match.get("match_type") == "topic"),
            "fallback": sum(1 for match in matches if match.get("match_type") == "fallback"),
        }

        article_type_index: dict[str, set[str]] = {}
        for match in matches:
            article = str(match.get("rule_article", "")).strip()
            if not article:
                continue
            article_type_index.setdefault(article, set()).add(match.get("match_type", ""))

        total_matched_articles = len(article_type_index)
        direct_articles = sum(1 for types in article_type_index.values() if "direct" in types)
        canonical_articles = sum(
            1 for types in article_type_index.values() if ("canonical" in types or "standard" in types)
        )
        topic_fallback_articles = sum(
            1 for types in article_type_index.values() if ("topic" in types or "fallback" in types)
        )

        direct_ratio = (direct_articles / total_matched_articles) if total_matched_articles else 0.0
        canonical_ratio = (canonical_articles / total_matched_articles) if total_matched_articles else 0.0
        topic_fallback_ratio = (
            topic_fallback_articles / total_matched_articles if total_matched_articles else 0.0
        )

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

        if canonical_ratio < self.canonical_ratio_threshold:
            failures.append(
                f"canonical_ratio_below_threshold({canonical_ratio:.2f} < {self.canonical_ratio_threshold:.2f})"
            )

        if topic_fallback_ratio > self.topic_fallback_ratio_threshold:
            failures.append(
                "topic_fallback_ratio_above_threshold"
                f"({topic_fallback_ratio:.2f} > {self.topic_fallback_ratio_threshold:.2f})"
            )

        passed_checks = []
        check_list = checks or []
        for check in check_list:
            if check.get("passed"):
                passed_checks.append(check.get("name", "unnamed_check"))
            else:
                failures.append(check.get("name", "unnamed_check"))

        score = self._compute_score(
            total_matches=total_matches,
            direct_ratio=direct_ratio,
            canonical_ratio=canonical_ratio,
            topic_fallback_ratio=topic_fallback_ratio,
            check_count=len(check_list),
            passed_check_count=len(passed_checks),
        )

        if score < self.min_score:
            failures.append(f"score_below_threshold({score:.2f} < {self.min_score:.2f})")

        status = "passed" if not failures else "failed"
        return {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "score": round(score, 2),
            "thresholds": {
                "direct_ratio_threshold": self.direct_ratio_threshold,
                "canonical_ratio_threshold": self.canonical_ratio_threshold,
                "topic_fallback_ratio_threshold": self.topic_fallback_ratio_threshold,
                "min_score": self.min_score,
            },
            "metrics": {
                "total_matches": total_matches,
                "total_matched_articles": total_matched_articles,
                "direct_matches": match_type_counts["direct"],
                "standard_matches": match_type_counts["standard"],
                "canonical_matches": match_type_counts["canonical"],
                "topic_matches": match_type_counts["topic"],
                "fallback_matches": match_type_counts["fallback"],
                "direct_match_ratio": round(direct_ratio, 4),
                "match_canonical_ratio": round(canonical_ratio, 4),
                "topic_fallback_ratio": round(topic_fallback_ratio, 4),
                "reference_coverage_ratio": round(reference_coverage, 4),
            },
            "checks": check_list,
            "passed_checks": passed_checks,
            "failures": failures,
        }

    def _compute_score(
        self,
        total_matches: int,
        direct_ratio: float,
        canonical_ratio: float,
        topic_fallback_ratio: float,
        check_count: int,
        passed_check_count: int,
    ) -> float:
        if total_matches == 0:
            return 0.0

        score = 100.0

        if direct_ratio < self.direct_ratio_threshold:
            gap = (self.direct_ratio_threshold - direct_ratio) / max(self.direct_ratio_threshold, 1e-6)
            score -= 25.0 * gap

        if canonical_ratio < self.canonical_ratio_threshold:
            gap = (self.canonical_ratio_threshold - canonical_ratio) / max(
                self.canonical_ratio_threshold, 1e-6
            )
            score -= 25.0 * gap

        if topic_fallback_ratio > self.topic_fallback_ratio_threshold:
            over = (topic_fallback_ratio - self.topic_fallback_ratio_threshold) / max(
                1.0 - self.topic_fallback_ratio_threshold,
                1e-6,
            )
            score -= 25.0 * over

        if check_count > 0:
            failed_ratio = (check_count - passed_check_count) / check_count
            score -= 25.0 * failed_ratio

        return max(0.0, min(100.0, score))
