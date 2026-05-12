# 🪟 Windows 10 로컬 구동 가이드

> 본 가이드는 **Windows 10** 환경에서 별도 도커/WSL 없이 로컬 PC로 시스템을 띄우는 절차입니다.

---

## 0. 사전 준비

1. **Python 3.10 이상** 설치
   - 다운로드: <https://www.python.org/downloads/>
   - 설치 시 **"Add Python to PATH" 체크 필수**
2. (선택) **Git** 또는 압축 풀린 프로젝트 폴더
3. 최신 브라우저 (Chrome / Edge 권장)
4. (선택, 운영용) Redis for Windows
   - <https://github.com/tporadowski/redis/releases> 또는 WSL의 redis-server
   - 미설치 시 **fakeredis 모드**로 동작 (개발/데모용)

---

## 1. 폴더 준비

프로젝트 전체를 임의의 경로에 배치합니다. 권장 경로:

```
C:\projects\unique-code-system\
├── backend\
├── frontend\
├── windows\
└── ...
```

---

## 2. 초기 설정 (1회만)

`windows\setup.bat` 더블클릭 또는 명령 프롬프트 실행:

```cmd
cd C:\projects\unique-code-system
windows\setup.bat
```

수행 내용:
- Python 버전 확인
- `.venv\` 가상환경 생성
- `backend\requirements.txt` + `fakeredis` 설치
- `backend\data\` 폴더 생성

---

## 3. 실행

### 3-1. 한 번에 띄우기 (권장)

```cmd
windows\start-all.bat
```

→ 백엔드(:8099)와 프론트엔드(:8989) 콘솔 창이 별도로 열리고, 자동으로 브라우저가 `http://localhost:8989/index.html` 을 엽니다.

### 3-2. 개별 기동

```cmd
windows\start-backend.bat        REM fakeredis 모드 (기본)
windows\start-frontend.bat       REM 정적 서버
```

### 3-3. 실 Redis로 기동

먼저 Redis 서버를 띄우고:

```cmd
set USE_REAL_REDIS=1
set UCS_REDIS_URL=redis://localhost:6379/0
windows\start-backend.bat
```

---

## 4. 종료

각 콘솔 창에서 `Ctrl + C` 또는 X 버튼.

전부 한 번에 정리:

```cmd
windows\stop-all.bat
```

→ 8099/8989 포트를 점유한 python.exe 프로세스를 `taskkill` 로 종료.

---

## 5. 접속 URL

| URL | 화면 |
|-----|------|
| <http://localhost:8989/index.html> | 메인 분기 |
| <http://localhost:8989/request.html> | 채번 의뢰 |
| <http://localhost:8989/admin.html> | Admin 콘솔 |
| <http://localhost:8989/dashboard.html> | 대시보드 |
| <http://localhost:8099/docs> | Swagger UI (OpenAPI) |
| <http://localhost:8099/health> | 헬스 체크 |

---

## 6. 자주 발생하는 문제

### ❌ "python 명령을 찾을 수 없습니다"
PATH에 등록되지 않은 경우. Python 재설치 시 **Add Python to PATH** 체크 후 PC 재로그인.

### ❌ "포트 8099/8989 이 이미 사용 중"
```cmd
windows\stop-all.bat
```
또는 작업 관리자에서 해당 python.exe 종료.

### ❌ pip 설치 실패 (TLS / 회사 프록시)
```cmd
.venv\Scripts\activate.bat
pip install --proxy http://USER:PASS@proxy.company.com:8080 -r backend\requirements.txt
```

### ❌ 한글 깨짐 (CMD)
콘솔 코드페이지를 UTF-8로:
```cmd
chcp 65001
```

### ❌ 방화벽 차단
사설 네트워크 사용 시 Windows Defender 방화벽이 python.exe의 인바운드를 차단할 수 있음. 첫 실행 시 **허용** 선택. 외부 PC에서 접근 필요 시 인바운드 규칙으로 8989/TCP 허용.

---

## 7. 데이터 위치

| 항목 | 경로 |
|------|------|
| JSON DB | `backend\data\ucs.json` |
| 가상환경 | `.venv\` |
| 백엔드 로그 | 백엔드 콘솔 창 (별도 파일 출력 없음) |

JSON DB를 초기화하려면 백엔드를 종료한 뒤 파일을 삭제하고 다시 기동.

---

## 8. 운영 전환 시 체크리스트

- [ ] Redis for Windows 또는 외부 Redis 인스턴스 연결 (`USE_REAL_REDIS=1`)
- [ ] Windows 작업 스케줄러로 백엔드 자동 시작 등록
- [ ] 외부 노출 시 IIS / nginx 리버스 프록시 앞단 배치
- [ ] `backend\data\ucs.json` 일/주 단위 백업 작업 등록
- [ ] 방화벽 인바운드 규칙 명시

---

## 9. 디자인 시스템

브라우저에서 직접 확인:
- 메인 → Admin → 의뢰 승인 모달 (Prefix 입력 + 실시간 미리보기)
- 코드 테이블 → 파기 버튼 → "결번 복원..." 확인 모달
- 대시보드 → 시맨틱 컬러 카드 + 사용률 게이지

세부 규칙: `..\ui-design-system.md`

---

_Windows 10 (1809+) / Windows 11 동작 확인_
