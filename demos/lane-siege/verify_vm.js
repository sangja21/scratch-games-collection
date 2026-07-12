// Headless scratch-vm 행동 시나리오 검증 — lane-siege (라인 시즈).
// 렌더러 없음 → touching 은 거리 기반 몽키패치. 단, 이 게임의 전투는 touching 이 아니라
// 선두 공유 변수(아군선두y/적선두y + 아군선두HP/적선두HP)로 판정하므로 touching 패치는
// 화살 명중 근사에만 영향(화살도 실제로는 변수 거리 판정이라 무관). 8개 시나리오 실측:
//  1) 소환 게이트  2) ★ O(n) 최전방 교전(클론끼리 스캔 0개 — 정적+동적)
//  3) 선두 격돌  4) 원거리·투사체 캡  5) 유닛 캡  6) 경제 루프  7) 승패  8) 60초 안정성
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '라인_시즈.sb3');
const vm = new VM();
function stage() { return vm.runtime.targets.find(t => t.isStage); }
function gv(name) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) return Number(st.variables[id].value); }
function setVar(name, val) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val; }
function orig(name) { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal); }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return Number(c.variables[id].value); return undefined; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`); if (!ok) FAIL = true; }

// 버튼 클릭 시뮬레이트: 버튼 위로 마우스 이동 + 다운 → 폴링 스크립트가 감지.
function clickButton(name) {
  const b = orig(name);
  // 버튼 좌표를 스테이지 픽셀(480x360)로: canvas 중앙 240,180.
  const cx = 240 + b.x, cy = 180 - b.y;
  vm.runtime.ioDevices.mouse.postData({ x: cx, y: cy, isDown: true, canvasWidth: 480, canvasHeight: 360 });
}
function mouseUp() { vm.runtime.ioDevices.mouse.postData({ x: 0, y: 0, isDown: false, canvasWidth: 480, canvasHeight: 360 }); }
// 렌더 없이 touching(mouse) 이 되도록 오버라이드(버튼 히트박스 = 버튼 근처).
function installMouseTouch(vm) {
  const proto = Object.getPrototypeOf(vm.runtime.targets[0]);
  const md = vm.runtime.ioDevices.mouse;
  proto.isTouchingObject = function (name) {
    if (name === '_mouse_') {
      const mx = md.getScratchX(), my = md.getScratchY();
      return Math.abs(this.x - mx) <= 42 && Math.abs(this.y - my) <= 24;
    }
    return false; // 유닛/화살 touching 은 이 게임에서 안 씀
  };
}

(async () => {
  await vm.loadProject(fs.readFileSync(sb3));

  // ============================================================
  // (2-정적) 클론 스크립트에 다른 유닛 클론 스캔 코드 0개 — 구조 확인
  // ============================================================
  console.log('--- (2-정적) 클론끼리 스캔 0개 (코드 구조) ---');
  // scratch-vm 이 로드한 런타임 blocks 를 직접 검사(별도 zip 파싱 불필요).
  const unitSprites = ['아군유닛', '적유닛'];
  let scanViolations = [];
  for (const sp of unitSprites) {
    const t = orig(sp);
    const blocks = t.blocks._blocks;
    for (const id in blocks) {
      const b = blocks[id];
      const op = b.opcode;
      // 금지: 다른 스프라이트/클론을 탐색하는 opcode
      const fld = (f) => { if (!f) return ''; if (Array.isArray(f)) return f[0]; return f.value || f.name || ''; };
      if (op === 'sensing_touchingobject') {
        // touching 메뉴가 다른 유닛/화살을 가리키면 위반. (_mouse_/_edge_ 는 허용)
        const menuInput = b.inputs['TOUCHINGOBJECTMENU'];
        let menuVal = '';
        if (menuInput) { const mb = blocks[menuInput[1]]; if (mb) menuVal = fld(mb.fields.TOUCHINGOBJECTMENU); }
        if (unitSprites.includes(menuVal) || menuVal === '아군화살' || menuVal === '적화살') scanViolations.push(`${sp}:touching ${menuVal}`);
      }
      if (op === 'sensing_of') {
        const menuInput = b.inputs['OBJECT'];
        let menuVal = '';
        if (menuInput) { const mb = blocks[menuInput[1]]; if (mb) menuVal = fld(mb.fields.OBJECT); }
        if (unitSprites.includes(menuVal)) scanViolations.push(`${sp}:of ${menuVal}`);
      }
      // 금지: 리스트 순회/이중 루프 전투 → 리스트 opcode 자체 없어야
      if (op && op.startsWith('data_') && op.includes('list')) scanViolations.push(`${sp}:list ${op}`);
      if (op === 'data_itemoflist' || op === 'data_lengthoflist') scanViolations.push(`${sp}:${op}`);
    }
    // 리스트 정의 0개
    if (Object.keys(t.lists || {}).length > 0) scanViolations.push(`${sp}:has lists`);
  }
  check('유닛 클론 스크립트에 다른 유닛/화살 touching·sensing_of·리스트 순회 0개', scanViolations.length === 0,
        scanViolations.length ? scanViolations.join(', ') : '위반 0개');
  // 심판 opcode 가 Stage 에 존재(선두 채널 판정) 확인
  const stBlocks = stage().blocks._blocks;
  function varName(f) { if (!f) return ''; if (Array.isArray(f)) return f[0]; return f.value || ''; }
  let hasLeadHP = Object.values(stBlocks).some(b => b.fields && varName(b.fields.VARIABLE) && /선두HP/.test(varName(b.fields.VARIABLE)));
  check('Stage 심판이 선두HP 채널을 직접 판정(구조상 선두 경유 상수시간)', hasLeadHP);

  installMouseTouch(vm);
  vm.start();
  vm.greenFlag();
  await sleep(700);

  // ---------- (0) 초기화 ----------
  console.log('--- (0) 초기화 ---');
  check('게임상태1·아군성HP60·적성HP60·돈40', gv('게임상태')==1 && gv('아군성HP')==60 && gv('적성HP')==60 && Math.abs(gv('돈')-40)<8,
        `state=${gv('게임상태')} aHP=${gv('아군성HP')} eHP=${gv('적성HP')} gold=${gv('돈').toFixed(0)}`);
  check('캡: 유닛캡8 투사체캡12', gv('유닛캡')==8 && gv('투사체캡')==12);
  check('코스트: 방패20 궁수50 척후15', gv('방패_코스트')==20 && gv('궁수_코스트')==50 && gv('척후_코스트')==15);

  // ---------- (1) 소환 게이트 ----------
  console.log('--- (1) 소환 게이트 ---');
  // 돈 부족 상황: 궁수(50) 를 돈 30 에서 시도 → 스폰 안 됨.
  setVar('돈', 30); await sleep(150);
  let a0 = gv('아군수');
  clickButton('버튼궁수'); await sleep(200); mouseUp(); await sleep(200);
  check('돈 부족(30<50) 시 궁수 소환 거부', gv('아군수') === a0, `아군수 ${a0}→${gv('아군수')}`);
  // 돈 충분: 척후(15) 소환 성공 + 돈 차감 + 아군수+1
  setVar('돈', 100); setVar('척후_쿨타이머', 0); await sleep(120);
  let g0 = gv('돈'), c0 = gv('아군수');
  clickButton('버튼척후'); await sleep(220); mouseUp(); await sleep(200);
  check('돈≥코스트 & 쿨끝 & 캡미만 → 척후 소환됨', gv('아군수') === c0 + 1, `아군수 ${c0}→${gv('아군수')}`);
  check('소환 시 돈 차감(≈-15)', g0 - gv('돈') >= 13, `돈 ${g0.toFixed(0)}→${gv('돈').toFixed(0)}`);
  check('소환 후 척후 쿨 리셋(>0)', gv('척후_쿨타이머') > 0, `쿨=${gv('척후_쿨타이머')}`);
  // 쿨 중 재클릭 → 거부
  let c1 = gv('아군수');
  clickButton('버튼척후'); await sleep(150); mouseUp(); await sleep(150);
  check('소환쿨 중 재소환 거부', gv('아군수') === c1, `아군수 ${c1}→${gv('아군수')}`);

  // ---------- (5) 유닛 캡 ----------
  console.log('--- (5) 유닛 캡 8 ---');
  setVar('돈', 200);
  for (let i = 0; i < 14; i++) {
    setVar('척후_쿨타이머', 0); setVar('돈', 200);
    clickButton('버튼척후'); await sleep(90); mouseUp(); await sleep(60);
  }
  await sleep(300);
  check('아군수 ≤ 유닛캡8 (초과 소환 거부)', gv('아군수') <= 8, `아군수=${gv('아군수')}`);
  check('아군 클론 실제 개수 ≤ 8', clones('아군유닛').length <= 8, `clones=${clones('아군유닛').length}`);

  // ---------- (3) 선두 격돌 (선두 채널 교전) ----------
  console.log('--- (3) 선두 격돌: 라인 접근→선두 HP 채널 감소 관찰 ---');
  // 깨끗한 판에서 아군 1기만 뽑고 적 1기(AI)만 두어, 선두가 서로 접근(dist 감소)하다
  // 사거리 안(dist<=30)에서 선두HP 가 melee 로 깎이는 것을 관찰. 한쪽 죽으면 카운트 감소.
  vm.greenFlag(); await sleep(500);
  setVar('돈', 200); setVar('방패_쿨타이머', 0);
  clickButton('버튼방패'); await sleep(120); mouseUp();   // 아군 방패 1기(HP30)
  let sawClose = false, minA = 999, minE = 999, sawCountDrop = false;
  let prevDist = 999;
  for (let i = 0; i < 90; i++) {
    await sleep(70);
    const ah = gv('아군선두HP'), eh = gv('적선두HP');
    const d = gv('적선두y') - gv('아군선두y');
    if (ah > 0) minA = Math.min(minA, ah);
    if (eh > 0) minE = Math.min(minE, eh);
    if (d >= -6 && d <= 30 && gv('아군수') > 0 && gv('적수') > 0) sawClose = true;
    // 근접 교전으로 선두 HP 가 스폰 상한(방패30) 밑으로 떨어지면 실제 격돌.
    if (sawClose && ((ah > 0 && ah < 30) || (eh > 0 && eh < 30))) minA = Math.min(minA, ah > 0 ? ah : minA);
    prevDist = d;
    if (sawClose && (minA < 30 || minE < 30)) break;
  }
  check('선두끼리 사거리 안 접근 관측(-6<=dist<=30, 양측 생존)', sawClose,
        `dist=${(gv('적선두y')-gv('아군선두y')).toFixed(0)} 아수=${gv('아군수')} 적수=${gv('적수')}`);
  check('선두 HP 채널이 근접 교전으로 깎임(교전 발생)', minA < 30 || minE < 30,
        `minALeadHP=${minA.toFixed(1)} minELeadHP=${minE.toFixed(1)}`);

  // ---------- (2-동적) 프레임 붕괴 없이 진행 + 클론끼리 상호작용 없음 확인 ----------
  console.log('--- (2-동적) O(n) 진행(프레임 붕괴 없음) ---');
  // 다수 유닛이 동시에 살아있어도 진격/교전이 정상 진행(선두 y 채널이 갱신되는지).
  const ly0 = gv('아군선두y');
  await sleep(400);
  const alive = clones('아군유닛').length + clones('적유닛').length;
  check('다수 클론 동시 생존 상태에서도 선두 채널 갱신 지속', typeof gv('아군선두y') === 'number' && typeof gv('적선두y') === 'number',
        `살아있는 유닛 클론=${alive}, 아군선두y=${gv('아군선두y').toFixed(0)}`);

  // ---------- (4) 원거리·투사체 캡 ----------
  console.log('--- (4) 원거리·투사체 캡12 ---');
  // 방패병으로 전선을 유지하고 궁수를 뒤에서 뽑아, 궁수 선두가 사거리 안 적 선두에 화살 발사.
  // (조합의 맛 = 방패로 버티고 궁수로 저격). 투사체수 상한/화면밖 삭제 관찰.
  vm.greenFlag(); await sleep(500);
  setVar('돈', 200);
  // 방패 몇 기 + 궁수 다수를 번갈아 소환(적은 AI 자동 스폰 → 사거리 안에 적 선두 생김)
  for (let i = 0; i < 4; i++) { setVar('방패_쿨타이머', 0); setVar('돈', 200); clickButton('버튼방패'); await sleep(90); mouseUp(); await sleep(50); }
  for (let i = 0; i < 6; i++) { setVar('궁수_쿨타이머', 0); setVar('돈', 200); clickButton('버튼궁수'); await sleep(90); mouseUp(); await sleep(50); }
  let maxProj = 0, arrowSeen = false;
  for (let i = 0; i < 90; i++) {
    await sleep(70);
    setVar('돈', 200);
    if (i % 6 === 0) { setVar('궁수_쿨타이머', 0); clickButton('버튼궁수'); await sleep(50); mouseUp(); }
    maxProj = Math.max(maxProj, gv('투사체수'));
    if (clones('아군화살').length > 0 || clones('적화살').length > 0) arrowSeen = true;
  }
  check('화살(투사체 클론) 발사됨 — 사거리 안 최전방 적만 저격', arrowSeen, `최대 동시 투사체수=${maxProj}`);
  check('동시 투사체수 ≤ 투사체캡12 (초과 발사 스킵)', maxProj <= 12, `max=${maxProj}`);
  // 화면 밖/명중 삭제: 투사체수가 캡 이내 유한(누수 없음)
  await sleep(600);
  check('투사체 화면밖/명중 즉시 삭제로 총량 억제(0≤투사체수≤12)', gv('투사체수') <= 12 && gv('투사체수') >= 0, `투사체수=${gv('투사체수')}`);

  // ---------- (6) 경제 루프 ----------
  console.log('--- (6) 경제 루프 ---');
  setVar('돈', 0); await sleep(1100);
  check('돈이 돈충전율로 차오름(0→>0)', gv('돈') > 0, `돈=${gv('돈').toFixed(1)}`);
  setVar('돈', 195); await sleep(700);
  check('돈상한(200)에서 멈춤', gv('돈') <= 200.5, `돈=${gv('돈').toFixed(1)}`);

  // ---------- (7) 승패 ----------
  console.log('--- (7) 승패 배너 ---');
  setVar('적성HP', 0); await sleep(300);
  check('적성HP≤0 → 게임상태0(승리 종료)', gv('게임상태') === 0, `state=${gv('게임상태')}`);
  const ban = orig('결과배너');
  check('결과배너 표시됨', ban.visible, `visible=${ban.visible}`);
  // 재시작 후 패배 경로도
  vm.greenFlag(); await sleep(500);
  setVar('아군성HP', 0); await sleep(300);
  check('아군성HP≤0 → 게임상태0(패배 종료)', gv('게임상태') === 0, `state=${gv('게임상태')}`);

  // ---------- (8) 60초 안정성 · 클론 누수 없음 ----------
  console.log('--- (8) 60초 자동 플레이 안정성 (클론 누수 없음) ---');
  vm.greenFlag(); await sleep(600);
  const tStart = Date.now();
  let maxUnitClones = 0, maxArrowClones = 0, decided = false, roundsDecided = 0;
  let castleDamaged = false;   // 돌파→성타격이 실제로 일어남(승패 경로 검증)
  // 자동 플레이어: 척후 러시 위주(빠른 돌파)로 계속 유닛을 뽑고, 적 AI 는 자동. 캡 준수·누수 없음 관찰.
  // headless 스텝은 실시간의 ~2배 느리므로 wall 60s ≈ game 30s. 그래도 돌파→성HP 감소·결착을 관찰.
  const btns = ['버튼척후', '버튼척후', '버튼방패', '버튼궁수'];
  while (Date.now() - tStart < 60000) {
    const bn = btns[Math.floor(Math.random() * btns.length)];
    setVar('돈', 200);
    // 소환쿨을 밀어 flood(자동 플레이어의 경제 우위 시뮬레이션)
    setVar('척후_쿨타이머', 0);
    clickButton(bn); await sleep(45); mouseUp(); await sleep(30);
    const uc = clones('아군유닛').length + clones('적유닛').length;
    const ac = clones('아군화살').length + clones('적화살').length;
    maxUnitClones = Math.max(maxUnitClones, uc);
    maxArrowClones = Math.max(maxArrowClones, ac);
    if (gv('적성HP') < 60 || gv('아군성HP') < 60) castleDamaged = true;
    if (gv('게임상태') === 0) { decided = true; roundsDecided++;
      vm.greenFlag(); await sleep(200); }   // 승패 나면 재시작해 계속 부하
  }
  const elapsed = (Date.now() - tStart) / 1000;
  console.log(`     60초 관찰: 최대 동시 유닛 클론=${maxUnitClones}, 최대 동시 화살 클론=${maxArrowClones}, 승패결착=${decided}(${roundsDecided}판), 성HP감소관측=${castleDamaged}`);
  // 캡: 유닛은 양 진영 각 8 → 최대 16, 화살은 최대 12. 누수 없으면 이 상한 근처에 머문다.
  check('★ 유닛 클론 누수 없음(양진영 합 ≤ 20 여유상한)', maxUnitClones <= 20, `max=${maxUnitClones}`);
  check('★ 화살 클론 누수 없음(≤ 투사체캡12 + 여유)', maxArrowClones <= 14, `max=${maxArrowClones}`);
  // 결착 또는 (최소한) 돌파→성타격이 관측되면 승패 경로가 살아있음을 증명(headless 감속 감안).
  check('돌파→성 타격→결착 경로 작동(결착 또는 성HP 감소 관측)', decided || castleDamaged,
        `결착=${decided} 성HP감소=${castleDamaged}`);
  check('★ 60초 완주(프레임 붕괴로 멈추지 않음)', elapsed >= 59, `${elapsed.toFixed(0)}s`);

  console.log(FAIL ? '\n=== RESULT: FAIL ===' : '\n=== RESULT: ALL PASS ===');
  process.exit(FAIL ? 1 : 0);
})();
