# -*- coding: utf-8 -*-
"""숙제 합본 — `숙제합본` 스킬("숙제 합쳐" · "숙제 합본" · "인쇄 준비")이 돌린다.

    py 공용/build/쪽뽑기/숙제합본.py <수업 폴더>      (반 폴더에서: py ../공용/build/쪽뽑기/숙제합본.py 1002금)

수업 폴더의 4_내줄숙제_*.pdf 를 이름순으로 한 파일(4_내줄숙제_합본_양면인쇄.pdf)로 합친다.
(2026-10-14부터 오늘 내줄 숙제는 "4_내줄숙제_" 이름. 그 전 폴더의 "4_숙제_" 도 읽는다)
- 양면 인쇄 기준. 한 부를 스테이플러로 묶는다
- 첫 쪽 위 양쪽 모서리에 회색 삼각형 표식을 찍는다 (첫쪽표식.py) — 인쇄 더미에서 다음 부의 첫 장을 찾는 용도
- 낱개 숙제 파일에 표식이 이미 있으면 멈춘다 — 합본 중간 쪽에 표식이 끼면 부 경계와 헷갈린다
- 전체 쪽수가 홀수면 끝에 빈 쪽을 붙인다 — 부수를 한 파일로 이어 뽑아도 다음 부가 앞면에서 시작한다
"""
import glob, os, sys
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 첫쪽표식 import mark_first_page, has_mark

OUT = "4_내줄숙제_합본_양면인쇄.pdf"
OLD_OUT = "4_숙제_합본_양면인쇄.pdf"


def main(folder):
    files = sorted(f for f in glob.glob(os.path.join(folder, "4_내줄숙제_*.pdf")) if os.path.basename(f) != OUT)
    if not files:   # 2026-10-14 전 폴더
        files = sorted(f for f in glob.glob(os.path.join(folder, "4_숙제_*.pdf")) if os.path.basename(f) != OLD_OUT)
    if not files:
        raise RuntimeError(f"{folder} 에 4_내줄숙제_*.pdf 가 없다")
    doc = pymupdf.open()
    for f in files:
        src = pymupdf.open(f)
        if any(has_mark(pg) for pg in src):
            raise RuntimeError(f"낱개 숙제 파일에 표식이 있다 (합본에만 찍는다): {os.path.basename(f)}")
        doc.insert_pdf(src)
        print(f"  {os.path.basename(f)}  {src.page_count}쪽")
    n = doc.page_count
    cs = mark_first_page(doc)
    if n % 2:
        doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
    p = os.path.join(folder, OUT)
    doc.save(p, garbage=4, deflate=True)
    print(f"→ {p}  {n}쪽" + (" + 빈 쪽 1" if n % 2 else "") + f" · 양면 {(n + 1) // 2}장 · 표식 {[tuple(round(v) for v in c) for c in cs]}")


KEY_OUT = "2_숙제확인_합본_답지.pdf"


def keys(folder):
    """그 수업 폴더의 2_숙제확인_*.pdf (지난 숙제 답지)를 한 파일로. 교사용이라 표식은 찍지 않는다."""
    files = sorted(f for f in glob.glob(os.path.join(folder, "2_숙제확인_*.pdf")) if os.path.basename(f) != KEY_OUT)
    if not files:
        raise RuntimeError(f"{folder} 에 2_숙제확인_*.pdf 가 없다")
    doc = pymupdf.open()
    for f in files:
        src = pymupdf.open(f)
        doc.insert_pdf(src)
        print(f"  {os.path.basename(f)}  {src.page_count}쪽")
    p = os.path.join(folder, KEY_OUT)
    doc.save(p, garbage=4, deflate=True)
    print(f"→ {p}  {doc.page_count}쪽")


if __name__ == "__main__":
    # py 숙제합본.py <수업 폴더>            숙제 합본
    # py 숙제합본.py --답지 <폴더> [<폴더>…]  답지 합본 (숙제를 확인하는 날의 폴더)
    if sys.argv[1] == "--답지":
        for d in sys.argv[2:]:
            keys(d)
    else:
        main(sys.argv[1])
