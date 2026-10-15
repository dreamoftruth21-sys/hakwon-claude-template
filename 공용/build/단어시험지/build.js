/* 단어시험지 빌더 — DOCX → LibreOffice → PDF (시험지 + 정답지)

   사용: node 공용/build/단어시험지/build.js <data.json> [--out 폴더]
   - 데이터 형식은 같은 폴더 README.md
   - 학교 규격은 공용/build/학교/<school>.json 의 "vocab_test" (총 문항 · 내지 않는 파트 유형)
   - 점검(데이터 → PDF 실물)에 하나라도 걸리면 PDF를 내보내지 않는다
   기준 구현: .claude/skills/단어시험지/reference/hs/test10b.js (한솔고2) · sj2/test_l1.js (세종예고2) · sj1/test2.js (세종예고1)
*/
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, BorderStyle, AlignmentType, ShadingType, VerticalAlign, PageBreak } = require("docx");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..", "..", "..");
const SOFFICE = "C:\\Program Files\\LibreOffice\\program\\soffice.com";
const KR = "맑은 고딕";
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noB = { top: NONE, bottom: NONE, left: NONE, right: NONE };
const ul = { top: NONE, left: NONE, right: NONE, bottom: { style: BorderStyle.SINGLE, size: 4, color: "999999" } };
const CONTENT = 10106, GAP = 240, RED = "C00000";
const CIRC = ["①", "②", "③", "④", "⑤"];
const CIR6 = ["ⓐ", "ⓑ", "ⓒ", "ⓓ", "ⓔ", "ⓕ"];
const TEACHER = ["하세요", "판서", "채점하면", "학생이", "재시험", "커트라인", "통과 기준"];

/* ───────── 불러오기 ───────── */
const args = process.argv.slice(2);
if (!args.length) { console.error("사용: node build.js <data.json> [--out 폴더]"); process.exit(2); }
const dataPath = path.resolve(args[0]);
const outDir = args.includes("--out") ? path.resolve(args[args.indexOf("--out") + 1]) : path.dirname(dataPath);
const D = JSON.parse(fs.readFileSync(dataPath, "utf8"));
for (const k of ["school", "name", "head1", "head2", "parts"])
  if (!(k in D)) { console.error(`data.json 에 '${k}' 가 없다`); process.exit(2); }
const profPath = path.join(ROOT, "공용", "build", "학교", D.school + ".json");
if (!fs.existsSync(profPath)) { console.error("학교 설정이 없다: " + profPath); process.exit(2); }
const PROF = JSON.parse(fs.readFileSync(profPath, "utf8")).vocab_test || {};
const ACC = D.accent || "1F4E79";
const LEX = D.lexicon || {};                // { word: {m, syn:[], ant:[]} }
const STYLE = D.cell_style || "a";          // a: 위·아래 여백 = m (기본 150) / b: 위 = m (기본 124), 아래 = mb (기본 40)
const NS = D.layout === "나성중";             // 나성중3 판형 (reference/ns6/build_def.js): 글자 18 · 칸 위 정렬 · 여백 58 · 주황 상자
const ANS_SUFFIX = D.answer_suffix || "_답지";

/* ───────── 점검 모음 ───────── */
const bad = [], info = [];
const fail = (tag, msg) => bad.push(`[${tag}] ${msg}`);

/* ───────── 문서 조각 ───────── */
function T(t, o = {}) { return new TextRun({ text: t, font: KR, size: o.size || (NS ? 18 : 19), bold: !!o.bold,
  color: o.color || "000000", underline: o.u ? {} : undefined }); }
function P_(runs, o = {}) { return new Paragraph({ spacing: { before: o.b || 0, after: o.a || 0, line: o.line || 230, lineRule: "auto" },
  alignment: o.align || AlignmentType.LEFT, indent: o.ind, children: runs }); }
