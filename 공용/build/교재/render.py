# -*- coding: utf-8 -*-
"""교재에 넣을 직접 출제 부분: data/*.json (README 「직접 출제」 형식) → <작업>/_parts/sec_<key>.pdf · ans_<key>.pdf (섹션마다).
쪽번호는 build.py 가 교재 전체에 찍는다. build.py 가 부른다 — 따로 돌릴 때는

    py 공용/build/교재/render.py <교재.json> <data.json>…

섹션 판형 (섹션 머리 칸):
  "layout": "exam"     시험지처럼 두 단 · 회(part)마다 새 쪽 · 머리 상자. "exam_sub" = 머리 상자 둘째 줄.
                       답지도 회마다 새 쪽, 맨 위 정답 번호표 → 그 아래 해설 (10/15 세종예고2 강사 지시)
  "layout": "compact"  판정표 칸을 줄여 한 쪽에 두 문제
  "newpage": true      part 마다 새 쪽에서 시작 (exam 은 늘 새 쪽)
"""
import json, re, html, pathlib, sys
from playwright.sync_api import sync_playwright

TITLE, SHORT, PARTS = "", "", None                     # run() 이 교재.json 에서 채운다
CIR = "①②③④⑤⑥⑦⑧⑨⑩"


def is_exam(sec): return sec.get("layout") == "exam"
def is_compact(sec): return sec.get("layout") == "compact"
def is_newpage(sec): return sec.get("newpage") or is_exam(sec)

CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:"Malgun Gothic","맑은 고딕",sans-serif;color:#1f2633;font-size:10pt;line-height:1.55;
     -webkit-print-color-adjust:exact;print-color-adjust:exact}
