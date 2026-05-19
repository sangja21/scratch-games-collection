#!/usr/bin/env python3
"""Apple Catch — 바구니를 좌우로 움직여 떨어지는 사과를 받고 폭탄을 피한다."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "사과_받기.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: sky + grass + clouds --------
random.seed(11)
clouds = []
for cx, cy, sx in [(80, 70, 1.0), (340, 50, 1.15), (200, 110, 0.8)]:
    clouds.append(
        f'<g transform="translate({cx},{cy}) scale({sx})">'
        f'<ellipse cx="0" cy="0" rx="38" ry="14" fill="#FFFFFF" opacity="0.95"/>'
        f'<ellipse cx="-20" cy="6" rx="22" ry="12" fill="#FFFFFF" opacity="0.95"/>'
        f'<ellipse cx="22" cy="6" rx="26" ry="13" fill="#FFFFFF" opacity="0.95"/>'
        f'</g>'
    )
CLOUDS = "\n  ".join(clouds)

# grass blades
blades = []
for _ in range(40):
    x = random.randint(0, 480)
    h = random.randint(6, 14)
    blades.append(
        f'<path d="M{x},290 q1,{-h/2} 0,{-h} q-1,{-h/2} 0,{-h}" '
        f'stroke="#2E7D32" stroke-width="1.2" fill="none"/>'
    )
BLADES = "\n  ".join(blades)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#B3E5FC"/>
  <rect y="270" width="480" height="90" fill="#66BB6A"/>
  <rect y="285" width="480" height="6" fill="#43A047"/>
  {CLOUDS}
  {BLADES}
  <!-- sun -->
  <circle cx="430" cy="50" r="22" fill="#FFEB3B" stroke="#FBC02D" stroke-width="2"/>
</svg>"""

# -------- Basket (wide wicker basket with handle) --------
BASKET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="70" viewBox="0 0 100 70">
  <!-- handle -->
  <path d="M20,32 q30,-30 60,0" stroke="#6D4C41" stroke-width="5" fill="none" stroke-linecap="round"/>
  <!-- basket body -->
  <path d="M10,30 L90,30 L82,62 L18,62 Z" fill="#8D6E63" stroke="#4E342E" stroke-width="2.5"/>
  <!-- weave horizontal lines -->
  <line x1="14" y1="38" x2="86" y2="38" stroke="#5D4037" stroke-width="1.4"/>
  <line x1="15" y1="46" x2="85" y2="46" stroke="#5D4037" stroke-width="1.4"/>
  <line x1="16" y1="54" x2="84" y2="54" stroke="#5D4037" stroke-width="1.4"/>
  <!-- weave vertical -->
  <line x1="30" y1="30" x2="27" y2="62" stroke="#4E342E" stroke-width="1.2"/>
  <line x1="50" y1="30" x2="50" y2="62" stroke="#4E342E" stroke-width="1.2"/>
  <line x1="70" y1="30" x2="73" y2="62" stroke="#4E342E" stroke-width="1.2"/>
  <!-- rim -->
  <ellipse cx="50" cy="30" rx="40" ry="5" fill="#A1887F" stroke="#4E342E" stroke-width="2"/>
</svg>"""

# -------- Apple (red apple with leaf and stem) --------
APPLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="56" viewBox="0 0 50 56">
  <!-- shadow -->
  <ellipse cx="25" cy="52" rx="14" ry="3" fill="#000000" opacity="0.18"/>
  <!-- apple body -->
  <path d="M25,10 C8,10 5,28 8,40 C11,52 22,54 25,54 C28,54 39,52 42,40 C45,28 42,10 25,10 Z"
        fill="#E53935" stroke="#B71C1C" stroke-width="2"/>
  <!-- highlight -->
  <ellipse cx="17" cy="22" rx="5" ry="8" fill="#FFCDD2" opacity="0.75"/>
  <!-- stem -->
  <path d="M25,12 q1,-6 3,-8" stroke="#5D4037" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <!-- leaf -->
  <path d="M28,8 q8,-2 10,4 q-6,2 -10,-4 Z" fill="#66BB6A" stroke="#2E7D32" stroke-width="1.2"/>
</svg>"""

