#!/usr/bin/env python3
"""Flappy Bird — 한 버튼 점프로 파이프 사이 통과."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "플래피_버드.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: sky blue gradient + faint clouds --------
random.seed(42)
clouds = []
for _ in range(6):
    cx = random.randint(40, 440); cy = random.randint(40, 180)
    rx = random.randint(28, 48); ry = random.randint(10, 18)
    op = random.uniform(0.45, 0.75)
    clouds.append(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
        f'fill="#FFFFFF" opacity="{op:.2f}"/>'
    )
    # small puff alongside
    clouds.append(
        f'<ellipse cx="{cx-rx//2}" cy="{cy+4}" rx="{rx//2}" ry="{ry-2}" '
        f'fill="#FFFFFF" opacity="{op*0.8:.2f}"/>'
    )
CLOUDS = "\n    ".join(clouds)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="#4FC3F7"/>
      <stop offset="60%"  stop-color="#81D4FA"/>
      <stop offset="100%" stop-color="#B3E5FC"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <g>
    {CLOUDS}
  </g>
  <!-- ground hint at bottom -->
  <rect x="0" y="340" width="480" height="20" fill="#A5D6A7" opacity="0.6"/>
</svg>"""

# -------- Bird (60x45, yellow body facing right) --------
BIRD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="45" viewBox="0 0 60 45">
  <!-- body -->
  <ellipse cx="28" cy="24" rx="20" ry="15" fill="#FFEB3B" stroke="#F57F17" stroke-width="1.8"/>
  <!-- belly highlight -->
  <ellipse cx="26" cy="30" rx="14" ry="7" fill="#FFF59D" opacity="0.7"/>
  <!-- wing -->
  <ellipse cx="22" cy="26" rx="10" ry="6" fill="#FBC02D" stroke="#F57F17" stroke-width="1.4"/>
  <!-- eye white -->
  <circle cx="40" cy="18" r="6" fill="#FFFFFF" stroke="#212121" stroke-width="1.2"/>
  <!-- pupil -->
  <circle cx="42" cy="18" r="3" fill="#212121"/>
  <!-- beak -->
  <polygon points="50,22 58,20 58,26 50,28" fill="#FF7043" stroke="#BF360C" stroke-width="1.2"/>
  <!-- red cheek -->
  <circle cx="34" cy="26" r="2.5" fill="#E53935" opacity="0.6"/>
  <!-- tail feather -->
  <polygon points="8,20 2,16 4,24 2,30 8,28" fill="#F9A825" stroke="#F57F17" stroke-width="1.2"/>
</svg>"""

# -------- Top pipe (100x200) -- green body, rim at the BOTTOM (gap side) --------
PIPE_TOP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="200" viewBox="0 0 100 200">
  <!-- main body -->
  <rect x="12" y="0" width="76" height="180" fill="#4CAF50" stroke="#1B5E20" stroke-width="2.4"/>
  <!-- inner highlight stripe -->
  <rect x="20" y="0" width="10" height="180" fill="#81C784" opacity="0.7"/>
  <!-- inner shadow stripe -->
  <rect x="70" y="0" width="8" height="180" fill="#2E7D32" opacity="0.5"/>
  <!-- rim at the bottom (gap-facing) -->
  <rect x="2" y="170" width="96" height="28" fill="#43A047" stroke="#1B5E20" stroke-width="2.4"/>
  <rect x="6" y="174" width="14" height="20" fill="#81C784" opacity="0.7"/>
  <rect x="80" y="174" width="8"  height="20" fill="#2E7D32" opacity="0.6"/>
</svg>"""

