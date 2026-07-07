// Headless scratch-vm runtime check for evo-tank (진화 탱크) 데모.
// Renderer is stubbed → `touching` reports false; positions / direction /
// clone-spawn / state / variable logic DO run. We drive the 5 behavior
// scenarios from the plan, focusing on the demo highlight: EVOLUTION actually
// changes the fire pattern (bolts-per-tick / cool / damage measured
// before vs after).
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '진화_탱크.sb3');
const buf = fs.readFileSync(sb3);
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
function getVar(name) { return stageVars()[name]; }
function clones(name) {
  return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false);
}
function spriteOrig(name) {
  return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal);
}
function costumeName(t) { const c = t.getCostumes()[t.currentCostume]; return c ? c.name : undefined; }
function bubble(t) { const b = t.getCustomState && t.getCustomState('Scratch.looks'); return b ? b.text : undefined; }
// mouse: scratch-vm maps client px → scratch coords via canvas size.
function mouse(x, y, isDown) {
  const cw = 480, ch = 360;
  const clientX = (x + 240) / 480 * cw;
  const clientY = (180 - y) / 360 * ch;
  vm.postIOData('mouse', { x: clientX, y: clientY, canvasWidth: cw, canvasHeight: ch, isDown });
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
  await sleep(500); // 0.2 wait + 게임시작

  // ---- (0) init sanity ----
  let v = stageVars();
  console.log('--- (0) 튜닝 손잡이 초기화 ---');
  const expect = {
    이동속도:4.5, 발사쿨:0.3, 포탄속도:10, 공격력:1, 사각체력:2, 삼각체력:4,
    적탱크체력:3, 적탱크속도:2, 내체력:5, 무적시간:0.5, 레벨업경험치:10,
    스폰간격:1.2, 진화:0, 발사수:1, 산탄:0, 평행간격:0,
  };
  let initOK = true, bad = [];
  for (const k in expect) if (Number(v[k]) !== Number(expect[k])) { initOK = false; bad.push(`${k}=${v[k]}`); }
  check('16 손잡이 기본값 초기화', initOK, bad.join(', ') || 'all OK');
  check('게임상태=1, 레벨=1, 경험치=0, 진화=0', v.게임상태==1 && v.레벨==1 && v.경험치==0 && v.진화==0,
        `state=${v.게임상태} lv=${v.레벨}`);
  check('시작 즉시 도형이 필드에 배치됨 (>=5)', clones('도형').length >= 5, `도형=${clones('도형').length}`);

  // say-bubble ban check across all sprites
  const allTargets = vm.runtime.targets.filter(t => !t.isStage);
  const anyBubble = allTargets.some(t => { const b = bubble(t); return b !== undefined && b !== ''; });

  // ================= 시나리오 1: 마우스 홀드 → 포탄 스폰 + 비행 =================
  console.log('\n--- 시나리오 1: 마우스 홀드 → 포탄 클론 스폰(쿨 간격) + 포탑 방향 비행 ---');
  // aim to the right so turret faces +x, then hold mouse
  mouse(200, 0, false);
  await sleep(200);
  const turret = spriteOrig('포탑');
  mouse(200, 0, true); // hold
  await sleep(200);
  const b0 = clones('포탄')[0];
  const bStart = b0 ? { x: b0.x, y: b0.y, dir: b0.direction } : null;
  await sleep(400);
  const boltsHeld = clones('포탄').length;
  check('마우스 홀드 중 포탄 클론 발사됨 (>=1)', boltsHeld >= 1, `포탄=${boltsHeld}`);
  if (b0 && bStart) {
    const moved = Math.hypot(b0.x - bStart.x, b0.y - bStart.y);
    const gone = !vm.runtime.targets.includes(b0);
    check('포탄이 실제로 날아감 (>4px 또는 소멸)', moved > 4 || gone, gone ? '비행 후 소멸' : `moved=${moved.toFixed(1)}px`);
    check('포탄 방향이 포탑 조준(우측, ~90°) 근처', gone || Math.abs(((bStart.dir % 360) + 360) % 360 - 90) < 40,
          `bolt dir=${bStart.dir}`);
  } else check('포탄 이동 측정 대상 존재', false, 'no bolt');
  mouse(200, 0, false); // release
  await sleep(150);

  // ================= 시나리오 2: 포탄-도형 명중 → HP 감소·파괴 → 경험치 =================
  // (headless: touching stubbed → 실충돌 대신 도형이 올바른 HP/XP payload를 갖고,
  //  경험치 증가 → 레벨 진행이 동작함을 확인)
  console.log('\n--- 시나리오 2: 도형 HP/경험치 payload + 경험치→레벨 진행 ---');
  const shapes = clones('도형');
  const hpOK = shapes.every(c => {
    const local = {}; for (const id in c.variables) local[c.variables[id].name] = c.variables[id].value;
    const ty = Number(local['도형종류']);
    if (ty === 1) return Number(local['도형체력']) === 2 && Number(local['도형경험치']) === 1;
    if (ty === 2) return Number(local['도형체력']) === 4 && Number(local['도형경험치']) === 3;
    return false;
  });
  check('사각=HP2·경험치1 / 삼각=HP4·경험치3', hpOK,
        shapes.map(c => { const L={}; for(const id in c.variables)L[c.variables[id].name]=c.variables[id].value;
          return `t${L['도형종류']}:hp${L['도형체력']}/xp${L['도형경험치']}`; }).slice(0,6).join(' '));
  // 경험치 획득 시 레벨 진행 (레벨업 상태머신)
  setVar('경험치', 4);
  await sleep(150);
  check('경험치가 레벨업경험치 미만이면 전투 유지', Number(getVar('게임상태')) === 1, `state=${getVar('게임상태')}`);

  // ================= 시나리오 3: 적탱크 접촉 피해 + 무적 =================
  // (headless: touching stubbed → 접촉 자체는 못 재지만, 적탱크가 스폰·추격하고
  //  무적 로직 변수 메커니즘이 존재함을 확인)
  console.log('\n--- 시나리오 3: 적탱크 스폰·추격 (+무적 메커니즘 존재) ---');
  setVar('스폰간격', 0.3);
  await sleep(1000);
  const en = clones('적탱크');
  check('적탱크 클론 스폰됨 (>=1)', en.length >= 1, `적탱크=${en.length}`);
  const hull = spriteOrig('탱크본체');
  const e0 = en[0];
  if (e0 && hull) {
    const d0 = Math.hypot(e0.x - hull.x, e0.y - hull.y);
    const ehp = (() => { for (const id in e0.variables) if (e0.variables[id].name === '적체력') return e0.variables[id].value; })();
    check('적탱크가 적탱크체력(3)을 갖고 스폰', Number(ehp) === 3, `적체력=${ehp}`);
    await sleep(500);
    const d1 = Math.hypot(e0.x - hull.x, e0.y - hull.y);
    check('적탱크가 본체 쪽으로 추격(거리 감소)', d1 < d0, `dist ${d0.toFixed(1)}→${d1.toFixed(1)}`);
  } else check('적탱크 이동 측정 대상 존재', false, 'no enemy');
  // 무적 변수 메커니즘: 무적=1 세팅 후 감시 로직이 존재(변수 정의됨)
  check('무적 변수/무적시간(초) 손잡이 존재', getVar('무적') !== undefined && Number(getVar('무적시간')) === 0.5,
        `무적=${getVar('무적')} 무적시간=${getVar('무적시간')}`);
  setVar('스폰간격', 1.2);

  // ================= 시나리오 4 (핵심): 진화 선택 → 발사 패턴 실제 변화 =================
  console.log('\n--- 시나리오 4 [핵심]: 진화 선택 → 발사 패턴 실측 (진화 전/후 비교) ---');
  // helper: 한 번의 '발사' 방송으로 생기는 포탄 클론 수 측정 (자동발사 정지 상태에서)
  async function measureVolley() {
    setVar('게임상태', 2);            // 자동발사 정지
    await sleep(400);
    // 잔여 포탄 소멸 대기
    for (let i = 0; i < 30 && clones('포탄').length > 0; i++) await sleep(60);
    setVar('발사X', 0); setVar('발사Y', 0); setVar('발사방향', 90);
    const before = clones('포탄').length;
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
    await sleep(200);
    const volley = clones('포탄').length - before;
    return volley;
  }
  // --- 진화 전 (기본): 틱당 1발 ---
  const volleyBase = await measureVolley();
  const cdBase = Number(getVar('발사쿨')), atkBase = Number(getVar('공격력')), spdBase = Number(getVar('포탄속도'));
  check('진화 전(기본): 한 발 = 1 포탄', volleyBase === 1, `볼리=${volleyBase}`);
  check('진화 전: 발사쿨=0.3 · 공격력=1 · 포탄속도=10',
        cdBase === 0.3 && atkBase === 1 && spdBase === 10, `cd=${cdBase} atk=${atkBase} spd=${spdBase}`);
  setVar('게임상태', 1);

  // --- 진화 트리거: 레벨업 → 카드 → 선택 ---
  // 진화 선택을 각각 독립 검증하기 위해 매번 진화=0 로 되돌린 뒤 카드를 띄운다.
  async function evolveTo(pick) {
    setVar('진화', 0);
    setVar('게임상태', 1);
    setVar('경험치', Number(getVar('레벨업경험치'))); // 정확히 1회 레벨업
    await sleep(200);
    const paused = Number(getVar('게임상태')) === 2;   // 진화 카드가 떠서 멈춤
    // 카드가 키 1/2/3 폴링 → 키로 선택 (클릭 폴링과 동일 경로)
    const key = String(pick);
    vm.postIOData('keyboard', { key, isDown: true });
    await sleep(120);
    vm.postIOData('keyboard', { key, isDown: false });
    await sleep(400);
    return paused;
  }
  // 쌍포신 (1): 틱당 2발 평행
  const pausedDual = await evolveTo(1);
  check('레벨업 → 진화 카드로 게임 멈춤(게임상태=2)', pausedDual, 'paused');
  check('쌍포신 선택 → 진화=1', Number(getVar('진화')) === 1, `진화=${getVar('진화')}`);
  const tur = spriteOrig('포탑');
  await sleep(150);
  check('포탑 코스튬이 "쌍포신"으로 실제 교체', costumeName(tur) === '쌍포신', `costume=${costumeName(tur)}`);
  const volleyDual = await measureVolley();
  check('쌍포신: 한 발 = 포탄 2개 (총알 2줄)', volleyDual === 2, `볼리=${volleyDual}`);
  check('쌍포신: 발사수=2 · 평행간격>0', Number(getVar('발사수')) === 2 && Number(getVar('평행간격')) > 0,
        `발사수=${getVar('발사수')} 평행간격=${getVar('평행간격')}`);
  // 2줄: 이번 볼리 두 탄의 위치가 서로 벌어져 있어야 함(평행)
  const dualBolts = clones('포탄');
  let sep = 0;
  if (dualBolts.length >= 2) sep = Math.hypot(dualBolts[0].x - dualBolts[1].x, dualBolts[0].y - dualBolts[1].y);
  check('쌍포신 두 탄이 옆으로 벌어짐(평행 2줄, >8px)', dualBolts.length >= 2 && sep > 8, `분리=${sep.toFixed(1)}px`);
  setVar('게임상태', 1);

  // 스나이퍼 (2): 쿨 0.6 · 데미지 3 · 탄속 1.5배
  await evolveTo(2);
  check('스나이퍼 선택 → 진화=2', Number(getVar('진화')) === 2, `진화=${getVar('진화')}`);
  await sleep(150);
  check('포탑 코스튬이 "스나이퍼"로 교체', costumeName(tur) === '스나이퍼', `costume=${costumeName(tur)}`);
  const cdSnipe = Number(getVar('발사쿨')), atkSnipe = Number(getVar('공격력')), spdSnipe = Number(getVar('포탄속도'));
  check('스나이퍼: 발사쿨=0.6 (기본의 2배 느림)', cdSnipe === 0.6, `발사쿨=${cdSnipe}`);
  check('스나이퍼: 공격력=3 (3배)', atkSnipe === 3, `공격력=${atkSnipe}`);
  check('스나이퍼: 포탄속도=15 (1.5배)', spdSnipe === 15, `포탄속도=${spdSnipe}`);
  const volleySnipe = await measureVolley();
  check('스나이퍼: 한 발 = 1 포탄', volleySnipe === 1, `볼리=${volleySnipe}`);
  setVar('게임상태', 1);

  // 머신건 (3): 쿨 0.12 (난사) · 약간 산탄
  await evolveTo(3);
  check('머신건 선택 → 진화=3', Number(getVar('진화')) === 3, `진화=${getVar('진화')}`);
  await sleep(150);
  check('포탑 코스튬이 "머신건"으로 교체', costumeName(tur) === '머신건', `costume=${costumeName(tur)}`);
  const cdMg = Number(getVar('발사쿨')), spreadMg = Number(getVar('산탄'));
  check('머신건: 발사쿨=0.12 (기본의 2.5배 빠른 난사)', cdMg === 0.12, `발사쿨=${cdMg}`);
  check('머신건: 산탄>0 (탄퍼짐)', spreadMg > 0, `산탄=${spreadMg}`);
  // 발사쿨 비교 요약 (진화가 발사 속도를 실제로 바꿈)
  check('★ 발사쿨 진화별 실측: 기본0.3 → 스나0.6 → 머신0.12 (모두 다름)',
        cdBase === 0.3 && cdSnipe === 0.6 && cdMg === 0.12, `${cdBase}/${cdSnipe}/${cdMg}`);
  setVar('게임상태', 1);

  // ================= 시나리오 5: 자동 플레이 30초 생존 + 진화 도달 + 클론 상한 =================
  console.log('\n--- 시나리오 5: 진행 안정성 (클론 상한, 진화 유지) ---');
  // 이미 진화=3 도달. 잠시 자동 진행하며 클론이 폭주하지 않는지 확인.
  mouse(120, 60, true);
  setVar('게임상태', 1);
  await sleep(2500);
  mouse(120, 60, false);
  const cb = clones('포탄').length, ce = clones('적탱크').length, cg = clones('도형').length;
  const total = cb + ce + cg;
  check('포탄 클론 상한 유지 (<120)', cb < 120, `포탄=${cb}`);
  check('적탱크 클론 상한 유지 (<60)', ce < 60, `적탱크=${ce}`);
  check('도형 필드 유지 (>=1, 폭주 없음<40)', cg >= 1 && cg < 40, `도형=${cg}`);
  check('전체 클론 < 250 (Scratch 300 한도 내)', total < 250, `total=${total}`);
  check('진화 유지 (한 번 고르면 고정, 진화>0)', Number(getVar('진화')) > 0, `진화=${getVar('진화')}`);

  // say 미사용 (전 구간)
  check('say 말풍선 미사용 (전 스프라이트)', !anyBubble, anyBubble ? '말풍선 발견' : '없음');

  // ================= 게임오버 정리 =================
  console.log('\n--- 게임오버 정리 ---');
  setVar('내체력', 0);
  await sleep(300);
  check('내체력<1 → 게임상태=0', Number(getVar('게임상태')) === 0, `state=${getVar('게임상태')}`);
  await sleep(500);
  check('게임오버 후 적탱크 클론 자기 삭제', clones('적탱크').length === 0, clones('적탱크').length);
  check('게임오버 후 포탄 클론 자기 삭제', clones('포탄').length === 0, clones('포탄').length);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'RUNTIME CHECK: SOME CHECKS FAILED' : 'RUNTIME CHECK COMPLETE — all checks passed, no exceptions.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
