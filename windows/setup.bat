@echo off
REM ========================================================
REM  Unique Code System - Windows Setup (1회성)
REM  - Python 3.10+ 필요 (https://www.python.org/downloads/)
REM  - 가상환경(.venv) 생성 + 의존성 설치
REM  - 외부 서비스 의존 0 (SQLite 단일 파일, Redis 불필요)
REM ========================================================
setlocal
cd /d "%~dp0\.."

echo [UCS] 1) Python 확인
where python >nul 2>&1
if errorlevel 1 goto NOPY
python --version

echo [UCS] 2) 가상환경(.venv)
if not exist ".venv" python -m venv .venv
if errorlevel 1 goto VENVFAIL

echo [UCS] 3) 의존성 설치
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
if errorlevel 1 goto PIPFAIL

echo [UCS] 4) 데이터 폴더
if not exist "backend\data" mkdir "backend\data"

echo.
echo [OK] 설치 완료.  기동: windows\start.bat
echo.
pause
exit /b 0

:NOPY
echo [X] python 명령을 찾을 수 없습니다. https://www.python.org/downloads/ 설치 시 "Add Python to PATH" 체크.
pause
exit /b 1

:VENVFAIL
echo [X] 가상환경 생성 실패
pause
exit /b 1

:PIPFAIL
echo [X] 의존성 설치 실패 (프록시 환경이면 pip --proxy 옵션 참조)
pause
exit /b 1
