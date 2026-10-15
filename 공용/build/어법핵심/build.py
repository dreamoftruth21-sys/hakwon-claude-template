# -*- coding: utf-8 -*-
"""어법 핵심 정리 (학생 배부용, 보통 2쪽) — py 공용/build/어법핵심/build.py <data.json> [--out 폴더]
   유형마다 [규칙 한 줄 · 규칙 표 · 예문]. 예문은 그 반 시험 범위 원문에서 문장 전체를 찾아 넣는다 —
   원문에 없는 문장, 표시할 부분이 문장에 없음, 한 문장으로 안 좁혀짐, 쪽 수 초과, 쪽보다 넓은 내용, 금지어 중 하나라도 걸리면 PDF를 내보내지 않는다.
   다른 교재(첫단추 · 천일문 등)의 개념·예문은 쓰지 않는다 — 규칙 표의 줄마다 범위 원문 예문이 있어야 한다 (2026-09-29 사용자 지시).
   data.json 형식은 README.md. 원본 경로는 학원 폴더 기준.
"""
import os, sys, html, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))       # 학원 폴더
FORBID = ["하세요", "판서", "채점하면", "학생이", "배점", "출제자"]


def A(p): return os.path.normpath(os.path.join(ROOT, p))


def _clean(t, strip=()):
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)                    # 텍스트 변환본의 쪽 표시
    t = re.sub(r"\d+\s*[-–‐]\s*\d+\s*[-–‐]", " ", t)
    for h in strip: t = t.replace(h, " ")
    t = t.replace("­", "-")
    t = re.sub(r"\s\*+ ?[A-Za-z][\w\- ]*: ?[가-힣][^A-Z*]*", " ", t)      # 각주 (* cash nexus: 현금 거래 관계)
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[①-⑤ⓐ-ⓕ]", "", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_PDF = {}


def load(spec):
    """원문 하나를 불러온다. md(교과서 텍스트 변환본) · bynum(학평 원문 json) · pdf(학평 문제지 + 원문 복원) 중 하나."""
    if "md" in spec:
        t = open(A(spec["md"]), encoding="utf-8").read()
        if spec.get("until"): t = t[:t.find(spec["until"])] if spec["until"] in t else t
        if spec.get("drop_korean_lines", True):
            t = "\n".join(l for l in t.split("\n") if not re.search("[가-힣]", l) and not l.startswith("#"))
        return _clean(t, spec.get("strip", []))
    if "bynum" in spec:
        by = json.load(open(A(r"공용/교재/모의고사/_데이터/%s_bynum.json" % spec["bynum"]), encoding="utf-8"))
        return _clean(by[spec["round"]][spec["num"]], spec.get("strip", []))
    if "pdf" in spec:
        if spec["pdf"] not in _PDF:
            import pymupdf
            full = "\n".join(p.get_text() for p in pymupdf.open(A(spec["pdf"])))
            parts = re.split(r"\n\s*(\d{2})\.\s", full)
            _PDF[spec["pdf"]] = {parts[j]: parts[j + 1] for j in range(len(parts) - 2, 0, -2)}   # 같은 번호가 또 나오면 앞의 것
        t = _clean(_PDF[spec["pdf"]][spec["num"]], spec.get("strip", []))
        rep = list(spec.get("replace", []))
        if spec.get("replace_from"):                                   # 실전 모의고사 data.json 의 sources.<키>[0].replace
            d = json.load(open(A(spec["replace_from"]), encoding="utf-8"))
            rep += d["sources"][spec.get("replace_key", "M")][0]["replace"]
        for a, b in rep: t = t.replace(a, b)
        return t
    raise SystemExit("원문 형식을 모름: %s" % spec)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?\"])\s+(?=[A-Z\"])", text) if s.strip()]


