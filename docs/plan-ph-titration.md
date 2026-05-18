# 🧪 pH 적정 실험실 — 구현 계획

> **주제**: 로그 스케일 — `pH = -log₁₀[H⁺]`. H⁺ 농도가 10배 변해도 pH는 1만 변함을 체감.
> **카테고리**: 학습형 (지수/로그)
> **난이도**: ★★★ (블록 ~200~250개)
> **폴더**: `games/ph-titration/`
> **출력**: `pH_적정_실험실.sb3`
> **베이스**: `games/decibel-dj/build.py` 90% 재사용 (슬라이더+log+라운드+힌트 패턴)

## 학습 목표

플레이어가 게임 중 다음을 *체감*하도록 한다.

1. **로그 스케일의 의미** — pH 정의 `pH = -log₁₀[H⁺]`. 한 방울로 H⁺ 농도를 ÷2 (= 0.5배) 해도 pH 는 약 0.3 만 변한다. 10배 변해야 pH 1 변함을 직접 확인.
2. **산성/염기성의 거리감** — pH 3 의 강산성 용액을 pH 7 중성으로 만들려면 약 10000 배 희석 (= 한 방울 ×0.5 를 13~14번). "한 자릿수 차이가 곧 10배 차이" 라는 로그 직관.
3. **누적 효과** — 한 방울씩 추가하는 단순 동작이 곱셈 누적으로 작용 → pH 가 거의 선형으로 보임. 곱셈 → 덧셈 변환이 로그의 본질.

## 게임 한 줄

비커 안의 H⁺ 농도를 보고, 산(↓) / 염기(↑) 방울 버튼을 클릭해 목표 pH (±0.3) 에 도달시켜라. 한 방울당 H⁺ 농도가 ×2 또는 ÷2 변화 (pH 는 ≈±0.30 변화). 5 라운드 누적 점수 게임.

## 화면 레이아웃 (480×360)

```
┌────────────────────────────────────────┐
│ 🧪 pH 적정 실험실  점수: 12  라운드 3/5 │  ← HUD
│ 현재 pH: 4.2   목표 pH: 7.0   방울: 8  │
├──────┬───────────────────────────┬─────┤
│ pH   │                           │     │
│ 14 ─ │                           │     │
│ 13 ─ │                           │     │
│  ⋮   │       🧪 비커             │     │
│  7 ━ │     (색상이 pH 따라        │     │
│  ⋮   │      바뀜: 빨→노→초→파)    │     │
│  1 ─ │                           │     │
│  0 ─ │                           │     │
├──────┴───────────────────────────┴─────┤
│  [ 산 한 방울 ▼ ]   [ 염기 한 방울 ▲ ]  │
│      ÷2 H⁺              ×2 H⁺          │
└────────────────────────────────────────┘
```

- 좌측 로그 막대 (`pH 0~14`): 현재 pH 마커(녹색 원)와 목표 pH 마커(빨간 십자)가 y 좌표로 표시. **눈금이 등간격이라도 H⁺ 농도는 10배씩 점프** 가 보임.
- 중앙 비커: 코스튬 4종 (빨강 = 강산, 노랑 = 약산, 초록 = 중성, 파랑 = 염기) 을 `pH` 구간에 따라 switch.
- 우측 하단 버튼 2개 (산/염기): 클릭 = 한 방울 추가.

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **Stage (배경)** | `lab` — 실험실 톤 그라데이션 + pH 막대 눈금 (0~14) + HUD 영역 | 단일 코스튬 |
| **비커** (Beaker) | `acid_strong` (빨강, pH<3), `acid_weak` (노랑, 3≤pH<6), `neutral` (초록, 6≤pH<8), `base` (파랑, pH≥8) — 단일 SVG 4종 | 중앙 (0, 0) 근처 |
| **현재마커** (PhMarker) | 녹색 원 (pH 막대 위 위치 표시) | x=-180 고정, y = pH 함수 |
| **목표마커** (TargetMarker) | 빨간 십자 (목표 pH 위치) | x=-200 고정, y = 목표pH 함수 |
| **산방울** (AcidButton) | 빨간 원 + "↓ 산" 텍스트, 60×60 | 클릭 시 BR_ACID |
| **염기방울** (BaseButton) | 파란 원 + "↑ 염기" 텍스트, 60×60 | 클릭 시 BR_BASE |
| **힌트버튼** (HintBtn) | 보라 알약 + "힌트 ▼" | 클릭 시 BR_HINT |

