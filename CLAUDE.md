# 취업규칙 자동 변경 시스템 (Work Rules Updater)

법령 개정사항을 자동 추적하여 회사 취업규칙 수정안 + 신구조문 대조표를 생성하는 노무사 실무 자동화 도구

---
## 행동 규칙 (Behavioral Guidelines)

LLM 코딩 실수를 줄이기 위한 행동 지침.
Tradeoff: 속도보다 신중함. 사소한 작업은 판단에 맡긴다.

### 1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
- **Never silently switch approaches** — if your plan changes, explain the pivot.

### 2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated issues, don't fix them — report with `[Observation]` at end of response.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

**If your fix needs a fix, STOP.** Rollback and try an alternative approach, or ask for guidance.

---

## 자동 실행 규칙

- 파일 읽기/쓰기/수정, Python 실행 — 확인 없이 자동 실행
- Git 작업 (add, commit, push) — 요청 시 자동 실행
- 에러 발생 시 → 자동 수정 시도
- 작업 완료 시: 실행 → 자체 검토 → 개선 → 요약 및 다음 단계 제안


## 현재 상태 (2026-02-14)

| 항목 | 값 |
|------|-----|
| 레벨 | Phase 1 진행 중 |
| 다음 작업 | Phase 1 완료 후 Phase 2: 취업규칙 파싱 |
| API 상태 | 공공데이터포털 검색 OK / law.go.kr 조문상세 OC 승인 대기 |

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

공공데이터포털 (주 API - 검색용):
- URL: https://apis.data.go.kr/1170000/law/lawSearchList.do
- 인증: ServiceKey (인코딩키를 URL에 직접 삽입, 이중 인코딩 방지)
- 제공: 법령 목록 검색만 (조문 상세 없음)
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
- [x] API 클라이언트 구현 (공공데이터포털 검색)
- [ ] XML 파싱 → 조문 구조화 (law.go.kr OC 승인 후)
- [ ] 법령 개정 이력 조회 및 비교
- [x] 로컬 캐시 (불필요한 API 호출 방지)

### Phase 2: 취업규칙 파싱
- [x] .docx 파싱 (python-docx)
- [x] .hwpx 파싱 (ZIP+XML 직접 파싱)
- [x] 조문 번호 자동 인식 (정규식)
- [x] 법령 참조 조항 추출
- [ ] 표준취업규칙 파싱

### Phase 3: 매칭 & 수정안 생성
- [ ] 법령 변경 ↔ 취업규칙 조문 매칭
- [ ] 수정안 초안 생성 (AI)
- [ ] 변경 사유 자동 기재

### Phase 4: 산출물 생성
- [ ] 신구조문 대조표 (.xlsx, openpyxl)
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
- 입력: .docx, .hwpx 지원
- 출력: 신구조문 대조표 .xlsx / 수정 취업규칙 .docx
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
