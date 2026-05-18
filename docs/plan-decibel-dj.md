# 🎧 데시벨 DJ — 구현 계획

> **주제**: 로그 — 데시벨(dB)의 비밀, 두 소리를 합치면 "그냥 더하기" 가 아니다
> **카테고리**: 학습형 (지수/로그 단원 — 로그의 응용)
> **난이도**: ★★ (블록 ~120개)
> **폴더**: `games/decibel-dj/`
> **출력**: `데시벨_DJ.sb3`
> **베이스**: `exponential-shooter/build.py` 의 슬라이더/HUD/라운드 패턴 약 60% 재사용

## 학습 목표

플레이어가 게임 중 다음을 *체감*하도록 한다.

1. **dB = 10·log₁₀(I/I₀) — 로그 스케일의 의미** — 강도(I) 가 10배 커지면 dB 는 +10 만 늘어난다. 강도 100배 = +20 dB. 로그가 큰 수를 "압축" 한다는 직관.
2. **두 소리의 합산 dB ≠ dB₁ + dB₂** — 60 dB + 60 dB 는 120 dB 가 아니라 **63 dB** 다. 같은 dB 두 개를 합치면 단지 +3 dB. (강도는 두 배가 되니 `10·log₁₀(2) ≈ 3`)
3. **두 강도가 크게 다르면 큰 쪽이 거의 결정** — 80 dB + 60 dB ≈ 80.04 dB. 작은 쪽이 거의 묻힘.
4. **슬라이더로 답을 맞춰 보며 위 세 가지를 손으로 확인**

## 게임 한 줄

DJ 부스에서 두 트랙(I₁, I₂)이 흘러나온다. 각각의 dB 값이 화면에 표시된다. 슬라이더로 **"합산 dB"** 를 추측해 ±1 dB 이내로 맞춰 노이즈 게이트를 통과시켜라. 60초 안에 가장 많이 통과시키면 승.

## 화면 레이아웃 (480×360)

```
┌──────────────────────────────────────────────────────┐
│ 점수: 5    남은 시간: 47s    라운드: 6               │
│ ┌─────────────┐         ┌─────────────┐              │
│ │  🎵 트랙 A   │         │  🎵 트랙 B   │              │
│ │  I₁ = 100k  │         │  I₂ = 50k   │              │
│ │  dB₁ = 50.0 │         │  dB₂ = 47.0 │              │
│ └─────────────┘         └─────────────┘              │
│                                                      │
│         합산 dB 슬라이더 (40 ~ 100)                  │
│   ┌─────────────●──────────────────────┐  내 답: 51.2│
│   │              ↑ 정답 근처            │             │
│                                                      │
│   힌트(2초 누르기): 10·log₁₀((I₁+I₂)/I₀) = 51.8       │
│                                                      │
│   [ 통과 시도 ▶ Space ]    피드백: "정답! +1"        │
└──────────────────────────────────────────────────────┘
```

기본 dB 기준 `I₀ = 10³ = 1000`. 강도는 천 ~ 천만 범위에서 출제.

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **Stage** (Background) | 한 장: DJ 부스 컨셉 + 두 트랙 패널 + 슬라이더 영역 | SVG 직접 그림 |
| **TrackA** | 1개 (음표 + 사각 패널, 빨강 계열) | 상시 표시. 라운드별 I₁, dB₁ 값은 변수 모니터로 |
| **TrackB** | 1개 (음표 + 사각 패널, 파랑 계열) | 상시 표시. 라운드별 I₂, dB₂ |
| **Judge** (판정/피드백) | 1개 (라벨 박스) | `looks_say` 로 정답/오답 메시지 |
| **HintBtn** | 1개 ("힌트 ▼" 버튼) | 클릭 시 정답 노출 (선택적 — 점수 감점 없음, 학습용) |

**사운드**: `pop.wav` (exponential-shooter 에서 재사용 — 정답 통과 시), `beep.wav` (저음 비프 — 오답 시. 새로 합성)

## 변수 / 메시지

