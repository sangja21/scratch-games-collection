# 사과 받기 (apple-catch) — Plan

> 바구니를 화면 하단에서 좌/우 화살표로 움직여, 화면 위에서 떨어지는 사과를 받는다. 받으면 점수, 놓치면 라이프 -1. 가끔 폭탄이 섞여 떨어지는데 받으면 라이프 -1. 시간이 갈수록 사과 생성 주기가 짧아져 난이도 ramp.
> 베이스: `games/meteor-dodge/build.py` (클론 무한 스폰 + 위→아래 낙하 + 난이도 ramp 패턴). **차이점**: 우주선 → 바구니(좌우 이동만), 충돌 = 점수(or 라이프 -1), 폭탄 분기 추가, 라이프 3개 시스템, 게임오버는 라이프=0 일 때만.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지.

---

## 1. 한 줄 룰

좌/우 화살표로 바구니를 움직여 떨어지는 사과를 받는다. 사과 받으면 점수 +1, 놓치면 라이프 -1. 폭탄을 받아도 라이프 -1. 라이프 0 → 게임오버.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 연한 하늘색 + 풀밭(아래쪽 1/4), 흰 구름 두어 개.
- 모니터 좌상단: 점수 / 최고기록 / 라이프.

---

## 3. 스프라이트 (4개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 + 과일 스폰 타이머 호스트 + 난이도 ramp | 게임시작 broadcast 발신 |
| 1 | 바구니 | 좌/우 화살표로 좌우 이동, 가장자리 clamp | y 고정 (-130), rotationStyle: don't rotate |
| 2 | 사과 | 클론 무한 스폰. 화면 위 무작위 x에서 등장 → 아래로 낙하. 2 코스튬 (apple / bomb) | rotationStyle: don't rotate |
| 3 | 게임오버 | "GAME OVER" 배너, 평소 숨김. 라이프=0 일 때만 보임. | meteor-dodge 패턴 그대로 |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 받은 사과 수 |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 |
| 라이프 | `varLife03` | 3 | 남은 라이프 (0 → 게임오버) |
| 게임상태 | `varState04` | 1 | 1=플레이, 0=게임오버 |
| 사과X | `varAX05` | 0 | 스폰 x 좌표 |
| 사과타입 | `varAType06` | 1 | 1=사과(apple), 2=폭탄(bomb) |
| 사과속도 | `varASpeed07` | 4 | 낙하 속도 (스폰마다 무작위) |
| 스폰주기 | `varSpawn08` | 0.9 | 스폰 인터벌(초). 시간 지날수록 감소 |
| 경과틱 | `varTick09` | 0 | 초 단위 경과 (난이도 ramp 표시용) |

사과 sprite-local 변수:

| 변수명 | ID | 용도 |
|--------|----|------|
| 내속도 | `varMyV10` | 클론 시작 시 stage 변수 `사과속도` 로컬 복사. 매 틱 y -= 내속도 |
| 내타입 | `varMyT11` | 클론 시작 시 stage 변수 `사과타입` 로컬 복사 (1=apple, 2=bomb). 충돌 처리 분기에 사용 |

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 과일스폰 | `brSpawn02` | Stage 가 매 `스폰주기` 초마다 발신 → 사과 클론 1개 생성 |

---

## 6. 메커닉 상세

### 6.1 바구니 (좌표/조작)

매 틱(약 0.025s):

1. 좌/우 화살표 입력 → x ± 8 (속도 8px/틱).
2. y 는 -130 고정 (점프/낙하 없음).
3. **가장자리 clamp**:
   - x < -210 → x = -210
   - x > 210 → x = 210
4. 충돌 판정은 사과(클론) 쪽에서 한다 (바구니에 닿았는지 검사).
5. wait 0.025.

### 6.2 과일 스폰 (Stage)

`when receive 게임시작` 의 스폰 forever:

