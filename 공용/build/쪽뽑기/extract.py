"""교재 PDF 에서 필요한 쪽만 뽑아 수업 폴더에 넣는다.

    py 공용/build/쪽뽑기/extract.py <jobs.json>
    py 공용/build/쪽뽑기/extract.py <교재키> <쪽> <저장경로>          # 한 건만
    py 공용/build/쪽뽑기/extract.py --list                              # 등록된 교재 보기

- 쪽은 **책에 인쇄된 쪽 번호**로 쓴다: "162-165", "68-69,71", "148". 교재.json 의 offset 으로 PDF 쪽을 구한다
  (offset 이 없는 교재 — 정답지처럼 인쇄 쪽 번호가 흩어진 것 — 는 "pdf:23" 처럼 PDF 쪽으로 준다)
- 경로는 학원 폴더 기준. 저장 경로는 실행한 폴더 기준 (반 폴더에서 돌리면 "0930수/3_수업_….pdf")
- 점검: 뽑은 쪽마다 글자나 그림이 있는지 본다. 빈 쪽이 하나라도 있으면 저장하지 않는다
  (내콘 부가자료 PDF 는 여는 순간 "aes" 경고가 뜨는데 내용은 멀쩡하다 — 경고를 끄고 이 점검으로 대신한다)

jobs.json:
  [{"src": "내콘중3_중간_L7", "pages": "162-165", "out": "0930수/3_수업_내콘L7_문법_162-165.pdf"},
   {"src": "내콘중3_중간_정답", "pages": "pdf:23", "out": "1002금/2_숙제확인_내콘L7_166-167_답지.pdf"}]
"""
import json, pathlib, sys
import pymupdf

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent          # 학원 폴더
BOOKS = json.loads((HERE / "교재.json").read_text(encoding="utf-8-sig"))
pymupdf.TOOLS.mupdf_display_errors(False)


def pdf_pages(book, spec):
    """'162-165,170' → PDF 쪽 번호(1부터) 목록. 'pdf:' 로 시작하면 PDF 쪽 그대로."""
    raw = spec.startswith("pdf:")
    spec = spec[4:] if raw else spec
    off = 0 if raw else book.get("offset")
    if off is None:
        sys.exit(f"[점검] {book['pdf']} 는 인쇄 쪽 → PDF 쪽 대응(offset)이 없다. 'pdf:' 로 PDF 쪽을 준다")
    out = []
    for part in str(spec).split(","):
        a, _, b = part.strip().partition("-")
        a, b = int(a), int(b or a)
        out += [n - off for n in range(a, b + 1)]
    return out


def run(job):
    key = job["src"]
    if key not in BOOKS:
        sys.exit(f"[점검] 교재.json 에 '{key}' 가 없다 — 등록부터 한다 (--list 로 목록)")
    book = BOOKS[key]
    src = pymupdf.open(ROOT / book["pdf"])
    pages = pdf_pages(book, job["pages"])
    bad = [p for p in pages if not (1 <= p <= src.page_count)]
    if bad:
        sys.exit(f"[점검] {key} {job['pages']} → PDF {bad}쪽이 범위 밖 (1~{src.page_count})")
    doc = pymupdf.open()
    for p in pages:
        doc.insert_pdf(src, from_page=p - 1, to_page=p - 1)
    empty = [pages[i] for i, pg in enumerate(doc)
             if len(pg.get_text().strip()) < 5 and not pg.get_images() and not pg.get_drawings()]
    out = pathlib.Path(job["out"])
    if empty:
        sys.exit(f"[점검] {out.name}: PDF {empty}쪽이 비어 있다 — 저장하지 않았다")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    print(f"  {out}  ← {key} {job['pages']} ({doc.page_count}쪽)")


def main():
    a = sys.argv[1:]
    if a == ["--list"]:
        for k, v in BOOKS.items():
            print(f"{k:22} offset={v.get('offset', '-')!s:5} {v['pdf']}  {v.get('memo', '')}")
        return
    if len(a) == 3:
        jobs = [{"src": a[0], "pages": a[1], "out": a[2]}]
    elif len(a) == 1:
        jobs = json.loads(pathlib.Path(a[0]).read_text(encoding="utf-8-sig"))
    else:
        sys.exit(__doc__)
    for j in jobs:
        run(j)
    print(f"── 쪽뽑기 {len(jobs)}건 · 결함 0")


if __name__ == "__main__":
    main()
