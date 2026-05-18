# 🎹 옥타브 피아노 — 구현 계획

> **주제**: 음악 = 로그 스케일. 주파수 2배 = 한 옥타브 (log₂ 단위)
> **카테고리**: 학습형 (지수/로그) + 음악
> **난이도**: ★★ (블록 ~120개)
> **폴더**: `games/octave-piano/`
> **출력**: `옥타브_피아노.sb3`

## 학습 목표

플레이어가 게임 중 다음을 *체감* 한다.

1. **옥타브 = 주파수 ×2** — 두 건반의 주파수 비 `f₂/f₁` 가 정확히 `2^k` 일 때만 옥타브 관계.
2. **음악 = 로그 스케일** — 건반은 균등 간격이지만 주파수는 *지수적* 으로 증가. 음악적 거리는 `log₂(f₂/f₁)` (옥타브 단위) 또는 `12·log₂(f₂/f₁)` (반음 단위).
3. **밑이 2 인 로그의 직관** — 화면 HUD 가 매 라운드 `f₂/f₁` 와 `log₂(f₂/f₁)` 를 실시간으로 보여줌. 정수일 때만 옥타브.

## 게임 한 줄

화면에 1~2 옥타브 피아노가 있다. 매 라운드 두 건반이 강조 표시된다.
플레이어는 두 음이 **같은 음이름의 다른 옥타브** 인지 판단해 `O` (옥타브) /
`X` (옥타브 아님) 키를 누른다. HUD 에 `f₂/f₁` 와 `log₂(f₂/f₁)` 가 실시간
표시되어, *로그값이 정수면 옥타브* 라는 직관을 키운다. 60 초 제한.

## 화면 레이아웃 (480×360)

```
┌────────────────────────────────────────────────┐
│ 점수: 7    시간: 42s    f₂/f₁ = 2.00           │  ← HUD (Stage 모니터)
│ log₂(f₂/f₁) = 1.00      → 정수면 옥타브 (O)    │
├────────────────────────────────────────────────┤
│                                                │
│                ★         ★                    │  ← 강조된 두 건반 (예시: C4, C5)
│  ┌──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┐  │
│  │C │D │E │F │G │A │B │C │D │E │F │G │A │B │  │  ← 흰건반 14개 (C4~B5)
│  │4 │4 │4 │4 │4 │4 │4 │5 │5 │5 │5 │5 │5 │5 │  │
│  └──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┘  │
│        O = 옥타브       X = 옥타브 아님        │  ← 조작 안내 (배경에 텍스트)
└────────────────────────────────────────────────┘
```

좌표 변환: 건반 14개를 화면 가로 ~420px 에 배치. 폭 = 30px, 좌측 시작 x=30 (SVG)
→ Scratch x = -210 + 키번호·30. 강조 표시 y(SVG) = 130 → Scratch y = 50.

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **Background** | `piano` — 건반 14개 + HUD 영역 + 안내 텍스트 | 별도 sprite 없이 배경에 그려넣음 |
| **Highlight** (clone-driven, 2개) | `star` — 노란 별 + 부드러운 외곽선 | 두 건반 위에 떠 있는 마커. 라운드마다 위치 갱신 |
| **Result** | `correct` (✓ 초록), `wrong` (✗ 빨강), `blank` (투명) | 정/오답 결과를 0.5초간 표시 |
| **GameOver** | `banner` — "게임 종료 / 점수 N" | 시간 0 이 되면 중앙에 등장 |

**사운드** (모두 build.py 에서 `wave` 모듈로 합성):

- `note_low.wav` — 낮은 건반의 사인파 (주파수는 라운드별 다름, 합성 시 기본 C4=261.63Hz)
- `note_high.wav` — 높은 건반의 사인파 (기본 C5=523.25Hz)
- `correct.wav` — 정답 (밝은 두 음 화음)
- `wrong.wav` — 오답 (저음 노이즈)

> **간단화** — 두 음 재생은 라운드 진입 시마다 *주파수만* 달라지지만 Scratch
> 에서 동적 주파수 합성은 어렵다. 대신 **고정된 두 사운드 (note_low.wav,
> note_high.wav) 를 sound effect 의 `PITCH` 효과로 셔플** 한다.
> Scratch PITCH = 반음 × 10 (즉 PITCH 120 = 1옥타브 위, PITCH -120 = 1옥타브 아래).

## 변수 / 리스트 / 메시지

