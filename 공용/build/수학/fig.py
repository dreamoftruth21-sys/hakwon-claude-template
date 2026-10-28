# -*- coding: utf-8 -*-
"""수학 그림 — data.json 의 fig 를 파이썬이 계산해 SVG 로 그린다. 좌표를 손으로 짐작하지 않는다.

    svg, errors, notes = draw(fig, fid)

형식은 README.md 「그림(fig)」. 요약
    좌표 그림   {"x":[x0,x1], "y":[y0,y1], "w":56, "axes":true, "ticks":{...}, "points":{...}, "items":[...]}
    수직선     {"kind":"numberline", "range":[a,b], "ticks":[...], "marks":[...], "spans":[...]}
    직접 SVG   {"svg":"<svg …>…</svg>"}
점은 points 에 이름으로 정의한다 — 좌표 [x,y] 또는 작도 도우미(polar · foot · mid · divide · intersect · tangent · rotate · on_func).
계산은 sympy 로 정확히 하고, 그릴 때만 소수로 바꾼다.
흑백 인쇄: 선은 모두 검정, 보조선은 점선, 색칠은 빗금(hatch) 또는 회색.
"""
import html
import math
import re

import sympy as sp

X = sp.Symbol("x")
Y = sp.Symbol("y")
NS = {}
exec("from sympy import *", NS)
NS["x"], NS["y"] = X, Y

PAD = 4.0                 # 그림 둘레 여백 (mm) — 축 화살표 · 이름표 자리
FS = 3.2                  # 이름표 글자 크기 (mm) ≈ 9pt
MAX_W = 86.0              # 시험지 한 단 폭 안 (mm)
W_CURVE, W_LINE, W_AUX, W_AXIS = 0.32, 0.27, 0.2, 0.18
DASH = {"solid": "", "dashed": ' stroke-dasharray="1.3 0.8"', "dotted": ' stroke-dasharray="0.25 0.6" stroke-linecap="round"'}
GRAY = "#cfcfcf"
TOL = 1e-7


class FigError(Exception):
    pass


def num(v, where=""):
    try:
        e = sp.sympify(v, locals=dict(NS)) if isinstance(v, str) else sp.sympify(v)
    except Exception as ex:
        raise FigError("%s 값 '%s' 를 읽지 못함 (%s)" % (where, v, ex))
    return e


def f2(v):
    return float(sp.N(v))


def fmt(v):
    return ("%.3f" % v).rstrip("0").rstrip(".")