def ex(S, e):
    """원문 문장 전체 + 표시할 부분 굵게 + 틀린 형태 · 덧붙임."""
    key = e["src"]
    ss = [s for s in S[key]["sents"] if e["find"] in s]
    if len(ss) != 1:
        raise SystemExit("예문을 하나로 못 찾음 (%d개): %s %s" % (len(ss), key, e["find"]))
    s = ss[0]
    s = re.sub(r"^.*?(?=[A-Z])", "", s) if re.match(r"^[^A-Za-z\"]", s) else s     # 발문 등 앞 잔재 제거
    body = html.escape(s)
    marks = e.get("mark", [])
    for m in ([marks] if isinstance(marks, str) else marks):
        if m not in s:
            raise SystemExit('표시할 부분 "%s" 이 예문에 없음: %s' % (m, s[:70]))
        body = body.replace(html.escape(m), "<b class=k>%s</b>" % html.escape(m), 1)
    tail = ""
    if e.get("wrong"): tail += "<span class=wr>✗ %s</span>" % html.escape(e["wrong"])
    if e.get("note"): tail += "<span class=nt>%s</span>" % e["note"]
    return "<div class=ex><span class=src>%s</span> <span class=en>%s</span>%s</div>" % (S[key]["name"], body, tail)


def build(dp, out_dir=None):
    d = json.load(open(dp, encoding="utf-8"))
    S = {k: dict(v, sents=sentences(load(v))) for k, v in d["sources"].items()}
    h = ["<h1>%s</h1>" % d["title"], "<p class=sub>%s</p>" % d["sub"]]
    if d.get("check"):
        h.append("<div class=check><h2>%s</h2><ol>%s</ol></div>" % (d.get("check_title", "밑줄 문장 점검 순서"), "".join("<li>%s</li>" % c for c in d["check"])))
    for sec in d["sections"]:
        assert sec["ex"], (sec["title"], "예문 없는 유형 — 범위 원문 예문이 있어야 한다")
        rows = "".join("<tr><td>%s</td><td>%s</td></tr>" % (html.escape(a), html.escape(b)) for a, b in sec.get("table", []))
        h.append("<div class=sec><h2><span class=n>%s</span>%s</h2><p class=rule>%s</p><table>%s</table>%s</div>"
                 % (sec["n"], sec["title"], sec["rule"], rows, "".join(ex(S, e) for e in sec["ex"])))
    body = "".join(h)
    plain = re.sub("<[^>]+>", " ", body)
    for w in FORBID:
        assert w not in plain, ("금지어", w)
    css = open(os.path.join(HERE, "style.css"), encoding="utf-8").read() + d.get("css", "")
    doc = "<html><head><meta charset=utf-8><style>%s</style></head><body>%s</body></html>" % (css, body)
    out_dir = out_dir or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(dp)), d.get("out", ".")))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, d["name"] + ".pdf")
    hp = os.path.splitext(os.path.abspath(dp))[0] + ".html"
    open(hp, "w", encoding="utf-8").write(doc)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 710, "height": 1000}); pg.emulate_media(media="print")
        pg.goto("file:///" + hp.replace("\\", "/"))
        sw, cw = pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        assert sw <= cw, ("쪽보다 넓은 내용 — PDF 가 축소된다", sw, cw)
        foot = d.get("footer", d["title"])
        pg.pdf(path=out, format="A4", print_background=True, display_header_footer=True,
               header_template="<div></div>",
               footer_template='<div style="width:100%;font-size:7.5px;color:#777;text-align:center;font-family:Malgun Gothic">'
                               + foot + ' &nbsp; <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
               margin={"top": "11mm", "bottom": "13mm", "left": "12mm", "right": "12mm"})
        b.close()
    import pymupdf
    n = len(pymupdf.open(out))
    print("저장", out, n, "쪽")
    if n > d.get("max_pages", 2):
        os.remove(out)
        raise SystemExit("%d쪽 — 최대 %d쪽을 넘어 PDF를 지웠다. 예문을 줄이거나 css 로 간격을 줄인다" % (n, d.get("max_pages", 2)))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    od = None
    if "--out" in a:
        i = a.index("--out"); od = os.path.abspath(a[i + 1]); del a[i:i + 2]
    build(a[0], od)
