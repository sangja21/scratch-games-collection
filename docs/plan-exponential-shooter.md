# 📈 지수함수 슈터 — 구현 계획

> **주제**: 지수함수 `y = a · b^x` + 로그 스케일의 의미
> **카테고리**: 학습형
> **난이도**: ★★★ (블록 ~200개)
> **폴더**: `games/exponential-shooter/`
> **출력**: `지수함수_슈터.sb3`
> **베이스**: `polynomial-shooter` 코드 약 70% 재사용

## 학습 목표

1. **밑 `b` 와 계수 `a` 의 역할 분리**
   - `a` = y절편 (x=0 일 때 값)
   - `b` = 성장률 (1보다 크면 증가, 작으면 감소, 1이면 상수)
2. **`b=1` 의 경계** — 정확히 1 일 때 직선이 되는 순간을 시각으로 확인
3. **로그 스케일** — "로그 보기" 토글을 누르면 지수곡선이 **직선**으로 변한다. 이게 로그의 직관: 지수의 가파름을 풀어주는 변환.
4. **지수의 음수 입력** — x 가 음수일 때 `b^x = 1/b^|x|` 가 어떻게 보이는지

## 게임 한 줄

화면에 풍선들이 흩어져 있다. 슬라이더로 `a`, `b` 를 조절해 지수곡선 `y = a · b^x` 가 풍선을 지나가게 만들고 로켓을 발사한다. **로그 토글** 을 켜면 좌표축이 로그 스케일로 변해 곡선이 직선이 된다.

## 화면 레이아웃 (480×360)

```
┌────────────────────────────────────────┐
│ y = 2.0 · 1.5^x        점수: 12        │
│ [a: ──●───] 2.0  [b: ──●───] 1.5       │
│ [로그 보기 ☐]   [발사 ▶]   라운드 3    │
├────────────────────────────────────────┤
│                                        │
│         🎈                              │
│                  🎈                    │
│  🚀━━━━━━━━━━━━━━━━━━━━━━━              │  ← 곡선 미리보기 (분홍)
│            🎈                          │
│   🎈                                   │
└────────────────────────────────────────┘
```

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **Rocket** | 기존 polynomial-shooter `rocket.svg` 재사용 | 곡선 따라 글라이드 |
| **Balloon** | 기존 `balloon.svg` 재사용, 색상 4종 (라운드 마커) | 클론으로 4~6개 |
| **Curve Pen** | 빈 스프라이트, pen 확장으로 곡선 그리기 | `polynomial-shooter` 와 동일 패턴 |
| **HUD-Eq** | 식 표시 | 변수 V_EQ 모니터로 처리 |
| **Background** | 좌표축이 그려진 그래프지 — **두 코스튬**: `linear` (선형) / `log` (로그 스케일, y축 눈금 1/10/100/1000) | 토글 시 switch costume |

**사운드**: `pop.wav` (재사용), `whoosh.wav` (발사 — polynomial-shooter 것 재사용), `toggle.wav` (스케일 변환 시).

## 변수 / 메시지

```
변수 (전역)
  V_A         계수 a   (슬라이더 0.5 ~ 5.0, 0.1 step)
  V_B         밑   b   (슬라이더 0.3 ~ 3.0, 0.1 step)
  V_LOG       로그 보기 0/1
  V_SCORE
  V_ROUND
  V_XSTEP     곡선 그리기 x 증분 (= 0.2)
  V_PREV_X    펜용 (로컬)
  V_EQ        식 문자열   "y = 2.0 · 1.5^x"
  V_BCOUNT    남은 풍선 수

메시지
  BR_START
  BR_DRAW_CURVE     슬라이더 변할 때마다 곡선 다시 그리기
  BR_FIRE
  BR_TOGGLE_LOG
  BR_HIT_BALLOON
  BR_ROUND_CLEAR
```

## 곡선 좌표 변환 (핵심)

Scratch 좌표는 `x: -240..240, y: -180..180`. 게임 내 논리 좌표(`x_g`)를 `-6..6` 으로 두고 다음 변환을 사용한다.

**선형 모드** (`V_LOG = 0`):
```
화면x = 40 · x_g                # 1단위 = 40px
화면y = 30 · (a · b^x_g)  - 120 # 1단위 = 30px, 바닥에서 -120 오프셋
```

**로그 모드** (`V_LOG = 1`):
```
화면y = 30 · log_10(a · b^x_g) - 30
      = 30 · (log_10(a) + x_g · log_10(b)) - 30   # ← 직선!
```

이 변환식 자체가 학습 포인트라 README 와 코드 주석에 명시.

## 게임 흐름

```
[초록 깃발]
   ↓
초기화: V_A=2, V_B=1.5, V_LOG=0, V_ROUND=1
   ↓
풍선 6개 무작위 배치 (라운드별 패턴)
   ↓
[메인 루프]
   ├─ V_A, V_B 슬라이더 값 변할 때마다 → BR_DRAW_CURVE
   ├─ 로그 토글 클릭 → V_LOG 반전 → 배경 코스튬 교체 + BR_DRAW_CURVE
   ├─ "발사" 클릭 → 로켓이 곡선 따라 글라이드 → 풍선 충돌 시 pop
   └─ V_BCOUNT = 0 → BR_ROUND_CLEAR → 다음 라운드
```

