#!/usr/bin/env python3
"""Alien Invasion — Galaga/Space Invaders style shoot-em-up."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "외계인_침공.sb3")

# -------- Background SVG: dark space with nebulae and stars --------
random.seed(42)
star_paths = []
for _ in range(80):
    x = random.randint(5, 475)
    y = random.randint(5, 355)
    r = random.choice([0.6, 0.9, 1.1, 1.1, 1.4, 1.8])
    op = round(random.uniform(0.4, 1.0), 2)
    star_paths.append(f'<circle cx="{x}" cy="{y}" r="{r}" opacity="{op}"/>')
STARS = "\n    ".join(star_paths)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <radialGradient id="space" cx="0.5" cy="0.5" r="0.8">
      <stop offset="0%"   stop-color="#1A1A3E"/>
      <stop offset="60%"  stop-color="#0F0F2A"/>
      <stop offset="100%" stop-color="#06061A"/>
    </radialGradient>
  </defs>
  <rect width="480" height="360" fill="url(#space)"/>
  <ellipse cx="380" cy="80"  rx="110" ry="45" fill="#5E35B1" opacity="0.22"/>
  <ellipse cx="100" cy="280" rx="80"  ry="30" fill="#1E88E5" opacity="0.18"/>
  <ellipse cx="240" cy="200" rx="160" ry="20" fill="#7E57C2" opacity="0.10"/>
  <g fill="white">
    {STARS}
  </g>
</svg>"""

# -------- Player bullet: small yellow streak --------
P_BULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="6" height="14" viewBox="0 0 6 14">
  <rect width="6" height="14" rx="3" fill="#FFEB3B"/>
  <rect x="1.5" y="2" width="3" height="10" rx="1.5" fill="#FFFFFF" opacity="0.6"/>
</svg>"""

# -------- Enemy bullet: small red streak --------
E_BULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="7" height="14" viewBox="0 0 7 14">
  <rect width="7" height="14" rx="3.5" fill="#F44336"/>
  <rect x="2" y="2" width="3" height="10" rx="1.5" fill="#FFCDD2" opacity="0.6"/>
</svg>"""

# -------- Game Over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.88"
        stroke="#FF1744" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#FF1744" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">▶ 다시 시작하기</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#FFB74D" font-family="Arial, Helvetica, sans-serif"
        font-size="14">최종 점수는 좌상단 모니터 확인</text>
