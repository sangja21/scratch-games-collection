#!/usr/bin/env python3
"""Ghost Hunt — dark cartoon-y room, flashlight aim, blinking ghosts (60s time attack)."""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "유령_사냥.sb3")

# ==============================================================
#  SVG ASSETS
# ==============================================================

# -------- Dark cartoon-y room background --------
ROOM_BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#1A0F2E"/>
      <stop offset="60%" stop-color="#2A1B3D"/>
      <stop offset="100%" stop-color="#3D2A4E"/>
    </linearGradient>
    <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#1A0F2E"/>
      <stop offset="100%" stop-color="#0A0518"/>
    </linearGradient>
    <radialGradient id="moonlight" cx="0.5" cy="0.4" r="0.45">
      <stop offset="0%"   stop-color="#9C7BC4" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#9C7BC4" stop-opacity="0"/>
    </radialGradient>
    <pattern id="dots" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
      <circle cx="20" cy="20" r="1.2" fill="#5C4280" opacity="0.4"/>
    </pattern>
  </defs>
  <rect width="480" height="280" fill="url(#wall)"/>
  <rect width="480" height="280" fill="url(#dots)"/>
  <rect y="280" width="480" height="80" fill="url(#floor)"/>

  <!-- Two arched windows with moonlight -->
  <g>
    <rect x="80"  y="50" width="80" height="120" rx="40" fill="#0F0820" stroke="#5C4280" stroke-width="3"/>
    <rect x="80"  y="50" width="80" height="120" rx="40" fill="url(#moonlight)"/>
    <line x1="120" y1="50" x2="120" y2="170" stroke="#5C4280" stroke-width="2"/>
    <line x1="80"  y1="110" x2="160" y2="110" stroke="#5C4280" stroke-width="2"/>

    <rect x="320" y="50" width="80" height="120" rx="40" fill="#0F0820" stroke="#5C4280" stroke-width="3"/>
    <rect x="320" y="50" width="80" height="120" rx="40" fill="url(#moonlight)"/>
    <line x1="360" y1="50" x2="360" y2="170" stroke="#5C4280" stroke-width="2"/>
    <line x1="320" y1="110" x2="400" y2="110" stroke="#5C4280" stroke-width="2"/>
  </g>

  <!-- Bookshelf silhouette left -->
  <g fill="#0A0518" stroke="#3D2A4E" stroke-width="1.5">
    <rect x="20"  y="200" width="50" height="80"/>
    <line x1="20" y1="220" x2="70" y2="220"/>
    <line x1="20" y1="245" x2="70" y2="245"/>
    <rect x="24" y="203" width="6" height="16" fill="#3D2A4E"/>
    <rect x="32" y="203" width="6" height="16" fill="#5C4280"/>
    <rect x="40" y="203" width="6" height="16" fill="#3D2A4E"/>
    <rect x="24" y="225" width="6" height="18" fill="#5C4280"/>
    <rect x="32" y="225" width="6" height="18" fill="#3D2A4E"/>
  </g>

  <!-- Sofa silhouette center-bottom -->
  <g fill="#0A0518" stroke="#3D2A4E" stroke-width="1.5">
    <rect x="180" y="235" width="120" height="45" rx="10"/>
    <rect x="180" y="225" width="20" height="20" rx="5"/>
    <rect x="280" y="225" width="20" height="20" rx="5"/>
  </g>

  <!-- Spider web in top-right corner -->
  <g stroke="#5C4280" stroke-width="0.8" fill="none" opacity="0.6">
    <path d="M 480 0 L 430 30 L 480 50"/>
    <path d="M 480 0 L 450 50 L 480 80"/>
    <path d="M 480 0 L 470 60 L 480 100"/>
    <path d="M 460 10 L 465 25 L 458 40"/>
  </g>

  <!-- Floor shadow line -->
  <line x1="0" y1="280" x2="480" y2="280" stroke="#5C4280" stroke-width="1.5" opacity="0.5"/>
</svg>"""

# -------- Flashlight: big translucent yellow circle + small crosshair --------
FLASHLIGHT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
  <defs>
    <radialGradient id="lightcone" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%"   stop-color="#FFF59D" stop-opacity="0.55"/>
      <stop offset="50%"  stop-color="#FFEB3B" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="#FFEB3B" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <circle cx="80" cy="80" r="78" fill="url(#lightcone)"/>
  <circle cx="80" cy="80" r="22" fill="none" stroke="#FFFFFF" stroke-width="2" opacity="0.85"/>
  <line x1="80" y1="56" x2="80" y2="70" stroke="#FFFFFF" stroke-width="2.5" opacity="0.9"/>
  <line x1="80" y1="90" x2="80" y2="104" stroke="#FFFFFF" stroke-width="2.5" opacity="0.9"/>
  <line x1="56" y1="80" x2="70" y2="80" stroke="#FFFFFF" stroke-width="2.5" opacity="0.9"/>
  <line x1="90" y1="80" x2="104" y2="80" stroke="#FFFFFF" stroke-width="2.5" opacity="0.9"/>
  <circle cx="80" cy="80" r="2" fill="#FF5252"/>
</svg>"""

