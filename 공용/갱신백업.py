"""갱신 백업 — 갱신이 선생님 폴더에 쓰기 직전에 쓸 파일을 통째로 복사해 두고, 「갱신 되돌려 줘」로 원래대로 돌린다.

    py 공용/갱신백업.py 백업 <목록파일> [--root <선생님 폴더>] [--판 <지금 판>]
        목록파일: 한 줄에 하나, 선생님 폴더 기준 상대 경로(posix). 갱신이 덮어쓰거나 새로 만들 파일 전부.
        있는 파일은 백업 폴더로 복사하고, 없는 파일은 「새로 생길 파일」로 적어 둔다(되돌릴 때 지운다).
        백업 폴더: 선생님 폴더 바로 바깥 `<폴더 이름>_갱신백업_<YYYYMMDD_HHMM>/` · 그 안 목록.json
    py 공용/갱신백업.py 되돌리기 [<백업 폴더>] [--root <선생님 폴더>]
        백업 폴더를 안 주면 가장 최근 것. 있던 파일은 백업 것으로 되돌리고, 새로 생긴 파일은 지운다.
    py 공용/갱신백업.py 목록 [--root <선생님 폴더>]
        백업 폴더들과 판 · 파일 수를 보여 준다.

반 폴더 데이터 · 우리학원.md 처럼 갱신이 건드리지 않는 파일은 목록에 넣지 않는다 — 되돌리기도 그 파일들을 건드리지 않는다.
"""
import datetime
import json
import pathlib
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def find_root(start):
    p = pathlib.Path(start).resolve()
    for d in [p, *p.parents]:
        if (d / "공용" / "VERSION.txt").exists():
            return d
    return None


def root_dir():
    r = arg("--root")
    root = pathlib.Path(r).resolve() if r else find_root(pathlib.Path.cwd())
    if root is None or not root.exists():
        print("선생님 폴더(공용/VERSION.txt 가 있는 폴더)를 찾지 못했다. --root 로 준다.")
        sys.exit(1)
    return root


def backups(root):
    return sorted(root.parent.glob(root.name + "_갱신백업_*"), key=lambda p: p.name)


def cmd_backup():
    root = root_dir()
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    rels = [l.strip().replace("\\", "/") for l in pathlib.Path(sys.argv[2]).read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    rels = sorted(set(r for r in rels if not r.startswith("../") and ".." not in r.split("/")))
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    dst = root.parent / f"{root.name}_갱신백업_{stamp}"
    n = 1
    while dst.exists():
        n += 1
        dst = root.parent / f"{root.name}_갱신백업_{stamp}_{n}"
    had, new = [], []
    for r in rels:
        src = root / r
        if src.is_file():
            to = dst / "파일" / r
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, to)
            had.append(r)
        else:
            new.append(r)
    dst.mkdir(parents=True, exist_ok=True)
    info = {"만든 시각": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "선생님 폴더": str(root),
            "갱신 전 판": arg("--판", ""), "있던 파일": had, "새로 생길 파일": new}
    (dst / "목록.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    # 복사가 맞는지 — 파일 수와 크기
    bad = [r for r in had if (dst / "파일" / r).stat().st_size != (root / r).stat().st_size]
    if bad:
        print("백업이 원본과 크기가 다르다 — 갱신을 멈춘다:", bad[:5])
        sys.exit(1)
    print("백업 %s — 있던 파일 %d개 복사 · 새로 생길 파일 %d개 기록" % (dst, len(had), len(new)))


def cmd_restore():
    root = root_dir()
    given = [a for a in sys.argv[2:] if not a.startswith("--") and sys.argv[sys.argv.index(a) - 1] != "--root"]
    if given:
        bk = pathlib.Path(given[0]).resolve()
    else:
        found = backups(root)
        if not found:
            print("갱신 백업이 없다.")
            sys.exit(1)
        bk = found[-1]
    info = json.loads((bk / "목록.json").read_text(encoding="utf-8"))
    back, removed = 0, 0
    for r in info["있던 파일"]:
        src = bk / "파일" / r
        to = root / r
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, to)
        back += 1
    for r in info["새로 생길 파일"]:
        p = root / r
        if p.is_file():
            p.unlink()
            removed += 1
            for d in p.parents:                      # 갱신이 만든 빈 폴더도 치운다
                if d == root or any(d.iterdir()):
                    break
                d.rmdir()
    print("되돌림 %s — 파일 %d개를 갱신 전으로 · 갱신이 새로 만든 파일 %d개 지움 (갱신 전 판: %s)"
          % (bk.name, back, removed, info.get("갱신 전 판") or "?"))


def cmd_list():
    root = root_dir()
    found = backups(root)
    if not found:
        print("갱신 백업이 없다.")
        return
    for b in found:
        try:
            info = json.loads((b / "목록.json").read_text(encoding="utf-8"))
            print("%s · 갱신 전 판 %s · 있던 파일 %d · 새 파일 %d" % (b.name, info.get("갱신 전 판") or "?",
                                                            len(info["있던 파일"]), len(info["새로 생길 파일"])))
        except Exception:
            print(b.name, "(목록.json 을 읽지 못함)")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"백업": cmd_backup, "되돌리기": cmd_restore, "목록": cmd_list}.get(c, lambda: print(__doc__))()
