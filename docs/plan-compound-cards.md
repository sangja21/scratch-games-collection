# 💰 복리 카드 게임 — 구현 계획

> **주제**: 지수 / 복리 — `A = P · (1 + r)^n`
> **카테고리**: 학습형 (지수/로그)
> **난이도**: ★★ (메커닉 자체는 ★★, 실제 블록 ~300개로 ★★★ — 카드 풀(8종) × 3슬롯의 if-체인 unrolling 때문)
> **폴더**: `games/compound-cards/`
> **출력**: `복리_카드_게임.sb3`
> **베이스**: `whack-a-prime/build.py` (클릭 + 클론 + 변수 계산 패턴)

## 학습 목표

플레이어가 게임 중 다음을 *체감*하도록 한다.

1. **복리 = 곱셈의 누적** — `A = P · (1+r)^n` 의 본질이 매 턴 `× (1+r)` 라는 사실을 손으로 확인.
2. **이자율 1%p 차이가 누적되면 큰 차이** — 매 턴 +5% 와 +10% 의 카드 선택이 10턴 뒤 자산을 어떻게 바꾸는지 직접 비교.
3. **기하평균(연복리 평균) 의 직관** — "10턴 안에 자산을 10배로 만들려면 매 턴 평균 몇 %?" → HUD가 `r_avg = (목표/현재)^(1/턴남음) - 1` 을 실시간 표시 → 이게 **n번째 루트 = 분수 지수** 학습 포인트.
4. **기댓값과 위험** — 각 카드에 `E[r] = p·r_성공 + (1-p)·r_실패` 라벨이 붙어, 큰 r 이 반드시 더 좋은 선택은 아님을 학습.

## 게임 한 줄

자산 1000원으로 시작. 매 턴 3장의 이자율 카드(예: +5% 안전 / +15% 60% 확률 / +50% 30% 확률) 중 한 장을 골라 자산을 굴린다. 10턴 안에 자산이 10,000원에 도달하면 승리.

## 화면 레이아웃 (480×360)

```
┌────────────────────────────────────────┐
│ 자산: 1,234      턴: 3/10              │  ← HUD (상단)
│ 목표: 10,000   필요 r: 25.7%           │
├────────────────────────────────────────┤
│                                        │
│   ┌──────┐  ┌──────┐  ┌──────┐        │
│   │ +5%  │  │ +15% │  │ +50% │        │  ← 카드 3장 (클론)
│   │ p:100│  │ p:60 │  │ p:30 │        │
│   │ E:+5 │  │ E:+1 │  │ E:-20│        │
│   └──────┘  └──────┘  └──────┘        │
│                                        │
│         [클릭해서 카드 선택]            │
└────────────────────────────────────────┘
```

좌표 변환: SVG `(0,0)` 좌상단 ↔ Scratch `(-240, 180)`.
- 카드 슬롯 1: Scratch `(-150, -30)` (SVG `90, 210`)
- 카드 슬롯 2: Scratch `(   0, -30)` (SVG `240, 210`)
- 카드 슬롯 3: Scratch `( 150, -30)` (SVG `390, 210`)

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **Background** | `테이블` (1종) — 짙은 녹색 펠트 + HUD 영역 분리 | 카지노 톤 |
| **Card** (clone-driven) | `카드` (1종, SVG에 빈 텍스트 영역) — `say` 블록으로 카드 정보 표시 | 클론 3개 = 한 턴의 카드 3장 |
| **NewTurnButton** | `버튼` (1종, "다음 턴") — 클릭 시 새 카드 3장 spawn (게임 시작 시 자동 1회) | 게임 종료 시 라벨이 "다시" 로 |

**사운드**: `pop.wav` (재사용 — 카드 선택 / 성공), `alarm.wav` (재사용 — 실패 / 게임오버).

## 변수 / 메시지

