# Unique Code Management System — Backend

FastAPI 기반 채번 엔진. **JSON DB (영속 기록) + Redis ZSET (대기열)** 혼합 구조.

## 📁 폴더 구조

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py          # 환경설정 + 코드 제외 문자 정의
│   │   └── codes.py           # 432개 코드 결정론적 생성 (A1~Z9, 1A~9Z)
│   ├── db/
│   │   └── database.py        # JSON 파일 영속 저장소 (atomic write + RLock)
│   ├── services/
│   │   └── sequence_manager.py# Redis ZSET 채번 엔진 (ZPOPMIN/ZADD)
│   ├── models/
│   │   └── schemas.py         # Pydantic 요청/응답 모델
│   ├── routers/
│   │   └── codes.py           # /api/codes/* 엔드포인트
│   └── main.py                # FastAPI 진입점 + lifespan 부트스트랩
├── data/
│   └── ucs.json               # 런타임 생성 (gitignore 권장)
├── requirements.txt
└── .env.example
```

## 🧮 코드 생성 규칙 (총 432개 고정)

- 영문자 24자 (A~Z 중 **O, I 제외**)
- 숫자 9자 (1~9, **0 제외**)
- **1순위**: 영문+숫자 (A1, A2, ... Z9) — 216개
- **2순위**: 숫자+영문 (1A, 1B, ... 9Z) — 216개
- 발급 순서는 위 순서로 고정 (랜덤 ❌, Sequential ✅)

## 🔁 채번/복원 시맨틱

| 동작 | Redis 명령 | 효과 |
|------|------------|------|
| 시드 | `ZADD nx` | 432개 코드를 score 1~432로 일괄 삽입 |
| 발급 | `ZPOPMIN` | 가장 앞선 코드 1건 원자 추출 (동시성 보장) |
| 파기 → 복원 | `ZADD nx` | 코드의 **원래 score**로 재삽입 → 제자리 복귀 |

> 파기된 코드는 **무조건 원래 순번 위치**로 돌아간다. 대기열 내 발급 순서가 보존됨.

## 🚀 실행

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 필요 시 수정

# Redis가 로컬에 떠 있어야 함 (redis://localhost:6379/0)
python -m app.main
# 또는
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API 문서: <http://localhost:8000/docs>

## 🔌 주요 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET    | `/health`                 | Redis 연결 + 큐 크기 |
| GET    | `/api/codes`              | 코드 목록 (status 필터 가능) |
| GET    | `/api/codes/stats`        | 상태별 통계 |
| GET    | `/api/codes/peek?n=10`    | 다음 발급 예정 N개 미리보기 |
| GET    | `/api/codes/{code}`       | 단건 조회 |
| POST   | `/api/codes/issue`        | **발급** (ZPOPMIN) |
| POST   | `/api/codes/{code}/revoke`| **파기** → 원래 순번 복원 |

## 🧪 빠른 테스트

```bash
# 발급
curl -X POST localhost:8000/api/codes/issue \
  -H 'Content-Type: application/json' \
  -d '{"issued_to": "test-user"}'
# → { "code": "A1", "score": 1, ... }

# 파기 (제자리로 복원)
curl -X POST localhost:8000/api/codes/A1/revoke \
  -H 'Content-Type: application/json' \
  -d '{"by": "admin"}'
# → { "code": "A1", "score": 1, "returned_to_queue": true }
```
