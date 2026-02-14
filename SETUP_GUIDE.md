# 🚀 프로젝트 초기 세팅 가이드

## 1단계: GitHub 레포 생성

GitHub에서 `work-rules-updater` 레포를 **Private**으로 생성하세요.
- Repository name: `work-rules-updater`
- Private 체크
- README, .gitignore 추가하지 않음 (이미 포함되어 있음)

## 2단계: 로컬 세팅

```powershell
# 원하는 위치에 프로젝트 폴더 생성
cd C:\dev
mkdir work-rules-updater
cd work-rules-updater

# 다운로드한 tar.gz 압축 해제 후 파일 복사
# 또는 Claude Code로 아래 실행:

git init
git remote add origin https://github.com/seojaehong/work-rules-updater.git
```

## 3단계: 파일 배치

다운로드한 `work-rules-updater.tar.gz`를 압축 해제하여
`C:\dev\work-rules-updater\` 에 파일들을 배치하세요.

최종 구조:
```
C:\dev\work-rules-updater\
├── CLAUDE.md
├── README.md
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   ├── tracked_laws.json
│   └── law_mapping.json
├── src/
│   ├── law_api/
│   │   ├── client.py
│   │   ├── parser.py
│   │   └── diff.py
│   ├── rules/
│   │   ├── docx_parser.py
│   │   ├── matcher.py
│   │   └── updater.py
│   └── output/
│       └── comparison_table.py
├── templates/
├── data/
│   ├── company_rules/
│   ├── standard_rules/
│   └── law_cache/
└── output/
```

## 4단계: 환경 설정

```powershell
# 가상환경 생성 (선택)
python -m venv venv
.\venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
copy .env.example .env
# .env 파일 열어서 LAW_API_ID 입력
```

### 국가법령정보센터 API ID 발급
1. https://www.law.go.kr/DRF/login.do 접속
2. 회원가입 (무료)
3. 가입한 ID를 `.env` 파일의 `LAW_API_ID`에 입력

## 5단계: 첫 커밋 & 푸시

```powershell
git add .
git commit -m "init: 취업규칙 자동 변경 시스템 초기 세팅"
git push -u origin main
```

## 6단계: Claude Code로 개발 시작

```powershell
# VS Code에서 프로젝트 열기
code .

# Claude Code 실행
claude

# 첫 작업 예시:
# "CLAUDE.md 읽고 Phase 1부터 시작해줘. 국가법령정보 API로 근로기준법 조문 조회 테스트해보자"
```

## 참고: Claude Code 에이전트 모드로 쓰는 팁

```bash
# 단순 개발이 아닌 에이전트로 활용:

claude "법령 API 테스트해서 근로기준법 최신 시행일 확인해줘"
claude "data/company_rules/ 에 있는 취업규칙 파싱해서 조문 목록 보여줘"
claude "근로기준법 개정사항이 이 취업규칙의 어떤 조문에 영향주는지 분석해줘"
```

Claude Code가 CLAUDE.md를 읽고 프로젝트 맥락을 이해한 상태에서
코드 실행 + 분석 + 파일 생성까지 에이전트처럼 처리합니다.
