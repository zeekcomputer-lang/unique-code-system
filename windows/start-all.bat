@echo off
REM ========================================================
REM  통합 기동 - 단일 포트(8099) 서버 창 + 브라우저 자동 오픈
REM  (단일 포트 통합 이후 프론트/백 분리 기동 불필요)
REM ========================================================
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\activate.bat" goto NOVENV
if "%UCS_PORT%"=="" set UCS_PORT=8099

echo [UCS] 서버 콘솔 기동 (:%UCS_PORT%)
start "UCS Server" cmd /k "%~dp0start.bat"

timeout /t 3 /nobreak >nul
start "" "http://localhost:%UCS_PORT%/index.html"

echo.
echo [OK] 서버 창이 열렸습니다. 종료 시 해당 창에서 Ctrl+C.
echo.
pause
exit /b 0

:NOVENV
echo [X] .venv 가 없습니다. 먼저 windows\setup.bat 실행.
pause
exit /b 1
