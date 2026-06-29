// Headless scratch-vm runtime check for magic-survivor.
// Renderer is stubbed → touching returns false; distance-to / positions / state
// logic DO run. We verify: var init, auto-fire handshake, enemy spawn ramp,
// survival timer, difficulty stage, level-up state machine, damage popup,
// game over, and that clone counts stay bounded (no runaway multiplication).
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '마법_생존.sb3');
const buf = fs.readFileSync(sb3);
const vm = new VM();

function stage() { return vm.runtime.targets.find(t => t.isStage); }
function stageVars() {
  const st = stage(); const out = {};
  for (const id in st.variables) {
    const v = st.variables[id];
    if (v.type !== 'list') out[v.name] = v.value;
  }
  return out;
}
function setVar(name, val) {
  const st = stage();
  for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val;
}
function clones(name) {
  return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false);
}
function cloneLocal(c, name) {
  for (const id in c.variables) if (c.variables[id].name === name) return c.variables[id].value;
  return undefined;
}
function costumeName(t) {
  const c = t.getCostumes()[t.currentCostume];
  return c ? c.name : undefined;
}
function sayBubble(t) {
  const b = t.getCustomState && t.getCustomState('Scratch.looks');
  return b ? b.text : undefined;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`);
  if (!ok) FAIL = true;
}

(async () => {
  await vm.loadProject(buf);
  vm.start();
  vm.greenFlag();
  await sleep(500); // 0.3 wait + 게임시작

  // ---- (1) tuning var init (24) ----
  let v = stageVars();
  console.log('--- (1) tuning init (24 한글 변수) ---');
  const expect = {
    마법공격력:1, 발사간격:0.6, 마법탄속도:8, 관통:1, 추가발사:1, 이동속도:4,
    최대체력:5, 체력:5, 무적시간:25, 흡수범위:90, 흡수속도:6, 레벨업경험치:5,
    강화량:1, 스폰간격:1.2, 난이도주기:15,
    약한적_체력:1, 약한적_속도:1.2, 약한적_경험치:1,
    중간적_체력:3, 중간적_속도:0.9, 중간적_경험치:3,
    강한적_체력:6, 강한적_속도:0.6, 강한적_경험치:6,
  };
  let initOK = true, bad = [];
  for (const k in expect) if (Number(v[k]) !== Number(expect[k])) { initOK = false; bad.push(`${k}=${v[k]}`); }
  check('24 tuning vars initialized to defaults', initOK, bad.join(', ') || 'all OK');
  check('진행: 게임상태=1, 생존시간=0, 레벨=1, 경험치=0, 단계=0',
        v.게임상태==1 && v.생존시간==0 && v.레벨==1 && v.경험치==0 && v.단계==0,
        `state=${v.게임상태} time=${v.생존시간} lv=${v.레벨}`);
  check('조준거리 starts 99999, 조준있음=0', v.조준거리==99999 && v.조준있음==0);

  // speed up difficulty ramp so 단계 transitions within the test window
  setVar('난이도주기', 2);

  // ---- (2) enemy spawn ramp ----
  await sleep(2600); // ~2 spawns at 스폰간격 1.2 + ramp
  let en = clones('적');
  v = stageVars();
  console.log('--- (2) enemy spawner (시간 기반) ---');
  check('적 클론이 스폰됨 (>=1)', en.length >= 1, `clones=${en.length}, 적수=${v.적수}`);
  check('스폰카운트 누적 증가', Number(v.스폰카운트) >= 1, `스폰카운트=${v.스폰카운트}`);
  const types = en.map(c => Number(cloneLocal(c, '적종류')));
  check('적 클론 적종류 ∈ {1,2,3}', types.every(t => t >= 1 && t <= 3), JSON.stringify(types));
  // each clone got 내체력/내속도 from its type's tuning vars
  const hpMap = {1:1, 2:3, 3:6}, spdMap = {1:1.2, 2:0.9, 3:0.6};
  let statOK = en.every(c => {
    const ty = Number(cloneLocal(c, '적종류'));
    return Number(cloneLocal(c, '내체력')) === hpMap[ty] && Number(cloneLocal(c, '내속도')) === spdMap[ty];
  });
  check('내체력/내속도가 적종류별 튜닝 변수와 일치', statOK,
        en.map(c => `t${cloneLocal(c,'적종류')}:hp${cloneLocal(c,'내체력')}/spd${cloneLocal(c,'내속도')}`).join(' '));

  // ---- (3) survival timer + difficulty stage ----
  console.log('--- (3) 생존시간 타이머 + 단계 ---');
  check('생존시간 증가 (>=2초)', Number(v.생존시간) >= 2, `생존시간=${v.생존시간}`);
  check('단계 = floor(생존시간/난이도주기) > 0', Number(v.단계) >= 1,
        `단계=${v.단계} (생존시간=${v.생존시간}, 난이도주기=2)`);

  // ---- (4) auto-aim handshake + auto-fire ----
  console.log('--- (4) 자동 조준 핸드셰이크 + 마법탄 발사 ---');
  // with enemies present, 조준요청 broadcast&wait should reduce 조준거리 and set 조준있음
  await sleep(800);
  v = stageVars();
  check('조준있음=1 (가까운 적 발견)', Number(v.조준있음) === 1, `조준있음=${v.조준있음}, 조준거리=${Number(v.조준거리).toFixed(1)}`);
  check('조준거리 < 99999 (최솟값 리덕션 동작)', Number(v.조준거리) < 99999, v.조준거리);
  let bolts = clones('마법탄');
  check('마법탄 클론이 발사됨 (>=1)', bolts.length >= 1, `bolts=${bolts.length}`);

  // ---- (5) damage popup as NUMBER COSTUMES (no say bubbles) ----
  console.log('--- (5) 데미지 팝업 (숫자 코스튬, say 미사용) ---');
  async function fireDamage(atk, x, y) {
    setVar('마법공격력', atk);
    setVar('데미지표시값', atk);
    setVar('데미지표시x', x);
    setVar('데미지표시y', y);
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '데미지표시' });
    await sleep(230);
    const cl = clones('데미지');
    return {
      digits: cl.map(c => costumeName(c)),
      bubbles: cl.map(c => sayBubble(c)).filter(t => t !== undefined && t !== ''),
      count: cl.length,
    };
  }
  let d1 = await fireDamage(3, 0, 0);
  check('마법공격력=3 → 코스튬 "3" 렌더', d1.digits.includes('3'), JSON.stringify(d1.digits));
  check('say 말풍선 0개', d1.bubbles.length === 0, `bubbles=${d1.bubbles.length}`);
  await sleep(450);
  let d2 = await fireDamage(12, 30, 0);
  check('마법공격력=12 → 코스튬 "1"&"2" 두 자리', d2.digits.slice().sort().join(',') === '1,2', JSON.stringify(d2.digits));
  await sleep(450);
  setVar('마법공격력', 1);
  await sleep(400);
  check('데미지 클론 페이드 후 정리됨', clones('데미지').length === 0, clones('데미지').length);

  // ---- (6) level-up state machine 1→2→1 + 강화 적용 ----
  console.log('--- (6) 레벨업 → 강화 택1 → 전투 재개 ---');
  const lvBefore = Number(stageVars().레벨);
  const atkBefore = Number(stageVars().마법공격력);
  const lvupCost = Number(stageVars().레벨업경험치);
  setVar('경험치', lvupCost); // exactly one level-up worth
  await sleep(250);
  v = stageVars();
  check('경험치 충족 → 게임상태=2 (강화선택중)', Number(v.게임상태) === 2, `state=${v.게임상태}`);
  check('레벨 +1', Number(v.레벨) === lvBefore + 1, `lv ${lvBefore}→${v.레벨}`);
  check('경험치 -= 레벨업경험치 (→0)', Number(v.경험치) === 0, `경험치=${v.경험치}`);
  // pick upgrade 1 (마법공격력+)
  vm.postIOData('keyboard', { key: '1', isDown: true });
  await sleep(120);
  vm.postIOData('keyboard', { key: '1', isDown: false });
  await sleep(500);
  v = stageVars();
  check('강화1 적용: 마법공격력 += 강화량', Number(v.마법공격력) === atkBefore + 1, `atk ${atkBefore}→${v.마법공격력}`);
  check('강화완료 → 게임상태=1 (전투 재개)', Number(v.게임상태) === 1, `state=${v.게임상태}`);

  // ---- (7) clone counts bounded (no runaway 복제 폭주) ----
  console.log('--- (7) 클론 폭주 가드 ---');
  await sleep(1500);
  const cb = clones('마법탄').length, ce = clones('적').length, cg = clones('경험치보석').length;
  const total = cb + ce + cg + clones('데미지').length;
  check('마법탄 클론 상한 유지 (<120)', cb < 120, `bolts=${cb}`);
  check('적 클론 상한 유지 (<60)', ce < 60, `enemies=${ce}`);
  check('전체 클론 < 250 (Scratch 300 한도 내)', total < 250, `total=${total}`);

  // ---- (8) game over: 체력 0 → 게임상태 0, 클론 자기 삭제 ----
  console.log('--- (8) 게임오버 ---');
  setVar('경험치', 0);
  setVar('체력', 0);
  await sleep(400);
  v = stageVars();
  check('체력<1 → 게임상태=0 (게임오버)', Number(v.게임상태) === 0, `state=${v.게임상태}`);
  await sleep(400);
  check('게임오버 후 적 클론 자기 삭제', clones('적').length === 0, clones('적').length);
  check('게임오버 후 마법탄 클론 자기 삭제', clones('마법탄').length === 0, clones('마법탄').length);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'RUNTIME CHECK: SOME CHECKS FAILED' : 'RUNTIME CHECK COMPLETE — all checks passed, no exceptions.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
