#!/usr/bin/env python3
"""테트리스 미니 (tetris-mini) — 7종 테트로미노가 8×14 보드 위로 떨어진다.

←/→ 이동, ↑ 회전, ↓ 소프트드롭, space 하드드롭. 가로줄이 꽉 차면 사라지고
점수 +. 천장까지 쌓이면 게임오버.

베이스: games/snake/build.py (리스트로 게임 상태 표현 + make_list_helpers,
클론이 리스트 항목을 읽어 위치를 잡는 패턴) + games/breakout 의 클론 격자.

이 빌드는 snake 골격에 추가로:
  (1) make_list_helpers 에 replace_at (data_replaceitemoflist) 추가
  (2) my block(procedures_definition/prototype/call) 지원 추가 — 충돌?/고정
  (3) 보드(112)/오프셋C(112)/오프셋R(112) 리스트를 contents 로 직접 임베드
를 구현한다.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "테트리스미니.sb3")

# ============================================================
#  피스 오프셋 데이터 (6.4절) — 7피스 × 4회전 × 4셀 = 112
#  각 셀 = 기준칸(현열,현행) 대비 (dc, dr). dc 오른쪽 +, dr 아래쪽 +.
# ============================================================
OFFSETS = [
    # I (피스1)
    [(0,1),(1,1),(2,1),(3,1)], [(2,0),(2,1),(2,2),(2,3)], [(0,2),(1,2),(2,2),(3,2)], [(1,0),(1,1),(1,2),(1,3)],
    # O (피스2)
    [(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)],
    # T (피스3)
    [(1,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(2,1),(1,2)], [(0,1),(1,1),(2,1),(1,2)], [(1,0),(0,1),(1,1),(1,2)],
    # S (피스4)
    [(1,0),(2,0),(0,1),(1,1)], [(1,0),(1,1),(2,1),(2,2)], [(1,1),(2,1),(0,2),(1,2)], [(0,0),(0,1),(1,1),(1,2)],
    # Z (피스5)
    [(0,0),(1,0),(1,1),(2,1)], [(2,0),(1,1),(2,1),(1,2)], [(0,1),(1,1),(1,2),(2,2)], [(1,0),(0,1),(1,1),(0,2)],
    # J (피스6)
    [(0,0),(0,1),(1,1),(2,1)], [(1,0),(2,0),(1,1),(1,2)], [(0,1),(1,1),(2,1),(2,2)], [(1,0),(1,1),(0,2),(1,2)],
    # L (피스7)
    [(2,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(1,2),(2,2)], [(0,1),(1,1),(2,1),(0,2)], [(0,0),(1,0),(1,1),(1,2)],
]
assert len(OFFSETS) == 28
offC = [c for grp in OFFSETS for (c, r) in grp]   # 길이 112
offR = [r for grp in OFFSETS for (c, r) in grp]   # 길이 112
assert len(offC) == 112 and len(offR) == 112

# ============================================================
#  SVG assets
# ============================================================
# 보드 좌상단 칸(col0,row0) 중심 무대좌표 = (-150, 143). 칸 22px.
# SVG 좌표: svg_x = scratch_x + 240, svg_y = 180 - scratch_y.
# col0 중심 scratch x=-150 -> svg 90 ; row0 중심 scratch y=143 -> svg 37.
# 셀은 20px, 칸 22px -> 셀 좌상단(중심에서 -10): col0 svg x 80, row0 svg y 27.
# 보드 외곽: 8열*22=176 폭, 14행*22=308 높이. 좌상단 svg (79, 26) 근처.
PIECE_COLORS = ["#00BCD4", "#FFEB3B", "#9C27B0", "#4CAF50", "#F44336", "#2196F3", "#FF9800"]
PIECE_STROKES = ["#00838F", "#FBC02D", "#6A1B9A", "#2E7D32", "#B71C1C", "#1565C0", "#E65100"]

def _grid_lines():
    """보드 영역 옅은 격자선 (22px 간격)."""
    lines = []
    bx0, by0 = 79, 26          # 보드 좌상단 svg
    w, h = 176, 308
    for c in range(9):         # 세로선 9개 (0..8)
        x = bx0 + c * 22
        lines.append(f'    <line x1="{x}" y1="{by0}" x2="{x}" y2="{by0+h}" stroke="#283593" stroke-width="1"/>')
    for r in range(15):        # 가로선 15개 (0..14)
        y = by0 + r * 22
        lines.append(f'    <line x1="{bx0}" y1="{y}" x2="{bx0+w}" y2="{y}" stroke="#283593" stroke-width="1"/>')
    return "\n".join(lines)

def _next_box():
    """오른쪽 NEXT 미리보기 박스 (4×4 칸, 22px). 좌상단 svg (320, 60)."""
    nx0, ny0 = 320, 60
    return (f'    <rect x="{nx0}" y="{ny0}" width="{4*22}" height="{4*22}" '
            f'fill="#0D1330" stroke="#FFFFFF" stroke-width="2"/>')

BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect x="0" y="0" width="480" height="360" fill="#101840"/>
  <!-- 보드 외곽 -->
  <rect x="79" y="26" width="176" height="308" fill="#0A1030" stroke="#FFFFFF" stroke-width="3"/>
  <!-- 격자선 -->
  <g>
__GRID__
  </g>
  <!-- NEXT 패널 -->
  <text x="320" y="50" fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="bold">NEXT</text>
__NEXTBOX__
  <text x="295" y="190" fill="#90CAF9" font-family="Arial, Helvetica, sans-serif" font-size="14">←/→ 이동</text>
  <text x="295" y="212" fill="#90CAF9" font-family="Arial, Helvetica, sans-serif" font-size="14">↑ 회전</text>
  <text x="295" y="234" fill="#90CAF9" font-family="Arial, Helvetica, sans-serif" font-size="14">↓ 빨리 / space 떨구기</text>
</svg>""".replace("__GRID__", _grid_lines()).replace("__NEXTBOX__", _next_box())

def _cell_svg(fill, stroke):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <rect x="1" y="1" width="18" height="18" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
  <rect x="3.5" y="3.5" width="8" height="8" rx="2" fill="#FFFFFF" opacity="0.28"/>
</svg>"""

CELL_SVGS = [_cell_svg(PIECE_COLORS[i], PIECE_STROKES[i]) for i in range(7)]

GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#000000" opacity="0.92" stroke="#2196F3" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle" fill="#42A5F5"
        font-family="Arial, Helvetica, sans-serif" font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF"
        font-family="Arial, Helvetica, sans-serif" font-size="18">블록이 천장까지 쌓였어요</text>
  <text x="180" y="138" text-anchor="middle" fill="#81D4FA"
        font-family="Arial, Helvetica, sans-serif" font-size="13">초록 깃발(▶) 다시 클릭으로 재시작</text>
</svg>"""

# ============================================================
#  helpers (snake build.py 와 동일 — 그대로 복제)
# ============================================================
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n):  return [1, [4, str(n)]]
def text_lit(s): return [1, [10, str(s)]]
def slot(bid, sk=4, sv="0"): return [3, bid, [sk, str(sv)]]

def mk(opcode, *, parent=None, next_=None, inputs=None, fields=None,
       top=False, x=0, y=0, shadow=False, mutation=None):
    b = {"opcode": opcode, "next": next_, "parent": parent,
         "inputs": inputs or {}, "fields": fields or {},
         "shadow": shadow, "topLevel": top}
    if top: b["x"] = x; b["y"] = y
    if mutation is not None: b["mutation"] = mutation
    return b

_ic = [0]
def gen():
    _ic[0] += 1
    return f"b{_ic[0]:04d}"

def chain(seq):
    for i in range(len(seq)-1):
        cid, c = seq[i]; nid, n = seq[i+1]
        c["next"] = nid; n["parent"] = cid