```
변수 (전역, Stage)
  V_SCORE       점수 (정답 +1, 오답 -1)
  V_TIME        남은 시간 (초)
  V_STATE       게임 상태 (1=playing, 0=over)
  V_K1          왼쪽 건반의 인덱스 (1..14)
  V_K2          오른쪽 건반의 인덱스 (1..14)
  V_F1          왼쪽 건반의 주파수 (Hz)
  V_F2          오른쪽 건반의 주파수 (Hz)
  V_RATIO       f2/f1 (HUD 표시용, 소수 2자리)
  V_LOG2        log₂(f2/f1) (HUD 표시용, 소수 2자리)
  V_IS_OCT      현재 라운드의 정답 (1=옥타브, 0=아님)
  V_FEEDBACK    마지막 입력의 결과 (1=correct, 0=wrong, -1=none)
  V_ROUND       현재 라운드 인덱스 (1..)

변수 (Highlight 클론 로컬)
  L_SIDE        1=왼쪽 마커, 2=오른쪽 마커

리스트 (전역)
  L_FREQ        14개 흰건반 주파수 (C4~B5)
  L_NAME        14개 흰건반 이름 ("C4","D4",...,"B5")

메시지
  BR_START          게임 시작
  BR_NEW_ROUND      새 라운드 (두 건반을 고르고 강조 마커 위치 갱신)
  BR_PLAY_LOW       낮은 건반 소리 재생
  BR_PLAY_HIGH      높은 건반 소리 재생
  BR_ANSWER_OCT     "O" 키 입력 (옥타브라고 응답)
  BR_ANSWER_NOT     "X" 키 입력 (옥타브 아니라고 응답)
  BR_SHOW_CORRECT   정답 ✓ 표시
  BR_SHOW_WRONG     오답 ✗ 표시
  BR_GAMEOVER       게임 종료
```

흰건반 14개 = C4~B5. 주파수표 (12음 평균율 기준):

```
C4=261.63, D4=293.66, E4=329.63, F4=349.23, G4=392.00, A4=440.00, B4=493.88,
C5=523.25, D5=587.33, E5=659.25, F5=698.46, G5=783.99, A5=880.00, B5=987.77
```

## 씬 / 상태머신

```
[초록 깃발]
   ↓
초기화: V_SCORE=0, V_TIME=60, V_STATE=1, V_ROUND=0
L_FREQ, L_NAME 채우기
   ↓
broadcast BR_START
   ├─ Stage: 매 1초 V_TIME -= 1, V_TIME = 0 면 BR_GAMEOVER
   ├─ Stage: BR_NEW_ROUND 송신 시작
   └─ Background: 첫 라운드 마커 갱신
   ↓
[라운드 루프]  (V_STATE = 1 동안)
   ├─ BR_NEW_ROUND
   │    ├─ 두 인덱스 V_K1, V_K2 무작위 선택 (V_K1 < V_K2)
   │    ├─ V_F1 = L_FREQ[V_K1], V_F2 = L_FREQ[V_K2]
   │    ├─ V_RATIO = round(V_F2 / V_F1 * 100) / 100
   │    ├─ V_LOG2  = round(log(V_RATIO) / log(2) * 100) / 100
   │    ├─ V_IS_OCT = 1 if (V_K2 - V_K1 == 7) else 0
   │    │   (이유: 흰건반 7개 = 한 옥타브)
   │    ├─ 두 건반 위에 별 마커 클론 2개 띄움 (1=왼쪽, 2=오른쪽)
   │    └─ 0.2초 후 두 음 차례로 재생 (PITCH 효과로 옥타브 표현)
   ├─ 키 입력 'O' → BR_ANSWER_OCT
   │     V_IS_OCT == 1 → 정답 (점수+1, ✓)
   │     V_IS_OCT == 0 → 오답 (점수-1, ✗)
   ├─ 키 입력 'X' → BR_ANSWER_NOT
   │     V_IS_OCT == 0 → 정답
   │     V_IS_OCT == 1 → 오답
   └─ 정/오답 후 0.6초 대기 → BR_NEW_ROUND
   ↓
[V_TIME == 0]
   broadcast BR_GAMEOVER → V_STATE=0, 게임오버 배너 표시, 모든 클론 삭제
```

## 블록 흐름 (스프라이트별 의사코드)

### Stage — 초기화 + 타이머 + 라운드 로직

