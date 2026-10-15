# -*- coding: utf-8 -*-
"""학평 변형문제집 재조판 — 원본 변형문제집(유형별 배열)에서 범위 지문 문항만 지문별로 다시 모은다.

사용: py 공용/build/변형문제/재조판.py <data.json> [--out 폴더]

- 원래 문항 번호를 유지한다. 쪽마다 지문 원문을 왼쪽 위에 한 번만 두고,
  원문 그대로인 지문은 문항에서 빼고(발문+선택지만), 밑줄·변형 지문은 통째로 싣는다.
- 원문 지문과 변형 지문을 같은 쪽에 두지 않는다 (대조로 정답이 보인다).
- 답지는 원본 정답표에서 범위 밖 문항을 흰색으로 지운다.
- 점검에 하나라도 걸리면 PDF를 내보내지 않는다.
기준 구현: 세종예고1/…/9월학평_변형문제 · 양지고2/…/변형문제 (두 원본 PDF로 동일 출력 확인)
"""
import argparse
import collections
import json
import pathlib
import re
import shutil
import sys
import tempfile

import pymupdf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import checks as C  # noqa: E402
from core import sources as S  # noqa: E402

FONT = r"C:\Windows\Fonts\malgun.ttf"
QN = re.compile(r"^(\d{1,3})\.(.*)")
TOPY, BOTY = 45.0, 812.0
PW, PH = 595.0, 842.0
CLIPX = [(18.0, 293.0), (307.0, 582.0)]
DESTX = [18.0, 307.0]
TOP, BOT = 50.0, 806.0
GAP = 12.0
FOOT_RE = r"변형문제\s*·\s*(\d{1,2}(?:~\d{1,2})?)번"


def col(x):
    return 0 if x < 297 else 1


def clean(t):
    return re.sub(r"\s+", " ", t).strip()


def norm(t):
    return re.sub(r"[^a-z]", "", t.lower())


def fail(msg):
    raise SystemExit("원본 판독 실패 — " + msg)


# ── 1. 원본 문항 단위 수집 ──────────────────────────────────
def collect(src, d):
    lab = re.compile(d.get("label_regex", r"^(\d{1,2}(?:~\d{1,2})?)번$"))
    fx = d.get("footer_x_max")
    orphan_ok = set(d.get("orphan_ok", []))
    units, lastunit = [], {}
    for i in range(d["question_last_page"]):
        p = src[i]
        allb = p.get_text("blocks")
        bl = [b for b in allb if b[4].strip() and TOPY < b[1] < BOTY]
        foot = [clean(b[4]) for b in allb if b[1] > BOTY and b[4].strip() and (fx is None or b[0] < fx)]
        sec = re.sub(r"\s*\d+$", "", foot[0]) if foot else "?"
        for c in (0, 1):
            cb = sorted([b for b in bl if col(b[0]) == c], key=lambda b: b[1])
            if not cb:
                continue
            starts = [k for k, b in enumerate(cb) if lab.match(clean(b[4]))]
            if not starts or starts[0] != 0:
                endk = starts[0] if starts else len(cb)
                pu = lastunit.get((i, 0) if c == 1 else (i - 1, 1))
                if pu is None:
                    if d.get("strict_continuation") and i != 0 and clean(cb[0][4]) not in orphan_ok:
                        fail("%d쪽 %d칸 앞 문항 없이 이어짐" % (i + 1, c))
                else:
                    pu["cont"] = (i, c, cb[0][1] - 3, cb[endk - 1][3] + 4)
            for j, k in enumerate(starts):
                end = starts[j + 1] if j + 1 < len(starts) else len(cb)
                ub = cb[k:end]
                ps = lab.match(clean(cb[k][4])).group(1)
                if len(ub) < 2:
                    fail("%d쪽 %s번 발문 블록 없음" % (i + 1, ps))
                m = QN.match(clean(ub[1][4]))
                if not m:
                    fail("%d쪽 %s번 발문 판독 불가: %s" % (i + 1, ps, clean(ub[1][4])[:40]))
                base = cb[k][0]
                rest = ub[2:]
                pas = []
                for b in rest:
                    if b[0] < base + 8 and not re.match(r"^\(A\)", clean(b[4])):
                        pas.append(b)
                    else:
                        break
                u = dict(page=i, col=c, sec=sec, ps=ps, q=int(m.group(1)), stem=m.group(2),
                         y0=cb[k][1], ystem0=ub[1][1], ystem1=ub[1][3],
                         pas_y0=pas[0][1] if pas else None, pas_y1=pas[-1][3] if pas else None,
                         pas_text=" ".join(clean(b[4]) for b in pas),
                         after_y0=rest[len(pas)][1] if len(rest) > len(pas) else None,
                         y1=max(b[3] for b in ub), cont=None)
                units.append(u)
                lastunit[(i, c)] = u
    nq = d["total_questions"]
    nums = sorted(u["q"] for u in units)
    if nums != list(range(1, nq + 1)):
        s = set(nums)
        fail("원본 문항 %d개 (기대 %d) — 누락 %s / 중복 %s" % (
            len(nums), nq, [n for n in range(1, nq + 1) if n not in s][:12],
            [n for n in s if nums.count(n) > 1][:12]))
    labs = {u["ps"] for u in units}
    for p in d["passages"]:
        if p not in labs:
            fail("원본에 %s번 지문 라벨이 없음 — 실제 라벨: %s" % (p, sorted(labs)))
    return units


