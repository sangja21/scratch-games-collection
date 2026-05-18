#!/usr/bin/env python3
"""Duck Hunt — Nintendo 1984 classic clone (mouse aim + click shoot + limited ammo)."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "오리_사냥.sb3")

# -------- Background: sky gradient + clouds + grass/trees silhouette --------
random.seed(11)
cloud_paths = []
for cx, cy, w, h in [(110, 60, 50, 18), (340, 90, 60, 22), (220, 130, 45, 16)]:
    cloud_paths.append(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{w}" ry="{h}" fill="#FFFFFF" opacity="0.85"/>'
    )
    cloud_paths.append(
        f'<ellipse cx="{cx-w*0.4:.0f}" cy="{cy+h*0.3:.0f}" rx="{w*0.55:.0f}" ry="{h*0.7:.0f}" fill="#FFFFFF" opacity="0.75"/>'
    )
    cloud_paths.append(
        f'<ellipse cx="{cx+w*0.45:.0f}" cy="{cy+h*0.3:.0f}" rx="{w*0.5:.0f}" ry="{h*0.65:.0f}" fill="#FFFFFF" opacity="0.75"/>'
    )
CLOUDS = "\n    ".join(cloud_paths)

# Tree silhouettes along the bottom
trees = []
for tx in [30, 90, 160, 240, 310, 380, 440]:
    h = random.randint(38, 70)
    w_tree = random.randint(24, 38)
    trees.append(
        f'<path d="M {tx} 280 '
        f'C {tx-w_tree} {280-h*0.4:.0f}, {tx-w_tree*0.6:.0f} {280-h:.0f}, {tx} {280-h:.0f} '
        f'C {tx+w_tree*0.6:.0f} {280-h:.0f}, {tx+w_tree} {280-h*0.4:.0f}, {tx+w_tree} 280 Z" '
        f'fill="#1B5E20" opacity="0.95"/>'
    )
TREES = "\n    ".join(trees)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#4FC3F7"/>
      <stop offset="60%" stop-color="#81D4FA"/>
      <stop offset="100%" stop-color="#FFE0B2"/>
    </linearGradient>
    <linearGradient id="grass" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#388E3C"/>
      <stop offset="100%" stop-color="#1B5E20"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <circle cx="60" cy="60" r="25" fill="#FFEB3B" opacity="0.85"/>
  <circle cx="60" cy="60" r="35" fill="#FFEB3B" opacity="0.25"/>
  <g>
    {CLOUDS}
  </g>
  <rect x="0" y="280" width="480" height="80" fill="url(#grass)"/>
  <g>
    {TREES}
  </g>
  <g stroke="#0D3F12" stroke-width="1.2" fill="none">
    <path d="M 20 330 Q 25 315 30 330"/>
    <path d="M 70 340 Q 75 325 80 340"/>
    <path d="M 130 332 Q 135 318 140 332"/>
    <path d="M 200 345 Q 205 330 210 345"/>
    <path d="M 280 335 Q 285 320 290 335"/>
    <path d="M 350 342 Q 355 327 360 342"/>
    <path d="M 420 333 Q 425 318 430 333"/>
  </g>
</svg>"""

# -------- Crosshair --------
CROSSHAIR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="14" fill="none" stroke="#FF1744" stroke-width="2"/>
  <line x1="20" y1="2"  x2="20" y2="14" stroke="#FF1744" stroke-width="2.5"/>
  <line x1="20" y1="26" x2="20" y2="38" stroke="#FF1744" stroke-width="2.5"/>
  <line x1="2"  y1="20" x2="14" y2="20" stroke="#FF1744" stroke-width="2.5"/>
  <line x1="26" y1="20" x2="38" y2="20" stroke="#FF1744" stroke-width="2.5"/>
  <circle cx="20" cy="20" r="1.5" fill="#FF1744"/>
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

