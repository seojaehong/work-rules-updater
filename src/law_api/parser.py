"""
국가법령정보 XML 응답 파서

법령 본문 XML을 조문 단위로 구조화합니다.
"""
from typing import Optional
from lxml import etree


class LawXMLParser:
    """법령 XML 파서"""

    def parse_law_detail(self, xml_content: bytes) -> Optional[dict]:
        """법령 본문 XML 파싱

        Args:
            xml_content: XML 바이트 문자열

        Returns:
            구조화된 법령 데이터
        """
        try:
            root = etree.fromstring(xml_content)
        except etree.XMLSyntaxError as e:
            print(f"❌ XML 파싱 오류: {e}")
            return None

        law_data = {
            "law_name": self._find_text(root, ".//법령명_한글"),
            "law_id": self._find_text(root, ".//법령ID") or self._find_text(root, ".//법령일련번호"),
            "promulgation_date": self._find_text(root, ".//공포일자"),
            "effective_date": self._find_text(root, ".//시행일자"),
            "articles": [],
            "changed_articles": [],
        }

        # 조문 파싱
        for article_elem in root.findall(".//조문단위"):
            article = self._parse_article(article_elem)
            if article:
                law_data["articles"].append(article)

        return law_data

    def _parse_article(self, elem) -> Optional[dict]:
        """개별 조문 파싱"""
        article_num = self._find_text(elem, "조문번호")
        if not article_num:
            return None

        article = {
            "number": article_num,
            "title": self._find_text(elem, "조문제목") or "",
            "content": self._find_text(elem, "조문내용") or "",
            "paragraphs": [],
        }

        # 항 파싱
        for para_elem in elem.findall(".//항"):
            para = {
                "number": self._find_text(para_elem, "항번호") or "",
                "content": self._find_text(para_elem, "항내용") or "",
                "subparagraphs": [],
            }

            # 호 파싱
            for sub_elem in para_elem.findall(".//호"):
                sub = {
                    "number": self._find_text(sub_elem, "호번호") or "",
                    "content": self._find_text(sub_elem, "호내용") or "",
                }
                para["subparagraphs"].append(sub)

            article["paragraphs"].append(para)

        return article

    def parse_amendment_info(self, xml_content: bytes) -> list[dict]:
        """개정 이력 파싱

        Returns:
            개정 이력 리스트
        """
        try:
            root = etree.fromstring(xml_content)
        except etree.XMLSyntaxError:
            return []

        amendments = []
        for item in root.findall(".//개정문단위"):
            amendment = {
                "date": self._find_text(item, "공포일자") or "",
                "type": self._find_text(item, "개정구분명") or "",
                "reason": self._find_text(item, "제개정이유") or "",
                "summary": self._find_text(item, "개정문내용") or "",
            }
            amendments.append(amendment)

        return amendments

    @staticmethod
    def _find_text(elem, path: str) -> Optional[str]:
        """XML 요소에서 텍스트 추출"""
        found = elem.find(path)
        if found is not None and found.text:
            return found.text.strip()
        return None
