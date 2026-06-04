# 풍선 펌프 (balloon-pump) — Plan

> 화면 가운데 풍선에 펌프로 바람을 넣는다. **스페이스를 꾹 누르면** 풍선이 점점 커지고(크기 +1/틱) 점수도 함께 오른다. 너무 욕심내면 **펑!** 터져서 그 라운드는 0점. 터지기 직전에 스페이스를 떼면 그때까지 모은 점수가 확정된다. 라운드마다 터지는 한계치(크기 120~220)는 랜덤이고 비공개 — 풍선이 한계에 가까워지면 **떨림 + 색 변화**로 슬쩍 경고한다. 5라운드 합계와 베스트 기록을 겨룬다.
> 베이스: `games/cowboy-duel/build.py`(라운드 진행 + 합계/베스트 + 결과 배너 + "스페이스 1키" 긴장형 액션) + `games/apple-catch/build.py`(결과 배너 show/hide + pop 사운드 재사용). 풍선 크기 펌프(`set size`) + 떨림(`change x by ±`) + 파편 클론 터짐은 신규지만 모두 단순.
> 학습 콘셉트 **없음**. 순수 액션 + 긴장감(욕심 vs 안전 트레이드오프). 초등학생 대상 직관적(스페이스 1키만). 추상 개념·수식 노출 절대 금지. 점수가 크기^1.5 로 가속되는 것은 내부 계산일 뿐 플레이어에게는 "크게 불수록 점수가 빨리 오른다"로만 체감된다. (MEMORY.md → feedback-game-design 준수)

---

## 1. 한 줄 룰

가운데 풍선을 **스페이스를 꾹 눌러** 점점 크게 분다. 크게 불수록 점수가 빨리 오른다. 하지만 풍선마다 터지는 한계가 다르고 보이지 않는다 — 풍선이 떨리고 색이 변하기 시작하면 위험 신호! 터지기 직전에 스페이스를 떼면 그때까지 모은 점수가 내 것. 너무 욕심내서 터뜨리면 그 라운드는 0점. 5라운드 합계로 베스트를 노린다.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- SVG 좌표(0..480 / 0..360) ↔ Scratch 좌표 변환: `sx = svgX - 240`, `sy = 180 - svgY`.
- **풍선 위치(피벗)**: x = 0, y = +20 (화면 중앙, 살짝 위). 풍선은 항상 여기서 부푼다. 풍선 코스튬 rotationCenter 를 **꼭지(아래쪽)** 에 두면 위로만 커져 펌프 호스와 자연스럽게 연결(빌더 선택 — 중앙 rotationCenter 도 허용).
- **펌프 위치**: x = -120, y = -120 (화면 왼쪽 아래). 풍선 꼭지와 호스로 연결. 스페이스 누를 때 손잡이가 위아래로 들썩이는 2코스튬 연출.
- **풍선 꼭지(호스 연결점)**: y = -60 근처. 펌프 → 호스 → 풍선 아래쪽으로 이어지는 그림(배경 또는 펌프 코스튬에 포함).
- **HUD(상단)**: 라운드 / 이번점수(현재 부는 중 점수) / 합계 / 베스트.
- **떨림**: 한계 접근 시 풍선 x 를 매 틱 ±2 흔든다. 단 **흔들림 시작점은 한계치의 60~80% 랜덤 지점** — 한계치를 직접 누설하지 않도록 라운드마다 떨림 시작 비율을 다르게 한다.
- **색 변화**: 크기가 커질수록 풍선 색 효과(color effect)를 점점 올려 노랑→주황→빨강 쪽으로 물들게(위험 경고). 색 효과 양도 떨림과 같은 "현재 크기 / 한계치" 비율 기반.

```
+----------------------------------------------------------+ y=+180
| 라운드:2/5   이번점수:340   합계:1250   베스트:1800       |  ← 변수 모니터 (상단)
|                                                          |
|                      (  ●●●  )                           |  y=+20  풍선(크기=size)
|                     ( ●●●●●● )   ← 커질수록 색 빨개지고   |
|                      (  ●●●  )      떨림(±2 x흔들)        |
|                         │  ← 호스                         |
|              ┌──┐       │                                 |  y=-60
|              │펌│───────┘                                 |
|         ┌────┤프├────┐    ← 펌프(손잡이 들썩)            |  y=-120
|         └────┴──┴────┘                                   |
|====================================================== ==  | y=-150 바닥
+----------------------------------------------------------+ y=-180
  x=-240                                              x=+240
              [ 스페이스 꾹 = 펌프 / 떼면 = 점수 확정 ]
```

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 코스튬 |
|---|------|------|--------|
| 0 | Stage | 배경(방/축제 톤) + 전역 변수 + 라운드 진행(5라운드) + 한계치 생성 + 합계/베스트 판정 | bg.svg |
| 1 | 풍선 | **메인 컨트롤러**. 펌프 입력(스페이스 길게)으로 크기 증가 + 점수 가속 + 떨림/색 경고 + 한계 도달 시 터짐 판정 + 라운드별 색 변경 | balloon.svg (1개, 색은 color effect 로 라운드별 변경) |
| 2 | 펌프 | 왼쪽 아래 펌프. 스페이스 누르는 동안 손잡이 들썩(2코스튬 번갈아). 안 누르면 정지 코스튬 | pump_up.svg, pump_down.svg |
| 3 | 파편 | 풍선이 터질 때 사방으로 튀는 조각 클론(8~12개). 평소 숨김 | shard.svg |
| 4 | 결과배너 | 라운드 결과("펑! 0점" / "+OOO점") + 최종 결과("합계 OOO!" / "신기록!") 배너. 평소 숨김 | pop.svg(터짐), safe.svg(안전 확정), result.svg(최종), newbest.svg(신기록) |

