"""
취업규칙 조문 수정안 생성

매칭된 법령 변경사항을 반영하여 취업규칙 수정안 초안을 생성합니다.
"""

from __future__ import annotations

import re


class RulesUpdater:
    """취업규칙 수정안 생성기"""

    def generate_draft(
        self,
        matches: list[dict],
        original_articles: list[dict],
    ) -> list[dict]:
        """매칭 결과를 바탕으로 조문별 수정안 초안을 생성."""
        if not matches:
            return []

        article_map = {str(article.get("number", "")).strip(): article for article in original_articles}
        grouped: dict[str, list[dict]] = {}

        for match in matches:
            article_no = str(match.get("rule_article", "")).strip()
            if not article_no:
                continue
            grouped.setdefault(article_no, []).append(match)

        drafts = []
        for article_no in sorted(grouped.keys(), key=self._article_sort_key):
            source = article_map.get(article_no, {})
            current_text = (
                source.get("full_text")
                or source.get("content")
                or source.get("rule_content")
                or ""
            )
            title = source.get("title", "")
            related_matches = grouped[article_no]

            review_lines = []
            for idx, match in enumerate(related_matches, start=1):
                law_name = match.get("law_name", "")
                law_article = match.get("law_article", "")
                match_type = match.get("match_type", "")
                reason = match.get("reason", "")
                review_lines.append(
                    f"{idx}) {law_name} {law_article} [{match_type}] - {reason}".strip()
                )

            suggestion_header = "[개정 검토 포인트]"
            suggested_text = current_text.strip()
            if suggested_text:
                suggested_text += "\n\n"
            suggested_text += suggestion_header + "\n" + "\n".join(review_lines)

            drafts.append(
                {
                    "rule_article": article_no,
                    "rule_title": title,
                    "current_text": current_text,
                    "suggested_text": suggested_text,
                    "review_points": review_lines,
                    "match_count": len(related_matches),
                    "matches": related_matches,
                }
            )

        return drafts

    @staticmethod
    def _article_sort_key(article_no: str):
        text = (article_no or "").strip()
        match = re.match(r"^(\d+)", text)
        if match:
            return (0, int(match.group(1)), text)
        return (1, 0, text)
