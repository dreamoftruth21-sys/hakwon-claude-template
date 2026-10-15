"""온라인 채점 자동 설치 (clasp). 처음시작 스킬 4단계가 순서대로 부른다.

    py 공용/온라인채점/설치.py 확인        상태만 본다 (로그인 · 스크립트 · 웹 앱 주소)
    py 공용/온라인채점/설치.py 로그인      clasp 로그인 — 브라우저가 열린다. 선생님이 구글 로그인 · 허용
    py 공용/온라인채점/설치.py 만들기      시트 + 스크립트 생성 → 코드 올리기 → 웹 앱 배포 → 주소 기록
    py 공용/온라인채점/설치.py 편집기      스크립트 편집기 열기 — 선생님이 「설치확인」 실행 → 권한 허용
    py 공용/온라인채점/설치.py 재배포      Code.gs · Index.html 을 고친 뒤 같은 주소로 다시 배포

만들기 전에 선생님 계정의 Apps Script API 설정이 켜져 있어야 한다:
    https://script.google.com/home/usersettings  →  「Google Apps Script API」 사용
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APPS = HERE / "apps_script"
README = HERE / "README.md"
STATE = ROOT / "공용" / "설정상태.json"
TITLE = "온라인채점"
SETTINGS_URL = "https://script.google.com/home/usersettings"


def clasp(args, cwd=None, timeout=600):
    r = subprocess.run("clasp " + args, shell=True, cwd=str(cwd or APPS), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8-sig"))  # BOM 이 붙어 있어도 읽는다 (못 읽으면 백업 기록까지 덮어쓴다)
    except Exception:
        return {}


def save_state(**kw):
    s = state()
    s.setdefault("온라인채점", {}).update(kw)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def script_id():
    f = APPS / ".clasp.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8")).get("scriptId")


def logged_in():
    code, out = clasp("show-authorized-user")
    return code == 0 and "not logged" not in out.lower() and "@" in out, out.strip()


def write_url(dep):
    url = "https://script.google.com/macros/s/%s/exec" % dep
    t = README.read_text(encoding="utf-8")
    t = re.sub(r"(?m)^- 웹 앱 URL:.*$", "- 웹 앱 URL: " + url, t)
    t = re.sub(r"(?m)^- 배포 ID:.*$", "- 배포 ID: " + dep, t)
    README.write_text(t, encoding="utf-8")
    save_state(웹앱=url, 배포ID=dep)
    return url


def cmd_check():
    ok, who = logged_in()
    sid = script_id()
    st = state().get("온라인채점", {})
    print("clasp 로그인:", "됨 · " + who.splitlines()[0] if ok else "안 됨 → py 공용/온라인채점/설치.py 로그인")
    print("스크립트:", sid or "없음 → py 공용/온라인채점/설치.py 만들기")
    print("웹 앱 주소:", st.get("웹앱") or "없음")
    print("권한 허용(설치확인 실행):", "끝" if st.get("권한") else "아직")


def cmd_login():
    print("브라우저가 열리면 구글 계정으로 로그인하고 「허용」을 누른다. 끝나면 이 창에 로그인 완료가 뜬다.")
    code, out = clasp("login", timeout=600)
    print(out)
    sys.exit(0 if code == 0 else 1)


def cmd_create():
    if script_id():
        print("이미 스크립트가 있다 (.clasp.json). 새로 만들지 않는다. 코드를 다시 올리려면: 재배포")
        sys.exit(1)
    ok, _ = logged_in()
    if not ok:
        print("clasp 로그인이 먼저다 → 로그인")
        sys.exit(1)
    tmp = HERE / "_설치임시"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    code, out = clasp('create --type sheets --title "%s" --rootDir .' % TITLE, cwd=tmp)
    print(out)
    if code != 0 or not (tmp / ".clasp.json").exists():
        if "Apps Script API" in out or "usersettings" in out:
            print("\n→ Apps Script API 설정이 꺼져 있다. 이 주소에서 「Google Apps Script API」를 켠 뒤 다시 만들기:\n  " + SETTINGS_URL)
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(1)
    sid = json.loads((tmp / ".clasp.json").read_text(encoding="utf-8"))["scriptId"]
    shutil.rmtree(tmp, ignore_errors=True)
    (APPS / ".clasp.json").write_text(json.dumps({"scriptId": sid, "rootDir": "."}, indent=1), encoding="utf-8")
    save_state(스크립트ID=sid)
    code, out = clasp("push --force")
    print(out)
    if code != 0:
        sys.exit(1)
    code, out = clasp('deploy -d "첫 배포"')
    print(out)
    m = re.search(r"(AKfy[\w-]+)", out)
    if code != 0 or not m:
        print("배포 ID 를 찾지 못했다. 위 출력을 확인한다.")
        sys.exit(1)
    url = write_url(m.group(1))
    print("\n웹 앱 주소:", url)
    print("다음: py 공용/온라인채점/설치.py 편집기 → 「설치확인」 실행 → 권한 허용")


def cmd_editor():
    code, out = clasp("open-script")
    print(out)
    print("편집기 위쪽 함수 목록에서 「설치확인」을 고르고 「실행」 → 「권한 검토」 → 계정 선택 → "
          "(확인되지 않은 앱 화면이 나오면 「고급」 → 「온라인채점(으)로 이동」) → 「허용」.")


def cmd_redeploy():
    dep = state().get("온라인채점", {}).get("배포ID")
    if not dep:
        print("배포 ID 가 없다 → 만들기부터")
        sys.exit(1)
    code, out = clasp("push --force")
    print(out)
    code, out = clasp('deploy -i %s -d "재배포"' % dep)
    print(out)
    sys.exit(code)


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "확인"
    {"확인": cmd_check, "로그인": cmd_login, "만들기": cmd_create, "편집기": cmd_editor, "재배포": cmd_redeploy}.get(
        c, lambda: print(__doc__))()
