# 골드 마이너 (gold-miner) — Plan

> 화면 위쪽 중앙의 광부에서 후크가 줄에 매달려 좌↔우로 진자처럼 흔들린다. **스페이스(또는 클릭)** 로 후크를 발사하면 현재 가리키는 각도 방향으로 직선 하강 → 아이템에 닿으면 잡아서 되감기, 빗나가면 끝까지 갔다가 되감기. 잡은 아이템 무게에 따라 되감기 속도가 달라진다(무거울수록 느림). 60초 안에 라운드 목표 점수를 달성하면 다음 라운드(목표 점수 증가 + 아이템 재배치), 못 채우면 게임오버.
> 베이스: `games/bubble-shooter/build.py`(상단 피벗에서 각도 조준 + 발사체 직선 이동 패턴) + `games/apple-catch/build.py`(클론 무한 배치 + sprite-local 변수로 개체별 속도/타입 분기) + `games/cowboy-duel`·`games/duck-hunt/build.py`(라운드 진행 + 60초 타이머 + 목표/게임오버 배너).
> 학습 콘셉트 절대 없음. 순수 액션(타이밍 + 무게 전략). 초등학생 대상 직관적(스페이스 1키). 클래식 "골드 마이너" 메커닉 충실 재현. (MEMORY.md → feedback-game-design 준수)

---

## 1. 한 줄 룰

좌우로 흔들리는 후크를 보고 타이밍 맞춰 **스페이스**를 눌러 발사한다. 후크가 가리키던 방향으로 쭉 내려가 닿은 아이템을 끌어올린다. 무거운 금괴는 점수가 크지만 천천히 올라오고, 가벼운 다이아는 빠르게 올라온다. 돌은 무겁고 점수가 작으니 피하는 게 이득. 60초 안에 목표 점수를 채우면 다음 라운드로!

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- SVG 좌표(0..480 / 0..360) ↔ Scratch 좌표 변환: `sx = svgX - 240`, `sy = 180 - svgY`.
- **피벗(광부의 손/도르래) 위치**: x = 0, y = +120 (화면 위쪽 중앙). 후크와 줄은 모두 이 점을 기준으로 회전·발사한다.
- **흔들림 영역**: 피벗을 중심으로 각도 -75°~+75° 왕복(아래 방향 기준). 후크는 발사 전 항상 피벗에서 일정 거리(줄길이 60px)에 매달려 흔들린다.
- **플레이(아이템) 영역**: y = -20 ~ -160 (화면 하단 2/3). 아이템 8~10개가 이 영역에 랜덤 배치, 겹침 최소화.
- HUD(상단 모니터): 점수 / 목표점수 / 시간 / 라운드.

```
+----------------------------------------------------------+ y=+180
| 점수:120  목표:200   시간:47   라운드:1                   |  ← 변수 모니터 (상단)
|                    ⛏️ 광부 (피벗 x=0,y=+120)              |  y=+120  ● 피벗
|                   /  |  \                                 |
|                 /    |    \   ← 후크가 진자처럼 흔들림     |
|               /  -75°|+75° \                              |
|              ↙       ↓       ↘   (줄 끝 후크, 줄길이 60)   |  y=+60
|                                                          |
|   💎      🪙(대)        🪨                                |  y=-40
|        🪙(소)     💎        🪙(중)     🪨                  |  y=-100
|     🪨       🪙(대)      💎        🪙(소)                  |  y=-150
+----------------------------------------------------------+ y=-180
  x=-240                                              x=+240
                  [ 스페이스 / 클릭 = 후크 발사 ]
```

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 코스튬 |
|---|------|------|--------|
| 0 | Stage | 배경(광산/땅속) + 전역 변수 + 60초 타이머 + 라운드 진행/목표 판정 + 아이템 배치 트리거 | bg.svg |
| 1 | 광부 | 피벗 위치 장식(고정). 발사 시 살짝 당기는 연출(선택). 항상 보임 | miner.svg |
| 2 | 후크 | **메인 컨트롤러**. 진자 흔들림 + 발사/하강/되감기 상태머신. 줄도 이 스프라이트가 stretch 코스튬으로 그림 | hook.svg(후크만, 줄은 별도) |
| 3 | 줄 | 피벗→후크를 잇는 얇은 막대. `set size`(세로 stretch)로 길이 조절, `point toward` 로 방향 맞춤. (안전한 줄 표현 — pen 사용 안 함) | rope.svg(세로 1px폭 막대) |
| 4 | 아이템 | 클론 무한 배치. 금괴 대/중/소·돌·다이아 5타입. 무게별 되감기 속도 + 점수. 잡히면 후크 따라 올라옴 | gold_l, gold_m, gold_s, rock, diamond (5코스튬) |
| 5 | 게임오버/클리어 배너 | 목표 미달=게임오버, 60초 내 달성=라운드 클리어 연출. 평소 숨김 | gameover.svg, clear.svg |