총 5 스프라이트(Stage 포함). 파편 클론 외 리스트 없음. 파편은 연출이라 빌더 시간 부족 시 개수 축소 허용(아래 검증에서 명시).

> **풍선 색 = color effect**: 코스튬을 라운드 색깔별로 여러 장 그리지 않고, 단일 `balloon.svg`(중간 채도) 1장에 `set color effect to (라운드별 기준값)` 으로 라운드마다 다른 색을 준다. 그 위에 "위험 경고용 색 변화"는 별도 효과로 겹치기 어려우므로, **위험 경고는 `set color effect to (라운드기준색 + 위험가산)`** 로 한 변수에서 합산해 적용한다(아래 7.2). 빌더 단순화: 색 효과 한 종류만 쓴다.

---

## 4. 변수 (Stage 글로벌)

| 한국어 | ID | 초기값 | 의미 |
|--------|----|--------|------|
| 게임상태 | `varState01` | 0 | 0=펌프 중(입력 가능), 1=라운드 결과 처리중, 2=전체 종료 |
| 라운드 | `varRound02` | 1 | 현재 라운드 번호(1~5) |
| 총라운드 | `varMaxRound03` | 5 | 전체 라운드 수 |
| 이번점수 | `varCurScore04` | 0 | 지금 부는 중 누적 점수. 떼면 합계로 확정, 터지면 버림 |
| 합계 | `varTotal05` | 0 | 확정된 라운드 점수 합 |
| 베스트 | `varBest06` | 0 | 5라운드 합계 최고 기록 |
| 현재크기 | `varSize07` | 80 | 풍선 현재 크기(size %). 펌프할 때마다 +1/틱. 시작 80 |
| 한계치 | `varLimit08` | 0 | 이번 라운드 터지는 크기(120~220 랜덤, **비공개**) |
| 떨림시작 | `varShakeStart09` | 0 | 떨림/색경고 시작 크기 = 한계치 × (0.60~0.80 랜덤). 누설 방지로 라운드마다 비율 다름 |
| 라운드결과 | `varRResult10` | 0 | 0=미정, 1=안전 확정(점수 획득), 2=터짐(0점) |
| 펌프중 | `varPumping11` | 0 | 1=스페이스 눌러 펌프 중, 0=정지. 펌프 손잡이 연출이 참조 |

> **점수 가속(크기^1.5)**: 펌프 매 틱마다 `이번점수 ← round((현재크기 - 80) ^ 1.5)` 로 갱신(80 은 시작 크기 = 부푼 양 0 기준). `^1.5` 는 `((현재크기-80) * sqrt(현재크기-80))` 또는 `operator_mathop`(없으므로) → `(현재크기-80) * ((현재크기-80) 의 제곱근)` 으로 구현(아래 7.2). 효과: 작게 멈추면 점수 적고, 크게 불수록 점수가 가파르게 오름 → "조금 더, 조금만 더…" 욕심 유발. 계수/지수는 빌더가 체감 조정 가능(잘 불면 라운드당 300~600점).

풍선 sprite-local 변수: 없음(모든 상태를 Stage 글로벌로 — 펌프·파편·결과배너가 같은 값을 참조).

파편 sprite-local: 없음(클론 방향/속도는 클론 생성 시 인라인 결정; 필요 시 `lvVx01`,`lvVy02` 2개 허용).

---

## 5. 방송 (broadcasts)

| 한국어 | ID | 트리거 |
|--------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 → 변수 초기화 직후 |
| 라운드시작 | `brRoundStart02` | 새 라운드 시작(게임시작 직후 + 매 라운드 결과 후). 한계치·떨림시작·라운드색 새로 뽑고, 풍선 크기 80 으로 리셋, 펌프 입력 가능 |
| 터짐 | `brPop03` | 현재크기 ≥ 한계치 → 풍선 펑! (파편 클론 + 소리 + 풍선 숨김), 라운드결과=2 |
| 확정 | `brConfirm04` | 펌프 중 스페이스 뗌 → 이번점수 합계로 확정(라운드결과=1), 안전 배너 |
| 라운드끝 | `brRoundEnd05` | 터짐/확정 후 결과 배너 + 점수 처리 트리거. Stage 가 다음 라운드 or 최종 판정 |
| 결과 | `brResult06` | 라운드 5 종료 → 합계/베스트 최종 배너 |

