# -*- coding: utf-8 -*-
"""쉬운말 번역 문서 빌더 — 「영문 지문 분석 및 번역 모음」 docx

  py build.py <회차폴더>                       JSON → docx (+ 미리보기 PDF)
  py build.py <회차폴더> --import <기존.docx>  기존 docx를 JSON으로 되살린 뒤 빌드

회차폴더 = 공용/교재/모의고사/<연도_학년_월>
데이터   = <회차폴더>/작업/쉬운말번역.json
결과     = <회차폴더>/Translation_and_Analysis.docx (+ .pdf)

검증에 걸리면 SystemExit — 문서가 만들어지지 않는다.
"""
import json, re, sys, shutil, subprocess, unicodedata
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn

TITLE = '영문 지문 분석 및 번역 모음'
KO_FONT = '맑은 고딕'
STYLES = ('Normal', 'Title', 'Heading 1', 'Heading 2', 'List Bullet')
H = ['1. 이 글의 제목', '2. 이 글의 주장, 전개, 결론', '3. 이 글의 한 줄 요약', '4. 쉬운 말 번역']
LABELS = [('주장', 'claim'), ('전개', 'develop'), ('결론', 'conclude')]
SOFFICE = r'C:\Program Files\LibreOffice\program\soffice.com'


# ── 원문 정규화: 문항 기호·밑줄 번호·주석·줄바꿈 하이픈을 걷어 낸다
def norm(s):
    s = unicodedata.normalize('NFKC', s).replace('\u00ad', '')
    s = re.sub(r'[①②③④⑤⑥⑦⑧⑨ⓐⓑⓒⓓⓔⓕⓖⓗⓘ]', '', s)
    s = re.sub(r'\((?:A|B|C|D)\)', '', s)
    s = s.replace('―', '-').replace('—', '-').replace('–', '-')
    s = re.sub(r'[‘’´`]', "'", s); s = re.sub(r'[“”]', '"', s)
    s = re.sub(r'_+', '', s)
    s = re.sub(r'\s+', '', s)
    return s.lower()


def sort_key(p):
    """모의고사는 번호(24번)의 숫자로 정렬한다.
    내신 지문처럼 번호에 숫자 체계가 섞이면(9강 1번 · Theme 01-1 · Unit 47) 지문에 order 를 준다."""
    if 'order' in p:
        return int(p['order'])
    return int(re.sub(r'\D', '', str(p.get('no'))) or 0)


def check(data):
    errs = []
    seen = set()
    nos = [p.get('no') for p in data['passages']]
    keys = [sort_key(p) for p in data['passages']]
    if keys != sorted(keys):
        errs.append(f'문항 번호가 오름차순이 아니다: {nos}')
    for p in data['passages']:
        no = p.get('no')
        tag = f'[{no}번]'
        if no in seen: errs.append(f'{tag} 번호 중복')
        seen.add(no)
        for k in ('title_ko', 'title_en', 'claim', 'develop', 'conclude', 'summary'):
            if not str(p.get(k, '')).strip(): errs.append(f'{tag} {k} 비어 있음')
        sents = p.get('sentences') or []
        if not sents: errs.append(f'{tag} 쉬운 말 번역 문장이 없다')
        for i, s in enumerate(sents, 1):
            if not s.get('easy', '').strip(): errs.append(f'{tag} {i:02d}번 쉬운 말 번역 비어 있음')
            if not s.get('en', '').strip(): errs.append(f'{tag} {i:02d}번 원문 문장 비어 있음')
        # 원문 대조 — 문장들을 이으면 지문 원문과 같아야 한다 (문장 누락·병합 방지)
        src = p.get('source', '')
        if src.strip():
            joined = norm(' '.join(s.get('en', '') for s in sents))
            if joined != norm(src):
                a, b = joined, norm(src)
                k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
                errs.append(f'{tag} 원문 대조 불일치 — {k}번째 글자부터 다르다: 문장="{a[k:k+40]}" / 원문="{b[k:k+40]}"')
        else:
            errs.append(f'{tag} source(지문 원문)가 없다 — 원문 대조를 못 한다')
        # 표현 규칙
        text = ' '.join([str(p.get(k, '')) for k in ('title_ko', 'claim', 'develop', 'conclude', 'summary')] + [s.get('easy', '') for s in sents])
        for m in re.finditer(r'.{0,6}자리.{0,6}', text):
            if not re.search(r'(부사|형용사|명사|동사|원급|주어|목적어|보어) ?자리|잠자리|일자리|돗자리|술자리', m.group(0)):
                errs.append(f'{tag} "자리" 표현: …{m.group(0)}…')
        for bad in ('하세요', '판서', '채점하면', '학생이 '):
            if bad in text: errs.append(f'{tag} 강사용 멘트 "{bad}"')
    return errs


def set_korean_font(doc):
    """python-docx 기본 서식은 한글 글꼴이 비어 있다(eastAsiaTheme 만 걸려 있음).
    그대로 LibreOffice 로 PDF 를 만들면 한글이 PC에 깔린 아무 글꼴(KERISKEDU B 같은 굵은 글꼴)로 대체된다.
    스타일마다 한글 글꼴을 직접 지정하고, 직접 지정보다 우선하는 eastAsiaTheme 속성은 지운다."""
    for name in STYLES:
        rpr = doc.styles[name].element.get_or_add_rPr()
        rfonts = rpr.find(qn('w:rFonts'))
        if rfonts is None:
            rfonts = rpr.makeelement(qn('w:rFonts'), {})
            rpr.insert(0, rfonts)
        rfonts.attrib.pop(qn('w:eastAsiaTheme'), None)
        rfonts.set(qn('w:eastAsia'), KO_FONT)