# -------- Bottom pipe (100x200) -- green body, rim at the TOP (gap side) --------
PIPE_BOT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="200" viewBox="0 0 100 200">
  <!-- rim at the top (gap-facing) -->
  <rect x="2" y="2" width="96" height="28" fill="#43A047" stroke="#1B5E20" stroke-width="2.4"/>
  <rect x="6" y="6" width="14" height="20" fill="#81C784" opacity="0.7"/>
  <rect x="80" y="6" width="8"  height="20" fill="#2E7D32" opacity="0.6"/>
  <!-- main body -->
  <rect x="12" y="20" width="76" height="180" fill="#4CAF50" stroke="#1B5E20" stroke-width="2.4"/>
  <rect x="20" y="20" width="10" height="180" fill="#81C784" opacity="0.7"/>
  <rect x="70" y="20" width="8"  height="180" fill="#2E7D32" opacity="0.5"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#FFEB3B" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">파이프에 부딪혔어요</text>
  <text x="180" y="132" text-anchor="middle"
        fill="#FFF59D" font-family="Arial, Helvetica, sans-serif"
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

# ============================================================
#  IDs
# ============================================================
V_SCORE  = "varScore01"
V_BEST   = "varBest02"
V_STATE  = "varState03"
V_VY     = "varVY04"
V_SCROLL = "varScroll05"
V_SPAWN  = "varSpawn06"
V_GAPY   = "varGapY07"
V_GAPH   = "varGapH08"
V_PREV   = "varPrevKey09"

# pipe sprite-local: 통과여부
V_PASSED_TOP = "varPassedTop01"

BR_START = "brStart01"
BR_SPAWN = "brSpawn02"

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init vars + broadcast 게임시작 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    s_score = gen(); bs[s_score] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점수", V_SCORE]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    s_vy = gen(); bs[s_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    s_scroll = gen(); bs[s_scroll] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["스크롤속도", V_SCROLL]})
    s_spawn = gen(); bs[s_spawn] = mk("data_setvariableto",
        inputs={"VALUE": num(1.5)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    s_gapy = gen(); bs[s_gapy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["GAP중심", V_GAPY]})
    s_gaph = gen(); bs[s_gaph] = mk("data_setvariableto",
        inputs={"VALUE": num(100)}, fields={"VARIABLE": ["GAP크기", V_GAPH]})
    s_prev = gen(); bs[s_prev] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["이전키", V_PREV]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_state,bs[s_state]),(s_vy,bs[s_vy]),
           (s_scroll,bs[s_scroll]),(s_spawn,bs[s_spawn]),(s_gapy,bs[s_gapy]),
           (s_gaph,bs[s_gaph]),(s_prev,bs[s_prev]),(bc_start,bs[bc_start])])

    # === when receive 게임시작 (forever: pipe pair spawn) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # GAP중심 = pick random -80 to 80
    rnd = gen(); bs[rnd] = mk("operator_random",
        inputs={"FROM": num(-80), "TO": num(80)})
    set_gapy = gen(); bs[set_gapy] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd)}, fields={"VARIABLE": ["GAP중심", V_GAPY]})
    bs[rnd]["parent"] = set_gapy

    # broadcast 파이프스폰
    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["파이프스폰", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    # wait 스폰주기
    spawn_v = vrep("스폰주기", V_SPAWN)
    wt_sp = gen(); bs[wt_sp] = mk("control_wait",
        inputs={"DURATION": slot(spawn_v)})
    bs[spawn_v]["parent"] = wt_sp

    chain([(set_gapy,bs[set_gapy]),(bc_sp,bs[bc_sp]),(wt_sp,bs[wt_sp])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,set_gapy]})
    bs[cond_over]["parent"] = rep_until
    bs[set_gapy]["parent"] = rep_until

    chain([(h2,bs[h2]),(rep_until,bs[rep_until])])

    return bs

