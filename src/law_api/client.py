"""
국가법령정보 API 클라이언트

API 소스:
- 공공데이터포털: https://apis.data.go.kr/1170000/law (검색)
- 국가법령정보 공동활용: http://www.law.go.kr/DRF/ (조문 상세)
"""
import os
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, date
from urllib.parse import quote

import requests
from lxml import etree
from dotenv import load_dotenv

load_dotenv()


class LawAPIClient:
    """국가법령정보 API 클라이언트"""

    # 공공데이터포털 (법령 검색)
    DATA_GO_KR_URL = "https://apis.data.go.kr/1170000/law/lawSearchList.do"
    # 국가법령정보 공동활용 (조문 상세 조회)
    LAW_GO_KR_URL = "http://www.law.go.kr/DRF/lawService.do"

    def __init__(self, cache_dir: str = "data/law_cache"):
        self.oc = os.getenv("LAW_API_ID", "")
        self.service_key = os.getenv("DATA_GO_KR_KEY", "")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not self.service_key:
            print("[WARN] DATA_GO_KR_KEY가 설정되지 않았습니다.")

        # 추적 대상 법령 로드
        config_path = Path("config/tracked_laws.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {"laws": []}

    def search_law(self, query: str, exact: bool = True) -> list[dict]:
        """법령 검색 (공공데이터포털)

        Args:
            query: 법령명 (예: "근로기준법")
            exact: 정확한 법령명 매칭 여부

        Returns:
            검색 결과 리스트
        """
        # serviceKey를 URL에 직접 삽입 (이중 인코딩 방지)
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
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            root = etree.fromstring(resp.content)

            # 에러 체크
            result_code = root.findtext("resultCode", "")
            if result_code and result_code != "00":
                print(f"[ERROR] API 오류: {root.findtext('resultMsg', '')}")
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

        except etree.XMLSyntaxError as e:
            print(f"[ERROR] XML 파싱 실패 (API 응답이 XML이 아닙니다): {e}")
            return []
        except requests.RequestException as e:
            print(f"[ERROR] API 호출 실패: {e}")
            return []

    def get_law_detail(self, mst: str) -> Optional[dict]:
        """법령 본문 조회 - 조문 단위 (law.go.kr 공동활용)

        Args:
            mst: 법령일련번호

        Returns:
            법령 상세 정보 (조문 포함), law.go.kr 미승인 시 None
        """
        # 캐시 확인
        cache_file = self.cache_dir / f"law_{mst}.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                cached_date = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
                if (datetime.now() - cached_date).days < 7:
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
            resp = requests.get(self.LAW_GO_KR_URL, params=params, timeout=30)
            resp.raise_for_status()

            # HTML 응답이면 OC 미승인
            if not resp.text.strip().startswith("<?xml"):
                print("[WARN] law.go.kr OC 승인 대기 중 - 조문 상세 조회 불가")
                return None

            from src.law_api.parser import LawXMLParser
            parser = LawXMLParser()
            law_data = parser.parse_law_detail(resp.content)

            if law_data:
                law_data["cached_at"] = datetime.now().isoformat()
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(law_data, f, ensure_ascii=False, indent=2)

            return law_data

        except requests.RequestException as e:
            print(f"[ERROR] 법령 본문 조회 실패: {e}")
            return None

    def check_amendments(
        self,
        law_names: Optional[list[str]] = None,
        since: Optional[str] = None,
    ) -> list[dict]:
        """법령 개정사항 확인

        Args:
            law_names: 확인할 법령명 리스트 (None이면 config의 전체 법령)
            since: 기준일 (YYYY-MM-DD, None이면 올해 1월 1일)

        Returns:
            변경사항 리스트
        """
        if since is None:
            since = f"{date.today().year}-01-01"
        since_compact = since.replace("-", "")

        # 추적 대상 법령 결정
        if law_names:
            target_laws = [
                law for law in self.config.get("laws", [])
                if law["name"] in law_names
            ]
            config_names = [law["name"] for law in target_laws]
            for name in law_names:
                if name not in config_names:
                    target_laws.append({"name": name, "mst": ""})
        else:
            target_laws = self.config.get("laws", [])

        amendments = []

        for law_info in target_laws:
            law_name = law_info["name"]
            print(f"  >> {law_name} 확인 중...")

            results = self.search_law(law_name)

            if not results:
                print(f"     [WARN] 검색 결과 없음")
                continue

            for result in results:
                effective_date = result.get("effective_date", "")

                if effective_date and effective_date >= since_compact:
                    mst = result.get("law_mst", law_info.get("mst", ""))
                    detail = self.get_law_detail(mst) if mst else None

                    amendments.append({
                        "law_name": law_name,
                        "effective_date": effective_date,
                        "promulgation_date": result.get("promulgation_date", ""),
                        "amendment_type": result.get("amendment_type", ""),
                        "law_mst": mst,
                        "changed_articles": detail.get("changed_articles", []) if detail else [],
                        "priority": law_info.get("priority", "medium"),
                    })

        return amendments

    @staticmethod
    def _cdata_text(elem, tag: str) -> str:
        """CDATA 포함 XML 텍스트 추출"""
        found = elem.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        return ""


if __name__ == "__main__":
    client = LawAPIClient()
    results = client.search_law("근로기준법", exact=False)
    for r in results:
        print(f"{r['law_name']} ({r['law_type']}, {r['amendment_type']}, 시행: {r['effective_date']})")
