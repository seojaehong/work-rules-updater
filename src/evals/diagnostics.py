"""Matching diagnostics generator for lookup/matching failure analysis."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

from src.ingestion.law_reference import normalize_law_name
from src.matching.matcher import RulesMatcher


class MatchDiagnostics:
    """Build article-level diagnostics for unmatched rules."""

    def __init__(self, matcher: RulesMatcher):
        self.matcher = matcher

    def build(
        self,
        *,
        rule_articles: list[dict],
        matches: list[dict],
        report: Optional[dict] = None,
        amendments: Optional[list[dict]] = None,
        since: Optional[str] = None,
    ) -> dict:
        report = report or {}
        amendments = amendments or []

        signature_hits = Counter(self._match_signature(match) for match in matches)

        unmatched_articles: list[dict] = []
        matched_article_count = 0
        for article in rule_articles:
            signature = self._article_signature(article)
            if signature_hits[signature] > 0:
                signature_hits[signature] -= 1
                matched_article_count += 1
                continue
            unmatched_articles.append(
                self._diagnose_unmatched_article(
                    article=article,
                    amendments=amendments,
                    report=report,
                )
            )

        match_type_counts = Counter(str(match.get("match_type", "unknown")) for match in matches)
        lookup_errors = self._summarize_lookup_errors(report.get("errors", []))
        failed_laws = sorted(
            {
                normalize_law_name(str(item.get("law_name", "")))
                for item in lookup_errors
                if item.get("law_name")
            }
        )
        diagnostic_code_counts = Counter(
            str(item.get("diagnostic_code", "UNKNOWN")) for item in unmatched_articles
        )

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": report.get("source", "provided"),
            "since": since,
            "summary": {
                "rule_article_count": len(rule_articles),
                "matched_article_count": matched_article_count,
                "unmatched_article_count": len(unmatched_articles),
                "match_count": len(matches),
                "match_type_counts": dict(match_type_counts),
                "degraded": bool(report.get("status") == "degraded"),
                "lookup_failed_law_count": len(failed_laws),
            },
            "lookup_failures": {
                "failed_laws": failed_laws,
                "entries": lookup_errors,
            },
            "diagnostic_code_counts": dict(diagnostic_code_counts),
            "unmatched_articles": unmatched_articles,
            "recommendations": self._build_recommendations(
                code_counts=diagnostic_code_counts,
                failed_law_count=len(failed_laws),
            ),
        }

    def _diagnose_unmatched_article(
        self,
        *,
        article: dict,
        amendments: list[dict],
        report: dict,
    ) -> dict:
        article_no = str(article.get("number", "")).strip()
        title = str(article.get("title", "")).strip()
        refs = article.get("law_references", []) or []

        amendments_by_law = self._index_amendments_by_law(amendments)
        amended_laws = set(amendments_by_law.keys())

        ref_laws = {
            normalize_law_name(str(ref.get("law", "")))
            for ref in refs
            if str(ref.get("law", "")).strip()
        }

        failed_laws = {
            normalize_law_name(str(error.get("law_name", "")))
            for error in report.get("errors", [])
            if str(error.get("law_name", "")).strip()
        }

        blocked_laws = sorted(ref_laws & failed_laws)

        direct_overlap = False
        if amendments and refs:
            direct_overlap = any(
                self.matcher._check_direct_match(ref, amendments) is not None for ref in refs
            )

        standard_probe = self._probe_standard(
            article=article,
            amendments_by_law=amendments_by_law,
            has_amendments=bool(amendments),
        )
        canonical_probe = self._probe_canonical(
            article=article,
            amendments_by_law=amendments_by_law,
            has_amendments=bool(amendments),
        )

        code = "UNMATCHED_UNKNOWN"
        reason = "매칭 후보를 찾지 못했습니다."

        if blocked_laws:
            code = "LAW_LOOKUP_FAILED"
            reason = (
                "법령 조회 실패로 참조 법령의 개정 여부 확인이 불가합니다"
                f" ({', '.join(blocked_laws)})."
            )
        elif refs:
            if not ref_laws & amended_laws:
                code = "REFERENCED_LAW_NOT_AMENDED"
                reason = "조문이 참조한 법령이 이번 개정 대상에 없습니다."
            elif not direct_overlap:
                code = "REFERENCED_ARTICLE_NOT_CHANGED"
                reason = "참조 법령은 개정되었지만 참조 조문과 변경 조문이 겹치지 않습니다."
            else:
                code = "DIRECT_MATCH_REJECTED"
                reason = "직접 인용 조문은 있으나 매칭 조건(조문정규화/중복제거)에서 제외되었습니다."
        else:
            if standard_probe.get("has_candidate"):
                law_in_amendments = standard_probe.get("law_in_amendments")
                change_overlap = standard_probe.get("change_overlap")
                if law_in_amendments is False:
                    code = "STANDARD_LAW_NOT_AMENDED"
                    reason = "표준 조문 후보는 있으나 해당 법령이 이번 개정 대상에 없습니다."
                elif law_in_amendments is True and change_overlap is False:
                    code = "STANDARD_ARTICLE_NOT_CHANGED"
                    reason = "표준 조문 후보 법령은 개정되었지만 표준 연결 조문이 변경 목록과 겹치지 않습니다."
                else:
                    code = "STANDARD_MATCH_REJECTED"
                    reason = "표준 조문 후보는 있으나 최종 매칭 조건을 만족하지 못했습니다."
            elif canonical_probe.get("has_candidate"):
                if not canonical_probe.get("over_threshold", False):
                    code = "CANONICAL_SIMILARITY_BELOW_THRESHOLD"
                    reason = "제목 유사도가 임계값보다 낮아 canonical 매칭에서 제외되었습니다."
                elif canonical_probe.get("law_in_amendments") is False:
                    code = "CANONICAL_LAW_NOT_AMENDED"
                    reason = "canonical 후보 법령이 이번 개정 대상에 없습니다."
                elif canonical_probe.get("law_in_amendments") is True and not canonical_probe.get(
                    "change_overlap", False
                ):
                    code = "CANONICAL_ARTICLE_NOT_CHANGED"
                    reason = "canonical 후보 조문이 변경 목록과 겹치지 않습니다."
                else:
                    code = "CANONICAL_MATCH_REJECTED"
                    reason = "canonical 후보는 있으나 최종 매칭 조건을 만족하지 못했습니다."
            else:
                code = "NO_REFERENCE_AND_LOW_SIMILARITY"
                reason = "법령 직접 인용이 없고 제목 유사도 후보도 임계값 미만입니다."

        return {
            "rule_article": article_no,
            "rule_title": title,
            "has_law_reference": bool(refs),
            "law_references": refs,
            "diagnostic_code": code,
            "diagnostic_reason": reason,
            "standard_probe": standard_probe,
            "canonical_probe": canonical_probe,
        }

    @staticmethod
    def _article_signature(article: dict) -> tuple[str, str]:
        uid = str(article.get("uid", "")).strip()
        if uid:
            return ("uid", uid)
        return (
            str(article.get("number", "")).strip(),
            str(article.get("title", "")).strip(),
        )

    @staticmethod
    def _match_signature(match: dict) -> tuple[str, str]:
        uid = str(match.get("rule_uid", "")).strip()
        if uid:
            return ("uid", uid)
        return (
            str(match.get("rule_article", "")).strip(),
            str(match.get("rule_title", "")).strip(),
        )

    @staticmethod
    def _index_amendments_by_law(amendments: list[dict]) -> dict[str, dict]:
        indexed: dict[str, dict] = {}
        for amendment in amendments:
            law_norm = normalize_law_name(str(amendment.get("law_name", "")))
            if not law_norm:
                continue
            indexed.setdefault(law_norm, amendment)
        return indexed

    def _probe_standard(
        self,
        *,
        article: dict,
        amendments_by_law: dict[str, dict],
        has_amendments: bool,
    ) -> dict:
        candidates = self.matcher._select_standard_entry_candidates(
            str(article.get("number", "")).strip(),
            str(article.get("title", "")),
        )
        if not candidates:
            return {
                "has_candidate": False,
            }

        top = candidates[0]
        entry = top.get("entry", {})
        law = normalize_law_name(str(entry.get("law", "")))
        law_in_amendments: Optional[bool] = None
        change_overlap: Optional[bool] = None

        if has_amendments:
            law_in_amendments = law in amendments_by_law
            if law_in_amendments:
                changed = amendments_by_law[law].get("changed_articles", [])
                if not changed:
                    change_overlap = True
                else:
                    change_overlap = self.matcher._has_changed_overlap(
                        entry.get("articles", []),
                        changed,
                    )

        return {
            "has_candidate": True,
            "key": top.get("key", ""),
            "matched_alias": top.get("matched_alias", ""),
            "similarity": round(float(top.get("similarity", 0.0)), 4),
            "law_name": law,
            "law_articles": entry.get("articles", []),
            "law_in_amendments": law_in_amendments,
            "change_overlap": change_overlap,
        }

    def _probe_canonical(
        self,
        *,
        article: dict,
        amendments_by_law: dict[str, dict],
        has_amendments: bool,
    ) -> dict:
        best = self._best_canonical_candidate(str(article.get("title", "")))
        if not best:
            return {
                "has_candidate": False,
                "best_similarity": 0.0,
                "min_similarity": self.matcher.min_similarity,
                "over_threshold": False,
            }

        law = normalize_law_name(best.get("law", ""))
        law_in_amendments: Optional[bool] = None
        change_overlap: Optional[bool] = None
        if has_amendments:
            law_in_amendments = law in amendments_by_law
            if law_in_amendments:
                changed = amendments_by_law[law].get("changed_articles", [])
                if not changed:
                    change_overlap = True
                else:
                    change_overlap = self.matcher._has_changed_overlap(
                        best.get("articles", []),
                        changed,
                    )

        similarity = float(best.get("similarity", 0.0))
        return {
            "has_candidate": True,
            "matched_alias": best.get("matched_alias", ""),
            "best_similarity": round(similarity, 4),
            "min_similarity": self.matcher.min_similarity,
            "over_threshold": similarity >= self.matcher.min_similarity,
            "law_name": law,
            "law_articles": best.get("articles", []),
            "law_in_amendments": law_in_amendments,
            "change_overlap": change_overlap,
        }

    def _best_canonical_candidate(self, title: str) -> Optional[dict]:
        best: Optional[dict] = None
        best_score = -1.0

        for entry in self.matcher.canonical_entries:
            for alias_raw, _alias_norm in entry.get("aliases", []):
                score = self.matcher._sentence_similarity(title, alias_raw)
                if score <= best_score:
                    continue
                best_score = score
                best = {
                    "law": entry.get("law", ""),
                    "articles": entry.get("articles", []),
                    "matched_alias": alias_raw,
                    "similarity": score,
                }

        return best

    @staticmethod
    def _summarize_lookup_errors(errors: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, str, str], int] = defaultdict(int)
        for error in errors:
            law_name = normalize_law_name(str(error.get("law_name", "")))
            stage = str(error.get("stage", "")).strip()
            message = str(error.get("error", "")).strip()
            grouped[(law_name, stage, message)] += 1

        rows = []
        for (law_name, stage, message), count in grouped.items():
            rows.append(
                {
                    "law_name": law_name,
                    "stage": stage,
                    "error": message,
                    "count": count,
                }
            )

        rows.sort(key=lambda item: (item.get("law_name", ""), -int(item.get("count", 0))))
        return rows

    @staticmethod
    def _build_recommendations(code_counts: Counter, failed_law_count: int) -> list[str]:
        recommendations: list[str] = []

        if failed_law_count > 0:
            recommendations.append(
                "법령조회 실패가 있어 DATA_GO_KR_KEY/LAW_API_ID/게이트웨이 차단 여부를 우선 점검하고 재실행하세요."
            )

        if code_counts.get("REFERENCED_ARTICLE_NOT_CHANGED", 0) > 0:
            recommendations.append(
                "직접 인용 법령은 있으나 변경 조문과 불일치한 항목은 현행유지 후보로 분류하고 수기 확인만 수행하세요."
            )

        if code_counts.get("NO_REFERENCE_AND_LOW_SIMILARITY", 0) > 0:
            recommendations.append(
                "무인용/저유사도 조문은 canonical_map aliases 보강 또는 조문 내 법령 인용 문구 추가를 검토하세요."
            )

        if code_counts.get("STANDARD_ARTICLE_NOT_CHANGED", 0) > 0:
            recommendations.append(
                "표준조문 후보가 있으나 변경 조문 미중첩인 항목은 추적 법령의 changed_articles 정확도부터 점검하세요."
            )

        if not recommendations:
            recommendations.append("현재 진단에서 즉시 조치가 필요한 실패 패턴은 탐지되지 않았습니다.")

        return recommendations
