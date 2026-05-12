"""
Sequence Manager (Redis ZSET 기반 채번 엔진)
-------------------------------------------
유니크 2자리 코드(총 432개)를 순차 발급하고, 파기 시 원래 순번으로 복원한다.

Redis 자료구조
--------------
KEY  : settings.REDIS_KEY_QUEUE  (default: "ucs:code:queue")
TYPE : Sorted Set (ZSET)
- member : 코드 문자열 (예: "A1", "1B")
- score  : 1 ~ 432 (코드의 "원래 순번" — 불변)

핵심 연산
---------
- bootstrap()       : 시스템 기동 시 ZSET을 432개로 시드(존재 시 보존).
- pop_code()        : ZPOPMIN 으로 가장 앞선 코드를 원자적으로 추출.
- return_code(code) : 원래 순번(Score)을 찾아 ZADD로 재삽입.
- peek_next(n)      : 다음 발급 예정 N개 미리보기 (제거 없음).
- queue_size()      : 현재 대기열 크기.

동시성:
  - ZPOPMIN / ZADD 모두 Redis 단일 명령으로 원자성 보장.
  - 다중 워커/프로세스 환경에서도 동일 코드 중복 발급이 발생하지 않음.

복원 시맨틱:
  - 파기된 코드는 원래 Score(1~432)로 다시 ZADD되므로,
    같은 Score를 가진 대기 코드 사이의 정렬 위치(원래 순번 = 제자리)로 정확히 복귀.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import redis
from redis.exceptions import RedisError

from app.core.codes import code_to_score, generate_all_codes
from app.core.config import settings


logger = logging.getLogger(__name__)


class SequenceManager:
    """
    Redis ZSET 기반 채번 매니저.

    인스턴스는 main.py의 lifespan에서 생성/주입하고,
    FastAPI 라우터는 의존성 주입을 통해 사용한다.
    """

    def __init__(self, redis_url: Optional[str] = None, key: Optional[str] = None) -> None:
        self._redis = redis.Redis.from_url(
            redis_url or settings.REDIS_URL,
            decode_responses=True,
        )
        self._key = key or settings.REDIS_KEY_QUEUE

    # ─────────────────────────── 부트스트랩 ───────────────────────────

    def ping(self) -> bool:
        try:
            return bool(self._redis.ping())
        except RedisError as e:
            logger.error("Redis ping failed: %s", e)
            return False

    def bootstrap(self, force: bool = False) -> int:
        """
        시스템 기동 시 ZSET에 432개 코드를 시드한다.

        Parameters
        ----------
        force : bool
            True면 기존 ZSET을 삭제하고 재시드. (운영 환경에서는 신중히)

        Returns
        -------
        int
            현재 ZSET 크기 (시드 후).
        """
        if force:
            self._redis.delete(self._key)

        existing = self._redis.zcard(self._key)
        if existing > 0 and not force:
            logger.info("Queue already initialized (size=%d); skip bootstrap.", existing)
            return existing

        mapping = {code: idx for idx, code in enumerate(generate_all_codes(), start=1)}
        # 단일 ZADD 호출로 일괄 삽입
        added = self._redis.zadd(self._key, mapping=mapping, nx=True)
        size = self._redis.zcard(self._key)
        logger.info("Bootstrap complete: added=%s, total=%d", added, size)
        return size

    # ─────────────────────────── 핵심 연산 ───────────────────────────

    def pop_code(self) -> Optional[Tuple[str, int]]:
        """
        가장 앞선 코드를 원자적으로 추출.

        Returns
        -------
        (code, score) | None
            대기열이 비어 있으면 None.
        """
        result = self._redis.zpopmin(self._key, count=1)
        if not result:
            return None
        code, score = result[0]
        return code, int(score)

    def return_code(self, code: str) -> int:
        """
        파기된 코드를 원래 순번(Score)으로 ZSET에 재삽입한다.

        Parameters
        ----------
        code : str
            복원할 코드.

        Returns
        -------
        int
            복원된 원래 순번(Score).

        Raises
        ------
        ValueError
            코드가 432개 시드에 존재하지 않는 경우.
        RuntimeError
            이미 대기열에 존재해 복원이 불필요한 경우.
        """
        score = code_to_score(code)
        if score is None:
            raise ValueError(f"유효하지 않은 코드: {code}")

        # NX 옵션: 이미 존재하면 추가하지 않음 → 중복 복원 방지
        added = self._redis.zadd(self._key, mapping={code: score}, nx=True)
        if added == 0:
            raise RuntimeError(f"이미 대기열에 존재하는 코드: {code}")
        logger.info("Returned code=%s to score=%d", code, score)
        return score

    # ─────────────────────────── 조회 ───────────────────────────

    def force_pop(self, code: str) -> Tuple[str, int]:
        """
        강제 채번: 특정 코드를 대기열 상태와 무관하게 확보한다.

        - 유욨성(432개 시드 포함 여부) 검증
        - 큐에 존재하면 ZREM 으로 제거
        - 존재하지 않아도 (이미 발급되어 있더라도) 성공 리턴 —
          이 경우 호출측은 DB 상태를 재확인하여 ACTIVE 중복 발급을 막아야 한다.

        Returns
        -------
        (code, score) : 원래 순번(score)과 함께 반환.
        """
        score = code_to_score(code)
        if score is None:
            raise ValueError(f"유효하지 않은 코드: {code}")
        # 큐에 존재하면 제거 (없으면 0을 반환, 에러 아님)
        self._redis.zrem(self._key, code)
        logger.info("Force-popped code=%s (score=%d)", code, score)
        return code, score

    def queue_size(self) -> int:
        return int(self._redis.zcard(self._key))

    def peek_next(self, n: int = 10) -> List[Tuple[str, int]]:
        """다음 발급 예정 N개를 미리보기 (대기열에서 제거하지 않음)."""
        rows = self._redis.zrange(self._key, 0, n - 1, withscores=True)
        return [(member, int(score)) for member, score in rows]

    def contains(self, code: str) -> bool:
        return self._redis.zscore(self._key, code) is not None

    def score_of(self, code: str) -> Optional[int]:
        s = self._redis.zscore(self._key, code)
        return int(s) if s is not None else None

    # ─────────────────────────── 유지보수 ───────────────────────────

    def reset_all(self) -> int:
        """ZSET을 완전히 비우고 432개로 재시드. (관리자/테스트 전용)"""
        self._redis.delete(self._key)
        return self.bootstrap(force=True)


# ─────────────────────────── 싱글톤 ───────────────────────────
_manager: Optional[SequenceManager] = None


def get_sequence_manager() -> SequenceManager:
    """FastAPI 의존성 주입에서 사용할 단일 인스턴스 반환."""
    global _manager
    if _manager is None:
        _manager = SequenceManager()
    return _manager
