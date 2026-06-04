# 카우보이 결투 (cowboy-duel) — Plan

> 서부 석양 배경 1대1 권총 결투. 화면에 "DRAW!" 신호(시각 섬광 + 총소리/벨)가 뜨는 순간, 누가 먼저 **스페이스**를 누르나 반응속도 대결. 신호 전에 누르면 부정출발(반칙) = 그 라운드 즉시 패배. AI 상대는 라운드마다 반응시간이 랜덤이고 라운드가 갈수록 빨라진다. 내 반응시간(ms)과 베스트 기록을 표시. 5판 3선승.
> 베이스: `games/pong/build.py`(게임상태 broadcast + 깃발 재시작 + 결과 배너 win/lose 코스튬 2개 + 점수 watcher) + `games/duck-hunt/build.py`(라운드 진행 + 코스튬 전환 연출). **차이점**: 물리/이동이 없다. 핵심은 (a) 랜덤 대기 후 신호, (b) `timer` 블록으로 ms 반응시간 측정, (c) 신호 전 입력 = 부정출발 판정. 클론·리스트 없음.
> 학습 콘셉트 절대 없음. 순수 반응속도 액션. 초등학생 대상 직관적(스페이스 1키). 연출(석양·긴장감·총 쏘는 포즈·쓰러지는 상대)에 집중. (MEMORY.md → feedback-game-design 준수)

---

## 1. 한 줄 룰

석양 아래 두 카우보이가 마주 선다. "준비..." 후 언제 뜰지 모르는 **"DRAW!"** 신호가 번쩍이면 즉시 스페이스를 눌러 사격한다. AI보다 빠르면 라운드 승리. 신호 전에 누르면 반칙으로 그 라운드 패배. 먼저 3라운드를 이기면 최종 승리.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- SVG 좌표(0..480 / 0..360) ↔ Scratch 좌표 변환: `sx = svgX - 240`, `sy = 180 - svgY`.
- 배경: 서부 석양. 위쪽 주황→빨강 그라데이션 하늘 + 가운데 큰 노란 태양 원(중앙 약간 위) + 아래쪽 사막 갈색 대지 + 멀리 메사(붉은 바위) 실루엣 2~3개 + 굴러가는 회전초(tumbleweed) 실루엣 1개(정적). 신호 직전 긴장감을 위해 배경 자체는 차분하게.
- **플레이어 카우보이(왼쪽)**: x = -150, y = -40 고정. 화면 왼쪽, 오른쪽(상대)을 바라보는 자세. 대기/사격/패배 3코스튬.
- **AI 카우보이(오른쪽)**: x = +150, y = -40 고정. 화면 오른쪽, 왼쪽을 바라보는 자세(좌우 반전). 대기/사격/패배 3코스튬.
- **DRAW 신호 배너**: x = 0, y = +60 (두 카우보이 사이 위쪽). 평소 숨김. 신호 순간만 크게 번쩍("DRAW!").
- **결과 배너**: x = 0, y = 0 (화면 중앙). 라운드 결과("YOU WIN!"/"YOU LOSE"/"FOUL!") + 최종 결과("VICTORY!"/"DEFEAT") 코스튬. 평소 숨김.

```
+----------------------------------------------------------+ y=+180
| 내승:1   베스트:312ms   내기록:285ms        AI승:0       |  ← 변수 모니터 (상단)
|                  ☀ (석양 태양)                            |
|                                                          |
|                 ┌──────────┐                            |  y=+60
|                 │  DRAW!   │  ← DRAW 신호 배너(번쩍)     |
|                 └──────────┘                            |
|    🤠                              🤠                     |  y=-40
|  플레이어(x-150)                  AI(x+150, 좌우반전)     |
| ░░░ 메사 실루엣 ░░░░░░░ 사막 대지 ░░░░░░░░░░░░░░░░░░░░░░ |
+----------------------------------------------------------+ y=-180
  x=-240                                              x=+240
            [ 스페이스 = 사격 ]
```

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 코스튬 |
|---|------|------|--------|
| 0 | Stage | 배경(석양) + 전역 변수 + 라운드 진행/대결 로직(서브 스크립트) + 최종 승패 판정 | bg.svg |
| 1 | 플레이어 | 왼쪽 카우보이. 대기→(신호 후 스페이스)→사격 코스튬, 라운드 패배 시 쓰러짐 코스튬 | p_ready.svg, p_shoot.svg, p_down.svg |
| 2 | AI | 오른쪽 카우보이. 대기→(AI반응시간 경과 시)→사격 코스튬, 라운드 패배 시 쓰러짐 코스튬 | a_ready.svg, a_shoot.svg, a_down.svg |
| 3 | DRAW배너 | 신호 순간 "DRAW!" 번쩍 + "준비..." 텍스트 표시. 평소 숨김 | ready.svg(준비...), draw.svg(DRAW!) |
| 4 | 결과배너 | 라운드 결과(WIN/LOSE/FOUL) + 최종 결과(VICTORY/DEFEAT) | win.svg, lose.svg, foul.svg, victory.svg, defeat.svg |

