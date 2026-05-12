"""
개발/데모용 부트 스크립트.
실제 Redis가 없을 때 fakeredis로 SequenceManager를 띄운다.
운영에서는 사용하지 말 것.
"""
from __future__ import annotations

import logging

import fakeredis
import uvicorn

# 1) SequenceManager 모듈의 redis.Redis.from_url을 fakeredis로 패치
import app.services.sequence_manager as smod

_fake = fakeredis.FakeRedis(decode_responses=True)


class _RedisShim:
    @staticmethod
    def from_url(_url, decode_responses=True):
        return _fake


# redis 모듈 자체를 가짜로 교체 (Redis.from_url만 사용함)
class _RedisModuleShim:
    Redis = _RedisShim


smod.redis = _RedisModuleShim  # type: ignore[attr-defined]

logging.getLogger("ucs").info("Using fakeredis (in-process)")

if __name__ == "__main__":
    import os
    host = os.getenv("UCS_HOST", "0.0.0.0")
    port = int(os.getenv("UCS_PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
