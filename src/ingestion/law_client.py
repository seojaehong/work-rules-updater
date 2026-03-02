"""
국가법령정보 API 클라이언트

API 소스:
- 공공데이터포털: https://apis.data.go.kr/1170000/law (검색)
- 국가법령정보 공동활용: http://www.law.go.kr/DRF/ (조문 상세)
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from lxml import etree

from src.ingestion.law_reference import normalize_law_name

load_dotenv()


class LawAPIClient:
    """국가법령정보 API 클라이언트"""

    DATA_GO_KR_URL = "https://apis.data.go.kr/1170000/law/lawSearchList.do"
    LAW_GO_KR_URL = "http://www.law.go.kr/DRF/lawService.do"

    def __init__(self, cache_dir: str = "data/law_cache"):
        self.oc = os.getenv("LAW_API_ID", "")
        self.service_key = os.getenv("DATA_GO_KR_KEY", "")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_file = self.cache_dir / "amendments_snapshot_latest.json"
        self.failure_dir = self.cache_dir / "failures"
        self.failure_dir.mkdir(parents=True, exist_ok=True)

        if not self.service_key:
            print("[WARN] DATA_GO_KR_KEY가 설정되지 않았습니다.")

        config_path = Path("config/tracked_laws.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as file:
                self.config = json.load(file)
        else:
            self.config = {"laws": []}

        self._last_search_error: str | None = None
        self.last_check_report: dict = {}

    def search_law(self, query: str, exact: bool = True) -> list[dict]:
        """법령 검색 (공공데이터포털)."""
        self._last_search_error = None
        query_encoded = quote(query, safe="")
        url = (
            f"{self.DATA_GO_KR_URL}"
            f"?serviceKey={self.service_key}"
            f"&target=law"
            f"&query={query_encoded}"
            f"&numOfRows=20"
            f"&pageNo=1"
        )

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            body = response.text or ""
            if self._looks_like_html_challenge(body):
                self._last_search_error = (
                    "API 응답이 XML이 아니라 HTML(JavaScript challenge)입니다. "
                    "네트워크/게이트웨이 정책 또는 API 경로 상태를 확인하세요."
                )
                print(f"[ERROR] {self._last_search_error}")
                return []

            try:
                root = etree.fromstring(response.content)
            except etree.XMLSyntaxError as exc:
                content_type = response.headers.get("content-type", "")
                snippet = re.sub(r"\s+", " ", body[:160])
                self._last_search_error = (
                    "XML 파싱 실패: "
                    f"content-type={content_type or '-'}, body={snippet or '-'}"
                )
                print(f"[ERROR] XML 파싱 실패 (API 응답이 XML이 아닙니다): {exc}")
                return []

            result_code = root.findtext("resultCode", "")
            if result_code and result_code != "00":
                result_msg = root.findtext("resultMsg", "")
                self._last_search_error = f"API 오류: {result_msg}"
                print(f"[ERROR] {self._last_search_error}")
                return []

            results = []
            for item in root.findall(".//law"):
                law_data = {
                    "law_id": self._cdata_text(item, "법령일련번호"),
                    "law_name": self._cdata_text(item, "법령명한글"),
                    "law_name_short": self._cdata_text(item, "법령약칭명"),
                    "law_mst": self._cdata_text(item, "법령일련번호"),
                    "law_code": self._cdata_text(item, "법령ID"),
                    "promulgation_date": self._cdata_text(item, "공포일자"),
                    "effective_date": self._cdata_text(item, "시행일자"),
                    "law_type": self._cdata_text(item, "법령구분명"),
                    "amendment_type": self._cdata_text(item, "제개정구분명"),
                    "department": self._cdata_text(item, "소관부처명"),
                    "current_status": self._cdata_text(item, "현행연혁코드"),
                    "link": self._cdata_text(item, "법령상세링크"),
                }

                if exact and law_data["law_name"] != query:
                    continue
                results.append(law_data)

            return results

        except requests.RequestException as exc:
            sanitized = self._sanitize_error_message(str(exc))
            self._last_search_error = sanitized
            print(f"[ERROR] API 호출 실패: {sanitized}")
            return []

    def get_law_detail(self, mst: str) -> Optional[dict]:
        """법령 본문 조회 - 조문 단위."""
        cache_file = self.cache_dir / f"law_{mst}.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as file:
                cached = json.load(file)
            cached_at = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
            if (datetime.now() - cached_at).days < 7:
                return cached

        if not self.oc:
            print("[WARN] LAW_API_ID 미설정 - 조문 상세 조회 불가 (검색만 가능)")
            return None

        params = {
            "OC": self.oc,
            "target": "law",
            "MST": mst,
            "type": "XML",
        }

        try:
            response = requests.get(self.LAW_GO_KR_URL, params=params, timeout=30)
            response.raise_for_status()

            if self._looks_like_html_challenge(response.text or ""):
                print("[WARN] law.go.kr 응답이 HTML(JavaScript challenge)입니다. 조문 상세 조회 불가")
                return None

            if not response.text.strip().startswith("<?xml"):
                print("[WARN] law.go.kr OC 승인 대기 중 - 조문 상세 조회 불가")
                return None

            from src.ingestion.law_parser import LawXMLParser

            parser = LawXMLParser()
            law_data = parser.parse_law_detail(response.content)
            if law_data:
                law_data["cached_at"] = datetime.now().isoformat()
                with open(cache_file, "w", encoding="utf-8") as file:
                    json.dump(law_data, file, ensure_ascii=False, indent=2)
            return law_data

        except requests.RequestException as exc:
            sanitized = self._sanitize_error_message(str(exc))
            print(f"[ERROR] 법령 본문 조회 실패: {sanitized}")
            return None

    def check_amendments(
        self,
        law_names: Optional[list[str]] = None,
        since: Optional[str] = None,
    ) -> list[dict]:
        """법령 개정사항 확인."""
        if since is None:
            since = f"{date.today().year}-01-01"
        since_compact = since.replace("-", "")

        if law_names:
            target_laws = [
                law for law in self.config.get("laws", []) if law["name"] in law_names
            ]
            configured_names = {law["name"] for law in target_laws}
            for law_name in law_names:
                if law_name not in configured_names:
                    target_laws.append({"name": law_name, "mst": ""})
        else:
            target_laws = self.config.get("laws", [])

        amendments = []
        errors = []

        for law_info in target_laws:
            law_name = law_info["name"]
            print(f"  >> {law_name} 확인 중...")

            results = self.search_law(law_name)
            if not results:
                print("     [WARN] 검색 결과 없음")
                if self._last_search_error:
                    errors.append(
                        {
                            "law_name": law_name,
                            "stage": "search_law",
                            "error": self._last_search_error,
                        }
                    )
                continue

            for result in results:
                effective_date = result.get("effective_date", "")
                if not effective_date or effective_date < since_compact:
                    continue

                mst = result.get("law_mst", law_info.get("mst", ""))
                detail = self.get_law_detail(mst) if mst else None

                amendments.append(
                    {
                        "law_name": law_name,
                        "effective_date": effective_date,
                        "promulgation_date": result.get("promulgation_date", ""),
                        "amendment_type": result.get("amendment_type", ""),
                        "law_mst": mst,
                        "changed_articles": detail.get("changed_articles", []) if detail else [],
                        "priority": law_info.get("priority", "medium"),
                    }
                )

        failure_summary_file = ""
        snapshot_recovered_laws: list[str] = []

        if errors:
            failure_summary_file = self._write_failure_summary(
                since=since,
                target_laws=target_laws,
                errors=errors,
                amendments=amendments,
            )
            amendments, snapshot_recovered_laws = self._recover_from_snapshot(
                amendments=amendments,
                errors=errors,
            )

        if amendments:
            self._write_amendments_snapshot(
                since=since,
                target_laws=target_laws,
                amendments=amendments,
            )

        unresolved_failed_laws = sorted(
            {
                normalize_law_name(str(err.get("law_name", "")))
                for err in errors
                if str(err.get("law_name", "")).strip()
            }
            - {
                normalize_law_name(str(item.get("law_name", "")))
                for item in amendments
                if str(item.get("law_name", "")).strip()
            }
        )

        snapshot_used = bool(snapshot_recovered_laws)
        self.last_check_report = {
            "status": "degraded" if unresolved_failed_laws else "ok",
            "searched_laws": len(target_laws),
            "failed_laws": len(errors),
            "amendment_count": len(amendments),
            "errors": errors,
            "had_errors": bool(errors),
            "snapshot_used": snapshot_used,
            "snapshot_file": str(self.snapshot_file) if snapshot_used else "",
            "snapshot_recovered_laws": snapshot_recovered_laws,
            "failure_summary_file": failure_summary_file,
            "unresolved_failed_laws": unresolved_failed_laws,
        }

        return amendments

    def _write_amendments_snapshot(
        self,
        *,
        since: str,
        target_laws: list[dict],
        amendments: list[dict],
    ) -> None:
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "since": since,
            "target_laws": [str(law.get("name", "")).strip() for law in target_laws],
            "amendments": amendments,
        }
        try:
            with open(self.snapshot_file, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            print(f"[WARN] 개정 스냅샷 저장 실패: {exc}")

    def _read_amendments_snapshot(self) -> list[dict]:
        if not self.snapshot_file.exists():
            return []

        try:
            with open(self.snapshot_file, "r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, ValueError) as exc:
            print(f"[WARN] 개정 스냅샷 로드 실패: {exc}")
            return []

        if isinstance(payload, dict):
            amendments = payload.get("amendments", [])
        elif isinstance(payload, list):
            amendments = payload
        else:
            return []

        if not isinstance(amendments, list):
            return []
        return amendments

    def _recover_from_snapshot(self, *, amendments: list[dict], errors: list[dict]) -> tuple[list[dict], list[str]]:
        snapshot = self._read_amendments_snapshot()
        if not snapshot:
            return amendments, []

        current = list(amendments)
        existing_laws = {
            normalize_law_name(str(item.get("law_name", "")))
            for item in current
            if str(item.get("law_name", "")).strip()
        }

        snapshot_by_law: dict[str, dict] = {}
        for item in snapshot:
            law_name = normalize_law_name(str(item.get("law_name", "")))
            if law_name and law_name not in snapshot_by_law:
                snapshot_by_law[law_name] = item

        recovered_laws: list[str] = []
        for error in errors:
            law_name = normalize_law_name(str(error.get("law_name", "")))
            if not law_name or law_name in existing_laws:
                continue

            fallback_item = snapshot_by_law.get(law_name)
            if not fallback_item:
                continue

            hydrated = dict(fallback_item)
            hydrated.setdefault("source", "snapshot")
            current.append(hydrated)
            existing_laws.add(law_name)
            recovered_laws.append(law_name)

        if recovered_laws:
            print(
                "[WARN] API 조회 실패 법령을 스냅샷으로 복구합니다: "
                + ", ".join(sorted(recovered_laws))
            )

        return current, sorted(recovered_laws)

    def _write_failure_summary(
        self,
        *,
        since: str,
        target_laws: list[dict],
        errors: list[dict],
        amendments: list[dict],
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.failure_dir / f"amendments_failure_{timestamp}.json"
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "since": since,
            "target_laws": [str(law.get("name", "")).strip() for law in target_laws],
            "failed_law_count": len(errors),
            "errors": errors,
            "api_amendment_count": len(amendments),
        }
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
            return str(path)
        except OSError as exc:
            print(f"[WARN] 실패 요약 저장 실패: {exc}")
            return ""

    @staticmethod
    def _cdata_text(elem, tag: str) -> str:
        found = elem.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        return ""

    @staticmethod
    def _sanitize_error_message(message: str) -> str:
        if not message:
            return ""
        masked = re.sub(r"(serviceKey=)[^&\s]+", r"\1***", message, flags=re.IGNORECASE)
        masked = re.sub(r"(OC=)[^&\s]+", r"\1***", masked, flags=re.IGNORECASE)
        return masked

    @staticmethod
    def _looks_like_html_challenge(body: str) -> bool:
        compact = (body or "").lstrip().lower()
        if compact.startswith("<!doctype html") or compact.startswith("<html"):
            if "location.assign" in compact or "<script" in compact:
                return True
        return False