총 5 스프라이트(Stage 포함). 클론 없음, 리스트 없음.

---

## 4. 변수 (Stage 글로벌)

| 한국어 | ID | 초기값 | 의미 |
|--------|----|--------|------|
| 게임상태 | `varState01` | 1 | 1=게임 진행, 0=최종 종료(매치 끝) |
| 내승 | `varPWins02` | 0 | 플레이어가 이긴 라운드 수 |
| AI승 | `varAWins03` | 0 | AI가 이긴 라운드 수 |
| 목표승 | `varTarget04` | 3 | 먼저 도달 시 최종 승리(5판 3선승) |
| 라운드 | `varRound05` | 1 | 현재 라운드 번호 |
| 라운드상태 | `varRStatus06` | 0 | 0=대기/카운트다운, 1=신호 떴음(사격 가능), 2=라운드 끝(결과 처리중) |
| AI반응 | `varAIRT07` | 0.5 | 이번 라운드 AI 반응시간(초). 신호 후 이 시간이 지나면 AI 사격 |
| 내반응ms | `varPRT08` | 0 | 이번 라운드 내 반응시간(밀리초). 신호~스페이스 사이 timer 차이 ×1000 |
| 베스트ms | `varBest09` | 9999 | 매치 중 최고(최소) 반응시간 기록(ms). 갱신 시 표시 |
| 라운드결과 | `varRResult10` | 0 | 0=미정, 1=플레이어 승, 2=AI 승, 3=부정출발(반칙 패) |
| 최종결과 | `varFinal11` | 0 | 0=진행중, 1=플레이어 최종승, 2=AI 최종승 |
| 신호시각 | `varSigT12` | 0 | 신호가 뜬 순간의 `timer` 값(초). 반응시간 = 현재 timer - 신호시각 |

스프라이트 sprite-local 변수: 없음(모두 Stage 글로벌 — 디버깅 용이, pong/duck-hunt 관례).

> `timer` 는 Scratch 내장 블록(`sensing_timer`). 깃발 클릭 시 자동 0으로 리셋되지 않으므로, 신호를 띄우는 순간 `신호시각 ← timer` 로 기준점을 잡고, 스페이스를 누른 순간 `내반응ms ← round((timer - 신호시각) * 1000)` 로 ms 계산. (별도 `reset timer` 불필요 — 차이만 쓰면 됨.)

---

## 5. 방송 (broadcasts)

| 한국어 | ID | 트리거 |
|--------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 → 변수 초기화 직후. 카우보이/배너가 초기 포즈로 리셋 |
| 라운드시작 | `brRoundStart02` | 매 라운드 시작 시(게임시작 직후 1회 + 라운드 종료 후 다음 라운드). "준비..." 표시 → 랜덤 대기 → 신호 처리는 Stage 가 담당 |
| 신호 | `brDraw03` | 랜덤 대기가 끝나 "DRAW!" 신호를 띄울 때. 배너 번쩍 + 총소리/벨 + `신호시각` 기록 + `라운드상태=1` |
| 라운드끝 | `brRoundEnd04` | 라운드 승패가 정해졌을 때(플레이어 승/AI 승/부정출발). 결과 배너 + 코스튬 연출 트리거 |

> 라운드 1판은 **Stage 의 메인 대결 스크립트** 한 곳에서 순서대로 처리(랜덤 대기 → 신호 → 누가 먼저인지 판정). 클론/병렬 없이 직선적이라 디버그·검증이 쉽다.

---

## 6. 씬 / 상태머신

