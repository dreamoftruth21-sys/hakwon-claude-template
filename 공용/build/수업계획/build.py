"""수업 계획표 — 진도를 한눈에 (A4 가로 1쪽)

    py 공용/build/수업계획/build.py <계획.json> [--today 2026-10-13] [--out 폴더]

- 계획.json 은 반 `시험대비/<시험>/작업/수업계획/계획.json` 에 둔다
- 결과는 반 폴더 최상위 `<파일>.html` (화면용) + `<파일>.pdf` (인쇄용). --out 을 주면 그 폴더에
- 주 × 수업 요일 격자. 끝난 회차는 흐리게, 다음 회차는 굵은 테두리, 지났는데 끝 표시가 없는 회차는 빨간 점선
- 위쪽 띠: 구간별 회차 수와 끝난 수 · 전체 진행 · 시험까지 남은 날
- 점검에 걸리면 아무것도 쓰지 않는다. 형식은 README.md
"""
import argparse, datetime as dt, html, json, pathlib, re, sys

DAYS = "월화수목금토일"
COLORS = {  # 이름: (바탕, 진한 색)
    "파랑": ("#dbeafe", "#2563eb"), "초록": ("#dcfce7", "#16a34a"), "주황": ("#ffedd5", "#ea580c"),
    "보라": ("#ede9fe", "#7c3aed"), "빨강": ("#fee2e2", "#dc2626"), "노랑": ("#fef9c3", "#a16207"),
    "청록": ("#ccfbf1", "#0d9488"), "회색": ("#f1f5f9", "#64748b"),
}
# 수업하지 않는 날 (루트 CLAUDE.md "공휴일은 수업하지 않는다"). 음력 공휴일은 해마다 여기 더한다
HOLIDAYS = {
    "01-01": "신정", "03-01": "삼일절", "05-05": "어린이날", "06-06": "현충일", "08-15": "광복절",
    "10-03": "개천절", "10-09": "한글날", "12-25": "성탄절",
    "2026-09-24": "추석 연휴", "2026-09-25": "추석 연휴", "2026-10-05": "개천절 대체공휴일",
}
LONG = 38  # 진도 칸 글자 수 — 넘으면 경고 (한눈에 보이게)

CSS = """
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#fff;color:#1f2633;font:13px/1.45 "Malgun Gothic","맑은 고딕",sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:19px;margin:0 0 2px;color:#1e3a5f}
.sub{color:#4a5465;font-size:12px;margin-bottom:8px}
.top{display:flex;gap:14px;align-items:stretch;margin-bottom:8px}
.big{border:1px solid #c9d2df;border-radius:8px;padding:6px 12px;min-width:150px}
.big b{display:block;font-size:22px;line-height:1.15;color:#1e3a5f}
.big small{color:#4a5465;font-size:11px}
.bar{flex:1;display:flex;gap:3px}
.seg{position:relative;border-radius:6px;overflow:hidden;min-width:92px;border:1px solid #c9d2df}
.seg .fill{position:absolute;left:0;top:0;bottom:0}
.seg .lb{position:relative;padding:4px 7px;font-size:11px;line-height:1.3}
.seg .lb b{display:block;font-size:12px}
table.g{width:100%;border-collapse:separate;border-spacing:4px 3px;table-layout:fixed}
table.g th{font-size:12px;color:#4a5465;text-align:left;padding:0 4px}
td.wk{width:62px;font-size:12px;font-weight:700;color:#1e3a5f;vertical-align:middle}
td.wk small{display:block;font-weight:400;color:#4a5465;font-size:11px}
td.cell{padding:0;vertical-align:top}
.c{border-radius:6px;padding:4px 8px;border:1px solid #c9d2df;border-left-width:5px}
.c+.c{margin-top:3px}
.c.done{opacity:.5}
.c.next{outline:2.5px solid #1e3a5f;outline-offset:-1px}
.c.miss{outline:2px dashed #dc2626;outline-offset:-1px}
.c.off{background:repeating-linear-gradient(135deg,#f4f4f5 0 6px,#e9e9ec 6px 12px);color:#71717a;border-color:#d4d4d8}
.c.exam{background:#1e3a5f;color:#fff;border-color:#1e3a5f;font-weight:700}
.d{font-size:11.5px;font-weight:700;color:#4a5465;margin-right:6px}
.exam .d,.off .d{color:inherit}
.pill{display:inline-block;font-size:10px;font-weight:700;border-radius:8px;padding:0 6px;margin-left:5px;vertical-align:1px}
.pill.done{background:#e2e8f0;color:#334155}.pill.next{background:#1e3a5f;color:#fff}.pill.miss{background:#dc2626;color:#fff}
.p{font-size:12.5px;font-weight:600}
.v{font-size:11px;color:#3d4655}
.m{font-style:italic}
.ck{color:#b42318;font-weight:700}
.bot{display:flex;gap:8px;margin-top:8px}
.box{flex:1;border:1px solid #9aa7bd;border-radius:6px;padding:5px 10px}
.box h3{font-size:12px;margin:0 0 2px;color:#1e3a5f}
.box ul{margin:0;padding-left:16px}.box li{font-size:11.5px;line-height:1.4}
@page{size:A4 landscape;margin:8mm 9mm 11mm}
@media print{main{max-width:none;padding:0}}
body.compact{font-size:11px}
body.compact .p{font-size:11px} body.compact .d{font-size:11px}
body.compact .v,body.compact .m,body.compact .ck,body.compact .box li{font-size:10px}
body.compact .c{padding:2px 6px} body.compact table.g{border-spacing:3px 2px}
"""


