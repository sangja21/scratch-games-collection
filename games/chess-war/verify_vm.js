// Headless scratch-vm runtime check for chess-war.
// Renderer stubbed → positions/state/list logic DO run. Verifies: var init (124),
// list init (10 empty), enemy spawner append (list grows, 적군수++), 렌더 클론,
// 소환(마우스 폴링 5칸) → 아군 리스트 append + 아군수++ + 골드 차감, 전투매니저 시뮬
// (적 전진 → 하얀킹체력 감소 / 아군이 적 처치 → 살아있음=0·적군수--), 룩 광역 포격,
// 퀸 이중 공격(단일+광역), 검은 퀸 보스 스폰, 게임상태 전이(1→2 클리어, 1→0 게임오버),
// 강화 택1(1/2/3/4) + 지수 스케일(적배율=배율^(n-1)), 효과음 10종(orphan 0).
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '체스_대전쟁.sb3');
const buf = fs.readFileSync(sb3);
const vm = new VM();

function stage() { return vm.runtime.targets.find(t => t.isStage); }
function stageVars() {
  const st = stage(); const out = {};
  for (const id in st.variables) { const v = st.variables[id]; if (v.type !== 'list' && v.type !== 'broadcast_msg') out[v.name] = v.value; }
  return out;
}
function setVar(name, val) {
  const st = stage();
  for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val;
}
function listVal(name) { const st = stage(); for (const id in st.variables) { const v = st.variables[id]; if (v.type === 'list' && v.name === name) return v.value; } return undefined; }
function orig(name) { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal); }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`);
  if (!ok) FAIL = true;
}
function setMouse(sx, sy, isDown) {
  vm.runtime.ioDevices.mouse.postData({ x: sx + 240, y: 180 - sy, canvasWidth: 480, canvasHeight: 360, isDown: !!isDown });
}

(async () => {
  await vm.loadProject(buf);
  vm.start();
  vm.greenFlag();
  await sleep(600);

  // ---- (1) var init ----
  console.log('--- (1) 변수/리스트 초기화 ---');
  let v = stageVars();
  check('게임상태=1, 스테이지=1, 골드≈시작골드(200)', v.게임상태==1 && v.스테이지==1 && v.골드>=200 && v.골드<=215,
        `state=${v.게임상태} stage=${v.스테이지} gold=${v.골드}`);
  check('하얀킹체력=100, 검은킹체력=120, 적배율=1', v.하얀킹체력==100 && v.검은킹체력==120 && v.적배율==1,
        `my=${v.하얀킹체력} en=${v.검은킹체력} scale=${v.적배율}`);
  check('유닛공격력배수=1, 유닛체력배수=1, 나이트/룩/퀸해금=0',
        v.유닛공격력배수==1 && v.유닛체력배수==1 && v.나이트해금==0 && v.룩해금==0 && v.퀸해금==0);
  check('아군 리스트 비어있음(소환 전)', (listVal('아군X')||[]).length===0);
  const gv = Object.keys(v).length;
  check('전역 변수 124개 (방송 10개 제외)', gv === 124, `count=${gv}`);

  // ---- (2) enemy spawner ----
  console.log('--- (2) 적 스포너 (리스트 append · 적군수++ · 렌더 클론) ---');
  setVar('적소환간격', 0.3);
  await sleep(1600);
  v = stageVars();
  check('적군X 리스트 자라남 (>=1)', (listVal('적군X')||[]).length >= 1, `len=${(listVal('적군X')||[]).length}`);
  check('적군수 >= 1', Number(v.적군수) >= 1, `적군수=${v.적군수}`);
  check('적군유닛 렌더 클론 스폰됨', clones('적군유닛').length >= 1, `clones=${clones('적군유닛').length}`);
  const enT = listVal('적군타입'), enHP = listVal('적군HP');
  check('스테이지1 적=검은폰(타입1), 적군HP=10×적배율(1)',
        (enT||[]).every(t=>Number(t)===1) && (enT||[]).every((t,i)=>Math.abs(Number(enHP[i])-10)<1e-6),
        `types=${JSON.stringify(enT)} hp=${JSON.stringify(enHP)}`);

  // ---- (3) 적 전진 → 하얀킹 피격 ----
  console.log('--- (3) 적 전진 → 하얀 킹 피격 ---');
  const myBefore = Number(stageVars().하얀킹체력);
  const enXlist = listVal('적군X');
  for (let i = 0; i < enXlist.length; i++) enXlist[i] = -170;
  await sleep(1500);
  v = stageVars();
  check('적이 하얀 킹 도달 → 하얀킹체력 감소', Number(v.하얀킹체력) < myBefore, `하얀킹체력 ${myBefore}→${v.하얀킹체력}`);

  // ---- (4) 소환(마우스 폴링 5칸) ----
  console.log('--- (4) 소환 (마우스 폴링, 폰=x영역1) ---');
  setVar('골드', 500);
  const goldB = Number(stageVars().골드);
  const allyB = (listVal('아군X')||[]).length;
  const anB = Number(stageVars().아군수);
  setMouse(-190, -150, true);
  await sleep(250);
  setMouse(-190, -150, false);
  await sleep(300);
  v = stageVars();
  check('폰 소환 → 아군X 리스트 +1', (listVal('아군X')||[]).length === allyB + 1, `len ${allyB}→${(listVal('아군X')||[]).length}`);
  check('아군수 +1', Number(v.아군수) === anB + 1, `아군수 ${anB}→${v.아군수}`);
  const goldDelta = goldB - Number(v.골드);
  check('골드 -폰코스트(18) (초당골드 누적 여지 10)', goldDelta >= 8 && goldDelta <= 18, `골드 ${goldB}→${v.골드} (delta ${goldDelta})`);
  check('아군타입 마지막=1(폰), 아군살아있음=1', Number((listVal('아군타입')||[]).slice(-1)[0])===1 &&
        Number((listVal('아군살아있음')||[]).slice(-1)[0])===1);
  check('아군유닛 렌더 클론 등장', clones('아군유닛').length >= 1, `clones=${clones('아군유닛').length}`);

  // ---- (5) 전투: 아군이 적 처치 (통제된 1:1) ----
  console.log('--- (5) 전투 시뮬 (적 처치, 통제된 시나리오) ---');
  setVar('게임상태', 2); setVar('적최대유닛수', 0); setVar('적폰_공격력', 0);
  await sleep(200);
  for (const nm of ['적군X','적군HP','적군타입','적군살아있음','적군쿨','아군X','아군HP','아군타입','아군살아있음','아군쿨']) {
    const L = listVal(nm); L.length = 0;
  }
  listVal('적군X').push(-150); listVal('적군HP').push(1); listVal('적군타입').push(1);
  listVal('적군살아있음').push(1); listVal('적군쿨').push(0); setVar('적군수', 1);
  listVal('아군X').push(-170); listVal('아군HP').push(12); listVal('아군타입').push(1);
  listVal('아군살아있음').push(1); listVal('아군쿨').push(0); setVar('아군수', 1);
  const goldBefore = Number(stageVars().골드);
  setVar('게임상태', 1);
  await sleep(1200);
  v = stageVars();
  check('적 체력 0 → 적군살아있음[1]=0 (삭제 아님, 인덱스 불변)', Number(listVal('적군살아있음')[0]) === 0,
        `살아있음=${listVal('적군살아있음')[0]}`);
  check('적 처치 → 적군수 0', Number(v.적군수) === 0, `적군수=${v.적군수}`);
  check('적 처치 → 골드 증가(처치골드)', Number(v.골드) > goldBefore, `골드 ${goldBefore}→${v.골드}`);
  check('리스트 길이 불변', listVal('적군X').length === 1, `len=${listVal('적군X').length}`);

  // ---- (5b) 룩 광역: 한 발에 여러 적 동시 피해 ----
  console.log('--- (5b) 룩 광역 포격 (반경 안 적 전부 동시 피해) ---');
  setVar('게임상태', 2);
  for (const nm of ['적군X','적군HP','적군타입','적군살아있음','적군쿨','아군X','아군HP','아군타입','아군살아있음','아군쿨']) {
    const L = listVal(nm); L.length = 0;
  }
  for (const ex of [80, 100, 120]) { listVal('적군X').push(ex); listVal('적군HP').push(999);
    listVal('적군타입').push(1); listVal('적군살아있음').push(1); listVal('적군쿨').push(0); }
  setVar('적군수', 3);
  listVal('아군X').push(0); listVal('아군HP').push(16); listVal('아군타입').push(4);
  listVal('아군살아있음').push(1); listVal('아군쿨').push(0); setVar('아군수', 1);
  setVar('유닛공격력배수', 1);
  const hp0 = listVal('적군HP').map(Number);
  setVar('게임상태', 1);
  await sleep(500);
  const hp1 = listVal('적군HP').map(Number);
  const hitCount = hp0.filter((h,i)=>hp1[i] < h).length;
  check('룩 포격 1발이 반경 안 적 여러 기(>=2)에 동시 피해', hitCount >= 2,
        `피해 입은 적 ${hitCount}/3 (${hp0}→${hp1})`);

  // ---- (5c) 퀸 이중 공격: 최전방 적이 단일+광역 둘 다 맞음 ----
  console.log('--- (5c) 퀸 이중 공격 (최전방=단일+광역 둘 다) ---');
  setVar('게임상태', 2);
  for (const nm of ['적군X','적군HP','적군타입','적군살아있음','적군쿨','아군X','아군HP','아군타입','아군살아있음','아군쿨']) {
    const L = listVal(nm); L.length = 0;
  }
  listVal('적군X').push(80); listVal('적군HP').push(9999); listVal('적군타입').push(1);
  listVal('적군살아있음').push(1); listVal('적군쿨').push(0);
  listVal('적군X').push(110); listVal('적군HP').push(9999); listVal('적군타입').push(1);
  listVal('적군살아있음').push(1); listVal('적군쿨').push(0);
  setVar('적군수', 2);
  listVal('아군X').push(0); listVal('아군HP').push(30); listVal('아군타입').push(5);
  listVal('아군살아있음').push(1); listVal('아군쿨').push(0); setVar('아군수', 1);
  setVar('퀸_공격력', 7); setVar('유닛공격력배수', 1); setVar('퀸_공속', 99);
  const qhp0 = listVal('적군HP').map(Number);
  setVar('게임상태', 1);
  await sleep(250);
  const qhp1 = listVal('적군HP').map(Number);
  const frontDmg = qhp0[0] - qhp1[0];   // 최전방(80): 단일+광역 → 14
  const backDmg = qhp0[1] - qhp1[1];    // 뒤(110): 광역만 → 7
  check('퀸 한 쿨: 최전방 적은 단일+광역 둘 다 (뎀 ≈ 2×공격력=14)', Math.abs(frontDmg - 14) < 0.5, `최전방 피해=${frontDmg}`);
  check('퀸 한 쿨: 뒤 적은 광역만 (뎀 ≈ 공격력=7)', Math.abs(backDmg - 7) < 0.5, `뒤 피해=${backDmg}`);
  check('이중 공격: 최전방 피해 > 뒤 피해 (단일이 더해짐)', frontDmg > backDmg, `${frontDmg} vs ${backDmg}`);

  // ---- (5d) 검은 퀸 보스 스폰 (6+스테이지) ----
  console.log('--- (5d) 검은 퀸 보스 스폰 (6+스테이지) ---');
  setVar('게임상태', 2);
  for (const nm of ['적군X','적군HP','적군타입','적군살아있음','적군쿨']) { listVal(nm).length = 0; }
  // 보스는 스폰마다 1/8 확률 → 스폰을 많이 돌려 관측 확률↑ (min간격 낮추고 상한 크게, 길게)
  setVar('적군수', 0); setVar('적최대유닛수', 999);
  setVar('적소환간격', 0.1); setVar('적소환간격감소', 0); setVar('적소환최소간격', 0.05);
  setVar('스테이지', 8); setVar('적배율', 2);
  setVar('게임상태', 1);
  await sleep(4000);
  const types = (listVal('적군타입')||[]).map(Number);
  const sawQueen = types.includes(5);
  const validTypes = types.length >= 1 && types.every(t => t>=1 && t<=5);
  check('6+스테이지 스폰 타입이 1~5 범위', validTypes, `types=${JSON.stringify(types)}`);
  check('여러 스폰 중 검은 퀸(타입5) 보스 등장', sawQueen, `saw5=${sawQueen} (types=${JSON.stringify(types)})`);
  if (sawQueen) {
    const qi = types.indexOf(5);
    const eqHp = Number(listVal('적군HP')[qi]);
    check('검은 퀸 HP = 적퀸_체력(40) × 적배율(2) = 80', Math.abs(eqHp - 80) < 1e-6, `HP=${eqHp}`);
  }

  // ---- (6) 스테이지 클리어 → 강화 → 지수 스케일 ----
  console.log('--- (6) 스테이지 클리어(체크메이트) → 강화 → 지수 스케일 ---');
  setVar('적최대유닛수', 0);
  setVar('스테이지', 1); setVar('나이트해금', 0); setVar('룩해금', 0); setVar('퀸해금', 0);
  setVar('게임상태', 1); setVar('검은킹체력', 0);
  await sleep(300);
  v = stageVars();
  check('검은킹체력<=0(체크메이트) → 게임상태=2', Number(v.게임상태) === 2, `state=${v.게임상태}`);
  const atkMulBefore = Number(stageVars().유닛공격력배수);
  vm.postIOData('keyboard', { key: '2', isDown: true });
  await sleep(150);
  vm.postIOData('keyboard', { key: '2', isDown: false });
  await sleep(500);
  v = stageVars();
  check('강화2: 유닛공격력배수 ×= 강화공격배수(1.15)', Math.abs(Number(v.유닛공격력배수) - atkMulBefore*1.15) < 1e-6,
        `${atkMulBefore}→${v.유닛공격력배수}`);
  check('강화 후 스테이지 2', Number(v.스테이지) === 2, `stage=${v.스테이지}`);
  check('강화완료 → 게임상태=1', Number(v.게임상태) === 1, `state=${v.게임상태}`);
  const n = Number(v.스테이지), scale = Number(stageVars().적성장배율);
  const expected = Math.pow(scale, n-1);
  check('적배율 = 적성장배율^(스테이지-1) (지수)', Math.abs(Number(v.적배율) - expected) < 1e-6,
        `적배율=${v.적배율} 기대=${expected.toFixed(4)}`);
  check('검은킹체력 = 검은킹기본체력 × 적배율', Math.abs(Number(v.검은킹체력) - 120*expected) < 1e-3, `검은킹체력=${v.검은킹체력}`);
  check('스테이지2 → 나이트해금=1', Number(v.나이트해금) === 1, `나이트해금=${v.나이트해금}`);
  check('강화 후 리스트 비워짐(전장 리셋)', (listVal('적군X')||[]).length === 0 && (listVal('아군X')||[]).length === 0);

  // ---- (7) 게임오버 ----
  console.log('--- (7) 게임오버 ---');
  setVar('게임상태', 1); setVar('하얀킹체력', 0);
  await sleep(300);
  v = stageVars();
  check('하얀킹체력<=0 → 게임상태=0', Number(v.게임상태) === 0, `state=${v.게임상태}`);
  await sleep(400);
  check('게임오버 후 아군·적 클론 자기 삭제', clones('아군유닛').length === 0 && clones('적군유닛').length === 0);
  check('게임오버 배너 show', orig('게임오버') && orig('게임오버').visible === true);

  // ---- (8) 효과음 10종 (orphan 0) ----
  console.log('--- (8) 합성 효과음 10종 ---');
  const want = {
    소환버튼: ['summon','error'], 전투매니저: ['clash','cannon','coin'], 아군유닛: ['death'],
    적군유닛: ['death'], 하얀킹: ['kinghit','break'], 검은킹: ['kinghit','break'],
    Stage: ['horn'], 강화카드: ['upgrade'],
  };
  let sndOK = true, sdet = [], total = 0;
  for (const sp in want) {
    const t = vm.runtime.targets.find(x => (x.isStage && sp==='Stage') || (x.sprite && x.sprite.name===sp && x.isOriginal));
    const names = (t && t.sprite && t.sprite.sounds || []).map(s => s.name);
    total += names.length;
    for (const w of want[sp]) if (!names.includes(w)) { sndOK = false; sdet.push(`${sp}!${w}`); }
  }
  check('스프라이트별 효과음 등록(소환2·매니저3·유닛1·킹2·Stage1·카드1)', sndOK, sdet.join(' ') || 'all present');
  check('효과음 총 13개 슬롯(10종·킹2채·유닛2 death 중복 등록, orphan 0)', total === 13, `total=${total}`);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'RUNTIME CHECK: SOME CHECKS FAILED' : 'RUNTIME CHECK COMPLETE — all checks passed, no exceptions.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
