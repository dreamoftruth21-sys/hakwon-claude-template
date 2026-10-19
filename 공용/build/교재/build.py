# -*- coding: utf-8 -*-
"""시험대비 교재 (여러 자료를 푸는 순서대로 묶은 책) — 표지 · 차례 · 단계별 속표지 · 내용 · 정답과 해설까지 한 권.

    py 공용/build/교재/build.py <교재.json> [--skip-prep]
      1) prep 명령과 직접 출제 data(render.py)로 <작업>/_parts/ 를 만든다 (--skip-prep 이면 건너뛴다)
      2) 표지 → 차례 → 단계마다 [속표지 · 뒷면 비움 · 내용] → 「정답과 해설」 속표지 → 단계별 정답 순서로 묶는다.
         속표지는 언제나 홀수 쪽(양면 인쇄의 앞면)에 오게 앞에 빈 쪽을 끼운다.
      3) 원본 교재 쪽: hide 에 걸리는 쪽(범위 밖 지문)은 글자까지 지운다. 원래 쪽번호는 가리고 교재 쪽번호(n / N)를 찍는다
         (표지 · 차례 · 속표지 · 빈 쪽에는 찍지 않는다 — 쪽 수에는 센다). 첫 쪽 삼각형 표식은 찍지 않는다.
         가져온 정답 쪽은 원본정답.py 로 교재에 없는 활동의 답을 지운다.
      4) 쪽번호표 <작업>/_parts/쪽.json 을 쓰고, plan 이 있으면 수업계획 문서의 한 절(날짜별 숙제 쪽)을 그 표로 다시 쓴다
      5) after 명령 (계획표 빌드 등)
    → out (책) · out 이름 끝에 _답지 (「정답과 해설」 부분만 — 쪽번호도 책과 같다, 채점용)

교재.json 형식은 README.md. 구성은 반마다 새로 정한다 — 세종예고2 사례는 공용/규칙/교재구성.md.
"""
import pathlib, subprocess, sys, re, html, json
import pymupdf
from playwright.sync_api import sync_playwright

ENGINE = pathlib.Path(__file__).resolve().parent
ROOT = ENGINE.parents[2]                                         # 학원 폴더
sys.path.insert(0, str(ENGINE))
import render, 원본정답

NUM = re.compile(r"^-?\s*\d{1,3}\s*-?$")
NAVY, ORANGE = "#233a5e", "#f2a33a"


def pages_of(spec):
    """"1,3-22" · [1, 3, 4] · 7 → 쪽 목록."""
    if isinstance(spec, int): return [spec]
    if isinstance(spec, list): return spec
    out = []
    for x in str(spec).split(","):
        a, _, b = x.strip().partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


