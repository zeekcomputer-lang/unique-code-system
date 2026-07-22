#!/usr/bin/env bash
# =========================================================
#  Unique Code System — WSL2 / Linux 셋업 (1회성)
#  - python3 venv(.venv-wsl) 생성 + 의존성 설치
#  - 외부 서비스 의존 0 (SQLite 단일 파일, Redis 불필요)
#  - 이식형: 스크립트 위치 기준으로 프로젝트 루트 자동 해석
# =========================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT_DIR/.venv-wsl"
# 인터프리터 지정 가능(예: UCS_PYTHON=/usr/bin/python3.12). 기본 python3.
PYTHON="${UCS_PYTHON:-python3}"

echo "[UCS] 프로젝트 루트: $ROOT_DIR"

# 1) python 확인
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "  ✘ '$PYTHON' 를 찾을 수 없습니다. 'sudo apt install python3 python3-venv' 후 재시도." >&2
  exit 1
fi
echo "[UCS] $($PYTHON --version)"

# 2) venv 생성
if [ ! -d "$VENV" ]; then
  echo "[UCS] 가상환경 생성: $VENV"
  "$PYTHON" -m venv "$VENV" || {
    echo "  ✘ venv 생성 실패. 'sudo apt install python3-venv' 필요할 수 있음." >&2; exit 1; }
else
  echo "[UCS] .venv-wsl 이미 존재 → 재사용"
fi

# 3) 의존성 설치
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$ROOT_DIR/backend/requirements.txt"

# 4) 데이터 폴더
mkdir -p "$ROOT_DIR/backend/data" "$SCRIPT_DIR/logs"

echo ""
echo "✓ 셋업 완료."
echo "  - 기동:  linux/start.sh"
echo "  - 상태:  linux/status.sh"
echo "  - 종료:  linux/stop.sh"
