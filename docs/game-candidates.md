# 🎮 게임 후보 목록 (Game Candidates)

> 다음에 만들 게임 후보를 모아둔 문서입니다. 인터넷 자료(영어/한국어 Scratch 강의·블로그·MIT 공식)에서 반복적으로 등장하는 게임들 + 컬렉션 컨셉(학습형 + 액션 보너스)에 어울리는 후보들을 카테고리별로 정리했습니다.
>
> **작성일**: 2026-05-07
> **현재 컬렉션 상태**: 3개 게임 — `polynomial-shooter`, `whack-a-prime`, `alien-invasion`

## 난이도 표기

- ★ : 매우 쉬움 (블록 ~50개, 1시간 이내 빌드)
- ★★ : 쉬움 (블록 ~100개)
- ★★★ : 중간 (블록 ~200개, 클론/충돌/상태머신)
- ★★★★ : 어려움 (블록 ~400개, 복잡한 로직)
- ★★★★★ : 매우 어려움 (대규모 게임)

---

## 🕹 클래식 아케이드 (레퍼런스 풍부)

| 게임 | 메커닉 | 난이도 | 비고 |
|------|--------|-------|------|
| **Flappy Bird** | 한 버튼(스페이스/마우스) 점프, 파이프 사이 비행 | ★★ | Scratch에서 가장 자주 만들어지는 게임. 짧은 코드로 완성. griffpatch 버전 유명 |
| **Snake** | 꼬리 자라는 뱀, 자기 몸 충돌 회피 | ★★★ | 클론으로 꼬리 관리. 격자 기반 이동 |
| **Pong** | 패들 두 개 + 공 (1인 vs AI 또는 2인) | ★★ | 가장 단순한 클래식, 입문에 좋음 |
| **Breakout / 벽돌깨기** | 패들 + 공 + 벽돌 격자 | ★★★ | `alien-invasion` 의 격자 코드 일부 재사용 가능 |
| **Tetris** | 7가지 블록 회전 + 라인 제거 | ★★★★ | 어렵지만 만족도 매우 높음. 블록 회전 매트릭스 |
| **Pac-Man** | 미로 + 도트 + 유령 AI | ★★★★★ | 복잡, 유령 AI 패턴 4종(추격/매복/순찰/도주) |

## 🏃 리액션 / 엔드리스

| 게임 | 메커닉 | 난이도 | 비고 |
|------|--------|-------|------|
| **Catching Game (사과 받기)** | 떨어지는 사과 좌우로 받기 | ★ | 한국 스크래치 자료의 입문 게임 단골 |
| **Doodle Jump** | 위로 끝없이 점프 + 발판 | ★★★ | 카메라 이동 (모든 발판이 함께 내려가는 식) |
| **Endless Runner** | 좌우 이동/점프로 장애물 피함 | ★★★ | 지오메트리 대시 단순화 버전 |
| **Geometry Dash (griffpatch 스타일)** | 리듬 점프, 가시밭 통과 | ★★★★ | 음악과 동기화하면 리듬 게임 |

## 🧩 퍼즐 / 두뇌

| 게임 | 메커닉 | 난이도 | 비고 |
|------|--------|-------|------|
| **Tic-Tac-Toe** | OX 3×3 (AI 추가하면 ★★★) | ★★ | 미니맥스 알고리즘 학습 좋음 |
| **Memory Match** | 카드 뒤집어 짝 맞추기 | ★★ | 클론 + 상태(앞/뒤/매치) 관리 |
| **2048** | 숫자 슬라이드 합치기 | ★★★★ | 4×4 격자, 깔끔한 알고리즘 |
| **미로 탐험** | 키보드로 출발→골 | ★★ | 비주얼 단순, 레벨 디자인 재밌음 |
| **Sokoban (박스 밀기)** | 박스를 정해진 자리로 | ★★★★ | 충돌/되돌리기 로직 |

## 🎓 학습형 (컬렉션 컨셉 일관성)

