# 엔드리스 러너 (endless-runner) — Plan

> 캐릭터가 화면 좌측에 고정된 채 자동으로 달린다. 우측에서 좌측으로 스크롤되는 두 종류의 장애물(바닥 = 선인장, 공중 = 박쥐)을 회피한다. **위 화살표/스페이스 = 점프, 아래 화살표 = 슬라이드**.
> 베이스: `games/flappy-bird/build.py` (에지 디텍션 + 클론 스크롤 + 게임오버 패턴) + `games/helicopter-cave/build.py` (1버튼 입력 패턴) 결합.
> **차이점**: (1) 점프는 에지 디텍션(키 누른 순간 VY=9, 매 틱 -0.8 중력), 바닥(y=-130) 닿으면 VY=0 + 다시 점프 가능. (2) 슬라이드는 아래 화살표 누르면 size 80→40 (작아짐), 떼면 80 복귀. (3) 장애물 2종: 바닥(공중 점프 회피)/공중(슬라이드 회피). 스폰 주기마다 무작위 선택. (4) 점수는 시간 경과에 비례(매 0.1초 +1), 스크롤 속도는 시간 지날수록 가속.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션(MEMORY.md → feedback-game-design 준수).

---

## 1. 한 줄 룰

자동으로 달리는 캐릭터. **위 화살표/스페이스 = 점프**, **아래 화살표 = 슬라이드**. 장애물(선인장 = 점프 회피, 박쥐 = 슬라이드 회피)에 닿으면 게임오버. 살아남은 시간이 점수.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 황혼 사막 배경 (위는 주황 그라데이션, 아래는 모래색).
- 캐릭터(러너): 화면 좌측 고정 x = -150. y는 점프/슬라이드 외에는 -130 고정.
- 바닥선: y = -150 정도(시각적 표시).
- 선인장 클론(바닥 장애물): 우측(x=260)에서 등장 → 좌측 스크롤 → x<-260 삭제. y = -125 고정.
- 박쥐 클론(공중 장애물): 우측에서 등장 → 좌측 스크롤. y = -90 고정 (서있을 때는 닿고, 슬라이드 때는 피해감).
- 모니터 좌상단: 점수 / 최고기록 / 스크롤속도.

---

## 3. 스프라이트 (6개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태, 장애물 스폰 타이머, 점수 누적, 스크롤 속도 가속 | 게임시작 / 장애물스폰 broadcast 발신 |
| 1 | 러너 | x=-150 고정. 점프 키 에지 → VY=9. 중력 -0.8. y<=-130 이면 VY=0. 아래 화살표 누르면 size=40, 떼면 size=80. 장애물 접촉 시 게임상태=0. | costume 1개. rotationStyle: don't rotate. |
| 2 | 선인장 | 클론. y=-125. 스폰 시 x=260. 좌측 스크롤. x<-260 삭제. | costume "cactus" |
| 3 | 박쥐 | 클론. y=-90. 스폰 시 x=260. 좌측 스크롤. x<-260 삭제. | costume "bat" |
| 4 | 바닥 | 시각적 바닥선 (배경 위에 띠 한 줄). 코드 없음. | costume "ground" |
| 5 | 게임오버 | "GAME OVER" 배너, 평소 숨김. 게임상태=0 일 때 보임. | flappy-bird 패턴 그대로 |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 살아남은 시간 단위(0.1초마다 +1) |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| VY | `varVY04` | 0 | 러너의 수직 속도 |
| 스크롤속도 | `varScroll05` | 5 | 장애물 좌측 스크롤(px/tick). 시간 지날수록 가속 |
| 스폰주기 | `varSpawn06` | 1.4 | 장애물 스폰 인터벌(초). 가속 시 점점 짧아짐 |
| 점프이전키 | `varPrevJump07` | 0 | 점프 키 에지 디텍션용 |
| 장애물종류 | `varKind08` | 0 | 0=선인장(바닥), 1=박쥐(공중). Stage 가 스폰 직전 무작위 결정 |