총 6 스프라이트(Stage 포함). 줄을 별도 스프라이트로 분리하면 후크 상태머신과 독립적으로 그릴 수 있어 디버그 쉬움.

> **줄 표현 결정(중요)**: Scratch 에서 pen 은 클론·재시작 시 잔상/지우기 관리가 번거롭다. 따라서 **줄은 별도 스프라이트 + stretch 코스튬** 방식을 채택한다. `rope.svg` 는 세로로 긴 얇은 막대(viewBox 4×100, rotationCenter 를 **맨 위 끝**에 둠 → 위 끝이 피벗에 고정되고 아래로 늘어남). 매 틱 `줄: goto 피벗(0,120) → point toward 후크 → set size to (피벗~후크 거리 / 기준길이 ×100)`. 후크가 내려갈수록 size 의 세로가 늘어 줄이 길어지는 효과. (대안: 줄 없이 후크만 — 더 단순하지만 클래식 느낌이 약함. 빌더가 시간이 부족하면 줄 스프라이트 생략 가능 → 5 스프라이트.)

---

## 4. 변수 (Stage 글로벌)

| 한국어 | ID | 초기값 | 의미 |
|--------|----|--------|------|
| 점수 | `varScore01` | 0 | 끌어올린 아이템 점수 누적 |
| 목표점수 | `varGoal02` | 150 | 이번 라운드 목표. 라운드마다 증가 |
| 시간 | `varTime03` | 60 | 매 1초 -1. 0 되면 라운드 판정 |
| 라운드 | `varRound04` | 1 | 현재 라운드 번호 |
| 게임상태 | `varState05` | 1 | 1=플레이 중, 0=게임오버(종료) |
| 후크상태 | `varHookSt06` | 0 | 0=대기(흔들림), 1=하강 중, 2=되감기 중 |
| 후크각도 | `varHookAng07` | 0 | 발사 순간 고정되는 하강 방향(도). 90=정아래 기준이 아니라 Scratch direction(180=정아래) |
| 잡힌점수 | `varCaught08` | 0 | 현재 후크에 잡힌 아이템의 점수(되감기 완료 시 점수에 더함) |
| 잡힌속도 | `varCaughtSp09` | 0 | 현재 잡힌 아이템의 되감기 속도(px/틱). 무게로 결정 |
| 잡힘플래그 | `varGrabbed10` | 0 | 0=아직 못 잡음, 1=이번 발사에서 아이템을 잡음 |
| 아이템수 | `varItemN11` | 9 | 이번 라운드 배치할 아이템 개수 |
| 배치X | `varSpawnX12` | 0 | 아이템 클론 배치 x |
| 배치Y | `varSpawnY13` | 0 | 아이템 클론 배치 y |
| 배치타입 | `varSpawnT14` | 1 | 1=금괴대 2=금괴중 3=금괴소 4=돌 5=다이아 |

후크 sprite-local 변수: 없음(상태는 Stage 글로벌로 — 줄/아이템이 후크 위치를 참조해야 하므로 후크의 x/y 는 `x position of 후크` 센싱으로 읽음).

아이템 sprite-local 변수:

| 한국어 | ID | 의미 |
|--------|----|------|
| 내타입 | `varMyType15` | 클론 시작 시 `배치타입` 복사. 코스튬·점수·속도 분기 |
| 내점수 | `varMyScore16` | 타입별 점수(대200/중100/소50/돌20/다이아150 등) |
| 내속도 | `varMySpeed17` | 타입별 되감기 속도(무거울수록 느림) |
| 잡혔나 | `varMyHeld18` | 0=땅에 놓임, 1=내가 후크에 잡혀 끌려오는 중 |

---

## 5. 방송 (broadcasts)

| 한국어 | ID | 트리거 |
|--------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 → 변수 초기화 직후. 후크 흔들림 시작, 타이머 시작, 첫 라운드 배치 |
| 라운드시작 | `brRoundStart02` | 새 라운드 시작 시(게임시작 직후 1회 + 라운드 클리어 후). 기존 클론 삭제 → 아이템 재배치 → 시간 60 리셋 |
| 아이템배치 | `brSpawnItem03` | 라운드 시작 시 `아이템수` 만큼 반복 발송 → 아이템 클론 1개씩 생성 |
| 발사 | `brFire04` | 후크 대기 중 스페이스/클릭 입력 → 후크상태=1(하강) 전환 신호. 줄·후크 동기화용 |
| 라운드끝 | `brRoundEnd05` | 시간=0 도달 시. 점수≥목표 → 라운드 클리어(다음 라운드), 미달 → 게임오버 |

---

## 6. 씬 / 상태머신

