# 스네이크 (snake) — Plan

> 방향키로 16px 격자 위를 움직이는 뱀을 조종해 사과를 먹는다. 사과를 먹을 때마다 꼬리가 한 칸씩 길어진다. 벽 또는 자기 몸(꼬리)에 부딪히면 게임오버. 1976 아케이드 Blockade / Nokia "Snake" 의 클래식 메커닉.
> 베이스: `games/car-race/build.py` (격자/차선 스냅 이동 + 키 에지 입력 `wait until NOT key` + 클론 풀 + 게임상태 broadcast 패턴) + `games/flappy-bird/build.py` (이벤트 기반 점수 +1, 게임오버 배너). **차이점**: (1) 자유 이동·낙하가 아니라 **고정 시간격(스텝)으로 한 칸씩 격자 점프 이동** + 4방향 회전. (2) 꼬리는 **머리가 지나온 좌표를 리스트(`궤적X`/`궤적Y`)에 기록**하고, 꼬리 세그먼트 클론이 자기 순번만큼 **지연된 과거 좌표**를 읽어 따라간다. (3) 자기충돌은 머리가 꼬리 세그먼트 클론에 `touching` 으로 판정.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지(MEMORY.md → feedback-game-design 준수).

---

## 1. 한 줄 룰

방향키로 뱀을 한 칸씩 움직여 사과를 먹는다. 사과를 먹으면 꼬리가 한 칸 길어지고 점수 +1. 벽이나 자기 꼬리에 닿으면 게임오버.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- **격자(grid)**: 한 칸 = 16px. 플레이 영역은 28칸(가로) × 20칸(세로) = 448×320px 중앙 보드.
  - 보드 x 범위: -224 .. +224 (칸 중심은 -216, -200, ..., +216 — 즉 16px 간격, 28개).
  - 보드 y 범위: -160 .. +160 (칸 중심은 -152, ..., +152 — 16px 간격, 20개).
  - **좌표 스냅 규칙**: 머리는 항상 16의 배수 + 8 격자 중심에 위치. 칸 중심 x = `colIndex*16 - 216` (colIndex 0..27), y = `rowIndex*16 - 152` (rowIndex 0..19). 빌더는 colIndex/rowIndex 를 직접 쓸 필요 없이, **이동은 항상 `change x/y by ±16`** 로 처리하면 자동으로 격자에 머문다 (시작점이 격자 중심이면 ±16 의 누적도 항상 격자 중심).
- 배경: 짙은 녹색 체크무늬 보드(밝은/어두운 녹색 16px 타일 번갈아) + 보드 둘레 두꺼운 갈색 벽 테두리. 벽 판정은 좌표로 한다(아래 6.1).
- 머리/꼬리: 한 칸(16×16)에 딱 맞는 사각 둥근 몸통. 사과도 16×16.
- 모니터 좌상단: 점수 / 최고기록 / 길이.

