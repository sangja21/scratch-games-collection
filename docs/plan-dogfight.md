# 도그파이트 (dogfight) — Plan

> 두 비행기 1대1 공중전. 좌/우 화살표로 회전하면서 항상 일정 속도로 전진하는 비행기. 스페이스 = 전방 기관총 발사. AI 적기는 플레이어를 쫓아 회전하면서 가끔 사격. **정면 사격이 가장 강함**(상대 후방을 잡아야 유리하고 후방을 내주면 불리). 한 라운드만, 적기 격추 → 승리 / 플레이어 체력 0 → 패배.
> 베이스: `games/asteroids/build.py` 의 회전+전진+화면wrap 패턴 + `games/tank-battle/build.py` 의 사격 클론 풀 + 적 AI(추적+사격). **차이점**: asteroids 의 관성(VX/VY) 제거, 비행기는 매 틱 일정 속도(3 steps)로 전진. 분열·라운드 없음.
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션.

## 1. 컨셉 / 메커닉

- 톱다운 하늘 시점, 480×360 무대. 배경 = 밝은 푸른 하늘 + 가벼운 구름.
- **플레이어 조작**:
  - 왼쪽 화살표 = 좌회전 (틱당 −4°)
  - 오른쪽 화살표 = 우회전 (틱당 +4°)
  - 항상 전진 (틱당 move 3, **관성 없음**)
  - 스페이스 = 기관총 발사 (전방 직선, 쿨다운 0.25초)
- **화면 wrap**: 비행기·총알 모두. x>240→−240, x<−240→240, y>180→−180, y<−180→180.
- **체력**:
  - 플레이어 체력 = 3, 적 체력 = 3.
  - 자기 총알에 닿으면 안 됨 → 총알은 자기 발사자를 무시. 단순화: 플레이어 총알 ↔ 적 비행기, 적 총알 ↔ 플레이어 비행기 만 충돌 체크.
- **승패**:
  - 적 체력 = 0 → 승리 배너
  - 플레이어 체력 = 0 → 패배 배너
  - 라운드 진행 없음. 한 판 끝.
- **적 AI**:
  - 매 틱 플레이어 방향(point towards 플레이어)을 계산하고, 자기 현재 방향과의 차이로 회전 결정:
    - 단순화: 매 틱 `point towards 플레이어` 한 뒤 추가로 random(-15..15) 만큼 회전(예측 불가성). → 너무 정확하면 어려움.
  - 추가로 매 틱 `move 2.4` (플레이어 3 보다 약간 느림 → 플레이어가 따라잡을 수 있음).
  - 매 1~2초마다 (랜덤 쿨다운 = 0.8~2.0초) 전방 사격.
- **사격**:
  - 플레이어 총알: 발사 시점 플레이어 위치/방향에서 클론 생성, move 9 per tick, 수명 50틱(≈1.5초), wrap O. 적 비행기 닿으면 적 체력 −1 + 자기 소멸.
  - 적 총알: 발사 시점 적 위치/방향에서 클론 생성, move 7 per tick, 수명 50틱, wrap O. 플레이어 닿으면 플레이어 체력 −1 + 자기 소멸.
- **격추 시각 효과**:
  - 적이 격추되면(체력=0) 적 스프라이트 0.5초 깜빡 후 hide. `게임상태=2`(승리) 마킹.
  - 플레이어가 격추되면 비행기 hide. `게임상태=0`(패배) 마킹.
- **시작**: 깃발 클릭 → 1초 카운트("READY!") 없이 즉시 시작 (간단). 플레이어는 (−150, 0) direction=90(오른쪽), 적은 (150, 0) direction=−90(왼쪽). 서로 마주보기.

## 2. 화면 레이아웃

```
       ┌────────────────────────────────────┐
       │  파란 하늘 + 옅은 구름                │
       │                                      │
       │          ☁                            │
       │                                      │
       │    ✈ (플레이어, 오른쪽 향함)         │
       │                          ✈ (적, 왼쪽) │
       │                                      │
       │              ☁                        │
       │   ← → 회전, 스페이스 = 사격            │
       └────────────────────────────────────┘
좌상단 변수 모니터: 내체력 / 적체력
```

## 3. 스프라이트

