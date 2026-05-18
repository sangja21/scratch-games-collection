# 비트 탭 (Beat Tap)

4-lane rhythm game in Scratch 3.0. Hit the falling notes on the judgment line by pressing the matching key.

## 빌드

```bash
python3 build.py
```

`비트_탭.sb3` 가 같은 폴더에 만들어진다. Scratch 에디터(또는 [TurboWarp](https://turbowarp.org/))에 드래그하면 바로 열린다.

## 조작

| 키 | 레인 |
|----|------|
| `D` | 1 (가장 왼쪽) |
| `F` | 2 |
| `J` | 3 |
| `K` | 4 (가장 오른쪽) |

## 판정 / 점수

- **Perfect** (±0.06초): +100점, 콤보 +1
- **Good** (0.06 ~ 0.13초): +50점, 콤보 +1
- **Miss** (0.16초 이상): 콤보 0으로 초기화

좌상단 모니터에 점수 / 콤보 / 최대 콤보가, 우상단에 마지막 판정 텍스트가 나온다.

## 게임 흐름

1. 초록 깃발 클릭 → 차트 데이터를 stage 리스트(`채보시각`, `채보레인`)로 로드, BGM 시작
2. 메인 루프(0.02초마다)가 `곡시간`을 증가시키면서, 등장 시각 `FALL_TIME(1.5초)` 전이 되면 음표를 클론으로 띄움
3. 클론은 위 y=180 → 아래 y=-130까지 1.5초 동안 일정 속도로 낙하
4. 판정선(y=-130)에 도달하기 전후로 키를 누르면 판정
5. 채보 끝나고 2초 뒤 게임 종료 → "CLEAR!" 배너 표시

## 채보 / 곡 길이

기본 채보는 BPM 120, 16마디, 총 **84개 음표 / 약 36초**. `build.py` 의 `build_chart()` 함수에서 패턴 단위로 수정할 수 있다.

차트 시작은 t=2.0초로 설정 — BGM 재생과 첫 음표 등장 사이에 1.5초 낙하 시간 + 0.5초 버퍼를 둠.

## BGM / 사운드

BGM, tick(hit), miss 세 사운드는 **build.py 실행 시 그 자리에서 합성**된다 (Python `wave` 모듈, 22050Hz/16비트 mono).

- `tick.wav` — 1500Hz 짧은 사인파 + 하모닉, 감쇠 → Perfect/Good 히트에 재생
- `miss.wav` — 180Hz 저주파 thud
- `bgm.wav` — 채보의 각 음표 시각에 4개 음(C4/E4/G4/C5)의 사각파 + 4박자 베이스라인 + 8분음표 하이햇

## 타이밍 보정

Scratch 의 `start sound` 와 `change V_TIME by 0.02 / wait 0.02` 사이에는 OS 오디오 큐 지연이 있어 시청각이 어긋날 수 있다.

`오디오오프셋` (stage 변수, slider monitor, 기본 0.0) 을 두었으나 현재 코드에는 오프셋을 자동 적용하는 로직이 없다. 시청각이 어긋나 보이면:
- BGM 이 너무 빠르다 (음표가 도착하기 전에 들린다) → 채보의 t0(현재 2.0초) 를 올리거나 `gen_bgm_wav` 의 톤 위치를 늦춤
- BGM 이 너무 느리다 → 반대

또한, `FALL_TIME` / `WIN_PERFECT` / `WIN_GOOD` / `WIN_MISS_AFTER` 모두 `build.py` 상단에서 튜닝 가능.

## 알려진 제약

- 노래 끝나고 결과 배너는 단일 "CLEAR!" 만 보여줌. 최대 콤보 / 점수는 좌상단 모니터로 확인.
- 한 곡 끝나면 다시 깃발 눌러야 새로 시작 (자동 재시작 없음).
- TurboWarp 의 가속 모드에서는 V_TIME 이 빠르게 흘러 BGM 과 어긋날 수 있음 — 일반 속도로 플레이.

## 파일

```
beat-tap/
├── build.py           # 빌드 스크립트 (이 README 와 같이 보면 좋음)
├── README.md
├── assets/            # build 가 생성한 SVG/WAV 사본 (디버그/검수용)
│   ├── background.svg
│   ├── note_normal.svg / note_perfect.svg / note_good.svg / note_miss.svg
│   ├── result.svg
│   ├── tick.wav / miss.wav / bgm.wav
└── 비트_탭.sb3        # 빌드 출력
```