```
[깃발]
  → init(게임상태1, 내승0, AI승0, 목표승3, 라운드1, 베스트ms9999, 최종결과0)
  → broadcast 게임시작        (카우보이=대기코스튬, 배너 숨김)
  → broadcast 라운드시작      (첫 라운드)
   │
   ▼
[라운드시작]  라운드상태 ← 0
   - DRAW배너: "준비..." 표시
   - 카우보이 둘 다 대기 코스튬
   - AI반응 ← 라운드별 랜덤값 (라운드 갈수록 빨라짐)
   - 랜덤 대기 1.5~4초  ─── 이 사이 스페이스 누르면? → 부정출발 감시
   │                                              │
   │ (랜덤 대기 중 스페이스 입력)                  ▼
   │                                    [부정출발] 라운드결과←3
   ▼ (대기 끝, 정상)                       broadcast 라운드끝(FOUL, 플레이어 쓰러짐)
[신호]  broadcast 신호
   - DRAW배너: "DRAW!" 번쩍 + 총소리
   - 신호시각 ← timer,  라운드상태 ← 1
   - AI: 신호 받고 AI반응 초 후 자동 사격(타이머)
   - 플레이어: 신호 후 스페이스 누르면 내반응ms 기록
   │
   ▼ (먼저 사격한 쪽 판정)
[라운드끝]
   - 내반응(스페이스 timer) < AI반응  → 라운드결과1 (플레이어 승, AI 쓰러짐)
   - AI반응 먼저 경과            → 라운드결과2 (AI 승, 플레이어 쓰러짐)
   - 승자 카우보이 사격 코스튬 / 패자 쓰러짐 코스튬
   - 결과 배너(WIN/LOSE/FOUL) 표시 + 효과음
   - 점수 갱신(내승/AI승 +1), 베스트ms 갱신
   ▼
[승패 검사]
   - 내승 ≥ 목표승 → 최종결과1, 게임상태0 → VICTORY 배너
   - AI승 ≥ 목표승 → 최종결과2, 게임상태0 → DEFEAT 배너
   - 아니면 → 라운드+1 → 잠깐 대기 → broadcast 라운드시작 (반복)
   ▼ [깃발 재클릭] → 처음으로
```

---

## 7. 메커닉 상세

### 7.1 Stage — 대결 진행(핵심) 

라운드 1판 전체를 Stage 의 `라운드시작` 핸들러 하나가 순서대로 처리한다. 핵심 3요소: **랜덤 대기 + 부정출발 감시**, **신호 발신**, **선착 판정**.

```
when receive 라운드시작:
  라운드상태 ← 0
  라운드결과 ← 0
  내반응ms ← 0
  # 라운드별 AI 반응시간: 라운드 갈수록 빨라짐 (0.30~0.60초 → 라운드마다 약간 감소)
  AI반응 ← (pick random 0.45 to 0.70) - (라운드 - 1) * 0.05
  if AI반응 < 0.28:  AI반응 ← 0.28        # 하한(너무 빠르면 이길 수 없음 → 최소 0.28초 보장)
  broadcast 라운드시작 처리됨 (배너/카우보이는 이 방송으로 대기포즈 — 또는 같은 방송 핸들러로)
  # --- 랜덤 대기 + 부정출발 감시 ---
  대기시간 ← pick random 1.5 to 4.0
  reset timer                              # 부정출발 측정 기준
  부정 ← 0
  repeat until (timer ≥ 대기시간):
    if key space pressed?:                 # 신호 전 입력 = 부정출발
      부정 ← 1
      stop this script (→ 부정출발 처리로)  # 아래 부정 분기로
    # (구현: repeat until 조건에 (timer≥대기시간) OR (key space) 를 넣고, 빠져나온 뒤 원인 판별)
  # repeat until 빠져나옴: 원인 판별
  if (key space pressed?) AND (timer < 대기시간):
    # 부정출발
    라운드결과 ← 3
    라운드상태 ← 2
    broadcast 라운드끝
    stop this script
  # --- 정상: 신호 발신 ---
  신호시각 ← timer
  라운드상태 ← 1
  broadcast 신호
  # --- 선착 판정: 플레이어 스페이스 vs AI반응 시간 ---
  wait until (key space pressed?) OR (timer ≥ 신호시각 + AI반응)
  if (key space pressed?) AND ((timer - 신호시각) < AI반응):
    # 플레이어가 AI반응 시간보다 먼저 눌렀다 → 플레이어 승
    내반응ms ← round((timer - 신호시각) * 1000)
    라운드결과 ← 1
  else:
    # AI반응 시간이 먼저 경과(플레이어가 못 눌렀거나 느림) → AI 승
    내반응ms ← round((timer - 신호시각) * 1000)   # 참고용 표시(느린 기록)
    라운드결과 ← 2
  라운드상태 ← 2
  broadcast 라운드끝
```

