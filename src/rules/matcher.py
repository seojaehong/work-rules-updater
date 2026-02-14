"""
법령 변경사항 ↔ 취업규칙 매칭 모듈

법령 개정으로 영향받는 취업규칙 조문을 찾아냅니다.
매칭 방식:
  1. 직접 매칭: 취업규칙 조문 내 법령 참조 → 해당 법령 개정 여부 확인
  2. 규칙 기반 매칭: config/law_mapping.json의 사전 정의 매핑
  3. AI 매칭: 조문 내용 의미 분석 (Phase 3에서 구현)
"""
import json
from pathlib import Path
from typing import Optional


class RulesMatcher:
    """법령-취업규칙 매칭"""

    def __init__(self):
        # 매핑 룰 로드
        mapping_path = Path("config/law_mapping.json")
        if mapping_path.exists():
            with open(mapping_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.mappings = config.get("mappings", [])
        else:
            self.mappings = []

    def find_matches(
        self,
        rule_articles: list[dict],
        since: Optional[str] = None,
    ) -> list[dict]:
        """취업규칙 조문과 법령 변경사항 매칭

        Args:
            rule_articles: 파싱된 취업규칙 조문 리스트
            since: 법령 변경 기준일

        Returns:
            매칭 결과 리스트
        """
        from src.law_api.client import LawAPIClient

        # 1. 법령 변경사항 확인
        client = LawAPIClient()
        amendments = client.check_amendments(since=since)

        if not amendments:
            return []

        matches = []

        for article in rule_articles:
            # 직접 매칭: 조문 내 법령 참조
            for ref in article.get("law_references", []):
                match = self._check_direct_match(ref, amendments)
                if match:
                    matches.append({
                        "rule_article": article["number"],
                        "rule_title": article.get("title", ""),
                        "rule_content": article.get("content", "")[:200],
                        "law_name": match["law_name"],
                        "law_article": ref["article"],
                        "effective_date": match.get("effective_date", ""),
                        "match_type": "direct",
                        "reason": f"{match['law_name']} {ref['article']} 개정 "
                                  f"(시행일: {match.get('effective_date', '-')})",
                    })

            # 규칙 기반 매칭: law_mapping.json
            topic_match = self._check_topic_match(article, amendments)
            if topic_match:
                # 중복 제거 (직접 매칭과 겹치는 경우)
                existing = {(m["rule_article"], m["law_name"]) for m in matches}
                if (article["number"], topic_match["law_name"]) not in existing:
                    matches.append({
                        "rule_article": article["number"],
                        "rule_title": article.get("title", ""),
                        "rule_content": article.get("content", "")[:200],
                        "law_name": topic_match["law_name"],
                        "law_article": topic_match.get("law_articles", ""),
                        "effective_date": topic_match.get("effective_date", ""),
                        "match_type": "topic",
                        "reason": topic_match.get("reason", ""),
                    })

        return matches

    def _check_direct_match(
        self,
        law_ref: dict,
        amendments: list[dict],
    ) -> Optional[dict]:
        """직접 매칭: 취업규칙에서 인용한 법령 조항이 개정되었는지 확인"""
        for amendment in amendments:
            if amendment["law_name"] == law_ref["law"]:
                # 변경된 조문 목록이 있으면 확인
                changed = amendment.get("changed_articles", [])
                if not changed or law_ref["article"] in changed:
                    return amendment
        return None

    def _check_topic_match(
        self,
        article: dict,
        amendments: list[dict],
    ) -> Optional[dict]:
        """규칙 기반 매칭: 주제(topic)로 연결"""
        article_title = article.get("title", "").lower()
        article_content = article.get("content", "").lower()

        amended_laws = {a["law_name"] for a in amendments}

        for mapping in self.mappings:
            if mapping["law"] not in amended_laws:
                continue

            topic = mapping.get("rule_topic", "").lower()
            description = mapping.get("description", "").lower()

            # 조문 제목이나 내용에 주제가 포함되는지 확인
            if topic and (topic in article_title or topic in article_content):
                amendment = next(
                    (a for a in amendments if a["law_name"] == mapping["law"]),
                    None
                )
                if amendment:
                    return {
                        "law_name": mapping["law"],
                        "law_articles": ", ".join(mapping.get("articles", [])),
                        "effective_date": amendment.get("effective_date", ""),
                        "reason": f"{mapping['law']} {mapping.get('description', '')} 관련 개정",
                    }

        return None
