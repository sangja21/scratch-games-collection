# 지아이조 (gi-joe) — Plan

> 옆보기 **엄폐 사격**. 지아이조 한 명이 몰려오는 적 병사를 각도를 올려 엄폐 너머로 쏜다. 제목은 지아이조.
> 포트리스(턴제·지형 구덩이)는 **폐기**. 실시간 각도 사격만 가져온다. **점프 없음.**
> 베이스: `games/rogue-knight/build.py`(←→ · VY/중력 · 바닥 클램프 · Z/X 입력) + `games/bomb-squad/build.py`(클론 스포너 · `복제됨` 가드 · 탄 상한 · 합성 WAV).
> 스크롤 없음(트레드밀). 높은 칸은 벽=엄폐. 지형 파괴·차량 탑승·비행적 없음(v2).
> ★★★☆☆.

- **주제**: 엄폐 사격
- **카테고리**: 액션
- **난이도**: ★★★☆☆
- **폴더**: `games/gi-joe/`
- **출력 파일**: `지아이조.sb3`
- **빌드**: `python3 games/gi-joe/build.py`

---

## 1. 게임 한 줄

지아이조 한 명으로 왼쪽 전선을 지킨다. `←→` 이동, `↑↓` 각도, **space 차지 발사**(짧게=약, 길게=강), **X 수류탄**. 체력 5. 높은 칸은 엄폐. 체력 0이면 게임오버.

---

## 2. 화면 레이아웃 (480×360)

```
 (-240,180)                                            (240,180)
   ┌──────────────────────────────────────────────────────┐
   │ ⭐점수  ❤️체력  WAVE                                   │
   │                                                      │
   │  지아이조▶  ●●●               적  적                    │  Z 직선탄
   │     ⬤ (수류탄 포물선)          적 →                   │  X 수류탄
   │████████████████████████████████████████ 지면          │  바닥Y
   │  ←→이동  ↑↓조준  space차지발사  X수류탄                │
   └──────────────────────────────────────────────────────┘
```

- 플레이어 x 클램프: −200 ~ 60 (왼쪽~중앙).
- 적 스폰 x ≈ 230, 왼쪽으로 이동. y = 바닥Y.
- 예고선 없음. 스크롤·카메라 없음.

---

## 3. 스프라이트

| # | 이름 | 역할 | 코스튬 | 초기 |
|---|------|------|--------|------|
| 0 | Stage | 사막 전선 배경 + 핸들 초기화 + 스폰 루프 | `bg` | — |
| 1 | 지형 | 칸 스탬프 | `tile` | 숨김 |
| 2 | 지아이조 | 이동·조준·방패·사격·장전·수류탄 | `idle`, `reload` | (−140, 바닥Y) |
| 3 | 총구 | 발사방향을 가리키는 총+조준선 | `gun` | 숨김 |
| 4 | 총알 | 원본 숨김. `발사` → 각도 직선 클론 | `bullet` | 숨김 |
| 5 | 수류탄 | 원본 숨김. `수류탄` → 포물선 클론 | `nade`, `boom` | 숨김 |
| 6 | 적 | 원본 숨김. 돌격/사수, 엄폐 조준 | `walker`, `shooter`, `boom` | 숨김 |
| 7 | 적탄 | 사수가 쏘는 탄 (atan 조준) | `ebullet` | 숨김 |
| 8 | 방패 | space 동안 앞에 붙음 | `shield` | 숨김 |
| 9 | 배너 | 게임오버 | `gameover` | 숨김 |

타깃 **10개** (Stage 포함). 게임상태 1=플레이, 2=오버, 3=웨이브 정지.

---

## 4. 사운드 (합성, orphan 0)

| 함수 | 이름 | 등록 | 트리거 |
|------|------|------|--------|
| `synth_fire` | fire | 총알 | 묵직한 발사 |
| `synth_nade` | nade | 수류탄 | 투척 |
| `synth_boom` | boom | 수류탄 | 착탄 |
| `synth_pop` | pop | 적 | 처치 |
| `synth_click` | click | 지아이조 | 빈 탄창 / 방패 들기 / 장전 끝 |
| `synth_reload` | reload | 지아이조 | C 장전 시작 (찰칵 찰칵) |
| `synth_hurt` | hurt | 지아이조 | 피격 |
| `synth_gameover` | gameover | 배너 | 오버 |

---

## 5. 변수

### 5.1 핸들 (Stage 깃발만 초기화)

