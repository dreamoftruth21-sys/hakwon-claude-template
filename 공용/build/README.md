# 공용 빌더

**새 자료는 스크립트를 새로 짜지 않고 data.json 하나만 만든다.** 점검에 하나라도 걸리면 PDF를 내보내지 않는다.
아래 명령은 학원 폴더 기준이다 — 반 폴더에서 실행하면 `../공용/build/…`. data.json 안의 원본 경로(`source`·`pdf` 등)는 어디서 실행하든 학원 폴더 기준으로 쓴다.

| 자료 | 실행 | 설명 |
|---|---|---|
| 실전 모의고사 (5지선다 학교 규격) | `py 공용/build/모의고사/build.py <data.json> [--out 폴더]` | `모의고사/README.md` |
| 단어장 | `py 공용/build/단어장/build.py <data.json> [--out 폴더]` | `단어장/README.md` |
| 학평 변형문제집 재조판 | `py 공용/build/변형문제/재조판.py <data.json> [--out 폴더]` | `변형문제/README.md` |
| 내신기출·변형문제 지문 지우기(✕)·뽑기 | `py 공용/build/변형문제/기출가공.py <data.json> [--out 폴더]` | `변형문제/README.md` |
| 단어 시험지 | `node 공용/build/단어시험지/build.js <data.json> [--out 폴더]` | `단어시험지/README.md` |
| 어법 핵심 정리 (범위 원문 예문만, 2쪽) | `py 공용/build/어법핵심/build.py <data.json> [--out 폴더]` | `어법핵심/README.md` |
| 교재 PDF에서 수업·숙제·답지 쪽 뽑기 (인쇄 쪽 번호로) | `py 공용/build/쪽뽑기/extract.py <교재키> <쪽> <저장경로>` · `<jobs.json>` · `--list` | `쪽뽑기/README.md` |
| 수업 계획표 (진도를 한눈에, A4 가로 1쪽) | `py 공용/build/수업계획/build.py <계획.json> [--today 날짜] [--out 폴더]` | `수업계획/README.md` · `수업계획` 스킬 |
| 시험대비 교재 (표지 · 차례 · 속표지 · 원본 쪽 · 직접 출제 · 정답과 해설을 푸는 순서로 한 권) | `py 공용/build/교재/build.py <교재.json> [--skip-prep]` | `교재/README.md` · `교재만들기` 스킬 |
| 학생별 약점 보완 자료 · 약점 확인 시험 | `py 공용/build/약점보완/build.py <작업폴더> 이름…` · `py 공용/build/약점보완/확인시험.py <작업폴더>` | `약점보완/README.md` · `약점보완` 스킬 |
| 시험 결과 피드백 (학부모용 한 쪽 · 학생용 오답 해설) | `py 공용/build/피드백/부모용.py <content.json>` · `py 공용/build/피드백/학생용.py <학생.json>` | `피드백/README.md` · `내신피드백` 스킬 |

- `학교/<학교>.json` — 학교 규격 (`exam` 모의고사 · `wordlist` 단어장 · `vocab_test` 단어시험지). 처음에는 `_예시.json` 뿐이다 — 반을 만들 때 `시험지분석` 스킬이 그 학교 기출로 `<학교>.json` 을 쓴다
- `core/` — 공통 모듈: `text`(정규화·선택지 회전) · `checks`(결함 모음·멘트·"자리"·정답 분포·3-gram·PDF 실물) · `render`(HTML→PDF, 점검 통과 후에만 저장) · `sources`(학평 원문·PDF·원본 텍스트)
- 학평 원문: `공용/교재/모의고사/_데이터/고1_bynum.json` · `고2_bynum.json` — 한 벌뿐이다 (반 폴더 사본은 2026-09-18 정리)
- 각 빌더 `예시/` 의 data.json 은 옛 스크립트 산출물과 쪽별 텍스트가 같은 것을 확인한 것이다 (2026-09-18)

## 빌더에 없는 형식이면
1. 반 `작업/` 에서 새로 짜되 `core/` 를 가져다 쓴다 (`sys.path.insert(0, "공용/build")` → `from core import checks`)
2. 같은 형식을 **두 번째로** 만들게 되면 공용 빌더로 올린다

## 옛 것
- `bld.py` — 옛 판형 모듈. 한솔고2·나성중3 스크립트 8개가 쓴다. **손대지 않는다** (Cowork 크로미움 경로가 박혀 이 PC에서는 그대로 안 돈다)
- `빌드스크립트_README.md` — Cowork 시절 스크립트 목록
- `공용화계획.md` · `_계획/01_조사.md` — 이 빌더들을 만든 계획과 조사
