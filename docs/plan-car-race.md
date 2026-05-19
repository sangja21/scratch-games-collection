# 자동차 레이싱 (car-race) — Plan

> 화면 하단의 내 차를 좌/우 화살표로 한 차선씩 스냅 이동, 위에서 내려오는 적 차를 회피한다. 도로 페인트 라인이 위→아래로 흘러 속도감을 표현한다. 시간이 지날수록 적 차 스폰 주기가 짧아지고 낙하 속도가 빨라진다.
> 베이스: `games/meteor-dodge/build.py` (위→아래 클론 무한 스폰 + 시간 ramp + touching 충돌 게임오버 패턴) + `games/apple-catch/build.py` (좌우 이동만 하는 플레이어 + 가장자리 clamp). **차이점**: 자유 이동 대신 4차선 스냅 이동(키 누름 한 번에 한 차선 이동, key released 후 재누름까지 무시), 도로 스크롤용 페인트 라인 별도 클론 풀, 점수는 거리(시간) 기반.
> 1976 아타리 Night Driver / Road Fighter / 캐주얼 차선 변경 회피 게임에서 영감.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지.

---

## 1. 한 줄 룰

좌/우 화살표로 내 차를 한 차선씩 옮겨 위에서 내려오는 적 차를 피한다. 한 번 부딪히면 게임오버. 생존 시간이 점수.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 양옆 풀밭(녹색), 가운데 회색 4차선 도로 (도로 폭 ≈ 240px, x = -120..+120). 도로 가장자리에 흰 라인 2줄, 차선 사이에 흰 점선 3줄.
- **4차선**: 차선 중심 x 좌표 = -90, -30, +30, +90 (각 차선 폭 60px).
- 모니터 좌상단: 점수 / 최고기록.

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 + 적 차 스폰 타이머 + 점수 +1 매 초 + 난이도 ramp + 페인트 라인 스폰 | 게임시작 broadcast 발신 |
| 1 | 내차 | 좌/우 화살표로 한 차선씩 스냅 이동 (4차선). y = -130 고정. 적 차 접촉 시 게임오버. | rotationStyle: don't rotate |
| 2 | 적차 | 클론 무한 스폰. 위(y=210)에서 무작위 차선(-90/-30/+30/+90)에서 등장 → 아래로. 3 코스튬(빨강/파랑/노랑). | rotationStyle: don't rotate |
| 3 | 페인트라인 | 흰 점선 클론. 도로 가운데(차선 사이) 3 위치에서 위→아래 스크롤. 무한 스폰. | 시각 효과용. 충돌 판정 없음. |
| 4 | 게임오버 | "GAME OVER" 배너, 평소 숨김. 게임상태=0 일 때만 보임. | meteor-dodge 패턴 그대로 |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 생존 시간 (매 초 +1) |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 (게임오버 시 갱신) |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| 차선 | `varLane04` | 2 | 내 차 현재 차선 (1~4). 시작 시 2번 차선 (x=-30). |
| 적X | `varEX05` | 0 | 적 차 스폰 x 좌표 (차선 중심) |
| 적색상 | `varEColor06` | 1 | 1=빨강, 2=파랑, 3=노랑 (스폰 시 set) |
| 적속도 | `varESpeed07` | 4 | 적 차 낙하 속도 (시간 지날수록 증가) |
| 스폰주기 | `varSpawn08` | 0.9 | 적 차 스폰 인터벌(초). 시간 지날수록 감소 |
| 라인속도 | `varLSpeed09` | 6 | 페인트 라인 스크롤 속도 (적속도와 함께 ramp) |
| 경과틱 | `varTick10` | 0 | 초 단위 경과 타이머 |
| 라인X | `varLX11` | 0 | 페인트 라인 스폰 x 좌표 (-60/0/+60 중 하나) |

내차 sprite-local 변수: 없음 (차선 변수는 stage 글로벌이지만, 내 차 본인만 읽고 쓴다).

적차 sprite-local 변수:

