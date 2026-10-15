# 실전 모의고사 빌더

학교 규격 5지선다 시험지 + 정답해설 PDF. **새 회차는 data.json 하나만 만든다.**

```
py 공용/build/모의고사/build.py <data.json> [--out 폴더] [--html]
```
- `--out` 이 없으면 data.json 이 있는 폴더에 PDF 2개
- 점검(데이터 → 원문 대조·누출 → PDF 실물) 중 하나라도 걸리면 **PDF를 내보내지 않는다**
- 학교 규격은 `공용/build/학교/<school>.json` 의 `exam` (문항 수·배점·정답 분포·금지 유형·답지 형식)

예시 (옛 회차를 옮긴 것, 옛 PDF와 쪽별 텍스트 동일 확인 2026-09-18):
`예시/세종예고2_실전모의고사_2회.json` · `예시/나성중3_실전모의고사_3회.json`
옛 py 데이터를 옮길 때: `옛py변환.py`

## data.json

```json
{
 "school": "세종예고",                         // 학교/세종예고.json
 "name": "세종예고2_영어II_1과+9월학평_실전모의고사_3회",   // PDF 파일 이름
 "title": "2026학년도 2학기 중간고사 대비 <b>실전 모의고사 3회</b>",
 "subtitle": "세종예술고등학교 2학년 영어Ⅱ &nbsp;·&nbsp; Lesson 1 + 9월 학력평가",
 "guide": "시험지 머리 안내 상자 (HTML)",
 "footer": "세종예고 2학년 · 영어Ⅱ 실전 모의고사 3회",
 "target": [2,3,0,4,1, …],     // 문항별 정답 위치(0~4). 고정 문항은 원래 정답과 같아야 한다
 "sol_numbers": "forbid",      // 선택지를 돌리는 문항 해설의 ①~⑤: forbid(금지) / remap(자동 재매핑). 생략하면 학교 설정

 "passages": {
  "G23": {
   "header": "[2~3] 다음 글을 읽고 물음에 답하시오.",
   "range": [2, 3],            // 이 지문을 쓰는 문항 번호 (선택)
   "body": "… {{빈칸}} …",      // {{빈칸}} 은 빈칸 밑줄로 바뀐다
   "kind": "orig",             // orig 원문 그대로 / edit 출제용 수정 / rewrite 재작성(원문 대조 제외)
   "src": "L1",                // sources 의 키
   "restore": [["바꾼 표현", "원문 표현"]],   // edit: 대조 전에 원문으로 되돌린다
   "free": ["새로 쓴 빈칸 문장"],             // edit: 대조에서 뺀다. "(A)"·"①" 처럼 정리하면 빈 글자가 되는 항목은 결함 — 대조가 통째로 꺼진다 (2026-09-30)
                                              // 순서 문항 문단 기호 (A)(B)(C) 는 빌더가 문단 경계로 알아서 끊는다 — free 에 넣지 않는다
   "guard": ["원래 표현"]                     // 시험지 어디에도 보이면 안 되는 원문 표현
  }
 },

 "questions": [
  {"n": 1, "pt": 3.4, "passage": "G23", "box": null, "box_ref": null,
   "stem": "발문", "show": "list", "fixed": false,
   "opts": ["…","…","…","…","…"], "ans": 0, "sol": "해설"}
 ],
 // passage: 묶음 지문 키 · box: <보기> 상자 글 · box_ref: 단독 지문 키를 상자로
 // show: list(세로) / row(한 줄) / none(지문 속 ①~⑤, opts 없이 fixed)

 "sources": {                  // 원문 대조 (선택)
  "L1": [{"pdf": "세종예고2/학교자료/…/1과_본문.pdf", "until": "Read More"}],
  "M":  [{"pdf": "공용/교재/모의고사/2026_고2_9월/…문제지.pdf", "replace": [["places which", "places where"]]},
         {"bynum": "고2", "round": "2025-9", "nums": ["32", "34"]}]
 },
 "range_block": ["PCT", "Pacific Crest"],   // 지문·보기·학생용 PDF에 나오면 안 되는 범위 밖 소재

 "checks": [ … ]               // 회차마다 심은 장치가 실제로 들어갔는지 (아래)
}
```

## checks 종류

| type | 필드 | 뜻 |
|---|---|---|
| `contains` / `absent` | `in`, `texts`, `plain`, `ci` | 대상에 글이 있어야/없어야 한다. `plain` 은 태그 걷고 비교, `ci` 는 대소문자 무시 |
| `count` | `in`, `token` 또는 `regex`, `expect`, `minus_blanks` | 개수 |
| `blank_once` | `passages` | 지문마다 빈칸 정확히 1개 |
| `answer_is` / `answer_contains` | `q`, `text` | 회전 후 정답 선택지 글 |
| `options_subset` | `q`, `of` | 선택지가 모두 목록 안에 |
| `underlines_match_options` | `q`, `passage` | 지문 밑줄 ①~⑤ = 선택지 |
| `box_not_in_passage` | `q`, `passage` | <보기> 문장이 지문에 이미 있으면 안 된다 (문장 삽입) |

`in` 대상: `passage:<키>` · `box:<번호>` · `stem:<번호>` · `options:<번호>` · `answer:<번호>` · `sol:<번호>` · `all`
모든 check 에 `why` 를 달 수 있다 — 결함 메시지에 붙는다.

## 자동으로 하는 점검

