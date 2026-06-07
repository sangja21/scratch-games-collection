#!/usr/bin/env python3
"""Geometry Dash — 자동 달리는 큐브, 1버튼 점프로 가시/블록/천장가시 회피."""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "지오메트리_대시.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: neon dark grid (purple → magenta) --------
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="#1A237E"/>
      <stop offset="40%"  stop-color="#311B92"/>
      <stop offset="80%"  stop-color="#4A148C"/>
      <stop offset="100%" stop-color="#1A0033"/>
    </linearGradient>
    <linearGradient id="floor" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="#6A1B9A"/>
      <stop offset="100%" stop-color="#1A0033"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <!-- horizontal neon grid lines (perspective floor) -->
  <line x1="0" y1="300" x2="480" y2="300" stroke="#E91E63" stroke-width="1.5" opacity="0.5"/>
  <line x1="0" y1="320" x2="480" y2="320" stroke="#E91E63" stroke-width="1.5" opacity="0.4"/>
  <line x1="0" y1="340" x2="480" y2="340" stroke="#E91E63" stroke-width="1.5" opacity="0.3"/>
  <!-- vertical grid lines -->
  <line x1="60"  y1="290" x2="0"   y2="360" stroke="#00E5FF" stroke-width="1" opacity="0.4"/>
  <line x1="160" y1="290" x2="140" y2="360" stroke="#00E5FF" stroke-width="1" opacity="0.4"/>
  <line x1="260" y1="290" x2="270" y2="360" stroke="#00E5FF" stroke-width="1" opacity="0.4"/>
  <line x1="360" y1="290" x2="400" y2="360" stroke="#00E5FF" stroke-width="1" opacity="0.4"/>
  <line x1="430" y1="290" x2="480" y2="360" stroke="#00E5FF" stroke-width="1" opacity="0.4"/>
  <!-- floor band -->
  <rect x="0" y="290" width="480" height="70" fill="url(#floor)" opacity="0.6"/>
  <!-- distant glow stars -->
  <circle cx="60"  cy="50" r="1.5" fill="#FFFFFF"/>
  <circle cx="120" cy="90" r="1"   fill="#FFFFFF"/>
  <circle cx="200" cy="40" r="1.5" fill="#FFFFFF"/>
  <circle cx="300" cy="70" r="1"   fill="#FFFFFF"/>
  <circle cx="380" cy="50" r="1.5" fill="#FFFFFF"/>
  <circle cx="440" cy="110" r="1"  fill="#FFFFFF"/>
  <circle cx="80"  cy="160" r="1"  fill="#FFFFFF"/>
  <circle cx="260" cy="140" r="1.5" fill="#FFFFFF"/>
</svg>"""

# -------- Cube (50x50) — yellow/cyan with face --------
CUBE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 50 50">
  <!-- main square (rounded) -->
  <rect x="3" y="3" width="44" height="44" rx="6" fill="#FFEB3B" stroke="#F57F17" stroke-width="2.5"/>
  <!-- inner shadow strip -->
  <rect x="3" y="38" width="44" height="9" rx="3" fill="#F9A825" opacity="0.7"/>
  <!-- cyan corner highlight -->
  <rect x="6" y="6" width="14" height="14" rx="3" fill="#00E5FF" opacity="0.7"/>
  <!-- face: eyes -->
  <circle cx="18" cy="24" r="3" fill="#212121"/>
  <circle cx="32" cy="24" r="3" fill="#212121"/>
  <!-- eye shine -->
  <circle cx="19" cy="23" r="1" fill="#FFFFFF"/>
  <circle cx="33" cy="23" r="1" fill="#FFFFFF"/>
  <!-- smile -->
  <path d="M17,33 Q25,38 33,33" stroke="#212121" stroke-width="2" fill="none" stroke-linecap="round"/>
</svg>"""

# -------- Spike (40x30) — white/red triangle (ground spikes, point up) --------
SPIKE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30" viewBox="0 0 40 30">
  <!-- three spikes pointing up -->
  <polygon points="3,28 11,4 19,28" fill="#FFFFFF" stroke="#E53935" stroke-width="1.4"/>
  <polygon points="14,28 22,2 30,28" fill="#FFFFFF" stroke="#E53935" stroke-width="1.4"/>
  <polygon points="25,28 33,5 37,28" fill="#FFFFFF" stroke="#E53935" stroke-width="1.4"/>
  <!-- base highlight -->
  <line x1="0" y1="28" x2="40" y2="28" stroke="#B71C1C" stroke-width="1.5"/>