| # | 이름 | 역할 | 코스튬 |
|---|------|------|--------|
| 0 | Stage | 하늘 배경 + 전역 변수 + 시작/종료 감시 | bg.svg |
| 1 | 플레이어기 | 회전+전진+발사+피격 | plane_blue.svg |
| 2 | 적기 | 추적 AI+전진+발사+피격 | plane_red.svg |
| 3 | 플레이어총알 | 클론, 전방 직선, wrap, 적기 격중 시 소멸 | bullet_blue.svg |
| 4 | 적총알 | 클론, 전방 직선, wrap, 플레이어 격중 시 소멸 | bullet_red.svg |
| 5 | 승리배너 | 적 격추 시 표시 | win.svg |
| 6 | 패배배너 | 플레이어 격추 시 표시 | lose.svg |

총 7 스프라이트 (Stage 포함).

## 4. 변수 (Stage 전역)

| 한국어 | ID | 초기값 | 의미 |
|--------|----|--------|------|
| 내체력 | varPHP01 | 3 | 플레이어 체력 |
| 적체력 | varEHP02 | 3 | 적 체력 |
| 게임상태 | varState03 | 1 | 1=진행, 0=패배, 2=승리 |
| 플쿨다운 | varPCD04 | 0 | 플레이어 발사 쿨다운 |
| 적쿨다운 | varECD05 | 30 | 적 발사 쿨다운 (틱 단위, 처음 약간 여유) |
| 플총X | varPBX06 | 0 | 플레이어 총알 스폰 X |
| 플총Y | varPBY07 | 0 | 플레이어 총알 스폰 Y |
| 플총방향 | varPBDir08 | 90 | 플레이어 총알 스폰 방향 |
| 적총X | varEBX09 | 0 | 적 총알 스폰 X |
| 적총Y | varEBY10 | 0 | 적 총알 스폰 Y |
| 적총방향 | varEBDir11 | -90 | 적 총알 스폰 방향 |

✱ 변수 11개.

## 5. 방송 (broadcasts)

| 한국어 | ID | 트리거 |
|--------|----|--------|
| 게임시작 | brStart01 | 깃발 클릭 후 초기화 직후 |
| 플사격 | brPFire02 | 플레이어 스페이스 → 플총알 클론 |
| 적사격 | brEFire03 | 적 쿨다운 0 → 적총알 클론 |

## 6. 스프라이트별 블록 흐름

### Stage

1. **깃발 클릭** → 변수 초기화 (내체력=3, 적체력=3, 게임상태=1, 플쿨다운=0, 적쿨다운=30) → wait 0.5 → broadcast `게임시작`.
2. **forever (쿨다운 카운터)**:
   - if 플쿨다운 > 0 → 플쿨다운 −1
   - if 적쿨다운 > 0 → 적쿨다운 −1
   - wait 0.04 (≈25fps tick)

### 플레이어기

1. **깃발 클릭** → 보이기, size 60, 위치 (−150, 0), 방향 90, 회전스타일=all around.
2. **forever (조작 + 전진 + wrap)** :
   - if left arrow → turn ccw 4
   - if right arrow → turn cw 4
   - if 게임상태=1: move 3 (관성 X, 일정 속도)
   - wrap (x>240→−240 등 4개)
   - wait 0.03
3. **forever (사격)**:
   - if space pressed AND 플쿨다운=0 AND 게임상태=1:
     - 플총X = self x, 플총Y = self y, 플총방향 = self direction
     - play pop @ pitch 200
     - broadcast `플사격`
     - 플쿨다운 = 6 (≈0.25초)
   - wait 0.04
4. **forever (피격 감시)**:
   - if (touching 적총알) AND 게임상태=1:
     - 내체력 −1
     - play pop @ pitch -200
     - 잠깐 색깔 효과(ghost 50 → 0.1초 → 0) — 단순화: skip
     - if 내체력 ≤ 0:
       - 게임상태 = 0
       - hide
     - wait 0.3 (무적 시간)
   - wait 0.05

### 적기

1. **깃발 클릭** → 보이기, size 60, 위치 (150, 0), 방향 −90, 회전스타일=all around.
2. **forever (AI 회전 + 전진 + wrap)**:
   - if 게임상태=1:
     - point towards 플레이어기
     - turn cw (random −15..15) — 약간 부정확
     - move 2.4
     - wrap (x>240→−240 등 4개)
   - wait 0.04
3. **forever (사격)**:
   - if 적쿨다운=0 AND 게임상태=1:
     - 적총X = self x, 적총Y = self y, 적총방향 = self direction
     - play pop @ pitch 100
     - broadcast `적사격`
     - 적쿨다운 = random(20..50) (≈0.8~2.0초)
   - wait 0.05
4. **forever (피격 감시)**:
   - if (touching 플레이어총알) AND 게임상태=1:
     - 적체력 −1
     - play pop @ pitch -100
     - if 적체력 ≤ 0:
       - 게임상태 = 2
       - hide
     - wait 0.3 (무적)
   - wait 0.05

