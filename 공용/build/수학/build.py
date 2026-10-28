# -*- coding: utf-8 -*-
"""수학 시험지 빌더 — 학교 규격 수학 시험지 + 정답·해설 (수식 KaTeX, 그림은 계산해서 SVG).

사용: py 공용/build/수학/build.py <data.json> [--out 폴더] [--html]
  - 데이터 형식은 같은 폴더 README.md · 예시는 예시/샘플_수학.json
  - 학교 규격은 공용/build/학교/<school>.json 의 "math_exam"
  - 아래 중 하나라도 걸리면 PDF 를 내지 않는다
      수식(KaTeX) 오류 · 그림 결함(범위 밖 · 각/직각/같은 길이 표시가 실제와 다름 · 이름표 겹침)
      · 검산(verify) 불일치 · 진도 밖 단원 · 규격(문항 수 · 배점) · 선택지 중복(글자 · 값)
      · 조판 넘침(수식 · 그림이 단 밖으로) · PDF 실물(빈 쪽 · 쪽번호 · 정답 노출 · 강사용 멘트 · 수식 잔재)
"""
import argparse
import json
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from core import brand  # noqa: E402
from core import checks as C  # noqa: E402
from core import render as R  # noqa: E402
from core import sources as S  # noqa: E402
from core import text as T  # noqa: E402
import fig as F  # noqa: E402
import tex as X  # noqa: E402
import verify as V  # noqa: E402

CIR = T.CIRC_ENT
KINDS = ("choice", "short", "essay")          # 선택형 · 단답형 · 서술형
SHOWS = ("auto", "row", "grid32", "cols2", "list")

CSS = r"""
@page{size:A4;margin:13mm 11mm 12mm 11mm}
*{box-sizing:border-box}
body{font-family:"Noto Serif KR","Batang","Malgun Gothic",serif;font-size:9.6pt;line-height:1.75;color:#111;margin:0}
.brand-top{text-align:right;line-height:0;margin:0 0 1.4mm 0}
.head{border:1.2pt solid #111;padding:2.4mm 3mm;margin:0 0 4mm 0}
.head .t1{font-size:13.5pt;font-weight:700;text-align:center;letter-spacing:-.02em}
.head .t2{font-size:9.4pt;text-align:center;margin-top:1mm;color:#333}
.bar{display:flex;gap:3mm;margin:2.5mm 0 0 0;font-size:9.2pt;border-top:.6pt solid #999;padding-top:2mm}
.bar span{flex:1}
.guide{font-size:8.8pt;color:#333;border:.6pt solid #999;padding:2mm 2.6mm;margin:0 0 4mm 0;background:#fafafa}
.cols{column-count:2;column-gap:7mm;column-rule:.5pt solid #bbb}
.q{break-inside:avoid;page-break-inside:avoid;margin:0 0 3.8mm 0;padding-top:1.2mm;display:inline-block;width:100%;vertical-align:top}
/* padding-top: 첫 줄의 분수가 상자 위로 삐져나오면 그 조각이 앞 쪽 끝에 찍힌다 · inline-block: 쪼갤 수 없는 상자 */
.qh{margin:0 0 1.4mm 0;text-indent:-5.6mm;padding-left:5.6mm}
.qn{font-weight:700}
.pt{font-size:8.4pt;color:#555;white-space:nowrap}
.box{border:.6pt solid #777;padding:2mm 2.4mm;margin:1.4mm 0;line-height:1.8}
.figw{text-align:center;margin:1.6mm 0 1.6mm 0;line-height:0}
.figw svg{overflow:visible}
.figw text{fill:#000}
.flab{color:#000}
.op{margin:.6mm 0 0 2mm;text-indent:-4.4mm;padding-left:4.4mm}
.row{margin:1mm 0 0 2mm;display:flex;flex-wrap:nowrap;justify-content:space-between}
.row .op{margin:0;text-indent:0;padding-left:0}
.cols2,.grid32{display:grid;column-gap:3mm;row-gap:.8mm;margin:.8mm 0 0 2mm}
.cols2{grid-template-columns:1fr 1fr}
.grid32{grid-template-columns:repeat(3,1fr)}
.cols2 .op,.grid32 .op{margin:0;text-indent:0;padding-left:0}
.af{margin:1.4mm 0 0 2mm;font-weight:700}
.af .bl{display:inline-block;border-bottom:.6pt solid #333;min-width:34mm;height:5mm;vertical-align:bottom}
.work{border:.6pt solid #999;margin:1.4mm 0 0 0;position:relative}
.work .wt{position:absolute;left:1.6mm;top:.6mm;font-size:8pt;color:#777}
.work .wa{position:absolute;right:2mm;bottom:1.2mm;font-size:9pt;font-weight:700}
.work .wa .bl{display:inline-block;border-bottom:.6pt solid #333;min-width:26mm;height:5mm;vertical-align:bottom}
.foot{margin-top:4mm;border-top:.6pt solid #999;padding-top:1.6mm;font-size:7.8pt;color:#666}
.pb{page-break-before:always}
h2{font-size:11.5pt;background:#111;color:#fff;padding:1.8mm 3mm;margin:0 0 3mm 0}
table{width:100%;border-collapse:collapse;font-size:9pt;margin:0 0 4mm 0}
th,td{border:.6pt solid #888;padding:1.3mm 1.6mm;text-align:center}
th{background:#eee;font-weight:700}
table.ans{table-layout:fixed}
table.ans td{font-size:11.5pt;line-height:1.25}
table.ans td.pp{font-size:7.8pt;color:#444;padding:.8mm .4mm}
.sol{break-inside:avoid;page-break-inside:avoid;margin:0 0 3.4mm 0;font-size:9.2pt;text-indent:-6.5mm;padding-left:6.5mm}
.sol .figw{text-indent:0}
.steps{margin:1mm 0 0 0;text-indent:0;font-size:8.8pt}
.steps td,.steps th{text-align:left;padding:.8mm 1.4mm}
.steps td.p{text-align:center;width:11mm;white-space:nowrap}
.mans{border:.8pt solid #c00;color:#b00;padding:1.2mm 2.2mm;margin:1.2mm 0 0 0}
.texerr{color:#c00;font-weight:700}
.katex{font-size:1.08em}
.op .katex,.row .katex{font-size:1.05em}
.katex-display{margin:1.2mm 0}
"""


