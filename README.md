# 취업규칙 자동 변경 시스템 (Work Rules Updater)

법령 개정사항을 추적하여 취업규칙 변경 검토안과 신구조문 대조표를 생성하는 CLI 도구입니다.

## 주요 기능

- 법령 개정 조회 (`check-updates`)
- 취업규칙 파싱 (`.docx`, `.hwpx`)
- 법령 변경사항 ↔ 취업규칙 조문 매칭
- 산출물 생성 (`json`, `xlsx`, `hwpx`)
- 수정안 초안 생성 (`draft_revisions.json`)
- smoke/rubric 기반 기본 검증

## 설치

```bash
git clone https://github.com/seojaehong/work-rules-updater.git
cd work-rules-updater
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
copy .env.example .env
```

## 시작 전 점검

```bash
python main.py doctor
```

`doctor`는 아래 항목을 확인합니다.

- `DATA_GO_KR_KEY`, `LAW_API_ID` 설정 여부
- `data/company_rules/` 입력 파일 존재 여부
- `HWPX_TEMPLATE_PATH` 템플릿 존재 여부

## 사용법

입력 파일(`.docx` 또는 `.hwpx`)은 저장소에 포함되지 않으므로 직접 준비해야 합니다.
예: `data/company_rules/취업규칙.docx`

```bash
# 법령 개정사항 확인
python main.py check-updates

# 취업규칙 파싱
python main.py parse-rules data/company_rules/취업규칙.docx

# 매칭 분석
python main.py match data/company_rules/취업규칙.docx

# 오프라인 개정 데이터(JSON) 기반 매칭 분석
python main.py match data/company_rules/취업규칙.docx --amendments-file data/offline/amendments.json

# 매칭 실패 원인 진단 리포트 생성
python main.py diagnose-match data/company_rules/취업규칙.docx -o output/diagnostics/match_diagnosis.json

# 오프라인 개정 데이터(JSON) 기반 진단
python main.py diagnose-match data/company_rules/취업규칙.docx --amendments-file data/offline/amendments.json -o output/diagnostics/match_diagnosis.json

# 신구조문 대조표 생성
python main.py generate-table data/company_rules/취업규칙.docx -o output/

# 오프라인 개정 데이터(JSON) 기반 대조표 생성
python main.py generate-table data/company_rules/취업규칙.docx --amendments-file data/offline/amendments.json -o output/

# HWPX까지 생성 (템플릿 지정)
python main.py generate-table data/company_rules/취업규칙.docx --hwpx-template templates/base.hwpx

# smoke eval 실행
python scripts/run_rubric_smoke.py
```

## 환경 변수

`.env` 예시:

```
LAW_API_ID=your_law_go_kr_id
DATA_GO_KR_KEY=your_service_key
HWPX_TEMPLATE_PATH=templates/base.hwpx
```

주의:

- `data/company_rules/`, `data/law_cache/`, `output/`은 기본적으로 git ignore 대상입니다.
- API 조회 실패 시 매칭은 폴백 모드(`match_type=fallback`)로 검토 후보를 생성할 수 있습니다.
- `LawAPIClient`는 조회 실패 요약을 `data/law_cache/failures/`에 자동 저장하며, `data/law_cache/amendments_snapshot_latest.json` 스냅샷이 있으면 자동 복구를 시도합니다.
- API 장애 시 품질 검증은 `--amendments-file` 옵션으로 오프라인 개정 JSON을 지정해 수행할 수 있습니다.

## src 구조

```
src/
├── ingestion/
├── matching/
├── outputs/
├── evals/
├── law_api/   (호환 래퍼)
├── rules/     (호환 래퍼)
└── output/    (호환 래퍼)
```

## License

Private - 상업적 사용 금지
