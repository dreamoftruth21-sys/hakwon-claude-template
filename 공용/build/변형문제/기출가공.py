# -*- coding: utf-8 -*-
"""학평 내신기출·변형문제집 가공 — 범위 밖 지문 문항을 ✕로 지우거나(지우기), 범위 지문 문항만 뽑아 새로 조판한다(뽑기).

사용: py 공용/build/변형문제/기출가공.py <data.json> [--out 폴더]

book  "내신기출" — 이그잼포유 「내신기출 N회」 (문항에 지문 번호 라벨이 없어 학평 원문 6-gram 으로 지문을 판정한다)
      "변형문제" — 이그잼포유 「변형문제」 (문항 위 `NN번` 라벨)
mode  "지우기" — 원본 전체를 두고 대상 지문 문항·해설을 흰색으로 덮고 ✕ 표시
      "뽑기"   — 대상 지문 문항·해설만 잘라 제목·구획 띠를 붙여 새로 조판
점검에 하나라도 걸리면 PDF를 내보내지 않는다.
기준 구현: 한솔고2/…/학평_가공 hs_kb.py·hs_var.py · 양지고2/…/학평_가공 yg_kb.py·yg_var.py · 세종예고2/…/학평_가공 sj_kb.py·sj_var.py (+flow.py·banner.py)
"""
import argparse
import html
import json
import pathlib
import re
import shutil
import sys
import tempfile

import pymupdf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import checks as C  # noqa: E402
from core import render as R  # noqa: E402
from core import sources as S  # noqa: E402

QN = re.compile(r"^(\d{1,3})\s*\.")
GP = re.compile(r"^\[\s*(\d{1,3})\s*[-~]\s*(\d{1,3})\s*\]")
LAB = re.compile(r"^(\d{1,2}(?:~\d{1,2})?)번$")
HDRS = {'대의파악', '요약문', '내용일치/불일치', '어법', '어휘', '빈칸추론', '순서', '삽입', '무관한문장', '장문', '지칭추론',
        '함축의미', '제목', '주제', '요지', '목적', '심경', '주장'}


def toks(s):
    return [w for w in re.sub(r"[^A-Za-z ]", " ", s.lower()).split() if len(w) > 1]


def grams6(s):
    t = toks(s)
    return set(tuple(t[i:i + 6]) for i in range(len(t) - 5))


def fail(msg):
    raise SystemExit("원본 판독 실패 — " + msg)


def x_mark(d, byp):
    """쪽별 사각형을 흰색으로 덮고 테두리 + ✕ (hs_kb.py)"""
    n = 0
    for i, rs in byp.items():
        p = d[i]
        for r in rs:
            p.add_redact_annot(r, fill=(1, 1, 1))
        p.apply_redactions()
        for r in rs:
            p.draw_rect(r, color=(0.25, 0.25, 0.25), width=1.0)
            p.draw_line(r.tl, r.br, color=(0.15, 0.15, 0.15), width=2.0)
            p.draw_line(r.tr, r.bl, color=(0.15, 0.15, 0.15), width=2.0)
            n += 1
    return n


# ── 조판 틀 (flow.py · banner.py) ───────────────────────────
PW, PH = 595.0, 842.0
TOPY, BOTY = 44.0, 812.0
COLX, COLW = [16.0, 304.0], 284.0
TITH, SECH = 42.0, 20.0
BANNER_FONT = '"Noto Sans CJK KR","Noto Sans KR","Malgun Gothic",sans-serif'


