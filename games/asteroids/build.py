#!/usr/bin/env python3
"""Asteroids — classic inertial spaceship vs splitting asteroids (rotate + thrust + fire + screen wrap)."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "소행성.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: deep space + stars --------
random.seed(13)
stars = []
for _ in range(120):
    x = random.randint(0, 480); y = random.randint(0, 360)
    r = random.choice([0.6, 0.8, 1.0, 1.2, 1.6])
    op = random.uniform(0.45, 0.95)
    stars.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#FFFFFF" opacity="{op:.2f}"/>')
STARS = "\n    ".join(stars)

nebulae = []
for _ in range(5):
    cx = random.randint(30, 450); cy = random.randint(30, 330)
    rx = random.randint(40, 90);  ry = random.randint(30, 70)
    color = random.choice(["#2E1A47", "#3A1A66", "#1A2E66", "#2C1A4F"])
    nebulae.append(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
        f'fill="{color}" opacity="0.25"/>'
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

# -------- Spaceship (triangle pointing up = direction 0) --------
SHIP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="44" viewBox="0 0 40 44">
  <!-- thrust flame -->
  <polygon points="15,34 25,34 22,42 18,42" fill="#FF8A00" opacity="0.85"/>
  <polygon points="17,34 23,34 20,40" fill="#FFEB3B" opacity="0.9"/>
  <!-- body outline -->
  <polygon points="20,2 6,36 12,32 20,28 28,32 34,36" fill="#ECEFF1" stroke="#37474F" stroke-width="1.6"/>
  <!-- inner stripe -->
  <polygon points="20,8 14,30 26,30" fill="#90CAF9" stroke="#1976D2" stroke-width="1"/>
  <!-- cockpit -->
  <circle cx="20" cy="20" r="3" fill="#0D47A1" stroke="#FFFFFF" stroke-width="1"/>
  <!-- nose marker -->
  <polygon points="20,2 18,8 22,8" fill="#FFEB3B"/>
</svg>"""

# -------- Bullet (small bright pellet) --------
BULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="10" height="14" viewBox="0 0 10 14">
  <ellipse cx="5" cy="7" rx="4" ry="6" fill="#FFFFFF" stroke="#FFEB3B" stroke-width="1.4"/>
  <ellipse cx="5" cy="6" rx="2" ry="3" fill="#FFFDE7"/>
</svg>"""

# -------- Asteroids (big / med / small — irregular polygons) --------
ROCK_BIG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80">
  <polygon points="14,30 24,10 46,6 64,18 74,38 70,58 54,72 32,72 16,58 8,42"
           fill="#90A4AE" stroke="#37474F" stroke-width="2.2"/>
  <polygon points="22,30 32,22 44,24 38,36 28,40" fill="#78909C" stroke="#37474F" stroke-width="1"/>
  <polygon points="50,38 60,34 64,46 58,54" fill="#78909C" stroke="#37474F" stroke-width="1"/>
  <circle cx="32" cy="52" r="3" fill="#546E7A"/>
  <circle cx="56" cy="60" r="2.2" fill="#546E7A"/>
  <circle cx="20" cy="48" r="1.8" fill="#546E7A"/>
</svg>"""

ROCK_MED_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="10,24 20,8 36,6 50,16 54,34 46,50 30,54 14,46 6,34"
           fill="#A1B0B7" stroke="#37474F" stroke-width="2"/>
  <polygon points="18,24 26,18 36,22 30,32 22,32" fill="#7E8E94" stroke="#37474F" stroke-width="1"/>
  <circle cx="40" cy="38" r="2.4" fill="#546E7A"/>
  <circle cx="22" cy="42" r="1.6" fill="#546E7A"/>
