"""
취업규칙 조문 수정안 생성

매칭된 법령 변경사항을 반영하여 취업규칙 수정안을 생성합니다.
"""


class RulesUpdater:
    """취업규칙 수정안 생성기"""

    def generate_draft(
        self,
        matches: list[dict],
        original_articles: list[dict],
    ) -> list[dict]:
        """수정안 초안 생성."""
        raise NotImplementedError("Phase 3에서 구현 예정")
