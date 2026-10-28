# 처음시작 1단계 — 이 템플릿이 쓰는 프로그램을 한 번에 깐다. 이미 있는 것은 건너뛴다.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File 공용/설치/프로그램설치.ps1          깔기
#   powershell -NoProfile -ExecutionPolicy Bypass -File 공용/설치/프로그램설치.ps1 -Check   무엇이 있고 없는지만 본다
#
# 한 번 허용으로 끝나게 명령 여러 개를 이 파일 하나에 묶었다. Python 은 사용자 계정에 깔아 윈도우 「예」 창이 뜨지 않는다.
# Node · LibreOffice 는 관리자 설치라 「예」 창이 한 번씩 뜬다. 마지막 줄에 결과를 한 줄씩 적는다.
param([switch]$Check)

$ErrorActionPreference = 'Continue'
$result = [ordered]@{}

function Has($name) { $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }
function RefreshPath { $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') }
function PyCmd {
    if (Has 'py') { return 'py' }
    $p = Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'
    if (Test-Path $p) { return $p }
    return $null
}
function Winget($id, $extra) {
    $args = @('install', '-e', '--id', $id, '--silent', '--accept-source-agreements', '--accept-package-agreements') + $extra
    & winget @args | Out-Host
    return $LASTEXITCODE
}
$soffice = @('C:\Program Files\LibreOffice\program\soffice.com', 'C:\Program Files (x86)\LibreOffice\program\soffice.com') |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $soffice) { $soffice = 'C:\Program Files\LibreOffice\program\soffice.com' }

# ── 무엇이 있나 ─────────────────────────────────────────────
$need = [ordered]@{
    'Python'      = -not (PyCmd)
    'Node'        = -not (Has 'node')
    'LibreOffice' = -not (Test-Path $soffice)
}
if ($Check) {
    foreach ($k in $need.Keys) { Write-Output ("{0}: {1}" -f $k, $(if ($need[$k]) { '없음' } else { '있음' })) }
    $py = PyCmd
    if ($py) {
        & $py -c "import importlib.util as u; m=['fitz','playwright','pdfplumber','openpyxl','docx','olefile']; print('Python 모듈 없음: ' + (', '.join(x for x in m if not u.find_spec(x)) or '없음'))"
    }
    Write-Output ("clasp: {0}" -f $(if (Has 'clasp') { '있음' } else { '없음' }))
    exit 0
}

# ── 1. 프로그램 ─────────────────────────────────────────────
if ($need['Python']) {
    Write-Output '[Python] 설치합니다 (사용자 계정)'
    $null = Winget 'Python.Python.3.12' @('--scope', 'user')
    RefreshPath
    $result['Python'] = $(if (PyCmd) { '설치함' } else { '실패' })
} else { $result['Python'] = '있음' }

if ($need['Node']) {
    Write-Output '[Node] 설치합니다 — 윈도우 「예」 창이 뜹니다'
    $null = Winget 'OpenJS.NodeJS.LTS' @()
    RefreshPath
    $result['Node'] = $(if (Has 'node') { '설치함' } else { '실패' })
} else { $result['Node'] = '있음' }

if ($need['LibreOffice']) {
    Write-Output '[LibreOffice] 설치합니다 — 내려받기가 커서 5분쯤 걸립니다. 윈도우 「예」 창이 뜹니다'
    $null = Winget 'TheDocumentFoundation.LibreOffice' @()
    $result['LibreOffice'] = $(if (Test-Path $soffice) { '설치함' } else { '실패 (단어 시험지에만 쓴다 — 나중에 다시)' })
} else { $result['LibreOffice'] = '있음' }

# ── 2. Python 모듈 · 브라우저 ───────────────────────────────
$py = PyCmd
if ($py) {
    Write-Output '[Python 모듈] 설치합니다'
    & $py -m pip install --quiet --disable-pip-version-check pymupdf playwright pdfplumber openpyxl python-docx olefile | Out-Host
    & $py -m playwright install chromium | Out-Host
    $result['Python 모듈'] = $(if ($LASTEXITCODE -eq 0) { '설치함' } else { '실패' })
} else { $result['Python 모듈'] = '건너뜀 (Python 없음)' }

# ── 3. clasp · docx (Node) ──────────────────────────────────
if (Has 'npm') {
    Write-Output '[clasp · docx] 설치합니다'
    & npm install -g --silent @google/clasp docx | Out-Host
    $root = (& npm root -g).Trim()
    [Environment]::SetEnvironmentVariable('NODE_PATH', $root, 'User')
    $env:NODE_PATH = $root
    RefreshPath
    $result['clasp · docx'] = $(if (Has 'clasp') { '설치함' } else { '실패' })
} else { $result['clasp · docx'] = '건너뜀 (Node 없음)' }

# ── 결과 ───────────────────────────────────────────────────
Write-Output ''
Write-Output '== 결과 =='
foreach ($k in $result.Keys) { Write-Output ("{0}: {1}" -f $k, $result[$k]) }
if ($result.Values -match '실패') { exit 1 } else { exit 0 }
