"""
법령 변경사항 ↔ 취업규칙 매칭 모듈.

매칭 우선순위:
1. 2026 표준취업규칙 조문 매핑(JSON 하드코딩)
2. 직접 매칭: 취업규칙 조문 내 법령 참조
3. canonical 매칭: title_map 기반 정규화+longest-match
4. topic 매칭: 기존 mapping 규칙 (보수적 적용)
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from src.ingestion.law_reference import normalize_article_reference, normalize_law_name


class RulesMatcher:
    """법령-취업규칙 매칭."""

    def __init__(
        self,
        mapping_path: str = "config/law_mapping.json",
        canonical_path: str = "config/canonical_map.json",
        standard_map_path: str = "config/standard_rules_2026_map.json",
        override_path: Optional[str] = None,
    ):
        mapping_file = Path(mapping_path)
        if mapping_file.exists():
            with open(mapping_file, "r", encoding="utf-8") as file:
                mapping_config = json.load(file)
            self.mappings = mapping_config.get("mappings", [])
        else:
            self.mappings = []

        self.match_rules = {
            "normalize": True,
            "longest_match_priority": True,
            "min_similarity": 0.8,
        }

        canonical_config: dict = {}
        canonical_file = Path(canonical_path)
        if canonical_file.exists():
            with open(canonical_file, "r", encoding="utf-8") as file:
                canonical_config = json.load(file)
            self.match_rules.update(canonical_config.get("match_rules", {}))

        standard_config: dict = {}
        standard_file = Path(standard_map_path)
        if standard_file.exists():
            with open(standard_file, "r", encoding="utf-8") as file:
                standard_config = json.load(file)
            self.match_rules.update(standard_config.get("match_rules", {}))

        # Company-specific override: 동일 key는 override가 global을 덮어씀
        standard_articles = dict(standard_config.get("articles", {}))
        if override_path:
            override_file = Path(override_path)
            if override_file.exists():
                with open(override_file, "r", encoding="utf-8") as file:
                    override_config = json.load(file)
                standard_articles.update(override_config.get("articles", {}))

        self.normalize_enabled = bool(self.match_rules.get("normalize", True))
        self.longest_match_priority = bool(self.match_rules.get("longest_match_priority", True))
        self.min_similarity = float(self.match_rules.get("min_similarity", 0.8))

        self.canonical_entries = self._build_canonical_entries(canonical_config.get("title_map", {}))
        self.standard_article_map = self._build_standard_article_map(standard_articles)
        self.last_report: dict = {}

    def find_matches(
        self,
        rule_articles: list[dict],
        since: Optional[str] = None,
        amendments: Optional[list[dict]] = None,
        api_report: Optional[dict] = None,
    ) -> list[dict]:
        """취업규칙 조문과 법령 변경사항 매칭."""
        source = "provided"
        report_data: dict = dict(api_report or {})
        if amendments is not None and report_data:
            source = "api"

        if amendments is None:
            from src.ingestion.law_client import LawAPIClient

            client = LawAPIClient()
            amendments = client.check_amendments(since=since)
            report_data = getattr(client, "last_check_report", {})
            source = "api"

        if not amendments:
            errors = report_data.get("errors", []) if report_data else []
            fallback_matches = self._build_fallback_matches(rule_articles, errors) if errors else []
            self.last_report = self._build_report(
                status="degraded" if errors else "ok",
                source=source,
                amendments=amendments,
                matches=fallback_matches,
                errors=errors,
            )
            return fallback_matches

        matches: list[dict] = []
        existing_keys: set[tuple[str, str, str, str]] = set()

        for article in rule_articles:
            standard = self._find_standard_article_match(article, amendments=amendments)
            if standard:
                self._append_unique(matches, existing_keys, [standard])

            direct = self._find_direct_matches(article, amendments)
            self._append_unique(matches, existing_keys, direct)

            canonical = None
            if not standard:
                canonical = self._find_canonical_match(article, amendments=amendments)
                if canonical:
                    self._append_unique(matches, existing_keys, [canonical])

            if not standard and not direct and not canonical:
                topic_matches = self._find_topic_matches(article, amendments)
                self._append_unique(matches, existing_keys, topic_matches)

        self.last_report = self._build_report(
            status="ok",
            source=source,
            amendments=amendments,
            matches=matches,
            errors=report_data.get("errors", []) if report_data else [],
        )
        return matches

    def _find_standard_article_match(
        self,
        article: dict,
        amendments: Optional[list[dict]] = None,
        failed_laws: Optional[set[str]] = None,
    ) -> Optional[dict]:
        article_no = str(article.get("number", "")).strip()
        if not article_no:
            return None

        title = article.get("title", "")
        candidates = self._select_standard_entry_candidates(article_no, title)
        if not candidates:
            return None

        for candidate in candidates:
            entry = candidate["entry"]
            law_name = entry.get("law", "")
            law_norm = normalize_law_name(law_name)
            law_articles = entry.get("articles", [])
            if not law_name or not law_articles:
                continue

            effective_date = ""
            if amendments is not None:
                amendment = next(
                    (
                        item
                        for item in amendments
                        if normalize_law_name(item.get("law_name", "")) == law_norm
                    ),
                    None,
                )
                if not amendment:
                    continue

                changed = amendment.get("changed_articles", [])
                if changed and not self._has_changed_overlap(law_articles, changed):
                    continue

                law_name = amendment.get("law_name", law_name)
                effective_date = amendment.get("effective_date", "")
            elif failed_laws is not None and failed_laws and law_norm not in failed_laws:
                continue

            matched_alias = candidate.get("matched_alias", "")
            similarity = candidate.get("similarity", 0.0)
            matched_key = candidate.get("key", "")
            articles_text = ", ".join(law_articles)

            return {
                "rule_uid": article.get("uid", ""),
                "rule_article": article_no,
                "rule_title": title,
                "rule_content": article.get("content", "")[:200],
                "law_name": law_name,
                "law_article": articles_text,
                "effective_date": effective_date,
                "match_type": "standard",
                "reason": (
                    f"2026 표준취업규칙 조문 매핑({matched_key}) 기반 매칭"
                    f" (alias={matched_alias}, sim={similarity:.2f})"
                ),
                "match_confidence": round(similarity, 4),
            }

        return None

    def _find_direct_matches(self, article: dict, amendments: list[dict]) -> list[dict]:
        found: list[dict] = []
        for ref in article.get("law_references", []):
            amendment = self._check_direct_match(ref, amendments)
            if not amendment:
                continue

            law_article = ref.get("reference") or self._compose_reference(
                ref.get("article", ""),
                ref.get("paragraph", ""),
                ref.get("item", ""),
            )

            found.append(
                {
                    "rule_uid": article.get("uid", ""),
                    "rule_article": article.get("number", ""),
                    "rule_title": article.get("title", ""),
                    "rule_content": article.get("content", "")[:200],
                    "law_name": amendment.get("law_name", ""),
                    "law_article": law_article,
                    "effective_date": amendment.get("effective_date", ""),
                    "match_type": "direct",
                    "reason": (
                        f"{amendment.get('law_name', '')} {law_article} 개정 "
                        f"(시행일: {amendment.get('effective_date', '-')})"
                    ),
                }
            )
        return found

    def _check_direct_match(self, law_ref: dict, amendments: list[dict]) -> Optional[dict]:
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

    def _find_canonical_match(
        self,
        article: dict,
        amendments: Optional[list[dict]] = None,
        failed_laws: Optional[set[str]] = None,
    ) -> Optional[dict]:
        candidate = self._select_best_canonical_entry(article.get("title", ""))
        if not candidate:
            return None

        law_name = candidate.get("law", "")
        law_norm = normalize_law_name(law_name)
        law_articles = ", ".join(candidate.get("articles", []))

        effective_date = ""
        if amendments is not None:
            amendment = next(
                (
                    item
                    for item in amendments
                    if normalize_law_name(item.get("law_name", "")) == law_norm
                ),
                None,
            )
            if not amendment:
                return None
            law_name = amendment.get("law_name", law_name)
            effective_date = amendment.get("effective_date", "")
        elif failed_laws is not None and failed_laws and law_norm not in failed_laws:
            return None

        similarity = candidate.get("similarity", 0.0)
        matched_alias = candidate.get("matched_alias", "")
        reason = (
            f"{law_name} {law_articles} canonical 매칭"
            f" (alias={matched_alias}, sim={similarity:.2f})"
        )

        return {
            "rule_uid": article.get("uid", ""),
            "rule_article": article.get("number", ""),
            "rule_title": article.get("title", ""),
            "rule_content": article.get("content", "")[:200],
            "law_name": law_name,
            "law_article": law_articles,
            "effective_date": effective_date,
            "match_type": "canonical",
            "reason": reason,
            "match_confidence": round(similarity, 4),
        }

    def _find_topic_matches(self, article: dict, amendments: list[dict]) -> list[dict]:
        """규칙 기반 매칭: title 기준 보수적으로 적용."""
        title_norm = self._normalize_title_key(article.get("title", ""))
        if not title_norm:
            return []

        amended_laws = {normalize_law_name(a.get("law_name", "")) for a in amendments}
        topic_matches: list[dict] = []

        for mapping in self.mappings:
            mapped_law = normalize_law_name(mapping.get("law", ""))
            if mapped_law not in amended_laws:
                continue

            topic_raw = mapping.get("rule_topic", "")
            topic_norm = self._normalize_title_key(topic_raw)
            if not topic_norm:
                continue

            similarity = self._sentence_similarity(article.get("title", ""), topic_raw)
            if similarity < self.min_similarity:
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

            topic_matches.append(
                {
                    "rule_uid": article.get("uid", ""),
                    "rule_article": article.get("number", ""),
                    "rule_title": article.get("title", ""),
                    "rule_content": article.get("content", "")[:200],
                    "law_name": amendment.get("law_name", mapping.get("law", "")),
                    "law_article": ", ".join(mapping.get("articles", [])),
                    "effective_date": amendment.get("effective_date", ""),
                    "match_type": "topic",
                    "reason": (
                        f"{amendment.get('law_name', mapping.get('law', ''))} "
                        f"{mapping.get('description', '')} 관련 개정"
                    ),
                    "match_confidence": round(similarity, 4),
                }
            )

        return topic_matches

    def _build_fallback_matches(self, rule_articles: list[dict], errors: list[dict]) -> list[dict]:
        """API 조회 실패 시 표준조문+직접참조 기반 검토 후보 생성."""
        failed_laws = {
            normalize_law_name(error.get("law_name", ""))
            for error in errors
            if error.get("law_name")
        }

        matches: list[dict] = []
        existing_keys: set[tuple[str, str, str, str]] = set()

        for article in rule_articles:
            standard = self._find_standard_article_match(article, amendments=None, failed_laws=failed_laws)
            if standard:
                standard["match_type"] = "fallback"
                standard["reason"] = f"{standard['law_name']} 조회 실패로 표준조문 매핑 기반 검토 필요"
                self._append_unique(matches, existing_keys, [standard])

            fallback_direct: list[dict] = []
            for ref in article.get("law_references", []):
                law_name = normalize_law_name(ref.get("law", ""))
                if failed_laws and law_name not in failed_laws:
                    continue

                law_article = ref.get("reference") or self._compose_reference(
                    ref.get("article", ""),
                    ref.get("paragraph", ""),
                    ref.get("item", ""),
                )
                fallback_direct.append(
                    {
                        "rule_uid": article.get("uid", ""),
                        "rule_article": article.get("number", ""),
                        "rule_title": article.get("title", ""),
                        "rule_content": article.get("content", "")[:200],
                        "law_name": law_name,
                        "law_article": law_article,
                        "effective_date": "",
                        "match_type": "fallback",
                        "reason": f"{law_name} 개정정보 조회 실패로 검토 필요 (직접 참조 기반)",
                    }
                )

            self._append_unique(matches, existing_keys, fallback_direct)

        return matches

    def _append_unique(
        self,
        sink: list[dict],
        existing_keys: set[tuple[str, str, str, str]],
        candidates: list[dict],
    ) -> None:
        for candidate in candidates:
            rule_uid = str(candidate.get("rule_uid", "")).strip()
            if not rule_uid:
                rule_uid = (
                    f"{str(candidate.get('rule_article', '')).strip()}"
                    f"|{str(candidate.get('rule_title', '')).strip()}"
                )
            key = (
                rule_uid,
                normalize_law_name(candidate.get("law_name", "")),
                str(candidate.get("law_article", "")),
                str(candidate.get("match_type", "")),
            )
            if key in existing_keys:
                continue
            existing_keys.add(key)
            sink.append(candidate)

    def _build_report(
        self,
        status: str,
        source: str,
        amendments: list[dict],
        matches: list[dict],
        errors: list[dict],
    ) -> dict:
        counts = {
            "standard": sum(1 for m in matches if m.get("match_type") == "standard"),
            "direct": sum(1 for m in matches if m.get("match_type") == "direct"),
            "canonical": sum(1 for m in matches if m.get("match_type") == "canonical"),
            "topic": sum(1 for m in matches if m.get("match_type") == "topic"),
            "fallback": sum(1 for m in matches if m.get("match_type") == "fallback"),
        }
        return {
            "status": status,
            "source": source,
            "amendment_count": len(amendments),
            "errors": errors,
            "had_errors": bool(errors),
            "match_count": len(matches),
            "match_type_counts": counts,
            "fallback_count": counts["fallback"],
        }

    def _build_standard_article_map(self, article_map: dict) -> dict[str, dict]:
        built: dict[str, dict] = {}
        for article_no, payload in article_map.items():
            key = str(article_no).strip()
            if not key:
                continue

            law = payload.get("law", "")
            articles = payload.get("articles", [])
            aliases = payload.get("aliases", [])
            title = payload.get("title", "")
            if not law or not articles:
                continue

            normalized_aliases: list[str] = []
            seen_aliases: set[str] = set()
            for alias in [title] + list(aliases):
                alias_norm = self._normalize_title_key(alias)
                if not alias_norm or alias_norm in seen_aliases:
                    continue
                seen_aliases.add(alias_norm)
                normalized_aliases.append(alias)

            built[key] = {
                "key": key,
                "number_hint": self._extract_number_hint(key),
                "title": title,
                "aliases": normalized_aliases,
                "law": law,
                "articles": articles,
            }
        return built

    def _title_matches_standard_entry(self, title: str, entry: dict) -> bool:
        title_norm = self._normalize_title_key(title)
        if not title_norm:
            return True

        candidates = [entry.get("title", "")] + list(entry.get("aliases", []))
        candidates = [item for item in candidates if item]
        if not candidates:
            return True

        best_similarity = max(self._sentence_similarity(title, candidate) for candidate in candidates)
        return best_similarity >= self.min_similarity


    def _select_standard_entry_candidates(self, article_no: str, title: str) -> list[dict]:
        title_norm = self._normalize_title_key(title)
        article_no_int = int(article_no) if article_no.isdigit() else None

        candidates: list[dict] = []
        for key, entry in self.standard_article_map.items():
            aliases = [entry.get("title", "")] + list(entry.get("aliases", []))
            aliases = [alias for alias in aliases if alias]
            if not aliases:
                continue

            best_alias = ""
            best_similarity = 0.0
            for alias in aliases:
                similarity = self._sentence_similarity(title, alias)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_alias = alias

            is_exact_number = key == article_no
            number_hint = entry.get("number_hint")
            is_hint_match = article_no_int is not None and number_hint == article_no_int

            if title_norm:
                if best_similarity < self.min_similarity:
                    continue
            elif not (is_exact_number or is_hint_match):
                continue

            priority = 2 if is_exact_number else 1 if is_hint_match else 0
            alias_len = len(self._normalize_title_key(best_alias))
            candidates.append(
                {
                    "key": key,
                    "entry": entry,
                    "priority": priority,
                    "similarity": best_similarity,
                    "alias_len": alias_len,
                    "matched_alias": best_alias,
                }
            )

        if self.longest_match_priority:
            candidates.sort(
                key=lambda item: (item["priority"], item["alias_len"], item["similarity"]),
                reverse=True,
            )
        else:
            candidates.sort(
                key=lambda item: (item["priority"], item["similarity"], item["alias_len"]),
                reverse=True,
            )

        return candidates

    @staticmethod
    def _extract_number_hint(raw_key: str) -> Optional[int]:
        match = re.match(r"^(?P<num>\d+)", str(raw_key).strip())
        if not match:
            return None
        return int(match.group("num"))

    def _has_changed_overlap(self, mapped_articles: list[str], changed_articles: list) -> bool:
        mapped_norm = [normalize_article_reference(str(item)) for item in mapped_articles]
        mapped_norm = [item for item in mapped_norm if item]
        if not mapped_norm:
            return False

        for changed in changed_articles:
            changed_norm = self._normalize_changed_article(changed)
            if not changed_norm:
                changed_text = re.sub(r"\s+", "", str(changed))
                if any(m["article"] in changed_text for m in mapped_norm):
                    return True
                continue

            for mapped in mapped_norm:
                if self._is_reference_match(mapped, changed_norm):
                    return True

        return False

    def _build_canonical_entries(self, title_map: dict) -> list[dict]:
        entries: list[dict] = []
        for normalized_key, payload in title_map.items():
            law = payload.get("law", "")
            articles = payload.get("articles", [])
            aliases = payload.get("aliases", [])

            raw_aliases = [normalized_key] + [alias for alias in aliases if alias]
            normalized_aliases = []
            seen_aliases: set[str] = set()
            for alias in raw_aliases:
                alias_norm = self._normalize_title_key(alias)
                if not alias_norm or alias_norm in seen_aliases:
                    continue
                seen_aliases.add(alias_norm)
                normalized_aliases.append((alias, alias_norm))

            if not law or not normalized_aliases:
                continue

            entries.append(
                {
                    "key": normalized_key,
                    "law": law,
                    "articles": articles,
                    "aliases": normalized_aliases,
                }
            )

        return entries

    def _select_best_canonical_entry(self, title: str) -> Optional[dict]:
        title_norm = self._normalize_title_key(title)
        if not title_norm:
            return None

        candidates: list[dict] = []
        for entry in self.canonical_entries:
            for alias_raw, alias_norm in entry.get("aliases", []):
                similarity = self._sentence_similarity(title, alias_raw)
                if similarity < self.min_similarity:
                    continue

                priority = 2 if title_norm == alias_norm else 1
                candidates.append(
                    {
                        "entry": entry,
                        "priority": priority,
                        "alias_len": len(alias_norm),
                        "similarity": similarity,
                        "matched_alias": alias_raw,
                    }
                )

        if not candidates:
            return None

        if self.longest_match_priority:
            candidates.sort(
                key=lambda item: (item["priority"], item["alias_len"], item["similarity"]),
                reverse=True,
            )
        else:
            candidates.sort(
                key=lambda item: (item["priority"], item["similarity"], item["alias_len"]),
                reverse=True,
            )

        best = candidates[0]
        return {
            "key": best["entry"].get("key", ""),
            "law": best["entry"].get("law", ""),
            "articles": best["entry"].get("articles", []),
            "matched_alias": best.get("matched_alias", ""),
            "similarity": best.get("similarity", 0.0),
        }

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

    def _normalize_title_key(self, text: str) -> str:
        value = (text or "").strip().lower()
        if not value:
            return ""
        if self.normalize_enabled:
            value = re.sub(r"\([^)]*\)", "", value)
            value = re.sub(r"\[[^\]]*\]", "", value)
            value = re.sub(r"（[^）]*）", "", value)
            value = value.replace("·", "")
            value = value.replace("ㆍ", "")
            value = value.replace(".", "")
            value = re.sub(r"\s+", "", value)
            value = re.sub(r"[^0-9a-z가-힣]", "", value)
        return value

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        return SequenceMatcher(None, left, right).ratio()

    def _sentence_similarity(self, left_raw: str, right_raw: str) -> float:
        left_norm = self._normalize_title_key(left_raw)
        right_norm = self._normalize_title_key(right_raw)
        if not left_norm or not right_norm:
            return 0.0
        if left_norm == right_norm:
            return 1.0

        char_ratio = self._similarity(left_norm, right_norm)
        token_ratio = self._jaccard(self._tokenize(left_raw), self._tokenize(right_raw))
        ngram_ratio = self._jaccard(self._char_ngrams(left_norm), self._char_ngrams(right_norm))

        return (0.5 * char_ratio) + (0.25 * token_ratio) + (0.25 * ngram_ratio)

    def _tokenize(self, text: str) -> set[str]:
        clean = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", (text or "").lower())
        tokens = [token for token in re.split(r"\s+", clean.strip()) if token]
        return set(tokens)

    @staticmethod
    def _char_ngrams(text: str, n_values: tuple[int, ...] = (2, 3)) -> set[str]:
        grams: set[str] = set()
        source = text or ""
        for n in n_values:
            if len(source) < n:
                continue
            for idx in range(len(source) - n + 1):
                grams.add(source[idx : idx + n])
        return grams

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        inter = len(left & right)
        union = len(left | right)
        if union == 0:
            return 0.0
        return inter / union
