#!/usr/bin/env bash
# =========================================================
#  Unique Code System — WSL2 / Linux 종료
# =========================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$SCRIPT_DIR/ucs.pid"
PORT="${UCS_PORT:-8099}"

stopped=0
if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "[UCS] 종료 PID $PID"
    kill "$PID" 2>/dev/null || true
    sleep 1
    kill -9 "$PID" 2>/dev/null || true
    stopped=1
  fi
  rm -f "$PIDFILE"
fi

# PID 파일이 없을 때: 포트 점유 프로세스 정리 (fallback)
if [ "$stopped" = "0" ] && command -v fuser >/dev/null 2>&1; then
  if fuser "$PORT/tcp" >/dev/null 2>&1; then
    echo "[UCS] 포트 $PORT 점유 프로세스 종료"
    fuser -k "$PORT/tcp" 2>/dev/null || true
    stopped=1
  fi
fi

[ "$stopped" = "1" ] && echo "✓ 종료 완료" || echo "  (실행 중인 인스턴스 없음)"
