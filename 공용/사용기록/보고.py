"""사용 기록 보고 — 이 컴퓨터에 쌓인 기록(공용/사용기록/기록/*.jsonl)과 만든 자료 · 스킬을 묶어 제작자 시트로 보낸다.
수업준비 스킬 0단계가 부른다. 보내는 것은 선생님이 「보내」를 골랐을 때뿐이다.

    py 공용/사용기록/보고.py 상태          보낼 기록 수 · 물을 문구 (JSON 한 줄). 스킬이 이것을 읽고 묻는다
    py 공용/사용기록/보고.py 보기          보낼 내용을 거른 뒤 그대로 보여 준다 (선생님이 보고 싶다고 할 때)
    py 공용/사용기록/보고.py 과목 <과목>   이 컴퓨터 선생님의 과목을 적는다 (영어 · 수학 · 국어 …). 보낼 때 같이 간다
    py 공용/사용기록/보고.py 미루기        「다음에」를 골랐을 때. 다음에는 "○일간 보내지 않았습니다" 문구로 묻는다
    py 공용/사용기록/보고.py 보내기        거른 뒤 수신주소.txt 의 웹 앱으로 보낸다. 성공하면 마지막 전송 시각을 적는다

보내는 것 — 설치ID(이 컴퓨터를 구별하는 무작위 8자) · 템플릿 판 · 과목 · 기간 · 종류별 건수 · 스킬별 횟수
  · 기록: 요청 · Claude 답 · 바뀐 규칙 · 오류
  · 자료: 지난 전송 뒤 만들거나 고친 문제 · 시험지의 data.json (반 폴더 안 `작업/` 아래). 과목별로 선생님끼리 문제를 나눠 쓰는 데 쓴다
  · 스킬: 선생님이 새로 만들었거나 고친 스킬 폴더의 파일 전부 (템플릿 판_지문과 대조해 찾는다)
거르는 것 — 반 폴더 `학생.md` 의 학생 이름(→ 학생A · 학생B …) · 메일 주소 · 전화번호 · 윈도우 사용자 이름(경로).
자료에서 빼는 것 — 경로에 피드백 · 채점 · 결과 · 답안 · 배부본 · 정정이 들어간 파일 (학생 답 · 점수가 들어 있을 수 있다) · 설치 확인용 샘플(_설치확인).
처음 세팅 중 기록은 오류만 보낸다 (공용/설정상태.json 의 6_안내 · 설치끝 기준).
학생 점수 · 선생님 구글 계정은 보내지 않는다.
"""
import datetime
import hashlib
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
MANIFEST = ROOT / "공용" / "판_지문.json"
SKILL_DIR = ROOT / ".claude" / "skills"
MAX_RECORDS = 1500
SHOW_RECORDS = 50           # 「보기」가 보여 주는 기록 수

MAX_FILE = 300_000          # 자료 · 스킬 파일 하나 (글자)
MAX_TOTAL = 3_000_000       # 한 번 보내는 자료 · 스킬 합계 (글자)
MAX_MATERIALS = 40          # 한 번에 보내는 자료 수
SHARE_EXCLUDE = ("피드백", "채점", "결과", "답안", "배부본", "정정", "_설치확인")   # _설치확인 은 처음시작 4단계 샘플
SKILL_EXT = (".md", ".py", ".js", ".json", ".txt", ".ps1", ".html", ".css", ".gs")

MSG_FIRST = ("이 플러그인을 쓰면서 남은 기록(요청과 답 · 오류 · 만든 문제 · 만든 스킬)을 제작자에게 보내 주세요. "
             "플러그인 보완과 과목별 선생님끼리 문제를 나눠 쓰는 데 씁니다. 학생 이름 · 연락처는 빼고 보냅니다.")
MSG_LATER = "기록을 %d일간 보내지 않았습니다. 지금 보낼까요?"

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
    c = {"요청": 0, "답": 0, "스킬": 0, "규칙변경": 0, "오류": 0}
    skills = {}
    for r in recs:
        k = r.get("종류")
        if k in c:
            c[k] += 1
        if k == "스킬" and r.get("내용"):
            skills[r["내용"]] = skills.get(r["내용"], 0) + 1
    c["합계"] = sum(c.values())
    return c, skills


