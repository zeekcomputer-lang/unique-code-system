@echo off
REM ========================================================
REM  8099 포트를 점유한 python 프로세스 종료
REM ========================================================
setlocal
if "%UCS_PORT%"=="" set UCS_PORT=8099

echo [UCS] %UCS_PORT% 포트 정리
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%UCS_PORT% " ^| findstr LISTENING') do (
  echo   kill PID %%P
  taskkill /F /PID %%P >nul 2>&1
)
echo [OK] 종료 완료
pause
