"""
FastAPI Entry Point
-------------------
- 앱 부팅 시 SQLite 단일 SSOT 초기화(스키마 + 432 코드 시드)
- 통합 API 라우터 마운트
- 단일 포트(기본 8099)에서 정적 프론트엔드(frontend/)까지 함께 서빙
  → UI 와 API 가 동일 오리진 → 클라이언트는 상대경로(`UCS_API_BASE=""`)로 접근
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import get_routers
from app.core.config import settings
from app.db.sqlite_db import get_db


logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ucs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    db = get_db()
    logger.info(
        "SQLite DB ready (%s): codes=%s requests=%s",
        settings.DB_FILE, db.stats(), db.stats_requests(),
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api", tags=["meta"])
def api_info() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


# 통합 API 라우터 등록 (정적 마운트보다 먼저 → 경로 우선순위 확보)
for r in get_routers():
    app.include_router(r)


# 정적 프론트엔드 서빙 (단일 포트 통합). API/문서 라우트 등록 이후 "/" 에 마운트.
if settings.SERVE_FRONTEND and settings.FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(settings.FRONTEND_DIR), html=True),
        name="frontend",
    )
    logger.info("Serving frontend from %s at '/'", settings.FRONTEND_DIR)
else:
    logger.warning(
        "Frontend 정적 서빙 비활성(경로 없음/off): %s", settings.FRONTEND_DIR
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
