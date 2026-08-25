const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const buf = fs.readFileSync(path.join(__dirname, '지아이조.sb3'));
const vm = new VM();

function stage() { return vm.runtime.targets.find(t => t.isStage); }
function vars() {
  const st = stage(); const o = {};
  for (const id in st.variables) {
    const v = st.variables[id];
    if (v.type !== 'list') o[v.name] = v.value;
  }
  return o;
}
function setVar(n, val) {
  const st = stage();
  for (const id in st.variables) if (st.variables[id].name === n) st.variables[id].value = val;
}
function getVar(n) { return Number(vars()[n]); }
function getList(n) {
  const st = stage();
  for (const id in st.variables) {
    const v = st.variables[id];
    if (v.type === 'list' && v.name === n) return v.value;
  }
  return [];
}
function clones(n) {
  return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === n && t.isOriginal === false);
}
function sprite(n) {
  return vm.runtime.targets.find(t => t.sprite && t.sprite.name === n && t.isOriginal);
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
  await sleep(500);

  console.log('--- 초기화 ---');
  const v = vars();
  check('게임상태=1', Number(v.게임상태) === 1, v.게임상태);
  check('체력=5', Number(v.체력) === 5, v.체력);
  check('탄속=10', Number(v.탄속) === 10, v.탄속);
  check('웨이브킬=16', Number(v.웨이브킬) === 16, v.웨이브킬);
  check('파워=0', Number(v.파워) === 0, v.파워);
  check('발사탄속', Number(v.발사탄속) === 10, v.발사탄속);
  check('파워배율', Number(v.파워배율) === 2.4, v.파워배율);
  check('브금볼륨', Number(v.브금볼륨) === 70, v.브금볼륨);
  const stageSounds = (stage().sprite.sounds || []).map(s => s.name);
  check('bgm 등록', stageSounds.includes('bgm'), stageSounds.join(','));
  const heights = getList('지형높이');
  check('지형 칸수=20', heights.length === 20, heights.length);
  const p = sprite('지아이조');
  check('지아이조 존재', !!p, p && `x=${p.x.toFixed(0)} y=${p.y.toFixed(0)}`);
  check('지아이조가 칸 지면 위', p && p.y < -40 && p.y > -130, p && p.y.toFixed(1));

  console.log('--- 지면 (점프 없음) ---');
  const y0 = p.y;
  await sleep(400);
  check('지면 유지', Math.abs(p.y - y0) < 10, `y ${y0.toFixed(1)}→${p.y.toFixed(1)}`);
  check('각도 초기값', getVar('각도') === 50, getVar('각도'));
  const costumes = (p.sprite.costumes || []).map(c => c.name);
  check('reload 없음', !costumes.includes('reload'), costumes.join(','));
  check('boom1 코스튬', costumes.includes('boom1'), costumes.join(','));
  check('방패 없음', !sprite('방패'));
  check('파워틀 존재', !!sprite('파워틀'));
  check('파워바 존재', !!sprite('파워바'));
  const bgs = ((stage().sprite && stage().sprite.costumes) || []).map(c => c.name);
  check('배경 6장', ['bg1','bg2','bg3','bg4','bg5','bg6'].every(n => bgs.includes(n)), bgs.join(','));
  check('보스 존재', !!sprite('보스'));
  check('스테이지=1', getVar('스테이지') === 1, getVar('스테이지'));
  check('보스전=0', getVar('보스전') === 0, getVar('보스전'));
  const shotSpr = sprite('총알');
  const shotCs = ((shotSpr && shotSpr.sprite.costumes) || []).map(c => c.name);
  check('총알 폭발프레임', ['boom1','boom2','boom3','boom4'].every(n => shotCs.includes(n)), shotCs.join(','));
  const shotSounds = ((shotSpr && shotSpr.sprite.sounds) || []).map(s => s.name);
  check('포발사 fire', shotSounds.includes('fire'), shotSounds.join(','));
  check('폭발음 boom', shotSounds.includes('boom'), shotSounds.join(','));
  const gun = sprite('총구');
  check('총구 존재', !!gun);
  await sleep(80);
  if (gun) {
    check('총구가 발사방향을 가리킴', Math.abs(gun.direction - getVar('발사방향')) < 12,
      `dir=${gun.direction.toFixed(0)} 발사방향=${getVar('발사방향')}`);
  }

  console.log('--- 총알 조준 ---');
  setVar('최대적수', 0);
  clones('적').forEach(c => vm.runtime.disposeTarget(c));
  setVar('적수', 0);
  setVar('탄수', 0);
  setVar('바라봄', 90);
  setVar('각도', 45);
  setVar('발사방향', 45);
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
  await sleep(150);
  const shots = clones('총알');
  check('총알 클론', shots.length >= 1, shots.length);
  if (shots.length) {
    const s = shots[0];
    const x0 = s.x;
    const sy0 = s.y;
    check('총알이 발보다 위에서 나감', s.y > p.y + 10, `탄y=${s.y.toFixed(0)} 발y=${p.y.toFixed(0)}`);
    await sleep(100);
    const yUp = s.y;
    check('곡사 상승', yUp > sy0, `${sy0.toFixed(0)}→${yUp.toFixed(0)}`);
    check('총알이 오른쪽으로 이동', s.x > x0 + 3, `${x0.toFixed(0)}→${s.x.toFixed(0)}`);
    await sleep(350);
    check('곡사 하강', s.y < yUp - 4, `${yUp.toFixed(0)}→${s.y.toFixed(0)}`);
    let sawBoom = false;
    for (let i = 0; i < 50; i++) {
      await sleep(40);
      const live = clones('총알');
      for (const c of live) {
        const cs = c.sprite.costumes || [];
        const nm = cs[c.currentCostume] && cs[c.currentCostume].name;
        if (nm && String(nm).startsWith('boom')) sawBoom = true;
      }
      if (sawBoom) break;
    }
    check('착탄 폭발 애니', sawBoom);
  }
  await sleep(80);
  if (gun) {
    check('45도일 때 총구도 위를 가리킴', gun.direction < 70, `dir=${gun.direction.toFixed(0)}`);
  }

  console.log('--- 웨이브 정지 ---');
  const px0 = p.x;
  setVar('게임상태', 3);
  await sleep(250);
  check('정지 중 주인공 안 움직임', Math.abs(p.x - px0) < 2, `${px0.toFixed(0)}→${p.x.toFixed(0)}`);
  setVar('게임상태', 1);

  console.log('--- 수류탄 포물선 ---');
  setVar('각도', 50);
  setVar('발사방향', 40);
  setVar('수류탄수', 0);
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '수류탄' });
  await sleep(120);
  const nades = clones('수류탄');
  check('수류탄 클론', nades.length >= 1, nades.length);
  if (nades.length) {
    const g = nades[0];
    const y0 = g.y;
    await sleep(150);
    const y1 = g.y;
    await sleep(400);
    const y2 = g.y;
    check('수류탄 올라갔다 떨어짐', y1 > y0 - 1 && y2 < y1 - 2, `y ${y0.toFixed(0)}→${y1.toFixed(0)}→${y2.toFixed(0)}`);
  }

  console.log('--- 적 ---');
  setVar('최대적수', 6);
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '적생성' });
  await sleep(250);
  const ens = clones('적');
  check('적 스폰', ens.length >= 1, ens.length);
  if (ens.length) {
    const e = ens[0];
    const x0 = e.x;
    await sleep(350);
    check('적 살아있음', vm.runtime.targets.includes(e), `x=${e.x.toFixed(0)}`);
  }

  console.log('--- 보스 사이클 ---');
  setVar('웨이브', 6);
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '맵변경' });
  await sleep(500);
  check('스테이지=6', getVar('스테이지') === 6, getVar('스테이지'));
  check('보스전=1', getVar('보스전') === 1, getVar('보스전'));
  const boss = sprite('보스');
  check('보스 보임', boss && boss.visible, boss && `vis=${boss.visible} x=${boss.x.toFixed(0)}`);
  check('보스체력>=8', getVar('보스체력') >= 8, getVar('보스체력'));

  process.exit(FAIL ? 1 : 0);
})().catch(err => { console.error(err); process.exit(1); });
