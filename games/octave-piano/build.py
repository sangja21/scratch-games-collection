#!/usr/bin/env python3
"""Octave Piano — 옥타브 짝짓기 게임.

매 라운드 두 흰건반이 강조 표시되고, 플레이어는 두 음이 한 옥타브 차이인지
(O / X 키로) 판단한다. HUD 는 두 주파수의 비율 V_RATIO = f2/f1 과
로그값 V_LOG2 = log2(f2/f1) 를 실시간 표시. log₂ 가 정수일 때만 옥타브 관계.
밑 변환 공식 log_2(x) = log10(x) / log10(2) 가 게임 안에 들어있는 학습 포인트.

빌드: python3 build.py  →  옥타브_피아노.sb3
"""
import json, os, wave, zipfile, shutil, hashlib, struct, math

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "옥타브_피아노.sb3")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 14 white keys, C4 ~ B5
KEY_NAMES = ["C4","D4","E4","F4","G4","A4","B4",
             "C5","D5","E5","F5","G5","A5","B5"]
# 12-TET equal-temperament frequencies (Hz)
KEY_FREQS = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88,
             523.25, 587.33, 659.25, 698.46, 783.99, 880.00, 987.77]
# Semitone offset from C4 for each white key (k=1..14 → index 0..13)
# C->D=2, D->E=2, E->F=1, F->G=2, G->A=2, A->B=2, B->C=1
KEY_SEMITONES = [0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17, 19, 21, 23]

SAMPLE_RATE = 22050
GAME_TIME   = 60  # seconds

# Key geometry on stage (Scratch coordinates)
# Background draws 14 keys with width 30px each, starting at SVG x=30.
# Highlight star sits at the *top of the key*, slightly above the keybed.
KEY_WIDTH_PX     = 30
KEY_LEFT_SVG     = 30      # SVG x of left edge of key 1
KEY_TOP_SVG      = 170     # SVG y of top of key
# Scratch x of *center* of key k (1..14): -210 + (k-1)*30 + 15 = -195 + (k-1)*30
def key_x(k):  return -195 + (k - 1) * KEY_WIDTH_PX
def key_top_y(): return 180 - KEY_TOP_SVG   # = 10 (just above the keybed)

# ---------------------------------------------------------------------------
# SVG assets
# ---------------------------------------------------------------------------

def build_bg_svg():
    """Background: title bar (HUD area) + 14 white keys + instruction text."""
    parts = []
    parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" '
        'viewBox="0 0 480 360">'
    )
    parts.append("""
  <defs>
    <linearGradient id="hud" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1A237E"/>
      <stop offset="100%" stop-color="#283593"/>
    </linearGradient>
    <linearGradient id="key" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FAFAFA"/>
      <stop offset="100%" stop-color="#E0E0E0"/>
    </linearGradient>
    <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#5D4037"/>
      <stop offset="100%" stop-color="#3E2723"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="#0B1020"/>
  <rect x="0" y="0" width="480" height="120" fill="url(#hud)"/>
  <line x1="0" y1="120" x2="480" y2="120" stroke="#5C6BC0" stroke-width="1"/>
""")
    # Title text
    parts.append("""
  <text x="14" y="22" fill="#FFE082"
        font-family="Arial, Helvetica, sans-serif"
        font-size="13" font-weight="bold">옥타브 피아노 — 같은 음의 다른 옥타브를 찾아라</text>
  <text x="14" y="42" fill="#C5CAE9"
        font-family="Arial, Helvetica, sans-serif"
        font-size="11">두 ★ 건반: 한 옥타브 차이면 O, 아니면 X</text>
  <text x="14" y="60" fill="#A5D6A7"
        font-family="Arial, Helvetica, sans-serif"
        font-size="11">옥타브 = 주파수 2배 = log₂(f₂/f₁) 가 정수</text>
""")
    # Keybed floor
    parts.append('<rect x="20" y="170" width="440" height="160" fill="url(#floor)"/>')
    # 14 white keys
    for i in range(14):
        x = KEY_LEFT_SVG + i * KEY_WIDTH_PX
        parts.append(
            f'<rect x="{x}" y="175" width="{KEY_WIDTH_PX - 2}" height="145" '
            f'rx="3" fill="url(#key)" stroke="#212121" stroke-width="0.8"/>'
        )
        # key label (note name)
        name = KEY_NAMES[i]
        parts.append(
            f'<text x="{x + KEY_WIDTH_PX/2}" y="310" text-anchor="middle" '
            f'fill="#212121" font-family="Arial, Helvetica, sans-serif" '
            f'font-size="9">{name}</text>'
        )
    # Controls hint at bottom
    parts.append("""
  <text x="240" y="345" text-anchor="middle"
        fill="#FFAB91" font-family="Arial, Helvetica, sans-serif"
        font-size="11">[O] 옥타브 맞음    [X] 옥타브 아님</text>
""")
    parts.append("</svg>")
    return "".join(parts)

BG_SVG = build_bg_svg()

# Highlight star — yellow glowing star marker placed above a key
HIGHLIGHT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <defs>
    <radialGradient id="s" cx="0.5" cy="0.5" r="0.6">
      <stop offset="0%"   stop-color="#FFF59D"/>
      <stop offset="60%"  stop-color="#FFEB3B"/>
      <stop offset="100%" stop-color="#F9A825"/>
    </radialGradient>
  </defs>
  <circle cx="20" cy="20" r="18" fill="#FFEB3B" opacity="0.18"/>
  <polygon points="20,3 24,15 37,15 27,23 31,36 20,28 9,36 13,23 3,15 16,15"
           fill="url(#s)" stroke="#E65100" stroke-width="1.2"/>
</svg>"""

# Result icons — ✓ correct / ✗ wrong
CORRECT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <circle cx="60" cy="60" r="48" fill="#43A047" opacity="0.85" stroke="#1B5E20" stroke-width="4"/>
  <path d="M 32 62 L 52 82 L 88 38" stroke="#FFFFFF" stroke-width="9" fill="none"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

WRONG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <circle cx="60" cy="60" r="48" fill="#E53935" opacity="0.85" stroke="#B71C1C" stroke-width="4"/>
  <line x1="36" y1="36" x2="84" y2="84" stroke="#FFFFFF" stroke-width="9" stroke-linecap="round"/>
  <line x1="84" y1="36" x2="36" y2="84" stroke="#FFFFFF" stroke-width="9" stroke-linecap="round"/>
</svg>"""

