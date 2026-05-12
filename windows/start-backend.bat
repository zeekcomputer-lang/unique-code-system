@echo off
REM ========================================================
REM  Backend (FastAPI) — fakeredis 모드
REM  포트 변경: UCS_PORT 환경변수
REM  실 Redis 사용 시 USE_REAL_REDIS=1
REM ========================================================
setlocal
cd /d "%~dp0\..\backend"

if not exist "..\.venv\Scripts\activate.bat" (
  echo  ✘ .venv 가 없습니다. 먼저 windows\setup.bat 을 실행하세요.
  pause & exit /b 1
)

call "..\.venv\Scripts\activate.bat"

REM ── 포트 설정 (기본 8099) ────────────────────────────
if "%UCS_PORT%"=="" set UCS_PORT=8099

if /I "%USE_REAL_REDIS%"=="1" (
  echo [UCS] 실 Redis 모드 ^(포트 %UCS_PORT%, UCS_REDIS_URL=%UCS_REDIS_URL%^)
  python -m app.main
) else (
  echo [UCS] fakeredis 모드 ^(포트 %UCS_PORT%^)
  python run_with_fakeredis.py
)

pause