def fail(msgs):
    print("  결함 " + str(len(msgs)) + "건")
    for x in msgs:
        print("    " + x)
    sys.exit("점검 실패 — 아무것도 쓰지 않았다.")


def parse_date(s, year, exam):
    s = str(s).strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", s):
        return dt.date.fromisoformat("-".join(p.zfill(2) for p in s.split("-")))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", s)
    if not m:
        raise ValueError(s)
    d = dt.date(year, int(m.group(1)), int(m.group(2)))
    if exam and (exam - d).days > 200:  # 12월에 짠 1월 수업처럼 해를 넘긴 날
        d = dt.date(year + 1, d.month, d.day)
    return d


def holiday(d, extra):
    for k in (d.isoformat(), d.strftime("%m-%d")):
        if k in extra:
            return extra[k]
        if k in HOLIDAYS:
            return HOLIDAYS[k]
    return None


def label(d):
    return f"{d.month}/{d.day} {DAYS[d.weekday()]}"


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def find_class_dir(p):
    for a in p.parents:
        if (a.parent / "공용").is_dir() and (a / "CLAUDE.md").exists():
            return a
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--today")
    ap.add_argument("--out")
    a = ap.parse_args()

    src = pathlib.Path(a.json).resolve()
    J = json.loads(src.read_text(encoding="utf-8"))
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    bad, warn = [], []

    for k in ("제목", "파일", "연도", "시험", "열", "구간", "회차"):
        if k not in J:
            bad.append(f"'{k}' 가 없다")
    if bad:
        fail(bad)

    year = int(J["연도"])
    exam = parse_date(J["시험"], year, None)
    title = J["제목"]
    cls_dir = find_class_dir(src)
    if cls_dir and cls_dir.name not in title:
        bad.append(f"제목에 반 이름({cls_dir.name})이 없다")
    if not re.search(r"20\d\d", title):
        bad.append("제목에 연도가 없다 (반 · 연도 · 무슨 자료)")
    out_dir = pathlib.Path(a.out).resolve() if a.out else cls_dir
    if out_dir is None:
        bad.append("반 폴더를 못 찾았다 — 계획.json 을 반 폴더 안에 두거나 --out 을 준다")

    cols = J["열"]
    col_of = {}
    for i, c in enumerate(cols):
        for y in c.get("요일", []):
            if y in col_of:
                bad.append(f"요일 '{y}' 가 열 두 곳에 있다")
            col_of[y] = i
    stages = {s["키"]: s for s in J["구간"]}
    palette = list(COLORS)
    for i, s in enumerate(J["구간"]):
        s.setdefault("색", palette[i % len(palette)])
        if s["색"] not in COLORS:
            bad.append(f"구간 '{s['키']}' 색 '{s['색']}' — 쓸 수 있는 색: {' '.join(COLORS)}")
    extra_off = {}
    for k, v in J.get("휴일", {}).items():
        extra_off[parse_date(k, year, exam).isoformat()] = v

    rows = []  # 회차마다 {dates, col, ...}
    for n, r in enumerate(J["회차"], 1):
        where = f"회차 {n}번째"
        ds = r.get("날짜")
        ds = ds if isinstance(ds, list) else [ds]
        try:
            dates = [parse_date(x, year, exam) for x in ds]
        except Exception:
            bad.append(f"{where} — 날짜를 못 읽었다: {r.get('날짜')}")
            continue
        d0 = dates[0]
        where = f"{label(d0)}"
        col = r.get("열")
        if col is None:
            col = col_of.get(DAYS[d0.weekday()])
        if col is None or not (0 <= col < len(cols)):
            bad.append(f"{where} — 들어갈 열이 없다 ('열' 요일에 {DAYS[d0.weekday()]} 를 넣거나 회차에 \"열\": 번호)")
            continue
        off = r.get("휴강")
        if not off:
            if r.get("구간") not in stages:
                bad.append(f"{where} — 구간 '{r.get('구간')}' 이 '구간' 목록에 없다")
            if not r.get("진도"):
                bad.append(f"{where} — 진도가 비었다")
            elif len(r["진도"]) > LONG:
                warn.append(f"{where} — 진도가 길다 ({len(r['진도'])}자). 한 줄로 줄인다 — 쪽·숙제는 수업안 몫")
            for d in dates:
                h = holiday(d, extra_off)
                if h:
                    bad.append(f"{label(d)} — {h}. 공휴일은 수업하지 않는다 — \"휴강\": \"휴강 — {h}\" 줄로 바꾼다")
                if d > exam:
                    bad.append(f"{label(d)} — 시험({label(exam)}) 뒤 수업")
            if r.get("끝") and d0 > today:
                bad.append(f"{where} — 아직 오지 않은 날인데 끝으로 표시했다 (기준일 {label(today)})")
        rows.append({**r, "dates": dates, "col": col, "off": off})

    keys = [(x["dates"][0], x["col"]) for x in rows]
    for k in set(keys):
        if keys.count(k) > 1:
            bad.append(f"{label(k[0])} — 같은 날 같은 열에 회차가 둘이다")
    if bad:
        fail(bad)

    rows.sort(key=lambda x: x["dates"][0])
    lessons = [x for x in rows if not x["off"]]
    total = len(lessons)
    done = sum(1 for x in lessons if x.get("끝"))
    # 같은 내용을 두 슬롯에서 나가면(월수 · 화목) 마지막 날이 지나야 끝난 회차다
    nxt = next((x for x in lessons if not x.get("끝") and x["dates"][-1] >= today), None)
    for x in lessons:
        x["state"] = "done" if x.get("끝") else ("miss" if x["dates"][-1] < today else "")
    if nxt is not None:
        nxt["state"] = "next"
    miss = [x for x in lessons if x["state"] == "miss"]
    for x in miss:
        warn.append(f"{label(x['dates'][0])} — 지난 날인데 끝 표시가 없다 (수업일지와 맞춰 '끝' 을 넣거나 일정을 고친다)")

    # ── 위쪽 띠
    seg = []
    for s in J["구간"]:
        mine = [x for x in lessons if x.get("구간") == s["키"]]
        if not mine:
            warn.append(f"구간 '{s['키']}' 에 회차가 없다")
            continue
        k = sum(1 for x in mine if x.get("끝"))
        bg, fg = COLORS[s["색"]]
        md = lambda d: f"{d.month}/{d.day}"
        span = md(mine[0]["dates"][0]) + (f"~{md(mine[-1]['dates'][0])}" if len(mine) > 1 else "")
        seg.append(f"<div class='seg' style='flex:{len(mine)};background:{bg}' title='{html.escape(span)}'>"
                   f"<div class='fill' style='width:{100 * k / len(mine):.0f}%;background:{fg};opacity:.35'></div>"
                   f"<div class='lb'><b>{html.escape(s['이름'])}</b>{k}/{len(mine)}회 · {span}</div></div>")
    dleft = (exam - today).days
    big = (f"<div class='big'><b>{done} / {total}회</b><small>남은 수업 {total - done}회 · "
           + (f"시험까지 {dleft}일" if dleft >= 0 else "시험 끝") + "</small></div>")

    # ── 격자
    weeks = {}  # 주 월요일 → 열 → 칸에 쌓을 것 (같은 주 같은 열에 휴강과 수업이 같이 올 수 있다)
    for x in rows:
        weeks.setdefault(monday(x["dates"][0]), {}).setdefault(x["col"], []).append(x)
    ex_col = col_of.get(DAYS[exam.weekday()])
    exam_mark = None
    weeks.setdefault(monday(exam), {})
    if ex_col is not None:
        weeks[monday(exam)].setdefault(ex_col, []).append({"exam": True})
    else:
        exam_mark = monday(exam)
    em = monday(exam)

    def cell(xs):
        return "<td class='cell'>" + "".join(block(x) for x in xs) + "</td>"

    def block(x):
        if x.get("exam"):
            return f"<div class='c exam'><div class='p'><span class='d'>{label(exam)}</span>시험</div></div>"
        when = " · ".join(label(d) for d in x["dates"])
        if x["off"]:
            return f"<div class='c off'><div class='p'><span class='d'>{when}</span>{html.escape(x['off'])}</div></div>"
        bg, fg = COLORS[stages[x["구간"]]["색"]]
        pill = {"done": "<span class='pill done'>✓ 끝</span>", "next": "<span class='pill next'>다음</span>",
                "miss": "<span class='pill miss'>기록?</span>"}.get(x["state"], "")
        h = (f"<div class='c {x['state']}' style='background:{bg};border-left-color:{fg}'>"
             f"<div class='p'><span class='d'>{when}</span>{html.escape(x['진도'])}{pill}</div>")
        sub = []
        if x.get("단어"):
            sub.append(f"<span>단어 {html.escape(x['단어'])}</span>")
        if x.get("메모"):
            sub.append(f"<span class='m'>{html.escape(x['메모'])}</span>")
        if x.get("확인"):
            sub.append(f"<span class='ck'>⚠ {html.escape(x['확인'])}</span>")
        if sub:
            h += "<div class='v'>" + " · ".join(sub) + "</div>"
        return h + "</div>"

    trs = []
    for wm in sorted(weeks):
        n = (em - wm).days // 7
        tag = "시험 주" if n == 0 else (f"D-{n}주" if n > 0 else "")
        if exam_mark == wm:
            tag += f" · 시험 {label(exam)}"
        tds = "".join(cell(weeks[wm].get(i, [])) for i in range(len(cols)))
        trs.append(f"<tr><td class='wk'>{wm.month}/{wm.day} 주<small>{tag}</small></td>{tds}</tr>")
    head = "".join(f"<th>{html.escape(c['이름'])}</th>" for c in cols)

    boxes = []
    for key, h3 in (("매수업", "매 수업"), ("확인", "⚠ 확인할 것"), ("상세", "자세한 계획 · 근거")):
        if J.get(key):
            boxes.append(f"<div class='box'><h3>{h3}</h3><ul>" + "".join(f"<li>{html.escape(t)}</li>" for t in J[key]) + "</ul></div>")

    sub = " · ".join(t for t in (J.get("범위"), f"시험 {label(exam)}" + (f" ({J['시험_메모']})" if J.get("시험_메모") else ""),
                                  f"기준일 {today.isoformat()}") if t)
    page = (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'><title>{html.escape(title)}</title>"
            f"<style>{CSS}</style></head><body><main>"
            f"<h1>{html.escape(title)}</h1><div class='sub'>{html.escape(sub)}</div>"
            f"<div class='top'>{big}<div class='bar'>{''.join(seg)}</div></div>"
            f"<table class='g'><colgroup><col style='width:62px'>{'<col>' * len(cols)}</colgroup>"
            f"<tr><th></th>{head}</tr>{''.join(trs)}</table>"
            + (f"<div class='bot'>{''.join(boxes)}</div>" if boxes else "")
            + f"<!-- 원본: {html.escape(str(src))} --></main></body></html>")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_html = out_dir / (J["파일"] + ".html")
    out_pdf = out_dir / (J["파일"] + ".pdf")
    tmp_pdf = out_dir / (J["파일"] + ".tmp.pdf")
    tmp_html = out_dir / (J["파일"] + ".tmp.html")
    tmp_html.write_text(page, encoding="utf-8")

    import pymupdf
    from playwright.sync_api import sync_playwright
    foot = ('<div style="width:100%;font-size:8px;color:#666;text-align:center;font-family:Malgun Gothic,sans-serif">'
            + html.escape(title) + ' &nbsp;·&nbsp; <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
    compact = False
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(tmp_html.as_uri())
        for attempt in range(2):
            pg.pdf(path=str(tmp_pdf), format="A4", landscape=True, print_background=True,
                   display_header_footer=True, header_template="<div></div>", footer_template=foot,
                   margin={"top": "8mm", "bottom": "11mm", "left": "9mm", "right": "9mm"})
            with pymupdf.open(tmp_pdf) as d:
                pages = d.page_count
            if pages == 1 or attempt == 1:
                break
            pg.evaluate("document.body.classList.add('compact')")
            compact = True
        b.close()
    tmp_html.unlink()

    with pymupdf.open(tmp_pdf) as d:
        n = d.page_count
        for i, pgx in enumerate(d, 1):
            if f"{i} / {n}" not in pgx.get_text():
                bad.append(f"{i}쪽 — 쪽 번호가 안 찍혔다")
    if bad:
        tmp_pdf.unlink(missing_ok=True)
        fail(bad)
    if n > 1:
        warn.append(f"{n}쪽이다 — 한 쪽에 들어가게 진도 글을 줄이거나 '매수업'·'확인' 을 줄인다")

    out_html.write_text(page.replace("<body>", "<body class='compact'>") if compact else page, encoding="utf-8")
    tmp_pdf.replace(out_pdf)
    print(f"── {src.name} → {out_pdf.name} · {n}쪽{' (촘촘하게)' if compact else ''} · 진행 {done}/{total} · "
          f"다음 {label(nxt['dates'][0]) if nxt else '없음'}")
    for x in warn:
        print("  경고 " + x)
    print("  저장 " + str(out_html))
    print("  저장 " + str(out_pdf))


if __name__ == "__main__":
    main()
