# ☢️ 반감기 광산 — 구현 계획

> **주제**: 지수 — 지수 *감쇠* 의 직관 (박테리아 디펜스의 정반대)
> **카테고리**: 학습형 + 액션
> **난이도**: ★★★ (블록 ~200개)
> **폴더**: `games/radioactive-mine/`
> **출력**: `반감기_광산.sb3`

## 학습 목표

플레이어가 게임 중 다음을 *체감* 하도록 한다.

1. **지수 감쇠의 직관** — 광물의 질량이 매 `T` 초마다 절반으로 줄어드는 모습을 *시각적 크기* 와 *점수* 로 동시에 보여준다. "지금 캘까, 더 기다릴까" 의 갈등이 곧 `N(t) = N₀ · (1/2)^(t/T)` 의 형태.
2. **반감기 `T` 의 의미** — 광물마다 반감기가 다르다. `T=1` 짜리는 1초만에 반토막, `T=5` 짜리는 5초 버틴다. 같은 시간이 흘러도 다른 비율로 감쇠.
3. **"수명" 의 로그적 계산 (보너스)** — 각 광물이 *소멸 임계* `N_min = 0.05·N₀` 에 도달하기까지 남은 시간을 `t_life = T · log₂(N/N_min)` 로 실시간 표시. 로그 = "절반을 몇 번 더 반복해야 임계에 닿나" 를 HUD 가 가르친다.

## 게임 한 줄

방사능 광물 4개가 무작위 위치에 등장한다. 각 광물은 고유한 반감기 `T`(1~5초)와 시작 질량 `N₀`(50~200)을 가지고 매 0.1초마다 질량이 줄어든다(`(1/2)^(Δt/T)`). 광물을 클릭하면 *현재* 질량이 점수에 가산된다. 60초 안에 가장 많은 질량을 캐자.

## 화면 레이아웃 (480×360)

```
┌────────────────────────────────────────────┐
│  점수: 187   남은시간: 42s   처치: 6        │  ← 상단 HUD (높이 50)
├────────────────────────────────────────────┤
│                                            │
│      ☢                ☢                    │
│         (T=2s)            (T=4s)            │ ← 광물 4개 (클론)
│                                            │   - 시간 갈수록 작아지고
│              ☢                              │     색이 흐려진다
│                (T=1s)        ☢              │
│                                 (T=3s)      │
│                                            │
└────────────────────────────────────────────┘
        ↑ 클릭으로 채굴 (현재 질량만큼 점수 가산)
```

좌표계: SVG (0~480, 0~360) ↔ Scratch (-240~240, -180~180). 광물 스폰 영역은 SVG `(40~440, 90~330)` → Scratch `(-200~200, -150~90)`.

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **Background** | `mine` (어두운 광산 벽 + 상단 HUD 영역) | 단일 SVG, 페트리 배경 톤 대신 광산 채광 콘셉트 |
| **광물** (clone-driven) | `fresh` (밝은 청록 → 시각상 N₀ 의 100%), `decayed` (회색 톤, 시각상 5% 이하) | 두 코스튬 사이 전환은 `V_MASS_NOW / V_N0` 비율로 결정 |
| **게임오버 / 결과** | `result` (60초 종료 후 큰 배너) | bacteria-defense 의 banner SVG 패턴 재사용 |

**사운드** — `assets/` 에 합성:

| 파일 | 용도 |
|------|------|
| `pick.wav` | 채굴 효과음 (밝은 1200Hz 클릭 + 880Hz 하모닉, 0.08s 감쇠) |
| `vanish.wav` | 광물 자가 소멸 시 (낮은 200Hz, 0.15s) |
| `tick.wav` | 매 10초 카운트다운 ping (단일 1500Hz 50ms) |

## 변수 / 메시지

