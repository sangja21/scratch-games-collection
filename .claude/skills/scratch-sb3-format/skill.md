---
name: scratch-sb3-format
description: Scratch 3.0 .sb3 프로젝트 JSON 포맷 레퍼런스. 블록 opcode, input/field 키, 자산 등록 스키마, 변수/리스트/방송 정의 형식을 담는다. build.py 에서 새 블록 타입을 추가할 때마다 이 스킬을 참조하라.
---

# scratch-sb3-format

## .sb3 zip 구조

```
{한국어이름}.sb3 (zip)
├── project.json         프로젝트 정의 (필수)
├── {md5}.svg            SVG 자산 (코스튬 / 배경)
├── {md5}.wav            WAV 자산 (사운드)
└── ...
```

`project.json` 의 모든 `assetId` 는 해당 md5 해시와 정확히 일치해야 한다.

## project.json 최상위 스키마

```json
{
  "targets": [stage, sprite1, sprite2, ...],
  "monitors": [...],
  "extensions": [],
  "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "..."}
}
```

`targets[0]` 은 반드시 Stage (`isStage: true`).

## Stage 스키마

```json
{
  "isStage": true, "name": "Stage",
  "variables": {"varId": ["변수이름", 초기값], ...},
  "lists": {"listId": ["리스트이름", []], ...},
  "broadcasts": {"brId": "방송이름", ...},
  "blocks": { ... },
  "comments": {},
  "currentCostume": 0,
  "costumes": [{
    "name": "배경", "dataFormat": "svg",
    "assetId": "{md5}", "md5ext": "{md5}.svg",
    "rotationCenterX": 240, "rotationCenterY": 180
  }],
  "sounds": [...],
  "volume": 100, "layerOrder": 0, "tempo": 60,
  "videoTransparency": 50, "videoState": "on",
  "textToSpeechLanguage": null
}
```

## Sprite 스키마

Stage 와 동일한 필드 + 추가:
```
"isStage": false,
"visible": true,
"x": 0, "y": 0, "size": 100, "direction": 90,
"draggable": false, "rotationStyle": "all around" | "left-right" | "don't rotate"
```

## Block 스키마

```json
"{blockId}": {
  "opcode": "...",
  "next": "{nextBlockId}" | null,
  "parent": "{parentBlockId}" | null,
  "inputs": { "KEY": [type, value | shadowId, ...] },
  "fields": { "KEY": ["fieldValue", "fieldId" | null] },
  "shadow": false,
  "topLevel": false,
  "x": 0, "y": 0   // topLevel: true 일 때만
}
```

### Inputs 슬롯 인코딩

- `[1, [4, "42"]]` — 숫자 리터럴
- `[1, [10, "텍스트"]]` — 문자열 리터럴
- `[1, blockId]` — shadow 블록 (broadcast_menu 등)
- `[2, blockId]` — boolean / substack (shadow 없음)
- `[3, blockId, [4, "0"]]` — 변수/식 슬롯 (값은 다른 블록에서, fallback shadow 는 숫자 0)

## 자주 쓰는 Opcode

### Event
| Opcode | 설명 | top |
|--------|------|-----|
| `event_whenflagclicked` | 깃발 클릭 시 | ✓ |
| `event_whenbroadcastreceived` | 방송 받으면, fields: `BROADCAST_OPTION` | ✓ |
| `event_whenkeypressed` | 키 눌렀을 때, fields: `KEY_OPTION` ("space"/"a"/...) | ✓ |
| `event_whenthisspriteclicked` | 스프라이트 클릭 시 | ✓ |
| `event_broadcast` | 방송 보내기, inputs: `BROADCAST_INPUT` |  |
| `event_broadcast_menu` | (shadow) 방송 메뉴 | shadow |

### Control
| Opcode | 설명 |
|--------|------|
| `control_wait` | inputs: `DURATION` |
| `control_repeat` | inputs: `TIMES`, `SUBSTACK` |
| `control_forever` | inputs: `SUBSTACK` |
| `control_if` | inputs: `CONDITION` (boolean), `SUBSTACK` |
| `control_if_else` | inputs: `CONDITION`, `SUBSTACK`, `SUBSTACK2` |
| `control_repeat_until` | inputs: `CONDITION`, `SUBSTACK` |
| `control_wait_until` | inputs: `CONDITION` |
| `control_create_clone_of` | inputs: `CLONE_OPTION` ([1, menu_id]) |
| `control_create_clone_of_menu` | (shadow) fields: `CLONE_OPTION` (["_myself_", null]) |
| `control_start_as_clone` | 클론으로 시작 시 | top |
| `control_delete_this_clone` | 클론 삭제 |

### Motion
| Opcode | 설명 |
|--------|------|
| `motion_gotoxy` | inputs: `X`, `Y` |
| `motion_movesteps` | inputs: `STEPS` |
| `motion_turnright` / `motion_turnleft` | inputs: `DEGREES` |
| `motion_pointindirection` | inputs: `DIRECTION` |
| `motion_changexby` / `motion_changeyby` | inputs: `DX` / `DY` |
| `motion_setx` / `motion_sety` | inputs: `X` / `Y` |
| `motion_glidesecstoxy` | inputs: `SECS`, `X`, `Y` |

