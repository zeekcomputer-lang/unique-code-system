@echo off
REM ========================================================
REM  Frontend (정적 서버, :8080)
REM ========================================================
setlocal
cd /d "%~dp0\..\frontend"

where python >nul 2>&1
if errorlevel 1 (
  echo  ✘ python 을 찾을 수 없습니다. setup.bat 먼저 실행하세요.
  pause & exit /b 1
)

echo [UCS] 프론트엔드 http://localhost:8080/index.html
python -m http.server 8080 --bind 127.0.0.1
pause