def is_choice(q):
    return q["kind"] == "choice"


def qlabel(q, prof):
    if is_choice(q):
        return "%d." % q["n"]
    return "%s %d." % (prof.get("written_label", "서답형"), q["n"])


def ptxt(q, prof):
    return prof.get("pt_format", "[%s점]") % T.fmt_pt(q["pt"])


# ── 불러오기 ────────────────────────────────────────────────
def load(data_path):
    d = json.loads(pathlib.Path(data_path).read_text(encoding="utf-8"))
    if d.get("subject") != "math":
        raise SystemExit('수학 빌더용 data.json 은 "subject": "math" 를 적는다')
    for k in ("school", "name", "title", "subtitle", "guide", "footer", "covered", "questions"):
        if k not in d:
            raise SystemExit("data.json 에 '%s' 가 없다" % k)
    d.setdefault("brand", brand.name(data_path))
    d.setdefault("macros", {})
    d.setdefault("range_block", [])
    prof = S.profile(d["school"]).get("math_exam")
    if not prof:
        raise SystemExit("학교/%s.json 에 math_exam(수학 시험 규격)이 없다 — _예시.json 을 본떠 넣는다" % d["school"])
    # 진도 밖 단원은 아예 만들지 않는다 (작업 규칙: 진도가 안 나간 구간은 출제하지 않는다)
    covered = set(d["covered"])
    for q in d["questions"]:
        n = q.get("n", "?")
        for k in ("n", "kind", "pt", "unit", "stem", "sol"):
            if k not in q:
                raise SystemExit("%s번 문항에 '%s' 가 없다" % (n, k))
        if q["kind"] not in KINDS:
            raise SystemExit("%s번 문항 kind 는 %s" % (n, " · ".join(KINDS)))
        if q["unit"] not in covered:
            raise SystemExit("%s번 문항 단원 '%s' 는 진도(covered) 밖이다 — 출제하지 않는다" % (n, q["unit"]))
        if q["kind"] == "choice":
            for k in ("opts", "ans"):
                if k not in q:
                    raise SystemExit("%s번 선택형에 '%s' 가 없다" % (n, k))
        elif "answer" not in q:
            raise SystemExit("%s번 %s 에 answer(모범답안)가 없다" % (n, q["kind"]))
        q.setdefault("show", "auto")
        q.setdefault("steps", [])
        q.setdefault("criteria", "")
    return d, prof