| 한국어 | ID | 기본 |
|--------|----|------|
| 이동속도 | `varMove01` | 4 |
| 점프력 | `varJump02` | 11 |
| 중력 | `varGrav03` | −1.1 |
| 바닥Y | `varFloor04` | −100 |
| 연사간격 | `varFireGap05` | 0.12 |
| 탄속 | `varShotSpd06` | 11 |
| 최대탄수 | `varMaxShot07` | 8 |
| 수류탄력 | `varNadeSpd08` | 6 |
| 수류탄띄움 | `varNadeUp09` | 8 |
| 수류탄쿨 | `varNadeCD10` | 1.2 |
| 적속도 | `varEnSpd11` | 1.3 |
| 스폰간격 | `varSpawn12` | 1.2 |
| 최대적수 | `varMaxEn13` | 6 |
| 최대체력 | `varMaxHP14` | 6 |
| 적공격 | `varEnAtk15` | 1 |
| 무적시간 | `varIFrame16` | 1.0 |
| 난이도증가율 | `varRamp17` | 0.05 |
| 웨이브킬 | `varWaveKills73` | 16 |
| 총알높이 | `varMuzzleY19` | 24 |
| 총구앞 | `varMuzzleF20` | 16 |
| 탄히트범위 | `varShotRad21` | 22 |
| 수류탄범위 | `varNadeRad22` | 100 |
| 장벽넘기 | `varBarHop23` | 26 |
| 사수확률 | `varShootP24` | 35 |
| 뒤쪽확률 | `varBackP25` | 28 |
| 사정거리 | `varRange26` | 110 |
| 적연사간격 | `varEFireG27` | 1.1 |
| 적탄속 | `varEShotS28` | 7 |
| 최대적탄 | `varMaxESh29` | 4 |
| 칸크기 | `varCellW30` | 24 |
| 칸수 | `varCellN31` | 20 |
| 탄창 | `varMag32` | 6 |
| 재장전시간 | `varReloadT33` | 0.8 |
| 포탄수명 | `varBallLife34` | 70 |
| 조준속도 | `varAimStep35` | 3 |

### 5.2 진행 (전역)

| 한국어 | ID | 기본 |
|--------|----|------|
| 게임상태 | `varState40` | 1 |
| 점수 | `varScore41` | 0 |
| 체력 | `varHP42` | 5 |
| 웨이브 | `varWave43` | 1 |
| 탄수 | `varShotN44` | 0 |
| 적수 | `varEnN45` | 0 |
| 처치수 | `varKills46` | 0 |
| 바라봄 | `varFacing47` | 90 |
| 수류탄쿨남은 | `varNadeT48` | 0 |
| VY | `varVY49` | 0 |
| 점프이전키 | `varPrevJ50` | 0 |
| 무적타이머 | `varIFrmT51` | 0 |
| 수류탄수 | `varNadeN52` | 0 |
| 탄히트X | `varShotHitX56` | 0 |
| 수류탄히트X | `varNadeHitX57` | 0 |
| 플레이어X | `varPlayerX58` | -140 |
| 적탄수 | `varEShotN59` | 0 |
| 적탄X | `varEShotX60` | 0 |
| 적탄Y | `varEShotY61` | 0 |
| 적탄방향 | `varEShotDir62` | -90 |
| 남은탄 | `varAmmo63` | 6 |
| 재장전중 | `varReloading64` | 0 |
| 재장전남은 | `varRelLeft65` | 0 |
| 방패중 | `varShield66` | 0 |
| 지형i | `varTerrI67` | 1 |
| 임시 | `varTmp68` | 0 |
| 임시k | `varTmpK69` | 1 |
| 각도 | `varAngle70` | 20 |
| 발사방향 | `varFireDir71` | 70 |
| 플레이어Y | `varPlayerY72` | -100 |

### 5.3 스프라이트 로컬

- **지아이조**: `칸번호` `varTankCol`
- **총알**: `복제됨` `varShotIsC` · `칸번호` `varShotCol` · `남은수명` `varShotLife`
- **수류탄**: `복제됨` `varNadeIsC` · `속도X` `varNadeVX` · `속도Y` `varNadeVY`
- **적**: `복제됨` `varEnIsC` · `종류` `varEnKind` · `내VY` `varEnVY` · `바라봄` `varEnFace` · `사격쿨` `varEnFireT` · `칸번호` `varEnCol` · `막힘` `varEnBlock`
- **적탄**: `복제됨` `varEShotIsC` · `칸번호` `varEShotCol` · `남은수명` `varEShotLife`

### 5.4 방송

| 이름 | ID |
|------|-----|
| 게임시작 | `brStart01` |
| 발사 | `brFire02` |
| 수류탄 | `brNade03` |
| 적생성 | `brSpawn04` |
| 게임오버 | `brOver05` |
| 탄맞음 | `brHitShot06` |
| 수류탄폭발 | `brHitNade07` |
| 적발사 | `brEShot08` |
| 맵변경 | `brMap09` |
| 지형그리기 | `brDraw10` |

리스트: `지형높이` (`listHeight01`) — 칸마다 1~3 높이. 웨이브마다 재생성.

---

## 6. 상태머신

```
깃발 → 핸들 초기화, 체력=최대체력, 바라봄=90, 각도=20, 게임시작
플레이 → 이동/조준/방패/Z사격/C장전/X수류탄, 적 스폰
피격 → 무적타이머>0 동안 고스트, 데미지 1회
처치 웨이브킬(기본 16)의 배수 → 웨이브+1, 스폰간격↓ (하한 0.4)
체력≤0 → 게임상태=2, 게임오버 배너
```

---

## 7. 블록 흐름

### 지아이조

**(A) 깃발** show, left-right, goto (−140, 바닥Y), VY=0, 코스튬 idle.

