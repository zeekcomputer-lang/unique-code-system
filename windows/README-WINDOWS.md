# 🪟 Windows 네이티브 운영 가이드

> **단일 포트(기본 8099)** 에서 UI + API 를 함께 서빙합니다.
> 저장소는 **SQLite 단일 파일**, **Redis 등 외부 서비스 불필요.**
> WSL2 트랙은 [`../linux/README-WSL2.md`](../linux/README-WSL2.md) 참조.

---

## 0. 사전 준비

1. **Python 3.10 이상** — <https://www.python.org/downloads/> (설치 시 **"Add Python to PATH" 체크**)
2. 최신 브라우저 (Chrome / Edge)

---

## 1. 설치 (1회)

```cmd
cd C:\projects\unique-code-system
windows\setup.bat
```
- `.venv` 생성 + `backend\requirements.txt` 설치 + `backend\data\` 생성.

---

## 2. 기동 / 종료

```cmd
windows\start.bat        REM 단일 서버(:8099) 콘솔 기동
windows\start-all.bat    REM 서버 기동 + 브라우저 자동 오픈
windows\stop-all.bat     REM 8099 포트 프로세스 종료
```

포트 변경:
```cmd
set UCS_PORT=9000
windows\start.bat
```

---

## 3. 접속

| URL | 화면 |
|-----|------|
| `http://localhost:8099/` | 메인 |
| `http://localhost:8099/dashboard.html` | 대시보드 |
| `http://localhost:8099/docs` | Swagger(OpenAPI) |
| `http://localhost:8099/health` | 헬스 체크 |

프론트는 상대경로(`UCS_API_BASE=""`)로 호출하므로 **접속 IP 무관 자동 동작**.

---

## 4. 🌐 같은 통신망(LAN) 다른 PC 에서 접속

서버가 `0.0.0.0:8099` 로 바인딩되므로, **Windows 네이티브 실행 시** 다른 PC 는
이 PC 의 고정 IP 로 바로 접속합니다:

```
http://<이 PC 고정 IP>:8099/
```

- 방화벽 인바운드 8099/TCP(사설망) 허용 전제(요구사항 C4).
- 사내 안내문에는 고정 IP 를 직접 기입해 공유하면 됩니다(코드 하드코딩 불필요).

> ⚠️ **WSL2 안에서 띄운 경우**는 네트워킹이 다릅니다(NAT). 그때는
> [`../linux/README-WSL2.md`](../linux/README-WSL2.md) §3 의 portproxy/mirrored 를 따르세요.

---

## 5. 데이터 / 백업

| 항목 | 경로 |
|------|------|
| SQLite DB | `backend\data\ucs.sqlite3` (+ `-wal`, `-shm`) |
| 가상환경 | `.venv\` |

초기화: 서버 종료 후 `backend\data\ucs.sqlite3*` 삭제 → 재기동 시 432개 자동 시드.

---

## 6. 자주 발생하는 문제

- **python 없음:** PATH 미등록. 재설치 시 "Add Python to PATH" 체크.
- **포트 점유:** `windows\stop-all.bat` 또는 `set UCS_PORT=9000`.
- **pip 프록시:** `.venv\Scripts\activate.bat` 후 `pip install --proxy http://USER:***@proxy:8080 -r backend\requirements.txt`.
- **CMD 한글 깨짐:** `chcp 65001`.

---

## 7. 운영 전환 체크리스트

- [ ] 고정 IP / DHCP 예약 확인
- [ ] 방화벽 인바운드 8099/TCP 규칙
- [ ] `backend\data\ucs.sqlite3` 정기 백업 (`.backup` 권장)
- [ ] 상시 실행: 작업 스케줄러 "로그온 시" `windows\start.bat` 등록
- [ ] (향후) HTTPS: nginx/caddy 리버스 프록시 TLS 종단

---

_Windows 네이티브 트랙 · 단일 포트 + SQLite SSOT_