</svg>"""

def rotate_svg(svg_content, degrees, cx, cy):
    """Wrap SVG inner content in a <g transform="rotate(...)"> for visual rotation."""
    open_end = svg_content.find('>') + 1
    close_start = svg_content.rfind('</svg>')
    inner = svg_content[open_end:close_start]
    return (svg_content[:open_end] +
            f'<g transform="rotate({degrees} {cx} {cy})">' +
            inner + '</g>' + svg_content[close_start:])

# -------- helpers --------
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

# Variable / broadcast IDs
V_SCORE = "varScore01"
V_LIFE  = "varLife02"
V_WAVE  = "varWave03"
V_STATE = "varState04"
V_FX    = "varFX05"
V_FY    = "varFY06"
V_DIR   = "varDir07"
V_SPEED = "varSpeed08"
V_ECNT  = "varECnt09"
V_FRX   = "varFRX10"     # spawn x for enemy bullet
V_FRY   = "varFRY11"
V_SX    = "varSX12"      # enemy local: formation slot x
V_SY    = "varSY13"      # enemy local: formation slot y

BR_START   = "brStart01"
BR_SPAWN   = "brSpawn02"
BR_NEXT    = "brNext03"
BR_OVER    = "brOver04"

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
    def bool_and(a, b_):
        bid = gen()
        bs[bid] = mk("operator_and", inputs={"OPERAND1":[2,a],"OPERAND2":[2,b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid
        return bid
    return vrep, op, cmp_op, bool_and

def broadcast_block(name, bid_const):
    """Returns (broadcast_block_id, dict). Emits an event_broadcast with the given target."""
    pass  # handled inline

# ==============================================================
#  STAGE blocks
# ==============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # === when flag clicked: init + start ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    s_score = gen(); bs[s_score] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점수", V_SCORE]})
    s_life = gen(); bs[s_life] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["라이프", V_LIFE]})
    s_wave = gen(); bs[s_wave] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_WAVE]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    s_speed = gen(); bs[s_speed] = mk("data_setvariableto",
        inputs={"VALUE": num(1.5)}, fields={"VARIABLE": ["적_속도", V_SPEED]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_life,bs[s_life]),(s_wave,bs[s_wave]),
           (s_state,bs[s_state]),(s_speed,bs[s_speed]),(bc_start,bs[bc_start])])

    # === on 게임시작: setup formation values, broadcast 적생성, run formation loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    s_fx = gen(); bs[s_fx] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["진영X", V_FX]})
    s_fy = gen(); bs[s_fy] = mk("data_setvariableto",
        inputs={"VALUE": num(130)}, fields={"VARIABLE": ["진영Y", V_FY]})
    s_dir = gen(); bs[s_dir] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["적_방향", V_DIR]})
    s_ecnt = gen(); bs[s_ecnt] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["적수", V_ECNT]})

    bm_spawn = gen(); bs[bm_spawn] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]}, shadow=True)
    bc_spawn = gen(); bs[bc_spawn] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_spawn]})
    bs[bm_spawn]["parent"] = bc_spawn

    # repeat until 게임상태=0: formation movement
    state_var = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_var, 0)

    # body: change 진영X by 적_방향 * 적_속도
    dir_var = vrep("적_방향", V_DIR)
    speed_var = vrep("적_속도", V_SPEED)
    step = op("operator_multiply", dir_var, speed_var)
    chg_fx = gen(); bs[chg_fx] = mk("data_changevariableby",
        inputs={"VALUE": slot(step)}, fields={"VARIABLE": ["진영X", V_FX]})
    bs[step]["parent"] = chg_fx

    # if 진영X > 80 → flip + drop + clamp
    fx_v1 = vrep("진영X", V_FX)
    cond_right = cmp_op("operator_gt", fx_v1, 80)
    set_dir_neg = gen(); bs[set_dir_neg] = mk("data_setvariableto",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["적_방향", V_DIR]})
    chg_fy_a = gen(); bs[chg_fy_a] = mk("data_changevariableby",
        inputs={"VALUE": num(-15)}, fields={"VARIABLE": ["진영Y", V_FY]})
    set_fx_max = gen(); bs[set_fx_max] = mk("data_setvariableto",
        inputs={"VALUE": num(80)}, fields={"VARIABLE": ["진영X", V_FX]})
    chain([(set_dir_neg,bs[set_dir_neg]),(chg_fy_a,bs[chg_fy_a]),(set_fx_max,bs[set_fx_max])])
    if_right = gen(); bs[if_right] = mk("control_if",
        inputs={"CONDITION":[2,cond_right], "SUBSTACK":[2,set_dir_neg]})
    bs[cond_right]["parent"] = if_right
    bs[set_dir_neg]["parent"] = if_right

    # if 진영X < -80 → flip + drop + clamp
    fx_v2 = vrep("진영X", V_FX)
    cond_left = cmp_op("operator_lt", fx_v2, -80)
    set_dir_pos = gen(); bs[set_dir_pos] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["적_방향", V_DIR]})
    chg_fy_b = gen(); bs[chg_fy_b] = mk("data_changevariableby",
        inputs={"VALUE": num(-15)}, fields={"VARIABLE": ["진영Y", V_FY]})
    set_fx_min = gen(); bs[set_fx_min] = mk("data_setvariableto",
        inputs={"VALUE": num(-80)}, fields={"VARIABLE": ["진영X", V_FX]})
    chain([(set_dir_pos,bs[set_dir_pos]),(chg_fy_b,bs[chg_fy_b]),(set_fx_min,bs[set_fx_min])])
    if_left = gen(); bs[if_left] = mk("control_if",
        inputs={"CONDITION":[2,cond_left], "SUBSTACK":[2,set_dir_pos]})
    bs[cond_left]["parent"] = if_left
    bs[set_dir_pos]["parent"] = if_left

    # if 진영Y < -130 → game over (reached player line)
    fy_v = vrep("진영Y", V_FY)
    cond_floor = cmp_op("operator_lt", fy_v, -130)
    set_state_0 = gen(); bs[set_state_0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_floor = gen(); bs[if_floor] = mk("control_if",
        inputs={"CONDITION":[2,cond_floor], "SUBSTACK":[2,set_state_0]})
    bs[cond_floor]["parent"] = if_floor
    bs[set_state_0]["parent"] = if_floor

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.04)})

    chain([(chg_fx,bs[chg_fx]),(if_right,bs[if_right]),(if_left,bs[if_left]),
           (if_floor,bs[if_floor]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,chg_fx]})
    bs[cond_over]["parent"] = rep_until
    bs[chg_fx]["parent"] = rep_until

    chain([(h2,bs[h2]),(s_fx,bs[s_fx]),(s_fy,bs[s_fy]),(s_dir,bs[s_dir]),
           (s_ecnt,bs[s_ecnt]),(bc_spawn,bs[bc_spawn]),(rep_until,bs[rep_until])])

    # === on 다음웨이브: speed up + reset formation + spawn ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=600,
        fields={"BROADCAST_OPTION": ["다음웨이브", BR_NEXT]})
    chg_wave = gen(); bs[chg_wave] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_WAVE]})
    chg_speed = gen(); bs[chg_speed] = mk("data_changevariableby",
        inputs={"VALUE": num(0.5)}, fields={"VARIABLE": ["적_속도", V_SPEED]})
    r_fx = gen(); bs[r_fx] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["진영X", V_FX]})
    r_fy = gen(); bs[r_fy] = mk("data_setvariableto",
        inputs={"VALUE": num(130)}, fields={"VARIABLE": ["진영Y", V_FY]})
    r_dir = gen(); bs[r_dir] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["적_방향", V_DIR]})
    bm_sp2 = gen(); bs[bm_sp2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]}, shadow=True)
    bc_sp2 = gen(); bs[bc_sp2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp2]})
    bs[bm_sp2]["parent"] = bc_sp2

    chain([(h3,bs[h3]),(chg_wave,bs[chg_wave]),(chg_speed,bs[chg_speed]),
           (r_fx,bs[r_fx]),(r_fy,bs[r_fy]),(r_dir,bs[r_dir]),(bc_sp2,bs[bc_sp2])])

    return bs

# ==============================================================
#  PLAYER (우주선) blocks
# ==============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # === when flag clicked: init position ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(0), "Y": num(-150)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(140)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(sh,bs[sh])])

    # === movement loop on 게임시작 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # repeat until 게임상태=0:
    state_var = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_var, 0)

    # body: check ← key, change x
    key_l = gen(); bs[key_l] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    sense_l = gen(); bs[sense_l] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_l]})
    bs[key_l]["parent"] = sense_l
    chx_l = gen(); bs[chx_l] = mk("motion_changexby", inputs={"DX": num(-6)})
    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION":[2,sense_l], "SUBSTACK":[2,chx_l]})
    bs[sense_l]["parent"] = if_l
    bs[chx_l]["parent"] = if_l

    key_r = gen(); bs[key_r] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    sense_r = gen(); bs[sense_r] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_r]})
    bs[key_r]["parent"] = sense_r
    chx_r = gen(); bs[chx_r] = mk("motion_changexby", inputs={"DX": num(6)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION":[2,sense_r], "SUBSTACK":[2,chx_r]})
    bs[sense_r]["parent"] = if_r
    bs[chx_r]["parent"] = if_r

    # clamp x to [-220, 220]
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    cond_xmin = cmp_op("operator_lt", xp1, -220)
    set_xmin = gen(); bs[set_xmin] = mk("motion_setx", inputs={"X": num(-220)})
    if_xmin = gen(); bs[if_xmin] = mk("control_if",
        inputs={"CONDITION":[2,cond_xmin], "SUBSTACK":[2,set_xmin]})
    bs[cond_xmin]["parent"] = if_xmin
    bs[set_xmin]["parent"] = if_xmin
    bs[xp1]["parent"] = cond_xmin

    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    cond_xmax = cmp_op("operator_gt", xp2, 220)
    set_xmax = gen(); bs[set_xmax] = mk("motion_setx", inputs={"X": num(220)})
    if_xmax = gen(); bs[if_xmax] = mk("control_if",
        inputs={"CONDITION":[2,cond_xmax], "SUBSTACK":[2,set_xmax]})
    bs[cond_xmax]["parent"] = if_xmax
    bs[set_xmax]["parent"] = if_xmax
    bs[xp2]["parent"] = cond_xmax

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(if_l,bs[if_l]),(if_r,bs[if_r]),(if_xmin,bs[if_xmin]),(if_xmax,bs[if_xmax]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_l]})
    bs[cond_over]["parent"] = rep_until
    bs[if_l]["parent"] = rep_until

    chain([(h2,bs[h2]),(rep_until,bs[rep_until])])

    # === when space pressed: shoot (create bullet clone) ===
    h3 = gen(); bs[h3] = mk("event_whenkeypressed", top=True, x=400, y=20,
        fields={"KEY_OPTION": ["space", None]})
    state_var2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_var2, 1)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["총알", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1,cmenu]})
    bs[cmenu]["parent"] = cclone
    if_play = gen(); bs[if_play] = mk("control_if",
        inputs={"CONDITION":[2,cond_play], "SUBSTACK":[2,cclone]})
    bs[cond_play]["parent"] = if_play
    bs[cclone]["parent"] = if_play
    chain([(h3,bs[h3]),(if_play,bs[if_play])])

    return bs

# ==============================================================
#  PLAYER BULLET (총알) blocks
# ==============================================================
def build_player_bullet_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)

    # go to (player x, player y + 30)
    sx_menu = gen(); bs[sx_menu] = mk("sensing_of_object_menu",
        fields={"OBJECT": ["우주선", None]}, shadow=True)
    sense_px = gen(); bs[sense_px] = mk("sensing_of",
        inputs={"OBJECT":[1, sx_menu]},
        fields={"PROPERTY":["x position", None]})
    bs[sx_menu]["parent"] = sense_px

    sy_menu = gen(); bs[sy_menu] = mk("sensing_of_object_menu",
        fields={"OBJECT": ["우주선", None]}, shadow=True)
    sense_py = gen(); bs[sense_py] = mk("sensing_of",
        inputs={"OBJECT":[1, sy_menu]},
        fields={"PROPERTY":["y position", None]})
    bs[sy_menu]["parent"] = sense_py

    add_y = op("operator_add", sense_py, 25)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(sense_px), "Y": slot(add_y)})
    bs[sense_px]["parent"] = g_init
    bs[add_y]["parent"] = g_init

    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(110)})
    show = gen(); bs[show] = mk("looks_show")

    # repeat until off-screen / hit / game over
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_top = cmp_op("operator_gt", yp, 180)
    bs[yp]["parent"] = cond_top

    # body: change y by 12, if touching enemy delete, wait
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": num(13)})

    # if touching 외계인 → wait 0.05s (so the enemy clone has time to run its
    # own collision tick and self-destruct) → delete this clone
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["외계인", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc
    wait_kill = gen(); bs[wait_kill] = mk("control_wait",
        inputs={"DURATION": num(0.05)})
    del_a = gen(); bs[del_a] = mk("control_delete_this_clone")
    chain([(wait_kill,bs[wait_kill]),(del_a,bs[del_a])])
    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION":[2, tc], "SUBSTACK":[2, wait_kill]})
    bs[tc]["parent"] = if_hit
    bs[wait_kill]["parent"] = if_hit

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(chy,bs[chy]),(if_hit,bs[if_hit]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_top], "SUBSTACK":[2,chy]})
    bs[cond_top]["parent"] = rep_until
    bs[chy]["parent"] = rep_until

    del_b = gen(); bs[del_b] = mk("control_delete_this_clone")

    chain([(ch,bs[ch]),(g_init,bs[g_init]),(sz,bs[sz]),(show,bs[show]),
           (rep_until,bs[rep_until]),(del_b,bs[del_b])])

    return bs

# ==============================================================
#  ENEMY (외계인) blocks
# ==============================================================
def build_enemy_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # === when flag clicked: hide original ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(95)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    # === on 적생성: spawn 5×3 = 15 clones ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]})

    # build 15 sequential blocks: set 자기X, 자기Y, create clone, wait 0.02
    spawn_chain = []
    cols = [-100, -50, 0, 50, 100]
    rows = [0, -38, -76]   # row offsets (top to bottom in screen)
    for ry in rows:
        for cx in cols:
            sx = gen(); bs[sx] = mk("data_setvariableto",
                inputs={"VALUE": num(cx)}, fields={"VARIABLE": ["자기X", V_SX]})
            sy = gen(); bs[sy] = mk("data_setvariableto",
                inputs={"VALUE": num(ry)}, fields={"VARIABLE": ["자기Y", V_SY]})
            cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
                fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
            cclone = gen(); bs[cclone] = mk("control_create_clone_of",
                inputs={"CLONE_OPTION":[1, cmenu]})
            bs[cmenu]["parent"] = cclone
            inc_cnt = gen(); bs[inc_cnt] = mk("data_changevariableby",
                inputs={"VALUE": num(1)}, fields={"VARIABLE": ["적수", V_ECNT]})
            wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.02)})
            spawn_chain.extend([(sx,bs[sx]),(sy,bs[sy]),(cclone,bs[cclone]),
                                (inc_cnt,bs[inc_cnt]),(wt,bs[wt])])

    chain([(h2, bs[h2])] + spawn_chain)

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)
    show = gen(); bs[show] = mk("looks_show")

    # repeat until 게임상태=0:
    state_var = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_var, 0)

    # body: go to (진영X+자기X, 진영Y+자기Y)
    fx_v = vrep("진영X", V_FX); sx_v = vrep("자기X", V_SX)
    add_x = op("operator_add", fx_v, sx_v)
    fy_v = vrep("진영Y", V_FY); sy_v = vrep("자기Y", V_SY)
    add_y = op("operator_add", fy_v, sy_v)
    g_iter = gen(); bs[g_iter] = mk("motion_gotoxy",
        inputs={"X": slot(add_x), "Y": slot(add_y)})
    bs[add_x]["parent"] = g_iter; bs[add_y]["parent"] = g_iter

    # if touching 총알 → +1 score, sound, dec 적수, if 적수=0 broadcast 다음웨이브, delete
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["총알", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc

    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(10)}, fields={"VARIABLE": ["점수", V_SCORE]})
    pitch_set = gen(); bs[pitch_set] = mk("sound_seteffectto",
        inputs={"VALUE": num(150)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    dec_cnt = gen(); bs[dec_cnt] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["적수", V_ECNT]})

    # if 적수=0: broadcast 다음웨이브
    ecnt_v = vrep("적수", V_ECNT)
    cond_zero = cmp_op("operator_equals", ecnt_v, 0)
    bm_next = gen(); bs[bm_next] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["다음웨이브", BR_NEXT]}, shadow=True)
    bc_next = gen(); bs[bc_next] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_next]})
    bs[bm_next]["parent"] = bc_next
    if_zero = gen(); bs[if_zero] = mk("control_if",
        inputs={"CONDITION":[2,cond_zero], "SUBSTACK":[2,bc_next]})
    bs[cond_zero]["parent"] = if_zero
    bs[bc_next]["parent"] = if_zero

    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(inc_score,bs[inc_score]),(pitch_set,bs[pitch_set]),(snd,bs[snd]),
           (dec_cnt,bs[dec_cnt]),(if_zero,bs[if_zero]),(delc,bs[delc])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION":[2,tc], "SUBSTACK":[2,inc_score]})
    bs[tc]["parent"] = if_hit
    bs[inc_score]["parent"] = if_hit

    # random fire chance: if (random 1..400) = 1 → fire bullet
    rand_n = op("operator_random", 1, 400, key1="FROM", key2="TO")
    cond_fire = cmp_op("operator_equals", rand_n, 1)

    xp_self = gen(); bs[xp_self] = mk("motion_xposition")
    set_frx = gen(); bs[set_frx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xp_self)}, fields={"VARIABLE": ["발사X", V_FRX]})
    bs[xp_self]["parent"] = set_frx
    yp_self = gen(); bs[yp_self] = mk("motion_yposition")
    sub_y = op("operator_subtract", yp_self, 18)
    set_fry = gen(); bs[set_fry] = mk("data_setvariableto",
        inputs={"VALUE": slot(sub_y)}, fields={"VARIABLE": ["발사Y", V_FRY]})
    bs[sub_y]["parent"] = set_fry
    cm_eb = gen(); bs[cm_eb] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["적탄", None]}, shadow=True)
    cc_eb = gen(); bs[cc_eb] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1,cm_eb]})
    bs[cm_eb]["parent"] = cc_eb

    chain([(set_frx,bs[set_frx]),(set_fry,bs[set_fry]),(cc_eb,bs[cc_eb])])
    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION":[2,cond_fire], "SUBSTACK":[2,set_frx]})
    bs[cond_fire]["parent"] = if_fire
    bs[set_frx]["parent"] = if_fire

    wt_iter = gen(); bs[wt_iter] = mk("control_wait", inputs={"DURATION": num(0.04)})

    chain([(g_iter,bs[g_iter]),(if_hit,bs[if_hit]),(if_fire,bs[if_fire]),(wt_iter,bs[wt_iter])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,g_iter]})
    bs[cond_over]["parent"] = rep_until
    bs[g_iter]["parent"] = rep_until

    chain([(ch,bs[ch]),(show,bs[show]),(rep_until,bs[rep_until])])

    return bs

# ==============================================================
#  ENEMY BULLET (적탄) blocks
# ==============================================================
def build_enemy_bullet_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)

    frx_v = vrep("발사X", V_FRX); fry_v = vrep("발사Y", V_FRY)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(frx_v), "Y": slot(fry_v)})
    bs[frx_v]["parent"] = g_init; bs[fry_v]["parent"] = g_init
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(110)})
    show = gen(); bs[show] = mk("looks_show")

    # repeat until off-screen / hit player
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_off = cmp_op("operator_lt", yp, -180)
    bs[yp]["parent"] = cond_off

    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": num(-7)})

    # if touching 우주선 → -1 life, sound, delete
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["우주선", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc
    dec_life = gen(); bs[dec_life] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["라이프", V_LIFE]})
    pitch_low = gen(); bs[pitch_low] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd

    # if 라이프 ≤ 0 → 게임상태 = 0
    life_v = vrep("라이프", V_LIFE)
    cond_dead = cmp_op("operator_lt", life_v, 1)
    set_state = gen(); bs[set_state] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION":[2,cond_dead], "SUBSTACK":[2,set_state]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state]["parent"] = if_dead

    delc_a = gen(); bs[delc_a] = mk("control_delete_this_clone")
    chain([(dec_life,bs[dec_life]),(pitch_low,bs[pitch_low]),(snd,bs[snd]),
           (if_dead,bs[if_dead]),(delc_a,bs[delc_a])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION":[2,tc], "SUBSTACK":[2,dec_life]})
    bs[tc]["parent"] = if_hit
    bs[dec_life]["parent"] = if_hit

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.03)})
    chain([(chy,bs[chy]),(if_hit,bs[if_hit]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_off], "SUBSTACK":[2,chy]})
    bs[cond_off]["parent"] = rep_until
    bs[chy]["parent"] = rep_until

    delc_b = gen(); bs[delc_b] = mk("control_delete_this_clone")
    chain([(ch,bs[ch]),(g_init,bs[g_init]),(sz,bs[sz]),(show,bs[show]),
           (rep_until,bs[rep_until]),(delc_b,bs[delc_b])])

    return bs

# ==============================================================
#  GAME OVER banner blocks
# ==============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # when flag clicked → hide, go to center, wait until 게임상태=0, show
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # wait until 게임상태 = 0
    state_v = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", state_v, 0)
    wait_until = gen(); bs[wait_until] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_zero]})
    bs[cond_zero]["parent"] = wait_until

    show = gen(); bs[show] = mk("looks_show")
    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front]),
           (wait_until,bs[wait_until]),(show,bs[show])])
    return bs

# ==============================================================
#  ASSEMBLE PROJECT
# ==============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # Save background
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    # Save bullets
    pb_md5 = md5_bytes(P_BULLET_SVG.encode("utf-8"))
    with open(f"{WORK}/{pb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(P_BULLET_SVG)
    eb_md5 = md5_bytes(E_BULLET_SVG.encode("utf-8"))
    with open(f"{WORK}/{eb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(E_BULLET_SVG)

    # Rotate rocket so it points up, then save
    with open(f"{ASSETS}/rocket.svg", "rb") as f: rocket_raw = f.read().decode("utf-8")
    rocket_rotated = rotate_svg(rocket_raw, -45, 18, 18)
    rocket_md5 = md5_bytes(rocket_rotated.encode("utf-8"))
    with open(f"{WORK}/{rocket_md5}.svg", "w", encoding="utf-8") as f:
        f.write(rocket_rotated)

    # Alien (twemoji as-is)
    with open(f"{ASSETS}/alien.svg", "rb") as f: alien_bytes = f.read()
    alien_md5 = md5_bytes(alien_bytes)
    with open(f"{WORK}/{alien_md5}.svg", "wb") as f:
        f.write(alien_bytes)

    # Pop sound
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    # Save game over banner
    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    stage_blocks    = build_stage_blocks()
    player_blocks   = build_player_blocks()
    pbullet_blocks  = build_player_bullet_blocks()
    enemy_blocks    = build_enemy_blocks()
    ebullet_blocks  = build_enemy_bullet_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 48000, "sampleCount": 1123,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE: ["점수", 0],
            V_LIFE:  ["라이프", 3],
            V_WAVE:  ["라운드", 1],
            V_STATE: ["게임상태", 1],
            V_FX:    ["진영X", 0],
            V_FY:    ["진영Y", 130],
            V_DIR:   ["적_방향", 1],
            V_SPEED: ["적_속도", 1.5],
            V_ECNT:  ["적수", 0],
            V_FRX:   ["발사X", 0],
            V_FRY:   ["발사Y", 0],
        },
        "lists": {},
        "broadcasts": {BR_START:"게임시작", BR_SPAWN:"적생성",
                        BR_NEXT:"다음웨이브", BR_OVER:"게임종료"},
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

    player = {
        "isStage": False, "name": "우주선",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": player_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "rocket", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": rocket_md5, "md5ext": f"{rocket_md5}.svg",
            "rotationCenterX": 18, "rotationCenterY": 18
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 0, "y": -150, "size": 140, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    pbullet = {
        "isStage": False, "name": "총알",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pbullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "총알", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pb_md5, "md5ext": f"{pb_md5}.svg",
            "rotationCenterX": 3, "rotationCenterY": 7
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 110, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    enemy = {
        "isStage": False, "name": "외계인",
        "variables": {V_SX: ["자기X", 0], V_SY: ["자기Y", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "외계인", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": alien_md5, "md5ext": f"{alien_md5}.svg",
            "rotationCenterX": 18, "rotationCenterY": 18
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 100, "size": 95, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ebullet = {
        "isStage": False, "name": "적탄",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ebullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "적탄", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": eb_md5, "md5ext": f"{eb_md5}.svg",
            "rotationCenterX": 3.5, "rotationCenterY": 7
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 110, "direction": 90,
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
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

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
        "volume": 100, "layerOrder": 5, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    project = {
        "targets": [stage, player, pbullet, enemy, ebullet, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "alien-invasion-builder"}
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
    print(f"✓ wrote {OUTPUT}")

if __name__ == "__main__":
    main()
