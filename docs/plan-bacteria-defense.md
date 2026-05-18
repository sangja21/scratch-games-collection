# 🦠 박테리아 디펜스 — 구현 계획

> **주제**: 지수 — 지수 증가의 폭발성을 손으로 체감
> **카테고리**: 학습형 + 액션
> **난이도**: ★★★ (블록 ~200개)
> **폴더**: `games/bacteria-defense/`
> **출력**: `박테리아_디펜스.sb3`

## 학습 목표

플레이어가 게임 중 다음을 *체감*하도록 한다.

1. **지수 증가의 폭발성** — "한 마리만 늦게 잡았는데" 1초 뒤에 두 배가 된다.
2. **밑(base) 의 의미** — 분열 속도 슬라이더(밑 `r` = 1.5 / 2 / 3)를 직접 바꿔보며 곡선의 가파름이 달라짐을 본다.
3. **로그의 실용** — 화면 상단 "임계치까지 남은 시간"은 `t = log_r(N_max / N)` 로 실시간 계산되어 표시된다. 로그 = "몇 번 곱해야 그 수가 되는가" 를 게임 HUD가 가르친다.

## 게임 한 줄

화면에 박테리아 한 마리가 등장한다. 그냥 두면 매 `T` 초마다 `r` 배로 분열한다. 항생제를 발사해 박테리아를 클릭으로 제거하라. 총 개체수가 임계치(예: 1024) 도달하면 게임 오버.

## 화면 레이아웃 (480×360)

```
┌────────────────────────────────────────┐
│ 개체수: 32   임계까지: 5 / log₂(1024/32) │  ← HUD
│ 라운드: 3   r(분열률): 2.0  T: 1.5s     │
├────────────────────────────────────────┤
│                                        │
│         🦠      🦠                      │
│              🦠   🦠  🦠                │  ← 페트리 접시 영역
│      🦠  🦠   🦠    🦠                  │
│                                        │
│  ─────── 항생제 게이지 ──────           │
└────────────────────────────────────────┘
```

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **Bacteria** (clone-driven) | `idle` (초록), `splitting` (노랑 깜빡), `dying` (회색) | 단일 SVG, 살짝 흔들리는 애니메이션은 회전으로 처리 |
| **Antibiotic** (cursor) | `target` (조준원), `firing` (밝은 원) | 마우스 따라옴 |
| **Background** | 페트리 접시 격자 + HUD 영역 분리 | `polynomial-shooter` 배경 톤 재사용 가능 |
| **HUD-Equation** | 식 표시용 텍스트 sprite | `say` 블록 또는 `보이기` 변수 |

**사운드**: `pop.wav` (기존 재사용 — 박테리아 제거), `split.wav` (낮은 톤, 분열 시), `alarm.wav` (임계치 80% 시 경고).

## 변수 / 메시지

```
변수 (전역)
  V_N         현재 박테리아 개체수 (= 클론 개수)
  V_NMAX      임계치 (라운드별: 256 → 512 → 1024 → ...)
  V_R         분열률 (라운드별: 1.5 → 2 → 2 → 3)
  V_T         분열 주기(초)
  V_ROUND     현재 라운드
  V_SCORE     누적 점수 (= 처치한 박테리아 수)
  V_REMAIN    임계까지 남은 분열 횟수 = log_r(N_MAX / N)  (소수 1자리)
  V_GAMEOVER  0/1
  V_HISCORE   최고점수 (저장)

변수 (클론 로컬)
  L_AGE       이 박테리아의 생존 시간 (분열 타이밍 계산용)

메시지
  BR_START         게임 시작
  BR_TICK_SPLIT    분열 타이밍 트리거 (배경이 매 V_T 초마다 송신)
  BR_GAMEOVER
  BR_NEXT_ROUND
```

## 게임 흐름

```
[초록 깃발]
   ↓
초기화: V_N=1, V_R=1.5, V_T=2, V_NMAX=256, V_ROUND=1
   ↓
박테리아 클론 1마리 생성 (정중앙)
   ↓
[메인 루프]
   ├─ 매 V_T 초: BR_TICK_SPLIT 송신 → 모든 클론이 옆에 자기 복제본 생성
   ├─ 마우스 클릭 + 박테리아 hit: 클론 삭제, V_SCORE++, pop.wav
   ├─ V_REMAIN = log(V_NMAX / V_N) / log(V_R)   매 0.1초 갱신
   ├─ V_N >= V_NMAX  →  BR_GAMEOVER
   └─ 라운드 클리어 조건(처치 N마리 누적) → BR_NEXT_ROUND
                                             V_R↑ 또는 V_T↓, V_NMAX↑
```