def make_banners(title, sub, sections, outdir):
    css = ('*{margin:0;padding:0;box-sizing:border-box}'
           'body{font-family:%s;-webkit-print-color-adjust:exact;print-color-adjust:exact}' % BANNER_FONT)
    bt = ('<!doctype html><meta charset="utf-8"><style>%s @page{size:563pt 42pt;margin:0}'
          'body{padding:2pt 0 0 0}h1{font-size:14pt;color:#12212f;letter-spacing:-.02em}'
          'p{font-size:8.4pt;color:#5d6470;margin-top:3pt}hr{margin-top:5pt;border:0;border-top:.8pt solid #8d96a3}'
          '</style><body><h1>%s</h1><p>%s</p><hr></body>' % (css, html.escape(title), html.escape(sub)))
    pgs = "".join('<div class="b"%s><span>%s</span></div>' % (' style="page-break-before:always"' if i else "",
                                                            html.escape(x)) for i, x in enumerate(sections))
    bs = ('<!doctype html><meta charset="utf-8"><style>%s @page{size:563pt 20pt;margin:0}'
          '.b{height:20pt;background:#12212f;display:flex;align-items:center;padding-left:8pt;border-radius:2pt}'
          'span{color:#fff;font-size:10.3pt;font-weight:700}</style><body>%s</body>' % (css, pgs))
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as pw:
        b = R.launch(pw)
        pg = b.new_page()
        for name, doc, h in (("bt", bt, 42), ("bs", bs, 20)):
            hp = pathlib.Path(outdir) / (name + ".html")
            hp.write_text(doc, encoding="utf-8")
            pg.goto(hp.as_uri())
            pg.emulate_media(media="print")
            o = pathlib.Path(outdir) / (name + ".pdf")
            pg.pdf(path=str(o), width="%fin" % (563 / 72), height="%fin" % (h / 72), print_background=True,
                   margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            out.append(str(o))
        b.close()
    return out


class Flow:
    def __init__(self, bt, bs, seclist):
        self.doc = pymupdf.open()
        self.bt, self.bs = pymupdf.open(bt), pymupdf.open(bs)
        self.sec = {s: i for i, s in enumerate(seclist)}
        self.page, self.col, self.y, self.n = None, 0, TOPY, 0
        self._new(first=True)

    def _new(self, first=False):
        self.page = self.doc.new_page(width=PW, height=PH)
        self.n += 1
        if first:
            self.page.show_pdf_page(pymupdf.Rect(16, 20, 579, 20 + TITH), self.bt, 0)
            self.y = 20 + TITH + 8
        else:
            self.y = TOPY
        self._pagetop, self._used, self.col = self.y, False, 0

    def _nextcol(self):
        if self.col == 0:
            self.col, self.y = 1, self._pagetop
        else:
            self._new()

    def place(self, src, pno, rect, full=False):
        h, w = rect.height, rect.width
        if full:
            if self.col != 0 or self.y + h > BOTY:
                self._new()
            self.page.show_pdf_page(pymupdf.Rect(16.0, self.y, 16.0 + min(w, 563.0), self.y + h), src, pno, clip=rect)
            self.y += h + 10
            self.col, self._used = 1, True
            return
        if self.y + h > BOTY:
            self._nextcol()
        if self.y + h > BOTY:
            self._new()
        x = COLX[self.col]
        self.page.show_pdf_page(pymupdf.Rect(x, self.y, x + min(w, COLW), self.y + h), src, pno, clip=rect)
        self.y += h + 9
        self._used = True

    def section(self, label):
        if self._used:
            self._new()
        self.page.show_pdf_page(pymupdf.Rect(16, self.y, 579, self.y + SECH), self.bs, self.sec[label])
        self.y += SECH + 10
        self._pagetop = self.y

    def save(self, path):
        for i, p in enumerate(self.doc):
            p.insert_text((PW / 2 - 16, 830), "%d / %d" % (i + 1, self.doc.page_count),
                          fontname="helv", fontsize=7.5, color=(0.6, 0.63, 0.68))
        self.doc.save(path, garbage=4, deflate=True, clean=True)
        return self.doc.page_count


# ── 내신기출 ────────────────────────────────────────────────
KB_LX, KB_RX, KB_BOT = (22.0, 288.0), (311.0, 575.0), 812.0


def kb_col(x):
    return 0 if x < 300 else 1


def kb_segments(d, idx, sol_page):
    GR = {n: grams6(v) for n, v in idx.items()}
    segs, MARK, TOPB, MAXB = [], {}, {}, {}
    for i, p in enumerate(d):
        if i > sol_page:
            continue
        blocks = [b for b in p.get_text("blocks") if b[4].strip() and b[1] < KB_BOT]
        for c in (0, 1):
            cb = sorted([b for b in blocks if kb_col(b[0]) == c], key=lambda b: b[1])
            st = []
            for j, b in enumerate(cb):
                t = re.sub(r"\s+", " ", b[4]).strip()
                m, g = QN.match(t), GP.match(t)
                if not (m or g):
                    continue
                y = b[1]
                if j > 0 and cb[j - 1][4].strip().startswith("기출") and y - cb[j - 1][1] < 40:
                    y = cb[j - 1][1]
                st.append((y, m.group(1) if m else g.group(0), t))
            if cb:
                MARK[(i, c)] = [z[0] for z in st]
                TOPB[(i, c)] = min(b[1] for b in cb)
                MAXB[(i, c)] = max(b[3] for b in cb)
            for k, (y, lab, stem) in enumerate(st):
                hi = st[k + 1][0] if k + 1 < len(st) else KB_BOT
                inner = [b for b in cb if b[1] >= y - 2 and b[1] < hi]
                segs.append(dict(page=i, col=c, y0=y, y1=min(hi, max([b[3] for b in inner], default=hi) + 5),
                                 lab=lab, stem=stem[:40], txt=" ".join(re.sub(r"\s+", " ", b[4]) for b in inner)))
    prev = None
    for s in segs:
        if re.search(r"윗글|위 글", s["stem"]) or len(toks(s["txt"])) < 28:
            s["num"] = prev
        else:
            g = grams6(s["txt"])
            bs, best = 0, None
            for n, G in GR.items():
                sc = len(g & G) / max(1, len(g))
                if sc > bs:
                    bs, best = sc, n
            s["num"] = best if bs >= 0.10 else None
            prev = s["num"]
    return segs, MARK, TOPB, MAXB


def kb_lines(d, sol_page):
    lin = []
    for i, p in enumerate(d):
        if i <= sol_page:
            continue
        bl = [b for b in p.get_text("blocks") if b[4].strip() and b[1] < KB_BOT]
        for c in (0, 1):
            for b in sorted([x for x in bl if kb_col(x[0]) == c], key=lambda x: x[1]):
                lin.append((i, c, b[1], b[3], re.sub(r"\s+", " ", b[4]).strip()))
    return lin


def kb_erase(d, targets, idx, sol_page):
    segs, MARK, TOPB, MAXB = kb_segments(d, idx, sol_page)

    def contrect(pg, c):
        key = (pg, 1) if c == 0 else (pg + 1, 0)
        if key not in TOPB:
            return None
        ms = sorted(MARK.get(key, []))
        if ms and ms[0] <= TOPB[key] + 10:
            return None
        y0 = TOPB[key] - 4
        y1 = (ms[0] - 7) if ms else MAXB[key] + 4
        if y1 - y0 <= 10:
            return None
        return dict(page=key[0], col=key[1], y0=y0 + 6, y1=y1 - 3, lab="연속", num="연속")
    kill, qs = [], set()
    for s in segs:
        if s["num"] in targets:
            kill.append(s)
            if MARK.get((s["page"], s["col"])) and abs(s["y0"] - MARK[(s["page"], s["col"])][-1]) < 0.6:
                cr = contrect(s["page"], s["col"])
                if cr:
                    kill.append(cr)
            if s["lab"].startswith("["):
                a, b = GP.match(s["lab"]).groups()
                qs.update([a, b])
            else:
                qs.add(s["lab"])
    if not qs:
        fail("지울 문항을 하나도 못 찾음")
    lin = kb_lines(d, sol_page)
    lo = hi = None
    tgt = sorted(int(x) for x in qs)
    for k, (i, c, y0, y1, t) in enumerate(lin):
        m = QN.match(t)
        if not m:
            continue
        v = int(m.group(1))
        if v == tgt[0] and lo is None:
            lo = k
        if lo is not None and v > tgt[-1] and hi is None:
            hi = k
    if lo is not None:
        hi = hi or len(lin)
        grp = {}
        for i, c, y0, y1, t in lin[lo:hi]:
            k = (i, c)
            grp[k] = (min(grp.get(k, (y0, y1))[0], y0), max(grp.get(k, (y0, y1))[1], y1))
        for (i, c), (y0, y1) in grp.items():
            kill.append(dict(page=i, col=c, y0=y0, y1=y1, lab="해설", num="해설"))
    byp = {}
    for s in kill:
        xr = KB_LX if s["col"] == 0 else KB_RX
        byp.setdefault(s["page"], []).append(pymupdf.Rect(xr[0], s["y0"] - 6, xr[1], s["y1"] + 3))
    n = x_mark(d, byp)
    return sorted(qs, key=int), n


def kb_extract(d, keep, idx, sol_page, title, sub, tmp):
    segs, MARK, TOPB, MAXB = kb_segments(d, idx, sol_page)

    def cont(s):
        key = (s["page"], 1) if s["col"] == 0 else (s["page"] + 1, 0)
        if key not in TOPB:
            return None
        ms = sorted(MARK.get(key, []))
        if ms and ms[0] <= TOPB[key] + 10:
            return None
        y0 = TOPB[key] - 4
        y1 = (ms[0] - 7) if ms else MAXB[key] + 4
        return (key[0], key[1], y0, y1) if y1 - y0 > 10 else None
    for s in segs:
        last = MARK.get((s["page"], s["col"]), []) and abs(s["y0"] - MARK[(s["page"], s["col"])][-1]) < 0.6
        s["cont"] = cont(s) if last else None
    kept = [s for s in segs if s["num"] in keep]
    Q2L = {}
    for s in kept:
        if s["lab"].startswith("["):
            a, b = GP.match(s["lab"]).groups()
            for q in range(int(a), int(b) + 1):
                Q2L[str(q)] = s["num"]
        else:
            Q2L[s["lab"]] = s["num"]
    if not Q2L:
        fail("뽑을 문항을 하나도 못 찾음")
    ORD = {k: j for j, k in enumerate(keep)}
    kept.sort(key=lambda s: (ORD[s["num"]], s["page"], s["col"], s["y0"]))
    lin = kb_lines(d, sol_page)
    marks = [(k, QN.match(t).group(1)) for k, (i, c, y0, y1, t) in enumerate(lin) if QN.match(t)]
    sol = []
    for j, (k, v) in enumerate(marks):
        if v in Q2L:
            end = marks[j + 1][0] if j + 1 < len(marks) else len(lin)
            cur = None
            for i, c, y0, y1, t in lin[k:end]:
                if cur and cur[0] == i and cur[1] == c:
                    cur[3] = max(cur[3], y1)
                else:
                    if cur:
                        sol.append(cur)
                    cur = [i, c, y0, y1, Q2L[v]]
            if cur:
                sol.append(cur)
    sol.sort(key=lambda x: (ORD.get(x[4], 9),))
    SECS = ["%s번 지문" % n for n in keep] + ["정답 및 해설 — %s번 지문" % n for n in keep]
    bt, bs = make_banners(title, sub.replace("{문항수}", str(len(Q2L))), SECS, tmp)
    f = Flow(bt, bs, SECS)
    cur = None
    for s in kept:
        if s["num"] != cur:
            f.section("%s번 지문" % s["num"])
            cur = s["num"]
        xr = KB_LX if s["col"] == 0 else KB_RX
        f.place(d, s["page"], pymupdf.Rect(xr[0], s["y0"] - 6, xr[1], s["y1"] + 3), False)
        if s["cont"]:
            pp, cc, a, b = s["cont"]
            x2 = KB_LX if cc == 0 else KB_RX
            f.place(d, pp, pymupdf.Rect(x2[0], a, x2[1], b), False)
    cur = None
    for i, c, y0, y1, lab in sol:
        if lab != cur:
            f.section("정답 및 해설 — %s번 지문" % lab)
            cur = lab
        xr = KB_LX if c == 0 else KB_RX
        f.place(d, i, pymupdf.Rect(xr[0], y0 - 5, xr[1], y1 + 4), False)
    return f, sorted(Q2L, key=int)


# ── 변형문제 ────────────────────────────────────────────────
VR_LX, VR_RX, VR_FX, VR_TOP, VR_BOT = (16.0, 300.0), (304.0, 582.0), (16.0, 582.0), 45.0, 815.0


def vr_col(x):
    return 0 if x < 150 else 1


def vr_labs(blocks):
    return sorted([(vr_col(b[0]), b[1], LAB.match(b[4].strip()).group(1)) for b in blocks if LAB.match(b[4].strip())],
                  key=lambda z: (z[0], z[1]))


def vr_qnum(blocks, c, lo, hi):
    for b in sorted(blocks, key=lambda b: b[1]):
        if vr_col(b[0]) != c or not (lo - 2 <= b[1] < hi):
            continue
        m = QN.match(re.sub(r"\s+", " ", b[4]).strip())
        if m:
            return m.group(1)
    return None


def vr_lines(d, qend):
    lin = []
    for i, p in enumerate(d):
        if i < qend + 1:
            continue
        for b in sorted([x for x in p.get_text("blocks") if x[4].strip() and 38 < x[1] < VR_BOT],
                        key=lambda x: (vr_col(x[0]), x[1])):
            lin.append([i, vr_col(b[0]), b[1], b[3], re.sub(r"\s+", " ", b[4]).strip()])
    return lin


def vr_erase(d, targets, qend):
    COLS = {}
    for i in range(qend):
        bb = [b for b in d[i].get_text("blocks") if b[4].strip() and 38 < b[1] < VR_BOT]
        for c in (0, 1):
            cb = sorted([b for b in bb if vr_col(b[0]) == c], key=lambda b: b[1])
            if cb:
                COLS[(i, c)] = cb
    ORDER = sorted(COLS)
    POS = {k: j for j, k in enumerate(ORDER)}

    def contkill(pg, c):
        j = POS.get((pg, c))
        if j is None or j + 1 >= len(ORDER):
            return None
        key = ORDER[j + 1]
        cb = COLS[key]
        first = re.sub(r"\s+", " ", cb[0][4]).strip()
        if LAB.match(first) or QN.match(first) or first in HDRS or len(first) < 12:
            return None
        stop = None
        for b in cb:
            t = re.sub(r"\s+", " ", b[4]).strip()
            if LAB.match(t) or QN.match(t) or t in HDRS:
                stop = b[1]
                break
        y0 = cb[0][1] - 6
        y1 = (stop - 7) if stop else max(b[3] for b in cb) + 5
        xr = VR_LX if key[1] == 0 else VR_RX
        return (key[0], pymupdf.Rect(xr[0], max(VR_TOP, y0), xr[1], min(VR_BOT, y1)))
    kill, qnums = [], set()
    for i, p in enumerate(d):
        if i >= qend:
            break
        blocks = [b for b in p.get_text("blocks") if b[4].strip() and 38 < b[1] < VR_BOT]
        labs = vr_labs(blocks)
        if len(labs) == 1:
            c, y, n = labs[0]
            if n in targets:
                ext = max([b[3] for b in blocks], default=VR_BOT)
                kill.append((i, pymupdf.Rect(VR_FX[0], max(VR_TOP, y - 7), VR_FX[1], min(VR_BOT, ext + 5))))
                for cc in (0, 1):
                    q = vr_qnum(blocks, cc, y, VR_BOT)
                    if q:
                        qnums.add(q)
            continue
        for k, (c, y, n) in enumerate(labs):
            nxt = next((y2 for c2, y2, _ in labs[k + 1:] if c2 == c), None)
            lo = max(VR_TOP, y - 7)
            hi = (nxt - 7) if nxt else VR_BOT
            if n not in targets:
                continue
            inner = [b for b in blocks if vr_col(b[0]) == c and lo - 2 <= b[1] < hi]
            ext = max([b[3] for b in inner], default=hi)
            xr = VR_LX if c == 0 else VR_RX
            kill.append((i, pymupdf.Rect(xr[0], lo, xr[1], min(hi, ext + 5))))
            q = vr_qnum(blocks, c, lo, hi)
            if q:
                qnums.add(q)
            if nxt is None:
                ck = contkill(i, c)
                if ck:
                    kill.append(ck)
    if not qnums:
        fail("지울 문항을 하나도 못 찾음")
    lin = vr_lines(d, qend)
    marks = [(k, int(QN.match(t).group(1))) for k, (i, c, y0, y1, t) in enumerate(lin) if QN.match(t)]
    grp = {}
    for j, (k, v) in enumerate(marks):
        if str(v) in qnums:
            end = marks[j + 1][0] if j + 1 < len(marks) else len(lin)
            for i, c, y0, y1, t in lin[k:end]:
                g = grp.get((i, c))
                grp[(i, c)] = (min(g[0], y0), max(g[1], y1)) if g else (y0, y1)
    for (i, c), (y0, y1) in grp.items():
        xr = VR_LX if c == 0 else VR_RX
        kill.append((i, pymupdf.Rect(xr[0], y0 - 5, xr[1], y1 + 4)))
    byp = {}
    for i, r in kill:
        byp.setdefault(i, []).append(r)
    n = x_mark(d, byp)
    return sorted(qnums, key=int), n


def vr_extract(d, keep, qend, title, sub, tmp):
    items, qnums = [], set()
    for i, p in enumerate(d):
        if i >= qend:
            break
        blocks = [b for b in p.get_text("blocks") if b[4].strip() and 38 < b[1] < VR_BOT]
        labs = vr_labs(blocks)
        if len(labs) == 1:
            c, y, n = labs[0]
            if n in keep:
                ext = max([b[3] for b in blocks], default=VR_BOT)
                qq = [vr_qnum(blocks, cc, y, VR_BOT) for cc in (0, 1)]
                items.append((n, i, pymupdf.Rect(VR_FX[0], max(VR_TOP, y - 7), VR_FX[1], min(VR_BOT, ext + 5)), True,
                              [q for q in qq if q]))
                qnums.update(q for q in qq if q)
            continue
        for k, (c, y, n) in enumerate(labs):
            nxt = next((y2 for c2, y2, _ in labs[k + 1:] if c2 == c), None)
            lo = max(VR_TOP, y - 7)
            hi = (nxt - 7) if nxt else VR_BOT
            if n not in keep:
                continue
            inner = [b for b in blocks if vr_col(b[0]) == c and lo - 2 <= b[1] < hi]
            ext = max([b[3] for b in inner], default=hi)
            xr = VR_LX if c == 0 else VR_RX
            q = vr_qnum(blocks, c, lo, hi)
            items.append((n, i, pymupdf.Rect(xr[0], lo, xr[1], min(hi, ext + 5)), False, [q] if q else []))
            if q:
                qnums.add(q)
    if not items:
        fail("뽑을 문항을 하나도 못 찾음")
    Q2L = {q: n for n, i, r, full, qs in items for q in qs}
    ORD = {k: j for j, k in enumerate(keep)}
    items.sort(key=lambda x: (ORD[x[0]],))
    lin = vr_lines(d, qend)
    marks = [(k, int(QN.match(t).group(1))) for k, (i, c, y0, y1, t) in enumerate(lin) if QN.match(t)]
    sol = []
    for j, (k, v) in enumerate(marks):
        if str(v) in qnums:
            end = marks[j + 1][0] if j + 1 < len(marks) else len(lin)
            cur, lab = None, Q2L.get(str(v))
            for i, c, y0, y1, t in lin[k:end]:
                if cur and cur[0] == i and cur[1] == c:
                    cur[3] = max(cur[3], y1)
                else:
                    if cur:
                        sol.append(cur)
                    cur = [i, c, y0, y1, lab]
            if cur:
                sol.append(cur)
    SECS = ["%s번 지문 변형문제" % n for n in keep] + ["정답 및 해설 — %s번 지문" % n for n in keep]
    bt, bs = make_banners(title, sub.replace("{문항수}", str(len(qnums))), SECS, tmp)
    f = Flow(bt, bs, SECS)
    cur = None
    for n, i, r, full, qs in items:
        if n != cur:
            f.section("%s번 지문 변형문제" % n)
            cur = n
        f.place(d, i, r, full)
    sol.sort(key=lambda x: (ORD.get(x[4], 9),))
    cur = None
    for i, c, y0, y1, lab in sol:
        if lab != cur:
            f.section("정답 및 해설 — %s번 지문" % lab)
            cur = lab
        xr = VR_LX if c == 0 else VR_RX
        f.place(d, i, pymupdf.Rect(xr[0], y0 - 5, xr[1], y1 + 4), False)
    return f, sorted(qnums, key=int)


# ── 점검 ────────────────────────────────────────────────────
def check(rep, d, out_pdf, src_pages, idx, question_pages):
    """대상 지문 원문이 남았는지(지우기) / 대상 밖 지문이 섞였는지(뽑기) — 학평 원문 6-gram 으로 본다."""
    mode, targets = d["mode"], d["passages"]
    G = {n: grams6(v) for n, v in idx.items()}
    with pymupdf.open(out_pdf) as doc:
        pages = [p.get_text() for p in doc]
        if mode == "지우기":
            if len(doc) != src_pages:
                rep.add("쪽수", "원본 %d쪽인데 결과 %d쪽" % (src_pages, len(doc)))
            qtext = " ".join(pages[:question_pages])
            g = grams6(qtext)
            for n in targets:
                if n in G and G[n]:
                    left = len(G[n] & g) / len(G[n])
                    if left > 0.05:
                        rep.add("남음", "지울 %s번 지문 원문이 문항 쪽에 %.0f%% 남아 있음" % (n, left * 100))
            for n in (d.get("expect_kept") or []):
                if n in G and G[n] and len(G[n] & g) / len(G[n]) < 0.3:
                    rep.add("지나침", "남겨야 할 %s번 지문이 문항 쪽에서 거의 사라짐" % n)
        else:
            g_all = grams6(" ".join(pages))
            for n in targets:
                if n in G and G[n] and len(G[n] & g_all) / len(G[n]) < 0.3:
                    rep.add("누락", "뽑을 %s번 지문이 결과에 거의 없음" % n)
            for n, gg in G.items():
                if n in targets or not gg:
                    continue
                hit = len(gg & g_all) / len(gg)
                if hit > 0.15:
                    rep.add("섞임", "대상 밖 %s번 지문이 결과에 %.0f%% 섞여 있음" % (n, hit * 100))
        C.pdf_physical(rep, "결과", doc, min_chars=20, page_numbers=(mode == "뽑기"), bottom_free_warn=0.9)
        rep.note("결과 %d쪽" % len(doc))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out")
    a = ap.parse_args()
    d = json.loads(pathlib.Path(a.data).read_text(encoding="utf-8"))
    for k in ("name", "source", "book", "mode", "passages", "bynum"):
        if k not in d:
            raise SystemExit("data.json 에 '%s' 가 없다" % k)
    if d["book"] not in ("내신기출", "변형문제") or d["mode"] not in ("지우기", "뽑기"):
        raise SystemExit("book 은 내신기출/변형문제, mode 는 지우기/뽑기")
    if d.get("range") is not None and d["mode"] == "뽑기":
        extra = [p for p in d["passages"] if p not in d["range"]]
        if extra:
            raise SystemExit("범위 밖 지문 %s" % extra)
    g = d["bynum"]
    idx = S.load_json(S.BYNUM_DIR / ("%s_bynum.json" % g["grade"]))[g["round"]]
    src = pymupdf.open(S.path(d["source"]))
    src_pages = len(src)
    targets = set(d["passages"])
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gichul_"))
    try:
        rep = C.Report("%s · 기출가공 점검" % d["name"])
        out_pdf = tmp / (d["name"] + ".pdf")
        if d["book"] == "내신기출":
            sol_page = d["solution_after_page"]
            qpages = sol_page + 1
            if d["mode"] == "지우기":
                qs, n = kb_erase(src, targets, idx, sol_page)
                src.save(out_pdf, garbage=3, deflate=True)
                rep.note("지운 문항 %s · ✕ 블록 %d" % (qs, n))
            else:
                f, qs = kb_extract(src, d["passages"], idx, sol_page, d["title"], d["subtitle"], tmp)
                rep.note("뽑은 문항 %s" % qs)
                f.save(str(out_pdf))
        else:
            qend = d["question_pages"]
            qpages = qend
            if d["mode"] == "지우기":
                qs, n = vr_erase(src, targets, qend)
                src.save(out_pdf, garbage=3, deflate=True)
                rep.note("지운 문항 %d개 · ✕ 블록 %d" % (len(qs), n))
            else:
                f, qs = vr_extract(src, d["passages"], qend, d["title"], d["subtitle"], tmp)
                rep.note("뽑은 문항 %d개" % len(qs))
                f.save(str(out_pdf))
        src.close()
        check(rep, d, out_pdf, src_pages, idx, qpages)
        rep.stop_if_bad()
        dest = pathlib.Path(a.out) if a.out else pathlib.Path(a.data).resolve().parent
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_pdf, dest / out_pdf.name)
        print("저장", dest / out_pdf.name)
        rep.print()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