# -------- Duck flying frame 1 (wings up) --------
DUCK_FLY1_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="50" viewBox="0 0 60 50">
  <ellipse cx="32" cy="28" rx="18" ry="11" fill="#5D4037" stroke="#3E2723" stroke-width="1.2"/>
  <ellipse cx="48" cy="22" rx="9" ry="8" fill="#6D4C41" stroke="#3E2723" stroke-width="1.2"/>
  <polygon points="56,21 60,19 60,24 56,24" fill="#FFB300" stroke="#FF6F00" stroke-width="0.8"/>
  <circle cx="50" cy="20" r="1.5" fill="#000000"/>
  <circle cx="50.5" cy="19.5" r="0.5" fill="#FFFFFF"/>
  <path d="M 22 22 Q 14 4 8 12 Q 12 18 20 26 Z" fill="#795548" stroke="#3E2723" stroke-width="1"/>
  <path d="M 28 22 Q 22 6 18 12 Q 22 18 28 26 Z" fill="#8D6E63" stroke="#3E2723" stroke-width="1"/>
  <polygon points="18,35 14,42 22,38" fill="#FFB300" stroke="#FF6F00" stroke-width="0.8"/>
  <polygon points="28,35 24,42 32,38" fill="#FFB300" stroke="#FF6F00" stroke-width="0.8"/>
  <ellipse cx="38" cy="33" rx="2" ry="1.5" fill="#3E2723" opacity="0.5"/>
</svg>"""

# -------- Duck flying frame 2 (wings down) --------
DUCK_FLY2_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="50" viewBox="0 0 60 50">
  <ellipse cx="32" cy="28" rx="18" ry="11" fill="#5D4037" stroke="#3E2723" stroke-width="1.2"/>
  <ellipse cx="48" cy="22" rx="9" ry="8" fill="#6D4C41" stroke="#3E2723" stroke-width="1.2"/>
  <polygon points="56,21 60,19 60,24 56,24" fill="#FFB300" stroke="#FF6F00" stroke-width="0.8"/>
  <circle cx="50" cy="20" r="1.5" fill="#000000"/>
  <circle cx="50.5" cy="19.5" r="0.5" fill="#FFFFFF"/>
  <path d="M 22 30 Q 14 46 8 40 Q 12 34 20 30 Z" fill="#795548" stroke="#3E2723" stroke-width="1"/>
  <path d="M 28 30 Q 22 46 18 40 Q 22 34 28 30 Z" fill="#8D6E63" stroke="#3E2723" stroke-width="1"/>
  <polygon points="18,35 14,42 22,38" fill="#FFB300" stroke="#FF6F00" stroke-width="0.8"/>
  <polygon points="28,35 24,42 32,38" fill="#FFB300" stroke="#FF6F00" stroke-width="0.8"/>
  <ellipse cx="38" cy="33" rx="2" ry="1.5" fill="#3E2723" opacity="0.5"/>
</svg>"""

# -------- Duck hit (X-eye, feathers scattered) --------
DUCK_HIT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="50" viewBox="0 0 60 50">
  <ellipse cx="32" cy="32" rx="17" ry="10" fill="#5D4037" stroke="#3E2723" stroke-width="1.2"/>
  <ellipse cx="46" cy="26" rx="9" ry="8" fill="#6D4C41" stroke="#3E2723" stroke-width="1.2"/>
  <polygon points="54,25 58,23 58,28 54,28" fill="#FFB300" stroke="#FF6F00" stroke-width="0.8"/>
  <line x1="46" y1="22" x2="50" y2="26" stroke="#000000" stroke-width="1.8"/>
  <line x1="50" y1="22" x2="46" y2="26" stroke="#000000" stroke-width="1.8"/>
  <path d="M 22 32 L 14 30 L 18 36 L 12 38" stroke="#3E2723" stroke-width="1.2" fill="none"/>
  <circle cx="8"  cy="20" r="2" fill="#8D6E63" opacity="0.75"/>
  <circle cx="12" cy="12" r="1.5" fill="#8D6E63" opacity="0.75"/>
  <circle cx="20" cy="8"  r="2.5" fill="#8D6E63" opacity="0.75"/>
  <circle cx="50" cy="44" r="2" fill="#8D6E63" opacity="0.65"/>
  <text x="30" y="6" text-anchor="middle" fill="#FFEB3B" font-family="Arial" font-size="9" font-weight="bold">!</text>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.88"
        stroke="#FF1744" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#FF1744" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">오리가 모두 도망갔어요</text>
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

