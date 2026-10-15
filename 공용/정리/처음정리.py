"""처음 설치 때 여기저기 있는 선생님 수업 자료를 백업한 뒤 이 폴더(학원수업)로 모아 반 폴더 구조로 옮긴다.
처음시작 스킬 2단계가 부른다.

    py 공용/정리/처음정리.py 백업 <경로>...          자료가 있는 폴더 · 파일을 통째로 백업 (<이 폴더>_백업_<날짜>/ — 이 폴더 바로 바깥)
    py 공용/정리/처음정리.py 백업확인                설정상태에 적힌 백업마다 파일 수가 원래보다 적지 않은지
    py 공용/정리/처음정리.py 목록 [<경로>...]         이 폴더 + 지정한 위치의 파일 목록과 폴더 요약 (템플릿 파일 · 백업 제외)
    py 공용/정리/처음정리.py 실행 <계획.tsv>          승인한 계획대로 옮긴다 (백업된 곳만 · 덮어쓰지 않는다 · 기록을 남긴다)
    py 공용/정리/처음정리.py 되돌리기 <이동.tsv>       옮긴 것을 원래 자리로

계획.tsv — 한 줄에 「원래 경로<TAB>새 경로」. 원래 경로는 절대 경로 또는 이 폴더 기준 상대 경로, 새 경로는 이 폴더 기준 상대 경로.
원래 경로가 폴더면 폴더째 옮긴다. 「#」으로 시작하는 줄과 빈 줄은 건너뛴다.
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
NOW = datetime.datetime.now()
STAMP = NOW.strftime("%Y%m%d_%H%M")
BK = ROOT.parent / f"{ROOT.name}_백업_{NOW:%Y%m%d}"


def state():
    return json.loads(STATE.read_text(encoding="utf-8-sig")) if STATE.exists() else {}  # PowerShell 로 쓰면 BOM 이 붙는다


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def backups():
    b = state().get("백업", [])
    return [b] if isinstance(b, dict) else b      # 옛 형식(한 개)도 읽는다


def is_backup(p):
    return "_백업_" in p.name


def src_path(a):
    p = pathlib.Path(a)
    return p if p.is_absolute() else ROOT / p


def count(p):
    if p.is_file():
        return 1
    return sum(1 for x in p.rglob("*") if x.is_file()) if p.exists() else 0


def size(p):
    if p.is_file():
        return p.stat().st_size
    return sum(x.stat().st_size for x in p.rglob("*") if x.is_file())


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{u}"
        n /= 1024
    return f"{n:.1f}TB"


def mine():
    """이 폴더 안 선생님 파일 (템플릿 · 백업 · 정리기록 제외)"""
    out = []
    for top in sorted(ROOT.iterdir()):
        if top.name in TEMPLATE or is_backup(top):
            continue
        out += [top] if top.is_file() else [p for p in top.rglob("*") if p.is_file()]
    return out


# ── 백업 ─────────────────────────────────────────────
def cmd_백업(paths):
    items = [pathlib.Path(p).resolve() for p in paths]
    for p in items:
        if not p.exists():
            print("없는 경로:", p)
            sys.exit(1)
        if p == ROOT or ROOT in p.parents:
            print("이 폴더 안 자료는 설치 때 README 절차로 백업한다 (설정상태 「백업」에 이 폴더가 있는지 본다):", p)
            sys.exit(1)
    need = sum(size(p) for p in items)
    free = shutil.disk_usage(ROOT.parent).free
    print(f"백업할 양 {human(need)} · 남은 공간 {human(free)}")
    if need * 1.1 > free:
        print("공간이 모자란다 — USB 같은 다른 저장 장치가 필요하다. 백업하지 않았다.")
        sys.exit(1)
    s = state()
    lst = backups()
    for p in items:
        dst = BK / (p.parent.name or p.drive.rstrip(":\\")) / p.name
        if p.is_dir():
            shutil.copytree(p, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
        n0, n1 = count(p), count(dst)
        ok = n1 >= n0
        print(f"{'✔' if ok else '✘'} {p} → {dst}  ({n0}개 → {n1}개)")
        if not ok:
            print("백업 파일 수가 모자란다 — 멈춘다.")
            sys.exit(1)
        lst = [x for x in lst if x.get("원래") != str(p)]
        lst.append({"원래": str(p), "백업": str(dst), "파일수": n0, "날짜": f"{NOW:%Y-%m-%d %H:%M}"})
    s["백업"] = lst
    save_state(s)
    print(f"백업 끝 — {BK}")


def cmd_백업확인():
    lst = backups()
    if not lst:
        print("백업 기록 없음 — 정리 전에 백업부터 한다 (처음시작 스킬 2-2)")
        sys.exit(1)
    bad = 0
    for b in lst:
        org, bk = pathlib.Path(b.get("원래", "")), pathlib.Path(b.get("백업", b.get("경로", "")))
        n0 = len(mine()) if org.resolve() == ROOT else count(org)   # 이 폴더는 설치 뒤 템플릿 파일이 더해졌다
        n1 = count(bk)
        ok = bk.exists() and n1 >= n0
        bad += not ok
        print(f"{'✔' if ok else '✘'} {org}  지금 {n0}개 · 백업 {n1}개")
    if bad:
        print("백업보다 파일이 많은 곳이 있다 — 그곳을 다시 백업한다.")
        sys.exit(1)
    print("백업 확인 끝")


def covered(p):
    """이 경로가 백업된 곳 안에 있는가"""
    p = p.resolve()
    for b in backups():
        org = pathlib.Path(b.get("원래", "")).resolve()
        if p == org or org in p.parents:
            return True
    return False


# ── 목록 ─────────────────────────────────────────────
def cmd_목록(extra):
    groups = [("이 폴더", ROOT, mine())]
    for e in extra:
        p = pathlib.Path(e).resolve()
        groups.append((str(p), p, [p] if p.is_file() else [x for x in p.rglob("*") if x.is_file()]))
    LOG.mkdir(parents=True, exist_ok=True)
    out = LOG / f"{STAMP}_목록.tsv"
    with out.open("w", encoding="utf-8") as w:
        w.write("경로\t크기\t수정일\t확장자\n")
        for _, _, fs in groups:
            for p in fs:
                st = p.stat()
                w.write(f"{p}\t{st.st_size}\t{datetime.date.fromtimestamp(st.st_mtime)}\t{p.suffix.lower()}\n")
    print("목록:", out.relative_to(ROOT))
    for title, base, fs in groups:
        print(f"\n■ {title} — 파일 {len(fs)}개 · {human(sum(p.stat().st_size for p in fs))}")
        summ = {}
        for p in fs:
            rel = p.relative_to(base).parts[:-1] if base.is_dir() else ()
            for d in range(1, min(len(rel), 3) + 1):
                k = "/".join(rel[:d])
                c, s = summ.get(k, (0, 0))
                summ[k] = (c + 1, s + p.stat().st_size)
        for k in sorted(summ):
            c, s = summ[k]
            print("  " + "  " * k.count("/") + f"{k.split('/')[-1]}/  {c}개 · {human(s)}")
        loose = [p for p in fs if base.is_dir() and p.parent == base]
        if loose:
            print(f"  (폴더 밖 낱개 파일 {len(loose)}개)")
        exts = {}
        for p in fs:
            k = p.suffix.lower() or "(없음)"
            exts[k] = exts.get(k, 0) + 1
        print("  종류:", " · ".join(f"{e} {n}" for e, n in sorted(exts.items(), key=lambda x: -x[1])[:10]))


# ── 옮기기 ───────────────────────────────────────────
def read_plan(tsv):
    rows = []
    for ln in pathlib.Path(tsv).read_text(encoding="utf-8-sig").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        a, b = ln.split("\t")[:2]
        rows.append((a.strip(), b.strip()))
    return rows


def move_rows(rows, log_name, need_backup):
    LOG.mkdir(parents=True, exist_ok=True)
    log = LOG / log_name
    moved = files_in = files_out = 0
    clash, missing, locked, nobk = [], [], [], []
    srcs = set()
    with log.open("w", encoding="utf-8") as w:
        for a, b in rows:
            src, dst = src_path(a), src_path(b)
            if not src.exists():
                missing.append(a)
                continue
            if need_backup and not covered(src):
                nobk.append(a)
                continue
            if dst.exists():
                clash.append(f"{a} → {b}")
                continue
            n = count(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(src), str(dst))
            except OSError as e:
                locked.append(f"{a} ({e.strerror})")
                continue
            w.write(f"{src}\t{dst}\n")
            moved += 1
            files_in += n
            files_out += count(dst)
            srcs.add(src.parent)
    removed = 0
    for d in sorted(srcs, key=lambda p: -len(p.parts)):     # 옮긴 뒤 비어 버린 원래 폴더만 지운다
        # 이 폴더 안이거나 백업된 곳 안쪽만 — 바탕화면 · 다운로드 같은 상위 폴더는 비어도 지우지 않는다
        while d != ROOT and d.exists() and d.is_dir() and not any(d.iterdir()) and (ROOT in d.parents or covered(d)):
            d.rmdir()
            removed += 1
            d = d.parent
    print(f"옮김 {moved}건 (파일 {files_in}개 → 새 자리 {files_out}개)" + ("" if files_in == files_out else "  ← 다르다! 확인할 것"))
    print(f"겹침 {len(clash)} · 없음 {len(missing)} · 잠김 {len(locked)} · 백업 안 된 곳 {len(nobk)} · 빈 폴더 정리 {removed}")
    for t, xs in (("겹침 (새 자리에 이미 있음 — 옮기지 않음)", clash), ("없음", missing),
                  ("잠김 (열려 있는 파일 — 닫고 다시)", locked), ("백업 안 된 곳 (옮기지 않음 — 백업부터)", nobk)):
        if xs:
            print(t + ":")
            print("\n".join("  " + x for x in xs))
    print("기록:", log.relative_to(ROOT))


def cmd_실행(tsv):
    if not backups():
        print("백업 기록이 없다 — 백업 없이 옮기지 않는다.")
        sys.exit(1)
    move_rows(read_plan(tsv), f"{STAMP}_처음정리_이동.tsv", need_backup=True)


def cmd_되돌리기(tsv):
    rows = [(b, a) for a, b in read_plan(tsv)][::-1]
    move_rows(rows, f"{STAMP}_되돌리기_이동.tsv", need_backup=False)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "백업" and len(a) > 1:
        cmd_백업(a[1:])
    elif a[0] == "백업확인":
        cmd_백업확인()
    elif a[0] == "목록":
        cmd_목록(a[1:])
    elif a[0] == "실행" and len(a) > 1:
        cmd_실행(a[1])
    elif a[0] == "되돌리기" and len(a) > 1:
        cmd_되돌리기(a[1])
    else:
        print(__doc__)
