"""
SQLite 단일 SSOT (Single Source of Truth)
-----------------------------------------
기존 JSON 파일 DB + Redis ZSET 큐를 **SQLite 단일 파일**로 통합한 영속 계층.

설계 원칙
---------
- 데이터 무결성 1순위: 모든 상태 전이는 ``BEGIN IMMEDIATE`` 트랜잭션으로 직렬화.
- 외부 서비스 의존 0: Redis 불필요. 단일 ``.sqlite3`` 파일로 clone/pull 배포 즉시 동작.
- WAL 모드: 동시 읽기 자유 + 단일 라이터. busy_timeout 으로 경합 대기.

큐 개념
-------
- "대기열" = ``status='WAITING'`` 인 코드들을 ``score`` 오름차순으로 본 것.
- ``score`` 는 코드별 불변 순번(1~432). 파기 시 status 를 다시 WAITING 으로 되돌리면
  score 정렬에 의해 **원래 순번(제자리)** 으로 자동 복귀한다. (별도 재삽입 불필요)

상태
----
- codes.status : WAITING | ACTIVE   (REVOKED 는 history 이벤트로만 기록, 코드는 WAITING 복귀)
- requests.status : PENDING | APPROVED | REJECTED
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from app.core.codes import generate_all_codes
from app.core.config import settings


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─────────────────────────── 예외 ───────────────────────────
class DbError(Exception):
    """도메인 예외 베이스."""


class QueueEmpty(DbError):
    pass


class CodeNotFound(DbError):
    pass


class CodeAlreadyActive(DbError):
    pass


class CodeNotActive(DbError):
    pass


class RequestNotFound(DbError):
    pass


class RequestNotPending(DbError):
    pass


_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS codes (
    code         TEXT PRIMARY KEY,
    score        INTEGER NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT 'WAITING',
    prefix       TEXT,
    full_code    TEXT,
    request_id   TEXT,
    issued_to    TEXT,
    issued_at    TEXT,
    revoked_at   TEXT,
    force_issued INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_codes_status_score ON codes(status, score);
CREATE INDEX IF NOT EXISTS idx_codes_full ON codes(full_code);
CREATE TABLE IF NOT EXISTS code_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL,
    event      TEXT NOT NULL,
    at         TEXT NOT NULL,
    by_who     TEXT,
    prefix     TEXT,
    full_code  TEXT,
    request_id TEXT
);
CREATE TABLE IF NOT EXISTS requests (
    id               TEXT PRIMARY KEY,
    requester        TEXT NOT NULL,
    reason           TEXT NOT NULL,
    desired_prefix   TEXT,
    status           TEXT NOT NULL DEFAULT 'PENDING',
    issued_code      TEXT,
    issued_full_code TEXT,
    created_at       TEXT NOT NULL,
    approved_at      TEXT,
    approver         TEXT,
    note             TEXT
);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
"""

_CODE_FIELDS = (
    "code", "score", "status", "prefix", "full_code", "request_id",
    "issued_to", "issued_at", "revoked_at", "force_issued",
)


def _code_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = {k: row[k] for k in _CODE_FIELDS}
    d["force_issued"] = bool(d["force_issued"])
    return d


def _request_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "requester": row["requester"],
        "reason": row["reason"],
        "desired_prefix": row["desired_prefix"],
        "status": row["status"],
        "issued_code": row["issued_code"],
        "issued_full_code": row["issued_full_code"],
        "created_at": row["created_at"],
        "approved_at": row["approved_at"],
        "approver": row["approver"],
        "note": row["note"],
    }