function C_(ch, w, b, o = {}) {
  if (NS) return new TableCell({ width: { size: w, type: WidthType.DXA }, borders: b || noB,
    verticalAlign: o.va || VerticalAlign.TOP, margins: { top: o.m === undefined ? 58 : o.m,
      bottom: o.mb !== undefined ? o.mb : (o.m === undefined ? 58 : o.m), left: 36, right: 36 }, children: ch });
  const top = STYLE === "b" ? (o.m === undefined ? 124 : o.m) : (o.m === undefined ? 150 : o.m);
  const bottom = STYLE === "b" ? (o.mb !== undefined ? o.mb : 40)
                               : (o.mb !== undefined ? o.mb : (o.m === undefined ? 150 : o.m));
  return new TableCell({ width: { size: w, type: WidthType.DXA }, borders: b || noB,
    verticalAlign: o.va || VerticalAlign.BOTTOM, margins: { top, bottom, left: 38, right: 38 }, children: ch });
}
const bd = { style: BorderStyle.SINGLE, size: 6, color: "9AA6B2" };
function boxTable(children, margins) {
  return new Table({ columnWidths: [CONTENT], width: { size: CONTENT, type: WidthType.DXA },
    rows: [new TableRow({ children: [new TableCell({ width: { size: CONTENT, type: WidthType.DXA },
      borders: { top: bd, bottom: bd, left: bd, right: bd }, margins, children })] })] });
}
/* 나성중3 보기 상자 — 머리 없이 연한 주황 바탕 */
function boxNS(words, per) {
  const b2 = { style: BorderStyle.SINGLE, size: 6, color: "D9B48F" };
  const lines = [];
  for (let i = 0; i < words.length; i += per) lines.push(words.slice(i, i + per));
  return new Table({ columnWidths: [CONTENT], width: { size: CONTENT, type: WidthType.DXA },
    rows: [new TableRow({ children: [new TableCell({ width: { size: CONTENT, type: WidthType.DXA },
      borders: { top: b2, bottom: b2, left: b2, right: b2 }, shading: { type: ShadingType.CLEAR, fill: "FBF6F0", color: "auto" },
      margins: { top: 70, bottom: 70, left: 120, right: 120 },
      children: lines.map((l, i) => new Paragraph({ spacing: { before: i ? 55 : 0, after: 0, line: 230, lineRule: "auto" },
        alignment: AlignmentType.CENTER, children: [T(l.join("      "), { size: 18 })] })) })] })] });
}
/* 〈보기〉 상자 — 단어를 per 개씩 한 줄 (세종예고 형식) */
function boxWords(words, per) {
  if (NS) return boxNS(words, per);
  const lines = [];
  for (let i = 0; i < words.length; i += per) lines.push(words.slice(i, i + per).join("        "));
  return boxTable([P_([T("< 보 기 >", { size: 15, bold: true, color: "6B7684" })], { align: AlignmentType.CENTER, a: 75 }),
    ...lines.map((l, i) => P_([T(l, { size: 18 })], { align: AlignmentType.CENTER, b: i ? 65 : 0 }))],
    { top: 115, bottom: 115, left: 120, right: 120 });
}
/* 뜻 번호 상자 — 줄 단위 (한솔고 다의어 형식) */
function boxLines(lines) {
  return boxTable(lines.map((l, i) => P_([T(l, { size: 17 })], { align: AlignmentType.CENTER, b: i ? 60 : 0 })),
    { top: 110, bottom: 110, left: 120, right: 120 });
}
function tag(type) {
  return new TextRun({ text: " " + type + " ", font: KR, size: 15, bold: true, color: "FFFFFF",
    shading: { type: ShadingType.CLEAR, fill: type === "유의어" ? "2E5C8A" : "C0504D", color: "auto" } });
}
function secH(letter, title, sub) {
  if (NS) return new Paragraph({ spacing: { before: 170, after: 80 }, children: [
    new TextRun({ text: " " + letter + " ", font: KR, size: 19, bold: true, color: "FFFFFF",
      shading: { type: ShadingType.CLEAR, fill: ACC, color: "auto" } }),
    new TextRun({ text: "  " + title, font: KR, size: 19, bold: true, color: ACC }),
    ...(sub ? [new TextRun({ text: "   " + sub, font: KR, size: 15, color: "909090" })] : [])] });
  return new Paragraph({ spacing: { before: 215, after: 100 }, children: [
    new TextRun({ text: " " + letter + " ", font: KR, size: 20, bold: true, color: "FFFFFF",
      shading: { type: ShadingType.CLEAR, fill: ACC, color: "auto" } }),
    new TextRun({ text: "  " + title, font: KR, size: 20, bold: true, color: ACC }),
    new TextRun({ text: "   " + sub, font: KR, size: 15, color: "909090" })] });
}
const spacer = () => NS ? P_([T("", { size: 6 })], { a: 60 }) : P_([T("", { size: 8 })], { a: 70 });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

/* ───────── 파트 유형 ─────────
   각 유형: n(part) 문항 수 · words(part) 표제어(파트 간 중복 검사용) · check(part, start) · render(part, start, ans) */
const TYPES = {};

/* 뜻쓰기 — 영어 제시, 우리말 뜻 쓰기. 2단 표 */
TYPES.meaning = {
  n: p => p.items.length,
  words: p => p.items.map(x => x.w),
  check(p, L) {
    const ws = p.items.map(x => x.w);
    if (new Set(ws).size !== ws.length) fail(L, "표제어 중복");
    if (p.items.length % 2 && !NS) fail(L, "2단 배치라 문항 수가 짝수여야 한다");
    p.items.forEach(x => { if (!x.m || !x.m.trim()) fail(L, "뜻 없음: " + x.w); });
    const ms = p.items.map(x => x.m), dm = ms.filter((m, i) => ms.indexOf(m) !== i);
    if (dm.length && !p.allow_same_meaning) fail(L, "우리말 뜻이 완전히 같은 항목: " + [...new Set(dm)].join(", "));
    if (p.order) {
      const o = p.order;
      if (o.length !== ws.length || new Set(o).size !== o.length || Math.min(...o) !== 0 || Math.max(...o) !== o.length - 1)
        fail(L, "order 가 0~N-1 순열이 아님");
      let run = 1, mx = 1;
      for (let i = 1; i < o.length; i++) { run = o[i] === o[i - 1] + 1 ? run + 1 : 1; mx = Math.max(mx, run); }
      if (mx >= 3) fail(L, "교재 순서를 연속 " + mx + "개 따라감");
    } else info.push(`${L}: order 없음 — 입력 순서대로 싣는다`);
  },
  render(p, start, ans) {
    if (NS) {   // build_def.js two()
      const [qw, aw] = p.widths || [1900, 2623], G = 260, VB = VerticalAlign.BOTTOM, m = p.m;
      const items = (p.order || p.items.map((_, i) => i)).map(i => p.items[i]);
      const o = { m, mb: 34, va: VB };
      if (p.cols === 1) {   // 긴 어구(Collocations)용 1단 — widths 는 [어구, 답칸], 합이 CONTENT - 400
        const [q1, a1] = p.widths || [4700, CONTENT - 400 - 4700];
        return [new Table({ columnWidths: [400, q1, a1], width: { size: CONTENT, type: WidthType.DXA },
          rows: items.map((x, i) => new TableRow({ children: [
            C_([P_([T(String(start + i) + ".", { size: 17 })])], 400, noB, o),
            C_([P_([T(x.w, { size: 18 })])], q1, noB, o),
            ans ? C_([P_([T(x.m, { size: 18, bold: true, color: RED })])], a1, noB, o) : C_([P_([T("")])], a1, ul, o)] })) })];
      }
      const rows = [], half = Math.ceil(items.length / 2);
      for (let i = 0; i < half; i++) {
        const mk = idx => {
          if (idx >= items.length) return [C_([P_([T("")])], 400, noB, o), C_([P_([T("")])], qw, noB, o), C_([P_([T("")])], aw, noB, o)];
          const x = items[idx];
          return [C_([P_([T(String(start + idx) + ".", { size: 17 })])], 400, noB, o),
            C_([P_([T(x.w, { size: 18 })])], qw, noB, o),
            ans ? C_([P_([T(x.m, { size: 18, bold: true, color: RED })])], aw, noB, o) : C_([P_([T("")])], aw, ul, o)];
        };
        rows.push(new TableRow({ children: [...mk(i), C_([P_([T("")])], G, noB, { m, mb: m + 30 }), ...mk(i + half)] }));
      }
      return [new Table({ columnWidths: [400, qw, aw, G, 400, qw, aw], width: { size: CONTENT, type: WidthType.DXA }, rows })];
    }
    const [wn, we, wa] = p.widths || [420, 2400, CONTENT / 2 - 420 - 2400 - GAP / 2];
    const items = (p.order || p.items.map((_, i) => i)).map(i => p.items[i]);
    const rows = [], half = items.length / 2;
    for (let i = 0; i < half; i++) {
      const mk = idx => { const x = items[idx]; return [
        C_([P_([T(String(start + idx) + ".", { size: 18 })])], wn, noB, { m: p.m }),
        C_([P_([T(x.w, { size: 18 })])], we, noB, { m: p.m }),
        ans ? C_([P_([T(x.m, { size: 16, bold: true, color: RED }),
                      ...(x.tag ? [T("  [" + x.tag + "]", { size: 13, color: "999999" })] : [])])], wa, noB, { m: p.m })
            : C_([P_([T("")])], wa, ul, { m: p.m })]; };
      rows.push(new TableRow({ children: [...mk(i), C_([P_([T("")])], GAP, noB, { m: p.m }), ...mk(i + half)] }));
    }
    return [new Table({ columnWidths: [wn, we, wa, GAP, wn, we, wa], width: { size: CONTENT, type: WidthType.DXA }, rows })];
  },
};

