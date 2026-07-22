#!/usr/bin/env bash
# =========================================================
#  Unique Code System — 상태 점검 (WSL2 / Linux)
# =========================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$SCRIPT_DIR/ucs.pid"
PORT="${UCS_PORT:-8099}"

echo "── 프로세스 ──"
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "  RUNNING (PID $(cat "$PIDFILE"))"
else
  echo "  STOPPED"
fi

echo "── 포트 $PORT ──"
if command -v ss >/dev/null 2>&1; then
  ss -ltn "( sport = :$PORT )" 2>/dev/null | grep ":$PORT" || echo "  (미점유)"
fi

echo "── WSL IP (LAN 노출 시 portproxy 대상) ──"
hostname -I 2>/dev/null | awk '{print "  "$1}'

echo "── health / dashboard ──"
if command -v curl >/dev/null 2>&1; then
  curl -s "http://localhost:$PORT/health" && echo
  curl -s "http://localhost:$PORT/api/dashboard" 2>/dev/null | head -c 400 && echo
else
  echo "  (curl 미설치)"
fi
