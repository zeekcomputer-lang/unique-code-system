# 🔁 HANDOFF — 유니크 코드 통합 관리 시스템

> **인계 대상**: 다음 개발/운영 담당자
> **최종 갱신**: 2026-07-22 (v0.4)
> **현재 단계**: SQLite 단일 SSOT 전환 + 단일 포트 통합 + Windows/WSL2 2-Track + LAN 서비스 · 전 시나리오+동시성 검증 완료
> **GitHub**: <https://github.com/zeekcomputer-lang/unique-code-system>

---

## ★ v0.4 핵심 변경 (2026-07-22) — 먼저 읽으세요

아키텍처가 크게 바뀌었습니다. 이전 v0.3 설명 중 Redis/JSON/2포트 관련 내용은 **폐기**됩니다.

| 항목 | v0.3 (구) | **v0.4 (현)** |
|------|-----------|----------------|
| 저장소 | JSON 파일 + Redis ZSET | **SQLite 단일 SSOT** (`backend/data/ucs.sqlite3`, WAL) |
| 큐 | Redis `ZPOPMIN`/`ZADD` | `codes.status='WAITING'` + 불변 `score` 정렬 |
| 원자성 | Redis 명령 | `BEGIN IMMEDIATE` 트랜잭션 (동시발급 중복 0, 20병렬 검증) |
| 포트 | 백 8099 + 프론트 8989 (2포트) | **단일 8099** (FastAPI 가 `frontend/` StaticFiles 마운트) |
| 프론트 API base | `http://localhost:8099` 하드코딩 | **`UCS_API_BASE=""`** (상대경로, 접속 IP 무관) |
| 외부 의존 | Redis 필요 | **0** (SQLite만) → git clone 즉시 기동 |
| 트랙 | Windows 단일 | **Windows + WSL2 2-Track** |

**삭제된 파일**: `backend/app/services/sequence_manager.py`, `backend/app/db/database.py`, `backend/run_with_fakeredis.py`, `windows/start-backend.bat`, `windows/start-frontend.bat`.
**신규 파일**: `backend/app/db/sqlite_db.py`, `linux/*` (setup/start/stop/status.sh, systemd, install-systemd.sh, README-WSL2.md), `windows/start.bat`, `windows/wsl-portproxy.ps1`.

### 배포 모델 (중요)
개발환경(WSL2 등)≠운영환경. **운영 서버에서 git clone/pull → setup → start.** 머신 고유값(IP·경로) 하드코딩 금지, 모두 env/문서로 주입.

### LAN 서비스 (사내 인트라넷)
- 서버는 `0.0.0.0:8099` 바인딩. **HTTP MVP**(HTTPS 향후), **무인증 MVP**.
- Linux 실물/VM: 서버 고정 IP로 바로 접속.
- **Windows+WSL2**: 현 운영 환경은 **`.wslconfig networkingMode=mirrored` 채택** → WSL 이 Windows 호스트 IP 직결 → 0.0.0.0:8099 바인드만으로 다른 PC 가 `WindowsIP:8099` 직접 접속(**portproxy 불필요**). NAT 모드용 대안은 `windows/wsl-portproxy.ps1`. 상세: `linux/README-WSL2.md` §3. 참고: SSH 도 동일하게 호스트 IP 로 접속(기존 2222 portproxy 불필요해짐).

---

---

## 0. 변경 이력 (Changelog)

