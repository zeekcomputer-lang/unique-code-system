# 🐧 WSL2 (Ubuntu) / Linux 운영 가이드

> 이 시스템은 **단일 포트(기본 8099)** 에서 UI(정적) + API 를 함께 서빙합니다.
> 저장소는 **SQLite 단일 파일**이며 **Redis 등 외부 서비스가 필요 없습니다.**
> git clone/pull 후 아래 절차만으로 사내 인트라넷(LAN) 서비스가 가능합니다.

---

## 0. 배포 모델

- 개발환경(현재 WSL2)과 **운영환경은 별개**입니다.
- 운영 절차: **운영 서버에서 저장소를 `git clone`(또는 `git pull`) → `linux/setup.sh` → `linux/start.sh`.**
- 머신 고유값(IP·경로)은 **하드코딩하지 않고 환경변수/문서**로 주입합니다.

---

## 1. 사전 준비 (Ubuntu / WSL2)

```bash
sudo apt update
sudo apt install -y python3 python3-venv git curl
```

---

## 2. 설치 & 기동

```bash
git clone https://github.com/zeekcomputer-lang/unique-code-system.git
cd unique-code-system

bash linux/setup.sh        # 1회: .venv-wsl + 의존성
bash linux/start.sh        # 백그라운드 기동 (:8099)
bash linux/status.sh       # 상태 점검
bash linux/stop.sh         # 종료
```

포그라운드(로그 콘솔)로 보고 싶으면:

```bash
FOREGROUND=1 bash linux/start.sh
```

포트 변경:

```bash
UCS_PORT=9000 bash linux/start.sh
```

접속:

| URL | 화면 |
|-----|------|
| `http://localhost:8099/` | 메인 |
| `http://localhost:8099/dashboard.html` | 대시보드 |
| `http://localhost:8099/docs` | Swagger(OpenAPI) |
| `http://localhost:8099/health` | 헬스 체크 |

> 프론트는 `UCS_API_BASE=""`(상대경로) 이므로 **어떤 IP/호스트로 접속하든 자동으로 같은 서버의 API** 를 호출합니다. 별도 설정 불필요.

---

## 3. 🌐 같은 통신망(LAN) 다른 PC 에서 접속하기

서버는 `0.0.0.0:8099` 로 바인딩되어 있습니다. 접속 방식은 **운영 서버 형태**에 따라 갈립니다.

### 케이스 A) 운영 서버가 "Linux 실물/VM" 인 경우 — **추가 설정 불필요**
그 서버의 고정 IP 로 바로 접속:
```
http://<서버 고정 IP>:8099/
```

### 케이스 B) 운영 서버가 "Windows + WSL2" 인 경우 — **연결 룰 1개 필요**

WSL2 는 기본 **NAT 모드**라, WSL 안의 서버는 자체 가상 IP 를 가집니다.
- Windows **자신**에서 `localhost:8099` → WSL 로 자동 전달됨(이건 자동).
- 그러나 **다른 PC → Windows고정IP:8099** 는 기본적으로 WSL 로 전달되지 않습니다.

→ 아래 **둘 중 하나**로 노출합니다.

**(B-1) portproxy (Win10/11 모두 가능, 권장)**

관리자 PowerShell 에서 (프로젝트의 헬퍼 사용):
```powershell
powershell -ExecutionPolicy Bypass -File windows\wsl-portproxy.ps1 -Port 8099
```
- `WindowsIP:8099 → WSL_IP:8099` 포워딩 + 방화벽 인바운드 허용을 자동 설정합니다.
- **WSL 재기동 시 WSL IP 가 바뀌므로**, 부팅/WSL 재시작 후 다시 실행해야 합니다.
  (작업 스케줄러 "로그온 시" 트리거로 등록 권장)
- 해제: `... wsl-portproxy.ps1 -Remove`

**(B-2) mirrored networking (Windows 11 최신 빌드)**

`C:\Users\<사용자>\.wslconfig` 에 추가 후 `wsl --shutdown`:
```ini
[wsl2]
networkingMode=mirrored
```
- WSL 이 호스트 네트워크를 공유 → **portproxy 없이** `WindowsIP:8099` 로 바로 접속.

접속 주소(양 케이스 공통):
```
http://<Windows 호스트 고정 IP>:8099/
```

> **방화벽 전제:** 인바운드 8099/TCP · 사설망(Private) 규칙은 허용된 상태로 가정합니다(요구사항 C4). portproxy 헬퍼는 규칙을 자동 추가합니다.

---

## 4. 📌 고정 IP 안내 문서화 (운영자용)

호스트 IP 가 **고정**이라면, 사내 안내문/북마크에 아래 형식으로 직접 기입하면 됩니다.
프론트엔드 코드는 IP 를 하드코딩하지 않으므로 **주소만 공유**하면 됩니다.

```
■ 유니크 코드 관리 시스템
  - 접속 주소 : http://192.168.x.x:8099/      ← 운영 서버 고정 IP 로 교체
  - 대시보드 : http://192.168.x.x:8099/dashboard.html
```

특정 NIC 로만 서비스하려면 그 IP 를 직접 바인딩:
```bash
UCS_HOST=192.168.x.x UCS_PORT=8099 bash linux/start.sh
```

---

## 5. 상시 자동기동 (선택, systemd --user)

```bash
bash linux/install-systemd.sh
sudo loginctl enable-linger "$USER"     # 재부팅/로그아웃 후에도 유지
journalctl --user -u ucs.service -f     # 로그
```

---

## 6. 데이터 / 백업

| 항목 | 경로 |
|------|------|
| SQLite DB | `backend/data/ucs.sqlite3` (+ `-wal`, `-shm`) |
| venv | `.venv-wsl/` |
| 로그 | `linux/logs/backend.log` |

백업(무중단 안전):
```bash
sqlite3 backend/data/ucs.sqlite3 ".backup 'backup-$(date +%F).sqlite3'"
```

초기화: 서버 종료 후 `backend/data/ucs.sqlite3*` 삭제 → 재기동 시 432개 자동 시드.

---

## 7. 트러블슈팅

- **다른 PC 에서 접속 안 됨(Windows+WSL2):** §3 케이스 B 의 portproxy/mirrored 확인. `bash linux/status.sh` 로 WSL IP 확인 후 portproxy 재적용.
- **포트 점유:** `bash linux/stop.sh` 또는 `UCS_PORT=9000 bash linux/start.sh`.
- **동시 기동 충돌:** Windows 트랙과 WSL 트랙을 **동시에 같은 포트**로 띄우지 마세요(DB/포트 충돌). start 스크립트가 포트 점유를 감지해 중단합니다.
- **HTTPS:** 현재 MVP 는 HTTP 전용. 향후 nginx/caddy 리버스 프록시로 TLS 종단(8099 를 내부 업스트림으로) 예정.

---

_2Track(Windows/WSL2) 중 WSL2 트랙 가이드 · 단일 포트 + SQLite SSOT_