def make_helpers(bs):
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
    def bool_op(opcode, a, b_):
        bid = gen()
        bs[bid] = mk(opcode, inputs={"OPERAND1":[2,a],"OPERAND2":[2,b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid
        return bid
    return vrep, op, cmp_op, bool_op

# ---- list block helpers (snake + replace_at 추가) ----
def make_list_helpers(bs):
    def add_to(name, lid, item):
        bid = gen()
        ins = {"ITEM": slot(item) if isinstance(item, str) else text_lit(item)}
        bs[bid] = mk("data_addtolist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(item, str): bs[item]["parent"] = bid
        return bid

    def delete_all(name, lid):
        bid = gen()
        bs[bid] = mk("data_deletealloflist", fields={"LIST": [name, lid]})
        return bid

    def item_of(name, lid, index):
        bid = gen()
        ins = {"INDEX": slot(index) if isinstance(index, str) else text_lit(index)}
        bs[bid] = mk("data_itemoflist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(index, str): bs[index]["parent"] = bid
        return bid

    def length_of(name, lid):
        bid = gen()
        bs[bid] = mk("data_lengthoflist", fields={"LIST": [name, lid]})
        return bid

    def replace_at(name, lid, index, item):
        """replace item INDEX of LIST with ITEM. (data_replaceitemoflist)"""
        bid = gen()
        ins = {
            "INDEX": slot(index) if isinstance(index, str) else text_lit(index),
            "ITEM":  slot(item)  if isinstance(item, str)  else text_lit(item),
        }
        bs[bid] = mk("data_replaceitemoflist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(index, str): bs[index]["parent"] = bid
        if isinstance(item, str):  bs[item]["parent"] = bid
        return bid

    return add_to, delete_all, item_of, length_of, replace_at

# ---- my block (custom procedure) helpers ----
def make_proc_def(bs, proccode, warp=True):
    """인자 없는 커스텀 블록 정의 hat 을 만든다.
    반환: (def_id, proto_id)  — def_id 가 hat(top), 본문은 def_id 의 next 로 연결."""
    proto_id = gen()
    def_id   = gen()
    mut = {
        "tagName": "mutation", "children": [],
        "proccode": proccode,
        "argumentids": "[]", "argumentnames": "[]", "argumentdefaults": "[]",
        "warp": "true" if warp else "false",
    }
    bs[proto_id] = mk("procedures_prototype",
                      inputs={}, shadow=True, mutation=dict(mut))
    bs[proto_id]["parent"] = def_id
    bs[def_id] = mk("procedures_definition", top=True,
                    inputs={"custom_block": [1, proto_id]})
    return def_id, proto_id

def make_proc_call(bs, proccode, warp=True):
    bid = gen()
    mut = {
        "tagName": "mutation", "children": [],
        "proccode": proccode,
        "argumentids": "[]", "argumentnames": "[]", "argumentdefaults": "[]",
        "warp": "true" if warp else "false",
    }
    bs[bid] = mk("procedures_call", inputs={}, mutation=mut)
    return bid

# ============================================================
#  IDs
# ============================================================
# 글로벌 변수
V_SCORE   = "varScore01"
V_BEST    = "varBest02"
V_STATE   = "varState03"
V_LINES   = "varLines04"
V_LEVEL   = "varLevel05"
V_DROP    = "varDrop06"
V_PIECE   = "varPiece07"
V_ROT     = "varRot08"
V_COL     = "varCol09"
V_ROW     = "varRow10"
V_NEXT    = "varNext11"
V_CLEARED = "varCleared12"
# 판정기 sprite-local
V_TCOL    = "varTestCol13"
V_TROW    = "varTestRow14"
V_TROT    = "varTestRot15"
V_CELLCOL = "varCellCol16"
V_CELLROW = "varCellRow17"
V_CELLIDX = "varCellIdx18"
V_I       = "varI19"
V_J       = "varJ20"
V_OFFBASE = "varOffBase21"
V_HIT     = "varHit22"
V_ROWFULL = "varRowFull23"
# 현재블록 sprite-local
V_SEG     = "varSeg24"
# 현재블록 sprite-local 그리기 임시 (충돌의도와 안 겹치게 별도)
V_CUR_OFFBASE = "varCurOff27"
V_CUR_CELLCOL = "varCurCol28"
V_CUR_CELLROW = "varCurRow29"
# 보드셀 sprite-local
V_DRAWIDX = "varDrawIdx25"
V_DRAWCOL = "varDrawColor26"

# 리스트
L_BOARD = "L_board01"
L_OFFC  = "L_offC02"
L_OFFR  = "L_offR03"
L_CURX  = "L_curX04"
L_CURY  = "L_curY05"

# broadcasts
BR_START    = "brStart01"
BR_TICK     = "brTick02"
BR_SPAWN    = "brSpawn03"
BR_DRAWCUR  = "brDrawCur04"
BR_DRAWBRD  = "brDrawBoard05"
BR_CLEARC   = "brClearCells06"

# 좌표 상수
BOARD_X0 = -150
BOARD_Y0 = 143
CELL = 22

# proccodes
PC_HIT = "충돌?"
PC_LOCK = "고정"

# ============================================================
#  공용 broadcast 빌더
# ============================================================
def broadcast(bs, name, brid):
    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    bc = gen(); bs[bc] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm]})
    bs[bm]["parent"] = bc
    return bc

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    add_to, delete_all, item_of, length_of, replace_at = make_list_helpers(bs)

    # === when flag clicked: init vars + 보드/리스트 초기화 + broadcast ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]

    inits = [
        ("점수", V_SCORE, 0),
        ("게임상태", V_STATE, 1),
        ("줄수", V_LINES, 0),
        ("레벨", V_LEVEL, 1),
        ("낙하간격", V_DROP, 0.8),
        ("현회전", V_ROT, 0),
        ("현열", V_COL, 3),
        ("현행", V_ROW, 0),
        ("지운줄카운트", V_CLEARED, 0),
    ]
    for name, vid, val in inits:
        sid = gen()
        bs[sid] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
        seq.append((sid, bs[sid]))

    # 현피스 = random 1..7 ; 다음피스 = random 1..7
    r1 = gen(); bs[r1] = mk("operator_random", inputs={"FROM": num(1), "TO": num(7)})
    sp = gen(); bs[sp] = mk("data_setvariableto",
        inputs={"VALUE": slot(r1)}, fields={"VARIABLE": ["현피스", V_PIECE]})
    bs[r1]["parent"] = sp
    seq.append((sp, bs[sp]))
    r2 = gen(); bs[r2] = mk("operator_random", inputs={"FROM": num(1), "TO": num(7)})
    sn = gen(); bs[sn] = mk("data_setvariableto",
        inputs={"VALUE": slot(r2)}, fields={"VARIABLE": ["다음피스", V_NEXT]})
    bs[r2]["parent"] = sn
    seq.append((sn, bs[sn]))

    # 보드 112칸 0 으로: delete all 보드 ; repeat 112: add 0 to 보드
    da_b = delete_all("보드", L_BOARD)
    seq.append((da_b, bs[da_b]))
    add0 = add_to("보드", L_BOARD, 0)
    rep_b = gen(); bs[rep_b] = mk("control_repeat",
        inputs={"TIMES": num(112), "SUBSTACK": [2, add0]})
    bs[add0]["parent"] = rep_b
    seq.append((rep_b, bs[rep_b]))

    # broadcast 게임시작 ; broadcast 새블록
    bc_start = broadcast(bs, "게임시작", BR_START)
    seq.append((bc_start, bs[bc_start]))
    bc_spawn = broadcast(bs, "새블록", BR_SPAWN)
    seq.append((bc_spawn, bs[bc_spawn]))

    chain(seq)

    # === when receive 게임시작: 중력 타이머 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    state_a = vrep("게임상태", V_STATE)
    cond_over_a = cmp_op("operator_equals", state_a, 0)
    bc_tick = broadcast(bs, "브틱", BR_TICK)
    drop_v = vrep("낙하간격", V_DROP)
    wt_tick = gen(); bs[wt_tick] = mk("control_wait", inputs={"DURATION": slot(drop_v)})
    bs[drop_v]["parent"] = wt_tick
    chain([(bc_tick, bs[bc_tick]), (wt_tick, bs[wt_tick])])
    rep_a = gen(); bs[rep_a] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over_a], "SUBSTACK": [2, bc_tick]})
    bs[cond_over_a]["parent"] = rep_a
    bs[bc_tick]["parent"] = rep_a
    chain([(h2, bs[h2]), (rep_a, bs[rep_a])])

    # === when receive 게임시작: 레벨/속도 ramp ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    state_b = vrep("게임상태", V_STATE)
    cond_over_b = cmp_op("operator_equals", state_b, 0)

    # 레벨 = floor(줄수 / 5) + 1
    lines_v = vrep("줄수", V_LINES)
    div5 = op("operator_divide", lines_v, 5)
    floor_l = gen(); bs[floor_l] = mk("operator_mathop",
        inputs={"NUM": slot(div5)}, fields={"OPERATOR": ["floor", None]})
    bs[div5]["parent"] = floor_l
    plus1 = gen(); bs[plus1] = mk("operator_add",
        inputs={"NUM1": slot(floor_l), "NUM2": num(1)})
    bs[floor_l]["parent"] = plus1
    set_level = gen(); bs[set_level] = mk("data_setvariableto",
        inputs={"VALUE": slot(plus1)}, fields={"VARIABLE": ["레벨", V_LEVEL]})
    bs[plus1]["parent"] = set_level

    # 낙하간격 = 0.8 - (레벨-1)*0.1
    level_v = vrep("레벨", V_LEVEL)
    sub_lv = gen(); bs[sub_lv] = mk("operator_subtract",
        inputs={"NUM1": slot(level_v), "NUM2": num(1)})
    bs[level_v]["parent"] = sub_lv
    mul_lv = gen(); bs[mul_lv] = mk("operator_multiply",
        inputs={"NUM1": slot(sub_lv), "NUM2": num(0.1)})
    bs[sub_lv]["parent"] = mul_lv
    set_drop = gen(); bs[set_drop] = mk("operator_subtract",
        inputs={"NUM1": num(0.8), "NUM2": slot(mul_lv)})
    bs[mul_lv]["parent"] = set_drop
    setd = gen(); bs[setd] = mk("data_setvariableto",
        inputs={"VALUE": slot(set_drop)}, fields={"VARIABLE": ["낙하간격", V_DROP]})
    bs[set_drop]["parent"] = setd

    # if 낙하간격 < 0.12: 낙하간격 = 0.12
    drop_r = vrep("낙하간격", V_DROP)
    cond_clamp = cmp_op("operator_lt", drop_r, 0.12)
    set_clamp = gen(); bs[set_clamp] = mk("data_setvariableto",
        inputs={"VALUE": num(0.12)}, fields={"VARIABLE": ["낙하간격", V_DROP]})
    if_clamp = gen(); bs[if_clamp] = mk("control_if",
        inputs={"CONDITION": [2, cond_clamp], "SUBSTACK": [2, set_clamp]})
    bs[cond_clamp]["parent"] = if_clamp
    bs[set_clamp]["parent"] = if_clamp

    wt_r = gen(); bs[wt_r] = mk("control_wait", inputs={"DURATION": num(0.2)})
    chain([(set_level, bs[set_level]), (setd, bs[setd]),
           (if_clamp, bs[if_clamp]), (wt_r, bs[wt_r])])
    rep_b2 = gen(); bs[rep_b2] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over_b], "SUBSTACK": [2, set_level]})
    bs[cond_over_b]["parent"] = rep_b2
    bs[set_level]["parent"] = rep_b2
    chain([(h3, bs[h3]), (rep_b2, bs[rep_b2])])

    return bs