# Game-over banner
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.9"
        stroke="#FFB300" stroke-width="4"/>
  <text x="180" y="60" text-anchor="middle"
        fill="#FFB300" font-family="Arial, Helvetica, sans-serif"
        font-size="36" font-weight="bold">게임 종료</text>
  <text x="180" y="92" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">점수 모니터 확인</text>
  <text x="180" y="120" text-anchor="middle"
        fill="#90CAF9" font-family="Arial, Helvetica, sans-serif"
        font-size="13">▶ 깃발을 다시 누르면 재시작</text>
  <text x="180" y="142" text-anchor="middle"
        fill="#A5D6A7" font-family="Arial, Helvetica, sans-serif"
        font-size="11">옥타브 = 주파수 ×2 = log₂(f₂/f₁) 가 정수</text>
</svg>"""

# ---------------------------------------------------------------------------
# Audio synthesis (sine waves; Scratch will adjust pitch via PITCH effect)
# ---------------------------------------------------------------------------

def write_wav(path, samples_i16, rate=SAMPLE_RATE):
    """Write 16-bit mono PCM WAV."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples_i16))

def gen_piano_note(freq, dur=0.55, harmonics=((1, 0.65), (2, 0.25), (3, 0.10))):
    """Synthesize a soft piano-ish note: fundamental + harmonics with exp decay."""
    n = int(dur * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 3.5)  # decay
        # short attack so it doesn't click
        if t < 0.005:
            env *= t / 0.005
        s = 0.0
        for mult, amp in harmonics:
            s += amp * math.sin(2 * math.pi * freq * mult * t)
        # gentle vibrato
        s *= 1 + 0.02 * math.sin(2 * math.pi * 5 * t)
        out.append(int(max(-1, min(1, s * env)) * 24000))
    return out

def gen_correct_chord():
    """A short bright two-tone chord."""
    dur = 0.35
    n = int(dur * SAMPLE_RATE)
    out = []
    # Major third up from C5: C5 + E5
    freqs = [523.25, 659.25]
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 5.0)
        if t < 0.005:
            env *= t / 0.005
        s = sum(math.sin(2*math.pi*f*t) for f in freqs) / len(freqs)
        out.append(int(max(-1, min(1, s * env)) * 22000))
    return out

def gen_wrong_buzz():
    """A short low buzz for wrong answers."""
    dur = 0.30
    n = int(dur * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 6.0)
        if t < 0.005:
            env *= t / 0.005
        # detuned low square-ish tone
        s1 = math.sin(2*math.pi*150*t)
        s1 = 1.0 if s1 > 0 else -1.0
        s2 = math.sin(2*math.pi*155*t)
        s2 = 1.0 if s2 > 0 else -1.0
        s = (s1 + s2) * 0.35
        out.append(int(max(-1, min(1, s * env)) * 22000))
    return out

