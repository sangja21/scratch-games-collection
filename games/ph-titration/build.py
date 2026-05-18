#!/usr/bin/env python3
"""pH 적정 실험실 — 산/염기 한 방울로 목표 pH 도달.

핵심 공식: pH = -log₁₀([H⁺])
한 방울 = ×2 (산) 또는 ×0.5 (염기) → pH 약 ±0.30 변화
즉 10배 변해야 pH 1 변함이라는 로그 직관을 손으로 체감.

build.py 베이스: games/decibel-dj/build.py (슬라이더+log+라운드+힌트 패턴)
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "pH_적정_실험실.sb3")

# ============================================================
# SVG assets
# ============================================================
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="lab" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0F1A2E"/>
      <stop offset="60%" stop-color="#1A2A45"/>
      <stop offset="100%" stop-color="#0A0F1A"/>
    </linearGradient>
    <linearGradient id="phbar" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0%"   stop-color="#E64545"/>
      <stop offset="25%"  stop-color="#FFC247"/>
      <stop offset="50%"  stop-color="#7BD96B"/>
      <stop offset="75%"  stop-color="#4DAEFF"/>
      <stop offset="100%" stop-color="#7C5CFF"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#lab)"/>

  <!-- Title strip -->
  <rect x="0" y="0" width="480" height="32" fill="#050810" opacity="0.85"/>
  <text x="240" y="22" fill="#7BD96B" font-family="monospace" font-size="16"
    font-weight="bold" text-anchor="middle">🧪  pH  적정  실험실</text>

  <!-- Left pH bar (logarithmic axis 0..14, displayed as linear ladder) -->
  <g>
    <rect x="45" y="40" width="24" height="280" rx="6" ry="6"
      fill="url(#phbar)" stroke="#FFFFFF" stroke-width="2" opacity="0.92"/>
    <!-- ticks every 1 pH unit: y = 40 + (14 - ph) * 20 -->
    <g font-family="monospace" font-size="9" fill="#FFFFFF" text-anchor="end">
      <text x="42" y="44">14</text>
      <text x="42" y="64">13</text>
      <text x="42" y="84">12</text>
      <text x="42" y="104">11</text>
      <text x="42" y="124">10</text>
      <text x="42" y="144">9</text>
      <text x="42" y="164">8</text>
      <text x="42" y="184">7</text>
      <text x="42" y="204">6</text>
      <text x="42" y="224">5</text>
      <text x="42" y="244">4</text>
      <text x="42" y="264">3</text>
      <text x="42" y="284">2</text>
      <text x="42" y="304">1</text>
      <text x="42" y="324">0</text>
    </g>
    <text x="57" y="334" fill="#7BD96B" font-family="monospace" font-size="9"
      text-anchor="middle">pH</text>
    <!-- mark pH 7 line emphasized -->
    <line x1="44" y1="184" x2="70" y2="184" stroke="#FFFFFF" stroke-width="1" opacity="0.7"/>
  </g>

  <!-- HUD area -->
  <g>
    <rect x="90" y="40" width="370" height="56" rx="10" ry="10"
      fill="#1F2D4D" stroke="#7BD96B" stroke-width="2" opacity="0.85"/>
    <text x="100" y="58" fill="#FFFFFF" font-family="monospace" font-size="10"
      opacity="0.7">현재 pH</text>
    <text x="200" y="58" fill="#FFFFFF" font-family="monospace" font-size="10"
      opacity="0.7">목표 pH</text>
    <text x="295" y="58" fill="#FFFFFF" font-family="monospace" font-size="10"
      opacity="0.7">방울</text>
    <text x="385" y="58" fill="#FFFFFF" font-family="monospace" font-size="10"
      opacity="0.7">점수 / 라운드</text>
  </g>

  <!-- Beaker stand -->
  <g>
    <rect x="180" y="120" width="160" height="160" rx="4" ry="4"
      fill="none" stroke="#7BD96B" stroke-width="2" stroke-dasharray="4 3" opacity="0.5"/>
    <text x="260" y="115" fill="#7BD96B" font-family="monospace" font-size="10"
      text-anchor="middle" opacity="0.8">— 비커 —</text>
  </g>

  <!-- Bottom action bar -->
  <rect x="0" y="320" width="480" height="40" fill="#050810" opacity="0.9"/>
  <text x="240" y="338" fill="#FFC247" font-family="monospace" font-size="11"
    text-anchor="middle">[↓ 산 한 방울 = H⁺ × 2 → pH ↓ 0.30]  [↑ 염기 한 방울 = H⁺ × 0.5 → pH ↑ 0.30]</text>
  <text x="240" y="352" fill="#A29BFE" font-family="monospace" font-size="9"
    text-anchor="middle" opacity="0.85">목표 pH ±0.3 도달 시 정답.  pH = -log₁₀[H⁺]  —  10배 변해야 pH 1 변함</text>
</svg>"""

