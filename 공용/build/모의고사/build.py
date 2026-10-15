# -*- coding: utf-8 -*-
"""실전 모의고사 빌더 — 학교 규격 5지선다 시험지 + 정답해설.

사용: py 공용/build/모의고사/build.py <data.json> [--out 폴더] [--html]
  - 데이터 형식은 같은 폴더 README.md
  - 학교 규격은 공용/build/학교/<school>.json 의 "exam"
  - 점검(데이터 → 원문 대조 → PDF 실물)에 하나라도 걸리면 PDF를 내보내지 않는다
기준 구현: 세종예고2/…/실전모의고사_2회 (mk.py·chk.py), 나성중3 L5-6_모의고사_3회 (선택지 회전·해설 번호 재매핑)
"""
import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import checks as C  # noqa: E402
from core import render as R  # noqa: E402
from core import sources as S  # noqa: E402
from core import text as T  # noqa: E402

BLANK_TOKEN = "{{빈칸}}"
MAX_UL_WORDS = 6          # 어법·어휘 문항의 지문 밑줄 한 곳이 넘으면 안 되는 낱말 수
BL = ("&nbsp;<u>" + "&nbsp;" * 26 + "</u>&nbsp;")
# 순서 문항 문단 기호: 문장 끝(. ! ? 따옴표)·줄바꿈·지문 맨 앞 바로 뒤의 (A)~(E) — check_sources 에서 문단 경계로 끊는다
PARA_MARK = re.compile(r"(^|[.!?\"”’]|<br\s*/?>)\s*(?:<b>)?\s*\([A-E]\)\s*(?:</b>)?")
CIR = T.CIRC_ENT

CSS = r"""
@page{size:A4;margin:13mm 11mm 12mm 11mm}
*{box-sizing:border-box}
body{font-family:"Noto Serif CJK KR","Noto Sans CJK KR",serif;font-size:9.3pt;line-height:1.62;color:#111;margin:0}
.head{border:1.2pt solid #111;padding:2.4mm 3mm;margin:0 0 4mm 0}
.head .t1{font-size:13.5pt;font-weight:700;text-align:center;letter-spacing:-.02em}
.head .t2{font-size:9.4pt;text-align:center;margin-top:1mm;color:#333}
.bar{display:flex;gap:3mm;margin:2.5mm 0 0 0;font-size:9.2pt;border-top:.6pt solid #999;padding-top:2mm}
.bar span{flex:1}
.guide{font-size:8.8pt;color:#333;border:.6pt solid #999;padding:2mm 2.6mm;margin:0 0 4mm 0;background:#fafafa}
.cols{column-count:2;column-gap:7mm;column-rule:.5pt solid #bbb}
.q{break-inside:avoid;page-break-inside:avoid;margin:0 0 3.6mm 0}
.qh{font-size:9.3pt;margin:0 0 1.2mm 0;text-indent:-5.6mm;padding-left:5.6mm}
.qn{font-weight:700}
.pt{font-size:8.4pt;color:#555;white-space:nowrap}
.psgh{font-weight:700;font-size:9.1pt;margin:1.5mm 0 1.2mm 0;break-after:avoid;page-break-after:avoid}
.psg{border:.7pt solid #777;padding:2.4mm 2.8mm;margin:0 0 3mm 0;font-size:9pt;line-height:1.72;
 text-align:justify;break-inside:avoid;page-break-inside:avoid}
.psg u{text-underline-offset:1.6px}
.box{border:.6pt solid #777;padding:2mm 2.4mm;margin:1.4mm 0;font-size:9pt;line-height:1.7;
 break-inside:avoid;page-break-inside:avoid}
.bogi{border:.5pt dashed #888;padding:1.8mm 2.2mm;margin:1.4mm 0;font-size:8.9pt;line-height:1.7}
.op{margin:.5mm 0 0 2mm;font-size:9.1pt;text-indent:-4.4mm;padding-left:4.4mm}
.fn{font-size:8.2pt;color:#444}
.nt{border:.7pt solid #777;padding:2.6mm 3mm;line-height:1.78;margin:0 0 3mm 0;break-inside:avoid;page-break-inside:avoid}
.nt .ntt{font-weight:700;font-size:10pt;text-align:center;border-bottom:.6pt solid #777;
 padding-bottom:1.4mm;margin-bottom:1.8mm}
.foot{margin-top:4mm;border-top:.6pt solid #999;padding-top:1.6mm;font-size:7.8pt;color:#666}
.pb{page-break-before:always}
h2{font-size:11.5pt;background:#111;color:#fff;padding:1.8mm 3mm;margin:0 0 3mm 0;border-radius:0}
table{width:100%;border-collapse:collapse;font-size:9pt;margin:0 0 4mm 0}
th,td{border:.6pt solid #888;padding:1.3mm 1.6mm;text-align:center}
th{background:#eee;font-weight:700}
.lg{font-size:8.6pt;color:#222;margin:0 0 2.2mm 0}
.lg .lgi{display:inline-block;margin-right:6mm}
.lg .p3,.lg .p4,.lg .p5{padding:.3mm 1mm;margin-right:.8mm}
table.ans{table-layout:fixed}
table.ans th,table.ans td{padding:1.4mm .8mm;text-align:center}
table.ans td{font-size:11.5pt;line-height:1.25}
table.ans td.pp{font-size:7.8pt;color:#444;padding:.8mm .4mm}
th.h3{background:#f4f4f4}
th.h4{background:#c9c9c9}
th.h5{background:#111;color:#fff}
td.p3{background:#fff;font-weight:400}
td.p4{background:#d9d9d9;font-weight:700}
td.p5{background:#fff;font-weight:700;box-shadow:inset 0 0 0 1.8pt #111}
.lg .p3{border:.6pt solid #999}
.lg .p4{background:#d9d9d9;font-weight:700;border:.6pt solid #999}
.lg .p5{font-weight:700;border:1.8pt solid #111}
.sol{break-inside:avoid;page-break-inside:avoid;margin:0 0 3mm 0;font-size:9pt;text-indent:-6.5mm;padding-left:6.5mm}
body{font-family:"Noto Serif KR","Batang","Malgun Gothic",serif}
.row{margin:.8mm 0 0 2mm}
.row .op{display:inline-block;margin:0 4.6mm 0 0;text-indent:0;padding-left:0}
.sumh{text-align:center;font-size:8.6pt;font-weight:700;margin:0 0 .6mm 0}
.ansl{margin:.8mm 0 0 2mm;font-size:9.1pt;font-weight:700}
.wl{border-bottom:.6pt solid #999;height:7.2mm;margin:0 0 0 2mm}
.cond{border:.6pt dashed #888;padding:1.4mm 2.2mm;margin:1.2mm 0;font-size:8.8pt}
.mans{border:.8pt solid #c00;color:#b00;padding:1.4mm 2.2mm;margin:1.2mm 0 0 0;font-size:9pt}
.subh{font-weight:700;font-size:9.6pt;margin:1mm 0 2.4mm 0;padding:1mm 0;border-bottom:.8pt solid #111;column-span:all}
.ktag{font-size:8.6pt}
.af{margin:1.4mm 0 0 2mm;font-size:9.2pt;line-height:2}
.af .gap{display:inline-block;width:58mm}
.af .bl{display:inline-block;border-bottom:.6pt solid #333;min-width:26mm;height:5mm;vertical-align:bottom}
table.ft{margin:1.4mm 0 0 0;width:100%}
table.ft th{background:#d9d9d9;font-weight:400;font-size:8.8pt}
table.ft td{height:9mm}
.oh{margin:.8mm 0 0 8.4mm;font-size:9pt;font-weight:700}
.arrow{text-align:center;font-size:11pt;margin:.4mm 0}
.nb{display:inline-block;border:.7pt solid #222;padding:0 1.4mm;line-height:1.25;text-indent:0}
.cols2{display:grid;grid-template-columns:1fr 1fr;column-gap:3mm}
.grid32{display:grid;grid-template-columns:repeat(3,1fr);column-gap:3mm}
"""
KINDS = ("choice", "short", "essay")          # 선택형 · 단답형 · 서술형

