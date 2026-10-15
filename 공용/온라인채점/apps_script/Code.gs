/**
 * 카이젠 온라인 답 입력 · 채점
 * 구글 시트에 붙은(확장 프로그램 → Apps Script) 스크립트다. 설치는 ../README.md.
 *
 * 링크: <웹앱 URL>?t=<시험ID>
 * 채점키: 드라이브에서 "<시험ID>_채점키.json" 을 파일명으로 찾는다 (공용/온라인채점/채점키/ 가 동기화된 것).
 * 정답은 서버에만 있다. 학생 브라우저로는 문항 번호·배점·입력 방식·학생 명단만 간다.
 *
 * 문항 mode: choice(①~⑤) · symbol(ⓐ~ 기호 고르기, 자동 채점) · auto(단어 쓰기, 인정 답 목록으로 자동 채점 — 칸별 부분 점수)
 *           · text(단어 쓰기) · essay(서술형)
 * text·essay 는 채점하지 않고 답만 기록한다. 선생님이 문항별 탭 '득점' 칸에 점수를 넣으면 제출 탭 '최종 점수'가 채워진다.
 * 제출 탭 '최종 점수'는 문항별 탭 '득점' 합계 수식이다 — 자동 채점 결과도 득점 칸을 고치면 최종 점수가 따라 바뀐다.
 */

const TZ = 'Asia/Seoul';
const SHEET_SUBMIT = '제출';
const SHEET_ITEMS = '문항별';
const HEAD_SUBMIT = ['제출 시각', '시험', '이름', '시도', '점수', '만점', '맞은 수', '문항 수', '틀린 번호', '입력한 답', '채점 대기', '최종 점수'];
const HEAD_ITEMS = ['제출 시각', '시험', '이름', '시도', '번호', '유형', '출처', '학생 답', '정답', '정오', '배점', '득점', '찍음'];
const SHEET_ESSAY = '서술형 채점', SHEET_STAT = '현황', SHEET_RATE = '문항 정답률', SHEET_WEAK = '학생 약점', SHEET_ARCH = '보관';

