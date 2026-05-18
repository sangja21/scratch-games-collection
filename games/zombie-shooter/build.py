#!/usr/bin/env python3
"""Zombie Shooter — top-down twin-stick shooter (arrow/WASD move + mouse aim + click fire)."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "좀비_슈터.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: grass tiles + dirt patches --------
random.seed(31)
tiles = []
for ty in range(0, 360, 40):
    for tx in range(0, 480, 40):
        shade = "#43A047" if (tx // 40 + ty // 40) % 2 == 0 else "#388E3C"
        tiles.append(f'<rect x="{tx}" y="{ty}" width="40" height="40" fill="{shade}"/>')
TILES = "\n    ".join(tiles)

dots = []
for _ in range(28):
    x = random.randint(10, 470); y = random.randint(10, 350)
    r = random.uniform(1.4, 2.6)
    dots.append(f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="#1B5E20" opacity="0.55"/>')
DOTS = "\n    ".join(dots)

grass_blades = []
for _ in range(40):
    x = random.randint(10, 470); y = random.randint(15, 350)
    grass_blades.append(
        f'<path d="M {x} {y} Q {x-2} {y-7} {x} {y-11} Q {x+2} {y-7} {x} {y}" '
        f'fill="#66BB6A" opacity="0.7"/>'
    )
GRASS = "\n    ".join(grass_blades)

dirt_patches = []
for cx, cy, rx, ry in [(110, 80, 50, 22), (360, 200, 60, 28), (220, 290, 45, 18)]:
    dirt_patches.append(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
        f'fill="#8D6E63" opacity="0.45"/>'
    )
DIRT = "\n    ".join(dirt_patches)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <g>
    {TILES}
  </g>
  <g>
    {DIRT}
  </g>
  <g>
    {DOTS}
  </g>
  <g>
    {GRASS}
  </g>
</svg>"""

# -------- Player (top-down): hat + shoulders + arrow pointing forward --------
PLAYER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 50 50">
  <!-- shoulders -->
  <ellipse cx="25" cy="30" rx="14" ry="10" fill="#1565C0" stroke="#0D47A1" stroke-width="1.5"/>
  <!-- head -->
  <circle cx="25" cy="22" r="9" fill="#FFCC80" stroke="#5D4037" stroke-width="1.2"/>
  <!-- hat brim -->
  <ellipse cx="25" cy="18" rx="11" ry="3" fill="#212121"/>
  <!-- hat top -->
  <rect x="20" y="10" width="10" height="8" rx="2" fill="#424242" stroke="#212121" stroke-width="1"/>
  <!-- arms -->
  <circle cx="11" cy="32" r="4" fill="#1565C0" stroke="#0D47A1" stroke-width="1"/>
  <circle cx="39" cy="32" r="4" fill="#1565C0" stroke="#0D47A1" stroke-width="1"/>
  <!-- gun barrel pointing UP (Scratch direction 0 = up after pointtowards mouse) -->
  <rect x="22" y="0" width="6" height="14" fill="#37474F" stroke="#212121" stroke-width="1"/>
  <rect x="20" y="11" width="10" height="4" fill="#263238" stroke="#212121" stroke-width="1"/>
  <!-- forward indicator -->
  <polygon points="25,2 22,7 28,7" fill="#FFEB3B"/>
</svg>"""

# -------- Player (hit flash) --------
PLAYER_HIT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 50 50">
  <ellipse cx="25" cy="30" rx="14" ry="10" fill="#E53935" stroke="#B71C1C" stroke-width="1.5"/>
  <circle cx="25" cy="22" r="9" fill="#FFAB91" stroke="#5D4037" stroke-width="1.2"/>
  <ellipse cx="25" cy="18" rx="11" ry="3" fill="#212121"/>
  <rect x="20" y="10" width="10" height="8" rx="2" fill="#424242" stroke="#212121" stroke-width="1"/>
  <circle cx="11" cy="32" r="4" fill="#E53935" stroke="#B71C1C" stroke-width="1"/>
  <circle cx="39" cy="32" r="4" fill="#E53935" stroke="#B71C1C" stroke-width="1"/>
  <rect x="22" y="0" width="6" height="14" fill="#37474F" stroke="#212121" stroke-width="1"/>
  <rect x="20" y="11" width="10" height="4" fill="#263238" stroke="#212121" stroke-width="1"/>
  <polygon points="25,2 22,7 28,7" fill="#FFEB3B"/>
</svg>"""

# -------- Bullet: yellow oblong --------
BULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
  <ellipse cx="7" cy="7" rx="6" ry="2.4" fill="#FFEB3B" stroke="#F57F17" stroke-width="1"/>
  <ellipse cx="9" cy="7" rx="1.5" ry="1" fill="#FFFDE7"/>
