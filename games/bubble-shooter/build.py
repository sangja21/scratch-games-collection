#!/usr/bin/env python3
"""버블 슈터 (bubble-shooter) — 화면 아래 발사대에서 색깔 거품을 위로 쏜다.

마우스로 조준(위쪽 반원 ±80° clamp)하고 클릭하면 거품이 직선으로 날아간다.
좌우 벽에 맞으면 튕기고, 천장이나 기존 거품에 닿으면 가장 가까운 빈 격자 칸에
딱 붙는다(스냅). 같은 색 거품이 3개 이상 연결되면 그 무리가 전부 터지고 점수 +.
거품이 바닥선(row11)까지 내려오면 게임오버, 화면의 거품을 전부 없애면 승리.

베이스: games/tetris-mini/build.py
  (2D 격자 → 1D 리스트 평탄화 idx=row*8+col+1 + data_replaceitemoflist(replace_at)
   + 셀 클론 격자 렌더 + my block(procedures_*) 동기 서브루틴)
  + games/pacman-mini/build.py (보드 리스트 단일 진실원)
  + games/missile-command/build.py · zombie-shooter (마우스 조준 point towards
    mouse-pointer + 각도 clamp + sin/cos 속도 분해 + dx/dy 직선 비행 + 벽 반사)
  + games/car-race/build.py (게임상태 broadcast + 게임오버/승리 배너)

구현 범위 (plan MVP 권장):
  - 떠 있는 거품 낙하(7.6 낙하정리) **생략** (MVP 권장).
  - 압박(한줄내림, 7.7) **포함** (한줄주기=5).
  - NEXT 미리보기 sprite **포함** (5 targets).
  - 충돌검사는 좌표 기반(결정적) — 비행 거품 중심이 찬 칸 중심과 28px 이내면 충돌.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "버블슈터.sb3")

# ============================================================
#  좌표 / 격자 상수 (2절)
# ============================================================
COLS = 8
ROWS = 12
CELL = 30                 # 한 칸 30px (거품 28px + 2px 틈)
COL0_X = -210             # col0 중심 X
ROW0_Y = 165              # row0 중심 Y
LEFT_WALL  = -225 + 14    # = -211 (왼쪽 벽 + 반지름 14)
RIGHT_WALL = 15 - 14      # = 1   (오른쪽 벽 - 반지름 14)
CEIL_Y = 165              # 비행Y >= 165 면 천장(row0 줄) 충돌
SHOOTER_X = -105
SHOOTER_Y = -150
SPEED = 12                # 프레임당 비행 속도(px)
COLLIDE_DIST = 28         # 충돌검사 임계 거리(px)

# ============================================================
#  거품 색 (1빨강 2주황 3노랑 4초록 5파랑)
# ============================================================
BUBBLE_FILL   = ["#F44336", "#FF9800", "#FFEB3B", "#4CAF50", "#2196F3"]
BUBBLE_STROKE = ["#B71C1C", "#E65100", "#F9A825", "#2E7D32", "#1565C0"]

# ============================================================
#  helpers (tetris/snake build.py 와 동일 — 그대로 복제)
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

# ---- list block helpers (snake + replace_at + delete_at) ----
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

    def delete_at(name, lid, index):
        bid = gen()
        ins = {"INDEX": slot(index) if isinstance(index, str) else text_lit(index)}
        bs[bid] = mk("data_deleteoflist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(index, str): bs[index]["parent"] = bid
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
        bid = gen()
        ins = {
            "INDEX": slot(index) if isinstance(index, str) else text_lit(index),
            "ITEM":  slot(item)  if isinstance(item, str)  else text_lit(item),
        }
        bs[bid] = mk("data_replaceitemoflist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(index, str): bs[index]["parent"] = bid
        if isinstance(item, str):  bs[item]["parent"] = bid
        return bid

    return add_to, delete_all, delete_at, item_of, length_of, replace_at

# ---- my block (custom procedure) helpers ----
def make_proc_def(bs, proccode, warp=True):
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
#  IDs (12절)
# ============================================================
# 글로벌 변수 (Stage)
V_SCORE  = "varScore01"
V_BEST   = "varBest02"
V_STATE  = "varState03"
V_REMAIN = "varRemain04"
V_CUR    = "varCurColor05"
V_NEXT   = "varNextColor06"
V_SHOTS  = "varShots07"
V_PUSH   = "varPushEvery08"
# 슈터 sprite-local
V_FLYX   = "varFlyX09"
V_FLYY   = "varFlyY10"
V_VX     = "varVX11"
V_VY     = "varVY12"
V_SNAPC  = "varSnapCol13"
V_SNAPR  = "varSnapRow14"
V_SNAPI  = "varSnapIdx15"
V_BESTD  = "varBestDist16"
V_MCOLOR = "varMatchColor17"
V_GROUPN = "varGroupN18"
V_CURIDX = "varCurIdx19"
V_CURCOL = "varCurCol20"
V_CURROW = "varCurRow21"
V_NBRIDX = "varNbrIdx22"
V_I      = "varI23"
V_ANGLE  = "varAngle24"
V_CELLX  = "varCellX27"   # 충돌검사/스냅 임시
V_CELLY  = "varCellY28"
V_DIST   = "varDist29"
V_HITF   = "varHitFlag30" # 비행루프 충돌 플래그
# 격자셀 sprite-local
V_DRAWIDX = "varDrawIdx25"
V_DRAWCOL = "varDrawColor26"

# 리스트 (Stage 글로벌)
L_BOARD   = "L_board01"
L_QUEUE   = "L_queue02"
L_VISITED = "L_visited03"
L_REMOVE  = "L_remove04"

# broadcasts
BR_START   = "brStart01"
BR_DRAW    = "brDrawBoard02"
BR_CLEAR   = "brClearCells03"
BR_NEXT    = "brNextReady04"

# proccodes
PC_FLY   = "비행루프"
PC_COLL  = "충돌검사"
PC_SNAP  = "스냅"
PC_MATCH = "매칭"
PC_NEXTB = "다음거품"
PC_PUSH  = "한줄내림"

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
#  SVG assets
# ============================================================
# SVG(0~480,0~360) ↔ Scratch(-240~240,-180~180): svg_x = scratch_x+240, svg_y=180-scratch_y
# 격자 영역: Scratch (-225,180)~(15,-180) -> svg (15,0)~(255,360).
def _grid_lines():
    lines = []
    gx0, gy0 = 15, 0
    w, h = COLS * CELL, ROWS * CELL   # 240 x 360
    for c in range(COLS + 1):
        x = gx0 + c * CELL
        lines.append(f'    <line x1="{x}" y1="{gy0}" x2="{x}" y2="{gy0+h}" stroke="#3949AB" stroke-width="1" opacity="0.5"/>')
    for r in range(ROWS + 1):
        y = gy0 + r * CELL
        lines.append(f'    <line x1="{gx0}" y1="{y}" x2="{gx0+w}" y2="{y}" stroke="#3949AB" stroke-width="1" opacity="0.5"/>')
    return "\n".join(lines)

# row11 윗 경계(=row10/row11 사이) = row10 중심+15 = Y=165-10.5*30+15... 단순히 row11 윗변:
# row11 중심 Y=165-11*30=-165, 윗변=-165+15=-150 -> svg y = 180-(-150)=330.
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#1A1146"/>
      <stop offset="1" stop-color="#0B0828"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="480" height="360" fill="url(#bgGrad)"/>
  <!-- 격자 영역 배경 -->
  <rect x="15" y="0" width="240" height="360" fill="#15103A" opacity="0.55"/>
  <!-- 격자선 -->
  <g>
__GRID__
  </g>
  <!-- 좌/우/천장 벽 라인 -->
  <line x1="15" y1="0" x2="15" y2="360" stroke="#7E57C2" stroke-width="3"/>
  <line x1="255" y1="0" x2="255" y2="360" stroke="#7E57C2" stroke-width="3"/>
  <line x1="15" y1="0" x2="255" y2="0" stroke="#7E57C2" stroke-width="3"/>
  <!-- 빨간 바닥선 (row11 윗 경계, svg y=330) -->
  <line x1="15" y1="330" x2="255" y2="330" stroke="#FF1744" stroke-width="3" stroke-dasharray="8 5"/>
  <text x="135" y="352" text-anchor="middle" fill="#FF5252" font-family="Arial, Helvetica, sans-serif" font-size="12">바닥선</text>
  <!-- 오른쪽 패널 -->
  <text x="360" y="40" text-anchor="middle" fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="bold">BUBBLE</text>
  <text x="360" y="62" text-anchor="middle" fill="#B39DDB" font-family="Arial, Helvetica, sans-serif" font-size="16" font-weight="bold">SHOOTER</text>
  <text x="360" y="150" text-anchor="middle" fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif" font-size="16" font-weight="bold">NEXT</text>
  <rect x="330" y="160" width="60" height="60" rx="10" fill="#0D0A28" stroke="#FFFFFF" stroke-width="2"/>
  <text x="360" y="300" text-anchor="middle" fill="#90CAF9" font-family="Arial, Helvetica, sans-serif" font-size="12">마우스로 조준</text>
  <text x="360" y="320" text-anchor="middle" fill="#90CAF9" font-family="Arial, Helvetica, sans-serif" font-size="12">클릭/스페이스 발사</text>
</svg>""".replace("__GRID__", _grid_lines())