# ---------------------------------------------------------------------------
# Helpers — same shape as sister build.py files
# ---------------------------------------------------------------------------
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n):      return [1, [4, str(n)]]
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
        bs[bid] = mk(opcode, inputs={"OPERAND1": [2, a], "OPERAND2": [2, b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid
        return bid
    def mathop(name, a):
        bid = gen()
        ins = {"NUM": slot(a)} if isinstance(a, str) else {"NUM": num(a)}
        bs[bid] = mk("operator_mathop", inputs=ins,
                     fields={"OPERATOR": [name, None]})
        if isinstance(a, str): bs[a]["parent"] = bid
        return bid
    def litem(name, vid, idx):
        """data_itemoflist — get item INDEX of list."""
        bid = gen()
        if isinstance(idx, str):
            ins = {"INDEX": slot(idx)}
        else:
            ins = {"INDEX": num(idx)}
        bs[bid] = mk("data_itemoflist", inputs=ins,
                     fields={"LIST": [name, vid]})
        if isinstance(idx, str): bs[idx]["parent"] = bid
        return bid
    return vrep, op, cmp_op, bool_op, mathop, litem

# ---------------------------------------------------------------------------
# Variable + broadcast IDs
# ---------------------------------------------------------------------------
V_SCORE    = "varScore001"
V_TIME     = "varTime002"
V_STATE    = "varState003"
V_K1       = "varK1_004"
V_K2       = "varK2_005"
V_F1       = "varF1_006"
V_F2       = "varF2_007"
V_RATIO    = "varRatio008"
V_LOG2     = "varLog2_009"
V_IS_OCT   = "varIsOct010"
V_FEEDBACK = "varFeedback011"
V_ROUND    = "varRound012"
V_SIDE     = "varSide013"     # used by Highlight clones: 1 = left, 2 = right
V_HALF     = "varHalf014"     # scratch: halfsteps for current note
V_OFFSET   = "varOffset015"   # used to randomize non-octave pair

L_FREQ_ID = "listFreq001"
L_NAME_ID = "listName002"

BR_START          = "brStart001"
BR_NEW_ROUND      = "brNewRound002"
BR_PLAY_LOW       = "brPlayLow003"
BR_PLAY_HIGH      = "brPlayHigh004"
BR_ANSWER_OCT     = "brAnsOct005"
BR_ANSWER_NOT     = "brAnsNot006"
BR_SHOW_CORRECT   = "brShowCorrect007"
BR_SHOW_WRONG     = "brShowWrong008"
BR_GAMEOVER       = "brGameOver009"

# ---------------------------------------------------------------------------
# STAGE blocks — init, timer, round logic, answer judgement, sound playback
# ---------------------------------------------------------------------------
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop, litem = make_helpers(bs)

    # ---- when flag clicked ----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)

    setups = []
    def setvar(name, vid, val):
        bid = gen()
        bs[bid] = mk("data_setvariableto",
                     inputs={"VALUE": num(val)},
                     fields={"VARIABLE": [name, vid]})
        setups.append((bid, bs[bid]))
        return bid

    setvar("점수",       V_SCORE,    0)
    setvar("시간",       V_TIME,     GAME_TIME)
    setvar("상태",       V_STATE,    1)
    setvar("K1",         V_K1,       1)
    setvar("K2",         V_K2,       8)
    setvar("F1",         V_F1,       0)
    setvar("F2",         V_F2,       0)
    setvar("비율",       V_RATIO,    0)
    setvar("log2",       V_LOG2,     0)
    setvar("정답",       V_IS_OCT,   0)
    setvar("결과",       V_FEEDBACK, -1)
    setvar("라운드",     V_ROUND,    0)
    setvar("Side",      V_SIDE,     0)
    setvar("Half",      V_HALF,     0)
    setvar("Offset",    V_OFFSET,   0)

    # delete & populate L_FREQ
    del_freq = gen(); bs[del_freq] = mk("data_deletealloflist",
        fields={"LIST": ["주파수", L_FREQ_ID]})
    setups.append((del_freq, bs[del_freq]))
    for f in KEY_FREQS:
        addf = gen(); bs[addf] = mk("data_addtolist",
            inputs={"ITEM": num(f)},
            fields={"LIST": ["주파수", L_FREQ_ID]})
        setups.append((addf, bs[addf]))

    # delete & populate L_NAME
    del_name = gen(); bs[del_name] = mk("data_deletealloflist",
        fields={"LIST": ["음이름", L_NAME_ID]})
    setups.append((del_name, bs[del_name]))
    for name in KEY_NAMES:
        addn = gen(); bs[addn] = mk("data_addtolist",
            inputs={"ITEM": text_lit(name)},
            fields={"LIST": ["음이름", L_NAME_ID]})
        setups.append((addn, bs[addn]))

    # broadcast start
    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h, bs[h])] + setups + [(bc_start, bs[bc_start])])

    # ---- when received 시작 → kick off first round + timer ----
    h_start = gen(); bs[h_start] = mk("event_whenbroadcastreceived",
        top=True, x=20, y=300,
        fields={"BROADCAST_OPTION": ["시작", BR_START]})

    bm_nr0 = gen(); bs[bm_nr0] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]}, shadow=True)
    bc_nr0 = gen(); bs[bc_nr0] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_nr0]})
    bs[bm_nr0]["parent"] = bc_nr0

    chain([(h_start, bs[h_start]), (bc_nr0, bs[bc_nr0])])

    # ---- timer loop (separate top script triggered by 시작) ----
    h_tm = gen(); bs[h_tm] = mk("event_whenbroadcastreceived",
        top=True, x=320, y=300,
        fields={"BROADCAST_OPTION": ["시작", BR_START]})

    t_var = vrep("시간", V_TIME)
    cond_t0 = cmp_op("operator_equals", t_var, 0)

    wt1 = gen(); bs[wt1] = mk("control_wait", inputs={"DURATION": num(1)})
    dec_t = gen(); bs[dec_t] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["시간", V_TIME]})
    chain([(wt1, bs[wt1]), (dec_t, bs[dec_t])])

    rep_t = gen(); bs[rep_t] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_t0], "SUBSTACK": [2, wt1]})
    bs[cond_t0]["parent"] = rep_t
    bs[wt1]["parent"] = rep_t

    # after timer: set state=0, broadcast 게임종료
    set_off = gen(); bs[set_off] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["상태", V_STATE]})
    bm_go = gen(); bs[bm_go] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]}, shadow=True)
    bc_go = gen(); bs[bc_go] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_go]})
    bs[bm_go]["parent"] = bc_go

    chain([(h_tm, bs[h_tm]), (rep_t, bs[rep_t]),
           (set_off, bs[set_off]), (bc_go, bs[bc_go])])

    # ---- when received 새라운드: pick keys, compute HUD, play notes ----
    h_nr = gen(); bs[h_nr] = mk("event_whenbroadcastreceived",
        top=True, x=20, y=600,
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]})

    # guard: only run if 상태 = 1
    state_v_nr = vrep("상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v_nr, 1)

    # increment round
    inc_r = gen(); bs[inc_r] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})

    # pick K1: random 1..7
    rk1 = op("operator_random", 1, 7, key1="FROM", key2="TO")
    set_k1 = gen(); bs[set_k1] = mk("data_setvariableto",
        inputs={"VALUE": slot(rk1)}, fields={"VARIABLE": ["K1", V_K1]})
    bs[rk1]["parent"] = set_k1

    # decide if this round will be an octave: random 1..2 = 1 → octave
    coin = op("operator_random", 1, 2, key1="FROM", key2="TO")
    cond_coin = cmp_op("operator_equals", coin, 1)

    # if octave: K2 = K1 + 7
    k1_v_a = vrep("K1", V_K1)
    sum_k1_7 = op("operator_add", k1_v_a, 7)
    set_k2_oct = gen(); bs[set_k2_oct] = mk("data_setvariableto",
        inputs={"VALUE": slot(sum_k1_7)}, fields={"VARIABLE": ["K2", V_K2]})
    bs[sum_k1_7]["parent"] = set_k2_oct

    # else: K2 = K1 + offset, offset random in {1..6, 8..(14-K1)}.
    # We use: K2 = K1 + (random 1..6) at first; if K2 == K1 + 7 (won't happen
    # since random is 1..6); but we want some pairs > 7 too. Strategy:
    #   pick Offset in random 1..7. If Offset == 7, replace with 8.
    #   Then K2 = min(K1 + Offset, 14). If K2 == K1 + 7, bump up by 1.
    # This produces a healthy spread of non-octave intervals 1..13 except 7.
    rand_off = op("operator_random", 1, 8, key1="FROM", key2="TO")
    set_off_var = gen(); bs[set_off_var] = mk("data_setvariableto",
        inputs={"VALUE": slot(rand_off)},
        fields={"VARIABLE": ["Offset", V_OFFSET]})
    bs[rand_off]["parent"] = set_off_var

    # if Offset == 7 → Offset = 8 (avoid octave by accident)
    off_v_a = vrep("Offset", V_OFFSET)
    cond_off7 = cmp_op("operator_equals", off_v_a, 7)
    set_off_8 = gen(); bs[set_off_8] = mk("data_setvariableto",
        inputs={"VALUE": num(8)}, fields={"VARIABLE": ["Offset", V_OFFSET]})
    if_off7 = gen(); bs[if_off7] = mk("control_if",
        inputs={"CONDITION": [2, cond_off7], "SUBSTACK": [2, set_off_8]})
    bs[cond_off7]["parent"] = if_off7
    bs[set_off_8]["parent"] = if_off7

    # K2 = K1 + Offset
    k1_v_b = vrep("K1", V_K1)
    off_v_b = vrep("Offset", V_OFFSET)
    sum_k1_off = op("operator_add", k1_v_b, off_v_b)
    set_k2_non = gen(); bs[set_k2_non] = mk("data_setvariableto",
        inputs={"VALUE": slot(sum_k1_off)}, fields={"VARIABLE": ["K2", V_K2]})
    bs[sum_k1_off]["parent"] = set_k2_non

    # clamp K2 to 14
    k2_v_c = vrep("K2", V_K2)
    cond_k2_big = cmp_op("operator_gt", k2_v_c, 14)
    set_k2_14 = gen(); bs[set_k2_14] = mk("data_setvariableto",
        inputs={"VALUE": num(14)}, fields={"VARIABLE": ["K2", V_K2]})
    if_clamp = gen(); bs[if_clamp] = mk("control_if",
        inputs={"CONDITION": [2, cond_k2_big], "SUBSTACK": [2, set_k2_14]})
    bs[cond_k2_big]["parent"] = if_clamp
    bs[set_k2_14]["parent"] = if_clamp

    # Compose else-branch body (non-octave path)
    chain([(set_off_var, bs[set_off_var]),
           (if_off7,     bs[if_off7]),
           (set_k2_non,  bs[set_k2_non]),
           (if_clamp,    bs[if_clamp])])

    # if/else: K1+7 oct vs non-oct
    if_oct = gen(); bs[if_oct] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_coin],
                "SUBSTACK":  [2, set_k2_oct],
                "SUBSTACK2": [2, set_off_var]})
    bs[cond_coin]["parent"] = if_oct
    bs[set_k2_oct]["parent"] = if_oct
    bs[set_off_var]["parent"] = if_oct

    # set F1 = item K1 of L_FREQ
    k1_v_f = vrep("K1", V_K1)
    f1_item = litem("주파수", L_FREQ_ID, k1_v_f)
    set_f1 = gen(); bs[set_f1] = mk("data_setvariableto",
        inputs={"VALUE": slot(f1_item)}, fields={"VARIABLE": ["F1", V_F1]})
    bs[f1_item]["parent"] = set_f1

    # set F2 = item K2 of L_FREQ
    k2_v_f = vrep("K2", V_K2)
    f2_item = litem("주파수", L_FREQ_ID, k2_v_f)
    set_f2 = gen(); bs[set_f2] = mk("data_setvariableto",
        inputs={"VALUE": slot(f2_item)}, fields={"VARIABLE": ["F2", V_F2]})
    bs[f2_item]["parent"] = set_f2

    # ratio = round((F2 / F1) * 100) / 100
    f2_v_r = vrep("F2", V_F2)
    f1_v_r = vrep("F1", V_F1)
    div_r = op("operator_divide", f2_v_r, f1_v_r)
    mul_r = op("operator_multiply", div_r, 100)
    rnd_r = mathop("floor", op_helper := None) if False else None  # placeholder
    # use operator_round
    round_r = gen(); bs[round_r] = mk("operator_round",
        inputs={"NUM": slot(mul_r)})
    bs[mul_r]["parent"] = round_r
    div_back = op("operator_divide", round_r, 100)
    set_ratio = gen(); bs[set_ratio] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_back)}, fields={"VARIABLE": ["비율", V_RATIO]})
    bs[div_back]["parent"] = set_ratio

    # log2 = round((log(F2/F1) / log(2)) * 100) / 100   (change-of-base)
    f2_v_l = vrep("F2", V_F2)
    f1_v_l = vrep("F1", V_F1)
    div_l = op("operator_divide", f2_v_l, f1_v_l)
    log_ratio = mathop("log", div_l)        # log10(F2/F1)
    log_2 = mathop("log", 2)                # log10(2)  (Scratch log = base 10)
    div_logs = op("operator_divide", log_ratio, log_2)
    mul_logs = op("operator_multiply", div_logs, 100)
    round_logs = gen(); bs[round_logs] = mk("operator_round",
        inputs={"NUM": slot(mul_logs)})
    bs[mul_logs]["parent"] = round_logs
    div_back_l = op("operator_divide", round_logs, 100)
    set_log2 = gen(); bs[set_log2] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_back_l)}, fields={"VARIABLE": ["log2", V_LOG2]})
    bs[div_back_l]["parent"] = set_log2

    # is_oct = (K2 - K1 == 7) ? 1 : 0
    k2_v_o = vrep("K2", V_K2)
    k1_v_o = vrep("K1", V_K1)
    diff_k = op("operator_subtract", k2_v_o, k1_v_o)
    cond_diff7 = cmp_op("operator_equals", diff_k, 7)
    set_oct_1 = gen(); bs[set_oct_1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["정답", V_IS_OCT]})
    set_oct_0 = gen(); bs[set_oct_0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["정답", V_IS_OCT]})
    if_oct_set = gen(); bs[if_oct_set] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_diff7],
                "SUBSTACK":  [2, set_oct_1],
                "SUBSTACK2": [2, set_oct_0]})
    bs[cond_diff7]["parent"] = if_oct_set
    bs[set_oct_1]["parent"] = if_oct_set
    bs[set_oct_0]["parent"] = if_oct_set

    # reset feedback
    set_fb = gen(); bs[set_fb] = mk("data_setvariableto",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["결과", V_FEEDBACK]})

    # wait 0.2s for Highlight clones to spawn, then play LOW note
    wait_a = gen(); bs[wait_a] = mk("control_wait", inputs={"DURATION": num(0.2)})
    bm_low = gen(); bs[bm_low] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["저음재생", BR_PLAY_LOW]}, shadow=True)
    bc_low = gen(); bs[bc_low] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_low]})
    bs[bm_low]["parent"] = bc_low

    wait_b = gen(); bs[wait_b] = mk("control_wait", inputs={"DURATION": num(0.45)})
    bm_high = gen(); bs[bm_high] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["고음재생", BR_PLAY_HIGH]}, shadow=True)
    bc_high = gen(); bs[bc_high] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_high]})
    bs[bm_high]["parent"] = bc_high

    # Assemble the if-guard body
    body_seq = [
        (inc_r,        bs[inc_r]),
        (set_k1,       bs[set_k1]),
        (if_oct,       bs[if_oct]),
        (set_f1,       bs[set_f1]),
        (set_f2,       bs[set_f2]),
        (set_ratio,    bs[set_ratio]),
        (set_log2,     bs[set_log2]),
        (if_oct_set,   bs[if_oct_set]),
        (set_fb,       bs[set_fb]),
        (wait_a,       bs[wait_a]),
        (bc_low,       bs[bc_low]),
        (wait_b,       bs[wait_b]),
        (bc_high,      bs[bc_high]),
    ]
    chain(body_seq)

    if_play = gen(); bs[if_play] = mk("control_if",
        inputs={"CONDITION": [2, cond_play], "SUBSTACK": [2, inc_r]})
    bs[cond_play]["parent"] = if_play
    bs[inc_r]["parent"] = if_play

    chain([(h_nr, bs[h_nr]), (if_play, bs[if_play])])

    # ---- key 'o' pressed → BR_ANSWER_OCT (if playing) ----
    h_o = gen(); bs[h_o] = mk("event_whenkeypressed",
        top=True, x=320, y=600,
        fields={"KEY_OPTION": ["o", None]})
    state_v_o = vrep("상태", V_STATE)
    cond_play_o = cmp_op("operator_equals", state_v_o, 1)
    bm_ao = gen(); bs[bm_ao] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["응답옥타브", BR_ANSWER_OCT]}, shadow=True)
    bc_ao = gen(); bs[bc_ao] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ao]})
    bs[bm_ao]["parent"] = bc_ao
    if_o = gen(); bs[if_o] = mk("control_if",
        inputs={"CONDITION": [2, cond_play_o], "SUBSTACK": [2, bc_ao]})
    bs[cond_play_o]["parent"] = if_o
    bs[bc_ao]["parent"] = if_o
    chain([(h_o, bs[h_o]), (if_o, bs[if_o])])

    # ---- key 'x' pressed → BR_ANSWER_NOT ----
    h_x = gen(); bs[h_x] = mk("event_whenkeypressed",
        top=True, x=620, y=600,
        fields={"KEY_OPTION": ["x", None]})
    state_v_x = vrep("상태", V_STATE)
    cond_play_x = cmp_op("operator_equals", state_v_x, 1)
    bm_an = gen(); bs[bm_an] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["응답아님", BR_ANSWER_NOT]}, shadow=True)
    bc_an = gen(); bs[bc_an] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_an]})
    bs[bm_an]["parent"] = bc_an
    if_x = gen(); bs[if_x] = mk("control_if",
        inputs={"CONDITION": [2, cond_play_x], "SUBSTACK": [2, bc_an]})
    bs[cond_play_x]["parent"] = if_x
    bs[bc_an]["parent"] = if_x
    chain([(h_x, bs[h_x]), (if_x, bs[if_x])])

    # ---- when received 응답옥타브 ----
    def build_answer_branch(handler_id_top, br_pair, expected_oct):
        """expected_oct: 1 → user pressed O (claims octave); 0 → pressed X."""
        h_a = gen(); bs[h_a] = mk("event_whenbroadcastreceived",
            top=True, x=handler_id_top[0], y=handler_id_top[1],
            fields={"BROADCAST_OPTION": br_pair})

        # if 정답 == expected → correct, else wrong
        is_v = vrep("정답", V_IS_OCT)
        cond_match = cmp_op("operator_equals", is_v, expected_oct)

        # correct branch
        inc_s = gen(); bs[inc_s] = mk("data_changevariableby",
            inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
        set_fb_ok = gen(); bs[set_fb_ok] = mk("data_setvariableto",
            inputs={"VALUE": num(1)}, fields={"VARIABLE": ["결과", V_FEEDBACK]})
        bm_ok = gen(); bs[bm_ok] = mk("event_broadcast_menu",
            fields={"BROADCAST_OPTION": ["정답표시", BR_SHOW_CORRECT]}, shadow=True)
        bc_ok = gen(); bs[bc_ok] = mk("event_broadcast",
            inputs={"BROADCAST_INPUT": [1, bm_ok]})
        bs[bm_ok]["parent"] = bc_ok
        chain([(inc_s, bs[inc_s]), (set_fb_ok, bs[set_fb_ok]), (bc_ok, bs[bc_ok])])

        # wrong branch
        dec_s = gen(); bs[dec_s] = mk("data_changevariableby",
            inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["점수", V_SCORE]})
        set_fb_no = gen(); bs[set_fb_no] = mk("data_setvariableto",
            inputs={"VALUE": num(0)}, fields={"VARIABLE": ["결과", V_FEEDBACK]})
        bm_no = gen(); bs[bm_no] = mk("event_broadcast_menu",
            fields={"BROADCAST_OPTION": ["오답표시", BR_SHOW_WRONG]}, shadow=True)
        bc_no = gen(); bs[bc_no] = mk("event_broadcast",
            inputs={"BROADCAST_INPUT": [1, bm_no]})
        bs[bm_no]["parent"] = bc_no
        chain([(dec_s, bs[dec_s]), (set_fb_no, bs[set_fb_no]), (bc_no, bs[bc_no])])

        if_e = gen(); bs[if_e] = mk("control_if_else",
            inputs={"CONDITION": [2, cond_match],
                    "SUBSTACK":  [2, inc_s],
                    "SUBSTACK2": [2, dec_s]})
        bs[cond_match]["parent"] = if_e
        bs[inc_s]["parent"] = if_e
        bs[dec_s]["parent"] = if_e

        # wait 0.7s then broadcast 새라운드 — but only if state=1 still
        wait_n = gen(); bs[wait_n] = mk("control_wait",
            inputs={"DURATION": num(0.7)})
        state_v_n = vrep("상태", V_STATE)
        cond_still = cmp_op("operator_equals", state_v_n, 1)
        bm_nr = gen(); bs[bm_nr] = mk("event_broadcast_menu",
            fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]}, shadow=True)
        bc_nr = gen(); bs[bc_nr] = mk("event_broadcast",
            inputs={"BROADCAST_INPUT": [1, bm_nr]})
        bs[bm_nr]["parent"] = bc_nr
        if_still = gen(); bs[if_still] = mk("control_if",
            inputs={"CONDITION": [2, cond_still], "SUBSTACK": [2, bc_nr]})
        bs[cond_still]["parent"] = if_still
        bs[bc_nr]["parent"] = if_still

        chain([(h_a, bs[h_a]), (if_e, bs[if_e]),
               (wait_n, bs[wait_n]), (if_still, bs[if_still])])

    build_answer_branch((20,  900), ["응답옥타브", BR_ANSWER_OCT], 1)
    build_answer_branch((620, 900), ["응답아님",   BR_ANSWER_NOT], 0)

    return bs

