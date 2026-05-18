# 헬리콥터 동굴 (helicopter-cave) — Plan

> 스페이스(또는 마우스)를 꾹 누르면 헬리콥터가 상승, 떼면 자유낙하. 좌우로 끝없이 스크롤되는 좁아지는 동굴(천장+바닥 막대)을 통과한다. 2002 Flash 클래식 "Helicopter Game" 의 메커닉.
> 베이스: `games/meteor-dodge/build.py` (클론 스폰/스폰퇴장/forever 패턴 + 충돌 게임오버 + 게임오버 배너) + `games/doodle-jump/build.py` (1버튼 점프 vy 누적 패턴). **차이점**: 헬리콥터는 x 고정, y 만 변화 / 동굴은 오른쪽→왼쪽 스크롤 / 천장+바닥 두 종류 클론 / 통과 가능 폭이 시간에 따라 좁아짐.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지(MEMORY.md → feedback-game-design 준수).

---

## 1. 한 줄 룰

스페이스 또는 마우스를 누르고 있는 동안 헬리콥터 상승, 떼면 하강. 천장·바닥·장애물에 닿으면 게임오버. 살아남은 시간이 점수.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- 배경: 어두운 동굴 (짙은 갈색/회색 그라데이션) + 천장/바닥에 어렴풋한 암벽 무늬.
- 헬리콥터: 화면 좌측 고정 x = -150. y 만 변화.
- 천장 막대 클론: y = 180 ~ 130 사이의 사각형. 화면 오른쪽(x=240+)에서 등장 → 왼쪽으로 스크롤 → x < -260 일 때 클론 삭제.
- 바닥 막대 클론: y = -180 ~ -130 사이의 사각형. 동일한 스크롤.
- 모니터 좌상단: 점수 / 최고기록.

---

## 3. 스프라이트 (5개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 + 막대 스폰 타이머 + 1초 타이머(점수+1) + 난이도 ramp(천장+바닥 두께 합 증가) | 게임시작 broadcast 발신 |
| 1 | 헬리콥터 | x=-150 고정. 스페이스/마우스 누르면 VY += 0.5, 안 누르면 VY -= 0.4. y += VY 매 틱. 천장·바닥·막대 접촉 시 게임상태=0. | rotationStyle: don't rotate. 코스튬 2개(rotor 회전 효과로 두 프레임 교대) |
| 2 | 천장막대 | 클론 무한 스폰. x=260 에서 등장, x -= 스크롤속도 매 틱. y = 180 - (천장두께/2). size 는 두께에 비례. | rotationStyle: don't rotate. costume "ceil" |
| 3 | 바닥막대 | 같은 메커닉, y = -180 + (바닥두께/2). costume "floor" | rotationStyle: don't rotate |
| 4 | 게임오버 | "GAME OVER" 배너, 평소 숨김. 게임상태=0 일 때만 보임. | meteor-dodge 패턴 그대로 |

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 생존 시간 (매 초 +1) |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 (게임오버 시 갱신) |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| VY | `varVY04` | 0 | 헬리콥터 수직 속도 |
| 천장두께 | `varCeilT05` | 40 | 현재 스폰할 천장 막대 두께 (px) |
| 바닥두께 | `varFloorT06` | 40 | 현재 스폰할 바닥 막대 두께 (px) |
| 스크롤속도 | `varScroll07` | 4 | 막대 좌측 스크롤 속도 (px/tick) |
| 스폰주기 | `varSpawn08` | 0.5 | 막대 스폰 인터벌(초). 시간 지날수록 약간 감소 |
| 경과틱 | `varTick09` | 0 | 초 단위 경과 타이머 (난이도 ramp 용) |

> 천장두께+바닥두께 합이 통과 공간을 결정한다. 합 80 으로 시작 → 시간 지남에 따라 합 180까지 증가(통과폭 360→180 으로 줄어듦).

헬리콥터 sprite-local 변수: 없음.
천장/바닥 막대 sprite-local 변수: 없음 (등장 시점에 stage 변수 천장두께/바닥두께 를 코스튬 크기로 즉시 반영).

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화 끝나면 발신 |
| 막대스폰 | `brSpawn02` | Stage 가 매 `스폰주기` 초마다 발신 → 천장막대 + 바닥막대 각각 클론 1개 생성 |

