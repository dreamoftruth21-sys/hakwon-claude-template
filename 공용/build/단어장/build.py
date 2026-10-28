# -*- coding: utf-8 -*-
"""단어장 빌더 — 지문(단원)별 표: 번호 | 단어 | 우리말 뜻 | (덧붙일 열: 혼동어·유의어·반의어 …)

사용: py 공용/build/단어장/build.py <data.json> [--out 폴더]
  - 데이터 형식은 같은 폴더 README.md
  - 점검(데이터 → 원문 근거 → 지면 넘침 → PDF 실물)에 하나라도 걸리면 PDF를 내보내지 않는다
기준 구현: 세종예고1/…/9월학평_단어장 (build.py·chk.py)
"""
import argparse
import html
import json
import pathlib
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import brand  # noqa: E402
from core import checks as C  # noqa: E402
from core import render as R  # noqa: E402
from core import sources as S  # noqa: E402
from core import text as T  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Malgun Gothic','Noto Sans KR',sans-serif; color: #12212f; }
.page { width: 210mm; height: 297mm; padding: 15mm 12mm 0 12mm; position: relative; }
.top { display:flex; justify-content:space-between; align-items:center; }
.src { border:1px solid %(c)s; border-radius:4px; padding:3mm 4mm; font-size:8.6pt; font-weight:700; color:%(c)s; }
.grade { background:%(c)s; color:#fff; font-size:8pt; font-weight:700; border-radius:3px; padding:2.2mm 3mm; }
h1 { margin-top:5mm; font-size:13pt; font-weight:700; color:%(c)s; }
h1 span { font-size:9pt; font-weight:400; color:#5d6470; margin-left:2.5mm; }
.sec { margin-top:4.5mm; border-left:1.1mm solid %(c)s; padding-left:2.5mm; font-size:10.5pt; font-weight:700; line-height:5.6mm; }
.sec em { font-style:normal; font-size:8.6pt; font-weight:400; color:#5d6470; margin-left:3mm; }
table { margin-top:2mm; width:186mm; border-collapse:collapse; table-layout:fixed; }
%(cols)s
th { background:#eef2f7; font-size:8.2pt; font-weight:700; text-align:left; padding:0 1.6mm; height:7mm;
     border-top:0.26mm solid #9fb0c4; border-bottom:0.26mm solid #9fb0c4; }
td { font-size:8.5pt; padding:0.8mm 1.6mm; height:7.1mm; border-bottom:0.26mm solid #dde3ea; vertical-align:middle; line-height:1.2; }
td.no{color:#7b8291;} td.w{font-weight:700;}
td.c{font-size:7.3pt;color:#8a6a3a;white-space:nowrap;}
.L{border-right:0.26mm solid #dde3ea;}
.foot{position:absolute;bottom:8mm;left:0;right:0;text-align:center;font-size:8pt;color:#7b8291;}
"""

# 열 너비(mm). layout "half" = 좌우 두 표(각 93mm), "full" = 한 표(186mm). 덧붙일 열 수에 따라 고른다.
WIDTHS = {
    "half": {0: (7, 43, 43, []), 1: (7, 31, 32, [23]), 2: (7, 26, 26, [17, 17])},
    "full": {0: (8, 70, 108, []), 1: (8, 50, 70, [58]), 2: (8, 42, 52, [42, 42])},
}

LAYOUT_JS = """(() => {
  const ts=[...document.querySelectorAll('table')];
  const last=ts[ts.length-1].getBoundingClientRect();
  const f=document.querySelector('.foot').getBoundingClientRect();
  const g=document.querySelector('.grade').getBoundingClientRect();
  const wide=ts.some(t=>t.getBoundingClientRect().right > g.right + 1);
  const ov=[...document.querySelectorAll('td.c, td.w')].filter(d=>d.scrollWidth > d.clientWidth + 1).map(d=>d.textContent);
  const tds=[...document.querySelectorAll('tr')].flatMap(r=>[...r.children]).filter(c=>!c.className);
  const h=Math.min(...tds.map(c=>c.getBoundingClientRect().height));
  const wrap2=tds.filter(c=>c.getBoundingClientRect().height > h*1.6).map(c=>c.textContent);
  return [last.bottom > f.top - 6, wide, ov, wrap2];
})()"""


def is_phrase(x):
    return " " in x or "~" in x


def load(p):
    d = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    if d.get("layout") == "book":
        for k in ("name", "title", "parts"):
            if k not in d:
                raise SystemExit("data.json 에 '%s' 가 없다" % k)
        d.setdefault("namebar", brand.name(p))      # 이름 칸 왼쪽의 학원 표기 — 반 CLAUDE.md → 우리학원.md
        prof =S.profile(d["school"]).get("wordlist", {}) if d.get("school") else {}
        return d, prof
    for k in ("name", "source_label", "grade_label", "title", "footer", "sections"):
        if k not in d:
            raise SystemExit("data.json 에 '%s' 가 없다" % k)
    d.setdefault("color", "#1F4E79")
    d.setdefault("title_sub", "")
    d.setdefault("columns", [])
    d.setdefault("layout", "half")
    d.setdefault("key_suffix", "번")
    if d["layout"] not in WIDTHS:
        raise SystemExit("layout 은 half / full")
    if len(d["columns"]) not in WIDTHS[d["layout"]]:
        raise SystemExit("덧붙일 열은 2개까지다")
    prof = S.profile(d["school"]).get("wordlist", {}) if d.get("school") else {}
    return d, prof


# ── 점검 1: 데이터 ──────────────────────────────────────────
def check_data(rep, d):
    keys = [s["key"] for s in d["sections"]]
    if d.get("range") is not None:
        extra = [k for k in keys if k not in d["range"]]
        miss = [k for k in d["range"] if k not in keys]
        if extra:
            rep.add("범위이탈", "범위 밖 지문 %s" % extra)
        if miss:
            rep.add("범위", "범위인데 빠진 지문 %s" % miss)
    if len(set(keys)) != len(keys):
        rep.add("구성", "지문 키 중복")
    per = d.get("per_section")
    for s in d["sections"]:
        if s.get("source_page"):
            sp = s["source_page"]
            if s.get("items"):
                rep.add("구성", "%s번 원본 쪽을 끼우는 섹션에 items 가 있음 — 둘 중 하나만" % s["key"])
            if not S.path(sp["file"]).exists():
                rep.add("원본", "%s번 원본 파일 없음: %s" % (s["key"], sp["file"]))
            continue
        ws = [i["w"].lower() for i in s["items"]]
        dup = sorted({w for w in ws if ws.count(w) > 1})
        if dup:
            rep.add("중복", "%s번 표제어 중복 %s" % (s["key"], dup))
        if per and len(ws) != per:
            rep.add("개수", "%s번 %d개 — %d개여야 함" % (s["key"], len(ws), per))
        for i in s["items"]:
            if not i.get("m", "").strip():
                rep.add("뜻", "%s번 '%s' 뜻 없음" % (s["key"], i["w"]))
            for col in d["columns"]:
                v = i.get(col["key"], "")
                if v and v.lower() == i["w"].lower():
                    rep.add(col["label"], "%s번 '%s' 의 %s 이 자기 자신" % (s["key"], i["w"], col["label"]))
    pages = d.get("per_page")
    if isinstance(pages, list) and sum(pages) != len(d["sections"]):
        rep.add("구성", "쪽 배분 합 %d ≠ 지문 %d개" % (sum(pages), len(d["sections"])))


def check_grounding(rep, d):
    """표제어가 실제 그 지문에 쓰였는지 (grounding 이 있을 때)."""
    g = d.get("grounding")
    if not g:
        rep.note("원문 근거 대조 없음 (grounding 미지정)")
        return
    nums = [s.get("src", s["key"]) for s in d["sections"] if not s.get("source_page")]
    texts = S.bynum(g["bynum"], g["round"], nums)
    for s in d["sections"]:
        if s.get("source_page"):
            continue
        body = set(re.findall(r"[a-z]+", texts[s.get("src", s["key"])].lower()))
        for i in s["items"]:
            w = i["w"]
            ok = T.phrase_in_text(w, body) if is_phrase(w) else T.word_in_text(w, body)
            if not ok:
                rep.add("근거", "%s번 '%s' 가 그 지문 원문에 없음" % (s["key"], w))


# ── 조판 ────────────────────────────────────────────────────
def css(d):
    no, w, m, extra = WIDTHS[d["layout"]][len(d["columns"])]
    cols = "col.no{width:%dmm;} col.w{width:%dmm;} col.m{width:%dmm;}" % (no, w, m)
    cols += "".join(" col.c%d{width:%dmm;}" % (k, x) for k, x in enumerate(extra))
    return CSS % {"c": d["color"], "cols": cols}


def section_html(d, s):
    cols = d["columns"]
    items = s["items"]
    full = d["layout"] == "full"
    half = len(items) if full else (len(items) + 1) // 2
    colgroup = ('<col class="no"><col class="w"><col class="m">' +
                "".join('<col class="c%d">' % k for k in range(len(cols)))) * (1 if full else 2)
    head = []
    for side in (("",) if full else ("L", "")):
        cells = ['<th colspan="2">단어</th>']
        labels = ["우리말 뜻"] + [c["label"] for c in cols]
        for j, lab in enumerate(labels):
            last = j == len(labels) - 1
            cells.append('<th%s>%s</th>' % (' class="L"' if last and side else "", lab))
        head.append("".join(cells))
    rows = []
    for r in range(half):
        cells = []
        for j, side in (((r, ""),) if full else ((r, "L"), (r + half, ""))):
            n_extra = len(cols)
            if j < len(items):
                it = items[j]
                c = ['<td class="no">%d.</td><td class="w">%s</td>' % (j + 1, html.escape(it["w"]))]
                if n_extra:
                    c.append("<td>%s</td>" % html.escape(it["m"]))
                    for k, col in enumerate(cols):
                        v = it.get(col["key"], "")
                        v = (col.get("prefix", "") + v) if v else ""
                        last = k == n_extra - 1
                        c.append('<td class="c %s">%s</td>' % (side if last else "", html.escape(v)))
                else:
                    c.append('<td class="%s">%s</td>' % (side, html.escape(it["m"])))
                cells.append("".join(c))
            else:
                blanks = ["<td></td>"] * n_extra
                cells.append('<td class="no"></td><td></td>' + ("<td></td>" + "".join(blanks[:-1]) +
                             '<td class="%s"></td>' % side if n_extra else '<td class="%s"></td>' % side))
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return ('<div class="sec">%s%s <em>%s</em></div>\n<table><colgroup>%s</colgroup>\n<tr>%s</tr>\n%s\n</table>'
            % (html.escape(s["key"]), d["key_suffix"], html.escape(s.get("title", "")), colgroup, "\n    ".join(head),
               "".join(rows)))


def page_html(d, group, pageno):
    return ('<div class="page">\n<div class="top"><div class="src">%s</div><div class="grade">%s</div></div>\n'
            '<h1>%s<span>%s</span></h1>\n%s\n<div class="foot">%s &nbsp;&nbsp;-&nbsp;%d&nbsp;-</div>\n</div>'
            % (d["source_label"], d["grade_label"], d["title"], d["title_sub"],
               "".join(section_html(d, s) for s in group), d["footer"], pageno))


def groups(d):
    per = d.get("per_page", 1)
    secs = d["sections"]
    split = per if isinstance(per, list) else [per] * ((len(secs) + per - 1) // per)
    out, k = [], 0
    for c in split:
        out.append(secs[k:k + c])
        k += c
    return out


# ── 점검 2: PDF 실물 ────────────────────────────────────────
def check_pdf(rep, d, prof, pdf, inserted=()):
    """inserted: 원본 교재에서 그대로 끼운 쪽 번호(0부터) — 멘트·표현 점검에서 뺀다 (출판사 글이다)"""
    import pymupdf
    with pymupdf.open(pdf) as doc:
        txt = C.pdf_text(doc)
        own = "\n".join(p.get_text() for i, p in enumerate(doc) if i not in inserted)
        for s in d["sections"]:
            if s.get("source_page"):
                continue
            for i in s["items"]:
                pat = re.escape(i["w"]).replace(r"\ ", r"\s+")
                if not re.search(pat, txt):
                    rep.add("PDF", "%s번 '%s' 가 지면에 없음" % (s["key"], i["w"]))
            if not re.search(re.escape(s["key"] + d["key_suffix"]), txt):
                rep.add("PDF", "%s번 섹션 머리가 없음" % s["key"])
        C.teacher_words(rep, "지면", own)
        C.jari(rep, "지면", own)
        C.residue(rep, "지면", own)
        for w in prof.get("excluded_labels", []):
            if w in own:
                rep.add("제외유형", "지면에 '%s'" % w)
        C.pdf_physical(rep, "단어장", doc, page_numbers=False)
        if inserted:
            rep.note("원본 교재 쪽 %d개를 그대로 끼움 (%s쪽)" % (len(inserted), ", ".join(str(i + 1) for i in inserted)))
        rep.note("%d쪽 · 지문 %d개 · 표제어 %d개" % (len(doc), len(d["sections"]),
                                                sum(len(s["items"]) for s in d["sections"])))


# ── 책 형태 (한솔고2 단어장 2권 판형: PART · 목차 · 연속 흐름) ──────────
BOOK_CSS = r"""
@page{size:A4;margin:15mm 13mm 14mm 13mm}
*{box-sizing:border-box}
body{font-family:"Noto Sans KR","Malgun Gothic",sans-serif;font-size:9.4pt;line-height:1.55;color:#16181d;margin:0}
h1{font-size:16pt;color:#12212f;margin:0 0 1.5mm 0;letter-spacing:-.02em}
.sub{font-size:9pt;color:#5d6470;margin:0 0 4mm 0}
.namebar{border:.8pt solid #12212f;border-radius:1mm;padding:2mm 3mm;font-size:9.3pt;margin:0 0 6mm 0;
 background:#f7f9fc;display:flex;justify-content:space-between}
h2{font-size:12pt;color:#fff;background:#12212f;margin:0 0 3.5mm 0;padding:2mm 3mm;border-radius:1mm;
 break-after:avoid;page-break-after:avoid}
h3{font-size:10.2pt;color:#12212f;margin:4.5mm 0 1.6mm 0;padding-left:2.4mm;border-left:3pt solid #e8a33d;
 break-after:avoid;page-break-after:avoid}
table{width:100%;table-layout:fixed;border-collapse:collapse;margin:1.4mm 0 2.5mm 0;font-size:8.9pt}
th{background:#e9edf3;color:#12212f;font-weight:700;text-align:left;border:.6pt solid #aeb6c3;padding:1.1mm 1.6mm;font-size:8.4pt}
td{border:.6pt solid #ccd2dc;padding:1.15mm 1.6mm;vertical-align:top;word-break:keep-all}
tbody tr:nth-child(even) td{background:#fafbfd}
tr{break-inside:avoid;page-break-inside:avoid}
.en{font-weight:600;color:#12212f}
.sy{color:#1c4d8f}
.an{color:#b34a10}
.pb{page-break-before:always}
.foot{margin-top:6mm;padding-top:2mm;border-top:.6pt solid #d5dae2;font-size:7.8pt;color:#7b8291}
.toc{background:#f4f7fb;border:.7pt solid #cfd8e4;border-radius:1mm;padding:3mm 3.6mm;margin:0 0 5mm 0;font-size:9.2pt}
.toc b{color:#12212f}
.toc ol{margin:1.5mm 0 0 0;padding-left:5mm}
.toc li{margin:.6mm 0}
.note{background:#fff8ec;border:.7pt solid #e8c98d;border-radius:1mm;padding:2.6mm 3.2mm;margin:0 0 5mm 0;font-size:8.7pt}
.note b{color:#8a5a12}
"""
BOOK_FOOT = ('<div style="width:100%;font-size:7.3pt;color:#9aa0ad;font-family:sans-serif;text-align:center;">'
             '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')


def book_html(d):
    E = lambda s: html.escape(s or "")

    def wtab(rows):
        o = ['<table><colgroup><col style="width:22%"><col style="width:28%">'
             '<col style="width:22%"><col style="width:28%"></colgroup>'
             '<thead><tr><th>단어</th><th>뜻</th><th>단어</th><th>뜻</th></tr></thead><tbody>']
        half = (len(rows) + 1) // 2
        L, Rr = rows[:half], rows[half:]
        for i in range(half):
            a, b = L[i], (Rr[i] if i < len(Rr) else None)
            c = ('<td class="en">%s</td><td>%s</td>' % (E(b["w"]), E(b["m"]))) if b else '<td></td><td></td>'
            o.append('<tr><td class="en">%s</td><td>%s</td>%s</tr>' % (E(a["w"]), E(a["m"]), c))
        o.append("</tbody></table>")
        return "".join(o)

    def stab(rows):
        o = ['<table><colgroup><col style="width:17%"><col style="width:20%"><col style="width:33%"><col style="width:30%">'
             '</colgroup><thead><tr><th>단어</th><th>뜻</th><th>유의어</th><th>반의어</th></tr></thead><tbody>']
        for x in rows:
            o.append('<tr><td class="en">%s</td><td>%s</td><td class="sy">%s</td><td class="an">%s</td></tr>'
                     % (E(x["w"]), E(x["m"]), E(x.get("syn")) or "–", E(x.get("ant")) or "–"))
        o.append("</tbody></table>")
        return "".join(o)

    def h3(title, n):
        return ('<h3>%s <span style="font-weight:400;color:#7b8291;font-size:8.6pt">(%d개)</span></h3>' % (E(title), n))

    def part_body(part, kind):
        out = []
        for g in part["groups"]:
            if kind == "w":
                out.append(h3(g["title"], len(g["items"])))
                out.append(wtab(g["items"]))
            else:
                rows = [x for x in g["items"] if x.get("syn") or x.get("ant")]
                if rows:
                    out.append(h3(g["title"], len(rows)))
                    out.append(stab(rows))
        return "".join(out)
    raw = []
    for part in d["parts"]:
        raw.append((part["title"] + " – 단어", part_body(part, "w")))
        if d.get("syn"):
            raw.append((part["title"] + " – 유의어 · 반의어", part_body(part, "s")))
    parts = [("PART %d. %s" % (i + 1, t), b) for i, (t, b) in enumerate(raw)]
    body = "".join('<div class="%s"><h2>%s</h2>%s</div>' % ("pb" if i else "", E(t), b) for i, (t, b) in enumerate(parts))
    counts = [(p["short"], sum(len(g["items"]) for g in p["groups"])) for p in d["parts"]]
    nsyn = sum(1 for p in d["parts"] for g in p["groups"] for x in g["items"] if x.get("syn") or x.get("ant"))
    tail = ("&nbsp;|&nbsp; 유의어·반의어 수록 %d개" % nsyn) if d.get("syn") else ""
    toc = ('<div class="toc"><b>구성</b><ol>' + "".join("<li>%s</li>" % E(t) for t, _ in parts) + "</ol>"
           '<div style="margin-top:2mm;color:#5d6470;font-size:8.7pt">'
           "수록 어휘 %s (총 %d개) %s</div></div>"
           % (" · ".join("%s %d개" % c for c in counts), sum(n for _, n in counts), tail))
    note = ('<div class="note">%s</div>' % d["note"]) if d.get("note") else ""
    return ('<!doctype html><meta charset="utf-8"><style>%s</style><body>'
            "<h1>%s</h1>"
            '<div class="sub">%s</div>'
            '<div class="namebar"><span>%s</span><span>이름 ______________</span></div>'
            '%s%s%s<div class="foot">%s</div></body>'
            % (BOOK_CSS, d["title"], E(d.get("sub", "")), E(d["namebar"]),
               note, toc, body, E(d.get("footer", ""))))


def main_book(a, d, prof):
    rep = C.Report("%s · 단어장(책) 점검" % d["name"])
    for p in d["parts"]:
        for g in p["groups"]:
            ws = [x["w"].lower() for x in g["items"]]
            dup = sorted({w for w in ws if ws.count(w) > 1})
            if dup:
                rep.add("중복", "%s 표제어 중복 %s" % (g["title"], dup))
            for x in g["items"]:
                if not (x.get("m") or "").strip():
                    rep.add("뜻", "%s '%s' 뜻 없음" % (g["title"], x["w"]))
    rep.stop_if_bad()

    def post(paths):
        import pymupdf
        with pymupdf.open(paths[0]) as doc:
            txt = re.sub(r"\s+", " ", C.pdf_text(doc))
            for p in d["parts"]:
                for g in p["groups"]:
                    for x in g["items"]:
                        if re.sub(r"\s+", " ", x["w"]) not in txt:
                            rep.add("PDF", "%s '%s' 가 지면에 없음" % (g["title"], x["w"]))
            C.teacher_words(rep, "지면", txt)
            C.jari(rep, "지면", txt)
            C.residue(rep, "지면", txt)
            for w in prof.get("excluded_labels", []):
                if w in txt:
                    rep.add("제외유형", "지면에 '%s'" % w)
            C.pdf_physical(rep, "단어장", doc, min_chars=40, page_numbers=True, bottom_free_warn=0.99)
            rep.note("%d쪽 · 표제어 %d개" % (len(doc), sum(len(g["items"]) for p in d["parts"] for g in p["groups"])))
        return rep
    out = pathlib.Path(a.out) if a.out else pathlib.Path(a.data).resolve().parent
    final = R.render_checked([(book_html(d), d["name"] + ".pdf")], out, post, footer=BOOK_FOOT,
                             margin={"top": "15mm", "bottom": "14mm", "left": "13mm", "right": "13mm"})
    for f in final:
        print("저장", f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out")
    a = ap.parse_args()
    d, prof = load(a.data)
    if d.get("layout") == "book":
        return main_book(a, d, prof)
    rep = C.Report("%s · 단어장 점검" % d["name"])
    check_data(rep, d)
    check_grounding(rep, d)
    rep.stop_if_bad()

    import pymupdf
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="wordlist_"))
    try:
        final = pymupdf.open()
        inserted = []
        style = css(d)
        with sync_playwright() as pw:
            br = R.launch(pw)
            pg = br.new_page()
            for idx, group in enumerate(groups(d), start=1):
                if len(group) == 1 and group[0].get("source_page"):
                    sp = group[0]["source_page"]
                    with pymupdf.open(S.path(sp["file"])) as src:
                        hit = [i for i, pp in enumerate(src) if sp["contains"] in pp.get_text()]
                        if len(hit) != 1:
                            rep.add("원본", "%s번 원본에서 '%s' 쪽이 %d개" % (group[0]["key"], sp["contains"], len(hit)))
                        else:
                            inserted.append(len(final))
                            final.insert_pdf(src, from_page=hit[0], to_page=hit[0])
                    continue
                if any(s.get("source_page") for s in group):
                    rep.add("구성", "원본 쪽을 끼우는 섹션은 한 쪽에 혼자 있어야 한다 (per_page)")
                    continue
                pg.set_content('<html><head><meta charset="utf-8"><style>%s</style></head><body>%s</body></html>'
                               % (style, page_html(d, group, idx)))
                pg.evaluate("document.fonts.ready")
                over = pg.evaluate(LAYOUT_JS)
                n = "·".join(s["key"] for s in group)
                if over[0]:
                    rep.add("지면", "%s번 표가 쪽 아래로 넘침" % n)
                if over[1]:
                    rep.add("지면", "%s번 표가 오른쪽 여백을 넘음" % n)
                if over[2]:
                    rep.add("지면", "%s번 칸 넘침: %s" % (n, over[2][:5]))
                if over[3]:
                    rep.add("지면", "%s번 두 줄로 깨짐: %s" % (n, over[3][:5]))
                p = tmp / ("%d.pdf" % idx)
                pg.pdf(path=str(p), format="A4", print_background=True,
                       margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
                with pymupdf.open(p) as one:
                    if len(one) != 1:
                        rep.add("지면", "%s번 %d쪽으로 넘침" % (n, len(one)))
                    final.insert_pdf(one)
            br.close()
        rep.stop_if_bad()
        out_tmp = tmp / (d["name"] + ".pdf")
        final.save(out_tmp, garbage=3, deflate=True)
        final.close()
        check_pdf(rep, d, prof, out_tmp, inserted)
        rep.stop_if_bad()
        out = pathlib.Path(a.out) if a.out else pathlib.Path(a.data).resolve().parent
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_tmp, out / out_tmp.name)
        rep.print()
        print("저장", out / out_tmp.name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
