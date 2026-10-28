# -*- coding: utf-8 -*-
"""독립 재풀이 답 대조 — 검증 에이전트가 학생용 시험지만 보고 푼 답을 data.json 의 정답과 맞춘다.

사용: py 공용/build/수학/답대조.py <data.json> <풀이답.json>

풀이답.json — 시험지에 인쇄된 문항 이름을 키로, 답을 글자로 (자체점검 스킬 「수학 시험지」)
    {"1": "③", "2": "1", "서답형 1": "9/8", "서답형 2": "(9/2, 0)"}
- 선택형: ①~⑤ 또는 1~5
- 서답형: 9/8 · 1.125 · 5√2 · 2√(7) · x² · π · (9/2, 0) 처럼 써도 된다. 값이 같으면 일치
같은 값인지는 sympy 로 본다 (verify.same). 불일치 · 빠진 문항 · 읽지 못한 답이 하나라도 있으면 1 로 끝난다.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify as V  # noqa: E402

CIRC = "①②③④⑤"


def school_label(d):
    p = HERE.parent / "학교" / ("%s.json" % d.get("school", ""))
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("math_exam", {}).get("written_label", "서답형")
    except Exception:
        return "서답형"


def key_of(s):
    return re.sub(r"[\s.번]", "", str(s))


def read_value(s):
    """사람이 쓴 답 글자 → sympy 값."""
    s = str(s).strip().strip("$").strip()
    if "\\" in s:
        return V.tex_value(s)
    s = re.sub(r"^[A-Z]\s*(?=\()", "", s)          # P(9/2, 0) → (9/2, 0)
    s = re.sub(r"^[a-zA-Z]\s*=\s*", "", s)          # x = 3 → 3
    s = s.replace("×", "*").replace("·", "*").replace("π", "pi").replace("−", "-")
    s = re.sub(r"√\(", "sqrt(", s)
    s = re.sub(r"√([0-9a-zA-Z.]+)", r"sqrt(\1)", s)
    s = s.replace("²", "**2").replace("³", "**3")
    ns = dict(V.NS)
    ns["i"] = V.sp.I
    return V.parse_expr(s, local_dict=ns, transformations=V.TRANS)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    d = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    got = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
    got = {key_of(k): v for k, v in got.items() if not str(k).startswith("_")}
    wl = school_label(d)
    bad = 0
    for q in d["questions"]:
        if q["kind"] == "choice":
            lab = str(q["n"])
            want = q["ans"] + 1
        else:
            lab = "%s %d" % (wl, q["n"])
        g = got.get(key_of(lab))
        if g is None or str(g).strip() == "":
            print("[빠짐] %s 풀이 답이 없다" % lab)
            bad += 1
            continue
        if q["kind"] == "choice":
            t = str(g).strip()
            n = CIRC.index(t[0]) + 1 if t and t[0] in CIRC else (int(t) if t.isdigit() else None)
            if n == want:
                print("[일치] %s %s" % (lab, CIRC[want - 1]))
            else:
                print("[불일치] %s 정답 %s · 재풀이 %s" % (lab, CIRC[want - 1], t))
                bad += 1
            continue
        try:
            w = V.py_value(q["value"]) if q.get("value") is not None else V.tex_value(q["answer"])
        except Exception as ex:
            print("[확인] %s 모범답안 값을 읽지 못했다 (%s) — 눈으로 맞춘다: 정답 %s · 재풀이 %s" % (lab, ex, q.get("answer"), g))
            bad += 1
            continue
        try:
            v = read_value(g)
        except Exception as ex:
            print("[확인] %s 재풀이 답 '%s' 를 읽지 못했다 (%s) — 눈으로 맞춘다" % (lab, g, ex))
            bad += 1
            continue
        if V.same(w, v):
            print("[일치] %s %s" % (lab, g))
        else:
            print("[불일치] %s 정답 %s · 재풀이 %s" % (lab, w, g))
            bad += 1
    extra = set(got) - {key_of(q["n"]) if q["kind"] == "choice" else key_of("%s %d" % (wl, q["n"])) for q in d["questions"]}
    for k in sorted(extra):
        print("[확인] 시험지에 없는 문항 이름 '%s'" % k)
        bad += 1
    print("결과: %s" % ("전 문항 일치" if not bad else "%d건 확인 필요" % bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