---

## 6. 메커닉 상세

### 6.1 헬리콥터 (1버튼 상승/낙하)

매 틱(0.025s):

1. **입력**: 스페이스 OR 마우스 다운 → VY = VY + 0.5 (상승 가속)
2. **자유낙하**: 누르지 않으면 → VY = VY - 0.4 (하강 가속)
3. **속도 clamp**: -8 ≤ VY ≤ 8 (너무 빠르지 않게)
4. **위치 갱신**: y = y + VY
5. **천장 충돌**: y > 175 → 게임상태 = 0
6. **바닥 충돌**: y < -175 → 게임상태 = 0
7. **막대 충돌**: touching 천장막대 OR touching 바닥막대 → 게임상태 = 0
8. 최고기록 갱신 (점수 > 최고기록 이면)
9. wait 0.025

> doodle-jump 의 vy 패턴과 동일. 단지 점프 트리거가 한 번이 아니라 "누르고 있는 동안 계속" 으로 바뀐 것뿐.

### 6.2 막대 스폰 (Stage)

`when receive 게임시작` 의 forever 루프:

```
repeat until 게임상태 = 0:
  broadcast 막대스폰   # 천장+바닥 둘 다 받음
  wait 스폰주기
```

### 6.3 천장 막대 (클론)

`when receive 막대스폰`:
- goto (260, 180 - 천장두께/2)  # 화면 우측 + y=상단에서 두께만큼 아래
- size = 천장두께 (코스튬은 viewBox 100×100 정사각형 → size 가 곧 px 두께)
- 잠깐 무작위 ±10 변동 (다음 클론과 자연스럽게 이어지지 않도록 살짝 들쭉날쭉)
- create clone of myself

`when I start as clone`:
```
show
repeat until 게임상태 = 0:
  change x by (-1 * 스크롤속도)
  if x position < -260: delete this clone
  wait 0.025
delete this clone
```

### 6.4 바닥 막대 (클론)

천장과 거의 동일. 다른 점:
- goto (260, -180 + 바닥두께/2)
- costume "floor"
- size = 바닥두께

### 6.5 난이도 ramp (Stage 별도 forever)

```
repeat until 게임상태 = 0:
  wait 1
  경과틱 = 경과틱 + 1
  점수 = 점수 + 1     # 매 초 점수 +1
```

별도 forever (3초마다 두께 +3씩, 최대 90까지):
```
repeat until 게임상태 = 0:
  wait 3
  if 천장두께 < 90: 천장두께 = 천장두께 + 3
  if 바닥두께 < 90: 바닥두께 = 바닥두께 + 3
```

> 시작: 천장40 + 바닥40 = 80px 차단 → 통과폭 280px (충분히 여유)
> 약 90초 후: 천장90 + 바닥90 = 180px 차단 → 통과폭 180px (헬리콥터 자체가 ~45px이므로 빠듯)

### 6.6 게임오버 / 재시작

게임오버 배너 sprite 가 `wait_until 게임상태=1 → wait_until 게임상태=0 → show` (meteor-dodge 동일).
깃발 다시 클릭 → 모든 변수 리셋 → 새 게임.

---

## 7. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  게임상태 ← 1
  VY ← 0
  천장두께 ← 40
  바닥두께 ← 40
  스크롤속도 ← 4
  스폰주기 ← 0.5
  경과틱 ← 0
  broadcast 게임시작

when receive 게임시작:   # forever 1: 막대 스폰
  repeat until 게임상태 = 0:
    broadcast 막대스폰
    wait 스폰주기

when receive 게임시작:   # forever 2: 1초 타이머 + 점수
  repeat until 게임상태 = 0:
    wait 1
    경과틱 ← 경과틱 + 1
    점수 ← 점수 + 1

when receive 게임시작:   # forever 3: 3초마다 두께 증가 (난이도 ramp)
  repeat until 게임상태 = 0:
    wait 3
    if 천장두께 < 90: 천장두께 ← 천장두께 + 3
    if 바닥두께 < 90: 바닥두께 ← 바닥두께 + 3
```

### 헬리콥터

```
when flag clicked:
  goto -150, 0
  size 60
  point in direction 90
  show

