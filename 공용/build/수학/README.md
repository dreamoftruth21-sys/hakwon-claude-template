# 수학 시험지 빌더

학교 규격 수학 시험지(선택형 · 단답형 · 서술형)와 정답 · 해설 답지를 data.json 하나로 만든다.
수식은 KaTeX 로 조판하고, 그림은 좌표를 계산해 SVG 로 그리고, 정답은 sympy 로 검산한다. 점검에 하나라도 걸리면 PDF 를 내지 않는다.

```
py 공용/build/수학/build.py <data.json> [--out 폴더] [--html]
```
- 결과: `<name>.pdf`(학생용) · `<name>_답지.pdf`(정답 · 해설 · 채점 기준). `--out` 이 없으면 data.json 옆에 둔다. `--html` 은 조판 HTML 도 남긴다(눈으로 고칠 때)
- 예시: `예시/샘플_수학.json` (선택형 6 · 서답형 2 · 30점, 그림 4개) — 형식이 헷갈리면 이 파일을 복사해 고친다
- 학교 규격: `공용/build/학교/<school>.json` 의 `math_exam` (처음에는 `_예시.json` 뿐. 반을 만들 때 `시험지분석` 스킬이 그 학교 기출로 쓴다)
- 필요한 것: `pip install sympy` · `npm install -g katex` (그 밖은 다른 빌더와 같다 — pymupdf · playwright)

## JSON 에서 역슬래시는 두 번

수식은 LaTeX 로 쓰고 글 속에 `$…$`(글줄 안) · `$$…$$`(가운데 한 줄)로 넣는다. **JSON 문자열 안에서는 `\` 를 `\\` 로 쓴다.**
`"$\\dfrac{1}{2}$"` ○ · `"$\dfrac{1}{2}$"` ✕ — `\f` · `\t` · `\b` · `\n` · `\r` 이 제어문자가 되어 `\frac` · `\times` · `\beta` · `\neq` · `\right` 가 소리 없이 깨진다. 빌더가 제어문자를 찾으면 막는다.
글자 그대로의 `$` 는 `\\$`. 점 이름은 `$\\mathrm{A}$`(바로 선 글자), 변수는 그냥 `$x$`.

## data.json

| 키 | 뜻 |
|---|---|
| `subject` | `"math"` (온라인 채점 변환이 이것으로 수학인 줄 안다) |
| `school` | 학교 규격 파일 이름 (`학교/<school>.json`) |
| `name` | 파일 이름 (확장자 없이) |
| `title` · `subtitle` | 첫 쪽 제목 · 부제 — 제목에 반 · 연도 · 회차 |
| `guide` | 첫 쪽 안내 한 줄 |
| `footer` | 쪽 아래 글 (쪽번호는 저절로) |
| `covered` | 진도가 나간 단원 목록. 문항의 `unit` 이 여기 없으면 멈춘다 |
| `range_block` | 들어가면 안 되는 낱말 (진도 밖 개념 이름 등). 선택 |
| `macros` | KaTeX 매크로 `{"\\R": "\\mathbb{R}"}`. 선택 |
| `questions` | 문항 목록 — 선택형을 모두 앞에, 서답형을 뒤에. 번호는 선택형 1부터 · 서답형 1부터 따로 |

### 문항

공통: `n` · `kind`(`choice` · `short` · `essay`) · `pt`(배점) · `unit`(covered 안의 단원) · `type`(유형 이름 — 온라인 채점 · 약점 분석이 쓴다) · `stem`(발문) · `sol`(해설) · `fig`(발문 그림) · `sol_fig`(해설 그림) · `verify`(검산).

| kind | 더 쓰는 키 |
|---|---|
| `choice` | `opts`(5개, ①~⑤ 는 쓰지 않는다) · `ans`(정답 번호, **0부터**) · `show`(선택지 배치 `auto` · `row` · `grid32` · `cols2` · `list`, 기본 auto) · `opt_values`(수식으로 못 읽는 선택지의 값) |
| `short` | `answer`(모범답안, 수식) · `value`(answer 를 못 읽을 때 값) · `accept`(온라인 채점 인정 글자 `["5√2","5루트2"]`) · `space_mm` |
| `essay` | `answer` · `value` · `steps`(`[{"desc": 채점 단계, "pt": 점수}]` — 합이 `pt`) · `criteria`(감점 기준 글) · `space_mm`(풀이 칸 높이, 기본은 규격 `essay_space_mm`) |

- 선택지 속 `\frac` 은 `\dfrac` 으로 키운다. `show: auto` 는 가장 긴 선택지 글자 수로 고른다 (5자 이하 한 줄 · 9자 이하 3+2 · 18자 이하 2단 · 그보다 길면 한 줄에 하나)
- 서답형 이름(「서답형 1.」)과 배점 표기(「[4점]」)는 학교 규격의 `written_label` · `pt_format`

## 검산 (verify)

sympy 식이나 짧은 코드. `from sympy import *` 가 깔려 있다.
- 한 줄 식: `"sqrt(5**2 - 3**2)"`
- 여러 문장: `"x = symbols('x'); r = solve(x**2-3*x-4, x); result = r[1]-r[0]"` — 답을 `result`(또는 `답`)에 넣는다

비교
- 선택형: 다섯 선택지 값 중 검산 값과 같은 것이 **정확히 하나**이고 그것이 `ans` 여야 한다. 값이 같은 선택지 둘(√8 과 2√2)도 막는다
- 단답형: `answer`(못 읽으면 `value`)가 검산 값과 같아야 한다
- 서술형: `value` 와 비교한다 (좌표는 `"(9/2, 0)"` 처럼 튜플)
- 수식 읽기: 분수 · 근호 · π · 거듭제곱 · 곱셈 생략 · Σ. `i` 는 허수단위로 읽는다
- `verify` 가 없는 문항은 알림만 하고 넘어간다 — 계산 문항에는 반드시 쓴다

## 그림(fig)

그림은 좌표를 손으로 짐작하지 않는다. 점을 정의하면 파이썬(sympy)이 정확히 계산해 그리고, 맞지 않으면 빌드를 멈춘다.
흑백 인쇄 기준: 선은 모두 검정, 보조선은 점선, 색칠은 빗금 또는 회색.

### 좌표 그림

```json
{"x": [-2, 6], "y": [-1, 5], "w": 50, "axes": true, "grid": 1,
 "ticks": {"x": [1, 2, {"v": 4, "t": "a"}], "y": [1, 2]},
 "points": {"O": [0, 0], "A": {"polar": ["O", 4, 60]}},
 "items": [ … ],
 "asserts": [["dist(O,A)", "4"]]}
