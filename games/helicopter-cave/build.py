#!/usr/bin/env python3
"""Helicopter Cave — 한 버튼으로 헬리콥터 상승, 좁아지는 동굴 통과."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "헬리콥터_동굴.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: dark cave with rough texture --------
random.seed(33)
specks = []
for _ in range(80):
    x = random.randint(0, 480); y = random.randint(0, 360)
    r = random.choice([0.5, 0.7, 0.9, 1.1])
    op = random.uniform(0.20, 0.55)
    specks.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#6D4C41" opacity="{op:.2f}"/>')
SPECKS = "\n    ".join(specks)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="cave" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="#1A1410"/>
      <stop offset="50%"  stop-color="#2C1F18"/>
      <stop offset="100%" stop-color="#1A1410"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#cave)"/>
  <g>
    {SPECKS}
  </g>
</svg>"""

# -------- Helicopter costume 1: rotor horizontal (60x40, side view facing right) --------
HELI_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40" viewBox="0 0 60 40">
  <!-- tail boom -->
  <rect x="2" y="18" width="22" height="6" rx="2" fill="#FFC107" stroke="#5D4037" stroke-width="1.4"/>
  <!-- tail rotor support -->
  <rect x="2" y="14" width="3" height="14" rx="1" fill="#5D4037"/>
  <!-- tail rotor -->
  <line x1="1" y1="10" x2="6" y2="32" stroke="#212121" stroke-width="1.6"/>
  <!-- main body -->
  <ellipse cx="38" cy="22" rx="18" ry="11" fill="#FFC107" stroke="#5D4037" stroke-width="1.6"/>
  <!-- nose -->
  <polygon points="56,22 50,17 50,27" fill="#FFA000" stroke="#5D4037" stroke-width="1.2"/>
  <!-- cockpit window -->
  <ellipse cx="46" cy="20" rx="6" ry="5" fill="#90CAF9" stroke="#1976D2" stroke-width="1.2"/>
  <!-- landing skid -->
  <rect x="28" y="34" width="22" height="2" rx="1" fill="#424242"/>
  <line x1="32" y1="32" x2="32" y2="34" stroke="#424242" stroke-width="1.5"/>
  <line x1="46" y1="32" x2="46" y2="34" stroke="#424242" stroke-width="1.5"/>
  <!-- rotor mast -->
  <rect x="36" y="6" width="4" height="6" rx="1" fill="#424242"/>
  <!-- main rotor: horizontal position -->
  <ellipse cx="38" cy="5" rx="26" ry="1.8" fill="#212121" opacity="0.85"/>
  <ellipse cx="38" cy="5" rx="26" ry="0.8" fill="#616161" opacity="0.5"/>
</svg>"""

# -------- Helicopter costume 2: rotor tilted (60x40, 45-degree rotation effect) --------
HELI_SVG2 = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40" viewBox="0 0 60 40">
  <!-- tail boom -->
  <rect x="2" y="18" width="22" height="6" rx="2" fill="#FFC107" stroke="#5D4037" stroke-width="1.4"/>
  <!-- tail rotor support -->
  <rect x="2" y="14" width="3" height="14" rx="1" fill="#5D4037"/>
  <!-- tail rotor -->
  <line x1="1" y1="10" x2="6" y2="32" stroke="#212121" stroke-width="1.6"/>
  <!-- main body -->
  <ellipse cx="38" cy="22" rx="18" ry="11" fill="#FFC107" stroke="#5D4037" stroke-width="1.6"/>
  <!-- nose -->
  <polygon points="56,22 50,17 50,27" fill="#FFA000" stroke="#5D4037" stroke-width="1.2"/>
  <!-- cockpit window -->
  <ellipse cx="46" cy="20" rx="6" ry="5" fill="#90CAF9" stroke="#1976D2" stroke-width="1.2"/>
  <!-- landing skid -->
  <rect x="28" y="34" width="22" height="2" rx="1" fill="#424242"/>
  <line x1="32" y1="32" x2="32" y2="34" stroke="#424242" stroke-width="1.5"/>
  <line x1="46" y1="32" x2="46" y2="34" stroke="#424242" stroke-width="1.5"/>
  <!-- rotor mast -->
  <rect x="36" y="6" width="4" height="6" rx="1" fill="#424242"/>
  <!-- main rotor: tilted 45° position -->
  <ellipse cx="38" cy="5" rx="18" ry="18" fill="none" stroke="#212121" stroke-width="1.8" opacity="0.7"/>
  <line x1="19" y1="-12" x2="57" y2="22" stroke="#212121" stroke-width="1.8" opacity="0.85"/>
  <line x1="19" y1="22" x2="57" y2="-12" stroke="#212121" stroke-width="1.8" opacity="0.85"/>
</svg>"""