**(B) 이동·조준** forever wait 0.025, 게임상태=1일 때:

- right: 바라봄=90, point 90, x += 이동속도
- left: 바라봄=−90, point −90, x -= 이동속도
- x clamp −220..220. 상자는 앞에 그려진 엄폐(걸어 지나감). 탄만 막힘.
- ↑ 각도 += 조준속도 (최대 70), ↓ 각도 −= (최소 −20)
- 바라봄>0 → 발사방향=90−각도, 아니면 −90+각도
- 플레이어X/Y 갱신
- VY += 중력 ; y += VY (낮은 칸으로만 떨어짐)
- y < 지면Y → y=지면Y, VY=0, 재장전중=0이면 코스튬 idle
- y > 바닥Y+2 → 코스튬 jump
- 무적타이머>0 → −0.025, ghost 40 ; 아니면 ghost 0
- 체력≤0 → 게임상태=2, 게임오버

**(C) Z 사격** forever: 게임상태=1 and z and 남은탄>0 and 재장전중=0 and 방패중=0 and 탄수<최대탄수 → broadcast 발사, 남은탄−1, wait 연사간격. 빈 탄창 Z → click, wait 0.16.

**(C2) C 장전** C and 재장전중=0 and 남은탄<탄창 → 재장전중=1, 코스튬 reload, reload 사운드. 끝나면 남은탄=탄창, idle, click.

**(C3) space 방패** space → 방패중=1 (처음 들 때 click). 떼면 0.

**(D) X 수류탄** forever wait 0.03: x키 and 수류탄쿨남은≤0 and 수류탄수<2 → broadcast 수류탄, 수류탄쿨남은=수류탄쿨. 쿨>0이면 −0.03

**(E) 피격은 적이 처리.** 지아이조는 무적타이머만 본다.

### 총알

깃발 hide, 복제됨=0.
`발사`: 원본만 and 탄수<최대탄수 → clone.
클론: 복제됨=1, 탄수+1, go to 지아이조, point 발사방향, 속도X/Y=탄속·sin/cos(방향), 매 틱 속도Y+=탄중력 (곡사포).
repeat until abs(x)>250 or touching 적 or 게임상태=2: move 탄속, wait 0.02
탄수−1, delete.

### 수류탄

깃발 hide, 복제됨=0.
`수류탄`: 원본만 → clone.
클론: 복제됨=1, 수류탄수+1, go to 지아이조, nade 사운드
속도X = (바라봄>0 ? 수류탄력 : 0−수류탄력), 속도Y=수류탄띄움
repeat until y≤바닥Y or touching 적 or 게임상태=2:
  속도Y += 중력 ; x+=속도X ; y+=속도Y ; wait 0.02
boom 코스튬, boom 사운드, size↑, wait 0.12 (적이 이 동안 touching 수류탄으로 사망)
수류탄수−1, delete.

### 적

깃발 hide, 복제됨=0, left-right.
`적생성`: 원본만 → clone.
클론: 복제됨=1, 적수+1, x=225, y=바닥Y, point −90, show
forever:
  if 게임상태=2: 적수−1, delete
  x -= 적속도
  if touching 총알 or touching 수류탄: 점수+100, 처치수+1, 적수−1, (처치수 mod 웨이브킬=0 → 웨이브+1, 스폰간격×(1−난이도증가율), 하한 0.4), pop, boom, delete
  if touching 지아이조 and 무적타이머≤0: 체력−=적공격, 무적타이머=무적시간, 적수−1, delete
  if x < −230: 체력−=적공격 (무적 무시하지 않음: 무적 중이면 통과만), 적수−1, delete — 프로토타입: 무적 중이면 데미지 스킵 후 삭제
  wait 0.03

### Stage 스폰

깃발: 핸들 set, 진행 리셋, broadcast 게임시작.
병렬: wait 0.6, forever: 게임상태=1이면 wait 스폰간격 후 적수<최대적수면 적생성.

### 배너

`게임오버` → show, gameover 사운드.

---

## 8. 재사용

- rogue-knight: VY/중력, 바닥 클램프, left-right
- bomb-squad: 클론 가드, 탄 상한, synth WAV
- 포트리스에서 가져옴: ↑↓ 각도, 발사방향=90−각도, 적 atan 조준. 점프·턴제·구덩이는 없음.

---

## 9. 학습 포인트 (보너스)

직선탄 vs 수류탄 포물선(VY에 중력이 붙는 차이). 핸들 `탄속`/`수류탄띄움`/`중력`으로 체감.

---

## 10. 테스트

- [ ] ←→ 이동, 방향 전환, 점프 없이 지면 유지
- [ ] ↑↓ 각도, Z 탄이 발사방향으로 (45도면 위로)
- [ ] space 방패, C 장전 코스튬+사운드, 빈 Z 클릭
- [ ] X 수류탄이 포물선을 그리고 바닥에서 터짐
- [ ] 적이 오른쪽에서 와 맞으면 죽음
- [ ] 접촉 시 체력 감소 + 짧은 무적
- [ ] 체력 0 게임오버
- [ ] 핸들 ID 1:1
