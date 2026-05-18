#!/usr/bin/env python3
"""Dogfight — two planes 1v1 aerial combat (rotate + constant forward + fire + AI enemy + screen wrap)."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "도그파이트.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: blue sky + clouds --------
random.seed(7)
clouds = []
for _ in range(7):
    cx = random.randint(40, 440); cy = random.randint(30, 330)
    r1 = random.randint(20, 38); r2 = random.randint(18, 32); r3 = random.randint(16, 28)
    op = random.uniform(0.70, 0.95)
    clouds.append(
        f'<g opacity="{op:.2f}">'
        f'<ellipse cx="{cx}" cy="{cy}" rx="{r1}" ry="{r1*0.55:.0f}" fill="#FFFFFF"/>'
        f'<ellipse cx="{cx-r1*0.6:.0f}" cy="{cy+4}" rx="{r2}" ry="{r2*0.5:.0f}" fill="#FFFFFF"/>'
        f'<ellipse cx="{cx+r1*0.6:.0f}" cy="{cy+5}" rx="{r3}" ry="{r3*0.5:.0f}" fill="#FFFFFF"/>'
        f'</g>'
    )
CLOUDS = "\n  ".join(clouds)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#9CC8F0"/>
      <stop offset="1" stop-color="#6FA8E2"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  {CLOUDS}
</svg>"""

# -------- Player plane (blue biplane, nose points up = direction 0) --------
def plane_svg(body, wing, accent, stripe):
    # 40x44 viewBox, top is nose
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="40" height="44" viewBox="0 0 40 44">
  <!-- tail fin -->
  <polygon points="16,38 24,38 22,44 18,44" fill="{accent}" stroke="#1a1a1a" stroke-width="1"/>
  <!-- lower wing -->
  <rect x="2" y="28" width="36" height="6" rx="2" fill="{wing}" stroke="#1a1a1a" stroke-width="1.2"/>
  <!-- fuselage -->
  <polygon points="20,2 14,10 14,36 26,36 26,10" fill="{body}" stroke="#1a1a1a" stroke-width="1.4"/>
  <!-- upper wing -->
  <rect x="4" y="14" width="32" height="6" rx="2" fill="{wing}" stroke="#1a1a1a" stroke-width="1.2"/>
  <!-- stripe -->
  <rect x="14" y="20" width="12" height="3" fill="{stripe}"/>
  <!-- cockpit -->
  <ellipse cx="20" cy="26" rx="3" ry="4" fill="#222" stroke="#FFF" stroke-width="1"/>
  <!-- propeller -->
  <rect x="13" y="0" width="14" height="2" fill="#444"/>
  <circle cx="20" cy="3" r="2" fill="#222"/>
  <!-- nose tip -->
  <polygon points="20,2 18,6 22,6" fill="#FFEB3B"/>
</svg>"""

PLANE_BLUE_SVG = plane_svg("#1E88E5", "#42A5F5", "#0D47A1", "#FFFFFF")
PLANE_RED_SVG  = plane_svg("#E53935", "#EF5350", "#B71C1C", "#FFEB3B")

# -------- Bullets --------
BULLET_BLUE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="10" height="14" viewBox="0 0 10 14">
  <ellipse cx="5" cy="7" rx="3.5" ry="6" fill="#80DEEA" stroke="#006064" stroke-width="1.3"/>
  <ellipse cx="5" cy="6" rx="1.6" ry="2.6" fill="#E0F7FA"/>
</svg>"""

BULLET_RED_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="10" height="14" viewBox="0 0 10 14">
  <ellipse cx="5" cy="7" rx="3.5" ry="6" fill="#FFCC80" stroke="#BF360C" stroke-width="1.3"/>
  <ellipse cx="5" cy="6" rx="1.6" ry="2.6" fill="#FFF3E0"/>
</svg>"""

# -------- Win / Lose banners --------
WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#0D47A1" opacity="0.95"
        stroke="#FFEB3B" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">YOU WIN!</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">적기를 격추했어요!</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#B3E5FC" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭</text>
</svg>"""

LOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#EF5350" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#EF5350" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">YOU LOSE</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">격추당했어요…</text>
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
V_PHP   = "varPHP01"
V_EHP   = "varEHP02"
V_STATE = "varState03"
V_PCD   = "varPCD04"
V_ECD   = "varECD05"
V_PBX   = "varPBX06"
V_PBY   = "varPBY07"
V_PBDIR = "varPBDir08"
V_EBX   = "varEBX09"
V_EBY   = "varEBY10"
V_EBDIR = "varEBDir11"

BR_START = "brStart01"
BR_PFIRE = "brPFire02"
BR_EFIRE = "brEFire03"

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
#  Common wrap-block builder (returns head id of a chain of 4 if-blocks)
# ============================================================
def build_wrap_chain(bs, cmp_op):
    """Builds 4 wrap if-blocks chained: x>240→-240, x<-240→240, y>180→-180, y<-180→180.
       Returns (head_id, tail_id)."""
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

    chain([(if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo])])
    return if_xhi, if_ylo

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
        (("내체력", V_PHP),    3),
        (("적체력", V_EHP),    3),
        (("게임상태", V_STATE), 1),
        (("플쿨다운", V_PCD),   0),
        (("적쿨다운", V_ECD),  30),
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

    # --- forever cooldown counter for both players ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    pcd_v = vrep("플쿨다운", V_PCD)
    c_pcd = cmp_op("operator_gt", pcd_v, 0)
    dec_pcd = gen(); bs[dec_pcd] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["플쿨다운", V_PCD]})
    if_pcd = gen(); bs[if_pcd] = mk("control_if",
        inputs={"CONDITION": [2, c_pcd], "SUBSTACK": [2, dec_pcd]})
    bs[c_pcd]["parent"] = if_pcd
    bs[dec_pcd]["parent"] = if_pcd

    ecd_v = vrep("적쿨다운", V_ECD)
    c_ecd = cmp_op("operator_gt", ecd_v, 0)
    dec_ecd = gen(); bs[dec_ecd] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["적쿨다운", V_ECD]})
    if_ecd = gen(); bs[if_ecd] = mk("control_if",
        inputs={"CONDITION": [2, c_ecd], "SUBSTACK": [2, dec_ecd]})
    bs[c_ecd]["parent"] = if_ecd
    bs[dec_ecd]["parent"] = if_ecd

    w_ctr = gen(); bs[w_ctr] = mk("control_wait", inputs={"DURATION": num(0.04)})
    chain([(if_pcd, bs[if_pcd]), (if_ecd, bs[if_ecd]), (w_ctr, bs[w_ctr])])
    fe_ctr = gen(); bs[fe_ctr] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_pcd]})
    bs[if_pcd]["parent"] = fe_ctr
    chain([(h2, bs[h2]), (fe_ctr, bs[fe_ctr])])

    return bs

