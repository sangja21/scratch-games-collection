#!/usr/bin/env python3
"""Station Docking — 4-thruster inertial spaceship docks gently to a space station."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "우주정거장_도킹.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: deep space + stars --------
random.seed(31)
stars = []
for _ in range(140):
    x = random.randint(0, 480); y = random.randint(0, 360)
    r = random.choice([0.5, 0.8, 1.0, 1.3, 1.6])
    op = random.uniform(0.45, 0.95)
    stars.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#FFFFFF" opacity="{op:.2f}"/>')
STARS = "\n    ".join(stars)

nebulae = []
for _ in range(4):
    cx = random.randint(40, 440); cy = random.randint(40, 320)
    rx = random.randint(50, 100); ry = random.randint(40, 80)
    color = random.choice(["#1A2E66", "#3A1A66", "#2C1A4F", "#1E3A52"])
    nebulae.append(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
        f'fill="{color}" opacity="0.22"/>'
    )
NEB = "\n    ".join(nebulae)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#04060F"/>
  <g>
    {NEB}
  </g>
  <g>
    {STARS}
  </g>
</svg>"""

# -------- Spaceship (top-down — small triangular shuttle with 4 small thrusters) --------
SHIP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <!-- 4 thruster nubs (top/bottom/left/right) -->
  <rect x="22" y="2"  width="4" height="6" fill="#FF8A00" stroke="#37474F" stroke-width="0.8"/>
  <rect x="22" y="40" width="4" height="6" fill="#FF8A00" stroke="#37474F" stroke-width="0.8"/>
  <rect x="2"  y="22" width="6" height="4" fill="#FF8A00" stroke="#37474F" stroke-width="0.8"/>
  <rect x="40" y="22" width="6" height="4" fill="#FF8A00" stroke="#37474F" stroke-width="0.8"/>
  <!-- main hull (round body) -->
  <circle cx="24" cy="24" r="14" fill="#ECEFF1" stroke="#37474F" stroke-width="1.8"/>
  <!-- inner ring -->
  <circle cx="24" cy="24" r="9" fill="#90CAF9" stroke="#1976D2" stroke-width="1.2"/>
  <!-- cockpit dot -->
  <circle cx="24" cy="24" r="4" fill="#0D47A1" stroke="#FFFFFF" stroke-width="1"/>
  <!-- forward marker (right side = approach side) -->
  <polygon points="38,24 32,21 32,27" fill="#FFEB3B" stroke="#37474F" stroke-width="0.8"/>
</svg>"""

# -------- Station (large with docking port on left side) --------
STATION_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="100" viewBox="0 0 120 100">
  <!-- solar panels (top/bottom) -->
  <rect x="50" y="2"  width="20" height="14" fill="#1565C0" stroke="#0D47A1" stroke-width="1.4"/>
  <rect x="50" y="84" width="20" height="14" fill="#1565C0" stroke="#0D47A1" stroke-width="1.4"/>
  <line x1="50" y1="9"  x2="70" y2="9"  stroke="#FFFFFF" stroke-width="0.6"/>
  <line x1="50" y1="91" x2="70" y2="91" stroke="#FFFFFF" stroke-width="0.6"/>
  <line x1="60" y1="2"  x2="60" y2="16" stroke="#FFFFFF" stroke-width="0.6"/>
  <line x1="60" y1="84" x2="60" y2="98" stroke="#FFFFFF" stroke-width="0.6"/>
  <!-- truss connecting panels -->
  <line x1="60" y1="16" x2="60" y2="30" stroke="#90A4AE" stroke-width="3"/>
  <line x1="60" y1="70" x2="60" y2="84" stroke="#90A4AE" stroke-width="3"/>
  <!-- main hull -->
  <rect x="38" y="30" width="60" height="40" rx="6"
        fill="#B0BEC5" stroke="#37474F" stroke-width="2"/>
  <rect x="44" y="36" width="48" height="28" rx="3"
        fill="#CFD8DC" stroke="#546E7A" stroke-width="1"/>
  <!-- windows -->
  <circle cx="56" cy="50" r="3" fill="#0D47A1" stroke="#FFFFFF" stroke-width="0.8"/>
  <circle cx="68" cy="50" r="3" fill="#0D47A1" stroke="#FFFFFF" stroke-width="0.8"/>
  <circle cx="80" cy="50" r="3" fill="#0D47A1" stroke="#FFFFFF" stroke-width="0.8"/>
  <!-- docking port (LEFT side) -->
  <rect x="22" y="42" width="18" height="16" fill="#FFEB3B" stroke="#F57F17" stroke-width="2"/>
  <rect x="26" y="46" width="10" height="8" fill="#37474F" stroke="#000000" stroke-width="1"/>
  <line x1="22" y1="50" x2="40" y2="50" stroke="#F57F17" stroke-width="0.8"/>
  <line x1="31" y1="42" x2="31" y2="58" stroke="#F57F17" stroke-width="0.8"/>
</svg>"""