## 핵심 스크립트 (의사코드)

### 배경 — 분열 타이머

```
when flag clicked
   초기화
   broadcast BR_START
   forever
      wait V_T seconds
      broadcast BR_TICK_SPLIT
```

### 박테리아 — 분열

```
when I receive BR_TICK_SPLIT
   set L_AGE to L_AGE + V_T
   repeat (V_R - 1)               # r=2 → 복제 1개, r=3 → 복제 2개
      create clone of myself      # 분열률을 클론 수로 표현
   change V_N by (V_R - 1)        # 개체수 갱신
   change costume → splitting → idle (0.15s 깜빡)
   play sound split.wav at -25dB
```

> ⚠️ `V_R` 이 소수(예: 1.5) 일 때 — 매 틱 50% 확률로 1개 추가 클론. `(pick random 0 to 1) < (V_R - floor(V_R))` 패턴.

### 박테리아 — 클릭 처리

```
when this sprite clicked
   if V_GAMEOVER = 0
      change V_SCORE by 1
      change V_N by -1
      play pop.wav
      delete this clone
```

### HUD — 로그 계산

```
forever
   if V_N > 0
      set V_REMAIN to (round((log(V_NMAX / V_N) / log(V_R)) * 10)) / 10
   else
      set V_REMAIN to "∞"
```

> Scratch 의 `log` 블록은 상용로그(밑 10). 임의 밑 로그는 **밑 변환 공식** `log_r(x) = log(x) / log(r)` 으로 계산. 이게 학습 포인트라서 코드 주석으로도 노출.

### 게임 오버

```
when I receive BR_GAMEOVER
   set V_GAMEOVER to 1
   stop other scripts in sprite
   say "임계치 도달! 점수 V_SCORE" for 5 sec
   stop all
```

## 난이도 / 밸런스 (라운드 표)

| 라운드 | V_R (분열률) | V_T (주기) | V_NMAX | 처치 목표 |
|--------|--------------|-----------|--------|----------|
| 1 | 1.5 | 2.5s | 128 | 30 |
| 2 | 2.0 | 2.0s | 256 | 60 |
| 3 | 2.0 | 1.5s | 512 | 120 |
| 4 | 2.5 | 1.5s | 768 | 200 |
| 5 | 3.0 | 1.5s | 1024 | ∞ (sudden-death) |

## 단계별 구현 체크리스트

- [ ] 폴더 `games/bacteria-defense/` + assets 디렉토리 생성
- [ ] 박테리아 SVG (60×60, 3 costumes)
- [ ] 페트리 접시 배경 SVG
- [ ] 분열 사운드(`split.wav`) — 짧은 비트 또는 합성, 기존 `pop.wav` 와 음색 다르게
- [ ] `build.py` 초안 — 기존 두 게임 헬퍼(`mk`, `gen`, `chain`, `num`, `slot`) 복사
- [ ] 변수/메시지 ID 정의
- [ ] 박테리아 분열 스크립트 (소수 분열률 처리 포함)
- [ ] 클릭 제거 스크립트
- [ ] 로그 HUD 스크립트 (밑 변환 공식 명시)
- [ ] 라운드 진행 / 게임 오버
- [ ] 첫 빌드 → Scratch 에서 동작 확인 → 밸런스 조정
- [ ] README.md (게임 소개 + 학습 포인트 + 조작법)
- [ ] 루트 README.md + game-candidates.md 표 업데이트

## 빌드 노트

- 클론 수가 1000 가까이 가면 Scratch 의 클론 한도(300개) 초과. **두 가지 옵션**:
  1. **시각적 박테리아 = 1 클론 = N 개체** (클론 1개가 V_N 값을 분할해 가지는 추상 모델). 코드 단순하지만 직관 손실.
  2. **클론 한도 도달 시 "콜로니" 모드** — 클론은 멈추고 V_N 만 지수 증가, 화면에는 큰 박테리아 1개에 숫자 표시. *권장*: 라운드 5(sudden death) 에서만 발동.
- 매 틱마다 모든 클론에서 `V_N` 을 갱신하면 race condition 발생 가능. **항상 부모(배경) 가 V_R 만큼 증가시키고, 클론은 자기 복제만 담당**.

## 참고

- 곡선 비교: `polynomial-shooter` 의 곡선 미리보기 스타일 차용 가능 (선택 사항 — 화면 우측 작은 패널에 `y = a·r^x` 곡선과 현재 위치 점)
- 메커닉 출처: 자체 설계 (지수함수 단원 직결)
