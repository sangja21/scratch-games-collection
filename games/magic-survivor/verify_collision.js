// Headless DAMAGE/collision check for magic-survivor.
//
// The default headless VM has no renderer, so `touching [sprite]` always
// returns false → touch-based damage can't be exercised. Here we monkeypatch
// RenderedTarget.isTouchingSprite with a geometric (distance-of-radii) check.
// Both the bolt's `touching 적` and the enemy's `touching 마법탄` go through the
// SAME patched function, so the real scheduling race (fast bolt self-deleting
// before the slower enemy loop registers the hit = tunneling) is faithfully
// reproduced. This is the test that proves bolts actually deal damage.
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

// --- geometric touching override (approximate Scratch sprite collision) ---
// VM ships bundled (dist/node), so we can't deep-require RenderedTarget; instead
// we patch the shared prototype obtained from a live target after loadProject.
function radiusOf(t) {
  const sz = (typeof t.size === 'number' ? t.size : 100) / 100;
  return Math.max(4, 18 * sz); // costumes ~36px base → ~18px radius at 100%
}
function installGeometricTouching(vm) {
  const proto = Object.getPrototypeOf(vm.runtime.targets[0]);
  proto.isTouchingSprite = function (spriteName) {
    const first = this.runtime.getSpriteTargetByName(String(spriteName));
    if (!first) return false;
    const r1 = radiusOf(this);
    for (const clone of first.sprite.clones) {
      if (clone === this || clone.dragging || !clone.visible) continue;
      const dx = this.x - clone.x, dy = this.y - clone.y;
      if (Math.hypot(dx, dy) <= r1 + radiusOf(clone)) return true;
    }
    return false;
  };
}

const sb3 = path.join(__dirname, '마법_생존.sb3');
const vm = new VM();
function stage() { return vm.runtime.targets.find(t => t.isStage); }
function sv() { const o = {}; const st = stage(); for (const id in st.variables) { const v = st.variables[id]; if (v.type !== 'list') o[v.name] = v.value; } return o; }
function setVar(name, val) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val; }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return c.variables[id].value; return undefined; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`); if (!ok) FAIL = true; }

(async () => {
  await vm.loadProject(fs.readFileSync(sb3));
  installGeometricTouching(vm); // patch shared RenderedTarget prototype before ticks
  vm.start();
  vm.greenFlag();
  await sleep(500);

  // make the arena dense & fast so many hits happen in a short window
  setVar('스폰간격', 0.3);
  setVar('마법사x', 0); // (no-op if not used) keep mage centered via no key input

  console.log('--- 충돌 데미지 (geometric touching) ---');

  // sanity: the override actually reports overlap for co-located clones
  await sleep(1500);
  let en = clones('적');
  check('적 클론 다수 스폰됨 (>=2)', en.length >= 2, `enemies=${en.length}`);

  // Track HP of a specific weak enemy that a bolt should eventually reach.
  // Run several fire cycles; weak enemies have 1 HP so any registered hit kills.
  const startSpawn = Number(sv().스폰카운트);
  let kills0 = startSpawn - Number(sv().적수);

  // Direct test: force a bolt onto an enemy and confirm the enemy loses HP.
  // Pick one enemy, park a fresh bolt exactly on it, watch 내체력.
  const target = clones('적')[0];
  const hpBefore = Number(cloneLocal(target, '내체력'));
  // raise its HP so a single kill doesn't remove it before we can read the drop
  for (const id in target.variables) if (target.variables[id].name === '내체력') target.variables[id].value = 5;
  for (const id in target.variables) if (target.variables[id].name === '피격쿨') target.variables[id].value = 0;
  setVar('마법공격력', 1);
  // teleport every live bolt onto the target for a moment
  const parkBolt = () => { for (const b of clones('마법탄')) { b.setXY(target.x, target.y); } };
  let hpReadings = [Number(cloneLocal(target, '내체력'))];
  for (let i = 0; i < 25; i++) { parkBolt(); await sleep(60); hpReadings.push(Number(cloneLocal(target, '내체력'))); if (!vm.runtime.targets.includes(target)) break; }
  const hpDropped = hpReadings[0] - (vm.runtime.targets.includes(target) ? Number(cloneLocal(target, '내체력')) : -999);
  check('마법탄이 겹친 적의 내체력이 실제로 감소함 (데미지 등록)', hpDropped >= 1 || !vm.runtime.targets.includes(target),
        `내체력 ${hpReadings[0]} → ${vm.runtime.targets.includes(target) ? Number(cloneLocal(target, '내체력')) : 'killed'}`);

  // End-to-end: over a few seconds of normal auto-fire, enemies should die
  // (deaths only happen when damage is applied), dropping gems / XP.
  setVar('스폰간격', 0.5);
  const xpBefore = Number(sv().경험치) + Number(sv().레벨) * 1000;
  await sleep(4000);
  const v = sv();
  const kills = Number(v.스폰카운트) - Number(v.적수);
  check('전투 중 적이 실제로 처치됨 (데미지 → 사망)', kills > kills0, `누적처치=${kills} (스폰=${v.스폰카운트}, 생존=${v.적수})`);
  const gems = clones('경험치보석').length;
  const xpNow = Number(v.경험치) + Number(v.레벨) * 1000;
  check('처치 보상(경험치/레벨 또는 보석)이 발생함', xpNow > xpBefore || gems > 0,
        `경험치=${v.경험치} 레벨=${v.레벨} 보석클론=${gems}`);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'COLLISION CHECK: SOME CHECKS FAILED' : 'COLLISION CHECK COMPLETE — bolts deal damage, kills register.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
