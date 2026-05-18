# 운석 회피 (meteor-dodge) — Plan

> 우주선을 화살표로 자유 이동시켜 화면 위에서 무작위로 떨어지는 운석을 피한다. 오래 살아남을수록 점수↑. 시간 지날수록 운석 생성 주기가 짧아져 난이도가 올라간다.
> 베이스: `games/doodle-jump/build.py` (클론 스폰/스폰퇴장/카메라 같은 forever 패턴) + `games/asteroids/build.py` (우주 배경/우주선 SVG/3 크기 코스튬). **차이점**: 우주선 관성 없음(직접 위치 변경), 카메라 스크롤 없음, 운석은 위→아래 일방향 낙하, 발사 메커닉 없음.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지.

---

## 1. 한 줄 룰

화살표 4방향으로 우주선을 자유 이동, 위에서 떨어지는 운석을 피한다. 한 번 부딪히면 게임오버. 생존 시간이 점수.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 검은 우주 + 작은 별 점들 (asteroids 스타일).
- 모니터 좌상단: 점수 / 최고기록.

---

## 3. 스프라이트 (4개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 + 운석 스폰 타이머 호스트 + 점수 +1 매 초 | 게임시작 broadcast 발신 |
| 1 | 우주선 | 화살표 4방향 자유 이동, 가장자리 clamp, 운석 접촉 시 게임상태=0 | rotationStyle: don't rotate |
| 2 | 운석 | 클론 무한 스폰. 화면 위 무작위 x에서 등장 → 아래로 떨어짐. 화면 밖이면 클론 삭제. 3 코스튬(큰/중/작) | rotationStyle: don't rotate |
| 3 | 게임오버 | "GAME OVER" 배너, 평소 숨김. 게임상태=0 일 때만 보임. | doodle-jump 패턴 그대로 |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 생존 시간 (매 초 +1) |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 (게임오버 시 갱신) |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| 운석X | `varMX04` | 0 | 운석 스폰 x 좌표 |
| 운석크기 | `varMSize05` | 1 | 1=큰, 2=중, 3=작 (스폰 시 set) |
| 운석속도 | `varMSpeed06` | 3 | 운석 낙하 속도 (크기별 다름) |
| 스폰주기 | `varSpawn07` | 1.0 | 운석 스폰 인터벌(초). 시간 지날수록 감소 |
| 경과틱 | `varTick08` | 0 | 초 단위 경과 타이머 (난이도 ramp) |

운석 sprite-local 변수:

| 변수명 | ID | 용도 |
|--------|----|------|
| 내속도 | `varMyV09` | 클론 시작 시 stage 변수 `운석속도` 로컬 복사. 매 틱 y -= 내속도 |

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 운석스폰 | `brSpawn02` | Stage 가 매 `스폰주기` 초마다 발신 → 운석 클론 1개 생성 |

---

## 6. 메커닉 상세

### 6.1 우주선 (좌표/조작)

매 틱(약 0.025s, 40fps):

1. 좌/우/위/아래 화살표 입력 → x/y ± 5 (단순 직접 변경, 관성 없음).
2. **가장자리 clamp** (wrap 아님, 가장자리에 부딪힘):
   - x < -230 → x = -230
   - x > 230 → x = 230
   - y < -170 → y = -170
   - y > 170 → y = 170
3. **충돌 체크**: `touching 운석` 이면 → 게임상태 = 0, 최고기록 갱신.
4. wait 0.025.

### 6.2 운석 스폰 (Stage)

`when receive 게임시작` 의 forever 루프:

```
repeat until 게임상태 = 0:
  운석X = random(-220..220)
  k = random(1..10)
  if k <= 3:   # 30%
    운석크기 = 1   # 큰
    운석속도 = 2.5
  else if k <= 7:  # 40%
    운석크기 = 2   # 중
    운석속도 = 3.5
  else:            # 30%
    운석크기 = 3   # 작
    운석속도 = 4.5
  broadcast 운석스폰
  wait 스폰주기
```

별도 forever (난이도 ramp):

```
repeat until 게임상태 = 0:
  wait 1
  경과틱 += 1
  점수 += 1     # 매 초 점수 +1 (생존시간)
  # 5초마다 스폰주기 10% 줄이기 (하한 0.25)
  if 경과틱 mod 5 = 0 and 스폰주기 > 0.25:
    스폰주기 = 스폰주기 * 0.9
```

> 단순화: `mod` 대신 `5초마다` 별도 wait 5 forever 로 처리해 ramp 한 번씩 줄이는 게 빌더에 친화적이다. 본 plan은 후자(별도 wait-5 forever)로 구현.

### 6.3 운석 (클론)

`when receive 운석스폰`:
- goto (운석X, 200) — 화면 상단 살짝 위
- 코스튬: 운석크기에 따라 분기 — 1→"rock_big"/size 100, 2→"rock_med"/size 70, 3→"rock_small"/size 50
- 내속도 = 운석속도
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

> 운석 충돌 판정은 우주선 쪽에서 `touching 운석` 으로 한다(운석 쪽에서 안 함). 게임오버 시 모든 클론은 repeat until 종료 후 delete.

### 6.4 게임오버

우주선 sprite 가 매 틱 충돌 체크 → 게임상태 = 0 + 최고기록 갱신.
게임오버 배너 sprite 가 `wait_until 게임상태=1 → wait_until 게임상태=0 → show`.

