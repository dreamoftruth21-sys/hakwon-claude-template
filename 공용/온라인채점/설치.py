"""온라인 채점 자동 설치 (clasp). 처음시작 스킬 4단계가 순서대로 부른다.

    py 공용/온라인채점/설치.py 확인          상태만 본다 (로그인한 구글 계정 · 확인한 계정 · 스크립트 · 웹 앱 주소)
    py 공용/온라인채점/설치.py 로그인        clasp 로그인 — 브라우저가 열린다. 선생님이 구글 계정을 골라 로그인 · 허용
    py 공용/온라인채점/설치.py 계정 <메일>    선생님이 "내 계정이 맞다"고 한 메일을 적는다. 로그인한 계정과 같아야 한다
    py 공용/온라인채점/설치.py 로그아웃      다른 계정으로 로그인됐을 때. 그다음 로그인을 다시 한다
    py 공용/온라인채점/설치.py 설정          Apps Script API 설정 화면을 그 계정으로 연다
    py 공용/온라인채점/설치.py 만들기        시트 + 스크립트 생성 → 코드 올리기 → 웹 앱 배포 → 주소 기록
    py 공용/온라인채점/설치.py 편집기        스크립트 편집기를 그 계정으로 연다 — 선생님이 「설치확인」 실행 → 권한 허용
    py 공용/온라인채점/설치.py 재배포        Code.gs · Index.html 을 고친 뒤 같은 주소로 다시 배포
    py 공용/온라인채점/설치.py 처음부터      다른 계정에 만들어졌을 때. 이 컴퓨터의 연결(.clasp.json · 주소 기록)을 지우고 로그아웃한다
                                            (그 계정에 생긴 시트 · 스크립트는 지우지 않는다 — 계정 주인이 지운다)

clasp 는 이 컴퓨터 브라우저에 로그인된 구글 계정 가운데 선생님이 고른 계정으로 만든다.
브라우저에 다른 사람 계정이 로그인돼 있으면 그 계정에 만들어질 수 있다 — 그래서 만들기 전에 계정을 확인받는다.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import webbrowser

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


def login_email():
    """clasp 에 로그인한 구글 계정 메일. 로그인 안 돼 있으면 None."""
    code, out = clasp("show-authorized-user")
    m = re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", out)
    if code != 0 or "not logged" in out.lower() or not m:
        return None
    return m.group(0).lower()


def confirmed():
    return state().get("온라인채점", {}).get("계정")


def need_account():
    """로그인한 계정이 선생님이 확인한 계정과 같아야 다음으로 간다."""
    who = login_email()
    if not who:
        print("clasp 로그인이 먼저다 → 로그인")
        sys.exit(1)
    ok = confirmed()
    if not ok:
        print("로그인한 계정: %s\n선생님께 이 계정이 선생님 구글 계정이 맞는지 확인받은 뒤 → 계정 %s" % (who, who))
        sys.exit(1)
    if ok != who:
        print("로그인한 계정(%s)이 선생님이 확인한 계정(%s)과 다르다. 로그아웃 → 로그인을 다시 한다." % (who, ok))
        sys.exit(1)
    return who


def open_as(url, who):
    url += ("&" if "?" in url else "?") + "authuser=" + who  # 브라우저에 여러 계정이 있어도 이 계정으로 연다
    print("브라우저로 연다:", url)
    webbrowser.open(url)


def write_url(dep):
    url = "https://script.google.com/macros/s/%s/exec" % dep
    t = README.read_text(encoding="utf-8")
    t = re.sub(r"(?m)^- 웹 앱 URL:.*$", "- 웹 앱 URL: " + url, t)
    t = re.sub(r"(?m)^- 배포 ID:.*$", "- 배포 ID: " + dep, t)
    README.write_text(t, encoding="utf-8")
    save_state(웹앱=url, 배포ID=dep)
    return url


def cmd_check():
    who = login_email()
    sid = script_id()
    st = state().get("온라인채점", {})
    print("clasp 로그인 계정:", who or "안 됨 → py 공용/온라인채점/설치.py 로그인")
    print("선생님이 확인한 계정:", st.get("계정") or "아직 → 선생님께 확인받고 계정 <메일>")
    if who and st.get("계정") and who != st.get("계정"):
        print("  ! 두 계정이 다르다 → 로그아웃 → 로그인")
    print("스크립트:", sid or "없음 → py 공용/온라인채점/설치.py 만들기")
    if sid and st.get("만든계정"):
        print("  만든 계정:", st["만든계정"])
    print("웹 앱 주소:", st.get("웹앱") or "없음")
    print("권한 허용(설치확인 실행):", "끝" if st.get("권한") else "아직")


def cmd_login():
    print("브라우저가 열리면 계정 고르기 화면에서 선생님 구글 계정을 고른다(목록에 없으면 「다른 계정 사용」). "
          "그다음 「허용」을 누른다. 끝나면 이 창에 로그인 완료가 뜬다.")
    code, out = clasp("login", timeout=600)
    print(out)
    who = login_email()
    if who:
        print("\n로그인한 계정:", who, "— 선생님 계정이 맞는지 확인받는다 → 계정", who)
    sys.exit(0 if code == 0 and who else 1)


def cmd_account():
    if len(sys.argv) < 3:
        print("쓰는 법: 계정 <메일>")
        sys.exit(1)
    want = sys.argv[2].strip().lower()
    who = login_email()
    if who != want:
        print("로그인한 계정(%s)이 %s 가 아니다. 로그아웃 → 로그인에서 %s 를 고른다." % (who or "없음", want, want))
        sys.exit(1)
    save_state(계정=want)
    print("확인한 계정:", want)


def cmd_logout():
    code, out = clasp("logout")
    print(out.strip() or "로그아웃했다.")
    print("다음: 로그인 (계정 고르기 화면에서 선생님 계정을 고른다)")


def cmd_settings():
    open_as(SETTINGS_URL, need_account())


def cmd_create():
    if script_id():
        print("이미 스크립트가 있다 (.clasp.json). 새로 만들지 않는다. 코드를 다시 올리려면: 재배포")
        sys.exit(1)
    who = need_account()
    tmp = HERE / "_설치임시"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    code, out = clasp('create --type sheets --title "%s" --rootDir .' % TITLE, cwd=tmp)
    print(out)
    if code != 0 or not (tmp / ".clasp.json").exists():
        if "Apps Script API" in out or "usersettings" in out:
            print("\n→ Apps Script API 설정이 꺼져 있다. 설정 → 「Google Apps Script API」를 켠 뒤 다시 만들기")
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(1)
    sid = json.loads((tmp / ".clasp.json").read_text(encoding="utf-8"))["scriptId"]
    shutil.rmtree(tmp, ignore_errors=True)
    (APPS / ".clasp.json").write_text(json.dumps({"scriptId": sid, "rootDir": "."}, indent=1), encoding="utf-8")
    save_state(스크립트ID=sid, 만든계정=who)
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
    print("\n만든 계정:", who)
    print("웹 앱 주소:", url)
    print("다음: py 공용/온라인채점/설치.py 편집기 → 「설치확인」 실행 → 권한 허용")


def cmd_editor():
    sid = script_id()
    if not sid:
        print("스크립트가 없다 → 만들기부터")
        sys.exit(1)
    open_as("https://script.google.com/d/%s/edit" % sid, need_account())
    print("편집기 위쪽 함수 목록에서 「설치확인」을 고르고 「실행」 → 「권한 검토」 → 계정 선택(위와 같은 계정) → "
          "(확인되지 않은 앱 화면이 나오면 「고급」 → 「온라인채점(으)로 이동」) → 「허용」.")


def cmd_redeploy():
    dep = state().get("온라인채점", {}).get("배포ID")
    if not dep:
        print("배포 ID 가 없다 → 만들기부터")
        sys.exit(1)
    need_account()
    code, out = clasp("push --force")
    print(out)
    code, out = clasp('deploy -i %s -d "재배포"' % dep)
    print(out)
    sys.exit(code)


def cmd_reset():
    st = state().get("온라인채점", {})
    sid = script_id()
    print("이 컴퓨터의 온라인 채점 연결을 지운다.")
    if sid or st.get("웹앱"):
        print("  지금 연결된 스크립트: %s (만든 계정 %s)" % (sid or "-", st.get("만든계정") or "모름"))
        print("  그 계정의 구글 드라이브에 「온라인채점」 시트가 남아 있다. 필요 없으면 그 계정 주인이 드라이브에서 지운다.")
    (APPS / ".clasp.json").unlink(missing_ok=True)
    s = state()
    s.pop("온라인채점", None)
    s.pop("4_온라인채점", None)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    t = README.read_text(encoding="utf-8")
    t = re.sub(r"(?m)^- 웹 앱 URL:.*$", "- 웹 앱 URL: (아직 없음 — 처음시작 스킬 4단계 · `py 공용/온라인채점/설치.py 만들기` 가 채운다)", t)
    t = re.sub(r"(?m)^- 배포 ID:.*$", "- 배포 ID: (아직 없음)", t)
    README.write_text(t, encoding="utf-8")
    cmd_logout()


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "확인"
    {"확인": cmd_check, "로그인": cmd_login, "계정": cmd_account, "로그아웃": cmd_logout, "설정": cmd_settings,
     "만들기": cmd_create, "편집기": cmd_editor, "재배포": cmd_redeploy, "처음부터": cmd_reset}.get(
        c, lambda: print(__doc__))()
