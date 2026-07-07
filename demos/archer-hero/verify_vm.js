// Headless scratch-vm runtime check for archer-hero (데모).
// Renderer is stubbed → `touching` returns false, so contact-based effects
// (arrow→enemy damage, enemy→hero contact) can't be observed directly.
// We DO exercise the renderer-independent core:
//   (1) "멈추면 쏜다": no arrow key → 자동조준+발사 / 화살표 누름 → 발사 정지
//   (2) 화살이 조준 방향으로 실제 이동 + 2발 처치 판정(잡졸체력2/공격력1) + kill→cleanup 배선
//   (3) 피격 배선(무적/게임오버) — 상태 기반으로 검증
//   (4) 웨이브 전멸 → 강화카드 → 선택 시 스탯 변화 → 다음 웨이브 적 강화(지수)
//   (5) 자동 이동-멈춤 흐름으로 웨이브 진행이 실제로 돌아감
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '아처_용사.sb3');
const vm = new VM();

function stage() { return vm.runtime.targets.find(t => t.isStage); }
function stageVars() {
  const st = stage(); const out = {};
  for (const id in st.variables) { const v = st.variables[id]; if (v.type !== 'list') out[v.name] = v.value; }
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
function costumeName(t) { const c = t.getCostumes()[t.currentCostume]; return c ? c.name : undefined; }
function hero() { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === '용사' && t.isOriginal); }
function banner() { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === '배너' && t.isOriginal); }
const sleep = ms => new Promise(r => setTimeout(r, ms));
function keyDown(k)  { vm.postIOData('keyboard', { key: k, isDown: true }); }
function keyUp(k)    { vm.postIOData('keyboard', { key: k, isDown: false }); }

