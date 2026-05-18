#!/usr/bin/env python3
"""Doodle Jump — 발판 밟고 끝없이 위로 점프, 떨어지면 게임오버."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "두들_점프.sb3")

# ==============================================================
#  ASSETS (inline SVG)
# ==============================================================
random.seed(7)
cloud_paths = []
for _ in range(5):
    cx = random.randint(40, 440)
    cy = random.randint(20, 220)
    rx = random.randint(40, 80)
    ry = random.randint(14, 26)
    op = round(random.uniform(0.35, 0.6), 2)
    cloud_paths.append(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="white" opacity="{op}"/>'
    )
CLOUDS = "\n    ".join(cloud_paths)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="#87CEEB"/>
      <stop offset="55%"  stop-color="#B5E2F5"/>
      <stop offset="100%" stop-color="#E8F5FE"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <g>
    {CLOUDS}
  </g>
</svg>"""

# 두들이 (face left/right; rotationStyle = left-right)
DOODLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <ellipse cx="24" cy="26" rx="18" ry="16" fill="#7CB342" stroke="#33691E" stroke-width="2"/>
  <ellipse cx="24" cy="22" rx="13" ry="11" fill="#9CCC65"/>
  <!-- legs -->
  <rect x="13" y="40" width="6" height="6" rx="2" fill="#33691E"/>
  <rect x="29" y="40" width="6" height="6" rx="2" fill="#33691E"/>
  <!-- arm waving right (indicates facing) -->
  <ellipse cx="42" cy="28" rx="5" ry="3" fill="#7CB342" stroke="#33691E" stroke-width="1.5"/>
  <!-- eyes -->
  <circle cx="20" cy="20" r="4" fill="white" stroke="#000" stroke-width="1.2"/>
  <circle cx="30" cy="20" r="4" fill="white" stroke="#000" stroke-width="1.2"/>
  <circle cx="21" cy="21" r="1.8" fill="#000"/>
  <circle cx="31" cy="21" r="1.8" fill="#000"/>
  <!-- smile -->
  <path d="M 19 30 Q 24 34 29 30" stroke="#33691E" stroke-width="1.8" fill="none" stroke-linecap="round"/>
</svg>"""

PLATFORM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="20" viewBox="0 0 80 20">
  <rect x="2" y="2" width="76" height="16" rx="8" fill="#66BB6A" stroke="#2E7D32" stroke-width="2"/>
  <rect x="6" y="5" width="68" height="4" rx="2" fill="#A5D6A7" opacity="0.85"/>
</svg>"""

GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="180" viewBox="0 0 360 180">
  <rect x="5" y="5" width="350" height="170" rx="14"
        fill="#000000" opacity="0.86"
        stroke="#FF1744" stroke-width="4"/>
  <text x="180" y="64" text-anchor="middle"
        fill="#FF1744" font-family="Arial, Helvetica, sans-serif"
        font-size="42" font-weight="bold">GAME OVER</text>
  <text x="180" y="100" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">바닥으로 떨어졌어요</text>
  <text x="180" y="128" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="16">좌상단의 점수/최고기록 확인</text>
  <text x="180" y="156" text-anchor="middle"
        fill="#81D4FA" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶)을 다시 눌러 재시작</text>
