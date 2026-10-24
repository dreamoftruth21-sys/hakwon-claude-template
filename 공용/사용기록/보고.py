"""사용 기록 보고 — 이 컴퓨터에 쌓인 기록(공용/사용기록/기록/*.jsonl)을 묶어 제작자 시트로 보낸다.
수업준비 스킬 0단계가 부른다. 보내는 것은 선생님이 「보내」를 골랐을 때뿐이다.

    py 공용/사용기록/보고.py 상태      보낼 기록 수 · 물을 문구 (JSON 한 줄). 스킬이 이것을 읽고 묻는다
    py 공용/사용기록/보고.py 보기      보낼 내용을 거른 뒤 그대로 보여 준다 (선생님이 보고 싶다고 할 때)
    py 공용/사용기록/보고.py 미루기    「다음에」를 골랐을 때. 다음에는 "○일간 보내지 않았습니다" 문구로 묻는다
    py 공용/사용기록/보고.py 보내기    거른 뒤 수신주소.txt 의 웹 앱으로 보낸다. 성공하면 마지막 전송 시각을 적는다

거르는 것 — 반 폴더 `학생.md` 의 학생 이름(→ 학생A · 학생B …) · 메일 주소 · 전화번호 · 윈도우 사용자 이름(경로).
보내는 것 — 설치ID(이 컴퓨터를 구별하는 무작위 8자) · 템플릿 판 · 기간 · 종류별 건수 · 스킬별 횟수 · 기록(요청 요지 · 바뀐 규칙 · 오류).
학생 이름 · 점수 · 선생님 이름 · 구글 계정은 보내지 않는다.
"""
import datetime
import json
import pathlib
import re
import sys
import urllib.request
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOG_DIR = HERE / "기록"
STATE = HERE / "상태.json"
URL_FILE = HERE / "수신주소.txt"
VERSION = ROOT / "공용" / "VERSION.txt"
MAX_RECORDS = 1500

MSG_FIRST = ("이 플러그인 사용하면서 발생한 오류 관련 정보를 제작자에게 보내주세요. "
             "플러그인 보완에 사용됩니다. 개인정보는 수집하지 않습니다.")
MSG_LATER = "오류 정보를 %d일간 보내지 않았습니다. 지금 보낼까요?"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ── 상태 ──────────────────────────────────────────────────────────────
def state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def save_state(**kw):
    s = state()
    s.update(kw)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return s


def install_id():
    s = state()
    if not s.get("설치ID"):
        s = save_state(설치ID=uuid.uuid4().hex[:8])
    return s["설치ID"]


def version():
    try:
        return VERSION.read_text(encoding="utf-8-sig").strip().splitlines()[0].split(" — ")[0][:40]
    except Exception:
        return "?"


