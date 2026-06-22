// Headless scratch-vm runtime check for rogue-knight.
// Renderer is stubbed → touching returns false; we verify coordinate/state logic only.
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '로그_나이트.sb3');
const buf = fs.readFileSync(sb3);

const vm = new VM();

function stageVars() {
  const st = vm.runtime.targets.find(t => t.isStage);
  const out = {};
  for (const id in st.variables) {
    const v = st.variables[id];
    if (v.type !== 'list') out[v.name] = v.value;
  }
  return out;
}
function knight() { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === '기사' && !t.isOriginal === false); }
function knightOrig() { return vm.runtime.targets.find(t => t.getName && t.getName() === '기사'); }
function enemyClones() {
  return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === '적' && t.isOriginal === false);
}
function platformClones() {
  return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === '발판' && t.isOriginal === false);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  await vm.loadProject(buf);
  vm.start();
  vm.greenFlag();
  await sleep(500); // through 0.3 wait + 게임시작 + 방빌드

  let v = stageVars();
  console.log('--- after green flag + room build ---');
  const expect = {공격력:1,최대체력:5,체력:5,이동속도:4,점프력:12,중력:-1,점프횟수상한:2,
    대시거리:90,대시쿨:30,무적시간:25,
    약한적_체력:1,약한적_속도:2.0,중간적_체력:2,중간적_속도:1.3,강한적_체력:4,강한적_속도:0.8,
    강화량:1};
  let initOK = true;
  for (const k in expect) {
    if (Number(v[k]) !== Number(expect[k])) { console.log('  INIT MISMATCH', k, v[k], '!=', expect[k]); initOK=false; }
  }
  console.log('  tuning init values OK:', initOK);
  console.log('  게임상태:', v['게임상태'], ' 방번호:', v['방번호'], ' 방목표:', v['방목표']);

  await sleep(900); // enemy spawn loop (방목표=3, wait 0.15 each + 0.2 init)
  const enemies = enemyClones();
  const platforms = platformClones();
  console.log('  enemy clones spawned:', enemies.length, '(expect ~3)');
  console.log('  platform clones:', platforms.length, '(room1 set => 3)');
  console.log('  적수:', stageVars()['적수']);

  // ── Enemy type system: room 1 = all WEAK (type 1, HP=약한적_체력, size small) ──
  function cloneLocal(clone, name) {
    for (const id in clone.variables) {
      if (clone.variables[id].name === name) return clone.variables[id].value;
    }
    return undefined;
  }
  console.log('--- enemy types (room 1 → all WEAK, type 1) ---');
  const room1types = enemies.map(c => Number(cloneLocal(c, '적종류')));
  const room1hp    = enemies.map(c => Number(cloneLocal(c, '내체력')));
  const room1spd   = enemies.map(c => Number(cloneLocal(c, '내속도')));
  const room1size  = enemies.map(c => Number(c.size));
  console.log('  적종류:', room1types, ' all weak(1):', room1types.every(t => t === 1));
  console.log('  내체력:', room1hp, ' == 약한적_체력(1):', room1hp.every(h => h === 1));
  console.log('  내속도:', room1spd, ' == 약한적_속도(2):', room1spd.every(s => s === 2));
  // NOTE: size(set size 45/60/78) is only applied when a renderer is present
  // (scratch-vm RenderedTarget.setSize early-returns headless). 외형(크기/색)은
  // 구조로만 확인 가능 — 종류 분기가 내체력/내속도를 종류별로 정확히 세팅하는 것이
  // 곧 외형 분기도 같은 substack 에서 실행됨을 보장한다.
  console.log('  size:', room1size, ' (headless: 렌더러 없어 set size 미적용 — 외형은 구조로 확인)');

  // Knight jump test: record y, press up, see y rise (gravity/VY physics)
  const kn = knightOrig();
  const y0 = kn.y;
  vm.postIOData('keyboard', {key:'ArrowUp', isDown:true});
  await sleep(60);
  vm.postIOData('keyboard', {key:'ArrowUp', isDown:false});
  await sleep(120);
  const y1 = kn.y;
  console.log('--- jump physics ---');
  console.log('  knight y before:', y0.toFixed(1), ' after up-press:', y1.toFixed(1), ' rose:', (y1 > y0));

  // Move right test
  const x0 = kn.x;
  vm.postIOData('keyboard', {key:'ArrowRight', isDown:true});
  await sleep(150);
  vm.postIOData('keyboard', {key:'ArrowRight', isDown:false});
  const x1 = kn.x;
  console.log('--- move ---');
  console.log('  knight x before:', x0.toFixed(1), ' after right:', x1.toFixed(1), ' moved right:', (x1 > x0));

  // Force clear: set 처치수 >= 방목표 to test state 1->2 transition
  const st = vm.runtime.targets.find(t => t.isStage);
  function setVar(name, val){ for (const id in st.variables){ if (st.variables[id].name===name){ st.variables[id].value=val; } } }
  setVar('처치수', 99);
  await sleep(200);
  console.log('--- clear → upgrade transition ---');
  console.log('  게임상태 (expect 2):', stageVars()['게임상태']);

  // Pick upgrade 1 (공격력+)
  const atkBefore = Number(stageVars()['공격력']);
  vm.postIOData('keyboard', {key:'1', isDown:true});
  await sleep(100);
  vm.postIOData('keyboard', {key:'1', isDown:false});
  await sleep(500); // upgrade apply + 다음방 + 방빌드 (방빌드 resets 처치수=0)
  const av = stageVars();
  console.log('--- upgrade applied + next room ---');
  console.log('  공격력 before:', atkBefore, ' after:', av['공격력'], ' (강화량=1 → +1):', Number(av['공격력'])===atkBefore+1);
  console.log('  방번호 (expect 2):', av['방번호'], ' 게임상태 (expect 1):', av['게임상태'], ' 방목표 (expect 4):', av['방목표'], ' 처치수 (expect 0):', av['처치수']);

  // ── Room 2 enemies: types are weak(1) OR mid(2) (pick random 1~2) ──
  await sleep(800); // let room 2 spawn
  const room2 = enemyClones();
  const room2types = room2.map(c => Number(cloneLocal(c, '적종류')));
  console.log('--- enemy types (room 2 → weak/mid, 1 or 2) ---');
  console.log('  적종류:', room2types, ' all in {1,2}:', room2types.every(t => t === 1 || t === 2));

  // ── Force room 3 to verify STRONG enemies (type 2 or 3) appear with strong stats ──
  // Clear leftover room-2 clones first (a real 다음방 transition deletes them; here we
  // jump rooms directly so we remove them by hand for a clean type-set assertion).
  for (const c of enemyClones()) vm.runtime.disposeTarget(c);
  setVar('방번호', 3);
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '방빌드' });
  await sleep(1300); // room 3 spawn (방목표 = 2+3 = 5)
  const room3 = enemyClones();
  const room3types = room3.map(c => Number(cloneLocal(c, '적종류')));
  const strongs = room3.filter(c => Number(cloneLocal(c, '적종류')) === 3);
  console.log('--- enemy types (room 3 → mid/strong, 2 or 3) ---');
  console.log('  적종류:', room3types, ' all in {2,3}:', room3types.every(t => t === 2 || t === 3));
  if (strongs.length) {
    const s = strongs[0];
    console.log('  strong sample → 내체력:', cloneLocal(s, '내체력'),
                '(==강한적_체력 4):', Number(cloneLocal(s, '내체력')) === 4,
                ' 내속도:', cloneLocal(s, '내속도'), '(==강한적_속도 0.8):', Number(cloneLocal(s, '내속도')) === 0.8,
                ' (size set 78 — 렌더러 필요, 구조로 확인)');
  } else {
    console.log('  (no strong enemy in this random draw — type set still {2,3})');
  }
  // mid sample check (size 60, color differs from weak)
  const mids = room3.filter(c => Number(cloneLocal(c, '적종류')) === 2);
  if (mids.length) {
    const m = mids[0];
    console.log('  mid sample → 내체력:', cloneLocal(m, '내체력'),
                '(==중간적_체력 2):', Number(cloneLocal(m, '내체력')) === 2,
                ' (size set 60 — 렌더러 필요, 구조로 확인)');
  }

  // ── Damage popup renders NUMBER COSTUMES (not say bubbles); value follows 공격력 ──
  console.log('--- damage popup as number costumes (데미지표시 = 공격력) ---');
  function damageClones() {
    return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === '데미지' && t.isOriginal === false);
  }
  function costumeName(target) {
    const c = target.getCostumes()[target.currentCostume];
    return c ? c.name : undefined;
  }
  function bubbleText(target) {
    const b = target.getCustomState && target.getCustomState('Scratch.looks');
    return b ? b.text : undefined;
  }
  // confirm NO say bubble anywhere on damage clones (we use costumes now)
  // helper: fire a popup with given 공격력 value, return shown digit-costume names
  async function fireDamageAndRead(atk, x, y) {
    setVar('공격력', atk);
    setVar('데미지표시값', atk); // mirrors enemy: 데미지표시값 = 공격력
    setVar('데미지표시x', x);
    setVar('데미지표시y', y);
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '데미지표시' });
    await sleep(210); // both digit clones created (0.12 wait between) + costume switched, before fade-delete
    const cl = damageClones();
    const digits = cl.map(c => costumeName(c));
    const bubbles = cl.map(c => bubbleText(c)).filter(t => t !== undefined && t !== '');
    return { count: cl.length, digits, bubbles };
  }

  // (1) 공격력 = 2 → one-digit popup, costume "2", no say bubble
  let r1 = await fireDamageAndRead(2, 0, -90);
  console.log('  공격력=2 → clones:', r1.count, ' digit costumes:', JSON.stringify(r1.digits),
              ' shows "2":', r1.digits.includes('2'), ' say bubbles (expect 0):', r1.bubbles.length);
  await sleep(500);

  // (2) 공격력 = 12 → two-digit popup, costumes "1" and "2"
  let r2 = await fireDamageAndRead(12, 40, -90);
  const set2 = r2.digits.slice().sort().join(',');
  console.log('  공격력=12 → clones:', r2.count, ' digit costumes:', JSON.stringify(r2.digits),
              ' shows 1&2:', (set2 === '1,2'), ' say bubbles (expect 0):', r2.bubbles.length);
  await sleep(500);

  // (3) 공격력 = 7 → costume "7" (proves value follows 공격력, not magic number)
  let r3 = await fireDamageAndRead(7, -40, -90);
  console.log('  공격력=7 → digit costumes:', JSON.stringify(r3.digits), ' shows "7":', r3.digits.includes('7'));
  await sleep(500);
  console.log('  popups cleaned up after fade (expect 0):', damageClones().length);

  // restore 공격력 to default
  setVar('공격력', 1);

  // Game over: set 체력 to 0 (and ensure not in a clear state)
  setVar('처치수', 0);
  setVar('체력', 0);
  await sleep(250);
  console.log('--- game over ---');
  console.log('  게임상태 (expect 0):', stageVars()['게임상태']);

  vm.quit && vm.quit();
  console.log('\\nRUNTIME CHECK COMPLETE — no exceptions thrown.');
  process.exit(0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
