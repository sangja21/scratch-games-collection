#!/usr/bin/env python3
"""Car Race — 좌/우 화살표로 차선 변경, 위에서 내려오는 적 차를 회피."""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "자동차_레이싱.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: grass + 4-lane road + edge stripes (정적) --------
# 도로 폭 240px (x = -120..+120 → 0..480 무대 좌표에서 120..360)
# 풀밭: 0..120, 360..480
# 차선 경계: 240 (가운데), 180 (좌측), 300 (우측). y 방향 점선은 페인트라인 sprite 가 처리.
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <!-- grass left/right -->
  <rect x="0" y="0" width="120" height="360" fill="#2E7D32"/>
  <rect x="360" y="0" width="120" height="360" fill="#2E7D32"/>
  <!-- grass texture dots -->
  <g fill="#1B5E20" opacity="0.6">
    <circle cx="20" cy="40" r="3"/><circle cx="60" cy="80" r="2.5"/>
    <circle cx="35" cy="140" r="3"/><circle cx="90" cy="180" r="2.5"/>
    <circle cx="50" cy="240" r="3"/><circle cx="25" cy="300" r="2.5"/>
    <circle cx="80" cy="340" r="3"/>
    <circle cx="400" cy="40" r="3"/><circle cx="440" cy="90" r="2.5"/>
    <circle cx="385" cy="150" r="3"/><circle cx="450" cy="200" r="2.5"/>
    <circle cx="410" cy="260" r="3"/><circle cx="445" cy="310" r="2.5"/>
    <circle cx="380" cy="340" r="3"/>
  </g>
  <!-- road -->
  <rect x="120" y="0" width="240" height="360" fill="#37474F"/>
  <!-- road edge stripes (solid white) -->
  <rect x="118" y="0" width="4" height="360" fill="#FFFFFF"/>
  <rect x="358" y="0" width="4" height="360" fill="#FFFFFF"/>
  <!-- 약한 음영 (도로 양쪽 edge near grass) -->
  <rect x="122" y="0" width="6" height="360" fill="#000000" opacity="0.18"/>
  <rect x="352" y="0" width="6" height="360" fill="#000000" opacity="0.18"/>
</svg>"""

# -------- Player car (위에서 본 흰/하늘 자동차) --------
PLAYER_CAR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="64" viewBox="0 0 40 64">
  <!-- shadow -->
  <rect x="3" y="6" width="34" height="54" rx="7" fill="#000000" opacity="0.25"/>
  <!-- body -->
  <rect x="2" y="4" width="34" height="54" rx="7" fill="#E3F2FD" stroke="#1565C0" stroke-width="2"/>
  <!-- hood -->
  <rect x="6" y="6" width="26" height="14" rx="3" fill="#90CAF9" stroke="#1565C0" stroke-width="1"/>
  <!-- windshield -->
  <rect x="6" y="22" width="26" height="14" rx="3" fill="#0D47A1" stroke="#1565C0" stroke-width="1"/>
  <!-- rear window -->
  <rect x="6" y="38" width="26" height="10" rx="3" fill="#1976D2" stroke="#1565C0" stroke-width="1"/>
  <!-- trunk line -->
  <rect x="6" y="50" width="26" height="6" rx="2" fill="#BBDEFB" stroke="#1565C0" stroke-width="1"/>
  <!-- wheels -->
  <rect x="0" y="14" width="6" height="12" rx="2" fill="#212121"/>
  <rect x="34" y="14" width="6" height="12" rx="2" fill="#212121"/>
  <rect x="0" y="40" width="6" height="12" rx="2" fill="#212121"/>
  <rect x="34" y="40" width="6" height="12" rx="2" fill="#212121"/>
  <!-- headlights (앞을 향함 = 위쪽) -->
  <circle cx="10" cy="7" r="2.2" fill="#FFEB3B"/>
  <circle cx="28" cy="7" r="2.2" fill="#FFEB3B"/>
</svg>"""