```
[깃발]
  → init(점수0, 라운드1, 목표점수150, 게임상태1, 후크상태0)
  → broadcast 게임시작
  → broadcast 라운드시작 (첫 라운드)
   │
   ▼
[라운드시작]
  - 기존 아이템 클론 전부 삭제
  - 시간 ← 60, 점수는 누적 유지(또는 라운드별 리셋 — 본 plan은 누적 유지 + 목표는 누적 기준)
  - 아이템수 ← 8 + min(라운드,2)  (라운드 갈수록 살짝 많게, 상한 10)
  - repeat 아이템수: 배치X/Y/타입 랜덤 → broadcast 아이템배치
  - 후크상태 ← 0 (흔들림 시작)
  - 60초 타이머 시작
   │
   ▼
[후크 상태머신]  (후크 스프라이트가 forever 로 관리)
   ┌─ 후크상태 0 (대기/흔들림) ──────────────────────────┐
   │  피벗(0,120) 기준 각도 -75..+75 왕복 진자 운동       │
   │  스페이스 또는 클릭? → broadcast 발사 → 후크상태 1   │
   └────────────────────────────────────────────────────┘
   ┌─ 후크상태 1 (하강) ─────────────────────────────────┐
   │  발사 순간 각도 고정 → 그 방향으로 직선 이동         │
   │  아이템에 닿음? → 잡힘(잡힌점수/속도 기록) → 후크상태2│
   │  화면 끝(가장자리 또는 y<-175) 도달? → 후크상태 2    │
   └────────────────────────────────────────────────────┘
   ┌─ 후크상태 2 (되감기) ───────────────────────────────┐
   │  피벗 방향으로 되돌아옴(잡힌속도 = 무게 반영)        │
   │  피벗 도달? → 잡았으면 점수 += 잡힌점수, 아이템 삭제 │
   │            → 후크상태 0 (다시 흔들림)                │
   └────────────────────────────────────────────────────┘
   │
   ▼ (시간=0)
[라운드끝]
   - 점수 ≥ 목표점수 → 라운드 클리어
        라운드 ← 라운드+1, 목표점수 ← 목표점수 + 100, CLEAR 배너
        wait → broadcast 라운드시작 (다음 라운드)
   - 점수 < 목표점수 → 게임상태 ← 0, GAME OVER 배너 → 종료
   ▼ [깃발 재클릭] → 처음으로
```

---

## 7. 메커닉 상세

### 7.1 후크 — 진자 흔들림 + 발사/하강/되감기 (핵심)

후크 스프라이트 하나가 상태머신 전체를 forever 로 돌린다. 피벗은 (0, 120). 후크는 **Scratch direction** 으로 각도를 표현(90=오른쪽, 180=아래, 0=위). 정아래는 180. 흔들림 범위는 정아래 기준 ±75° → direction 105° ~ 255° 사이를 왕복(아래 반구).

> 단순화를 위해 흔들림은 **별도 위상 변수 phase 로 사인 진자**를 만든다: `각도 ← 180 + 75 × sin(phase)` (phase 를 매 틱 += 4 정도 증가 → 부드러운 좌우 왕복). 줄길이(피벗~후크 거리) = 60px 고정. 후크 위치는 피벗에서 각도 방향으로 60px:
> `후크x = 0 + sin(각도) × 60`, `후크y = 120 - cos(각도) × 60` (Scratch direction 기준: x = pivotX + sin(dir)×r, y = pivotY + cos(dir)×r → 단, Scratch 의 sin/cos 는 도(degree) 입력).

```
when receive 게임시작:
  goto pivot (0, 120)
  set 후크상태 ← 0
  set phase ← 0                      # sprite-local 또는 글로벌 임시
  forever:
    if 게임상태 = 0: stop this script

    # ── 상태 0: 대기/흔들림 ──
    if 후크상태 = 0:
      phase ← phase + 4
      후크각도 ← 180 + 75 * (sin of phase)      # 정아래±75°
      후크x ← 0 + (sin of 후크각도) * 60
      후크y ← 120 + (cos of 후크각도) * 60       # cos(180)=-1 → y=60 (아래)
      goto (후크x, 후크y)
      point in direction 후크각도              # 후크 머리가 줄 방향 향함
      if (key space pressed?) OR (mouse down?):
        broadcast 발사
        후크상태 ← 1
        # 후크각도는 이 순간 값으로 고정(이미 변수에 들어있음)
        잡힘플래그 ← 0
        잡힌점수 ← 0
        잡힌속도 ← 0

    # ── 상태 1: 하강 ──
    if 후크상태 = 1:
      # 고정된 후크각도 방향으로 직선 이동 (8px/틱)
      change x by (sin of 후크각도) * 8
      change y by (cos of 후크각도) * 8
      # (충돌은 아이템 스프라이트가 검사 → 잡힘플래그/잡힌점수/잡힌속도 설정 후 후크상태=2)
      if 잡힘플래그 = 1:
        후크상태 ← 2
      # 화면 끝 도달 → 빈손 되감기
      if (y position < -175) OR (touching edge?) OR (x position < -235) OR (x position > 235):
        후크상태 ← 2                          # 빈손, 잡힌속도=0 → 기본 빠른 되감기
        if 잡힌속도 = 0: 잡힌속도 ← 12         # 빈손은 빠르게 복귀

    # ── 상태 2: 되감기 ──
    if 후크상태 = 2:
      # 피벗(0,120) 방향으로 잡힌속도 만큼 이동
      point toward pivot               # 후크 → 피벗 각도 (또는 atan 계산)
      move (잡힌속도) steps             # 잡힌속도 = 무게 반영(2~12)
      if (distance to pivot) < 8:       # 피벗 도착
        goto (0,120) 흔들림 시작점 근처
        if 잡힘플래그 = 1:
          점수 ← 점수 + 잡힌점수
          play sound coin (피치 = 타입별)
          broadcast 아이템수거됨        # 잡힌 아이템 클론 삭제 신호
        후크상태 ← 0                    # 다시 흔들림
    wait 0.02
```

