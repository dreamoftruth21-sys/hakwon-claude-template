"""모의고사 data.json → 온라인 답 입력용 채점키 json.

    py 공용/온라인채점/채점키.py <data.json> --id <시험ID> [--open]

- 정답은 인쇄본 기준이다. data.json 의 target(선택지 회전 뒤 번호)을 쓰고,
  같은 반 배부/ 의 <name>_답지.pdf 해설부 "N. 정답 ③" 과 대조해 하나라도 다르면 멈춘다.
- 학생 목록은 <반>/학생.md 의 "- **이름**" 줄에서 읽는다.
- 수학 빌더(공용/build/수학) data.json("subject": "math")도 읽는다 — 선택형 · 수 단답형은 자동 채점
  (같은 값의 표기 9/8 · 1.125 · 8분의 9 를 인정 답으로 펼친다), 서술형은 입력만 (math_written_item).
- 결과: 공용/온라인채점/채점키/<시험ID>_채점키.json
  이 폴더는 구글 드라이브와 동기화되므로, 웹앱이 파일명으로 찾아 읽는다.
"""
import argparse, html, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # 학원 폴더
OUT = Path(__file__).resolve().parent / "채점키"
CIRCLED = "①②③④⑤"

# 순서가 중요하다: 요약 문항 발문에 "빈칸"이 들어 있다.
TYPES = [
    ("요약", "요약"), ("영작", "영작"), ("영작", "영어로"), ("영영 풀이", "영영"),
    ("어법", "어법상"), ("어법", "용법"), ("어휘", "낱말의 쓰임"), ("어휘", "단어의 쓰임"), ("지칭", "가리키는"),
    ("무관한 문장", "관계 없는"), ("순서", "순서"), ("삽입", "들어가기"), ("삽입", "들어갈 위치"),
    ("사례", "사례"), ("사례", "예시"),
    ("내용 이해", "답할 수 없는"), ("내용 이해", "답을 찾을 수 없는"), ("내용 이해", "잘못 이해"), ("내용 이해", "설명으로"),
    ("함축 의미", "의미하는 바"), ("목적", "목적"), ("주제", "주제"), ("제목", "제목"),
    ("요지", "요지"), ("내용 일치", "일치"), ("빈칸", "빈칸"),
]


def qtype(stem):
    s = html.unescape(re.sub(r"<[^>]+>", "", stem))
    for name, key in TYPES:
        if key in s:
            return name
    print(f"  유형 미분류 → 기타: {s[:50]}")
    return "기타"


def source(pkey, passage):
    """반마다 표기가 다르다. 아는 형태만 풀어 쓰고 나머지는 지문 키를 그대로 둔다."""
    if passage is None:
        return "단독 문항"
    src = passage.get("src") or ""
    if re.fullmatch(r"L\d+", src):
        return f"교과서 {src[1:]}과"
    m = re.match(r"M(\d+)", pkey)
    if src == "M" and m:
        return f"학평 {m.group(1)}번"
    return f"지문 {pkey}"


def students(school):
    f = ROOT / school / "학생.md"
    names = re.findall(r"(?m)^- \*\*(.+?)\*\*", f.read_text(encoding="utf-8"))
    if not names:
        raise SystemExit(f"학생 이름을 못 읽음: {f}")
    return names


def printed_key(school, name):
    hits = list((ROOT / school).rglob(f"배부/{name}_답지.pdf"))
    if not hits:
        raise SystemExit(f"답지 PDF 없음: {school}/**/배부/{name}_답지.pdf")
    import pymupdf
    doc = pymupdf.open(hits[0])
    text = "\n".join(p.get_text() for p in doc)
    return {int(n): CIRCLED.index(c) + 1
            for n, c in re.findall(r"(?m)^(\d+)\.\s*정답\s*([①②③④⑤])", text)}, hits[0]