| 버전 | SHA | 내용 |
|------|-----|------|
| v0.4 | (본 커밋) | **SQLite 단일 SSOT** 전환(Redis/JSON 제거) + **단일 포트 통합**(8099 UI+API) + **Windows/WSL2 2-Track** + **LAN 서비스**(0.0.0.0, portproxy 헬퍼) + 동시발급 원자성(BEGIN IMMEDIATE) |
| v0.3 | `17a6898` | Prefix 정책 완화: 영문 → **영문+숫자 1~16자** (자동 대문자) |
| v0.2 | `365242d` | base 코드 입력에 숫자 허용(`#frcBase` 분리), full_code 포맷 **`{prefix}{base}`** (하이픈 제거) |
| v0.2 | `c0515be` | 기본 포트 변경: 백엔드 `8000→8099`, 프론트 `8080→8989` |
| v0.1 | `f25f8d9` | Initial MVP (FastAPI + Redis ZSET + Bootstrap 5.3) |

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
| 기본 포트 | 백엔드 **8099**, 프론트 **8989** |

---

## 2. 폴더 구조

```
projects/unique-code-system/
├── ui-design-system.md       # 디자인 시스템(Bootstrap 5.3판)
├── HANDOFF.md                # 본 문서
├── README.md                 # 프로젝트 메인
├── .gitignore
├── backend/
│   ├── app/
│   │   ├── core/{codes.py, config.py}
│   │   ├── db/database.py
│   │   ├── services/sequence_manager.py
│   │   ├── models/schemas.py
│   │   ├── api/routes.py
│   │   └── main.py
│   ├── data/                 # ucs.json 런타임 자동 생성 (gitignore)
│   ├── requirements.txt
│   ├── .env.example
│   ├── run_with_fakeredis.py # ★ Redis 미설치 시 개발용 부트
│   └── README.md
├── frontend/
│   ├── index.html · request.html · admin.html · dashboard.html
│   └── assets/
│       ├── css/ucs-theme.css
│       └── js/{ucs-common.js, request.js, admin.js, dashboard.js}
└── windows/
    ├── setup.bat
    ├── start-backend.bat · start-frontend.bat · start-all.bat · stop-all.bat
    └── README-WINDOWS.md
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

## 4. Prefix 규칙 (v0.3 갱신)

- 정규식: **`^[A-Za-z0-9]{1,16}$`** — 영문(대소문자) + 숫자 허용
- 입력 시 **자동 대문자 변환** (`v2` → `V2`)
- 비허용 문자(한글·공백·특수문자)는 클라이언트 입력 즉시 제거 + 서버에서 422
- 발급 예: `prefix=APP2024` + base `A1` → **`APP2024A1`** (하이픈 없음)
- 길이: 1~16자 (단, **base 2자리 포함 최종 코드는 최대 18자**)

### 입력 필드 클래스 분리 (중요)
| 클래스 | 용도 | 자동 변환 |
|--------|------|-----------|
| `.ucs-input-prefix` | Prefix 전용 | **있음** (영숫자 외 제거 + 대문자) |
| `.ucs-input-code` | base 코드 등 시각 스타일 | **없음** (별도 핸들러로 처리) |

---

## 5. 데이터 모델

### `codes.{BASE_CODE}` (JSON DB)
```json
{
  "code": "A1", "score": 1,
  "status": "WAITING|ACTIVE|REVOKED",
  "prefix": "APP2024", "full_code": "APP2024A1",
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
  "desired_prefix": "APP2024",
  "status": "PENDING|APPROVED|REJECTED",
  "issued_code": "A1", "issued_full_code": "APP2024A1",
  "created_at": "...", "approved_at": "...", "approver": "admin", "note": null
}
```

### Redis ZSET
- Key: `ucs:code:queue` (환경변수 `UCS_REDIS_KEY`)
- member = 코드 문자열, score = 1~432

---

## 6. API 명세 (요약)

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

전체 OpenAPI: 백엔드 기동 후 <http://localhost:8099/docs>

---

## 7. 로컬 실행

### Linux / macOS / WSL

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

### Windows 10/11

```cmd
windows\setup.bat       REM 1회: .venv + 의존성
windows\start-all.bat   REM 백엔드(:8099) + 프론트(:8989) + 브라우저 자동 오픈
windows\stop-all.bat    REM 포트 점유 프로세스 일괄 종료
```

자세한 가이드: [`windows/README-WINDOWS.md`](windows/README-WINDOWS.md)

---

## 8. 환경변수

| Key | 기본값 | 설명 |
|-----|--------|------|
| `UCS_DEBUG` | `false` | true 시 reload + DEBUG 로그 |
| `UCS_HOST` | `0.0.0.0` | 백엔드 바인드 |
| `UCS_PORT` | `8099` (Windows 배치) / 코드 기본은 `8000` | 백엔드 포트 |
| `UCS_REDIS_URL` | `redis://localhost:6379/0` | Redis 접속 |
| `UCS_REDIS_KEY` | `ucs:code:queue` | ZSET 키 |
| `UCS_DB_FILE` | `ucs.json` | `backend/data/` 하위 파일명 |
| `UCS_WEB_PORT` | `8989` (Windows 배치만) | 프론트 정적 서버 포트 |

