"""
국가법령정보센터 Open API 클라이언트

API 문서: https://open.law.go.kr/LSO/openApi/guideResult.do
Base URL: http://www.law.go.kr/DRF/lawSearch.do

인증: OC 파라미터 (법령정보센터 회원 ID)
응답: XML 형식
"""
import os
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime, date

import requests
from lxml import etree
from dotenv import load_dotenv

load_dotenv()


class LawAPIClient:
    """국가법령정보 API 클라이언트"""

    BASE_URL = "http://www.law.go.kr/DRF/lawSearch.do"

    def __init__(self, cache_dir: str = "data/law_cache"):
        self.oc = os.getenv("LAW_API_ID", "")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not self.oc:
            print("⚠️ LAW_API_ID가 설정되지 않았습니다. .env 파일을 확인하세요.")

        # 추적 대상 법령 로드
        config_path = Path("config/tracked_laws.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {"laws": []}

    def search_law(self, query: str, exact: bool = True) -> list[dict]:
        """법령 검색

        Args:
            query: 법령명 (예: "근로기준법")
            exact: 정확한 법령명 매칭 여부

        Returns:
            검색 결과 리스트
        """
        params = {
            "OC": self.oc,
            "target": "law",
            "type": "XML",
            "query": query,
            "display": 20,
        }

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()

            root = etree.fromstring(resp.content)
            total = root.findtext("totalCnt", "0")

            results = []
            for item in root.findall(".//law"):
                law_data = {
                    "law_id": item.findtext("법령일련번호", ""),
                    "law_name": item.findtext("법령명한글", ""),
                    "law_mst": item.findtext("법령MST", ""),
                    "promulgation_date": item.findtext("공포일자", ""),
                    "effective_date": item.findtext("시행일자", ""),
                    "law_type": item.findtext("법령구분명", ""),
                    "department": item.findtext("소관부처명", ""),
                    "link": item.findtext("법령상세링크", ""),
                }

                if exact and law_data["law_name"] != query:
                    continue

                results.append(law_data)

            return results

        except requests.RequestException as e:
            print(f"❌ API 호출 실패: {e}")
            return []

    def get_law_detail(self, mst: str) -> Optional[dict]:
        """법령 본문 조회 (조문 단위)

        Args:
            mst: 법령MST 번호

        Returns:
            법령 상세 정보 (조문 포함)
        """
        # 캐시 확인
        cache_file = self.cache_dir / f"law_{mst}.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                # 캐시가 7일 이내면 사용
                cached_date = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
                if (datetime.now() - cached_date).days < 7:
                    return cached

        params = {
            "OC": self.oc,
            "target": "law",
            "MST": mst,
            "type": "XML",
        }

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()

            from src.law_api.parser import LawXMLParser
            parser = LawXMLParser()
            law_data = parser.parse_law_detail(resp.content)

            if law_data:
                # 캐시 저장
                law_data["cached_at"] = datetime.now().isoformat()
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(law_data, f, ensure_ascii=False, indent=2)

            return law_data

        except requests.RequestException as e:
            print(f"❌ 법령 본문 조회 실패: {e}")
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

        # 추적 대상 법령 결정
        if law_names:
            target_laws = [
                law for law in self.config.get("laws", [])
                if law["name"] in law_names
            ]
            # config에 없는 법령도 추가
            config_names = [law["name"] for law in target_laws]
            for name in law_names:
                if name not in config_names:
                    target_laws.append({"name": name, "mst": ""})
        else:
            target_laws = self.config.get("laws", [])

        amendments = []

        for law_info in target_laws:
            law_name = law_info["name"]
            print(f"  🔍 {law_name} 확인 중...")

            # 법령 검색
            results = self.search_law(law_name)

            if not results:
                print(f"     ⚠️ 검색 결과 없음")
                continue

            for result in results:
                effective_date = result.get("effective_date", "")

                # 시행일이 기준일 이후인지 확인
                if effective_date and effective_date.replace(".", "-") >= since.replace("-", ""):
                    # 상세 조문 조회
                    mst = result.get("law_mst", law_info.get("mst", ""))
                    detail = self.get_law_detail(mst) if mst else None

                    amendments.append({
                        "law_name": law_name,
                        "effective_date": effective_date,
                        "promulgation_date": result.get("promulgation_date", ""),
                        "law_mst": mst,
                        "changed_articles": detail.get("changed_articles", []) if detail else [],
                        "priority": law_info.get("priority", "medium"),
                    })

        return amendments


if __name__ == "__main__":
    client = LawAPIClient()
    results = client.search_law("근로기준법")
    for r in results:
        print(f"{r['law_name']} (시행: {r['effective_date']})")
