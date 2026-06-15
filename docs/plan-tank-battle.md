# 탱크 배틀 (tank-battle) — Plan

> 톱다운 솔로 서바이벌. 화살표키로 **누른 방향으로 바로 이동** + 스페이스로 포탄 발사. 화면 위쪽 랜덤 위치에서 끝없이 몰려오는 적 탱크를 **한 방에 격파**(처치 +1점)하며, 흩어진 엄폐물 뒤에 숨어 내 체력 0이 될 때까지 **최대한 오래 버틴다.**
> 베이스: 기존 `games/tank-battle/build.py` (톱다운 탱크·포탄·엄폐물 자산 + 포탄 스프라이트 분리 + 클론 증식 가드). 거기서 **1:1·적체력·승리조건**을 들어내고 **적 스포너 + 한 방 격파 + 점수**로 전환.
> 학습 콘셉트 없음(보너스 액션 게임). 톱다운 시점이므로 포탄은 직선(포물선 아님). 만화풍 귀여운 디자인. 초등학생이 즐길 수 있는 적당한 난이도.

- **주제**: 솔로 탱크 서바이벌 (vs 무한 등장 적)
- **카테고리**: 액션
- **난이도**: ★★☆☆☆
- **폴더**: `games/tank-battle/`
- **출력 파일**: `탱크_배틀.sb3`
- **빌드**: `python3 games/tank-battle/build.py`

---

## 1. 게임 한 줄

플레이어 탱크 1대로 톱다운 화면에서 끝없이 등장하는 적 탱크들을 상대한다. 적은 포탄 한 방에 폭발하며(점수 +1), 적 포탄이나 돌격에 맞아 내 체력 3이 0이 되면 게임오버. 승리 조건은 없고 **오래 버티기 / 많이 처치하기**가 목표다.

---

## 2. 화면 레이아웃 (480×360)

좌표계: SVG/무대 픽셀(0~480, 0~360) ↔ Scratch 좌표(-240~240, -180~180). 변환: `scratchX = svgX - 240`, `scratchY = 180 - svgY`.

```
 (-240,180)                                            (240,180)
   ┌──────────────────────────────────────────────────────┐
   │ 내체력:♥♥♥                                              │  ← 좌상단 변수 모니터
   │ 점수:0          [적▼] [적▼] [적▼]   ← 위쪽 랜덤 스폰     │  적: y 110~170, x -200~200
   │                                                        │     (동시 최대 5대)
   │     [■]    [■]        [■]    [■]      ← 엄폐물 8개       │  흩뿌린 고정 벽
   │          [■]    [■]        [■]                          │  (부서지지 않음)
   │                                                        │
   │                  [플레이어 ▲]  (0,-120)                 │  플레이어 시작: 아래 중앙
   │            ↑↓←→ 누른 방향 이동   space 발사            │
   └──────────────────────────────────────────────────────┘
 (-240,-180)                                          (240,-180)

  내 체력 0 이 되면 화면 중앙에 GAME OVER 배너(게임오버 스프라이트) 표시.
```

- HUD: 좌상단에 `내체력` `점수` 변수 모니터만 노출.
- 엄폐물은 **흩뿌린 고정 좌표 8개를 1회만 배치**(부서지지 않는 영구 벽). 플레이어가 뒤에 숨어 적 포탄을 막는 용도. 플레이어 시작점(0,−120)과 적 스폰 밴드(y≥110)는 피해 배치.

---

## 3. 스프라이트 / 코스튬 / 초기 상태