> 백엔드 코드 자체의 `UCS_PORT` 기본값은 여전히 `8000`이며, Windows 배치(`start-backend.bat`)에서 `set UCS_PORT=8099`로 주입함. Linux/macOS는 명령행에서 `UCS_PORT=8099 python ...` 형태로 전달.

---

## 9. 디자인 시스템 (반드시 준수)

문서: [`ui-design-system.md`](ui-design-system.md) (Bootstrap 5.3판)

**금지**
- Tailwind, MUI, Bootstrap 기본 파랑 그대로 노출, jQuery 사용

**필수**
- 모든 코드 출력부에 `.ucs-code` (필요 시 `.ucs-code-primary`)
- Prefix 입력: 영숫자 자동 필터 + 대문자 (자동 바인더 또는 `.ucs-input-prefix` 적용)
- 폼 제출 로딩: `UCS.loading.start(btn)` (스피너 교체 + disabled)
- 알림: `UCS.toast.*` (alert 절대 금지)
- 파괴적 액션: Bootstrap Modal + **"결번 복원을 위해 대기열 시퀀스의 원래 순번(제자리)으로 반환됩니다."** 문구
- 파기 행: `.ucs-row-revoked` (취소선 + 흐림)

### 프론트 ↔ 백엔드 API base 결정 로직 (`ucs-common.js`)

우선순위:
1. HTML에서 `<script>window.UCS_API_BASE = 'http://localhost:8099';</script>` 주입한 값 (현재 4개 HTML에 모두 적용됨)
2. 같은 오리진이면 빈 문자열(상대 경로)
3. `file://` 로 열면 `http://localhost:8099` 폴백

포트 재변경 시 HTML 4개의 주입 줄만 갱신하면 끝.

---

## 10. 검증 완료 시나리오

| # | 시나리오 | 상태 |
|---|----------|------|
| 1 | 432개 생성, O/I/0 제외, Z9(216) → 1A(217) 경계 | ✅ |
| 2 | 의뢰 접수 → PENDING | ✅ |
| 3 | 의뢰 승인 + Prefix=`APP2024` → `APP2024A1` 발급 | ✅ |
| 4 | `APP2024A1` 파기 → score 1 제자리 복귀 (peek 최상단 = A1) | ✅ |
| 5 | Prefix `v2` (소문자) → 자동 대문자 `V2` 적용 (`V2A2`) | ✅ |
| 6 | 강제 채번 `Z9` + `8K` → `8KZ9` (force_issued=true) | ✅ |
| 7 | 강제 채번 base `1A`, `9Z` 등 숫자 시작 코드 입력 가능 | ✅ |
| 8 | Prefix `DEV!` / `개발` → 422 거부 | ✅ |
| 9 | 정적 자원 9종 200, API 라운드트립 통과 | ✅ |
| 10 | 포트 변경(8099/8989) 후 전 화면 정상 동작 | ✅ |

---

## 11. 알려진 한계 / TODO

