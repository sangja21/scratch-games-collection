# 지오메트리 대시 (geometry-dash) — Plan

> 큐브가 화면 좌측에 고정되어 자동으로 달린다. 우측에서 좌측으로 스크롤되는 가시/블록 패턴을 **스페이스 또는 위 화살표 단일 키 점프**로 회피한다. 가시에 닿거나 천장 가시에 닿으면 즉사. 블록 위에는 착지하고 점프 가능.
> 베이스: `games/endless-runner/build.py` (자동 달리기 + 클론 스크롤 + 게임오버 패턴) — 거의 그대로 카피.
> **차이점**: (1) 슬라이드 없음. 점프 1버튼만. (2) 점프 더 빠르고 짧음(VY=11, 중력=-1.2). (3) 장애물 3종: **가시(바닥)** — 점프 회피, **블록** — 점프해서 위에 착지하고 다시 점프 가능, **천장가시** — 일정 높이 이상에 즉사 띠. (4) 비트 동기화: 스폰 주기 = 0.55초 고정(BPM ≈ 109), 매 스폰 사이클마다 패턴 무작위 선택. (5) 거리 점수 = 시간 누적. (6) 게임오버 즉시 깃발 다시 누르면 처음부터.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션(MEMORY.md → feedback-game-design 준수).

---

## 1. 한 줄 룰

자동으로 달리는 큐브. **스페이스/위 화살표 = 점프**. 바닥 가시·천장 가시는 닿으면 즉사. 블록은 위에 착지해 다시 점프할 수 있다. 살아남은 시간이 점수.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 네온 다크 (위는 보라/남색 그라데이션, 아래는 진보라). Geometry Dash 풍.
- 큐브(플레이어): 화면 좌측 고정 x = -150. y는 점프 외에는 -130 (바닥) 고정.
- 바닥선: y = -150 (시각적 띠).
- 천장 가시 띠: y = +80 ~ +130 영역 (점프로 너무 높이 안 가게 위협).
- 가시 클론(바닥): 우측(x=260)에서 등장 → 좌측 스크롤 → x<-260 삭제. y = -130 고정 (큐브와 같은 높이).
- 블록 클론(낮음 점프대): 우측에서 등장 → 좌측 스크롤. y = -105 고정 (큐브가 위에 착지하면 y ≈ -85).
- 천장가시 클론: 우측에서 등장 → 좌측 스크롤. y = +110 고정. 큐브가 너무 높이 점프하면 닿음.
- 모니터 좌상단: 점수 / 최고기록 / 스크롤속도.

---

## 3. 스프라이트 (7개 = Stage + 6)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태, 비트 스폰 타이머, 점수 누적, 스크롤 속도 가속 | 게임시작 / 가시스폰 / 블록스폰 / 천장스폰 broadcast 발신 |
| 1 | 큐브 | x=-150 고정. 점프 키 에지 → VY=11. 중력 -1.2. y<=-130 이면 VY=0, 다시 점프 가능. 블록 위 착지 시 VY=0. 가시/천장가시 접촉 시 게임상태=0. | costume 1개. rotationStyle: don't rotate. |
| 2 | 가시 | 클론. y=-130. 스폰 시 x=260. 좌측 스크롤. x<-260 삭제. | costume "spike" |
| 3 | 블록 | 클론. y=-105. 스폰 시 x=260. 좌측 스크롤. x<-260 삭제. | costume "block" |
| 4 | 천장가시 | 클론. y=+110. 스폰 시 x=260. 좌측 스크롤. x<-260 삭제. | costume "ceil" |
| 5 | 바닥 | 시각적 바닥선 (배경 위에 네온 띠). 코드 없음. | costume "ground" |
| 6 | 게임오버 | "GAME OVER" 배너, 평소 숨김. 게임상태=0 일 때 보임. | endless-runner 패턴 그대로 |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 살아남은 시간 단위(0.1초마다 +1) |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| VY | `varVY04` | 0 | 큐브의 수직 속도 |
| 스크롤속도 | `varScroll05` | 6 | 장애물 좌측 스크롤(px/tick). 시간 지날수록 가속 |
| 스폰주기 | `varSpawn06` | 0.55 | 장애물 스폰 인터벌(초). BPM ≈ 109 비트. 가속 시 짧아짐. |
| 점프이전키 | `varPrevJump07` | 0 | 점프 키 에지 디텍션용 |
| 패턴종류 | `varKind08` | 0 | 0=가시, 1=블록, 2=천장가시 |