---

## 6. 씬 / 상태머신

```
[깃발]
  → init(라운드1, 총라운드5, 합계0, 베스트유지?→0, 게임상태0)
  → broadcast 게임시작
  → broadcast 라운드시작 (첫 라운드)
   │
   ▼
[라운드시작]  (게임상태=0)
  - 한계치   ← pick random 120..220        (이번 라운드 터지는 크기, 비공개)
  - 떨림시작 ← 한계치 * (pick random 60..80)/100   (누설 방지 랜덤 비율)
  - 현재크기 ← 80,  이번점수 ← 0,  라운드결과 ← 0
  - 풍선: size 80, color effect = 라운드색(라운드 번호로 결정), 떨림/색경고 0, 보이기
  - 펌프중 ← 0
   │
   ▼
[펌프]  (게임상태=0, 풍선 스프라이트가 매 틱 관리)
  repeat (게임상태=0 인 동안):
    if (key space pressed?):
      펌프중 ← 1
      현재크기 ← 현재크기 + 1                 # 펌프 +1/틱
      set size to 현재크기
      이번점수 ← round((현재크기-80) * sqrt(현재크기-80))   # 크기^1.5 가속
      # 위험 경고: 현재크기 ≥ 떨림시작 이면 떨림 + 색 빨개짐
      if 현재크기 ≥ 떨림시작:
        change x by (pick random -2 to 2)      # 떨림 (단 평균 0 → 제자리 흔들)
        set color effect to (라운드색 + (현재크기-떨림시작)*위험계수)
      # 터짐 판정
      if 현재크기 ≥ 한계치:
        라운드결과 ← 2
        게임상태 ← 1
        broadcast 터짐
    else:
      펌프중 ← 0
      # 펌프하던 중 떼면 = 확정 (단, 한 번이라도 불었을 때만)
      if 현재크기 > 80:
        라운드결과 ← 1
        게임상태 ← 1
        broadcast 확정
    wait 0.02
   │
   ├─(현재크기≥한계치)─▶ [터짐]  라운드결과2
   │                       - 파편 클론 사방으로, pop 소리, 풍선 숨김
   │                       - 이번점수는 버림(0점)
   │                       - broadcast 라운드끝
   │
   └─(스페이스 뗌)──────▶ [확정]  라운드결과1
                           - 안전 배너 "+이번점수", 띵 소리
                           - broadcast 라운드끝
   │
   ▼
[라운드끝]  (게임상태=1)  ← Stage 처리
  - if 라운드결과=1: 합계 ← 합계 + 이번점수      (확정 점수 합산)
  - if 라운드결과=2: (합계 변화 없음 — 0점)
  - 결과 배너 표시(pop / safe)
  - wait 1.4
  - if 라운드 < 총라운드:
      라운드 ← 라운드 + 1
      wait 0.4
      broadcast 라운드시작                       (다음 라운드)
  - else:
      게임상태 ← 2
      if 합계 > 베스트: 베스트 ← 합계
      broadcast 결과                              (최종 배너)
   │
   ▼ [깃발 재클릭] → 처음으로
```

---

## 7. 메커닉 상세

### 7.1 Stage — 라운드(5판) 진행 / 한계치 생성 / 판정

```
when flag clicked:
  라운드 ← 1
  총라운드 ← 5
  합계 ← 0
  베스트 ← 0                # (베스트를 세션 내 유지하려면 init 에서 0 으로 두지 말 것 — 단순화: flag 마다 0)
  게임상태 ← 0
  이번점수 ← 0
  broadcast 게임시작
  broadcast 라운드시작

when receive 라운드시작:
  라운드결과 ← 0
  이번점수 ← 0
  현재크기 ← 80
  # 이번 라운드 한계치 + 떨림 시작점(비공개)
  한계치 ← pick random 120 to 220
  떨림시작 ← round( 한계치 * (pick random 60 to 80) / 100 )
  펌프중 ← 0
  wait 0.1                  # 풍선/펌프가 라운드시작 핸들러로 리셋될 시간
  게임상태 ← 0              # 펌프 입력 개시

when receive 라운드끝:
  if 라운드결과 = 1:
    합계 ← 합계 + 이번점수
  # 라운드결과 = 2(터짐)은 점수 0 → 합계 변화 없음
  wait 1.4                  # 결과 배너 감상
  if 라운드 < 총라운드:
    라운드 ← 라운드 + 1
    wait 0.4
    broadcast 라운드시작
  else:
    게임상태 ← 2
    if 합계 > 베스트:  베스트 ← 합계
    broadcast 결과
```

