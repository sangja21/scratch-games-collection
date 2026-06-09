#!/usr/bin/env python3
"""Tank Battle — top-down tank shooter (arrows = rotate + move, space = fire, covers + rounds)."""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "탱크_배틀.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: sandy desert tiles + pebbles --------
random.seed(7)
tiles = []
for ty in range(0, 360, 40):
    for tx in range(0, 480, 40):
        shade = "#E0C68A" if (tx // 40 + ty // 40) % 2 == 0 else "#D6B775"
        tiles.append(f'<rect x="{tx}" y="{ty}" width="40" height="40" fill="{shade}"/>')
TILES = "\n    ".join(tiles)

dots = []
for _ in range(36):
    x = random.randint(8, 472); y = random.randint(8, 352)
    r = random.uniform(1.2, 2.6)
    dots.append(f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="#8D6E63" opacity="0.5"/>')
DOTS = "\n    ".join(dots)

pebbles = []
for _ in range(22):
    x = random.randint(10, 470); y = random.randint(10, 350)
    rx = random.uniform(2.5, 4.5); ry = random.uniform(1.8, 3.0)
    pebbles.append(
        f'<ellipse cx="{x}" cy="{y}" rx="{rx:.1f}" ry="{ry:.1f}" '
        f'fill="#A1887F" stroke="#5D4037" stroke-width="0.6" opacity="0.7"/>'
    )
PEBBLES = "\n    ".join(pebbles)

tracks = []
for cx, cy, rot in [(120, 90, -25), (340, 240, 15), (220, 310, 40)]:
    for i in range(-3, 4):
        offx = i * 6
        tracks.append(
            f'<rect x="{cx + offx - 1}" y="{cy - 4}" width="3" height="8" '
            f'fill="#6D4C41" opacity="0.35" transform="rotate({rot} {cx} {cy})"/>'
        )
TRACKS = "\n    ".join(tracks)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <g>
    {TILES}
  </g>
  <g>
    {TRACKS}
  </g>
  <g>
    {DOTS}
  </g>
  <g>
    {PEBBLES}
  </g>
</svg>"""

# -------- Player tank (top-down, barrel pointing UP = direction 0) --------
TANK_PLAYER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <!-- shadow -->
  <ellipse cx="30" cy="52" rx="20" ry="3" fill="#000000" opacity="0.25"/>
  <!-- tracks (left + right) -->
  <rect x="6"  y="14" width="10" height="34" rx="3" fill="#37474F" stroke="#1B262C" stroke-width="1.5"/>
  <rect x="44" y="14" width="10" height="34" rx="3" fill="#37474F" stroke="#1B262C" stroke-width="1.5"/>
  <!-- track tread lines -->
  <line x1="6"  y1="20" x2="16" y2="20" stroke="#1B262C" stroke-width="1"/>
  <line x1="6"  y1="26" x2="16" y2="26" stroke="#1B262C" stroke-width="1"/>
  <line x1="6"  y1="32" x2="16" y2="32" stroke="#1B262C" stroke-width="1"/>
  <line x1="6"  y1="38" x2="16" y2="38" stroke="#1B262C" stroke-width="1"/>
  <line x1="44" y1="20" x2="54" y2="20" stroke="#1B262C" stroke-width="1"/>
  <line x1="44" y1="26" x2="54" y2="26" stroke="#1B262C" stroke-width="1"/>
  <line x1="44" y1="32" x2="54" y2="32" stroke="#1B262C" stroke-width="1"/>
  <line x1="44" y1="38" x2="54" y2="38" stroke="#1B262C" stroke-width="1"/>
  <!-- hull -->
  <rect x="14" y="18" width="32" height="28" rx="4" fill="#1976D2" stroke="#0D47A1" stroke-width="2"/>
  <!-- turret -->
  <circle cx="30" cy="32" r="10" fill="#1565C0" stroke="#0D47A1" stroke-width="1.6"/>
  <circle cx="30" cy="32" r="3"  fill="#0D47A1"/>
  <!-- barrel (pointing UP) -->
  <rect x="27" y="6" width="6" height="22" rx="1" fill="#263238" stroke="#0D1B22" stroke-width="1.2"/>
  <rect x="25" y="4" width="10" height="4" fill="#37474F" stroke="#0D1B22" stroke-width="1"/>
  <!-- forward marker -->
  <polygon points="30,2 27,7 33,7" fill="#FFEB3B"/>
  <!-- hatch -->
  <circle cx="22" cy="22" r="2" fill="#0D47A1"/>
</svg>"""

# -------- Enemy tank (red) --------
TANK_ENEMY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="52" rx="20" ry="3" fill="#000000" opacity="0.25"/>
  <rect x="6"  y="14" width="10" height="34" rx="3" fill="#3E2723" stroke="#1B0F0A" stroke-width="1.5"/>
  <rect x="44" y="14" width="10" height="34" rx="3" fill="#3E2723" stroke="#1B0F0A" stroke-width="1.5"/>
  <line x1="6"  y1="20" x2="16" y2="20" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="6"  y1="26" x2="16" y2="26" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="6"  y1="32" x2="16" y2="32" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="6"  y1="38" x2="16" y2="38" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="44" y1="20" x2="54" y2="20" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="44" y1="26" x2="54" y2="26" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="44" y1="32" x2="54" y2="32" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="44" y1="38" x2="54" y2="38" stroke="#1B0F0A" stroke-width="1"/>
  <rect x="14" y="18" width="32" height="28" rx="4" fill="#C62828" stroke="#7F0000" stroke-width="2"/>
  <circle cx="30" cy="32" r="10" fill="#B71C1C" stroke="#7F0000" stroke-width="1.6"/>
  <circle cx="30" cy="32" r="3"  fill="#7F0000"/>
  <rect x="27" y="6" width="6" height="22" rx="1" fill="#263238" stroke="#0D1B22" stroke-width="1.2"/>
  <rect x="25" y="4" width="10" height="4" fill="#37474F" stroke="#0D1B22" stroke-width="1"/>
  <polygon points="30,2 27,7 33,7" fill="#FFCDD2"/>
  <circle cx="22" cy="22" r="2" fill="#7F0000"/>
</svg>"""

# -------- Shell (small dark oblong + yellow tail) --------
SHELL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="20" viewBox="0 0 16 20">
  <!-- tail spark -->
  <ellipse cx="8" cy="17" rx="3" ry="2" fill="#FFB300" opacity="0.85"/>
  <ellipse cx="8" cy="18" rx="2" ry="1.2" fill="#FFEB3B" opacity="0.95"/>
  <!-- body -->
  <rect x="5" y="4" width="6" height="10" rx="1.5" fill="#37474F" stroke="#000000" stroke-width="1"/>
  <!-- nose -->
  <polygon points="5,4 11,4 8,0" fill="#263238" stroke="#000000" stroke-width="1"/>
</svg>"""

# -------- Enemy shell (red, distinct sprite so it never self-destructs on its
#          firing tank and never gets confused with player shells) --------
SHELL_ENEMY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="20" viewBox="0 0 16 20">
  <ellipse cx="8" cy="17" rx="3" ry="2" fill="#FF7043" opacity="0.85"/>
  <ellipse cx="8" cy="18" rx="2" ry="1.2" fill="#FFAB91" opacity="0.95"/>
  <rect x="5" y="4" width="6" height="10" rx="1.5" fill="#B71C1C" stroke="#3E0000" stroke-width="1"/>
  <polygon points="5,4 11,4 8,0" fill="#7F0000" stroke="#3E0000" stroke-width="1"/>
</svg>"""

# -------- Cover block (stone wall 50x50) --------
COVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 50 50">
  <rect x="2" y="2" width="46" height="46" rx="3" fill="#9E9E9E" stroke="#424242" stroke-width="2"/>
  <!-- brick lines -->
  <line x1="2"  y1="16" x2="48" y2="16" stroke="#616161" stroke-width="1"/>
  <line x1="2"  y1="32" x2="48" y2="32" stroke="#616161" stroke-width="1"/>
  <line x1="14" y1="2"  x2="14" y2="16" stroke="#616161" stroke-width="1"/>
  <line x1="34" y1="2"  x2="34" y2="16" stroke="#616161" stroke-width="1"/>
  <line x1="24" y1="16" x2="24" y2="32" stroke="#616161" stroke-width="1"/>
  <line x1="14" y1="32" x2="14" y2="48" stroke="#616161" stroke-width="1"/>
  <line x1="34" y1="32" x2="34" y2="48" stroke="#616161" stroke-width="1"/>
  <!-- highlights -->
  <circle cx="10" cy="10" r="1.5" fill="#BDBDBD"/>
  <circle cx="40" cy="42" r="1.5" fill="#BDBDBD"/>
  <circle cx="38" cy="24" r="1.2" fill="#BDBDBD"/>
  <circle cx="12" cy="40" r="1.2" fill="#BDBDBD"/>
</svg>"""

# -------- Game over banner --------
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.88"
        stroke="#FFB300" stroke-width="4"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#FFB300" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">탱크가 파괴되었어요</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#FFCC80" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭</text>
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

# ============================================================
#  IDs
# ============================================================
V_SCORE = "varScore01"
V_HP    = "varHP02"
V_ROUND = "varRound03"
V_STATE = "varState04"
V_ELEFT = "varEnemyLeft05"
V_ESPD  = "varESpeed06"
V_SX    = "varSX07"
V_SY    = "varSY08"
V_BX    = "varBX09"
V_BY    = "varBY10"
V_BDIR  = "varBDir11"
V_BKIND = "varBKind12"
V_INV   = "varInv13"
V_CD    = "varCD14"
# sprite-local "복제됨" 플래그 (원본=0, 클론=1) — 클론이 클론생성 방송을 받아도
# 다시 클론을 만들지 않게 가드. 안 그러면 적/엄폐물/적포탄이 기하급수로 증식.
V_EISC  = "varEnemyIsClone15"   # 적탱크 local
V_CVISC = "varCoverIsClone16"   # 엄폐물 local
V_ESISC = "varEShellIsClone17"  # 적포탄 local

BR_START   = "brStart01"
BR_ROUND   = "brRound02"
BR_ESPAWN  = "brESpawn03"
BR_COVER   = "brCover04"
BR_EFIRE   = "brEFire06"
BR_CLRCOV  = "brClrCov07"

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
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- when flag clicked: init + broadcast 게임시작 ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = []
    for var_pair, val in [
        (("점수", V_SCORE),   0),
        (("체력", V_HP),      3),
        (("라운드", V_ROUND), 1),
        (("게임상태", V_STATE), 1),
        (("잔여적", V_ELEFT), 0),
        (("적속도", V_ESPD),  1.0),
        (("무적", V_INV),     0),
        (("쿨다운", V_CD),    0),
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

    # --- on 게임시작: broadcast 라운드시작 ---
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    bm_r = gen(); bs[bm_r] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]}, shadow=True)
    bc_r = gen(); bs[bc_r] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_r]})
    bs[bm_r]["parent"] = bc_r
    chain([(h2, bs[h2]), (bc_r, bs[bc_r])])

    # --- on 라운드시작: set 잔여적 + spawn covers + spawn enemies ---
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=600,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]})

    # 잔여적 = min(라운드, 3)
    round_v = vrep("라운드", V_ROUND)
    cond_lt3 = cmp_op("operator_lt", round_v, 3)
    # if 라운드 < 3 → 잔여적 = 라운드 else 잔여적 = 3
    round_v2 = vrep("라운드", V_ROUND)
    set_eleft_a = gen(); bs[set_eleft_a] = mk("data_setvariableto",
        inputs={"VALUE": slot(round_v2)}, fields={"VARIABLE": ["잔여적", V_ELEFT]})
    bs[round_v2]["parent"] = set_eleft_a
    set_eleft_b = gen(); bs[set_eleft_b] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["잔여적", V_ELEFT]})
    if_eleft = gen(); bs[if_eleft] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_lt3],
                "SUBSTACK":  [2, set_eleft_a],
                "SUBSTACK2": [2, set_eleft_b]})
    bs[cond_lt3]["parent"] = if_eleft
    bs[set_eleft_a]["parent"] = if_eleft
    bs[set_eleft_b]["parent"] = if_eleft

    # --- Broadcast 엄폐물제거 first to clear existing cover clones before spawning new ones ---
    bm_clrcov = gen(); bs[bm_clrcov] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["엄폐물제거", BR_CLRCOV]}, shadow=True)
    bc_clrcov = gen(); bs[bc_clrcov] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_clrcov]})
    bs[bm_clrcov]["parent"] = bc_clrcov
    w_clrcov = gen(); bs[w_clrcov] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(bc_clrcov, bs[bc_clrcov]), (w_clrcov, bs[w_clrcov])])

    # --- Cover spawn loop: repeat 5 ---
    # body: SX=random(-200..200), SY=random(-140..140) gated abs(SY)>25 via simple second random pick
    sx_calc = gen(); bs[sx_calc] = mk("operator_random",
        inputs={"FROM": num(-200), "TO": num(200)})
    set_sx_c = gen(); bs[set_sx_c] = mk("data_setvariableto",
        inputs={"VALUE": slot(sx_calc)}, fields={"VARIABLE": ["스폰X", V_SX]})
    bs[sx_calc]["parent"] = set_sx_c

    # SY: 두 영역 중 하나 — random(1..2): 1 → random(-140..-30), 2 → random(30..140)
    pick_calc = gen(); bs[pick_calc] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(2)})
    set_sy_pick = gen(); bs[set_sy_pick] = mk("data_setvariableto",
        inputs={"VALUE": slot(pick_calc)}, fields={"VARIABLE": ["스폰Y", V_SY]})
    bs[pick_calc]["parent"] = set_sy_pick
    # if 스폰Y = 1 → SY = random(-140..-30)
    sy_v_a = vrep("스폰Y", V_SY)
    cond_sy1 = cmp_op("operator_equals", sy_v_a, 1)
    sy_calc_neg = gen(); bs[sy_calc_neg] = mk("operator_random",
        inputs={"FROM": num(-140), "TO": num(-30)})
    set_sy_neg = gen(); bs[set_sy_neg] = mk("data_setvariableto",
        inputs={"VALUE": slot(sy_calc_neg)}, fields={"VARIABLE": ["스폰Y", V_SY]})
    bs[sy_calc_neg]["parent"] = set_sy_neg
    sy_calc_pos = gen(); bs[sy_calc_pos] = mk("operator_random",
        inputs={"FROM": num(30), "TO": num(140)})
    set_sy_pos = gen(); bs[set_sy_pos] = mk("data_setvariableto",
        inputs={"VALUE": slot(sy_calc_pos)}, fields={"VARIABLE": ["스폰Y", V_SY]})
    bs[sy_calc_pos]["parent"] = set_sy_pos
    if_sy_split = gen(); bs[if_sy_split] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_sy1],
                "SUBSTACK":  [2, set_sy_neg],
                "SUBSTACK2": [2, set_sy_pos]})
    bs[cond_sy1]["parent"] = if_sy_split
    bs[set_sy_neg]["parent"] = if_sy_split
    bs[set_sy_pos]["parent"] = if_sy_split

    # broadcast 엄폐물생성
    bm_cov = gen(); bs[bm_cov] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["엄폐물생성", BR_COVER]}, shadow=True)
    bc_cov = gen(); bs[bc_cov] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_cov]})
    bs[bm_cov]["parent"] = bc_cov

    w_cov = gen(); bs[w_cov] = mk("control_wait", inputs={"DURATION": num(0.05)})

    chain([(set_sx_c, bs[set_sx_c]), (set_sy_pick, bs[set_sy_pick]),
           (if_sy_split, bs[if_sy_split]), (bc_cov, bs[bc_cov]),
           (w_cov, bs[w_cov])])

    rep_cov = gen(); bs[rep_cov] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK": [2, set_sx_c]})
    bs[set_sx_c]["parent"] = rep_cov

    # --- Enemy spawn loop: repeat 잔여적 ---
    e_sx_calc = gen(); bs[e_sx_calc] = mk("operator_random",
        inputs={"FROM": num(-220), "TO": num(220)})
    e_set_sx = gen(); bs[e_set_sx] = mk("data_setvariableto",
        inputs={"VALUE": slot(e_sx_calc)}, fields={"VARIABLE": ["스폰X", V_SX]})
    bs[e_sx_calc]["parent"] = e_set_sx

    e_sy_calc = gen(); bs[e_sy_calc] = mk("operator_random",
        inputs={"FROM": num(80), "TO": num(160)})
    e_set_sy = gen(); bs[e_set_sy] = mk("data_setvariableto",
        inputs={"VALUE": slot(e_sy_calc)}, fields={"VARIABLE": ["스폰Y", V_SY]})
    bs[e_sy_calc]["parent"] = e_set_sy

    bm_es = gen(); bs[bm_es] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적스폰", BR_ESPAWN]}, shadow=True)
    bc_es = gen(); bs[bc_es] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_es]})
    bs[bm_es]["parent"] = bc_es

    w_es = gen(); bs[w_es] = mk("control_wait", inputs={"DURATION": num(0.3)})

    chain([(e_set_sx, bs[e_set_sx]), (e_set_sy, bs[e_set_sy]),
           (bc_es, bs[bc_es]), (w_es, bs[w_es])])

    eleft_v = vrep("잔여적", V_ELEFT)
    rep_e = gen(); bs[rep_e] = mk("control_repeat",
        inputs={"TIMES": slot(eleft_v), "SUBSTACK": [2, e_set_sx]})
    bs[eleft_v]["parent"] = rep_e
    bs[e_set_sx]["parent"] = rep_e

    chain([(h3, bs[h3]), (if_eleft, bs[if_eleft]),
           (bc_clrcov, bs[bc_clrcov]),
           (rep_cov, bs[rep_cov]), (rep_e, bs[rep_e])])

    # --- forever counter (무적/쿨다운 decrement) ---
    h4 = gen(); bs[h4] = mk("event_whenflagclicked", top=True, x=400, y=20)
    # if 무적 > 0 → 무적 -1
    inv_v = vrep("무적", V_INV)
    c_inv = cmp_op("operator_gt", inv_v, 0)
    dec_inv = gen(); bs[dec_inv] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["무적", V_INV]})
    if_inv = gen(); bs[if_inv] = mk("control_if",
        inputs={"CONDITION": [2, c_inv], "SUBSTACK": [2, dec_inv]})
    bs[c_inv]["parent"] = if_inv
    bs[dec_inv]["parent"] = if_inv

    cd_v = vrep("쿨다운", V_CD)
    c_cd = cmp_op("operator_gt", cd_v, 0)
    dec_cd = gen(); bs[dec_cd] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["쿨다운", V_CD]})
    if_cd = gen(); bs[if_cd] = mk("control_if",
        inputs={"CONDITION": [2, c_cd], "SUBSTACK": [2, dec_cd]})
    bs[c_cd]["parent"] = if_cd
    bs[dec_cd]["parent"] = if_cd

    w_ctr = gen(); bs[w_ctr] = mk("control_wait", inputs={"DURATION": num(0.04)})

    chain([(if_inv, bs[if_inv]), (if_cd, bs[if_cd]), (w_ctr, bs[w_ctr])])
    fe_ctr = gen(); bs[fe_ctr] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_inv]})
    bs[if_inv]["parent"] = fe_ctr

    chain([(h4, bs[h4]), (fe_ctr, bs[fe_ctr])])

    # --- round watcher: wait until 잔여적>0 → wait until 잔여적=0 AND 게임상태=1 → next round
    # This pattern avoids the race condition where 잔여적=0 at flag-click fires the watcher
    # before the first round's enemies have been spawned.
    h5 = gen(); bs[h5] = mk("event_whenflagclicked", top=True, x=400, y=400)

    # wait until 잔여적 > 0  (확인: 적이 실제로 스폰될 때까지 대기)
    eleft_pos1 = vrep("잔여적", V_ELEFT)
    cond_epos = cmp_op("operator_gt", eleft_pos1, 0)
    wu_epos = gen(); bs[wu_epos] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_epos]})
    bs[cond_epos]["parent"] = wu_epos

    # wait until 잔여적 = 0 AND 게임상태 = 1
    eleft_v2 = vrep("잔여적", V_ELEFT)
    cond_e0 = cmp_op("operator_equals", eleft_v2, 0)
    state_v = vrep("게임상태", V_STATE)
    cond_alive = cmp_op("operator_equals", state_v, 1)
    cond_next = bool_op("operator_and", cond_e0, cond_alive)
    wu_done = gen(); bs[wu_done] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_next]})
    bs[cond_next]["parent"] = wu_done

    w_pre = gen(); bs[w_pre] = mk("control_wait", inputs={"DURATION": num(1.5)})
    inc_r = gen(); bs[inc_r] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
    esp_v = vrep("적속도", V_ESPD)
    mul_esp = op("operator_multiply", esp_v, 1.10)
    set_esp = gen(); bs[set_esp] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_esp)}, fields={"VARIABLE": ["적속도", V_ESPD]})
    bs[mul_esp]["parent"] = set_esp

    bm_r2 = gen(); bs[bm_r2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUND]}, shadow=True)
    bc_r2 = gen(); bs[bc_r2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_r2]})
    bs[bm_r2]["parent"] = bc_r2

    chain([(wu_epos, bs[wu_epos]), (wu_done, bs[wu_done]),
           (w_pre, bs[w_pre]), (inc_r, bs[inc_r]),
           (set_esp, bs[set_esp]), (bc_r2, bs[bc_r2])])

    fe_watch = gen(); bs[fe_watch] = mk("control_forever",
        inputs={"SUBSTACK": [2, wu_epos]})
    bs[wu_epos]["parent"] = fe_watch

    chain([(h5, bs[h5]), (fe_watch, bs[fe_watch])])

    return bs

