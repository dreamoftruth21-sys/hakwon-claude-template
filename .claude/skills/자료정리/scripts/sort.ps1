# 자료정리 — 다운로드(또는 지정 폴더)의 수업자료를 학원 폴더 제자리로 옮긴다.
#   계획만:  sort.ps1                 (기본 소스 = 다운로드)
#   실행:    sort.ps1 -Run
#   소스 지정: sort.ps1 -Source "G:\...\학원 수업 준비" -Run   (학원 폴더 루트에 새로 넣은 자료)
#
# 원칙: 지우지 않는다 · 덮어쓰지 않는다 · 규칙에 안 맞는 파일은 건드리지 않는다.
param([string]$Source = (Join-Path $env:USERPROFILE 'Downloads'), [switch]$Run)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$R = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..\..')).Path
. (Join-Path $PSScriptRoot '..\rules.ps1')
$Source = (Resolve-Path -LiteralPath $Source).Path
$REC = Join-Path $R '_정리대기\정리기록'
New-Item -ItemType Directory -Force -Path $REC | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd_HHmm'

# 학원 폴더 루트를 소스로 쓸 때 이미 정리된 곳은 제외
$protected = @('반', '공용', '행정', '_정리대기', '.claude', 'CLAUDE.md', '시작하기.md', '이번주.md', 'desktop.ini')
$ignoreFile = Join-Path $PSScriptRoot '..\무시목록.txt'
$ignore = @{}; if (Test-Path -LiteralPath $ignoreFile) { Get-Content -LiteralPath $ignoreFile -Encoding UTF8 | Where-Object { $_ -and $_ -notlike '#*' } | ForEach-Object { $ignore[$_.Trim()] = 1 } }
$skipExt = '\.(exe|msi|apk|pkg|dmg|egg|winmd|lnk|ini|ico|ttf|otf|crdownload|tmp)$'

# ── 1. 계획
$plan = New-Object System.Collections.Generic.List[object]
$unmatched = New-Object System.Collections.Generic.List[string]
function Add-Plan($file, $dest, $srcRoot) {
  $plan.Add([pscustomobject]@{ Src = $file.FullName; Name = $file.Name; Len = $file.Length; Time = $file.LastWriteTime; Dest = (Resolve-Dest $R $dest); Kind = 'MOVE'; Note = '' })
}
foreach ($it in Get-ChildItem -LiteralPath $Source -Force) {
  if ($Source -eq $R -and $protected -contains $it.Name) { continue }
  if ($it.Name -like '~$*') { continue }
  $dest = Classify $it.Name
  if ($it.PSIsContainer) {
    $files = @(Get-ChildItem -LiteralPath $it.FullName -Recurse -File -Force -ErrorAction SilentlyContinue)
    if ($dest) {
      foreach ($f in $files) {
        $own = Classify $f.Name
        $rel = Split-Path $f.FullName.Substring($it.FullName.Length + 1) -Parent
        if ($own -like '_정리대기*') { Add-Plan $f $own } else { Add-Plan $f $(if ($rel) { Join-Path $dest $rel } else { $dest }) }
      }
    } else {
      # 폴더 이름으로 모르면 안의 파일을 하나씩 본다. 하나도 안 맞으면 폴더째 보고만 한다.
      $hit = 0
      foreach ($f in $files) { $own = Classify $f.Name; if ($own) { Add-Plan $f $own; $hit++ } }
      if ($hit -lt $files.Count -and $files.Count -gt 0 -and -not $ignore.ContainsKey($it.Name)) { $unmatched.Add("[폴더] $($it.Name)  (파일 $($files.Count)개 중 규칙에 안 맞는 것 $($files.Count - $hit)개)") }
    }
  } elseif ($dest) {
    Add-Plan $it $dest
  } elseif ($it.Name -notmatch $skipExt -and -not $ignore.ContainsKey($it.Name)) {
    $unmatched.Add($it.Name)
  }
}