> **point toward pivot**: 후크에서 (0,120)을 향하는 방향. Scratch `point towards` 는 다른 스프라이트/마우스만 가능하므로, **피벗 위치(0,120)를 가진 보이지 않는 "피벗" 헬퍼 스프라이트**를 두고 `point towards 피벗` 하거나, 광부 스프라이트(피벗에 위치)를 향하게 한다. **빌더 권장**: 광부 스프라이트를 피벗(0,120)에 두고 `point towards 광부` 후 `move 잡힌속도 steps`. (별도 헬퍼 불필요.)
> **잡힌속도(무게 반영)**: 무거울수록 작다(느림). 금괴대=3, 금괴중=5, 금괴소=8, 돌=2.5, 다이아=11. 빈손=12. → 무거운 대형 금괴는 끌어올리는 데 시간이 걸려 그 사이 시간 압박(전략 요소).
> **각도 고정**: 발사 순간의 `후크각도` 값이 상태 1 내내 유지되어야 하므로, 상태 0에서만 후크각도를 갱신하고 상태 1·2에서는 건드리지 않는다(위 코드 구조가 이미 그렇게 됨 — 후크각도 갱신은 `if 후크상태=0` 블록 안에만).

### 7.2 줄 (rope) — stretch 표현

매 틱 피벗과 후크를 잇는다. rotationCenter 가 막대 **위 끝**에 있는 세로 막대 코스튬.

```
when receive 게임시작:
  forever:
    goto (0, 120)                     # 위 끝을 피벗에 고정
    point towards 후크                 # 줄이 후크를 향함
    d ← distance to 후크               # 피벗~후크 거리
    set size to (d / 60 * 100)        # 기준 60px일 때 100% → 거리 비례 stretch
    wait 0.02
```

> 코스튬 viewBox 가 세로 60px(폭 4px) 기준이면 size 100%에서 길이 60. 후크가 멀어지면 size↑로 길어짐. **줄 폭도 같이 늘어나는 문제**가 있으면(size 는 가로세로 동시 스케일), 폭을 매우 얇게(2px) 그려 두면 시각적으로 무시 가능. 더 정밀히 하려면 줄을 생략(빌더 판단). 본 plan 의 검증은 줄 생략도 허용.

### 7.3 아이템 (클론 배치 + 잡힘)

라운드 시작 시 `아이템수` 만큼 클론 생성. 각 클론은 타입별 코스튬/점수/속도를 로컬에 갖고, 평소엔 가만히 있다가 후크(하강 상태)에 닿으면 자신을 "잡힘" 상태로 만들고 후크 위치를 따라온다.

```
when flag clicked:
  hide
  set size 60

when receive 아이템배치:
  # Stage 가 배치X/Y/타입을 정해 보냄 → 클론 1개 생성
  내타입 ← 배치타입
  goto (배치X, 배치Y)
  create clone of _myself_

when I start as clone:
  잡혔나 ← 0
  # 타입별 코스튬/점수/속도 매핑
  if 내타입 = 1: switch costume gold_l; 내점수 ← 200; 내속도 ← 3       # 금괴 대(무거움→느림)
  if 내타입 = 2: switch costume gold_m; 내점수 ← 100; 내속도 ← 5       # 금괴 중
  if 내타입 = 3: switch costume gold_s; 내점수 ← 50;  내속도 ← 8       # 금괴 소(가벼움→빠름)
  if 내타입 = 4: switch costume rock;   내점수 ← 20;  내속도 ← 2.5     # 돌(무겁+저점)
  if 내타입 = 5: switch costume diamond;내점수 ← 150; 내속도 ← 11      # 다이아(가볍+고점)
  size by 타입(대 80 / 중 65 / 소 50 / 돌 70 / 다이아 55)
  show
  forever:
    if 게임상태 = 0: delete this clone
    if 잡혔나 = 0:
      # 땅에 놓인 상태: 하강 중인 후크에 닿았는지 검사
      if (후크상태 = 1) AND (touching 후크?) AND (잡힘플래그 = 0):
        잡혔나 ← 1
        잡힘플래그 ← 1            # 후크에게 "잡았다" 알림
        잡힌점수 ← 내점수
        잡힌속도 ← 내속도
    if 잡혔나 = 1:
      # 후크에 매달려 따라옴
      goto (x position of 후크, y position of 후크)
      # 후크가 피벗 도착해 점수 처리하면 아래 방송으로 삭제
    wait 0.02

when receive 아이템수거됨:
  if 잡혔나 = 1:
    delete this clone               # 끌어올려진 아이템 제거

when receive 라운드시작:
  delete this clone                 # 새 라운드 → 기존 클론 정리(본체는 hide 라 영향 없음)
```

