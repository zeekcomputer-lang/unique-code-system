#!/usr/bin/env bash
# =========================================================
#  systemd --user 서비스 설치 (선택: WSL2 상시 자동기동)
#  - 재부팅/세션 종료 후에도 자동 복구하려면 linger 필요:
#      sudo loginctl enable-linger "$USER"
# =========================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PORT="${UCS_PORT:-8099}"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT="ucs.service"

if [ ! -x "$ROOT_DIR/.venv-wsl/bin/python" ]; then
  echo "  ✘ .venv-wsl 없음. 먼저 linux/setup.sh 실행." >&2
  exit 1
fi

mkdir -p "$UNIT_DIR"
sed -e "s#__ROOT__#$ROOT_DIR#g" -e "s#__PORT__#$PORT#g" \
    "$SCRIPT_DIR/systemd/$UNIT" > "$UNIT_DIR/$UNIT"

systemctl --user daemon-reload
systemctl --user enable --now "$UNIT"

echo "✓ 설치/기동 완료: systemctl --user status $UNIT"
echo "  상시 자동기동(재부팅 후에도): sudo loginctl enable-linger $USER"
echo "  로그: journalctl --user -u $UNIT -f"
