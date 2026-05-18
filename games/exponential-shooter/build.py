#!/usr/bin/env python3
"""Generate a Scratch 3.0 .sb3 exponential-curve shooter game.

Curve: y = a · b^x   (a: 0.5..5.0, b: 0.3..3.0)
Scratch has no `^` operator. We compute b^x as:

    b^x = 10^(x · log10(b))   ← itself a learning point (a^b = 10^(b·log a))

via two `operator_mathop` blocks (`log` then `10 ^`).

Coordinate transform (논리 x_g in [-6, 6]):

    screen_x = 40 · x_g
    선형 (V_LOG=0):  screen_y = 30 · (a · b^x_g) - 120
    로그 (V_LOG=1):  screen_y = 30 · log10(a · b^x_g) - 30
                            = 30 · (log10(a) + x_g · log10(b)) - 30   ← 직선!

This is reused by the curve-preview pen sprite AND the rocket fly path.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "지수함수_슈터.sb3")

# ---------- backgrounds ----------
BG_LINEAR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0F2027"/>
      <stop offset="60%" stop-color="#203A43"/>
      <stop offset="100%" stop-color="#2C5364"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <!-- grid (선형: 균등 간격) -->
  <g stroke="#3A6478" stroke-width="0.6" opacity="0.55">
    <line x1="0" y1="60"  x2="480" y2="60"/>
    <line x1="0" y1="120" x2="480" y2="120"/>
    <line x1="0" y1="180" x2="480" y2="180"/>
    <line x1="0" y1="240" x2="480" y2="240"/>
    <line x1="0" y1="300" x2="480" y2="300"/>
    <line x1="60"  y1="0" x2="60"  y2="360"/>
    <line x1="120" y1="0" x2="120" y2="360"/>
    <line x1="180" y1="0" x2="180" y2="360"/>
    <line x1="240" y1="0" x2="240" y2="360"/>
    <line x1="300" y1="0" x2="300" y2="360"/>
    <line x1="360" y1="0" x2="360" y2="360"/>
    <line x1="420" y1="0" x2="420" y2="360"/>
  </g>
  <!-- axes -->
  <g stroke="#6FB3D2" stroke-width="2" opacity="0.85">
    <!-- x-axis: screen y = -120 → svg y = 180+120 = 300 -->
    <line x1="0" y1="300" x2="480" y2="300"/>
    <!-- y-axis: screen x = 0 → svg x = 240 -->
    <line x1="240" y1="0" x2="240" y2="360"/>
  </g>
  <!-- y-tick labels (linear: 0, 2, 4, 6, 8) -->
  <g fill="#A8D8EA" font-family="monospace" font-size="11">
    <text x="246" y="296">0</text>
    <text x="246" y="236">2</text>
    <text x="246" y="176">4</text>
    <text x="246" y="116">6</text>
    <text x="246" y="56">8</text>
  </g>
  <!-- x-tick labels (every 40px = 1 unit) -->
  <g fill="#A8D8EA" font-family="monospace" font-size="11">
    <text x="44"  y="316">-5</text>
    <text x="124" y="316">-3</text>
    <text x="204" y="316">-1</text>
    <text x="284" y="316">1</text>
    <text x="364" y="316">3</text>
    <text x="444" y="316">5</text>
  </g>
  <!-- mode label -->
  <text x="380" y="22" fill="#FFD166" font-family="monospace" font-size="14" font-weight="bold">선형 스케일</text>
</svg>"""

BG_LOG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1A2980"/>
      <stop offset="60%" stop-color="#26303A"/>
      <stop offset="100%" stop-color="#0F1626"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky2)"/>
  <!-- log grid: y maps log10(v); v=0.01→y=-60, v=0.1→y=-30, v=1→y=0, v=10→y=30, v=100→y=60, v=1000→y=90 -->
  <!-- screen_y = 30·log10(v) - 30, so v=1 → svg y = 180+30 = 210; v=10 → svg y=180; v=100→150; v=1000→120; v=0.1→240; v=0.01→270 -->
  <g stroke="#5A4FCF" stroke-width="0.6" opacity="0.45">
    <line x1="0" y1="270" x2="480" y2="270"/>
    <line x1="0" y1="240" x2="480" y2="240"/>
    <line x1="0" y1="210" x2="480" y2="210"/>
    <line x1="0" y1="180" x2="480" y2="180"/>
    <line x1="0" y1="150" x2="480" y2="150"/>
    <line x1="0" y1="120" x2="480" y2="120"/>
    <line x1="0" y1="90"  x2="480" y2="90"/>
    <line x1="0" y1="60"  x2="480" y2="60"/>
    <line x1="60"  y1="0" x2="60"  y2="360"/>
    <line x1="120" y1="0" x2="120" y2="360"/>
    <line x1="180" y1="0" x2="180" y2="360"/>
    <line x1="240" y1="0" x2="240" y2="360"/>
    <line x1="300" y1="0" x2="300" y2="360"/>
    <line x1="360" y1="0" x2="360" y2="360"/>
    <line x1="420" y1="0" x2="420" y2="360"/>
  </g>
  <g stroke="#A29BFE" stroke-width="2" opacity="0.85">
    <!-- log x-axis at v=1 → svg y = 210 -->
    <line x1="0" y1="210" x2="480" y2="210"/>
    <line x1="240" y1="0" x2="240" y2="360"/>
  </g>
  <!-- y tick labels (log: 0.01, 0.1, 1, 10, 100, 1000) -->
  <g fill="#C9C5F0" font-family="monospace" font-size="11">
    <text x="246" y="274">0.01</text>
    <text x="246" y="244">0.1</text>
    <text x="246" y="214">1</text>
    <text x="246" y="184">10</text>
    <text x="246" y="154">100</text>
    <text x="246" y="124">1000</text>
  </g>
  <g fill="#C9C5F0" font-family="monospace" font-size="11">
    <text x="44"  y="226">-5</text>
    <text x="124" y="226">-3</text>
    <text x="204" y="226">-1</text>
    <text x="284" y="226">1</text>
    <text x="364" y="226">3</text>
    <text x="444" y="226">5</text>
  </g>
  <text x="380" y="22" fill="#FFD166" font-family="monospace" font-size="14" font-weight="bold">로그 스케일</text>
