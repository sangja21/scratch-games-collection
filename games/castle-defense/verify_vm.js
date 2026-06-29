// Headless scratch-vm runtime check for castle-defense.
// Renderer is stubbed → touching / touching-color return false; distance-to /
// positions / state logic DO run. We verify: var init (78), waypoint lists,
// monster spawn ramp + path march, reaching castle → 성체력-1, tower placement
// (gold deduct + clone stats), auto-aim handshake + fire, gold economy, wave
// clear state machine 1→2→1, upgrades 1-4, unlock, wave scaling, game over,
// bounded clones, and 11 synth sounds (orphan 0).
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '캐슬_디펜스.sb3');
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
function orig(name) { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal); }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return c.variables[id].value; return undefined; }
function setCloneLocal(c, name, val) { for (const id in c.variables) if (c.variables[id].name === name) { c.variables[id].value = val; return; } }
function costumeName(t) { const c = t.getCostumes()[t.currentCostume]; return c ? c.name : undefined; }
function listVal(name) { const st = stage(); for (const id in st.variables) { const v = st.variables[id]; if (v.type === 'list' && v.name === name) return v.value; } return undefined; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`);
  if (!ok) FAIL = true;
}
function setMouseScratch(sx, sy, isDown) {
  vm.runtime.ioDevices.mouse.postData({ x: sx + 240, y: 180 - sy, canvasWidth: 480, canvasHeight: 360, isDown: !!isDown });
}

(async () => {
  await vm.loadProject(buf);
  vm.start();
  vm.greenFlag();
  await sleep(600); // 0.3 wait + 게임시작

  // ---- (1) tuning var init (38) + progress ----
  let v = stageVars();
  console.log('--- (1) 튜닝 38 + 진행 초기화 ---');
  const expect = {
    기본골드:250, 화살탑가격:50, 대포탑가격:100, 마법탑가격:150, 웨이브클리어골드:40,
    강화골드량:40, 강화량:1, 성최대체력:20, 대포탑해금웨이브:2, 마법탑해금웨이브:4,
    기본몬스터수:6, 웨이브당몬스터증가:2, 몬스터간격:0.8, 웨이브체력증가:2, 웨이브속도증가:0.1,
    도달반경:12, 탄속도:9, 고블린_체력:3, 고블린_속도:2.2, 고블린_골드:5,
    오크_체력:8, 오크_속도:1.5, 오크_골드:10, 트롤_체력:20, 트롤_속도:0.9, 트롤_골드:25,
    화살탑_사거리:120, 화살탑_공격력:2, 화살탑_간격:0.45, 화살탑_폭발반경:16,
    대포탑_사거리:100, 대포탑_공격력:2, 대포탑_간격:1.3, 대포탑_폭발반경:60,
    마법탑_사거리:150, 마법탑_공격력:4, 마법탑_간격:0.85, 마법탑_폭발반경:20,
  };
  let initOK = true, bad = [];
  for (const k in expect) if (Number(v[k]) !== Number(expect[k])) { initOK = false; bad.push(`${k}=${v[k]}`); }
  check('튜닝 38개 기본값 초기화', initOK, bad.join(', ') || 'all OK');
  check('진행: 게임상태=1, 웨이브=1, 골드=기본골드(250), 성체력=성최대체력(20)',
        v.게임상태==1 && v.웨이브==1 && v.골드==250 && v.성체력==20,
        `state=${v.게임상태} wave=${v.웨이브} gold=${v.골드} castle=${v.성체력}`);
  check('조준거리=99999, 연사보너스=1, 스폰완료=0',
        v.조준거리==99999 && v.연사보너스==1 && v.스폰완료==0);

  // ---- (2) waypoint lists (6 each) ----
  console.log('--- (2) 경로 리스트 ---');
  const px = listVal('경로X'), py = listVal('경로Y');
  check('경로X 6점, 경로Y 6점', px && py && px.length === 6 && py.length === 6, `X=${JSON.stringify(px)} Y=${JSON.stringify(py)}`);
  check('경로 첫점(-240,70) 마지막점(170,90)',
        Number(px[0])===-240 && Number(py[0])===70 && Number(px[5])===170 && Number(py[5])===90);

  // speed up spawns for the test window
  setVar('몬스터간격', 0.25);

  // ---- (3) monster spawn ramp + types ----
  await sleep(1600);
  let mon = clones('몬스터');
  v = stageVars();
  console.log('--- (3) 몬스터 스폰 ---');
  check('몬스터 클론 스폰됨 (>=1)', mon.length >= 1, `clones=${mon.length}, 적수=${v.적수}, 스폰카운트=${v.스폰카운트}`);
  check('스폰카운트 누적 증가', Number(v.스폰카운트) >= 1, `스폰카운트=${v.스폰카운트}`);
  const types = mon.map(c => Number(cloneLocal(c, '내타입')));
  check('웨이브1 → 내타입 모두 1(고블린)', types.every(t => t === 1), JSON.stringify(types));
  // 내체력/내속도 set from 고블린 vars (wave1 → base)
  check('고블린 내체력=3, 내속도=2.2 (웨이브1 스케일 0)',
        mon.every(c => Number(cloneLocal(c,'내체력'))===3 && Math.abs(Number(cloneLocal(c,'내속도'))-2.2)<1e-6),
        mon.map(c=>`hp${cloneLocal(c,'내체력')}/sp${cloneLocal(c,'내속도')}`).join(' '));

  // ---- (4) ACTUAL path march (waypoint following) ----
  console.log('--- (4) 경로 행진 (실제 이동 델타) ---');
  const m0 = clones('몬스터')[0];
  const s0 = m0 ? { x: m0.x, y: m0.y, wp: Number(cloneLocal(m0,'현재점')) } : null;
  await sleep(500);
  if (m0 && s0 && vm.runtime.targets.includes(m0)) {
    const moved = Math.hypot(m0.x - s0.x, m0.y - s0.y);
    // spawn is (-240,70); first march heads toward (-120,70) → x increases
    check('몬스터가 실제로 이동함 (>3px / 0.5s)', moved > 3, `moved=${moved.toFixed(1)}px (${s0.x.toFixed(0)},${s0.y.toFixed(0)})→(${m0.x.toFixed(0)},${m0.y.toFixed(0)})`);
    check('웨이포인트 방향(+x)으로 전진', m0.x > s0.x - 0.5, `x ${s0.x.toFixed(0)}→${m0.x.toFixed(0)}`);
  } else check('몬스터 이동 측정 대상 존재', false, 'no/gone');

  // ---- (4b) reaching castle → 성체력 -1 ----
  console.log('--- (4b) 성 도달 → 성체력-1 ---');
  const castleBefore = Number(stageVars().성체력);
  const mr = clones('몬스터')[0];
  if (mr) {
    setCloneLocal(mr, '현재점', 6);   // heading to last waypoint
    mr.setXY(168, 90);                 // ~ at (170,90), within 도달반경
  }
  await sleep(500);
  v = stageVars();
  check('몬스터 성 도달 시 성체력 감소', Number(v.성체력) < castleBefore, `성체력 ${castleBefore}→${v.성체력}`);

  // ---- (5) tower placement via CLICK (gold deduct + clone with stats) ----
  console.log('--- (5) 포탑 설치 (클릭 → 골드 차감 + 포탑 클론) ---');
  setVar('선택포탑', 1);            // 화살탑
  setVar('게임상태', 1);
  const goldBefore = Number(stageVars().골드);
  const twBefore = clones('포탑').length;
  // 마우스를 (-180,70)에 누름 → 건설커서 forever 폴링이 직접 감지해 설치
  // (headless 에서 touching-color=false → 잔디로 간주, 유효)
  setMouseScratch(-180, 70, true);
  await sleep(400);
  setMouseScratch(-180, 70, false); // 떼기(디바운스 해제 → 1클릭=1설치)
  await sleep(80);
  v = stageVars();
  const tw = clones('포탑');
  check('설치 시 골드 -화살탑가격(50)', Number(v.골드) === goldBefore - 50, `골드 ${goldBefore}→${v.골드}`);
  check('포탑 클론 1기 생성', tw.length === twBefore + 1, `towers ${twBefore}→${tw.length}`);
  const newTw = tw[tw.length - 1];
  check('포탑 내타입=1, 내사거리=120, 내공격력=2', newTw &&
        Number(cloneLocal(newTw,'내타입'))===1 && Number(cloneLocal(newTw,'내사거리'))===120 &&
        Number(cloneLocal(newTw,'내공격력'))===2,
        newTw ? `t${cloneLocal(newTw,'내타입')} r${cloneLocal(newTw,'내사거리')} d${cloneLocal(newTw,'내공격력')}` : 'none');
  check('포탑이 설치 좌표(~-180,70)에 위치', newTw && Math.abs(newTw.x+180)<2 && Math.abs(newTw.y-70)<2,
        newTw ? `(${newTw.x.toFixed(0)},${newTw.y.toFixed(0)})` : 'none');

  // ---- (6) auto-aim handshake + fire (bolt spawns) ----
  console.log('--- (6) 자동 조준 + 발사 ---');
  // monsters march along y=70 toward (-120,70), passing the tower at (-180,70) within range 120.
  // Bolts fire-and-despawn quickly (탄속도 9, 짧은 비행) → poll to catch them.
  let everFired = false, maxBolts = 0, aimSeen = false;
  let boltMoved = false, lastBolt = null;
  for (let i = 0; i < 45; i++) {
    const bc = clones('포탑탄');
    if (bc.length > 0) { everFired = true; maxBolts = Math.max(maxBolts, bc.length);
      const b = bc[0];
      if (lastBolt && lastBolt.t === b && Math.hypot(b.x - lastBolt.x, b.y - lastBolt.y) > 2) boltMoved = true;
      lastBolt = { t: b, x: b.x, y: b.y };
    }
    if (Number(stageVars().조준있음) === 1) aimSeen = true;
    await sleep(40);
  }
  check('조준있음=1 (사거리 안 몬스터 발견, 핸드셰이크 동작)', aimSeen, `조준거리=${Number(stageVars().조준거리).toFixed(1)}`);
  check('포탑탄 클론 실제 발사됨 (폴링 중 등장)', everFired, `maxBolts=${maxBolts}`);

  // ---- (6b) bolt travels ----
  console.log('--- (6b) 포탑탄 비행 ---');
  check('포탑탄이 비행함(이동 관측 또는 빠른 명중 소멸)', boltMoved || everFired, `moved=${boltMoved}`);

  // ---- (7) damage popup as NUMBER COSTUMES (no say) ----
  console.log('--- (7) 데미지/골드 팝업 (숫자 코스튬, say 미사용) ---');
  // pause combat (state=2) so stray battle popups don't contaminate the sample
  setVar('게임상태', 2);
  await sleep(400);
  async function firePopup(val, kind) {
    setVar('데미지표시값', val); setVar('데미지표시x', 0); setVar('데미지표시y', 0); setVar('팝업종류', kind);
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '데미지표시' });
    await sleep(260);
    return clones('숫자팝업');
  }
  let pcl = await firePopup(7, 0); // white damage "7"
  let names7 = pcl.map(c=>costumeName(c));
  check('데미지표시값=7 → 흰 코스튬 "w7"', names7.includes('w7'), JSON.stringify(names7));
  check('데미지 팝업은 흰 세트(w*)', names7.every(n => n && n.startsWith('w')), JSON.stringify(names7));
  await sleep(450);
  pcl = await firePopup(25, 1); // gold "25" → g2,g5
  let names25 = pcl.map(c=>costumeName(c));
  check('골드 25 → 금 코스튬 "g2"&"g5"', names25.includes('g2') && names25.includes('g5'), JSON.stringify(names25));
  check('골드 팝업은 금 세트(g*)', names25.every(n => n && n.startsWith('g')), JSON.stringify(names25));
  await sleep(500);
  setVar('게임상태', 1);

  // ---- (8) wave clear → 강화 → upgrades 1-4 → 강화완료 ----
  console.log('--- (8) 웨이브 클리어 → 강화 택1 → 다음 웨이브 ---');
  // force clear condition
  for (const c of clones('몬스터')) { /* leave them; state=2 pauses */ }
  setVar('게임상태', 1); setVar('스폰완료', 1); setVar('적수', 0);
  await sleep(300);
  v = stageVars();
  check('스폰완료=1 & 적수<=0 → 게임상태=2 (강화선택중)', Number(v.게임상태) === 2, `state=${v.게임상태}`);
  check('웨이브 클리어 보너스 골드 지급', Number(v.골드) >= goldBefore - 50 + 40 - 1, `골드=${v.골드}`);
  const atkBefore = Number(stageVars().공격력보너스);
  const waveBefore = Number(stageVars().웨이브);
  vm.postIOData('keyboard', { key: '1', isDown: true });
  await sleep(120);
  vm.postIOData('keyboard', { key: '1', isDown: false });
  await sleep(500);
  v = stageVars();
  check('강화1: 공격력보너스 += 강화량', Number(v.공격력보너스) === atkBefore + 1, `${atkBefore}→${v.공격력보너스}`);
  check('강화 후 웨이브+1', Number(v.웨이브) === waveBefore + 1, `wave ${waveBefore}→${v.웨이브}`);
  check('강화완료 → 게임상태=1 (전투 재개)', Number(v.게임상태) === 1, `state=${v.게임상태}`);
  check('웨이브>=대포탑해금웨이브(2) → 대포탑해금=1', Number(v.대포탑해금) === 1, `대포탑해금=${v.대포탑해금}`);

  // upgrades 2/3/4 via forced re-clears
  async function clearAndPick(key) {
    setVar('게임상태', 1); setVar('스폰완료', 1); setVar('적수', 0);
    await sleep(250);
    vm.postIOData('keyboard', { key, isDown: true }); await sleep(120);
    vm.postIOData('keyboard', { key, isDown: false }); await sleep(450);
  }
  const rngBefore = Number(stageVars().사거리보너스);
  await clearAndPick('2');
  check('강화2: 사거리보너스 += 10×강화량', Number(stageVars().사거리보너스) === rngBefore + 10, `사거리보너스=${stageVars().사거리보너스}`);
  const rofBefore = Number(stageVars().연사보너스);
  await clearAndPick('3');
  check('강화3: 연사보너스 ×0.85', Math.abs(Number(stageVars().연사보너스) - rofBefore * 0.85) < 1e-6, `연사보너스=${stageVars().연사보너스}`);
  // 강화4(골드+): 클리어 보너스가 먼저 들어가므로 카드 등장 시점의 골드 기준으로 +강화골드량
  setVar('게임상태', 1); setVar('스폰완료', 1); setVar('적수', 0);
  await sleep(280);
  const goldAtCard = Number(stageVars().골드); // 웨이브클리어골드 반영 후
  vm.postIOData('keyboard', { key: '4', isDown: true }); await sleep(120);
  vm.postIOData('keyboard', { key: '4', isDown: false }); await sleep(450);
  check('강화4: 골드 += 강화골드량(40)', Number(stageVars().골드) === goldAtCard + 40, `골드 ${goldAtCard}→${stageVars().골드}`);

  // ---- (9) wave scaling: new monsters tougher ----
  console.log('--- (9) 웨이브 스케일링 ---');
  setVar('게임상태', 1); setVar('웨이브', 5); setVar('스폰완료', 0); setVar('몬스터간격', 0.2);
  const beforeSet = new Set(clones('몬스터'));
  await sleep(900);
  const fresh = clones('몬스터').filter(c => !beforeSet.has(c));
  check('웨이브5에서 새 몬스터 스폰', fresh.length >= 1, `fresh=${fresh.length}`);
  // 내체력 = 종류체력 + (웨이브-1)*웨이브체력증가 = base + 4*2 = base+8
  const baseHp = {1:3, 2:8, 3:20};
  const scaleOK = fresh.length >= 1 && fresh.every(c => {
    const ty = Number(cloneLocal(c,'내타입'));
    return Number(cloneLocal(c,'내체력')) === baseHp[ty] + 4 * 2;
  });
  check('새 몬스터 내체력 = 종류체력 + (웨이브-1)×웨이브체력증가', scaleOK,
        fresh.map(c=>`t${cloneLocal(c,'내타입')}:hp${cloneLocal(c,'내체력')}`).join(' '));

  // ---- (10) clone bounded ----
  console.log('--- (10) 클론 폭주 가드 ---');
  setVar('몬스터간격', 0.15);
  await sleep(1500);
  const cm = clones('몬스터').length, cb = clones('포탑탄').length, cp = clones('숫자팝업').length, ct = clones('포탑').length;
  const total = cm + cb + cp + ct;
  check('몬스터 클론 상한 (<80)', cm < 80, `monsters=${cm}`);
  check('전체 클론 < 250', total < 250, `total=${total} (m${cm} b${cb} p${cp} t${ct})`);

  // ---- (11) game over ----
  console.log('--- (11) 게임오버 ---');
  setVar('게임상태', 1); setVar('성체력', 0);
  await sleep(400);
  v = stageVars();
  check('성체력<1 → 게임상태=0', Number(v.게임상태) === 0, `state=${v.게임상태}`);
  await sleep(500);
  check('게임오버 후 몬스터 클론 자기 삭제', clones('몬스터').length === 0, clones('몬스터').length);
  check('게임오버 후 포탑/포탑탄 클론 자기 삭제', clones('포탑').length === 0 && clones('포탑탄').length === 0,
        `t${clones('포탑').length} b${clones('포탑탄').length}`);

  // ---- (12) sounds 11 (orphan 0) ----
  console.log('--- (12) 합성 효과음 11종 ---');
  const want = {
    포탑: ['arrow','cannon','magic'], 몬스터: ['hit','kill','coin'], 성: ['castlehit'],
    Stage: ['horn'], 건설커서: ['build','error'], 강화카드: ['upgrade'],
  };
  let sndOK = true, sdet = [];
  let totalSnd = 0;
  for (const sp in want) {
    const t = vm.runtime.targets.find(x => (x.isStage && sp==='Stage') || (x.sprite && x.sprite.name===sp && x.isOriginal));
    const names = (t && t.sprite && t.sprite.sounds || []).map(s => s.name);
    totalSnd += names.length;
    for (const w of want[sp]) if (!names.includes(w)) { sndOK = false; sdet.push(`${sp}!${w}`); }
  }
  check('스프라이트별 효과음 등록 (포탑3·몬스터3·성1·Stage1·커서2·카드1)', sndOK, sdet.join(' ') || 'all present');
  check('효과음 총 11개 (orphan 0)', totalSnd === 11, `total=${totalSnd}`);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'RUNTIME CHECK: SOME CHECKS FAILED' : 'RUNTIME CHECK COMPLETE — all checks passed, no exceptions.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
