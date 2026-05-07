# 🎮 Scratch Games Collection

Scratch 3.0 으로 만든 학습형 미니게임 모음입니다. 코드(블록)와 함께 자동 생성 스크립트(Python)도 같이 들어 있어서, 마음대로 뜯어보거나 수정해 다시 빌드할 수 있어요.

## 🎯 게임 목록

| 게임 | 주제 | 한 줄 설명 |
|------|------|-----------|
| [다항함수 발사 게임](games/polynomial-shooter/) | 수학 — 다항함수 | 계수 a, b 를 조절해 곡선을 만들고 그 곡선을 따라 로켓을 발사해 풍선을 터뜨립니다. |
| [두더지 소수잡기](games/whack-a-prime/) | 수학 — 소수 | 풀밭에서 튀어나오는 두더지의 숫자가 소수일 때만 두드려 점수 획득. 60초 제한. |
| [외계인 침공](games/alien-invasion/) | 액션 — 슈팅 | 갤러그/스페이스인베이더 스타일. 외계인 격자 격파 + 라운드 진행. 학습 요소 X, 보너스 게임. |

## 🚀 게임 실행 방법

1. 원하는 게임 폴더에 들어가서 `.sb3` 파일을 다운로드합니다.
2. [scratch.mit.edu](https://scratch.mit.edu) 에 접속해 **만들기** 클릭.
3. 상단 메뉴 → **파일 → 컴퓨터에서 가져오기** → 받은 `.sb3` 선택.
4. 초록 깃발(▶) 클릭으로 시작.

오프라인 에디터([Scratch Desktop](https://scratch.mit.edu/download))에서도 동일하게 열 수 있습니다.

## 🛠 게임 다시 빌드하기

각 게임 폴더에는 `build.py` 가 들어 있습니다. 스프라이트 SVG, 사운드, 블록 코드까지 전부 코드로 정의되어 있어서, 값만 바꾸고 다시 돌리면 새 `.sb3` 가 만들어집니다.

```bash
cd games/polynomial-shooter
python3 build.py
# → 다항함수_게임.sb3 가 갱신됨
```

Python 3.x 만 있으면 외부 라이브러리 없이 돕니다.

## 📂 레포 구조

```
scratch-games-collection/
├── README.md                 ← 이 파일 (게임 모음 소개)
└── games/
    └── polynomial-shooter/   ← 게임 한 개당 폴더 하나
        ├── README.md         ← 게임 설명서
        ├── 다항함수_게임.sb3   ← 바로 플레이 가능한 빌드 결과
        ├── build.py          ← 자동 생성 스크립트
        └── assets/           ← 스프라이트/사운드 원본
```

## ➕ 새 게임 추가하기

1. `games/<game-name>/` 폴더 생성
2. 게임 파일들과 README 작성
3. 위 게임 목록 표에 한 줄 추가

## 📜 라이선스

코드(`build.py`, README): MIT
스프라이트 일부(🚀 🎈)는 [Twemoji](https://github.com/jdecked/twemoji) 사용 (CC-BY 4.0).