큐브 sprite-local: 없음.
장애물 sprite-local: 없음.

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 가시스폰 | `brSpawnSpike02` | Stage 가 매 `스폰주기` 초마다, 패턴종류=0 인 경우 발신 |
| 블록스폰 | `brSpawnBlock03` | Stage 가 매 `스폰주기` 초마다, 패턴종류=1 인 경우 발신 |
| 천장스폰 | `brSpawnCeil04` | Stage 가 매 `스폰주기` 초마다, 패턴종류=2 인 경우 발신 |

> 세 종류 장애물 sprite 가 각자 독립 스폰되도록 broadcast 분리.

---

## 6. 메커닉 상세

### 6.1 큐브 (점프만)

매 틱(0.025s):

1. **점프 에지 디텍션**: `현재점프키 = (key "up arrow" pressed) OR (key space pressed)`
2. `if 현재점프키 = 1 AND 점프이전키 = 0 AND VY = 0` → `VY = 11` (땅이나 블록 위에 있어 VY=0 인 순간에만 점프)
3. `점프이전키 = 현재점프키`
4. **중력**: `VY = VY - 1.2`
5. **위치 갱신**: `change y by VY`
6. **블록 위 착지**: `if touching 블록 AND VY < 0` → `change y by 4` (블록 위로 한 칸 밀어올림) + `VY = 0` (다시 점프 가능 상태로 만듦)
   - 단순화: `if touching 블록`이면 일단 위로 밀어내며 `VY = 0`. 옆에서 부딪힐 경우는 큐브가 워낙 낮은 위치 + 짧은 점프라 거의 발생하지 않음. 블록 높이 30px, 큐브 size 50px.
7. **바닥 도착**: `if y < -130 → y = -130, VY = 0`
8. **즉사**: `if touching 가시 OR touching 천장가시 → 게임상태 = 0`
9. **최고기록**: `if 점수 > 최고기록 → 최고기록 = 점수`
10. wait 0.025

> 핵심 트릭: VY=11, 중력=-1.2 → 점프 정점 약 y = -130 + (11+9.8+8.6+...+0) ≈ -130 + 50 = -80 정도. 천장가시 y=+110 까지는 닿지 않음. 단, **블록 위에서 점프** 시: 출발 y ≈ -85, 정점 y ≈ -35. 여전히 천장가시 안 닿음. 천장가시는 *블록 두 번 점프* 같은 욕심 부릴 때만 위협이 됨.

### 6.2 장애물 스폰 (Stage)

`when receive 게임시작` forever (장애물 패턴):
```
repeat until 게임상태 = 0:
  패턴종류 = pick random 0 to 2
  if 패턴종류 = 0: broadcast 가시스폰
  else:
    if 패턴종류 = 1: broadcast 블록스폰
    else: broadcast 천장스폰
  wait 스폰주기
```

별도 forever (점수 누적 & 가속):
```
repeat until 게임상태 = 0:
  점수 = 점수 + 1
  if (점수 mod 80) = 0:
    스크롤속도 = 스크롤속도 + 1
    if 스폰주기 > 0.35:
      스폰주기 = 스폰주기 - 0.05
  wait 0.1
```

### 6.3 가시 (클론)

`when receive 가시스폰`:
- size=70, y=-130, x=260 → create clone

`when I start as clone`:
```
show
repeat until 게임상태 = 0:
  change x by (-1 * 스크롤속도)
  if x position < -260: delete this clone
  wait 0.025
delete this clone
```

### 6.4 블록 (클론)

동일하지만 y=-105.

### 6.5 천장가시 (클론)

동일하지만 y=+110. 크기는 size=70 (가시 뒤집힌 모양).

### 6.6 게임오버 / 재시작

endless-runner 와 동일. 배너 sprite 가 `wait_until 게임상태=1 → wait_until 게임상태=0 → show`. 깃발 다시 클릭 → 변수 리셋 → 새 게임. 큐브 sprite 에서 게임오버 시 pop 효과음.

---

## 7. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  게임상태 ← 1
  VY ← 0
  스크롤속도 ← 6
  스폰주기 ← 0.55
  점프이전키 ← 0
  패턴종류 ← 0
  broadcast 게임시작

