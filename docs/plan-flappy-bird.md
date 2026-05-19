# 플래피 버드 (flappy-bird) — Plan

> 스페이스를 한 번 누를 때마다 새가 위로 짧게 점프(파닥). 누르지 않으면 중력으로 자유낙하. 화면 우측에서 좌측으로 스크롤되는 파이프 페어(상단+하단, 가운데 빈 공간) 사이를 통과한다. 2013 Dong Nguyen "Flappy Bird" 의 메커닉.
> 베이스: `games/helicopter-cave/build.py` (1버튼 + VY 누적 + 막대 클론 스크롤 + 게임오버 패턴). **차이점**: (1) "꾹 누르기" 가 아닌 "한 번 누를 때마다 VY = 8 점프" — 에지 디텍션 필요. (2) 천장/바닥 막대 대신 파이프 페어(상단+하단) — gap 의 y 중심이 무작위. (3) 매 초 점수 +1 이 아니라 파이프 페어 넘길 때마다 +1.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지(MEMORY.md → feedback-game-design 준수).

---

## 1. 한 줄 룰

스페이스(또는 마우스 클릭)를 한 번 누를 때마다 새가 위로 파닥. 파이프나 천장·바닥에 닿으면 게임오버. 통과한 파이프 페어 수가 점수.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 하늘색 그라데이션 (낮 하늘) + 옅은 구름 점들.
- 새: 화면 좌측 고정 x = -100. y 만 변화.
- 파이프(상단) 클론: 초록 사각형. 위에서 아래로 내려옴. 화면 우측(x=240+)에서 등장 → 왼쪽으로 스크롤(-3px/틱) → x < -260 에서 클론 삭제.
- 파이프(하단) 클론: 동일한 메커닉, 아래에서 위로.
- 한 페어 = 상단 + 하단 두 클론이 동시 스폰. 가운데 gap = 100px, gap 의 y 중심 = 무작위 (-80 ~ +80).
- 모니터 좌상단: 점수 / 최고기록.

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 + 파이프 페어 스폰 타이머 + gap 중심 무작위 발생 | 게임시작/파이프스폰 broadcast 발신 |
| 1 | 새 | x=-100 고정. 입력 에지(한 번 누름) 시 VY=8. 매 틱 VY -= 0.8 (중력). y += VY. 천장(y>175) / 바닥(y<-175) / 파이프 접촉 시 게임상태=0. | rotationStyle: don't rotate. 코스튬 1개. |
| 2 | 상단파이프 | 클론 스폰 시 y = gap중심 + gap크기/2 + 파이프높이/2 위치. x=260 등장 → -스크롤속도/틱 → 통과 시 +점수 1회 → x<-260 삭제. | rotationStyle: don't rotate. costume "pipe_top". |
| 3 | 하단파이프 | 동일하지만 y = gap중심 - gap크기/2 - 파이프높이/2. 점수 카운트는 상단파이프가 담당(중복 방지). costume "pipe_bot". | rotationStyle: don't rotate. |
| 4 | 게임오버 | "GAME OVER" 배너, 평소 숨김. 게임상태=0 일 때만 보임. | helicopter-cave 패턴 그대로. |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 통과한 파이프 페어 수 |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| VY | `varVY04` | 0 | 새의 수직 속도 |
| 스크롤속도 | `varScroll05` | 3 | 파이프 좌측 스크롤 (px/tick) |
| 스폰주기 | `varSpawn06` | 1.5 | 파이프 페어 스폰 인터벌(초) |
| GAP중심 | `varGapY07` | 0 | 다음 파이프 페어의 gap 중심 y |
| GAP크기 | `varGapH08` | 100 | gap 의 세로 크기 (px) |
| 이전키 | `varPrevKey09` | 0 | 직전 틱 입력 상태 (에지 디텍션용. 1=눌림 / 0=안눌림) |

새 sprite-local 변수: 없음.
파이프 sprite-local 변수: `통과여부` (각 클론마다 점수 +1 1회 한정). Scratch 의 클론은 sprite 변수 "for this sprite only" 를 자동 복제하므로 사용 가능.

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 파이프스폰 | `brSpawn02` | Stage 가 매 `스폰주기` 초마다 발신. GAP중심을 무작위로 갱신한 직후 발신 → 상단파이프+하단파이프 동시 수신 |

---

## 6. 메커닉 상세

### 6.1 새 (1버튼 점프, 중력)

매 틱(0.025s):

1. **에지 디텍션 입력**: `현재키눌림 = (key space pressed) OR (mouse down)`
2. `if 현재키눌림 = 1 AND 이전키 = 0` → `VY = 8` (위로 파닥 한 번)
3. `이전키 = 현재키눌림` (다음 틱을 위해 저장)
4. **중력**: `VY = VY - 0.8`
5. **VY clamp 하한**: `if VY < -10 → VY = -10` (너무 빨리 떨어지지 않게)
6. **위치 갱신**: `change y by VY`
7. **천장/바닥**: `if y > 175 → 게임상태=0`, `if y < -175 → 게임상태=0`
8. **파이프 충돌**: `touching 상단파이프 OR touching 하단파이프 → 게임상태=0`
9. **최고기록**: `if 점수 > 최고기록 → 최고기록 = 점수`
10. wait 0.025

