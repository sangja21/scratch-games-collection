#!/usr/bin/env python3
"""Shuriken Throw — Ninja shoots spinning shuriken upward at patrolling targets.

Left/Right arrows move the ninja along the bottom.
Space or mouse click throws a shuriken upward (spins via motion_turnright).
Targets (bullseye / scroll / golden bell) drift left-right at the top.
Round-based progression: clear N targets to advance, speed scales up.
Cap at round 10 = "ninja master" banner.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "수리검_던지기.sb3")

# =====================================================================
#  BACKGROUND  (night sky + moon + stars + dark ground)
# =====================================================================
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="night" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#1A237E"/>
      <stop offset="55%"  stop-color="#311B92"/>
      <stop offset="100%" stop-color="#4A148C"/>
    </linearGradient>
    <radialGradient id="moonglow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%"   stop-color="#FFF59D" stop-opacity="0.85"/>
      <stop offset="60%"  stop-color="#FFF59D" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="#FFF59D" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="480" height="360" fill="url(#night)"/>
  <circle cx="400" cy="65" r="55" fill="url(#moonglow)"/>
  <circle cx="400" cy="65" r="32" fill="#FFF9C4"/>
  <circle cx="392" cy="58" r="6" fill="#FFE082" opacity="0.6"/>
  <circle cx="410" cy="75" r="4" fill="#FFE082" opacity="0.5"/>
  <g fill="#FFFFFF">
    <circle cx="40"  cy="50"  r="1.6" opacity="0.9"/>
    <circle cx="90"  cy="30"  r="1.2" opacity="0.7"/>
    <circle cx="140" cy="80"  r="1.8" opacity="0.95"/>
    <circle cx="200" cy="45"  r="1.3" opacity="0.7"/>
    <circle cx="260" cy="90"  r="1.5" opacity="0.85"/>
    <circle cx="310" cy="40"  r="1.1" opacity="0.7"/>
    <circle cx="60"  cy="120" r="1.4" opacity="0.85"/>
    <circle cx="180" cy="135" r="1.0" opacity="0.65"/>
    <circle cx="340" cy="120" r="1.6" opacity="0.9"/>
    <circle cx="450" cy="160" r="1.2" opacity="0.7"/>
  </g>
  <rect x="0" y="290" width="480" height="70" fill="#0D0D2B"/>
  <rect x="0" y="285" width="480" height="6" fill="#1A1A4D"/>
  <g fill="#1A1A4D" opacity="0.7">
    <rect x="20"  y="295" width="40" height="6"/>
    <rect x="120" y="300" width="60" height="5"/>
    <rect x="240" y="295" width="50" height="6"/>
    <rect x="360" y="302" width="70" height="5"/>
  </g>
</svg>"""

# =====================================================================
#  NINJA  (idle + throw)
# =====================================================================
NINJA_IDLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80" viewBox="0 0 60 80">
  <ellipse cx="30" cy="74" rx="22" ry="4" fill="#000000" opacity="0.45"/>
  <rect x="14" y="36" width="32" height="32" rx="5" fill="#212121"/>
  <rect x="14" y="44" width="32" height="6" fill="#B71C1C"/>
  <circle cx="30" cy="22" r="14" fill="#212121"/>
  <rect x="16" y="20" width="28" height="6" fill="#37474F"/>
  <ellipse cx="25" cy="23" rx="2.4" ry="1.4" fill="#FFFFFF"/>
  <ellipse cx="35" cy="23" rx="2.4" ry="1.4" fill="#FFFFFF"/>
  <circle cx="25" cy="23" r="1.1" fill="#000000"/>
  <circle cx="35" cy="23" r="1.1" fill="#000000"/>
  <rect x="6"  y="40" width="10" height="22" rx="3" fill="#212121"/>
  <rect x="44" y="40" width="10" height="22" rx="3" fill="#212121"/>
  <rect x="8"  y="58" width="8" height="8" rx="2" fill="#37474F"/>
  <rect x="44" y="58" width="8" height="8" rx="2" fill="#37474F"/>
  <rect x="16" y="64" width="12" height="12" rx="2" fill="#37474F"/>
  <rect x="32" y="64" width="12" height="12" rx="2" fill="#37474F"/>
  <polygon points="48,8 52,16 60,18 54,22 56,30 48,26 40,30 42,22 36,18 44,16"
           fill="#90A4AE" stroke="#37474F" stroke-width="0.6" opacity="0.9"/>
</svg>"""

NINJA_THROW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80" viewBox="0 0 60 80">
  <ellipse cx="30" cy="74" rx="22" ry="4" fill="#000000" opacity="0.45"/>
  <rect x="14" y="36" width="32" height="32" rx="5" fill="#212121"/>
  <rect x="14" y="44" width="32" height="6" fill="#B71C1C"/>
  <circle cx="30" cy="22" r="14" fill="#212121"/>
  <rect x="16" y="20" width="28" height="6" fill="#37474F"/>
  <ellipse cx="25" cy="23" rx="2.4" ry="1.4" fill="#FFFFFF"/>
  <ellipse cx="35" cy="23" rx="2.4" ry="1.4" fill="#FFFFFF"/>
  <circle cx="25" cy="23" r="1.1" fill="#000000"/>
  <circle cx="35" cy="23" r="1.1" fill="#000000"/>
  <rect x="32" y="6"  width="9" height="28" rx="3" fill="#212121" transform="rotate(18 36 20)"/>
  <rect x="44" y="40" width="10" height="22" rx="3" fill="#212121"/>
  <rect x="44" y="58" width="8" height="8" rx="2" fill="#37474F"/>
  <rect x="16" y="64" width="12" height="12" rx="2" fill="#37474F"/>
  <rect x="32" y="64" width="12" height="12" rx="2" fill="#37474F"/>
  <polygon points="48,4 52,12 60,14 54,18 56,26 48,22 40,26 42,18 36,14 44,12"
           fill="#90A4AE" stroke="#37474F" stroke-width="0.6"/>
</svg>"""