class SqliteDatabase:
    """SQLite 단일 SSOT. 채번 큐 + 코드 레코드 + 의뢰서를 모두 관리."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path: Path = Path(path) if path else settings.DB_FILE
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = threading.Lock()
        self._init_db()

    # ─────────────────────────── 연결 ───────────────────────────

    def _raw_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self._path),
            timeout=10.0,               # busy 대기 (초)
            isolation_level=None,       # 오토커밋 — 트랜잭션 수동 제어
            check_same_thread=False,    # 커넥션-퍼-콜이므로 안전
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        conn = self._raw_connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _write_txn(self) -> Iterator[sqlite3.Connection]:
        """
        ``BEGIN IMMEDIATE`` 트랜잭션. SELECT→UPDATE 사이 경합을 막기 위해
        트랜잭션 시작 시점에 즉시 쓰기 락을 확보한다. (중복 발급 원천 차단)
        """
        conn = self._raw_connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    # ─────────────────────────── 초기화/시드 ───────────────────────────

    def _init_db(self) -> None:
        with self._init_lock:
            conn = self._raw_connect()
            try:
                conn.executescript(_SCHEMA)
                cur = conn.execute("SELECT COUNT(*) AS c FROM codes;")
                if cur.fetchone()["c"] == 0:
                    conn.execute("BEGIN IMMEDIATE;")
                    try:
                        rows = [
                            (code, idx)
                            for idx, code in enumerate(generate_all_codes(), start=1)
                        ]
                        conn.executemany(
                            "INSERT INTO codes(code, score, status) VALUES (?, ?, 'WAITING');",
                            rows,
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO meta(key, value) VALUES ('request_seq', '0');"
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO meta(key, value) VALUES ('version', ?);",
                            (settings.APP_VERSION,),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO meta(key, value) VALUES ('initialized_at', ?);",
                            (_utcnow(),),
                        )
                        conn.execute("COMMIT;")
                    except Exception:
                        conn.execute("ROLLBACK;")
                        raise
            finally:
                conn.close()

    def ping(self) -> bool:
        try:
            with self._read() as conn:
                conn.execute("SELECT 1;")
            return True
        except Exception:
            return False

    # ─────────────────────────── codes: 조회 ───────────────────────────

    def list_codes(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._read() as conn:
            if status:
                cur = conn.execute(
                    "SELECT * FROM codes WHERE status=? ORDER BY score;", (status,)
                )
            else:
                cur = conn.execute("SELECT * FROM codes ORDER BY score;")
            return [_code_row_to_dict(r) for r in cur.fetchall()]

    def get_code(self, code: str) -> Optional[Dict[str, Any]]:
        with self._read() as conn:
            cur = conn.execute("SELECT * FROM codes WHERE code=?;", (code,))
            row = cur.fetchone()
            return _code_row_to_dict(row) if row else None

    def find_code_by_full(self, full_code: str) -> Optional[Dict[str, Any]]:
        with self._read() as conn:
            cur = conn.execute("SELECT * FROM codes WHERE full_code=?;", (full_code,))
            row = cur.fetchone()
            return _code_row_to_dict(row) if row else None

    def stats(self) -> Dict[str, int]:
        with self._read() as conn:
            counts = {"WAITING": 0, "ACTIVE": 0, "REVOKED": 0, "TOTAL": 0}
            cur = conn.execute("SELECT status, COUNT(*) AS c FROM codes GROUP BY status;")
            for r in cur.fetchall():
                counts[r["status"]] = r["c"]
                counts["TOTAL"] += r["c"]
            return counts

    def queue_size(self) -> int:
        with self._read() as conn:
            cur = conn.execute("SELECT COUNT(*) AS c FROM codes WHERE status='WAITING';")
            return int(cur.fetchone()["c"])

    def peek_next(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._read() as conn:
            cur = conn.execute(
                "SELECT * FROM codes WHERE status='WAITING' ORDER BY score LIMIT ?;", (n,)
            )
            return [_code_row_to_dict(r) for r in cur.fetchall()]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "codes": {r["code"]: r for r in self.list_codes()},
            "requests": {r["id"]: r for r in self.list_requests()},
        }

    # ─────────────────────────── 내부 헬퍼 (txn 안에서 호출) ───────────────────────────

    @staticmethod
    def _get_code_row(conn: sqlite3.Connection, code: str) -> Optional[sqlite3.Row]:
        return conn.execute("SELECT * FROM codes WHERE code=?;", (code,)).fetchone()

    @staticmethod
    def _add_history(
        conn: sqlite3.Connection, code: str, event: str, *,
        by: Optional[str] = None, prefix: Optional[str] = None,
        full_code: Optional[str] = None, request_id: Optional[str] = None,
    ) -> None:
        conn.execute(
            "INSERT INTO code_history(code, event, at, by_who, prefix, full_code, request_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);",
            (code, event, _utcnow(), by, prefix, full_code, request_id),
        )

    @staticmethod
    def _approve_request_txn(
        conn: sqlite3.Connection, req_id: str, *,
        base_code: str, full_code: str, approver: Optional[str],
    ) -> None:
        row = conn.execute("SELECT status FROM requests WHERE id=?;", (req_id,)).fetchone()
        if row is None:
            raise RequestNotFound(f"존재하지 않는 의뢰서: {req_id}")
        if row["status"] != "PENDING":
            raise RequestNotPending(
                f"PENDING 상태가 아닌 의뢰서: {req_id} ({row['status']})"
            )
        conn.execute(
            "UPDATE requests SET status='APPROVED', issued_code=?, issued_full_code=?, "
            "approved_at=?, approver=? WHERE id=?;",
            (base_code, full_code, _utcnow(), approver, req_id),
        )

    # ─────────────────────────── codes: 발급/파기 (원자적) ───────────────────────────

    def issue_next_for_request(
        self, req_id: str, *, prefix: str,
        issued_to: Optional[str] = None, approver: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        의뢰서 승인 + 대기열 최상단 발급을 **단일 트랜잭션**으로 원자 처리.

        순서: PENDING 검증 → 최소 score WAITING 확보 → ACTIVE 전환 → 의뢰서 APPROVED.
        """
        with self._write_txn() as conn:
            req = conn.execute(
                "SELECT status FROM requests WHERE id=?;", (req_id,)
            ).fetchone()
            if req is None:
                raise RequestNotFound(f"존재하지 않는 의뢰서: {req_id}")
            if req["status"] != "PENDING":
                raise RequestNotPending(f"PENDING 상태가 아닙니다 (현재: {req['status']})")

            row = conn.execute(
                "SELECT * FROM codes WHERE status='WAITING' ORDER BY score LIMIT 1;"
            ).fetchone()
            if row is None:
                raise QueueEmpty("대기열이 비어 있습니다 (발급 가능 코드 없음)")

            base_code = row["code"]
            full_code = f"{prefix}{base_code}"
            now = _utcnow()
            conn.execute(
                "UPDATE codes SET status='ACTIVE', prefix=?, full_code=?, request_id=?, "
                "issued_to=?, issued_at=?, revoked_at=NULL, force_issued=0 WHERE code=?;",
                (prefix, full_code, req_id, issued_to, now, base_code),
            )
            self._add_history(
                conn, base_code, "ISSUED",
                by=issued_to, prefix=prefix, full_code=full_code, request_id=req_id,
            )
            self._approve_request_txn(
                conn, req_id, base_code=base_code, full_code=full_code, approver=approver,
            )
            return _code_row_to_dict(self._get_code_row(conn, base_code))

    def force_issue(
        self, *, base_code: str, prefix: str,
        request_id: Optional[str] = None, issued_to: Optional[str] = None,
        approver: Optional[str] = None, reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        강제 채번: 대기열 순서를 무시하고 특정 base 코드를 할당. (원자적)

        - base_code 는 432개 유효 시드에 존재해야 한다.
        - 이미 ACTIVE 인 코드는 중복 발급 방지를 위해 거부.
        """
        with self._write_txn() as conn:
            row = self._get_code_row(conn, base_code)
            if row is None:
                raise CodeNotFound(f"존재하지 않는 base 코드: {base_code}")
            if row["status"] == "ACTIVE":
                raise CodeAlreadyActive(
                    f"이미 ACTIVE 상태입니다: {row['full_code'] or base_code}"
                )

            if request_id:
                # 존재/PENDING 사전 검증 (approve 에서도 재검증)
                req = conn.execute(
                    "SELECT status FROM requests WHERE id=?;", (request_id,)
                ).fetchone()
                if req is None:
                    raise RequestNotFound(f"존재하지 않는 의뢰서: {request_id}")
                if req["status"] != "PENDING":
                    raise RequestNotPending(
                        f"PENDING 상태가 아닌 의뢰서: {request_id} ({req['status']})"
                    )

            full_code = f"{prefix}{base_code}"
            now = _utcnow()
            conn.execute(
                "UPDATE codes SET status='ACTIVE', prefix=?, full_code=?, request_id=?, "
                "issued_to=?, issued_at=?, revoked_at=NULL, force_issued=1 WHERE code=?;",
                (prefix, full_code, request_id, issued_to, now, base_code),
            )
            self._add_history(
                conn, base_code, "FORCE_ISSUED",
                by=approver or issued_to, prefix=prefix,
                full_code=full_code, request_id=request_id,
            )
            if request_id:
                self._approve_request_txn(
                    conn, request_id, base_code=base_code,
                    full_code=full_code, approver=approver,
                )
            return _code_row_to_dict(self._get_code_row(conn, base_code))

    def revoke(self, code_or_full: str, *, by: Optional[str] = None) -> Dict[str, Any]:
        """
        파기 → 원래 순번(제자리)으로 대기열 복원. (원자적)

        base 코드 또는 full 코드 모두 허용.
        SQLite 에서는 status 를 WAITING 으로 되돌리면 score 정렬에 의해
        자동으로 원래 순번 위치로 복귀한다.
        """
        key = code_or_full.upper()
        with self._write_txn() as conn:
            row = self._get_code_row(conn, key)
            if row is None:
                row = conn.execute(
                    "SELECT * FROM codes WHERE full_code=?;", (key,)
                ).fetchone()
            if row is None:
                raise CodeNotFound("코드를 찾을 수 없습니다")
            if row["status"] != "ACTIVE":
                raise CodeNotActive(
                    f"ACTIVE 상태가 아닌 코드는 파기 불가: {row['code']} ({row['status']})"
                )

            base_code = row["code"]
            full_code_before = row["full_code"]
            score = row["score"]
            now = _utcnow()
            self._add_history(conn, base_code, "REVOKED", by=by, full_code=full_code_before)
            # 대기열 복귀: 발급 정보 초기화 + WAITING
            conn.execute(
                "UPDATE codes SET status='WAITING', prefix=NULL, full_code=NULL, "
                "request_id=NULL, issued_to=NULL, issued_at=NULL, revoked_at=?, "
                "force_issued=0 WHERE code=?;",
                (now, base_code),
            )
            return {
                "code": base_code,
                "full_code": full_code_before,
                "score": score,
                "revoked_at": now,
                "returned_to_queue": True,
            }

    # ─────────────────────────── requests ───────────────────────────

    def create_request(
        self, *, requester: str, reason: str,
        desired_prefix: Optional[str] = None, note: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._write_txn() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key='request_seq';"
            ).fetchone()
            seq = (int(row["value"]) if row else 0) + 1
            conn.execute(
                "UPDATE meta SET value=? WHERE key='request_seq';", (str(seq),)
            )
            req_id = f"REQ-{seq:04d}"
            now = _utcnow()
            conn.execute(
                "INSERT INTO requests(id, requester, reason, desired_prefix, status, "
                "created_at) VALUES (?, ?, ?, ?, 'PENDING', ?);",
                (req_id, requester, reason, desired_prefix, now),
            )
            r = conn.execute("SELECT * FROM requests WHERE id=?;", (req_id,)).fetchone()
            return _request_row_to_dict(r)

    def list_requests(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._read() as conn:
            if status:
                cur = conn.execute(
                    "SELECT * FROM requests WHERE status=? ORDER BY created_at DESC;",
                    (status,),
                )
            else:
                cur = conn.execute("SELECT * FROM requests ORDER BY created_at DESC;")
            return [_request_row_to_dict(r) for r in cur.fetchall()]

    def get_request(self, req_id: str) -> Optional[Dict[str, Any]]:
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM requests WHERE id=?;", (req_id,)
            ).fetchone()
            return _request_row_to_dict(row) if row else None

    def stats_requests(self) -> Dict[str, int]:
        with self._read() as conn:
            counts = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0, "TOTAL": 0}
            cur = conn.execute(
                "SELECT status, COUNT(*) AS c FROM requests GROUP BY status;"
            )
            for r in cur.fetchall():
                counts[r["status"]] = r["c"]
                counts["TOTAL"] += r["c"]
            return counts


# ─────────────────────────── 싱글톤 ───────────────────────────
_db_instance: Optional[SqliteDatabase] = None
_db_lock = threading.Lock()


def get_db() -> SqliteDatabase:
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = SqliteDatabase()
    return _db_instance