/* 문장 속 밑줄어 유의어·반의어 5지선다 (한솔고 B) */
TYPES.choice5_sentence = {
  n: p => p.items.length,
  words: p => p.items.map(x => x.lemma || x.word),
  check(p, L) {
    p.items.forEach(x => {
      if (x.options.length !== 5 || new Set(x.options).size !== 5) fail(L, "선택지 오류: " + x.word);
      if (!(x.answer >= 0 && x.answer <= 4)) fail(L, "정답 번호 오류: " + x.word);
      const lx = LEX[x.lemma || x.word];
      if (lx) {
        const pool = x.type === "유의어" ? lx.syn : lx.ant;
        if (pool && pool.length && !pool.includes(x.options[x.answer]))
          info.push(`${L}: ${x.word} 정답 '${x.options[x.answer]}' 이 단어장 ${x.type} 목록에 없음 (문맥 판단 확인)`);
      } else if (Object.keys(LEX).length) fail(L, "단어장에 없음: " + (x.lemma || x.word));
    });
    const a = p.items.map(x => x.answer);
    let run = 1, mx = 1;
    for (let i = 1; i < a.length; i++) { run = (a[i] === a[i - 1] + 1 || a[i] === a[i - 1]) ? run + 1 : 1; mx = Math.max(mx, run); }
    if (mx >= 4) fail(L, "정답이 연속 패턴(" + mx + "개)");
    const types = p.items.map(x => x.type), fa = types.indexOf("반의어");
    if (fa !== -1 && types.slice(fa).some(t => t === "유의어")) fail(L, "유의어/반의어가 섞여 배치됨");
    const cnt = {}; a.forEach(v => cnt[v] = (cnt[v] || 0) + 1);
    const v = Object.values(cnt);
    if (a.length >= 5 && (Object.keys(cnt).length !== 5 || Math.max(...v) - Math.min(...v) > 1))
      fail(L, "정답 번호 편중: " + JSON.stringify(cnt));
  },
  render(p, start, ans) {
    const out = [];
    p.items.forEach((x, i) => {
      out.push(new Paragraph({ spacing: { before: i === 0 ? 110 : (p.gap || 1000), after: 60 }, children: [
        T(String(start + i) + ".  ", { size: 18 }), tag(x.type),
        T("   ", { size: 17 }), T(x.pre, { size: 18 }), T(x.word, { size: 18, bold: true, u: true }), T(x.post, { size: 18 })] }));
      out.push(new Paragraph({ spacing: { before: 0, after: 250, line: 230 }, indent: { left: 420 }, children:
        x.options.flatMap((o, j) => { const hit = ans && j === x.answer;
          return [T(CIRC[j] + " ", { size: 18, bold: hit, color: hit ? RED : "000000" }),
                  T(o + "    ", { size: 18, bold: hit, color: hit ? RED : "000000" })]; }) }));
    });
    return out;
  },
};

/* 대화 흐름 5지선다 — 빈칸(____) 한 곳에 들어갈 의사소통 표현 고르기 (나성중3 축하·유감·빈도·제안, 2026-09-19)
   items[{ctx, options[5], answer}] · ctx 안의 "____" 한 곳이 빈칸. 선택지는 한 줄로 흘려 쓴다 */
TYPES.dialog_choice5 = {
  n: p => p.items.length,
  words: p => [],
  check(p, L) {
    p.items.forEach((x, i) => {
      if ((x.ctx.match(/_{4,}/g) || []).length !== 1) fail(L, `${i + 1}번 빈칸이 한 곳이 아님`);
      if (x.options.length !== 5 || new Set(x.options).size !== 5) fail(L, `${i + 1}번 선택지 오류`);
      if (!(x.answer >= 0 && x.answer <= 4)) fail(L, `${i + 1}번 정답 번호 오류`);
    });
    const a = p.items.map(x => x.answer);
    let run = 1, mx = 1;
    for (let i = 1; i < a.length; i++) { run = (a[i] === a[i - 1] + 1 || a[i] === a[i - 1]) ? run + 1 : 1; mx = Math.max(mx, run); }
    if (mx >= 3) fail(L, "정답이 연속 패턴(" + mx + "개)");
    const cnt = {}; a.forEach(v => cnt[v] = (cnt[v] || 0) + 1);
    const v = Object.values(cnt);
    if (a.length >= 5 && (Object.keys(cnt).length !== 5 || Math.max(...v) - Math.min(...v) > 1))
      fail(L, "정답 번호 편중: " + JSON.stringify(cnt));
  },
  render(p, start, ans) {
    const out = [];
    p.items.forEach((x, i) => {
      const [pre, post] = x.ctx.split(/_{4,}/);
      out.push(new Paragraph({ spacing: { before: i === 0 ? 110 : (p.gap || 200), after: 40 }, indent: { left: 340, hanging: 340 },
        children: [T(String(start + i) + ".  ", { size: 18 }), T(pre, { size: 18 }),
                   T("                    ", { size: 18, u: true }), T(post, { size: 18 })] }));
      out.push(new Paragraph({ spacing: { before: 0, after: 60, line: 250 }, indent: { left: 340 }, children:
        x.options.flatMap((o, j) => { const hit = ans && j === x.answer;
          // 선택지 하나는 줄 중간에서 끊기지 않게 — 안쪽 공백을 줄바꿈 없는 공백으로
          return [T(CIRC[j] + " " + o.replace(/ /g, " "), { size: 17, bold: hit, color: hit ? RED : "000000" }),
                  T("     ", { size: 17 })]; }) }));
    });
    return out;
  },
};