### Looks
| Opcode | 설명 |
|--------|------|
| `looks_show` / `looks_hide` | (no inputs) |
| `looks_setsizeto` | inputs: `SIZE` |
| `looks_say` | inputs: `MESSAGE` |
| `looks_switchcostumeto` | inputs: `COSTUME` ([1, costume_menu_id]) |
| `looks_costume` | (shadow) fields: `COSTUME` (["이름", null]) |

### Sensing
| Opcode | 설명 |
|--------|------|
| `sensing_touchingobject` | inputs: `TOUCHINGOBJECTMENU` |
| `sensing_touchingobjectmenu` | (shadow) fields: `TOUCHINGOBJECTMENU` |
| `sensing_keypressed` | inputs: `KEY_OPTION` ([1, menu_id]) |
| `sensing_keyoptions` | (shadow) fields: `KEY_OPTION` |
| `sensing_mousex` / `sensing_mousey` | (no inputs) |
| `sensing_timer` | (no inputs) |
| `sensing_resettimer` | (no inputs) |

### Operators
| Opcode | 설명 |
|--------|------|
| `operator_add` / `subtract` / `multiply` / `divide` | inputs: `NUM1`, `NUM2` |
| `operator_random` | inputs: `FROM`, `TO` |
| `operator_lt` / `gt` / `equals` | inputs: `OPERAND1`, `OPERAND2` |
| `operator_and` / `or` | inputs: `OPERAND1`, `OPERAND2` (boolean, [2, id]) |
| `operator_not` | inputs: `OPERAND` |
| `operator_mod` | inputs: `NUM1`, `NUM2` |
| `operator_round` | inputs: `NUM` |
| `operator_mathop` | inputs: `NUM`, fields: `OPERATOR` ("sin"/"cos"/"tan"/"log"/"ln"/"abs"/"sqrt"/"floor"/"ceiling") |
| `operator_join` | inputs: `STRING1`, `STRING2` |

### Data (변수/리스트)
| Opcode | 설명 |
|--------|------|
| `data_variable` | (reporter, used as slot value) fields: `VARIABLE` (["이름", varId]) |
| `data_setvariableto` | inputs: `VALUE`, fields: `VARIABLE` |
| `data_changevariableby` | inputs: `VALUE`, fields: `VARIABLE` |
| `data_showvariable` / `data_hidevariable` | fields: `VARIABLE` |
| `data_addtolist` | inputs: `ITEM`, fields: `LIST` (["이름", listId]) |
| `data_deletealloflist` | fields: `LIST` |
| `data_itemoflist` | inputs: `INDEX`, fields: `LIST` |
| `data_lengthoflist` | fields: `LIST` |
| `data_replaceitemoflist` | inputs: `INDEX`, `ITEM`, fields: `LIST` |

### Sound
| Opcode | 설명 |
|--------|------|
| `sound_play` | inputs: `SOUND_MENU` ([1, menu_id]) |
| `sound_playuntildone` | inputs: `SOUND_MENU` |
| `sound_stopallsounds` | (no inputs) |
| `sound_seteffectto` | inputs: `VALUE`, fields: `EFFECT` ("PITCH"/"PAN") |
| `sound_sounds_menu` | (shadow) fields: `SOUND_MENU` (["이름", null]) |
| `sound_setvolumeto` | inputs: `VOLUME` |

### Pen (extensions: ["pen"])
| Opcode | 설명 |
|--------|------|
| `pen_clear` | (no inputs) |
| `pen_penDown` / `pen_penUp` | (no inputs) |
| `pen_setPenColorToColor` | inputs: `COLOR` |
| `pen_setPenSizeTo` | inputs: `SIZE` |
| `pen_stamp` | (no inputs) |

펜 사용 시 project.json 최상위 `extensions: ["pen"]`.

## Monitor 스키마

```json
{
  "id": "varId",  // 또는 listId
  "mode": "default" | "large" | "slider" | "list",
  "opcode": "data_variable" | "data_listcontents",
  "params": {"VARIABLE": "변수이름"} | {"LIST": "리스트이름"},
  "spriteName": null,   // sprite-local 변수면 sprite 이름
  "value": 0,
  "width": 0, "height": 0,
  "x": 5, "y": 5,
  "visible": true,
  "sliderMin": 0, "sliderMax": 100, "isDiscrete": true   // 슬라이더만
}
```

## 자주 발생하는 검증 오류

- **`unknown opcode`**: opcode 오타. 위 표에서 정확히 매칭 확인.
- **`Input shape mismatch`**: shadow 가 있어야 할 자리에 `[2, id]`(boolean) 를 넣었거나 그 반대.
- **빨간 변수 블록**: variables 딕셔너리에 ID 가 없거나 `vrep` 의 (name, id) 페어가 stage 의 (name, id) 와 불일치.
- **블록은 보이는데 동작 X**: `parent`/`next` 가 다른 sprite 의 block ID 를 가리킴 (sprite 간 ID 충돌). 각 sprite 의 blocks dict 는 독립 namespace 이지만 ID 는 자주 충돌하므로 `gen()` 카운터를 sprite 간에 공유하는 게 안전.