# -------- Bomb (black sphere with fuse and spark) --------
BOMB_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="56" viewBox="0 0 50 56">
  <!-- shadow -->
  <ellipse cx="25" cy="52" rx="15" ry="3" fill="#000000" opacity="0.22"/>
  <!-- bomb body -->
  <circle cx="25" cy="34" r="18" fill="#212121" stroke="#000000" stroke-width="2"/>
  <!-- highlight -->
  <ellipse cx="17" cy="26" rx="5" ry="3.5" fill="#616161" opacity="0.85"/>
  <!-- fuse cap -->
  <rect x="22" y="12" width="6" height="5" fill="#6D4C41" stroke="#3E2723" stroke-width="1.2"/>
  <!-- fuse curve -->
  <path d="M25,12 q4,-6 8,-8" stroke="#8D6E63" stroke-width="2.2" fill="none" stroke-linecap="round"/>
  <!-- spark -->
  <circle cx="34" cy="3" r="3.5" fill="#FFEB3B"/>
  <circle cx="34" cy="3" r="1.8" fill="#FF6F00"/>
  <line x1="34" y1="3" x2="40" y2="0" stroke="#FFEB3B" stroke-width="1.2"/>
  <line x1="34" y1="3" x2="38" y2="8" stroke="#FFEB3B" stroke-width="1.2"/>
  <line x1="34" y1="3" x2="29" y2="-2" stroke="#FFEB3B" stroke-width="1.2"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#E53935" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#E53935" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">라이프가 모두 떨어졌어요</text>
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
V_LIFE   = "varLife03"
V_STATE  = "varState04"
V_AX     = "varAX05"
V_ATYPE  = "varAType06"
V_ASPEED = "varASpeed07"
V_SPAWN  = "varSpawn08"
V_TICK   = "varTick09"
V_MYV    = "varMyV10"      # apple sprite-local
V_MYT    = "varMyT11"      # apple sprite-local

BR_START = "brStart01"
BR_SPAWN = "brSpawn02"

