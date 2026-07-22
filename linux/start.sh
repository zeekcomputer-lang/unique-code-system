#!/usr/bin/env bash
# =========================================================
#  Unique Code System — WSL2 / Linux 기동 (단일 포트)
#  - 하나의 uvicorn 프로세스가 UI(정적) + API 를 8099 에서 서빙
#  - 0.0.0.0 바인딩 → 같은 통신망(LAN) PC 에서 접속 가능
#  - 단일 워커(데이터 무결성 우선). 백그라운드 실행 + PID/로그 파일.
#
#  환경변수(선택):
#    UCS_PORT   외부 접속 포트 (기본 8099)
#    UCS_HOST   바인드 주소     (기본 0.0.0.0 = 전체 인터페이스)
#    FOREGROUND=1  포그라운드 실행(로그 콘솔 출력, Ctrl+C 종료)
# =========================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT_DIR/.venv-wsl"
PIDFILE="$SCRIPT_DIR/ucs.pid"
LOGDIR="$SCRIPT_DIR/logs"
LOG="$LOGDIR/backend.log"

PORT="${UCS_PORT:-8099}"
HOST="${UCS_HOST:-0.0.0.0}"

if [ ! -x "$VENV/bin/python" ]; then
  echo "  ✘ .venv-wsl 없음. 먼저 linux/setup.sh 실행." >&2
  exit 1
fi
mkdir -p "$LOGDIR"

# 이미 기동 중이면 안내
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "  ! 이미 실행 중 (PID $(cat "$PIDFILE")). 재기동은 linux/stop.sh 후 다시." >&2
  exit 0
fi

# 포트 점유 가드 (Windows 트랙 등과 동시 기동 방지)
if command -v ss >/dev/null 2>&1 && ss -ltn "( sport = :$PORT )" 2>/dev/null | grep -q ":$PORT"; then
  echo "  ✘ 포트 $PORT 이 이미 사용 중입니다. 다른 인스턴스를 종료 후 재시도." >&2
  exit 1
fi

cd "$ROOT_DIR/backend"
export UCS_PORT="$PORT" UCS_HOST="$HOST"

CMD=("$VENV/bin/python" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --workers 1)

if [ "${FOREGROUND:-0}" = "1" ]; then
  echo "[UCS] 포그라운드 기동: http://$HOST:$PORT  (Ctrl+C 종료)"
  exec "${CMD[@]}"
fi

echo "[UCS] 백그라운드 기동 → $LOG"
nohup "${CMD[@]}" >"$LOG" 2>&1 &
echo $! > "$PIDFILE"
sleep 2

if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "✓ 기동 완료 (PID $(cat "$PIDFILE"))"
  echo "  - 로컬:     http://localhost:$PORT/"
  echo "  - LAN 접속:  http://<이 PC 고정 IP>:$PORT/   (README-WSL2.md 참조)"
  echo "  - API 문서: http://localhost:$PORT/docs"
else
  echo "  ✘ 기동 실패. 로그 확인: $LOG" >&2
  tail -20 "$LOG" >&2 || true
  exit 1
fi
