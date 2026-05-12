"""
Code Generator
--------------
432개 유니크 2자리 코드를 결정론적으로(순서 고정) 생성한다.

규칙:
  - 영문자: A~Z 중 O, I 제외 → 24자
  - 숫자  : 1~9 (0 제외)     → 9자
  - 1순위: 영문+숫자 (A1~Z9)  → 24 × 9 = 216개
  - 2순위: 숫자+영문 (1A~9Z)  → 9 × 24 = 216개
  - 합계 : 432개

이 모듈이 반환하는 리스트의 인덱스(+1)는 곧 "원래 순번(Score)"이며,
Redis ZSET 초기화와 파기 시 복원에서 공통으로 사용된다.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from .config import settings


_ALL_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ALL_DIGITS = "0123456789"


def _letters() -> str:
    return "".join(c for c in _ALL_LETTERS if c not in settings.EXCLUDED_LETTERS)


def _digits() -> str:
    return "".join(c for c in _ALL_DIGITS if c not in settings.EXCLUDED_DIGITS)


@lru_cache(maxsize=1)
def generate_all_codes() -> List[str]:
    """
    432개 코드를 발급 순서대로 반환.

    Returns
    -------
    list[str]
        ["A1", "A2", ..., "Z9", "1A", "1B", ..., "9Z"]  (총 432개)
    """
    letters = _letters()   # 24자
    digits = _digits()     # 9자

    # 1순위: 영문 + 숫자 (A1, A2, ... A9, B1, ..., Z9)
    primary = [f"{L}{D}" for L in letters for D in digits]

    # 2순위: 숫자 + 영문 (1A, 1B, ... 1Z, 2A, ..., 9Z)
    secondary = [f"{D}{L}" for D in digits for L in letters]

    codes = primary + secondary
    assert len(codes) == 432, f"코드 총 개수 불일치: {len(codes)} != 432"
    assert len(set(codes)) == 432, "코드 중복 발생"
    return codes


def code_to_score(code: str) -> int | None:
    """
    코드 → 원래 순번(1-based Score) 매핑.

    Returns
    -------
    int | None
        해당 코드의 1~432 사이 순번. 없으면 None.
    """
    try:
        return generate_all_codes().index(code) + 1
    except ValueError:
        return None
