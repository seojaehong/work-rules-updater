"""
취업규칙 파서

Word(.docx) 및 한글(.hwpx) 문서로 된 취업규칙을 조문 단위로 파싱합니다.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Optional

from docx import Document
from lxml import etree

from src.ingestion.law_reference import extract_law_references


class WorkRulesParser:
    """취업규칙 .docx / .hwpx 파서"""

    SUPPORTED_FORMATS = {".docx", ".hwpx"}

    ARTICLE_PATTERNS = [
        re.compile(
            r"^제\s*(?P<article>\d+)\s*조(?:\s*의\s*(?P<sub_article>\d+))?\s*[\(（](?P<title>[^)）]+)[\)）]"
        ),
        re.compile(
            r"^제\s*(?P<article>\d+)\s*조(?:\s*의\s*(?P<sub_article>\d+))?\s+(?P<title>.+)"
        ),
        re.compile(r"^제\s*(?P<article>\d+)\s*조(?:\s*의\s*(?P<sub_article>\d+))?"),
    ]

    SKIP_TITLE_PATTERNS = [
        re.compile(r"^신설필요$"),
        re.compile(r"^현\s*제\s*\d+\s*조"),
    ]

    PARAGRAPH_PATTERN = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*")
    SUBPARAGRAPH_PATTERN = re.compile(r"^\d+\.\s*")

    def parse(self, file_path: str) -> list[dict]:
        """취업규칙 파일을 조문 단위로 파싱."""
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
        lines = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return self._build_articles(lines)

    def _parse_hwpx(self, path: Path) -> list[dict]:
        """`.hwpx` 파일 파싱 (ZIP+XML/OWPML)."""
        hp_ns = "http://www.hancom.co.kr/hwpml/2011/paragraph"
        ht_ns = "http://www.hancom.co.kr/hwpml/2011/text"

        texts: list[str] = []

        with zipfile.ZipFile(path, "r") as zf:
            section_files = sorted(
                name
                for name in zf.namelist()
                if name.startswith("Contents/section") and name.endswith(".xml")
            )

            if not section_files:
                raise ValueError(f".hwpx 파일에서 섹션을 찾을 수 없습니다: {path}")

            for section_file in section_files:
                xml_bytes = zf.read(section_file)
                root = etree.fromstring(xml_bytes)

                for p_elem in root.iter(f"{{{hp_ns}}}p"):
                    para_texts = []
                    for t_elem in p_elem.iter():
                        if t_elem.tag in (f"{{{hp_ns}}}t", f"{{{ht_ns}}}t") and t_elem.text:
                            para_texts.append(t_elem.text)
                    line = "".join(para_texts).strip()
                    if line:
                        texts.append(line)

        return self._build_articles(texts)

    def _build_articles(self, lines: list[str]) -> list[dict]:
        articles = []
        current_article = None
        article_seq = 0

        for text in lines:
            article_info = self._match_article(text)
            if article_info:
                if current_article:
                    current_article["law_references"] = extract_law_references(
                        current_article["content"]
                    )
                    articles.append(current_article)

                if self._is_skippable_article(article_info):
                    current_article = None
                    continue

                article_seq += 1
                current_article = {
                    "uid": str(article_seq),
                    "number": article_info["number"],
                    "title": article_info.get("title", ""),
                    "content": text,
                    "full_text": text,
                    "paragraphs": [],
                    "law_references": [],
                }
                continue

            if not current_article:
                continue

            current_article["full_text"] += "\n" + text
            if self.PARAGRAPH_PATTERN.match(text) or self.SUBPARAGRAPH_PATTERN.match(text):
                current_article["paragraphs"].append(text)
            else:
                current_article["content"] += "\n" + text

        if current_article:
            current_article["law_references"] = extract_law_references(current_article["content"])
            articles.append(current_article)

        return self._deduplicate_articles(articles)

    @staticmethod
    def _deduplicate_articles(articles: list[dict]) -> list[dict]:
        """같은 조문번호/제목이 중복될 때 인용정보가 풍부한 항목을 우선 유지."""
        if not articles:
            return []

        best_by_key: dict[tuple[str, str], dict] = {}
        order: list[tuple[str, str]] = []

        for article in articles:
            key = (
                str(article.get("number", "")).strip(),
                str(article.get("title", "")).strip(),
            )
            score = (
                len(article.get("law_references", []) or []),
                len(str(article.get("content", ""))),
                len(str(article.get("full_text", ""))),
            )

            if key not in best_by_key:
                best_by_key[key] = article
                order.append(key)
                continue

            current = best_by_key[key]
            current_score = (
                len(current.get("law_references", []) or []),
                len(str(current.get("content", ""))),
                len(str(current.get("full_text", ""))),
            )
            if score > current_score:
                best_by_key[key] = article

        deduped: list[dict] = []
        for key in order:
            deduped.append(best_by_key[key])
        return deduped

    def _match_article(self, text: str) -> Optional[dict]:
        for pattern in self.ARTICLE_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue

            article_no = (match.groupdict().get("article") or "").strip()
            sub_article = (match.groupdict().get("sub_article") or "").strip()
            title = (match.groupdict().get("title") or "").strip()

            number = f"{article_no}의{sub_article}" if sub_article else article_no
            result = {"number": number}
            if title:
                result["title"] = title
            return result
        return None

    @classmethod
    def _is_skippable_article(cls, article_info: dict) -> bool:
        title = str(article_info.get("title", "")).strip()
        if not title:
            return False
        return any(pattern.match(title) for pattern in cls.SKIP_TITLE_PATTERNS)