```
repeat until 게임상태 = 0:
  사과X = random(-210..210)
  k = random(1..10)
  if k <= 8:   # 80% — 사과
    사과타입 = 1
  else:        # 20% — 폭탄
    사과타입 = 2
  사과속도 = random(3..6)   # 무작위 낙하 속도
  broadcast 과일스폰
  wait 스폰주기
```

별도 forever (1초 타이머):

```
repeat until 게임상태 = 0:
  wait 1
  경과틱 = 경과틱 + 1
```

별도 forever (5초마다 난이도 ramp):

```
repeat until 게임상태 = 0:
  wait 5
  if 스폰주기 > 0.30:
    스폰주기 = 스폰주기 * 0.88
```

3개의 `when receive 게임시작` 핸들러로 병렬 forever 구현 (meteor-dodge 와 동일 패턴).

### 6.3 사과 (클론)

`when receive 과일스폰`:
- goto (사과X, 200) — 화면 상단 살짝 위
- 코스튬: 사과타입에 따라 분기 — 1 → "apple"(size 70), 2 → "bomb"(size 70)
- 내속도 = 사과속도
- 내타입 = 사과타입
- create clone of myself

`when I start as clone`:

```
show
repeat until 게임상태 = 0:
  change y by (-1 * 내속도)
  if touching 바구니:
    if 내타입 = 1:
      점수 = 점수 + 1
    else:
      라이프 = 라이프 - 1
      if 라이프 < 1:
        게임상태 = 0
        if 점수 > 최고기록: 최고기록 = 점수
    delete this clone
  if y position < -180:
    if 내타입 = 1:
      # 사과를 놓쳤다 → 라이프 -1
      라이프 = 라이프 - 1
      if 라이프 < 1:
        게임상태 = 0
        if 점수 > 최고기록: 최고기록 = 점수
    # 폭탄은 그냥 사라짐 (안 받아도 페널티 없음)
    delete this clone
  wait 0.025
delete this clone
```

> 충돌·바닥 도달 양쪽에서 `delete this clone` 즉시 호출. 게임오버 시 outer repeat 종료 → 최종 delete.

### 6.4 게임오버

라이프가 0이 되는 시점에서 게임상태=0 + 최고기록 갱신.
게임오버 배너 sprite 가 `wait_until 게임상태=1 → wait_until 게임상태=0 → show`.

### 6.5 재시작

깃발 다시 클릭 → 모든 변수 리셋(라이프=3 포함) → 새 게임.

---

## 7. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  라이프 ← 3
  게임상태 ← 1
  스폰주기 ← 0.9
  경과틱 ← 0
  broadcast 게임시작

when receive 게임시작:   # forever 1: 스폰 루프
  repeat until 게임상태 = 0:
    사과X ← random(-210..210)
    k = random(1..10)
    if k < 9: 사과타입 = 1
    if k > 8: 사과타입 = 2
    사과속도 ← random(3..6)
    broadcast 과일스폰
    wait 스폰주기

when receive 게임시작:   # forever 2: 1초 타이머
  repeat until 게임상태 = 0:
    wait 1
    경과틱 ← 경과틱 + 1

when receive 게임시작:   # forever 3: 5초마다 난이도 ramp
  repeat until 게임상태 = 0:
    wait 5
    if 스폰주기 > 0.30:
      스폰주기 ← 스폰주기 * 0.88
```

### 바구니

```
when flag clicked:
  goto 0, -130
  size 80
  point in direction 90
  show

when receive 게임시작:
  goto 0, -130
  repeat until 게임상태 = 0:
    if key ←: change x by -8
    if key →: change x by 8
    # clamp
    if x < -210: set x to -210
    if x > 210: set x to 210
    wait 0.025
```

### 사과 (스폰 + 클론)

```
when flag clicked:
  hide
  size 70

when receive 과일스폰:
  goto (사과X, 200)
  if 사과타입 = 1: switch costume "apple"
  if 사과타입 = 2: switch costume "bomb"
  set 내속도 ← 사과속도
  set 내타입 ← 사과타입
  create clone of _myself_