# ── 수식 ────────────────────────────────────────────────────
def dfrac_opts(s):
    """선택지 속 \\frac 은 \\dfrac 으로 (글줄 안 분수가 작아 읽기 어렵다)."""
    return re.sub(r"\\frac(?![A-Za-z])", r"\\dfrac", s)


def texts(q):
    """(어디, 글) — 수식을 모을 모든 글."""
    out = [("%s번 발문" % q["n"], q["stem"]), ("%s번 해설" % q["n"], q["sol"])]
    for k in ("box", "answer", "criteria"):
        if q.get(k):
            out.append(("%s번 %s" % (q["n"], k), q[k]))
    for i, o in enumerate(q.get("opts") or []):
        out.append(("%s번 선택지 %d" % (q["n"], i + 1), o))
    for i, s in enumerate(q["steps"]):
        out.append(("%s번 채점 단계 %d" % (q["n"], i + 1), s["desc"]))
    for k in ("fig_svg", "sol_fig_svg"):
        if q.get(k):
            out.append(("%s번 그림" % q["n"], q[k]))
    return out


# ── 그림 ────────────────────────────────────────────────────
def draw_figs(rep, Q):
    for q in Q:
        for key, fid in (("fig", "q%d%s" % (q["n"], q["kind"][0])), ("sol_fig", "s%d%s" % (q["n"], q["kind"][0]))):
            if not q.get(key):
                continue
            svg, errs, notes = F.draw(q[key], fid)
            for e in errs:
                rep.add("그림", "%s %s" % (q["n"], e))
            for n in notes:
                rep.note("%s번 그림: %s" % (q["n"], n))
            q[key + "_svg"] = svg


