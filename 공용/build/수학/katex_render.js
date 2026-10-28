// LaTeX → HTML (KaTeX, 빌드할 때 이 PC 에서 바로 — 인터넷이 없어도 된다).
// 사용: node katex_render.js <katex 패키지 폴더>   표준 입력: {"items":[{"t":"x^2","d":false}], "macros":{}}
// 표준 출력: [{"h":"<span class=katex>…"} | {"e":"오류 내용"}]  — 오류가 하나라도 있으면 빌더가 PDF 를 내지 않는다.
const katex = require(process.argv[2]);
let buf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => (buf += c));
process.stdin.on("end", () => {
  const job = JSON.parse(buf);
  const out = job.items.map(({ t, d }) => {
    try {
      // strict: "error" — 수식 안 한글(\text{} 없이) 같은 것도 오류로 본다
      return { h: katex.renderToString(t, { displayMode: !!d, throwOnError: true, strict: "error",
                                            output: "html", macros: Object.assign({}, job.macros || {}) }) };
    } catch (e) {
      return { e: String(e.message || e) };
    }
  });
  process.stdout.write(JSON.stringify(out));
});
