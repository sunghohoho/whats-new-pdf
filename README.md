# AWS 업데이트 리포트 PDF 생성기

매달 바뀌는 내용만 채워 넣으면, **항상 동일한 형식·스타일**의 PDF가 생성됩니다.
스타일과 레이아웃은 템플릿에 고정되어 있어 매번 손댈 필요가 없습니다.

사용 방법은 두 가지입니다.

- **웹앱** (`webapp/`): 스크립트를 붙여넣고 실시간 미리보기를 보며 항목을 수정한 뒤 PDF 다운로드. 엔지니어 모두가 브라우저로 접근.
- **CLI** (`generate.py`): YAML 파일을 넣으면 PDF 생성. 자동화/배치용.

두 방식 모두 동일한 렌더러(`webapp/renderer.py`)와 템플릿을 사용하므로 결과물이 완전히 같습니다.

## 구조

```
pdf-automation/
├── webapp/                  # 웹앱
│   ├── server.py            #   FastAPI 서버
│   ├── renderer.py          #   공용 렌더러 (데이터→HTML→PDF)
│   ├── parser.py            #   원본 스크립트 → 구조화 데이터
│   └── static/              #   프론트엔드 (index.html, app.js, sample.json)
├── templates/
│   └── report.html.j2       # 고정 템플릿 (스타일/레이아웃)
├── assets/fonts/            # 내장 Noto Sans KR (오프라인 렌더링 보장)
├── data/                    # CLI용 YAML 데이터
│   └── 2026-06.yml
├── generate.py              # CLI 생성 스크립트
├── start.sh                 # 원클릭 실행 (macOS/Linux)
├── start.bat                # 원클릭 실행 (Windows)
├── requirements.txt
└── out/                     # 생성된 PDF (git 미포함)
```

## 웹앱 사용 (권장) — 원클릭 실행

최초 실행 시 가상환경 · 라이브러리 · Chromium을 **자동 설치**하고, 이후에는 바로 뜹니다.
서버가 준비되면 **브라우저도 자동으로 열립니다.** (파이썬만 미리 설치되어 있으면 됩니다)

macOS / Linux:
```bash
./start.sh              # 기본 포트 8010
./start.sh 9000         # 포트 지정
```

Windows (파일 탐색기에서 **start.bat 더블클릭**, 또는 명령창에서):
```bat
start.bat               REM 기본 포트 8010
start.bat 9000          REM 포트 지정
```

> 크로스플랫폼: 이 앱은 Python + Playwright(자체 Chromium 내장) 기반이라 **macOS · Windows · Linux 모두 동일하게 동작**합니다.
> 한글 폰트(Noto Sans KR)도 프로젝트에 내장되어 있어 OS의 한글 폰트 설치 여부와 무관하게 결과물이 같습니다.

자동으로 열리지 않으면 브라우저에서 `http://localhost:8010` 로 접속하세요. 이후:

1. **원본 스크립트** 칸에 AI가 정리한 텍스트를 붙여넣고 **파싱하여 채우기** 클릭
2. 자동 인식이 완벽하지 않으므로, 오른쪽 **실시간 미리보기**를 보며 왼쪽 폼에서 항목을 수정/추가/삭제
3. **PDF 다운로드** 클릭

> 팀 공유: 사내 서버에서 `./start.sh` 를 실행하면 `http://<서버IP>:8010` 으로 모두 접근할 수 있습니다.
> ⚠️ 이 서버에는 **인증이 없습니다.** 사내망에서만 노출하거나, 외부 공개가 필요하면 리버스 프록시(예: nginx)에 접근 제어를 두세요.

## 파싱: 형식이 제각각인 문제 해결

엔지니어마다 붙여넣는 스크립트 형식이 달라 파싱이 흔들립니다. 두 가지 방법을 함께 제공합니다.

### 1) LLM 자동 파싱 (형식 무관, 권장)

환경변수로 LLM을 연결하면, 형식이 뭐든 붙여넣은 텍스트를 고정 스키마로 정규화합니다.
연결이 없거나 호출이 실패하면 규칙 기반 파서로 자동 폴백합니다. (앱은 항상 동작)

**OpenAI 호환 엔드포인트**(사내 게이트웨이/OpenAI 등):
```bash
pip install openai      # 최초 1회
export LLM_PROVIDER=openai
export LLM_BASE_URL=http://<게이트웨이>/v1   # OpenAI 본가면 생략
export LLM_API_KEY=<키>
export LLM_MODEL=gpt-4o-mini                 # 원하는 모델
```

**AWS Bedrock Claude** (권장, 설정은 `.env` 파일로):
```bash
pip install boto3          # 최초 1회
cp .env.example .env       # 그리고 .env 편집
```
`.env` 예시 (서울 리전에서 동작 확인된 모델):
```bash
LLM_PROVIDER=bedrock
AWS_REGION=ap-northeast-2
# Haiku (빠르고 저렴, 기본):
BEDROCK_MODEL_ID=apac.anthropic.claude-3-haiku-20240307-v1:0
# Sonnet 3.5 v2 (더 정확):
# BEDROCK_MODEL_ID=apac.anthropic.claude-3-5-sonnet-20241022-v2:0
```
AWS 자격증명은 표준 체인(`~/.aws/credentials`, 환경변수, IAM 역할)을 사용합니다.
Bedrock 콘솔에서 해당 Claude 모델에 대한 **모델 액세스**가 활성화되어 있어야 합니다.