> **한계치는 절대 모니터에 표시하지 않는다**(`varLimit08`/`varShakeStart09` 는 화면 비표시). 누설되면 게임이 무의미해진다. 빌더는 이 두 변수의 monitor visible=false 보장.
> **떨림시작 = 한계치 × 0.60~0.80**: 한계치가 200이면 떨림은 120~160 사이 어디선가 시작 → 떨리기 시작해도 "아직 한참 남았을 수도, 곧 터질 수도" 라서 한계치가 역산되지 않는다. 라운드마다 비율이 달라 패턴 학습 불가.

### 7.2 풍선 — 펌프 입력 + 점수 가속 + 떨림/색 경고 + 터짐 (핵심)

풍선 스프라이트가 라운드시작 시 리셋되고, `게임상태=0` 동안 매 틱 펌프 입력을 처리한다.

```
when flag clicked:
  goto (0, 20)
  switch costume balloon
  set size to 80
  clear graphic effects
  hide                      # 게임시작 전엔 숨김(라운드시작에서 show)

when receive 라운드시작:
  goto (0, 20)
  현재크기 ← 80
  set size to 80
  set color effect to (라운드번호로 색 결정 — 아래 라운드색 식)
  show

# 라운드색: 라운드마다 풍선 기본 색을 다르게(color effect 오프셋)
#   라운드색 = (라운드 - 1) * 40    → 1:0(빨강계) 2:40 3:80 4:120 5:160 등 색상환 회전
#   (이 값을 위험 경고 가산과 합쳐 set color effect 한 번에 적용)

when flag clicked:   (별도 스크립트 — 펌프 루프)
  forever:
    if 게임상태 = 0:
      if (key space pressed?):
        펌프중 ← 1
        현재크기 ← 현재크기 + 1
        set size to 현재크기
        # 점수 가속: (부푼양)^1.5 = (부푼양) * sqrt(부푼양)
        부푼양 ← 현재크기 - 80          # (인라인 가능: 매번 현재크기-80)
        이번점수 ← round( 부푼양 * (sqrt of 부푼양) )
        # 위험 경고(떨림 + 색): 떨림시작 넘으면
        if 현재크기 ≥ 떨림시작:
          change x by (pick random -2 to 2)
          set color effect to ( (라운드-1)*40 + (현재크기 - 떨림시작) * 8 )
        else:
          set x to 0                     # 떨림 구간 밖이면 제자리 고정
          set color effect to ( (라운드-1)*40 )
        # 터짐 판정
        if 현재크기 ≥ 한계치:
          라운드결과 ← 2
          게임상태 ← 1
          broadcast 터짐
      else:
        # 스페이스 안 눌림
        if (펌프중 = 1) AND (현재크기 > 80):
          # 펌프하던 손을 뗌 = 점수 확정
          펌프중 ← 0
          set x to 0
          라운드결과 ← 1
          게임상태 ← 1
          broadcast 확정
        펌프중 ← 0
    wait 0.02

when receive 터짐:
  # 풍선 펑! → 숨김(파편이 대신 튐)
  hide
  set x to 0

when receive 확정:
  # 안전 확정 → 잠깐 통통 튀는 연출 후 라운드끝 트리거는 Stage 가
  set x to 0
  repeat 2:                 # 가벼운 "탄력" 연출(선택)
    set size to (현재크기 + 4)
    wait 0.05
    set size to 현재크기
    wait 0.05
  broadcast 라운드끝

when receive 터짐:        (두 번째 핸들러 또는 위와 합침)
  broadcast 라운드끝       # 터짐 연출 후 라운드끝 (파편이 트리거해도 됨 — 한 곳만)
```

> **`^1.5` 구현**: Scratch 에 거듭제곱 블록이 없으므로 `부푼양^1.5 = 부푼양 * sqrt(부푼양)`. `sqrt` 는 `operator_mathop`(sqrt). 예: 부푼양 100 → 100 * 10 = 1000점, 부푼양 40 → 40 * 6.3 = 252점. 작게 멈추면 손해, 크게 불수록 점수 가속 → 욕심 트레이드오프. 계수 조정으로 점수 스케일 튜닝.
> **떨림이 제자리 흔들리게**: `change x by (pick random -2 to 2)` 는 누적되면 풍선이 한쪽으로 흘러갈 수 있다. 더 안전한 안: `set x to (pick random -2 to 2)`(원점 0 기준 ±2 흔들). 빌더 권장 = `set x to (0 + pick random -2 to 2)`. 떨림 구간 밖에서는 `set x to 0` 으로 고정.
> **색 경고**: `set color effect to ((라운드-1)*40 + (현재크기-떨림시작)*8)`. 라운드 기본색에 위험 구간 진입분(현재크기-떨림시작)을 더해 점점 색이 변함(빨개짐 체감). 계수 8 은 빌더 튜닝.
> **확정 조건 `현재크기 > 80`**: 한 번도 안 불고 떼면(시작 직후) 확정되지 않게 — 최소 한 번은 펌프해야 라운드 성립. (스페이스를 누르기 전 떼는 잘못된 확정 방지.)
> **펌프 루프 vs 라운드시작 핸들러 분리**: 라운드시작은 풍선 위치/크기/색 리셋만, 펌프 입력은 별도 forever 가 `게임상태=0` 일 때만 처리(상태 가드). cowboy-duel 의 "Stage 단일 흐름 + 스프라이트는 연출" 패턴과 동일 구조 — 단 여기선 풍선이 입력+판정을 겸한다(게임이 더 단순해서).