</svg>"""

# -------- Zombie walk frame 1 (left arm up) — cartoon green, friendly face --------
ZOMBIE1_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 50 50">
  <!-- shadow -->
  <ellipse cx="25" cy="44" rx="13" ry="3" fill="#000000" opacity="0.25"/>
  <!-- body -->
  <ellipse cx="25" cy="33" rx="11" ry="9" fill="#7CB342" stroke="#33691E" stroke-width="1.4"/>
  <!-- shirt rip -->
  <path d="M 17 35 L 22 31 L 20 37 L 25 34 L 23 39 Z" fill="#558B2F" opacity="0.6"/>
  <!-- head -->
  <circle cx="25" cy="20" r="10" fill="#9CCC65" stroke="#33691E" stroke-width="1.4"/>
  <!-- eyes (big, friendly) -->
  <circle cx="21" cy="19" r="3" fill="#FFFFFF" stroke="#33691E" stroke-width="0.8"/>
  <circle cx="29" cy="19" r="3" fill="#FFFFFF" stroke="#33691E" stroke-width="0.8"/>
  <circle cx="21" cy="19.5" r="1.3" fill="#212121"/>
  <circle cx="29" cy="19.5" r="1.3" fill="#212121"/>
  <!-- smile -->
  <path d="M 20 24 Q 25 28 30 24" stroke="#33691E" stroke-width="1.3" fill="none" stroke-linecap="round"/>
  <!-- arms -->
  <rect x="6" y="22" width="6" height="3.5" rx="1.5" fill="#9CCC65" stroke="#33691E" stroke-width="1" transform="rotate(-20 9 24)"/>
  <rect x="38" y="32" width="6" height="3.5" rx="1.5" fill="#9CCC65" stroke="#33691E" stroke-width="1"/>
  <!-- tiny tuft of hair -->
  <path d="M 23 11 L 25 8 L 27 11" stroke="#33691E" stroke-width="1.5" fill="none"/>
</svg>"""

# -------- Zombie walk frame 2 (right arm up) --------
ZOMBIE2_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 50 50">
  <ellipse cx="25" cy="44" rx="13" ry="3" fill="#000000" opacity="0.25"/>
  <ellipse cx="25" cy="33" rx="11" ry="9" fill="#7CB342" stroke="#33691E" stroke-width="1.4"/>
  <path d="M 17 35 L 22 31 L 20 37 L 25 34 L 23 39 Z" fill="#558B2F" opacity="0.6"/>
  <circle cx="25" cy="20" r="10" fill="#9CCC65" stroke="#33691E" stroke-width="1.4"/>
  <circle cx="21" cy="19" r="3" fill="#FFFFFF" stroke="#33691E" stroke-width="0.8"/>
  <circle cx="29" cy="19" r="3" fill="#FFFFFF" stroke="#33691E" stroke-width="0.8"/>
  <circle cx="21" cy="19.5" r="1.3" fill="#212121"/>
  <circle cx="29" cy="19.5" r="1.3" fill="#212121"/>
  <path d="M 20 24 Q 25 28 30 24" stroke="#33691E" stroke-width="1.3" fill="none" stroke-linecap="round"/>
  <rect x="6" y="32" width="6" height="3.5" rx="1.5" fill="#9CCC65" stroke="#33691E" stroke-width="1"/>
  <rect x="38" y="22" width="6" height="3.5" rx="1.5" fill="#9CCC65" stroke="#33691E" stroke-width="1" transform="rotate(20 41 24)"/>
  <path d="M 23 11 L 25 8 L 27 11" stroke="#33691E" stroke-width="1.5" fill="none"/>
</svg>"""

# -------- Zombie dead (X-eyes, lying) --------
ZOMBIE_DEAD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 50 50">
  <ellipse cx="25" cy="44" rx="16" ry="3" fill="#000000" opacity="0.25"/>
  <ellipse cx="25" cy="32" rx="15" ry="8" fill="#689F38" stroke="#33691E" stroke-width="1.4"/>
  <circle cx="14" cy="28" r="8" fill="#9CCC65" stroke="#33691E" stroke-width="1.4"/>
  <line x1="11" y1="26" x2="15" y2="30" stroke="#212121" stroke-width="1.5"/>
  <line x1="15" y1="26" x2="11" y2="30" stroke="#212121" stroke-width="1.5"/>
  <line x1="17" y1="26" x2="21" y2="30" stroke="#212121" stroke-width="1.5"/>
  <line x1="21" y1="26" x2="17" y2="30" stroke="#212121" stroke-width="1.5"/>
  <path d="M 13 33 Q 16 31 18 33" stroke="#33691E" stroke-width="1.2" fill="none"/>
  <circle cx="35" cy="35" r="2" fill="#9CCC65" opacity="0.7"/>
  <circle cx="40" cy="33" r="1.5" fill="#9CCC65" opacity="0.7"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.88"
        stroke="#7CB342" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#7CB342" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">좀비에게 잡혔어요</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#FFB74D" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭</text>
</svg>"""

# ============================================================
#  helpers (mirrors duck-hunt patterns)
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

# ============================================================
#  IDs
# ============================================================
V_SCORE   = "varScore01"
V_LIFE    = "varLife02"
V_WAVE    = "varWave03"
V_STATE   = "varState04"
V_KILLS   = "varKills05"
V_TARGET  = "varTarget06"
V_ZSPEED  = "varZSpeed07"
V_SX      = "varSX08"
V_SY      = "varSY09"
V_BX      = "varBX10"
V_BY      = "varBY11"
V_BDIR    = "varBDir12"
V_INV     = "varInv13"
V_SPAWNED = "varSpawned14"