### 6.5 재시작

깃발 다시 클릭 → 모든 변수 리셋 → 새 게임.

---

## 7. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  게임상태 ← 1
  스폰주기 ← 1.0
  경과틱 ← 0
  broadcast 게임시작

when receive 게임시작:
  # forever 1: 스폰 루프
  repeat until 게임상태 = 0:
    운석X ← random(-220..220)
    k = random(1..10)
    if k < 4: 운석크기=1, 운석속도=2.5
    if 3 < k AND k < 8: 운석크기=2, 운석속도=3.5
    if k > 7: 운석크기=3, 운석속도=4.5
    broadcast 운석스폰
    wait 스폰주기

when receive 게임시작:   # 별도 forever 2: 1초 타이머 + 점수
  repeat until 게임상태 = 0:
    wait 1
    경과틱 ← 경과틱 + 1
    점수 ← 점수 + 1

when receive 게임시작:   # 별도 forever 3: 5초마다 난이도 ramp
  repeat until 게임상태 = 0:
    wait 5
    if 스폰주기 > 0.25:
      스폰주기 ← 스폰주기 * 0.85
```

> 3개의 `when receive 게임시작` 핸들러를 둬서 병렬 forever 구현. Scratch 표준 패턴.

### 우주선

```
when flag clicked:
  goto 0, -100
  size 70
  point in direction 0
  show

when receive 게임시작:
  goto 0, -100
  repeat until 게임상태 = 0:
    if key ←: change x by -5
    if key →: change x by 5
    if key ↑: change y by 5
    if key ↓: change y by -5
    # clamp
    if x < -230: set x to -230
    if x > 230: set x to 230
    if y < -170: set y to -170
    if y > 170: set y to 170
    # 충돌
    if touching 운석:
      게임상태 ← 0
      if 점수 > 최고기록: 최고기록 ← 점수
    wait 0.025
```

### 운석

```
when flag clicked:
  hide
  size 100

when receive 운석스폰:
  goto (운석X, 200)
  if 운석크기 = 1: switch costume "rock_big",  set size 100
  if 운석크기 = 2: switch costume "rock_med", set size 70
  if 운석크기 = 3: switch costume "rock_small", set size 50
  set 내속도 ← 운석속도
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
| 배경 | SVG (인라인) | 검은 우주 + 작은 별 점 약 40개 |
| 우주선 | SVG (인라인) | 위쪽을 향한 흰/하늘 삼각형 우주선 + 분사구. 36×36 viewBox |
| rock_big | SVG (인라인) | 큰 회색 다각형 (asteroids 의 rock_big 와 유사) |
| rock_med | SVG (인라인) | 중간 회색 다각형 |
| rock_small | SVG (인라인) | 작은 회색 다각형 |
| 게임오버 배너 | SVG (인라인) | 검은 배너 "GAME OVER" + "운석에 부딪혔어요" 안내 |
| pop.wav | WAV (assets/) | doodle-jump 의 것 복사. 운석 스폰 또는 게임오버 효과음 |

assets/ 폴더에 둘 외부 파일: `pop.wav` 하나면 충분. 나머지 SVG 는 build.py 인라인.

---

## 9. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과
2. `project.json` JSON 로드 OK
3. targets 수: 4 (Stage, 우주선, 운석, 게임오버)
4. Stage 변수 8개(점수/최고기록/게임상태/운석X/운석크기/운석속도/스폰주기/경과틱) 모두 등록
5. 운석 sprite-local 변수 1개(내속도) 등록
6. Broadcasts: 게임시작 / 운석스폰 2개
7. 운석 스프라이트 코스튬 3개 (rock_big, rock_med, rock_small)
8. 자산 6 SVG (배경/우주선/rock_big/rock_med/rock_small/게임오버) + 1 WAV (pop)
9. 우주선 sprite 의 control_repeat_until 안에 화살표 4방향 sensing_keypressed × 4 가 모두 존재
10. 우주선 sprite 의 같은 루프 안에 `sensing_touchingobject`("운석") + `data_setvariableto`(게임상태=0) 블록 존재
11. Stage 에 `when receive 게임시작` 핸들러가 3개 이상 (스폰 루프 + 1초 타이머 + 5초 ramp)
12. 운석 sprite 의 `control_start_as_clone` 트리에 `motion_changeyby` (내속도 사용) 와 `control_delete_this_clone` 모두 존재
13. monitors 에 점수·최고기록 모니터 표시
14. 모든 자산 MD5 일치 (zip 안 파일명 ↔ assetId)
15. 블록 카운트 150~280 범위

---

## 10. 빌드 카운트 예상

- Stage: ~55 블록 (init + 3개 forever 핸들러)
- 우주선: ~80 블록 (4방향 키 입력 + clamp ×4 + 충돌 + 최고기록 갱신)
- 운석: ~50 블록 (스폰 분기 3 + 클론 forever + 삭제)
- 게임오버: ~12 블록 (doodle-jump 와 동일)
- **총합 예상: 180~220 블록**

---

## 11. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (4방향 이동 + 회피)
- [x] 추상 학습 콘셉트 없음 (운석 = 운석. 수학·과학 개념 매핑 없음)
- [x] 즉시 이해되는 룰 (피하면 점수, 부딪히면 끝)
- [x] 시각적 위협감 + 적절한 난이도 ramp
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