</svg>"""

ROCK_SMALL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <polygon points="8,16 14,6 24,4 32,12 34,24 28,32 16,32 6,24"
           fill="#B0BEC5" stroke="#37474F" stroke-width="1.6"/>
  <polygon points="14,16 20,12 26,16 22,22 16,22" fill="#7E8E94" stroke="#37474F" stroke-width="0.8"/>
  <circle cx="24" cy="26" r="1.4" fill="#546E7A"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#90CAF9" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#90CAF9" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">우주선이 파괴되었어요</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#B3E5FC" font-family="Arial, Helvetica, sans-serif"
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
V_SCORE  = "varScore01"
V_ROUND  = "varRound02"
V_STATE  = "varState03"
V_LEFT   = "varLeft04"
V_SPDMUL = "varSpdMul05"
V_SVX    = "varShipVX06"
V_SVY    = "varShipVY07"
V_CD     = "varCD08"
V_BX     = "varBX09"
V_BY     = "varBY10"
V_BDIR   = "varBDir11"
V_AX     = "varAX12"
V_AY     = "varAY13"
V_ASIZE  = "varASize14"
V_ADIR   = "varADir15"

BR_START    = "brStart01"
BR_ROUND    = "brRound02"
BR_ASPAWN   = "brASpawn03"
BR_SPLITMED = "brSplitMed04"
BR_SPLITSML = "brSplitSmall05"
BR_FIRE     = "brFire06"

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

# Math helper: sin(deg) / cos(deg) blocks
def sin_of(bs, deg_block_id):
    bid = gen()
    bs[bid] = mk("operator_mathop", inputs={"NUM": slot(deg_block_id)},
                 fields={"OPERATOR": ["sin", None]})
    bs[deg_block_id]["parent"] = bid
    return bid

def cos_of(bs, deg_block_id):
    bid = gen()
    bs[bid] = mk("operator_mathop", inputs={"NUM": slot(deg_block_id)},
                 fields={"OPERATOR": ["cos", None]})
    bs[deg_block_id]["parent"] = bid
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
        (("점수", V_SCORE),    0),
        (("라운드", V_ROUND),  1),
        (("게임상태", V_STATE), 1),
        (("잔여", V_LEFT),     0),
        (("속도배수", V_SPDMUL), 1.0),
        (("우주선VX", V_SVX),  0),
        (("우주선VY", V_SVY),  0),
        (("쿨다운", V_CD),     0),
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

    # --- on 라운드시작: set 잔여=0, spawn N big asteroids ---
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=600,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]})

    # reset 잔여=0
    set_left0 = gen(); bs[set_left0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["잔여", V_LEFT]})

    # 큰 소행성 개수 = min(라운드 + 2, 6)
    # if (라운드 + 2) > 6 → cnt=6, else cnt=라운드+2
    # 단순화: 두 stage 변수 _N 없이 직접 repeat 안에 식 넣기 어려움
    # repeat 블록 TIMES 에 계산식 슬롯 가능
    round_v = vrep("라운드", V_ROUND)
    plus2 = op("operator_add", round_v, 2)
    # cnt 결정: if plus2 > 6 → 6 else plus2.
    # repeat times: just use "operator_mathop floor of min(...)" — 어차피 단순화 위해
    # if (라운드 > 4) → repeat 6 / else repeat (라운드+2)
    # 두 개의 repeat 블록을 if/else 로 분기
    round_v2 = vrep("라운드", V_ROUND)
    cond_clamp = cmp_op("operator_gt", round_v2, 4)

    # --- common asteroid spawn body (factor it once) ---
    def make_spawn_body(parent_label):
        # 소행X 픽
        pickx = gen(); bs[pickx] = mk("operator_random",
            inputs={"FROM": num(1), "TO": num(2)})
        set_pickx = gen(); bs[set_pickx] = mk("data_setvariableto",
            inputs={"VALUE": slot(pickx)}, fields={"VARIABLE": ["소행X", V_AX]})
        bs[pickx]["parent"] = set_pickx

        ax_v = vrep("소행X", V_AX)
        cond_x1 = cmp_op("operator_equals", ax_v, 1)
        ax_neg = gen(); bs[ax_neg] = mk("operator_random",
            inputs={"FROM": num(-220), "TO": num(-100)})
        set_ax_neg = gen(); bs[set_ax_neg] = mk("data_setvariableto",
            inputs={"VALUE": slot(ax_neg)}, fields={"VARIABLE": ["소행X", V_AX]})
        bs[ax_neg]["parent"] = set_ax_neg
        ax_pos = gen(); bs[ax_pos] = mk("operator_random",
            inputs={"FROM": num(100), "TO": num(220)})
        set_ax_pos = gen(); bs[set_ax_pos] = mk("data_setvariableto",
            inputs={"VALUE": slot(ax_pos)}, fields={"VARIABLE": ["소행X", V_AX]})
        bs[ax_pos]["parent"] = set_ax_pos
        if_ax_split = gen(); bs[if_ax_split] = mk("control_if_else",
            inputs={"CONDITION": [2, cond_x1],
                    "SUBSTACK":  [2, set_ax_neg],
                    "SUBSTACK2": [2, set_ax_pos]})
        bs[cond_x1]["parent"] = if_ax_split
        bs[set_ax_neg]["parent"] = if_ax_split
        bs[set_ax_pos]["parent"] = if_ax_split

        # 소행Y 픽
        picky = gen(); bs[picky] = mk("operator_random",
            inputs={"FROM": num(1), "TO": num(2)})
        set_picky = gen(); bs[set_picky] = mk("data_setvariableto",
            inputs={"VALUE": slot(picky)}, fields={"VARIABLE": ["소행Y", V_AY]})
        bs[picky]["parent"] = set_picky

        ay_v = vrep("소행Y", V_AY)
        cond_y1 = cmp_op("operator_equals", ay_v, 1)
        ay_neg = gen(); bs[ay_neg] = mk("operator_random",
            inputs={"FROM": num(-160), "TO": num(-80)})
        set_ay_neg = gen(); bs[set_ay_neg] = mk("data_setvariableto",
            inputs={"VALUE": slot(ay_neg)}, fields={"VARIABLE": ["소행Y", V_AY]})
        bs[ay_neg]["parent"] = set_ay_neg
        ay_pos = gen(); bs[ay_pos] = mk("operator_random",
            inputs={"FROM": num(80), "TO": num(160)})
        set_ay_pos = gen(); bs[set_ay_pos] = mk("data_setvariableto",
            inputs={"VALUE": slot(ay_pos)}, fields={"VARIABLE": ["소행Y", V_AY]})
        bs[ay_pos]["parent"] = set_ay_pos
        if_ay_split = gen(); bs[if_ay_split] = mk("control_if_else",
            inputs={"CONDITION": [2, cond_y1],
                    "SUBSTACK":  [2, set_ay_neg],
                    "SUBSTACK2": [2, set_ay_pos]})
        bs[cond_y1]["parent"] = if_ay_split
        bs[set_ay_neg]["parent"] = if_ay_split
        bs[set_ay_pos]["parent"] = if_ay_split

        # 소행방향 random(0..359)
        dirrand = gen(); bs[dirrand] = mk("operator_random",
            inputs={"FROM": num(0), "TO": num(359)})
        set_adir = gen(); bs[set_adir] = mk("data_setvariableto",
            inputs={"VALUE": slot(dirrand)}, fields={"VARIABLE": ["소행방향", V_ADIR]})
        bs[dirrand]["parent"] = set_adir

        # 소행크기=1
        set_asize = gen(); bs[set_asize] = mk("data_setvariableto",
            inputs={"VALUE": num(1)}, fields={"VARIABLE": ["소행크기", V_ASIZE]})

        # 잔여 += 1
        inc_left = gen(); bs[inc_left] = mk("data_changevariableby",
            inputs={"VALUE": num(1)}, fields={"VARIABLE": ["잔여", V_LEFT]})

        # broadcast 소행성스폰
        bm_as = gen(); bs[bm_as] = mk("event_broadcast_menu",
            fields={"BROADCAST_OPTION": ["소행성스폰", BR_ASPAWN]}, shadow=True)
        bc_as = gen(); bs[bc_as] = mk("event_broadcast",
            inputs={"BROADCAST_INPUT": [1, bm_as]})
        bs[bm_as]["parent"] = bc_as

        w_as = gen(); bs[w_as] = mk("control_wait", inputs={"DURATION": num(0.2)})

        chain([(set_pickx, bs[set_pickx]), (if_ax_split, bs[if_ax_split]),
               (set_picky, bs[set_picky]), (if_ay_split, bs[if_ay_split]),
               (set_adir, bs[set_adir]),
               (set_asize, bs[set_asize]), (inc_left, bs[inc_left]),
               (bc_as, bs[bc_as]), (w_as, bs[w_as])])

        return set_pickx  # head of chain

    body_a_head = make_spawn_body("A")
    body_b_head = make_spawn_body("B")

    # repeat 6 (if 라운드 > 4)
    rep_clamp = gen(); bs[rep_clamp] = mk("control_repeat",
        inputs={"TIMES": num(6), "SUBSTACK": [2, body_a_head]})
    bs[body_a_head]["parent"] = rep_clamp

    # repeat (라운드+2) (else)
    round_v3 = vrep("라운드", V_ROUND)
    plus2b = op("operator_add", round_v3, 2)
    rep_norm = gen(); bs[rep_norm] = mk("control_repeat",
        inputs={"TIMES": slot(plus2b), "SUBSTACK": [2, body_b_head]})
    bs[plus2b]["parent"] = rep_norm
    bs[body_b_head]["parent"] = rep_norm

    if_clamp = gen(); bs[if_clamp] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_clamp],
                "SUBSTACK":  [2, rep_clamp],
                "SUBSTACK2": [2, rep_norm]})
    bs[cond_clamp]["parent"] = if_clamp
    bs[rep_clamp]["parent"] = if_clamp
    bs[rep_norm]["parent"] = if_clamp

    chain([(h3, bs[h3]), (set_left0, bs[set_left0]), (if_clamp, bs[if_clamp])])

    # --- forever (쿨다운 counter) ---
    h4 = gen(); bs[h4] = mk("event_whenflagclicked", top=True, x=400, y=20)
    cd_v = vrep("쿨다운", V_CD)
    c_cd = cmp_op("operator_gt", cd_v, 0)
    dec_cd = gen(); bs[dec_cd] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["쿨다운", V_CD]})
    if_cd = gen(); bs[if_cd] = mk("control_if",
        inputs={"CONDITION": [2, c_cd], "SUBSTACK": [2, dec_cd]})
    bs[c_cd]["parent"] = if_cd
    bs[dec_cd]["parent"] = if_cd
    w_ctr = gen(); bs[w_ctr] = mk("control_wait", inputs={"DURATION": num(0.04)})
    chain([(if_cd, bs[if_cd]), (w_ctr, bs[w_ctr])])
    fe_ctr = gen(); bs[fe_ctr] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_cd]})
    bs[if_cd]["parent"] = fe_ctr
    chain([(h4, bs[h4]), (fe_ctr, bs[fe_ctr])])

    # --- forever round watcher ---
    h5 = gen(); bs[h5] = mk("event_whenflagclicked", top=True, x=400, y=400)
    left_v = vrep("잔여", V_LEFT)
    cond_e0 = cmp_op("operator_equals", left_v, 0)
    state_v = vrep("게임상태", V_STATE)
    cond_alive = cmp_op("operator_equals", state_v, 1)
    cond_next = bool_op("operator_and", cond_e0, cond_alive)

    w_pre = gen(); bs[w_pre] = mk("control_wait", inputs={"DURATION": num(1.5)})
    inc_r = gen(); bs[inc_r] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
    spd_v = vrep("속도배수", V_SPDMUL)
    mul_spd = op("operator_multiply", spd_v, 1.10)
    set_spd = gen(); bs[set_spd] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_spd)}, fields={"VARIABLE": ["속도배수", V_SPDMUL]})
    bs[mul_spd]["parent"] = set_spd

    bm_r2 = gen(); bs[bm_r2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]}, shadow=True)
    bc_r2 = gen(); bs[bc_r2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_r2]})
    bs[bm_r2]["parent"] = bc_r2

    chain([(w_pre, bs[w_pre]), (inc_r, bs[inc_r]),
           (set_spd, bs[set_spd]), (bc_r2, bs[bc_r2])])

    if_next = gen(); bs[if_next] = mk("control_if",
        inputs={"CONDITION": [2, cond_next], "SUBSTACK": [2, w_pre]})
    bs[cond_next]["parent"] = if_next
    bs[w_pre]["parent"] = if_next

    w_watch = gen(); bs[w_watch] = mk("control_wait", inputs={"DURATION": num(0.2)})
    chain([(if_next, bs[if_next]), (w_watch, bs[w_watch])])
    fe_watch = gen(); bs[fe_watch] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_next]})
    bs[if_next]["parent"] = fe_watch
    chain([(h5, bs[h5]), (fe_watch, bs[fe_watch])])

    return bs

# ============================================================
#  SHIP (player spaceship — inertial motion + wrap + fire + collide)
# ============================================================
def build_ship_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- flag: init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    set_vx0 = gen(); bs[set_vx0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    set_vy0 = gen(); bs[set_vy0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["우주선VY", V_SVY]})

    # forever (controls + physics)
    # if left arrow → turn ccw 5
    l_menu = gen(); bs[l_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    l_press = gen(); bs[l_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, l_menu]})
    bs[l_menu]["parent"] = l_press
    turn_ccw = gen(); bs[turn_ccw] = mk("motion_turnleft", inputs={"DEGREES": num(5)})
    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION": [2, l_press], "SUBSTACK": [2, turn_ccw]})
    bs[l_press]["parent"] = if_l
    bs[turn_ccw]["parent"] = if_l

    # if right arrow → turn cw 5
    r_menu = gen(); bs[r_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    r_press = gen(); bs[r_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, r_menu]})
    bs[r_menu]["parent"] = r_press
    turn_cw = gen(); bs[turn_cw] = mk("motion_turnright", inputs={"DEGREES": num(5)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION": [2, r_press], "SUBSTACK": [2, turn_cw]})
    bs[r_press]["parent"] = if_r
    bs[turn_cw]["parent"] = if_r

    # if up arrow → VX += sin(dir)*0.18, VY += cos(dir)*0.18
    up_menu = gen(); bs[up_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["up arrow", None]}, shadow=True)
    up_press = gen(); bs[up_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, up_menu]})
    bs[up_menu]["parent"] = up_press

    # sin(dir)*0.18
    dir_a = gen(); bs[dir_a] = mk("motion_direction")
    sin_dir = sin_of(bs, dir_a)
    mul_sin = op("operator_multiply", sin_dir, 0.18)
    chg_vx = gen(); bs[chg_vx] = mk("data_changevariableby",
        inputs={"VALUE": slot(mul_sin)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    bs[mul_sin]["parent"] = chg_vx

    # cos(dir)*0.18
    dir_b = gen(); bs[dir_b] = mk("motion_direction")
    cos_dir = cos_of(bs, dir_b)
    mul_cos = op("operator_multiply", cos_dir, 0.18)
    chg_vy = gen(); bs[chg_vy] = mk("data_changevariableby",
        inputs={"VALUE": slot(mul_cos)}, fields={"VARIABLE": ["우주선VY", V_SVY]})
    bs[mul_cos]["parent"] = chg_vy

    chain([(chg_vx, bs[chg_vx]), (chg_vy, bs[chg_vy])])

    if_up = gen(); bs[if_up] = mk("control_if",
        inputs={"CONDITION": [2, up_press], "SUBSTACK": [2, chg_vx]})
    bs[up_press]["parent"] = if_up
    bs[chg_vx]["parent"] = if_up

    # clamp VX [-4.5, 4.5]
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

    # update position: change x by VX, change y by VY
    vx_c = vrep("우주선VX", V_SVX)
    chx = gen(); bs[chx] = mk("motion_changexby", inputs={"DX": slot(vx_c)})
    bs[vx_c]["parent"] = chx
    vy_c = vrep("우주선VY", V_SVY)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": slot(vy_c)})
    bs[vy_c]["parent"] = chy

    # friction: VX *= 0.99
    vx_d = vrep("우주선VX", V_SVX)
    mul_vx = op("operator_multiply", vx_d, 0.99)
    set_vx_f = gen(); bs[set_vx_f] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_vx)}, fields={"VARIABLE": ["우주선VX", V_SVX]})
    bs[mul_vx]["parent"] = set_vx_f

    vy_d = vrep("우주선VY", V_SVY)
    mul_vy = op("operator_multiply", vy_d, 0.99)
    set_vy_f = gen(); bs[set_vy_f] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_vy)}, fields={"VARIABLE": ["우주선VY", V_SVY]})
    bs[mul_vy]["parent"] = set_vy_f

    # wrap: if x>240 → set x to -240, etc.
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    c_xhi = cmp_op("operator_gt", xp1, 240)
    sx_neg = gen(); bs[sx_neg] = mk("motion_setx", inputs={"X": num(-240)})
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, c_xhi], "SUBSTACK": [2, sx_neg]})
    bs[c_xhi]["parent"] = if_xhi
    bs[sx_neg]["parent"] = if_xhi

    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_xlo = cmp_op("operator_lt", xp2, -240)
    sx_pos = gen(); bs[sx_pos] = mk("motion_setx", inputs={"X": num(240)})
    if_xlo = gen(); bs[if_xlo] = mk("control_if",
        inputs={"CONDITION": [2, c_xlo], "SUBSTACK": [2, sx_pos]})
    bs[c_xlo]["parent"] = if_xlo
    bs[sx_pos]["parent"] = if_xlo

    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    c_yhi = cmp_op("operator_gt", yp1, 180)
    sy_neg = gen(); bs[sy_neg] = mk("motion_sety", inputs={"Y": num(-180)})
    if_yhi = gen(); bs[if_yhi] = mk("control_if",
        inputs={"CONDITION": [2, c_yhi], "SUBSTACK": [2, sy_neg]})
    bs[c_yhi]["parent"] = if_yhi
    bs[sy_neg]["parent"] = if_yhi

    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    c_ylo = cmp_op("operator_lt", yp2, -180)
    sy_pos = gen(); bs[sy_pos] = mk("motion_sety", inputs={"Y": num(180)})
    if_ylo = gen(); bs[if_ylo] = mk("control_if",
        inputs={"CONDITION": [2, c_ylo], "SUBSTACK": [2, sy_pos]})
    bs[c_ylo]["parent"] = if_ylo
    bs[sy_pos]["parent"] = if_ylo

    w_ctrl = gen(); bs[w_ctrl] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(if_l, bs[if_l]), (if_r, bs[if_r]), (if_up, bs[if_up]),
           (if_vxhi, bs[if_vxhi]), (if_vxlo, bs[if_vxlo]),
           (if_vyhi, bs[if_vyhi]), (if_vylo, bs[if_vylo]),
           (chx, bs[chx]), (chy, bs[chy]),
           (set_vx_f, bs[set_vx_f]), (set_vy_f, bs[set_vy_f]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (w_ctrl, bs[w_ctrl])])

    fe_ctrl = gen(); bs[fe_ctrl] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_l]})
    bs[if_l]["parent"] = fe_ctrl

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (pd, bs[pd]), (front, bs[front]),
           (set_vx0, bs[set_vx0]), (set_vy0, bs[set_vy0]),
           (fe_ctrl, bs[fe_ctrl])])

    # --- forever (fire input) ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)
    sp_menu = gen(); bs[sp_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sp_press = gen(); bs[sp_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, sp_menu]})
    bs[sp_menu]["parent"] = sp_press

    cd_v = vrep("쿨다운", V_CD)
    cond_cd0 = cmp_op("operator_equals", cd_v, 0)
    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)
    cond_a = bool_op("operator_and", sp_press, cond_cd0)
    cond_can_fire = bool_op("operator_and", cond_a, cond_play)

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

    pitch_fire = gen(); bs[pitch_fire] = mk("sound_seteffectto",
        inputs={"VALUE": num(200)}, fields={"EFFECT": ["PITCH", None]})
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

    set_cd = gen(); bs[set_cd] = mk("data_setvariableto",
        inputs={"VALUE": num(10)}, fields={"VARIABLE": ["쿨다운", V_CD]})

    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]),
           (set_bdir, bs[set_bdir]),
           (pitch_fire, bs[pitch_fire]), (snd_fire, bs[snd_fire]),
           (cclone, bs[cclone]), (set_cd, bs[set_cd])])

    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, cond_can_fire], "SUBSTACK": [2, set_bx]})
    bs[cond_can_fire]["parent"] = if_fire
    bs[set_bx]["parent"] = if_fire

    w_fire = gen(); bs[w_fire] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_fire, bs[if_fire]), (w_fire, bs[w_fire])])
    fe_fire = gen(); bs[fe_fire] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_fire]})
    bs[if_fire]["parent"] = fe_fire
    chain([(h2, bs[h2]), (fe_fire, bs[fe_fire])])

    # --- forever (collision: touching 소행성 → game over) ---
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)
    tm_a = gen(); bs[tm_a] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["소행성", None]}, shadow=True)
    tc_a = gen(); bs[tc_a] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_a]})
    bs[tm_a]["parent"] = tc_a

    state_v2 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state_v2, 1)
    cond_die = bool_op("operator_and", tc_a, cond_play2)

    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    pitch_die = gen(); bs[pitch_die] = mk("sound_seteffectto",
        inputs={"VALUE": num(-400)}, fields={"EFFECT": ["PITCH", None]})
    snm_d = gen(); bs[snm_d] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_d = gen(); bs[snd_d] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_d]})
    bs[snm_d]["parent"] = snd_d

    chain([(set_state0, bs[set_state0]), (pitch_die, bs[pitch_die]),
           (snd_d, bs[snd_d])])

    if_die = gen(); bs[if_die] = mk("control_if",
        inputs={"CONDITION": [2, cond_die], "SUBSTACK": [2, set_state0]})
    bs[cond_die]["parent"] = if_die
    bs[set_state0]["parent"] = if_die

    w_die = gen(); bs[w_die] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_die, bs[if_die]), (w_die, bs[w_die])])
    fe_die = gen(); bs[fe_die] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_die]})
    bs[if_die]["parent"] = fe_die
    chain([(h3, bs[h3]), (fe_die, bs[fe_die])])

    return bs

# ============================================================
#  BULLET
# ============================================================
def build_bullet_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    # clone start: move/wrap/lifetime
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

    # body: move 8 + wrap + if touching 소행성 → break
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(8)})

    # wrap x
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    c_xhi = cmp_op("operator_gt", xp1, 240)
    sx_neg = gen(); bs[sx_neg] = mk("motion_setx", inputs={"X": num(-240)})
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, c_xhi], "SUBSTACK": [2, sx_neg]})
    bs[c_xhi]["parent"] = if_xhi
    bs[sx_neg]["parent"] = if_xhi
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_xlo = cmp_op("operator_lt", xp2, -240)
    sx_pos = gen(); bs[sx_pos] = mk("motion_setx", inputs={"X": num(240)})
    if_xlo = gen(); bs[if_xlo] = mk("control_if",
        inputs={"CONDITION": [2, c_xlo], "SUBSTACK": [2, sx_pos]})
    bs[c_xlo]["parent"] = if_xlo
    bs[sx_pos]["parent"] = if_xlo

    # wrap y
    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    c_yhi = cmp_op("operator_gt", yp1, 180)
    sy_neg = gen(); bs[sy_neg] = mk("motion_sety", inputs={"Y": num(-180)})
    if_yhi = gen(); bs[if_yhi] = mk("control_if",
        inputs={"CONDITION": [2, c_yhi], "SUBSTACK": [2, sy_neg]})
    bs[c_yhi]["parent"] = if_yhi
    bs[sy_neg]["parent"] = if_yhi
    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    c_ylo = cmp_op("operator_lt", yp2, -180)
    sy_pos = gen(); bs[sy_pos] = mk("motion_sety", inputs={"Y": num(180)})
    if_ylo = gen(); bs[if_ylo] = mk("control_if",
        inputs={"CONDITION": [2, c_ylo], "SUBSTACK": [2, sy_pos]})
    bs[c_ylo]["parent"] = if_ylo
    bs[sy_pos]["parent"] = if_ylo

    # if touching 소행성 → hide + delete (stop this script ends repeat)
    tm_a = gen(); bs[tm_a] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["소행성", None]}, shadow=True)
    tc_a = gen(); bs[tc_a] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_a]})
    bs[tm_a]["parent"] = tc_a
    hi_a = gen(); bs[hi_a] = mk("looks_hide")
    del_a = gen(); bs[del_a] = mk("control_delete_this_clone")
    chain([(hi_a, bs[hi_a]), (del_a, bs[del_a])])
    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION": [2, tc_a], "SUBSTACK": [2, hi_a]})
    bs[tc_a]["parent"] = if_hit
    bs[hi_a]["parent"] = if_hit

    w_b = gen(); bs[w_b] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(mv, bs[mv]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (if_hit, bs[if_hit]), (w_b, bs[w_b])])

    rep_life = gen(); bs[rep_life] = mk("control_repeat",
        inputs={"TIMES": num(60), "SUBSTACK": [2, mv]})
    bs[mv]["parent"] = rep_life

    hi_end = gen(); bs[hi_end] = mk("looks_hide")
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (point_b, bs[point_b]),
           (show, bs[show]), (rep_life, bs[rep_life]),
           (hi_end, bs[hi_end]), (del_end, bs[del_end])])

    return bs

# ============================================================
#  ASTEROID
# ============================================================
def build_asteroid_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- flag init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["don't rotate", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs])])

    # --- on 소행성스폰 → create clone ---
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["소행성스폰", BR_ASPAWN]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(h2, bs[h2]), (cclone, bs[cclone])])

    # --- on 분열중 → create clone (med) ---
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=300, y=200,
        fields={"BROADCAST_OPTION": ["분열중", BR_SPLITMED]})
    cmenu2 = gen(); bs[cmenu2] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone2 = gen(); bs[cclone2] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu2]})
    bs[cmenu2]["parent"] = cclone2
    chain([(h3, bs[h3]), (cclone2, bs[cclone2])])

    # --- on 분열소 → create clone (small) ---
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=600, y=200,
        fields={"BROADCAST_OPTION": ["분열소", BR_SPLITSML]})
    cmenu3 = gen(); bs[cmenu3] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone3 = gen(); bs[cclone3] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu3]})
    bs[cmenu3]["parent"] = cclone3
    chain([(h4, bs[h4]), (cclone3, bs[cclone3])])

    # --- clone start ---
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=400)

    # goto 소행X, 소행Y
    ax_v = vrep("소행X", V_AX); ay_v = vrep("소행Y", V_AY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(ax_v), "Y": slot(ay_v)})
    bs[ax_v]["parent"] = g; bs[ay_v]["parent"] = g

    # set costume + size based on 소행크기
    asize_v1 = vrep("소행크기", V_ASIZE)
    cond_big = cmp_op("operator_equals", asize_v1, 1)
    cm_big = gen(); bs[cm_big] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen()]})
    # need a real costume menu shadow
    big_menu = list(bs[cm_big]["inputs"]["COSTUME"])
    big_menu_id = big_menu[1]
    bs[big_menu_id] = mk("looks_costume",
        fields={"COSTUME": ["rock_big", None]}, shadow=True, parent=cm_big)
    sz_big = gen(); bs[sz_big] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(cm_big, bs[cm_big]), (sz_big, bs[sz_big])])
    if_big = gen(); bs[if_big] = mk("control_if",
        inputs={"CONDITION": [2, cond_big], "SUBSTACK": [2, cm_big]})
    bs[cond_big]["parent"] = if_big
    bs[cm_big]["parent"] = if_big

    asize_v2 = vrep("소행크기", V_ASIZE)
    cond_med = cmp_op("operator_equals", asize_v2, 2)
    cm_med = gen(); bs[cm_med] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen()]})
    med_menu_id = bs[cm_med]["inputs"]["COSTUME"][1]
    bs[med_menu_id] = mk("looks_costume",
        fields={"COSTUME": ["rock_med", None]}, shadow=True, parent=cm_med)
    sz_med = gen(); bs[sz_med] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    chain([(cm_med, bs[cm_med]), (sz_med, bs[sz_med])])
    if_med = gen(); bs[if_med] = mk("control_if",
        inputs={"CONDITION": [2, cond_med], "SUBSTACK": [2, cm_med]})
    bs[cond_med]["parent"] = if_med
    bs[cm_med]["parent"] = if_med

    asize_v3 = vrep("소행크기", V_ASIZE)
    cond_sm = cmp_op("operator_equals", asize_v3, 3)
    cm_sm = gen(); bs[cm_sm] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen()]})
    sm_menu_id = bs[cm_sm]["inputs"]["COSTUME"][1]
    bs[sm_menu_id] = mk("looks_costume",
        fields={"COSTUME": ["rock_small", None]}, shadow=True, parent=cm_sm)
    sz_sm = gen(); bs[sz_sm] = mk("looks_setsizeto", inputs={"SIZE": num(45)})
    chain([(cm_sm, bs[cm_sm]), (sz_sm, bs[sz_sm])])
    if_sm = gen(); bs[if_sm] = mk("control_if",
        inputs={"CONDITION": [2, cond_sm], "SUBSTACK": [2, cm_sm]})
    bs[cond_sm]["parent"] = if_sm
    bs[cm_sm]["parent"] = if_sm

    # direction = 소행방향 + random(-30..30)
    adir_v = vrep("소행방향", V_ADIR)
    djit = gen(); bs[djit] = mk("operator_random",
        inputs={"FROM": num(-30), "TO": num(30)})
    dsum = op("operator_add", adir_v, djit)
    point_d = gen(); bs[point_d] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(dsum)})
    bs[dsum]["parent"] = point_d

    show = gen(); bs[show] = mk("looks_show")

    # --- forever body ---
    # detect bullet collision FIRST
    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["총알", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b]})
    bs[tm_b]["parent"] = tc_b

    # --- handle hit based on size ---
    # branch: if size = 100 (big)
    size_a = gen(); bs[size_a] = mk("looks_size")
    cond_szbig = cmp_op("operator_equals", size_a, 100)

    # big body: score +20, set 소행X = self x, 소행Y = self y, broadcast 분열중 twice (with 방향 ±45), 잔여 +1
    add_score_big = gen(); bs[add_score_big] = mk("data_changevariableby",
        inputs={"VALUE": num(20)}, fields={"VARIABLE": ["점수", V_SCORE]})
    xb1 = gen(); bs[xb1] = mk("motion_xposition")
    set_axb = gen(); bs[set_axb] = mk("data_setvariableto",
        inputs={"VALUE": slot(xb1)}, fields={"VARIABLE": ["소행X", V_AX]})
    bs[xb1]["parent"] = set_axb
    yb1 = gen(); bs[yb1] = mk("motion_yposition")
    set_ayb = gen(); bs[set_ayb] = mk("data_setvariableto",
        inputs={"VALUE": slot(yb1)}, fields={"VARIABLE": ["소행Y", V_AY]})
    bs[yb1]["parent"] = set_ayb
    set_szmed = gen(); bs[set_szmed] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["소행크기", V_ASIZE]})
    # 방향 = direction + 45
    dir_b1 = gen(); bs[dir_b1] = mk("motion_direction")
    dir_p45 = op("operator_add", dir_b1, 45)
    set_adir_p = gen(); bs[set_adir_p] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_p45)}, fields={"VARIABLE": ["소행방향", V_ADIR]})
    bs[dir_p45]["parent"] = set_adir_p
    bm_sm1 = gen(); bs[bm_sm1] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["분열중", BR_SPLITMED]}, shadow=True)
    bc_sm1 = gen(); bs[bc_sm1] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sm1]})
    bs[bm_sm1]["parent"] = bc_sm1
    # 방향 = direction - 45
    dir_b2 = gen(); bs[dir_b2] = mk("motion_direction")
    dir_m45 = op("operator_add", dir_b2, -45)
    set_adir_m = gen(); bs[set_adir_m] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_m45)}, fields={"VARIABLE": ["소행방향", V_ADIR]})
    bs[dir_m45]["parent"] = set_adir_m
    bm_sm2 = gen(); bs[bm_sm2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["분열중", BR_SPLITMED]}, shadow=True)
    bc_sm2 = gen(); bs[bc_sm2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sm2]})
    bs[bm_sm2]["parent"] = bc_sm2
    inc_left_big = gen(); bs[inc_left_big] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["잔여", V_LEFT]})
    pitch_big = gen(); bs[pitch_big] = mk("sound_seteffectto",
        inputs={"VALUE": num(-100)}, fields={"EFFECT": ["PITCH", None]})
    snm_b1 = gen(); bs[snm_b1] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_b1 = gen(); bs[snd_b1] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_b1]})
    bs[snm_b1]["parent"] = snd_b1
    hi_big = gen(); bs[hi_big] = mk("looks_hide")
    del_big = gen(); bs[del_big] = mk("control_delete_this_clone")
    chain([(add_score_big, bs[add_score_big]),
           (set_axb, bs[set_axb]), (set_ayb, bs[set_ayb]),
           (set_szmed, bs[set_szmed]),
           (set_adir_p, bs[set_adir_p]), (bc_sm1, bs[bc_sm1]),
           (set_adir_m, bs[set_adir_m]), (bc_sm2, bs[bc_sm2]),
           (inc_left_big, bs[inc_left_big]),
           (pitch_big, bs[pitch_big]), (snd_b1, bs[snd_b1]),
           (hi_big, bs[hi_big]), (del_big, bs[del_big])])
    if_big_hit = gen(); bs[if_big_hit] = mk("control_if",
        inputs={"CONDITION": [2, cond_szbig], "SUBSTACK": [2, add_score_big]})
    bs[cond_szbig]["parent"] = if_big_hit
    bs[add_score_big]["parent"] = if_big_hit

    # branch: if size = 70 (med)
    size_b = gen(); bs[size_b] = mk("looks_size")
    cond_szmed = cmp_op("operator_equals", size_b, 70)
    add_score_med = gen(); bs[add_score_med] = mk("data_changevariableby",
        inputs={"VALUE": num(50)}, fields={"VARIABLE": ["점수", V_SCORE]})
    xm1 = gen(); bs[xm1] = mk("motion_xposition")
    set_axm = gen(); bs[set_axm] = mk("data_setvariableto",
        inputs={"VALUE": slot(xm1)}, fields={"VARIABLE": ["소행X", V_AX]})
    bs[xm1]["parent"] = set_axm
    ym1 = gen(); bs[ym1] = mk("motion_yposition")
    set_aym = gen(); bs[set_aym] = mk("data_setvariableto",
        inputs={"VALUE": slot(ym1)}, fields={"VARIABLE": ["소행Y", V_AY]})
    bs[ym1]["parent"] = set_aym
    set_szsm = gen(); bs[set_szsm] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["소행크기", V_ASIZE]})
    dir_m1 = gen(); bs[dir_m1] = mk("motion_direction")
    dir_mp45 = op("operator_add", dir_m1, 45)
    set_adir_mp = gen(); bs[set_adir_mp] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_mp45)}, fields={"VARIABLE": ["소행방향", V_ADIR]})
    bs[dir_mp45]["parent"] = set_adir_mp
    bm_ss1 = gen(); bs[bm_ss1] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["분열소", BR_SPLITSML]}, shadow=True)
    bc_ss1 = gen(); bs[bc_ss1] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ss1]})
    bs[bm_ss1]["parent"] = bc_ss1
    dir_m2 = gen(); bs[dir_m2] = mk("motion_direction")
    dir_mm45 = op("operator_add", dir_m2, -45)
    set_adir_mm = gen(); bs[set_adir_mm] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_mm45)}, fields={"VARIABLE": ["소행방향", V_ADIR]})
    bs[dir_mm45]["parent"] = set_adir_mm
    bm_ss2 = gen(); bs[bm_ss2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["분열소", BR_SPLITSML]}, shadow=True)
    bc_ss2 = gen(); bs[bc_ss2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ss2]})
    bs[bm_ss2]["parent"] = bc_ss2
    inc_left_med = gen(); bs[inc_left_med] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["잔여", V_LEFT]})
    pitch_med = gen(); bs[pitch_med] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["PITCH", None]})
    snm_m1 = gen(); bs[snm_m1] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_m1 = gen(); bs[snd_m1] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_m1]})
    bs[snm_m1]["parent"] = snd_m1
    hi_med = gen(); bs[hi_med] = mk("looks_hide")
    del_med = gen(); bs[del_med] = mk("control_delete_this_clone")
    chain([(add_score_med, bs[add_score_med]),
           (set_axm, bs[set_axm]), (set_aym, bs[set_aym]),
           (set_szsm, bs[set_szsm]),
           (set_adir_mp, bs[set_adir_mp]), (bc_ss1, bs[bc_ss1]),
           (set_adir_mm, bs[set_adir_mm]), (bc_ss2, bs[bc_ss2]),
           (inc_left_med, bs[inc_left_med]),
           (pitch_med, bs[pitch_med]), (snd_m1, bs[snd_m1]),
           (hi_med, bs[hi_med]), (del_med, bs[del_med])])
    if_med_hit = gen(); bs[if_med_hit] = mk("control_if",
        inputs={"CONDITION": [2, cond_szmed], "SUBSTACK": [2, add_score_med]})
    bs[cond_szmed]["parent"] = if_med_hit
    bs[add_score_med]["parent"] = if_med_hit

    # branch: if size = 45 (small) → +100, 잔여 -1, no split, delete
    size_c = gen(); bs[size_c] = mk("looks_size")
    cond_szsm = cmp_op("operator_equals", size_c, 45)
    add_score_sm = gen(); bs[add_score_sm] = mk("data_changevariableby",
        inputs={"VALUE": num(100)}, fields={"VARIABLE": ["점수", V_SCORE]})
    dec_left_sm = gen(); bs[dec_left_sm] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["잔여", V_LEFT]})
    pitch_sm = gen(); bs[pitch_sm] = mk("sound_seteffectto",
        inputs={"VALUE": num(100)}, fields={"EFFECT": ["PITCH", None]})
    snm_s1 = gen(); bs[snm_s1] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_s1 = gen(); bs[snd_s1] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_s1]})
    bs[snm_s1]["parent"] = snd_s1
    hi_sm = gen(); bs[hi_sm] = mk("looks_hide")
    del_sm = gen(); bs[del_sm] = mk("control_delete_this_clone")
    chain([(add_score_sm, bs[add_score_sm]),
           (dec_left_sm, bs[dec_left_sm]),
           (pitch_sm, bs[pitch_sm]), (snd_s1, bs[snd_s1]),
           (hi_sm, bs[hi_sm]), (del_sm, bs[del_sm])])
    if_sm_hit = gen(); bs[if_sm_hit] = mk("control_if",
        inputs={"CONDITION": [2, cond_szsm], "SUBSTACK": [2, add_score_sm]})
    bs[cond_szsm]["parent"] = if_sm_hit
    bs[add_score_sm]["parent"] = if_sm_hit

    # wrap if branches inside one master `if touching 총알`
    chain([(if_big_hit, bs[if_big_hit]),
           (if_med_hit, bs[if_med_hit]),
           (if_sm_hit,  bs[if_sm_hit])])
    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION": [2, tc_b], "SUBSTACK": [2, if_big_hit]})
    bs[tc_b]["parent"] = if_hit
    bs[if_big_hit]["parent"] = if_hit

    # --- move based on size (and 속도배수) ---
    # if size=100 → move 1.2 * 속도배수
    size_d = gen(); bs[size_d] = mk("looks_size")
    cond_mvbig = cmp_op("operator_equals", size_d, 100)
    spd_v1 = vrep("속도배수", V_SPDMUL)
    spd_big = op("operator_multiply", spd_v1, 1.2)
    mv_big = gen(); bs[mv_big] = mk("motion_movesteps", inputs={"STEPS": slot(spd_big)})
    bs[spd_big]["parent"] = mv_big
    if_mvbig = gen(); bs[if_mvbig] = mk("control_if",
        inputs={"CONDITION": [2, cond_mvbig], "SUBSTACK": [2, mv_big]})
    bs[cond_mvbig]["parent"] = if_mvbig
    bs[mv_big]["parent"] = if_mvbig

    # if size=70 → move 1.7 * 속도배수
    size_e = gen(); bs[size_e] = mk("looks_size")
    cond_mvmed = cmp_op("operator_equals", size_e, 70)
    spd_v2 = vrep("속도배수", V_SPDMUL)
    spd_med = op("operator_multiply", spd_v2, 1.7)
    mv_med = gen(); bs[mv_med] = mk("motion_movesteps", inputs={"STEPS": slot(spd_med)})
    bs[spd_med]["parent"] = mv_med
    if_mvmed = gen(); bs[if_mvmed] = mk("control_if",
        inputs={"CONDITION": [2, cond_mvmed], "SUBSTACK": [2, mv_med]})
    bs[cond_mvmed]["parent"] = if_mvmed
    bs[mv_med]["parent"] = if_mvmed

    # if size=45 → move 2.2 * 속도배수
    size_f = gen(); bs[size_f] = mk("looks_size")
    cond_mvsm = cmp_op("operator_equals", size_f, 45)
    spd_v3 = vrep("속도배수", V_SPDMUL)
    spd_sm = op("operator_multiply", spd_v3, 2.2)
    mv_sm = gen(); bs[mv_sm] = mk("motion_movesteps", inputs={"STEPS": slot(spd_sm)})
    bs[spd_sm]["parent"] = mv_sm
    if_mvsm = gen(); bs[if_mvsm] = mk("control_if",
        inputs={"CONDITION": [2, cond_mvsm], "SUBSTACK": [2, mv_sm]})
    bs[cond_mvsm]["parent"] = if_mvsm
    bs[mv_sm]["parent"] = if_mvsm

    # wrap x
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    c_xhi = cmp_op("operator_gt", xp1, 240)
    sx_neg = gen(); bs[sx_neg] = mk("motion_setx", inputs={"X": num(-240)})
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, c_xhi], "SUBSTACK": [2, sx_neg]})
    bs[c_xhi]["parent"] = if_xhi
    bs[sx_neg]["parent"] = if_xhi
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_xlo = cmp_op("operator_lt", xp2, -240)
    sx_pos = gen(); bs[sx_pos] = mk("motion_setx", inputs={"X": num(240)})
    if_xlo = gen(); bs[if_xlo] = mk("control_if",
        inputs={"CONDITION": [2, c_xlo], "SUBSTACK": [2, sx_pos]})
    bs[c_xlo]["parent"] = if_xlo
    bs[sx_pos]["parent"] = if_xlo
    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    c_yhi = cmp_op("operator_gt", yp1, 180)
    sy_neg = gen(); bs[sy_neg] = mk("motion_sety", inputs={"Y": num(-180)})
    if_yhi = gen(); bs[if_yhi] = mk("control_if",
        inputs={"CONDITION": [2, c_yhi], "SUBSTACK": [2, sy_neg]})
    bs[c_yhi]["parent"] = if_yhi
    bs[sy_neg]["parent"] = if_yhi
    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    c_ylo = cmp_op("operator_lt", yp2, -180)
    sy_pos = gen(); bs[sy_pos] = mk("motion_sety", inputs={"Y": num(180)})
    if_ylo = gen(); bs[if_ylo] = mk("control_if",
        inputs={"CONDITION": [2, c_ylo], "SUBSTACK": [2, sy_pos]})
    bs[c_ylo]["parent"] = if_ylo
    bs[sy_pos]["parent"] = if_ylo

    w_iter = gen(); bs[w_iter] = mk("control_wait", inputs={"DURATION": num(0.04)})

    chain([(if_hit, bs[if_hit]),
           (if_mvbig, bs[if_mvbig]),
           (if_mvmed, bs[if_mvmed]),
           (if_mvsm, bs[if_mvsm]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (w_iter, bs[w_iter])])

    fe_body = gen(); bs[fe_body] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_hit]})
    bs[if_hit]["parent"] = fe_body

    chain([(ch, bs[ch]), (g, bs[g]),
           (if_big, bs[if_big]), (if_med, bs[if_med]), (if_sm, bs[if_sm]),
           (point_d, bs[point_d]),
           (show, bs[show]), (fe_body, bs[fe_body])])

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
    sh_md5 = md5_bytes(SHIP_SVG.encode("utf-8"))
    with open(f"{WORK}/{sh_md5}.svg", "w", encoding="utf-8") as f: f.write(SHIP_SVG)
    bl_md5 = md5_bytes(BULLET_SVG.encode("utf-8"))
    with open(f"{WORK}/{bl_md5}.svg", "w", encoding="utf-8") as f: f.write(BULLET_SVG)
    rb_md5 = md5_bytes(ROCK_BIG_SVG.encode("utf-8"))
    with open(f"{WORK}/{rb_md5}.svg", "w", encoding="utf-8") as f: f.write(ROCK_BIG_SVG)
    rm_md5 = md5_bytes(ROCK_MED_SVG.encode("utf-8"))
    with open(f"{WORK}/{rm_md5}.svg", "w", encoding="utf-8") as f: f.write(ROCK_MED_SVG)
    rs_md5 = md5_bytes(ROCK_SMALL_SVG.encode("utf-8"))
    with open(f"{WORK}/{rs_md5}.svg", "w", encoding="utf-8") as f: f.write(ROCK_SMALL_SVG)
    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f: f.write(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    ship_blocks     = build_ship_blocks()
    bullet_blocks   = build_bullet_blocks()
    asteroid_blocks = build_asteroid_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:  ["점수", 0],
            V_ROUND:  ["라운드", 1],
            V_STATE:  ["게임상태", 1],
            V_LEFT:   ["잔여", 0],
            V_SPDMUL: ["속도배수", 1.0],
            V_SVX:    ["우주선VX", 0],
            V_SVY:    ["우주선VY", 0],
            V_CD:     ["쿨다운", 0],
            V_BX:     ["총알X", 0],
            V_BY:     ["총알Y", 0],
            V_BDIR:   ["총알방향", 0],
            V_AX:     ["소행X", 0],
            V_AY:     ["소행Y", 0],
            V_ASIZE:  ["소행크기", 1],
            V_ADIR:   ["소행방향", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:    "게임시작",
            BR_ROUND:    "라운드시작",
            BR_ASPAWN:   "소행성스폰",
            BR_SPLITMED: "분열중",
            BR_SPLITSML: "분열소",
            BR_FIRE:     "발사",
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
            "rotationCenterX": 20, "rotationCenterY": 22
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": 0, "size": 70, "direction": 0,
        "draggable": False, "rotationStyle": "all around"
    }

    bullet = {
        "isStage": False, "name": "총알",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bullet", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bl_md5, "md5ext": f"{bl_md5}.svg",
            "rotationCenterX": 5, "rotationCenterY": 7
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 0,
        "draggable": False, "rotationStyle": "all around"
    }

    asteroid = {
        "isStage": False, "name": "소행성",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": asteroid_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "rock_big", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": rb_md5, "md5ext": f"{rb_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 40},
            {"name": "rock_med", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": rm_md5, "md5ext": f"{rm_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "rock_small", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": rs_md5, "md5ext": f"{rs_md5}.svg",
             "rotationCenterX": 20, "rotationCenterY": 20},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
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
        "volume": 100, "layerOrder": 6, "visible": False,
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
        {"id": V_LEFT, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "잔여"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 30, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, ship, bullet, asteroid, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "asteroids-builder"}
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
    print(f"  bullet:   {len(bullet_blocks)} blocks")
    print(f"  asteroid: {len(asteroid_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(ship_blocks) + len(bullet_blocks)
             + len(asteroid_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
