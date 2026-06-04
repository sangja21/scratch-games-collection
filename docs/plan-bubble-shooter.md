# 버블 슈터 (bubble-shooter) — Plan

> 화면 아래 발사대에서 색깔 거품을 위로 쏜다. 마우스로 조준(point towards mouse, 위쪽 반원으로 각도 제한)하고 클릭하면 거품이 직선으로 날아간다 — 좌우 벽에 맞으면 튕기고, 천장이나 기존 거품에 닿으면 가장 가까운 빈 격자 칸에 딱 붙는다(스냅). 붙은 자리에서 같은 색 거품이 3개 이상 연결되면 그 무리가 전부 터지고 점수가 오른다. 거품이 바닥선까지 내려오면 게임오버, 화면의 거품을 전부 없애면 승리. 1994 Taito "Puzzle Bobble(버블보블 퍼즐)" 의 간소화 버전 — **정육각 오프셋 격자 대신 정사각 격자 8열×12행으로 간소화**.
> 베이스: `games/tetris-mini/build.py`(**2D 격자를 1D 리스트로 평탄화 `idx=row*COLS+col+1` + `data_replaceitemoflist` 로 칸 값 치환 + 셀 클론 격자 렌더(`보드그리기`: 리스트 훑어 값≠0 칸마다 클론 + idx→좌표/색 복사) + my block(`충돌?`/`고정`) 동기 서브루틴**) + `games/pacman-mini/build.py`(**보드 리스트 1개로 격자 상태 단일 진실원 + 초기 배치 데이터 임베드 + 먹이 셀 클론 재렌더 패턴**) + `games/missile-command/build.py` 또는 `games/asteroids/build.py`(**마우스 조준 `point towards mouse-pointer` + dx/dy 직선 비행 발사체 + 벽 반사**) + `games/car-race/build.py`(게임상태 broadcast + 깃발 재시작 + 게임오버/승리 배너).
> **차이점**: tetris 는 블록이 격자에 떨어지지만 bubble-shooter 는 **자유 비행하는 발사체가 격자에 "스냅"** 된다 — 비행 중에는 격자와 무관한 (x,y) 좌표로 움직이다가, 충돌 순간 **현재 (x,y) 에서 가장 가까운 빈 칸**을 찾아 그 칸 인덱스에 색을 기록한다. 매칭은 tetris 의 라인검출(행 단위) 대신 **임의 모양 연결 무리를 스택 리스트 기반 flood fill** 로 찾는다(Scratch 재귀 불가 → 대기 리스트에 인덱스 push/pop).
> 학습 콘셉트 없음. 초등학생 대상 직관적 액션. 추상 학습 콘셉트 금지(MEMORY.md → feedback-game-design 준수).

- **주제**: 색 매칭 발사 퍼즐 (조준 발사 + 같은 색 3개 연결 제거)
- **카테고리**: 액션 / 퍼즐
- **난이도**: ★★★★
- **폴더**: `games/bubble-shooter/`
- **출력**: `games/bubble-shooter/bubble-shooter.sb3`

---

## 1. 한 줄 룰

마우스로 조준하고 클릭해 색깔 거품을 쏜다. 같은 색 거품이 3개 이상 모이면 터지고 점수 +. 거품이 바닥선까지 내려오면 게임오버, 다 없애면 승리.

---

## 2. 화면 / 좌표 (480×360)

- 무대 480×360 (Scratch 표준). 좌표 -240..240 / -180..180.
- **격자(grid)**: **8열 × 12행**(정사각 격자로 간소화). 한 칸 = **30px**(거품 코스튬 28px + 2px 틈). 격자 크기 = 240×360px, 화면 **왼쪽~중앙**에 배치하고 오른쪽에 HUD/다음거품.
  - 격자 픽셀 폭 = 8×30 = 240, 높이 = 12×30 = 360.
  - **칸 (col, row) 중심 ↔ 무대 좌표 (핵심 공식)**:
    - col(0..7), row(0..11, 0=맨 위=천장, 11=맨 아래=바닥선):
      - `X = -210 + col*30`   (col0 중심 X=-210, col7 중심 X=0)
      - `Y = 165 - row*30`    (row0 중심 Y=+165, row11 중심 Y=-165)
    - **1차원 리스트 인덱스(1-base)**: `idx = row*8 + col + 1`  (행 우선 평탄화, 8=열 수, 리스트 길이 96)
      - 역변환: `col = (idx-1) mod 8`, `row = floor((idx-1)/8)`.
  - **격자 좌우 경계 X**: 왼쪽 벽 = `-210 - 15 = -225`(col0 왼쪽 가장자리), 오른쪽 벽 = `0 + 15 = +15`(col7 오른쪽 가장자리). 비행하는 거품이 이 두 X 에서 좌우 반사한다.
  - **천장 Y**: `165 + 15 = +180`(무대 위끝). 비행 거품이 이 위로 가면 천장 충돌.
  - **바닥선(게임오버) row**: **row 11**. 어떤 칸이든 row 11 에 거품이 들어오면 게임오버(2절 6.4 참조). 초기 배치는 row 0~4 만 채워 여유를 둔다.
- **발사대(슈터)**: 격자 아래가 아니라 **격자 오른쪽 아래 빈 영역**(col7 보다 오른쪽, X≈+90, Y≈-120)에 두면 격자와 안 겹쳐 깔끔하지만, 정통 버블슈터 손맛을 위해 **격자 폭 중앙 바로 아래**(X = col 중앙 ≈ `-210 + 3.5*30 = -105`, Y = `-165 - 15 = -180` 부근, 무대 맨 아래)에 둔다. 본문은 슈터를 **(슈터X, 슈터Y) = (-105, -150)** 에 고정(격자 중앙 열 아래, 바닥선보다 약간 아래). 거품은 여기서 출발해 위로 날아간다.
- **SVG(0~480, 0~360) ↔ Scratch(-240~240, -180~180) 변환**: `Scratch_x = SVG_x - 240`, `Scratch_y = 180 - SVG_y`. 격자 영역은 SVG 좌상단 `(15, 0)` ~ 우하단 `(255, 360)`(= Scratch `(-225, 180)`~`(15, -180)`). 빌더는 배경 SVG 에서 이 영역에 옅은 격자선(30px) + 좌/우/천장 벽 라인 + **row11 위쪽에 빨간 바닥선**을 그린다.
- 배경: 짙은 보라/남색 그라데이션. 왼쪽 8×12 격자 영역(옅은 셀선) + **빨간 바닥선(row11 경계)** + 오른쪽 패널에 "NEXT" 미리보기 박스 + 점수/남은거품/발사수 모니터.

```
+----------------------------------------------------+  y=+180 (천장)
| ● ● ● ● ● ● ● ●  ← 초기 거품 (row0)      |          |
| ● ● ● ● ● ● ● ●     (row1)               |  점수:0   |
| ● ● ● ● ● ● ● ●     (row2)               |          |
| ● ● ● ● ● ● ● ●     (row3)               | 남은거품:|
| ● ● ● ● ● ● ● ●     (row4)               |   40     |
| . . . . . . . .     (row5)               |          |
| . . . . . . . .     (row6)               |  NEXT:   |
| . . . . . . . .     (row7)               | +------+ |
| . . . . . . . .     (row8)               | |  ●   | |
| . . . . . . . .     (row9)               | +------+ |
| . . . . . . . .     (row10)              |  발사:7  |
|=====바닥선(row11)========================|          |  ← 여기 닿으면 GAME OVER
|              ╲  ↑조준선                   |          |
|               ● ← 발사대(슈터) (-105,-150)|          |
+----------------------------------------------------+  y=-180
x=-240 col0중심 X=-210 ... col7중심 X=0          x=+240
       row0중심 Y=+165 ... row11중심 Y=-165
```