# ============================================================
#  helper: build "lose 1 life + maybe game over" sub-stack
#  returns (first_block_id, last_block_id)
# ============================================================
def build_lose_life(bs, vrep, cmp_op):
    # 라이프 = 라이프 - 1
    dec_life = gen(); bs[dec_life] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["라이프", V_LIFE]})

    # if 라이프 < 1 → 게임상태 = 0 + best update
    life_v = vrep("라이프", V_LIFE)
    cond_dead = cmp_op("operator_lt", life_v, 1)

    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})

    # best update
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

    chain([(set_state0,bs[set_state0]),(if_best,bs[if_best])])

    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION":[2,cond_dead], "SUBSTACK":[2,set_state0]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state0]["parent"] = if_dead

    chain([(dec_life,bs[dec_life]),(if_dead,bs[if_dead])])
    return dec_life, if_dead

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
    s_life = gen(); bs[s_life] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["라이프", V_LIFE]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    s_spawn = gen(); bs[s_spawn] = mk("data_setvariableto",
        inputs={"VALUE": num(0.9)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    s_tick = gen(); bs[s_tick] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["경과틱", V_TICK]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_life,bs[s_life]),
           (s_state,bs[s_state]),(s_spawn,bs[s_spawn]),(s_tick,bs[s_tick]),
           (bc_start,bs[bc_start])])

    # === when receive 게임시작 (forever 1: 과일 스폰 루프) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=240,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_a = vrep("게임상태", V_STATE)
    cond_over_a = cmp_op("operator_equals", state_v_a, 0)

    # 사과X = random(-210..210)
    rand_x = gen(); bs[rand_x] = mk("operator_random",
        inputs={"FROM": num(-210), "TO": num(210)})
    set_ax = gen(); bs[set_ax] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_x)}, fields={"VARIABLE": ["사과X", V_AX]})
    bs[rand_x]["parent"] = set_ax

    # k = random(1..10) → 임시로 사과타입 에 저장 후 비교
    # 1~8 → 사과(1), 9~10 → 폭탄(2)
    rand_k = gen(); bs[rand_k] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(10)})
    set_k = gen(); bs[set_k] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_k)}, fields={"VARIABLE": ["사과타입", V_ATYPE]})
    bs[rand_k]["parent"] = set_k

    # if 사과타입 < 9 → 사과타입 = 1
    at_v1 = vrep("사과타입", V_ATYPE)
    cond_apple = cmp_op("operator_lt", at_v1, 9)
    set_t1 = gen(); bs[set_t1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["사과타입", V_ATYPE]})
    if_apple = gen(); bs[if_apple] = mk("control_if",
        inputs={"CONDITION":[2,cond_apple], "SUBSTACK":[2,set_t1]})
    bs[cond_apple]["parent"] = if_apple
    bs[set_t1]["parent"] = if_apple

    # if 사과타입 > 8 → 사과타입 = 2
    at_v2 = vrep("사과타입", V_ATYPE)
    cond_bomb = cmp_op("operator_gt", at_v2, 8)
    set_t2 = gen(); bs[set_t2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["사과타입", V_ATYPE]})
    if_bomb = gen(); bs[if_bomb] = mk("control_if",
        inputs={"CONDITION":[2,cond_bomb], "SUBSTACK":[2,set_t2]})
    bs[cond_bomb]["parent"] = if_bomb
    bs[set_t2]["parent"] = if_bomb

    # 사과속도 = random(3..6)
    rand_sp = gen(); bs[rand_sp] = mk("operator_random",
        inputs={"FROM": num(3), "TO": num(6)})
    set_sp = gen(); bs[set_sp] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_sp)}, fields={"VARIABLE": ["사과속도", V_ASPEED]})
    bs[rand_sp]["parent"] = set_sp

    # broadcast 과일스폰
    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["과일스폰", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    # wait 스폰주기
    spawn_v = vrep("스폰주기", V_SPAWN)
    wt_sp = gen(); bs[wt_sp] = mk("control_wait",
        inputs={"DURATION": slot(spawn_v)})
    bs[spawn_v]["parent"] = wt_sp

    chain([(set_ax,bs[set_ax]),(set_k,bs[set_k]),
           (if_apple,bs[if_apple]),(if_bomb,bs[if_bomb]),
           (set_sp,bs[set_sp]),(bc_sp,bs[bc_sp]),(wt_sp,bs[wt_sp])])

    rep_until_a = gen(); bs[rep_until_a] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_a], "SUBSTACK":[2,set_ax]})
    bs[cond_over_a]["parent"] = rep_until_a
    bs[set_ax]["parent"] = rep_until_a

    chain([(h2,bs[h2]),(rep_until_a,bs[rep_until_a])])

    # === when receive 게임시작 (forever 2: 1초 타이머) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=300, y=240,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_b = vrep("게임상태", V_STATE)
    cond_over_b = cmp_op("operator_equals", state_v_b, 0)

    wt_1 = gen(); bs[wt_1] = mk("control_wait", inputs={"DURATION": num(1)})
    inc_tick = gen(); bs[inc_tick] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["경과틱", V_TICK]})
    chain([(wt_1,bs[wt_1]),(inc_tick,bs[inc_tick])])

    rep_until_b = gen(); bs[rep_until_b] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_b], "SUBSTACK":[2,wt_1]})
    bs[cond_over_b]["parent"] = rep_until_b
    bs[wt_1]["parent"] = rep_until_b

    chain([(h3,bs[h3]),(rep_until_b,bs[rep_until_b])])

    # === when receive 게임시작 (forever 3: 5초마다 스폰주기 0.88배 ramp) ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=580, y=240,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_c = vrep("게임상태", V_STATE)
    cond_over_c = cmp_op("operator_equals", state_v_c, 0)

    wt_5 = gen(); bs[wt_5] = mk("control_wait", inputs={"DURATION": num(5)})

    # if 스폰주기 > 0.30 → 스폰주기 = 스폰주기 * 0.88
    sp_v_a = vrep("스폰주기", V_SPAWN)
    cond_sp_gt = cmp_op("operator_gt", sp_v_a, 0.30)
    sp_v_b = vrep("스폰주기", V_SPAWN)
    mul_sp = op("operator_multiply", sp_v_b, 0.88)
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
#  BASKET blocks
# ============================================================
def build_basket_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init pos + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(0), "Y": num(-130)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: movement loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": num(0), "Y": num(-130)})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # --- LEFT arrow ---
    key_l = gen(); bs[key_l] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    sense_l = gen(); bs[sense_l] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_l]})
    bs[key_l]["parent"] = sense_l
    chx_l = gen(); bs[chx_l] = mk("motion_changexby", inputs={"DX": num(-8)})
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
    chx_r = gen(); bs[chx_r] = mk("motion_changexby", inputs={"DX": num(8)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION":[2,sense_r], "SUBSTACK":[2,chx_r]})
    bs[sense_r]["parent"] = if_r
    bs[chx_r]["parent"] = if_r

    # --- clamp x left ---
    xp_l = gen(); bs[xp_l] = mk("motion_xposition")
    cond_xl = cmp_op("operator_lt", xp_l, -210)
    bs[xp_l]["parent"] = cond_xl
    setx_l = gen(); bs[setx_l] = mk("motion_setx", inputs={"X": num(-210)})
    if_xl = gen(); bs[if_xl] = mk("control_if",
        inputs={"CONDITION":[2,cond_xl], "SUBSTACK":[2,setx_l]})
    bs[cond_xl]["parent"] = if_xl
    bs[setx_l]["parent"] = if_xl

    # --- clamp x right ---
    xp_r = gen(); bs[xp_r] = mk("motion_xposition")
    cond_xr = cmp_op("operator_gt", xp_r, 210)
    bs[xp_r]["parent"] = cond_xr
    setx_r = gen(); bs[setx_r] = mk("motion_setx", inputs={"X": num(210)})
    if_xr = gen(); bs[if_xr] = mk("control_if",
        inputs={"CONDITION":[2,cond_xr], "SUBSTACK":[2,setx_r]})
    bs[cond_xr]["parent"] = if_xr
    bs[setx_r]["parent"] = if_xr

    # wait 0.025
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(if_l,bs[if_l]),(if_r,bs[if_r]),
           (if_xl,bs[if_xl]),(if_xr,bs[if_xr]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_l]})
    bs[cond_over]["parent"] = rep_until
    bs[if_l]["parent"] = rep_until

    chain([(h2,bs[h2]),(g0,bs[g0]),(rep_until,bs[rep_until])])

    return bs

