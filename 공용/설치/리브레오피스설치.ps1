# 처음시작 1단계 끝 — LibreOffice 만 따로 깐다. 내려받기가 커서(350MB 남짓) 백그라운드로 돌리고 그동안 2단계(자료 정리)를 한다.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File 공용/설치/리브레오피스설치.ps1
#
# 15초마다 진행 한 줄(받은 MB · % · 걸린 시간)을 화면과 진행 파일(%TEMP%\LibreOffice설치_진행.txt)에 적는다.
# Claude 는 그 파일 한 줄을 읽어 선생님께 알린다. 2분 넘게 크기가 그대로면 「멈춤?」을 붙인다.
# 내려받기가 끝나면 윈도우 「예」 창이 한 번 뜬다. 마지막 줄: 「LibreOffice: 있음 · 설치함 · 실패」.
# Python · Node 설치(프로그램설치.ps1)가 끝난 뒤에 돌린다 — 윈도우 설치 관리자는 한 번에 하나만 깐다.

$ErrorActionPreference = 'Continue'
$id = 'TheDocumentFoundation.LibreOffice'
$progressFile = Join-Path $env:TEMP 'LibreOffice설치_진행.txt'
$soffice = @('C:\Program Files\LibreOffice\program\soffice.com', 'C:\Program Files (x86)\LibreOffice\program\soffice.com') |
    Where-Object { Test-Path $_ } | Select-Object -First 1

function Say($line) {
    Write-Output $line
    Set-Content -Path $progressFile -Value $line -Encoding utf8
}

if ($soffice) { Say 'LibreOffice: 있음'; exit 0 }

# 전체 크기 — winget 이 알려 주는 설치 파일 주소에 크기만 물어본다. 못 알아내면 %는 빼고 MB 만 적는다
$totalMB = 0
try {
    $info = winget show -e --id $id --accept-source-agreements | Out-String
    $url = ([regex]'https?://\S+\.(msi|exe)').Match($info).Value
    if ($url) {
        $head = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 20
        $totalMB = [int]([int64]$head.Headers['Content-Length'] / 1MB)
    }
} catch { }

$start = Get-Date
Say ('LibreOffice 내려받기를 시작합니다' + $(if ($totalMB) { " (전체 $totalMB MB)" } else { '' }))
$p = Start-Process winget -PassThru -WindowStyle Hidden -ArgumentList @(
    'install', '-e', '--id', $id, '--silent', '--accept-source-agreements', '--accept-package-agreements')
$null = $p.Handle   # 끝난 뒤 ExitCode 를 읽으려면 미리 잡아 둔다

# winget 은 %TEMP%\WinGet\<패키지>.<버전>\ 에 설치 파일을 받는다 — 시작 뒤에 바뀐 파일 크기를 더한다
$dlDir = Join-Path $env:TEMP 'WinGet'
$lastMB = -1; $sameSince = Get-Date
while (-not $p.WaitForExit(15000)) {
    $bytes = (Get-ChildItem $dlDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $start.AddMinutes(-1) -and $_.FullName -notmatch '\\cache\\' } |
        Measure-Object Length -Sum).Sum
    $mb = [int]($bytes / 1MB)
    $min = [int]((Get-Date) - $start).TotalMinutes
    if ($mb -ne $lastMB) { $lastMB = $mb; $sameSince = Get-Date }
    $stuck = ((Get-Date) - $sameSince).TotalMinutes -ge 2

    if ($totalMB -and $mb -ge $totalMB - 1) {
        Say "LibreOffice 설치 중 — 내려받기 끝. 윈도우 「예」 창이 떴으면 「예」를 눌러 주세요 · $min 분 지남"
    } elseif ($mb -eq 0) {
        Say "LibreOffice 내려받기 준비 중 · $min 분 지남"
    } else {
        $pct = $(if ($totalMB) { " / $totalMB MB (" + [int](100 * $mb / $totalMB) + '%)' } else { ' MB' })
        Say ("LibreOffice 내려받는 중 $mb$pct · $min 분 지남" + $(if ($stuck) { ' · 2분째 그대로 — 멈춤? 인터넷 확인' } else { '' }))
    }
}

$soffice = @('C:\Program Files\LibreOffice\program\soffice.com', 'C:\Program Files (x86)\LibreOffice\program\soffice.com') |
    Where-Object { Test-Path $_ } | Select-Object -First 1
$min = [int]((Get-Date) - $start).TotalMinutes
if ($soffice) { Say "LibreOffice: 설치함 ($min 분)"; exit 0 }
Say "LibreOffice: 실패 (winget 끝 코드 $($p.ExitCode) — 「예」 창을 놓쳤으면 같은 명령을 다시 돌린다. 단어 시험지에만 쓴다)"
exit 1