> 클론 수 산정: 격자 셀 렌더 클론은 **최대 96개**(8×12 전부 찼을 때, 실제론 게임오버 전이라 그보다 적음). 비행 거품은 슈터 sprite 본체 1개(클론 불필요). NEXT 미리보기 1개. 합쳐도 **약 100개** ≪ Scratch 클론 한계 300 → 안전. 정육각 오프셋 격자(행마다 반 칸씩 어긋남)는 좌표·이웃 계산이 복잡하므로 **정사각 격자 채택**(상하좌우 4-이웃 flood fill 로 단순). 색 매칭/재미에는 충분.

---

## 3. 초기 보드 데이터 (빌더가 생성 규칙으로 채움) — **핵심 자료구조**

8열×12행 = **96칸**. 값: **0=빈칸, 1~5=거품 색**(1빨강 2주황 3노랑 4초록 5파랑).

- **초기 배치 규칙**: 게임시작 시 `보드` 96칸을 0으로 채운 뒤, **row 0~4(위 5행, 총 40칸)** 를 각 칸 `pick random 1 to 5` 로 채운다(나머지 row5~11 은 0). → 시작 시 거품 40개, 천장에 5줄.
  - 빌더는 Stage init 에서 `repeat 96: add 0`(또는 리스트 contents 96×0 임베드) 후, `row 0..4 / col 0..7` 이중 루프로 `replace item(row*8+col+1) of 보드 with (pick random 1 to 5)`.
  - **단순 루프 구현**: `i ← 1; repeat 40: replace item(i) of 보드 with (pick random 1 to 5); i ← i+1` (idx 1..40 = row0~4 의 40칸과 정확히 일치, `40 = 5*8`).
- **남은거품 카운트**: 초기화 직후 `남은거품 ← 40`. 거품이 터질 때마다 -개수, 새로 붙을 때마다 +1. **0 되면 승리.**

> **보드 리스트 초기화**: 게임시작 시 `보드` 를 `delete all` 한 뒤 96번 `add 0`, 그다음 idx 1..40 을 랜덤색으로 치환. 이후 절대 길이를 바꾸지 않고 **`replace item idx of 보드 = 값`**(`data_replaceitemoflist`) 로만 칸 값을 수정한다. **0=빈칸이 단일 진실원** — 스냅·매칭·게임오버·승리 판정 전부 이 리스트 조회로 한다.
> **(선택) 결정적 초기 배치**: 매번 랜덤이 싫으면 아래처럼 고정 패턴을 임베드해도 됨(빌더 재량, MVP 는 랜덤 권장).
> ```python
> # build.py 임베드용 (선택). idx(1-base)=row*8+col+1. row0..4 만 색, 나머지 0.
> BOARD0 = (
>   [3,3,1,1,2,2,5,5]   # row0
>  +[3,4,1,4,2,3,5,1]   # row1
>  +[2,4,4,4,3,3,1,1]   # row2
>  +[5,5,2,2,4,4,3,3]   # row3
>  +[1,1,5,5,2,2,4,4]   # row4
>  +[0]*56 )            # row5..11 (7행 × 8 = 56칸) = 빈칸
> assert len(BOARD0) == 96
> ```

---

## 4. 스프라이트 (4개 + Stage)

| # | 이름 | 역할 | 비고 |
|---|------|------|------|
| 0 | Stage | 전역 상태 init + 보드 리스트(96칸) 생성/랜덤 채움 + 발사수 카운트(압박 메커닉용) | 게임시작/보드그리기/다음거품준비 broadcast 발신 |
| 1 | 슈터 (발사대 + 비행 거품) | **게임의 두뇌**. 평소엔 발사대로 마우스 조준(`point towards mouse`, 각도 위쪽 반원 clamp). 클릭하면 현재거품을 dx/dy 직선 비행시킴 — 좌우 벽 반사 + 천장/기존 거품 충돌 검출. 충돌 시 **가장 가까운 빈 칸 찾기(스냅)** → 보드에 색 기록 → **flood fill 매칭** → 3개↑면 무리 제거 + 점수 → (선택)낙하 처리 → 다음 거품 준비 + 게임오버/승리 체크. | rotationStyle "all around"(조준 회전). 색 코스튬 5개. 비행은 본체 1개로(클론 X). **모든 게임 규칙 담당.** |
| 2 | 격자셀 (거품 클론 ≤96개) | **격자에 붙은 거품들**을 그린다. `보드그리기` broadcast 수신 시 기존 클론 전부 삭제 후, 보드 리스트 96칸을 훑어 값≠0 칸마다 클론 1개 생성(해당 칸 좌표 + 값=색 코스튬). | 색 코스튬 5개(슈터와 동일 세트 공유). tetris 보드셀 / pacman 먹이 렌더 패턴. |
| 3 | NEXT 미리보기 | 다음에 쏠 거품 색을 오른쪽 NEXT 박스에 표시. `다음거품준비` 수신 시 `다음색` 코스튬으로 전환. | 색 코스튬 5개 공유. 단일 sprite(클론 X). 생략 가능(MVP). |
| 4 | 배너 | "GAME OVER" / "YOU WIN!" 배너. 게임상태로 표시 분기. 평소 숨김. | car-race/snake 배너 패턴. |

> NEXT 미리보기 sprite 는 MVP 에서 생략 가능(슈터 본체가 `다음색` 모니터만 보여도 됨). 본문은 별도 sprite 안으로 둠.

---

## 5. 변수 (Stage 글로벌)

| 변수명 | ID | 초기값 | 용도 |
|--------|----|---------|------|
| 점수 | `varScore01` | 0 | 거품 1개 터질 때 +10 (무리 크면 누적). 콤보 보너스 선택 |
| 최고기록 | `varBest02` | 0 | 세션 최고 점수 |
| 게임상태 | `varState03` | 1 | 1=조준대기, 2=발사중(비행), 0=게임오버, 3=승리 |
| 남은거품 | `varRemain04` | 40 | 격자에 붙은 거품 수. 0 되면 승리(게임상태=3) |
| 현재색 | `varCurColor05` | (랜덤1~5) | 지금 슈터에 장전된 거품 색(코스튬 번호) |
| 다음색 | `varNextColor06` | (랜덤1~5) | 다음에 장전될 색(NEXT 미리보기) |
| 발사수 | `varShots07` | 0 | 누적 발사 횟수. N발(예:5)마다 한 줄 내려옴(압박, 선택) |
| 한줄주기 | `varPushEvery08` | 5 | 몇 발마다 보드 한 줄 내릴지(압박 메커닉. 0이면 비활성) |

### 5.1 슈터 sprite-local 변수 (비행 / 스냅 / 매칭 임시) — **핵심**

| 변수명 | ID | 용도 |
|--------|----|------|
| 비행X | `varFlyX09` | 비행 중 거품 현재 x (격자와 무관한 자유 좌표) |
| 비행Y | `varFlyY10` | 비행 중 거품 현재 y |
| 속도X | `varVX11` | 비행 x 속도(프레임당 이동, 좌우 반사 시 부호 반전) |
| 속도Y | `varVY12` | 비행 y 속도(항상 + = 위로) |
| 스냅col | `varSnapCol13` | 스냅: 현재 (비행X,비행Y) 에서 가장 가까운 칸의 열 |
| 스냅row | `varSnapRow14` | 스냅: 가장 가까운 칸의 행 |
| 스냅idx | `varSnapIdx15` | 스냅 칸 보드 인덱스 = 스냅row*8 + 스냅col + 1 |
| 최소거리 | `varBestDist16` | 스냅: 빈 칸 중 거품 위치와 거리 최소값 추적 |
| 매칭색 | `varMatchColor17` | flood fill 대상 색(스냅한 거품 색) |
| 무리수 | `varGroupN18` | flood fill 로 찾은 같은 색 연결 무리 크기 |
| 현idx | `varCurIdx19` | flood fill: 스택에서 pop 한 현재 칸 인덱스 |
| 현col | `varCurCol20` | 현idx 의 열 = (현idx-1) mod 8 |
| 현row | `varCurRow21` | 현idx 의 행 = floor((현idx-1)/8) |
| 이웃idx | `varNbrIdx22` | flood fill: 4-이웃 칸 인덱스 임시 |
| i | `varI23` | 일반 루프 카운터(스냅 96칸 훑기 / 줄내림 등) |
| 각도 | `varAngle24` | 조준 각도(위쪽 반원 clamp 결과) |