```
변수 (전역)
  V_I1        트랙 A 강도 (정수)
  V_I2        트랙 B 강도 (정수)
  V_I0        기준 강도 (= 1000, 고정)
  V_DB1       dB₁ = 10·log₁₀(I₁/I₀)  (소수 1자리 반올림)
  V_DB2       dB₂ = 10·log₁₀(I₂/I₀)
  V_DB_ANS    정답 합산 dB = 10·log₁₀((I₁+I₂)/I₀)
  V_DB_USER   사용자 슬라이더 입력 (40 ~ 100, 0.1 step)
  V_SCORE     맞춘 라운드 수
  V_ROUND     현재 라운드
  V_TIME      남은 시간 (60 → 0)
  V_FEEDBACK  피드백 문자열 ("정답!" / "차이 X dB" / "준비")
  V_HINT      힌트 노출 문자열 ("정답: XX.X dB" 또는 "")
  V_GAMEOVER  0/1

메시지
  BR_START         게임 시작
  BR_NEW_ROUND     새 라운드 생성 (I₁, I₂ 무작위)
  BR_TRY           Space — 통과 시도
  BR_HINT          힌트 보기
  BR_GAMEOVER      시간 초과
```

## 라운드 / 난이도 설계

라운드별로 (I₁, I₂) 의 비율과 절대값을 다양화해서 학습 포인트를 골고루 경험시킨다.

| 라운드 | I₁ | I₂ | 학습 의도 |
|--------|----|----|----------|
| 1 | 10,000 | 10,000 | 같은 강도 두 개 → +3 dB 만 추가됨 (dB₁=dB₂=10, ans≈13) |
| 2 | 100,000 | 100,000 | 위와 동일 패턴, 다른 절대값 (dB=20, ans≈23) |
| 3 | 1,000,000 | 100 | 극단적 차이 → 큰 쪽이 거의 결정 (ans ≈ dB₁) |
| 4 | 100,000 | 50,000 | 약 2:1 — 약 +1.8 dB |
| 5 | 1,000 | 1,000 | 두 dB 모두 0, ans≈3 (dB 0이 "들리지 않음" 이 아님!) |
| 6+ | 무작위 (1e3 ~ 1e7) | 무작위 (1e3 ~ 1e7) | 자유 라운드 |

## 게임 흐름

```
[초록 깃발]
   ↓
초기화: V_SCORE=0, V_ROUND=0, V_TIME=60, V_GAMEOVER=0
   ↓
broadcast BR_NEW_ROUND
   ↓
[메인 루프]
   ├─ 타이머: 매 1초 V_TIME -= 1 → V_TIME=0 일 때 BR_GAMEOVER
   ├─ Space 키 → BR_TRY
   │     |V_DB_USER - V_DB_ANS| < 1.0 → 정답 (점수+1, pop 사운드, BR_NEW_ROUND)
   │     else → 차이 표시 ("X dB 차이")
   ├─ "힌트" 버튼 클릭 → BR_HINT (V_HINT 에 정답 표시)
   └─ BR_NEW_ROUND:
        V_ROUND += 1
        라운드별 (I₁, I₂) 결정
        V_DB1 = round(10·log₁₀(I₁/I₀), 1)
        V_DB2 = round(10·log₁₀(I₂/I₀), 1)
        V_DB_ANS = round(10·log₁₀((I₁+I₂)/I₀), 2)   # 비교는 ±1.0 으로
        V_HINT = ""
   ↓
BR_GAMEOVER: 모든 스크립트 정지, "최종 점수: V_SCORE" 표시
```

## 핵심 스크립트 (의사코드)

### Stage — 초기화 + 타이머

```
when flag clicked
   set V_I0 to 1000
   set V_SCORE to 0
   set V_ROUND to 0
   set V_TIME to 60
   set V_GAMEOVER to 0
   set V_FEEDBACK to "준비"
   set V_HINT to ""
   set V_DB_USER to 60
   broadcast BR_NEW_ROUND
   forever
      wait 1 second
      if V_GAMEOVER = 0
         change V_TIME by -1
         if V_TIME <= 0
            broadcast BR_GAMEOVER
```