# ============================================================
#  블록판정기 (logic sprite, hidden)
# ============================================================
def build_logic_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    add_to, delete_all, item_of, length_of, replace_at = make_list_helpers(bs)

    # ---------- helper: 오프베이스 set 식 ((piece-1)*4 + rot)*4 ----------
    def set_offbase(rot_vid, rot_name):
        """오프베이스 = ((현피스-1)*4 + rot)*4 ; returns set block id."""
        piece_v = vrep("현피스", V_PIECE)
        sub_p = gen(); bs[sub_p] = mk("operator_subtract",
            inputs={"NUM1": slot(piece_v), "NUM2": num(1)})
        bs[piece_v]["parent"] = sub_p
        mul_p = gen(); bs[mul_p] = mk("operator_multiply",
            inputs={"NUM1": slot(sub_p), "NUM2": num(4)})
        bs[sub_p]["parent"] = mul_p
        rot_v = vrep(rot_name, rot_vid)
        add_r = gen(); bs[add_r] = mk("operator_add",
            inputs={"NUM1": slot(mul_p), "NUM2": slot(rot_v)})
        bs[mul_p]["parent"] = add_r; bs[rot_v]["parent"] = add_r
        mul4 = gen(); bs[mul4] = mk("operator_multiply",
            inputs={"NUM1": slot(add_r), "NUM2": num(4)})
        bs[add_r]["parent"] = mul4
        setb = gen(); bs[setb] = mk("data_setvariableto",
            inputs={"VALUE": slot(mul4)}, fields={"VARIABLE": ["오프베이스", V_OFFBASE]})
        bs[mul4]["parent"] = setb
        return setb

    # =========================================================
    #  define 충돌?  (run without screen refresh)
    # =========================================================
    def_hit, _ = make_proc_def(bs, PC_HIT, warp=True)

    # 충돌됨 = 0
    set_hit0 = gen(); bs[set_hit0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["충돌됨", V_HIT]})
    # 오프베이스 = ((현피스-1)*4 + 시험회전)*4
    set_ob = set_offbase(V_TROT, "시험회전")
    # i = 1
    set_i1 = gen(); bs[set_i1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["i", V_I]})

    # --- repeat 4 본문 ---
    # 셀col = 시험열 + item(오프베이스+i) of 오프셋C
    tcol_v = vrep("시험열", V_TCOL)
    ob_v1 = vrep("오프베이스", V_OFFBASE); i_v1 = vrep("i", V_I)
    obi1 = gen(); bs[obi1] = mk("operator_add",
        inputs={"NUM1": slot(ob_v1), "NUM2": slot(i_v1)})
    bs[ob_v1]["parent"] = obi1; bs[i_v1]["parent"] = obi1
    offc1 = item_of("오프셋C", L_OFFC, obi1)
    add_cc = gen(); bs[add_cc] = mk("operator_add",
        inputs={"NUM1": slot(tcol_v), "NUM2": slot(offc1)})
    bs[tcol_v]["parent"] = add_cc; bs[offc1]["parent"] = add_cc
    set_cc = gen(); bs[set_cc] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_cc)}, fields={"VARIABLE": ["셀col", V_CELLCOL]})
    bs[add_cc]["parent"] = set_cc

    # 셀row = 시험행 + item(오프베이스+i) of 오프셋R
    trow_v = vrep("시험행", V_TROW)
    ob_v2 = vrep("오프베이스", V_OFFBASE); i_v2 = vrep("i", V_I)
    obi2 = gen(); bs[obi2] = mk("operator_add",
        inputs={"NUM1": slot(ob_v2), "NUM2": slot(i_v2)})
    bs[ob_v2]["parent"] = obi2; bs[i_v2]["parent"] = obi2
    offr1 = item_of("오프셋R", L_OFFR, obi2)
    add_cr = gen(); bs[add_cr] = mk("operator_add",
        inputs={"NUM1": slot(trow_v), "NUM2": slot(offr1)})
    bs[trow_v]["parent"] = add_cr; bs[offr1]["parent"] = add_cr
    set_cr = gen(); bs[set_cr] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_cr)}, fields={"VARIABLE": ["셀row", V_CELLROW]})
    bs[add_cr]["parent"] = set_cr

    # if (셀col<0) OR (셀col>7) OR (셀row>13): 충돌됨=1  else: { if 셀row>=0: ... }
    cc1 = vrep("셀col", V_CELLCOL); c_lt0 = cmp_op("operator_lt", cc1, 0)
    cc2 = vrep("셀col", V_CELLCOL); c_gt7 = cmp_op("operator_gt", cc2, 7)
    cr1 = vrep("셀row", V_CELLROW); c_rgt13 = cmp_op("operator_gt", cr1, 13)
    or_a = bool_op("operator_or", c_lt0, c_gt7)
    or_wall = bool_op("operator_or", or_a, c_rgt13)
    set_hit1 = gen(); bs[set_hit1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["충돌됨", V_HIT]})

    # else branch: if 셀row>=0 (=NOT 셀row<0): 셀idx=셀row*8+셀col+1 ; if item(셀idx) of 보드 != 0: 충돌됨=1
    cr2 = vrep("셀row", V_CELLROW)
    c_rlt0 = cmp_op("operator_lt", cr2, 0)
    not_rlt0 = gen(); bs[not_rlt0] = mk("operator_not", inputs={"OPERAND": [2, c_rlt0]})
    bs[c_rlt0]["parent"] = not_rlt0

    # 셀idx = 셀row*8 + 셀col + 1
    cr3 = vrep("셀row", V_CELLROW)
    mul8 = gen(); bs[mul8] = mk("operator_multiply",
        inputs={"NUM1": slot(cr3), "NUM2": num(8)})
    bs[cr3]["parent"] = mul8
    cc3 = vrep("셀col", V_CELLCOL)
    add_idx1 = gen(); bs[add_idx1] = mk("operator_add",
        inputs={"NUM1": slot(mul8), "NUM2": slot(cc3)})
    bs[mul8]["parent"] = add_idx1; bs[cc3]["parent"] = add_idx1
    add_idx2 = gen(); bs[add_idx2] = mk("operator_add",
        inputs={"NUM1": slot(add_idx1), "NUM2": num(1)})
    bs[add_idx1]["parent"] = add_idx2
    set_idx = gen(); bs[set_idx] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_idx2)}, fields={"VARIABLE": ["셀idx", V_CELLIDX]})
    bs[add_idx2]["parent"] = set_idx

    # if item(셀idx) of 보드 != 0: 충돌됨=1
    idx_r = vrep("셀idx", V_CELLIDX)
    brd_item = item_of("보드", L_BOARD, idx_r)
    c_ne0 = cmp_op("operator_not_equals", brd_item, 0)
    set_hit1b = gen(); bs[set_hit1b] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["충돌됨", V_HIT]})
    if_ne0 = gen(); bs[if_ne0] = mk("control_if",
        inputs={"CONDITION": [2, c_ne0], "SUBSTACK": [2, set_hit1b]})
    bs[c_ne0]["parent"] = if_ne0; bs[set_hit1b]["parent"] = if_ne0

    chain([(set_idx, bs[set_idx]), (if_ne0, bs[if_ne0])])
    if_rge0 = gen(); bs[if_rge0] = mk("control_if",
        inputs={"CONDITION": [2, not_rlt0], "SUBSTACK": [2, set_idx]})
    bs[not_rlt0]["parent"] = if_rge0; bs[set_idx]["parent"] = if_rge0

    # if_else: 벽 충돌 / else 보드검사
    if_wall = gen(); bs[if_wall] = mk("control_if_else",
        inputs={"CONDITION": [2, or_wall], "SUBSTACK": [2, set_hit1],
                "SUBSTACK2": [2, if_rge0]})
    bs[or_wall]["parent"] = if_wall
    bs[set_hit1]["parent"] = if_wall
    bs[if_rge0]["parent"] = if_wall

    # i = i + 1
    inc_i = gen(); bs[inc_i] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["i", V_I]})

    # repeat 4 본문 체인: set_cc -> set_cr -> if_wall -> inc_i
    chain([(set_cc, bs[set_cc]), (set_cr, bs[set_cr]),
           (if_wall, bs[if_wall]), (inc_i, bs[inc_i])])
    rep4 = gen(); bs[rep4] = mk("control_repeat",
        inputs={"TIMES": num(4), "SUBSTACK": [2, set_cc]})
    bs[set_cc]["parent"] = rep4

    chain([(def_hit, bs[def_hit]), (set_hit0, bs[set_hit0]),
           (set_ob, bs[set_ob]), (set_i1, bs[set_i1]), (rep4, bs[rep4])])

    # =========================================================
    #  define 고정  (run without screen refresh)
    # =========================================================
    def_lock, _ = make_proc_def(bs, PC_LOCK, warp=True)

    # (1) 4셀을 보드에 굳힘. 오프베이스 = ((현피스-1)*4 + 현회전)*4
    set_ob2 = set_offbase(V_ROT, "현회전")
    set_i1b = gen(); bs[set_i1b] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["i", V_I]})

    # 셀col = 현열 + item(오프베이스+i) of 오프셋C
    col_v = vrep("현열", V_COL)
    ob_l1 = vrep("오프베이스", V_OFFBASE); i_l1 = vrep("i", V_I)
    obi_l1 = gen(); bs[obi_l1] = mk("operator_add",
        inputs={"NUM1": slot(ob_l1), "NUM2": slot(i_l1)})
    bs[ob_l1]["parent"] = obi_l1; bs[i_l1]["parent"] = obi_l1
    offc_l = item_of("오프셋C", L_OFFC, obi_l1)
    add_lcc = gen(); bs[add_lcc] = mk("operator_add",
        inputs={"NUM1": slot(col_v), "NUM2": slot(offc_l)})
    bs[col_v]["parent"] = add_lcc; bs[offc_l]["parent"] = add_lcc
    set_lcc = gen(); bs[set_lcc] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_lcc)}, fields={"VARIABLE": ["셀col", V_CELLCOL]})
    bs[add_lcc]["parent"] = set_lcc

    # 셀row = 현행 + item(오프베이스+i) of 오프셋R
    row_v = vrep("현행", V_ROW)
    ob_l2 = vrep("오프베이스", V_OFFBASE); i_l2 = vrep("i", V_I)
    obi_l2 = gen(); bs[obi_l2] = mk("operator_add",
        inputs={"NUM1": slot(ob_l2), "NUM2": slot(i_l2)})
    bs[ob_l2]["parent"] = obi_l2; bs[i_l2]["parent"] = obi_l2
    offr_l = item_of("오프셋R", L_OFFR, obi_l2)
    add_lcr = gen(); bs[add_lcr] = mk("operator_add",
        inputs={"NUM1": slot(row_v), "NUM2": slot(offr_l)})
    bs[row_v]["parent"] = add_lcr; bs[offr_l]["parent"] = add_lcr
    set_lcr = gen(); bs[set_lcr] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_lcr)}, fields={"VARIABLE": ["셀row", V_CELLROW]})
    bs[add_lcr]["parent"] = set_lcr

    # if 셀row>=0: 셀idx=셀row*8+셀col+1 ; replace item 셀idx of 보드 = 현피스
    crl = vrep("셀row", V_CELLROW)
    c_crl_lt0 = cmp_op("operator_lt", crl, 0)
    not_crl = gen(); bs[not_crl] = mk("operator_not", inputs={"OPERAND": [2, c_crl_lt0]})
    bs[c_crl_lt0]["parent"] = not_crl

    crl2 = vrep("셀row", V_CELLROW)
    mul8l = gen(); bs[mul8l] = mk("operator_multiply",
        inputs={"NUM1": slot(crl2), "NUM2": num(8)})
    bs[crl2]["parent"] = mul8l
    ccl2 = vrep("셀col", V_CELLCOL)
    add_lidx1 = gen(); bs[add_lidx1] = mk("operator_add",
        inputs={"NUM1": slot(mul8l), "NUM2": slot(ccl2)})
    bs[mul8l]["parent"] = add_lidx1; bs[ccl2]["parent"] = add_lidx1
    add_lidx2 = gen(); bs[add_lidx2] = mk("operator_add",
        inputs={"NUM1": slot(add_lidx1), "NUM2": num(1)})
    bs[add_lidx1]["parent"] = add_lidx2
    set_lidx = gen(); bs[set_lidx] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_lidx2)}, fields={"VARIABLE": ["셀idx", V_CELLIDX]})
    bs[add_lidx2]["parent"] = set_lidx

    lidx_r = vrep("셀idx", V_CELLIDX)
    piece_w = vrep("현피스", V_PIECE)
    rep_board = replace_at("보드", L_BOARD, lidx_r, piece_w)
    chain([(set_lidx, bs[set_lidx]), (rep_board, bs[rep_board])])
    if_lrge0 = gen(); bs[if_lrge0] = mk("control_if",
        inputs={"CONDITION": [2, not_crl], "SUBSTACK": [2, set_lidx]})
    bs[not_crl]["parent"] = if_lrge0; bs[set_lidx]["parent"] = if_lrge0

    inc_il = gen(); bs[inc_il] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["i", V_I]})
    chain([(set_lcc, bs[set_lcc]), (set_lcr, bs[set_lcr]),
           (if_lrge0, bs[if_lrge0]), (inc_il, bs[inc_il])])
    rep4_l = gen(); bs[rep4_l] = mk("control_repeat",
        inputs={"TIMES": num(4), "SUBSTACK": [2, set_lcc]})
    bs[set_lcc]["parent"] = rep4_l

    # (2) 라인검출 + 끌어내림
    set_cleared0 = gen(); bs[set_cleared0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["지운줄카운트", V_CLEARED]})
    set_trow13 = gen(); bs[set_trow13] = mk("data_setvariableto",
        inputs={"VALUE": num(13)}, fields={"VARIABLE": ["시험행", V_TROW]})

    # outer: repeat until 시험행 < 0
    trow_c = vrep("시험행", V_TROW)
    cond_trow_lt0 = cmp_op("operator_lt", trow_c, 0)

    # 행꽉참 = 1 ; j = 0
    set_full1 = gen(); bs[set_full1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["행꽉참", V_ROWFULL]})
    set_j0 = gen(); bs[set_j0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["j", V_J]})

    # repeat 8: if item(시험행*8 + j + 1) of 보드 = 0: 행꽉참=0 ; j+=1
    trc1 = vrep("시험행", V_TROW)
    tmul8 = gen(); bs[tmul8] = mk("operator_multiply",
        inputs={"NUM1": slot(trc1), "NUM2": num(8)})
    bs[trc1]["parent"] = tmul8
    jv1 = vrep("j", V_J)
    tadd1 = gen(); bs[tadd1] = mk("operator_add",
        inputs={"NUM1": slot(tmul8), "NUM2": slot(jv1)})
    bs[tmul8]["parent"] = tadd1; bs[jv1]["parent"] = tadd1
    tadd2 = gen(); bs[tadd2] = mk("operator_add",
        inputs={"NUM1": slot(tadd1), "NUM2": num(1)})
    bs[tadd1]["parent"] = tadd2
    tbrd = item_of("보드", L_BOARD, tadd2)
    c_eq0 = cmp_op("operator_equals", tbrd, 0)
    set_full0 = gen(); bs[set_full0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["행꽉참", V_ROWFULL]})
    if_eq0 = gen(); bs[if_eq0] = mk("control_if",
        inputs={"CONDITION": [2, c_eq0], "SUBSTACK": [2, set_full0]})
    bs[c_eq0]["parent"] = if_eq0; bs[set_full0]["parent"] = if_eq0
    inc_j1 = gen(); bs[inc_j1] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["j", V_J]})
    chain([(if_eq0, bs[if_eq0]), (inc_j1, bs[inc_j1])])
    rep8_check = gen(); bs[rep8_check] = mk("control_repeat",
        inputs={"TIMES": num(8), "SUBSTACK": [2, if_eq0]})
    bs[if_eq0]["parent"] = rep8_check

    # if 행꽉참 = 1: { 지운줄카운트+=1 ; 끌어내림 ; row0 비움 } else: 시험행 -= 1
    full_c = vrep("행꽉참", V_ROWFULL)
    c_full1 = cmp_op("operator_equals", full_c, 1)

    inc_cleared = gen(); bs[inc_cleared] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["지운줄카운트", V_CLEARED]})

    # i = 시험행
    trow_set = vrep("시험행", V_TROW)
    set_i_trow = gen(); bs[set_i_trow] = mk("data_setvariableto",
        inputs={"VALUE": slot(trow_set)}, fields={"VARIABLE": ["i", V_I]})
    bs[trow_set]["parent"] = set_i_trow

    # repeat until i < 1
    iv_c = vrep("i", V_I)
    cond_i_lt1 = cmp_op("operator_lt", iv_c, 1)

    # inner copy: j=0 ; repeat 8: replace item(i*8+j+1) of 보드 = item((i-1)*8+j+1) of 보드 ; j+=1
    set_j0b = gen(); bs[set_j0b] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["j", V_J]})

    # dest idx = i*8 + j + 1
    iv_d = vrep("i", V_I)
    dmul = gen(); bs[dmul] = mk("operator_multiply",
        inputs={"NUM1": slot(iv_d), "NUM2": num(8)})
    bs[iv_d]["parent"] = dmul
    jv_d = vrep("j", V_J)
    dadd1 = gen(); bs[dadd1] = mk("operator_add",
        inputs={"NUM1": slot(dmul), "NUM2": slot(jv_d)})
    bs[dmul]["parent"] = dadd1; bs[jv_d]["parent"] = dadd1
    dadd2 = gen(); bs[dadd2] = mk("operator_add",
        inputs={"NUM1": slot(dadd1), "NUM2": num(1)})
    bs[dadd1]["parent"] = dadd2

    # src idx = (i-1)*8 + j + 1 ; src value = item(src) of 보드
    iv_s = vrep("i", V_I)
    ssub = gen(); bs[ssub] = mk("operator_subtract",
        inputs={"NUM1": slot(iv_s), "NUM2": num(1)})
    bs[iv_s]["parent"] = ssub
    smul = gen(); bs[smul] = mk("operator_multiply",
        inputs={"NUM1": slot(ssub), "NUM2": num(8)})
    bs[ssub]["parent"] = smul
    jv_s = vrep("j", V_J)
    sadd1 = gen(); bs[sadd1] = mk("operator_add",
        inputs={"NUM1": slot(smul), "NUM2": slot(jv_s)})
    bs[smul]["parent"] = sadd1; bs[jv_s]["parent"] = sadd1
    sadd2 = gen(); bs[sadd2] = mk("operator_add",
        inputs={"NUM1": slot(sadd1), "NUM2": num(1)})
    bs[sadd1]["parent"] = sadd2
    src_item = item_of("보드", L_BOARD, sadd2)

    rep_copy = replace_at("보드", L_BOARD, dadd2, src_item)
    inc_j2 = gen(); bs[inc_j2] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["j", V_J]})
    chain([(rep_copy, bs[rep_copy]), (inc_j2, bs[inc_j2])])
    rep8_copy = gen(); bs[rep8_copy] = mk("control_repeat",
        inputs={"TIMES": num(8), "SUBSTACK": [2, rep_copy]})
    bs[rep_copy]["parent"] = rep8_copy

    dec_i = gen(); bs[dec_i] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["i", V_I]})
    chain([(set_j0b, bs[set_j0b]), (rep8_copy, bs[rep8_copy]), (dec_i, bs[dec_i])])
    rep_pull = gen(); bs[rep_pull] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_i_lt1], "SUBSTACK": [2, set_j0b]})
    bs[cond_i_lt1]["parent"] = rep_pull
    bs[set_j0b]["parent"] = rep_pull

    # row0 비움: j=0 ; repeat 8: replace item(0*8+j+1) of 보드 = 0 ; j+=1
    set_j0c = gen(); bs[set_j0c] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["j", V_J]})
    jv_z = vrep("j", V_J)
    zadd = gen(); bs[zadd] = mk("operator_add",
        inputs={"NUM1": slot(jv_z), "NUM2": num(1)})
    bs[jv_z]["parent"] = zadd
    rep_zero = replace_at("보드", L_BOARD, zadd, 0)
    inc_j3 = gen(); bs[inc_j3] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["j", V_J]})
    chain([(rep_zero, bs[rep_zero]), (inc_j3, bs[inc_j3])])
    rep8_zero = gen(); bs[rep8_zero] = mk("control_repeat",
        inputs={"TIMES": num(8), "SUBSTACK": [2, rep_zero]})
    bs[rep_zero]["parent"] = rep8_zero

    # then-branch 체인: inc_cleared -> set_i_trow -> rep_pull -> set_j0c -> rep8_zero
    chain([(inc_cleared, bs[inc_cleared]), (set_i_trow, bs[set_i_trow]),
           (rep_pull, bs[rep_pull]), (set_j0c, bs[set_j0c]), (rep8_zero, bs[rep8_zero])])

    # else: 시험행 -= 1
    dec_trow = gen(); bs[dec_trow] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["시험행", V_TROW]})

    if_full = gen(); bs[if_full] = mk("control_if_else",
        inputs={"CONDITION": [2, c_full1], "SUBSTACK": [2, inc_cleared],
                "SUBSTACK2": [2, dec_trow]})
    bs[c_full1]["parent"] = if_full
    bs[inc_cleared]["parent"] = if_full
    bs[dec_trow]["parent"] = if_full

    # outer body 체인: set_full1 -> set_j0 -> rep8_check -> if_full
    chain([(set_full1, bs[set_full1]), (set_j0, bs[set_j0]),
           (rep8_check, bs[rep8_check]), (if_full, bs[if_full])])
    rep_outer = gen(); bs[rep_outer] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_trow_lt0], "SUBSTACK": [2, set_full1]})
    bs[cond_trow_lt0]["parent"] = rep_outer
    bs[set_full1]["parent"] = rep_outer

    # (3) 점수/줄수
    def score_if(n, pts):
        cl_v = vrep("지운줄카운트", V_CLEARED)
        c_eq = cmp_op("operator_equals", cl_v, n)
        inc = gen(); bs[inc] = mk("data_changevariableby",
            inputs={"VALUE": num(pts)}, fields={"VARIABLE": ["점수", V_SCORE]})
        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION": [2, c_eq], "SUBSTACK": [2, inc]})
        bs[c_eq]["parent"] = ifb; bs[inc]["parent"] = ifb
        return ifb
    if_s1 = score_if(1, 100)
    if_s2 = score_if(2, 300)
    if_s3 = score_if(3, 500)
    if_s4 = score_if(4, 800)

    # 줄수 += 지운줄카운트
    cl_add = vrep("지운줄카운트", V_CLEARED)
    inc_lines = gen(); bs[inc_lines] = mk("data_changevariableby",
        inputs={"VALUE": slot(cl_add)}, fields={"VARIABLE": ["줄수", V_LINES]})
    bs[cl_add]["parent"] = inc_lines

    # if 점수 > 최고기록: 최고기록 = 점수
    sc_b = vrep("점수", V_SCORE); be_b = vrep("최고기록", V_BEST)
    c_best = cmp_op("operator_gt", sc_b, be_b)
    sc_b2 = vrep("점수", V_SCORE)
    set_best = gen(); bs[set_best] = mk("data_setvariableto",
        inputs={"VALUE": slot(sc_b2)}, fields={"VARIABLE": ["최고기록", V_BEST]})
    bs[sc_b2]["parent"] = set_best
    if_best = gen(); bs[if_best] = mk("control_if",
        inputs={"CONDITION": [2, c_best], "SUBSTACK": [2, set_best]})
    bs[c_best]["parent"] = if_best; bs[set_best]["parent"] = if_best

    # if 지운줄카운트 > 0: play sound clear(pop)
    cl_p = vrep("지운줄카운트", V_CLEARED)
    c_cl_gt0 = cmp_op("operator_gt", cl_p, 0)
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU": [1, snm]})
    bs[snm]["parent"] = snd
    if_snd = gen(); bs[if_snd] = mk("control_if",
        inputs={"CONDITION": [2, c_cl_gt0], "SUBSTACK": [2, snd]})
    bs[c_cl_gt0]["parent"] = if_snd; bs[snd]["parent"] = if_snd

    # (4) broadcast 보드그리기 ; broadcast 새블록
    bc_drawb = broadcast(bs, "보드그리기", BR_DRAWBRD)
    bc_spawn2 = broadcast(bs, "새블록", BR_SPAWN)

    chain([(def_lock, bs[def_lock]), (set_ob2, bs[set_ob2]), (set_i1b, bs[set_i1b]),
           (rep4_l, bs[rep4_l]),
           (set_cleared0, bs[set_cleared0]), (set_trow13, bs[set_trow13]),
           (rep_outer, bs[rep_outer]),
           (if_s1, bs[if_s1]), (if_s2, bs[if_s2]), (if_s3, bs[if_s3]), (if_s4, bs[if_s4]),
           (inc_lines, bs[inc_lines]), (if_best, bs[if_best]), (if_snd, bs[if_snd]),
           (bc_drawb, bs[bc_drawb]), (bc_spawn2, bs[bc_spawn2])])

    # =========================================================
    #  when flag clicked: hide
    # =========================================================
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(hf, bs[hf]), (hi, bs[hi])])

    # =========================================================
    #  when receive 새블록  (7.4)
    # =========================================================
    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=300, y=20,
        fields={"BROADCAST_OPTION": ["새블록", BR_SPAWN]})

    # 현피스 = 다음피스
    next_v = vrep("다음피스", V_NEXT)
    set_piece = gen(); bs[set_piece] = mk("data_setvariableto",
        inputs={"VALUE": slot(next_v)}, fields={"VARIABLE": ["현피스", V_PIECE]})
    bs[next_v]["parent"] = set_piece
    # 다음피스 = random 1..7
    rn = gen(); bs[rn] = mk("operator_random", inputs={"FROM": num(1), "TO": num(7)})
    set_next = gen(); bs[set_next] = mk("data_setvariableto",
        inputs={"VALUE": slot(rn)}, fields={"VARIABLE": ["다음피스", V_NEXT]})
    bs[rn]["parent"] = set_next
    # 현회전=0 ; 현열=3 ; 현행=0
    set_rot0 = gen(); bs[set_rot0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["현회전", V_ROT]})
    set_col3 = gen(); bs[set_col3] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["현열", V_COL]})
    set_row0 = gen(); bs[set_row0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["현행", V_ROW]})

    # 시험열=현열 ; 시험행=현행 ; 시험회전=현회전 ; call 충돌?
    set_tc = _copy_var(bs, "시험열", V_TCOL, "현열", V_COL)
    set_tr = _copy_var(bs, "시험행", V_TROW, "현행", V_ROW)
    set_trt = _copy_var(bs, "시험회전", V_TROT, "현회전", V_ROT)
    call_hit_s = make_proc_call(bs, PC_HIT, warp=True)

    # if 충돌됨 = 1: 게임상태 = 0
    hit_s = vrep("충돌됨", V_HIT)
    c_hit1 = cmp_op("operator_equals", hit_s, 1)
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_over = gen(); bs[if_over] = mk("control_if",
        inputs={"CONDITION": [2, c_hit1], "SUBSTACK": [2, set_state0]})
    bs[c_hit1]["parent"] = if_over; bs[set_state0]["parent"] = if_over

    bc_dc_s = broadcast(bs, "현재블록그리기", BR_DRAWCUR)
    bc_db_s = broadcast(bs, "보드그리기", BR_DRAWBRD)

    chain([(hs, bs[hs]), (set_piece, bs[set_piece]), (set_next, bs[set_next]),
           (set_rot0, bs[set_rot0]), (set_col3, bs[set_col3]), (set_row0, bs[set_row0]),
           (set_tc, bs[set_tc]), (set_tr, bs[set_tr]), (set_trt, bs[set_trt]),
           (call_hit_s, bs[call_hit_s]), (if_over, bs[if_over]),
           (bc_dc_s, bs[bc_dc_s]), (bc_db_s, bs[bc_db_s])])

    # =========================================================
    #  when receive 브틱  (7.5)
    # =========================================================
    ht = gen(); bs[ht] = mk("event_whenbroadcastreceived", top=True, x=300, y=300,
        fields={"BROADCAST_OPTION": ["브틱", BR_TICK]})

    state_t = vrep("게임상태", V_STATE)
    c_state1 = cmp_op("operator_equals", state_t, 1)

    # 시험열=현열 ; 시험행=현행+1 ; 시험회전=현회전 ; call 충돌?
    set_tc_t = _copy_var(bs, "시험열", V_TCOL, "현열", V_COL)
    set_tr_t = _set_rowplus1(bs)
    set_trt_t = _copy_var(bs, "시험회전", V_TROT, "현회전", V_ROT)
    call_hit_t = make_proc_call(bs, PC_HIT, warp=True)

    # if 충돌됨=0: 현행+=1 ; broadcast 현재블록그리기  else: call 고정
    hit_t = vrep("충돌됨", V_HIT)
    c_hit0_t = cmp_op("operator_equals", hit_t, 0)
    inc_row = gen(); bs[inc_row] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["현행", V_ROW]})
    bc_dc_t = broadcast(bs, "현재블록그리기", BR_DRAWCUR)
    chain([(inc_row, bs[inc_row]), (bc_dc_t, bs[bc_dc_t])])
    call_lock_t = make_proc_call(bs, PC_LOCK, warp=True)
    if_hit_t = gen(); bs[if_hit_t] = mk("control_if_else",
        inputs={"CONDITION": [2, c_hit0_t], "SUBSTACK": [2, inc_row],
                "SUBSTACK2": [2, call_lock_t]})
    bs[c_hit0_t]["parent"] = if_hit_t
    bs[inc_row]["parent"] = if_hit_t
    bs[call_lock_t]["parent"] = if_hit_t

    chain([(set_tc_t, bs[set_tc_t]), (set_tr_t, bs[set_tr_t]),
           (set_trt_t, bs[set_trt_t]), (call_hit_t, bs[call_hit_t]),
           (if_hit_t, bs[if_hit_t])])
    if_play = gen(); bs[if_play] = mk("control_if",
        inputs={"CONDITION": [2, c_state1], "SUBSTACK": [2, set_tc_t]})
    bs[c_state1]["parent"] = if_play; bs[set_tc_t]["parent"] = if_play
    chain([(ht, bs[ht]), (if_play, bs[if_play])])

    # =========================================================
    #  when receive 게임시작: 입력 forever  (7.2)
    # =========================================================
    hi2 = gen(); bs[hi2] = mk("event_whenbroadcastreceived", top=True, x=600, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_in = vrep("게임상태", V_STATE)
    cond_over_in = cmp_op("operator_equals", state_in, 0)

    # --- helper: key pressed boolean ---
    def key_pressed(key_name):
        km = gen(); bs[km] = mk("sensing_keyoptions",
            fields={"KEY_OPTION": [key_name, None]}, shadow=True)
        kp = gen(); bs[kp] = mk("sensing_keypressed", inputs={"KEY_OPTION": [1, km]})
        bs[km]["parent"] = kp
        return kp

    def wait_until_not_key(key_name):
        kp = key_pressed(key_name)
        nt = gen(); bs[nt] = mk("operator_not", inputs={"OPERAND": [2, kp]})
        bs[kp]["parent"] = nt
        wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, nt]})
        bs[nt]["parent"] = wu
        return wu

    # --- 좌/우/회전 공통 분기 (에지 입력) ---
    def move_branch(key_name, dcol, drot_expr):
        """if key: { set 시험열/시험행/시험회전 ; call 충돌? ; if 충돌됨=0: apply ; wait until NOT key }"""
        # 시험열 = 현열 + dcol
        if dcol == 0:
            set_tcb = _copy_var(bs, "시험열", V_TCOL, "현열", V_COL)
        else:
            col_b = vrep("현열", V_COL)
            addc = gen(); bs[addc] = mk("operator_add",
                inputs={"NUM1": slot(col_b), "NUM2": num(dcol)})
            bs[col_b]["parent"] = addc
            set_tcb = gen(); bs[set_tcb] = mk("data_setvariableto",
                inputs={"VALUE": slot(addc)}, fields={"VARIABLE": ["시험열", V_TCOL]})
            bs[addc]["parent"] = set_tcb
        # 시험행 = 현행
        set_trb = _copy_var(bs, "시험행", V_TROW, "현행", V_ROW)
        # 시험회전 = drot_expr  (None=현회전 / "rot" = (현회전+1) mod 4)
        if drot_expr is None:
            set_trtb = _copy_var(bs, "시험회전", V_TROT, "현회전", V_ROT)
        else:
            rot_b = vrep("현회전", V_ROT)
            addr = gen(); bs[addr] = mk("operator_add",
                inputs={"NUM1": slot(rot_b), "NUM2": num(1)})
            bs[rot_b]["parent"] = addr
            modr = gen(); bs[modr] = mk("operator_mod",
                inputs={"NUM1": slot(addr), "NUM2": num(4)})
            bs[addr]["parent"] = modr
            set_trtb = gen(); bs[set_trtb] = mk("data_setvariableto",
                inputs={"VALUE": slot(modr)}, fields={"VARIABLE": ["시험회전", V_TROT]})
            bs[modr]["parent"] = set_trtb
        # call 충돌?
        callb = make_proc_call(bs, PC_HIT, warp=True)
        # if 충돌됨=0: apply (현열=시험열 / 현회전=시험회전) ; broadcast 현재블록그리기
        hit_b = vrep("충돌됨", V_HIT)
        c0 = cmp_op("operator_equals", hit_b, 0)
        if drot_expr is None:
            apply_set = _copy_var(bs, "현열", V_COL, "시험열", V_TCOL)
        else:
            apply_set = _copy_var(bs, "현회전", V_ROT, "시험회전", V_TROT)
        bc_d = broadcast(bs, "현재블록그리기", BR_DRAWCUR)
        chain([(apply_set, bs[apply_set]), (bc_d, bs[bc_d])])
        if_apply = gen(); bs[if_apply] = mk("control_if",
            inputs={"CONDITION": [2, c0], "SUBSTACK": [2, apply_set]})
        bs[c0]["parent"] = if_apply; bs[apply_set]["parent"] = if_apply
        # wait until NOT key
        wun = wait_until_not_key(key_name)
        # body 체인
        chain([(set_tcb, bs[set_tcb]), (set_trb, bs[set_trb]),
               (set_trtb, bs[set_trtb]), (callb, bs[callb]),
               (if_apply, bs[if_apply]), (wun, bs[wun])])
        # outer if key
        kp = key_pressed(key_name)
        ifk = gen(); bs[ifk] = mk("control_if",
            inputs={"CONDITION": [2, kp], "SUBSTACK": [2, set_tcb]})
        bs[kp]["parent"] = ifk; bs[set_tcb]["parent"] = ifk
        return ifk

    if_left  = move_branch("left arrow",  -1, None)
    if_right = move_branch("right arrow",  1, None)
    if_up    = move_branch("up arrow",     0, "rot")

    # --- ↓ 소프트드롭 (에지 아님) ---
    # if key down: { 시험열=현열 ; 시험행=현행+1 ; 시험회전=현회전 ; call 충돌? ;
    #                if 충돌됨=0: 현행=시험행 ; broadcast 현재블록그리기  else: call 고정 ; wait 0.04 }
    sd_tc = _copy_var(bs, "시험열", V_TCOL, "현열", V_COL)
    sd_tr = _set_rowplus1(bs)
    sd_trt = _copy_var(bs, "시험회전", V_TROT, "현회전", V_ROT)
    sd_call = make_proc_call(bs, PC_HIT, warp=True)
    sd_hit = vrep("충돌됨", V_HIT)
    sd_c0 = cmp_op("operator_equals", sd_hit, 0)
    sd_apply = _copy_var(bs, "현행", V_ROW, "시험행", V_TROW)
    sd_bc = broadcast(bs, "현재블록그리기", BR_DRAWCUR)
    chain([(sd_apply, bs[sd_apply]), (sd_bc, bs[sd_bc])])
    sd_lock = make_proc_call(bs, PC_LOCK, warp=True)
    sd_ife = gen(); bs[sd_ife] = mk("control_if_else",
        inputs={"CONDITION": [2, sd_c0], "SUBSTACK": [2, sd_apply],
                "SUBSTACK2": [2, sd_lock]})
    bs[sd_c0]["parent"] = sd_ife
    bs[sd_apply]["parent"] = sd_ife
    bs[sd_lock]["parent"] = sd_ife
    sd_wait = gen(); bs[sd_wait] = mk("control_wait", inputs={"DURATION": num(0.04)})
    chain([(sd_tc, bs[sd_tc]), (sd_tr, bs[sd_tr]), (sd_trt, bs[sd_trt]),
           (sd_call, bs[sd_call]), (sd_ife, bs[sd_ife]), (sd_wait, bs[sd_wait])])
    sd_kp = key_pressed("down arrow")
    if_down = gen(); bs[if_down] = mk("control_if",
        inputs={"CONDITION": [2, sd_kp], "SUBSTACK": [2, sd_tc]})
    bs[sd_kp]["parent"] = if_down; bs[sd_tc]["parent"] = if_down

    # --- space 하드드롭 (에지) ---
    # if key space: { repeat until 충돌됨=1: { 시험열=현열 ; 시험행=현행+1 ; 시험회전=현회전 ;
    #                  call 충돌? ; if 충돌됨=0: 현행+=1 }
    #                broadcast 현재블록그리기 ; call 고정 ; wait until NOT key space }
    hd_tc = _copy_var(bs, "시험열", V_TCOL, "현열", V_COL)
    hd_tr = _set_rowplus1(bs)
    hd_trt = _copy_var(bs, "시험회전", V_TROT, "현회전", V_ROT)
    hd_call = make_proc_call(bs, PC_HIT, warp=True)
    hd_hit = vrep("충돌됨", V_HIT)
    hd_c0 = cmp_op("operator_equals", hd_hit, 0)
    hd_inc = gen(); bs[hd_inc] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["현행", V_ROW]})
    hd_ifinc = gen(); bs[hd_ifinc] = mk("control_if",
        inputs={"CONDITION": [2, hd_c0], "SUBSTACK": [2, hd_inc]})
    bs[hd_c0]["parent"] = hd_ifinc; bs[hd_inc]["parent"] = hd_ifinc
    chain([(hd_tc, bs[hd_tc]), (hd_tr, bs[hd_tr]), (hd_trt, bs[hd_trt]),
           (hd_call, bs[hd_call]), (hd_ifinc, bs[hd_ifinc])])
    hd_hit2 = vrep("충돌됨", V_HIT)
    hd_cond = cmp_op("operator_equals", hd_hit2, 1)
    hd_rep = gen(); bs[hd_rep] = mk("control_repeat_until",
        inputs={"CONDITION": [2, hd_cond], "SUBSTACK": [2, hd_tc]})
    bs[hd_cond]["parent"] = hd_rep; bs[hd_tc]["parent"] = hd_rep
    hd_bc = broadcast(bs, "현재블록그리기", BR_DRAWCUR)
    hd_lock = make_proc_call(bs, PC_LOCK, warp=True)
    hd_wun = wait_until_not_key("space")
    chain([(hd_rep, bs[hd_rep]), (hd_bc, bs[hd_bc]),
           (hd_lock, bs[hd_lock]), (hd_wun, bs[hd_wun])])
    hd_kp = key_pressed("space")
    if_space = gen(); bs[if_space] = mk("control_if",
        inputs={"CONDITION": [2, hd_kp], "SUBSTACK": [2, hd_rep]})
    bs[hd_kp]["parent"] = if_space; bs[hd_rep]["parent"] = if_space

    # forever-tick wait 0.03
    wt_in = gen(); bs[wt_in] = mk("control_wait", inputs={"DURATION": num(0.03)})

    chain([(if_left, bs[if_left]), (if_right, bs[if_right]), (if_up, bs[if_up]),
           (if_down, bs[if_down]), (if_space, bs[if_space]), (wt_in, bs[wt_in])])
    rep_in = gen(); bs[rep_in] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over_in], "SUBSTACK": [2, if_left]})
    bs[cond_over_in]["parent"] = rep_in
    bs[if_left]["parent"] = rep_in
    chain([(hi2, bs[hi2]), (rep_in, bs[rep_in])])

    # =========================================================
    #  when flag clicked: 게임오버 효과음
    # =========================================================
    hg = gen(); bs[hg] = mk("event_whenflagclicked", top=True, x=600, y=320)
    st_w = vrep("게임상태", V_STATE)
    c_w0 = cmp_op("operator_equals", st_w, 0)
    wu_g = gen(); bs[wu_g] = mk("control_wait_until", inputs={"CONDITION": [2, c_w0]})
    bs[c_w0]["parent"] = wu_g
    snm_g = gen(); bs[snm_g] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_g = gen(); bs[snd_g] = mk("sound_play", inputs={"SOUND_MENU": [1, snm_g]})
    bs[snm_g]["parent"] = snd_g
    chain([(hg, bs[hg]), (wu_g, bs[wu_g]), (snd_g, bs[snd_g])])

    return bs

