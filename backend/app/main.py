"""
FastAPI Entry Point
-------------------
- 앱 부팅 시 JSON DB 초기화 + Redis ZSET 시드(bootstrap)
- 통합 라우터 마운트
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import get_routers
from app.core.config import settings
from app.db.database import get_db
from app.services.sequence_manager import get_sequence_manager


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
    logger.info("JSON DB ready: codes=%s requests=%s", db.stats(), db.stats_requests())

    seq = get_sequence_manager()
    if not seq.ping():
        logger.error("Redis 연결 실패: %s", settings.REDIS_URL)
    else:
        size = seq.bootstrap(force=False)
        logger.info("Redis queue ready: size=%d (key=%s)", size, settings.REDIS_KEY_QUEUE)

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


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


# 통합 라우터 등록
for r in get_routers():
    app.include_router(r)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
