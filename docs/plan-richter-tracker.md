# 🌋 리히터 진앙 추적 — 구현 계획

> **주제**: 리히터 매그니튜드 — 진폭 10배 차이 = 매그니튜드 1 차이
> **카테고리**: 학습형 (지수/로그)
> **난이도**: ★★★ (블록 ~200개)
> **폴더**: `games/richter-tracker/`
> **출력**: `리히터_진앙_추적.sb3`
> **베이스**: `games/decibel-dj/build.py` (라운드+슬라이더+log 패턴 90% 재사용)

## 학습 목표

플레이어가 게임 중 다음을 *체감* 하도록 한다.

1. **매그니튜드 정의** — `M = log₁₀(A / A₀)` — 진폭 비의 상용로그
2. **두 지진의 매그니튜드 차** — `ΔM = log₁₀(A_max / A_min)`
3. **"매그니튜드 1 차이 = 진폭 10배"** — 정수 ΔM 라운드(1, 2, 3, 4)에서 비율을 눈으로 확인
4. **로그 스케일 시각화** — 진폭 막대를 로그 스케일로 그려, 10000:1 비율도 한 화면에 표현 가능함을 직관적으로 보여줌

## 게임 한 줄

두 도시(A, B) 의 지진계에 진폭이 표시된다. 슬라이더로 두 지진의 매그니튜드 차 ΔM 을 추측해 ±0.3 이내로 맞추면 정답. 5라운드 안에 최대한 많이 맞춰라.

## 화면 레이아웃 (480×360)

```
┌────────────────────────────────────────────────┐
│ 점수 / 라운드 / 남은시간                        │ ← HUD (상단)
├────────────────────────────────────────────────┤
│  ┌─────────────┐         ┌─────────────┐       │
│  │   A 도시    │         │   B 도시    │       │
│  │   진폭바    │         │   진폭바    │       │ ← 로그스케일 막대
│  │   A_amp =   │         │   B_amp =   │       │
│  └─────────────┘         └─────────────┘       │
│                                                │
│   ── 내답ΔM 슬라이더 (0.0 ~ 5.0) ──            │
│                                                │
│           판정 풍선: "정답!" / "차이 X.X"      │
│                                                │
│   힌트 ▼ 버튼 — 정답 ΔM 노출 + 비율 학습 텍스트 │
└────────────────────────────────────────────────┘
```

### SVG ↔ Scratch 좌표

- `scratch_x = svg_x - 240`
- `scratch_y = 180 - svg_y`
- 진폭 막대 SVG 는 60×30 짜리 작은 sprite. y 좌표를 base 로 두고, **세로 길이(size) 가 `log₁₀(amp)` 에 비례** 하도록 동적으로 stretch.

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **시계A** (지진계 A) | `seismoA` (빨강 막대) | 위치 (-100, +30), size = `20 * log₁₀(A_amp)` 로 키 변화 |
| **시계B** (지진계 B) | `seismoB` (파랑 막대) | 위치 (+100, +30), size = `20 * log₁₀(B_amp)` 로 키 변화 |
| **판정** | 보라 원 (느낌표) | 화면 하단 가운데, `looks_say` 로 V_FEEDBACK 표시 |
| **힌트버튼** | 보라 라운드 박스 ("힌트 ▼") | 클릭 시 BR_HINT 송신 |
| **Background** | 클럽 톤 → 지진학 톤(어두운 갈색/녹색)으로 변경 | 두 패널 라벨 "A 도시" / "B 도시" 정적 텍스트 |

**사운드**: `pop.wav` (재사용, 정답/클릭 효과음).

## 변수 / 메시지

