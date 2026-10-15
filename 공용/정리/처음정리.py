"""처음 설치 때 선생님 기존 수업 폴더를 반 폴더 구조로 옮긴다. 처음시작 스킬 2단계가 부른다.

    py 공용/정리/처음정리.py 목록                 지금 있는 파일 목록 + 폴더 요약 (템플릿 파일 · 백업 제외)
    py 공용/정리/처음정리.py 백업확인              설정상태의 백업 폴더 파일 수가 지금 목록과 같은지
    py 공용/정리/처음정리.py 실행 <계획.tsv>        승인한 계획대로 옮긴다 (덮어쓰지 않는다 · 기록을 남긴다)
    py 공용/정리/처음정리.py 되돌리기 <이동.tsv>     옮긴 것을 원래 자리로

계획.tsv — 한 줄에 「원래 경로<TAB>새 경로」 (폴더 기준 상대 경로). 원래 경로가 폴더면 폴더째 옮긴다.
「#」으로 시작하는 줄과 빈 줄은 건너뛴다.
기록은 _정리대기/정리기록/ 에 남는다. 파일을 지우지 않는다 (옮긴 뒤 비어 버린 폴더만 지운다).
"""
import datetime
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOG = ROOT / "_정리대기" / "정리기록"
STATE = ROOT / "공용" / "설정상태.json"
TEMPLATE = {".claude", "공용", "_새반_틀", "CLAUDE.md", "README.md", ".gitignore", "_정리대기", ".git"}
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M")


def state():
    return json.loads(STATE.read_text(encoding="utf-8-sig")) if STATE.exists() else {}  # PowerShell 로 쓰면 BOM 이 붙는다


def is_backup(p):
    return "_백업_" in p.name


def files():
    out = []
    for top in sorted(ROOT.iterdir()):
        if top.name in TEMPLATE or is_backup(top):
            continue
        if top.is_file():
            out.append(top)
        else:
            out += [p for p in top.rglob("*") if p.is_file()]
    return out


def total():
    """옮기기 전후 비교용 — 백업 · 기록 · .git 만 빼고 폴더 전체 파일 수"""
    return sum(1 for p in ROOT.rglob("*")
               if p.is_file() and ".git" not in p.parts and LOG not in p.parents
               and not is_backup(ROOT / p.relative_to(ROOT).parts[0]))


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{u}"
        n /= 1024
    return f"{n:.1f}TB"


def cmd_목록():
    fs = files()
    LOG.mkdir(parents=True, exist_ok=True)
    out = LOG / f"{STAMP}_목록.tsv"
    with out.open("w", encoding="utf-8") as w:
        w.write("경로\t크기\t수정일\t확장자\n")
        for p in fs:
            st = p.stat()
            w.write(f"{p.relative_to(ROOT)}\t{st.st_size}\t{datetime.date.fromtimestamp(st.st_mtime)}\t{p.suffix.lower()}\n")
    # 폴더 요약 — 3단계 깊이까지 파일 수 · 크기
    summ = {}
    for p in fs:
        rel = p.relative_to(ROOT).parts[:-1]
        for d in range(1, min(len(rel), 3) + 1):
            k = "/".join(rel[:d])
            c, s = summ.get(k, (0, 0))
            summ[k] = (c + 1, s + p.stat().st_size)
    loose = [p for p in fs if p.parent == ROOT]
    print(f"파일 {len(fs)}개 · {human(sum(p.stat().st_size for p in fs))}  (목록: {out.relative_to(ROOT)})")
    for k in sorted(summ):
        depth = k.count("/")
        c, s = summ[k]
        print("  " * depth + f"{k.split('/')[-1]}/  {c}개 · {human(s)}")
    if loose:
        print(f"폴더 밖 낱개 파일 {len(loose)}개")
    exts = {}
    for p in fs:
        exts[p.suffix.lower() or "(없음)"] = exts.get(p.suffix.lower() or "(없음)", 0) + 1
    print("종류:", " · ".join(f"{e} {n}" for e, n in sorted(exts.items(), key=lambda x: -x[1])))


def cmd_백업확인():
    b = state().get("백업", {})
    path = pathlib.Path(b.get("경로", ""))
    if not b or not path.exists():
        print("백업 없음 — 정리 전에 백업부터 한다 (처음시작 스킬 2-1)")
        sys.exit(1)
    nb = sum(1 for p in path.rglob("*") if p.is_file())
    nn = len([p for p in files() if p.relative_to(ROOT).parts[0] != "_가져온자료"])  # 복사해 온 것은 원본이 제자리에 있다
    print(f"백업 {path} · 파일 {nb}개 / 지금 {nn}개")
    if nb < nn:
        print("백업보다 지금 파일이 많다 — 백업 뒤에 새로 생긴 파일이 있다. 다시 백업하거나 선생님께 알린다.")
        sys.exit(1)
    print("백업 확인 끝")


def read_plan(tsv):
    rows = []
    for ln in pathlib.Path(tsv).read_text(encoding="utf-8-sig").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        a, b = ln.split("\t")[:2]
        rows.append((a.strip(), b.strip()))
    return rows


def move_rows(rows, log_name):
    LOG.mkdir(parents=True, exist_ok=True)
    log = LOG / log_name
    before = total()
    moved, clash, missing, locked = 0, [], [], []
    srcs = set()
    with log.open("w", encoding="utf-8") as w:
        for a, b in rows:
            src, dst = ROOT / a, ROOT / b
            if not src.exists():
                missing.append(a)
                continue
            if dst.exists():
                clash.append(f"{a} → {b}")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(src), str(dst))
            except OSError as e:
                locked.append(f"{a} ({e.strerror})")
                continue
            w.write(f"{a}\t{b}\n")
            moved += 1
            srcs.add(src.parent)
    # 옮긴 뒤 비어 버린 원래 폴더만 지운다 (위로 올라가며)
    removed = 0
    for d in sorted(srcs, key=lambda p: -len(p.parts)):
        while d != ROOT and d.exists() and not any(d.iterdir()):
            d.rmdir()
            removed += 1
            d = d.parent
    after = total()
    print(f"옮김 {moved} · 겹침 {len(clash)} · 없음 {len(missing)} · 잠김 {len(locked)} · 빈 폴더 정리 {removed}")
    print(f"파일 수 {before} → {after}" + ("" if before == after else "  ← 다르다! 확인할 것"))
    for t, xs in (("겹침 (새 자리에 이미 있음 — 옮기지 않음)", clash), ("없음", missing), ("잠김 (열려 있는 파일 — 닫고 다시)", locked)):
        if xs:
            print(t + ":")
            print("\n".join("  " + x for x in xs))
    print("기록:", log.relative_to(ROOT))


def cmd_실행(tsv):
    if "백업" not in state():
        print("설정상태에 백업 기록이 없다 — 백업 없이 옮기지 않는다.")
        sys.exit(1)
    move_rows(read_plan(tsv), f"{STAMP}_처음정리_이동.tsv")


def cmd_되돌리기(tsv):
    rows = [(b, a) for a, b in read_plan(tsv)][::-1]
    move_rows(rows, f"{STAMP}_되돌리기_이동.tsv")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "목록":
        cmd_목록()
    elif a[0] == "백업확인":
        cmd_백업확인()
    elif a[0] == "실행" and len(a) > 1:
        cmd_실행(a[1])
    elif a[0] == "되돌리기" and len(a) > 1:
        cmd_되돌리기(a[1])
    else:
        print(__doc__)
