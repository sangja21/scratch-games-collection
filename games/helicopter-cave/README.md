# 🚁 헬리콥터 동굴 (helicopter-cave)

> 2002 Flash 클래식 「Helicopter Game」 스타일. 스페이스(또는 마우스)를 **꾹** 누르면 헬리콥터가 상승, 떼면 자유낙하. 점점 좁아지는 동굴을 통과해 오래 살아남는다.

## 🎮 조작

- **스페이스 / 마우스 클릭** — 누르고 있으면 상승, 떼면 하강
- 천장·바닥·암벽 막대에 닿으면 게임오버
- 살아남은 1초마다 점수 +1

## 🛠 다시 빌드

```bash
cd games/helicopter-cave
python3 build.py
# → 헬리콥터_동굴.sb3 가 갱신됨
```

## 🧩 구조

- 헬리콥터: x = -150 고정, y 만 변화 (VY 누적 + 매 틱 change y by VY)
- 천장·바닥 막대: 화면 오른쪽(x=260)에서 등장 → 왼쪽으로 스크롤 → x < -260 일 때 클론 삭제
- 두께: 시작 천장40+바닥40 (통과폭 280) → 3초마다 +3씩 늘어나 최대 천장90+바닥90 (통과폭 180)
- 블록 총합 163 (Stage 39 / 헬리콥터 58 / 천장막대 27 / 바닥막대 27 / 게임오버 12)

## 📂 파일

- `헬리콥터_동굴.sb3` — 바로 플레이 가능
- `build.py` — 자동 생성 스크립트 (Python 3.x, 외부 라이브러리 없음)
- `assets/pop.wav` — 게임오버 효과음

## 🧪 검증 (verifier PASS)

- zip 무결성 / project.json 파싱 / 5 targets / 7 자산 / MD5 일치
- Stage 변수 9개 (점수/최고기록/게임상태/VY/천장두께/바닥두께/스크롤속도/스폰주기/경과틱)
- 헬리콥터 메인 루프: keypressed(space) + mousedown + operator_or, VY +0.5/-0.4 둘 다, motion_changeyby, touching 천장막대 + 바닥막대 둘 다, 게임오버 사운드
- Stage 의 `when receive 게임시작` 핸들러 3개 (스폰 / 1초 타이머 / 3초 난이도 ramp)
- 천장막대·바닥막대 클론: motion_changexby + control_start_as_clone + control_delete_this_clone