class Book:
    def __init__(self, cf):
        self.cf = pathlib.Path(cf).resolve()
        self.c = json.loads(self.cf.read_text(encoding="utf-8"))
        self.work = self.cf.parent
        self.parts = self.work / "_parts"
        c = self.c
        self.title = c["title"]
        self.out = ROOT / c["out"]
        self.out_a = self.out.with_name(self.out.stem + "_답지.pdf")
        base = ROOT / c.get("source_base", "")
        self.src = {k: dict(v, path=base / v["file"]) for k, v in c["sources"].items()}
        hd = c.get("hide")
        self.hide_rx = re.compile(hd["regex"], re.I) if hd else None
        self.hide_marker = ([hd["marker"]] if isinstance(hd["marker"], str) else hd["marker"]) if hd else None   # 표시 줄 하나 또는 여러 개 (과마다 다를 때)
        for st in c["stages"]:
            st.setdefault("toc", f"{st['label']}  {st['name']}")
            st.setdefault("short", st["toc"].replace("  ", " "))
        self.stage = {st["label"]: st for st in c["stages"]}

    # ---------- 준비 ----------
    def run(self, cmd):
        cmd = [sys.executable if x == "py" else x for x in cmd]
        subprocess.run(cmd, check=True, cwd=self.work)

    def prep(self):
        for cmd in self.c.get("prep", []): self.run(cmd)
        files = sorted(str(p) for g in self.c.get("data", []) for p in self.work.glob(g))
        if files: render.run(self.c, self.parts, files)

    # ---------- 쪽 ----------
    def srcs(self, item):
        """["part", 파일] · ["part", 파일, [시작, 끝]] (그 파일의 일부 — 시작 · 끝은 쪽 첫머리 정규식, null 이면 처음 · 끝까지) · [원본, 쪽]
        → part 는 (파일, 첫 쪽, 끝 쪽) 0부터, 원본은 쪽 목록."""
        out = []
        for x in item["src"]:
            s, p = x[0], x[1]
            if s != "part": out.append((s, pages_of(p))); continue
            d = pymupdf.open(self.parts / p); a, b = 0, d.page_count - 1
            if len(x) > 2:
                def find(rx):
                    i = next((i for i, pg in enumerate(d) if re.search(rx, pg.get_text()[:700], re.M)), None)
                    if i is None: raise RuntimeError(f"{item.get('key', item['title'])}: {p} 에서 '{rx}' 쪽을 못 찾았다")
                    return i
                lo, hi = x[2]
                if lo: a = find(lo)
                if hi: b = find(hi) - 1
                if b < a: raise RuntimeError(f"{item.get('key', item['title'])}: {p} 구간이 비었다")
            out.append((s, (p, a, b)))
        return out

    def count(self, srcs):
        return sum(p[2] - p[1] + 1 if s == "part" else len(p) for s, p in srcs)

    def page_texts(self, srcs):
        out = []
        for s, p in srcs:
            if s == "part":
                d = pymupdf.open(self.parts / p[0]); out += [d[i].get_text() for i in range(p[1], p[2] + 1)]
            else:
                d = pymupdf.open(self.src[s]["path"]); out += [d[q - 1].get_text() for q in p]
        return out

    def splits(self, item, srcs, s, n):
        """숙제로 나눠 낼 구간 — [이름, 시작] 시작은 항목 안 몇째 쪽(0부터) 또는 그 쪽 첫머리에 나오는 정규식."""
        sp = item.get("split")
        if not sp: return {}
        texts = self.page_texts(srcs) if any(isinstance(x, str) for _, x in sp) else None
        starts = []
        for key, at in sp:
            if isinstance(at, str):
                at = next((i for i, t in enumerate(texts) if re.search(at, t[:700], re.M)), None)
                if at is None: raise RuntimeError(f"{item['key']} 나누기: '{key}' 시작 쪽을 못 찾았다")
            starts.append((key, at))
        out = {}
        for i, (key, a) in enumerate(starts):
            b = starts[i + 1][1] - 1 if i + 1 < len(starts) else n - 1
            out[key] = rng(s + a, s + b)
        return out

    def layout(self):
        """쪽 배치를 먼저 계산한다 (차례 · 속표지에 쪽번호를 넣으려고). 쪽번호 = 실제 쪽 (표지가 1쪽)."""
        seq = [("cover",), ("blank",), ("toc",)]
        def pad():
            if len(seq) % 2 == 1: seq.append(("blank",))       # 다음 쪽이 짝수(뒷면)면 빈 쪽 — 속표지는 앞면에
        toc, pages = [], {}
        for st in self.c["stages"]:
            pad(); dv = len(seq) + 1
            rows = []
            seq.append(("div", st["label"])); seq.append(("blank",))
            for it in st["items"]:
                srcs = self.srcs(it); s = len(seq) + 1; n = self.count(srcs)
                seq += [("body",)] * n
                rows.append((it["title"], it.get("sub", ""), rng(s, s + n - 1))); pages[it["key"]] = rng(s, s + n - 1)
                pages.update(self.splits(it, srcs, s, n))
            toc.append((st, dv, rows))
        pad(); adv = len(seq) + 1
        seq.append(("div", "답")); seq.append(("blank",))
        arows = []
        for grp in self.c["answers"]:
            for it in grp["items"]:
                s = len(seq) + 1; n = self.count(self.srcs(it))
                seq += [("ans",)] * n
                arows.append((grp["stage"], it["title"], rng(s, s + n - 1)))
        pages["답"] = str(adv); pages["전체"] = str(len(seq))
        return seq, toc, adv, arows, pages

    # ---------- 원본 쪽 ----------
    def hide(self, pg):
        """범위 밖 지문이 섞인 쪽: 표시 줄부터 쪽 아래 머리글 위까지 지운다 (글자까지 — 흰 칸만 덮으면 복사 · 검색에 남는다)."""
        hits = [h for m in self.hide_marker for h in pg.search_for(m)]
        if not hits: return False
        y = min(h.y0 for h in hits) - 4
        pg.add_redact_annot(pymupdf.Rect(0, y, pg.rect.width, pg.rect.height - 24), fill=(1, 1, 1))
        pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
        return True

    def append(self, out, srcs, answer, log, clean=None):
        for s, pages in srcs:
            if s == "part":
                out.insert_pdf(pymupdf.open(self.parts / pages[0]), from_page=pages[1], to_page=pages[2]); continue
            info = self.src[s]; d = pymupdf.open(info["path"])
            for p in pages:
                t = d[p - 1].get_text()
                out.insert_pdf(d, from_page=p - 1, to_page=p - 1)
                pg = out[-1]
                hit = bool(self.hide_rx and self.hide_rx.search(t)) and not answer
                hid = self.hide(pg) if hit else False
                if hit and not hid:
                    raise RuntimeError(f"{s} {p}쪽에 범위 밖 지문이 있는데 가릴 곳('{self.hide_marker}')을 못 찾았다")
                for r in old_number(pg):
                    pg.draw_rect(r + (-2, -2, 2, 2), color=None, fill=(1, 1, 1), overlay=True)
                if hid: log.append(f"{s}:{p}")
                if answer and clean:
                    log.append(f"정답 {s}:{p} 지움 {원본정답.clean(pg, info['kind'], p, clean, d, info['answer_from'])}")

    # ---------- 조립 ----------
    def build(self):
        seq, toc, adv, arows, pages = self.layout()
        total = len(seq)
        rows = []
        for st, dv, items in toc:
            rows.append(("g", st["toc"], "", dv))
            rows += [("i", t, s, p) for t, s, p in items]
        rows.append(("g", "정답과 해설", "", adv))
        for st in self.c["stages"]:                                  # 정답은 단계마다 한 줄 (차례가 한 쪽에 들어가게)
            ps = [p for l, t, p in arows if l == st["label"]]
            if not ps: continue
            a, z = ps[0].split('~')[0], ps[-1].split('~')[-1]
            rows.append(("i", f"{st['short']} 정답", " · ".join(t.split(' — ')[0] for l, t, p in arows if l == st["label"]), rng(int(a), int(z))))
        self.parts.mkdir(exist_ok=True)
        docs = {"cover": html_pdf(self.cover_html(), self.parts / "_cover.pdf")}
        for tight in (0, 1, 2):                                    # 줄이 많으면 줄 간격을 좁혀 한 쪽에 맞춘다
            docs["toc"] = html_pdf(toc_html(rows, tight), self.parts / "_toc.pdf")
            lastb = max(b[3] for b in docs["toc"][0].get_text("blocks"))
            if docs["toc"].page_count == 1 and lastb < 800: break
        assert docs["toc"].page_count == 1, f"차례가 {docs['toc'].page_count}쪽 — 한 쪽으로 줄일 것"
        assert lastb < 800, f"차례가 쪽 아래로 넘친다 (마지막 줄 y={lastb:.0f})"
        dvd = {}
        for st, dv, items in toc:
            dvd[st["label"]] = html_pdf(self.divider_html(st["label"], st["name"], st.get("desc", ""), items, tight=len(items) > 10), self.parts / f"_div_{dv}.pdf")   # 항목이 많으면 촘촘하게
        ans_items = [(self.stage[l]["short"], t, p) for l, t, p in arows]
        dvd["답"] = html_pdf(self.divider_html("✔", "정답과 해설", "", ans_items, tight=True), self.parts / "_div_ans.pdf")
        for k, d in dvd.items():                                   # 속표지 표가 쪽 아래로 넘치지 않게
            lastb = max(bl[3] for bl in d[0].get_text("blocks"))
            assert d.page_count == 1 and lastb < 805, f"속표지 {k} 넘침 (y={lastb:.0f})"

        out = pymupdf.open(); log = []; nostamp = set()
        flat_body = [it for st in self.c["stages"] for it in st["items"]]
        flat_ans = [it for grp in self.c["answers"] for it in grp["items"]]
        bi = ai = 0; i = 0
        while i < len(seq):
            kind = seq[i][0]
            if kind in ("cover", "toc"): out.insert_pdf(docs[kind]); nostamp.add(i); i += 1
            elif kind == "blank": out.new_page(width=595.28, height=841.89); nostamp.add(i); i += 1
            elif kind == "div": out.insert_pdf(dvd[seq[i][1]]); nostamp.add(i); i += 1
            elif kind == "body":
                it = flat_body[bi]; srcs = self.srcs(it); self.append(out, srcs, False, log); bi += 1; i += self.count(srcs)
            else:
                it = flat_ans[ai]; srcs = self.srcs(it); self.append(out, srcs, True, log, it.get("clean")); ai += 1; i += self.count(srcs)
        assert out.page_count == total, (out.page_count, total)
        for k in range(total):                                     # 쪽번호
            if k in nostamp: continue
            pg = out[k]; s = f"{k + 1} / {total}"
            w = pymupdf.get_text_length(s, fontname="helv", fontsize=8.5); x = pg.rect.width / 2 - w / 2; y = pg.rect.height - 26
            pg.draw_rect(pymupdf.Rect(x - 5, y - 9, x + w + 5, y + 3), color=None, fill=(1, 1, 1), overlay=True)
            pg.insert_text((x, y), s, fontname="helv", fontsize=8.5, color=(.25, .25, .3))
        self.out.parent.mkdir(parents=True, exist_ok=True)
        out.save(self.out, garbage=4, deflate=True)
        a = pymupdf.open(); a.insert_pdf(out, from_page=adv - 1, to_page=total - 1); a.save(self.out_a, garbage=4, deflate=True)
        (self.parts / ("쪽.json" if self.cf.stem == "교재" else f"쪽_{self.cf.stem}.json")).write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"saved {self.out.name}  {total}쪽 · 정답과 해설 {adv}~{total}쪽  지움: {log}")
        for st, dv, items in toc:
            print(f"   {dv:>4}  [{st['short']}]"); [print(f"   {p:>8}  {t}") for t, s, p in items]
        print(f"   {adv:>4}  [정답과 해설]"); [print(f"   {p:>8}  {self.stage[l]['short']} — {t}") for l, t, p in arows]
        print(f"saved {self.out_a.name}  ({total - adv + 1}쪽 — 책의 {adv}~{total}쪽)")
        return pages

    # ---------- 수업계획 문서 ----------
    def update_plan(self, pg):
        pl = self.c.get("plan")
        if not pl: return
        md = ROOT / pl["md"]
        t = md.read_text(encoding="utf-8")
        s, e = t.index(pl["from"]), t.index(pl["to"])
        rows = "\n".join(f"| {d} | {h.format_map(pg)} | {m.format_map(pg)} |" for d, h, m in pl["rows"])
        sec = "\n".join(pl["text"]).format_map(dict(pg, rows=rows)) + "\n\n"
        t = t[:s] + sec + t[e:]
        for rx, rep in pl.get("replace", []):
            t = re.sub(rx, rep.format_map(pg).replace("\\", "\\\\"), t)
        md.write_text(t, encoding="utf-8")
        print(f"{md.name} '{pl['from']}' 다시 씀")

    # ---------- HTML ----------
    def cover_html(self):
        cv = self.c["cover"]
        flow = "".join(f"<div><b>{html.escape(st['label'])}</b>{html.escape(st['name'])}</div>" for st in self.c["stages"]) + "<div><b>✔</b>정답과 해설</div>"
        b1, b2 = cv["brand"]
        return (BASE + f"""<div class='pg cv'>
<div class='top'><div class='brand'>{html.escape(b1)} <span>{html.escape(b2)}</span></div><div class='sch'>{'<br>'.join(html.escape(x) for x in cv['school'])}</div></div>
<div class='band'><div class='o'></div></div>
<div class='ey'>{html.escape(cv['eyebrow'])}</div>
<div class='tt'>{html.escape(cv['title'])}</div>
<div class='tt2'>{html.escape(cv['title2'])}</div>
<div class='st'>{html.escape(cv.get('subtitle', ''))}</div>
<div class='flow'>{flow}</div>
<div class='nm'>이름<span></span></div></div></body>""")

    def divider_html(self, lab, name, desc, items, tight=False):
        tr = "".join(f"<tr><td class='t'>{html.escape(t)}</td><td class='s'>{html.escape(s)}</td><td class='p'>{p}</td></tr>" for t, s, p in items)
        return (BASE + f"<div class='pg dv{' tight' if tight else ''}'><div class='hd small'>{html.escape(self.title)}</div><div class='lab'>{html.escape(lab)}</div>"
                f"<div class='nm2'>{html.escape(name)}</div><div class='bar'></div><div class='ds'>{html.escape(desc)}</div><table>{tr}</table></div></body>")


