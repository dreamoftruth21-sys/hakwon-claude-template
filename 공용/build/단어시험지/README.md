# 단어시험지 빌더

시험지 + 정답지(같은 배치, 답만 빨간색). DOCX → LibreOffice → PDF. **새 시험은 data.json 하나만 만든다.**

```
node 공용/build/단어시험지/build.js <data.json> [--out 폴더]
```
- 점검(데이터 → PDF 실물)에 하나라도 걸리면 **PDF를 내보내지 않는다**
- 학교 규격: `공용/build/학교/<school>.json` 의 `vocab_test` — 총 문항 수 · 내지 않는 파트 유형
- 규칙(학교·반·번호 칸 금지, 영어 제시 → 우리말, 범위 이탈 금지 …)은 `.claude/skills/단어시험지/SKILL.md`

예시 (`예시/`):
| 파일 | 파트 | 확인 |
|---|---|---|
| `한솔고2_10강_B형.json` | 뜻쓰기 · 문장 5지선다 · 있는 대로 · 다의어 | 옛 스크립트를 이 PC에서 돌린 PDF와 쪽별 텍스트 동일 |
| `세종예고2_1과.json` | 뜻쓰기 · 유의어 보기 · 반의어 5지선다 · 문맥 O·X | 〃 |
| `세종예고1_2과.json` | 뜻쓰기 · 문장 빈칸 | 〃 |

> **이 PC에서는 맑은 고딕이 Cowork 때 글꼴보다 넓다.** 옛 판형 여백 그대로면 쪽이 늘어난다(한솔고2 4→7쪽). 예시 파일의 `m`·`gap` 은 이 PC에서 옛 쪽수에 맞춘 값이다. 새 시험도 `max_pages` 를 주면 넘칠 때 멈춘다.

## data.json

```json
{
 "school": "한솔고",
 "name": "HS2_L11_TEST",            // 파일 이름
 "answer_suffix": "_답지",           // 기본 _답지
 "accent": "1F4E79",                 // 고등 남색 / 중3 주황 C55A11
 "cell_style": "a",                  // a: 칸 위·아래 여백 = m / b: 위 = m, 아래 = mb(기본 40) — 세종예고1 판형
 "head1": "고2 영어 · 수능특강 Light 11강 · 본문분석 「핵심 단어」 · 지문 1번 ~ 5~7번",   // 출제 범위를 반드시 적는다
 "head2": "2026.09.16  한솔고 2학년 단어시험  [ 11강 ]",
 "total": 60,                        // 선택. 합계 확인
 "max_pages": 4,                     // 선택. 넘으면 중단
 "lexicon": {"ultimate": {"m": "궁극적인", "syn": ["final"], "ant": []}},   // 선택. 유의어·반의어 정답을 교재 단어장과 대조
 "parts": [ {"letter": "A", "type": "meaning", "title": "다음 단어의 우리말 뜻을 쓰시오.", "sub": "", "page_break_after": true, … } ]
}
```
파트 제목 뒤 `[1~30]` 번호 범위는 자동으로 붙는다.

## 파트 유형

| type | 문항 | 필드 | 자동 점검 |
|---|---|---|---|
| `meaning` 뜻쓰기 (영어 → 우리말) | 2단 표 | `items[{w, m, tag?}]` · `order`(섞은 순서) · `widths` · `m` | 중복 · 뜻 누락 · 뜻 완전 동일 · order 순열 · 교재 순서 3연속 |
| `choice5_sentence` 문장 속 밑줄 유의어/반의어 5지선다 | | `items[{type, pre, word, post, options, answer, lemma?}]` · `gap` | 선택지 5개·중복 · 연속 패턴 · 유의어→반의어 순 · 정답 번호 고르게 · 단어장 대조(참고) |
| `select_all` 있는 대로 고르기 (6개) | | `items[{word, m, type, options, answers}]` · `gap` | 단어장 유의어/반의어와 정답·누락 대조 · 정답 조합 반복 |
| `polysemy` 다의어 | 번호 상자 | `box["① 뜻", …]` · `box_per_line` · `items[{pre, word, post, answer, lemma?}]` · `m` | 정답 중복 · 상자 순서대로 나열 · 연속 번호 · 같은 단어 연달아 |
| `syn_pick` 유의어 보기에서 골라 쓰기 | 〈보기〉 | `box` · `items[{word, m, answer}]` | 정답 ∈ 보기 · 정답 중복 · 오답 보기가 유의어인지 |
| `ant_choice5` 반의어 5지선다 | | `items[{word, m, options, answer}]` · `gap` | 단어장 반의어 · 복수정답 · 같은 번호 3연속 · 순서 나열 · 쏠림 |
| `context_ox` 문맥 O·X + 고쳐 쓰기 | 〈보기〉 | `box` · `items[{pre, word, post, ok, fix}]` · `m` | 판정 쏠림 · 고칠 말 ∈ 보기 · 반의어 관계 · OXOX 교대 |
| `fill_blank` 문장 빈칸 (알맞은 형태) | 〈보기〉 | `box` · `items[{pre, post, form, base}]` · `m` | 정답 ∈ 보기 · 마침표 · 변형형 일치 · 보기 > 정답 |
| `definition` 영영풀이 → 단어 | 〈보기〉 | `box` · `items[{w, def}]` · `m` | 정답 ∈ 보기 · 풀이에 정답 단어 노출 · 보기 > 정답 |
| `word_write` 제시어 보고 쓰기 (접두사·접미사·in-/im-) | 〈보기〉 선택 | `items[{prompt, answer, hint?}]` · `box?` | 정답 중복 |

공통 점검: 학교가 내지 않는 유형 · 총 문항 규격 · **파트 간 표제어·보기 중복**(서로 힌트) · 머리말·제목의 강사용 멘트·"자리"·학교/반/번호 칸 · PDF 실물(이름·점수 칸, 문항 번호 전부, 시험지 = 정답지 쪽 수, 최대 쪽수)

## 나성중3 판형 — `"layout": "나성중"`

`reference/ns6/build_def.js` 판형: 글자 18 · 칸 위 정렬 · 칸 여백 58 · 주황 보기 상자(머리 없음) · 제목 한 줄 29 · 쪽 여백 800/650.
`meaning`(two) · `definition`(defList) · `fill_blank`(fillIn) · `polysemy`(multi) 가 이 판형으로 그려진다.
- 같은 보기를 여러 번 쓰는 빈칸(worth / value / valuable)은 `fill_blank` 에 `"reuse_box": true`
- 예시: `예시/나성중3_L6_영영풀이다의어.json` — 옛 스크립트를 이 PC에서 돌린 PDF와 동일 확인 후 2쪽에 맞게 여백 조정

## A/B형 대조 — `"compare_with"`

B형 data.json 에 A형 파일 경로(이 파일 기준 상대경로)를 주면, **같은 파트 같은 자리에 같은 문항**이 오면 막는다. 겹치는 문항 수는 참고로 알려준다.
```json
{"name": "SJ2_L1_TEST_B", "compare_with": "../SJ2_L1_TEST/data.json", …}
```

## 아직 없는 것
- `word_write`(접두사·접미사 쓰기)는 나성중3 판형이 없다 — 세종예고1 판형으로만 그린다.