def page_footer(doc):
    """쪽 아래 가운데 'N / 전체'"""
    from docx.oxml import OxmlElement
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    def field(run, code):
        for kind in ('begin', 'instr', 'end'):
            if kind == 'instr':
                e = OxmlElement('w:instrText'); e.set(qn('xml:space'), 'preserve'); e.text = code
            else:
                e = OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'), kind)
            run._r.append(e)
    for s in doc.sections:
        p = s.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        field(p.add_run(), 'PAGE'); p.add_run(' / '); field(p.add_run(), 'NUMPAGES')


def build(folder, data):
    # 제목에 반·연도·회차가 반드시 들어가야 한다 (예: "양지고2 · 2025년 9월 고2 학평 · 영문 지문 분석 및 번역 모음")
    title = data.get('title') or ''
    if title.strip() == TITLE or not any(c.isdigit() for c in title):
        raise SystemExit('title 에 반 이름·연도·회차를 넣는다 — 예: "양지고2 · 2025년 9월 고2 학평 · ' + TITLE + '"')
    doc = Document()
    set_korean_font(doc)
    doc.add_heading(title, 0)
    page_footer(doc)
    for p in data['passages']:
        doc.add_heading(str(p['no']), 1)
        doc.add_heading(H[0], 2)
        doc.add_paragraph(f"{p['title_ko']} ({p['title_en']})")
        doc.add_heading(H[1], 2)
        for label, key in LABELS:
            para = doc.add_paragraph(style='List Bullet')
            para.add_run(f'{label}: ').bold = True
            para.add_run(p[key])
        doc.add_heading(H[2], 2)
        doc.add_paragraph(p['summary'])
        doc.add_heading(H[3], 2)
        for i, s in enumerate(p['sentences'], 1):
            doc.add_paragraph(f"{i:02d} {s['easy']}")
    out = folder / (data.get('filename') or 'Translation_and_Analysis.docx')
    if out.exists():
        bak = folder / '작업' / (out.stem + '_이전.docx')
        shutil.copy2(out, bak)
    doc.save(out)
    pdf = None
    if Path(SOFFICE).exists():
        subprocess.run([SOFFICE, '--headless', '--convert-to', 'pdf', '--outdir', str(folder / '작업'), str(out)],
                       check=True, capture_output=True)
        pdf = folder / '작업' / (out.stem + '.pdf')
    return out, pdf


# ── 기존 docx → JSON (원문 source·en 은 비어 있으니 채워 넣어야 검증을 통과한다)
def import_docx(path):
    d = Document(path)
    data = {'title': TITLE, 'filename': Path(path).name, 'passages': []}
    cur, sec = None, None
    for para in d.paragraphs:
        st, t = para.style.name, para.text.strip()
        if st == 'Title': data['title'] = t; continue
        if st == 'Heading 1':
            cur = {'no': t, 'title_ko': '', 'title_en': '', 'claim': '', 'develop': '', 'conclude': '', 'summary': '', 'source': '', 'sentences': []}
            data['passages'].append(cur); sec = None; continue
        if st == 'Heading 2': sec = H.index(t) if t in H else None; continue
        if not cur or not t: continue
        if sec == 0:
            m = re.match(r'(.*)\(([^()]*)\)\s*$', t)
            cur['title_ko'], cur['title_en'] = (m.group(1).strip(), m.group(2).strip()) if m else (t, '')
        elif sec == 1:
            for label, key in LABELS:
                if t.startswith(label + ':'): cur[key] = t[len(label) + 1:].strip()
        elif sec == 2:
            cur['summary'] = (cur['summary'] + ' ' + t).strip()
        elif sec == 3:
            m = re.match(r'(\d{2})\s+(.*)', t)
            cur['sentences'].append({'en': '', 'easy': m.group(2) if m else t})
    return data


def main():
    folder = Path(sys.argv[1])
    work = folder / '작업'; work.mkdir(parents=True, exist_ok=True)
    # 여러 반이 같은 회차 폴더를 쓰면 반별 데이터 파일을 둔다: --data 쉬운말번역_<반>.json (2026-10-15)
    js = work / (sys.argv[sys.argv.index('--data') + 1] if '--data' in sys.argv else '쉬운말번역.json')
    if '--import' in sys.argv:
        src = Path(sys.argv[sys.argv.index('--import') + 1])
        if js.exists(): sys.exit(f'이미 {js} 가 있다. 가져오기를 하면 덮어쓴다 — 먼저 확인할 것')
        js.write_text(json.dumps(import_docx(src), ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'가져옴 → {js}  (각 지문의 source·en 을 채운 뒤 다시 빌드)')
        return
    data = json.loads(js.read_text(encoding='utf-8'))
    data['passages'].sort(key=sort_key)
    errs = check(data)
    if errs:
        print('검증 실패 — 문서를 만들지 않았다'); [print('  ' + e) for e in errs]; sys.exit(1)
    out, pdf = build(folder, data)
    n = sum(len(p['sentences']) for p in data['passages'])
    print(f"지문 {len(data['passages'])}개 · 문장 {n}개 · 결함 0")
    print(f'docx → {out}')
    if pdf: print(f'미리보기 PDF → {pdf}')


if __name__ == '__main__':
    main()
