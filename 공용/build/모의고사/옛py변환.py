# -*- coding: utf-8 -*-
"""옛 실전 모의고사 py 데이터를 data.json 으로 옮긴다. 옛 폴더는 읽기만 한다.

  세종예고2 형식 (exam.py: Q 사전 목록 · PSG{kind,restore,guard,free,src,body} · TARGET · GROUPS · BL)
    py 옛py변환.py sejong <옛 폴더> <출력 json>
  나성중3 형식 (ex*.py: Q 튜플 · PSG{키: (머리글, 본문)} / mk*.py: FIXED · POS)
    py 옛py변환.py nasung <옛 폴더> <출력 json> <ex 모듈명> <mk 파일명>

회차마다 심은 장치 점검("checks")·원문("sources")·제목 문구는 옮기지 않는다 — 옮긴 뒤 손으로 채운다.
"""
import importlib.util
import json
import pathlib
import re
import sys

BLANK_TOKEN = "{{빈칸}}"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(pathlib.Path(path).parent))
    spec.loader.exec_module(m)
    return m


def sub_blank(obj, bl):
    if isinstance(obj, str):
        return obj.replace(bl, BLANK_TOKEN) if bl else obj
    if isinstance(obj, (list, tuple)):
        return [sub_blank(x, bl) for x in obj]
    if isinstance(obj, dict):
        return {k: sub_blank(v, bl) for k, v in obj.items()}
    return obj


def sejong(folder):
    ex = load_module(folder / "exam.py", "exam_old")
    passages = {}
    for k, p in ex.PSG.items():
        e = {"kind": p.get("kind", "rewrite"), "src": p.get("src"), "body": p["body"],
             "restore": [list(x) for x in p.get("restore", [])], "guard": list(p.get("guard", [])),
             "free": list(p.get("free", []))}
        if k in ex.GROUPS:
            label = ex.GROUPS[k]
            e["header"] = "%s 다음 글을 읽고 물음에 답하시오." % label
            e["range"] = list(map(int, label.strip("[]").split("~")))
        passages[k] = e
    qs = []
    for q in ex.Q:
        box, box_ref = q["box"], None
        if box and box in ex.PSG:
            box, box_ref = None, q["box"]
        qs.append({"n": q["n"], "pt": q["pt"], "passage": q["grp"], "box": box, "box_ref": box_ref,
                   "stem": q["stem"], "show": q["show"], "fixed": q["fixed"], "ans": q["ans"],
                   "opts": q["opts"], "sol": q["sol"]})
    d = {"passages": passages, "questions": qs, "target": list(ex.TARGET), "sol_numbers": "forbid"}
    return sub_blank(d, ex.BL), ex


def nasung(folder, ex_name, mk_name):
    ex = load_module(folder / (ex_name + ".py"), ex_name)
    mk = (folder / mk_name).read_text(encoding="utf-8")
    fixed = set(map(int, re.search(r"FIXED\s*=\s*\{([^}]*)\}", mk).group(1).replace(" ", "").split(",")))
    pos = list(map(int, re.search(r"POS\s*=\s*\[([^\]]*)\]", mk).group(1).replace(" ", "").split(",")))
    passages = {k: {"header": h, "body": b, "kind": "rewrite"} for k, (h, b) in ex.PSG.items()}
    qs, target, k = [], [], 0
    for n, pt, psg, stem, bogi, opts, ans, sol in ex.Q:
        if n in fixed:
            target.append(ans)
        else:
            target.append(pos[k % len(pos)])
            k += 1
        qs.append({"n": n, "pt": pt, "passage": psg, "box": bogi or None, "box_ref": None, "stem": stem,
                   "show": "list", "fixed": n in fixed, "ans": ans, "opts": list(opts), "sol": sol})
    return {"passages": passages, "questions": qs, "target": target, "sol_numbers": "remap"}, ex


if __name__ == "__main__":
    kind, folder, out = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    if kind == "sejong":
        d, _ = sejong(folder)
    else:
        d, _ = nasung(folder, sys.argv[4], sys.argv[5])
    out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장", out, "· 문항", len(d["questions"]), "· 지문", len(d["passages"]))
