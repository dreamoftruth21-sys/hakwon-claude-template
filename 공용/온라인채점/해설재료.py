"""온라인 해설을 쓰기 위한 재료: 채점키 + 원본 data.json → 문항별 발문·지문·인쇄 순서 선택지·정답·원본 해설(sol).

    py 공용/온라인채점/해설재료.py <시험ID> [--out 파일.md]

- 선택지는 **학생 시험지에 인쇄된 순서**로 적는다 (data.json 은 돌리기 전 순서라 번호가 다르다).
  이유(why)는 이 번호로 쓴다.
- 정답이 채점키와 다르면 멈춘다.
"""
import argparse, html, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = Path(__file__).resolve().parent / "채점키"
CIRC = "①②③④⑤⑥⑦"


def plain(s):
    s = re.sub(r"<br\s*/?>", "\n", str(s or ""))
    s = re.sub(r"</?u>", "_", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def pair(key, d):
    """채점키 문항 ↔ data.json 문항. 모의고사 형식은 선택형 뒤에 서답형, 그 밖은 번호 순."""
    qs = d["questions"]
    if any(q.get("kind") in (None, "choice") and "opts" in q for q in qs):
        cs = [q for q in qs if q.get("kind", "choice") == "choice"]
        ws = [q for q in qs if q.get("kind", "choice") != "choice"]
        src = cs + ws
    else:
        src = qs
    if len(src) != len(key["items"]):
        raise SystemExit(f"문항 수 다름: 채점키 {len(key['items'])} · data {len(src)}")
    return list(zip(key["items"], src))


def printed(q, i, target):
    opts = q.get("opts")
    if not opts:
        return None, q.get("ans")
    if target and not q.get("fixed"):
        r = (q["ans"] - target[i]) % len(opts)
        return opts[r:] + opts[:r], target[i]
    return opts, q["ans"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--out")
    a = ap.parse_args()
    key = json.loads((KEYS / f"{a.id}_채점키.json").read_text(encoding="utf-8"))
    d = json.loads((ROOT / key["data"]).read_text(encoding="utf-8"))
    target = d.get("target")
    passages = d.get("passages", {})

    out, shown, ci = [f"# {key['title']} ({a.id}) — 해설 재료", ""], set(), 0
    for it, q in pair(key, d):
        pk = q.get("passage") or q.get("box_ref")   # 단독 문항은 box_ref 로 지문을 가리킨다 (한솔고)
        body = passages.get(pk) if isinstance(pk, str) else pk
        if isinstance(pk, str) and pk not in shown and body:
            shown.add(pk)
            out += [f"## 지문 {pk}", plain(body.get("header", "")), plain(body.get("body", "")), ""]
        out.append(f"### [{it['label']}] 유형: {it.get('type')} · 입력: {it.get('mode', 'choice')}")
        if isinstance(pk, dict):
            out.append("지문: " + plain(pk.get("body", "")))
        out.append("발문: " + plain(q.get("stem")))
        if q.get("box"):
            out.append("박스: " + plain(q["box"]))
        if it.get("mode", "choice") == "choice":
            opts, ans = printed(q, ci, target)
            if int(it["ans"]) != ans + 1:
                raise SystemExit(f"{it['label']}번 정답 불일치: 채점키 {it['ans']} · 계산 {ans + 1}")
            ci += 1
            if opts:
                out += [f"  {CIRC[j]} {plain(o)}{'  ✔정답' if j == ans else ''}" for j, o in enumerate(opts)]
            else:
                out.append(f"  (선택지는 지문 속 {CIRC[0]}~{CIRC[4]}) 정답 {CIRC[ans]}")
        else:
            out.append("정답/모범답안: " + plain(it.get("ans")))
            for k in ("conditions", "criteria"):
                if q.get(k):
                    out.append(f"{k}: " + plain(q[k] if isinstance(q[k], str) else " / ".join(map(str, q[k]))))
        out.append("원본 해설: " + (plain(q.get("sol")) or "(없음)"))
        out.append("")

    text = "\n".join(out)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(a.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
