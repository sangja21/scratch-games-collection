# 벽돌깨기 (breakout) — Plan

> 화면 하단의 패들을 좌/우 화살표(또는 마우스 X 추적)로 움직여 공을 받아친다. 공은 좌·우·위 3면 벽에서 튕기고, 패들에 맞으면 위로 반사된다. 패들 중심에서 얼마나 벗어나 맞느냐(오프셋)에 따라 공의 좌우 각도가 바뀌어 조준할 수 있다. 위쪽에는 8열 × 4행 벽돌 격자가 있고, 공이 벽돌에 닿으면 그 벽돌이 깨지며 점수를 얻고 공의 Y 방향이 반전된다. 윗행일수록 점수가 높다. 벽돌을 모두 깨면 다음 라운드(공 속도 ↑, 벽돌 격자 리셋). 공을 못 받아 바닥으로 떨어뜨리면 라이프 -1, 라이프 3개가 모두 닳으면 게임오버.
> 베이스: `games/pong/build.py`(공 1개가 매 틱 dx/dy 로 이동 + 벽 반사 + 패들 반사 시 중심 오프셋으로 각도 조절 + 속도 ramp 패턴) + `games/alien-invasion/build.py`(중첩 루프로 N열×M행 클론 격자 배치 + 글로벌 set→create clone→클론이 자기 좌표/속성 복사 + `적수` 카운터로 전멸 감지 후 `다음웨이브` broadcast 패턴) + `games/car-race/build.py`(게임상태 broadcast + 깃발 재시작 + 게임오버 배너).
> **차이점(pong 대비)**: AI 패들이 없고 위쪽이 벽돌 격자다. 공의 패들 반사는 항상 "위로"(공dy 를 무조건 양수로) 만들고, 오프셋은 X 각도를 만든다(pong 은 오프셋이 Y 각도). 득점/서브 개념 대신 라이프(목숨)·라운드 개념. **차이점(alien-invasion 대비)**: 벽돌은 총알에 맞는 게 아니라 1개뿐인 공에 `touching` 으로 맞고, 행마다 색·점수가 다르다.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지(MEMORY.md → feedback-game-design 준수).

---

## 1. 한 줄 룰

좌/우 화살표(또는 마우스)로 패들을 움직여 공을 받아친다. 위쪽 벽돌에 공을 맞혀 다 깨면 다음 라운드. 공을 바닥으로 떨어뜨리면 목숨 -1. 목숨 3개를 다 쓰면 게임오버.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 짙은 남색/검정. 좌·우·위 가장자리에 밝은 경계선 3줄(반사벽 표시). 아래쪽은 뚫림(공이 빠지는 곳).
- **플레이 영역**: x -240..+240 / y -180..+180.
  - 좌/우 벽 반사선: x = ±232 (공 코스튬 반지름 고려).
  - 위 벽 반사선: y = +170.
  - 바닥 추락선: y < -175 → 라이프 -1 (패들보다 아래).
- **패들**: y = -150 고정, x 가변(-200..+200 clamp). 좌/우 화살표 또는 마우스 X 추적으로 이동. 패들 폭 약 70px(반폭 35).
- **벽돌 격자**: 8열 × 4행 = 32개. 화면 상단에 배치.
  - 열 중심 x: -175, -125, -75, -25, +25, +75, +125, +175 (50px 간격, 8개). 즉 `colIndex*50 - 175` (colIndex 0..7).
  - 행 중심 y: +140, +115, +90, +65 (위→아래 25px 간격, 4개). 즉 `140 - rowIndex*25` (rowIndex 0..3).
  - 벽돌 크기: 약 44×18 (열 간격 50 보다 약간 작아 사이 틈 보임, 행 간격 25 보다 작음).
- **행별 색/점수**:
  | rowIndex | y | 색 | 점수 |
  |---|---|---|---|
  | 0 (맨 위) | +140 | 빨강 | 50 |
  | 1 | +115 | 주황 | 30 |
  | 2 | +90 | 노랑 | 20 |
  | 3 (맨 아래) | +65 | 초록 | 10 |
- 모니터 좌상단: 점수 / 최고기록 / 목숨 / 라운드.