# -------- Muzzle flash (yellow 8-pointed star) --------
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

# -------- Cartoon ghost frame A (normal) --------
GHOST_A_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="100" viewBox="0 0 80 100">
  <!-- ghost body: rounded top + wavy bottom -->
  <path d="M 40 6
           C 18 6, 8 26, 8 46
           L 8 84
           Q 8 96, 16 90
           Q 24 84, 32 92
           Q 40 100, 48 92
           Q 56 84, 64 92
           Q 72 96, 72 84
           L 72 46
           C 72 26, 62 6, 40 6 Z"
        fill="#F5F5F5" stroke="#9E9E9E" stroke-width="2" opacity="0.96"/>
  <!-- subtle inner shadow -->
  <path d="M 40 12
           C 22 12, 14 30, 14 48
           L 14 78"
        fill="none" stroke="#E0E0E0" stroke-width="1.5" opacity="0.6"/>
  <!-- eyes (big black circles + white highlight) -->
  <ellipse cx="28" cy="42" rx="6" ry="8" fill="#1A1A1A"/>
  <ellipse cx="52" cy="42" rx="6" ry="8" fill="#1A1A1A"/>
  <circle cx="30" cy="38" r="1.8" fill="#FFFFFF"/>
  <circle cx="54" cy="38" r="1.8" fill="#FFFFFF"/>
  <!-- friendly smile (curved line) -->
  <path d="M 30 58 Q 40 66 50 58"
        fill="none" stroke="#1A1A1A" stroke-width="2.2" stroke-linecap="round"/>
  <!-- rosy cheeks -->
  <circle cx="22" cy="56" r="3" fill="#FFB6C1" opacity="0.55"/>
  <circle cx="58" cy="56" r="3" fill="#FFB6C1" opacity="0.55"/>
</svg>"""

# -------- Cartoon ghost frame B (slightly faded for blink) --------
GHOST_B_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="100" viewBox="0 0 80 100">
  <path d="M 40 8
           C 20 8, 10 28, 10 46
           L 10 82
           Q 10 92, 18 88
           Q 26 84, 34 90
           Q 40 96, 46 90
           Q 54 84, 62 88
           Q 70 92, 70 82
           L 70 46
           C 70 28, 60 8, 40 8 Z"
        fill="#F5F5F5" stroke="#9E9E9E" stroke-width="2" opacity="0.65"/>
  <ellipse cx="28" cy="42" rx="6" ry="8" fill="#1A1A1A" opacity="0.75"/>
  <ellipse cx="52" cy="42" rx="6" ry="8" fill="#1A1A1A" opacity="0.75"/>
  <circle cx="30" cy="38" r="1.8" fill="#FFFFFF" opacity="0.75"/>
  <circle cx="54" cy="38" r="1.8" fill="#FFFFFF" opacity="0.75"/>
  <path d="M 30 58 Q 40 64 50 58"
        fill="none" stroke="#1A1A1A" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
</svg>"""

# -------- Ghost hit (surprised X-eyes + sparkles) --------
GHOST_HIT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="100" viewBox="0 0 80 100">
  <path d="M 40 8
           C 20 8, 10 28, 10 46
           L 10 80
           Q 10 90, 18 86
           Q 26 82, 34 88
           Q 40 92, 46 88
           Q 54 82, 62 86
           Q 70 90, 70 80
           L 70 46
           C 70 28, 60 8, 40 8 Z"
        fill="#FFE0B2" stroke="#FF9800" stroke-width="2"/>
  <!-- X eyes -->
  <line x1="22" y1="36" x2="34" y2="48" stroke="#1A1A1A" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="34" y1="36" x2="22" y2="48" stroke="#1A1A1A" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="46" y1="36" x2="58" y2="48" stroke="#1A1A1A" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="58" y1="36" x2="46" y2="48" stroke="#1A1A1A" stroke-width="2.5" stroke-linecap="round"/>
  <!-- open "o" mouth -->
  <circle cx="40" cy="62" r="4" fill="#1A1A1A"/>
  <!-- sparkles around -->
  <polygon points="6,20 8,24 12,22 9,26 12,30 8,28 6,32 5,28 1,30 4,26 1,22 5,24" fill="#FFEB3B"/>
  <polygon points="74,30 76,33 79,32 77,35 79,38 76,37 74,40 73,37 70,38 72,35 70,32 73,33" fill="#FFEB3B"/>
  <polygon points="68,68 70,71 73,70 71,73 73,76 70,75 68,78 67,75 64,76 66,73 64,70 67,71" fill="#FFEB3B"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#1A0F2E" opacity="0.95"
        stroke="#9C7BC4" stroke-width="4"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="42" font-weight="bold">TIME UP!</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">유령 사냥 끝!</text>
  <text x="180" y="134" text-anchor="middle"
        fill="#9C7BC4" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭</text>
