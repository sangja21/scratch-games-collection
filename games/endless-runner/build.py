#!/usr/bin/env python3
"""Endless Runner — 자동 달리기 + 점프/슬라이드로 장애물 회피."""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "엔드리스_러너.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: dusk desert (orange sky → sand) --------
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="#FF7043"/>
      <stop offset="55%"  stop-color="#FFB74D"/>
      <stop offset="80%"  stop-color="#FFE0B2"/>
      <stop offset="100%" stop-color="#FFCC80"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <!-- sun -->
  <circle cx="380" cy="120" r="38" fill="#FFEE58" opacity="0.85"/>
  <circle cx="380" cy="120" r="54" fill="#FFEE58" opacity="0.3"/>
  <!-- distant mountains -->
  <polygon points="0,260 70,200 140,250 210,180 290,260 360,210 440,260 480,230 480,300 0,300" fill="#8D6E63" opacity="0.7"/>
  <polygon points="0,290 60,250 120,280 200,240 270,290 340,260 420,290 480,270 480,320 0,320" fill="#5D4037" opacity="0.7"/>
  <!-- sand floor band -->
  <rect x="0" y="290" width="480" height="70" fill="#D7B083"/>
  <rect x="0" y="290" width="480" height="6" fill="#B0844F"/>
</svg>"""

# -------- Runner (60x80) — friendly pixel-like character, frame 1 (left leg forward) --------
RUNNER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80" viewBox="0 0 60 80">
  <!-- head -->
  <circle cx="30" cy="14" r="11" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.6"/>
  <!-- hair cap -->
  <path d="M19,12 Q30,0 41,12 Q41,8 30,4 Q19,8 19,12 Z" fill="#5D4037"/>
  <!-- eye -->
  <circle cx="34" cy="14" r="1.6" fill="#212121"/>
  <!-- smile -->
  <path d="M30,18 Q34,21 37,18" stroke="#5D4037" stroke-width="1.2" fill="none"/>
  <!-- body (red shirt) -->
  <rect x="18" y="24" width="24" height="26" rx="6" fill="#E53935" stroke="#B71C1C" stroke-width="1.6"/>
  <!-- arm front (swinging forward) -->
  <rect x="38" y="28" width="8" height="20" rx="4" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.4"/>
  <!-- arm back -->
  <rect x="14" y="30" width="8" height="18" rx="4" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.4"/>
  <!-- shorts (blue) -->
  <rect x="20" y="48" width="20" height="10" fill="#1E88E5" stroke="#0D47A1" stroke-width="1.4"/>
  <!-- leg front (left leg forward) -->
  <rect x="18" y="58" width="8" height="18" rx="3" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.4"/>
  <!-- leg back (right leg back) -->
  <rect x="34" y="56" width="8" height="12" rx="3" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.4"/>
  <!-- shoes -->
  <ellipse cx="22" cy="77" rx="6" ry="2.4" fill="#212121"/>
  <ellipse cx="38" cy="69" rx="6" ry="2.4" fill="#212121"/>
</svg>"""

# -------- Runner frame 2 (right leg forward) — alternate running pose --------
RUNNER_RUN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80" viewBox="0 0 60 80">
  <!-- head -->
  <circle cx="30" cy="14" r="11" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.6"/>
  <!-- hair cap -->
  <path d="M19,12 Q30,0 41,12 Q41,8 30,4 Q19,8 19,12 Z" fill="#5D4037"/>
  <!-- eye -->
  <circle cx="34" cy="14" r="1.6" fill="#212121"/>
  <!-- smile -->
  <path d="M30,18 Q34,21 37,18" stroke="#5D4037" stroke-width="1.2" fill="none"/>
  <!-- body (red shirt) -->
  <rect x="18" y="24" width="24" height="26" rx="6" fill="#E53935" stroke="#B71C1C" stroke-width="1.6"/>
  <!-- arm front (swinging back) -->
  <rect x="38" y="32" width="8" height="18" rx="4" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.4"/>
  <!-- arm back (swinging forward) -->
  <rect x="14" y="26" width="8" height="22" rx="4" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.4"/>
  <!-- shorts (blue) -->
  <rect x="20" y="48" width="20" height="10" fill="#1E88E5" stroke="#0D47A1" stroke-width="1.4"/>
  <!-- leg front (right leg forward) -->
  <rect x="34" y="58" width="8" height="18" rx="3" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.4"/>
  <!-- leg back (left leg back) -->
  <rect x="18" y="56" width="8" height="12" rx="3" fill="#FFE0B2" stroke="#5D4037" stroke-width="1.4"/>
  <!-- shoes -->
  <ellipse cx="38" cy="77" rx="6" ry="2.4" fill="#212121"/>
  <ellipse cx="22" cy="69" rx="6" ry="2.4" fill="#212121"/>