# =====================================================================
#  SHURIKEN  (4-pointed star, centered)
# =====================================================================
SHURIKEN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="30,2 36,24 58,30 36,36 30,58 24,36 2,30 24,24"
           fill="#B0BEC5" stroke="#263238" stroke-width="1.8"/>
  <polygon points="30,10 33,26 50,30 33,34 30,50 27,34 10,30 27,26"
           fill="#ECEFF1" opacity="0.55"/>
  <circle cx="30" cy="30" r="5" fill="#263238"/>
  <circle cx="30" cy="30" r="2" fill="#90A4AE"/>
</svg>"""

# =====================================================================
#  TARGETS
# =====================================================================
TARGET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="70" height="70" viewBox="0 0 70 70">
  <circle cx="35" cy="35" r="33" fill="#FFFFFF" stroke="#212121" stroke-width="1.5"/>
  <circle cx="35" cy="35" r="27" fill="#D50000"/>
  <circle cx="35" cy="35" r="21" fill="#FFFFFF"/>
  <circle cx="35" cy="35" r="15" fill="#D50000"/>
  <circle cx="35" cy="35" r="9"  fill="#FFFFFF"/>
  <circle cx="35" cy="35" r="4"  fill="#D50000"/>
</svg>"""

SCROLL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="90" height="60" viewBox="0 0 90 60">
  <rect x="10" y="14" width="70" height="32" fill="#FFECB3" stroke="#5D4037" stroke-width="1.2"/>
  <rect x="10" y="16" width="70" height="3"  fill="#D7CCC8"/>
  <rect x="10" y="42" width="70" height="3"  fill="#D7CCC8"/>
  <rect x="4"  y="10" width="12" height="40" rx="6" fill="#6D4C41" stroke="#3E2723" stroke-width="1"/>
  <rect x="74" y="10" width="12" height="40" rx="6" fill="#6D4C41" stroke="#3E2723" stroke-width="1"/>
  <g fill="#3E2723">
    <rect x="22" y="22" width="14" height="2"/>
    <rect x="22" y="28" width="20" height="2"/>
    <rect x="22" y="34" width="16" height="2"/>
    <rect x="46" y="22" width="18" height="2"/>
    <rect x="46" y="28" width="14" height="2"/>
    <rect x="46" y="34" width="20" height="2"/>
  </g>
</svg>"""

BELL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80" viewBox="0 0 60 80">
  <defs>
    <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#FFE082"/>
      <stop offset="50%"  stop-color="#FFC107"/>
      <stop offset="100%" stop-color="#FF8F00"/>
    </linearGradient>
  </defs>
  <path d="M 30 8 Q 12 18 12 50 L 12 58 L 48 58 L 48 50 Q 48 18 30 8 Z"
        fill="url(#gold)" stroke="#5D4037" stroke-width="1.5"/>
  <rect x="8" y="58" width="44" height="6" rx="2" fill="#FFB300" stroke="#5D4037" stroke-width="1.2"/>
  <ellipse cx="30" cy="70" rx="5" ry="6" fill="#5D4037"/>
  <ellipse cx="22" cy="28" rx="3" ry="8" fill="#FFF59D" opacity="0.8"/>
  <circle cx="30" cy="6" r="3" fill="#FFB300" stroke="#5D4037" stroke-width="1"/>
</svg>"""

HIT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <polygon points="50,5 58,38 92,38 64,58 76,92 50,72 24,92 36,58 8,38 42,38"
           fill="#FFEB3B" stroke="#F57F17" stroke-width="2.5"/>
  <polygon points="50,18 55,40 78,42 60,55 68,78 50,65 32,78 40,55 22,42 45,40"
           fill="#FFFFFF" opacity="0.85"/>
  <text x="50" y="60" text-anchor="middle"
        fill="#D50000" font-family="Arial" font-size="20" font-weight="bold">HIT!</text>
</svg>"""

# =====================================================================
#  ROUND BANNERS
# =====================================================================
ROUND_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="320" height="100" viewBox="0 0 320 100">
  <rect x="5" y="5" width="310" height="90" rx="14"
        fill="#000000" opacity="0.85"
        stroke="#FFEB3B" stroke-width="3"/>
  <text x="160" y="50" text-anchor="middle"
        fill="#FFEB3B" font-family="Arial, Helvetica, sans-serif"
        font-size="34" font-weight="bold">NEXT ROUND!</text>
  <text x="160" y="80" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">표적이 더 빨라집니다</text>
</svg>"""

MASTER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="380" height="180" viewBox="0 0 380 180">
  <defs>
    <linearGradient id="ngold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#FFE082"/>
      <stop offset="100%" stop-color="#FF8F00"/>
    </linearGradient>
  </defs>
  <rect x="5" y="5" width="370" height="170" rx="16"
        fill="#1A1A2E" opacity="0.95"
        stroke="url(#ngold)" stroke-width="5"/>
  <text x="190" y="65" text-anchor="middle"
        fill="url(#ngold)" font-family="Arial, Helvetica, sans-serif"
        font-size="42" font-weight="bold">NINJA MASTER!</text>
  <text x="190" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="22">라운드 10 클리어</text>
  <text x="190" y="148" text-anchor="middle"
        fill="#FFCC80" font-family="Arial, Helvetica, sans-serif"
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

# --- Variable / broadcast IDs ---
V_SCORE   = "varScore01"
V_ROUND   = "varRound02"
V_KILLS   = "varKills03"
V_TARGET  = "varTarget04"
V_TSPEED  = "varTSpeed05"
V_SPAWNED = "varSpawned06"
V_STATE   = "varState07"
V_SX      = "varSX08"
V_SY      = "varSY09"
V_TKIND   = "varTKind10"
V_TSX     = "varTStartX11"
V_TSY     = "varTStartY12"
V_TDIR    = "varTDir13"

LV_KIND   = "lvKind01"
LV_SPEED  = "lvSpeed02"
LV_DIR    = "lvDir03"
LV_SCORE  = "lvScore04"