러너 sprite-local: 없음.
장애물(선인장/박쥐) sprite-local: 없음 (단순 스크롤+삭제만).

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 선인장스폰 | `brSpawnCactus02` | Stage 가 매 `스폰주기` 초마다, 장애물종류=0 인 경우 발신 |
| 박쥐스폰 | `brSpawnBat03` | Stage 가 매 `스폰주기` 초마다, 장애물종류=1 인 경우 발신 |

> 두 종류 장애물 클론 스폰을 같은 broadcast 로 하면 두 sprite 가 항상 함께 스폰됨. 따라서 종류별로 별도 broadcast.

---

## 6. 메커닉 상세

### 6.1 러너 (점프 + 슬라이드)

매 틱(0.025s):

1. **점프 에지 디텍션**: `현재점프키 = (key "up arrow" pressed) OR (key space pressed)`
2. `if 현재점프키 = 1 AND 점프이전키 = 0 AND y <= -129` → `VY = 9` (바닥에 있을 때만 점프)
3. `점프이전키 = 현재점프키`
4. **중력**: `VY = VY - 0.8`
5. **위치 갱신**: `change y by VY`
6. **바닥 도착**: `if y < -130 → y = -130, VY = 0` (다시 점프 가능)
7. **슬라이드(크기)**: `if (key "down arrow" pressed) → size = 40 else size = 80`
8. **장애물 충돌**: `touching 선인장 OR touching 박쥐 → 게임상태=0`
9. **최고기록**: `if 점수 > 최고기록 → 최고기록 = 점수`
10. wait 0.025

> 핵심 트릭: 슬라이드는 size 를 작게 만들어 박쥐(y=-90)의 충돌 박스를 빠져나간다. 박쥐는 y=-90 고정, 러너는 y=-130 고정. 러너 size=80 (높이 약 80px) → 머리 ~ -90. 박쥐 충돌 가능. size=40 → 머리 ~ -110. 박쥐 안 닿음.

### 6.2 장애물 스폰 (Stage)

`when receive 게임시작` forever:
```
repeat until 게임상태 = 0:
  장애물종류 = pick random 0 to 1
  if 장애물종류 = 0:
    broadcast 선인장스폰
  else:
    broadcast 박쥐스폰
  wait 스폰주기
```

별도 forever 로 점수 누적 & 가속:
```
repeat until 게임상태 = 0:
  점수 = 점수 + 1
  # 매 5점마다 스크롤속도 +1, 스폰주기 -0.05
  if (점수 mod 50 = 0):
    스크롤속도 = 스크롤속도 + 1
    if 스폰주기 > 0.6:
      스폰주기 = 스폰주기 - 0.1
  wait 0.1
```

### 6.3 선인장 (클론)

`when receive 선인장스폰`:
- size=80, y=-125, x=260 위치 잡기 → create clone

`when I start as clone`:
```
show
repeat until 게임상태 = 0:
  change x by (-1 * 스크롤속도)
  if x position < -260: delete this clone
  wait 0.025
delete this clone
```

### 6.4 박쥐 (클론)

동일하지만 y=-90.

### 6.5 게임오버 / 재시작

flappy-bird 와 동일. 배너 sprite 가 `wait_until 게임상태=1 → wait_until 게임상태=0 → show`. 깃발 다시 클릭 → 변수 리셋 → 새 게임. 러너 sprite 에서 게임오버 시 pop 효과음.

---

## 7. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  게임상태 ← 1
  VY ← 0
  스크롤속도 ← 5
  스폰주기 ← 1.4
  점프이전키 ← 0
  장애물종류 ← 0
  broadcast 게임시작

when receive 게임시작:   # forever 1: 장애물 스폰
  repeat until 게임상태 = 0:
    장애물종류 ← pick random 0 to 1
    if 장애물종류 = 0:
      broadcast 선인장스폰
    else:
      broadcast 박쥐스폰
    wait 스폰주기