# Beaker — 4 costumes by pH band
BEAKER_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="140" viewBox="0 0 120 140">
  <!-- Beaker outline -->
  <path d="M 22 16 L 22 110 Q 22 130 42 130 L 78 130 Q 98 130 98 110 L 98 16 Z"
    fill="none" stroke="#FFFFFF" stroke-width="3"/>
  <!-- Liquid (gradient) -->
  <path d="M 26 60 L 26 108 Q 26 126 42 126 L 78 126 Q 94 126 94 108 L 94 60 Z"
    fill="{LIQUID}" opacity="0.88"/>
  <!-- Bubble highlights -->
  <circle cx="40" cy="80" r="3" fill="#FFFFFF" opacity="0.55"/>
  <circle cx="70" cy="95" r="4" fill="#FFFFFF" opacity="0.45"/>
  <circle cx="55" cy="105" r="2" fill="#FFFFFF" opacity="0.6"/>
  <!-- Rim -->
  <ellipse cx="60" cy="16" rx="38" ry="6" fill="none"
    stroke="#FFFFFF" stroke-width="3"/>
  <!-- Label -->
  <text x="60" y="50" fill="#FFFFFF" font-family="monospace" font-size="9"
    text-anchor="middle" opacity="0.75">{LABEL}</text>
</svg>"""

BEAKER_ACID_STRONG = BEAKER_TEMPLATE.format(LIQUID="#E64545", LABEL="강산")
BEAKER_ACID_WEAK   = BEAKER_TEMPLATE.format(LIQUID="#FFC247", LABEL="약산")
BEAKER_NEUTRAL     = BEAKER_TEMPLATE.format(LIQUID="#7BD96B", LABEL="중성")
BEAKER_BASE        = BEAKER_TEMPLATE.format(LIQUID="#4DAEFF", LABEL="염기")

# Current-pH marker (green circle) — points right
PH_MARKER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20" viewBox="0 0 40 20">
  <polygon points="0,10 12,3 12,17" fill="#7BD96B" stroke="#FFFFFF" stroke-width="2"/>
  <text x="26" y="14" fill="#7BD96B" font-family="monospace" font-size="9"
    font-weight="bold">현</text>
</svg>"""

# Target-pH marker (red cross) — points right
TARGET_MARKER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20" viewBox="0 0 40 20">
  <polygon points="0,10 12,3 12,17" fill="#E64545" stroke="#FFFFFF" stroke-width="2"/>
  <text x="26" y="14" fill="#E64545" font-family="monospace" font-size="9"
    font-weight="bold">목</text>
</svg>"""

# Acid button (red ↓) — sprite
ACID_BTN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 72 72">
  <circle cx="36" cy="36" r="32" fill="#E64545" stroke="#FFFFFF" stroke-width="3"/>
  <text x="36" y="32" fill="#FFFFFF" font-family="sans-serif" font-size="22"
    font-weight="bold" text-anchor="middle">↓</text>
  <text x="36" y="52" fill="#FFFFFF" font-family="monospace" font-size="11"
    font-weight="bold" text-anchor="middle">산</text>
</svg>"""

# Base button (blue ↑) — sprite
BASE_BTN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 72 72">
  <circle cx="36" cy="36" r="32" fill="#4DAEFF" stroke="#FFFFFF" stroke-width="3"/>
  <text x="36" y="34" fill="#FFFFFF" font-family="sans-serif" font-size="22"
    font-weight="bold" text-anchor="middle">↑</text>
  <text x="36" y="52" fill="#FFFFFF" font-family="monospace" font-size="10"
    font-weight="bold" text-anchor="middle">염기</text>
</svg>"""

# Hint button — clickable pill
HINT_BTN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="32" viewBox="0 0 100 32">
  <rect x="1" y="1" width="98" height="30" rx="15" ry="15"
    fill="#7C5CFF" stroke="#FFFFFF" stroke-width="2"/>
  <text x="50" y="21" fill="#FFFFFF" font-family="sans-serif" font-size="12"
    font-weight="bold" text-anchor="middle">힌트 ▼</text>
</svg>"""


# ============================================================
# helpers (copied from decibel-dj)
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
# Variable & broadcast IDs
# ============================================================
V_HCONC      = "varHconc_001"
V_PH         = "varPh_002"
V_PH_TARGET  = "varPhTgt_003"
V_DROPS      = "varDrops_004"
V_SCORE      = "varScore_005"
V_ROUND      = "varRound_006"
V_GAMEOVER   = "varGameover_007"
V_FEEDBACK   = "varFeedback_008"
V_HINT       = "varHint_009"
V_DIFF       = "varDiff_010"

BR_START      = "brStart_001"
BR_NEW_ROUND  = "brNewRound_002"
BR_ACID       = "brAcid_003"
BR_BASE       = "brBase_004"
BR_RECALC     = "brRecalc_005"
BR_TRY        = "brTry_006"
BR_HINT       = "brHint_007"
BR_GAMEOVER   = "brGameover_008"