### 7.3 펌프 — 손잡이 들썩 연출

```
when flag clicked:
  goto (-120, -120)
  switch costume pump_up
  show

when flag clicked:   (별도 스크립트 — 손잡이 애니)
  forever:
    if 펌프중 = 1:
      switch costume pump_down
      wait 0.08
      switch costume pump_up
      wait 0.08
    else:
      switch costume pump_up
      wait 0.05
```

> 펌프는 순수 연출. `펌프중` 변수만 보고 손잡이를 위아래로 번갈아. 펌프 소리(쉭쉭)는 선택 — pop.wav 를 낮은 피치로 짧게 재생하거나 생략.

### 7.4 파편 — 터질 때 사방으로

```
when flag clicked:
  hide

when receive 터짐:
  # 본체가 파편 클론 8~12개를 풍선 위치에서 사방으로 생성
  goto (0, 20)
  play sound pop                 # 펑!
  repeat 10:
    create clone of myself
  # (본체는 계속 숨김)

when I start as clone:
  show
  goto (0, 20)
  point in direction (pick random 1 to 360)
  set size to (pick random 40 to 90)
  set [속도] to (pick random 4 to 9)        # lvVx 대용(인라인 가능)
  repeat 16:
    move (속도) steps                         # 방향대로 튀어나감
    change y by -1                            # 살짝 중력
    change [ghost] effect by 5                # 점점 투명
    wait 0.02
  delete this clone
```

> 파편은 연출. `point in direction (random 1..360)` 으로 사방, `move steps` 로 퍼지며 ghost 로 사라짐. 빌더 시간 부족 시 클론 6개로 축소 허용. 라운드끝 broadcast 는 풍선의 `확정`/`터짐` 핸들러 한 곳에서만 — 파편이 중복 발신하지 않게(7.2 에서 풍선이 라운드끝 발신).

### 7.5 결과배너 + 최종

```
when flag clicked:
  goto (0, 0)
  go to front
  hide

when receive 터짐:
  switch costume pop                # "펑! 0점"
  show
  wait 1.2
  hide

when receive 확정:
  switch costume safe               # "+이번점수!" (수치는 변수 모니터 이번점수)
  show
  play sound ding                   # 안전 확정음(pop.wav 높은 피치)
  wait 1.2
  hide

when receive 결과:
  switch costume result             # "합계 OOO!" (수치는 합계 모니터)
  show
  go to front
  if 합계 > 베스트 or (합계 = 베스트 and 합계 > 0):   # 신기록 표시(베스트 갱신 직전 비교는 Stage가 처리)
    # 신기록 연출은 별도 코스튬으로 잠깐
    switch costume newbest
    wait 1
  switch costume result
```

> 결과배너는 cowboy-duel 결과배너 패턴(코스튬 분기 + show/hide)을 그대로 가져와 코스튬을 4개(pop/safe/result/newbest)로. 수치(이번점수/합계/베스트)는 변수 모니터로 보여주므로 배너에 숫자를 그려 넣을 필요 없음.

---

## 8. 스프라이트별 블록 트리 (의사코드 요약)

> 7장이 이미 스프라이트별 의사코드 수준이므로 핵심 분기만 압축(빌더 1:1 매핑용). 상세 수치는 7장 참조.

### Stage
- `when flag` → init(라운드1, 총라운드5, 합계0, 베스트0, 게임상태0, 이번점수0) + broadcast 게임시작 + 라운드시작
- `when 라운드시작` → 라운드결과0; 이번점수0; 현재크기80; 한계치=rand(120..220); 떨림시작=round(한계치*rand(60..80)/100); 펌프중0; wait0.1; 게임상태0
- `when 라운드끝` → if 라운드결과1: 합계+=이번점수; wait1.4; if 라운드<총라운드{라운드+1; wait0.4; broadcast 라운드시작} else{게임상태2; if 합계>베스트 베스트=합계; broadcast 결과}

### 풍선 (메인)
- `when flag` → goto(0,20); size80; clear effects; hide
- `when 라운드시작` → goto(0,20); 현재크기80; size80; color effect=(라운드-1)*40; show
- `when flag`(펌프 forever) → if 게임상태0: `if space`{펌프중1; 현재크기+1; set size 현재크기; 이번점수=round((현재크기-80)*sqrt(현재크기-80)); if 현재크기≥떨림시작{set x rand(-2..2); color effect=(라운드-1)*40+(현재크기-떨림시작)*8} else{set x 0; color effect=(라운드-1)*40}; if 현재크기≥한계치{라운드결과2; 게임상태1; broadcast 터짐}} `else`{if 펌프중1 and 현재크기>80{set x0; 라운드결과1; 게임상태1; broadcast 확정}; 펌프중0}
- `when 확정` → set x0; (탄력 repeat2); broadcast 라운드끝
- `when 터짐` → hide; set x0; broadcast 라운드끝