BR_START = "brStart01"
BR_SPAWN = "brSpawn02"
BR_NEXT  = "brNext03"
BR_FIRE  = "brFire04"

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

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init + broadcast 게임시작 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = []
    for var_pair, val in [
        (("점수", V_SCORE), 0),
        (("라이프", V_LIFE), 3),
        (("웨이브", V_WAVE), 1),
        (("게임상태", V_STATE), 1),
        (("처치수", V_KILLS), 0),
        (("웨이브목표", V_TARGET), 5),
        (("좀비속도", V_ZSPEED), 1.4),
        (("무적시간", V_INV), 0),
        (("스폰수", V_SPAWNED), 0),
    ]:
        sid = gen(); bs[sid] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": list(var_pair)})
        inits.append((sid, bs[sid]))

    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(0.5)})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h, bs[h])] + inits + [(w1, bs[w1]), (bc_start, bs[bc_start])])

    # === on 게임시작: spawn loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # if 게임상태=1 AND 스폰수<웨이브목표:
    state_v = vrep("게임상태", V_STATE)
    cond_alive = cmp_op("operator_equals", state_v, 1)
    sp_v = vrep("스폰수", V_SPAWNED)
    tg_v = vrep("웨이브목표", V_TARGET)
    cond_more = cmp_op("operator_lt", sp_v, tg_v)
    cond_both = bool_op("operator_and", cond_alive, cond_more)

    # pick side: random 1..4
    side_pick = gen(); bs[side_pick] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(4)})
    set_side_holder = gen(); bs[set_side_holder] = mk("data_setvariableto",
        inputs={"VALUE": slot(side_pick)}, fields={"VARIABLE": ["스폰X", V_SX]})
    bs[side_pick]["parent"] = set_side_holder
    # We'll repurpose: store side into SX temporarily, then compute SX/SY via if/else chain.
    # Simpler approach: use 4 independent random pickers with weighted ifs based on side.

    # Reset: use a cleaner approach — just compute SX, SY based on side value stored in V_SX (overloaded for one tick).
    # Branch on side value (read from V_SX before overwriting):
    side_v1 = vrep("스폰X", V_SX)
    cond_s1 = cmp_op("operator_equals", side_v1, 1)
    side_v2 = vrep("스폰X", V_SX)
    cond_s2 = cmp_op("operator_equals", side_v2, 2)
    side_v3 = vrep("스폰X", V_SX)
    cond_s3 = cmp_op("operator_equals", side_v3, 3)

    # Side=1: top edge → SX=random(-230..230), SY=180
    s1_sx_calc = gen(); bs[s1_sx_calc] = mk("operator_random",
        inputs={"FROM": num(-230), "TO": num(230)})
    s1_set_sx = gen(); bs[s1_set_sx] = mk("data_setvariableto",
        inputs={"VALUE": slot(s1_sx_calc)}, fields={"VARIABLE": ["스폰X", V_SX]})
    bs[s1_sx_calc]["parent"] = s1_set_sx
    s1_set_sy = gen(); bs[s1_set_sy] = mk("data_setvariableto",
        inputs={"VALUE": num(180)}, fields={"VARIABLE": ["스폰Y", V_SY]})
    chain([(s1_set_sx, bs[s1_set_sx]), (s1_set_sy, bs[s1_set_sy])])

    if_s1 = gen(); bs[if_s1] = mk("control_if",
        inputs={"CONDITION": [2, cond_s1], "SUBSTACK": [2, s1_set_sx]})
    bs[cond_s1]["parent"] = if_s1
    bs[s1_set_sx]["parent"] = if_s1

    # Side=2: bottom edge → SX=random(-230..230), SY=-180
    s2_sx_calc = gen(); bs[s2_sx_calc] = mk("operator_random",
        inputs={"FROM": num(-230), "TO": num(230)})
    s2_set_sx = gen(); bs[s2_set_sx] = mk("data_setvariableto",
        inputs={"VALUE": slot(s2_sx_calc)}, fields={"VARIABLE": ["스폰X", V_SX]})
    bs[s2_sx_calc]["parent"] = s2_set_sx
    s2_set_sy = gen(); bs[s2_set_sy] = mk("data_setvariableto",
        inputs={"VALUE": num(-180)}, fields={"VARIABLE": ["스폰Y", V_SY]})
    chain([(s2_set_sx, bs[s2_set_sx]), (s2_set_sy, bs[s2_set_sy])])

    if_s2 = gen(); bs[if_s2] = mk("control_if",
        inputs={"CONDITION": [2, cond_s2], "SUBSTACK": [2, s2_set_sx]})
    bs[cond_s2]["parent"] = if_s2
    bs[s2_set_sx]["parent"] = if_s2

    # Side=3: left edge → SX=-230, SY=random(-170..170)
    s3_sy_calc = gen(); bs[s3_sy_calc] = mk("operator_random",
        inputs={"FROM": num(-170), "TO": num(170)})
    s3_set_sx = gen(); bs[s3_set_sx] = mk("data_setvariableto",
        inputs={"VALUE": num(-230)}, fields={"VARIABLE": ["스폰X", V_SX]})
    s3_set_sy = gen(); bs[s3_set_sy] = mk("data_setvariableto",
        inputs={"VALUE": slot(s3_sy_calc)}, fields={"VARIABLE": ["스폰Y", V_SY]})
    bs[s3_sy_calc]["parent"] = s3_set_sy
    chain([(s3_set_sx, bs[s3_set_sx]), (s3_set_sy, bs[s3_set_sy])])

    if_s3 = gen(); bs[if_s3] = mk("control_if",
        inputs={"CONDITION": [2, cond_s3], "SUBSTACK": [2, s3_set_sx]})
    bs[cond_s3]["parent"] = if_s3
    bs[s3_set_sx]["parent"] = if_s3

    # Side=else (4): right edge → SX=230, SY=random(-170..170)
    s4_sy_calc = gen(); bs[s4_sy_calc] = mk("operator_random",
        inputs={"FROM": num(-170), "TO": num(170)})
    s4_set_sx = gen(); bs[s4_set_sx] = mk("data_setvariableto",
        inputs={"VALUE": num(230)}, fields={"VARIABLE": ["스폰X", V_SX]})
    s4_set_sy = gen(); bs[s4_set_sy] = mk("data_setvariableto",
        inputs={"VALUE": slot(s4_sy_calc)}, fields={"VARIABLE": ["스폰Y", V_SY]})
    bs[s4_sy_calc]["parent"] = s4_set_sy
    chain([(s4_set_sx, bs[s4_set_sx]), (s4_set_sy, bs[s4_set_sy])])

    # if NOT (s1 or s2 or s3) → run s4
    side_v_a = vrep("스폰X", V_SX)
    cond_s4a = cmp_op("operator_equals", side_v_a, 4)
    if_s4 = gen(); bs[if_s4] = mk("control_if",
        inputs={"CONDITION": [2, cond_s4a], "SUBSTACK": [2, s4_set_sx]})
    bs[cond_s4a]["parent"] = if_s4
    bs[s4_set_sx]["parent"] = if_s4

    # broadcast 좀비스폰
    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["좀비스폰", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    # 스폰수 +1
    inc_sp = gen(); bs[inc_sp] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["스폰수", V_SPAWNED]})

    # Compose substack: side_pick (overloads V_SX), then if_s1..s4, then broadcast + inc
    chain([(set_side_holder, bs[set_side_holder]),
           (if_s1, bs[if_s1]), (if_s2, bs[if_s2]),
           (if_s3, bs[if_s3]), (if_s4, bs[if_s4]),
           (bc_sp, bs[bc_sp]), (inc_sp, bs[inc_sp])])

    if_can_spawn = gen(); bs[if_can_spawn] = mk("control_if",
        inputs={"CONDITION": [2, cond_both], "SUBSTACK": [2, set_side_holder]})
    bs[cond_both]["parent"] = if_can_spawn
    bs[set_side_holder]["parent"] = if_can_spawn

    # wait: max(0.5, 2 / 웨이브)
    wave_v = vrep("웨이브", V_WAVE)
    wait_calc = op("operator_divide", 2, wave_v)
    wait_step = gen(); bs[wait_step] = mk("control_wait",
        inputs={"DURATION": slot(wait_calc)})
    bs[wait_calc]["parent"] = wait_step

    # forever block holding if_can_spawn + wait
    chain([(if_can_spawn, bs[if_can_spawn]), (wait_step, bs[wait_step])])
    forever = gen(); bs[forever] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_can_spawn]})
    bs[if_can_spawn]["parent"] = forever

    chain([(h2, bs[h2]), (forever, bs[forever])])

    # === on 다음웨이브 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=900,
        fields={"BROADCAST_OPTION": ["다음웨이브", BR_NEXT]})

    inc_wave = gen(); bs[inc_wave] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["웨이브", V_WAVE]})

    zsp_v = vrep("좀비속도", V_ZSPEED)
    mul_zsp = op("operator_multiply", zsp_v, 1.12)
    set_zsp = gen(); bs[set_zsp] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_zsp)}, fields={"VARIABLE": ["좀비속도", V_ZSPEED]})
    bs[mul_zsp]["parent"] = set_zsp

    inc_tg = gen(); bs[inc_tg] = mk("data_changevariableby",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["웨이브목표", V_TARGET]})

    r_kills = gen(); bs[r_kills] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["처치수", V_KILLS]})

    r_sp = gen(); bs[r_sp] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["스폰수", V_SPAWNED]})

    w_wave = gen(); bs[w_wave] = mk("control_wait", inputs={"DURATION": num(1.5)})

    chain([(h3, bs[h3]), (inc_wave, bs[inc_wave]), (set_zsp, bs[set_zsp]),
           (inc_tg, bs[inc_tg]), (r_kills, bs[r_kills]),
           (r_sp, bs[r_sp]), (w_wave, bs[w_wave])])

    return bs

