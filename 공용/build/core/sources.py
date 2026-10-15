"""원문 불러오기. 경로는 모두 학원 폴더 루트 기준 상대경로로 받는다."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]          # 학원 수업 준비
BYNUM_DIR = ROOT / "공용" / "교재" / "모의고사" / "_데이터"
PROFILE_DIR = ROOT / "공용" / "build" / "학교"


def path(rel):
    p = pathlib.Path(rel)
    return p if p.is_absolute() else ROOT / p


def load_json(rel):
    return json.loads(path(rel).read_text(encoding="utf-8"))


def profile(school):
    p = PROFILE_DIR / (school + ".json")
    if not p.exists():
        raise SystemExit("학교 설정이 없다: %s" % p)
    return json.loads(p.read_text(encoding="utf-8"))


def pdf_text(rel):
    import pymupdf
    with pymupdf.open(path(rel)) as d:
        return " ".join(p.get_text() for p in d)


def bynum(grade, round_, nums):
    """학평 지문 원문. grade '고1'/'고2', round_ '2025-9' 같은 키, nums ['32','34']."""
    f = BYNUM_DIR / ("%s_bynum.json" % grade)
    if not f.exists():
        raise SystemExit("학평 원문 파일이 없다: %s" % f)
    data = json.loads(f.read_text(encoding="utf-8"))
    rd = data.get(round_) or data.get("%s-%s" % (round_, grade))
    if rd is None:
        raise SystemExit("%s 에 회차 '%s' 가 없다 (있는 회차: %s)" % (f.name, round_, ", ".join(data)))
    missing = [n for n in nums if n not in rd]
    if missing:
        raise SystemExit("%s %s 에 없는 번호: %s" % (f.name, round_, missing))
    return {n: rd[n] for n in nums}


def md_text(rel):
    """학교자료/_텍스트 변환본 (없으면 None)."""
    p = path(rel)
    return p.read_text(encoding="utf-8") if p.exists() else None