```
+--------------------------------------------------+  y=+180
| #============== 위 벽 반사선 y=+170 ===========# |  점수: 240
| # [▮][▮][▮][▮][▮][▮][▮][▮]  ← 빨강 row0 y=+140 # |  최고: 600
| # [▮][▮][▮][▮][▮][▮][▮][▮]  ← 주황 row1 y=+115 # |  목숨: 2
| # [▮][▮][▮][▮][▮][▮][▮][▮]  ← 노랑 row2 y=+90  # |  라운드: 1
| # [▮][▮][▮][▮][▮][▮][▮][▮]  ← 초록 row3 y=+65  # |
| #                                              # |  ← 좌벽 x=-232
| #                  O ← 공                      # |  ← 우벽 x=+232
| #                                              # |
| #            ====== 패들 y=-150 ======         # |
+--------------------------------------------------+  y=-180
            바닥 추락선 y=-175 (공 빠지면 목숨-1)
x=-240         열중심 -175,-125,...,+175        x=+240
```

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 init + 벽돌 전멸 watcher(없음 → 라운드 진행은 벽돌 카운터로) + 게임오버 판정(목숨=0) | 게임시작/공발사/벽돌생성 broadcast 발신 |
| 1 | 패들 | 좌/우 화살표 또는 마우스 X 추적으로 좌우 이동, x clamp(-200..+200). y=-150 고정. | rotationStyle: don't rotate. 플레이어 조작 주체. |
| 2 | 공 | 1개. 매 틱 `공dx`/`공dy` 로 이동. 좌·우·위 벽 반사, 패들 반사(위로 + 오프셋 X 각도 + 속도 ramp), 벽돌 `touching` 시 Y 반전(벽돌 sprite 가 자기 삭제·점수 처리), 바닥 추락 시 라이프-1 + 재발사. | costume "ball". 단일 인스턴스. 물리 판정 주체. |
| 3 | 벽돌 | 8×4=32 클론 풀. 게임시작/다음라운드 시 중첩 루프로 격자 배치. 각 클론은 자기 `벽돌X`/`벽돌Y`/`벽돌행`(코스튬·점수 결정)을 복사. 공에 닿으면 점수 +행점수, `벽돌수` -1, delete this clone. | sprite-local `자기X`/`자기Y`/`자기행`. 코스튬 4개(행별 색). |
| 4 | 결과 배너 | "GAME OVER" / "STAGE CLEAR"(선택) 배너. 평소 숨김. 게임상태=0 일 때 보임. | car-race 배너 패턴. 게임오버 코스튬 1개(MVP). |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 깬 벽돌 점수 누적 |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| 목숨 | `varLives04` | 3 | 남은 라이프. 0이면 게임오버 |
| 라운드 | `varRound05` | 1 | 현재 라운드(클리어할 때마다 +1) |
| 공dx | `varBallDX06` | 3 | 공 x 속도(틱당 이동량). 음수=왼쪽, 양수=오른쪽 |
| 공dy | `varBallDY07` | 4 | 공 y 속도(틱당 이동량). 음수=아래, 양수=위 |
| 공속도 | `varBallSpd08` | 5 | 공 전체 속력. 패들 반사 ramp + 라운드마다 증가. dx/dy 재계산 기준 |
| 패들반폭 | `varPadHalf09` | 35 | 패들 코스튬 폭의 절반. 오프셋 정규화(-1..+1)에 사용 |
| 벽돌수 | `varBrickCnt10` | 0 | 현재 살아있는 벽돌 클론 수. 0이면 라운드 클리어 |
| 오프셋 | `varOff11` | 0 | 패들 반사 각 계산 임시(공 x 위치 - 패들 x)/패들반폭 |
| 결과 | `varResult12` | 0 | 0=진행중, 1=게임오버(목숨0), 2=(선택)전라운드클리어 |

패들 sprite-local: 없음.

공 sprite-local: 없음 (물리 변수는 글로벌 — 디버깅·다른 sprite 참조 가능).

벽돌 sprite-local 변수:

| 변수명 | ID | 용도 |
|--------|----|------|
| 자기X | `varBX13` | 클론 생성 직전 글로벌 set 값을 복사. 격자 열 중심 x |
| 자기Y | `varBY14` | 격자 행 중심 y |
| 자기행 | `varBRow15` | rowIndex 0..3. 코스튬(색)과 점수 결정 |

---

## 5. 리스트

- 없음. (벽돌은 클론 + sprite-local 좌표로 충분. snake 와 달리 궤적 추종이 없음.)

---

