@echo off
REM ========================================================
REM  8099/8989 포트를 점유한 python.exe 프로세스 종료
REM ========================================================
setlocal ENABLEDELAYEDEXPANSION

if "%UCS_PORT%"==""     set UCS_PORT=8099
if "%UCS_WEB_PORT%"=="" set UCS_WEB_PORT=8989

echo [UCS] %UCS_PORT% 포트 정리
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%UCS_PORT% " ^| findstr LISTENING') do (
  echo   kill PID %%P
  taskkill /F /PID %%P >nul 2>&1
)

echo [UCS] %UCS_WEB_PORT% 포트 정리
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%UCS_WEB_PORT% " ^| findstr LISTENING') do (
  echo   kill PID %%P
  taskkill /F /PID %%P >nul 2>&1
)

echo ✓ 종료 완료
pause