# ============================================================
# BlockBuilder
# ============================================================
class BlockBuilder:
    def __init__(self):
        self.bs = {}

    def vrep(self, name, vid):
        bid = gen()
        self.bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid

    def op(self, opcode, a, b_):
        bid = gen()
        ins = {}
        for key, val in [("NUM1", a), ("NUM2", b_)]:
            if isinstance(val, str):
                ins[key] = slot(val)
            else:
                ins[key] = num(val)
        self.bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): self.bs[v]["parent"] = bid
        return bid

    def mathop(self, name, inner):
        """Unary mathop — log/abs/floor/etc."""
        bid = gen()
        ins = {"NUM": slot(inner) if isinstance(inner, str) else num(inner)}
        self.bs[bid] = mk("operator_mathop",
            inputs=ins, fields={"OPERATOR": [name, None]})
        if isinstance(inner, str):
            self.bs[inner]["parent"] = bid
        return bid

    def cmp(self, opcode, a, b_):
        bid = gen()
        ins = {}
        for key, val in [("OPERAND1", a), ("OPERAND2", b_)]:
            if isinstance(val, str): ins[key] = slot(val)
            else: ins[key] = num(val)
        self.bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): self.bs[v]["parent"] = bid
        return bid

    def round_to_1dp(self, src_block_id):
        """Round value to 1 decimal place: floor(x · 10 + 0.5) / 10."""
        times10 = self.op("operator_multiply", src_block_id, 10)
        plus_half = self.op("operator_add", times10, 0.5)
        fl = gen()
        self.bs[fl] = mk("operator_mathop",
            inputs={"NUM": slot(plus_half)}, fields={"OPERATOR": ["floor", None]})
        self.bs[plus_half]["parent"] = fl
        return self.op("operator_divide", fl, 10)


def _set_var(bs, name, vid, val):
    bid = gen()
    if isinstance(val, str):
        bs[bid] = mk("data_setvariableto",
            inputs={"VALUE": text_lit(val)},
            fields={"VARIABLE": [name, vid]})
    else:
        bs[bid] = mk("data_setvariableto",
            inputs={"VALUE": num(val)},
            fields={"VARIABLE": [name, vid]})
    return bid

def _broadcast(bs, name, brid):
    """Returns [menu_id, broadcast_block_id] pair, chained."""
    m = gen(); bs[m] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, m]})
    bs[m]["parent"] = b
    return b