# ============================================================
#  APPLE blocks (spawn handler + clone fall loop)
# ============================================================
def build_apple_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when receive 과일스폰: position + costume + create clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["과일스폰", BR_SPAWN]})

    # goto (사과X, 200)
    ax_v = vrep("사과X", V_AX)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(ax_v), "Y": num(200)})
    bs[ax_v]["parent"] = g

    # if 사과타입 = 1 → costume apple
    at_v1 = vrep("사과타입", V_ATYPE)
    cond_apple = cmp_op("operator_equals", at_v1, 1)
    cm_apple = gen(); bs[cm_apple] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    apple_menu_id = bs[cm_apple]["inputs"]["COSTUME"][1]
    bs[apple_menu_id] = mk("looks_costume",
        fields={"COSTUME":["apple", None]}, shadow=True, parent=cm_apple)
    if_apple = gen(); bs[if_apple] = mk("control_if",
        inputs={"CONDITION":[2,cond_apple], "SUBSTACK":[2,cm_apple]})
    bs[cond_apple]["parent"] = if_apple
    bs[cm_apple]["parent"] = if_apple

    # if 사과타입 = 2 → costume bomb
    at_v2 = vrep("사과타입", V_ATYPE)
    cond_bomb = cmp_op("operator_equals", at_v2, 2)
    cm_bomb = gen(); bs[cm_bomb] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    bomb_menu_id = bs[cm_bomb]["inputs"]["COSTUME"][1]
    bs[bomb_menu_id] = mk("looks_costume",
        fields={"COSTUME":["bomb", None]}, shadow=True, parent=cm_bomb)
    if_bomb = gen(); bs[if_bomb] = mk("control_if",
        inputs={"CONDITION":[2,cond_bomb], "SUBSTACK":[2,cm_bomb]})
    bs[cond_bomb]["parent"] = if_bomb
    bs[cm_bomb]["parent"] = if_bomb

    # 내속도 = 사과속도
    spd_v = vrep("사과속도", V_ASPEED)
    set_myv = gen(); bs[set_myv] = mk("data_setvariableto",
        inputs={"VALUE": slot(spd_v)}, fields={"VARIABLE": ["내속도", V_MYV]})
    bs[spd_v]["parent"] = set_myv

    # 내타입 = 사과타입
    at_v3 = vrep("사과타입", V_ATYPE)
    set_myt = gen(); bs[set_myt] = mk("data_setvariableto",
        inputs={"VALUE": slot(at_v3)}, fields={"VARIABLE": ["내타입", V_MYT]})
    bs[at_v3]["parent"] = set_myt

    # create clone of _myself_
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(if_apple,bs[if_apple]),(if_bomb,bs[if_bomb]),
           (set_myv,bs[set_myv]),(set_myt,bs[set_myt]),(cclone,bs[cclone])])

    # === when I start as clone: show + fall + collision loop ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    show = gen(); bs[show] = mk("looks_show")
    # ensure clone is at proper size
    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # change y by (-1 * 내속도)
    myv_v = vrep("내속도", V_MYV)
    neg_myv = op("operator_multiply", -1, myv_v)
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(neg_myv)})
    bs[neg_myv]["parent"] = chy

    # --- collision: if touching 바구니 ---
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["바구니", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc

    # if 내타입 = 1 → 점수 += 1
    myt_v1 = vrep("내타입", V_MYT)
    cond_t_apple = cmp_op("operator_equals", myt_v1, 1)
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    if_t_apple = gen(); bs[if_t_apple] = mk("control_if",
        inputs={"CONDITION":[2,cond_t_apple], "SUBSTACK":[2,inc_score]})
    bs[cond_t_apple]["parent"] = if_t_apple
    bs[inc_score]["parent"] = if_t_apple

    # if 내타입 = 2 → 라이프 -= 1 + maybe game over
    myt_v2 = vrep("내타입", V_MYT)
    cond_t_bomb = cmp_op("operator_equals", myt_v2, 2)
    lose_first_b, _ = build_lose_life(bs, vrep, cmp_op)
    if_t_bomb = gen(); bs[if_t_bomb] = mk("control_if",
        inputs={"CONDITION":[2,cond_t_bomb], "SUBSTACK":[2,lose_first_b]})
    bs[cond_t_bomb]["parent"] = if_t_bomb
    bs[lose_first_b]["parent"] = if_t_bomb

    # delete this clone (after catch handled)
    del_hit = gen(); bs[del_hit] = mk("control_delete_this_clone")

    chain([(if_t_apple,bs[if_t_apple]),(if_t_bomb,bs[if_t_bomb]),(del_hit,bs[del_hit])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION":[2,tc], "SUBSTACK":[2,if_t_apple]})
    bs[tc]["parent"] = if_hit
    bs[if_t_apple]["parent"] = if_hit

    # --- bottom: if y < -180 ---
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_off = cmp_op("operator_lt", yp, -180)
    bs[yp]["parent"] = cond_off

    # if 내타입 = 1 (놓친 사과) → 라이프 -1 + maybe game over
    myt_v3 = vrep("내타입", V_MYT)
    cond_t_apple2 = cmp_op("operator_equals", myt_v3, 1)
    lose_first_a, _ = build_lose_life(bs, vrep, cmp_op)
    if_miss = gen(); bs[if_miss] = mk("control_if",
        inputs={"CONDITION":[2,cond_t_apple2], "SUBSTACK":[2,lose_first_a]})
    bs[cond_t_apple2]["parent"] = if_miss
    bs[lose_first_a]["parent"] = if_miss

    del_off = gen(); bs[del_off] = mk("control_delete_this_clone")
    chain([(if_miss,bs[if_miss]),(del_off,bs[del_off])])

    if_off = gen(); bs[if_off] = mk("control_if",
        inputs={"CONDITION":[2,cond_off], "SUBSTACK":[2,if_miss]})
    bs[cond_off]["parent"] = if_off
    bs[if_miss]["parent"] = if_off

    # wait 0.025
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    chain([(chy,bs[chy]),(if_hit,bs[if_hit]),(if_off,bs[if_off]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,chy]})
    bs[cond_over]["parent"] = rep_until
    bs[chy]["parent"] = rep_until

    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(ch,bs[ch]),(show,bs[show]),(set_sz,bs[set_sz]),
           (rep_until,bs[rep_until]),(del_end,bs[del_end])])

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

    bk_md5 = md5_bytes(BASKET_SVG.encode("utf-8"))
    with open(f"{WORK}/{bk_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BASKET_SVG)

    ap_md5 = md5_bytes(APPLE_SVG.encode("utf-8"))
    with open(f"{WORK}/{ap_md5}.svg", "w", encoding="utf-8") as f:
        f.write(APPLE_SVG)

    bo_md5 = md5_bytes(BOMB_SVG.encode("utf-8"))
    with open(f"{WORK}/{bo_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BOMB_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    # WAV (pop)
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    basket_blocks   = build_basket_blocks()
    apple_blocks    = build_apple_blocks()
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
            V_LIFE:   ["라이프", 3],
            V_STATE:  ["게임상태", 1],
            V_AX:     ["사과X", 0],
            V_ATYPE:  ["사과타입", 1],
            V_ASPEED: ["사과속도", 4],
            V_SPAWN:  ["스폰주기", 0.9],
            V_TICK:   ["경과틱", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "과일스폰",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "배경", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    basket = {
        "isStage": False, "name": "바구니",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": basket_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "바구니", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bk_md5, "md5ext": f"{bk_md5}.svg",
            "rotationCenterX": 50, "rotationCenterY": 35
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": 0, "y": -130, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    apple = {
        "isStage": False, "name": "사과",
        "variables": {
            V_MYV: ["내속도", 4],
            V_MYT: ["내타입", 1],
        },
        "lists": {}, "broadcasts": {},
        "blocks": apple_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "apple", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ap_md5, "md5ext": f"{ap_md5}.svg",
             "rotationCenterX": 25, "rotationCenterY": 28},
            {"name": "bomb", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bo_md5, "md5ext": f"{bo_md5}.svg",
             "rotationCenterX": 25, "rotationCenterY": 28},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
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
        {"id": V_LIFE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라이프"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, basket, apple, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "apple-catch-builder"}
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
    print(f"  basket:   {len(basket_blocks)} blocks")
    print(f"  apple:    {len(apple_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(basket_blocks)
             + len(apple_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
