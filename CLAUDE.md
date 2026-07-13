# Project: AWS Report Studio

AWS 서비스 변경사항(EOL·EOS / 신규 출시)을 붙여넣어 일관된 PDF로 만드는 도구.
웹앱(FastAPI) + CLI(generate.py) 두 진입점을 가지며, Python 3.11+ / Playwright 기반이라
macOS · Windows · Linux 에서 동일하게 동작한다.

## Setup

- 가상환경: macOS/Linux `source .venv/bin/activate`, Windows `.venv\Scripts\activate`
  (Python 명령 실행 전 항상 활성화, 또는 `.venv/bin/python` 을 직접 사용)
- 원클릭 실행/설치: `./start.sh` (Windows `start.bat`) — venv·의존성·Chromium 자동 설치
- 수동 설치: `pip install -r requirements.txt && playwright install chromium`
- 개발 도구: `pip install -r requirements-dev.txt` (ruff, mypy)
- 환경변수: `.env.example` 을 `.env` 로 복사. `.env` 는 커밋 금지(gitignore됨).

## Commands

- `./start.sh` — 웹앱 실행(자동 설치 + 브라우저 열림), 포트 지정 `./start.sh 9000`
- `.venv/bin/uvicorn webapp.server:app --reload` — 개발 서버 수동 실행
- `.venv/bin/python generate.py data/2026-06.yml` — CLI로 PDF 생성
- `.venv/bin/ruff check .` — 린트
- `.venv/bin/ruff format .` — 포매팅
- `.venv/bin/mypy` — 타입 체크 (설정은 pyproject.toml)

커밋 전 실행: `ruff check . && ruff format --check . && mypy`

> 개발 서버(`uvicorn --reload`)나 `start.sh` 같은 장시간 실행 명령은 에이전트가 직접
> 백그라운드로 띄우지 말고, 사용자가 직접 터미널에서 실행하도록 안내한다.

## Project Structure

- `webapp/` — 웹 애플리케이션 (계층: server → parser/llm_parser → renderer)
  - `server.py` — FastAPI 진입점, 라우트, `.env` 로더, 파싱 결과 후처리
  - `parser.py` — 규칙 기반(정규식) 파서. LLM 미사용/폴백 경로
  - `llm_parser.py` — LLM 파서(Bedrock/OpenAI 호환). 실패 시 예외 → server가 폴백
  - `renderer.py` — 공용 렌더러(데이터→HTML→PDF). 미리보기·CLI·PDF가 모두 이걸 사용
  - `defaults.py` — 문서 기본값(작성자 등). 환경변수로 override
  - `static/` — 프론트엔드(index.html, app.js, sample.json)
- `templates/report.html.j2` — 고정 PDF 템플릿(스타일/레이아웃). **디자인은 여기서만 변경**
- `assets/fonts/` — 내장 Noto Sans KR(오프라인 렌더링 일관성 보장). 삭제 금지
- `data/*.yml` — CLI용 입력 데이터
- `docs/PROMPT.md` — 입력 표준화용 생성 프롬프트
- `generate.py` — CLI 진입점
- `out/` — 생성 결과물(gitignore)

## Coding Conventions

- 모든 함수 시그니처에 타입 힌트(파라미터·반환)
- 모든 모듈 상단에 `from __future__ import annotations`
- 파일 경로는 `pathlib.Path` (os.path 금지)
- 문자열 포매팅은 f-string
- 공개 함수는 Google 스타일 docstring
- **웹/서비스 코드(webapp/)는 `print()` 대신 `logging` 사용.**
  단, CLI(`generate.py`)의 사용자 대상 출력은 `print()` 허용(관례).
- 미리보기·PDF·CLI는 반드시 `renderer.render_html` / `html_to_pdf_bytes` 를 공유해
  결과가 항상 일치하도록 한다. 렌더링 로직을 복제하지 말 것.

## Parsing Rules (도메인 규칙)

- 파싱 규칙(`parser.py`)과 LLM 프롬프트(`llm_parser.py`)와 생성 프롬프트(`docs/PROMPT.md`)는
  **같은 규칙**을 공유한다. 한쪽을 바꾸면 나머지도 함께 맞춘다.
- badge: 운영 종료/EOL → `eol`, 신규가입중단/Maintenance/SDK EOS/요금·방식 변경 → `eos`.
- 신규 항목 설명은 항상 `body` 한 곳으로 모아 렌더링(제목 옆 인라인 금지).
- 날짜 YYYY.MM.DD 통일, 신규는 최신순, 없는 값(날짜/URL)은 지어내지 않는다.

## Security

- 시크릿은 환경변수/`.env` 로만. 코드·데이터·문서에 키/토큰/계정ID/개인정보 하드코딩 금지.
- 붙여넣은 스크립트, LLM 출력, 웹 요청 본문은 **신뢰할 수 없는 입력**으로 취급.
  템플릿 렌더링은 Jinja2 autoescape 유지.
- 웹 서버에는 인증이 없다. 사내망 한정으로 노출하거나 리버스 프록시로 접근 제어.
- 내부 코멘트/고객사명/코드네임/프로젝트명은 리포트에 포함하지 않는다.
- **푸시 전 시크릿 스캔**: `.githooks/pre-push` 가 푸시되는 커밋의 diff에서 AWS 키·프라이빗 키·
  토큰(sk-/ghp_/xox-/AIza) 및 `.env`·`*.pem` 등 민감 파일을 검사해 발견 시 푸시를 차단한다.
  오탐이 확실할 때만 `ALLOW_SECRETS=1 git push` 로 우회.

## Do NOT

- `import *` 금지
- webapp/ 에서 `print()` 로 디버그 출력 금지(logging 사용)
- 렌더링/파싱 로직 복제 금지(공용 모듈 사용)
- 템플릿 외의 곳에 인라인 스타일/디자인 하드코딩 금지
- `.env`, `.venv/`, `out/`, 폰트 캐시 등 gitignore 대상 커밋 금지
- Playwright의 브라우저를 요청마다 남겨두지 말고 사용 후 `browser.close()`

## Git

- Conventional Commits: `type(scope): subject` (feat, fix, chore, refactor, docs)
- 명령형·마침표 없음. 커밋 전 `ruff check . && mypy` 통과.
- 커밋 제목 끝에는 `.githooks/prepare-commit-msg` 훅이 랜덤 깜찍 이모티콘을 자동으로 붙인다
  (예: `feat: 파서 개선  (｡•̀ᴗ-)✧`). 손으로 붙이지 말 것 — 훅이 처리한다.
  merge/squash/amend 커밋에는 붙지 않는다.
- 훅 활성화(최초 1회): `git config core.hooksPath "$(pwd)/.githooks"`
  - `prepare-commit-msg`: 커밋 제목에 랜덤 이모티콘 부여
  - `pre-push`: 푸시 전 시크릿 스캔(발견 시 차단, `ALLOW_SECRETS=1` 로 우회)
- 사용자가 명시적으로 요청할 때만 커밋. 강제 푸시/`--amend`(푸시된 커밋)/`--no-verify` 금지.

## See Also

- `README.md` — 사용자용 설치·실행 안내
- `docs/PROMPT.md` — 입력 스크립트 표준화 프롬프트