REQ_Q = ("n", "pt", "stem", "sol")


def is_choice(q):
    return q.get("kind", "choice") == "choice"


def qkey(q):
    """점검에서 문항을 가리키는 키 — 선택형은 번호(int), 서답형은 's번호'."""
    return q["n"] if is_choice(q) else "s%d" % q["n"]


def qlabel(q, prof):
    if is_choice(q):
        return "%d." % q["n"]
    return prof.get("written_label_fmt", "%s %d.") % (prof.get("written_label", "서답형"), q["n"])


# ── 불러오기 ────────────────────────────────────────────────
def expand(obj):
    """문자열 안의 {{빈칸}} 을 빈칸 HTML로."""
    if isinstance(obj, str):
        return obj.replace(BLANK_TOKEN, BL)
    if isinstance(obj, list):
        return [expand(x) for x in obj]
    if isinstance(obj, dict):
        return {k: expand(v) for k, v in obj.items()}
    return obj


def load(data_path):
    d = json.loads(pathlib.Path(data_path).read_text(encoding="utf-8"))
    for k in ("school", "name", "title", "subtitle", "guide", "footer", "passages", "questions"):
        if k not in d:
            raise SystemExit("data.json 에 '%s' 가 없다" % k)
    for q in d["questions"]:
        miss = [k for k in REQ_Q if k not in q]
        q.setdefault("kind", "choice")
        if q["kind"] not in KINDS:
            raise SystemExit("%s번 문항 kind 는 %s" % (q.get("n", "?"), "/".join(KINDS)))
        if q["kind"] == "choice" and "ans" not in q:
            miss.append("ans")
        if q["kind"] != "choice" and "answer" not in q:
            miss.append("answer")
        if miss:
            raise SystemExit("%s번 문항에 %s 가 없다" % (q.get("n", "?"), miss))
        q.setdefault("ans", None)
        q.setdefault("lines", 3 if q["kind"] == "essay" else 1)
        q.setdefault("conditions", [])
        q.setdefault("criteria", "")
        q.setdefault("must_use", [])
        q.setdefault("no_quote_3gram", False)
        q.setdefault("from_passage", False)
        q.setdefault("passage", None)
        q.setdefault("box", None)
        q.setdefault("box_ref", None)
        q.setdefault("show", "list")
        q.setdefault("fixed", False)
        q.setdefault("opts", None)
    for p in d["passages"].values():
        p.setdefault("header", "")
        p.setdefault("kind", "rewrite")
        p.setdefault("restore", [])
        p.setdefault("guard", [])
        p.setdefault("free", [])
    prof = S.profile(d["school"])["exam"]
    # 학교 규격이 바뀌기 전에 배부한 회차를 고쳐 다시 뽑을 때만 쓴다 — 배부판 형식을 그대로 유지한다
    ov = d.get("profile_override")
    if ov:
        if not ov.get("why"):
            raise SystemExit("profile_override 에는 why(예외 사유)가 있어야 한다")
        prof = dict(prof, **{k: v for k, v in ov.items() if k != "why"})
    return expand(d), prof


def spread(d, prof):
    """정답을 target 위치로 돌린다. 해설 속 번호는 설정에 따라 재매핑하거나(remap) 금지한다(forbid)."""
    target = d.get("target")
    mode = d.get("sol_numbers", prof.get("sol_numbers", "forbid"))
    out = []
    choice_i = -1
    for q in d["questions"]:
        q = dict(q)
        q["orig_ans"] = q["ans"]
        if not is_choice(q):
            out.append(q)
            continue
        choice_i += 1
        i = choice_i
        if target and not q["fixed"] and q["opts"]:
            q["opts"], q["ans"], r = T.rotate(q["opts"], q["ans"], target[i])
            if mode == "remap" and r:
                q["sol"] = T.remap_circled(q["sol"], r)
        out.append(q)
    return out


# ── 조판 ────────────────────────────────────────────────────
def tight(body):
    for p in (".", ";", ","):
        body = body.replace(BL + p, BL[:-len("&nbsp;")] + p)
    return body


def band(p, prof):
    for limit, b in prof.get("bands", [[3.5, 3], [4.5, 4], [999, 5]]):
        if p < limit:
            return b
    return 5