function doGet(e) {
  const id = (e && e.parameter && e.parameter.t) || '';
  const key = id ? loadKey_(id) : null;
  const t = HtmlService.createTemplateFromFile('Index');
  t.meta = JSON.stringify(key ? publicMeta_(key) : { error: id ? '시험을 찾지 못했다: ' + id : '링크에 시험 ID가 없다' });
  return t.evaluate()
    .setTitle(key ? key.title : '답 입력')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/** 시험용 이름 (2026-09-30 선생님 요청): 모든 시험 명단 끝에 붙는다. 몇 번이든 다시 낼 수 있고 알림 메일은 가지 않는다.
 *  시트에는 기록된다 — 분석할 때 이름 TEST 는 뺀다 */
const TEST_NAME = 'TEST';
function students_(key) { return key.students.indexOf(TEST_NAME) >= 0 ? key.students : key.students.concat([TEST_NAME]); }

function mode_(it) { return it.mode || 'choice'; }
function label_(it) { return it.label || String(it.n); }
function isAuto_(it) { return mode_(it) === 'choice' || mode_(it) === 'symbol' || mode_(it) === 'auto'; }

/** 학생 화면에 보내는 것: 정답 빼고 전부 (auto 문항은 칸 이름만 — 인정 답 목록은 보내지 않는다) */
function publicMeta_(key) {
  return {
    id: key.id, title: key.title, students: students_(key), choices: key.choices, total: key.total,
    survey: !!key.survey, intro: key.intro || null,
    items: key.items.map(function (it) {
      return { n: it.n, label: label_(it), pt: it.pt, mode: mode_(it), page: it.page || null,
               symbols: it.symbols || null, multi: !!it.multi, lines: it.lines || 1,
               parts: it.parts ? it.parts.map(function (p) { return { label: p.label }; }) : null,
               q: it.q || null, sub: it.sub || null, opts: it.opts || null, optional: !!it.optional,
               sec: it.sec || null, secSub: it.secSub || null };
    })
  };
}

/** 자동 채점 비교용 — 채점키.py 의 norm_text 와 같아야 한다: 소문자 · 굽은 따옴표 → ' · 끝 문장부호 제거 · 공백 하나로 */
function normText_(s) {
  return String(s == null ? '' : s).toLowerCase().replace(/[‘’]/g, "'").replace(/ /g, ' ')
    .replace(/\s+/g, ' ').trim().replace(/[.,;:!?]+$/, '').trim();
}

/** 한 칸에 적힌 옛 답을 칸 수만큼 나눈다. 못 나누면 null.
 *  ① "(1) who is (2) …" · "1. who is 2. …" 처럼 번호가 있으면 번호로 ② 줄을 바꿔 썼으면 줄로
 *  ③ 번호 없이 한 줄로 이어 썼으면("who is which provides whatever she") 칸마다 정해진 단어 수로 끊는다
 *     — 칸의 인정 답이 모두 같은 단어 수일 때만 (예: 각 2단어 조건) */
function splitParts_(s, parts) {
  const n = parts.length;
  s = String(s || '').trim();
  if (n === 1) return [s];
  const re = /(?:^|\s)\(?\s*([1-9])\s*[).]/g, marks = [];   // (1) · 1) · 1. (2026-09-29 학생M "1. tension 2. splits …")
  let m;
  while ((m = re.exec(s))) marks.push({ k: Number(m[1]), at: m.index, end: re.lastIndex });
  if (marks.length === n && marks.every(function (x, i) { return x.k === i + 1; })) {
    return marks.map(function (x, i) { return s.slice(x.end, i + 1 < n ? marks[i + 1].at : s.length).replace(/[\/,]\s*$/, '').trim(); });
  }
  const lines = s.split(/\n+/).map(function (x) { return x.trim(); }).filter(Boolean);
  if (lines.length === n) return lines.map(function (x) { return x.replace(/^\(?[1-9][.)]\s*/, ''); });
  const counts = parts.map(function (p) {
    const c = p.accept.map(function (a) { return a.split(' ').length; });
    return c.every(function (x) { return x === c[0]; }) ? c[0] : 0;
  });
  const words = s.split(/[\s,\/]+/).filter(Boolean);
  if (counts.every(Boolean) && words.length === counts.reduce(function (a, b) { return a + b; }, 0)) {
    let at = 0;
    return counts.map(function (c) { const w = words.slice(at, at + c).join(' '); at += c; return w; });
  }
  return null;
}

/** auto 문항 채점: 칸마다 인정 답 목록과 비교해 부분 점수. 답은 칸별 배열(새 화면) 또는 한 줄 글(옛 제출).
 *  반환 { a: 시트에 적을 답, got: 득점, full: 만점 여부 } · 칸을 못 나누면 null */
function gradeAuto_(it, v) {
  const n = it.parts.length;
  const arr = Array.isArray(v) ? v.map(function (x) { return String(x || '').slice(0, 300); }) : splitParts_(v, it.parts);
  if (!arr) return null;
  let got = 0;
  it.parts.forEach(function (p, j) {
    const s = normText_(String(arr[j] || '').replace(/^\(?\s*[1-9]\s*\)\s*/, ''));
    if (s && p.accept.indexOf(s) >= 0) got += p.pt;
  });
  got = Math.round(got * 10) / 10;
  const a = n > 1 ? it.parts.map(function (p, j) { return p.label + ' ' + String(arr[j] || '').trim(); }).join(' / ')
                  : String(arr[0] || '').trim();
  return { a: arr.every(function (x) { return !String(x || '').trim(); }) ? '' : a, got: got, full: Math.abs(got - it.pt) < 1e-6 };
}
function mark_(it, ok, got) {   // 문항별 탭 '정오'
  if (ok === null) return '채점 대기';
  if (mode_(it) === 'auto' && !ok && got > 0) return '△';
  return ok ? 'O' : 'X';
}

/** 선택형 정답 판정 — 정답 정정으로 복수 정답(alt)을 인정한 문항은 alt 도 정답 */
function okChoice_(it, a) { return a === Number(it.ans) || (it.alt || []).map(Number).indexOf(a) >= 0; }
function ansText_(it) { return it.alt && it.alt.length ? [it.ans].concat(it.alt).join(',') : it.ans; }

/** fresh: 캐시를 건너뛰고 드라이브에서 다시 읽는다 (재채점) */
function loadKey_(id, fresh) {
  if (!/^[0-9A-Za-z가-힣_\-]+$/.test(id)) return null;
  const cache = CacheService.getScriptCache();
  let s = fresh ? null : cache.get('key:' + id);
  if (!s) {
    const it = DriveApp.searchFiles("title = '" + id + "_채점키.json' and trashed = false");
    let best = null;
    while (it.hasNext()) {
      const f = it.next();
      if (!best || f.getLastUpdated() > best.getLastUpdated()) best = f;
    }
    if (!best) return null;
    s = best.getBlob().getDataAsString('UTF-8');
    cache.put('key:' + id, s, 300);   // 채점키를 고치면 5분 안에 반영된다
  }
  return JSON.parse(s);
}

function sortSymbols_(s) { return String(s || '').replace(/[^ⓐ-ⓩ]/g, '').split('').sort().join(''); }

/** 학생 제출 → 채점 → 시트 기록 → 결과 반환 */
function submit(id, name, answers, guess) {
  const key = loadKey_(id);
  if (!key) throw new Error('시험을 찾지 못했다');
  if (students_(key).indexOf(name) < 0) throw new Error('명단에 없는 이름');
  if (!Array.isArray(answers) || answers.length !== key.items.length) throw new Error('답 개수가 맞지 않는다');
  if (archived_(SpreadsheetApp.getActiveSpreadsheet(), id)) return { closed: true };
  if (key.survey) return submitSurvey_(key, id, name, answers);
  guess = Array.isArray(guess) ? guess : [];

  let score = 0, autoTotal = 0, pendTotal = 0, correct = 0, autoCount = 0;
  const wrong = [], pending = [], fix = [];
  const rows = key.items.map(function (it, i) {
    const m = mode_(it);
    let a, ok = null, got = 0;
    if (m === 'choice') { a = Number(answers[i]) || 0; ok = okChoice_(it, a); }
    else if (m === 'symbol') { a = sortSymbols_(answers[i]); ok = a === it.ans; }
    else if (m === 'auto') {
      const g = gradeAuto_(it, answers[i]);
      if (g) { a = g.a; ok = g.full; got = g.got; }
      else { a = String(answers[i] || '').trim().slice(0, 2000); }   // 칸을 못 나누면 선생님 채점
    }
    else { a = String(answers[i] || '').trim().slice(0, 2000); }
    if (ok === null) { pendTotal += it.pt; pending.push(label_(it)); }
    else {
      if (m !== 'auto') got = ok ? it.pt : 0;
      autoTotal += it.pt; autoCount++; score += got;
      if (ok) correct++; else { wrong.push(label_(it)); fix.push(fix_(it, a)); }
    }
    return { it: it, m: m, a: a, ok: ok, got: got, guess: !!guess[i] && (m === 'choice' || m === 'symbol') };
  });
  const r1 = function (x) { return Math.round(x * 10) / 10; };

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sub = sheet_(ss, SHEET_SUBMIT, HEAD_SUBMIT);
    const itm = sheet_(ss, SHEET_ITEMS, HEAD_ITEMS);

    // 한 학생은 한 시험을 한 번만 낸다 (2026-09-28). 틀린 번호를 보고 답을 바꿔 다시 내며 정답을 찾는 것을 막는다.
    // 이미 낸 기록이 있으면 채점·기록 없이 첫 제출 결과를 다시 보여 준다.
    const isTest = name === TEST_NAME;
    const past = isTest ? null : pastResult_(ss, key, id, name);
    if (past) return past;
    // TEST 는 다시 낼 때마다 시도 번호를 올린다 (최종 점수 수식이 시도로 줄을 가른다)
    const attempt = !isTest || sub.getLastRow() < 2 ? 1 : sub.getRange(2, 2, sub.getLastRow() - 1, 2).getValues()
      .filter(function (r) { return r[0] === id && r[1] === name; }).length + 1;
    const now = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm:ss');

    // 번호 목록·입력한 답은 앞에 ' 를 붙여 글자로 넣는다 — 안 붙이면 시트가 "7, 9, 22" 를 날짜(2007-09-22)로,
    // 숫자만 긴 답(26자리)을 숫자로 바꿔 버린다 (2026-09-28 발견). ' 는 칸에 보이지 않는다.
    const txt = function (s) { return s ? "'" + s : ''; };
    sub.appendRow([now, id, name, attempt, r1(score), key.total, correct, key.items.length, txt(wrong.join(', ')),
      txt(rows.map(function (r) { return r.m === 'choice' ? (r.a || '-') : r.m === 'symbol' ? '[' + (r.a || '-') + ']' : '✎'; }).join('')),
      txt(pending.join(', '))]);
    const row = sub.getLastRow();
    // 최종 점수 = 문항별 탭 득점 합계. 선생님이 서답형 득점을 다 넣으면 합계가 뜨고, 자동 채점 득점을 고쳐도 따라 바뀐다.
    const mm = "문항별!$A:$A,$A" + row + ",문항별!$B:$B,$B" + row + ",문항별!$C:$C,$C" + row + ",문항별!$D:$D,$D" + row;
    sub.getRange(row, 12).setFormula('=IF(COUNTIFS(' + mm + ',문항별!$L:$L,"")>0,"채점 중",SUMIFS(문항별!$L:$L,' + mm + '))');

    itm.getRange(itm.getLastRow() + 1, 1, rows.length, HEAD_ITEMS.length).setValues(rows.map(function (r) {
      return [now, id, name, attempt, label_(r.it), r.it.type, r.it.src, r.a === 0 ? '' : r.a,
        ansText_(r.it), mark_(r.it, r.ok, r.got), r.it.pt, r.ok === null ? '' : r.got, r.guess ? 'V' : ''];
    }));
    SpreadsheetApp.flush();
    var cmp = compare_(ss, id, name, attempt, score, autoTotal, rows);
  } finally {
    lock.releaseLock();
  }

  // 새 제출이면 선생님께 메일 (2026-09-30 요청). 메일이 실패해도 학생 제출은 그대로 끝난다.
  if (name !== TEST_NAME) {
    try { notify_(key, id, name, r1(score), wrong, pending); } catch (err) { Logger.log('메일 실패: ' + err); }
  }

  return { score: r1(score), autoTotal: r1(autoTotal), total: key.total, correct: correct, autoCount: autoCount,
           pending: pending, pendTotal: r1(pendTotal), wrong: key.showWrong ? wrong : null,
           fix: key.showWrong ? fix : null,
           lucky: lucky_(rows.map(function (r) { return { it: r.it, ok: r.ok, guess: r.guess, a: r.a }; })),
           models: key.showModel ? rows.filter(function (r) { return r.ok === null; })
                                       .map(function (r) { return model_(r.it, r.a); }) : null,
           exps: key.showExp ? rows.map(function (r) { return exp_(r.it, r.a, r.ok, r.got, r.guess); }) : null,
           fb: feedback_(rows, score, autoTotal), cmp: cmp };
}