/* 있는 대로 고르기 — 표제어의 유의어/반의어를 6개 중 모두 (한솔고 C) */
TYPES.select_all = {
  n: p => p.items.length,
  words: p => p.items.map(x => x.word),
  check(p, L) {
    p.items.forEach(x => {
      if (x.options.length !== 6 || new Set(x.options).size !== 6) fail(L, "선택지 오류: " + x.word);
      const lx = LEX[x.word];
      if (Object.keys(LEX).length && !lx) { fail(L, "단어장에 없음: " + x.word); return; }
      if (lx) {
        const pool = x.type === "유의어" ? lx.syn : lx.ant;
        x.answers.forEach(i => { if (!pool.includes(x.options[i])) fail(L, `정답이 단어장 ${x.type}와 불일치: ${x.word} → ${x.options[i]}`); });
        x.options.forEach((o, i) => { if (!x.answers.includes(i) && pool.includes(o)) fail(L, `정답 누락: ${x.word} → ${o}`); });
      }
    });
    const by = {}; p.items.forEach(x => (by[x.type] = by[x.type] || []).push(x.answers.join(",")));
    Object.entries(by).forEach(([t, arr]) => { if (arr.length > 1 && new Set(arr).size === 1) fail(L, `${t} 문항 정답 위치가 전부 같음`); });
    if (new Set(p.items.map(x => x.answers.join(","))).size < p.items.length - 2) fail(L, "정답 조합이 지나치게 반복됨");
  },
  render(p, start, ans) {
    const out = [];
    p.items.forEach((x, i) => {
      out.push(new Paragraph({ spacing: { before: i === 0 ? 110 : (p.gap || 600), after: 60 }, children: [
        T(String(start + i) + ".  ", { size: 18 }), T(x.word, { size: 19, bold: true }), T("  (" + x.m + ")", { size: 16, color: "707070" }),
        T("  의  ", { size: 17 }), tag(x.type), T(" 를 있는 대로 고르시오.", { size: 17 })] }));
      const wl = CONTENT - 460 - 1500;
      out.push(new Table({ columnWidths: [460, wl, 1500], width: { size: CONTENT, type: WidthType.DXA },
        rows: [new TableRow({ children: [
          C_([P_([T("")])], 460, noB, { m: 245 }),
          C_([P_(x.options.flatMap((o, j) => { const hit = ans && x.answers.includes(j);
            return [T(CIR6[j] + " ", { size: 18, bold: hit, color: hit ? RED : "000000" }),
                    T(o + "      ", { size: 18, bold: hit, color: hit ? RED : "000000" })]; }))], wl, noB, { m: 245 }),
          ans ? C_([P_([T(x.answers.map(j => CIR6[j]).join(", "), { size: 18, bold: true, color: RED })])], 1500, noB, { m: 60 })
              : C_([P_([T("")])], 1500, ul, { m: 60 })] })] }));
    });
    return out;
  },
};

/* 다의어 — 밑줄 친 단어의 뜻을 번호 상자에서 (한솔고 D) */
TYPES.polysemy = {
  n: p => p.items.length,
  words: p => [...new Set(p.items.map(x => (x.lemma || x.word).toLowerCase()))],
  check(p, L) {
    const syms = p.box.map(x => x[0]);
    if (new Set(p.items.map(x => x.answer)).size !== p.items.length) fail(L, "정답 중복");
    p.items.forEach(x => { if (!syms.includes(x.answer)) fail(L, "정답 기호가 상자에 없음: " + x.answer); });
    const idx = p.items.map(x => syms.indexOf(x.answer));
    if (idx.length > 2 && idx.every((v, i) => i === 0 || v > idx[i - 1])) fail(L, "정답이 상자 번호 순서대로 나열됨");
    let run = 1, mx = 1;
    for (let i = 1; i < idx.length; i++) { run = idx[i] === idx[i - 1] + 1 ? run + 1 : 1; mx = Math.max(mx, run); }
    if (mx >= 3) fail(L, "정답이 연속 번호 " + mx + "개");
    const lem = x => (x.lemma || x.word).toLowerCase();
    for (let i = 1; i < p.items.length; i++) if (lem(p.items[i]) === lem(p.items[i - 1])) fail(L, "같은 단어가 연달아 배치됨: " + p.items[i].word);
  },
  render(p, start, ans) {
    if (NS) {   // build_def.js multi()
      const qw = 8300, aw = CONTENT - qw, m = p.m;
      const rows = p.items.map((x, i) => new TableRow({ children: [
        C_([P_([T(String(start + i) + ".  ", { size: 17 }), T(x.pre, { size: 18 }),
          new TextRun({ text: x.word, font: KR, size: 18, bold: true, underline: {} }), T(x.post, { size: 18 })],
          { ind: { left: 320, hanging: 320 } })], qw, noB, { m }),
        C_([P_([T("(     ", { size: 18 }), ans ? T(x.answer, { size: 18, bold: true, color: RED }) : T("      ", { size: 18 }), T("     )", { size: 18 })],
          { align: AlignmentType.RIGHT })], aw, noB, { m })] }));
      return [boxNS(p.box, p.box_per_line || 3), spacer(),
        new Table({ columnWidths: [qw, aw], width: { size: CONTENT, type: WidthType.DXA }, rows })];
    }
    const per = p.box_per_line || 4, lines = [];
    for (let i = 0; i < p.box.length; i += per) lines.push(p.box.slice(i, i + per).join("      "));
    const rows = p.items.map((x, i) => new TableRow({ children: [
      C_([P_([T(String(start + i) + ".  ", { size: 18 }), T(x.pre, { size: 18 }), T(x.word, { size: 18, bold: true, u: true }), T(x.post, { size: 18 })],
        { ind: { left: 320, hanging: 320 } })], 8400, noB, { va: VerticalAlign.TOP, m: p.m || 420 }),
      C_([P_([T("(     ", { size: 18 }), ans ? T(x.answer, { size: 18, bold: true, color: RED }) : T("        ", { size: 18 }), T("     )", { size: 18 })],
        { align: AlignmentType.RIGHT })], 1706, noB, { va: VerticalAlign.TOP, m: p.m || 420 })] }));
    return [boxLines(lines), P_([T("", { size: 8 })], { a: 70 }),
      new Table({ columnWidths: [8400, 1706], width: { size: CONTENT, type: WidthType.DXA }, rows })];
  },
};

