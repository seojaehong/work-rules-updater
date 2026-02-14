# 취업규칙 자동 변경 시스템 (Work Rules Updater)

법령 개정사항을 자동 추적하여 회사 취업규칙 수정안 + 신구조문 대조표를 생성하는 노무사 실무 자동화 도구

---

## 현재 상태 (2026-02-14)

| 항목 | 값 |
|------|-----|
| 레벨 | 초기 셋업 |
| 다음 작업 | Phase 1: 국가법령정보 API 연동 |

---

## 프로젝트 목적

**수작업 프로세스 (현재):**
1. 법령 개정 확인 (국가법령정보센터, 고용노동부 표준취업규칙)
2. 회사 취업규칙과 대조 (눈으로 비교)
3. 해당 조문 수정
4. 신구조문 대조표 작성 (Word)
5. 변경 사유 기재
6. 의견청취 절차 안내

**자동화 목표:**
- 2~5번 과정을 AI + API로 자동화
- 최종 산출물: 수정 취업규칙(.docx) + 신구조문 대조표(.docx) + 변경사항 보고서

---

## 빠른 실행

```bash
# 법령 개정사항 확인
python main.py check-updates --laws 근로기준법,산업안전보건법

# 취업규칙 분석
python main.py parse-rules --input data/company_rules/sample.docx

# 신구조문 대조표 생성
python main.py generate-table --rules data/company_rules/sample.docx --output output/
```

---

## 프로젝트 구조

```
work-rules-updater/
├── CLAUDE.md              # 이 파일 (세션 재개용)
├── main.py                # CLI 진입점 (Click)
├── requirements.txt       # Python 의존성
├── .env                   # API 키 (git 추적 안 함)
├── config/
│   ├── tracked_laws.json  # 추적 대상 법령 목록
│   └── law_mapping.json   # 법령 조항 ↔ 취업규칙 조문 매핑 룰
├── src/
│   ├── law_api/           # 국가법령정보 API 클라이언트
│   │   ├── client.py      # API 호출 (REST, XML 파싱)
│   │   ├── parser.py      # XML → 조문 구조화
│   │   └── diff.py        # 법령 신구 비교
│   ├── rules/             # 취업규칙 처리
│   │   ├── docx_parser.py # .docx 파싱 (조문별 분리)
│   │   ├── matcher.py     # 법령 ↔ 취업규칙 매칭 (AI)
│   │   └── updater.py     # 조문 수정안 생성
│   └── output/            # 산출물 생성
│       ├── comparison_table.py  # 신구조문 대조표 (.docx)
│       └── report.py      # 변경사항 보고서
├── templates/
│   └── 신구조문대조표_템플릿.docx
├── data/
│   ├── company_rules/     # 회사별 취업규칙 원본
│   ├── standard_rules/    # 고용노동부 표준취업규칙
│   └── law_cache/         # 법령 API 응답 캐시
└── output/                # 생성된 결과물
```

---

## 핵심 데이터 흐름

```
[국가법령정보 API] → law_api/client.py → 법령 조문 (구조화 JSON)
                                            ↓
[회사 취업규칙.docx] → rules/docx_parser.py → 조문별 파싱
                                            ↓
                    rules/matcher.py ← AI가 매칭 판단
                    "근기법 제60조 개정 → 취업규칙 제15조 영향"
                                            ↓
                    rules/updater.py → 수정안 생성
                                            ↓
                    output/comparison_table.py → 신구조문 대조표.docx
                    output/report.py → 변경사항 보고서.docx
```

---

## 국가법령정보 API

```
Base URL: http://www.law.go.kr/DRF/lawSearch.do
인증: OC 파라미터 (법령정보센터 회원 ID)

주요 엔드포인트:
- 법령 검색: ?OC={id}&target=law&type=XML&query={법령명}
- 법령 본문: ?OC={id}&target=law&MST={법령일련번호}&type=XML
- 연혁 조회: ?OC={id}&target=law&MST={법령일련번호}&type=XML&efYd={시행일}

공공데이터포털 (대안):
- URL: http://apis.data.go.kr/1170000/law
- 인증: ServiceKey (발급 필요)
```

---

## 추적 대상 법령 (노무사 실무 기준)

### 필수 (취업규칙 직접 영향)
- 근로기준법 / 시행령 / 시행규칙
- 최저임금법
- 남녀고용평등법
- 산업안전보건법
- 근로자퇴직급여보장법
- 기간제및단시간근로자보호법

### 확장 (간접 영향)
- 고용보험법
- 산업재해보상보험법
- 노동조합법
- 직장 내 괴롭힘 관련 (근기법 제76조의2~3)

---

## 환경 설정

```bash
# .env
LAW_API_ID=your_law_go_kr_id          # 국가법령정보센터 회원 ID
DATA_GO_KR_KEY=your_service_key       # 공공데이터포털 서비스 키 (대안)
```

---

## 개발 로드맵

### Phase 1: 국가법령정보 API 연동 (MVP)
- [ ] API 클라이언트 구현 (법령 검색, 본문 조회)
- [ ] XML 파싱 → 조문 구조화 (조/항/호 단위)
- [ ] 법령 개정 이력 조회 및 비교
- [ ] 로컬 캐시 (불필요한 API 호출 방지)

### Phase 2: 취업규칙 파싱
- [ ] .docx 파싱 (python-docx)
- [ ] 조문 번호 자동 인식 (정규식)
- [ ] 법령 참조 조항 추출
- [ ] 표준취업규칙 파싱

### Phase 3: 매칭 & 수정안 생성
- [ ] 법령 변경 ↔ 취업규칙 조문 매칭
- [ ] 수정안 초안 생성 (AI)
- [ ] 변경 사유 자동 기재

### Phase 4: 산출물 생성
- [ ] 신구조문 대조표 (.docx)
- [ ] 수정된 취업규칙 (.docx)
- [ ] 변경사항 요약 보고서

### Phase 5: 고도화
- [ ] 회사별 커스텀 조항 보호 (수정 불가 마킹)
- [ ] 연간 변경 이력 관리
- [ ] 의견청취 안내문 자동 생성

---

## 작업 규칙

### 코드 스타일
- Python 3.11+
- 한글 주석, 영문 변수명
- Type hints 필수
- 독스트링: 한글로 작성

### 파일 처리
- 원본 파일 절대 수정 금지 → output/에만 생성
- .docx 생성 시 A4 기준 (한국 표준)
- 인코딩: UTF-8

### 보안
- API 키는 반드시 .env로 관리
- .gitignore에 .env, data/company_rules/ 포함
- 회사명, 개인정보 마스킹

---

## 작업 재개 시 체크리스트

1. [ ] `git pull` - 최신 코드 확인
2. [ ] `pip install -r requirements.txt` - 의존성 확인
3. [ ] `.env` 파일 확인 (API 키)
4. [ ] 위 "개발 로드맵" 섹션에서 현재 Phase 확인
