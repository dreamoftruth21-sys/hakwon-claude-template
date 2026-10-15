# 자료정리 분류 규칙
# 파일(또는 폴더) 이름 → 학원 폴더 기준 상대 경로. 맞는 규칙이 없으면 $null (건드리지 않는다).
# 위에서부터 첫 번째로 맞는 규칙을 쓴다. 구체적인 규칙을 위에, 넓은 규칙을 아래에 둔다.
# {시험:반이름} 은 그 반 시험대비 아래 가장 최근 회차 폴더로 바뀐다.
#
# 처음시작 스킬이 반을 만들 때 그 반 교재 이름 규칙을 「반별 규칙」에 넣는다.
# 사용자가 새 분류를 알려 주면 여기에 한 줄 추가한다. 한 번 물어본 것은 다시 묻지 않게.
# 고친 뒤에는 UTF-8 BOM 으로 저장한다 (Windows PowerShell 5.1 은 BOM 이 없으면 한글 정규식이 깨진다).

function Classify([string]$n) {

  # ── 반별 규칙 (처음시작 스킬이 채운다)
  # 예: if ($n -match 'YBM\(박준언\)') { return '중앙고2\학교자료\부교재' }
  # 예: if ($n -match '고사.*\(중앙고2') { return '중앙고2\학교자료\기출' }

  # ── 모의고사 (학평) → 공용/교재/모의고사/연도_학년_월
  if ($n -match '^(?:\(2022개정\))?(20\d\d)년_(고[123])_0?(\d+)월_') { return "공용\교재\모의고사\$($Matches[1])_$($Matches[2])_$($Matches[3])월" }
  if ($n -match '^(20\d\d)년_0?(\d+)월_(고[123])_') { return "공용\교재\모의고사\$($Matches[1])_$($Matches[3])_$($Matches[2])월" }
  if ($n -match '^(20\d\d) (고[123]) 모의고사 영어 0?(\d+)월') { return "공용\교재\모의고사\$($Matches[1])_$($Matches[2])_$($Matches[3])월" }
  if ($n -match '^(\d\d)년 (고[123]) 0?(\d+)월 (모의고사 )?워크북') { return "공용\교재\모의고사\20$($Matches[1])_$($Matches[2])_$($Matches[3])월" }
  if ($n -match '^모의고사_(\d)학년_(20\d\d)년_0?(\d+)월') { return "공용\교재\모의고사\$($Matches[2])_고$($Matches[1])_$($Matches[3])월" }

  # ── 출석부 · 주간보고서 — 어느 반 것인지 이름으로 모르면 묻는다
  if ($n -match '^@*출석부_|^Weekly Report|주간보고서|주간 ?리포트') { return '_정리대기\다운로드_확인필요' }

  return $null
}

# {시험:반} → 그 반 시험대비 아래 가장 최근 회차 폴더
function Resolve-Dest([string]$root, [string]$dest) {
  if ($dest -notmatch '\{시험:([^}]+)\}') { return $dest }
  $cls = $Matches[1]
  $base = Join-Path $root "$cls\시험대비"
  $latest = Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
  if (-not $latest) { throw "시험대비 회차 폴더가 없다: $base" }
  return $dest -replace '\{시험:[^}]+\}', "시험대비\$($latest.Name)"
}
