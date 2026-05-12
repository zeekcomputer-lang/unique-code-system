"""
Pydantic Schemas
----------------
API 요청/응답 모델 정의.
"""
from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


CodeStatus = Literal["WAITING", "ACTIVE", "REVOKED"]
RequestStatus = Literal["PENDING", "APPROVED", "REJECTED"]


# ─────────────────────────── 공통 ───────────────────────────
class HealthResponse(BaseModel):
    status: str = "ok"
    redis: bool
    queue_size: int


# ─────────────────────────── Prefix 검증 ───────────────────────────
# Prefix 규칙:
#   - 영문(A-Z, a-z) + 숫자(0-9) 허용
#   - 1~16자
#   - 자동 대문자 변환
_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")


def _validate_prefix(value: str) -> str:
    v = (value or "").strip().upper()
    if not _PREFIX_PATTERN.match(v):
        raise ValueError("Prefix는 영문·숫자만 1~16자로 입력해야 합니다.")
    return v


# ─────────────────────────── 코드(Codes) ───────────────────────────
class CodeRecord(BaseModel):
    code: str = Field(..., description="2자리 base 코드 (예: A1)")
    score: int = Field(..., description="원래 순번 (1~432, 불변)")
    status: CodeStatus
    prefix: Optional[str] = None
    full_code: Optional[str] = Field(None, description="{prefix}-{base} 형식")
    request_id: Optional[str] = None
    issued_to: Optional[str] = None
    issued_at: Optional[str] = None
    revoked_at: Optional[str] = None
    force_issued: bool = False


class IssueByRequestPayload(BaseModel):
    """POST /api/codes/issue/{req_id} 페이로드."""
    prefix: str = Field(..., description="수기로 입력한 Prefix (영문 1~16자)")
    issued_to: Optional[str] = Field(default=None, max_length=128)
    approver: Optional[str] = Field(default=None, max_length=128)

    @field_validator("prefix")
    @classmethod
    def _v_prefix(cls, v: str) -> str:
        return _validate_prefix(v)


class IssueResponse(BaseModel):
    request_id: Optional[str] = None
    base_code: str = Field(..., description="2자리 base 코드")
    full_code: str = Field(..., description="{prefix}-{base}")
    prefix: str
    score: int = Field(..., description="원래 순번 (복원용)")
    issued_to: Optional[str] = None
    issued_at: str
    force_issued: bool = False


class ForceIssuePayload(BaseModel):
    """POST /api/codes/force 페이로드 — 큐 상태 무시하고 특정 코드 강제 할당."""
    base_code: str = Field(..., description="할당할 2자리 base 코드 (예: A1)")
    prefix: str
    request_id: Optional[str] = Field(
        default=None, description="연결할 의뢰서 ID(선택)"
    )
    issued_to: Optional[str] = Field(default=None, max_length=128)
    approver: Optional[str] = Field(default=None, max_length=128)
    reason: Optional[str] = Field(
        default=None,
        description="강제 채번 사유(감사 목적 권장)",
        max_length=256,
    )

    @field_validator("base_code")
    @classmethod
    def _v_base(cls, v: str) -> str:
        v2 = (v or "").strip().upper()
        if len(v2) != 2:
            raise ValueError("base_code는 2자리여야 합니다.")
        return v2

    @field_validator("prefix")
    @classmethod
    def _v_prefix(cls, v: str) -> str:
        return _validate_prefix(v)


class RevokeResponse(BaseModel):
    code: str = Field(..., description="파기된 base 코드")
    full_code: Optional[str] = Field(None, description="파기 전 최종 코드")
    score: int = Field(..., description="대기열로 복귀한 원래 순번")
    revoked_at: str
    returned_to_queue: bool = True


class PeekResponse(BaseModel):
    next: List[CodeRecord]


# ─────────────────────────── 의뢰서(Requests) ───────────────────────────
class RequestRecord(BaseModel):
    id: str
    requester: str
    reason: str
    desired_prefix: Optional[str] = None
    status: RequestStatus
    issued_code: Optional[str] = None
    issued_full_code: Optional[str] = None
    created_at: str
    approved_at: Optional[str] = None
    approver: Optional[str] = None
    note: Optional[str] = None


class CreateRequestPayload(BaseModel):
    requester: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=1, max_length=512)
    desired_prefix: Optional[str] = Field(
        default=None, description="희망 Prefix(참고용, 승인 시 변경 가능)"
    )
    note: Optional[str] = Field(default=None, max_length=512)

    @field_validator("desired_prefix")
    @classmethod
    def _v_prefix(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return _validate_prefix(v)


# ─────────────────────────── 대시보드 ───────────────────────────
class CodeStats(BaseModel):
    total: int
    active: int
    waiting: int
    revoked: int
    remaining_in_queue: int = Field(
        ..., description="Redis 대기열에 남은 발급 가능 개수"
    )
    usage_pct: float = Field(..., description="ACTIVE / TOTAL × 100 (소수 1자리)")


class RequestStats(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int


class NextPreviewItem(BaseModel):
    code: str
    score: int


class DashboardResponse(BaseModel):
    codes: CodeStats
    requests: RequestStats
    next_preview: List[NextPreviewItem]
    redis_ok: bool