# ── 조판 ────────────────────────────────────────────────────
def opt_len(o):
    """선택지 길이 어림 (글자 수 · 분수는 넓게)."""
    s = X.plain(o)
    s = re.sub(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", lambda m: "x" * max(len(m.group(1)), len(m.group(2))), s)
    s = re.sub(r"\\sqrt", "v", s)
    s = re.sub(r"\\sum_\{[^}]*\}\^\{?[^ }]*\}?", "SS", s)
    s = re.sub(r"\\[A-Za-z]+|[{}^_ ]", "", s)
    return len(s)


def layout(q):
    if q["show"] != "auto":
        return q["show"]
    m = max(opt_len(o) for o in q["opts"])
    if m <= 5:
        return "row"
    if m <= 9:
        return "grid32"
    if m <= 18:
        return "cols2"
    return "list"


def q_html(q, prof, tx, answers):
    b = ['<div class="q"><div class="qh"><span class="qn">%s</span> %s <span class="pt">%s</span></div>'
         % (qlabel(q, prof), tx.apply(q["stem"]), ptxt(q, prof))]
    if q.get("box"):
        b.append('<div class="box">%s</div>' % tx.apply(q["box"]))
    if q.get("fig_svg"):
        b.append('<div class="figw">%s</div>' % tx.apply(q["fig_svg"]))
    if is_choice(q):
        show = layout(q)
        cells = ['<%s class="op">%s %s</%s>' % ("span" if show == "row" else "div", CIR[i], tx.apply(dfrac_opts(o)),
                                                 "span" if show == "row" else "div") for i, o in enumerate(q["opts"])]
        b.append('<div class="%s">%s</div>' % (show, "".join(cells)) if show != "list" else "".join(cells))
    elif answers:
        b.append('<div class="mans">&#10004; 모범답안 &nbsp;%s</div>' % tx.apply(q["answer"]))
    elif q["kind"] == "short":
        b.append('<div class="af">답: <span class="bl"></span></div>')
    else:
        h = q.get("space_mm", prof.get("essay_space_mm", 45))
        b.append('<div class="work" style="height:%smm"><span class="wt">풀이</span>'
                 '<span class="wa">답: <span class="bl"></span></span></div>' % h)
    b.append("</div>")
    return "".join(b)


def steps_html(q, tx):
    if not q["steps"]:
        return ""
    rows = "".join('<tr><td>%s</td><td class="p">%s점</td></tr>' % (tx.apply(s["desc"]), T.fmt_pt(s["pt"]))
                   for s in q["steps"])
    return '<table class="steps"><tr><th>채점 단계 (부분 점수)</th><th>배점</th></tr>%s</table>' % rows


def page_html(Q, d, prof, tx, answers=False):
    logo = brand.header_logo("8mm")
    b = ['<div class="brand-top">%s</div>' % logo] if logo else []
    b += ['<div class="head"><div class="t1">%s%s</div><div class="t2">%s</div>'
          '<div class="bar"><span>이름 ______________________</span><span>점수 ________ / %s</span></div></div>'
          % (d["title"], prof.get("answer_title_suffix", "") if answers else "", d["subtitle"],
             T.fmt_pt(prof.get("total", 100))),
          '<div class="guide">%s</div>' % tx.apply(d["guide"]), '<div class="cols">']
    for q in Q:
        b.append(q_html(q, prof, tx, answers))
    b.append("</div>")
    b.append('<div class="foot">%s</div>' % " · ".join(x for x in (d["footer"], d["brand"]) if x))
    if answers:
        b.append('<div class="pb"></div><h2>정답 및 해설</h2>')
        QC = [q for q in Q if is_choice(q)]
        half = (len(QC) + 1) // 2 if len(QC) > 10 else len(QC)
        for rows in (QC[:half], QC[half:]):
            if not rows:
                continue
            h = "".join("<th>%d</th>" % q["n"] for q in rows)
            dd = "".join("<td>%s</td>" % CIR[q["ans"]] for q in rows)
            pr = "".join('<td class="pp">%s점</td>' % T.fmt_pt(q["pt"]) for q in rows)
            b.append('<table class="ans"><tr>%s</tr><tr>%s</tr><tr>%s</tr></table>' % (h, dd, pr))
        b.append('<div class="cols">')
        for q in Q:
            fig = '<div class="figw">%s</div>' % tx.apply(q["sol_fig_svg"]) if q.get("sol_fig_svg") else ""
            if is_choice(q):
                b.append('<div class="sol"><b>%d.</b> 정답 <b>%s</b> &nbsp;%s%s</div>'
                         % (q["n"], CIR[q["ans"]], tx.apply(q["sol"]), fig))
            else:
                crit = (' &nbsp;<b>[채점]</b> %s' % tx.apply(q["criteria"])) if q["criteria"] else ""
                b.append('<div class="sol"><b>%s</b> 모범답안 <b>%s</b> &nbsp;%s%s%s%s</div>'
                         % (qlabel(q, prof), tx.apply(q["answer"]), tx.apply(q["sol"]), fig, crit, steps_html(q, tx)))
        b.append("</div>")
    return '<!doctype html><meta charset="utf-8"><style>%s%s</style><body>%s%s</body>' % (
        X.css(), CSS + prof.get("css_extra", ""), brand.watermark(), "".join(b))


# ── 점검 1: 데이터 · 검산 ────────────────────────────────────
def option_values(rep, q):
    """선택지마다 sympy 값 — opt_values 가 있으면 그것, 없으면 선택지 수식을 읽는다."""
    if q.get("opt_values"):
        if len(q["opt_values"]) != len(q["opts"]):
            rep.add("검산", "%d번 opt_values 개수가 선택지와 다르다" % q["n"])
            return None
        try:
            return [V.py_value(v) for v in q["opt_values"]]
        except Exception as e:
            rep.add("검산", "%d번 opt_values 를 읽지 못함 (%s)" % (q["n"], e))
            return None
    vals = []
    for i, o in enumerate(q["opts"]):
        try:
            vals.append(V.tex_value(o))
        except Exception as e:
            rep.add("검산", "%d번 선택지 %s '%s' 를 값으로 읽지 못함 (%s) — opt_values 를 적는다"
                    % (q["n"], T.CIRC[i], X.plain(o), e))
            return None
    return vals


def check_verify(rep, Q, prof):
    unchecked = []
    for q in Q:
        lab = qlabel(q, prof)
        if not q.get("verify"):
            unchecked.append(lab)
            continue
        try:
            got = V.run(q["verify"])
        except Exception as e:
            rep.add("검산", "%s verify 실행 실패: %s" % (lab, e))
            continue
        if is_choice(q):
            vals = option_values(rep, q)
            if vals is None:
                continue
            hit = [i for i, v in enumerate(vals) if V.same(got, v)]
            if not hit:
                rep.add("검산", "%s 검산 값 %s 가 어느 선택지와도 같지 않다" % (lab, got))
            elif len(hit) > 1:
                rep.add("검산", "%s 검산 값 %s 와 같은 선택지가 %s — 정답이 둘 이상" % (lab, got, [T.CIRC[i] for i in hit]))
            elif hit[0] != q["ans"]:
                rep.add("검산", "%s 표시한 정답은 %s 인데 검산 값 %s 는 %s" % (lab, T.CIRC[q["ans"]], got, T.CIRC[hit[0]]))
        else:
            try:
                want = V.py_value(q["value"]) if "value" in q else V.tex_value(q["answer"])
            except Exception as e:
                rep.add("검산", "%s 모범답안을 값으로 읽지 못함 (%s) — value 를 적는다" % (lab, e))
                continue
            if not V.same(got, want):
                rep.add("검산", "%s 모범답안 값 %s ≠ 검산 값 %s" % (lab, want, got))
        q["verified"] = got
    if unchecked:
        rep.note("검산(verify) 없는 문항 %s — 손으로 다시 풀어 확인한다" % ", ".join(unchecked))


def check_backslash(rep, d):
    """JSON 에 \\frac · \\times · \\beta · \\neq 를 \\ 하나로 쓰면 글자가 제어문자(\\f · \\t · \\b · \\n)로 바뀌고
    KaTeX 는 오류 없이 엉뚱하게 그린다. 수식 안의 제어문자 · 어디든 \\f \\b \\t \\r 을 결함으로 본다."""
    bad = re.compile("[\x07\x08\x09\x0b\x0c\x0d]")

    def walk(v, where):
        if isinstance(v, dict):
            for k, x in v.items():
                if k not in ("verify",):
                    walk(x, "%s.%s" % (where, k) if where else k)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, "%s[%d]" % (where, i))
        elif isinstance(v, str):
            math = "".join(re.findall(r"\$[^$]*\$", v, re.S))
            if bad.search(v) or "\n" in math:
                rep.add("데이터", "%s 에 제어문자가 있다 — JSON 에서는 \\\\frac 처럼 역슬래시를 두 번 쓴다" % where)

    walk(d, "")