```
when flag clicked
   set V_SCORE=0, V_TIME=60, V_STATE=1, V_ROUND=0
   delete all of L_FREQ, L_NAME
   add 261.63 .. 987.77 to L_FREQ      # 14개 push
   add "C4" .. "B5" to L_NAME          # 14개 push
   broadcast BR_START

when I receive BR_START
   broadcast BR_NEW_ROUND
   # 타이머 루프
   repeat until V_TIME = 0
      wait 1
      change V_TIME by -1
   set V_STATE to 0
   broadcast BR_GAMEOVER

when I receive BR_NEW_ROUND
   if V_STATE = 1
      change V_ROUND by 1
      set V_K1 to (random 1..7)              # 왼쪽: C4..B4 중
      # 옥타브 정답을 50% 확률로 보장
      if (random 1..2) = 1
         set V_K2 to V_K1 + 7                # 정확히 한 옥타브 위 (정답 = O)
      else
         set V_K2 to V_K1 + (random 1..6) + 1  # 한 옥타브 아닌 위쪽 (정답 = X)
         if V_K2 > 14: set V_K2 to 14         # clamp
         if V_K2 = V_K1 + 7: set V_K2 to V_K1 + 8  # 우연히 옥타브가 됐다면 옆 칸으로
         if V_K2 > 14: set V_K2 to V_K1 + 6
      set V_F1 to item V_K1 of L_FREQ
      set V_F2 to item V_K2 of L_FREQ
      set V_RATIO to round((V_F2 / V_F1) * 100) / 100
      set V_LOG2  to round((log(V_RATIO) / log(2)) * 100) / 100
      set V_IS_OCT to (V_K2 - V_K1 = 7 ? 1 : 0)
      set V_FEEDBACK to -1
      # 마커 갱신
      broadcast BR_NEW_ROUND_HIGHLIGHT  (실제로는 같은 BR_NEW_ROUND 를 Highlight sprite 가 수신)
      wait 0.15
      broadcast BR_PLAY_LOW
      wait 0.45
      broadcast BR_PLAY_HIGH

when key 'o' pressed
   if V_STATE = 1: broadcast BR_ANSWER_OCT

when key 'x' pressed
   if V_STATE = 1: broadcast BR_ANSWER_NOT

when I receive BR_ANSWER_OCT
   if V_IS_OCT = 1
      change V_SCORE by 1
      broadcast BR_SHOW_CORRECT
   else
      change V_SCORE by -1
      broadcast BR_SHOW_WRONG
   wait 0.6
   broadcast BR_NEW_ROUND

when I receive BR_ANSWER_NOT
   if V_IS_OCT = 0
      change V_SCORE by 1
      broadcast BR_SHOW_CORRECT
   else
      change V_SCORE by -1
      broadcast BR_SHOW_WRONG
   wait 0.6
   broadcast BR_NEW_ROUND

# 사운드 재생: PITCH 효과로 옥타브 표현
# C4 ~ B5 중 V_K1 번째 건반은 기준 C4(261.63Hz) 에서 몇 반음 위인지 = halfsteps(V_K1)
# halfsteps: C->D=2, D->E=2, E->F=1, F->G=2, G->A=2, A->B=2, B->C=1
# 13개 인덱스 (1..14) 의 반음 수: 0,2,4,5,7,9,11,12,14,16,17,19,21,23
when I receive BR_PLAY_LOW
   set sound effect PITCH to (halfsteps(V_K1) * 10)
   play note_low.wav

when I receive BR_PLAY_HIGH
   set sound effect PITCH to (halfsteps(V_K2) * 10)
   play note_high.wav
```

> halfsteps 계산은 if 블록 14개 분기로 처리 (V_K1 = i 면 set V_HALF to TABLE[i]).
> 또는 더 우아하게: floor((V_K1-1)/7) * 12 + 흰건반 반음테이블[(V_K1-1) mod 7]
> 흰건반 반음테이블 = [0, 2, 4, 5, 7, 9, 11]
> 실제 build.py 에서는 단순함을 위해 if 분기 사용.

### Highlight sprite — 두 건반 위에 별 띄우기

```
when flag clicked
   hide

when I receive BR_NEW_ROUND
   wait 0.05   # Stage 가 V_K1/V_K2 를 세팅할 시간을 줌
   delete all clones of Highlight  (실제로는 broadcast 받으면 모든 클론이 자기 삭제)
   create clone of myself  (왼쪽 마커, L_SIDE=1)
   set L_SIDE to 1  # 부모용 - 클론이 받아씀
   ...
   create clone of myself  (오른쪽 마커, L_SIDE=2)

when I start as a clone
   if L_SIDE = 1
      set x to keyx(V_K1)   ; set y to 50
   else
      set x to keyx(V_K2)   ; set y to 50
   show
   wait until ... (다음 라운드까지)

# keyx(k) = -210 + 15 + (k-1) * 30  = -195 + (k-1)*30
# k=1 → -195, k=7 → -15, k=8 → 15, k=14 → 195
```

실제 build.py 에서는 클론 로컬 변수를 쓰지 않고, 부모 sprite 가
**클론 생성 직전에 공유 변수 V_K1/V_K2 와 SpawnSide 변수를 세팅** 하는 패턴 사용
(`bacteria-defense` 의 SpawnX/SpawnY 와 동일).

### Result sprite — ✓/✗ 표시

```
when flag clicked
   hide

when I receive BR_SHOW_CORRECT
   switch costume to "correct"
   show
   wait 0.5
   hide

when I receive BR_SHOW_WRONG
   switch costume to "wrong"
   show
   wait 0.5
   hide
```