| # | 이름 | layerOrder | 역할 | 코스튬(자산) | 초기 위치 | 방향 | 크기 | visible | rotationStyle |
|---|------|-----------|------|--------------|-----------|------|------|---------|---------------|
| 0 | Stage | 0 | 배경 + 전역 변수 + 게임 시작/초기화 + 패배 감시 | `bg.svg` (사막 타일) | — | — | — | — | — |
| 1 | 플레이어탱크 | 5 | 방향키 이동 + 발사, 적포탄/적탱크 피격 시 내체력 −1 | `tank_player.svg` (파란 탱크) | (0, −120) | 0 | 75 | true | all around |
| 2 | 포탄 | 3 | 플레이어 발사 포탄(클론). 직선 이동, 적탱크/엄폐물/가장자리에서 소멸 | `shell.svg` (검은 탄두+노란 꼬리) | (0,0) | 90 | 80 | false | all around |
| 3 | 적포탄 | 3 | 적 발사 포탄(클론, **별도 스프라이트**). 직선 이동, 플레이어/엄폐물/가장자리에서 소멸 | `shell_enemy.svg` (붉은 탄두) | (0,0) | 90 | 80 | false | all around |
| 4 | 적탱크 | 4 | **스포너+적 본체.** 깃발 후 무한 스폰. 클론은 추적·간헐 발사, **포탄 한 방에 폭발** | `tank_enemy.svg`(빨강) + `폭발`(불꽃) **2코스튬** | (0, 120) | 180 | 70 | false(클론이 show) | all around |
| 5 | 엄폐물 | 2 | 깃발 시 8개 고정 배치(클론). **부서지지 않는 영구 벽** | `cover.svg` (회색 벽돌 50×50) | (0,0) | 90 | 70 | false(클론이 show) | don't rotate |
| 6 | 게임오버 | 6 | GAME OVER 결과 배너 | `result.svg` (2코스튬: 승리/패배, 실사용은 패배) | (0,0) | 90 | 100 | false | don't rotate |

총 7 타깃(Stage 포함).

> **아트 방향(중요)**: 탱크·포탄 SVG는 위를 향하게 그린 뒤 `<g transform="rotate(90 cx cy)">`로 **오른쪽(=Scratch "전방향 회전"의 기준 방향 90)**을 보게 한다. 이걸 안 하면 스프라이트가 90° 틀어져 렌더되어 포탄이 옆으로 날아가는 것처럼 보인다(이전 버그의 원인). 포탄 2종은 오른쪽을 향하게 직접 그린다.

> **포탄 스프라이트 분리 패턴(필수 유지)**: 플레이어 포탄=`포탄`, 적 포탄=`적포탄`을 별도 스프라이트로 둔다. 자폭/friendly-fire 분기가 전혀 필요 없다 — 적탱크는 `touching 포탄`만, 플레이어탱크는 `touching 적포탄`만 보면 된다. 발사한 탱크는 정지 조건에 자기 탱크를 넣지 않으므로 자기 포탄과 충돌하지 않는다.

---

## 4. 사운드

`assets/pop.wav` 1종을 pitch 이펙트로 재사용.

| 이벤트 | sound_seteffectto PITCH | 위치 |
|--------|--------------------------|------|
| 플레이어 발사 | 100 | 플레이어탱크 발사 시 |
| 적 발사 | −100 | 적탱크 발사 시 |
| 적 격파(폭발) | 0 | 적 클론 포탄 피격 시 |
| 플레이어 피격(내체력 −1) | −300 | 플레이어탱크 피격 시 |

---

## 5. 변수 / 리스트 / 메시지

### 전역 변수 (Stage) — ID 컨벤션 `V_*` / `var*`

| 한국어 | ID | 초기값 | 의미 |
|--------|----|--------|------|
| 내체력 | `varHP01` | 3 | 적 포탄/적 탱크에 맞으면 −1. 0 → 게임오버 |
| 게임상태 | `varState03` | 1 | 1=진행, 0=종료 |
| 결과 | `varResult04` | 2 | 항상 2(패배) — 게임오버 배너 코스튬 호환용(승리 없음) |
| 포탄X | `varBX05` | 0 | 포탄/적포탄 클론 스폰 X (발사 시 set, 클론이 즉시 사용). 시작 시 엄폐물 배치 채널로도 재활용 |
| 포탄Y | `varBY06` | 0 | 〃 Y |
| 포탄방향 | `varBDir07` | 90 | 〃 발사 방향 |
| 무적 | `varInv08` | 0 | >0 동안 플레이어가 피해 무시(연타 즉사 방지, 틱 카운트) |
| 쿨다운 | `varCD10` | 0 | >0 동안 플레이어 발사 불가(틱 카운트) |
| 점수 | `varScore14` | 0 | 적 처치 수. 처치할 때마다 +1 |
| 적수 | `varECnt15` | 0 | 현재 살아있는 적 클론 수(동시 스폰 상한 제어) |
| 적생성X | `varSPX16` | 0 | 적 스폰 좌표 X 전달 채널(스포너→클론) |
| 적생성Y | `varSPY17` | 0 | 〃 Y |

총 전역 변수 12개.

> **제거된 변수**(이전 1:1 버전 대비): 적체력/적무적(한 방 격파라 불필요). **추가**: 점수/적수/적생성X/적생성Y.

### 클론-로컬 변수 — ID 컨벤션 `V_*ISC`

