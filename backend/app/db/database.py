"""
JSON Database (RDBMS 대체)
--------------------------
단일 JSON 파일을 데이터 저장소로 사용한다.

Schema
------
{
  "meta": {
    "version": "0.1.0",
    "initialized_at": "ISO-8601",
    "last_updated_at": "ISO-8601",
    "request_seq": <int>
  },
  "codes": {
    "<BASE_CODE>": {                    // 2자리 기본 코드 (예: "A1")
      "code": "A1",
      "score": 1,                       // 원래 순번 (불변, 1~432)
      "status": "WAITING" | "ACTIVE" | "REVOKED",
      "prefix": null | "DEV",           // 발급 시 입력한 Prefix
      "full_code": null | "DEV-A1",     // 최종 조합 코드
      "request_id": null | "REQ-0007",  // 연결된 의뢰서
      "issued_to": null | "string",
      "issued_at": null | "ISO-8601",
      "revoked_at": null | "ISO-8601",
      "force_issued": false,            // 강제 채번 여부
      "history": [
        { "event": "ISSUED"|"REVOKED"|"FORCE_ISSUED", "at": "...", "by": "..." }
      ]
    }
  },
  "requests": {
    "<REQ_ID>": {                       // "REQ-0001" 형식
      "id": "REQ-0001",
      "requester": "홍길동",
      "reason": "신규 서비스 식별자",
      "desired_prefix": null | "DEV",   // 의뢰자가 희망한 Prefix(참고용)
      "status": "PENDING" | "APPROVED" | "REJECTED",
      "issued_code": null | "A1",       // 승인 시 연결된 2자리 base code
      "issued_full_code": null | "DEV-A1",
      "created_at": "ISO-8601",
      "approved_at": null | "ISO-8601",
      "approver": null | "string",
      "note": null | "string"
    }
  }
}

동시성:
  - 파일 락(threading.RLock)으로 멀티스레드 환경에서 직렬화.
  - JSON 쓰기는 모두 atomic(tempfile → os.replace).
  - 멀티프로세스/워커 환경에서는 Redis가 채번 SSOT이며,
    JSON DB는 발급/파기/의뢰서 영속 기록 용도로 사용한다.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.codes import generate_all_codes
from app.core.config import settings


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JsonDatabase:
    """
    단일 JSON 파일 기반 영속 저장소.

    - codes / requests 두 컬렉션 관리
    - atomic write (tempfile → os.replace)
    - threading.RLock 기반 직렬화
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path: Path = Path(path) if path else settings.DB_FILE
        self._lock = threading.RLock()
        self._ensure_initialized()
        self._migrate_if_needed()

    # ─────────────────────────── 내부 I/O ───────────────────────────

    def _ensure_initialized(self) -> None:
        # 존재하고 비어 있지 않은 정상 파일이면 리턴
        if self._path.exists() and self._path.stat().st_size > 0:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)

        codes_dict: Dict[str, Dict[str, Any]] = {}
        for idx, code in enumerate(generate_all_codes(), start=1):
            codes_dict[code] = self._new_code_record(code, idx)

        initial: Dict[str, Any] = {
            "meta": {
                "version": settings.APP_VERSION,
                "initialized_at": _utcnow(),
                "last_updated_at": _utcnow(),
                "request_seq": 0,
            },
            "codes": codes_dict,
            "requests": {},
        }
        self._atomic_write(initial)

    def _migrate_if_needed(self) -> None:
        """구버전(Phase 1) 파일 호환: 누락 필드 보강."""
        with self._lock:
            data = self._read()
            changed = False

            meta = data.setdefault("meta", {})
            if "request_seq" not in meta:
                meta["request_seq"] = 0
                changed = True

            if "requests" not in data:
                data["requests"] = {}
                changed = True

            for code, rec in data.get("codes", {}).items():
                for key, default in (
                    ("prefix", None),
                    ("full_code", None),
                    ("request_id", None),
                    ("force_issued", False),
                ):
                    if key not in rec:
                        rec[key] = default
                        changed = True

            if changed:
                self._atomic_write(data)

    @staticmethod
    def _new_code_record(code: str, score: int) -> Dict[str, Any]:
        return {
            "code": code,
            "score": score,
            "status": "WAITING",
            "prefix": None,
            "full_code": None,
            "request_id": None,
            "issued_to": None,
            "issued_at": None,
            "revoked_at": None,
            "force_issued": False,
            "history": [],
        }

    def _read(self) -> Dict[str, Any]:
        with self._path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        data.setdefault("meta", {})["last_updated_at"] = _utcnow()
        directory = self._path.parent
        fd, tmp_path = tempfile.mkstemp(prefix=".ucs_", suffix=".json.tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

    # ─────────────────────────── 공용 ───────────────────────────

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._read()

    # ─────────────────────────── codes ───────────────────────────

    def list_codes(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._read()
            records = list(data["codes"].values())
            if status:
                records = [r for r in records if r["status"] == status]
            records.sort(key=lambda r: r["score"])
            return records

    def get_code(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._read()["codes"].get(code)

    def mark_issued(
        self,
        code: str,
        *,
        prefix: str,
        request_id: Optional[str] = None,
        issued_to: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        2자리 base code를 ACTIVE로 전환하고 Prefix와 최종 코드를 기록.

        Parameters
        ----------
        code : str          base 2자리 코드 (예: "A1")
        prefix : str        발급 시 입력한 Prefix (예: "DEV")
        request_id : str    연결된 의뢰서 ID (선택)
        issued_to : str     발급 대상(메모/태그)
        force : bool        강제 채번 여부 → history 이벤트 구분
        """
        with self._lock:
            data = self._read()
            rec = data["codes"].get(code)
            if rec is None:
                raise KeyError(f"존재하지 않는 코드: {code}")
            if rec["status"] == "ACTIVE":
                raise ValueError(f"이미 ACTIVE 상태인 코드: {code}")

            now = _utcnow()
            full_code = f"{prefix}{code}"
            rec["status"] = "ACTIVE"
            rec["prefix"] = prefix
            rec["full_code"] = full_code
            rec["request_id"] = request_id
            rec["issued_to"] = issued_to
            rec["issued_at"] = now
            rec["revoked_at"] = None
            rec["force_issued"] = bool(force)
            rec["history"].append(
                {
                    "event": "FORCE_ISSUED" if force else "ISSUED",
                    "at": now,
                    "by": issued_to,
                    "prefix": prefix,
                    "full_code": full_code,
                    "request_id": request_id,
                }
            )
            self._atomic_write(data)
            return rec

    def mark_revoked(self, code: str, by: Optional[str] = None) -> Dict[str, Any]:
        """ACTIVE → REVOKED 전환."""
        with self._lock:
            data = self._read()
            rec = data["codes"].get(code)
            if rec is None:
                raise KeyError(f"존재하지 않는 코드: {code}")
            if rec["status"] != "ACTIVE":
                raise ValueError(
                    f"ACTIVE 상태가 아닌 코드는 파기 불가: {code} ({rec['status']})"
                )
            now = _utcnow()
            rec["status"] = "REVOKED"
            rec["revoked_at"] = now
            rec["history"].append({"event": "REVOKED", "at": now, "by": by})
            self._atomic_write(data)
            return rec

    def reset_to_waiting(self, code: str) -> Dict[str, Any]:
        """
        파기 후 대기열 복귀 시 호출. Prefix/연결정보를 모두 초기화.
        (history는 보존)
        """
        with self._lock:
            data = self._read()
            rec = data["codes"].get(code)
            if rec is None:
                raise KeyError(f"존재하지 않는 코드: {code}")
            rec["status"] = "WAITING"
            rec["prefix"] = None
            rec["full_code"] = None
            rec["request_id"] = None
            rec["issued_to"] = None
            rec["issued_at"] = None
            rec["revoked_at"] = None
            rec["force_issued"] = False
            self._atomic_write(data)
            return rec

    def find_code_by_full(self, full_code: str) -> Optional[Dict[str, Any]]:
        """full_code(예: "DEV-A1")로 base record를 찾는다."""
        with self._lock:
            for rec in self._read()["codes"].values():
                if rec.get("full_code") == full_code:
                    return rec
            return None

    def stats(self) -> Dict[str, int]:
        with self._lock:
            data = self._read()
            counts = {"WAITING": 0, "ACTIVE": 0, "REVOKED": 0, "TOTAL": 0}
            for rec in data["codes"].values():
                counts["TOTAL"] += 1
                counts[rec["status"]] = counts.get(rec["status"], 0) + 1
            return counts

    # ─────────────────────────── requests ───────────────────────────

    def _next_request_id(self, data: Dict[str, Any]) -> str:
        meta = data.setdefault("meta", {})
        seq = int(meta.get("request_seq", 0)) + 1
        meta["request_seq"] = seq
        return f"REQ-{seq:04d}"

    def create_request(
        self,
        *,
        requester: str,
        reason: str,
        desired_prefix: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            req_id = self._next_request_id(data)
            now = _utcnow()
            rec = {
                "id": req_id,
                "requester": requester,
                "reason": reason,
                "desired_prefix": desired_prefix,
                "status": "PENDING",
                "issued_code": None,
                "issued_full_code": None,
                "created_at": now,
                "approved_at": None,
                "approver": None,
                "note": note,
            }
            data["requests"][req_id] = rec
            self._atomic_write(data)
            return rec

    def list_requests(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._read()
            records = list(data["requests"].values())
            if status:
                records = [r for r in records if r["status"] == status]
            records.sort(key=lambda r: r["created_at"], reverse=True)
            return records

    def get_request(self, req_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._read()["requests"].get(req_id)

    def approve_request(
        self,
        req_id: str,
        *,
        base_code: str,
        full_code: str,
        approver: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            req = data["requests"].get(req_id)
            if req is None:
                raise KeyError(f"존재하지 않는 의뢰서: {req_id}")
            if req["status"] != "PENDING":
                raise ValueError(
                    f"PENDING 상태가 아닌 의뢰서는 승인 불가: {req_id} ({req['status']})"
                )
            req["status"] = "APPROVED"
            req["issued_code"] = base_code
            req["issued_full_code"] = full_code
            req["approved_at"] = _utcnow()
            req["approver"] = approver
            self._atomic_write(data)
            return req

    def stats_requests(self) -> Dict[str, int]:
        with self._lock:
            data = self._read()
            counts = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0, "TOTAL": 0}
            for rec in data["requests"].values():
                counts["TOTAL"] += 1
                counts[rec["status"]] = counts.get(rec["status"], 0) + 1
            return counts


# ─────────────────────────── 싱글톤 ───────────────────────────
_db_instance: Optional[JsonDatabase] = None
_db_lock = threading.Lock()


def get_db() -> JsonDatabase:
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = JsonDatabase()
    return _db_instance