> **부정출발 감시 구현 정석(Scratch)**: `repeat until ((timer ≥ 대기시간) OR (key space pressed?))` 로 루프를 돌리고, 루프 탈출 후 `if (key space pressed?) AND (timer < 대기시간)` 이면 부정출발. 이 패턴이 stop-this-script 보다 블록 매핑이 깔끔하다. 빌더는 이 방식 권장.
> **timer 기준**: `reset timer` 는 대기 시작 시 한 번. 신호 발신 시 `신호시각 ← timer` 로 신호 순간을 기록. 반응시간 = `(timer - 신호시각)`. ms 변환은 `× 1000` 후 `round`.
> **AI반응 라운드 스케일링**: 라운드1 ≈ 0.45~0.70초, 라운드2 ≈ 0.40~0.65초 ... 점점 빨라져 긴장감. 하한 0.28초로 묶어 사람이 절대 못 이기는 상황 방지(아동 친화).
> **AI 사격 연출 타이밍**: AI 카우보이는 `신호` 를 받고 `wait AI반응` 후 사격 코스튬으로 바꾼다(7.3). 단, 라운드 승패의 **판정**은 위 Stage 스크립트가 단독으로 한다(연출과 판정 분리 → 동기화 버그 방지).

### 7.2 플레이어 카우보이 (왼쪽)

신호가 뜨면(라운드상태=1) 스페이스를 누른 순간 사격 코스튬. 라운드 결과에 따라 승리(사격 자세 유지) 또는 쓰러짐(부정출발/AI승) 코스튬.

```
when flag clicked:
  set x to -150, set y to -40
  point in direction 90
  switch costume p_ready
  show

when receive 라운드시작:
  switch costume p_ready          # 대기 자세로 리셋
  point in direction 90

when receive 신호:
  # 신호 후 스페이스 누르면 사격 포즈(연출만 — 판정은 Stage)
  wait until (key space pressed?) OR (라운드상태 = 2)
  if 라운드상태 = 1:              # 아직 라운드 진행 중(=내가 눌러서 깸)
    switch costume p_shoot
    play sound shot (pitch 0)

when receive 라운드끝:
  if 라운드결과 = 1:              # 내가 이김
    switch costume p_shoot
  if 라운드결과 = 2 OR 라운드결과 = 3:   # AI 승 또는 부정출발 → 내가 쓰러짐
    switch costume p_down
```

### 7.3 AI 카우보이 (오른쪽)

신호 후 `AI반응` 초가 지나면 사격 코스튬. 라운드 결과에 따라 승리/쓰러짐.

```
when flag clicked:
  set x to 150, set y to -40
  point in direction 90
  set rotation style: left-right    # 좌우반전으로 플레이어를 바라봄(또는 코스튬 자체를 좌향으로 그림)
  switch costume a_ready
  show

when receive 라운드시작:
  switch costume a_ready

when receive 신호:
  wait AI반응 seconds              # 라운드별 AI 반응시간
  if 라운드상태 = 1:              # 아직 플레이어가 안 끝냈으면 AI가 쏨(연출)
    switch costume a_shoot
    play sound shot (pitch 0)

when receive 라운드끝:
  if 라운드결과 = 2:              # AI가 이김
    switch costume a_shoot
  if 라운드결과 = 1 OR 라운드결과 = 3:   # 플레이어 승 또는 부정출발(플레이어 반칙이지만 연출상 AI는 멀쩡 → a_shoot 또는 a_ready)
    switch costume a_down          # 플레이어 승이면 AI 쓰러짐
```

> 부정출발(라운드결과=3)은 플레이어 반칙 패 → 플레이어가 쓰러지고 AI는 멀쩡(`a_ready` 유지). 위 분기에서 라운드결과=3일 때 AI는 `a_down` 대신 `a_ready`/`a_shoot` 가 자연스럽다. **빌더 권장 분기**: AI는 `if 라운드결과=1 → a_down`, `else → a_shoot`(2번 승리) / 부정출발(3)은 `a_shoot`(AI가 의기양양). 아래 8장 블록 트리에 반영.

### 7.4 DRAW 신호 배너

"준비..." → (랜덤 대기) → "DRAW!" 번쩍.

```
when flag clicked:
  goto 0, 60
  hide

when receive 라운드시작:
  switch costume ready            # "준비..." 텍스트
  show

when receive 신호:
  switch costume draw             # "DRAW!" 큰 글자
  # 번쩍 연출
  repeat 3:
    set size to 130
    wait 0.06
    set size to 100
    wait 0.06
  # 라운드 끝나면 숨김
  wait until 라운드상태 = 2
  hide

when receive 라운드끝:
  hide                            # 부정출발 등으로 신호 없이 끝난 경우도 숨김
```