</svg>"""

# -------- Cactus (50x60) — ground obstacle --------
CACTUS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="60" viewBox="0 0 50 60">
  <!-- main stem -->
  <rect x="20" y="6" width="14" height="52" rx="5" fill="#388E3C" stroke="#1B5E20" stroke-width="1.6"/>
  <!-- left arm -->
  <rect x="6" y="22" width="10" height="20" rx="4" fill="#388E3C" stroke="#1B5E20" stroke-width="1.6"/>
  <rect x="6" y="18" width="10" height="8" rx="3" fill="#388E3C" stroke="#1B5E20" stroke-width="1.6"/>
  <!-- right arm -->
  <rect x="36" y="14" width="10" height="20" rx="4" fill="#388E3C" stroke="#1B5E20" stroke-width="1.6"/>
  <rect x="36" y="10" width="10" height="8" rx="3" fill="#388E3C" stroke="#1B5E20" stroke-width="1.6"/>
  <!-- spines (white dots) -->
  <circle cx="27" cy="16" r="1.2" fill="#FFFFFF"/>
  <circle cx="27" cy="28" r="1.2" fill="#FFFFFF"/>
  <circle cx="27" cy="40" r="1.2" fill="#FFFFFF"/>
  <circle cx="27" cy="50" r="1.2" fill="#FFFFFF"/>
  <circle cx="11" cy="30" r="1.2" fill="#FFFFFF"/>
  <circle cx="41" cy="22" r="1.2" fill="#FFFFFF"/>
</svg>"""

# -------- Bat (70x40) — air obstacle --------
BAT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="70" height="40" viewBox="0 0 70 40">
  <!-- left wing -->
  <path d="M35,20 Q18,4 4,14 Q12,18 6,26 Q18,22 35,26 Z" fill="#37474F" stroke="#212121" stroke-width="1.4"/>
  <!-- right wing -->
  <path d="M35,20 Q52,4 66,14 Q58,18 64,26 Q52,22 35,26 Z" fill="#37474F" stroke="#212121" stroke-width="1.4"/>
  <!-- body -->
  <ellipse cx="35" cy="22" rx="9" ry="11" fill="#212121" stroke="#000000" stroke-width="1.4"/>
  <!-- ears -->
  <polygon points="30,10 32,4 34,11" fill="#212121"/>
  <polygon points="40,10 38,4 36,11" fill="#212121"/>
  <!-- red eyes -->
  <circle cx="32" cy="20" r="1.4" fill="#E53935"/>
  <circle cx="38" cy="20" r="1.4" fill="#E53935"/>
  <!-- fang -->
  <polygon points="34,26 35,29 36,26" fill="#FFFFFF"/>
