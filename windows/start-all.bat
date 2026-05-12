@echo off
REM ========================================================
REM  통합 시작 — 백엔드(:8099) + 프론트엔드(:8989) 동시 기동
REM ========================================================
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\activate.bat" (
  echo  ✘ .venv 가 없습니다. 먼저 windows\setup.bat 을 실행하세요.
  pause & exit /b 1
)

if "%UCS_PORT%"==""     set UCS_PORT=8099
if "%UCS_WEB_PORT%"=="" set UCS_WEB_PORT=8989

echo [UCS] 백엔드 콘솔 기동 ^(:%UCS_PORT%^)
start "UCS Backend"  cmd /k "%~dp0start-backend.bat"

REM 백엔드 부팅 대기
timeout /t 2 /nobreak >nul

echo [UCS] 프론트엔드 콘솔 기동 ^(:%UCS_WEB_PORT%^)
start "UCS Frontend" cmd /k "%~dp0start-frontend.bat"

REM 자동으로 브라우저 열기
timeout /t 2 /nobreak >nul
start "" "http://localhost:%UCS_WEB_PORT%/index.html"

echo.
echo ✓ 두 콘솔이 열렸습니다. 종료 시 각 창의 Ctrl+C 또는 X 버튼 사용.
echo.
pause