def q_html(q, d, answers, prof):
    tag = ""
    if not is_choice(q) and prof.get("written_kind_tag"):
        tag = '<span class="ktag">(%s)</span> ' % ("서술형" if q["kind"] == "essay" else "단답형")
    # stem_after: 배점 뒤에 붙는 말 (한솔고 1회고사 서답형7 "[4점] (각 1점씩)")
    # sub_pts: 여러 칸 문항의 칸별 배점 → 발문 끝은 "[총6점]" (양지고 기출 단답형 1 — 칸마다 [2점])
    b = ['<div class="q"><div class="qh"><span class="qn">%s</span> %s%s <span class="pt">[%s%s점]</span>%s</div>'
         % (qlabel(q, prof), tag, q["stem"], "총" if q.get("sub_pts") else "", T.fmt_pt(q["pt"]),
            (" " + q["stem_after"]) if q.get("stem_after") else "")]
    if q["box_ref"]:
        b.append('<div class="box">%s</div>' % tight(d["passages"][q["box_ref"]]["body"]))
    if q.get("arrow"):          # 지문 상자 → ↓ → 요약문 상자 (한솔고 요약문 문항)
        b.append('<div class="arrow">&darr;</div>')
    if q["box"]:   # 단독 지문(box_ref) + 요약문 상자(box)를 같이 쓰는 문항도 둘 다 싣는다
        b.append('<div class="box">%s</div>' % q["box"])
    if not is_choice(q):
        if q["conditions"]:
            bullet = prof.get("cond_bullet", "&#8226; ")
            b.append('<div class="cond">%s<br>%s</div>' % (prof.get("cond_title", "&lt;조건&gt;"),
                                                          "<br>".join(bullet + c for c in q["conditions"])))
        if answers:
            b.append('<div class="mans">&#10004; 모범답안 &nbsp;%s</div>' % q["answer"])
        else:
            b.append(answer_form(q))
        b.append("</div>")
        return "".join(b)
    if q.get("opt_head"):       # 짝 선택지 머리 — "[a] … [b]"
        b.append('<div class="oh">%s</div>' % q["opt_head"])
    if q["show"] == "list":
        for i, o in enumerate(q["opts"]):
            mk = " <b>&#10004;</b>" if answers and i == q["ans"] else ""
            b.append('<div class="op">%s %s%s</div>' % (CIR[i], o, mk))
    elif q["show"] == "row":
        cells = []
        for i, o in enumerate(q["opts"]):
            mk = "<b>&#10004;</b>" if answers and i == q["ans"] else ""
            cells.append('<span class="op">%s %s%s</span>' % (CIR[i], o, mk))
        b.append('<div class="row">%s</div>' % "".join(cells))
    elif q["show"] in ("cols2", "grid32"):     # 2열(순서형) · 3+2 격자(기호 조합형) — 양지고 기출 배치
        cells = []
        for i, o in enumerate(q["opts"]):
            mk = " <b>&#10004;</b>" if answers and i == q["ans"] else ""
            cells.append('<div class="op">%s %s%s</div>' % (CIR[i], o, mk))
        b.append('<div class="%s">%s</div>' % (q["show"], "".join(cells)))
    if answers and q["show"] == "none":
        b.append('<div class="ansl">&#10004; 정답 %s</div>' % CIR[q["ans"]])
    b.append("</div>")
    return "".join(b)


FORMS = ("line", "paren", "table", "cells", "fill")


def answer_form(q):
    """서답형 답란. form: line(줄, 기본) · paren(답: (   ) 기호 쓰기) · table(칸별 배점 표)
    · cells(답: 이름표마다 빈칸) · fill(답: 틀 문장의 {{칸}} 채우기)"""
    form = q.get("form", "line")
    bl = '<span class="bl"></span>'
    if form == "paren":
        return '<div class="af">답: (<span class="gap"></span>)</div>'
    if form == "table":
        th = "".join("<th>%s (%s점)</th>" % (c, T.fmt_pt(p)) for c, p in q["form_cols"])
        return '<table class="ft"><tr>%s</tr><tr>%s</tr></table>' % (th, "<td></td>" * len(q["form_cols"]))
    if form == "cells":
        sub = q.get("sub_pts") or []
        cols = ["%s <span class=\"pt\">[%s점]</span>" % (c, T.fmt_pt(sub[i])) if len(sub) == len(q["form_cols"]) else c
                for i, c in enumerate(q["form_cols"])]
        # 칸 이름과 밑줄은 한 덩어리로 줄을 넘긴다 (좁은 단에서 밑줄만 따로 떨어지지 않게)
        return '<div class="af">답: %s</div>' % " ".join(
            '<span style="display:inline-block;white-space:nowrap;margin-right:4mm">%s %s</span>' % (c, bl) for c in cols)
    if form == "fill":
        return '<div class="af">답: %s</div>' % q["form_text"].replace("{{칸}}", bl)
    return '<div class="af">답:</div>' + '<div class="wl"></div>' * q["lines"]


def page_html(Q, d, prof, answers=False):
    total = prof.get("total", 100)
    b = ['<div class="head"><div class="t1">%s%s</div><div class="t2">%s</div>'
         '<div class="bar"><span>이름 ______________________</span>'
         '<span>점수 ________ / %d</span></div></div>'
         % (d["title"], prof.get("answer_title_suffix", "") if answers else "", d["subtitle"], total),
         '<div class="guide">%s</div>' % d["guide"], '<div class="cols">']
    shown, written_started = set(), False
    for q in Q:
        if not is_choice(q) and not written_started and prof.get("written_heading") and not prof.get("interleave"):
            b.append('<div class="subh">%s</div>' % prof["written_heading"])
            written_started = True
        k = q["passage"]
        if k and k not in shown:
            p = d["passages"][k]
            b.append('<div class="psgh">%s</div>' % p["header"])
            b.append('<div class="psg">%s</div>' % tight(p["body"]))
            shown.add(k)
        b.append(q_html(q, d, answers, prof))
    b.append("</div>")
    b.append('<div class="foot">%s · 카이젠 나성 캠퍼스</div>' % d["footer"])
    if answers:
        b.append('<div class="pb"></div><h2>정답 및 해설</h2>')
        b.append('<div class="lg">배점 표시 &nbsp;%s</div>' % prof["legend"])
        QC = [q for q in Q if is_choice(q)]
        half = (len(QC) + 1) // 2
        for rows in (QC[:half], QC[half:]):
            h = "".join('<th class="h%d">%d</th>' % (band(q["pt"], prof), q["n"]) for q in rows)
            dd = "".join('<td class="p%d">%s</td>' % (band(q["pt"], prof), CIR[q["ans"]]) for q in rows)
            pr = ""
            if prof.get("answer_points_row"):
                pr = "<tr>%s</tr>" % "".join('<td class="pp">%s</td>' % T.fmt_pt(q["pt"]) for q in rows)
            b.append('<table class="ans"><thead><tr>%s</tr></thead><tbody><tr>%s</tr>%s</tbody></table>'
                     % (h, dd, pr))
        b.append('<div class="cols">')
        for q in Q:
            if is_choice(q):
                b.append('<div class="sol"><b>%d.</b> 정답 <b>%s</b> &nbsp;%s</div>' % (q["n"], CIR[q["ans"]], q["sol"]))
            else:
                crit = (' &nbsp;<b>[채점]</b> %s' % q["criteria"]) if q["criteria"] else ""
                b.append('<div class="sol"><b>%s</b> 모범답안 <b>%s</b> &nbsp;%s%s</div>'
                         % (qlabel(q, prof), q["answer"], q["sol"], crit))
        b.append("</div>")
    return '<!doctype html><meta charset="utf-8"><style>%s</style><body>%s</body>' % (
        CSS + prof.get("css_extra", ""), "".join(b))