> **잡힘 단일화**: `잡힘플래그 = 0` 조건으로 한 번에 한 아이템만 잡히게 한다(여러 아이템 동시 잡힘 방지). 첫 충돌 아이템이 플래그를 1로 올리면 나머지는 못 잡음.
> **따라오기**: 잡힌 아이템은 매 틱 후크 위치로 goto. 후크가 되감기로 피벗에 도착 → `아이템수거됨` 방송 → 클론 삭제 + 점수 가산(점수 가산은 후크가, 삭제는 아이템이).
> **겹침 최소화**: Stage 배치 시 그리드 기반(아래 7.4). 완벽한 비겹침은 불필요 — 살짝 겹쳐도 게임성 문제 없음.

### 7.4 Stage — 라운드 진행 / 배치 / 타이머 / 판정

```
when flag clicked:
  점수 ← 0
  라운드 ← 1
  목표점수 ← 150
  게임상태 ← 1
  후크상태 ← 0
  broadcast 게임시작
  broadcast 라운드시작

when receive 라운드시작:
  시간 ← 60
  아이템수 ← 8 + (라운드 if 라운드<2 else 2)     # 8~10개
  if 아이템수 > 10: 아이템수 ← 10
  wait 0.1                                       # 기존 클론 삭제 처리 대기
  repeat 아이템수:
    배치X ← pick random -210 to 210
    배치Y ← pick random -160 to -20
    배치타입 ← 가중 랜덤 (아래 표)
    broadcast 아이템배치
    wait 0.03                                    # 클론 생성 간격(겹침·동시성 완화)

when receive 게임시작:          # 60초 타이머 (별도 핸들러)
  forever:
    if 게임상태 = 0: stop this script
    wait 1
    if 게임상태 = 1:
      시간 ← 시간 - 1
      if 시간 ≤ 0:
        broadcast 라운드끝
        stop this script        # 라운드끝에서 다음 타이머 재가동

when receive 라운드끝:
  if 점수 ≥ 목표점수:
    # 라운드 클리어
    broadcast 클리어연출        # CLEAR 배너
    wait 2
    라운드 ← 라운드 + 1
    목표점수 ← 목표점수 + 100
    broadcast 라운드시작
    broadcast 게임시작          # 타이머 재가동(타이머 핸들러 재실행)
  else:
    게임상태 ← 0
    broadcast 게임오버연출      # GAME OVER 배너
```

가중 랜덤(배치타입) — 금괴 중심, 다이아·돌 소량:

| 타입 | 값 | 확률(대략) |
|------|----|-----------|
| 금괴 대 | 1 | 15% |
| 금괴 중 | 2 | 30% |
| 금괴 소 | 3 | 30% |
| 돌 | 4 | 15% |
| 다이아 | 5 | 10% |

구현: `r ← pick random 1 to 100`; `if r≤15:1` `elif r≤45:2` `elif r≤75:3` `elif r≤90:4` `else:5`.

### 7.5 광부 / 배너

```
# 광부 (피벗 장식 + point toward 타겟)
when flag clicked:
  goto (0, 120)                  # 피벗 위치 — 후크/줄이 이걸 향함
  show
  switch costume miner_idle
# (발사 시 살짝 당기는 연출은 선택: when receive 발사 → 잠깐 다른 코스튬)

# 배너
when flag clicked:
  hide; goto (0,0); size 100; go to front
when receive 클리어연출:
  switch costume clear; show; play sound win; wait 1.8; hide
when receive 게임오버연출:
  switch costume gameover; show; play sound lose       # 깃발 전까지 유지
```

---

## 8. 스프라이트별 블록 트리 (의사코드)

> 7장이 이미 스프라이트별 의사코드 수준이므로, 여기서는 핵심 분기만 압축 재기재(빌더 1:1 매핑용). 상세 수치는 7장 참조.