# Variable / broadcast IDs (Stage-global)
V_SCORE = "varScore01"
V_LIFE  = "varLife02"
V_WAVE  = "varWave03"
V_STATE = "varState04"
V_KILLS = "varKills05"
V_TOTAL = "varTotal06"
V_SPEED = "varSpeed07"
V_AMMO  = "varAmmo08"
V_FX    = "varFX09"
V_FY    = "varFY10"
V_DUCKS = "varDuckS11"  # 오리상태: 0=비행, 1=맞음, 2=도망
V_DIR   = "varDir12"    # 1=오른쪽 진행, -1=왼쪽 진행
V_DONE  = "varDone13"   # 이번 라운드 처리완료 오리 수

BR_START = "brStart01"
BR_SPAWN = "brSpawn02"
BR_NEXT  = "brNext03"
BR_HIT   = "brHit04"

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
#  STAGE
# ==============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init + start ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = []
    for var_pair, val in [
        (("점수", V_SCORE), 0),
        (("라이프", V_LIFE), 3),
        (("라운드", V_WAVE), 1),
        (("게임상태", V_STATE), 1),
        (("잡은수", V_KILLS), 0),
        (("라운드오리수", V_TOTAL), 6),
        (("오리속도", V_SPEED), 2.4),
        (("탄약", V_AMMO), 3),
        (("라운드처리완료", V_DONE), 0),
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

    # === on 게임시작: broadcast 오리등장 (first duck) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=300,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["오리등장", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    chain([(h2, bs[h2]), (bc_sp, bs[bc_sp])])

    # === on 다음라운드: ramp difficulty, reset round-counters, then 오리등장 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=480,
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]})

    chg_wave = gen(); bs[chg_wave] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_WAVE]})

    # 오리속도 *= 1.15
    spd_v = vrep("오리속도", V_SPEED)
    mul_spd = op("operator_multiply", spd_v, 1.15)
    set_spd = gen(); bs[set_spd] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_spd)}, fields={"VARIABLE": ["오리속도", V_SPEED]})
    bs[mul_spd]["parent"] = set_spd

    chg_total = gen(); bs[chg_total] = mk("data_changevariableby",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["라운드오리수", V_TOTAL]})
    r_kills = gen(); bs[r_kills] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["잡은수", V_KILLS]})
    r_done = gen(); bs[r_done] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["라운드처리완료", V_DONE]})

    w2 = gen(); bs[w2] = mk("control_wait", inputs={"DURATION": num(1.5)})

    bm_sp2 = gen(); bs[bm_sp2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["오리등장", BR_SPAWN]}, shadow=True)
    bc_sp2 = gen(); bs[bc_sp2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp2]})
    bs[bm_sp2]["parent"] = bc_sp2

    chain([(h3, bs[h3]), (chg_wave, bs[chg_wave]), (set_spd, bs[set_spd]),
           (chg_total, bs[chg_total]), (r_kills, bs[r_kills]),
           (r_done, bs[r_done]), (w2, bs[w2]), (bc_sp2, bs[bc_sp2])])

    return bs

# ==============================================================
#  CROSSHAIR
# ==============================================================
def build_crosshair_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === flag: setup + follow mouse forever ===
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

    chain([(h, bs[h]), (sz, bs[sz]), (front, bs[front]), (show, bs[show]), (forever, bs[forever])])

    # === when sprite clicked: fire ===
    h2 = gen(); bs[h2] = mk("event_whenthisspriteclicked", top=True, x=300, y=20)

    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)
    ammo_v = vrep("탄약", V_AMMO)
    cond_have = cmp_op("operator_gt", ammo_v, 0)
    cond_both = bool_op("operator_and", cond_play, cond_have)

    # ammo -1
    dec_ammo = gen(); bs[dec_ammo] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["탄약", V_AMMO]})

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

    chain([(dec_ammo, bs[dec_ammo]), (set_fx, bs[set_fx]), (set_fy, bs[set_fy]),
           (cclone, bs[cclone]), (pitch, bs[pitch]), (snd, bs[snd])])

    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, cond_both], "SUBSTACK": [2, dec_ammo]})
    bs[cond_both]["parent"] = if_fire
    bs[dec_ammo]["parent"] = if_fire

    chain([(h2, bs[h2]), (if_fire, bs[if_fire])])

    return bs

# ==============================================================
#  FLASH (섬광)
# ==============================================================
def build_flash_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(65)})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz])])

    # === clone start ===
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

