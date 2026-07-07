// Headless scratch-vm 행동 시나리오 검증 — 탕탕 헌터 (데모).
// 렌더러 없음 → `touching [sprite]` 는 항상 false 라, RenderedTarget.isTouchingSprite 를
// 거리(반지름 합) 기반으로 몽키패치(reference-headless-scratchvm-verification 기법).
// 그래야 총알-적 명중 / 적-플레이어 접촉 데미지 로직이 실제로 '실행'된다.
//
// plan 의 행동 시나리오 5개:
//  1) 마우스다운 → 총알 클론 스폰(발사쿨 간격) + 마우스 방향으로 실제 좌표 이동
//  2) 총알-적 명중 → 적체력 감소, 2발째 처치(경험치 증가)
//  3) 적 접촉 → 0.5초 내 내체력 감소 + 무적 성립
//  4) 경험치 만충 → 강화카드 표시, 클릭 존별로 해당 스탯 실제 변화(디바운스)
//  5) 자동 플레이(이동+발사)로 30초 생존 (속도 5 > 적속도 2.5 카이팅)
const fs = require('fs');
const path = require('path');
const VM = require('scratch-vm');

// --- 거리 기반 touching 오버라이드(근사 Scratch 충돌) ---
function radiusOf(t) {
  const sz = (typeof t.size === 'number' ? t.size : 100) / 100;
  return Math.max(8, 24 * sz);
}
function installGeometricTouching(vm) {
  const proto = Object.getPrototypeOf(vm.runtime.targets[0]);
  proto.isTouchingSprite = function (spriteName) {
    const first = this.runtime.getSpriteTargetByName(String(spriteName));
    if (!first) return false;
    const r1 = radiusOf(this);
    for (const other of [first, ...first.sprite.clones]) {
      if (other === this || !other.visible) continue;
      const dx = this.x - other.x, dy = this.y - other.y;
      if (Math.hypot(dx, dy) <= r1 + radiusOf(other)) return true;
    }
    return false;
  };
}

const sb3 = path.join(__dirname, '탕탕_헌터.sb3');
const vm = new VM();
function stage() { return vm.runtime.targets.find(t => t.isStage); }
function gv(name) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) return Number(st.variables[id].value); }
function setVar(name, val) { const st = stage(); for (const id in st.variables) if (st.variables[id].name === name) st.variables[id].value = val; }
function orig(name) { return vm.runtime.targets.find(t => t.sprite && t.sprite.name === name && t.isOriginal); }
function clones(name) { return vm.runtime.targets.filter(t => t.sprite && t.sprite.name === name && t.isOriginal === false); }
function cloneLocal(c, name) { for (const id in c.variables) if (c.variables[id].name === name) return Number(c.variables[id].value); return undefined; }
function setCloneLocal(c, name, val) { for (const id in c.variables) if (c.variables[id].name === name) c.variables[id].value = val; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
const key = (k, down) => vm.runtime.ioDevices.keyboard.postData({ key: k, isDown: !!down });
function mouse(sx, sy, down) {
  // scratchX = clientX-240, scratchY = 180-clientY  (canvas 480x360)
  const data = { x: sx + 240, y: 180 - sy, canvasWidth: 480, canvasHeight: 360 };
  if (down !== undefined) data.isDown = !!down;
  vm.runtime.ioDevices.mouse.postData(data);
}
function fireBroadcast() { vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '발사' }); }
function spawnEnemy() { vm.runtime.startHats('event_whenbroadcastreceived', { BROADCAST_OPTION: '적스폰' }); }

