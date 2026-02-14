"""
취업규칙 파서

Word(.docx) 및 한글(.hwpx) 문서로 된 취업규칙을 조문 단위로 파싱합니다.
.hwpx는 ZIP+XML(OWPML) 형식으로, 직접 파싱합니다.
"""
import re
import zipfile
from pathlib import Path
from typing import Optional

from docx import Document
from lxml import etree


class WorkRulesParser:
    """취업규칙 .docx / .hwpx 파서"""

    SUPPORTED_FORMATS = {".docx", ".hwpx"}

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
        """취업규칙 파일을 조문 단위로 파싱

        Args:
            file_path: .docx 또는 .hwpx 파일 경로

        Returns:
            조문 리스트 [{number, title, content, paragraphs, law_references}]
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"지원하지 않는 파일 형식: {suffix} ({', '.join(self.SUPPORTED_FORMATS)} 지원)"
            )

        if suffix == ".hwpx":
            return self._parse_hwpx(path)

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

    def _parse_hwpx(self, path: Path) -> list[dict]:
        """.hwpx 파일 파싱 (ZIP+XML/OWPML 형식)

        .hwpx 구조:
        - Contents/section0.xml ~ sectionN.xml: 본문 내용
        - hp: 네임스페이스 (http://www.hancom.co.kr/hwpml/2011/paragraph)
        """
        HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
        HT_NS = "http://www.hancom.co.kr/hwpml/2011/text"

        texts: list[str] = []

        with zipfile.ZipFile(path, "r") as zf:
            # section 파일들 찾기 (section0.xml, section1.xml, ...)
            section_files = sorted(
                name for name in zf.namelist()
                if name.startswith("Contents/section") and name.endswith(".xml")
            )

            if not section_files:
                raise ValueError(f".hwpx 파일에서 섹션을 찾을 수 없습니다: {path}")

            for section_file in section_files:
                xml_bytes = zf.read(section_file)
                root = etree.fromstring(xml_bytes)

                # 모든 텍스트 노드에서 텍스트 추출
                # <hp:p> 요소가 문단, 내부의 <hp:t> 또는 <ht:t>가 텍스트
                for p_elem in root.iter(f"{{{HP_NS}}}p"):
                    para_texts = []
                    for t_elem in p_elem.iter():
                        if t_elem.tag in (f"{{{HP_NS}}}t", f"{{{HT_NS}}}t") and t_elem.text:
                            para_texts.append(t_elem.text)
                    line = "".join(para_texts).strip()
                    if line:
                        texts.append(line)

        # 추출된 텍스트를 조문으로 구조화 (docx와 동일 로직)
        articles = []
        current_article = None

        for text in texts:
            article_info = self._match_article(text)

            if article_info:
                if current_article:
                    current_article["law_references"] = self._extract_law_references(
                        current_article["content"]
                    )
                    articles.append(current_article)

                current_article = {
                    "number": article_info["number"],
                    "title": article_info.get("title", ""),
                    "content": text,
                    "full_text": text,
                    "paragraphs": [],
                    "law_references": [],
                }
            elif current_article:
                current_article["full_text"] += "\n" + text

                if self.PARAGRAPH_PATTERN.match(text):
                    current_article["paragraphs"].append(text)
                elif self.SUBPARAGRAPH_PATTERN.match(text):
                    current_article["paragraphs"].append(text)
                else:
                    current_article["content"] += "\n" + text

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
