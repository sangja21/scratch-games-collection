#!/usr/bin/env python3
"""스네이크 (snake) — 방향키로 격자 위 뱀을 조종해 사과를 먹는다.

베이스: games/car-race/build.py (격자 스냅 이동 + 키 입력 + 클론 풀 + 게임상태 broadcast)
      + games/flappy-bird/build.py (이벤트 기반 점수 +1, 게임오버 배너).

리스트 블록(data_insertatindex/data_itemoflist/data_deleteoflist/
data_lengthoflist/data_deletealloflist)을 쓰는 첫 게임. 꼬리는 머리가 지나온
좌표를 궤적X/궤적Y 리스트에 기록하고, 각 꼬리 세그먼트 클론이 자기 순번만큼
지연된 과거 좌표를 읽어 머리를 따라간다.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "스네이크.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: 갈색 벽 테두리 + 28x20 녹색 체크무늬 보드 (16px 타일) --------
# 보드 내부 무대좌표 x -224..224 / y -160..160.
# 무대 픽셀좌표(좌상단 0,0): 보드 x = 240+gx, y = 180-gy.
#   x -224 -> 16,  x +224 -> 464  (가로 448px, 28칸)
#   y +160 -> 20,  y -160 -> 340  (세로 320px, 20칸)
def _board_tiles():
    cells = []
    for r in range(20):          # rowIndex 0..19 (위->아래로 그림)
        for c in range(28):      # colIndex 0..27
            px = 16 + c * 16
            py = 20 + r * 16
            light = (c + r) % 2 == 0
            fill = "#43A047" if light else "#388E3C"
            cells.append(
                f'    <rect x="{px}" y="{py}" width="16" height="16" fill="{fill}"/>')
    return "\n".join(cells)

BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <!-- 갈색 벽 (전체 배경) -->
  <rect x="0" y="0" width="480" height="360" fill="#6D4C41"/>
  <rect x="4" y="4" width="472" height="352" fill="#8D6E63"/>
  <rect x="10" y="10" width="460" height="340" fill="#5D4037"/>
  <!-- 보드 체크무늬 (28x20, 16px 타일) -->
  <g>
__TILES__
  </g>
  <!-- 보드 안쪽 테두리 음영 -->
  <rect x="16" y="20" width="448" height="320" fill="none" stroke="#2E7D32" stroke-width="2"/>
</svg>""".replace("__TILES__", _board_tiles())

# -------- Snake head: 둥근 진녹색 사각 + 눈 2개 + 빨간 혀 (16x16) --------
HEAD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <rect x="0.5" y="0.5" width="15" height="15" rx="4" fill="#1B5E20" stroke="#0B3D0B" stroke-width="1"/>
  <!-- eyes -->
  <circle cx="5" cy="5.5" r="2.2" fill="#FFFFFF"/>
  <circle cx="11" cy="5.5" r="2.2" fill="#FFFFFF"/>
  <circle cx="5.4" cy="5.5" r="1.0" fill="#111111"/>
  <circle cx="11.4" cy="5.5" r="1.0" fill="#111111"/>
  <!-- tongue -->
  <rect x="7" y="11.5" width="2" height="4" rx="1" fill="#E53935"/>
  <rect x="6" y="14" width="4" height="1.6" rx="0.8" fill="#E53935"/>
</svg>"""

# -------- Snake tail segment: 둥근 옅은 녹색 사각 (16x16) --------
TAIL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <rect x="1" y="1" width="14" height="14" rx="4" fill="#43A047" stroke="#1B5E20" stroke-width="1.2"/>
  <rect x="4.5" y="4.5" width="7" height="7" rx="2" fill="#66BB6A"/>
</svg>"""

# -------- Apple: 빨간 원 + 갈색 꼭지 + 초록 잎 (16x16) --------
APPLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <circle cx="8" cy="9.5" r="6" fill="#E53935" stroke="#B71C1C" stroke-width="1"/>
  <ellipse cx="6" cy="7.5" rx="2" ry="1.4" fill="#FF8A80" opacity="0.8"/>
  <rect x="7.4" y="1.5" width="1.4" height="4" rx="0.7" fill="#6D4C41"/>
  <path d="M9 3 Q13 1 12.5 4.5 Q9.5 5 9 3 Z" fill="#2E7D32"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#43A047" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#66BB6A" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">꼬리/벽에 부딪혔어요</text>
  <text x="180" y="132" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="14">좌상단의 점수/최고기록 확인</text>
  <text x="180" y="156" text-anchor="middle"
        fill="#81D4FA" font-family="Arial, Helvetica, sans-serif"
        font-size="13">초록 깃발(▶) 다시 클릭으로 재시작</text>