```
| 키 | 뜻 |
|---|---|
| `x` · `y` | 보여 줄 범위 (수학 좌표) |
| `w` · `h` | 그림 폭 · 높이 (mm). 기본 폭 52. 여백을 더해 한 단 폭(86mm)을 넘으면 멈춘다 |
| `equal` | 가로세로 같은 비율 (기본 true). 원을 그리려면 true 여야 한다 |
| `axes` | `true` 또는 `{"x": "x", "y": "y", "origin": "O"}` (축 이름 · 원점 이름) |
| `ticks` | 눈금 `[값 …]` 또는 `{"v": 값, "t": "이름표"}` |
| `grid` | 모눈 간격 (회색) |
| `points` | 이름 → 좌표 `[x, y]` 또는 작도 도우미 (아래) |
| `items` | 그릴 것 (아래) |
| `asserts` | `[["식", "기대값"]]` — 그림이 문제 조건과 맞는지 확인. `dist(A,B)` · `angle(A,B,C)`(도, B 가 꼭짓점) · `A.x` · `A.y` |

값은 숫자 또는 sympy 식 글자(`"sqrt(3)"`, `"9/2"`, `"pi/3"`). 함수식은 파이썬 꼴 `"x**2-2*x-3"`.

**작도 도우미** (점을 다른 점에서 계산)

| 키 | 뜻 |
|---|---|
| `{"polar": [중심, r, 도]}` · `{"on_circle": …}` | 중심에서 거리 r, 각 도 위치 |
| `{"foot": [P, A, B]}` | P 에서 직선 AB 에 내린 수선의 발 |
| `{"mid": [A, B]}` | 중점 |
| `{"divide": [A, B, m, n]}` | AB 를 m:n 으로 내분 |
| `{"rotate": [A, C, 도]}` | C 를 중심으로 A 를 돌린 점 (반시계 +) |
| `{"on_func": [f, x]}` | 그래프 y=f(x) 위 x 인 점 |
| `{"intersect": [대상1, 대상2], "pick": …}` | 교점. 대상 `{"func": f}` · `{"line": [A, B]}` · `{"circle": [중심, r 또는 점 이름]}` · `{"hline": y}` · `{"vline": x}`. `pick` 은 번호(왼쪽부터 0) 또는 `left` · `right` · `upper` · `lower` |
| `{"tangent": [중심, r, P], "pick": …}` | 원 밖의 점 P 에서 그은 접선의 접점 |

**items** — 모든 선 항목에 `style`(`solid` · `dashed` · `dotted`) · `width` · `label` · `pos`(이름표 방향 `n` `ne` `e` … 기본 auto)

| type | 키 |
|---|---|
| `func` | `f` · `domain`(기본 x 범위) · `label` · `label_at`(이름표를 붙일 x) — 범위 밖으로 나간 부분은 잘라 그린다 |
| `point` | `at`(이름 또는 이름 목록) · `dot`(`filled` · `open` · `none`) · `label`(false 면 이름 안 씀) |
| `segment` · `vector` · `polyline` | `from` · `to` 또는 `pts` · `arrow` |
| `polygon` | `pts` · `fill`(`hatch` · `gray`) |
| `line` · `ray` | `x`(수직선) · `y`(수평선) · `through` + `slope` · `pts` |
| `circle` | `center` · `r` 또는 `through`(점 이름) — 그림 범위 안에 다 들어와야 한다 |
| `arc` | `center` · `r` 또는 `through` · `from` · `to`(도) |
| `angle` | `at`(꼭짓점) · `from` · `to` · `deg`(표시할 각 — 실제와 다르면 멈춘다) · `r`(기본 3.2mm) · `arcs`(호 개수) · `label` |
| `right` | 직각 표시 — `at` · `from` · `to` · `size`(기본 2.0mm). 실제로 직각이 아니면 멈춘다 |
| `equal` | 같은 길이 표시 — `segs`(`[[A,B],[C,D]]`) · `ticks`(눈금 수). 길이가 다르면 멈춘다 |
| `label` | 글자만 — `text` · `at`(점) 또는 `mid`(`[A, B]` 변 가운데) · `pos` |
| `shade` | 색칠 — `pts`(다각형) 또는 `between`(`[f, g]`) + `domain` · `fill` |
| `guides` | 점에서 축까지 점선 — `at` · `to`(`x` · `y` · `both`) |

이름표 글자: 소문자는 기울임(변수), 대문자는 바로 선 글자(점 이름). `^` · `_` 는 위 · 아래 첨자(`y=x^2`, `a_1`).

### 수직선

```json
{"kind": "numberline", "range": [-3, 7], "w": 52, "ticks": [-1, 5],
 "marks": [{"at": -1, "closed": true}, {"at": 5, "closed": false}],
 "spans": [{"from": -1, "to": 5, "level": 1}, {"from": 5, "to": "inf", "level": 2}]}
