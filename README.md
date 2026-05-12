# 🎯 Unique Code Management System

> 2자리 고정 풀(432개) 기반 유니크 코드 의뢰 → 발급 → 파기 → **결번 자동 복원** 관리 시스템

![Stack](https://img.shields.io/badge/backend-FastAPI-009688?style=flat&logo=fastapi)
![Frontend](https://img.shields.io/badge/frontend-Bootstrap%205.3-7952B3?style=flat&logo=bootstrap)
![Redis](https://img.shields.io/badge/redis-ZSET-DC382D?style=flat&logo=redis)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## ✨ 주요 특징

- **결정론적 순차 채번** — 432개 고정 풀 (A1~Z9 + 1A~9Z, O/I/0 제외)
- **결번 자동 복원** — 파기 시 Redis ZSET의 원래 순번(score)으로 제자리 복귀
- **JSON DB + Redis 혼합** — RDBMS 없이 JSON 영속화 + Redis ZSET 원자성
- **Vanilla JS + Bootstrap 5.3** — jQuery/SPA 프레임워크 0 dependency
- **디자인 시스템 100% 준수** — `.ucs-code` 모노스페이스 / Toast 알림 / Modal 파기 확인

---

## 🚀 빠른 시작

### Linux / macOS / WSL

```bash
cd backend
pip install -r requirements.txt
pip install fakeredis            # 실 Redis 없을 때
python run_with_fakeredis.py     # → :8000

# 다른 터미널
cd frontend
python -m http.server 8080       # → http://localhost:8080
```

### Windows 10

```cmd
windows\setup.bat                REM 가상환경 + 의존성 자동 설치
windows\start-all.bat            REM 백/프론트 동시 기동 + 브라우저 자동 오픈
```

자세한 가이드: [`windows/README-WINDOWS.md`](windows/README-WINDOWS.md)

---

## 📁 폴더 구조

```
unique-code-system/
├── HANDOFF.md                  # 다음 작업자용 인계 문서
├── ui-design-system.md         # Bootstrap 5.3 기반 디자인 가이드
├── backend/
│   ├── app/
│   │   ├── core/{codes,config}.py
│   │   ├── db/database.py              # JSON I/O + RLock + atomic write
│   │   ├── services/sequence_manager.py # Redis ZSET 채번 엔진
│   │   ├── models/schemas.py
│   │   ├── api/routes.py
│   │   └── main.py
│   ├── requirements.txt
│   └── run_with_fakeredis.py
├── frontend/
│   ├── index.html · request.html · admin.html · dashboard.html
│   └── assets/{css/ucs-theme.css, js/*.js}
└── windows/{setup,start-*,stop-all}.bat
```

---

## 🧮 채번 규칙 (불변)

| 항목 | 규칙 |
|------|------|
| 영문자 24자 | A~Z 중 **O, I 제외** |
| 숫자 9자 | 1~9 (**0 제외**) |
| 1순위 216개 | 영문+숫자 (`A1` ~ `Z9`, score 1~216) |
| 2순위 216개 | 숫자+영문 (`1A` ~ `9Z`, score 217~432) |
| 발급 | Redis `ZPOPMIN` — 순차, 동시성 보장 |
| 파기 복원 | 원래 score로 `ZADD nx` — **제자리 복귀** |

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

전체 OpenAPI: 서버 기동 후 <http://localhost:8000/docs>

---

## 🎨 화면 4종

| 화면 | URL | 역할 |
|------|-----|------|
| 메인 | `/index.html` | 의뢰 / Admin 분기 + 시스템 상태 |
| 의뢰 | `/request.html` | 의뢰 폼 + 내 의뢰 목록 |
| Admin | `/admin.html` | PENDING 승인 모달 · 전체 코드 테이블 · 강제 채번 · 파기 확인 모달 |
| 대시보드 | `/dashboard.html` | 시맨틱 컬러 카드 + 사용률 게이지 + 자동 새로고침 |

---

## 🛡️ 디자인 시스템 준수

- Bootstrap 5.3 + Vanilla JS만 사용 (Tailwind/jQuery/MUI 금지)
- 모든 코드 출력부에 `.ucs-code` 모노스페이스 적용
- Prefix 입력: `replace(/[^a-zA-Z]/g,'').toUpperCase()` 강제
- 알림: Bootstrap Toast 우측 하단 (`alert()` 절대 금지)
- 파기: Bootstrap Modal + **"결번 복원을 위해 대기열 시퀀스의 원래 순번(제자리)으로 반환됩니다."** 문구
- 파기된 행: `.ucs-row-revoked` (취소선 + 흐림)

세부 규칙: [`ui-design-system.md`](ui-design-system.md)

---

## ✅ 검증 완료

- 432개 생성, O/I/0 제외, Z9→1A 경계 정확
- 의뢰 접수 → 승인 + Prefix=DEV → `DEV-A1` 발급
- 파기 → A1이 score 1 **최상단 제자리 복귀** (peek 검증)
- 강제 채번 `Z9` + `VIP` → `VIP-Z9` (`force_issued: true`)
- 중복 강제 채번 409, Prefix 유효성 위반 422
- 대시보드 통계 일치, 정적 자원/API 라운드트립 통과

---

## 📝 다음 작업 후보

- [ ] 의뢰서 REJECT API
- [ ] Admin / Dashboard 인증·권한
- [ ] pytest 정식 테스트 스위트
- [ ] Docker Compose (app + redis)
- [ ] JSON DB 백업 / 스냅샷 정책

자세한 인계 사항: [`HANDOFF.md`](HANDOFF.md)

---

## 📜 License

MIT
