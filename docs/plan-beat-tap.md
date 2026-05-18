# 🎵 비트 탭 — 구현 계획

> **주제**: 음악·반응속도 (학습 요소 X — 보너스 게임)
> **카테고리**: 액션 / 리듬
> **난이도**: ★★★ (블록 ~250개)
> **폴더**: `games/beat-tap/`
> **출력**: `비트_탭.sb3`

## 게임 한 줄

위에서 4개 레인을 따라 음표가 떨어진다. 음표가 판정선에 닿는 순간 해당 키(`D` `F` `J` `K`)를 누른다. 판정: **Perfect / Good / Miss**. 콤보 끊기지 않고 노래 끝까지 가는 것이 목표.

## 화면 레이아웃 (480×360)

```
┌────────────────────────────────────────┐
│ 점수: 12,340     콤보: 42x    Perfect! │  ← HUD
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│  │       │       │       │             │
│  │  ♪    │       │       │             │
│  │       │       │  ♪    │             │
│  │       │  ♪    │       │             │  ← 4개 레인 (낙하 영역)
│  │       │       │       │  ♪          │
│  │  ♪    │       │       │             │
│  ╧───────╧───────╧───────╧───────╧     │  ← 판정선
│  [ D ]   [ F ]   [ J ]   [ K ]         │  ← 키 표시
└────────────────────────────────────────┘
```

## 스프라이트 / 코스튬 / 사운드

| 스프라이트 | 코스튬 | 비고 |
|------------|--------|------|
| **Note** (clone-driven) | `normal`, `hit_perfect`, `hit_good`, `miss` | 단일 SVG, 색만 변경 |
| **Lane-bg** | 4개 레인의 반투명 트랙 | 배경에 그려넣어도 OK |
| **Hit-line** | 판정선 + D/F/J/K 라벨 | 배경에 포함 |
| **Judgment-text** | "Perfect!" / "Good" / "Miss" 텍스트 | `say` 또는 별도 스프라이트 |
| **Background** | 어두운 무대 + 네온 그라데이션 | 새 SVG |

**사운드**:
- `tick.wav` — 음표 hit (Perfect/Good)
- `miss.wav` — 미스
- `bgm.wav` — 백그라운드 음악 (8마디, ~30초). **자체 합성** (build.py 에서 sine wave 생성) 또는 무료 8-bit 트랙

## 변수 / 메시지

```
변수 (전역)
  V_SCORE
  V_COMBO
  V_MAX_COMBO
  V_TIME        곡 시작 후 경과 시간(초) — 모든 타이밍의 기준
  V_GAMEOVER

리스트 (전역)
  L_NOTE_TIME   각 음표의 등장 시각 (예: [0.5, 1.0, 1.5, 1.75, 2.0, ...])
  L_NOTE_LANE   각 음표의 레인 (1~4)
  L_NOTE_FIRED  이미 클론으로 띄운 음표인지 0/1

변수 (클론 로컬)
  L_LANE        이 음표의 레인 (1~4)
  L_TARGET_T    이 음표가 판정선에 도달해야 할 V_TIME
  L_STATE       0=떨어지는중, 1=판정완료(사라지는중)

메시지
  BR_START
  BR_TICK       매 0.02초 (V_TIME += 0.02)
  BR_KEY_D / BR_KEY_F / BR_KEY_J / BR_KEY_K
  BR_HIT_PERFECT / BR_HIT_GOOD / BR_MISS
  BR_GAMEOVER
```

## 채보(차트) 형식

음표 데이터는 `(시각, 레인)` 쌍의 리스트로 보관. build.py 에서 하드코딩으로 채워둔다.

```python
# build.py 안 — 예시 8마디, BPM 120 (1마디 = 2초)
NOTES = [
    (0.50, 1), (1.00, 2), (1.50, 3), (2.00, 4),     # 1마디: 좌→우
    (2.50, 1), (2.75, 4), (3.00, 1), (3.25, 4),     # 2마디: 양끝 번갈아
    (3.50, 2), (3.75, 3), (4.00, 2), (4.25, 3),     # 3마디: 중간 번갈아
    # ...
]
```

이걸 `L_NOTE_TIME`, `L_NOTE_LANE` 두 리스트로 init 시 채워넣는다.

## 게임 흐름

```
[초록 깃발]
   ↓
초기화: V_TIME=0, V_SCORE=0, V_COMBO=0
L_NOTE_FIRED 모두 0 으로
   ↓
broadcast BR_START → BGM 재생 시작
   ↓
[메인 루프 — 배경]
   forever
      change V_TIME by 0.02
      wait 0.02 sec
      check_notes_to_spawn:
         각 음표 i 에 대해:
            if L_NOTE_FIRED[i] = 0 AND L_NOTE_TIME[i] - V_TIME <= FALL_TIME
               create clone of Note with (lane=L_NOTE_LANE[i], target_t=L_NOTE_TIME[i])
               set L_NOTE_FIRED[i] to 1
```

## 핵심 스크립트 (의사코드)

### 음표 클론 — 낙하

```
when I start as a clone
   set L_STATE to 0
   set x to lane_x(L_LANE)              # 1→-120, 2→-40, 3→40, 4→120
   set y to 180                         # 화면 상단
   show
   forever
      # 판정선(y = -130) 까지 FALL_TIME 초에 걸쳐 내려옴
      # 진행률 p = (V_TIME - (L_TARGET_T - FALL_TIME)) / FALL_TIME
      set p to (V_TIME - (L_TARGET_T - FALL_TIME)) / FALL_TIME
      set y to 180 - (180 - (-130)) * p
      if V_TIME > L_TARGET_T + 0.15 AND L_STATE = 0    # 판정 윈도우 초과
         broadcast BR_MISS
         set L_STATE to 1
         change costume to miss
         wait 0.2 sec
         delete this clone
```