# ============================================================
#  BIRD blocks
# ============================================================
def build_bird_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init pos + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(-100), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: input + physics + collision loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    reset_vy = gen(); bs[reset_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    reset_prev = gen(); bs[reset_prev] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["이전키", V_PREV]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": num(-100), "Y": num(0)})

    # repeat until 게임상태 = 0
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # --- edge detection input: (space pressed OR mouse down) AND 이전키=0 → VY=8 ---
    key_space_a = gen(); bs[key_space_a] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sense_sp_a = gen(); bs[sense_sp_a] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_space_a]})
    bs[key_space_a]["parent"] = sense_sp_a

    sense_md_a = gen(); bs[sense_md_a] = mk("sensing_mousedown")

    cond_input_a = bool_op("operator_or", sense_sp_a, sense_md_a)

    prev_v1 = vrep("이전키", V_PREV)
    cond_prev0 = cmp_op("operator_equals", prev_v1, 0)

    cond_edge = bool_op("operator_and", cond_input_a, cond_prev0)

    set_vy_jump = gen(); bs[set_vy_jump] = mk("data_setvariableto",
        inputs={"VALUE": num(8)}, fields={"VARIABLE": ["VY", V_VY]})

    if_jump = gen(); bs[if_jump] = mk("control_if",
        inputs={"CONDITION":[2,cond_edge], "SUBSTACK":[2,set_vy_jump]})
    bs[cond_edge]["parent"] = if_jump
    bs[set_vy_jump]["parent"] = if_jump

    # --- update 이전키: if (input) then 이전키=1 else 이전키=0 ---
    key_space_b = gen(); bs[key_space_b] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sense_sp_b = gen(); bs[sense_sp_b] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_space_b]})
    bs[key_space_b]["parent"] = sense_sp_b

    sense_md_b = gen(); bs[sense_md_b] = mk("sensing_mousedown")

    cond_input_b = bool_op("operator_or", sense_sp_b, sense_md_b)

    set_prev_1 = gen(); bs[set_prev_1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["이전키", V_PREV]})
    set_prev_0 = gen(); bs[set_prev_0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["이전키", V_PREV]})

    if_else_prev = gen(); bs[if_else_prev] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_input_b],
                "SUBSTACK":[2,set_prev_1],
                "SUBSTACK2":[2,set_prev_0]})
    bs[cond_input_b]["parent"] = if_else_prev
    bs[set_prev_1]["parent"] = if_else_prev
    bs[set_prev_0]["parent"] = if_else_prev

    # --- gravity: VY -= 0.8 ---
    grav = gen(); bs[grav] = mk("data_changevariableby",
        inputs={"VALUE": num(-0.8)}, fields={"VARIABLE": ["VY", V_VY]})

    # --- VY clamp bottom: if VY < -10 → VY = -10 ---
    vy_v_c = vrep("VY", V_VY)
    cond_vylo = cmp_op("operator_lt", vy_v_c, -10)
    set_vy_lo = gen(); bs[set_vy_lo] = mk("data_setvariableto",
        inputs={"VALUE": num(-10)}, fields={"VARIABLE": ["VY", V_VY]})
    if_vylo = gen(); bs[if_vylo] = mk("control_if",
        inputs={"CONDITION":[2,cond_vylo], "SUBSTACK":[2,set_vy_lo]})
    bs[cond_vylo]["parent"] = if_vylo
    bs[set_vy_lo]["parent"] = if_vylo

    # --- change y by VY ---
    vy_v_d = vrep("VY", V_VY)
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(vy_v_d)})
    bs[vy_v_d]["parent"] = chy

    # --- ceiling: if y > 175 → state=0 ---
    yp_t = gen(); bs[yp_t] = mk("motion_yposition")
    cond_yt = cmp_op("operator_gt", yp_t, 175)
    bs[yp_t]["parent"] = cond_yt
    set_st_t = gen(); bs[set_st_t] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_yt = gen(); bs[if_yt] = mk("control_if",
        inputs={"CONDITION":[2,cond_yt], "SUBSTACK":[2,set_st_t]})
    bs[cond_yt]["parent"] = if_yt
    bs[set_st_t]["parent"] = if_yt

    # --- floor: if y < -175 → state=0 ---
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cond_yb = cmp_op("operator_lt", yp_b, -175)
    bs[yp_b]["parent"] = cond_yb
    set_st_b = gen(); bs[set_st_b] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_yb = gen(); bs[if_yb] = mk("control_if",
        inputs={"CONDITION":[2,cond_yb], "SUBSTACK":[2,set_st_b]})
    bs[cond_yb]["parent"] = if_yb
    bs[set_st_b]["parent"] = if_yb

    # --- touching 상단파이프 → state=0 ---
    tm_top = gen(); bs[tm_top] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["상단파이프", None]}, shadow=True)
    tc_top = gen(); bs[tc_top] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_top]})
    bs[tm_top]["parent"] = tc_top
    set_st_top = gen(); bs[set_st_top] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_top = gen(); bs[if_top] = mk("control_if",
        inputs={"CONDITION":[2,tc_top], "SUBSTACK":[2,set_st_top]})
    bs[tc_top]["parent"] = if_top
    bs[set_st_top]["parent"] = if_top

    # --- touching 하단파이프 → state=0 ---
    tm_bot = gen(); bs[tm_bot] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["하단파이프", None]}, shadow=True)
    tc_bot = gen(); bs[tc_bot] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_bot]})
    bs[tm_bot]["parent"] = tc_bot
    set_st_bot = gen(); bs[set_st_bot] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_bot = gen(); bs[if_bot] = mk("control_if",
        inputs={"CONDITION":[2,tc_bot], "SUBSTACK":[2,set_st_bot]})
    bs[tc_bot]["parent"] = if_bot
    bs[set_st_bot]["parent"] = if_bot

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

    # --- VY-based tilt: point in direction (90 - VY*4), clamped to [55, 125] ---
    # Clamp upper: if (90 - VY*4) > 125 then point 125
    vy_v_thi = vrep("VY", V_VY)
    tilt_mul_hi = op("operator_multiply", vy_v_thi, 4)
    tilt_calc_hi = op("operator_subtract", 90, tilt_mul_hi, key1="NUM1", key2="NUM2")
    cond_hi = cmp_op("operator_gt", tilt_calc_hi, 125)
    bs[tilt_calc_hi]["parent"] = cond_hi
    set_dir_hi = gen(); bs[set_dir_hi] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(125)})
    if_tilt_hi = gen(); bs[if_tilt_hi] = mk("control_if",
        inputs={"CONDITION":[2,cond_hi], "SUBSTACK":[2,set_dir_hi]})
    bs[cond_hi]["parent"] = if_tilt_hi
    bs[set_dir_hi]["parent"] = if_tilt_hi

    # Clamp lower: if (90 - VY*4) < 55 then point 55
    vy_v_tlo = vrep("VY", V_VY)
    tilt_mul_lo = op("operator_multiply", vy_v_tlo, 4)
    tilt_calc_lo = op("operator_subtract", 90, tilt_mul_lo, key1="NUM1", key2="NUM2")
    cond_lo = cmp_op("operator_lt", tilt_calc_lo, 55)
    bs[tilt_calc_lo]["parent"] = cond_lo
    set_dir_lo = gen(); bs[set_dir_lo] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(55)})
    if_tilt_lo = gen(); bs[if_tilt_lo] = mk("control_if",
        inputs={"CONDITION":[2,cond_lo], "SUBSTACK":[2,set_dir_lo]})
    bs[cond_lo]["parent"] = if_tilt_lo
    bs[set_dir_lo]["parent"] = if_tilt_lo

    # Normal: point in direction (90 - VY*4)
    vy_v_tn = vrep("VY", V_VY)
    tilt_mul_n = op("operator_multiply", vy_v_tn, 4)
    tilt_calc_n = op("operator_subtract", 90, tilt_mul_n, key1="NUM1", key2="NUM2")
    pdir_tilt = gen(); bs[pdir_tilt] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(tilt_calc_n)})
    bs[tilt_calc_n]["parent"] = pdir_tilt

    # wait 0.025
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(if_jump,bs[if_jump]),(if_else_prev,bs[if_else_prev]),
           (grav,bs[grav]),(if_vylo,bs[if_vylo]),(chy,bs[chy]),
           (if_yt,bs[if_yt]),(if_yb,bs[if_yb]),
           (if_top,bs[if_top]),(if_bot,bs[if_bot]),
           (if_best,bs[if_best]),
           (if_tilt_hi,bs[if_tilt_hi]),(if_tilt_lo,bs[if_tilt_lo]),
           (pdir_tilt,bs[pdir_tilt]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_jump]})
    bs[cond_over]["parent"] = rep_until
    bs[if_jump]["parent"] = rep_until

    chain([(h2,bs[h2]),(reset_vy,bs[reset_vy]),(reset_prev,bs[reset_prev]),
           (g0,bs[g0]),(rep_until,bs[rep_until])])

    # === when flag clicked: play pop on game over ===
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=400, y=20)
    state_v_d = vrep("게임상태", V_STATE)
    cond_zero_d = cmp_op("operator_equals", state_v_d, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_zero_d]})
    bs[cond_zero_d]["parent"] = wait_over

    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(-400)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd

    chain([(h3,bs[h3]),(wait_over,bs[wait_over]),(pitch,bs[pitch]),(snd,bs[snd])])

    return bs