# ============================================================
#  PLAYER
# ============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === flag: init ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    cm0 = gen(); bs[cm0] = mk("looks_costume",
        fields={"COSTUME": ["alive", None]}, shadow=True)
    swc0 = gen(); bs[swc0] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm0]})
    bs[cm0]["parent"] = swc0
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # forever: aim + move
    # aim: point towards mouse-pointer
    mp_menu = gen(); bs[mp_menu] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["_mouse_", None]}, shadow=True)
    point_m = gen(); bs[point_m] = mk("motion_pointtowards",
        inputs={"TOWARDS": [1, mp_menu]})
    bs[mp_menu]["parent"] = point_m

    # Up key check
    up_menu = gen(); bs[up_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["up arrow", None]}, shadow=True)
    up_press = gen(); bs[up_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, up_menu]})
    bs[up_menu]["parent"] = up_press
    w_menu = gen(); bs[w_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["w", None]}, shadow=True)
    w_press = gen(); bs[w_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["w", None]}, shadow=True)
    w_press_b = gen(); bs[w_press_b] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, w_menu]})
    bs[w_menu]["parent"] = w_press_b
    up_or_w = bool_op("operator_or", up_press, w_press_b)
    chy_up = gen(); bs[chy_up] = mk("motion_changeyby", inputs={"DY": num(3)})
    if_up = gen(); bs[if_up] = mk("control_if",
        inputs={"CONDITION": [2, up_or_w], "SUBSTACK": [2, chy_up]})
    bs[up_or_w]["parent"] = if_up
    bs[chy_up]["parent"] = if_up

    # Down key check
    dn_menu = gen(); bs[dn_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["down arrow", None]}, shadow=True)
    dn_press = gen(); bs[dn_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, dn_menu]})
    bs[dn_menu]["parent"] = dn_press
    s_menu = gen(); bs[s_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["s", None]}, shadow=True)
    s_press = gen(); bs[s_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, s_menu]})
    bs[s_menu]["parent"] = s_press
    dn_or_s = bool_op("operator_or", dn_press, s_press)
    chy_dn = gen(); bs[chy_dn] = mk("motion_changeyby", inputs={"DY": num(-3)})
    if_dn = gen(); bs[if_dn] = mk("control_if",
        inputs={"CONDITION": [2, dn_or_s], "SUBSTACK": [2, chy_dn]})
    bs[dn_or_s]["parent"] = if_dn
    bs[chy_dn]["parent"] = if_dn

    # Left
    l_menu = gen(); bs[l_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    l_press = gen(); bs[l_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, l_menu]})
    bs[l_menu]["parent"] = l_press
    a_menu = gen(); bs[a_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["a", None]}, shadow=True)
    a_press = gen(); bs[a_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, a_menu]})
    bs[a_menu]["parent"] = a_press
    l_or_a = bool_op("operator_or", l_press, a_press)
    chx_l = gen(); bs[chx_l] = mk("motion_changexby", inputs={"DX": num(-3)})
    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION": [2, l_or_a], "SUBSTACK": [2, chx_l]})
    bs[l_or_a]["parent"] = if_l
    bs[chx_l]["parent"] = if_l

    # Right
    r_menu = gen(); bs[r_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    r_press = gen(); bs[r_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, r_menu]})
    bs[r_menu]["parent"] = r_press
    d_menu = gen(); bs[d_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["d", None]}, shadow=True)
    d_press = gen(); bs[d_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, d_menu]})
    bs[d_menu]["parent"] = d_press
    r_or_d = bool_op("operator_or", r_press, d_press)
    chx_r = gen(); bs[chx_r] = mk("motion_changexby", inputs={"DX": num(3)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION": [2, r_or_d], "SUBSTACK": [2, chx_r]})
    bs[r_or_d]["parent"] = if_r
    bs[chx_r]["parent"] = if_r

    # clamp x/y
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    c_xhi = cmp_op("operator_gt", xp1, 230)
    sx_hi = gen(); bs[sx_hi] = mk("motion_setx", inputs={"X": num(230)})
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, c_xhi], "SUBSTACK": [2, sx_hi]})
    bs[c_xhi]["parent"] = if_xhi
    bs[sx_hi]["parent"] = if_xhi

    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_xlo = cmp_op("operator_lt", xp2, -230)
    sx_lo = gen(); bs[sx_lo] = mk("motion_setx", inputs={"X": num(-230)})
    if_xlo = gen(); bs[if_xlo] = mk("control_if",
        inputs={"CONDITION": [2, c_xlo], "SUBSTACK": [2, sx_lo]})
    bs[c_xlo]["parent"] = if_xlo
    bs[sx_lo]["parent"] = if_xlo

    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    c_yhi = cmp_op("operator_gt", yp1, 170)
    sy_hi = gen(); bs[sy_hi] = mk("motion_sety", inputs={"Y": num(170)})
    if_yhi = gen(); bs[if_yhi] = mk("control_if",
        inputs={"CONDITION": [2, c_yhi], "SUBSTACK": [2, sy_hi]})
    bs[c_yhi]["parent"] = if_yhi
    bs[sy_hi]["parent"] = if_yhi

    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    c_ylo = cmp_op("operator_lt", yp2, -170)
    sy_lo = gen(); bs[sy_lo] = mk("motion_sety", inputs={"Y": num(-170)})
    if_ylo = gen(); bs[if_ylo] = mk("control_if",
        inputs={"CONDITION": [2, c_ylo], "SUBSTACK": [2, sy_lo]})
    bs[c_ylo]["parent"] = if_ylo
    bs[sy_lo]["parent"] = if_ylo

    # decrement invulnerability
    inv_v = vrep("무적시간", V_INV)
    c_inv = cmp_op("operator_gt", inv_v, 0)
    dec_inv = gen(); bs[dec_inv] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["무적시간", V_INV]})
    if_inv = gen(); bs[if_inv] = mk("control_if",
        inputs={"CONDITION": [2, c_inv], "SUBSTACK": [2, dec_inv]})
    bs[c_inv]["parent"] = if_inv
    bs[dec_inv]["parent"] = if_inv

    # forever body
    chain([(point_m, bs[point_m]),
           (if_up, bs[if_up]), (if_dn, bs[if_dn]),
           (if_l, bs[if_l]), (if_r, bs[if_r]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (if_inv, bs[if_inv])])
    forever = gen(); bs[forever] = mk("control_forever",
        inputs={"SUBSTACK": [2, point_m]})
    bs[point_m]["parent"] = forever

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (swc0, bs[swc0]), (front, bs[front]),
           (forever, bs[forever])])

    # === flag (separate script): fire input forever (rate-limited) ===
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    md = gen(); bs[md] = mk("sensing_mousedown")
    sp_menu = gen(); bs[sp_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sp_press = gen(); bs[sp_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, sp_menu]})
    bs[sp_menu]["parent"] = sp_press
    fire_input = bool_op("operator_or", md, sp_press)

    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)
    cond_can_fire = bool_op("operator_and", fire_input, cond_play)

    bm_fire = gen(); bs[bm_fire] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["사격", BR_FIRE]}, shadow=True)
    bc_fire = gen(); bs[bc_fire] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_fire]})
    bs[bm_fire]["parent"] = bc_fire

    w_fire = gen(); bs[w_fire] = mk("control_wait",
        inputs={"DURATION": num(0.18)})
    chain([(bc_fire, bs[bc_fire]), (w_fire, bs[w_fire])])

    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, cond_can_fire], "SUBSTACK": [2, bc_fire]})
    bs[cond_can_fire]["parent"] = if_fire
    bs[bc_fire]["parent"] = if_fire

    fire_forever = gen(); bs[fire_forever] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_fire]})
    bs[if_fire]["parent"] = fire_forever

    chain([(h2, bs[h2]), (fire_forever, bs[fire_forever])])

    # === on 사격 received: set bullet pos+dir + create clone of 총알 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=400, y=400,
        fields={"BROADCAST_OPTION": ["사격", BR_FIRE]})

    xp_s = gen(); bs[xp_s] = mk("motion_xposition")
    set_bx = gen(); bs[set_bx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xp_s)}, fields={"VARIABLE": ["총알X", V_BX]})
    bs[xp_s]["parent"] = set_bx

    yp_s = gen(); bs[yp_s] = mk("motion_yposition")
    set_by = gen(); bs[set_by] = mk("data_setvariableto",
        inputs={"VALUE": slot(yp_s)}, fields={"VARIABLE": ["총알Y", V_BY]})
    bs[yp_s]["parent"] = set_by

    dir_s = gen(); bs[dir_s] = mk("motion_direction")
    set_bdir = gen(); bs[set_bdir] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_s)}, fields={"VARIABLE": ["총알방향", V_BDIR]})
    bs[dir_s]["parent"] = set_bdir

    # pop sound
    pitch_fire = gen(); bs[pitch_fire] = mk("sound_seteffectto",
        inputs={"VALUE": num(150)}, fields={"EFFECT": ["PITCH", None]})
    snm_fire = gen(); bs[snm_fire] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_fire = gen(); bs[snd_fire] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_fire]})
    bs[snm_fire]["parent"] = snd_fire

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["총알", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h3, bs[h3]), (set_bx, bs[set_bx]), (set_by, bs[set_by]),
           (set_bdir, bs[set_bdir]), (pitch_fire, bs[pitch_fire]),
           (snd_fire, bs[snd_fire]), (cclone, bs[cclone])])

    return bs