# ---- 작은 보조 빌더 (logic 전용; bs 받음) ----
def _copy_var(bs, dst_name, dst_id, src_name, src_id):
    """dst = src (변수 복사 set 블록)."""
    src_v = gen(); bs[src_v] = mk("data_variable", fields={"VARIABLE": [src_name, src_id]})
    setb = gen(); bs[setb] = mk("data_setvariableto",
        inputs={"VALUE": slot(src_v)}, fields={"VARIABLE": [dst_name, dst_id]})
    bs[src_v]["parent"] = setb
    return setb

def _set_rowplus1(bs):
    """시험행 = 현행 + 1."""
    row_v = gen(); bs[row_v] = mk("data_variable", fields={"VARIABLE": ["현행", V_ROW]})
    addr = gen(); bs[addr] = mk("operator_add",
        inputs={"NUM1": slot(row_v), "NUM2": num(1)})
    bs[row_v]["parent"] = addr
    setb = gen(); bs[setb] = mk("data_setvariableto",
        inputs={"VALUE": slot(addr)}, fields={"VARIABLE": ["시험행", V_TROW]})
    bs[addr]["parent"] = setb
    return setb

# ============================================================
#  현재블록 (4셀 클론)
# ============================================================
def build_current_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    add_to, delete_all, item_of, length_of, replace_at = make_list_helpers(bs)

    # when flag clicked: hide
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(hf, bs[hf]), (hi, bs[hi])])

    # when receive 게임시작: hide ; 셀번호=0 ; repeat 4: 셀번호+=1 ; create clone of myself
    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    set_seg0 = gen(); bs[set_seg0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["셀번호", V_SEG]})
    inc_seg = gen(); bs[inc_seg] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["셀번호", V_SEG]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(inc_seg, bs[inc_seg]), (cclone, bs[cclone])])
    rep4 = gen(); bs[rep4] = mk("control_repeat",
        inputs={"TIMES": num(4), "SUBSTACK": [2, inc_seg]})
    bs[inc_seg]["parent"] = rep4
    chain([(hs, bs[hs]), (hi2, bs[hi2]), (set_seg0, bs[set_seg0]), (rep4, bs[rep4])])

    # when I start as clone: show
    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=300, y=20)
    show_c = gen(); bs[show_c] = mk("looks_show")
    chain([(sc, bs[sc]), (show_c, bs[show_c])])

    # when receive 현재블록그리기 (모든 클론):
    #   오프베이스(현블록로컬) = ((현피스-1)*4 + 현회전)*4
    #   셀col = 현열 + item(오프베이스+셀번호) of 오프셋C
    #   셀row = 현행 + item(오프베이스+셀번호) of 오프셋R
    #   switch costume to 현피스
    #   if 셀row<0: hide else: show ; goto(-150+셀col*22, 143-셀row*22)
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=300, y=160,
        fields={"BROADCAST_OPTION": ["현재블록그리기", BR_DRAWCUR]})

    # 오프베이스 = ((현피스-1)*4 + 현회전)*4
    piece_v = vrep("현피스", V_PIECE)
    sub_p = gen(); bs[sub_p] = mk("operator_subtract",
        inputs={"NUM1": slot(piece_v), "NUM2": num(1)})
    bs[piece_v]["parent"] = sub_p
    mul_p = gen(); bs[mul_p] = mk("operator_multiply",
        inputs={"NUM1": slot(sub_p), "NUM2": num(4)})
    bs[sub_p]["parent"] = mul_p
    rot_v = vrep("현회전", V_ROT)
    add_r = gen(); bs[add_r] = mk("operator_add",
        inputs={"NUM1": slot(mul_p), "NUM2": slot(rot_v)})
    bs[mul_p]["parent"] = add_r; bs[rot_v]["parent"] = add_r
    mul4 = gen(); bs[mul4] = mk("operator_multiply",
        inputs={"NUM1": slot(add_r), "NUM2": num(4)})
    bs[add_r]["parent"] = mul4
    set_ob = gen(); bs[set_ob] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul4)}, fields={"VARIABLE": ["오프베이스C", V_CUR_OFFBASE]})
    bs[mul4]["parent"] = set_ob

    # 셀col = 현열 + item(오프베이스+셀번호) of 오프셋C
    col_v = vrep("현열", V_COL)
    ob_v1 = vrep("오프베이스C", V_CUR_OFFBASE); seg_v1 = vrep("셀번호", V_SEG)
    obi1 = gen(); bs[obi1] = mk("operator_add",
        inputs={"NUM1": slot(ob_v1), "NUM2": slot(seg_v1)})
    bs[ob_v1]["parent"] = obi1; bs[seg_v1]["parent"] = obi1
    offc1 = item_of("오프셋C", L_OFFC, obi1)
    add_cc = gen(); bs[add_cc] = mk("operator_add",
        inputs={"NUM1": slot(col_v), "NUM2": slot(offc1)})
    bs[col_v]["parent"] = add_cc; bs[offc1]["parent"] = add_cc
    set_cc = gen(); bs[set_cc] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_cc)}, fields={"VARIABLE": ["셀colC", V_CUR_CELLCOL]})
    bs[add_cc]["parent"] = set_cc

    # 셀row = 현행 + item(오프베이스+셀번호) of 오프셋R
    row_v = vrep("현행", V_ROW)
    ob_v2 = vrep("오프베이스C", V_CUR_OFFBASE); seg_v2 = vrep("셀번호", V_SEG)
    obi2 = gen(); bs[obi2] = mk("operator_add",
        inputs={"NUM1": slot(ob_v2), "NUM2": slot(seg_v2)})
    bs[ob_v2]["parent"] = obi2; bs[seg_v2]["parent"] = obi2
    offr1 = item_of("오프셋R", L_OFFR, obi2)
    add_cr = gen(); bs[add_cr] = mk("operator_add",
        inputs={"NUM1": slot(row_v), "NUM2": slot(offr1)})
    bs[row_v]["parent"] = add_cr; bs[offr1]["parent"] = add_cr
    set_cr = gen(); bs[set_cr] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_cr)}, fields={"VARIABLE": ["셀rowC", V_CUR_CELLROW]})
    bs[add_cr]["parent"] = set_cr

    # switch costume to 현피스
    piece_c = vrep("현피스", V_PIECE)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(piece_c)})
    bs[piece_c]["parent"] = sw

    # if 셀row<0: hide  else: show ; goto(...)
    cr_v = vrep("셀rowC", V_CUR_CELLROW)
    c_rlt0 = cmp_op("operator_lt", cr_v, 0)
    hide_c = gen(); bs[hide_c] = mk("looks_hide")
    show_d = gen(); bs[show_d] = mk("looks_show")
    # goto x = -150 + 셀col*22
    ccx = vrep("셀colC", V_CUR_CELLCOL)
    mulx = gen(); bs[mulx] = mk("operator_multiply",
        inputs={"NUM1": slot(ccx), "NUM2": num(CELL)})
    bs[ccx]["parent"] = mulx
    addx = gen(); bs[addx] = mk("operator_add",
        inputs={"NUM1": num(BOARD_X0), "NUM2": slot(mulx)})
    bs[mulx]["parent"] = addx
    # goto y = 143 - 셀row*22
    cry = vrep("셀rowC", V_CUR_CELLROW)
    muly = gen(); bs[muly] = mk("operator_multiply",
        inputs={"NUM1": slot(cry), "NUM2": num(CELL)})
    bs[cry]["parent"] = muly
    suby = gen(); bs[suby] = mk("operator_subtract",
        inputs={"NUM1": num(BOARD_Y0), "NUM2": slot(muly)})
    bs[muly]["parent"] = suby
    goto_c = gen(); bs[goto_c] = mk("motion_gotoxy",
        inputs={"X": slot(addx), "Y": slot(suby)})
    bs[addx]["parent"] = goto_c; bs[suby]["parent"] = goto_c
    chain([(show_d, bs[show_d]), (goto_c, bs[goto_c])])
    if_vis = gen(); bs[if_vis] = mk("control_if_else",
        inputs={"CONDITION": [2, c_rlt0], "SUBSTACK": [2, hide_c],
                "SUBSTACK2": [2, show_d]})
    bs[c_rlt0]["parent"] = if_vis
    bs[hide_c]["parent"] = if_vis
    bs[show_d]["parent"] = if_vis

    chain([(hd, bs[hd]), (set_ob, bs[set_ob]), (set_cc, bs[set_cc]),
           (set_cr, bs[set_cr]), (sw, bs[sw]), (if_vis, bs[if_vis])])

    return bs