| 변수명 | ID | 용도 |
|--------|----|------|
| 내속도 | `varMyV12` | 클론 시작 시 stage `적속도` 로컬 복사. 매 틱 y -= 내속도 |

페인트라인 sprite-local 변수:

| 변수명 | ID | 용도 |
|--------|----|------|
| 라인내속도 | `varMyL13` | 클론 시작 시 stage `라인속도` 로컬 복사. 매 틱 y -= 라인내속도 |

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 적스폰 | `brSpawn02` | Stage 가 매 `스폰주기` 초마다 발신 → 적차 클론 1개 생성 |
| 라인스폰 | `brLine03` | Stage 가 매 0.18초마다 발신 → 페인트라인 클론 1개 생성 |

---

## 6. 메커닉 상세

### 6.1 내 차 (스냅 차선 이동)

차선 4개의 중심 x: 1=-90, 2=-30, 3=+30, 4=+90.

매 틱(약 0.025s):

1. **좌 화살표 눌렸을 때** & `차선 > 1`: `차선 ← 차선 - 1`, 그 후 `wait until 좌 화살표 안 눌림` (재누름 방지 — 한 번 눌러서 한 차선 이동만).
2. **우 화살표 눌렸을 때** & `차선 < 4`: `차선 ← 차선 + 1`, 그 후 `wait until 우 화살표 안 눌림`.
3. 매 틱 차선 변수에 따라 목표 x 계산 후 glide 가 아니라 직접 `set x to ((차선 * 60) - 150)`:
   - 차선 1 → -90 / 차선 2 → -30 / 차선 3 → +30 / 차선 4 → +90
4. y 는 -130 고정.
5. **충돌 체크**: `touching 적차` 이면 → 게임상태 = 0, 최고기록 갱신.
6. wait 0.025.

> 키 누름 후 wait_until 키 안 눌림 패턴: Scratch 에서 한 키프레스 = 한 차선 이동 보장하는 표준 방식. 길게 누르면 한 번만 이동하고, 손을 떼고 다시 눌러야 다음 차선으로 이동.

> 키 입력 처리와 set_x/충돌 체크를 같은 forever 안에 둔다. 즉 forever 한 반복 내부:
> - if key left and 차선>1: 차선-=1, wait_until not key left
> - if key right and 차선<4: 차선+=1, wait_until not key right
> - set x to (차선*60 - 150)
> - if touching 적차: 게임오버
> - wait 0.025

### 6.2 적 차 스폰 (Stage)

`when receive 게임시작` 의 forever 루프 1 (적 스폰):

```
repeat until 게임상태 = 0:
  k = random(1..4)            # 차선 무작위
  적X = (k * 60) - 150        # -90/-30/+30/+90
  c = random(1..3)
  적색상 = c
  # 적속도는 stage 전역. ramp 루프가 시간 따라 올림.
  broadcast 적스폰
  wait 스폰주기
```

forever 2 (페인트 라인 스폰, 도로 스크롤 표현):

```
repeat until 게임상태 = 0:
  m = random(1..3)
  라인X = (m * 60) - 120      # -60/0/+60 (차선 경계선 위치)
  broadcast 라인스폰
  wait 0.18
```

forever 3 (1초 타이머 + 점수):

```
repeat until 게임상태 = 0:
  wait 1
  경과틱 = 경과틱 + 1
  점수 = 점수 + 1
```

forever 4 (5초마다 난이도 ramp):

```
repeat until 게임상태 = 0:
  wait 5
  if 스폰주기 > 0.30:
    스폰주기 = 스폰주기 * 0.88
  if 적속도 < 9:
    적속도 = 적속도 + 0.6
  if 라인속도 < 12:
    라인속도 = 라인속도 + 0.8
```

4개의 `when receive 게임시작` 핸들러로 병렬 forever 구현 (meteor-dodge 와 동일 패턴).

### 6.3 적 차 (클론)

`when receive 적스폰`:
- goto (적X, 210)
- 코스튬: 적색상에 따라 분기 — 1→"car_red", 2→"car_blue", 3→"car_yellow"
- 내속도 = 적속도
- create clone of myself

