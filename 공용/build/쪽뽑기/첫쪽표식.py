# -*- coding: utf-8 -*-
"""첫 쪽 표식 — 학생에게 배부하는 자료의 첫 쪽 위 양쪽 모서리에 회색 삼각형을 찍는다.

    py 공용/build/쪽뽑기/첫쪽표식.py <pdf> [<pdf> …]      (반 폴더에서: py ../공용/build/쪽뽑기/첫쪽표식.py 1002금/1_단어시험_….pdf)

인쇄 더미에서 한 부씩 스테이플러로 찝을 때 다음 부의 첫 장을 찾는 표식이다 (2026-10-02 강사 지정).
- 삼각형은 변 약 18mm, 직각이 종이 모서리에 온다
- 위 모서리에 내용이 있으면 그쪽만 아래 모서리로 내린다. 위아래 다 막히면 멈춘다
- 이미 찍힌 파일은 건너뛴다 (두 번 돌려도 된다)
- 답지(교사용) · 단어 시험지(1~2쪽) · 합본에 들어갈 낱개 숙제 파일에는 찍지 않는다 — 숙제는 합본(숙제합본.py)에만 찍는다
"""
import os, sys
import pymupdf

MARK = 51          # pt (약 18mm)
GRAY = (.5, .5, .5)


def _tri(pg, c):
    r = pg.rect
    cx = c.x1 if c.x1 >= r.x1 - 1 else c.x0
    cy = c.y0 if c.y0 <= 1 else c.y1
    ox = c.x0 if cx == c.x1 else c.x1
    oy = c.y1 if cy == c.y0 else c.y0
    pg.draw_polyline([(cx, cy), (ox, cy), (cx, oy), (cx, cy)], color=None, fill=GRAY, closePath=True)


def has_mark(pg):
    """모서리에 붙은 회색 삼각형(이 도구가 찍은 것)이 있는가."""
    r = pg.rect
    for d in pg.get_drawings():
        f, b = d.get("fill"), d["rect"]
        if not f or any(abs(a - g) > .02 for a, g in zip(f, GRAY)):
            continue
        if b.width > 70 or b.height > 70 or abs(b.width - b.height) > 2:
            continue
        if (b.x0 < 1 or b.x1 > r.x1 - 1) and (b.y0 < 1 or b.y1 > r.y1 - 1):
            return True
    return False


def corners(pg):
    """오른쪽·왼쪽에 하나씩. 위 모서리에 내용이 있으면 그쪽은 아래 모서리로 내린다."""
    r = pg.rect
    draws = [d["rect"] for d in pg.get_drawings()]
    imgs = [pymupdf.Rect(i["bbox"]) for i in pg.get_image_info()]

    words = [pymupdf.Rect(w[:4]) for w in pg.get_text("words")]

    def free(c):
        # 네모 칸이 아니라 삼각형과 겹치는지 본다 — 모서리에서 가장 가까운 점까지 dx + dy 가 변 길이 안쪽이면 겹친다
        px = r.x1 if c.x1 >= r.x1 - 1 else 0
        py = 0 if c.y0 <= 1 else r.y1
        for x in words + [b for b in draws + imgs if b.get_area() < r.get_area() * 0.5]:
            dx = max(x.x0 - px, px - x.x1, 0)
            dy = max(x.y0 - py, py - x.y1, 0)
            if dx + dy < MARK + 3:
                return False
        return True

    out = []
    for x0 in (r.x1 - MARK, 0):
        for y0 in (0, r.y1 - MARK):
            c = pymupdf.Rect(x0, y0, x0 + MARK, y0 + MARK)
            if free(c):
                out.append(c)
                break
        else:
            raise RuntimeError("첫 쪽 " + ("오른쪽" if x0 else "왼쪽") + " 모서리에 내용이 있어 표식을 둘 곳이 없다")
    return out


def mark_first_page(doc):
    """doc 첫 쪽에 표식을 찍고 찍은 칸을 돌려준다. 이미 있으면 None."""
    pg = doc[0]
    if has_mark(pg):
        return None
    cs = corners(pg)
    for c in cs:
        _tri(pg, c)
    return cs


def main(paths):
    for p in paths:
        name = os.path.basename(p)
        if "답지" in name or "ANSWER" in name.upper() or "정답" in name:
            raise RuntimeError(f"답지에는 찍지 않는다: {name}")
        doc = pymupdf.open(p)
        cs = mark_first_page(doc)
        if cs is None:
            print(f"  {name}  이미 표식 있음")
            continue
        doc.save(p, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        print(f"  {name}  표식 {[tuple(round(v) for v in c) for c in cs]}")


if __name__ == "__main__":
    main(sys.argv[1:])
