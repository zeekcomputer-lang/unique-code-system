@echo off
REM ========================================================
REM  8000/8080 포트를 점유한 python.exe 프로세스 종료
REM ========================================================
setlocal ENABLEDELAYEDEXPANSION

echo [UCS] 8000 포트 정리
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do (
  echo   kill PID %%P
  taskkill /F /PID %%P >nul 2>&1
)

echo [UCS] 8080 포트 정리
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8080 " ^| findstr LISTENING') do (
  echo   kill PID %%P
  taskkill /F /PID %%P >nul 2>&1
)

echo ✓ 종료 완료
pause