BR_START  = "brStart01"
BR_SPAWN  = "brSpawn02"
BR_FIRE   = "brFire03"
BR_NEXT   = "brNext04"
BR_MASTER = "brMaster05"

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
        (("점수",     V_SCORE),  0),
        (("라운드",   V_ROUND),  1),
        (("처치수",   V_KILLS),  0),
        (("라운드목표", V_TARGET), 5),
        (("표적속도", V_TSPEED), 2.5),
        (("스폰수",   V_SPAWNED), 0),
        (("게임상태", V_STATE),  1),
        (("수리검X",  V_SX),     0),
        (("수리검Y",  V_SY),    -110),
        (("표적종류", V_TKIND),  1),
        (("표적X시작", V_TSX),  -220),
        (("표적Y시작", V_TSY),   110),
        (("표적방향", V_TDIR),   1),
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

    # ----- B) on 게임시작: spawn loop forever -----
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=420,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # condition: 게임상태=1 AND 스폰수 < 라운드목표
    state_v = vrep("게임상태", V_STATE)
    cond_alive = cmp_op("operator_equals", state_v, 1)
    spawned_v = vrep("스폰수", V_SPAWNED); target_v = vrep("라운드목표", V_TARGET)
    cond_need = cmp_op("operator_lt", spawned_v, target_v)
    cond_both = bool_op("operator_and", cond_alive, cond_need)

    # draw one random 1..10 into 표적종류 (single draw — shared for both thresholds)
    rand_k = op("operator_random", 1, 10, key1="FROM", key2="TO")
    set_kind = gen(); bs[set_kind] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_k)}, fields={"VARIABLE": ["표적종류", V_TKIND]})
    bs[rand_k]["parent"] = set_kind

    # Use if-else chain against the stored value to get correct 60/30/10 distribution:
    #   표적종류 > 9  → 3 (bell,   10%)
    #   표적종류 > 6  → 2 (scroll, 30%)
    #   else         → 1 (target, 60%)
    # Check > 9 first (sets 3); inner else checks > 6 (sets 2); innermost else sets 1.

    # innermost else branch: set 표적종류 = 1
    set_kind_one = gen(); bs[set_kind_one] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["표적종류", V_TKIND]})

    # middle branch: set 표적종류 = 2
    set_k2 = gen(); bs[set_k2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["표적종류", V_TKIND]})

    # inner if-else: if 표적종류 > 6 → set 2; else → set 1
    kv_a = vrep("표적종류", V_TKIND)
    cond_gt6 = cmp_op("operator_gt", kv_a, 6)
    if_gt6 = gen(); bs[if_gt6] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_gt6], "SUBSTACK": [2, set_k2], "SUBSTACK2": [2, set_kind_one]})
    bs[cond_gt6]["parent"] = if_gt6
    bs[set_k2]["parent"] = if_gt6
    bs[set_kind_one]["parent"] = if_gt6

    # outer branch: set 표적종류 = 3
    set_k3 = gen(); bs[set_k3] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["표적종류", V_TKIND]})

    # outer if-else: if 표적종류 > 9 → set 3; else → inner if-else
    kv_b = vrep("표적종류", V_TKIND)
    cond_gt9 = cmp_op("operator_gt", kv_b, 9)
    if_gt9 = gen(); bs[if_gt9] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_gt9], "SUBSTACK": [2, set_k3], "SUBSTACK2": [2, if_gt6]})
    bs[cond_gt9]["parent"] = if_gt9
    bs[set_k3]["parent"] = if_gt9
    bs[if_gt6]["parent"] = if_gt9

    # 표적방향 = (random 0..1 * 2) - 1 → -1 or 1
    rand_d = op("operator_random", 0, 1, key1="FROM", key2="TO")
    mul_d = op("operator_multiply", rand_d, 2)
    sub_d = op("operator_subtract", mul_d, 1)
    # Force integer: round(...)
    round_d = gen(); bs[round_d] = mk("operator_round", inputs={"NUM": slot(sub_d)})
    bs[sub_d]["parent"] = round_d
    # If round result is 0, force to 1 — but range -1..1 rounds to -1 or 0 or 1.
    # Simpler: set 표적방향 = round(rand 0..1)*2 - 1 → outputs -1 or 1
    set_dir = gen(); bs[set_dir] = mk("data_setvariableto",
        inputs={"VALUE": slot(round_d)}, fields={"VARIABLE": ["표적방향", V_TDIR]})
    bs[round_d]["parent"] = set_dir

    # If 표적방향 = 0, set to 1 (safety)
    dv = vrep("표적방향", V_TDIR)
    cond_d_zero = cmp_op("operator_equals", dv, 0)
    set_d_one = gen(); bs[set_d_one] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["표적방향", V_TDIR]})
    if_d_zero = gen(); bs[if_d_zero] = mk("control_if",
        inputs={"CONDITION": [2, cond_d_zero], "SUBSTACK": [2, set_d_one]})
    bs[cond_d_zero]["parent"] = if_d_zero; bs[set_d_one]["parent"] = if_d_zero

    # 표적X시작 = (표적방향 = 1) ? -220 : 220 → default 220, then if dir=1 set -220
    set_tsx_def = gen(); bs[set_tsx_def] = mk("data_setvariableto",
        inputs={"VALUE": num(220)}, fields={"VARIABLE": ["표적X시작", V_TSX]})
    dv2 = vrep("표적방향", V_TDIR)
    cond_d_pos = cmp_op("operator_equals", dv2, 1)
    set_tsx_neg = gen(); bs[set_tsx_neg] = mk("data_setvariableto",
        inputs={"VALUE": num(-220)}, fields={"VARIABLE": ["표적X시작", V_TSX]})
    if_d_pos = gen(); bs[if_d_pos] = mk("control_if",
        inputs={"CONDITION": [2, cond_d_pos], "SUBSTACK": [2, set_tsx_neg]})
    bs[cond_d_pos]["parent"] = if_d_pos; bs[set_tsx_neg]["parent"] = if_d_pos

    # 표적Y시작 = random 70..150
    rand_y = op("operator_random", 70, 150, key1="FROM", key2="TO")
    set_tsy = gen(); bs[set_tsy] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_y)}, fields={"VARIABLE": ["표적Y시작", V_TSY]})
    bs[rand_y]["parent"] = set_tsy

    # broadcast 표적스폰
    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["표적스폰", BR_SPAWN]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    inc_spawned = gen(); bs[inc_spawned] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["스폰수", V_SPAWNED]})

    # wait = max(0.5, 1.4 - 라운드 * 0.08)
    # Scratch has no native max block; implement as if-else on the computed value:
    #   if (1.4 - 라운드 * 0.08) < 0.5 → wait 0.5
    #                              else → wait (1.4 - 라운드 * 0.08)
    rv_a = vrep("라운드", V_ROUND)
    mul_rd = op("operator_multiply", rv_a, 0.08)
    sub_rd = op("operator_subtract", 1.4, mul_rd)
    rv_a2 = vrep("라운드", V_ROUND)
    mul_rd2 = op("operator_multiply", rv_a2, 0.08)
    sub_rd2 = op("operator_subtract", 1.4, mul_rd2)
    cond_clamp = cmp_op("operator_lt", sub_rd, 0.5)
    wt_floor = gen(); bs[wt_floor] = mk("control_wait", inputs={"DURATION": num(0.5)})
    wt_sp = gen(); bs[wt_sp] = mk("control_wait", inputs={"DURATION": slot(sub_rd2)})
    bs[sub_rd2]["parent"] = wt_sp
    if_clamp = gen(); bs[if_clamp] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_clamp], "SUBSTACK": [2, wt_floor], "SUBSTACK2": [2, wt_sp]})
    bs[cond_clamp]["parent"] = if_clamp
    bs[wt_floor]["parent"] = if_clamp
    bs[wt_sp]["parent"] = if_clamp

    # chain body of if_alive (set_kind draws one random; if_gt9 branches to if_gt6 or set_k3)
    chain([(set_kind, bs[set_kind]),
           (if_gt9, bs[if_gt9]),
           (set_dir, bs[set_dir]),
           (if_d_zero, bs[if_d_zero]),
           (set_tsx_def, bs[set_tsx_def]),
           (if_d_pos, bs[if_d_pos]),
           (set_tsy, bs[set_tsy]),
           (bc_sp, bs[bc_sp]),
           (inc_spawned, bs[inc_spawned]),
           (if_clamp, bs[if_clamp])])

    if_alive = gen(); bs[if_alive] = mk("control_if",
        inputs={"CONDITION": [2, cond_both], "SUBSTACK": [2, set_kind]})
    bs[cond_both]["parent"] = if_alive
    bs[set_kind]["parent"] = if_alive

    # idle wait outside if
    w_idle = gen(); bs[w_idle] = mk("control_wait", inputs={"DURATION": num(0.1)})
    chain([(if_alive, bs[if_alive]), (w_idle, bs[w_idle])])

    forever_sp = gen(); bs[forever_sp] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_alive]})
    bs[if_alive]["parent"] = forever_sp
    chain([(h2, bs[h2]), (forever_sp, bs[forever_sp])])

    # ----- C) 다음라운드 받으면 -----
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=920,
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]})

    inc_round = gen(); bs[inc_round] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
    # 표적속도 ×1.15: set 표적속도 = 표적속도 * 1.15
    sv = vrep("표적속도", V_TSPEED)
    new_spd = op("operator_multiply", sv, 1.15)
    set_spd = gen(); bs[set_spd] = mk("data_setvariableto",
        inputs={"VALUE": slot(new_spd)}, fields={"VARIABLE": ["표적속도", V_TSPEED]})
    bs[new_spd]["parent"] = set_spd

    inc_tgt = gen(); bs[inc_tgt] = mk("data_changevariableby",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["라운드목표", V_TARGET]})
    reset_kills = gen(); bs[reset_kills] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["처치수", V_KILLS]})
    reset_spawned = gen(); bs[reset_spawned] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["스폰수", V_SPAWNED]})
    wt_round = gen(); bs[wt_round] = mk("control_wait", inputs={"DURATION": num(1.5)})

    chain([(h3, bs[h3]), (inc_round, bs[inc_round]), (set_spd, bs[set_spd]),
           (inc_tgt, bs[inc_tgt]), (reset_kills, bs[reset_kills]),
           (reset_spawned, bs[reset_spawned]), (wt_round, bs[wt_round])])

    # ----- D) 마스터 받으면 → 게임상태 = 2 -----
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=20, y=1180,
        fields={"BROADCAST_OPTION": ["마스터", BR_MASTER]})
    set_state2 = gen(); bs[set_state2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    chain([(h4, bs[h4]), (set_state2, bs[set_state2])])

    return bs

# =====================================================================
#  NINJA  (player)
# =====================================================================
def build_ninja_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ----- flag: init -----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-130)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    cm_idle0 = gen(); bs[cm_idle0] = mk("looks_costume",
        fields={"COSTUME": ["idle", None]}, shadow=True)
    sw_idle0 = gen(); bs[sw_idle0] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_idle0]})
    bs[cm_idle0]["parent"] = sw_idle0
    set_dir90 = gen(); bs[set_dir90] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["left-right", None]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sw_idle0, bs[sw_idle0]),
           (set_dir90, bs[set_dir90]), (rs, bs[rs]), (show, bs[show])])

    # ----- forever (movement) -----
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=20, y=300)

    # if left key pressed → change x by -4
    km_left = gen(); bs[km_left] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    kp_left = gen(); bs[kp_left] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, km_left]})
    bs[km_left]["parent"] = kp_left
    chx_l = gen(); bs[chx_l] = mk("motion_changexby", inputs={"DX": num(-4)})
    if_left = gen(); bs[if_left] = mk("control_if",
        inputs={"CONDITION": [2, kp_left], "SUBSTACK": [2, chx_l]})
    bs[kp_left]["parent"] = if_left; bs[chx_l]["parent"] = if_left

    km_right = gen(); bs[km_right] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    kp_right = gen(); bs[kp_right] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, km_right]})
    bs[km_right]["parent"] = kp_right
    chx_r = gen(); bs[chx_r] = mk("motion_changexby", inputs={"DX": num(4)})
    if_right = gen(); bs[if_right] = mk("control_if",
        inputs={"CONDITION": [2, kp_right], "SUBSTACK": [2, chx_r]})
    bs[kp_right]["parent"] = if_right; bs[chx_r]["parent"] = if_right

    # clamp x: if x < -210 → set x to -210
    xp_a = gen(); bs[xp_a] = mk("motion_xposition")
    cond_xlow = cmp_op("operator_lt", xp_a, -210)
    set_xneg = gen(); bs[set_xneg] = mk("motion_setx", inputs={"X": num(-210)})
    if_xlow = gen(); bs[if_xlow] = mk("control_if",
        inputs={"CONDITION": [2, cond_xlow], "SUBSTACK": [2, set_xneg]})
    bs[cond_xlow]["parent"] = if_xlow; bs[set_xneg]["parent"] = if_xlow

    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cond_xhi = cmp_op("operator_gt", xp_b, 210)
    set_xpos = gen(); bs[set_xpos] = mk("motion_setx", inputs={"X": num(210)})
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, cond_xhi], "SUBSTACK": [2, set_xpos]})
    bs[cond_xhi]["parent"] = if_xhi; bs[set_xpos]["parent"] = if_xhi

    chain([(if_left, bs[if_left]), (if_right, bs[if_right]),
           (if_xlow, bs[if_xlow]), (if_xhi, bs[if_xhi])])
    forever_mv = gen(); bs[forever_mv] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_left]})
    bs[if_left]["parent"] = forever_mv
    chain([(h2, bs[h2]), (forever_mv, bs[forever_mv])])

    # ----- forever (fire input) -----
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=320, y=20)

    # mouse down OR space pressed
    md = gen(); bs[md] = mk("sensing_mousedown")
    km_sp = gen(); bs[km_sp] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    kp_sp = gen(); bs[kp_sp] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, km_sp]})
    bs[km_sp]["parent"] = kp_sp
    or_fire = bool_op("operator_or", md, kp_sp)

    # AND 게임상태 = 1
    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)
    and_fire = bool_op("operator_and", or_fire, cond_play)

    # body: switch to throw, set 수리검X/Y, broadcast 사격, wait, switch back, wait
    cm_thr = gen(); bs[cm_thr] = mk("looks_costume",
        fields={"COSTUME": ["throw", None]}, shadow=True)
    sw_thr = gen(); bs[sw_thr] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_thr]})
    bs[cm_thr]["parent"] = sw_thr

    xp_c = gen(); bs[xp_c] = mk("motion_xposition")
    set_sx = gen(); bs[set_sx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xp_c)}, fields={"VARIABLE": ["수리검X", V_SX]})
    bs[xp_c]["parent"] = set_sx

    yp_a = gen(); bs[yp_a] = mk("motion_yposition")
    add_sy = op("operator_add", yp_a, 20)
    set_sy = gen(); bs[set_sy] = mk("data_setvariableto",
        inputs={"VALUE": slot(add_sy)}, fields={"VARIABLE": ["수리검Y", V_SY]})
    bs[add_sy]["parent"] = set_sy

    bm_fire = gen(); bs[bm_fire] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["사격", BR_FIRE]}, shadow=True)
    bc_fire = gen(); bs[bc_fire] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_fire]})
    bs[bm_fire]["parent"] = bc_fire

    wt_thr = gen(); bs[wt_thr] = mk("control_wait", inputs={"DURATION": num(0.1)})
    cm_idle1 = gen(); bs[cm_idle1] = mk("looks_costume",
        fields={"COSTUME": ["idle", None]}, shadow=True)
    sw_idle1 = gen(); bs[sw_idle1] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_idle1]})
    bs[cm_idle1]["parent"] = sw_idle1
    wt_cool = gen(); bs[wt_cool] = mk("control_wait", inputs={"DURATION": num(0.12)})

    chain([(sw_thr, bs[sw_thr]), (set_sx, bs[set_sx]), (set_sy, bs[set_sy]),
           (bc_fire, bs[bc_fire]), (wt_thr, bs[wt_thr]),
           (sw_idle1, bs[sw_idle1]), (wt_cool, bs[wt_cool])])

    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, and_fire], "SUBSTACK": [2, sw_thr]})
    bs[and_fire]["parent"] = if_fire; bs[sw_thr]["parent"] = if_fire

    # small wait so forever doesn't spin
    w_idle_fire = gen(); bs[w_idle_fire] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(if_fire, bs[if_fire]), (w_idle_fire, bs[w_idle_fire])])

    forever_fire = gen(); bs[forever_fire] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_fire]})
    bs[if_fire]["parent"] = forever_fire
    chain([(h3, bs[h3]), (forever_fire, bs[forever_fire])])

    return bs

