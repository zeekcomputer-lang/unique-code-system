<#
  wsl-portproxy.ps1  —  WSL2(NAT) 서버를 사내 LAN 에 노출
  ---------------------------------------------------------
  WSL2 는 기본 NAT 모드라 다른 PC 가 Windows 호스트 IP:포트로 접속해도
  WSL 안의 서버로 전달되지 않는다. 이 스크립트가 Windows 에 portproxy 규칙을
  걸어 (WindowsIP:PORT → WSL_IP:PORT) 전달되도록 한다.

  * WSL IP 는 재기동 시 바뀌므로, 부팅 후 또는 WSL 재시작 후 다시 실행해야 한다.
    (작업 스케줄러 '로그온 시' 트리거로 등록 권장)
  * 반드시 "관리자 권한 PowerShell" 에서 실행.

  사용:
    powershell -ExecutionPolicy Bypass -File windows\wsl-portproxy.ps1
    powershell -ExecutionPolicy Bypass -File windows\wsl-portproxy.ps1 -Port 8099
    powershell -ExecutionPolicy Bypass -File windows\wsl-portproxy.ps1 -Remove
#>
param(
  [int]$Port = 8099,
  [switch]$Remove
)

$ErrorActionPreference = "Stop"

# 관리자 권한 확인
$isAdmin = ([Security.Principal.WindowsPrincipal] `
  [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Error "관리자 권한 PowerShell 에서 실행하세요."
  exit 1
}

$ruleName = "UCS WSL portproxy $Port"

if ($Remove) {
  netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 | Out-Null
  Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  Write-Host "✓ portproxy/방화벽 규칙 제거 (port $Port)"
  netsh interface portproxy show v4tov4
  exit 0
}

# 현재 WSL IP 조회 (첫 번째 IPv4)
$wslIp = (wsl.exe hostname -I).Trim().Split(" ")[0]
if ([string]::IsNullOrWhiteSpace($wslIp)) {
  Write-Error "WSL IP 를 가져오지 못했습니다. WSL 이 실행 중인지 확인하세요."
  exit 1
}
Write-Host "WSL IP = $wslIp,  Port = $Port"

# 기존 규칙 제거 후 재등록 (IP 변동 대응)
netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 2>$null | Out-Null
netsh interface portproxy add v4tov4 `
  listenport=$Port listenaddress=0.0.0.0 `
  connectport=$Port connectaddress=$wslIp | Out-Null

# 방화벽 인바운드 허용 (없으면 생성)
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName $ruleName -Direction Inbound `
    -Action Allow -Protocol TCP -LocalPort $Port -Profile Private,Domain | Out-Null
}

Write-Host "✓ 적용 완료. 현재 규칙:"
netsh interface portproxy show v4tov4

# 이 Windows 호스트의 LAN IP 안내
$ips = (Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.PrefixOrigin -ne 'WellKnown' -and $_.IPAddress -notlike '169.*' -and $_.IPAddress -notlike '127.*' } |
  Select-Object -ExpandProperty IPAddress) -join ", "
Write-Host ""
Write-Host "→ 다른 PC 접속 주소:  http://<이 PC IP>:$Port/   (후보 IP: $ips)"