설정 후 `./start.sh` (Windows는 `start.bat`) 로 실행하면, 원본 스크립트 카드에 **"AI 파싱 사용 (bedrock)"** 배지가 뜹니다.

> 서울 리전에서 사용 가능한 Claude 모델 목록은 다음으로 조회할 수 있습니다:
> `aws bedrock list-inference-profiles --region ap-northeast-2`

**OpenAI 호환** 방식도 `.env` 에 `LLM_PROVIDER=openai` 로 설정 가능합니다 (`.env.example` 참고).

### 2) 입력 형식 표준화 (LLM 없이도 정확)

스크립트가 AI 생성이라면, 애초에 **일관된 형식으로 출력하도록 프롬프트를 표준화**하는 것이 가장 확실합니다.
엔지니어에게 배포할 프롬프트와 표준 형식은 [`docs/PROMPT.md`](docs/PROMPT.md) 참고. 규칙 기반 파서가 거의 완벽히 인식합니다.

> 규칙 파서는 표준 형식 외에도 `EOL/Maintenance/SDK` 하위 섹션 헤더, 괄호 없는 날짜,
> 제목 괄호 안 배지(`(GA, 2026.05.28)`), `{eol}`/`{eos}` 마커 등을 폭넓게 인식합니다.

## 설치 (최초 1회, 수동)

`start.sh` / `start.bat` 를 쓰면 자동으로 처리되지만, 수동 설치는 다음과 같습니다.

macOS / Linux:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

Windows:
```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\playwright install chromium
```

## CLI 사용

macOS / Linux 는 `.venv/bin/python`, Windows 는 `.venv\Scripts\python` 을 사용합니다.

```bash
# 기본: out/<파일명>.pdf 로 생성
.venv/bin/python generate.py data/2026-06.yml

# 출력 경로 지정
.venv/bin/python generate.py data/2026-06.yml -o out/2026년6월_AWS_변경사항.pdf

# 디버그: PDF 대신 중간 HTML만 저장 (브라우저로 열어 확인)
.venv/bin/python generate.py data/2026-06.yml --html
```

## 매달 하는 일

1. `data/` 안의 기존 파일을 복사해서 새 달 파일을 만듭니다. 예: `cp data/2026-06.yml data/2026-07.yml`
2. AI가 정리한 스크립트 내용을 YAML 필드에 채워 넣습니다.
3. `generate.py` 를 실행합니다. 끝.

## 데이터 작성 규칙

### meta (문서 머리말)
| 필드 | 설명 |
|------|------|
| `eyebrow` | 상단 소제목 (주황색, 대문자) |
| `title` | 문서 제목 |
| `subtitle` | 부제 |
| `author` / `written` | 작성자 / 작성일 |
| `intro` | 회색 안내 박스 문구 |

### eol_eos (서비스 종료 표)
```yaml
eol_eos:
  - service: "Aurora MySQL"          # 서비스명
    target: "3.05 / 3.06 / 3.07"     # 대상 버전·항목 (없으면 "—")
    date: "2026.06.30"               # 종료·변경일
    action: "3.10 이상으로 자동 업그레이드"  # 조치·비고
    badge: "eol"                  # eol(서비스 종료) | eos(변경/종료)
```

### whats_new (신규 출시 — 항상 새 페이지에서 시작)
```yaml
whats_new:
  # 단일 항목
  - title: "Amazon Bedrock"
    badge: "GA"          # GA | PREVIEW 등 (생략 가능)
    date: "2026.06.01"
    note: "서울 리전 미출시"   # 제목 옆 회색 부가설명 (생략 가능)
    body: "설명 문장"
    url: "https://..."

  # 묶음 항목 (하위 항목 여러 개)
  - title: "Amazon EC2"
    badge: "GA"
    subitems:
      - subtitle: "G7 인스턴스 GA"
        date: "2026.06.18"
        body: "설명"
        url: "https://..."
```

## 스타일 규칙 (건드리지 말 것)

일관성과 "AI 티 안 나는" 느낌을 위해 지켜지는 규칙입니다. 수정이 필요하면 `templates/report.html.j2` 에서만 변경하세요.

- 색상: 네이비 `#16233b` + 오렌지 포인트 `#d97706` 두 가지만 사용
- 그림자 / 그라데이션 / 이모지 사용 안 함
- 레이아웃은 `display:table` 기반 (flexbox 미사용 — 렌더링 호환성)
- 폰트: 프로젝트 내장 Noto Sans KR (400/500/700)
- 신규 출시 섹션은 새 페이지에서 시작, 섹션 간 여백 넉넉히

## 팀 공유 (public 접근)

모든 엔지니어가 동일 결과를 얻도록 이 폴더 전체(폰트 포함)를 사내 Git 저장소에 올려 공유하세요.
`.venv/` 와 `out/` 은 `.gitignore` 처리되어 있으므로, 받는 사람은 위 "설치" 단계만 1회 수행하면 됩니다.