/**
 * 제출 알림 메일 — 받는 사람은 웹 앱 주인(배포할 때 '실행 계정: 나' 로 고른 계정).
 * 끄려면 NOTIFY 를 false 로 바꾸고 새 버전으로 배포한다. 처음 켤 때 메일 보내기 권한 승인이 한 번 더 필요하다.
 */
const NOTIFY = true;
function notify_(key, id, name, score, wrong, pending) {
  if (!NOTIFY) return;
  const to = Session.getEffectiveUser().getEmail();
  if (!to) return;
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const lines = [
    '시험: ' + key.title + ' (' + id + ')',
    '학생: ' + name,
    '점수: ' + score + ' / ' + key.total + (pending.length ? ' (자동 채점분만 — 선생님 채점 대기 ' + pending.join(', ') + ')' : ''),
    '틀린 번호: ' + (wrong.length ? wrong.join(', ') : '없음'),
    '제출 시각: ' + Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'),
    '',
    '시트: ' + ss.getUrl()
  ];
  MailApp.sendEmail(to, '[온라인채점] ' + name + ' · ' + id + ' · ' + score + '점', lines.join('\n'));
}

/** 서답형(단어 쓰기·서술형) 하나: 번호 · 내 답 · 모범답안. showModel 채점키만 (한솔고 — 2026-09-28).
 *  한 번만 제출할 수 있으므로 제출 뒤에 모범답안을 보여 줘도 된다. */
function model_(it, a) { return { label: label_(it), mine: String(a || '') || '(빈칸)', model: String(it.ans || '') }; }

/** 틀린 문항 하나: 번호 · 학생 답 · 정답 (결과 화면에 보여 준다. 한 번만 제출할 수 있으므로 정답을 보여 줘도 된다 — 2026-09-28) */
const CIRC_ = ['①', '②', '③', '④', '⑤', '⑥', '⑦'];
function fmtAns_(it, v) {
  if (v === '' || v == null || v === 0 || v === '-') return '(빈칸)';
  return mode_(it) === 'choice' ? (CIRC_[Number(v) - 1] || String(v)) : String(v);
}
function fmtKey_(it) {   // 정답 표시 — 복수 정답이면 "②, ④"
  return [it.ans].concat(it.alt || []).map(function (v) { return fmtAns_(it, v); }).join(', ');
}
function fix_(it, a) { return { label: label_(it), mine: fmtAns_(it, a), ans: fmtKey_(it) }; }

/** 찍어서 맞힌 문항 (학생이 [?] 를 누르고 낸 답이 정답) — 결과 화면에 따로 표시한다 (2026-10-15 선생님 요청).
 *  list: [{ it, ok, guess, a }] */
function lucky_(list) {
  return list.filter(function (g) { return g.ok === true && g.guess; })
             .map(function (g) { return { label: label_(g.it), ans: fmtKey_(g.it) }; });
}

/** 해설 하나 (showExp 채점키 — 해설넣기.py 가 넣는다 · 2026-09-30).
 *  mark: O · X · △ · 대기 · why: 어법·어휘 선택형에서 학생이 고른 오답 선택지가 왜 답이 아닌지 (고른 번호 것만) */
function exp_(it, a, ok, got, guess) {
  const m = mode_(it);
  const mark = ok === null ? '대기' : ok ? 'O' : (m === 'auto' && got > 0 ? '△' : 'X');
  const pick = m === 'choice' ? Number(a) || 0 : 0;
  return { label: label_(it), mark: mark, exp: it.exp || '', guess: !!guess,
           mine: m === 'choice' || m === 'symbol' ? fmtAns_(it, a) : '', ans: m === 'choice' || m === 'symbol' ? fmtKey_(it) : '',
           why: !ok && pick && it.why && it.why[String(pick)] ? { pick: CIRC_[pick - 1], text: it.why[String(pick)] } : null };
}

/**
 * 결과 화면 피드백 (2026-09-30 선생님 결정)
 * - 점수 구간별 한마디: 인터넷 말투. 자동 채점된 문항만의 비율로 구간을 정한다
 * - 약한 유형: 담담한 설명 말투 (인터넷 말투는 한마디에만). 같은 유형 2개 이상 틀림, 또는 2문항 이상인 유형에서 절반 이상 틀림 → 많이 틀린 순 최대 3개
 */
const FB_BANDS = [
  [100, 'ㄷㄷ 100점!! 혹시... 천.재.? 🤯'],
  [90, '어때? 90점대의 공기가...다음엔 만점 각!!'],
  [80, '올~ 폼 좋은데? 90점이 코 앞이다!!'],
  [70, '기본기는 됐다 ㅇㅇ 이제 약점 뿌수러 가보자고~'],
  [60, '이번 판은 ㄲㅂ~ 다음엔 더 잘해보자!'],
  [0, '이게...점수? (농담) 수업 때 쌤 말 좀 귀담아 들어라!!']
];
const FB_TIPS = [   // [유형 이름에 들어 있는 말, 한마디] — 위에서부터 먼저 맞는 것
  [/어법/, '동사를 찾고 주어와의 수 일치·병렬 구조·관계사 뒤 문장 성분을 먼저 확인하는 연습'],
  [/어휘/, '밑줄 낱말을 반대말로 바꿔 넣어 보고 글 흐름과 맞는 쪽 고르기'],
  [/요약/, '요약문 낱말을 본문의 바꿔 말한 표현과 짝짓기'],
  [/빈칸/, '빈칸 앞뒤 문장에서 같은 말을 바꿔 되풀이한 근거 찾기'],
  [/주제|제목|요지|목적/, '첫 문장과 마지막 문장에서 글쓴이의 주장 찾기'],
  [/일치|이해|사례/, '선택지마다 본문 근거 문장을 찾아 한 곳씩 대조하기'],
  [/순서|삽입/, '대명사·연결어(this, such, however)로 앞뒤 문장 잇기'],
  [/무관/, '첫 문장의 중심 소재에서 벗어나는 문장 찾기'],
  [/지칭/, '대명사 바로 앞 명사가 아니라 뜻으로 대상 확인하기'],
  [/함축/, '밑줄을 쉬운 말로 풀어 쓰고 글의 요지와 맞춰 보기'],
  [/./, '조건(단어 수·형태·어법)을 먼저 확인하고 해설의 핵심 요소와 비교하기']
];
const FB_NONE = '특별히 약한 유형 없이 틀린 문항이 흩어져 있다. 해설로 하나씩 확인하자.';