/* 유의어 — 〈보기〉에서 골라 쓰기 (세종예고2 B) */
TYPES.syn_pick = {
  n: p => p.items.length,
  words: p => [...p.items.map(x => x.word), ...p.box],
  check(p, L) {
    p.items.forEach(x => {
      if (!p.box.includes(x.answer)) fail(L, "정답이 보기에 없음: " + x.answer);
      const lx = LEX[x.word];
      if (Object.keys(LEX).length && (!lx || !lx.syn.includes(x.answer))) fail(L, `정답이 단어장 유의어가 아님: ${x.word} → ${x.answer}`);
      if (!x.m) fail(L, "뜻 없음: " + x.word);
    });
    if (new Set(p.items.map(x => x.answer)).size !== p.items.length) fail(L, "정답 중복");
    if (new Set(p.box).size !== p.box.length) fail(L, "보기 중복");
    const used = new Set(p.items.map(x => x.answer));
    p.box.filter(b => !used.has(b)).forEach(d => p.items.forEach(x => {
      if (LEX[x.word] && LEX[x.word].syn.includes(d)) fail(L, `오답 보기가 ${x.word}의 유의어: ${d}`); }));
  },
  render(p, start, ans) {
    const wn = 460, we = 3500, wh = 420, wa = CONTENT - wn - we - wh, m = p.m || 150;
    const rows = p.items.map((x, i) => new TableRow({ children: [
      C_([P_([T(String(start + i) + ".", { size: 18 })])], wn, noB, { m }),
      C_([P_([T(x.word, { size: 19, bold: true }), T("  (" + x.m + ")", { size: 15, color: "707070" })])], we, noB, { m }),
      C_([P_([T("=", { size: 18 })])], wh, noB, { m }),
      ans ? C_([P_([T(x.answer, { size: 18, bold: true, color: RED })])], wa, noB, { m }) : C_([P_([T("")])], wa, ul, { m })] }));
    return [boxWords(p.box, p.box_per_line || 5), spacer(),
      new Table({ columnWidths: [wn, we, wh, wa], width: { size: CONTENT, type: WidthType.DXA }, rows })];
  },
};

/* 반의어 5지선다 (세종예고2 C) */
TYPES.ant_choice5 = {
  n: p => p.items.length,
  words: p => [...p.items.map(x => x.word), ...p.items.flatMap(x => x.options)],
  check(p, L) {
    p.items.forEach(x => {
      if (x.options.length !== 5 || new Set(x.options).size !== 5) fail(L, "보기 오류: " + x.word);
      const lx = LEX[x.word];
      if (Object.keys(LEX).length) {
        if (!lx || !lx.ant.includes(x.options[x.answer])) fail(L, `정답이 단어장 반의어가 아님: ${x.word} → ${x.options[x.answer]}`);
        else x.options.forEach((o, i) => { if (i !== x.answer && lx.ant.includes(o)) fail(L, `복수정답: ${x.word} → ${o}`); });
      }
    });
    const a = p.items.map(x => x.answer);
    let run = 1, mx = 1;
    for (let i = 1; i < a.length; i++) { run = a[i] === a[i - 1] ? run + 1 : 1; mx = Math.max(mx, run); }
    if (mx >= 3) fail(L, "정답이 같은 번호로 " + mx + "개 연속");
    if (a.length > 2 && (a.every((v, i) => i === 0 || v > a[i - 1]) || a.every((v, i) => i === 0 || v < a[i - 1]))) fail(L, "정답이 순서대로 나열됨");
    const cnt = {}; a.forEach(v => cnt[v] = (cnt[v] || 0) + 1);
    if (Math.max(...Object.values(cnt)) > Math.ceil(a.length / 2)) fail(L, "정답이 특정 번호에 쏠림: " + JSON.stringify(cnt));
  },
  render(p, start, ans) {
    const out = [];
    p.items.forEach((x, i) => {
      out.push(new Paragraph({ spacing: { before: i === 0 ? 110 : (p.gap || 505), after: 60 }, children: [
        T(String(start + i) + ".  ", { size: 18 }), T(x.word, { size: 19, bold: true }),
        T("  (" + x.m + ")", { size: 16, color: "707070" }), T("  의 반의어로 알맞은 것은?", { size: 18 })] }));
      out.push(new Paragraph({ spacing: { before: 0, after: 0, line: 230 }, indent: { left: 440 }, children:
        x.options.flatMap((o, j) => { const hit = ans && j === x.answer;
          return [T(CIRC[j] + " ", { size: 18, bold: hit, color: hit ? RED : "000000" }),
                  T(o + "     ", { size: 18, bold: hit, color: hit ? RED : "000000" })]; }) }));
    });
    return out;
  },
};