```
변수 (전역)
  V_P         현재 자산 (시작 1000)
  V_GOAL      목표 자산 (10000)
  V_TURN      현재 턴 (1..10)
  V_MAXTURN   최대 턴 수 (10)
  V_STATE     게임상태 (1=진행, 0=종료)
  V_RESULT    승패 (1=승, -1=패, 0=진행)
  V_NEED_R    목표 도달에 필요한 연복리 평균 r (%) = ((V_GOAL/V_P)^(1/(V_MAXTURN-V_TURN+1)) - 1) · 100

변수 (Card 클론 로컬 — 버튼 스프라이트에 정의)
  V_CARD_SLOT 카드 슬롯 번호 (1, 2, 3 — 부모 버튼은 0)
  V_CARD_R    이 카드의 이자율 (예: 0.05, 0.15, 0.50)
  V_CARD_P    이 카드의 성공 확률 (예: 1.0, 0.6, 0.3)
  V_CARD_E    기대값 E[r] (%) = (p·r + (1-p)·(-0.5)) · 100

변수 (버튼 임시)
  V_LAST_MSG  마지막 결과 메시지 (HUD 표시용, 전역)
  V_PICK      카드 풀 인덱스 무작위 추첨 임시 (버튼 로컬)

메시지
  BR_START         게임 시작
  BR_NEW_TURN      새 턴 시작 (카드 3장 spawn)
  BR_CARD_CHOSEN   카드 선택됨 (다른 카드 클론 삭제 + 게임종료 시 정리도 동일 흐름)
  BR_GAMEOVER      게임 종료
```

## 카드 풀 (라운드별 무작위 추첨)

매 턴 아래 풀에서 무작위로 3장 뽑힘 (중복 없이). 각 카드는 (r, p) 튜플. 실패 시 자산은 ×0.5.

```
카드 풀 (총 8종):
  1. (+5%,  p=100%)  E = +5.0%        — 안전한 채권
  2. (+8%,  p=95%)   E = +5.1%        — 우량 회사채
  3. (+12%, p=85%)   E = +2.7%        — 주식 (안정)
  4. (+20%, p=70%)   E = -1.0%        — 주식 (성장)
  5. (+35%, p=55%)   E = -3.5%        — 모험 자산
  6. (+50%, p=40%)   E = -10.0%       — 투기
  7. (+100%, p=25%)  E = -12.5%       — 도박
  8. (-3%,  p=100%)  E = -3.0%        — 현금 보관 (-3% 인플레이션 보정 패널티)
```

> 모든 카드의 E[r] 가 다르므로, "기댓값이 양수인 카드만 골라도 안전한가?" 와 "10턴 안에 10배 도달" 사이의 트레이드오프가 핵심. 안전 카드(+5%)만 골라서 10턴 ≈ 1000·(1.05)^10 ≈ 1629, 즉 10배 불가능 → 어느 정도 위험을 감수해야 함.

## 좌표·계산 핵심

### 자산 곱셈

```
선택 → 무작위 굴림 r_roll ∈ [0,1]
  if r_roll < V_CARD_P:
    V_P = V_P · (1 + V_CARD_R)     # 성공
  else:
    V_P = V_P · 0.5                # 실패
  V_P = round(V_P)                 # 정수로 깔끔하게
```

### `필요 r` 계산 (학습 포인트)

```
n_left = V_MAXTURN - V_TURN + 1
ratio  = V_GOAL / V_P
필요r  = ratio^(1/n_left) - 1
       = e^(ln(ratio) / n_left) - 1     # ← Scratch 에 power 가 없어서 사용
       = (mathop("e^") of (mathop("ln") of ratio) / n_left) - 1
표시   = round(필요r · 1000) / 10        # % 소수 1자리
```

> Scratch 의 `operator_mathop` 에는 `e^`, `ln`, `log`, `10^`, `floor` 등이 있다. `x^(1/n) = e^(ln(x)/n)` 을 그대로 매핑.

### `기댓값 E[r]` 계산 (카드 생성 시 미리 계산해 라벨에)

