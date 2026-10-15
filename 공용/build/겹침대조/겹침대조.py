# -*- coding: utf-8 -*-
"""모의고사 문항이 학생이 이미 푼 문항과 같은 곳을 묻는지 **참고로** 보여 준다.

    py 공용/build/겹침대조/겹침대조.py <모의고사 data.json>

**막지 않는다.** 같은 지문을 다시 쓰는 것은 당연하고, 같은 곳을 다시 묻는 것도 금지가 아니다
(복습용으로 일부러 다시 물을 수 있다). 겹친 곳을 보여 주고, 의도한 것인지 만드는 쪽이 판단한다.
처음 만든 곳: 한솔고2 2학기 중간 실모 2~5회 (2026-09-23) → 공용으로 옮김 (2026-09-30)

무엇과 대조하나 — data.json 이 있는 `작업/` 폴더 전체를 훑는다
  - 다른 회차 모의고사: 작업/ 아래 `questions` 가 있는 json (공용 모의고사 빌더 형식)의 선택지 · <보기> · 모범답안
  - 워크북 · 변형문제 등: 작업/ 아래 .py · .json 의 영어 문자열 가운데 문항 요소로 보이는 것
      7~34단어 문자열만 본다. 35단어 이상은 지문으로 보고 "지문 말뭉치"에 넣는다.
      지문 말뭉치와 5단어 연쇄가 절반 넘게 겹치는 문자열(지문을 그대로 옮긴 것)은 뺀다
  - 제외: 대상 data.json 과 같은 폴더(그 회차 자신) · 이름이 _ 로 시작하는 폴더(이전판 · 렌더) · __pycache__
대조하는 쪽: 대상 시험지의 선택지 · <보기> 줄 · 모범답안 (지문은 보지 않는다)
기준: 4단어 연쇄가 45% 이상 겹치면 적는다
"""
import json, pathlib, re, sys

TAG = re.compile(r"<[^>]+>")
STR = re.compile(r'"([^"\n]{40,})"|\'([^\'\n]{40,})\'')      # 한 줄 안에 닫히는 문자열
HIT = 0.45


def plain(s):
    s = TAG.sub(" ", str(s))
    for a, b in (("&nbsp;", " "), ("&mdash;", "-"), ("&lsquo;", "'"), ("&rsquo;", "'"), ("&ldquo;", '"'),
                 ("&rdquo;", '"'), ("&amp;", "&"), ("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("—", "-")):
        s = s.replace(a, b)
    return " ".join(s.split())


def words(s):
    return re.findall(r"[a-z']+", plain(s).lower())


def grams(s, n):
    w = words(s)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def is_exam(obj):
    return isinstance(obj, dict) and isinstance(obj.get("questions"), list)


def exam_items(d, src):
    for q in d["questions"]:
        for o in (q.get("opts") or []):
            yield src, o
        for key in ("box", "answer"):
            if q.get(key):
                yield src, q[key]


# 지문 원문을 담는 파일 — 문장 단위로 쪼개 둔 것도 있어서(양지고 body.json) 길이와 상관없이 전부 지문으로 본다
SOURCE_NAME = re.compile(r"^(body|src|light|ext|all|raw|text)$|원문|본문")


def scan(work, target):
    """작업/ 폴더를 훑어 (이미 나간 문항 요소 목록, 훑은 파일 수)를 만든다.
    대상 시험지 자신과, 대상과 같은 폴더의 시험지가 아닌 파일(그 회차의 mk.py · src.json)은 뺀다.
    한 폴더에 여러 회차가 있으면(양지고 1회.json … 5회.json) 다른 회차는 대조에 넣는다."""
    exams, texts, corpus = [], [], []
    files = [p for p in work.rglob("*") if p.suffix in (".py", ".json") and p.is_file()
             and "__pycache__" not in p.parts
             and not any(part.startswith("_") for part in p.relative_to(work).parts[:-1])
             and p != target]
    for p in files:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        rel = p.relative_to(work).as_posix()
        obj = None
        if p.suffix == ".json":
            try:
                obj = json.loads(txt)
            except ValueError:
                obj = None
        if is_exam(obj):
            exams += list(exam_items(obj, rel))
            corpus += [v.get("body", "") for v in (obj.get("passages") or {}).values() if isinstance(v, dict)]
            continue
        if p.parent == target.parent:        # 대상 회차 자신의 빌드 파일
            continue
        src_file = bool(SOURCE_NAME.search(p.stem))
        for m in STR.finditer(txt):
            s = plain(m.group(1) or m.group(2) or "")
            w = words(s)
            if len(re.findall(r"[가-힣]", s)) > len(w):      # 해설·채점기준 등 우리말 덩어리
                continue
            if src_file or len(w) >= 35:
                corpus.append(s)
            elif len(w) >= 7:
                texts.append((rel, s))
    cg = set()
    for c in corpus:
        cg |= grams(c, 5)
    used, seen = [], set()
    for src, s in texts:
        g = grams(s, 5)
        if not g or len(g & cg) / len(g) >= 0.5:            # 지문을 그대로 옮긴 문자열
            continue
        key = " ".join(words(s))
        if key not in seen:
            seen.add(key)
            used.append((src, s))
    used += [(src, s) for src, s in exams if words(s)]
    return used, len(files)


def main(path):
    target = pathlib.Path(path).resolve()
    work = next((p for p in target.parents if p.name == "작업"), None)
    if work is None:
        raise SystemExit("data.json 위에 '작업' 폴더가 없다: %s" % target)
    used, nfiles = scan(work, target)
    index = [(src, s, grams(s, 4)) for src, s in used]
    index = [x for x in index if x[2]]
    d = json.loads(target.read_text(encoding="utf-8"))

    out = []

    def check(item, label):
        g = grams(item, 4)
        if not g:
            return
        best = max(((len(g & ug) / len(g), src, s) for src, s, ug in index), default=(0, "", ""))
        if best[0] >= HIT:
            out.append("%s — %s 와 %.0f%%\n        이번: %s\n        이미: %s"
                       % (label, best[1], best[0] * 100, plain(item)[:90], plain(best[2])[:90]))

    for q in d["questions"]:
        kind = q.get("kind", "choice")
        n = ("%d번" % q["n"]) if kind == "choice" else ("서답형 %d" % q["n"])
        for i, o in enumerate(q.get("opts") or []):
            check(o, "%s 선택지 %d" % (n, i + 1))
        if q.get("box"):
            for line in re.split(r"<br>|[ⓐ-ⓗ]", q["box"]):
                check(line, "%s <보기>" % n)
        if q.get("answer"):
            check(q["answer"], "%s 모범답안" % n)

    print("겹침 대조 (참고) — %s 의 %d개 파일에서 이미 나간 문항 요소 %d개와 대조" % (work, nfiles, len(index)))
    if not out:
        print("겹친 곳 없음")
    else:
        print("겹친 곳 %d곳 — 막지 않는다. 같은 곳을 일부러 다시 물었는지 확인만 한다\n  " % len(out) + "\n  ".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
