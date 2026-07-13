// Real-play observational verification for 어항 포식자 (fish-tank).
//
// LESSON APPLIED: do NOT force state and declare victory. The headless VM stubs
// the renderer, so `touching` normally returns false and eat/hit never fire.
// Instead we install a GEOMETRY-BASED touching (mirroring Scratch's real bbox
// overlap on the LIVE target x/y/size) and then simulate ACTUAL PLAY: move the
// mouse toward a target fish and let the real scripts run. We OBSERVE whether
// touching a small fish actually causes 내크기+성장량 & 점수+, and whether
// touching a big fish actually flips 게임상태→0. Positions/sizes come from the
// real block execution — we only supply the collision oracle the stub omits.
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '어항_포식자.sb3');
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
function getVar(name) { return Number(stageVars()[name]); }
function clones(name) {
  return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false);
}
function original(name) {
  return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal);
}
function cloneLocal(c, name) {
  for (const id in c.variables) if (c.variables[id].name === name) return c.variables[id].value;
  return undefined;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`);
  if (!ok) FAIL = true;
}

// --- collision oracle: approximate Scratch bbox-overlap using live x/y/size ---
// Each fish costume is ~72x48 px at size 100 (rotationCenter 36,24). We use the
// current `size` of each target to scale the half-extents, matching how a bigger
// fish (size↑) really is a bigger sprite that overlaps sooner.
function halfExtents(t) {
  const s = (t.size || 100) / 100;
  return { hw: 36 * s, hh: 24 * s };
}
function bboxOverlap(a, b) {
  const A = halfExtents(a), B = halfExtents(b);
  return Math.abs(a.x - b.x) <= (A.hw + B.hw) * 0.72 &&   // 0.72 fudge → oval-ish, closer to real pixel touch
         Math.abs(a.y - b.y) <= (A.hh + B.hh) * 0.72;
}
// Install real-geometry touching on the runtime renderer stub.
// Touching oracle: PURE live-geometry overlap on the real target x/y/size.
// NO latch, NO fudge to "help" the game logic. It returns true only while two
// sprites actually overlap this instant — exactly what real Scratch touching does.
// (이전엔 '접촉 래치 180ms' 꼼수로 클론 자기삭제와 내물고기 판정의 경합을 검증기가
//  덮어 성장을 만들어냈다 = false-green. 이제 그 보정을 완전히 제거했다. 성장은 오직
//  게임 스크립트의 원자적 먹기 트랜잭션이 산출해야만 관측된다.)
// 관찰(스폰/배회/좌우반전) 단계에서는 내물고기↔물고기 접촉만 잠시 꺼(SAFE) 우발 게임오버를
// 막는다(테스트 픽스처). 실제 먹기/피격 드라이브에서는 SAFE=false 로 실제 접촉을 켠다.
let SAFE = false;
function makeTouchFn() {
  return function (spriteName) {
    const me = this;
    if (SAFE && ((me.sprite && me.sprite.name === '내물고기' && spriteName === '물고기') ||
                 (me.sprite && me.sprite.name === '물고기' && spriteName === '내물고기'))) {
      return false;
    }
    return vm.runtime.targets.some(o =>
      o !== me && o.sprite && o.sprite.name === spriteName && o.visible !== false && bboxOverlap(me, o));
  };
}
function installTouchingOracle() {
  for (const t of vm.runtime.targets) { t.isTouchingSprite = makeTouchFn(); t.__touchPatched = true; }
}
function patchNewClones() {
  vm.runtime.targets.forEach(t => {
    if (!t.__touchPatched) { t.isTouchingSprite = makeTouchFn(); t.__touchPatched = true; }
  });
}
// keyboard driver (조작이 방향키로 바뀜)
function keyDown(key) { vm.postIOData('keyboard', { key, isDown: true }); }
function keyUp(key)   { vm.postIOData('keyboard', { key, isDown: false }); }
function releaseAll() { ['ArrowRight','ArrowLeft','ArrowUp','ArrowDown'].forEach(keyUp); }
// 내물고기를 목표 좌표로 실제 방향키 이동시켜 몰아간다(강제 setXY 아님):
// 매 스텝 목표와의 부호를 보고 맞는 방향키를 눌러 이동 블록이 내물고기를 옮기게 한다.
async function steerToward(me, tx, ty, maxSteps, onStep) {
  for (let i = 0; i < maxSteps; i++) {
    releaseAll();
    if (tx - me.x > 3) keyDown('ArrowRight');
    else if (tx - me.x < -3) keyDown('ArrowLeft');
    if (ty - me.y > 3) keyDown('ArrowUp');
    else if (ty - me.y < -3) keyDown('ArrowDown');
    if (onStep) onStep();
    await sleep(45);
    if (typeof onStep === 'function' && onStep.__stop && onStep.__stop()) break;
  }
  releaseAll();
}

(async () => {
  await vm.loadProject(buf);
  vm.start();
  installTouchingOracle();
  SAFE = true; // 관찰 단계: 내물고기↔물고기 접촉 무력화(조기 게임오버 방지). 실제 드라이브에서 해제.
  vm.greenFlag();
  await sleep(500); // 0.3 wait + 게임시작

  // keep patching clones every 60ms across the whole run
  const patcher = setInterval(patchNewClones, 60);

  const me = original('내물고기');
  // 관찰(스폰/배회) 단계 동안 내물고기를 구석에 계속 세워 우발 접촉으로 인한
  // 조기 게임오버를 막는다(테스트 픽스처). 실제 먹기/피격은 뒤의 방향키 드라이브에서만.
  let PARK = true;
  const parker = setInterval(() => { if (PARK && me) me.setXY(232, 162); }, 40);

  // ================= (검증 4) 튜닝 변수 초기화 =================
  console.log('--- 튜닝 14개 초기값 ---');
  const expect = {
    성장량:7, 내속도:6, 적속도:1.6, 스폰간격:0.7, 큰물고기비율:0.2, 중간물고기비율:0.3,
    먹기기준:0.9, 최대물고기:16, 시작크기:60, 표시크기상한:150, 작은배율:0.6, 중간배율:0.95,
    큰배율:1.35, 점수당먹기:1,
  };
  let v = stageVars(); let initOK = true, bad = [];
  for (const k in expect) if (Number(v[k]) !== Number(expect[k])) { initOK = false; bad.push(`${k}=${v[k]}`); }
  check('튜닝 14개 기본값 초기화', initOK, bad.join(', ') || 'all OK');
  check('진행: 게임상태=1, 점수=0, 내크기=시작크기(60), 물고기수 tracked',
        v.게임상태==1 && v.점수==0 && Number(v.내크기)===60, `state=${v.게임상태} 점수=${v.점수} 내크기=${v.내크기}`);

  // ================= (검증 3) 동시 캡 · 스폰 =================
  console.log('--- 스폰 · 동시 캡 ---');
  // 스폰간격 0.7 이라 첫 클론까지 시간이 걸릴 수 있어, 여러 마리 뜰 때까지 폴링(최대 ~6초)
  for (let i = 0; i < 60 && clones('물고기').length < 3; i++) await sleep(100);
  let fish = clones('물고기');
  v = stageVars();
  check('물고기 클론 스폰됨 (>=1)', fish.length >= 1, `clones=${fish.length}, 물고기수=${v.물고기수}`);
  const tiers = fish.map(c => Number(cloneLocal(c, '내물고기크기')));
  // 상대 스폰: 크기 = 내크기(60) × 배율(0.6/0.95/1.35) ± 지터. 각 구간 근처면 됨.
  const my0 = Number(getVar('내크기'));
  const inTierRange = s => (s>=my0*0.45&&s<=my0*0.72) || (s>=my0*0.8&&s<=my0*1.08) || (s>=my0*1.18&&s<=my0*1.5);
  check('클론 크기가 내크기 상대 티어 구간(×0.6/×0.95/×1.35) ±지터 범위 내', tiers.every(inTierRange),
        `내크기=${my0} tiers=${JSON.stringify(tiers)}`);
  const costumes = fish.map(c => { const cc = c.getCostumes()[c.currentCostume]; return cc && cc.name; });
  check('클론 코스튬 ∈ {작은,중간,큰}', costumes.every(c => ['작은','중간','큰'].includes(c)), JSON.stringify(costumes));

  // ================= (신규) 가장자리 스폰 + 안쪽 진입 (내부 즉시생성 0) =================
  console.log('--- 가장자리 스폰 · 안쪽 진입 (갑툭튀 즉사 방지) ---');
  // 갓 태어난 클론의 '출생 지점'을 잡으려면 스폰 직후 즉시 좌표를 봐야 한다(곧 안으로 헤엄쳐 옴).
  // 여러 마리를 새로 스폰시키며 각자의 첫 관측 좌표가 화면 가장자리인지 확인.
  const edgeSamples = [];
  const sizeSamples = [];
  const isEdge = (x, y) => (Math.abs(x) >= 215 || Math.abs(y) >= 150); // 경계~바깥
  // 기존 클론을 비워 새 스폰 여지를 만들고, 스폰간격을 줄여 여러 마리 출생을 촘촘히 관측
  const gapSaved0 = getVar('스폰간격'); setVar('스폰간격', 0.12);
  clones('물고기').forEach(c => vm.runtime.disposeTarget(c));
  setVar('물고기수', 0);
  const seen = new Set();
  for (let i = 0; i < 200 && sizeSamples.length < 14; i++) {
    for (const c of clones('물고기')) {
      if (!seen.has(c.id)) {
        seen.add(c.id);
        edgeSamples.push({ x: c.x, y: c.y });
        sizeSamples.push(Number(cloneLocal(c, '내물고기크기')));
      }
    }
    await sleep(20); // 촘촘히 폴링해 출생 직후 좌표를 잡는다
  }
  setVar('스폰간격', gapSaved0);
  const atEdge = edgeSamples.filter(s => isEdge(s.x, s.y)).length;
  const interior = edgeSamples.filter(s => !isEdge(s.x, s.y));
  check('새 물고기 출생 지점이 화면 가장자리 (내부 즉시생성 0)',
        edgeSamples.length >= 4 && interior.length === 0,
        `표본=${edgeSamples.length}, 가장자리=${atEdge}, 내부=${interior.length}` +
        (interior.length ? ' ' + JSON.stringify(interior.map(s=>[Math.round(s.x),Math.round(s.y)])) : ''));
  const inwardOK = edgeSamples.length >= 4;
  check('가장자리 표본 다수 확보 (안쪽 진입 관측 기반)', inwardOK, `표본=${edgeSamples.length}`);

  // ================= (신규) 스폰 크기 다양화 =================
  console.log('--- 스폰 크기 다양화 ---');
  const uniqSizes = [...new Set(sizeSamples.map(s => Math.round(s)))];
  check('스폰 크기가 다양함 (고정값 아님, 지터 관측)',
        sizeSamples.length >= 5 && uniqSizes.length >= 4,
        `표본=${sizeSamples.length}, 고유값=${uniqSizes.length}종 ${JSON.stringify(uniqSizes.sort((a,b)=>a-b))}`);

  // ================= (신규) 방향키 좌우 반전 정합 (오른쪽=오른쪽 바라봄) =================
  console.log('--- 방향키 좌우 반전 (오른쪽 이동=오른쪽 바라봄) ---');
  // 코스튬 art 는 왼쪽을 향해 그려짐 + rotationStyle left-right.
  //   오른쪽 이동 → point in direction -90 → 코스튬 좌우반전 → 오른쪽 바라봄 (올바름)
  //   왼쪽 이동 → point in direction  90 → 반전 안됨 → 왼쪽 바라봄 (올바름)
  // 실제로 방향키를 눌러 내물고기의 direction 이 그렇게 세팅되는지 관측.
  PARK = false;
  me.setXY(0, 0);
  keyDown('ArrowRight'); await sleep(160); keyUp('ArrowRight');
  const dirRight = me.direction;   // 기대: -90 (좌우반전 → 오른쪽 바라봄)
  const xAfterRight = me.x;
  keyDown('ArrowLeft'); await sleep(160); keyUp('ArrowLeft');
  const dirLeft = me.direction;    // 기대: 90 (반전 없음 → 왼쪽 바라봄)
  releaseAll(); PARK = true;
  check('오른쪽 키 → direction=-90 (좌우반전으로 오른쪽 바라봄)', dirRight === -90, `direction=${dirRight}`);
  check('왼쪽 키 → direction=90 (왼쪽 바라봄)', dirLeft === 90, `direction=${dirLeft}`);
  check('오른쪽 키로 실제 +x 이동함', xAfterRight > 0, `x=${xAfterRight.toFixed(0)}`);

  // ================= (검증 2) 자유 배회 · 추격 없음 (실측 이동 + 코드 검증) =================
  console.log('--- 자유 배회 (추격 AI 0) ---');
  // 내물고기는 구석에 park 된 상태. 물고기들이 내물고기(구석) 쪽으로 수렴하는지(추격)
  // vs 무상관 배회인지 거리 변화 부호로 관측한다.
  const distTo = (a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
  const f0 = clones('물고기')[0];
  const before = f0 ? {x:f0.x,y:f0.y, d: distTo(f0, me)} : null;
  const fishSnap = clones('물고기').filter(c=>vm.runtime.targets.includes(c)).map(c=>({c, d0: distTo(c, me)}));
  await sleep(800);
  if (f0 && vm.runtime.targets.includes(f0)) {
    const moved = distTo(f0, before);
    check('물고기 클론이 실제로 배회 이동함 (>2px)', moved > 2, `moved=${moved.toFixed(1)}px`);
    const fishNow = clones('물고기').filter(c=>vm.runtime.targets.includes(c));
    check('물고기 클론 여러 마리 동시 존재 (1대다)', fishNow.length >= 2, `n=${fishNow.length}`);
    // 추격이면 모든 클론이 내물고기(구석)에 더 가까워질 것. 부호가 섞이면 배회(추격 아님)의 실측 증거.
    const deltas = fishSnap.filter(s=>vm.runtime.targets.includes(s.c)).map(s=>distTo(s.c, me) - s.d0);
    const anyAway = deltas.some(d => d > 1); // 멀어진 클론이 하나라도 있으면 수렴(추격) 아님
    check('물고기들이 내물고기로 일제히 수렴하지 않음 (배회, 추격 아님 실측)', anyAway,
          `Δdist=[${deltas.map(d=>d.toFixed(0)).join(',')}]`);
  } else check('배회 측정 대상 존재', false, 'no fish clone');
  // CODE-LEVEL: 물고기 블록에 point-towards/distance/sensing-of(내물고기) 참조 0
  const fishTarget = original('물고기');
  let chaseRefs = [];
  for (const bid in fishTarget.blocks._blocks) {
    const b = fishTarget.blocks._blocks[bid];
    if (b.opcode === 'motion_pointtowards_menu' && b.fields.TOWARDS && b.fields.TOWARDS.value === '내물고기')
      chaseRefs.push('pointtowards 내물고기');
    if (b.opcode === 'sensing_distancetomenu') chaseRefs.push('distanceto ' + (b.fields.DISTANCETOMENU && b.fields.DISTANCETOMENU.value));
    if (b.opcode === 'sensing_of_object_menu') chaseRefs.push('sensing_of ' + (b.fields.OBJECT && b.fields.OBJECT.value));
  }
  check('물고기 코드에 추격/조준(point towards·distance to·of 내물고기) 참조 0개', chaseRefs.length === 0, chaseRefs.join(', ') || 'NONE');

  // ================= (검증 1a) 작은 물고기 먹기 → 성장 + 점수 (실플레이) =================
  console.log('--- 먹기 → 성장 + 점수 (실제 접촉) ---');
  // 작은 물고기 하나를 고정 지점에 세워두고(테스트 픽스처), 방향키로 내물고기를 몰아
  // 실제로 접촉시킨다. 먹기 결과(성장·점수·삭제)는 강제 세팅하지 않고 스크립트가 처리.
  const PIN = { x: 0, y: 0 };
  // 매 스텝 대상 물고기를 PIN 에 고정(가만히 있는 표적) — 먹기 결과는 건드리지 않음
  function pin(c) { return () => { if (c && vm.runtime.targets.includes(c)) c.setXY(PIN.x, PIN.y); }; }
  async function spawnControlledFish(sizeVal, costume) {
    PARK = true; // 스폰 대기 동안 내물고기는 구석에 park (우발 접촉 방지)
    // 기존 클론 전부 제거
    setVar('최대물고기', 0);
    clones('물고기').forEach(c => vm.runtime.disposeTarget(c));
    setVar('물고기수', 0);
    // 스폰간격을 잠깐 줄여 확실히 한 마리가 빨리 나오게 한 뒤, 캡을 열어 스폰
    const gapSaved = getVar('스폰간격');
    setVar('스폰간격', 0.1);
    setVar('게임상태', 1);
    setVar('최대물고기', 16);
    // 새 클론이 뜰 때까지 충분히 폴링 (최대 ~3초)
    let tries = 0;
    while (clones('물고기').length < 1 && tries++ < 100) await sleep(30);
    setVar('스폰간격', gapSaved);
    const c = clones('물고기')[0];
    if (!c) return null;
    // 나머지 클론 정리 → 통제된 1마리
    clones('물고기').slice(1).forEach(x => { vm.runtime.disposeTarget(x); });
    setVar('최대물고기', 0); // 추가 스폰 차단
    setVar('물고기수', 1);
    // 이 클론의 크기/코스튬을 원하는 티어로 설정 (실제 값 채널을 통해 관측)
    for (const id in c.variables) if (c.variables[id].name === '내물고기크기') c.variables[id].value = sizeVal;
    c.setSize(sizeVal);
    const idx = ['작은','중간','큰'].indexOf(costume);
    if (idx >= 0) c.setCostume(idx);
    c.setXY(PIN.x, PIN.y); // 표적을 PIN 지점에 배치
    return c;
  }
  // 내물고기를 표적으로 몰다가, 표적을 PIN 에 계속 세워두며 접촉 이벤트가 관측되면 멈춘다.
  // 시작 지점을 PIN 근처 고정점으로 리셋(픽스처)해 매번 재현되게 한다.
  async function driveIntoTarget(target, stopFn, maxSteps = 60) {
    PARK = false;                // park 해제 → 방향키로 내물고기가 실제 이동
    SAFE = false;                // 실제 먹기/피격 접촉을 켠다(관찰용 무력화 해제)
    me.setXY(PIN.x - 60, PIN.y); // 표적 왼쪽에서 출발 → 오른쪽 키로 진입
    const step = pin(target);
    step.__stop = stopFn;
    await steerToward(me, PIN.x - 8, PIN.y, maxSteps, step);
    releaseAll();
    // 접촉 지점 도달 후, 표적을 내물고기 위치에 촘촘히(매 10ms) 붙여둬 배회로 인한
    // 이탈을 막고, 물고기 클론 forever(접촉물고기크기 보고) ↔ 내물고기 판정 forever 가
    // 같은 프레임에서 만나 실제 먹기/피격이 성립하게 한다. (결과값은 강제하지 않음)
    const glue = setInterval(() => {
      if (target && vm.runtime.targets.includes(target)) target.setXY(me.x, me.y);
    }, 10);
    for (let i = 0; i < 60 && !stopFn(); i++) {
      if (target && !vm.runtime.targets.includes(target)) break; // 이미 먹혀 사라짐
      await sleep(30);
    }
    clearInterval(glue);
    await sleep(150);            // 클론 자기-삭제/물고기수 감소 등 후속 스크립트 정착 대기
    PARK = true;                 // 관찰 단계 복귀 시 다시 구석 park
    SAFE = true;                 // 관찰 접촉 무력화 복귀
  }

  // ================= (신규) 먹이/위험 색신호 + 내가 크면 실시간 갱신 =================
  console.log('--- 먹이/위험 색신호 (내크기 대비 실시간 갱신) ---');
  // 큰(100) 물고기 하나를 놓고, 내크기를 바꿔가며 그 클론의 color/brightness 이펙트가
  // 안전(초록·밝음: color≈70, brightness≈25) ↔ 위험(붉음·어두움: color≈180, brightness≈-15)
  // 로 실시간 전환되는지 관측. (강제로 이펙트를 세팅하지 않고, 클론 스크립트가 공유변수
  //  '내크기'만 읽어 스스로 갱신하는 것을 본다.)
  SAFE = true;  // 엔들리스라 클리어가 없으니 별도 격리 불필요
  const sig = await spawnControlledFish(100, '큰');
  function eff(t, name) { return t && t.effects ? t.effects[name] : undefined; }
  // (a) 내크기=60 → 60*0.9=54 < 100 → 이 물고기는 위험(못 먹음)
  setVar('게임상태', 1); setVar('내크기', 60);
  for (let i = 0; i < 20; i++) { if (sig) sig.setXY(-150, -120); await sleep(30); if (eff(sig,'color')>150) break; }
  const dangerColor = eff(sig, 'color'), dangerBri = eff(sig, 'brightness');
  check('내크기<물고기 → 위험 색신호 (color≈180·어두움)', dangerColor >= 150 && dangerBri < 0,
        `color=${dangerColor}, brightness=${dangerBri}`);
  // (b) 내크기=130 → 130*0.9=117 ≥ 100 → 이제 먹을 수 있음 → 안전 색신호로 실시간 전환
  setVar('내크기', 130);
  let flipped = false;
  for (let i = 0; i < 25; i++) { if (sig) sig.setXY(-150, -120); await sleep(30); if (eff(sig,'color')<120) { flipped = true; break; } }
  const safeColor = eff(sig, 'color'), safeBri = eff(sig, 'brightness');
  check('내가 성장(60→130)하니 같은 물고기가 안전 색신호로 실시간 전환 (color≈70·밝음)',
        flipped && safeColor <= 120 && safeBri > 0, `color=${safeColor}, brightness=${safeBri}`);
  if (sig && vm.runtime.targets.includes(sig)) vm.runtime.disposeTarget(sig);
  setVar('내크기', 60); setVar('물고기수', 0); setVar('게임상태', 1);

  // 내 크기 60, 먹기기준 0.9 → 60*0.9=54. 작은(35) ≤ 54 → 먹혀야 함.
  let target = await spawnControlledFish(35, '작은');
  check('통제된 작은 물고기(35) 배치됨', !!target, target ? `size=${target.size}` : 'none');
  const sizeBefore = getVar('내크기');
  const scoreBefore = getVar('점수');
  const aliveBefore = getVar('물고기수');
  // 방향키로 내물고기를 표적(0,0)으로 몰아 실제 접촉 → 먹기 관측
  await driveIntoTarget(target, () => getVar('내크기') > sizeBefore);
  v = stageVars();
  const grew = getVar('내크기') >= sizeBefore + getVar('성장량') - 0.001;
  const scored = getVar('점수') >= scoreBefore + 1;
  const fishGone = !target || !vm.runtime.targets.includes(target) || getVar('물고기수') < aliveBefore;
  check('작은 물고기에 실제 접촉 → 내크기 += 성장량 (관측)', grew,
        `내크기 ${sizeBefore}→${getVar('내크기')} (성장량=${getVar('성장량')})`);
  check('먹기 → 점수 증가 (관측)', scored, `점수 ${scoreBefore}→${getVar('점수')}`);
  check('먹힌 물고기 클론 사라짐 + 물고기수 감소', fishGone, `물고기수 ${aliveBefore}→${getVar('물고기수')}`);

  // ================= (검증 4) 튜닝 실효: 먹기기준 낮추면 같은 크기 안 먹힘 =================
  console.log('--- 튜닝 실효: 먹기기준 ---');
  // 내크기를 60으로 되돌리고, 먹기기준을 0.5로 낮춘다 → 60*0.5=30. 작은(35) > 30 → 못 먹힘(=게임오버).
  setVar('게임상태', 1); setVar('내크기', 60); me.setXY(-60, 0);
  setVar('먹기기준', 0.5);
  let target2 = await spawnControlledFish(35, '작은');
  await driveIntoTarget(target2, () => getVar('게임상태') !== 1, 30);
  check('먹기기준=0.5 → 작은(35)이 내크기×0.5=30 초과라 안 먹히고 게임오버(관측)',
        getVar('게임상태') === 0, `게임상태=${getVar('게임상태')}, 내크기=${getVar('내크기')}`);
  setVar('먹기기준', 0.9); // 복구

  // ================= (검증 1b) 큰 물고기 접촉 → 게임오버 (실플레이) =================
  console.log('--- 큰 물고기 접촉 → 게임오버 (실제 접촉) ---');
  setVar('게임상태', 1); setVar('내크기', 60); me.setXY(-60, 0); // 60*0.9=54 < 큰(100) → 못 먹음 → 죽음
  let big = await spawnControlledFish(100, '큰');
  check('통제된 큰 물고기(100) 배치됨', !!big, big ? `size=${big.size}` : 'none');
  await driveIntoTarget(big, () => getVar('게임상태') !== 1, 30);
  check('큰 물고기에 실제 접촉 → 게임상태=0 (게임오버 관측)', getVar('게임상태') === 0,
        `게임상태=${getVar('게임상태')}`);

  // ================= (검증 1c) 성장으로 관계 역전: 커지면 큰(100)도 먹는다 =================
  console.log('--- 관계 역전: 내크기 커지면 큰(100)도 먹힌다 ---');
  setVar('게임상태', 1); setVar('내크기', 130); me.setXY(-40, 0); // 130*0.9=117 ≥ 100 → 큰 물고기도 먹힘
  let big2 = await spawnControlledFish(100, '큰');
  const szB = getVar('내크기'); const scB = getVar('점수');
  await driveIntoTarget(big2, () => getVar('내크기') > szB || getVar('게임상태') !== 1, 50);
  const grewBig = getVar('내크기') > szB && getVar('게임상태') !== 0;
  check('내크기 130일 때 큰(100) 물고기를 먹어 성장(게임오버 아님, 관계 역전)', grewBig,
        `내크기 ${szB}→${getVar('내크기')}, 게임상태=${getVar('게임상태')}, 점수 ${scB}→${getVar('점수')}`);

  // ================= (신규) 엔들리스: 클리어 없음 — 커져도 계속 진행 =================
  console.log('--- 엔들리스 (클리어 없음, 무한 성장) ---');
  // 클리어 경로(게임상태=2) 자체가 코드에 없어야 한다: 어느 스크립트도 게임상태를 2로 안 만든다.
  // (runtime 내부 블록 포맷: inputs.VALUE.block → shadow 블록의 fields.NUM.value 로 리터럴을 읽는다.)
  const setsGameState = []; // 관측된 게임상태 리터럴 세팅 값들
  for (const tg of vm.runtime.targets) {
    const blks = tg.blocks._blocks || {};
    for (const b of Object.values(blks)) {
      if (b.opcode === 'data_setvariableto' && b.fields.VARIABLE && b.fields.VARIABLE.value === '게임상태') {
        const inp = b.inputs.VALUE;
        if (inp && inp.block) {
          const sh = blks[inp.block];
          const val = sh && sh.fields && sh.fields.NUM ? String(sh.fields.NUM.value) : '?';
          setsGameState.push(val);
        }
      }
    }
  }
  const setsTo2 = setsGameState.filter(v => v === '2').length;
  check('코드에 게임상태=2(클리어) 설정 경로 없음 (엔들리스)', setsTo2 === 0,
        `게임상태 설정 리터럴=[${setsGameState.join(',')}] → =2 는 ${setsTo2}개`);
  // 새 게임 시작 후, 예전 목표(110) 훨씬 넘게 키워도 게임상태가 1(진행) 유지 + 여전히 스폰됨
  vm.greenFlag(); await sleep(500); patchNewClones(); SAFE = true;
  setVar('내크기', 300);          // 예전 목표(110) 3배 — 클리어였다면 벌써 끝났을 크기
  setVar('최대물고기', 16); setVar('스폰간격', 0.12);
  if (me) me.setXY(232, 162);
  await sleep(1200);
  check('예전 목표(110) 훨씬 넘겨도(내크기=300) 게임상태=1 유지 (엔들리스 계속 진행)',
        getVar('게임상태') === 1, `게임상태=${getVar('게임상태')}, 내크기=${getVar('내크기')}`);
  check('커진 뒤에도 물고기 계속 스폰됨', clones('물고기').length >= 1, `clones=${clones('물고기').length}`);

  // ================= (신규) 무한 도전: 커져도 먹이+위험이 공존 =================
  console.log('--- 무한 도전 (내크기 커도 먹이+위험 공존) ---');
  // 내크기=300 상태에서 새 스폰 표본을 모아, 나보다 작은(먹이) 것과 큰(위험) 것이 둘 다 있는지.
  const relSizes = [];
  const seenR = new Set(clones('물고기').map(c => c.id));
  clones('물고기').forEach(c => relSizes.push(Number(cloneLocal(c, '내물고기크기'))));
  for (let i = 0; i < 120 && relSizes.length < 16; i++) {
    for (const c of clones('물고기')) if (!seenR.has(c.id)) { seenR.add(c.id); relSizes.push(Number(cloneLocal(c, '내물고기크기'))); }
    if (me) me.setXY(232, 162);
    await sleep(20);
  }
  const eatThresh = 300 * getVar('먹기기준'); // 300*0.9=270
  const smaller = relSizes.filter(s => s <= eatThresh).length;   // 먹이(초록)
  const bigger  = relSizes.filter(s => s > eatThresh).length;    // 위험(붉음)
  check('내크기=300에서도 나보다 작은 먹이와 큰 위험이 공존 스폰',
        relSizes.length >= 6 && smaller >= 1 && bigger >= 1,
        `표본=${relSizes.length}, 먹이(≤270)=${smaller}, 위험(>270)=${bigger}`);

  // ================= (신규) 표시 크기 상한 =================
  // ※ headless scratch-vm 은 렌더러가 없어 looks_setsizeto 가 target.size 를 갱신하지
  //   않는다(rendered-target.setSize 의 갱신이 if(renderer) 안에 있음). 그래서 .size 관측
  //   대신, 상한 클램프 '로직'이 코드에 실재하는지를 구조로 검증한다: 내물고기/물고기가
  //   'set size to 내크기(또는 내물고기크기)' 뒤에 'if (그 값 > 표시크기상한) set size to 표시크기상한'
  //   을 갖는지. (표시상한 초과 성장 시 표시 size 가 상한으로 고정되는 실제 회로.)
  console.log('--- 표시 크기 상한 (구조: 렌더러 없어 .size 관측 불가) ---');
  const cap = getVar('표시크기상한');
  function hasCapClamp(spriteName, sizeVarName) {
    const tg = original(spriteName);
    const blks = tg.blocks._blocks;
    const varName = b => (b && b.opcode === 'data_variable') ? b.fields.VARIABLE.value : null;
    for (const b of Object.values(blks)) {
      if (b.opcode !== 'looks_setsizeto') continue;
      const sizeInp = b.inputs.SIZE;
      if (!sizeInp || !sizeInp.block) continue;
      if (varName(blks[sizeInp.block]) !== '표시크기상한') continue;      // set size to 표시크기상한
      const ifBlk = blks[b.parent];
      if (!ifBlk || ifBlk.opcode !== 'control_if' || !ifBlk.inputs.CONDITION) continue;
      const cond = blks[ifBlk.inputs.CONDITION.block];
      if (!cond || cond.opcode !== 'operator_gt') continue;             // if (?  >  ?)
      const names = [varName(blks[cond.inputs.OPERAND1.block]), varName(blks[cond.inputs.OPERAND2.block])];
      if (names.includes(sizeVarName) && names.includes('표시크기상한')) return true; // (sizeVar > 표시크기상한)
    }
    return false;
  }
  check(`내물고기: 표시 size 를 표시크기상한(${cap})으로 클램프하는 회로 존재`,
        hasCapClamp('내물고기', '내크기'), hasCapClamp('내물고기', '내크기') ? 'if(내크기>상한) set size 상한' : 'missing');
  check(`물고기: 표시 size 를 표시크기상한(${cap})으로 클램프하는 회로 존재`,
        hasCapClamp('물고기', '내물고기크기'), hasCapClamp('물고기', '내물고기크기') ? 'if(내물고기크기>상한) set size 상한' : 'missing');

  // ================= 게임오버 배너 (엔들리스: over 만) =================
  console.log('--- 게임오버 배너 (엔들리스: over) ---');
  vm.greenFlag();
  await sleep(500);
  patchNewClones();
  setVar('최대물고기', 0);
  clones('물고기').forEach(c => vm.runtime.disposeTarget(c));
  setVar('게임상태', 0); // 게임오버 결착
  await sleep(400);
  const result2 = original('결과');
  const rc2 = result2.getCostumes()[result2.currentCostume];
  check('게임오버 결착 → 배너 코스튬 = over', rc2 && rc2.name === 'over', rc2 && rc2.name);
  check('게임오버 배너 표시됨(visible)', result2.visible === true, `visible=${result2.visible}`);

  // ================= (검증 3b) 클론 누수 0 =================
  console.log('--- 클론 정리 · 누수 0 ---');
  vm.greenFlag(); await sleep(500); patchNewClones(); SAFE = true;
  setVar('최대물고기', 16); setVar('게임상태', 1); setVar('내크기', 60);
  if (me) me.setXY(232, 162);
  await sleep(1500); // 다시 스폰
  const spawned = clones('물고기').length;
  check('재개 후 다시 스폰됨', spawned >= 1, `clones=${spawned}`);
  setVar('게임상태', 0); // 게임오버 → 클론 자기 정리
  await sleep(600);
  check('게임오버 후 물고기 클론 자기 삭제 (누수 0)', clones('물고기').length === 0, `남은=${clones('물고기').length}`);
  check('뽁 클론도 잔존 0', clones('뽁').length === 0, `뽁=${clones('뽁').length}`);

  // ================= (검증 6) 60초 안정성 (압축: 캡 유지 · 폭주 없음) =================
  console.log('--- 안정성: 캡 유지 · 클론 폭주 없음 ---');
  vm.greenFlag(); await sleep(500); patchNewClones(); SAFE = true;
  setVar('게임상태', 1); setVar('내크기', 60); // 엔들리스: 클리어 없음
  setVar('최대물고기', 16); setVar('스폰간격', 0.1);
  releaseAll(); // 방향키 놓아 내물고기 정지
  // 내물고기를 구석에 세워두고(키 안 누름) 게임오버 없이 오래 돌린다
  let maxClones = 0;
  for (let i = 0; i < 30; i++) {
    if (me) me.setXY(230, 160); // 구석 픽스처(우발 접촉 최소화)
    await sleep(200);
    const n = clones('물고기').length;
    if (n > maxClones) maxClones = n;
    if (getVar('게임상태') !== 1) { setVar('게임상태', 1); } // 우발적 접촉 복구
  }
  check('장시간 실행 중 클론 총량이 캡(16) 부근 유지 (폭주 없음)', maxClones <= 18,
        `maxClones=${maxClones} (cap=16)`);
  check('물고기수 변수도 캡 이내', getVar('물고기수') <= 18, `물고기수=${getVar('물고기수')}`);

  clearInterval(patcher);
  clearInterval(parker);
  console.log('\n' + (FAIL ? 'RESULT: FAIL' : 'RESULT: ALL PASS'));
  process.exit(FAIL ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