> 슈터 sprite-local 임시가 많지만 전부 비행·스냅·flood fill 의 내부 계산용(플레이어 비노출). 글로벌로 빼도 되나 다른 sprite 와 안 겹치게 슈터 로컬 권장.

### 5.2 격자셀 / NEXT sprite-local 변수

| 변수명 | ID | 소속 | 용도 |
|--------|----|------|------|
| 그릴idx | `varDrawIdx25` | 격자셀 | 보드그리기 루프에서 훑는 보드 인덱스(클론 생성 직전 set) |
| 그릴색 | `varDrawColor26` | 격자셀 | 그 칸 색(코스튬 번호). 클론이 복사 |

---

## 6. 리스트 (Stage 글로벌) — **핵심 자료구조**

| 리스트명 | ID | 길이 | 용도 |
|----------|----|------|------|
| 보드 | `L_board01` | 96 | **8열×12행 격자**를 행 우선 평탄화. 0=빈칸, 1~5=거품색. `idx=row*8+col+1`. 게임 상태의 단일 진실원. 스냅 시 `replace ... with 색`, 매칭 제거 시 `replace ... with 0`. |
| 매칭대기 | `L_queue02` | 가변(0~96) | **flood fill 스택**. 검사할 칸 인덱스를 push(add)/pop(맨끝 item+delete). 7.5 의사코드 참조. 매 매칭마다 비우고(`delete all`) 시작. |
| 매칭표시 | `L_visited03` | 96 | flood fill 방문 여부(0=미방문,1=방문). 같은 칸 재방문/무한루프 방지. 매 매칭 전 96칸 0 으로 리셋. **또는** 방문한 칸을 보드에서 임시로 -색 처리하는 대신 별도 표시 리스트가 안전. |
| 제거대기 | `L_remove04` | 가변(0~96) | flood fill 로 모은 "같은 색 연결 무리" 인덱스들. 무리수≥3 이면 이 리스트의 칸을 전부 0 으로 치움. 매 매칭마다 `delete all`. |

> **리스트 4개 모두 게임시작 시 초기화**: `보드`(96, 0채움+랜덤), `매칭대기`/`제거대기`(빈 리스트로 시작, 매칭마다 delete all), `매칭표시`(96, 매칭마다 0 리셋). `매칭표시` 도 길이 96 고정으로 두고 매칭 전 `i←1; repeat 96: replace item(i) of 매칭표시 with 0; i←i+1`.
> **왜 스택 리스트?**: Scratch 는 재귀/함수 호출 스택이 없어 전통적 재귀 flood fill 불가. 대신 **명시적 스택(리스트)에 "아직 검사 안 한 칸"을 쌓아두고, 비어질 때까지 하나씩 꺼내 4-이웃을 검사** 하는 반복(iterative) flood fill 로 같은 색 연결 무리를 안전하게 찾는다(7.5).

---

## 7. 메커닉 상세

### 7.1 좌표 ↔ 인덱스 헬퍼 (모든 곳에서 사용)

- 칸 (col,row) 무대 좌표: `X = -210 + col*30`, `Y = 165 - row*30`.
- 칸 (col,row) 보드 인덱스: `idx = row*8 + col + 1`.
- idx → 칸: `col = (idx-1) mod 8`, `row = floor((idx-1)/8)`.
- **4-이웃(정사각 격자 상하좌우)**: 칸 (col,row) 의 이웃 = 오른(col+1,row) / 왼(col-1,row) / 위(col,row-1) / 아래(col,row+1). 각 이웃은 `0 ≤ col ≤ 7` AND `0 ≤ row ≤ 11` 일 때만 유효(경계 밖 무시). 인덱스로는: 왼/오른은 같은 행이라 `현idx±1` 이지만 **행 경계 넘침 주의** — col 을 따로 계산해 `col±1 이 0..7 범위인지` 확인 후 `현idx±1`. 위/아래는 `현idx±8`(범위는 1..96).

### 7.2 조준 (슈터, 마우스 추적 + 각도 clamp) — 위쪽 반원

발사대는 항상 마우스를 향하되 **위쪽 반원(거의 수평~수직 위)** 으로만 조준한다(아래로는 못 쏨).

```
when receive 게임시작:        # 조준 forever (게임상태=1 일 때만)
  goto (-105, -150)            # 슈터 고정 위치
  repeat until 게임상태 = 0 OR 게임상태 = 3:
    if 게임상태 = 1:                       # 조준 대기 중에만 회전
      point towards (mouse-pointer)
      # Scratch 방향: 0=위, 90=오른쪽, 180=아래, -90=왼쪽
      # 위쪽 반원으로 clamp: 방향을 -80..+80 범위로(천장 향해 좌우 80도까지)
      각도 ← direction
      if 각도 > 80:  각도 ← 80          # 너무 오른쪽 아래로 못 가게
      if 각도 < -80: 각도 ← -80         # 너무 왼쪽 아래로 못 가게
      point in direction 각도
    wait 0.02
```

> **방향 규칙**: Scratch `point in direction d` 에서 0=정북(위), 90=동(오른쪽), -90=서(왼쪽). 마우스가 슈터보다 아래에 있으면 `point towards` 결과가 100~180 또는 -100~-180(아래쪽)이 되는데, `각도>80 → 80`, `각도<-80 → -80` clamp 로 항상 위쪽 반원만 조준(좌우 최대 80도까지 기울어진 위 방향). 빌더는 clamp 를 if 2개로 단순 처리.
> **조준선(선택)**: 발사대에서 조준 방향으로 점선(pen) 또는 화살표 코스튬을 그려 어디로 갈지 보여주면 초등학생 친화적(MVP 생략 가능).

### 7.3 발사 (슈터, 클릭 → dx/dy 직선 비행 + 벽 반사) — **핵심**

마우스 클릭(또는 스페이스)으로 현재거품을 조준 방향으로 발사. 비행 중 좌우 벽 반사, 천장/기존 거품 충돌 시 7.4(스냅) 호출.

```
when receive 게임시작:        # 발사 forever
  repeat until 게임상태 = 0 OR 게임상태 = 3:
    if (게임상태 = 1) AND (mouse down? OR key space):
      게임상태 ← 2                         # 발사중 (조준 회전 멈춤)
      # 초기 위치·속도: 슈터 위치에서 현재 조준 각도로
      비행X ← -105 ; 비행Y ← -150
      속도X ← (sin(각도)) * 12             # 각도 deg → 속도 벡터 (프레임당 12px)
      속도Y ← (cos(각도)) * 12             # cos(0)=1=위로 최대, sin 으로 좌우
      switch costume to 현재색
      show ; goto (비행X, 비행Y)
      call 비행루프                        # my block(아래) — 충돌까지 직선비행
    wait 0.02
```