# ============================================================
#  PLAYER TANK
# ============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- flag: init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(75)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # forever (controls)
    # left arrow → turn ccw 4
    l_menu = gen(); bs[l_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    l_press = gen(); bs[l_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, l_menu]})
    bs[l_menu]["parent"] = l_press
    turn_ccw = gen(); bs[turn_ccw] = mk("motion_turnleft", inputs={"DEGREES": num(4)})
    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION": [2, l_press], "SUBSTACK": [2, turn_ccw]})
    bs[l_press]["parent"] = if_l
    bs[turn_ccw]["parent"] = if_l

    # right arrow → turn cw 4
    r_menu = gen(); bs[r_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    r_press = gen(); bs[r_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, r_menu]})
    bs[r_menu]["parent"] = r_press
    turn_cw = gen(); bs[turn_cw] = mk("motion_turnright", inputs={"DEGREES": num(4)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION": [2, r_press], "SUBSTACK": [2, turn_cw]})
    bs[r_press]["parent"] = if_r
    bs[turn_cw]["parent"] = if_r

    # up arrow → move 2.2
    up_menu = gen(); bs[up_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["up arrow", None]}, shadow=True)
    up_press = gen(); bs[up_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, up_menu]})
    bs[up_menu]["parent"] = up_press
    mv_fwd = gen(); bs[mv_fwd] = mk("motion_movesteps", inputs={"STEPS": num(2.2)})
    if_up = gen(); bs[if_up] = mk("control_if",
        inputs={"CONDITION": [2, up_press], "SUBSTACK": [2, mv_fwd]})
    bs[up_press]["parent"] = if_up
    bs[mv_fwd]["parent"] = if_up

    # down arrow → move -1.6
    dn_menu = gen(); bs[dn_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["down arrow", None]}, shadow=True)
    dn_press = gen(); bs[dn_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, dn_menu]})
    bs[dn_menu]["parent"] = dn_press
    mv_bwd = gen(); bs[mv_bwd] = mk("motion_movesteps", inputs={"STEPS": num(-1.6)})
    if_dn = gen(); bs[if_dn] = mk("control_if",
        inputs={"CONDITION": [2, dn_press], "SUBSTACK": [2, mv_bwd]})
    bs[dn_press]["parent"] = if_dn
    bs[mv_bwd]["parent"] = if_dn

    # if touching 엄폐물 → move -2.5 (bounce back)
    tm_cov = gen(); bs[tm_cov] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["엄폐물", None]}, shadow=True)
    tc_cov = gen(); bs[tc_cov] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_cov]})
    bs[tm_cov]["parent"] = tc_cov
    mv_back = gen(); bs[mv_back] = mk("motion_movesteps", inputs={"STEPS": num(-2.5)})
    if_cov = gen(); bs[if_cov] = mk("control_if",
        inputs={"CONDITION": [2, tc_cov], "SUBSTACK": [2, mv_back]})
    bs[tc_cov]["parent"] = if_cov
    bs[mv_back]["parent"] = if_cov

    # clamp x/y
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    c_xhi = cmp_op("operator_gt", xp1, 220)
    sx_hi = gen(); bs[sx_hi] = mk("motion_setx", inputs={"X": num(220)})
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, c_xhi], "SUBSTACK": [2, sx_hi]})
    bs[c_xhi]["parent"] = if_xhi
    bs[sx_hi]["parent"] = if_xhi

    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_xlo = cmp_op("operator_lt", xp2, -220)
    sx_lo = gen(); bs[sx_lo] = mk("motion_setx", inputs={"X": num(-220)})
    if_xlo = gen(); bs[if_xlo] = mk("control_if",
        inputs={"CONDITION": [2, c_xlo], "SUBSTACK": [2, sx_lo]})
    bs[c_xlo]["parent"] = if_xlo
    bs[sx_lo]["parent"] = if_xlo

    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    c_yhi = cmp_op("operator_gt", yp1, 160)
    sy_hi = gen(); bs[sy_hi] = mk("motion_sety", inputs={"Y": num(160)})
    if_yhi = gen(); bs[if_yhi] = mk("control_if",
        inputs={"CONDITION": [2, c_yhi], "SUBSTACK": [2, sy_hi]})
    bs[c_yhi]["parent"] = if_yhi
    bs[sy_hi]["parent"] = if_yhi

    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    c_ylo = cmp_op("operator_lt", yp2, -160)
    sy_lo = gen(); bs[sy_lo] = mk("motion_sety", inputs={"Y": num(-160)})
    if_ylo = gen(); bs[if_ylo] = mk("control_if",
        inputs={"CONDITION": [2, c_ylo], "SUBSTACK": [2, sy_lo]})
    bs[c_ylo]["parent"] = if_ylo
    bs[sy_lo]["parent"] = if_ylo

    w_ctrl = gen(); bs[w_ctrl] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(if_l, bs[if_l]), (if_r, bs[if_r]),
           (if_up, bs[if_up]), (if_dn, bs[if_dn]),
           (if_cov, bs[if_cov]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (w_ctrl, bs[w_ctrl])])
    fe_ctrl = gen(); bs[fe_ctrl] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_l]})
    bs[if_l]["parent"] = fe_ctrl

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (pd, bs[pd]), (front, bs[front]),
           (fe_ctrl, bs[fe_ctrl])])

    # --- fire input forever (space, cooldown) ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    sp_menu = gen(); bs[sp_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sp_press = gen(); bs[sp_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, sp_menu]})
    bs[sp_menu]["parent"] = sp_press

    cd_v = vrep("쿨다운", V_CD)
    cond_cd0 = cmp_op("operator_equals", cd_v, 0)
    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)
    cond_a = bool_op("operator_and", sp_press, cond_cd0)
    cond_can_fire = bool_op("operator_and", cond_a, cond_play)

    # body: set 포탄X/Y/방향/종류, sound, create clone of 포탄, set 쿨다운=12, set 무적=4
    xp_s = gen(); bs[xp_s] = mk("motion_xposition")
    set_bx = gen(); bs[set_bx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xp_s)}, fields={"VARIABLE": ["포탄X", V_BX]})
    bs[xp_s]["parent"] = set_bx

    yp_s = gen(); bs[yp_s] = mk("motion_yposition")
    set_by = gen(); bs[set_by] = mk("data_setvariableto",
        inputs={"VALUE": slot(yp_s)}, fields={"VARIABLE": ["포탄Y", V_BY]})
    bs[yp_s]["parent"] = set_by

    dir_s = gen(); bs[dir_s] = mk("motion_direction")
    set_bdir = gen(); bs[set_bdir] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_s)}, fields={"VARIABLE": ["포탄방향", V_BDIR]})
    bs[dir_s]["parent"] = set_bdir

    pitch_fire = gen(); bs[pitch_fire] = mk("sound_seteffectto",
        inputs={"VALUE": num(100)}, fields={"EFFECT": ["PITCH", None]})
    snm_fire = gen(); bs[snm_fire] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_fire = gen(); bs[snd_fire] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_fire]})
    bs[snm_fire]["parent"] = snd_fire

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["포탄", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone

    set_cd = gen(); bs[set_cd] = mk("data_setvariableto",
        inputs={"VALUE": num(12)}, fields={"VARIABLE": ["쿨다운", V_CD]})

    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]),
           (set_bdir, bs[set_bdir]),
           (pitch_fire, bs[pitch_fire]), (snd_fire, bs[snd_fire]),
           (cclone, bs[cclone]),
           (set_cd, bs[set_cd])])

    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, cond_can_fire], "SUBSTACK": [2, set_bx]})
    bs[cond_can_fire]["parent"] = if_fire
    bs[set_bx]["parent"] = if_fire

    w_fire = gen(); bs[w_fire] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_fire, bs[if_fire]), (w_fire, bs[w_fire])])

    fe_fire = gen(); bs[fe_fire] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_fire]})
    bs[if_fire]["parent"] = fe_fire

    chain([(h2, bs[h2]), (fe_fire, bs[fe_fire])])

    # --- damage watcher: touching 적포탄 AND 무적=0 → HP -1 ---
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)

    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["적포탄", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b]})
    bs[tm_b]["parent"] = tc_b

    inv_v = vrep("무적", V_INV)
    cond_no_inv = cmp_op("operator_equals", inv_v, 0)
    state_v2 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state_v2, 1)
    cond_dmg_a = bool_op("operator_and", tc_b, cond_no_inv)
    cond_dmg = bool_op("operator_and", cond_dmg_a, cond_play2)

    dec_hp = gen(); bs[dec_hp] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["체력", V_HP]})
    set_inv2 = gen(); bs[set_inv2] = mk("data_setvariableto",
        inputs={"VALUE": num(25)}, fields={"VARIABLE": ["무적", V_INV]})
    pitch_dmg = gen(); bs[pitch_dmg] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT": ["PITCH", None]})
    snm_d = gen(); bs[snm_d] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_d = gen(); bs[snd_d] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_d]})
    bs[snm_d]["parent"] = snd_d

    hp_v = vrep("체력", V_HP)
    cond_dead = cmp_op("operator_lt", hp_v, 1)
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, set_state0]})
    bs[cond_dead]["parent"] = if_dead
    bs[set_state0]["parent"] = if_dead

    chain([(dec_hp, bs[dec_hp]), (set_inv2, bs[set_inv2]),
           (pitch_dmg, bs[pitch_dmg]), (snd_d, bs[snd_d]),
           (if_dead, bs[if_dead])])

    if_dmg = gen(); bs[if_dmg] = mk("control_if",
        inputs={"CONDITION": [2, cond_dmg], "SUBSTACK": [2, dec_hp]})
    bs[cond_dmg]["parent"] = if_dmg
    bs[dec_hp]["parent"] = if_dmg

    w_dmg = gen(); bs[w_dmg] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_dmg, bs[if_dmg]), (w_dmg, bs[w_dmg])])
    fe_dmg = gen(); bs[fe_dmg] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_dmg]})
    bs[if_dmg]["parent"] = fe_dmg

    chain([(h3, bs[h3]), (fe_dmg, bs[fe_dmg])])

    return bs