# ============================================================
#  보드셀 (고정 블록 클론)
# ============================================================
def build_boardcell_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    add_to, delete_all, item_of, length_of, replace_at = make_list_helpers(bs)

    # when flag clicked: hide
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(hf, bs[hf]), (hi, bs[hi])])

    # when receive 보드그리기 (본체):
    #   broadcast 보드지우기 ; wait 0
    #   그릴idx=1 ; repeat 112: 그릴색 = item(그릴idx) of 보드 ;
    #       if 그릴색 != 0: create clone ; 그릴idx+=1
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["보드그리기", BR_DRAWBRD]})
    bc_clear = broadcast(bs, "보드지우기", BR_CLEARC)
    wt0 = gen(); bs[wt0] = mk("control_wait", inputs={"DURATION": num(0)})
    set_di1 = gen(); bs[set_di1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["그릴idx", V_DRAWIDX]})

    # body of repeat 112
    di_v = vrep("그릴idx", V_DRAWIDX)
    brd_item = item_of("보드", L_BOARD, di_v)
    set_dc = gen(); bs[set_dc] = mk("data_setvariableto",
        inputs={"VALUE": slot(brd_item)}, fields={"VARIABLE": ["그릴색", V_DRAWCOL]})
    bs[brd_item]["parent"] = set_dc

    dc_v = vrep("그릴색", V_DRAWCOL)
    c_ne0 = cmp_op("operator_not_equals", dc_v, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_ne0 = gen(); bs[if_ne0] = mk("control_if",
        inputs={"CONDITION": [2, c_ne0], "SUBSTACK": [2, cclone]})
    bs[c_ne0]["parent"] = if_ne0; bs[cclone]["parent"] = if_ne0
    inc_di = gen(); bs[inc_di] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["그릴idx", V_DRAWIDX]})
    chain([(set_dc, bs[set_dc]), (if_ne0, bs[if_ne0]), (inc_di, bs[inc_di])])
    rep112 = gen(); bs[rep112] = mk("control_repeat",
        inputs={"TIMES": num(112), "SUBSTACK": [2, set_dc]})
    bs[set_dc]["parent"] = rep112
    chain([(hd, bs[hd]), (bc_clear, bs[bc_clear]), (wt0, bs[wt0]),
           (set_di1, bs[set_di1]), (rep112, bs[rep112])])

    # when I start as clone:
    #   switch costume to 그릴색
    #   goto(-150 + ((그릴idx-1) mod 8)*22, 143 - floor((그릴idx-1)/8)*22)
    #   show
    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=300, y=20)
    dc_c = vrep("그릴색", V_DRAWCOL)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(dc_c)})
    bs[dc_c]["parent"] = sw

    # col = (그릴idx-1) mod 8
    di_x = vrep("그릴idx", V_DRAWIDX)
    sub1x = gen(); bs[sub1x] = mk("operator_subtract",
        inputs={"NUM1": slot(di_x), "NUM2": num(1)})
    bs[di_x]["parent"] = sub1x
    modx = gen(); bs[modx] = mk("operator_mod",
        inputs={"NUM1": slot(sub1x), "NUM2": num(8)})
    bs[sub1x]["parent"] = modx
    mulx = gen(); bs[mulx] = mk("operator_multiply",
        inputs={"NUM1": slot(modx), "NUM2": num(CELL)})
    bs[modx]["parent"] = mulx
    addx = gen(); bs[addx] = mk("operator_add",
        inputs={"NUM1": num(BOARD_X0), "NUM2": slot(mulx)})
    bs[mulx]["parent"] = addx

    # row = floor((그릴idx-1)/8)
    di_y = vrep("그릴idx", V_DRAWIDX)
    sub1y = gen(); bs[sub1y] = mk("operator_subtract",
        inputs={"NUM1": slot(di_y), "NUM2": num(1)})
    bs[di_y]["parent"] = sub1y
    divy = gen(); bs[divy] = mk("operator_divide",
        inputs={"NUM1": slot(sub1y), "NUM2": num(8)})
    bs[sub1y]["parent"] = divy
    floory = gen(); bs[floory] = mk("operator_mathop",
        inputs={"NUM": slot(divy)}, fields={"OPERATOR": ["floor", None]})
    bs[divy]["parent"] = floory
    muly = gen(); bs[muly] = mk("operator_multiply",
        inputs={"NUM1": slot(floory), "NUM2": num(CELL)})
    bs[floory]["parent"] = muly
    suby = gen(); bs[suby] = mk("operator_subtract",
        inputs={"NUM1": num(BOARD_Y0), "NUM2": slot(muly)})
    bs[muly]["parent"] = suby

    goto_c = gen(); bs[goto_c] = mk("motion_gotoxy",
        inputs={"X": slot(addx), "Y": slot(suby)})
    bs[addx]["parent"] = goto_c; bs[suby]["parent"] = goto_c
    show_c = gen(); bs[show_c] = mk("looks_show")
    chain([(sc, bs[sc]), (sw, bs[sw]), (goto_c, bs[goto_c]), (show_c, bs[show_c])])

    # when receive 보드지우기 (클론만): delete this clone
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=300, y=200,
        fields={"BROADCAST_OPTION": ["보드지우기", BR_CLEARC]})
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    chain([(hc, bs[hc]), (del_c, bs[del_c])])

    return bs