</svg>"""

# -------- Ground band (480x30) --------
GROUND_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="30" viewBox="0 0 480 30">
  <rect x="0" y="0" width="480" height="30" fill="#A1763C"/>
  <rect x="0" y="0" width="480" height="3" fill="#7A5328"/>
  <!-- pebble dots -->
  <circle cx="40"  cy="14" r="2" fill="#5D4037" opacity="0.6"/>
  <circle cx="120" cy="20" r="2" fill="#5D4037" opacity="0.6"/>
  <circle cx="200" cy="12" r="2" fill="#5D4037" opacity="0.6"/>
  <circle cx="290" cy="22" r="2" fill="#5D4037" opacity="0.6"/>
  <circle cx="370" cy="16" r="2" fill="#5D4037" opacity="0.6"/>
  <circle cx="440" cy="10" r="2" fill="#5D4037" opacity="0.6"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#000000" opacity="0.92"
        stroke="#FFCA28" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#FFCA28" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">장애물에 부딪혔어요</text>
  <text x="180" y="132" text-anchor="middle"
        fill="#FFE082" font-family="Arial, Helvetica, sans-serif"
        font-size="14">↑/스페이스 = 점프  ↓ = 슬라이드</text>
  <text x="180" y="156" text-anchor="middle"
        fill="#FFCC80" font-family="Arial, Helvetica, sans-serif"
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
    def key_pressed(key_name):
        menu_id = gen()
        bs[menu_id] = mk("sensing_keyoptions",
            fields={"KEY_OPTION": [key_name, None]}, shadow=True)
        kp = gen()
        bs[kp] = mk("sensing_keypressed",
            inputs={"KEY_OPTION":[1, menu_id]})
        bs[menu_id]["parent"] = kp
        return kp
    return vrep, op, cmp_op, bool_op, key_pressed

# ============================================================
#  IDs
# ============================================================
V_SCORE     = "varScore01"
V_BEST      = "varBest02"
V_STATE     = "varState03"
V_VY        = "varVY04"
V_SCROLL    = "varScroll05"
V_SPAWN     = "varSpawn06"
V_PREV_JUMP = "varPrevJump07"
V_KIND      = "varKind08"

BR_START        = "brStart01"
BR_SPAWN_CACTUS = "brSpawnCactus02"
BR_SPAWN_BAT    = "brSpawnBat03"

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, _ = make_helpers(bs)

    # === when flag clicked: init vars + broadcast 게임시작 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    st_snd_stop = gen(); bs[st_snd_stop] = mk("sound_stopallsounds")
    st_snd_clr = gen(); bs[st_snd_clr] = mk("sound_cleareffects")
    st_looks_clr = gen(); bs[st_looks_clr] = mk("looks_cleargraphiceffects")
    st_vol = gen(); bs[st_vol] = mk("sound_setvolumeto", inputs={"VOLUME": num(100)})
    s_score = gen(); bs[s_score] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점수", V_SCORE]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    s_vy = gen(); bs[s_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    s_scroll = gen(); bs[s_scroll] = mk("data_setvariableto",
        inputs={"VALUE": num(5)}, fields={"VARIABLE": ["스크롤속도", V_SCROLL]})
    s_spawn = gen(); bs[s_spawn] = mk("data_setvariableto",
        inputs={"VALUE": num(1.4)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    s_prev = gen(); bs[s_prev] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점프이전키", V_PREV_JUMP]})
    s_kind = gen(); bs[s_kind] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["장애물종류", V_KIND]})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    # brief wait so all "when flag clicked" handlers in other sprites can run first
    wt_init = gen(); bs[wt_init] = mk("control_wait", inputs={"DURATION": num(0)})

    chain([(h,bs[h]),(st_snd_stop,bs[st_snd_stop]),(st_snd_clr,bs[st_snd_clr]),
           (st_looks_clr,bs[st_looks_clr]),(st_vol,bs[st_vol]),
           (s_score,bs[s_score]),(s_state,bs[s_state]),(s_vy,bs[s_vy]),
           (s_scroll,bs[s_scroll]),(s_spawn,bs[s_spawn]),(s_prev,bs[s_prev]),
           (s_kind,bs[s_kind]),(wt_init,bs[wt_init]),(bc_start,bs[bc_start])])

    # === when receive 게임시작 — forever 1: 장애물 스폰 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_a = vrep("게임상태", V_STATE)
    cond_over_a = cmp_op("operator_equals", state_v_a, 0)

    # 장애물종류 = pick random 0 to 1
    rnd_kind = gen(); bs[rnd_kind] = mk("operator_random",
        inputs={"FROM": num(0), "TO": num(1)})
    set_kind = gen(); bs[set_kind] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_kind)}, fields={"VARIABLE": ["장애물종류", V_KIND]})
    bs[rnd_kind]["parent"] = set_kind

    # if 장애물종류 = 0 → broadcast 선인장스폰 else → broadcast 박쥐스폰
    kind_v = vrep("장애물종류", V_KIND)
    cond_kind0 = cmp_op("operator_equals", kind_v, 0)

    bm_cact = gen(); bs[bm_cact] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["선인장스폰", BR_SPAWN_CACTUS]}, shadow=True)
    bc_cact = gen(); bs[bc_cact] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_cact]})
    bs[bm_cact]["parent"] = bc_cact

    bm_bat = gen(); bs[bm_bat] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["박쥐스폰", BR_SPAWN_BAT]}, shadow=True)
    bc_bat_call = gen(); bs[bc_bat_call] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_bat]})
    bs[bm_bat]["parent"] = bc_bat_call

    if_else_spawn = gen(); bs[if_else_spawn] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_kind0],
                "SUBSTACK":[2,bc_cact],
                "SUBSTACK2":[2,bc_bat_call]})
    bs[cond_kind0]["parent"] = if_else_spawn
    bs[bc_cact]["parent"] = if_else_spawn
    bs[bc_bat_call]["parent"] = if_else_spawn

    # wait 스폰주기
    spawn_v = vrep("스폰주기", V_SPAWN)
    wt_sp = gen(); bs[wt_sp] = mk("control_wait",
        inputs={"DURATION": slot(spawn_v)})
    bs[spawn_v]["parent"] = wt_sp

    chain([(set_kind,bs[set_kind]),(if_else_spawn,bs[if_else_spawn]),(wt_sp,bs[wt_sp])])

    rep_until_a = gen(); bs[rep_until_a] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_a], "SUBSTACK":[2,set_kind]})
    bs[cond_over_a]["parent"] = rep_until_a
    bs[set_kind]["parent"] = rep_until_a

    # initial grace period: wait 1.5 before first obstacle
    wt_grace = gen(); bs[wt_grace] = mk("control_wait", inputs={"DURATION": num(1.5)})

    chain([(h2,bs[h2]),(wt_grace,bs[wt_grace]),(rep_until_a,bs[rep_until_a])])

    # === when receive 게임시작 — forever 2: 점수 누적 + 가속 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    state_v_b = vrep("게임상태", V_STATE)
    cond_over_b = cmp_op("operator_equals", state_v_b, 0)

    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})

    # if (점수 mod 50) = 0 → 스크롤속도 += 1, if 스폰주기 > 0.6 → 스폰주기 -= 0.1
    score_v_a = vrep("점수", V_SCORE)
    mod_op = op("operator_mod", score_v_a, 50)
    cond_mod0 = cmp_op("operator_equals", mod_op, 0)
    bs[mod_op]["parent"] = cond_mod0

    inc_scroll = gen(); bs[inc_scroll] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["스크롤속도", V_SCROLL]})

    spawn_v_b = vrep("스폰주기", V_SPAWN)
    cond_sp_gt = cmp_op("operator_gt", spawn_v_b, 0.6)
    dec_spawn = gen(); bs[dec_spawn] = mk("data_changevariableby",
        inputs={"VALUE": num(-0.1)}, fields={"VARIABLE": ["스폰주기", V_SPAWN]})
    if_sp = gen(); bs[if_sp] = mk("control_if",
        inputs={"CONDITION":[2,cond_sp_gt], "SUBSTACK":[2,dec_spawn]})
    bs[cond_sp_gt]["parent"] = if_sp
    bs[dec_spawn]["parent"] = if_sp

    chain([(inc_scroll,bs[inc_scroll]),(if_sp,bs[if_sp])])

    if_accel = gen(); bs[if_accel] = mk("control_if",
        inputs={"CONDITION":[2,cond_mod0], "SUBSTACK":[2,inc_scroll]})
    bs[cond_mod0]["parent"] = if_accel
    bs[inc_scroll]["parent"] = if_accel

    wt_score = gen(); bs[wt_score] = mk("control_wait", inputs={"DURATION": num(0.1)})

    chain([(inc_score,bs[inc_score]),(if_accel,bs[if_accel]),(wt_score,bs[wt_score])])

    rep_until_b = gen(); bs[rep_until_b] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_b], "SUBSTACK":[2,inc_score]})
    bs[cond_over_b]["parent"] = rep_until_b
    bs[inc_score]["parent"] = rep_until_b

    chain([(h3,bs[h3]),(rep_until_b,bs[rep_until_b])])

    return bs

# ============================================================
#  RUNNER blocks
# ============================================================
def build_runner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, key_pressed = make_helpers(bs)

    # === when flag clicked: init pos + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    snd_clr = gen(); bs[snd_clr] = mk("sound_cleareffects")
    snd_stop = gen(); bs[snd_stop] = mk("sound_stopallsounds")
    looks_clr = gen(); bs[looks_clr] = mk("looks_cleargraphiceffects")
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(-150), "Y": num(-130)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    # switch to frame 1 on flag click
    cm_init = gen(); bs[cm_init] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen()]})
    cm_init_menu = bs[cm_init]["inputs"]["COSTUME"][1]
    bs[cm_init_menu] = mk("looks_costume",
        fields={"COSTUME": ["runner", None]}, shadow=True, parent=cm_init)
    sh = gen(); bs[sh] = mk("looks_show")
    vol = gen(); bs[vol] = mk("sound_setvolumeto", inputs={"VOLUME": num(100)})
    chain([(h,bs[h]),(snd_clr,bs[snd_clr]),(snd_stop,bs[snd_stop]),(looks_clr,bs[looks_clr]),
           (vol,bs[vol]),
           (g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),(cm_init,bs[cm_init]),(sh,bs[sh])])

    # === when receive 게임시작: input + physics + collision loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    sh2 = gen(); bs[sh2] = mk("looks_show")
    looks_clr2 = gen(); bs[looks_clr2] = mk("looks_cleargraphiceffects")
    vol2 = gen(); bs[vol2] = mk("sound_setvolumeto", inputs={"VOLUME": num(100)})
    reset_vy = gen(); bs[reset_vy] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    reset_prev = gen(); bs[reset_prev] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점프이전키", V_PREV_JUMP]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": num(-150), "Y": num(-130)})
    sz0 = gen(); bs[sz0] = mk("looks_setsizeto", inputs={"SIZE": num(80)})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # --- jump edge detection ---
    # 현재점프키 = (key up arrow pressed) OR (key space pressed)
    k_up_a = key_pressed("up arrow")
    k_sp_a = key_pressed("space")
    cond_jump_input_a = bool_op("operator_or", k_up_a, k_sp_a)

    # prev key = 0?
    prev_v1 = vrep("점프이전키", V_PREV_JUMP)
    cond_prev0 = cmp_op("operator_equals", prev_v1, 0)

    # y < -129?  (on the floor)
    yp_floor_chk = gen(); bs[yp_floor_chk] = mk("motion_yposition")
    cond_on_floor = cmp_op("operator_lt", yp_floor_chk, -129)
    bs[yp_floor_chk]["parent"] = cond_on_floor

    # (input AND prev=0)
    cond_edge_inner = bool_op("operator_and", cond_jump_input_a, cond_prev0)
    # ((input AND prev=0) AND on_floor)
    cond_edge_jump = bool_op("operator_and", cond_edge_inner, cond_on_floor)

    set_vy_jump = gen(); bs[set_vy_jump] = mk("data_setvariableto",
        inputs={"VALUE": num(9)}, fields={"VARIABLE": ["VY", V_VY]})

    if_jump = gen(); bs[if_jump] = mk("control_if",
        inputs={"CONDITION":[2,cond_edge_jump], "SUBSTACK":[2,set_vy_jump]})
    bs[cond_edge_jump]["parent"] = if_jump
    bs[set_vy_jump]["parent"] = if_jump

    # --- update 점프이전키 ---
    k_up_b = key_pressed("up arrow")
    k_sp_b = key_pressed("space")
    cond_jump_input_b = bool_op("operator_or", k_up_b, k_sp_b)

    set_prev_1 = gen(); bs[set_prev_1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점프이전키", V_PREV_JUMP]})
    set_prev_0 = gen(); bs[set_prev_0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점프이전키", V_PREV_JUMP]})

    if_else_prev = gen(); bs[if_else_prev] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_jump_input_b],
                "SUBSTACK":[2,set_prev_1],
                "SUBSTACK2":[2,set_prev_0]})
    bs[cond_jump_input_b]["parent"] = if_else_prev
    bs[set_prev_1]["parent"] = if_else_prev
    bs[set_prev_0]["parent"] = if_else_prev

    # --- gravity: VY -= 0.8 ---
    grav = gen(); bs[grav] = mk("data_changevariableby",
        inputs={"VALUE": num(-0.8)}, fields={"VARIABLE": ["VY", V_VY]})

    # --- change y by VY ---
    vy_v_d = vrep("VY", V_VY)
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(vy_v_d)})
    bs[vy_v_d]["parent"] = chy

    # --- floor clamp: if y < -130 → goto -150,-130 + VY=0 ---
    yp_f = gen(); bs[yp_f] = mk("motion_yposition")
    cond_floor = cmp_op("operator_lt", yp_f, -130)
    bs[yp_f]["parent"] = cond_floor
    g_floor = gen(); bs[g_floor] = mk("motion_gotoxy",
        inputs={"X": num(-150), "Y": num(-130)})
    set_vy_zero = gen(); bs[set_vy_zero] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["VY", V_VY]})
    chain([(g_floor,bs[g_floor]),(set_vy_zero,bs[set_vy_zero])])
    if_floor = gen(); bs[if_floor] = mk("control_if",
        inputs={"CONDITION":[2,cond_floor], "SUBSTACK":[2,g_floor]})
    bs[cond_floor]["parent"] = if_floor
    bs[g_floor]["parent"] = if_floor

    # --- running animation: if on floor (y < -129) → next costume, else → costume "runner" ---
    # y = -130 on floor; jumping raises y above -130.
    # operator_lt(y_position, -129) is TRUE only when y <= -130 (on ground).
    yp_anim = gen(); bs[yp_anim] = mk("motion_yposition")
    cond_on_floor_anim = cmp_op("operator_lt", yp_anim, -129)
    bs[yp_anim]["parent"] = cond_on_floor_anim

    next_cos = gen(); bs[next_cos] = mk("looks_nextcostume")

    cm_run = gen(); bs[cm_run] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen()]})
    run_menu_id = bs[cm_run]["inputs"]["COSTUME"][1]
    bs[run_menu_id] = mk("looks_costume",
        fields={"COSTUME": ["runner", None]}, shadow=True, parent=cm_run)

    if_else_anim = gen(); bs[if_else_anim] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_on_floor_anim],
                "SUBSTACK":  [2, next_cos],
                "SUBSTACK2": [2, cm_run]})
    bs[cond_on_floor_anim]["parent"] = if_else_anim
    bs[next_cos]["parent"] = if_else_anim
    bs[cm_run]["parent"] = if_else_anim

    # --- slide size: if (key down arrow pressed) → size 40 else size 80 ---
    k_down = key_pressed("down arrow")
    set_size_small = gen(); bs[set_size_small] = mk("looks_setsizeto",
        inputs={"SIZE": num(40)})
    set_size_norm = gen(); bs[set_size_norm] = mk("looks_setsizeto",
        inputs={"SIZE": num(80)})
    if_else_slide = gen(); bs[if_else_slide] = mk("control_if_else",
        inputs={"CONDITION":[2,k_down],
                "SUBSTACK":[2,set_size_small],
                "SUBSTACK2":[2,set_size_norm]})
    bs[k_down]["parent"] = if_else_slide
    bs[set_size_small]["parent"] = if_else_slide
    bs[set_size_norm]["parent"] = if_else_slide

    # --- touching 선인장 → state=0 ---
    tm_cact = gen(); bs[tm_cact] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["선인장", None]}, shadow=True)
    tc_cact = gen(); bs[tc_cact] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_cact]})
    bs[tm_cact]["parent"] = tc_cact
    set_st_cact = gen(); bs[set_st_cact] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_cact = gen(); bs[if_cact] = mk("control_if",
        inputs={"CONDITION":[2,tc_cact], "SUBSTACK":[2,set_st_cact]})
    bs[tc_cact]["parent"] = if_cact
    bs[set_st_cact]["parent"] = if_cact

    # --- touching 박쥐 → state=0 ---
    tm_bat = gen(); bs[tm_bat] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["박쥐", None]}, shadow=True)
    tc_bat = gen(); bs[tc_bat] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_bat]})
    bs[tm_bat]["parent"] = tc_bat
    set_st_bat = gen(); bs[set_st_bat] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_bat = gen(); bs[if_bat] = mk("control_if",
        inputs={"CONDITION":[2,tc_bat], "SUBSTACK":[2,set_st_bat]})
    bs[tc_bat]["parent"] = if_bat
    bs[set_st_bat]["parent"] = if_bat

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

    chain([(if_jump,bs[if_jump]),(if_else_prev,bs[if_else_prev]),
           (grav,bs[grav]),(chy,bs[chy]),(if_floor,bs[if_floor]),
           (if_else_anim,bs[if_else_anim]),
           (if_else_slide,bs[if_else_slide]),
           (if_cact,bs[if_cact]),(if_bat,bs[if_bat]),
           (if_best,bs[if_best]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_jump]})
    bs[cond_over]["parent"] = rep_until
    bs[if_jump]["parent"] = rep_until

    # reset costume to frame 1 on each game start
    cm_reset = gen(); bs[cm_reset] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen()]})
    cm_reset_menu = bs[cm_reset]["inputs"]["COSTUME"][1]
    bs[cm_reset_menu] = mk("looks_costume",
        fields={"COSTUME": ["runner", None]}, shadow=True, parent=cm_reset)

    hi2 = gen(); bs[hi2] = mk("looks_hide")

    chain([(h2,bs[h2]),(sh2,bs[sh2]),(looks_clr2,bs[looks_clr2]),(vol2,bs[vol2]),
           (reset_vy,bs[reset_vy]),(reset_prev,bs[reset_prev]),
           (g0,bs[g0]),(sz0,bs[sz0]),(cm_reset,bs[cm_reset]),(rep_until,bs[rep_until]),
           (hi2,bs[hi2])])

    # === when flag clicked: play pop on game over ===
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=400, y=20)
    state_v_d = vrep("게임상태", V_STATE)
    cond_zero_d = cmp_op("operator_equals", state_v_d, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_zero_d]})
    bs[cond_zero_d]["parent"] = wait_over

    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd

    chain([(h3,bs[h3]),(wait_over,bs[wait_over]),(pitch,bs[pitch]),(snd,bs[snd])])

    return bs

# ============================================================
#  CACTUS blocks
# ============================================================
def build_cactus_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    clr_fx = gen(); bs[clr_fx] = mk("looks_cleargraphiceffects")
    clr_snd = gen(); bs[clr_snd] = mk("sound_cleareffects")
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": num(300), "Y": num(-125)})
    pdir_init = gen(); bs[pdir_init] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(90)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz]),(clr_fx,bs[clr_fx]),(clr_snd,bs[clr_snd]),
           (g_init,bs[g_init]),(pdir_init,bs[pdir_init])])

    # === when receive 선인장스폰: goto + size + costume + clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["선인장스폰", BR_SPAWN_CACTUS]})

    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": num(-125)})
    sz_sp = gen(); bs[sz_sp] = mk("looks_setsizeto", inputs={"SIZE": num(80)})

    cm = gen(); bs[cm] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    menu_id = bs[cm]["inputs"]["COSTUME"][1]
    bs[menu_id] = mk("looks_costume",
        fields={"COSTUME":["cactus", None]}, shadow=True, parent=cm)

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(sz_sp,bs[sz_sp]),(cm,bs[cm]),(cclone,bs[cclone])])

    # === when I start as clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    # ensure position, size, direction, effects at clone start
    cl_g = gen(); bs[cl_g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": num(-125)})
    cl_sz = gen(); bs[cl_sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    cl_dir = gen(); bs[cl_dir] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(90)})
    cl_clr = gen(); bs[cl_clr] = mk("looks_cleargraphiceffects")
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
    chain([(ch,bs[ch]),(cl_g,bs[cl_g]),(cl_sz,bs[cl_sz]),(cl_dir,bs[cl_dir]),
           (cl_clr,bs[cl_clr]),(show,bs[show]),(rep_until,bs[rep_until]),(del_end,bs[del_end])])

    return bs

# ============================================================
#  BAT blocks
# ============================================================
def build_bat_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    clr_fx = gen(); bs[clr_fx] = mk("looks_cleargraphiceffects")
    clr_snd = gen(); bs[clr_snd] = mk("sound_cleareffects")
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": num(300), "Y": num(-90)})
    pdir_init = gen(); bs[pdir_init] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(90)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz]),(clr_fx,bs[clr_fx]),(clr_snd,bs[clr_snd]),
           (g_init,bs[g_init]),(pdir_init,bs[pdir_init])])

    # === when receive 박쥐스폰: goto + size + costume + clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["박쥐스폰", BR_SPAWN_BAT]})

    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": num(-90)})
    sz_sp = gen(); bs[sz_sp] = mk("looks_setsizeto", inputs={"SIZE": num(80)})

    cm = gen(); bs[cm] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, gen()]})
    menu_id = bs[cm]["inputs"]["COSTUME"][1]
    bs[menu_id] = mk("looks_costume",
        fields={"COSTUME":["bat", None]}, shadow=True, parent=cm)

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(h2,bs[h2]),(g,bs[g]),(sz_sp,bs[sz_sp]),(cm,bs[cm]),(cclone,bs[cclone])])

    # === when I start as clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=200)
    # ensure position, size, direction at clone start
    cl_g = gen(); bs[cl_g] = mk("motion_gotoxy",
        inputs={"X": num(260), "Y": num(-90)})
    cl_sz = gen(); bs[cl_sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    cl_dir = gen(); bs[cl_dir] = mk("motion_pointindirection",
        inputs={"DIRECTION": num(90)})
    cl_clr = gen(); bs[cl_clr] = mk("looks_cleargraphiceffects")
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
    chain([(ch,bs[ch]),(cl_g,bs[cl_g]),(cl_sz,bs[cl_sz]),(cl_dir,bs[cl_dir]),
           (cl_clr,bs[cl_clr]),(show,bs[show]),(rep_until,bs[rep_until]),(del_end,bs[del_end])])

    return bs

# ============================================================
#  GROUND blocks (static)
# ============================================================
def build_ground_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-150)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    clr = gen(); bs[clr] = mk("looks_cleargraphiceffects")
    snd_clr = gen(); bs[snd_clr] = mk("sound_cleareffects")
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(pdir,bs[pdir]),
           (clr,bs[clr]),(snd_clr,bs[snd_clr]),(sh,bs[sh])])
    return bs

# ============================================================
#  GAME OVER banner blocks
# ============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    clr_go = gen(); bs[clr_go] = mk("looks_cleargraphiceffects")
    snd_clr_go = gen(); bs[snd_clr_go] = mk("sound_cleareffects")
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

    # ensure at center and front when showing
    g2 = gen(); bs[g2] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front2 = gen(); bs[front2] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")

    chain([(h,bs[h]),(hi,bs[hi]),(clr_go,bs[clr_go]),(snd_clr_go,bs[snd_clr_go]),
           (g,bs[g]),(sz,bs[sz]),(front,bs[front]),
           (wait_start,bs[wait_start]),(wait_over,bs[wait_over]),
           (g2,bs[g2]),(front2,bs[front2]),(show,bs[show])])
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

    run_md5 = md5_bytes(RUNNER_SVG.encode("utf-8"))
    with open(f"{WORK}/{run_md5}.svg", "w", encoding="utf-8") as f:
        f.write(RUNNER_SVG)

    run2_md5 = md5_bytes(RUNNER_RUN_SVG.encode("utf-8"))
    with open(f"{WORK}/{run2_md5}.svg", "w", encoding="utf-8") as f:
        f.write(RUNNER_RUN_SVG)

    cact_md5 = md5_bytes(CACTUS_SVG.encode("utf-8"))
    with open(f"{WORK}/{cact_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CACTUS_SVG)

    bat_md5 = md5_bytes(BAT_SVG.encode("utf-8"))
    with open(f"{WORK}/{bat_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BAT_SVG)

    gnd_md5 = md5_bytes(GROUND_SVG.encode("utf-8"))
    with open(f"{WORK}/{gnd_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GROUND_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    runner_blocks   = build_runner_blocks()
    cactus_blocks   = build_cactus_blocks()
    bat_blocks      = build_bat_blocks()
    ground_blocks   = build_ground_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:     ["점수", 0],
            V_BEST:      ["최고기록", 0],
            V_STATE:     ["게임상태", 1],
            V_VY:        ["VY", 0],
            V_SCROLL:    ["스크롤속도", 5],
            V_SPAWN:     ["스폰주기", 1.4],
            V_PREV_JUMP: ["점프이전키", 0],
            V_KIND:      ["장애물종류", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:        "게임시작",
            BR_SPAWN_CACTUS: "선인장스폰",
            BR_SPAWN_BAT:    "박쥐스폰",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "사막", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    ground = {
        "isStage": False, "name": "바닥",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ground_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "ground", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": gnd_md5, "md5ext": f"{gnd_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 15
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 0, "y": -150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    cactus = {
        "isStage": False, "name": "선인장",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": cactus_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "cactus", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": cact_md5, "md5ext": f"{cact_md5}.svg",
            "rotationCenterX": 25, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    bat = {
        "isStage": False, "name": "박쥐",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bat_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bat", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bat_md5, "md5ext": f"{bat_md5}.svg",
            "rotationCenterX": 35, "rotationCenterY": 20
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    runner = {
        "isStage": False, "name": "러너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": runner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "runner", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": run_md5, "md5ext": f"{run_md5}.svg",
                "rotationCenterX": 30, "rotationCenterY": 40
            },
            {
                "name": "runner-run", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": run2_md5, "md5ext": f"{run2_md5}.svg",
                "rotationCenterX": 30, "rotationCenterY": 40
            }
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": True,
        "x": -150, "y": -130, "size": 80, "direction": 90,
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
        {"id": V_SCROLL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "스크롤속도"}, "spriteName": None,
         "value": 5, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 50, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, ground, cactus, bat, runner, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "endless-runner-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    total = sum(len(b) for b in [stage_blocks, runner_blocks, cactus_blocks,
                                 bat_blocks, ground_blocks, gameover_blocks])
    print(f"[endless-runner] built {OUTPUT}")
    print(f"  stage: {len(stage_blocks)}  runner: {len(runner_blocks)}  "
          f"cactus: {len(cactus_blocks)}  bat: {len(bat_blocks)}  "
          f"ground: {len(ground_blocks)}  gameover: {len(gameover_blocks)}  "
          f"total: {total}")

if __name__ == "__main__":
    main()
