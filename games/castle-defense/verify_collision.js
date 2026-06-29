// Headless collision / color-gate check for castle-defense.
//
// The default headless VM has no renderer → `touching [sprite]` and
// `touching color` always return false. Two things in this game lean on those:
//   (1) 탄 광역 타격: the bolt's `touching 몬스터` stop is renderer-bound, BUT the
//       actual area damage (타격) is DISTANCE-based (폭발반경) so it works headless.
//       We still install a geometric isTouchingSprite so end-to-end auto-fire kills
//       reproduce faithfully.
//   (2) 포탑 배치 유효성(길 위 금지): the build cursor decides with
//       `touching color [길색]`. We monkeypatch isTouchingColor to a controllable
//       flag and prove BOTH directions (on-path → rejected, off-path → placed) —
//       i.e. sensitivity: if the build ignored color the on-path case would FAIL.
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

let ONPATH = false; // controls patched isTouchingColor (true = cursor sits on 길색)

function radiusOf(t) {
  const sz = (typeof t.size === 'number' ? t.size : 100) / 100;
  return Math.max(4, 18 * sz);
}
function installPatches(vm) {
  const proto = Object.getPrototypeOf(vm.runtime.targets[0]);
  proto.isTouchingSprite = function (spriteName) {
    const first = this.runtime.getSpriteTargetByName(String(spriteName));
    if (!first) return false;
    const r1 = radiusOf(this);
    const all = [first, ...first.sprite.clones];
    for (const clone of all) {
      if (clone === this || clone.dragging || !clone.visible) continue;
      const dx = this.x - clone.x, dy = this.y - clone.y;
      if (Math.hypot(dx, dy) <= r1 + radiusOf(clone)) return true;
    }
    return false;
  };
  // geometric color gate: cursor "touches 길색" iff ONPATH flag set
  proto.isTouchingColor = function () { return ONPATH; };
}

