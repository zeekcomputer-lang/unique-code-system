@echo off
REM ========================================================
REM  Backend (FastAPI) — fakeredis 모드
REM  실 Redis 사용 시 USE_REAL_REDIS=1 환경변수 후 실행
REM ========================================================
setlocal
cd /d "%~dp0\..\backend"

if not exist "..\.venv\Scripts\activate.bat" (
  echo  ✘ .venv 가 없습니다. 먼저 windows\setup.bat 을 실행하세요.
  pause & exit /b 1
)

call "..\.venv\Scripts\activate.bat"

if /I "%USE_REAL_REDIS%"=="1" (
  echo [UCS] 실 Redis 모드 ^(UCS_REDIS_URL=%UCS_REDIS_URL%^)
  python -m app.main
) else (
  echo [UCS] fakeredis 모드 ^(개발용^)
  python run_with_fakeredis.py
)

pause