</svg>"""

# ============================================================
#  helpers
# ============================================================
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

# ---- list block helpers (snake 가 처음 도입) ----
# data_addtolist        : inputs ITEM ; fields LIST [name, id]
# data_insertatindex    : inputs ITEM, INDEX ; fields LIST
# data_deleteoflist     : inputs INDEX ; fields LIST
# data_deletealloflist  : fields LIST
# data_itemoflist       : inputs INDEX ; fields LIST  (reporter)
# data_lengthoflist     : fields LIST                 (reporter)
def make_list_helpers(bs):
    def listref(name, lid):
        """reporter: data_listcontents (the list itself)."""
        bid = gen()
        bs[bid] = mk("data_listcontents", fields={"LIST": [name, lid]})
        return bid

    def add_to(name, lid, item):
        """item: 숫자/문자 -> text_lit, 또는 reporter block id -> slot."""
        bid = gen()
        ins = {"ITEM": slot(item) if isinstance(item, str) else text_lit(item)}
        bs[bid] = mk("data_addtolist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(item, str): bs[item]["parent"] = bid
        return bid

    def insert_at(name, lid, item, index):
        bid = gen()
        ins = {
            "ITEM":  slot(item) if isinstance(item, str) else text_lit(item),
            "INDEX": slot(index) if isinstance(index, str) else text_lit(index),
        }
        bs[bid] = mk("data_insertatindex", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(item, str):  bs[item]["parent"] = bid
        if isinstance(index, str): bs[index]["parent"] = bid
        return bid

    def delete_of(name, lid, index):
        bid = gen()
        ins = {"INDEX": slot(index) if isinstance(index, str) else text_lit(index)}
        bs[bid] = mk("data_deleteoflist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(index, str): bs[index]["parent"] = bid
        return bid

    def delete_all(name, lid):
        bid = gen()
        bs[bid] = mk("data_deletealloflist", fields={"LIST": [name, lid]})
        return bid

    def item_of(name, lid, index):
        """reporter."""
        bid = gen()
        ins = {"INDEX": slot(index) if isinstance(index, str) else text_lit(index)}
        bs[bid] = mk("data_itemoflist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(index, str): bs[index]["parent"] = bid
        return bid

    def length_of(name, lid):
        """reporter."""
        bid = gen()
        bs[bid] = mk("data_lengthoflist", fields={"LIST": [name, lid]})
        return bid

    return (listref, add_to, insert_at, delete_of, delete_all, item_of, length_of)

# ============================================================
#  IDs
# ============================================================
V_SCORE   = "varScore01"
V_BEST    = "varBest02"
V_STATE   = "varState03"
V_LEN     = "varLen04"
V_DIR     = "varDir05"
V_NEXTDIR = "varNextDir06"
V_STEP    = "varStep07"
V_APPLEX  = "varAppleX08"
V_APPLEY  = "varAppleY09"
V_HEADX   = "varHeadX10"
V_HEADY   = "varHeadY11"
V_GAP     = "varGap12"
V_SEG     = "varSeg13"        # 꼬리 sprite-local (세그번호)
V_SEGISS  = "varSegIssue14"   # 글로벌 임시 (세그발급)

L_TRAILX  = "L_trailX01"
L_TRAILY  = "L_trailY02"

BR_START  = "brStart01"
BR_STEP   = "brStep02"
BR_APPLE  = "brPlaceApple03"
BR_TAIL   = "brTail04"   # 머리가 궤적 insert 완료 후 발신 -> 꼬리가 갱신된 궤적을 읽음 (수신순서 보장)

# 보드 경계 (칸 중심 좌표)
BX = 224   # |머리X| > 224 이면 벽
BY = 160   # |머리Y| > 160 이면 벽
HEAD_START_X = -24
HEAD_START_Y = -8

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init vars + broadcast 게임시작 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = [
        ("점수", V_SCORE, 0),
        ("게임상태", V_STATE, 1),
        ("길이", V_LEN, 3),
        ("방향", V_DIR, 1),
        ("다음방향", V_NEXTDIR, 1),
        ("스텝간격", V_STEP, 0.18),
        ("기록간격", V_GAP, 1),
        ("머리X", V_HEADX, HEAD_START_X),
        ("머리Y", V_HEADY, HEAD_START_Y),
        ("세그발급", V_SEGISS, 0),
    ]
    seq = [(h, bs[h])]
    for name, vid, val in inits:
        sid = gen()
        bs[sid] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
        seq.append((sid, bs[sid]))

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start
    seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # === when receive 게임시작 (스텝 발생기) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_a = vrep("게임상태", V_STATE)
    cond_over_a = cmp_op("operator_equals", state_a, 0)

    bm_step = gen(); bs[bm_step] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["스텝", BR_STEP]}, shadow=True)
    bc_step = gen(); bs[bc_step] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_step]})
    bs[bm_step]["parent"] = bc_step

    step_v = vrep("스텝간격", V_STEP)
    wt_step = gen(); bs[wt_step] = mk("control_wait",
        inputs={"DURATION": slot(step_v)})
    bs[step_v]["parent"] = wt_step

    chain([(bc_step, bs[bc_step]), (wt_step, bs[wt_step])])

    rep_a = gen(); bs[rep_a] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_a], "SUBSTACK":[2,bc_step]})
    bs[cond_over_a]["parent"] = rep_a
    bs[bc_step]["parent"] = rep_a
    chain([(h2, bs[h2]), (rep_a, bs[rep_a])])

    # === when receive 게임시작 (난이도 ramp) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_b = vrep("게임상태", V_STATE)
    cond_over_b = cmp_op("operator_equals", state_b, 0)

    wt_r = gen(); bs[wt_r] = mk("control_wait", inputs={"DURATION": num(0.05)})

    # if (점수 >= 5) AND (스텝간격 > 0.07):
    score_r = vrep("점수", V_SCORE)
    cond_score = cmp_op("operator_gt", score_r, 4)       # >=5 == >4 (정수 점수)
    step_r1 = vrep("스텝간격", V_STEP)
    cond_step = cmp_op("operator_gt", step_r1, 0.07)
    cond_and_r = bool_op("operator_and", cond_score, cond_step)

    # 스텝간격 = 0.18 - (점수 * 0.008)
    score_r2 = vrep("점수", V_SCORE)
    mul_s = op("operator_multiply", score_r2, 0.008)
    sub_s = gen(); bs[sub_s] = mk("operator_subtract",
        inputs={"NUM1": num(0.18), "NUM2": slot(mul_s)})
    bs[mul_s]["parent"] = sub_s
    set_step_new = gen(); bs[set_step_new] = mk("data_setvariableto",
        inputs={"VALUE": slot(sub_s)}, fields={"VARIABLE": ["스텝간격", V_STEP]})
    bs[sub_s]["parent"] = set_step_new

    # if 스텝간격 < 0.07: 스텝간격 = 0.07
    step_r2 = vrep("스텝간격", V_STEP)
    cond_clamp = cmp_op("operator_lt", step_r2, 0.07)
    set_step_clamp = gen(); bs[set_step_clamp] = mk("data_setvariableto",
        inputs={"VALUE": num(0.07)}, fields={"VARIABLE": ["스텝간격", V_STEP]})
    if_clamp = gen(); bs[if_clamp] = mk("control_if",
        inputs={"CONDITION":[2,cond_clamp], "SUBSTACK":[2,set_step_clamp]})
    bs[cond_clamp]["parent"] = if_clamp
    bs[set_step_clamp]["parent"] = if_clamp

    chain([(set_step_new, bs[set_step_new]), (if_clamp, bs[if_clamp])])

    if_ramp = gen(); bs[if_ramp] = mk("control_if",
        inputs={"CONDITION":[2,cond_and_r], "SUBSTACK":[2,set_step_new]})
    bs[cond_and_r]["parent"] = if_ramp
    bs[set_step_new]["parent"] = if_ramp

    chain([(wt_r, bs[wt_r]), (if_ramp, bs[if_ramp])])

    rep_b = gen(); bs[rep_b] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_b], "SUBSTACK":[2,wt_r]})
    bs[cond_over_b]["parent"] = rep_b
    bs[wt_r]["parent"] = rep_b
    chain([(h3, bs[h3]), (rep_b, bs[rep_b])])

    return bs

# ============================================================
#  HEAD blocks
# ============================================================
def build_head_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    (listref, add_to, insert_at, delete_of, delete_all,
     item_of, length_of) = make_list_helpers(bs)

    # === when flag clicked: size/dir/show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(sz,bs[sz]),(pd,bs[pd]),(sh,bs[sh])])

    # === when receive 게임시작: goto + show + 첫 사과 + 입력 forever ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    hx_v = vrep("머리X", V_HEADX)
    hy_v = vrep("머리Y", V_HEADY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(hx_v), "Y": slot(hy_v)})
    bs[hx_v]["parent"] = g; bs[hy_v]["parent"] = g
    show2 = gen(); bs[show2] = mk("looks_show")

    bm_ap = gen(); bs[bm_ap] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["사과배치", BR_APPLE]}, shadow=True)
    bc_ap = gen(); bs[bc_ap] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ap]})
    bs[bm_ap]["parent"] = bc_ap

    # input forever: repeat until 게임상태 = 0
    state_in = vrep("게임상태", V_STATE)
    cond_over_in = cmp_op("operator_equals", state_in, 0)

    def key_if(key_name, dir_val, banned_dir):
        # if (key pressed AND 방향 != banned) → 다음방향 = dir_val
        km = gen(); bs[km] = mk("sensing_keyoptions",
            fields={"KEY_OPTION": [key_name, None]}, shadow=True)
        kp = gen(); bs[kp] = mk("sensing_keypressed",
            inputs={"KEY_OPTION":[1, km]})
        bs[km]["parent"] = kp
        dir_v = vrep("방향", V_DIR)
        ceq = cmp_op("operator_equals", dir_v, banned_dir)
        cnot = gen(); bs[cnot] = mk("operator_not", inputs={"OPERAND":[2,ceq]}); bs[ceq]["parent"] = cnot
        cand = bool_op("operator_and", kp, cnot)
        setnd = gen(); bs[setnd] = mk("data_setvariableto",
            inputs={"VALUE": num(dir_val)}, fields={"VARIABLE": ["다음방향", V_NEXTDIR]})
        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION":[2,cand], "SUBSTACK":[2,setnd]})
        bs[cand]["parent"] = ifb
        bs[setnd]["parent"] = ifb
        return ifb

    if_right = key_if("right arrow", 1, 3)
    if_up    = key_if("up arrow",    2, 4)
    if_left  = key_if("left arrow",  3, 1)
    if_down  = key_if("down arrow",  4, 2)
    wt_in = gen(); bs[wt_in] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(if_right,bs[if_right]),(if_up,bs[if_up]),
           (if_left,bs[if_left]),(if_down,bs[if_down]),(wt_in,bs[wt_in])])

    rep_in = gen(); bs[rep_in] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_in], "SUBSTACK":[2,if_right]})
    bs[cond_over_in]["parent"] = rep_in
    bs[if_right]["parent"] = rep_in

    chain([(h2,bs[h2]),(g,bs[g]),(show2,bs[show2]),(bc_ap,bs[bc_ap]),
           (rep_in,bs[rep_in])])

    # === when receive 스텝: 회전 적용 + 1칸 이동 + 충돌 + 궤적기록 + 사과먹기 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=20,
        fields={"BROADCAST_OPTION": ["스텝", BR_STEP]})

    # 방향 = 다음방향
    nd_v = vrep("다음방향", V_NEXTDIR)
    set_dir = gen(); bs[set_dir] = mk("data_setvariableto",
        inputs={"VALUE": slot(nd_v)}, fields={"VARIABLE": ["방향", V_DIR]})
    bs[nd_v]["parent"] = set_dir

    # 4개 방향 이동 분기 (if 방향 = k → change x/y by ±16)
    def move_if(dir_val, axis, delta):
        dv = vrep("방향", V_DIR)
        cnd = cmp_op("operator_equals", dv, dir_val)
        if axis == "x":
            mvb = gen(); bs[mvb] = mk("motion_changexby", inputs={"DX": num(delta)})
        else:
            mvb = gen(); bs[mvb] = mk("motion_changeyby", inputs={"DY": num(delta)})
        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION":[2,cnd], "SUBSTACK":[2,mvb]})
        bs[cnd]["parent"] = ifb
        bs[mvb]["parent"] = ifb
        return ifb

    mif_r = move_if(1, "x",  16)
    mif_u = move_if(2, "y",  16)
    mif_l = move_if(3, "x", -16)
    mif_d = move_if(4, "y", -16)

    # 머리X = x position ; 머리Y = y position
    xpos = gen(); bs[xpos] = mk("motion_xposition")
    set_hx = gen(); bs[set_hx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xpos)}, fields={"VARIABLE": ["머리X", V_HEADX]})
    bs[xpos]["parent"] = set_hx
    ypos = gen(); bs[ypos] = mk("motion_yposition")
    set_hy = gen(); bs[set_hy] = mk("data_setvariableto",
        inputs={"VALUE": slot(ypos)}, fields={"VARIABLE": ["머리Y", V_HEADY]})
    bs[ypos]["parent"] = set_hy

    # 벽 충돌: if (머리X>224 OR 머리X<-224 OR 머리Y>160 OR 머리Y<-160) → 게임상태=0
    hx1 = vrep("머리X", V_HEADX); c_xgt = cmp_op("operator_gt", hx1,  BX)
    hx2 = vrep("머리X", V_HEADX); c_xlt = cmp_op("operator_lt", hx2, -BX)
    hy1 = vrep("머리Y", V_HEADY); c_ygt = cmp_op("operator_gt", hy1,  BY)
    hy2 = vrep("머리Y", V_HEADY); c_ylt = cmp_op("operator_lt", hy2, -BY)
    or1 = bool_op("operator_or", c_xgt, c_xlt)
    or2 = bool_op("operator_or", c_ygt, c_ylt)
    or_wall = bool_op("operator_or", or1, or2)
    set_state_wall = gen(); bs[set_state_wall] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_wall = gen(); bs[if_wall] = mk("control_if",
        inputs={"CONDITION":[2,or_wall], "SUBSTACK":[2,set_state_wall]})
    bs[or_wall]["parent"] = if_wall
    bs[set_state_wall]["parent"] = if_wall

    # 자기충돌: if touching 꼬리 → 게임상태=0
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["꼬리", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc
    set_state_self = gen(); bs[set_state_self] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_self = gen(); bs[if_self] = mk("control_if",
        inputs={"CONDITION":[2,tc], "SUBSTACK":[2,set_state_self]})
    bs[tc]["parent"] = if_self
    bs[set_state_self]["parent"] = if_self

    # 궤적 기록: insert 머리X at 1 of 궤적X ; insert 머리Y at 1 of 궤적Y
    hx_ins = vrep("머리X", V_HEADX)
    ins_x = insert_at("궤적X", L_TRAILX, hx_ins, 1)
    hy_ins = vrep("머리Y", V_HEADY)
    ins_y = insert_at("궤적Y", L_TRAILY, hy_ins, 1)

    # 버퍼 트림: repeat until (length 궤적X) <= (길이 + 5): delete last 궤적X/Y
    lenx = length_of("궤적X", L_TRAILX)
    len_v = vrep("길이", V_LEN)
    plus5 = op("operator_add", len_v, 5)
    # length <= 길이+5  =>  NOT (length > 길이+5).  cmp_op gt 사용 후 not.
    cmp_gt = cmp_op("operator_gt", lenx, plus5)   # length > 길이+5
    not_trim = gen(); bs[not_trim] = mk("operator_not", inputs={"OPERAND":[2,cmp_gt]})
    bs[cmp_gt]["parent"] = not_trim
    # delete last: index = length of list
    lenx2 = length_of("궤적X", L_TRAILX)
    del_x = delete_of("궤적X", L_TRAILX, lenx2)
    leny2 = length_of("궤적Y", L_TRAILY)
    del_y = delete_of("궤적Y", L_TRAILY, leny2)
    chain([(del_x, bs[del_x]), (del_y, bs[del_y])])
    rep_trim = gen(); bs[rep_trim] = mk("control_repeat_until",
        inputs={"CONDITION":[2,not_trim], "SUBSTACK":[2,del_x]})
    bs[not_trim]["parent"] = rep_trim
    bs[del_x]["parent"] = rep_trim

    # 사과 먹기: if (머리X=사과X AND 머리Y=사과Y) → 점수+1/길이+1/best/사과배치/세그발급+1/clone
    hxe = vrep("머리X", V_HEADX); axe = vrep("사과X", V_APPLEX)
    c_ex = cmp_op("operator_equals", hxe, axe)
    hye = vrep("머리Y", V_HEADY); aye = vrep("사과Y", V_APPLEY)
    c_ey = cmp_op("operator_equals", hye, aye)
    c_eat = bool_op("operator_and", c_ex, c_ey)

    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    inc_len = gen(); bs[inc_len] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["길이", V_LEN]})

    # if 점수 > 최고기록: 최고기록 = 점수
    sc_b = vrep("점수", V_SCORE); be_b = vrep("최고기록", V_BEST)
    c_best = cmp_op("operator_gt", sc_b, be_b)
    sc_b2 = vrep("점수", V_SCORE)
    set_best = gen(); bs[set_best] = mk("data_setvariableto",
        inputs={"VALUE": slot(sc_b2)}, fields={"VARIABLE": ["최고기록", V_BEST]})
    bs[sc_b2]["parent"] = set_best
    if_best = gen(); bs[if_best] = mk("control_if",
        inputs={"CONDITION":[2,c_best], "SUBSTACK":[2,set_best]})
    bs[c_best]["parent"] = if_best
    bs[set_best]["parent"] = if_best

    # broadcast 사과배치
    bm_ap2 = gen(); bs[bm_ap2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["사과배치", BR_APPLE]}, shadow=True)
    bc_ap2 = gen(); bs[bc_ap2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ap2]})
    bs[bm_ap2]["parent"] = bc_ap2

    # 세그발급 += 1 ; create clone of 꼬리
    inc_seg = gen(); bs[inc_seg] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["세그발급", V_SEGISS]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["꼬리", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(inc_score,bs[inc_score]),(inc_len,bs[inc_len]),(if_best,bs[if_best]),
           (bc_ap2,bs[bc_ap2]),(inc_seg,bs[inc_seg]),(cclone,bs[cclone])])
    if_eat = gen(); bs[if_eat] = mk("control_if",
        inputs={"CONDITION":[2,c_eat], "SUBSTACK":[2,inc_score]})
    bs[c_eat]["parent"] = if_eat
    bs[inc_score]["parent"] = if_eat

    # broadcast 꼬리갱신: 궤적 insert/트림이 끝난 뒤 발신 -> 꼬리가 최신 궤적을 읽어 머리를 끊김없이 따라옴
    bm_tail = gen(); bs[bm_tail] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["꼬리갱신", BR_TAIL]}, shadow=True)
    bc_tail = gen(); bs[bc_tail] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_tail]})
    bs[bm_tail]["parent"] = bc_tail

    chain([(h3,bs[h3]),(set_dir,bs[set_dir]),
           (mif_r,bs[mif_r]),(mif_u,bs[mif_u]),(mif_l,bs[mif_l]),(mif_d,bs[mif_d]),
           (set_hx,bs[set_hx]),(set_hy,bs[set_hy]),
           (if_wall,bs[if_wall]),(if_self,bs[if_self]),
           (ins_x,bs[ins_x]),(ins_y,bs[ins_y]),(rep_trim,bs[rep_trim]),
           (if_eat,bs[if_eat]),(bc_tail,bs[bc_tail])])

    # === when flag clicked: 게임오버 효과음 ===
    h4 = gen(); bs[h4] = mk("event_whenflagclicked", top=True, x=620, y=20)
    st_w = vrep("게임상태", V_STATE)
    c_w0 = cmp_op("operator_equals", st_w, 0)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION":[2,c_w0]})
    bs[c_w0]["parent"] = wu
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    chain([(h4,bs[h4]),(wu,bs[wu]),(snd,bs[snd])])

    return bs

# ============================================================
#  TAIL blocks
# ============================================================
def build_tail_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    (listref, add_to, insert_at, delete_of, delete_all,
     item_of, length_of) = make_list_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when receive 게임시작: 시드 채우기 + 세그번호 클론 생성 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    da_x = delete_all("궤적X", L_TRAILX)
    da_y = delete_all("궤적Y", L_TRAILY)

    # 시드: repeat (길이 + 6): insert 머리X at 1 / insert 머리Y at 1
    len_seed = vrep("길이", V_LEN)
    plus6 = op("operator_add", len_seed, 6)
    hx_s = vrep("머리X", V_HEADX)
    seed_ix = insert_at("궤적X", L_TRAILX, hx_s, 1)
    hy_s = vrep("머리Y", V_HEADY)
    seed_iy = insert_at("궤적Y", L_TRAILY, hy_s, 1)
    chain([(seed_ix, bs[seed_ix]), (seed_iy, bs[seed_iy])])
    rep_seed = gen(); bs[rep_seed] = mk("control_repeat",
        inputs={"TIMES": slot(plus6), "SUBSTACK":[2,seed_ix]})
    bs[plus6]["parent"] = rep_seed
    bs[seed_ix]["parent"] = rep_seed

    # 세그발급 = 0
    set_seg0 = gen(); bs[set_seg0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["세그발급", V_SEGISS]})

    # repeat (길이): 세그발급+1 ; create clone of _myself_
    len_cl = vrep("길이", V_LEN)
    inc_seg = gen(); bs[inc_seg] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["세그발급", V_SEGISS]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(inc_seg, bs[inc_seg]), (cclone, bs[cclone])])
    rep_cl = gen(); bs[rep_cl] = mk("control_repeat",
        inputs={"TIMES": slot(len_cl), "SUBSTACK":[2,inc_seg]})
    bs[len_cl]["parent"] = rep_cl
    bs[inc_seg]["parent"] = rep_cl

    chain([(h2,bs[h2]),(hi2,bs[hi2]),(da_x,bs[da_x]),(da_y,bs[da_y]),
           (rep_seed,bs[rep_seed]),(set_seg0,bs[set_seg0]),(rep_cl,bs[rep_cl])])

    # === when I start as clone: 세그번호 채택 + show + goto item(세그번호+1) ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=320, y=180)
    seg_iss = vrep("세그발급", V_SEGISS)
    set_seg = gen(); bs[set_seg] = mk("data_setvariableto",
        inputs={"VALUE": slot(seg_iss)}, fields={"VARIABLE": ["세그번호", V_SEG]})
    bs[seg_iss]["parent"] = set_seg
    show_c = gen(); bs[show_c] = mk("looks_show")

    seg_c1 = vrep("세그번호", V_SEG)
    idx_c1 = op("operator_add", seg_c1, 1)
    itx_c = item_of("궤적X", L_TRAILX, idx_c1)
    seg_c2 = vrep("세그번호", V_SEG)
    idx_c2 = op("operator_add", seg_c2, 1)
    ity_c = item_of("궤적Y", L_TRAILY, idx_c2)
    goto_c = gen(); bs[goto_c] = mk("motion_gotoxy",
        inputs={"X": slot(itx_c), "Y": slot(ity_c)})
    bs[itx_c]["parent"] = goto_c; bs[ity_c]["parent"] = goto_c

    chain([(ch,bs[ch]),(set_seg,bs[set_seg]),(show_c,bs[show_c]),(goto_c,bs[goto_c])])

    # === when receive 꼬리갱신: if 세그번호 <= 길이 → goto item(세그번호+1) ===
    # (머리가 궤적 insert 를 끝낸 뒤 발신하므로 항상 최신 궤적을 읽음 = 머리 뒤에 끊김없이 붙음)
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=620, y=180,
        fields={"BROADCAST_OPTION": ["꼬리갱신", BR_TAIL]})

    seg_le = vrep("세그번호", V_SEG); len_le = vrep("길이", V_LEN)
    # 세그번호 <= 길이  ==  NOT (세그번호 > 길이)
    cmp_seg_gt = cmp_op("operator_gt", seg_le, len_le)
    not_seg = gen(); bs[not_seg] = mk("operator_not", inputs={"OPERAND":[2,cmp_seg_gt]})
    bs[cmp_seg_gt]["parent"] = not_seg

    seg_s1 = vrep("세그번호", V_SEG)
    idx_s1 = op("operator_add", seg_s1, 1)
    itx_s = item_of("궤적X", L_TRAILX, idx_s1)
    seg_s2 = vrep("세그번호", V_SEG)
    idx_s2 = op("operator_add", seg_s2, 1)
    ity_s = item_of("궤적Y", L_TRAILY, idx_s2)
    goto_s = gen(); bs[goto_s] = mk("motion_gotoxy",
        inputs={"X": slot(itx_s), "Y": slot(ity_s)})
    bs[itx_s]["parent"] = goto_s; bs[ity_s]["parent"] = goto_s

    if_step = gen(); bs[if_step] = mk("control_if",
        inputs={"CONDITION":[2,not_seg], "SUBSTACK":[2,goto_s]})
    bs[not_seg]["parent"] = if_step
    bs[goto_s]["parent"] = if_step

    chain([(h3,bs[h3]),(if_step,bs[if_step])])

    return bs

# ============================================================
#  APPLE blocks
# ============================================================
def build_apple_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: size + costume + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    cm_menu = gen(); bs[cm_menu] = mk("looks_costume",
        fields={"COSTUME":["apple", None]}, shadow=True)
    cm = gen(); bs[cm] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, cm_menu]})
    bs[cm_menu]["parent"] = cm
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(sz,bs[sz]),(cm,bs[cm]),(sh,bs[sh])])

    # === when receive 사과배치: show + repeat until (빈 칸) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["사과배치", BR_APPLE]})
    show2 = gen(); bs[show2] = mk("looks_show")

    # 사과X = (random 0..27)*16 - 216
    rc = gen(); bs[rc] = mk("operator_random", inputs={"FROM": num(0), "TO": num(27)})
    mul_c = op("operator_multiply", rc, 16)
    sub_c = gen(); bs[sub_c] = mk("operator_subtract",
        inputs={"NUM1": slot(mul_c), "NUM2": num(216)})
    bs[mul_c]["parent"] = sub_c
    set_ax = gen(); bs[set_ax] = mk("data_setvariableto",
        inputs={"VALUE": slot(sub_c)}, fields={"VARIABLE": ["사과X", V_APPLEX]})
    bs[sub_c]["parent"] = set_ax

    # 사과Y = (random 0..19)*16 - 152
    rr = gen(); bs[rr] = mk("operator_random", inputs={"FROM": num(0), "TO": num(19)})
    mul_r = op("operator_multiply", rr, 16)
    sub_r = gen(); bs[sub_r] = mk("operator_subtract",
        inputs={"NUM1": slot(mul_r), "NUM2": num(152)})
    bs[mul_r]["parent"] = sub_r
    set_ay = gen(); bs[set_ay] = mk("data_setvariableto",
        inputs={"VALUE": slot(sub_r)}, fields={"VARIABLE": ["사과Y", V_APPLEY]})
    bs[sub_r]["parent"] = set_ay

    # goto (사과X, 사과Y)
    ax_v = vrep("사과X", V_APPLEX); ay_v = vrep("사과Y", V_APPLEY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(ax_v), "Y": slot(ay_v)})
    bs[ax_v]["parent"] = g; bs[ay_v]["parent"] = g

    chain([(set_ax,bs[set_ax]),(set_ay,bs[set_ay]),(g,bs[g])])

    # 조건: NOT touching 머리 AND NOT touching 꼬리
    tmh = gen(); bs[tmh] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["머리", None]}, shadow=True)
    tch = gen(); bs[tch] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tmh]})
    bs[tmh]["parent"] = tch
    not_h = gen(); bs[not_h] = mk("operator_not", inputs={"OPERAND":[2,tch]})
    bs[tch]["parent"] = not_h

    tmt = gen(); bs[tmt] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["꼬리", None]}, shadow=True)
    tct = gen(); bs[tct] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tmt]})
    bs[tmt]["parent"] = tct
    not_t = gen(); bs[not_t] = mk("operator_not", inputs={"OPERAND":[2,tct]})
    bs[tct]["parent"] = not_t

    cond_empty = bool_op("operator_and", not_h, not_t)

    rep_place = gen(); bs[rep_place] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_empty], "SUBSTACK":[2,set_ax]})
    bs[cond_empty]["parent"] = rep_place
    bs[set_ax]["parent"] = rep_place

    chain([(h2,bs[h2]),(show2,bs[show2]),(rep_place,bs[rep_place])])

    return bs

# ============================================================
#  GAME OVER banner blocks
# ============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})

    state_v1 = vrep("게임상태", V_STATE)
    cond_one = cmp_op("operator_equals", state_v1, 1)
    wait_start = gen(); bs[wait_start] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_one]})
    bs[cond_one]["parent"] = wait_start

    state_v2 = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", state_v2, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_zero]})
    bs[cond_zero]["parent"] = wait_over

    show = gen(); bs[show] = mk("looks_show")

    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front]),
           (wait_start,bs[wait_start]),(wait_over,bs[wait_over]),(show,bs[show])])
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

    bg_md5    = write_svg(BG_SVG)
    head_md5  = write_svg(HEAD_SVG)
    tail_md5  = write_svg(TAIL_SVG)
    apple_md5 = write_svg(APPLE_SVG)
    go_md5    = write_svg(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    head_blocks     = build_head_blocks()
    tail_blocks     = build_tail_blocks()
    apple_blocks    = build_apple_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:   ["점수", 0],
            V_BEST:    ["최고기록", 0],
            V_STATE:   ["게임상태", 1],
            V_LEN:     ["길이", 3],
            V_DIR:     ["방향", 1],
            V_NEXTDIR: ["다음방향", 1],
            V_STEP:    ["스텝간격", 0.18],
            V_APPLEX:  ["사과X", 0],
            V_APPLEY:  ["사과Y", 0],
            V_HEADX:   ["머리X", HEAD_START_X],
            V_HEADY:   ["머리Y", HEAD_START_Y],
            V_GAP:     ["기록간격", 1],
            V_SEGISS:  ["세그발급", 0],
        },
        "lists": {
            L_TRAILX: ["궤적X", []],
            L_TRAILY: ["궤적Y", []],
        },
        "broadcasts": {
            BR_START: "게임시작",
            BR_STEP:  "스텝",
            BR_APPLE: "사과배치",
            BR_TAIL:  "꼬리갱신",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "보드", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    head = {
        "isStage": False, "name": "머리",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": head_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "head", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": head_md5, "md5ext": f"{head_md5}.svg",
            "rotationCenterX": 8, "rotationCenterY": 8
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": HEAD_START_X, "y": HEAD_START_Y, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    tail = {
        "isStage": False, "name": "꼬리",
        "variables": {V_SEG: ["세그번호", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": tail_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "tail", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": tail_md5, "md5ext": f"{tail_md5}.svg",
            "rotationCenterX": 8, "rotationCenterY": 8
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    apple = {
        "isStage": False, "name": "사과",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": apple_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "apple", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": apple_md5, "md5ext": f"{apple_md5}.svg",
            "rotationCenterX": 8, "rotationCenterY": 8
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    gameover = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": gameover_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": go_md5, "md5ext": f"{go_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 85
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10000, "isDiscrete": True},
        {"id": V_BEST, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "최고기록"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 10000, "isDiscrete": True},
        {"id": V_LEN, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "길이"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 10000, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, apple, tail, head, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "snake-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # self-check: valid JSON + valid zip
    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)
    bad = zipfile.ZipFile(OUTPUT).testzip()
    assert bad is None, f"corrupt zip member: {bad}"

    print(f"wrote {OUTPUT}")
    print(f"  stage:    {len(stage_blocks)} blocks")
    print(f"  head:     {len(head_blocks)} blocks")
    print(f"  tail:     {len(tail_blocks)} blocks")
    print(f"  apple:    {len(apple_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(head_blocks)
             + len(tail_blocks) + len(apple_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")
    print(f"  targets:  5")

if __name__ == "__main__":
    main()