# =====================================================================
#  SHURIKEN  (clone)
# =====================================================================
def build_shuriken_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ----- flag: setup -----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(50)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    # ----- on 사격: create clone of myself -----
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["사격", BR_FIRE]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cmenu]
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(h2, bs[h2]), (cclone, bs[cclone])])

    # ----- clone start: position, fire pop, rise + spin -----
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=300, y=20)
    sx_v = vrep("수리검X", V_SX); sy_v = vrep("수리검Y", V_SY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(sx_v), "Y": slot(sy_v)})
    bs[sx_v]["parent"] = g; bs[sy_v]["parent"] = g

    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(0)})
    show = gen(); bs[show] = mk("looks_show")

    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(250)}, fields={"EFFECT": ["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU": [1, snm]})
    bs[snm]["parent"] = snd

    # rise loop: repeat until (y > 180 OR touching 표적)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": num(14)})
    turn = gen(); bs[turn] = mk("motion_turnright", inputs={"DEGREES": num(25)})
    wt_step = gen(); bs[wt_step] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(chy, bs[chy]), (turn, bs[turn]), (wt_step, bs[wt_step])])

    yp_a = gen(); bs[yp_a] = mk("motion_yposition")
    cond_top = cmp_op("operator_gt", yp_a, 180)

    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["표적", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm]})
    bs[tm]["parent"] = tc

    or_end = bool_op("operator_or", cond_top, tc)

    repeat_until = gen(); bs[repeat_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, or_end], "SUBSTACK": [2, chy]})
    bs[or_end]["parent"] = repeat_until
    bs[chy]["parent"] = repeat_until

    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (pd, bs[pd]), (show, bs[show]),
           (pitch, bs[pitch]), (snd, bs[snd]),
           (repeat_until, bs[repeat_until]), (hi2, bs[hi2]), (delc, bs[delc])])

    return bs