when receive 게임시작:   # forever 2: 점수 + 가속
  repeat until 게임상태 = 0:
    점수 ← 점수 + 1
    if (점수 mod 50) = 0:
      스크롤속도 ← 스크롤속도 + 1
      if 스폰주기 > 0.6:
        스폰주기 ← 스폰주기 - 0.1
    wait 0.1
```

### 러너

```
when flag clicked:
  goto -150, -130
  size 80
  point in direction 90
  show

when receive 게임시작:
  VY ← 0
  점프이전키 ← 0
  goto -150, -130
  size 80
  repeat until 게임상태 = 0:
    # 점프 에지 디텍션 (바닥에 있을 때만)
    if ((key up arrow pressed) OR (key space pressed)) AND 점프이전키=0 AND (y < -129):
      VY ← 9
    if (key up arrow pressed) OR (key space pressed):
      점프이전키 ← 1
    else:
      점프이전키 ← 0
    # 중력
    VY ← VY - 0.8
    change y by VY
    # 바닥 클램프
    if y position < -130:
      goto x:-150 y:-130
      VY ← 0
    # 슬라이드 크기
    if (key down arrow pressed):
      size 40
    else:
      size 80
    # 충돌
    if touching 선인장: 게임상태 ← 0
    if touching 박쥐: 게임상태 ← 0
    # 최고기록
    if 점수 > 최고기록: 최고기록 ← 점수
    wait 0.025

when flag clicked:   # 게임오버 시 효과음
  wait until 게임상태 = 0
  play sound pop
```

### 선인장

```
when flag clicked:
  hide
  size 80

when receive 선인장스폰:
  goto (260, -125)
  switch costume "cactus"
  create clone of _myself_

when I start as clone:
  show
  repeat until 게임상태 = 0:
    change x by (-1 * 스크롤속도)
    if x position < -260: delete this clone
    wait 0.025
  delete this clone
```

### 박쥐

```
when flag clicked:
  hide
  size 80

when receive 박쥐스폰:
  goto (260, -90)
  switch costume "bat"
  create clone of _myself_

when I start as clone:
  show
  repeat until 게임상태 = 0:
    change x by (-1 * 스크롤속도)
    if x position < -260: delete this clone
    wait 0.025
  delete this clone
```

### 바닥

```
when flag clicked:
  goto 0, -150
  show