# ── 점검 1: 데이터 ──────────────────────────────────────────
def check_data(rep, Q, d, prof):
    P = d["passages"]
    QC = [q for q in Q if is_choice(q)]
    QW = [q for q in Q if not is_choice(q)]
    wl = prof.get("written_label", "서답형")
    # interleave: 서답형이 자기 지문 묶음 안에 선택형과 섞여 나온다 (한솔고 【6, 서답형1】)
    if not prof.get("interleave") and Q[:len(QC)] != QC:
        rep.add("규격", "선택형이 모두 앞에, 서답형이 뒤에 와야 한다")
    n_q = prof.get("questions")
    if n_q is not None and len(QC) != n_q and not prof.get("written"):
        rep.add("규격", "문항 수 %d (규격 %d)" % (len(QC), n_q))
    if [q["n"] for q in QC] != list(range(1, len(QC) + 1)):
        rep.add("규격", "선택형 번호가 1부터 연속이 아님")
    if [q["n"] for q in QW] != list(range(1, len(QW) + 1)):
        rep.add("규격", "%s 번호가 1부터 연속이 아님" % wl)
    pts = [q["pt"] for q in Q]
    if round(sum(pts), 6) != prof.get("total", 100):
        rep.add("규격", "총점 %s" % T.fmt_pt(sum(pts)))
    rule = d.get("points") or prof.get("points", {})
    if "blueprint" in rule and pts != rule["blueprint"]:
        rep.add("규격", "문항별 배점이 학교 배점표와 다름")
    if "counter" in rule:
        got = {T.fmt_pt(k): v for k, v in collections.Counter(pts).items()}
        if got != rule["counter"]:
            rep.add("규격", "배점 구성 %s (규격 %s)" % (got, rule["counter"]))
    for part, qs in (("choice", QC), ("written", QW)):
        spec = prof.get(part)
        if not spec:
            continue
        name = "선택형" if part == "choice" else wl
        lo, hi = spec.get("count", [None, None]) if isinstance(spec.get("count"), list) else (spec.get("count"), spec.get("count"))
        if lo is not None and not lo <= len(qs) <= hi:
            rep.add("규격", "%s %d문항 (규격 %s)" % (name, len(qs), spec["count"]))
        if "total" in spec and round(sum(q["pt"] for q in qs), 6) != spec["total"]:
            rep.add("규격", "%s 배점 합 %s (규격 %s)" % (name, T.fmt_pt(sum(q["pt"] for q in qs)), spec["total"]))
        if "kinds" in spec:
            for q in qs:
                if q["kind"] not in spec["kinds"]:
                    rep.add("규격", "%s %d번 '%s' 는 이 학교 %s에 없는 형식" % (name, q["n"], q["kind"], name))
        # 단답형·서술형 따로 문항 수·배점 합 (한솔고 표지: 단답형 7문항 30점 · 서술형 4문항 20점)
        for kind, ks in spec.get("by_kind", {}).items():
            kq = [q for q in qs if q["kind"] == kind]
            kname = {"short": "단답형", "essay": "서술형"}.get(kind, kind)
            c = ks.get("count")
            lo, hi = (c if isinstance(c, list) else [c, c]) if c is not None else (None, None)
            if lo is not None and not lo <= len(kq) <= hi:
                rep.add("규격", "%s %d문항 (규격 %s)" % (kname, len(kq), c))
            if "total" in ks and round(sum(q["pt"] for q in kq), 6) != ks["total"]:
                rep.add("규격", "%s 배점 합 %s (규격 %s)" % (kname, T.fmt_pt(sum(q["pt"] for q in kq)), ks["total"]))
    # 이 학교가 선택형으로 내지 않는 유형 (한솔고: 어법·어휘는 서답형으로만 나온다)
    for q in QC:
        for w in prof.get("choice_stem_forbidden", []):
            if w in T.strip_html(q["stem"]):
                rep.add("유형", "%d번 '%s' 는 이 학교에서 선택형으로 나오지 않는다 (서답형으로)" % (q["n"], w))
        # 선택지 배치 (양지고 기출: 순서형 2열 · 기호 조합형 3+2 격자)
        for pat, want in prof.get("stem_show", {}).items():
            if pat in T.strip_html(q["stem"]) and q["show"] != want:
                rep.add("배치", "%d번 '%s' 문항 선택지는 %s 배치 (학교 기출)" % (q["n"], pat, want))
        combo = prof.get("combo_show")
        if combo and q["opts"] and all(re.fullmatch(r"[ⓐ-ⓩa-h](\s*,\s*[ⓐ-ⓩa-h])*", T.strip_html(o).strip())
                                       for o in q["opts"]) and q["show"] != combo:
            rep.add("배치", "%d번 기호 조합형 선택지는 %s 배치 (학교 기출)" % (q["n"], combo))
    # '않은 · 틀린 · 없는' 에 밑줄 (양지고 기출)
    for q in Q:
        s = q["stem"]
        for w in prof.get("neg_underline", []):
            if w in T.strip_html(s) and not re.search(r"<u>[^<]*%s[^<]*</u>" % w, s):
                rep.add("발문", "%s '%s' 에 밑줄이 없다 (학교 기출)" % (qlabel(q, prof), w))
    # 여러 칸 문항의 칸별 배점 (양지고 기출: "[총6점]" + 칸마다 [2점])
    for q in QW:
        sub = q.get("sub_pts")
        if sub and abs(sum(sub) - q["pt"]) > 1e-6:
            rep.add("규격", "%s 칸별 배점 합 %s ≠ 배점 %s" % (qlabel(q, prof), T.fmt_pt(sum(sub)), T.fmt_pt(q["pt"])))
        if prof.get("multi_part_sub_pts") and not sub:
            blob = T.strip_html(q["stem"] + " " + (q["box"] or ""))
            if ("(1)" in blob and "(2)" in blob) or re.search(r"\(1\)\s*[~∼-]\s*\(\d\)", blob):
                rep.add("규격", "%s 는 칸이 여럿이다 — sub_pts(칸별 배점)를 적는다 (학교 기출 [총N점])" % qlabel(q, prof))
    for q in QW:
        lab = qlabel(q, prof)
        # 학원에서 빼기로 한 서답형 조건 (한솔고: 연속 3단어 인용 금지, 2026-09-23 선생님 지시)
        blob = T.strip_html(q["stem"] + " " + " ".join(q["conditions"]))
        for w in prof.get("written_forbidden", []):
            if w in blob:
                rep.add("서답형", "%s 발문·조건에 '%s' — 이 반에서 빼기로 한 조건" % (lab, w))
        if prof.get("written_forbidden") and q["no_quote_3gram"]:
            rep.add("서답형", "%s no_quote_3gram — 이 반에서 빼기로 한 조건" % lab)
        form = q.get("form", "line")
        if form not in FORMS:
            rep.add("서답형", "%s form '%s' 는 %s 중 하나" % (lab, form, "/".join(FORMS)))
        if form in ("table", "cells") and not q.get("form_cols"):
            rep.add("서답형", "%s form_cols 없음" % lab)
        if form == "fill" and "{{칸}}" not in q.get("form_text", ""):
            rep.add("서답형", "%s form_text 에 {{칸}} 없음" % lab)
        if form == "table" and abs(sum(p for _c, p in q["form_cols"]) - q["pt"]) > 1e-6:
            rep.add("서답형", "%s 답란 칸별 배점 합이 문항 배점과 다름" % lab)
        stem = T.strip_html(q["stem"])
        for pat, want in prof.get("stem_form", {}).items():     # "어법상 틀린" → table
            if pat in stem and form != want:
                rep.add("서답형", "%s '%s' 문항 답란은 %s 형식이어야 한다 (학교 기출)" % (lab, pat, want))
        # 어법·어휘 ⓐ~ 밑줄은 낱말 단위 (한솔고 기출: increases · that · where · easier …)
        if re.search(r"어법|낱말", stem) and q["passage"] in P:
            spans = re.findall(r"[ⓐ-ⓩ]\s*<u>(.*?)</u>", P[q["passage"]]["body"], re.S)
            lim = prof.get("mark_max_words", MAX_UL_WORDS)
            long = [s for s in spans if len(T.strip_html(s).split()) > lim]
            if long:
                rep.add("밑줄", "%s 밑줄이 %d단어를 넘는다: %s" % (lab, lim, " / ".join(T.strip_html(s)[:40] for s in long)))
            if not spans:
                rep.add("밑줄", "%s 지문에 ⓐ~ 밑줄이 없다" % lab)
    if QW and not prof.get("written"):
        rep.add("규격", "이 학교 설정에는 서답형이 없다 (학교/%s.json exam.written)" % d["school"])
    # 지문에 남은 빈칸·삽입 표시·ⓐ 기호는 그 지문을 쓰는 문항 어딘가에서 물어야 한다
    # (다른 회차 지문을 가져오면서 묻지 않는 빈칸이 남은 사고 — 나성중3 3회, 2026-09-18)
    for k, p in P.items():
        body = T.strip_html(p["body"])
        qs = [q for q in Q if q["passage"] == k or q.get("box_ref") == k]
        asked = " ".join(T.strip_html((q["stem"] or "") + " " + (q.get("box") or "") + " " + " ".join(q["opts"] or []))
                         for q in qs)
        if re.search(r"_{4,}", body) and not re.search(r"빈칸|들어갈", asked):
            rep.add("잔재", "%s 지문에 빈칸이 있는데 묻는 문항이 없다" % k)
        if re.search(r"\(\s?[A-E]\s?\)", body) and not re.search(r"들어가|들어갈|위치|배열|\(\s?[A-E]\s?\)", asked):
            rep.add("잔재", "%s 지문에 ( A ) 류 표시가 있는데 묻는 문항이 없다" % k)
        got = set(re.findall(r"[ⓐ-ⓩ]", asked))
        for a, b in re.findall(r"([ⓐ-ⓩ])\s*[~∼-]\s*([ⓐ-ⓩ])", asked):   # "ⓐ~ⓔ" 범위
            got |= {chr(c) for c in range(ord(a), ord(b) + 1)}
        for sym in sorted(set(re.findall(r"[ⓐ-ⓩ]", body))):
            if sym not in got:
                rep.add("잔재", "%s 지문의 %s 를 묻는 문항이 없다" % (k, sym))
    target = d.get("target")
    if target and len(target) != len(QC):
        rep.add("규격", "target 길이 %d (선택형 %d)" % (len(target), len(QC)))
    for q in QW:
        lab = qlabel(q, prof)
        ans_plain = T.strip_html(q["answer"])
        if not ans_plain.strip():
            rep.add("서답형", "%s 모범답안 없음" % lab)
        if q["opts"]:
            rep.add("서답형", "%s 에 선택지가 있음" % lab)
        body = " ".join(T.strip_html(P[k]["body"]) for k in (q["passage"], q["box_ref"]) if k and k in P)
        for w in q["must_use"]:
            if w.lower() not in ans_plain.lower():
                rep.add("서답형", "%s 모범답안에 지정 표현 '%s' 없음" % (lab, w))
        if q["no_quote_3gram"]:
            if not body:
                rep.add("서답형", "%s 인용 금지 조건인데 대상 지문이 없음" % lab)
            C.quote_3gram(rep, lab, ans_plain, body)
        if q["from_passage"]:
            words = set(re.findall(r"[a-z]+", body.lower()))
            for part in re.split(r"\s*[/,·]\s*", ans_plain):
                for w in re.findall(r"[A-Za-z]+", part):
                    if not T.word_in_text(w, words):
                        rep.add("서답형", "%s 모범답안 '%s' 가 지문에 없는 낱말 (찾아 쓰기)" % (lab, w))
    for i, q in enumerate(QC):
        n = q["n"]
        if q["opts"] is not None:
            if len(q["opts"]) != 5:
                rep.add("선택지", "%d번 선택지 %d개" % (n, len(q["opts"])))
            if len({T.strip_html(o) for o in q["opts"]}) != len(q["opts"]):
                rep.add("선택지", "%d번 선택지 중복" % n)
            if not 0 <= q["ans"] < len(q["opts"]):
                rep.add("선택지", "%d번 정답 번호 범위 밖" % n)
            # 선택지 앞에 ①~⑤를 또 붙이면 빌더 번호와 겹쳐 "① ① …"로 찍힌다 (나성중3 3·4회, 2026-09-18)
            if any(re.match(r"\s*[①-⑤]", T.strip_html(o)) for o in q["opts"]):
                rep.add("선택지", "%d번 선택지 앞에 ①~⑤ 표시가 있다 — 번호가 두 번 찍힌다" % n)
            if prof.get("options_no_hangul") and any(re.search("[가-힣]", T.strip_html(o))
                                                     and not re.fullmatch(r"\d+개", T.strip_html(o)) for o in q["opts"]):   # "3개"(개수 문항)는 예외
                rep.add("선택지", "%d번 한국어 선택지 — 이 학교 기출에는 없다 (학교/%s.json)" % (n, d["school"]))
        elif q["show"] != "none":
            rep.add("선택지", "%d번 선택지 없음" % n)
        if not q["sol"].strip():
            rep.add("해설", "%d번 해설 없음" % n)
        if T.strip_html(q["sol"]).startswith("모두 옳다"):
            rep.add("해설", "%d번 해설이 '모두 옳다'로 시작 — 오류를 안 심은 어법 문항" % n)
        # 어법·어휘는 지문 속 ①~⑤ 밑줄로 묻는다. 밑줄이 절 단위로 길면 한 밑줄 안에 포인트가 여러 개라
        # 어느 것을 묻는지 알 수 없고 다른 요소가 복수정답이 된다 (한솔고2 1회 2번, 2026-09-23)
        if q["show"] == "none" and re.search(r"어법|낱말", T.strip_html(q["stem"])) and q["passage"] in P:
            # ①~⑤ 가 붙은 밑줄만 본다 (함축 ⓐ 밑줄은 길어도 된다)
            spans = re.findall(r"[①-⑤]\s*<u>(.*?)</u>", P[q["passage"]]["body"], re.S)
            long = [s for s in spans if len(T.strip_html(s).split()) > MAX_UL_WORDS]
            if long:
                rep.add("밑줄", "%d번 밑줄이 너무 길다 (%d단어 넘음): %s"
                        % (n, MAX_UL_WORDS, " / ".join(T.strip_html(s)[:40] for s in long[:3])))
        if target and q["fixed"] and q["ans"] != target[i]:
            rep.add("규격", "%d번 고정 문항 정답(%d)이 target(%d)과 다름" % (n, q["ans"] + 1, target[i] + 1))
    for q in Q:
        lab = qlabel(q, prof)
        if not is_choice(q) and not q["sol"].strip():
            rep.add("해설", "%s 해설 없음" % lab)
        for key in (q["passage"], q["box_ref"]):
            if key and key not in P:
                rep.add("지문", "%s 지문 키 없음: %s" % (lab, key))
        if q["passage"] and q["box_ref"]:
            rep.add("지문", "%s 묶음 지문·단독 지문 동시 지정" % lab)
    used = {q["passage"] for q in Q} | {q["box_ref"] for q in Q}
    for k in P:
        if k not in used:
            rep.note("쓰지 않은 지문 %s" % k)
    for k, p in P.items():
        if "range" in p:
            a, b = p["range"]
            ns = [q["n"] for q in QC if q["passage"] == k]
            if ns and ns != list(range(a, b + 1)):
                rep.add("지문", "%s 묶음 [%d~%d] 인데 문항 %s" % (k, a, b, ns))
    labels = [q["n"] for q in QC]
    dist = C.answer_distribution(rep, labels, [q["ans"] for q in QC], prof.get("answer_same_max"),
                                 prof.get("answer_spread_max"), prof.get("no_triple", True))
    rep.note("정답 분포 %s" % dist)
    stems = " ".join(q["stem"] for q in Q)
    for w in prof.get("stem_forbidden", []):
        if w in stems:
            rep.add("유형", "이 학교가 내지 않는 유형 표현 '%s'" % w)
    if d.get("sol_numbers", prof.get("sol_numbers", "forbid")) == "forbid":
        for q in QC:
            if target and not q["fixed"] and re.search(r"[①-⑤]|&#931[2-6];", q["sol"]):
                rep.add("해설", "%d번 해설에 선택지 번호 — 순서 회전 후 틀어짐" % q["n"])
    # 범위 밖 소재
    for w in d.get("range_block", []):
        for k, p in P.items():
            if w.lower() in T.norm_source(p["body"]).lower():
                rep.add("범위", "%s 지문에 범위 밖 소재 '%s'" % (k, w))
        for q in Q:
            blob = q["stem"] + " ".join(q["opts"] or []) + (q["box"] or "")
            if w.lower() in T.norm_source(blob).lower():
                rep.add("범위", "%s 발문·보기에 범위 밖 소재 '%s'" % (qlabel(q, prof), w))
    custom_checks(rep, Q, d)


