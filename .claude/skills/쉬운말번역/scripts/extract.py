# -*- coding: utf-8 -*-
"""학평 문제지 PDF에서 지정한 번호의 지문 원문을 뽑는다 (텍스트 PDF만).

  py extract.py <문제지.pdf> 24 29 32

발문·선택지·주석이 같이 나온다. source 에는 지문 본문만 옮긴다.
스캔 PDF라 텍스트가 안 나오면 쪽을 png로 렌더해서 눈으로 받아 적는다.
"""
import re, sys
import pymupdf

pdf, nos = sys.argv[1], sys.argv[2:]
text = '\n'.join(p.get_text() for p in pymupdf.open(pdf))
if len(text.strip()) < 200:
    sys.exit('텍스트가 거의 없다 — 스캔본이다. 렌더해서 읽을 것')
for n in nos:
    m = re.search(rf'\n{n}\.\s(.*?)(?=\n{int(n) + 1}\.\s|\Z)', text, re.S)
    print(f'===== {n}')
    if not m:
        print('(못 찾음 — 묶음 문항 [41~42] 이면 앞 번호로 찾을 것)')
        continue
    body = m.group(1)
    body = re.sub(r'(?m)^\s*\d+\s*$', '', body)            # 쪽 번호
    body = re.sub(r'(?m)^(영어영역|고\d)\s*$', '', body)      # 머리글
    body = re.sub(r'(?<=\w)\s*\n\s*(?=\w)', ' ', body)       # 줄바꿈으로 끊긴 단어 사이
    print(re.sub(r'\n{2,}', '\n', body).strip())