# -------- Enemy cars (3색, 위에서 본 모양. 헤드라이트는 아래쪽으로 = 마주 오는 차 느낌) --------
def enemy_car_svg(body, dark):
    # 적 차는 아래로 내려오면서 플레이어 차와 마주봄. 헤드라이트는 아래쪽.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="40" height="64" viewBox="0 0 40 64">
  <rect x="3" y="6" width="34" height="54" rx="7" fill="#000000" opacity="0.25"/>
  <rect x="2" y="4" width="34" height="54" rx="7" fill="{body}" stroke="{dark}" stroke-width="2"/>
  <!-- back (위쪽) -->
  <rect x="6" y="6" width="26" height="10" rx="3" fill="{dark}" opacity="0.5"/>
  <!-- rear window -->
  <rect x="6" y="18" width="26" height="10" rx="3" fill="{dark}"/>
  <!-- windshield -->
  <rect x="6" y="30" width="26" height="14" rx="3" fill="{dark}"/>
  <!-- hood (아래쪽) -->
  <rect x="6" y="46" width="26" height="10" rx="3" fill="{body}" stroke="{dark}" stroke-width="1"/>
  <!-- wheels -->
  <rect x="0" y="14" width="6" height="12" rx="2" fill="#212121"/>
  <rect x="34" y="14" width="6" height="12" rx="2" fill="#212121"/>
  <rect x="0" y="40" width="6" height="12" rx="2" fill="#212121"/>
  <rect x="34" y="40" width="6" height="12" rx="2" fill="#212121"/>
  <!-- headlights at bottom (마주오는 느낌) -->
  <circle cx="10" cy="57" r="2.4" fill="#FFF59D"/>
  <circle cx="28" cy="57" r="2.4" fill="#FFF59D"/>
