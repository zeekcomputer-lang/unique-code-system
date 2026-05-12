# 🔁 HANDOFF — 유니크 코드 통합 관리 시스템

> **인계 대상**: 다음 개발/운영 담당자
> **작성일**: 2026-05-12
> **현재 단계**: MVP 4단계 완료 · 로컬 데모 가능 · 운영 전환 전 단계

---

## 1. 프로젝트 한눈에 보기

| 항목 | 내용 |
|------|------|
| 목적 | 2자리 고정 풀(432개) 기반 유니크 코드 의뢰 → 발급 → 파기 → 결번 복원 |
| 백엔드 | Python 3.10+ · FastAPI · Uvicorn · Redis(ZSET) · JSON 파일 DB |
| 프론트엔드 | HTML5 · Vanilla JS · Bootstrap 5.3 · FontAwesome 6.4 · Noto Sans KR |
| 화면 | index / request / admin / dashboard (4종) |
| API | 11개 엔드포인트 (`/api/requests/*`, `/api/codes/*`, `/api/dashboard`, `/health`) |
| 동시성 | Redis `ZPOPMIN`/`ZADD nx` 원자성 + JSON I/O `RLock` + atomic write |

---

## 2. 폴더 구조

```
projects/unique-code-system/
├── ui-design-system.md       # 디자인 시스템(Bootstrap 5.3판) — 변경 시 갱신 필수
├── HANDOFF.md                # 본 문서
├── backend/
│   ├── app/
│   │   ├── core/{codes.py, config.py}
│   │   ├── db/database.py
│   │   ├── services/sequence_manager.py
│   │   ├── models/schemas.py
│   │   ├── api/routes.py
│   │   └── main.py
│   ├── data/ucs.json         # 런타임 생성 (gitignore 권장)
│   ├── requirements.txt
│   ├── .env.example
│   ├── run_with_fakeredis.py # ★ Redis 미설치 시 개발용 부트
│   └── README.md
└── frontend/
    ├── index.html · request.html · admin.html · dashboard.html
    └── assets/
        ├── css/ucs-theme.css
        └── js/{ucs-common.js, request.js, admin.js, dashboard.js}
```

---

## 3. 채번 규칙 (불변)

- 영문자 24자: A~Z **중 O, I 제외**
- 숫자 9자: 1~9 (**0 제외**)
- 1순위 영문+숫자 216개 (`A1`…`Z9`, score 1~216)
- 2순위 숫자+영문 216개 (`1A`…`9Z`, score 217~432)
- **총 432개, 랜덤 아닌 순차 발급**
- 파기 시 원래 score로 ZADD → 큐의 **제자리(원래 순번)** 로 복귀

> 이 규칙은 `backend/app/core/codes.py`에 결정론적으로 구현되어 있음. **건드리지 말 것** (인덱스 변경 시 기존 데이터 불일치).

---

## 4. 데이터 모델

### `codes.{BASE_CODE}` (JSON DB)
```json
{
  "code": "A1", "score": 1,
  "status": "WAITING|ACTIVE|REVOKED",
  "prefix": "DEV", "full_code": "DEV-A1",
  "request_id": "REQ-0001",
  "issued_to": "alice", "issued_at": "...", "revoked_at": null,
  "force_issued": false,
  "history": [{ "event": "ISSUED", "at": "...", "by": "..." }]
}
```

### `requests.{REQ_ID}`
```json
{
  "id": "REQ-0001", "requester": "홍길동", "reason": "...",
  "desired_prefix": "DEV",
  "status": "PENDING|APPROVED|REJECTED",
  "issued_code": "A1", "issued_full_code": "DEV-A1",
  "created_at": "...", "approved_at": "...", "approver": "admin", "note": null
}
```

### Redis ZSET
- Key: `ucs:code:queue` (환경변수 `UCS_REDIS_KEY`)
- member = 코드 문자열, score = 1~432

---

## 5. API 명세 (요약)

| Method | Path | 비고 |
|--------|------|------|
| GET | `/health` | Redis 연결 + 큐 크기 |
| POST | `/api/requests` | 의뢰 접수 → PENDING |
| GET | `/api/requests?status=` | 의뢰 목록 (status 필터) |
| GET | `/api/requests/{id}` | 단건 |
| GET | `/api/codes?status=` | 코드 목록 |
| GET | `/api/codes/peek?n=` | 발급 예정 N개 |
| GET | `/api/codes/{code}` | base 또는 full 코드 |
| POST | `/api/codes/issue/{req_id}` | **승인+발급** — payload: `{prefix, issued_to?, approver?}` |
| POST | `/api/codes/force` | **강제 채번** — payload: `{base_code, prefix, request_id?, ...}` |
| POST | `/api/codes/revoke/{code}` | **파기** — 원래 score로 복원 |
| GET | `/api/dashboard` | 통계 + next_preview |

전체 OpenAPI: 백엔드 기동 후 `http://localhost:8099/docs`

---

## 6. 로컬 실행 (Linux/macOS/WSL)

```bash
cd backend
pip install -r requirements.txt

# A) 진짜 Redis 사용
UCS_PORT=8099 python -m app.main

# B) Redis 미설치 환경 (개발용 fakeredis)
pip install fakeredis
UCS_PORT=8099 python run_with_fakeredis.py

# 프론트엔드 정적 서빙
cd ../frontend
python -m http.server 8989
# → http://localhost:8989/index.html
```

