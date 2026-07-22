# 계획서 — Windows + WSL2(Ubuntu) 2-Track 선택적 셋업/운영

- **작성일:** 2026-07-22
- **대상:** unique-code-system
- **목표:** 기존 Windows 네이티브 셋업에 더해 **WSL2(Ubuntu) 트랙**을 추가하여, 사용자가 환경에 따라 선택적으로 설치·운영할 수 있도록 한다.

---

## 1. 배경 / 목표

- 현재 셋업은 `windows/*.bat` (Windows 네이티브 Python) **단일 트랙**.
- WSL2(Ubuntu)에서 운영하면 **실 Redis 설치가 용이**하고(apt), systemd로 자동기동이 가능해 **운영 환경에 더 가깝다**.
- 요구사항: **Windows 트랙과 WSL2 트랙을 병존**시키고, 사용자가 상황에 맞게 **선택**하도록 한다.

---

## 2. 현재 상태 점검

| 항목 | 현황 |
|------|------|
| Windows 트랙 | `windows/setup.bat`, `start-all/backend/frontend.bat`, `stop-all.bat` (완성) |
| Linux/WSL 실행 | README/HANDOFF에 **수동 명령**만 문서화 (전용 스크립트 없음) |
| Redis | Windows=fakeredis 기본 / 실Redis는 `USE_REAL_REDIS=1` |
| 포트 | 코드 기본 8000, 배치·문서 기본 8099 (**불일치**) |
| 프론트-백 연결 | 4개 HTML의 `window.UCS_API_BASE=http://localhost:8099` |
| 자동기동 | Windows 작업스케줄러 언급만, 스크립트 없음 |

**핵심 관찰:** WSL2에서는 localhost 포워딩으로 `localhost:8099/8989`가 **Windows 브라우저에서 그대로 접속** 가능 → 프론트 `UCS_API_BASE` 변경 불필요. 즉 코드 변경 최소로 트랙 추가 가능.

---

## 3. 트랙 비교 (설계 방향)

| 구분 | Windows 트랙 (기존) | WSL2 트랙 (신규) |
|------|--------------------|------------------|
| Python | Windows 네이티브 + `.venv` | Ubuntu python3 + `.venv-wsl` (분리) |
| Redis | fakeredis 기본 / 실Redis 선택 | **실 redis-server 기본** (apt) / fakeredis 선택 |
| 기동 | `start-all.bat` (별도 콘솔) | `start-all.sh` (nohup/백그라운드) 또는 **systemd user 서비스** |
| 자동기동 | 작업 스케줄러(수동) | **systemd --user + linger** (권장) |
| 접속 | localhost:8989 | localhost:8989 (WSL localhost 포워딩) |
| 데이터 | `backend/data/ucs.json` (공유 리포 동일 경로) | 동일 (단, 두 트랙 **동시 기동 금지** — DB/포트 충돌) |

> **가상환경 분리 필수:** Windows `.venv`(Scripts/)와 Linux `.venv`(bin/)는 바이너리 호환 불가. WSL 트랙은 `.venv-wsl`로 분리하여 상호 오염 방지. (둘 다 `.gitignore`)

---

## 4. 제안 변경점 (파일)

### 4-1. 신규 디렉터리 `linux/` (WSL2 트랙)
| 파일 | 역할 |
|------|------|
| `linux/setup.sh` | python3/venv 확인·생성(.venv-wsl) + requirements + fakeredis, (옵션)redis-server 안내, data 폴더 |
| `linux/start-all.sh` | 백엔드+프론트 nohup 백그라운드 기동 + PID 기록 + health 대기 |
| `linux/start-backend.sh` | fakeredis/실redis 분기 (`USE_REAL_REDIS=1`) |
| `linux/start-frontend.sh` | `python3 -m http.server 8989 --bind 0.0.0.0` |
| `linux/stop-all.sh` | PID 파일 기반 정리 (fallback: 포트 점유 프로세스) |
| `linux/status.sh` | health/dashboard/포트 점유 상태 점검 |
| `linux/README-WSL2.md` | WSL2 설치·구동·문제해결 가이드 |

### 4-2. 신규 systemd(선택) `linux/systemd/`
| 파일 | 역할 |
|------|------|
| `ucs-backend.service` | user 서비스 (자동기동, `WantedBy=default.target`) |
| `ucs-frontend.service` | 정적 서버 user 서비스 |
| `linux/install-systemd.sh` | 유닛 링크 + `enable --now` + linger 안내 |