/* 문맥 O·X + 고쳐 쓰기 (세종예고2 D) */
TYPES.context_ox = {
  n: p => p.items.length,
  words: p => [...p.items.map(x => x.word), ...p.box],
  check(p, L) {
    const o = p.items.filter(x => x.ok).length;
    if (o === 0 || o === p.items.length) fail(L, "판정이 한쪽으로 쏠림");
    p.items.forEach(x => {
      if (x.ok && x.fix) fail(L, "적절한 문항에 고칠 말이 있음: " + x.word);
      if (!x.ok) {
        if (!x.fix) fail(L, "부적절 문항에 고칠 말이 없음: " + x.word);
        else if (!p.box.includes(x.fix)) fail(L, "고칠 말이 보기에 없음: " + x.fix);
        else if (Object.keys(LEX).length && !((LEX[x.fix] || {}).ant || []).includes(x.word) && !((LEX[x.word] || {}).ant || []).includes(x.fix))
          fail(L, `고칠 말이 반의어 관계가 아님: ${x.word} ↔ ${x.fix}`);
      }
    });
    const pat = p.items.map(x => x.ok ? "O" : "X").join("");
    if (pat.length >= 4 && /^(OX)+O?$|^(XO)+X?$/.test(pat)) fail(L, "판정이 교대 패턴: " + pat);
  },
  render(p, start, ans) {
    const wn = 520, ws = 6900, wo = 900, wf = CONTENT - wn - ws - wo;
    const o = { va: VerticalAlign.BOTTOM, m: p.m || 560, mb: p.mb || 45 };
    const rows = p.items.map((x, i) => new TableRow({ children: [
      C_([P_([T(String(start + i) + ".", { size: 18 })])], wn, noB, o),
      C_([P_([T(x.pre, { size: 18 }), T(x.word, { size: 18, bold: true, u: true }), T(x.post, { size: 18 })])], ws, noB, o),
      C_([P_([T("( ", { size: 18 }), ans ? T(x.ok ? "O" : "X", { size: 18, bold: true, color: RED }) : T("    ", { size: 18 }), T(" )", { size: 18 })])], wo, noB, o),
      ans ? C_([P_([T(x.fix || "—", { size: 17, bold: !!x.fix, color: x.fix ? RED : "B0B0B0" })])], wf, noB, o)
          : C_([P_([T("")])], wf, ul, o)] }));
    return [boxWords(p.box, p.box_per_line || 6), spacer(),
      new Table({ columnWidths: [wn, ws, wo, wf], width: { size: CONTENT, type: WidthType.DXA }, rows })];
  },
};

/* 문장 빈칸 — 〈보기〉에서 골라 알맞은 형태로 쓰기 (세종예고1 B) */
TYPES.fill_blank = {
  n: p => p.items.length,
  words: p => p.box,
  check(p, L) {
    p.items.forEach(x => {
      if (!p.box.includes(x.base)) fail(L, "정답이 보기에 없음: " + x.base);
      if (!/[.?!]$/.test(x.post.trim())) fail(L, "문장 마침표 누락: " + x.post);
      if (!x.form.toLowerCase().startsWith(x.base.slice(0, 4).toLowerCase())) fail(L, `변형형이 보기 단어와 다름: ${x.base} → ${x.form}`);
    });
    if (new Set(p.box).size !== p.box.length) fail(L, "보기 중복");
    if (p.reuse_box) {   // 같은 보기를 여러 번 쓰는 구별 문항 (worth / value / valuable)
      const used = new Set(p.items.map(x => x.base));
      p.box.forEach(b => { if (!used.has(b)) fail(L, "쓰이지 않은 보기: " + b); });
      let run = 1, mx = 1;
      for (let i = 1; i < p.items.length; i++) { run = p.items[i].base === p.items[i - 1].base ? run + 1 : 1; mx = Math.max(mx, run); }
      if (mx >= 3) fail(L, "같은 정답 " + mx + "개 연속");
    } else {
      if (new Set(p.items.map(x => x.base)).size !== p.items.length) fail(L, "정답 중복");
      if (p.box.length <= p.items.length) fail(L, "보기가 정답 수보다 많아야 한다 (소거법 차단)");
    }
  },
  render(p, start, ans) {
    const m = p.m || 150;
    if (NS) {   // build_def.js fillIn()
      const rows = p.items.map((x, i) => {
        const runs = [T(String(start + i) + ".  ", { size: 17 }), T(x.pre + " ", { size: 18 })];
        runs.push(ans ? T(x.form, { size: 18, bold: true, color: RED, u: true }) : T("                          ", { size: 18, u: true }));
        runs.push(T(" " + x.post, { size: 18 }));
        return new TableRow({ children: [C_([P_(runs, { ind: { left: 340, hanging: 340 } })], CONTENT, noB, { m })] });
      });
      return [boxNS(p.box, p.box_per_line || 3), spacer(),
        new Table({ columnWidths: [CONTENT], width: { size: CONTENT, type: WidthType.DXA }, rows })];
    }
    const rows = p.items.map((x, i) => {
      const runs = [T(String(start + i) + ".  ", { size: 18 }), T(x.pre + " ", { size: 18 })];
      runs.push(ans ? T(x.form, { size: 18, bold: true, color: RED, u: true }) : T("                          ", { size: 18, u: true }));
      runs.push(T(/^[.,!?;:]/.test(x.post) ? x.post : " " + x.post, { size: 18 }));
      return new TableRow({ children: [C_([P_(runs, { ind: { left: 360, hanging: 360 } })], CONTENT, noB, { m, va: VerticalAlign.TOP })] });
    });
    return [boxWords(p.box, p.box_per_line || 4), spacer(),
      new Table({ columnWidths: [CONTENT], width: { size: CONTENT, type: WidthType.DXA }, rows })];
  },
};