## 6. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 벽돌생성 | `brBricks02` | 게임시작 시 1회 + 다음라운드마다 발신 → 벽돌 sprite 가 8×4 격자 클론 생성 (`벽돌수`=32 세팅 포함) |
| 공발사 | `brLaunch03` | 게임시작 시 1회 + 목숨 잃고 공이 떨어진 직후 발신 → 공이 패들 위 중앙에서 잠깐 멈췄다가 위로 출발 |
| 다음라운드 | `brNextRound04` | `벽돌수` 가 0이 되었을 때(벽돌 sprite 마지막 클론이 깨질 때) 발신 → 라운드+1, 공속도+1, `벽돌생성` + `공발사` |

---

## 7. 메커닉 상세

### 7.1 패들 (플레이어) — 좌우 이동

y=-150 고정. 좌/우 화살표로 좌우 이동 + clamp. (선택) 마우스 X 추적 모드 병행. apple-catch 의 좌우 이동 + clamp 패턴.

```
when receive 게임시작:
  set y to -150
  set x to 0
  repeat until 게임상태 = 0:
    # 키 입력 모드
    if key →:  change x by 7
    if key ←:  change x by -7
    # (선택) 마우스 추적 모드: set x to (mouse x), 단 아래 clamp 적용
    #   → 빌더 재량. MVP 는 화살표. 마우스 병행 시 "마우스가 무대 안일 때만 set x to mouse x" 추가.
    if x position > 200:  set x to 200
    if x position < -200: set x to -200
    set y to -150
    wait 0.016
```

> 이동량 7 은 부드러운 조작. 키를 누르고 있으면 연속 이동(에지 입력 아님). 마우스 병행을 원하면 `set x to (mouse x)` 후 같은 clamp 를 적용 — 둘 다 같은 clamp 를 거치므로 충돌 없음.

### 7.2 공 — 물리 (3면 벽 반사 + 패들 반사 + 벽돌 Y반전 + 추락) — **핵심 메커닉**

공은 매 틱 `change x by 공dx` / `change y by 공dy` 후 반사·추락 검사. pong 의 공 물리에서 (1) 아래 벽 반사를 **제거**하고 추락(라이프-1)으로 대체, (2) 패들 반사를 **항상 위로** 만들고 오프셋을 X 각도로 사용한다.

```
when receive 공발사:
  # 공을 패들 위 중앙으로, 잠깐 멈춤 후 위로 출발
  set x to (패들의 x position)         # 패들 따라 시작 (sensing_of)
  set y to -135
  공dx ← (pick random -2 to 2)         # 약간의 무작위 가로 각
  공dy ← 공속도                          # 위로 출발(양수)
  wait 0.6                              # 발사 전 정지(플레이어 준비)

when receive 게임시작:
  show
  repeat until 게임상태 = 0:
    change x by 공dx
    change y by 공dy

    # (1) 좌/우 벽 반사 (X 반전)
    if (x position > 232) OR (x position < -232):
      공dx ← 공dx * -1
      if x position > 232:  set x to 232
      if x position < -232: set x to -232

    # (2) 위 벽 반사 (Y 반전, 아래로)
    if (y position > 170):
      공dy ← -1 * (abs of 공dy)         # 무조건 아래로
      set y to 170

    # (3) 패들 반사 (공이 아래로 가는 중 + 패들에 닿음) — 무조건 위로 + 오프셋 X 각
    if (touching 패들) AND (공dy < 0):
      공속도 ← 공속도 + 0.3                          # 랠리 ramp
      오프셋 ← ((x position) - (패들의 x position)) / 패들반폭   # -1..+1
      공dx ← 오프셋 * 공속도                          # 패들 끝에 맞으면 옆으로 가파르게
      공dy ← 공속도                                  # 무조건 위로(양수)
      set y to -135                                 # 패들 위로 빼서 재충돌 방지
      play sound bounce

    # (4) 벽돌 반사: 벽돌에 닿으면 Y 반전 (벽돌 sprite 가 점수·삭제·벽돌수-- 처리)
    if (touching 벽돌):
      공dy ← 공dy * -1
      play sound brick

    # (5) 바닥 추락: 목숨 -1, 게임오버 아니면 재발사
    if (y position < -175):
      목숨 ← 목숨 - 1
      if 목숨 ≤ 0:
        결과 ← 1
        게임상태 ← 0
      else:
        broadcast 공발사        # 패들 위에서 다시 시작
    wait 0.016
```