const sb3 = path.join(__dirname, '캐슬_디펜스.sb3');
const vm = new VM();
function stage() { return vm.runtime.targets.find(t => t.isStage); }
function sv() { const o = {}; const st = stage(); for (const id in st.variables) { const v = st.variables[id]; if (v.type !== 'list') o[v.name] = v.value; } return o; }
function setVar(name, val) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val; }
function orig(name) { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal); }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return c.variables[id].value; return undefined; }
function setCloneLocal(c, name, val) { for (const id in c.variables) if (c.variables[id].name === name) { c.variables[id].value = val; return; } }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`); if (!ok) FAIL = true; }
function setMouseScratch(sx, sy, isDown) {
  vm.runtime.ioDevices.mouse.postData({ x: sx + 240, y: 180 - sy, canvasWidth: 480, canvasHeight: 360, isDown: !!isDown });
}

(async () => {
  await vm.loadProject(fs.readFileSync(sb3));
  installPatches(vm);
  vm.start();
  vm.greenFlag();
  await sleep(600);

  // ---- (A) 타격 광역 데미지 (반경 안 모두 / 반경 밖 제외) ----
  console.log('--- (A) 타격 광역/단일 데미지 (거리 기반 반경 판정) ---');
  setVar('몬스터간격', 0.25);
  await sleep(1400);
  let mon = clones('몬스터');
  check('몬스터 다수 스폰 (>=3)', mon.length >= 3, `monsters=${mon.length}`);
  // cluster 3 near (0,0), park one far at (200,0). raise HP so they survive to read drop.
  const near = mon.slice(0, 3), far = mon[3] || null;
  for (const m of near) { m.setXY(0, 0); setCloneLocal(m, '내체력', 20); }
  if (far) { far.setXY(200, 0); setCloneLocal(far, '내체력', 20); }
  setVar('게임상태', 1);
  setVar('폭발X', 0); setVar('폭발Y', 0); setVar('폭발데미지', 5); setVar('폭발반경', 50);
  const nearBefore = near.map(m => Number(cloneLocal(m, '내체력')));
  const farBefore = far ? Number(cloneLocal(far, '내체력')) : null;
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '타격' });
  await sleep(120);
  const nearAfter = near.map(m => vm.runtime.targets.includes(m) ? Number(cloneLocal(m, '내체력')) : -999);
  const multiOK = near.every((m, i) => nearBefore[i] - nearAfter[i] === 5);
  check('폭발반경 안 몬스터 3마리 모두 -폭발데미지(5)', multiOK,
        near.map((m, i) => `${nearBefore[i]}→${nearAfter[i]}`).join(' '));
  if (far) {
    const farAfter = vm.runtime.targets.includes(far) ? Number(cloneLocal(far, '내체력')) : -999;
    check('폭발반경 밖 몬스터(200,0)는 피해 없음 (민감도)', farAfter === farBefore, `${farBefore}→${farAfter}`);
  } else check('반경 밖 대상 존재', true, 'skip');

  // ---- (B) 포탑 배치 색 게이트 (길 위 금지) — 민감도 양방향 ----
  console.log('--- (B) 포탑 배치 유효성: 길색 감지 게이트 (민감도) ---');
  setVar('게임상태', 1);
  setVar('선택포탑', 1);
  const cursor = orig('건설커서');
  setMouseScratch(-100, -100, true); // 스프라이트와 안 겹치는 지점
  // (B1) ON-PATH → 설치 거부 (골드 불변, 포탑 클론 불변)
  ONPATH = true;
  let goldA = Number(sv().골드), twA = clones('포탑').length;
  vm.runtime.startHats('event_whenthisspriteclicked', null, cursor);
  await sleep(350);
  let goldB = Number(sv().골드), twB = clones('포탑').length;
  check('길 위(touching color 길색=true) → 설치 거부: 골드 불변·포탑 미생성', goldB === goldA && twB === twA,
        `골드 ${goldA}→${goldB}, 포탑 ${twA}→${twB}`);
  // (B2) OFF-PATH → 설치 성공 (골드 -50, 포탑 +1) ⇒ (B1)이 진짜 색 때문에 막혔음을 증명
  ONPATH = false;
  goldA = Number(sv().골드); twA = clones('포탑').length;
  setMouseScratch(-100, -100, true);
  vm.runtime.startHats('event_whenthisspriteclicked', null, cursor);
  await sleep(350);
  goldB = Number(sv().골드); twB = clones('포탑').length;
  check('잔디 위(길색=false) → 설치 성공: 골드 -50·포탑 +1', goldB === goldA - 50 && twB === twA + 1,
        `골드 ${goldA}→${goldB}, 포탑 ${twA}→${twB}`);

  // ---- (C) end-to-end: 자동 발사 → 몬스터 처치 → 골드 ----
  console.log('--- (C) 전투 종합: 자동 발사 → 처치 → 골드 ---');
  // place a couple towers right on the y=70 lane so marching monsters get shot
  for (const [tx, ty] of [[-150, 70], [-60, 70], [-120, -50]]) {
    setVar('설치X', tx); setVar('설치Y', ty); setVar('설치타입', 1);
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '포탑설치' });
    await sleep(120);
  }
  setVar('몬스터간격', 0.4);
  const spawnBefore = Number(sv().스폰카운트);
  const killsBefore = Number(sv().스폰카운트) - Number(sv().적수);
  const goldStart = Number(sv().골드);
  await sleep(5000);
  const s = sv();
  const kills = Number(s.스폰카운트) - Number(s.적수);
  check('전투 중 몬스터가 실제로 처치됨 (데미지 → 사망)', kills > killsBefore,
        `누적처치 ${killsBefore}→${kills} (스폰=${s.스폰카운트}, 생존=${s.적수})`);
  check('처치 보상으로 골드 증가', Number(s.골드) > goldStart, `골드 ${goldStart}→${s.골드}`);
  check('클론 폭주 없음 (몬스터<80, 포탑탄<120)', clones('몬스터').length < 80 && clones('포탑탄').length < 120,
        `m${clones('몬스터').length} b${clones('포탑탄').length}`);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'COLLISION CHECK: SOME CHECKS FAILED' : 'COLLISION CHECK COMPLETE — area damage + color gate + kills verified.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