### 7.5 결과 배너 + 최종 판정

라운드 결과(WIN/LOSE/FOUL) 표시 → 점수 갱신 → 베스트 갱신 → 최종 승패 검사. 이 흐름은 Stage 가 점수/판정을 담당하고, 결과배너 sprite 는 코스튬만 띄운다(pong 결과배너 패턴 확장).

Stage 의 라운드끝 핸들러:
```
when receive 라운드끝:
  # 점수 갱신
  if 라운드결과 = 1:  내승 ← 내승 + 1
  if 라운드결과 = 2:  AI승 ← AI승 + 1
  if 라운드결과 = 3:  AI승 ← AI승 + 1     # 부정출발도 AI 승점
  # 베스트 갱신(정상 승리 때만 — 부정/패배 기록은 베스트 제외)
  if (라운드결과 = 1) AND (내반응ms < 베스트ms):  베스트ms ← 내반응ms
  wait 1.6                                # 결과 연출 감상
  # 최종 승패 검사
  if 내승 ≥ 목표승:
    최종결과 ← 1
    게임상태 ← 0
    broadcast 최종결과
    stop this script
  if AI승 ≥ 목표승:
    최종결과 ← 2
    게임상태 ← 0
    broadcast 최종결과
    stop this script
  # 다음 라운드
  라운드 ← 라운드 + 1
  wait 0.4
  broadcast 라운드시작
```

결과배너 sprite:
```
when flag clicked:
  goto 0, 0
  go to front
  hide

when receive 라운드끝:
  if 라운드결과 = 1:  switch costume win
  if 라운드결과 = 2:  switch costume lose
  if 라운드결과 = 3:  switch costume foul
  show
  play sound (라운드결과=1 ? win_sound : lose_sound)
  wait 1.4
  hide

when receive 최종결과:
  if 최종결과 = 1:  switch costume victory
  else:            switch costume defeat
  show
```

---

## 8. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  게임상태 ← 1
  내승 ← 0
  AI승 ← 0
  목표승 ← 3
  라운드 ← 1
  라운드상태 ← 0
  베스트ms ← 9999
  내반응ms ← 0
  최종결과 ← 0
  broadcast 게임시작
  broadcast 라운드시작

when receive 라운드시작:
  라운드상태 ← 0
  라운드결과 ← 0
  내반응ms ← 0
  AI반응 ← (pick random 0.45 to 0.70) - (라운드 - 1) * 0.05
  if AI반응 < 0.28:  AI반응 ← 0.28
  대기시간 ← pick random 1.5 to 4.0          # 임시: 글로벌 varWait13 또는 인라인
  reset timer
  repeat until (timer ≥ 대기시간) OR (key space pressed?):
    (빈 루프 / wait 0.005)
  if (key space pressed?) AND (timer < 대기시간):
    라운드결과 ← 3
    라운드상태 ← 2
    broadcast 라운드끝
    stop this script
  신호시각 ← timer
  라운드상태 ← 1
  broadcast 신호
  wait until (key space pressed?) OR (timer ≥ (신호시각 + AI반응))
  if (key space pressed?) AND ((timer - 신호시각) < AI반응):
    내반응ms ← round((timer - 신호시각) * 1000)
    라운드결과 ← 1
  else:
    내반응ms ← round((timer - 신호시각) * 1000)
    라운드결과 ← 2
  라운드상태 ← 2
  broadcast 라운드끝

when receive 라운드끝:
  if 라운드결과 = 1:  내승 ← 내승 + 1
  if 라운드결과 = 2:  AI승 ← AI승 + 1
  if 라운드결과 = 3:  AI승 ← AI승 + 1
  if (라운드결과 = 1) AND (내반응ms < 베스트ms):  베스트ms ← 내반응ms
  wait 1.6
  if 내승 ≥ 목표승:
    최종결과 ← 1
    게임상태 ← 0
    broadcast 최종결과
    stop this script
  if AI승 ≥ 목표승:
    최종결과 ← 2
    게임상태 ← 0
    broadcast 최종결과
    stop this script
  라운드 ← 라운드 + 1
  wait 0.4
  broadcast 라운드시작
```

> 임시 변수 `대기시간`(`varWait13`)을 Stage 글로벌로 1개 추가. 인라인 `pick random` 을 `repeat until` 조건과 `if` 두 곳에서 같은 값으로 써야 하므로 변수로 저장 필요(랜덤은 매 평가마다 달라지므로 반드시 변수에 한 번 담는다).

### 플레이어

```
when flag clicked:
  goto -150, -40
  point in direction 90
  switch costume p_ready
  size 100
  show