| 게임 | 메커닉 | 난이도 | 학습 |
|------|--------|-------|------|
| **국기/수도 퀴즈 (World Explorer)** | 국기 보고 나라 클릭 | ★★ | 사회/지리 |
| **타자 연습** | 떨어지는 단어 빨리 타이핑 | ★★ | 영단어 / 한글 자모 |
| **Math Mayhem** | 사칙연산 문제 빠르게 풀기 | ★★ | 산수 / 암산 |
| **분수 피자 가게** | "2/3 주세요" 주문 받아 자르기 | ★★★ | 분수 / 동치분수 |
| **삼각함수 서핑** | `y = A·sin(B·x + C)` 파도 위 서핑 | ★★★ | 진폭 / 주기 / 위상 |
| **좌표평면 낚시** | (-3, 4) 좌표 클릭 | ★★ | 사분면 / 음수좌표 |
| **양팔저울 방정식** | `3x + 2 = 11` 균형 맞추기 | ★★★ | 일차방정식 |
| **두더지 슬링샷** | 슬링샷으로 두더지 격파 (이전 *실수* 후보) | ★★★★ | 포물선 운동 (물리) |

## 🎨 색다른 / 도전적

| 게임 | 메커닉 | 난이도 | 비고 |
|------|--------|-------|------|
| **리듬 게임 (Beat Tap)** | 떨어지는 음표 타이밍에 맞춰 누르기 | ★★★ | 음악 동기화 |
| **타워 디펜스** | 경로에 타워 배치 → 적 웨이브 막기 | ★★★★★ | 가장 복잡, 경로/적/타워 클론 다수 |
| **공 튕기기 (Pong-like)** | 마우스로 패들 → 공 컨트롤 | ★ | 입문, 한국 자료 단골 |
| **Idle Clicker** | 클릭 + 업그레이드 | ★ | 단순하지만 중독성 |

---

## 🎯 추천 우선순위 (현재 컬렉션 기준)

### 🥇 1순위 — 가장 빠르게 추가 가능

1. **🌊 삼각함수 서핑** (★★★ / 학습형)
   - `polynomial-shooter` 의 곡선 미리보기 + 수식 모니터 + 슬라이더 코드 약 **90% 재사용** 가능
   - `y = a·x² + b·x` 의 식만 `y = A·sin(B·x + C)` 로 바꾸면 끝
   - 컬렉션 안에서 *2차 함수 → 삼각함수* 흐름이 자연스러움

2. **🍎 Catching Game (사과 받기)** (★ / 액션)
   - Scratch 자료의 표준 입문 게임. 가장 단순한 코드로 게임 한 편 완성
   - alien-invasion 보다 훨씬 가벼움 → "★ 난이도 슬롯" 비어있음

3. **🐦 Flappy Bird** (★★ / 액션)
   - 컬렉션의 "한 버튼" 게임 슬롯
   - 파이프 클론 무한 생성 + 스크롤 + 점프 물리

### 🥈 2순위 — 다양성 확보

4. **🐍 Snake** (★★★ / 액션)
   - 클래식. 클론으로 꼬리 관리, 격자 이동, 자기충돌 패턴 학습
   - 한 번도 패턴 비슷한 게임이 없는 카테고리

5. **🎲 2048** (★★★★ / 두뇌)
   - 컬렉션에 *슬로우 페이스 두뇌형* 부재
   - 4×4 격자 슬라이드 알고리즘이 흥미로움

6. **🟦 Tic-Tac-Toe (vs AI)** (★★~★★★ / 두뇌)
   - 미니맥스 AI 구현하면 학습 깊이 ↑
   - 짧은 코드로 완성 가능

### 🥉 3순위 — 도전적

7. **🟧 Tetris** (★★★★ / 액션·퍼즐)
8. **🛡 타워 디펜스** (★★★★★ / 액션·전략)
9. **🎵 리듬 게임** (★★★ / 음악·반응속도)

---

## 📌 게임별 키 메커니즘 노트

선택해서 만들 때 참고할 핵심 패턴:

### Flappy Bird
- 새: y 좌표만 변화 (중력으로 매 틱 -1.5px씩 떨어짐, 스페이스로 +12px)
- 파이프: 클론. 우측에서 등장 → 좌측으로 스크롤 → 화면 밖 삭제
- 충돌: 파이프 닿거나 바닥/천장 도달
- 점수: 파이프를 넘기면 +1

### Snake
- 격자 이동 (예: 20×15, 칸 크기 24px)
- 머리 + 꼬리 클론들
- 매 틱 머리가 한 칸 이동, 꼬리는 머리 위치 기록 후 따라옴
- 사과 먹으면 꼬리 +1
- 자기 몸/벽 닿으면 게임오버

### Catching Game
- 캐릭터(바구니): 좌우 이동
- 사과 클론: 위에서 떨어짐, 바구니 닿으면 점수+, 바닥 닿으면 라이프-
- 60초 또는 라이프제

### 삼각함수 서핑
- `polynomial-shooter` 골격 그대로
- 곡선식만 변경: `y = -120 + A·sin(B·x + C)`
- A/B/C 슬라이더 (각각 진폭/주기/위상)
- 분홍 펜으로 sin 곡선 미리보기 + 수식 모니터 표시
- 서퍼(고양이/펭귄?)가 곡선 따라 글라이드, 장애물(상어?) 회피

### 2048
- 4×4 격자, 각 칸의 숫자
- 화살표 키로 4방향 슬라이드
- 같은 숫자 만나면 합쳐짐 (2+2=4, 4+4=8, ...)
- 빈 칸 무작위로 2 또는 4 등장
- 2048 도달 = 클리어

---

## 📚 검색 출처

### 영어
- [15 Best Scratch Projects for Kids — Create & Learn](https://www.create-learn.us/blog/scratch-projects-for-kids/)
- [30+ Scratch Project Ideas — Modern Age Coders](https://learn.modernagecoders.com/blog/30-plus-scratch-project-ideas-kids-fun-coding-beginner-advanced)
- [Scratch Game Ideas For Kids — CodaKid](https://codakid.com/scratch-game-ideas/)
- [15 Fun Scratch Games to Code (2026) — Codingal](https://www.codingal.com/coding-for-kids/blog/easy-games-to-code-in-scratch/)
- [25 Best Scratch Games to Play and Remix — CodeWizardsHQ](https://www.codewizardshq.com/25-best-scratch-games/)
- [13 Game Ideas for Scratch — FunTech](https://funtech.co.uk/latest/13-game-ideas-for-scratch)
- [Programming Math Games in Scratch — Codeyoung](https://www.codeyoung.com/blog/programming-math-games-in-scratch-fun-ways-to-make-learning-engaging-cm706qgnc0038u7cg8mndzabr)
- [35 Best Scratch Games for Kids — CodaKid](https://codakid.com/unlocking-creativity-and-learning-with-codakid-the-35-best-scratch-games-for-kids/)
- [Top Scratch Games — YoungWonks](https://www.youngwonks.com/blog/best-scratch-games)
- [Griffpatch (Scratch user, 클래식 게임 다수)](https://scratch.mit.edu/users/griffpatch/)
- [Scratch Ideas (MIT 공식)](https://scratch.mit.edu/ideas)
- [Best Scratch Games for Kids 2025 — JetLearn](https://www.jetlearn.com/blog/best-scratch-games)

### 한국어
- [스크래치로 추억의 플래시 게임 만들기 — 스파르타클럽](https://spartaclub.kr/blog/scratch)
- [스크래치로 사과 받기 게임 만들기 — imssam](https://imssam.me/story/story_detail.php?sq=113)
- [스크래치로 공 튕기기 게임 만들기 — imssam](https://imssam.me/story/story_detail.php?sq=112)
- [10. 스크래치 게임만들기 — 처음코딩 (생활코딩)](https://opentutorials.org/course/2967/15342)
- [스크래치 게임 만들기 강의 — SONOL YouTube](https://www.youtube.com/watch?v=CWcKxR2i8as)

---

*이 문서는 새 게임 만들 때 출발점으로 쓰세요. 후보 추가/제외 자유롭게 편집해도 됩니다.*
