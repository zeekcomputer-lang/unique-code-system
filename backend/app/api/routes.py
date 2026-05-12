"""
API Routes
----------
유니크 코드 통합 관리 시스템의 모든 엔드포인트.

라우터 그룹
-----------
- /api/requests/*     : 채번 의뢰서 (접수/조회)
- /api/codes/*        : 코드 발급/파기/강제채번/조회/미리보기
- /api/dashboard      : 대시보드 통계
- /health             : 헬스 체크
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.database import JsonDatabase, get_db
from app.models.schemas import (
    CodeRecord,
    CodeStats,
    CreateRequestPayload,
    DashboardResponse,
    ForceIssuePayload,
    HealthResponse,
    IssueByRequestPayload,
    IssueResponse,
    NextPreviewItem,
    PeekResponse,
    RequestRecord,
    RequestStats,
    RevokeResponse,
)
from app.services.sequence_manager import SequenceManager, get_sequence_manager


logger = logging.getLogger(__name__)


# ╭───────────────────────────────────────────────────────────╮
# │ Health                                                    │
# ╰───────────────────────────────────────────────────────────╯
health_router = APIRouter(tags=["meta"])


@health_router.get("/health", response_model=HealthResponse)
def health(seq: SequenceManager = Depends(get_sequence_manager)) -> HealthResponse:
    redis_ok = seq.ping()
    return HealthResponse(
        status="ok",
        redis=redis_ok,
        queue_size=seq.queue_size() if redis_ok else 0,
    )


# ╭───────────────────────────────────────────────────────────╮
# │ Requests (채번 의뢰서)                                    │
# ╰───────────────────────────────────────────────────────────╯
requests_router = APIRouter(prefix="/api/requests", tags=["requests"])


@requests_router.post(
    "",
    response_model=RequestRecord,
    status_code=status.HTTP_201_CREATED,
    summary="채번 의뢰 접수 (PENDING)",
)
def create_request(
    payload: CreateRequestPayload,
    db: JsonDatabase = Depends(get_db),
) -> RequestRecord:
    rec = db.create_request(
        requester=payload.requester,
        reason=payload.reason,
        desired_prefix=payload.desired_prefix,
        note=payload.note,
    )
    return RequestRecord(**rec)


@requests_router.get(
    "",
    response_model=List[RequestRecord],
    summary="채번 의뢰 목록 조회",
)
def list_requests(
    status_filter: Optional[str] = Query(
        default=None, alias="status",
        description="PENDING | APPROVED | REJECTED",
    ),
    db: JsonDatabase = Depends(get_db),
) -> List[RequestRecord]:
    if status_filter and status_filter not in {"PENDING", "APPROVED", "REJECTED"}:
        raise HTTPException(status_code=400, detail="유효하지 않은 status 값")
    return [RequestRecord(**r) for r in db.list_requests(status=status_filter)]


@requests_router.get(
    "/{req_id}",
    response_model=RequestRecord,
    summary="채번 의뢰 단건 조회",
)
def get_request(req_id: str, db: JsonDatabase = Depends(get_db)) -> RequestRecord:
    rec = db.get_request(req_id)
    if not rec:
        raise HTTPException(status_code=404, detail="의뢰서를 찾을 수 없습니다")
    return RequestRecord(**rec)


# ╭───────────────────────────────────────────────────────────╮
# │ Codes (발급/파기/강제/조회)                                │
# ╰───────────────────────────────────────────────────────────╯
codes_router = APIRouter(prefix="/api/codes", tags=["codes"])


# ── 조회 ────────────────────────────────────────────────────
@codes_router.get(
    "",
    response_model=List[CodeRecord],
    summary="코드 목록 조회 (status 필터 가능)",
)
def list_codes(
    status_filter: Optional[str] = Query(
        default=None, alias="status",
        description="WAITING | ACTIVE | REVOKED",
    ),
    db: JsonDatabase = Depends(get_db),
) -> List[CodeRecord]:
    if status_filter and status_filter not in {"WAITING", "ACTIVE", "REVOKED"}:
        raise HTTPException(status_code=400, detail="유효하지 않은 status 값")
    return [CodeRecord(**r) for r in db.list_codes(status=status_filter)]


@codes_router.get(
    "/peek",
    response_model=PeekResponse,
    summary="다음 발급 예정 N개 미리보기",
)
def peek_next(
    n: int = Query(default=10, ge=1, le=100),
    seq: SequenceManager = Depends(get_sequence_manager),
    db: JsonDatabase = Depends(get_db),
) -> PeekResponse:
    items: List[CodeRecord] = []
    for code, score in seq.peek_next(n):
        rec = db.get_code(code)
        items.append(CodeRecord(**rec) if rec else CodeRecord(code=code, score=score, status="WAITING"))
    return PeekResponse(next=items)


@codes_router.get(
    "/{code}",
    response_model=CodeRecord,
    summary="코드 단건 조회 (base 코드 또는 full 코드)",
)
def get_code(code: str, db: JsonDatabase = Depends(get_db)) -> CodeRecord:
    key = code.upper()
    rec = db.get_code(key)
    if not rec:
        # full_code(예: DEV-A1)로도 조회
        rec = db.find_code_by_full(key)
    if not rec:
        raise HTTPException(status_code=404, detail="코드를 찾을 수 없습니다")
    return CodeRecord(**rec)


# ── 발급 ────────────────────────────────────────────────────
@codes_router.post(
    "/issue/{req_id}",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="채번 승인 및 발급 (의뢰서 기반 + 수기 Prefix)",
)
def issue_by_request(
    req_id: str,
    payload: IssueByRequestPayload,
    seq: SequenceManager = Depends(get_sequence_manager),
    db: JsonDatabase = Depends(get_db),
) -> IssueResponse:
    """
    1) 의뢰서 PENDING 검증
    2) Redis ZPOPMIN으로 2자리 base 코드 추출 (원자성)
    3) DB에 ACTIVE 기록 + 의뢰서 APPROVED 전환
    4) 실패 시 Redis 큐로 롤백
    """
    req = db.get_request(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="의뢰서를 찾을 수 없습니다")
    if req["status"] != "PENDING":
        raise HTTPException(
            status_code=409,
            detail=f"PENDING 상태가 아닙니다 (현재: {req['status']})",
        )

    popped = seq.pop_code()
    if popped is None:
        raise HTTPException(
            status_code=409,
            detail="대기열이 비어 있습니다 (발급 가능 코드 없음)",
        )
    base_code, score = popped
    full_code = f"{payload.prefix}-{base_code}"

    try:
        rec = db.mark_issued(
            base_code,
            prefix=payload.prefix,
            request_id=req_id,
            issued_to=payload.issued_to,
            force=False,
        )
        db.approve_request(
            req_id,
            base_code=base_code,
            full_code=full_code,
            approver=payload.approver,
        )
    except Exception as e:
        logger.exception("발급 처리 실패 → 큐 롤백 시도 (%s)", base_code)
        try:
            seq.return_code(base_code)
        except Exception:
            logger.exception("큐 롤백도 실패: %s", base_code)
        raise HTTPException(status_code=500, detail=f"발급 처리 중 오류: {e}")

    return IssueResponse(
        request_id=req_id,
        base_code=rec["code"],
        full_code=rec["full_code"],
        prefix=rec["prefix"],
        score=rec["score"],
        issued_to=rec["issued_to"],
        issued_at=rec["issued_at"],
        force_issued=False,
    )


# ── 강제 채번 ───────────────────────────────────────────────
@codes_router.post(
    "/force",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="강제 수기 채번 (대기열 무시하고 특정 코드 할당)",
)
def force_issue(
    payload: ForceIssuePayload,
    seq: SequenceManager = Depends(get_sequence_manager),
    db: JsonDatabase = Depends(get_db),
) -> IssueResponse:
    """
    관리자 권한으로 큐 상태를 무시하고 특정 base 코드를 강제 할당한다.

    제약:
      - base_code는 432개 유효 시드에 포함되어야 한다.
      - 현재 ACTIVE 상태인 코드는 강제 할당 불가 (중복 발급 방지).
    """
    base_code = payload.base_code
    rec = db.get_code(base_code)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"존재하지 않는 base 코드: {base_code}")
    if rec["status"] == "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail=f"이미 ACTIVE 상태입니다: {rec.get('full_code') or base_code}",
        )

    # 의뢰서 연결 검증(선택)
    req_id = payload.request_id
    if req_id:
        req = db.get_request(req_id)
        if not req:
            raise HTTPException(status_code=404, detail=f"존재하지 않는 의뢰서: {req_id}")
        if req["status"] != "PENDING":
            raise HTTPException(
                status_code=409,
                detail=f"PENDING 상태가 아닌 의뢰서: {req_id} ({req['status']})",
            )

    # Redis에서 강제 제거 (없어도 OK)
    try:
        seq.force_pop(base_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    full_code = f"{payload.prefix}-{base_code}"

    try:
        issued = db.mark_issued(
            base_code,
            prefix=payload.prefix,
            request_id=req_id,
            issued_to=payload.issued_to,
            force=True,
        )
        if req_id:
            db.approve_request(
                req_id,
                base_code=base_code,
                full_code=full_code,
                approver=payload.approver,
            )
    except Exception as e:
        logger.exception("강제 채번 DB 기록 실패 → 큐 복원 시도 (%s)", base_code)
        try:
            seq.return_code(base_code)
        except Exception:
            logger.exception("큐 복원 실패: %s", base_code)
        raise HTTPException(status_code=500, detail=f"강제 채번 처리 중 오류: {e}")

    logger.warning(
        "FORCE_ISSUED base=%s prefix=%s full=%s by=%s reason=%s",
        base_code, payload.prefix, full_code, payload.approver, payload.reason,
    )

    return IssueResponse(
        request_id=req_id,
        base_code=issued["code"],
        full_code=issued["full_code"],
        prefix=issued["prefix"],
        score=issued["score"],
        issued_to=issued["issued_to"],
        issued_at=issued["issued_at"],
        force_issued=True,
    )


# ── 파기 ────────────────────────────────────────────────────
@codes_router.post(
    "/revoke/{code}",
    response_model=RevokeResponse,
    summary="파기 → 원래 순번(제자리)로 대기열 복원",
)
def revoke(
    code: str,
    by: Optional[str] = Query(default=None, max_length=128),
    seq: SequenceManager = Depends(get_sequence_manager),
    db: JsonDatabase = Depends(get_db),
) -> RevokeResponse:
    """
    Path Parameter는 base 코드(`A1`) 또는 full 코드(`DEV-A1`) 둘 다 허용한다.
    """
    key = code.upper()
    rec = db.get_code(key) or db.find_code_by_full(key)
    if not rec:
        raise HTTPException(status_code=404, detail="코드를 찾을 수 없습니다")

    base_code: str = rec["code"]
    full_code_before: Optional[str] = rec.get("full_code")

    try:
        revoked = db.mark_revoked(base_code, by=by)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 원래 순번으로 큐에 복원
    try:
        restored_score = seq.return_code(base_code)
    except RuntimeError:
        logger.warning("이미 큐에 존재: %s — DB만 WAITING 동기화", base_code)
        db.reset_to_waiting(base_code)
        return RevokeResponse(
            code=base_code,
            full_code=full_code_before,
            score=revoked["score"],
            revoked_at=revoked["revoked_at"],
            returned_to_queue=True,
        )

    db.reset_to_waiting(base_code)

    return RevokeResponse(
        code=base_code,
        full_code=full_code_before,
        score=restored_score,
        revoked_at=revoked["revoked_at"] or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        returned_to_queue=True,
    )


# ╭───────────────────────────────────────────────────────────╮
# │ Dashboard                                                  │
# ╰───────────────────────────────────────────────────────────╯
dashboard_router = APIRouter(prefix="/api", tags=["dashboard"])


@dashboard_router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="대시보드 통계 (코드/의뢰서/큐 잔여/미리보기)",
)
def dashboard(
    db: JsonDatabase = Depends(get_db),
    seq: SequenceManager = Depends(get_sequence_manager),
) -> DashboardResponse:
    code_counts = db.stats()
    req_counts = db.stats_requests()
    redis_ok = seq.ping()
    queue_size = seq.queue_size() if redis_ok else 0

    total = code_counts.get("TOTAL", 0)
    active = code_counts.get("ACTIVE", 0)
    usage_pct = round((active / total * 100), 1) if total else 0.0

    preview = (
        [NextPreviewItem(code=c, score=s) for c, s in seq.peek_next(5)]
        if redis_ok else []
    )

    return DashboardResponse(
        codes=CodeStats(
            total=total,
            active=active,
            waiting=code_counts.get("WAITING", 0),
            revoked=code_counts.get("REVOKED", 0),
            remaining_in_queue=queue_size,
            usage_pct=usage_pct,
        ),
        requests=RequestStats(
            total=req_counts.get("TOTAL", 0),
            pending=req_counts.get("PENDING", 0),
            approved=req_counts.get("APPROVED", 0),
            rejected=req_counts.get("REJECTED", 0),
        ),
        next_preview=preview,
        redis_ok=redis_ok,
    )


# ╭───────────────────────────────────────────────────────────╮
# │ 통합 라우터                                                │
# ╰───────────────────────────────────────────────────────────╯
def get_routers() -> List[APIRouter]:
    return [health_router, requests_router, codes_router, dashboard_router]