/** graded: [{ it, ok, guess }] — ok 가 null(선생님 채점)인 문항은 뺀다.
 *  찍어서 맞힌 문항(guess && ok)은 점수에는 들어가지만 약한 유형을 고를 때는 틀린 것과 같이 센다 (2026-09-30) */
function feedback_(graded, score, autoTotal) {
  if (!(autoTotal > 0)) return null;
  const pct = score / autoTotal * 100;
  const band = FB_BANDS.filter(function (b) { return pct >= b[0] - 1e-6; })[0];
  const by = {};
  graded.forEach(function (g) {
    if (g.ok === null) return;
    const t = String(g.it.type || '기타');
    by[t] = by[t] || { type: t, n: 0, wrong: 0, lucky: 0 };
    by[t].n++;
    if (!g.ok) by[t].wrong++;
    else if (g.guess) by[t].lucky++;
  });
  const weak = Object.keys(by).map(function (k) { return by[k]; })
    .map(function (x) { x.bad = x.wrong + x.lucky; return x; })
    .filter(function (x) { return x.bad >= 2 || (x.n >= 2 && x.bad / x.n >= 0.5); })
    .sort(function (a, b) { return b.bad - a.bad || b.bad / b.n - a.bad / a.n; })
    .slice(0, 3)
    .map(function (x) { return { type: x.type, n: x.n, wrong: x.wrong, lucky: x.lucky,
                                  tip: FB_TIPS.filter(function (t) { return t[0].test(x.type); })[0][1] }; });
  const anyWrong = graded.some(function (g) { return g.ok === false || (g.ok && g.guess); });
  return { msg: band[1], weak: weak, none: anyWrong && !weak.length ? FB_NONE : null };
}

/** 이름을 고를 때 학생 화면이 부른다: 이미 낸 시험이면 첫 제출 결과, 아니면 { already: false } */
function status(id, name) {
  const key = loadKey_(id);
  if (!key) throw new Error('시험을 찾지 못했다');
  if (students_(key).indexOf(name) < 0) throw new Error('명단에 없는 이름');
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (archived_(ss, id)) return { closed: true };
  if (name === TEST_NAME) return { already: false };
  if (key.survey) return surveyDone_(ss, id, name) || { already: false };
  return pastResult_(ss, key, id, name) || { already: false };
}

/**
 * 설문 (2026-10-06 — 세종예고2 중간고사 오답 돌아보기). 채점키에 "survey": true 를 넣으면 채점하지 않고
 * 문항별 질문(q)·보기(opts)를 화면에 보여 주고, 답을 '설문' 탭에 한 문항 한 줄로 적는다.
 * mode: pick(보기 고르기 · multi 면 여러 개) · essay(쓰기). 한 학생은 한 번만 낸다 (TEST 는 몇 번이든).
 */
const SHEET_SURVEY = '설문';
const HEAD_SURVEY = ['제출 시각', '설문', '이름', '시도', '번호', '질문', '답'];
function surveyDone_(ss, id, name) {
  const sh = ss.getSheetByName(SHEET_SURVEY);
  if (!sh || sh.getLastRow() < 2) return null;
  const r = sh.getRange(2, 1, sh.getLastRow() - 1, 3).getValues()
    .filter(function (x) { return x[1] === id && x[2] === name; })[0];
  if (!r) return null;
  const at = r[0] instanceof Date ? Utilities.formatDate(r[0], TZ, 'yyyy-MM-dd HH:mm') : String(r[0]).slice(0, 16);
  return { survey: true, already: true, at: at };
}
function submitSurvey_(key, id, name, answers) {
  const isTest = name === TEST_NAME;
  const rows = key.items.map(function (it, i) {
    const v = answers[i];
    const a = Array.isArray(v) ? v.filter(Boolean).join(' / ') : String(v == null ? '' : v);
    return [label_(it), it.q || '', a.trim().slice(0, 3000)];
  });
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  let attempt = 1;
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    if (!isTest) { const past = surveyDone_(ss, id, name); if (past) return past; }
    const sh = sheet_(ss, SHEET_SURVEY, HEAD_SURVEY);
    if (isTest && sh.getLastRow() >= 2) {
      attempt = sh.getRange(2, 1, sh.getLastRow() - 1, 4).getValues()
        .filter(function (x) { return x[1] === id && x[2] === name; })
        .reduce(function (m, x) { return Math.max(m, Number(x[3]) || 0); }, 0) + 1;
    }
    const now = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm:ss');
    const txt = function (s) { return s ? "'" + s : ''; };
    sh.getRange(sh.getLastRow() + 1, 1, rows.length, HEAD_SURVEY.length).setValues(rows.map(function (r) {
      return [now, id, name, attempt, txt(r[0]), r[1], txt(r[2])];
    }));
    sh.getRange(2, 6, sh.getLastRow() - 1, 2).setWrap(true);
    SpreadsheetApp.flush();
  } finally {
    lock.releaseLock();
  }
  if (!isTest && NOTIFY) {
    try {
      const to = Session.getEffectiveUser().getEmail();
      if (to) MailApp.sendEmail(to, '[온라인채점 설문] ' + name + ' · ' + id,
        ['설문: ' + key.title + ' (' + id + ')', '학생: ' + name, ''].concat(rows.map(function (r) {
          return r[0] + '. ' + r[1] + '\n→ ' + (r[2] || '(빈칸)');
        })).join('\n\n') + '\n\n시트: ' + SpreadsheetApp.getActiveSpreadsheet().getUrl());
    } catch (err) { Logger.log('메일 실패: ' + err); }
  }
  return { survey: true, done: true };
}

/**
 * 첫 제출 결과를 시트에서 다시 만든다. 없으면 null.
 * 문항별 탭의 정오(O·X·채점 대기)로 만든다 — 제출 탭 '틀린 번호' 칸은 옛 기록에서 날짜로 바뀐 것이 있어 쓰지 않는다.
 */