```
변수 (전역)
  V_A_AMP     A 도시 진폭 (1 ~ 100000)
  V_B_AMP     B 도시 진폭 (1 ~ 100000)
  V_A0        기준 진폭 (1, 고정)
  V_MA        도시 A 매그니튜드 = log(A_amp / A0)   (참고용 표시)
  V_MB        도시 B 매그니튜드 = log(B_amp / A0)
  V_DM_ANS    정답 ΔM = |MA - MB| = log(max/min)
  V_DM_USER   슬라이더 입력값 (0.0 ~ 5.0)
  V_DIFF      |V_DM_USER - V_DM_ANS|
  V_RATIO     A/B 또는 B/A 중 큰 쪽 비율 (힌트 표시용)
  V_SCORE     점수
  V_ROUND     현재 라운드 (1~5+)
  V_TIME      남은시간 (60s)
  V_FEEDBACK  판정 메시지 ("준비" / "정답! +1" / "차이 X.X")
  V_HINT      힌트 텍스트 ("정답: 2.0 ΔM = 진폭 100배")
  V_GAMEOVER  0/1

메시지
  BR_START      게임 시작
  BR_NEW_ROUND  새 라운드 시작
  BR_TRY        Space 눌러 시도
  BR_HINT       힌트 보기
  BR_GAMEOVER
  BR_REDRAW     진폭 막대 크기 갱신 (sprite 가 수신)
```

## 게임 흐름

```
[초록 깃발]
   ↓
초기화: V_SCORE=0, V_ROUND=0, V_TIME=60, V_A0=1, V_DM_USER=2.5, V_GAMEOVER=0
   ↓
broadcast BR_NEW_ROUND
   ↓
[메인 루프 = 타이머 loop @ Stage]
   ├─ 매 1s : V_TIME -= 1, V_TIME <= 0 → BR_GAMEOVER
   └─ Space → BR_TRY
        ├─ |V_DM_USER - V_DM_ANS| < 0.3 → V_SCORE += 1, BR_NEW_ROUND
        └─ else → V_FEEDBACK = "차이 X.X"
   ↓
[새 라운드 핸들러]
   ├─ V_ROUND += 1
   ├─ 라운드 1~3 고정: 정수 ΔM (10:1, 100:1, 1000:1)
   ├─ 라운드 4~5 자유: 무작위 ΔM (random 0..4 정수 → A=10^x, B=10^(x+ΔM))
   ├─ V_MA, V_MB, V_DM_ANS 계산
   └─ broadcast BR_REDRAW → 두 진폭 막대 sprite 가 size 갱신
```

## 핵심 스크립트 (의사코드)

### Stage — 초기화 + 타이머 loop

```
when flag clicked
   초기화 모든 변수 (V_A0=1, V_DM_USER=2.5, ...)
   broadcast BR_NEW_ROUND

when flag clicked
   forever
      wait 1
      if V_GAMEOVER == 0
         change V_TIME by -1
         if V_TIME < 1 → broadcast BR_GAMEOVER
```

### Stage — 새 라운드 (라운드별 분기)

```
when I receive BR_NEW_ROUND
   change V_ROUND by 1
   set V_HINT = ""
   set V_FEEDBACK = "ΔM 을 맞춰라"

   # 라운드 1~5 고정 시나리오
   FIXED = [
     (R=1,  A_amp=100,    B_amp=10)        # ΔM=1, ratio=10
     (R=2,  A_amp=10000,  B_amp=100)       # ΔM=2, ratio=100
     (R=3,  A_amp=100000, B_amp=100)       # ΔM=3, ratio=1000
     (R=4,  A_amp=10000,  B_amp=10)        # ΔM=3
     (R=5,  A_amp=100000, B_amp=10)        # ΔM=4
   ]
   if V_ROUND in FIXED → set A_amp, B_amp

   # R >= 6: random 10^a vs 10^(a+k), k random 1..4
   else
     base   = 10^(random 1..3)
     delta  = random 1..4  (정수)
     V_A_AMP = base * 10^delta
     V_B_AMP = base
     # (50% 확률로 swap)
     if (random 0..1) < 0.5
        swap A_amp, B_amp

   # 매그니튜드 계산
   V_MA = log(V_A_AMP / V_A0)
   V_MB = log(V_B_AMP / V_A0)
   V_DM_ANS = abs(V_MA - V_MB)
   # ratio = bigger / smaller (힌트용)
   if V_A_AMP > V_B_AMP
      V_RATIO = V_A_AMP / V_B_AMP
   else
      V_RATIO = V_B_AMP / V_A_AMP

   broadcast BR_REDRAW
```