def select(sel, Q, d):
    """sel: passage:<키> · all · box|stem|sol|options|answer:<번호 또는 s번호(서답형)>"""
    byn = {qkey(q): q for q in Q}
    kind, _, key = sel.partition(":")
    if kind == "passage":
        return d["passages"][key]["body"]
    if kind == "all":
        return " ".join([p["body"] for p in d["passages"].values()] +
                        [q["stem"] + " " + (q["box"] or "") + " " + " ".join(q["opts"] or []) for q in Q])
    q = byn[int(key) if key.isdigit() else key]
    ans = q["answer"] if not is_choice(q) else (q["opts"] or [""])[q["ans"]]
    return {"box": q["box"] or "", "stem": q["stem"], "sol": q["sol"],
            "options": " ".join(q["opts"] or []), "answer": ans}[kind]


def custom_checks(rep, Q, d):
    """data.json "checks" — 회차마다 심은 장치가 실제로 들어갔는지."""
    byn = {qkey(q): q for q in Q}
    for c in d.get("checks", []):
        t, why = c["type"], c.get("why", "")
        try:
            if t in ("contains", "absent"):
                s = select(c["in"], Q, d)
                if c.get("plain"):
                    s = T.strip_html(s)
                for w in c["texts"]:
                    a, b = (w.lower(), s.lower()) if c.get("ci") else (w, s)
                    if (t == "contains") != (a in b):
                        rep.add("장치", "%s %s '%s' %s" % (c["in"], "에 없음:" if t == "contains" else "에 있음:",
                                                          w, why))
            elif t == "count":
                s = select(c["in"], Q, d)
                if "regex" in c:
                    got = len(re.findall(c["regex"], s))
                else:
                    got = s.count(c["token"])
                    if c.get("minus_blanks"):
                        got -= s.count(BL)
                if got != c["expect"]:
                    rep.add("장치", "%s 의 '%s' %d개 (기대 %d) %s" % (c["in"], c.get("token", c.get("regex")),
                                                                 got, c["expect"], why))
            elif t == "blank_once":
                for k in c["passages"]:
                    if d["passages"][k]["body"].count(BL) != 1:
                        rep.add("장치", "%s 빈칸이 1개가 아님" % k)
            elif t == "answer_is":
                got = T.strip_html(select("answer:%s" % c["q"], Q, d))
                if got != c["text"]:
                    rep.add("장치", "%s번 정답 '%s' (기대 '%s') %s" % (c["q"], got, c["text"], why))
            elif t == "answer_contains":
                got = T.strip_html(select("answer:%s" % c["q"], Q, d))
                if c["text"] not in got:
                    rep.add("장치", "%s번 정답 '%s' 에 '%s' 없음 %s" % (c["q"], got, c["text"], why))
            elif t == "options_subset":
                for o in byn[c["q"]]["opts"]:
                    if T.strip_html(o) not in c["of"]:
                        rep.add("장치", "%d번 선택지 '%s' 가 보기 목록에 없음" % (c["q"], T.strip_html(o)))
            elif t == "underlines_match_options":
                body = d["passages"][c["passage"]]["body"]
                marks = [T.strip_html(m[1]) for m in re.findall(r"<u>&#(931[2-6]);([^<]*)</u>", body)]
                want = []
                for o in byn[c["q"]]["opts"]:
                    s = T.strip_html(o)
                    want.append(s.split(" ", 1)[1] if s[:1] in "①②③④⑤" else s)
                if sorted(marks) != sorted(want):
                    rep.add("장치", "%d번 선택지 ≠ %s 밑줄: 지문 %s / 선택지 %s" % (c["q"], c["passage"], marks, want))
            elif t == "box_not_in_passage":
                if T.strip_html(byn[c["q"]]["box"]) in T.strip_html(d["passages"][c["passage"]]["body"]):
                    rep.add("장치", "%d번 <보기> 문장이 %s 지문에 이미 있음" % (c["q"], c["passage"]))
            else:
                rep.add("설정", "모르는 점검 종류 '%s'" % t)
        except (KeyError, IndexError) as e:
            rep.add("설정", "점검 %s 의 대상이 없음: %s" % (t, e))


