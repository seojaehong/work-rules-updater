# 프로젝트 세팅 가이드

## 1) 클론 및 의존성 설치

```powershell
cd C:\dev
git clone https://github.com/seojaehong/work-rules-updater.git
cd work-rules-updater
pip install -r requirements.txt
copy .env.example .env
```

## 2) 환경 변수 설정

`.env`에서 아래 값을 채우세요.

- `DATA_GO_KR_KEY`
- `LAW_API_ID` (조문 상세 조회 시)
- `HWPX_TEMPLATE_PATH` (선택)

## 3) 입력 파일 준비

`data/company_rules/` 경로에 회사 취업규칙 파일을 넣으세요.

지원 형식:

- `.docx`
- `.hwpx`

예시:

- `data/company_rules/취업규칙.docx`

## 4) 사전 점검

```powershell
python main.py doctor
```

## 5) 실행

```powershell
python main.py check-updates
python main.py parse-rules data/company_rules/취업규칙.docx
python main.py match data/company_rules/취업규칙.docx
python main.py diagnose-match data/company_rules/취업규칙.docx -o output/diagnostics/match_diagnosis.json
python main.py generate-table data/company_rules/취업규칙.docx -o output/

# API 장애 시 오프라인 개정 JSON 사용
python main.py match data/company_rules/취업규칙.docx --amendments-file data/offline/amendments.json
python main.py diagnose-match data/company_rules/취업규칙.docx --amendments-file data/offline/amendments.json -o output/diagnostics/match_diagnosis.json
python main.py generate-table data/company_rules/취업규칙.docx --amendments-file data/offline/amendments.json -o output/
```

## 6) 검증

```powershell
python evals/smoke_test.py
python scripts/run_rubric_smoke.py
```