> 에지 디텍션이 핵심. helicopter-cave 의 "VY += 0.5 매 틱" 방식이 아니라 "키 입력 순간 한 번만 VY=8" 으로 바꾸는 게 핵심 차이.

### 6.2 파이프 페어 스폰 (Stage)

`when receive 게임시작` 의 forever:
```
repeat until 게임상태 = 0:
  GAP중심 = pick random -80 to 80
  broadcast 파이프스폰   # 상단+하단 둘 다 수신
  wait 스폰주기
```

### 6.3 상단 파이프 (클론)

`when receive 파이프스폰`:
- 상단파이프 SVG 는 100×200 (가로 100, 세로 200 = 충분히 길게). size=100.
- y = GAP중심 + GAP크기/2 + 100 (파이프 세로의 절반=100). x=260.
- create clone of myself

`when I start as clone`:
```
통과여부 = 0
show
repeat until 게임상태 = 0:
  change x by (-1 * 스크롤속도)
  # 통과 카운트: x position < -100 (새의 x) 이면서 통과여부=0 일 때
  if x position < -100 AND 통과여부 = 0:
    점수 = 점수 + 1
    통과여부 = 1
  if x position < -260: delete this clone
  wait 0.025
delete this clone
```

### 6.4 하단 파이프 (클론)

`when receive 파이프스폰`:
- y = GAP중심 - GAP크기/2 - 100 (파이프 세로 절반=100). x=260.
- create clone of myself

`when I start as clone`: 상단과 동일하되 **점수 카운트는 하지 않음**(상단이 담당). 단지 스크롤+삭제만.

### 6.5 게임오버 / 재시작

helicopter-cave 와 동일. 배너 sprite 가 `wait_until 게임상태=1 → wait_until 게임상태=0 → show`. 깃발 다시 클릭 → 변수 리셋 → 새 게임. 새 sprite 에 게임오버 사운드(pop) 재생.

---

## 7. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  최고기록 유지 (전역 변수 보존)  # 굳이 리셋하지 않음
  게임상태 ← 1
  VY ← 0
  스크롤속도 ← 3
  스폰주기 ← 1.5
  GAP중심 ← 0
  GAP크기 ← 100
  이전키 ← 0
  broadcast 게임시작

when receive 게임시작:   # forever 1: 파이프 페어 스폰
  repeat until 게임상태 = 0:
    GAP중심 ← pick random -80 to 80
    broadcast 파이프스폰
    wait 스폰주기
```

### 새

```
when flag clicked:
  goto -100, 0
  size 80
  point in direction 90
  show

when receive 게임시작:
  VY ← 0
  이전키 ← 0
  goto -100, 0
  repeat until 게임상태 = 0:
    # 에지 디텍션
    if (key space pressed OR mouse down) AND 이전키 = 0:
      VY ← 8
    if (key space pressed OR mouse down):
      이전키 ← 1
    else:
      이전키 ← 0
    # 중력
    VY ← VY - 0.8
    if VY < -10: VY ← -10
    # 위치
    change y by VY
    # 천장/바닥
    if y position > 175:   게임상태 ← 0
    if y position < -175:  게임상태 ← 0
    # 파이프 충돌
    if touching 상단파이프:  게임상태 ← 0
    if touching 하단파이프:  게임상태 ← 0
    # 최고기록
    if 점수 > 최고기록: 최고기록 ← 점수
    wait 0.025

when flag clicked:   # 별도 hat: 게임오버 시 효과음
  wait until 게임상태 = 0
  play sound pop
```

### 상단파이프

```
when flag clicked:
  hide
  size 100

when receive 파이프스폰:
  goto (260, GAP중심 + GAP크기/2 + 100)
  switch costume "pipe_top"
  create clone of _myself_

when I start as clone:
  통과여부 ← 0
  show
  repeat until 게임상태 = 0:
    change x by (-1 * 스크롤속도)
    if x position < -100 AND 통과여부 = 0:
      점수 ← 점수 + 1
      통과여부 ← 1
    if x position < -260: delete this clone
    wait 0.025
  delete this clone
```

### 하단파이프

```
when flag clicked:
  hide
  size 100

when receive 파이프스폰:
  goto (260, GAP중심 - GAP크기/2 - 100)
  switch costume "pipe_bot"
  create clone of _myself_

when I start as clone:
  show
  repeat until 게임상태 = 0:
    change x by (-1 * 스크롤속도)
    if x position < -260: delete this clone
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
| 배경 | SVG (인라인) | 하늘색 그라데이션 + 옅은 구름 |
| 새 | SVG (인라인) | 60×45. 노란 몸통 + 주황 부리 + 빨간 깃 + 검은 눈. rotationCenterX 30, rotationCenterY 22. |
| pipe_top | SVG (인라인) | 100×200. 초록 파이프 본체 + 아래쪽(바닥)에 두꺼운 림(rim) 강조. rotationCenterX 50, rotationCenterY 100. |
| pipe_bot | SVG (인라인) | 100×200. 초록 파이프 본체 + 위쪽(천장)에 두꺼운 림 강조. rotationCenterX 50, rotationCenterY 100. |
| 게임오버 배너 | SVG (인라인) | "GAME OVER" + "파이프에 부딪혔어요" |
| pop.wav | WAV (assets/) | helicopter-cave/assets/pop.wav 복사. 게임오버 효과음 |