### Stage — 새 라운드 생성

```
when I receive BR_NEW_ROUND
   change V_ROUND by 1
   # 라운드 1~5 는 고정 시나리오, 6+ 는 무작위
   if V_ROUND = 1
      set V_I1 to 10000; set V_I2 to 10000
   else if V_ROUND = 2
      set V_I1 to 100000; set V_I2 to 100000
   else if V_ROUND = 3
      set V_I1 to 1000000; set V_I2 to 100
   else if V_ROUND = 4
      set V_I1 to 100000; set V_I2 to 50000
   else if V_ROUND = 5
      set V_I1 to 1000; set V_I2 to 1000
   else
      set V_I1 to 10 ^ (pick random 3 to 7)
      set V_I2 to 10 ^ (pick random 3 to 7)

   set V_DB1 to round( 10 · log(V_I1 / V_I0) , 1 ) / 1   # = round to 0.1
   set V_DB2 to round( 10 · log(V_I2 / V_I0) , 1 )
   set V_DB_ANS to 10 · log( (V_I1 + V_I2) / V_I0 )
   set V_HINT to ""
   set V_FEEDBACK to "트랙 합산 dB 를 맞춰라"
```

> `log` 블록 = `operator_mathop` with `OPERATOR: "log"` (상용로그, 밑 10). 이게 **핵심 학습 블록**.

### Stage — Space 입력 (통과 시도)

```
when key 'space' pressed
   if V_GAMEOVER = 0
      set diff to abs(V_DB_USER - V_DB_ANS)
      if diff < 1.0
         change V_SCORE by 1
         set V_FEEDBACK to "정답! +1"
         play pop.wav
         wait 0.4 sec
         broadcast BR_NEW_ROUND
      else
         set V_FEEDBACK to join(join("차이 ", round(diff·10)/10), " dB")
         play beep.wav
```

### HintBtn — 클릭 시 정답 노출

```
when this sprite clicked
   set V_HINT to join("정답: ", join(round(V_DB_ANS · 10) / 10, " dB"))
```

### Judge — 피드백 표시

```
when flag clicked
   forever
      say V_FEEDBACK
```

### TrackA / TrackB — 위치 유지 + 표시

스프라이트 본체는 시각적 표시(음표 패널). 값은 변수 모니터(V_DB1, V_I1) 가 화면에 항상 보임.

```
when flag clicked
   goto (-110, 60)   # TrackA — 왼쪽 패널
   show
   forever
      change y by 2
      wait 0.3 sec
      change y by -2
      wait 0.3 sec   # 살짝 통통 튀는 애니메이션
```

### Stage — 게임오버

```
when I receive BR_GAMEOVER
   set V_GAMEOVER to 1
   set V_FEEDBACK to join("종료! 점수 ", V_SCORE)
   stop other scripts in stage
```

## 슬라이더 monitor 구성

`V_DB_USER` 가 핵심 슬라이더. monitor 정의:

```json
{
  "id": V_DB_USER, "mode": "slider", "opcode": "data_variable",
  "params": {"VARIABLE": "내답dB"},
  "value": 60, "x": 5, "y": 230,
  "visible": true,
  "sliderMin": 40, "sliderMax": 100, "isDiscrete": false
}
```

다른 모니터(점수/라운드/시간/dB1/dB2/I1/I2/정답피드백/힌트)는 `mode: "default"` 또는 `"large"`.

## 재사용 가능한 코드

