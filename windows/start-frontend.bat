@echo off
REM ========================================================
REM  Frontend (정적 서버, 기본 :8989)
REM  포트 변경: 첫 번째 인자 또는 UCS_WEB_PORT 환경변수
REM ========================================================
setlocal
cd /d "%~dp0\..\frontend"

where python >nul 2>&1
if errorlevel 1 (
  echo  ✘ python 을 찾을 수 없습니다. setup.bat 먼저 실행하세요.
  pause & exit /b 1
)

if "%UCS_WEB_PORT%"=="" set UCS_WEB_PORT=8989
if not "%~1"=="" set UCS_WEB_PORT=%~1

echo [UCS] 프론트엔드 http://localhost:%UCS_WEB_PORT%/index.html
python -m http.server %UCS_WEB_PORT% --bind 127.0.0.1
pause