> **각도 컨트롤 직관(pong 재사용, 축만 회전)**: pong 은 좌패들에서 `오프셋 = (공Y - 패들Y)/반높이` 로 **Y 각**을 만들었다. breakout 은 패들이 아래에 가로로 있으므로 `오프셋 = (공X - 패들X)/반폭` 로 **X 각**을 만든다. 패들 중앙에 맞으면 `오프셋≈0` → 공이 거의 수직으로 위로. 패들 오른쪽 끝에 맞으면 `오프셋≈+1` → 공이 오른쪽 위로 가파르게. 플레이어가 패들 위치로 받아치는 방향을 조준한다.
> **항상 위로 반사**: 패들 반사 시 `공dy ← 공속도`(항상 양수)로 두면 공이 패들 밑으로 빨려들거나 끼는 일이 없다. 위 벽 반사도 `공dy ← -abs(공dy)`(항상 음수=아래)로 안전화.
> **속도 ramp**: 패들에 맞을 때마다 `공속도 += 0.3`. 라운드 클리어 시 다음라운드 핸들러가 `공속도 += 1` (아래 7.5). 무한 가속 방지를 위해 라운드/발사 시작 시 기준값으로 살짝 리셋해도 됨(빌더 재량 — MVP 는 그대로 누적).
> **벽돌 다중 충돌**: 한 틱에 두 벽돌에 동시에 닿을 수 있으나 `touching 벽돌` 은 한 번만 Y 반전. 점수·삭제는 벽돌 sprite 각 클론이 자기 `touching 공` 으로 독립 처리하므로, 동시에 닿은 클론들이 각자 깨질 수 있다(허용 가능한 약간의 보너스).

### 7.3 벽돌 (8×4 격자 클론) — **핵심 메커닉 (alien-invasion 재사용)**

**클론 풀 구성**: `벽돌생성` 수신 시 중첩 루프(행 4 × 열 8)로 32개 클론을 순차 생성. 생성 직전 글로벌이 아닌 sprite-local `자기X`/`자기Y`/`자기행` 을 set 한 뒤 `create clone of _myself_`. alien-invasion 의 `cols×rows` 중첩 spawn + `적수` 카운터 패턴 그대로(여기선 `벽돌수`).

```
when flag clicked:
  hide

when receive 벽돌생성:
  hide
  벽돌수 ← 0
  # 행 0..3 × 열 0..7 = 32
  for rowIndex in 0..3:        # Scratch 에선 변수 row 0→3 repeat 또는 펼친 중첩
    for colIndex in 0..7:
      자기X ← colIndex * 50 - 175
      자기Y ← 140 - rowIndex * 25
      자기행 ← rowIndex
      create clone of _myself_
      벽돌수 ← 벽돌수 + 1
      wait 0.01      # 클론이 자기 값 복사할 시간 양보

when I start as clone:
  goto (자기X, 자기Y)
  switch costume to (자기행 + 1)     # 코스튬 1=빨강(row0) .. 4=초록(row3)
  show
  repeat until 게임상태 = 0:
    if touching 공:
      # 행별 점수: row0=50, row1=30, row2=20, row3=10
      if 자기행 = 0:  점수 ← 점수 + 50
      if 자기행 = 1:  점수 ← 점수 + 30
      if 자기행 = 2:  점수 ← 점수 + 20
      if 자기행 = 3:  점수 ← 점수 + 10
      if 점수 > 최고기록: 최고기록 ← 점수
      벽돌수 ← 벽돌수 - 1
      play sound brick
      if 벽돌수 ≤ 0:
        broadcast 다음라운드
      delete this clone
    wait 0.016
```

> **중첩 루프 구현**: Scratch 에 중첩 for 가 없으므로 두 가지 중 택1.
> (a) **펼친 32-블록 체인**(alien-invasion 방식): build.py 의 파이썬 루프로 `for ry in rows: for cx in cols:` 돌며 set자기X/set자기Y/set자기행/create clone/벽돌수+1/wait 블록을 32세트 펼쳐 chain. 블록 수는 많지만 가장 안전·명확. **권장**.
> (b) **변수 카운터 중첩 repeat**: `repeat 4`(행) 안에 `repeat 8`(열) — 블록 수 적으나 colIndex/rowIndex 변수 관리 필요. 빌더 재량.
> **코스튬 인덱스**: 벽돌 sprite 코스튬 4개(빨강/주황/노랑/초록). `switch costume to (자기행 + 1)` 로 행에 맞는 색 선택. (Scratch 코스튬 번호는 1부터, 자기행은 0부터 → +1.)
> **per-clone 값 복사 타이밍**: alien-invasion 과 동일하게 `set 자기X/자기Y/자기행 → create clone → wait 0.01`. 클론이 `start as clone` 에서 그 값을 읽어 위치·코스튬을 잡는다. wait 0.01 로 다음 set 전에 클론이 값을 집을 시간을 준다.
> **점수 분기 단순화**: `if 자기행=0..3` 4분기 대신 점수표를 `[50,30,20,10]` 매핑 식 `(50 - 자기행*?)` 으로 못 줄이므로 4 if 분기가 가장 명확(또는 `점수 ← 점수 + item(자기행+1) of 점수표리스트` 형태로 리스트 1개 추가 가능 — MVP 는 4 if).