def check_data(rep, Q, d, prof):
    check_backslash(rep, d)
    QC = [q for q in Q if is_choice(q)]
    QW = [q for q in Q if not is_choice(q)]
    if Q[:len(QC)] != QC:
        rep.add("규격", "선택형이 모두 앞에, 서답형이 뒤에 와야 한다")
    if [q["n"] for q in QC] != list(range(1, len(QC) + 1)):
        rep.add("규격", "선택형 번호가 1부터 연속이 아님")
    if [q["n"] for q in QW] != list(range(1, len(QW) + 1)):
        rep.add("규격", "서답형 번호가 1부터 연속이 아님")
    pts = [q["pt"] for q in Q]
    if round(sum(pts), 6) != prof.get("total", 100):
        rep.add("규격", "총점 %s (규격 %s)" % (T.fmt_pt(sum(pts)), prof.get("total", 100)))
    bp = prof.get("points", {}).get("blueprint")
    if bp and pts != bp:
        rep.add("규격", "문항별 배점 %s 가 학교 배점표 %s 와 다름" % (pts, bp))
    for part, qs in (("choice", QC), ("written", QW)):
        spec = prof.get(part) or {}
        name = "선택형" if part == "choice" else "서답형"
        c = spec.get("count")
        if c is not None:
            lo, hi = c if isinstance(c, list) else (c, c)
            if not lo <= len(qs) <= hi:
                rep.add("규격", "%s %d문항 (규격 %s)" % (name, len(qs), c))
        if "total" in spec and round(sum(q["pt"] for q in qs), 6) != spec["total"]:
            rep.add("규격", "%s 배점 합 %s (규격 %s)" % (name, T.fmt_pt(sum(q["pt"] for q in qs)), spec["total"]))
    for q in QC:
        n = q["n"]
        if len(q["opts"]) != 5:
            rep.add("선택지", "%d번 선택지 %d개" % (n, len(q["opts"])))
        if not 0 <= q["ans"] < len(q["opts"]):
            rep.add("선택지", "%d번 정답 번호(ans, 0부터) 범위 밖" % n)
        norm = [re.sub(r"\s+|\\[,;!]|\\[dt]?(?=frac)", "", o) for o in q["opts"]]
        if len(set(norm)) != len(norm):
            rep.add("선택지", "%d번 선택지 글자 중복" % n)
        if q["show"] not in SHOWS:
            rep.add("선택지", "%d번 show 는 %s" % (n, " · ".join(SHOWS)))
        if any(re.match(r"\s*[①-⑤]", o) for o in q["opts"]):
            rep.add("선택지", "%d번 선택지 앞에 ①~⑤ — 번호가 두 번 찍힌다" % n)
        # 값이 같은 선택지 (√8 과 2√2 같은 것) — 정답이 둘이 된다
        try:
            vals = [V.py_value(v) for v in q["opt_values"]] if q.get("opt_values") else [V.tex_value(o) for o in q["opts"]]
        except Exception:
            vals = None
        if vals:
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    if V.same(vals[i], vals[j]):
                        rep.add("선택지", "%d번 선택지 %s 와 %s 의 값이 같다" % (n, T.CIRC[i], T.CIRC[j]))
    for q in QW:
        lab = qlabel(q, prof)
        if q.get("opts"):
            rep.add("서답형", "%s 에 선택지가 있음" % lab)
        if not X.plain(q["answer"]).strip():
            rep.add("서답형", "%s 모범답안 없음" % lab)
        if q["kind"] == "essay":
            if not q["steps"]:
                rep.add("서답형", "%s 서술형인데 채점 단계(steps · 부분 점수)가 없다" % lab)
            elif abs(sum(s["pt"] for s in q["steps"]) - q["pt"]) > 1e-9:
                rep.add("서답형", "%s 채점 단계 배점 합 %s ≠ 배점 %s"
                        % (lab, T.fmt_pt(sum(s["pt"] for s in q["steps"])), T.fmt_pt(q["pt"])))
    for q in Q:
        if not X.plain(q["sol"]).strip():
            rep.add("해설", "%s 해설 없음" % qlabel(q, prof))
    if QC:
        dist = C.answer_distribution(rep, [q["n"] for q in QC], [q["ans"] for q in QC], prof.get("answer_same_max"),
                                     prof.get("answer_spread_max"), prof.get("no_triple", True))
        rep.note("정답 분포 %s" % dist)
    for w in d["range_block"]:
        for q in Q:
            blob = " ".join([q["stem"], q.get("box") or ""] + (q.get("opts") or []))
            if w in blob:
                rep.add("범위", "%s 발문·선택지에 범위 밖 표현 '%s'" % (qlabel(q, prof), w))
    check_verify(rep, Q, prof)