when receive 게임시작:   # forever 1: 비트 스폰
  repeat until 게임상태 = 0:
    패턴종류 ← pick random 0 to 2
    if 패턴종류 = 0:
      broadcast 가시스폰
    else:
      if 패턴종류 = 1:
        broadcast 블록스폰
      else:
        broadcast 천장스폰
    wait 스폰주기

when receive 게임시작:   # forever 2: 점수 + 가속
  repeat until 게임상태 = 0:
    점수 ← 점수 + 1
    if (점수 mod 80) = 0:
      스크롤속도 ← 스크롤속도 + 1
      if 스폰주기 > 0.35:
        스폰주기 ← 스폰주기 - 0.05
    wait 0.1
```

### 큐브

```
when flag clicked:
  goto -150, -130
  size 70
  point in direction 90
  show

when receive 게임시작:
  VY ← 0
  점프이전키 ← 0
  goto -150, -130
  size 70
  repeat until 게임상태 = 0:
    # 점프 에지 디텍션 (VY=0 = 바닥 또는 블록 위 정지 상태)
    if ((key up arrow pressed) OR (key space pressed)) AND 점프이전키=0 AND VY=0:
      VY ← 11
    if (key up arrow pressed) OR (key space pressed):
      점프이전키 ← 1
    else:
      점프이전키 ← 0
    # 중력
    VY ← VY - 1.2
    change y by VY
    # 블록 위 착지 (touching → 위로 밀어내고 VY=0)
    if touching 블록:
      change y by 4
      VY ← 0
    # 바닥 클램프
    if y position < -130:
      goto x:-150 y:-130
      VY ← 0
    # 즉사 충돌
    if touching 가시: 게임상태 ← 0
    if touching 천장가시: 게임상태 ← 0
    # 최고기록
    if 점수 > 최고기록: 최고기록 ← 점수
    wait 0.025

when flag clicked:   # 게임오버 시 효과음
  wait until 게임상태 = 0
  play sound pop
```

### 가시

```
when flag clicked:
  hide
  size 70

when receive 가시스폰:
  goto (260, -130)
  switch costume "spike"
  create clone of _myself_

when I start as clone:
  show
  repeat until 게임상태 = 0:
    change x by (-1 * 스크롤속도)
    if x position < -260: delete this clone
    wait 0.025
  delete this clone
```

### 블록

```
when flag clicked:
  hide
  size 70

when receive 블록스폰:
  goto (260, -105)
  switch costume "block"
  create clone of _myself_

when I start as clone:
  show
  repeat until 게임상태 = 0:
    change x by (-1 * 스크롤속도)
    if x position < -260: delete this clone
    wait 0.025
  delete this clone
```

### 천장가시

```
when flag clicked:
  hide
  size 70

when receive 천장스폰:
  goto (260, 110)
  switch costume "ceil"
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

endless-runner 와 동일 (wait_until 게임상태=1 → wait_until 게임상태=0 → show).

---

## 8. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| 배경 | SVG (인라인) | 네온 다크. 위쪽 보라/남색 그라데이션, 아래쪽 진보라, 가로 그리드 라인 |
| 큐브 | SVG (인라인) | 50×50. 노란/하늘색 큐브 + 얼굴(점 두 개 + 입). rotationCenterX 25, rotationCenterY 25 |
| 가시 | SVG (인라인) | 40×30. 흰색/회색 삼각형 가시 3개 묶음. 위로 뾰족. rotationCenterX 20, rotationCenterY 15 |
| 블록 | SVG (인라인) | 40×30. 회색 블록 + 모서리 하이라이트. rotationCenterX 20, rotationCenterY 15 |
| 천장가시 | SVG (인라인) | 40×30. 가시 삼각형이지만 아래로 뾰족 (천장에서 내려옴). rotationCenterX 20, rotationCenterY 15 |
| 바닥 | SVG (인라인) | 480×30. 네온 띠 (자홍/시안 라인). rotationCenterX 240, rotationCenterY 15 |
| 게임오버 배너 | SVG (인라인) | "GAME OVER" + "장애물에 부딪혔어요" |
| pop.wav | WAV (assets/) | endless-runner/assets/pop.wav 복사. 게임오버 효과음 |

---