# ============================================================
#  BULLET
# ============================================================
def build_bullet_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)
    bx_v = vrep("총알X", V_BX); by_v = vrep("총알Y", V_BY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g

    bdir_v = vrep("총알방향", V_BDIR)
    point_b = gen(); bs[point_b] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(bdir_v)})
    bs[bdir_v]["parent"] = point_b

    show = gen(); bs[show] = mk("looks_show")

    # repeat until out-of-bounds OR touching 좀비
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(10)})
    w_iter = gen(); bs[w_iter] = mk("control_wait",
        inputs={"DURATION": num(0.02)})
    chain([(mv, bs[mv]), (w_iter, bs[w_iter])])

    xp = gen(); bs[xp] = mk("motion_xposition")
    cx_hi = cmp_op("operator_gt", xp, 240)
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cx_lo = cmp_op("operator_lt", xp_b, -240)
    cx_out = bool_op("operator_or", cx_hi, cx_lo)
    yp = gen(); bs[yp] = mk("motion_yposition")
    cy_hi = cmp_op("operator_gt", yp, 180)
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cy_lo = cmp_op("operator_lt", yp_b, -180)
    cy_out = bool_op("operator_or", cy_hi, cy_lo)
    c_xy_out = bool_op("operator_or", cx_out, cy_out)

    tm_z = gen(); bs[tm_z] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["좀비", None]}, shadow=True)
    tc_z = gen(); bs[tc_z] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_z]})
    bs[tm_z]["parent"] = tc_z

    c_stop = bool_op("operator_or", c_xy_out, tc_z)

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_stop], "SUBSTACK": [2, mv]})
    bs[c_stop]["parent"] = rep_until
    bs[mv]["parent"] = rep_until

    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (point_b, bs[point_b]),
           (show, bs[show]), (rep_until, bs[rep_until]),
           (hi2, bs[hi2]), (delc, bs[delc])])

    return bs