# ==============================================================
#  DUCK (오리) — single sprite, no cloning. One duck at a time.
# ==============================================================
def build_duck_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === flag: hide + size + costume ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    cm0 = gen(); bs[cm0] = mk("looks_costume",
        fields={"COSTUME": ["fly1", None]}, shadow=True)
    swc0 = gen(); bs[swc0] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm0]})
    bs[cm0]["parent"] = swc0
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (swc0, bs[swc0])])

    # === on 오리등장: setup + flight loop + resolve ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["오리등장", BR_SPAWN]})

    # 오리상태 = 0
    set_ds0 = gen(); bs[set_ds0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["오리상태", V_DUCKS]})

    # 탄약 = 3
    set_ammo3 = gen(); bs[set_ammo3] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["탄약", V_AMMO]})

    # 오리방향: random 1..2 -> 1 means +1, 2 means -1
    rand_d = op("operator_random", 1, 2, key1="FROM", key2="TO")
    sub_d = op("operator_subtract", rand_d, 1)
    # if (rand-1)=0 -> 1, else -1. Use: 1 - 2*(rand-1) -> 1 or -1
    mul_d = op("operator_multiply", sub_d, 2)
    final_d = op("operator_subtract", 1, mul_d)
    set_dir = gen(); bs[set_dir] = mk("data_setvariableto",
        inputs={"VALUE": slot(final_d)}, fields={"VARIABLE": ["오리방향", V_DIR]})
    bs[final_d]["parent"] = set_dir

    # start X = -220 * 오리방향  (going right starts left, going left starts right)
    dir_v = vrep("오리방향", V_DIR)
    start_x_calc = op("operator_multiply", dir_v, -220)
    # start Y = random 60..160
    start_y_calc = op("operator_random", 60, 160, key1="FROM", key2="TO")
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(start_x_calc), "Y": slot(start_y_calc)})
    bs[start_x_calc]["parent"] = g_init
    bs[start_y_calc]["parent"] = g_init

    # set rotation style left-right
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["left-right", None]})

    # point in direction: if 오리방향 = 1 -> 90, else -90
    dir_v2 = vrep("오리방향", V_DIR)
    dir_deg_calc = op("operator_multiply", dir_v2, 90)
    point_d = gen(); bs[point_d] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(dir_deg_calc)})
    bs[dir_deg_calc]["parent"] = point_d

    cm1 = gen(); bs[cm1] = mk("looks_costume",
        fields={"COSTUME": ["fly1", None]}, shadow=True)
    swc1 = gen(); bs[swc1] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm1]})
    bs[cm1]["parent"] = swc1

    show = gen(); bs[show] = mk("looks_show")

    # ---- flight loop body ----
    # next costume (wing flap)
    nc = gen(); bs[nc] = mk("looks_nextcostume")

    # change x by 오리속도 * 오리방향
    spd_v = vrep("오리속도", V_SPEED); dir_v3 = vrep("오리방향", V_DIR)
    dx_calc = op("operator_multiply", spd_v, dir_v3)
    chx = gen(); bs[chx] = mk("motion_changexby",
        inputs={"DX": slot(dx_calc)})
    bs[dx_calc]["parent"] = chx

    # change y by random -3..3 (gentle bobbing)
    dy_rand = op("operator_random", -3, 3, key1="FROM", key2="TO")
    chy = gen(); bs[chy] = mk("motion_changeyby",
        inputs={"DY": slot(dy_rand)})
    bs[dy_rand]["parent"] = chy

    # if y > 170 → set y to 170 (clamp top)
    yp_top = gen(); bs[yp_top] = mk("motion_yposition")
    cond_high = cmp_op("operator_gt", yp_top, 170)
    sety_top = gen(); bs[sety_top] = mk("motion_setyposition", inputs={"Y": num(170)})
    if_top = gen(); bs[if_top] = mk("control_if",
        inputs={"CONDITION": [2, cond_high], "SUBSTACK": [2, sety_top]})
    bs[cond_high]["parent"] = if_top
    bs[sety_top]["parent"] = if_top

    # if y < 30 → set y to 30 (clamp above grass)
    yp_bot = gen(); bs[yp_bot] = mk("motion_yposition")
    cond_low = cmp_op("operator_lt", yp_bot, 30)
    sety_bot = gen(); bs[sety_bot] = mk("motion_setyposition", inputs={"Y": num(30)})
    if_bot = gen(); bs[if_bot] = mk("control_if",
        inputs={"CONDITION": [2, cond_low], "SUBSTACK": [2, sety_bot]})
    bs[cond_low]["parent"] = if_bot
    bs[sety_bot]["parent"] = if_bot

    # if touching 섬광 → 오리상태=1, score+100, kills+1, broadcast 명중, costume=hit
    tm_h = gen(); bs[tm_h] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["섬광", None]}, shadow=True)
    tc_h = gen(); bs[tc_h] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_h]})
    bs[tm_h]["parent"] = tc_h

    set_ds1 = gen(); bs[set_ds1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["오리상태", V_DUCKS]})
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(100)}, fields={"VARIABLE": ["점수", V_SCORE]})
    inc_kills = gen(); bs[inc_kills] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["잡은수", V_KILLS]})

    pitch_hit = gen(); bs[pitch_hit] = mk("sound_seteffectto",
        inputs={"VALUE": num(80)}, fields={"EFFECT": ["PITCH", None]})
    snm_hit = gen(); bs[snm_hit] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_hit = gen(); bs[snd_hit] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_hit]})
    bs[snm_hit]["parent"] = snd_hit

    cm_hit = gen(); bs[cm_hit] = mk("looks_costume",
        fields={"COSTUME": ["hit", None]}, shadow=True)
    swc_hit = gen(); bs[swc_hit] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_hit]})
    bs[cm_hit]["parent"] = swc_hit

    chain([(set_ds1, bs[set_ds1]), (inc_score, bs[inc_score]),
           (inc_kills, bs[inc_kills]), (pitch_hit, bs[pitch_hit]),
           (snd_hit, bs[snd_hit]), (swc_hit, bs[swc_hit])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION": [2, tc_h], "SUBSTACK": [2, set_ds1]})
    bs[tc_h]["parent"] = if_hit
    bs[set_ds1]["parent"] = if_hit

    # if x > 240 OR x < -240 → 오리상태 = 2 (도망)
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    cond_far_r = cmp_op("operator_gt", xp1, 240)
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    cond_far_l = cmp_op("operator_lt", xp2, -240)
    cond_escape = bool_op("operator_or", cond_far_r, cond_far_l)

    set_ds2 = gen(); bs[set_ds2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["오리상태", V_DUCKS]})
    if_esc = gen(); bs[if_esc] = mk("control_if",
        inputs={"CONDITION": [2, cond_escape], "SUBSTACK": [2, set_ds2]})
    bs[cond_escape]["parent"] = if_esc
    bs[set_ds2]["parent"] = if_esc

    wt_iter = gen(); bs[wt_iter] = mk("control_wait", inputs={"DURATION": num(0.05)})

    chain([(nc, bs[nc]), (chx, bs[chx]), (chy, bs[chy]),
           (if_top, bs[if_top]), (if_bot, bs[if_bot]),
           (if_hit, bs[if_hit]), (if_esc, bs[if_esc]),
           (wt_iter, bs[wt_iter])])

    # repeat until 오리상태 ≠ 0
    ds_v = vrep("오리상태", V_DUCKS)
    cond_done = cmp_op("operator_gt", ds_v, 0)
    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_done], "SUBSTACK": [2, nc]})
    bs[cond_done]["parent"] = rep_until
    bs[nc]["parent"] = rep_until

    # ---- post-loop resolution ----
    # if 오리상태 = 1: stay hit costume + fall animation
    ds_v2 = vrep("오리상태", V_DUCKS)
    cond_was_hit = cmp_op("operator_equals", ds_v2, 1)

    wt_hit_pause = gen(); bs[wt_hit_pause] = mk("control_wait", inputs={"DURATION": num(0.25)})
    # fall: repeat 15 ( change y by -10, wait 0.025 )
    cy_fall = gen(); bs[cy_fall] = mk("motion_changeyby", inputs={"DY": num(-10)})
    w_fall = gen(); bs[w_fall] = mk("control_wait", inputs={"DURATION": num(0.025)})
    chain([(cy_fall, bs[cy_fall]), (w_fall, bs[w_fall])])
    rep_fall = gen(); bs[rep_fall] = mk("control_repeat",
        inputs={"TIMES": num(15), "SUBSTACK": [2, cy_fall]})
    bs[cy_fall]["parent"] = rep_fall

    chain([(wt_hit_pause, bs[wt_hit_pause]), (rep_fall, bs[rep_fall])])

    if_was_hit = gen(); bs[if_was_hit] = mk("control_if",
        inputs={"CONDITION": [2, cond_was_hit], "SUBSTACK": [2, wt_hit_pause]})
    bs[cond_was_hit]["parent"] = if_was_hit
    bs[wt_hit_pause]["parent"] = if_was_hit

    # if 오리상태 = 2: 라이프 -1 + low pop sound
    ds_v3 = vrep("오리상태", V_DUCKS)
    cond_was_esc = cmp_op("operator_equals", ds_v3, 2)
    dec_life = gen(); bs[dec_life] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["라이프", V_LIFE]})
    pitch_lo = gen(); bs[pitch_lo] = mk("sound_seteffectto",
        inputs={"VALUE": num(-200)}, fields={"EFFECT": ["PITCH", None]})
    snm_lo = gen(); bs[snm_lo] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_lo = gen(); bs[snd_lo] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_lo]})
    bs[snm_lo]["parent"] = snd_lo
    chain([(dec_life, bs[dec_life]), (pitch_lo, bs[pitch_lo]), (snd_lo, bs[snd_lo])])

    if_was_esc = gen(); bs[if_was_esc] = mk("control_if",
        inputs={"CONDITION": [2, cond_was_esc], "SUBSTACK": [2, dec_life]})
    bs[cond_was_esc]["parent"] = if_was_esc
    bs[dec_life]["parent"] = if_was_esc

    # hide duck
    hide_after = gen(); bs[hide_after] = mk("looks_hide")

    # 라운드처리완료 += 1
    inc_done = gen(); bs[inc_done] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드처리완료", V_DONE]})

    # if 라이프 <= 0: 게임상태 = 0
    life_v = vrep("라이프", V_LIFE)
    cond_dead = cmp_op("operator_lt", life_v, 1)
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, set_state0]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state0]["parent"] = if_dead

    # if 게임상태 = 1: branch on 라운드처리완료 >= 라운드오리수
    state_v = vrep("게임상태", V_STATE)
    cond_alive = cmp_op("operator_equals", state_v, 1)

    done_v = vrep("라운드처리완료", V_DONE)
    total_v = vrep("라운드오리수", V_TOTAL)
    # 라운드처리완료 >= 라운드오리수  → use NOT(<) for >=
    cond_lt_total = cmp_op("operator_lt", done_v, total_v)
    not_lt = gen(); bs[not_lt] = mk("operator_not",
        inputs={"OPERAND": [2, cond_lt_total]})
    bs[cond_lt_total]["parent"] = not_lt

    # then-branch: broadcast 다음라운드
    bm_next = gen(); bs[bm_next] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]}, shadow=True)
    bc_next = gen(); bs[bc_next] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_next]})
    bs[bm_next]["parent"] = bc_next

    # else-branch: wait 0.7 → broadcast 오리등장
    wt_next = gen(); bs[wt_next] = mk("control_wait", inputs={"DURATION": num(0.7)})
    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["오리등장", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp
    chain([(wt_next, bs[wt_next]), (bc_sp, bs[bc_sp])])

    if_else_round = gen(); bs[if_else_round] = mk("control_if_else",
        inputs={"CONDITION": [2, not_lt],
                "SUBSTACK": [2, bc_next], "SUBSTACK2": [2, wt_next]})
    bs[not_lt]["parent"] = if_else_round
    bs[bc_next]["parent"] = if_else_round
    bs[wt_next]["parent"] = if_else_round

    # wrap in "if 게임상태=1" so we don't spawn next duck after game over
    if_alive = gen(); bs[if_alive] = mk("control_if",
        inputs={"CONDITION": [2, cond_alive], "SUBSTACK": [2, if_else_round]})
    bs[cond_alive]["parent"] = if_alive
    bs[if_else_round]["parent"] = if_alive

    # Chain on duck-spawn handler
    chain([(h2, bs[h2]), (set_ds0, bs[set_ds0]), (set_ammo3, bs[set_ammo3]),
           (set_dir, bs[set_dir]), (g_init, bs[g_init]), (rs, bs[rs]),
           (point_d, bs[point_d]), (swc1, bs[swc1]), (show, bs[show]),
           (rep_until, bs[rep_until]),
           (if_was_hit, bs[if_was_hit]), (if_was_esc, bs[if_was_esc]),
           (hide_after, bs[hide_after]), (inc_done, bs[inc_done]),
           (if_dead, bs[if_dead]), (if_alive, bs[if_alive])])

    return bs

# ==============================================================
#  GAME OVER banner
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
        inputs={"CONDITION": [2, cond_one]})
    bs[cond_one]["parent"] = wait_start

    state_v2 = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", state_v2, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_zero]})
    bs[cond_zero]["parent"] = wait_over

    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (wait_start, bs[wait_start]), (wait_over, bs[wait_over]), (show, bs[show])])
    return bs