```
`marks` 는 ●(closed) · ○, `spans` 는 범위 화살표(`-inf` · `inf` 가능, `level` 로 높이를 나눈다).

### 직접 SVG

`{"svg": "<svg …>…</svg>"}` — 위 형식으로 못 그리는 그림만. 좌표 점검을 못 하므로 빌드가 알림을 띄운다. 반드시 눈으로 본다.

### 그림이 멈추는 경우

점 · 곡선이 범위 밖 · 한 단 폭 초과 · 원인데 `equal` 이 false · 각 · 직각 · 같은 길이 표시가 실제와 다름 · `asserts` 불일치 · 교점 없음 · pick 범위 밖. 이름표가 선에 닿으면 알림(멈추지는 않는다 — `pos` 로 옮긴다).

## 점검 (걸리면 PDF 를 내지 않는다)

- 데이터: 제어문자(역슬래시 한 번), 필수 키, 진도 밖 단원(`covered`), `range_block` 낱말
- 수식: KaTeX 오류(문법 · 모르는 명령) · `$` 짝
- 그림: 위 「그림이 멈추는 경우」
- 검산: `verify` 불일치 · 선택형 정답 둘 · 값이 같은 선택지
- 규격(`math_exam`): 총점 · 선택형/서답형 문항 수와 배점 합 · 문항별 배점표(`blueprint`) · 선택형 앞 서답형 뒤 · 번호 연속 · 서술형 채점 단계 합 · 정답 분포(같은 번호 `answer_same_max` · 세 번 연속 `no_triple`)
- 조판: 수식 · 그림이 단 밖으로 넘침
- PDF 실물: 빈 쪽 · 쪽번호 · 학생용에 정답 · 해설 노출(`student_absent`) · 강사용 멘트 · 수식 잔재(`$`, `\frac` 이 글자로 남음)

이 점검은 **문제가 맞게 풀리는지**까지는 보지 않는다(검산은 출제자가 쓴 식이 맞다는 전제). 빌드가 통과하면 `자체점검` 스킬 「수학 시험지」대로 `검증` 에이전트에게 학생용 PDF 만 주고 전 문항을 다시 풀게 한 뒤 답을 맞춘다.
```
py 공용/build/수학/답대조.py <data.json> <풀이답.json>      ← {"1": "③", "서답형 1": "9/8"} · 같은 값의 다른 꼴은 일치
```

## 학교 규격 math_exam

`공용/build/학교/_예시.json` 을 본다. 키: `total` · `choice` `{count, total}` · `written` `{count, total}` (count 는 `[최소, 최대]` 도 된다) · `points.blueprint`(문항별 배점, 선택형 → 서답형 순) · `answer_same_max` · `no_triple` · `written_label` · `pt_format` · `essay_space_mm` · `student_absent` · `student_forbidden` · `answer_suffix` · `answer_title_suffix` · `근거`(어느 기출에서 정했는지).

## 온라인 채점

`py 공용/온라인채점/채점키.py <data.json> --id <시험ID>` 가 `subject: "math"` 를 알아본다 (`온라인배포` 스킬). 답지 PDF 가 같은 반 `배부/` 에 있어야 대조한다.
- 휴대폰 화면에는 수식 · 그림이 나오지 않는다. 학생은 종이 시험지를 보고 답만 입력한다
- 선택형 · 숫자 단답형은 자동 채점. 같은 값의 다른 꼴(`9/8` · `1.125` · `8분의 9`)도 맞게 친다
- 숫자가 아닌 단답(식 · 좌표 · 근호)은 `accept` 를 적어야 자동 채점, 없으면 입력만
- 서술형은 입력만 — `steps` · `criteria` 가 「서술형 채점」 탭의 채점 기준으로 간다
