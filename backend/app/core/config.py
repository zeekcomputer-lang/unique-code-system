"""
Application Settings
--------------------
환경변수 기반 설정. 운영 시 .env 또는 시스템 환경변수에서 주입.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Final


BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]   # backend/
DATA_DIR: Final[Path] = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    # ── App
    APP_NAME: str = "Unique Code Management System"
    APP_VERSION: str = "0.4.0"
    DEBUG: bool = os.getenv("UCS_DEBUG", "false").lower() == "true"

    # ── HTTP
    HOST: str = os.getenv("UCS_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("UCS_PORT", "8099"))

    # ── 정적 프론트엔드 (단일 포트 통합 서빙)
    #    기본: 프로젝트 루트의 frontend/ 를 FastAPI 가 직접 서빙 → UI+API 동일 오리진.
    SERVE_FRONTEND: bool = os.getenv("UCS_SERVE_FRONTEND", "true").lower() == "true"
    FRONTEND_DIR: Path = Path(
        os.getenv("UCS_FRONTEND_DIR", str(BASE_DIR.parent / "frontend"))
    )

    # ── SQLite 단일 SSOT
    DB_FILE: Path = DATA_DIR / os.getenv("UCS_DB_FILE", "ucs.sqlite3")

    # ── 코드 채번 규칙
    EXCLUDED_LETTERS: frozenset[str] = frozenset({"O", "I"})
    EXCLUDED_DIGITS: frozenset[str] = frozenset({"0"})
    # 총 24 × 9 × 2 = 432개


settings = Settings()