```
define 비행루프 (커스텀 블록, run WITHOUT screen refresh 끄기 — 화면 갱신 ON 필요!)
  # ※ 비행은 매 프레임 보여야 하므로 'run without screen refresh' 를 켜면 안 됨.
  #   대신 repeat 안에 작은 wait 없이 일반 repeat until 로 두고, 한 스텝당 적게 움직임.
  repeat until (천장도달 OR 거품충돌):
    비행X ← 비행X + 속도X
    비행Y ← 비행Y + 속도Y
    # (1) 좌우 벽 반사
    if 비행X < -225 + 14:                  # 왼쪽 벽(거품 반지름 14 고려)
      비행X ← -225 + 14 ; 속도X ← 속도X * -1
    if 비행X > 15 - 14:                    # 오른쪽 벽
      비행X ← 15 - 14 ; 속도X ← 속도X * -1
    goto (비행X, 비행Y)
    # (2) 천장 도달? (row0 중심 Y=165, 거품 반지름 14 → 비행Y ≥ 165-? 면 천장칸 줄)
    if 비행Y ≥ 165:                        # row0 줄에 닿음 = 천장 충돌
      call 스냅                            # 7.4
      stop this script
    # (3) 기존 거품과 충돌? — 현재 (비행X,비행Y) 가장 가까운 '찬 칸'과 거리 < 28 이면 충돌
    #     단순/안전 구현: 비행 거품과 격자셀 클론의 touching 으로도 가능하나,
    #     좌표·리스트 기반이 결정적 → 아래 '충돌검사' 사용.
    call 충돌검사                          # 충돌이면 call 스냅 + stop (아래)
  # (루프 자연 종료 케이스 없음 — 충돌/천장에서 stop this script)
```

> **비행 충돌검사(좌표 기반, 결정적)** — 비행 거품 중심이 어떤 **찬 칸 중심**과 28px(=거의 한 칸) 이내로 가까워지면 충돌로 본다:
> ```
> define 충돌검사 (커스텀 블록, run without screen refresh)
>   i ← 1
>   repeat 96:
>     if (item(i) of 보드) ≠ 0:                       # 찬 칸만
>       셀X ← -210 + ((i-1) mod 8)*30
>       셀Y ← 165 - (floor((i-1)/8))*30
>       거리 ← sqrt( (비행X-셀X)^2 + (비행Y-셀Y)^2 )   # operator_mathop sqrt
>       if 거리 < 28:                                  # 닿음
>         call 스냅 ; stop this script (호출부에서 루프 종료 플래그)
>     i ← i + 1
> ```
> **간단 대안(touching 기반)**: `충돌검사` 대신 **`if touching(격자셀)?` → call 스냅** 로도 됨(격자셀 sprite 의 클론과 접촉 감지). 좌표 루프보다 블록 수 적고 직관적이나, 접촉 순간 거품이 칸을 살짝 파고들 수 있어 스냅이 살짝 부정확할 수 있음. **빌더 재량 — MVP 는 `touching(격자셀)?` 권장**(7.4 스냅이 가장 가까운 빈 칸을 찾으므로 약간의 오차는 흡수됨).
> **반사 직관**: `속도X ← 속도X * -1` 만으로 좌우 벽에서 입사각=반사각. 천장 반사는 없음(천장에 닿으면 바로 붙음). `속도Y` 는 항상 양수(위로)라 결국 천장이나 거품에 닿는다 → 무한 비행 없음.
> **sin/cos**: `operator_mathop("sin"/"cos", 각도)`. Scratch 는 도(degree) 단위. 각도 0 → cos=1(위로), sin=0(좌우 0). 각도 +80 → 거의 오른쪽 위. 부호: 무대에서 +Y 가 위이므로 `속도Y = cos(각도)`(각도0에서 최대 양수)면 위로 감. `속도X = sin(각도)`(각도+면 오른쪽).

### 7.4 스냅 — 가장 가까운 빈 칸에 붙이기 (슈터 my block) — **핵심**

비행 거품이 멈춘 (비행X, 비행Y) 에서 **거리가 가장 가까운 빈 칸(보드 값=0)** 을 찾아 그 칸에 현재색을 기록한다.

```
define 스냅 (커스텀 블록, run without screen refresh)
  최소거리 ← 999999
  스냅idx ← 0
  i ← 1
  repeat 96:
    if (item(i) of 보드) = 0:                         # 빈 칸만 후보
      셀X ← -210 + ((i-1) mod 8)*30
      셀Y ← 165 - (floor((i-1)/8))*30
      거리 ← (비행X-셀X)*(비행X-셀X) + (비행Y-셀Y)*(비행Y-셀Y)   # 제곱거리(sqrt 불필요)
      if 거리 < 최소거리:
        최소거리 ← 거리
        스냅idx ← i
    i ← i + 1
  # 안전장치: 빈 칸을 못 찾으면(만석) 그냥 무시
  if 스냅idx > 0:
    replace item(스냅idx) of 보드 with 현재색           # 보드에 색 기록
    스냅row ← floor((스냅idx-1)/8)
    남은거품 ← 남은거품 + 1
    broadcast 보드그리기                               # 격자 재렌더
    play sound stick
    # 바닥선 도달 = 게임오버
    if 스냅row ≥ 11:
      게임상태 ← 0
    else:
      call 매칭                                        # 7.5 같은색 무리 검사·제거
  hide                                                 # 비행 거품 본체 숨김(이제 격자셀이 그림)
  # 다음 거품 준비 + 다시 조준 대기
  if 게임상태 ≠ 0 AND 게임상태 ≠ 3:
    call 다음거품
    게임상태 ← 1
```

> **"가장 가까운 빈 칸" 이 스냅의 핵심**: 비행 거품이 어디서 멈췄든, 빈 칸 96개(실제론 빈 칸만) 중 유클리드(제곱)거리 최소 칸에 붙인다. 정사각 격자라 보통 충돌 직전 위치 바로 위/옆 빈 칸이 잡혀 자연스럽다. `sqrt` 안 쓰고 **제곱거리 비교**로 충분(최소만 찾으면 되므로 단조 변환 불필요 → 블록·연산 절약).
> **만석 안전장치**: 거의 발생 안 하나 빈 칸이 0개면 `스냅idx=0` 으로 두고 그냥 거품 소멸(게임오버 직전 상황).

### 7.5 매칭 — 스택 리스트 flood fill (슈터 my block) — **핵심**

스냅한 칸에서 시작해 **같은 색으로 상하좌우 연결된 무리** 를 스택 기반 반복 flood fill 로 모으고, 3개 이상이면 전부 제거한다. **Scratch 재귀 불가 → 명시적 스택(`매칭대기` 리스트)에 push/pop.**