# ── 점검 2: 원문 대조·누출 ──────────────────────────────────
def build_sources(rep, d):
    src = {}
    for key, parts in d.get("sources", {}).items():
        chunks = []
        for s in parts:
            if "pdf" in s:
                t = T.norm_source(S.pdf_text(s["pdf"]))
                if "until" in s:
                    if s["until"] not in t:
                        rep.add("원문준비", "%s 에서 경계 '%s' 를 못 찾음" % (s["pdf"], s["until"]))
                    t = t.split(s["until"])[0]
                for a, b in s.get("replace", []):
                    if a not in t:
                        rep.add("원문준비", "%s 에서 '%s' 를 못 찾음" % (s["pdf"], a))
                    t = t.replace(a, b)
                chunks.append(t)
            elif "bynum" in s:
                chunks.append(T.norm_source(" ".join(S.bynum(s["bynum"], s["round"], s["nums"]).values())))
            elif "json" in s:
                # 스캔본이라 텍스트 레이어가 없는 원본 — 전사해 둔 json 을 원문으로 쓴다
                # {"json": "<학원 폴더 기준 경로>", "keys": ["T1-2", …], "field": "body"}
                jp = pathlib.Path(__file__).resolve().parents[3] / s["json"]   # 학원 폴더 기준 경로
                if not jp.exists():
                    rep.add("원문준비", "%s 가 없다" % s["json"])
                    continue
                obj = json.loads(jp.read_text(encoding="utf-8"))
                field = s.get("field")
                got = []
                for k in s.get("keys", list(obj)):
                    if k not in obj:
                        rep.add("원문준비", "%s 에 '%s' 가 없다" % (s["json"], k))
                        continue
                    v = obj[k]
                    if isinstance(v, dict):
                        v = v.get(field or "body", "")
                    got.append(str(v))
                chunks.append(T.norm_source(" ".join(got)))
        src[key] = " ".join(chunks)
    return src