```
+--------------------------------------------------+  y=+180
| ## WALL ######################################## |
| #                                              # |  점수: 5
| #        [사과]                                 # |  최고: 12
| #                                              # |  길이: 6
| #        OOO@   ← @=머리, O=꼬리                # |
| #                                              # |
| #                                              # |
| ## WALL ######################################## |
+--------------------------------------------------+  y=-180
x=-240                                          x=+240
   보드 내부: x -224..+224 / y -160..+160 (16px 격자)
```

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 + 스텝 타이머(일정 간격마다 머리 1칸 전진 트리거) + 난이도(스텝 간격 단축) | 게임시작/스텝 broadcast 발신 |
| 1 | 머리 | 방향키로 진행 방향 변경(역방향 금지). 매 스텝마다 현재 방향으로 1칸(±16) 이동. 이동 직후 자기 좌표를 `궤적X`/`궤적Y` 리스트 맨 앞에 기록. 벽/꼬리 충돌 시 게임상태=0. 사과 접촉 시 길이+1·점수+1·사과 재배치. | rotationStyle: don't rotate (코스튬으로 방향 표현하거나 단일 코스튬). 충돌 판정 주체. |
| 2 | 꼬리 | `길이` 만큼의 클론 풀. 각 클론은 자기 순번 `세그번호`(1..길이) 를 가지고, 매 스텝마다 `궤적` 리스트의 `(세그번호*간격)` 번째 과거 좌표로 점프 → 머리를 따라 줄줄이 이동. | sprite-local 변수 `세그번호`. 머리의 자기충돌 대상. |
| 3 | 사과 | 빈 격자 칸 무작위 위치에 1개. 머리가 먹으면 새 위치로 재배치(머리/꼬리와 겹치지 않게 재추첨). | costume "apple". 단일 인스턴스(클론 아님). |
| 4 | 게임오버 | "GAME OVER" 배너. 평소 숨김. 게임상태=0 일 때만 보임. | car-race/flappy-bird 패턴 그대로. |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 먹은 사과 수 |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| 길이 | `varLen04` | 3 | 현재 꼬리 세그먼트 개수 (시작 3) |
| 방향 | `varDir05` | 1 | 현재 진행 방향. 1=오른쪽, 2=위, 3=왼쪽, 4=아래 |
| 다음방향 | `varNextDir06` | 1 | 입력으로 예약된 다음 스텝의 방향. 스텝 직전에 `방향 ← 다음방향` (1스텝 1회전 보장 + 역방향 차단) |
| 스텝간격 | `varStep07` | 0.18 | 머리가 1칸 전진하는 주기(초). 작을수록 빠름 |
| 사과X | `varAppleX08` | 0 | 사과 격자 중심 x |
| 사과Y | `varAppleY09` | 0 | 사과 격자 중심 y |
| 머리X | `varHeadX10` | -24 | 머리 현재 x (꼬리/사과가 참조) |
| 머리Y | `varHeadY11` | 0 | 머리 현재 y |
| 기록간격 | `varGap12` | 1 | 궤적 리스트에서 세그먼트 간 인덱스 간격(=1). "한 칸 = 리스트 한 항목" 으로 단순화 |

머리 sprite-local 변수: 없음 (위 글로벌만 읽고 씀).

꼬리 sprite-local 변수:

| 변수명 | ID | 용도 |
|--------|----|------|
| 세그번호 | `varSeg13` | 클론 생성 시 1..길이 부여. 궤적 리스트의 `세그번호` 번째 항목을 읽어 위치. 1=머리 바로 뒤 |

사과 sprite-local 변수: 없음.

---

## 5. 리스트 (Stage 글로벌)

| 리스트명 | ID | 용도 |
|----------|----|------|
| 궤적X | `L_trailX01` | 머리가 매 스텝 지나온 x 좌표 기록. 항상 **맨 앞(index 1)에 insert** → index 1 = 가장 최근 머리 위치, index n = n스텝 전 위치 |
| 궤적Y | `L_trailY02` | 위와 동일하게 y 좌표 기록 |

> 리스트 길이 관리: 매 스텝 머리가 `insert (머리X) at 1 of 궤적X` 한 뒤, 리스트 길이가 `길이 + 5` 를 넘으면 맨 끝 항목을 `delete (last) of 궤적X` 로 잘라 무한 증가를 막는다. (+5 여유는 꼬리가 길어질 때 과거 좌표가 부족하지 않게 하는 버퍼.)
> 꼬리 세그번호 k 인 클론은 매 스텝 `item (k) of 궤적X / 궤적Y` 로 점프 → 머리보다 k스텝 뒤의 위치를 따라간다. 이것이 "꼬리가 머리가 지나온 길을 그대로 따라가는" 스네이크의 핵심.

---

## 6. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 스텝 | `brStep02` | Stage 가 매 `스텝간격` 초마다 발신 → 머리 1칸 전진 + 꼬리 갱신. **머리와 꼬리 모두 수신**. 순서 보장을 위해 머리가 먼저 좌표를 기록한 뒤 꼬리가 읽도록, 머리는 스텝 수신 즉시 처리하고 꼬리는 같은 broadcast 를 받되 머리 처리 후 값을 읽는다(아래 6.4 순서 노트 참조) |
| 사과배치 | `brPlaceApple03` | 게임시작 시 1회 + 머리가 사과를 먹을 때마다 발신 → 사과 재배치 |

---

## 7. 메커닉 상세

### 7.1 머리 (격자 스텝 이동 + 입력 + 충돌)

**입력(매 틱, 빠른 forever — 스텝과 별개)**: 방향키를 눌렀을 때 `다음방향` 만 예약한다. 실제 이동은 스텝에서만. 역방향 금지(예: 현재 오른쪽이면 왼쪽 입력 무시).