### 펌프
- `when flag` → goto(-120,-120); costume pump_up; show
- `when flag`(애니 forever) → if 펌프중1{pump_down; wait0.08; pump_up; wait0.08} else{pump_up; wait0.05}

### 파편
- `when flag` hide
- `when 터짐` → goto(0,20); play pop; repeat10 create clone
- `when start as clone` → show; goto(0,20); point dir rand(1..360); size rand(40..90); 속도=rand(4..9); repeat16{move 속도; change y -1; ghost+5; wait0.02}; delete clone

### 결과배너
- `when flag` → goto(0,0); front; hide
- `when 터짐` → costume pop; show; wait1.2; hide
- `when 확정` → costume safe; show; play ding; wait1.2; hide
- `when 결과` → costume result; show; front (신기록 시 newbest 잠깐)

---

## 9. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| bg.svg | SVG (인라인) | 480×360. 밝은 축제/방 분위기 그라데이션(연파랑→연보라 등) + 하단 바닥선(y≈-150) + 왼쪽 아래에 펌프가 놓일 자리(테이블/바닥) + 풍선 꼭지로 이어질 호스 그림(선택, 펌프 코스튬에 포함해도 됨) |
| balloon.svg | SVG (인라인) | 둥근 풍선(아래 꼭지 + 매듭). 약 80×100(size 100 기준). 중간 채도 색(color effect 로 라운드별 변색되도록 회색끼 없는 선명한 단색). rotationCenter 중앙 또는 꼭지 |
| pump_up.svg | SVG (인라인) | 펌프 손잡이 올라간 상태. 약 90×80. 왼쪽 아래 배치 |
| pump_down.svg | SVG (인라인) | 펌프 손잡이 눌린 상태(손잡이 y 낮춤, 몸통 살짝 눌림). 같은 캔버스/rotationCenter |
| shard.svg | SVG (인라인) | 작은 풍선 조각(찢어진 고무 한 조각). 약 20×16. 색은 풍선과 비슷 |
| pop.svg | SVG (인라인) | 결과배너 코스튬: "펑! 0점" 빨강 |
| safe.svg | SVG (인라인) | 결과배너 코스튬: "+점수!" 초록(수치는 모니터) |
| result.svg | SVG (인라인) | 결과배너 코스튬: "끝! 합계 OOO" (수치는 모니터). 밝은 색 |
| newbest.svg | SVG (인라인) | 결과배너 코스튬: "신기록!" 금색 반짝 |
| pop.wav | WAV (assets/) | 터짐 "펑" 소리. 기존 `games/apple-catch/assets/pop.wav` 또는 `games/cowboy-duel/assets/pop.wav` 복사 |
| ding.wav / pump.wav | WAV (assets/) | 안전 확정음(띵)·펌프 쉭쉭음(선택). pop.wav 피치 변주로 1개만 있어도 동작 |

> WAV 는 `games/apple-catch/assets/pop.wav` 1개 복사 → 터짐=pop(피치 0), 확정=ding(피치 +300 짧게), 펌프=pump(피치 -300 짧게)로 변주(`sound_seteffectto` PITCH). 최소 pop.wav 1개로 충분.
> 풍선·펌프 코스튬은 같은 캔버스 크기/rotationCenter 로 그려 코스튬·크기 전환 시 위치 흔들림 없게.
> assets/ 폴더: 최소 `pop.wav`. 나머지 SVG 는 build.py 인라인.

---

## 10. 변수/리스트/메시지 요약 (ID 컨벤션)