### Stage
- `when flag` → init 9변수 + broadcast 게임시작 + 라운드시작
- `when 라운드시작` → 시간60, 아이템수 계산, `repeat 아이템수 {배치X/Y/타입 랜덤; broadcast 아이템배치; wait 0.03}`
- `when 게임시작` → 타이머 forever (`wait 1; 시간-1; if 시간≤0 broadcast 라운드끝; stop`)
- `when 라운드끝` → if 점수≥목표 {클리어연출; 라운드+1; 목표+100; broadcast 라운드시작+게임시작} else {게임상태0; 게임오버연출}

### 후크 (메인 상태머신)
- `when 게임시작` → goto(0,120), 후크상태0, phase0, **forever**:
  - `if 게임상태0: stop`
  - `if 후크상태0`: phase+=4; 후크각도=180+75*sin(phase); goto sin/cos 위치; point in direction 후크각도; `if (space or mouse down){broadcast 발사; 후크상태1; 잡힘플래그0; 잡힌점수0; 잡힌속도0}`
  - `if 후크상태1`: change x by sin(후크각도)*8; change y by cos(후크각도)*8; `if 잡힘플래그1 → 후크상태2`; `if 화면끝 → 후크상태2; if 잡힌속도0 잡힌속도12`
  - `if 후크상태2`: point towards 광부; move 잡힌속도 steps; `if distance to 광부 <8 {goto pivot; if 잡힘플래그1 {점수+=잡힌점수; play coin; broadcast 아이템수거됨}; 후크상태0}`
  - `wait 0.02`

### 줄 (선택)
- `when 게임시작` → forever: goto(0,120); point towards 후크; set size to (distance to 후크 / 60 *100); wait 0.02

### 아이템 (클론)
- `when flag` → hide, size60
- `when 아이템배치` → 내타입=배치타입; goto(배치X,배치Y); create clone of myself
- `when start as clone` → 잡혔나0; 타입별 코스튬/내점수/내속도/size 분기(5개); show; **forever**:
  - `if 게임상태0: delete`
  - `if 잡혔나0 and 후크상태1 and touching 후크 and 잡힘플래그0`: 잡혔나1; 잡힘플래그1; 잡힌점수=내점수; 잡힌속도=내속도
  - `if 잡혔나1`: goto (x of 후크, y of 후크)
  - `wait 0.02`
- `when 아이템수거됨` → if 잡혔나1: delete this clone
- `when 라운드시작` → delete this clone

### 광부
- `when flag` → goto(0,120), switch miner_idle, show

### 배너
- `when flag` → hide, goto(0,0), front
- `when 클리어연출` → costume clear, show, win sound, wait1.8, hide
- `when 게임오버연출` → costume gameover, show, lose sound

---

## 9. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| bg.svg | SVG (인라인) | 480×360. 위쪽 갈색 땅 표면(광부 서 있는 지면) + 아래쪽 어두운 땅속 동굴(짙은 갈색→검정 그라데이션) + 군데군데 광맥 반짝임 점 |
| miner.svg | SVG (인라인) | 광부 캐릭터(헬멧+곡괭이). 약 60×70. rotationCenter 중앙. (0,120)에 설치 |
| hook.svg | SVG (인라인) | 금속 갈고리(아래 향한 ⌣ 모양). 약 24×30. rotationCenter 를 **위쪽(줄 연결점)** 에 둠 → point in direction 시 갈고리 끝이 아래 향함 |
| rope.svg | SVG (인라인) | 세로 얇은 막대(viewBox 4×60, 갈색/회색). rotationCenter 를 **맨 위 끝**에. 줄 생략 시 불필요 |
| gold_l.svg | SVG (인라인) | 큰 금괴(노랑/주황 사다리꼴, 반짝임). 점수200 |
| gold_m.svg | SVG (인라인) | 중간 금괴 |
| gold_s.svg | SVG (인라인) | 작은 금덩이 |
| rock.svg | SVG (인라인) | 회색 돌멩이(울퉁불퉁) |
| diamond.svg | SVG (인라인) | 파란/하늘색 다이아몬드(반짝임) |
| clear.svg | SVG (인라인) | "ROUND CLEAR!" 금색 배너 + "다음 라운드로!" |
| gameover.svg | SVG (인라인) | "GAME OVER" 배너 + "목표 점수를 못 채웠어요" |
| coin.wav / win.wav / lose.wav | WAV (assets/) | 수거음/클리어/게임오버. 기존 `games/duck-hunt/assets/pop.wav` 복사 후 피치 변주로 1개만 있어도 동작 |