let FAIL = false;
function check(label, ok, extra) { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${extra !== undefined ? '  → ' + extra : ''}`); if (!ok) FAIL = true; }

(async () => {
  const buf = fs.readFileSync(sb3);
  await vm.loadProject(buf);
  installGeometricTouching(vm);
  vm.start();
  vm.greenFlag();
  await sleep(700); // 0.4 wait + 게임시작

  // ---------- (0) 초기화 ----------
  console.log('--- (0) 초기화 (튜닝 12 손잡이) ---');
  const expect = { 이동속도:5, 발사쿨:0.15, 총알속도:12, 공격력:1, 잡졸체력:2, 적속도:2.5,
    스폰간격:0.8, 최대체력:5, 무적시간:0.5, 레벨업경험치:8, 적성장배율:1.2, 경험치획득:1 };
  let bad = [];
  for (const k in expect) if (gv(k) !== expect[k]) bad.push(`${k}=${gv(k)}`);
  check('튜닝 12개 기본값 초기화', bad.length === 0, bad.join(', ') || 'all OK');
  check('진행: 게임상태1·점수0·레벨1·경험치0·내체력5', gv('게임상태')==1 && gv('점수')==0 && gv('레벨')==1 && gv('경험치')==0 && gv('내체력')==5,
        `state=${gv('게임상태')} hp=${gv('내체력')}`);
  check('플레이어 visible, 초기 x≈0', orig('플레이어').visible && Math.abs(orig('플레이어').x) < 5);

  // ---------- (1) 마우스다운 → 총알 스폰 + 마우스 방향 이동 ----------
  console.log('--- (1) 마우스다운 → 총알 연사 + 마우스 방향 비행 ---');
  setVar('스폰간격', 999);            // 스폰 정지(노이즈 제거)
  await sleep(300);
  for (const c of clones('적')) setCloneLocal(c, '적체력', 0); // 기존 적 정리 유도
  // 플레이어 중앙, 마우스는 오른쪽(scratchX=+200 → direction 90)
  orig('플레이어').setXY(0, 0);
  mouse(200, 0, true);
  await sleep(250);
  check('플레이어가 마우스(오른쪽) 방향 조준 (direction≈90)', Math.abs(orig('플레이어').direction - 90) < 8, `dir=${orig('플레이어').direction.toFixed(1)}`);
  const bulletsMid = clones('총알').length;
  check('마우스다운 유지 → 총알 클론 연사됨 (>=1)', bulletsMid >= 1, `총알클론=${bulletsMid}`);
  // 한 발 골라 위치 추적: 오른쪽(+x)로 실제 이동?
  const b0 = clones('총알')[0];
  const bStart = b0 ? { x: b0.x, y: b0.y } : null;
  await sleep(160);
  if (b0 && bStart) {
    const gone = !vm.runtime.targets.includes(b0);
    const dx = gone ? 999 : b0.x - bStart.x;
    check('총알이 마우스 방향(+x)으로 실제 이동/소멸', gone || dx > 4, gone ? '비행 후 소멸' : `Δx=${dx.toFixed(1)}px`);
  } else check('총알 이동 측정 대상 존재', false);
  // 연사 간격: 0.15초 → ~1초에 5~7발. 마우스 유지 1초간 스폰수 관찰.
  const before = clones('총알').length;
  await sleep(1000);
  const rate = clones('총알').length; // 순간 존재 수(비행중 소멸 감안)
  check('연사 지속으로 총알이 계속 생성됨(화면에 다수 존재)', rate >= 2, `동시존재≈${rate}발`);
  mouse(200, 0, false);
  await sleep(300);

  // ---------- (2) 총알-적 명중 → 적체력 감소, 2발째 처치 + 경험치 ----------
  console.log('--- (2) 총알 명중 → 적체력 2→1→처치 (경험치 증가) ---');
  setVar('무적', 999);   // 플레이어-접촉 피해 경로 차단(총알 피해만 격리)
  setVar('총알속도', 1); // 총알이 표적에 잠깐 머물러 명중 확실히(피격쿨이 중복피해 방지)
  setVar('게임상태', 1);
  spawnEnemy(); await sleep(80);
  const tgt = clones('적').slice(-1)[0];
  check('표적 적 클론 확보', !!tgt);
  tgt.setXY(0, 0); setCloneLocal(tgt, '이속', 0); setCloneLocal(tgt, '적체력', 2); setCloneLocal(tgt, '피격쿨', 0);
  orig('플레이어').setXY(0, 0); mouse(200, 0);
  const expBefore = gv('경험치');
  let hpReadings = [cloneLocal(tgt, '적체력')], hits = 0, killed = false;
  for (let shot = 0; shot < 6 && !killed; shot++) {
    if (!vm.runtime.targets.includes(tgt)) { killed = true; break; }
    tgt.setXY(0, 0); setCloneLocal(tgt, '이속', 0); setCloneLocal(tgt, '피격쿨', 0);
    const hpPrev = cloneLocal(tgt, '적체력');
    fireBroadcast();
    // 명중을 짧은 간격으로 폴링(표적 고정 유지) → 프레임 지터에도 확실히 감지
    for (let t = 0; t < 20; t++) {
      await sleep(20);
      if (vm.runtime.targets.includes(tgt)) tgt.setXY(0, 0);
      if (!vm.runtime.targets.includes(tgt) || cloneLocal(tgt, '적체력') < hpPrev) break;
    }
    if (!vm.runtime.targets.includes(tgt) || cloneLocal(tgt, '적체력') < 1) { killed = true; hits++; hpReadings.push(0); break; }
    const hpNow = cloneLocal(tgt, '적체력');
    if (hpNow < hpPrev) { hits++; hpReadings.push(hpNow); }
    await sleep(200);           // 피격쿨(4틱) 소진 대기(다음 발이 새 명중이 되게)
  }
  await sleep(400);  // 처치 후 보상 블록(점수·경험치 증가 + 팝 연출)이 마무리될 시간
  console.log(`     적체력 추이: ${hpReadings.join(' → ')}  (명중 ${hits}회)`);
  check('총알 명중 시 적체력 실제 감소', hpReadings[1] !== undefined && hpReadings[1] < 2, `첫 명중 후 적체력=${hpReadings[1]}`);
  check('2발(공격력1×2=잡졸체력2)로 처치', killed && hits <= 2, `명중=${hits} killed=${killed}`);
  check('처치 시 경험치 += 경험치획득', gv('경험치') >= expBefore + 1, `경험치 ${expBefore}→${gv('경험치')}`);
  setVar('총알속도', 12);

  // ---------- (3) 적 접촉 → 0.5초 내 내체력 감소 + 무적 성립 ----------
  console.log('--- (3) 적 접촉 → 0.5초 내 내체력 감소 + 무적 발동 ---');
  setVar('무적', 999); setVar('내체력', 5); setVar('게임상태', 1);  // 배치 동안 피해 차단
  spawnEnemy(); await sleep(120);
  const foe = clones('적').slice(-1)[0];
  foe.setXY(0, 0); setCloneLocal(foe, '이속', 0); setCloneLocal(foe, '적체력', 99); setCloneLocal(foe, '피격쿨', 99);
  orig('플레이어').setXY(0, 0);
  await sleep(60);
  const hpBefore = gv('내체력');            // 아직 무적이라 5 그대로
  setVar('무적', 0);                        // 지금부터 접촉 피해 허용 → 0.5초 내 감소해야
  let dmgHp = hpBefore, invSet = false;
  for (let i = 0; i < 25; i++) {           // 최대 0.5s 관찰
    foe.setXY(0, 0);
    await sleep(20);
    if (gv('내체력') < hpBefore) { dmgHp = gv('내체력'); invSet = gv('무적') > 0; break; }
  }
  check('적 접촉 0.5초 내 내체력 감소', dmgHp < hpBefore, `내체력 ${hpBefore}→${dmgHp}`);
  check('피격 시 무적 발동 (>0, 무적시간 0.5)', invSet && gv('무적') > 0, `무적=${gv('무적').toFixed(3)}`);
  setCloneLocal(foe, '적체력', 0); // 표적 정리
  await sleep(200);

  // ---------- (4) 레벨업 → 강화카드 클릭 존별 스탯 변화 (디바운스) ----------
  console.log('--- (4) 레벨업 → 강화카드 클릭 폴링/디바운스 ---');
  setVar('무적', 999); setVar('게임상태', 1); setVar('스폰간격', 999);
  async function levelUpAndClick(sx, label) {
    mouse(sx, 0, false); await sleep(60);   // 손 뗀 상태 보장(디바운스 진입)
    const lvBefore = gv('레벨');
    setVar('경험치', gv('레벨업경험치'));   // 정확히 1회 레벨업
    await sleep(260);
    const shown = orig('강화카드').visible, st2 = gv('게임상태'), lvUp = gv('레벨') === lvBefore + 1;
    mouse(sx, 0, true); await sleep(140);    // 존 클릭
    mouse(sx, 0, false); await sleep(260);   // 뗌 → 디바운스 통과, 선택 확정
    return { shown, st2, lvUp, back: gv('게임상태'), hidden: !orig('강화카드').visible };
  }
  // 존1 공격력 (마우스x=-120 < -70)
  let atkB = gv('공격력');
  let r1 = await levelUpAndClick(-120, '공격력');
  check('레벨업 → 게임상태=2 & 카드 표시 & 레벨+1', r1.shown && r1.st2 === 2 && r1.lvUp, `visible=${r1.shown} state=${r1.st2} lv+1=${r1.lvUp}`);
  check('존1 클릭 → 공격력 +1 & 전투 재개(게임상태1) & 카드 숨김', gv('공격력') === atkB + 1 && r1.back === 1 && r1.hidden,
        `공격력 ${atkB}→${gv('공격력')} state=${r1.back}`);
  // 존3 이동속도 (마우스x=+120 > 70)
  let mvB = gv('이동속도');
  let r3 = await levelUpAndClick(120, '이동속도');
  check('존3 클릭 → 이동속도 +1', gv('이동속도') === mvB + 1 && r3.back === 1, `이동속도 ${mvB}→${gv('이동속도')}`);
  // 존2 연사속도 (마우스x=0, 가운데 → 발사쿨 감소=더 빠른 연사)
  let gapB = gv('발사쿨');
  let r2 = await levelUpAndClick(0, '연사속도');
  check('존2 클릭 → 발사쿨 감소(연사 빨라짐)', gv('발사쿨') < gapB && r2.back === 1, `발사쿨 ${gapB.toFixed(3)}→${gv('발사쿨').toFixed(3)}`);

  // ---------- (5) 자동 플레이 30초 생존 (카이팅) ----------
  console.log('--- (5) 자동 플레이 30초 생존 (속도5 > 적속도2.5 카이팅) ---');
  vm.greenFlag();                 // 깨끗한 리셋 (클론 정리 + 변수 초기화)
  await sleep(700);
  setVar('게임상태', 1);
  mouse(120, 0, true);            // 계속 발사
  let dirIdx = 0;
  const legs = [['right arrow'], ['up arrow'], ['left arrow'], ['down arrow']];
  let cur = [];
  const press = arr => { for (const k of cur) if (!arr.includes(k)) key(k, false); for (const k of arr) key(k, true); cur = arr; };
  const T0 = Date.now(); let minHp = 5, killsSeen = 0;
  while (Date.now() - T0 < 30000) {
    const p = orig('플레이어');
    // 사각 순회(벽 근처에서 방향 전환) — 속도5로 계속 이동해 적(2.5)을 따돌린다
    if (dirIdx === 0 && p.x > 190) dirIdx = 1;
    else if (dirIdx === 1 && p.y > 140) dirIdx = 2;
    else if (dirIdx === 2 && p.x < -190) dirIdx = 3;
    else if (dirIdx === 3 && p.y < -140) dirIdx = 0;
    press(legs[dirIdx]);
    // 조준을 진행 방향으로 스윕(앞의 적을 정리)
    const aim = [[200,0],[0,150],[-200,0],[0,-150]][dirIdx];
    mouse(aim[0], aim[1], true);
    await sleep(120);
    minHp = Math.min(minHp, gv('내체력'));
    killsSeen = gv('점수');
    if (gv('게임상태') === 0) break;
  }
  press([]); mouse(120, 0, false);
  const survived = gv('게임상태') !== 0 && gv('내체력') >= 1;
  check('30초 자동 플레이 생존 (게임상태≠0, 내체력≥1)', survived, `내체력=${gv('내체력')} 최소내체력=${minHp} 점수=${killsSeen} state=${gv('게임상태')}`);
  check('자동 플레이 중 적 처치 발생 (점수>0)', gv('점수') > 0, `점수=${gv('점수')}`);

  vm.quit && vm.quit();
  console.log('\n' + (FAIL ? 'RUNTIME CHECK: SOME CHECKS FAILED' : 'RUNTIME CHECK COMPLETE — all scenarios passed.'));
  process.exit(FAIL ? 2 : 0);
})().catch(e => { console.error('RUNTIME ERROR:', e); process.exit(1); });