when receive 게임시작:
  VY ← 0
  goto -150, 0
  repeat until 게임상태 = 0:
    # 1버튼 입력 (꾹 누르기)
    if (key space pressed) OR (mouse down):
      VY ← VY + 0.5
    else:
      VY ← VY - 0.4
    # VY clamp
    if VY > 8:  VY ← 8
    if VY < -8: VY ← -8
    # 위치 갱신
    change y by VY
    # 천장/바닥 hard limit (충돌 + 즉시 게임오버)
    if y position > 175:
      게임상태 ← 0
    if y position < -175:
      게임상태 ← 0
    # 막대 충돌
    if touching 천장막대 OR touching 바닥막대:
      게임상태 ← 0
    # 최고기록
    if 점수 > 최고기록: 최고기록 ← 점수
    wait 0.025
```

### 천장막대

```
when flag clicked:
  hide
  size 100

when receive 막대스폰:
  # y = 180 - 천장두께/2  →  바형이 화면 최상단에 붙음
  goto (260, 180 - (천장두께 / 2))
  switch costume "ceil"
  set size to 천장두께   # SVG viewBox 100×100 → size = px 두께
  create clone of _myself_

when I start as clone:
  show
  repeat until 게임상태 = 0:
    change x by (-1 * 스크롤속도)
    if x position < -260: delete this clone
    wait 0.025
  delete this clone
```

### 바닥막대

```
when flag clicked:
  hide
  size 100

when receive 막대스폰:
  goto (260, -180 + (바닥두께 / 2))
  switch costume "floor"
  set size to 바닥두께
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
| 배경 | SVG (인라인) | 짙은 동굴 — 어두운 갈색/회색 그라데이션 + 어렴풋한 암벽 점 |
| 헬리콥터 | SVG (인라인) | 60×40 정도. 노란/빨강 본체 + 검은 회전날개. rotationCenterX 30, rotationCenterY 20 |
| ceil | SVG (인라인) | 100×100 정사각형. 짙은 회색 암석. 위쪽 가장자리(y=0 근처)에 거친 텍스처, 아래쪽은 매끈. |
| floor | SVG (인라인) | 100×100 정사각형. 짙은 갈색 암석. 아래쪽 거친 텍스처, 위쪽 매끈. |
| 게임오버 배너 | SVG (인라인) | 검은 배너 "GAME OVER" + "동굴에 부딪혔어요" |
| pop.wav | WAV (assets/) | meteor-dodge 의 pop.wav 복사. 게임오버 효과음 |

assets/ 폴더에 둘 외부 파일: `pop.wav` 하나. 나머지 SVG 는 build.py 인라인.

> SVG size 매핑: viewBox 100×100 → Scratch size 100 = 100px 너비/높이. size = N 으로 두께 N px 의 정사각형. **하지만 막대는 가로로 길게 보이게 하려면 SVG 가로를 더 길게 (예: 100×100 viewBox 안에 가로 100 세로 100 정사각형이면 size=40 → 40×40 정사각형)**.
>
> 해결: 막대 SVG 를 viewBox 100×100 정사각형 그대로 두고, size=두께 로 정사각 두께 막대. 가로폭이 짧으면 다음 막대와 사이 간격이 너무 벌어진다. → 스폰 주기를 짧게(0.5초 × 스크롤4 = 0.5초당 2px 진행하므로 거리 차이 ~120px = size 100 정사각형이면 충분히 겹쳐서 천장이 끊김 없이 보임).
>
> 실용 결정: 막대 viewBox 를 **120 가로 × 100 세로** 로 두고, `set size to (두께)` 가 세로 = 두께 가 되도록 한다. Scratch 의 size 는 실제로 "원래 크기의 N%". viewBox 100×100 정사각형, 원본 100×100px. size=40 → 40×40px. 두께(세로) = 40 으로 매칭됨. 가로폭이 부족하면 천장이 점 무더기로 보일 수 있음. → 그래서 **막대 가로폭을 100 으로 두고, 스폰주기 × 스크롤속도 ≈ 100 px 진행이 되도록** 0.5초 × 4 = 진행 2px… 잠깐. 0.5초당 (40fps × 0.025s × 4px) = 80px 진행. 막대 가로 100 보다 약간 좁아 끊김 없이 이어진다.
>
> 최종: 막대 SVG viewBox 100×100, size=두께(40~90), 스폰주기 0.5초, 스크롤속도 4 → 막대 사이 진행거리 80px < 막대폭 100px = 연속해서 보임. OK.

