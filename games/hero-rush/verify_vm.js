// Headless scratch-vm 행동 시나리오 검증 — hero-rush (용사 진격전).
// 렌더러 없음 → `touching [sprite]` 는 항상 false 라, RenderedTarget.isTouchingSprite 를
// 거리(반지름 합) 기반으로 몽키패치(reference-headless-scratchvm-verification 기법).
// 검판정/스킬판정·적·용사·성문의 touching 데미지 로직이 실제로 '실행'되게 만든 뒤 행동 관찰:
//  A) 자동 플레이로 1스테이지 진격→공성→성문 파괴(게임상태 1→2) 시간 실측
//  B) 적 접촉 순간부터 0.5초(무적시간 20틱) 이내 체력 감소 + 무적 발동
//  C) 잡졸(체력4) vs 공격력3 → 검격 2타 이내 처치(내체력 4→1→처치, 피격쿨 중복방지)
//  D) 스킬 게이지 게이트: 만충(스킬타이머0)에서만 발동 → 스킬쿨 리셋 → 0으로 재충전
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

// --- 거리 기반 touching 오버라이드(근사 Scratch 충돌) ---
function radiusOf(t) {
  const sz = (typeof t.size === 'number' ? t.size : 100) / 100;
  return Math.max(10, 26 * sz);  // 코스튬 ~52px 기준 반지름 ~26px @100%
}
function installGeometricTouching(vm) {
  const proto = Object.getPrototypeOf(vm.runtime.targets[0]);
  proto.isTouchingSprite = function (spriteName) {
    const first = this.runtime.getSpriteTargetByName(String(spriteName));
    if (!first) return false;
    const r1 = radiusOf(this);
    const targets = [first, ...first.sprite.clones];
    for (const other of targets) {
      if (other === this || !other.visible) continue;
      const dx = this.x - other.x, dy = this.y - other.y;
      if (Math.hypot(dx, dy) <= r1 + radiusOf(other)) return true;
    }
    return false;
  };
}