# -------- Docked banner --------
DOCK_OK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="320" height="120" viewBox="0 0 320 120">
  <rect x="5" y="5" width="310" height="110" rx="14"
        fill="#0D47A1" opacity="0.95"
        stroke="#FFEB3B" stroke-width="4"/>
  <text x="160" y="58" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="38" font-weight="bold">DOCKED!</text>
  <text x="160" y="92" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="16">정확하게 도킹 성공</text>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#EF5350" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#EF5350" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">너무 빠르게 충돌했어요</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#FFCDD2" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭</text>
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

# ============================================================
#  IDs
# ============================================================
V_SCORE = "varScore01"
V_ROUND = "varRound02"
V_STATE = "varState03"
V_FUEL  = "varFuel04"
V_SVX   = "varShipVX05"
V_SVY   = "varShipVY06"
V_STY   = "varStY07"

BR_START   = "brStart01"
BR_ROUND   = "brRound02"
BR_DOCKED  = "brDocked03"
BR_CRASH   = "brCrash04"

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

def abs_of(bs, val_block_id):
    bid = gen()
    bs[bid] = mk("operator_mathop", inputs={"NUM": slot(val_block_id)},
                 fields={"OPERATOR": ["abs", None]})
    bs[val_block_id]["parent"] = bid
    return bid

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- when flag clicked: init + broadcast 게임시작 ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = []
    for var_pair, val in [
        (("점수", V_SCORE), 0),
        (("라운드", V_ROUND), 1),
        (("게임상태", V_STATE), 1),
        (("연료", V_FUEL), 100),
        (("우주선VX", V_SVX), 0),
        (("우주선VY", V_SVY), 0),
        (("정거장Y", V_STY), 0),
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

    # --- on 게임시작: broadcast 라운드시작 ---
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    bm_r = gen(); bs[bm_r] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]}, shadow=True)
    bc_r = gen(); bs[bc_r] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_r]})
    bs[bm_r]["parent"] = bc_r
    chain([(h2, bs[h2]), (bc_r, bs[bc_r])])

    # --- on 라운드시작: reset VX/VY, fuel=100, 정거장Y = random(-100..100) ---
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=600,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]})

    rs_vx = gen(); bs[rs_vx] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    rs_vy = gen(); bs[rs_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VY", V_SVY]})
    rs_fuel = gen(); bs[rs_fuel] = mk("data_setvariableto",
        inputs={"VALUE": num(100)}, fields={"VARIABLE": ["연료", V_FUEL]})

    sty_rand = gen(); bs[sty_rand] = mk("operator_random",
        inputs={"FROM": num(-100), "TO": num(100)})
    set_sty = gen(); bs[set_sty] = mk("data_setvariableto",
        inputs={"VALUE": slot(sty_rand)}, fields={"VARIABLE": ["정거장Y", V_STY]})
    bs[sty_rand]["parent"] = set_sty

    chain([(h3, bs[h3]), (rs_vx, bs[rs_vx]), (rs_vy, bs[rs_vy]),
           (rs_fuel, bs[rs_fuel]), (set_sty, bs[set_sty])])

    # --- on 도킹성공: score += 100 + 연료, round +=1, wait 1.5, 라운드시작 ---
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=300, y=600,
        fields={"BROADCAST_OPTION": ["도킹성공", BR_DOCKED]})

    fuel_v = vrep("연료", V_FUEL)
    score_add = op("operator_add", 100, fuel_v)
    chg_score = gen(); bs[chg_score] = mk("data_changevariableby",
        inputs={"VALUE": slot(score_add)}, fields={"VARIABLE": ["점수", V_SCORE]})
    bs[score_add]["parent"] = chg_score

    inc_round = gen(); bs[inc_round] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})

    w_d = gen(); bs[w_d] = mk("control_wait", inputs={"DURATION": num(1.5)})

    bm_r2 = gen(); bs[bm_r2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]}, shadow=True)
    bc_r2 = gen(); bs[bc_r2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_r2]})
    bs[bm_r2]["parent"] = bc_r2

    chain([(h4, bs[h4]), (chg_score, bs[chg_score]),
           (inc_round, bs[inc_round]), (w_d, bs[w_d]), (bc_r2, bs[bc_r2])])

    return bs

