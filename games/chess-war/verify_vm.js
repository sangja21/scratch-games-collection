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
  check('전역 변수 129개 (방송 10개 제외; 유닛표시 +1)', gv === 129, `count=${gv}`);
  // 2차 패치 #2(템포↑): 속도·공격력↑, 공속·적체력↓
  check('템포: 폰_속도 5.5, 나이트_속도 6.0, 적폰_속도 5.0 (횡단 빠르게)',
        Number(v.폰_속도)===5.5 && Number(v.나이트_속도)===6.0 && Number(v.적폰_속도)===5.0,
        `폰${v.폰_속도} 나${v.나이트_속도} 적폰${v.적폰_속도}`);
  check('템포: 폰_공격력 6·공속 0.4 → 검은폰(체력8) 2타 결판', Number(v.폰_공격력)===6 && Number(v.폰_공속)===0.4 && Number(v.적폰_체력)===8,
        `폰뎀${v.폰_공격력} 폰공속${v.폰_공속} 적폰HP${v.적폰_체력}`);
  check('템포: 초당골드 8→14, 처치골드 2→3 (경제 비례 상향)', Number(v.초당골드)===14 && Number(v.처치골드)===3);
  // 2차 패치 #1(비숍 버그): 원거리 사거리 대폭 상향(뒤에서 사격)
  check('비숍 버그 수정: 원거리 사거리 필드횡단(비숍380·룩400·퀸390) → 후방 아티'+'\n'+'(적선두 사격 + 킹 공성으로 스테이지 클리어 가능)',
        Number(v.비숍_사거리)===380 && Number(v.룩_사거리)===400 && Number(v.퀸_사거리)===390,
        `비숍${v.비숍_사거리} 룩${v.룩_사거리} 퀸${v.퀸_사거리}`);
  check('유닛 상한=12, 시뮬틱=0.02', Number(v.최대유닛수)===12 && Number(v.적최대유닛수)===12 && Number(v.시뮬틱)===0.02);
  check('쿨오버레이 스프라이트 존재 + 코스튬 4', !!orig('쿨오버레이') && orig('쿨오버레이').getCostumes().length===4);
  // 2차 패치 #3: n/12 유닛 표시 변수
  check('유닛 표시 변수 초기 "0/12"', String(v.유닛)==='0/12', `유닛=${v.유닛}`);

  // ---- (2) enemy spawner ----
  console.log('--- (2) 적 스포너 (리스트 append · 적군수++ · 렌더 클론) ---');
  setVar('적소환간격', 0.3);
  await sleep(1600);
  v = stageVars();
  check('적군X 리스트 자라남 (>=1)', (listVal('적군X')||[]).length >= 1, `len=${(listVal('적군X')||[]).length}`);
  check('적군수 >= 1', Number(v.적군수) >= 1, `적군수=${v.적군수}`);
  check('적군유닛 렌더 클론 스폰됨', clones('적군유닛').length >= 1, `clones=${clones('적군유닛').length}`);
  const enT = listVal('적군타입'), enHP = listVal('적군HP');
  check('스테이지1 적=검은폰(타입1), 적군HP=적폰_체력(8)×적배율(1)',
        (enT||[]).every(t=>Number(t)===1) && (enT||[]).every((t,i)=>Math.abs(Number(enHP[i])-8)<1e-6),
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
  check('오버레이 클론 5기(버튼 5칸 상태)', clones('쿨오버레이').length === 5, `clones=${clones('쿨오버레이').length}`);
  // n/12 라이브 갱신(방금 폰 1기 소환 → "1/12")
  await sleep(120);
  check('유닛 표시 라이브 갱신: 아군수 1 → "1/12"', String(stageVars().유닛)==='1/12', `유닛=${stageVars().유닛}`);

  // ---- (4bis) [버그 회귀] 뒤에 선 비숍/룩이 실제로 사격하는지 (혼성 시나리오) ----
  console.log('--- (4bis) 원거리 유닛 후방 사격 (비숍/룩 버그 회귀) ---');
  async function backlineFires(allyType, enemyMul, label) {
    setVar('게임상태', 2); setVar('적최대유닛수', 0); await sleep(120);
    for (const nm of ['적군X','적군HP','적군타입','적군살아있음','적군쿨','아군X','아군HP','아군타입','아군살아있음','아군쿨']) listVal(nm).length = 0;
    setVar('유닛공격력배수', 1);
    // 폰(앞, -100, melee) + 원거리유닛(뒤, -160) ; 적 2기(앞 -75, 뒤 -30) — 원거리 사거리 안
    listVal('아군X').push(-100, -160); listVal('아군HP').push(9999, 9999); listVal('아군타입').push(1, allyType);
    listVal('아군살아있음').push(1, 1); listVal('아군쿨').push(0, 0); setVar('아군수', 2);
    listVal('적군X').push(-75, -30); listVal('적군HP').push(99999, 99999); listVal('적군타입').push(1, 1);
    listVal('적군살아있음').push(1, 1); listVal('적군쿨').push(0, 0); setVar('적군수', 2);
    setVar('폰_공격력', 0); // 폰 데미지 0 → 적 HP 감소는 오직 원거리 유닛 몫
    const e0 = listVal('적군HP').map(Number);
    setVar('게임상태', 1);
    await sleep(900);
    const e1 = listVal('적군HP').map(Number);
    const dmg = (e0[0]-e1[0]) + (e0[1]-e1[1]);
    check(`${label}: 폰 앞에 있어도 뒤의 원거리 유닛이 사격(데미지>0)`, dmg > 0, `총 데미지=${dmg}`);
    setVar('폰_공격력', 6);
  }
  await backlineFires(2, 1, '비숍(뒤)');   // 타입2 비숍
  await backlineFires(4, 1, '룩(뒤·광역)'); // 타입4 룩

  // 적 검은비숍도 대칭으로 후방 사격하는지
  console.log('--- (4bis-2) 검은비숍 후방 사격 (대칭) ---');
  setVar('게임상태', 2); setVar('적최대유닛수', 0); await sleep(120);
  for (const nm of ['적군X','적군HP','적군타입','적군살아있음','적군쿨','아군X','아군HP','아군타입','아군살아있음','아군쿨']) listVal(nm).length = 0;
  // 검은폰(앞 100) + 검은비숍(뒤 160) ; 아군 2기(앞 75, 뒤 30) 검은비숍 사거리(190) 안
  listVal('적군X').push(100, 160); listVal('적군HP').push(9999, 9999); listVal('적군타입').push(1, 2);
  listVal('적군살아있음').push(1, 1); listVal('적군쿨').push(0, 0); setVar('적군수', 2);
  listVal('아군X').push(75, 30); listVal('아군HP').push(99999, 99999); listVal('아군타입').push(1, 1);
  listVal('아군살아있음').push(1, 1); listVal('아군쿨').push(0, 0); setVar('아군수', 2);
  setVar('적폰_공격력', 0);
  const a0 = listVal('아군HP').map(Number);
  setVar('게임상태', 1);
  await sleep(900);
  const a1 = listVal('아군HP').map(Number);
  const admg = (a0[0]-a1[0])+(a0[1]-a1[1]);
  check('검은비숍(뒤)도 검은폰 앞에서 아군에게 사격(데미지>0)', admg > 0, `총 데미지=${admg}`);
  setVar('적폰_공격력', 3); setVar('적최대유닛수', 12);

  // ---- (4ter) 킹 공성: 적이 살아있어도 원거리 유닛이 검은 킹을 깎는다 (스테이지 클리어 가능성) ----
  console.log('--- (4ter) 킹 공성 (적 존재해도 원거리가 킹 사격 → 클리어 가능) ---');
  setVar('게임상태', 2); setVar('적최대유닛수', 0); await sleep(120);
  for (const nm of ['적군X','적군HP','적군타입','적군살아있음','적군쿨','아군X','아군HP','아군타입','아군살아있음','아군쿨']) listVal(nm).length = 0;
  setVar('검은킹체력', 500); setVar('유닛공격력배수', 1);
  // 적 1기(살아있음=1, 적선두슬롯≠0 보장) + 아군 비숍 1기(필드 어디서든 킹 사거리 380 안)
  listVal('적군X').push(-50); listVal('적군HP').push(99999); listVal('적군타입').push(1);
  listVal('적군살아있음').push(1); listVal('적군쿨').push(0); setVar('적군수', 1);
  listVal('아군X').push(-100); listVal('아군HP').push(9999); listVal('아군타입').push(2); // 비숍
  listVal('아군살아있음').push(1); listVal('아군쿨').push(0); setVar('아군수', 1);
  const enK0 = Number(stageVars().검은킹체력), enFrontSlot0 = Number(stageVars().적선두슬롯);
  setVar('게임상태', 1);
  await sleep(900);
  const enK1 = Number(stageVars().검은킹체력);
  check('적 유닛 살아있는데도(적선두슬롯≠0) 비숍이 검은 킹 공성', enK1 < enK0, `검은킹 ${enK0}→${enK1}`);
  check('적선두슬롯≠0 유지(킹이 아니라 적을 최전방으로 잡음에도 킹 공성됨)', Number(stageVars().적선두슬롯) !== 0,
        `적선두슬롯=${stageVars().적선두슬롯}`);
  setVar('검은킹체력', 120); setVar('적최대유닛수', 12);

  // ---- (4b) 이동 속도(틱당 X 증가량) 상향 확인 ----
  console.log('--- (4b) 이동 속도(틱당 X 증가) ---');
  setVar('게임상태', 2); setVar('적최대유닛수', 0);
  await sleep(150);
  for (const nm of ['적군X','적군HP','적군타입','적군살아있음','적군쿨','아군X','아군HP','아군타입','아군살아있음','아군쿨']) { listVal(nm).length = 0; }
  // 폰 1기, 적 선두 없음(적선두X=검은킹X=200) → 사거리 밖이라 매 틱 폰_속도(4.0)만큼 전진
  listVal('아군X').push(-150); listVal('아군HP').push(12); listVal('아군타입').push(1);
  listVal('아군살아있음').push(1); listVal('아군쿨').push(0); setVar('아군수', 1);
  setVar('게임상태', 1);
  const x0 = Number(listVal('아군X')[0]);
  await sleep(300);   // ~15 틱(시뮬틱0.02, headless 빠름)
  const x1 = Number(listVal('아군X')[0]);
  const moved = x1 - x0;
  check('폰이 오른쪽으로 실제 전진(틱당 폰_속도만큼 X 증가)', moved > 4, `X ${x0}→${x1} (Δ=${moved.toFixed(1)})`);

  // ---- (4c) 유닛 상한 도달 → 소환 거부 ----
  console.log('--- (4c) 유닛 상한 도달 시 소환 거부 ---');
  setVar('게임상태', 2);
  for (const nm of ['아군X','아군HP','아군타입','아군살아있음','아군쿨']) { listVal(nm).length = 0; }
  setVar('최대유닛수', 12);
  for (let i = 0; i < 12; i++) { listVal('아군X').push(-150); listVal('아군HP').push(12);
    listVal('아군타입').push(1); listVal('아군살아있음').push(1); listVal('아군쿨').push(0); }
  setVar('아군수', 12); setVar('골드', 999);
  setVar('폰쿨타이머', 0); setVar('비숍쿨타이머', 0);
  setVar('게임상태', 1);
  const lenCap = listVal('아군X').length, anCap = Number(stageVars().아군수);
  setMouse(-190, -150, true); await sleep(200); setMouse(-190, -150, false); await sleep(250);
  check('아군수=최대유닛수(12) → 소환 거부(아군수 불변)', Number(stageVars().아군수) === anCap, `아군수 ${anCap}→${stageVars().아군수}`);
  check('상한 도달 → 리스트 안 자람', listVal('아군X').length === lenCap, `len ${lenCap}→${listVal('아군X').length}`);

  // ---- (4d) 쿨 중 소환 거부 + 버튼 상태(쿨타이머>0) ----
  console.log('--- (4d) 쿨 중 소환 거부 ---');
  setVar('게임상태', 2);
  for (const nm of ['아군X','아군HP','아군타입','아군살아있음','아군쿨']) { listVal(nm).length = 0; }
  setVar('아군수', 0); setVar('골드', 999); setVar('폰쿨타이머', 5); // 쿨 걸어둠
  setVar('게임상태', 1);
  const anCd = Number(stageVars().아군수);
  setMouse(-190, -150, true); await sleep(200); setMouse(-190, -150, false); await sleep(250);
  check('폰쿨타이머>0 → 폰 소환 거부(아군수 불변)', Number(stageVars().아군수) === anCd, `아군수 ${anCd}→${stageVars().아군수}`);
  check('쿨 상태 변수(폰쿨타이머)가 버튼/오버레이가 읽는 채널로 살아있음(>0)', Number(stageVars().폰쿨타이머) > 0,
        `폰쿨타이머=${Number(stageVars().폰쿨타이머).toFixed(2)}`);

  // ---- (4e) 죽은 슬롯 재사용(메모리 상한: 리스트 무한 성장 방지) ----
  console.log('--- (4e) 죽은 슬롯 재사용 (replace, 리스트 길이 유지) ---');
  setVar('게임상태', 2);
  for (const nm of ['아군X','아군HP','아군타입','아군살아있음','아군쿨']) { listVal(nm).length = 0; }
  // 살아있는 폰 2기 + 죽은 슬롯 1기(중간)
  listVal('아군X').push(-150,-120,-100);
  listVal('아군HP').push(12,12,12);
  listVal('아군타입').push(1,1,1);
  listVal('아군살아있음').push(1,0,1);   // index2 죽음
  listVal('아군쿨').push(0,0,0);
  setVar('아군수', 2); setVar('골드', 999); setVar('폰쿨타이머', 0); setVar('최대유닛수', 12);
  setVar('게임상태', 1);
  const lenReuse = listVal('아군X').length;
  setMouse(-190, -150, true); await sleep(200); setMouse(-190, -150, false); await sleep(250);
  check('죽은 슬롯 재사용 → 리스트 길이 그대로(3, 무한 성장 X)', listVal('아군X').length === lenReuse,
        `len ${lenReuse}→${listVal('아군X').length}`);
  check('재사용 슬롯 되살아남(살아있음[2]=1)', Number(listVal('아군살아있음')[1]) === 1, `살아있음[2]=${listVal('아군살아있음')[1]}`);
  check('아군수 재증가(2→3)', Number(stageVars().아군수) === 3, `아군수=${stageVars().아군수}`);
  setVar('적최대유닛수', 12);

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
    check('검은 퀸 HP = 적퀸_체력(32) × 적배율(2) = 64', Math.abs(eqHp - 64) < 1e-6, `HP=${eqHp}`);
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