# ============================================================
#  ZOMBIE
# ============================================================
def build_zombie_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    cm0 = gen(); bs[cm0] = mk("looks_costume",
        fields={"COSTUME": ["walk1", None]}, shadow=True)
    swc0 = gen(); bs[swc0] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm0]})
    bs[cm0]["parent"] = swc0
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (swc0, bs[swc0])])

    # on 좀비스폰 → create clone
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["좀비스폰", BR_SPAWN]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(h2, bs[h2]), (cclone, bs[cclone])])

    # clone start
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)
    sx_v = vrep("스폰X", V_SX); sy_v = vrep("스폰Y", V_SY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(sx_v), "Y": slot(sy_v)})
    bs[sx_v]["parent"] = g; bs[sy_v]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")
    cm1 = gen(); bs[cm1] = mk("looks_costume",
        fields={"COSTUME": ["walk1", None]}, shadow=True)
    swc1 = gen(); bs[swc1] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm1]})
    bs[cm1]["parent"] = swc1

    # repeat until (touching 총알) OR ((touching 플레이어) AND 무적시간=0)
    # body: point towards 플레이어, move 좀비속도 steps, sometimes next costume, wait
    mp_menu = gen(); bs[mp_menu] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["플레이어", None]}, shadow=True)
    point_p = gen(); bs[point_p] = mk("motion_pointtowards",
        inputs={"TOWARDS": [1, mp_menu]})
    bs[mp_menu]["parent"] = point_p

    zsp_v = vrep("좀비속도", V_ZSPEED)
    mv = gen(); bs[mv] = mk("motion_movesteps",
        inputs={"STEPS": slot(zsp_v)})
    bs[zsp_v]["parent"] = mv

    # animation: pick random 1..6, if =1 → next costume
    r_anim = op("operator_random", 1, 6, key1="FROM", key2="TO")
    c_anim = cmp_op("operator_equals", r_anim, 1)
    nc = gen(); bs[nc] = mk("looks_nextcostume")
    if_anim = gen(); bs[if_anim] = mk("control_if",
        inputs={"CONDITION": [2, c_anim], "SUBSTACK": [2, nc]})
    bs[c_anim]["parent"] = if_anim
    bs[nc]["parent"] = if_anim

    w_iter = gen(); bs[w_iter] = mk("control_wait",
        inputs={"DURATION": num(0.04)})

    chain([(point_p, bs[point_p]), (mv, bs[mv]),
           (if_anim, bs[if_anim]), (w_iter, bs[w_iter])])

    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["총알", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b]})
    bs[tm_b]["parent"] = tc_b

    tm_p = gen(); bs[tm_p] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["플레이어", None]}, shadow=True)
    tc_p = gen(); bs[tc_p] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_p]})
    bs[tm_p]["parent"] = tc_p

    inv_v = vrep("무적시간", V_INV)
    cond_no_inv = cmp_op("operator_equals", inv_v, 0)
    cond_hit_p = bool_op("operator_and", tc_p, cond_no_inv)
    cond_stop = bool_op("operator_or", tc_b, cond_hit_p)

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_stop], "SUBSTACK": [2, point_p]})
    bs[cond_stop]["parent"] = rep_until
    bs[point_p]["parent"] = rep_until

    # post-loop: figure out which case
    tm_b2 = gen(); bs[tm_b2] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["총알", None]}, shadow=True)
    tc_b2 = gen(); bs[tc_b2] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b2]})
    bs[tm_b2]["parent"] = tc_b2

    # if touching 총알: kill flow
    inc_kills = gen(); bs[inc_kills] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["처치수", V_KILLS]})
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(10)}, fields={"VARIABLE": ["점수", V_SCORE]})
    pitch_hit = gen(); bs[pitch_hit] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["PITCH", None]})
    snm_h = gen(); bs[snm_h] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_h = gen(); bs[snd_h] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_h]})
    bs[snm_h]["parent"] = snd_h
    cm_dead = gen(); bs[cm_dead] = mk("looks_costume",
        fields={"COSTUME": ["dead", None]}, shadow=True)
    swc_dead = gen(); bs[swc_dead] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_dead]})
    bs[cm_dead]["parent"] = swc_dead
    w_dead = gen(); bs[w_dead] = mk("control_wait",
        inputs={"DURATION": num(0.18)})

    # 처치수 >= 웨이브목표 → broadcast 다음웨이브 + reset 처치수 inside next-wave handler
    kills_v = vrep("처치수", V_KILLS)
    tg_v = vrep("웨이브목표", V_TARGET)
    cond_lt = cmp_op("operator_lt", kills_v, tg_v)
    not_lt = gen(); bs[not_lt] = mk("operator_not",
        inputs={"OPERAND": [2, cond_lt]})
    bs[cond_lt]["parent"] = not_lt

    bm_next = gen(); bs[bm_next] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["다음웨이브", BR_NEXT]}, shadow=True)
    bc_next = gen(); bs[bc_next] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_next]})
    bs[bm_next]["parent"] = bc_next

    if_next = gen(); bs[if_next] = mk("control_if",
        inputs={"CONDITION": [2, not_lt], "SUBSTACK": [2, bc_next]})
    bs[not_lt]["parent"] = if_next
    bs[bc_next]["parent"] = if_next

    chain([(inc_kills, bs[inc_kills]), (inc_score, bs[inc_score]),
           (pitch_hit, bs[pitch_hit]), (snd_h, bs[snd_h]),
           (swc_dead, bs[swc_dead]), (w_dead, bs[w_dead]),
           (if_next, bs[if_next])])

    if_killed = gen(); bs[if_killed] = mk("control_if_else",
        inputs={"CONDITION": [2, tc_b2],
                "SUBSTACK": [2, inc_kills]})  # SUBSTACK2 wired below
    bs[tc_b2]["parent"] = if_killed
    bs[inc_kills]["parent"] = if_killed

    # ELSE branch: damage flow
    dec_life = gen(); bs[dec_life] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["라이프", V_LIFE]})
    set_inv = gen(); bs[set_inv] = mk("data_setvariableto",
        inputs={"VALUE": num(20)}, fields={"VARIABLE": ["무적시간", V_INV]})
    pitch_dmg = gen(); bs[pitch_dmg] = mk("sound_seteffectto",
        inputs={"VALUE": num(-250)}, fields={"EFFECT": ["PITCH", None]})
    snm_d = gen(); bs[snm_d] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_d = gen(); bs[snd_d] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_d]})
    bs[snm_d]["parent"] = snd_d

    # if 라이프 <= 0 → 게임상태 = 0
    life_v = vrep("라이프", V_LIFE)
    cond_dead = cmp_op("operator_lt", life_v, 1)
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, set_state0]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state0]["parent"] = if_dead

    chain([(dec_life, bs[dec_life]), (set_inv, bs[set_inv]),
           (pitch_dmg, bs[pitch_dmg]), (snd_d, bs[snd_d]),
           (if_dead, bs[if_dead])])

    # wire ELSE substack
    bs[if_killed]["inputs"]["SUBSTACK2"] = [2, dec_life]
    bs[dec_life]["parent"] = if_killed

    hide_after = gen(); bs[hide_after] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (show, bs[show]), (swc1, bs[swc1]),
           (rep_until, bs[rep_until]), (if_killed, bs[if_killed]),
           (hide_after, bs[hide_after]), (delc, bs[delc])])

    return bs

