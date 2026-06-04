# 핑퐁 (pong) — Plan

> 좌측 패들을 위/아래 화살표로 움직여 공을 받아치고, 우측 AI 패들과 점수 대결을 한다. 공은 위/아래 벽에서 튕기고, 패들에 맞으면 X 방향이 반전된다. 패들의 어디에 맞느냐(중심으로부터의 거리)에 따라 공의 Y 속도가 바뀌어 각도를 조절할 수 있다. 랠리가 이어질수록 공이 조금씩 빨라진다. 공이 좌/우 벽 밖으로 나가면 반대편이 1점. 먼저 5점에 도달하면 승리/패배.
> 베이스: `games/car-race/build.py`(게임상태 broadcast + 깃발 재시작 + 게임오버 배너 패턴) + `games/apple-catch/build.py`(위/아래 화살표 한 축 이동 + 가장자리 clamp). **차이점**: 떨어지는 클론 풀이 없고, 공 1개가 매 틱 자기 dx/dy 로 움직이며 벽·패들과 물리 반사한다. AI 패들은 공의 Y 를 추적하되 최대 속도 제한이 있어 빠른 공을 놓칠 수 있다(=플레이어가 이길 수 있는 난이도). 점수는 클래식 양쪽 점수제(좌/우 각각).
> 1972 아타리 PONG 의 클래식 메커닉. 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지(MEMORY.md → feedback-game-design 준수).

---

## 1. 한 줄 룰

위/아래 화살표로 왼쪽 패들을 움직여 공을 받아친다. 오른쪽은 컴퓨터(AI)다. 공이 내 뒤(왼쪽 벽)로 나가면 컴퓨터 +1, 컴퓨터 뒤(오른쪽 벽)로 나가면 나 +1. 먼저 5점이면 승리.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 짙은 남색/검정 코트. 가운데 흰 점선 네트(세로). 위/아래 가장자리에 흰 경계선 2줄.
- **플레이 영역**: x -240..+240 / y -180..+180 전체. 위/아래 벽 반사선 y = ±165 (패들/공 코스튬 높이 고려). 좌/우 득점선 x = ±235.
- **좌 패들(플레이어)**: x = -210 고정, y 가변(-130..+130 clamp). 위/아래 화살표로 이동.
- **우 패들(AI)**: x = +210 고정, y 가변(-130..+130 clamp). 공 Y 추적.
- **점수 표시**: 무대 상단 중앙 양옆. 왼쪽 큰 숫자 = 내 점수, 오른쪽 큰 숫자 = 컴퓨터 점수. Scratch 변수 모니터(좌상단·우상단)로 표시.