- 글로벌 변수 11개: `varState01`(게임상태) `varRound02`(라운드) `varMaxRound03`(총라운드) `varCurScore04`(이번점수) `varTotal05`(합계) `varBest06`(베스트) `varSize07`(현재크기) `varLimit08`(한계치) `varShakeStart09`(떨림시작) `varRResult10`(라운드결과) `varPumping11`(펌프중)
- **비공개 변수(monitor visible=false)**: `varLimit08`(한계치) `varShakeStart09`(떨림시작) — 화면에 절대 표시 금지(누설 방지)
- 풍선 sprite-local: 없음(상태는 모두 글로벌 — 펌프/파편/배너가 공유 참조)
- 파편 sprite-local: 없음(클론 속도 인라인; 필요 시 `lvVx01`/`lvVy02` 허용)
- 리스트: 없음
- broadcasts 6개: `brStart01`(게임시작) `brRoundStart02`(라운드시작) `brPop03`(터짐) `brConfirm04`(확정) `brRoundEnd05`(라운드끝) `brResult06`(결과)
- 모니터(상단 표시): 라운드(라운드/총라운드) / 이번점수 / 합계 / 베스트 — 한계치·떨림시작은 **숨김**

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **라운드 진행(라운드+1, 다음 라운드 broadcast, 합계/베스트 판정) + "스페이스 1키" 긴장형 단일 흐름**: `games/cowboy-duel/build.py`(5판 라운드 진행 + 합계/베스트 + 결과 배너 + 단일 상태머신, 물리/클론 없음). 본 게임은 cowboy-duel 과 거의 같은 골격 — "랜덤 대기 후 신호" 대신 "스페이스 길게 누름 → 크기 증가 → 한계 도달 시 펑". 라운드끝/최종판정 핸들러를 거의 그대로 가져온다.
- **결과 배너(코스튬 분기 + show/hide + 사운드)**: `games/cowboy-duel/build.py`(win/lose/foul + victory/defeat 코스튬 분기) · `games/apple-catch/build.py`(결과 배너). 코스튬을 4개(pop/safe/result/newbest)로 가져와 방송별 분기.
- **클론 사방 분출 + 이동 + ghost 페이드 + delete**: `games/asteroids/build.py`(폭발 파편) · `games/missile-command/build.py`(폭발 연출) · `games/duck-hunt`(맞은 연출). 풍선 파편에 그대로.
- **키 입력 길게 누름 감지(`sensing_keypressed` + forever)**: 거의 모든 게임(`games/flappy-bird`, `games/geometry-dash` 스페이스). 여기선 "누르는 동안 계속 +1" 이라 `wait until 키뗌` 없이 매 틱 증가.
- **pop 사운드 + 피치 변주(`sound_seteffectto` PITCH)**: `games/apple-catch`·`games/cowboy-duel` 의 pop.wav 재사용. 1개 파일을 터짐/확정/펌프로 변주.
- **`set size to`(크기 펌프) + `set color effect to`(위험 색경고/라운드색)**: 일반 looks 블록. 크기 펌프는 `set size to 현재크기`(매 틱 +1), 색은 라운드색 오프셋 + 위험 가산 합산.

빌더 권장 진행: (1) cowboy-duel build.py 를 베이스로 — 라운드 진행/합계/베스트/결과배너 골격 복사, (2) 좌/우 카우보이 → 가운데 풍선 1개(입력+판정 겸함) + 왼쪽 펌프(연출), (3) "랜덤 대기 + 신호 + timer 판정" 스크립트 → "펌프 forever(스페이스 누름→크기+1→점수 가속→떨림/색 경고→한계 도달 시 터짐, 떼면 확정)"으로 교체, (4) 파편 클론 sprite 신규(asteroids 폭발 패턴), (5) 결과배너 코스튬 5→4개로 조정, (6) 배경을 석양 → 축제/방 톤으로 교체. **한계치·떨림시작 변수는 monitor 숨김 필수.**

**필요한 블록 opcode (확인용)**:
- `operator_mathop`(sqrt — 점수 ^1.5 계산), `operator_random`(한계치/떨림시작/떨림x/파편), `operator_round`(점수/떨림시작 정수화), `operator_mult`/`subtract`/`divide`/`add`, `operator_gt`/`ge`(이상 비교는 `not (a < b)` 또는 `(a > b) or (a = b)`), `operator_and`
- `sensing_keypressed`("space")
- `looks_setsizeto`(크기 펌프), `looks_seteffectto`(COLOR — 라운드색/위험경고; GHOST — 파편 페이드), `looks_cleargraphiceffects`, `looks_switchcostumeto`, `looks_show`/`hide`, `looks_gotofront`
- `motion_gotoxy`, `motion_setx`(떨림 ±2), `motion_changeyby`(파편 중력), `motion_pointindirection`(파편 사방), `motion_movesteps`(파편)
- `control_forever`, `control_if`/`if_else`, `control_repeat`, `control_create_clone_of`, `control_start_as_clone`, `control_delete_this_clone`, `control_wait`
- `event_broadcast`, `data_setvariableto`/`changevariableby`
- `sound_playuntildone`/`sound_play`, `sound_seteffectto`(PITCH 변주)

> **`≥` 구현 주의**: Scratch 에는 `≥`(이상) 블록이 없다. `현재크기 ≥ 한계치` 는 `not (현재크기 < 한계치)` 또는 `(현재크기 > 한계치) or (현재크기 = 한계치)` 로. 크기가 정수 +1 씩 늘어 한계치(정수)와 정확히 일치하므로 `현재크기 = 한계치` 검사 또는 `현재크기 > 한계치-1` 로도 가능. 빌더는 `not (현재크기 < 한계치)` 권장.

---