# ============================================================
#  SHELL (bullet)
# ============================================================
def build_shell_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)

    bx_v = vrep("포탄X", V_BX); by_v = vrep("포탄Y", V_BY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g

    bdir_v = vrep("포탄방향", V_BDIR)
    point_b = gen(); bs[point_b] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(bdir_v)})
    bs[bdir_v]["parent"] = point_b

    show = gen(); bs[show] = mk("looks_show")

    # repeat until OOB OR touching 적탱크/엄폐물
    # (플레이어탱크 excluded: player bullets spawn at player center and would
    #  immediately self-destruct; player damage is handled by player's own watcher)
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(10)})
    w_iter = gen(); bs[w_iter] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(mv, bs[mv]), (w_iter, bs[w_iter])])

    xp = gen(); bs[xp] = mk("motion_xposition")
    cx_hi = cmp_op("operator_gt", xp, 240)
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cx_lo = cmp_op("operator_lt", xp_b, -240)
    cx_out = bool_op("operator_or", cx_hi, cx_lo)

    yp = gen(); bs[yp] = mk("motion_yposition")
    cy_hi = cmp_op("operator_gt", yp, 180)
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cy_lo = cmp_op("operator_lt", yp_b, -180)
    cy_out = bool_op("operator_or", cy_hi, cy_lo)

    c_oob = bool_op("operator_or", cx_out, cy_out)

    tm_e = gen(); bs[tm_e] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["적탱크", None]}, shadow=True)
    tc_e = gen(); bs[tc_e] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_e]})
    bs[tm_e]["parent"] = tc_e

    tm_c = gen(); bs[tm_c] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["엄폐물", None]}, shadow=True)
    tc_c = gen(); bs[tc_c] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_c]})
    bs[tm_c]["parent"] = tc_c

    c_ec = bool_op("operator_or", tc_e, tc_c)
    c_stop = bool_op("operator_or", c_oob, c_ec)

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_stop], "SUBSTACK": [2, mv]})
    bs[c_stop]["parent"] = rep_until
    bs[mv]["parent"] = rep_until

    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (point_b, bs[point_b]),
           (show, bs[show]), (rep_until, bs[rep_until]),
           (hi2, bs[hi2]), (delc, bs[delc])])

    return bs