# ============================================================
#  GAME OVER
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
#  ASSEMBLE
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f: f.write(BG_SVG)
    pl_md5 = md5_bytes(PLAYER_SVG.encode("utf-8"))
    with open(f"{WORK}/{pl_md5}.svg", "w", encoding="utf-8") as f: f.write(PLAYER_SVG)
    ph_md5 = md5_bytes(PLAYER_HIT_SVG.encode("utf-8"))
    with open(f"{WORK}/{ph_md5}.svg", "w", encoding="utf-8") as f: f.write(PLAYER_HIT_SVG)
    bu_md5 = md5_bytes(BULLET_SVG.encode("utf-8"))
    with open(f"{WORK}/{bu_md5}.svg", "w", encoding="utf-8") as f: f.write(BULLET_SVG)
    z1_md5 = md5_bytes(ZOMBIE1_SVG.encode("utf-8"))
    with open(f"{WORK}/{z1_md5}.svg", "w", encoding="utf-8") as f: f.write(ZOMBIE1_SVG)
    z2_md5 = md5_bytes(ZOMBIE2_SVG.encode("utf-8"))
    with open(f"{WORK}/{z2_md5}.svg", "w", encoding="utf-8") as f: f.write(ZOMBIE2_SVG)
    zd_md5 = md5_bytes(ZOMBIE_DEAD_SVG.encode("utf-8"))
    with open(f"{WORK}/{zd_md5}.svg", "w", encoding="utf-8") as f: f.write(ZOMBIE_DEAD_SVG)
    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f: f.write(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    player_blocks   = build_player_blocks()
    bullet_blocks   = build_bullet_blocks()
    zombie_blocks   = build_zombie_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 48000, "sampleCount": 1123,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:   ["점수", 0],
            V_LIFE:    ["라이프", 3],
            V_WAVE:    ["웨이브", 1],
            V_STATE:   ["게임상태", 1],
            V_KILLS:   ["처치수", 0],
            V_TARGET:  ["웨이브목표", 5],
            V_ZSPEED:  ["좀비속도", 1.4],
            V_SX:      ["스폰X", 0],
            V_SY:      ["스폰Y", 0],
            V_BX:      ["총알X", 0],
            V_BY:      ["총알Y", 0],
            V_BDIR:    ["총알방향", 90],
            V_INV:     ["무적시간", 0],
            V_SPAWNED: ["스폰수", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "좀비스폰",
            BR_NEXT:  "다음웨이브",
            BR_FIRE:  "사격",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "풀밭", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    player = {
        "isStage": False, "name": "플레이어",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": player_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "alive", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pl_md5, "md5ext": f"{pl_md5}.svg",
             "rotationCenterX": 25, "rotationCenterY": 25},
            {"name": "hit", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ph_md5, "md5ext": f"{ph_md5}.svg",
             "rotationCenterX": 25, "rotationCenterY": 25},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    bullet = {
        "isStage": False, "name": "총알",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bullet", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bu_md5, "md5ext": f"{bu_md5}.svg",
            "rotationCenterX": 7, "rotationCenterY": 7
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    zombie = {
        "isStage": False, "name": "좀비",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": zombie_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "walk1", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": z1_md5, "md5ext": f"{z1_md5}.svg",
             "rotationCenterX": 25, "rotationCenterY": 25},
            {"name": "walk2", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": z2_md5, "md5ext": f"{z2_md5}.svg",
             "rotationCenterX": 25, "rotationCenterY": 25},
            {"name": "dead", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": zd_md5, "md5ext": f"{zd_md5}.svg",
             "rotationCenterX": 25, "rotationCenterY": 25},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    gameover = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": gameover_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": go_md5, "md5ext": f"{go_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 80
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
         "visible": True, "sliderMin": 0, "sliderMax": 1000, "isDiscrete": True},
        {"id": V_LIFE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라이프"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 5, "isDiscrete": True},
        {"id": V_WAVE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "웨이브"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_KILLS, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "처치수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, player, bullet, zombie, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "zombie-shooter-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)
    print(f"wrote {OUTPUT}")
    print(f"  stage:    {len(stage_blocks)} blocks")
    print(f"  player:   {len(player_blocks)} blocks")
    print(f"  bullet:   {len(bullet_blocks)} blocks")
    print(f"  zombie:   {len(zombie_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(player_blocks) + len(bullet_blocks)
             + len(zombie_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