def check_sources(rep, Q, d):
    src = build_sources(rep, d)
    P = d["passages"]
    for key, p in P.items():
        if p["kind"] == "rewrite":
            rep.note("%s 재작성 — 원문 대조 제외" % key)
            continue
        if p.get("src") not in src:
            rep.add("원문", "%s 의 원문 '%s' 가 sources 에 없음" % (key, p.get("src")))
            continue
        # 순서 문항 문단 기호 (A)(B)(C) 는 문장 끝·줄바꿈 바로 뒤에 붙어 온다("…concerns.(B) To come…").
        # 기호를 걷으면 앞뒤 문장이 붙어 원문과 달라지므로 문단 경계로 끊는다. 문장 속 (A) [a / b] 같은 어휘 표시는 건드리지 않는다.
        body = PARA_MARK.sub(lambda m: m.group(1) + " ||| ", p["body"])
        text = T.norm_source(body.replace(BL, " ||| "))
        # restore·free 항목이 정규화 뒤 빈 글자가 되면("(A)"·"①" 같은 표시만 적은 경우) replace("") 가 글자마다
        # 구분자를 끼워 넣어 이 지문의 원문 대조가 통째로 꺼진다 (2026-09-30 양지고2 실전 3회에서 발견). 막는다.
        for shown, orig in p["restore"]:
            s2 = T.norm_source(shown)
            if not s2.strip():
                rep.add("수정표", "%s: restore 의 '%s' 가 정리하면 빈 글자다 — 앞뒤 낱말까지 넣어 적는다" % (key, shown[:50]))
                continue
            if s2 not in text:
                rep.add("수정표", "%s: '%s' 가 지문에 없음" % (key, shown[:50]))
            text = text.replace(s2, T.norm_source(orig))
        for f in p["free"]:
            f2 = T.norm_source(f.replace(BL, " ||| "))    # 새로 쓴 글 속 빈칸도 지문과 같게 바꿔서 찾는다
            if not f2.replace("|||", "").strip():
                rep.add("수정표", "%s: free 의 '%s' 가 정리하면 빈 글자다 — 대조가 꺼지므로 뺀다 (표시 기호는 대조 때 원래 걷힌다)" % (key, f[:50]))
                continue
            if f2 not in text:
                rep.add("수정표", "%s: 새로 쓴 부분 '%s' 가 지문에 없음" % (key, f[:50]))
            text = text.replace(f2, " ||| ")
        for chunk in text.split("|||"):
            for sent in T.split_sentences(chunk):
                if len(sent) >= 15 and sent not in src[p["src"]]:
                    rep.add("원문", "%s: \"%s\"" % (key, sent[:80]))
    # 정답 누출 — 정답 선택지 문장이 다른 지문·발문·보기에 그대로 있으면 안 된다
    visible = {"지문 " + k: T.norm_source(p["body"].replace(BL, " ")) for k, p in P.items()}
    for q in Q:
        visible["%s번 발문·보기" % qkey(q)] = T.norm_source(" ".join([q["stem"], q["box"] or ""] + (q["opts"] or [])))
    for q in Q:
        if not q["opts"] or q["fixed"]:
            continue
        a = T.norm_source(q["opts"][q["ans"]]).lower()
        own = {"%s번 발문·보기" % qkey(q), "지문 %s" % q["passage"], "지문 %s" % q["box_ref"]}
        for where, txt in visible.items():
            if where not in own and len(a) >= 12 and a in txt.lower():
                rep.add("정답누출", "%d번 정답 \"%s\" 가 %s 에 그대로 있음" % (q["n"], a, where))
    # 바꾼 문장의 원래 표현(guard)이 시험지 어디에도 보이면 안 된다
    users = collections.defaultdict(set)
    for q in Q:
        for k in (q["passage"], q["box_ref"]):
            if k:
                users[k].add("%s번 발문·보기" % qkey(q))
    for key, p in P.items():
        own = {"지문 " + key} | users[key]
        for g in p["guard"]:
            gl = T.norm_source(g).lower()
            for where, txt in visible.items():
                if gl in txt.lower():
                    if where in own and where.startswith("지문"):
                        rep.add("근거누출", "%s 의 원래 표현 \"%s\" 가 자기 지문에 남아 있음" % (key, g))
                    elif where not in own:
                        rep.add("근거누출", "%s 의 원래 표현 \"%s\" 가 %s 에 보임" % (key, g, where))


