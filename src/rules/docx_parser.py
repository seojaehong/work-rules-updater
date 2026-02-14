"""
취업규칙 .docx 파서

Word 문서로 된 취업규칙을 조문 단위로 파싱합니다.
"""
import re
from pathlib import Path
from typing import Optional

from docx import Document


class WorkRulesParser:
    """취업규칙 .docx 파서"""

    # 조문 번호 패턴
    ARTICLE_PATTERNS = [
        # 제1조, 제2조, 제10조 등
        re.compile(r'^제\s*(\d+)\s*조\s*[\(（]([^)）]+)[\)）]'),
        re.compile(r'^제\s*(\d+)\s*조\s+(.+)'),
        re.compile(r'^제\s*(\d+)\s*조'),
    ]

    # 항 번호 패턴
    PARAGRAPH_PATTERN = re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*')

    # 호 번호 패턴
    SUBPARAGRAPH_PATTERN = re.compile(r'^\d+\.\s*')

    def parse(self, file_path: str) -> list[dict]:
        """취업규칙 .docx 파일을 조문 단위로 파싱

        Args:
            file_path: .docx 파일 경로

        Returns:
            조문 리스트 [{number, title, content, paragraphs, law_references}]
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        if path.suffix.lower() != ".docx":
            raise ValueError(f"지원하지 않는 파일 형식: {path.suffix} (.docx만 지원)")

        doc = Document(file_path)
        articles = []
        current_article = None

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # 조문 시작인지 확인
            article_info = self._match_article(text)

            if article_info:
                # 이전 조문 저장
                if current_article:
                    current_article["law_references"] = self._extract_law_references(
                        current_article["content"]
                    )
                    articles.append(current_article)

                # 새 조문 시작
                current_article = {
                    "number": article_info["number"],
                    "title": article_info.get("title", ""),
                    "content": text,
                    "full_text": text,
                    "paragraphs": [],
                    "law_references": [],
                }
            elif current_article:
                # 기존 조문에 내용 추가
                current_article["full_text"] += "\n" + text

                if self.PARAGRAPH_PATTERN.match(text):
                    current_article["paragraphs"].append(text)
                elif self.SUBPARAGRAPH_PATTERN.match(text):
                    current_article["paragraphs"].append(text)
                else:
                    current_article["content"] += "\n" + text

        # 마지막 조문 저장
        if current_article:
            current_article["law_references"] = self._extract_law_references(
                current_article["content"]
            )
            articles.append(current_article)

        return articles

    def _match_article(self, text: str) -> Optional[dict]:
        """조문 번호 매칭"""
        for pattern in self.ARTICLE_PATTERNS:
            match = pattern.match(text)
            if match:
                groups = match.groups()
                result = {"number": groups[0]}
                if len(groups) > 1:
                    result["title"] = groups[1].strip()
                return result
        return None

    def _extract_law_references(self, text: str) -> list[dict]:
        """조문 내 법령 참조 추출

        예: "근로기준법 제60조에 따라" → [{"law": "근로기준법", "article": "제60조"}]
        """
        references = []

        # 법령명 + 조문 패턴
        law_ref_pattern = re.compile(
            r'(근로기준법|최저임금법|남녀고용평등법|산업안전보건법|'
            r'근로자퇴직급여\s*보장법|기간제[^\s]*법|파견[^\s]*법|'
            r'고용보험법|산업재해보상보험법|노동조합[^\s]*법)'
            r'\s*제\s*(\d+)\s*조'
        )

        for match in law_ref_pattern.finditer(text):
            references.append({
                "law": match.group(1),
                "article": f"제{match.group(2)}조",
            })

        return references
