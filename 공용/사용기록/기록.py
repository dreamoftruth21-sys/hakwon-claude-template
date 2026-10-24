"""사용 기록 훅 — Claude Code 가 .claude/settings.json 의 훅으로 부른다. 선생님이 직접 실행할 일은 없다.

표준 입력으로 들어오는 훅 JSON 을 읽어 `공용/사용기록/기록/<연-월>.jsonl` 에 한 줄 적는다.
적는 것 네 가지:
  요청     선생님이 입력창에 쓴 말 (UserPromptSubmit)
  스킬     어느 스킬을 썼는지 (PostToolUse · Skill)
  규칙변경  규칙 파일(CLAUDE.md · SKILL.md · 공용/규칙 · 에이전트)을 Claude 가 고친 것 (PostToolUse · Edit/Write)
  오류     명령이 오류를 낸 것 (PostToolUse · Bash 의 Traceback/Error, PostToolUseFailure)

이 파일은 이 컴퓨터에만 쌓인다. 밖으로 나가는 것은 `보고.py 보내기` 를 선생님이 승인했을 때뿐이고,
그때 학생 이름 · 메일 · 전화번호를 거른다 (보고.py).

어떤 경우에도 Claude 의 작업을 막지 않는다 — 무슨 일이 나도 조용히 0 으로 끝난다.
"""
import datetime
import json
import pathlib
import re
import sys

MAX_TEXT = 600          # 한 기록에 남기는 글자 수 상한
RULE_FILES = ("CLAUDE.md", "SKILL.md")
RULE_DIRS = ("공용/규칙", ".claude/agents", ".claude/skills")
ERROR_MARKS = ("Traceback (most recent call last)", "Error:", "error:", "오류", "실패", "FileNotFoundError",
               "ModuleNotFoundError", "PermissionError", "not recognized", "command not found")


def find_root(start):
    """cwd 에서 위로 올라가며 템플릿 루트(공용/VERSION.txt 가 있는 폴더)를 찾는다."""
    p = pathlib.Path(start).resolve()
    for d in [p, *p.parents]:
        if (d / "공용" / "VERSION.txt").exists():
            return d
    return None


def clip(s, n=MAX_TEXT):
    s = str(s or "")
    return s if len(s) <= n else s[:n] + " …(%d자 줄임)" % (len(s) - n)


def rel(root, path):
    try:
        return pathlib.Path(path).resolve().relative_to(root).as_posix()
    except Exception:
        return pathlib.Path(str(path)).name


def is_rule_file(relpath):
    name = relpath.rsplit("/", 1)[-1]
    if name in RULE_FILES:
        return True
    return any(relpath.startswith(d + "/") for d in RULE_DIRS) and relpath.endswith(".md")


def looks_error(text):
    return any(m in text for m in ERROR_MARKS)


def build_record(ev, root):
    event = ev.get("hook_event_name") or ""
    tool = ev.get("tool_name") or ""
    inp = ev.get("tool_input") or {}
    resp = ev.get("tool_response")
    cwd = pathlib.Path(ev.get("cwd") or ".").resolve()
    ban = cwd.name if cwd != root else ""   # 반 폴더에서 열었으면 그 이름, 루트면 빈 칸

    if event == "UserPromptSubmit":
        text = (ev.get("prompt") or "").strip()
        if not text:
            return None
        return {"종류": "요청", "반": ban, "내용": clip(text)}

    if event == "PostToolUseFailure":
        err = ev.get("error") or ev.get("tool_response") or ""
        return {"종류": "오류", "반": ban, "도구": tool, "내용": clip(str(err))}

    if event != "PostToolUse":
        return None

    if tool == "Skill":
        return {"종류": "스킬", "반": ban, "내용": str(inp.get("skill") or inp.get("name") or "")}

    if tool in ("Edit", "Write", "MultiEdit"):
        fp = inp.get("file_path") or ""
        r = rel(root, fp)
        if not is_rule_file(r):
            return None
        rec = {"종류": "규칙변경", "반": ban, "파일": r, "도구": tool}
        if tool == "Edit":
            rec["전"] = clip(inp.get("old_string"), 400)
            rec["후"] = clip(inp.get("new_string"), 400)
        elif tool == "MultiEdit":
            eds = inp.get("edits") or []
            rec["후"] = clip(" | ".join(str(e.get("new_string", "")) for e in eds), 400)
        else:
            rec["후"] = clip(inp.get("content"), 400)
        return rec

    if tool == "Bash":
        out = ""
        if isinstance(resp, dict):
            out = (str(resp.get("stderr") or "") + "\n" + str(resp.get("stdout") or "")).strip()
        elif resp is not None:
            out = str(resp)
        if not out or not looks_error(out):
            return None
        return {"종류": "오류", "반": ban, "도구": "Bash", "명령": clip(inp.get("command"), 200),
                "내용": clip(out[-MAX_TEXT:])}

    return None


def main():
    try:
        data = sys.stdin.buffer.read()
        try:
            raw = data.decode("utf-8")
        except UnicodeDecodeError:
            raw = data.decode("cp949", errors="replace")   # PowerShell 파이프를 거쳐 다시 인코딩된 경우
        ev = json.loads(raw) if raw.strip() else {}
        root = find_root(ev.get("cwd") or pathlib.Path.cwd())
        if root is None:
            return
        rec = build_record(ev, root)
        if rec is None:
            return
        now = datetime.datetime.now()
        rec = {"시각": now.strftime("%Y-%m-%d %H:%M:%S"), "세션": (ev.get("session_id") or "")[:8], **rec}
        d = root / "공용" / "사용기록" / "기록"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / (now.strftime("%Y-%m") + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