```
when receive 게임시작:   # 입력 예약 forever (틱 0.02s)
  repeat until 게임상태 = 0:
    if key → AND 방향 ≠ 3:  다음방향 ← 1
    if key ↑ AND 방향 ≠ 4:  다음방향 ← 2
    if key ← AND 방향 ≠ 1:  다음방향 ← 3
    if key ↓ AND 방향 ≠ 2:  다음방향 ← 4
    wait 0.02
```

> 역방향 차단 조건: 새 방향이 현재 `방향` 의 정반대일 때 무시. 반대 쌍: 1↔3(좌우), 2↔4(상하). 위 코드의 `방향 ≠ 반대값` 가드가 그 역할.

**스텝 처리(스텝 broadcast 수신, 1칸 전진)**:

```
when receive 스텝:
  방향 ← 다음방향                  # 예약된 회전 1회 적용
  # 1칸 전진
  if 방향 = 1: change x by 16
  if 방향 = 2: change y by 16
  if 방향 = 3: change x by -16
  if 방향 = 4: change y by -16
  머리X ← x position
  머리Y ← y position
  # 벽 충돌: 보드 밖이면 게임오버
  if (머리X > 224) OR (머리X < -224) OR (머리Y > 160) OR (머리Y < -160):
    게임상태 ← 0
  # 자기충돌: 꼬리 세그먼트에 닿으면 게임오버
  if touching 꼬리:
    게임상태 ← 0
  # 궤적 기록 (맨 앞 insert)
  insert (머리X) at 1 of 궤적X
  insert (머리Y) at 1 of 궤적Y
  # 버퍼 트림
  repeat until (length of 궤적X) ≤ (길이 + 5):
    delete (last) of 궤적X
    delete (last) of 궤적Y
  # 사과 먹기
  if (머리X = 사과X) AND (머리Y = 사과Y):
    점수 ← 점수 + 1
    길이 ← 길이 + 1
    if 점수 > 최고기록: 최고기록 ← 점수
    broadcast 사과배치
    create clone of 꼬리   # 늘어난 길이만큼 세그먼트 1개 추가 → 꼬리 sprite 가 처리
```

> **충돌 판정 타이밍 주의**: `touching 꼬리` 는 머리가 새 칸으로 이동한 직후, 그 칸에 꼬리 세그먼트가 있을 때 참이 된다. 꼬리는 같은 스텝에서 머리 뒤 위치로 움직이므로, "머리가 막 떠난 칸(=세그번호 1)" 과의 자기겹침 오판을 막기 위해 **꼬리 세그번호 1 클론은 충돌 무시 처리**가 필요할 수 있음 → 더 단순하게: 머리가 먼저 이동·기록한 뒤 꼬리가 이동하므로, 꼬리 세그번호 1은 "직전 머리 위치(궤적 index 2)"에 서고 새 머리 칸과 겹치지 않는다. (아래 6.4 인덱스 설계로 자연 해소.)

### 7.2 스텝 타이머 (Stage)

```
when receive 게임시작:   # 스텝 발생 forever
  repeat until 게임상태 = 0:
    broadcast 스텝
    wait 스텝간격

when receive 게임시작:   # 난이도 ramp: 5칸 먹을 때마다 빨라짐
  repeat until 게임상태 = 0:
    wait 0.05
    # 점수 기반 스텝간격 단축 (하한 0.07)
    if (점수 ≥ 5) AND (스텝간격 > 0.07):
      스텝간격 ← 0.18 - (점수 * 0.008)   # 점수 ↑ → 간격 ↓ (대략적, 하한 clamp)
      if 스텝간격 < 0.07: 스텝간격 ← 0.07
```

> ramp 는 선택적. MVP 는 스텝간격 고정 0.18 로 두고, ramp 핸들러는 추가 재미 요소. 빌더는 위 한 줄 공식으로 충분.

### 7.3 사과 (재배치)

```
when receive 사과배치:
  repeat until (사과가 빈 칸에 놓임):
    c = pick random 0 to 27          # colIndex
    r = pick random 0 to 19          # rowIndex
    사과X ← c * 16 - 216
    사과Y ← r * 16 - 152
    goto (사과X, 사과Y)
    # 머리/꼬리와 겹치면 다시 추첨
    if NOT (touching 머리) AND NOT (touching 꼬리):
      stop this script   # 빈 칸 찾음 → 종료
  # (repeat until 형태로 빈 칸 찾을 때까지 반복)
```

