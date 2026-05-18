---
name: scratch-game-template
description: Scratch 3.0 .sb3 빌드용 build.py 의 공통 패턴·헬퍼·스켈레톤을 제공. games/*/build.py 를 새로 작성하거나 수정할 때 반드시 이 스킬을 참조하라. SVG 자산, 블록 빌더, project.json 조립, zip 출력의 검증된 패턴을 담고 있다.
---

# scratch-game-template

build.py 를 새로 작성할 때 따라야 할 공통 구조와 헬퍼 함수 모음. 기존 6개 게임에서 추출한 검증된 패턴.

## 파일 골격

```python
#!/usr/bin/env python3
"""{게임 이름} — {한 줄 설명}."""
import json, os, wave, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "{한국어이름}.sb3")

# --- SVG assets (인라인 Python 문자열) ---
BG_SVG = """<svg ...>...</svg>"""
SPRITE_SVG = """<svg ...>...</svg>"""

# --- 필수 헬퍼 (절대 재구현 금지, 그대로 복사) ---
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n):  return [1, [4, str(n)]]
def text_lit(s): return [1, [10, str(s)]]
def slot(bid, sk=4, sv="0"): return [3, bid, [sk, str(sv)]]

def mk(opcode, *, parent=None, next_=None, inputs=None, fields=None,
       top=False, x=0, y=0, shadow=False):
    b = {"opcode": opcode, "next": next_, "parent": parent,
         "inputs": inputs or {}, "fields": fields or {},
         "shadow": shadow, "topLevel": top}
    if top: b["x"] = x; b["y"] = y
    return b

_ic = [0]
def gen():
    _ic[0] += 1
    return f"b{_ic[0]:04d}"

def chain(seq):
    """seq = [(id, block), ...] — 인접한 두 블록을 next/parent 로 연결."""
    for i in range(len(seq)-1):
        cid, c = seq[i]; nid, n = seq[i+1]
        c["next"] = nid; n["parent"] = cid

def make_helpers(bs):
    """sprite-local block dict bs 에 대한 vrep/op/bool_op/cmp_op 클로저 반환."""
    def vrep(name, vid):
        bid = gen()
        bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid
    def op(opcode, a, b_, key1="NUM1", key2="NUM2"):
        bid = gen()
        ins = {}
        for key, val in [(key1, a), (key2, b_)]:
            if isinstance(val, str): ins[key] = slot(val)
            else: ins[key] = num(val)
        bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): bs[v]["parent"] = bid
        return bid
    def bool_op(opcode, a, b_):
        bid = gen()
        bs[bid] = mk(opcode, inputs={"OPERAND1": [2, a], "OPERAND2": [2, b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid
        return bid
    def cmp_op(opcode, a, b_):
        bid = gen()
        ins = {}
        for key, val in [("OPERAND1", a), ("OPERAND2", b_)]:
            if isinstance(val, str): ins[key] = slot(val)
            else: ins[key] = num(val)
        bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): bs[v]["parent"] = bid
        return bid
    return vrep, op, bool_op, cmp_op

# --- 변수/방송/리스트 ID 상수 (상단 정의 권장) ---
V_SCORE = "varScore001"
V_TIME  = "varTime002"
BR_START = "brStart001"
L_NOTES  = "listNotes001"

# --- 스프라이트별 블록 빌더 함수 ---
def build_stage_blocks():
    bs = {}
    vrep, op, bool_op, cmp_op = make_helpers(bs)
    # ... 블록 정의
    return bs

def build_player_blocks():
    bs = {}
    vrep, op, bool_op, cmp_op = make_helpers(bs)
    # ...
    return bs

# --- 조립 ---
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # 1. SVG 자산 MD5 해시 → .build/ 에 저장
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)
    # ... 다른 SVG 도 동일

    # 2. WAV 자산 (assets/ 에서 읽음)
    # pop_src = f"{ASSETS}/pop.wav"
    # with open(pop_src, "rb") as f: pop_bytes = f.read()
    # pop_md5 = md5_bytes(pop_bytes)
    # with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    # 3. project.json 조립
    stage = {
        "isStage": True, "name": "Stage",
        "variables": {V_SCORE: ["점수", 0], V_TIME: ["시간", 60]},
        "lists": {},
        "broadcasts": {BR_START: "게임시작"},
        "blocks": build_stage_blocks(), "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "배경", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    sprite = {
        "isStage": False, "name": "플레이어",
        "variables": {},
        "lists": {}, "broadcasts": {},
        "blocks": build_player_blocks(), "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "기본", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": "...", "md5ext": "....svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    monitors = [
        {"id": V_SCORE, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, sprite],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "{slug}-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)  # validate
    print(f"✓ wrote {OUTPUT}")

if __name__ == "__main__":
    main()
```

## 좌표 변환 규칙

SVG 좌표 (왼쪽 위 (0,0), 오른쪽 아래 (480,360)) ↔ Scratch 무대 좌표 (가운데 (0,0), -240~240 / -180~180):

```
scratch_x = svg_x - 240
scratch_y = 180 - svg_y
```

## 자산 등록 패턴 (왜 MD5 인가)

Scratch .sb3 zip 안의 모든 자산 파일은 **MD5 해시값.확장자** 형식이어야 한다. project.json 의 `costumes[].assetId` 가 해시값과 일치해야 Scratch 가 자산을 찾는다.

SVG는 `md5_bytes(svg_str.encode("utf-8"))`, WAV 는 바이트 그대로 해싱.

## 흔한 함정

| 함정 | 증상 | 해결 |
|------|------|------|
| `chain()` 빠뜨림 | 게임 시작해도 첫 블록만 실행 | 모든 순차 블록을 `chain([(id1,b1),(id2,b2),...])` 로 연결 |
| 자식 블록의 `parent` 미설정 | Scratch 가 블록을 표시 못 함 | `bs[child]["parent"] = parent_id` 명시 |
| `variables` 누락 | 변수 사용 블록이 빨갛게 표시됨 | stage 또는 sprite 의 `variables` 딕셔너리에 모든 ID 정의 |
| `shadow: true` 인 메뉴 블록의 parent 미설정 | 메뉴 드롭다운 빈 칸 | broadcast_menu / sounds_menu / clone_menu 의 parent 를 부모 블록 ID 로 |
| input 키 이름 오타 | 블록은 보이지만 동작 안 함 | `scratch-sb3-format` 의 opcode 별 input 키 표 확인 |
| 한국어 이름과 ID 의 페어링 누락 | 변수 모니터에 변수 이름이 안 뜸 | `variables: {V_SCORE: ["점수", 0]}` 처럼 [한국어이름, 초기값] 쌍 |

## 블록 입력 형식 (간단 cheatsheet)

- **숫자 리터럴 입력**: `inputs={"VALUE": num(42)}` → `[1, [4, "42"]]`
- **텍스트 리터럴 입력**: `inputs={"MESSAGE": text_lit("안녕")}` → `[1, [10, "안녕"]]`
- **변수/식 슬롯 입력** (값을 다른 블록에서): `slot(child_id)` → `[3, child_id, [4, "0"]]`
- **boolean 슬롯 입력** (and/or/not/비교): `[2, child_id]` (shadow 없음)
- **substack 입력** (if/repeat 안의 블록 묶음): `[2, first_block_id]`
- **broadcast 입력**: shadow `event_broadcast_menu` 만들고 `[1, menu_id]`

## 게임별 패턴 매칭

새 게임을 만들 때 가장 가까운 기존 게임을 골라 시작:

| 새 게임 메커닉 | 베이스로 좋은 기존 게임 |
|--------------|---------------------|
| 클릭으로 클론 제거 | `whack-a-prime`, `bacteria-defense` |
| 슬라이더로 곡선 조절 | `polynomial-shooter`, `exponential-shooter` |
| 격자 적 + 슈팅 | `alien-invasion` |
| 리스트 기반 타이밍 (음표/이벤트) | `beat-tap` |
| 매 틱마다 자가 분열/성장 | `bacteria-defense` |
| 키보드(여러 키) + 판정선 | `beat-tap` |

## 참고

- 추가 opcode·input 키 사양: `scratch-sb3-format` 스킬
- 빌드 후 검증 절차: `scratch-verification` 스킬
- 기존 build.py 예시: `games/whack-a-prime/build.py` (가장 단순), `games/bacteria-defense/build.py` (클론 분열), `games/exponential-shooter/build.py` (슬라이더+곡선)
