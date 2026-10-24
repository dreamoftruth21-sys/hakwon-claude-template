"""판 지문 — 템플릿 파일마다 내용 지문(sha256 앞 32자)을 만들고, 갱신 때 선생님이 고친 파일을 찾아낸다.

    py 공용/판지문.py 만들기                         이 폴더(템플릿 저장소)의 파일 지문을 공용/판_지문.json 에 쓴다. 판을 낼 때 제작자가 돌린다
    py 공용/판지문.py 대조 <옛판 폴더> <새판 폴더>     갱신 스킬이 돌린다. 지금 폴더(또는 셋째 인수)의 파일을 옛 판 · 새 판과 대조해
                                                    「덮어쓰기 · 유지 · 충돌 · 삭제됨 · 추가」로 나누고, 충돌 파일은 선생님이 더한 줄을 보여 준다
                                                    옛 판 폴더를 모르면 `-` (그때는 새 판과 다른 파일을 모두 충돌로 본다)

대상은 갱신이 덮어쓰는 템플릿 파일만이다. 반 폴더 · 설정상태 · 채점키 · 공용/규칙/우리학원.md 는 보지 않는다.
사람이 읽는 것은 「충돌」 파일의 달라진 줄뿐이다. 지문 대조는 프로그램이 한다.
"""
import difflib
import hashlib
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MANIFEST = "공용/판_지문.json"
TAG_PREFIX = "판-"

# 갱신이 덮어쓰는 템플릿 파일. (포함 패턴, 제외 패턴) — 경로는 템플릿 루트 기준 posix
INCLUDE = [
    r"^\.claude/(skills|agents|prompts)/.+",
    r"^\.claude/settings\.json$",
    r"^공용/build/.+",
    r"^공용/규칙/.+\.md$",
    r"^공용/온라인채점/[^/]+\.py$",
    r"^공용/온라인채점/apps_script/(Code\.gs|Index\.html|appsscript\.json|\.claspignore)$",
    r"^공용/사용기록/([^/]+\.py|수신주소\.txt)$",
    r"^공용/정리/.+",
    r"^공용/판지문\.py$",
    r"^_새반_틀/.+",
    r"^README\.md$",
    r"^CLAUDE\.md$",
]
EXCLUDE = [
    r"(^|/)__pycache__/", r"\.pyc$", r"(^|/)\.gitkeep$",
    r"^공용/build/학교/(?!_예시\.json$).+",       # 선생님 학교 규격
    r"^공용/규칙/우리학원\.md$",                   # 선생님 학원 규칙 — 갱신이 건드리지 않는다
    r"^\.claude/skills/자료정리/(rules\.ps1|무시목록\.txt)$",
    r"(^|/)\.clasp\.json$",
]
INC = [re.compile(p) for p in INCLUDE]
EXC = [re.compile(p) for p in EXCLUDE]


def managed(rel):
    return any(p.search(rel) for p in INC) and not any(p.search(rel) for p in EXC)


def fingerprint(path):
    try:
        data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")   # 줄 끝 차이는 수정으로 보지 않는다
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        return hashlib.sha256(data).hexdigest()[:32]
    except Exception:
        return None


def walk(root):
    out = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(".git/") or not managed(rel):
            continue
        out[rel] = fingerprint(p)
    return out


def find_root(start):
    p = pathlib.Path(start).resolve()
    for d in [p, *p.parents]:
        if (d / "공용" / "VERSION.txt").exists():
            return d
    return None


def version_date(root):
    try:
        first = (root / "공용" / "VERSION.txt").read_text(encoding="utf-8-sig").strip().splitlines()[0]
        m = re.match(r"(\d{4}-\d{2}-\d{2})", first)
        return m.group(1) if m else None
    except Exception:
        return None


# ── 만들기 ────────────────────────────────────────────────────────────
def cmd_make():
    root = find_root(pathlib.Path.cwd())
    if root is None:
        print("템플릿 루트(공용/VERSION.txt 가 있는 폴더)에서 돌린다.")
        sys.exit(1)
    date = version_date(root)
    files = walk(root)
    files.pop(MANIFEST, None)
    m = {"판": date, "태그": TAG_PREFIX + date if date else None, "파일수": len(files), "파일": dict(sorted(files.items()))}
    (root / MANIFEST).write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print("지문 %d개 → %s (판 %s · 태그 %s)" % (len(files), MANIFEST, date, m["태그"]))
    print("판을 낼 때: git add -A · commit · git tag %s · git push --tags" % m["태그"])


# ── 대조 ──────────────────────────────────────────────────────────────
def read_lines(path):
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n").splitlines()
    except Exception:
        return []


