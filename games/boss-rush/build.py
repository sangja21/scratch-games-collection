#!/usr/bin/env python3
"""Boss Rush — 1v1 player vs giant boss with 3-phase bullet patterns + HP bar."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "보스_러시.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: dark purple boss-arena + tiny stars --------
random.seed(11)
stars = []
for _ in range(28):
    sx = random.randint(8, 472); sy = random.randint(8, 352)
    r  = random.choice([1, 1, 1, 2, 2, 3])
    op = random.uniform(0.5, 0.95)
    stars.append(f'<circle cx="{sx}" cy="{sy}" r="{r}" fill="#FFFFFF" opacity="{op:.2f}"/>')
STARS = "\n  ".join(stars)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#1A0033"/>
      <stop offset="0.6" stop-color="#2E0854"/>
      <stop offset="1" stop-color="#120226"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  {STARS}
  <!-- horizon glow -->
  <ellipse cx="240" cy="55" rx="220" ry="40" fill="#6A1B9A" opacity="0.35"/>
</svg>"""

# -------- Player ship (small cyan fighter, nose UP = direction 0) --------
PLAYER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="36" height="40" viewBox="0 0 36 40">
  <!-- left wing -->
  <polygon points="2,30 14,22 14,34" fill="#0097A7" stroke="#003C40" stroke-width="1.2"/>
  <!-- right wing -->
  <polygon points="34,30 22,22 22,34" fill="#0097A7" stroke="#003C40" stroke-width="1.2"/>
  <!-- body -->
  <polygon points="18,2 12,18 12,34 24,34 24,18" fill="#26C6DA" stroke="#004D40" stroke-width="1.4"/>
  <!-- nose -->
  <polygon points="18,2 14,10 22,10" fill="#FFEB3B" stroke="#7E5700" stroke-width="1"/>
  <!-- cockpit -->
  <ellipse cx="18" cy="20" rx="3.5" ry="5" fill="#1A237E" stroke="#FFFFFF" stroke-width="1"/>
  <!-- thruster glow -->
  <rect x="15" y="34" width="6" height="5" fill="#FFD54F"/>
  <rect x="16" y="36" width="4" height="4" fill="#FF8A65"/>
</svg>"""

# -------- Boss (giant UFO with one red eye, ~140x80) --------
BOSS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="160" height="100" viewBox="0 0 160 100">
  <!-- bottom dome / underbelly -->
  <ellipse cx="80" cy="60" rx="70" ry="34" fill="#4A148C" stroke="#1A0033" stroke-width="2.5"/>
  <!-- top hull -->
  <ellipse cx="80" cy="48" rx="56" ry="28" fill="#7B1FA2" stroke="#1A0033" stroke-width="2.5"/>
  <!-- yellow rim lights -->
  <circle cx="22" cy="60" r="5" fill="#FFEB3B" stroke="#7E5700" stroke-width="1"/>
  <circle cx="50" cy="72" r="5" fill="#FFEB3B" stroke="#7E5700" stroke-width="1"/>
  <circle cx="80" cy="78" r="5" fill="#FFEB3B" stroke="#7E5700" stroke-width="1"/>
  <circle cx="110" cy="72" r="5" fill="#FFEB3B" stroke="#7E5700" stroke-width="1"/>
  <circle cx="138" cy="60" r="5" fill="#FFEB3B" stroke="#7E5700" stroke-width="1"/>
  <!-- single red eye -->
  <ellipse cx="80" cy="42" rx="22" ry="14" fill="#FFCDD2" stroke="#1A0033" stroke-width="2"/>
  <ellipse cx="80" cy="44" rx="13" ry="9" fill="#E53935" stroke="#7F0000" stroke-width="1.4"/>
  <circle cx="80" cy="44" r="4" fill="#1A0033"/>
  <!-- top antenna -->
  <rect x="78" y="14" width="4" height="10" fill="#1A0033"/>
  <circle cx="80" cy="12" r="4" fill="#FF5252" stroke="#7F0000" stroke-width="1"/>
</svg>"""

# -------- Player bullet (cyan) --------
BULLET_PLAYER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="10" height="16" viewBox="0 0 10 16">
  <ellipse cx="5" cy="8" rx="3.5" ry="7" fill="#80DEEA" stroke="#006064" stroke-width="1.4"/>
  <ellipse cx="5" cy="6" rx="1.6" ry="3" fill="#E0F7FA"/>
</svg>"""

# -------- Boss bullet (orange-red) --------
BULLET_BOSS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
  <circle cx="7" cy="7" r="6" fill="#FF7043" stroke="#BF360C" stroke-width="1.5"/>
  <circle cx="6" cy="5" r="2" fill="#FFE0B2"/>
</svg>"""

# -------- HP bar background (grey empty bar) --------
HPBAR_BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="210" height="22" viewBox="0 0 210 22">
  <rect x="2" y="2" width="206" height="18" rx="4" fill="#37474F" stroke="#ECEFF1" stroke-width="2"/>
  <rect x="5" y="5" width="200" height="12" rx="2" fill="#212121"/>
</svg>"""

# -------- HP bar fill (red, exactly 200 wide at size=100) --------
HPBAR_FILL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="12" viewBox="0 0 200 12">
  <rect x="0" y="0" width="200" height="12" rx="2" fill="#E53935"/>
  <rect x="0" y="0" width="200" height="4" rx="2" fill="#FF8A80" opacity="0.7"/>
</svg>"""

# -------- Win banner --------
WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#1A237E" opacity="0.95"
        stroke="#FFEB3B" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">VICTORY!</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">보스를 격파했어요!</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#B3E5FC" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭</text>