# ==============================================================
#  ASSEMBLE
# ==============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f: f.write(BG_SVG)
    ch_md5 = md5_bytes(CROSSHAIR_SVG.encode("utf-8"))
    with open(f"{WORK}/{ch_md5}.svg", "w", encoding="utf-8") as f: f.write(CROSSHAIR_SVG)
    fl_md5 = md5_bytes(FLASH_SVG.encode("utf-8"))
    with open(f"{WORK}/{fl_md5}.svg", "w", encoding="utf-8") as f: f.write(FLASH_SVG)
    d1_md5 = md5_bytes(DUCK_FLY1_SVG.encode("utf-8"))
    with open(f"{WORK}/{d1_md5}.svg", "w", encoding="utf-8") as f: f.write(DUCK_FLY1_SVG)
    d2_md5 = md5_bytes(DUCK_FLY2_SVG.encode("utf-8"))
    with open(f"{WORK}/{d2_md5}.svg", "w", encoding="utf-8") as f: f.write(DUCK_FLY2_SVG)
    dh_md5 = md5_bytes(DUCK_HIT_SVG.encode("utf-8"))
    with open(f"{WORK}/{dh_md5}.svg", "w", encoding="utf-8") as f: f.write(DUCK_HIT_SVG)
    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f: f.write(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks     = build_stage_blocks()
    crosshair_blocks = build_crosshair_blocks()
    flash_blocks     = build_flash_blocks()
    duck_blocks      = build_duck_blocks()
    gameover_blocks  = build_gameover_blocks()

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
            V_KILLS: ["잡은수", 0],
            V_TOTAL: ["라운드오리수", 6],
            V_SPEED: ["오리속도", 2.4],
            V_AMMO:  ["탄약", 3],
            V_FX:    ["섬광X", 0],
            V_FY:    ["섬광Y", 0],
            V_DUCKS: ["오리상태", 0],
            V_DIR:   ["오리방향", 1],
            V_DONE:  ["라운드처리완료", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_SPAWN: "오리등장",
            BR_NEXT:  "다음라운드",
            BR_HIT:   "명중",
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

    duck = {
        "isStage": False, "name": "오리",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": duck_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "fly1", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": d1_md5, "md5ext": f"{d1_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 25},
            {"name": "fly2", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": d2_md5, "md5ext": f"{d2_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 25},
            {"name": "hit", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": dh_md5, "md5ext": f"{dh_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 25},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 100, "size": 90, "direction": 90,
        "draggable": False, "rotationStyle": "left-right"
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
        {"id": V_AMMO, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "탄약"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 3, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, crosshair, flash, duck, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "duck-hunt-builder"}
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
    print(f"✓ wrote {OUTPUT}")
    # block counts
    print(f"  stage:     {len(stage_blocks)} blocks")
    print(f"  crosshair: {len(crosshair_blocks)} blocks")
    print(f"  flash:     {len(flash_blocks)} blocks")
    print(f"  duck:      {len(duck_blocks)} blocks")
    print(f"  gameover:  {len(gameover_blocks)} blocks")
    print(f"  TOTAL:     {len(stage_blocks)+len(crosshair_blocks)+len(flash_blocks)+len(duck_blocks)+len(gameover_blocks)} blocks")

if __name__ == "__main__":
    main()