def page_of(school, name, labels, wl="서답형"):
    """시험지 PDF에서 각 문항이 처음 나오는 쪽. 번호가 순서대로 나올 때만 잡는다 (본문 속 연도·숫자 무시).
    wl: 서답형 번호 앞말 (수학은 학교 설정의 written_label)."""
    hits = list((ROOT / school).rglob(f"배부/{name}.pdf"))
    if not hits:
        print(f"  시험지 PDF 없음 → 쪽 경계 표시 없이 만든다: {name}.pdf")
        return {}
    import pymupdf
    pages, k = {}, 0
    for pno, p in enumerate(pymupdf.open(hits[0]), 1):
        for m in re.finditer(rf"(?m)^(?:(\d+)\.\s|({re.escape(wl)})\s*(\d+))", p.get_text()):
            got = f"{wl} {m.group(3)}" if m.group(2) else m.group(1)
            if k < len(labels) and got == labels[k]:
                pages[labels[k]] = pno
                k += 1
    if k != len(labels):
        print(f"  시험지 PDF에서 {labels[k]} 를 못 찾음 → 그 뒤는 쪽 경계 표시 없음")
    return pages


SYMBOLS = "ⓐⓑⓒⓓⓔⓕⓖⓗ"


def norm_text(s):
    """자동 채점 비교용 — Code.gs 의 normText_ 와 같아야 한다: 소문자 · 굽은 따옴표 → ' · 끝 문장부호 제거 · 공백 하나로"""
    s = str(s).lower().replace("’", "'").replace("‘", "'").replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"[.,;:!?]+$", "", s).strip()


def written_item(q):
    """서답형: 기호 고르기는 자동 채점. 단어 쓰기는 data.json 에 accept(인정 답 목록)가 있으면 자동 채점,
    없으면(서술형 포함) 입력만 받는다.
    accept = [[(1)의 인정 답…], [(2)…], …] · accept_pts = 칸별 배점 (칸이 하나면 생략 가능)
    accept_labels = 칸 이름 (생략하면 (1)(2)…) — 예: ["기호", "고친 표현"]"""
    ans = html.unescape(re.sub(r"<[^>]+>", "", str(q.get("answer", ""))))
    stem = html.unescape(re.sub(r"<[^>]+>", "", q["stem"]))
    if q.get("accept"):
        acc = q["accept"]
        pts = q.get("accept_pts") or [q["pt"]]
        if len(pts) != len(acc) or abs(sum(pts) - q["pt"]) > 1e-6:
            raise SystemExit(f"서답형 {q['n']}: accept {len(acc)}칸 · accept_pts {pts} 가 배점 {q['pt']} 와 맞지 않음")
        labels = q.get("accept_labels") or [f"({i + 1})" if len(acc) > 1 else "" for i in range(len(acc))]
        if len(labels) != len(acc):
            raise SystemExit(f"서답형 {q['n']}: accept_labels {len(labels)}개가 칸 수 {len(acc)} 와 다름")
        parts = [{"label": labels[i], "pt": p,
                  "accept": sorted({norm_text(a) for a in al})} for i, (al, p) in enumerate(zip(acc, pts))]
        if any(not p["accept"] for p in parts):
            raise SystemExit(f"서답형 {q['n']}: 인정 답이 빈 칸이 있음")
        return {"mode": "auto", "ans": ans, "parts": parts}
    if q["kind"] == "short" and re.fullmatch(rf"[{SYMBOLS}](\s*,\s*[{SYMBOLS}])*", ans.strip()):
        box = html.unescape(str(q.get("box") or "")) + stem
        last = max([SYMBOLS.index(c) for c in box if c in SYMBOLS] + [4])
        syms = "".join(sorted(c for c in ans if c in SYMBOLS))
        # 「모두 고르시오/적으시오」도 여러 개 선택이다 — 예전에는 「있는 대로」만 봐서 하나만 고를 수 있었다 (2026-10-07 학생 제보)
        return {"mode": "symbol", "ans": syms, "symbols": SYMBOLS[:last + 1],
                "multi": any(w in stem for w in ("있는 대로", "모두")) or len(syms) > 1}
    # criteria(채점 기준)·conditions(조건)는 서버에만 둔다 — 시트 '서술형 채점' 탭과 채점 제안에 쓴다. 학생 화면에는 가지 않는다
    crit = " / ".join(html.unescape(re.sub(r"<[^>]+>", "", str(x))) for x in
                      ([q["criteria"]] if isinstance(q.get("criteria"), str) else q.get("criteria") or []))
    cond = " / ".join(html.unescape(re.sub(r"<[^>]+>", "", str(x))) for x in (q.get("conditions") or []))
    return {"mode": "essay" if q["kind"] == "essay" else "text", "ans": ans,
            "lines": int(q.get("lines") or (1 if q["kind"] == "short" else 3)),
            "criteria": (f"[조건] {cond} " if cond else "") + crit}