</svg>"""

# -------- Lose banner --------
LOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#EF5350" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#EF5350" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">보스에게 당했어요…</text>
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
V_PHP    = "varPHP01"
V_BHP    = "varBHP02"
V_STATE  = "varState03"
V_PCD    = "varPCD04"
V_BCD    = "varBCD05"
V_PHASE  = "varPhase06"
V_BDIR   = "varBDir07"
V_BX     = "varBX08"
V_BY     = "varBY09"
V_BSPD   = "varBSpd10"
V_PBX    = "varPBX11"
V_PBY    = "varPBY12"
V_BBX    = "varBBX13"
V_BBY    = "varBBY14"
V_BBDIR  = "varBBDir15"
V_INV    = "varInv16"
V_I      = "varI17"

BR_START  = "brStart01"
BR_PFIRE  = "brPFire02"
BR_BFIRE1 = "brBFire1_03"
BR_BFIRE2 = "brBFire2_04"
BR_BFIRE3 = "brBFire3_05"

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

    # --- when flag clicked: init all 16 vars + broadcast 게임시작 ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = []
    for var_pair, val in [
        (("내체력", V_PHP),       5),
        (("보스체력", V_BHP),    100),
        (("게임상태", V_STATE),    1),
        (("플쿨다운", V_PCD),       0),
        (("보스쿨다운", V_BCD),    30),
        (("현재페이즈", V_PHASE),    1),
        (("보스방향", V_BDIR),    180),
        (("보스X", V_BX),            0),
        (("보스Y", V_BY),          110),
        (("보스속도", V_BSPD),     1.5),
        (("플총X", V_PBX),           0),
        (("플총Y", V_PBY),         -125),
        (("보스탄X", V_BBX),         0),
        (("보스탄Y", V_BBY),        95),
        (("보스탄방향", V_BBDIR), 180),
        (("무적", V_INV),            0),
        (("i카운터", V_I),           0),
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

    # --- forever (phase update based on 보스체력) ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    # Phase 1: 보스체력 > 66 → 현재페이즈=1, 보스속도=1.5
    bhp_v1 = vrep("보스체력", V_BHP)
    c_p1 = cmp_op("operator_gt", bhp_v1, 66)
    set_p1 = gen(); bs[set_p1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["현재페이즈", V_PHASE]})
    set_sp1 = gen(); bs[set_sp1] = mk("data_setvariableto",
        inputs={"VALUE": num(1.5)}, fields={"VARIABLE": ["보스속도", V_BSPD]})
    chain([(set_p1, bs[set_p1]), (set_sp1, bs[set_sp1])])
    if_p1 = gen(); bs[if_p1] = mk("control_if",
        inputs={"CONDITION": [2, c_p1], "SUBSTACK": [2, set_p1]})
    bs[c_p1]["parent"] = if_p1
    bs[set_p1]["parent"] = if_p1

    # Phase 2: 보스체력 ≤ 66 AND > 33
    bhp_v2a = vrep("보스체력", V_BHP)
    c_le66 = cmp_op("operator_lt", bhp_v2a, 67)   # < 67 == ≤ 66
    bhp_v2b = vrep("보스체력", V_BHP)
    c_gt33 = cmp_op("operator_gt", bhp_v2b, 33)
    c_p2 = bool_op("operator_and", c_le66, c_gt33)
    set_p2 = gen(); bs[set_p2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["현재페이즈", V_PHASE]})
    set_sp2 = gen(); bs[set_sp2] = mk("data_setvariableto",
        inputs={"VALUE": num(2.5)}, fields={"VARIABLE": ["보스속도", V_BSPD]})
    chain([(set_p2, bs[set_p2]), (set_sp2, bs[set_sp2])])
    if_p2 = gen(); bs[if_p2] = mk("control_if",
        inputs={"CONDITION": [2, c_p2], "SUBSTACK": [2, set_p2]})
    bs[c_p2]["parent"] = if_p2
    bs[set_p2]["parent"] = if_p2

    # Phase 3: 보스체력 ≤ 33 (실은 < 34)
    bhp_v3 = vrep("보스체력", V_BHP)
    c_p3 = cmp_op("operator_lt", bhp_v3, 34)
    set_p3 = gen(); bs[set_p3] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["현재페이즈", V_PHASE]})
    set_sp3 = gen(); bs[set_sp3] = mk("data_setvariableto",
        inputs={"VALUE": num(3.5)}, fields={"VARIABLE": ["보스속도", V_BSPD]})
    chain([(set_p3, bs[set_p3]), (set_sp3, bs[set_sp3])])
    if_p3 = gen(); bs[if_p3] = mk("control_if",
        inputs={"CONDITION": [2, c_p3], "SUBSTACK": [2, set_p3]})
    bs[c_p3]["parent"] = if_p3
    bs[set_p3]["parent"] = if_p3

    w_phase = gen(); bs[w_phase] = mk("control_wait", inputs={"DURATION": num(0.1)})
    chain([(if_p1, bs[if_p1]), (if_p2, bs[if_p2]), (if_p3, bs[if_p3]), (w_phase, bs[w_phase])])
    fe_phase = gen(); bs[fe_phase] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_p1]})
    bs[if_p1]["parent"] = fe_phase
    chain([(h2, bs[h2]), (fe_phase, bs[fe_phase])])

    # --- forever cooldown counter (플쿨다운, 보스쿨다운, 무적) + 보스 사격 발사 ---
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)

    pcd_v = vrep("플쿨다운", V_PCD)
    c_pcd = cmp_op("operator_gt", pcd_v, 0)
    dec_pcd = gen(); bs[dec_pcd] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["플쿨다운", V_PCD]})
    if_pcd = gen(); bs[if_pcd] = mk("control_if",
        inputs={"CONDITION": [2, c_pcd], "SUBSTACK": [2, dec_pcd]})
    bs[c_pcd]["parent"] = if_pcd
    bs[dec_pcd]["parent"] = if_pcd

    bcd_v = vrep("보스쿨다운", V_BCD)
    c_bcd = cmp_op("operator_gt", bcd_v, 0)
    dec_bcd = gen(); bs[dec_bcd] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["보스쿨다운", V_BCD]})
    if_bcd = gen(); bs[if_bcd] = mk("control_if",
        inputs={"CONDITION": [2, c_bcd], "SUBSTACK": [2, dec_bcd]})
    bs[c_bcd]["parent"] = if_bcd
    bs[dec_bcd]["parent"] = if_bcd

    inv_v = vrep("무적", V_INV)
    c_inv = cmp_op("operator_gt", inv_v, 0)
    dec_inv = gen(); bs[dec_inv] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["무적", V_INV]})
    if_inv = gen(); bs[if_inv] = mk("control_if",
        inputs={"CONDITION": [2, c_inv], "SUBSTACK": [2, dec_inv]})
    bs[c_inv]["parent"] = if_inv
    bs[dec_inv]["parent"] = if_inv

    # if 보스쿨다운=0 AND 게임상태=1 → spawn boss bullet via phase broadcast
    bcd_v2 = vrep("보스쿨다운", V_BCD)
    c_bcd0 = cmp_op("operator_equals", bcd_v2, 0)
    state_v = vrep("게임상태", V_STATE)
    c_play  = cmp_op("operator_equals", state_v, 1)
    c_canf  = bool_op("operator_and", c_bcd0, c_play)

    # 보스탄X = 보스X, 보스탄Y = 보스Y - 15
    bx_v = vrep("보스X", V_BX)
    set_bbx = gen(); bs[set_bbx] = mk("data_setvariableto",
        inputs={"VALUE": slot(bx_v)}, fields={"VARIABLE": ["보스탄X", V_BBX]})
    bs[bx_v]["parent"] = set_bbx
    by_v = vrep("보스Y", V_BY)
    sub_by = op("operator_subtract", by_v, 15, "NUM1", "NUM2")
    set_bby = gen(); bs[set_bby] = mk("data_setvariableto",
        inputs={"VALUE": slot(sub_by)}, fields={"VARIABLE": ["보스탄Y", V_BBY]})
    bs[sub_by]["parent"] = set_bby

    # If 현재페이즈=1 → broadcast 보스사격1 + 보스쿨다운=25
    ph_v1 = vrep("현재페이즈", V_PHASE)
    c_isp1 = cmp_op("operator_equals", ph_v1, 1)
    bm_b1 = gen(); bs[bm_b1] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["보스사격1", BR_BFIRE1]}, shadow=True)
    bc_b1 = gen(); bs[bc_b1] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_b1]})
    bs[bm_b1]["parent"] = bc_b1
    set_bcd1 = gen(); bs[set_bcd1] = mk("data_setvariableto",
        inputs={"VALUE": num(25)}, fields={"VARIABLE": ["보스쿨다운", V_BCD]})
    chain([(bc_b1, bs[bc_b1]), (set_bcd1, bs[set_bcd1])])
    if_p1f = gen(); bs[if_p1f] = mk("control_if",
        inputs={"CONDITION": [2, c_isp1], "SUBSTACK": [2, bc_b1]})
    bs[c_isp1]["parent"] = if_p1f
    bs[bc_b1]["parent"] = if_p1f

    # If 현재페이즈=2 → broadcast 보스사격2 + 보스쿨다운=20
    ph_v2 = vrep("현재페이즈", V_PHASE)
    c_isp2 = cmp_op("operator_equals", ph_v2, 2)
    bm_b2 = gen(); bs[bm_b2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["보스사격2", BR_BFIRE2]}, shadow=True)
    bc_b2 = gen(); bs[bc_b2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_b2]})
    bs[bm_b2]["parent"] = bc_b2
    set_bcd2 = gen(); bs[set_bcd2] = mk("data_setvariableto",
        inputs={"VALUE": num(20)}, fields={"VARIABLE": ["보스쿨다운", V_BCD]})
    chain([(bc_b2, bs[bc_b2]), (set_bcd2, bs[set_bcd2])])
    if_p2f = gen(); bs[if_p2f] = mk("control_if",
        inputs={"CONDITION": [2, c_isp2], "SUBSTACK": [2, bc_b2]})
    bs[c_isp2]["parent"] = if_p2f
    bs[bc_b2]["parent"] = if_p2f

    # If 현재페이즈=3 → broadcast 보스사격3 + 보스쿨다운=30
    ph_v3 = vrep("현재페이즈", V_PHASE)
    c_isp3 = cmp_op("operator_equals", ph_v3, 3)
    bm_b3 = gen(); bs[bm_b3] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["보스사격3", BR_BFIRE3]}, shadow=True)
    bc_b3 = gen(); bs[bc_b3] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_b3]})
    bs[bm_b3]["parent"] = bc_b3
    set_bcd3 = gen(); bs[set_bcd3] = mk("data_setvariableto",
        inputs={"VALUE": num(30)}, fields={"VARIABLE": ["보스쿨다운", V_BCD]})
    chain([(bc_b3, bs[bc_b3]), (set_bcd3, bs[set_bcd3])])
    if_p3f = gen(); bs[if_p3f] = mk("control_if",
        inputs={"CONDITION": [2, c_isp3], "SUBSTACK": [2, bc_b3]})
    bs[c_isp3]["parent"] = if_p3f
    bs[bc_b3]["parent"] = if_p3f

    # chain inside the "can fire" if:
    chain([(set_bbx, bs[set_bbx]), (set_bby, bs[set_bby]),
           (if_p1f, bs[if_p1f]), (if_p2f, bs[if_p2f]), (if_p3f, bs[if_p3f])])
    if_canf = gen(); bs[if_canf] = mk("control_if",
        inputs={"CONDITION": [2, c_canf], "SUBSTACK": [2, set_bbx]})
    bs[c_canf]["parent"] = if_canf
    bs[set_bbx]["parent"] = if_canf

    w_ctr = gen(); bs[w_ctr] = mk("control_wait", inputs={"DURATION": num(0.04)})
    chain([(if_pcd, bs[if_pcd]), (if_bcd, bs[if_bcd]), (if_inv, bs[if_inv]),
           (if_canf, bs[if_canf]), (w_ctr, bs[w_ctr])])
    fe_ctr = gen(); bs[fe_ctr] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_pcd]})
    bs[if_pcd]["parent"] = fe_ctr
    chain([(h3, bs[h3]), (fe_ctr, bs[fe_ctr])])

    return bs

# ============================================================
#  PLAYER
# ============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- flag: init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-140)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["don't rotate", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # --- forever (좌우 이동) ---
    # left arrow + x > -210 + state=1 → change x by -4
    l_menu = gen(); bs[l_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    l_press = gen(); bs[l_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, l_menu]})
    bs[l_menu]["parent"] = l_press

    xp_l = gen(); bs[xp_l] = mk("motion_xposition")
    c_xgt = cmp_op("operator_gt", xp_l, -210)
    state_v_lm = vrep("게임상태", V_STATE)
    c_play_l = cmp_op("operator_equals", state_v_lm, 1)
    c_la = bool_op("operator_and", l_press, c_xgt)
    c_lall = bool_op("operator_and", c_la, c_play_l)

    cx_neg = gen(); bs[cx_neg] = mk("motion_changexby", inputs={"DX": num(-4)})
    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION": [2, c_lall], "SUBSTACK": [2, cx_neg]})
    bs[c_lall]["parent"] = if_l
    bs[cx_neg]["parent"] = if_l

    # right arrow + x < 210 + state=1 → change x by +4
    r_menu = gen(); bs[r_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    r_press = gen(); bs[r_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, r_menu]})
    bs[r_menu]["parent"] = r_press

    xp_r = gen(); bs[xp_r] = mk("motion_xposition")
    c_xlt = cmp_op("operator_lt", xp_r, 210)
    state_v_rm = vrep("게임상태", V_STATE)
    c_play_r = cmp_op("operator_equals", state_v_rm, 1)
    c_ra = bool_op("operator_and", r_press, c_xlt)
    c_rall = bool_op("operator_and", c_ra, c_play_r)

    cx_pos = gen(); bs[cx_pos] = mk("motion_changexby", inputs={"DX": num(4)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION": [2, c_rall], "SUBSTACK": [2, cx_pos]})
    bs[c_rall]["parent"] = if_r
    bs[cx_pos]["parent"] = if_r

    w_mv = gen(); bs[w_mv] = mk("control_wait", inputs={"DURATION": num(0.03)})
    chain([(if_l, bs[if_l]), (if_r, bs[if_r]), (w_mv, bs[w_mv])])
    fe_mv = gen(); bs[fe_mv] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_l]})
    bs[if_l]["parent"] = fe_mv

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (pd, bs[pd]), (front, bs[front]),
           (fe_mv, bs[fe_mv])])

    # --- forever (fire) ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)
    sp_menu = gen(); bs[sp_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sp_press = gen(); bs[sp_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, sp_menu]})
    bs[sp_menu]["parent"] = sp_press

    pcd_v = vrep("플쿨다운", V_PCD)
    cond_cd0 = cmp_op("operator_equals", pcd_v, 0)
    state_v2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v2, 1)
    cond_a = bool_op("operator_and", sp_press, cond_cd0)
    cond_can_fire = bool_op("operator_and", cond_a, cond_play)

    xp_s = gen(); bs[xp_s] = mk("motion_xposition")
    set_bx = gen(); bs[set_bx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xp_s)}, fields={"VARIABLE": ["플총X", V_PBX]})
    bs[xp_s]["parent"] = set_bx
    yp_s = gen(); bs[yp_s] = mk("motion_yposition")
    add_y = op("operator_add", yp_s, 15, "NUM1", "NUM2")
    set_by = gen(); bs[set_by] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_y)}, fields={"VARIABLE": ["플총Y", V_PBY]})
    bs[add_y]["parent"] = set_by

    pitch_fire = gen(); bs[pitch_fire] = mk("sound_seteffectto",
        inputs={"VALUE": num(200)}, fields={"EFFECT": ["PITCH", None]})
    snm_fire = gen(); bs[snm_fire] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_fire = gen(); bs[snd_fire] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_fire]})
    bs[snm_fire]["parent"] = snd_fire

    bm_pf = gen(); bs[bm_pf] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["플사격", BR_PFIRE]}, shadow=True)
    bc_pf = gen(); bs[bc_pf] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_pf]})
    bs[bm_pf]["parent"] = bc_pf

    set_pcd = gen(); bs[set_pcd] = mk("data_setvariableto",
        inputs={"VALUE": num(11)}, fields={"VARIABLE": ["플쿨다운", V_PCD]})

    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]),
           (pitch_fire, bs[pitch_fire]), (snd_fire, bs[snd_fire]),
           (bc_pf, bs[bc_pf]), (set_pcd, bs[set_pcd])])

    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, cond_can_fire], "SUBSTACK": [2, set_bx]})
    bs[cond_can_fire]["parent"] = if_fire
    bs[set_bx]["parent"] = if_fire

    w_fire = gen(); bs[w_fire] = mk("control_wait", inputs={"DURATION": num(0.04)})
    chain([(if_fire, bs[if_fire]), (w_fire, bs[w_fire])])
    fe_fire = gen(); bs[fe_fire] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_fire]})
    bs[if_fire]["parent"] = fe_fire
    chain([(h2, bs[h2]), (fe_fire, bs[fe_fire])])

    # --- forever (hit detection: touching 보스탄 OR 보스) ---
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)
    tm_bb = gen(); bs[tm_bb] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["보스탄", None]}, shadow=True)
    tc_bb = gen(); bs[tc_bb] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_bb]})
    bs[tm_bb]["parent"] = tc_bb

    tm_bs = gen(); bs[tm_bs] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["보스", None]}, shadow=True)
    tc_bs = gen(); bs[tc_bs] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_bs]})
    bs[tm_bs]["parent"] = tc_bs

    cond_any_touch = bool_op("operator_or", tc_bb, tc_bs)

    inv_v_p = vrep("무적", V_INV)
    cond_inv0 = cmp_op("operator_equals", inv_v_p, 0)
    state_v3 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state_v3, 1)
    cond_hit_ok = bool_op("operator_and", cond_any_touch, cond_inv0)
    cond_die = bool_op("operator_and", cond_hit_ok, cond_play2)

    dec_php = gen(); bs[dec_php] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["내체력", V_PHP]})
    set_inv = gen(); bs[set_inv] = mk("data_setvariableto",
        inputs={"VALUE": num(12)}, fields={"VARIABLE": ["무적", V_INV]})
    pitch_hit = gen(); bs[pitch_hit] = mk("sound_seteffectto",
        inputs={"VALUE": num(-200)}, fields={"EFFECT": ["PITCH", None]})
    snm_h = gen(); bs[snm_h] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_h = gen(); bs[snd_h] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_h]})
    bs[snm_h]["parent"] = snd_h

    # if 내체력 ≤ 0 → 게임상태=0, hide
    php_v = vrep("내체력", V_PHP)
    cond_dead = cmp_op("operator_lt", php_v, 1)
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    hide_p = gen(); bs[hide_p] = mk("looks_hide")
    chain([(set_state0, bs[set_state0]), (hide_p, bs[hide_p])])
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, set_state0]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state0]["parent"] = if_dead

    chain([(dec_php, bs[dec_php]), (set_inv, bs[set_inv]),
           (pitch_hit, bs[pitch_hit]), (snd_h, bs[snd_h]),
           (if_dead, bs[if_dead])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION": [2, cond_die], "SUBSTACK": [2, dec_php]})
    bs[cond_die]["parent"] = if_hit
    bs[dec_php]["parent"] = if_hit

    w_hit = gen(); bs[w_hit] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_hit, bs[if_hit]), (w_hit, bs[w_hit])])
    fe_hit = gen(); bs[fe_hit] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_hit]})
    bs[if_hit]["parent"] = fe_hit
    chain([(h3, bs[h3]), (fe_hit, bs[fe_hit])])

    return bs

# ============================================================
#  BOSS
# ============================================================
def build_boss_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- flag: init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(110)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["don't rotate", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # --- forever (좌우 왕복 + 보스X/Y 갱신) ---
    state_v = vrep("게임상태", V_STATE)
    c_alive = cmp_op("operator_equals", state_v, 1)

    # 보스X = self.x, 보스Y = self.y
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    set_bx = gen(); bs[set_bx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xp_b)}, fields={"VARIABLE": ["보스X", V_BX]})
    bs[xp_b]["parent"] = set_bx
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    set_by = gen(); bs[set_by] = mk("data_setvariableto",
        inputs={"VALUE": slot(yp_b)}, fields={"VARIABLE": ["보스Y", V_BY]})
    bs[yp_b]["parent"] = set_by

    # move 보스속도
    bspd_v = vrep("보스속도", V_BSPD)
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": slot(bspd_v)})
    bs[bspd_v]["parent"] = mv

    # if 방향=90 AND x > 170 → 방향=−90
    dir_r = gen(); bs[dir_r] = mk("motion_direction")
    c_dir90 = cmp_op("operator_equals", dir_r, 90)
    xp_r = gen(); bs[xp_r] = mk("motion_xposition")
    c_xhi = cmp_op("operator_gt", xp_r, 170)
    c_right_edge = bool_op("operator_and", c_dir90, c_xhi)
    set_dir_neg = gen(); bs[set_dir_neg] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(-90)})
    if_r_edge = gen(); bs[if_r_edge] = mk("control_if",
        inputs={"CONDITION": [2, c_right_edge], "SUBSTACK": [2, set_dir_neg]})
    bs[c_right_edge]["parent"] = if_r_edge
    bs[set_dir_neg]["parent"] = if_r_edge

    # if 방향=−90 AND x < −170 → 방향=90
    dir_l = gen(); bs[dir_l] = mk("motion_direction")
    c_dirneg = cmp_op("operator_equals", dir_l, -90)
    xp_l = gen(); bs[xp_l] = mk("motion_xposition")
    c_xlo = cmp_op("operator_lt", xp_l, -170)
    c_left_edge = bool_op("operator_and", c_dirneg, c_xlo)
    set_dir_pos = gen(); bs[set_dir_pos] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(90)})
    if_l_edge = gen(); bs[if_l_edge] = mk("control_if",
        inputs={"CONDITION": [2, c_left_edge], "SUBSTACK": [2, set_dir_pos]})
    bs[c_left_edge]["parent"] = if_l_edge
    bs[set_dir_pos]["parent"] = if_l_edge

    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]),
           (mv, bs[mv]), (if_r_edge, bs[if_r_edge]), (if_l_edge, bs[if_l_edge])])
    if_mv = gen(); bs[if_mv] = mk("control_if",
        inputs={"CONDITION": [2, c_alive], "SUBSTACK": [2, set_bx]})
    bs[c_alive]["parent"] = if_mv
    bs[set_bx]["parent"] = if_mv

    w_mv = gen(); bs[w_mv] = mk("control_wait", inputs={"DURATION": num(0.04)})
    chain([(if_mv, bs[if_mv]), (w_mv, bs[w_mv])])
    fe_mv = gen(); bs[fe_mv] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_mv]})
    bs[if_mv]["parent"] = fe_mv

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (pd, bs[pd]), (front, bs[front]),
           (fe_mv, bs[fe_mv])])

    # --- forever (hit detection: touching 플레이어총알) ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)
    tm_a = gen(); bs[tm_a] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["플레이어총알", None]}, shadow=True)
    tc_a = gen(); bs[tc_a] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_a]})
    bs[tm_a]["parent"] = tc_a

    state_v3 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state_v3, 1)
    cond_die = bool_op("operator_and", tc_a, cond_play2)

    dec_bhp = gen(); bs[dec_bhp] = mk("data_changevariableby",
        inputs={"VALUE": num(-2)}, fields={"VARIABLE": ["보스체력", V_BHP]})
    pitch_hit = gen(); bs[pitch_hit] = mk("sound_seteffectto",
        inputs={"VALUE": num(-100)}, fields={"EFFECT": ["PITCH", None]})
    snm_h = gen(); bs[snm_h] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_h = gen(); bs[snd_h] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_h]})
    bs[snm_h]["parent"] = snd_h

    bhp_v = vrep("보스체력", V_BHP)
    cond_dead = cmp_op("operator_lt", bhp_v, 1)
    set_state2 = gen(); bs[set_state2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    hide_b = gen(); bs[hide_b] = mk("looks_hide")
    chain([(set_state2, bs[set_state2]), (hide_b, bs[hide_b])])
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, set_state2]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state2]["parent"] = if_dead

    w_inv = gen(); bs[w_inv] = mk("control_wait", inputs={"DURATION": num(0.08)})

    chain([(dec_bhp, bs[dec_bhp]), (pitch_hit, bs[pitch_hit]), (snd_h, bs[snd_h]),
           (if_dead, bs[if_dead]), (w_inv, bs[w_inv])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION": [2, cond_die], "SUBSTACK": [2, dec_bhp]})
    bs[cond_die]["parent"] = if_hit
    bs[dec_bhp]["parent"] = if_hit

    w_hit = gen(); bs[w_hit] = mk("control_wait", inputs={"DURATION": num(0.03)})
    chain([(if_hit, bs[if_hit]), (w_hit, bs[w_hit])])
    fe_hit = gen(); bs[fe_hit] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_hit]})
    bs[if_hit]["parent"] = fe_hit
    chain([(h2, bs[h2]), (fe_hit, bs[fe_hit])])

    return bs

# ============================================================
#  PLAYER BULLET
# ============================================================
def build_pbullet_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # flag init
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["don't rotate", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    # on 플사격 → create clone
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["플사격", BR_PFIRE]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(h2, bs[h2]), (cclone, bs[cclone])])

    # clone start
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=400)
    bx_v = vrep("플총X", V_PBX)
    by_v = vrep("플총Y", V_PBY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g
    point_up = gen(); bs[point_up] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(0)})
    show = gen(); bs[show] = mk("looks_show")

    # repeat 35 body
    cy = gen(); bs[cy] = mk("motion_changeyby", inputs={"DY": num(12)})
    # if y > 180 → hide + delete
    yp_t = gen(); bs[yp_t] = mk("motion_yposition")
    c_yhi = cmp_op("operator_gt", yp_t, 180)
    hi_y = gen(); bs[hi_y] = mk("looks_hide")
    del_y = gen(); bs[del_y] = mk("control_delete_this_clone")
    chain([(hi_y, bs[hi_y]), (del_y, bs[del_y])])
    if_y = gen(); bs[if_y] = mk("control_if",
        inputs={"CONDITION": [2, c_yhi], "SUBSTACK": [2, hi_y]})
    bs[c_yhi]["parent"] = if_y
    bs[hi_y]["parent"] = if_y

    # if touching 보스 → hide + delete
    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["보스", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b]})
    bs[tm_b]["parent"] = tc_b
    hi_t = gen(); bs[hi_t] = mk("looks_hide")
    del_t = gen(); bs[del_t] = mk("control_delete_this_clone")
    chain([(hi_t, bs[hi_t]), (del_t, bs[del_t])])
    if_t = gen(); bs[if_t] = mk("control_if",
        inputs={"CONDITION": [2, tc_b], "SUBSTACK": [2, hi_t]})
    bs[tc_b]["parent"] = if_t
    bs[hi_t]["parent"] = if_t

    w_b = gen(); bs[w_b] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(cy, bs[cy]), (if_y, bs[if_y]), (if_t, bs[if_t]), (w_b, bs[w_b])])

    rep_life = gen(); bs[rep_life] = mk("control_repeat",
        inputs={"TIMES": num(35), "SUBSTACK": [2, cy]})
    bs[cy]["parent"] = rep_life

    hi_end = gen(); bs[hi_end] = mk("looks_hide")
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (point_up, bs[point_up]),
           (show, bs[show]), (rep_life, bs[rep_life]),
           (hi_end, bs[hi_end]), (del_end, bs[del_end])])

    return bs

# ============================================================
#  BOSS BULLET (3 phase handlers + clone start)
# ============================================================
def build_bbullet_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # flag init
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    # ----- Phase 1: 보스사격1 받으면 → repeat 3 (i=0..2) -----
    h_p1 = gen(); bs[h_p1] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["보스사격1", BR_BFIRE1]})
    set_i0_a = gen(); bs[set_i0_a] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["i카운터", V_I]})

    # body: 보스탄방향 = 180 + (i-1)*20 ; create clone; wait 0.04; i++
    i_v_a = vrep("i카운터", V_I)
    sub1_a = op("operator_subtract", i_v_a, 1, "NUM1", "NUM2")
    mul_a = op("operator_multiply", sub1_a, 20, "NUM1", "NUM2")
    add_a = op("operator_add", mul_a, 180, "NUM1", "NUM2")
    set_dir_a = gen(); bs[set_dir_a] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_a)}, fields={"VARIABLE": ["보스탄방향", V_BBDIR]})
    bs[add_a]["parent"] = set_dir_a

    cmenu_a = gen(); bs[cmenu_a] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone_a = gen(); bs[cclone_a] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu_a]})
    bs[cmenu_a]["parent"] = cclone_a

    w_a = gen(); bs[w_a] = mk("control_wait", inputs={"DURATION": num(0.04)})
    inc_i_a = gen(); bs[inc_i_a] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["i카운터", V_I]})
    chain([(set_dir_a, bs[set_dir_a]), (cclone_a, bs[cclone_a]),
           (w_a, bs[w_a]), (inc_i_a, bs[inc_i_a])])
    rep_a = gen(); bs[rep_a] = mk("control_repeat",
        inputs={"TIMES": num(3), "SUBSTACK": [2, set_dir_a]})
    bs[set_dir_a]["parent"] = rep_a
    chain([(h_p1, bs[h_p1]), (set_i0_a, bs[set_i0_a]), (rep_a, bs[rep_a])])

    # ----- Phase 2: 보스사격2 받으면 → repeat 5 -----
    h_p2 = gen(); bs[h_p2] = mk("event_whenbroadcastreceived", top=True, x=300, y=200,
        fields={"BROADCAST_OPTION": ["보스사격2", BR_BFIRE2]})
    set_i0_b = gen(); bs[set_i0_b] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["i카운터", V_I]})

    i_v_b = vrep("i카운터", V_I)
    sub2_b = op("operator_subtract", i_v_b, 2, "NUM1", "NUM2")
    mul_b = op("operator_multiply", sub2_b, 15, "NUM1", "NUM2")
    add_b = op("operator_add", mul_b, 180, "NUM1", "NUM2")
    set_dir_b = gen(); bs[set_dir_b] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_b)}, fields={"VARIABLE": ["보스탄방향", V_BBDIR]})
    bs[add_b]["parent"] = set_dir_b

    cmenu_b = gen(); bs[cmenu_b] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone_b = gen(); bs[cclone_b] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu_b]})
    bs[cmenu_b]["parent"] = cclone_b

    w_b = gen(); bs[w_b] = mk("control_wait", inputs={"DURATION": num(0.04)})
    inc_i_b = gen(); bs[inc_i_b] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["i카운터", V_I]})
    chain([(set_dir_b, bs[set_dir_b]), (cclone_b, bs[cclone_b]),
           (w_b, bs[w_b]), (inc_i_b, bs[inc_i_b])])
    rep_b = gen(); bs[rep_b] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK": [2, set_dir_b]})
    bs[set_dir_b]["parent"] = rep_b
    chain([(h_p2, bs[h_p2]), (set_i0_b, bs[set_i0_b]), (rep_b, bs[rep_b])])

    # ----- Phase 3: 보스사격3 받으면 → repeat 16 (원형) -----
    h_p3 = gen(); bs[h_p3] = mk("event_whenbroadcastreceived", top=True, x=600, y=200,
        fields={"BROADCAST_OPTION": ["보스사격3", BR_BFIRE3]})
    set_i0_c = gen(); bs[set_i0_c] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["i카운터", V_I]})

    i_v_c = vrep("i카운터", V_I)
    mul_c = op("operator_multiply", i_v_c, 22.5, "NUM1", "NUM2")
    set_dir_c = gen(); bs[set_dir_c] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_c)}, fields={"VARIABLE": ["보스탄방향", V_BBDIR]})
    bs[mul_c]["parent"] = set_dir_c

    cmenu_c = gen(); bs[cmenu_c] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone_c = gen(); bs[cclone_c] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu_c]})
    bs[cmenu_c]["parent"] = cclone_c

    w_c = gen(); bs[w_c] = mk("control_wait", inputs={"DURATION": num(0.02)})
    inc_i_c = gen(); bs[inc_i_c] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["i카운터", V_I]})
    chain([(set_dir_c, bs[set_dir_c]), (cclone_c, bs[cclone_c]),
           (w_c, bs[w_c]), (inc_i_c, bs[inc_i_c])])
    rep_c = gen(); bs[rep_c] = mk("control_repeat",
        inputs={"TIMES": num(16), "SUBSTACK": [2, set_dir_c]})
    bs[set_dir_c]["parent"] = rep_c
    chain([(h_p3, bs[h_p3]), (set_i0_c, bs[set_i0_c]), (rep_c, bs[rep_c])])

    # ----- Clone start (common) -----
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=600)
    bbx_v = vrep("보스탄X", V_BBX)
    bby_v = vrep("보스탄Y", V_BBY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(bbx_v), "Y": slot(bby_v)})
    bs[bbx_v]["parent"] = g; bs[bby_v]["parent"] = g
    bbdir_v = vrep("보스탄방향", V_BBDIR)
    point_b = gen(); bs[point_b] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(bbdir_v)})
    bs[bbdir_v]["parent"] = point_b
    show = gen(); bs[show] = mk("looks_show")

    # repeat 50 body
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(4)})

    # off-screen check: x>240 OR x<-240 OR y>180 OR y<-180 → hide + delete
    xpt = gen(); bs[xpt] = mk("motion_xposition")
    c_xh = cmp_op("operator_gt", xpt, 240)
    xpt2 = gen(); bs[xpt2] = mk("motion_xposition")
    c_xl = cmp_op("operator_lt", xpt2, -240)
    c_x_or = bool_op("operator_or", c_xh, c_xl)
    ypt = gen(); bs[ypt] = mk("motion_yposition")
    c_yh = cmp_op("operator_gt", ypt, 180)
    ypt2 = gen(); bs[ypt2] = mk("motion_yposition")
    c_yl = cmp_op("operator_lt", ypt2, -180)
    c_y_or = bool_op("operator_or", c_yh, c_yl)
    c_off = bool_op("operator_or", c_x_or, c_y_or)

    hi_o = gen(); bs[hi_o] = mk("looks_hide")
    del_o = gen(); bs[del_o] = mk("control_delete_this_clone")
    chain([(hi_o, bs[hi_o]), (del_o, bs[del_o])])
    if_off = gen(); bs[if_off] = mk("control_if",
        inputs={"CONDITION": [2, c_off], "SUBSTACK": [2, hi_o]})
    bs[c_off]["parent"] = if_off
    bs[hi_o]["parent"] = if_off

    # if touching 플레이어 → hide + delete
    tm_p = gen(); bs[tm_p] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["플레이어", None]}, shadow=True)
    tc_p = gen(); bs[tc_p] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_p]})
    bs[tm_p]["parent"] = tc_p
    hi_p = gen(); bs[hi_p] = mk("looks_hide")
    del_p = gen(); bs[del_p] = mk("control_delete_this_clone")
    chain([(hi_p, bs[hi_p]), (del_p, bs[del_p])])
    if_tp = gen(); bs[if_tp] = mk("control_if",
        inputs={"CONDITION": [2, tc_p], "SUBSTACK": [2, hi_p]})
    bs[tc_p]["parent"] = if_tp
    bs[hi_p]["parent"] = if_tp

    w_body = gen(); bs[w_body] = mk("control_wait", inputs={"DURATION": num(0.03)})
    chain([(mv, bs[mv]), (if_off, bs[if_off]), (if_tp, bs[if_tp]), (w_body, bs[w_body])])

    rep_life = gen(); bs[rep_life] = mk("control_repeat",
        inputs={"TIMES": num(50), "SUBSTACK": [2, mv]})
    bs[mv]["parent"] = rep_life

    hi_end = gen(); bs[hi_end] = mk("looks_hide")
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (point_b, bs[point_b]),
           (show, bs[show]), (rep_life, bs[rep_life]),
           (hi_end, bs[hi_end]), (del_end, bs[del_end])])

    return bs

# ============================================================
#  HP BAR BG (static)
# ============================================================
def build_hpbar_bg_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(155)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])
    return bs

# ============================================================
#  HP BAR FILL (size = 보스체력)
# ============================================================
def build_hpbar_fill_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    # position the left edge at x = -100 so it grows rightward; for simplicity, center at 0.
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(155)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (front, bs[front])])

    # forever: size = 보스체력; if ≤0 hide
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)
    bhp_v = vrep("보스체력", V_BHP)
    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto",
        inputs={"SIZE": slot(bhp_v)})
    bs[bhp_v]["parent"] = set_sz

    bhp_v2 = vrep("보스체력", V_BHP)
    c_dead = cmp_op("operator_lt", bhp_v2, 1)
    hi = gen(); bs[hi] = mk("looks_hide")
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, c_dead], "SUBSTACK": [2, hi]})
    bs[c_dead]["parent"] = if_dead
    bs[hi]["parent"] = if_dead

    w_b = gen(); bs[w_b] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(set_sz, bs[set_sz]), (if_dead, bs[if_dead]), (w_b, bs[w_b])])
    fe = gen(); bs[fe] = mk("control_forever",
        inputs={"SUBSTACK": [2, set_sz]})
    bs[set_sz]["parent"] = fe
    chain([(h2, bs[h2]), (fe, bs[fe])])
    return bs

# ============================================================
#  WIN / LOSE BANNERS
# ============================================================
def build_banner_blocks(target_state_value):
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
    cond_target = cmp_op("operator_equals", state_v2, target_state_value)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_target]})
    bs[cond_target]["parent"] = wait_over

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

    def save_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f: f.write(svg)
        return m

    bg_md5      = save_svg(BG_SVG)
    player_md5  = save_svg(PLAYER_SVG)
    boss_md5    = save_svg(BOSS_SVG)
    pbull_md5   = save_svg(BULLET_PLAYER_SVG)
    bbull_md5   = save_svg(BULLET_BOSS_SVG)
    hpbg_md5    = save_svg(HPBAR_BG_SVG)
    hpfill_md5  = save_svg(HPBAR_FILL_SVG)
    win_md5     = save_svg(WIN_SVG)
    lose_md5    = save_svg(LOSE_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    player_blocks   = build_player_blocks()
    boss_blocks     = build_boss_blocks()
    pbullet_blocks  = build_pbullet_blocks()
    bbullet_blocks  = build_bbullet_blocks()
    hpbg_blocks     = build_hpbar_bg_blocks()
    hpfill_blocks   = build_hpbar_fill_blocks()
    win_blocks      = build_banner_blocks(2)
    lose_blocks     = build_banner_blocks(0)

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_PHP:    ["내체력", 5],
            V_BHP:    ["보스체력", 100],
            V_STATE:  ["게임상태", 1],
            V_PCD:    ["플쿨다운", 0],
            V_BCD:    ["보스쿨다운", 30],
            V_PHASE:  ["현재페이즈", 1],
            V_BDIR:   ["보스방향", 180],
            V_BX:     ["보스X", 0],
            V_BY:     ["보스Y", 110],
            V_BSPD:   ["보스속도", 1.5],
            V_PBX:    ["플총X", 0],
            V_PBY:    ["플총Y", -125],
            V_BBX:    ["보스탄X", 0],
            V_BBY:    ["보스탄Y", 95],
            V_BBDIR:  ["보스탄방향", 180],
            V_INV:    ["무적", 0],
            V_I:      ["i카운터", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:  "게임시작",
            BR_PFIRE:  "플사격",
            BR_BFIRE1: "보스사격1",
            BR_BFIRE2: "보스사격2",
            BR_BFIRE3: "보스사격3",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "arena", "dataFormat": "svg",
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
        "costumes": [{
            "name": "ship", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": player_md5, "md5ext": f"{player_md5}.svg",
            "rotationCenterX": 18, "rotationCenterY": 20
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": True,
        "x": 0, "y": -140, "size": 70, "direction": 0,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    boss = {
        "isStage": False, "name": "보스",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": boss_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "boss", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": boss_md5, "md5ext": f"{boss_md5}.svg",
            "rotationCenterX": 80, "rotationCenterY": 50
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": 110, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    pbullet = {
        "isStage": False, "name": "플레이어총알",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pbullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "pbullet", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pbull_md5, "md5ext": f"{pbull_md5}.svg",
            "rotationCenterX": 5, "rotationCenterY": 8
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 0,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    bbullet = {
        "isStage": False, "name": "보스탄",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bbullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bbullet", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bbull_md5, "md5ext": f"{bbull_md5}.svg",
            "rotationCenterX": 7, "rotationCenterY": 7
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 180,
        "draggable": False, "rotationStyle": "all around"
    }

    hpbg = {
        "isStage": False, "name": "체력바배경",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hpbg_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "hpbg", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hpbg_md5, "md5ext": f"{hpbg_md5}.svg",
            "rotationCenterX": 105, "rotationCenterY": 11
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": True,
        "x": 0, "y": 155, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    hpfill = {
        "isStage": False, "name": "체력바채움",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hpfill_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "hpfill", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hpfill_md5, "md5ext": f"{hpfill_md5}.svg",
            "rotationCenterX": 100, "rotationCenterY": 6
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 7, "visible": True,
        "x": 0, "y": 155, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    win_banner = {
        "isStage": False, "name": "승리배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": win_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "win", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": win_md5, "md5ext": f"{win_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 80
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    lose_banner = {
        "isStage": False, "name": "패배배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": lose_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "lose", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": lose_md5, "md5ext": f"{lose_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 80
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_PHP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "내체력"}, "spriteName": None,
         "value": 5, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
        {"id": V_BHP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "보스체력"}, "spriteName": None,
         "value": 100, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_PHASE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "현재페이즈"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 1, "sliderMax": 3, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, player, boss, pbullet, bbullet, hpbg, hpfill, win_banner, lose_banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "boss-rush-builder"}
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
    print(f"  boss:     {len(boss_blocks)} blocks")
    print(f"  pbullet:  {len(pbullet_blocks)} blocks")
    print(f"  bbullet:  {len(bbullet_blocks)} blocks")
    print(f"  hpbg:     {len(hpbg_blocks)} blocks")
    print(f"  hpfill:   {len(hpfill_blocks)} blocks")
    print(f"  win:      {len(win_blocks)} blocks")
    print(f"  lose:     {len(lose_blocks)} blocks")
    total = (len(stage_blocks) + len(player_blocks) + len(boss_blocks)
             + len(pbullet_blocks) + len(bbullet_blocks)
             + len(hpbg_blocks) + len(hpfill_blocks)
             + len(win_blocks) + len(lose_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