function pastResult_(ss, key, id, name) {
  const sub = ss.getSheetByName(SHEET_SUBMIT);
  if (!sub || sub.getLastRow() < 2) return null;
  const subs = sub.getRange(2, 1, sub.getLastRow() - 1, HEAD_SUBMIT.length).getValues()
    .filter(function (r) { return r[1] === id && r[2] === name; });
  if (!subs.length) return null;
  const firstSub = subs.reduce(function (a, b) { return Number(b[3]) < Number(a[3]) ? b : a; });
  const attempt = Number(firstSub[3]);
  const at = firstSub[0] instanceof Date ? Utilities.formatDate(firstSub[0], TZ, 'yyyy-MM-dd HH:mm') : String(firstSub[0]).slice(0, 16);

  const itm = ss.getSheetByName(SHEET_ITEMS);
  const rows = !itm || itm.getLastRow() < 2 ? [] : itm.getRange(2, 1, itm.getLastRow() - 1, HEAD_ITEMS.length).getValues()
    .filter(function (r) { return r[1] === id && r[2] === name && Number(r[3]) === attempt; });
  const byLabel = {};
  rows.forEach(function (r) { byLabel[String(r[4])] = r; });

  let score = 0, autoTotal = 0, pendTotal = 0, correct = 0, autoCount = 0;
  const wrong = [], pending = [], fix = [], models = [], exps = [], graded = [];
  key.items.forEach(function (it) {
    const r = byLabel[label_(it)];
    const gs = !!(r && r[12] === 'V');   // r[12] = 찍음
    graded.push({ it: it, ok: !isAuto_(it) || (r && r[9] === '채점 대기') ? null : !!(r && r[9] === 'O'), guess: gs,
                  a: r ? r[7] : '' });
    if (key.showExp) {
      const mk = r ? r[9] : '';
      exps.push(exp_(it, r ? r[7] : '', mk === '채점 대기' || !isAuto_(it) ? null : mk === 'O', mk === '△' ? 1 : 0, gs));
    }
    // 입력만 받는 문항, 또는 자동 채점으로 바꾸기 전에 낸 답(아직 '채점 대기')은 선생님 채점분
    if (!isAuto_(it) || (r && r[9] === '채점 대기')) {
      pendTotal += it.pt; pending.push(label_(it)); models.push(model_(it, r ? r[7] : '')); return;
    }
    autoTotal += it.pt; autoCount++;
    score += r ? Number(r[11]) || 0 : 0;   // r[11] = 득점 (auto 는 부분 점수)
    if (r && r[9] === 'O') correct++;
    else { wrong.push(label_(it)); fix.push(fix_(it, r ? r[7] : '')); }   // r[7] = 문항별 탭 '학생 답'
  });
  const r1 = function (x) { return Math.round(x * 10) / 10; };
  const fin = firstSub[11];
  return { already: true, at: at, score: r1(score), autoTotal: r1(autoTotal), total: key.total, correct: correct,
           autoCount: autoCount, pending: pending, pendTotal: r1(pendTotal),
           final: typeof fin === 'number' && pending.length ? r1(fin) : null,
           wrong: key.showWrong ? wrong : null, fix: key.showWrong ? fix : null, lucky: lucky_(graded),
           models: key.showModel ? models : null, exps: key.showExp ? exps : null,
           fb: feedback_(graded, score, autoTotal),
           cmp: compare_(ss, id, name, attempt, score, autoTotal, graded) };
}

/**
 * 지난 회차와 비교 (2026-09-30). 같은 반·같은 종류 시험(ID 가 "<앞부분><번호>회")에서 이 학생이 낸 바로 앞 회차.
 * 자동 채점 문항만으로 정답률을 비교한다. 두 시험 모두 전부 자동 채점이면 점수(100점 만점)로, 아니면 정답률(%)로 보여 준다.
 * graded: 이번 회차 [{ it, ok }] · 반환 null 이면 비교할 앞 회차 없음
 */
function compare_(ss, id, name, attempt, score, autoTotal, graded) {
  const m = /^(.*?)(\d+)회$/.exec(id);
  if (!m || !(autoTotal > 0)) return null;
  const sub = ss.getSheetByName(SHEET_SUBMIT), itm = ss.getSheetByName(SHEET_ITEMS);
  if (!sub || !itm || sub.getLastRow() < 2) return null;
  let prev = null;
  sub.getRange(2, 1, sub.getLastRow() - 1, 4).getValues().forEach(function (r) {
    const pm = /^(.*?)(\d+)회$/.exec(String(r[1]));
    if (r[2] !== name || !pm || pm[1] !== m[1] || Number(pm[2]) >= Number(m[2])) return;
    if (!prev || Number(pm[2]) > prev.no || (Number(pm[2]) === prev.no && Number(r[3]) < prev.attempt)) {
      prev = { id: String(r[1]), no: Number(pm[2]), attempt: Number(r[3]) };
    }
  });
  if (!prev) return null;
  const rows = itm.getRange(2, 1, itm.getLastRow() - 1, 12).getValues()
    .filter(function (r) { return r[1] === prev.id && r[2] === name && Number(r[3]) === prev.attempt && r[9] !== '채점 대기'; });
  if (!rows.length) return null;
  let pScore = 0, pTotal = 0;
  const pType = {}, cType = {};
  rows.forEach(function (r) {
    pScore += Number(r[11]) || 0; pTotal += Number(r[10]) || 0;
    const t = String(r[5]); pType[t] = pType[t] || [0, 0]; pType[t][1]++; if (r[9] === 'O') pType[t][0]++;
  });
  graded.forEach(function (g) {
    if (g.ok === null) return;
    const t = String(g.it.type); cType[t] = cType[t] || [0, 0]; cType[t][1]++; if (g.ok) cType[t][0]++;
  });
  const pct = function (a, b) { return Math.round(a / b * 100); };
  const key = loadKey_(id);
  const allAuto = key && Math.abs(autoTotal - key.total) < 1e-6 && Math.abs(pTotal - 100) < 1e-6 && Math.abs(key.total - 100) < 1e-6;
  const before = allAuto ? Math.round(pScore * 10) / 10 : pct(pScore, pTotal);
  const after = allAuto ? Math.round(score * 10) / 10 : pct(score, autoTotal);
  const types = Object.keys(cType).length < 2 ? [] : Object.keys(cType).filter(function (t) { return pType[t]; })   // 유형이 하나뿐이면 점수 줄과 같다
    .map(function (t) { return { type: t, before: pct(pType[t][0], pType[t][1]), after: pct(cType[t][0], cType[t][1]) }; })
    .filter(function (x) { return x.before !== x.after; })
    .sort(function (a, b) { return Math.abs(b.after - b.before) - Math.abs(a.after - a.before); })
    .slice(0, 3);
  return { prev: prev.no + '회', unit: allAuto ? '점' : '%', before: before, after: after, types: types };
}

/** 시트가 없으면 만들고, 머리글이 옛것(짧은 것)이면 새 머리글로 늘린다 */
function sheet_(ss, name, header) {
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.setFrozenRows(1);
  }
  if (sh.getLastColumn() < header.length) {
    sh.getRange(1, 1, 1, header.length).setValues([header]).setFontWeight('bold');
  }
  return sh;
}

/**
 * 편집기에서 한 번 실행: 자동 채점(auto)으로 바꾸기 전에 낸 서답형 답('채점 대기')을 지금 채점키로 채점한다.
 * 한 칸에 "(1) … (2) … (3) …" 처럼 적은 답을 칸별로 나눠 비교한다. 못 나누면 그대로 두고 로그에 남긴다(선생님 채점).
 * 제출 탭의 '점수'(자동 채점분)·'채점 대기'도 다시 적는다. 선생님이 이미 득점을 넣은 줄은 건드리지 않는다.
 */
