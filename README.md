# 취업규칙 자동 변경 시스템 (Work Rules Updater)

법령 개정사항을 자동 추적하여 **취업규칙 수정안**과 **신구조문 대조표**를 생성하는 노무사 실무 자동화 도구

## 주요 기능

- 🔍 **법령 개정 자동 추적**: 국가법령정보센터 Open API 연동
- 📄 **취업규칙 자동 파싱**: .docx 파일을 조문 단위로 분석
- 🔗 **자동 매칭**: 개정 법령 ↔ 영향받는 취업규칙 조문 연결
- 📊 **신구조문 대조표 생성**: 현행/변경/사유를 정리한 .docx 자동 생성

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
```

## 환경 설정

국가법령정보센터 회원가입 후 `.env` 파일에 ID를 설정하세요:

```
LAW_API_ID=your_id
```

## License

Private - 상업적 사용 금지
