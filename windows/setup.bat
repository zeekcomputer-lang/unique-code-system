@echo off
REM ========================================================
REM  Unique Code System — Windows 10 Setup
REM  - Python 3.10+ 필요 (https://www.python.org/downloads/)
REM  - 가상환경(.venv) 생성 + 의존성 설치
REM ========================================================

setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0\.."

echo.
echo [UCS] 1) Python 버전 확인
where python >nul 2>&1
if errorlevel 1 (
  echo  ✘ python 명령을 찾을 수 없습니다.
  echo    https://www.python.org/downloads/ 에서 3.10 이상 설치 후
  echo    설치 시 "Add Python to PATH" 옵션을 체크하세요.
  pause
  exit /b 1
)
python --version

echo.
echo [UCS] 2) 가상환경(.venv) 생성
if not exist ".venv" (
  python -m venv .venv
  if errorlevel 1 (
    echo  ✘ 가상환경 생성 실패
    pause & exit /b 1
  )
) else (
  echo  - 이미 .venv 존재 → 재사용
)

echo.
echo [UCS] 3) 의존성 설치
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install fakeredis
if errorlevel 1 (
  echo  ✘ 의존성 설치 실패
  pause & exit /b 1
)

echo.
echo [UCS] 4) 데이터 폴더 확인
if not exist "backend\data" mkdir "backend\data"

echo.
echo ✓ 설치 완료.
echo   - 백엔드 시작:  windows\start-backend.bat
echo   - 프론트 시작:  windows\start-frontend.bat
echo   - 통합 시작:    windows\start-all.bat
echo.
pause