# =====================================================================
#  TARGET  (clone)
# =====================================================================
def build_target_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ----- flag: hide master -----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(110)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["don't rotate", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g0, bs[g0]), (rs, bs[rs])])

    # ----- on 표적스폰: create clone of myself -----
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["표적스폰", BR_SPAWN]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(h2, bs[h2]), (cclone, bs[cclone])])

    # ----- clone start: configure per kind, then patrol -----
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=300, y=20)

    # copy globals → locals
    kg_v = vrep("표적종류", V_TKIND)
    set_kind_l = gen(); bs[set_kind_l] = mk("data_setvariableto",
        inputs={"VALUE": slot(kg_v)}, fields={"VARIABLE": ["내종류", LV_KIND]})
    bs[kg_v]["parent"] = set_kind_l

    sg_v = vrep("표적속도", V_TSPEED)
    set_spd_l = gen(); bs[set_spd_l] = mk("data_setvariableto",
        inputs={"VALUE": slot(sg_v)}, fields={"VARIABLE": ["내속도", LV_SPEED]})
    bs[sg_v]["parent"] = set_spd_l

    dg_v = vrep("표적방향", V_TDIR)
    set_dir_l = gen(); bs[set_dir_l] = mk("data_setvariableto",
        inputs={"VALUE": slot(dg_v)}, fields={"VARIABLE": ["내방향", LV_DIR]})
    bs[dg_v]["parent"] = set_dir_l

    set_score_def = gen(); bs[set_score_def] = mk("data_setvariableto",
        inputs={"VALUE": num(10)}, fields={"VARIABLE": ["내점수", LV_SCORE]})

    # default look: target
    cm_tgt = gen(); bs[cm_tgt] = mk("looks_costume",
        fields={"COSTUME": ["target", None]}, shadow=True)
    sw_tgt = gen(); bs[sw_tgt] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_tgt]})
    bs[cm_tgt]["parent"] = sw_tgt
    set_size_def = gen(); bs[set_size_def] = mk("looks_setsizeto", inputs={"SIZE": num(70)})

    # if 내종류 = 2 → scroll setup
    k_v_a = vrep("내종류", LV_KIND)
    cond_k2 = cmp_op("operator_equals", k_v_a, 2)
    cm_sc = gen(); bs[cm_sc] = mk("looks_costume",
        fields={"COSTUME": ["scroll", None]}, shadow=True)
    sw_sc = gen(); bs[sw_sc] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_sc]})
    bs[cm_sc]["parent"] = sw_sc
    set_size_sc = gen(); bs[set_size_sc] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    set_score_sc = gen(); bs[set_score_sc] = mk("data_setvariableto",
        inputs={"VALUE": num(15)}, fields={"VARIABLE": ["내점수", LV_SCORE]})
    sp_v_a = vrep("내속도", LV_SPEED)
    mul_spd_sc = op("operator_multiply", sp_v_a, 0.85)
    set_spd_sc = gen(); bs[set_spd_sc] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_spd_sc)}, fields={"VARIABLE": ["내속도", LV_SPEED]})
    bs[mul_spd_sc]["parent"] = set_spd_sc
    chain([(sw_sc, bs[sw_sc]), (set_size_sc, bs[set_size_sc]),
           (set_score_sc, bs[set_score_sc]), (set_spd_sc, bs[set_spd_sc])])
    if_k2 = gen(); bs[if_k2] = mk("control_if",
        inputs={"CONDITION": [2, cond_k2], "SUBSTACK": [2, sw_sc]})
    bs[cond_k2]["parent"] = if_k2; bs[sw_sc]["parent"] = if_k2

    # if 내종류 = 3 → bell setup
    k_v_b = vrep("내종류", LV_KIND)
    cond_k3 = cmp_op("operator_equals", k_v_b, 3)
    cm_bl = gen(); bs[cm_bl] = mk("looks_costume",
        fields={"COSTUME": ["bell", None]}, shadow=True)
    sw_bl = gen(); bs[sw_bl] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_bl]})
    bs[cm_bl]["parent"] = sw_bl
    set_size_bl = gen(); bs[set_size_bl] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    set_score_bl = gen(); bs[set_score_bl] = mk("data_setvariableto",
        inputs={"VALUE": num(30)}, fields={"VARIABLE": ["내점수", LV_SCORE]})
    sp_v_b = vrep("내속도", LV_SPEED)
    mul_spd_bl = op("operator_multiply", sp_v_b, 1.2)
    set_spd_bl = gen(); bs[set_spd_bl] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_spd_bl)}, fields={"VARIABLE": ["내속도", LV_SPEED]})
    bs[mul_spd_bl]["parent"] = set_spd_bl
    chain([(sw_bl, bs[sw_bl]), (set_size_bl, bs[set_size_bl]),
           (set_score_bl, bs[set_score_bl]), (set_spd_bl, bs[set_spd_bl])])
    if_k3 = gen(); bs[if_k3] = mk("control_if",
        inputs={"CONDITION": [2, cond_k3], "SUBSTACK": [2, sw_bl]})
    bs[cond_k3]["parent"] = if_k3; bs[sw_bl]["parent"] = if_k3

    # go to (표적X시작, 표적Y시작), show
    tx_v = vrep("표적X시작", V_TSX); ty_v = vrep("표적Y시작", V_TSY)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(tx_v), "Y": slot(ty_v)})
    bs[tx_v]["parent"] = g_init; bs[ty_v]["parent"] = g_init
    show_c = gen(); bs[show_c] = mk("looks_show")

    # ---- patrol loop body (movement + bounce + game-state guard) ----
    sp_v_loop = vrep("내속도", LV_SPEED)
    dir_v_loop = vrep("내방향", LV_DIR)
    mul_step = op("operator_multiply", sp_v_loop, dir_v_loop)
    chx = gen(); bs[chx] = mk("motion_changexby", inputs={"DX": slot(mul_step)})
    bs[mul_step]["parent"] = chx

    # if x > 220 → 내방향 = -1
    xp_a = gen(); bs[xp_a] = mk("motion_xposition")
    cond_xhi = cmp_op("operator_gt", xp_a, 220)
    set_dir_neg = gen(); bs[set_dir_neg] = mk("data_setvariableto",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["내방향", LV_DIR]})
    if_xhi = gen(); bs[if_xhi] = mk("control_if",
        inputs={"CONDITION": [2, cond_xhi], "SUBSTACK": [2, set_dir_neg]})
    bs[cond_xhi]["parent"] = if_xhi; bs[set_dir_neg]["parent"] = if_xhi

    # if x < -220 → 내방향 = 1
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cond_xlo = cmp_op("operator_lt", xp_b, -220)
    set_dir_pos = gen(); bs[set_dir_pos] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["내방향", LV_DIR]})
    if_xlo = gen(); bs[if_xlo] = mk("control_if",
        inputs={"CONDITION": [2, cond_xlo], "SUBSTACK": [2, set_dir_pos]})
    bs[cond_xlo]["parent"] = if_xlo; bs[set_dir_pos]["parent"] = if_xlo

    wt_step = gen(); bs[wt_step] = mk("control_wait", inputs={"DURATION": num(0.025)})

    # game-state guard inside patrol loop: if 게임상태 ≠ 1 → 숨기기 + 클론 삭제
    # not(게임상태 = 1) to detect game-over / restart mid-round
    gs_v = vrep("게임상태", V_STATE)
    cond_gs_eq1 = cmp_op("operator_equals", gs_v, 1)
    guard_not = gen(); bs[guard_not] = mk("operator_not",
        inputs={"OPERAND": [2, cond_gs_eq1]})
    bs[cond_gs_eq1]["parent"] = guard_not
    hi_guard = gen(); bs[hi_guard] = mk("looks_hide")
    del_guard = gen(); bs[del_guard] = mk("control_delete_this_clone")
    chain([(hi_guard, bs[hi_guard]), (del_guard, bs[del_guard])])
    if_guard = gen(); bs[if_guard] = mk("control_if",
        inputs={"CONDITION": [2, guard_not], "SUBSTACK": [2, hi_guard]})
    bs[guard_not]["parent"] = if_guard
    bs[hi_guard]["parent"] = if_guard

    chain([(chx, bs[chx]), (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (wt_step, bs[wt_step]), (if_guard, bs[if_guard])])

    # repeat until touching 수리검
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["수리검", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm]})
    bs[tm]["parent"] = tc

    repeat_until = gen(); bs[repeat_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, tc], "SUBSTACK": [2, chx]})
    bs[tc]["parent"] = repeat_until
    bs[chx]["parent"] = repeat_until

    # ---- on hit ----
    cm_hit = gen(); bs[cm_hit] = mk("looks_costume",
        fields={"COSTUME": ["hit", None]}, shadow=True)
    sw_hit = gen(); bs[sw_hit] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_hit]})
    bs[cm_hit]["parent"] = sw_hit
    set_hit_size = gen(); bs[set_hit_size] = mk("looks_setsizeto", inputs={"SIZE": num(90)})

    sc_v = vrep("내점수", LV_SCORE)
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": slot(sc_v)}, fields={"VARIABLE": ["점수", V_SCORE]})
    bs[sc_v]["parent"] = inc_score

    inc_kills = gen(); bs[inc_kills] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["처치수", V_KILLS]})

    pitch0 = gen(); bs[pitch0] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU": [1, snm]})
    bs[snm]["parent"] = snd

    wt_hit = gen(); bs[wt_hit] = mk("control_wait", inputs={"DURATION": num(0.18)})

    # if 처치수 >= 라운드목표 → if 라운드 >= 10 → 마스터 else → 다음라운드
    kv = vrep("처치수", V_KILLS); tv = vrep("라운드목표", V_TARGET)
    cond_done = cmp_op("operator_gt", kv, op_minus_one := op("operator_subtract", tv, 1))
    # The above creates "처치수 > (라운드목표 - 1)" == "처치수 >= 라운드목표"

    rv = vrep("라운드", V_ROUND)
    cond_master = cmp_op("operator_gt", rv, 9)  # round > 9 = round >= 10

    bm_master = gen(); bs[bm_master] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["마스터", BR_MASTER]}, shadow=True)
    bc_master = gen(); bs[bc_master] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_master]})
    bs[bm_master]["parent"] = bc_master

    bm_next = gen(); bs[bm_next] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]}, shadow=True)
    bc_next = gen(); bs[bc_next] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_next]})
    bs[bm_next]["parent"] = bc_next

    if_else_master = gen(); bs[if_else_master] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_master],
                "SUBSTACK":  [2, bc_master],
                "SUBSTACK2": [2, bc_next]})
    bs[cond_master]["parent"] = if_else_master
    bs[bc_master]["parent"] = if_else_master
    bs[bc_next]["parent"] = if_else_master

    if_done = gen(); bs[if_done] = mk("control_if",
        inputs={"CONDITION": [2, cond_done], "SUBSTACK": [2, if_else_master]})
    bs[cond_done]["parent"] = if_done
    bs[if_else_master]["parent"] = if_done

    hi_c = gen(); bs[hi_c] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(sw_hit, bs[sw_hit]), (set_hit_size, bs[set_hit_size]),
           (inc_score, bs[inc_score]), (inc_kills, bs[inc_kills]),
           (pitch0, bs[pitch0]), (snd, bs[snd]), (wt_hit, bs[wt_hit]),
           (if_done, bs[if_done]), (hi_c, bs[hi_c]), (delc, bs[delc])])

    # chain clone start
    chain([(ch, bs[ch]), (set_kind_l, bs[set_kind_l]), (set_spd_l, bs[set_spd_l]),
           (set_dir_l, bs[set_dir_l]), (set_score_def, bs[set_score_def]),
           (sw_tgt, bs[sw_tgt]), (set_size_def, bs[set_size_def]),
           (if_k2, bs[if_k2]), (if_k3, bs[if_k3]),
           (g_init, bs[g_init]), (show_c, bs[show_c]),
           (repeat_until, bs[repeat_until]),
           (sw_hit, bs[sw_hit])])

    return bs