```

### 게임오버 배너

flappy-bird 와 동일.

---

## 8. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| 배경 | SVG (인라인) | 황혼 사막. 위쪽 주황 그라데이션, 아래쪽 모래색, 멀리 산 실루엣 |
| 러너 | SVG (인라인) | 60×80. 캐릭터 (귀여운 픽토 인간). rotationCenterX 30, rotationCenterY 40 |
| 선인장 | SVG (인라인) | 50×60. 초록 선인장 + 흰 가시. rotationCenterX 25, rotationCenterY 30 |
| 박쥐 | SVG (인라인) | 70×40. 검은 박쥐 (날개 펼친). rotationCenterX 35, rotationCenterY 20 |
| 바닥 | SVG (인라인) | 480×30. 갈색 모래 띠. rotationCenterX 240, rotationCenterY 15 |
| 게임오버 배너 | SVG (인라인) | "GAME OVER" + "장애물에 부딪혔어요" |
| pop.wav | WAV (assets/) | flappy-bird/assets/pop.wav 복사. 게임오버 효과음 |

---

## 9. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과
2. `project.json` JSON 로드 OK
3. targets 수: 6 (Stage, 러너, 선인장, 박쥐, 바닥, 게임오버) — Stage 포함 6개
4. Stage 변수 8개(점수/최고기록/게임상태/VY/스크롤속도/스폰주기/점프이전키/장애물종류) 모두 등록
5. Broadcasts: 게임시작 / 선인장스폰 / 박쥐스폰 3개
6. 선인장 sprite 코스튬 1개(cactus), 박쥐 sprite 코스튬 1개(bat)
7. 자산: 6 SVG + 1 WAV(pop)
8. 러너 sprite 의 `control_repeat_until` 안에:
   - `sensing_keypressed`("up arrow") 와 `sensing_keypressed`("space") 둘 다 존재
   - `sensing_keypressed`("down arrow") 존재
   - `data_setvariableto`(VY, 9) 점프 트리거 존재
   - `data_changevariableby`(VY, -0.8) 중력 존재
   - `motion_changeyby` (VY 사용) 존재
   - `looks_setsizeto`(40) 슬라이드 크기 변경 존재
   - `looks_setsizeto`(80) 일반 크기 복귀 존재
   - `sensing_touchingobject`("선인장"), `sensing_touchingobject`("박쥐") 둘 다 존재
9. Stage 에 `when receive 게임시작` 핸들러 2개 이상 (장애물 스폰 + 점수 누적)
10. 선인장 sprite 의 `control_start_as_clone` 트리에 `motion_changexby`(스크롤속도) 와 `control_delete_this_clone` 존재
11. 박쥐 sprite 의 `control_start_as_clone` 트리에 `motion_changexby` 와 `control_delete_this_clone` 존재
12. monitors 에 점수·최고기록 표시
13. 모든 자산 MD5 일치
14. 블록 카운트 220~330 범위

---

## 10. 빌드 카운트 예상

- Stage: ~45 블록 (init 8개 + 장애물 스폰 forever + 점수+가속 forever)
- 러너: ~120 블록 (에지 디텍션 + 점프 + 중력 + 바닥 클램프 + 슬라이드 + 충돌 2종 + 최고기록 + 사운드)
- 선인장: ~35 블록 (스폰 + 클론 스크롤)
- 박쥐: ~35 블록 (스폰 + 클론 스크롤)
- 바닥: ~5 블록 (정적)
- 게임오버: ~12 블록
- **총합 예상: 240~260 블록**

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **에지 디텍션 + 클론 스크롤 + 게임오버 배너**: `games/flappy-bird/build.py` — 거의 그대로.
- **차이 1**: 새의 단일 점프 키 + 천장/바닥 → 러너의 "바닥에 있을 때만 점프 가능" 조건 + 슬라이드 크기 변경.
- **차이 2**: 파이프 페어(상단+하단) 동시 스폰 → 단일 장애물 스폰 (랜덤 선인장 or 박쥐).
- **차이 3**: flappy-bird 의 통과 카운트 점수 → 시간 누적 점수 (Stage forever).
- **차이 4**: helicopter-cave 의 시간 지날수록 가속 패턴 차용.

빌더는 flappy-bird 의 build.py 를 거의 그대로 카피한 뒤 다음만 바꾸면 됨:
1. 파이프 페어 → 단일 장애물 (선인장/박쥐 2 sprite)
2. 새의 1버튼 점프 → 러너의 (점프 키 에지) + (바닥 클램프) + (슬라이드 키 size 변경)
3. flappy-bird Stage 의 단일 forever → Stage 의 forever 2개(장애물 스폰 / 점수 누적+가속)
4. 변수: 점수/최고기록/게임상태/VY/스크롤속도/스폰주기/점프이전키/장애물종류 (GAP중심·GAP크기 제거)

---

## 12. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (Chrome 공룡, Subway Surfers 의 단순화)
- [x] 추상 학습 콘셉트 없음 (러너=캐릭터, 선인장=장애물, 박쥐=장애물)
- [x] 즉시 이해되는 룰 (점프 / 슬라이드 / 부딪히면 끝)
- [x] 시각적 위협감 (장애물 다가옴) + 도전감 (속도 가속)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
- [x] Chrome 공룡 게임 — 검증된 재미 메커닉