### 키 입력 (배경 또는 별도 스프라이트)

```
when key D pressed
   broadcast BR_KEY_D
# (F, J, K 동일)
```

### 음표 — 판정 처리

```
when I receive BR_KEY_D                   # 레인 1 만 반응
   if L_LANE = 1 AND L_STATE = 0
      set diff to abs(V_TIME - L_TARGET_T)
      if diff <= 0.05
         broadcast BR_HIT_PERFECT
         change costume to hit_perfect
      else if diff <= 0.12
         broadcast BR_HIT_GOOD
         change costume to hit_good
      else
         # 너무 일찍/늦음 — 무시 또는 miss 처리
         exit
      set L_STATE to 1
      wait 0.15 sec
      delete this clone
```

### 점수 / 콤보

```
when I receive BR_HIT_PERFECT
   change V_SCORE by 100
   change V_COMBO by 1
   play tick.wav

when I receive BR_HIT_GOOD
   change V_SCORE by 50
   change V_COMBO by 1
   play tick.wav at -3dB

when I receive BR_MISS
   set V_COMBO to 0
   play miss.wav
```

## 타이밍 / 판정 윈도우

- `FALL_TIME` = 1.5초 (음표가 위에서 판정선까지 내려오는 시간)
- **Perfect**: |diff| ≤ 0.05초 (=50ms)
- **Good**:    0.05 < |diff| ≤ 0.12초
- **Miss**:    diff > 0.15초

이 값들은 모두 build.py 상단에 상수로 뽑아둘 것 — 튜닝하기 위함.

## 핵심 도전

### 1. BGM 동기화

Scratch 에서 `play sound until done` 동안 다른 스크립트는 정상 실행되지만, **BGM 시작 시각과 V_TIME=0 시각을 정확히 맞춰야** 채보가 어긋나지 않는다.

```
when flag clicked
   reset_timer
   set V_TIME to 0
   start sound bgm.wav         # play sound (until done 아님)
   # 동시에 메인 루프 시작
```

### 2. 음표 클론 한도

Scratch 클론은 동시에 최대 300개. 30초에 음표 ~100개 정도가 적정. 음표가 판정선 통과 후 즉시 삭제되므로 동시 존재 ~20개 이하로 유지 가능.

### 3. 키 동시 입력

D + J 동시 누름 같은 경우 — Scratch 의 `when key X pressed` 는 독립적으로 트리거되므로 자동 처리됨. **단**, `<key X pressed?>` 로 폴링하면 안 됨. 이벤트 기반으로만.

### 4. 음표 데이터 입력의 지루함

8마디 ~100개 음표를 손으로 적기 부담. **대안**:
- BPM + 패턴 코드로 압축 (예: `"1234,1414,2323"` 같은 문자열을 파싱)
- `build.py` 에서 패턴 → `(시각, 레인)` 리스트로 전개

## 단계별 구현 체크리스트

- [ ] 폴더 `games/beat-tap/` + assets
- [ ] 음표 SVG (4 코스튬: normal/perfect/good/miss)
- [ ] 무대 배경 SVG (4 레인 트랙 + 판정선)
- [ ] BGM 파일 준비 (자체 합성 또는 라이선스 OK 한 8-bit 트랙 30초)
- [ ] `tick.wav`, `miss.wav` 사운드
- [ ] 채보 데이터 — `NOTES` 리스트를 build.py 에 하드코딩
- [ ] `build.py` 초안 (alien-invasion 의 클론 패턴 참고)
- [ ] 변수/리스트/메시지 ID 정의
- [ ] 메인 시간축 루프
- [ ] 음표 스폰 로직 (L_NOTE_FIRED 체크)
- [ ] 음표 낙하 + 자동 miss
- [ ] 키 입력 → 판정 윈도우 체크
- [ ] 점수/콤보 HUD
- [ ] 게임 끝(채보 완주) → 결과 화면
- [ ] 첫 빌드 → BGM 동기화 미세조정
- [ ] **타이밍 튜닝** — Perfect/Good 윈도우, FALL_TIME, BGM 시작 오프셋
- [ ] README.md
- [ ] 루트 README.md + game-candidates.md 표 업데이트

## 빌드 노트 / 위험 요소

- **가장 큰 리스크 = BGM 동기화**. Scratch 의 사운드 재생은 OS 오디오 큐 지연이 있어 V_TIME 과 실제 BGM 위치 간 ~50ms 오차가 생길 수 있다. 빌드 후 직접 플레이해서 오프셋 변수(`V_AUDIO_OFFSET`) 로 보정한다.
- 채보를 짧게 시작 (1마디 = 8음표) → 동작 확인 후 늘리기
- 음표 클론 생성 빈도가 높을 때 (16비트 마디 = 8개/2초) Scratch 가 살짝 끊길 수 있음. 그 경우 `FALL_TIME` 을 2초로 늘려서 동시 클론 수 더 허용.
- BGM 자체 합성 — 파이썬 `wave` 모듈로 사인파 + 단순 멜로디 (C4 → E4 → G4 같은 8-bit 멜로디) 생성. `audioop` 으로 짧은 마디 반복.

## 향후 확장

- 곡 선택 (3곡)
- 난이도 Easy/Normal/Hard — 같은 곡, 다른 채보 밀도
- 자체 채보 에디터 (외부 도구로 JSON 만들고 build.py 가 import) — 욕심나면.

## 참고

- 메커닉 출처: `docs/game-candidates.md` 의 "리듬 게임 (Beat Tap)" / griffpatch 스타일
- 클론 + 시간축 패턴: `alien-invasion` 의 외계인 클론 진행, `whack-a-prime` 의 시간 카운터 참고