</svg>"""

# -------- Block (40x30) — gray square block --------
BLOCK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30" viewBox="0 0 40 30">
  <!-- main block -->
  <rect x="2" y="2" width="36" height="26" rx="2" fill="#90A4AE" stroke="#37474F" stroke-width="2"/>
  <!-- top highlight -->
  <rect x="2" y="2" width="36" height="5" fill="#CFD8DC"/>
  <!-- bottom shadow -->
  <rect x="2" y="22" width="36" height="6" fill="#546E7A"/>
  <!-- center bolts -->
  <circle cx="10" cy="15" r="2" fill="#37474F"/>
  <circle cx="30" cy="15" r="2" fill="#37474F"/>
</svg>"""

# -------- Ceiling spike (40x30) — point down --------
CEIL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30" viewBox="0 0 40 30">
  <!-- three spikes pointing down -->
  <polygon points="3,2 11,26 19,2" fill="#FFFFFF" stroke="#E53935" stroke-width="1.4"/>
  <polygon points="14,2 22,28 30,2" fill="#FFFFFF" stroke="#E53935" stroke-width="1.4"/>
  <polygon points="25,2 33,25 37,2" fill="#FFFFFF" stroke="#E53935" stroke-width="1.4"/>
  <!-- base highlight (top edge) -->
  <line x1="0" y1="2" x2="40" y2="2" stroke="#B71C1C" stroke-width="1.5"/>
