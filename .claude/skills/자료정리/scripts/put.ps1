# 파일 하나를 학원 폴더 안 지정 위치로 옮긴다. 사용자가 확인해 준 뒤 손으로 옮길 때 쓴다.
#   put.ps1 -Src "C:\...\파일.pdf" -Dest "세종예고2\학교자료\부교재"
# sort.ps1 과 같은 원칙: 덮어쓰지 않는다. 같은 파일이면 _중복, 이름만 같으면 최신본을 제자리에.
param([Parameter(Mandatory)][string]$Src, [Parameter(Mandatory)][string]$Dest)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$R = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..\..')).Path
$REC = Join-Path $R '_정리대기\정리기록'; New-Item -ItemType Directory -Force -Path $REC | Out-Null
$LOG = Join-Path $REC ((Get-Date -Format 'yyyy-MM-dd') + '_수동.tsv')

$f = Get-Item -LiteralPath $Src
$dir = Join-Path $R $Dest; New-Item -ItemType Directory -Force -Path $dir | Out-Null
$dst = Join-Path $dir $f.Name
function Free-Path($d, $name) { $q = Join-Path $d $name; if (-not (Test-Path -LiteralPath $q)) { return $q }; $b = [IO.Path]::GetFileNameWithoutExtension($name); $e = [IO.Path]::GetExtension($name); $i = 1; do { $p = Join-Path $d ("{0}__{1}{2}" -f $b, $i, $e); $i++ } while (Test-Path -LiteralPath $p); $p }

if (Test-Path -LiteralPath $dst) {
  $old = Get-Item -LiteralPath $dst
  if ((Get-FileHash -LiteralPath $f.FullName -Algorithm MD5).Hash -eq (Get-FileHash -LiteralPath $dst -Algorithm MD5).Hash) {
    $d = Join-Path $R '_정리대기\_중복'; New-Item -ItemType Directory -Force -Path $d | Out-Null
    $p = Free-Path $d $f.Name; Move-Item -LiteralPath $f.FullName -Destination $p
    "DUP`t$Src`t$p" | Out-File -LiteralPath $LOG -Append -Encoding utf8; "중복 — 같은 파일이 이미 $Dest 에 있다"; return
  }
  $c = Join-Path $R "_정리대기\_충돌\$Dest"; New-Item -ItemType Directory -Force -Path $c | Out-Null
  $p = Free-Path $c $f.Name
  if ($f.LastWriteTime -gt $old.LastWriteTime) {
    Move-Item -LiteralPath $dst -Destination $p; Move-Item -LiteralPath $f.FullName -Destination $dst
    "REPLACE`t$Src`t$dst (구버전 → $p)" | Out-File -LiteralPath $LOG -Append -Encoding utf8; "최신본으로 교체 — 구버전은 _충돌"
  } else {
    Move-Item -LiteralPath $f.FullName -Destination $p
    "OLDER`t$Src`t$p" | Out-File -LiteralPath $LOG -Append -Encoding utf8; "구버전 — 제자리에 더 최신본이 있어 _충돌로"
  }
  return
}
Move-Item -LiteralPath $f.FullName -Destination $dst
"MOVE`t$Src`t$dst" | Out-File -LiteralPath $LOG -Append -Encoding utf8
"이동 → $Dest"