when receive 라운드시작:
  switch costume p_ready

when receive 신호:
  wait until (key space pressed?) OR (라운드상태 = 2)
  if 라운드상태 = 1:
    switch costume p_shoot
    play sound shot

when receive 라운드끝:
  if 라운드결과 = 1:  switch costume p_shoot
  else:  switch costume p_down       # 라운드결과 2(AI승) 또는 3(부정출발) → 쓰러짐
```

### AI

```
when flag clicked:
  goto 150, -40
  point in direction 90
  switch costume a_ready
  size 100
  show

when receive 라운드시작:
  switch costume a_ready

when receive 신호:
  wait AI반응 seconds
  if 라운드상태 = 1:
    switch costume a_shoot
    play sound shot

when receive 라운드끝:
  if 라운드결과 = 1:  switch costume a_down     # 플레이어 승 → AI 쓰러짐
  else:  switch costume a_shoot                 # AI승(2) 또는 부정출발(3) → AI 멀쩡/사격
```

### DRAW배너

```
when flag clicked:
  goto 0, 60
  size 100
  hide

when receive 라운드시작:
  switch costume ready
  show

when receive 신호:
  switch costume draw
  repeat 3:
    set size to 130
    wait 0.06
    set size to 100
    wait 0.06
  wait until 라운드상태 = 2
  hide

when receive 라운드끝:
  hide
```

### 결과배너

```
when flag clicked:
  goto 0, 0
  go to front
  size 100
  hide

when receive 라운드끝:
  if 라운드결과 = 1:  switch costume win
  if 라운드결과 = 2:  switch costume lose
  if 라운드결과 = 3:  switch costume foul
  show
  if 라운드결과 = 1:  play sound win_sound
  else:              play sound lose_sound
  wait 1.4
  hide

when receive 최종결과:
  if 최종결과 = 1:  switch costume victory
  else:            switch costume defeat
  go to front
  show
