#!/usr/bin/env python3
"""Missile Command — Atari 1980 classic clone (3 cities, mouse-click intercept)."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "미사일_커맨드.sb3")

# -------- Background SVG: night sky + horizon + stars --------
random.seed(7)
star_paths = []
for _ in range(70):
    x = random.randint(5, 475)
    y = random.randint(5, 230)
    r = random.choice([0.6, 0.9, 1.1, 1.4, 1.8])
    op = round(random.uniform(0.4, 1.0), 2)
    star_paths.append(f'<circle cx="{x}" cy="{y}" r="{r}" opacity="{op}"/>')
STARS = "\n    ".join(star_paths)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#0B1438"/>
      <stop offset="70%" stop-color="#1A2050"/>
      <stop offset="100%" stop-color="#322050"/>
    </linearGradient>
    <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#3D2E1A"/>
      <stop offset="100%" stop-color="#1A0F08"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <ellipse cx="380" cy="60"  rx="100" ry="35" fill="#5E35B1" opacity="0.18"/>
  <ellipse cx="100" cy="160" rx="80"  ry="20" fill="#1E88E5" opacity="0.12"/>
  <g fill="white">
    {STARS}
  </g>
  <rect x="0" y="270" width="480" height="90" fill="url(#ground)"/>
  <line x1="0" y1="270" x2="480" y2="270" stroke="#5C3E1F" stroke-width="2"/>
</svg>"""

# -------- Crosshair: red plus + circle --------
CROSSHAIR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="14" fill="none" stroke="#FF1744" stroke-width="2"/>
  <line x1="20" y1="2"  x2="20" y2="14" stroke="#FF1744" stroke-width="2.5"/>
  <line x1="20" y1="26" x2="20" y2="38" stroke="#FF1744" stroke-width="2.5"/>
  <line x1="2"  y1="20" x2="14" y2="20" stroke="#FF1744" stroke-width="2.5"/>
  <line x1="26" y1="20" x2="38" y2="20" stroke="#FF1744" stroke-width="2.5"/>
  <circle cx="20" cy="20" r="1.5" fill="#FF1744"/>
</svg>"""

# -------- Explosion: radial white/yellow --------
EXPLOSION_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <defs>
    <radialGradient id="boom" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%"   stop-color="#FFFFFF" stop-opacity="0.95"/>
      <stop offset="40%"  stop-color="#FFEB3B" stop-opacity="0.85"/>
      <stop offset="75%"  stop-color="#FF9800" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#F44336" stop-opacity="0.0"/>
    </radialGradient>
  </defs>
  <circle cx="30" cy="30" r="28" fill="url(#boom)"/>
</svg>"""

# -------- Enemy missile: red missile pointing down with trail --------
ENEMY_MISSILE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="50" viewBox="0 0 20 50">
  <path d="M10 2 L7 40 L13 40 Z" fill="#FFEB3B" opacity="0.55"/>
  <path d="M10 8 L8 40 L12 40 Z" fill="#FFFFFF" opacity="0.4"/>
  <rect x="6" y="38" width="8" height="9" rx="2" fill="#F44336"/>
  <polygon points="6,46 2,49 6,47" fill="#B71C1C"/>
  <polygon points="14,46 18,49 14,47" fill="#B71C1C"/>
  <polygon points="6,38 10,32 14,38" fill="#E53935"/>
  <circle cx="10" cy="44" r="1.5" fill="#FFEB3B"/>
</svg>"""

# -------- City intact: blue 3-tower block --------
CITY_INTACT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40" viewBox="0 0 60 40">
  <rect x="2"  y="20" width="14" height="18" fill="#42A5F5" stroke="#1565C0" stroke-width="1"/>
  <rect x="22" y="12" width="16" height="26" fill="#5C6BC0" stroke="#283593" stroke-width="1"/>
  <rect x="44" y="22" width="14" height="16" fill="#42A5F5" stroke="#1565C0" stroke-width="1"/>
  <rect x="5"  y="24" width="3" height="3" fill="#FFEB3B"/>
  <rect x="10" y="24" width="3" height="3" fill="#FFEB3B"/>
  <rect x="5"  y="30" width="3" height="3" fill="#FFEB3B"/>
  <rect x="25" y="16" width="3" height="3" fill="#FFEB3B"/>
  <rect x="30" y="16" width="3" height="3" fill="#FFEB3B"/>
  <rect x="33" y="22" width="3" height="3" fill="#FFEB3B"/>
  <rect x="25" y="28" width="3" height="3" fill="#FFEB3B"/>
  <rect x="47" y="26" width="3" height="3" fill="#FFEB3B"/>
  <rect x="52" y="26" width="3" height="3" fill="#FFEB3B"/>
</svg>"""

