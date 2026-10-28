# -*- coding: utf-8 -*-
"""수식 — 글 속 $…$(글줄 안) · $$…$$(가운데 한 줄)를 KaTeX HTML 로 바꾼다.

빌드할 때 node + 전역 katex 로 한 번에 바꾼다(인터넷 불필요). 글꼴은 HTML 에 넣는다.
    Tex(macros).collect(s)  → 바꿀 수식을 모은다 (여러 번)
    .run()                  → node 를 한 번 돌린다. 오류는 .errors [(어디, 수식, 내용)]
    .apply(s)               → 모아 둔 결과로 바꾼 글
글자 그대로의 $ 는 \\$ 로 쓴다.
"""
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
JS = HERE / "katex_render.js"
# $$…$$ 를 먼저, 그다음 $…$ — 앞에 \ 가 붙은 $ 는 글자
PAT = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$|(?<!\\)\$(.+?)(?<!\\)\$", re.S)


def katex_dir():
    """전역 katex 패키지 폴더 — NODE_PATH → npm root -g → %APPDATA%\\npm\\node_modules 순서로 찾는다."""
    cands = [p for p in os.environ.get("NODE_PATH", "").split(os.pathsep) if p]
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm:
        try:
            cands.append(subprocess.run([npm, "root", "-g"], capture_output=True, text=True, timeout=60).stdout.strip())
        except Exception:
            pass
    if os.environ.get("APPDATA"):
        cands.append(str(pathlib.Path(os.environ["APPDATA"]) / "npm" / "node_modules"))
    for c in cands:
        k = pathlib.Path(c) / "katex"
        if (k / "dist" / "katex.min.css").exists():
            return k
    raise SystemExit("katex 를 찾지 못했다 — `npm install -g katex` 로 설치한다 (공용/설치/프로그램설치.ps1)")


_CSS = None


def css():
    """katex.min.css + 글꼴(woff2)을 data URI 로 넣은 것. HTML 파일 하나로 어디서 열어도 같은 모양."""
    global _CSS
    if _CSS is None:
        dist = katex_dir() / "dist"
        s = (dist / "katex.min.css").read_text(encoding="utf-8")

        def font(m):
            f = dist / "fonts" / (m.group(1) + ".woff2")
            return "url(data:font/woff2;base64,%s) format(\"woff2\")" % base64.b64encode(f.read_bytes()).decode("ascii")
        # url(fonts/X.woff2) format("woff2"),url(fonts/X.woff) format("woff"),url(fonts/X.ttf) format("truetype") → woff2 하나
        s = re.sub(r"url\(fonts/(KaTeX_[\w-]+)\.woff2\) format\(\"woff2\"\)(,url\(fonts/[\w-]+\.(woff|ttf)\) format\(\"\w+\"\))*",
                   font, s)
        if "url(fonts/" in s:
            raise SystemExit("katex.min.css 글꼴 경로를 바꾸지 못했다 — katex 판이 바뀌었는지 본다")
        _CSS = s
    return _CSS


class Tex:
    def __init__(self, macros=None):
        self.macros = macros or {}
        self.items = {}          # (tex, display) → 결과 html
        self.where = {}          # (tex, display) → 처음 나온 곳
        self.errors = []

    def collect(self, s, where=""):
        if not isinstance(s, str):
            return
        for m in PAT.finditer(s):
            key = ((m.group(1) if m.group(1) is not None else m.group(2)).strip(), m.group(1) is not None)
            self.items.setdefault(key, None)
            self.where.setdefault(key, where)
        # 짝이 안 맞는 $ — 바꾸고 남은 글에 $ 가 있으면 수식이 깨진 것
        rest = PAT.sub("", s).replace("\\$", "")
        if "$" in rest:
            self.errors.append((where, rest[max(0, rest.index("$") - 15):rest.index("$") + 15], "$ 짝이 맞지 않는다"))

    def run(self):
        keys = [k for k, v in self.items.items() if v is None]
        if not keys:
            return
        node = shutil.which("node") or shutil.which("node.exe")
        if not node:
            raise SystemExit("node 가 없다 — Node.js 를 설치한다")
        job = {"items": [{"t": t, "d": d} for t, d in keys], "macros": self.macros}
        r = subprocess.run([node, str(JS), str(katex_dir())], input=json.dumps(job).encode("utf-8"),
                           capture_output=True, timeout=300)
        if r.returncode != 0:
            raise SystemExit("KaTeX 실행 실패:\n" + r.stderr.decode("utf-8", "replace"))
        for k, res in zip(keys, json.loads(r.stdout.decode("utf-8"))):
            if "e" in res:
                self.errors.append((self.where.get(k, ""), k[0], res["e"]))
                self.items[k] = '<span class="texerr">[수식 오류]</span>'
            else:
                self.items[k] = res["h"]

    def apply(self, s):
        if not isinstance(s, str):
            return s

        def rep(m):
            key = ((m.group(1) if m.group(1) is not None else m.group(2)).strip(), m.group(1) is not None)
            h = self.items.get(key)
            if h is None:
                raise RuntimeError("모으지 않은 수식: %s" % key[0])
            return h
        return PAT.sub(rep, s).replace("\\$", "$")


def plain(s):
    """$ 표시만 걷어 낸 글 (길이 어림 · 점검용)."""
    return PAT.sub(lambda m: m.group(1) or m.group(2), s or "")


SUP = str.maketrans("0123456789+-n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ")
SYM = {"le": "≤", "ge": "≥", "leq": "≤", "geq": "≥", "ne": "≠", "neq": "≠", "pi": "π", "theta": "θ",
       "alpha": "α", "beta": "β", "cdot": "·", "times": "×", "div": "÷", "pm": "±", "infty": "∞",
       "angle": "∠", "triangle": "△", "circ": "°", "therefore": "∴", "in": "∈", "cup": "∪", "cap": "∩"}
BS = "\\"


def phone(s):
    """온라인 채점 화면 · 시트에 넣을 글 — 수식을 휴대폰 글자로 어림한다 (√ · 분수 a/b · 위첨자).
    그림과 복잡한 수식은 화면에 나오지 않는다. 학생은 종이 시험지를 보고 답만 입력한다."""
    s = plain(s or "")
    s = re.sub(r"\\(left|right|displaystyle|,|;|!|quad|qquad)",
               lambda m: " " if m.group(1) in (",", ";", "quad", "qquad") else "", s)
    s = re.sub(r"\\(mathrm|text|mathbf|operatorname)\{([^{}]*)\}", r"\2", s)
    s = re.sub(r"\\overline\{([^{}]*)\}", r"\1", s)
    for _ in range(4):
        s = re.sub(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}",
                   lambda m: "%s/%s" % tuple(x if re.fullmatch(r"[\w.]+", x) else "(%s)" % x for x in m.groups()), s)
        s = re.sub(r"\\sqrt\{([^{}]*)\}",
                   lambda m: "√" + (m.group(1) if re.fullmatch(r"\w+", m.group(1)) else "(%s)" % m.group(1)), s)
    s = re.sub(r"\^\{?\\circ\}?", "°", s)
    s = re.sub(r"\^(?:\{([0-9+\-n]+)\}|([0-9n]))", lambda m: (m.group(1) or m.group(2)).translate(SUP), s)
    s = re.sub(r"\\([A-Za-z]+) ?", lambda m: SYM.get(m.group(1), m.group(1)), s)
    s = s.replace("{", "").replace("}", "").replace(BS, "")
    return re.sub(r"\s+", " ", s).strip()
