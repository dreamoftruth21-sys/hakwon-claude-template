# -*- coding: utf-8 -*-
"""내신결과 분석 피드백 · 학부모용 한 쪽 (HTML → PDF). 내용은 json 하나, 학생 여럿.

    py 공용/build/피드백/부모용.py <content.json> [이름 …]     (이름 없으면 전원)
→ json 과 같은 폴더에 "<file_prefix> (<이름>, <class_label>).pdf" + 이미지/<같은 이름>.png

한 쪽을 넘치거나 머리띠 글자가 잘리면 멈춘다 — 문장을 줄인다. 두 쪽 판은 만들지 않는다.
첫 쪽 삼각형 표식은 찍지 않는다 (결과 피드백 문서).
형식: 예시/부모용_예시.json
"""
import html
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

CSS = """
@page{size:A4;margin:0}
*{box-sizing:border-box}
body{margin:0;font-family:"Malgun Gothic","맑은 고딕",sans-serif;color:#2b2317;background:#FFF8EA;
 -webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{width:210mm;height:297mm;padding:9mm 12mm 7mm;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1.6pt solid #8A6116;padding-bottom:2mm}
.brand{font-size:17pt;font-weight:800;color:#5a3d0c;letter-spacing:.5pt}
.brand span{color:#B8862B}
.year{font-size:9.5pt;font-weight:700;color:#8A6116;margin-bottom:.8mm;letter-spacing:.3pt}
.who{font-size:11pt;font-weight:700}
.who u{text-decoration:none;border-bottom:1pt solid #2b2317;padding:0 4mm}
.sec{margin-top:3.6mm}
.bar{display:flex;align-items:center;gap:4mm;border:1.2pt solid #8A6116;border-radius:8mm;background:#fff;height:10.5mm;padding-right:5mm}
.pill{flex:none;width:36mm;height:100%;border-radius:8mm;background:linear-gradient(#C9973A,#8A6116);
 color:#fff;font-size:12.5pt;font-weight:800;display:flex;align-items:center;justify-content:center;letter-spacing:2pt}
.bar .t{font-size:11pt;font-weight:700;color:#3b2a10;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.box{border:1.2pt solid #8A6116;background:#fff;margin-top:2.5mm;padding:3.4mm 5mm}
table{border-collapse:collapse;width:100%;font-size:8.6pt;text-align:center}
th,td{border:.6pt solid #b9a27a;padding:1mm .8mm}
th{background:#F3E6CC;font-weight:700}
td.k{background:#FBF4E4;font-weight:700}
tr.sum td{font-weight:700;background:#F3E6CC}
p{margin:0;font-size:9.4pt;line-height:1.66;text-align:left;word-break:keep-all}
p+p{margin-top:2.2mm}
.num{font-weight:700;color:#8A6116}
.fb p{text-indent:3mm}
.foot{margin-top:auto;text-align:center;font-size:8.5pt;color:#5a3d0c;border-top:1pt solid #8A6116;padding-top:2mm}
"""


def build(C, s, here):
    head = "<tr><th>문제 유형 / 시험 범위</th>%s<th>합</th></tr>" % "".join("<th>%s</th>" % html.escape(c) for c in C["cols"])
    body = "".join("<tr%s><td class='k'>%s</td>%s</tr>" % (
        " class='sum'" if r[0] == "합" else "", html.escape(str(r[0])), "".join("<td>%s</td>" % html.escape(str(x)) for x in r[1:]))
        for r in C["table"])
    review = "".join("<p><span class='num'>%s</span> %s</p>" % tuple(html.escape(p) for p in (x.split(" ", 1) + [""])[:2])
                     for x in C["review"])
    fb = "".join("<p>%s</p>" % html.escape(x) for x in s["fb_paras"])
    score = str(s["score"]) + ("" if "점" in str(s["score"]) else "점")
    doc = f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style><body><div class="page">
<div class="top"><div><div class="year">{html.escape(C['year_title'])}</div><div class="brand">{html.escape(C['brand'])} <span>{html.escape(C['subject'])}</span></div></div>
 <div class="who">{html.escape(C['school'])} &nbsp;<u>{html.escape(str(C['grade']))}</u>&nbsp;학년 &nbsp;/&nbsp; 이름 &nbsp;<u>{html.escape(s.get('spaced') or s['name'])}</u></div></div>
<div class="sec"><div class="bar"><div class="pill">기출분석</div><div class="t">{html.escape(C['exam_title'])}</div></div>
 <div class="box"><table>{head}{body}</table></div></div>
<div class="sec"><div class="bar"><div class="pill">시험총평</div><div class="t">{html.escape(C['headline'])}</div></div>
 <div class="box">{review}</div></div>
<div class="sec"><div class="bar"><div class="pill">개별피드백</div><div class="t">{html.escape(s['name'])}의 학습 성취에 관한 일대일 피드백입니다 &nbsp;( {html.escape(score)} )</div></div>
 <div class="box fb">{fb}</div></div>
<div class="foot">{html.escape(C.get('footer', ''))}</div>
</div></body>"""
    h = here / ("_부모용_%s.html" % s["name"])
    h.write_text(doc, encoding="utf-8")
    pdf = here / ("%s (%s, %s).pdf" % (C["file_prefix"], s["name"], C["class_label"]))
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page()
        pg.goto(h.as_uri())
        over = pg.evaluate("document.querySelector('.page').scrollHeight - document.querySelector('.page').clientHeight")
        cut = pg.evaluate("[...document.querySelectorAll('.bar .t')].filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.textContent)")
        if over > 2 or cut:
            br.close()
            h.unlink()
            raise SystemExit("%s: 한 쪽 넘침 %spx · 머리띠 잘림 %s — 문장을 줄인다" % (s["name"], over, cut))
        pg.pdf(path=str(pdf), width="210mm", height="297mm", print_background=True)
        br.close()
    h.unlink()
    import pymupdf
    (here / "이미지").mkdir(exist_ok=True)
    pymupdf.open(pdf)[0].get_pixmap(dpi=200).save(str(here / "이미지" / (pdf.stem + ".png")))
    print("저장", pdf.name)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = pathlib.Path(sys.argv[1]).resolve()
    C = json.loads(src.read_text(encoding="utf-8"))
    names = sys.argv[2:] or [x["name"] for x in C["students"]]
    for n in names:
        s = next((x for x in C["students"] if x["name"] == n), None)
        if not s:
            sys.exit("json 에 없는 이름: " + n)
        build(C, s, src.parent)


if __name__ == "__main__":
    main()