const sb3 = path.join(__dirname, '용사_진격전.sb3');
const vm = new VM();
function stage() { return vm.runtime.targets.find(t => t.isStage); }
function stageVars() { const st = stage(); const o = {}; for (const id in st.variables) { const v = st.variables[id]; if (v.type !== 'list' && v.type !== 'broadcast_msg') o[v.name] = v.value; } return o; }
function gv(name) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) return Number(st.variables[id].value); }
function setVar(name, val) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val; }
function orig(name) { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal); }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return Number(c.variables[id].value); return undefined; }
function setCloneLocal(c, name, val) { for (const id in c.variables) if (c.variables[id].name === name) c.variables[id].value = val; }
function visible(name) { const o = orig(name); return o ? o.visible : undefined; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`); if (!ok) FAIL = true; }
const key = (k, down) => vm.runtime.ioDevices.keyboard.postData({ key: k, isDown: !!down });

(async () => {
  await vm.loadProject(buf());
  installGeometricTouching(vm);
  vm.start();
  vm.greenFlag();
  await sleep(700);

  // ---------- (0) 초기화 ----------
  console.log('--- (0) 초기화 ---');
  let v = stageVars();
  check('게임상태1·스테이지1·진격도0·공성중0·적배율1', v.게임상태==1 && v.스테이지==1 && v.진격도==0 && v.공성중==0 && v.적배율==1,
        `state=${v.게임상태} stage=${v.스테이지} prog=${v.진격도} siege=${v.공성중} scale=${v.적배율}`);
  check('체력=최대체력=6, 성문체력=성문기본체력=40', v.체력==6 && v.최대체력==6 && v.성문체력==40, `hp=${v.체력}/${v.최대체력} gate=${v.성문체력}`);
  check('튜닝: 공격력3·이동속도6·진격속도1.8·검격쿨8·스킬쿨200·잡졸_체력4·적성장배율1.22',
        v.공격력==3 && v.이동속도==6 && v.진격속도==1.8 && v.검격쿨==8 && v.스킬쿨==200 && v.잡졸_체력==4 && v.적성장배율==1.22);
  check('용사 visible, 초기 x≈-120', orig('용사').visible && Math.abs(orig('용사').x + 120) < 5, `x=${orig('용사').x.toFixed(1)}`);

  // ---------- (B) 적 접촉 → 0.5초 내 피해 + 무적 ----------
  console.log('--- (B) 적 접촉 0.5초 내 피해 + 무적 ---');
  // 자연 스폰된 적 클론 하나를 용사 위로 순간이동 → 접촉 데미지 로직 실행 관찰.
  let e = null;
  for (let i = 0; i < 60 && !e; i++) { await sleep(80); e = clones('적').find(c => c.visible); }
  check('적 클론 스폰됨', !!e, e ? `적수=${gv('적수')}` : '없음');
  let latency = null, invSet = false;
  if (e) {
    setVar('무적', 0);
    const hero = orig('용사');
    const hp0 = gv('체력');
    const t0 = Date.now();
    // 접촉 유지: 적을 용사 위에 여러 프레임 고정.
    for (let i = 0; i < 20; i++) {
      e.setXY(hero.x, hero.y);
      await sleep(30);
      if (gv('체력') < hp0 && latency === null) latency = Date.now() - t0;
      if (gv('무적') > 0) invSet = true;
      if (latency !== null && invSet) break;
    }
    check('접촉 후 체력 감소', latency !== null, latency !== null ? `${gv('체력')} (from ${hp0})` : '감소 없음');
    check('피해 지연 0.5초 이내', latency !== null && latency <= 600, `${latency}ms`);
    check('피격 시 무적 발동(>0)', invSet, `무적=${gv('무적')}`);
  }

  // ---------- (C) 잡졸 검격 2타 이내 처치 ----------
  console.log('--- (C) 잡졸 2타 처치 (내체력 4→1→처치) ---');
  check('공식: 잡졸_체력×적배율=4 vs 공격력3 → ceil=2타', Math.ceil((gv('잡졸_체력')*gv('적배율'))/gv('공격력'))===2,
        `hp=${gv('잡졸_체력')*gv('적배율')} atk=${gv('공격력')}`);
  // 잡졸 클론 하나를 골라 검판정 위치에 고정, 검격 펄스마다 내체력을 읽는다.
  let tgt = null;
  for (let i = 0; i < 60 && !tgt; i++) { await sleep(80); tgt = clones('적').find(c => c.visible && cloneLocal(c,'적종류')===1); }
  if (!tgt) { check('잡졸(적종류1) 클론 확보', false); }
  else {
    // 통제: 이 클론 내체력=4, 내속도=0(고정), 피격쿨=0.
    setCloneLocal(tgt, '내체력', 4); setCloneLocal(tgt, '내속도', 0); setCloneLocal(tgt, '피격쿨', 0);
    const hero = orig('용사'); hero.setDirection(90);         // 오른쪽 향함 → 검판정 = 용사x+검격범위
    const slashX = () => hero.x + gv('검격범위');
    const hpReadings = [cloneLocal(tgt, '내체력')];
    // 실제 '명중(내체력 감소)' 횟수를 센다 — 헤드리스 setTimeout 지터로 히트박스 창을
    // 놓친 헛스윙은 세지 않는다(게임 로직 = 4HP/공격력3 = 2명중, verifier 권고 반영).
    let hits = 0, killed = false, prevHp = cloneLocal(tgt, '내체력');
    const perHit = [];
    for (let s = 0; s < 6 && !killed; s++) {
      // 한 번의 명중을 확실히 성사시킨다: 검격 창을 열고 표적을 검판정 지점에 고정,
      // 피격쿨>0(명중)이 될 때까지 재시도. 명중하면 즉시 이탈시켜 같은 스윙 중복피격 금지.
      let landed = false;
      for (let attempt = 0; attempt < 6 && !landed; attempt++) {
        key(' ', true); await sleep(50); key(' ', false);
        for (let k = 0; k < 14; k++) {
          if (!vm.runtime.targets.includes(tgt)) { killed = true; landed = true; break; }
          if (cloneLocal(tgt, '피격쿨') > 0) { landed = true; break; }   // 명중 등록
          tgt.setXY(slashX(), gv('레인Y'));
          await sleep(15);
        }
        if (!landed) await sleep(120);   // 창 놓침 → 재스윙
      }
      if (vm.runtime.targets.includes(tgt)) tgt.setXY(slashX() + 400, gv('레인Y'));
      await sleep(320);   // 피격쿨(6틱≈0.15s) 소진 대기
      if (!landed) break;
      hits++;
      const alive = vm.runtime.targets.includes(tgt) && tgt.visible;
      const hpNow = alive ? cloneLocal(tgt, '내체력') : 0;   // 처치 시 클론 소멸 → <1 로 간주
      perHit.push(prevHp - hpNow); prevHp = hpNow;
      hpReadings.push(alive ? hpNow : 'DEAD');
      if (!alive || hpNow < 1) killed = true;
    }
    console.log(`     내체력 추이: ${hpReadings.join(' → ')}  (실제 명중 ${hits}회, 명중별 피해 ${perHit.join('/')})`);
    check('검격 1타에 정확히 공격력(3)만큼 감소(4→1)', hpReadings[1] === 1, `1타 후=${hpReadings[1]}`);
    check('실제 명중 2회 이내 처치(4HP/공격력3=2)', killed && hits <= 2, `명중=${hits} killed=${killed}`);
  }

  // ---------- (D) 스킬 게이지 게이트 ----------
  console.log('--- (D) 스킬 게이지 게이트/쿨/재충전 ---');
  setVar('스킬타이머', 0); await sleep(120);
  check('발동 전 스킬타이머=0(만충 READY)', gv('스킬타이머')==0, `t=${gv('스킬타이머')}`);
  let skVis = false;
  key('x', true); await sleep(80); key('x', false);
  for (let i = 0; i < 12; i++) { await sleep(30); if (visible('스킬판정')) skVis = true; }
  const skAfter = gv('스킬타이머');
  check('X 발동 → 스킬타이머 스킬쿨(≈200)로 리셋', skAfter > 150, `t=${skAfter}`);
  check('스킬판정(회전베기 링) 활성 창에 show', skVis);
  const m1 = gv('스킬타이머'); await sleep(600); const m2 = gv('스킬타이머');
  check('스킬 재충전(스킬타이머 감소 = 게이지 0→100%)', m2 < m1, `${m1}→${m2}`);
  const bfr = gv('스킬타이머'); key('x', true); await sleep(80); key('x', false); await sleep(120); const aft = gv('스킬타이머');
  check('쿨 중 X 무시(다시 200으로 안 튐)', aft <= bfr + 2, `${bfr}→${aft}`);

  // ---------- (A) 자동 플레이 1스테이지 클리어 시간 ----------
  console.log('--- (A) 자동 플레이 1스테이지 클리어 시간(템포 실측) ---');
  // A 는 '클리어까지 걸리는 템포(진격속도·스테이지길이·검격쿨·성문체력)' 실측.
  // 생존(접촉 피해)은 B 가 이미 증명 → 여기선 auto-heal 로 자동플레이어를 살려 순수 지속시간만 잰다.
  setVar('진격도', 0); setVar('공성중', 0); setVar('체력', gv('최대체력')); setVar('게임상태', 1);
  await sleep(60);
  const tStart = Date.now();
  let tSiege = null, tClear = null;
  const heal = () => setVar('체력', gv('최대체력'));   // 자동플레이어 생존 유지
  key('ArrowRight', true);
  // 1단계: 진격(우측 홀드 + 검격 펄스) → 공성중=1
  while (Date.now() - tStart < 60000 && tSiege === null) {
    heal();
    key(' ', true); await sleep(50); key(' ', false); await sleep(50);
    if (gv('공성중') == 1) tSiege = (Date.now() - tStart) / 1000;
  }
  key('ArrowRight', false);
  check('공성 진입(공성중=1) 도달', tSiege !== null, tSiege !== null ? `${tSiege.toFixed(1)}s(wall)` : '미도달');
  // 2단계: 성문 공격(용사를 성문 사거리에 배치·좌향, 검격 펄스) → 성문체력 0 → 게임상태=2
  if (tSiege !== null) {
    await sleep(500);   // 성문 슬라이드 인 대기
    const hero = orig('용사'); const gate = orig('성문');
    while (Date.now() - tStart < 60000 && tClear === null) {
      heal();
      hero.setDirection(-90); hero.setXY(gate.x + gv('검격범위'), gv('레인Y'));
      key(' ', true); await sleep(50); key(' ', false); await sleep(50);
      if (gv('게임상태') == 2 || gv('스테이지') > 1) tClear = (Date.now() - tStart) / 1000;
    }
  }
  key(' ', false);
  const S = stageVars();
  check('성문 파괴로 스테이지 클리어(게임상태=2)', tClear !== null,
        tClear !== null ? `클리어=${tClear.toFixed(1)}s(wall)` : `상태=${S.게임상태} 성문체력=${S.성문체력}`);
  check('클리어 시간 60초 이내', tClear !== null && tClear <= 60, tClear !== null ? `${tClear.toFixed(1)}s` : 'n/a');
  if (tClear !== null) {
    // headless 는 wait 블록이 실시간이지만 스텝이 ~0.5x 로 느려 wall-clock ≈ 2× game-time.
    const gameEst = tClear / 2;
    console.log(`  ▶ 시나리오 A 실측: 공성 ${tSiege.toFixed(1)}s(wall) → 클리어 ${tClear.toFixed(1)}s(wall); 추정 game-time ≈ ${gameEst.toFixed(0)}s`);
    console.log('    (진격도 채우기는 순수 좌표 로직; 성문 파괴는 geometric touching 으로 실행 확인)');
    if (gameEst < 25) console.log('    (참고: game-time 25초 미만 = 다소 빠름 — 진격속도↓ 또는 스테이지길이↑ 로 30~60초에 맞출 여지)');
  }

  console.log(FAIL ? '\n=== RESULT: FAIL ===' : '\n=== RESULT: ALL PASS ===');
  process.exit(FAIL ? 1 : 0);
})();

function buf() { return fs.readFileSync(sb3); }