</svg>"""

# ==============================================================
#  HELPERS
# ==============================================================
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
        bs[bid] = mk(opcode, inputs={"OPERAND1": [2, a], "OPERAND2": [2, b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid
        return bid
    return vrep, op, cmp_op, bool_op

# ==============================================================
#  IDS
# ==============================================================
V_SCORE = "varScore01"
V_BEST  = "varBest02"
V_STATE = "varState03"
V_VY    = "varVY04"
V_CAM   = "varCam05"
V_BASEY = "varBaseY06"
V_PSY   = "varPSY07"     # platform sprite-local: spawn y counter

BR_START  = "brStart01"
BR_SPAWN  = "brSpawn02"
BR_ADD    = "brAdd03"
BR_BOUNCE = "brBounce04"

# ==============================================================
#  STAGE blocks
# ==============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init + start ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    s_score = gen(); bs[s_score] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점수", V_SCORE]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    s_vy = gen(); bs[s_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(15)}, fields={"VARIABLE": ["VY", V_VY]})
    s_cam = gen(); bs[s_cam] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["카메라", V_CAM]})
    s_basey = gen(); bs[s_basey] = mk("data_setvariableto",
        inputs={"VALUE": num(-60)}, fields={"VARIABLE": ["시작Y", V_BASEY]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    bm_spawn = gen(); bs[bm_spawn] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["발판생성", BR_SPAWN]}, shadow=True)
    bc_spawn = gen(); bs[bc_spawn] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_spawn]})
    bs[bm_spawn]["parent"] = bc_spawn

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_state,bs[s_state]),
           (s_vy,bs[s_vy]),(s_cam,bs[s_cam]),(s_basey,bs[s_basey]),
           (bc_start,bs[bc_start]),(bc_spawn,bs[bc_spawn])])

    # === when receive 튕김: VY = 15 + play pop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=260,
        fields={"BROADCAST_OPTION": ["튕김", BR_BOUNCE]})
    set_vy = gen(); bs[set_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(15)}, fields={"VARIABLE": ["VY", V_VY]})
    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(80)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    chain([(h2,bs[h2]),(set_vy,bs[set_vy]),(pitch,bs[pitch]),(snd,bs[snd])])

    return bs

# ==============================================================
#  DOODLE (player) blocks
# ==============================================================
def build_doodle_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init position ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(0), "Y": num(-60)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === movement loop on 게임시작 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # initial position + VY
    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": num(0), "Y": num(-60)})
    set_vy0 = gen(); bs[set_vy0] = mk("data_setvariableto",
        inputs={"VALUE": num(15)}, fields={"VARIABLE": ["VY", V_VY]})

    # repeat until 게임상태=0:
    state_var = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_var, 0)

    # --- LEFT arrow ---
    key_l = gen(); bs[key_l] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    sense_l = gen(); bs[sense_l] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_l]})
    bs[key_l]["parent"] = sense_l
    chx_l = gen(); bs[chx_l] = mk("motion_changexby", inputs={"DX": num(-6)})
    pdl = gen(); bs[pdl] = mk("motion_pointindirection", inputs={"DIRECTION": num(-90)})
    chain([(chx_l,bs[chx_l]),(pdl,bs[pdl])])
    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION":[2,sense_l], "SUBSTACK":[2,chx_l]})
    bs[sense_l]["parent"] = if_l
    bs[chx_l]["parent"] = if_l

    # --- RIGHT arrow ---
    key_r = gen(); bs[key_r] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    sense_r = gen(); bs[sense_r] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_r]})
    bs[key_r]["parent"] = sense_r
    chx_r = gen(); bs[chx_r] = mk("motion_changexby", inputs={"DX": num(6)})
    pdr = gen(); bs[pdr] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    chain([(chx_r,bs[chx_r]),(pdr,bs[pdr])])
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION":[2,sense_r], "SUBSTACK":[2,chx_r]})
    bs[sense_r]["parent"] = if_r
    bs[chx_r]["parent"] = if_r

    # --- wrap left ---
    xp_w1 = gen(); bs[xp_w1] = mk("motion_xposition")
    cond_xleft = cmp_op("operator_lt", xp_w1, -240)
    bs[xp_w1]["parent"] = cond_xleft
    set_xr = gen(); bs[set_xr] = mk("motion_setx", inputs={"X": num(240)})
    if_wleft = gen(); bs[if_wleft] = mk("control_if",
        inputs={"CONDITION":[2, cond_xleft], "SUBSTACK":[2, set_xr]})
    bs[cond_xleft]["parent"] = if_wleft
    bs[set_xr]["parent"] = if_wleft

    # --- wrap right ---
    xp_w2 = gen(); bs[xp_w2] = mk("motion_xposition")
    cond_xright = cmp_op("operator_gt", xp_w2, 240)
    bs[xp_w2]["parent"] = cond_xright
    set_xl = gen(); bs[set_xl] = mk("motion_setx", inputs={"X": num(-240)})
    if_wright = gen(); bs[if_wright] = mk("control_if",
        inputs={"CONDITION":[2, cond_xright], "SUBSTACK":[2, set_xl]})
    bs[cond_xright]["parent"] = if_wright
    bs[set_xl]["parent"] = if_wright

    # --- VY 적용: change y by VY ---
    vy_v1 = vrep("VY", V_VY)
    chy_vy = gen(); bs[chy_vy] = mk("motion_changeyby", inputs={"DY": slot(vy_v1)})
    bs[vy_v1]["parent"] = chy_vy

    # --- gravity: change VY by -1 ---
    chg_vy = gen(); bs[chg_vy] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["VY", V_VY]})

    # --- camera scroll: if y > 0 → cam=y, set y to 0, score += cam ; else cam=0 ---
    yp_cam = gen(); bs[yp_cam] = mk("motion_yposition")
    cond_up = cmp_op("operator_gt", yp_cam, 0)
    bs[yp_cam]["parent"] = cond_up

    yp_cam2 = gen(); bs[yp_cam2] = mk("motion_yposition")
    set_cam = gen(); bs[set_cam] = mk("data_setvariableto",
        inputs={"VALUE": slot(yp_cam2)}, fields={"VARIABLE": ["카메라", V_CAM]})
    bs[yp_cam2]["parent"] = set_cam
    sety_0 = gen(); bs[sety_0] = mk("motion_sety", inputs={"Y": num(0)})
    cam_v = vrep("카메라", V_CAM)
    chg_score = gen(); bs[chg_score] = mk("data_changevariableby",
        inputs={"VALUE": slot(cam_v)}, fields={"VARIABLE": ["점수", V_SCORE]})
    bs[cam_v]["parent"] = chg_score
    chain([(set_cam,bs[set_cam]),(sety_0,bs[sety_0]),(chg_score,bs[chg_score])])

    set_cam0 = gen(); bs[set_cam0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["카메라", V_CAM]})

    if_cam = gen(); bs[if_cam] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_up],
                "SUBSTACK":[2, set_cam],
                "SUBSTACK2":[2, set_cam0]})
    bs[cond_up]["parent"] = if_cam
    bs[set_cam]["parent"] = if_cam
    bs[set_cam0]["parent"] = if_cam

    # --- fall check: y < -190 → state=0, update best ---
    yp_fall = gen(); bs[yp_fall] = mk("motion_yposition")
    cond_fall = cmp_op("operator_lt", yp_fall, -190)
    bs[yp_fall]["parent"] = cond_fall

    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})

    # best update: if 점수 > 최고기록 → 최고기록 = 점수
    score_v = vrep("점수", V_SCORE)
    best_v = vrep("최고기록", V_BEST)
    cond_best = cmp_op("operator_gt", score_v, best_v)

    score_v2 = vrep("점수", V_SCORE)
    set_best = gen(); bs[set_best] = mk("data_setvariableto",
        inputs={"VALUE": slot(score_v2)}, fields={"VARIABLE": ["최고기록", V_BEST]})
    bs[score_v2]["parent"] = set_best

    if_best = gen(); bs[if_best] = mk("control_if",
        inputs={"CONDITION":[2, cond_best], "SUBSTACK":[2, set_best]})
    bs[cond_best]["parent"] = if_best
    bs[set_best]["parent"] = if_best

    chain([(set_state0,bs[set_state0]),(if_best,bs[if_best])])

    if_fall = gen(); bs[if_fall] = mk("control_if",
        inputs={"CONDITION":[2, cond_fall], "SUBSTACK":[2, set_state0]})
    bs[cond_fall]["parent"] = if_fall
    bs[set_state0]["parent"] = if_fall

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(if_l,bs[if_l]),(if_r,bs[if_r]),(if_wleft,bs[if_wleft]),(if_wright,bs[if_wright]),
           (chy_vy,bs[chy_vy]),(chg_vy,bs[chg_vy]),(if_cam,bs[if_cam]),(if_fall,bs[if_fall]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_over], "SUBSTACK":[2, if_l]})
    bs[cond_over]["parent"] = rep_until
    bs[if_l]["parent"] = rep_until

    chain([(h2,bs[h2]),(g0,bs[g0]),(set_vy0,bs[set_vy0]),(rep_until,bs[rep_until])])

    return bs

# ==============================================================
#  PLATFORM (발판) blocks
# ==============================================================
def build_platform_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    # === when receive 발판생성: 12개 클론 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["발판생성", BR_SPAWN]})

    # initial spawn y counter
    init_psy = gen(); bs[init_psy] = mk("data_setvariableto",
        inputs={"VALUE": num(-130)}, fields={"VARIABLE": ["자리Y", V_PSY]})

    # repeat 12: pick random x, set y to 자리Y, create clone, 자리Y += 28, wait 0.01
    rand_x = gen(); bs[rand_x] = mk("operator_random",
        inputs={"FROM": num(-200), "TO": num(200)})
    psy_v1 = vrep("자리Y", V_PSY)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(rand_x), "Y": slot(psy_v1)})
    bs[rand_x]["parent"] = g_init; bs[psy_v1]["parent"] = g_init

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    inc_psy = gen(); bs[inc_psy] = mk("data_changevariableby",
        inputs={"VALUE": num(28)}, fields={"VARIABLE": ["자리Y", V_PSY]})

    wt0 = gen(); bs[wt0] = mk("control_wait", inputs={"DURATION": num(0.01)})

    chain([(g_init,bs[g_init]),(cclone,bs[cclone]),(inc_psy,bs[inc_psy]),(wt0,bs[wt0])])

    rep12 = gen(); bs[rep12] = mk("control_repeat",
        inputs={"TIMES": num(12), "SUBSTACK":[2, g_init]})
    bs[g_init]["parent"] = rep12

    chain([(h2,bs[h2]),(init_psy,bs[init_psy]),(rep12,bs[rep12])])

    # === when receive 발판추가: 한 개만 생성, 상단(y=180) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=400, y=20,
        fields={"BROADCAST_OPTION": ["발판추가", BR_ADD]})

    rand_x2 = gen(); bs[rand_x2] = mk("operator_random",
        inputs={"FROM": num(-200), "TO": num(200)})
    g_add = gen(); bs[g_add] = mk("motion_gotoxy",
        inputs={"X": slot(rand_x2), "Y": num(180)})
    bs[rand_x2]["parent"] = g_add

    cmenu2 = gen(); bs[cmenu2] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone2 = gen(); bs[cclone2] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu2]})
    bs[cmenu2]["parent"] = cclone2

    chain([(h3,bs[h3]),(g_add,bs[g_add]),(cclone2,bs[cclone2])])

    # === when I start as clone: ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    show = gen(); bs[show] = mk("looks_show")

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # body: change y by (-1 * 카메라)
    cam_v = vrep("카메라", V_CAM)
    neg_cam = op("operator_multiply", -1, cam_v)
    chy_scroll = gen(); bs[chy_scroll] = mk("motion_changeyby",
        inputs={"DY": slot(neg_cam)})
    bs[neg_cam]["parent"] = chy_scroll

    # if touching 두들이 AND VY < 0: broadcast 튕김
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["두들이", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc

    vy_v = vrep("VY", V_VY)
    cond_falling = cmp_op("operator_lt", vy_v, 0)
    cond_bounce = bool_op("operator_and", tc, cond_falling)

    bm_b = gen(); bs[bm_b] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["튕김", BR_BOUNCE]}, shadow=True)
    bc_b = gen(); bs[bc_b] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_b]})
    bs[bm_b]["parent"] = bc_b

    if_bounce = gen(); bs[if_bounce] = mk("control_if",
        inputs={"CONDITION":[2, cond_bounce], "SUBSTACK":[2, bc_b]})
    bs[cond_bounce]["parent"] = if_bounce
    bs[bc_b]["parent"] = if_bounce

    # if y < -190: broadcast 발판추가, delete clone
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cond_off = cmp_op("operator_lt", yp_b, -190)
    bs[yp_b]["parent"] = cond_off

    bm_a = gen(); bs[bm_a] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["발판추가", BR_ADD]}, shadow=True)
    bc_a = gen(); bs[bc_a] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_a]})
    bs[bm_a]["parent"] = bc_a
    del_a = gen(); bs[del_a] = mk("control_delete_this_clone")
    chain([(bc_a,bs[bc_a]),(del_a,bs[del_a])])

    if_off = gen(); bs[if_off] = mk("control_if",
        inputs={"CONDITION":[2, cond_off], "SUBSTACK":[2, bc_a]})
    bs[cond_off]["parent"] = if_off
    bs[bc_a]["parent"] = if_off

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(chy_scroll,bs[chy_scroll]),(if_bounce,bs[if_bounce]),(if_off,bs[if_off]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_over], "SUBSTACK":[2, chy_scroll]})
    bs[cond_over]["parent"] = rep_until
    bs[chy_scroll]["parent"] = rep_until

    del_b = gen(); bs[del_b] = mk("control_delete_this_clone")
    chain([(ch,bs[ch]),(show,bs[show]),(rep_until,bs[rep_until]),(del_b,bs[del_b])])

    return bs

# ==============================================================
#  GAME OVER banner blocks
# ==============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # wait until 게임상태=1 first (so restart doesn't show banner instantly)
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

# ==============================================================
#  ASSEMBLE PROJECT
# ==============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # SVG 자산 저장
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    dd_md5 = md5_bytes(DOODLE_SVG.encode("utf-8"))
    with open(f"{WORK}/{dd_md5}.svg", "w", encoding="utf-8") as f:
        f.write(DOODLE_SVG)

    pl_md5 = md5_bytes(PLATFORM_SVG.encode("utf-8"))
    with open(f"{WORK}/{pl_md5}.svg", "w", encoding="utf-8") as f:
        f.write(PLATFORM_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    # 자산: assets/doodle.svg 등을 외부에서 쓰지 않으므로 모두 인라인.
    # 사운드: pop.wav 사용
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    doodle_blocks   = build_doodle_blocks()
    platform_blocks = build_platform_blocks()
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
            V_BEST:  ["최고기록", 0],
            V_STATE: ["게임상태", 1],
            V_VY:    ["VY", 0],
            V_CAM:   ["카메라", 0],
            V_BASEY: ["시작Y", -60],
        },
        "lists": {},
        "broadcasts": {
            BR_START:  "게임시작",
            BR_SPAWN:  "발판생성",
            BR_ADD:    "발판추가",
            BR_BOUNCE: "튕김",
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

    doodle = {
        "isStage": False, "name": "두들이",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": doodle_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "두들이", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": dd_md5, "md5ext": f"{dd_md5}.svg",
            "rotationCenterX": 24, "rotationCenterY": 24
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": 0, "y": -60, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "left-right"
    }

    platform = {
        "isStage": False, "name": "발판",
        "variables": {V_PSY: ["자리Y", -130]},
        "lists": {}, "broadcasts": {},
        "blocks": platform_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "발판", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pl_md5, "md5ext": f"{pl_md5}.svg",
            "rotationCenterX": 40, "rotationCenterY": 10
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
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
            "rotationCenterX": 180, "rotationCenterY": 90
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
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
    ]

    project = {
        "targets": [stage, platform, doodle, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "doodle-jump-builder"}
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

if __name__ == "__main__":
    main()
