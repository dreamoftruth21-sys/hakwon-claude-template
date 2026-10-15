# 학생별 약점 보완 자료 공용 빌더 — py 공용/build/약점보완/build.py <작업폴더> 이름 [이름…] [--out 폴더]
# 작업폴더: 설정.json · 응시기록.json · <방법 모듈>.py(METHODS · VOCAB) · 학생_<이름>.py(GROUPS · ITEMS)  — 형식은 README.md
# 산출: 문제편(표지 · 약점마다 [틀린 문제 · 원인 · 보완 방법 · 예제 풀이 · 다시 풀기 · 연습 문제]) + 답지(정답과 해설, 학생 자가 채점용)
# 문항은 반의 실전 모의고사 data.json(공용 모의고사 빌더 형식) 원문 그대로 — 지문·선택지 순서는 학생이 받은 시험지와 같다. 새 문항은 만들지 않는다.
# 데이터만 쓸 때(에이전트가 학생 답 확인): sys.path 에 이 폴더를 넣고 import build as B; B.init(작업폴더); B.first_ans(...)
import json, re, sys, os, html, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
C5 = "①②③④⑤"
TITLE = "약점 보완 자료"
FORBID = ["하세요", "판서", "채점하면", "학생이", "배점", "출제자", "출제 의도", "기록 없"]      # 문제편 금지어
FORBID_OWN = ["모양", "나는", "틀려 보", "맞아 보"]                                          # 우리가 쓴 설명 글 금지 표현

H = CFG = D = REC = METHODS = VOCAB = None
ROUNDS, PAPER = [], []


def init(folder):
    """작업폴더의 설정·응시기록·회차 데이터를 읽는다."""
    global H, CFG, D, REC, METHODS, VOCAB, ROUNDS, PAPER
    H = os.path.abspath(folder)
    CFG = json.load(open(os.path.join(H, "설정.json"), encoding="utf-8"))
    D = {int(n): json.load(open(os.path.normpath(os.path.join(H, p)), encoding="utf-8")) for n, p in CFG["rounds"].items()}
    ROUNDS = sorted(D); PAPER = [int(n) for n in CFG.get("paper_rounds", [])]
    REC = json.load(open(os.path.join(H, "응시기록.json"), encoding="utf-8"))
    if H not in sys.path: sys.path.insert(0, H)
    m = importlib.import_module(CFG.get("methods", "방법"))
    METHODS, VOCAB = dict(m.METHODS), dict(getattr(m, "VOCAB", {}))


def student(name):
    m = importlib.import_module("학생_" + name)
    METHODS.update(getattr(m, "METHODS_EXTRA", {})); VOCAB.update(getattr(m, "VOCAB_EXTRA", {}))
    return {"groups": m.GROUPS}, m.ITEMS


def kind(q):
    s = re.sub("<[^>]+>", "", q["stem"])
    # 반 설정.json 의 "kinds_extra": [[이름, 정규식], …] 를 먼저 본다 — 기본 목록에서 "기타"로 떨어지는 유형(순서·삽입 등)을
    # 따로 묶을 때. 없으면 예전과 같다 (세종예고2 자료는 이 칸 없이 만들었다 — 2026-09-30 양지고2에서 추가)
    for k, pat in (CFG or {}).get("kinds_extra", []):
        if re.search(pat, s): return k
    k = base_kind(s)
    # 반 설정.json 의 "sub_kinds": {기본유형: [[이름, 정규식], …]} — 발문이 모두 같은 유형(어법)을 해설(sol)로 다시 나눈다.
    # 첫 번째로 맞는 이름, 없으면 기본 유형. 없으면 예전과 같다 (2026-09-30 세종예고1 — 어법만 푼 회차가 섞여서 추가)
    for sk, pat in (CFG or {}).get("sub_kinds", {}).get(k, []):
        if re.search(pat, plain(q.get("sol", ""))): return sk
    return k