# ── 점검 2: 조판 넘침 (브라우저로 실제 배치를 잰다) ─────────────
MEASURE = r"""() => {
  const out = [];
  document.querySelectorAll('.q, .sol').forEach((q) => {
    const r = q.getBoundingClientRect();
    const lab = (q.querySelector('.qn, b') || {}).textContent || '?';
    q.querySelectorAll('.katex, .katex-display, svg.fig, .op, table').forEach((e) => {
      const x = e.getBoundingClientRect();
      if (x.right > r.right + 1.5 || x.left < r.left - 1.5)
        out.push(lab.trim() + ' ' + (e.className.baseVal !== undefined ? 'svg 그림' : e.className) +
                 ' 이 단 밖으로 ' + Math.round(Math.max(x.right - r.right, r.left - x.left)) + 'px');
    });
  });
  document.querySelectorAll('.row').forEach((row) => {
    const ops = row.querySelectorAll('.op');
    if (ops.length && ops[ops.length - 1].getBoundingClientRect().top > ops[0].getBoundingClientRect().top + 2)
      out.push('선택지 한 줄 배치가 두 줄로 넘어감: ' + row.textContent.slice(0, 30));
  });
  return out;
}"""


def check_layout(rep, docs):
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as td, sync_playwright() as pw:
        br = R.launch(pw)
        pg = br.new_page(viewport={"width": 711, "height": 1000})     # A4 폭 - 좌우 여백 22mm ≈ 711px
        for where, doc in docs:
            h = pathlib.Path(td) / "m.html"
            h.write_text(doc, encoding="utf-8")
            pg.goto(h.as_uri())
            pg.emulate_media(media="print")
            pg.evaluate("document.fonts.ready.then(() => true)")
            for m in pg.evaluate(MEASURE):
                rep.add("조판", "%s %s" % (where, m))
            bad = pg.evaluate("[...document.fonts].filter(f => f.family.startsWith('KaTeX') && f.status === 'error')"
                              ".map(f => f.family)")
            if bad:
                rep.add("조판", "%s KaTeX 글꼴을 불러오지 못함 %s" % (where, sorted(set(bad))))
        br.close()


