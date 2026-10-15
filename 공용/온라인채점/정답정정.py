"""이미 배포한 시험의 선택형 정답을 고치거나 복수 정답을 인정한다. 고친 뒤 시트 메뉴 [온라인채점 → 정답 고친 시험 재채점].

    py 공용/온라인채점/정답정정.py <시험ID> <번호> <정답>[,<정답>…] [--사유 "…"]
    py 공용/온라인채점/정답정정.py 세종예고1_실전4회 7 4        # 7번 정답을 ④로
    py 공용/온라인채점/정답정정.py 세종예고1_실전4회 7 2,4      # 7번은 ②·④ 둘 다 정답
    py 공용/온라인채점/정답정정.py <시험ID> --다시              # 정정 기록을 채점키에 다시 넣기 (채점키.py 가 부른다)

- 번호는 인쇄된 번호(채점키 label). 정답도 인쇄된 선택지 번호
- 정정 기록은 정정/<시험ID>_정정.json 에 남는다 — 채점키를 다시 만들어도 사라지지 않게
- **원본 data.json·배부한 답지 PDF 는 고치지 않는다.** 필요하면 따로 고친다
- 그 문항 해설(exp·why)이 옛 정답 기준이면 해설/<시험ID>_해설.json 도 고치고 해설넣기.py 를 다시 돌린다
"""
import argparse, json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS, FIXES = HERE / "채점키", HERE / "정정"


def apply(key, fixes):
    by = {it["label"]: it for it in key["items"]}
    for lab, f in fixes.items():
        it = by.get(lab)
        if not it:
            raise SystemExit(f"채점키에 없는 번호: {lab}")
        if it.get("mode", "choice") != "choice":
            raise SystemExit(f"{lab}번은 선택형이 아니다 — 서답형은 data.json 을 고쳐 채점키를 다시 만든다")
        it["ans"] = f["ans"][0]
        if len(f["ans"]) > 1:
            it["alt"] = f["ans"][1:]
        else:
            it.pop("alt", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("label", nargs="?")
    ap.add_argument("answers", nargs="?")
    ap.add_argument("--사유", default="")
    ap.add_argument("--다시", action="store_true")
    a = ap.parse_args()

    kf, ff = KEYS / f"{a.id}_채점키.json", FIXES / f"{a.id}_정정.json"
    key = json.loads(kf.read_text(encoding="utf-8"))
    fixes = json.loads(ff.read_text(encoding="utf-8")) if ff.exists() else {}
    if not a.다시:
        if not a.label or not a.answers:
            raise SystemExit("번호와 정답을 준다 (예: 7 2,4)")
        ans = [int(x) for x in a.answers.split(",")]
        if any(not 1 <= x <= key.get("choices", 5) for x in ans):
            raise SystemExit("정답은 1~5")
        old = next((it for it in key["items"] if it["label"] == a.label), None)
        fixes[a.label] = {"ans": ans, "old": old and [old["ans"]] + old.get("alt", []),
                          "사유": a.사유, "시각": datetime.now().strftime("%Y-%m-%d %H:%M")}
        FIXES.mkdir(exist_ok=True)
        ff.write_text(json.dumps(fixes, ensure_ascii=False, indent=1), encoding="utf-8")
    apply(key, fixes)
    kf.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    for lab, f in fixes.items():
        print(f"{a.id} {lab}번 정답 → {', '.join('①②③④⑤'[x - 1] for x in f['ans'])}" + (f"  (전: {f['old']})" if f.get("old") else ""))
    if not a.다시:
        print("드라이브 동기화 뒤 시트 메뉴 [온라인채점 → 정답 고친 시험 재채점] 에 이 시험 ID 를 넣는다")


if __name__ == "__main__":
    main()