# -------- Ceiling rock chunk (100x100, dark gray, rough bottom edge) --------
CEIL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <!-- main body: rough rectangle, flat top, jagged bottom -->
  <polygon points="0,0 100,0 100,82 92,88 84,80 76,86 68,78 60,90 52,82 44,88 36,78 28,86 20,80 12,90 4,84 0,86"
           fill="#3E2C1F" stroke="#1A1208" stroke-width="1.4"/>
  <!-- inner texture: small dark spots -->
  <circle cx="20" cy="30" r="3" fill="#231509"/>
  <circle cx="60" cy="22" r="2.4" fill="#231509"/>
  <circle cx="80" cy="50" r="3.2" fill="#231509"/>
  <circle cx="30" cy="60" r="2" fill="#231509"/>
  <circle cx="70" cy="68" r="2.6" fill="#231509"/>
  <!-- highlight stripe -->
  <polygon points="10,10 90,10 90,18 10,18" fill="#5D4037" opacity="0.4"/>
</svg>"""

# -------- Floor rock chunk (100x100, dark brown, rough top edge) --------
FLOOR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <!-- main body: rough rectangle, flat bottom, jagged top -->
  <polygon points="0,14 4,16 12,10 20,20 28,14 36,22 44,12 52,18 60,10 68,22 76,14 84,20 92,12 100,18 100,100 0,100"
           fill="#4E342E" stroke="#1A1208" stroke-width="1.4"/>
  <!-- inner texture -->
  <circle cx="20" cy="60" r="3" fill="#2A1810"/>
  <circle cx="60" cy="70" r="2.4" fill="#2A1810"/>
  <circle cx="80" cy="50" r="3.2" fill="#2A1810"/>
  <circle cx="30" cy="80" r="2" fill="#2A1810"/>
  <circle cx="70" cy="40" r="2.6" fill="#2A1810"/>
  <!-- highlight stripe near bottom -->
  <polygon points="10,84 90,84 90,92 10,92" fill="#6D4C41" opacity="0.35"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#FFC107" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#FFC107" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">동굴에 부딪혔어요</text>
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

# ============================================================
#  IDs
# ============================================================
V_SCORE   = "varScore01"
V_BEST    = "varBest02"
V_STATE   = "varState03"
V_VY      = "varVY04"
V_CEILT   = "varCeilT05"
V_FLOORT  = "varFloorT06"
V_SCROLL  = "varScroll07"
V_SPAWN   = "varSpawn08"
V_TICK    = "varTick09"

BR_START  = "brStart01"
BR_SPAWN  = "brSpawn02"

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
    s_ceilt = gen(); bs[s_ceilt] = mk("data_setvariableto",
        inputs={"VALUE": num(40)}, fields={"VARIABLE": ["천장두께", V_CEILT]})
    s_floort = gen(); bs[s_floort] = mk("data_setvariableto",
        inputs={"VALUE": num(40)}, fields={"VARIABLE": ["바닥두께", V_FLOORT]})
    s_scroll = gen(); bs[s_scroll] = mk("data_setvariableto",
        inputs={"VALUE": num(4)}, fields={"VARIABLE": ["스크롤속도", V_SCROLL]})
    s_spawn = gen(); bs[s_spawn] = mk("data_setvariableto",
        inputs={"VALUE": num(0.5)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    s_tick = gen(); bs[s_tick] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["경과틱", V_TICK]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_state,bs[s_state]),(s_vy,bs[s_vy]),
           (s_ceilt,bs[s_ceilt]),(s_floort,bs[s_floort]),(s_scroll,bs[s_scroll]),
           (s_spawn,bs[s_spawn]),(s_tick,bs[s_tick]),(bc_start,bs[bc_start])])

    # === when receive 게임시작 (forever 1: 막대 스폰) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=260,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_a = vrep("게임상태", V_STATE)
    cond_over_a = cmp_op("operator_equals", state_v_a, 0)

    # broadcast 막대스폰
    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["막대스폰", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    # wait 스폰주기
    spawn_v = vrep("스폰주기", V_SPAWN)
    wt_sp = gen(); bs[wt_sp] = mk("control_wait",
        inputs={"DURATION": slot(spawn_v)})
    bs[spawn_v]["parent"] = wt_sp

    chain([(bc_sp,bs[bc_sp]),(wt_sp,bs[wt_sp])])

    rep_until_a = gen(); bs[rep_until_a] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_a], "SUBSTACK":[2,bc_sp]})
    bs[cond_over_a]["parent"] = rep_until_a
    bs[bc_sp]["parent"] = rep_until_a

    chain([(h2,bs[h2]),(rep_until_a,bs[rep_until_a])])

    # === when receive 게임시작 (forever 2: 1초 타이머, 점수+1) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=300, y=260,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_b = vrep("게임상태", V_STATE)
    cond_over_b = cmp_op("operator_equals", state_v_b, 0)

    wt_1 = gen(); bs[wt_1] = mk("control_wait", inputs={"DURATION": num(1)})
    inc_tick = gen(); bs[inc_tick] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["경과틱", V_TICK]})
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    chain([(wt_1,bs[wt_1]),(inc_tick,bs[inc_tick]),(inc_score,bs[inc_score])])

    rep_until_b = gen(); bs[rep_until_b] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_b], "SUBSTACK":[2,wt_1]})
    bs[cond_over_b]["parent"] = rep_until_b
    bs[wt_1]["parent"] = rep_until_b

    chain([(h3,bs[h3]),(rep_until_b,bs[rep_until_b])])

    # === when receive 게임시작 (forever 3: 3초마다 두께 +3, 최대 90) ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=580, y=260,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_c = vrep("게임상태", V_STATE)
    cond_over_c = cmp_op("operator_equals", state_v_c, 0)

    wt_3 = gen(); bs[wt_3] = mk("control_wait", inputs={"DURATION": num(3)})

    # if 천장두께 < 90 → 천장두께 += 3
    ceilt_v = vrep("천장두께", V_CEILT)
    cond_c_lt = cmp_op("operator_lt", ceilt_v, 90)
    inc_ceilt = gen(); bs[inc_ceilt] = mk("data_changevariableby",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["천장두께", V_CEILT]})
    if_c = gen(); bs[if_c] = mk("control_if",
        inputs={"CONDITION":[2,cond_c_lt], "SUBSTACK":[2,inc_ceilt]})
    bs[cond_c_lt]["parent"] = if_c
    bs[inc_ceilt]["parent"] = if_c

    # if 바닥두께 < 90 → 바닥두께 += 3
    floort_v = vrep("바닥두께", V_FLOORT)
    cond_f_lt = cmp_op("operator_lt", floort_v, 90)
    inc_floort = gen(); bs[inc_floort] = mk("data_changevariableby",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["바닥두께", V_FLOORT]})
    if_f = gen(); bs[if_f] = mk("control_if",
        inputs={"CONDITION":[2,cond_f_lt], "SUBSTACK":[2,inc_floort]})
    bs[cond_f_lt]["parent"] = if_f
    bs[inc_floort]["parent"] = if_f

    chain([(wt_3,bs[wt_3]),(if_c,bs[if_c]),(if_f,bs[if_f])])

    rep_until_c = gen(); bs[rep_until_c] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_c], "SUBSTACK":[2,wt_3]})
    bs[cond_over_c]["parent"] = rep_until_c
    bs[wt_3]["parent"] = rep_until_c

    chain([(h4,bs[h4]),(rep_until_c,bs[rep_until_c])])

    return bs

# ============================================================
#  HELICOPTER blocks
# ============================================================
def build_heli_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init pos + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(-150), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: input + physics + collision loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # reset VY = 0, position
    reset_vy = gen(); bs[reset_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": num(-150), "Y": num(0)})

    # repeat until 게임상태 = 0
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # --- input: (space pressed) OR (mouse down) ---
    key_space = gen(); bs[key_space] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sense_sp = gen(); bs[sense_sp] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_space]})
    bs[key_space]["parent"] = sense_sp

    sense_md = gen(); bs[sense_md] = mk("sensing_mousedown")

    cond_input = bool_op("operator_or", sense_sp, sense_md)

    # if input → VY += 0.5  ELSE → VY -= 0.4
    inc_vy = gen(); bs[inc_vy] = mk("data_changevariableby",
        inputs={"VALUE": num(0.5)}, fields={"VARIABLE": ["VY", V_VY]})
    dec_vy = gen(); bs[dec_vy] = mk("data_changevariableby",
        inputs={"VALUE": num(-0.4)}, fields={"VARIABLE": ["VY", V_VY]})

    if_else = gen(); bs[if_else] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_input],
                "SUBSTACK":[2,inc_vy],
                "SUBSTACK2":[2,dec_vy]})
    bs[cond_input]["parent"] = if_else
    bs[inc_vy]["parent"] = if_else
    bs[dec_vy]["parent"] = if_else

    # --- VY clamp top: if VY > 8 → VY = 8 ---
    vy_v1 = vrep("VY", V_VY)
    cond_vyhi = cmp_op("operator_gt", vy_v1, 8)
    set_vy_hi = gen(); bs[set_vy_hi] = mk("data_setvariableto",
        inputs={"VALUE": num(8)}, fields={"VARIABLE": ["VY", V_VY]})
    if_vyhi = gen(); bs[if_vyhi] = mk("control_if",
        inputs={"CONDITION":[2,cond_vyhi], "SUBSTACK":[2,set_vy_hi]})
    bs[cond_vyhi]["parent"] = if_vyhi
    bs[set_vy_hi]["parent"] = if_vyhi

    # --- VY clamp bottom: if VY < -8 → VY = -8 ---
    vy_v2 = vrep("VY", V_VY)
    cond_vylo = cmp_op("operator_lt", vy_v2, -8)
    set_vy_lo = gen(); bs[set_vy_lo] = mk("data_setvariableto",
        inputs={"VALUE": num(-8)}, fields={"VARIABLE": ["VY", V_VY]})
    if_vylo = gen(); bs[if_vylo] = mk("control_if",
        inputs={"CONDITION":[2,cond_vylo], "SUBSTACK":[2,set_vy_lo]})
    bs[cond_vylo]["parent"] = if_vylo
    bs[set_vy_lo]["parent"] = if_vylo

    # --- change y by VY ---
    vy_v3 = vrep("VY", V_VY)
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(vy_v3)})
    bs[vy_v3]["parent"] = chy

    # --- ceiling hard limit: if y > 175 → state=0 ---
    yp_t = gen(); bs[yp_t] = mk("motion_yposition")
    cond_yt = cmp_op("operator_gt", yp_t, 175)
    bs[yp_t]["parent"] = cond_yt
    set_st_t = gen(); bs[set_st_t] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_yt = gen(); bs[if_yt] = mk("control_if",
        inputs={"CONDITION":[2,cond_yt], "SUBSTACK":[2,set_st_t]})
    bs[cond_yt]["parent"] = if_yt
    bs[set_st_t]["parent"] = if_yt

    # --- floor hard limit: if y < -175 → state=0 ---
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cond_yb = cmp_op("operator_lt", yp_b, -175)
    bs[yp_b]["parent"] = cond_yb
    set_st_b = gen(); bs[set_st_b] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_yb = gen(); bs[if_yb] = mk("control_if",
        inputs={"CONDITION":[2,cond_yb], "SUBSTACK":[2,set_st_b]})
    bs[cond_yb]["parent"] = if_yb
    bs[set_st_b]["parent"] = if_yb

    # --- touching 천장막대 OR 바닥막대 → state=0 (단일 control_if) ---
    tm_c = gen(); bs[tm_c] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["천장막대", None]}, shadow=True)
    tc_c = gen(); bs[tc_c] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_c]})
    bs[tm_c]["parent"] = tc_c

    tm_f = gen(); bs[tm_f] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["바닥막대", None]}, shadow=True)
    tc_f = gen(); bs[tc_f] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_f]})
    bs[tm_f]["parent"] = tc_f

    cond_touch = bool_op("operator_or", tc_c, tc_f)
    set_st_touch = gen(); bs[set_st_touch] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_touch = gen(); bs[if_touch] = mk("control_if",
        inputs={"CONDITION":[2,cond_touch], "SUBSTACK":[2,set_st_touch]})
    bs[cond_touch]["parent"] = if_touch
    bs[set_st_touch]["parent"] = if_touch

    # --- next costume: rotor animation ---
    next_cos = gen(); bs[next_cos] = mk("looks_nextcostume")

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

    chain([(if_else,bs[if_else]),(if_vyhi,bs[if_vyhi]),(if_vylo,bs[if_vylo]),
           (chy,bs[chy]),(if_yt,bs[if_yt]),(if_yb,bs[if_yb]),
           (if_touch,bs[if_touch]),(next_cos,bs[next_cos]),(if_best,bs[if_best]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_else]})
    bs[cond_over]["parent"] = rep_until
    bs[if_else]["parent"] = rep_until

    chain([(h2,bs[h2]),(reset_vy,bs[reset_vy]),(g0,bs[g0]),(rep_until,bs[rep_until])])

    # === when game over: play pop sound ===
    # Use a separate hat: when state becomes 0 via wait_until pattern.
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
#  CEILING BAR blocks
# ============================================================
def build_ceil_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide + set size 100 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz_init = gen(); bs[sz_init] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz_init,bs[sz_init])])

    # === when receive 막대스폰: goto + costume + size + clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["막대스폰", BR_SPAWN]})

    # goto (260, 180 - 천장두께/2)
    ceilt_v1 = vrep("천장두께", V_CEILT)
    half_c = op("operator_divide", ceilt_v1, 2, key1="NUM1", key2="NUM2")
    y_top = op("operator_subtract", 180, half_c, key1="NUM1", key2="NUM2")
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": slot(y_top)})
    bs[y_top]["parent"] = g

    # switch costume "ceil"
    cm = gen(); bs[cm] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    menu_id = bs[cm]["inputs"]["COSTUME"][1]
    bs[menu_id] = mk("looks_costume",
        fields={"COSTUME":["ceil", None]}, shadow=True, parent=cm)

    # set size to 천장두께
    ceilt_v2 = vrep("천장두께", V_CEILT)
    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto",
        inputs={"SIZE": slot(ceilt_v2)})
    bs[ceilt_v2]["parent"] = set_sz

    # create clone of _myself_
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(cm,bs[cm]),(set_sz,bs[set_sz]),(cclone,bs[cclone])])

    # === when I start as clone: show + scroll loop ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    show = gen(); bs[show] = mk("looks_show")

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # change x by (-1 * 스크롤속도)
    scroll_v = vrep("스크롤속도", V_SCROLL)
    neg_scroll = op("operator_multiply", -1, scroll_v)
    chx = gen(); bs[chx] = mk("motion_changexby",
        inputs={"DX": slot(neg_scroll)})
    bs[neg_scroll]["parent"] = chx

    # if x < -260 → delete this clone
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
#  FLOOR BAR blocks (same as ceiling, with floor variables)
# ============================================================
def build_floor_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz_init = gen(); bs[sz_init] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz_init,bs[sz_init])])

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["막대스폰", BR_SPAWN]})

    # goto (260, -180 + 바닥두께/2)
    floort_v1 = vrep("바닥두께", V_FLOORT)
    half_f = op("operator_divide", floort_v1, 2, key1="NUM1", key2="NUM2")
    y_bot = op("operator_add", -180, half_f, key1="NUM1", key2="NUM2")
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": slot(y_bot)})
    bs[y_bot]["parent"] = g

    cm = gen(); bs[cm] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    menu_id = bs[cm]["inputs"]["COSTUME"][1]
    bs[menu_id] = mk("looks_costume",
        fields={"COSTUME":["floor", None]}, shadow=True, parent=cm)

    floort_v2 = vrep("바닥두께", V_FLOORT)
    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto",
        inputs={"SIZE": slot(floort_v2)})
    bs[floort_v2]["parent"] = set_sz

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(cm,bs[cm]),(set_sz,bs[set_sz]),(cclone,bs[cclone])])

    # === when I start as clone: scroll ===
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

    # write SVG assets
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    hl_md5 = md5_bytes(HELI_SVG.encode("utf-8"))
    with open(f"{WORK}/{hl_md5}.svg", "w", encoding="utf-8") as f:
        f.write(HELI_SVG)

    hl2_md5 = md5_bytes(HELI_SVG2.encode("utf-8"))
    with open(f"{WORK}/{hl2_md5}.svg", "w", encoding="utf-8") as f:
        f.write(HELI_SVG2)

    ce_md5 = md5_bytes(CEIL_SVG.encode("utf-8"))
    with open(f"{WORK}/{ce_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CEIL_SVG)

    fl_md5 = md5_bytes(FLOOR_SVG.encode("utf-8"))
    with open(f"{WORK}/{fl_md5}.svg", "w", encoding="utf-8") as f:
        f.write(FLOOR_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    # WAV (pop)
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    heli_blocks     = build_heli_blocks()
    ceil_blocks     = build_ceil_blocks()
    floor_blocks    = build_floor_blocks()
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
            V_CEILT:  ["천장두께", 40],
            V_FLOORT: ["바닥두께", 40],
            V_SCROLL: ["스크롤속도", 4],
            V_SPAWN:  ["스폰주기", 0.5],
            V_TICK:   ["경과틱", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "막대스폰",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "동굴", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    helicopter = {
        "isStage": False, "name": "헬리콥터",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": heli_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "heli", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": hl_md5, "md5ext": f"{hl_md5}.svg",
                "rotationCenterX": 30, "rotationCenterY": 20
            },
            {
                "name": "heli2", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": hl2_md5, "md5ext": f"{hl2_md5}.svg",
                "rotationCenterX": 30, "rotationCenterY": 20
            }
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": -150, "y": 0, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ceil_bar = {
        "isStage": False, "name": "천장막대",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ceil_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "ceil", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ce_md5, "md5ext": f"{ce_md5}.svg",
            "rotationCenterX": 50, "rotationCenterY": 50
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 40, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    floor_bar = {
        "isStage": False, "name": "바닥막대",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": floor_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "floor", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": fl_md5, "md5ext": f"{fl_md5}.svg",
            "rotationCenterX": 50, "rotationCenterY": 50
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 40, "direction": 90,
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
        "targets": [stage, ceil_bar, floor_bar, helicopter, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "helicopter-cave-builder"}
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
    print(f"  stage:      {len(stage_blocks)} blocks")
    print(f"  helicopter: {len(heli_blocks)} blocks")
    print(f"  ceil bar:   {len(ceil_blocks)} blocks")
    print(f"  floor bar:  {len(floor_blocks)} blocks")
    print(f"  gameover:   {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(heli_blocks)
             + len(ceil_blocks) + len(floor_blocks) + len(gameover_blocks))
    print(f"  TOTAL:      {total} blocks")

if __name__ == "__main__":
    main()