/* 영영풀이 → 〈보기〉에서 단어 골라 쓰기 (세종예고1 defTable 판형. 나성중3 A·E파트용) */
TYPES.definition = {
  n: p => p.items.length,
  words: p => p.box,
  check(p, L) {
    p.items.forEach(x => {
      if (!p.box.includes(x.w)) fail(L, "정답이 보기에 없음: " + x.w);
      if (!x.def || !x.def.trim()) fail(L, "영영풀이 없음: " + x.w);
      if (x.def && x.def.toLowerCase().split(/\W+/).includes(x.w.toLowerCase())) fail(L, `영영풀이에 정답 단어가 그대로 있음: ${x.w}`);
    });
    if (new Set(p.items.map(x => x.w)).size !== p.items.length) fail(L, "정답 중복");
    if (new Set(p.box).size !== p.box.length) fail(L, "보기 중복");
    if (p.box.length <= p.items.length) fail(L, "보기가 정답 수보다 많아야 한다 (소거법 차단)");
  },
  render(p, start, ans) {
    if (NS) {   // build_def.js defList()
      const nw = 430, aw = 2500, dw = CONTENT - nw - aw, m = p.m, o = { m, mb: m + 30 };
      const rows = p.items.map((x, i) => new TableRow({ children: [
        C_([P_([T(String(start + i) + ".", { size: 17 })])], nw, noB, o),
        ans ? C_([P_([T(x.w, { size: 18, bold: true, color: RED })])], aw, noB, o) : C_([P_([T("")])], aw, ul, o),
        C_([P_([T(" :  " + x.def, { size: 18 })], { ind: { left: 250, hanging: 250 } })], dw, noB, o)] }));
      return [boxNS(p.box, p.box_per_line || 6), spacer(),
        new Table({ columnWidths: [nw, aw, dw], width: { size: CONTENT, type: WidthType.DXA }, rows })];
    }
    const wn = 460, wa = 2250, wd = CONTENT - wn - wa, m = p.m || 150;
    const rows = p.items.map((x, i) => new TableRow({ children: [
      C_([P_([T(String(start + i) + ".", { size: 18 })])], wn, noB, { m, va: VerticalAlign.TOP }),
      ans ? C_([P_([T(x.w, { size: 18, bold: true, color: RED })])], wa, noB, { m, mb: m + 30 })
          : C_([P_([T("")])], wa, ul, { m, mb: m + 30 }),
      C_([P_([T(" :  " + x.def, { size: 17 })], { ind: { left: 250, hanging: 250 } })], wd, noB, { m, va: VerticalAlign.TOP })] }));
    return [boxWords(p.box, p.box_per_line || 6), spacer(),
      new Table({ columnWidths: [wn, wa, wd], width: { size: CONTENT, type: WidthType.DXA }, rows })];
  },
};

/* 제시어를 보고 답 쓰기 — 접두사·접미사 붙이기, in-/im- 반의어 등 (나성중3 B·C·D파트용) */
TYPES.word_write = {
  n: p => p.items.length,
  words: p => p.items.map(x => x.answer),
  check(p, L) {
    p.items.forEach(x => {
      if (!x.prompt || !x.answer) fail(L, "제시어·정답 없음");
      if (p.must_contain && !x.answer.toLowerCase().includes(x.base || "")) fail(L, `정답에 원래 단어가 없음: ${x.answer}`);
    });
    if (new Set(p.items.map(x => x.answer)).size !== p.items.length) fail(L, "정답 중복");
  },
  render(p, start, ans) {
    const [wn, wp, wa] = [460, 5200, CONTENT - 460 - 5200], m = p.m || 150;
    const rows = p.items.map((x, i) => new TableRow({ children: [
      C_([P_([T(String(start + i) + ".", { size: 18 })])], wn, noB, { m }),
      C_([P_([T(x.prompt, { size: 18 }), ...(x.hint ? [T("  (" + x.hint + ")", { size: 15, color: "707070" })] : [])])], wp, noB, { m }),
      ans ? C_([P_([T(x.answer, { size: 18, bold: true, color: RED })])], wa, noB, { m }) : C_([P_([T("")])], wa, ul, { m })] }));
    const out = [];
    if (p.box) out.push(boxWords(p.box, p.box_per_line || 6), spacer());
    out.push(new Table({ columnWidths: [wn, wp, wa], width: { size: CONTENT, type: WidthType.DXA }, rows }));
    return out;
  },
};

/* ───────── 데이터 점검 ───────── */
let total = 0;
const starts = [];
D.parts.forEach((p, k) => {
  const ty = TYPES[p.type];
  const L = `${p.letter || k + 1}파트`;
  if (!ty) { fail("설정", `${L} 모르는 유형 '${p.type}' (있는 유형: ${Object.keys(TYPES).join(", ")})`); starts.push(0); return; }
  if ((PROF.excluded_types || []).includes(p.type)) fail("학교규격", `${L} '${p.type}' 는 ${D.school} 에서 내지 않는 유형`);
  starts.push(total + 1);
  total += ty.n(p);
  ty.check(p, L);
});
if (D.total !== undefined && total !== D.total) fail("규격", `총 문항 ${total} (data total ${D.total})`);
if (PROF.total && !D.total_override && !PROF.total.includes(total)) fail("규격", `총 문항 ${total} — ${D.school} 규격 ${PROF.total.join("/")}`);
{ // 파트 간 표제어·보기 중복 — 서로 힌트가 된다
  const seen = new Map(), dup = [];
  D.parts.forEach((p, k) => { const ty = TYPES[p.type]; if (!ty) return;
    const own = new Set();
    ty.words(p).forEach(w => { const key = w.toLowerCase(); if (own.has(key)) return; own.add(key);
      if (seen.has(key)) dup.push(`${w} (${seen.get(key)}·${p.letter})`); else seen.set(key, p.letter); }); });
  if (dup.length && !D.allow_cross_part_duplicates) fail("중복", "파트 간 중복: " + dup.join(", "));
}
/* A/B형 대조 — compare_with 에 A형 data.json 을 주면, 같은 파트 같은 자리에 같은 문항이 오면 막는다 */
function slotKeys(p) {
  const pick = {
    meaning: x => x.w, choice5_sentence: x => (x.lemma || x.word), select_all: x => x.word,
    polysemy: x => (x.lemma || x.word) + "|" + x.answer, syn_pick: x => x.word, ant_choice5: x => x.word,
    context_ox: x => x.word, fill_blank: x => x.base + "|" + x.post, definition: x => x.w, word_write: x => x.answer,
  }[p.type];
  if (!pick) return [];
  const items = p.type === "meaning" && p.order ? p.order.map(i => p.items[i]) : p.items;
  return items.map(x => String(pick(x)).toLowerCase());
}
if (D.compare_with) {
  const other = path.resolve(path.dirname(dataPath), D.compare_with);
  if (!fs.existsSync(other)) fail("A/B형", "compare_with 파일이 없음: " + other);
  else {
    const A = JSON.parse(fs.readFileSync(other, "utf8"));
    let same = 0, overlap = 0;
    D.parts.forEach(p => {
      const q = A.parts.find(x => x.letter === p.letter);
      if (!q) return;
      const kb = slotKeys(p), ka = slotKeys(q);
      if (p.type === q.type) kb.forEach((k, i) => { if (ka[i] === k) { same++; fail("A/B형", `${p.letter}파트 ${i + 1}번째 자리가 A형과 같은 문항: ${k.split("|")[0]}`); } });
      const sa = new Set(ka); kb.forEach(k => { if (sa.has(k)) overlap++; });
    });
    info.push(`A형(${path.basename(other)})과 겹치는 문항 ${overlap}개 · 같은 자리 ${same}개`);
  }
}
const texts = [D.head1, D.head2, ...D.parts.map(p => (p.title || "") + (p.sub || ""))].join(" ");
TEACHER.forEach(w => { if (texts.includes(w)) fail("멘트", `머리말·파트 제목에 '${w}'`); });
if (/학교\s*_|반\s*_{2,}|번호\s*_/.test(texts)) fail("규격", "학교·반·번호 칸 금지");
if (/자리/.test(texts.replace(/(동사|주어|목적어|보어|부사|형용사|명사) ?자리/g, ""))) fail("표현", "'자리' 표현");