function 서답형자동채점_기존제출() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const itm = ss.getSheetByName(SHEET_ITEMS), sub = ss.getSheetByName(SHEET_SUBMIT);
  if (!itm || itm.getLastRow() < 2) return;
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const vals = itm.getRange(2, 1, itm.getLastRow() - 1, HEAD_ITEMS.length).getValues();
    const keys = {}, touched = {};
    let done = 0, left = 0;
    vals.forEach(function (r, i) {
      if (r[9] !== '채점 대기' || r[11] !== '') return;
      const id = r[1];
      if (!(id in keys)) keys[id] = loadKey_(id);
      const key = keys[id];
      const it = key && key.items.filter(function (x) { return label_(x) === String(r[4]); })[0];
      if (!it || mode_(it) !== 'auto') return;
      const g = gradeAuto_(it, r[7]);
      if (!g) { left++; Logger.log('칸을 못 나눔 → 선생님 채점: ' + id + ' ' + r[2] + ' ' + r[4] + ' | ' + r[7]); return; }
      itm.getRange(i + 2, 8, 1, 5).setValues([[g.a || r[7], it.ans, mark_(it, g.full, g.got), it.pt, g.got]]);
      touched[id + '\t' + r[2] + '\t' + r[3]] = true;
      done++;
    });
    // 제출 탭 '점수'·'채점 대기' 다시 쓰기
    if (sub && sub.getLastRow() >= 2) {
      const now = itm.getRange(2, 1, itm.getLastRow() - 1, HEAD_ITEMS.length).getValues();
      const srows = sub.getRange(2, 1, sub.getLastRow() - 1, HEAD_SUBMIT.length).getValues();
      srows.forEach(function (s, i) {
        const k = s[1] + '\t' + s[2] + '\t' + s[3];
        if (!touched[k]) return;
        const mine = now.filter(function (r) { return r[1] === s[1] && r[2] === s[2] && String(r[3]) === String(s[3]); });
        const sc = mine.filter(function (r) { return r[9] !== '채점 대기'; }).reduce(function (t, r) { return t + (Number(r[11]) || 0); }, 0);
        const pend = mine.filter(function (r) { return r[9] === '채점 대기'; }).map(function (r) { return r[4]; });
        const ok = mine.filter(function (r) { return r[9] === 'O'; }).length;
        const bad = mine.filter(function (r) { return r[9] === 'X' || r[9] === '△'; }).map(function (r) { return r[4]; });
        sub.getRange(i + 2, 5).setValue(Math.round(sc * 10) / 10);
        sub.getRange(i + 2, 7).setValue(ok);
        sub.getRange(i + 2, 9).setValue(bad.length ? "'" + bad.join(', ') : '');
        sub.getRange(i + 2, 11).setValue(pend.length ? "'" + pend.join(', ') : '');
      });
    }
    Logger.log('자동 채점 ' + done + '칸 · 선생님 채점으로 남김 ' + left + '칸');
  } finally {
    lock.releaseLock();
  }
}

/* ─────────────────────────── 선생님 메뉴 (시트 위 [온라인채점]) ─────────────────────────── */

function onOpen() {
  SpreadsheetApp.getUi().createMenu('온라인채점')
    .addItem('현황 새로 고침', '현황갱신')
    .addItem('서술형 채점 탭 새로 고침', '서술형탭갱신')
    .addSeparator()
    .addItem('정답 고친 시험 재채점', '재채점메뉴')
    .addItem('시험 기간 보관 (중간·기말 끝나고)', '보관메뉴')
    .addSeparator()
    .addItem('시트 열 때 현황 자동 새로 고침 켜기', '자동갱신켜기')
    .addToUi();
}

/** 날짜로 바뀐 '제출 시각' 칸을 원래 글자로 — 줄을 짝지을 때 쓴다 */
function stamp_(v) { return v instanceof Date ? Utilities.formatDate(v, TZ, 'yyyy-MM-dd HH:mm:ss') : String(v); }
function rowKey_(r) { return [stamp_(r[0]), r[1], r[2], r[3], r[4]].join('|'); }
function vals_(sh, cols) { return !sh || sh.getLastRow() < 2 ? [] : sh.getRange(2, 1, sh.getLastRow() - 1, cols).getValues(); }
function isReal_(name) { return name && name !== TEST_NAME; }

/* ── 1. 재채점: 채점키 정답을 고친 뒤(정답정정.py) 그 시험 제출분을 다시 채점한다 ── */

function 재채점메뉴() {
  const ui = SpreadsheetApp.getUi();
  const r = ui.prompt('재채점', '정답을 고친 시험 ID (예: 세종예고1_실전4회)', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return;
  ui.alert(재채점(r.getResponseText().trim()));
}

/** 선택형·기호 단답만 다시 채점한다 (단어 쓰기·서술형 득점은 선생님이 넣은 값일 수 있어 건드리지 않는다) */
function 재채점(id) {
  const key = loadKey_(id, true);
  if (!key) return '채점키를 찾지 못했다: ' + id;
  CacheService.getScriptCache().put('key:' + id, JSON.stringify(key), 300);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const itm = ss.getSheetByName(SHEET_ITEMS), sub = ss.getSheetByName(SHEET_SUBMIT);
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  let changed = 0;
  const touched = {};
  try {
    const vals = vals_(itm, HEAD_ITEMS.length);
    vals.forEach(function (r, i) {
      if (r[1] !== id) return;
      const it = key.items.filter(function (x) { return label_(x) === String(r[4]); })[0];
      if (!it) return;
      const m = mode_(it);
      if (m !== 'choice' && m !== 'symbol') return;
      const ok = m === 'choice' ? okChoice_(it, Number(r[7]) || 0) : sortSymbols_(r[7]) === it.ans;
      const got = ok ? it.pt : 0;
      const next = [ansText_(it), ok ? 'O' : 'X', it.pt, got];
      if (String(r[8]) !== String(next[0]) || r[9] !== next[1] || Number(r[11]) !== got) {
        itm.getRange(i + 2, 9, 1, 4).setValues([next]);
        touched[[r[1], r[2], r[3]].join('|')] = true;
        changed++;
      }
    });
    // 제출 탭 점수·맞은 수·틀린 번호 다시 쓰기 (최종 점수는 수식이라 따라 바뀐다)
    const now = vals_(itm, HEAD_ITEMS.length);
    vals_(sub, HEAD_SUBMIT.length).forEach(function (s, i) {
      if (!touched[[s[1], s[2], s[3]].join('|')]) return;
      const mine = now.filter(function (r) { return r[1] === s[1] && r[2] === s[2] && String(r[3]) === String(s[3]); });
      const done = mine.filter(function (r) { return r[9] !== '채점 대기'; });
      sub.getRange(i + 2, 5).setValue(Math.round(done.reduce(function (t, r) { return t + (Number(r[11]) || 0); }, 0) * 10) / 10);
      sub.getRange(i + 2, 7).setValue(mine.filter(function (r) { return r[9] === 'O'; }).length);
      const bad = mine.filter(function (r) { return r[9] === 'X' || r[9] === '△'; }).map(function (r) { return r[4]; });
      sub.getRange(i + 2, 9).setValue(bad.length ? "'" + bad.join(', ') : '');
    });
  } finally {
    lock.releaseLock();
  }
  return id + ': ' + changed + '칸 바뀜 · 제출 ' + Object.keys(touched).length + '건 점수 다시 계산';
}

/* ── 4. 현황 탭 3개: 현황(시험별 제출·미제출) · 문항 정답률 · 학생 약점 ── TEST 는 뺀다 */

function 자동갱신켜기() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === '현황갱신') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('현황갱신').forSpreadsheet(ss).onOpen().create();
  SpreadsheetApp.getUi().alert('이제 시트를 열 때마다 현황 탭 3개가 새로 고쳐진다.');
}

