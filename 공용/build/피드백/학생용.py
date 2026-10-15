# -*- coding: utf-8 -*-
"""시험 결과 피드백 · 학생용 (오답 해설 포함, 여러 쪽). 학생 한 명에 json 하나.

    py 공용/build/피드백/학생용.py <학생.json>
→ json 과 같은 폴더에 "<file_name>.pdf"

섹션: 결과 요약 · 오답 해설(고른 답 → 정답 · 출제 의도 · 정답 근거 · 보완 방법) · 잘한 점 · 아쉬운 점 · 다음 시험 대비.
점수 대조: 틀린 문항 배점 합 + 점수 = 만점이 아니면 멈춘다 (부분 점수가 있으면 json 에 "check_total": false 와 이유 "check_note").
첫 쪽 삼각형 표식은 찍지 않는다 (결과 피드백 문서).
형식: 예시/학생용_예시.json
"""
import html
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from core.render import html_to_pdf, footer_html  # noqa: E402

CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:"Malgun Gothic","맑은 고딕",sans-serif;color:#1f2a36;background:#fff;
 -webkit-print-color-adjust:exact;print-color-adjust:exact}
.top{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1.6pt solid #1F4E79;padding-bottom:2mm}
.year{font-size:9.5pt;font-weight:700;color:#1F4E79;margin-bottom:.8mm;letter-spacing:.3pt}
.brand{font-size:17pt;font-weight:800;color:#163a5c;letter-spacing:.5pt}
.brand span{color:#3A78B5}
.who{font-size:11pt;font-weight:700;text-align:right}
.who .sc{font-size:20pt;font-weight:800;color:#1F4E79;letter-spacing:.5pt}
.sec{margin-top:2.8mm}
.row{display:flex;gap:4mm;align-items:stretch;break-inside:avoid}
.row .sec{flex:1;min-width:0;display:flex;flex-direction:column}
.row .box{flex:1}
.row .pill{width:26mm;letter-spacing:1pt}
.row .bar .t{font-size:9.3pt}
.bar{break-after:avoid;display:flex;align-items:center;gap:4mm;border:1.2pt solid #1F4E79;border-radius:8mm;background:#fff;height:9mm;padding-right:5mm}
.pill{flex:none;width:32mm;height:100%;border-radius:8mm;background:linear-gradient(#3A78B5,#1F4E79);
 color:#fff;font-size:11.5pt;font-weight:800;display:flex;align-items:center;justify-content:center;letter-spacing:1.5pt}
.bar .t{font-size:10pt;font-weight:700;color:#163a5c}
.box{border:1.2pt solid #1F4E79;background:#F7FAFD;margin-top:2mm;padding:2.5mm 4.4mm}
p{margin:0;font-size:9.6pt;line-height:1.64;word-break:keep-all}
.stat{display:flex;gap:3mm;margin-bottom:2.6mm}
.stat div{flex:1;border:.8pt solid #9db7d1;background:#fff;border-radius:2mm;padding:1.8mm 2mm;text-align:center}
.stat .k{font-size:8.3pt;font-weight:700;color:#1F4E79;display:block;margin-bottom:.8mm}
.stat .v{font-size:11pt;font-weight:800}
.q{border:.8pt solid #9db7d1;background:#fff;border-radius:2mm;padding:2.3mm 3.4mm;margin-top:2mm;break-inside:avoid}
.q:first-child{margin-top:0}
.qh{display:flex;align-items:baseline;gap:2.5mm;border-bottom:.8pt dashed #9db7d1;padding-bottom:1.4mm;margin-bottom:1.8mm;flex-wrap:wrap;break-after:avoid}
.qh .no{font-size:11.5pt;font-weight:800;color:#1F4E79}
.qh .pt{font-size:8.3pt;font-weight:700;color:#fff;background:#3A78B5;border-radius:3mm;padding:.4mm 2mm}
.qh .ty{font-size:9.3pt;font-weight:700;flex:1}
.qa{font-size:9pt;margin-bottom:1.4mm}
.qa .mine{color:#8A3B16;font-weight:700}
.qa .ans{color:#1F4E79;font-weight:800}
.q p{font-size:9.2pt;line-height:1.56;orphans:2;widows:2}
.q p+p{margin-top:1.3mm}
.lab{font-weight:800;color:#1F4E79;margin-right:1.5mm}
ul{margin:0;padding-left:5mm}
li{font-size:9.55pt;line-height:1.6;margin-top:1.3mm;word-break:keep-all}
li:first-child{margin-top:0}
"""


def ul(items):
    return "<ul>%s</ul>" % "".join("<li>%s</li>" % x for x in items)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = pathlib.Path(sys.argv[1]).resolve()
    D = json.loads(src.read_text(encoding="utf-8"))
    Q = D["questions"]
    total = D.get("total", 100)
    lost = round(sum(q["pt"] for q in Q), 1)
    if D.get("check_total", True) and abs(lost + D["score"] - total) > 0.05:
        sys.exit("점수 대조 실패: 틀린 문항 배점 합 %s + 점수 %s ≠ %s — 받은 정보를 다시 확인한다" % (lost, D["score"], total))
    cards = []
    for q in Q:
        written = q.get("written") or str(q["no"]).startswith(("단답", "서답", "서술"))
        cards.append(
            f"<div class='q'><div class='qh'><span class='no'>{html.escape(str(q['no']))}</span><span class='pt'>{q['pt']:.1f}점</span>"
            f"<span class='ty'>{html.escape(q['type'])}</span></div>"
            f"<p class='qa'>{'쓴 답' if written else '고른 답'} <span class='mine'>{html.escape(q['mine'])}</span> &nbsp;→&nbsp; 정답 <span class='ans'>{html.escape(q['ans'])}</span></p>"
            f"<p><span class='lab'>출제 의도</span>{q['ask']}</p>"
            f"<p><span class='lab'>정답 근거</span>{q['key']}</p>"
            f"<p><span class='lab'>보완 방법</span>{q['next']}</p></div>")
    doc = f"""<!doctype html><meta charset="utf-8"><title>학생용 결과 피드백</title><style>{CSS}</style><body>
<div class="top"><div><div class="year">{html.escape(D['title_line'])}</div>
 <div class="brand">{html.escape(D['brand'])} <span>{html.escape(D['subject'])}</span></div></div>
 <div class="who">{html.escape(D['name'])}<br><span class="sc">{D['score']}점</span></div></div>
<div class="sec"><div class="bar"><div class="pill">결과 요약</div><div class="t">점수와 오답 현황</div></div>
 <div class="box">
  <div class="stat"><div><span class="k">점수</span><span class="v">{D['score']} / {total}</span></div>
   <div><span class="k">{html.escape(D.get('wrong_label', '틀린 문항'))}</span><span class="v" style="font-size:9.6pt">{html.escape(' · '.join(str(q['no']) for q in Q))}</span></div>
   <div><span class="k">놓친 점수</span><span class="v">{round(total - D['score'], 1)}점</span></div></div>
  <p>{D['summary']}</p></div></div>
<div class="sec"><div class="bar"><div class="pill">오답 해설</div><div class="t">문항별 출제 의도와 정답 근거</div></div>
 <div class="box">{"".join(cards)}</div></div>
<div class="row">
 <div class="sec"><div class="bar"><div class="pill">잘한 점</div><div class="t">확인한 강점</div></div>
  <div class="box">{ul(D['good'])}</div></div>
 <div class="sec"><div class="bar"><div class="pill">아쉬운 점</div><div class="t">점수를 잃은 원인</div></div>
  <div class="box">{ul(D['bad'])}</div></div></div>
<div class="sec"><div class="bar"><div class="pill">{html.escape(D.get('plan_title', '다음 시험 대비'))}</div><div class="t">다음 시험까지 할 일</div></div>
 <div class="box">{ul(D['plan'])}</div></div>
</body>"""
    pdf = src.parent / (D["file_name"] + ".pdf")
    html_to_pdf([(doc, pdf)], footer=footer_html(html.escape(D.get("footer", D["file_name"]))),
                margin={"top": "10mm", "bottom": "12mm", "left": "12mm", "right": "12mm"})
    print("저장", pdf.name)


if __name__ == "__main__":
    main()