### Stage — 시도 (Space)

```
when space pressed
   broadcast BR_TRY

when I receive BR_TRY
   if V_GAMEOVER == 0
      V_DIFF = abs(V_DM_USER - V_DM_ANS)
      if V_DIFF < 0.3
         V_SCORE += 1
         V_FEEDBACK = "정답! +1"
         play pop.wav
         wait 0.5
         broadcast BR_NEW_ROUND
      else
         V_FEEDBACK = join("차이 ", join(round(diff·10)/10, " ΔM"))
```

### Stage — 힌트 / 게임오버

```
when I receive BR_HINT
   # join("정답: ", DM_ANS_rounded, " ΔM = 진폭 ", RATIO_rounded, " 배")
   V_HINT = "정답: 2.0 ΔM = 진폭 100 배"

when I receive BR_GAMEOVER
   V_GAMEOVER = 1
   V_FEEDBACK = join("종료! 점수 ", V_SCORE)
```

### 진폭 막대 sprite — 로그 스케일 redraw

```
when flag clicked
   go to (-100, 30)
   size = 100
   show

when I receive BR_REDRAW
   # size = 20 * log10(A_amp), 최소 20 보장
   # log(0) 회피: A_amp 가 항상 >= 1 이므로 안전
   set my size to (20 * log(V_A_AMP)) + 20
```

> 진폭 1 → size 20, 진폭 10 → size 40, 진폭 100 → size 60, 진폭 100000 → size 120. 한 화면에 5자릿수 차이를 다 담을 수 있는 것이 로그 스케일의 의의.

## 라운드 / 진폭 표

| 라운드 | A_amp | B_amp | 정답 ΔM | 비율 | 학습 의도 |
|--------|-------|-------|---------|------|----------|
| 1 | 100 | 10 | 1.0 | 10:1 | "매그니튜드 1 차이 = 진폭 10배" 의 기본 |
| 2 | 10000 | 100 | 2.0 | 100:1 | 매그니튜드 2 차이 = 100배 |
| 3 | 100000 | 100 | 3.0 | 1000:1 | 매그니튜드 3 차이 = 1000배 |
| 4 | 10000 | 10 | 3.0 | 1000:1 | 같은 ΔM 도 절대값이 다를 수 있음 |
| 5 | 100000 | 10 | 4.0 | 10000:1 | 가장 큰 차이 (학습 정점) |
| 6+ | 무작위 | 무작위 | 정수 1~4 | 10/100/1000/10000 | 자유 라운드 |

## Monitor (HUD) 배치

| 변수 | 모드 | 위치 | 비고 |
|------|------|------|------|
| `V_DM_USER` | slider (min 0, max 5, isDiscrete=false) | (5, 200) | 핵심 입력 — 소수 입력 |
| `V_SCORE` | default | (5, 5) | |
| `V_ROUND` | default | (5, 35) | |
| `V_TIME` | default | (5, 65) | |
| `V_A_AMP` | default | (5, 100) | 좌측 |
| `V_MA` | default | (5, 130) | 좌측 |
| `V_B_AMP` | default | (330, 100) | 우측 |
| `V_MB` | default | (330, 130) | 우측 |
| `V_HINT` | large | (130, 235) | 힌트 버튼 누른 후만 |
| `V_FEEDBACK` | (모니터 X) | — | `looks_say` 로 판정 sprite 가 표시 |

## 재사용 가능한 코드

- `games/decibel-dj/build.py` 거의 그대로:
  - `BlockBuilder` 클래스 (vrep / op / mathop / cmp / round_to_1dp) 100% 재사용
  - 라운드 타이머 / Space → TRY / 힌트 버튼 클릭 / 게임오버 핸들러 구조 동일
  - 라운드 분기 if-체인 패턴 동일 (FIXED 리스트만 교체)
  - HUD monitor 배열 거의 동일 (변수 ID/이름만 교체)