function 현황갱신() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const subs = vals_(ss.getSheetByName(SHEET_SUBMIT), HEAD_SUBMIT.length).filter(function (r) { return isReal_(r[2]); });
  const items = vals_(ss.getSheetByName(SHEET_ITEMS), HEAD_ITEMS.length).filter(function (r) { return isReal_(r[2]); });

  // 시험 목록: 제출이 있는 시험 + 최근 3주 안에 만든 채점키 (아직 아무도 안 낸 시험도 미제출로 보이게)
  const ids = {};
  subs.forEach(function (r) { ids[r[1]] = true; });
  const since = Utilities.formatDate(new Date(Date.now() - 21 * 864e5), 'UTC', "yyyy-MM-dd'T'HH:mm:ss");
  const it = DriveApp.searchFiles("title contains '_채점키.json' and modifiedDate > '" + since + "' and trashed = false");
  while (it.hasNext()) ids[it.next().getName().replace(/_채점키\.json$/, '')] = true;
  const arch = archivedIds_(ss);

  // 첫 제출만 센다
  const first = {};
  subs.forEach(function (r) {
    const k = r[1] + '|' + r[2];
    if (!first[k] || Number(r[3]) < Number(first[k][3])) first[k] = r;
  });

  const stat = [['시험', '제목', '명단', '제출', '미제출', '평균(자동)', '최저', '최고', '서술형 채점 대기']];
  const rate = [['시험', '번호', '유형', '제출', '정답률', '가장 많이 고른 오답', '찍음']];
  Object.keys(ids).sort().forEach(function (id) {
    if (arch[id]) return;
    const key = loadKey_(id);
    if (!key || key.survey) return;   // 설문은 '설문' 탭에서 본다
    const done = key.students.filter(function (s) { return first[id + '|' + s]; });
    const miss = key.students.filter(function (s) { return !first[id + '|' + s]; });
    const sc = done.map(function (s) { return Number(first[id + '|' + s][4]) || 0; });
    const avg = sc.length ? Math.round(sc.reduce(function (a, b) { return a + b; }, 0) / sc.length * 10) / 10 : '';
    const mine = items.filter(function (r) {
      const f = first[r[1] + '|' + r[2]];
      return r[1] === id && f && Number(r[3]) === Number(f[3]);
    });
    const pend = mine.filter(function (r) { return r[9] === '채점 대기' && r[11] === ''; }).length;
    stat.push([id, key.title, key.students.length, done.length, miss.join(', '), avg,
               sc.length ? Math.min.apply(null, sc) : '', sc.length ? Math.max.apply(null, sc) : '', pend || '']);
    key.items.forEach(function (x) {
      const rs = mine.filter(function (r) { return String(r[4]) === label_(x) && r[9] !== '채점 대기'; });
      if (!rs.length) return;
      const okN = rs.filter(function (r) { return r[9] === 'O'; }).length;
      const cnt = {};
      rs.filter(function (r) { return r[9] !== 'O' && r[7] !== ''; }).forEach(function (r) { cnt[r[7]] = (cnt[r[7]] || 0) + 1; });
      const top = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; })[0];
      rate.push([id, label_(x), x.type, rs.length, Math.round(okN / rs.length * 100) + '%',
                 top ? fmtAns_(x, mode_(x) === 'choice' ? Number(top) : top) + ' (' + cnt[top] + '명)' : '',
                 rs.filter(function (r) { return r[12] === 'V'; }).length || '']);
    });
  });

  // 학생 약점: 이 시트(이번 시험 기간)의 첫 제출 전부 · 유형별 · 정답률 낮은 순
  const weak = {};
  items.forEach(function (r) {
    const f = first[r[1] + '|' + r[2]];
    if (!f || Number(r[3]) !== Number(f[3]) || r[9] === '채점 대기' || arch[r[1]]) return;
    const k = r[2] + '|' + String(r[1]).split('_')[0] + '|' + r[5];
    weak[k] = weak[k] || [0, 0, 0];
    weak[k][0]++;
    if (r[9] === 'O') { weak[k][1]++; if (r[12] === 'V') weak[k][2]++; }
  });
  const wk = [['이름', '반', '유형', '문항', '맞힘', '찍어서 맞힘', '정답률(찍은 것 빼고)']];
  Object.keys(weak).map(function (k) {
    const p = k.split('|'), w = weak[k];
    return [p[0], p[1], p[2], w[0], w[1], w[2] || '', Math.round((w[1] - w[2]) / w[0] * 100)];
  }).sort(function (a, b) { return a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[6] - b[6]; })
    .forEach(function (r) { r[6] = r[6] + '%'; wk.push(r); });

  write_(ss, SHEET_STAT, stat, '갱신 ' + Utilities.formatDate(new Date(), TZ, 'MM-dd HH:mm') + ' · 첫 제출 기준 · TEST 제외');
  write_(ss, SHEET_RATE, rate);
  write_(ss, SHEET_WEAK, wk);
}

/** 탭을 통째로 다시 쓴다 (선생님이 손으로 적는 탭이 아니다) */
function write_(ss, name, rows, note) {
  let sh = ss.getSheetByName(name) || ss.insertSheet(name);
  sh.clear();
  const w = rows[0].length;
  sh.getRange(1, 1, rows.length, w).setValues(rows.map(function (r) {
    return r.concat(new Array(w - r.length).fill('')).map(function (v) { return typeof v === 'string' && /^[\d,\s]+$/.test(v) && v ? "'" + v : v; });
  }));
  sh.getRange(1, 1, 1, w).setFontWeight('bold');
  sh.setFrozenRows(1);
  if (note) sh.getRange(1, w + 2).setValue(note).setFontColor('#888888');
}

/* ── 14·15. 서술형 채점 탭 · 채점 제안 ── */

/**
 * '채점 대기'이고 득점이 빈 서답형을 한 탭에 모은다. '득점' 칸에 점수를 넣으면(onEdit) 문항별 탭에 바로 반영되고
 * 제출 탭 최종 점수가 계산된다. '제안 점수·제안 이유'는 드라이브의 "온라인채점_서술형제안.json" 에서 읽는다
 * (Claude 가 채점 기준으로 만든 제안 — 확정은 선생님).
 */