### 7.4 게임오버 판정

목숨 처리는 공 sprite 가 추락 시 직접 한다(7.2 (5)). `목숨 ≤ 0 → 결과=1, 게임상태=0`. 별도 Stage watcher 불필요(pong 의 점수 watcher 대신 공이 직접 판정). 원하면 Stage 에 `repeat until 목숨=0` watcher 를 둬도 됨(빌더 재량 — 본문은 공 직접 처리).

### 7.5 다음 라운드 (전 벽돌 클리어)

벽돌 마지막 클론이 깨질 때 `벽돌수=0` → `broadcast 다음라운드`. Stage 가 라운드+1·공속도+1 후 벽돌 재생성 + 공 재발사. alien-invasion 의 `다음웨이브`(formation 리셋 + speed up) 패턴 그대로.

```
when receive 다음라운드:        # Stage
  라운드 ← 라운드 + 1
  공속도 ← 공속도 + 1            # 라운드마다 공 빨라짐
  목숨 ← 목숨 + 0               # (선택) 보너스 라이프 없음. 원하면 +1
  wait 0.3                      # 잠깐 텀
  broadcast 벽돌생성             # 격자 리셋(벽돌수 다시 32)
  broadcast 공발사              # 공 패들 위에서 재발사
```

> **공 sprite 와의 충돌 주의**: 다음라운드 시 공이 화면 중간에 떠 있을 수 있으므로 `공발사` 가 공을 패들 위로 다시 끌어온다(set x to 패들X / set y -135). 이미 7.2 `공발사` 핸들러가 그 일을 함.

### 7.6 결과 배너 / 재시작

car-race/pong 패턴. 배너 sprite `wait until 게임상태=0 → switch costume(결과별) → show`. 깃발 재클릭 → 모든 변수 리셋(점수0/게임상태1/목숨3/라운드1/공속도5) → 모든 클론 삭제(Scratch 깃발이 자동 삭제) → 새 게임. 게임오버 시 pop/lose 사운드.

```
when flag clicked:
  hide
  goto 0, 0
  go to front
  wait until 게임상태 = 0
  switch costume "gameover"     # (선택: 결과=2 면 "clear" 코스튬)
  show
  play sound lose              # 선택
```

---

## 8. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  게임상태 ← 1
  목숨 ← 3
  라운드 ← 1
  공속도 ← 5
  패들반폭 ← 35
  결과 ← 0
  벽돌수 ← 0
  broadcast 게임시작
  broadcast 벽돌생성        # 첫 격자
  broadcast 공발사         # 첫 발사

when receive 다음라운드:
  라운드 ← 라운드 + 1
  공속도 ← 공속도 + 1
  wait 0.3
  broadcast 벽돌생성
  broadcast 공발사
```

### 패들

```
when flag clicked:
  size 100
  point in direction 90
  show

when receive 게임시작:
  set y to -150
  set x to 0
  repeat until 게임상태 = 0:
    if key →:  change x by 7
    if key ←:  change x by -7
    if x position > 200:  set x to 200
    if x position < -200: set x to -200
    set y to -150
    wait 0.016
```

### 공

```
when flag clicked:
  size 100
  switch costume "ball"
  show

when receive 공발사:
  set x to ([x position] of 패들)
  set y to -135
  공dx ← pick random -2 to 2
  공dy ← 공속도
  wait 0.6

when receive 게임시작:
  show
  repeat until 게임상태 = 0:
    change x by 공dx
    change y by 공dy
    if (x position > 232) OR (x position < -232):
      공dx ← 공dx * -1
      if x position > 232:  set x to 232
      if x position < -232: set x to -232
    if (y position > 170):
      공dy ← -1 * (abs of 공dy)
      set y to 170
    if (touching 패들) AND (공dy < 0):
      공속도 ← 공속도 + 0.3
      오프셋 ← (x position - [x position] of 패들) / 패들반폭
      공dx ← 오프셋 * 공속도
      공dy ← 공속도
      set y to -135
      play sound bounce
    if (touching 벽돌):
      공dy ← 공dy * -1
      play sound brick
    if (y position < -175):
      목숨 ← 목숨 - 1
      if 목숨 ≤ 0:
        결과 ← 1
        게임상태 ← 0
      else:
        broadcast 공발사
    wait 0.016