```
define 매칭 (커스텀 블록, run without screen refresh)
  매칭색 ← 현재색                          # 방금 붙인 거품 색
  # (0) 작업 리스트 초기화
  delete all of 매칭대기
  delete all of 제거대기
  i ← 1
  repeat 96: replace item(i) of 매칭표시 with 0 ; i ← i + 1   # 방문표시 0 리셋
  # (1) 시작 칸을 스택에 push + 방문표시
  add 스냅idx to 매칭대기
  replace item(스냅idx) of 매칭표시 with 1
  # (2) 스택이 빌 때까지: pop → 같은색이면 제거대기에 담고 4-이웃 push
  repeat until (length of 매칭대기) = 0:
    현idx ← item (length of 매칭대기) of 매칭대기      # 스택 top peek
    delete (length of 매칭대기) of 매칭대기            # pop
    if (item(현idx) of 보드) = 매칭색:                # 같은 색이면 무리에 포함
      add 현idx to 제거대기
      현col ← (현idx - 1) mod 8
      현row ← floor((현idx - 1) / 8)
      # --- 4-이웃을 검사해 (범위 내 + 미방문) 면 push + 방문표시 ---
      # 오른쪽 (col+1)
      if 현col < 7:
        이웃idx ← 현idx + 1
        if (item(이웃idx) of 매칭표시) = 0:
          replace item(이웃idx) of 매칭표시 with 1
          add 이웃idx to 매칭대기
      # 왼쪽 (col-1)
      if 현col > 0:
        이웃idx ← 현idx - 1
        if (item(이웃idx) of 매칭표시) = 0:
          replace item(이웃idx) of 매칭표시 with 1
          add 이웃idx to 매칭대기
      # 위 (row-1)
      if 현row > 0:
        이웃idx ← 현idx - 8
        if (item(이웃idx) of 매칭표시) = 0:
          replace item(이웃idx) of 매칭표시 with 1
          add 이웃idx to 매칭대기
      # 아래 (row+1)
      if 현row < 11:
        이웃idx ← 현idx + 8
        if (item(이웃idx) of 매칭표시) = 0:
          replace item(이웃idx) of 매칭표시 with 1
          add 이웃idx to 매칭대기
  # (3) 무리 크기 = 제거대기 길이. 3개 이상이면 전부 제거
  무리수 ← length of 제거대기
  if 무리수 ≥ 3:
    i ← 1
    repeat 무리수:
      replace item( item(i) of 제거대기 ) of 보드 with 0   # 그 칸 비움
      i ← i + 1
    점수 ← 점수 + 무리수 * 10
    남은거품 ← 남은거품 - 무리수
    if 점수 > 최고기록: 최고기록 ← 점수
    play sound pop
    # (선택) 떠 있는(천장 미연결) 거품 낙하 — 7.6
    call 낙하정리                          # ← 생략 가능(아래 7.6 참조)
    broadcast 보드그리기
    # 승리 체크
    if 남은거품 ≤ 0: 게임상태 ← 3
```

> **스택 flood fill 핵심 동작**: ① 시작 칸을 `매칭대기`(스택)에 넣고 방문표시. ② 스택에서 맨 끝(top)을 꺼내(pop) 같은 색이면 `제거대기`에 기록하고, 그 칸의 4-이웃 중 **아직 방문 안 한 칸**을 스택에 넣고 즉시 방문표시(중복 push 방지). ③ 스택이 빌 때까지 반복 → 시작 칸과 같은 색으로 연결된 모든 칸이 `제거대기`에 모인다. **방문표시(`매칭표시`)로 같은 칸을 두 번 처리하지 않아 무한루프·중복이 없다.**
> **pop = "맨 끝 항목 읽고 삭제"**: Scratch 리스트엔 pop 블록이 없으므로 `item(length) of 매칭대기` 로 마지막을 읽고 `delete (length) of 매칭대기` 로 지운다(LIFO 스택). 큐(FIFO) 로 `item 1` + `delete 1` 해도 결과 동일(연결 무리는 같음).
> **이웃 인덱스 주의**: 왼/오른은 `현idx±1` 이지만 **행을 넘지 않게 `현col<7`/`현col>0` 으로 가드**(col7 의 오른쪽이 다음 행 col0 이 되면 안 됨). 위/아래는 `현idx±8`(`현row` 범위 가드). 7.1 의 4-이웃 규칙 그대로.
> **방문표시를 미리(push 시점) 찍는 이유**: pop 시점에 찍으면 같은 칸이 스택에 여러 번 들어가 비효율·중복. push 즉시 표시하면 각 칸이 스택에 최대 1번만 들어간다.

### 7.6 (선택) 떠 있는 거품 낙하 — `낙하정리` my block

매칭 제거로 윗부분과 끊겨 **천장(row0)과 연결되지 않은** 거품 무리는 아래로 떨어져 사라진다(정통 버블슈터 손맛). **구현 비용이 크면 생략 가능.**

- **알고리즘(또 다른 flood fill)**: ① `매칭표시` 96칸 0 리셋. ② **row0 의 모든 찬 칸**(idx 1..8 중 보드 값≠0)을 시드로 스택에 push + 방문표시. ③ 스택이 빌 때까지 pop → 4-이웃 중 **찬 칸(값≠0)** 이고 미방문이면 push+표시("천장에 연결됨" 표시). 색 무관, **빈 칸 아닌 모든 연결만** 따라감. ④ 끝나면 `매칭표시=0` 인데 보드 값≠0 인 칸 = **천장 미연결(떠 있음)** → 그 칸들 `replace ... with 0` + `남은거품--` + 점수 보너스(개당 +20). ⑤ `broadcast 보드그리기`.
- **의사코드 골격**(7.5 와 동일 스택 패턴, 시드와 "같은색" 조건만 다름):
  ```
  define 낙하정리 (run without screen refresh)
    delete all of 매칭대기
    i ← 1 ; repeat 96: replace item(i) of 매칭표시 with 0 ; i ← i+1
    # row0 찬 칸을 시드로
    i ← 1
    repeat 8:
      if (item(i) of 보드) ≠ 0:
        replace item(i) of 매칭표시 with 1 ; add i to 매칭대기
      i ← i + 1
    # 천장 연결 flood (색 무관, 찬 칸만 따라감)
    repeat until (length of 매칭대기) = 0:
      현idx ← item(length of 매칭대기) of 매칭대기 ; delete (length) of 매칭대기
      현col ← (현idx-1) mod 8 ; 현row ← floor((현idx-1)/8)
      # 4-이웃: 범위내 + 보드값≠0 + 매칭표시=0 → push+표시  (7.5 와 동일 4분기)
      ...
    # 미연결(떠 있는) 칸 제거
    i ← 1
    repeat 96:
      if (item(i) of 보드 ≠ 0) AND (item(i) of 매칭표시 = 0):
        replace item(i) of 보드 with 0
        남은거품 ← 남은거품 - 1 ; 점수 ← 점수 + 20
      i ← i + 1
  ```
> **생략 시**: 7.5 의 `call 낙하정리` 줄을 빼면 됨. 떠 있는 거품이 그냥 공중에 남아도 게임은 정상 동작(매칭으로만 제거). **MVP 는 생략 권장**(블록 ~40개 절약). 여유 되면 추가해 손맛↑. 본 plan 의 난이도/카운트는 **낙하 생략 기준**.

### 7.7 다음 거품 / 압박(한 줄 내림) — Stage + 슈터

```
define 다음거품 (슈터 my block, 또는 broadcast)
  현재색 ← 다음색
  다음색 ← pick random 1 to 5
  발사수 ← 발사수 + 1
  switch costume to 현재색
  goto (-105, -150) ; show
  broadcast 다음거품준비          # NEXT 미리보기 갱신
  # (선택) 압박: 한줄주기 발마다 보드 한 줄 내림
  if (한줄주기 > 0) AND (발사수 mod 한줄주기 = 0):
    call 한줄내림
```

```
define 한줄내림 (run without screen refresh)   # 모든 거품을 한 행 아래로 + 맨 위 새 줄
  # row11 부터 row1 까지: 보드[row] ← 보드[row-1] (아래로 복사)
  현row ← 11
  repeat until 현row < 1:
    i ← 0
    repeat 8:
      replace item(현row*8 + i + 1) of 보드 with (item((현row-1)*8 + i + 1) of 보드)
      i ← i + 1
    현row ← 현row - 1
  # row0 = 새 랜덤 줄
  i ← 0
  repeat 8:
    replace item(0*8 + i + 1) of 보드 with (pick random 1 to 5)
    남은거품 ← 남은거품 + 1
    i ← i + 1
  broadcast 보드그리기
  # 내려서 바닥선(row11) 에 거품이 생겼으면 게임오버
  i ← 11*8 + 1                    # = 89 (row11 첫 칸)
  repeat 8:
    if (item(i) of 보드) ≠ 0: 게임상태 ← 0
    i ← i + 1
```

