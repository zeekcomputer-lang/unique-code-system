# 🎯 Unique Code Management System

> 2자리 고정 풀(432개) 기반 유니크 코드 의뢰 → 발급 → 파기 → **결번 자동 복원** 관리 시스템
>
> **단일 포트(8099)에서 UI+API 통합 서빙 · SQLite 단일 SSOT · 외부 서비스 의존 0 · 사내 인트라넷(LAN) 서비스 · Windows/WSL2 2-Track**

![Stack](https://img.shields.io/badge/backend-FastAPI-009688?style=flat&logo=fastapi)
![Frontend](https://img.shields.io/badge/frontend-Bootstrap%205.3-7952B3?style=flat&logo=bootstrap)
![DB](https://img.shields.io/badge/db-SQLite%20WAL-003B57?style=flat&logo=sqlite)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## ✨ 주요 특징

- **결정론적 순차 채번** — 432개 고정 풀 (A1~Z9 + 1A~9Z, O/I/0 제외)
- **결번 자동 복원** — 파기 시 SQLite status→WAITING, 불변 score 정렬로 원래 순번(제자리) 자동 복귀
- **SQLite 단일 SSOT** — WAL + `BEGIN IMMEDIATE` 로 쓰기 직렬화(동시 발급 중복 0). **Redis 불필요**
- **단일 포트 통합 서빙** — FastAPI 가 프론트(정적)까지 8099 에서 서빙 → 동일 오리진, 어떤 IP 로 접속해도 자동 동작
- **Windows / WSL2 2-Track** — 환경에 맞춰 선택적 셋업·운영
- **Vanilla JS + Bootstrap 5.3** — jQuery/SPA 프레임워크 0 dependency
- **디자인 시스템 100% 준수** — `.ucs-code` 모노스페이스 / Toast 알림 / Modal 파기 확인

---

## 🚀 빠른 시작

> 배포 모델: **운영 서버에서 git clone/pull → 셋업 → 기동.** 단일 포트(8099)에서 UI+API 통합.

### WSL2 (Ubuntu) / Linux

```bash
bash linux/setup.sh        # .venv-wsl + 의존성 (1회)
bash linux/start.sh        # 백그라운드 기동 → http://localhost:8099/
bash linux/status.sh       # 상태 점검
bash linux/stop.sh         # 종료
```
자세한 가이드(LAN 노출·systemd·백업): [`linux/README-WSL2.md`](linux/README-WSL2.md)

### Windows

```cmd
windows\setup.bat                REM 가상환경 + 의존성 (1회)
windows\start-all.bat            REM 서버 기동 + 브라우저 자동 오픈
```
자세한 가이드: [`windows/README-WINDOWS.md`](windows/README-WINDOWS.md)

> 접속: `http://localhost:8099/` · 대시보드 `/dashboard.html` · API 문서 `/docs`
> LAN 다른 PC: `http://<서버 고정 IP>:8099/` (Windows+WSL2 NAT 시 portproxy/mirrored — WSL2 가이드 §3)

---

## 📁 폴더 구조

```
unique-code-system/
├── HANDOFF.md                  # 다음 작업자용 인계 문서
├── ui-design-system.md         # Bootstrap 5.3 기반 디자인 가이드
├── backend/
│   ├── app/
│   │   ├── core/{codes,config}.py
│   │   ├── db/sqlite_db.py             # SQLite 단일 SSOT (큐+레코드, BEGIN IMMEDIATE)
│   │   ├── models/schemas.py
│   │   ├── api/routes.py
│   │   └── main.py                     # API + 정적 프론트 단일 포트 서빙
│   ├── data/                           # ucs.sqlite3 런타임 생성 (gitignore)
│   └── requirements.txt
├── frontend/
│   ├── index.html · request.html · admin.html · dashboard.html
│   └── assets/{css/ucs-theme.css, js/*.js}
├── linux/                      # WSL2/Linux 트랙 (setup/start/stop/status.sh, systemd, README-WSL2)
└── windows/                    # Windows 트랙 (setup/start/start-all/stop-all.bat, wsl-portproxy.ps1)
```

---

## 🧮 채번 규칙 (불변)

| 항목 | 규칙 |
|------|------|
| 영문자 24자 | A~Z 중 **O, I 제외** |
| 숫자 9자 | 1~9 (**0 제외**) |
| 1순위 216개 | 영문+숫자 (`A1` ~ `Z9`, score 1~216) |
| 2순위 216개 | 숫자+영문 (`1A` ~ `9Z`, score 217~432) |
| 발급 | 최소 score `WAITING` 1건 → ACTIVE (`BEGIN IMMEDIATE`, 중복 0) |
| 파기 복원 | status→`WAITING` — score 정렬로 **제자리 복귀** |

---

## 🌐 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | Redis 연결 + 큐 크기 |
| POST | `/api/requests` | 채번 의뢰 접수 → `PENDING` |
| GET | `/api/requests?status=` | 의뢰 목록 |
| GET | `/api/requests/{id}` | 의뢰 단건 |
| GET | `/api/codes?status=` | 코드 목록 |
| GET | `/api/codes/peek?n=` | 발급 예정 N개 |
| GET | `/api/codes/{code}` | 단건 (base/full 모두) |
| POST | `/api/codes/issue/{req_id}` | 의뢰 승인 + 발급 (수기 Prefix 조합) |
| POST | `/api/codes/force` | 강제 수기 채번 |
| POST | `/api/codes/revoke/{code}` | 파기 → 원래 순번 복원 |
| GET | `/api/dashboard` | 종합 통계 + next preview |

전체 OpenAPI: 서버 기동 후 <http://localhost:8099/docs>

---

## 🎨 화면 4종

| 화면 | URL | 역할 |
|------|-----|------|
| 메인 | `http://localhost:8099/index.html` | 의뢰 / Admin 분기 + 시스템 상태 |
| 의뢰 | `/request.html` | 의뢰 폼 + 내 의뢰 목록 |
| Admin | `/admin.html` | PENDING 승인 모달 · 전체 코드 테이블 · 강제 채번 · 파기 확인 모달 |
| 대시보드 | `/dashboard.html` | 시맨틱 컬러 카드 + 사용률 게이지 + 자동 새로고침 |

> 모든 화면은 서버와 **동일 오리진(8099)** 에서 서빙되어 접속 IP 무관 자동 동작.

---

## 🛡️ 디자인 시스템 준수

- Bootstrap 5.3 + Vanilla JS만 사용 (Tailwind/jQuery/MUI 금지)
- 모든 코드 출력부에 `.ucs-code` 모노스페이스 적용
- Prefix 입력: 영문·숫자 1~16자 강제 (`^[A-Za-z0-9]{1,16}$`) + 자동 대문자 변환
- 알림: Bootstrap Toast 우측 하단 (`alert()` 절대 금지)
- 파기: Bootstrap Modal + **"결번 복원을 위해 대기열 시퀀스의 원래 순번(제자리)으로 반환됩니다."** 문구
- 파기된 행: `.ucs-row-revoked` (취소선 + 흐림)

세부 규칙: [`ui-design-system.md`](ui-design-system.md)

---

## ✅ 검증 완료

- 432개 생성, O/I/0 제외, Z9→1A 경계 정확
- 의뢰 접수 → 승인 + Prefix=`APP2024` → `APP2024A1` 발급
- 파기 → A1이 score 1 **최상단 제자리 복귀** (peek 검증)
- 소문자 입력 `v2` → 자동 대문자 변환 → `V2A2`
- 강제 채번 `Z9` + `8K` → `8KZ9` (`force_issued: true`)
- 중복 강제 채번 409, Prefix 유효성 위반(`DEV!`, `개발` 등) 422
- 대시보드 통계 일치, 정적 자원/API 라운드트립 통과

---

## 📝 다음 작업 후보

- [ ] 의뢰서 REJECT API
- [ ] Admin / Dashboard 인증·권한 (LAN 무인증 MVP → Basic Auth/IP 화이트리스트)
- [ ] pytest 정식 테스트 스위트
- [ ] HTTPS (nginx/caddy 리버스 프록시 TLS 종단)
- [ ] SQLite `.backup` 정기 스냅샷 자동화

자세한 인계 사항: [`HANDOFF.md`](HANDOFF.md)

---

## 📜 License

MIT
