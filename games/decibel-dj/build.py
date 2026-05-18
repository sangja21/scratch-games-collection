#!/usr/bin/env python3
"""데시벨 DJ — 두 트랙의 합산 dB 를 슬라이더로 맞추는 로그 학습 게임.

핵심 공식: dB = 10 · log₁₀(I / I₀)
두 음원 합산: dB_total = 10 · log₁₀((I₁ + I₂) / I₀)

학습 포인트: 같은 dB 두 개를 더해도 +3 dB 만 추가됨 — 로그가 단순 덧셈이 아님.

build.py 베이스: games/exponential-shooter/build.py
"""
import json, os, wave, struct, math, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "데시벨_DJ.sb3")

# ============================================================
# SVG assets
# ============================================================
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="club" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1A0033"/>
      <stop offset="50%" stop-color="#2D0050"/>
      <stop offset="100%" stop-color="#10001A"/>
    </linearGradient>
    <radialGradient id="spot" cx="50%" cy="0%" r="60%">
      <stop offset="0%" stop-color="#FFD166" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#FFD166" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="480" height="360" fill="url(#club)"/>
  <rect width="480" height="360" fill="url(#spot)"/>
  <!-- Title strip -->
  <rect x="0" y="0" width="480" height="32" fill="#0A0014" opacity="0.85"/>
  <text x="240" y="22" fill="#FFD166" font-family="monospace" font-size="16"
    font-weight="bold" text-anchor="middle">🎧  데시벨  DJ  —  합산  dB  맞추기</text>

  <!-- Two track panels -->
  <g>
    <rect x="60"  y="60" width="160" height="110" rx="14" ry="14"
      fill="#3B1A4A" stroke="#FF5577" stroke-width="3" opacity="0.92"/>
    <text x="140" y="84" fill="#FF8FA8" font-family="monospace" font-size="14"
      font-weight="bold" text-anchor="middle">트랙 A</text>
    <text x="140" y="106" fill="#FFFFFF" font-family="monospace" font-size="11"
      text-anchor="middle" opacity="0.7">I₁ (강도)</text>
    <text x="140" y="146" fill="#FFFFFF" font-family="monospace" font-size="11"
      text-anchor="middle" opacity="0.7">dB₁</text>
  </g>
  <g>
    <rect x="260" y="60" width="160" height="110" rx="14" ry="14"
      fill="#1A2A4A" stroke="#55AAFF" stroke-width="3" opacity="0.92"/>
    <text x="340" y="84" fill="#8FB8FF" font-family="monospace" font-size="14"
      font-weight="bold" text-anchor="middle">트랙 B</text>
    <text x="340" y="106" fill="#FFFFFF" font-family="monospace" font-size="11"
      text-anchor="middle" opacity="0.7">I₂ (강도)</text>
    <text x="340" y="146" fill="#FFFFFF" font-family="monospace" font-size="11"
      text-anchor="middle" opacity="0.7">dB₂</text>
  </g>

  <!-- Slider region label -->
  <text x="240" y="200" fill="#A29BFE" font-family="monospace" font-size="13"
    font-weight="bold" text-anchor="middle">↓  합산 dB 슬라이더 (V_DB_USER) ↓</text>

  <!-- Bottom bar: target zone label -->
  <rect x="0" y="318" width="480" height="42" fill="#0A0014" opacity="0.85"/>
  <text x="240" y="338" fill="#FFD166" font-family="monospace" font-size="12"
    text-anchor="middle">Space = 통과 시도 (오차 ±1.0 dB 이내면 정답)</text>
  <text x="240" y="354" fill="#A29BFE" font-family="monospace" font-size="11"
    text-anchor="middle" opacity="0.8">힌트 버튼 = 정답 노출 (학습용)</text>
</svg>"""

# Track A sprite — red music note panel
TRACK_A_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <circle cx="30" cy="30" r="26" fill="#FF5577" stroke="#FFFFFF" stroke-width="2"/>
  <text x="30" y="40" fill="#FFFFFF" font-family="serif" font-size="34"
    text-anchor="middle" font-weight="bold">♪</text>
</svg>"""

# Track B sprite — blue music note panel
TRACK_B_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <circle cx="30" cy="30" r="26" fill="#55AAFF" stroke="#FFFFFF" stroke-width="2"/>
  <text x="30" y="40" fill="#FFFFFF" font-family="serif" font-size="34"
    text-anchor="middle" font-weight="bold">♫</text>