</svg>"""

# ==============================================================
#  HELPERS
# ==============================================================
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n):  return [1, [4, str(n)]]
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
V_SCORE = "varScore01"
V_TIME  = "varTime02"
V_STATE = "varState03"
V_FX    = "varFX04"
V_FY    = "varFY05"
V_GX    = "varGX06"
V_GY    = "varGY07"

BR_START = "brStart01"
BR_SPAWN = "brSpawn02"
BR_END   = "brEnd03"

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

# ==============================================================
#  STAGE — init + timer + spawn loop
# ==============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init + start ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = []
    for var_pair, val in [
        (("점수", V_SCORE), 0),
        (("남은시간", V_TIME), 60),
        (("게임상태", V_STATE), 1),
        (("섬광X", V_FX), 0),
        (("섬광Y", V_FY), 0),
        (("유령X", V_GX), 0),
        (("유령Y", V_GY), 0),
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

    # === on 게임시작 (script A — timer): wait 1s, time-1, repeat until time<=0 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # body: wait 1; time -= 1
    wt1 = gen(); bs[wt1] = mk("control_wait", inputs={"DURATION": num(1)})
    dec_t = gen(); bs[dec_t] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["남은시간", V_TIME]})
    chain([(wt1, bs[wt1]), (dec_t, bs[dec_t])])

    # condition: 남은시간 <= 0  →  use NOT(>0)
    time_v = vrep("남은시간", V_TIME)
    cond_pos = cmp_op("operator_gt", time_v, 0)
    not_pos = gen(); bs[not_pos] = mk("operator_not",
        inputs={"OPERAND": [2, cond_pos]})
    bs[cond_pos]["parent"] = not_pos

    rep_t = gen(); bs[rep_t] = mk("control_repeat_until",
        inputs={"CONDITION": [2, not_pos], "SUBSTACK": [2, wt1]})
    bs[not_pos]["parent"] = rep_t
    bs[wt1]["parent"] = rep_t

    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})

    bm_end = gen(); bs[bm_end] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임종료", BR_END]}, shadow=True)
    bc_end = gen(); bs[bc_end] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_end]})
    bs[bm_end]["parent"] = bc_end

    chain([(h2, bs[h2]), (rep_t, bs[rep_t]),
           (set_state0, bs[set_state0]), (bc_end, bs[bc_end])])

    # === on 게임시작 (script B — spawn loop): random pos → broadcast 유령등장 → wait ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # body
    rand_gx = op("operator_random", -200, 200, key1="FROM", key2="TO")
    set_gx = gen(); bs[set_gx] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_gx)}, fields={"VARIABLE": ["유령X", V_GX]})
    bs[rand_gx]["parent"] = set_gx

    rand_gy = op("operator_random", -100, 140, key1="FROM", key2="TO")
    set_gy = gen(); bs[set_gy] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_gy)}, fields={"VARIABLE": ["유령Y", V_GY]})
    bs[rand_gy]["parent"] = set_gy

    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["유령등장", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    # wait random 0.7..1.2
    rand_wt = op("operator_random", 0.7, 1.2, key1="FROM", key2="TO")
    wt_sp = gen(); bs[wt_sp] = mk("control_wait",
        inputs={"DURATION": slot(rand_wt)})
    bs[rand_wt]["parent"] = wt_sp

    chain([(set_gx, bs[set_gx]), (set_gy, bs[set_gy]),
           (bc_sp, bs[bc_sp]), (wt_sp, bs[wt_sp])])

    # repeat until 게임상태 = 0  →  use NOT(state=1)
    state_v = vrep("게임상태", V_STATE)
    cond_alive = cmp_op("operator_equals", state_v, 1)
    not_alive = gen(); bs[not_alive] = mk("operator_not",
        inputs={"OPERAND": [2, cond_alive]})
    bs[cond_alive]["parent"] = not_alive

    rep_sp = gen(); bs[rep_sp] = mk("control_repeat_until",
        inputs={"CONDITION": [2, not_alive], "SUBSTACK": [2, set_gx]})
    bs[not_alive]["parent"] = rep_sp
    bs[set_gx]["parent"] = rep_sp

    chain([(h3, bs[h3]), (rep_sp, bs[rep_sp])])

    return bs

# ==============================================================
#  FLASHLIGHT — follow mouse + click to fire flash
# ==============================================================
def build_flashlight_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === flag: setup + follow mouse forever ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
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

    # === when sprite clicked: fire (only if state=1) ===
    h2 = gen(); bs[h2] = mk("event_whenthisspriteclicked", top=True, x=320, y=20)

    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)

    # 섬광X = mouseX
    mx2 = gen(); bs[mx2] = mk("sensing_mousex")
    set_fx = gen(); bs[set_fx] = mk("data_setvariableto",
        inputs={"VALUE": slot(mx2)}, fields={"VARIABLE": ["섬광X", V_FX]})
    bs[mx2]["parent"] = set_fx

    # 섬광Y = mouseY
    my2 = gen(); bs[my2] = mk("sensing_mousey")
    set_fy = gen(); bs[set_fy] = mk("data_setvariableto",
        inputs={"VALUE": slot(my2)}, fields={"VARIABLE": ["섬광Y", V_FY]})
    bs[my2]["parent"] = set_fy

    # create clone of 섬광
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["섬광", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone

    # pop sound high pitch
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

# ==============================================================
#  FLASH (섬광) — clone shown 0.12s then deleted
# ==============================================================
def build_flash_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz])])

    # === clone start ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)
    fx_v = vrep("섬광X", V_FX); fy_v = vrep("섬광Y", V_FY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(fx_v), "Y": slot(fy_v)})
    bs[fx_v]["parent"] = g; bs[fy_v]["parent"] = g

    sz2 = gen(); bs[sz2] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.12)})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (sz2, bs[sz2]), (front, bs[front]),
           (show, bs[show]), (wt, bs[wt]), (hi2, bs[hi2]), (delc, bs[delc])])

    return bs

# ==============================================================
#  GHOST — clone-based, blink for ~0.5s then disappear (or get shot)
# ==============================================================
def build_ghost_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === flag: hide + setup ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    cm0 = gen(); bs[cm0] = mk("looks_costume",
        fields={"COSTUME": ["ghost_a", None]}, shadow=True)
    swc0 = gen(); bs[swc0] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm0]})
    bs[cm0]["parent"] = swc0
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (swc0, bs[swc0])])

    # === on 유령등장: create clone of myself ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["유령등장", BR_SPAWN]})

    cmenu_g = gen(); bs[cmenu_g] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone_g = gen(); bs[cclone_g] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu_g]})
    bs[cmenu_g]["parent"] = cclone_g

    chain([(h2, bs[h2]), (cclone_g, bs[cclone_g])])

    # === clone start: go to (유령X, 유령Y), blink, check shot, delete ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)

    gx_v = vrep("유령X", V_GX); gy_v = vrep("유령Y", V_GY)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(gx_v), "Y": slot(gy_v)})
    bs[gx_v]["parent"] = g_init; bs[gy_v]["parent"] = g_init

    cm_a = gen(); bs[cm_a] = mk("looks_costume",
        fields={"COSTUME": ["ghost_a", None]}, shadow=True)
    swc_a = gen(); bs[swc_a] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_a]})
    bs[cm_a]["parent"] = swc_a

    show = gen(); bs[show] = mk("looks_show")

    # ---- blink loop body (one iteration: next costume + check hit + wait) ----
    nc = gen(); bs[nc] = mk("looks_nextcostume")

    # if touching 섬광 → hit costume, score+10, pop sound, wait, delete
    tm_h = gen(); bs[tm_h] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["섬광", None]}, shadow=True)
    tc_h = gen(); bs[tc_h] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_h]})
    bs[tm_h]["parent"] = tc_h

    cm_hit = gen(); bs[cm_hit] = mk("looks_costume",
        fields={"COSTUME": ["ghost_hit", None]}, shadow=True)
    swc_hit = gen(); bs[swc_hit] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_hit]})
    bs[cm_hit]["parent"] = swc_hit

    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(10)}, fields={"VARIABLE": ["점수", V_SCORE]})

    pitch_hit = gen(); bs[pitch_hit] = mk("sound_seteffectto",
        inputs={"VALUE": num(80)}, fields={"EFFECT": ["PITCH", None]})
    snm_hit = gen(); bs[snm_hit] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_hit = gen(); bs[snd_hit] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_hit]})
    bs[snm_hit]["parent"] = snd_hit

    wt_hit = gen(); bs[wt_hit] = mk("control_wait",
        inputs={"DURATION": num(0.18)})
    hi_hit = gen(); bs[hi_hit] = mk("looks_hide")
    del_hit = gen(); bs[del_hit] = mk("control_delete_this_clone")

    chain([(swc_hit, bs[swc_hit]), (inc_score, bs[inc_score]),
           (pitch_hit, bs[pitch_hit]), (snd_hit, bs[snd_hit]),
           (wt_hit, bs[wt_hit]), (hi_hit, bs[hi_hit]),
           (del_hit, bs[del_hit])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION": [2, tc_h], "SUBSTACK": [2, swc_hit]})
    bs[tc_h]["parent"] = if_hit
    bs[swc_hit]["parent"] = if_hit

    wt_b = gen(); bs[wt_b] = mk("control_wait",
        inputs={"DURATION": num(0.13)})

    chain([(nc, bs[nc]), (if_hit, bs[if_hit]), (wt_b, bs[wt_b])])

    # repeat 4 times (a↔b toggled 4 times ≈ 0.52s)
    rep_b = gen(); bs[rep_b] = mk("control_repeat",
        inputs={"TIMES": num(4), "SUBSTACK": [2, nc]})
    bs[nc]["parent"] = rep_b

    # After blink loop: hide + delete clone
    hi_end = gen(); bs[hi_end] = mk("looks_hide")
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g_init, bs[g_init]), (swc_a, bs[swc_a]),
           (show, bs[show]), (rep_b, bs[rep_b]),
           (hi_end, bs[hi_end]), (del_end, bs[del_end])])

    return bs

# ==============================================================
#  GAME OVER banner — show when 게임종료 broadcast
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
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    # === on 게임종료: show banner ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임종료", BR_END]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(h2, bs[h2]), (show, bs[show])])

    return bs

# ==============================================================
#  ASSEMBLE
# ==============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    def w(name_svg, content):
        m = md5_bytes(content.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f:
            f.write(content)
        return m

    bg_md5 = w("room_bg", ROOM_BG_SVG)
    fl_md5 = w("flashlight", FLASHLIGHT_SVG)
    fs_md5 = w("flash", FLASH_SVG)
    ga_md5 = w("ghost_a", GHOST_A_SVG)
    gb_md5 = w("ghost_b", GHOST_B_SVG)
    gh_md5 = w("ghost_hit", GHOST_HIT_SVG)
    go_md5 = w("gameover", GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks      = build_stage_blocks()
    flashlight_blocks = build_flashlight_blocks()
    flash_blocks      = build_flash_blocks()
    ghost_blocks      = build_ghost_blocks()
    gameover_blocks   = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE: ["점수", 0],
            V_TIME:  ["남은시간", 60],
            V_STATE: ["게임상태", 1],
            V_FX:    ["섬광X", 0],
            V_FY:    ["섬광Y", 0],
            V_GX:    ["유령X", 0],
            V_GY:    ["유령Y", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "유령등장",
            BR_END:   "게임종료",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "방", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    flashlight = {
        "isStage": False, "name": "회중전등",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": flashlight_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "라이트", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": fl_md5, "md5ext": f"{fl_md5}.svg",
            "rotationCenterX": 80, "rotationCenterY": 80
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    flash = {
        "isStage": False, "name": "섬광",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": flash_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "flash", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": fs_md5, "md5ext": f"{fs_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ghost = {
        "isStage": False, "name": "유령",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ghost_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "ghost_a", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ga_md5, "md5ext": f"{ga_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 50},
            {"name": "ghost_b", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": gb_md5, "md5ext": f"{gb_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 50},
            {"name": "ghost_hit", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": gh_md5, "md5ext": f"{gh_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 50},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 90, "direction": 90,
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
            "rotationCenterX": 180, "rotationCenterY": 80
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
         "params": {"VARIABLE": "남은시간"}, "spriteName": None,
         "value": 60, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 60, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, flashlight, flash, ghost, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "ghost-hunt-builder"}
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
    print(f"  stage:      {len(stage_blocks)} blocks")
    print(f"  flashlight: {len(flashlight_blocks)} blocks")
    print(f"  flash:      {len(flash_blocks)} blocks")
    print(f"  ghost:      {len(ghost_blocks)} blocks")
    print(f"  gameover:   {len(gameover_blocks)} blocks")
    total = (len(stage_blocks)+len(flashlight_blocks)+len(flash_blocks)
             +len(ghost_blocks)+len(gameover_blocks))
    print(f"  TOTAL:      {total} blocks")

if __name__ == "__main__":
    main()
