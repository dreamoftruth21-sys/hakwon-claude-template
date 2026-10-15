"""수업 계획 HTML → 인쇄용 PDF (A4 가로).

    py 공용/build/수업계획/pdf.py <계획.html> [--out <파일.pdf>] [--portrait]

- 화면용 HTML 은 그대로 두고, 인쇄할 때만 라이트 테마·촘촘한 표·쪽 나눔을 입힌다
- 쪽 아래: "<h1 제목> · 쪽 / 전체쪽" (자료 제목에 반·연도·자료명을 넣는 규칙)
- HTML 쪽에서 쓰는 표시 (템플릿.html 참고)
    class="print-break"      이 요소 앞에서 쪽을 넘긴다
    class="print-move-up"    인쇄할 때만 첫 print-break 앞으로 옮긴다 (1쪽 빈자리를 채울 때)
- 점검: 쪽 아래 제목·쪽 번호가 모든 쪽에 찍혔는지, 빈 쪽이 없는지. 걸리면 PDF 를 남기지 않는다
"""
import argparse, html, pathlib, re, sys
import pymupdf
from playwright.sync_api import sync_playwright

PRINT_CSS = """
@page{size:A4 %(orient)s;margin:10mm 9mm 13mm;@bottom-center{content:none}}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
:root{color-scheme:light}
body{background:#fff !important;font-size:12px}
main{max-width:none !important;padding:0 !important}
h1{font-size:18px} h2{font-size:15px;margin:10px 0 6px;padding-bottom:4px;break-after:avoid}
.lead{margin-bottom:10px}
.cards{grid-template-columns:repeat(5,1fr);gap:6px}
.card{padding:7px 10px} .card span{font-size:13px} .cards .card small{font-size:10.5px}
.wrap{overflow:visible !important}
table{min-width:0 !important}
th,td{font-size:11px;padding:4px 7px;line-height:1.45}
tr{break-inside:avoid} tr.week{break-after:avoid}
.flow{margin:3px 0 5px;gap:4px}
.step{font-size:11px;padding:3px 7px;line-height:1.35} .step small{font-size:10px}
p.pg,.src{font-size:10.5px;margin:4px 0}
.note{padding:6px 12px} li{margin:1px 0;font-size:11.5px}
footer{display:none}
.print-break{break-before:page;margin-top:0}
"""

MOVE_UP = """() => {
  const brk = document.querySelector('.print-break');
  if (!brk) return 0;
  const els = [...document.querySelectorAll('.print-move-up')];
  els.forEach(e => brk.parentNode.insertBefore(e, brk));
  return els.length;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--out")
    ap.add_argument("--portrait", action="store_true")
    a = ap.parse_args()

    src = pathlib.Path(a.html).resolve()
    out = pathlib.Path(a.out).resolve() if a.out else src.with_suffix(".pdf")
    tmp = out.with_suffix(".tmp.pdf")

    raw = src.read_text(encoding="utf-8")
    m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
    if not m:
        sys.exit("[점검] <h1> 제목이 없다 — 쪽 아래에 찍을 자료 제목(반·연도·자료명)을 h1 에 쓴다")
    title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()

    footer = ('<div style="width:100%;font-size:8px;color:#666;text-align:center;'
              'font-family:Malgun Gothic,sans-serif">' + html.escape(title) +
              ' &nbsp;·&nbsp; <span class="pageNumber"></span> / <span class="totalPages"></span></div>')

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(color_scheme="light")
        pg.goto(src.as_uri())
        pg.add_style_tag(content=PRINT_CSS % {"orient": "portrait" if a.portrait else "landscape"})
        moved = pg.evaluate(MOVE_UP)
        pg.emulate_media(media="print", color_scheme="light")
        pg.pdf(path=str(tmp), format="A4", landscape=not a.portrait, print_background=True,
               display_header_footer=True, header_template="<div></div>", footer_template=footer,
               margin={"top": "10mm", "bottom": "13mm", "left": "9mm", "right": "9mm"})
        b.close()

    doc = pymupdf.open(tmp)
    n = doc.page_count
    bad = []
    for i, page in enumerate(doc, 1):
        t = page.get_text()
        if f"{i} / {n}" not in t:
            bad.append(f"{i}쪽 — 쪽 번호가 안 찍혔다")
        if len(t.replace(title, "").strip()) < 20:
            bad.append(f"{i}쪽 — 빈 쪽")
    doc.close()

    print(f"── {src.name} → {out.name} · {n}쪽 · 옮긴 요소 {moved}")
    if bad:
        tmp.unlink(missing_ok=True)
        print("  결함 " + str(len(bad)) + "건")
        for x in bad:
            print("    " + x)
        sys.exit("점검 실패 — PDF 를 내보내지 않았다.")
    tmp.replace(out)
    print("  결함 0 · 저장 " + str(out))


if __name__ == "__main__":
    main()