# ============================================================
# STAGE blocks — all game logic centered here
# ============================================================
def build_stage_blocks():
    B = BlockBuilder()
    bs = B.bs

    # =============== when flag clicked: init + first round ===============
    h_flag = gen(); bs[h_flag] = mk("event_whenflagclicked", top=True, x=20, y=20)

    inits = [
        _set_var(bs, "라운드", V_ROUND, 0),
        _set_var(bs, "점수", V_SCORE, 0),
        _set_var(bs, "게임오버", V_GAMEOVER, 0),
        _set_var(bs, "피드백", V_FEEDBACK, "준비"),
        _set_var(bs, "힌트", V_HINT, ""),
        _set_var(bs, "방울", V_DROPS, 0),
        _set_var(bs, "차이", V_DIFF, 0),
        _set_var(bs, "현재pH", V_PH, 7),
        _set_var(bs, "목표pH", V_PH_TARGET, 7),
        _set_var(bs, "H농도", V_HCONC, 0.0000001),
    ]
    nr0 = _broadcast(bs, "새라운드", BR_NEW_ROUND)
    chain([(h_flag, bs[h_flag])] + [(bid, bs[bid]) for bid in inits] + [(nr0, bs[nr0])])

    # =============== when receive BR_NEW_ROUND ===============
    nr_h = gen(); bs[nr_h] = mk("event_whenbroadcastreceived", top=True, x=400, y=20,
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]})

    # V_ROUND += 1
    inc_r = gen(); bs[inc_r] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})

    # if V_ROUND > 5 → broadcast GAMEOVER
    rR_go = B.vrep("라운드", V_ROUND)
    cond_go = B.cmp("operator_gt", rR_go, 5)
    go_b = _broadcast(bs, "게임오버", BR_GAMEOVER)
    if_go = gen(); bs[if_go] = mk("control_if",
        inputs={"CONDITION":[2, cond_go], "SUBSTACK":[2, go_b]})
    bs[cond_go]["parent"] = if_go
    bs[go_b]["parent"] = if_go

    # Reset round state
    s_drops = _set_var(bs, "방울", V_DROPS, 0)
    s_hint  = _set_var(bs, "힌트", V_HINT, "")
    s_fb    = _set_var(bs, "피드백", V_FEEDBACK, "목표 pH 에 도달하라")

    # Round table — sequential if branches
    ROUNDS = [
        (1, 0.001,       6),   # pH 3 → 6
        (2, 0.000000001, 7),   # pH 9 → 7
        (3, 0.1,         5),   # pH 1 → 5
        (4, 0.00000000001, 8), # pH 11 → 8
        (5, 0.00001,     7),   # pH 5 → 7
    ]
    branch_ids = []
    for R, hconc_v, ph_t in ROUNDS:
        rR = B.vrep("라운드", V_ROUND)
        eqR = B.cmp("operator_equals", rR, R)
        # set H_CONC, V_PH_TARGET inside
        s_h = _set_var(bs, "H농도", V_HCONC, hconc_v)
        s_t = _set_var(bs, "목표pH", V_PH_TARGET, ph_t)
        chain([(s_h, bs[s_h]), (s_t, bs[s_t])])
        if_R = gen(); bs[if_R] = mk("control_if",
            inputs={"CONDITION":[2, eqR], "SUBSTACK":[2, s_h]})
        bs[eqR]["parent"] = if_R
        bs[s_h]["parent"] = if_R
        branch_ids.append(if_R)

    # broadcast BR_RECALC at end
    recalc_b = _broadcast(bs, "재계산", BR_RECALC)

    # chain: nr_h → inc_r → if_go → s_drops → s_hint → s_fb → branch1 → ... → branch5 → recalc_b
    chain([(nr_h, bs[nr_h]), (inc_r, bs[inc_r]), (if_go, bs[if_go]),
           (s_drops, bs[s_drops]), (s_hint, bs[s_hint]), (s_fb, bs[s_fb])]
          + [(bid, bs[bid]) for bid in branch_ids]
          + [(recalc_b, bs[recalc_b])])

    # =============== when receive BR_ACID ===============
    ac_h = gen(); bs[ac_h] = mk("event_whenbroadcastreceived", top=True, x=20, y=300,
        fields={"BROADCAST_OPTION": ["산방울", BR_ACID]})

    # if V_GAMEOVER = 0:
    rGo_a = B.vrep("게임오버", V_GAMEOVER)
    cond_alive_a = B.cmp("operator_equals", rGo_a, 0)

    # V_HCONC = V_HCONC * 2
    rH_a = B.vrep("H농도", V_HCONC)
    mul_a = B.op("operator_multiply", rH_a, 2)
    set_h_a = gen(); bs[set_h_a] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_a)},
        fields={"VARIABLE": ["H농도", V_HCONC]})
    bs[mul_a]["parent"] = set_h_a

    # clamp: if V_HCONC > 1 → V_HCONC = 1
    rH_clA = B.vrep("H농도", V_HCONC)
    cond_clA = B.cmp("operator_gt", rH_clA, 1)
    set_h_clA = _set_var(bs, "H농도", V_HCONC, 1)
    if_clA = gen(); bs[if_clA] = mk("control_if",
        inputs={"CONDITION":[2, cond_clA], "SUBSTACK":[2, set_h_clA]})
    bs[cond_clA]["parent"] = if_clA
    bs[set_h_clA]["parent"] = if_clA

    # V_DROPS += 1
    inc_d_a = gen(); bs[inc_d_a] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["방울", V_DROPS]})

    rec_a = _broadcast(bs, "재계산", BR_RECALC)
    try_a = _broadcast(bs, "판정", BR_TRY)

    chain([(set_h_a, bs[set_h_a]), (if_clA, bs[if_clA]),
           (inc_d_a, bs[inc_d_a]), (rec_a, bs[rec_a]), (try_a, bs[try_a])])

    if_alive_a = gen(); bs[if_alive_a] = mk("control_if",
        inputs={"CONDITION":[2, cond_alive_a], "SUBSTACK":[2, set_h_a]})
    bs[cond_alive_a]["parent"] = if_alive_a
    bs[set_h_a]["parent"] = if_alive_a

    chain([(ac_h, bs[ac_h]), (if_alive_a, bs[if_alive_a])])

    # =============== when receive BR_BASE ===============
    bs_h = gen(); bs[bs_h] = mk("event_whenbroadcastreceived", top=True, x=400, y=300,
        fields={"BROADCAST_OPTION": ["염기방울", BR_BASE]})

    rGo_b = B.vrep("게임오버", V_GAMEOVER)
    cond_alive_b = B.cmp("operator_equals", rGo_b, 0)

    rH_b = B.vrep("H농도", V_HCONC)
    mul_b = B.op("operator_multiply", rH_b, 0.5)
    set_h_b = gen(); bs[set_h_b] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_b)},
        fields={"VARIABLE": ["H농도", V_HCONC]})
    bs[mul_b]["parent"] = set_h_b

    # clamp: if V_HCONC < 1e-14 → V_HCONC = 1e-14
    rH_clB = B.vrep("H농도", V_HCONC)
    cond_clB = B.cmp("operator_lt", rH_clB, 1e-14)
    set_h_clB = _set_var(bs, "H농도", V_HCONC, 1e-14)
    if_clB = gen(); bs[if_clB] = mk("control_if",
        inputs={"CONDITION":[2, cond_clB], "SUBSTACK":[2, set_h_clB]})
    bs[cond_clB]["parent"] = if_clB
    bs[set_h_clB]["parent"] = if_clB

    inc_d_b = gen(); bs[inc_d_b] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["방울", V_DROPS]})

    rec_b = _broadcast(bs, "재계산", BR_RECALC)
    try_b = _broadcast(bs, "판정", BR_TRY)

    chain([(set_h_b, bs[set_h_b]), (if_clB, bs[if_clB]),
           (inc_d_b, bs[inc_d_b]), (rec_b, bs[rec_b]), (try_b, bs[try_b])])

    if_alive_b = gen(); bs[if_alive_b] = mk("control_if",
        inputs={"CONDITION":[2, cond_alive_b], "SUBSTACK":[2, set_h_b]})
    bs[cond_alive_b]["parent"] = if_alive_b
    bs[set_h_b]["parent"] = if_alive_b

    chain([(bs_h, bs[bs_h]), (if_alive_b, bs[if_alive_b])])

    # =============== when receive BR_RECALC ===============
    # Core formula: V_PH = -log10(V_HCONC), rounded to 1 decimal
    rc_h = gen(); bs[rc_h] = mk("event_whenbroadcastreceived", top=True, x=20, y=600,
        fields={"BROADCAST_OPTION": ["재계산", BR_RECALC]})

    rH_rc = B.vrep("H농도", V_HCONC)
    log_h = B.mathop("log", rH_rc)         # log10([H+])
    neg_log = B.op("operator_subtract", 0, log_h)   # 0 - log10(...) = -log10(...)
    rounded = B.round_to_1dp(neg_log)
    set_ph = gen(); bs[set_ph] = mk("data_setvariableto",
        inputs={"VALUE": slot(rounded)},
        fields={"VARIABLE": ["현재pH", V_PH]})
    bs[rounded]["parent"] = set_ph

    chain([(rc_h, bs[rc_h]), (set_ph, bs[set_ph])])

    # =============== when receive BR_TRY ===============
    try_h = gen(); bs[try_h] = mk("event_whenbroadcastreceived", top=True, x=400, y=600,
        fields={"BROADCAST_OPTION": ["판정", BR_TRY]})

    # V_DIFF = abs(V_PH - V_PH_TARGET)
    rPh_t = B.vrep("현재pH", V_PH)
    rTgt_t = B.vrep("목표pH", V_PH_TARGET)
    sub_t = B.op("operator_subtract", rPh_t, rTgt_t)
    abs_d = gen(); bs[abs_d] = mk("operator_mathop",
        inputs={"NUM": slot(sub_t)}, fields={"OPERATOR": ["abs", None]})
    bs[sub_t]["parent"] = abs_d
    set_diff = gen(); bs[set_diff] = mk("data_setvariableto",
        inputs={"VALUE": slot(abs_d)},
        fields={"VARIABLE": ["차이", V_DIFF]})
    bs[abs_d]["parent"] = set_diff

    # if V_DIFF < 0.31 → correct branch
    rDiff_c = B.vrep("차이", V_DIFF)
    cond_correct = B.cmp("operator_lt", rDiff_c, 0.31)

    # CORRECT branch:
    #   bonus = 20 - V_DROPS; if bonus < 1 → 1
    #   V_SCORE += bonus; V_FEEDBACK = "정답!"; wait 0.6; BR_NEW_ROUND
    rDr = B.vrep("방울", V_DROPS)
    bonus = B.op("operator_subtract", 20, rDr)
    set_bonus_diff_var = gen(); bs[set_bonus_diff_var] = mk("data_setvariableto",
        inputs={"VALUE": slot(bonus)},
        fields={"VARIABLE": ["차이", V_DIFF]})  # reuse V_DIFF as temp
    bs[bonus]["parent"] = set_bonus_diff_var

    # if V_DIFF < 1 → V_DIFF = 1
    rTmp = B.vrep("차이", V_DIFF)
    cond_clamp1 = B.cmp("operator_lt", rTmp, 1)
    set_one = _set_var(bs, "차이", V_DIFF, 1)
    if_cl1 = gen(); bs[if_cl1] = mk("control_if",
        inputs={"CONDITION":[2, cond_clamp1], "SUBSTACK":[2, set_one]})
    bs[cond_clamp1]["parent"] = if_cl1
    bs[set_one]["parent"] = if_cl1

    # V_SCORE += V_DIFF (bonus stored in V_DIFF temp)
    rDiff_bonus = B.vrep("차이", V_DIFF)
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": slot(rDiff_bonus)},
        fields={"VARIABLE": ["점수", V_SCORE]})
    bs[rDiff_bonus]["parent"] = inc_score

    set_fb_ok = _set_var(bs, "피드백", V_FEEDBACK, "정답! 다음 라운드로...")

    # play pop sound
    pm = gen(); bs[pm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    pp = gen(); bs[pp] = mk("sound_play", inputs={"SOUND_MENU":[1, pm]})
    bs[pm]["parent"] = pp

    w_ok = gen(); bs[w_ok] = mk("control_wait", inputs={"DURATION": num(0.6)})
    nr_b2 = _broadcast(bs, "새라운드", BR_NEW_ROUND)

    chain([(set_bonus_diff_var, bs[set_bonus_diff_var]), (if_cl1, bs[if_cl1]),
           (inc_score, bs[inc_score]), (set_fb_ok, bs[set_fb_ok]),
           (pp, bs[pp]), (w_ok, bs[w_ok]), (nr_b2, bs[nr_b2])])

    # WRONG branch: choose feedback based on V_PH < V_PH_TARGET vs ≥
    rPh_w = B.vrep("현재pH", V_PH)
    rTgt_w = B.vrep("목표pH", V_PH_TARGET)
    cond_low = B.cmp("operator_lt", rPh_w, rTgt_w)

    set_fb_more_base = _set_var(bs, "피드백", V_FEEDBACK, "더 염기로! (↑ 버튼)")
    set_fb_more_acid = _set_var(bs, "피드백", V_FEEDBACK, "더 산성으로! (↓ 버튼)")

    if_else_wr = gen(); bs[if_else_wr] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_low],
                "SUBSTACK":[2, set_fb_more_base],
                "SUBSTACK2":[2, set_fb_more_acid]})
    bs[cond_low]["parent"] = if_else_wr
    bs[set_fb_more_base]["parent"] = if_else_wr
    bs[set_fb_more_acid]["parent"] = if_else_wr

    # outer if_else (correct vs wrong)
    if_else_try = gen(); bs[if_else_try] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_correct],
                "SUBSTACK":[2, set_bonus_diff_var],
                "SUBSTACK2":[2, if_else_wr]})
    bs[cond_correct]["parent"] = if_else_try
    bs[set_bonus_diff_var]["parent"] = if_else_try
    bs[if_else_wr]["parent"] = if_else_try

    chain([(try_h, bs[try_h]), (set_diff, bs[set_diff]), (if_else_try, bs[if_else_try])])

    # =============== when receive BR_HINT ===============
    hh = gen(); bs[hh] = mk("event_whenbroadcastreceived", top=True, x=20, y=900,
        fields={"BROADCAST_OPTION": ["힌트", BR_HINT]})

    # V_HINT = "목표 pH: " join V_PH_TARGET
    rTgt_h = B.vrep("목표pH", V_PH_TARGET)
    j1 = gen(); bs[j1] = mk("operator_join",
        inputs={"STRING1": text_lit("목표 pH: "),
                "STRING2": slot(rTgt_h, sk=10, sv="")})
    bs[rTgt_h]["parent"] = j1
    set_hint = gen(); bs[set_hint] = mk("data_setvariableto",
        inputs={"VALUE": slot(j1, sk=10, sv="")},
        fields={"VARIABLE": ["힌트", V_HINT]})
    bs[j1]["parent"] = set_hint
    chain([(hh, bs[hh]), (set_hint, bs[set_hint])])

    # =============== when receive BR_GAMEOVER ===============
    goh = gen(); bs[goh] = mk("event_whenbroadcastreceived", top=True, x=400, y=900,
        fields={"BROADCAST_OPTION": ["게임오버", BR_GAMEOVER]})
    set_go = gen(); bs[set_go] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임오버", V_GAMEOVER]})

    # Feedback "종료! 점수 X"
    rSc = B.vrep("점수", V_SCORE)
    j_end = gen(); bs[j_end] = mk("operator_join",
        inputs={"STRING1": text_lit("종료! 점수 "),
                "STRING2": slot(rSc, sk=10, sv="")})
    bs[rSc]["parent"] = j_end
    set_fb_end = gen(); bs[set_fb_end] = mk("data_setvariableto",
        inputs={"VALUE": slot(j_end, sk=10, sv="")},
        fields={"VARIABLE": ["피드백", V_FEEDBACK]})
    bs[j_end]["parent"] = set_fb_end

    chain([(goh, bs[goh]), (set_go, bs[set_go]), (set_fb_end, bs[set_fb_end])])

    return bs