</svg>"""

# Judge sprite — small invisible (uses say balloon for feedback)
JUDGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="14" fill="#7C5CFF" stroke="#FFFFFF" stroke-width="2"/>
  <text x="16" y="22" fill="#FFFFFF" font-family="monospace" font-size="14"
    text-anchor="middle" font-weight="bold">!</text>
</svg>"""

# Hint button sprite — clickable
HINT_BTN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="36" viewBox="0 0 120 36">
  <rect x="1" y="1" width="118" height="34" rx="17" ry="17"
    fill="#7C5CFF" stroke="#FFFFFF" stroke-width="2"/>
  <text x="60" y="23" fill="#FFFFFF" font-family="sans-serif" font-size="14"
    font-weight="bold" text-anchor="middle">힌트 ▼</text>
</svg>"""


# ============================================================
# helpers (copied from exponential-shooter)
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
V_I1       = "varI1_001"
V_I2       = "varI2_002"
V_I0       = "varI0_003"
V_DB1      = "varDb1_004"
V_DB2      = "varDb2_005"
V_DB_ANS   = "varDbAns_006"
V_DB_USER  = "varDbUser_007"
V_SCORE    = "varScore_008"
V_ROUND    = "varRound_009"
V_TIME     = "varTime_010"
V_FEEDBACK = "varFeedback_011"
V_HINT     = "varHint_012"
V_GAMEOVER = "varGameover_013"
V_DIFF     = "varDiff_014"   # temp |user - ans|

BR_START      = "brStart_001"
BR_NEW_ROUND  = "brNewRound_002"
BR_TRY        = "brTry_003"
BR_HINT       = "brHint_004"
BR_GAMEOVER   = "brGameover_005"


# ============================================================
# BlockBuilder class (math helpers)
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

    def db_from_intensity(self, intensity_var_name, intensity_vid):
        """Build a block tree computing 10 · log₁₀(I / I₀)."""
        rI = self.vrep(intensity_var_name, intensity_vid)
        rI0 = self.vrep("기준강도", V_I0)
        ratio = self.op("operator_divide", rI, rI0)
        log_ratio = self.mathop("log", ratio)
        return self.op("operator_multiply", 10, log_ratio)


# ============================================================
# STAGE blocks — game logic
# ============================================================
def build_stage_blocks():
    B = BlockBuilder()
    bs = B.bs

    # ---------- when flag clicked: init + start timer loop ----------
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

    set_var("기준강도", V_I0, 1000)
    set_var("점수", V_SCORE, 0)
    set_var("라운드", V_ROUND, 0)
    set_var("남은시간", V_TIME, 60)
    set_var("게임오버", V_GAMEOVER, 0)
    set_var("피드백", V_FEEDBACK, "준비")
    set_var("힌트", V_HINT, "")
    set_var("내답dB", V_DB_USER, 60)
    set_var("I1", V_I1, 0)
    set_var("I2", V_I2, 0)
    set_var("dB1", V_DB1, 0)
    set_var("dB2", V_DB2, 0)
    set_var("정답dB", V_DB_ANS, 0)
    set_var("차이", V_DIFF, 0)

    # broadcast BR_NEW_ROUND
    nrm = gen(); bs[nrm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]}, shadow=True)
    nrb = gen(); bs[nrb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, nrm]})
    bs[nrm]["parent"] = nrb

    chain([(h, bs[h])] + [(bid, bs[bid]) for bid in inits] + [(nrb, bs[nrb])])

    # ---------- timer loop: forever wait 1; decrement time ----------
    # Reset timer first
    rt = gen(); bs[rt] = mk("sensing_resettimer")

    th = gen(); bs[th] = mk("event_whenflagclicked", top=True, x=20, y=300)

    # wait 1 sec
    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(1)})
    # if V_GAMEOVER = 0
    rgo = B.vrep("게임오버", V_GAMEOVER)
    cond_go = gen(); bs[cond_go] = mk("operator_equals",
        inputs={"OPERAND1": slot(rgo), "OPERAND2": num(0)})
    bs[rgo]["parent"] = cond_go
    # change V_TIME by -1
    dec_t = gen(); bs[dec_t] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["남은시간", V_TIME]})
    # if V_TIME <= 0 -> broadcast GAMEOVER
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

    # set V_FEEDBACK = "트랙 합산 dB 를 맞춰라"
    set_fb = gen(); bs[set_fb] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("트랙 합산 dB 를 맞춰라")},
        fields={"VARIABLE": ["피드백", V_FEEDBACK]})

    # ---- Round 1..5 fixed scenarios, else random ----
    # Build: if R=1: I1=10000,I2=10000; if R=2: 100000,100000; ...
    FIXED = [
        (1, 10000,   10000),
        (2, 100000,  100000),
        (3, 1000000, 100),
        (4, 100000,  50000),
        (5, 1000,    1000),
    ]
    round_branches = []
    for R, i1v, i2v in FIXED:
        rR = B.vrep("라운드", V_ROUND)
        eqR = gen(); bs[eqR] = mk("operator_equals",
            inputs={"OPERAND1": slot(rR), "OPERAND2": num(R)})
        bs[rR]["parent"] = eqR

        si1 = gen(); bs[si1] = mk("data_setvariableto",
            inputs={"VALUE": num(i1v)}, fields={"VARIABLE": ["I1", V_I1]})
        si2 = gen(); bs[si2] = mk("data_setvariableto",
            inputs={"VALUE": num(i2v)}, fields={"VARIABLE": ["I2", V_I2]})
        chain([(si1, bs[si1]), (si2, bs[si2])])

        if_R = gen(); bs[if_R] = mk("control_if",
            inputs={"CONDITION":[2, eqR], "SUBSTACK":[2, si1]})
        bs[eqR]["parent"] = if_R
        bs[si1]["parent"] = if_R
        round_branches.append(if_R)

    # else (R >= 6): I1 = 10^(random 3..7), I2 = 10^(random 3..7)
    rR_else = B.vrep("라운드", V_ROUND)
    cond_else = gen(); bs[cond_else] = mk("operator_gt",
        inputs={"OPERAND1": slot(rR_else), "OPERAND2": num(5)})
    bs[rR_else]["parent"] = cond_else

    # I1: 10^(random 3..7)
    rnd1 = gen(); bs[rnd1] = mk("operator_random",
        inputs={"FROM": num(3), "TO": num(7)})
    pow10_1 = gen(); bs[pow10_1] = mk("operator_mathop",
        inputs={"NUM": slot(rnd1)}, fields={"OPERATOR": ["10 ^", None]})
    bs[rnd1]["parent"] = pow10_1
    set_i1_rnd = gen(); bs[set_i1_rnd] = mk("data_setvariableto",
        inputs={"VALUE": slot(pow10_1)}, fields={"VARIABLE": ["I1", V_I1]})
    bs[pow10_1]["parent"] = set_i1_rnd

    rnd2 = gen(); bs[rnd2] = mk("operator_random",
        inputs={"FROM": num(3), "TO": num(7)})
    pow10_2 = gen(); bs[pow10_2] = mk("operator_mathop",
        inputs={"NUM": slot(rnd2)}, fields={"OPERATOR": ["10 ^", None]})
    bs[rnd2]["parent"] = pow10_2
    set_i2_rnd = gen(); bs[set_i2_rnd] = mk("data_setvariableto",
        inputs={"VALUE": slot(pow10_2)}, fields={"VARIABLE": ["I2", V_I2]})
    bs[pow10_2]["parent"] = set_i2_rnd

    chain([(set_i1_rnd, bs[set_i1_rnd]), (set_i2_rnd, bs[set_i2_rnd])])

    if_else = gen(); bs[if_else] = mk("control_if",
        inputs={"CONDITION":[2, cond_else], "SUBSTACK":[2, set_i1_rnd]})
    bs[cond_else]["parent"] = if_else
    bs[set_i1_rnd]["parent"] = if_else

    round_branches.append(if_else)

    # chain all round branches in sequence
    chain([(bid, bs[bid]) for bid in round_branches])

    # ---- compute dB1, dB2, dB_ANS ----
    # V_DB1 = round1dp(10 · log(I1 / I0))
    db1_raw = B.db_from_intensity("I1", V_I1)
    db1_rounded = B.round_to_1dp(db1_raw)
    set_db1 = gen(); bs[set_db1] = mk("data_setvariableto",
        inputs={"VALUE": slot(db1_rounded)},
        fields={"VARIABLE": ["dB1", V_DB1]})
    bs[db1_rounded]["parent"] = set_db1

    db2_raw = B.db_from_intensity("I2", V_I2)
    db2_rounded = B.round_to_1dp(db2_raw)
    set_db2 = gen(); bs[set_db2] = mk("data_setvariableto",
        inputs={"VALUE": slot(db2_rounded)},
        fields={"VARIABLE": ["dB2", V_DB2]})
    bs[db2_rounded]["parent"] = set_db2

    # V_DB_ANS = 10 · log((I1 + I2) / I0)  (NOT rounded — compared with ±1.0)
    rI1_ans = B.vrep("I1", V_I1)
    rI2_ans = B.vrep("I2", V_I2)
    sum_i = B.op("operator_add", rI1_ans, rI2_ans)
    rI0_ans = B.vrep("기준강도", V_I0)
    ratio_ans = B.op("operator_divide", sum_i, rI0_ans)
    log_ans = B.mathop("log", ratio_ans)
    mul10_ans = B.op("operator_multiply", 10, log_ans)
    set_ans = gen(); bs[set_ans] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul10_ans)},
        fields={"VARIABLE": ["정답dB", V_DB_ANS]})
    bs[mul10_ans]["parent"] = set_ans

    # chain new-round flow
    chain([(nh, bs[nh]), (inc_r, bs[inc_r]), (set_hint_empty, bs[set_hint_empty]),
           (set_fb, bs[set_fb])] +
          [(round_branches[0], bs[round_branches[0]])])
    # set_fb -> first branch already linked via chain above; need to link last branch -> set_db1
    chain([(round_branches[-1], bs[round_branches[-1]]),
           (set_db1, bs[set_db1]), (set_db2, bs[set_db2]), (set_ans, bs[set_ans])])

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

    # compute V_DIFF = abs(V_DB_USER - V_DB_ANS)
    rUser = B.vrep("내답dB", V_DB_USER)
    rAns = B.vrep("정답dB", V_DB_ANS)
    sub_ua = B.op("operator_subtract", rUser, rAns)
    abs_diff = gen(); bs[abs_diff] = mk("operator_mathop",
        inputs={"NUM": slot(sub_ua)}, fields={"OPERATOR": ["abs", None]})
    bs[sub_ua]["parent"] = abs_diff
    set_diff = gen(); bs[set_diff] = mk("data_setvariableto",
        inputs={"VALUE": slot(abs_diff)},
        fields={"VARIABLE": ["차이", V_DIFF]})
    bs[abs_diff]["parent"] = set_diff

    # if V_DIFF < 1.0 → correct path; else → wrong path
    rDiff = B.vrep("차이", V_DIFF)
    cond_correct = gen(); bs[cond_correct] = mk("operator_lt",
        inputs={"OPERAND1": slot(rDiff), "OPERAND2": num(1)})
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
    w_ok = gen(); bs[w_ok] = mk("control_wait", inputs={"DURATION": num(0.4)})
    nrm2 = gen(); bs[nrm2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]}, shadow=True)
    nrb2 = gen(); bs[nrb2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, nrm2]})
    bs[nrm2]["parent"] = nrb2
    chain([(inc_score, bs[inc_score]), (set_fb_ok, bs[set_fb_ok]),
           (pp, bs[pp]), (w_ok, bs[w_ok]), (nrb2, bs[nrb2])])

    # === WRONG branch ===
    # Build feedback string: join("차이 ", join(round(diff·10)/10, " dB"))
    rDiff2 = B.vrep("차이", V_DIFF)
    d10 = B.op("operator_multiply", rDiff2, 10)
    d10_add_half = B.op("operator_add", d10, 0.5)
    fl_w = gen(); bs[fl_w] = mk("operator_mathop",
        inputs={"NUM": slot(d10_add_half)}, fields={"OPERATOR": ["floor", None]})
    bs[d10_add_half]["parent"] = fl_w
    d10_div = B.op("operator_divide", fl_w, 10)

    j_inner = gen(); bs[j_inner] = mk("operator_join",
        inputs={"STRING1": slot(d10_div, sk=10, sv=""),
                "STRING2": text_lit(" dB")})
    bs[d10_div]["parent"] = j_inner
    j_outer = gen(); bs[j_outer] = mk("operator_join",
        inputs={"STRING1": text_lit("차이 "),
                "STRING2": slot(j_inner, sk=10, sv="")})
    bs[j_inner]["parent"] = j_outer

    set_fb_no = gen(); bs[set_fb_no] = mk("data_setvariableto",
        inputs={"VALUE": slot(j_outer, sk=10, sv="")},
        fields={"VARIABLE": ["피드백", V_FEEDBACK]})
    bs[j_outer]["parent"] = set_fb_no

    # ifElse: correct vs wrong
    if_else_try = gen(); bs[if_else_try] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_correct],
                "SUBSTACK":[2, inc_score],
                "SUBSTACK2":[2, set_fb_no]})
    bs[cond_correct]["parent"] = if_else_try
    bs[inc_score]["parent"] = if_else_try
    bs[set_fb_no]["parent"] = if_else_try

    chain([(set_diff, bs[set_diff]), (if_else_try, bs[if_else_try])])

    # wrap with if alive
    if_alive = gen(); bs[if_alive] = mk("control_if",
        inputs={"CONDITION":[2, cond_alive], "SUBSTACK":[2, set_diff]})
    bs[cond_alive]["parent"] = if_alive
    bs[set_diff]["parent"] = if_alive

    chain([(tryh, bs[tryh]), (if_alive, bs[if_alive])])

    # ---------- when receive BR_HINT ----------
    hh = gen(); bs[hh] = mk("event_whenbroadcastreceived", top=True, x=20, y=900,
        fields={"BROADCAST_OPTION": ["힌트", BR_HINT]})
    # V_HINT = join("정답: ", join(round(V_DB_ANS·10)/10, " dB"))
    rAns_h = B.vrep("정답dB", V_DB_ANS)
    a10 = B.op("operator_multiply", rAns_h, 10)
    a10_add = B.op("operator_add", a10, 0.5)
    fl_h = gen(); bs[fl_h] = mk("operator_mathop",
        inputs={"NUM": slot(a10_add)}, fields={"OPERATOR": ["floor", None]})
    bs[a10_add]["parent"] = fl_h
    a10_div = B.op("operator_divide", fl_h, 10)

    jh_inner = gen(); bs[jh_inner] = mk("operator_join",
        inputs={"STRING1": slot(a10_div, sk=10, sv=""),
                "STRING2": text_lit(" dB")})
    bs[a10_div]["parent"] = jh_inner
    jh_outer = gen(); bs[jh_outer] = mk("operator_join",
        inputs={"STRING1": text_lit("정답: "),
                "STRING2": slot(jh_inner, sk=10, sv="")})
    bs[jh_inner]["parent"] = jh_outer

    set_hint = gen(); bs[set_hint] = mk("data_setvariableto",
        inputs={"VALUE": slot(jh_outer, sk=10, sv="")},
        fields={"VARIABLE": ["힌트", V_HINT]})
    bs[jh_outer]["parent"] = set_hint

    chain([(hh, bs[hh]), (set_hint, bs[set_hint])])

    # ---------- when receive BR_GAMEOVER ----------
    goh = gen(); bs[goh] = mk("event_whenbroadcastreceived", top=True, x=400, y=900,
        fields={"BROADCAST_OPTION": ["게임오버", BR_GAMEOVER]})
    set_go = gen(); bs[set_go] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임오버", V_GAMEOVER]})
    # final feedback
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
# Track A sprite — visual decoration
# ============================================================
def build_track_a_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-100), "Y": num(70)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    sh = gen(); bs[sh] = mk("looks_show")

    # bounce loop
    cy1 = gen(); bs[cy1] = mk("motion_changeyby", inputs={"DY": num(3)})
    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(0.3)})
    cy2 = gen(); bs[cy2] = mk("motion_changeyby", inputs={"DY": num(-3)})
    w2 = gen(); bs[w2] = mk("control_wait", inputs={"DURATION": num(0.3)})
    chain([(cy1, bs[cy1]), (w1, bs[w1]), (cy2, bs[cy2]), (w2, bs[w2])])
    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, cy1]})
    bs[cy1]["parent"] = fv

    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh]), (fv, bs[fv])])
    return bs


# ============================================================
# Track B sprite — same pattern, different position
# ============================================================
def build_track_b_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(100), "Y": num(70)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    sh = gen(); bs[sh] = mk("looks_show")

    cy1 = gen(); bs[cy1] = mk("motion_changeyby", inputs={"DY": num(3)})
    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(0.35)})
    cy2 = gen(); bs[cy2] = mk("motion_changeyby", inputs={"DY": num(-3)})
    w2 = gen(); bs[w2] = mk("control_wait", inputs={"DURATION": num(0.35)})
    chain([(cy1, bs[cy1]), (w1, bs[w1]), (cy2, bs[cy2]), (w2, bs[w2])])
    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, cy1]})
    bs[cy1]["parent"] = fv

    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh]), (fv, bs[fv])])
    return bs


# ============================================================
# Judge sprite — speaks V_FEEDBACK
# ============================================================
def build_judge_blocks():
    B = BlockBuilder()
    bs = B.bs

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-90)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    sh = gen(); bs[sh] = mk("looks_show")

    # forever: say V_FEEDBACK
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
# Hint button sprite — click → broadcast BR_HINT
# ============================================================
def build_hint_blocks():
    bs = {}
    # init position
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(180), "Y": num(-30)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh])])

    # on click → broadcast BR_HINT + pop sound
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
    ta_md5 = md5_bytes(TRACK_A_SVG.encode("utf-8"))
    with open(f"{WORK}/{ta_md5}.svg", "w", encoding="utf-8") as f:
        f.write(TRACK_A_SVG)
    tb_md5 = md5_bytes(TRACK_B_SVG.encode("utf-8"))
    with open(f"{WORK}/{tb_md5}.svg", "w", encoding="utf-8") as f:
        f.write(TRACK_B_SVG)
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
    track_a_blocks = build_track_a_blocks()
    track_b_blocks = build_track_b_blocks()
    judge_blocks = build_judge_blocks()
    hint_blocks = build_hint_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_I0:       ["기준강도", 1000],
            V_I1:       ["I1", 0],
            V_I2:       ["I2", 0],
            V_DB1:      ["dB1", 0],
            V_DB2:      ["dB2", 0],
            V_DB_ANS:   ["정답dB", 0],
            V_DB_USER:  ["내답dB", 60],
            V_SCORE:    ["점수", 0],
            V_ROUND:    ["라운드", 0],
            V_TIME:     ["남은시간", 60],
            V_FEEDBACK: ["피드백", "준비"],
            V_HINT:     ["힌트", ""],
            V_GAMEOVER: ["게임오버", 0],
            V_DIFF:     ["차이", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:     "게임시작",
            BR_NEW_ROUND: "새라운드",
            BR_TRY:       "시도",
            BR_HINT:      "힌트",
            BR_GAMEOVER:  "게임오버",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "club", "dataFormat": "svg",
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

    track_a = {
        "isStage": False, "name": "트랙A",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": track_a_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "trackA", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ta_md5, "md5ext": f"{ta_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": -100, "y": 70, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    track_b = {
        "isStage": False, "name": "트랙B",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": track_b_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "trackB", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": tb_md5, "md5ext": f"{tb_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": 100, "y": 70, "size": 85, "direction": 90,
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
        "x": 0, "y": -90, "size": 80, "direction": 90,
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
        "x": 180, "y": -30, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # ============================================================
    # Monitors — slider for V_DB_USER, default for others
    # ============================================================
    monitors = [
        # Slider for user input — KEY learning interaction
        {"id": V_DB_USER, "mode": "slider", "opcode": "data_variable",
         "params": {"VARIABLE": "내답dB"}, "spriteName": None,
         "value": 60, "width": 0, "height": 0, "x": 5, "y": 200,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": False},

        # HUD: score, round, time
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

        # Track A info
        {"id": V_I1, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "I1"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 100,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_DB1, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "dB1"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 130,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},

        # Track B info
        {"id": V_I2, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "I2"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 330, "y": 100,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_DB2, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "dB2"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 330, "y": 130,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},

        # Hint (only shown after clicking 힌트 button)
        {"id": V_HINT, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "힌트"}, "spriteName": None,
         "value": "", "width": 0, "height": 0, "x": 130, "y": 235,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, track_a, track_b, judge, hint],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "decibel-dj-builder"}
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