---

## 9. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과
2. `project.json` JSON 로드 OK
3. targets 수: 5 (Stage, 헬리콥터, 천장막대, 바닥막대, 게임오버)
4. Stage 변수 9개(점수/최고기록/게임상태/VY/천장두께/바닥두께/스크롤속도/스폰주기/경과틱) 모두 등록
5. Broadcasts: 게임시작 / 막대스폰 2개
6. 천장막대 sprite 코스튬 1개(ceil), 바닥막대 sprite 코스튬 1개(floor)
7. 자산: 5 SVG(배경/헬리콥터/ceil/floor/게임오버) + 1 WAV(pop)
8. 헬리콥터 sprite 의 `control_repeat_until` 안에:
   - `sensing_keypressed`("space") 존재
   - `sensing_mousedown` 존재
   - `operator_or` 로 둘을 결합
   - `data_changevariableby`(VY, 0.5) + `data_changevariableby`(VY, -0.4) 둘 다 존재
   - `motion_changeyby` (VY 사용) 존재
   - `sensing_touchingobject`("천장막대"), `sensing_touchingobject`("바닥막대") 둘 다 존재
9. Stage 에 `when receive 게임시작` 핸들러 3개 이상 (스폰 / 1초 타이머 / 3초 ramp)
10. 천장막대 sprite 의 `control_start_as_clone` 트리에 `motion_changexby`(스크롤속도 사용) 와 `control_delete_this_clone` 모두 존재
11. 바닥막대 sprite 도 동일 구조
12. monitors 에 점수·최고기록 모니터 표시
13. 모든 자산 MD5 일치 (zip 안 파일명 ↔ assetId)
14. 블록 카운트 200~320 범위

---

## 10. 빌드 카운트 예상

- Stage: ~50 블록 (init + 3개 forever 핸들러)
- 헬리콥터: ~95 블록 (1버튼 입력 + VY clamp×2 + 위치 갱신 + 천장/바닥 한계 + 막대 충돌×2 + 최고기록 + 사운드)
- 천장막대: ~30 블록 (스폰 + 클론 forever)
- 바닥막대: ~30 블록 (동일)
- 게임오버: ~12 블록
- **총합 예상: 215~250 블록** (★★★ 범위)

---

## 11. 재사용 코드 (builder 가 참조할 부분)

- **VY 누적 패턴**: `games/doodle-jump/build.py` — vy 누적 + 매 틱 change y by vy. helicopter-cave 는 점프 트리거가 없고 꾹 누르기만 다름.
- **클론 스폰/스폰퇴장 + 게임오버 배너**: `games/meteor-dodge/build.py` — 거의 동일 패턴. 운석=막대 로 매핑하면 됨.
- **충돌 → 게임상태=0 + 최고기록 갱신 + pop 사운드**: `games/meteor-dodge/build.py` 의 ship 충돌 블록과 동일.
- **3개 forever 병렬**: `games/meteor-dodge/build.py` 의 stage 패턴.
- **monitors / project assemble**: meteor-dodge 그대로 사용.

빌더는 meteor-dodge 의 build.py 를 거의 그대로 카피한 뒤 다음만 바꾸면 됨:
1. ship → helicopter (x 고정, VY 누적, 1버튼 입력)
2. meteor → 천장막대 + 바닥막대 (수직 낙하 → 수평 스크롤, 두 스프라이트로 분리)
3. 운석크기/속도 분기 제거 (대신 size = 두께)
4. 변수 9개로 갱신

---

## 12. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (1버튼, 꾹 누르기만)
- [x] 추상 학습 콘셉트 없음 (헬리콥터 = 헬리콥터, 동굴 = 동굴)
- [x] 즉시 이해되는 룰 (누르면 위, 떼면 아래, 부딪히면 끝)
- [x] 시각적 위협감 (동굴이 점점 좁아짐) + 점진적 난이도 ramp
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭)
- [x] 2002 Helicopter Game 클래식 — 검증된 재미 메커닉