# ============================================================
# Beaker sprite — costume switch by V_PH band
# ============================================================
def build_beaker_blocks():
    B = BlockBuilder()
    bs = B.bs

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(60), "Y": num(-10)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(110)})
    sh = gen(); bs[sh] = mk("looks_show")

    # forever: choose costume by V_PH band
    rPh1 = B.vrep("현재pH", V_PH)
    cond_lt3 = B.cmp("operator_lt", rPh1, 3)
    cs_acid_strong_m = gen(); bs[cs_acid_strong_m] = mk("looks_costume",
        fields={"COSTUME": ["acid_strong", None]}, shadow=True)
    cs_acid_strong = gen(); bs[cs_acid_strong] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cs_acid_strong_m]})
    bs[cs_acid_strong_m]["parent"] = cs_acid_strong

    rPh2 = B.vrep("현재pH", V_PH)
    cond_lt6 = B.cmp("operator_lt", rPh2, 6)
    cs_acid_weak_m = gen(); bs[cs_acid_weak_m] = mk("looks_costume",
        fields={"COSTUME": ["acid_weak", None]}, shadow=True)
    cs_acid_weak = gen(); bs[cs_acid_weak] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cs_acid_weak_m]})
    bs[cs_acid_weak_m]["parent"] = cs_acid_weak

    rPh3 = B.vrep("현재pH", V_PH)
    cond_lt8 = B.cmp("operator_lt", rPh3, 8)
    cs_neutral_m = gen(); bs[cs_neutral_m] = mk("looks_costume",
        fields={"COSTUME": ["neutral", None]}, shadow=True)
    cs_neutral = gen(); bs[cs_neutral] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cs_neutral_m]})
    bs[cs_neutral_m]["parent"] = cs_neutral

    cs_base_m = gen(); bs[cs_base_m] = mk("looks_costume",
        fields={"COSTUME": ["base", None]}, shadow=True)
    cs_base = gen(); bs[cs_base] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cs_base_m]})
    bs[cs_base_m]["parent"] = cs_base

    # if pH < 8 → neutral else base
    if_lt8 = gen(); bs[if_lt8] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_lt8],
                "SUBSTACK":[2, cs_neutral],
                "SUBSTACK2":[2, cs_base]})
    bs[cond_lt8]["parent"] = if_lt8
    bs[cs_neutral]["parent"] = if_lt8
    bs[cs_base]["parent"] = if_lt8

    # if pH < 6 → acid_weak else (if_lt8 above)
    if_lt6 = gen(); bs[if_lt6] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_lt6],
                "SUBSTACK":[2, cs_acid_weak],
                "SUBSTACK2":[2, if_lt8]})
    bs[cond_lt6]["parent"] = if_lt6
    bs[cs_acid_weak]["parent"] = if_lt6
    bs[if_lt8]["parent"] = if_lt6

    # if pH < 3 → acid_strong else (if_lt6 above)
    if_lt3 = gen(); bs[if_lt3] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_lt3],
                "SUBSTACK":[2, cs_acid_strong],
                "SUBSTACK2":[2, if_lt6]})
    bs[cond_lt3]["parent"] = if_lt3
    bs[cs_acid_strong]["parent"] = if_lt3
    bs[if_lt6]["parent"] = if_lt3

    w = gen(); bs[w] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_lt3, bs[if_lt3]), (w, bs[w])])
    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, if_lt3]})
    bs[if_lt3]["parent"] = fv

    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh]), (fv, bs[fv])])
    return bs