## 12. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과 / `project.json` JSON 로드 OK
2. targets 수: 5 (Stage, 풍선, 펌프, 파편, 결과배너)
3. Stage 글로벌 변수 11개 등록 / 리스트 0개 / 풍선 sprite-local 0개(또는 파편 lvVx/lvVy 허용)
4. Broadcasts 등록: 게임시작/라운드시작/터짐/확정/라운드끝/결과 — 6개
5. **비공개 변수 숨김**: `varLimit08`(한계치) `varShakeStart09`(떨림시작) monitor visible=false (화면 비표시). 누설 시 실패
6. Stage 라운드시작: `한계치 = rand(120..220)` + `떨림시작 = round(한계치 * rand(60..80)/100)` + 현재크기=80 리셋 존재
7. **풍선 펌프 forever**: `if 게임상태=0` 안에 `if space`{현재크기+1; set size 현재크기; 이번점수=round((현재크기-80)*sqrt(현재크기-80)) — `operator_mathop` sqrt 사용; 떨림/색 경고; 한계 도달 시 터짐} / `else`{현재크기>80 이고 펌프중이면 확정} 분기 존재
8. 점수 가속이 `sqrt`(또는 동등한 ^1.5 비선형) 사용 — 단순 선형(현재크기에 비례)만이면 미흡(욕심 트레이드오프 핵심)
9. 떨림/색 경고가 `현재크기 ≥ 떨림시작`(=한계치 직접 비교가 아닌 비율 기반) 조건에서 시작 — `현재크기 ≥ 한계치`(터짐 직전)에서만 시작하면 미흡(긴장 연출 안 됨)
10. 터짐: 현재크기 한계치 도달 → broadcast 터짐 → 파편 클론(8~12개, 시간부족 시 6 허용) 사방 분출 + pop 사운드 + 풍선 hide + 이번점수 미합산(0점)
11. 확정: 펌프 중 스페이스 뗌(현재크기>80) → broadcast 확정 → 안전 배너 + 이번점수 합계 합산
12. Stage 라운드끝: 라운드결과1→합계+=이번점수 / 라운드결과2→합계 불변; 라운드<5면 라운드+1+라운드시작, 5면 게임상태2+베스트 갱신+결과 배너 분기 존재
13. 펌프 sprite: `펌프중=1` 일 때 손잡이 2코스튬 들썩, 0이면 정지 코스튬
14. 결과배너 코스튬 4개(pop/safe/result/newbest) + 각 방송 분기 존재
15. monitors: 라운드/이번점수/합계/베스트 표시(한계치·떨림시작은 숨김)
16. 자산: SVG(bg/balloon/pump_up/pump_down/shard/pop/safe/result/newbest) + WAV(최소 pop) MD5 일치
17. 블록 카운트 120~180 범위
18. (동작 검증) 스페이스 꾹 → 풍선이 점점 커지고 점수가 가파르게 오름 → 어느 시점부터 떨리고 색이 빨개짐(경고) → 떼면 점수 확정(+합계) / 계속 누르면 한계에서 펑! 0점(파편 분출) → 다음 라운드 한계치·떨림 시작점이 매번 달라짐(패턴 학습 불가) → 5라운드 후 합계/베스트 배너

---

## 13. 빌드 카운트 예상

- Stage: ~30 블록 (init + 라운드시작 한계치/떨림 생성 + 라운드끝 점수/최종판정)
- 풍선: ~55 블록 (flag 리셋 + 라운드시작 리셋 + 펌프 forever(입력/크기/점수가속/떨림·색/터짐·확정 분기) + 확정/터짐 핸들러)
- 펌프: ~14 블록 (손잡이 들썩 forever)
- 파편: ~22 블록 (터짐 클론 생성 + 클론 사방 이동/페이드)
- 결과배너: ~24 블록 (pop/safe/result/newbest 방송 분기 + 사운드)
- **총합 예상: 130~170 블록** (★★ — 물리/리스트 없이 크기 펌프 + 비선형 점수 + 떨림·색 경고 + 한계치 은닉이 핵심. 클론은 파편 연출만. 난이도 중하)

---

## 14. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (스페이스 1키만 — "꾹 누르면 풍선 커짐, 떼면 점수, 터지면 0점" 즉시 이해)
- [x] 추상 학습 콘셉트 없음 (반응·도박 심리 게임. 수학·과학 개념 매핑 전혀 없음. 점수 ^1.5 가속은 내부 계산일 뿐 "크게 불수록 점수 빨리 오름"으로만 체감)
- [x] 즉시 이해되는 룰 (불수록 점수↑, 너무 불면 펑! 직전에 멈춰라)
- [x] 긴장감/연출 (보이지 않는 한계치, 떨림 시작 = "이제 위험할지도", 색이 빨개지는 경고, 펑! 파편 + 소리. "조금만 더…"의 조마조마함이 핵심)
- [x] 욕심 vs 안전 트레이드오프 (작게 멈추면 안전하지만 점수 적고, 크게 불면 점수 가속하지만 터질 위험 — 매 라운드 도박 결정)
- [x] 운 + 감 (한계치 랜덤·비공개 = 운, 떨림/색 경고 읽기 = 감. 패턴 학습 불가하게 라운드마다 떨림 시작 비율도 랜덤)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭). 5라운드 = 1세트로 빠른 회전
- [x] 비폭력·친근(풍선 + 펌프 + 축제 톤 — 누구나 아는 평화로운 상황. 터짐도 만화적 "펑")