# ============================================================
#  PLAYER PLANE
# ============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- flag: init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(-150), "Y": num(0)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # --- forever (controls + forward + wrap) ---
    # left arrow → turn ccw 4
    l_menu = gen(); bs[l_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    l_press = gen(); bs[l_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, l_menu]})
    bs[l_menu]["parent"] = l_press
    turn_ccw = gen(); bs[turn_ccw] = mk("motion_turnleft", inputs={"DEGREES": num(4)})
    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION": [2, l_press], "SUBSTACK": [2, turn_ccw]})
    bs[l_press]["parent"] = if_l
    bs[turn_ccw]["parent"] = if_l

    # right arrow → turn cw 4
    r_menu = gen(); bs[r_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    r_press = gen(); bs[r_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, r_menu]})
    bs[r_menu]["parent"] = r_press
    turn_cw = gen(); bs[turn_cw] = mk("motion_turnright", inputs={"DEGREES": num(4)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION": [2, r_press], "SUBSTACK": [2, turn_cw]})
    bs[r_press]["parent"] = if_r
    bs[turn_cw]["parent"] = if_r

    # if 게임상태=1 → move 3
    state_v = vrep("게임상태", V_STATE)
    c_alive = cmp_op("operator_equals", state_v, 1)
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(3)})
    if_mv = gen(); bs[if_mv] = mk("control_if",
        inputs={"CONDITION": [2, c_alive], "SUBSTACK": [2, mv]})
    bs[c_alive]["parent"] = if_mv
    bs[mv]["parent"] = if_mv

    # wrap chain
    wrap_head, wrap_tail = build_wrap_chain(bs, cmp_op)

    w_ctrl = gen(); bs[w_ctrl] = mk("control_wait", inputs={"DURATION": num(0.03)})

    chain([(if_l, bs[if_l]), (if_r, bs[if_r]), (if_mv, bs[if_mv]),
           (wrap_head, bs[wrap_head])])
    # append w_ctrl after wrap_tail
    bs[wrap_tail]["next"] = w_ctrl
    bs[w_ctrl]["parent"] = wrap_tail

    fe_ctrl = gen(); bs[fe_ctrl] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_l]})
    bs[if_l]["parent"] = fe_ctrl

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (pd, bs[pd]), (front, bs[front]),
           (fe_ctrl, bs[fe_ctrl])])

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
    set_by = gen(); bs[set_by] = mk("data_setvariableto",
        inputs={"VALUE": slot(yp_s)}, fields={"VARIABLE": ["플총Y", V_PBY]})
    bs[yp_s]["parent"] = set_by
    dir_s = gen(); bs[dir_s] = mk("motion_direction")
    set_bdir = gen(); bs[set_bdir] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_s)}, fields={"VARIABLE": ["플총방향", V_PBDIR]})
    bs[dir_s]["parent"] = set_bdir

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
        inputs={"VALUE": num(6)}, fields={"VARIABLE": ["플쿨다운", V_PCD]})

    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]), (set_bdir, bs[set_bdir]),
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

    # --- forever (hit detection: touching 적총알) ---
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)
    tm_a = gen(); bs[tm_a] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["적총알", None]}, shadow=True)
    tc_a = gen(); bs[tc_a] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_a]})
    bs[tm_a]["parent"] = tc_a

    state_v3 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state_v3, 1)
    cond_die = bool_op("operator_and", tc_a, cond_play2)

    dec_php = gen(); bs[dec_php] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["내체력", V_PHP]})
    pitch_hit = gen(); bs[pitch_hit] = mk("sound_seteffectto",
        inputs={"VALUE": num(-200)}, fields={"EFFECT": ["PITCH", None]})
    snm_h = gen(); bs[snm_h] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_h = gen(); bs[snd_h] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_h]})
    bs[snm_h]["parent"] = snd_h

    # if 내체력 <= 0 → 게임상태=0, hide
    php_v = vrep("내체력", V_PHP)
    cond_dead = cmp_op("operator_lt", php_v, 1)  # <1 means 0 or less
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    hide_p = gen(); bs[hide_p] = mk("looks_hide")
    chain([(set_state0, bs[set_state0]), (hide_p, bs[hide_p])])
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, set_state0]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state0]["parent"] = if_dead

    w_inv = gen(); bs[w_inv] = mk("control_wait", inputs={"DURATION": num(0.3)})

    chain([(dec_php, bs[dec_php]), (pitch_hit, bs[pitch_hit]), (snd_h, bs[snd_h]),
           (if_dead, bs[if_dead]), (w_inv, bs[w_inv])])

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
#  ENEMY PLANE (AI: point towards player + jitter + move + fire on cooldown)
# ============================================================
def build_enemy_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- flag: init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(150), "Y": num(0)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(-90)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # --- forever (AI rotate + forward + wrap) ---
    state_v = vrep("게임상태", V_STATE)
    c_alive = cmp_op("operator_equals", state_v, 1)

    # point towards 플레이어기
    ptm = gen(); bs[ptm] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["플레이어기", None]}, shadow=True)
    pt = gen(); bs[pt] = mk("motion_pointtowards",
        inputs={"TOWARDS": [1, ptm]})
    bs[ptm]["parent"] = pt

    # turn cw random(-15..15)
    jit = gen(); bs[jit] = mk("operator_random",
        inputs={"FROM": num(-15), "TO": num(15)})
    turn_jit = gen(); bs[turn_jit] = mk("motion_turnright",
        inputs={"DEGREES": slot(jit)})
    bs[jit]["parent"] = turn_jit

    # move 2.4
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(2.4)})

    chain([(pt, bs[pt]), (turn_jit, bs[turn_jit]), (mv, bs[mv])])

    if_ai = gen(); bs[if_ai] = mk("control_if",
        inputs={"CONDITION": [2, c_alive], "SUBSTACK": [2, pt]})
    bs[c_alive]["parent"] = if_ai
    bs[pt]["parent"] = if_ai

    # wrap chain
    wrap_head, wrap_tail = build_wrap_chain(bs, cmp_op)

    w_ai = gen(); bs[w_ai] = mk("control_wait", inputs={"DURATION": num(0.04)})

    chain([(if_ai, bs[if_ai]), (wrap_head, bs[wrap_head])])
    bs[wrap_tail]["next"] = w_ai
    bs[w_ai]["parent"] = wrap_tail

    fe_ai = gen(); bs[fe_ai] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_ai]})
    bs[if_ai]["parent"] = fe_ai

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (pd, bs[pd]), (front, bs[front]),
           (fe_ai, bs[fe_ai])])

    # --- forever (auto fire when 적쿨다운=0) ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)
    ecd_v = vrep("적쿨다운", V_ECD)
    cond_cd0 = cmp_op("operator_equals", ecd_v, 0)
    state_v2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v2, 1)
    cond_can_fire = bool_op("operator_and", cond_cd0, cond_play)

    xp_s = gen(); bs[xp_s] = mk("motion_xposition")
    set_bx = gen(); bs[set_bx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xp_s)}, fields={"VARIABLE": ["적총X", V_EBX]})
    bs[xp_s]["parent"] = set_bx
    yp_s = gen(); bs[yp_s] = mk("motion_yposition")
    set_by = gen(); bs[set_by] = mk("data_setvariableto",
        inputs={"VALUE": slot(yp_s)}, fields={"VARIABLE": ["적총Y", V_EBY]})
    bs[yp_s]["parent"] = set_by
    dir_s = gen(); bs[dir_s] = mk("motion_direction")
    set_bdir = gen(); bs[set_bdir] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_s)}, fields={"VARIABLE": ["적총방향", V_EBDIR]})
    bs[dir_s]["parent"] = set_bdir

    pitch_fire = gen(); bs[pitch_fire] = mk("sound_seteffectto",
        inputs={"VALUE": num(100)}, fields={"EFFECT": ["PITCH", None]})
    snm_fire = gen(); bs[snm_fire] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_fire = gen(); bs[snd_fire] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_fire]})
    bs[snm_fire]["parent"] = snd_fire

    bm_ef = gen(); bs[bm_ef] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적사격", BR_EFIRE]}, shadow=True)
    bc_ef = gen(); bs[bc_ef] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ef]})
    bs[bm_ef]["parent"] = bc_ef

    # 적쿨다운 = random(20..50)
    rnd_cd = gen(); bs[rnd_cd] = mk("operator_random",
        inputs={"FROM": num(20), "TO": num(50)})
    set_ecd = gen(); bs[set_ecd] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_cd)}, fields={"VARIABLE": ["적쿨다운", V_ECD]})
    bs[rnd_cd]["parent"] = set_ecd

    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]), (set_bdir, bs[set_bdir]),
           (pitch_fire, bs[pitch_fire]), (snd_fire, bs[snd_fire]),
           (bc_ef, bs[bc_ef]), (set_ecd, bs[set_ecd])])

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

    # --- forever (hit detection: touching 플레이어총알) ---
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)
    tm_a = gen(); bs[tm_a] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["플레이어총알", None]}, shadow=True)
    tc_a = gen(); bs[tc_a] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_a]})
    bs[tm_a]["parent"] = tc_a

    state_v3 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state_v3, 1)
    cond_die = bool_op("operator_and", tc_a, cond_play2)

    dec_ehp = gen(); bs[dec_ehp] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["적체력", V_EHP]})
    pitch_hit = gen(); bs[pitch_hit] = mk("sound_seteffectto",
        inputs={"VALUE": num(-100)}, fields={"EFFECT": ["PITCH", None]})
    snm_h = gen(); bs[snm_h] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_h = gen(); bs[snd_h] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_h]})
    bs[snm_h]["parent"] = snd_h

    ehp_v = vrep("적체력", V_EHP)
    cond_dead = cmp_op("operator_lt", ehp_v, 1)
    set_state2 = gen(); bs[set_state2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    hide_e = gen(); bs[hide_e] = mk("looks_hide")
    chain([(set_state2, bs[set_state2]), (hide_e, bs[hide_e])])
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, set_state2]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state2]["parent"] = if_dead

    w_inv = gen(); bs[w_inv] = mk("control_wait", inputs={"DURATION": num(0.3)})

    chain([(dec_ehp, bs[dec_ehp]), (pitch_hit, bs[pitch_hit]), (snd_h, bs[snd_h]),
           (if_dead, bs[if_dead]), (w_inv, bs[w_inv])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION": [2, cond_die], "SUBSTACK": [2, dec_ehp]})
    bs[cond_die]["parent"] = if_hit
    bs[dec_ehp]["parent"] = if_hit

    w_hit = gen(); bs[w_hit] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_hit, bs[if_hit]), (w_hit, bs[w_hit])])
    fe_hit = gen(); bs[fe_hit] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_hit]})
    bs[if_hit]["parent"] = fe_hit
    chain([(h3, bs[h3]), (fe_hit, bs[fe_hit])])

    return bs