</svg>"""

# -------- Ground band (480x30) — neon stripe --------
GROUND_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="30" viewBox="0 0 480 30">
  <rect x="0" y="0" width="480" height="30" fill="#6A1B9A"/>
  <rect x="0" y="0" width="480" height="3" fill="#E91E63"/>
  <rect x="0" y="27" width="480" height="3" fill="#00E5FF"/>
  <!-- glow dots -->
  <circle cx="40"  cy="15" r="2" fill="#FFFFFF" opacity="0.8"/>
  <circle cx="120" cy="15" r="2" fill="#FFFFFF" opacity="0.8"/>
  <circle cx="200" cy="15" r="2" fill="#FFFFFF" opacity="0.8"/>
  <circle cx="290" cy="15" r="2" fill="#FFFFFF" opacity="0.8"/>
  <circle cx="370" cy="15" r="2" fill="#FFFFFF" opacity="0.8"/>
  <circle cx="440" cy="15" r="2" fill="#FFFFFF" opacity="0.8"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#E91E63" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#E91E63" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">장애물에 부딪혔어요</text>
  <text x="180" y="132" text-anchor="middle"
        fill="#00E5FF" font-family="Arial, Helvetica, sans-serif"
        font-size="14">↑ 또는 스페이스 = 점프</text>
  <text x="180" y="156" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
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
    def key_pressed(key_name):
        menu_id = gen()
        bs[menu_id] = mk("sensing_keyoptions",
            fields={"KEY_OPTION": [key_name, None]}, shadow=True)
        kp = gen()
        bs[kp] = mk("sensing_keypressed",
            inputs={"KEY_OPTION":[1, menu_id]})
        bs[menu_id]["parent"] = kp
        return kp
    return vrep, op, cmp_op, bool_op, key_pressed

# ============================================================
#  IDs
# ============================================================
V_SCORE     = "varScore01"
V_BEST      = "varBest02"
V_STATE     = "varState03"
V_VY        = "varVY04"
V_SCROLL    = "varScroll05"
V_SPAWN     = "varSpawn06"
V_PREV_JUMP = "varPrevJump07"
V_KIND      = "varKind08"

BR_START       = "brStart01"
BR_SPAWN_SPIKE = "brSpawnSpike02"
BR_SPAWN_BLOCK = "brSpawnBlock03"
BR_SPAWN_CEIL  = "brSpawnCeil04"

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, _ = make_helpers(bs)

    # === when flag clicked: init vars + broadcast 게임시작 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    s_score = gen(); bs[s_score] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점수", V_SCORE]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    s_vy = gen(); bs[s_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    s_scroll = gen(); bs[s_scroll] = mk("data_setvariableto",
        inputs={"VALUE": num(6)}, fields={"VARIABLE": ["스크롤속도", V_SCROLL]})
    s_spawn = gen(); bs[s_spawn] = mk("data_setvariableto",
        inputs={"VALUE": num(0.55)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    s_prev = gen(); bs[s_prev] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점프이전키", V_PREV_JUMP]})
    s_kind = gen(); bs[s_kind] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["패턴종류", V_KIND]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_state,bs[s_state]),(s_vy,bs[s_vy]),
           (s_scroll,bs[s_scroll]),(s_spawn,bs[s_spawn]),(s_prev,bs[s_prev]),
           (s_kind,bs[s_kind]),(bc_start,bs[bc_start])])

    # === when receive 게임시작 — forever 1: 비트 스폰 (3분기) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_a = vrep("게임상태", V_STATE)
    cond_over_a = cmp_op("operator_equals", state_v_a, 0)

    # 패턴종류 = pick random 0 to 2
    rnd_kind = gen(); bs[rnd_kind] = mk("operator_random",
        inputs={"FROM": num(0), "TO": num(2)})
    set_kind = gen(); bs[set_kind] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_kind)}, fields={"VARIABLE": ["패턴종류", V_KIND]})
    bs[rnd_kind]["parent"] = set_kind

    # outer if/else: 패턴종류 = 0 → 가시스폰, else → inner (블록 / 천장)
    kind_v_outer = vrep("패턴종류", V_KIND)
    cond_kind0 = cmp_op("operator_equals", kind_v_outer, 0)

    bm_spike = gen(); bs[bm_spike] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["가시스폰", BR_SPAWN_SPIKE]}, shadow=True)
    bc_spike = gen(); bs[bc_spike] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_spike]})
    bs[bm_spike]["parent"] = bc_spike

    # inner if/else: 패턴종류 = 1 → 블록스폰, else → 천장스폰
    kind_v_inner = vrep("패턴종류", V_KIND)
    cond_kind1 = cmp_op("operator_equals", kind_v_inner, 1)

    bm_block = gen(); bs[bm_block] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["블록스폰", BR_SPAWN_BLOCK]}, shadow=True)
    bc_block = gen(); bs[bc_block] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_block]})
    bs[bm_block]["parent"] = bc_block

    bm_ceil = gen(); bs[bm_ceil] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["천장스폰", BR_SPAWN_CEIL]}, shadow=True)
    bc_ceil = gen(); bs[bc_ceil] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ceil]})
    bs[bm_ceil]["parent"] = bc_ceil

    if_else_inner = gen(); bs[if_else_inner] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_kind1],
                "SUBSTACK":[2,bc_block],
                "SUBSTACK2":[2,bc_ceil]})
    bs[cond_kind1]["parent"] = if_else_inner
    bs[bc_block]["parent"] = if_else_inner
    bs[bc_ceil]["parent"] = if_else_inner

    if_else_outer = gen(); bs[if_else_outer] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_kind0],
                "SUBSTACK":[2,bc_spike],
                "SUBSTACK2":[2,if_else_inner]})
    bs[cond_kind0]["parent"] = if_else_outer
    bs[bc_spike]["parent"] = if_else_outer
    bs[if_else_inner]["parent"] = if_else_outer

    # wait 스폰주기
    spawn_v = vrep("스폰주기", V_SPAWN)
    wt_sp = gen(); bs[wt_sp] = mk("control_wait",
        inputs={"DURATION": slot(spawn_v)})
    bs[spawn_v]["parent"] = wt_sp

    chain([(set_kind,bs[set_kind]),(if_else_outer,bs[if_else_outer]),(wt_sp,bs[wt_sp])])

    rep_until_a = gen(); bs[rep_until_a] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_a], "SUBSTACK":[2,set_kind]})
    bs[cond_over_a]["parent"] = rep_until_a
    bs[set_kind]["parent"] = rep_until_a

    chain([(h2,bs[h2]),(rep_until_a,bs[rep_until_a])])

    # === when receive 게임시작 — forever 2: 점수 누적 + 가속 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_b = vrep("게임상태", V_STATE)
    cond_over_b = cmp_op("operator_equals", state_v_b, 0)

    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})

    # if (점수 mod 80) = 0 → 스크롤속도 += 1, if 스폰주기 > 0.35 → 스폰주기 -= 0.05
    score_v_a = vrep("점수", V_SCORE)
    mod_op = op("operator_mod", score_v_a, 80)
    cond_mod0 = cmp_op("operator_equals", mod_op, 0)
    bs[mod_op]["parent"] = cond_mod0

    inc_scroll = gen(); bs[inc_scroll] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["스크롤속도", V_SCROLL]})

    spawn_v_b = vrep("스폰주기", V_SPAWN)
    cond_sp_gt = cmp_op("operator_gt", spawn_v_b, 0.35)
    dec_spawn = gen(); bs[dec_spawn] = mk("data_changevariableby",
        inputs={"VALUE": num(-0.05)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    if_sp = gen(); bs[if_sp] = mk("control_if",
        inputs={"CONDITION":[2,cond_sp_gt], "SUBSTACK":[2,dec_spawn]})
    bs[cond_sp_gt]["parent"] = if_sp
    bs[dec_spawn]["parent"] = if_sp

    chain([(inc_scroll,bs[inc_scroll]),(if_sp,bs[if_sp])])

    if_accel = gen(); bs[if_accel] = mk("control_if",
        inputs={"CONDITION":[2,cond_mod0], "SUBSTACK":[2,inc_scroll]})
    bs[cond_mod0]["parent"] = if_accel
    bs[inc_scroll]["parent"] = if_accel

    wt_score = gen(); bs[wt_score] = mk("control_wait", inputs={"DURATION": num(0.1)})

    chain([(inc_score,bs[inc_score]),(if_accel,bs[if_accel]),(wt_score,bs[wt_score])])

    rep_until_b = gen(); bs[rep_until_b] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_b], "SUBSTACK":[2,inc_score]})
    bs[cond_over_b]["parent"] = rep_until_b
    bs[inc_score]["parent"] = rep_until_b

    chain([(h3,bs[h3]),(rep_until_b,bs[rep_until_b])])

    return bs

# ============================================================
#  CUBE blocks
# ============================================================
def build_cube_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, key_pressed = make_helpers(bs)

    # === when flag clicked: init pos + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(-150), "Y": num(-130)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: input + physics + collision loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    reset_vy = gen(); bs[reset_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    reset_prev = gen(); bs[reset_prev] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점프이전키", V_PREV_JUMP]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": num(-150), "Y": num(-130)})
    sz0 = gen(); bs[sz0] = mk("looks_setsizeto", inputs={"SIZE": num(70)})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # --- jump edge detection ---
    # 현재점프키 = (key up arrow pressed) OR (key space pressed)
    k_up_a = key_pressed("up arrow")
    k_sp_a = key_pressed("space")
    cond_jump_input_a = bool_op("operator_or", k_up_a, k_sp_a)

    # prev key = 0?
    prev_v1 = vrep("점프이전키", V_PREV_JUMP)
    cond_prev0 = cmp_op("operator_equals", prev_v1, 0)

    # VY = 0? (on ground or block, stationary vertically)
    vy_v_chk = vrep("VY", V_VY)
    cond_vy0 = cmp_op("operator_equals", vy_v_chk, 0)

    # (input AND prev=0)
    cond_edge_inner = bool_op("operator_and", cond_jump_input_a, cond_prev0)
    # ((input AND prev=0) AND VY=0)
    cond_edge_jump = bool_op("operator_and", cond_edge_inner, cond_vy0)

    set_vy_jump = gen(); bs[set_vy_jump] = mk("data_setvariableto",
        inputs={"VALUE": num(11)}, fields={"VARIABLE": ["VY", V_VY]})

    if_jump = gen(); bs[if_jump] = mk("control_if",
        inputs={"CONDITION":[2,cond_edge_jump], "SUBSTACK":[2,set_vy_jump]})
    bs[cond_edge_jump]["parent"] = if_jump
    bs[set_vy_jump]["parent"] = if_jump

    # --- update 점프이전키 ---
    k_up_b = key_pressed("up arrow")
    k_sp_b = key_pressed("space")
    cond_jump_input_b = bool_op("operator_or", k_up_b, k_sp_b)

    set_prev_1 = gen(); bs[set_prev_1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점프이전키", V_PREV_JUMP]})
    set_prev_0 = gen(); bs[set_prev_0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점프이전키", V_PREV_JUMP]})

    if_else_prev = gen(); bs[if_else_prev] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_jump_input_b],
                "SUBSTACK":[2,set_prev_1],
                "SUBSTACK2":[2,set_prev_0]})
    bs[cond_jump_input_b]["parent"] = if_else_prev
    bs[set_prev_1]["parent"] = if_else_prev
    bs[set_prev_0]["parent"] = if_else_prev

    # --- gravity: VY -= 1.2 ---
    grav = gen(); bs[grav] = mk("data_changevariableby",
        inputs={"VALUE": num(-1.2)}, fields={"VARIABLE": ["VY", V_VY]})

    # --- change y by VY ---
    vy_v_d = vrep("VY", V_VY)
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(vy_v_d)})
    bs[vy_v_d]["parent"] = chy

    # --- block landing: if (touching 블록 AND VY<0) → change y by 4, VY=0 ---
    tm_block = gen(); bs[tm_block] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["블록", None]}, shadow=True)
    tc_block = gen(); bs[tc_block] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_block]})
    bs[tm_block]["parent"] = tc_block
    # VY < 0 guard
    vy_v_block = vrep("VY", V_VY)
    cond_vy_neg = cmp_op("operator_lt", vy_v_block, 0)
    cond_block_land = bool_op("operator_and", tc_block, cond_vy_neg)
    push_up = gen(); bs[push_up] = mk("motion_changeyby", inputs={"DY": num(4)})
    set_vy_zero_block = gen(); bs[set_vy_zero_block] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    chain([(push_up,bs[push_up]),(set_vy_zero_block,bs[set_vy_zero_block])])
    if_block = gen(); bs[if_block] = mk("control_if",
        inputs={"CONDITION":[2,cond_block_land], "SUBSTACK":[2,push_up]})
    bs[cond_block_land]["parent"] = if_block
    bs[push_up]["parent"] = if_block

    # --- floor clamp: if y < -130 → goto -150,-130 + VY=0 ---
    yp_f = gen(); bs[yp_f] = mk("motion_yposition")
    cond_floor = cmp_op("operator_lt", yp_f, -130)
    bs[yp_f]["parent"] = cond_floor
    g_floor = gen(); bs[g_floor] = mk("motion_gotoxy",
        inputs={"X": num(-150), "Y": num(-130)})
    set_vy_zero = gen(); bs[set_vy_zero] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    chain([(g_floor,bs[g_floor]),(set_vy_zero,bs[set_vy_zero])])
    if_floor = gen(); bs[if_floor] = mk("control_if",
        inputs={"CONDITION":[2,cond_floor], "SUBSTACK":[2,g_floor]})
    bs[cond_floor]["parent"] = if_floor
    bs[g_floor]["parent"] = if_floor

    # --- touching 가시 → state=0 ---
    tm_spike = gen(); bs[tm_spike] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["가시", None]}, shadow=True)
    tc_spike = gen(); bs[tc_spike] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_spike]})
    bs[tm_spike]["parent"] = tc_spike
    set_st_spike = gen(); bs[set_st_spike] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_spike = gen(); bs[if_spike] = mk("control_if",
        inputs={"CONDITION":[2,tc_spike], "SUBSTACK":[2,set_st_spike]})
    bs[tc_spike]["parent"] = if_spike
    bs[set_st_spike]["parent"] = if_spike

    # --- touching 천장가시 → state=0 ---
    tm_ceil = gen(); bs[tm_ceil] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["천장가시", None]}, shadow=True)
    tc_ceil = gen(); bs[tc_ceil] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_ceil]})
    bs[tm_ceil]["parent"] = tc_ceil
    set_st_ceil = gen(); bs[set_st_ceil] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_ceil = gen(); bs[if_ceil] = mk("control_if",
        inputs={"CONDITION":[2,tc_ceil], "SUBSTACK":[2,set_st_ceil]})
    bs[tc_ceil]["parent"] = if_ceil
    bs[set_st_ceil]["parent"] = if_ceil

    # --- best score: if 점수 > 최고기록 → 최고기록 = 점수 ---
    score_v = vrep("점수", V_SCORE)
    best_v = vrep("최고기록", V_BEST)
    cond_best = cmp_op("operator_gt", score_v, best_v)
    score_v2 = vrep("점수", V_SCORE)
    set_best = gen(); bs[set_best] = mk("data_setvariableto",
        inputs={"VALUE": slot(score_v2)}, fields={"VARIABLE": ["최고기록", V_BEST]})
    bs[score_v2]["parent"] = set_best
    if_best = gen(); bs[if_best] = mk("control_if",
        inputs={"CONDITION":[2,cond_best], "SUBSTACK":[2,set_best]})
    bs[cond_best]["parent"] = if_best
    bs[set_best]["parent"] = if_best

    # wait 0.025
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(if_jump,bs[if_jump]),(if_else_prev,bs[if_else_prev]),
           (grav,bs[grav]),(chy,bs[chy]),
           (if_block,bs[if_block]),(if_floor,bs[if_floor]),
           (if_spike,bs[if_spike]),(if_ceil,bs[if_ceil]),
           (if_best,bs[if_best]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_jump]})
    bs[cond_over]["parent"] = rep_until
    bs[if_jump]["parent"] = rep_until

    chain([(h2,bs[h2]),(reset_vy,bs[reset_vy]),(reset_prev,bs[reset_prev]),
           (g0,bs[g0]),(sz0,bs[sz0]),(rep_until,bs[rep_until])])

    # === when flag clicked: play pop on game over ===
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=400, y=20)
    state_v_d = vrep("게임상태", V_STATE)
    cond_zero_d = cmp_op("operator_equals", state_v_d, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_zero_d]})
    bs[cond_zero_d]["parent"] = wait_over

    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd

    chain([(h3,bs[h3]),(wait_over,bs[wait_over]),(pitch,bs[pitch]),(snd,bs[snd])])

    return bs

# ============================================================
#  obstacle factory (spike / block / ceiling) — same pattern,
#  varies by broadcast id, spawn y, costume name
# ============================================================
def build_obstacle_blocks(spawn_broadcast_id, spawn_broadcast_name,
                          spawn_y, costume_name):
    bs = {}
    vrep, op, cmp_op, bool_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    # === when receive {spawn}: goto + costume + clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": [spawn_broadcast_name, spawn_broadcast_id]})

    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": num(spawn_y)})

    cm = gen(); bs[cm] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    menu_id = bs[cm]["inputs"]["COSTUME"][1]
    bs[menu_id] = mk("looks_costume",
        fields={"COSTUME":[costume_name, None]}, shadow=True, parent=cm)

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(cm,bs[cm]),(cclone,bs[cclone])])

    # === when I start as clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    show = gen(); bs[show] = mk("looks_show")

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    scroll_v = vrep("스크롤속도", V_SCROLL)
    neg_scroll = op("operator_multiply", -1, scroll_v)
    chx = gen(); bs[chx] = mk("motion_changexby",
        inputs={"DX": slot(neg_scroll)})
    bs[neg_scroll]["parent"] = chx

    xp = gen(); bs[xp] = mk("motion_xposition")
    cond_off = cmp_op("operator_lt", xp, -260)
    bs[xp]["parent"] = cond_off
    del_off = gen(); bs[del_off] = mk("control_delete_this_clone")
    if_off = gen(); bs[if_off] = mk("control_if",
        inputs={"CONDITION":[2,cond_off], "SUBSTACK":[2,del_off]})
    bs[cond_off]["parent"] = if_off
    bs[del_off]["parent"] = if_off

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(chx,bs[chx]),(if_off,bs[if_off]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,chx]})
    bs[cond_over]["parent"] = rep_until
    bs[chx]["parent"] = rep_until

    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(ch,bs[ch]),(show,bs[show]),(rep_until,bs[rep_until]),(del_end,bs[del_end])])

    return bs

# ============================================================
#  GROUND blocks (static)
# ============================================================
def build_ground_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-150)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sh,bs[sh])])
    return bs

# ============================================================
#  GAME OVER banner blocks
# ============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _, _ = make_helpers(bs)

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

    # wait 1 tick before showing banner to avoid last-frame flicker
    wt_tick = gen(); bs[wt_tick] = mk("control_wait", inputs={"DURATION": num(0.05)})

    show = gen(); bs[show] = mk("looks_show")

    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front]),
           (wait_start,bs[wait_start]),(wait_over,bs[wait_over]),(wt_tick,bs[wt_tick]),(show,bs[show])])
    return bs

# ============================================================
#  ASSEMBLE PROJECT
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    cube_md5 = md5_bytes(CUBE_SVG.encode("utf-8"))
    with open(f"{WORK}/{cube_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CUBE_SVG)

    spike_md5 = md5_bytes(SPIKE_SVG.encode("utf-8"))
    with open(f"{WORK}/{spike_md5}.svg", "w", encoding="utf-8") as f:
        f.write(SPIKE_SVG)

    block_md5 = md5_bytes(BLOCK_SVG.encode("utf-8"))
    with open(f"{WORK}/{block_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BLOCK_SVG)

    ceil_md5 = md5_bytes(CEIL_SVG.encode("utf-8"))
    with open(f"{WORK}/{ceil_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CEIL_SVG)

    gnd_md5 = md5_bytes(GROUND_SVG.encode("utf-8"))
    with open(f"{WORK}/{gnd_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GROUND_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    cube_blocks     = build_cube_blocks()
    spike_blocks    = build_obstacle_blocks(BR_SPAWN_SPIKE, "가시스폰", -130, "spike")
    block_blocks    = build_obstacle_blocks(BR_SPAWN_BLOCK, "블록스폰", -105, "block")
    ceil_blocks     = build_obstacle_blocks(BR_SPAWN_CEIL,  "천장스폰",  110, "ceil")
    ground_blocks   = build_ground_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:     ["점수", 0],
            V_BEST:      ["최고기록", 0],
            V_STATE:     ["게임상태", 1],
            V_VY:        ["VY", 0],
            V_SCROLL:    ["스크롤속도", 6],
            V_SPAWN:     ["스폰주기", 0.55],
            V_PREV_JUMP: ["점프이전키", 0],
            V_KIND:      ["패턴종류", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:       "게임시작",
            BR_SPAWN_SPIKE: "가시스폰",
            BR_SPAWN_BLOCK: "블록스폰",
            BR_SPAWN_CEIL:  "천장스폰",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "네온", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    ground = {
        "isStage": False, "name": "바닥",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ground_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "ground", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": gnd_md5, "md5ext": f"{gnd_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 15
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 0, "y": -150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    spike = {
        "isStage": False, "name": "가시",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": spike_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "spike", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": spike_md5, "md5ext": f"{spike_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 15
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    block = {
        "isStage": False, "name": "블록",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": block_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "block", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": block_md5, "md5ext": f"{block_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 15
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ceil_sp = {
        "isStage": False, "name": "천장가시",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ceil_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "ceil", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ceil_md5, "md5ext": f"{ceil_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 15
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    cube = {
        "isStage": False, "name": "큐브",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": cube_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "cube", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": cube_md5, "md5ext": f"{cube_md5}.svg",
            "rotationCenterX": 25, "rotationCenterY": 25
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": -150, "y": -130, "size": 70, "direction": 90,
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
        "volume": 100, "layerOrder": 6, "visible": False,
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
        {"id": V_SCROLL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "스크롤속도"}, "spriteName": None,
         "value": 6, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 50, "isDiscrete": False},
    ]

    project = {
        "targets": [stage, ground, spike, block, ceil_sp, cube, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "geometry-dash-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    total = sum(len(b) for b in [stage_blocks, cube_blocks, spike_blocks,
                                 block_blocks, ceil_blocks, ground_blocks,
                                 gameover_blocks])
    print(f"[geometry-dash] built {OUTPUT}")
    print(f"  stage: {len(stage_blocks)}  cube: {len(cube_blocks)}  "
          f"spike: {len(spike_blocks)}  block: {len(block_blocks)}  "
          f"ceil: {len(ceil_blocks)}  ground: {len(ground_blocks)}  "
          f"gameover: {len(gameover_blocks)}  total: {total}")

if __name__ == "__main__":
    main()