```
+--------------------------------------------------+  y=+180
|  내점수: 2        :        컴퓨터: 1             |  ← 점수 모니터
| ------------------------------------------------ |  y=+165 (위 벽 반사선)
| |                  :                          |  |
| |                  :                  O ← 공   |  |
||L|                 :                       |R| |   ← L=좌패들(x-210) R=우패들(x+210)
| |                  :                          |  |
| |                  :                          |  |
| ------------------------------------------------ |  y=-165 (아래 벽 반사선)
+--------------------------------------------------+  y=-180
x=-240            네트(점선)                    x=+240
   좌 득점선 x=-235                       우 득점선 x=+235
```

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 + 라운드 진행(서브) + 승패 판정 | 게임시작/서브 broadcast 발신 |
| 1 | 좌패들 | 위/아래 화살표로 상하 이동, y clamp(-130..+130). x=-210 고정. | rotationStyle: don't rotate. 플레이어 조작 주체. |
| 2 | 우패들 | AI. 매 틱 공 Y 를 향해 이동하되 `AI속도`(최대 이동량) 만큼만. x=+210 고정, y clamp. | rotationStyle: don't rotate. 단일 인스턴스(클론 아님). |
| 3 | 공 | 1개. 매 틱 `공dx`/`공dy` 로 이동. 위/아래 벽 반사, 양 패들 반사(X 반전 + 충돌 위치로 Y 조절 + 속도 ramp), 좌/우 득점선 통과 시 득점 처리 후 서브. | costume "ball". 단일 인스턴스. 충돌·물리 판정 주체. |
| 4 | 결과 배너 | "YOU WIN!" / "YOU LOSE" 배너. 평소 숨김. 게임상태=0 일 때만 보임. | car-race 게임오버 배너 패턴. 승/패 코스튬 2개. |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 내점수 | `varPScore01` | 0 | 플레이어(좌) 점수 |
| 컴점수 | `varAScore02` | 0 | AI(우) 점수 |
| 게임상태 | `varState03` | 1 | 1=플레이(랠리 진행), 0=게임 종료(승/패 결정) |
| 목표점수 | `varTarget04` | 5 | 먼저 도달 시 승리하는 점수 |
| 공dx | `varBallDX05` | 4 | 공의 x 속도(틱당 이동량). 음수=왼쪽, 양수=오른쪽 |
| 공dy | `varBallDY06` | 2 | 공의 y 속도(틱당 이동량). 음수=아래, 양수=위 |
| 공속도 | `varBallSpd07` | 4.5 | 공의 현재 전체 속력(랠리마다 ramp). dx/dy 재계산 기준 |
| 서브방향 | `varServe08` | -1 | 다음 서브 시 공이 향하는 x 방향. -1=왼쪽(내 쪽으로), +1=오른쪽(컴퓨터 쪽으로). 득점한 쪽의 반대로 서브 |
| AI속도 | `varAISpeed09` | 4 | 우 패들이 한 틱에 움직일 수 있는 최대 거리. 작을수록 약함(공 놓침) |
| 패들반높이 | `varPadHalf10` | 35 | 패들 코스튬 높이의 절반. 충돌 위치 정규화(중심 거리/반높이)에 사용 |
| 결과 | `varResult11` | 0 | 0=진행중, 1=플레이어 승, 2=AI 승. 결과 배너가 코스튬 선택에 사용 |

좌패들 sprite-local: 없음.

우패들 sprite-local: 없음 (글로벌 `AI속도` 만 읽고, 자기 y position 으로 추적).

공 sprite-local: 없음 (모든 물리 변수는 글로벌. 다른 sprite 가 디버깅용으로 읽을 수 있게).

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 서브 | `brServe02` | 게임시작 시 1회 + 한쪽이 득점할 때마다 발신 → 공이 가운데로 복귀 후 잠깐 멈췄다가 `서브방향` 으로 출발 |
| 득점 | `brGoal03` | 공이 좌/우 득점선 밖으로 나갈 때 발신 → Stage 가 점수 갱신 + 승패 판정. (공 sprite 가 직접 점수 변수를 올려도 되지만, 판정 로직은 Stage 에 모으기 위해 broadcast) |

> 단순화 옵션: 공 sprite 가 득점 시 직접 `내점수`/`컴점수` 를 올리고 `broadcast 서브` 만 쏴도 된다. 그 경우 `득점` broadcast 는 생략 가능. 빌더 재량(아래 7.4 본문은 공이 직접 점수 올림 + Stage 가 승패 판정 watcher 로 구성).

---

## 6. 씬 / 상태머신

```
[깃발] → init(점수 0/0, 게임상태 1, 결과 0, 공속도 4.5, AI속도 4) → broadcast 게임시작
   │
   ├─ broadcast 서브 (첫 서브)
   ▼
[랠리 진행 게임상태=1]
   - 좌패들: 화살표 상하 이동
   - 우패들: 공 Y 추적(AI속도 제한)
   - 공: 매 틱 이동 → 벽 반사 / 패들 반사(속도 ramp) / 득점선 통과 시 득점+서브
   - 매 득점 후: 승패 판정 watcher 가 (내점수≥목표 또는 컴점수≥목표) 검사
   ▼ (한쪽이 목표점수 도달)
[게임 종료 게임상태=0]
   - 결과 ← 1(플레이어 승) 또는 2(AI 승)
   - 결과 배너 show (승/패 코스튬)
   - 공·패들 정지
   ▼ [깃발 재클릭] → 처음으로
```

---

## 7. 메커닉 상세