```

> `abs of 공dy` 는 `operator_mathop`("abs", 공dy). 위 벽 반사를 항상 아래로 보내기 위함. 단순화하려면 좌/우 벽처럼 `공dy ← 공dy * -1` + `set y to 170` 로 둬도 정상(공이 위로 가던 중에만 y>170 에 도달하므로 `*-1` 이 곧 아래가 됨). 빌더 재량.

### 벽돌

```
when flag clicked:
  hide

when receive 벽돌생성:        # (펼친 32-블록 체인: build.py 파이썬 루프로 생성)
  hide
  벽돌수 ← 0
  # for ry(행) 0..3, cx(열) 0..7:
  #   자기X ← cx*50 - 175
  #   자기Y ← 140 - ry*25
  #   자기행 ← ry
  #   create clone of _myself_
  #   벽돌수 ← 벽돌수 + 1
  #   wait 0.01

when I start as clone:
  goto (자기X, 자기Y)
  switch costume to (자기행 + 1)
  show
  repeat until 게임상태 = 0:
    if touching 공:
      if 자기행 = 0: 점수 ← 점수 + 50
      if 자기행 = 1: 점수 ← 점수 + 30
      if 자기행 = 2: 점수 ← 점수 + 20
      if 자기행 = 3: 점수 ← 점수 + 10
      if 점수 > 최고기록: 최고기록 ← 점수
      벽돌수 ← 벽돌수 - 1
      play sound brick
      if 벽돌수 ≤ 0: broadcast 다음라운드
      delete this clone
    wait 0.016
```

### 결과 배너

```
when flag clicked:
  hide
  goto 0, 0
  go to front
  wait until 게임상태 = 0
  switch costume "gameover"
  show
