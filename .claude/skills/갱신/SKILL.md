---
name: 갱신
description: GitHub 에 올라온 이 템플릿의 새 판(스킬 · 빌더 · 규칙 · 온라인 채점 코드)을 받아 이 컴퓨터에 덮어쓴다. 반 폴더와 선생님 데이터는 건드리지 않는다. 사용자가 "갱신해줘", "업데이트", "새 판 받아", "최신으로"라고 할 때 쓴다.
---

# 템플릿 갱신

저장소: `https://github.com/dreamoftruth21-sys/hakwon-claude-template` (zip: `https://github.com/dreamoftruth21-sys/hakwon-claude-template/archive/refs/heads/main.zip`)

1. 지금 판: `공용/VERSION.txt`. zip 을 스크래치 폴더에 내려받아 풀고 새 판의 `공용/VERSION.txt` 와 비교한다. 같으면 "이미 최신입니다"로 끝낸다.
2. 바뀌는 파일 목록을 보여 주고 승인을 받는다.
3. 덮어쓰는 것: `.claude/skills/` · `.claude/agents/` · `공용/build/` · `공용/규칙/` · `공용/온라인채점/`(코드와 README 형식) · `_새반_틀/` · `README.md` · `공용/VERSION.txt`
4. **건드리지 않는 것** — 반 폴더 전부 · `공용/설정상태.json` · `공용/온라인채점/채점키/` · `해설/` · `정정/` · `제안/` · `apps_script/.clasp.json` · `공용/build/학교/` 의 `_예시.json` 밖 파일 · `.claude/skills/자료정리/rules.ps1` · `무시목록.txt` · 선생님이 새로 만든 스킬(새 판에 없는 스킬 폴더는 그대로 둔다)
5. `공용/온라인채점/README.md` 는 새 판으로 바꾸되 「링크」 절의 웹 앱 URL · 배포 ID · 시험 링크 줄은 지금 것을 그대로 옮겨 넣는다.
6. 루트 `CLAUDE.md` 는 선생님이 고쳤을 수 있다. 새 판과 다르면 달라진 부분을 보여 주고 어떻게 할지 묻는다.
7. `Code.gs` · `Index.html` 이 바뀌었으면 `py 공용/온라인채점/설치.py 재배포` 로 같은 주소에 다시 배포한다. 새 권한이 생겼으면 편집기에서 「설치확인」을 한 번 실행해 허용해 달라고 한다.
8. 보고: 새 판 번호 · 바뀐 스킬 · 재배포 여부.