```
변수 (전역, Stage)
  V_SCORE       총점수 (누적 채굴량)
  V_TIME_LEFT   남은 시간 (60 → 0)
  V_PICKED      처치한 광물 수 (HUD)
  V_GAMEOVER    0/1
  V_SPAWN_X     스폰 좌표 (parent → clone 전달)
  V_SPAWN_Y
  V_SPAWN_N0    스폰 시 N₀
  V_SPAWN_T     스폰 시 반감기
  V_LN_HALF     상수 ln(0.5) ≈ -0.6931471805599453 (e^ 합성용)
  V_LOG_HALF    상수 log₁₀(0.5) ≈ -0.3010299956639812 (10^ 합성용; 미사용 백업)
  V_CLONE_COUNT 현재 살아있는 광물 클론 수

변수 (광물 클론 로컬 — Sprite-local, "이 스프라이트에서만" 으로 정의)
  V_N0          이 광물의 시작 질량
  V_T_HALFLIFE  이 광물의 반감기 (초)
  V_T_BIRTH    이 광물의 출생 timer 값 (Stage 의 sensing_timer)
  V_MASS_NOW    현재 질량 (매 0.1초 갱신)
  V_LIFE_LEFT   소멸까지 남은 시간 = T·log₂(N/N_min), 광물 위 표시(보너스)

메시지
  BR_START         게임 시작
  BR_SPAWN_MORE    스폰 트리거 (Stage 가 광물 수가 적을 때 송신)
  BR_GAMEOVER
```

### 왜 클론-로컬 변수인가
박테리아 디펜스는 *모든 박테리아가 같은 r·T 로 분열* 했지만, 이 게임은 **광물마다 다른 반감기** 가 핵심이다. Scratch 의 "이 스프라이트에서만" 변수는 클론별로 독립된 값을 가지므로 (참고: Scratch 3.0 공식 동작), 클론마다 `N₀`, `T`, `t_birth` 가 다를 수 있다.

## 게임 흐름

```
[초록 깃발]
   ↓
초기화 V_SCORE=0, V_TIME_LEFT=60, V_GAMEOVER=0, V_CLONE_COUNT=0,
       V_LN_HALF=-0.6931471805599453
   ↓
sensing_resettimer  ← 모든 광물의 V_T_BIRTH 가 이 timer 기준
   ↓
broadcast BR_START
   ├─ 광물 스프라이트: 4번 반복 (각 다른 T, N₀, 좌표 세팅 후 clone)
   │
   └─ Stage: 3개 동시 루프
        ├─ A. 매 1초 V_TIME_LEFT--. 0 이 되면 V_GAMEOVER=1 + broadcast BR_GAMEOVER
        ├─ B. 매 1.5초 V_CLONE_COUNT < 4 면 스폰 좌표/T/N₀ 세팅 후 broadcast BR_SPAWN_MORE
        └─ C. (없음 — HUD 모니터가 V_SCORE / V_TIME_LEFT / V_PICKED 를 자동 표시)

광물 클론 (start_as_clone)
   ├─ 자기 위치/색/크기를 초기화: motion_gotoxy(V_SPAWN_X, V_SPAWN_Y)
   ├─ V_N0 ← V_SPAWN_N0, V_T_HALFLIFE ← V_SPAWN_T, V_T_BIRTH ← sensing_timer
   ├─ V_CLONE_COUNT++
   ├─ forever:
   │    Δt = sensing_timer - V_T_BIRTH
   │    V_MASS_NOW = V_N0 · e^((Δt / V_T_HALFLIFE) · ln(0.5))
   │                = V_N0 · 0.5^(Δt/T)
   │    size = 100 · sqrt(V_MASS_NOW / V_N0)   (시각 크기, 0.5 → 70% / 0.25 → 50%)
   │    if V_MASS_NOW < 0.05 · V_N0:
   │        switch costume → decayed
   │        play vanish.wav
   │        V_CLONE_COUNT--
   │        delete this clone
   │    wait 0.1
   │
   └─ on click:
        V_SCORE += round(V_MASS_NOW)
        V_PICKED++
        play pick.wav
        V_CLONE_COUNT--
        delete this clone
```

## 핵심 스크립트 (의사코드)

### Stage — 초기화 + 타이머

```
when flag clicked
   set V_SCORE = 0
   set V_TIME_LEFT = 60
   set V_PICKED = 0
   set V_GAMEOVER = 0
   set V_CLONE_COUNT = 0
   set V_LN_HALF = -0.6931471805599453
   reset timer
   broadcast BR_START

when I receive BR_START
   repeat until V_GAMEOVER = 1
      wait 1
      change V_TIME_LEFT by -1
      if V_TIME_LEFT <= 0
         set V_GAMEOVER = 1
         broadcast BR_GAMEOVER
```

### Stage — 스폰 디스패처

```
when I receive BR_START
   wait 0.2
   repeat until V_GAMEOVER = 1
      if V_CLONE_COUNT < 4
         set V_SPAWN_X = (pick random -200 to 200)
         set V_SPAWN_Y = (pick random -150 to 90)
         set V_SPAWN_T = (pick random 10 to 50) / 10     # 1.0 ~ 5.0 초
         set V_SPAWN_N0 = (pick random 50 to 200)
         broadcast BR_SPAWN_MORE
      wait 1.5
```