def math_mods():
    """수학 빌더(공용/build/수학)의 tex · verify 를 빌려 온다."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "수학"))
    import tex, verify
    return tex, verify


def math_written_item(q):
    """수학 서답형 (subject: math).
    단답형: 답이 수(정수 · 분수 · 유한소수)면 같은 값의 여러 표기(9/8 · 1.125 · 8분의 9 …)를 인정 답으로 펼쳐 자동 채점.
            수가 아니면(근호 · 식 · 좌표) 입력만 받는다. 더 인정할 표기는 data.json 의 accept(글자 목록)에 적는다.
    서술형: 입력만 받는다 — 채점 단계(steps) · 채점 기준(criteria)은 시트 '서술형 채점' 탭으로 간다.
    휴대폰 화면에는 수식 · 그림이 나오지 않는다. 답 · 기준은 √ · a/b · ² 같은 글자로 어림해 넣는다."""
    tex, verify = math_mods()
    ans = tex.phone(q.get("answer", ""))
    if q["kind"] == "short":
        forms = []
        try:
            v = verify.py_value(q["value"]) if "value" in q else verify.tex_value(q.get("answer", ""))
            forms = verify.accept_forms(v)
        except Exception:
            pass
        extra = [a for a in (q.get("accept") or []) if isinstance(a, str)]
        if forms or extra:
            acc = sorted({norm_text(a) for a in forms + extra + [ans] if a})
            return {"mode": "auto", "ans": ans, "parts": [{"label": "", "pt": q["pt"], "accept": acc}]}
        print(f"  서답형 {q['n']}: 답 {ans} 은 수가 아니라 자동 채점하지 않는다 (인정 답은 accept 에 적는다)")
    steps = " / ".join(f"{i + 1}) {tex.phone(s['desc'])} ({s['pt']}점)" for i, s in enumerate(q.get("steps") or []))
    crit = tex.phone(q["criteria"] if isinstance(q.get("criteria"), str) else " / ".join(q.get("criteria") or []))
    return {"mode": "essay" if q["kind"] == "essay" else "text", "ans": ans,
            "lines": int(q.get("lines") or (1 if q["kind"] == "short" else 3)),
            "criteria": " ".join(x for x in (f"[단계] {steps}" if steps else "", crit) if x)}


def math_label(d):
    """수학은 학교 설정(math_exam.written_label)의 서답형 이름을 쓴다 — 인쇄본 번호와 같아야 쪽을 찾는다."""
    p = Path(__file__).resolve().parents[1] / "build" / "학교" / f"{d.get('school', '')}.json"
    if p.exists():
        return (json.loads(p.read_text(encoding="utf-8")).get("math_exam") or {}).get("written_label", "서답형")
    return "서답형"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--id", required=True, help="짧은 시험 ID (예: 세종예고1_실전1회)")
    ap.add_argument("--open", action="store_true", help="웹 페이지에 틀린 번호까지 보여 준다 (기본: 점수만)")
    ap.add_argument("--models", action="store_true",
                    help="제출 뒤 서답형(단어 쓰기·서술형) 모범답안을 내 답과 나란히 보여 준다 (한솔고 — 2026-09-28 선생님 요청)")
    a = ap.parse_args()
    if not re.fullmatch(r"[0-9A-Za-z가-힣_\-]+", a.id):
        raise SystemExit("ID에는 한글·영문·숫자·_·- 만 쓴다")

    data = Path(a.data).resolve()
    d = json.loads(data.read_text(encoding="utf-8"))
    school = data.relative_to(ROOT).parts[0]   # 반 폴더 (data.json 의 school 은 학교 이름일 수 있다)
    qs = [q for q in d["questions"] if q.get("kind", "choice") == "choice"]
    ws = [q for q in d["questions"] if q.get("kind", "choice") != "choice"]
    target = d.get("target")
    if target and len(target) != len(qs):
        raise SystemExit(f"target {len(target)}개와 선택형 {len(qs)}문항 수가 다름")

    math = d.get("subject") == "math"     # 수학 빌더 data.json — 유형은 type, 출처 칸은 단원(unit)
    wl = math_label(d) if math else "서답형"
    items = []
    for i, q in enumerate(qs):
        if q["n"] != i + 1:
            raise SystemExit(f"문항 번호가 순서대로가 아님: {q['n']}")
        ans = (target[i] if target else q["ans"]) + 1
        items.append({"n": q["n"], "label": str(q["n"]), "mode": "choice", "ans": ans, "pt": q["pt"],
                      "type": (q.get("type") or "기타") if math else qtype(q["stem"]),
                      "src": (q.get("unit") or "단독 문항") if math else
                      source(q.get("passage"), d.get("passages", {}).get(q.get("passage")))})
    for i, q in enumerate(ws):
        if q["n"] != i + 1:
            raise SystemExit(f"서답형 번호가 순서대로가 아님: {q['n']}")
        items.append({"n": len(qs) + i + 1, "label": f"{wl} {q['n']}", "pt": q["pt"],
                      "type": "단답형" if q["kind"] == "short" else "서술형",
                      "src": (q.get("unit") or "단독 문항") if math else
                      source(q.get("passage"), d.get("passages", {}).get(q.get("passage"))),
                      **(math_written_item(q) if math else written_item(q))})

    printed, pdf = printed_key(school, d["name"])
    diff = [it["n"] for it in items if it["mode"] == "choice" and printed.get(it["n"]) != it["ans"]]
    if len(printed) != len(qs) or diff:
        raise SystemExit(f"답지 PDF와 정답이 다름: {diff or '문항 수 불일치'} ({pdf.name})")

    pages = page_of(school, d["name"], [it["label"] for it in items], wl)
    for it in items:
        if it["label"] in pages:
            it["page"] = pages[it["label"]]

    total = round(sum(it["pt"] for it in items), 1)
    title = re.sub(r"<[^>]+>", "", d["title"])
    key = {"id": a.id, "school": school, "title": f"{school} · {title}", "data": data.relative_to(ROOT).as_posix(),
           "students": students(school), "choices": 5, "total": total,
           "showWrong": a.open, "showModel": a.models, "items": items}

    OUT.mkdir(exist_ok=True)
    out = OUT / f"{a.id}_채점키.json"
    out.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    auto = round(sum(it["pt"] for it in items if it["mode"] in ("choice", "symbol", "auto")), 1)
    print(f"{out}\n{len(items)}문항 · {total}점 (자동 채점 {auto}점) · 학생 {len(key['students'])}명 · 답지 PDF 대조 통과")
    if ws:
        from collections import Counter
        print("서답형:", dict(Counter(it["mode"] for it in items if it["mode"] != "choice")),
              "— symbol·auto(인정 답 목록) 는 자동 채점, text·essay 는 선생님 채점")
    print("쪽:", sorted(set(pages.values())) or "없음")
    from collections import Counter
    print("유형:", dict(Counter(it["type"] for it in items)))
    # 정답 정정이 있으면 다시 넣는다 (정답정정.py)
    fix = Path(__file__).resolve().parent / "정정" / f"{a.id}_정정.json"
    if fix.exists():
        import subprocess, sys as _sys
        subprocess.run([_sys.executable, str(Path(__file__).resolve().parent / "정답정정.py"), a.id, "--다시"], check=True)
    # 해설이 이미 있으면 다시 넣는다 (채점키를 다시 만들어도 해설이 빠지지 않게)
    if (Path(__file__).resolve().parent / "해설" / f"{a.id}_해설.json").exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("해설넣기", Path(__file__).resolve().parent / "해설넣기.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        m.main(a.id)
    else:
        print("해설 없음 — 결과 화면에 [해설 보기] 가 안 나온다 (온라인배포 스킬 4단계)")


if __name__ == "__main__":
    main()