### 7.1 좌 패들 (플레이어)

x=-210 고정. 위/아래 화살표로 상하 이동. apple-catch 의 한 축 이동 + clamp 패턴.

```
when receive 게임시작:
  set x to -210
  set y to 0
  repeat until 게임상태 = 0:
    if key ↑:  change y by 6
    if key ↓:  change y by -6
    # 화면 밖 방지 clamp (패들 중심 -130..+130)
    if y position > 130:  set y to 130
    if y position < -130: set y to -130
    set x to -210            # x 고정(혹시 흔들림 방지)
    wait 0.016
```

> 이동량 6 은 부드러운 조작. 키를 누르고 있으면 계속 이동(에지 입력 아님 — 패들은 연속 이동이 자연스러움).

### 7.2 우 패들 (AI) — **이길 수 있게 만드는 핵심**

공의 Y 를 향해 이동하되, 한 틱에 `AI속도`(=4) 이상은 못 움직인다. 공이 빠르거나 급격히 각도가 바뀌면 따라가지 못해 놓친다. → 플레이어가 이길 수 있는 난이도.

```
when receive 게임시작:
  set x to 210
  set y to 0
  repeat until 게임상태 = 0:
    # 공 Y 와 내 Y 의 차이만큼 따라가되 AI속도로 clamp
    차 = (공의 y position) - (내 y position)
    if 차 > AI속도:   change y by AI속도
    else if 차 < (-1 * AI속도): change y by (-1 * AI속도)
    else:            change y by 차       # 거의 다 따라왔으면 정확히 맞춤
    # clamp
    if y position > 130:  set y to 130
    if y position < -130: set y to -130
    set x to 210
    wait 0.016
```

> **난이도 조절 레버**: `AI속도` 를 4 로 두면 공의 평균 X 속도(4.5)보다 살짝 느려 플레이어가 빠른 각으로 받아치면 AI 가 놓친다. 너무 쉬우면 5, 너무 어려우면 3 으로. (MVP: 4 고정. 라운드가 길어지면 약간 올리는 ramp 는 선택.)
> 공의 y position 을 읽을 때는 `sensing_of`(공 sprite 의 "y position") 블록 사용. zombie-shooter/dogfight 의 적 AI 가 플레이어 위치를 `sensing_of` 로 읽는 패턴과 동일.

### 7.3 공 — 물리 (벽 반사 + 패들 반사 + 속도 ramp) — **핵심 메커닉**

공은 매 틱 `change x by 공dx` / `change y by 공dy`. 그 후 반사·득점 검사.

```
when receive 서브:
  # 공을 가운데로 복귀, 잠깐 멈춤 후 출발
  set x to 0
  set y to 0
  공속도 ← 4.5                       # 새 랠리 시작 시 속도 초기화
  공dx ← 서브방향 * 4                 # 좌(-)/우(+) 로 출발
  공dy ← (pick random -2 to 2)        # 약간의 무작위 세로 각
  wait 0.6                            # 서브 전 정지(플레이어 준비 시간)

when receive 게임시작:
  show
  repeat until 게임상태 = 0:
    change x by 공dx
    change y by 공dy

    # (1) 위/아래 벽 반사
    if (y position > 165) OR (y position < -165):
      공dy ← 공dy * -1
      # 벽 안으로 살짝 밀어넣기(끼임 방지)
      if y position > 165:  set y to 165
      if y position < -165: set y to -165

    # (2) 좌 패들 반사 (공이 왼쪽으로 가는 중 + 패들에 닿음)
    if (touching 좌패들) AND (공dx < 0):
      공속도 ← 공속도 + 0.4                       # 랠리 ramp
      # 충돌 위치 정규화: 패들 중심 기준 -1..+1
      오프셋 ← ((y position) - (좌패들의 y position)) / 패들반높이
      공dx ← 공속도                                # 오른쪽으로 반전(양수)
      공dy ← 오프셋 * 공속도                        # 위쪽 맞으면 위로, 아래쪽 맞으면 아래로
      set x to -200                               # 패들 앞으로 빼서 재충돌 방지

    # (3) 우 패들 반사 (공이 오른쪽으로 가는 중 + 패들에 닿음)
    if (touching 우패들) AND (공dx > 0):
      공속도 ← 공속도 + 0.4
      오프셋 ← ((y position) - (우패들의 y position)) / 패들반높이
      공dx ← -1 * 공속도                           # 왼쪽으로 반전(음수)
      공dy ← 오프셋 * 공속도
      set x to 200

    # (4) 득점: 좌 득점선 밖 → 컴퓨터 +1, 우 득점선 밖 → 플레이어 +1
    if (x position < -235):
      컴점수 ← 컴점수 + 1
      서브방향 ← 1            # 득점당한 쪽(플레이어)을 향해? → PONG 관례: 득점한 쪽이 상대에게 서브
      broadcast 서브
    if (x position > 235):
      내점수 ← 내점수 + 1
      서브방향 ← -1
      broadcast 서브

    wait 0.016
```

