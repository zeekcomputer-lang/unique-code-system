@echo off
REM ========================================================
REM  Unique Code System - Windows 기동 (단일 포트)
REM  하나의 uvicorn 이 UI(정적) + API 를 8099 에서 서빙.
REM  0.0.0.0 바인딩 -> 같은 통신망(LAN) PC 에서 접속 가능.
REM  포트 변경: set UCS_PORT=9000  후 실행
REM ========================================================
setlocal
cd /d "%~dp0\..\backend"

if not exist "..\.venv\Scripts\activate.bat" goto NOVENV

call "..\.venv\Scripts\activate.bat"
if "%UCS_PORT%"=="" set UCS_PORT=8099
set UCS_HOST=0.0.0.0

echo [UCS] http://localhost:%UCS_PORT%/   (LAN: http://이-PC-고정IP:%UCS_PORT%/)
echo [UCS] 종료: 이 창에서 Ctrl+C
python -m uvicorn app.main:app --host 0.0.0.0 --port %UCS_PORT% --workers 1
pause
exit /b 0

:NOVENV
echo [X] .venv 가 없습니다. 먼저 windows\setup.bat 실행.
pause
exit /b 1
