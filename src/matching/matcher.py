"""
법령 변경사항 ↔ 취업규칙 매칭 모듈.

매칭 우선순위:
1. 직접 매칭: 취업규칙 조문 내 법령 참조
2. 규칙 기반 매칭: config/law_mapping.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from src.ingestion.law_reference import normalize_article_reference, normalize_law_name


class RulesMatcher:
    """법령-취업규칙 매칭."""

    def __init__(self, mapping_path: str = "config/law_mapping.json"):
        path = Path(mapping_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as file:
                config = json.load(file)
            self.mappings = config.get("mappings", [])
        else:
            self.mappings = []

    def find_matches(
        self,
        rule_articles: list[dict],
        since: Optional[str] = None,
        amendments: Optional[list[dict]] = None,
    ) -> list[dict]:
        """취업규칙 조문과 법령 변경사항 매칭."""
        if amendments is None:
            from src.ingestion.law_client import LawAPIClient

            client = LawAPIClient()
            amendments = client.check_amendments(since=since)

        if not amendments:
            return []

        matches: list[dict] = []
        existing_keys: set[tuple[str, str, str]] = set()

        for article in rule_articles:
            for ref in article.get("law_references", []):
                amendment = self._check_direct_match(ref, amendments)
                if not amendment:
                    continue

                law_article = ref.get("reference") or self._compose_reference(
                    ref.get("article", ""),
                    ref.get("paragraph", ""),
                    ref.get("item", ""),
                )
                key = (article["number"], amendment["law_name"], law_article)
                if key in existing_keys:
                    continue
                existing_keys.add(key)

                matches.append(
                    {
                        "rule_article": article["number"],
                        "rule_title": article.get("title", ""),
                        "rule_content": article.get("content", "")[:200],
                        "law_name": amendment["law_name"],
                        "law_article": law_article,
                        "effective_date": amendment.get("effective_date", ""),
                        "match_type": "direct",
                        "reason": (
                            f"{amendment['law_name']} {law_article} 개정 "
                            f"(시행일: {amendment.get('effective_date', '-')})"
                        ),
                    }
                )

            topic_match = self._check_topic_match(article, amendments)
            if not topic_match:
                continue

            key = (
                article["number"],
                topic_match["law_name"],
                topic_match.get("law_articles", ""),
            )
            if key in existing_keys:
                continue
            existing_keys.add(key)

            matches.append(
                {
                    "rule_article": article["number"],
                    "rule_title": article.get("title", ""),
                    "rule_content": article.get("content", "")[:200],
                    "law_name": topic_match["law_name"],
                    "law_article": topic_match.get("law_articles", ""),
                    "effective_date": topic_match.get("effective_date", ""),
                    "match_type": "topic",
                    "reason": topic_match.get("reason", ""),
                }
            )

        return matches

    def _check_direct_match(
        self,
        law_ref: dict,
        amendments: list[dict],
    ) -> Optional[dict]:
        """직접 매칭: 인용한 법령 조항이 개정됐는지 확인."""
        reference_law = normalize_law_name(law_ref.get("law", ""))
        reference_norm = self._normalize_reference(law_ref)

        for amendment in amendments:
            amended_law = normalize_law_name(amendment.get("law_name", ""))
            if amended_law != reference_law:
                continue

            changed_articles = amendment.get("changed_articles", [])
            if not changed_articles:
                return amendment

            if not reference_norm:
                continue

            for changed in changed_articles:
                changed_norm = self._normalize_changed_article(changed)
                if changed_norm and self._is_reference_match(reference_norm, changed_norm):
                    return amendment

                changed_text = re.sub(r"\s+", "", str(changed))
                if reference_norm["article"] in changed_text:
                    return amendment

        return None

    def _check_topic_match(
        self,
        article: dict,
        amendments: list[dict],
    ) -> Optional[dict]:
        """규칙 기반 매칭: 주제(topic)로 연결."""
        article_title = article.get("title", "").lower()
        article_content = article.get("content", "").lower()

        amended_laws = {normalize_law_name(a.get("law_name", "")) for a in amendments}

        for mapping in self.mappings:
            mapped_law = normalize_law_name(mapping.get("law", ""))
            if mapped_law not in amended_laws:
                continue

            topic = mapping.get("rule_topic", "").lower()
            if not topic:
                continue

            if topic not in article_title and topic not in article_content:
                continue

            amendment = next(
                (
                    amended
                    for amended in amendments
                    if normalize_law_name(amended.get("law_name", "")) == mapped_law
                ),
                None,
            )
            if not amendment:
                continue

            return {
                "law_name": amendment.get("law_name", mapping.get("law", "")),
                "law_articles": ", ".join(mapping.get("articles", [])),
                "effective_date": amendment.get("effective_date", ""),
                "reason": (
                    f"{amendment.get('law_name', mapping.get('law', ''))} "
                    f"{mapping.get('description', '')} 관련 개정"
                ),
            }

        return None

    @staticmethod
    def _compose_reference(article: str, paragraph: str = "", item: str = "") -> str:
        return f"{article}{paragraph}{item}".strip()

    def _normalize_reference(self, law_ref: dict) -> Optional[dict]:
        source = law_ref.get("reference") or self._compose_reference(
            law_ref.get("article", ""),
            law_ref.get("paragraph", ""),
            law_ref.get("item", ""),
        )
        return normalize_article_reference(source)

    def _normalize_changed_article(self, changed_article) -> Optional[dict]:
        if isinstance(changed_article, dict):
            source = changed_article.get("reference") or self._compose_reference(
                changed_article.get("article", ""),
                changed_article.get("paragraph", ""),
                changed_article.get("item", ""),
            )
        else:
            source = str(changed_article)
        return normalize_article_reference(source)

    @staticmethod
    def _is_reference_match(reference: dict, changed: dict) -> bool:
        if reference["article"] != changed["article"]:
            return False

        ref_paragraph = reference.get("paragraph", "")
        changed_paragraph = changed.get("paragraph", "")
        if ref_paragraph and changed_paragraph and ref_paragraph != changed_paragraph:
            return False

        ref_item = reference.get("item", "")
        changed_item = changed.get("item", "")
        if ref_item and changed_item and ref_item != changed_item:
            return False

        return True
