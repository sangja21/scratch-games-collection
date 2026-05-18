#!/usr/bin/env python3
"""Meteor Dodge — 우주선이 화면 가득 떨어지는 운석을 피하며 생존."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "운석_회피.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: deep space + stars --------
random.seed(29)
stars = []
for _ in range(90):
    x = random.randint(0, 480); y = random.randint(0, 360)
    r = random.choice([0.6, 0.8, 1.0, 1.2, 1.6])
    op = random.uniform(0.45, 0.95)
    stars.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#FFFFFF" opacity="{op:.2f}"/>')
STARS = "\n    ".join(stars)

nebulae = []
for _ in range(4):
    cx = random.randint(30, 450); cy = random.randint(30, 330)
    rx = random.randint(40, 90);  ry = random.randint(30, 70)
    color = random.choice(["#2E1A47", "#3A1A66", "#1A2E66", "#2C1A4F"])
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

# -------- Meteors (big / med / small — irregular polygons, fiery edges) --------
ROCK_BIG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80">
  <polygon points="14,30 24,10 46,6 64,18 74,38 70,58 54,72 32,72 16,58 8,42"
           fill="#7E5A3C" stroke="#3E2723" stroke-width="2.2"/>
  <polygon points="22,30 32,22 44,24 38,36 28,40" fill="#5D4037" stroke="#3E2723" stroke-width="1"/>
  <polygon points="50,38 60,34 64,46 58,54" fill="#6D4C41" stroke="#3E2723" stroke-width="1"/>
  <circle cx="32" cy="52" r="3" fill="#3E2723"/>
  <circle cx="56" cy="60" r="2.2" fill="#3E2723"/>
  <circle cx="20" cy="48" r="1.8" fill="#3E2723"/>
  <!-- glowing edge -->
  <polygon points="24,10 46,6 64,18" fill="#FF6F00" opacity="0.45"/>
</svg>"""

ROCK_MED_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="10,24 20,8 36,6 50,16 54,34 46,50 30,54 14,46 6,34"
           fill="#8D6E63" stroke="#3E2723" stroke-width="2"/>
  <polygon points="18,24 26,18 36,22 30,32 22,32" fill="#6D4C41" stroke="#3E2723" stroke-width="1"/>
  <circle cx="40" cy="38" r="2.4" fill="#3E2723"/>
  <circle cx="22" cy="42" r="1.6" fill="#3E2723"/>
  <polygon points="20,8 36,6 50,16" fill="#FF8F00" opacity="0.45"/>