# ============================================================
#  TOP PIPE blocks (스폰 + scroll + score count)
# ============================================================
def build_top_pipe_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    # === when receive 파이프스폰: goto + costume + clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["파이프스폰", BR_SPAWN]})

    # y = GAP중심 + GAP크기/2 + 100
    gapy_v = vrep("GAP중심", V_GAPY)
    gaph_v = vrep("GAP크기", V_GAPH)
    half_gap = op("operator_divide", gaph_v, 2, key1="NUM1", key2="NUM2")
    sum1 = op("operator_add", gapy_v, half_gap, key1="NUM1", key2="NUM2")
    sum2 = op("operator_add", sum1, 100, key1="NUM1", key2="NUM2")
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": slot(sum2)})
    bs[sum2]["parent"] = g

    cm = gen(); bs[cm] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    menu_id = bs[cm]["inputs"]["COSTUME"][1]
    bs[menu_id] = mk("looks_costume",
        fields={"COSTUME":["pipe_top", None]}, shadow=True, parent=cm)

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(cm,bs[cm]),(cclone,bs[cclone])])

    # === when I start as clone: init 통과여부, show, scroll loop with score count ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)

    set_passed_0 = gen(); bs[set_passed_0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["통과여부", V_PASSED_TOP]})

    show = gen(); bs[show] = mk("looks_show")

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # change x by (-1 * 스크롤속도)
    scroll_v = vrep("스크롤속도", V_SCROLL)
    neg_scroll = op("operator_multiply", -1, scroll_v)
    chx = gen(); bs[chx] = mk("motion_changexby",
        inputs={"DX": slot(neg_scroll)})
    bs[neg_scroll]["parent"] = chx

    # if x < -100 AND 통과여부=0 → 점수+1, 통과여부=1
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    cond_xlt = cmp_op("operator_lt", xp1, -100)
    bs[xp1]["parent"] = cond_xlt
    passed_v = vrep("통과여부", V_PASSED_TOP)
    cond_npass = cmp_op("operator_equals", passed_v, 0)
    cond_scoring = bool_op("operator_and", cond_xlt, cond_npass)
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    set_passed_1 = gen(); bs[set_passed_1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["통과여부", V_PASSED_TOP]})
    chain([(inc_score,bs[inc_score]),(set_passed_1,bs[set_passed_1])])
    if_score = gen(); bs[if_score] = mk("control_if",
        inputs={"CONDITION":[2,cond_scoring], "SUBSTACK":[2,inc_score]})
    bs[cond_scoring]["parent"] = if_score
    bs[inc_score]["parent"] = if_score

    # if x < -260 → delete this clone
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    cond_off = cmp_op("operator_lt", xp2, -260)
    bs[xp2]["parent"] = cond_off
    del_off = gen(); bs[del_off] = mk("control_delete_this_clone")
    if_off = gen(); bs[if_off] = mk("control_if",
        inputs={"CONDITION":[2,cond_off], "SUBSTACK":[2,del_off]})
    bs[cond_off]["parent"] = if_off
    bs[del_off]["parent"] = if_off

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(chx,bs[chx]),(if_score,bs[if_score]),(if_off,bs[if_off]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,chx]})
    bs[cond_over]["parent"] = rep_until
    bs[chx]["parent"] = rep_until

    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")

    chain([(ch,bs[ch]),(set_passed_0,bs[set_passed_0]),(show,bs[show]),
           (rep_until,bs[rep_until]),(del_end,bs[del_end])])

    return bs