# ── 2. 중복 판정 (크기가 같을 때만 해시)
$existing = @{}
foreach ($top in '반', '공용', '행정', '.claude') {
  Get-ChildItem -LiteralPath (Join-Path $R $top) -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not $existing.ContainsKey($_.Length)) { $existing[$_.Length] = New-Object System.Collections.Generic.List[string] }
    $existing[$_.Length].Add($_.FullName)
  }
}
$hashCache = @{}
function Get-Md5($p) { if (-not $hashCache.ContainsKey($p)) { $hashCache[$p] = (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash }; $hashCache[$p] }
$seen = @{}
foreach ($it in ($plan | Sort-Object Time -Descending)) {
  if ($it.Dest -like '_정리대기\삭제예정*') { continue }
  if ($existing.ContainsKey($it.Len)) {
    $h = Get-Md5 $it.Src
    $same = $existing[$it.Len] | Where-Object { (Get-Md5 $_) -eq $h } | Select-Object -First 1
    if ($same) { $it.Kind = 'DUP'; $it.Note = $same.Substring($R.Length + 1); continue }
  }
  if (@($plan | Where-Object { $_.Len -eq $it.Len -and $_.Src -ne $it.Src }).Count -gt 0) {
    $h = Get-Md5 $it.Src
    if ($seen.ContainsKey($h)) { $it.Kind = 'DUP'; $it.Note = '같은 소스 안 사본: ' + $seen[$h]; continue }
    $seen[$h] = $it.Name
  }
}

$planFile = Join-Path $REC "${stamp}_계획.csv"
$plan | Select-Object Kind, Dest, Name, Note, Src | Export-Csv -LiteralPath $planFile -NoTypeInformation -Encoding UTF8

"소스: $Source"
"계획: 이동 {0} · 중복 {1} · 규칙에 안 맞음 {2}" -f @($plan | Where-Object Kind -eq 'MOVE').Count, @($plan | Where-Object Kind -eq 'DUP').Count, $unmatched.Count
$plan | Where-Object Kind -eq 'MOVE' | Group-Object Dest | Sort-Object Name | ForEach-Object { "{0,4}  {1}" -f $_.Count, $_.Name }
if ($unmatched.Count) { "── 규칙에 안 맞은 것 (이름으로 수업자료인지 판단할 것)"; $unmatched | ForEach-Object { "  $_" } }
"계획 파일: $planFile"
if (-not $Run) { return }

# ── 3. 실행
$LOG = Join-Path $REC "${stamp}_이동.tsv"
$cnt = @{ MOVE = 0; DUP = 0; REPLACE = 0; OLDER = 0; LOCKED = 0 }
function Log($k, $a, $b) { "$k`t$a`t$b" | Out-File -LiteralPath $LOG -Append -Encoding utf8 }
function Free-Path($dir, $name) {
  $p = Join-Path $dir $name; if (-not (Test-Path -LiteralPath $p)) { return $p }
  $base = [IO.Path]::GetFileNameWithoutExtension($name); $ext = [IO.Path]::GetExtension($name); $i = 1
  do { $p = Join-Path $dir ("{0}__{1}{2}" -f $base, $i, $ext); $i++ } while (Test-Path -LiteralPath $p)
  $p
}
function Try-Move($src, $dst) {
  try { Move-Item -LiteralPath $src -Destination $dst; return $true }
  catch {
    # 다른 드라이브로 옮길 때는 복사 후 원본 삭제라, 원본이 잠겨 있으면 사본만 남는다 → 사본을 치운다
    if ((Test-Path -LiteralPath $src) -and (Test-Path -LiteralPath $dst)) { Remove-Item -LiteralPath $dst -Force }
    return $false
  }
}
foreach ($it in $plan) {
  if (-not (Test-Path -LiteralPath $it.Src)) { continue }
  if ($it.Kind -eq 'DUP') {
    $dir = Join-Path $R '_정리대기\_중복'; New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $dst = Free-Path $dir $it.Name
    if (Try-Move $it.Src $dst) { $cnt.DUP++; Log 'DUP' $it.Src "$dst (같은 파일: $($it.Note))" } else { $cnt.LOCKED++; Log 'LOCKED' $it.Src '' }
    continue
  }
  $dir = Join-Path $R $it.Dest; New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $dst = Join-Path $dir $it.Name
  if (Test-Path -LiteralPath $dst) {
    # 같은 이름, 다른 내용 → 최신본을 제자리에, 나머지는 _충돌
    $cdir = Join-Path $R "_정리대기\_충돌\$($it.Dest)"; New-Item -ItemType Directory -Force -Path $cdir | Out-Null
    $old = Get-Item -LiteralPath $dst
    if ($it.Time -gt $old.LastWriteTime) {
      $park = Free-Path $cdir $it.Name
      Move-Item -LiteralPath $dst -Destination $park
      if (Try-Move $it.Src $dst) { $cnt.REPLACE++; Log 'REPLACE' $it.Src "$dst (구버전 → $park)" }
      else { Move-Item -LiteralPath $park -Destination $dst; $cnt.LOCKED++; Log 'LOCKED' $it.Src '' }
    } else {
      $park = Free-Path $cdir $it.Name
      if (Try-Move $it.Src $park) { $cnt.OLDER++; Log 'OLDER' $it.Src "$park (제자리에 더 최신본 있음)" } else { $cnt.LOCKED++; Log 'LOCKED' $it.Src '' }
    }
    continue
  }
  if (Try-Move $it.Src $dst) { $cnt.MOVE++; Log 'MOVE' $it.Src $dst } else { $cnt.LOCKED++; Log 'LOCKED' $it.Src '' }
}

# 소스 안에서 비게 된 폴더만 지운다 (파일이 하나라도 있으면 둔다)
foreach ($d in Get-ChildItem -LiteralPath $Source -Directory -Force) {
  if ($Source -eq $R -and $protected -contains $d.Name) { continue }
  $touched = @($plan | Where-Object { $_.Src -like "$($d.FullName)\*" }).Count -gt 0
  if ($touched -and @(Get-ChildItem -LiteralPath $d.FullName -Recurse -File -Force -ErrorAction SilentlyContinue).Count -eq 0) {
    try { [IO.Directory]::Delete($d.FullName, $true) } catch { "빈 폴더 삭제 실패(직접 지울 것): $($d.Name)" }
  }
}

"실행: 이동 {0} · 중복 {1} · 최신본으로 교체 {2} · 구버전 {3} · 잠김 {4}" -f $cnt.MOVE, $cnt.DUP, $cnt.REPLACE, $cnt.OLDER, $cnt.LOCKED
if ($cnt.LOCKED) { "── 잠겨서 못 옮긴 것 (열려 있는 뷰어를 닫고 다시 실행)"; Get-Content -LiteralPath $LOG -Encoding UTF8 | Where-Object { $_ -like 'LOCKED*' } | ForEach-Object { '  ' + (Split-Path ($_ -split "`t")[1] -Leaf) } }
"기록: $LOG"