`when I start as clone`:
```
show
repeat until 게임상태 = 0:
  change y by (-1 * 내속도)
  if y position < -190:
    delete this clone
  wait 0.025
delete this clone
```

> 적 차 충돌 판정은 내 차 쪽에서 `touching 적차` 로 한다. 적 차 본인은 안 함.

### 6.4 페인트 라인 (클론, 시각 효과만)

`when receive 라인스폰`:
- goto (라인X, 210)
- 라인내속도 = 라인속도
- create clone of myself

`when I start as clone`:
```
show
repeat until 게임상태 = 0:
  change y by (-1 * 라인내속도)
  if y position < -190:
    delete this clone
  wait 0.025
delete this clone
```

### 6.5 게임오버

내 차 sprite 가 매 틱 충돌 체크 → 게임상태=0 + 최고기록 갱신.
게임오버 배너 sprite 가 `wait_until 게임상태=1 → wait_until 게임상태=0 → show`.

### 6.6 재시작

깃발 다시 클릭 → 모든 변수 리셋(차선=2, 적속도=4, 라인속도=6 포함) → 새 게임.

---

## 7. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  게임상태 ← 1
  차선 ← 2
  적속도 ← 4
  라인속도 ← 6
  스폰주기 ← 0.9
  경과틱 ← 0
  broadcast 게임시작

when receive 게임시작:   # forever 1: 적 스폰
  repeat until 게임상태 = 0:
    k = random(1..4)
    적X ← (k * 60) - 150
    c = random(1..3)
    적색상 ← c
    broadcast 적스폰
    wait 스폰주기

when receive 게임시작:   # forever 2: 라인 스폰
  repeat until 게임상태 = 0:
    m = random(1..3)
    라인X ← (m * 60) - 120
    broadcast 라인스폰
    wait 0.18

when receive 게임시작:   # forever 3: 1초 타이머 + 점수
  repeat until 게임상태 = 0:
    wait 1
    경과틱 ← 경과틱 + 1
    점수 ← 점수 + 1

when receive 게임시작:   # forever 4: 5초마다 난이도 ramp
  repeat until 게임상태 = 0:
    wait 5
    if 스폰주기 > 0.30:
      스폰주기 ← 스폰주기 * 0.88
    if 적속도 < 9:
      적속도 ← 적속도 + 0.6
    if 라인속도 < 12:
      라인속도 ← 라인속도 + 0.8
```

### 내차

```
when flag clicked:
  goto (-30, -130)
  size 70
  point in direction 0
  show

when receive 게임시작:
  차선 ← 2
  set x to -30
  set y to -130
  repeat until 게임상태 = 0:
    if key ← AND 차선 > 1:
      차선 ← 차선 - 1
      wait until NOT key ←
    if key → AND 차선 < 4:
      차선 ← 차선 + 1
      wait until NOT key →
    set x to ((차선 * 60) - 150)
    if touching 적차:
      게임상태 ← 0
      if 점수 > 최고기록: 최고기록 ← 점수
    wait 0.025
```

### 적차

```
when flag clicked:
  hide
  size 70

when receive 적스폰:
  goto (적X, 210)
  if 적색상 = 1: switch costume "car_red"
  if 적색상 = 2: switch costume "car_blue"
  if 적색상 = 3: switch costume "car_yellow"
  set 내속도 ← 적속도
  create clone of _myself_

when I start as clone:
  show
  repeat until 게임상태 = 0:
    change y by (-1 * 내속도)
    if y position < -200:
      delete this clone
    wait 0.025
  delete this clone
```

### 페인트라인

```
when flag clicked:
  hide
  size 100

when receive 라인스폰:
  goto (라인X, 210)
  set 라인내속도 ← 라인속도
  create clone of _myself_

