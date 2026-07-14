// Runtime smoke test for 폭탄 스쿼드 (bomb-squad).
// Headless scratch-vm cannot do real mouse-drag / touching / pen render, so we
// verify what IS observable: (1) flag-init sets all tuning knobs, (2) flower
// clones spawn = 꽃개수, (3) bombs spawn and fall, (4) the cannonball physics —
// inject a clamped pull vector into 당김X/당김Y, broadcast 발사, and OBSERVE the
// spawned 포탄 clone's x/y trajectory: velocity should = 당김×발사력배율 and the
// path must arc (rise then fall under 중력). This is the curriculum-critical check.
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

const sb3 = path.join(__dirname, '폭탄_스쿼드.sb3');
const buf = fs.readFileSync(sb3);
const vm = new VM();

function stage() { return vm.runtime.targets.find(t => t.isStage); }
function stageVars() { const st = stage(); const o = {}; for (const id in st.variables) { const v = st.variables[id]; if (v.type !== 'list') o[v.name] = v.value; } return o; }
function setVar(n, val) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === n) st.variables[id].value = val; }
function getVar(n) { return Number(stageVars()[n]); }
function clones(n) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === n && t.isOriginal === false); }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let FAIL = false;
function check(label, ok, extra) { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`); if (!ok) FAIL = true; }

(async () => {
  await vm.loadProject(buf);
  vm.start();
  vm.greenFlag();
  await sleep(600); // flag init (0.2 wait) + 게임시작

  // (1) tuning init (v3+v4: 24 knobs — +포탄수명, +브금볼륨)
  console.log('--- 튜닝 24개 초기값 (v3+v4) ---');
  const expect = {
    발사력배율: 0.22, 최대당김거리: 90, 중력: 0.3, 바람: 0, 낙하속도: 0.7, 스폰간격: 1.6,
    난이도증가율: 0.02, 스폰최대: 8, 흔들폭: 12, 라키투확률: 40, 라키투속도: 3, 꽃개수: 4,
    요격점수: 100, 콤보배율: 2, 콤보최대: 32, 포탄반경: 14, 착탄허용밖: 250, 지면Y: -120,
    미리보기점수: 70, 미리보기간격: 3, 관통횟수: 2, 최대포탄수: 5, 포탄수명: 150, 브금볼륨: 70,
  };
  const v = stageVars(); const bad = [];
  for (const k in expect) if (Number(v[k]) !== Number(expect[k])) bad.push(`${k}=${v[k]}(≠${expect[k]})`);
  check('튜닝 24개 기본값 초기화 (포탄수명=150·브금볼륨=70 포함)', bad.length === 0, bad.join(', ') || 'all OK');
  check('진행: 게임상태=1, 점수=0, 콤보배수=1, 꽃남음=꽃개수(4), 앵커=(0,-60) [v2 앵커Y 올림]',
    v.게임상태 == 1 && v.점수 == 0 && v.콤보배수 == 1 && Number(v.꽃남음) === 4 && Number(v.앵커X) === 0 && Number(v.앵커Y) === -60,
    `상태=${v.게임상태} 점수=${v.점수} 콤보배수=${v.콤보배수} 꽃남음=${v.꽃남음} 앵커Y=${v.앵커Y}`);

  // (2) flower clones = 꽃개수
  console.log('--- 꽃 클론 (라이프) = 꽃개수 ---');
  for (let i = 0; i < 30 && clones('꽃').length < 4; i++) await sleep(50);
  check('꽃 클론 수 = 꽃개수(4)', clones('꽃').length === 4, `clones=${clones('꽃').length}`);
  const fxs = clones('꽃').map(c => Math.round(c.x)).sort((a, b) => a - b);
  check('꽃 균등 배치 (-150,-50,50,150)', JSON.stringify(fxs) === JSON.stringify([-150, -50, 50, 150]), JSON.stringify(fxs));

  // (3) enemies spawn + fall (v2: sprite 폭탄→적, 폭탄수→적수)
  console.log('--- 적 몬스터 스폰 · 낙하 (v2 리스킨) ---');
  setVar('스폰간격', 0.15); // speed up spawning for the test
  for (let i = 0; i < 60 && clones('적').length < 1; i++) await sleep(50);
  check('적 클론 스폰됨 (>=1)', clones('적').length >= 1, `clones=${clones('적').length}, 적수=${getVar('적수')}`);
  // Observe fall on a settled clone: sample the max downward displacement across all live enemies.
  const before = clones('적').map(c => ({ c, y: c.y }));
  await sleep(600);
  const fell = before.some(o => vm.runtime.targets.includes(o.c) && o.c.y < o.y - 1);
  const anyBomb = before.length > 0;
  check('적이 아래로 낙하함 (y 감소)', anyBomb && fell,
    anyBomb ? before.filter(o => vm.runtime.targets.includes(o.c)).map(o => `${o.y.toFixed(0)}→${o.c.y.toFixed(0)}`).join(' ') : 'no enemy');
  // 스폰최대 상한
  await sleep(1500);
  check('적 동시 수 ≤ 스폰최대(8)', getVar('적수') <= 8 && clones('적').length <= 8,
    `적수=${getVar('적수')}, clones=${clones('적').length}`);
  setVar('스폰간격', 1.6);

  // (4) CANNONBALL PHYSICS — inject clamped pull vector, fire, observe arc
  console.log('--- 포탄 물리: 속도=당김×발사력배율 + 중력 적분(포물선) ---');
  // Clear enemies so touching doesn't end the flight early, and stop spawner interference.
  setVar('스폰최대', 0);
  clones('적').forEach(c => vm.runtime.disposeTarget(c));
  setVar('적수', 0);
  // Gentle straight-up pull so the ball peaks ON-screen (below y=190) and we can
  // observe the descent. v0 = 당김Y*발사력배율 must be small enough that apex < 190.
  // anchor y=-60 (v2); want apex ≈ -60 + v0²/(2·중력) < 190 → v0 < ~12. Use 당김Y=50 → v0≈11.
  setVar('포탄수', 0);
  setVar('당김X', 0); setVar('당김Y', 50); setVar('당김크기', 50);
  const yTrace = [];
  const powMul = getVar('발사력배율'), grav = getVar('중력');
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
  // find the 포탄 clone
  let ball = null;
  for (let i = 0; i < 40 && !ball; i++) { ball = clones('포탄')[0]; await sleep(20); }
  check('발사 → 포탄 클론 생성됨', !!ball, ball ? 'yes' : 'none');
  if (ball) {
    const startY = ball.y;
    let peakY = ball.y;
    for (let i = 0; i < 120; i++) {
      yTrace.push(Math.round(ball.y));
      if (ball.y > peakY) peakY = ball.y;
      await sleep(20);
      if (!vm.runtime.targets.includes(ball)) break;
    }
    // arc: reached a peak above start, then came back down below the peak
    const rose = peakY > startY + 20;
    const fellAfter = yTrace[yTrace.length - 1] < peakY - 10;
    check('포탄이 위로 솟았다가(정점) 떨어짐 (포물선 = 중력 적분)', rose && fellAfter,
      `startY=${startY.toFixed(0)} peakY=${peakY.toFixed(0)} endY=${yTrace[yTrace.length-1]}`);
    // initial velocity check: 당김Y=50, 발사력배율=0.22 → v0≈11.0. The steepest early
    // upward step ≈ v0 (gravity only decelerates from there). We take the MAX per-sample
    // rise over the first ~6 samples to be robust against sampler/VM-tick aliasing
    // (two reads can land in the same tick → 0; the fastest step reflects v0).
    let maxStep = 0;
    for (let i = 1; i < Math.min(7, yTrace.length); i++) maxStep = Math.max(maxStep, yTrace[i] - yTrace[i - 1]);
    const v0 = 50 * powMul; // 50*0.22 = 11.0
    check('초기 상승 속도 ≈ 당김Y×발사력배율 (11.0±2)', Math.abs(maxStep - v0) < 3,
      `초기 최대 상승 step=${maxStep}, 예측 v0=${v0.toFixed(1)}`);
  }

  // (5) horizontal pull → 속도X nonzero (velocity decomposition)
  console.log('--- 벡터 분해: 대각선 당김 → 속도X·속도Y 성분 ---');
  clones('포탄').forEach(c => vm.runtime.disposeTarget(c));
  setVar('포탄수', 0);
  // 45-degree pull: 당김X = 당김Y = 90/√2 ≈ 63.64
  const comp = 90 / Math.SQRT2;
  setVar('당김X', comp); setVar('당김Y', comp); setVar('당김크기', 90);
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
  let ball2 = null;
  for (let i = 0; i < 40 && !ball2; i++) { ball2 = clones('포탄')[0]; await sleep(20); }
  if (ball2) {
    const x0 = ball2.x;
    await sleep(150);
    const movedX = ball2.x - x0;
    check('대각선 당김 → 포탄이 옆(+x)으로도 이동 (속도X 성분 존재)', movedX > 5,
      `Δx=${movedX.toFixed(1)} (예측 속도X≈${(comp * powMul).toFixed(1)}/tick)`);
  } else check('대각선 발사 포탄 존재', false, 'none');

  // (6) RAPID FIRE (v2): 여러 발이 동시에 공중에 존재, 최대포탄수 상한
  console.log('--- 연사 (v2): 포탄 클론 다발 + 최대포탄수 상한 ---');
  clones('포탄').forEach(c => vm.runtime.disposeTarget(c));
  setVar('포탄수', 0);
  setVar('게임상태', 1);
  setVar('당김X', 0); setVar('당김Y', 50); setVar('당김크기', 50); // gentle up so they stay airborne
  // 발사 방송을 빠르게 여러 번 → 이전 발이 공중에 있어도 계속 생성돼야 함
  for (let i = 0; i < 8; i++) {
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
    await sleep(40);
  }
  await sleep(60);
  const airborne = clones('포탄').length;
  check('연사: 여러 포탄 클론이 동시에 공중에 존재 (>=2, 비행중 잠금 없음)', airborne >= 2,
    `동시 포탄=${airborne}, 포탄수=${getVar('포탄수')}`);
  // 최대포탄수(5) 상한: 계속 쏴도 5를 안 넘어야 함
  let maxBalls = airborne;
  for (let i = 0; i < 20; i++) {
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
    await sleep(25);
    if (clones('포탄').length > maxBalls) maxBalls = clones('포탄').length;
  }
  check('연사: 동시 포탄 수 ≤ 최대포탄수(5) [클론 폭주 방지]', maxBalls <= 5,
    `관측 최대 동시 포탄=${maxBalls} (cap=5)`);
  clones('포탄').forEach(c => vm.runtime.disposeTarget(c));
  setVar('포탄수', 0);

  // (7) PIERCE (v2): 한 포탄 클론이 남은관통을 소진하며 여러 적을 통과
  //   headless 는 touching 이 렌더러 없이 false 라 실제 적 관통은 못 보지만, 관통 로직이
  //   코드에 실재하고 초기 남은관통=관통횟수(2)로 세팅되는지 + 관통 소진 시 소멸 조건을
  //   클론-로컬 값으로 확인한다.
  console.log('--- 관통샷 (v2): 남은관통=관통횟수 세팅 + 소진 소멸 조건 ---');
  setVar('관통횟수', 3); // 바꾼 값이 클론에 반영되는지도 겸사
  setVar('게임상태', 1);
  setVar('당김X', 0); setVar('당김Y', 50); setVar('당김크기', 50);
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
  let pball = null;
  for (let i = 0; i < 40 && !pball; i++) { pball = clones('포탄')[0]; await sleep(20); }
  function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return c.variables[id].value; }
  const pierceLeft = pball ? Number(cloneLocal(pball, '남은관통')) : NaN;
  check('관통샷: 새 포탄 클론의 남은관통 = 관통횟수(3) [튜닝 반영]', pierceLeft === 3,
    `남은관통=${pierceLeft}`);
  // 소진 소멸: 남은관통을 0으로 만들면(적에 3번 맞은 셈) 포탄이 소멸해야 함 (exit cond 남은관통<1)
  if (pball && vm.runtime.targets.includes(pball)) {
    for (const id in pball.variables) if (pball.variables[id].name === '남은관통') pball.variables[id].value = 0;
    let gone = false;
    for (let i = 0; i < 30; i++) { await sleep(30); if (!vm.runtime.targets.includes(pball)) { gone = true; break; } }
    check('관통샷: 남은관통 소진(0) → 포탄 소멸 [관통 상한 동작]', gone, gone ? 'deleted' : 'still alive');
  } else check('관통 대상 포탄 존재', false, 'none');
  setVar('관통횟수', 2); // 복구
  clones('포탄').forEach(c => vm.runtime.disposeTarget(c));
  setVar('포탄수', 0);

  // (8) LOCK-BUG REGRESSION (v3): 연사 다발 후 포탄수 카운터가 도로 회복 → 계속 발사 가능
  //   과거 버그: 화면 밖/미삭제 포탄이 포탄수를 안 줄여 포탄수≥최대포탄수 에 영원히 막힘.
  //   이제 단일 출구(수명만료 포함)로 포탄수 항상 감소. 포탄이 다 소멸하면 포탄수→0 복귀해야 함.
  console.log('--- 잠김버그 회귀 (v3): 연사 다발 → 카운터 회복 → 계속 발사 ---');
  setVar('게임상태', 1);
  setVar('포탄수명', 15); // 수명 짧게(≈0.3초) → 곧 만료돼 카운터가 도로 줄어드는지 관측
  // 세게 위로 쏴 여러 발을 공중에 채운다
  setVar('당김X', 0); setVar('당김Y', 90); setVar('당김크기', 90);
  for (let i = 0; i < 15; i++) {
    vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
    await sleep(20);
  }
  const peakCount = getVar('포탄수');
  check('연사 다발 → 포탄수 늘어남(>=2, 최대포탄수 이내)', peakCount >= 2 && peakCount <= 5,
    `peak 포탄수=${peakCount}`);
  // 수명 만료로 포탄들이 소멸하면서 포탄수가 도로 감소해 0 근처로 회복해야 함
  let recovered = false;
  for (let i = 0; i < 60; i++) { await sleep(50); if (getVar('포탄수') === 0 && clones('포탄').length === 0) { recovered = true; break; } }
  check('★수명 만료 후 포탄수→0 회복 (카운터 누수 없음 = 잠김버그 근본해결)', recovered,
    `포탄수=${getVar('포탄수')}, 잔여 클론=${clones('포탄').length}`);
  // 회복 후 다시 발사되는지 (계속 쏠 수 있음)
  setVar('포탄수명', 150);
  setVar('당김X', 0); setVar('당김Y', 50); setVar('당김크기', 50);
  const beforeFire = clones('포탄').length;
  vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' });
  let refired = false;
  for (let i = 0; i < 30 && !refired; i++) { await sleep(20); if (clones('포탄').length > beforeFire) refired = true; }
  check('회복 후 재발사 성공 (더 이상 잠기지 않음)', refired, `발사 후 포탄 클론=${clones('포탄').length}`);
  clones('포탄').forEach(c => vm.runtime.disposeTarget(c));
  setVar('포탄수', 0);

  // (9) BGM (v4): bgm 사운드 등록 + Stage 별도 병렬 깃발 스크립트 존재 (정적)
  console.log('--- BGM (v4): 사운드 등록 + 병렬 재생 스크립트 ---');
  const st = stage();
  const hasBgm = (st.sprite.sounds || st.getSounds()).some(s => s.name === 'bgm');
  check('Stage 에 bgm 사운드 등록됨', hasBgm, hasBgm ? 'bgm registered' : 'missing');
  // 별도 flag hat 에 sound_playuntildone(bgm) 존재 확인
  const blks = st.blocks._blocks;
  let bgmLoop = false;
  for (const b of Object.values(blks)) {
    if (b.opcode === 'sound_playuntildone') {
      const inp = b.inputs.SOUND_MENU;
      if (inp && inp.block) { const sh = blks[inp.block]; if (sh && sh.fields.SOUND_MENU && sh.fields.SOUND_MENU.value === 'bgm') bgmLoop = true; }
    }
  }
  check('BGM 재생(play bgm until done) 블록 존재 [무한 루프 재생]', bgmLoop, bgmLoop ? 'playuntildone bgm found' : 'missing');

  console.log('\n' + (FAIL ? 'RESULT: FAIL' : 'RESULT: ALL PASS'));
  process.exit(FAIL ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
