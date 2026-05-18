#!/usr/bin/env python3
"""Balloon Shooter — 60-second casual click-to-pop balloon arcade.

Floating balloons rise from the bottom; mouse-click pops them.
Small balloons = 30 pts, medium = 20, big = 10.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "풍선_슈터.sb3")

# =====================================================================
#  BACKGROUND  (lavender → pink sky + sun + clouds)
# =====================================================================
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#B39DDB"/>
      <stop offset="55%"  stop-color="#F8BBD0"/>
      <stop offset="100%" stop-color="#FFCCBC"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <circle cx="400" cy="70" r="38" fill="#FFEE58" opacity="0.95"/>
  <circle cx="400" cy="70" r="55" fill="#FFEE58" opacity="0.25"/>
  <g fill="#FFFFFF" opacity="0.85">
    <ellipse cx="90"  cy="80"  rx="42" ry="14"/>
    <ellipse cx="70"  cy="92"  rx="28" ry="11"/>
    <ellipse cx="110" cy="92"  rx="30" ry="11"/>
    <ellipse cx="260" cy="130" rx="50" ry="16"/>
    <ellipse cx="235" cy="142" rx="28" ry="11"/>
    <ellipse cx="285" cy="142" rx="32" ry="11"/>
    <ellipse cx="170" cy="200" rx="34" ry="11"/>
    <ellipse cx="350" cy="220" rx="38" ry="12"/>
  </g>
  <g stroke="#FFFFFF" stroke-width="1" opacity="0.4" fill="none">
    <path d="M 0 320 Q 120 310 240 320 T 480 320"/>
    <path d="M 0 340 Q 120 332 240 340 T 480 340"/>
  </g>
</svg>"""

# =====================================================================
#  CROSSHAIR  (re-using duck-hunt look)
# =====================================================================
CROSSHAIR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="14" fill="none" stroke="#D50000" stroke-width="2"/>
  <line x1="20" y1="2"  x2="20" y2="14" stroke="#D50000" stroke-width="2.5"/>
  <line x1="20" y1="26" x2="20" y2="38" stroke="#D50000" stroke-width="2.5"/>
  <line x1="2"  y1="20" x2="14" y2="20" stroke="#D50000" stroke-width="2.5"/>
  <line x1="26" y1="20" x2="38" y2="20" stroke="#D50000" stroke-width="2.5"/>
  <circle cx="20" cy="20" r="1.8" fill="#D50000"/>
</svg>"""

# =====================================================================
#  FLASH
# =====================================================================
FLASH_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <defs>
    <radialGradient id="flash" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%"   stop-color="#FFFFFF" stop-opacity="1"/>
      <stop offset="40%"  stop-color="#FFF59D" stop-opacity="0.9"/>
      <stop offset="80%"  stop-color="#FFB300" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#FF6F00" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <polygon points="30,2 35,22 55,25 38,33 48,52 30,40 12,52 22,33 5,25 25,22"
           fill="url(#flash)" stroke="#FFC107" stroke-width="1"/>
  <circle cx="30" cy="30" r="6" fill="#FFFFFF"/>
</svg>"""

# =====================================================================
#  BALLOON SVGs  (5 colors)
# =====================================================================
def balloon_svg(body, highlight, knot):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="70" height="100" viewBox="0 0 70 100">
  <ellipse cx="35" cy="40" rx="28" ry="34" fill="{body}" stroke="#3E2723" stroke-width="1.2"/>
  <ellipse cx="25" cy="28" rx="7" ry="11" fill="{highlight}" opacity="0.85"/>
  <polygon points="32,74 38,74 35,82" fill="{knot}"/>
  <path d="M 35 82 Q 38 90 33 96 Q 30 99 35 100" stroke="#5D4037" stroke-width="1.2" fill="none"/>
