// Headless COLLISION/touching check for downwell (다운웰).
//
// The default headless VM has no renderer → `touching [sprite]` always returns
// false, so touch-based mechanics (스톰프, 총알 명중, 발판 착지) can't be exercised.
// Here we monkeypatch RenderedTarget.isTouchingSprite with a geometric
// (distance-of-radii) check, so the SAME scheduling race (fast bullet self-
// deleting before the slower enemy loop registers the hit = tunneling) is
// faithfully reproduced. This is the test that proves hits actually land.
//
// 민감도 확인 포함: 패치 전엔 touching=false 라 처치/충전이 일어나지 않음(아래 sanity).
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

function radiusOf(t) {
  const sz = (typeof t.size === 'number' ? t.size : 100) / 100;
  return Math.max(4, 18 * sz); // 코스튬 ~36px 기준 → 100%에서 반경 ~18px
}
function installGeometricTouching(vm) {
  const proto = Object.getPrototypeOf(vm.runtime.targets[0]);
  proto.isTouchingSprite = function (spriteName) {
    const first = this.runtime.getSpriteTargetByName(String(spriteName));
    if (!first) return false;
    const r1 = radiusOf(this);
    const pool = [first, ...first.sprite.clones];
    for (const c of pool) {
      if (c === this || c.dragging || !c.visible) continue;
      const dx = this.x - c.x, dy = this.y - c.y;
      if (Math.hypot(dx, dy) <= r1 + radiusOf(c)) return true;
    }
    return false;
  };
}