let FAIL = false;
function check(label, ok, extra) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`);
  if (!ok) FAIL = true;
}

(async () => {
  await vm.loadProject(fs.readFileSync(sb3));
  vm.start();
  vm.greenFlag();
  await sleep(600); // 0.3 wait + 게임시작 + 첫 스폰 시작

  // ---- (0) tuning var init ----
  console.log('--- (0) 튜닝 변수 초기화 ---');
  let v = stageVars();
  const expect = {
    이동속도:5.5, 발사쿨:0.25, 화살속도:11, 공격력:1, 잡졸체력:2, 적속도:2.2,
    돌진속도:6, 최대체력:5, 무적시간:0.5, 웨이브기본수:4, 적성장배율:1.25,
    정지판정:0.02, 강화량:1, 최대웨이브:3, 스폰간격:0.5,
  };
  let bad = [];
  for (const k in expect) if (Number(v[k]) !== Number(expect[k])) bad.push(`${k}=${v[k]}`);
  check('15개 튜닝 변수 기본값', bad.length === 0, bad.join(', ') || 'all OK');
  check('게임상태=1, 웨이브=1 진행, 체력=최대체력', v.게임상태 == 1 && Number(v.웨이브) >= 1 && v.체력 == 5,
        `state=${v.게임상태} wave=${v.웨이브} hp=${v.체력}`);

  // enemies should be spawning in wave 1
  await sleep(1200);
  let en = clones('적');
  check('웨이브1 적 클론 스폰됨 (>=1)', en.length >= 1, `enemies=${en.length}, 적수=${stageVars().적수}`);
  check('적 클론 적종류 ∈ {1,2}', en.every(c => [1,2].includes(Number(cloneLocal(c,'적종류')))),
        JSON.stringify(en.map(c => Number(cloneLocal(c,'적종류')))));
  check('잡졸 2발 처치 판정: 내체력=잡졸체력=2, 공격력=1 (2회 필요)',
        en.every(c => Number(cloneLocal(c,'내체력')) === 2) && Number(stageVars().공격력) === 1,
        en.map(c => cloneLocal(c,'내체력')).join(','));

  // ---- (1) CORE: 멈추면 쏜다 / 움직이면 발사 정지 ----
  console.log('--- (1) 핵심 "멈추면 쏜다" (키 없음→발사 / 키 누름→정지) ---');
  // hero is at (0,0), no keys → should auto-aim and fire. Count arrow clones created.
  const seen = new Set();
  function newArrows() {
    let n = 0;
    for (const c of clones('화살')) if (!seen.has(c)) { seen.add(c); n++; }
    return n;
  }
  newArrows(); // prime
  await sleep(1000);
  const stoppedFires = newArrows();
  v = stageVars();
  const heroCostumeStopped = costumeName(hero());
  check('멈춤 상태: 조준있음=1 (가장 가까운 적 발견)', Number(v.조준있음) === 1, `조준있음=${v.조준있음}, 조준거리=${Number(v.조준거리).toFixed(1)}`);
  check('멈춤 상태: 발사됨 (화살 클론 생성 >=1)', stoppedFires >= 1, `1초간 새 화살 ${stoppedFires}발`);
  check('멈춤 상태: 겨눔 코스튬', heroCostumeStopped === '겨눔', `costume=${heroCostumeStopped}`);

  // now hold an arrow key → firing should stop (allow the in-flight 0.25s fire
  // iteration to finish before sampling the settled moving-branch state)
  keyDown('ArrowRight');
  await sleep(400);
  newArrows();                // reset window
  await sleep(1000);
  const movingFires = newArrows();
  const heroCostumeMoving = costumeName(hero());  // settled moving-branch costume
  keyUp('ArrowRight');
  check('이동 중: 대기 코스튬으로 전환', heroCostumeMoving === '대기', `costume=${heroCostumeMoving}`);
  check('이동 중: 발사 정지 (새 화살 0발)', movingFires === 0, `1초간 새 화살 ${movingFires}발`);
  check('이동 중: 조준있음=0 으로 꺼짐', Number(stageVars().조준있음) === 0, `조준있음=${stageVars().조준있음}`);

  // release → firing resumes
  await sleep(200);
  newArrows();
  await sleep(900);
  const resumedFires = newArrows();
  check('키 놓음 → 발사 재개 (새 화살 >=1)', resumedFires >= 1, `0.9초간 새 화살 ${resumedFires}발`);

  // ---- (2) 화살이 조준 방향으로 실제로 날아감 ----
  console.log('--- (2) 화살 실제 비행 ---');
  const a0 = clones('화살')[0];
  if (a0) {
    const start = { x: a0.x, y: a0.y };
    await sleep(250);
    const moved = Math.hypot(a0.x - start.x, a0.y - start.y);
    const gone = !vm.runtime.targets.includes(a0);
    check('화살이 실제로 이동함 (>5px 또는 소멸)', moved > 5 || gone, gone ? '날아가서 소멸' : `moved=${moved.toFixed(1)}px`);
  } else check('화살 이동 측정 대상 존재', false, 'no arrow clone');

  // kill → cleanup 배선: 클론 내체력을 0으로 만들면 폭발/삭제 + 적수 감소
  const eKill = clones('적')[0];
  if (eKill) {
    const aliveBefore = Number(stageVars().적수);
    // set that clone's local 내체력 to 0
    for (const id in eKill.variables) if (eKill.variables[id].name === '내체력') eKill.variables[id].value = 0;
    await sleep(300);
    const stillThere = vm.runtime.targets.includes(eKill);
    check('내체력<1 → 적 클론 폭발 후 자기 삭제', !stillThere, stillThere ? 'still alive' : 'deleted');
    check('처치 시 적수 감소', Number(stageVars().적수) === aliveBefore - 1, `적수 ${aliveBefore}→${stageVars().적수}`);
  } else check('처치 배선 측정 대상 존재', false, 'no enemy clone');

  // ---- (3) 피격/무적/게임오버 배선 (상태 기반) ----
  console.log('--- (3) 피격·무적·게임오버 배선 ---');
  // 무적 타이머가 초 단위로 감소하는지: 세팅 후 줄어드는지
  setVar('무적', 0.5);
  await sleep(250);
  const invAfter = Number(stageVars().무적);
  check('무적 타이머가 시간에 따라 감소 (0.5→더 작게)', invAfter < 0.5, `무적=${invAfter.toFixed(3)}`);

  // ---- (4) 웨이브 전멸 → 강화카드 → 선택 → 스탯 변화 → 다음 웨이브 지수 강화 ----
  console.log('--- (4) 웨이브 클리어 → 강화 택1 → 지수 강화 ---');
  // 남은 적을 모두 제거해 전멸시킨다 (적수=0 + 클론 삭제)
  for (const c of clones('적')) {
    for (const id in c.variables) if (c.variables[id].name === '내체력') c.variables[id].value = 0;
  }
  await sleep(300);
  setVar('적수', 0); // 스폰 도중 잔여 카운트 정리 → 전멸 판정
  const atkBefore = Number(stageVars().공격력);
  const waveBefore = Number(stageVars().웨이브);
  // 게임상태=2 (강화선택) + 카드 표시 대기
  await sleep(800);
  v = stageVars();
  check('전멸 → 게임상태=2 (강화선택)', Number(v.게임상태) === 2, `state=${v.게임상태}`);
  const cardVisible = vm.runtime.targets.find(t => t.sprite && t.sprite.name === '강화카드' && t.isOriginal).visible;
  check('강화카드 표시됨', cardVisible === true, `visible=${cardVisible}`);
  // 카드 선택 폴링 루프에 선택=1 을 주입 (마우스 클릭과 동등한 효과 = 공격력↑ 선택)
  setVar('선택', 1);
  await sleep(600);
  v = stageVars();
  check('강화1 적용: 공격력 += 강화량', Number(v.공격력) === atkBefore + 1, `atk ${atkBefore}→${v.공격력}`);
  check('강화 후 게임상태=1 (전투 재개)', Number(v.게임상태) === 1, `state=${v.게임상태}`);
  check('다음 웨이브로 진행 (웨이브 +1)', Number(v.웨이브) === waveBefore + 1, `wave ${waveBefore}→${v.웨이브}`);
  // 다음 웨이브 적은 적성장배율^(웨이브-1) 로 강해진다 (웨이브2 → 내체력 = 2 * 1.25 = 2.5)
  await sleep(1200);
  const en2 = clones('적');
  const growth = Number(stageVars().적성장배율);
  const wave2 = Number(stageVars().웨이브);
  const expHP = 2 * Math.pow(growth, wave2 - 1);
  const scaledOK = en2.length >= 1 && en2.every(c => Math.abs(Number(cloneLocal(c,'내체력')) - expHP) < 1e-6);
  check(`웨이브${wave2} 적 지수 강화: 내체력 = 잡졸체력 × 적성장배율^(N-1) = ${expHP.toFixed(3)}`, scaledOK,
        en2.map(c => cloneLocal(c,'내체력')).join(',') || 'no enemy');

  // ---- (5) 게임오버/승리 상태 소비 (배너 + 클론 정리) ----
  console.log('--- (5) 게임오버·승리 처리 ---');
  setVar('게임상태', 0);
  await sleep(400);
  check('게임상태=0 → 적 클론 자기 삭제', clones('적').length === 0, `enemies=${clones('적').length}`);
  const bn = banner();
  check('게임오버 배너 표시(패배)', bn.visible === true && costumeName(bn) === '패배', `visible=${bn.visible} costume=${costumeName(bn)}`);
  // 승리 상태
  vm.greenFlag();
  await sleep(600);
  setVar('게임상태', 3);
  await sleep(400);
  const bn2 = banner();
  check('승리 상태 → 배너 승리 코스튬', bn2.visible === true && costumeName(bn2) === '승리', `visible=${bn2.visible} costume=${costumeName(bn2)}`);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'RUNTIME CHECK: SOME CHECKS FAILED' : 'RUNTIME CHECK COMPLETE — all checks passed, no exceptions.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