> 파이프 크기: SVG viewBox 100×200, Scratch size 100 → 100×200 px. 가로 100 px, 세로 200 px (충분히 길어 화면 위/아래로 빠져나가도 빈 공간 안 보임). gap 크기 100 px, gap 중심 ±80 → gap 상단 = 130 ~ -30, gap 하단 = 30 ~ -130 범위로 자연스럽게 변동.

---

## 9. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과
2. `project.json` JSON 로드 OK
3. targets 수: 5 (Stage, 새, 상단파이프, 하단파이프, 게임오버)
4. Stage 변수 9개(점수/최고기록/게임상태/VY/스크롤속도/스폰주기/GAP중심/GAP크기/이전키) 모두 등록
5. Broadcasts: 게임시작 / 파이프스폰 2개
6. 상단파이프 sprite 코스튬 1개(pipe_top), 하단파이프 sprite 코스튬 1개(pipe_bot)
7. 자산: 5 SVG(배경/새/pipe_top/pipe_bot/게임오버) + 1 WAV(pop)
8. 새 sprite 의 `control_repeat_until` 안에:
   - `sensing_keypressed`("space") 존재
   - `sensing_mousedown` 존재
   - `operator_or` 로 둘 결합
   - `operator_and` 로 (입력 AND 이전키=0) 에지 디텍션 존재
   - `data_setvariableto`(VY, 8) 점프 트리거 존재
   - `data_changevariableby`(VY, -0.8) 중력 존재
   - `motion_changeyby` (VY 사용) 존재
   - `sensing_touchingobject`("상단파이프"), `sensing_touchingobject`("하단파이프") 둘 다 존재
9. Stage 에 `when receive 게임시작` 핸들러 1개 이상 (파이프 스폰)
10. 상단파이프 sprite 의 `control_start_as_clone` 트리에 `motion_changexby`(스크롤속도) 와 `control_delete_this_clone`, `data_changevariableby`(점수, 1) 모두 존재
11. 하단파이프 sprite 의 `control_start_as_clone` 트리에 `motion_changexby` 와 `control_delete_this_clone` 존재 (점수 카운트는 없음)
12. monitors 에 점수·최고기록 표시
13. 모든 자산 MD5 일치
14. 블록 카운트 200~320 범위

---

## 10. 빌드 카운트 예상

- Stage: ~25 블록 (init 9개 + 파이프 스폰 forever 1개)
- 새: ~110 블록 (에지 디텍션 + 중력 + 위치 + 천장/바닥/파이프 충돌 + 최고기록 + 사운드)
- 상단파이프: ~45 블록 (스폰 + 클론 forever + 점수 카운트)
- 하단파이프: ~35 블록 (스폰 + 클론 forever, 점수 없음)
- 게임오버: ~12 블록
- **총합 예상: 225~280 블록** (★★★ 범위)

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **VY 누적 + 클론 스크롤**: `games/helicopter-cave/build.py` — 거의 같은 패턴. 헬리콥터→새, 천장막대→상단파이프, 바닥막대→하단파이프.
- **차이 1**: 헬리콥터의 `VY += 0.5 / -0.4` 매 틱 방식 대신 "에지 디텍션 + VY = 8 점프 + 매 틱 -0.8 중력".
- **차이 2**: 천장/바닥막대는 같은 y 라인에서 size 만 변함. 파이프는 y 자체가 GAP중심 ± 오프셋으로 변함.
- **차이 3**: helicopter-cave 는 매 초 점수 +1 (시간 기반). 파이프는 통과 시 +1 (이벤트 기반). 상단파이프 클론이 `if x < -100 AND 통과여부=0 → 점수+1, 통과여부=1`.
- **monitors / project assemble**: helicopter-cave 의 main() 거의 그대로 사용.

빌더는 helicopter-cave 의 build.py 를 거의 그대로 카피한 뒤 다음만 바꾸면 됨:
1. 헬리콥터의 입력 메커닉 → 에지 디텍션 + 점프 트리거
2. 천장/바닥 막대 두께 ramp → 파이프 페어 y 위치 무작위
3. 1초 타이머 점수 → 파이프 통과 점수 (상단파이프 클론 내부에서 카운트)
4. 천장두께/바닥두께/경과틱 변수 제거, GAP중심/GAP크기/이전키 변수 추가

---

## 12. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (1버튼 탭 + 파이프 회피, 룰 즉시 이해)
- [x] 추상 학습 콘셉트 없음 (새=새, 파이프=파이프)
- [x] 즉시 이해되는 룰 (누르면 파닥, 부딪히면 끝, 통과하면 점수)
- [x] 시각적 위협감 (파이프가 다가옴) + 도전감 (gap 위치 무작위)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
- [x] 2013 Flappy Bird 클래식 — 검증된 재미 메커닉
