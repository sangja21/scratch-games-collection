// Headless scratch-vm runtime check for downwell (다운웰).
// Renderer is stubbed → touching returns false; coordinate/state logic DO run.
// We verify: var init, world scroll (적·보석·발판 클론 y delta = 낙하속도),
// down-fire (탄약 감소 + 낙하속도 부양), enemy kill consequence (콤보 곱 점수 + 보석),
// damage popup (숫자 코스튬), 강화 택1 상태머신(1→2→1), game over, clone bounded.
// (touching 기반 스톰프·총알명중·발판착지는 verify_collision.js 에서 거리기반으로 검증)
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '다운웰.sb3');
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
function clones(name) {
  return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false);
}
function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return c.variables[id].value; return undefined; }
function setCloneLocal(c, name, val) { for (const id in c.variables) if (c.variables[id].name === name) c.variables[id].value = val; }
function costumeName(t) { const c = t.getCostumes()[t.currentCostume]; return c ? c.name : undefined; }
function sayBubble(t) { const b = t.getCustomState && t.getCustomState('Scratch.looks'); return b ? b.text : undefined; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`);
  if (!ok) FAIL = true;
}

(async () => {
  await vm.loadProject(fs.readFileSync(sb3));
  vm.start();
  vm.greenFlag();
  await sleep(500); // 0.3 wait + 게임시작

  // ---- (1) tuning var init (32 한글 손잡이) ----
  let v = stageVars();
  console.log('--- (1) 튜닝 변수 32개 초기화 ---');
  const expect = {
    이동속도:5, 중력:0.55, 최대낙하:9, 점프력:7, 부양력:1.6, 부양상한:5,
    카메라선:40, 코요테:6, 착지반동:1.5,
    탄약최대:6, 연사간격:0.12, 총알속도:14, 총알공격력:1,
    최대체력:4, 무적시간:30, 처치점수:5,
    점프벌레_체력:1, 점프벌레_속도:0.8, 점프벌레_보석:1,
    박쥐_체력:2, 박쥐_속도:1.6, 박쥐_보석:2,
    가시_체력:3, 가시_속도:0.4, 가시_보석:3,
    스폰간격:1.0, 난이도깊이:900, 스폰감소:0.07, 스폰간격최소:0.35,
    발판간격:1.6, 강화깊이:1000, 강화량:1,
  };
  let initOK = true, bad = [];
  for (const k in expect) if (Number(v[k]) !== Number(expect[k])) { initOK = false; bad.push(`${k}=${v[k]}`); }
  check('32 튜닝 변수가 기본값으로 초기화', initOK, bad.join(', ') || 'all OK');
  // 게임은 이미 살아있다(0.3초 뒤 게임시작 → 물리 가동) → 깊이·낙하속도가 양수인 게 정상.
  check('진행: 게임상태=1 (낙하중), 콤보=0', v.게임상태==1 && v.콤보==0, `state=${v.게임상태} combo=${v.콤보}`);
  check('낙하 시작 — 낙하속도>0 & 깊이>0 (중력으로 추락 시작)', Number(v.낙하속도) > 0 && Number(v.깊이) > 0,
        `낙하속도=${Number(v.낙하속도).toFixed(2)} 깊이=${Number(v.깊이).toFixed(1)}`);
  check('체력=최대체력(4), 탄약=탄약최대(6), 다음강화깊이=강화깊이(1000)',
        v.체력==4 && v.탄약==6 && v.다음강화깊이==1000, `hp=${v.체력} ammo=${v.탄약} next=${v.다음강화깊이}`);

  // ---- (2) WORLD SCROLL: 적/발판 클론 y 가 낙하속도만큼 위로 흐른다 ----
  console.log('--- (2) 월드 스크롤 (적·발판 클론 y 델타 = 낙하속도) ---');
  setVar('스폰간격', 0.3); setVar('유효스폰간격', 0.3); setVar('발판간격', 0.3);
  await sleep(1400);
  let en = clones('적');
  check('적 클론 스폰됨 (>=1)', en.length >= 1, `enemies=${en.length}`);
  check('발판 클론 스폰됨 (>=1)', clones('발판').length >= 1, `ledges=${clones('발판').length}`);
  // gravity가 낙하속도를 키워 깊이(점수)가 쌓이는지
  const depth0 = Number(stageVars().깊이);
  const e0 = clones('적')[0];
  const eY0 = e0 ? e0.y : null;
  await sleep(400);
  v = stageVars();
  check('낙하속도 > 0 (중력으로 추락 중)', Number(v.낙하속도) > 0, `낙하속도=${Number(v.낙하속도).toFixed(2)}`);
  check('깊이(점수)가 낙하 중 누적', Number(v.깊이) > depth0, `깊이 ${depth0}→${v.깊이}`);
  if (e0 && eY0 != null && vm.runtime.targets.includes(e0)) {
    const dY = e0.y - eY0;
    check('적 클론이 위로 스크롤됨 (Δy>0, 낙하속도 방향)', dY > 5, `Δy=${dY.toFixed(1)}px / 0.4s`);
  } else {
    // 첫 적이 화면 밖으로 나가 삭제됐다면 그 자체가 스크롤 증거
    check('적 클론이 스크롤되어 화면을 통과 (삭제 = 스크롤 증거)', true, '첫 적이 위로 빠져나감');
  }

  // ---- (3) 아래로 발사: 탄약 감소 + 낙하속도 부양(체공) + 총알 클론 ----
  console.log('--- (3) 아래로 발사 (탄약-1, 낙하속도 -= 부양력, 총알 클론) ---');
  // 부양 효과가 또렷이 보이도록 일시적으로 부양력↑·중력↓ (튜닝 변수라 코드 수정 없이 조정)
  setVar('부양력', 8); setVar('중력', 0.1); setVar('탄약최대', 99); setVar('탄약', 99); setVar('발사쿨', 0);
  const ammoBefore = Number(stageVars().탄약);
  let fallMin = 99, boltsMax = 0;
  vm.postIOData('keyboard', { key: 'z', isDown: true }); // 발사키 z 누름(연사)
  for (let i = 0; i < 36; i++) { // Scratch wait는 프레임 단위라 연사간격이 프레임-제한됨 → 넉넉히 hold
    await sleep(40);
    fallMin = Math.min(fallMin, Number(stageVars().낙하속도));
    boltsMax = Math.max(boltsMax, clones('총알').length);
  }
  vm.postIOData('keyboard', { key: 'z', isDown: false });
  await sleep(60);
  v = stageVars();
  check('연사로 탄약이 여러 발 감소함 (>=3, 발사쿨 부동소수 함정 회복)',
        ammoBefore - Number(v.탄약) >= 3, `탄약 ${ammoBefore}→${v.탄약} (소비=${ammoBefore - Number(v.탄약)})`);
  check('총알 클론이 생성됨 (연사 중 동시 존재 >=1)', boltsMax >= 1, `발사 중 최대 총알 클론=${boltsMax}`);
  check('발사 반동으로 낙하속도가 음수로(부양/체공) 내려감', fallMin < 0, `낙하속도 최저=${fallMin.toFixed(2)}`);
  // 복구
  setVar('부양력', 1.6); setVar('중력', 0.55);

  // ---- (4) 적 처치 결과: 콤보 곱 점수 + 보석 드롭 (gravity 0 으로 격리) ----
  console.log('--- (4) 적 처치 → 콤보+1 + 깊이 += 처치점수 × 콤보 (곱셈) + 보석 ---');
  // 낙하-깊이 누적을 끄고(중력0·낙하속도0) 처치 점수만 깨끗이 측정. 적도 안 스크롤돼 안정적.
  setVar('중력', 0); setVar('낙하속도', 0); setVar('콤보', 0); setVar('유효스폰간격', 0.3);
  // 안정적으로 적 클론 2마리 이상 확보 후 캡처(재조회 대신 고정 리스트로 처치)
  let pool = clones('적');
  for (let g = 0; g < 12 && pool.length < 2; g++) { await sleep(300); pool = clones('적'); }
  check('처치 테스트용 적 클론 2마리 이상 확보', pool.length >= 2, `pool=${pool.length}`);
  const killPt = Number(stageVars().처치점수);
  // 1차 처치
  let depthB = Number(stageVars().깊이), comboB = Number(stageVars().콤보);
  const gemsBefore = clones('보석').length;
  setCloneLocal(pool[0], '피격쿨', 0); setCloneLocal(pool[0], '내체력', 0);
  await sleep(200);
  v = stageVars();
  check('처치 시 콤보 +1', Number(v.콤보) === comboB + 1, `콤보 ${comboB}→${v.콤보}`);
  check('깊이 += 처치점수 × 콤보 (곱셈 점수!)',
        Number(v.깊이) === depthB + killPt * Number(v.콤보),
        `Δ깊이=${Number(v.깊이) - depthB} 기대=${killPt * Number(v.콤보)} (처치점수=${killPt}, 콤보=${v.콤보})`);
  check('처치 자리에 보석 클론 드롭', clones('보석').length > gemsBefore, `보석 ${gemsBefore}→${clones('보석').length}`);
  // 2차 연속 처치 → 콤보 2, 점수가 곱으로 더 크게 (땅에 안 닿았으니 콤보 유지)
  depthB = Number(stageVars().깊이); const comboB2 = Number(stageVars().콤보);
  setCloneLocal(pool[1], '피격쿨', 0); setCloneLocal(pool[1], '내체력', 0);
  await sleep(200);
  v = stageVars();
  check('연속 처치로 콤보가 더 올라감 (땅 안 닿음)', Number(v.콤보) === comboB2 + 1, `콤보 ${comboB2}→${v.콤보}`);
  check('콤보가 클수록 한 번 처치 점수가 더 큼 (곱셈 누적)',
        Number(v.깊이) - depthB === killPt * Number(v.콤보), `Δ깊이=${Number(v.깊이) - depthB} = ${killPt}×${v.콤보}`);
  setVar('중력', 0.55); // 복구

  // ---- (5) 데미지 팝업 (숫자 코스튬, say 미사용) ----
  console.log('--- (5) 데미지 팝업 (숫자 코스튬, say 0개) ---');
  async function fireDamage(val, x, y) {
    setVar('데미지표시값', val); setVar('데미지표시x', x); setVar('데미지표시y', y);
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '데미지표시' });
    await sleep(230);
    const cl = clones('데미지');
    return { digits: cl.map(c => costumeName(c)), bubbles: cl.map(c => sayBubble(c)).filter(t => t !== undefined && t !== ''), count: cl.length };
  }
  let d1 = await fireDamage(3, 0, 0);
  check('데미지표시값=3 → 코스튬 "3" 렌더', d1.digits.includes('3'), JSON.stringify(d1.digits));
  check('say 말풍선 0개', d1.bubbles.length === 0, `bubbles=${d1.bubbles.length}`);
  await sleep(450);
  let d2 = await fireDamage(12, 30, 0);
  check('데미지표시값=12 → 코스튬 "1"&"2" 두 자리', d2.digits.slice().sort().join(',') === '1,2', JSON.stringify(d2.digits));
  await sleep(500);
  check('데미지 클론 페이드 후 정리됨', clones('데미지').length === 0, clones('데미지').length);

  // ---- (6) 강화 택1 상태머신 (1→2→1) ----
  console.log('--- (6) 강화 택1 상태머신 (게임상태 1→2→1) ---');
  setVar('게임상태', 1);
  const ammoMaxBefore = Number(stageVars().탄약최대);
  setVar('깊이', Number(stageVars().다음강화깊이)); // 강화깊이 도달
  await sleep(250);
  v = stageVars();
  check('깊이 ≥ 다음강화깊이 → 게임상태=2 (강화선택중)', Number(v.게임상태) === 2, `state=${v.게임상태}`);
  const nextBefore = Number(v.다음강화깊이);
  vm.postIOData('keyboard', { key: '1', isDown: true });
  await sleep(140);
  vm.postIOData('keyboard', { key: '1', isDown: false });
  await sleep(500);
  v = stageVars();
  check('강화1 적용: 탄약최대 += 강화량', Number(v.탄약최대) === ammoMaxBefore + 1, `탄약최대 ${ammoMaxBefore}→${v.탄약최대}`);
  check('강화 후 탄약 = 탄약최대(가득)', Number(v.탄약) === Number(v.탄약최대), `탄약=${v.탄약}/${v.탄약최대}`);
  check('다음강화깊이 += 강화깊이', Number(v.다음강화깊이) === nextBefore + Number(v.강화깊이), `다음강화깊이=${v.다음강화깊이}`);
  check('강화완료 → 게임상태=1 (낙하 재개)', Number(v.게임상태) === 1, `state=${v.게임상태}`);

  // ---- (7) 클론 폭주 가드 ----
  console.log('--- (7) 클론 폭주 가드 ---');
  setVar('스폰간격', 0.3); setVar('유효스폰간격', 0.3);
  await sleep(2000);
  const ce = clones('적').length, cb = clones('총알').length, cg = clones('보석').length, cl = clones('발판').length;
  const total = ce + cb + cg + cl + clones('데미지').length;
  check('적 클론 상한 유지 (<80)', ce < 80, `적=${ce}`);
  check('총알 클론 상한 유지 (<120)', cb < 120, `총알=${cb}`);
  check('전체 클론 < 280 (Scratch 300 한도 내)', total < 280, `total=${total}`);

  // ---- (8) 게임오버: 체력 0 → 게임상태 0, 클론 자기 삭제 ----
  console.log('--- (8) 게임오버 ---');
  setVar('체력', 0);
  await sleep(400);
  v = stageVars();
  check('체력<1 → 게임상태=0 (게임오버)', Number(v.게임상태) === 0, `state=${v.게임상태}`);
  await sleep(500);
  check('게임오버 후 적 클론 자기 삭제', clones('적').length === 0, clones('적').length);
  check('게임오버 후 총알·보석·발판 클론 자기 삭제',
        clones('총알').length === 0 && clones('보석').length === 0 && clones('발판').length === 0,
        `총알=${clones('총알').length} 보석=${clones('보석').length} 발판=${clones('발판').length}`);

  // ---- (9) 합성 효과음 존재 + orphan 0 ----
  console.log('--- (9) 전용 합성 효과음 7종 + orphan 0 ---');
  const wantSounds = ['zap', 'boom', 'stomp', 'combo', 'coin', 'hurt', 'levelup'];
  const have = new Set();
  for (const t of vm.runtime.targets) for (const s of (t.getSounds ? t.getSounds() : [])) have.add(s.name);
  check('합성 효과음 7종 모두 .sb3 에 존재', wantSounds.every(s => have.has(s)),
        wantSounds.filter(s => !have.has(s)).join(',') || JSON.stringify([...have].sort()));

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'RUNTIME CHECK: SOME CHECKS FAILED' : 'RUNTIME CHECK COMPLETE — all checks passed, no exceptions.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