# ── 2. 선별 ─────────────────────────────────────────────────
def select(units, d):
    passages = d["passages"]
    by, dropped = collections.defaultdict(list), collections.Counter()
    for u in units:
        if u["ps"] not in passages:
            continue
        hit = [r for r in d.get("drop", []) if u["sec"] == r["sec"]
               and (not r.get("stem_any") or any(s in u["stem"] for s in r["stem_any"]))]
        if hit:
            r = hit[0]
            dropped[u["sec"] + ("(%s)" % "·".join(r["stem_any"]) if r.get("stem_any") else "")] += 1
            continue
        by[u["ps"]].append(u)
    # 지문·유형별 상한 — {"default": {유형: n}, "21": {…}} 문항 번호 순으로 앞에서 n개만 남긴다
    quota = d.get("quota")
    if quota:
        for ps in list(by):
            q = quota.get(ps, quota.get("default", {}))
            seen, kept = collections.Counter(), []
            for u in sorted(by[ps], key=lambda u: u["q"]):
                if seen[u["sec"]] < q.get(u["sec"], 0):
                    seen[u["sec"]] += 1
                    kept.append(u)
                else:
                    dropped["상한(%s)" % u["sec"]] += 1
            by[ps] = kept
    plain = {}
    for ps in passages:
        by[ps].sort(key=lambda u: u["q"])
        if not by[ps]:
            fail("%s번 문항 없음" % ps)
        cand = [u for u in by[ps] if u["sec"] == "대의파악" and u["pas_y0"]]
        if not cand:
            fail("%s번 원문 지문을 가진 대의파악 문항 없음" % ps)
        plain[ps] = cand[0]
    omit_secs = set(d.get("omit_sections", ["대의파악", "내용일치/불일치"]))
    omit_if = d.get("omit_sections_if_stem", {})
    for ps in passages:
        ref = norm(plain[ps]["pas_text"])
        for u in by[ps]:
            same = u["pas_y0"] is not None and norm(u["pas_text"]) == ref
            ok_sec = u["sec"] in omit_secs or (u["sec"] in omit_if and omit_if[u["sec"]] in u["stem"])
            u["omit"] = same and ok_sec
            if u["sec"] in ("어법", "어휘", "함축어구") or ("밑줄" in u["stem"]):
                u["omit"] = False
            u["modified"] = (not u["omit"]) and u["pas_y0"] is not None and norm(u["pas_text"]) != ref
    return by, plain, dropped