</svg>"""

BALLOON_RED    = balloon_svg("#E53935", "#FFCDD2", "#B71C1C")
BALLOON_BLUE   = balloon_svg("#1E88E5", "#BBDEFB", "#0D47A1")
BALLOON_YELLOW = balloon_svg("#FDD835", "#FFF9C4", "#F57F17")
BALLOON_GREEN  = balloon_svg("#43A047", "#C8E6C9", "#1B5E20")
BALLOON_PURPLE = balloon_svg("#8E24AA", "#E1BEE7", "#4A148C")

# Pop effect (burst star)
BALLOON_POP = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <polygon points="50,5 58,38 92,38 64,58 76,92 50,72 24,92 36,58 8,38 42,38"
           fill="#FFEB3B" stroke="#F57F17" stroke-width="2.5"/>
  <polygon points="50,18 55,40 78,42 60,55 68,78 50,65 32,78 40,55 22,42 45,40"
           fill="#FFFFFF" opacity="0.85"/>
  <text x="50" y="60" text-anchor="middle"
        fill="#D50000" font-family="Arial" font-size="20" font-weight="bold">POP!</text>
</svg>"""

# =====================================================================
#  TIME UP banner
# =====================================================================
TIMEUP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="380" height="180" viewBox="0 0 380 180">
  <rect x="5" y="5" width="370" height="170" rx="16"
        fill="#000000" opacity="0.88"
        stroke="#FFEB3B" stroke-width="4"/>
  <text x="190" y="68" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">TIME UP!</text>
  <text x="190" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="22">최종 점수는 왼쪽 위에서 확인하세요</text>
  <text x="190" y="148" text-anchor="middle"
        fill="#FFB74D" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭으로 재도전</text>