</svg>"""

ROCK_SMALL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <polygon points="8,16 14,6 24,4 32,12 34,24 28,32 16,32 6,24"
           fill="#A1887F" stroke="#3E2723" stroke-width="1.6"/>
  <polygon points="14,16 20,12 26,16 22,22 16,22" fill="#6D4C41" stroke="#3E2723" stroke-width="0.8"/>
  <circle cx="24" cy="26" r="1.4" fill="#3E2723"/>
  <polygon points="14,6 24,4 32,12" fill="#FFA000" opacity="0.5"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#FF6F00" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#FF6F00" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">운석에 부딪혔어요</text>
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
V_SCORE  = "varScore01"
V_BEST   = "varBest02"
V_STATE  = "varState03"
V_MX     = "varMX04"
V_MSIZE  = "varMSize05"
V_MSPEED = "varMSpeed06"
V_SPAWN  = "varSpawn07"
V_TICK   = "varTick08"
V_MYV    = "varMyV09"      # meteor sprite-local

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
    s_spawn = gen(); bs[s_spawn] = mk("data_setvariableto",
        inputs={"VALUE": num(1.0)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    s_tick = gen(); bs[s_tick] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["경과틱", V_TICK]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_state,bs[s_state]),
           (s_spawn,bs[s_spawn]),(s_tick,bs[s_tick]),(bc_start,bs[bc_start])])

    # === when receive 게임시작 (forever 1: 운석 스폰 루프) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=240,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # repeat until 게임상태 = 0
    state_v_a = vrep("게임상태", V_STATE)
    cond_over_a = cmp_op("operator_equals", state_v_a, 0)

    # 운석X = random(-220..220)
    rand_x = gen(); bs[rand_x] = mk("operator_random",
        inputs={"FROM": num(-220), "TO": num(220)})
    set_mx = gen(); bs[set_mx] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_x)}, fields={"VARIABLE": ["운석X", V_MX]})
    bs[rand_x]["parent"] = set_mx

    # k = random(1..10) — 한 번 뽑고 3개 if 로 분기
    # 큰: k <= 3 (30%), 중: 4 <= k <= 7 (40%), 작: k >= 8 (30%)
    # Scratch 에 로컬 변수가 없으므로 stage 변수에 임시 저장하는 대신,
    # 각 if 마다 random 을 다시 뽑으면 분포가 깨진다.
    # → 한 번 뽑아서 V_MSIZE 에 임시 저장하고, 그 값을 비교한 뒤 V_MSIZE 를 1/2/3 으로 set.
    # 단순화: random(1..10) 을 V_MSIZE 에 임시 저장 → 비교 후 다시 1/2/3 set.
    rand_k = gen(); bs[rand_k] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(10)})
    set_k = gen(); bs[set_k] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_k)}, fields={"VARIABLE": ["운석크기", V_MSIZE]})
    bs[rand_k]["parent"] = set_k

    # if 운석크기 <= 3 → 큰 (size=1, speed=2.5)
    msz_v1 = vrep("운석크기", V_MSIZE)
    cond_big = cmp_op("operator_lt", msz_v1, 4)
    set_sz1 = gen(); bs[set_sz1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["운석크기", V_MSIZE]})
    set_sp1 = gen(); bs[set_sp1] = mk("data_setvariableto",
        inputs={"VALUE": num(2.5)}, fields={"VARIABLE": ["운석속도", V_MSPEED]})
    chain([(set_sz1,bs[set_sz1]),(set_sp1,bs[set_sp1])])
    if_big = gen(); bs[if_big] = mk("control_if",
        inputs={"CONDITION":[2,cond_big], "SUBSTACK":[2,set_sz1]})
    bs[cond_big]["parent"] = if_big
    bs[set_sz1]["parent"] = if_big

    # if (운석크기 > 3) AND (운석크기 < 8) → 중 (size=2, speed=3.5)
    msz_v2a = vrep("운석크기", V_MSIZE)
    cond_gt3 = cmp_op("operator_gt", msz_v2a, 3)
    msz_v2b = vrep("운석크기", V_MSIZE)
    cond_lt8 = cmp_op("operator_lt", msz_v2b, 8)
    cond_mid = bool_op("operator_and", cond_gt3, cond_lt8)
    set_sz2 = gen(); bs[set_sz2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["운석크기", V_MSIZE]})
    set_sp2 = gen(); bs[set_sp2] = mk("data_setvariableto",
        inputs={"VALUE": num(3.5)}, fields={"VARIABLE": ["운석속도", V_MSPEED]})
    chain([(set_sz2,bs[set_sz2]),(set_sp2,bs[set_sp2])])
    if_mid = gen(); bs[if_mid] = mk("control_if",
        inputs={"CONDITION":[2,cond_mid], "SUBSTACK":[2,set_sz2]})
    bs[cond_mid]["parent"] = if_mid
    bs[set_sz2]["parent"] = if_mid

    # if 운석크기 > 7 → 작 (size=3, speed=4.5)
    msz_v3 = vrep("운석크기", V_MSIZE)
    cond_sml = cmp_op("operator_gt", msz_v3, 7)
    set_sz3 = gen(); bs[set_sz3] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["운석크기", V_MSIZE]})
    set_sp3 = gen(); bs[set_sp3] = mk("data_setvariableto",
        inputs={"VALUE": num(4.5)}, fields={"VARIABLE": ["운석속도", V_MSPEED]})
    chain([(set_sz3,bs[set_sz3]),(set_sp3,bs[set_sp3])])
    if_sml = gen(); bs[if_sml] = mk("control_if",
        inputs={"CONDITION":[2,cond_sml], "SUBSTACK":[2,set_sz3]})
    bs[cond_sml]["parent"] = if_sml
    bs[set_sz3]["parent"] = if_sml

    # broadcast 운석스폰
    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["운석스폰", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    # wait 스폰주기
    spawn_v = vrep("스폰주기", V_SPAWN)
    wt_sp = gen(); bs[wt_sp] = mk("control_wait",
        inputs={"DURATION": slot(spawn_v)})
    bs[spawn_v]["parent"] = wt_sp

    # chain body and wrap in repeat_until
    chain([(set_mx,bs[set_mx]),(set_k,bs[set_k]),
           (if_big,bs[if_big]),(if_mid,bs[if_mid]),(if_sml,bs[if_sml]),
           (bc_sp,bs[bc_sp]),(wt_sp,bs[wt_sp])])

    rep_until_a = gen(); bs[rep_until_a] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_a], "SUBSTACK":[2,set_mx]})
    bs[cond_over_a]["parent"] = rep_until_a
    bs[set_mx]["parent"] = rep_until_a

    chain([(h2,bs[h2]),(rep_until_a,bs[rep_until_a])])

    # === when receive 게임시작 (forever 2: 1초 타이머, 점수+1) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=300, y=240,
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

    # === when receive 게임시작 (forever 3: 5초마다 스폰주기 0.85배 ramp) ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=580, y=240,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_c = vrep("게임상태", V_STATE)
    cond_over_c = cmp_op("operator_equals", state_v_c, 0)

    wt_5 = gen(); bs[wt_5] = mk("control_wait", inputs={"DURATION": num(5)})

    # if 스폰주기 > 0.25 → 스폰주기 = 스폰주기 * 0.85
    sp_v_a = vrep("스폰주기", V_SPAWN)
    cond_sp_gt = cmp_op("operator_gt", sp_v_a, 0.25)
    sp_v_b = vrep("스폰주기", V_SPAWN)
    mul_sp = op("operator_multiply", sp_v_b, 0.85)
    set_sp_new = gen(); bs[set_sp_new] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_sp)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    bs[mul_sp]["parent"] = set_sp_new
    if_ramp = gen(); bs[if_ramp] = mk("control_if",
        inputs={"CONDITION":[2,cond_sp_gt], "SUBSTACK":[2,set_sp_new]})
    bs[cond_sp_gt]["parent"] = if_ramp
    bs[set_sp_new]["parent"] = if_ramp

    chain([(wt_5,bs[wt_5]),(if_ramp,bs[if_ramp])])

    rep_until_c = gen(); bs[rep_until_c] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_c], "SUBSTACK":[2,wt_5]})
    bs[cond_over_c]["parent"] = rep_until_c
    bs[wt_5]["parent"] = rep_until_c

    chain([(h4,bs[h4]),(rep_until_c,bs[rep_until_c])])

    return bs

# ============================================================
#  SHIP blocks
# ============================================================
def build_ship_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init pos + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(0), "Y": num(-100)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(0)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: movement + collision loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # initial position
    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": num(0), "Y": num(-100)})

    # repeat until 게임상태 = 0
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # --- LEFT arrow ---
    key_l = gen(); bs[key_l] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    sense_l = gen(); bs[sense_l] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_l]})
    bs[key_l]["parent"] = sense_l
    chx_l = gen(); bs[chx_l] = mk("motion_changexby", inputs={"DX": num(-5)})
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
    chx_r = gen(); bs[chx_r] = mk("motion_changexby", inputs={"DX": num(5)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION":[2,sense_r], "SUBSTACK":[2,chx_r]})
    bs[sense_r]["parent"] = if_r
    bs[chx_r]["parent"] = if_r

    # --- UP arrow ---
    key_u = gen(); bs[key_u] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["up arrow", None]}, shadow=True)
    sense_u = gen(); bs[sense_u] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_u]})
    bs[key_u]["parent"] = sense_u
    chy_u = gen(); bs[chy_u] = mk("motion_changeyby", inputs={"DY": num(5)})
    if_u = gen(); bs[if_u] = mk("control_if",
        inputs={"CONDITION":[2,sense_u], "SUBSTACK":[2,chy_u]})
    bs[sense_u]["parent"] = if_u
    bs[chy_u]["parent"] = if_u

    # --- DOWN arrow ---
    key_d = gen(); bs[key_d] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["down arrow", None]}, shadow=True)
    sense_d = gen(); bs[sense_d] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_d]})
    bs[key_d]["parent"] = sense_d
    chy_d = gen(); bs[chy_d] = mk("motion_changeyby", inputs={"DY": num(-5)})
    if_d = gen(); bs[if_d] = mk("control_if",
        inputs={"CONDITION":[2,sense_d], "SUBSTACK":[2,chy_d]})
    bs[sense_d]["parent"] = if_d
    bs[chy_d]["parent"] = if_d

    # --- clamp x left ---
    xp_l = gen(); bs[xp_l] = mk("motion_xposition")
    cond_xl = cmp_op("operator_lt", xp_l, -230)
    bs[xp_l]["parent"] = cond_xl
    setx_l = gen(); bs[setx_l] = mk("motion_setx", inputs={"X": num(-230)})
    if_xl = gen(); bs[if_xl] = mk("control_if",
        inputs={"CONDITION":[2,cond_xl], "SUBSTACK":[2,setx_l]})
    bs[cond_xl]["parent"] = if_xl
    bs[setx_l]["parent"] = if_xl

    # --- clamp x right ---
    xp_r = gen(); bs[xp_r] = mk("motion_xposition")
    cond_xr = cmp_op("operator_gt", xp_r, 230)
    bs[xp_r]["parent"] = cond_xr
    setx_r = gen(); bs[setx_r] = mk("motion_setx", inputs={"X": num(230)})
    if_xr = gen(); bs[if_xr] = mk("control_if",
        inputs={"CONDITION":[2,cond_xr], "SUBSTACK":[2,setx_r]})
    bs[cond_xr]["parent"] = if_xr
    bs[setx_r]["parent"] = if_xr

    # --- clamp y bottom ---
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cond_yb = cmp_op("operator_lt", yp_b, -170)
    bs[yp_b]["parent"] = cond_yb
    sety_b = gen(); bs[sety_b] = mk("motion_sety", inputs={"Y": num(-170)})
    if_yb = gen(); bs[if_yb] = mk("control_if",
        inputs={"CONDITION":[2,cond_yb], "SUBSTACK":[2,sety_b]})
    bs[cond_yb]["parent"] = if_yb
    bs[sety_b]["parent"] = if_yb

    # --- clamp y top ---
    yp_t = gen(); bs[yp_t] = mk("motion_yposition")
    cond_yt = cmp_op("operator_gt", yp_t, 170)
    bs[yp_t]["parent"] = cond_yt
    sety_t = gen(); bs[sety_t] = mk("motion_sety", inputs={"Y": num(170)})
    if_yt = gen(); bs[if_yt] = mk("control_if",
        inputs={"CONDITION":[2,cond_yt], "SUBSTACK":[2,sety_t]})
    bs[cond_yt]["parent"] = if_yt
    bs[sety_t]["parent"] = if_yt

    # --- collision: if touching 운석 → state=0, best update, play pop ---
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["운석", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc

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
        inputs={"CONDITION":[2,cond_best], "SUBSTACK":[2,set_best]})
    bs[cond_best]["parent"] = if_best
    bs[set_best]["parent"] = if_best

    # pop @ pitch -400
    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(-400)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd

    chain([(set_state0,bs[set_state0]),(if_best,bs[if_best]),
           (pitch,bs[pitch]),(snd,bs[snd])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION":[2,tc], "SUBSTACK":[2,set_state0]})
    bs[tc]["parent"] = if_hit
    bs[set_state0]["parent"] = if_hit

    # wait 0.025
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(if_l,bs[if_l]),(if_r,bs[if_r]),(if_u,bs[if_u]),(if_d,bs[if_d]),
           (if_xl,bs[if_xl]),(if_xr,bs[if_xr]),(if_yb,bs[if_yb]),(if_yt,bs[if_yt]),
           (if_hit,bs[if_hit]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_l]})
    bs[cond_over]["parent"] = rep_until
    bs[if_l]["parent"] = rep_until

    chain([(h2,bs[h2]),(g0,bs[g0]),(rep_until,bs[rep_until])])

    return bs

# ============================================================
#  METEOR blocks
# ============================================================
def build_meteor_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when receive 운석스폰: position + costume + size + create clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["운석스폰", BR_SPAWN]})

    # goto (운석X, 200)
    mx_v = vrep("운석X", V_MX)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(mx_v), "Y": num(200)})
    bs[mx_v]["parent"] = g

    # if 운석크기 = 1 → costume rock_big + size 100
    msz_v1 = vrep("운석크기", V_MSIZE)
    cond_big = cmp_op("operator_equals", msz_v1, 1)
    cm_big = gen(); bs[cm_big] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    big_menu_id = bs[cm_big]["inputs"]["COSTUME"][1]
    bs[big_menu_id] = mk("looks_costume",
        fields={"COSTUME":["rock_big", None]}, shadow=True, parent=cm_big)
    sz_big = gen(); bs[sz_big] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(cm_big,bs[cm_big]),(sz_big,bs[sz_big])])
    if_big = gen(); bs[if_big] = mk("control_if",
        inputs={"CONDITION":[2,cond_big], "SUBSTACK":[2,cm_big]})
    bs[cond_big]["parent"] = if_big
    bs[cm_big]["parent"] = if_big

    # if 운석크기 = 2 → costume rock_med + size 70
    msz_v2 = vrep("운석크기", V_MSIZE)
    cond_med = cmp_op("operator_equals", msz_v2, 2)
    cm_med = gen(); bs[cm_med] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    med_menu_id = bs[cm_med]["inputs"]["COSTUME"][1]
    bs[med_menu_id] = mk("looks_costume",
        fields={"COSTUME":["rock_med", None]}, shadow=True, parent=cm_med)
    sz_med = gen(); bs[sz_med] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    chain([(cm_med,bs[cm_med]),(sz_med,bs[sz_med])])
    if_med = gen(); bs[if_med] = mk("control_if",
        inputs={"CONDITION":[2,cond_med], "SUBSTACK":[2,cm_med]})
    bs[cond_med]["parent"] = if_med
    bs[cm_med]["parent"] = if_med

    # if 운석크기 = 3 → costume rock_small + size 50
    msz_v3 = vrep("운석크기", V_MSIZE)
    cond_sml = cmp_op("operator_equals", msz_v3, 3)
    cm_sml = gen(); bs[cm_sml] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    sml_menu_id = bs[cm_sml]["inputs"]["COSTUME"][1]
    bs[sml_menu_id] = mk("looks_costume",
        fields={"COSTUME":["rock_small", None]}, shadow=True, parent=cm_sml)
    sz_sml = gen(); bs[sz_sml] = mk("looks_setsizeto", inputs={"SIZE": num(50)})
    chain([(cm_sml,bs[cm_sml]),(sz_sml,bs[sz_sml])])
    if_sml = gen(); bs[if_sml] = mk("control_if",
        inputs={"CONDITION":[2,cond_sml], "SUBSTACK":[2,cm_sml]})
    bs[cond_sml]["parent"] = if_sml
    bs[cm_sml]["parent"] = if_sml

    # 내속도 = 운석속도
    spd_v = vrep("운석속도", V_MSPEED)
    set_myv = gen(); bs[set_myv] = mk("data_setvariableto",
        inputs={"VALUE": slot(spd_v)}, fields={"VARIABLE": ["내속도", V_MYV]})
    bs[spd_v]["parent"] = set_myv

    # create clone of _myself_
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(if_big,bs[if_big]),(if_med,bs[if_med]),
           (if_sml,bs[if_sml]),(set_myv,bs[set_myv]),(cclone,bs[cclone])])

    # === when I start as clone: show + fall loop ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    show = gen(); bs[show] = mk("looks_show")

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # change y by (-1 * 내속도)
    myv_v = vrep("내속도", V_MYV)
    neg_myv = op("operator_multiply", -1, myv_v)
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(neg_myv)})
    bs[neg_myv]["parent"] = chy

    # if y < -200 → delete this clone
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_off = cmp_op("operator_lt", yp, -200)
    bs[yp]["parent"] = cond_off
    del_off = gen(); bs[del_off] = mk("control_delete_this_clone")
    if_off = gen(); bs[if_off] = mk("control_if",
        inputs={"CONDITION":[2,cond_off], "SUBSTACK":[2,del_off]})
    bs[cond_off]["parent"] = if_off
    bs[del_off]["parent"] = if_off

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(chy,bs[chy]),(if_off,bs[if_off]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,chy]})
    bs[cond_over]["parent"] = rep_until
    bs[chy]["parent"] = rep_until

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

    sh_md5 = md5_bytes(SHIP_SVG.encode("utf-8"))
    with open(f"{WORK}/{sh_md5}.svg", "w", encoding="utf-8") as f:
        f.write(SHIP_SVG)

    rb_md5 = md5_bytes(ROCK_BIG_SVG.encode("utf-8"))
    with open(f"{WORK}/{rb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(ROCK_BIG_SVG)

    rm_md5 = md5_bytes(ROCK_MED_SVG.encode("utf-8"))
    with open(f"{WORK}/{rm_md5}.svg", "w", encoding="utf-8") as f:
        f.write(ROCK_MED_SVG)

    rs_md5 = md5_bytes(ROCK_SMALL_SVG.encode("utf-8"))
    with open(f"{WORK}/{rs_md5}.svg", "w", encoding="utf-8") as f:
        f.write(ROCK_SMALL_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    # WAV (pop)
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    ship_blocks     = build_ship_blocks()
    meteor_blocks   = build_meteor_blocks()
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
            V_MX:     ["운석X", 0],
            V_MSIZE:  ["운석크기", 1],
            V_MSPEED: ["운석속도", 3],
            V_SPAWN:  ["스폰주기", 1.0],
            V_TICK:   ["경과틱", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "운석스폰",
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
            "name": "우주선", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": sh_md5, "md5ext": f"{sh_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 22
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": 0, "y": -100, "size": 70, "direction": 0,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    meteor = {
        "isStage": False, "name": "운석",
        "variables": {V_MYV: ["내속도", 3]},
        "lists": {}, "broadcasts": {},
        "blocks": meteor_blocks, "comments": {},
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
        "targets": [stage, meteor, ship, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "meteor-dodge-builder"}
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
    print(f"  meteor:   {len(meteor_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(ship_blocks)
             + len(meteor_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