> 아이템 5코스튬은 **아이템 스프라이트 1개**에 모두 넣는다(코스튬 인덱스 1~5 = gold_l/gold_m/gold_s/rock/diamond). `switch costume to (내타입)` 로 번호 직접 사용 가능하게 순서 정렬.
> WAV 는 `games/duck-hunt/assets/pop.wav` 1개 복사 → coin 으로 사용, 피치로 타입별 변주(다이아 +300, 금괴 0, 돌 -200). 최소 pop.wav 1개로 충분.

assets/ 폴더: 최소 `pop.wav`. 나머지 SVG 는 build.py 인라인.

---

## 10. 변수/리스트/메시지 요약 (ID 컨벤션)

- 글로벌 변수 14개: `varScore01`(점수) `varGoal02`(목표점수) `varTime03`(시간) `varRound04`(라운드) `varState05`(게임상태) `varHookSt06`(후크상태) `varHookAng07`(후크각도) `varCaught08`(잡힌점수) `varCaughtSp09`(잡힌속도) `varGrabbed10`(잡힘플래그) `varItemN11`(아이템수) `varSpawnX12`(배치X) `varSpawnY13`(배치Y) `varSpawnT14`(배치타입)
- 후크 sprite-local 임시: `phase`(진자 위상 — 글로벌 임시로 둬도 무방, 권장은 후크 로컬)
- 아이템 sprite-local 4개: `varMyType15`(내타입) `varMyScore16`(내점수) `varMySpeed17`(내속도) `varMyHeld18`(잡혔나)
- 리스트: 없음
- broadcasts 6개: `brStart01`(게임시작) `brRoundStart02`(라운드시작) `brSpawnItem03`(아이템배치) `brFire04`(발사) `brRoundEnd05`(라운드끝) + 연출용 `brCleared06`(클리어연출)/`brGameOver07`(게임오버연출)/`brCollect08`(아이템수거됨) — 실제 8개. 발사(brFire04)는 연출 동기화용(생략 가능).
- 모니터(상단 표시): 점수(좌상단), 목표점수, 시간, 라운드.

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **상단 피벗에서 각도 조준 + 발사체 직선 이동(point in direction → change x/y by sin/cos)**: `games/bubble-shooter/build.py`(조준선 각도 + 버블 발사) 와 `games/shuriken-throw`·`games/asteroids/build.py`(direction 기반 이동). 후크 하강이 이 패턴과 동일 — sin/cos × 속도로 직선 이동.
- **진자 사인 흔들림(`각도 = 중심 + 진폭 × sin(phase)`, phase 매 틱 증가)**: `games/balloon-shooter`(풍선 좌우 sin 흔들림) 의 위상 누적 sin 패턴. 후크 흔들림에 그대로 적용.
- **클론 무한 배치 + sprite-local 변수로 개체별 속도/타입/점수 분기 + 타입별 코스튬 switch**: `games/apple-catch/build.py`(사과/폭탄 타입 분기) · `games/balloon-shooter/build.py`(색×크기 코스튬 분기). 아이템 5타입 분기가 동일 구조.
- **60초 타이머(별도 `when 게임시작` forever) + 시간 모니터**: `games/whack-a-prime`·`games/balloon-shooter/build.py`. 라운드 클리어 시 타이머 재가동만 추가.
- **라운드 진행(라운드+1, 목표 증가, 다음 라운드 broadcast) + 클리어/게임오버 배너 코스튬 분기**: `games/cowboy-duel/build.py`(라운드 스케일링) + `games/duck-hunt`·`games/apple-catch/build.py`(배너 sprite show/hide).
- **`point towards <스프라이트> + move steps` 로 되감기**: 거의 모든 추적 게임(`games/zombie-shooter`·`games/dogfight`)의 추적 이동. 후크 되감기는 광부(피벗)를 향해 move.

빌더 권장 진행: (1) bubble-shooter 의 조준/발사체 구조를 후크 상태머신 골격으로, (2) apple-catch 의 클론+로컬변수 구조를 아이템으로, (3) cowboy-duel/duck-hunt 의 라운드·배너·타이머를 Stage 로 합친다.

**필요한 블록 opcode (확인용)**:
- `operator_mathop`(sin/cos), `operator_random`, `operator_mult`/`operator_add`/`operator_div`(각도→위치, stretch 비율)
- `motion_pointindirection`, `motion_pointtowards`("광부"/"후크"), `motion_movesteps`, `motion_changexby`/`changeyby`, `motion_gotoxy`, `motion_xposition`/`yposition`, `sensing_distanceto`
- `sensing_touchingobject`("후크"/edge), `sensing_keypressed`("space"), `sensing_mousedown`
- `control_create_clone_of`, `control_start_as_clone`, `control_delete_this_clone`, `control_forever`, `control_repeat`, `control_if`(중첩 분기)
- `looks_switchcostumeto`(번호/이름), `looks_setsizeto`, `looks_show`/`hide`
- `event_broadcast`, `data_setvariableto`/`changevariableby`
- `sound_seteffectto`(PITCH 변주, 선택)

