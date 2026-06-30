// Headless scratch-vm runtime check for castle-defense.
// Renderer is stubbed → touching / touching-color return false; distance-to /
// positions / state logic DO run. We verify: var init (79), waypoint lists,
// monster spawn ramp + path march, reaching castle → 성체력-1, tower placement
// (gold deduct + clone stats), auto-aim handshake + fire, gold economy, wave
// clear state machine 1→2→1, upgrades 1-4, unlock, wave scaling, ⚡ 전체 번개
// 주문(스페이스/HUD 시전·전체 데미지·연타 가드·재충전), game over, bounded
// clones, and 14 synth sounds (orphan 0).
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
  console.log('--- (1) 튜닝 42 + 진행 초기화 ---');
  const expect = {
    기본골드:250, 화살탑가격:50, 대포탑가격:100, 마법탑가격:150, 웨이브클리어골드:40,
    강화골드량:40, 강화량:1, 성최대체력:20, 대포탑해금웨이브:2, 마법탑해금웨이브:4,
    기본몬스터수:6, 웨이브당몬스터증가:3, 몬스터간격:0.8, 웨이브체력증가:8, 웨이브속도증가:0.13,
    도달반경:12, 탄속도:9, 고블린_체력:3, 고블린_속도:2.2, 고블린_골드:5,
    오크_체력:8, 오크_속도:1.5, 오크_골드:10, 트롤_체력:20, 트롤_속도:0.9, 트롤_골드:25,
    화살탑_사거리:120, 화살탑_공격력:2, 화살탑_간격:0.45, 화살탑_폭발반경:16,
    대포탑_사거리:100, 대포탑_공격력:3, 대포탑_간격:1.3, 대포탑_폭발반경:60,
    마법탑_사거리:150, 마법탑_공격력:5, 마법탑_간격:0.85, 마법탑_폭발반경:20,
    수리비용:60, 수리량:5, 주문공격력:9999, 주문쿨:20, 주문최대횟수:3,
  };
  let initOK = true, bad = [];
  for (const k in expect) if (Number(v[k]) !== Number(expect[k])) { initOK = false; bad.push(`${k}=${v[k]}`); }
  check('튜닝 43개 기본값 초기화 (주문공격력9999=원턴킬·주문쿨20·주문최대횟수3 포함)', initOK, bad.join(', ') || 'all OK');
  check('진행: 주문쿨남음=0 (전체 번개 준비됨)', Number(v.주문쿨남음) === 0, `주문쿨남음=${v.주문쿨남음}`);
  check('진행: 주문횟수=주문최대횟수(3) — 게임 재시작 시 3번 충전', Number(v.주문횟수) === 3, `주문횟수=${v.주문횟수}`);
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
  // 강화4(골드+): 전투 노이즈(처치 골드) 제거 후 검증 — 안 그러면 검사 중 몬스터가 죽으며
  // 처치 골드가 섞여 +강화골드량보다 더 들어와 플래키. 포탑 발사를 멈추고(발사쿨 크게)
  // 남은 몬스터를 무적화해 처치 자체를 차단. (몬스터간격은 안 건드려야 이후 웨이브5 검사가 정상)
  for (const c of clones('포탑')) setCloneLocal(c, '발사쿨', 99999);
  for (const c of clones('몬스터')) setCloneLocal(c, '내체력', 99999);
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
  // 내체력 = 종류체력 + (웨이브-1)*웨이브체력증가 (웨이브5 → 4 × 웨이브체력증가)
  const baseHp = {1:3, 2:8, 3:20};
  const hpInc = Number(stageVars().웨이브체력증가);
  const scaleOK = fresh.length >= 1 && fresh.every(c => {
    const ty = Number(cloneLocal(c,'내타입'));
    return Number(cloneLocal(c,'내체력')) === baseHp[ty] + 4 * hpInc;
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

  // ---- (G) 유령 미리보기 (시각 전용: 존재·코스튬3·선택포탑별 코스튬 전환) ----
  console.log('--- (G) 유령 미리보기 ---');
  // 깨끗한 전투 상태 고정: 게임오버 감시(성체력<1)와 웨이브클리어 감시(스폰완료=1&적수<1)가
  // 게임상태를 0/2 로 흔들지 않도록 성체력=max, 적수>0 로 둔다.
  setVar('성체력', 20); setVar('스폰완료', 1); setVar('적수', 5); setVar('게임상태', 1);
  const ghost = orig('유령미리보기');
  check('유령미리보기 스프라이트 존재', !!ghost);
  check('유령 코스튬 3개', ghost && ghost.getCostumes().length === 3,
        ghost ? ghost.getCostumes().map(c=>c.name).join(',') : 'none');
  setVar('게임상태', 1); setVar('선택포탑', 2); setMouseScratch(0, 0, false);
  await sleep(220);
  check('선택포탑=2 → 유령 코스튬 2번(대포탑미리)', ghost && costumeName(ghost) === '대포탑미리', ghost && costumeName(ghost));
  check('선택포탑>0 & 게임상태=1 → 유령 보임', ghost && ghost.visible === true, ghost && ghost.visible);
  setVar('선택포탑', 3); await sleep(220);
  check('선택포탑=3 → 유령 코스튬 3번(마법탑미리)', ghost && costumeName(ghost) === '마법탑미리', ghost && costumeName(ghost));
  setVar('선택포탑', 1); await sleep(220);
  check('선택포탑=1 → 유령 코스튬 1번(화살탑미리)', ghost && costumeName(ghost) === '화살탑미리', ghost && costumeName(ghost));
  setVar('선택포탑', 0); await sleep(220);
  check('선택포탑=0 → 유령 숨김(시각 전용, 설치판정 무관)', ghost && ghost.visible === false, ghost && ghost.visible);
  // 선택표시(하이라이트)도 선택포탑에 따라 위치/표시
  const hl = orig('선택표시');
  check('선택표시 스프라이트 존재', !!hl);
  setVar('선택포탑', 2); await sleep(160);
  check('선택포탑=2 → 선택표시 보임 & 버튼2 위치(x≈-58)', hl && hl.visible === true && Math.abs(hl.x + 58) < 2, hl && `vis=${hl.visible} x=${hl.x}`);
  setVar('선택포탑', 0); await sleep(160);
  check('선택포탑=0 → 선택표시 숨김', hl && hl.visible === false, hl && hl.visible);

  // ---- (P) 팔레트 버튼 폴링: 한 버튼 고른 뒤에도 다른 버튼이 먹힘 (버그 회귀 가드) ----
  // 예전 버그: 화살탑을 고르면 유령미리보기(맨 앞)가 마우스 위에 떠 다음 버튼의 when-clicked 를
  // 가로채 안 눌렸음. 이제 마우스 누름 폴링이라 front 가림과 무관하게 동작 — 1 고른 뒤 2/3/4 도달 검증.
  console.log('--- (P) 팔레트 버튼 폴링 (1 고른 뒤 2·3·4 도달) ---');
  // 웨이브클리어/게임오버 감시가 흔들지 않게 고정 + 대포/마법 강제 해금
  setVar('스폰완료', 1); setVar('적수', 5); setVar('성체력', 20);
  setVar('게임상태', 1); setVar('대포탑해금', 1); setVar('마법탑해금', 1);
  // 골드를 낮게(40) 둬서 건설커서 폴링이 팔레트 띠에서 포탑을 설치하지 못하게(40 < 모든 포탑가격)
  // → headless 는 front 가림은 못 보지만, '마우스 y<-116 팔레트 띠' 폴링 경로는 그대로 재현됨.
  setVar('골드', 40); setVar('선택포탑', 0);
  // 팔레트 띠 한 가운데 y=-150. 버튼 중심 x: 1→-174, 2→-58, 3→58, 4→174
  async function pressPalette(sx) {     // 누름→대기→떼기 (1클릭=1동작 디바운스)
    setMouseScratch(sx, -150, true); await sleep(200);
    setMouseScratch(sx, -150, false); await sleep(140);
  }
  await pressPalette(-174);
  check('팔레트 버튼1(화살탑) 폴링 클릭 → 선택포탑=1', Number(stageVars().선택포탑) === 1, `선택포탑=${stageVars().선택포탑}`);
  await pressPalette(-58);
  check('버튼1 고른 뒤에도 버튼2(대포탑) 먹힘 → 선택포탑=2 (버그 회귀 가드)', Number(stageVars().선택포탑) === 2, `선택포탑=${stageVars().선택포탑}`);
  await pressPalette(58);
  check('버튼2 고른 뒤에도 버튼3(마법탑) 먹힘 → 선택포탑=3 (버그 회귀 가드)', Number(stageVars().선택포탑) === 3, `선택포탑=${stageVars().선택포탑}`);
  check('버튼 폴링 동안 골드 불변(팔레트 띠 클릭은 포탑 설치 안 됨, 40)', Number(stageVars().골드) === 40, `골드=${stageVars().골드}`);

  // ---- (R) 성수리 버튼 (팔레트 4구간 = 마우스 x≥116, y<-116 띠 폴링) ----
  console.log('--- (R) 성수리 (4번째 팔레트 버튼, 폴링) ---');
  setVar('스폰완료', 1); setVar('적수', 5);
  setVar('게임상태', 1); setVar('성최대체력', 20); setVar('수리비용', 60); setVar('수리량', 5);
  // 선택포탑=3(마법, 가격150) 유지 → 골드 140 이면 건설커서는 설치 실패(140<150)지만 수리(140≥60)는 성공.
  // 즉 4번 버튼은 '한 버튼 고른 뒤에도' 먹히고, 성수리는 선택포탑(3)을 안 바꿈을 함께 검증.
  // case 1: 골드 충분 + 성 안 풀피 → 수리
  setVar('골드', 140); setVar('성체력', 10); setVar('선택포탑', 3);
  await pressPalette(174);
  let r = stageVars();
  check('성수리: 골드 -수리비용 (140→80)', Number(r.골드) === 80, `골드=${r.골드}`);
  check('성수리: 성체력 +수리량 (10→15)', Number(r.성체력) === 15, `성체력=${r.성체력}`);
  check('버튼3 고른 뒤에도 버튼4(성수리) 먹힘 & 선택포탑 불변(여전히 3)', Number(r.선택포탑) === 3, `선택포탑=${r.선택포탑}`);
  // case 2: 상한 클램프 (성체력 18 + 5 = 23 → 20)
  setVar('골드', 140); setVar('성체력', 18);
  await pressPalette(174);
  r = stageVars();
  check('성수리 상한 클램프: 성체력 18→20 (24 아님, 민감도)', Number(r.성체력) === 20, `성체력=${r.성체력}`);
  check('클램프 시에도 골드는 차감됨 (140→80)', Number(r.골드) === 80, `골드=${r.골드}`);
  // case 3: 이미 풀피 → 변화 없음
  setVar('골드', 140); setVar('성체력', 20);
  await pressPalette(174);
  r = stageVars();
  check('이미 풀피면 수리 안 됨 (골드·성체력 불변)', Number(r.골드) === 140 && Number(r.성체력) === 20, `골드=${r.골드} 성체력=${r.성체력}`);
  // case 4: 골드 부족 → 변화 없음 (수리비용 60 > 골드 30)
  setVar('골드', 30); setVar('성체력', 10);
  await pressPalette(174);
  r = stageVars();
  check('골드 부족 시 수리 안 됨 (골드·성체력 불변, 민감도)', Number(r.골드) === 30 && Number(r.성체력) === 10, `골드=${r.골드} 성체력=${r.성체력}`);
  setVar('선택포탑', 0); setMouseScratch(0, 0, false);

  // ---- (S) ⚡ 전체 번개 주문 (스페이스 / HUD 버튼 시전) ----
  console.log('--- (S) 전체 번개 주문 ⚡ ---');
  // 깨끗한 전투 상태: 게임오버/클리어 감시가 게임상태를 흔들지 않게 성체력=max, 적수>0
  setVar('성체력', 20); setVar('스폰완료', 1); setVar('적수', 5);
  setVar('게임상태', 1); setVar('웨이브', 1);
  setVar('주문공격력', 5); setVar('주문쿨', 6); setVar('주문쿨남음', 0);
  setVar('주문횟수', 99); // (S)/(S2) 회귀 테스트는 횟수 가드에 막히지 않게 충분히 세팅
  // 화면에 몬스터 3마리 스폰
  setVar('생성타입', 1);
  for (let i = 0; i < 3; i++) { vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '몬스터생성' }); await sleep(70); }
  await sleep(200);
  let smon = clones('몬스터').filter(c => vm.runtime.targets.includes(c));
  // 클린 델타 측정용으로 체력을 높게(번개로 죽지 않게)
  for (const c of smon) setCloneLocal(c, '내체력', 50);
  check('번개 테스트용 몬스터 존재 (>=1)', smon.length >= 1, `mon=${smon.length}`);
  // 스페이스 키 시전
  vm.runtime.startHats('event_whenkeypressed', { KEY_OPTION: 'space' });
  await sleep(250);
  v = stageVars();
  const allHit = smon.length >= 1 && smon.every(c => Number(cloneLocal(c, '내체력')) === 45);
  check('스페이스 시전 → 화면 모든 몬스터 내체력 -= 주문공격력(5): 50→45', allHit,
        smon.map(c => cloneLocal(c, '내체력')).join(' '));
  check('시전 시 주문쿨남음 = 주문쿨(6, 재충전 시작)', Number(v.주문쿨남음) > 5 && Number(v.주문쿨남음) <= 6,
        `주문쿨남음=${Number(v.주문쿨남음).toFixed(2)}`);
  // 연타 가드: 쿨 중(주문쿨남음>0) 재시전 차단
  vm.runtime.startHats('event_whenkeypressed', { KEY_OPTION: 'space' });
  await sleep(200);
  const guardOK = smon.every(c => Number(cloneLocal(c, '내체력')) === 45);
  check('쿨 중(주문쿨남음>0) 재시전 차단 — 내체력 불변(연타 가드 민감도)', guardOK,
        smon.map(c => cloneLocal(c, '내체력')).join(' '));
  // 재충전: 시간 지나며 주문쿨남음 감소
  const left1 = Number(stageVars().주문쿨남음);
  await sleep(600);
  const left2 = Number(stageVars().주문쿨남음);
  check('시간이 지나며 주문쿨남음 감소(재충전)', left2 < left1, `${left1.toFixed(2)}→${left2.toFixed(2)}`);
  // HUD 버튼 클릭 시전 (쿨 리셋 후) — 주문버튼 타깃만 클릭
  setVar('주문쿨남음', 0);
  const sbtn = orig('주문버튼');
  check('주문버튼(HUD) 스프라이트 존재 + 코스튬 3(준비됨/충전중/소진)', !!sbtn && sbtn.getCostumes().length === 3,
        sbtn ? sbtn.getCostumes().map(c => c.name).join(',') : 'none');
  const before3 = smon.map(c => Number(cloneLocal(c, '내체력')));
  vm.runtime.startHats('event_whenthisspriteclicked', null, sbtn);
  await sleep(220);
  const clickOK = smon.every((c, i) => Number(cloneLocal(c, '내체력')) === before3[i] - 5);
  check('HUD 버튼 클릭 시전 → 몬스터 내체력 -= 주문공격력(45→40)', clickOK,
        smon.map(c => cloneLocal(c, '내체력')).join(' '));
  check('버튼 클릭 시전 후 주문쿨남음=주문쿨(>5)', Number(stageVars().주문쿨남음) > 5,
        `주문쿨남음=${Number(stageVars().주문쿨남음).toFixed(2)}`);
  // 게임상태≠1 (강화/오버) 일 때 시전 차단
  setVar('주문쿨남음', 0); setVar('게임상태', 2);
  const before4 = smon.map(c => Number(cloneLocal(c, '내체력')));
  vm.runtime.startHats('event_whenkeypressed', { KEY_OPTION: 'space' });
  await sleep(200);
  const stateBlock = smon.every((c, i) => Number(cloneLocal(c, '내체력')) === before4[i]);
  check('게임상태≠1 일 때 시전 차단 (전투중만 발동)', stateBlock,
        smon.map(c => cloneLocal(c, '내체력')).join(' '));
  setVar('게임상태', 1);

  // (S2) 기본값 주문공격력=9999 → 원턴킬: 단단한 몬스터도 한 방에 전멸
  console.log('--- (S2) 원턴킬 (기본 주문공격력 9999) ---');
  setVar('주문공격력', 9999); setVar('주문쿨남음', 0);
  for (const c of smon) if (vm.runtime.targets.includes(c)) setCloneLocal(c, '내체력', 500); // 일부러 매우 단단하게
  const aliveBefore = smon.filter(c => vm.runtime.targets.includes(c)).length;
  vm.runtime.startHats('event_whenkeypressed', { KEY_OPTION: 'space' });
  await sleep(400); // 처치 루프(폭발/삭제)까지 시간
  const aliveAfter = clones('몬스터').filter(c => smon.includes(c) && vm.runtime.targets.includes(c)).length;
  check('주문공격력 9999 → 체력 500짜리도 전부 처치 (원턴킬)', aliveBefore >= 1 && aliveAfter === 0,
        `생존 ${aliveBefore}→${aliveAfter}`);

  // ---- (S3) 제한 자원형 궁극기: 게임당 주문최대횟수(3)번·긴 쿨(20) ----
  console.log('--- (S3) 제한 자원 궁극기 (3번·긴 쿨) ---');
  setVar('성체력', 20); setVar('스폰완료', 1); setVar('적수', 5);
  setVar('게임상태', 1); setVar('웨이브', 1);
  setVar('주문공격력', 5); setVar('주문쿨', 20); setVar('주문최대횟수', 3);
  // 신선한 몬스터 2마리 스폰(앞 (S2)에서 모두 처치됨) — 번개로 안 죽게 체력 높임
  setVar('생성타입', 1);
  for (let i = 0; i < 2; i++) { vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '몬스터생성' }); await sleep(70); }
  await sleep(200);
  let s3mon = clones('몬스터').filter(c => vm.runtime.targets.includes(c));
  for (const c of s3mon) setCloneLocal(c, '내체력', 50);
  check('(S3) 테스트용 몬스터 존재 (>=1)', s3mon.length >= 1, `mon=${s3mon.length}`);

  // 1회 시전 → 주문횟수 3→2, 주문쿨남음=주문쿨(20)
  setVar('주문횟수', 3); setVar('주문쿨남음', 0);
  vm.runtime.startHats('event_whenkeypressed', { KEY_OPTION: 'space' });
  await sleep(230);
  v = stageVars();
  check('1회 시전 → 주문횟수 3→2 (1회 차감)', Number(v.주문횟수) === 2, `주문횟수=${v.주문횟수}`);
  check('1회 시전 → 주문쿨남음=주문쿨(20)', Number(v.주문쿨남음) > 19 && Number(v.주문쿨남음) <= 20,
        `주문쿨남음=${Number(v.주문쿨남음).toFixed(2)}`);

  // 3회 소진: 쿨을 매번 0으로 풀어주며 3번 시전 → 주문횟수 3→0
  setVar('주문횟수', 3);
  for (let i = 0; i < 3; i++) {
    setVar('주문쿨남음', 0);
    vm.runtime.startHats('event_whenkeypressed', { KEY_OPTION: 'space' });
    await sleep(200);
  }
  v = stageVars();
  check('3회 시전(쿨 매번 0으로 풀어줌) → 주문횟수 3→0 (소진)', Number(v.주문횟수) === 0, `주문횟수=${v.주문횟수}`);

  // 4번째 시전 차단: 쿨이 풀려 있어도 주문횟수=0 이면 발동 안 됨
  s3mon = s3mon.filter(c => vm.runtime.targets.includes(c));
  const before4th = s3mon.map(c => Number(cloneLocal(c, '내체력')));
  setVar('주문쿨남음', 0);
  vm.runtime.startHats('event_whenkeypressed', { KEY_OPTION: 'space' });
  await sleep(230);
  const block4 = s3mon.length >= 1 && s3mon.every((c, i) => Number(cloneLocal(c, '내체력')) === before4th[i]);
  check('4번째 시전 차단 — 주문횟수=0 → 몬스터 내체력 불변', block4,
        s3mon.map(c => cloneLocal(c, '내체력')).join(' '));
  check('4번째 차단 → 주문횟수 음수 안 됨 (0 유지)', Number(stageVars().주문횟수) === 0,
        `주문횟수=${stageVars().주문횟수}`);
  // HUD 클릭도 동일하게 차단되는지(같은 가드)
  const sbtn3 = orig('주문버튼');
  setVar('주문쿨남음', 0);
  const beforeClick = s3mon.map(c => Number(cloneLocal(c, '내체력')));
  vm.runtime.startHats('event_whenthisspriteclicked', null, sbtn3);
  await sleep(220);
  const blockClick = s3mon.length >= 1 && s3mon.every((c, i) => Number(cloneLocal(c, '내체력')) === beforeClick[i]);
  check('소진 상태 HUD 클릭도 차단 (주문횟수=0)', blockClick,
        s3mon.map(c => cloneLocal(c, '내체력')).join(' '));

  // ---- (12) sounds 14 (orphan 0) ----
  console.log('--- (12) 합성 효과음 14종 ---');
  const want = {
    포탑: ['arrow','cannon','magic'], 몬스터: ['hit','kill','coin'], 성: ['castlehit'],
    Stage: ['horn'], 건설커서: ['build','error'], 강화카드: ['upgrade'],
    팔레트: ['repair','error'], 주문버튼: ['thunder'],
  };
  let sndOK = true, sdet = [];
  let totalSnd = 0;
  for (const sp in want) {
    const t = vm.runtime.targets.find(x => (x.isStage && sp==='Stage') || (x.sprite && x.sprite.name===sp && x.isOriginal));
    const names = (t && t.sprite && t.sprite.sounds || []).map(s => s.name);
    totalSnd += names.length;
    for (const w of want[sp]) if (!names.includes(w)) { sndOK = false; sdet.push(`${sp}!${w}`); }
  }
  check('스프라이트별 효과음 등록 (포탑3·몬스터3·성1·Stage1·커서2·카드1·팔레트2·주문버튼1)', sndOK, sdet.join(' ') || 'all present');
  check('효과음 총 14개 (orphan 0)', totalSnd === 14, `total=${totalSnd}`);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'RUNTIME CHECK: SOME CHECKS FAILED' : 'RUNTIME CHECK COMPLETE — all checks passed, no exceptions.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
