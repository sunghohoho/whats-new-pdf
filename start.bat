@echo off
REM ─────────────────────────────────────────────────────────────
REM  AWS Report Studio - 원클릭 실행 (Windows)
REM    더블클릭하거나, 명령창에서:  start.bat        (기본 포트 8010)
REM                                  start.bat 9000   (포트 지정)
REM  최초 1회는 가상환경/라이브러리/Chromium을 자동 설치하고,
REM  이후에는 바로 실행됩니다. 브라우저도 자동으로 열립니다.
REM ─────────────────────────────────────────────────────────────
setlocal
cd /d "%~dp0"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8010"
set "MARKER=.venv\.setup_done"

REM 1) 파이썬 확인
where python >nul 2>&1
if errorlevel 1 (
  echo [오류] Python이 설치되어 있지 않습니다.
  echo        https://www.python.org/downloads/ 에서 설치 후 (설치 시 "Add to PATH" 체크) 다시 실행하세요.
  pause
  exit /b 1
)

REM 2) 최초 셋업 (가상환경 + 라이브러리 + Chromium)
if not exist "%MARKER%" (
  echo [setup] 최초 실행 준비 중입니다. 잠시만 기다려 주세요 ^(몇 분 소요될 수 있어요^)...
  if not exist ".venv\" python -m venv .venv
  call .venv\Scripts\python -m pip install --quiet --upgrade pip
  call .venv\Scripts\pip install --quiet -r requirements.txt
  call .venv\Scripts\python -m playwright install chromium
  echo done> "%MARKER%"
  echo [setup] 준비 완료!
)

REM 3) 서버가 뜨는 동안 브라우저 자동 열기 (지연 후)
start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:%PORT%"

REM 4) 실행
echo.
echo   ^> AWS Report Studio 실행 중:  http://localhost:%PORT%
echo     (종료하려면 이 창에서 Ctrl+C)
echo.
call .venv\Scripts\python -m uvicorn webapp.server:app --host 0.0.0.0 --port %PORT%

endlocal
