"""
법령 신구 비교 모듈

동일 법령의 두 시점 조문을 비교하여 변경사항을 추출합니다.
"""

from __future__ import annotations

from difflib import unified_diff


class LawDiff:
    """법령 신구 비교"""

    def compare_articles(
        self,
        old_articles: list[dict],
        new_articles: list[dict],
    ) -> list[dict]:
        """조문 단위 비교."""
        changes = []
        old_map = {a["number"]: a for a in old_articles}
        new_map = {a["number"]: a for a in new_articles}
        all_numbers = sorted(set(list(old_map.keys()) + list(new_map.keys())))

        for num in all_numbers:
            old_art = old_map.get(num)
            new_art = new_map.get(num)

            if old_art and not new_art:
                changes.append(
                    {
                        "article_number": num,
                        "change_type": "deleted",
                        "old_content": old_art.get("content", ""),
                        "new_content": "",
                        "title": old_art.get("title", ""),
                    }
                )
                continue

            if not old_art and new_art:
                changes.append(
                    {
                        "article_number": num,
                        "change_type": "added",
                        "old_content": "",
                        "new_content": new_art.get("content", ""),
                        "title": new_art.get("title", ""),
                    }
                )
                continue

            if not old_art or not new_art:
                continue

            old_content = self._flatten_article(old_art)
            new_content = self._flatten_article(new_art)
            if old_content == new_content:
                continue

            changes.append(
                {
                    "article_number": num,
                    "change_type": "modified",
                    "old_content": old_content,
                    "new_content": new_content,
                    "title": new_art.get("title", ""),
                    "diff": self._generate_diff(old_content, new_content),
                }
            )

        return changes

    def _flatten_article(self, article: dict) -> str:
        parts = [article.get("content", "")]

        for para in article.get("paragraphs", []):
            para_num = para.get("number", "")
            para_content = para.get("content", "")
            if para_num:
                parts.append(f"② {para_content}" if para_num == "2" else f"{para_content}")
            else:
                parts.append(para_content)

            for sub in para.get("subparagraphs", []):
                sub_num = sub.get("number", "")
                sub_content = sub.get("content", "")
                parts.append(f"  {sub_num}. {sub_content}")

        return "\n".join(parts)

    def _generate_diff(self, old_text: str, new_text: str) -> str:
        diff = unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="현행",
            tofile="개정",
            lineterm="",
        )
        return "\n".join(diff)