# ============================================================
#  ENEMY TANK
# ============================================================
def build_enemy_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(75)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    orig0 = gen(); bs[orig0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["복제됨", V_EISC]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # on 적스폰 → (원본만) create clone
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["적스폰", BR_ESPAWN]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    isc0 = cmp_op("operator_equals", vrep("복제됨", V_EISC), 0)
    if_spawn = gen(); bs[if_spawn] = mk("control_if",
        inputs={"CONDITION": [2, isc0], "SUBSTACK": [2, cclone]})
    bs[isc0]["parent"] = if_spawn; bs[cclone]["parent"] = if_spawn
    chain([(h2, bs[h2]), (if_spawn, bs[if_spawn])])

    # clone start
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)
    set_isc1 = gen(); bs[set_isc1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["복제됨", V_EISC]})
    sx_v = vrep("스폰X", V_SX); sy_v = vrep("스폰Y", V_SY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(sx_v), "Y": slot(sy_v)})
    bs[sx_v]["parent"] = g; bs[sy_v]["parent"] = g
    pd0 = gen(); bs[pd0] = mk("motion_pointindirection", inputs={"DIRECTION": num(180)})
    show = gen(); bs[show] = mk("looks_show")

    # forever body
    # enemy dies when touched by a PLAYER bullet (포탄 sprite). 적 포탄은 별도 스프라이트
    # '적포탄' 이므로 자기 포탄에 맞아 죽을 일이 없다 — 종류 구분(전역) 불필요.
    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["포탄", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b]})
    bs[tm_b]["parent"] = tc_b
    cond_killed = tc_b

    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(20)}, fields={"VARIABLE": ["점수", V_SCORE]})
    dec_eleft = gen(); bs[dec_eleft] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["잔여적", V_ELEFT]})
    pitch_kill = gen(); bs[pitch_kill] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["PITCH", None]})
    snm_k = gen(); bs[snm_k] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_k = gen(); bs[snd_k] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_k]})
    bs[snm_k]["parent"] = snd_k
    hi_k = gen(); bs[hi_k] = mk("looks_hide")
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")

    chain([(inc_score, bs[inc_score]), (dec_eleft, bs[dec_eleft]),
           (pitch_kill, bs[pitch_kill]), (snd_k, bs[snd_k]),
           (hi_k, bs[hi_k]), (del_k, bs[del_k])])

    if_killed = gen(); bs[if_killed] = mk("control_if",
        inputs={"CONDITION": [2, cond_killed], "SUBSTACK": [2, inc_score]})
    bs[cond_killed]["parent"] = if_killed
    bs[inc_score]["parent"] = if_killed

    # point towards 플레이어탱크
    pt_menu = gen(); bs[pt_menu] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["플레이어탱크", None]}, shadow=True)
    point_p = gen(); bs[point_p] = mk("motion_pointtowards",
        inputs={"TOWARDS": [1, pt_menu]})
    bs[pt_menu]["parent"] = point_p

    # move 적속도 steps
    esp_v = vrep("적속도", V_ESPD)
    mv = gen(); bs[mv] = mk("motion_movesteps",
        inputs={"STEPS": slot(esp_v)})
    bs[esp_v]["parent"] = mv

    # if touching 엄폐물: move -2.5 + turn cw 30
    tm_cv = gen(); bs[tm_cv] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["엄폐물", None]}, shadow=True)
    tc_cv = gen(); bs[tc_cv] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_cv]})
    bs[tm_cv]["parent"] = tc_cv
    mv_back = gen(); bs[mv_back] = mk("motion_movesteps", inputs={"STEPS": num(-2.5)})
    turn_cw30 = gen(); bs[turn_cw30] = mk("motion_turnright", inputs={"DEGREES": num(30)})
    chain([(mv_back, bs[mv_back]), (turn_cw30, bs[turn_cw30])])
    if_bump = gen(); bs[if_bump] = mk("control_if",
        inputs={"CONDITION": [2, tc_cv], "SUBSTACK": [2, mv_back]})
    bs[tc_cv]["parent"] = if_bump
    bs[mv_back]["parent"] = if_bump

    # clamp to stage
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    c_xhi = cmp_op("operator_gt", xp1, 230)
    sx_hi = gen(); bs[sx_hi] = mk("motion_setx", inputs={"X": num(230)})
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, c_xhi], "SUBSTACK": [2, sx_hi]})
    bs[c_xhi]["parent"] = if_xhi
    bs[sx_hi]["parent"] = if_xhi

    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_xlo = cmp_op("operator_lt", xp2, -230)
    sx_lo = gen(); bs[sx_lo] = mk("motion_setx", inputs={"X": num(-230)})
    if_xlo = gen(); bs[if_xlo] = mk("control_if",
        inputs={"CONDITION": [2, c_xlo], "SUBSTACK": [2, sx_lo]})
    bs[c_xlo]["parent"] = if_xlo
    bs[sx_lo]["parent"] = if_xlo

    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    c_yhi = cmp_op("operator_gt", yp1, 170)
    sy_hi = gen(); bs[sy_hi] = mk("motion_sety", inputs={"Y": num(170)})
    if_yhi = gen(); bs[if_yhi] = mk("control_if",
        inputs={"CONDITION": [2, c_yhi], "SUBSTACK": [2, sy_hi]})
    bs[c_yhi]["parent"] = if_yhi
    bs[sy_hi]["parent"] = if_yhi

    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    c_ylo = cmp_op("operator_lt", yp2, -170)
    sy_lo = gen(); bs[sy_lo] = mk("motion_sety", inputs={"Y": num(-170)})
    if_ylo = gen(); bs[if_ylo] = mk("control_if",
        inputs={"CONDITION": [2, c_ylo], "SUBSTACK": [2, sy_lo]})
    bs[c_ylo]["parent"] = if_ylo
    bs[sy_lo]["parent"] = if_ylo

    # firing probability: if random(1..120)=1 → set 포탄X/Y/dir/kind=1, sound, broadcast 적사격
    r_fire = gen(); bs[r_fire] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(120)})
    c_efire = cmp_op("operator_equals", r_fire, 1)
    bs[r_fire]["parent"] = c_efire

    xpe = gen(); bs[xpe] = mk("motion_xposition")
    set_bxe = gen(); bs[set_bxe] = mk("data_setvariableto",
        inputs={"VALUE": slot(xpe)}, fields={"VARIABLE": ["포탄X", V_BX]})
    bs[xpe]["parent"] = set_bxe
    ype = gen(); bs[ype] = mk("motion_yposition")
    set_bye = gen(); bs[set_bye] = mk("data_setvariableto",
        inputs={"VALUE": slot(ype)}, fields={"VARIABLE": ["포탄Y", V_BY]})
    bs[ype]["parent"] = set_bye
    dire = gen(); bs[dire] = mk("motion_direction")
    set_bdire = gen(); bs[set_bdire] = mk("data_setvariableto",
        inputs={"VALUE": slot(dire)}, fields={"VARIABLE": ["포탄방향", V_BDIR]})
    bs[dire]["parent"] = set_bdire

    pitch_ef = gen(); bs[pitch_ef] = mk("sound_seteffectto",
        inputs={"VALUE": num(-100)}, fields={"EFFECT": ["PITCH", None]})
    snm_ef = gen(); bs[snm_ef] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_ef = gen(); bs[snd_ef] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_ef]})
    bs[snm_ef]["parent"] = snd_ef

    bm_ef = gen(); bs[bm_ef] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적사격", BR_EFIRE]}, shadow=True)
    bc_ef = gen(); bs[bc_ef] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ef]})
    bs[bm_ef]["parent"] = bc_ef

    chain([(set_bxe, bs[set_bxe]), (set_bye, bs[set_bye]),
           (set_bdire, bs[set_bdire]),
           (pitch_ef, bs[pitch_ef]), (snd_ef, bs[snd_ef]),
           (bc_ef, bs[bc_ef])])

    if_efire = gen(); bs[if_efire] = mk("control_if",
        inputs={"CONDITION": [2, c_efire], "SUBSTACK": [2, set_bxe]})
    bs[c_efire]["parent"] = if_efire
    bs[set_bxe]["parent"] = if_efire

    w_iter = gen(); bs[w_iter] = mk("control_wait", inputs={"DURATION": num(0.04)})

    chain([(if_killed, bs[if_killed]),
           (point_p, bs[point_p]), (mv, bs[mv]),
           (if_bump, bs[if_bump]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (if_efire, bs[if_efire]), (w_iter, bs[w_iter])])

    fe_body = gen(); bs[fe_body] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_killed]})
    bs[if_killed]["parent"] = fe_body

    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (pd0, bs[pd0]),
           (show, bs[show]), (fe_body, bs[fe_body])])

    return bs

