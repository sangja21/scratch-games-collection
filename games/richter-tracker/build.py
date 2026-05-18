#!/usr/bin/env python3
"""리히터 진앙 추적 — 두 지진의 진폭 차이로 매그니튜드 차 ΔM 을 맞추는 로그 학습 게임.

핵심 공식: M = log₁₀(A / A₀)
두 지진의 매그니튜드 차: ΔM = log₁₀(A_max / A_min)
ΔM = 1 → 진폭 10배, ΔM = 2 → 100배, ΔM = 3 → 1000배

학습 포인트: "매그니튜드 1 차이 = 진폭 10배" 를 슬라이더로 직접 체험.
시각: 진폭 막대를 LOG 스케일(size = 20·log(A)+20) 로 그려서
      10000:1 같은 큰 비율도 한 화면에 표시.

build.py 베이스: games/decibel-dj/build.py
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "리히터_진앙_추적.sb3")

# ============================================================
# SVG assets
# ============================================================
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0F1A2A"/>
      <stop offset="55%" stop-color="#1F2D3F"/>
      <stop offset="100%" stop-color="#3A2418"/>
    </linearGradient>
    <radialGradient id="shock" cx="50%" cy="40%" r="60%">
      <stop offset="0%" stop-color="#FFB347" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#FFB347" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="480" height="360" fill="url(#ground)"/>
  <rect width="480" height="360" fill="url(#shock)"/>

  <!-- Title strip -->
  <rect x="0" y="0" width="480" height="32" fill="#08101A" opacity="0.9"/>
  <text x="240" y="22" fill="#FFB347" font-family="monospace" font-size="15"
    font-weight="bold" text-anchor="middle">🌋  리히터  진앙  추적  —  ΔM  맞추기</text>

  <!-- Two seismograph panels -->
  <g>
    <rect x="40"  y="60" width="170" height="180" rx="12" ry="12"
      fill="#2A1518" stroke="#FF6B6B" stroke-width="3" opacity="0.92"/>
    <text x="125" y="84" fill="#FFB3B3" font-family="monospace" font-size="14"
      font-weight="bold" text-anchor="middle">A 도시</text>
    <text x="125" y="104" fill="#FFFFFF" font-family="monospace" font-size="10"
      text-anchor="middle" opacity="0.7">진폭 A</text>
    <!-- baseline marker -->
    <line x1="60" y1="220" x2="190" y2="220" stroke="#FFB3B3"
      stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
    <text x="125" y="234" fill="#FFB3B3" font-family="monospace" font-size="9"
      text-anchor="middle" opacity="0.6">log 스케일</text>
  </g>
  <g>
    <rect x="270" y="60" width="170" height="180" rx="12" ry="12"
      fill="#15202A" stroke="#5BCFFF" stroke-width="3" opacity="0.92"/>
    <text x="355" y="84" fill="#B0E5FF" font-family="monospace" font-size="14"
      font-weight="bold" text-anchor="middle">B 도시</text>
    <text x="355" y="104" fill="#FFFFFF" font-family="monospace" font-size="10"
      text-anchor="middle" opacity="0.7">진폭 B</text>
    <line x1="290" y1="220" x2="420" y2="220" stroke="#B0E5FF"
      stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
    <text x="355" y="234" fill="#B0E5FF" font-family="monospace" font-size="9"
      text-anchor="middle" opacity="0.6">log 스케일</text>
  </g>

  <!-- Slider region label -->
  <text x="240" y="262" fill="#A29BFE" font-family="monospace" font-size="12"
    font-weight="bold" text-anchor="middle">↓  매그니튜드 차 ΔM 슬라이더  (V_DM_USER) ↓</text>

  <!-- Bottom bar: instructions -->
  <rect x="0" y="318" width="480" height="42" fill="#08101A" opacity="0.9"/>
  <text x="240" y="338" fill="#FFB347" font-family="monospace" font-size="11"
    text-anchor="middle">Space = 시도 (오차 ±0.3 이내면 정답)   ΔM = log₁₀(A_max / A_min)</text>
  <text x="240" y="354" fill="#A29BFE" font-family="monospace" font-size="10"
    text-anchor="middle" opacity="0.85">힌트 버튼 = 정답 노출 (학습용)</text>
</svg>"""

# Seismograph A (red bar that stretches vertically based on log10(amp))
SEISMO_A_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <rect x="6" y="0" width="28" height="40" rx="4" ry="4"
    fill="#FF6B6B" stroke="#FFFFFF" stroke-width="2"/>
  <circle cx="20" cy="20" r="6" fill="#FFFFFF" opacity="0.9"/>
  <text x="20" y="25" fill="#FF6B6B" font-family="monospace" font-size="10"
    font-weight="bold" text-anchor="middle">A</text>