# ── 3. 조판 ─────────────────────────────────────────────────
def compose(src, d, by, plain):
    out = pymupdf.open()
    footer_info, plain_on_page = [], []
    corr = d.get("corrections", {})

    def new_page(ps, with_plain):
        pg = out.new_page(width=PW, height=PH)
        pg.show_pdf_page(pymupdf.Rect(0, 0, PW, TOPY), src, plain[ps]["page"], clip=pymupdf.Rect(0, 0, PW, TOPY))
        wm = pymupdf.Rect(140, BOTY + 8, 456, PH - 4)
        pg.show_pdf_page(wm, src, plain[ps]["page"], clip=wm)
        footer_info.append(ps)
        plain_on_page.append(with_plain)
        if not with_plain:
            return pg, [TOP, TOP]
        pu = plain[ps]
        x0, x1 = CLIPX[pu["col"]]
        clip = pymupdf.Rect(x0, pu["pas_y0"] - 3, x1, pu["pas_y1"] + 4)
        pg.show_pdf_page(pymupdf.Rect(DESTX[0], TOP, DESTX[0] + clip.width, TOP + clip.height),
                         src, pu["page"], clip=clip)
        for phrase, wrong, right in corr.get(ps, []):
            hits = src[pu["page"]].search_for(phrase, clip=clip)
            if len(hits) != 1:
                fail("%s번 교정 위치 '%s' %d곳" % (ps, phrase, len(hits)))
            ws = [w for w in src[pu["page"]].get_text("words", clip=hits[0]) if w[4] == wrong]
            if len(ws) != 1:
                fail("%s번 교정 단어 '%s' 판독 불가" % (ps, wrong))
            r = pymupdf.Rect(ws[0][:4])
            dr = pymupdf.Rect(r.x0 - clip.x0 + DESTX[0], r.y0 - clip.y0 + TOP,
                              r.x1 - clip.x0 + DESTX[0], r.y1 - clip.y0 + TOP)
            pg.add_redact_annot(dr, fill=(1, 1, 1))
            pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
            pg.insert_text((dr.x0, dr.y1 - 2.2), right, fontsize=10.2, fontname="tiro", color=(0.1, 0.1, 0.1))
        return pg, [TOP + clip.height + GAP + 6, TOP]

    def pieces(u):
        x0, x1 = CLIPX[u["col"]]
        if u["omit"]:
            ps_ = [(u["page"], pymupdf.Rect(x0, u["ystem0"] - 3, x1, u["ystem1"] + 3))]
            if u["after_y0"] is not None:
                ps_.append((u["page"], pymupdf.Rect(x0, u["after_y0"] - 4, x1, u["y1"] + 4)))
        else:
            ps_ = [(u["page"], pymupdf.Rect(x0, u["ystem0"] - 3, x1, u["y1"] + 4))]
        if u["cont"]:
            cp, cc, a, b = u["cont"]
            cx0, cx1 = CLIPX[cc]
            ps_.append((cp, pymupdf.Rect(cx0, a, cx1, b)))
        return ps_

    placed = collections.defaultdict(list)
    for ps in d["passages"]:
        pg = None
        for u in by[ps]:
            parts = pieces(u)
            h = sum(r.height for _, r in parts) + GAP
            if h > BOT - TOP:
                fail("%d번 문항이 한 칸보다 김" % u["q"])
            need_plain = u["omit"]
            if pg is None or (need_plain and not plain_on_page[-1]) or (u["modified"] and plain_on_page[-1]):
                pg, ys = new_page(ps, need_plain)
                c = 0
            if ys[c] + h > BOT:
                if c == 0:
                    c = 1
                if ys[c] + h > BOT:
                    pg, ys = new_page(ps, need_plain)
                    c = 0
                    if ys[c] + h > BOT:
                        c = 1
            y = ys[c]
            for sp, r in parts:
                pg.show_pdf_page(pymupdf.Rect(DESTX[c], y, DESTX[c] + r.width, y + r.height), src, sp, clip=r)
                y += r.height
            ys[c] = y + GAP
            placed[ps].append(u["q"])
    for i, pg in enumerate(out):
        pg.insert_text((24, 829), "변형문제 · %s번" % footer_info[i], fontsize=7.5, fontname="mg",
                       fontfile=FONT, color=(0.45, 0.48, 0.53))
        pg.insert_text((562, 829), str(i + 1), fontsize=7.5, fontname="mg", fontfile=FONT,
                       color=(0.45, 0.48, 0.53))
    return out, placed