# ---------------------------------------------------------------------------
# HIGHLIGHT sprite — yellow stars marking the two highlighted keys
# ---------------------------------------------------------------------------
def build_highlight_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop, litem = make_helpers(bs)

    # ---- flag clicked: hide original ----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz])])

    # ---- on 새라운드: delete old clones, then spawn left + right ----
    # The clone path also receives 새라운드 and deletes itself; meanwhile the
    # *original* (this script runs only on the original because clones don't
    # auto-run "when I receive" if they were spawned by the same event? —
    # Actually clones DO receive broadcasts too. We need to distinguish.)
    # To distinguish: original has 'Side' = 0; clones set Side to 1 or 2
    # on spawn. The original handler waits 0.05s (so the "delete clone"
    # handler can run first) then spawns two fresh clones.

    h_nr = gen(); bs[h_nr] = mk("event_whenbroadcastreceived",
        top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW_ROUND]})

    # if Side == 0  → this is the original; spawn 2 clones
    side_v = vrep("Side", V_SIDE)
    cond_origin = cmp_op("operator_equals", side_v, 0)

    wt_clean = gen(); bs[wt_clean] = mk("control_wait", inputs={"DURATION": num(0.05)})

    # set Side = 1, create clone (clone reads Side=1 then we set Side=2)
    set_side_1 = gen(); bs[set_side_1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["Side", V_SIDE]})
    cm1 = gen(); bs[cm1] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cc1 = gen(); bs[cc1] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cm1]})
    bs[cm1]["parent"] = cc1

    set_side_2 = gen(); bs[set_side_2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["Side", V_SIDE]})
    cm2 = gen(); bs[cm2] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cc2 = gen(); bs[cc2] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cm2]})
    bs[cm2]["parent"] = cc2

    # reset Side to 0 so the original is detected next round
    set_side_0 = gen(); bs[set_side_0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["Side", V_SIDE]})

    chain([(wt_clean, bs[wt_clean]),
           (set_side_1, bs[set_side_1]), (cc1, bs[cc1]),
           (set_side_2, bs[set_side_2]), (cc2, bs[cc2]),
           (set_side_0, bs[set_side_0])])

    if_origin = gen(); bs[if_origin] = mk("control_if",
        inputs={"CONDITION": [2, cond_origin], "SUBSTACK": [2, wt_clean]})
    bs[cond_origin]["parent"] = if_origin
    bs[wt_clean]["parent"] = if_origin

    # else (Side != 0 → clone) → delete this clone
    # We handle that as a separate top-level handler using control_start_as_clone
    # logic via a second 새라운드 handler:
    #   "if Side != 0 → delete this clone".
    # The cleanest split is via if_else inside the same handler.

    # Reformulate: single if/else
    cond_clone = cmp_op("operator_equals", side_v, 0)  # already created above as cond_origin
    # The cond_origin was already consumed by if_origin. Let's instead build
    # a new comparison for the clone-side and use control_if separately.

    # Approach: in addition to if_origin above, we add a separate "delete me
    # if Side != 0" check after.
    side_v2 = vrep("Side", V_SIDE)
    cond_nz = cmp_op("operator_gt", side_v2, 0)  # Side > 0 → clone
    del_self = gen(); bs[del_self] = mk("control_delete_this_clone")
    if_del = gen(); bs[if_del] = mk("control_if",
        inputs={"CONDITION": [2, cond_nz], "SUBSTACK": [2, del_self]})
    bs[cond_nz]["parent"] = if_del
    bs[del_self]["parent"] = if_del

    chain([(h_nr, bs[h_nr]), (if_del, bs[if_del]), (if_origin, bs[if_origin])])

    # ---- when I start as a clone ----
    h_clone = gen(); bs[h_clone] = mk("control_start_as_clone",
        top=True, x=320, y=200)

    # decide x by Side:
    #   if Side == 1 → x = key_x(K1), y = key_top_y()
    #   if Side == 2 → x = key_x(K2)
    side_c = vrep("Side", V_SIDE)
    cond_left = cmp_op("operator_equals", side_c, 1)

    # left branch: go to (key_x(K1), key_top_y())
    k1_v_h = vrep("K1", V_K1)
    # x = -195 + (K1 - 1) * 30
    k1_minus_1 = op("operator_subtract", k1_v_h, 1)
    mul_30_a   = op("operator_multiply", k1_minus_1, 30)
    add_left   = op("operator_add", mul_30_a, -195)
    go_left = gen(); bs[go_left] = mk("motion_gotoxy",
        inputs={"X": slot(add_left), "Y": num(key_top_y())})
    bs[add_left]["parent"] = go_left

    # right branch: go to (key_x(K2), key_top_y())
    k2_v_h = vrep("K2", V_K2)
    k2_minus_1 = op("operator_subtract", k2_v_h, 1)
    mul_30_b   = op("operator_multiply", k2_minus_1, 30)
    add_right  = op("operator_add", mul_30_b, -195)
    go_right = gen(); bs[go_right] = mk("motion_gotoxy",
        inputs={"X": slot(add_right), "Y": num(key_top_y())})
    bs[add_right]["parent"] = go_right

    if_lr = gen(); bs[if_lr] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_left],
                "SUBSTACK":  [2, go_left],
                "SUBSTACK2": [2, go_right]})
    bs[cond_left]["parent"] = if_lr
    bs[go_left]["parent"] = if_lr
    bs[go_right]["parent"] = if_lr

    show_c = gen(); bs[show_c] = mk("looks_show")
    front_c = gen(); bs[front_c] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    chain([(h_clone, bs[h_clone]),
           (if_lr, bs[if_lr]),
           (show_c, bs[show_c]),
           (front_c, bs[front_c])])

    # ---- on 게임종료: delete all clones (handled by per-clone listener) ----
    h_go = gen(); bs[h_go] = mk("event_whenbroadcastreceived",
        top=True, x=620, y=200,
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]})
    # only clones delete themselves; original just hides
    side_g = vrep("Side", V_SIDE)
    cond_clone_g = cmp_op("operator_gt", side_g, 0)
    del_g = gen(); bs[del_g] = mk("control_delete_this_clone")
    if_dg = gen(); bs[if_dg] = mk("control_if",
        inputs={"CONDITION": [2, cond_clone_g], "SUBSTACK": [2, del_g]})
    bs[cond_clone_g]["parent"] = if_dg
    bs[del_g]["parent"] = if_dg

    chain([(h_go, bs[h_go]), (if_dg, bs[if_dg])])

    return bs