</svg>"""

# Seismograph B (blue bar)
SEISMO_B_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <rect x="6" y="0" width="28" height="40" rx="4" ry="4"
    fill="#5BCFFF" stroke="#FFFFFF" stroke-width="2"/>
  <circle cx="20" cy="20" r="6" fill="#FFFFFF" opacity="0.9"/>
  <text x="20" y="25" fill="#1A4A6B" font-family="monospace" font-size="10"
    font-weight="bold" text-anchor="middle">B</text>
</svg>"""

# Judge sprite — small purple circle for `looks_say` feedback
JUDGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="14" fill="#7C5CFF" stroke="#FFFFFF" stroke-width="2"/>
  <text x="16" y="22" fill="#FFFFFF" font-family="monospace" font-size="14"
    text-anchor="middle" font-weight="bold">!</text>
</svg>"""

# Hint button
HINT_BTN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="36" viewBox="0 0 120 36">
  <rect x="1" y="1" width="118" height="34" rx="17" ry="17"
    fill="#7C5CFF" stroke="#FFFFFF" stroke-width="2"/>
  <text x="60" y="23" fill="#FFFFFF" font-family="sans-serif" font-size="14"
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
V_A_AMP     = "varAamp_001"
V_B_AMP     = "varBamp_002"
V_A0        = "varA0_003"
V_MA        = "varMA_004"
V_MB        = "varMB_005"
V_DM_ANS    = "varDmAns_006"
V_DM_USER   = "varDmUser_007"
V_DIFF      = "varDiff_008"
V_RATIO     = "varRatio_009"
V_SCORE     = "varScore_010"
V_ROUND     = "varRound_011"
V_TIME      = "varTime_012"
V_FEEDBACK  = "varFeedback_013"
V_HINT      = "varHint_014"
V_GAMEOVER  = "varGameover_015"

BR_START      = "brStart_001"
BR_NEW_ROUND  = "brNewRound_002"
BR_TRY        = "brTry_003"
BR_HINT       = "brHint_004"
BR_GAMEOVER   = "brGameover_005"
BR_REDRAW     = "brRedraw_006"


# ============================================================
# BlockBuilder class (math helpers) — same as decibel-dj
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
        """Unary mathop — log/ln/abs/floor/etc."""
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

    def magnitude_from_amp(self, amp_var_name, amp_vid):
        """M = log(A / A0). Returns block id of the log result (not rounded)."""
        rA = self.vrep(amp_var_name, amp_vid)
        rA0 = self.vrep("기준진폭", V_A0)
        ratio = self.op("operator_divide", rA, rA0)
        return self.mathop("log", ratio)


# ============================================================
# STAGE blocks — game logic
# ============================================================
def build_stage_blocks():
    B = BlockBuilder()
    bs = B.bs

    # ---------- when flag clicked: init + send BR_NEW_ROUND ----------
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)

    inits = []
    def set_var(name, vid, val):
        bid = gen()
        if isinstance(val, str):
            bs[bid] = mk("data_setvariableto",
                inputs={"VALUE": text_lit(val)},
                fields={"VARIABLE": [name, vid]})
        else:
            bs[bid] = mk("data_setvariableto",
                inputs={"VALUE": num(val)},
                fields={"VARIABLE": [name, vid]})
        inits.append(bid)
        return bid

    set_var("기준진폭", V_A0, 1)
    set_var("점수", V_SCORE, 0)
    set_var("라운드", V_ROUND, 0)
    set_var("남은시간", V_TIME, 60)
    set_var("게임오버", V_GAMEOVER, 0)
    set_var("피드백", V_FEEDBACK, "준비")
    set_var("힌트", V_HINT, "")
    set_var("내답ΔM", V_DM_USER, 2.5)
    set_var("진폭A", V_A_AMP, 100)
    set_var("진폭B", V_B_AMP, 10)
    set_var("매그A", V_MA, 0)
    set_var("매그B", V_MB, 0)
    set_var("정답ΔM", V_DM_ANS, 0)
    set_var("차이", V_DIFF, 0)
    set_var("진폭비", V_RATIO, 10)

    # broadcast BR_NEW_ROUND
    nrm = gen(); bs[nrm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]}, shadow=True)
    nrb = gen(); bs[nrb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, nrm]})
    bs[nrm]["parent"] = nrb

    chain([(h, bs[h])] + [(bid, bs[bid]) for bid in inits] + [(nrb, bs[nrb])])

    # ---------- timer loop: forever wait 1 ; decrement time ----------
    th = gen(); bs[th] = mk("event_whenflagclicked", top=True, x=20, y=300)

    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(1)})
    # if V_GAMEOVER = 0
    rgo = B.vrep("게임오버", V_GAMEOVER)
    cond_go = gen(); bs[cond_go] = mk("operator_equals",
        inputs={"OPERAND1": slot(rgo), "OPERAND2": num(0)})
    bs[rgo]["parent"] = cond_go
    # change V_TIME by -1
    dec_t = gen(); bs[dec_t] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["남은시간", V_TIME]})
    # if V_TIME < 1 -> broadcast GAMEOVER
    rt_var = B.vrep("남은시간", V_TIME)
    cond_tle = gen(); bs[cond_tle] = mk("operator_lt",
        inputs={"OPERAND1": slot(rt_var), "OPERAND2": num(1)})
    bs[rt_var]["parent"] = cond_tle
    gom = gen(); bs[gom] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임오버", BR_GAMEOVER]}, shadow=True)
    gob = gen(); bs[gob] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, gom]})
    bs[gom]["parent"] = gob

    if_tle = gen(); bs[if_tle] = mk("control_if",
        inputs={"CONDITION":[2, cond_tle], "SUBSTACK":[2, gob]})
    bs[cond_tle]["parent"] = if_tle
    bs[gob]["parent"] = if_tle

    chain([(dec_t, bs[dec_t]), (if_tle, bs[if_tle])])

    if_go = gen(); bs[if_go] = mk("control_if",
        inputs={"CONDITION":[2, cond_go], "SUBSTACK":[2, dec_t]})
    bs[cond_go]["parent"] = if_go
    bs[dec_t]["parent"] = if_go

    chain([(w1, bs[w1]), (if_go, bs[if_go])])
    fv_t = gen(); bs[fv_t] = mk("control_forever", inputs={"SUBSTACK":[2, w1]})
    bs[w1]["parent"] = fv_t

    chain([(th, bs[th]), (fv_t, bs[fv_t])])

    # ---------- when receive BR_NEW_ROUND ----------
    nh = gen(); bs[nh] = mk("event_whenbroadcastreceived", top=True, x=400, y=20,
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]})

    # change V_ROUND by 1
    inc_r = gen(); bs[inc_r] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})

    # set V_HINT = ""
    set_hint_empty = gen(); bs[set_hint_empty] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("")}, fields={"VARIABLE": ["힌트", V_HINT]})

    # set V_FEEDBACK
    set_fb = gen(); bs[set_fb] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("ΔM 을 맞춰라")},
        fields={"VARIABLE": ["피드백", V_FEEDBACK]})

    # Round 1..5 fixed scenarios
    # (라운드, A_amp, B_amp) — 정답 ΔM = log10(A_amp/B_amp) 가 정수
    FIXED = [
        (1, 100,    10),      # ΔM=1, ratio=10
        (2, 10000,  100),     # ΔM=2, ratio=100
        (3, 100000, 100),     # ΔM=3, ratio=1000
        (4, 10000,  10),      # ΔM=3, ratio=1000 (다른 절대값)
        (5, 100000, 10),      # ΔM=4, ratio=10000
    ]
    round_branches = []
    for R, a_v, b_v in FIXED:
        rR = B.vrep("라운드", V_ROUND)
        eqR = gen(); bs[eqR] = mk("operator_equals",
            inputs={"OPERAND1": slot(rR), "OPERAND2": num(R)})
        bs[rR]["parent"] = eqR

        sa = gen(); bs[sa] = mk("data_setvariableto",
            inputs={"VALUE": num(a_v)}, fields={"VARIABLE": ["진폭A", V_A_AMP]})
        sb = gen(); bs[sb] = mk("data_setvariableto",
            inputs={"VALUE": num(b_v)}, fields={"VARIABLE": ["진폭B", V_B_AMP]})
        chain([(sa, bs[sa]), (sb, bs[sb])])

        if_R = gen(); bs[if_R] = mk("control_if",
            inputs={"CONDITION":[2, eqR], "SUBSTACK":[2, sa]})
        bs[eqR]["parent"] = if_R
        bs[sa]["parent"] = if_R
        round_branches.append(if_R)

    # else (R >= 6): A = base * 10^delta, B = base
    # base = 10^(random 1..3), delta = random 1..4 (정수)
    rR_else = B.vrep("라운드", V_ROUND)
    cond_else = gen(); bs[cond_else] = mk("operator_gt",
        inputs={"OPERAND1": slot(rR_else), "OPERAND2": num(5)})
    bs[rR_else]["parent"] = cond_else

    # base = 10^(random 1..3)
    rnd_base = gen(); bs[rnd_base] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(3)})
    pow_base = gen(); bs[pow_base] = mk("operator_mathop",
        inputs={"NUM": slot(rnd_base)}, fields={"OPERATOR": ["10 ^", None]})
    bs[rnd_base]["parent"] = pow_base

    set_b_rnd = gen(); bs[set_b_rnd] = mk("data_setvariableto",
        inputs={"VALUE": slot(pow_base)}, fields={"VARIABLE": ["진폭B", V_B_AMP]})
    bs[pow_base]["parent"] = set_b_rnd

    # delta = random 1..4
    rnd_delta = gen(); bs[rnd_delta] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(4)})
    pow_delta = gen(); bs[pow_delta] = mk("operator_mathop",
        inputs={"NUM": slot(rnd_delta)}, fields={"OPERATOR": ["10 ^", None]})
    bs[rnd_delta]["parent"] = pow_delta
    # A = B * 10^delta
    rB_rnd = B.vrep("진폭B", V_B_AMP)
    mul_a = B.op("operator_multiply", rB_rnd, pow_delta)
    set_a_rnd = gen(); bs[set_a_rnd] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_a)}, fields={"VARIABLE": ["진폭A", V_A_AMP]})
    bs[mul_a]["parent"] = set_a_rnd

    chain([(set_b_rnd, bs[set_b_rnd]), (set_a_rnd, bs[set_a_rnd])])

    if_else = gen(); bs[if_else] = mk("control_if",
        inputs={"CONDITION":[2, cond_else], "SUBSTACK":[2, set_b_rnd]})
    bs[cond_else]["parent"] = if_else
    bs[set_b_rnd]["parent"] = if_else

    round_branches.append(if_else)

    # chain all round branches in sequence
    chain([(bid, bs[bid]) for bid in round_branches])

    # ---- compute V_MA, V_MB, V_DM_ANS ----
    # V_MA = round1dp(log(A_amp / A0))
    ma_raw = B.magnitude_from_amp("진폭A", V_A_AMP)
    ma_rounded = B.round_to_1dp(ma_raw)
    set_ma = gen(); bs[set_ma] = mk("data_setvariableto",
        inputs={"VALUE": slot(ma_rounded)},
        fields={"VARIABLE": ["매그A", V_MA]})
    bs[ma_rounded]["parent"] = set_ma

    mb_raw = B.magnitude_from_amp("진폭B", V_B_AMP)
    mb_rounded = B.round_to_1dp(mb_raw)
    set_mb = gen(); bs[set_mb] = mk("data_setvariableto",
        inputs={"VALUE": slot(mb_rounded)},
        fields={"VARIABLE": ["매그B", V_MB]})
    bs[mb_rounded]["parent"] = set_mb

    # V_DM_ANS = abs(MA - MB)  — but compute from raw amps for precision
    rA_ans = B.vrep("진폭A", V_A_AMP)
    rB_ans = B.vrep("진폭B", V_B_AMP)
    ratio_amps = B.op("operator_divide", rA_ans, rB_ans)
    log_ratio = B.mathop("log", ratio_amps)
    abs_dm = gen(); bs[abs_dm] = mk("operator_mathop",
        inputs={"NUM": slot(log_ratio)}, fields={"OPERATOR": ["abs", None]})
    bs[log_ratio]["parent"] = abs_dm
    set_ans = gen(); bs[set_ans] = mk("data_setvariableto",
        inputs={"VALUE": slot(abs_dm)},
        fields={"VARIABLE": ["정답ΔM", V_DM_ANS]})
    bs[abs_dm]["parent"] = set_ans

    # V_RATIO = max(A,B) / min(A,B). 간단하게: if A>B then A/B else B/A
    rA_r = B.vrep("진폭A", V_A_AMP)
    rB_r = B.vrep("진폭B", V_B_AMP)
    cond_a_bigger = gen(); bs[cond_a_bigger] = mk("operator_gt",
        inputs={"OPERAND1": slot(rA_r), "OPERAND2": slot(rB_r)})
    bs[rA_r]["parent"] = cond_a_bigger
    bs[rB_r]["parent"] = cond_a_bigger

    # then branch: V_RATIO = A/B
    rA_d = B.vrep("진폭A", V_A_AMP)
    rB_d = B.vrep("진폭B", V_B_AMP)
    div_ab = B.op("operator_divide", rA_d, rB_d)
    set_r_ab = gen(); bs[set_r_ab] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_ab)},
        fields={"VARIABLE": ["진폭비", V_RATIO]})
    bs[div_ab]["parent"] = set_r_ab

    # else branch: V_RATIO = B/A
    rB_d2 = B.vrep("진폭B", V_B_AMP)
    rA_d2 = B.vrep("진폭A", V_A_AMP)
    div_ba = B.op("operator_divide", rB_d2, rA_d2)
    set_r_ba = gen(); bs[set_r_ba] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_ba)},
        fields={"VARIABLE": ["진폭비", V_RATIO]})
    bs[div_ba]["parent"] = set_r_ba

    if_ratio = gen(); bs[if_ratio] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_a_bigger],
                "SUBSTACK":[2, set_r_ab],
                "SUBSTACK2":[2, set_r_ba]})
    bs[cond_a_bigger]["parent"] = if_ratio
    bs[set_r_ab]["parent"] = if_ratio
    bs[set_r_ba]["parent"] = if_ratio

    # broadcast BR_REDRAW so sprites resize
    rdm = gen(); bs[rdm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["진폭갱신", BR_REDRAW]}, shadow=True)
    rdb = gen(); bs[rdb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, rdm]})
    bs[rdm]["parent"] = rdb

    # chain new-round flow
    chain([(nh, bs[nh]), (inc_r, bs[inc_r]), (set_hint_empty, bs[set_hint_empty]),
           (set_fb, bs[set_fb])] +
          [(round_branches[0], bs[round_branches[0]])])
    chain([(round_branches[-1], bs[round_branches[-1]]),
           (set_ma, bs[set_ma]), (set_mb, bs[set_mb]),
           (set_ans, bs[set_ans]),
           (if_ratio, bs[if_ratio]),
           (rdb, bs[rdb])])

    # ---------- when space pressed: try ----------
    sph = gen(); bs[sph] = mk("event_whenkeypressed", top=True, x=20, y=600,
        fields={"KEY_OPTION": ["space", None]})

    # broadcast BR_TRY
    trm = gen(); bs[trm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["시도", BR_TRY]}, shadow=True)
    trb = gen(); bs[trb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, trm]})
    bs[trm]["parent"] = trb
    chain([(sph, bs[sph]), (trb, bs[trb])])

    # ---------- when receive BR_TRY ----------
    tryh = gen(); bs[tryh] = mk("event_whenbroadcastreceived", top=True, x=400, y=600,
        fields={"BROADCAST_OPTION": ["시도", BR_TRY]})

    # only if V_GAMEOVER = 0
    rgo2 = B.vrep("게임오버", V_GAMEOVER)
    cond_alive = gen(); bs[cond_alive] = mk("operator_equals",
        inputs={"OPERAND1": slot(rgo2), "OPERAND2": num(0)})
    bs[rgo2]["parent"] = cond_alive

    # V_DIFF = abs(V_DM_USER - V_DM_ANS)
    rUser = B.vrep("내답ΔM", V_DM_USER)
    rAns = B.vrep("정답ΔM", V_DM_ANS)
    sub_ua = B.op("operator_subtract", rUser, rAns)
    abs_diff = gen(); bs[abs_diff] = mk("operator_mathop",
        inputs={"NUM": slot(sub_ua)}, fields={"OPERATOR": ["abs", None]})
    bs[sub_ua]["parent"] = abs_diff
    set_diff = gen(); bs[set_diff] = mk("data_setvariableto",
        inputs={"VALUE": slot(abs_diff)},
        fields={"VARIABLE": ["차이", V_DIFF]})
    bs[abs_diff]["parent"] = set_diff

    # if V_DIFF < 0.3 → correct ; else → wrong
    rDiff = B.vrep("차이", V_DIFF)
    cond_correct = gen(); bs[cond_correct] = mk("operator_lt",
        inputs={"OPERAND1": slot(rDiff), "OPERAND2": num(0.3)})
    bs[rDiff]["parent"] = cond_correct

    # === CORRECT branch ===
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    set_fb_ok = gen(); bs[set_fb_ok] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("정답!  +1")},
        fields={"VARIABLE": ["피드백", V_FEEDBACK]})
    pm = gen(); bs[pm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    pp = gen(); bs[pp] = mk("sound_play", inputs={"SOUND_MENU":[1, pm]})
    bs[pm]["parent"] = pp
    w_ok = gen(); bs[w_ok] = mk("control_wait", inputs={"DURATION": num(0.5)})
    nrm2 = gen(); bs[nrm2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]}, shadow=True)
    nrb2 = gen(); bs[nrb2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, nrm2]})
    bs[nrm2]["parent"] = nrb2
    chain([(inc_score, bs[inc_score]), (set_fb_ok, bs[set_fb_ok]),
           (pp, bs[pp]), (w_ok, bs[w_ok]), (nrb2, bs[nrb2])])

    # === WRONG branch ===
    # Build feedback string: join("차이 ", join(round(diff·10)/10, " ΔM"))
    rDiff2 = B.vrep("차이", V_DIFF)
    d10 = B.op("operator_multiply", rDiff2, 10)
    d10_add_half = B.op("operator_add", d10, 0.5)
    fl_w = gen(); bs[fl_w] = mk("operator_mathop",
        inputs={"NUM": slot(d10_add_half)}, fields={"OPERATOR": ["floor", None]})
    bs[d10_add_half]["parent"] = fl_w
    d10_div = B.op("operator_divide", fl_w, 10)

    j_inner = gen(); bs[j_inner] = mk("operator_join",
        inputs={"STRING1": slot(d10_div, sk=10, sv=""),
                "STRING2": text_lit(" ΔM")})
    bs[d10_div]["parent"] = j_inner
    j_outer = gen(); bs[j_outer] = mk("operator_join",
        inputs={"STRING1": text_lit("차이 "),
                "STRING2": slot(j_inner, sk=10, sv="")})
    bs[j_inner]["parent"] = j_outer

    set_fb_no = gen(); bs[set_fb_no] = mk("data_setvariableto",
        inputs={"VALUE": slot(j_outer, sk=10, sv="")},
        fields={"VARIABLE": ["피드백", V_FEEDBACK]})
    bs[j_outer]["parent"] = set_fb_no

    if_else_try = gen(); bs[if_else_try] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_correct],
                "SUBSTACK":[2, inc_score],
                "SUBSTACK2":[2, set_fb_no]})
    bs[cond_correct]["parent"] = if_else_try
    bs[inc_score]["parent"] = if_else_try
    bs[set_fb_no]["parent"] = if_else_try

    chain([(set_diff, bs[set_diff]), (if_else_try, bs[if_else_try])])

    if_alive = gen(); bs[if_alive] = mk("control_if",
        inputs={"CONDITION":[2, cond_alive], "SUBSTACK":[2, set_diff]})
    bs[cond_alive]["parent"] = if_alive
    bs[set_diff]["parent"] = if_alive

    chain([(tryh, bs[tryh]), (if_alive, bs[if_alive])])

    # ---------- when receive BR_HINT ----------
    # V_HINT = join("정답: ", join(DM_rounded, join(" ΔM = 진폭 ", join(RATIO_rounded, " 배"))))
    hh = gen(); bs[hh] = mk("event_whenbroadcastreceived", top=True, x=20, y=900,
        fields={"BROADCAST_OPTION": ["힌트", BR_HINT]})

    # round DM_ANS to 1dp
    rAns_h = B.vrep("정답ΔM", V_DM_ANS)
    dm10 = B.op("operator_multiply", rAns_h, 10)
    dm10_add = B.op("operator_add", dm10, 0.5)
    fl_dm = gen(); bs[fl_dm] = mk("operator_mathop",
        inputs={"NUM": slot(dm10_add)}, fields={"OPERATOR": ["floor", None]})
    bs[dm10_add]["parent"] = fl_dm
    dm_div = B.op("operator_divide", fl_dm, 10)

    # round RATIO to integer (floor(r + 0.5))
    rRatio_h = B.vrep("진폭비", V_RATIO)
    r_add = B.op("operator_add", rRatio_h, 0.5)
    fl_r = gen(); bs[fl_r] = mk("operator_mathop",
        inputs={"NUM": slot(r_add)}, fields={"OPERATOR": ["floor", None]})
    bs[r_add]["parent"] = fl_r

    # innermost: join(ratio, " 배")
    j_h1 = gen(); bs[j_h1] = mk("operator_join",
        inputs={"STRING1": slot(fl_r, sk=10, sv=""),
                "STRING2": text_lit(" 배")})
    bs[fl_r]["parent"] = j_h1
    # join(" ΔM = 진폭 ", j_h1)
    j_h2 = gen(); bs[j_h2] = mk("operator_join",
        inputs={"STRING1": text_lit(" ΔM = 진폭 "),
                "STRING2": slot(j_h1, sk=10, sv="")})
    bs[j_h1]["parent"] = j_h2
    # join(dm_div, j_h2)
    j_h3 = gen(); bs[j_h3] = mk("operator_join",
        inputs={"STRING1": slot(dm_div, sk=10, sv=""),
                "STRING2": slot(j_h2, sk=10, sv="")})
    bs[dm_div]["parent"] = j_h3
    bs[j_h2]["parent"] = j_h3
    # join("정답: ", j_h3)
    j_h4 = gen(); bs[j_h4] = mk("operator_join",
        inputs={"STRING1": text_lit("정답: "),
                "STRING2": slot(j_h3, sk=10, sv="")})
    bs[j_h3]["parent"] = j_h4

    set_hint = gen(); bs[set_hint] = mk("data_setvariableto",
        inputs={"VALUE": slot(j_h4, sk=10, sv="")},
        fields={"VARIABLE": ["힌트", V_HINT]})
    bs[j_h4]["parent"] = set_hint

    chain([(hh, bs[hh]), (set_hint, bs[set_hint])])

    # ---------- when receive BR_GAMEOVER ----------
    goh = gen(); bs[goh] = mk("event_whenbroadcastreceived", top=True, x=400, y=900,
        fields={"BROADCAST_OPTION": ["게임오버", BR_GAMEOVER]})
    set_go = gen(); bs[set_go] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임오버", V_GAMEOVER]})
    rScore_end = B.vrep("점수", V_SCORE)
    j_end = gen(); bs[j_end] = mk("operator_join",
        inputs={"STRING1": text_lit("종료! 점수 "),
                "STRING2": slot(rScore_end, sk=10, sv="")})
    bs[rScore_end]["parent"] = j_end
    set_fb_end = gen(); bs[set_fb_end] = mk("data_setvariableto",
        inputs={"VALUE": slot(j_end, sk=10, sv="")},
        fields={"VARIABLE": ["피드백", V_FEEDBACK]})
    bs[j_end]["parent"] = set_fb_end

    chain([(goh, bs[goh]), (set_go, bs[set_go]), (set_fb_end, bs[set_fb_end])])

    return bs


# ============================================================
# Seismograph A sprite — bar that resizes by log10(A_amp)
# ============================================================
def build_seismo_a_blocks():
    B = BlockBuilder()
    bs = B.bs

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-115), "Y": num(-50)})
    sz_init = gen(); bs[sz_init] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz_init, bs[sz_init]), (sh, bs[sh])])

    # when receive BR_REDRAW: size = 20 + 60 * log(A_amp)
    # (log(1)=0 → size 20, log(100000)=5 → size 320 — but max useful ~280)
    # Use scaling: size = 30 + 50 * log(A_amp)  → log(1)=30, log(100000)=280
    rh = gen(); bs[rh] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["진폭갱신", BR_REDRAW]})

    rA = B.vrep("진폭A", V_A_AMP)
    log_a = B.mathop("log", rA)
    scaled = B.op("operator_multiply", log_a, 50)
    final = B.op("operator_add", scaled, 30)

    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto",
        inputs={"SIZE": slot(final)})
    bs[final]["parent"] = set_sz

    chain([(rh, bs[rh]), (set_sz, bs[set_sz])])
    return bs


# ============================================================
# Seismograph B sprite — same but for V_B_AMP
# ============================================================
def build_seismo_b_blocks():
    B = BlockBuilder()
    bs = B.bs

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(115), "Y": num(-50)})
    sz_init = gen(); bs[sz_init] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz_init, bs[sz_init]), (sh, bs[sh])])

    rh = gen(); bs[rh] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["진폭갱신", BR_REDRAW]})

    rB = B.vrep("진폭B", V_B_AMP)
    log_b = B.mathop("log", rB)
    scaled = B.op("operator_multiply", log_b, 50)
    final = B.op("operator_add", scaled, 30)

    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto",
        inputs={"SIZE": slot(final)})
    bs[final]["parent"] = set_sz

    chain([(rh, bs[rh]), (set_sz, bs[set_sz])])
    return bs


# ============================================================
# Judge sprite — say V_FEEDBACK
# ============================================================
def build_judge_blocks():
    B = BlockBuilder()
    bs = B.bs

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-140)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(75)})
    sh = gen(); bs[sh] = mk("looks_show")

    rFb = B.vrep("피드백", V_FEEDBACK)
    say = gen(); bs[say] = mk("looks_say", inputs={"MESSAGE": slot(rFb, sk=10, sv="")})
    bs[rFb]["parent"] = say
    w = gen(); bs[w] = mk("control_wait", inputs={"DURATION": num(0.1)})
    chain([(say, bs[say]), (w, bs[w])])
    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, say]})
    bs[say]["parent"] = fv

    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh]), (fv, bs[fv])])
    return bs


# ============================================================
# Hint button — click → BR_HINT
# ============================================================
def build_hint_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(180), "Y": num(-60)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh])])

    ch = gen(); bs[ch] = mk("event_whenthisspriteclicked", top=True, x=20, y=200)
    hm = gen(); bs[hm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["힌트", BR_HINT]}, shadow=True)
    hb = gen(); bs[hb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, hm]})
    bs[hm]["parent"] = hb
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

    # backgrounds
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    # sprite SVGs
    sa_md5 = md5_bytes(SEISMO_A_SVG.encode("utf-8"))
    with open(f"{WORK}/{sa_md5}.svg", "w", encoding="utf-8") as f:
        f.write(SEISMO_A_SVG)
    sb_md5 = md5_bytes(SEISMO_B_SVG.encode("utf-8"))
    with open(f"{WORK}/{sb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(SEISMO_B_SVG)
    jdg_md5 = md5_bytes(JUDGE_SVG.encode("utf-8"))
    with open(f"{WORK}/{jdg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(JUDGE_SVG)
    hb_md5 = md5_bytes(HINT_BTN_SVG.encode("utf-8"))
    with open(f"{WORK}/{hb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(HINT_BTN_SVG)

    # pop.wav
    pop_src = f"{ASSETS}/pop.wav"
    with open(pop_src, "rb") as f:
        pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    # Build blocks
    stage_blocks = build_stage_blocks()
    seismo_a_blocks = build_seismo_a_blocks()
    seismo_b_blocks = build_seismo_b_blocks()
    judge_blocks = build_judge_blocks()
    hint_blocks = build_hint_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_A0:       ["기준진폭", 1],
            V_A_AMP:    ["진폭A", 100],
            V_B_AMP:    ["진폭B", 10],
            V_MA:       ["매그A", 0],
            V_MB:       ["매그B", 0],
            V_DM_ANS:   ["정답ΔM", 0],
            V_DM_USER:  ["내답ΔM", 2.5],
            V_DIFF:     ["차이", 0],
            V_RATIO:    ["진폭비", 10],
            V_SCORE:    ["점수", 0],
            V_ROUND:    ["라운드", 0],
            V_TIME:     ["남은시간", 60],
            V_FEEDBACK: ["피드백", "준비"],
            V_HINT:     ["힌트", ""],
            V_GAMEOVER: ["게임오버", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:     "게임시작",
            BR_NEW_ROUND: "새라운드",
            BR_TRY:       "시도",
            BR_HINT:      "힌트",
            BR_GAMEOVER:  "게임오버",
            BR_REDRAW:    "진폭갱신",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "ground", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    seismo_a = {
        "isStage": False, "name": "시계A",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": seismo_a_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "seismoA", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": sa_md5, "md5ext": f"{sa_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 20
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": -115, "y": -50, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    seismo_b = {
        "isStage": False, "name": "시계B",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": seismo_b_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "seismoB", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": sb_md5, "md5ext": f"{sb_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 20
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": 115, "y": -50, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    judge = {
        "isStage": False, "name": "판정",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": judge_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "judge", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": jdg_md5, "md5ext": f"{jdg_md5}.svg",
            "rotationCenterX": 16, "rotationCenterY": 16
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": 0, "y": -140, "size": 75, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    hint = {
        "isStage": False, "name": "힌트버튼",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hint_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "hint", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hb_md5, "md5ext": f"{hb_md5}.svg",
            "rotationCenterX": 60, "rotationCenterY": 18
        }],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 4, "visible": True,
        "x": 180, "y": -60, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # ============================================================
    # Monitors
    # ============================================================
    monitors = [
        # Key input slider — ΔM (0..5, continuous)
        {"id": V_DM_USER, "mode": "slider", "opcode": "data_variable",
         "params": {"VARIABLE": "내답ΔM"}, "spriteName": None,
         "value": 2.5, "width": 0, "height": 0, "x": 5, "y": 200,
         "visible": True, "sliderMin": 0, "sliderMax": 5, "isDiscrete": False},

        # HUD top: score, round, time
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_TIME, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "남은시간"}, "spriteName": None,
         "value": 60, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},

        # City A info (left panel)
        {"id": V_A_AMP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "진폭A"}, "spriteName": None,
         "value": 100, "width": 0, "height": 0, "x": 5, "y": 100,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_MA, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "매그A"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 130,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},

        # City B info (right panel)
        {"id": V_B_AMP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "진폭B"}, "spriteName": None,
         "value": 10, "width": 0, "height": 0, "x": 330, "y": 100,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_MB, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "매그B"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 330, "y": 130,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},

        # Hint (large readout)
        {"id": V_HINT, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "힌트"}, "spriteName": None,
         "value": "", "width": 0, "height": 0, "x": 130, "y": 235,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, seismo_a, seismo_b, judge, hint],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "richter-tracker-builder"}
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

    n_blocks = sum(len(t["blocks"]) for t in project["targets"])
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"✓ wrote {OUTPUT} ({size_kb:.1f} KB, {n_blocks} blocks)")


if __name__ == "__main__":
    main()
