"""Law reference extraction and normalization helpers."""

from __future__ import annotations

import re
from typing import Optional

LAW_NAME_ALIASES = {
    "근로기준법": "근로기준법",
    "최저임금법": "최저임금법",
    "남녀고용평등법": "남녀고용평등법",
    "남녀고용평등과일ㆍ가정양립지원에관한법률": "남녀고용평등법",
    "남녀고용평등과일가정양립지원에관한법률": "남녀고용평등법",
    "산업안전보건법": "산업안전보건법",
    "근로자퇴직급여보장법": "근로자퇴직급여보장법",
    "기간제및단시간근로자보호등에관한법률": "기간제및단시간근로자보호법",
    "기간제및단시간근로자보호법": "기간제및단시간근로자보호법",
    "파견근로자보호등에관한법률": "파견근로자보호법",
    "파견근로자보호법": "파견근로자보호법",
    "고용보험법": "고용보험법",
    "산업재해보상보험법": "산업재해보상보험법",
    "노동조합및노동관계조정법": "노동조합법",
    "노동조합법": "노동조합법",
    "고용상연령차별금지및고령자고용촉진에관한법률": "고령자고용법",
    "고령자고용법": "고령자고용법",
    "장애인고용촉진및직업재활법": "장애인고용촉진법",
    "장애인고용촉진법": "장애인고용촉진법",
    "채용절차의공정화에관한법률": "채용절차법",
    "채용절차법": "채용절차법",
}

_LAW_VARIANTS = [
    "남녀고용평등과 일ㆍ가정 양립 지원에 관한 법률",
    "기간제 및 단시간근로자 보호 등에 관한 법률",
    "파견근로자보호 등에 관한 법률",
    "고용상 연령차별금지 및 고령자고용촉진에 관한 법률",
    "채용절차의 공정화에 관한 법률",
    "장애인고용촉진 및 직업재활법",
    "노동조합 및 노동관계조정법",
    "근로자퇴직급여 보장법",
    "남녀고용평등법",
    "근로기준법",
    "최저임금법",
    "산업안전보건법",
    "근로자퇴직급여보장법",
    "기간제및단시간근로자보호법",
    "파견근로자보호법",
    "고용보험법",
    "산업재해보상보험법",
    "노동조합법",
]


def _variant_to_pattern(variant: str) -> str:
    escaped = re.escape(variant)
    return escaped.replace(r"\ ", r"\s*")


LAW_NAME_PATTERN = "|".join(
    _variant_to_pattern(name) for name in sorted(_LAW_VARIANTS, key=len, reverse=True)
)

# Supports: 제43조, 제43조의2, 제43조의2제1항, 제93조제1호
ARTICLE_PATTERN = re.compile(
    r"(?:제)?(?P<article>\d+)조"
    r"(?:의(?P<sub_article>\d+))?"
    r"(?:제(?P<paragraph>\d+)항)?"
    r"(?:제(?P<item>\d+)호)?"
)

ARTICLE_TEXT_PATTERN = re.compile(
    r"제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*제\s*\d+\s*항)?(?:\s*제\s*\d+\s*호)?"
)

LAW_CHAIN_PATTERN = re.compile(
    rf"(?P<law>{LAW_NAME_PATTERN})"
    r"(?P<refs>(?:\s*제\s*\d+\s*조(?:\s*의\s*\d+)?"
    r"(?:\s*제\s*\d+\s*항)?(?:\s*제\s*\d+\s*호)?"
    r"(?:\s*(?:,|및|또는|·)\s*)?)+)"
)


def normalize_law_name(law_name: str) -> str:
    """Normalize aliases to canonical short names."""
    cleaned = re.sub(r"\s+", "", (law_name or ""))
    return LAW_NAME_ALIASES.get(cleaned, law_name.strip())


def normalize_article_reference(reference: str) -> Optional[dict]:
    """Normalize article expression into comparable components."""
    if not reference:
        return None

    compact = re.sub(r"\s+", "", reference)
    match = ARTICLE_PATTERN.search(compact)
    if not match:
        return None

    article = f"제{match.group('article')}조"
    sub_article = match.group("sub_article")
    if sub_article:
        article = f"{article}의{sub_article}"

    paragraph = match.group("paragraph")
    item = match.group("item")

    paragraph_text = f"제{paragraph}항" if paragraph else ""
    item_text = f"제{item}호" if item else ""

    normalized = article + paragraph_text + item_text
    return {
        "article": article,
        "paragraph": paragraph_text,
        "item": item_text,
        "normalized": normalized,
    }


def extract_law_references(text: str) -> list[dict]:
    """Extract law references from rule text."""
    if not text:
        return []

    references: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for match in LAW_CHAIN_PATTERN.finditer(text):
        law = normalize_law_name(match.group("law"))
        refs_text = match.group("refs")

        for ref_match in ARTICLE_TEXT_PATTERN.finditer(refs_text):
            parsed = normalize_article_reference(ref_match.group(0))
            if not parsed:
                continue

            key = (law, parsed["normalized"])
            if key in seen:
                continue
            seen.add(key)

            references.append(
                {
                    "law": law,
                    "article": parsed["article"],
                    "paragraph": parsed["paragraph"],
                    "item": parsed["item"],
                    "reference": parsed["normalized"],
                }
            )

    return references