# ---------------------------------------------------------------------------
# SOUND sprite — plays the two notes with PITCH effect for the chosen keys
# Separate sprite so PITCH effects don't interfere with stage sounds.
# ---------------------------------------------------------------------------
def build_sound_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop, litem = make_helpers(bs)

    # ---- flag clicked: hide sprite ----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])

    def gen_set_half_chain():
        """Generate 14 if-blocks to set V_HALF based on K1/K2 value.
        Returns: (first_block_id, set_K_var_function) where the caller
        chooses which variable (K1 or K2) is being looked at by passing a
        vrep id. Implementation: directly inline 14 branches."""
        pass  # we'll inline this per call

    def emit_half_setter(k_vid_name, k_vid):
        """Build a list of (id, block) pairs that set V_HALF based on
        which K (K1 or K2) variable equals 1..14. Caller chains them."""
        seq = []
        for i in range(1, 15):
            kv = vrep(k_vid_name, k_vid)
            eq = cmp_op("operator_equals", kv, i)
            set_h = gen(); bs[set_h] = mk("data_setvariableto",
                inputs={"VALUE": num(KEY_SEMITONES[i-1])},
                fields={"VARIABLE": ["Half", V_HALF]})
            if_b = gen(); bs[if_b] = mk("control_if",
                inputs={"CONDITION": [2, eq], "SUBSTACK": [2, set_h]})
            bs[eq]["parent"] = if_b
            bs[set_h]["parent"] = if_b
            seq.append((if_b, bs[if_b]))
        return seq

    # ---- when received 저음재생: set Half based on K1, set PITCH, play low ----
    h_low = gen(); bs[h_low] = mk("event_whenbroadcastreceived",
        top=True, x=20, y=300,
        fields={"BROADCAST_OPTION": ["저음재생", BR_PLAY_LOW]})

    half_seq_1 = emit_half_setter("K1", V_K1)

    # pitch = Half * 10
    half_v = vrep("Half", V_HALF)
    pitch_val = op("operator_multiply", half_v, 10)
    set_pitch = gen(); bs[set_pitch] = mk("sound_seteffectto",
        inputs={"VALUE": slot(pitch_val)},
        fields={"EFFECT": ["PITCH", None]})
    bs[pitch_val]["parent"] = set_pitch

    # play note_low
    snm_low = gen(); bs[snm_low] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["note_low", None]}, shadow=True)
    snd_low = gen(); bs[snd_low] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_low]})
    bs[snm_low]["parent"] = snd_low

    chain([(h_low, bs[h_low])] + half_seq_1 + [(set_pitch, bs[set_pitch]),
                                                (snd_low, bs[snd_low])])

    # ---- when received 고음재생: set Half based on K2, set PITCH, play high ----
    h_high = gen(); bs[h_high] = mk("event_whenbroadcastreceived",
        top=True, x=620, y=300,
        fields={"BROADCAST_OPTION": ["고음재생", BR_PLAY_HIGH]})

    half_seq_2 = emit_half_setter("K2", V_K2)

    half_v_h = vrep("Half", V_HALF)
    # PITCH effect = (Half - 12) * 10 (since note_high.wav is C5 base = +12 semitones)
    diff_12 = op("operator_subtract", half_v_h, 12)
    pitch_val_h = op("operator_multiply", diff_12, 10)
    set_pitch_h = gen(); bs[set_pitch_h] = mk("sound_seteffectto",
        inputs={"VALUE": slot(pitch_val_h)},
        fields={"EFFECT": ["PITCH", None]})
    bs[pitch_val_h]["parent"] = set_pitch_h

    snm_high = gen(); bs[snm_high] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["note_high", None]}, shadow=True)
    snd_high = gen(); bs[snd_high] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_high]})
    bs[snm_high]["parent"] = snd_high

    chain([(h_high, bs[h_high])] + half_seq_2 + [(set_pitch_h, bs[set_pitch_h]),
                                                  (snd_high, bs[snd_high])])

    # ---- on 정답표시: play correct sound ----
    h_ok = gen(); bs[h_ok] = mk("event_whenbroadcastreceived",
        top=True, x=20, y=900,
        fields={"BROADCAST_OPTION": ["정답표시", BR_SHOW_CORRECT]})
    reset_pitch_ok = gen(); bs[reset_pitch_ok] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["PITCH", None]})
    snm_ok = gen(); bs[snm_ok] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["correct", None]}, shadow=True)
    snd_ok = gen(); bs[snd_ok] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_ok]})
    bs[snm_ok]["parent"] = snd_ok
    chain([(h_ok, bs[h_ok]), (reset_pitch_ok, bs[reset_pitch_ok]),
           (snd_ok, bs[snd_ok])])

    # ---- on 오답표시: play wrong sound ----
    h_no = gen(); bs[h_no] = mk("event_whenbroadcastreceived",
        top=True, x=320, y=900,
        fields={"BROADCAST_OPTION": ["오답표시", BR_SHOW_WRONG]})
    reset_pitch_no = gen(); bs[reset_pitch_no] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["PITCH", None]})
    snm_no = gen(); bs[snm_no] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["wrong", None]}, shadow=True)
    snd_no = gen(); bs[snd_no] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_no]})
    bs[snm_no]["parent"] = snd_no
    chain([(h_no, bs[h_no]), (reset_pitch_no, bs[reset_pitch_no]),
           (snd_no, bs[snd_no])])

    return bs