```
E = V_CARD_P · V_CARD_R + (1 - V_CARD_P) · (-0.5)
E_pct = round(E · 1000) / 10   # %
```

## 게임 흐름 (상태머신)

```
[초록 깃발]
   ↓
초기화: V_P=1000, V_GOAL=10000, V_TURN=1, V_STATE=1, V_RESULT=0
   ↓
broadcast BR_NEW_TURN
   ↓
[NewTurnButton ← BR_NEW_TURN]
   - 카드 3장 spawn (각각 V_CARD_SLOT = 1/2/3)
   ↓
[플레이어가 카드 클릭]
   - 굴림 → V_P 갱신, 사운드
   - broadcast BR_CARD_CHOSEN → 다른 두 카드 사라짐
   - V_TURN += 1
   - if V_P >= V_GOAL: V_RESULT=1, broadcast BR_GAMEOVER
   - elif V_TURN > V_MAXTURN: V_RESULT=-1, broadcast BR_GAMEOVER
   - else: broadcast BR_NEW_TURN
   ↓
[BR_GAMEOVER]
   - say "승리! / 실패..." 표시, 점수판 갱신
```

## 핵심 스크립트 (의사코드)

### 배경(Stage) — 초기화 + 필요 r HUD

```
when flag clicked
   V_P     ← 1000
   V_GOAL  ← 10000
   V_TURN  ← 1
   V_MAXTURN ← 10
   V_STATE ← 1
   V_RESULT← 0
   broadcast BR_NEW_TURN

when flag clicked  (2nd script)
   forever
      if V_STATE = 1 and V_P > 0:
         n_left = V_MAXTURN - V_TURN + 1
         ratio  = V_GOAL / V_P
         ln_r   = mathop("ln", ratio)
         div_n  = ln_r / n_left
         exp_r  = mathop("e^", div_n)
         need   = exp_r - 1
         V_NEED_R ← round(need · 1000) / 10
      wait 0.1
```

### NewTurnButton — 카드 3장 spawn

```
when flag clicked
   set size 80, go to (0, -160), show, say "다음 턴" (스프라이트 자체에는 텍스트가 있는 SVG)

when I receive BR_NEW_TURN
   wait 0.25 (이전 카드 클론들이 BR_CARD_CHOSEN/BR_GAMEOVER 로 정리될 시간)
   set V_CARD_SLOT ← 1
   pick random card → set V_CARD_R, V_CARD_P, V_CARD_E
   create clone of Card
   set V_CARD_SLOT ← 2
   pick random card → ...
   create clone of Card
   set V_CARD_SLOT ← 3
   pick random card → ...
   create clone of Card
```

> **무작위 추첨**: `pick random 1 to 8` 으로 인덱스를 뽑되, 같은 턴에 중복 방지하려면 단순히 매번 새로 추첨(중복 허용)으로 처리. 학습 효과상 큰 문제 없음.

### Card — 클론 시작

```
when I start as a clone
   if V_CARD_SLOT = 1: go to (-150, -30)
   if V_CARD_SLOT = 2: go to (   0, -30)
   if V_CARD_SLOT = 3: go to ( 150, -30)
   set size 90
   show
   say (만든 문자열: "+15% / p:60 / E:+1")  ← `looks_say`
```

### Card — 클릭

```
when this sprite clicked
   if V_STATE = 1:
      roll ← pick random 1 to 100
      if roll <= V_CARD_P · 100:
         V_P ← round(V_P · (1 + V_CARD_R))
         play pop
      else:
         V_P ← round(V_P · 0.5)
         play alarm
      V_TURN ← V_TURN + 1
      broadcast BR_CARD_CHOSEN
      if V_P >= V_GOAL:
         V_RESULT ← 1
         V_STATE  ← 0
         broadcast BR_GAMEOVER
      else if V_TURN > V_MAXTURN:
         V_RESULT ← -1
         V_STATE  ← 0
         broadcast BR_GAMEOVER
      else:
         wait 0.3
         broadcast BR_NEW_TURN
```