> **각도 컨트롤 직관**: 패들 중앙에 맞으면 `오프셋≈0` → 공이 거의 수평으로 곧게. 패들 위쪽 끝에 맞으면 `오프셋≈+1` → 공이 위로 가파르게. 아래쪽 끝이면 아래로. 플레이어가 패들 위치를 조절해 받아치는 각을 만든다 — PONG 의 핵심 손맛.
> **속도 ramp**: 패들에 맞을 때마다 `공속도 += 0.4`. dx/dy 가 `공속도` 기준으로 재계산되므로 랠리가 길수록 빨라진다. 서브 시 4.5 로 리셋해 무한 가속 방지.
> **오프셋/dx/dy 계산용 임시 변수**: `오프셋`(`varOff12`) 글로벌 임시 1개 추가. (sprite-local 로 둬도 무방.)
> **서브방향 관례**: 위 코드는 "득점한 쪽이 상대 코트로 서브" (좌 득점선 통과=컴퓨터 득점 → 다음 공은 오른쪽으로=서브방향+1). 단순화하려면 "항상 직전에 진 쪽으로 서브" 등 어느 쪽이든 일관되면 OK.

### 7.4 득점 / 승패 판정 (Stage watcher)

```
when receive 게임시작:   # 승패 판정 watcher
  repeat until (내점수 ≥ 목표점수) OR (컴점수 ≥ 목표점수):
    wait 0.05
  # 한쪽이 목표 도달
  if 내점수 ≥ 목표점수:  결과 ← 1     # 플레이어 승
  else:                 결과 ← 2     # AI 승
  게임상태 ← 0                       # 모든 forever 정지
```

> 공 sprite 가 득점 시 점수 변수를 직접 올리고, Stage 의 이 watcher 가 목표 도달을 감시 → 게임상태=0 으로 전환. car-race 의 게임상태 전환 패턴과 동일(거기선 충돌, 여기선 점수).

### 7.5 결과 배너 / 재시작

```
when receive 게임시작:
  hide

when flag clicked:
  hide
  goto 0, 0
  size 100
  go to front
  wait until 게임상태 = 0
  if 결과 = 1:  switch costume "win"
  else:         switch costume "lose"
  show
  play sound win_or_lose   # 선택
```

깃발 재클릭 → 모든 변수 리셋(내점수0/컴점수0/게임상태1/결과0/공속도4.5) → 새 게임. Scratch 깃발 클릭이 모든 클론을 지우지만 이 게임은 클론을 쓰지 않으므로 추가 정리 불필요.

---

## 8. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  내점수 ← 0
  컴점수 ← 0
  게임상태 ← 1
  결과 ← 0
  목표점수 ← 5
  공속도 ← 4.5
  AI속도 ← 4
  패들반높이 ← 35
  서브방향 ← -1
  broadcast 게임시작
  broadcast 서브            # 첫 서브

when receive 게임시작:      # 승패 판정 watcher
  repeat until (내점수 ≥ 목표점수) OR (컴점수 ≥ 목표점수):
    wait 0.05
  if 내점수 ≥ 목표점수: 결과 ← 1
  else: 결과 ← 2
  게임상태 ← 0
