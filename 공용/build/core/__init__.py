"""학원 자료 빌드 공용 모듈.

text     글자 다루기 — 정규화·태그 제거·선택지 회전·n-gram
checks   점검 — 결함을 모아 하나라도 있으면 PDF를 내보내지 않는다
render   HTML → PDF (임시 폴더에 뽑고 점검 통과 후에만 옮긴다)
sources  원문 불러오기 — 학평 bynum · PDF · 학교자료/_텍스트

옛 `공용/build/bld.py` 와는 별개다. 그 파일은 손대지 않는다.
"""