def answers(src, d, keep):
    a0, a1 = d["answer_pages"]
    nq, essay = d["total_questions"], d.get("essay_from")
    ans = pymupdf.open()
    ans.insert_pdf(src, from_page=a0 - 1, to_page=a1 - 1)
    shown = set()
    for pg in ans:
        rows = collections.defaultdict(list)
        for w in pg.get_text("words"):
            if TOPY < w[1] < BOTY and re.fullmatch(r"\d{1,3}", w[4]) and (w[0] < 270 or w[0] > 300):
                rows[(col(w[0]), round(w[1]))].append(w)
        for (c, _), ws in rows.items():
            ws.sort(key=lambda w: w[0])
            xs = [w[0] for w in ws]
            colright = 282 if c == 0 else 572
            for k, w in enumerate(ws):
                q = int(w[4])
                if not (1 <= q <= nq):
                    continue
                nxt = xs[k + 1] - 3 if k + 1 < len(ws) else colright
                if essay and q >= essay:
                    nxt = 290 if c == 0 else 580
                r = pymupdf.Rect(w[0] - 3, w[1] - 5, nxt, w[3] + 5)
                if q in keep:
                    shown.add(q)
                else:
                    pg.add_redact_annot(r, fill=(1, 1, 1))
        pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    note = d.get("answer_note")
    if note:
        ans[0].insert_text((150, note.get("y", 64)), note["text"], fontsize=8, fontname="mg", fontfile=FONT,
                           color=(0.45, 0.48, 0.53))
    if shown != keep:
        fail("정답표에 없는 문항 %s" % sorted(keep - shown)[:20])
    return ans