```

### 좌패들 (플레이어)

```
when flag clicked:
  size 100
  point in direction 90
  show

when receive 게임시작:
  set x to -210
  set y to 0
  repeat until 게임상태 = 0:
    if key ↑:  change y by 6
    if key ↓:  change y by -6
    if y position > 130:  set y to 130
    if y position < -130: set y to -130
    set x to -210
    wait 0.016
```

### 우패들 (AI)

```
when flag clicked:
  size 100
  point in direction 90
  show

when receive 게임시작:
  set x to 210
  set y to 0
  repeat until 게임상태 = 0:
    오프셋 ← ([y position] of 공) - (y position)      # 임시로 오프셋 변수 재사용 또는 인라인 계산
    if 오프셋 > AI속도:        change y by AI속도
    if 오프셋 < (-1*AI속도):   change y by (-1*AI속도)
    if (오프셋 ≤ AI속도) AND (오프셋 ≥ -1*AI속도): change y by 오프셋
    if y position > 130:  set y to 130
    if y position < -130: set y to -130
    set x to 210
    wait 0.016
```

> 우패들의 추적 차이 계산에 `오프셋` 글로벌을 공의 반사 계산과 공유하면 타이밍 충돌 위험이 있으니, **AI 추적용은 인라인 `( [y position] of 공 - y position )` 식을 if 조건마다 직접** 쓰거나 별도 임시 변수 `AI차`(`varAIdiff13`)를 두는 것을 권장. 빌더 재량.

### 공

```
when flag clicked:
  size 100
  switch costume "ball"
  show

when receive 서브:
  set x to 0
  set y to 0
  공속도 ← 4.5
  공dx ← 서브방향 * 4
  공dy ← pick random -2 to 2
  wait 0.6

when receive 게임시작:
  show
  repeat until 게임상태 = 0:
    change x by 공dx
    change y by 공dy
    if (y position > 165) OR (y position < -165):
      공dy ← 공dy * -1
      if y position > 165:  set y to 165
      if y position < -165: set y to -165
    if (touching 좌패들) AND (공dx < 0):
      공속도 ← 공속도 + 0.4
      오프셋 ← (y position - [y position] of 좌패들) / 패들반높이
      공dx ← 공속도
      공dy ← 오프셋 * 공속도
      set x to -200
      play sound bounce
    if (touching 우패들) AND (공dx > 0):
      공속도 ← 공속도 + 0.4
      오프셋 ← (y position - [y position] of 우패들) / 패들반높이
      공dx ← -1 * 공속도
      공dy ← 오프셋 * 공속도
      set x to 200
      play sound bounce
    if (x position < -235):
      컴점수 ← 컴점수 + 1
      서브방향 ← 1
      play sound score
      broadcast 서브
    if (x position > 235):
      내점수 ← 내점수 + 1
      서브방향 ← -1
      play sound score
      broadcast 서브
    wait 0.016
```

### 결과 배너

```
when flag clicked:
  hide
  goto 0, 0
  size 100
  go to front
  wait until 게임상태 = 0
  if 결과 = 1:  switch costume "win"
  else:         switch costume "lose"
  show