### 한계
- 인증/권한 없음 — Admin 화면이 누구나 접근 가능
- 단일 JSON 파일 영속 — 다중 워커 환경에서는 Redis가 SSOT, JSON은 기록 용도
- 의뢰서 REJECT 라우트 미구현 (PENDING/APPROVED만 동작)
- pytest 정식 스위트 없음 (라운드트립 수동 검증만)
- 운영용 Docker / systemd unit 미작성
- 백엔드 코드 자체의 `UCS_PORT` 기본값(8000)과 배치 스크립트 기본값(8099)이 다름 — 운영 일원화 권장

### 권장 후속 작업
1. **의뢰서 REJECT API** — `POST /api/requests/{id}/reject` + 사유 기록
2. **인증** — 최소 Basic Auth 혹은 토큰 헤더로 Admin/Dashboard 보호
3. **pytest 스위트** — `tests/` 디렉토리에 채번/파기/롤백/동시성 케이스
4. **Docker Compose** — app + redis + (옵션) nginx 정적 서빙
5. **이력 화면** — `codes.history[]` 활용한 코드별 타임라인
6. **백업/스냅샷** — `backend/data/ucs.json` 일/주 단위 스냅샷 보관 정책
7. **다중 워커 운영** — JSON 쓰기 직렬화 패턴(단일 라이터) 또는 SQLite/PostgreSQL 이전
8. **백엔드 기본 포트 통일** — `config.py`의 PORT 기본값을 8099로 변경하여 OS 무관 일관성 확보

---

## 12. 운영 시 주의사항

- `backend/data/ucs.json`은 **상태 진실 보관소**. 삭제 시 모든 발급 이력 손실.
- Redis ZSET이 사라지면 `bootstrap()`이 다시 432개를 시드하지만, ACTIVE 코드는 JSON에 남으므로 **JSON 기준으로 정합화 필요** (현재 코드는 ACTIVE 코드를 큐에서 자동 제외하지 않음 — 운영 전환 시 점검 필요).
- 강제 채번(FORCE_ISSUED)은 history에 기록되지만 별도 감사 로그 채널은 없음 — 운영 시 ELK/CloudWatch 연동 권장.
- Prefix 길이 16자 + base 2자 = **최종 코드 최대 18자**. 외부 시스템 연동 시 컬럼 폭 확인.

---

## 13. 빠른 디버깅 팁

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

### 포트 변경하고 싶을 때 (예: 9000/9100)
1. `windows\start-backend.bat`: `set UCS_PORT=9000`
2. `windows\start-frontend.bat`: 기본값 변수 `UCS_WEB_PORT=9100`
3. `windows\start-all.bat`, `stop-all.bat`도 새 포트로 갱신
4. **`frontend/index.html`, `request.html`, `admin.html`, `dashboard.html`** 의 `window.UCS_API_BASE` 4곳 모두 새 백엔드 포트로 변경 (이게 빠지면 fetch가 옛 포트로 감)

---

## 14. GitHub 인증 (zeekcomputer-lang)

| 항목 | 내용 |
|------|------|
| 사용자 | `zeekcomputer-lang` |
| 인증 파일 | `~/.git-credentials` (chmod 600), `~/.bashrc`의 `GH_TOKEN` |
| 토큰 만료 | **2026-05-19** (7일짜리, 이후 재발급 필요) |
| 갱신 위치 | <https://github.com/settings/tokens> |

만료 후 새 토큰 수신 시:
1. `~/.git-credentials` 의 토큰 부분 교체
2. `~/.bashrc` 의 `GH_TOKEN` 교체
3. `source ~/.bashrc`

---

## 15. 연락/참조

- 디자인 시스템: [`ui-design-system.md`](ui-design-system.md)
- 백엔드 README: [`backend/README.md`](backend/README.md)
- Windows 가이드: [`windows/README-WINDOWS.md`](windows/README-WINDOWS.md)
- 메인 README: [`README.md`](README.md)

_End of HANDOFF v0.3_