# ============================================================
#  BOTTOM PIPE blocks (스폰 + scroll only, no score)
# ============================================================
def build_bot_pipe_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["파이프스폰", BR_SPAWN]})

    # y = GAP중심 - GAP크기/2 - 100
    gapy_v = vrep("GAP중심", V_GAPY)
    gaph_v = vrep("GAP크기", V_GAPH)
    half_gap = op("operator_divide", gaph_v, 2, key1="NUM1", key2="NUM2")
    sub1 = op("operator_subtract", gapy_v, half_gap, key1="NUM1", key2="NUM2")
    sub2 = op("operator_subtract", sub1, 100, key1="NUM1", key2="NUM2")
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": slot(sub2)})
    bs[sub2]["parent"] = g

    cm = gen(); bs[cm] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    menu_id = bs[cm]["inputs"]["COSTUME"][1]
    bs[menu_id] = mk("looks_costume",
        fields={"COSTUME":["pipe_bot", None]}, shadow=True, parent=cm)

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(cm,bs[cm]),(cclone,bs[cclone])])

    # === when I start as clone: scroll only ===
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

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    bd_md5 = md5_bytes(BIRD_SVG.encode("utf-8"))
    with open(f"{WORK}/{bd_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BIRD_SVG)

    pt_md5 = md5_bytes(PIPE_TOP_SVG.encode("utf-8"))
    with open(f"{WORK}/{pt_md5}.svg", "w", encoding="utf-8") as f:
        f.write(PIPE_TOP_SVG)

    pb_md5 = md5_bytes(PIPE_BOT_SVG.encode("utf-8"))
    with open(f"{WORK}/{pb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(PIPE_BOT_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    bird_blocks     = build_bird_blocks()
    top_blocks      = build_top_pipe_blocks()
    bot_blocks      = build_bot_pipe_blocks()
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
            V_BEST:   ["최고기록", 0],
            V_STATE:  ["게임상태", 1],
            V_VY:     ["VY", 0],
            V_SCROLL: ["스크롤속도", 3],
            V_SPAWN:  ["스폰주기", 1.5],
            V_GAPY:   ["GAP중심", 0],
            V_GAPH:   ["GAP크기", 100],
            V_PREV:   ["이전키", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "파이프스폰",
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

    bird = {
        "isStage": False, "name": "새",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bird_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bird", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bd_md5, "md5ext": f"{bd_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 22
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": -100, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    top_pipe = {
        "isStage": False, "name": "상단파이프",
        "variables": {
            V_PASSED_TOP: ["통과여부", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": top_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "pipe_top", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pt_md5, "md5ext": f"{pt_md5}.svg",
            "rotationCenterX": 50, "rotationCenterY": 100
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    bot_pipe = {
        "isStage": False, "name": "하단파이프",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bot_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "pipe_bot", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pb_md5, "md5ext": f"{pb_md5}.svg",
            "rotationCenterX": 50, "rotationCenterY": 100
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
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
    ]

    project = {
        "targets": [stage, top_pipe, bot_pipe, bird, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "flappy-bird-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # block count summary
    total = sum(len(b) for b in [stage_blocks, bird_blocks, top_blocks,
                                 bot_blocks, gameover_blocks])
    print(f"[flappy-bird] built {OUTPUT}")
    print(f"  stage: {len(stage_blocks)}  bird: {len(bird_blocks)}  "
          f"top: {len(top_blocks)}  bot: {len(bot_blocks)}  "
          f"gameover: {len(gameover_blocks)}  total: {total}")

if __name__ == "__main__":
    main()