```

---

## 9. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| 배경 | SVG (인라인) | 480×360. 짙은 남색/검정 코트 + 가운데 흰 세로 점선 네트 + 위/아래 흰 경계선 2줄 |
| 좌패들 | SVG (인라인) | 약 14×70. 흰/하늘색 둥근 세로 막대. rotationCenter 중앙. 높이 70 → 반높이 35(=패들반높이) |
| 우패들 | SVG (인라인) | 약 14×70. 흰/주황 둥근 세로 막대(AI 구분 색). 높이 70 |
| ball | SVG (인라인) | 약 18×18. 흰 원(또는 노란 원) |
| win | SVG (인라인) | 결과 배너 코스튬 1: "YOU WIN!" 초록 배너 |
| lose | SVG (인라인) | 결과 배너 코스튬 2: "YOU LOSE" 빨강 배너 |
| bounce.wav | WAV (assets/) | 패들/벽 튕김 효과음. car-race/assets 의 짧은 효과음 복사 또는 pop.wav 재사용 |
| score.wav | WAV (assets/) | 득점 효과음 (선택, pop.wav 재사용 가능) |

> 패들 높이 70 ↔ `패들반높이=35` 가 정확히 맞아야 오프셋 정규화(-1..+1)가 패들 끝에서 ±1 이 된다. SVG 높이를 바꾸면 `패들반높이` 도 같이 조정.
> 결과 배너는 코스튬 2개(win/lose)를 한 sprite 에 넣고 `결과` 값으로 전환. car-race 게임오버 배너(단일 코스튬)에서 코스튬 1개 추가한 형태.

assets/ 폴더: `bounce.wav`(+선택 `score.wav`). 나머지 SVG 는 build.py 인라인.

---

## 10. 변수/리스트/메시지 요약 (ID 컨벤션)

- 글로벌 변수 11개: `varPScore01`(내점수) `varAScore02`(컴점수) `varState03`(게임상태) `varTarget04`(목표점수) `varBallDX05`(공dx) `varBallDY06`(공dy) `varBallSpd07`(공속도) `varServe08`(서브방향) `varAISpeed09`(AI속도) `varPadHalf10`(패들반높이) `varResult11`(결과)
- 추가 글로벌 임시: `varOff12`(오프셋 — 패들 반사 각 계산), 선택 `varAIdiff13`(AI차 — AI 추적 계산용)
- 리스트: 없음
- broadcasts 3개: `brStart01`(게임시작) `brServe02`(서브) `brGoal03`(득점, 선택 — 본문은 공이 직접 점수 올림 방식이라 미사용 가능)
- 모니터: `내점수`(좌상단), `컴점수`(우상단) 2개 표시

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **게임상태 broadcast + 깃발 재시작 + 결과 배너**: `games/car-race/build.py` — 게임상태 1/0 전환, 배너 sprite 의 `wait until 게임상태=0 → show`. 여기선 배너에 win/lose 코스튬 2개 + `결과` 분기 추가.
- **한 축(상하) 이동 + 가장자리 clamp**: `games/apple-catch/build.py`(바구니 좌우 이동·clamp)의 축을 좌우→상하로 바꾼 것. 좌패들이 그대로 이 패턴.
- **`sensing_of`(다른 sprite 의 y position) 읽기**: `games/zombie-shooter/build.py` / `games/dogfight/build.py` 의 적 AI 가 플레이어 좌표를 읽는 패턴. 우패들 AI 추적 + 공 반사의 패들 y 읽기에 사용.
- **`touching` 충돌 판정**: `games/car-race/build.py`(내차 touching 적차). 여기선 공 sprite 가 `touching 좌패들`/`touching 우패들`.
- **단일 sprite 매 틱 forever 이동(클론 없음)**: 공·패들 모두 클론 풀이 없는 단순 forever. car-race 보다 단순(클론 opcode 불필요).

빌더는 car-race 의 build.py 를 베이스로: (1) 적차/페인트라인 클론 풀 제거, (2) 내차→좌패들(상하 이동), (3) 우패들 sprite 신규(AI 추적, `sensing_of` 공 y), (4) 공 sprite 신규(매 틱 dx/dy 이동 + 벽/패들 반사 + 득점), (5) Stage 에 승패 watcher + 첫 서브 broadcast, (6) 게임오버 배너→결과 배너(win/lose 코스튬 2개).

**필요한 블록 opcode (car-race 대비 추가/확인)**:
- `sensing_of` (PROPERTY="y position", OBJECT=공/좌패들/우패들) — 다른 sprite 좌표 읽기
- `operator_divide` (오프셋 정규화 `/패들반높이`)
- `operator_random` (서브 dy 무작위)
- 나머지(`motion_changexby`/`changeyby`/`setx`/`sety`, `sensing_touchingobject`, `operator_gt/lt/and/or/multiply/subtract`, `data_setvariableto`, `control_repeat_until`, `event_broadcast`)는 car-race 에 이미 존재.

---

## 12. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과 / `project.json` JSON 로드 OK
2. targets 수: 5 (Stage, 좌패들, 우패들, 공, 결과 배너)
3. Stage 변수 11개(내점수/컴점수/게임상태/목표점수/공dx/공dy/공속도/서브방향/AI속도/패들반높이/결과) + 임시(오프셋) 등록
4. Broadcasts: 게임시작 / 서브 (+선택 득점) 등록
5. 좌패들 `when receive 게임시작` forever 에 ↑/↓ `sensing_keypressed` 2개 + `motion_changeyby`(±6) + y clamp(130/-130) 존재
6. 우패들 forever 에 `sensing_of`("y position", 공) 추적 + `AI속도` 로 이동량 제한(`operator_gt`/`operator_lt` 분기) + y clamp 존재
7. 공 `when receive 게임시작` forever 에:
   - `motion_changexby`(공dx) + `motion_changeyby`(공dy) 매 틱 이동
   - 위/아래 벽 반사(`공dy ← 공dy * -1`, y>165 / y<-165 조건) 존재
   - 좌패들 반사: `sensing_touchingobject`("좌패들") AND `공dx<0` → `공dx ← 공속도`(양수 반전) + 오프셋 기반 `공dy` 존재
   - 우패들 반사: `touching 우패들` AND `공dx>0` → `공dx ← -공속도`(음수 반전) + 오프셋 기반 `공dy` 존재
   - 속도 ramp: 패들 반사 시 `공속도 ← 공속도 + 0.4` 존재
   - 득점: x<-235 → 컴점수+1, x>235 → 내점수+1, 각각 `broadcast 서브` 존재
8. 공 `when receive 서브` 에 가운데 복귀(x0/y0) + `공dx ← 서브방향*4` + 무작위 `공dy`(`operator_random`) + 출발 전 `wait` 존재
9. 오프셋 정규화에 `operator_divide`(.../패들반높이) 존재
10. Stage 승패 watcher: `repeat until (내점수≥목표 OR 컴점수≥목표)` + `결과` 1/2 분기 + `게임상태 ← 0` 존재
11. 결과 배너 sprite 코스튬 2개(win/lose) + `결과` 값으로 코스튬 분기 후 show 존재
12. monitors: 내점수·컴점수 표시
13. 자산 6 SVG(배경/좌패들/우패들/ball/win/lose) + WAV(bounce, 선택 score), MD5 일치
14. 블록 카운트 130~210 범위
15. (동작 검증) AI속도(4) < 평균 공 X속도 → 플레이어가 각을 주면 AI 가 놓칠 수 있음(이길 수 있는 난이도). 공이 패들/벽에 끼지 않음(반사 후 `set x` 밀어내기). 5점 도달 시 게임 종료 + 배너 표시.

---

## 13. 빌드 카운트 예상

- Stage: ~25 블록 (init + 첫 서브 + 승패 watcher)
- 좌패들: ~20 블록 (상하 이동 + clamp)
- 우패들: ~25 블록 (AI 추적 분기 + clamp + sensing_of)
- 공: ~75 블록 (이동 + 벽 반사 + 좌/우 패들 반사 각 계산 + 득점 2 + 서브)
- 결과 배너: ~12 블록 (win/lose 코스튬 분기)
- **총합 예상: 140~190 블록** (★★★ 범위 — 물리 반사·각도 계산이 난이도 핵심이나 클론·리스트가 없어 중간 난이도)

---

## 14. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (위/아래 두 버튼으로 패들 조작 — 즉시 이해)
- [x] 추상 학습 콘셉트 없음 (패들=패들, 공=공. 수학·과학 개념 매핑 없음. 각도 컨트롤은 "어디에 맞히느냐" 손맛이지 학습 강요 아님)
- [x] 즉시 이해되는 룰 (받아치면 계속, 놓치면 상대 점수, 먼저 5점 승리)
- [x] 도전감 (랠리가 길수록 공이 빨라짐) + AI 가 이길 수 있을 만큼만 강함(AI속도 제한)
- [x] 1대1 대전의 긴장감 (점수 0~5 의 짧은 세트)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
- [x] 1972 아타리 PONG 클래식 — 검증된 재미 메커닉
</content>
</invoke>
