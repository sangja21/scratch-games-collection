# 주인공 보행 애니 시도 — 롤백 방법

실험 내용: 세세한 보행 스프라이트(walk_r0~4 / walk_l0~4) + 이동 시 프레임 사이클.

## 전체 롤백 (한 줄)

```bash
cd games/robot-shooter
cp .rollback/player-walk-attempt/build.py ./build.py
cp .rollback/player-walk-attempt/assets/player*.png assets/gen/
rm -f assets/gen/walk_*.png assets/gen/_walk_preview.png
cp .rollback/player-walk-attempt/로봇_슈터.sb3 ./로봇_슈터.sb3
# 또는 재빌드:
# python3 build.py
```

## 유지하면서 미세조정만 하고 싶을 때

- 프레임 PNG: `assets/gen/walk_r0.png` ~ `walk_r4.png` (l 은 자동 반전본)
- 애니 속도: `build.py` 의 `보행틱` 임계값 (현재 2틱마다 프레임 전환)
- 크기: `looks_setsizeto` SIZE 48