> 구현 단순화: `repeat until (NOT touching 머리 AND NOT touching 꼬리)` 형태의 do-while 로 빈 칸을 찾는다. 격자 칸 수(560)가 꼬리보다 훨씬 많아 보통 1~2회 추첨에 성공.

### 7.4 꼬리 (궤적 추종 클론) — **핵심 메커닉**

**클론 풀 구성**: 게임시작 시 `길이`(=3) 개의 클론을 만들고, 사과를 먹어 `길이`가 늘 때마다 머리가 `create clone of 꼬리` 로 1개 추가. 각 클론은 생성 순서대로 `세그번호` 를 1씩 증가시켜 부여한다.

```
when flag clicked:
  hide

when receive 게임시작:
  # 본체는 숨김. 세그번호 발급용 카운터를 위해 글로벌 임시 안 쓰고
  # 길이만큼 클론을 순차 생성하며 세그번호 부여
  hide
  delete all of 궤적X
  delete all of 궤적Y
  # 시작 궤적 시드: 머리 시작 위치를 길이+5 만큼 미리 채움(꼬리가 첫 스텝에 읽을 과거 좌표 확보)
  set i ← 0
  repeat (길이 + 6):
    insert (머리X) at 1 of 궤적X
    insert (머리Y) at 1 of 궤적Y
  # 길이만큼 세그먼트 클론 생성, 세그번호 1..길이
  set 세그발급 ← 0      # Stage 글로벌 임시 카운터 (또는 sprite 변수)
  repeat (길이):
    세그발급 ← 세그발급 + 1
    create clone of _myself_
    wait 0   # 클론이 세그번호를 집을 시간 양보 (선택)

when I start as clone:
  세그번호 ← 세그발급      # 생성 직전 카운터 값 채택
  show
  goto (item(세그번호) of 궤적X, item(세그번호) of 궤적Y)

when receive 스텝:        # 매 스텝, 자기 순번의 과거 좌표로 점프
  if 세그번호 ≤ 길이:      # 길이 줄어드는 일은 없지만 안전 가드
    goto (item(세그번호 + 1) of 궤적X, item(세그번호 + 1) of 궤적Y)
```

> **인덱스 설계(중요)**: 머리는 스텝마다 새 좌표를 index 1 에 insert 한다. 따라서 스텝 처리 후:
> - index 1 = 방금 머리가 도착한 칸(=머리 본체와 동일)
> - index 2 = 1스텝 전 머리 위치 → 꼬리 세그번호 1 이 여기 위치
> - index k+1 = k스텝 전 위치 → 세그번호 k 가 위치
>
> 그래서 꼬리는 `item(세그번호 + 1)` 을 읽는다. 이렇게 하면 세그번호 1 꼬리가 "머리가 방금 떠난 칸" 에 정확히 들어와 몸이 끊기지 않고 이어진다. 머리의 `touching 꼬리` 자기충돌은 머리가 **꺾여서 자기 몸 칸으로 들어갈 때만** 참이 되므로 정상 직진 시 오판 없음.
>
> **스텝 수신 순서**: 머리의 `when receive 스텝` 가 먼저 좌표를 기록(insert)해야 꼬리가 갱신된 궤적을 읽는다. Scratch 의 같은 broadcast 수신 스크립트 실행 순서는 비결정적이므로, **안전책**으로 머리는 `스텝` 수신 시 insert 까지 한 뒤 `broadcast 꼬리갱신` 를 추가로 쏘고, 꼬리는 `스텝` 대신 `꼬리갱신` 을 수신하게 해도 된다. (빌더 재량 — 단순화 시 둘 다 `스텝` 수신 + 머리 스크립트가 리스트 insert 를 맨 앞에서 수행하면 대부분 정상 동작.)

> **클론 세그번호 발급**: Scratch 에서 클론 생성 직후 클론이 글로벌 `세그발급` 값을 읽어 자기 `세그번호` 로 저장하는 방식. 순차 생성(`repeat`) 중 카운터를 1씩 올리며 `create clone` 하면 각 클론이 고유 번호를 갖는다. car-race/meteor-dodge 의 "스폰 직전 글로벌 set → create clone → 클론이 로컬 복사" 패턴과 동일.

### 7.5 게임오버 / 재시작