클론 생성 스프라이트에 **로컬** `복제됨` 플래그(원본=0, 클론=1). 적포탄·엄폐물은 방송/원본에서만 클론을 만들게 가드. (적탱크는 스포너 forever가 원본에서만 돌고 클론은 broadcast를 새로 안 받으므로 가드는 보조적.)

| 스프라이트 | 한국어 | ID | 초기값 |
|------------|--------|----|--------|
| 적탱크 | 복제됨 | `varEnemyIsClone11` | 0 |
| 엄폐물 | 복제됨 | `varCoverIsClone12` | 0 |
| 적포탄 | 복제됨 | `varEShellIsClone13` | 0 |

### 메시지(방송) — ID 컨벤션 `BR_*` / `br*`

| 한국어 | ID | 트리거 → 동작 |
|--------|----|---------------|
| 게임시작 | `brStart01` | Stage 깃발 초기화 직후 발송 → 적탱크 스포너 가동 + 엄폐물 8개 배치 |
| 적사격 | `brEFire02` | 적 클론이 발사 조건 충족 시 발송 → 적포탄 클론 생성 |

---

## 6. 씬 / 상태머신

```
[깃발 클릭]
   │  Stage: 내체력=3, 게임상태=1, 결과=2, 점수=0, 적수=0, 무적=0, 쿨다운=0
   │  플레이어탱크: 위치(0,-120) dir 0 / 나머지: 초기 숨김
   ▼
[게임시작 방송]
   │  엄폐물 원본 → 고정 좌표 8개 클론 배치 (포탄X/Y 채널 재활용, ~0.16s)
   │  적탱크 원본 → wait 0.4 후 스포너 forever 가동(엄폐물 배치 끝난 뒤 시작 → 채널 경쟁 방지)
   ▼
[게임플레이 forever]  (게임상태=1 동안)
   ├ 플레이어: ↑↓←→ 방향 이동 / space 발사(쿨다운) / 엄폐물 밀림 / 적포탄·적탱크 피격→내체력-1
   ├ 적 스포너: 적수<5 일 때 랜덤 좌표에 0.6~1.6s 간격으로 클론 생성, 적수+1
   ├ 적 클론: 추적 이동 + 간헐 발사 / touching 포탄 → 폭발(점수+1, 적수-1, 삭제) / touching 플레이어 → 삭제
   ├ 포탄/적포탄: 직선 비행, 대상·엄폐물·가장자리에서 소멸
   └ Stage 패배 감시: 내체력≤0 → 결과=2, 게임상태=0
   ▼
[종료]  게임상태=0
   │  게임오버: 패배 배너 show / 살아있던 적 클론은 게임상태=0 보고 자기 삭제
   ▼
[다시 시작]  초록 깃발 재클릭
```

---

## 7. 블록 흐름 (스프라이트별 의사코드)

> 모든 forever 루프는 끝에 `wait` 넣어 CPU 폭주 방지. 충돌·이동은 0.02~0.05초 틱.

### Stage

**(A) 깃발 클릭 → 초기화 → 게임시작**
```
when green flag clicked
  set 내체력 = 3 ; set 게임상태 = 1 ; set 결과 = 2
  set 점수 = 0 ; set 적수 = 0 ; set 무적 = 0 ; set 쿨다운 = 0
  wait 0.3
  broadcast 게임시작
```

**(B) 카운터 forever (무적/쿨다운 감소)**
```
when green flag clicked
  forever
    if 무적   > 0 : change 무적   by -1
    if 쿨다운 > 0 : change 쿨다운 by -1
    wait 0.04
```

**(C) 패배 감시 forever** (승리 없음)
```
when green flag clicked
  wait until (게임상태 = 1)          ← 초기화 완료 대기(레이스 방지)
  forever
    if (내체력 < 1) and (게임상태 = 1)
        set 결과 = 2
        set 게임상태 = 0
    wait 0.05
```

### 플레이어탱크

**(A) 깃발 초기화**
```
when green flag clicked
  show ; set size 75 ; goto (0,-120)
  set rotation style [all around] ; point in direction 0 ; go to front
```

**(B) 조작 forever — 화살표 = 누른 방향으로 바로 이동**
```
forever
  if key [up arrow]    : point in direction 0   ; move 3
  if key [down arrow]  : point in direction 180 ; move 3
  if key [left arrow]  : point in direction -90 ; move 3
  if key [right arrow] : point in direction 90  ; move 3
  if touching [엄폐물]  : move -3                 ← 벽 통과 방지(되튕김)
  clamp x to ±220, y to ±160
  wait 0.02
```
> 탱크가 향하는 쪽 = 진행 방향 = 포신 방향이므로, 발사도 자연히 그 방향으로 나간다.

