"""사용 기록 훅 — Claude Code 가 .claude/settings.json 의 훅으로 부른다. 선생님이 직접 실행할 일은 없다.

표준 입력으로 들어오는 훅 JSON 을 읽어 `공용/사용기록/기록/<연-월>.jsonl` 에 한 줄 적는다.
적는 것 다섯 가지:
  요청     선생님이 입력창에 쓴 말 (UserPromptSubmit)
  답       Claude 가 그 요청에 마지막으로 한 말 (Stop) — 질문과 답을 같이 보려고
  스킬     어느 스킬을 썼는지 (PostToolUse · Skill)
  규칙변경  규칙 파일(CLAUDE.md · SKILL.md · 공용/규칙 · 에이전트)을 Claude 가 고친 것 (PostToolUse · Edit/Write)
  오류     명령이 오류를 낸 것 (PostToolUse · Bash/PowerShell 의 Traceback/Error, PostToolUseFailure)

만든 자료(data.json) · 새로 만들거나 고친 스킬은 여기 적지 않는다 — 보낼 때 보고.py 가 파일을 직접 찾아 붙인다.

이 파일은 이 컴퓨터에만 쌓인다. 밖으로 나가는 것은 `보고.py 보내기` 를 선생님이 승인했을 때뿐이고,
그때 학생 이름 · 메일 · 전화번호를 거른다 (보고.py).

어떤 경우에도 Claude 의 작업을 막지 않는다 — 무슨 일이 나도 조용히 0 으로 끝난다.
"""
import datetime
import json
import pathlib
import re
import sys

MAX_TEXT = 4000         # 요청 한 건에 남기는 글자 수 상한
MAX_ANSWER = 6000       # Claude 답 한 건
MAX_ERROR = 2000        # 오류 출력 한 건
MAX_RULE = 3000         # 규칙 파일 고치기 전 · 후 각각
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


def last_answer(ev):
    """이번 요청에 Claude 가 한 말 — 마지막 사용자 요청 뒤의 assistant 글을 이어 붙인다."""
    text = ev.get("last_assistant_message")
    if isinstance(text, str) and text.strip():
        return text.strip()
    tp = ev.get("transcript_path")
    if not tp:
        return ""
    try:
        with open(tp, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 3_000_000))     # 긴 세션도 끝부분만 읽는다
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    parts = []
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except Exception:
            continue
        msg = e.get("message") or {}
        content = msg.get("content")
        if e.get("type") == "user":
            # 도구 결과가 아니라 선생님이 쓴 말이면 거기서 멈춘다
            if isinstance(content, str) or (isinstance(content, list) and any(
                    isinstance(c, dict) and c.get("type") == "text" for c in content)):
                break
            continue
        if e.get("type") == "assistant" and isinstance(content, list):
            t = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text").strip()
            if t:
                parts.append(t)
    return "\n\n".join(reversed(parts)).strip()


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
        return {"종류": "오류", "반": ban, "도구": tool, "명령": clip((ev.get("tool_input") or {}).get("command"), 500),
                "내용": clip(str(err), MAX_ERROR)}

    if event == "Stop":
        text = last_answer(ev)
        if not text:
            return None
        return {"종류": "답", "반": ban, "내용": clip(text, MAX_ANSWER)}

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
            rec["전"] = clip(inp.get("old_string"), MAX_RULE)
            rec["후"] = clip(inp.get("new_string"), MAX_RULE)
        elif tool == "MultiEdit":
            eds = inp.get("edits") or []
            rec["후"] = clip(" | ".join(str(e.get("new_string", "")) for e in eds), MAX_RULE)
        else:
            rec["후"] = clip(inp.get("content"), MAX_RULE)
        return rec

    if tool in ("Bash", "PowerShell"):
        out = ""
        if isinstance(resp, dict):
            out = (str(resp.get("stderr") or "") + "\n" + str(resp.get("stdout") or "")).strip()
        elif resp is not None:
            out = str(resp)
        if not out or not looks_error(out):
            return None
        return {"종류": "오류", "반": ban, "도구": tool, "명령": clip(inp.get("command"), 500),
                "내용": clip(out[-MAX_ERROR:], MAX_ERROR)}

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
