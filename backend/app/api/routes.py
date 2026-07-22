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

저장소: SQLite 단일 SSOT (app.db.sqlite_db). 모든 상태 전이는 원자적 트랜잭션.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.sqlite_db import (
    CodeAlreadyActive,
    CodeNotActive,
    CodeNotFound,
    QueueEmpty,
    RequestNotFound,
    RequestNotPending,
    SqliteDatabase,
    get_db,
)
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


logger = logging.getLogger(__name__)


# ╭───────────────────────────────────────────────────────────╮
# │ Health                                                     │
# ╰───────────────────────────────────────────────────────────╯
health_router = APIRouter(tags=["meta"])


@health_router.get("/health", response_model=HealthResponse)
def health(db: SqliteDatabase = Depends(get_db)) -> HealthResponse:
    ok = db.ping()
    return HealthResponse(
        status="ok",
        redis=ok,                       # 저장소(SQLite) 정상 여부 (스키마 호환 유지)
        queue_size=db.queue_size() if ok else 0,
    )


# ╭───────────────────────────────────────────────────────────╮
# │ Requests (채번 의뢰서)                                     │
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
    db: SqliteDatabase = Depends(get_db),
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
    db: SqliteDatabase = Depends(get_db),
) -> List[RequestRecord]:
    if status_filter and status_filter not in {"PENDING", "APPROVED", "REJECTED"}:
        raise HTTPException(status_code=400, detail="유효하지 않은 status 값")
    return [RequestRecord(**r) for r in db.list_requests(status=status_filter)]


@requests_router.get(
    "/{req_id}",
    response_model=RequestRecord,
    summary="채번 의뢰 단건 조회",
)
def get_request(req_id: str, db: SqliteDatabase = Depends(get_db)) -> RequestRecord:
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
    db: SqliteDatabase = Depends(get_db),
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
    db: SqliteDatabase = Depends(get_db),
) -> PeekResponse:
    items = [CodeRecord(**r) for r in db.peek_next(n)]
    return PeekResponse(next=items)


@codes_router.get(
    "/{code}",
    response_model=CodeRecord,
    summary="코드 단건 조회 (base 코드 또는 full 코드)",
)
def get_code(code: str, db: SqliteDatabase = Depends(get_db)) -> CodeRecord:
    key = code.upper()
    rec = db.get_code(key) or db.find_code_by_full(key)
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
    db: SqliteDatabase = Depends(get_db),
) -> IssueResponse:
    """
    의뢰서 승인 + 대기열 최상단 발급을 **단일 SQLite 트랜잭션**으로 원자 처리.
    (PENDING 검증 → 최소 score WAITING 확보 → ACTIVE 전환 → 의뢰서 APPROVED)
    """
    try:
        rec = db.issue_next_for_request(
            req_id,
            prefix=payload.prefix,
            issued_to=payload.issued_to,
            approver=payload.approver,
        )
    except RequestNotFound:
        raise HTTPException(status_code=404, detail="의뢰서를 찾을 수 없습니다")
    except RequestNotPending as e:
        raise HTTPException(status_code=409, detail=str(e))
    except QueueEmpty as e:
        raise HTTPException(status_code=409, detail=str(e))

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
    db: SqliteDatabase = Depends(get_db),
) -> IssueResponse:
    """
    관리자 권한으로 큐 상태를 무시하고 특정 base 코드를 강제 할당한다. (원자적)

    제약:
      - base_code는 432개 유효 시드에 포함되어야 한다.
      - 현재 ACTIVE 상태인 코드는 강제 할당 불가 (중복 발급 방지).
    """
    try:
        issued = db.force_issue(
            base_code=payload.base_code,
            prefix=payload.prefix,
            request_id=payload.request_id,
            issued_to=payload.issued_to,
            approver=payload.approver,
            reason=payload.reason,
        )
    except CodeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CodeAlreadyActive as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RequestNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RequestNotPending as e:
        raise HTTPException(status_code=409, detail=str(e))

    logger.warning(
        "FORCE_ISSUED base=%s prefix=%s full=%s by=%s reason=%s",
        payload.base_code, payload.prefix, issued["full_code"],
        payload.approver, payload.reason,
    )

    return IssueResponse(
        request_id=payload.request_id,
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
    db: SqliteDatabase = Depends(get_db),
) -> RevokeResponse:
    """
    Path Parameter는 base 코드(`A1`) 또는 full 코드(`DEVA1`) 둘 다 허용한다.
    SQLite 에서 status 를 WAITING 으로 되돌리면 score 정렬로 원래 순번에 자동 복귀.
    """
    try:
        r = db.revoke(code, by=by)
    except CodeNotFound:
        raise HTTPException(status_code=404, detail="코드를 찾을 수 없습니다")
    except CodeNotActive as e:
        raise HTTPException(status_code=409, detail=str(e))

    return RevokeResponse(
        code=r["code"],
        full_code=r["full_code"],
        score=r["score"],
        revoked_at=r["revoked_at"],
        returned_to_queue=r["returned_to_queue"],
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
def dashboard(db: SqliteDatabase = Depends(get_db)) -> DashboardResponse:
    code_counts = db.stats()
    req_counts = db.stats_requests()
    storage_ok = db.ping()
    queue_size = db.queue_size()

    total = code_counts.get("TOTAL", 0)
    active = code_counts.get("ACTIVE", 0)
    usage_pct = round((active / total * 100), 1) if total else 0.0

    preview = [NextPreviewItem(code=r["code"], score=r["score"]) for r in db.peek_next(5)]

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
        redis_ok=storage_ok,            # 저장소 정상 여부 (스키마 호환 유지)
    )


# ╭───────────────────────────────────────────────────────────╮
# │ 통합 라우터                                                │
# ╰───────────────────────────────────────────────────────────╯
def get_routers() -> List[APIRouter]:
    return [health_router, requests_router, codes_router, dashboard_router]