**사운드**: `pop.wav` (decibel-dj 재사용 — 방울 떨어지는 효과 / 정답 효과 공용).

## 변수 / 메시지

```
변수 (전역, 모두 Stage)
  V_HCONC      [H⁺] mol/L (예: 1e-3 = pH 3). 핵심 상태값.
  V_PH         현재 pH = -log10(V_HCONC). 매 변경 직후 갱신.
  V_PH_TARGET  목표 pH (라운드별: 6, 7, 5, 8, 7)
  V_DROPS      이번 라운드 사용한 방울 수
  V_SCORE      누적 점수
  V_ROUND      현재 라운드 (1~5)
  V_GAMEOVER   0/1
  V_FEEDBACK   상단 메시지 ("준비", "정답!", "더 산성으로", ...)
  V_HINT       힌트 텍스트 (정답 pH 노출)
  V_DIFF       |V_PH - V_PH_TARGET|. 판정용.
  V_PH_INT     int(V_PH) — 코스튬 분기용 (옵션)

메시지 (BROADCAST)
  BR_START         초록 깃발 시 game 시작
  BR_NEW_ROUND     새 라운드 셋업
  BR_ACID          산 한 방울 추가
  BR_BASE          염기 한 방울 추가
  BR_RECALC        V_HCONC 변경 후 V_PH 재계산 + 마커 위치 갱신
  BR_TRY           목표 도달 판정
  BR_HINT          힌트 표시
  BR_GAMEOVER      5라운드 종료
```

## 좌표 변환 (pH 막대)

화면 좌측 pH 막대는 y 좌표로 pH 를 표현.

```
y_marker = -120 + V_PH · 20    # pH 0 → y=-120, pH 14 → y=160
# 막대 길이 = 14 · 20 = 280px (Scratch y 범위 -120..160 사용)
```

따라서:
- 현재마커: `motion_sety(-120 + 20·V_PH)`, x = -180 고정
- 목표마커: `motion_sety(-120 + 20·V_PH_TARGET)`, x = -200 고정

## 핵심 공식 (코드 주석으로도 노출)

```
V_PH = -1 · log₁₀(V_HCONC)        # operator_mathop("log", V_HCONC) → ×(-1)
산 한 방울:  V_HCONC ← V_HCONC × 2     (H⁺ 증가, pH ↓ ≈0.30)
염기 한 방울: V_HCONC ← V_HCONC × 0.5  (H⁺ 감소, pH ↑ ≈0.30)
```

> 가드: 한 방울 후 `V_HCONC` 가 너무 작아지지 않도록 (log 입력 0 회피).
> 실제로는 V_HCONC 범위는 1e-14 ~ 1 사이로 클램프 — pH 0~14.

## 게임 흐름

```
[초록 깃발]
   ↓
초기화: V_ROUND=0, V_SCORE=0, V_GAMEOVER=0
   ↓
broadcast BR_NEW_ROUND
   ├─ V_ROUND++
   ├─ 라운드별 초기 V_HCONC, V_PH_TARGET 설정 (테이블 참고)
   ├─ V_DROPS = 0
   ├─ broadcast BR_RECALC  → 마커/비커 코스튬 갱신
   └─ V_FEEDBACK = "목표 pH 에 도달하라"

[루프] — 클릭 이벤트로 진행
   ├─ AcidButton 클릭 → BR_ACID → V_HCONC ×= 2, V_DROPS++, BR_RECALC, pop sound, BR_TRY
   ├─ BaseButton 클릭 → BR_BASE → V_HCONC ×= 0.5, V_DROPS++, BR_RECALC, pop sound, BR_TRY
   ├─ HintBtn 클릭 → BR_HINT → V_HINT = "목표 pH: " & V_PH_TARGET
   │
   ├─ BR_RECALC 받음 (Stage):
   │     V_PH = round1dp(-log10(V_HCONC))
   │     V_HCONC 가드 (1e-14 ~ 1)
   │     → 마커 sprite 들이 자기 y 좌표 갱신 (각자 forever 또는 broadcast 수신)
   │     → 비커가 코스튬 전환
   │
   └─ BR_TRY 받음 (Stage):
        V_DIFF = abs(V_PH - V_PH_TARGET)
        if V_DIFF < 0.3 → V_SCORE += max(20 - V_DROPS, 1), V_FEEDBACK = "정답!", wait 0.6, BR_NEW_ROUND
        elif V_PH < V_PH_TARGET → V_FEEDBACK = "더 염기로!"
        else                     → V_FEEDBACK = "더 산성으로!"

V_ROUND > 5 일 때 → BR_GAMEOVER
   set V_GAMEOVER=1, V_FEEDBACK = "종료! 점수 X"
```