```

---

## 9. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| bg.svg | SVG (인라인) | 480×360. 석양 하늘 그라데이션(주황→빨강) + 가운데 위쪽 노란 태양 원 + 하단 사막 갈색 대지 + 메사 실루엣 2~3개 + 회전초 실루엣 1개 |
| p_ready.svg | SVG (인라인) | 플레이어 대기 자세(권총 홀스터에, 손은 옆). 오른쪽(상대)을 바라봄. 약 70×110 |
| p_shoot.svg | SVG (인라인) | 플레이어 사격 자세(권총 든 팔 뻗음, 총구 섬광). 같은 캔버스 크기 |
| p_down.svg | SVG (인라인) | 플레이어 쓰러짐(눈 X, 모자 떨어짐, 누운 자세) |
| a_ready.svg | SVG (인라인) | AI 대기 자세. 왼쪽을 바라봄(플레이어와 색/모자 구분 — 예: 검은 모자/조끼) |
| a_shoot.svg | SVG (인라인) | AI 사격 자세 |
| a_down.svg | SVG (인라인) | AI 쓰러짐 |
| ready.svg | SVG (인라인) | DRAW배너 코스튬1: "준비..." 작은 회색/베이지 텍스트 |
| draw.svg | SVG (인라인) | DRAW배너 코스튬2: "DRAW!" 크고 굵은 빨강/노랑 텍스트(테두리) |
| win.svg | SVG (인라인) | 결과배너: "YOU WIN!" 초록 |
| lose.svg | SVG (인라인) | 결과배너: "YOU LOSE" 빨강 |
| foul.svg | SVG (인라인) | 결과배너: "너무 빨라요! 반칙!"(FOUL) 주황 |
| victory.svg | SVG (인라인) | 결과배너: "VICTORY!" 금색 큰 배너 |
| defeat.svg | SVG (인라인) | 결과배너: "DEFEAT" 회색/빨강 큰 배너 |
| shot.wav | WAV (assets/) | 총소리("탕"). 기존 `games/duck-hunt/assets/pop.wav` 복사 후 피치 조절로 사용 가능 |
| draw_bell.wav | WAV (assets/) | 신호 순간 벨/땡 소리(선택). 없으면 신호 시 shot.wav 대신 pop @ 높은 피치 |
| win_sound.wav / lose_sound.wav | WAV (assets/) | 라운드 결과음(선택, pop.wav 피치 재사용 가능) |

> WAV 는 `games/duck-hunt/assets/pop.wav` 또는 `games/car-race/assets/pop.wav` 를 복사해 `shot.wav` 로 쓰고, 피치(`sound_seteffectto` PITCH)로 변주: 사격 피치 0, 신호 벨 피치 +400, 부정출발 피치 -300. 최소 1개(pop.wav)만 있어도 동작.
> 카우보이 코스튬은 같은 캔버스 크기/rotationCenter 로 그려 코스튬 전환 시 위치 흔들림 없게.

assets/ 폴더: 최소 `pop.wav`(→shot 으로 사용). 나머지 SVG 는 build.py 인라인.

---

## 10. 변수/리스트/메시지 요약 (ID 컨벤션)

- 글로벌 변수 12개: `varState01`(게임상태) `varPWins02`(내승) `varAWins03`(AI승) `varTarget04`(목표승) `varRound05`(라운드) `varRStatus06`(라운드상태) `varAIRT07`(AI반응) `varPRT08`(내반응ms) `varBest09`(베스트ms) `varRResult10`(라운드결과) `varFinal11`(최종결과) `varSigT12`(신호시각)
- 추가 임시 글로벌: `varWait13`(대기시간 — 랜덤 대기값 저장)
- 리스트: 없음
- broadcasts 5개: `brStart01`(게임시작) `brRoundStart02`(라운드시작) `brDraw03`(신호) `brRoundEnd04`(라운드끝) `brFinal05`(최종결과)
- 모니터(상단 표시): `내승`(좌상단), `AI승`(우상단), `베스트ms`(상단 중앙), `내반응ms`(베스트 옆) — 총 4개. `라운드`도 선택 표시.

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **게임상태 broadcast + 깃발 재시작 + 결과 배너(win/lose 코스튬 분기 + `결과` 값으로 switch)**: `games/pong/build.py`. 결과배너 sprite 구조를 그대로 가져와 코스튬을 5개(win/lose/foul/victory/defeat)로 확장.
- **라운드 진행(라운드+1, 다음 라운드 broadcast, 라운드별 난이도 스케일링) + 코스튬 전환 연출(대기↔사격↔쓰러짐)**: `games/duck-hunt/build.py`(라운드 ramp + 오리 fly↔hit 코스튬 전환). 카우보이 3코스튬 전환이 오리 코스튬 전환과 같은 패턴.
- **키 입력(`sensing_keypressed`) + `wait until`/`repeat until` 조건 분기**: 거의 모든 게임에 존재(`games/flappy-bird`, `games/geometry-dash` 의 스페이스 입력). 여기선 단일 키(스페이스)만.
- **`timer`(`sensing_timer`) + `reset timer`(`sensing_resettimer`)로 시간 측정**: 신규 패턴. 기존 게임에 직접 동일 사례는 적으나, `wait until (timer ≥ ...)` 형태로 단순. ms 변환은 `operator_round((timer - 신호시각) * 1000)`.
- **단일 흐름 상태머신(클론·리스트 없음)**: `games/pong/build.py` 보다 단순(물리 없음). Stage 한 스크립트가 라운드 1판을 순차 처리.

빌더는 pong build.py 를 베이스로: (1) 좌/우 패들 → 좌/우 카우보이(고정 위치, 3코스튬), (2) 공 sprite 제거(물리 없음), (3) Stage 의 승패 watcher → 라운드 대결 스크립트(랜덤 대기 + 부정출발 감시 + 신호 + timer 선착 판정)로 교체, (4) 결과 배너 코스튬 2→5개 확장, (5) DRAW배너 sprite 신규(번쩍 연출), (6) 배경을 코트 → 석양으로 교체.

**필요한 블록 opcode (pong 대비 추가/확인)**:
- `sensing_timer` (반응시간 측정), `sensing_resettimer` (대기 기준 리셋)
- `sensing_keypressed` (KEY_OPTION="space")
- `operator_round`(ms 정수화), `operator_mult`/`operator_subtract`(반응시간 계산), `operator_random`(대기시간·AI반응)
- `control_wait_until`, `control_repeat_until`, `control_wait`(AI반응 초 대기)
- `sound_seteffectto`(PITCH 변주, 선택)
- 나머지(`event_broadcast`, `data_setvariableto`, `looks_switchcostumeto`, `looks_show/hide`, `looks_setsizeto`, `motion_gotoxy`, `operator_gt/lt/and`)는 pong/duck-hunt 에 이미 존재.

---

## 12. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과 / `project.json` JSON 로드 OK
2. targets 수: 5 (Stage, 플레이어, AI, DRAW배너, 결과배너)
3. Stage 변수 12개 + 임시(대기시간) 등록 / 리스트 0개
4. Broadcasts 5개(게임시작/라운드시작/신호/라운드끝/최종결과) 등록
5. Stage 라운드시작 핸들러에:
   - `operator_random`(1.5~4.0)으로 대기시간 변수 설정 + `sensing_resettimer`
   - `repeat until ((timer ≥ 대기시간) OR (key space))` 부정출발 감시 루프 존재
   - 탈출 후 `if (key space) AND (timer < 대기시간)` → 라운드결과=3 + broadcast 라운드끝 (부정출발 분기) 존재
   - 정상 분기: `신호시각 ← timer`, `라운드상태 ← 1`, `broadcast 신호` 존재
   - `wait until ((key space) OR (timer ≥ 신호시각+AI반응))` + 선착 판정(`(timer-신호시각) < AI반응` → 결과1, else 결과2) 존재
   - `내반응ms ← round((timer - 신호시각) * 1000)` (`operator_round`/`operator_mult`) 존재
6. Stage 라운드끝 핸들러: 점수 갱신(결과1→내승+1, 결과2/3→AI승+1) + `if (결과1 AND 내반응ms<베스트ms) → 베스트ms 갱신` + 최종 승패 검사(목표승 도달 → 게임상태0 + broadcast 최종결과) + else 라운드+1 + broadcast 라운드시작 존재
7. 라운드별 AI반응 스케일링: `AI반응 ← random - (라운드-1)*0.05` + 하한 0.28 clamp 존재
8. 플레이어/AI sprite 각 3코스튬(ready/shoot/down) + 라운드끝 결과값 분기로 코스튬 전환 존재. AI는 `신호` 받고 `wait AI반응` 후 사격 코스튬(연출) 존재
9. DRAW배너: 라운드시작 → ready 코스튬 show, 신호 → draw 코스튬 + 크기 번쩍(repeat) 연출 존재
10. 결과배너 코스튬 5개(win/lose/foul/victory/defeat) + 라운드끝 결과값 분기 + 최종결과 분기 존재
11. monitors: 내승/AI승/베스트ms/내반응ms 표시
12. 자산: SVG 14개(bg + 카우보이6 + 배너 ready/draw + 결과5) + WAV(최소 pop.wav→shot), MD5 일치
13. 블록 카운트 130~200 범위
14. (동작 검증) 신호 전 스페이스 → FOUL(플레이어 쓰러짐, AI 멀쩡, AI 승점) / 신호 후 빠른 스페이스 → WIN(AI 쓰러짐, 내반응ms 기록·베스트 갱신) / 느리거나 안 누름 → LOSE(플레이어 쓰러짐) / 라운드 갈수록 AI 빨라짐 / 한쪽 3승 → VICTORY/DEFEAT 배너 후 종료

---

## 13. 빌드 카운트 예상

- Stage: ~70 블록 (init + 라운드 대결 스크립트(랜덤대기+부정감시+신호+선착판정) + 라운드끝 점수/최종판정)
- 플레이어: ~20 블록 (초기화 + 3 핸들러 코스튬 분기)
- AI: ~22 블록 (초기화 + wait AI반응 사격 + 결과 코스튬 분기)
- DRAW배너: ~20 블록 (준비/DRAW 코스튬 + 번쩍 repeat)
- 결과배너: ~30 블록 (라운드결과 3분기 + 최종 2분기 + 사운드)
- **총합 예상: 150~190 블록** (★★ 범위 — 물리/클론/리스트 없이 timer 측정 + 부정출발 판정이 핵심. 난이도 중하)

---

## 14. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (스페이스 1키 — "번쩍이면 눌러!" 즉시 이해)
- [x] 추상 학습 콘셉트 없음 (반응속도 게임. 수학·과학 개념 매핑 전혀 없음. ms 표시는 "내 기록" 자랑거리일 뿐 학습 강요 아님)
- [x] 즉시 이해되는 룰 (DRAW 뜨면 누르기, 먼저 누른 쪽 승, 미리 누르면 반칙)
- [x] 긴장감/연출 (석양 배경, "준비..." 후 랜덤 대기의 조마조마함, 번쩍 신호, 총 쏘는 포즈 + 쓰러지는 상대)
- [x] 도전감 (라운드 갈수록 AI가 빨라짐) + 이길 수 있는 난이도(AI반응 하한 0.28초로 사람이 이길 여지 보장)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭). 5판 3선승의 짧은 매치
- [x] 서부 결투 = 누구나 아는 클래식 상황 — 검증된 긴장 메커닉