# ============================================================
#  COVER
# ============================================================
def build_cover_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    orig0 = gen(); bs[orig0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["복제됨", V_CVISC]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (orig0, bs[orig0])])

    # on 엄폐물제거 → delete this clone (clears all cover clones before round restart)
    h_clr = gen(); bs[h_clr] = mk("event_whenbroadcastreceived", top=True, x=400, y=200,
        fields={"BROADCAST_OPTION": ["엄폐물제거", BR_CLRCOV]})
    del_clr = gen(); bs[del_clr] = mk("control_delete_this_clone")
    chain([(h_clr, bs[h_clr]), (del_clr, bs[del_clr])])

    # on 엄폐물생성 → (원본만) create clone
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["엄폐물생성", BR_COVER]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    isc0 = cmp_op("operator_equals", vrep("복제됨", V_CVISC), 0)
    if_spawn = gen(); bs[if_spawn] = mk("control_if",
        inputs={"CONDITION": [2, isc0], "SUBSTACK": [2, cclone]})
    bs[isc0]["parent"] = if_spawn; bs[cclone]["parent"] = if_spawn
    chain([(h2, bs[h2]), (if_spawn, bs[if_spawn])])

    # clone start
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)
    set_isc1 = gen(); bs[set_isc1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["복제됨", V_CVISC]})
    sx_v = vrep("스폰X", V_SX); sy_v = vrep("스폰Y", V_SY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(sx_v), "Y": slot(sy_v)})
    bs[sx_v]["parent"] = g; bs[sy_v]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")

    # forever: if touching 포탄 → sound + hide + delete
    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["포탄", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b]})
    bs[tm_b]["parent"] = tc_b

    pitch_br = gen(); bs[pitch_br] = mk("sound_seteffectto",
        inputs={"VALUE": num(-100)}, fields={"EFFECT": ["PITCH", None]})
    snm_b = gen(); bs[snm_b] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_b = gen(); bs[snd_b] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_b]})
    bs[snm_b]["parent"] = snd_b
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(pitch_br, bs[pitch_br]), (snd_b, bs[snd_b]),
           (hi2, bs[hi2]), (delc, bs[delc])])

    if_brk = gen(); bs[if_brk] = mk("control_if",
        inputs={"CONDITION": [2, tc_b], "SUBSTACK": [2, pitch_br]})
    bs[tc_b]["parent"] = if_brk
    bs[pitch_br]["parent"] = if_brk

    w_iter = gen(); bs[w_iter] = mk("control_wait", inputs={"DURATION": num(0.04)})
    chain([(if_brk, bs[if_brk]), (w_iter, bs[w_iter])])

    fe_body = gen(); bs[fe_body] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_brk]})
    bs[if_brk]["parent"] = fe_body

    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (show, bs[show]), (fe_body, bs[fe_body])])

    return bs