```

---

## 9. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| 배경 | SVG (인라인) | 480×360. 짙은 남색/검정 + 좌·우·위 밝은 경계선 3줄(반사벽). 아래쪽 뚫림 |
| 패들 | SVG (인라인) | 약 70×16. 밝은 하늘색/흰 둥근 가로 막대. rotationCenter 중앙. 폭 70 → 반폭 35(=패들반폭) |
| ball | SVG (인라인) | 약 14×14. 흰 또는 노란 원 |
| 벽돌 (코스튬 4개) | SVG (인라인) ×4 | 약 44×18 둥근 사각. 코스튬1=빨강 / 2=주황 / 3=노랑 / 4=초록 (행 색) |
| 결과 배너 | SVG (인라인) | 검은 배너 "GAME OVER". (선택 코스튬2 "STAGE CLEAR") |
| bounce.wav | WAV (assets/) | 패들 튕김. car-race/assets/pop.wav 복사·재사용 가능 |
| brick.wav | WAV (assets/) | 벽돌 깨짐 (pop.wav 재사용 또는 짧은 변형) |
| lose.wav | WAV (assets/) | 게임오버 (선택, pop.wav 재사용) |

> 패들 폭 70 ↔ `패들반폭=35` 가 정확히 맞아야 오프셋 정규화(-1..+1)가 패들 끝에서 ±1 이 된다. SVG 폭을 바꾸면 `패들반폭` 도 같이 조정.
> 벽돌 코스튬 4개는 한 sprite 에 색만 다른 둥근 사각. `자기행+1` 로 선택.

assets/ 폴더: `pop.wav`(=bounce/brick/lose 공용 재사용 가능). 나머지 SVG 는 build.py 인라인.

---

## 10. 변수/리스트/메시지 요약 (ID 컨벤션)

- 글로벌 변수 12개: `varScore01`(점수) `varBest02`(최고기록) `varState03`(게임상태) `varLives04`(목숨) `varRound05`(라운드) `varBallDX06`(공dx) `varBallDY07`(공dy) `varBallSpd08`(공속도) `varPadHalf09`(패들반폭) `varBrickCnt10`(벽돌수) `varOff11`(오프셋) `varResult12`(결과)
- 벽돌 sprite-local 3개: `varBX13`(자기X) `varBY14`(자기Y) `varBRow15`(자기행)
- 리스트: 없음 (선택: `점수표`(L_score01) 1개로 행 점수 4 if 를 1 itemoflist 로 대체 가능)
- broadcasts 4개: `brStart01`(게임시작) `brBricks02`(벽돌생성) `brLaunch03`(공발사) `brNextRound04`(다음라운드)
- 모니터: 점수(좌상단) / 최고기록 / 목숨 / 라운드 4개 표시

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **공 1개 매 틱 dx/dy 이동 + 벽 반사 + 패들 반사(중심 오프셋 각도) + 속도 ramp**: `games/pong/build.py` 의 공 sprite 가 거의 그대로. 변경점: (1) 아래 벽 반사 삭제 → 추락(목숨-1) + `broadcast 공발사`, (2) 패들 반사 시 `공dy` 를 항상 양수(`공속도`), 오프셋은 `공dx` 에 적용(pong 은 Y, breakout 은 X), (3) 우패들/득점 로직 삭제, (4) 벽돌 `touching` Y반전 추가, (5) 좌·우·위 3면 벽 반사로 변경.
- **N열×M행 클론 격자 배치 + per-clone 좌표/속성 복사 + 카운터 전멸 감지 후 broadcast**: `games/alien-invasion/build.py` 의 `적생성`(cols×rows 펼친 spawn_chain) + `적수` 카운터 + `적수=0 → 다음웨이브` 패턴 그대로. 여기선 `벽돌생성`/`벽돌수`/`다음라운드`. 격자 크기만 5×3 → 8×4, 행별 코스튬·점수 차등 추가.
- **per-clone 식별값 복사**: alien-invasion 의 `set 자기X/자기Y → create clone → start as clone 에서 읽기`. 여기선 `자기행` 추가(코스튬·점수 결정).
- **패들 좌우 이동 + clamp**: `games/apple-catch/build.py`(바구니 좌우 이동·clamp) 그대로. (마우스 추적 병행 시 `mouse x` set + 같은 clamp.)
- **게임상태 broadcast + 깃발 재시작 + 결과 배너**: `games/car-race/build.py` / `games/pong/build.py`(배너 `wait until 게임상태=0 → show`).
- **`sensing_of`(다른 sprite x position)**: `games/pong/build.py`(공이 패들 y 읽음) → 여기선 공이 패들 x 읽음(발사 위치 + 반사 오프셋).

빌더 권장 베이스: **pong 의 build.py 를 공·패들·Stage 의 골격으로** 잡고, **alien-invasion 의 build.py 에서 격자 spawn_chain + 카운터/다음웨이브 코드를 가져와** 벽돌 sprite 를 구성한다. (1) pong 우패들 sprite 삭제, (2) pong 좌패들 → 하단 가로 패들(상하→좌우 축 교체), (3) pong 공 반사 로직을 위 7.2 로 수정, (4) alien-invasion 격자 spawn 을 벽돌 sprite 로 이식(8×4, 코스튬/점수 차등), (5) Stage 에 목숨/라운드/벽돌수/다음라운드 추가, (6) 결과 배너 game over.

**필요한 블록 opcode (위 베이스 대비 확인)**:
- `control_create_clone_of`(_myself_) + `control_start_as_clone` + `control_delete_this_clone` (alien-invasion 에 존재)
- `looks_switchcostumeto`(VALUE = `자기행 + 1` 연산) — alien-invasion/pong 에 코스튬 전환 존재, 입력에 연산 슬롯 사용
- `sensing_of`(PROPERTY="x position", OBJECT=패들) — pong 에 존재(y position)
- `operator_mathop`("abs") — 위 벽 반사 단순화 안 쓰면 불필요
- `operator_divide`(오프셋 정규화) / `operator_random`(발사 dx) — pong 에 존재
- 나머지(`motion_changexby/changeyby/setx/sety/gotoxy`, `sensing_touchingobject`, `operator_gt/lt/and/or/multiply/subtract/equals`, `data_setvariableto/changevariableby`, `control_repeat_until/if/if_else`, `event_broadcast`)는 pong/alien-invasion 에 모두 존재.

---

## 12. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과 / `project.json` JSON 로드 OK
2. targets 수: 5 (Stage, 패들, 공, 벽돌, 결과 배너)
3. Stage 글로벌 변수 12개(점수/최고기록/게임상태/목숨/라운드/공dx/공dy/공속도/패들반폭/벽돌수/오프셋/결과) 등록
4. 벽돌 sprite-local 변수 3개(자기X=varBX13 / 자기Y=varBY14 / 자기행=varBRow15) 등록
5. Broadcasts 4개: 게임시작 / 벽돌생성 / 공발사 / 다음라운드 등록
6. 패들 `when receive 게임시작` forever 에 ←/→ `sensing_keypressed` 2개 + `motion_changexby`(±7) + x clamp(±200) + `set y to -150` 존재
7. 공 `when receive 게임시작` forever 에:
   - `motion_changexby`(공dx) + `motion_changeyby`(공dy) 매 틱 이동
   - 좌/우 벽 반사: `(x>232 OR x<-232) → 공dx ← 공dx*-1` 존재
   - 위 벽 반사: `y>170 → 공dy` 음수화(아래로) 존재
   - 패들 반사: `touching 패들 AND 공dy<0 → 공dy ← 공속도(양수) + 오프셋 기반 공dx + 공속도+=0.3` 존재
   - 벽돌 반사: `touching 벽돌 → 공dy ← 공dy*-1` 존재
   - 추락: `y<-175 → 목숨-1`, `목숨≤0 → 결과=1·게임상태=0`, else `broadcast 공발사` 존재
8. 공 `when receive 공발사` 에 패들 위 복귀(`set x to [x position] of 패들`, set y -135) + `공dy ← 공속도` + 무작위 `공dx`(`operator_random`) + `wait` 존재
9. 오프셋 정규화에 `operator_divide`(... / 패들반폭) 존재
10. 벽돌 `when receive 벽돌생성` 에 32회 클론 생성(펼친 체인 또는 중첩 repeat) + `벽돌수` 32 세팅 + per-clone `자기X/자기Y/자기행` set→`control_create_clone_of`(_myself_) 존재
11. 벽돌 `control_start_as_clone` 에 `goto(자기X,자기Y)` + `looks_switchcostumeto`(자기행+1) 존재
12. 벽돌 클론 forever 에 `touching 공 → 행별 점수 +(50/30/20/10) + 벽돌수-1 + (벽돌수≤0 → broadcast 다음라운드) + delete this clone` 존재
13. Stage `when receive 다음라운드` 에 라운드+1 + 공속도+1 + `broadcast 벽돌생성` + `broadcast 공발사` 존재
14. 결과 배너 sprite `wait until 게임상태=0 → switch costume "gameover" → show` 존재
15. monitors: 점수·최고기록·목숨·라운드 표시
16. 자산: SVG(배경/패들/ball/벽돌 코스튬4/게임오버) + WAV(pop 재사용), MD5 일치
17. 블록 카운트 230~330 범위(펼친 32 벽돌 spawn 포함)
18. (동작 검증) 공이 좌·우·위 3면에서 튕김 / 패들 끝에 맞으면 옆으로 가파른 각 / 벽돌 닿으면 깨지고 Y반전 / 벽돌 32개 다 깨면 라운드+1·공 빨라짐 / 바닥 추락 시 목숨-1 후 패들 위 재발사 / 목숨 0 시 게임오버 배너 / 공이 패들·벽에 끼지 않음

---

## 13. 빌드 카운트 예상

- Stage: ~22 블록 (init + 다음라운드 핸들러)
- 패들: ~18 블록 (좌우 이동 + clamp)
- 공: ~70 블록 (이동 + 3면 벽 반사 + 패들 반사 각 계산 + 벽돌 반사 + 추락/목숨/재발사 + 발사 핸들러)
- 벽돌: ~120 블록 (펼친 32 spawn 체인 ~96 + start-as-clone ~6 + 충돌/점수/카운터 forever ~18) — (b) 중첩 repeat 방식이면 ~40
- 결과 배너: ~10 블록
- **총합 예상: 240~310 블록** (★★★★ 범위 — 격자 클론 spawn + 공 물리 반사가 난이도 핵심. 중첩 repeat 채택 시 ★★★ 하단)

---

## 14. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (좌/우 버튼으로 패들 조작 — 즉시 이해)
- [x] 추상 학습 콘셉트 없음 (패들=패들, 공=공, 벽돌=벽돌. 수학·과학 매핑 없음. 각도 컨트롤은 "패들 어디에 맞히느냐" 손맛)
- [x] 즉시 이해되는 룰 (위 벽돌 다 깨면 다음판, 공 떨어뜨리면 목숨 줄고, 목숨 다 쓰면 끝)
- [x] 도전감 (랠리·라운드마다 공이 빨라짐) + 점진적 보상(윗행일수록 고득점)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
- [x] 1976 아타리 Breakout 클래식 — 검증된 재미 메커닉
