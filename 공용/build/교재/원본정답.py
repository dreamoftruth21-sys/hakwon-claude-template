# -*- coding: utf-8 -*-
"""다른 교재에서 가져온 정답 쪽에서 교재에 넣지 않은 활동의 답을 지운다 (글자까지 — 복사 · 검색에도 남지 않게).

원본 정답 쪽은 여러 활동의 답이 한 쪽에 섞여 있다. 쪽을 읽는 순서(왼쪽 단 → 오른쪽 단)로 글자 덩어리를 훑으며
지금 어느 활동의 답인지(상태)를 따라가고, 남길 활동이 아니면 그 덩어리를 지운다.

종류 (교재.json sources 의 "kind"):
  이그잼포유워크북  "워크북 N" 머리 · "본문 외 지문"(World Link) → clean {"keep": ["워크북2", …]}
  쏠북워크북        "어휘 선택 12p" 같은 활동 머리 + 문항 "01 " → clean {"keep": [활동…], "max_item": {"*": 5, "문장삽입": 4}}
                    (쪽 전체에 깔린 답 칸 회색 바탕 그림은 지운 칸 바탕만 남아서 통째로 뺀다)
  이그잼포유GBU     "Pattern 1 Exercise 9" 머리 → clean {"drop": [[1, 9], …]}  (Warm-up · 실전문제 = Exercise 0 · 기출 = 99)
clean 에 "head": [앞쪽, [x0, y0, x1, y1]] — 앞 쪽 맨 아래에만 남는 활동 머리를 이 쪽 왼쪽 단 맨 위로 끌어온다 (빈 쪽을 만들지 않게).
"""
import re
import pymupdf

SOL_SEC = re.compile(r"^(어휘 선택|어법 선택|동사 바꾸기|어법 오류 수정|빈칸 채우기|내용일치 TF|순서배열|문장삽입|단어배열|해석 쓰기|영작)\s*\d+p")
SOL_TAIL = re.compile(r"(?m)^(어휘 선택|어법 선택|동사 바꾸기|어법 오류 수정|빈칸 채우기|내용일치 TF|순서배열|문장삽입|단어배열|해석 쓰기|영작)\s*\d+p\s*$")
SOL_OUT = re.compile(r"\[(Read Culture|Read More|World Link)\]")


def blocks(pg):
    """본문 글자 덩어리를 읽는 순서로. 머리글 · 바닥글 · 'Answer Key' 머리는 뺀다."""
    W, H = pg.rect.width, pg.rect.height
    bl = [b for b in pg.get_text("blocks") if b[6] == 0 and b[3] > 50 and b[1] < H - 45 and "Answer Key" not in b[4]]
    return sorted(bl, key=lambda b: (b[0] > W / 2 - 10, b[1]))


def state(kind, b, st):
    t = re.sub(r"\s+", " ", b[4]).strip()
    if kind == "이그잼포유워크북":
        m = re.match(r"워크북\s?(\d+)", t)
        if "본문 외 지문" in t: st["sec"] = "WL"
        elif m: st["sec"] = "워크북" + m.group(1)
    elif kind == "쏠북워크북":
        m = SOL_SEC.match(t)
        if m: st["sec"], st["item"], st["out"] = m.group(1), None, False
        else:
            mi = re.match(r"(\d\d)\s", t)
            if mi and st.get("sec"): st["item"] = int(mi.group(1))
            if SOL_OUT.search(t): st["out"] = True                # 범위 밖 지문 표시 — 다음 활동 머리까지 지운다 (번호가 01부터 다시 시작하는 활동)
            mt = SOL_TAIL.search(b[4])                            # 앞 활동 해설 덩어리 끝에 붙은 다음 활동 머리 — 이 덩어리를 판정한 뒤에 바꾼다
            if mt: st["pending"] = mt.group(1)
    elif kind == "이그잼포유GBU":
        m = re.match(r"Pattern (\d) (Exercise (\d+)|Warm-up|실전문제|기출)", t)
        if m: st["sec"] = [int(m.group(1)), int(m.group(3)) if m.group(3) else (99 if m.group(2) == "기출" else 0)]
    else:
        raise ValueError(f"정답 지우기를 모르는 종류: {kind}")


def after(st):
    if st.get("pending"): st["sec"], st["item"], st["out"] = st.pop("pending"), None, False


def keep(kind, spec, st):
    sec = st.get("sec")
    if sec is None: return True                                  # 첫 활동 머리 앞 (책 머리글)
    if kind == "이그잼포유워크북": return sec in spec["keep"]
    if kind == "쏠북워크북":
        it, mx = st.get("item"), spec.get("max_item", {})
        return sec in spec["keep"] and not st.get("out") and (it is None or it <= mx.get(sec, mx.get("*", 99)))
    if kind == "이그잼포유GBU": return sec not in spec["drop"]
    return True


def clean(pg, kind, p, spec, srcdoc, first):
    """pg = 책에 넣은 원본 p쪽. first = 원본에서 정답이 시작하는 쪽 (앞 쪽에서 이어지는 활동을 알아내려고). 지운 덩어리 수를 돌려준다."""
    st = {}
    for q in range(first, p):
        for b in blocks(srcdoc[q - 1]): state(kind, b, st); after(st)
    hide, right = [], False
    W = pg.rect.width
    for b in blocks(pg):
        state(kind, b, st)
        if not keep(kind, spec, st): hide.append(pymupdf.Rect(b[:4]) + (-12, -2, 2, 2))   # 왼쪽 머리표 그림까지
        elif b[0] > W / 2 - 10: right = True
        after(st)
    if hide and not right:                                       # 오른쪽 단을 다 지웠으면 가운데 점선도
        hide.append(pymupdf.Rect(W / 2 - 1, 50, W / 2 + 8, pg.rect.height - 60))
    for r in hide: pg.add_redact_annot(r, fill=(1, 1, 1))
    if hide: pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED)
    if kind == "쏠북워크북":
        for im in pg.get_images(): pg.delete_image(im[0])
    if spec.get("head"): pull_head(pg, spec["head"], srcdoc)
    return len(hide)


def pull_head(pg, head, srcdoc):
    """앞 쪽 맨 아래에만 있는 활동 머리를 이 쪽 왼쪽 단 맨 위로 끌어오고, 남긴 답은 그 아래로 내린다."""
    q, clip = head; clip = pymupdf.Rect(clip)
    kept = [pymupdf.Rect(b[:4]) for b in blocks(pg) if b[0] < pg.rect.width / 2 - 10]
    if not kept: raise RuntimeError("정답 쪽에 남긴 답이 없다")
    body = pymupdf.Rect(18, min(r.y0 for r in kept) - 4, pg.rect.width / 2 - 2, max(r.y1 for r in kept) + 4)
    tmp = pymupdf.open(); tmp.insert_pdf(pg.parent, from_page=pg.number, to_page=pg.number)
    pg.add_redact_annot(body, fill=(1, 1, 1)); pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
    top = body.y0
    pg.show_pdf_page(pymupdf.Rect(body.x0 - 4, top, body.x0 - 4 + clip.width, top + clip.height), srcdoc, q - 1, clip=clip)
    y = top + clip.height + 2
    pg.show_pdf_page(pymupdf.Rect(body.x0, y, body.x1, y + body.height), tmp, 0, clip=body)