**(C) 발사 입력 forever**
```
forever
  if (key [space]) and (쿨다운 = 0) and (게임상태 = 1)
      set 포탄X = x position ; set 포탄Y = y position ; set 포탄방향 = direction
      set sound effect [pitch] to 100 ; play sound pop
      create clone of [포탄]
      set 쿨다운 = 12               ← ≈0.45초
  wait 0.05
```

**(D) 피격 감시 forever**
```
forever
  if (touching [적포탄] or touching [적탱크]) and (무적 = 0) and (게임상태 = 1)
      change 내체력 by -1
      set 무적 = 25                 ← ≈1초 무적
      set sound effect [pitch] to -300 ; play sound pop
  wait 0.05
```
> 적 탱크에 부딪혀도(돌격) 피해를 받는다. 닿은 적은 자기 스크립트가 스스로 폭발 처리.

### 포탄 (플레이어 포탄)

```
when green flag clicked : hide ; set size 80 ; set rotation style [all around]

when I start as a clone
  goto (포탄X, 포탄Y) ; point in direction 포탄방향 ; show
  repeat until ( out-of-bounds OR touching [적탱크] OR touching [엄폐물] )
      move 10 steps ; wait 0.02
  hide ; delete this clone
```
- out-of-bounds = `(x>240 or x<-240) or (y>180 or y<-180)`.
- 정지 조건에 `플레이어탱크` 미포함 → 발사 시 자기 탱크에서 즉시 자폭 안 함.

### 적포탄 (별도 스프라이트)

```
when green flag clicked : hide ; set size 80 ; set rotation style [all around] ; set 복제됨 = 0

when I receive [적사격]
  if (복제됨 = 0) : create clone of [myself]      ← 원본만 생성(증식 가드)

when I start as a clone
  set 복제됨 = 1 ; goto (포탄X, 포탄Y) ; point in direction 포탄방향 ; show
  repeat until ( out-of-bounds OR touching [플레이어탱크] OR touching [엄폐물] )
      move 7 steps ; wait 0.02                    ← 적 포탄은 약간 느리게(피하기 쉽게)
  hide ; delete this clone
```
- 내체력 차감은 플레이어 피격 감시가 처리.

### 적탱크 (스포너 + 한 방 격파 클론)

**(A) 깃발 초기화**
```
when green flag clicked
  hide ; set size 70 ; set rotation style [all around] ; set 복제됨 = 0
```

**(B) 게임시작 → 스포너 forever** (원본이 무한 생성)
```
when I receive [게임시작]
  wait 0.4                                   ← 엄폐물 배치(포탄X/Y 채널 공유) 끝난 뒤 시작
  forever
    if (적수 < 5) and (게임상태 = 1)
        set 적생성X = pick random -200 to 200
        set 적생성Y = pick random 110 to 170
        change 적수 by 1
        create clone of [myself]
    wait (pick random 6 to 16) / 10           ← 0.6~1.6초 간격
```

**(C) 클론 본체**
```
when I start as a clone
  set 복제됨 = 1 ; goto (적생성X, 적생성Y) ; point towards [플레이어탱크] ; show
  forever
    # 1) 게임오버 정리
    if (게임상태 = 0) : hide ; delete this clone
    # 2) 포탄에 맞으면 한 방에 폭발
    if touching [포탄]
        change 점수 by 1
        change 적수 by -1
        switch costume to [폭발]
        set sound effect [pitch] to 0 ; play sound pop
        set size to 85 ; set [ghost] effect to 0
        repeat 5 : change size by 16 ; change [ghost] effect by 20 ; wait 0.02
        delete this clone
    # 3) 돌격 충돌: 플레이어에 닿으면 스스로 폭발(HP 차감은 플레이어가 처리)
    if touching [플레이어탱크] : change 적수 by -1 ; hide ; delete this clone
    # 4) 부정확한 추적
    if (pick random 1 to 3) < 3 : point towards [플레이어탱크]
    # 5) 전진(느린 고정 속도)
    move 1.2 steps
    # 6) 엄폐물·벽 회피
    if touching [엄폐물] : move -2 ; turn cw 30
    clamp x to ±230, y to ±170
    # 7) 간헐 발사
    if (pick random 1 to 100) = 1
        set 포탄X = x position ; set 포탄Y = y position ; set 포탄방향 = direction
        set sound effect [pitch] to -100 ; play sound pop ; broadcast 적사격
    wait 0.04
```
> **한 방 격파**: 이전의 적체력+적무적 프레임 구조를 없애, `touching 포탄` 한 번이면 즉시 폭발한다("마지막 한 방이 안 맞는" 문제 해소). 폭발 연출 = 폭발 코스튬 전환 후 크게 부풀며(size +16×5) 투명해진(ghost +20×5) 뒤 클론 삭제. 새 클론은 원본 상태(tank 코스튬·size 70·이펙트 없음)를 물려받아 영향 없음.
> **동시 상한**: `적수 < 5`로 동시 생존 수 제한. 스폰 시 +1, 격파/돌격/게임오버 정리 시 −1.

