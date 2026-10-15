"""글자 다루기."""
import html
import re

CIRC = ["①", "②", "③", "④", "⑤"]
CIRC_ENT = ["&#9312;", "&#9313;", "&#9314;", "&#9315;", "&#9316;"]


def strip_html(s):
    """태그를 걷고 엔티티를 풀고 공백을 한 칸으로. (나성중3 chk3.py strip)"""
    s = re.sub(r"<br\s*/?>|</?div[^>]*>", " ", s or "")
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def norm_source(s):
    """원문 대조용 정규화 — 문장부호 모양·밑줄 기호·(A)(B)를 걷는다. (세종예고2 실전모의고사_2회 chk.py norm)"""
    s = re.sub(r"<br\s*/?>|</?div[^>]*>", " ", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    for a, b in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("—", "-"),
                 ("―", "-"), ("–", "-"), ("­", "-"), ("…", "..."), (" ", " "),
                 ("•", " ")):
        s = s.replace(a, b)
    s = re.sub(r"[ⓐ-ⓕ①-⑤]", "", s)
    s = re.sub(r"\((A|B)\)", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*-\s*", "-", s)
    return s.strip()


def norm_alnum(s):
    """영숫자만 남긴 소문자 — 줄바꿈·하이픈이 흔들리는 PDF 텍스트 대조용. (한솔고2 본문분석_27지문 chk.py norm)"""
    s = re.sub(r"[‘’]", "'", s or "")
    s = re.sub(r"[“”]", '"', s)
    s = re.sub(r"[–—−]", "-", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def toks(s):
    """영어 낱말 목록 (소문자, 두 글자 이상)."""
    return [w for w in re.sub(r"[^A-Za-z ]", " ", s or "").lower().split() if len(w) > 1]


def grams(s, n=3):
    """연속 n낱말 묶음 집합. (한솔고2 통합워크북_2권 chk.py grams)"""
    w = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


IRREG = {"be": ("is", "are", "was", "were", "being", "been", "am"),
         "hold": ("held",), "catch": ("caught",), "make": ("made",), "keep": ("kept",),
         "feel": ("felt",), "know": ("knew", "known"), "go": ("went", "gone"),
         "spread": ("spread",), "come": ("came",), "give": ("gave", "given"),
         "take": ("took", "taken"), "bring": ("brought",), "think": ("thought",), "find": ("found",),
         "lead": ("led",), "leave": ("left",), "seek": ("sought",), "teach": ("taught",),
         "buy": ("bought",), "lose": ("lost",), "run": ("ran",), "begin": ("began", "begun")}


def word_in_text(word, body_words, irreg=None):
    """표제어가 지문에 어형만 바뀌어 쓰였는지 — 원형·불규칙형·앞 6글자 일치(길이 차 4 이하).
    (세종예고1 9월학평_단어장 chk.py)  body_words: 지문 낱말 소문자 집합"""
    irreg = irreg or IRREG
    x = word.lower()
    if x in body_words or any(v in body_words for v in irreg.get(x, ())):
        return True
    k = min(len(x), 6)
    return any(b.startswith(x[:k]) and abs(len(b) - len(x)) <= 4 for b in body_words)


def phrase_in_text(phrase, body_words):
    """어구는 내용어 하나만 지문에 있어도 근거로 본다 (one's · A · B 제외)."""
    parts = [p for p in re.findall(r"[A-Za-z']+", phrase) if p not in ("one's", "A", "B", "sb", "sth")]
    return not parts or any(word_in_text(p, body_words) for p in parts)


def split_sentences(s):
    return [x.strip(" ;,") for x in re.split(r'(?<=[.!?"])\s+(?=[A-Z"])', s.strip()) if x.strip(" ;,")]


def rotate(opts, ans, target):
    """정답이 target 위치에 오도록 선택지를 돌린다. 돌린 칸 수 r 을 함께 돌려준다."""
    r = (ans - target) % len(opts)
    return opts[r:] + opts[:r], target, r


def remap_circled(s, r, n=5):
    """선택지를 r칸 돌렸을 때 해설 속 ①~⑤(문자·엔티티 모두)를 새 번호로 바꾼다. (나성중3 mk3.py remap)"""
    def ent(m):
        i = int(m.group(1)) - 9312
        return "&#%d;" % (9312 + (i - r) % n)

    def lit(m):
        i = CIRC.index(m.group(0))
        return CIRC[(i - r) % n]
    s = re.sub(r"&#(931[2-6]);", ent, s)
    return re.sub(r"[①-⑤]", lit, s)


def fmt_pt(p):
    return ("%d" % p) if abs(p - round(p)) < 1e-9 else ("%.1f" % p)