- 새로 추가:
  - 진폭 막대 sprite 의 `BR_REDRAW` 수신 → size 변경 (`looks_setsizeto` + `20 * log(amp) + 20`)
  - `V_RATIO` 계산 (힌트 텍스트의 "진폭 N배" 부분)
  - 힌트 텍스트 포맷이 decibel-dj 보다 길어짐 (조인 4단계)

## 학습 포인트 (수식 + 직관)

리히터 매그니튜드의 정의:

$$ M = \log_{10}\left(\dfrac{A}{A_0}\right) $$

두 지진의 매그니튜드 차:

$$ \Delta M = M_A - M_B = \log_{10}\!\left(\dfrac{A_A}{A_0}\right) - \log_{10}\!\left(\dfrac{A_B}{A_0}\right) = \log_{10}\!\left(\dfrac{A_A}{A_B}\right) $$

즉, **ΔM = 진폭 비의 상용로그**. 따라서:

- ΔM = 1 → 진폭 10 배
- ΔM = 2 → 진폭 100 배
- ΔM = 3 → 진폭 1000 배 (예: 규모 6 vs 규모 9 지진 = 진폭 1000 배 차이!)

이 게임은 **진폭 막대를 로그 스케일로 그려서**, 100000:1 같은 큰 비율도 화면에 깔끔히 보여준다. 사용자는 슬라이더로 ΔM(정수) 을 직접 맞추며 "10배 = 1, 100배 = 2" 라는 매핑을 손에 익힌다.

Scratch 의 `operator_mathop` 블록은 `OPERATOR: "log"` 로 **상용로그(밑 10)** 를 그대로 제공한다. 그래서 추가 변환 없이 `log(A_amp / A0)` = 매그니튜드.

## 테스트 체크리스트

- [ ] `리히터_진앙_추적.sb3` 가 유효한 zip
- [ ] Stage 변수 13 개 (V_A_AMP, V_B_AMP, V_A0, V_MA, V_MB, V_DM_ANS, V_DM_USER, V_DIFF, V_RATIO, V_SCORE, V_ROUND, V_TIME, V_FEEDBACK, V_HINT, V_GAMEOVER)
- [ ] Stage broadcasts 6 개 (BR_START, BR_NEW_ROUND, BR_TRY, BR_HINT, BR_GAMEOVER, BR_REDRAW)
- [ ] 5 개 스프라이트: Stage, 시계A, 시계B, 판정, 힌트버튼
- [ ] `operator_mathop` `OPERATOR: "log"` 가 실제로 stage blocks 안에 존재 (V_MA, V_MB 계산용)
- [ ] V_DM_USER monitor 가 `mode: "slider"`, `isDiscrete: false`, `sliderMin: 0`, `sliderMax: 5`
- [ ] 라운드 1~5 분기와 R>=6 자유 분기 모두 존재
- [ ] 블록 카운트 150~300 범위 (★★★)
- [ ] BR_REDRAW 송신/수신 양쪽 모두 존재 (sprite 별 size 갱신)

## 빌드 노트

- decibel-dj 의 `db_from_intensity()` 헬퍼는 그대로 쓸 수 있지만 곱하기 10 부분만 제거 → `magnitude_from_amplitude()` 로 이름 변경 (또는 그냥 `B.mathop("log", ratio)`)
- `V_DM_ANS` 는 `|MA - MB|` 의 절대값. `operator_mathop "abs"` 사용
- 진폭 막대 sprite 2개의 `BR_REDRAW` 핸들러는 동일 구조. 변수만 V_A_AMP / V_B_AMP 로 다름
- `V_DM_USER` 슬라이더 step 은 Scratch 가 자동 (isDiscrete=false 면 연속) — 사용자가 약 0.1 단위로 움직임
- 허용 오차 0.3 → 정수 정답일 때 ±0.3 범위라 살짝 너그러움. 학습이 목적이므로 OK

## 참고

- 베이스: `games/decibel-dj/build.py` (사실상 90% 복제)
- 학습 출처: 고등학교 수학 (지수·로그) + 지구과학 (지진학)
- 사운드: `games/decibel-dj/assets/pop.wav` 재사용