# ============================================================
#  SHIP (4-directional thrusters, inertia, dock/crash detection)
# ============================================================
def build_ship_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- flag: init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(-180), "Y": num(0)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["don't rotate", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # --- on 라운드시작: re-position to (-180, 0) ---
    hR = gen(); bs[hR] = mk("event_whenbroadcastreceived", top=True, x=20, y=800,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]})
    gR = gen(); bs[gR] = mk("motion_gotoxy", inputs={"X": num(-180), "Y": num(0)})
    chain([(hR, bs[hR]), (gR, bs[gR])])

    # ---- helper: build one direction thruster if (key, dx, dy) ----
    # Returns (if_block_id) -- "if key_pressed AND fuel>0 AND state=1 → VX/VY += d, fuel -= 1"
    def build_thrust_if(key_name, var_pair, var_id, delta):
        k_menu = gen(); bs[k_menu] = mk("sensing_keyoptions",
            fields={"KEY_OPTION": [key_name, None]}, shadow=True)
        k_press = gen(); bs[k_press] = mk("sensing_keypressed",
            inputs={"KEY_OPTION": [1, k_menu]})
        bs[k_menu]["parent"] = k_press

        fuel_v = vrep("연료", V_FUEL)
        cond_fuel = cmp_op("operator_gt", fuel_v, 0)
        state_v = vrep("게임상태", V_STATE)
        cond_state = cmp_op("operator_equals", state_v, 1)
        cond_a = bool_op("operator_and", k_press, cond_fuel)
        cond_all = bool_op("operator_and", cond_a, cond_state)

        chg_v = gen(); bs[chg_v] = mk("data_changevariableby",
            inputs={"VALUE": num(delta)}, fields={"VARIABLE": list(var_pair)})
        dec_fuel = gen(); bs[dec_fuel] = mk("data_changevariableby",
            inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["연료", V_FUEL]})
        chain([(chg_v, bs[chg_v]), (dec_fuel, bs[dec_fuel])])

        if_blk = gen(); bs[if_blk] = mk("control_if",
            inputs={"CONDITION": [2, cond_all], "SUBSTACK": [2, chg_v]})
        bs[cond_all]["parent"] = if_blk
        bs[chg_v]["parent"] = if_blk
        return if_blk

    if_up    = build_thrust_if("up arrow",    ("우주선VY", V_SVY), V_SVY,  0.3)
    if_down  = build_thrust_if("down arrow",  ("우주선VY", V_SVY), V_SVY, -0.3)
    if_right = build_thrust_if("right arrow", ("우주선VX", V_SVX), V_SVX,  0.3)
    if_left  = build_thrust_if("left arrow",  ("우주선VX", V_SVX), V_SVX, -0.3)

    # --- VX clamp ±4.5 ---
    vx_a = vrep("우주선VX", V_SVX)
    c_vxhi = cmp_op("operator_gt", vx_a, 4.5)
    set_vxhi = gen(); bs[set_vxhi] = mk("data_setvariableto",
        inputs={"VALUE": num(4.5)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    if_vxhi = gen(); bs[if_vxhi] = mk("control_if",
        inputs={"CONDITION": [2, c_vxhi], "SUBSTACK": [2, set_vxhi]})
    bs[c_vxhi]["parent"] = if_vxhi
    bs[set_vxhi]["parent"] = if_vxhi

    vx_b = vrep("우주선VX", V_SVX)
    c_vxlo = cmp_op("operator_lt", vx_b, -4.5)
    set_vxlo = gen(); bs[set_vxlo] = mk("data_setvariableto",
        inputs={"VALUE": num(-4.5)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    if_vxlo = gen(); bs[if_vxlo] = mk("control_if",
        inputs={"CONDITION": [2, c_vxlo], "SUBSTACK": [2, set_vxlo]})
    bs[c_vxlo]["parent"] = if_vxlo
    bs[set_vxlo]["parent"] = if_vxlo

    # --- VY clamp ±4.5 ---
    vy_a = vrep("우주선VY", V_SVY)
    c_vyhi = cmp_op("operator_gt", vy_a, 4.5)
    set_vyhi = gen(); bs[set_vyhi] = mk("data_setvariableto",
        inputs={"VALUE": num(4.5)}, fields={"VARIABLE": ["우주선VY", V_SVY]})
    if_vyhi = gen(); bs[if_vyhi] = mk("control_if",
        inputs={"CONDITION": [2, c_vyhi], "SUBSTACK": [2, set_vyhi]})
    bs[c_vyhi]["parent"] = if_vyhi
    bs[set_vyhi]["parent"] = if_vyhi

    vy_b = vrep("우주선VY", V_SVY)
    c_vylo = cmp_op("operator_lt", vy_b, -4.5)
    set_vylo = gen(); bs[set_vylo] = mk("data_setvariableto",
        inputs={"VALUE": num(-4.5)}, fields={"VARIABLE": ["우주선VY", V_SVY]})
    if_vylo = gen(); bs[if_vylo] = mk("control_if",
        inputs={"CONDITION": [2, c_vylo], "SUBSTACK": [2, set_vylo]})
    bs[c_vylo]["parent"] = if_vylo
    bs[set_vylo]["parent"] = if_vylo

    # --- change x by VX, change y by VY ---
    vx_c = vrep("우주선VX", V_SVX)
    chx = gen(); bs[chx] = mk("motion_changexby", inputs={"DX": slot(vx_c)})
    bs[vx_c]["parent"] = chx
    vy_c = vrep("우주선VY", V_SVY)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": slot(vy_c)})
    bs[vy_c]["parent"] = chy

    # --- wall stop: x > 235 → x=235, VX=0 ---
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    c_xhi = cmp_op("operator_gt", xp1, 235)
    sx_hi = gen(); bs[sx_hi] = mk("motion_setx", inputs={"X": num(235)})
    zvx_hi = gen(); bs[zvx_hi] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    chain([(sx_hi, bs[sx_hi]), (zvx_hi, bs[zvx_hi])])
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, c_xhi], "SUBSTACK": [2, sx_hi]})
    bs[c_xhi]["parent"] = if_xhi
    bs[sx_hi]["parent"] = if_xhi

    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_xlo = cmp_op("operator_lt", xp2, -235)
    sx_lo = gen(); bs[sx_lo] = mk("motion_setx", inputs={"X": num(-235)})
    zvx_lo = gen(); bs[zvx_lo] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    chain([(sx_lo, bs[sx_lo]), (zvx_lo, bs[zvx_lo])])
    if_xlo = gen(); bs[if_xlo] = mk("control_if",
        inputs={"CONDITION": [2, c_xlo], "SUBSTACK": [2, sx_lo]})
    bs[c_xlo]["parent"] = if_xlo
    bs[sx_lo]["parent"] = if_xlo

    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    c_yhi = cmp_op("operator_gt", yp1, 175)
    sy_hi = gen(); bs[sy_hi] = mk("motion_sety", inputs={"Y": num(175)})
    zvy_hi = gen(); bs[zvy_hi] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VY", V_SVY]})
    chain([(sy_hi, bs[sy_hi]), (zvy_hi, bs[zvy_hi])])
    if_yhi = gen(); bs[if_yhi] = mk("control_if",
        inputs={"CONDITION": [2, c_yhi], "SUBSTACK": [2, sy_hi]})
    bs[c_yhi]["parent"] = if_yhi
    bs[sy_hi]["parent"] = if_yhi

    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    c_ylo = cmp_op("operator_lt", yp2, -175)
    sy_lo = gen(); bs[sy_lo] = mk("motion_sety", inputs={"Y": num(-175)})
    zvy_lo = gen(); bs[zvy_lo] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VY", V_SVY]})
    chain([(sy_lo, bs[sy_lo]), (zvy_lo, bs[zvy_lo])])
    if_ylo = gen(); bs[if_ylo] = mk("control_if",
        inputs={"CONDITION": [2, c_ylo], "SUBSTACK": [2, sy_lo]})
    bs[c_ylo]["parent"] = if_ylo
    bs[sy_lo]["parent"] = if_ylo

    w_ctrl = gen(); bs[w_ctrl] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(if_up, bs[if_up]), (if_down, bs[if_down]),
           (if_right, bs[if_right]), (if_left, bs[if_left]),
           (if_vxhi, bs[if_vxhi]), (if_vxlo, bs[if_vxlo]),
           (if_vyhi, bs[if_vyhi]), (if_vylo, bs[if_vylo]),
           (chx, bs[chx]), (chy, bs[chy]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (w_ctrl, bs[w_ctrl])])

    fe_ctrl = gen(); bs[fe_ctrl] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_up]})
    bs[if_up]["parent"] = fe_ctrl

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (pd, bs[pd]), (front, bs[front]),
           (fe_ctrl, bs[fe_ctrl])])

    # --- forever (dock/crash detection) ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    tm_s = gen(); bs[tm_s] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["정거장", None]}, shadow=True)
    tc_s = gen(); bs[tc_s] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_s]})
    bs[tm_s]["parent"] = tc_s

    state_v2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v2, 1)
    cond_touch = bool_op("operator_and", tc_s, cond_play)

    # speed gentle check: |VX|<1.5 AND |VY|<1.5
    vx_d = vrep("우주선VX", V_SVX)
    abs_vx = abs_of(bs, vx_d)
    cond_vx_ok = cmp_op("operator_lt", abs_vx, 1.5)

    vy_d = vrep("우주선VY", V_SVY)
    abs_vy = abs_of(bs, vy_d)
    cond_vy_ok = cmp_op("operator_lt", abs_vy, 1.5)

    cond_gentle = bool_op("operator_and", cond_vx_ok, cond_vy_ok)

    # gentle branch (SUBSTACK): VX=0, VY=0, broadcast 도킹성공, sound, wait 1.5
    z_vx = gen(); bs[z_vx] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    z_vy = gen(); bs[z_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VY", V_SVY]})
    bm_d = gen(); bs[bm_d] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["도킹성공", BR_DOCKED]}, shadow=True)
    bc_d = gen(); bs[bc_d] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_d]})
    bs[bm_d]["parent"] = bc_d
    pit_ok = gen(); bs[pit_ok] = mk("sound_seteffectto",
        inputs={"VALUE": num(400)}, fields={"EFFECT": ["PITCH", None]})
    snm_ok = gen(); bs[snm_ok] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_ok = gen(); bs[snd_ok] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_ok]})
    bs[snm_ok]["parent"] = snd_ok
    w_ok = gen(); bs[w_ok] = mk("control_wait", inputs={"DURATION": num(1.5)})

    chain([(z_vx, bs[z_vx]), (z_vy, bs[z_vy]), (bc_d, bs[bc_d]),
           (pit_ok, bs[pit_ok]), (snd_ok, bs[snd_ok]), (w_ok, bs[w_ok])])

    # crash branch (SUBSTACK2): 게임상태=0, broadcast 충돌, sound
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bm_c = gen(); bs[bm_c] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["충돌", BR_CRASH]}, shadow=True)
    bc_c = gen(); bs[bc_c] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_c]})
    bs[bm_c]["parent"] = bc_c
    pit_c = gen(); bs[pit_c] = mk("sound_seteffectto",
        inputs={"VALUE": num(-400)}, fields={"EFFECT": ["PITCH", None]})
    snm_c = gen(); bs[snm_c] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_c = gen(); bs[snd_c] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_c]})
    bs[snm_c]["parent"] = snd_c

    chain([(set_state0, bs[set_state0]), (bc_c, bs[bc_c]),
           (pit_c, bs[pit_c]), (snd_c, bs[snd_c])])

    # if/else: gentle → dock | else → crash
    if_else = gen(); bs[if_else] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_gentle],
                "SUBSTACK":  [2, z_vx],
                "SUBSTACK2": [2, set_state0]})
    bs[cond_gentle]["parent"] = if_else
    bs[z_vx]["parent"] = if_else
    bs[set_state0]["parent"] = if_else

    # outer if: cond_touch → if_else
    if_touch = gen(); bs[if_touch] = mk("control_if",
        inputs={"CONDITION": [2, cond_touch], "SUBSTACK": [2, if_else]})
    bs[cond_touch]["parent"] = if_touch
    bs[if_else]["parent"] = if_touch

    w_det = gen(); bs[w_det] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_touch, bs[if_touch]), (w_det, bs[w_det])])
    fe_det = gen(); bs[fe_det] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_touch]})
    bs[if_touch]["parent"] = fe_det
    chain([(h2, bs[h2]), (fe_det, bs[fe_det])])

    # --- forever (fuel-out game-over watcher) ---
    # Simplified: fuel <= 0 AND state=1 → immediately game over (no speed check)
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)
    fuel_w = vrep("연료", V_FUEL)
    cond_f0 = cmp_op("operator_lt", fuel_w, 1)
    state_w = vrep("게임상태", V_STATE)
    cond_alive = cmp_op("operator_equals", state_w, 1)

    cond_stranded = bool_op("operator_and", cond_f0, cond_alive)

    set_state0_f = gen(); bs[set_state0_f] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bm_cf = gen(); bs[bm_cf] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["충돌", BR_CRASH]}, shadow=True)
    bc_cf = gen(); bs[bc_cf] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_cf]})
    bs[bm_cf]["parent"] = bc_cf

    chain([(set_state0_f, bs[set_state0_f]), (bc_cf, bs[bc_cf])])

    if_strand = gen(); bs[if_strand] = mk("control_if",
        inputs={"CONDITION": [2, cond_stranded], "SUBSTACK": [2, set_state0_f]})
    bs[cond_stranded]["parent"] = if_strand
    bs[set_state0_f]["parent"] = if_strand

    w_strand = gen(); bs[w_strand] = mk("control_wait", inputs={"DURATION": num(0.2)})
    chain([(if_strand, bs[if_strand]), (w_strand, bs[w_strand])])
    fe_strand = gen(); bs[fe_strand] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_strand]})
    bs[if_strand]["parent"] = fe_strand
    chain([(h3, bs[h3]), (fe_strand, bs[fe_strand])])

    return bs