# ============================================================
#  BULLET BUILDER (generic for player/enemy)
# ============================================================
def build_bullet_blocks(broadcast_name, broadcast_id,
                         pos_x_var_name, pos_x_var_id,
                         pos_y_var_name, pos_y_var_id,
                         dir_var_name, dir_var_id,
                         target_sprite_name, move_steps):
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # flag init
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    # on broadcast → create clone of myself
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": [broadcast_name, broadcast_id]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(h2, bs[h2]), (cclone, bs[cclone])])

    # clone start
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=400)
    bx_v = vrep(pos_x_var_name, pos_x_var_id)
    by_v = vrep(pos_y_var_name, pos_y_var_id)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g
    bdir_v = vrep(dir_var_name, dir_var_id)
    point_b = gen(); bs[point_b] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(bdir_v)})
    bs[bdir_v]["parent"] = point_b
    show = gen(); bs[show] = mk("looks_show")

    # body inside repeat 50
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(move_steps)})
    # wrap chain
    wrap_head, wrap_tail = build_wrap_chain(bs, cmp_op)

    # if touching target → hide + delete (stop)
    tm_a = gen(); bs[tm_a] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": [target_sprite_name, None]}, shadow=True)
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

    # chain: mv → wrap_head … wrap_tail → if_hit → w_b
    chain([(mv, bs[mv]), (wrap_head, bs[wrap_head])])
    bs[wrap_tail]["next"] = if_hit
    bs[if_hit]["parent"] = wrap_tail
    chain([(if_hit, bs[if_hit]), (w_b, bs[w_b])])

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
#  WIN / LOSE BANNERS
# ============================================================
def build_banner_blocks(target_state_value):
    """target_state_value: 2 for win, 0 for lose"""
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

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f: f.write(BG_SVG)
    pb_md5 = md5_bytes(PLANE_BLUE_SVG.encode("utf-8"))
    with open(f"{WORK}/{pb_md5}.svg", "w", encoding="utf-8") as f: f.write(PLANE_BLUE_SVG)
    pr_md5 = md5_bytes(PLANE_RED_SVG.encode("utf-8"))
    with open(f"{WORK}/{pr_md5}.svg", "w", encoding="utf-8") as f: f.write(PLANE_RED_SVG)
    bb_md5 = md5_bytes(BULLET_BLUE_SVG.encode("utf-8"))
    with open(f"{WORK}/{bb_md5}.svg", "w", encoding="utf-8") as f: f.write(BULLET_BLUE_SVG)
    br_md5 = md5_bytes(BULLET_RED_SVG.encode("utf-8"))
    with open(f"{WORK}/{br_md5}.svg", "w", encoding="utf-8") as f: f.write(BULLET_RED_SVG)
    win_md5 = md5_bytes(WIN_SVG.encode("utf-8"))
    with open(f"{WORK}/{win_md5}.svg", "w", encoding="utf-8") as f: f.write(WIN_SVG)
    lose_md5 = md5_bytes(LOSE_SVG.encode("utf-8"))
    with open(f"{WORK}/{lose_md5}.svg", "w", encoding="utf-8") as f: f.write(LOSE_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks   = build_stage_blocks()
    player_blocks  = build_player_blocks()
    enemy_blocks   = build_enemy_blocks()
    pbullet_blocks = build_bullet_blocks(
        "플사격", BR_PFIRE,
        "플총X", V_PBX, "플총Y", V_PBY, "플총방향", V_PBDIR,
        "적기", 9)
    ebullet_blocks = build_bullet_blocks(
        "적사격", BR_EFIRE,
        "적총X", V_EBX, "적총Y", V_EBY, "적총방향", V_EBDIR,
        "플레이어기", 7)
    win_blocks  = build_banner_blocks(2)
    lose_blocks = build_banner_blocks(0)

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_PHP:   ["내체력", 3],
            V_EHP:   ["적체력", 3],
            V_STATE: ["게임상태", 1],
            V_PCD:   ["플쿨다운", 0],
            V_ECD:   ["적쿨다운", 30],
            V_PBX:   ["플총X", 0],
            V_PBY:   ["플총Y", 0],
            V_PBDIR: ["플총방향", 90],
            V_EBX:   ["적총X", 0],
            V_EBY:   ["적총Y", 0],
            V_EBDIR: ["적총방향", -90],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_PFIRE: "플사격",
            BR_EFIRE: "적사격",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "하늘", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    player = {
        "isStage": False, "name": "플레이어기",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": player_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "plane_blue", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pb_md5, "md5ext": f"{pb_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 22
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": -150, "y": 0, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    enemy = {
        "isStage": False, "name": "적기",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "plane_red", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pr_md5, "md5ext": f"{pr_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 22
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": True,
        "x": 150, "y": 0, "size": 60, "direction": -90,
        "draggable": False, "rotationStyle": "all around"
    }

    pbullet = {
        "isStage": False, "name": "플레이어총알",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pbullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bullet_blue", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bb_md5, "md5ext": f"{bb_md5}.svg",
            "rotationCenterX": 5, "rotationCenterY": 7
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    ebullet = {
        "isStage": False, "name": "적총알",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ebullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bullet_red", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": br_md5, "md5ext": f"{br_md5}.svg",
            "rotationCenterX": 5, "rotationCenterY": 7
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
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
        "volume": 100, "layerOrder": 7, "visible": False,
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
        "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_PHP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "내체력"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
        {"id": V_EHP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "적체력"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, player, enemy, pbullet, ebullet, win_banner, lose_banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "dogfight-builder"}
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
    print(f"  enemy:    {len(enemy_blocks)} blocks")
    print(f"  pbullet:  {len(pbullet_blocks)} blocks")
    print(f"  ebullet:  {len(ebullet_blocks)} blocks")
    print(f"  win:      {len(win_blocks)} blocks")
    print(f"  lose:     {len(lose_blocks)} blocks")
    total = (len(stage_blocks) + len(player_blocks) + len(enemy_blocks)
             + len(pbullet_blocks) + len(ebullet_blocks)
             + len(win_blocks) + len(lose_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