car-race/flappy-bird 와 동일. 배너 sprite 가 `wait until 게임상태=1 → wait until 게임상태=0 → show`. 깃발 다시 클릭 → 변수·리스트 리셋(길이=3, 방향=1, 스텝간격=0.18, 궤적 비우기) → 모든 클론 삭제 → 새 게임. 머리 sprite 에서 게임오버 시 pop 사운드 재생.

---

## 8. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  게임상태 ← 1
  길이 ← 3
  방향 ← 1
  다음방향 ← 1
  스텝간격 ← 0.18
  머리X ← -24        # 시작 격자 칸 (대략 보드 좌중앙)
  머리Y ← 0
  broadcast 게임시작

when receive 게임시작:   # 스텝 발생기
  repeat until 게임상태 = 0:
    broadcast 스텝
    wait 스텝간격

when receive 게임시작:   # 난이도 ramp (선택)
  repeat until 게임상태 = 0:
    wait 0.05
    if (점수 ≥ 5) AND (스텝간격 > 0.07):
      스텝간격 ← 0.18 - (점수 * 0.008)
      if 스텝간격 < 0.07: 스텝간격 ← 0.07
```

### 머리

```
when flag clicked:
  size 100
  point in direction 90
  show

when receive 게임시작:
  goto (머리X, 머리Y)     # (-24, 0)
  show
  broadcast 사과배치       # 첫 사과 배치
  # 입력 예약 forever
  repeat until 게임상태 = 0:
    if key → AND 방향 ≠ 3:  다음방향 ← 1
    if key ↑ AND 방향 ≠ 4:  다음방향 ← 2
    if key ← AND 방향 ≠ 1:  다음방향 ← 3
    if key ↓ AND 방향 ≠ 2:  다음방향 ← 4
    wait 0.02

when receive 스텝:
  방향 ← 다음방향
  if 방향 = 1: change x by 16
  if 방향 = 2: change y by 16
  if 방향 = 3: change x by -16
  if 방향 = 4: change y by -16
  머리X ← x position
  머리Y ← y position
  if (머리X > 224) OR (머리X < -224) OR (머리Y > 160) OR (머리Y < -160):
    게임상태 ← 0
  if touching 꼬리:
    게임상태 ← 0
  insert (머리X) at 1 of 궤적X
  insert (머리Y) at 1 of 궤적Y
  repeat until (length of 궤적X) ≤ (길이 + 5):
    delete (last) of 궤적X
    delete (last) of 궤적Y
  if (머리X = 사과X) AND (머리Y = 사과Y):
    점수 ← 점수 + 1
    길이 ← 길이 + 1
    if 점수 > 최고기록: 최고기록 ← 점수
    broadcast 사과배치
    세그발급 ← 세그발급 + 1
    create clone of 꼬리

when flag clicked:   # 게임오버 효과음
  wait until 게임상태 = 0
  play sound pop
```

### 꼬리

```
when flag clicked:
  hide

when receive 게임시작:
  hide
  delete this clone  (모든 기존 클론) → 실제로는: stop other / 깃발 시 클론 정리
  delete all of 궤적X
  delete all of 궤적Y
  세그발급 ← 0
  repeat (길이 + 6):
    insert (머리X) at 1 of 궤적X
    insert (머리Y) at 1 of 궤적Y
  repeat (길이):
    세그발급 ← 세그발급 + 1
    create clone of _myself_

when I start as clone:
  세그번호 ← 세그발급
  show
  goto (item(세그번호 + 1) of 궤적X, item(세그번호 + 1) of 궤적Y)

when receive 스텝:
  if 세그번호 ≤ 길이:
    goto (item(세그번호 + 1) of 궤적X, item(세그번호 + 1) of 궤적Y)
```

### 사과

```
when flag clicked:
  size 100
  switch costume "apple"
  show

when receive 사과배치:
  show
  repeat until (NOT touching 머리 AND NOT touching 꼬리):
    사과X ← (pick random 0 to 27) * 16 - 216
    사과Y ← (pick random 0 to 19) * 16 - 152
    goto (사과X, 사과Y)
```

### 게임오버 배너

```
when flag clicked:
  hide
  goto 0, 0
  size 100
  go to front
  wait until 게임상태 = 1
  wait until 게임상태 = 0
  show