# ============================================================
#  STATION
# ============================================================
def build_station_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # init
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["don't rotate", None]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(160), "Y": num(0)})
    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (rs, bs[rs]), (g0, bs[g0])])

    # on 라운드시작 → goto x=160, y=정거장Y
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]})
    sty_v = vrep("정거장Y", V_STY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(160), "Y": slot(sty_v)})
    bs[sty_v]["parent"] = g
    show2 = gen(); bs[show2] = mk("looks_show")
    chain([(h2, bs[h2]), (g, bs[g]), (show2, bs[show2])])

    return bs

# ============================================================
#  DOCK OK banner
# ============================================================
def build_dockok_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION": ["도킹성공", BR_DOCKED]})
    show = gen(); bs[show] = mk("looks_show")
    w = gen(); bs[w] = mk("control_wait", inputs={"DURATION": num(1.0)})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(h2, bs[h2]), (show, bs[show]), (w, bs[w]), (hi2, bs[hi2])])

    return bs

# ============================================================
#  GAME OVER banner
# ============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # --- flag clicked: hide, position, size, front, then loop: wait→show→wait→hide ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # wait until 게임상태=0 (game over happened)
    state_v2 = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", state_v2, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_zero]})
    bs[cond_zero]["parent"] = wait_over

    show = gen(); bs[show] = mk("looks_show")

    # wait until 게임상태=1 (game restarted)
    state_v3 = vrep("게임상태", V_STATE)
    cond_one_again = cmp_op("operator_equals", state_v3, 1)
    wait_restart = gen(); bs[wait_restart] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_one_again]})
    bs[cond_one_again]["parent"] = wait_restart

    hi2 = gen(); bs[hi2] = mk("looks_hide")

    chain([(wait_over, bs[wait_over]), (show, bs[show]),
           (wait_restart, bs[wait_restart]), (hi2, bs[hi2])])

    fe = gen(); bs[fe] = mk("control_forever", inputs={"SUBSTACK": [2, wait_over]})
    bs[wait_over]["parent"] = fe

    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (fe, bs[fe])])

    # --- on 충돌 broadcast: show game over banner immediately ---
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=300, y=20,
        fields={"BROADCAST_OPTION": ["충돌", BR_CRASH]})
    show2 = gen(); bs[show2] = mk("looks_show")
    chain([(h2, bs[h2]), (show2, bs[show2])])

    return bs

