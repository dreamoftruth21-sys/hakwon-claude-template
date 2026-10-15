"""HTML → PDF.

render_checked() 는 임시 폴더에 PDF를 뽑고, 점검 함수가 결함 0을 돌려줄 때만 최종 폴더로 옮긴다.
점검에 걸리면 최종 폴더에는 아무것도 생기지 않는다.
"""
import pathlib
import shutil
import tempfile

from playwright.sync_api import sync_playwright

MARGIN = {"top": "13mm", "bottom": "12mm", "left": "11mm", "right": "11mm"}


def footer_html(label):
    return ('<div style="width:100%;font-size:7.4pt;color:#666;font-family:sans-serif;text-align:center;">'
            + label + ' · <span class="pageNumber"></span> / <span class="totalPages"></span></div>')


def launch(pw):
    """chrome → msedge → playwright 기본 크로미움 순서로 띄운다."""
    for ch in ("chrome", "msedge"):
        try:
            return pw.chromium.launch(channel=ch)
        except Exception:
            pass
    return pw.chromium.launch()


def html_to_pdf(jobs, footer=None, margin=None):
    """jobs: [(html 문자열, pdf 경로)]"""
    margin = margin or MARGIN
    with tempfile.TemporaryDirectory() as td, sync_playwright() as pw:
        br = launch(pw)
        pg = br.new_page()
        for i, (doc, out) in enumerate(jobs):
            h = pathlib.Path(td) / ("p%d.html" % i)
            h.write_text(doc, encoding="utf-8")
            pg.goto(h.as_uri())
            pg.emulate_media(media="print")
            opts = dict(path=str(out), format="A4", print_background=True, margin=margin)
            if footer:
                opts.update(display_header_footer=True, header_template="<div></div>", footer_template=footer)
            pg.pdf(**opts)
        br.close()


def render_checked(jobs, out_dir, check, footer=None, margin=None, keep_html=False):
    """jobs: [(html 문자열, 파일이름.pdf)]
    check(임시경로 목록) → Report. 결함이 있으면 멈추고 out_dir 에는 쓰지 않는다."""
    out_dir = pathlib.Path(out_dir)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="build_"))
    try:
        paths = [tmp / name for _, name in jobs]
        html_to_pdf([(doc, p) for (doc, _), p in zip(jobs, paths)], footer=footer, margin=margin)
        rep = check(paths)
        rep.stop_if_bad()
        out_dir.mkdir(parents=True, exist_ok=True)
        final = []
        for p in paths:
            dst = out_dir / p.name
            shutil.copy2(p, dst)
            final.append(dst)
        if keep_html:
            for (doc, name) in jobs:
                (out_dir / (pathlib.Path(name).stem + ".html")).write_text(doc, encoding="utf-8")
        rep.print()
        return final
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
