# -*- coding: utf-8 -*-
"""정답 검산 — 문항의 verify(sympy 식이나 코드)를 돌려 표시한 정답과 맞는지 본다.

verify 쓰는 법
    한 줄 식      "sqrt(5**2 - 3**2)"
    여러 문장     "x = symbols('x'); r = solve(x**2-3*x-4, x); result = r[1]-r[0]"   ← result(또는 답)에 넣는다
sympy 전부(from sympy import *)를 쓸 수 있다.

표시한 정답의 값
    선택형  opts[ans] 를 수식으로 읽는다 (분수 · 근호 · π · 거듭제곱 · Σ). 못 읽으면 opt_values 로 적는다
    단답형  answer 를 읽는다 (못 읽으면 value)
    서술형  value (최종 답의 값, sympy 식) — 없으면 비교하지 않고 알린다
"""
import re

import sympy as sp
from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application,
                                        parse_expr, standard_transformations)

TRANS = standard_transformations + (implicit_multiplication_application, convert_xor)
NS = {}
exec("from sympy import *", NS)


def _group(s, i):
    """s[i] == '{' 일 때 짝 '}' 까지 (안쪽, 끝 다음 위치)."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    raise ValueError("중괄호 짝이 맞지 않는다")


def _arg(s, i):
    """명령 뒤 인자 하나 — {…} 또는 글자 하나."""
    while i < len(s) and s[i] == " ":
        i += 1
    if s[i] == "{":
        return _group(s, i)
    return s[i], i + 1


def tex_to_py(t):
    """자주 쓰는 LaTeX 를 sympy 가 읽는 식으로. 못 읽는 명령이 남으면 ValueError."""
    t = t.strip().strip("$").strip()
    t = re.sub(r"\\(left|right|displaystyle|,|;|!|quad|qquad)", " ", t)
    t = t.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/").replace("\\pi", " pi ")
    t = t.replace("\\infty", " oo ").replace("\\le", "<=").replace("\\ge", ">=")
    out, i = [], 0
    while i < len(t):
        if t.startswith("\\sum", i):
            m = re.match(r"\\sum\s*_\s*\{\s*([a-z])\s*=\s*([^}]*)\}\s*\^\s*(\{[^}]*\}|\w)", t[i:])
            if not m:
                raise ValueError("Σ 는 \\sum_{k=1}^{n} 꼴로 쓴다")
            body = tex_to_py(t[i + m.end():])
            hi = m.group(3).strip("{}")
            out.append("Sum((%s),(%s,%s,%s)).doit()" % (body, m.group(1), tex_to_py(m.group(2)), tex_to_py(hi)))
            break                           # Σ 의 몸은 끝까지
        for cmd in ("\\dfrac", "\\tfrac", "\\frac"):
            if t.startswith(cmd, i):
                a, j = _arg(t, i + len(cmd))
                b, j = _arg(t, j)
                out.append("((%s)/(%s))" % (tex_to_py(a), tex_to_py(b)))
                i = j
                break
        else:
            if t.startswith("\\sqrt", i):
                j = i + 5
                n = None
                if j < len(t) and t[j] == "[":
                    k = t.index("]", j)
                    n, j = t[j + 1:k], k + 1
                a, j = _arg(t, j)
                out.append("sqrt(%s)" % tex_to_py(a) if n is None else "root(%s,%s)" % (tex_to_py(a), tex_to_py(n)))
                i = j
            elif t[i] == "\\":
                m = re.match(r"\\[A-Za-z]+", t[i:])
                raise ValueError("읽지 못하는 명령 %s" % (m.group(0) if m else t[i:i + 2]))
            elif t[i] == "{":
                a, j = _group(t, i)
                out.append("(%s)" % tex_to_py(a))
                i = j
            else:
                out.append(t[i])
                i += 1
    return "".join(out)


def tex_value(t):
    """$…$ 글 → sympy 값. 선택지·답에 한글이 있으면 읽지 않는다."""
    s = re.sub(r"<[^>]+>", "", t or "")
    if re.search("[가-힣]", s):
        raise ValueError("한글이 섞여 있다")
    ns = dict(NS)
    ns["i"] = sp.I                  # 선택지 · 답의 i 는 허수단위
    return parse_expr(tex_to_py(s), local_dict=ns, transformations=TRANS)


def py_value(s):
    return sp.sympify(s, locals=dict(NS)) if isinstance(s, str) else sp.sympify(s)


def run(code):
    """verify 를 돌려 값을 돌려준다."""
    ns = dict(NS)
    code = code.strip()
    one_line = "\n" not in code and ";" not in code and not re.search(r"(^|[^=!<>])=([^=]|$)", code)
    if one_line:
        return eval(code, ns)
    exec(code, ns)
    for k in ("result", "답"):
        if k in ns:
            return ns[k]
    raise ValueError("verify 코드가 result 에 답을 넣지 않았다")


def same(a, b):
    """수학적으로 같은 값인가 — 식 · 집합 · 순서쌍."""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    try:
        a, b = sp.sympify(a), sp.sympify(b)
    except Exception:
        return a == b
    if isinstance(a, sp.Set) or isinstance(b, sp.Set):
        return a == b or sp.simplify(a.symmetric_difference(b)) == sp.S.EmptySet
    if isinstance(a, sp.Tuple) and isinstance(b, sp.Tuple):
        return same(list(a), list(b))
    try:
        if sp.simplify(a - b) == 0:
            return True
        v = complex(sp.N(a - b, 30))
        return abs(v) < 1e-12
    except Exception:
        return a == b


def as_number(v):
    """채점키 인정 답 만들기용 — 유리수면 Rational, 아니면 None."""
    try:
        v = sp.nsimplify(sp.sympify(v))
    except Exception:
        return None
    return v if v.is_Rational else None


def accept_forms(v):
    """수의 같은 표기들 (온라인 채점 인정 답). 1/2 → 1/2 · 0.5 · .5 · 2분의 1 같은 꼴.
    Code.gs 는 글자 그대로 비교하므로 여기서 펼쳐 둔다."""
    r = as_number(v)
    if r is None:
        return []
    p, q = int(r.p), int(r.q)
    out = set()
    if q == 1:
        out |= {str(p), "%d.0" % p}
        if p >= 0:
            out.add("+%d" % p)
        return sorted(out)
    out |= {"%d/%d" % (p, q), "%d / %d" % (p, q)}
    if p < 0:
        out |= {"-(%d/%d)" % (-p, q), "(%d)/%d" % (p, q)}
    # 유한소수면 소수도 인정
    qq = q
    for f in (2, 5):
        while qq % f == 0:
            qq //= f
    if qq == 1:
        dec = str(sp.Float(sp.Rational(p, q), 20)).rstrip("0").rstrip(".")
        out.add(dec)
        if dec.startswith("0."):
            out.add(dec[1:])
        if dec.startswith("-0."):
            out.add("-" + dec[2:])
    if p > 0:
        out.add("%d분의 %d" % (q, p))
        out.add("%d분의%d" % (q, p))
    return sorted(out)