## 라운드 표

| 라운드 | 초기 V_HCONC | 초기 pH | 목표 pH | 의도 |
|--------|-------------|---------|---------|------|
| 1 | 1e-3 = 0.001 | 3.0 | 6.0 | 산 → 중성. 방울 ≈ 10번 (×0.5⁹·⁹ ≈ 1e-3·10⁻³) |
| 2 | 1e-9 | 9.0 | 7.0 | 약염기 → 중성. 방울 ≈ 7번 (×2 약 7회) |
| 3 | 1e-1 = 0.1 | 1.0 | 5.0 | 강산 → 약산. 방울 ≈ 13번 |
| 4 | 1e-11 | 11.0 | 8.0 | 강염기 → 약염기. 방울 ≈ 10번 |
| 5 | 1e-5 | 5.0 | 7.0 | 미세 조정. 짧은 라운드 |

## 핵심 스크립트 (의사코드)

### Stage — 깃발 클릭
```
when flag clicked
  V_ROUND=0; V_SCORE=0; V_GAMEOVER=0; V_FEEDBACK="준비"; V_HINT=""
  broadcast BR_NEW_ROUND
```

### Stage — BR_NEW_ROUND
```
when I receive BR_NEW_ROUND
  V_ROUND += 1
  if V_ROUND > 5 → broadcast BR_GAMEOVER; stop
  V_DROPS = 0
  V_HINT = ""
  V_FEEDBACK = "목표 pH 에 도달하라"
  if V_ROUND=1: V_HCONC=0.001; V_PH_TARGET=6
  elif V_ROUND=2: V_HCONC=1e-9; V_PH_TARGET=7
  elif V_ROUND=3: V_HCONC=0.1; V_PH_TARGET=5
  elif V_ROUND=4: V_HCONC=1e-11; V_PH_TARGET=8
  elif V_ROUND=5: V_HCONC=1e-5; V_PH_TARGET=7
  broadcast BR_RECALC
```

### Stage — BR_ACID (산 한 방울)
```
when I receive BR_ACID
  if V_GAMEOVER = 0
    V_HCONC = V_HCONC * 2
    if V_HCONC > 1 → V_HCONC = 1     # clamp pH ≥ 0
    V_DROPS += 1
    broadcast BR_RECALC
    broadcast BR_TRY
```

### Stage — BR_BASE (염기 한 방울)
```
when I receive BR_BASE
  if V_GAMEOVER = 0
    V_HCONC = V_HCONC * 0.5
    if V_HCONC < 1e-14 → V_HCONC = 1e-14   # clamp pH ≤ 14
    V_DROPS += 1
    broadcast BR_RECALC
    broadcast BR_TRY
```

### Stage — BR_RECALC (pH 재계산)
```
when I receive BR_RECALC
  raw = log(V_HCONC)        # operator_mathop("log") = log10
  V_PH = round1dp(0 - raw)  # = -log10(V_HCONC)
```

### Stage — BR_TRY (판정)
```
when I receive BR_TRY
  V_DIFF = abs(V_PH - V_PH_TARGET)
  if V_DIFF < 0.31
    bonus = 20 - V_DROPS; if bonus < 1 → bonus = 1
    V_SCORE += bonus
    V_FEEDBACK = "정답!"
    play pop.wav
    wait 0.6
    broadcast BR_NEW_ROUND
  else
    if V_PH < V_PH_TARGET
      V_FEEDBACK = "더 염기로! (▲ 버튼)"
    else
      V_FEEDBACK = "더 산성으로! (▼ 버튼)"
```