## 9. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과
2. `project.json` JSON 로드 OK
3. targets 수: 7 (Stage, 큐브, 가시, 블록, 천장가시, 바닥, 게임오버)
4. Stage 변수 8개(점수/최고기록/게임상태/VY/스크롤속도/스폰주기/점프이전키/패턴종류) 모두 등록
5. Broadcasts: 게임시작 / 가시스폰 / 블록스폰 / 천장스폰 4개
6. 자산: 7 SVG + 1 WAV(pop)
7. 큐브 sprite 의 `control_repeat_until` 안에:
   - `sensing_keypressed`("up arrow") 와 `sensing_keypressed`("space") 둘 다 존재
   - `data_setvariableto`(VY, 11) 점프 트리거 존재
   - `data_changevariableby`(VY, -1.2) 중력 존재
   - `motion_changeyby` (VY 사용) 존재
   - `sensing_touchingobject`("가시"), `sensing_touchingobject`("블록"), `sensing_touchingobject`("천장가시") 셋 다 존재
8. Stage 에 `when receive 게임시작` 핸들러 2개 이상
9. 가시·블록·천장가시 sprite 각자 `control_start_as_clone` 트리에 `motion_changexby` 와 `control_delete_this_clone` 존재
10. monitors 에 점수·최고기록 표시
11. 모든 자산 MD5 일치
12. 블록 카운트 250~360 범위

---

## 10. 빌드 카운트 예상

- Stage: ~55 블록 (init 8개 + 비트 스폰 forever (3분기) + 점수+가속 forever)
- 큐브: ~135 블록 (에지 디텍션 + 점프 + 중력 + 블록 착지 + 바닥 클램프 + 충돌 3종 + 최고기록 + 사운드)
- 가시: ~30 블록 (스폰 + 클론 스크롤)
- 블록: ~30 블록 (스폰 + 클론 스크롤)
- 천장가시: ~30 블록 (스폰 + 클론 스크롤)
- 바닥: ~5 블록 (정적)
- 게임오버: ~12 블록
- **총합 예상: 290~310 블록**

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **베이스**: `games/endless-runner/build.py` — 거의 그대로 카피.
- **차이 1**: 슬라이드 제거. 큐브는 점프만.
- **차이 2**: 장애물 2종(선인장/박쥐) → 3종(가시/블록/천장가시). Stage 의 if/else 가 3분기로 변형.
- **차이 3**: 점프 파라미터 변경. VY=9 → 11, 중력=-0.8 → -1.2 (더 빠른 점프).
- **차이 4**: 블록 위 착지 로직 추가 (`if touching 블록: change y by 4; VY=0`).
- **차이 5**: 점프 가능 조건 변경. endless-runner 는 `y < -129` 로 바닥 판정. geometry-dash 는 `VY = 0` (땅 또는 블록 위에 정지 상태)으로 일반화.
- **차이 6**: 스폰주기 0.55초 고정 시작(비트), 가속 임계는 매 80점.
- **차이 7**: SVG 자산 — 큐브(50×50 둥근 사각형), 가시(삼각형), 블록(회색 사각), 천장가시(역삼각형). 배경 네온 다크.

빌더는 endless-runner build.py 를 카피 후 다음만 바꾸면 됨:
1. SVG 6개 모두 교체 (배경/캐릭터/장애물 3종/바닥/게임오버 배너 텍스트만).
2. 변수 `장애물종류` → `패턴종류` 이름만 다름. 동일 ID 사용 가능 (`V_KIND`).
3. 점프 파라미터 (9→11, -0.8→-1.2) 변경.
4. 점프 가능 조건 `y<-129` → `VY=0` 으로 교체.
5. 슬라이드 블록(size 40/80 if/else) 제거.
6. 박쥐 충돌 → 가시/천장가시/블록 3분기 충돌. 블록은 즉사 X, 위로 밀어내기.
7. Stage 의 스폰 if/else (2분기) → 3분기 (가시/블록/천장).
8. broadcast 이름 변경 (선인장스폰→가시스폰, 박쥐스폰→블록스폰, 추가 천장스폰).
9. Sprite 추가: 천장가시 (새 SVG + 새 빌드 함수).

---

## 12. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (Geometry Dash 의 단순화)
- [x] 추상 학습 콘셉트 없음 (큐브=캐릭터, 가시=즉사, 블록=발판)
- [x] 즉시 이해되는 룰 (점프만 / 가시 닿으면 끝)
- [x] 시각적 위협감 (장애물 다가옴) + 도전감 (속도 가속)
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
- [x] Geometry Dash — 검증된 재미 메커닉 (10년 이상 인기, Scratch griffpatch 버전도 유명)