# =====================================================================
#  ROUND BANNER
# =====================================================================
def build_banner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ----- flag: hide, center -----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    # ----- on 다음라운드: show round banner briefly -----
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]})
    cm_rd = gen(); bs[cm_rd] = mk("looks_costume",
        fields={"COSTUME": ["round", None]}, shadow=True)
    sw_rd = gen(); bs[sw_rd] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_rd]})
    bs[cm_rd]["parent"] = sw_rd
    show2 = gen(); bs[show2] = mk("looks_show")
    wt2 = gen(); bs[wt2] = mk("control_wait", inputs={"DURATION": num(0.9)})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(h2, bs[h2]), (sw_rd, bs[sw_rd]), (show2, bs[show2]), (wt2, bs[wt2]), (hi2, bs[hi2])])

    # ----- on 마스터: show master banner forever -----
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=440,
        fields={"BROADCAST_OPTION": ["마스터", BR_MASTER]})
    cm_ms = gen(); bs[cm_ms] = mk("looks_costume",
        fields={"COSTUME": ["master", None]}, shadow=True)
    sw_ms = gen(); bs[sw_ms] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_ms]})
    bs[cm_ms]["parent"] = sw_ms
    show3 = gen(); bs[show3] = mk("looks_show")
    chain([(h3, bs[h3]), (sw_ms, bs[sw_ms]), (show3, bs[show3])])

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

    bg_md5     = emit_svg(BG_SVG)
    n_idle_md5 = emit_svg(NINJA_IDLE_SVG)
    n_thr_md5  = emit_svg(NINJA_THROW_SVG)
    sh_md5     = emit_svg(SHURIKEN_SVG)
    tg_md5     = emit_svg(TARGET_SVG)
    sc_md5     = emit_svg(SCROLL_SVG)
    bl_md5     = emit_svg(BELL_SVG)
    hit_md5    = emit_svg(HIT_SVG)
    rd_md5     = emit_svg(ROUND_SVG)
    ms_md5     = emit_svg(MASTER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    ninja_blocks    = build_ninja_blocks()
    shuriken_blocks = build_shuriken_blocks()
    target_blocks   = build_target_blocks()
    banner_blocks   = build_banner_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 48000, "sampleCount": 1123,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:   ["점수",     0],
            V_ROUND:   ["라운드",   1],
            V_KILLS:   ["처치수",   0],
            V_TARGET:  ["라운드목표", 5],
            V_TSPEED:  ["표적속도", 2.5],
            V_SPAWNED: ["스폰수",   0],
            V_STATE:   ["게임상태", 1],
            V_SX:      ["수리검X",  0],
            V_SY:      ["수리검Y", -110],
            V_TKIND:   ["표적종류", 1],
            V_TSX:     ["표적X시작", -220],
            V_TSY:     ["표적Y시작", 110],
            V_TDIR:    ["표적방향", 1],
        },
        "lists": {},
        "broadcasts": {
            BR_START:  "게임시작",
            BR_SPAWN:  "표적스폰",
            BR_FIRE:   "사격",
            BR_NEXT:   "다음라운드",
            BR_MASTER: "마스터",
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

    ninja = {
        "isStage": False, "name": "닌자",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ninja_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "idle",  "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": n_idle_md5, "md5ext": f"{n_idle_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 40},
            {"name": "throw", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": n_thr_md5, "md5ext": f"{n_thr_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 40},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 0, "y": -130, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "left-right"
    }

    shuriken = {
        "isStage": False, "name": "수리검",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": shuriken_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "star", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": sh_md5, "md5ext": f"{sh_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": -110, "size": 50, "direction": 0,
        "draggable": False, "rotationStyle": "all around"
    }

    target = {
        "isStage": False, "name": "표적",
        "variables": {
            LV_KIND:  ["내종류", 1],
            LV_SPEED: ["내속도", 2.5],
            LV_DIR:   ["내방향", 1],
            LV_SCORE: ["내점수", 10],
        },
        "lists": {}, "broadcasts": {},
        "blocks": target_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "target", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": tg_md5, "md5ext": f"{tg_md5}.svg",
             "rotationCenterX": 35, "rotationCenterY": 35},
            {"name": "scroll", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": sc_md5, "md5ext": f"{sc_md5}.svg",
             "rotationCenterX": 45, "rotationCenterY": 30},
            {"name": "bell",   "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bl_md5, "md5ext": f"{bl_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 40},
            {"name": "hit",    "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": hit_md5, "md5ext": f"{hit_md5}.svg",
             "rotationCenterX": 50, "rotationCenterY": 50},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 110, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    banner = {
        "isStage": False, "name": "배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": banner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "round",  "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": rd_md5, "md5ext": f"{rd_md5}.svg",
             "rotationCenterX": 160, "rotationCenterY": 50},
            {"name": "master", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ms_md5, "md5ext": f"{ms_md5}.svg",
             "rotationCenterX": 190, "rotationCenterY": 90},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 1000, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 20, "isDiscrete": True},
        {"id": V_KILLS, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "처치수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 30, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, ninja, shuriken, target, banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "shuriken-throw-builder"}
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
    print(f"  stage:    {len(stage_blocks)} blocks")
    print(f"  ninja:    {len(ninja_blocks)} blocks")
    print(f"  shuriken: {len(shuriken_blocks)} blocks")
    print(f"  target:   {len(target_blocks)} blocks")
    print(f"  banner:   {len(banner_blocks)} blocks")
    total = sum(len(b) for b in
        [stage_blocks, ninja_blocks, shuriken_blocks, target_blocks, banner_blocks])
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