def _bubble_svg(fill, stroke):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">
  <circle cx="14" cy="14" r="13" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
  <ellipse cx="10" cy="9" rx="5" ry="4" fill="#FFFFFF" opacity="0.45"/>
</svg>"""

BUBBLE_SVGS = [_bubble_svg(BUBBLE_FILL[i], BUBBLE_STROKE[i]) for i in range(5)]

GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14" fill="#000000" opacity="0.92" stroke="#FF1744" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle" fill="#FF5252" font-family="Arial, Helvetica, sans-serif" font-size="42" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif" font-size="18">거품이 바닥에 닿았어요</text>
  <text x="180" y="138" text-anchor="middle" fill="#FFCDD2" font-family="Arial, Helvetica, sans-serif" font-size="13">초록 깃발(▶) 다시 클릭으로 재시작</text>
</svg>"""

WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14" fill="#000000" opacity="0.92" stroke="#69F0AE" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle" fill="#69F0AE" font-family="Arial, Helvetica, sans-serif" font-size="46" font-weight="bold">YOU WIN!</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif" font-size="18">거품을 다 터뜨렸어요!</text>
  <text x="180" y="138" text-anchor="middle" fill="#C8E6C9" font-family="Arial, Helvetica, sans-serif" font-size="13">초록 깃발(▶) 다시 클릭으로 재시작</text>