def old_number(pg):
    """원래 쪽번호 자리 (아래 오른쪽 숫자 · 아래 가운데 '- n -')."""
    out = []
    for w in pg.get_text("words"):
        r = pymupdf.Rect(w[:4])
        if r.y0 > pg.rect.height - 60 and NUM.match(w[4].strip(" -")) and (r.x0 > pg.rect.width - 70 or abs((r.x0 + r.x1) / 2 - pg.rect.width / 2) < 40):
            out.append(r)
    for b in pg.get_text("blocks"):
        if b[1] > pg.rect.height - 60 and re.fullmatch(r"\s*-\s*\d{1,3}\s*-\s*", b[4]):
            out.append(pymupdf.Rect(b[:4]))
    return out


def rng(a, b):
    return f"{a}~{b}" if b > a else f"{a}"


def html_pdf(h, path):
    tmp = path.with_suffix(".html"); tmp.write_text(h, encoding="utf-8")
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(); pg.goto(tmp.as_uri())
        pg.pdf(path=str(path), format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        b.close()
    tmp.unlink()
    return pymupdf.open(path)


BASE = f"""<!doctype html><meta charset='utf-8'><style>
body{{margin:0;font-family:'Malgun Gothic',sans-serif;color:#1f2633;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.pg{{width:210mm;height:297mm;position:relative;overflow:hidden;break-after:page}}
.small{{font-size:8.4pt;color:#6b7486}}
/* 표지 */
.cv .top{{position:absolute;left:24mm;right:24mm;top:30mm;display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1.4pt solid {NAVY};padding-bottom:2.5mm}}
.cv .brand{{font-size:15pt;font-weight:800;color:{NAVY}}}.cv .brand span{{color:{ORANGE}}}
.cv .sch{{font-size:10.5pt;color:#4a5465;text-align:right;line-height:1.5}}
.cv .band{{position:absolute;left:0;right:0;top:78mm;height:96mm;background:{NAVY}}}
.cv .band .o{{position:absolute;left:0;right:0;bottom:0;height:3mm;background:{ORANGE}}}
.cv .ey{{position:absolute;left:24mm;top:90mm;font-size:12.5pt;color:{ORANGE};font-weight:700;letter-spacing:.5pt}}
.cv .tt{{position:absolute;left:24mm;top:100mm;font-size:40pt;color:#fff;font-weight:800;line-height:1.1}}
.cv .tt2{{position:absolute;left:24mm;top:124mm;font-size:24pt;color:#fff;font-weight:700}}
.cv .st{{position:absolute;left:24mm;top:150mm;font-size:16pt;color:#dfe6f1;font-family:'Times New Roman',serif;font-style:italic}}
.cv .flow{{position:absolute;left:24mm;right:24mm;top:190mm;display:flex;flex-wrap:wrap;gap:2.4mm}}
.cv .flow div{{border:1pt solid {NAVY};border-radius:2mm;padding:1.6mm 3.2mm;font-size:10pt;color:{NAVY};font-weight:700}}
.cv .flow div b{{color:{ORANGE};margin-right:1.2mm}}
.cv .nm{{position:absolute;left:24mm;bottom:28mm;font-size:12pt}}
.cv .nm span{{display:inline-block;width:62mm;border-bottom:.9pt solid #1f2633;margin:0 8mm 0 3mm}}
/* 차례 */
.tc h1{{font-size:18pt;color:{NAVY};margin:15mm 20mm 2mm}}
.tc table{{border-collapse:collapse;margin:0 20mm;width:170mm}}
.tc td{{border-bottom:.6pt solid #d3dae5;padding:1.05mm 2mm;vertical-align:top;font-size:9.2pt}}
.tc td.g{{border:0;padding:2.6mm 0 .6mm;font-weight:800;color:#c4561f;font-size:10.2pt}}
.tc td.t{{font-weight:700;width:58mm;padding-left:5mm}}.tc td.s{{font-size:8.2pt;color:#4a5465}}
.tc td.p{{text-align:right;font-weight:700;color:{NAVY};width:14mm}}
.tc tr.ga td.g{{color:{NAVY}}}
/* 속표지 */
.dv .lab{{position:absolute;left:24mm;top:58mm;font-size:64pt;font-weight:800;color:{ORANGE};line-height:1}}
.dv .nm2{{position:absolute;left:24mm;top:92mm;font-size:30pt;font-weight:800;color:{NAVY}}}
.dv .bar{{position:absolute;left:24mm;top:112mm;width:30mm;height:2.2mm;background:{ORANGE}}}
.dv .ds{{position:absolute;left:24mm;right:24mm;top:122mm;font-size:12pt;color:#3c4656;line-height:1.7}}
.dv table{{position:absolute;left:24mm;right:24mm;top:150mm;border-collapse:collapse;width:162mm}}
.dv td{{border-bottom:.6pt solid #d3dae5;padding:2.4mm 2mm;font-size:10.5pt;vertical-align:top}}
.dv td.t{{font-weight:700;width:68mm}}.dv td.s{{font-size:9pt;color:#4a5465}}.dv td.p{{text-align:right;font-weight:700;color:{NAVY};width:16mm}}
.dv .hd{{position:absolute;left:24mm;right:24mm;top:20mm;border-bottom:.6pt solid #c9d1de;padding-bottom:1.2mm}}
.dv.tight table{{top:126mm}}.dv.tight td{{padding:1.5mm 2mm;font-size:9.6pt}}.dv.tight td.t{{width:44mm}}
</style><body>"""


def toc_html(rows, tight=0):
    tr = ""
    for kind, a, b, c in rows:
        if kind == "g":
            tr += f"<tr class='{'ga' if a == '정답과 해설' else ''}'><td colspan=2 class='g'>{html.escape(a)}</td><td class='p'>{c}</td></tr>"
        else:
            tr += f"<tr><td class='t'>{html.escape(a)}</td><td class='s'>{html.escape(b)}</td><td class='p'>{c}</td></tr>"
    pad = ["", ".tc td{padding:.75mm 2mm}.tc td.g{padding:2mm 0 .4mm}.tc h1{margin-top:12mm}",
           ".tc td{padding:.5mm 2mm;font-size:8.8pt}.tc td.g{padding:1.6mm 0 .3mm}.tc h1{margin-top:10mm}"][tight]
    return BASE.replace("</style>", pad + "</style>") + f"<div class='pg tc'><h1>차례</h1><table>{tr}</table></div></body>"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1: sys.exit("py 공용/build/교재/build.py <교재.json> [--skip-prep]")
    bk = Book(args[0])
    if "--skip-prep" not in sys.argv: bk.prep()
    pg = bk.build()
    bk.update_plan(pg)
    for cmd in bk.c.get("after", []): bk.run(cmd)