| 가져올 위치 | 무엇 |
|-------------|------|
| `exponential-shooter/build.py` 의 `BlockBuilder` 클래스 | `vrep`, `op`, `mathop` 헬퍼 그대로 — log 계산이 핵심 |
| `exponential-shooter/build.py` 의 라운드 분기 패턴 (`ROUND_LAYOUTS` 의 `if 라운드 = R`) | 라운드별 (I₁, I₂) 분기에 동일 패턴 |
| `exponential-shooter/build.py` 의 슬라이더 monitor 정의 | min/max/isDiscrete 그대로 |
| `exponential-shooter/build.py` 의 `event_whenkeypressed` "space" 패턴 | Space 통과 시도 트리거 |
| `exponential-shooter/build.py` 의 라운드 라벨 + 점수 모니터 | HUD 그대로 |
| `assets/pop.wav` (재사용) | 정답 사운드 |
| `bacteria-defense` 의 작은 합성 wav 기법 | `beep.wav` 새로 생성 (낮은 톤) |

## 학습 포인트 (수식 / 직관)

### 1. 데시벨의 정의

$$ \text{dB} = 10 \cdot \log_{10}\!\left(\dfrac{I}{I_0}\right) $$

- 강도(I) 가 10배 → dB 는 +10
- 강도가 100배 → dB 는 +20
- 강도가 2배  → dB 는 +3.01 (왜냐하면 `log₁₀(2) ≈ 0.301`)

### 2. 두 소리의 합산

$$ \text{dB}_{\text{total}} = 10 \cdot \log_{10}\!\left(\dfrac{I_1 + I_2}{I_0}\right) $$

이건 `dB₁ + dB₂` 가 **아니다**. 강도는 합쳐지지만 로그는 합쳐지지 않는다. 같은 dB 두 개를 더하면 강도가 2배 → +3 dB 만 추가.

예시:
- 60 dB + 60 dB → 강도 두 개 합치니 2배 → **63 dB**
- 80 dB + 60 dB → 강도 비 100:1 → 큰 쪽이 거의 결정 → **80.04 dB**

게임이 이걸 슬라이더로 손에 익히게 한다.

### 3. Scratch 의 `log` 블록

`operator_mathop` 의 OPERATOR 가 "log" → 상용로그 (밑 10), "ln" → 자연로그. 이 게임에서는 dB 정의 그대로 `log` 사용.

## 테스트 체크리스트 (verifier 확인)

- [ ] `python3 build.py` 가 `데시벨_DJ.sb3` 를 출력하고 `zipfile.testzip()` 가 None
- [ ] project.json 에 `V_DB_USER` 의 slider monitor 가 `sliderMin: 40, sliderMax: 100, isDiscrete: false` 로 존재
- [ ] `operator_mathop` 블록 중 `OPERATOR: "log"` 가 최소 3회 등장 (V_DB1, V_DB2, V_DB_ANS 계산)
- [ ] 라운드 1~5 의 고정 분기가 build 에 반영 (if V_ROUND = 1 .. 5 + else 무작위)
- [ ] Stage 의 `broadcasts` 에 BR_START / BR_NEW_ROUND / BR_TRY / BR_HINT / BR_GAMEOVER 모두 존재
- [ ] 블록 카운트 80 ~ 150 범위 (★★ 난이도)
- [ ] 모든 block 의 parent/next 가 같은 sprite 안의 유효한 ID

## 빌드 노트

- Scratch `log` 는 상용로그 (정확히 dB 정의에 맞음 — 별도 변환 불필요)
- `10 ^ (pick random 3 to 7)` 같은 식은 `operator_mathop "10 ^"` + `operator_random`
- 라운드 5 의 의도 (I₁=I₂=1000=I₀): dB1=dB2=0, ans=10·log₁₀(2)≈3.01. "0 dB 두 개 합쳐도 0 이 아니다" 가 인상적이라 일부러 포함.
- 슬라이더 range 40~100 은 일상 소음 영역 (도서관~록 콘서트). 라운드 5 정답은 3 이라 슬라이더 밖이지만, slider 는 `sliderMin` 미만으로 끌어도 입력 가능하다는 한계 인지. 대안: range 0~100 또는 모든 라운드 답을 40 이상으로 두기. → **slider range 를 0~100 으로** 확장.
- 통과 허용 오차 ±1 dB 가 학습용으로 적절 (너무 좁으면 정답 거의 못 맞춤, 너무 넓으면 학습 부족).