# ============================================================
# PhMarker sprite — current pH (green triangle) on left bar
# ============================================================
def build_ph_marker_blocks():
    B = BlockBuilder()
    bs = B.bs

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sx = gen(); bs[sx] = mk("motion_setx", inputs={"X": num(-167)})
    sh = gen(); bs[sh] = mk("looks_show")

    # forever: set y to -120 + 20·V_PH  →  pH 0 = -120, pH 14 = +160
    # actually scratch y: pH 0 = 320 svg, pH 14 = 40 svg
    # svg y = 40 + (14-ph)*20 → scratch y = 180 - svg y = 180 - 40 - (14-ph)*20
    #       = 140 - (14-ph)*20 = 140 - 280 + 20·ph = -140 + 20·ph
    rPh = B.vrep("현재pH", V_PH)
    m20 = B.op("operator_multiply", rPh, 20)
    yv = B.op("operator_add", m20, -140)
    sety = gen(); bs[sety] = mk("motion_sety",
        inputs={"Y": slot(yv)})
    bs[yv]["parent"] = sety
    w = gen(); bs[w] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(sety, bs[sety]), (w, bs[w])])
    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, sety]})
    bs[sety]["parent"] = fv

    chain([(h, bs[h]), (sx, bs[sx]), (sh, bs[sh]), (fv, bs[fv])])
    return bs