> *디스패처는 Stage 에 있다*. 광물 스프라이트는 BR_SPAWN_MORE 를 받으면 *원본만* clone 하나 만든다(이미 클론이 받는 broadcast 는 clone 하지 않게 분리).

### 광물 — clone 생성 핸들러 (원본 only)

```
when flag clicked
   hide                           # 원본 hide
   set size = 100

when I receive BR_SPAWN_MORE
   create clone of myself         # 원본만 이 핸들러를 실행 — 클론은 다른 스크립트
```

> ⚠️ 클론도 같은 이벤트를 받으므로, 원본 vs 클론 구분이 필요. **방법**: 클론은 `start_as_clone` 시 곧장 forever 루프로 진입하고, 다른 broadcast 핸들러는 갖지 않게 한다. 원본의 broadcast 핸들러는 단 하나 (`BR_SPAWN_MORE` → clone) 만 두면 클론이 받아도 무해 (클론이 또 clone 을 만들지만 V_CLONE_COUNT 검사로 막힘. 실제 무한 폭주 방지를 위해 `BR_SPAWN_MORE` 가 광물 한 마리만 만들도록 Stage 가 V_CLONE_COUNT < 4 일 때만 broadcast).

### 광물 — start_as_clone

```
when I start as a clone
   go to (V_SPAWN_X, V_SPAWN_Y)
   set V_N0 to V_SPAWN_N0                    # 클론 로컬 변수
   set V_T_HALFLIFE to V_SPAWN_T
   set V_T_BIRTH to timer                    # sensing_timer
   set V_MASS_NOW to V_N0
   switch costume → fresh
   set size to 100
   show
   change V_CLONE_COUNT by 1

   repeat until V_GAMEOVER = 1
      set V_MASS_NOW to V_N0 ·
           e^( ((timer - V_T_BIRTH) / V_T_HALFLIFE) · V_LN_HALF )
      set size to 100 · sqrt( V_MASS_NOW / V_N0 )
      set V_LIFE_LEFT to round( V_T_HALFLIFE · (log(V_MASS_NOW / (0.05·V_N0)) / log(2)) )
      if V_MASS_NOW / V_N0 < 0.30
         switch costume → decayed
      if V_MASS_NOW < 0.05 · V_N0
         play vanish.wav
         change V_CLONE_COUNT by -1
         delete this clone
      wait 0.1
```

### 광물 — 클릭 채굴

```
when this sprite clicked
   if V_GAMEOVER = 0
      change V_SCORE by round(V_MASS_NOW)
      change V_PICKED by 1
      play pick.wav
      change V_CLONE_COUNT by -1
      delete this clone
```

> ⚠️ 원본 스프라이트는 `looks_hide` 로 숨겨두므로 클릭 가능 영역이 없다. 클론만 가시화. `when this sprite clicked` 는 클론에도 적용된다 (Scratch 3.0 표준).

### 결과 배너

```
when I receive BR_GAMEOVER
   show
   say "60초 종료! 총 점수: V_SCORE, 채굴: V_PICKED" for 9999 sec
```

## 수식의 코드 구현 (핵심 포인트)

`0.5^x` 를 Scratch 의 `operator_mathop` 로 합성:

```
0.5^x  =  e^( x · ln(0.5) )

블록 구성:
  exp_arg   = operator_multiply( x_block, V_LN_HALF_var )   # x · ln(0.5)
  result    = operator_mathop( "e ^", inputs=NUM=slot(exp_arg) )
```

`x = (sensing_timer - V_T_BIRTH) / V_T_HALFLIFE` 이므로 최종:

```
V_MASS_NOW  ←  V_N0 ·  e^( ((timer - V_T_BIRTH) / V_T_HALFLIFE) · V_LN_HALF )
```

`log₂(x)` 도 동일한 패턴 (밑변환):
```
log₂(x)  =  log₁₀(x) / log₁₀(2)
         또는  ln(x) / ln(2)
```

`V_LIFE_LEFT = T · log₂(N / (0.05·N₀))` 는 보너스 HUD 용. Scratch 의 `operator_mathop("log", ...)` 는 상용로그 (밑10). plan 의 학습 포인트 (밑 변환) 가 박테리아 디펜스와 *대칭* 으로 연결된다.

## 재사용 가능한 코드