> **압박 메커닉(선택)**: tetris 의 라인 끌어내림과 반대 방향(아래로 밀고 맨 위에 새 줄). `한줄주기=5` → 5발마다 한 줄 추가로 압박↑. `한줄주기=0` 이면 비활성(MVP 는 비활성으로 시작해도 됨 — 그래도 초기 5줄 다 없애면 승리하므로 게임 성립). **남은거품 카운트는 줄내림으로 +8 됨에 주의**(승리 판정 일관).
> **mod**: `operator_mod`. `발사수 mod 한줄주기 = 0` 이면 그 발에서 줄내림.

### 7.8 렌더 (격자셀 / NEXT)

**격자셀 sprite**(붙은 거품 렌더, ≤96 클론) — tetris 보드셀 / pacman 먹이 패턴 그대로:

```
when flag clicked: hide
when receive 보드그리기:
  broadcast 격자지우기          # 기존 클론 자가삭제
  wait 0                        # 삭제 양보
  그릴idx ← 1
  repeat 96:
    그릴색 ← item(그릴idx) of 보드
    if 그릴색 ≠ 0:
      create clone of _myself_   # 클론이 그릴idx/그릴색 읽어 배치
    그릴idx ← 그릴idx + 1
when I start as clone:
  switch costume to 그릴색
  goto ( -210 + ((그릴idx-1) mod 8)*30 , 165 - (floor((그릴idx-1)/8))*30 )
  show
when receive 격자지우기:
  delete this clone
```

> **렌더 빈도**: `보드그리기` 는 **스냅/제거/줄내림 시에만** 호출(발사당 1~2회) → 96 클론 재생성도 가볍다. 비행 거품은 슈터 본체가 직접 그리므로(클론 X) 격자 재렌더와 무관.
> **`그릴idx`/`그릴색` 복사 타이밍**: set 직후 create clone → 클론이 start 에서 읽음(tetris/pacman/breakout 동일 패턴).

**NEXT 미리보기 sprite**:
```
when flag clicked: goto (NEXT박스 위치 ≈ 195, 30) ; show
when receive 다음거품준비:
  switch costume to 다음색
```

### 7.9 게임오버 / 승리 / 재시작

car-race/snake 패턴. 배너 sprite:
```
when flag clicked: hide ; goto 0,0 ; go to front
when receive 게임시작:
  wait until (게임상태 = 0) OR (게임상태 = 3)
  if 게임상태 = 0: switch costume "gameover"
  if 게임상태 = 3: switch costume "win"
  show
```
깃발 재클릭 → 변수 리셋(점수0/게임상태1/남은거품/현재색·다음색 랜덤/발사수0) + 보드 리스트 재초기화(96×0 + row0~4 랜덤) + 작업 리스트(`매칭대기`/`제거대기` 비움, `매칭표시` 96×0) + 모든 클론 삭제(Scratch 깃발이 자동) → 새 게임. 게임오버 시 buzz, 승리 시 fanfare(또는 pop 재사용).

---

## 8. 방송 (broadcasts)

| 이름 | ID | 트리거 |
|------|----|--------|
| 게임시작 | `brStart01` | 깃발 클릭 후 Stage 초기화(보드/변수) 끝나면 발신 |
| 보드그리기 | `brDrawBoard02` | 게임시작 1회 + 스냅·매칭제거·줄내림 후 → 격자셀 재렌더 |
| 격자지우기 | `brClearCells03` | 보드그리기 직전 → 격자셀 클론 자가삭제 |
| 다음거품준비 | `brNextReady04` | 발사 후 다음 거품 장전 시 → NEXT 미리보기 갱신 |

> 슈터의 `비행루프`/`충돌검사`/`스냅`/`매칭`/`다음거품`/`한줄내림`/`낙하정리` 는 **같은 sprite 내 my block(커스텀 블록) 동기 호출** 로 처리(broadcast 아님) — tetris 의 `충돌?`/`고정` 과 동일하게 순서 보장·변수 안전. my block 미지원이면 broadcast+`wait until 완료=1` 동기 패턴으로 대체.

---

## 9. 씬 / 상태머신

```
[깃발 클릭]
   ↓ Stage init (점수0/게임상태1/남은거품40/보드=랜덤5줄/현재색·다음색 랜덤) → broadcast 게임시작 + 보드그리기 + 다음거품준비
[조준 대기 (게임상태=1)] ──마우스 이동──> 슈터가 마우스 향해 회전(위쪽 반원 clamp)
        │
   (클릭 / 스페이스)
        ↓ 게임상태=2 (발사중)
[비행 (게임상태=2)] : dx/dy 직선 + 좌우 벽 반사
        │
   (천장 도달 OR 기존 거품 충돌)
        ↓ call 스냅 → 가장 가까운 빈 칸에 색 기록 → 보드그리기
        │
   ┌────┴───────────────┐
 (스냅 row ≥ 11)     (그 외)
 게임상태=0          call 매칭 (flood fill)
 [GAME OVER]              │
                  ┌───────┴────────┐
              (무리≥3)          (무리<3)
            무리 제거+점수      그대로 둠
            (선택)낙하정리          │
              남은거품--            │
                  │                │
            (남은거품=0)            │
            게임상태=3 [YOU WIN]    │
                  └───────┬────────┘
                          ↓ call 다음거품 → 게임상태=1 (다시 조준 대기)
                     (5발마다 한줄내림 → 바닥선 닿으면 게임상태=0)

[깃발 재클릭] → 처음으로
```

상태값: `게임상태` 1=조준대기 / 2=발사중 / 0=게임오버 / 3=승리. 조준·발사 forever 는 `repeat until 게임상태=0 OR =3` 로 종료, 조준 회전은 `게임상태=1` 일 때만.

---

## 10. 스프라이트별 블록 트리 (의사코드)

### Stage
```
when flag clicked:
  점수 ← 0 ; 게임상태 ← 1 ; 발사수 ← 0 ; 한줄주기 ← 5 (또는 0)
  현재색 ← pick random 1 to 5 ; 다음색 ← pick random 1 to 5
  # 보드 96칸 0 채움 + row0~4 랜덤
  delete all of 보드
  repeat 96: add 0 to 보드
  i ← 1 ; repeat 40: replace item(i) of 보드 with (pick random 1 to 5) ; i ← i+1
  남은거품 ← 40
  # 작업 리스트
  delete all of 매칭대기 ; delete all of 제거대기
  delete all of 매칭표시 ; repeat 96: add 0 to 매칭표시
  broadcast 게임시작
  broadcast 보드그리기
  broadcast 다음거품준비
```
> (Stage 는 타이머가 필요 없음 — 이벤트 드리븐. 비행은 슈터 my block 의 repeat 가 담당.)

### 슈터 (조준 + 비행 + 스냅 + 매칭)
```
when flag clicked: rotationStyle "all around" ; size 100
when receive 게임시작:
  goto (-105, -150) ; switch costume to 현재색 ; show
  <조준 forever — 7.2>
when receive 게임시작:
  <발사 forever — 7.3 상단>
# my blocks:
define 비행루프  : <7.3>
define 충돌검사  : <7.3 주석>      # 또는 touching(격자셀) 대안
define 스냅      : <7.4>
define 매칭      : <7.5>
define 다음거품  : <7.7 상단>
define 한줄내림  : <7.7 하단>      # 한줄주기>0 일 때만
define 낙하정리  : <7.6>           # 선택(생략 가능)
```

### 격자셀 (붙은 거품 클론) — 7.8 상단 그대로