# ── 만든 자료 · 스킬 찾기 ──────────────────────────────────────────────
def read_text(path):
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return None


def fingerprint(path):
    """판지문.py 와 같은 지문 (줄 끝 · BOM 무시, sha256 앞 32자)."""
    try:
        data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        return hashlib.sha256(data).hexdigest()[:32]
    except Exception:
        return None


def managed(rel):
    """판지문.py 의 「갱신이 덮어쓰는 파일」 기준. 판지문.py 가 없으면 모두 템플릿 파일로 본다."""
    try:
        sys.path.insert(0, str(ROOT / "공용"))
        import 판지문
        return 판지문.managed(rel)
    except Exception:
        return True


def class_dirs():
    out = []
    for d in sorted(ROOT.iterdir()):
        if d.is_dir() and not d.name.startswith(("_", ".")) and d.name != "공용" and (d / "CLAUDE.md").exists():
            out.append(d)
    return out


def since_ts(s):
    try:
        return datetime.datetime.strptime(s.get("마지막전송", ""), "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return 0.0


def find_materials(after_ts):
    """지난 전송 뒤 만들거나 고친 반 폴더의 data.json — 문제 · 시험지 · 단어 시험지의 원본."""
    found = []
    for d in class_dirs():
        for f in d.rglob("data.json"):
            rel = f.relative_to(ROOT).as_posix()
            parts = rel.split("/")
            if "작업" not in parts or any(w in rel for w in SHARE_EXCLUDE):
                continue
            try:
                mt = f.stat().st_mtime
            except Exception:
                continue
            if mt <= after_ts:
                continue
            found.append((mt, f, rel, d.name))
    found.sort(key=lambda x: x[0], reverse=True)          # 최근 것부터
    out = []
    for mt, f, rel, ban in found[:MAX_MATERIALS]:
        parts = rel.split("/")
        kind = parts[1] if len(parts) > 2 else ""          # 시험대비 · 단어시험 · 정규수업 …
        name = f.parent.name                                 # 시험 · 회차 이름
        out.append({"반": ban, "종류": kind, "이름": name, "파일": rel,
                    "고친 시각": datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M"), "_path": f})
    return out


def find_skills(sent):
    """템플릿에 없는 스킬(새로) · 템플릿 것과 지문이 다른 스킬(수정). 지난번에 보낸 그대로면 뺀다."""
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig")).get("파일", {})
    except Exception:
        manifest = {}
    out = []
    if not SKILL_DIR.exists():
        return out
    for d in sorted(SKILL_DIR.iterdir()):
        if not d.is_dir():
            continue
        files = sorted(f for f in d.rglob("*") if f.is_file() and f.suffix.lower() in SKILL_EXT
                       and "__pycache__" not in f.parts)
        if not files:
            continue
        rels = {f: f.relative_to(ROOT).as_posix() for f in files}
        in_template = any(r in manifest for r in rels.values())
        if in_template:   # 템플릿 스킬은 갱신이 덮어쓰는 파일만 본다 — rules.ps1 같은 선생님 몫 파일은 빼고
            files = [f for f in files if managed(rels[f])]
            if not files:
                continue
        fps = {rels[f]: fingerprint(f) for f in files}
        if in_template and all(manifest.get(r) == h for r, h in fps.items()):
            continue                                         # 템플릿 그대로
        whole = hashlib.sha256(json.dumps(fps, sort_keys=True).encode()).hexdigest()[:16]
        if sent.get(d.name) == whole:
            continue                                         # 지난번에 보낸 그대로
        changed = [r for r, h in fps.items() if manifest.get(r) != h]
        out.append({"이름": d.name, "상태": "수정" if in_template else "새로", "바뀐 파일": changed,
                    "_files": files, "_rels": rels, "_hash": whole})
    return out


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
def setup_cutoff():
    """처음 세팅이 끝난 시각. 그 전 기록은 오류만 보낸다 — 세팅 대화 · 반 정보 채우기는 보내도 쓸모가 없다.
    세팅 중이면 "9999"(모두 세팅 기록), 끝난 시각을 모르는 옛 설치는 ""(세팅 기록 없음으로 본다)."""
    try:
        st = json.loads((ROOT / "공용" / "설정상태.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return ""
    if not (st.get("단계") or {}).get("6_안내"):
        return "9999"
    return st.get("설치끝", "")


def pending():
    s = state()
    cutoff = setup_cutoff()
    recs = [r for r in load_records(s.get("마지막전송", ""))
            if r.get("종류") == "오류" or r.get("시각", "") > cutoff]
    return s, recs


def gather():
    """보낼 것 전부 — (상태, 기록, 자료, 스킬)."""
    s, recs = pending()
    mats = find_materials(since_ts(s))
    skills = find_skills(s.get("보낸스킬", {}))
    return s, recs, mats, skills


def summary_line(c, mats, skills):
    return ("이번에 보낼 것: 요청 %d건 · 답 %d건 · 바뀐 규칙 %d건 · 오류 %d건 · 만든 자료 %d개 · 새로 만들거나 고친 스킬 %d개"
            % (c["요청"], c["답"], c["규칙변경"], c["오류"], len(mats), len(skills)))


def cmd_status():
    s, recs, mats, skills = gather()
    c, by_skill = counts(recs)
    out = {"설치ID": install_id(), "과목": s.get("과목"), "과목물음": not s.get("과목"),
           "보낼것": c, "자료수": len(mats), "스킬수": len(skills), "스킬별": by_skill, "문구": None, "물음": "없음"}
    if recs or mats or skills:
        dates = [r["시각"][:10] for r in recs] + [m["고친 시각"][:10] for m in mats]
        out["기간"] = [min(dates), max(dates)] if dates else []
        if s.get("마지막답") == "다음에":
            since = s.get("마지막전송") or (min(dates) if dates else datetime.date.today().isoformat())
            days = max(1, (datetime.date.today() - datetime.date.fromisoformat(since[:10])).days)
            out["미보낸일수"] = days
            out["문구"] = MSG_LATER % days
            out["물음"] = "미룸"
        else:
            out["문구"] = MSG_FIRST
            out["물음"] = "처음"
        out["보낼것줄"] = summary_line(c, mats, skills)
    print(json.dumps(out, ensure_ascii=False))


def payload():
    s, recs, mats, skills = gather()
    sc = Scrubber()
    recs = recs[-MAX_RECORDS:]
    c, by_skill = counts(recs)
    budget = MAX_TOTAL
    notes = []

    mat_out = []
    for m in mats:
        text = read_text(m["_path"])
        if text is None:
            continue
        if len(text) > MAX_FILE or len(text) > budget:
            notes.append("자료 %s — 너무 커서 뺌 (%d자)" % (m["파일"], len(text)))
            continue
        budget -= len(text)
        mat_out.append({k: sc.text(v) if isinstance(v, str) else v for k, v in m.items() if not k.startswith("_")}
                       | {"내용": sc.text(text), "글자수": len(text)})

    skill_out = []
    for k in skills:
        files = {}
        for f in k["_files"]:
            text = read_text(f)
            if text is None:
                continue
            if len(text) > MAX_FILE or len(text) > budget:
                notes.append("스킬 %s 의 %s — 너무 커서 뺌" % (k["이름"], k["_rels"][f]))
                continue
            budget -= len(text)
            files[k["_rels"][f]] = sc.text(text)
        skill_out.append({"이름": k["이름"], "상태": k["상태"], "바뀐 파일": k["바뀐 파일"], "파일": files})

    dates = [r["시각"][:10] for r in recs] + [m["고친 시각"][:10] for m in mats]
    p = {
        "설치ID": install_id(), "판": version(), "과목": s.get("과목") or "",
        "기간": [min(dates), max(dates)] if dates else [],
        "집계": c | {"자료": len(mat_out), "새스킬": len(skill_out)}, "스킬별": by_skill,
        "기록": [sc.record(r) for r in recs if r.get("종류") != "스킬"],
        "자료": mat_out, "스킬": skill_out, "뺀것": notes,
    }
    return p, c, {k["이름"]: k["_hash"] for k in skills}


def cmd_show():
    p, c, _ = payload()
    print("설치ID %s · 판 %s · 과목 %s · 기간 %s" % (p["설치ID"], p["판"], p["과목"] or "(안 정함)", " ~ ".join(p["기간"]) or "-"))
    print("요청 %d · 답 %d · 스킬 사용 %d · 규칙변경 %d · 오류 %d · 만든 자료 %d · 새로 만들거나 고친 스킬 %d"
          % (c["요청"], c["답"], c["스킬"], c["규칙변경"], c["오류"], len(p["자료"]), len(p["스킬"])))
    if p["스킬별"]:
        print("스킬별:", ", ".join("%s %d" % kv for kv in sorted(p["스킬별"].items(), key=lambda x: -x[1])))
    for m in p["자료"]:
        print("자료  %s · %s · %s (%d자)" % (m["반"], m["종류"], m["이름"], m["글자수"]))
    for k in p["스킬"]:
        print("스킬  %s (%s) — 파일 %d개: %s" % (k["이름"], k["상태"], len(k["파일"]), ", ".join(k["파일"])))
    for n in p["뺀것"]:
        print("뺌   ", n)
    recs = p["기록"]
    if len(recs) > SHOW_RECORDS:                     # 대화에 다 붙이면 한도를 쓴다 — 최근 것만
        print("(기록 %d건 중 최근 %d건만 보여 줍니다)" % (len(recs), SHOW_RECORDS))
        recs = recs[-SHOW_RECORDS:]
    for r in recs:
        body = r.get("내용") or r.get("후") or ""
        extra = (" [%s]" % r["파일"]) if r.get("파일") else ""
        print("%s %s%s%s | %s" % (r.get("시각", "")[:16], r.get("종류"), (" " + r["반"]) if r.get("반") else "", extra,
                                  body.replace("\n", " ")[:160]))


def cmd_subject():
    if len(sys.argv) < 3 or not sys.argv[2].strip():
        print("쓰는 법: 과목 <과목 이름>  (예: 과목 영어)")
        sys.exit(1)
    save_state(과목=sys.argv[2].strip()[:20])
    print("과목을 %s(으)로 적었습니다." % sys.argv[2].strip()[:20])


def cmd_defer():
    save_state(마지막답="다음에", 마지막질문=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("미뤘습니다. 다음 수업 준비 때 다시 묻습니다.")


def cmd_send():
    url = URL_FILE.read_text(encoding="utf-8-sig").strip() if URL_FILE.exists() else ""
    if not url.startswith("https://"):
        print("수신 주소가 없습니다 (공용/사용기록/수신주소.txt). 갱신 스킬로 새 판을 받으면 채워집니다.")
        sys.exit(1)
    p, c, skill_hashes = payload()
    if c["합계"] == 0 and not p["자료"] and not p["스킬"]:
        print("보낼 기록이 없습니다.")
        return
    data = json.dumps(p, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
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
    sent = state().get("보낸스킬", {})
    sent.update(skill_hashes)
    save_state(마지막전송=now, 마지막답="보내", 마지막질문=now[:16], 보낸스킬=sent)
    print("보냈습니다 — 요청 %d건 · 답 %d건 · 바뀐 규칙 %d건 · 오류 %d건 · 만든 자료 %d개 · 스킬 %d개 "
          "(학생 이름 · 메일 · 전화번호는 걸렀습니다)."
          % (c["요청"], c["답"], c["규칙변경"], c["오류"], len(p["자료"]), len(p["스킬"])))


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "상태"
    {"상태": cmd_status, "보기": cmd_show, "과목": cmd_subject, "미루기": cmd_defer, "보내기": cmd_send}.get(
        c, lambda: print(__doc__))()
