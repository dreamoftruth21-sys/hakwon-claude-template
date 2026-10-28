"""학원 로고 — `공용/로고/` 의 두 파일을 시험지 · 피드백 문서에 넣는다.

    워터마크.png   쪽마다 가운데에 옅게 (position:fixed — 크로미움 인쇄에서 모든 쪽에 되풀이된다)
    머리로고.png   첫 쪽 오른쪽 위

파일이 없으면 빈 글자를 돌려준다 — 로고 없이 예전처럼 만든다.
쓰는 빌더: 모의고사(실전 모의고사 · 약점 확인 시험) · 피드백(학생용 · 부모용).

name(data.json 경로) — 학원 표기. 반 CLAUDE.md 를 먼저, 없으면 우리학원.md. 모의고사 바닥글 · 단어장 이름 칸이 쓴다.
"""
import base64
import pathlib
import re
import sys

LOGO_DIR = pathlib.Path(__file__).resolve().parents[2] / "로고"
WATERMARK = LOGO_DIR / "워터마크.png"
HEADER = LOGO_DIR / "머리로고.png"

WM_WIDTH = "115mm"       # 워터마크 지름
WM_OPACITY = 0.10        # 글자를 가리지 않을 만큼 (10/28 Danny: 7% 에서 살짝 진하게)


def _uri(path):
    try:
        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    except Exception:
        return ""


def watermark(front=False):
    """<body> 바로 뒤에 넣는다.
    front=False — 글 뒤에 깐다. 바탕이 투명한 시험지용
    front=True  — 표 · 상자 위에 겹친다(곱하기 섞기라 글자는 그대로 읽힌다). 표와 상자에 바탕색이 있는 피드백 문서용"""
    u = _uri(WATERMARK)
    if not u:
        return ""
    layer = "z-index:9999;mix-blend-mode:multiply" if front else "z-index:-1"
    return ('<img class="brand-wm" alt="" src="%s" style="position:fixed;left:50%%;top:50%%;width:%s;'
            'transform:translate(-50%%,-50%%);opacity:%s;%s;pointer-events:none">' % (u, WM_WIDTH, WM_OPACITY, layer))


def header_logo(height="9mm", style=""):
    """머리 로고 <img>. 흰 바탕은 mix-blend-mode 로 비친다."""
    u = _uri(HEADER)
    if not u:
        return ""
    return '<img class="brand-logo" alt="" src="%s" style="height:%s;mix-blend-mode:multiply;%s">' % (u, height, style)


def enabled():
    return WATERMARK.exists() or HEADER.exists()


# ── 학원 표기 (예: 나성카이젠) ── 여러 캠퍼스를 다니는 선생님은 반마다 다르다 (2026-10-29)
ROOT = LOGO_DIR.parents[1]                       # 템플릿 루트 (공용/ 의 위)
OUR = ROOT / "공용" / "규칙" / "우리학원.md"
_CLASS_LINE = re.compile(r"^캠퍼스:.*?학원 표기:\s*(.+?)\s*$", re.M)        # 반 CLAUDE.md 머리
_OUR_LINE = re.compile(r"^- 학원 표기:\s*(.+?)\s*$", re.M)                   # 우리학원.md 「학원 정보」


def _value(m):
    v = m.group(1) if m else ""
    return "" if not v or v[0] in "([" or "반마다" in v else v


def name(data_path):
    """data.json 이 든 반 폴더의 CLAUDE.md `학원 표기:` → 없으면 공용/규칙/우리학원.md → 없으면 빈 글자."""
    d = pathlib.Path(data_path).resolve().parent
    while d != ROOT and ROOT in d.parents:
        f = d / "CLAUDE.md"
        if f.exists():
            v = _value(_CLASS_LINE.search(f.read_text(encoding="utf-8")))
            if v:
                return v
        d = d.parent
    v = _value(_OUR_LINE.search(OUR.read_text(encoding="utf-8"))) if OUR.exists() else ""
    if not v:
        print("학원 표기를 찾지 못했다 — 반 CLAUDE.md 「캠퍼스 · 학원 표기」나 공용/규칙/우리학원.md 를 채운다", file=sys.stderr)
    return v