.top{font-size:7.6pt;color:#6b7486;border-bottom:.6pt solid #c9d1de;padding-bottom:1mm;margin-bottom:3mm}
h1{font-size:15pt;margin:0 0 1mm;color:#233a5e}
.intro{font-size:9pt;color:#3c4656;background:#f1f4f9;border-radius:1.4mm;padding:2mm 3mm;margin:0 0 3mm;line-height:1.6}
h2{font-size:11pt;margin:4mm 0 2mm;color:#fff;background:#233a5e;padding:1mm 3mm;border-radius:1.2mm;break-after:avoid}
.part.np{break-before:page}
.note{font-size:8.6pt;color:#4a5465;margin:-1mm 0 2mm}
.prob{break-inside:avoid;margin:0 0 4.5mm}
.q{font-weight:700;margin-bottom:1.2mm}
.q .n{color:#233a5e;margin-right:1.2mm}
.head{font-weight:700;margin:1mm 0 1.2mm;color:#233a5e}
.psg{font-family:"Times New Roman","Malgun Gothic",serif;font-size:11pt;line-height:1.75;border:.7pt solid #9aa7bd;
     border-radius:1.2mm;padding:2.2mm 3.2mm;margin:0 0 2mm;text-align:justify}
.psg p{margin:0 0 1.2mm}.psg p:last-child{margin:0}
.box{font-family:"Times New Roman","Malgun Gothic",serif;font-size:10.8pt;border:1pt solid #233a5e;padding:2mm 3mm;margin:0 0 2mm;
     border-radius:1mm;background:#fbfcfe}
u{text-decoration:underline;text-underline-offset:2px}
.lab{font-family:"Malgun Gothic",sans-serif;font-size:9.4pt;margin-right:.3mm}
.sn{font-family:"Malgun Gothic",sans-serif;font-size:6.6pt;color:#8a94a6;vertical-align:super;margin-right:.6mm}
.blank{display:inline-block;width:30mm;border-bottom:.8pt solid #1f2633;height:1em}
.ch{margin:0;padding:0;list-style:none}
.ch li{display:flex;gap:1.6mm;margin:.4mm 0;align-items:baseline}
.ch li .t{flex:1}
.ch.row{display:flex;flex-wrap:wrap;gap:1mm 7mm}.ch.row li .t{flex:none}
.ch .tag{flex:0 0 30mm;border-bottom:.6pt solid #9aa7bd;font-size:7.4pt;color:#9aa7bd;text-align:left;height:1.3em}
.en{font-family:"Times New Roman","Malgun Gothic",serif;font-size:10.6pt}
table.j{width:100%;border-collapse:collapse;font-size:8.6pt;margin-top:1.4mm}
table.j th{background:#e9eef6;color:#233a5e;font-weight:700;border:.6pt solid #9aa7bd;padding:.8mm 1.4mm;white-space:nowrap}
table.j td{border:.6pt solid #9aa7bd;height:7.2mm;padding:.6mm 1.4mm}
table.j td.k{width:11mm;text-align:center;font-size:10pt}
table.j td.ox{width:13mm}table.j td.fx{width:38mm}
.lines div{border-bottom:.6pt solid #9aa7bd;height:7.5mm}
table.v{width:100%;border-collapse:collapse;font-size:9.2pt}
table.v td,table.v th{border-bottom:.6pt solid #d3dae5;padding:1mm 1.4mm;vertical-align:top}
table.v th{font-size:8pt;color:#4a5465;text-align:left;border-bottom:1pt solid #233a5e;white-space:nowrap}
table.v td.w{font-family:"Times New Roman",serif;font-size:10.6pt;font-weight:700;white-space:nowrap}
table.v td.s{font-size:7.6pt;color:#8a94a6}
/* 답지 */
.a{break-inside:avoid;margin:0 0 2.2mm;font-size:9pt;line-height:1.5}
.a .an{font-weight:700;color:#c4561f;margin-right:1.4mm}
.a table{border-collapse:collapse;margin:.8mm 0 0 4mm;font-size:8.4pt}
.a td{border:.5pt solid #c9d1de;padding:.4mm 1.4mm;vertical-align:top}
.a .x{color:#c4561f;font-weight:700}.a .o{color:#1d5fbf;font-weight:700}
.cols{columns:2;column-gap:7mm}
table.grid{border-collapse:collapse;margin:1mm 0 4mm;width:100%;table-layout:fixed}table.grid td{border:.7pt solid #9aa7bd;text-align:center;padding:1.6mm .5mm;font-size:12pt}
table.grid .qn{display:block;font-size:7.6pt;color:#6b7486;margin-bottom:.4mm}table.grid b{color:#c4561f}
.solh{font-size:9.6pt;font-weight:800;color:#233a5e;border-bottom:.8pt solid #233a5e;margin:0 0 2mm;padding-bottom:.6mm}
"""


EXCSS = """
.exam .xh{border:1.2pt solid #111;padding:2.2mm 3mm;margin:0 0 3.5mm 0}
.exam .xh .t1{font-size:13.5pt;font-weight:700;text-align:center;color:#111}
.exam .xh .t2{font-size:9pt;text-align:center;margin-top:.8mm;color:#333}
.exam .xh .hb{display:flex;gap:3mm;margin-top:2mm;font-size:9.2pt;border-top:.6pt solid #999;padding-top:1.6mm}
.exam .xh .hb span{flex:1}
.exam .head{font-size:9.3pt;color:#111;break-after:avoid}
.psg,.box{break-inside:avoid;page-break-inside:avoid}   /* 지문은 단 · 쪽 경계에서 자르지 않는다 (공용/build/모의고사 와 같음, 10/15 강사 지적) */
.exam .prob .prob{margin-bottom:3.2mm}
.exam table.j{font-size:7.8pt;margin-top:1mm}.exam table.j th{padding:.5mm .8mm}.exam table.j td{height:5.4mm;padding:.3mm .8mm}
.exam table.j td.k{width:7mm;font-size:9pt}.exam table.j td.ox{width:10mm}.exam table.j td.fx{width:22mm}
.compact .psg{font-size:10.6pt;line-height:1.6;padding:1.8mm 2.8mm;margin-bottom:1.4mm}
.compact .prob{margin-bottom:3.4mm}
.compact h2{margin:2.4mm 0 1.6mm}
.compact table.j{font-size:8pt;margin-top:1mm}.compact table.j th{padding:.4mm 1mm}
.compact table.j td{height:5.6mm;padding:.2mm 1mm}.compact table.j td.k{width:9mm;font-size:9pt}
.compact table.j td.ox{width:11mm}.compact table.j td.fx{width:34mm}
.exam .cols{column-count:2;column-gap:7mm;column-rule:.5pt solid #bbb}
.exam .prob{break-inside:avoid;margin:0 0 4mm}
.prob.sel{break-inside:auto}.qp{break-inside:avoid}                              /* 「있는 대로」는 길어서 통째로 밀면 빈 쪽이 생긴다 — 지문 · 보기 상자 · 판정표는 각각 자르지 않는다 */
table.j.s{break-inside:avoid}table.j.s td{height:5.6mm}.exam table.j.s td{height:4.8mm}
.exam .q{font-size:9.3pt}
.exam .psg{font-size:10pt;line-height:1.62;border:.7pt solid #777;border-radius:0;padding:2mm 2.4mm;text-align:left}
.exam .box{font-size:9.8pt;border:.6pt solid #777;border-radius:0;background:#fff;padding:1.6mm 2.2mm}
.exam .ch li{margin:.3mm 0}
.exam .ch .t{font-size:9.8pt}
.exam .ch.row{gap:.6mm 5mm}
.exam .ch .tag{flex:0 0 13mm;font-size:0}.exam .ch .tag::before{content:'근거';font-size:6.8pt}
"""


def mk(s):
    """출제지침 표기 → HTML"""
    s = html.escape(s or "", quote=False)
    s = re.sub(r"\{([^|{}]+)\|([^{}]+)\}", lambda m: ("" if m[1] == "_" else f"<span class='lab'>{m[1]}</span>") + f"<u>{m[2]}</u>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[(\d{2})\]\s*", r"<span class='sn'>\1</span>", s)
    s = re.sub(r"_{5,}", "<span class='blank'></span>", s)
    return s


def para(s):
    return "".join(f"<p>{mk(x)}</p>" for x in (s or "").split("\n") if x.strip())


def choices(p):
    tag = p.get("tag")
    lis = []
    for i, c in enumerate(p["choices"]):
        t = f"<span class='tag'>{html.escape(tag)}</span>" if tag else ""
        if c.strip() == CIR[i]:                          # 선택지가 번호 그 자체(밑줄 ①~⑤ 고르기)면 한 번만 — '① ①' 이중 표기 방지
            lis.append(f"<li><span>{CIR[i]}</span>{t}</li>"); continue
        lis.append(f"<li><span>{CIR[i]}</span><span class='t {'en' if re.search(r'[A-Za-z]{3}', c) and not re.search(r'[가-힣]', c) else ''}'>{mk(c)}</span>{t}</li>")
    row = " row" if (not tag and max(len(c) for c in p["choices"]) <= 16) else ""
    return f"<ul class='ch{row}'>{''.join(lis)}</ul>"


def judge_table(p):
    rows = "".join(f"<tr><td class='k'>{it['k']}</td><td class='ox'></td><td class='fx'></td><td></td></tr>" for it in p["items"])
    return f"<table class='j'><tr><th>기호</th><th>O / X</th><th>X → 고칠 형태</th><th>판단 근거 (어법 규칙)</th></tr>{rows}</table>"


def select_html(p):
    """「있는 대로」 고르기 — 보기 상자 + 판정표(기호 · O/X · 근거 문장 번호 / 틀린 낱말) + 답 칸 (한솔고2 10/16)"""
    talk = re.compile(r"^(학생|Student)\s*[A-Z]\s*:")                # 학생 대화형 — t 가 「학생 A: …」로 시작하면 기호를 따로 붙이지 않는다
    box = "".join(f"<p>{mk(it['t'])}</p>" if talk.match(it["t"]) else f"<p><b>{html.escape(it['k'])}.</b> {mk(it['t'])}</p>" for it in p["items"])
    rows = "".join(f"<tr><td class='k'>{html.escape(it['k'])}</td><td class='ox'></td><td></td></tr>" for it in p["items"])
    return (f"<div class='box'>{box}</div>"
            f"<table class='j s'><tr><th>기호</th><th>O / X</th><th>O → 근거 문장 번호 · X → 틀린 낱말</th></tr>{rows}</table>"
            f"<div style='margin-top:1.6mm;font-weight:700'>답: (<span style='display:inline-block;width:60mm'></span>)</div>")


def vocab_table(p):
    rows = "".join(f"<tr><td style='width:5mm;color:#9aa7bd'>□</td><td class='w'>{html.escape(r['w'])}</td><td style='width:7mm;color:#6b7486;font-size:8pt'>{r.get('pos','')}</td>"
                   f"<td style='width:34mm'>{html.escape(r['m'])}</td><td class='en'>{html.escape(r.get('pair',''))}</td><td class='s'>{html.escape(r.get('src',''))}</td></tr>"
                   for r in p["rows"])
    return f"<table class='v'><tr><th></th><th>선택지 어휘</th><th></th><th>뜻</th><th>본문 속 짝</th><th>나온 곳</th></tr>{rows}</table>"


def prob_html(p, n):
    """문항 하나 → (html, 다음 번호)"""
    k = p["kind"]
    if k == "bundle":
        a = n; b = n + len(p["problems"]) - 1
        h = f"<div class='prob' style='break-inside:auto'><div class='head'>[{a}~{b}] {mk(p.get('head','다음 글을 읽고 물음에 답하시오.'))}</div><div class='psg'>{para(p['passage'])}</div>"
        for sp in p["problems"]:
            x, n = prob_html(sp, n)
            h += x
        return h + "</div>", n
    if k == "vocab":
        return f"<div class='prob' style='break-inside:auto'>{vocab_table(p)}</div>", n
    cls = "prob sel" if k == "select" else "prob"
    h = f"<div class='{cls}'>"
    qh = f"<div class='q'><span class='n'>{n}.</span>{mk(p.get('q',''))}</div>"
    bx = f"<div class='box'>{para(p['box'])}</div>" if p.get("box") else ""
    first = bx if p.get("box_first") else (f"<div class='psg'>{para(p['passage'])}</div>" if p.get("passage") else "")
    h += f"<div class='qp'>{qh}{first}</div>"            # 발문이 단 · 쪽 끝에 혼자 남지 않게 첫 덩어리와 묶는다
    if p.get("box_first"):                               # 순서배열의 주어진 글처럼 지문 앞에 오는 상자 (한솔고2 10/16)
        if p.get("passage"): h += f"<div class='psg'>{para(p['passage'])}</div>"
    elif bx: h += bx
    if k == "mcq" or (k == "judge" and p.get("choices")): h += choices(p)
    if k == "judge": h += judge_table(p)
    if k == "write": h += "<div class='lines'>" + "<div></div>" * int(p.get("lines", 2)) + "</div>"
    if k == "select": h += select_html(p)
    return h + "</div>", n + 1


def ans_html(p, n):
    k = p["kind"]
    if k == "bundle":
        h = ""
        for sp in p["problems"]:
            x, n = ans_html(sp, n); h += x
        return h, n
    if k == "vocab":
        return "", n
    h = f"<div class='a'><span class='an'>{n}.</span>"
    if k == "mcq" or (k == "judge" and p.get("choices")):
        h += f"<b>{CIR[p['answer'] - 1]}</b> "
    if k == "write":
        h += f"<b>예시 답</b> {mk(p['answer'])} "
    if k == "select":
        h += f"<b>{html.escape(p['answer'])}</b> "
    h += mk(p.get("explain", "")) + f" <span style='color:#8a94a6'>({html.escape(p.get('src',''))})</span>"
    if p.get("tags"):
        h += "<br><span style='color:#4a5465'>" + html.escape(p.get("tag", "")) + ":</span> " + " · ".join(f"{CIR[i]} {html.escape(t)}" for i, t in enumerate(p["tags"]))
    if k == "select":
        rows = "".join(f"<tr><td>{html.escape(it['k'])}</td><td class='{'o' if it['ok'] else 'x'}'>{'O' if it['ok'] else 'X'}</td><td>{mk(it.get('why',''))}</td></tr>" for it in p["items"])
        h += f"<table>{rows}</table>"
    if k == "judge":
        rows = "".join(
            f"<tr><td>{it['k']}</td><td class='{'o' if it['ok'] else 'x'}'>{'O' if it['ok'] else 'X'}</td>"
            f"<td class='en'>{html.escape(it.get('fix','') or '')}</td><td>{mk(it.get('why',''))}{' <b>(원문과 다르지만 옳음)</b>' if it.get('variant') else ''}</td></tr>"
            for it in p["items"])
        h += f"<table>{rows}</table>"
    return h + "</div>", n + 1


def render(sec, ans=False):
    out = [f"<div class='top'>{TITLE}{' · 답지' if ans else ''}</div><h1>{html.escape(sec['title'])}</h1>"]
    if sec.get("intro") and not ans: out.append("<div class='intro'>" + "<br>".join(mk(x) for x in sec["intro"].split("\n")) + "</div>")
    for i, part in enumerate(sec["parts"]):
        # 시험형 회차의 답지는 회마다 새 쪽 — 앞 회 답을 보다가 다음 회 답이 눈에 들어오지 않게 (10/15 강사 지시)
        np_ = " np" if (is_newpage(sec) and i > 0 and (not ans or is_exam(sec))) else ""
        ex = is_exam(sec) and not ans
        if ans and is_exam(sec):                         # 맨 위에 정답 번호만 → 그 아래 해설 (채점용)
            flat, k = [], part.get("start", 1)
            for p in part["problems"]:
                for q in (p["problems"] if p["kind"] == "bundle" else [p]):
                    a_ = q.get("answer")
                    flat.append((k, CIR[a_ - 1] if isinstance(a_, int) else (html.escape(a_) if q["kind"] == "select" else "—"))); k += 1
            cells = "".join(f"<td><span class='qn'>{n}</span><b>{a}</b></td>" for n, a in flat)
            out.append(f"<div class='part{np_}'><h2>{html.escape(part['title'])} 정답</h2><table class='grid'><tr>{cells}</tr></table>"
                       f"<div class='solh'>해설</div>")
            n = part.get("start", 1)
            for p in part["problems"]:
                x, n = ans_html(p, n); out.append(x)
            out.append("</div>")
            continue
        if ex:
            cnt = sum(len(p["problems"]) if p["kind"] == "bundle" else 1 for p in part["problems"])
            out.append(f"<div class='part{np_}'><div class='xh'><div class='t1'>{html.escape(part['title'])}</div>"
                       f"<div class='t2'>{SHORT} · {sec['exam_sub']} · {cnt}문항</div>"
                       f"<div class='hb'><span>이름</span><span>점수 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;/ {cnt}</span></div></div>")
            if part.get("note"): out.append(f"<div class='note'>{mk(part['note'])}</div>")
            out.append("<div class='cols'>")
        else:
            out.append(f"<div class='part{np_}'><h2>{html.escape(part['title'])}</h2>")
            if part.get("note") and not ans: out.append(f"<div class='note'>{mk(part['note'])}</div>")
        n = part.get("start", 1)                          # 나눠 실은 part 는 원래 번호부터 (한솔고2 10/16)
        for p in part["problems"]:
            x, n = (ans_html if ans else prob_html)(p, n)
            out.append(x)
        out.append("</div></div>" if ex else "</div>")
    body = "".join(out)
    if ans: body = body.replace("<h2>", "<h2 style='font-size:9.6pt;margin:2.4mm 0 1.4mm'>")
    cls = " class='exam'" if (is_exam(sec) and not ans) else (" class='compact'" if (is_compact(sec) and not ans) else "")
    return f"<!doctype html><meta charset='utf-8'><style>{CSS}{EXCSS}</style><body{cls}>{body}</body>"


def to_pdf(htmls):
    PARTS.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page()
        for name, h in htmls:
            tmp = PARTS / f"_{name}.html"; tmp.write_text(h, encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.pdf(path=str(PARTS / f"{name}.pdf"), format="A4", print_background=True,
                   margin={"top": "12mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
            tmp.unlink()
            import pymupdf
            print("  ", name, pymupdf.open(PARTS / f"{name}.pdf").page_count, "쪽")
        b.close()


def run(cfg, parts, files):
    """cfg = 교재.json 내용 · parts = _parts 폴더 · files = data json 경로들."""
    global TITLE, SHORT, PARTS
    TITLE, SHORT, PARTS = cfg["title"], cfg["short"], pathlib.Path(parts)
    jobs = []
    for f in files:
        for sec in json.loads(pathlib.Path(f).read_text(encoding="utf-8"))["sections"]:
            if is_exam(sec) and not sec.get("exam_sub"): raise ValueError(f"섹션 {sec['key']}: layout exam 에는 exam_sub 가 있어야 한다")
            jobs += [(f"sec_{sec['key']}", render(sec)), (f"ans_{sec['key']}", render(sec, ans=True))]
    to_pdf(jobs)


if __name__ == "__main__":
    cf = pathlib.Path(sys.argv[1]).resolve()
    cfg = json.loads(cf.read_text(encoding="utf-8"))
    run(cfg, cf.parent / "_parts", sys.argv[2:])