# -------- City ruined: gray rubble --------
CITY_RUINED_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40" viewBox="0 0 60 40">
  <polygon points="2,38 8,30 14,34 20,28 28,36 36,30 44,34 52,30 58,38" fill="#616161" stroke="#212121" stroke-width="1"/>
  <rect x="6"  y="34" width="4" height="4" fill="#424242"/>
  <rect x="18" y="32" width="3" height="6" fill="#424242"/>
  <rect x="30" y="33" width="4" height="5" fill="#424242"/>
  <rect x="42" y="32" width="3" height="6" fill="#424242"/>
  <circle cx="12" cy="36" r="1" fill="#FF5722"/>
  <circle cx="33" cy="35" r="1.2" fill="#FF5722"/>
  <circle cx="48" cy="36" r="1" fill="#FF5722"/>
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
        font-size="20">도시가 모두 파괴됐어요</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#FFB74D" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭</text>
</svg>"""

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
V_SCORE  = "varScore01"
V_LIFE   = "varLife02"
V_WAVE   = "varWave03"
V_STATE  = "varState04"
V_KILLS  = "varKills05"
V_TOTAL  = "varTotal06"
V_SPEED  = "varSpeed07"
V_EX     = "varEX08"
V_EY     = "varEY09"
V_TX     = "varTX10"
V_SX0    = "varSX011"   # missile clone local: start X
V_DX     = "varDX12"    # missile clone local: dx per tick
V_DY     = "varDY13"    # missile clone local: dy per tick
V_CITYN  = "varCityNum14"  # city sprite-local: 1/2/3

BR_START = "brStart01"
BR_SPAWN = "brSpawn02"
BR_NEXT  = "brNext03"
BR_CITY  = "brCity04"

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
#  STAGE blocks
# ==============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init + spawn cities + start ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    s_score = gen(); bs[s_score] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점수", V_SCORE]})
    s_life = gen(); bs[s_life] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["라이프", V_LIFE]})
    s_wave = gen(); bs[s_wave] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_WAVE]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    s_kills = gen(); bs[s_kills] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["격추수", V_KILLS]})
    s_total = gen(); bs[s_total] = mk("data_setvariableto",
        inputs={"VALUE": num(8)}, fields={"VARIABLE": ["라운드미사일수", V_TOTAL]})
    s_speed = gen(); bs[s_speed] = mk("data_setvariableto",
        inputs={"VALUE": num(1.6)}, fields={"VARIABLE": ["적속도", V_SPEED]})

    bm_city = gen(); bs[bm_city] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["도시생성", BR_CITY]}, shadow=True)
    bc_city = gen(); bs[bc_city] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_city]})
    bs[bm_city]["parent"] = bc_city

    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(0.3)})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h,bs[h]),(s_score,bs[s_score]),(s_life,bs[s_life]),(s_wave,bs[s_wave]),
           (s_state,bs[s_state]),(s_kills,bs[s_kills]),(s_total,bs[s_total]),
           (s_speed,bs[s_speed]),(bc_city,bs[bc_city]),(w1,bs[w1]),(bc_start,bs[bc_start])])

    # === on 게임시작: broadcast 적생성, then idle until state=0 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=240,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    chain([(h2,bs[h2]),(bc_sp,bs[bc_sp])])

    # === on 다음라운드: ramp difficulty + delay + 적생성 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=420,
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]})
    chg_wave = gen(); bs[chg_wave] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_WAVE]})
    chg_speed = gen(); bs[chg_speed] = mk("data_changevariableby",
        inputs={"VALUE": num(0.3)}, fields={"VARIABLE": ["적속도", V_SPEED]})
    chg_total = gen(); bs[chg_total] = mk("data_changevariableby",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["라운드미사일수", V_TOTAL]})
    r_kills = gen(); bs[r_kills] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["격추수", V_KILLS]})
    w2 = gen(); bs[w2] = mk("control_wait", inputs={"DURATION": num(1.2)})

    bm_sp2 = gen(); bs[bm_sp2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]}, shadow=True)
    bc_sp2 = gen(); bs[bc_sp2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_sp2]})
    bs[bm_sp2]["parent"] = bc_sp2

    chain([(h3,bs[h3]),(chg_wave,bs[chg_wave]),(chg_speed,bs[chg_speed]),
           (chg_total,bs[chg_total]),(r_kills,bs[r_kills]),(w2,bs[w2]),(bc_sp2,bs[bc_sp2])])

    return bs

# ==============================================================
#  CROSSHAIR (조준선) blocks
# ==============================================================
def build_crosshair_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # === when flag clicked: show + follow mouse forever ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")

    # forever: go to mouse
    mx = gen(); bs[mx] = mk("sensing_mousex")
    my = gen(); bs[my] = mk("sensing_mousey")
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(mx), "Y": slot(my)})
    bs[mx]["parent"] = g; bs[my]["parent"] = g

    forever = gen(); bs[forever] = mk("control_forever",
        inputs={"SUBSTACK":[2, g]})
    bs[g]["parent"] = forever

    chain([(h,bs[h]),(sz,bs[sz]),(front,bs[front]),(show,bs[show]),(forever,bs[forever])])

    # === when this sprite clicked: spawn 폭발 at mouse ===
    h2 = gen(); bs[h2] = mk("event_whenthisspriteclicked", top=True, x=300, y=20)
    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)

    mx2 = gen(); bs[mx2] = mk("sensing_mousex")
    set_ex = gen(); bs[set_ex] = mk("data_setvariableto",
        inputs={"VALUE": slot(mx2)}, fields={"VARIABLE": ["폭발X", V_EX]})
    bs[mx2]["parent"] = set_ex

    my2 = gen(); bs[my2] = mk("sensing_mousey")
    set_ey = gen(); bs[set_ey] = mk("data_setvariableto",
        inputs={"VALUE": slot(my2)}, fields={"VARIABLE": ["폭발Y", V_EY]})
    bs[my2]["parent"] = set_ey

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["폭발", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    chain([(set_ex,bs[set_ex]),(set_ey,bs[set_ey]),(cclone,bs[cclone])])

    if_play = gen(); bs[if_play] = mk("control_if",
        inputs={"CONDITION":[2,cond_play], "SUBSTACK":[2, set_ex]})
    bs[cond_play]["parent"] = if_play
    bs[set_ex]["parent"] = if_play

    chain([(h2,bs[h2]),(if_play,bs[if_play])])

    # === also support stage click (sensing mouse down) — when key 'space' as backup fire ===
    h3 = gen(); bs[h3] = mk("event_whenkeypressed", top=True, x=300, y=240,
        fields={"KEY_OPTION": ["space", None]})
    state_v3 = vrep("게임상태", V_STATE)
    cond_play3 = cmp_op("operator_equals", state_v3, 1)

    mx3 = gen(); bs[mx3] = mk("sensing_mousex")
    set_ex3 = gen(); bs[set_ex3] = mk("data_setvariableto",
        inputs={"VALUE": slot(mx3)}, fields={"VARIABLE": ["폭발X", V_EX]})
    bs[mx3]["parent"] = set_ex3
    my3 = gen(); bs[my3] = mk("sensing_mousey")
    set_ey3 = gen(); bs[set_ey3] = mk("data_setvariableto",
        inputs={"VALUE": slot(my3)}, fields={"VARIABLE": ["폭발Y", V_EY]})
    bs[my3]["parent"] = set_ey3
    cmenu3 = gen(); bs[cmenu3] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["폭발", None]}, shadow=True)
    cclone3 = gen(); bs[cclone3] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu3]})
    bs[cmenu3]["parent"] = cclone3

    chain([(set_ex3,bs[set_ex3]),(set_ey3,bs[set_ey3]),(cclone3,bs[cclone3])])

    if_play3 = gen(); bs[if_play3] = mk("control_if",
        inputs={"CONDITION":[2,cond_play3], "SUBSTACK":[2,set_ex3]})
    bs[cond_play3]["parent"] = if_play3
    bs[set_ex3]["parent"] = if_play3

    chain([(h3,bs[h3]),(if_play3,bs[if_play3])])

    return bs

# ==============================================================
#  EXPLOSION (폭발) blocks
# ==============================================================
def build_explosion_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # === when flag clicked: hide original ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)

    ex_v = vrep("폭발X", V_EX); ey_v = vrep("폭발Y", V_EY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(ex_v), "Y": slot(ey_v)})
    bs[ex_v]["parent"] = g; bs[ey_v]["parent"] = g

    sz0 = gen(); bs[sz0] = mk("looks_setsizeto", inputs={"SIZE": num(20)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")

    # play pop with high pitch
    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(80)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd

    # expand: repeat 12 (change size by 14, wait 0.02)
    cs_up = gen(); bs[cs_up] = mk("looks_changesizeby", inputs={"CHANGE": num(14)})
    w_up = gen(); bs[w_up] = mk("control_wait", inputs={"DURATION": num(0.025)})
    chain([(cs_up,bs[cs_up]),(w_up,bs[w_up])])
    rep_up = gen(); bs[rep_up] = mk("control_repeat",
        inputs={"TIMES": num(12), "SUBSTACK":[2, cs_up]})
    bs[cs_up]["parent"] = rep_up

    # contract: repeat 10 (change size by -16, wait 0.02)
    cs_dn = gen(); bs[cs_dn] = mk("looks_changesizeby", inputs={"CHANGE": num(-16)})
    w_dn = gen(); bs[w_dn] = mk("control_wait", inputs={"DURATION": num(0.025)})
    chain([(cs_dn,bs[cs_dn]),(w_dn,bs[w_dn])])
    rep_dn = gen(); bs[rep_dn] = mk("control_repeat",
        inputs={"TIMES": num(10), "SUBSTACK":[2, cs_dn]})
    bs[cs_dn]["parent"] = rep_dn

    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch,bs[ch]),(g,bs[g]),(sz0,bs[sz0]),(front,bs[front]),(show,bs[show]),
           (pitch,bs[pitch]),(snd,bs[snd]),(rep_up,bs[rep_up]),(rep_dn,bs[rep_dn]),
           (hi2,bs[hi2]),(delc,bs[delc])])

    return bs

# ==============================================================
#  ENEMY MISSILE (적미사일) blocks
# ==============================================================
def build_missile_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide original + size ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    # === on 적생성: spawn 라운드미사일수 clones with spacing ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]})

    # body of repeat: create clone of myself, wait random 0.4..1.2 / 적속도
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    rand_t = op("operator_random", 0.5, 1.3, key1="FROM", key2="TO")
    spd_v = vrep("적속도", V_SPEED)
    delay = op("operator_divide", rand_t, spd_v)
    wt_sp = gen(); bs[wt_sp] = mk("control_wait", inputs={"DURATION": slot(delay)})
    bs[delay]["parent"] = wt_sp

    chain([(cclone,bs[cclone]),(wt_sp,bs[wt_sp])])

    tot_v = vrep("라운드미사일수", V_TOTAL)
    rep_sp = gen(); bs[rep_sp] = mk("control_repeat",
        inputs={"TIMES": slot(tot_v), "SUBSTACK":[2, cclone]})
    bs[tot_v]["parent"] = rep_sp
    bs[cclone]["parent"] = rep_sp

    chain([(h2,bs[h2]),(rep_sp,bs[rep_sp])])

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)

    # start X = random -200..200, fixed start Y = 175
    sx_rand = op("operator_random", -200, 200, key1="FROM", key2="TO")
    set_sx = gen(); bs[set_sx] = mk("data_setvariableto",
        inputs={"VALUE": slot(sx_rand)}, fields={"VARIABLE": ["미사일시작X", V_SX0]})
    bs[sx_rand]["parent"] = set_sx

    # 목표X = pick random of {-140, 0, 140} via 3-branch random
    # Simpler: 목표X = (random 1..3 - 2) * 140  → yields {-140, 0, 140}
    rand3 = op("operator_random", 1, 3, key1="FROM", key2="TO")
    sub2 = op("operator_subtract", rand3, 2)
    mul140 = op("operator_multiply", sub2, 140)
    set_tx = gen(); bs[set_tx] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul140)}, fields={"VARIABLE": ["목표X", V_TX]})
    bs[mul140]["parent"] = set_tx

    # goto (sx, 175)
    sx_rep = vrep("미사일시작X", V_SX0)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(sx_rep), "Y": num(175)})
    bs[sx_rep]["parent"] = g_init

    # dx = (목표X - 미사일시작X) / 80
    tx_v = vrep("목표X", V_TX); sx_v2 = vrep("미사일시작X", V_SX0)
    sub_x = op("operator_subtract", tx_v, sx_v2)
    div_dx = op("operator_divide", sub_x, 80)
    set_dx = gen(); bs[set_dx] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_dx)}, fields={"VARIABLE": ["dx", V_DX]})
    bs[div_dx]["parent"] = set_dx

    # dy = (-140 - 175) / 80 = -3.9375 — but multiply by 적속도 to ramp speed
    # base dy = -3.9
    spd_v2 = vrep("적속도", V_SPEED)
    base_dy = op("operator_multiply", -2.6, spd_v2)
    set_dy = gen(); bs[set_dy] = mk("data_setvariableto",
        inputs={"VALUE": slot(base_dy)}, fields={"VARIABLE": ["dy", V_DY]})
    bs[base_dy]["parent"] = set_dy

    # point in direction (so missile graphic tilts toward city)
    # direction = atan2(dx, -dy) — Scratch lacks atan2, use sensing_of helper? Skip rotation, use rotationStyle don't rotate.

    show = gen(); bs[show] = mk("looks_show")

    # loop: repeat until 게임상태=0 OR touching 폭발 OR y<-145
    # body: change x by dx, change y by dy, wait 0.04
    dx_v = vrep("dx", V_DX); dy_v = vrep("dy", V_DY)
    chx = gen(); bs[chx] = mk("motion_changexby",
        inputs={"DX": slot(dx_v)})
    bs[dx_v]["parent"] = chx
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(dy_v)})
    bs[dy_v]["parent"] = chy
    wt_iter = gen(); bs[wt_iter] = mk("control_wait", inputs={"DURATION": num(0.04)})
    chain([(chx,bs[chx]),(chy,bs[chy]),(wt_iter,bs[wt_iter])])

    # exit condition: state=0 OR touching 폭발 OR yposition < -145
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)
    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["폭발", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm_b]})
    bs[tm_b]["parent"] = tc_b
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_low = cmp_op("operator_lt", yp, -140)
    bs[yp]["parent"] = cond_low
    cond_or1 = bool_op("operator_or", cond_over, tc_b)
    cond_or2 = bool_op("operator_or", cond_or1, cond_low)

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_or2], "SUBSTACK":[2, chx]})
    bs[cond_or2]["parent"] = rep_until
    bs[chx]["parent"] = rep_until

    # after loop:
    # if touching 폭발 → score +25, 격추수 +1, sound, if 격추수 = 라운드미사일수 → broadcast 다음라운드
    tm2 = gen(); bs[tm2] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["폭발", None]}, shadow=True)
    tc2 = gen(); bs[tc2] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm2]})
    bs[tm2]["parent"] = tc2

    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(25)}, fields={"VARIABLE": ["점수", V_SCORE]})
    inc_kills = gen(); bs[inc_kills] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["격추수", V_KILLS]})

    pitch_hi = gen(); bs[pitch_hi] = mk("sound_seteffectto",
        inputs={"VALUE": num(180)}, fields={"EFFECT":["PITCH", None]})
    snm_k = gen(); bs[snm_k] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_k = gen(); bs[snd_k] = mk("sound_play", inputs={"SOUND_MENU":[1, snm_k]})
    bs[snm_k]["parent"] = snd_k

    # if 격추수 >= 라운드미사일수 → broadcast 다음라운드
    kv = vrep("격추수", V_KILLS); tv = vrep("라운드미사일수", V_TOTAL)
    cond_done = cmp_op("operator_equals", kv, tv)
    bm_next = gen(); bs[bm_next] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]}, shadow=True)
    bc_next = gen(); bs[bc_next] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_next]})
    bs[bm_next]["parent"] = bc_next
    if_done = gen(); bs[if_done] = mk("control_if",
        inputs={"CONDITION":[2, cond_done], "SUBSTACK":[2, bc_next]})
    bs[cond_done]["parent"] = if_done
    bs[bc_next]["parent"] = if_done

    chain([(inc_score,bs[inc_score]),(inc_kills,bs[inc_kills]),
           (pitch_hi,bs[pitch_hi]),(snd_k,bs[snd_k]),(if_done,bs[if_done])])
    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION":[2, tc2], "SUBSTACK":[2, inc_score]})
    bs[tc2]["parent"] = if_hit
    bs[inc_score]["parent"] = if_hit

    # if y<-140 AND not touched 폭발 → hit ground: 라이프 -1, low pop, if 라이프<=0 → state=0
    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    cond_low2 = cmp_op("operator_lt", yp2, -140)
    bs[yp2]["parent"] = cond_low2

    dec_life = gen(); bs[dec_life] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["라이프", V_LIFE]})
    pitch_lo = gen(); bs[pitch_lo] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT":["PITCH", None]})
    snm_g = gen(); bs[snm_g] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_g = gen(); bs[snd_g] = mk("sound_play", inputs={"SOUND_MENU":[1, snm_g]})
    bs[snm_g]["parent"] = snd_g

    life_v = vrep("라이프", V_LIFE)
    cond_dead = cmp_op("operator_lt", life_v, 1)
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION":[2, cond_dead], "SUBSTACK":[2, set_state0]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state0]["parent"] = if_dead

    chain([(dec_life,bs[dec_life]),(pitch_lo,bs[pitch_lo]),(snd_g,bs[snd_g]),(if_dead,bs[if_dead])])
    if_ground = gen(); bs[if_ground] = mk("control_if",
        inputs={"CONDITION":[2, cond_low2], "SUBSTACK":[2, dec_life]})
    bs[cond_low2]["parent"] = if_ground
    bs[dec_life]["parent"] = if_ground

    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch,bs[ch]),(set_sx,bs[set_sx]),(set_tx,bs[set_tx]),(g_init,bs[g_init]),
           (set_dx,bs[set_dx]),(set_dy,bs[set_dy]),(show,bs[show]),
           (rep_until,bs[rep_until]),(if_hit,bs[if_hit]),(if_ground,bs[if_ground]),(delc,bs[delc])])

    return bs

# ==============================================================
#  CITY (도시) blocks
# ==============================================================
def build_city_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # === when flag clicked: hide original, size, costume intact ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(95)})
    cmenu = gen(); bs[cmenu] = mk("looks_costume",
        fields={"COSTUME": ["intact", None]}, shadow=True)
    swc = gen(); bs[swc] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cmenu]})
    bs[cmenu]["parent"] = swc
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz]),(swc,bs[swc])])

    # === on 도시생성: spawn 3 clones with 도시번호 1/2/3 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["도시생성", BR_CITY]})

    # for n in 1,2,3: set 도시번호 = n, create clone
    spawn_chain = []
    for n in (1, 2, 3):
        s_n = gen(); bs[s_n] = mk("data_setvariableto",
            inputs={"VALUE": num(n)}, fields={"VARIABLE": ["도시번호", V_CITYN]})
        cm = gen(); bs[cm] = mk("control_create_clone_of_menu",
            fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
        cc = gen(); bs[cc] = mk("control_create_clone_of",
            inputs={"CLONE_OPTION":[1, cm]})
        bs[cm]["parent"] = cc
        wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.05)})
        spawn_chain.extend([(s_n,bs[s_n]),(cc,bs[cc]),(wt,bs[wt])])

    chain([(h2, bs[h2])] + spawn_chain)

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)

    # x = (도시번호 - 2) * 140  → -140, 0, 140
    cn_v = vrep("도시번호", V_CITYN)
    sub2 = op("operator_subtract", cn_v, 2)
    mul140 = op("operator_multiply", sub2, 140)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(mul140), "Y": num(-150)})
    bs[mul140]["parent"] = g

    cmenu2 = gen(); bs[cmenu2] = mk("looks_costume",
        fields={"COSTUME": ["intact", None]}, shadow=True)
    swc2 = gen(); bs[swc2] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cmenu2]})
    bs[cmenu2]["parent"] = swc2

    show = gen(); bs[show] = mk("looks_show")

    # forever (while state=1): if touching 적미사일 → costume ruined + wait until state=0
    # Simpler: repeat until state=0 (or until I'm ruined)
    # Body: if touching 적미사일 and costume = intact → switch to ruined.
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["적미사일", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc

    # costume name reporter to check if already ruined
    cname = gen(); bs[cname] = mk("looks_costumenumbername",
        fields={"NUMBER_NAME": ["name", None]})
    cname_eq = gen(); bs[cname_eq] = mk("operator_equals",
        inputs={"OPERAND1": slot(cname), "OPERAND2": text_lit("ruined")})
    bs[cname]["parent"] = cname_eq
    not_ruined = gen(); bs[not_ruined] = mk("operator_not",
        inputs={"OPERAND": [2, cname_eq]})
    bs[cname_eq]["parent"] = not_ruined
    # combined: touching AND not ruined
    guard = gen(); bs[guard] = mk("operator_and",
        inputs={"OPERAND1": [2, tc], "OPERAND2": [2, not_ruined]})
    bs[tc]["parent"] = guard
    bs[not_ruined]["parent"] = guard

    cmenu3 = gen(); bs[cmenu3] = mk("looks_costume",
        fields={"COSTUME": ["ruined", None]}, shadow=True)
    swc3 = gen(); bs[swc3] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cmenu3]})
    bs[cmenu3]["parent"] = swc3
    chain([(swc3, bs[swc3])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION":[2, guard], "SUBSTACK":[2, swc3]})
    bs[guard]["parent"] = if_hit
    bs[swc3]["parent"] = if_hit

    wt_iter = gen(); bs[wt_iter] = mk("control_wait", inputs={"DURATION": num(0.08)})

    chain([(if_hit,bs[if_hit]),(wt_iter,bs[wt_iter])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_over], "SUBSTACK":[2, if_hit]})
    bs[cond_over]["parent"] = rep_until
    bs[if_hit]["parent"] = rep_until

    chain([(ch,bs[ch]),(g,bs[g]),(swc2,bs[swc2]),(show,bs[show]),(rep_until,bs[rep_until])])

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

    # Save SVG assets
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)
    ch_md5 = md5_bytes(CROSSHAIR_SVG.encode("utf-8"))
    with open(f"{WORK}/{ch_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CROSSHAIR_SVG)
    ex_md5 = md5_bytes(EXPLOSION_SVG.encode("utf-8"))
    with open(f"{WORK}/{ex_md5}.svg", "w", encoding="utf-8") as f:
        f.write(EXPLOSION_SVG)
    em_md5 = md5_bytes(ENEMY_MISSILE_SVG.encode("utf-8"))
    with open(f"{WORK}/{em_md5}.svg", "w", encoding="utf-8") as f:
        f.write(ENEMY_MISSILE_SVG)
    ci_md5 = md5_bytes(CITY_INTACT_SVG.encode("utf-8"))
    with open(f"{WORK}/{ci_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CITY_INTACT_SVG)
    cr_md5 = md5_bytes(CITY_RUINED_SVG.encode("utf-8"))
    with open(f"{WORK}/{cr_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CITY_RUINED_SVG)
    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    # Pop sound
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    crosshair_blocks= build_crosshair_blocks()
    explosion_blocks= build_explosion_blocks()
    missile_blocks  = build_missile_blocks()
    city_blocks     = build_city_blocks()
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
            V_KILLS: ["격추수", 0],
            V_TOTAL: ["라운드미사일수", 6],
            V_SPEED: ["적속도", 1.6],
            V_EX:    ["폭발X", 0],
            V_EY:    ["폭발Y", 0],
            V_TX:    ["목표X", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "적생성",
            BR_NEXT:  "다음라운드",
            BR_CITY:  "도시생성",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "밤하늘", "dataFormat": "svg",
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
        "x": 0, "y": 0, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    explosion = {
        "isStage": False, "name": "폭발",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": explosion_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "boom", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ex_md5, "md5ext": f"{ex_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 20, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    missile = {
        "isStage": False, "name": "적미사일",
        "variables": {
            V_SX0: ["미사일시작X", 0],
            V_DX:  ["dx", 0],
            V_DY:  ["dy", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": missile_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "미사일", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": em_md5, "md5ext": f"{em_md5}.svg",
            "rotationCenterX": 10, "rotationCenterY": 25
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 175, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    city = {
        "isStage": False, "name": "도시",
        "variables": {V_CITYN: ["도시번호", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": city_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "intact", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ci_md5, "md5ext": f"{ci_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 20},
            {"name": "ruined", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": cr_md5, "md5ext": f"{cr_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 20},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": -150, "size": 95, "direction": 90,
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
        {"id": V_LIFE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라이프"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 5, "isDiscrete": True},
        {"id": V_WAVE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, crosshair, explosion, missile, city, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "missile-command-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)  # validate
    print(f"✓ wrote {OUTPUT}")

if __name__ == "__main__":
    main()