---

## 12. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과 / `project.json` JSON 로드 OK
2. targets 수: 6 (Stage, 광부, 후크, 줄, 아이템, 배너) — 줄 생략 시 5도 허용
3. Stage 글로벌 변수 14개 등록 / 아이템 sprite-local 변수 4개(내타입/내점수/내속도/잡혔나) 등록 / 리스트 0개
4. Broadcasts 등록: 게임시작/라운드시작/아이템배치/라운드끝/클리어연출/게임오버연출/아이템수거됨 (발사 포함 ~8개)
5. 후크 상태머신: forever 안에 `if 후크상태=0`(흔들림: phase 누적 + `후크각도=180+75*sin(phase)` + sin/cos 위치 계산 + 스페이스/클릭 → 후크상태1), `if 후크상태=1`(`change x/y by sin/cos(후크각도)*속도` + 화면끝→후크상태2), `if 후크상태=2`(point towards 광부 + move 잡힌속도 + distance<8 → 점수 가산 + 후크상태0) 세 분기 모두 존재
6. 후크각도 갱신이 `후크상태=0` 분기 안에만 존재(상태1·2에서 각도 고정) — 발사 방향 유지 확인
7. 아이템 클론 트리: 타입별 코스튬/내점수/내속도 분기 5개 + `if 후크상태=1 AND touching 후크 AND 잡힘플래그=0` → 잡힘플래그1·잡힌점수·잡힌속도 설정 + `if 잡혔나=1 → goto (x of 후크, y of 후크)` 존재
8. 무게별 되감기 속도 매핑 확인(금괴대 느림 ~3, 다이아 빠름 ~11, 빈손 12) + 타입별 점수(대200/중100/소50/돌20/다이아150)
9. Stage 라운드시작: `repeat 아이템수 { 배치X/Y/타입 랜덤 + broadcast 아이템배치 }` + 가중 랜덤 타입(1~5) 존재. 아이템수 8~10 범위
10. Stage 60초 타이머(`when 게임시작` forever: wait1 + 시간-1 + 시간≤0 → broadcast 라운드끝) 존재
11. 라운드끝 판정: 점수≥목표 → 라운드+1·목표+100·broadcast 라운드시작 / 미달 → 게임상태0·게임오버연출 분기 존재
12. 배너 sprite 코스튬 2개(clear/gameover) + 각 연출 방송 분기 존재
13. monitors: 점수·목표점수·시간·라운드 표시
14. 자산: SVG(bg/miner/hook/rope/gold_l/gold_m/gold_s/rock/diamond/clear/gameover) + WAV(최소 pop) MD5 일치
15. 블록 카운트 200~300 범위
16. (동작 검증) 흔들리는 후크 발사 → 직선 하강 → 금괴 닿으면 잡고 되감기(무거우면 느림) → 피벗 도착 시 점수 가산 + 후크 다시 흔들림 / 빗나가면 화면끝까지 갔다가 빈손 되감기 / 60초 내 목표 달성 → 다음 라운드(목표↑·재배치) / 미달 → 게임오버

---

## 13. 빌드 카운트 예상

- Stage: ~55 블록 (init + 라운드시작 배치 + 타이머 + 라운드끝 판정 + 가중랜덤)
- 후크: ~70 블록 (forever 3상태 분기 + sin/cos 위치 계산 + 발사/되감기)
- 줄: ~12 블록 (stretch forever) — 생략 시 0
- 아이템: ~75 블록 (타입 5분기 + 클론 forever + 충돌/따라오기 + 수거 삭제)
- 광부: ~8 블록
- 배너: ~16 블록 (clear/gameover 분기)
- **총합 예상: 220~280 블록** (★★★ — 진자 흔들림 + 발사/하강/되감기 3상태 + 무게별 속도 + 라운드/타이머. 클론·각도 계산이 핵심. 난이도 중상)

---

## 14. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (스페이스/클릭 1키 — "흔들릴 때 눌러서 후크 던지기" 즉시 이해)
- [x] 추상 학습 콘셉트 없음 (금괴=점수, 무거우면 천천히 — 일상 직관. 수학·과학 개념 매핑 없음. 각도/sin 은 내부 구현일 뿐 플레이어에게 노출 안 됨)
- [x] 즉시 이해되는 룰 (값나가는 금괴/다이아 노리고, 돌은 피하고, 시간 안에 목표 채우기)
- [x] 전략·도전감 (무거운 대형 금괴는 점수 크지만 되감기 느려 시간 소모 → "지금 큰 거? 빠른 작은 거?" 판단. 라운드 갈수록 목표↑)
- [x] 시각 보상(반짝이는 금괴·다이아) vs 함정(돌) 분리
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭). 라운드제로 점진적 도전
- [x] 골드 마이너 = 누구나 아는 클래식 — 검증된 재미 메커닉
