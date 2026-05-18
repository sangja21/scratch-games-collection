# 두들 점프 (doodle-jump) — Plan

> 발판을 밟고 끝없이 위로 점프, 떨어지면 게임오버. 2009 Doodle Jump 클래식 메커닉의 Scratch 이식.
> 베이스 패턴: `alien-invasion` (클론 스폰/스폰퇴장) + 새로 작성하는 **카메라 스크롤** 패턴.
> 타깃: 초등학생. 학습 콘셉트 없음, 직관적 액션.

---

## 1. 한 줄 룰

화살표키 좌/우로 캐릭터를 이동, 자동 점프, 발판을 밟으면 위로 튕긴다. 화면 아래로 떨어지면 게임오버. 더 높이 올라간 만큼 점수.

---

## 2. 화면 / 좌표

- 무대 480×360 (Scratch 표준). 좌표: -240..240 / -180..180.
- 배경: 하늘색 그라데이션 + 옅은 구름. 가로 wrap을 시각적으로 강조하지는 않지만 의도 표현용.
- 모니터 좌상단: 점수 / 최고기록.

---

## 3. 스프라이트 (5개)

| 스프라이트 | 역할 | 비고 |
|------------|------|------|
| Stage | 전역 상태(점수·최고기록·게임상태·캐릭터 VY) + 게임 루프 호스트 | 발판 스폰 타이머 호스트 |
| `두들이` (player) | 화면 중앙 고정. y는 약간 위아래 진동만, 좌우 이동, 자동 중력+점프 처리. 좌↔우 wrap. | rotationStyle: left-right (방향 전환 모션) |
| `발판` (platform) | 클론 N개로 생성. 화면 어디든 자유 위치. 매 틱 카메라 스크롤량만큼 아래로 내려옴. 화면 아래로 사라지면 자기 클론 삭제. | 캐릭터가 위에서 내려와 접촉하면 BR_BOUNCE 방송 |
| `게임오버` | "GAME OVER" 배너, 평소 숨김. 게임상태=0 일 때만 보임. | 게임 시작(state=1) 대기 → 종료(state=0) 대기 → 표시 |
| `시작배너` (선택) | 화면 첫 표시 시 안내 (← → 이동, 떨어지면 끝). state=1로 바뀌면 사라짐. | 단순 |

> 5개로 운영. `시작배너`는 최소화(작은 안내문)로 처리하거나, 게임오버 배너에 안내문구를 통합해도 됨. 1차 빌드는 4개(Stage 제외)로 간다: 두들이 / 발판 / 게임오버.

---

## 4. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 누적 스크롤 거리 |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 (게임오버 시 갱신) |
| 게임상태 | `varState03` | 1 | 1=플레이, 0=게임오버 |
| VY | `varVY04` | 0 | 캐릭터 수직 속도(매 틱 중력 -1.0) |
| 카메라 | `varCam05` | 0 | 이번 틱의 스크롤량 (양수 = 모든 발판이 그만큼 아래로) |
| 시작Y | `varBaseY06` | -60 | 캐릭터 시작 y 좌표 (중앙 약간 아래) |

발판 sprite-local 변수:

| 변수명 | ID | 용도 |
|--------|----|------|
| 사용중 | `varPUsed07` | 1=활성 클론, 0=사용안함 (안전장치) |

---

## 5. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 가 초기화 끝나면 발신 |
| 발판생성 | `brSpawn02` | Stage 가 게임 시작 시 1회 (초기 발판 12개) |
| 발판추가 | `brAdd03` | 한 발판이 화면 아래로 사라질 때 → 새 발판 위쪽 생성 |
| 튕김 | `brBounce04` | 발판이 캐릭터와 접촉 + 캐릭터가 내려오는 중일 때 |
| 게임종료 | `brOver05` | (선택) 명시적 종료 신호. 1차는 게임상태=0 폴링으로 처리 |

---

## 6. 메커닉 상세

### 6.1 캐릭터 움직임 (두들이)

매 틱(약 0.025s, 40fps):

1. 좌/우 화살표 입력 → x ± 5.
2. **좌↔우 wrap**: x < -240 이면 x = 240, x > 240 이면 x = -240.
3. **VY 적용**: y += VY.
4. **중력**: VY -= 1.0. (점프 직후 VY≈+15 → 0 → 음수 진행)
5. **카메라 스크롤**:
   - 캐릭터 y > 0 (화면 중앙 위로 올라감) → `카메라 = y` 만큼, 캐릭터 y = 0 로 강제, **점수 += 카메라**, BR 없이 모든 발판이 자기 update 루프에서 카메라 값을 읽고 자기 y -= 카메라.
   - 그 외에는 카메라 = 0.
6. **낙사 체크**: y < -190 이면 `게임상태 = 0`, 게임오버.

> 캐릭터 y 좌표가 0 이상으로는 절대 안 올라가는 식. "캐릭터가 위로 올라간 만큼 모든 발판이 아래로 내려온다" 가 핵심.

### 6.2 발판 (platform 클론)

**초기 스폰(게임시작)**: 12개 클론 생성. y = -150, -120, -90, ... 30 (30 간격). x = random(-200..200).
- 첫 번째 클론(y=-150)은 캐릭터 바로 아래에 보장.

**각 클론 update 루프**:
- 매 틱 y -= 카메라.
- 캐릭터(두들이)에 닿았고 **VY < 0 (내려오는 중)** 이면 → `BR_BOUNCE` 방송.
- y < -190 이 되면 → `BR_ADD` 방송(새 발판 생성) + 자기 클론 삭제.