### 4-3. 최상위 셀렉터(선택) `install.sh`
- 실행 환경 자동 감지(`uname`/`/proc/version`에 microsoft) → Windows면 배치 안내, WSL/Linux면 `linux/setup.sh` 호출. 대화형 선택 제공.

### 4-4. 최소 코드/설정 개선
- `backend/app/core/config.py`: `UCS_PORT` 기본값 **8000 → 8099** 통일 (양 트랙·문서 일치). *(behavior 영향 낮음, HANDOFF §11-8 권장사항)*
- `.gitignore`: `.venv-wsl/`, `*.pid`, `linux/*.pid` 추가.
- `backend/requirements.txt`: 변경 없음 (fakeredis는 dev 옵션 유지).

---

## 5. 개선 제안 (트랙 추가와 함께 반영 권장)

1. **포트 기본값 통일(8099)** — OS 무관 일관성 (위 4-4).
2. **실 Redis 우선 경로** — WSL2는 `apt install redis-server`로 즉시 SSOT 확보 → 운영 유사도↑. 데모는 fakeredis 유지.
3. **PID/로그 파일화** — `linux/`는 `logs/backend.log`,`logs/frontend.log` + `*.pid`로 백그라운드 운영 가시성 확보 (Windows는 콘솔 유지).
4. **status/health 스크립트** — 양 트랙 공통 점검 UX.
5. **systemd user 서비스 + linger** — WSL2 상시 운영 시 재부팅/세션종료 후 자동 복구 (본 호스트 방침과 일치).
6. **동시 기동 가드** — 두 트랙이 같은 포트/DB를 쓰므로 start 스크립트에 포트 점유 감지 시 경고·중단.
7. **문서 정합** — README에 "트랙 선택" 섹션 신설, HANDOFF v0.4로 트랙 항목 추가.

---

## 6. 실행 계획 (Phase)

**Phase 1 — WSL2 기본 트랙 (핵심)**
- `linux/setup.sh`, `start-*.sh`, `stop-all.sh`, `status.sh` 작성
- fakeredis 기본 + 실redis 분기
- 로컬 실동작 검증(health/워크플로우 9종 재현)

**Phase 2 — 문서/셀렉터**
- `linux/README-WSL2.md` 작성
- 최상위 `install.sh`(환경 감지·선택)
- README "트랙 선택" 섹션 + HANDOFF v0.4

**Phase 3 — 운영 옵션(선택)**
- systemd user 유닛 + `install-systemd.sh` + linger 안내
- 포트 기본값 8099 통일 (config.py)
- 동시 기동 가드

**Phase 4 — 마무리**
- `.gitignore` 갱신, 커밋/푸시 (PUBLIC repo)
- 최종 검증 리포트

---

## 7. 리스크 / 유의

| 리스크 | 대응 |
|--------|------|
| Windows/WSL venv 상호 오염 | `.venv`(win) vs `.venv-wsl`(wsl) 분리 |
| 두 트랙 동시 기동 시 포트/DB 충돌 | start 스크립트 포트 점유 가드 + 문서 경고 |
| 포트 기본값 변경(8000→8099) 부작용 | 문서·배치와 일치시키는 방향이라 순영향, 회귀테스트로 확인 |
| WSL localhost 포워딩 미동작(구버전) | README에 `netsh portproxy`/WSL 버전 안내 |
| redis-server 미설치 환경 | fakeredis 폴백 기본 유지 |

---

## 8. 완료 기준 (Acceptance)

- [ ] `linux/setup.sh` 1회 실행으로 WSL2에서 구동 준비 완료
- [ ] `linux/start-all.sh` → health 200 + 워크플로우 9종 통과
- [ ] Windows 브라우저에서 `localhost:8989` 정상 접속
- [ ] Windows 트랙 기존 동작 무영향(회귀 없음)
- [ ] (선택) systemd 자동기동 + linger 검증
- [ ] 문서(README/HANDOFF/README-WSL2) 정합

---

## 9. 결정 요청 사항