function 서술형탭갱신() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const items = vals_(ss.getSheetByName(SHEET_ITEMS), HEAD_ITEMS.length)
    .filter(function (r) { return isReal_(r[2]) && r[9] === '채점 대기' && r[11] === ''; });
  const sugg = loadSuggest_();
  const keys = {};
  const rows = [['줄 번호(건드리지 않음)', '시험', '이름', '번호', '배점', '학생 답', '모범답안', '채점 기준', '제안 점수', '제안 이유', '득점 ✎', '반영']];
  items.forEach(function (r) {
    if (!(r[1] in keys)) keys[r[1]] = loadKey_(r[1]);
    const it = keys[r[1]] && keys[r[1]].items.filter(function (x) { return label_(x) === String(r[4]); })[0];
    const k = rowKey_(r), s = sugg[k] || {};
    rows.push([k, r[1], r[2], r[4], r[10], String(r[7]), it ? String(it.ans || '') : '', it ? String(it.criteria || '') : '',
               s.score === undefined ? '' : s.score, s.why || '', '', '']);
  });
  write_(ss, SHEET_ESSAY, rows, '득점 ✎ 칸에 점수를 넣으면 바로 반영된다');
  const sh = ss.getSheetByName(SHEET_ESSAY);
  sh.setColumnWidth(1, 40);
  [6, 7, 8, 10].forEach(function (c) { sh.setColumnWidth(c, 280); });
  if (rows.length > 1) sh.getRange(2, 1, rows.length - 1, 12).setWrap(true).setVerticalAlignment('top');
  if (rows.length > 1) sh.getRange(2, 11, rows.length - 1, 1).setBackground('#fff8e1');
}

function loadSuggest_() {
  const it = DriveApp.searchFiles("title = '온라인채점_서술형제안.json' and trashed = false");
  let best = null;
  while (it.hasNext()) { const f = it.next(); if (!best || f.getLastUpdated() > best.getLastUpdated()) best = f; }
  try { return best ? JSON.parse(best.getBlob().getDataAsString('UTF-8')) : {}; } catch (e) { return {}; }
}

/** 서술형 채점 탭 '득점 ✎' 칸 입력 → 문항별 탭 득점·정오에 반영 (간단 트리거라 따로 켤 필요 없다) */
function onEdit(e) {
  const sh = e.range.getSheet();
  if (sh.getName() !== SHEET_ESSAY || e.range.getColumn() !== 11 || e.range.getRow() < 2) return;
  const ss = sh.getParent(), itm = ss.getSheetByName(SHEET_ITEMS);
  for (let i = 0; i < e.range.getNumRows(); i++) {
    const row = e.range.getRow() + i;
    const k = String(sh.getRange(row, 1).getValue()), v = sh.getRange(row, 11).getValue(), pt = Number(sh.getRange(row, 5).getValue());
    if (!k || v === '' || isNaN(Number(v))) continue;
    const got = Math.max(0, Math.min(pt, Number(v)));
    const vals = vals_(itm, 12);
    for (let j = 0; j < vals.length; j++) {
      if (rowKey_(vals[j]) !== k) continue;
      itm.getRange(j + 2, 10).setValue(got >= pt ? 'O' : got > 0 ? '△' : 'X');
      itm.getRange(j + 2, 12).setValue(got);
      sh.getRange(row, 12).setValue('✔');
      break;
    }
  }
}

/* ── 16. 시험 기간 보관: 중간·기말이 끝나면 이번 기간 기록을 새 파일로 옮기고 비운다 ── */

function 보관메뉴() {
  const ui = SpreadsheetApp.getUi();
  const r = ui.prompt('시험 기간 보관', '보관 이름 (예: 2026-2학기 중간)\n\n제출·문항별 기록을 새 파일로 복사하고 이 시트에서는 지운다.\n보관한 시험 링크는 더 이상 제출을 받지 않는다.', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK || !r.getResponseText().trim()) return;
  ui.alert(보관(r.getResponseText().trim()));
}

function 보관(label) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const sub = ss.getSheetByName(SHEET_SUBMIT), itm = ss.getSheetByName(SHEET_ITEMS);
    const s = sub ? sub.getDataRange().getValues() : [], m = itm ? itm.getDataRange().getValues() : [];
    if (s.length < 2) return '보관할 제출 기록이 없다';
    const out = SpreadsheetApp.create('온라인채점 보관 · ' + label);
    const os = out.getSheets()[0].setName(SHEET_SUBMIT);
    os.getRange(1, 1, s.length, s[0].length).setValues(s.map(function (r) { return r.map(function (v) { return typeof v === 'string' && /^[\d,\s-]+$/.test(v) ? "'" + v : v; }); }));
    const om = out.insertSheet(SHEET_ITEMS);
    if (m.length) om.getRange(1, 1, m.length, m[0].length).setValues(m);
    // 원본 파일과 같은 폴더에 둔다
    const parent = DriveApp.getFileById(ss.getId()).getParents();
    if (parent.hasNext()) DriveApp.getFileById(out.getId()).moveTo(parent.next());

    const ids = {};
    s.slice(1).forEach(function (r) { if (r[1]) ids[r[1]] = true; });
    const ar = sheet_(ss, SHEET_ARCH, ['보관 이름', '보관 시각', '파일', '시험 ID']);
    ar.appendRow([label, Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'), out.getUrl(), Object.keys(ids).join(', ')]);

    sub.getRange(2, 1, sub.getLastRow() - 1, sub.getLastColumn()).clearContent();
    if (itm && itm.getLastRow() > 1) itm.getRange(2, 1, itm.getLastRow() - 1, itm.getLastColumn()).clearContent();
    [SHEET_ESSAY, SHEET_STAT, SHEET_RATE, SHEET_WEAK].forEach(function (n) { const x = ss.getSheetByName(n); if (x) x.clear(); });
    CacheService.getScriptCache().remove('arch');
    return '보관 완료: ' + Object.keys(ids).length + '개 시험 · 제출 ' + (s.length - 1) + '건 → ' + out.getUrl();
  } finally {
    lock.releaseLock();
  }
}

function archivedIds_(ss) {
  const cache = CacheService.getScriptCache();
  let s = cache.get('arch');
  if (s === null) {
    const map = {};
    vals_(ss.getSheetByName(SHEET_ARCH), 4).forEach(function (r) {
      String(r[3]).split(',').forEach(function (x) { x = x.trim(); if (x) map[x] = true; });
    });
    s = JSON.stringify(map);
    cache.put('arch', s, 600);
  }
  return JSON.parse(s);
}
function archived_(ss, id) { return !!archivedIds_(ss)[id]; }

/** 알림 메일 권한 승인 · 시험 발송: 편집기에서 한 번 실행하면 권한 창이 뜨고, 내 메일로 시험 메일이 한 통 온다. 시트에는 아무것도 적지 않는다 */
function 알림메일시험() {
  notify_({ title: '알림 메일 시험', total: 100 }, '시험ID', '(시험)', 0, [], []);
  Logger.log('보냄: ' + Session.getEffectiveUser().getEmail());
}

/** 설치 확인용: 편집기에서 한 번 실행하면 권한 승인 창이 뜨고, 채점키를 읽을 수 있는지 로그에 찍는다 */
function 설치확인() {
  const it = DriveApp.searchFiles("title contains '_채점키.json' and trashed = false");
  let n = 0; while (it.hasNext()) { it.next(); n++; }
  Logger.log('채점키 ' + n + '개 찾음');
  Logger.log('시트: ' + SpreadsheetApp.getActiveSpreadsheet().getName());
}