# ── 이름표 글자 ───────────────────────────────────────────────
def _tokens(s):
    """작은 수식 표기: 로마자는 기울임, ^ 위첨자 · _ 아래첨자 ({…} 또는 한 글자)."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c in "^_" and i + 1 < len(s):
            if s[i + 1] == "{":
                j = s.index("}", i + 1)
                out.append((c, s[i + 2:j]))
                i = j + 1
            else:
                out.append((c, s[i + 1]))
                i += 2
        else:
            out.append(("", c))
            i += 1
    return out


def _cw(c):
    if re.match("[가-힣]", c):
        return 0.95
    if c in "=+−<>≤≥":
        return 0.78
    if c == " ":
        return 0.25
    if c in "()[],.'°":
        return 0.36
    return 0.52


def text_width(s, fs=FS):
    if "$" in s:
        return len(re.sub(r"\\[a-z]+|[{}$^_]", "", s)) * 0.55 * fs + 0.5
    w = 0.0
    for kind, t in _tokens(s.replace("-", "−")):
        k = 0.7 if kind else 1.0
        w += sum(_cw(c) for c in t) * fs * k
    return w


def _run(t, fs):
    """글자 묶음 → tspan (소문자 변수는 기울임 KaTeX_Math, 점 이름 같은 대문자 · 숫자는 바로 선 KaTeX_Main)."""
    parts, cur, cur_it = [], "", None
    for c in t:
        it = bool(re.match("[a-z]", c))
        if cur and it != cur_it:
            parts.append((cur, cur_it))
            cur = ""
        cur += c
        cur_it = it
    if cur:
        parts.append((cur, cur_it))
    o = []
    for p, it in parts:
        p = html.escape(p.replace("=", " = ").replace("+", " + ").replace("<", " < ").replace(">", " > "))
        fam = "KaTeX_Math" if it else "KaTeX_Main,'Noto Sans KR','Malgun Gothic',sans-serif"
        o.append('<tspan font-family="%s"%s>%s</tspan>' % (fam, ' font-style="italic"' if it else "", p))
    return "".join(o)


def svg_text(s, cx, cy, fs=FS):
    """가운데 (cx,cy) 에 이름표. $…$ 가 있으면 KaTeX(foreignObject)."""
    w = text_width(s, fs)
    if "$" in s:
        h = fs * 1.6
        return ('<foreignObject x="%s" y="%s" width="%s" height="%s"><div xmlns="http://www.w3.org/1999/xhtml" '
                'class="flab" style="font-size:%smm;line-height:%smm;text-align:center;white-space:nowrap">%s</div>'
                '</foreignObject>' % (fmt(cx - w / 2 - 1), fmt(cy - h / 2), fmt(w + 2), fmt(h), fmt(fs * 0.86), fmt(h), s))
    s2 = s.replace("-", "−")
    b = ['<text x="%s" y="%s" font-size="%s" text-anchor="middle" xml:space="preserve">' % (fmt(cx), fmt(cy + 0.35 * fs), fmt(fs))]
    back = 0.0                              # 위 · 아래 첨자 뒤 기준선으로 돌아갈 만큼 (다음 글자 묶음에 붙인다)
    for kind, t in _tokens(s2):
        if kind in ("^", "_"):
            dy = (-0.42 if kind == "^" else 0.25) * fs
            b.append('<tspan dy="%s" font-size="%s">%s</tspan>' % (fmt(dy + back), fmt(0.7 * fs), _run(t, fs)))
            back = -dy
        elif back:
            b.append('<tspan dy="%s">%s</tspan>' % (fmt(back), _run(t, fs)))
            back = 0.0
        else:
            b.append(_run(t, fs))
    b.append("</text>")
    return "".join(b)


# ── 선분 자르기 (Liang–Barsky) ─────────────────────────────────
def clip(p, q, r):
    x0, y0, x1, y1 = r
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return None
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    if t0 > t1:
        return None
    return (p[0] + t0 * dx, p[1] + t0 * dy), (p[0] + t1 * dx, p[1] + t1 * dy)


class Figure:
    def __init__(self, spec, fid):
        self.spec, self.fid = spec, fid
        self.errors, self.notes = [], []
        self.P = {}                         # 이름 → (sympy x, sympy y)
        self.layers = {"shade": [], "grid": [], "axis": [], "geo": [], "mark": [], "dot": []}
        self.obst = []                      # 이름표가 피할 점 (종이 좌표)
        self.boxes = []                     # 놓인 이름표 상자
        self.labels = []                    # (글, 기준점, 선호 방향, 먼 쪽 기준점, 고정 위치)
        self.used = set()

    # 좌표 변환
    def setup(self):
        s = self.spec
        try:
            self.x0, self.x1 = [f2(num(v, "x 범위")) for v in s["x"]]
            self.y0, self.y1 = [f2(num(v, "y 범위")) for v in s["y"]]
        except KeyError:
            raise FigError("x · y 범위가 없다")
        if not (self.x0 < self.x1 and self.y0 < self.y1):
            raise FigError("범위가 거꾸로다")
        self.equal = s.get("equal", True)
        if self.equal:
            if "h" in s and "w" not in s:
                self.sx = self.sy = s["h"] / (self.y1 - self.y0)
            else:
                self.sx = self.sy = s.get("w", 52) / (self.x1 - self.x0)
                if "h" in s:
                    self.notes.append("equal 축척이라 h 는 무시했다")
        else:
            self.sx = s.get("w", 52) / (self.x1 - self.x0)
            self.sy = s.get("h", 40) / (self.y1 - self.y0)
        self.W = (self.x1 - self.x0) * self.sx + 2 * PAD
        self.H = (self.y1 - self.y0) * self.sy + 2 * PAD
        if self.W > MAX_W:
            self.errors.append("그림 폭 %.0fmm — 한 단(%.0fmm)을 넘는다. w 를 줄인다" % (self.W, MAX_W))
        self.win = (PAD, PAD, self.W - PAD, self.H - PAD)

    def X(self, x):
        return PAD + (x - self.x0) * self.sx

    def Yp(self, y):
        return PAD + (self.y1 - y) * self.sy

    def pp(self, pt):
        return (self.X(f2(pt[0])), self.Yp(f2(pt[1])))

    def inside(self, pt, eps=1e-6):
        x, y = f2(pt[0]), f2(pt[1])
        return self.x0 - eps <= x <= self.x1 + eps and self.y0 - eps <= y <= self.y1 + eps

    # ── 점 정의 ──
    def pt(self, ref, where=""):
        if isinstance(ref, str):
            if ref not in self.P:
                raise FigError("%s 점 '%s' 가 정의되지 않았다 (points 에서 먼저 정의)" % (where, ref))
            self.used.add(ref)
            return self.P[ref]
        if isinstance(ref, (list, tuple)) and len(ref) == 2:
            return (num(ref[0], where), num(ref[1], where))
        raise FigError("%s 점 '%s' 형식" % (where, ref))

    def curve_eq(self, o, where):
        """교점 대상 → x, y 에 대한 식 = 0"""
        if "line" in o:
            a, b = (self.pt(r, where) for r in o["line"])
            return (Y - a[1]) * (b[0] - a[0]) - (X - a[0]) * (b[1] - a[1])
        if "circle" in o:
            c = self.pt(o["circle"][0], where)
            r = o["circle"][1]
            r2 = ((self.pt(r)[0] - c[0]) ** 2 + (self.pt(r)[1] - c[1]) ** 2) if isinstance(r, str) and r in self.P \
                else num(r, where) ** 2
            return (X - c[0]) ** 2 + (Y - c[1]) ** 2 - r2
        if "func" in o:
            return Y - num(o["func"], where)
        if "hline" in o:
            return Y - num(o["hline"], where)
        if "vline" in o:
            return X - num(o["vline"], where)
        raise FigError("%s 교점 대상은 line · circle · func · hline · vline" % where)

    @staticmethod
    def pick(sols, how, where):
        sols = sorted(sols, key=lambda p: (f2(p[0]), f2(p[1])))
        if not sols:
            raise FigError("%s 교점이 없다" % where)
        if isinstance(how, int):
            if not -len(sols) <= how < len(sols):
                raise FigError("%s 교점 %d개인데 pick %d" % (where, len(sols), how))
            return sols[how]
        key = {"left": lambda p: f2(p[0]), "right": lambda p: -f2(p[0]),
               "lower": lambda p: f2(p[1]), "upper": lambda p: -f2(p[1])}.get(how)
        if not key:
            raise FigError("%s pick 은 번호 또는 left/right/upper/lower" % where)
        return min(sols, key=key)

    def solve2(self, e1, e2, where):
        try:
            res = sp.solve([e1, e2], [X, Y], dict=True)
        except Exception as ex:
            raise FigError("%s 교점 계산 실패 (%s)" % (where, ex))
        out = []
        for r in res:
            if X in r and Y in r:
                px, py = sp.simplify(r[X]), sp.simplify(r[Y])
                if abs(complex(sp.N(px)).imag) < 1e-12 and abs(complex(sp.N(py)).imag) < 1e-12:
                    out.append((px, py))
        return out

    def define(self, name, d):
        w = "점 %s:" % name
        if isinstance(d, (list, tuple)):
            return (num(d[0], w), num(d[1], w))
        if not isinstance(d, dict):
            raise FigError("%s 형식" % w)
        if "polar" in d or "on_circle" in d:
            c, r, deg = d.get("polar") or d.get("on_circle")
            c = self.pt(c, w)
            r, t = num(r, w), num(deg, w) * sp.pi / 180
            return (sp.simplify(c[0] + r * sp.cos(t)), sp.simplify(c[1] + r * sp.sin(t)))
        if "foot" in d:
            p, a, b = (self.pt(r, w) for r in d["foot"])
            ux, uy = b[0] - a[0], b[1] - a[1]
            t = ((p[0] - a[0]) * ux + (p[1] - a[1]) * uy) / (ux ** 2 + uy ** 2)
            return (sp.simplify(a[0] + t * ux), sp.simplify(a[1] + t * uy))
        if "mid" in d:
            a, b = (self.pt(r, w) for r in d["mid"])
            return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if "divide" in d:
            a, b, m, n = d["divide"]
            a, b, m, n = self.pt(a, w), self.pt(b, w), num(m, w), num(n, w)
            return (sp.simplify((n * a[0] + m * b[0]) / (m + n)), sp.simplify((n * a[1] + m * b[1]) / (m + n)))
        if "rotate" in d:
            a, c, deg = d["rotate"]
            a, c, t = self.pt(a, w), self.pt(c, w), num(deg, w) * sp.pi / 180
            dx, dy = a[0] - c[0], a[1] - c[1]
            return (sp.simplify(c[0] + dx * sp.cos(t) - dy * sp.sin(t)), sp.simplify(c[1] + dx * sp.sin(t) + dy * sp.cos(t)))
        if "on_func" in d:
            f, x = d["on_func"]
            x = num(x, w)
            return (x, sp.simplify(num(f, w).subs(X, x)))
        if "intersect" in d:
            o1, o2 = d["intersect"]
            sols = self.solve2(self.curve_eq(o1, w), self.curve_eq(o2, w), w)
            return self.pick(sols, d.get("pick", 0), w)
        if "tangent" in d:          # 원 (중심, 반지름) 밖의 점 P 에서 그은 접선의 접점
            c, r, p = d["tangent"]
            c, r, p = self.pt(c, w), num(r, w), self.pt(p, w)
            e1 = (X - c[0]) ** 2 + (Y - c[1]) ** 2 - r ** 2
            e2 = (X - c[0]) * (X - p[0]) + (Y - c[1]) * (Y - p[1])
            return self.pick(self.solve2(e1, e2, w), d.get("pick", 0), w)
        raise FigError("%s 작도 도우미는 polar · foot · mid · divide · rotate · on_func · intersect · tangent" % w)

    # ── 그리기 도우미 ──
    def poly_path(self, pts):
        return "M" + " L".join("%s %s" % (fmt(a), fmt(b)) for a, b in pts)

    def stroke(self, style, width):
        if style not in DASH:
            raise FigError("style 은 solid · dashed · dotted")
        return 'fill="none" stroke="#000" stroke-width="%s"%s' % (fmt(width), DASH[style])

    def add_obst(self, pts, step=0.45):
        for (a, b), (c, d) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(c - a, d - b) / step))
            for k in range(n + 1):
                self.obst.append((a + (c - a) * k / n, b + (d - b) * k / n))

    def seg_world(self, a, b, style, width, layer="geo"):
        p, q = self.pp(a), self.pp(b)
        self.layers[layer].append('<path d="%s" %s/>' % (self.poly_path([p, q]), self.stroke(style, width)))
        self.add_obst([p, q])
        return p, q

    def arrowhead(self, p, q, size=1.6, layer="geo"):
        """q 쪽 끝 화살촉 (p → q 방향)."""
        ang = math.atan2(q[1] - p[1], q[0] - p[0])
        a1, a2 = ang + math.radians(155), ang - math.radians(155)
        pts = [q, (q[0] + size * math.cos(a1), q[1] + size * math.sin(a1)),
               (q[0] + size * math.cos(a2), q[1] + size * math.sin(a2))]
        self.layers[layer].append('<path d="%s Z" fill="#000" stroke="none"/>' % self.poly_path(pts))

    def check_in(self, refs, what):
        for r in refs:
            p = self.pt(r, what)
            if not self.inside(p):
                self.errors.append("%s 의 점 %s (%.2f, %.2f) 가 그림 범위 밖" % (what, r, f2(p[0]), f2(p[1])))

    def label(self, text, anchor, pos="auto", away=None, gap=1.0):
        if text:
            self.labels.append((text, anchor, pos, away, gap))

    # ── 축 · 눈금 ──
    def axes(self):
        a = self.spec.get("axes")
        if not a:
            return
        a = a if isinstance(a, dict) else {}
        L, T_, R, B = self.win
        ext = 2.5
        if self.y0 <= 0 <= self.y1:
            y = self.Yp(0)
            p, q = (L - 1.0, y), (R + ext, y)
            self.layers["axis"].append('<path d="%s" %s/>' % (self.poly_path([p, q]), self.stroke("solid", W_AXIS)))
            self.arrowhead(p, q, 1.4, "axis")
            self.add_obst([p, q])
            self.place_fixed(a.get("x", "x"), (q[0] - 0.4, y + 2.6))
        else:
            self.notes.append("y=0 이 범위 밖이라 x축을 그리지 않았다")
        if self.x0 <= 0 <= self.x1:
            x = self.X(0)
            p, q = (x, B + 1.0), (x, T_ - ext)
            self.layers["axis"].append('<path d="%s" %s/>' % (self.poly_path([p, q]), self.stroke("solid", W_AXIS)))
            self.arrowhead(p, q, 1.4, "axis")
            self.add_obst([p, q])
            self.place_fixed(a.get("y", "y"), (x + 2.4, q[1] + 0.9))
        else:
            self.notes.append("x=0 이 범위 밖이라 y축을 그리지 않았다")
        if a.get("origin", "O") and self.x0 <= 0 <= self.x1 and self.y0 <= 0 <= self.y1:
            self.place_fixed(a.get("origin", "O"), (self.X(0) - 2.0, self.Yp(0) + 2.4))
        tk = self.spec.get("ticks", {})
        for v in tk.get("x", []):
            v, t = (v["v"], v.get("t")) if isinstance(v, dict) else (v, None)
            xv = f2(num(v, "눈금"))
            if not self.x0 <= xv <= self.x1:
                self.errors.append("x 눈금 %s 가 범위 밖" % v)
                continue
            px, py = self.X(xv), self.Yp(0) if self.y0 <= 0 <= self.y1 else self.win[3]
            self.layers["axis"].append('<path d="M%s %s L%s %s" %s/>' % (fmt(px), fmt(py - 0.7), fmt(px), fmt(py + 0.7),
                                                                         self.stroke("solid", W_AXIS)))
            self.place_fixed(t if t is not None else _numtxt(v), (px, py + 2.6))
        for v in tk.get("y", []):
            v, t = (v["v"], v.get("t")) if isinstance(v, dict) else (v, None)
            yv = f2(num(v, "눈금"))
            if not self.y0 <= yv <= self.y1:
                self.errors.append("y 눈금 %s 가 범위 밖" % v)
                continue
            px, py = self.X(0) if self.x0 <= 0 <= self.x1 else self.win[0], self.Yp(yv)
            self.layers["axis"].append('<path d="M%s %s L%s %s" %s/>' % (fmt(px - 0.7), fmt(py), fmt(px + 0.7), fmt(py),
                                                                         self.stroke("solid", W_AXIS)))
            s = t if t is not None else _numtxt(v)
            self.place_fixed(s, (px - 1.2 - text_width(s) / 2, py))

    def grid(self):
        g = self.spec.get("grid")
        if not g:
            return
        step = g if isinstance(g, (int, float)) and not isinstance(g, bool) else 1
        L, T_, R, B = self.win
        k = math.ceil(self.x0 / step)
        while k * step <= self.x1 + 1e-9:
            x = self.X(k * step)
            self.layers["grid"].append('<path d="M%s %s L%s %s" stroke="#999" stroke-width="0.12" stroke-dasharray="0.3 0.5"/>'
                                       % (fmt(x), fmt(T_), fmt(x), fmt(B)))
            k += 1
        k = math.ceil(self.y0 / step)
        while k * step <= self.y1 + 1e-9:
            y = self.Yp(k * step)
            self.layers["grid"].append('<path d="M%s %s L%s %s" stroke="#999" stroke-width="0.12" stroke-dasharray="0.3 0.5"/>'
                                       % (fmt(L), fmt(y), fmt(R), fmt(y)))
            k += 1

    def place_fixed(self, text, center):
        if not text:
            return
        w, h = text_width(text), FS * 1.05
        box = (center[0] - w / 2, center[1] - h / 2, center[0] + w / 2, center[1] + h / 2)
        self.boxes.append(box)
        self.layers["dot"].append(svg_text(text, center[0], center[1]))

    # ── 항목 ──
    def item(self, it, k):
        t = it.get("type")
        w = "items[%d] %s:" % (k, t)
        style = it.get("style", "solid")
        if t == "func":
            self.func(it, w)
        elif t == "point":
            refs = it["at"] if isinstance(it["at"], list) and it["at"] and isinstance(it["at"][0], str) else [it["at"]]
            for r in refs:
                p = self.pt(r, w)
                if not self.inside(p):
                    self.errors.append("%s 점 %s 가 그림 범위 밖" % (w, r))
                c = self.pp(p)
                dot = it.get("dot", "filled")
                if dot == "filled":
                    self.layers["dot"].append('<circle cx="%s" cy="%s" r="0.55" fill="#000"/>' % (fmt(c[0]), fmt(c[1])))
                elif dot == "open":
                    self.layers["dot"].append('<circle cx="%s" cy="%s" r="0.6" fill="#fff" stroke="#000" stroke-width="0.2"/>'
                                              % (fmt(c[0]), fmt(c[1])))
                self.obst.append(c)
                lab = it.get("label", r if isinstance(r, str) else "")
                if len(refs) > 1:
                    lab = r if it.get("label", True) is not False else ""
                self.label(lab, c, it.get("pos", "auto"), self.centroid())
        elif t in ("segment", "vector", "polyline"):
            pts = it.get("pts") or [it["from"], it["to"]]
            self.check_in(pts, w)
            P = [self.pt(r, w) for r in pts]
            pp = [self.pp(p) for p in P]
            width = it.get("width", W_AUX if style != "solid" else W_LINE)
            self.layers["geo"].append('<path d="%s" %s/>' % (self.poly_path(pp), self.stroke(style, width)))
            self.add_obst(pp)
            if t == "vector" or it.get("arrow"):
                self.arrowhead(pp[-2], pp[-1])
            if it.get("label"):
                self.side_label(it["label"], pp[0], pp[-1], it.get("pos", "auto"))
        elif t == "polygon":
            pts = it["pts"]
            self.check_in(pts, w)
            pp = [self.pp(self.pt(r, w)) for r in pts]
            fill = it.get("fill", "none")
            if fill != "none":
                self.layers["shade"].append('<path d="%s Z" %s stroke="none"/>' % (self.poly_path(pp), self.fill(fill, w)))
            self.layers["geo"].append('<path d="%s Z" %s/>' % (self.poly_path(pp), self.stroke(style, it.get("width", W_LINE))))
            self.add_obst(pp + [pp[0]])
        elif t in ("line", "ray"):
            self.line(it, w, t)
        elif t == "circle":
            c = self.pt(it["center"], w)
            r = self.radius(it, c, w)
            cx, cy = self.pp(c)
            rp = f2(r) * self.sx
            if not self.equal:
                self.errors.append("%s 원은 equal 축척에서만 그린다" % w)
            if (f2(c[0]) - f2(r) < self.x0 - 1e-6 or f2(c[0]) + f2(r) > self.x1 + 1e-6
                    or f2(c[1]) - f2(r) < self.y0 - 1e-6 or f2(c[1]) + f2(r) > self.y1 + 1e-6):
                self.errors.append("%s 원이 그림 범위를 넘는다" % w)
            self.layers["geo"].append('<circle cx="%s" cy="%s" r="%s" %s/>' % (fmt(cx), fmt(cy), fmt(rp),
                                                                              self.stroke(style, it.get("width", W_LINE))))
            self.add_obst([(cx + rp * math.cos(a), cy + rp * math.sin(a)) for a in
                           [2 * math.pi * k / 180 for k in range(181)]])
        elif t == "arc":
            c = self.pt(it["center"], w)
            r = f2(self.radius(it, c, w))
            a0, a1 = f2(num(it["from"], w)), f2(num(it["to"], w))
            if a1 < a0:
                a1 += 360
            pts = [(f2(c[0]) + r * math.cos(math.radians(a0 + (a1 - a0) * k / 120)),
                    f2(c[1]) + r * math.sin(math.radians(a0 + (a1 - a0) * k / 120))) for k in range(121)]
            for p in pts:
                if not self.inside(p):
                    self.errors.append("%s 호가 그림 범위를 넘는다" % w)
                    break
            pp = [self.pp(p) for p in pts]
            self.layers["geo"].append('<path d="%s" %s/>' % (self.poly_path(pp), self.stroke(style, it.get("width", W_LINE))))
            self.add_obst(pp)
        elif t == "angle":
            self.angle(it, w)
        elif t == "right":
            self.right(it, w)
        elif t == "equal":
            self.equal_marks(it, w)
        elif t == "label":
            if "mid" in it:
                a, b = (self.pp(self.pt(r, w)) for r in it["mid"])
                self.side_label(it["text"], a, b, it.get("pos", "auto"))
            else:
                p = self.pt(it["at"], w)
                if not self.inside(p):
                    self.errors.append("%s 이름표 위치가 그림 범위 밖" % w)
                self.label(it["text"], self.pp(p), it.get("pos", "auto"), self.centroid())
        elif t == "shade":
            self.shade(it, w)
        elif t == "guides":
            p = self.pt(it["at"], w)
            to = it.get("to", "both")
            if to in ("x", "both"):
                self.seg_world(p, (p[0], 0), "dashed", W_AUX)
            if to in ("y", "both"):
                self.seg_world(p, (0, p[1]), "dashed", W_AUX)
        else:
            raise FigError("%s 모르는 type (func · point · segment · vector · polyline · polygon · line · ray · circle · "
                           "arc · angle · right · equal · label · shade · guides)" % w)

    def radius(self, it, c, w):
        if "through" in it:
            p = self.pt(it["through"], w)
            return sp.sqrt((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2)
        return num(it["r"], w)

    def centroid(self):
        pts = [self.pp(p) for n, p in self.P.items() if n in self.used] or [((self.W) / 2, self.H / 2)]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    def fill(self, fill, w):
        if fill == "gray":
            return 'fill="%s"' % GRAY
        if fill == "hatch":
            return 'fill="url(#hatch%s)"' % self.fid
        raise FigError("%s fill 은 none · gray · hatch" % w)

    def side_label(self, text, a, b, pos):
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        self.label(text, m, pos, self.centroid(), gap=0.8)

    def sample(self, f, a, b, n=900):
        """f(x) 를 [a,b] 에서 — 점근선(정의되지 않는 곳)에서 끊어진 조각 목록 (세계 좌표)."""
        fl = sp.lambdify(X, f, "math")
        try:
            sing = sorted(f2(s) for s in sp.singularities(f, X, sp.Interval(a, b)) if s.is_real)
        except Exception:
            sing = []
        cuts = [a] + [s for s in sing if a < s < b] + [b]
        span = self.y1 - self.y0
        pieces = []
        for lo, hi in zip(cuts, cuts[1:]):
            eps = (hi - lo) * 1e-4 if (lo in sing or hi in sing) else 0
            lo2, hi2 = lo + (eps if lo in sing else 0), hi - (eps if hi in sing else 0)
            cur, prev = [], None
            m = max(60, int(n * (hi2 - lo2) / max(b - a, 1e-9)))
            for k in range(m + 1):
                x = lo2 + (hi2 - lo2) * k / m
                try:
                    y = fl(x)
                    y = float(y.real) if isinstance(y, complex) and abs(y.imag) < 1e-12 else float(y)
                    ok = math.isfinite(y)
                except Exception:
                    ok = False
                if ok and prev is not None and abs(y - prev) > 3 * span and (y > 0) != (prev > 0):
                    ok = False          # 놓친 점근선
                if not ok:
                    if len(cur) > 1:
                        pieces.append(cur)
                    cur, prev = [], None
                    continue
                cur.append((x, y))
                prev = y
            if len(cur) > 1:
                pieces.append(cur)
        return pieces

    def clip_pieces(self, pieces):
        """세계 좌표 조각 → 그림 창에 잘린 종이 좌표 조각."""
        out = []
        r = (self.x0, self.y0, self.x1, self.y1)
        for pc in pieces:
            cur = []
            for p, q in zip(pc, pc[1:]):
                c = clip(p, q, r)
                if c is None:
                    if len(cur) > 1:
                        out.append(cur)
                    cur = []
                    continue
                a, b = self.pp(c[0]), self.pp(c[1])
                if not cur:
                    cur = [a]
                elif math.hypot(cur[-1][0] - a[0], cur[-1][1] - a[1]) > 1e-6:
                    if len(cur) > 1:
                        out.append(cur)
                    cur = [a]
                cur.append(b)
            if len(cur) > 1:
                out.append(cur)
        return out

    def func(self, it, w):
        f = num(it["f"], w)
        a, b = [f2(num(v, w)) for v in it.get("domain", [self.x0, self.x1])]
        a, b = max(a, self.x0), min(b, self.x1)
        pieces = self.clip_pieces(self.sample(f, a, b))
        if not pieces:
            self.errors.append("%s 그래프가 그림 범위 안에 하나도 없다" % w)
            return
        style = it.get("style", "solid")
        d = " ".join(self.poly_path(pc) for pc in pieces)
        self.layers["geo"].append('<path d="%s" %s stroke-linejoin="round"/>' % (d, self.stroke(style, it.get("width", W_CURVE))))
        for pc in pieces:
            self.add_obst(pc)
        if it.get("label"):
            xl = f2(num(it["label_at"], w)) if "label_at" in it else None
            if xl is None:
                last = pieces[-1][-1]
                anchor = last
            else:
                yl = f2(f.subs(X, xl))
                anchor = self.pp((xl, yl))
            self.label(it["label"], anchor, it.get("pos", "auto"), self.centroid(), gap=1.2)

    def line(self, it, w, t):
        if "x" in it and "pts" not in it:
            xv = num(it["x"], w)
            a, b = (xv, self.y0), (xv, self.y1)
        elif "y" in it and "pts" not in it:
            yv = num(it["y"], w)
            a, b = (self.x0, yv), (self.x1, yv)
        elif "slope" in it:
            a = self.pt(it["through"], w)
            m = num(it["slope"], w)
            b = (a[0] + 1, a[1] + m)
        else:
            a, b = (self.pt(r, w) for r in it["pts"])
        a, b = (f2(a[0]), f2(a[1])), (f2(b[0]), f2(b[1]))
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx == dy == 0:
            raise FigError("%s 두 점이 같다" % w)
        big = 1e4
        p = a if t == "ray" else (a[0] - big * dx, a[1] - big * dy)
        q = (a[0] + big * dx, a[1] + big * dy)
        c = clip(p, q, (self.x0, self.y0, self.x1, self.y1))
        if c is None:
            self.errors.append("%s 직선이 그림 범위를 지나지 않는다" % w)
            return
        style = it.get("style", "solid")
        pa, pb = self.pp(c[0]), self.pp(c[1])
        self.layers["geo"].append('<path d="%s" %s/>' % (self.poly_path([pa, pb]),
                                                         self.stroke(style, it.get("width", W_LINE if style == "solid" else W_AUX))))
        self.add_obst([pa, pb])
        if it.get("label"):
            self.label(it["label"], pb, it.get("pos", "auto"), self.centroid(), gap=1.2)

    def vecs(self, it, w):
        v = self.pt(it["at"], w)
        a, b = self.pt(it["from"], w), self.pt(it["to"], w)
        return v, a, b

    @staticmethod
    def world_angle(v, a, b):
        ax, ay = f2(a[0] - v[0]), f2(a[1] - v[1])
        bx, by = f2(b[0] - v[0]), f2(b[1] - v[1])
        c = (ax * bx + ay * by) / (math.hypot(ax, ay) * math.hypot(bx, by))
        return math.degrees(math.acos(max(-1.0, min(1.0, c))))

    def angle(self, it, w):
        v, a, b = self.vecs(it, w)
        if not self.equal:
            self.errors.append("%s 각 표시는 equal 축척에서만" % w)
        real = self.world_angle(v, a, b)
        if "deg" in it and abs(real - f2(num(it["deg"], w))) > 1e-6:
            self.errors.append("%s 각 %s°라 했는데 그림의 실제 각은 %.4f°" % (w, it["deg"], real))
        V, A, B = self.pp(v), self.pp(a), self.pp(b)
        t1 = math.atan2(A[1] - V[1], A[0] - V[0])
        t2 = math.atan2(B[1] - V[1], B[0] - V[0])
        d = (t2 - t1) % (2 * math.pi)
        if d > math.pi:
            t1, d = t2, 2 * math.pi - d
        r = it.get("r", 3.2)
        for k in range(int(it.get("arcs", 1))):
            rr = r + 0.6 * k
            pts = [(V[0] + rr * math.cos(t1 + d * j / 40), V[1] + rr * math.sin(t1 + d * j / 40)) for j in range(41)]
            self.layers["mark"].append('<path d="%s" %s/>' % (self.poly_path(pts), self.stroke("solid", W_AUX)))
            self.add_obst(pts)
        if it.get("label"):
            tm = t1 + d / 2
            s = it["label"]
            wd, ht = text_width(s), FS
            dist = r + 0.6 * (int(it.get("arcs", 1)) - 1) + 0.9 + 0.5 * math.hypot(wd * math.cos(tm), ht * math.sin(tm))
            self.labels.append((s, (V[0] + dist * math.cos(tm), V[1] + dist * math.sin(tm)), "c", None, 0))

    def right(self, it, w):
        v, a, b = self.vecs(it, w)
        real = self.world_angle(v, a, b)
        if abs(real - 90) > 1e-6:
            self.errors.append("%s 직각 표시인데 실제 각은 %.4f°" % (w, real))
        if not self.equal:
            self.errors.append("%s 직각 표시는 equal 축척에서만" % w)
        V, A, B = self.pp(v), self.pp(a), self.pp(b)
        s = it.get("size", 2.0)
        ua = ((A[0] - V[0]) / math.hypot(A[0] - V[0], A[1] - V[1]), (A[1] - V[1]) / math.hypot(A[0] - V[0], A[1] - V[1]))
        ub = ((B[0] - V[0]) / math.hypot(B[0] - V[0], B[1] - V[1]), (B[1] - V[1]) / math.hypot(B[0] - V[0], B[1] - V[1]))
        pts = [(V[0] + s * ua[0], V[1] + s * ua[1]), (V[0] + s * (ua[0] + ub[0]), V[1] + s * (ua[1] + ub[1])),
               (V[0] + s * ub[0], V[1] + s * ub[1])]
        self.layers["mark"].append('<path d="%s" %s/>' % (self.poly_path(pts), self.stroke("solid", W_AUX)))
        self.add_obst(pts)

    def equal_marks(self, it, w):
        segs = it["segs"]
        n = int(it.get("ticks", 1))
        lens = []
        for s in segs:
            a, b = self.pt(s[0], w), self.pt(s[1], w)
            lens.append(sp.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2))
            A, B = self.pp(a), self.pp(b)
            L = math.hypot(B[0] - A[0], B[1] - A[1])
            u = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
            nrm = (-u[1], u[0])
            m = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
            for k in range(n):
                off = (k - (n - 1) / 2) * 0.7
                c = (m[0] + u[0] * off, m[1] + u[1] * off)
                p1 = (c[0] + nrm[0] * 1.1, c[1] + nrm[1] * 1.1)
                p2 = (c[0] - nrm[0] * 1.1, c[1] - nrm[1] * 1.1)
                self.layers["mark"].append('<path d="%s" %s/>' % (self.poly_path([p1, p2]), self.stroke("solid", W_LINE)))
        for s, L in zip(segs[1:], lens[1:]):
            if abs(f2(L - lens[0])) > TOL:
                self.errors.append("%s 같은 길이 표시인데 %s%s=%.4f, %s%s=%.4f"
                                   % (w, segs[0][0], segs[0][1], f2(lens[0]), s[0], s[1], f2(L)))

    def shade(self, it, w):
        fill = self.fill(it.get("fill", "hatch"), w)
        if "pts" in it:
            self.check_in(it["pts"], w)
            pp = [self.pp(self.pt(r, w)) for r in it["pts"]]
        elif "between" in it:
            f, g = (num(e, w) for e in it["between"])
            a, b = [f2(num(v, w)) for v in it["domain"]]
            fl, gl = sp.lambdify(X, f, "math"), sp.lambdify(X, g, "math")
            n = 300
            xs = [a + (b - a) * k / n for k in range(n + 1)]
            try:
                top = [(x, float(fl(x))) for x in xs]
                bot = [(x, float(gl(x))) for x in reversed(xs)]
            except Exception as ex:
                raise FigError("%s 색칠 구간에서 함수값 계산 실패 (%s)" % (w, ex))
            for p in top + bot:
                if not self.inside(p, 1e-6):
                    self.errors.append("%s 색칠한 부분이 그림 범위를 넘는다" % w)
                    break
            pp = [self.pp(p) for p in top + bot]
        else:
            raise FigError("%s shade 는 pts 또는 between+domain" % w)
        self.layers["shade"].append('<path d="%s Z" %s stroke="none"/>' % (self.poly_path(pp), fill))

    # ── 이름표 놓기 ──
    def place_labels(self):
        L, T_, R, B = 0.3, 0.3, self.W - 0.3, self.H - 0.3
        dirs = {"ne": 45, "nw": 135, "sw": 225, "se": 315, "e": 0, "n": 90, "w": 180, "s": 270}
        order = ["ne", "nw", "se", "sw", "e", "w", "n", "s"]
        for text, anchor, pos, away, gap in self.labels:
            wd, ht = text_width(text), FS * 1.05
            if pos == "c":
                cands = [("c", anchor)]
            else:
                names = [pos] if pos in dirs else order
                if pos not in dirs and pos != "auto":
                    self.errors.append("이름표 '%s' pos 는 auto · n · ne · e · se · s · sw · w · nw" % text)
                cands = []
                for ring in (gap, gap + 1.6, gap + 3.2):
                    for nm in names:
                        t = math.radians(dirs[nm])
                        dx, dy = math.cos(t), -math.sin(t)
                        cands.append((nm, (anchor[0] + dx * (wd / 2 + ring), anchor[1] + dy * (ht / 2 + ring))))
            best = None
            for i, (nm, c) in enumerate(cands):
                box = (c[0] - wd / 2, c[1] - ht / 2, c[0] + wd / 2, c[1] + ht / 2)
                hit = sum(1 for p in self.obst if box[0] - 0.25 <= p[0] <= box[2] + 0.25 and box[1] - 0.25 <= p[1] <= box[3] + 0.25)
                over = sum(1 for b in self.boxes if not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]))
                out = box[0] < L or box[1] < T_ or box[2] > R or box[3] > B
                score = hit * 10 + over * 1000 + (100000 if out else 0) + i * 0.5
                if away is not None and nm != "c":
                    vx, vy = c[0] - anchor[0], c[1] - anchor[1]
                    ax, ay = anchor[0] - away[0], anchor[1] - away[1]
                    if math.hypot(ax, ay) > 1e-6:
                        score -= 3 * (vx * ax + vy * ay) / (math.hypot(vx, vy) * math.hypot(ax, ay))
                if best is None or score < best[0]:
                    best = (score, c, box, hit, over, out)
            score, c, box, hit, over, out = best
            if out:
                self.errors.append("이름표 '%s' 가 그림 밖으로 나간다 — 범위를 넓히거나 pos 를 정한다" % text)
            elif over:
                self.errors.append("이름표 '%s' 가 다른 이름표와 겹친다 — pos 를 정한다" % text)
            elif hit and pos == "auto":
                self.notes.append("이름표 '%s' 가 선에 닿는다 (눈으로 확인 · 필요하면 pos)" % text)
            self.boxes.append(box)
            self.layers["dot"].append(svg_text(text, c[0], c[1]))

    def asserts(self):
        env = dict(NS)
        env.update({n: sp.Point(p[0], p[1]) for n, p in self.P.items()})
        env["dist"] = lambda a, b: a.distance(b)
        env["angle"] = lambda a, v, b: sp.deg(sp.acos(((a - v).dot(b - v)) / ((a - v).distance(sp.Point(0, 0)) *
                                                                             (b - v).distance(sp.Point(0, 0)))))
        for lhs, rhs in self.spec.get("asserts", []):
            try:
                l, r = eval(lhs, env), eval(str(rhs), env)
                ok = abs(f2(sp.sympify(l) - sp.sympify(r))) < 1e-9
            except Exception as ex:
                self.errors.append("asserts %s 계산 실패 (%s)" % (lhs, ex))
                continue
            if not ok:
                self.errors.append("asserts %s = %s 가 아니다 (실제 %.6f)" % (lhs, rhs, f2(l)))

    def render(self):
        self.setup()
        for name, d in self.spec.get("points", {}).items():
            try:
                self.P[name] = self.define(name, d)
            except FigError as e:
                self.errors.append(str(e))
                self.P[name] = (sp.Integer(0), sp.Integer(0))
        self.grid()
        self.axes()
        for k, it in enumerate(self.spec.get("items", [])):
            try:
                self.item(it, k)
            except FigError as e:
                self.errors.append(str(e))
            except KeyError as e:
                self.errors.append("items[%d] %s: %s 가 없다" % (k, it.get("type"), e))
        self.asserts()
        self.place_labels()
        return self.wrap()

    def wrap(self):
        defs = ('<defs><pattern id="hatch%s" patternUnits="userSpaceOnUse" width="1.3" height="1.3" '
                'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="1.3" stroke="#000" stroke-width="0.16"/>'
                '</pattern><clipPath id="win%s"><rect x="%s" y="%s" width="%s" height="%s"/></clipPath></defs>'
                % (self.fid, self.fid, fmt(PAD), fmt(PAD), fmt(self.W - 2 * PAD), fmt(self.H - 2 * PAD)))
        body = ['<g clip-path="url(#win%s)">%s</g>' % (self.fid, "".join(self.layers["shade"] + self.layers["grid"]))]
        for k in ("axis", "geo", "mark", "dot"):
            body.extend(self.layers[k])
        return ('<svg class="fig" xmlns="http://www.w3.org/2000/svg" width="%smm" height="%smm" viewBox="0 0 %s %s">%s%s</svg>'
                % (fmt(self.W), fmt(self.H), fmt(self.W), fmt(self.H), defs, "".join(body)))


def _numtxt(v):
    s = str(v)
    return s


# ── 수직선 ────────────────────────────────────────────────────
def numberline(spec, fid):
    errors, notes = [], []
    a, b = [f2(num(v, "range")) for v in spec["range"]]
    if not a < b:
        raise FigError("수직선 range 가 거꾸로다")
    w = spec.get("w", 60)
    if w + 2 * PAD > MAX_W:
        errors.append("수직선 폭이 한 단을 넘는다")
    s = w / (b - a)
    spans = spec.get("spans", [])
    levels = max([sp_.get("level", 1) for sp_ in spans] + [0])
    H = 2 * PAD + 3.4 * levels + 4.5
    base = PAD + 3.4 * levels + 1.0
    X_ = lambda v: PAD + (v - a) * s
    o = ['<path d="M%s %s L%s %s" fill="none" stroke="#000" stroke-width="%s"/>' % (fmt(PAD - 1.5), fmt(base), fmt(PAD + w + 1.5),
                                                                                    fmt(base), W_LINE)]
    q = (PAD + w + 2.8, base)
    o.append('<path d="M%s %s L%s %s L%s %s Z" fill="#000"/>' % (fmt(q[0]), fmt(q[1]), fmt(q[0] - 1.5), fmt(q[1] - 0.65),
                                                               fmt(q[0] - 1.5), fmt(q[1] + 0.65)))
    for t in spec.get("ticks", []):
        v, lab = (t["v"], t.get("t")) if isinstance(t, dict) else (t, None)
        x = f2(num(v, "ticks"))
        if not a <= x <= b:
            errors.append("수직선 눈금 %s 가 range 밖" % v)
            continue
        o.append('<path d="M%s %s L%s %s" stroke="#000" stroke-width="%s"/>' % (fmt(X_(x)), fmt(base - 0.8), fmt(X_(x)),
                                                                                fmt(base + 0.8), W_AXIS))
        o.append(svg_text(lab if lab is not None else str(v), X_(x), base + 3.0))
    for sp_ in spans:
        lv = sp_.get("level", 1)
        y = base - 3.4 * lv
        lo, hi = sp_["from"], sp_["to"]
        xl = PAD - 1.5 if lo == "-inf" else X_(f2(num(lo, "spans")))
        xr = PAD + w + 1.5 if hi == "inf" else X_(f2(num(hi, "spans")))
        for v in (lo, hi):
            if v not in ("-inf", "inf") and not a <= f2(num(v, "spans")) <= b:
                errors.append("수직선 구간 끝 %s 가 range 밖" % v)
        pts = []
        if lo != "-inf":
            pts.append((xl, base))
        pts += [(xl, y), (xr, y)]
        if hi != "inf":
            pts.append((xr, base))
        o.append('<path d="M%s" fill="none" stroke="#000" stroke-width="%s"/>' % (
            " L".join("%s %s" % (fmt(p[0]), fmt(p[1])) for p in pts), W_CURVE))
    for m in spec.get("marks", []):
        x = f2(num(m["at"], "marks"))
        if not a <= x <= b:
            errors.append("수직선 점 %s 가 range 밖" % m["at"])
        if m.get("closed", True):
            o.append('<circle cx="%s" cy="%s" r="0.75" fill="#000"/>' % (fmt(X_(x)), fmt(base)))
        else:
            o.append('<circle cx="%s" cy="%s" r="0.75" fill="#fff" stroke="#000" stroke-width="0.24"/>' % (fmt(X_(x)), fmt(base)))
    for sp_ in spans:       # 구간 끝마다 점이 있는지 (닫힌 · 열린 표시 빠뜨림)
        for v in (sp_["from"], sp_["to"]):
            if v in ("-inf", "inf"):
                continue
            if not any(abs(f2(num(m["at"], "marks")) - f2(num(v, "spans"))) < 1e-9 for m in spec.get("marks", [])):
                errors.append("수직선 구간 끝 %s 에 ● · ○ 표시(marks)가 없다" % v)
    Wt = w + 2 * PAD + 3
    svg = ('<svg class="fig" xmlns="http://www.w3.org/2000/svg" width="%smm" height="%smm" viewBox="0 0 %s %s">%s</svg>'
           % (fmt(Wt), fmt(H), fmt(Wt), fmt(H), "".join(o)))
    return svg, errors, notes


def draw(spec, fid):
    """→ (svg 문자열, 결함 목록, 참고 목록)"""
    try:
        if "svg" in spec:
            s = spec["svg"].strip()
            if not (s.startswith("<svg") and s.endswith("</svg>")):
                return "", ["직접 넣은 svg 가 <svg …>…</svg> 꼴이 아니다"], []
            return s, [], ["직접 넣은 svg — 좌표 검사를 하지 않았다 (눈으로 확인)"]
        if spec.get("kind") == "numberline":
            return numberline(spec, fid)
        f = Figure(spec, fid)
        svg = f.render()
        return svg, f.errors, f.notes
    except FigError as e:
        return "", [str(e)], []
    except KeyError as e:
        return "", ["그림에 %s 가 없다" % e], []