1. **Redis 기본값(WSL2 트랙):** 실 redis-server 기본 vs fakeredis 기본 — 어느 쪽으로?
2. **systemd 자동기동(Phase 3) 포함 여부** — 상시 운영 필요 시 권장.
3. **포트 기본값 8099 통일** 진행 여부(코드 1줄 변경).
4. Phase 1부터 바로 구현 착수할지 여부.

---

---

## 10. 사내 인트라넷(LAN) 서비스 전환 — 확정 요구사항 & 확인점 (2026-07-22 추가)

### 확정된 결정
- **바인딩:** 내 PC IP로 바인딩하여 같은 통신망(사내 인트라넷) PC들이 접속 가능하도록 서비스.
- **프로토콜:** MVP는 **HTTP only**, HTTPS는 향후 적용.
- **외부접속 포트 기본값: 8099.**

### ⚠️ 반드시 조치할 치명 이슈 (코드 실측 확인됨)
1. **프론트 `UCS_API_BASE` 하드코딩 = 원격 접속 시 파손.**
   - 현재 4개 HTML 모두 `window.UCS_API_BASE = "http://localhost:8099"`.
   - 원격 PC 브라우저에서는 `localhost`가 **그 PC 자신**을 가리켜 API 호출 실패.
   - **해결안 A(권장):** 프론트를 FastAPI에 StaticFiles로 마운트 → **단일 포트 8099**에서 UI+API 동시 서빙 → `UCS_API_BASE=""`(상대경로, 동일 오리진) → **모든 클라이언트 IP에서 자동 동작**. 방화벽 1개·CORS 불요.
   - **해결안 B:** 2포트 유지 + 주입값을 `http://` + `location.hostname` + `:8099`로 동적 산출 + 프론트 `0.0.0.0` 바인딩 + CORS 유지.

### 확인/결정 필요 항목
| # | 항목 | 내용 |
|---|------|------|
| C1 | **포트 구성** | 단일포트(8099에 UI+API 통합, 권장) vs 2포트(8099 API + 8989 UI) — "외부접속 8099"이면 단일포트 정합 |
| C2 | **프론트 바인딩** | 2포트 유지 시 현재 `--bind 127.0.0.1` → **0.0.0.0** 변경 필요(현재는 LAN 차단) |
| C3 | **인증/보안** | Admin 화면 **무인증** — LAN 노출 시 누구나 발급/파기 가능. 최소 Basic Auth 또는 IP 화이트리스트 **선적용 권장** |
| C4 | **Windows 방화벽** | 8099/TCP 인바운드 허용 규칙 필요(사설망). 관리자 권한(UAC) |
| C5 | **WSL2 LAN 노출** | WSL2 NAT라 LAN PC가 WSL 서비스 **직접 접속 불가**. 해결: (a)Win11 mirrored networking(`.wslconfig`) 또는 (b)`netsh portproxy`+방화벽. Windows 버전 확인 필요 |
| C6 | **호스트 IP 고정** | DHCP로 PC IP 변동 시 접속 끊김 → **고정 IP/DHCP 예약** 또는 호스트명 접속 권장 |
| C7 | **단일 워커** | 다중 사용자 동시 접속 시 JSON DB 무결성 위해 uvicorn **단일 워커** 유지(Redis가 큐 SSOT) |
| C8 | **CORS** | 단일포트면 불요 / 2포트면 현재 `allow_origins=["*"]` 유지(향후 사내망 대역으로 축소 권장) |
| C9 | **HTTPS 로드맵** | 향후 nginx/caddy 리버스 프록시로 TLS 종단 + 8099를 내부 업스트림으로 |

### 권장 구성 (요약)
- **단일 포트 8099**에 UI+API 통합 서빙(StaticFiles 마운트) + `0.0.0.0` 바인딩 + `UCS_API_BASE=""`.
- WSL2 트랙은 mirrored networking 또는 portproxy로 LAN 노출.
- Admin 최소 인증(Basic/토큰) 또는 IP 화이트리스트 동반.

---

---

## 11. 결정 확정 & 네트워킹/DB 해설 (2026-07-22 확정)

### 확정된 결정
- **C1 포트:** 단일 포트 **8099**에 UI+API 통합(StaticFiles 마운트) + `0.0.0.0` 바인딩 + `UCS_API_BASE=""`(상대경로). 권장안 채택.
- **C3 인증:** MVP는 **무인증** 구현. (향후 Basic Auth/IP 화이트리스트 옵션 여지 유지)
- **C4 방화벽:** 인바운드/사설망 규칙 **모두 허가된 상태 전제**.
- **C6 호스트 IP:** **고정 IP**. 문서(README)에 고정 IP 직접 입력/하드코딩 안내 포함.

