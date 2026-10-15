# 학생별 약점 확인 시험 — 새 문항 모음(bank_*.py)에서 학생마다 약점 유형만 뽑아 공용 모의고사 빌더로 시험지·답지를 만든다
#   py 공용/build/약점보완/확인시험.py <확인시험폴더>                 설정.json 의 tests 전부 → 배부/<prefix><이름>.pdf · _답지.pdf
#   py 공용/build/약점보완/확인시험.py <확인시험폴더> 학생S          한 명
#   py 공용/build/약점보완/확인시험.py <확인시험폴더> --bank bank_A   문항 모음 하나만 모아 시험 삼아 빌드 (<폴더>/_bank_A/, 배부 안 함)
#   py 공용/build/약점보완/확인시험.py <확인시험폴더> --dup           반의 기존 회차(설정.json rounds)와 겹침 점검 (빈칸 위치 · 밑줄 표적 · 선택지)
#   --out 폴더  를 붙이면 배부 대신 그 폴더에 만든다
# 문항 모음 형식: bank_X.py 의 ITEMS = [{"id", "type", "passage": {kind, src, body, restore?, guard?, free?}, "q": {stem, show, fixed, opts, ans, sol, box?}}]
#   passage 는 그 문항 하나만 쓰는 단독 지문(box_ref). 형식은 공용/build/모의고사/README.md · 설정은 README.md
import json, os, sys, re, subprocess, importlib, difflib
HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.normpath(os.path.join(HERE, "..", "모의고사", "build.py"))
H = CFG = None


def init(folder):
    global H, CFG
    H = os.path.abspath(folder)
    CFG = json.load(open(os.path.join(H, "설정.json"), encoding="utf-8"))
    if H not in sys.path: sys.path.insert(0, H)


def P(p): return os.path.normpath(os.path.join(H, p))


def items(banks=None):
    out = {}
    for b in (banks or CFG["banks"]):
        if not os.path.exists(os.path.join(H, b + ".py")): continue
        for it in importlib.import_module(b).ITEMS:
            assert it["id"] not in out, ("id 중복", it["id"])
            assert it["type"] in CFG["pt"], (it["id"], "설정.json pt 에 없는 유형", it["type"])
            out[it["id"]] = it
    return out


def targets(qs):
    """정답 위치: 고정 문항은 원래 정답, 나머지는 한 번호 최대 4개 · 3연속 없이 고르게"""
    order = [1, 3, 0, 4, 2]
    t, used = [], {i: 0 for i in range(5)}
    k = 0
    for q in qs:
        if q.get("fixed") or not q.get("opts"):
            v = q["ans"]
        else:
            for _ in range(10):
                v = order[k % 5]; k += 1
                if used[v] < 4 and not (len(t) >= 2 and t[-1] == t[-2] == v): break
        t.append(v); used[v] += 1
    return t


def make(label, ids, outdir, name, title, banks=None):
    IT = items(banks)
    miss = [i for i in ids if i not in IT]
    assert not miss, ("문항 모음에 없는 id", miss)
    PS, QS = {}, []
    for n, i in enumerate(ids, 1):
        it = IT[i]; key = "S%d" % n
        PS[key] = dict(it["passage"])
        q = dict(it["q"]); q["n"] = n; q["pt"] = CFG["pt"][it["type"]]; q["box_ref"] = key; q["passage"] = None
        QS.append(q)
    src = json.load(open(P(CFG["sources_from"]), encoding="utf-8"))
    pts = [q["pt"] for q in QS]
    d = {"school": CFG["school"], "name": name, "title": title, "subtitle": CFG["subtitle"],
         "guide": "&#9679; 문항 수 <b>%d문항</b> (선택형) &nbsp;&#9679; 모든 문항은 <b>5지선다</b>이다.<br>&#9679; 약점 보완 자료로 연습한 유형만 모았다. 모두 처음 보는 문항이다." % len(QS),
         "footer": CFG["footer"] + " · " + label,
         "target": targets(QS), "sol_numbers": "forbid",
         "passages": PS, "questions": QS,
         "sources": src["sources"], "range_block": src.get("range_block", []),
         "profile_override": {"questions": len(QS), "total": round(sum(pts), 6), "points": {},
                              "why": "학생별 약점 확인 시험 — 약점 유형만 뽑아 문항 수·배점표를 학생마다 달리한다"}}
    os.makedirs(outdir, exist_ok=True)
    dp = os.path.join(H, "_json", "%s.json" % label); os.makedirs(os.path.dirname(dp), exist_ok=True)
    json.dump(d, open(dp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    r = subprocess.run(["py", BUILD, dp, "--out", outdir], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-3000:], r.stderr[-3000:])
    return r.returncode, dp


def dup():
    """기존 회차와 겹침 — 같은 원문 문장에 낸 빈칸 · 같은 곳에 친 밑줄 표적 · 거의 같은 선택지"""
    def plain(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()
    def words(s): return re.findall(r"[a-z']+", s.lower())
    def grab(src, d):
        out = []
        for k, ps in d["passages"].items():
            b = ps["body"]
            for m in re.finditer(r"\{\{빈칸\}\}", b):
                pre = words(plain(b[:m.start()]))[-6:]; out.append((src, "빈칸", " ".join(pre), "…" + " ".join(pre) + " ____"))
            for m in re.finditer(r"<u>(.*?)</u>", b):
                if len(plain(m.group(1)).split()) > 6: continue
                pre = words(plain(re.sub(r"<b>[^<]*</b>", "", b[:m.start()])))[-3:]
                if len(pre) < 3: continue
                out.append((src, "밑줄", " ".join(pre), " ".join(pre) + " [" + plain(m.group(1)) + "]"))
        for q in d["questions"]:
            for o in (q.get("opts") or []):
                t = plain(o)
                if len(t) > 25: out.append((src, "선택지", t.lower(), t))
        return out
    old = []
    for n, p in CFG["rounds"].items(): old += grab("%s회" % n, json.load(open(P(p), encoding="utf-8")))
    new = []
    for i, it in items().items():
        new += grab(i, {"passages": {"x": it["passage"]}, "questions": [it["q"]]})
    hits = 0
    for a in new:
        for b in old:
            if a[1] != b[1]: continue
            if a[1] == "선택지":
                if difflib.SequenceMatcher(None, a[2], b[2]).ratio() < 0.85: continue
            elif a[2] != b[2]: continue
            hits += 1; print("%s %s | %s\n   %s %s" % (a[1], a[0], a[3][:100], b[0], b[3][:100]))
    print("겹침 %d건" % hits)
    return hits


def main(argv):
    a = list(argv)
    out = None
    if "--out" in a:
        i = a.index("--out"); out = os.path.abspath(a[i + 1]); del a[i:i + 2]
    init(a[0]); a = a[1:]
    if a[:1] == ["--dup"]:
        return 1 if dup() else 0
    if a[:1] == ["--bank"]:
        b = a[1]; ids = [it["id"] for it in importlib.import_module(b).ITEMS]
        rc, _ = make("_" + b, ids, out or os.path.join(H, "_" + b), CFG["file_prefix"] + "문항모음_" + b,
                     CFG["title"] % ("문항 모음 " + b), [b])
        return rc
    for nm in (a or list(CFG["tests"])):
        rc, _ = make(nm, CFG["tests"][nm], out or P(CFG["out"]), CFG["file_prefix"] + nm, CFG["title"] % nm)
        if rc: return rc
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