### GameOver sprite

```
when flag clicked
   hide
   wait until V_STATE = 0
   show
```

## 재사용 가능한 코드

- **클론 + 스폰 좌표 변수 패턴** (Highlight 별 마커): `bacteria-defense/build.py` 의
  `V_SPAWNX/V_SPAWNY` 변수와 `try_spawn_block_chain()` 패턴 그대로.
- **HUD 모니터 + 시간 카운트다운**: `whack-a-prime/build.py` 의 `V_TIME` repeat-until 루프.
- **로그 계산** (`log(V_RATIO) / log(2)`): `bacteria-defense/build.py` 의 HUD 갱신 부분
  (`log10(N_max/N) / log10(R)`) 과 똑같은 밑변환 공식 패턴.
- **사운드 합성 (사인파 WAV)**: `beat-tap/build.py` 의 `write_wav`, `gen_tick_wav`
  함수 그대로 차용 + 주파수만 교체.
- **결과 ✓/✗ + 게임오버 배너**: `whack-a-prime` 의 `looks_say` 대신
  별도 sprite + costume switch (bacteria-defense 의 GameOver 패턴).

## 학습 포인트 (수식이 게임 안에 어디 있나)

| 수식 | 게임 안 위치 |
|------|-------------|
| `f₂ / f₁ = 2^k` (옥타브 = 비율 2의 거듭제곱) | HUD `V_RATIO` 값. `V_K2 - V_K1 = 7` 일 때 정확히 2.00. |
| `log₂(f₂/f₁) = k` (옥타브 = 로그) | HUD `V_LOG2` 값. 정수일 때만 옥타브. |
| 밑 변환 `log₂(x) = log₁₀(x) / log₁₀(2)` | build.py 의 `V_LOG2` 계산식. Scratch 의 `log` 블록은 밑 10 이므로 필수. |
| 음악 = 로그 스케일 (등간격 건반, 지수 주파수) | 화면의 14개 건반 + 두 음 PITCH 효과의 차이. 흰건반 7칸 차이가 정확히 옥타브 = 주파수 ×2. |

## 테스트 체크리스트

- [ ] 깃발 클릭 후 1초 안에 두 별 마커가 두 흰건반 위에 떠야 함
- [ ] HUD 의 `V_RATIO` 가 두 주파수의 정확한 비를 표시 (소수 2자리)
- [ ] `V_K2 - V_K1 = 7` 일 때만 `V_LOG2 = 1.00` (옥타브 정답)
- [ ] `O` 키 → 옥타브 라운드면 점수 +1, 아닌 라운드면 -1
- [ ] `X` 키 → 옥타브 아닌 라운드면 +1, 옥타브 라운드면 -1
- [ ] 정/오답 후 0.6초 안에 다음 라운드 진입
- [ ] V_TIME 이 1초마다 줄어들고, 0 도달 시 GameOver 배너 표시
- [ ] 두 음 사운드가 들리고, 두 번째 음의 PITCH 가 두 키 차이의 반음수만큼 다름
- [ ] 클론(별 마커) 이 라운드마다 깨끗이 정리됨 (이전 라운드 마커 잔존 X)

## 빌드 노트

- **음정 PITCH 변환**: Scratch 의 `sound_seteffectto PITCH` 는 *반음 × 10 단위*.
  즉 PITCH = 120 → 1옥타브 (12반음) 위. 두 사운드(note_low.wav, note_high.wav)
  는 합성 시 *기준 주파수 C4 (261.63Hz)* 와 *C5 (523.25Hz)* 로 만들고,
  V_K1, V_K2 에 따라 PITCH 효과로 더 올린다.
- **PITCH 효과는 누적되지 않음** — `set sound effect PITCH to X` 는 *절대값* 으로 세팅.
  매 재생 전 새 값으로 세팅하면 다음 재생부터 즉시 반영됨. 동일 sprite 의
  다른 사운드도 같은 PITCH 효과 영향 받으므로, low/high 두 재생 사이에
  PITCH 를 다시 세팅해야 함 (이미 의사코드에 반영).
- **반음 수 테이블** (인덱스 1..14): `[0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17, 19, 21, 23]`.
  C 기준 흰건반의 반음 거리. 인덱스 i 와 i+7 의 차이는 항상 12.
- **클론 정리** — 라운드 전환마다 이전 마커 클론 2개를 삭제해야 함.
  `bacteria-defense` 와 똑같이 BR_NEW_ROUND 받을 때 모든 클론이 자기 삭제하고,
  부모가 새로 2개 생성하는 패턴.
- **시간 모니터** — `V_TIME` 은 `large` 모드, 우측 상단.
- **블록 카운트 예상** — ★★ 난이도, 약 100~140개. Stage 가 60~80, Highlight 20~30,
  Result 10~15, GameOver 10.