### Windows 10
별도 가이드: `windows/README-WINDOWS.md` 와 `windows/*.bat` 스크립트 참조.

---

## 7. 환경변수

| Key | 기본값 | 설명 |
|-----|--------|------|
| `UCS_DEBUG` | `false` | true 시 reload + DEBUG 로그 |
| `UCS_HOST` | `0.0.0.0` | 백엔드 바인드 |
| `UCS_PORT` | `8099` (권장) | 백엔드 포트 (`backend\.env`·batch·CLI 어디서든 주입 가능) |
| `UCS_REDIS_URL` | `redis://localhost:6379/0` | Redis 접속 |
| `UCS_REDIS_KEY` | `ucs:code:queue` | ZSET 키 |
| `UCS_DB_FILE` | `ucs.json` | `backend/data/` 하위 파일명 |

`.env.example` 참고.

---

## 8. 디자인 시스템 (반드시 준수)

- 문서: `ui-design-system.md` (Bootstrap 5.3판)
- **금지**: Tailwind, MUI, Bootstrap 기본 파랑 그대로 노출, jQuery 사용
- **필수**:
  - 모든 코드 출력부에 `.ucs-code` (필요 시 `.ucs-code-primary`)
  - Prefix 입력: `replace(/[^a-zA-Z]/g,'').toUpperCase()`
  - 폼 제출 로딩: `UCS.loading.start(btn)`
  - 알림: `UCS.toast.*` (alert 절대 금지)
  - 파괴적 액션: Bootstrap Modal + **"결번 복원을 위해 대기열 시퀀스의 원래 순번(제자리)으로 반환됩니다."** 문구
  - 파기 행: `ucs-row-revoked` 클래스

---

## 9. 검증 완료 시나리오

| # | 시나리오 | 상태 |
|---|----------|------|
| 1 | 432개 생성, O/I/0 제외, Z9(216) → 1A(217) 경계 | ✅ |
| 2 | 의뢰 접수 → PENDING | ✅ |
| 3 | 의뢰 승인 + Prefix=DEV → DEV-A1 | ✅ |
| 4 | DEV-A1 파기 → score 1 제자리 복귀 (peek 최상단 = A1) | ✅ |
| 5 | 강제 채번 Z9 + VIP → VIP-Z9, force_issued=true | ✅ |
| 6 | 중복 강제 채번 → 409 | ✅ |
| 7 | Prefix 유효성 위반 → 422 | ✅ |
| 8 | 대시보드 stats 일치 | ✅ |
| 9 | 정적 자원 9종 200, API 라운드트립 통과 | ✅ |

---

## 10. 알려진 한계 / TODO

### 한계
- 인증/권한 없음 — Admin 화면이 누구나 접근 가능
- 단일 JSON 파일 영속 — 다중 워커 환경에서는 Redis가 SSOT, JSON은 기록 용도
- 의뢰서 REJECT 라우트 미구현 (PENDING/APPROVED만 동작)
- pytest 정식 스위트 없음 (라운드트립 수동 검증만)
- 운영용 Docker / systemd unit 미작성

### 권장 후속 작업
1. **의뢰서 REJECT API** — `POST /api/requests/{id}/reject` + 사유 기록
2. **인증** — 최소 Basic Auth 혹은 토큰 헤더로 Admin/Dashboard 보호
3. **pytest 스위트** — `tests/` 디렉토리에 채번/파기/롤백/동시성 케이스
4. **Docker Compose** — app + redis + (옵션) nginx 정적 서빙
5. **이력 화면** — `codes.history[]` 활용한 코드별 타임라인
6. **백업/스냅샷** — `backend/data/ucs.json` 일/주 단위 스냅샷 보관 정책
7. **다중 워커 운영** — 현재 단일 프로세스 권장. 워커 늘릴 경우 JSON 쓰기를 Redis 발신 이벤트 큐 + 단일 라이터 패턴으로 전환 필요

---

## 11. 운영 시 주의사항

- `backend/data/ucs.json`은 **상태 진실 보관소**. 삭제 시 모든 발급 이력 손실.
- Redis ZSET이 사라지면 `bootstrap()`이 다시 432개를 시드하지만, ACTIVE 코드는 JSON에 남으므로 **JSON 기준으로 정합화 필요** (현재 코드는 ACTIVE 코드를 큐에서 자동 제외하지 않음 — 운영 전환 시 점검 필요).
- 강제 채번(FORCE_ISSUED)은 history에 기록되지만 별도 감사 로그 채널은 없음 — 운영 시 ELK/CloudWatch 연동 권장.

---

## 12. 빠른 디버깅 팁

```bash
# 상태 점검
curl http://localhost:8099/health
curl http://localhost:8099/api/dashboard | python -m json.tool

# JSON DB 상태
cat backend/data/ucs.json | python -m json.tool | less

# Redis 큐 상태 (실 Redis 사용 시)
redis-cli ZRANGE ucs:code:queue 0 5 WITHSCORES
redis-cli ZCARD ucs:code:queue
```

---

## 13. 연락/참조

- 디자인 시스템: `ui-design-system.md`
- 백엔드 README: `backend/README.md`
- Windows 가이드: `windows/README-WINDOWS.md`

_End of HANDOFF_