### Card — 클론 정리

```
when I receive BR_CARD_CHOSEN
   say ""
   hide
   delete this clone

when I receive BR_GAMEOVER
   say ""
   hide
   delete this clone

when I receive BR_NEW_TURN
   (parent only — not clones — but clones will be created by the parent script)
```

## 재사용 가능한 코드

- **클론 + 클릭** 패턴: `whack-a-prime/build.py` 의 두더지 클릭 로직 (`event_whenthisspriteclicked` → if/else → delete clone).
- **`looks_say` 로 라벨 표시**: `whack-a-prime` 의 숫자 표시 방식.
- **수식 계산 헬퍼 `mathop`**: `exponential-shooter/build.py` 의 `BlockBuilder.mathop` (이 게임은 `ln`, `e^`).
- **HUD 변수 모니터**: 기존 게임 공통 패턴 (`monitors` 배열).
- **카드 SVG**: 단순한 직사각형 + 모서리 둥글게 + 텍스트는 `say` 로. 텍스트 영역 비워둔 한 가지 코스튬으로 충분.

## 학습 포인트 (README 에 반영)

1. **`A = P · (1+r)^n` 의 곱셈 누적** — 매 턴 카드 선택 = 곱하기 한 번.
2. **`x^(1/n) = e^(ln(x)/n)`** — "10배로 만들려면 매 턴 몇 %?" HUD 가 이 식을 내부적으로 계산. 게임 끝나면 README 에 "왜 이 식을 썼는지" 설명.
3. **기댓값 ≠ 도착값** — 모든 카드가 E[r]>0 이어도 실패 한 번이면 ×0.5 라서 회복이 어렵다. "복리는 양방향" (위험에도 곱셈) 직관.
4. **위험-수익 트레이드오프** — 안전 카드만으로는 10배 불가능. 어느 정도 도박 카드를 섞어야 한다는 사실을 자연스럽게 학습.

## 테스트 체크리스트

- [ ] 깃발 클릭 시 자산 1000 / 턴 1/10 / 카드 3장 보임
- [ ] 카드 클릭 시 자산 곱셈 적용 (성공/실패 분기)
- [ ] 한 번 클릭하면 다른 두 카드 사라지고 다음 턴 카드 3장 등장
- [ ] `V_NEED_R` HUD 가 매 턴마다 갱신 (예: 시작 시 약 25.9%)
- [ ] 10턴 안에 V_P ≥ 10000 → 승리 메시지
- [ ] 10턴 안에 도달 못 함 → 실패 메시지
- [ ] 게임 종료 후 카드가 모두 사라져 있음
- [ ] 다시 깃발 클릭하면 처음부터 재시작

## 빌드 노트

- 카드 SVG 는 텍스트 없이 빈 카드 모양으로 만들고, 실제 라벨은 `looks_say` 로 표시 → 한 코스튬으로 모든 카드 처리.
- `looks_say` 메시지에 줄바꿈을 못 넣음 → "+15% p:60 E:+1" 같이 슬래시로 구분된 한 줄.
- 카드 선택 시 `broadcast BR_CARD_CHOSEN` 후 `wait 0.3` 다음 `BR_NEW_TURN` → 다음 턴의 카드 클론이 이전 클론과 겹치는 race 방지.
- 자산 표시: 정수 반올림 (`round`) 으로 깔끔하게.
- 게임 종료 후 자동 재시작은 안 함 — 사용자가 깃발 다시 누름.

## 참고

- 메커닉 출처: `docs/game-candidates.md` 의 "복리 카드 게임" 항목
- 학습 포인트: 고등학교 「지수와 로그」 단원의 복리 응용 + 기하평균
- 베이스 코드: `games/whack-a-prime/build.py` (클론+클릭) ~70% 재사용