### NEXT 미리보기 — 7.8 하단 그대로

### 배너 — 7.9 그대로

---

## 11. 자산 (SVG / WAV)

| 파일 | 종류 | 비고 |
|------|------|------|
| 배경 | SVG (인라인) | 480×360. 짙은 보라/남색. 왼쪽 8×12 격자 영역(SVG (15,0)~(255,360))에 옅은 셀선(30px) + 좌/우/천장 벽 라인 + **row11 경계에 빨간 바닥선**. 오른쪽 패널 "NEXT" 박스 + 라벨. |
| 거품 색 코스튬 | SVG (인라인) ×5 | ~28×28 둥근 원 + 하이라이트. costume1=빨강 2=주황 3=노랑 4=초록 5=파랑. rotationCenter 중앙. **슈터·격자셀·NEXT sprite 가 동일 5색 코스튬 공유**. |
| 배너 | SVG (인라인) ×2 | costume "gameover"=GAME OVER(+"거품이 바닥에 닿았어요"), "win"=YOU WIN!(+"거품을 다 터뜨렸어요!"). |
| pop.wav | WAV (assets/) | 거품 터지는 효과음. `games/car-race/assets/pop.wav` 복사·재사용. |
| stick.wav | WAV (assets/) | 거품 붙는 효과음(선택, pop 재사용 가능). |

> 거품 28px + 칸 30px → 2px 틈으로 격자가 보인다. `goto(칸 중심)` + size 100 이면 칸에 딱 맞음(viewBox 28×28 가정). 슈터/격자셀/NEXT 가 같은 5색 코스튬을 쓰므로 SVG 5개만 만들면 됨(슈터는 회전하지만 원형이라 무방). assets/ 폴더: `pop.wav` 1개(pop/stick 공용)로 시작.

---

## 12. 변수/리스트/메시지 요약 (ID 컨벤션)

- 글로벌 변수 8개: `varScore01`(점수) `varBest02`(최고기록) `varState03`(게임상태) `varRemain04`(남은거품) `varCurColor05`(현재색) `varNextColor06`(다음색) `varShots07`(발사수) `varPushEvery08`(한줄주기)
- 슈터 sprite-local 16개: `varFlyX09`(비행X) `varVX11`(속도X) … `varAngle24`(각도) — 5.1 표 전체(비행X/비행Y/속도X/속도Y/스냅col/스냅row/스냅idx/최소거리/매칭색/무리수/현idx/현col/현row/이웃idx/i/각도). 충돌검사·스냅의 임시 `셀X`/`셀Y`/`거리`도 슈터 로컬 추가.
- 격자셀 sprite-local 2개: `varDrawIdx25`(그릴idx) `varDrawColor26`(그릴색)
- 리스트 4개(Stage 글로벌): `L_board01`(보드,96) `L_queue02`(매칭대기,스택) `L_visited03`(매칭표시,96) `L_remove04`(제거대기)
- broadcasts 4개: `brStart01`(게임시작) `brDrawBoard02`(보드그리기) `brClearCells03`(격자지우기) `brNextReady04`(다음거품준비)
- 모니터: 점수 / 남은거품 / 발사수(또는 NEXT 색)

---

## 13. 재사용 코드 (builder 가 참조할 부분)

- **2D 격자 → 1D 리스트 평탄화(`idx=row*8+col+1`) + `data_replaceitemoflist`(`replace_at` 헬퍼) + 셀 클론 격자 렌더(`보드그리기`: 리스트 훑어 값≠0 칸마다 클론 + idx→좌표/색 복사) + my block(`procedures_*`) 동기 서브루틴**: `games/tetris-mini/build.py` — bubble-shooter 의 `보드`/격자셀 렌더/`스냅`·`매칭` my block 이 tetris 의 `보드`·보드셀·`충돌?`/`고정` 과 **거의 1:1**. tetris 의 `replace_at` + 보드셀 렌더 루프 + my block 정의 패턴을 그대로 가져온다.
- **보드 리스트 1개로 격자 단일 진실원 + 초기 배치 데이터 임베드 + 셀 클론 재렌더(값에 따라 코스튬 분기)**: `games/pacman-mini/build.py` — `보드` 초기화(0채움→데이터), 먹이 렌더(`값=1→dot,값=2→power`)가 bubble 의 격자셀(`값=색→코스튬`)과 동일. pacman 의 보드 init·렌더 구조 재사용.
- **마우스 조준 `point towards mouse-pointer` + 각도 clamp + dx/dy 직선 비행 발사체 + 좌우 벽 반사(`속도X*-1`)**: `games/missile-command/build.py` / `games/asteroids/build.py` / `games/dogfight.md` — 슈터 조준·비행 로직. `operator_mathop("sin"/"cos")` 로 각도→속도 벡터. (이 게임들에서 발사체 dx/dy 비행과 벽 처리 패턴 차용.)
- **게임상태 broadcast + 깃발 재시작 + 게임오버/승리 배너**: `games/car-race/build.py` / `games/snake/build.py` — 배너 표시·재시작.
- **N카운트마다 압박 증가(`한줄내림`)**: `games/breakout/build.py`(라운드 속도+) / tetris 라인 끌어내림(반대 방향) — `발사수 mod 한줄주기` 로 한 줄 추가.

**필요한 블록 opcode (빌더 확인/추가)**:
- 리스트: `data_addtolist` / `data_deletealloflist` / `data_itemoflist` / `data_lengthoflist` / `data_deleteoflist` — snake/tetris 에 있음(스택 pop = `data_deleteoflist` 로 `length` 항목 삭제).
- **`data_replaceitemoflist`** — snake 엔 없고 **tetris-mini/pacman-mini 에 있음**(`replace_at`). 보드 칸 치환·매칭표시 리셋의 핵심. tetris 헬퍼 그대로.
- `operator_mod`(idx→col, 발사수 mod 주기) / `operator_mathop`("floor")(idx→row) / `operator_mathop`("sin"/"cos")(각도→속도) — tetris/missile-command 등에 mathop 존재(sin/cos 는 missile/asteroids 류에 있음).
- 커스텀 블록(my block): `procedures_definition`/`procedures_prototype`/`procedures_call` + `argumentreporter` — **tetris-mini 에 있음**(`충돌?`/`고정`). 그대로 차용.
- `sensing_mousedown` / `sensing_mousex`·`mousey`(또는 `point towards _mouse_`) — missile-command/duck-hunt 류에 있음.
- 나머지(`motion_gotoxy`/`pointtowards`/`pointindirection`, `looks_switchcostumeto`/`show`/`hide`, `control_*`/`create_clone`/`start_as_clone`/`delete_this_clone`, `operator_*`, `data_setvariableto`/`changevariableby`, `event_broadcast`)는 tetris/pacman/missile-command 에 모두 존재.

빌더 권장 베이스: **tetris-mini build.py 를 골격**(보드 평탄화 + `replace_at` + 보드셀 클론 렌더 + my block)으로 잡고 — (1) 격자를 8×12·`idx=row*8+col+1` 로 바꾸고, (2) tetris 의 "떨어지는 블록" 대신 **슈터 sprite(조준+dx/dy 비행+벽반사)** 를 missile-command 발사체 패턴으로 새로 작성, (3) `고정` 대신 **`스냅`(가장 가까운 빈 칸) + `매칭`(스택 flood fill)** my block, (4) 보드셀 렌더는 색(1~5) 코스튬으로, (5) 초기 배치는 pacman 식 데이터/랜덤 채움, (6) (선택) `한줄내림`·`낙하정리` 추가.

---

## 14. 학습 포인트