</svg>"""

# Tiny placeholder for invisible sprites
TINY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8"><rect width="8" height="8" fill="none"/></svg>"""

# Log toggle button (clickable sprite)
TOGGLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="36" viewBox="0 0 120 36">
  <rect x="1" y="1" width="118" height="34" rx="17" ry="17" fill="#FF6B9D" stroke="#FFF" stroke-width="2"/>
  <text x="60" y="23" fill="white" font-family="sans-serif" font-size="14" font-weight="bold" text-anchor="middle">로그 보기 ▼</text>
</svg>"""

# ---------- helpers ----------
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

# ---------- Variable & broadcast IDs ----------
V_A       = "varA001"      # base coefficient
V_B       = "varB002"      # exponent base
V_SCORE   = "varScore003"
V_XSTEP   = "varXStep004"  # current x_g for rocket
V_BCOUNT  = "varBCount005"
V_ROUND   = "varRound006"
V_PREV_X  = "varPrevX007"  # local to curve preview
V_EQ      = "varEq008"     # equation string
V_LOG     = "varLog009"    # 0 = linear, 1 = log
V_BIDX    = "varBIdx010"   # balloon spawn index (local)
BR_START      = "brStart002"
BR_NEW_ROUND  = "brNew001"
BR_DRAW_CURVE = "brDraw003"
BR_TOGGLE_LOG = "brToggle004"
BR_FIRE       = "brFire005"


# ============================================================
# Block-builder helpers shared by all sprites
# ============================================================
class BlockBuilder:
    def __init__(self):
        self.bs = {}

    def vrep(self, name, vid):
        bid = gen()
        self.bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid

    def op(self, opcode, a, b_):
        """Binary numeric operator; a/b_ are either python number or block-id."""
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
        """Unary mathop (sqrt, log, 10 ^, ln, e ^, abs, floor, ceiling, sin, cos, tan, asin, acos, atan)."""
        bid = gen()
        ins = {"NUM": slot(inner) if isinstance(inner, str) else num(inner)}
        self.bs[bid] = mk("operator_mathop",
            inputs=ins, fields={"OPERATOR": [name, None]})
        if isinstance(inner, str):
            self.bs[inner]["parent"] = bid
        return bid

    def pow_b_x(self, x_block_or_num):
        """Compute b^x = 10^(x · log10(b))."""
        rB = self.vrep("b", V_B)
        log_b = self.mathop("log", rB)
        prod = self.op("operator_multiply", x_block_or_num, log_b)
        return self.mathop("10 ^", prod)

    def eval_y_value(self, x_block_or_num):
        """Compute a · b^x  (the y-value, not screen position)."""
        rA = self.vrep("a", V_A)
        return self.op("operator_multiply", rA, self.pow_b_x(x_block_or_num))

    def screen_x_of(self, x_g_block_or_num):
        """screen_x = 40 · x_g."""
        return self.op("operator_multiply", 40, x_g_block_or_num)

    def screen_y_linear_of_value(self, y_val_block):
        """screen_y = 30 · y_val - 120."""
        return self.op("operator_subtract",
                       self.op("operator_multiply", 30, y_val_block),
                       120)

    def screen_y_log_of_value(self, y_val_block):
        """screen_y = 30 · log10(y_val) - 30."""
        return self.op("operator_subtract",
                       self.op("operator_multiply", 30, self.mathop("log", y_val_block)),
                       30)

    def screen_y_of(self, x_g_block_or_num):
        """If V_LOG = 1 use log transform else linear. Builds an if/else expression
        via two parallel calculations multiplied/added by indicator. We can't easily
        do conditional expression — but we can use:

            screen_y = V_LOG · screen_y_log + (1 - V_LOG) · screen_y_linear

        Since V_LOG is 0 or 1, this gives the right value without branching.
        We need to be careful: when V_LOG=0 (linear) we want screen_y_linear regardless
        of log10 result. log10(0 or neg) returns NaN-ish in Scratch but multiplying by 0
        yields 0 in Scratch (NaN · 0 = 0 in Scratch's arithmetic). So this is safe
        as long as a > 0 and b > 0 (slider mins enforce this)."""
        # Need two separate evaluations of y_val so each branch has its own tree.
        y_val_lin = self.eval_y_value(x_g_block_or_num)
        sy_lin = self.screen_y_linear_of_value(y_val_lin)

        # For the log branch we need to re-eval x_g_block fresh if it's a block ref.
        # We can't reuse blocks (each must have unique parent), so this helper
        # ASSUMES x is a numeric variable read (like vrep) — caller builds two reads.
        # To keep it simple, instead build the log version inline at call site.
        # This method is not used externally; we inline both branches below.
        raise NotImplementedError("inline both branches at the call site")

    def blend_log_linear(self, y_screen_linear_block, y_screen_log_block):
        """screen_y = V_LOG · log_branch + (1 - V_LOG) · linear_branch."""
        rL1 = self.vrep("로그", V_LOG)
        rL2 = self.vrep("로그", V_LOG)
        one_minus = self.op("operator_subtract", 1, rL2)
        lin_part = self.op("operator_multiply", one_minus, y_screen_linear_block)
        log_part = self.op("operator_multiply", rL1, y_screen_log_block)
        return self.op("operator_add", lin_part, log_part)

    def build_screen_xy(self, x_g_var_name, x_g_var_id):
        """Build screen-x and screen-y blocks for a given x_g variable. Returns (sx_id, sy_id).

        Builds:
          screen_x = 40 · x_g
          screen_y = V_LOG · (30·log10(a·b^x) - 30) + (1-V_LOG) · (30·(a·b^x) - 120)
        """
        # screen x
        rX_sx = self.vrep(x_g_var_name, x_g_var_id)
        sx = self.op("operator_multiply", 40, rX_sx)

        # linear branch
        rX_lin = self.vrep(x_g_var_name, x_g_var_id)
        y_val_lin = self.eval_y_value(rX_lin)
        sy_lin = self.screen_y_linear_of_value(y_val_lin)

        # log branch
        rX_log = self.vrep(x_g_var_name, x_g_var_id)
        y_val_log = self.eval_y_value(rX_log)
        sy_log = self.screen_y_log_of_value(y_val_log)

        sy = self.blend_log_linear(sy_lin, sy_log)
        return sx, sy


# ============================================================
# ROCKET sprite
# ============================================================
def build_rocket_blocks():
    B = BlockBuilder()
    bs = B.bs

    # === when flag clicked: init + hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sa = gen(); bs[sa] = mk("data_setvariableto",
        inputs={"VALUE": num(2.0)}, fields={"VARIABLE": ["a", V_A]})
    sb = gen(); bs[sb] = mk("data_setvariableto",
        inputs={"VALUE": num(1.5)}, fields={"VARIABLE": ["b", V_B]})
    sl = gen(); bs[sl] = mk("data_setvariableto",
        inputs={"VALUE": num(0)},   fields={"VARIABLE": ["로그", V_LOG]})
    ss = gen(); bs[ss] = mk("data_setvariableto",
        inputs={"VALUE": num(0)},   fields={"VARIABLE": ["점수", V_SCORE]})
    sr = gen(); bs[sr] = mk("data_setvariableto",
        inputs={"VALUE": num(1)},   fields={"VARIABLE": ["라운드", V_ROUND]})
    siz = gen(); bs[siz] = mk("looks_setsizeto", inputs={"SIZE": num(110)})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-240), "Y": num(-120)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    hi = gen(); bs[hi] = mk("looks_hide")

    sm = gen(); bs[sm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    sb_b = gen(); bs[sb_b] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, sm]})
    bs[sm]["parent"] = sb_b

    chain([(h,bs[h]),(sa,bs[sa]),(sb,bs[sb]),(sl,bs[sl]),(ss,bs[ss]),(sr,bs[sr]),
           (siz,bs[siz]),(g,bs[g]),(pdir,bs[pdir]),(hi,bs[hi]),(sb_b,bs[sb_b])])

    # === arrow keys for fine-tuning a, b ===
    def key_change(key, var_name, vid, delta, ypos):
        kh = gen(); bs[kh] = mk("event_whenkeypressed", top=True, x=20, y=ypos,
            fields={"KEY_OPTION": [key, None]})
        kc = gen(); bs[kc] = mk("data_changevariableby",
            inputs={"VALUE": num(delta)}, fields={"VARIABLE": [var_name, vid]})
        chain([(kh,bs[kh]),(kc,bs[kc])])

    key_change("up arrow",    "a", V_A,  0.1, 200)
    key_change("down arrow",  "a", V_A, -0.1, 320)
    key_change("right arrow", "b", V_B,  0.1, 440)
    key_change("left arrow",  "b", V_B, -0.1, 560)

    # === space: fire (broadcast BR_FIRE) ===
    sp = gen(); bs[sp] = mk("event_whenkeypressed", top=True, x=400, y=20,
        fields={"KEY_OPTION": ["space", None]})
    fm = gen(); bs[fm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]}, shadow=True)
    fb = gen(); bs[fb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, fm]})
    bs[fm]["parent"] = fb
    chain([(sp,bs[sp]),(fb,bs[fb])])

    # === when received 발사: glide along curve ===
    fh = gen(); bs[fh] = mk("event_whenbroadcastreceived", top=True, x=400, y=200,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    so = gen(); bs[so] = mk("control_stop",
        fields={"STOP_OPTION": ["other scripts in sprite", None]})
    bs[so]["mutation"] = {"tagName":"mutation","children":[],"hasnext":"true"}

    # init x_g = -6
    sxs = gen(); bs[sxs] = mk("data_setvariableto",
        inputs={"VALUE": num(-6)}, fields={"VARIABLE": ["x걸음", V_XSTEP]})
    sho = gen(); bs[sho] = mk("looks_show")
    # play pop sound (whoosh-ish)
    snm0 = gen(); bs[snm0] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd0 = gen(); bs[snd0] = mk("sound_play", inputs={"SOUND_MENU":[1, snm0]})
    bs[snm0]["parent"] = snd0

    # initial goto: x_g = -6
    sx0, sy0 = B.build_screen_xy("x걸음", V_XSTEP)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(sx0), "Y": slot(sy0)})
    bs[sx0]["parent"] = g_init; bs[sy0]["parent"] = g_init

    # === loop body ===
    cx = gen(); bs[cx] = mk("data_changevariableby",
        inputs={"VALUE": num(0.2)}, fields={"VARIABLE": ["x걸음", V_XSTEP]})

    sx_i, sy_i = B.build_screen_xy("x걸음", V_XSTEP)
    g_iter = gen(); bs[g_iter] = mk("motion_gotoxy",
        inputs={"X": slot(sx_i), "Y": slot(sy_i)})
    bs[sx_i]["parent"] = g_iter; bs[sy_i]["parent"] = g_iter

    # if off-screen → exit
    xp = gen(); bs[xp] = mk("motion_xposition")
    cond_offx = gen(); bs[cond_offx] = mk("operator_gt",
        inputs={"OPERAND1": slot(xp), "OPERAND2": num(240)})
    bs[xp]["parent"] = cond_offx

    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_offy = gen(); bs[cond_offy] = mk("operator_lt",
        inputs={"OPERAND1": slot(yp), "OPERAND2": num(-178)})
    bs[yp]["parent"] = cond_offy

    cond_or = gen(); bs[cond_or] = mk("operator_or",
        inputs={"OPERAND1": [2, cond_offx], "OPERAND2": [2, cond_offy]})
    bs[cond_offx]["parent"] = cond_or
    bs[cond_offy]["parent"] = cond_or

    hide_in = gen(); bs[hide_in] = mk("looks_hide")
    stop_in = gen(); bs[stop_in] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]})
    bs[stop_in]["mutation"] = {"tagName":"mutation","children":[],"hasnext":"false"}
    chain([(hide_in,bs[hide_in]),(stop_in,bs[stop_in])])

    ifb = gen(); bs[ifb] = mk("control_if",
        inputs={"CONDITION":[2, cond_or], "SUBSTACK":[2, hide_in]})
    bs[cond_or]["parent"] = ifb
    bs[hide_in]["parent"] = ifb

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.03)})

    chain([(cx,bs[cx]),(g_iter,bs[g_iter]),(ifb,bs[ifb]),(wt,bs[wt])])

    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(70), "SUBSTACK":[2, cx]})
    bs[cx]["parent"] = rep

    end_hide = gen(); bs[end_hide] = mk("looks_hide")

    chain([(fh,bs[fh]),(so,bs[so]),(sxs,bs[sxs]),(sho,bs[sho]),
           (snd0,bs[snd0]),(g_init,bs[g_init]),(rep,bs[rep]),(end_hide,bs[end_hide])])

    return bs


# ============================================================
# BALLOON sprite (round-based placements via clone index)
# ============================================================
# Round layouts: list of (x_g, y_value) tuples. y_value is the LOGICAL value,
# we convert to screen coords using same transform as curve.
ROUND_LAYOUTS = [
    # Round 1: y = 2^x at x = 0,1,2,3  (a=1, b=2)
    [(0.0, 1.0), (1.0, 2.0), (2.0, 4.0), (3.0, 8.0)],
    # Round 2: y = 0.5^x decay
    [(0.0, 1.0), (1.0, 0.5), (2.0, 0.25), (3.0, 0.125)],
    # Round 3: negative x sampled, b=2
    [(-2.0, 0.25), (-1.0, 0.5), (0.0, 1.0), (1.0, 2.0), (2.0, 4.0)],
    # Round 4: y = 1.5 · 1.8^x (mixed a, b)
    [(-1.0, 0.833), (0.0, 1.5), (1.0, 2.7), (2.0, 4.86)],
    # Round 5: log-mode showcase — points on log-linear line. y values span large range.
    [(-3.0, 0.5), (-1.0, 2.0), (1.0, 8.0), (3.0, 32.0)],
]
MAX_BALLOONS = max(len(r) for r in ROUND_LAYOUTS)

def build_balloon_blocks():
    B = BlockBuilder()
    bs = B.bs

    # === when flag clicked: hide self, init counters ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sc = gen(); bs[sc] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["풍선수", V_BCOUNT]})
    chain([(h,bs[h]),(hi,bs[hi]),(sc,bs[sc])])

    # === when received 새라운드: spawn clones by round-layout ===
    # Strategy: iterate balloon index 1..N, set V_BIDX, create clone, wait.
    # Each clone reads V_BIDX immediately to know its slot (only safe because
    # we wait between spawns).
    bh = gen(); bs[bh] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]})
    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(0.3)})

    spawn_seq = [bh, w1]

    # For each balloon slot, build: set V_BIDX = i; create clone of self; wait
    for i in range(1, MAX_BALLOONS + 1):
        sidx = gen(); bs[sidx] = mk("data_setvariableto",
            inputs={"VALUE": num(i)}, fields={"VARIABLE": ["풍선번호", V_BIDX]})
        cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
            fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
        cclone = gen(); bs[cclone] = mk("control_create_clone_of",
            inputs={"CLONE_OPTION":[1, cmenu]})
        bs[cmenu]["parent"] = cclone
        wclone = gen(); bs[wclone] = mk("control_wait", inputs={"DURATION": num(0.08)})
        spawn_seq.extend([sidx, cclone, wclone])

    pairs = [(bid, bs[bid]) for bid in spawn_seq]
    chain(pairs)

    # === when received 게임시작 → broadcast 새라운드 ===
    sh = gen(); bs[sh] = mk("event_whenbroadcastreceived", top=True, x=20, y=520,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    nbm = gen(); bs[nbm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]}, shadow=True)
    nbb = gen(); bs[nbb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, nbm]})
    bs[nbm]["parent"] = nbb
    chain([(sh,bs[sh]),(nbb,bs[nbb])])

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)

    # increment 풍선수
    inc = gen(); bs[inc] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["풍선수", V_BCOUNT]})

    # === Position clone by (V_ROUND, V_BIDX) ===
    # Build a nested if/else over rounds and indexes. We construct a chain of
    # "if 라운드 = R then if 풍선번호 = I then goto(sx, sy); hide-if-out-of-layout".
    # First: position-set blocks go here. We'll build top-level "set_to_layout".
    #
    # Approach: build one master if/else-if tree using control_if_else chained.
    # For simplicity we build a flat sequence of `if (round==R and idx==I) { gotoxy + show }`
    # plus a default "if idx > layout_count → delete clone".

    # Helper to build goto block for screen coords of (xg, yv)
    def goto_block(xg, yv):
        # screen_x = 40 · xg  (literal)
        sx_const = 40.0 * xg
        # screen_y depends on V_LOG; use blend.
        sy_lin = 30.0 * yv - 120.0   # literal linear
        # log only if yv > 0
        import math
        if yv > 0:
            sy_log = 30.0 * math.log10(yv) - 30.0
        else:
            sy_log = -200  # off-screen
        # Build at-runtime: screen_y = V_LOG · sy_log + (1 - V_LOG) · sy_lin
        rL1 = B.vrep("로그", V_LOG)
        rL2 = B.vrep("로그", V_LOG)
        one_minus = B.op("operator_subtract", 1, rL2)
        lin_part = B.op("operator_multiply", one_minus, sy_lin)
        log_part = B.op("operator_multiply", rL1, sy_log)
        sy = B.op("operator_add", lin_part, log_part)

        g = gen(); bs[g] = mk("motion_gotoxy",
            inputs={"X": num(sx_const), "Y": slot(sy)})
        bs[sy]["parent"] = g
        return g

    # We'll build a single big chain inside the clone-start script:
    # 1) goto (-300, -300)  [off-screen default]
    # 2) for each round R in 1..N:
    #      if 라운드 = R:
    #          if 풍선번호 = 1: goto(...)
    #          if 풍선번호 = 2: goto(...)
    #          ...

    pre_g = gen(); bs[pre_g] = mk("motion_gotoxy", inputs={"X": num(-400), "Y": num(-400)})

    # Build round-blocks list
    round_chain_ids = []
    for R, layout in enumerate(ROUND_LAYOUTS, start=1):
        # build inner chain: for each index, "if 풍선번호 = i then goto"
        inner_seq = []
        for I, (xg, yv) in enumerate(layout, start=1):
            g_blk = goto_block(xg, yv)
            rI = B.vrep("풍선번호", V_BIDX)
            eqI = gen(); bs[eqI] = mk("operator_equals",
                inputs={"OPERAND1": slot(rI), "OPERAND2": num(I)})
            bs[rI]["parent"] = eqI
            ifI = gen(); bs[ifI] = mk("control_if",
                inputs={"CONDITION":[2, eqI], "SUBSTACK":[2, g_blk]})
            bs[eqI]["parent"] = ifI
            bs[g_blk]["parent"] = ifI
            inner_seq.append(ifI)

        # chain inner_seq inside the round
        if inner_seq:
            chain([(bid, bs[bid]) for bid in inner_seq])
            inner_head = inner_seq[0]
        else:
            inner_head = None

        rR = B.vrep("라운드", V_ROUND)
        eqR = gen(); bs[eqR] = mk("operator_equals",
            inputs={"OPERAND1": slot(rR), "OPERAND2": num(R)})
        bs[rR]["parent"] = eqR
        if_R = gen(); bs[if_R] = mk("control_if",
            inputs={"CONDITION":[2, eqR],
                    "SUBSTACK":[2, inner_head] if inner_head else None})
        if not inner_head:
            del bs[if_R]["inputs"]["SUBSTACK"]
        bs[eqR]["parent"] = if_R
        if inner_head:
            bs[inner_head]["parent"] = if_R
        round_chain_ids.append(if_R)

    # If clone x is still -400 (= no round matched our index), delete clone.
    # Simpler: check if 풍선번호 > current round's max count → delete.
    # Cleanest: check x position == -400 → delete.
    xp_clone = gen(); bs[xp_clone] = mk("motion_xposition")
    cond_offscreen = gen(); bs[cond_offscreen] = mk("operator_lt",
        inputs={"OPERAND1": slot(xp_clone), "OPERAND2": num(-300)})
    bs[xp_clone]["parent"] = cond_offscreen

    decb_off = gen(); bs[decb_off] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["풍선수", V_BCOUNT]})
    del_off = gen(); bs[del_off] = mk("control_delete_this_clone")
    chain([(decb_off, bs[decb_off]), (del_off, bs[del_off])])

    if_off = gen(); bs[if_off] = mk("control_if",
        inputs={"CONDITION":[2, cond_offscreen], "SUBSTACK":[2, decb_off]})
    bs[cond_offscreen]["parent"] = if_off
    bs[decb_off]["parent"] = if_off

    # size and color
    rs = gen(); bs[rs] = mk("operator_random",
        inputs={"FROM": num(70), "TO": num(95)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": slot(rs)})
    bs[rs]["parent"] = sz
    # tint based on round
    rR_color = B.vrep("라운드", V_ROUND)
    color_calc = B.op("operator_multiply", rR_color, 40)
    ce = gen(); bs[ce] = mk("looks_seteffectto",
        inputs={"VALUE": slot(color_calc)}, fields={"EFFECT": ["color", None]})
    bs[color_calc]["parent"] = ce
    show = gen(); bs[show] = mk("looks_show")

    # forever: check touching rocket
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["로켓", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc

    incs = gen(); bs[incs] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    sz0 = gen(); bs[sz0] = mk("looks_changesizeby", inputs={"CHANGE": num(-25)})
    sz1 = gen(); bs[sz1] = mk("looks_changesizeby", inputs={"CHANGE": num(-25)})
    decb = gen(); bs[decb] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["풍선수", V_BCOUNT]})

    # if 풍선수 = 0: next round
    rbc = B.vrep("풍선수", V_BCOUNT)
    eq_zero = gen(); bs[eq_zero] = mk("operator_equals",
        inputs={"OPERAND1": slot(rbc), "OPERAND2": num(0)})
    bs[rbc]["parent"] = eq_zero
    incr_round = gen(); bs[incr_round] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
    nbm2 = gen(); bs[nbm2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]}, shadow=True)
    nbb2 = gen(); bs[nbb2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, nbm2]})
    bs[nbm2]["parent"] = nbb2
    chain([(incr_round,bs[incr_round]),(nbb2,bs[nbb2])])
    if_round = gen(); bs[if_round] = mk("control_if",
        inputs={"CONDITION":[2, eq_zero], "SUBSTACK":[2, incr_round]})
    bs[eq_zero]["parent"] = if_round
    bs[incr_round]["parent"] = if_round

    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(incs,bs[incs]),(snd,bs[snd]),(sz0,bs[sz0]),(sz1,bs[sz1]),
           (decb,bs[decb]),(if_round,bs[if_round]),(delc,bs[delc])])

    if_touch = gen(); bs[if_touch] = mk("control_if",
        inputs={"CONDITION":[2, tc], "SUBSTACK":[2, incs]})
    bs[tc]["parent"] = if_touch
    bs[incs]["parent"] = if_touch

    fwait = gen(); bs[fwait] = mk("control_wait", inputs={"DURATION": num(0.03)})
    chain([(if_touch,bs[if_touch]),(fwait,bs[fwait])])

    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, if_touch]})
    bs[if_touch]["parent"] = fv

    # Assemble clone start: ch → inc → pre_g → [round chain] → if_off → rs/sz → ce → show → fv
    head_chain = [ch, inc, pre_g] + round_chain_ids + [if_off, sz, ce, show, fv]
    chain([(bid, bs[bid]) for bid in head_chain])

    return bs


# ============================================================
# CURVE PEN sprite — draws y = a·b^x with current log/linear transform
# ============================================================
def build_curve_blocks():
    B = BlockBuilder()
    bs = B.bs

    # === flag clicked: hide → loop forever redrawing ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hide_blk = gen(); bs[hide_blk] = mk("looks_hide")

    pu0 = gen(); bs[pu0] = mk("pen_penUp")
    clr = gen(); bs[clr] = mk("pen_clear")
    sc  = gen(); bs[sc]  = mk("pen_setPenColorToColor",
        inputs={"COLOR":[1,[9,"#FF4FA3"]]})
    sz_pen = gen(); bs[sz_pen] = mk("pen_setPenSizeTo", inputs={"SIZE": num(3)})

    # init x_g = -6
    spx = gen(); bs[spx] = mk("data_setvariableto",
        inputs={"VALUE": num(-6)}, fields={"VARIABLE": ["예측x", V_PREV_X]})

    # initial goto without pen down
    sx0, sy0 = B.build_screen_xy("예측x", V_PREV_X)
    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": slot(sx0), "Y": slot(sy0)})
    bs[sx0]["parent"] = g0; bs[sy0]["parent"] = g0

    pd = gen(); bs[pd] = mk("pen_penDown")

    # repeat 60 → step 0.2 from -6 to +6
    cx = gen(); bs[cx] = mk("data_changevariableby",
        inputs={"VALUE": num(0.2)}, fields={"VARIABLE": ["예측x", V_PREV_X]})

    sx_i, sy_i = B.build_screen_xy("예측x", V_PREV_X)
    g_iter = gen(); bs[g_iter] = mk("motion_gotoxy",
        inputs={"X": slot(sx_i), "Y": slot(sy_i)})
    bs[sx_i]["parent"] = g_iter; bs[sy_i]["parent"] = g_iter

    chain([(cx, bs[cx]), (g_iter, bs[g_iter])])
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(60), "SUBSTACK":[2, cx]})
    bs[cx]["parent"] = rep

    pu1 = gen(); bs[pu1] = mk("pen_penUp")
    wt  = gen(); bs[wt]  = mk("control_wait", inputs={"DURATION": num(0.08)})

    chain([(pu0,bs[pu0]),(clr,bs[clr]),(sc,bs[sc]),(sz_pen,bs[sz_pen]),
           (spx,bs[spx]),(g0,bs[g0]),(pd,bs[pd]),(rep,bs[rep]),(pu1,bs[pu1]),(wt,bs[wt])])

    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, pu0]})
    bs[pu0]["parent"] = fv

    chain([(h, bs[h]), (hide_blk, bs[hide_blk]), (fv, bs[fv])])

    # === 2nd script: equation builder forever loop ===
    def rounded(name, vid, decimals):
        f = 10 ** decimals
        rv = B.vrep(name, vid)
        m1 = B.op("operator_multiply", rv, f)
        a1 = B.op("operator_add", m1, 0.5)
        fl = gen(); bs[fl] = mk("operator_mathop",
            inputs={"NUM": slot(a1)}, fields={"OPERATOR": ["floor", None]})
        bs[a1]["parent"] = fl
        d1 = B.op("operator_divide", fl, f)
        return d1

    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    ar = rounded("a", V_A, 1)
    br = rounded("b", V_B, 1)

    j1 = gen(); bs[j1] = mk("operator_join",
        inputs={"STRING1": text_lit("y = "), "STRING2": slot(ar, sk=10, sv="")})
    bs[ar]["parent"] = j1
    j2 = gen(); bs[j2] = mk("operator_join",
        inputs={"STRING1": slot(j1, sk=10, sv=""), "STRING2": text_lit(" · ")})
    bs[j1]["parent"] = j2
    j3 = gen(); bs[j3] = mk("operator_join",
        inputs={"STRING1": slot(j2, sk=10, sv=""), "STRING2": slot(br, sk=10, sv="")})
    bs[j2]["parent"] = j3
    bs[br]["parent"] = j3
    j4 = gen(); bs[j4] = mk("operator_join",
        inputs={"STRING1": slot(j3, sk=10, sv=""), "STRING2": text_lit("^x")})
    bs[j3]["parent"] = j4
    set_eq = gen(); bs[set_eq] = mk("data_setvariableto",
        inputs={"VALUE": slot(j4, sk=10, sv="")},
        fields={"VARIABLE": ["수식", V_EQ]})
    bs[j4]["parent"] = set_eq

    wt2 = gen(); bs[wt2] = mk("control_wait", inputs={"DURATION": num(0.1)})
    chain([(set_eq, bs[set_eq]), (wt2, bs[wt2])])
    fv2 = gen(); bs[fv2] = mk("control_forever", inputs={"SUBSTACK":[2, set_eq]})
    bs[set_eq]["parent"] = fv2

    chain([(h2, bs[h2]), (fv2, bs[fv2])])
    return bs


# ============================================================
# LOG-TOGGLE button sprite
# ============================================================
def build_toggle_blocks():
    bs = {}

    # === when flag clicked: position top-right, show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(165), "Y": num(155)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(sh,bs[sh])])

    # === when this sprite clicked: toggle V_LOG, switch backdrop, redraw ===
    ch = gen(); bs[ch] = mk("event_whenthisspriteclicked", top=True, x=300, y=20)
    # V_LOG = 1 - V_LOG
    rL = gen(); bs[rL] = mk("data_variable", fields={"VARIABLE": ["로그", V_LOG]})
    one_minus = gen(); bs[one_minus] = mk("operator_subtract",
        inputs={"NUM1": num(1), "NUM2": slot(rL)})
    bs[rL]["parent"] = one_minus
    set_log = gen(); bs[set_log] = mk("data_setvariableto",
        inputs={"VALUE": slot(one_minus)}, fields={"VARIABLE": ["로그", V_LOG]})
    bs[one_minus]["parent"] = set_log

    # if V_LOG = 1 then switch backdrop "log" else "linear"
    rL2 = gen(); bs[rL2] = mk("data_variable", fields={"VARIABLE": ["로그", V_LOG]})
    eq1 = gen(); bs[eq1] = mk("operator_equals",
        inputs={"OPERAND1": slot(rL2), "OPERAND2": num(1)})
    bs[rL2]["parent"] = eq1

    bd_log_m = gen(); bs[bd_log_m] = mk("looks_backdrops",
        fields={"BACKDROP": ["log", None]}, shadow=True)
    sw_log = gen(); bs[sw_log] = mk("looks_switchbackdropto",
        inputs={"BACKDROP":[1, bd_log_m]})
    bs[bd_log_m]["parent"] = sw_log

    bd_lin_m = gen(); bs[bd_lin_m] = mk("looks_backdrops",
        fields={"BACKDROP": ["linear", None]}, shadow=True)
    sw_lin = gen(); bs[sw_lin] = mk("looks_switchbackdropto",
        inputs={"BACKDROP":[1, bd_lin_m]})
    bs[bd_lin_m]["parent"] = sw_lin

    if_else = gen(); bs[if_else] = mk("control_if_else",
        inputs={"CONDITION":[2, eq1],
                "SUBSTACK":[2, sw_log],
                "SUBSTACK2":[2, sw_lin]})
    bs[eq1]["parent"] = if_else
    bs[sw_log]["parent"] = if_else
    bs[sw_lin]["parent"] = if_else

    # play pop (toggle feedback)
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd

    chain([(ch,bs[ch]),(set_log,bs[set_log]),(if_else,bs[if_else]),(snd,bs[snd])])
    return bs


# ============================================================
# Assemble project
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # save backgrounds
    bg_lin_md5 = md5_bytes(BG_LINEAR_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_lin_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_LINEAR_SVG)
    bg_log_md5 = md5_bytes(BG_LOG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_log_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_LOG_SVG)

    def import_svg(name):
        src = f"{ASSETS}/{name}.svg"
        with open(src, "rb") as f: data = f.read()
        m = md5_bytes(data)
        with open(f"{WORK}/{m}.svg", "wb") as f: f.write(data)
        return m
    rocket_md5  = import_svg("rocket")
    balloon_md5 = import_svg("balloon")

    pop_src = f"{ASSETS}/pop.wav"
    with open(pop_src, "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    tiny_md5 = md5_bytes(TINY_SVG.encode("utf-8"))
    with open(f"{WORK}/{tiny_md5}.svg", "w", encoding="utf-8") as f:
        f.write(TINY_SVG)

    toggle_md5 = md5_bytes(TOGGLE_SVG.encode("utf-8"))
    with open(f"{WORK}/{toggle_md5}.svg", "w", encoding="utf-8") as f:
        f.write(TOGGLE_SVG)

    rocket_blocks  = build_rocket_blocks()
    balloon_blocks = build_balloon_blocks()
    curve_blocks   = build_curve_blocks()
    toggle_blocks  = build_toggle_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_A:      ["a", 2.0],
            V_B:      ["b", 1.5],
            V_LOG:    ["로그", 0],
            V_SCORE:  ["점수", 0],
            V_XSTEP:  ["x걸음", 0],
            V_BCOUNT: ["풍선수", 0],
            V_ROUND:  ["라운드", 1],
            V_EQ:     ["수식", "y = 2.0 · 1.5^x"],
        },
        "lists": {}, "broadcasts": {
            BR_NEW_ROUND: "새라운드",
            BR_START: "게임시작",
            BR_DRAW_CURVE: "곡선다시",
            BR_TOGGLE_LOG: "로그토글",
            BR_FIRE: "발사",
        },
        "blocks": {}, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "linear", "dataFormat": "svg",
                "assetId": bg_lin_md5, "md5ext": f"{bg_lin_md5}.svg",
                "rotationCenterX": 240, "rotationCenterY": 180
            },
            {
                "name": "log", "dataFormat": "svg",
                "assetId": bg_log_md5, "md5ext": f"{bg_log_md5}.svg",
                "rotationCenterX": 240, "rotationCenterY": 180
            },
        ],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    rocket = {
        "isStage": False, "name": "로켓",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": rocket_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "rocket", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": rocket_md5, "md5ext": f"{rocket_md5}.svg",
            "rotationCenterX": 18, "rotationCenterY": 18
        }],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": -240, "y": -120, "size": 110, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    balloon = {
        "isStage": False, "name": "풍선",
        "variables": {V_BIDX: ["풍선번호", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": balloon_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "balloon", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": balloon_md5, "md5ext": f"{balloon_md5}.svg",
            "rotationCenterX": 18, "rotationCenterY": 18
        }],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 100, "y": 0, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    curve = {
        "isStage": False, "name": "곡선",
        "variables": {V_PREV_X: ["예측x", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": curve_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "dot", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": tiny_md5, "md5ext": f"{tiny_md5}.svg",
            "rotationCenterX": 4, "rotationCenterY": 4
        }],
        "sounds": [],
        "volume": 0, "layerOrder": 1, "visible": False,
        "x": -200, "y": -120, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    toggle = {
        "isStage": False, "name": "로그버튼",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": toggle_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "toggle", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": toggle_md5, "md5ext": f"{toggle_md5}.svg",
            "rotationCenterX": 60, "rotationCenterY": 18
        }],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 4, "visible": True,
        "x": 165, "y": 155, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_EQ, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "수식"}, "spriteName": None,
         "value": "y = 2.0 · 1.5^x", "width": 0, "height": 0, "x": 130, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_A, "mode": "slider", "opcode": "data_variable",
         "params": {"VARIABLE": "a"}, "spriteName": None,
         "value": 2.0, "width": 0, "height": 0, "x": 5, "y": 70,
         "visible": True, "sliderMin": 0.5, "sliderMax": 5.0, "isDiscrete": False},
        {"id": V_B, "mode": "slider", "opcode": "data_variable",
         "params": {"VARIABLE": "b"}, "spriteName": None,
         "value": 1.5, "width": 0, "height": 0, "x": 5, "y": 105,
         "visible": True, "sliderMin": 0.3, "sliderMax": 3.0, "isDiscrete": False},
        {"id": V_LOG, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "로그"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 140,
         "visible": True, "sliderMin": 0, "sliderMax": 1, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, rocket, balloon, curve, toggle],
        "monitors": monitors,
        "extensions": ["pen"],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "exponential-shooter-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # validate parse
    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"✓ wrote {OUTPUT} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