</svg>"""

# =====================================================================
#  helpers
# =====================================================================
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n):       return [1, [4, str(n)]]
def text_lit(s):  return [1, [10, str(s)]]
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

# Variable / broadcast IDs (Stage-global)
V_SCORE  = "varScore01"
V_TIME   = "varTime02"
V_STATE  = "varState03"
V_FX     = "varFX04"
V_FY     = "varFY05"
V_BX     = "varBX06"
V_BSIZE  = "varBSize07"
V_BCOLOR = "varBColor08"

# Balloon-local variables
LV_MYSIZE  = "lvMySize01"
LV_MYSCORE = "lvMyScore02"
LV_PHASE   = "lvPhase03"

BR_START = "brStart01"
BR_SPAWN = "brSpawn02"
BR_END   = "brEnd03"

def make_helpers(bs):
    def vrep(name, vid):
        bid = gen()
        bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid
    def op(opcode, a, b_, key1="NUM1", key2="NUM2"):
        bid = gen(); ins = {}
        for key, val in [(key1, a), (key2, b_)]:
            if isinstance(val, str): ins[key] = slot(val)
            else: ins[key] = num(val)
        bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): bs[v]["parent"] = bid
        return bid
    def cmp_op(opcode, a, b_):
        bid = gen(); ins = {}
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

# =====================================================================
#  STAGE
# =====================================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ----- A) flag clicked: init + broadcast 게임시작 -----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)

    inits = []
    for var_pair, val in [
        (("점수",   V_SCORE), 0),
        (("시간",   V_TIME),  60),
        (("게임상태", V_STATE), 1),
        (("풍선스폰X", V_BX),  0),
        (("풍선크기", V_BSIZE), 2),
        (("풍선색", V_BCOLOR), 1),
    ]:
        sid = gen(); bs[sid] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": list(var_pair)})
        inits.append((sid, bs[sid]))

    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(1)})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h, bs[h])] + inits + [(w1, bs[w1]), (bc_start, bs[bc_start])])

    # ----- B) on 게임시작: spawn loop (forever) -----
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # condition: 게임상태 = 1
    state_v = vrep("게임상태", V_STATE)
    cond_alive = cmp_op("operator_equals", state_v, 1)

    # body when alive:
    rand_x = op("operator_random", -200, 200, key1="FROM", key2="TO")
    set_bx = gen(); bs[set_bx] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_x)}, fields={"VARIABLE": ["풍선스폰X", V_BX]})
    bs[rand_x]["parent"] = set_bx

    rand_c = op("operator_random", 1, 5, key1="FROM", key2="TO")
    set_bc = gen(); bs[set_bc] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_c)}, fields={"VARIABLE": ["풍선색", V_BCOLOR]})
    bs[rand_c]["parent"] = set_bc

    rand_s = op("operator_random", 1, 3, key1="FROM", key2="TO")
    set_bs = gen(); bs[set_bs] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_s)}, fields={"VARIABLE": ["풍선크기", V_BSIZE]})
    bs[rand_s]["parent"] = set_bs

    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["풍선스폰", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    rand_wait = op("operator_random", 0.4, 0.8, key1="FROM", key2="TO")
    wt_spawn = gen(); bs[wt_spawn] = mk("control_wait",
        inputs={"DURATION": slot(rand_wait)})
    bs[rand_wait]["parent"] = wt_spawn

    chain([(set_bx, bs[set_bx]), (set_bc, bs[set_bc]), (set_bs, bs[set_bs]),
           (bc_sp, bs[bc_sp]), (wt_spawn, bs[wt_spawn])])

    if_alive = gen(); bs[if_alive] = mk("control_if",
        inputs={"CONDITION": [2, cond_alive], "SUBSTACK": [2, set_bx]})
    bs[cond_alive]["parent"] = if_alive
    bs[set_bx]["parent"] = if_alive

    # idle wait when dead so forever doesn't busy-loop
    w_idle = gen(); bs[w_idle] = mk("control_wait", inputs={"DURATION": num(0.1)})
    chain([(if_alive, bs[if_alive]), (w_idle, bs[w_idle])])

    forever_spawn = gen(); bs[forever_spawn] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_alive]})
    bs[if_alive]["parent"] = forever_spawn

    chain([(h2, bs[h2]), (forever_spawn, bs[forever_spawn])])

    # ----- C) on 게임시작: 60s timer -----
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=640,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    wt_tick = gen(); bs[wt_tick] = mk("control_wait", inputs={"DURATION": num(1)})
    dec_time = gen(); bs[dec_time] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["시간", V_TIME]})
    chain([(wt_tick, bs[wt_tick]), (dec_time, bs[dec_time])])

    rep60 = gen(); bs[rep60] = mk("control_repeat",
        inputs={"TIMES": num(60), "SUBSTACK": [2, wt_tick]})
    bs[wt_tick]["parent"] = rep60

    # after countdown: 게임상태 = 0, broadcast 게임종료
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bm_end = gen(); bs[bm_end] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임종료", BR_END]}, shadow=True)
    bc_end = gen(); bs[bc_end] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_end]})
    bs[bm_end]["parent"] = bc_end

    chain([(h3, bs[h3]), (rep60, bs[rep60]),
           (set_state0, bs[set_state0]), (bc_end, bs[bc_end])])

    return bs

# =====================================================================
#  CROSSHAIR
# =====================================================================
def build_crosshair_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # flag: setup + follow mouse forever
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")

    mx = gen(); bs[mx] = mk("sensing_mousex")
    my = gen(); bs[my] = mk("sensing_mousey")
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(mx), "Y": slot(my)})
    bs[mx]["parent"] = g; bs[my]["parent"] = g

    forever = gen(); bs[forever] = mk("control_forever",
        inputs={"SUBSTACK": [2, g]})
    bs[g]["parent"] = forever
    chain([(h, bs[h]), (sz, bs[sz]), (front, bs[front]),
           (show, bs[show]), (forever, bs[forever])])

    # click → fire
    h2 = gen(); bs[h2] = mk("event_whenthisspriteclicked", top=True, x=300, y=20)

    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)

    mx2 = gen(); bs[mx2] = mk("sensing_mousex")
    set_fx = gen(); bs[set_fx] = mk("data_setvariableto",
        inputs={"VALUE": slot(mx2)}, fields={"VARIABLE": ["섬광X", V_FX]})
    bs[mx2]["parent"] = set_fx

    my2 = gen(); bs[my2] = mk("sensing_mousey")
    set_fy = gen(); bs[set_fy] = mk("data_setvariableto",
        inputs={"VALUE": slot(my2)}, fields={"VARIABLE": ["섬광Y", V_FY]})
    bs[my2]["parent"] = set_fy

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["섬광", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone

    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(200)}, fields={"EFFECT": ["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU": [1, snm]})
    bs[snm]["parent"] = snd

    chain([(set_fx, bs[set_fx]), (set_fy, bs[set_fy]),
           (cclone, bs[cclone]), (pitch, bs[pitch]), (snd, bs[snd])])

    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, cond_play], "SUBSTACK": [2, set_fx]})
    bs[cond_play]["parent"] = if_fire
    bs[set_fx]["parent"] = if_fire

    chain([(h2, bs[h2]), (if_fire, bs[if_fire])])
    return bs

# =====================================================================
#  FLASH
# =====================================================================
def build_flash_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(65)})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)
    fx_v = vrep("섬광X", V_FX); fy_v = vrep("섬광Y", V_FY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(fx_v), "Y": slot(fy_v)})
    bs[fx_v]["parent"] = g; bs[fy_v]["parent"] = g

    sz2 = gen(); bs[sz2] = mk("looks_setsizeto", inputs={"SIZE": num(65)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.12)})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (sz2, bs[sz2]), (front, bs[front]),
           (show, bs[show]), (wt, bs[wt]), (hi2, bs[hi2]), (delc, bs[delc])])
    return bs

# =====================================================================
#  BALLOON
# =====================================================================
def build_balloon_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ---- flag: hide the master sprite ----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-220)})
    chain([(h, bs[h]), (hi, bs[hi]), (g0, bs[g0])])

    # ---- on 풍선스폰: create clone of myself ----
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["풍선스폰", BR_SPAWN]})

    cmenu_self = gen(); bs[cmenu_self] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone_self = gen(); bs[cclone_self] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu_self]})
    bs[cmenu_self]["parent"] = cclone_self

    chain([(h2, bs[h2]), (cclone_self, bs[cclone_self])])

    # ---- on 게임종료: hide master (master remains hidden anyway) ----
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=260,
        fields={"BROADCAST_OPTION": ["게임종료", BR_END]})
    hi_end = gen(); bs[hi_end] = mk("looks_hide")
    chain([(h3, bs[h3]), (hi_end, bs[hi_end])])

    # ---- clone start: setup + rise + collision ----
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=300, y=20)

    # set costume = 풍선색 (1..5) — Scratch costume IDs map: red=1, blue=2, yellow=3, green=4, purple=5
    bc_v = vrep("풍선색", V_BCOLOR)
    # switch costume to (풍선색)
    sw_color = gen(); bs[sw_color] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, [3, bc_v, [10, ""]]]})
    bs[bc_v]["parent"] = sw_color

    # 내크기 = (40, 70, 100 mapping from 1/2/3) using:  -10 + 풍선크기 * 30 + 풍선크기 * (풍선크기 - 1) * 5
    # Simpler: use chained if-elif.
    set_mysize = gen(); bs[set_mysize] = mk("data_setvariableto",
        inputs={"VALUE": num(70)}, fields={"VARIABLE": ["내크기", LV_MYSIZE]})
    set_myscore = gen(); bs[set_myscore] = mk("data_setvariableto",
        inputs={"VALUE": num(20)}, fields={"VARIABLE": ["내점수", LV_MYSCORE]})
    chain([(set_mysize, bs[set_mysize]), (set_myscore, bs[set_myscore])])

    # if 풍선크기 = 1 → 내크기=40, 내점수=30
    bsize_v_a = vrep("풍선크기", V_BSIZE)
    cond_small = cmp_op("operator_equals", bsize_v_a, 1)
    set_s40  = gen(); bs[set_s40]  = mk("data_setvariableto",
        inputs={"VALUE": num(40)}, fields={"VARIABLE": ["내크기", LV_MYSIZE]})
    set_s30  = gen(); bs[set_s30]  = mk("data_setvariableto",
        inputs={"VALUE": num(30)}, fields={"VARIABLE": ["내점수", LV_MYSCORE]})
    chain([(set_s40, bs[set_s40]), (set_s30, bs[set_s30])])
    if_small = gen(); bs[if_small] = mk("control_if",
        inputs={"CONDITION": [2, cond_small], "SUBSTACK": [2, set_s40]})
    bs[cond_small]["parent"] = if_small
    bs[set_s40]["parent"] = if_small

    # if 풍선크기 = 3 → 내크기=100, 내점수=10
    bsize_v_b = vrep("풍선크기", V_BSIZE)
    cond_big = cmp_op("operator_equals", bsize_v_b, 3)
    set_s100 = gen(); bs[set_s100] = mk("data_setvariableto",
        inputs={"VALUE": num(100)}, fields={"VARIABLE": ["내크기", LV_MYSIZE]})
    set_s10  = gen(); bs[set_s10]  = mk("data_setvariableto",
        inputs={"VALUE": num(10)}, fields={"VARIABLE": ["내점수", LV_MYSCORE]})
    chain([(set_s100, bs[set_s100]), (set_s10, bs[set_s10])])
    if_big = gen(); bs[if_big] = mk("control_if",
        inputs={"CONDITION": [2, cond_big], "SUBSTACK": [2, set_s100]})
    bs[cond_big]["parent"] = if_big
    bs[set_s100]["parent"] = if_big

    # apply size: set size to 내크기
    mysz_v = vrep("내크기", LV_MYSIZE)
    set_size = gen(); bs[set_size] = mk("looks_setsizeto",
        inputs={"SIZE": slot(mysz_v)})
    bs[mysz_v]["parent"] = set_size

    # position: x=풍선스폰X, y=-180
    bx_v = vrep("풍선스폰X", V_BX)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(bx_v), "Y": num(-180)})
    bs[bx_v]["parent"] = g_init

    # show + front
    show_c = gen(); bs[show_c] = mk("looks_show")
    front_c = gen(); bs[front_c] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # 흔들위상 = random(0, 360)
    rand_ph = op("operator_random", 0, 360, key1="FROM", key2="TO")
    set_phase = gen(); bs[set_phase] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_ph)}, fields={"VARIABLE": ["흔들위상", LV_PHASE]})
    bs[rand_ph]["parent"] = set_phase

    # ---- rise loop body ----
    # change y by (2.5 - 내크기 * 0.018)
    mysz_v2 = vrep("내크기", LV_MYSIZE)
    mul_speed = op("operator_multiply", mysz_v2, 0.018)
    sub_speed = op("operator_subtract", 2.5, mul_speed)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": slot(sub_speed)})
    bs[sub_speed]["parent"] = chy

    # 흔들위상 += 8
    inc_phase = gen(); bs[inc_phase] = mk("data_changevariableby",
        inputs={"VALUE": num(8)}, fields={"VARIABLE": ["흔들위상", LV_PHASE]})

    # change x by sin(흔들위상) * 0.8
    phase_v = vrep("흔들위상", LV_PHASE)
    sin_op = gen(); bs[sin_op] = mk("operator_mathop",
        inputs={"NUM": slot(phase_v)},
        fields={"OPERATOR": ["sin", None]})
    bs[phase_v]["parent"] = sin_op
    dx_calc = op("operator_multiply", sin_op, 0.8)
    chx = gen(); bs[chx] = mk("motion_changexby", inputs={"DX": slot(dx_calc)})
    bs[dx_calc]["parent"] = chx

    # if touching 섬광 → pop sequence
    tm_h = gen(); bs[tm_h] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["섬광", None]}, shadow=True)
    tc_h = gen(); bs[tc_h] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_h]})
    bs[tm_h]["parent"] = tc_h

    # 점수 += 내점수
    mysc_v = vrep("내점수", LV_MYSCORE)
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": slot(mysc_v)}, fields={"VARIABLE": ["점수", V_SCORE]})
    bs[mysc_v]["parent"] = inc_score

    # costume = pop (costume #6)
    cm_pop = gen(); bs[cm_pop] = mk("looks_costume",
        fields={"COSTUME": ["pop", None]}, shadow=True)
    swc_pop = gen(); bs[swc_pop] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_pop]})
    bs[cm_pop]["parent"] = swc_pop

    # pitch = 300 - 내크기 * 2
    mysz_v3 = vrep("내크기", LV_MYSIZE)
    mul_pitch = op("operator_multiply", mysz_v3, 2)
    pitch_calc = op("operator_subtract", 300, mul_pitch)
    pitch_set = gen(); bs[pitch_set] = mk("sound_seteffectto",
        inputs={"VALUE": slot(pitch_calc)}, fields={"EFFECT": ["PITCH", None]})
    bs[pitch_calc]["parent"] = pitch_set

    snm_pop = gen(); bs[snm_pop] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_pop = gen(); bs[snd_pop] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_pop]})
    bs[snm_pop]["parent"] = snd_pop

    wt_pop = gen(); bs[wt_pop] = mk("control_wait", inputs={"DURATION": num(0.12)})
    del_clone_hit = gen(); bs[del_clone_hit] = mk("control_delete_this_clone")

    chain([(inc_score, bs[inc_score]), (swc_pop, bs[swc_pop]),
           (pitch_set, bs[pitch_set]), (snd_pop, bs[snd_pop]),
           (wt_pop, bs[wt_pop]), (del_clone_hit, bs[del_clone_hit])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION": [2, tc_h], "SUBSTACK": [2, inc_score]})
    bs[tc_h]["parent"] = if_hit
    bs[inc_score]["parent"] = if_hit

    # if y > 180 → delete clone (escaped)
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_top = cmp_op("operator_gt", yp, 180)
    del_clone_esc = gen(); bs[del_clone_esc] = mk("control_delete_this_clone")
    if_esc = gen(); bs[if_esc] = mk("control_if",
        inputs={"CONDITION": [2, cond_top], "SUBSTACK": [2, del_clone_esc]})
    bs[cond_top]["parent"] = if_esc
    bs[del_clone_esc]["parent"] = if_esc

    # if 게임상태 = 0 → delete clone
    st_v_loop = vrep("게임상태", V_STATE)
    cond_dead = cmp_op("operator_equals", st_v_loop, 0)
    del_clone_end = gen(); bs[del_clone_end] = mk("control_delete_this_clone")
    if_end = gen(); bs[if_end] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, del_clone_end]})
    bs[cond_dead]["parent"] = if_end
    bs[del_clone_end]["parent"] = if_end

    wt_iter = gen(); bs[wt_iter] = mk("control_wait", inputs={"DURATION": num(0.03)})

    chain([(chy, bs[chy]), (inc_phase, bs[inc_phase]), (chx, bs[chx]),
           (if_hit, bs[if_hit]), (if_esc, bs[if_esc]), (if_end, bs[if_end]),
           (wt_iter, bs[wt_iter])])

    forever_loop = gen(); bs[forever_loop] = mk("control_forever",
        inputs={"SUBSTACK": [2, chy]})
    bs[chy]["parent"] = forever_loop

    # chain clone start
    chain([(ch, bs[ch]), (sw_color, bs[sw_color]),
           (set_mysize, bs[set_mysize]),  # default size/score first
           (if_small, bs[if_small]), (if_big, bs[if_big]),
           (set_size, bs[set_size]), (g_init, bs[g_init]),
           (show_c, bs[show_c]), (front_c, bs[front_c]),
           (set_phase, bs[set_phase]), (forever_loop, bs[forever_loop])])

    return bs

# =====================================================================
#  TIMEUP BANNER  (mirrors duck-hunt gameover pattern)
# =====================================================================
def build_timeup_blocks():
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
    cond_zero = cmp_op("operator_equals", state_v2, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_zero]})
    bs[cond_zero]["parent"] = wait_over

    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (wait_start, bs[wait_start]), (wait_over, bs[wait_over]),
           (show, bs[show])])
    return bs

# =====================================================================
#  ASSEMBLE
# =====================================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    def emit_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f: f.write(svg)
        return m

    bg_md5    = emit_svg(BG_SVG)
    ch_md5    = emit_svg(CROSSHAIR_SVG)
    fl_md5    = emit_svg(FLASH_SVG)
    bRed_md5  = emit_svg(BALLOON_RED)
    bBlu_md5  = emit_svg(BALLOON_BLUE)
    bYel_md5  = emit_svg(BALLOON_YELLOW)
    bGrn_md5  = emit_svg(BALLOON_GREEN)
    bPur_md5  = emit_svg(BALLOON_PURPLE)
    bPop_md5  = emit_svg(BALLOON_POP)
    tu_md5    = emit_svg(TIMEUP_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks     = build_stage_blocks()
    crosshair_blocks = build_crosshair_blocks()
    flash_blocks     = build_flash_blocks()
    balloon_blocks   = build_balloon_blocks()
    timeup_blocks    = build_timeup_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 48000, "sampleCount": 1123,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:  ["점수",     0],
            V_TIME:   ["시간",     60],
            V_STATE:  ["게임상태", 1],
            V_FX:     ["섬광X",    0],
            V_FY:     ["섬광Y",    0],
            V_BX:     ["풍선스폰X", 0],
            V_BSIZE:  ["풍선크기", 2],
            V_BCOLOR: ["풍선색",   1],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "풍선스폰",
            BR_END:   "게임종료",
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

    crosshair = {
        "isStage": False, "name": "조준선",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": crosshair_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "십자선", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ch_md5, "md5ext": f"{ch_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 20
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    flash = {
        "isStage": False, "name": "섬광",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": flash_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "flash", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": fl_md5, "md5ext": f"{fl_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 65, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    balloon = {
        "isStage": False, "name": "풍선",
        "variables": {
            LV_MYSIZE:  ["내크기", 70],
            LV_MYSCORE: ["내점수", 20],
            LV_PHASE:   ["흔들위상", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": balloon_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "red", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bRed_md5, "md5ext": f"{bRed_md5}.svg",
             "rotationCenterX": 35, "rotationCenterY": 50},
            {"name": "blue", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bBlu_md5, "md5ext": f"{bBlu_md5}.svg",
             "rotationCenterX": 35, "rotationCenterY": 50},
            {"name": "yellow", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bYel_md5, "md5ext": f"{bYel_md5}.svg",
             "rotationCenterX": 35, "rotationCenterY": 50},
            {"name": "green", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bGrn_md5, "md5ext": f"{bGrn_md5}.svg",
             "rotationCenterX": 35, "rotationCenterY": 50},
            {"name": "purple", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bPur_md5, "md5ext": f"{bPur_md5}.svg",
             "rotationCenterX": 35, "rotationCenterY": 50},
            {"name": "pop", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bPop_md5, "md5ext": f"{bPop_md5}.svg",
             "rotationCenterX": 50, "rotationCenterY": 50},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": -220, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    timeup = {
        "isStage": False, "name": "시간종료",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": timeup_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": tu_md5, "md5ext": f"{tu_md5}.svg",
            "rotationCenterX": 190, "rotationCenterY": 90
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 1000, "isDiscrete": True},
        {"id": V_TIME, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "시간"}, "spriteName": None,
         "value": 60, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 60, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, crosshair, flash, balloon, timeup],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "balloon-shooter-builder"}
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
    print(f"OK wrote {OUTPUT}")
    print(f"  stage:     {len(stage_blocks)} blocks")
    print(f"  crosshair: {len(crosshair_blocks)} blocks")
    print(f"  flash:     {len(flash_blocks)} blocks")
    print(f"  balloon:   {len(balloon_blocks)} blocks")
    print(f"  timeup:    {len(timeup_blocks)} blocks")
    total = sum(len(b) for b in
        [stage_blocks, crosshair_blocks, flash_blocks, balloon_blocks, timeup_blocks])
    print(f"  TOTAL:     {total} blocks")

if __name__ == "__main__":
    main()