function report() {
  console.log(`── ${D.name} · 단어시험지 점검`);
  info.forEach(i => console.log("  참고: " + i));
  if (bad.length) { console.log(`  결함 ${bad.length}건`); bad.forEach(b => console.log("    " + b)); }
  else console.log("  결함 0");
}
if (bad.length) { report(); console.log("\n점검 실패 — PDF를 내보내지 않았다."); process.exit(1); }

/* ───────── 문서 ───────── */
function body(ans) {
  const c = ans ? RED : ACC;
  const out = NS
    ? [P_([T(D.head1, { size: 17, color: "808080" })], { a: 20 }),
       new Paragraph({ spacing: { after: 60 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: c } },
         children: [T(D.head2 + (ans ? "  정답지" : ""), { size: 29, bold: true })] })]
    : [P_([T(D.head1, { size: 17, color: "808080" })]),
       new Paragraph({ spacing: { before: 20, after: 60 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: c } },
         children: [T(D.head2, { size: 27, bold: true }), T(ans ? "   정답지" : "", { size: 22, bold: true, color: c })] })];
  if (!ans) out.push(NS ? P_([T("", { size: 8 })], { a: 40 }) : P_([T("", { size: 8 })]), new Table({ columnWidths: [6600, 3506], width: { size: CONTENT, type: WidthType.DXA },
    rows: [new TableRow({ children: [
      C_([P_([T("이름 ______________________", { size: 19 })])], 6600, noB, { m: 30 }),
      C_([P_([T("점수            /  " + total, { size: 19 })], { align: AlignmentType.RIGHT })], 3506, noB, { m: 30 })] })] }));
  D.parts.forEach((p, k) => {
    const n = TYPES[p.type].n(p);
    const range = `[${starts[k]}~${starts[k] + n - 1}]`;
    out.push(secH(p.letter, p.title, range + (p.sub ? "  " + p.sub : "")));
    out.push(...TYPES[p.type].render(p, starts[k], ans));
    if (p.page_break_after) out.push(pageBreak());
  });
  return out;
}
const margin = D.page_margin || (NS ? { top: 800, right: 900, bottom: 650, left: 900 } : { top: 820, right: 900, bottom: 620, left: 900 });
const pp = { page: { size: { width: 11906, height: 16838 }, margin } };

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "vocab_"));
  try {
    const names = [D.name, D.name + ANS_SUFFIX];
    for (const [i, nm] of names.entries()) {
      const buf = await Packer.toBuffer(new Document({ sections: [{ properties: pp, children: body(i === 1) }] }));
      fs.writeFileSync(path.join(tmp, nm + ".docx"), buf);
    }
    execFileSync(SOFFICE, ["--headless", "--convert-to", "pdf", "--outdir", tmp,
      ...names.map(n => path.join(tmp, n + ".docx"))], { stdio: "ignore" });
    for (const nm of names) if (!fs.existsSync(path.join(tmp, nm + ".pdf"))) fail("PDF", nm + ".pdf 변환 실패");
    if (!bad.length) {
      // PDF 실물 — Python pymupdf 로 텍스트를 뽑아 본다
      const py = `import sys,json,pymupdf
r=[]
for f in sys.argv[1:]:
    d=pymupdf.open(f); r.append({"pages":len(d),"text":"\\n".join(p.get_text() for p in d)})
print(json.dumps(r,ensure_ascii=False))`;
      const pyf = path.join(tmp, "t.py"); fs.writeFileSync(pyf, py);
      const res = JSON.parse(execFileSync("py", ["-X", "utf8", pyf, ...names.map(n => path.join(tmp, n + ".pdf"))], { encoding: "utf8" }));
      const [stu, key] = res;
      if (!stu.text.includes("이름")) fail("PDF", "시험지에 이름 칸 없음");
      if (!/점수/.test(stu.text)) fail("PDF", "시험지에 점수 칸 없음");
      if (/정답지/.test(stu.text)) fail("PDF", "시험지에 '정답지' 표시");
      TEACHER.forEach(w => { if (stu.text.includes(w)) fail("멘트", `시험지에 '${w}'`); });
      for (let n = 1; n <= total; n++) {
        if (!new RegExp(`(^|\\s)${n}\\.`).test(stu.text)) fail("PDF", `시험지에 ${n}번 없음`);
        if (!new RegExp(`(^|\\s)${n}\\.`).test(key.text)) fail("PDF", `정답지에 ${n}번 없음`);
      }
      if (stu.pages !== key.pages) fail("PDF", `시험지 ${stu.pages}쪽 · 정답지 ${key.pages}쪽 — 같은 배치여야 대조 채점이 된다`);
      if (D.max_pages && stu.pages > D.max_pages) fail("PDF", `${stu.pages}쪽 — ${D.max_pages}쪽 넘음`);
      info.push(`시험지 ${stu.pages}쪽 · 정답지 ${key.pages}쪽 · ${total}문항 (${D.parts.map(p => p.letter + TYPES[p.type].n(p)).join(" ")})`);
    }
    if (bad.length) { report(); console.log("\n점검 실패 — PDF를 내보내지 않았다."); process.exit(1); }
    fs.mkdirSync(outDir, { recursive: true });
    for (const nm of names) {
      fs.copyFileSync(path.join(tmp, nm + ".pdf"), path.join(outDir, nm + ".pdf"));
      console.log("저장 " + path.join(outDir, nm + ".pdf"));
    }
    report();
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})();