# ============================================================
# TargetMarker sprite — target pH (red triangle) — slightly offset
# ============================================================
def build_target_marker_blocks():
    B = BlockBuilder()
    bs = B.bs

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sx = gen(); bs[sx] = mk("motion_setx", inputs={"X": num(-200)})
    sh = gen(); bs[sh] = mk("looks_show")

    rT = B.vrep("목표pH", V_PH_TARGET)
    m20 = B.op("operator_multiply", rT, 20)
    yv = B.op("operator_add", m20, -140)
    sety = gen(); bs[sety] = mk("motion_sety", inputs={"Y": slot(yv)})
    bs[yv]["parent"] = sety
    w = gen(); bs[w] = mk("control_wait", inputs={"DURATION": num(0.1)})
    chain([(sety, bs[sety]), (w, bs[w])])
    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, sety]})
    bs[sety]["parent"] = fv

    chain([(h, bs[h]), (sx, bs[sx]), (sh, bs[sh]), (fv, bs[fv])])
    return bs


# ============================================================
# AcidButton sprite — click → broadcast BR_ACID
# ============================================================
def build_acid_button_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(140), "Y": num(-130)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh])])

    ch = gen(); bs[ch] = mk("event_whenthisspriteclicked", top=True, x=20, y=200)
    ab = _broadcast(bs, "산방울", BR_ACID)
    pm = gen(); bs[pm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    pp = gen(); bs[pp] = mk("sound_play", inputs={"SOUND_MENU":[1, pm]})
    bs[pm]["parent"] = pp
    chain([(ch, bs[ch]), (ab, bs[ab]), (pp, bs[pp])])
    return bs


# ============================================================
# BaseButton sprite — click → broadcast BR_BASE
# ============================================================
def build_base_button_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-50), "Y": num(-130)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh])])

    ch = gen(); bs[ch] = mk("event_whenthisspriteclicked", top=True, x=20, y=200)
    bb = _broadcast(bs, "염기방울", BR_BASE)
    pm = gen(); bs[pm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    pp = gen(); bs[pp] = mk("sound_play", inputs={"SOUND_MENU":[1, pm]})
    bs[pm]["parent"] = pp
    chain([(ch, bs[ch]), (bb, bs[bb]), (pp, bs[pp])])
    return bs


# ============================================================
# HintButton sprite — click → broadcast BR_HINT
# ============================================================
def build_hint_button_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(195), "Y": num(45)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh])])

    ch = gen(); bs[ch] = mk("event_whenthisspriteclicked", top=True, x=20, y=200)
    hb = _broadcast(bs, "힌트", BR_HINT)
    pm = gen(); bs[pm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    pp = gen(); bs[pp] = mk("sound_play", inputs={"SOUND_MENU":[1, pm]})
    bs[pm]["parent"] = pp
    chain([(ch, bs[ch]), (hb, bs[hb]), (pp, bs[pp])])
    return bs


# ============================================================
# Assemble project
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # Backgrounds
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    # Beaker 4 costumes
    bk_costumes = []
    for name, svg in [("acid_strong", BEAKER_ACID_STRONG),
                      ("acid_weak",   BEAKER_ACID_WEAK),
                      ("neutral",     BEAKER_NEUTRAL),
                      ("base",        BEAKER_BASE)]:
        md5 = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{md5}.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        bk_costumes.append({
            "name": name, "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": md5, "md5ext": f"{md5}.svg",
            "rotationCenterX": 60, "rotationCenterY": 70
        })

    # Marker SVGs
    pm_md5 = md5_bytes(PH_MARKER_SVG.encode("utf-8"))
    with open(f"{WORK}/{pm_md5}.svg", "w", encoding="utf-8") as f:
        f.write(PH_MARKER_SVG)
    tm_md5 = md5_bytes(TARGET_MARKER_SVG.encode("utf-8"))
    with open(f"{WORK}/{tm_md5}.svg", "w", encoding="utf-8") as f:
        f.write(TARGET_MARKER_SVG)

    # Buttons
    ab_md5 = md5_bytes(ACID_BTN_SVG.encode("utf-8"))
    with open(f"{WORK}/{ab_md5}.svg", "w", encoding="utf-8") as f:
        f.write(ACID_BTN_SVG)
    bb_md5 = md5_bytes(BASE_BTN_SVG.encode("utf-8"))
    with open(f"{WORK}/{bb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BASE_BTN_SVG)
    hb_md5 = md5_bytes(HINT_BTN_SVG.encode("utf-8"))
    with open(f"{WORK}/{hb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(HINT_BTN_SVG)

    # pop.wav
    pop_src = f"{ASSETS}/pop.wav"
    with open(pop_src, "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    # Build blocks
    stage_blocks = build_stage_blocks()
    beaker_blocks = build_beaker_blocks()
    ph_marker_blocks = build_ph_marker_blocks()
    target_marker_blocks = build_target_marker_blocks()
    acid_blocks = build_acid_button_blocks()
    base_blocks = build_base_button_blocks()
    hint_blocks = build_hint_button_blocks()

    pop_sound = {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 48000, "sampleCount": 1123,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_HCONC:    ["H농도", 0.0000001],
            V_PH:       ["현재pH", 7],
            V_PH_TARGET:["목표pH", 7],
            V_DROPS:    ["방울", 0],
            V_SCORE:    ["점수", 0],
            V_ROUND:    ["라운드", 0],
            V_GAMEOVER: ["게임오버", 0],
            V_FEEDBACK: ["피드백", "준비"],
            V_HINT:     ["힌트", ""],
            V_DIFF:     ["차이", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:     "게임시작",
            BR_NEW_ROUND: "새라운드",
            BR_ACID:      "산방울",
            BR_BASE:      "염기방울",
            BR_RECALC:    "재계산",
            BR_TRY:       "판정",
            BR_HINT:      "힌트",
            BR_GAMEOVER:  "게임오버",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "lab", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    beaker = {
        "isStage": False, "name": "비커",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": beaker_blocks, "comments": {},
        "currentCostume": 1,  # default to acid_weak
        "costumes": bk_costumes,
        "sounds": [],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 60, "y": -10, "size": 110, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ph_marker = {
        "isStage": False, "name": "현재마커",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ph_marker_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "marker", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pm_md5, "md5ext": f"{pm_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 10
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": -167, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    target_marker = {
        "isStage": False, "name": "목표마커",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": target_marker_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "target", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": tm_md5, "md5ext": f"{tm_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 10
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": -200, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    acid_btn = {
        "isStage": False, "name": "산버튼",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": acid_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "acid", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ab_md5, "md5ext": f"{ab_md5}.svg",
            "rotationCenterX": 36, "rotationCenterY": 36
        }],
        "sounds": [pop_sound],
        "volume": 100, "layerOrder": 4, "visible": True,
        "x": 140, "y": -130, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    base_btn = {
        "isStage": False, "name": "염기버튼",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": base_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "base", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bb_md5, "md5ext": f"{bb_md5}.svg",
            "rotationCenterX": 36, "rotationCenterY": 36
        }],
        "sounds": [pop_sound],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": -50, "y": -130, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    hint_btn = {
        "isStage": False, "name": "힌트버튼",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hint_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "hint", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hb_md5, "md5ext": f"{hb_md5}.svg",
            "rotationCenterX": 50, "rotationCenterY": 16
        }],
        "sounds": [pop_sound],
        "volume": 100, "layerOrder": 6, "visible": True,
        "x": 195, "y": 45, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # Monitors
    monitors = [
        # HUD: 현재 pH (large)
        {"id": V_PH, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "현재pH"}, "spriteName": None,
         "value": 7, "width": 0, "height": 0, "x": 95, "y": 40,
         "visible": True, "sliderMin": 0, "sliderMax": 14, "isDiscrete": False},
        # 목표 pH (large)
        {"id": V_PH_TARGET, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "목표pH"}, "spriteName": None,
         "value": 7, "width": 0, "height": 0, "x": 195, "y": 40,
         "visible": True, "sliderMin": 0, "sliderMax": 14, "isDiscrete": True},
        # 방울
        {"id": V_DROPS, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "방울"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 290, "y": 40,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        # 점수
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 380, "y": 40,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        # 라운드
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 380, "y": 70,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        # H농도 (실시간 [H+] 표시 — 로그 학습 강조)
        {"id": V_HCONC, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "H농도"}, "spriteName": None,
         "value": 0.0000001, "width": 0, "height": 0, "x": 290, "y": 70,
         "visible": True, "sliderMin": 0, "sliderMax": 1, "isDiscrete": False},
        # 피드백 (큰 텍스트, 하단 비커 위)
        {"id": V_FEEDBACK, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "피드백"}, "spriteName": None,
         "value": "준비", "width": 0, "height": 0, "x": 95, "y": 285,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        # 힌트
        {"id": V_HINT, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "힌트"}, "spriteName": None,
         "value": "", "width": 0, "height": 0, "x": 290, "y": 285,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, beaker, ph_marker, target_marker,
                    acid_btn, base_btn, hint_btn],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "ph-titration-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # Validate
    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)

    n_blocks = sum(len(t["blocks"]) for t in project["targets"])
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"✓ wrote {OUTPUT} ({size_kb:.1f} KB, {n_blocks} blocks)")


if __name__ == "__main__":
    main()