### 플레이어총알

1. **깃발 클릭** → 숨김, 크기 60, 회전스타일=all around.
2. **plFire 받으면** → create clone of myself.
3. **클론으로 시작**:
   - 위치 (플총X, 플총Y), 방향 = 플총방향, 보이기.
   - repeat 50:
     - move 9
     - wrap (x>240→−240 등 4개)
     - if touching 적기: hide → delete this clone (stop)
     - wait 0.02
   - hide → delete this clone

### 적총알

1. **깃발 클릭** → 숨김, 크기 60, 회전스타일=all around.
2. **adFire 받으면** → create clone of myself.
3. **클론으로 시작**:
   - 위치 (적총X, 적총Y), 방향 = 적총방향, 보이기.
   - repeat 50:
     - move 7
     - wrap (4개)
     - if touching 플레이어기: hide → delete this clone (stop)
     - wait 0.02
   - hide → delete this clone

### 승리배너

- 깃발 → hide + goto (0,0) + size 100 + front
- wait until 게임상태=1 → wait until 게임상태=2 → show

### 패배배너

- 깃발 → hide + goto (0,0) + size 100 + front
- wait until 게임상태=1 → wait until 게임상태=0 → show

## 7. 사운드

- **플레이어 사격**: pop @ pitch 200
- **적 사격**: pop @ pitch 100
- **플레이어 피격**: pop @ pitch -200
- **적 피격**: pop @ pitch -100

`assets/pop.wav` 는 asteroids 에서 복사.

## 8. 자산

- `bg.svg` — 하늘 배경 (#9CC8F0 → #6FA8E2 그라데이션 + 흰 구름 4~5개)
- `plane_blue.svg` — 파란 복엽기(WW1 풍), 위쪽이 정면(direction 0 기준). 회전스타일 all around 이므로 cockpit 위쪽이 노즈.
- `plane_red.svg` — 빨간 복엽기, 같은 모양 색만 다르게.
- `bullet_blue.svg` — 작은 청록색 탄
- `bullet_red.svg` — 작은 주황색 탄
- `win.svg` — "YOU WIN!" 검은 배너 + 파란 테두리
- `lose.svg` — "YOU LOSE…" 검은 배너 + 빨간 테두리
- `pop.wav` — 공용 사운드

## 9. 재사용 가능한 코드

- `asteroids/build.py`: 회전+wrap+사격 클론, 키 입력 패턴, 게임오버 배너 패턴.
- `tank-battle/build.py`: 적 AI(point towards + 약간 jitter) 패턴, 쿨다운 변수 패턴, 체력 변수 변경.
- 헬퍼(`md5_bytes/num/text_lit/slot/mk/gen/chain/make_helpers`, `sin_of/cos_of`) 전부 복제.

## 10. 예상 블록 카운트

- Stage: ~25 블록 (init + cd counter forever)
- 플레이어기: ~95 블록 (조작+전진+wrap forever + 사격 forever + 피격 forever)
- 적기: ~85 블록 (AI+전진+wrap forever + 사격 forever + 피격 forever)
- 플총알: ~50 블록 (init + clone start with wrap + lifetime)
- 적총알: ~50 블록
- 승리배너: ~12 블록
- 패배배너: ~12 블록
- **총합 예상: 320~360 블록**

## 11. 검증 체크리스트

- [ ] zip 열림, project.json 파싱 성공
- [ ] 자산 8종 (7 SVG + 1 WAV) 존재
- [ ] Stage 변수 11개, 방송 3개
- [ ] 스프라이트 7개 (Stage / 플레이어기 / 적기 / 플레이어총알 / 적총알 / 승리배너 / 패배배너)
- [ ] 블록 280~420 범위
- [ ] 좌/우 화살표 회전 (4도), 항상 전진(move 3), 스페이스 발사
- [ ] 적 AI: motion_pointtowards + 회전 jitter + move 2.4
- [ ] 적 자동 사격 (적쿨다운 0 시 broadcast)
- [ ] 화면 wrap (x>240 → -240 점프) 블록이 플레이어/적/플총알/적총알 모두에 존재
- [ ] 체력 변수(내체력, 적체력) 변경 블록 존재
- [ ] 적체력 ≤ 0 → 게임상태=2 (승리), 내체력 ≤ 0 → 게임상태=0 (패배)
- [ ] 디자인: 파란 하늘 (혐오/무서움 X, 초등학생 친화)