**새 발판 추가(BR_ADD)**:
- 빈 자리(원본 sprite)에서 `발판생성` 받았을 때와 동일한 단일 클론 생성: y = 180 (화면 상단), x = random(-200..200).

### 6.3 튕김(BR_BOUNCE)

Stage 가 받음 → VY = 15 (양수, 위로 튕김). (캐릭터 sprite 가 받아도 되지만 VY 가 Stage 변수이므로 Stage 에서 처리하는 게 깔끔.)

### 6.4 게임오버

캐릭터 sprite 가 매 틱 y < -190 체크 → 게임상태 = 0. 동시에 최고기록 < 점수 면 최고기록 = 점수.
게임오버 배너 sprite 가 `wait_until 게임상태=0` 으로 표시.

### 6.5 재시작

Scratch 의 기본 재시작은 깃발 다시 클릭. 별도 R 키는 1차 빌드 생략(요청에 없음).

---

## 7. 스프라이트별 블록 트리 (의사코드)

### Stage

```
when flag clicked:
  점수 ← 0
  게임상태 ← 1
  VY ← 0
  카메라 ← 0
  broadcast 게임시작
  broadcast 발판생성

when receive 튕김:
  VY ← 15

when receive 게임시작:
  # game-state polling for monitor; nothing else
```

### 두들이 (player)

```
when flag clicked:
  goto 0, -60
  size 60
  point in direction 90
  show

when receive 게임시작:
  VY ← 15        # 초기 점프
  repeat until 게임상태=0:
    # 좌우 이동 + wrap
    if key ←:
      change x by -5
      point in direction -90
    if key →:
      change x by 5
      point in direction 90
    if x < -240: set x to 240
    if x > 240:  set x to -240

    # VY 적용 + 중력
    change y by VY
    change VY by -1

    # 카메라 스크롤
    if y position > 0:
      카메라 ← y position
      set y to 0
      점수 ← 점수 + 카메라
    else:
      카메라 ← 0

    # 낙사
    if y position < -190:
      게임상태 ← 0
      if 점수 > 최고기록: 최고기록 ← 점수

    wait 0.025
```

### 발판 (platform)

```
when flag clicked:
  hide
  size 70

when receive 발판생성:
  # 12개 초기 클론
  set y(local var? no — 원본은 위치만 잡고 클론을 만든다)
  repeat 12:
    set x to (random -200..200)
    set y to (-150 + (loop_index * 30))      # 의사: 카운터 변수로 진행
    create clone of myself
    wait 0.01

when receive 발판추가:
  go to (random -200..200, 180)
  create clone of myself

when I start as clone:
  show
  repeat until 게임상태=0:
    change y by (-1 * 카메라)
    if touching 두들이 and VY < 0:
      broadcast 튕김
    if y position < -190:
      broadcast 발판추가
      delete this clone
    wait 0.025
  delete this clone
```

> 구현 노트: 12개를 만들 때 루프 카운터(스프라이트-로컬 var `자리Y`)를 -150 으로 시작해 30씩 증가시키면서 12회 반복. 마지막 클론 y = 180 근처.

### 게임오버 배너

```
when flag clicked:
  hide
  goto 0, 0
  size 100
  go to front

  wait until 게임상태=1     # 새 게임이 진짜 시작될 때까지 대기 (재시작 안전장치)
  wait until 게임상태=0
  show
```

---

## 8. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| 배경 | SVG | 하늘색 그라데이션 + 옅은 구름 3~4개 |
| 두들이 | SVG | 36×36, 둥근 몸체에 눈 두 개 + 작은 다리. 귀엽고 단순. left-right 회전용 |
| 발판 | SVG | 70×14, 연두색 둥근 막대 + 하이라이트 |
| 게임오버 배너 | SVG | "GAME OVER" + "최종 점수는 좌상단 확인" |
| pop.wav | WAV (assets/) | 발판 튕김 효과음 |

assets/ 에 둘 원본은 두들이 SVG / 발판 SVG / pop.wav 정도. 배경·배너는 build.py 인라인.

---

## 9. 검증 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과
2. `project.json` JSON 로드 OK
3. targets 수: 4 (Stage, 두들이, 발판, 게임오버)
4. Stage 변수 6개(점수/최고기록/게임상태/VY/카메라/시작Y) 모두 등록
5. Broadcasts: 게임시작/발판생성/발판추가/튕김 4개 (게임종료는 선택)
6. 두들이 sprite 의 control_repeat_until 안에 `motion_changexby`, `motion_changeyby`, `data_changevariableby`(VY 갱신), `motion_setx`(wrap) 모두 존재
7. 발판 sprite 의 `control_start_as_clone` 트리, 그 안에 `sensing_touchingobject`("두들이") + `operator_lt`(VY < 0) 결합한 if 가 존재
8. 발판 sprite 의 BR_ADD 핸들러가 `control_create_clone_of`("_myself_") 호출
9. 모든 자산 MD5 일치 (zip 안 파일명 ↔ assetId)
10. monitors 에 점수·최고기록 모니터 표시

---

## 10. 빌드 카운트 예상

- 총 블록 약 110~140개 (Stage 30 + 두들이 50 + 발판 35 + 게임오버 10).
- 변수 6 stage + 1 sprite-local.
- Broadcasts 4개.
- 자산 4 SVG + 1 WAV.