### AcidButton sprite
```
when flag clicked: goto (130, -130); show
when this sprite clicked:
  broadcast BR_ACID
  play pop.wav
```

### BaseButton sprite (BR_BASE 만 다름)
```
when flag clicked: goto (-130, -130); show
when this sprite clicked:
  broadcast BR_BASE
  play pop.wav
```

### PhMarker sprite (현재 pH 마커)
```
when flag clicked: goto (-180, 0); show
forever:
  set y to (-120 + 20 · V_PH)
```

### TargetMarker sprite (목표 pH 마커)
```
when flag clicked: goto (-200, 0); show
forever:
  set y to (-120 + 20 · V_PH_TARGET)
```

### Beaker sprite — 코스튬 전환
```
when flag clicked: goto (60, -10); show; size 100
forever:
  if V_PH < 3 → switch costume "acid_strong"
  elif V_PH < 6 → switch costume "acid_weak"
  elif V_PH < 8 → switch costume "neutral"
  else → switch costume "base"
```

### HintBtn sprite
```
when this sprite clicked → broadcast BR_HINT → play pop

(Stage) when I receive BR_HINT:
  V_HINT = "목표 pH: " & V_PH_TARGET
```

### Stage — BR_GAMEOVER
```
when I receive BR_GAMEOVER
  V_GAMEOVER = 1
  V_FEEDBACK = "종료! 점수 " & V_SCORE
```

## 재사용 가능한 코드

- **decibel-dj/build.py 의 BlockBuilder** — `vrep`/`op`/`mathop`/`cmp`/`round_to_1dp` 그대로 사용. 특히 `mathop("log", x)` 가 핵심.
- **decibel-dj 의 라운드 분기 패턴** — `if V_ROUND = N` 체인.
- **decibel-dj 의 힌트 + 피드백 모니터** — 큰 모니터로 텍스트 변수 표시.
- **decibel-dj 의 게임오버 분기** — V_GAMEOVER 가드.

## 학습 포인트 — 게임에 어떻게 녹였는가

| 학습 포인트 | 게임 안에서 |
|------------|-----------|
| `pH = -log₁₀[H⁺]` | `V_PH = -1 · operator_mathop("log", V_HCONC)` — 실제 블록으로 구현 |
| "10배 변해야 pH 1 변함" | 한 방울로 H⁺ ÷2 → pH +0.30 만 변함. 13~14 방울이 ÷2¹³⁻¹⁴ ≈ ÷10000 = pH +4 |
| 산성/염기성 거리감 | 비커 색상이 pH 구간에 따라 변함. pH 1→6 (강산→약산) 사이가 H⁺ 농도 10만 배 |
| 로그 스케일 등간격 | 좌측 pH 막대 — 눈금은 등간격이지만 한 칸이 10배 농도 차이 |

## 테스트 체크리스트 (verifier 가 확인)

- [ ] sb3 zip 무결성 OK, project.json 파싱 성공
- [ ] Stage 의 `variables` 에 13 개 변수 ID 모두 정의 (V_HCONC, V_PH, V_PH_TARGET, V_DROPS, V_SCORE, V_ROUND, V_GAMEOVER, V_FEEDBACK, V_HINT, V_DIFF)
- [ ] Stage 의 `broadcasts` 에 8 개 메시지 모두 정의
- [ ] 스프라이트 7개: 비커, 현재마커, 목표마커, 산버튼, 염기버튼, 힌트버튼 (Stage 제외 6개 + Stage)
- [ ] `operator_mathop` 의 fields `OPERATOR` 가 `"log"` 인 블록이 BR_RECALC 흐름 안에 1개 이상
- [ ] 한 방울당 V_HCONC 가 `operator_multiply` 2 또는 0.5 로 갱신
- [ ] 블록 카운트 150 ~ 300 (★★★ 범위)
- [ ] 모든 block 의 parent/next 가 같은 sprite 안에서 유효
- [ ] 자산 MD5 = assetId 일치