## 핵심 스크립트 (의사코드)

### 식 표시

```
forever
   set V_EQ to "y = " & V_A & " · " & V_B & "^x"
```

### 곡선 그리기 (Curve Pen)

```
when I receive BR_DRAW_CURVE
   pen up; erase all
   set V_PREV_X to -6
   set x to screen_x(-6); set y to screen_y(eval(-6))
   pen down; set pen color to pink; set pen size to 2
   repeat 60
      change V_PREV_X by V_XSTEP        # 0.2
      go to (screen_x(V_PREV_X), screen_y(eval(V_PREV_X)))
   pen up

# screen_x(x_g) = 40 * x_g
# screen_y(y_v) = (V_LOG=0) ? (30*y_v - 120) : (30*log10(y_v) - 30)
# eval(x_g)    = V_A * (V_B ^ x_g)
```

> Scratch 의 `^` 는 없음 → **`[지수 ▼] of (x_g · log(V_B))` = `10^(x_g·log b)` = `b^x_g`** 로 구현. (이것도 학습 포인트: a^b = 10^(b·log a))

### 로켓 발사

```
when I receive BR_FIRE
   set x to screen_x(-6); set y to screen_y(eval(-6))
   show
   set V_T to -6
   repeat 60
      change V_T by 0.2
      go to (screen_x(V_T), screen_y(eval(V_T)))
      if touching Balloon?
         broadcast BR_HIT_BALLOON   # 풍선이 자기 클론 삭제
   hide
```

### 로그 토글

```
when "로그 보기" clicked
   set V_LOG to (1 - V_LOG)
   if V_LOG = 1
      switch backdrop to "log"
   else
      switch backdrop to "linear"
   broadcast BR_DRAW_CURVE
   play toggle.wav
```

## 라운드 / 풍선 배치

| 라운드 | 풍선 위치 | 의도 |
|--------|----------|------|
| 1 | `(0, 2), (1, 4), (2, 8), (3, 16)` | `y=2^x` 정답: a=1, b=2 |
| 2 | `(0, 1), (1, 0.5), (2, 0.25), (3, 0.125)` | 감소 — b<1 의미 |
| 3 | `(-2, 0.25), (-1, 0.5), (0, 1), (1, 2), (2, 4)` | 음수 x 의 의미 |
| 4 | 무작위 4점 — 플레이어가 a, b 직접 추론 | 자유 라운드 |
| 5 | **로그 모드만 사용 가능** — 점들이 로그 스케일에서 직선 위에 있음 | 로그 변환 응용 |

## 단계별 구현 체크리스트

- [ ] 폴더 `games/exponential-shooter/` + assets 디렉토리
- [ ] polynomial-shooter 의 `build.py` 복사 → 시작점
- [ ] 변수 ID 재명명 (`V_A`, `V_B` 유지 / `V_LOG`, `V_EQ` 추가)
- [ ] 배경 SVG 두 종 — `linear` 와 `log` (로그 눈금: 0.1, 1, 10, 100)
- [ ] 슬라이더 범위 변경 (a, b 새 범위)
- [ ] 곡선 평가식을 `a·b^x` 로 — Scratch 의 `[지수 ▼] of` 활용
- [ ] 좌표 변환 두 종 구현 (선형 / 로그)
- [ ] 로그 토글 UI (스프라이트 버튼)
- [ ] 라운드별 풍선 배치 — 데이터 테이블화
- [ ] 식 표시 V_EQ
- [ ] 첫 빌드 → 동작 확인 → 슬라이더 step 조정
- [ ] README.md (조작법 + 학습 포인트)
- [ ] 루트 README.md + game-candidates.md 표 업데이트

## 빌드 노트

- Scratch 의 `^` 연산자 없음 → `[지수 ▼] of (x · log y)` 또는 `[e^ ▼] of (x · ln y)` 사용
- `log` 블록은 상용로그(밑 10), `ln` 블록은 자연로그 — 둘 다 사용 가능
- `b^x` 가 `x` 가 음수일 때 — `[지수 ▼] of` 는 잘 처리됨 (확인 필요, 그래프 그릴 때 `b<0` 은 허용 안 함: 슬라이더 최소값 0.3)
- pen 으로 곡선 그릴 때 — 한 프레임에 전부 그리지 말고 `wait 0` 으로 끊으면 슬라이더 조작 반응성 ↑
- polynomial-shooter 의 발사 애니메이션은 그대로 — 곡선 평가식만 교체

## 참고

- polynomial-shooter `build.py` 라인 ~100 부근의 곡선 그리기 패턴, 라인 ~400 부근의 발사 스크립트 그대로 활용
- 메커닉 출처: polynomial-shooter 의 확장 + `docs/game-candidates.md` 의 1순위 아이디어 변형 (삼각함수 서핑이 sin 대신 지수)