when I start as clone:
  show
  go to back
  repeat until 게임상태 = 0:
    change y by (-1 * 라인내속도)
    if y position < -200:
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
| 배경 | SVG (인라인) | 양옆 녹색 풀밭 + 가운데 회색 도로(폭 240px) + 도로 가장자리 흰 라인 2줄 (정적) |
| 내차 | SVG (인라인) | 위에서 본 자동차. 흰/하늘색 본체 + 검은 창문 + 4 바퀴. 40×64 viewBox (세로형) |
| car_red | SVG (인라인) | 위에서 본 빨간 차 |
| car_blue | SVG (인라인) | 위에서 본 파란 차 |
| car_yellow | SVG (인라인) | 위에서 본 노란 차 |
| 페인트라인 | SVG (인라인) | 흰 직사각형 점선 한 토막 (8×30 정도) |
| 게임오버 배너 | SVG (인라인) | 검은 배너 "GAME OVER" + "충돌!" |
| pop.wav | WAV (assets/) | meteor-dodge 의 것 복사. 시작·게임오버 효과음 |

assets/ 폴더: `pop.wav` 하나만. 나머지 SVG 는 build.py 인라인.

---

## 9. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과
2. `project.json` JSON 로드 OK
3. targets 수: 5 (Stage, 내차, 적차, 페인트라인, 게임오버)
4. Stage 변수 11개(점수/최고기록/게임상태/차선/적X/적색상/적속도/스폰주기/라인속도/경과틱/라인X) 모두 등록
5. 적차 sprite-local 변수 1개(내속도) 등록
6. 페인트라인 sprite-local 변수 1개(라인내속도) 등록
7. Broadcasts: 게임시작 / 적스폰 / 라인스폰 3개
8. 적차 스프라이트 코스튬 3개 (car_red, car_blue, car_yellow)
9. 자산 7 SVG (배경/내차/car_red/car_blue/car_yellow/페인트라인/게임오버) + 1 WAV (pop)
10. 내차 sprite 의 control_repeat_until 안에 좌/우 화살표 sensing_keypressed × 2 와 `차선` 변수 ±1 가 모두 존재
11. 내차 sprite 의 같은 forever 에 `sensing_touchingobject`("적차") + `data_setvariableto`(게임상태=0) 블록 존재
12. 내차 sprite 안에 한 차선씩만 이동되도록 `wait until NOT key`(operator_not + sensing_keypressed) 패턴이 좌/우 각각 존재
13. Stage 에 `when receive 게임시작` 핸들러가 4개 이상 (적 스폰 + 라인 스폰 + 1초 타이머 + 5초 ramp)
14. 적차 sprite 의 `control_start_as_clone` 트리에 `motion_changeyby` (내속도 사용) 와 `control_delete_this_clone` 모두 존재
15. 페인트라인 sprite 의 `control_start_as_clone` 트리에 `motion_changeyby` (라인내속도 사용) 와 `control_delete_this_clone` 모두 존재
16. monitors 에 점수·최고기록 모니터 표시
17. 모든 자산 MD5 일치 (zip 안 파일명 ↔ assetId)
18. 블록 카운트 200~340 범위

---

## 10. 빌드 카운트 예상

- Stage: ~70 블록 (init + 4개 forever 핸들러)
- 내차: ~50 블록 (좌/우 키 입력 + wait_until not key ×2 + 차선→x 계산 + 충돌 + 최고기록 갱신)
- 적차: ~50 블록 (스폰 분기 3 + 클론 forever + 삭제)
- 페인트라인: ~25 블록 (스폰 + 클론 forever + go to back + 삭제)
- 게임오버: ~12 블록 (meteor-dodge 와 동일)
- **총합 예상: 210~270 블록**

---

## 11. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (좌/우 두 버튼으로 차선 변경)
- [x] 추상 학습 콘셉트 없음 (자동차 = 자동차. 수학·과학 개념 매핑 없음)
- [x] 즉시 이해되는 룰 (피하면 점수, 부딪히면 끝)
- [x] 시각적 속도감 (페인트 라인 스크롤)
- [x] 시간 따른 난이도 ramp (적 빈도 ↑ + 속도 ↑)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