| 가져올 부분 | 출처 | 변경점 |
|------------|------|--------|
| `md5_bytes` / `num` / `text_lit` / `slot` / `mk` / `gen` / `chain` / `make_helpers` | `bacteria-defense/build.py` | 그대로 |
| `make_helpers` 의 `mathop` 클로저 | `bacteria-defense/build.py` | 그대로. `"e ^"` 와 `"log"` 사용. |
| Stage 의 "wait T → broadcast" 타이머 패턴 | `bacteria-defense/build.py` (split tick) | 광물 스폰 디스패처로 치환 |
| 클론 시작 → 좌표/속성 초기화 → forever 갱신 패턴 | `bacteria-defense/build.py` (bacterium clone) | 분열 대신 감쇠 계산 |
| `gen_costume_menu` 헬퍼 | `bacteria-defense/build.py` | 그대로 |
| 게임오버 배너 SVG + 표시 스크립트 | `bacteria-defense/build.py` (`GAME_OVER_SVG`, `build_gameover_blocks`) | 텍스트만 "60초 종료" 로 |
| WAV 합성 (`write_wav`, sine + exp envelope) | `beat-tap/build.py` (`gen_tick_wav` / `gen_miss_wav`) | pick / vanish / tick 3종 |

## 테스트 체크리스트 (verifier)

- [ ] .sb3 가 유효한 zip (`zipfile.testzip() == None`)
- [ ] `project.json` 의 `targets` 첫 요소가 Stage
- [ ] Stage 의 `variables` 에 plan 의 V_* 키가 모두 정의됨 (V_SCORE, V_TIME_LEFT, V_PICKED, V_GAMEOVER, V_SPAWN_X, V_SPAWN_Y, V_SPAWN_N0, V_SPAWN_T, V_LN_HALF, V_LOG_HALF, V_CLONE_COUNT)
- [ ] 광물 스프라이트의 `variables` 에 V_N0, V_T_HALFLIFE, V_T_BIRTH, V_MASS_NOW, V_LIFE_LEFT 5개 정의됨 (클론 로컬)
- [ ] `broadcasts` 에 BR_START, BR_SPAWN_MORE, BR_GAMEOVER 3개
- [ ] 광물 코스튬: `fresh`, `decayed` 2종
- [ ] `operator_mathop` 블록 중 `e ^` (또는 `e^`) OPERATOR 가 최소 1개 존재 → 감쇠식 구현 확인
- [ ] `operator_mathop` 의 `log` OPERATOR 가 최소 2개 (V_LIFE_LEFT 의 밑변환용 log₂)
- [ ] 총 블록 수가 ★★★ 범위 (150 ~ 300)
- [ ] 모든 블록의 parent/next 참조가 같은 sprite 안의 유효 ID
- [ ] 자산 파일 (배경 SVG, 광물 SVG 2종, 배너 SVG, WAV 3종) 모두 zip 안에 MD5 일치하는 이름으로 존재

## 빌드 노트

- **클론 수 제한**: 광물은 동시에 최대 4마리만 유지 (Stage 의 `V_CLONE_COUNT < 4` 검사). Scratch 300 클론 한도와 무관하게 화면을 깔끔하게.
- **클릭 영역 vs 시각 크기**: `looks_setsizeto(size)` 는 클릭 hit-box 도 같이 줄인다. 따라서 광물이 작아질수록 클릭이 어려워짐 — 이게 곧 학습 효과 ("늦으면 클릭조차 힘들어진다").
- **race condition**: 매 0.1초 갱신 중 timer 가 변하므로 `Δt = timer - V_T_BIRTH` 는 호출마다 다른 값. Scratch 의 reporter 는 호출 시점에 평가되므로 OK.
- **소수 정밀도**: `V_LN_HALF = -0.6931471805599453` 을 Stage 변수에 박아둔다. Scratch 의 float 는 충분한 정밀도를 가짐.
- **시각 vs 산술 일치**: `size = 100 · sqrt(N/N₀)` 이므로 N 이 0.5 가 되면 크기는 ~70%. 산술적 절반(`0.5`)과 시각적 절반(면적 기준)을 의도적으로 분리 — "산술 ≠ 시각" 학습 점 (sqrt 가 등장).

## 참고

- 메커닉 영감: `bacteria-defense` (지수 *증가*) ↔ `radioactive-mine` (지수 *감쇠*) — 같은 함수 형태, 부호만 반대.
- 학습 단원: 고1 지수와 로그 → 반감기는 대표 응용 (탄소-14, 방사성 동위원소).