# ============================================================
#  ENEMY SHELL (별도 스프라이트) — 적사격 방송으로 생성, 자기 탱크 위에서 시작해도
#  '적탱크' 를 정지조건에 넣지 않으므로 자폭하지 않는다. 플레이어/엄폐물/가장자리에서 소멸.
#  플레이어 피해는 플레이어의 'touching 적포탄' 와처가 처리.
# ============================================================
def build_enemy_shell_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    orig0 = gen(); bs[orig0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["복제됨", V_ESISC]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # on 적사격 → (원본만) create clone
    h_ef = gen(); bs[h_ef] = mk("event_whenbroadcastreceived", top=True, x=400, y=20,
        fields={"BROADCAST_OPTION": ["적사격", BR_EFIRE]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    isc0 = cmp_op("operator_equals", vrep("복제됨", V_ESISC), 0)
    if_spawn = gen(); bs[if_spawn] = mk("control_if",
        inputs={"CONDITION": [2, isc0], "SUBSTACK": [2, cclone]})
    bs[isc0]["parent"] = if_spawn; bs[cclone]["parent"] = if_spawn
    chain([(h_ef, bs[h_ef]), (if_spawn, bs[if_spawn])])

    # clone start: goto 포탄X/Y, point 포탄방향, fly until edge/엄폐물/플레이어
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)
    set_isc1 = gen(); bs[set_isc1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["복제됨", V_ESISC]})
    bx_v = vrep("포탄X", V_BX); by_v = vrep("포탄Y", V_BY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g
    bdir_v = vrep("포탄방향", V_BDIR)
    point_b = gen(); bs[point_b] = mk("motion_pointindirection", inputs={"DIRECTION": slot(bdir_v)})
    bs[bdir_v]["parent"] = point_b
    show = gen(); bs[show] = mk("looks_show")

    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(7)})
    w_iter = gen(); bs[w_iter] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(mv, bs[mv]), (w_iter, bs[w_iter])])

    xp = gen(); bs[xp] = mk("motion_xposition")
    cx_hi = cmp_op("operator_gt", xp, 240)
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cx_lo = cmp_op("operator_lt", xp_b, -240)
    cx_out = bool_op("operator_or", cx_hi, cx_lo)
    yp = gen(); bs[yp] = mk("motion_yposition")
    cy_hi = cmp_op("operator_gt", yp, 180)
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cy_lo = cmp_op("operator_lt", yp_b, -180)
    cy_out = bool_op("operator_or", cy_hi, cy_lo)
    c_oob = bool_op("operator_or", cx_out, cy_out)

    tm_p = gen(); bs[tm_p] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["플레이어탱크", None]}, shadow=True)
    tc_p = gen(); bs[tc_p] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, tm_p]})
    bs[tm_p]["parent"] = tc_p
    tm_c = gen(); bs[tm_c] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["엄폐물", None]}, shadow=True)
    tc_c = gen(); bs[tc_c] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, tm_c]})
    bs[tm_c]["parent"] = tc_c
    c_pc = bool_op("operator_or", tc_p, tc_c)
    c_stop = bool_op("operator_or", c_oob, c_pc)

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_stop], "SUBSTACK": [2, mv]})
    bs[c_stop]["parent"] = rep_until
    bs[mv]["parent"] = rep_until

    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (point_b, bs[point_b]),
           (show, bs[show]), (rep_until, bs[rep_until]),
           (hi2, bs[hi2]), (delc, bs[delc])])
    return bs