# ── 점검 3: PDF 실물 ────────────────────────────────────────
def check_pdfs(rep, Q, d, prof, stu_path, ans_path):
    import pymupdf
    with pymupdf.open(stu_path) as stu, pymupdf.open(ans_path) as ans:
        st = C.pdf_text(stu)
        at = re.sub(r"\s+", " ", C.pdf_text(ans))
        for w in prof.get("student_absent", ["정답", "해설", "✔"]):
            if w in st:
                rep.add("학생용", "'%s' 노출" % w)
        flat = re.sub(r"\s+", " ", st)
        for q in Q:
            lab = qlabel(q, prof)
            if "[%s%s점]" % ("총" if q.get("sub_pts") else "", T.fmt_pt(q["pt"])) not in flat:
                rep.add("학생용", "%s 배점 표시 누락" % lab)
            if not re.search(r"(^|\s)%s\s" % re.escape(lab), flat):
                rep.add("학생용", "%s 문항 번호 없음" % lab)
            if not is_choice(q) and not q["from_passage"]:
                a = re.sub(r"\s+", " ", T.strip_html(q["answer"]))
                if len(a) >= 15 and a in flat:
                    rep.add("학생용", "%s 모범답안이 학생용에 보임" % lab)
        masked = st
        for e in prof.get("student_forbidden_except", []):
            masked = masked.replace(e, "")
        C.teacher_words(rep, "학생용", masked, prof.get("student_forbidden", []))
        # 이 자료는 글쓰기 규칙(공용/규칙/글쓰기.md)의 예외다 — 해설까지 포함해 "자리"만 본다 (2026-09-23 지정)
        C.jari(rep, "학생용·해설", st + "\n" + "\n".join(T.strip_html(q["sol"] + " " + q["stem"]) for q in Q))
        C.residue(rep, "학생용", st)
        for w in d.get("range_block", []):
            if w.lower() in st.lower():
                rep.add("범위", "학생용에 범위 밖 소재 '%s'" % w)
        for q in Q:
            if not is_choice(q):
                if "%s 모범답안" % qlabel(q, prof) not in at:
                    rep.add("답지", "%s 모범답안 없음" % qlabel(q, prof))
                continue
            if "%d. 정답 %s" % (q["n"], T.CIRC[q["ans"]]) not in at:
                rep.add("답지", "%d번 해설 정답 표기 불일치" % q["n"])
        C.pdf_physical(rep, "학생용", stu)
        C.pdf_physical(rep, "답지", ans, page_numbers=True)
        rep.note("학생용 %d쪽 · 답지 %d쪽" % (len(stu), len(ans)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", help="PDF를 둘 폴더 (기본: data.json 이 있는 폴더)")
    ap.add_argument("--html", action="store_true", help="조판 HTML도 남긴다")
    a = ap.parse_args()
    d, prof = load(a.data)
    Q = spread(d, prof)
    rep = C.Report("%s · 모의고사 점검" % d["name"])
    check_data(rep, Q, d, prof)
    check_sources(rep, Q, d)
    rep.stop_if_bad()                       # PDF를 뽑기 전에 멈춘다

    stu_name = d["name"] + ".pdf"
    ans_name = d["name"] + d.get("answer_suffix", prof.get("answer_suffix", "_답지")) + ".pdf"
    jobs = [(page_html(Q, d, prof), stu_name), (page_html(Q, d, prof, answers=True), ans_name)]

    def post(paths):
        check_pdfs(rep, Q, d, prof, paths[0], paths[1])
        return rep
    out = pathlib.Path(a.out) if a.out else pathlib.Path(a.data).resolve().parent
    final = R.render_checked(jobs, out, post, footer=R.footer_html(d["footer"]), keep_html=a.html)
    for f in final:
        print("저장", f)


if __name__ == "__main__":
    main()