```

> 깃발 재클릭 시 잔존 꼬리 클론 정리: 각 sprite 의 `when flag clicked` 최상단에서 클론을 가진 sprite 는 처리 어려우므로, 표준 방식은 깃발 클릭 시 `delete this clone` 가 닿지 않는 본체 외 클론을 제거하기 위해 **모든 sprite 가 `when flag clicked` 에서 자기 클론을 멈추는** 패턴 또는 Scratch 의 깃발 클릭 = 전체 클론 자동 삭제 동작에 의존(Scratch 는 깃발 클릭 시 모든 클론을 삭제함). 따라서 별도 정리 코드 불필요.

---

## 9. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| 배경 | SVG (인라인) | 480×360. 갈색 벽 테두리 + 안쪽 28×20 녹색 체크무늬 보드(16px 타일, 밝은/어두운 녹색 교대). 보드 내부 x -224..224 / y -160..160 에 맞춤 |
| 머리 | SVG (인라인) | 16×16. 둥근 진녹색 사각 + 눈 2개(흰자+검은자) + 작은 빨간 혀. rotationCenter 8,8 |
| 꼬리 | SVG (인라인) | 16×16. 둥근 녹색 사각(머리보다 옅은 녹색). rotationCenter 8,8 |
| apple | SVG (인라인) | 16×16. 빨간 원 + 갈색 꼭지 + 초록 잎. |
| 게임오버 배너 | SVG (인라인) | 검은 배너 "GAME OVER" + "꼬리/벽에 부딪혔어요" |
| pop.wav | WAV (assets/) | car-race/assets/pop.wav 복사. 사과 먹기·게임오버 효과음 |

> 크기 주의: 모든 게임 오브젝트(머리/꼬리/사과)는 16×16 viewBox + Scratch size 100 → 16px = 정확히 한 격자 칸. `touching` 충돌이 칸 단위로 깔끔히 맞으려면 SVG 가 칸을 거의 꽉 채워야 함(둥근 모서리 약간 여백 OK).

assets/ 폴더: `pop.wav` 하나. 나머지 SVG 는 build.py 인라인.

---

## 10. 변수/리스트/메시지 요약 (ID 컨벤션)

- 글로벌 변수 12개: `varScore01` `varBest02` `varState03` `varLen04` `varDir05` `varNextDir06` `varStep07` `varAppleX08` `varAppleY09` `varHeadX10` `varHeadY11` `varGap12`
- 추가 글로벌 임시: `varSegIssue14`(세그발급) — 클론 세그번호 발급용 카운터
- 꼬리 sprite-local: `varSeg13`(세그번호)
- 리스트 2개: `L_trailX01`(궤적X) `L_trailY02`(궤적Y) — Stage 글로벌
- broadcasts 3개: `brStart01`(게임시작) `brStep02`(스텝) `brPlaceApple03`(사과배치)

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **격자 스냅 이동 + 키 입력**: `games/car-race/build.py` — 차선 스냅(`set x to ...`) 대신 `change x/y by ±16`. car-race 의 `wait until NOT key` 대신 여기선 "다음방향 예약 + 스텝에서 1회 적용" 으로 1스텝 1회전 보장(역방향 차단 가드 포함).
- **클론 풀 + 스폰 직전 글로벌 set → create clone → 클론 로컬 복사**: `games/car-race/build.py`(적차 색상/속도) / `games/meteor-dodge` 패턴. 여기선 `세그발급` 카운터를 1 올리고 `create clone` → 클론이 `세그번호` 로 복사.
- **리스트 insert/delete/item-of**: `games/duck-hunt/build.py` 등 lists 필드는 빈 dict 였으나, Stage 의 `lists` 딕셔너리에 `L_trailX01`/`L_trailY02` 등록 + `data_addtolist`/`data_insertatindex`/`data_deleteoflist`/`data_itemoflist`/`data_lengthoflist` 블록 사용. (리스트를 실제 쓰는 첫 게임이므로 블록 opcode 매핑을 build.py 에 새로 추가해야 함 — 아래 opcode 표 참조.)
- **이벤트 기반 점수 +1**: `games/flappy-bird/build.py`(파이프 통과 +1) 패턴 → 여기선 사과 먹을 때 +1.
- **게임오버 배너 + 깃발 재시작**: car-race/flappy-bird 그대로.

**필요한 리스트 블록 opcode (빌더가 새로 매핑)**:
- `data_addtolist` (ITEM, LIST)
- `data_insertatindex` (ITEM, INDEX, LIST) — 머리 궤적 맨 앞 insert (INDEX=1)
- `data_deleteoflist` (INDEX, LIST) — "last" 인덱스
- `data_deletealloflist` (LIST)
- `data_itemoflist` (INDEX, LIST) — 꼬리 위치 읽기
- `data_lengthoflist` (LIST) — 버퍼 트림 조건

빌더는 car-race 의 build.py 를 베이스로 잡고: (1) 차선 변수→방향/다음방향, (2) `set x to`→`change x/y by 16` 분기, (3) 적차 클론 풀→꼬리 세그먼트 클론(궤적 리스트 추종), (4) 페인트라인 제거, (5) 사과 sprite(빈 칸 재배치) 추가, (6) Stage lists 필드에 궤적X/Y 등록.

---

## 12. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과 / `project.json` JSON 로드 OK
2. targets 수: 5 (Stage, 머리, 꼬리, 사과, 게임오버)
3. Stage 변수 13개(점수/최고기록/게임상태/길이/방향/다음방향/스텝간격/사과X/사과Y/머리X/머리Y/기록간격/세그발급) 등록
4. Stage 리스트 2개(`궤적X`=L_trailX01, `궤적Y`=L_trailY02) 등록
5. 꼬리 sprite-local 변수 1개(세그번호=varSeg13) 등록
6. Broadcasts: 게임시작 / 스텝 / 사과배치 3개
7. 머리 sprite 의 `when receive 스텝` 트리에:
   - `motion_changexby`/`motion_changeyby` ±16 분기(방향 1~4) 존재
   - `data_insertatindex`(궤적X, INDEX 1) + (궤적Y) 존재
   - `data_deleteoflist`(last) 트림 + `data_lengthoflist` 조건 존재
   - 벽 충돌 OR 조건 4개(머리X/Y 경계) 존재
   - `sensing_touchingobject`("꼬리") 자기충돌 + `data_setvariableto`(게임상태,0) 존재
   - 사과 먹기 `if (머리X=사과X AND 머리Y=사과Y)` + 점수/길이 +1 + `control_create_clone`("꼬리") 존재
8. 머리 입력 forever 에 방향키 4개 `sensing_keypressed` + 역방향 차단 `operator_and`(방향≠반대) 4개 존재
9. 꼬리 sprite 의 `control_start_as_clone` 에 `data_itemoflist`(궤적X/Y, 세그번호+1) 점프 존재
10. 꼬리 sprite 의 `when receive 스텝` 에 `data_itemoflist`(세그번호+1) goto 존재
11. 사과 sprite 의 `when receive 사과배치` 에 `pick random` 격자 추첨 + `repeat until (NOT touching 머리 AND NOT touching 꼬리)` 존재
12. Stage `when receive 게임시작` 핸들러 2개 이상(스텝 발생 + ramp)
13. monitors: 점수·최고기록·길이 표시
14. 자산 5 SVG(배경/머리/꼬리/apple/게임오버) + 1 WAV(pop), MD5 일치
15. 블록 카운트 230~320 범위

---

## 13. 빌드 카운트 예상

- Stage: ~30 블록 (init + 스텝 발생 forever + ramp)
- 머리: ~90 블록 (입력 forever + 스텝 처리: 이동 분기/궤적 insert/트림/벽·자기충돌/사과먹기/클론생성 + 사운드)
- 꼬리: ~45 블록 (게임시작 시드+클론생성 + start-as-clone + 스텝 추종)
- 사과: ~20 블록 (재배치 repeat-until)
- 게임오버: ~12 블록
- **총합 예상: 235~290 블록** (★★★★ 범위 — 리스트 기반 꼬리 관리가 난이도 핵심)

---

## 14. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (방향키로 뱀 조종 — 즉시 이해)
- [x] 추상 학습 콘셉트 없음 (뱀=뱀, 사과=사과. 수학·과학 매핑 없음)
- [x] 즉시 이해되는 룰 (먹으면 길어지고 점수, 부딪히면 끝)
- [x] 도전감 (꼬리가 길수록 자기 몸을 피하기 어려워짐) + 난이도 ramp(속도 ↑)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
- [x] 1976 Blockade / Nokia Snake 클래식 — 검증된 재미 메커닉
</content>
</invoke>
