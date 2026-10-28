"""다운로드 · 카카오톡 받은 파일 폴더 접근 허용 — 처음시작 2-1 에서 선생님이 「허용」이라고 답했을 때만 돌린다.

    py 공용/설치/폴더허용.py 확인              두 폴더의 실제 위치를 찾아 보여 준다 (아무것도 쓰지 않는다)
    py 공용/설치/폴더허용.py 허용 ["<경로>" …]  찾은 두 폴더(+ 준 경로)를 이 PC 의 Claude 사용자 설정
                                              (%USERPROFILE%\\.claude\\settings.json 의 permissions.additionalDirectories)에 더한다.
                                              어느 세션(학원 공통 · 반 세션)에서든 그 폴더를 묻지 않고 읽는다
    py 공용/설치/폴더허용.py 안함              「안 함」을 기록만 한다 (그 폴더가 필요할 때 Claude 앱이 그때 허용 창을 띄운다)

답은 공용/설정상태.json 의 "폴더허용"(true/false)에 적는다 — 적혀 있으면 처음시작이 다시 묻지 않는다.
폴더를 열 수 있어도 자료정리 스킬 규칙(개인 파일은 열지 않는다)은 그대로다.
"""
import ctypes
import json
import pathlib
import sys
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[2]
STATE = ROOT / "공용" / "설정상태.json"
USER_SETTINGS = pathlib.Path.home() / ".claude" / "settings.json"
FOLDERID = {"Downloads": "374DE290-123F-4565-9164-39C4925E467B", "Documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7"}


def known_folder(name):
    """윈도우가 아는 실제 위치 (OneDrive 로 옮긴 문서 폴더도 맞게 나온다)."""
    try:
        class GUID(ctypes.Structure):
            _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort), ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]
        u = uuid.UUID(FOLDERID[name])
        g = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:]))
        p = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p)) == 0:
            out = p.value
            ctypes.windll.ole32.CoTaskMemFree(p)
            return pathlib.Path(out)
    except Exception:
        pass
    return pathlib.Path.home() / name


def find():
    down = known_folder("Downloads")
    docs = known_folder("Documents")
    kakao = None
    for c in [docs / "카카오톡 받은 파일", pathlib.Path.home() / "Documents" / "카카오톡 받은 파일",
              pathlib.Path.home() / "OneDrive" / "문서" / "카카오톡 받은 파일"]:
        if c.is_dir():
            kakao = c
            break
    return down, kakao


def save_state(value):
    s = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    s["폴더허용"] = value
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_check():
    down, kakao = find()
    print("다운로드:", down if down.is_dir() else f"{down} (없음)")
    print("카카오톡 받은 파일:", kakao or "못 찾음 — 선생님께 위치를 묻는다")


def cmd_allow():
    down, kakao = find()
    paths = [p for p in [down, kakao] if p and p.is_dir()]
    paths += [pathlib.Path(a) for a in sys.argv[2:] if pathlib.Path(a).is_dir()]
    if not paths:
        print("허용할 폴더를 찾지 못했다 — 선생님께 위치를 묻고 `허용 \"<경로>\"`")
        sys.exit(1)
    try:
        cfg = json.loads(USER_SETTINGS.read_text(encoding="utf-8-sig")) if USER_SETTINGS.exists() else {}
    except Exception as e:
        print("Claude 사용자 설정 파일을 읽지 못해 아무것도 바꾸지 않았다:", USER_SETTINGS, e)
        sys.exit(1)
    dirs = cfg.setdefault("permissions", {}).setdefault("additionalDirectories", [])
    added = []
    for p in paths:
        s = str(p)
        if s not in dirs:
            dirs.append(s)
            added.append(s)
    USER_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    USER_SETTINGS.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    save_state(True)
    print("허용한 폴더:", ", ".join(str(p) for p in paths), "· 새로 적음", len(added))
    if not kakao and not sys.argv[2:]:
        print("카카오톡 받은 파일 폴더는 못 찾았다 — 위치를 묻고 `허용 \"<경로>\"` 로 더한다")


def cmd_no():
    save_state(False)
    print("폴더 허용 안 함 — 기록했다. 그 폴더가 필요할 때 Claude 앱이 허용 창을 띄운다")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"확인": cmd_check, "허용": cmd_allow, "안함": cmd_no}.get(c, lambda: print(__doc__))()