### C5 — WSL2 네트워킹 설명 (핵심)
**실측 결과: 현재 WSL2 = NAT 모드** (eth0=192.168.233.x, GW=192.168.224.1 — Windows 호스트와 **별도 가상 IP**).

- WSL2는 경량 VM으로 **자체 가상 IP**를 가지며 Windows 뒤에서 NAT됨.
- Windows 호스트 **자신**이 `localhost:8099` 접속 → WSL로 자동 포워딩됨(이것만 자동).
- 그러나 **다른 LAN PC가 WindowsIP:8099 접속** → Windows가 그 트래픽을 WSL VM으로 넘기는 규칙이 **기본에 없음** → 실패.
- 즉 "WSL 호스팅 → Windows IP로 외부 PC 접속"은 **목표는 가능하지만 자동이 아니며 연결 룰 1개 필요**.

**해결 2안:**
| 방식 | 설명 | 적용성 |
|------|------|--------|
| **(A) portproxy** | Windows에서 `netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8099 connectaddress=<WSL_IP> connectport=8099` → LAN PC가 WindowsIP:8099 → WSL:8099 포워딩 | **Win10/11 모두**. 단, WSL IP가 재기동 시 변동하므로 **자동 갱신 스크립**(`windows/wsl-portproxy.ps1`, 부팅 시 Task Scheduler) 필요 |
| **(B) mirrored** | `.wslconfig`에 `networkingMode=mirrored` → WSL이 호스트 네트워크/IP 직결 → WSL에서 0.0.0.0 바인드만 해도 LAN에서 **WindowsIP:8099 직접 접속** (portproxy 불요) | **Win11 22H2+/최신 빌드**만. 가장 간단 |

> Windows interop이 현재 막혀(교체 필요) Windows 버전 자동확인 불가. 사용자가 Win10/11 알려주면 확정. **기본 권장=(A) portproxy + 자동갱신 스크립**(버전 무관 동작), Win11 최신이면 (B) mirrored 전환이 더 깔끔.

> 참고: Windows 네이티브 트랙은 이런 문제가 없음(Windows Python이 직접 호스트 IP에 바인드). LAN 노출 난이도: **Windows 트랙 ≤ WSL mirrored ≤ WSL portproxy**.

### C7 — RDBMS 도입 (데이터 무결성 1순위)
**실측: WSL에 SQLite 3.51.3 사용 가능(python+CLI). PostgreSQL/Redis는 미설치(apt 가능).**

현재 구조의 무결성 약점 = **JSON 파일 DB**(단일 파일, RLock으로 프로세스 내면 안전하나 다중워커/크래시 리스크). 큐는 Redis ZSET SSOT.

**권장안 (형제 프로젝tcode-2char-system에서 검증된 패턴):**
- **SQLite 단일 SSOT (WAL + BEGIN IMMEDIATE)** 로 전환 → JSON+Redis **모두 제거**.
  - 큐 = 432행 테이블(status/score). 발급 = `BEGIN IMMEDIATE` → 최소 score WAITING 1건 → ACTIVE UPDATE (쓰기 직렬화로 중복발급 0). 파기 = WAITING 복원.
  - 장점: 트랜잭션 무결성 보장, 단일 파일 백업 용이, **Redis 설치 불요**(WSL 운영 단순화), 동시 읽기 자유. 사내 추번 규모(저빈도 쓰기)에 충분.
- 대안 (변경 최소): Redis ZSET 큐 유지 + 레코드만 JSON→SQLite.
- 서버급 동시성 필요 시: PostgreSQL(apt) — 다중 워커 가능하나 서버 운영 부담. MVP에는 과함.

> 결론: **SQLite 단일 SSOT** 권장 (데이터 무결성 최상 + WSL 운영 최단순). 단, 코어 채번 엔진 리팩터링이므로 432풀 순서·결번복원 시맨틱 **재검증 필수**. C7 최종 승인 요청.

---

_계획 수립: OpenClaw · 2026-07-22 (v3: 네트워킹/DB 결정 반영)_