when I start as clone:
  show
  repeat until 게임상태 = 0:
    change y by (-1 * 내속도)
    if touching 바구니:
      if 내타입 = 1:
        점수 ← 점수 + 1
      if 내타입 = 2:
        라이프 ← 라이프 - 1
        if 라이프 < 1:
          게임상태 ← 0
          if 점수 > 최고기록: 최고기록 ← 점수
      delete this clone
    if y position < -180:
      if 내타입 = 1:
        라이프 ← 라이프 - 1
        if 라이프 < 1:
          게임상태 ← 0
          if 점수 > 최고기록: 최고기록 ← 점수
      delete this clone
    wait 0.025
  delete this clone
```

### 게임오버 배너

```
when flag clicked:
  hide
  goto 0, 0
  size 100
  go to front
  wait until 게임상태 = 1
  wait until 게임상태 = 0
  show
```

---

## 8. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| 배경 | SVG (인라인) | 하늘색 + 풀밭 + 흰 구름 2개 |
| 바구니 | SVG (인라인) | 갈색 등나무 바구니 (사다리꼴 + 손잡이). 90×60 viewBox |
| apple | SVG (인라인) | 빨간 사과 + 녹색 잎 + 갈색 줄기 |
| bomb | SVG (인라인) | 검은 구체 + 갈색 도화선 + 노랑 불꽃 |
| 게임오버 배너 | SVG (인라인) | 검은 배너 "GAME OVER" + "라이프가 모두 떨어졌어요" |
| pop.wav | WAV (assets/) | meteor-dodge 의 것 복사. 시작 효과음 |

assets/ 폴더에 둘 외부 파일: `pop.wav` 하나면 충분. 나머지 SVG 는 build.py 인라인.

---

## 9. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과
2. `project.json` JSON 로드 OK
3. targets 수: 4 (Stage, 바구니, 사과, 게임오버)
4. Stage 변수 9개(점수/최고기록/라이프/게임상태/사과X/사과타입/사과속도/스폰주기/경과틱) 모두 등록
5. 사과 sprite-local 변수 2개(내속도/내타입) 등록
6. Broadcasts: 게임시작 / 과일스폰 2개
7. 사과 스프라이트 코스튬 2개 (apple, bomb)
8. 자산 5 SVG (배경/바구니/apple/bomb/게임오버) + 1 WAV (pop)
9. 바구니 sprite 의 control_repeat_until 안에 좌/우 화살표 sensing_keypressed × 2 가 모두 존재
10. 사과 sprite 의 클론 트리 안에 `sensing_touchingobject`("바구니") 가 존재
11. Stage 에 `when receive 게임시작` 핸들러가 3개 이상
12. 사과 sprite 의 `control_start_as_clone` 트리에 `motion_changeyby` (내속도 사용) 와 `control_delete_this_clone` 모두 존재
13. monitors 에 점수·최고기록·라이프 모니터 표시
14. 모든 자산 MD5 일치 (zip 안 파일명 ↔ assetId)
15. 블록 카운트 150~280 범위

---

## 10. 빌드 카운트 예상

- Stage: ~55 블록 (init + 3개 forever 핸들러)
- 바구니: ~30 블록 (좌/우 키 입력 + clamp ×2)
- 사과: ~75 블록 (스폰 분기 2 + 클론 forever + 충돌·바닥 분기 2 × 라이프 분기)
- 게임오버: ~12 블록 (meteor-dodge 와 동일)
- **총합 예상: 170~220 블록**

---

## 11. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (좌우 이동 + 받기)
- [x] 추상 학습 콘셉트 없음 (사과 = 사과, 폭탄 = 폭탄. 수학·과학 개념 매핑 없음)
- [x] 즉시 이해되는 룰 (받으면 점수, 폭탄·놓침 = 라이프 -1)
- [x] 시각적 보상(사과)과 위협(폭탄) 분리
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