# ── 점검 3: PDF 실물 ────────────────────────────────────────
def check_pdfs(rep, Q, d, prof, stu_path, ans_path):
    import pymupdf
    with pymupdf.open(stu_path) as stu, pymupdf.open(ans_path) as ans:
        st = C.pdf_text(stu)
        at = re.sub(r"\s+", " ", C.pdf_text(ans))
        flat = re.sub(r"\s+", " ", st)
        for w in prof.get("student_absent", ["정답", "해설", "✔"]):
            if w in st:
                rep.add("학생용", "'%s' 노출" % w)
        for q in Q:
            lab = qlabel(q, prof)
            if ptxt(q, prof) not in flat:
                rep.add("학생용", "%s 배점 표시 누락" % lab)
            if not re.search(r"(^|\s)%s\s" % re.escape(lab), flat):
                rep.add("학생용", "%s 문항 번호 없음" % lab)
            if is_choice(q):
                if "%d. 정답 %s" % (q["n"], T.CIRC[q["ans"]]) not in at:
                    rep.add("답지", "%d번 해설 정답 표기 불일치" % q["n"])
            elif "%s 모범답안" % lab not in at:
                rep.add("답지", "%s 모범답안 없음" % lab)
        C.teacher_words(rep, "학생용", st, prof.get("student_forbidden", []))
        C.residue(rep, "학생용", st)
        for where, t in (("학생용", st), ("답지", at)):
            if "[수식 오류]" in t:
                rep.add("수식", "%s 에 [수식 오류]" % where)
            left = re.findall(r"\\[A-Za-z]{2,}|\$", t)
            if left:
                rep.add("수식", "%s 에 바뀌지 않은 TeX 잔재 %s" % (where, sorted(set(left))[:5]))
        for w in d["range_block"]:
            if w in st:
                rep.add("범위", "학생용에 범위 밖 표현 '%s'" % w)
        for where, doc in (("학생용", stu), ("답지", ans)):
            for i, pg in enumerate(doc):
                bottom = pg.rect.height - 12 * 72 / 25.4      # @page 아래 여백 12mm 위가 본문 끝
                for b in pg.get_text("dict")["blocks"]:
                    for ln in b.get("lines", []):
                        for sp in ln["spans"]:
                            if sp["font"].startswith("KaTeX") and sp["bbox"][3] > bottom + 2 and sp["text"].strip():
                                rep.add("조판", "%s %d쪽 아래 여백에 잘린 수식 조각 '%s'" % (where, i + 1, sp["text"]))
        C.pdf_physical(rep, "학생용", stu)
        C.pdf_physical(rep, "답지", ans)
        rep.note("학생용 %d쪽 · 답지 %d쪽" % (len(stu), len(ans)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", help="PDF를 둘 폴더 (기본: data.json 이 있는 폴더)")
    ap.add_argument("--html", action="store_true", help="조판 HTML도 남긴다")
    a = ap.parse_args()
    d, prof = load(a.data)
    Q = d["questions"]
    rep = C.Report("%s · 수학 시험지 점검" % d["name"])
    draw_figs(rep, Q)
    check_data(rep, Q, d, prof)

    tx = X.Tex(d["macros"])
    tx.collect(d["guide"], "안내문")
    for q in Q:
        for where, s in texts(q):
            tx.collect(dfrac_opts(s) if "선택지" in where else s, where)
    tx.run()
    for where, t, msg in tx.errors:
        rep.add("수식", "%s  %s  → %s" % (where, t[:60], msg[:160]))
    rep.stop_if_bad()                       # 수식 · 그림 · 검산 · 규격 결함이 있으면 여기서 멈춘다

    docs = [("학생용", page_html(Q, d, prof, tx)), ("답지", page_html(Q, d, prof, tx, answers=True))]
    check_layout(rep, docs)
    rep.stop_if_bad()

    stu_name = d["name"] + ".pdf"
    ans_name = d["name"] + prof.get("answer_suffix", "_답지") + ".pdf"
    jobs = [(docs[0][1], stu_name), (docs[1][1], ans_name)]

    def post(paths):
        check_pdfs(rep, Q, d, prof, paths[0], paths[1])
        return rep
    out = pathlib.Path(a.out) if a.out else pathlib.Path(a.data).resolve().parent
    final = R.render_checked(jobs, out, post, footer=R.footer_html(d["footer"]), keep_html=a.html)
    for f in final:
        print("저장", f)


if __name__ == "__main__":
    main()