</svg>"""

CAR_RED_SVG    = enemy_car_svg("#E53935", "#7F0000")
CAR_BLUE_SVG   = enemy_car_svg("#1E88E5", "#0D47A1")
CAR_YELLOW_SVG = enemy_car_svg("#FDD835", "#7E6500")

# -------- Lane paint stripe (흰 점선 한 토막) --------
LANE_PAINT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="10" height="36" viewBox="0 0 10 36">
  <rect x="1" y="1" width="8" height="34" rx="2" fill="#FFFFFF" stroke="#E0E0E0" stroke-width="0.6"/>
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
        font-size="18">충돌!</text>
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
V_LANE    = "varLane04"
V_EX      = "varEX05"
V_ECOLOR  = "varEColor06"
V_ESPEED  = "varESpeed07"
V_SPAWN   = "varSpawn08"
V_LSPEED  = "varLSpeed09"
V_TICK    = "varTick10"
V_LX      = "varLX11"
V_MYV     = "varMyV12"      # enemy sprite-local
V_MYL     = "varMyL13"      # lane-paint sprite-local

BR_START = "brStart01"
BR_SPAWN = "brSpawn02"
BR_LINE  = "brLine03"

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
    s_lane = gen(); bs[s_lane] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["차선", V_LANE]})
    s_espd = gen(); bs[s_espd] = mk("data_setvariableto",
        inputs={"VALUE": num(4)}, fields={"VARIABLE": ["적속도", V_ESPEED]})
    s_lspd = gen(); bs[s_lspd] = mk("data_setvariableto",
        inputs={"VALUE": num(6)}, fields={"VARIABLE": ["라인속도", V_LSPEED]})
    s_spawn = gen(); bs[s_spawn] = mk("data_setvariableto",
        inputs={"VALUE": num(0.9)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    s_tick = gen(); bs[s_tick] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["경과틱", V_TICK]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_state,bs[s_state]),
           (s_lane,bs[s_lane]),(s_espd,bs[s_espd]),(s_lspd,bs[s_lspd]),
           (s_spawn,bs[s_spawn]),(s_tick,bs[s_tick]),(bc_start,bs[bc_start])])

    # === when receive 게임시작 (forever 1: 적차 스폰 루프) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=260,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_a = vrep("게임상태", V_STATE)
    cond_over_a = cmp_op("operator_equals", state_v_a, 0)

    # k = random(1..4); 적X = (k * 60) - 150
    rand_lane = gen(); bs[rand_lane] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(4)})
    # 임시로 V_EX 에 k 저장 후 곱셈 하기보다는, 한번 random→임시 변수로 안 거치고
    # (random * 60) - 150 식을 직접 계산해 V_EX 에 set.
    mul60 = gen(); bs[mul60] = mk("operator_multiply",
        inputs={"NUM1": slot(rand_lane), "NUM2": num(60)})
    bs[rand_lane]["parent"] = mul60
    sub150 = gen(); bs[sub150] = mk("operator_subtract",
        inputs={"NUM1": slot(mul60), "NUM2": num(150)})
    bs[mul60]["parent"] = sub150
    set_ex = gen(); bs[set_ex] = mk("data_setvariableto",
        inputs={"VALUE": slot(sub150)}, fields={"VARIABLE": ["적X", V_EX]})
    bs[sub150]["parent"] = set_ex

    # 적색상 = random(1..3)
    rand_c = gen(); bs[rand_c] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(3)})
    set_ec = gen(); bs[set_ec] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_c)}, fields={"VARIABLE": ["적색상", V_ECOLOR]})
    bs[rand_c]["parent"] = set_ec

    # broadcast 적스폰
    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적스폰", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    # wait 스폰주기
    spawn_v = vrep("스폰주기", V_SPAWN)
    wt_sp = gen(); bs[wt_sp] = mk("control_wait",
        inputs={"DURATION": slot(spawn_v)})
    bs[spawn_v]["parent"] = wt_sp

    chain([(set_ex,bs[set_ex]),(set_ec,bs[set_ec]),(bc_sp,bs[bc_sp]),(wt_sp,bs[wt_sp])])

    rep_until_a = gen(); bs[rep_until_a] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_a], "SUBSTACK":[2,set_ex]})
    bs[cond_over_a]["parent"] = rep_until_a
    bs[set_ex]["parent"] = rep_until_a

    chain([(h2,bs[h2]),(rep_until_a,bs[rep_until_a])])

    # === when receive 게임시작 (forever 2: 페인트 라인 스폰) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=300, y=260,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_b = vrep("게임상태", V_STATE)
    cond_over_b = cmp_op("operator_equals", state_v_b, 0)

    # m = random(1..3); 라인X = (m * 60) - 120  → -60 / 0 / +60
    rand_m = gen(); bs[rand_m] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(3)})
    mul60b = gen(); bs[mul60b] = mk("operator_multiply",
        inputs={"NUM1": slot(rand_m), "NUM2": num(60)})
    bs[rand_m]["parent"] = mul60b
    sub120 = gen(); bs[sub120] = mk("operator_subtract",
        inputs={"NUM1": slot(mul60b), "NUM2": num(120)})
    bs[mul60b]["parent"] = sub120
    set_lx = gen(); bs[set_lx] = mk("data_setvariableto",
        inputs={"VALUE": slot(sub120)}, fields={"VARIABLE": ["라인X", V_LX]})
    bs[sub120]["parent"] = set_lx

    # broadcast 라인스폰
    bm_ln = gen(); bs[bm_ln] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["라인스폰", BR_LINE]}, shadow=True)
    bc_ln = gen(); bs[bc_ln] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ln]})
    bs[bm_ln]["parent"] = bc_ln

    # wait 0.18
    wt_ln = gen(); bs[wt_ln] = mk("control_wait", inputs={"DURATION": num(0.18)})

    chain([(set_lx,bs[set_lx]),(bc_ln,bs[bc_ln]),(wt_ln,bs[wt_ln])])

    rep_until_b = gen(); bs[rep_until_b] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_b], "SUBSTACK":[2,set_lx]})
    bs[cond_over_b]["parent"] = rep_until_b
    bs[set_lx]["parent"] = rep_until_b

    chain([(h3,bs[h3]),(rep_until_b,bs[rep_until_b])])

    # === when receive 게임시작 (forever 3: 1초 타이머 + 점수+1) ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=580, y=260,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_c = vrep("게임상태", V_STATE)
    cond_over_c = cmp_op("operator_equals", state_v_c, 0)

    wt_1 = gen(); bs[wt_1] = mk("control_wait", inputs={"DURATION": num(1)})
    inc_tick = gen(); bs[inc_tick] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["경과틱", V_TICK]})
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    chain([(wt_1,bs[wt_1]),(inc_tick,bs[inc_tick]),(inc_score,bs[inc_score])])

    rep_until_c = gen(); bs[rep_until_c] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_c], "SUBSTACK":[2,wt_1]})
    bs[cond_over_c]["parent"] = rep_until_c
    bs[wt_1]["parent"] = rep_until_c

    chain([(h4,bs[h4]),(rep_until_c,bs[rep_until_c])])

    # === when receive 게임시작 (forever 4: 5초마다 스폰주기/속도 ramp) ===
    h5 = gen(); bs[h5] = mk("event_whenbroadcastreceived", top=True, x=860, y=260,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_d = vrep("게임상태", V_STATE)
    cond_over_d = cmp_op("operator_equals", state_v_d, 0)

    wt_5 = gen(); bs[wt_5] = mk("control_wait", inputs={"DURATION": num(5)})

    # if 스폰주기 > 0.30 → 스폰주기 = 스폰주기 * 0.88
    sp_v_a = vrep("스폰주기", V_SPAWN)
    cond_sp_gt = cmp_op("operator_gt", sp_v_a, 0.30)
    sp_v_b = vrep("스폰주기", V_SPAWN)
    mul_sp = op("operator_multiply", sp_v_b, 0.88)
    set_sp_new = gen(); bs[set_sp_new] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_sp)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    bs[mul_sp]["parent"] = set_sp_new
    if_ramp_sp = gen(); bs[if_ramp_sp] = mk("control_if",
        inputs={"CONDITION":[2,cond_sp_gt], "SUBSTACK":[2,set_sp_new]})
    bs[cond_sp_gt]["parent"] = if_ramp_sp
    bs[set_sp_new]["parent"] = if_ramp_sp

    # if 적속도 < 9 → 적속도 += 0.6
    es_v_a = vrep("적속도", V_ESPEED)
    cond_es_lt = cmp_op("operator_lt", es_v_a, 9)
    inc_es = gen(); bs[inc_es] = mk("data_changevariableby",
        inputs={"VALUE": num(0.6)}, fields={"VARIABLE": ["적속도", V_ESPEED]})
    if_ramp_es = gen(); bs[if_ramp_es] = mk("control_if",
        inputs={"CONDITION":[2,cond_es_lt], "SUBSTACK":[2,inc_es]})
    bs[cond_es_lt]["parent"] = if_ramp_es
    bs[inc_es]["parent"] = if_ramp_es

    # if 라인속도 < 12 → 라인속도 += 0.8
    ls_v_a = vrep("라인속도", V_LSPEED)
    cond_ls_lt = cmp_op("operator_lt", ls_v_a, 12)
    inc_ls = gen(); bs[inc_ls] = mk("data_changevariableby",
        inputs={"VALUE": num(0.8)}, fields={"VARIABLE": ["라인속도", V_LSPEED]})
    if_ramp_ls = gen(); bs[if_ramp_ls] = mk("control_if",
        inputs={"CONDITION":[2,cond_ls_lt], "SUBSTACK":[2,inc_ls]})
    bs[cond_ls_lt]["parent"] = if_ramp_ls
    bs[inc_ls]["parent"] = if_ramp_ls

    chain([(wt_5,bs[wt_5]),(if_ramp_sp,bs[if_ramp_sp]),
           (if_ramp_es,bs[if_ramp_es]),(if_ramp_ls,bs[if_ramp_ls])])

    rep_until_d = gen(); bs[rep_until_d] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_d], "SUBSTACK":[2,wt_5]})
    bs[cond_over_d]["parent"] = rep_until_d
    bs[wt_5]["parent"] = rep_until_d

    chain([(h5,bs[h5]),(rep_until_d,bs[rep_until_d])])

    return bs

# ============================================================
#  PLAYER CAR blocks
# ============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init pos + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(-30), "Y": num(-130)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(0)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: lane snap + collision loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # reset lane=2, x=-30, y=-130
    set_lane_init = gen(); bs[set_lane_init] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["차선", V_LANE]})
    set_x_init = gen(); bs[set_x_init] = mk("motion_setx", inputs={"X": num(-30)})
    set_y_init = gen(); bs[set_y_init] = mk("motion_sety", inputs={"Y": num(-130)})

    # repeat until 게임상태 = 0
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # --- LEFT arrow: if (key left AND 차선 > 1) → 차선 -= 1, wait until NOT key left ---
    key_l_a = gen(); bs[key_l_a] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    sense_l_a = gen(); bs[sense_l_a] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_l_a]})
    bs[key_l_a]["parent"] = sense_l_a
    lane_v_l = vrep("차선", V_LANE)
    cond_l_gt1 = cmp_op("operator_gt", lane_v_l, 1)
    cond_l_and = bool_op("operator_and", sense_l_a, cond_l_gt1)

    dec_lane = gen(); bs[dec_lane] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["차선", V_LANE]})
    # wait until NOT key left
    key_l_b = gen(); bs[key_l_b] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    sense_l_b = gen(); bs[sense_l_b] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_l_b]})
    bs[key_l_b]["parent"] = sense_l_b
    not_l = gen(); bs[not_l] = mk("operator_not", inputs={"OPERAND":[2,sense_l_b]})
    bs[sense_l_b]["parent"] = not_l
    wait_not_l = gen(); bs[wait_not_l] = mk("control_wait_until",
        inputs={"CONDITION":[2, not_l]})
    bs[not_l]["parent"] = wait_not_l
    chain([(dec_lane,bs[dec_lane]),(wait_not_l,bs[wait_not_l])])

    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION":[2,cond_l_and], "SUBSTACK":[2,dec_lane]})
    bs[cond_l_and]["parent"] = if_l
    bs[dec_lane]["parent"] = if_l

    # --- RIGHT arrow: if (key right AND 차선 < 4) → 차선 += 1, wait until NOT key right ---
    key_r_a = gen(); bs[key_r_a] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    sense_r_a = gen(); bs[sense_r_a] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_r_a]})
    bs[key_r_a]["parent"] = sense_r_a
    lane_v_r = vrep("차선", V_LANE)
    cond_r_lt4 = cmp_op("operator_lt", lane_v_r, 4)
    cond_r_and = bool_op("operator_and", sense_r_a, cond_r_lt4)

    inc_lane = gen(); bs[inc_lane] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["차선", V_LANE]})
    key_r_b = gen(); bs[key_r_b] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    sense_r_b = gen(); bs[sense_r_b] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, key_r_b]})
    bs[key_r_b]["parent"] = sense_r_b
    not_r = gen(); bs[not_r] = mk("operator_not", inputs={"OPERAND":[2,sense_r_b]})
    bs[sense_r_b]["parent"] = not_r
    wait_not_r = gen(); bs[wait_not_r] = mk("control_wait_until",
        inputs={"CONDITION":[2, not_r]})
    bs[not_r]["parent"] = wait_not_r
    chain([(inc_lane,bs[inc_lane]),(wait_not_r,bs[wait_not_r])])

    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION":[2,cond_r_and], "SUBSTACK":[2,inc_lane]})
    bs[cond_r_and]["parent"] = if_r
    bs[inc_lane]["parent"] = if_r

    # --- set x to (차선 * 60) - 150 ---
    lane_v_x = vrep("차선", V_LANE)
    mul_lane = op("operator_multiply", lane_v_x, 60)
    sub_lane = gen(); bs[sub_lane] = mk("operator_subtract",
        inputs={"NUM1": slot(mul_lane), "NUM2": num(150)})
    bs[mul_lane]["parent"] = sub_lane
    set_x_loop = gen(); bs[set_x_loop] = mk("motion_setx",
        inputs={"X": slot(sub_lane)})
    bs[sub_lane]["parent"] = set_x_loop

    # --- collision: if touching 적차 → 게임상태=0, best update, play pop ---
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["적차", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc

    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})

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

    # pop @ pitch -300 (crash sound)
    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT":["PITCH", None]})
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

    chain([(if_l,bs[if_l]),(if_r,bs[if_r]),
           (set_x_loop,bs[set_x_loop]),(if_hit,bs[if_hit]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_l]})
    bs[cond_over]["parent"] = rep_until
    bs[if_l]["parent"] = rep_until

    chain([(h2,bs[h2]),(set_lane_init,bs[set_lane_init]),
           (set_x_init,bs[set_x_init]),(set_y_init,bs[set_y_init]),
           (rep_until,bs[rep_until])])

    return bs

# ============================================================
#  ENEMY CAR blocks (spawn handler + clone fall loop)
# ============================================================
def build_enemy_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when receive 적스폰: position + costume + create clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["적스폰", BR_SPAWN]})

    # goto (적X, 210)
    ex_v = vrep("적X", V_EX)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(ex_v), "Y": num(210)})
    bs[ex_v]["parent"] = g

    # if 적색상 = 1 → costume car_red
    ec_v1 = vrep("적색상", V_ECOLOR)
    cond_red = cmp_op("operator_equals", ec_v1, 1)
    cm_red = gen(); bs[cm_red] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    red_menu_id = bs[cm_red]["inputs"]["COSTUME"][1]
    bs[red_menu_id] = mk("looks_costume",
        fields={"COSTUME":["car_red", None]}, shadow=True, parent=cm_red)
    if_red = gen(); bs[if_red] = mk("control_if",
        inputs={"CONDITION":[2,cond_red], "SUBSTACK":[2,cm_red]})
    bs[cond_red]["parent"] = if_red
    bs[cm_red]["parent"] = if_red

    # if 적색상 = 2 → costume car_blue
    ec_v2 = vrep("적색상", V_ECOLOR)
    cond_blue = cmp_op("operator_equals", ec_v2, 2)
    cm_blue = gen(); bs[cm_blue] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    blue_menu_id = bs[cm_blue]["inputs"]["COSTUME"][1]
    bs[blue_menu_id] = mk("looks_costume",
        fields={"COSTUME":["car_blue", None]}, shadow=True, parent=cm_blue)
    if_blue = gen(); bs[if_blue] = mk("control_if",
        inputs={"CONDITION":[2,cond_blue], "SUBSTACK":[2,cm_blue]})
    bs[cond_blue]["parent"] = if_blue
    bs[cm_blue]["parent"] = if_blue

    # if 적색상 = 3 → costume car_yellow
    ec_v3 = vrep("적색상", V_ECOLOR)
    cond_yel = cmp_op("operator_equals", ec_v3, 3)
    cm_yel = gen(); bs[cm_yel] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    yel_menu_id = bs[cm_yel]["inputs"]["COSTUME"][1]
    bs[yel_menu_id] = mk("looks_costume",
        fields={"COSTUME":["car_yellow", None]}, shadow=True, parent=cm_yel)
    if_yel = gen(); bs[if_yel] = mk("control_if",
        inputs={"CONDITION":[2,cond_yel], "SUBSTACK":[2,cm_yel]})
    bs[cond_yel]["parent"] = if_yel
    bs[cm_yel]["parent"] = if_yel

    # 내속도 = 적속도
    spd_v = vrep("적속도", V_ESPEED)
    set_myv = gen(); bs[set_myv] = mk("data_setvariableto",
        inputs={"VALUE": slot(spd_v)}, fields={"VARIABLE": ["내속도", V_MYV]})
    bs[spd_v]["parent"] = set_myv

    # create clone of _myself_
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(if_red,bs[if_red]),(if_blue,bs[if_blue]),
           (if_yel,bs[if_yel]),(set_myv,bs[set_myv]),(cclone,bs[cclone])])

    # === when I start as clone: show + fall loop ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    show = gen(); bs[show] = mk("looks_show")
    # 적 차 크기 70
    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})

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
    chain([(ch,bs[ch]),(show,bs[show]),(set_sz,bs[set_sz]),
           (rep_until,bs[rep_until]),(del_end,bs[del_end])])

    return bs

# ============================================================
#  LANE PAINT blocks (spawn + clone scroll)
# ============================================================
def build_paint_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when receive 라인스폰: position + 라인내속도 = 라인속도 + clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["라인스폰", BR_LINE]})

    lx_v = vrep("라인X", V_LX)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(lx_v), "Y": num(210)})
    bs[lx_v]["parent"] = g

    lspd_v = vrep("라인속도", V_LSPEED)
    set_myl = gen(); bs[set_myl] = mk("data_setvariableto",
        inputs={"VALUE": slot(lspd_v)}, fields={"VARIABLE": ["라인내속도", V_MYL]})
    bs[lspd_v]["parent"] = set_myl

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(set_myl,bs[set_myl]),(cclone,bs[cclone])])

    # === when I start as clone: show + go to back + scroll loop ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    show = gen(); bs[show] = mk("looks_show")
    back = gen(); bs[back] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["back", None]})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    myl_v = vrep("라인내속도", V_MYL)
    neg_myl = op("operator_multiply", -1, myl_v)
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(neg_myl)})
    bs[neg_myl]["parent"] = chy

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
    chain([(ch,bs[ch]),(show,bs[show]),(back,bs[back]),
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

    pc_md5 = md5_bytes(PLAYER_CAR_SVG.encode("utf-8"))
    with open(f"{WORK}/{pc_md5}.svg", "w", encoding="utf-8") as f:
        f.write(PLAYER_CAR_SVG)

    cr_md5 = md5_bytes(CAR_RED_SVG.encode("utf-8"))
    with open(f"{WORK}/{cr_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CAR_RED_SVG)

    cb_md5 = md5_bytes(CAR_BLUE_SVG.encode("utf-8"))
    with open(f"{WORK}/{cb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CAR_BLUE_SVG)

    cy_md5 = md5_bytes(CAR_YELLOW_SVG.encode("utf-8"))
    with open(f"{WORK}/{cy_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CAR_YELLOW_SVG)

    lp_md5 = md5_bytes(LANE_PAINT_SVG.encode("utf-8"))
    with open(f"{WORK}/{lp_md5}.svg", "w", encoding="utf-8") as f:
        f.write(LANE_PAINT_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    # WAV (pop)
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    player_blocks   = build_player_blocks()
    enemy_blocks    = build_enemy_blocks()
    paint_blocks    = build_paint_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:   ["점수", 0],
            V_BEST:    ["최고기록", 0],
            V_STATE:   ["게임상태", 1],
            V_LANE:    ["차선", 2],
            V_EX:      ["적X", 0],
            V_ECOLOR:  ["적색상", 1],
            V_ESPEED:  ["적속도", 4],
            V_SPAWN:   ["스폰주기", 0.9],
            V_LSPEED:  ["라인속도", 6],
            V_TICK:    ["경과틱", 0],
            V_LX:      ["라인X", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "적스폰",
            BR_LINE:  "라인스폰",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "도로", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    player = {
        "isStage": False, "name": "내차",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": player_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "내차", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pc_md5, "md5ext": f"{pc_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 32
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": True,
        "x": -30, "y": -130, "size": 70, "direction": 0,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    enemy = {
        "isStage": False, "name": "적차",
        "variables": {V_MYV: ["내속도", 4]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "car_red", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": cr_md5, "md5ext": f"{cr_md5}.svg",
             "rotationCenterX": 20, "rotationCenterY": 32},
            {"name": "car_blue", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": cb_md5, "md5ext": f"{cb_md5}.svg",
             "rotationCenterX": 20, "rotationCenterY": 32},
            {"name": "car_yellow", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": cy_md5, "md5ext": f"{cy_md5}.svg",
             "rotationCenterX": 20, "rotationCenterY": 32},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    paint = {
        "isStage": False, "name": "페인트라인",
        "variables": {V_MYL: ["라인내속도", 6]},
        "lists": {}, "broadcasts": {},
        "blocks": paint_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "stripe", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": lp_md5, "md5ext": f"{lp_md5}.svg",
            "rotationCenterX": 5, "rotationCenterY": 18
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": False,
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
        "volume": 100, "layerOrder": 5, "visible": False,
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
        "targets": [stage, paint, enemy, player, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "car-race-builder"}
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
    print(f"  paint:    {len(paint_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(player_blocks)
             + len(enemy_blocks) + len(paint_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