const sb3 = path.join(__dirname, '다운웰.sb3');
const vm = new VM();
function stage() { return vm.runtime.targets.find(t => t.isStage); }
function sv() { const o = {}; const st = stage(); for (const id in st.variables) { const v = st.variables[id]; if (v.type !== 'list') o[v.name] = v.value; } return o; }
function setVar(name, val) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val; }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
function original(name) { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal); }
function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return c.variables[id].value; return undefined; }
function setCloneLocal(c, name, val) { for (const id in c.variables) if (c.variables[id].name === name) c.variables[id].value = val; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`); if (!ok) FAIL = true; }

(async () => {
  await vm.loadProject(fs.readFileSync(sb3));

  // ---- 민감도 확인: 패치 전엔 touching 이 항상 false ----
  console.log('--- 민감도 확인 (geometric touching 패치 유무) ---');
  const boy0 = original('소년');
  const before = boy0.isTouchingSprite('적');
  installGeometricTouching(vm);
  // 같은 좌표에 임시 비교용으로 적 원본을 보이게 두면 패치 후 true 여야 한다(스폰 후 확인)
  check('패치 전 isTouchingSprite("적") = false (렌더러 없음)', before === false, `before=${before}`);

  vm.start();
  vm.greenFlag();
  await sleep(500);

  const boy = original('소년');

  // 적이 충분히 깔리도록 스폰 빠르게, 낙하-스크롤은 잠시 멈춰 좌표를 우리가 통제
  setVar('유효스폰간격', 0.3);
  await sleep(1500);
  let en = clones('적');
  check('적 클론 다수 스폰됨 (>=2)', en.length >= 2, `enemies=${en.length}`);

  // ===== (1) 총알 명중 → 적 내체력 감소 (데미지 등록) =====
  console.log('--- (1) 총알 명중 → 적 내체력 감소 ---');
  // 적 한 마리를 골라 HP를 올리고, 모든 총알을 그 위로 순간이동시켜 명중 등록을 본다
  setVar('중력', 0); setVar('낙하속도', 0); // 좌표 고정
  let target = clones('적')[0];
  setCloneLocal(target, '내체력', 5);
  setCloneLocal(target, '피격쿨', 0);
  setVar('총알공격력', 1);
  // 총알을 계속 발사시키고(z) 매 프레임 타깃 위로 park → 거리기반 touching 등록
  setVar('탄약', 99); setVar('발사쿨', 0);
  vm.postIOData('keyboard', { key: 'z', isDown: true });
  const hp0 = Number(cloneLocal(target, '내체력'));
  let hpReadings = [hp0];
  for (let i = 0; i < 30; i++) {
    for (const b of clones('총알')) b.setXY(target.x, target.y);
    await sleep(50);
    if (!vm.runtime.targets.includes(target)) break;
    setCloneLocal(target, '피격쿨', Math.max(0, Number(cloneLocal(target, '피격쿨')))); // no-op, keep loop honest
    hpReadings.push(Number(cloneLocal(target, '내체력')));
  }
  vm.postIOData('keyboard', { key: 'z', isDown: false });
  const dead = !vm.runtime.targets.includes(target);
  const hpNow = dead ? -999 : Number(cloneLocal(target, '내체력'));
  check('총알이 겹친 적의 내체력이 실제로 감소함 (명중 등록)', dead || hpNow < hp0,
        dead ? '내체력 0 도달 → 처치됨' : `내체력 ${hp0} → ${hpNow}`);

  // ===== (2) 스톰프(점프벌레 밟기) → 처치 + 콤보 + 탄약 충전 =====
  console.log('--- (2) 스톰프(점프벌레 밟기) → 콤보 + 탄약 충전 + 처치 ---');
  setVar('탄약', 0); setVar('콤보', 0); setVar('낙하속도', 2); setVar('중력', 0); // 낙하 중(>0) 고정
  // 점프벌레(스톰프가능=1) 클론을 하나 골라 소년 바로 아래(카메라선보다 충분히 아래)에 배치
  let bug = clones('적').find(c => Number(cloneLocal(c, '스톰프가능')) === 1);
  if (!bug) { setVar('단계', 0); await sleep(600); bug = clones('적').find(c => Number(cloneLocal(c, '스톰프가능')) === 1); }
  check('스톰프 가능한 점프벌레 클론 확보', !!bug, bug ? `적종류=${cloneLocal(bug, '적종류')}` : 'none');
  if (bug) {
    // 소년 y=카메라선(40). 벌레를 y=24 에 두면 카메라선 > y+10(34) ✓, 거리 16px → touching ✓
    setCloneLocal(bug, '내체력', 1);
    const ammoMax = Number(sv().탄약최대);
    const comboBefore = Number(sv().콤보);
    // 소년 y=카메라선(40). 벌레를 y=24 에 두면 카메라선 > y+10(34) ✓, 거리 16px → touching ✓.
    // 스톰프가 낙하속도를 음수로 만들면(착지반동) 더는 2로 강제하지 않고 최저값을 캡처한다.
    let stomped = false, fallMin = 99;
    for (let i = 0; i < 24; i++) {
      if (vm.runtime.targets.includes(bug)) bug.setXY(boy.x, 24);
      if (Number(sv().낙하속도) >= 0 && vm.runtime.targets.includes(bug)) setVar('낙하속도', 2);
      await sleep(50);
      fallMin = Math.min(fallMin, Number(sv().낙하속도));
      if (!vm.runtime.targets.includes(bug)) { stomped = true; break; }
    }
    const v = sv();
    check('스톰프로 점프벌레가 처치됨(클론 삭제)', stomped, stomped ? '삭제됨' : '아직 살아있음');
    check('스톰프 시 탄약이 가득 충전됨 (탄약=탄약최대)', Number(v.탄약) === ammoMax, `탄약=${v.탄약}/${ammoMax}`);
    check('스톰프 처치로 콤보 증가', Number(v.콤보) > comboBefore, `콤보 ${comboBefore}→${v.콤보}`);
    check('스톰프 시 소년 튕김 (낙하속도가 -착지반동, 음수로 찍힘)', fallMin < 0, `낙하속도 최저=${fallMin.toFixed(2)}`);
  }

  // ===== (3) 발판 착지 → 탄약 충전 + 콤보 0 리셋 =====
  console.log('--- (3) 발판 착지 → 탄약 충전 + 콤보 리셋(0) ---');
  setVar('콤보', 7); setVar('탄약', 0); setVar('낙하속도', 2); setVar('중력', 0);
  setVar('발판간격', 0.3);
  let ledge = clones('발판')[0];
  for (let g = 0; g < 8 && !ledge; g++) { await sleep(300); ledge = clones('발판')[0]; }
  check('발판 클론 확보', !!ledge, ledge ? 'ok' : 'none');
  if (ledge) {
    const ammoMax = Number(sv().탄약최대);
    let landed = false;
    for (let i = 0; i < 16; i++) {
      ledge.setXY(boy.x, boy.y); // 발판을 소년 위치로 → touching
      setVar('낙하속도', 2);
      await sleep(50);
      if (Number(sv().콤보) === 0) { landed = true; break; }
    }
    const v = sv();
    check('발판 착지로 콤보가 0으로 리셋됨', Number(v.콤보) === 0, `콤보=${v.콤보}`);
    check('발판 착지로 탄약이 가득 충전됨', Number(v.탄약) === ammoMax, `탄약=${v.탄약}/${ammoMax}`);
    check('발판 착지로 낙하 멈춤 (낙하속도=0)', Number(v.낙하속도) === 0, `낙하속도=${v.낙하속도}`);
  }

  // ===== (4) 적 접촉 피격 → 체력 -1 + 무적 =====
  console.log('--- (4) 적 접촉 피격(옆/아래 접촉 = 스톰프 실패) → 체력 -1 + 무적 ---');
  setVar('무적', 0); setVar('중력', 0); setVar('낙하속도', 0); setVar('유효스폰간격', 0.3);
  // 적을 소년과 같은 높이(boy.y)에 두면 스톰프 조건(카메라선 > y+10)이 거짓 → 처치 대신 접촉 피격.
  // 스톰프가능=0 으로 강제해 박쥐/가시(반드시 쏘기) 상황을 재현.
  let foe = null;
  for (let g = 0; g < 10 && !foe; g++) { foe = clones('적')[0]; if (!foe) await sleep(300); }
  check('접촉 피격용 적 클론 확보', !!foe, foe ? 'ok' : 'none');
  if (foe) {
    setCloneLocal(foe, '스톰프가능', 0); // 박쥐/가시처럼 밟아도 안 죽는 적으로
    const hpBefore = Number(sv().체력);
    let hurt = false;
    for (let i = 0; i < 16; i++) {
      if (vm.runtime.targets.includes(foe)) foe.setXY(boy.x, boy.y); // 같은 높이=옆접촉
      await sleep(50);
      if (Number(sv().체력) < hpBefore) { hurt = true; break; }
    }
    const v = sv();
    check('적 접촉으로 체력 -1', Number(v.체력) === hpBefore - 1, `체력 ${hpBefore}→${v.체력}`);
    check('피격 후 무적 발동 (무적>0)', Number(v.무적) > 0, `무적=${v.무적}`);
  }

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'COLLISION CHECK: SOME CHECKS FAILED' : 'COLLISION CHECK COMPLETE — 명중·스톰프·발판착지·접촉피격 모두 등록됨.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
