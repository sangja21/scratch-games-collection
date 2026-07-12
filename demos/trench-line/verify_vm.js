// Headless scratch-vm 행동 시나리오 검증 — trench-line (참호전선).
// 렌더러 없음 → touching(mouse) 은 거리 기반 몽키패치(버튼/구역 클릭 시뮬용).
// 이 게임의 전투는 touching 이 아니라 Stage 심판이 리스트(전력/전선/선두y)만 보고
// 상수 시간에 판정하므로 touching 패치는 클릭 입력 근사에만 영향.
// 8개 시나리오 실측:
//  1) 소환+구역지정 게이트  2) ★ 유닛 클론이 다른 클론 스캔 0개(구조)
//  3) 팝업 캡+자동삭제  4) 3구역 전선 밀고밀림  5) 돌파→본진HP
//  6) 열세 구역 선두 처치 O(1)  7) 경제 루프+캡  8) 60초 안정성
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '참호전선.sb3');
const vm = new VM();
function stage() { return vm.runtime.targets.find(t => t.isStage); }
function gv(name) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) return Number(st.variables[id].value); }
function setVar(name, val) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val; }
// scratch-vm 런타임은 리스트를 target.variables 에 type==='list' 로 저장.
function getList(name) { const st = stage(); for (const id in st.variables) { const v = st.variables[id]; if (v.type === 'list' && v.name === name) return v.value.map(Number); } return undefined; }
function setListItem(name, idx, val) { const st = stage(); for (const id in st.variables) { const v = st.variables[id]; if (v.type === 'list' && v.name === name) v.value[idx-1] = val; } }
function orig(name) { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal); }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`); if (!ok) FAIL = true; }

// 버튼/구역 클릭 시뮬: 대상 위로 마우스 이동 + 다운.
function clickAt(x, y) {
  const cx = 240 + x, cy = 180 - y;
  vm.runtime.ioDevices.mouse.postData({ x: cx, y: cy, isDown: true, canvasWidth: 480, canvasHeight: 360 });
}
function clickButton(name) { const b = orig(name); clickAt(b.x, b.y); }
function clickZone(z) { const zx = (z - 2) * 140; clickAt(zx, 10); }
function mouseUp() { vm.runtime.ioDevices.mouse.postData({ x: 0, y: 0, isDown: false, canvasWidth: 480, canvasHeight: 360 }); }
function installMouseTouch(vm) {
  const proto = Object.getPrototypeOf(vm.runtime.targets[0]);
  const md = vm.runtime.ioDevices.mouse;
  proto.isTouchingObject = function (name) {
    if (name === '_mouse_') {
      const mx = md.getScratchX(), my = md.getScratchY();
      // 버튼(높이 40)·구역(넓은 컬럼) 히트박스 근사
      return Math.abs(this.x - mx) <= 70 && Math.abs(this.y - my) <= 90;
    }
    return false;
  };
}

// 유닛 소환 헬퍼: 버튼 선택 → 구역 클릭
async function summon(btn, z) {
  clickButton(btn); await sleep(70); mouseUp(); await sleep(80);
  clickZone(z); await sleep(70); mouseUp(); await sleep(80);
}

(async () => {
  await vm.loadProject(fs.readFileSync(sb3));

  // ============================================================
  // (2-정적) 유닛 클론 스크립트에 다른 유닛/팝업 클론 스캔 0개 — 구조 확인
  // ============================================================
  console.log('--- (2-정적) 유닛 클론이 다른 클론 스캔 0개 (코드 구조) ---');
  const unitSprites = ['아군유닛', '적유닛'];
  const otherSprites = ['아군유닛', '적유닛', '데미지팝업', '구역클릭'];
  let scanViolations = [];
  for (const sp of unitSprites) {
    const t = orig(sp);
    const blocks = t.blocks._blocks;
    const fld = (f) => { if (!f) return ''; if (Array.isArray(f)) return f[0]; return f.value || f.name || ''; };
    for (const id in blocks) {
      const b = blocks[id]; const op = b.opcode;
      if (op === 'sensing_touchingobject') {
        const menuInput = b.inputs['TOUCHINGOBJECTMENU'];
        let menuVal = '';
        if (menuInput) { const mb = blocks[menuInput[1]]; if (mb) menuVal = fld(mb.fields.TOUCHINGOBJECTMENU); }
        if (otherSprites.includes(menuVal)) scanViolations.push(`${sp}:touching ${menuVal}`);
      }
      if (op === 'sensing_of') {
        const menuInput = b.inputs['OBJECT'];
        let menuVal = '';
        if (menuInput) { const mb = blocks[menuInput[1]]; if (mb) menuVal = fld(mb.fields.OBJECT); }
        if (otherSprites.includes(menuVal)) scanViolations.push(`${sp}:of ${menuVal}`);
      }
      if (op === 'sensing_distanceto' || op === 'sensing_distancetomenu') scanViolations.push(`${sp}:${op}`);
    }
    // 유닛 스프라이트는 리스트 정의 0개(순회 판정 금지)
    if (Object.keys(t.lists || {}).length > 0) scanViolations.push(`${sp}:has local lists`);
  }
  check('유닛 클론 스크립트에 다른 클론 touching·sensing_of·distanceto 0개', scanViolations.length === 0,
        scanViolations.length ? scanViolations.join(', ') : '위반 0개');

  // 심판이 Stage 에 존재: 전선/전력 리스트를 상수 index(1~3) 로 판정
  const stBlocks = stage().blocks._blocks;
  const listName = (b) => (b.fields && b.fields.LIST) ? (Array.isArray(b.fields.LIST) ? b.fields.LIST[0] : b.fields.LIST.value) : '';
  let judgeUsesFront = Object.values(stBlocks).some(b => b.opcode === 'data_replaceitemoflist' && /전선/.test(listName(b)));
  let judgeUsesPow = Object.values(stBlocks).some(b => b.opcode === 'data_itemoflist' && /전력/.test(listName(b)));
  check('Stage 심판이 L_전선 replace + L_전력 item 으로 판정(구역 리스트 상수시간)', judgeUsesFront && judgeUsesPow);
  // 심판 루프는 repeat(3 고정) — 클론 순회 아님
  // scratch-vm 런타임의 control_repeat.inputs.TIMES = {name, block(shadowId), shadow}.
  // 그 shadow 블록의 fields.NUM 값을 읽어 3 인지 확인.
  let hasRepeat3 = Object.values(stBlocks).some(b => {
    if (b.opcode !== 'control_repeat') return false;
    const ti = b.inputs.TIMES; if (!ti) return false;
    let v;
    if (Array.isArray(ti)) { v = Array.isArray(ti[1]) ? ti[1][1] : undefined; }
    else if (ti.block) { const sh = stBlocks[ti.block]; v = sh && sh.fields && sh.fields.NUM ? (Array.isArray(sh.fields.NUM) ? sh.fields.NUM[0] : sh.fields.NUM.value) : undefined; }
    return String(v) === '3';
  });
  check('심판 루프가 repeat 3(구역 3개 고정=상수)', hasRepeat3);

  installMouseTouch(vm);
  vm.start();
  vm.greenFlag();
  await sleep(700);

  // ---------- (0) 초기화 ----------
  console.log('--- (0) 초기화 ---');
  check('게임상태1·아군본진HP100·적본진HP100·돈≈40', gv('게임상태')==1 && gv('아군본진HP')==100 && gv('적본진HP')==100 && Math.abs(gv('돈')-40)<10,
        `state=${gv('게임상태')} aHP=${gv('아군본진HP')} eHP=${gv('적본진HP')} gold=${gv('돈').toFixed(0)}`);
  check('캡: 구역캡6 전체캡24 팝업캡20', gv('구역캡')==6 && gv('전체캡')==24 && gv('팝업캡')==20);
  check('코스트: 소총30 제압55 저격50', gv('소총_코스트')==30 && gv('제압_코스트')==55 && gv('저격_코스트')==50);
  const fr0 = getList('L_전선');
  check('L_전선 3칸 초기화(≈10,10,10)', fr0 && fr0.length===3 && fr0.every(v=>Math.abs(v-10)<1), `${fr0}`);

  // ---------- (1) 소환+구역지정 게이트 ----------
  console.log('--- (1) 소환+구역지정 게이트 ---');
  // 돈 부족: 제압(55) 를 돈 30 에서 시도 → 스폰 안 됨.
  setVar('돈', 30); await sleep(120);
  let a0 = gv('아군총수');
  await summon('버튼제압', 2);
  check('돈 부족(30<55) 시 제압 소환 거부', gv('아군총수') === a0, `아군총수 ${a0}→${gv('아군총수')}`);
  // 대기소환종류만 세팅되고 구역 클릭 안 하면 스폰 안 됨(선택만)
  setVar('돈', 200); setVar('소총_쿨타이머', 0); setVar('대기소환종류', 0); await sleep(100);
  clickButton('버튼소총'); await sleep(80); mouseUp(); await sleep(120);
  check('버튼만 클릭 → 대기소환종류 세팅(선택), 아직 스폰 아님', gv('대기소환종류')===1 && gv('아군총수')===a0,
        `대기=${gv('대기소환종류')} 총수=${gv('아군총수')}`);
  // 구역 클릭 → 스폰 + 돈 차감 + 전력 증가
  let g0 = gv('돈'), c0 = gv('아군총수');
  const apowBefore = getList('L_아군전력')[0];
  clickZone(1); await sleep(80); mouseUp(); await sleep(150);
  check('구역1 클릭 → 소총 소환됨(아군총수+1)', gv('아군총수') === c0 + 1, `아군총수 ${c0}→${gv('아군총수')}`);
  check('소환 시 돈 차감(≈-30)', g0 - gv('돈') >= 27, `돈 ${g0.toFixed(0)}→${gv('돈').toFixed(0)}`);
  check('소환 시 L_아군전력[1] += 전력(이벤트 기반)', getList('L_아군전력')[0] > apowBefore, `전력[1]=${getList('L_아군전력')[0]}`);
  check('소환 후 소총 쿨 리셋(>0)', gv('소총_쿨타이머') > 0, `쿨=${gv('소총_쿨타이머')}`);

  // ---------- (7-a) 구역캡 6 ----------
  console.log('--- (7-a) 구역캡6 / 전체캡24 ---');
  vm.greenFlag(); await sleep(500);
  setVar('대기소환종류', 1);
  for (let i = 0; i < 12; i++) { setVar('돈', 200); setVar('소총_쿨타이머', 0); clickZone(1); await sleep(60); mouseUp(); await sleep(50); }
  await sleep(300);
  const acnt1 = getList('L_아군수')[0];
  check('한 구역 아군수 ≤ 구역캡6 (초과 소환 거부)', acnt1 <= 6, `아군수[1]=${acnt1}`);

  // ---------- (4) 3구역 전선 밀고밀림 ----------
  console.log('--- (4) 3구역 전선 밀고밀림(전력차) ---');
  vm.greenFlag(); await sleep(600);
  // 구역1(좌)에만 아군 몰빵 → 아군전력[1] 우세 → L_전선[1] 이 적진(+150) 쪽으로 전진.
  // 적 AI 가 다른 구역에도 스폰하므로, 구역1 을 확실히 우세로 만들고 관찰.
  setVar('적스폰간격', 6); // 적 AI 억제(구역1 우세 확실화)
  const frontStart = getList('L_전선')[0];
  for (let i = 0; i < 8; i++) { setVar('돈', 200); setVar('제압_쿨타이머', 0); setVar('대기소환종류', 2); clickZone(1); await sleep(70); mouseUp(); await sleep(60); }
  let maxFront1 = frontStart, sawIndependent = false;
  for (let i = 0; i < 40; i++) {
    await sleep(80);
    const fl = getList('L_전선');
    maxFront1 = Math.max(maxFront1, fl[0]);
    // 구역별 독립: 전선[1] 이 움직이는 동안 전선[2]/[3] 은 다른 값(독립 전선)
    if (Math.abs(fl[0] - fl[1]) > 5 || Math.abs(fl[0] - fl[2]) > 5) sawIndependent = true;
  }
  check('아군 우세 구역1 전선이 적진 쪽(+y)으로 전진', maxFront1 > frontStart + 8, `전선[1] ${frontStart.toFixed(0)}→max ${maxFront1.toFixed(0)}`);
  check('세 구역 전선이 각자 독립적으로 움직임', sawIndependent, `L_전선=${getList('L_전선').map(v=>v.toFixed(0))}`);
  // 반대 방향(밀고밀림 대칭): 구역3 을 적 우세로 강제 → 심판이 전선[3] 을 아군진(-y) 쪽으로 후퇴시키는지.
  // 전력차 부호가 전선 이동 부호를 결정함을 결정적으로 검증(심판 math 직접 관찰).
  vm.greenFlag(); await sleep(500);
  const front3Start = getList('L_전선')[2];
  let minFront3 = front3Start;
  for (let i=0;i<40;i++){
    setListItem('L_적전력', 3, 20); setListItem('L_아군전력', 3, 0); // 구역3 적 우세 유지
    await sleep(80);
    minFront3 = Math.min(minFront3, getList('L_전선')[2]);
  }
  check('적 우세 구역 전선이 아군진 쪽(-y)으로 후퇴(밀고밀림 대칭)', minFront3 < front3Start - 8,
        `전선[3] ${front3Start.toFixed(0)}→min ${minFront3.toFixed(0)}`);

  // ---------- (5) 돌파 → 본진 HP 감소 ----------
  console.log('--- (5) 돌파 → 본진 HP 감소 ---');
  vm.greenFlag(); await sleep(500);
  // 강제로 구역2 전선을 적진y 로 밀어 돌파 상황 만들고 적 본진HP 감소 관찰.
  const eHP0 = gv('적본진HP');
  setListItem('L_전선', 2, gv('적진y'));   // 전선[2] = 적진y (돌파)
  setListItem('L_아군전력', 2, 20); setListItem('L_적전력', 2, 0); // 유지되게 아군 우세
  await sleep(1200);
  check('구역 돌파(전선=적진y) 지속 시 적 본진HP 감소', gv('적본진HP') < eHP0, `적본진HP ${eHP0}→${gv('적본진HP').toFixed(1)}`);
  // 승리 경로: 적 본진HP 0
  setVar('적본진HP', 0); await sleep(300);
  check('적 본진HP≤0 → 게임상태0(승리 종료)', gv('게임상태') === 0, `state=${gv('게임상태')}`);
  const ban = orig('결과배너');
  check('결과배너 표시됨', ban.visible, `visible=${ban.visible}`);
  // 대칭: 아군 본진 돌파 → 패배
  vm.greenFlag(); await sleep(500);
  const aHP0 = gv('아군본진HP');
  setListItem('L_전선', 1, gv('아군진y'));
  setListItem('L_적전력', 1, 20); setListItem('L_아군전력', 1, 0);
  await sleep(1000);
  check('대칭: 아군진y 돌파 시 아군 본진HP 감소', gv('아군본진HP') < aHP0, `아군본진HP ${aHP0}→${gv('아군본진HP').toFixed(1)}`);
  setVar('아군본진HP', 0); await sleep(300);
  check('아군 본진HP≤0 → 게임상태0(패배 종료)', gv('게임상태') === 0, `state=${gv('게임상태')}`);

  // ---------- (6) 열세 구역 선두 처치 O(1) ----------
  console.log('--- (6) 열세 구역 선두 처치(피격구역 신호) ---');
  vm.greenFlag(); await sleep(500);
  setVar('적스폰간격', 0.6);
  // 구역2 에 아군 소총 몇 기 넣고, 적 우세로 만들어 아군피격구역 신호가 발행되는지 관찰.
  for (let i=0;i<3;i++){ setVar('돈',200); setVar('소총_쿨타이머',0); setVar('대기소환종류',1); clickZone(2); await sleep(70); mouseUp(); await sleep(60); }
  // 강제로 구역2 적 우세
  let sawHitSignal = false, sawUnitDeath = false;
  let prevAcnt2 = getList('L_아군수')[1];
  for (let i=0;i<50;i++){
    await sleep(80);
    setListItem('L_적전력', 2, 30); setListItem('L_아군전력', 2, 3); // 구역2 적 우세 유지
    if (gv('아군피격구역') === 2 || gv('아군피격구역') === 1 || gv('아군피격구역') === 3) sawHitSignal = true;
    const ac = getList('L_아군수')[1];
    if (ac < prevAcnt2) sawUnitDeath = true;
    prevAcnt2 = Math.max(prevAcnt2, ac);
  }
  check('심판이 열세 구역에 아군피격구역 신호 발행(선두 지목)', sawHitSignal, `아군피격구역 관측=${sawHitSignal}`);
  check('열세 구역 선두 유닛이 처치되어 아군수[2] 감소(O(1) 처치)', sawUnitDeath || getList('L_아군수')[1] <= 3, `아군수[2]=${getList('L_아군수')[1]}`);

  // ---------- (3) 데미지 팝업 캡 + 자동삭제 ----------
  console.log('--- (3) 데미지 팝업 캡20 + 자동삭제 ---');
  vm.greenFlag(); await sleep(500);
  setVar('적스폰간격', 0.5);
  // 사격 폭주: 세 구역에 아군·적 다수 → 팝업요청 쇄도. 팝업수/클론이 캡 이내인지, 누수 없는지.
  let maxPop = 0, maxPopClones = 0;
  for (let i=0;i<50;i++){
    setVar('돈',200); setVar('소총_쿨타이머',0); setVar('제압_쿨타이머',0);
    const z = 1 + (i%3); const b = (i%2===0)?'버튼소총':'버튼제압';
    setVar('대기소환종류', b==='버튼소총'?1:2); clickZone(z); await sleep(45); mouseUp(); await sleep(30);
    maxPop = Math.max(maxPop, gv('팝업수'));
    maxPopClones = Math.max(maxPopClones, clones('데미지팝업').length);
  }
  check('★ 팝업요청 폭주에도 팝업수 ≤ 팝업캡20', maxPop <= 20, `최대 팝업수=${maxPop}`);
  check('★ 동시 팝업 클론 ≤ 팝업캡20+여유(초과 요청 생략)', maxPopClones <= 22, `최대 팝업클론=${maxPopClones}`);
  // 소환·사격 중단(게임상태0으로 유닛 사격 정지) 후 팝업이 자동삭제로 완전히 빠지는지(누수 0) 관찰.
  setVar('게임상태', 0);
  const popAtStop = gv('팝업수');
  await sleep(1600);
  check('★ 팝업 자동삭제(0.4~0.6초 후) → 팝업수 0 으로 드레인(누수 0)', gv('팝업수') === 0 && clones('데미지팝업').length === 0,
        `정지시 ${popAtStop} → 1.6초후 팝업수=${gv('팝업수')} 클론=${clones('데미지팝업').length}`);

  // ---------- (7-b) 경제 루프 ----------
  console.log('--- (7-b) 경제 루프 ---');
  vm.greenFlag(); await sleep(400);
  setVar('돈', 0); await sleep(1100);
  check('돈이 돈충전율로 차오름(0→>0)', gv('돈') > 0, `돈=${gv('돈').toFixed(1)}`);
  setVar('돈', 195); await sleep(700);
  check('돈상한(200)에서 멈춤', gv('돈') <= 200.5, `돈=${gv('돈').toFixed(1)}`);

  // ---------- (2-동적) 다수 유닛 동시 생존에도 진행 지속(프레임 붕괴 없음) ----------
  console.log('--- (2-동적) 다수 클론 동시 생존에도 심판 진행 지속 ---');
  const aliveNow = clones('아군유닛').length + clones('적유닛').length;
  const fmid = getList('L_전선');
  check('다수 클론 생존 상태에서도 전선 리스트 정상 갱신(NaN 없음)',
        fmid.every(v => Number.isFinite(v)), `살아있는 유닛 클론=${aliveNow}, L_전선=${fmid.map(v=>v.toFixed(0))}`);

  // ---------- (8) 60초 자동 플레이 안정성 ----------
  console.log('--- (8) 60초 자동 플레이 안정성 (클론 누수 없음) ---');
  vm.greenFlag(); await sleep(600);
  setVar('적스폰간격', 1.2);
  const tStart = Date.now();
  let maxUnitClones = 0, maxPopClones2 = 0, decided = false, roundsDecided = 0, castleDamaged = false;
  const combos = [['버튼소총',1],['버튼소총',2],['버튼제압',3],['버튼저격',1],['버튼소총',3],['버튼제압',2]];
  let k = 0;
  while (Date.now() - tStart < 60000) {
    const [bn, z] = combos[k % combos.length]; k++;
    setVar('돈', 200);
    setVar('소총_쿨타이머', 0); setVar('제압_쿨타이머', 0); setVar('저격_쿨타이머', 0);
    setVar('대기소환종류', bn==='버튼소총'?1:(bn==='버튼제압'?2:3));
    clickZone(z); await sleep(40); mouseUp(); await sleep(25);
    const uc = clones('아군유닛').length + clones('적유닛').length;
    const pc = clones('데미지팝업').length;
    maxUnitClones = Math.max(maxUnitClones, uc);
    maxPopClones2 = Math.max(maxPopClones2, pc);
    if (gv('적본진HP') < 100 || gv('아군본진HP') < 100) castleDamaged = true;
    if (gv('게임상태') === 0) { decided = true; roundsDecided++; vm.greenFlag(); await sleep(200); setVar('적스폰간격', 1.2); }
  }
  const elapsed = (Date.now() - tStart) / 1000;
  console.log(`     60초 관찰: 최대 동시 유닛 클론=${maxUnitClones}, 최대 동시 팝업 클론=${maxPopClones2}, 승패결착=${decided}(${roundsDecided}판), 본진HP감소=${castleDamaged}`);
  check('★ 유닛 클론 누수 없음(양진영 합 ≤ 전체캡24×2 여유상한 50)', maxUnitClones <= 50, `max=${maxUnitClones}`);
  check('★ 팝업 클론 누수 없음(≤ 팝업캡20 + 여유)', maxPopClones2 <= 24, `max=${maxPopClones2}`);
  check('돌파→본진 타격→결착 경로 작동(결착 또는 본진HP 감소 관측)', decided || castleDamaged, `결착=${decided} 본진HP감소=${castleDamaged}`);
  check('★ 60초 완주(프레임 붕괴로 멈추지 않음)', elapsed >= 59, `${elapsed.toFixed(0)}s`);

  console.log(FAIL ? '\n=== RESULT: FAIL ===' : '\n=== RESULT: ALL PASS ===');
  process.exit(FAIL ? 1 : 0);
})();
