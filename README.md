# 취업규칙 자동 변경 시스템 (Work Rules Updater)

법령 개정사항을 자동 추적하여 **취업규칙 수정안**과 **신구조문 대조표**를 생성하는 노무사 실무 자동화 도구

## 주요 기능

- 🔍 **법령 개정 자동 추적**: 국가법령정보센터 Open API 연동
- 📄 **취업규칙 자동 파싱**: `.docx`, `.hwpx`를 조문 단위로 분석
- 🔗 **자동 매칭**: 개정 법령 ↔ 영향받는 취업규칙 조문 연결
- 📊 **산출물 파이프라인**: `json/xlsx/hwpx` 생성 모듈화
- 🧪 **루브릭 평가**: smoke eval + PR GitHub Actions 게이트

## 설치

```bash
git clone https://github.com/seojaehong/work-rules-updater.git
cd work-rules-updater
pip install -r requirements.txt
cp .env.example .env  # API 키 설정
```

## 사용법

```bash
# 법령 개정사항 확인
python main.py check-updates

# 취업규칙 파싱
python main.py parse-rules data/company_rules/취업규칙.docx

# 매칭 분석
python main.py match data/company_rules/취업규칙.docx

# 신구조문 대조표 생성
python main.py generate-table data/company_rules/취업규칙.docx

# HWPX까지 생성 (템플릿 지정)
python main.py generate-table data/company_rules/취업규칙.docx --hwpx-template templates/base.hwpx

# smoke eval 실행
python scripts/run_rubric_smoke.py
```

## 환경 설정

국가법령정보센터 회원가입 후 `.env` 파일에 ID를 설정하세요:

```
LAW_API_ID=your_id
DATA_GO_KR_KEY=your_service_key
HWPX_TEMPLATE_PATH=templates/base.hwpx
```

## src 구조 (리팩터링)

```
src/
├── ingestion/
│   ├── law_client.py
│   ├── law_parser.py
│   ├── law_diff.py
│   ├── law_reference.py
│   └── rules_parser.py
├── matching/
│   ├── matcher.py
│   └── updater.py
├── outputs/
│   ├── pipeline.py
│   ├── json_output.py
│   ├── xlsx_output.py
│   └── hwpx_output.py
└── evals/
    └── rubric.py
```

## License

Private - 상업적 사용 금지