# ============================================================
#  게임오버 배너
# ============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    state_v1 = vrep("게임상태", V_STATE)
    cond_one = cmp_op("operator_equals", state_v1, 1)
    wait_start = gen(); bs[wait_start] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_one]})
    bs[cond_one]["parent"] = wait_start

    state_v2 = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", state_v2, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_zero]})
    bs[cond_zero]["parent"] = wait_over

    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (wait_start, bs[wait_start]), (wait_over, bs[wait_over]), (show, bs[show])])
    return bs

# ============================================================
#  ASSEMBLE PROJECT
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    def write_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        return m

    bg_md5 = write_svg(BG_SVG)
    cell_md5 = [write_svg(s) for s in CELL_SVGS]
    go_md5 = write_svg(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks   = build_stage_blocks()
    logic_blocks   = build_logic_blocks()
    current_blocks = build_current_blocks()
    board_blocks   = build_boardcell_blocks()
    go_blocks      = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    cell_costumes = lambda: [{
        "name": str(i + 1), "bitmapResolution": 1, "dataFormat": "svg",
        "assetId": cell_md5[i], "md5ext": f"{cell_md5[i]}.svg",
        "rotationCenterX": 10, "rotationCenterY": 10
    } for i in range(7)]

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:   ["점수", 0],
            V_BEST:    ["최고기록", 0],
            V_STATE:   ["게임상태", 1],
            V_LINES:   ["줄수", 0],
            V_LEVEL:   ["레벨", 1],
            V_DROP:    ["낙하간격", 0.8],
            V_PIECE:   ["현피스", 1],
            V_ROT:     ["현회전", 0],
            V_COL:     ["현열", 3],
            V_ROW:     ["현행", 0],
            V_NEXT:    ["다음피스", 1],
            V_CLEARED: ["지운줄카운트", 0],
        },
        "lists": {
            L_BOARD: ["보드", [0] * 112],
            L_OFFC:  ["오프셋C", offC],
            L_OFFR:  ["오프셋R", offR],
            L_CURX:  ["현셀X", [0, 0, 0, 0]],
            L_CURY:  ["현셀Y", [0, 0, 0, 0]],
        },
        "broadcasts": {
            BR_START:   "게임시작",
            BR_TICK:    "브틱",
            BR_SPAWN:   "새블록",
            BR_DRAWCUR: "현재블록그리기",
            BR_DRAWBRD: "보드그리기",
            BR_CLEARC:  "보드지우기",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "배경", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    logic = {
        "isStage": False, "name": "블록판정기",
        "variables": {
            V_TCOL:    ["시험열", 0],
            V_TROW:    ["시험행", 0],
            V_TROT:    ["시험회전", 0],
            V_CELLCOL: ["셀col", 0],
            V_CELLROW: ["셀row", 0],
            V_CELLIDX: ["셀idx", 0],
            V_I:       ["i", 0],
            V_J:       ["j", 0],
            V_OFFBASE: ["오프베이스", 0],
            V_HIT:     ["충돌됨", 0],
            V_ROWFULL: ["행꽉참", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": logic_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": cell_costumes(),
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    current = {
        "isStage": False, "name": "현재블록",
        "variables": {
            V_SEG:         ["셀번호", 0],
            V_CUR_OFFBASE: ["오프베이스C", 0],
            V_CUR_CELLCOL: ["셀colC", 0],
            V_CUR_CELLROW: ["셀rowC", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": current_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": cell_costumes(),
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    board = {
        "isStage": False, "name": "보드셀",
        "variables": {
            V_DRAWIDX: ["그릴idx", 0],
            V_DRAWCOL: ["그릴색", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": board_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": cell_costumes(),
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    gameover = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": go_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": go_md5, "md5ext": f"{go_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 85
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 300, "y": 250,
         "visible": True, "sliderMin": 0, "sliderMax": 100000, "isDiscrete": True},
        {"id": V_LINES, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "줄수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 300, "y": 280,
         "visible": True, "sliderMin": 0, "sliderMax": 1000, "isDiscrete": True},
        {"id": V_LEVEL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "레벨"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 300, "y": 310,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_BEST, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "최고기록"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 300, "y": 340,
         "visible": True, "sliderMin": 0, "sliderMax": 100000, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, logic, board, current, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "tetris-mini-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # self-check
    with open(pj, "r", encoding="utf-8") as f:
        proj = json.load(f)
    bad = zipfile.ZipFile(OUTPUT).testzip()
    assert bad is None, f"corrupt zip member: {bad}"

    # 블록 참조 무결성: 각 sprite 의 next/parent/input/field 가 같은 dict 내 존재
    _check_integrity(proj)

    print(f"wrote {OUTPUT}")
    print(f"  stage:        {len(stage_blocks)} blocks")
    print(f"  블록판정기:   {len(logic_blocks)} blocks")
    print(f"  보드셀:       {len(board_blocks)} blocks")
    print(f"  현재블록:     {len(current_blocks)} blocks")
    print(f"  게임오버:     {len(go_blocks)} blocks")
    total = (len(stage_blocks) + len(logic_blocks) + len(board_blocks)
             + len(current_blocks) + len(go_blocks))
    print(f"  TOTAL:        {total} blocks")
    print(f"  targets:      {len(proj['targets'])}")
    print(f"  offC[1..4]={offC[0:4]}  offC[109..112]={offC[108:112]}")
    print(f"  offR[1..4]={offR[0:4]}  offR[109..112]={offR[108:112]}")


def _check_integrity(proj):
    """블록 참조 무결성 자체 검사 — next/parent 및 input/field 의 block-id 참조가
    같은 target.blocks dict 안에 모두 존재하는지 확인."""
    errs = []
    for t in proj["targets"]:
        blocks = t["blocks"]
        name = t["name"]
        ids = set(blocks.keys())
        for bid, b in blocks.items():
            if not isinstance(b, dict):
                continue
            nx = b.get("next")
            if nx is not None and nx not in ids:
                errs.append(f"{name}:{bid} next -> {nx} 없음")
            pa = b.get("parent")
            if pa is not None and pa not in ids:
                errs.append(f"{name}:{bid} parent -> {pa} 없음")
            for k, inp in (b.get("inputs") or {}).items():
                # inp 형태: [t, val, ...] 에서 block-id 후보 추출
                for el in inp[1:]:
                    if isinstance(el, str) and el.startswith("b") and el not in ids:
                        errs.append(f"{name}:{bid} input {k} -> {el} 없음")
                # [2, id] 형태
                if len(inp) >= 2 and isinstance(inp[1], str):
                    if inp[1].startswith("b") and inp[1] not in ids:
                        errs.append(f"{name}:{bid} input {k} -> {inp[1]} 없음")
    if errs:
        raise AssertionError("블록 참조 무결성 오류:\n" + "\n".join(errs[:40]))
    print("  integrity:    OK (모든 next/parent/input 참조 유효)")


if __name__ == "__main__":
    main()
