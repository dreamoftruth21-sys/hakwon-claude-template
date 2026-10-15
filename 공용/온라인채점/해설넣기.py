"""해설/<시험ID>_해설.json 을 점검하고 채점키에 넣는다. 결과 화면 [해설 보기] 에 나온다.

    py 공용/온라인채점/해설넣기.py <시험ID>

해설 파일 형식 (번호는 채점키 label — "3", "서답형 2"):
{
 "3":  {"exp": "두세 줄 해설"},
 "7":  {"exp": "...", "why": {"1": "①이 맞는 까닭 한 줄", "2": "...", "4": "...", "5": "..."}}
}
- 모든 문항에 exp (맞은 문항 해설도 보여 준다 — 2026-09-30 사용자 결정)
- why 는 어법·어휘 선택형에만, 정답을 뺀 선택지 번호 전부. 번호는 학생 시험지에 인쇄된 번호 (해설재료.py 출력 기준)
- 점검에 하나라도 걸리면 채점키를 고치지 않는다
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS, EXPS = HERE / "채점키", HERE / "해설"
WHY_TYPES = ("어법", "어휘")
BANNED = ["하세요", "판서", "채점하면", "학생이", "출제자", "배점"]
EXP_MAX, WHY_MAX = 170, 90


def check(key, exp):
    errs = []
    labels = [it["label"] for it in key["items"]]
    extra = set(exp) - set(labels)
    if extra:
        errs.append(f"채점키에 없는 번호: {sorted(extra)}")
    for it in key["items"]:
        lab, e = it["label"], exp.get(it["label"])
        if not e or not str(e.get("exp", "")).strip():
            errs.append(f"[{lab}] exp 없음")
            continue
        texts = [("exp", e["exp"], EXP_MAX)] + [(f"why {k}", v, WHY_MAX) for k, v in (e.get("why") or {}).items()]
        for name, t, mx in texts:
            if len(t) > mx:
                errs.append(f"[{lab}] {name} {len(t)}자 (최대 {mx})")
            for b in BANNED:
                if b in t:
                    errs.append(f"[{lab}] {name} 금지어 '{b}'")
            if re.search(r"\d+(\.\d+)?\s*점|부분 점수|감점", t):   # 학생 화면에 배점·채점 정보를 내지 않는다
                errs.append(f"[{lab}] {name} 점수 언급")
        needs_why = it.get("mode", "choice") == "choice" and any(t in str(it.get("type")) for t in WHY_TYPES)
        why = e.get("why")
        if needs_why:
            want = {str(c) for c in range(1, key.get("choices", 5) + 1)} - {str(it["ans"])}
            if not why or set(why) != want:
                errs.append(f"[{lab}] {it.get('type')} 문항 why 는 {sorted(want)} 번이 다 있어야 함 (있는 것: {sorted(why or {})})")
        elif why:
            errs.append(f"[{lab}] why 는 어법·어휘 선택형에만 (이 문항: {it.get('type')})")
    return errs


def main(id_):
    kf, ef = KEYS / f"{id_}_채점키.json", EXPS / f"{id_}_해설.json"
    key = json.loads(kf.read_text(encoding="utf-8"))
    exp = json.loads(ef.read_text(encoding="utf-8"))
    errs = check(key, exp)
    if errs:
        print(f"{id_}: 점검 {len(errs)}건 — 채점키 그대로\n  " + "\n  ".join(errs))
        return False
    for it in key["items"]:
        e = exp[it["label"]]
        it["exp"] = e["exp"].strip()
        if e.get("why"):
            it["why"] = {k: v.strip() for k, v in e["why"].items()}
        else:
            it.pop("why", None)
    key["showExp"] = True
    kf.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    n_why = sum(1 for it in key["items"] if it.get("why"))
    print(f"{id_}: 해설 {len(key['items'])}문항 · 선택지 이유 {n_why}문항 → 채점키에 넣음")
    return True


if __name__ == "__main__":
    ok = all([main(i) for i in sys.argv[1:]])
    sys.exit(0 if ok else 1)