# ── 기록 읽기 ──────────────────────────────────────────────────────────
def load_records(after=""):
    recs = []
    if not LOG_DIR.exists():
        return recs
    for f in sorted(LOG_DIR.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("시각", "") > after:
                recs.append(r)
    recs.sort(key=lambda r: r.get("시각", ""))
    return recs


def counts(recs):
    c = {"요청": 0, "스킬": 0, "규칙변경": 0, "오류": 0}
    skills = {}
    for r in recs:
        k = r.get("종류")
        if k in c:
            c[k] += 1
        if k == "스킬" and r.get("내용"):
            skills[r["내용"]] = skills.get(r["내용"], 0) + 1
    c["합계"] = sum(c.values())
    return c, skills


# ── 거르기 ────────────────────────────────────────────────────────────
def student_names():
    names = set()
    for f in ROOT.glob("*/학생.md"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in re.finditer(r"^\s*-\s*\*\*([^*\n]{2,10})\*\*", text, re.M):
            names.add(m.group(1).strip())
        for m in re.finditer(r"^\s*-\s*([가-힣]{2,4})(?=\s|$|[:·(,])", text, re.M):
            names.add(m.group(1))
    names.discard("TEST")
    return sorted(names, key=len, reverse=True)


class Scrubber:
    def __init__(self):
        self.names = student_names()
        self.alias = {}

    def _alias(self, name):
        if name not in self.alias:
            n = len(self.alias)
            tag = chr(ord("A") + n % 26) + (str(n // 26) if n >= 26 else "")
            self.alias[name] = "학생" + tag
        return self.alias[name]

    def text(self, s):
        if not isinstance(s, str) or not s:
            return s
        for name in self.names:
            if name in s:
                s = s.replace(name, self._alias(name))
        s = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "[메일]", s)
        s = re.sub(r"\b01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}\b", "[전화]", s)
        s = re.sub(r"(?i)([a-z]:[\\/]users[\\/])[^\\/\s\"']+", r"\1~", s)
        return s

    def record(self, r):
        out = {}
        for k, v in r.items():
            if k == "세션":
                continue
            out[k] = self.text(v) if isinstance(v, str) else v
        return out


# ── 명령 ──────────────────────────────────────────────────────────────
def pending():
    s = state()
    recs = load_records(s.get("마지막전송", ""))
    return s, recs


def cmd_status():
    s, recs = pending()
    c, skills = counts(recs)
    out = {"설치ID": install_id(), "보낼것": c, "스킬별": skills, "문구": None, "물음": "없음"}
    if recs:
        out["기간"] = [recs[0]["시각"][:10], recs[-1]["시각"][:10]]
        if s.get("마지막답") == "다음에":
            since = s.get("마지막전송") or recs[0]["시각"]
            days = max(1, (datetime.date.today() - datetime.date.fromisoformat(since[:10])).days)
            out["미보낸일수"] = days
            out["문구"] = MSG_LATER % days
            out["물음"] = "미룸"
        else:
            out["문구"] = MSG_FIRST
            out["물음"] = "처음"
        out["보낼것줄"] = "이번에 보낼 것: 요청 %d건 · 바뀐 규칙 %d건 · 오류 %d건" % (c["요청"], c["규칙변경"], c["오류"])
    print(json.dumps(out, ensure_ascii=False))


def payload():
    s, recs = pending()
    sc = Scrubber()
    recs = recs[-MAX_RECORDS:]
    c, skills = counts(recs)
    return {
        "설치ID": install_id(), "판": version(),
        "기간": [recs[0]["시각"][:10], recs[-1]["시각"][:10]] if recs else [],
        "집계": c, "스킬별": skills,
        "기록": [sc.record(r) for r in recs if r.get("종류") != "스킬"],
    }, c


def cmd_show():
    p, c = payload()
    print("설치ID %s · 판 %s · 기간 %s" % (p["설치ID"], p["판"], " ~ ".join(p["기간"]) or "-"))
    print("요청 %d · 스킬 %d · 규칙변경 %d · 오류 %d" % (c["요청"], c["스킬"], c["규칙변경"], c["오류"]))
    if p["스킬별"]:
        print("스킬별:", ", ".join("%s %d" % kv for kv in sorted(p["스킬별"].items(), key=lambda x: -x[1])))
    for r in p["기록"]:
        body = r.get("내용") or r.get("후") or ""
        extra = (" [%s]" % r["파일"]) if r.get("파일") else ""
        print("%s %s%s%s | %s" % (r.get("시각", "")[:16], r.get("종류"), (" " + r["반"]) if r.get("반") else "", extra,
                                  body.replace("\n", " ")[:160]))


def cmd_defer():
    save_state(마지막답="다음에", 마지막질문=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("미뤘습니다. 다음 수업 준비 때 다시 묻습니다.")


def cmd_send():
    url = URL_FILE.read_text(encoding="utf-8-sig").strip() if URL_FILE.exists() else ""
    if not url.startswith("https://"):
        print("수신 주소가 없습니다 (공용/사용기록/수신주소.txt). 갱신 스킬로 새 판을 받으면 채워집니다.")
        sys.exit(1)
    p, c = payload()
    if c["합계"] == 0:
        print("보낼 기록이 없습니다.")
        return
    data = json.dumps(p, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print("보내지 못했습니다:", e)
        sys.exit(1)
    try:
        ok = json.loads(body).get("ok")
    except Exception:
        ok = False
    if not ok:
        print("받는 쪽이 오류를 돌려줬습니다:", body[:300])
        sys.exit(1)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_state(마지막전송=now, 마지막답="보내", 마지막질문=now[:16])
    print("보냈습니다 — 요청 %d건 · 바뀐 규칙 %d건 · 오류 %d건 (학생 이름 · 메일 · 전화번호는 걸렀습니다)."
          % (c["요청"], c["규칙변경"], c["오류"]))


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "상태"
    {"상태": cmd_status, "보기": cmd_show, "미루기": cmd_defer, "보내기": cmd_send}.get(c, lambda: print(__doc__))()