# ============================================================
#  GAME OVER
# ============================================================
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

# ============================================================
#  ASSEMBLE
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f: f.write(BG_SVG)
    tp_md5 = md5_bytes(TANK_PLAYER_SVG.encode("utf-8"))
    with open(f"{WORK}/{tp_md5}.svg", "w", encoding="utf-8") as f: f.write(TANK_PLAYER_SVG)
    te_md5 = md5_bytes(TANK_ENEMY_SVG.encode("utf-8"))
    with open(f"{WORK}/{te_md5}.svg", "w", encoding="utf-8") as f: f.write(TANK_ENEMY_SVG)
    sh_md5 = md5_bytes(SHELL_SVG.encode("utf-8"))
    with open(f"{WORK}/{sh_md5}.svg", "w", encoding="utf-8") as f: f.write(SHELL_SVG)
    se_md5 = md5_bytes(SHELL_ENEMY_SVG.encode("utf-8"))
    with open(f"{WORK}/{se_md5}.svg", "w", encoding="utf-8") as f: f.write(SHELL_ENEMY_SVG)
    cv_md5 = md5_bytes(COVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{cv_md5}.svg", "w", encoding="utf-8") as f: f.write(COVER_SVG)
    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f: f.write(GAME_OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    player_blocks   = build_player_blocks()
    shell_blocks    = build_shell_blocks()
    eshell_blocks   = build_enemy_shell_blocks()
    enemy_blocks    = build_enemy_blocks()
    cover_blocks    = build_cover_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE: ["점수", 0],
            V_HP:    ["체력", 3],
            V_ROUND: ["라운드", 1],
            V_STATE: ["게임상태", 1],
            V_ELEFT: ["잔여적", 0],
            V_ESPD:  ["적속도", 1.0],
            V_SX:    ["스폰X", 0],
            V_SY:    ["스폰Y", 0],
            V_BX:    ["포탄X", 0],
            V_BY:    ["포탄Y", 0],
            V_BDIR:  ["포탄방향", 90],
            V_BKIND: ["포탄종류", 0],
            V_INV:   ["무적", 0],
            V_CD:    ["쿨다운", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:  "게임시작",
            BR_ROUND:  "라운드시작",
            BR_ESPAWN: "적스폰",
            BR_COVER:  "엄폐물생성",
            BR_EFIRE:  "적사격",
            BR_CLRCOV: "엄폐물제거",
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

    player = {
        "isStage": False, "name": "플레이어탱크",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": player_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "tank", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": tp_md5, "md5ext": f"{tp_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": -120, "size": 75, "direction": 0,
        "draggable": False, "rotationStyle": "all around"
    }

    shell = {
        "isStage": False, "name": "포탄",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": shell_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "shell", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": sh_md5, "md5ext": f"{sh_md5}.svg",
            "rotationCenterX": 8, "rotationCenterY": 10
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    eshell = {
        "isStage": False, "name": "적포탄",
        "variables": {V_ESISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": eshell_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "eshell", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": se_md5, "md5ext": f"{se_md5}.svg",
            "rotationCenterX": 8, "rotationCenterY": 10
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    enemy = {
        "isStage": False, "name": "적탱크",
        "variables": {V_EISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "tank_enemy", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": te_md5, "md5ext": f"{te_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 75, "direction": 180,
        "draggable": False, "rotationStyle": "all around"
    }

    cover = {
        "isStage": False, "name": "엄폐물",
        "variables": {V_CVISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": cover_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "cover", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": cv_md5, "md5ext": f"{cv_md5}.svg",
            "rotationCenterX": 25, "rotationCenterY": 25
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
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
        {"id": V_HP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "체력"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 5, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_ELEFT, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "잔여적"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, player, shell, eshell, enemy, cover, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "tank-battle-builder"}
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
    print(f"  shell:    {len(shell_blocks)} blocks")
    print(f"  eshell:   {len(eshell_blocks)} blocks")
    print(f"  enemy:    {len(enemy_blocks)} blocks")
    print(f"  cover:    {len(cover_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(player_blocks) + len(shell_blocks) + len(eshell_blocks)
             + len(enemy_blocks) + len(cover_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