</svg>"""

# ============================================================
#  STAGE blocks (10절)
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    add_to, delete_all, delete_at, item_of, length_of, replace_at = make_list_helpers(bs)

    # === when flag clicked: init vars + 보드/리스트 초기화 + broadcast ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]

    def set_var(name, vid, val):
        sid = gen()
        bs[sid] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
        seq.append((sid, bs[sid])); return sid

    set_var("점수", V_SCORE, 0)
    set_var("게임상태", V_STATE, 1)
    set_var("발사수", V_SHOTS, 0)
    set_var("한줄주기", V_PUSH, 5)

    # 현재색 = random 1..5 ; 다음색 = random 1..5
    r1 = gen(); bs[r1] = mk("operator_random", inputs={"FROM": num(1), "TO": num(5)})
    sc = gen(); bs[sc] = mk("data_setvariableto",
        inputs={"VALUE": slot(r1)}, fields={"VARIABLE": ["현재색", V_CUR]})
    bs[r1]["parent"] = sc; seq.append((sc, bs[sc]))
    r2 = gen(); bs[r2] = mk("operator_random", inputs={"FROM": num(1), "TO": num(5)})
    sn = gen(); bs[sn] = mk("data_setvariableto",
        inputs={"VALUE": slot(r2)}, fields={"VARIABLE": ["다음색", V_NEXT]})
    bs[r2]["parent"] = sn; seq.append((sn, bs[sn]))

    # 보드 96칸: delete all ; repeat 40: add (random 1..5) [row0~4] ; repeat 56: add 0 [row5~11]
    # (idx 1..40 = 색, idx 41..96 = 0 — plan 3절 초기 배치와 동일. 카운터 변수 불필요.)
    da_b = delete_all("보드", L_BOARD); seq.append((da_b, bs[da_b]))
    rr = gen(); bs[rr] = mk("operator_random", inputs={"FROM": num(1), "TO": num(5)})
    add_rnd = add_to("보드", L_BOARD, rr)
    rep40 = gen(); bs[rep40] = mk("control_repeat",
        inputs={"TIMES": num(40), "SUBSTACK": [2, add_rnd]})
    bs[add_rnd]["parent"] = rep40; seq.append((rep40, bs[rep40]))
    add0 = add_to("보드", L_BOARD, 0)
    rep56 = gen(); bs[rep56] = mk("control_repeat",
        inputs={"TIMES": num(56), "SUBSTACK": [2, add0]})
    bs[add0]["parent"] = rep56; seq.append((rep56, bs[rep56]))

    # 남은거품 = 40
    set_var("남은거품", V_REMAIN, 40)

    # 작업 리스트 초기화: 매칭대기/제거대기 비움 ; 매칭표시 96칸 0
    da_q = delete_all("매칭대기", L_QUEUE); seq.append((da_q, bs[da_q]))
    da_r = delete_all("제거대기", L_REMOVE); seq.append((da_r, bs[da_r]))
    da_v = delete_all("매칭표시", L_VISITED); seq.append((da_v, bs[da_v]))
    add0v = add_to("매칭표시", L_VISITED, 0)
    rep96v = gen(); bs[rep96v] = mk("control_repeat",
        inputs={"TIMES": num(96), "SUBSTACK": [2, add0v]})
    bs[add0v]["parent"] = rep96v; seq.append((rep96v, bs[rep96v]))

    # broadcast 게임시작 ; 보드그리기 ; 다음거품준비
    bc_start = broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    bc_draw = broadcast(bs, "보드그리기", BR_DRAW); seq.append((bc_draw, bs[bc_draw]))
    bc_next = broadcast(bs, "다음거품준비", BR_NEXT); seq.append((bc_next, bs[bc_next]))

    chain(seq)
    return bs

# ============================================================
#  슈터 (조준 + 비행 + 스냅 + 매칭) — 게임의 두뇌
# ============================================================
def build_shooter_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    add_to, delete_all, delete_at, item_of, length_of, replace_at = make_list_helpers(bs)

    # 작은 보조
    def set_num(name, vid, val):
        b = gen(); bs[b] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
        return b
    def set_expr(name, vid, expr_id):
        b = gen(); bs[b] = mk("data_setvariableto",
            inputs={"VALUE": slot(expr_id)}, fields={"VARIABLE": [name, vid]})
        bs[expr_id]["parent"] = b; return b
    def change_num(name, vid, val):
        b = gen(); bs[b] = mk("data_changevariableby",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
        return b
    def mathop(operator, x_id):
        b = gen(); bs[b] = mk("operator_mathop",
            inputs={"NUM": slot(x_id)}, fields={"OPERATOR": [operator, None]})
        bs[x_id]["parent"] = b; return b
    def state_over_cond():
        st1 = vrep("게임상태", V_STATE); c0 = cmp_op("operator_equals", st1, 0)
        st2 = vrep("게임상태", V_STATE); c3 = cmp_op("operator_equals", st2, 3)
        return bool_op("operator_or", c0, c3)

    # idx(1-base) -> col/row 식 (현idx 기반). idx_vid 는 변수 id.
    def col_from_idx(idx_name, idx_vid):
        iv = vrep(idx_name, idx_vid)
        sub1 = op("operator_subtract", iv, 1)
        return op("operator_mod", sub1, 8)
    def row_from_idx(idx_name, idx_vid):
        iv = vrep(idx_name, idx_vid)
        sub1 = op("operator_subtract", iv, 1)
        d8 = op("operator_divide", sub1, 8)
        return mathop("floor", d8)

    def sqdist():
        """제곱거리 = (비행X-셀X)^2 + (비행Y-셀Y)^2.
        각 제곱은 독립 reporter 2개를 곱한다(같은 블록 재사용 금지)."""
        # (비행X-셀X)^2 : 두 개의 별도 (비행X-셀X) 차이 reporter 를 곱함
        fxa = vrep("비행X", V_FLYX); cxa = vrep("셀X", V_CELLX)
        dxa = op("operator_subtract", fxa, cxa)
        fxb = vrep("비행X", V_FLYX); cxb = vrep("셀X", V_CELLX)
        dxb = op("operator_subtract", fxb, cxb)
        sqx = op("operator_multiply", dxa, dxb)
        fya = vrep("비행Y", V_FLYY); cya = vrep("셀Y", V_CELLY)
        dya = op("operator_subtract", fya, cya)
        fyb = vrep("비행Y", V_FLYY); cyb = vrep("셀Y", V_CELLY)
        dyb = op("operator_subtract", fyb, cyb)
        sqy = op("operator_multiply", dya, dyb)
        return op("operator_add", sqx, sqy)

    # ============================================================
    #  define 비행루프  (화면 갱신 ON 필요 → warp=False)
    # ============================================================
    def_fly, _ = make_proc_def(bs, PC_FLY, warp=False)

    # 히트플래그 = 0
    set_hit0 = set_num("히트플래그", V_HITF, 0)

    # --- repeat until 히트플래그 = 1 본문 ---
    # 비행X += 속도X ; 비행Y += 속도Y
    vx = vrep("속도X", V_VX)
    inc_flyx = gen(); bs[inc_flyx] = mk("data_changevariableby",
        inputs={"VALUE": slot(vx)}, fields={"VARIABLE": ["비행X", V_FLYX]})
    bs[vx]["parent"] = inc_flyx
    vy = vrep("속도Y", V_VY)
    inc_flyy = gen(); bs[inc_flyy] = mk("data_changevariableby",
        inputs={"VALUE": slot(vy)}, fields={"VARIABLE": ["비행Y", V_FLYY]})
    bs[vy]["parent"] = inc_flyy

    # (1) 좌측 벽: if 비행X < LEFT_WALL: 비행X=LEFT_WALL ; 속도X *= -1
    fx_l = vrep("비행X", V_FLYX)
    c_left = cmp_op("operator_lt", fx_l, LEFT_WALL)
    set_fxl = set_num("비행X", V_FLYX, LEFT_WALL)
    vx_l = vrep("속도X", V_VX)
    neg_vxl = op("operator_multiply", vx_l, -1)
    set_vxl = set_expr("속도X", V_VX, neg_vxl)
    chain([(set_fxl, bs[set_fxl]), (set_vxl, bs[set_vxl])])
    if_left = gen(); bs[if_left] = mk("control_if",
        inputs={"CONDITION": [2, c_left], "SUBSTACK": [2, set_fxl]})
    bs[c_left]["parent"] = if_left; bs[set_fxl]["parent"] = if_left

    # 우측 벽: if 비행X > RIGHT_WALL
    fx_r = vrep("비행X", V_FLYX)
    c_right = cmp_op("operator_gt", fx_r, RIGHT_WALL)
    set_fxr = set_num("비행X", V_FLYX, RIGHT_WALL)
    vx_r = vrep("속도X", V_VX)
    neg_vxr = op("operator_multiply", vx_r, -1)
    set_vxr = set_expr("속도X", V_VX, neg_vxr)
    chain([(set_fxr, bs[set_fxr]), (set_vxr, bs[set_vxr])])
    if_right = gen(); bs[if_right] = mk("control_if",
        inputs={"CONDITION": [2, c_right], "SUBSTACK": [2, set_fxr]})
    bs[c_right]["parent"] = if_right; bs[set_fxr]["parent"] = if_right

    # goto (비행X, 비행Y)
    fxg = vrep("비행X", V_FLYX); fyg = vrep("비행Y", V_FLYY)
    goto_fly = gen(); bs[goto_fly] = mk("motion_gotoxy",
        inputs={"X": slot(fxg), "Y": slot(fyg)})
    bs[fxg]["parent"] = goto_fly; bs[fyg]["parent"] = goto_fly

    # (2) 천장: if 비행Y >= CEIL_Y: call 스냅 ; 히트플래그 = 1
    fy_c = vrep("비행Y", V_FLYY)
    c_ceil = cmp_op("operator_gt", fy_c, CEIL_Y - 1)   # >= 165  ~= > 164
    call_snap_c = make_proc_call(bs, PC_SNAP, warp=True)
    set_hit1c = set_num("히트플래그", V_HITF, 1)
    chain([(call_snap_c, bs[call_snap_c]), (set_hit1c, bs[set_hit1c])])
    if_ceil = gen(); bs[if_ceil] = mk("control_if",
        inputs={"CONDITION": [2, c_ceil], "SUBSTACK": [2, call_snap_c]})
    bs[c_ceil]["parent"] = if_ceil; bs[call_snap_c]["parent"] = if_ceil

    # (3) if 히트플래그 = 0: call 충돌검사   (천장에서 이미 붙었으면 검사 skip)
    hf1 = vrep("히트플래그", V_HITF)
    c_hf0 = cmp_op("operator_equals", hf1, 0)
    call_coll = make_proc_call(bs, PC_COLL, warp=True)
    if_coll = gen(); bs[if_coll] = mk("control_if",
        inputs={"CONDITION": [2, c_hf0], "SUBSTACK": [2, call_coll]})
    bs[c_hf0]["parent"] = if_coll; bs[call_coll]["parent"] = if_coll

    # 본문 체인
    chain([(inc_flyx, bs[inc_flyx]), (inc_flyy, bs[inc_flyy]),
           (if_left, bs[if_left]), (if_right, bs[if_right]),
           (goto_fly, bs[goto_fly]), (if_ceil, bs[if_ceil]), (if_coll, bs[if_coll])])

    hf2 = vrep("히트플래그", V_HITF)
    c_hf1 = cmp_op("operator_equals", hf2, 1)
    rep_fly = gen(); bs[rep_fly] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_hf1], "SUBSTACK": [2, inc_flyx]})
    bs[c_hf1]["parent"] = rep_fly; bs[inc_flyx]["parent"] = rep_fly

    chain([(def_fly, bs[def_fly]), (set_hit0, bs[set_hit0]), (rep_fly, bs[rep_fly])])

    # ============================================================
    #  define 충돌검사 (warp) — 찬 칸 중심과 28px 이내면 스냅 + 히트
    # ============================================================
    def_coll, _ = make_proc_def(bs, PC_COLL, warp=True)
    set_i1c = set_num("i", V_I, 1)

    # repeat 96 본문: if item(i) of 보드 != 0: { 셀X/셀Y 계산 ; if dist<28: call 스냅 ; 히트플래그=1 }
    iv_c1 = vrep("i", V_I)
    brd_c = item_of("보드", L_BOARD, iv_c1)
    c_ne0 = cmp_op("operator_not_equals", brd_c, 0)

    # 셀X = -210 + ((i-1) mod 8)*30
    colc = col_from_idx("i", V_I)
    mulcx = op("operator_multiply", colc, CELL)
    addcx = op("operator_add", COL0_X, mulcx, key1="NUM1", key2="NUM2")
    # COL0_X is int literal -> need to ensure op handles int+str: op(a,b) with a int, b str
    set_cellx = set_expr("셀X", V_CELLX, addcx)
    # 셀Y = 165 - floor((i-1)/8)*30
    rowc = row_from_idx("i", V_I)
    mulcy = op("operator_multiply", rowc, CELL)
    subcy = op("operator_subtract", ROW0_Y, mulcy)
    set_celly = set_expr("셀Y", V_CELLY, subcy)

    # dist^2 = (비행X-셀X)^2 + (비행Y-셀Y)^2  (sqrt 불필요, 임계 28^2=784)
    sumd = sqdist()
    set_dist = set_expr("거리", V_DIST, sumd)

    dist_v = vrep("거리", V_DIST)
    c_close = cmp_op("operator_lt", dist_v, COLLIDE_DIST * COLLIDE_DIST)
    call_snap_coll = make_proc_call(bs, PC_SNAP, warp=True)
    set_hit1coll = set_num("히트플래그", V_HITF, 1)
    chain([(call_snap_coll, bs[call_snap_coll]), (set_hit1coll, bs[set_hit1coll])])
    if_close = gen(); bs[if_close] = mk("control_if",
        inputs={"CONDITION": [2, c_close], "SUBSTACK": [2, call_snap_coll]})
    bs[c_close]["parent"] = if_close; bs[call_snap_coll]["parent"] = if_close

    chain([(set_cellx, bs[set_cellx]), (set_celly, bs[set_celly]),
           (set_dist, bs[set_dist]), (if_close, bs[if_close])])
    if_filled = gen(); bs[if_filled] = mk("control_if",
        inputs={"CONDITION": [2, c_ne0], "SUBSTACK": [2, set_cellx]})
    bs[c_ne0]["parent"] = if_filled; bs[set_cellx]["parent"] = if_filled

    inc_ic = change_num("i", V_I, 1)
    # 조기 종료를 위해 히트플래그=1 이면 더 안 붙이도록: if 히트플래그=0 으로 감쌈
    hfc = vrep("히트플래그", V_HITF)
    c_hfc0 = cmp_op("operator_equals", hfc, 0)
    if_notyet = gen(); bs[if_notyet] = mk("control_if",
        inputs={"CONDITION": [2, c_hfc0], "SUBSTACK": [2, if_filled]})
    bs[c_hfc0]["parent"] = if_notyet; bs[if_filled]["parent"] = if_notyet
    chain([(if_notyet, bs[if_notyet]), (inc_ic, bs[inc_ic])])

    rep96c = gen(); bs[rep96c] = mk("control_repeat",
        inputs={"TIMES": num(96), "SUBSTACK": [2, if_notyet]})
    bs[if_notyet]["parent"] = rep96c
    chain([(def_coll, bs[def_coll]), (set_i1c, bs[set_i1c]), (rep96c, bs[rep96c])])

    # ============================================================
    #  define 스냅 (warp) — 가장 가까운 빈 칸에 붙이기 (7.4)
    # ============================================================
    def_snap, _ = make_proc_def(bs, PC_SNAP, warp=True)
    set_bestd = set_num("최소거리", V_BESTD, 999999)
    set_snapi0 = set_num("스냅idx", V_SNAPI, 0)
    set_i1s = set_num("i", V_I, 1)

    # repeat 96: if item(i)=0: { 셀X/셀Y ; 거리(제곱) ; if 거리<최소거리: 최소거리=거리 ; 스냅idx=i }
    iv_s1 = vrep("i", V_I)
    brd_s = item_of("보드", L_BOARD, iv_s1)
    c_eq0 = cmp_op("operator_equals", brd_s, 0)

    cols2 = col_from_idx("i", V_I)
    mulsx = op("operator_multiply", cols2, CELL)
    addsx = op("operator_add", COL0_X, mulsx)
    set_scellx = set_expr("셀X", V_CELLX, addsx)
    rows2 = row_from_idx("i", V_I)
    mulsy = op("operator_multiply", rows2, CELL)
    subsy = op("operator_subtract", ROW0_Y, mulsy)
    set_scelly = set_expr("셀Y", V_CELLY, subsy)

    sumds = sqdist()
    set_sdist = set_expr("거리", V_DIST, sumds)

    dist_s = vrep("거리", V_DIST); bestd_s = vrep("최소거리", V_BESTD)
    c_lt = cmp_op("operator_lt", dist_s, bestd_s)
    dist_s2 = vrep("거리", V_DIST)
    set_best = set_expr("최소거리", V_BESTD, dist_s2)
    iv_snap = vrep("i", V_I)
    set_snapi = set_expr("스냅idx", V_SNAPI, iv_snap)
    chain([(set_best, bs[set_best]), (set_snapi, bs[set_snapi])])
    if_better = gen(); bs[if_better] = mk("control_if",
        inputs={"CONDITION": [2, c_lt], "SUBSTACK": [2, set_best]})
    bs[c_lt]["parent"] = if_better; bs[set_best]["parent"] = if_better

    chain([(set_scellx, bs[set_scellx]), (set_scelly, bs[set_scelly]),
           (set_sdist, bs[set_sdist]), (if_better, bs[if_better])])
    if_empty = gen(); bs[if_empty] = mk("control_if",
        inputs={"CONDITION": [2, c_eq0], "SUBSTACK": [2, set_scellx]})
    bs[c_eq0]["parent"] = if_empty; bs[set_scellx]["parent"] = if_empty
    inc_is = change_num("i", V_I, 1)
    chain([(if_empty, bs[if_empty]), (inc_is, bs[inc_is])])
    rep96s = gen(); bs[rep96s] = mk("control_repeat",
        inputs={"TIMES": num(96), "SUBSTACK": [2, if_empty]})
    bs[if_empty]["parent"] = rep96s

    # if 스냅idx > 0: { replace 보드(스냅idx)=현재색 ; 스냅row=floor((스냅idx-1)/8) ;
    #                  남은거품+1 ; broadcast 보드그리기 ; play sound ;
    #                  if 스냅row>=11: 게임상태=0 else: call 매칭 }
    snapi_c = vrep("스냅idx", V_SNAPI)
    c_snap_gt0 = cmp_op("operator_gt", snapi_c, 0)

    snapi_w = vrep("스냅idx", V_SNAPI); cur_w = vrep("현재색", V_CUR)
    rep_board = gen(); bs[rep_board] = mk("data_replaceitemoflist",
        inputs={"INDEX": slot(snapi_w), "ITEM": slot(cur_w)},
        fields={"LIST": ["보드", L_BOARD]})
    bs[snapi_w]["parent"] = rep_board; bs[cur_w]["parent"] = rep_board

    # 스냅row = floor((스냅idx-1)/8)
    snapr_expr = row_from_idx("스냅idx", V_SNAPI)
    set_snapr = set_expr("스냅row", V_SNAPR, snapr_expr)
    inc_remain = change_num("남은거품", V_REMAIN, 1)
    bc_draw_s = broadcast(bs, "보드그리기", BR_DRAW)
    # play sound pop
    snm_s = gen(); bs[snm_s] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_s = gen(); bs[snd_s] = mk("sound_play", inputs={"SOUND_MENU": [1, snm_s]})
    bs[snm_s]["parent"] = snd_s

    # if 스냅row >= 11: 게임상태=0 else: call 매칭
    snapr_chk = vrep("스냅row", V_SNAPR)
    c_floor = cmp_op("operator_gt", snapr_chk, 10)  # >=11
    set_state0 = set_num("게임상태", V_STATE, 0)
    call_match = make_proc_call(bs, PC_MATCH, warp=True)
    if_floor = gen(); bs[if_floor] = mk("control_if_else",
        inputs={"CONDITION": [2, c_floor], "SUBSTACK": [2, set_state0],
                "SUBSTACK2": [2, call_match]})
    bs[c_floor]["parent"] = if_floor
    bs[set_state0]["parent"] = if_floor
    bs[call_match]["parent"] = if_floor

    chain([(rep_board, bs[rep_board]), (set_snapr, bs[set_snapr]),
           (inc_remain, bs[inc_remain]), (bc_draw_s, bs[bc_draw_s]),
           (snd_s, bs[snd_s]), (if_floor, bs[if_floor])])
    if_snapok = gen(); bs[if_snapok] = mk("control_if",
        inputs={"CONDITION": [2, c_snap_gt0], "SUBSTACK": [2, rep_board]})
    bs[c_snap_gt0]["parent"] = if_snapok; bs[rep_board]["parent"] = if_snapok

    # hide (비행 거품 본체 숨김)
    hide_s = gen(); bs[hide_s] = mk("looks_hide")

    chain([(def_snap, bs[def_snap]), (set_bestd, bs[set_bestd]),
           (set_snapi0, bs[set_snapi0]), (set_i1s, bs[set_i1s]),
           (rep96s, bs[rep96s]), (if_snapok, bs[if_snapok]), (hide_s, bs[hide_s])])

    # ============================================================
    #  define 매칭 (warp) — 스택 리스트 flood fill (7.5)
    # ============================================================
    def_match, _ = make_proc_def(bs, PC_MATCH, warp=True)

    # 매칭색 = 현재색
    cur_m = vrep("현재색", V_CUR)
    set_mcolor = set_expr("매칭색", V_MCOLOR, cur_m)
    # delete all 매칭대기 / 제거대기
    da_q = delete_all("매칭대기", L_QUEUE)
    da_r = delete_all("제거대기", L_REMOVE)
    # i=1 ; repeat 96: replace 매칭표시(i)=0 ; i+=1
    set_i1m = set_num("i", V_I, 1)
    iv_m1 = vrep("i", V_I)
    rep_vis0 = replace_at("매칭표시", L_VISITED, iv_m1, 0)
    inc_im = change_num("i", V_I, 1)
    chain([(rep_vis0, bs[rep_vis0]), (inc_im, bs[inc_im])])
    rep96m = gen(); bs[rep96m] = mk("control_repeat",
        inputs={"TIMES": num(96), "SUBSTACK": [2, rep_vis0]})
    bs[rep_vis0]["parent"] = rep96m

    # add 스냅idx to 매칭대기 ; replace 매칭표시(스냅idx)=1
    snapi_a = vrep("스냅idx", V_SNAPI)
    add_seed = add_to("매칭대기", L_QUEUE, snapi_a)
    snapi_v2 = vrep("스냅idx", V_SNAPI)
    rep_seed_vis = replace_at("매칭표시", L_VISITED, snapi_v2, 1)

    # --- repeat until length(매칭대기)=0 ---
    # 현idx = item(length(매칭대기)) of 매칭대기 ; delete (length) of 매칭대기
    len_q1 = length_of("매칭대기", L_QUEUE)
    pop_item = item_of("매칭대기", L_QUEUE, len_q1)
    set_curidx = set_expr("현idx", V_CURIDX, pop_item)
    len_q2 = length_of("매칭대기", L_QUEUE)
    del_pop = delete_at("매칭대기", L_QUEUE, len_q2)

    # if item(현idx) of 보드 = 매칭색: { add 현idx 제거대기 ; 현col ; 현row ; 4-이웃 push }
    curidx_b = vrep("현idx", V_CURIDX)
    brd_cur = item_of("보드", L_BOARD, curidx_b)
    mcolor_b = vrep("매칭색", V_MCOLOR)
    c_samecolor = cmp_op("operator_equals", brd_cur, mcolor_b)

    curidx_add = vrep("현idx", V_CURIDX)
    add_remove = add_to("제거대기", L_REMOVE, curidx_add)
    # 현col = (현idx-1) mod 8
    curcol_expr = col_from_idx("현idx", V_CURIDX)
    set_curcol = set_expr("현col", V_CURCOL, curcol_expr)
    # 현row = floor((현idx-1)/8)
    currow_expr = row_from_idx("현idx", V_CURIDX)
    set_currow = set_expr("현row", V_CURROW, currow_expr)

    # 4-이웃 helper: gen if-block. guard_cmp 는 (현col/현row 비교), nbr_offset 는 ±1/±8
    def neighbor_block(guard_cond_id, offset):
        # 이웃idx = 현idx + offset
        cur_n = vrep("현idx", V_CURIDX)
        nbr_add = op("operator_add", cur_n, offset)
        set_nbr = set_expr("이웃idx", V_NBRIDX, nbr_add)
        # if item(이웃idx) of 매칭표시 = 0: replace 매칭표시(이웃idx)=1 ; add 이웃idx 매칭대기
        nbr_v1 = vrep("이웃idx", V_NBRIDX)
        vis_item = item_of("매칭표시", L_VISITED, nbr_v1)
        c_unvisited = cmp_op("operator_equals", vis_item, 0)
        nbr_v2 = vrep("이웃idx", V_NBRIDX)
        rep_mark = replace_at("매칭표시", L_VISITED, nbr_v2, 1)
        nbr_v3 = vrep("이웃idx", V_NBRIDX)
        add_q = add_to("매칭대기", L_QUEUE, nbr_v3)
        chain([(rep_mark, bs[rep_mark]), (add_q, bs[add_q])])
        if_unv = gen(); bs[if_unv] = mk("control_if",
            inputs={"CONDITION": [2, c_unvisited], "SUBSTACK": [2, rep_mark]})
        bs[c_unvisited]["parent"] = if_unv; bs[rep_mark]["parent"] = if_unv
        chain([(set_nbr, bs[set_nbr]), (if_unv, bs[if_unv])])
        # outer guard
        if_guard = gen(); bs[if_guard] = mk("control_if",
            inputs={"CONDITION": [2, guard_cond_id], "SUBSTACK": [2, set_nbr]})
        bs[guard_cond_id]["parent"] = if_guard; bs[set_nbr]["parent"] = if_guard
        return if_guard

    # 오른쪽: 현col < 7
    col_r = vrep("현col", V_CURCOL); g_right = cmp_op("operator_lt", col_r, 7)
    nb_right = neighbor_block(g_right, 1)
    # 왼쪽: 현col > 0
    col_l = vrep("현col", V_CURCOL); g_left = cmp_op("operator_gt", col_l, 0)
    nb_left = neighbor_block(g_left, -1)
    # 위: 현row > 0
    row_u = vrep("현row", V_CURROW); g_up = cmp_op("operator_gt", row_u, 0)
    nb_up = neighbor_block(g_up, -8)
    # 아래: 현row < 11
    row_d = vrep("현row", V_CURROW); g_down = cmp_op("operator_lt", row_d, 11)
    nb_down = neighbor_block(g_down, 8)

    chain([(add_remove, bs[add_remove]), (set_curcol, bs[set_curcol]),
           (set_currow, bs[set_currow]),
           (nb_right, bs[nb_right]), (nb_left, bs[nb_left]),
           (nb_up, bs[nb_up]), (nb_down, bs[nb_down])])
    if_same = gen(); bs[if_same] = mk("control_if",
        inputs={"CONDITION": [2, c_samecolor], "SUBSTACK": [2, add_remove]})
    bs[c_samecolor]["parent"] = if_same; bs[add_remove]["parent"] = if_same

    chain([(set_curidx, bs[set_curidx]), (del_pop, bs[del_pop]), (if_same, bs[if_same])])
    len_q3 = length_of("매칭대기", L_QUEUE)
    c_q_empty = cmp_op("operator_equals", len_q3, 0)
    rep_flood = gen(); bs[rep_flood] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_q_empty], "SUBSTACK": [2, set_curidx]})
    bs[c_q_empty]["parent"] = rep_flood; bs[set_curidx]["parent"] = rep_flood

    # 무리수 = length(제거대기)
    len_rem = length_of("제거대기", L_REMOVE)
    set_groupn = set_expr("무리수", V_GROUPN, len_rem)

    # if 무리수 >= 3: { remove loop ; 점수 += 무리수*10 ; 남은거품 -= 무리수 ;
    #                  if 점수>최고기록: 최고기록=점수 ; play sound ; broadcast 보드그리기 ;
    #                  if 남은거품<=0: 게임상태=3 }
    groupn_c = vrep("무리수", V_GROUPN)
    c_ge3 = cmp_op("operator_gt", groupn_c, 2)  # >=3

    # i=1 ; repeat 무리수: replace 보드(item(i) of 제거대기)=0 ; i+=1
    set_i1r = set_num("i", V_I, 1)
    iv_r = vrep("i", V_I)
    rem_item = item_of("제거대기", L_REMOVE, iv_r)
    rep_clear = replace_at("보드", L_BOARD, rem_item, 0)
    inc_ir = change_num("i", V_I, 1)
    chain([(rep_clear, bs[rep_clear]), (inc_ir, bs[inc_ir])])
    groupn_rep = vrep("무리수", V_GROUPN)
    rep_remove = gen(); bs[rep_remove] = mk("control_repeat",
        inputs={"TIMES": slot(groupn_rep), "SUBSTACK": [2, rep_clear]})
    bs[groupn_rep]["parent"] = rep_remove; bs[rep_clear]["parent"] = rep_remove

    # 점수 += 무리수*10
    groupn_sc = vrep("무리수", V_GROUPN)
    mul10 = op("operator_multiply", groupn_sc, 10)
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": slot(mul10)}, fields={"VARIABLE": ["점수", V_SCORE]})
    bs[mul10]["parent"] = inc_score
    # 남은거품 -= 무리수
    groupn_rm = vrep("무리수", V_GROUPN)
    neg_groupn = op("operator_multiply", groupn_rm, -1)
    dec_remain = gen(); bs[dec_remain] = mk("data_changevariableby",
        inputs={"VALUE": slot(neg_groupn)}, fields={"VARIABLE": ["남은거품", V_REMAIN]})
    bs[neg_groupn]["parent"] = dec_remain
    # if 점수>최고기록: 최고기록=점수
    sc_b = vrep("점수", V_SCORE); be_b = vrep("최고기록", V_BEST)
    c_best = cmp_op("operator_gt", sc_b, be_b)
    sc_b2 = vrep("점수", V_SCORE)
    set_best2 = set_expr("최고기록", V_BEST, sc_b2)
    if_best = gen(); bs[if_best] = mk("control_if",
        inputs={"CONDITION": [2, c_best], "SUBSTACK": [2, set_best2]})
    bs[c_best]["parent"] = if_best; bs[set_best2]["parent"] = if_best
    # play sound pop
    snm_m = gen(); bs[snm_m] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_m = gen(); bs[snd_m] = mk("sound_play", inputs={"SOUND_MENU": [1, snm_m]})
    bs[snm_m]["parent"] = snd_m
    # broadcast 보드그리기
    bc_draw_m = broadcast(bs, "보드그리기", BR_DRAW)
    # if 남은거품 <= 0: 게임상태=3
    remain_c = vrep("남은거품", V_REMAIN)
    c_win = cmp_op("operator_lt", remain_c, 1)  # <=0
    set_state3 = set_num("게임상태", V_STATE, 3)
    if_win = gen(); bs[if_win] = mk("control_if",
        inputs={"CONDITION": [2, c_win], "SUBSTACK": [2, set_state3]})
    bs[c_win]["parent"] = if_win; bs[set_state3]["parent"] = if_win

    chain([(set_i1r, bs[set_i1r]), (rep_remove, bs[rep_remove]),
           (inc_score, bs[inc_score]), (dec_remain, bs[dec_remain]),
           (if_best, bs[if_best]), (snd_m, bs[snd_m]),
           (bc_draw_m, bs[bc_draw_m]), (if_win, bs[if_win])])
    if_clear = gen(); bs[if_clear] = mk("control_if",
        inputs={"CONDITION": [2, c_ge3], "SUBSTACK": [2, set_i1r]})
    bs[c_ge3]["parent"] = if_clear; bs[set_i1r]["parent"] = if_clear

    chain([(def_match, bs[def_match]), (set_mcolor, bs[set_mcolor]),
           (da_q, bs[da_q]), (da_r, bs[da_r]), (set_i1m, bs[set_i1m]),
           (rep96m, bs[rep96m]), (add_seed, bs[add_seed]),
           (rep_seed_vis, bs[rep_seed_vis]), (rep_flood, bs[rep_flood]),
           (set_groupn, bs[set_groupn]), (if_clear, bs[if_clear])])

    # ============================================================
    #  define 다음거품 (warp) — 7.7
    # ============================================================
    def_next, _ = make_proc_def(bs, PC_NEXTB, warp=True)
    # 현재색 = 다음색
    next_v = vrep("다음색", V_NEXT)
    set_cur = set_expr("현재색", V_CUR, next_v)
    # 다음색 = random 1..5
    rnd_n = gen(); bs[rnd_n] = mk("operator_random", inputs={"FROM": num(1), "TO": num(5)})
    set_nextc = set_expr("다음색", V_NEXT, rnd_n)
    # 발사수 += 1
    inc_shots = change_num("발사수", V_SHOTS, 1)
    # switch costume to 현재색
    cur_cos = vrep("현재색", V_CUR)
    sw_cos = gen(); bs[sw_cos] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(cur_cos)})
    bs[cur_cos]["parent"] = sw_cos
    # goto (-105,-150) ; show
    goto_sh = gen(); bs[goto_sh] = mk("motion_gotoxy",
        inputs={"X": num(SHOOTER_X), "Y": num(SHOOTER_Y)})
    pd_up = gen(); bs[pd_up] = mk("motion_pointindirection", inputs={"DIRECTION": num(0)})
    show_n = gen(); bs[show_n] = mk("looks_show")
    # broadcast 다음거품준비
    bc_next_n = broadcast(bs, "다음거품준비", BR_NEXT)
    # if 한줄주기>0 AND 발사수 mod 한줄주기 = 0: call 한줄내림
    push_v = vrep("한줄주기", V_PUSH)
    c_push_on = cmp_op("operator_gt", push_v, 0)
    shots_m = vrep("발사수", V_SHOTS); push_m = vrep("한줄주기", V_PUSH)
    mod_push = op("operator_mod", shots_m, push_m)
    c_mod0 = cmp_op("operator_equals", mod_push, 0)
    and_push = bool_op("operator_and", c_push_on, c_mod0)
    call_push = make_proc_call(bs, PC_PUSH, warp=True)
    if_push = gen(); bs[if_push] = mk("control_if",
        inputs={"CONDITION": [2, and_push], "SUBSTACK": [2, call_push]})
    bs[and_push]["parent"] = if_push; bs[call_push]["parent"] = if_push

    chain([(def_next, bs[def_next]), (set_cur, bs[set_cur]), (set_nextc, bs[set_nextc]),
           (inc_shots, bs[inc_shots]), (sw_cos, bs[sw_cos]), (goto_sh, bs[goto_sh]),
           (pd_up, bs[pd_up]), (show_n, bs[show_n]), (bc_next_n, bs[bc_next_n]),
           (if_push, bs[if_push])])

    # ============================================================
    #  define 한줄내림 (warp) — 7.7 하단 (압박)
    # ============================================================
    def_pushd, _ = make_proc_def(bs, PC_PUSH, warp=True)
    # 현row = 11 ; repeat until 현row < 1: { i=0 ; repeat 8: 보드(현row*8+i+1)=보드((현row-1)*8+i+1) ; i+=1 ; 현row-=1 }
    set_row11 = set_num("현row", V_CURROW, 11)
    set_i0p = set_num("i", V_I, 0)
    # dest idx = 현row*8 + i + 1
    row_d1 = vrep("현row", V_CURROW)
    dmul = op("operator_multiply", row_d1, 8)
    iv_d = vrep("i", V_I)
    dadd1 = op("operator_add", dmul, iv_d)
    dadd2 = op("operator_add", dadd1, 1)
    # src idx = (현row-1)*8 + i + 1
    row_s1 = vrep("현row", V_CURROW)
    ssub = op("operator_subtract", row_s1, 1)
    smul = op("operator_multiply", ssub, 8)
    iv_s = vrep("i", V_I)
    sadd1 = op("operator_add", smul, iv_s)
    sadd2 = op("operator_add", sadd1, 1)
    src_item = item_of("보드", L_BOARD, sadd2)
    rep_copy = replace_at("보드", L_BOARD, dadd2, src_item)
    inc_ip = change_num("i", V_I, 1)
    chain([(rep_copy, bs[rep_copy]), (inc_ip, bs[inc_ip])])
    rep8_copy = gen(); bs[rep8_copy] = mk("control_repeat",
        inputs={"TIMES": num(8), "SUBSTACK": [2, rep_copy]})
    bs[rep_copy]["parent"] = rep8_copy
    dec_row = change_num("현row", V_CURROW, -1)
    chain([(set_i0p, bs[set_i0p]), (rep8_copy, bs[rep8_copy]), (dec_row, bs[dec_row])])
    row_c = vrep("현row", V_CURROW)
    c_row_lt1 = cmp_op("operator_lt", row_c, 1)
    rep_down = gen(); bs[rep_down] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_row_lt1], "SUBSTACK": [2, set_i0p]})
    bs[c_row_lt1]["parent"] = rep_down; bs[set_i0p]["parent"] = rep_down

    # row0 = 새 랜덤 줄: i=0 ; repeat 8: 보드(i+1)=random1..5 ; 남은거품+1 ; i+=1
    set_i0p2 = set_num("i", V_I, 0)
    iv_z = vrep("i", V_I)
    zadd = op("operator_add", iv_z, 1)
    rnd_z = gen(); bs[rnd_z] = mk("operator_random", inputs={"FROM": num(1), "TO": num(5)})
    rep_newrow = replace_at("보드", L_BOARD, zadd, rnd_z)
    inc_remain2 = change_num("남은거품", V_REMAIN, 1)
    inc_iz = change_num("i", V_I, 1)
    chain([(rep_newrow, bs[rep_newrow]), (inc_remain2, bs[inc_remain2]), (inc_iz, bs[inc_iz])])
    rep8_new = gen(); bs[rep8_new] = mk("control_repeat",
        inputs={"TIMES": num(8), "SUBSTACK": [2, rep_newrow]})
    bs[rep_newrow]["parent"] = rep8_new

    # broadcast 보드그리기
    bc_draw_p = broadcast(bs, "보드그리기", BR_DRAW)

    # 바닥선 검사: i=89 ; repeat 8: if item(i) of 보드 != 0: 게임상태=0 ; i+=1
    set_i89 = set_num("i", V_I, 89)
    iv_f = vrep("i", V_I)
    brd_f = item_of("보드", L_BOARD, iv_f)
    c_f_ne0 = cmp_op("operator_not_equals", brd_f, 0)
    set_state0p = set_num("게임상태", V_STATE, 0)
    if_floorp = gen(); bs[if_floorp] = mk("control_if",
        inputs={"CONDITION": [2, c_f_ne0], "SUBSTACK": [2, set_state0p]})
    bs[c_f_ne0]["parent"] = if_floorp; bs[set_state0p]["parent"] = if_floorp
    inc_if = change_num("i", V_I, 1)
    chain([(if_floorp, bs[if_floorp]), (inc_if, bs[inc_if])])
    rep8_floor = gen(); bs[rep8_floor] = mk("control_repeat",
        inputs={"TIMES": num(8), "SUBSTACK": [2, if_floorp]})
    bs[if_floorp]["parent"] = rep8_floor

    chain([(def_pushd, bs[def_pushd]), (set_row11, bs[set_row11]),
           (rep_down, bs[rep_down]), (set_i0p2, bs[set_i0p2]), (rep8_new, bs[rep8_new]),
           (bc_draw_p, bs[bc_draw_p]), (set_i89, bs[set_i89]), (rep8_floor, bs[rep8_floor])])

    # ============================================================
    #  when flag clicked: rotationStyle all around, size 100
    # ============================================================
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(hf, bs[hf]), (rs, bs[rs]), (sz, bs[sz])])

    # ============================================================
    #  when receive 게임시작: 슈터 배치 + 장전 + 조준 forever (7.2)
    # ============================================================
    hg = gen(); bs[hg] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    goto_init = gen(); bs[goto_init] = mk("motion_gotoxy",
        inputs={"X": num(SHOOTER_X), "Y": num(SHOOTER_Y)})
    cur_cos2 = vrep("현재색", V_CUR)
    sw_init = gen(); bs[sw_init] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(cur_cos2)})
    bs[cur_cos2]["parent"] = sw_init
    show_init = gen(); bs[show_init] = mk("looks_show")

    # 조준 forever 본문: if 게임상태=1: { point towards mouse ; 각도=direction ; clamp ; point in dir 각도 } ; wait 0.02
    st_aim = vrep("게임상태", V_STATE)
    c_aim1 = cmp_op("operator_equals", st_aim, 1)
    mp_menu = gen(); bs[mp_menu] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["_mouse_", None]}, shadow=True)
    point_m = gen(); bs[point_m] = mk("motion_pointtowards",
        inputs={"TOWARDS": [1, mp_menu]})
    bs[mp_menu]["parent"] = point_m
    dir_r = gen(); bs[dir_r] = mk("motion_direction")
    set_angle = set_expr("각도", V_ANGLE, dir_r)
    # if 각도 > 80: 각도 = 80
    ang1 = vrep("각도", V_ANGLE)
    c_ang_gt = cmp_op("operator_gt", ang1, 80)
    set_ang80 = set_num("각도", V_ANGLE, 80)
    if_ang_gt = gen(); bs[if_ang_gt] = mk("control_if",
        inputs={"CONDITION": [2, c_ang_gt], "SUBSTACK": [2, set_ang80]})
    bs[c_ang_gt]["parent"] = if_ang_gt; bs[set_ang80]["parent"] = if_ang_gt
    # if 각도 < -80: 각도 = -80
    ang2 = vrep("각도", V_ANGLE)
    c_ang_lt = cmp_op("operator_lt", ang2, -80)
    set_angm80 = set_num("각도", V_ANGLE, -80)
    if_ang_lt = gen(); bs[if_ang_lt] = mk("control_if",
        inputs={"CONDITION": [2, c_ang_lt], "SUBSTACK": [2, set_angm80]})
    bs[c_ang_lt]["parent"] = if_ang_lt; bs[set_angm80]["parent"] = if_ang_lt
    # point in direction 각도
    ang3 = vrep("각도", V_ANGLE)
    pid = gen(); bs[pid] = mk("motion_pointindirection", inputs={"DIRECTION": slot(ang3)})
    bs[ang3]["parent"] = pid
    chain([(point_m, bs[point_m]), (set_angle, bs[set_angle]),
           (if_ang_gt, bs[if_ang_gt]), (if_ang_lt, bs[if_ang_lt]), (pid, bs[pid])])
    if_aim = gen(); bs[if_aim] = mk("control_if",
        inputs={"CONDITION": [2, c_aim1], "SUBSTACK": [2, point_m]})
    bs[c_aim1]["parent"] = if_aim; bs[point_m]["parent"] = if_aim
    wait_aim = gen(); bs[wait_aim] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(if_aim, bs[if_aim]), (wait_aim, bs[wait_aim])])
    cond_aim_over = state_over_cond()
    rep_aim = gen(); bs[rep_aim] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_aim_over], "SUBSTACK": [2, if_aim]})
    bs[cond_aim_over]["parent"] = rep_aim; bs[if_aim]["parent"] = rep_aim
    chain([(hg, bs[hg]), (goto_init, bs[goto_init]), (sw_init, bs[sw_init]),
           (show_init, bs[show_init]), (rep_aim, bs[rep_aim])])

    # ============================================================
    #  when receive 게임시작: 발사 forever (7.3 상단)
    # ============================================================
    hf2 = gen(); bs[hf2] = mk("event_whenbroadcastreceived", top=True, x=320, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # if (게임상태=1) AND (mouse down OR space):
    st_fire = vrep("게임상태", V_STATE)
    c_fire1 = cmp_op("operator_equals", st_fire, 1)
    md = gen(); bs[md] = mk("sensing_mousedown")
    sp_menu = gen(); bs[sp_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sp_press = gen(); bs[sp_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, sp_menu]})
    bs[sp_menu]["parent"] = sp_press
    or_input = bool_op("operator_or", md, sp_press)
    and_fire = bool_op("operator_and", c_fire1, or_input)
    # body: 게임상태=2 ; 비행X=-105 ; 비행Y=-150 ; 속도X=sin(각도)*12 ; 속도Y=cos(각도)*12 ;
    #       switch costume 현재색 ; show ; goto(비행X,비행Y) ; call 비행루프
    set_state2 = set_num("게임상태", V_STATE, 2)
    set_flyx = set_num("비행X", V_FLYX, SHOOTER_X)
    set_flyy = set_num("비행Y", V_FLYY, SHOOTER_Y)
    ang_s = vrep("각도", V_ANGLE)
    sin_a = mathop("sin", ang_s)
    mul_vx = op("operator_multiply", sin_a, SPEED)
    set_vx = set_expr("속도X", V_VX, mul_vx)
    ang_c = vrep("각도", V_ANGLE)
    cos_a = mathop("cos", ang_c)
    mul_vy = op("operator_multiply", cos_a, SPEED)
    set_vy = set_expr("속도Y", V_VY, mul_vy)
    cur_f = vrep("현재색", V_CUR)
    sw_f = gen(); bs[sw_f] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(cur_f)})
    bs[cur_f]["parent"] = sw_f
    show_f = gen(); bs[show_f] = mk("looks_show")
    fxg2 = vrep("비행X", V_FLYX); fyg2 = vrep("비행Y", V_FLYY)
    goto_f = gen(); bs[goto_f] = mk("motion_gotoxy",
        inputs={"X": slot(fxg2), "Y": slot(fyg2)})
    bs[fxg2]["parent"] = goto_f; bs[fyg2]["parent"] = goto_f
    call_fly = make_proc_call(bs, PC_FLY, warp=False)
    # 비행 끝나면: if 게임상태≠0 AND ≠3: call 다음거품 ; 게임상태=1
    st_after1 = vrep("게임상태", V_STATE); c_not0 = cmp_op("operator_not_equals", st_after1, 0)
    st_after2 = vrep("게임상태", V_STATE); c_not3 = cmp_op("operator_not_equals", st_after2, 3)
    and_alive = bool_op("operator_and", c_not0, c_not3)
    call_nextb = make_proc_call(bs, PC_NEXTB, warp=True)
    set_state1 = set_num("게임상태", V_STATE, 1)
    chain([(call_nextb, bs[call_nextb]), (set_state1, bs[set_state1])])
    if_alive = gen(); bs[if_alive] = mk("control_if",
        inputs={"CONDITION": [2, and_alive], "SUBSTACK": [2, call_nextb]})
    bs[and_alive]["parent"] = if_alive; bs[call_nextb]["parent"] = if_alive

    chain([(set_state2, bs[set_state2]), (set_flyx, bs[set_flyx]), (set_flyy, bs[set_flyy]),
           (set_vx, bs[set_vx]), (set_vy, bs[set_vy]), (sw_f, bs[sw_f]),
           (show_f, bs[show_f]), (goto_f, bs[goto_f]), (call_fly, bs[call_fly]),
           (if_alive, bs[if_alive])])
    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, and_fire], "SUBSTACK": [2, set_state2]})
    bs[and_fire]["parent"] = if_fire; bs[set_state2]["parent"] = if_fire
    wait_fire = gen(); bs[wait_fire] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(if_fire, bs[if_fire]), (wait_fire, bs[wait_fire])])
    cond_fire_over = state_over_cond()
    rep_fire = gen(); bs[rep_fire] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_fire_over], "SUBSTACK": [2, if_fire]})
    bs[cond_fire_over]["parent"] = rep_fire; bs[if_fire]["parent"] = rep_fire
    chain([(hf2, bs[hf2]), (rep_fire, bs[rep_fire])])

    return bs

# ============================================================
#  격자셀 (붙은 거품 클론 ≤96) — 7.8 상단
# ============================================================
def build_cell_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    add_to, delete_all, delete_at, item_of, length_of, replace_at = make_list_helpers(bs)

    # when flag clicked: hide
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(hf, bs[hf]), (hi, bs[hi])])

    # when receive 보드그리기: broadcast 격자지우기 ; wait 0 ; 그릴idx=1 ;
    #   repeat 96: 그릴색=item(그릴idx) of 보드 ; if 그릴색!=0: create clone ; 그릴idx+=1
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["보드그리기", BR_DRAW]})
    bc_clear = broadcast(bs, "격자지우기", BR_CLEAR)
    wt0 = gen(); bs[wt0] = mk("control_wait", inputs={"DURATION": num(0)})
    set_di1 = gen(); bs[set_di1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["그릴idx", V_DRAWIDX]})

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
    rep96 = gen(); bs[rep96] = mk("control_repeat",
        inputs={"TIMES": num(96), "SUBSTACK": [2, set_dc]})
    bs[set_dc]["parent"] = rep96
    chain([(hd, bs[hd]), (bc_clear, bs[bc_clear]), (wt0, bs[wt0]),
           (set_di1, bs[set_di1]), (rep96, bs[rep96])])

    # when I start as clone: switch costume 그릴색 ; goto(...) ; show
    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=300, y=20)
    dc_c = vrep("그릴색", V_DRAWCOL)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(dc_c)})
    bs[dc_c]["parent"] = sw
    # x = -210 + ((그릴idx-1) mod 8)*30
    di_x = vrep("그릴idx", V_DRAWIDX)
    sub1x = op("operator_subtract", di_x, 1)
    modx = op("operator_mod", sub1x, 8)
    mulx = op("operator_multiply", modx, CELL)
    addx = op("operator_add", COL0_X, mulx)
    # y = 165 - floor((그릴idx-1)/8)*30
    di_y = vrep("그릴idx", V_DRAWIDX)
    sub1y = op("operator_subtract", di_y, 1)
    divy = op("operator_divide", sub1y, 8)
    floory = gen(); bs[floory] = mk("operator_mathop",
        inputs={"NUM": slot(divy)}, fields={"OPERATOR": ["floor", None]})
    bs[divy]["parent"] = floory
    muly = op("operator_multiply", floory, CELL)
    suby = op("operator_subtract", ROW0_Y, muly)
    goto_c = gen(); bs[goto_c] = mk("motion_gotoxy",
        inputs={"X": slot(addx), "Y": slot(suby)})
    bs[addx]["parent"] = goto_c; bs[suby]["parent"] = goto_c
    show_c = gen(); bs[show_c] = mk("looks_show")
    chain([(sc, bs[sc]), (sw, bs[sw]), (goto_c, bs[goto_c]), (show_c, bs[show_c])])

    # when receive 격자지우기 (클론): delete this clone
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=300, y=200,
        fields={"BROADCAST_OPTION": ["격자지우기", BR_CLEAR]})
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    chain([(hc, bs[hc]), (del_c, bs[del_c])])

    return bs

# ============================================================
#  NEXT 미리보기 — 7.8 하단
# ============================================================
def build_next_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    # when flag clicked: goto NEXT box (svg 360,190 -> scratch 120, -10) ; show
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(120), "Y": num(-10)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    show = gen(); bs[show] = mk("looks_show")
    chain([(hf, bs[hf]), (g, bs[g]), (sz, bs[sz]), (show, bs[show])])

    # when receive 다음거품준비: switch costume to 다음색
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=300, y=20,
        fields={"BROADCAST_OPTION": ["다음거품준비", BR_NEXT]})
    next_v = vrep("다음색", V_NEXT)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(next_v)})
    bs[next_v]["parent"] = sw
    chain([(hd, bs[hd]), (sw, bs[sw])])
    return bs

# ============================================================
#  배너 (게임오버 / 승리) — 7.9
# ============================================================
def build_banner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # when flag clicked: hide ; goto 0,0 ; go to front
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(hf, bs[hf]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    # when receive 게임시작: wait until 게임상태=0 OR =3 ; if =0 costume gameover ; if =3 costume win ; show
    hg = gen(); bs[hg] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    st1 = vrep("게임상태", V_STATE); c0 = cmp_op("operator_equals", st1, 0)
    st2 = vrep("게임상태", V_STATE); c3 = cmp_op("operator_equals", st2, 3)
    or_end = bool_op("operator_or", c0, c3)
    wait_end = gen(); bs[wait_end] = mk("control_wait_until", inputs={"CONDITION": [2, or_end]})
    bs[or_end]["parent"] = wait_end
    # if 게임상태=0: costume gameover
    st3 = vrep("게임상태", V_STATE); c0b = cmp_op("operator_equals", st3, 0)
    cm_go = gen(); bs[cm_go] = mk("looks_costume",
        fields={"COSTUME": ["gameover", None]}, shadow=True)
    sw_go = gen(); bs[sw_go] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm_go]})
    bs[cm_go]["parent"] = sw_go
    if_go = gen(); bs[if_go] = mk("control_if",
        inputs={"CONDITION": [2, c0b], "SUBSTACK": [2, sw_go]})
    bs[c0b]["parent"] = if_go; bs[sw_go]["parent"] = if_go
    # if 게임상태=3: costume win
    st4 = vrep("게임상태", V_STATE); c3b = cmp_op("operator_equals", st4, 3)
    cm_win = gen(); bs[cm_win] = mk("looks_costume",
        fields={"COSTUME": ["win", None]}, shadow=True)
    sw_win = gen(); bs[sw_win] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm_win]})
    bs[cm_win]["parent"] = sw_win
    if_win = gen(); bs[if_win] = mk("control_if",
        inputs={"CONDITION": [2, c3b], "SUBSTACK": [2, sw_win]})
    bs[c3b]["parent"] = if_win; bs[sw_win]["parent"] = if_win
    show = gen(); bs[show] = mk("looks_show")
    chain([(hg, bs[hg]), (wait_end, bs[wait_end]), (if_go, bs[if_go]),
           (if_win, bs[if_win]), (show, bs[show])])
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
    bubble_md5 = [write_svg(s) for s in BUBBLE_SVGS]
    go_md5 = write_svg(GAME_OVER_SVG)
    win_md5 = write_svg(WIN_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks   = build_stage_blocks()
    shooter_blocks = build_shooter_blocks()
    cell_blocks    = build_cell_blocks()
    next_blocks    = build_next_blocks()
    banner_blocks  = build_banner_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }
    bubble_costumes = lambda: [{
        "name": str(i + 1), "bitmapResolution": 1, "dataFormat": "svg",
        "assetId": bubble_md5[i], "md5ext": f"{bubble_md5[i]}.svg",
        "rotationCenterX": 14, "rotationCenterY": 14
    } for i in range(5)]

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:  ["점수", 0],
            V_BEST:   ["최고기록", 0],
            V_STATE:  ["게임상태", 1],
            V_REMAIN: ["남은거품", 40],
            V_CUR:    ["현재색", 1],
            V_NEXT:   ["다음색", 1],
            V_SHOTS:  ["발사수", 0],
            V_PUSH:   ["한줄주기", 5],
        },
        "lists": {
            L_BOARD:   ["보드", [0] * 96],
            L_QUEUE:   ["매칭대기", []],
            L_VISITED: ["매칭표시", [0] * 96],
            L_REMOVE:  ["제거대기", []],
        },
        "broadcasts": {
            BR_START: "게임시작",
            BR_DRAW:  "보드그리기",
            BR_CLEAR: "격자지우기",
            BR_NEXT:  "다음거품준비",
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

    shooter = {
        "isStage": False, "name": "슈터",
        "variables": {
            V_FLYX:   ["비행X", 0],
            V_FLYY:   ["비행Y", 0],
            V_VX:     ["속도X", 0],
            V_VY:     ["속도Y", 0],
            V_SNAPC:  ["스냅col", 0],
            V_SNAPR:  ["스냅row", 0],
            V_SNAPI:  ["스냅idx", 0],
            V_BESTD:  ["최소거리", 0],
            V_MCOLOR: ["매칭색", 0],
            V_GROUPN: ["무리수", 0],
            V_CURIDX: ["현idx", 0],
            V_CURCOL: ["현col", 0],
            V_CURROW: ["현row", 0],
            V_NBRIDX: ["이웃idx", 0],
            V_I:      ["i", 0],
            V_ANGLE:  ["각도", 0],
            V_CELLX:  ["셀X", 0],
            V_CELLY:  ["셀Y", 0],
            V_DIST:   ["거리", 0],
            V_HITF:   ["히트플래그", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": shooter_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": bubble_costumes(),
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": SHOOTER_X, "y": SHOOTER_Y, "size": 100, "direction": 0,
        "draggable": False, "rotationStyle": "all around"
    }

    cell = {
        "isStage": False, "name": "격자셀",
        "variables": {
            V_DRAWIDX: ["그릴idx", 0],
            V_DRAWCOL: ["그릴색", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": cell_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": bubble_costumes(),
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    nextprev = {
        "isStage": False, "name": "NEXT미리보기",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": next_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": bubble_costumes(),
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": 120, "y": -10, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    banner = {
        "isStage": False, "name": "배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": banner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "gameover", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": go_md5, "md5ext": f"{go_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 85},
            {"name": "win", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": win_md5, "md5ext": f"{win_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 85},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 300, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100000, "isDiscrete": True},
        {"id": V_REMAIN, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "남은거품"}, "spriteName": None,
         "value": 40, "width": 0, "height": 0, "x": 300, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 200, "isDiscrete": True},
        {"id": V_SHOTS, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "발사수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 300, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 1000, "isDiscrete": True},
        {"id": V_BEST, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "최고기록"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 300, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 100000, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, shooter, cell, nextprev, banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "bubble-shooter-builder"}
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
    _check_integrity(proj)

    print(f"wrote {OUTPUT}")
    print(f"  Stage:        {len(stage_blocks)} blocks")
    print(f"  슈터:         {len(shooter_blocks)} blocks")
    print(f"  격자셀:       {len(cell_blocks)} blocks")
    print(f"  NEXT미리보기: {len(next_blocks)} blocks")
    print(f"  배너:         {len(banner_blocks)} blocks")
    total = (len(stage_blocks) + len(shooter_blocks) + len(cell_blocks)
             + len(next_blocks) + len(banner_blocks))
    print(f"  TOTAL:        {total} blocks")
    print(f"  targets:      {len(proj['targets'])}")


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
                def scan(el):
                    if isinstance(el, str) and el.startswith("b") and el not in ids:
                        errs.append(f"{name}:{bid} input {k} -> {el} 없음")
                    elif isinstance(el, list):
                        for sub in el: scan(sub)
                for el in inp[1:]:
                    scan(el)
    if errs:
        raise AssertionError("블록 참조 무결성 오류:\n" + "\n".join(errs[:40]))
    print("  integrity:    OK (모든 next/parent/input 참조 유효)")


if __name__ == "__main__":
    main()
