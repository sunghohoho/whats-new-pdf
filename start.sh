#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# AWS Report Studio — 원클릭 실행 (macOS / Linux)
#   사용법:  ./start.sh          (기본 포트 8010)
#            ./start.sh 9000     (포트 지정)
# 최초 1회는 가상환경/라이브러리/Chromium을 자동 설치하고,
# 이후에는 바로 실행됩니다. 브라우저도 자동으로 열립니다.
# ─────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

PORT="${1:-8010}"
MARKER=".venv/.setup_done"

# 1) 파이썬 확인
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "[오류] Python이 설치되어 있지 않습니다. https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요."
  exit 1
fi

# 2) 최초 셋업 (가상환경 + 라이브러리 + Chromium)
if [ ! -f "$MARKER" ]; then
  echo "[setup] 최초 실행 준비 중입니다. 잠시만 기다려 주세요 (몇 분 소요될 수 있어요)..."
  [ -d ".venv" ] || "$PY" -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
  ./.venv/bin/python -m playwright install chromium
  touch "$MARKER"
  echo "[setup] 준비 완료!"
fi

URL="http://localhost:${PORT}"

# 3) 서버가 뜨면 브라우저 자동 열기 (백그라운드)
(
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null "$URL" 2>/dev/null; then break; fi
    sleep 0.5
  done
  if command -v open >/dev/null 2>&1; then open "$URL"          # macOS
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" # Linux
  fi
) &

# 4) 실행
echo ""
echo "  ▶ AWS Report Studio 실행 중:  $URL"
echo "    (종료하려면 이 창에서 Ctrl+C)"
echo ""
exec ./.venv/bin/python -m uvicorn webapp.server:app --host 0.0.0.0 --port "$PORT"