없음 — **순수 액션/퍼즐(보너스 게임)**. 1994 Puzzle Bobble 클래식 메커닉(조준 발사 + 색 매칭). 추상 학습 콘셉트 없음. 내부 구현의 인덱스 산수(`row*8+col+1`)·스택 flood fill·삼각함수 속도 분해는 플레이어에게 노출되지 않는다(플레이어는 "겨눠서 쏘고 같은 색 3개 모으기"만 인지).

---

## 15. 테스트 체크리스트 (verifier 가 확인)

1. `zipfile.is_zipfile()` 통과 / `project.json` JSON 로드 OK.
2. targets 수: 5 (Stage, 슈터, 격자셀, NEXT 미리보기, 배너). (NEXT 생략 시 4.)
3. Stage 글로벌 변수 8개 등록(점수/최고기록/게임상태/남은거품/현재색/다음색/발사수/한줄주기).
4. 슈터 sprite-local 변수(비행X/비행Y/속도X/속도Y/스냅col/스냅row/스냅idx/최소거리/매칭색/무리수/현idx/현col/현row/이웃idx/i/각도 + 셀X/셀Y/거리) 등록. 격자셀 sprite-local(그릴idx/그릴색).
5. 리스트 4개 등록: `보드`=L_board01(초기 96칸, idx1..40 색1~5 / idx41..96 = 0), `매칭대기`=L_queue02, `매칭표시`=L_visited03(96), `제거대기`=L_remove04.
6. Broadcasts 4개(게임시작/보드그리기/격자지우기/다음거품준비).
7. 슈터 조준 forever 에 `point towards mouse-pointer` + 각도 clamp(`>80→80`, `<-80→-80`) + `게임상태=1` 가드 존재.
8. 슈터 발사 forever 에 `mouse down? OR key space` + 게임상태=1 → 게임상태=2 + `속도X=sin(각도)*속도`, `속도Y=cos(각도)*속도` + `call 비행루프` 존재.
9. `비행루프` my block 에: `비행X/Y += 속도X/Y` + **좌우 벽 반사**(`비행X<-211→속도X*-1`, `비행X>1→속도X*-1` 식, 반지름 보정) + 천장(`비행Y≥165`)·기존거품 충돌 시 `call 스냅` + `stop this script` 존재. (충돌은 `touching(격자셀)?` 또는 좌표 `충돌검사` 둘 중 하나.)
10. `스냅` my block 에: 보드 96칸 중 **값=0 칸만** 후보로 `제곱거리` 최소 칸 탐색 → `replace item(스냅idx) of 보드 with 현재색` + `남은거품+1` + `broadcast 보드그리기` + `스냅row≥11 → 게임상태=0` + `call 매칭` 존재.
11. `매칭` my block(스택 flood fill) 에:
    - `delete all 매칭대기/제거대기` + `매칭표시` 96칸 0 리셋
    - 시작 칸 `add 스냅idx to 매칭대기` + `replace 매칭표시(스냅idx)=1`
    - `repeat until length(매칭대기)=0`: `item(length)` peek + `delete(length)` pop → `item(현idx) of 보드 = 매칭색` 이면 `add 현idx to 제거대기` + **4-이웃**(현col<7→+1 / 현col>0→-1 / 현row>0→-8 / 현row<11→+8) 각각 `매칭표시=0` 이면 표시+push
    - `무리수 = length(제거대기)`, `≥3` 이면 제거대기 칸들 `보드=0` + `점수+무리수*10` + `남은거품-무리수` + `broadcast 보드그리기` + `남은거품≤0→게임상태=3` 존재.
12. `다음거품` my block: `현재색←다음색`, `다음색←pick random 1..5`, `발사수+1`, `switch costume to 현재색`, `goto(-105,-150)`, `broadcast 다음거품준비`; (한줄주기>0 AND 발사수 mod 한줄주기=0 → `call 한줄내림`) 존재.
13. (압박 켠 경우) `한줄내림` my block: row11→1 아래로 복사 + row0 새 랜덤 줄 + `남은거품` 보정 + row11 찬 칸 있으면 게임상태=0 + `broadcast 보드그리기` 존재.
14. 격자셀 sprite: `보드그리기` 수신 시 기존 클론 삭제 후 `repeat 96` 로 `item(그릴idx) of 보드 ≠ 0` 칸마다 클론 생성 + 클론이 idx→좌표(`-210+col*30`,`165-row*30`)/색 코스튬 복사 존재. 초기 클론 수 40.
15. NEXT 미리보기: `다음거품준비` 수신 시 `switch costume to 다음색`(생략 가능).
16. 배너 sprite: `게임상태=0`→GAME OVER / `게임상태=3`→YOU WIN 표시 존재.
17. 자산: SVG(배경-격자/바닥선 포함 / 거품 색코스튬5 / 배너2) + WAV(pop 재사용), MD5 일치.
18. monitors: 점수·남은거품(또는 NEXT/발사수) 표시.
19. 블록 카운트 240~360 범위(`비행루프`/`스냅`/`매칭` flood fill + 격자 렌더 포함; 낙하정리 생략 기준).
20. (동작 검증) 마우스로 조준(위쪽 반원만) → 클릭하면 거품이 직선 발사·좌우 벽 반사 / 천장·기존 거품에 닿으면 가장 가까운 빈 칸에 붙음 / 같은 색 3개↑ 연결되면 무리 전부 터지고 점수↑·남은거품↓ / 거품이 바닥선(row11) 닿으면 GAME OVER / 거품 전부 없애면 YOU WIN / (압박 켜면 5발마다 한 줄 내려옴) / 깃발 재시작.

---

## 16. 빌드 카운트 예상

- Stage: ~30 블록 (init + 보드 96채움/40랜덤 루프 + 매칭표시 96채움 + broadcast).
- 슈터: ~170 블록 (조준 forever ~12 + 발사 forever ~14 + `비행루프` ~25 + `충돌검사`/touching ~15 + `스냅` ~25 + `매칭` flood fill ~55 + `다음거품` ~12 + `한줄내림` ~22).
- 격자셀: ~18 블록 (보드그리기 루프 + start-as-clone + 격자지우기).
- NEXT: ~6 블록.
- 배너: ~12 블록.
- **총합 예상: 240~340 블록** (★★★★ — dx/dy 비행+벽반사 + "가장 가까운 빈 칸" 스냅 + **스택 리스트 flood fill(재귀 없이 같은 색 무리 탐색)** 이 난이도 핵심. tetris 의 보드 평탄화·`replace_at`·my block·셀 렌더 재사용으로 완화. 낙하정리 추가 시 +40, ★★★★~★★★★☆.)

난이도: ★★★★

---

## 17. feedback-game-design 준수 체크

- [x] 초등학생 대상 직관적 액션 (마우스로 겨누고 클릭해 쏘기 — 즉시 이해. 누구나 아는 버블슈터/퍼즐보블).
- [x] 추상 학습 콘셉트 없음 (거품=거품, 색=색. 수학·과학 매핑 없음. 인덱스/스택/삼각함수는 내부 구현일 뿐 비노출).
- [x] 즉시 이해되는 룰 (같은 색 3개 모으면 터지고 점수, 바닥에 닿으면 끝, 다 없애면 승리).
- [x] 도전감 (조준 정밀도 + 벽 반사 활용 + 연쇄/큰 무리 고득점 + (선택)줄 압박) — 너무 어렵지 않게 5색·정사각 격자로 완화.
- [x] 짧은 세션, 즉시 재시작 (깃발 클릭).
- [x] 1994 Puzzle Bobble 클래식 — 검증된 재미 메커닉. 정육각→정사각 8×12 격자, 5색, 낙하정리 선택으로 초등학생 난이도/구현 난이도 동시 완화.
```