def lab(n): return (CFG or {}).get("labels", {}).get(str(n), "%d회" % n)     # 회차 이름 — 설정.json "labels" (없으면 "3회")


def rn(x): return "%s %d번" % (lab(x[0]), x[1])


def base_kind(s):
    for k, pat in [("요약", "요약"), ("어법 개수", "개수"), ("용법 구분", "용법|쓰임이 나머지|의미상 쓰임|쓰임이 <?u?>?다른"),
                   ("생략 복원", "생략"), ("어법", "어법"), ("어휘", "낱말의 쓰임"), ("함축", "의미하는 바"),
                   ("빈칸", "빈칸"), ("답 못 찾는 질문", "답을 찾을 수"), ("예시", "예시"), ("지시대상", "가리키는"),
                   ("잘못 이해", "잘못"), ("내용 일치", "일치"), ("제목", "제목"), ("요지", "요지"), ("주제", "주제"), ("목적", "목적|주장")]:
        if re.search(pat, s): return k
    return "기타"


def written(q): return q.get("kind") in ("short", "essay")        # 서답형은 다루지 않는다 (선택형만)


def is_textbook(n, q):
    if n in CFG.get("textbook_rounds", []): return True             # 전 문항이 교과서인 회차 (옛 데이터라 src 표시가 없을 때)
    key = q.get("passage") or q.get("box_ref")
    return D[n]["passages"].get(key, {}).get("src") in CFG.get("textbook_src", ["L1"]) if key else False


def choice_index(n, q):
    return [x["n"] for x in D[n]["questions"] if not written(x)].index(q["n"])


def disp_opts(n, q):
    """학생 시험지의 선택지 순서와 정답 위치(0부터)"""
    if not q.get("opts"): return None, q["ans"]
    if q.get("fixed"): return q["opts"], q["ans"]
    t = D[n]["target"][choice_index(n, q)]
    r = (q["ans"] - t) % 5
    return q["opts"][r:] + q["opts"][:r], t


def Q(n, k): return [q for q in D[n]["questions"] if q["n"] == k and not written(q)][0]