- 규격: 문항 수 · 번호 연속 · 총점 · 배점표/배점 구성 · 선택지 5개·중복 · 해설 · 지문 키 · 묶음 번호 범위
- 정답 분포: 한 번호 최대 · 최다·최소 차 · 3연속
- 학교 비출제 유형 표현(발문) · 범위 밖 소재
- 원문 대조(orig/edit, 15자 이상 문장) · 정답 누출 · 원래 표현(guard) 누출 · 회전 문항 해설 번호
- 학생용 PDF: 정답·해설 노출 · 배점 표시 · 문항 번호 · 강사용 멘트 · "자리"(문법 용어 예외) · 태그 잔재 · 빈 쪽 · 쪽번호
- 답지 PDF: 문항별 "n. 정답 ⑤" 표기

## 단답형 · 서술형 (양지고 · 한솔고)

문항에 `"kind"` 를 준다. 선택형(`choice`, 기본)을 모두 앞에, 서답형을 뒤에 둔다. 서답형 번호는 따로 1부터.

```json
{"kind": "short", "n": 1, "pt": 6.0, "box_ref": "P32",
 "stem": "윗글에서 빈칸에 들어갈 두 단어를 찾아 쓰시오.",
 "answer": "financial incentives", "from_passage": true, "lines": 1,
 "sol": "해설", "criteria": "철자 오류 0점"}

{"kind": "essay", "n": 3, "pt": 5.0, "passage": "G34",
 "stem": "밑줄의 의미를 영어 1문장으로 쓰시오.",
 "conditions": ["연속 3단어 이상 본문 인용 금지", "지정 표현을 모두 사용할 것"],
 "answer": "모범답안", "no_quote_3gram": true, "must_use": ["rely on", "achieve"], "lines": 3,
 "sol": "해설", "criteria": "완전한 문장 2점 · 내용 3점"}
```

| 필드 | 뜻 | 자동 점검 |
|---|---|---|
| `answer` | 모범답안 (답지에만) | 비었는지 · 학생용 PDF에 보이는지 |
| `from_passage` | 글에서 찾아 쓰기 | 모범답안 낱말이 지문에 있는지 (어형 변화 허용) |
| `no_quote_3gram` | 연속 3단어 인용 금지 | 모범답안 ↔ 지문 3-gram |
| `must_use` | 지정 표현 모두 사용 | 모범답안에 전부 있는지 |
| `conditions` | 〈조건〉 상자에 인쇄 | |
| `lines` | 답 쓸 줄 수 (단답 1 · 서술 3 기본) | |
| `criteria` | 채점기준 (답지에만) | |
| `form` | 답란 모양: `line`(기본) · `paren` `답: (   )` · `table` 칸별 배점 표 · `cells` `답: 이름표 ___` · `fill` 틀 문장 채우기 | 칸별 배점 합 = 문항 배점 (table) |
| `form_cols` | table: `[["기호",1.5],["바르게 고친 표현",2.5]]` · cells: `["pushed:","pulled:"]` | |
| `form_text` | fill: `"This is {{칸}} because {{칸}}."` | `{{칸}}` 있는지 |

선택형에도 쓸 수 있는 것: `opt_head`(짝 선택지 머리 `[a] … [b]`) · `arrow`(box_ref 지문 상자와 box 요약문 사이 ↓).
`show` 에 `cols2`(선택지 2열) · `grid32`(3+2 격자)도 쓴다. 여러 칸 서답형은 `sub_pts`(칸별 배점 목록)를 주면 발문 끝이 `[총6점]`, cells 답란 칸마다 `[2점]`이 붙는다.
`stem_after` 는 배점 뒤에 붙는 말(`[4점] (각 1점씩)`).

학교 설정 `exam.choice` · `exam.written` 이 문항 수·배점 합·서답 형식을 막는다.
- 양지고: 선택형 22문항 80점 + **단답형** 4문항 20점 (단답형만). 기출 명세(`양지고2/분석/기출_문항명세_2026-1학기.md`)에서 옮긴 규칙
  (2026-09-30): 번호 `[단답형 1]` · 여러 칸 문항은 `sub_pts` 필수(`multi_part_sub_pts`) · 〈조건〉 점 없이 1. 2. ·
  '않은·틀린·없는' 밑줄(`neg_underline`) · 순서형 2열(`stem_show`) · 기호 조합형 3+2 격자(`combo_show`).
  이 규칙 전에 만든 실모 1~5회는 다시 뽑으면 걸린다 — 그 판 그대로 다시 뽑을 때는 data.json `profile_override`
- 한솔고: 선택형 14~15문항 50점 + 단답형 7~8문항 30점(`written.by_kind`) + 서술형 4문항 20점.
  `interleave` — 서답형이 자기 지문 묶음 【7, 서답형4】 안에 섞인다(선택형·서답형 순서 점검을 끈다).
  번호 `서답형3 (단답형)`(`written_label_fmt`). 어법·어휘는 선택형 금지(`choice_stem_forbidden`),
  어법 답란은 표(`stem_form`), ⓐ~ 밑줄은 2단어까지(`mark_max_words`). 순서배열·문장삽입 발문 금지.
  서답형 발문·조건의 금지어(`written_forbidden` — 「3단어」 인용 금지 조건, 3회부터 뺌).
  학교 규격을 바꾸기 전에 배부한 회차는 data.json `profile_override`(why 필수)로 그 판 형식대로 다시 뽑는다.
  근거 `한솔고2/분석/출제경향.md` 10장
- 나성중·세종예고: 서답형 없음 — 넣으면 막힌다

한솔고는 실전 모의고사 2회(2026-09-23)에서 실제 렌더를 눈으로 확인했다. 양지고는 아직 합성 데이터로만 확인했다.