# ============================================================
#  ASSEMBLE
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f: f.write(BG_SVG)
    sh_md5 = md5_bytes(SHIP_SVG.encode("utf-8"))
    with open(f"{WORK}/{sh_md5}.svg", "w", encoding="utf-8") as f: f.write(SHIP_SVG)
    st_md5 = md5_bytes(STATION_SVG.encode("utf-8"))
    with open(f"{WORK}/{st_md5}.svg", "w", encoding="utf-8") as f: f.write(STATION_SVG)
    dk_md5 = md5_bytes(DOCK_OK_SVG.encode("utf-8"))
    with open(f"{WORK}/{dk_md5}.svg", "w", encoding="utf-8") as f: f.write(DOCK_OK_SVG)
    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f: f.write(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    ship_blocks     = build_ship_blocks()
    station_blocks  = build_station_blocks()
    dockok_blocks   = build_dockok_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE: ["점수", 0],
            V_ROUND: ["라운드", 1],
            V_STATE: ["게임상태", 1],
            V_FUEL:  ["연료", 100],
            V_SVX:   ["우주선VX", 0],
            V_SVY:   ["우주선VY", 0],
            V_STY:   ["정거장Y", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:  "게임시작",
            BR_ROUND:  "라운드시작",
            BR_DOCKED: "도킹성공",
            BR_CRASH:  "충돌",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "우주", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    ship = {
        "isStage": False, "name": "우주선",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ship_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "ship", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": sh_md5, "md5ext": f"{sh_md5}.svg",
            "rotationCenterX": 24, "rotationCenterY": 24
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": -180, "y": 0, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    station = {
        "isStage": False, "name": "정거장",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": station_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "station", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": st_md5, "md5ext": f"{st_md5}.svg",
            "rotationCenterX": 60, "rotationCenterY": 50
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": 160, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    dockok = {
        "isStage": False, "name": "도킹성공",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": dockok_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": dk_md5, "md5ext": f"{dk_md5}.svg",
            "rotationCenterX": 160, "rotationCenterY": 60
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": False,
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
            "rotationCenterX": 180, "rotationCenterY": 80
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10000, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_FUEL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "연료"}, "spriteName": None,
         "value": 100, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, ship, station, dockok, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "station-docking-builder"}
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
    print(f"  ship:     {len(ship_blocks)} blocks")
    print(f"  station:  {len(station_blocks)} blocks")
    print(f"  dockok:   {len(dockok_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(ship_blocks) + len(station_blocks)
             + len(dockok_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
