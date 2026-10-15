"""점검. 결함은 Report 에 모으고, 하나라도 있으면 빌드가 PDF를 내보내지 않는다."""
import collections
import re
import sys

from . import text as T

TEACHER_WORDS = ("하세요", "판서", "채점하면", "학생이")
# "자리"는 문법 용어일 때만 허용
JARI_OK = r"(동사|주어|목적어|보어|부사|형용사|명사|분사|원급|비교급|최상급) ?자리"
RESIDUE = ("&amp;", "&nbsp;", "<u>", "</u>", "<b>", "%s", "{{", "}}", "@@")

# ── 글쓰기 규칙 (공용/규칙/글쓰기.md) 중 기계로 잡히는 것
# 영어 관용구를 직역한 비유. "축"은 좌표축·시간 축이 있어 목록에 넣지 않는다 — 눈으로 본다.
BIYU = ("깔아 둔", "깔아 두", "각도를 잡", "한 걸음 더 나아", "손대지 않",
        "명제를 세운", "다음 장에 넘기", "목록 위에 있")
# 행위자가 없는 피동. 문법 서술("쓰인다")은 예외라 넣지 않는다.
PIDONG = ("설명된다", "여겨진다", "보여진다", "생각된다", "간주된다", "요구된다", "평가된다")
# "-음" 명사화 — 원래 명사인 것이 많아 참고로만 알린다
EUM_OK = ("다음", "처음", "마음", "사람", "이름", "믿음", "죽음", "웃음", "울음", "얼음",
          "걸음", "졸음", "소음", "잡음", "모음", "자음", "발음", "녹음", "도움", "그림")


class Report:
    def __init__(self, title):
        self.title = title
        self.bad = []
        self.info = []

    def add(self, tag, msg):
        self.bad.append("[%s] %s" % (tag, msg))

    def note(self, msg):
        self.info.append(msg)

    def __bool__(self):
        return not self.bad

    def print(self):
        print("── %s" % self.title)
        for i in self.info:
            print("  참고: " + i)
        if self.bad:
            print("  결함 %d건" % len(self.bad))
            for b in self.bad:
                print("    " + b)
        else:
            print("  결함 0")

    def stop_if_bad(self):
        """결함이 있으면 출력하고 종료 코드 1로 끝낸다."""
        if self.bad:
            self.print()
            print("\n점검 실패 — PDF를 내보내지 않았다.")
            sys.exit(1)


def teacher_words(rep, where, s, extra=(), words=TEACHER_WORDS):
    """words 를 바꿀 수 있다 — 시중 교재를 잘라 붙인 자료는 선택지 속 '학생이' 가 정상 문장이다."""
    for w in tuple(words) + tuple(extra):
        if w in s:
            rep.add("멘트", "%s에 '%s'" % (where, w))


def jari(rep, where, s):
    for m in re.finditer(r".{0,6}자리.{0,6}", s):
        if not re.search(JARI_OK, m.group(0)):
            rep.add("표현", "%s '자리': %s" % (where, m.group(0).strip()))


def writing_ko(rep, where, s):
    """글쓰기 규칙(공용/규칙/글쓰기.md) 중 기계로 잡히는 것.

    **해설·설명 글에만 건다.** 지문·발문·선택지에 걸면 발문 "가장 적절한 것은?" 이 5번에 잡힌다.
    학생 가시 요소에는 jari() 와 teacher_words() 만 건다.
    """
    s = T.strip_html(s)
    jari(rep, where, s)
    for w in BIYU:
        if w in s:
            rep.add("표현", "%s 직역 비유 '%s'" % (where, w))
    for w in PIDONG:
        if w in s:
            rep.add("표현", "%s 행위자 없는 피동 '%s'" % (where, w))
    for sent in re.split(r"[.!?…\n]+", s):
        if sent.count("것") >= 2:
            rep.add("표현", "%s 한 문장에 '것' %d번: %s" % (where, sent.count("것"), sent.strip()[:40]))
    for m in re.finditer(r"([가-힣]{1,3}음)(에|에는|으로|을|이)\b", s):
        if m.group(1) not in EUM_OK:
            rep.note("%s '-음' 명사화인지 확인: %s" % (where, m.group(0)))


def residue(rep, where, s):
    for w in RESIDUE:
        if w in s:
            rep.add("잔재", "%s에 '%s'" % (where, w))


def answer_distribution(rep, labels, answers, max_same=None, max_spread=None, no_triple=True):
    dist = collections.Counter(answers)
    shown = dict(sorted((a + 1, c) for a, c in dist.items()))
    if max_same is not None and max(dist.values()) > max_same:
        rep.add("정답분포", "한 번호가 %d회 넘음 %s" % (max_same, shown))
    if max_spread is not None:
        counts = [dist.get(i, 0) for i in range(5)]
        if max(counts) - min(counts) > max_spread:
            rep.add("정답분포", "최다·최소 차이 %d 넘음 %s" % (max_spread, shown))
    if no_triple:
        for i in range(len(answers) - 2):
            if answers[i] == answers[i + 1] == answers[i + 2]:
                rep.add("정답분포", "정답 번호 3연속 %s번부터" % labels[i])
    return shown


def quote_3gram(rep, where, answer, passage, n=3):
    hit = T.grams(answer, n) & T.grams(passage, n)
    if hit:
        rep.add("인용", "%s 모범답안이 지문과 연속 %d낱말 일치: %s" % (where, n, ", ".join(sorted(hit)[:3])))


def pdf_text(doc):
    return "\n".join(p.get_text() for p in doc)


def pdf_physical(rep, where, doc, min_chars=40, page_numbers=True, bottom_free_warn=0.30):
    """빈 쪽 · 쪽번호 · 마지막 쪽 제외 아래 여백(참고)."""
    for i, p in enumerate(doc):
        t = p.get_text()
        if len(t.strip()) < min_chars:
            rep.add("PDF", "%s %d쪽이 거의 비어 있음" % (where, i + 1))
        if page_numbers and not re.search(r"%d\s*/\s*%d" % (i + 1, len(doc)), re.sub(r"\s+", " ", t)):
            rep.add("PDF", "%s %d쪽 쪽번호 없음" % (where, i + 1))
        if i < len(doc) - 1:
            blocks = [b for b in p.get_text("blocks") if b[4].strip()]
            if blocks:
                free = (p.rect.height - max(b[3] for b in blocks)) / p.rect.height
                if free > bottom_free_warn:
                    rep.note("%s %d쪽 아래 %.0f%% 비어 있음" % (where, i + 1, free * 100))