def plain(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&ndash;|&nbsp;", " ", s)).strip()


def body_html(b): return b.replace("{{빈칸}}", '<span class="blank"></span>')


def item_html(n, k, tag, trace=None):
    q = Q(n, k); P = D[n]["passages"]
    key = q.get("passage") or q.get("box_ref")
    out = ['<div class="item"><div class="ih"><span class="tag">%s</span> <b>%s</b> <span class="kd">%s</span></div>' % (tag, rn((n, k)), kind(q))]
    out.append('<div class="stem">%s</div>' % q["stem"])
    if key: out.append('<div class="psg">%s</div>' % body_html(P[key]["body"]))
    if q.get("box"): out.append('<div class="box">%s</div>' % q["box"])
    opts, _ = disp_opts(n, q)
    if opts is None:
        out.append('<div class="opts row">' + "".join("<span>%s</span>" % c for c in C5) + "</div>")
    elif q.get("show") == "row":
        out.append('<div class="opts row">' + "".join("<span>%s %s</span>" % (C5[i], o) for i, o in enumerate(opts)) + "</div>")
    else:
        out.append('<ol class="opts">' + "".join("<li><span class='c'>%s</span> %s</li>" % (C5[i], o) for i, o in enumerate(opts)) + "</ol>")
    if trace: out.append('<div class="trace"><b>근거</b> <span>%s</span><div class="ln"></div><div class="ln"></div><div class="ln"></div></div>' % trace)
    out.append("</div>")
    return "\n".join(out)


def online(name, n): return REC["online"].get(name, {}).get(str(n))


def first_ans(name, n, k):
    """온라인 첫 제출 답 (1~5, 0 = 빈칸). 종이 시험·미제출이면 None"""
    o = online(name, n)
    if not o: return None
    a = o["ans"][choice_index(n, Q(n, k))]
    return 0 if a == "-" else int(a)


def opt_label(n, k, i, cut=48):
    """선택지 i(0부터)를 짧게: ③ harmless – critical"""
    q = Q(n, k); opts, _ = disp_opts(n, q)
    if not opts: return C5[i]
    t = plain(opts[i]).replace("(A) ", "").replace(" (B) ", " – ")
    if len(t) <= 3 or kind(q) == "어법 개수": return t
    return "%s %s" % (C5[i], t if len(t) <= cut else t[:cut] + "…")


def chosen(name, n, k, cut=48):
    a = first_ans(name, n, k)
    if a is None: return None
    if a == 0: return "빈칸으로 냄"
    return opt_label(n, k, a - 1, cut)


def ans_text(n, k):
    q = Q(n, k); opts, cor = disp_opts(n, q)
    if opts and (q.get("show") == "row" or kind(q) == "요약"): return opt_label(n, k, cor, 80)
    return C5[cor]


def excluded(n): return REC.get("exclude", {}).get(str(n), [])


def wrong_set(name):
    ws = set()
    for n in ROUNDS:
        if n in PAPER: continue
        if not online(name, n): continue
        for q in D[n]["questions"]:
            if written(q) or q["n"] in excluded(n): continue
            a = first_ans(name, n, q["n"]); _, cor = disp_opts(n, q)
            if a == 0 or a - 1 != cor: ws.add((n, q["n"]))
    for n, ks in REC.get("paper", {}).get(name, {}).items():
        for k in ks:
            if k not in excluded(n): ws.add((int(n), k))
    return ws


def sat(name, n):
    """그 학생의 기록이 있는 회차 — 온라인 제출, 또는 응시기록 paper 에 그 학생·회차가 있는 종이 회차.
    종이 회차라도 기록이 없으면(시험지 분실 등) 푼 개수·연습 문제에서 뺀다 (2026-09-30 양지고2 학생N 1회)"""
    if n in PAPER: return str(n) in REC.get("paper", {}).get(name, {})
    return bool(online(name, n))


def taken(name):
    """응시한 선택형 문항 (범위 밖 제외 · 기록 없는 회차 제외)"""
    out = []
    for n in ROUNDS:
        if not sat(name, n): continue
        for q in D[n]["questions"]:
            if not written(q) and q["n"] not in excluded(n): out.append((n, q["n"]))
    return out


def vocab_html(items):
    ws = set()
    for n, k in items:
        for o in Q(n, k)["opts"]:
            t = plain(o).replace(" (B)", " – (B)")
            for w in re.findall(r"\(\w\)\s*([^–(]+?)\s*(?=–|$)", t): ws.add(w.strip())
    miss = sorted(w for w in ws if w not in VOCAB)
    assert not miss, ("VOCAB 에 뜻이 없는 단어", miss)
    ws = sorted(ws, key=str.lower); h = (len(ws) + 2) // 3
    cols = [ws[i * h:(i + 1) * h] for i in range(3)]
    rows = "".join("<tr>" + "".join("<td class='w'>%s</td><td class='l'>%s</td>" % ((c[r], VOCAB[c[r]]) if r < len(c) else ("", "")) for c in cols) + "</tr>" for r in range(h))
    return '<div class="how"><b>요약문 선택지 단어</b> (예제 · 다시 풀기 · 연습 문제에 나오는 단어 전부)<table class="voc">%s</table></div>' % rows


def score_cell(name, n):
    if n in PAPER:
        v = REC.get("paper_score", {}).get(str(n), {}).get(name)
        return "<td>%s%s</td>" % (v, CFG.get("paper_score_unit", {}).get(str(n), "점")) if v is not None else "<td>—</td>"
    o = online(name, n)
    return "<td>%s</td>" % ("%s점" % o["score"] if o else "—")


def build(name, pages=None, out_dir=None):
    S, IT = student(name)
    wrong_all = wrong_set(name); tk = taken(name)
    used = set()
    out_dir = out_dir or os.path.normpath(os.path.join(H, CFG["out"]))
    # 표지
    sc = [score_cell(name, n) for n in ROUNDS]
    rows, gk = [], set()
    for gi, g in enumerate(S["groups"], 1):
        gk |= set(g["kinds"])
        t = [x for x in tk if kind(Q(*x)) in g["kinds"]]
        w = sorted(x for x in t if x in wrong_all)
        g["_t"], g["_w"] = len(t), w
        rows.append("<tr><td class='l'>%s</td><td><b>%d</b> / %d</td><td class='l'>%s</td></tr>" % (
            g["title"], len(w), len(t), " · ".join(rn(x) for x in w)))
    rest = [x for x in tk if kind(Q(*x)) not in gk]
    rw = [x for x in rest if x in wrong_all]
    assert not rw, ("약점에 안 들어간 유형의 오답", rw)
    rk = sorted(set(kind(Q(*x)) for x in rest))
    if rest:
        rows.append("<tr><td class='l'>그 밖의 유형 (%s)</td><td><b>0</b> / %d</td><td class='l'>—</td></tr>" % (" · ".join(rk), len(rest)))
    pg = lambda key: str(pages.get(key, "")) if pages else "00"
    toc = "".join("<tr><td class='l'>약점 %d · %s</td><td>%s</td></tr>" % (gi, g["title"], pg(gi)) for gi, g in enumerate(S["groups"], 1))
    cover = ['<section class="cover"><h1>%s · %s</h1><div class="sub">%s</div>' % (name, TITLE, CFG["sub"]),
             '<h2>회차별 결과</h2><table class="score"><tr><th></th>' + "".join("<th>%s</th>" % lab(n) for n in ROUNDS) + "</tr><tr><th>결과</th>" + "".join(sc) + "</tr></table>",
             '<div class="note">%s</div>' % CFG.get("score_note", ""),
             '<h2>유형별 오답 개수</h2><table class="cnt"><tr><th>유형</th><th style="white-space:nowrap">틀린 개수 / 푼 개수</th><th>틀린 문제</th></tr>%s</table>' % "".join(rows),
             '<h2>약점</h2><ol class="weak">' + "".join("<li><b>%s</b> — %s</li>" % (g["title"], g["head"]) for g in S["groups"]) + "</ol>",
             '<div class="two"><div><h2>목차</h2><table class="toc"><tr><th>차례</th><th>쪽</th></tr>%s</table></div>' % toc,
             '<div><h2>푸는 순서</h2><ol class="steps">'
             '<li>☐ 틀린 문제 · 원인 · 보완 방법</li>'
             '<li>☐ 예제 풀이</li>'
             '<li>☐ 다시 풀기 → 연습 문제</li></ol></div></div></section>']
    body, keys = [], []
    for gi, g in enumerate(S["groups"], 1):
        miss = [x for x in g["wrong"] if x not in wrong_all]
        assert not miss, (g["title"], "틀리지 않은 문항", miss)
        assert sorted(g["wrong"]) == g["_w"], (g["title"], "유형과 틀린 문항이 어긋남", sorted(g["wrong"]), g["_w"])
        ex = g.get("example")
        assert ex is None or ex in g["wrong"]
        s = ['<section><h1 class="part">약점 %d · %s</h1><div class="sub">틀린 문제 %d개 / 푼 문제 %d개 — %s</div>' % (
            gi, g["title"], len(g["wrong"]), g["_t"], " · ".join(rn(x) for x in sorted(g["wrong"])))]
        ev = []
        for x in g["wrong"]:
            c = chosen(name, *x)
            if c is None: continue          # 종이 시험은 고른 답이 없다 — 표에서 뺀다 (안내 문구도 쓰지 않는다)
            ev.append("<tr><td>%s</td><td class='l'>%s</td><td class='l'>%s</td></tr>" % (rn(x), html.escape(c), IT[x]["miss"]))
        s.append('<h2>틀린 문제</h2>%s' % g["how"])
        if ev: s.append('<table class="ev"><tr><th>문제</th><th>내가 고른 답</th><th>%s</th></tr>%s</table>' % (g.get("col", "틀린 이유"), "".join(ev)))
        s.append('<h2>원인</h2><ul class="habit">%s</ul>' % "".join("<li><b>%s</b> — %s</li>" % h for h in g["habits"]))
        re_ = [x for x in g["wrong"] if x != ex]
        pool = []
        for n in sorted(ROUNDS, reverse=True):
            if not sat(name, n): continue   # 아직 안 푼 회차·기록 없는 회차는 연습 문제로 쓰지 않는다 (답지에 답이 실린다)
            for q in D[n]["questions"]:
                x = (n, q["n"])
                if written(q) or q["n"] in excluded(n) or x in wrong_all or x in used: continue
                if kind(q) in g["kinds"] and (g.get("p1과") is None or is_textbook(n, q) == g["p1과"]):
                    pool.append(x)
        prac = pool[:g.get("pmax", 6)]
        voc = vocab_html(([ex] if ex else []) + re_ + prac) if g.get("vocab") else ""
        s.append('<div class="method"><h2>보완 방법</h2>%s</div>%s' % ("".join(METHODS[m] for m in g["methods"]), voc))
        if ex:
            s.append('<h2 class="pb">예제 풀이 · %s</h2>' % rn(ex))
            s.append(item_html(ex[0], ex[1], "예제"))
            s.append('<div class="walkbox"><b>풀이</b>%s</div>' % g["walk"]); used.add(ex)
        if re_:
            s.append('<h2 class="grp">다시 풀기 · 틀린 문제 %d개</h2>' % len(re_))
            for x in re_:
                s.append(item_html(x[0], x[1], "다시 풀기", g.get("trace"))); keys.append((gi, g["title"], "다시 풀기", x)); used.add(x)
        if prac:
            s.append('<h2 class="grp">연습 문제 · 같은 유형 %d개</h2>' % len(prac))
            for x in prac:
                s.append(item_html(x[0], x[1], "연습", g.get("trace"))); keys.append((gi, g["title"], "연습 문제", x)); used.add(x)
        s.append("</section>")
        body.append("".join(s))
    placed = set(x for g in S["groups"] for x in g["wrong"])
    left = sorted(wrong_all - placed)
    assert not left, ("약점에 안 들어간 오답", left)
    # 정답과 해설 (학생 자가 채점용 — 실전 모의고사 답지 해설을 그대로 싣는다)
    def keyrow(x, retry):
        n, k = x; q = Q(n, k)
        r = '<div class="key"><div class="kh"><b>%s</b> <span class="kd">%s</span> · 정답 <b class="ans">%s</b></div>' % (rn(x), kind(q), html.escape(ans_text(n, k)))
        c = chosen(name, n, k, 80) if retry else None
        if c:
            r += '<div class="mine"><b>처음 고른 답</b> %s</div>' % html.escape(c)
            if IT[x]["why"]: r += '<div class="mine"><b>틀린 이유</b> %s</div>' % IT[x]["why"]
        return r + '<div class="sol"><b>해설</b> %s</div></div>' % q["sol"]
    ans = ['<section class="cover"><h1>%s · %s · 정답과 해설</h1><div class="sub">%s · 다시 풀기 · 연습 문제 채점용</div>' % (name, TITLE, CFG.get("answer_sub", CFG["sub"]))]
    cur = None
    for gi, t, part, x in keys:
        if cur != (gi, part):
            if cur is None or cur[0] != gi: ans.append('<h2 class="grp">약점 %d · %s</h2>' % (gi, t))
            ans.append('<h3>%s</h3>' % part); cur = (gi, part)
        ans.append(keyrow(x, part == "다시 풀기"))
    ans.append("</section>")
    cp = os.path.join(H, "pkg.css")
    css = open(cp if os.path.exists(cp) else os.path.join(HERE, "pkg.css"), encoding="utf-8").read()
    doc = '<html><head><meta charset="utf-8"><style>%s</style></head><body>%s%s</body></html>' % (css, "".join(cover), "".join(body))
    adoc = '<html><head><meta charset="utf-8"><style>%s</style></head><body>%s</body></html>' % (css, "".join(ans))
    # 점검 — 문제편 금지어 (답지는 원 해설이라 검사하지 않는다) · 우리가 쓴 설명 글 · 필수 칸
    txt = re.sub("<[^>]+>", " ", "".join(cover) + "".join(body))
    for w in FORBID:
        assert w not in txt, ("금지어", w)
    own = re.sub("<[^>]+>", " ", "".join(cover) + str(S) + str(IT) + str(METHODS))
    for gi, g in enumerate(S["groups"], 1):
        for f in ["title", "kinds", "head", "how", "trace", "habits", "methods", "wrong"] + (["walk"] if g.get("example") else []): assert f in g, (g["title"], "빠진 칸", f)
        for x in g["wrong"]:
            assert x in IT or x[0] in PAPER, (g["title"], "ITEMS 에 없는 온라인 오답", x)
    for w in FORBID_OWN:
        assert w not in own, ("설명 글 금지 표현", w)
    bad = [m.group(0) for m in re.finditer(r".{0,8}자리.{0,4}", own)]
    assert not bad, ("'자리'", bad)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "%s%s.pdf" % (CFG["file_prefix"], name))
    aout = os.path.join(out_dir, "%s%s_답지.pdf" % (CFG["file_prefix"], name))
    title = "%s · %s %s" % (CFG["footer"], name, TITLE)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for d, o, tt in [(doc, out, title), (adoc, aout, title + " · 정답과 해설")]:
            hp = os.path.join(H, "_%s%s.html" % (name, "_답지" if o == aout else "")); open(hp, "w", encoding="utf-8").write(d)
            p = b.new_page(viewport={"width": 688, "height": 1000}); p.emulate_media(media="print"); p.goto("file:///" + hp.replace("\\", "/"))
            sw, cw = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            assert sw <= cw, ("페이지보다 넓은 내용 — PDF 가 축소된다", o, sw, cw)
            p.pdf(path=o, format="A4", margin={"top": "14mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
                  display_header_footer=True, header_template="<span></span>",
                  footer_template='<div style="width:100%%;font-size:8px;color:#888;text-align:center;font-family:Malgun Gothic">%s · <span class="pageNumber"></span> / <span class="totalPages"></span></div>' % tt)
        b.close()
    if pages is None:       # 두 번째 빌드에서 목차 쪽번호를 채운다 — 장 첫 줄(h1)로 찾는다
        import pymupdf
        found = {}
        for i, page in enumerate(pymupdf.open(out)):
            if i == 0: continue
            first = next((l.strip() for l in page.get_text().split("\n") if l.strip()), "")
            for gi, g in enumerate(S["groups"], 1):
                if first == "약점 %d · %s" % (gi, g["title"]) and gi not in found: found[gi] = i + 1
        assert len(found) == len(S["groups"]), ("목차 쪽을 못 찾음", found)
        assert found[1] == 2, ("표지가 한 쪽을 넘음 — head 를 줄인다", found)
        return build(name, found, out_dir)
    return out, len([k for k in keys if k[2] == "다시 풀기"]), len([k for k in keys if k[2] == "연습 문제"]), pages


if __name__ == "__main__":
    a = sys.argv[1:]
    out_dir = None
    if "--out" in a:
        i = a.index("--out"); out_dir = os.path.abspath(a[i + 1]); del a[i:i + 2]
    init(a[0])
    for nm in a[1:]:
        print(build(nm, out_dir=out_dir))