# ---------------------------------------------------------------------------
# RESULT sprite — shows ✓ / ✗ icon for 0.5s
# ---------------------------------------------------------------------------
def build_result_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop, litem = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-30)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz])])

    # on 정답표시 → switch to correct costume, show 0.5s, hide
    h_ok = gen(); bs[h_ok] = mk("event_whenbroadcastreceived",
        top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["정답표시", BR_SHOW_CORRECT]})
    cm_ok = gen(); bs[cm_ok] = mk("looks_costume",
        fields={"COSTUME": ["correct", None]}, shadow=True)
    sw_ok = gen(); bs[sw_ok] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_ok]})
    bs[cm_ok]["parent"] = sw_ok
    front_ok = gen(); bs[front_ok] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show_ok = gen(); bs[show_ok] = mk("looks_show")
    wt_ok = gen(); bs[wt_ok] = mk("control_wait", inputs={"DURATION": num(0.5)})
    hi_ok = gen(); bs[hi_ok] = mk("looks_hide")
    chain([(h_ok, bs[h_ok]), (sw_ok, bs[sw_ok]), (front_ok, bs[front_ok]),
           (show_ok, bs[show_ok]), (wt_ok, bs[wt_ok]), (hi_ok, bs[hi_ok])])

    # on 오답표시
    h_no = gen(); bs[h_no] = mk("event_whenbroadcastreceived",
        top=True, x=320, y=200,
        fields={"BROADCAST_OPTION": ["오답표시", BR_SHOW_WRONG]})
    cm_no = gen(); bs[cm_no] = mk("looks_costume",
        fields={"COSTUME": ["wrong", None]}, shadow=True)
    sw_no = gen(); bs[sw_no] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, cm_no]})
    bs[cm_no]["parent"] = sw_no
    front_no = gen(); bs[front_no] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show_no = gen(); bs[show_no] = mk("looks_show")
    wt_no = gen(); bs[wt_no] = mk("control_wait", inputs={"DURATION": num(0.5)})
    hi_no = gen(); bs[hi_no] = mk("looks_hide")
    chain([(h_no, bs[h_no]), (sw_no, bs[sw_no]), (front_no, bs[front_no]),
           (show_no, bs[show_no]), (wt_no, bs[wt_no]), (hi_no, bs[hi_no])])

    # on 게임종료 → ensure hidden
    h_go = gen(); bs[h_go] = mk("event_whenbroadcastreceived",
        top=True, x=620, y=200,
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]})
    hi_g = gen(); bs[hi_g] = mk("looks_hide")
    chain([(h_go, bs[h_go]), (hi_g, bs[hi_g])])

    return bs