# ── 4. 점검 (임시 파일 대상) ────────────────────────────────
def check(rep, d, by, placed, qpdf, apdf):
    rng = set(d["passages"])
    keep = {q for qs in placed.values() for q in qs}
    mod = {u["q"] for ps in d["passages"] for u in by[ps] if u["modified"]}
    omit = {u["q"] for ps in d["passages"] for u in by[ps] if u["omit"]}
    with pymupdf.open(qpdf) as doc, pymupdf.open(apdf) as an:
        pages = [p.get_text() for p in doc]
        atxt = C.pdf_text(an)
        page_ps = []
        for i, t in enumerate(pages):
            m = re.search(FOOT_RE, t)
            page_ps.append(m.group(1) if m else None)
            if not m:
                rep.add("꼬리말", "%d쪽 지문 번호 없음" % (i + 1))
            elif m.group(1) not in rng:
                rep.add("범위이탈", "%d쪽 지문 %s번" % (i + 1, m.group(1)))
        seen = collections.Counter()
        for t in pages:
            body = re.sub(FOOT_RE, " ", t)
            for m in re.finditer(r"(?m)^\s*(\d{1,3})\s*\.\s*\S", body):
                seen[int(m.group(1))] += 1
        if set(seen) - keep:
            rep.add("문항", "선별에 없는 문항이 지면에: %s" % sorted(set(seen) - keep)[:12])
        if keep - set(seen):
            rep.add("문항", "지면에서 못 찾은 문항: %s" % sorted(keep - set(seen))[:12])
        dup = [q for q, c in seen.items() if c > 1]
        if dup:
            rep.add("문항", "같은 문항이 두 번 실림: %s" % sorted(dup)[:12])
        for i, t in enumerate(pages):
            for pat in d.get("excluded_patterns", []):
                if pat in t:
                    rep.add("제외유형", "%d쪽 '%s'" % (i + 1, pat))
            qs = {int(m.group(1)) for m in re.finditer(r"(?m)^\s*(\d{1,3})\s*\.\s*\S", t)} & keep
            if (qs & omit) and (qs & mod):
                rep.add("정답누출", "%d쪽에 원문 지문과 변형 지문이 함께 있음 (원문 %s · 변형 %s)"
                        % (i + 1, sorted(qs & omit)[:4], sorted(qs & mod)[:4]))
            if len(re.sub(r"\s", "", t)) < 200:
                rep.add("PDF", "%d쪽 텍스트 거의 없음" % (i + 1))
            # 원본 교재 글은 선택지에 '학생이' 가 흔하다 — 우리가 덧붙인 꼬리말·안내에서만 나올 멘트만 본다
            C.teacher_words(rep, "%d쪽" % (i + 1), t, words=("판서", "채점하면", "하세요"))
        g = d.get("bynum")
        if g:
            ref_all = S.bynum(g["grade"], g["round"], sorted(rng))
            for i, t in enumerate(pages):
                ps = page_ps[i]
                if not ps:
                    continue
                body = norm(re.sub(r"[가-힣].*", " ", t))
                if len(body) < 400:
                    continue
                head, ref = body[:200], norm(ref_all.get(ps, ""))
                if head and ref and head not in ref:
                    hit = sum(1 for k in range(0, len(head) - 20, 20) if head[k:k + 20] in ref)
                    if hit < (len(head) // 20) * 0.5:
                        rep.add("지문", "%d쪽 지문이 %s번 원문과 많이 다름" % (i + 1, ps))
        else:
            rep.note("지문 원문 대조 없음 (bynum 미지정 — 이 회차 원문이 _데이터 에 없으면 생략)")
        lack = [q for q in sorted(keep) if not re.search(r"\b%d\b" % q, atxt)]
        if lack:
            rep.add("답지", "정답표에 없는 문항 %s" % lack[:12])
        rep.note("문제 %d쪽 · 문항 %d개 · 답지 %d쪽" % (len(doc), len(keep), len(an)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out")
    a = ap.parse_args()
    d = json.loads(pathlib.Path(a.data).read_text(encoding="utf-8"))
    for k in ("name", "source", "question_last_page", "answer_pages", "total_questions", "passages"):
        if k not in d:
            raise SystemExit("data.json 에 '%s' 가 없다" % k)
    if d.get("range") is not None:
        extra = [p for p in d["passages"] if p not in d["range"]]
        if extra:
            raise SystemExit("범위 밖 지문 %s" % extra)
    src = pymupdf.open(S.path(d["source"]))
    units = collect(src, d)
    by, plain, dropped = select(units, d)
    out, placed = compose(src, d, by, plain)
    keep = {q for qs in placed.values() for q in qs}
    ans = answers(src, d, keep)

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="variant_"))
    try:
        qp, apath = tmp / (d["name"] + ".pdf"), tmp / (d["name"] + "_답지.pdf")
        out.save(qp, garbage=4, deflate=True)
        ans.save(apath, garbage=4, deflate=True)
        out.close()
        ans.close()
        rep = C.Report("%s · 변형문제 점검" % d["name"])
        if dropped:
            rep.note("제외: " + ", ".join("%s %d문항" % kv for kv in dropped.items()))
        for ps in d["passages"]:
            rep.note("%s번 %d문항" % (ps, len(placed[ps])))
        check(rep, d, by, placed, qp, apath)
        rep.stop_if_bad()
        dest = pathlib.Path(a.out) if a.out else pathlib.Path(a.data).resolve().parent
        dest.mkdir(parents=True, exist_ok=True)
        for p in (qp, apath):
            shutil.copy2(p, dest / p.name)
            print("저장", dest / p.name)
        rep.print()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