### 엄폐물 (부서지지 않는 영구 벽 8개)

**(A) 깃발 초기화**
```
when green flag clicked : hide ; set size 70 ; set 복제됨 = 0
```

**(B) 게임시작 → 고정 좌표 8개 배치** (원본만)
```
when I receive [게임시작]
  if (복제됨 = 0)
      for (x,y) in [(-150,70),(0,90),(150,70),(-90,0),(90,0),(-150,-90),(0,-50),(150,-90)]
          set 포탄X = x ; set 포탄Y = y ; create clone of [myself] ; wait 0.02
```
> 스폰 좌표 전용 변수 대신 **`포탄X`/`포탄Y`를 전달 채널로 재활용**(게임 시작 직후라 발사와 충돌 없음 — 적 스포너가 wait 0.4 후 시작하므로 안전).

**(C) 클론 본체** (영구 벽 — 부서지지 않음)
```
when I start as a clone
  set 복제됨 = 1 ; goto (포탄X, 포탄Y) ; show
  (이후 동작 없음 — 그 자리에 고정 표시)
```

### 게임오버 (패배 배너)

```
when green flag clicked
  hide ; goto (0,0) ; set size 100 ; go to front
  wait until (게임상태 = 1)
  wait until (게임상태 = 0)
  if (결과 = 1) : switch costume [승리]   ← 서바이벌에선 결과=2 고정이라 항상 아래로
  else          : switch costume [패배]
  show
```

---

## 8. 학습 포인트

보너스 액션 게임 — 수학 학습 콘셉트 없음. (톱다운 직선 포탄, 4방향 이동, 무한 서바이벌의 직관적 재미만.)

---

## 9. 빌드 / 검증 체크리스트

- [ ] zip 열기 성공, `project.json` 파싱 성공, 모든 자산 `(md5).svg`/`.wav` 존재
- [ ] 타깃 7개: Stage / 플레이어탱크 / 포탄 / 적포탄 / 적탱크 / 엄폐물 / 게임오버
- [ ] 전역 변수 **정확히 12개**, 클론-로컬 `복제됨` 3개(적탱크/엄폐물/적포탄), 방송 **정확히 2개**(게임시작/적사격)
- [ ] HUD 모니터 2개: 내체력·점수만 표시
- [ ] 적탱크 코스튬 2개(tank_enemy/폭발), 폭발 연출 블록(switch costume·change size·change ghost effect·repeat) 존재
- [ ] **화살표 = 누른 방향으로 이동** (↑0/↓180/←-90/→90), 발사 방향 = 탱크 방향
- [ ] 적 스포너: 시간차로 적 클론 생성, **동시 최대 5대** 상한, 위쪽 밴드(y 110~170)에 스폰
- [ ] 적 클론이 플레이어 추적(아래로 이동) + 간헐 발사, 엄폐물 뒤로 가면 적 포탄 막힘
- [ ] 적이 `touching 포탄` 한 번에 폭발 → 점수 +1, 적수 −1, 클론 삭제
- [ ] 적 포탄/적 돌격에 내체력 −1(무적 후 연타 즉사 방지), 내체력 0 → 게임상태=0 + GAME OVER 배너
- [ ] 게임오버 후 잔여 적 클론 전부 자기 삭제, 깃발 재클릭으로 재시작
- [ ] 엄폐물 8개 고정 배치(부서지지 않음), 포탄/적포탄이 엄폐물·가장자리에서 소멸
- [ ] headless scratch-vm 실행: 4방향 이동·발사 방향·적 스폰/추적/상한·게임오버 트리거 확인 (touching 기반 격파·폭발 연출은 headless 에서 검증 불가 → 구조/opcode 존재로 확인)
```