# ---------------------------------------------------------------------------
# GAME OVER sprite — banner shown when state = 0
# ---------------------------------------------------------------------------
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop, litem = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g  = gen(); bs[g]  = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz])])

    # on 게임종료 → bring to front, show
    h_go = gen(); bs[h_go] = mk("event_whenbroadcastreceived",
        top=True, x=320, y=200,
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(h_go, bs[h_go]), (front, bs[front]), (show, bs[show])])

    return bs

# ---------------------------------------------------------------------------
# ASSEMBLE
# ---------------------------------------------------------------------------
def wav_meta(path):
    with wave.open(path, "rb") as w:
        return w.getnframes(), w.getframerate()

def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)
    if not os.path.exists(ASSETS): os.makedirs(ASSETS)

    # ---- SVG assets ----
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    hi_md5 = md5_bytes(HIGHLIGHT_SVG.encode("utf-8"))
    with open(f"{WORK}/{hi_md5}.svg", "w", encoding="utf-8") as f:
        f.write(HIGHLIGHT_SVG)

    co_md5 = md5_bytes(CORRECT_SVG.encode("utf-8"))
    with open(f"{WORK}/{co_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CORRECT_SVG)

    wr_md5 = md5_bytes(WRONG_SVG.encode("utf-8"))
    with open(f"{WORK}/{wr_md5}.svg", "w", encoding="utf-8") as f:
        f.write(WRONG_SVG)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    # ---- WAV assets — synthesize if missing ----
    def ensure_wav(name, samples_fn):
        path = f"{ASSETS}/{name}.wav"
        if not os.path.exists(path):
            print(f"  synthesizing {name}.wav ...")
            write_wav(path, samples_fn())
        with open(path, "rb") as f: data = f.read()
        h = md5_bytes(data)
        with open(f"{WORK}/{h}.wav", "wb") as f: f.write(data)
        frames, rate = wav_meta(path)
        return {"name": name, "assetId": h, "dataFormat": "wav",
                "format": "", "rate": rate, "sampleCount": frames,
                "md5ext": f"{h}.wav"}

    low_snd     = ensure_wav("note_low",  lambda: gen_piano_note(261.63, dur=0.55))
    high_snd    = ensure_wav("note_high", lambda: gen_piano_note(523.25, dur=0.55))
    correct_snd = ensure_wav("correct",   gen_correct_chord)
    wrong_snd   = ensure_wav("wrong",     gen_wrong_buzz)

    # ---- build blocks ----
    stage_blocks     = build_stage_blocks()
    highlight_blocks = build_highlight_blocks()
    sound_blocks     = build_sound_blocks()
    result_blocks    = build_result_blocks()
    gameover_blocks  = build_gameover_blocks()

    # ---- targets ----
    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:    ["점수",    0],
            V_TIME:     ["시간",    GAME_TIME],
            V_STATE:    ["상태",    1],
            V_K1:       ["K1",      1],
            V_K2:       ["K2",      8],
            V_F1:       ["F1",      0],
            V_F2:       ["F2",      0],
            V_RATIO:    ["비율",    0],
            V_LOG2:     ["log2",    0],
            V_IS_OCT:   ["정답",    0],
            V_FEEDBACK: ["결과",    -1],
            V_ROUND:    ["라운드",   0],
            V_SIDE:     ["Side",   0],
            V_HALF:     ["Half",   0],
            V_OFFSET:   ["Offset", 0],
        },
        "lists": {
            L_FREQ_ID: ["주파수", []],
            L_NAME_ID: ["음이름", []],
        },
        "broadcasts": {
            BR_START:        "시작",
            BR_NEW_ROUND:    "새라운드",
            BR_PLAY_LOW:     "저음재생",
            BR_PLAY_HIGH:    "고음재생",
            BR_ANSWER_OCT:   "응답옥타브",
            BR_ANSWER_NOT:   "응답아님",
            BR_SHOW_CORRECT: "정답표시",
            BR_SHOW_WRONG:   "오답표시",
            BR_GAMEOVER:     "게임종료",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "piano", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180,
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None,
    }

    highlight = {
        "isStage": False, "name": "Highlight",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": highlight_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "star", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hi_md5, "md5ext": f"{hi_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 20,
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }

    soundsprite = {
        "isStage": False, "name": "Sound",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": sound_blocks, "comments": {},
        "currentCostume": 0,
        # Reuse the highlight star as a tiny invisible costume
        "costumes": [{
            "name": "_", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hi_md5, "md5ext": f"{hi_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 20,
        }],
        "sounds": [low_snd, high_snd, correct_snd, wrong_snd],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }

    result = {
        "isStage": False, "name": "Result",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": result_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "correct", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": co_md5, "md5ext": f"{co_md5}.svg",
             "rotationCenterX": 60, "rotationCenterY": 60},
            {"name": "wrong",   "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": wr_md5, "md5ext": f"{wr_md5}.svg",
             "rotationCenterX": 60, "rotationCenterY": 60},
        ],
        "sounds": [],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": -30, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }

    gameover = {
        "isStage": False, "name": "GameOver",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": gameover_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": go_md5, "md5ext": f"{go_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 80,
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 20, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }

    # ---- HUD monitors ----
    monitors = [
        {"id": V_SCORE, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_TIME, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "시간"}, "spriteName": None,
         "value": GAME_TIME, "width": 0, "height": 0, "x": 360, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": GAME_TIME, "isDiscrete": True},
        {"id": V_RATIO, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "비율"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 150, "y": 70,
         "visible": True, "sliderMin": 0, "sliderMax": 8, "isDiscrete": False},
        {"id": V_LOG2, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "log2"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 150, "y": 92,
         "visible": True, "sliderMin": 0, "sliderMax": 4, "isDiscrete": False},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 200, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, highlight, soundsprite, result, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "octave-piano-builder"},
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # validate JSON parsability
    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)

    # validate zip integrity
    with zipfile.ZipFile(OUTPUT) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"zip corrupt: {bad}")

    print(f"✓ wrote {OUTPUT}")
    # Report block counts
    print(f"  stage blocks:     {len(stage_blocks)}")
    print(f"  highlight blocks: {len(highlight_blocks)}")
    print(f"  sound blocks:     {len(sound_blocks)}")
    print(f"  result blocks:    {len(result_blocks)}")
    print(f"  gameover blocks:  {len(gameover_blocks)}")
    print(f"  total:            {len(stage_blocks)+len(highlight_blocks)+len(sound_blocks)+len(result_blocks)+len(gameover_blocks)}")

if __name__ == "__main__":
    main()