def added_lines(old_path, mine_path, limit=60):
    """선생님이 옛 판에서 바꾼 줄만 (unified diff, 앞뒤 1줄)."""
    diff = list(difflib.unified_diff(read_lines(old_path), read_lines(mine_path), "옛 판", "선생님 파일", n=1, lineterm=""))
    body = diff[2:] if len(diff) > 2 else diff
    if len(body) > limit:
        body = body[:limit] + ["… (%d줄 더)" % (len(body) - limit)]
    return "\n".join(body)


def cmd_compare():
    if len(sys.argv) < 4:
        print("쓰는 법: 대조 <옛판 폴더 또는 -> <새판 폴더> [내 폴더]")
        sys.exit(1)
    old = None if sys.argv[2] == "-" else pathlib.Path(sys.argv[2]).resolve()
    new = pathlib.Path(sys.argv[3]).resolve()
    mine = pathlib.Path(sys.argv[4]).resolve() if len(sys.argv) > 4 else find_root(pathlib.Path.cwd())
    if mine is None or not (new / "공용" / "VERSION.txt").exists():
        print("내 폴더(템플릿 루트)와 새 판 폴더를 찾지 못했다.")
        sys.exit(1)
    if old is not None and not (old / "공용" / "VERSION.txt").exists():
        print("옛 판 폴더에 공용/VERSION.txt 가 없다:", old)
        sys.exit(1)

    f_new = walk(new)
    f_old = walk(old) if old is not None else {}
    f_mine = walk(mine)
    f_new.pop(MANIFEST, None); f_old.pop(MANIFEST, None); f_mine.pop(MANIFEST, None)

    res = {"덮어쓰기": [], "같음": [], "새파일": [], "유지": [], "충돌": [], "삭제됨": [], "추가": []}
    for rel in sorted(set(f_new) | set(f_old)):
        h_new, h_old, h_mine = f_new.get(rel), f_old.get(rel), f_mine.get(rel)
        if rel not in f_new:                      # 새 판에서 없어진 파일 — 선생님 것은 두고 보고만
            if h_mine is not None and h_mine != h_old:
                res["유지"].append({"파일": rel, "이유": "새 판에는 없는 파일이고 선생님이 고쳤다"})
            continue
        if h_mine is None:
            res["새파일" if rel not in f_old else "삭제됨"].append(rel)
            continue
        if h_mine == h_new:
            res["같음"].append(rel)
            continue
        if old is not None and h_mine == h_old:      # 선생님이 안 고쳤다
            res["덮어쓰기"].append(rel)
            continue
        # 여기부터 선생님이 고친 파일
        if old is not None and h_new == h_old:       # 템플릿은 그대로 → 선생님 것 유지
            res["유지"].append({"파일": rel, "이유": "선생님이 고쳤고 새 판에서는 바뀌지 않았다"})
            continue
        item = {"파일": rel}
        item["선생님이_바꾼_줄"] = added_lines(old / rel, mine / rel) if old is not None else \
            added_lines(new / rel, mine / rel).replace("옛 판", "새 판")
        res["충돌"].append(item)
    for rel in sorted(set(f_mine) - set(f_new) - set(f_old)):
        res["추가"].append(rel)

    # 사람이 읽는 요약
    print("새 판과 같은 파일 %d · 덮어쓰기 %d · 새 판에 새로 생긴 파일 %d · 유지 %d · 충돌 %d · 삭제됨 %d · 선생님이 추가한 파일 %d"
          % (len(res["같음"]), len(res["덮어쓰기"]), len(res["새파일"]), len(res["유지"]), len(res["충돌"]),
             len(res["삭제됨"]), len(res["추가"])))
    if old is None:
        print("(옛 판 없이 대조 — 새 판과 다른 파일을 모두 충돌로 본다. 선생님이 안 고친 파일도 들어 있을 수 있다)")
    for it in res["유지"]:
        print("유지  %s — %s" % (it["파일"], it["이유"]))
    for it in res["충돌"]:
        print("\n충돌  %s — 선생님이 바꾼 줄:" % it["파일"])
        print(it["선생님이_바꾼_줄"] or "(줄 차이를 못 뽑음 — 파일을 직접 비교)")
    for rel in res["삭제됨"]:
        print("삭제됨  %s — 선생님 폴더에 없다. 새 판 것을 넣는다" % rel)
    for rel in res["추가"]:
        print("추가  %s — 선생님이 만든 파일. 그대로 둔다" % rel)
    print("\n@@JSON@@")
    print(json.dumps({k: v for k, v in res.items() if k != "같음"}, ensure_ascii=False))


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"만들기": cmd_make, "대조": cmd_compare}.get(c, lambda: print(__doc__))()
