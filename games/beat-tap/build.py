#!/usr/bin/env python3
"""Beat Tap — 4-lane rhythm game (D/F/J/K).

Emits 비트_탭.sb3 in this folder.

The chart is hard-coded in NOTES below (time-seconds, lane 1..4). The note
sprite is clone-driven: the stage's time loop advances V_TIME by 0.02 each
~0.02s and spawns a clone FALL_TIME seconds before its target time. Each
clone falls from y=180 to y=-130 over FALL_TIME, and is judged on key
presses (D=lane1, F=lane2, J=lane3, K=lane4) via broadcasts.
"""
import json, os, zipfile, shutil, hashlib, struct, math, wave

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "비트_탭.sb3")

# ----------------------------------------------------------------------
# Tunable constants
# ----------------------------------------------------------------------
FALL_TIME       = 1.5     # seconds a note takes to travel top → judgment line
WIN_PERFECT     = 0.06    # |diff| ≤ → Perfect (60ms — slightly looser than plan)
WIN_GOOD        = 0.13    # 0.06 < |diff| ≤ 0.13 → Good
WIN_MISS_AFTER  = 0.16    # diff > → auto-miss (note passed judgment line)
BPM             = 120
BEAT            = 60.0 / BPM      # 0.5 sec at 120 BPM
SAMPLE_RATE     = 22050

# Lane geometry (Scratch stage 480×360, origin centre)
LANE_X = {1: -120, 2: -40, 3: 40, 4: 120}
LANE_KEYS = {1: "d", 2: "f", 3: "j", 4: "k"}
TOP_Y          = 180
JUDGE_Y        = -130

# ----------------------------------------------------------------------
# Chart (time_sec, lane). Start with the song at t=2.0 to give a 2-second
# lead-in (player sees the first notes fall from the top before hit time).
# 16 bars at BPM 120, mostly 8th-note density = 64 notes. Patterns mix:
#   - L→R sweeps
#   - alt-edge (D/K)
#   - alt-mid (F/J)
#   - hand-cross
# ----------------------------------------------------------------------
def build_chart():
    notes = []
    bar = 4 * BEAT   # one 4-beat bar = 2.0 sec
    eighth = BEAT / 2   # 0.25 sec

    t0 = 2.0   # song start (gives 1.5s fall + 0.5s buffer)

    def add_bar_pattern(start_t, lanes):
        """lanes is a list of (offset_in_eighths, lane) tuples."""
        for off_e, ln in lanes:
            notes.append((round(start_t + off_e * eighth, 4), ln))

    # Bar 1 (t=2.0): L→R sweep on quarters
    add_bar_pattern(t0 + 0*bar, [(0,1),(2,2),(4,3),(6,4)])
    # Bar 2: R→L sweep on quarters
    add_bar_pattern(t0 + 1*bar, [(0,4),(2,3),(4,2),(6,1)])
    # Bar 3: alt-edges 8th notes
    add_bar_pattern(t0 + 2*bar, [(0,1),(1,4),(2,1),(3,4),(4,1),(5,4),(6,1),(7,4)])
    # Bar 4: alt-mid 8th notes
    add_bar_pattern(t0 + 3*bar, [(0,2),(1,3),(2,2),(3,3),(4,2),(5,3),(6,2),(7,3)])
    # Bar 5: L-pair then R-pair
    add_bar_pattern(t0 + 4*bar, [(0,1),(1,2),(4,3),(5,4)])
    # Bar 6: ladder up then down
    add_bar_pattern(t0 + 5*bar, [(0,1),(2,2),(4,3),(6,4)])
    # Bar 7: thicker, 8th notes
    add_bar_pattern(t0 + 6*bar, [(0,1),(1,3),(2,2),(3,4),(4,1),(5,3),(6,2),(7,4)])
    # Bar 8 (break): only beats 1 and 4 — give the player a rest
    add_bar_pattern(t0 + 7*bar, [(0,2),(6,3)])
    # Bar 9: re-entry on the offbeats, alt-edges
    add_bar_pattern(t0 + 8*bar, [(1,1),(3,4),(5,1),(7,4)])
    # Bar 10: ditto mids
    add_bar_pattern(t0 + 9*bar, [(1,2),(3,3),(5,2),(7,3)])
    # Bar 11: hand-cross D/J/F/K
    add_bar_pattern(t0 + 10*bar, [(0,1),(2,3),(4,2),(6,4)])
    # Bar 12: K/F/J/D
    add_bar_pattern(t0 + 11*bar, [(0,4),(2,2),(4,3),(6,1)])
    # Bar 13: 8th note climb
    add_bar_pattern(t0 + 12*bar, [(0,1),(1,2),(2,3),(3,4),(4,1),(5,2),(6,3),(7,4)])
    # Bar 14: 8th note fall
    add_bar_pattern(t0 + 13*bar, [(0,4),(1,3),(2,2),(3,1),(4,4),(5,3),(6,2),(7,1)])
    # Bar 15: edge-mid alternation
    add_bar_pattern(t0 + 14*bar, [(0,1),(2,4),(4,2),(6,3)])
    # Bar 16 (final): big chord-like spread, then end
    add_bar_pattern(t0 + 15*bar, [(0,1),(0,4),(4,2),(4,3),(6,1),(7,4)])

    # Sort by time
    notes.sort(key=lambda nt: (nt[0], nt[1]))
    return notes

NOTES = build_chart()
END_T = max(t for t, _ in NOTES) + 2.0    # song end = 2s after last note

# ----------------------------------------------------------------------
# Background SVG: 4 lane tracks, judgment line, key labels
# ----------------------------------------------------------------------
def build_bg_svg():
    # Lane geometry in SVG coordinates (svg x = scratchX + 240, svg y = 180 - scratchY)
    # Stage 480×360, lane width ≈ 70, gap ≈ 10
    lane_centres_svg = [240 + LANE_X[i] for i in (1, 2, 3, 4)]
    lane_w = 64
    lane_rects = ""
    for i, cx in enumerate(lane_centres_svg, start=1):
        x = cx - lane_w/2
        # subtle alternating shade
        fill = "#1A1F3A" if i % 2 else "#22284A"
        lane_rects += f'  <rect x="{x:.1f}" y="40" width="{lane_w}" height="280" fill="{fill}" opacity="0.85"/>\n'
        # lane outline
        lane_rects += f'  <rect x="{x:.1f}" y="40" width="{lane_w}" height="280" fill="none" stroke="#3B4378" stroke-width="1"/>\n'

    # Judgment line at scratchY = JUDGE_Y (-130) → svgY = 180 - (-130) = 310
    judge_y_svg = 180 - JUDGE_Y
    # Key labels under judgment line
    key_labels = ""
    for i, cx in enumerate(lane_centres_svg, start=1):
        key = LANE_KEYS[i].upper()
        key_labels += f"""  <rect x="{cx-22}" y="{judge_y_svg+8}" width="44" height="38" rx="8" fill="#0E1224" stroke="#7AE2FF" stroke-width="2"/>
  <text x="{cx}" y="{judge_y_svg+35}" text-anchor="middle" fill="#7AE2FF"
        font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="bold">{key}</text>
"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0A0D24"/>
      <stop offset="50%"  stop-color="#0E122E"/>
      <stop offset="100%" stop-color="#070819"/>
    </linearGradient>
    <linearGradient id="judgeLine" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#7AE2FF" stop-opacity="0.2"/>
      <stop offset="50%" stop-color="#7AE2FF" stop-opacity="1.0"/>
      <stop offset="100%" stop-color="#7AE2FF" stop-opacity="0.2"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#bg)"/>

  <!-- decorative neon glow at top -->
  <ellipse cx="240" cy="0" rx="240" ry="40" fill="#D946EF" opacity="0.10"/>

  <!-- lane rectangles -->
{lane_rects}

  <!-- judgment line + glow -->
  <rect x="40" y="{judge_y_svg-2}" width="400" height="4" fill="url(#judgeLine)"/>
  <rect x="40" y="{judge_y_svg-1}" width="400" height="2" fill="#FFFFFF" opacity="0.6"/>

  <!-- key labels -->
{key_labels}

  <!-- title strip -->
  <text x="240" y="28" text-anchor="middle" fill="#E0E5FF"
        font-family="Arial, Helvetica, sans-serif" font-size="20" font-weight="bold"
        opacity="0.85">BEAT TAP</text>
</svg>"""

BG_SVG = build_bg_svg()

# ----------------------------------------------------------------------
# Note SVG (one SVG per costume — 4 costumes for state colours)
# Size ≈ 56×24 (rectangular tap-bar). Center of sprite is (28, 12).
# ----------------------------------------------------------------------
def note_svg(fill_outer, fill_inner, glow):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="56" height="24" viewBox="0 0 56 24">
  <defs>
    <linearGradient id="n" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="{fill_inner}"/>
      <stop offset="100%" stop-color="{fill_outer}"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="52" height="20" rx="10" fill="{glow}" opacity="0.55"/>
  <rect x="4" y="4" width="48" height="16" rx="8"  fill="url(#n)"/>
  <rect x="6" y="5" width="44" height="6"  rx="3"  fill="#FFFFFF" opacity="0.40"/>
</svg>"""

NOTE_NORMAL  = note_svg("#3B82F6", "#A5C8FF", "#60A5FA")  # blue
NOTE_PERFECT = note_svg("#F59E0B", "#FEF3C7", "#FDE68A")  # gold
NOTE_GOOD    = note_svg("#10B981", "#D1FAE5", "#6EE7B7")  # green
NOTE_MISS    = note_svg("#6B7280", "#9CA3AF", "#4B5563")  # grey

# ----------------------------------------------------------------------
# Judgment banner SVG
# ----------------------------------------------------------------------
JUDGE_BANNER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="44" viewBox="0 0 200 44">
  <rect x="2" y="2" width="196" height="40" rx="20" fill="#000000" opacity="0.0"/>
</svg>"""

# ----------------------------------------------------------------------
# Final result banner
# ----------------------------------------------------------------------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="200" viewBox="0 0 360 200">
  <rect x="5" y="5" width="350" height="190" rx="16"
        fill="#0E122E" opacity="0.94"
        stroke="#7AE2FF" stroke-width="3"/>
  <text x="180" y="60" text-anchor="middle"
        fill="#7AE2FF" font-family="Arial, Helvetica, sans-serif"
        font-size="36" font-weight="bold">CLEAR!</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">점수 / 최대 콤보는 좌상단 모니터 확인</text>
  <text x="180" y="150" text-anchor="middle"
        fill="#FDE68A" font-family="Arial, Helvetica, sans-serif"
        font-size="16">초록 깃발을 다시 누르면 재시작</text>
  <text x="180" y="178" text-anchor="middle"
        fill="#94A3B8" font-family="Arial, Helvetica, sans-serif"
        font-size="13">D / F / J / K 키</text>
</svg>"""

# ----------------------------------------------------------------------
# Audio generation
# ----------------------------------------------------------------------
def write_wav(path, samples_i16, rate=SAMPLE_RATE):
    """Write a 16-bit mono PCM WAV file."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples_i16))

def gen_tick_wav():
    """A short bright click — used for Perfect/Good hits."""
    dur = 0.07
    n = int(dur * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        # decaying sine 1500Hz + harmonic
        env = math.exp(-t * 35.0)
        s = math.sin(2*math.pi*1500*t) * 0.5 + math.sin(2*math.pi*3000*t) * 0.25
        out.append(int(max(-1, min(1, s*env)) * 28000))
    return out

def gen_miss_wav():
    """A low thud for misses."""
    dur = 0.12
    n = int(dur * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 18.0)
        s = math.sin(2*math.pi*180*t) * 0.7 + math.sin(2*math.pi*90*t) * 0.4
        out.append(int(max(-1, min(1, s*env)) * 26000))
    return out

def gen_bgm_wav():
    """Synthesize a ~36s 8-bit melody at 120 BPM aligned to the chart.

    Each note in NOTES gets a short tone at its target time. We also lay a
    bassline on the downbeats and a soft tick on every eighth note so the
    rhythm is audible even on the sparse bars."""
    total_dur = END_T + 1.0
    n_total = int(total_dur * SAMPLE_RATE)
    buf = [0.0] * n_total

    # lane → pitch (C-major pentatonic-ish, 4 distinct tones)
    lane_freq = {1: 261.63, 2: 329.63, 3: 392.00, 4: 523.25}   # C4, E4, G4, C5

    def square_wave(t, freq):
        # mild square via sin(sin)
        s = math.sin(2*math.pi*freq*t)
        return 1.0 if s > 0 else -1.0

    def add_tone(start_t, dur, freq, amp=0.15, waveform="square"):
        i0 = max(0, int(start_t * SAMPLE_RATE))
        i1 = min(n_total, int((start_t + dur) * SAMPLE_RATE))
        for i in range(i0, i1):
            t = (i - i0) / SAMPLE_RATE
            env = math.exp(-t * 6.0) * (1.0 - (i - i0) / max(1, i1-i0)) ** 0.5
            if waveform == "square":
                s = square_wave(t, freq)
            elif waveform == "sine":
                s = math.sin(2*math.pi*freq*t)
            else:
                s = math.sin(2*math.pi*freq*t)
            buf[i] += s * amp * env

    # Melody: each NOTE → tone at its target time
    for t, lane in NOTES:
        add_tone(t, 0.18, lane_freq[lane], amp=0.18, waveform="square")

    # Bassline: low note every downbeat (every beat = 0.5s)
    t0 = 2.0
    bass_pattern = [65.41, 65.41, 87.31, 98.00]  # C2 C2 F2 G2 — simple 4-beat
    last_beat = int((END_T - t0) / BEAT)
    for k in range(last_beat):
        bt = t0 + k * BEAT
        bf = bass_pattern[k % 4]
        add_tone(bt, BEAT * 0.9, bf, amp=0.10, waveform="sine")

    # Hat: soft click on each eighth (very low amp)
    last_eighth = int((END_T - t0) / (BEAT/2))
    for k in range(last_eighth):
        ht = t0 + k * (BEAT/2)
        # short noise burst
        i0 = int(ht * SAMPLE_RATE)
        i1 = min(n_total, i0 + int(0.03 * SAMPLE_RATE))
        import random
        random.seed(k)
        for i in range(i0, i1):
            t = (i - i0) / SAMPLE_RATE
            env = math.exp(-t * 80.0)
            s = (random.random() * 2 - 1) * 0.05 * env
            buf[i] += s

    # Normalize
    peak = max((abs(s) for s in buf), default=1.0)
    if peak < 1e-6: peak = 1.0
    scale = 0.85 / peak
    samples = [int(max(-1, min(1, s * scale)) * 28000) for s in buf]
    return samples

# ----------------------------------------------------------------------
# Scratch JSON helpers (copied from sister build.py files)
# ----------------------------------------------------------------------
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

def make_helpers(bs):
    def vrep(name, vid):
        bid = gen()
        bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid
    def lrep(name, lid):
        # list reporter (the whole list as a string) — rarely used directly
        bid = gen()
        bs[bid] = mk("data_listcontents", fields={"LIST": [name, lid]})
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
    def unary(opcode, a, key="NUM"):
        bid = gen()
        if isinstance(a, str): ins = {key: slot(a)}
        else: ins = {key: num(a)}
        bs[bid] = mk(opcode, inputs=ins)
        if isinstance(a, str): bs[a]["parent"] = bid
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
    def list_item(name, lid, idx):
        """data_itemoflist reporter."""
        bid = gen()
        if isinstance(idx, str):
            ins = {"INDEX": slot(idx, sk=7, sv="1")}
            bs[idx]["parent"] = bid
        else:
            ins = {"INDEX": [1, [7, str(idx)]]}
        bs[bid] = mk("data_itemoflist", inputs=ins, fields={"LIST":[name, lid]})
        return bid
    def list_length(name, lid):
        bid = gen()
        bs[bid] = mk("data_lengthoflist", fields={"LIST":[name, lid]})
        return bid
    def list_replace(name, lid, idx, val):
        bid = gen()
        ins = {}
        if isinstance(idx, str):
            ins["INDEX"] = slot(idx, sk=7, sv="1"); bs[idx]["parent"] = bid
        else:
            ins["INDEX"] = [1, [7, str(idx)]]
        if isinstance(val, str):
            ins["ITEM"] = slot(val, sk=10, sv=""); bs[val]["parent"] = bid
        else:
            ins["ITEM"] = text_lit(val)
        bs[bid] = mk("data_replaceitemoflist", inputs=ins, fields={"LIST":[name, lid]})
        return bid
    def list_add(name, lid, val):
        bid = gen()
        if isinstance(val, str):
            ins = {"ITEM": slot(val, sk=10, sv="")}
            bs[val]["parent"] = bid
        else:
            ins = {"ITEM": text_lit(val)}
        bs[bid] = mk("data_addtolist", inputs=ins, fields={"LIST":[name, lid]})
        return bid
    def list_delete_all(name, lid):
        bid = gen()
        bs[bid] = mk("data_deletealloflist", fields={"LIST":[name, lid]})
        return bid
    return (vrep, lrep, op, unary, cmp_op, bool_op,
            list_item, list_length, list_replace, list_add, list_delete_all)

# Variable / list / broadcast IDs
V_SCORE     = "varScore01"
V_COMBO     = "varCombo02"
V_MAX_COMBO = "varMax03"
V_TIME      = "varTime04"
V_STATE     = "varState05"     # 1 = playing, 0 = over
V_AUDIO_OFF = "varAOff06"      # BGM offset in seconds (tunable post-build)
V_JUDGE_TXT = "varJudge07"     # last judgment text (display)
V_SPAWN_I   = "varSpawnI08"    # stage-local: spawn-index in NOTES
V_HIT_I     = "varHitI09"      # judging key handler scratch
V_HIT_DIFF  = "varHitDiff10"   # judging diff
V_HIT_BEST  = "varBestI11"     # best-candidate clone index

# Stage-scope spawn-pass variables (snapshot of the upcoming note)
V_NEXT_LANE = "varNxtLn12a"    # 1..4 — set by stage, read by clone on init
V_NEXT_TARG = "varNxtTg13a"    # target V_TIME — same
V_HITKEY    = "varHitKey15"    # for KEY broadcasts: 1..4 telling which lane

# Note-sprite LOCAL variables (each clone gets its own copy)
V_LANE      = "varLane12"      # 1..4 (sprite-local on 음표)
V_TARGET    = "varTarget13"    # target V_TIME (sprite-local on 음표)
V_NSTATE    = "varNState14"    # 0=falling, 1=judged (sprite-local on 음표)

# Lists
L_NOTE_T    = "listT01"
L_NOTE_L    = "listL02"

# Broadcasts
BR_START     = "brStart01"
BR_END       = "brEnd02"
BR_KEY       = "brKey03"          # carries V_HITKEY=1..4
BR_HIT_P     = "brHitP04"
BR_HIT_G     = "brHitG05"
BR_MISS      = "brMiss06"

# ======================================================================
#  STAGE blocks
# ======================================================================
def build_stage_blocks():
    bs = {}
    (vrep, lrep, op, unary, cmp_op, bool_op,
     list_item, list_length, list_replace, list_add, list_delete_all) = make_helpers(bs)

    # ----- when flag clicked -----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)

    # init variables
    inits = []
    for vid, name, val in [
        (V_SCORE, "점수", 0),
        (V_COMBO, "콤보", 0),
        (V_MAX_COMBO, "최대콤보", 0),
        (V_TIME, "곡시간", 0),
        (V_STATE, "게임상태", 1),
        (V_AUDIO_OFF, "오디오오프셋", 0.0),
        (V_SPAWN_I, "스폰_i", 1),
    ]:
        bid = gen(); bs[bid] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE":[name, vid]})
        inits.append((bid, bs[bid]))
    j_set = gen(); bs[j_set] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("Ready...")}, fields={"VARIABLE":["판정", V_JUDGE_TXT]})
    inits.append((j_set, bs[j_set]))

    # Rebuild the chart lists fresh each run
    clr_t = gen(); bs[clr_t] = mk("data_deletealloflist", fields={"LIST":["채보시각", L_NOTE_T]})
    clr_l = gen(); bs[clr_l] = mk("data_deletealloflist", fields={"LIST":["채보레인", L_NOTE_L]})
    inits.append((clr_t, bs[clr_t])); inits.append((clr_l, bs[clr_l]))

    for t, lane in NOTES:
        at = gen(); bs[at] = mk("data_addtolist",
            inputs={"ITEM": text_lit(t)},
            fields={"LIST":["채보시각", L_NOTE_T]})
        al = gen(); bs[al] = mk("data_addtolist",
            inputs={"ITEM": text_lit(lane)},
            fields={"LIST":["채보레인", L_NOTE_L]})
        inits.append((at, bs[at])); inits.append((al, bs[al]))

    # broadcast 게임시작
    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION":["게임시작", BR_START]}, shadow=True)
    bcast = gen(); bs[bcast] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm]})
    bs[bm]["parent"] = bcast

    chain([(h,bs[h])] + inits + [(bcast,bs[bcast])])

    # ----- on 게임시작: start BGM + run time loop -----
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION":["게임시작", BR_START]})

    # apply BGM offset by waiting (only if positive)
    # Simpler approach: play sound bgm immediately, then enter time loop.
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["bgm", None]}, shadow=True)
    play_bgm = gen(); bs[play_bgm] = mk("sound_play",
        inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = play_bgm

    # repeat until V_STATE=0
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # body:
    #   change V_TIME by 0.02
    #   while there are unspawned notes whose target_t - V_TIME ≤ FALL_TIME:
    #       set V_LANE, V_TARGET, create-clone of Note, change V_SPAWN_I by 1
    #   if V_TIME > END_T → V_STATE=0
    #   wait 0.02
    chg_t = gen(); bs[chg_t] = mk("data_changevariableby",
        inputs={"VALUE": num(0.02)}, fields={"VARIABLE":["곡시간", V_TIME]})

    # inner spawn loop:
    # condition: (스폰_i ≤ length(L_NOTE_T))  AND  (item(스폰_i, L_NOTE_T) - FALL_TIME ≤ V_TIME)
    spi_v = vrep("스폰_i", V_SPAWN_I)
    len_t = list_length("채보시각", L_NOTE_T)
    cond_idx_ok = cmp_op("operator_lt", spi_v, op("operator_add", len_t, 1))
    # We need (spi <= len) — use NOT (spi > len). Easier: spi < len+1.
    # cond_idx_ok above is correct since len+1 is computed via op_add.

    # condition 2: item(spi, T) - FALL_TIME <= V_TIME  i.e.  V_TIME ≥ item - FALL_TIME
    spi_v2 = vrep("스폰_i", V_SPAWN_I)
    it_t = list_item("채보시각", L_NOTE_T, spi_v2)
    spawn_threshold = op("operator_subtract", it_t, FALL_TIME)
    time_v = vrep("곡시간", V_TIME)
    cond_time = cmp_op("operator_gt", time_v, op("operator_subtract", spawn_threshold, 0.0001))
    # simpler: V_TIME ≥ (item - FALL_TIME) <==> V_TIME > (item - FALL_TIME - epsilon)

    cond_spawn = bool_op("operator_and", cond_idx_ok, cond_time)

    # spawn body — write to STAGE-scope V_NEXT_* (clone copies them on init)
    spi_v3 = vrep("스폰_i", V_SPAWN_I)
    it_t2 = list_item("채보시각", L_NOTE_T, spi_v3)
    set_target = gen(); bs[set_target] = mk("data_setvariableto",
        inputs={"VALUE": slot(it_t2)}, fields={"VARIABLE":["다음목표", V_NEXT_TARG]})
    bs[it_t2]["parent"] = set_target

    spi_v4 = vrep("스폰_i", V_SPAWN_I)
    it_l = list_item("채보레인", L_NOTE_L, spi_v4)
    set_lane = gen(); bs[set_lane] = mk("data_setvariableto",
        inputs={"VALUE": slot(it_l)}, fields={"VARIABLE":["다음레인", V_NEXT_LANE]})
    bs[it_l]["parent"] = set_lane

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["음표", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone

    inc_spi = gen(); bs[inc_spi] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE":["스폰_i", V_SPAWN_I]})

    chain([(set_target,bs[set_target]),(set_lane,bs[set_lane]),
           (cclone,bs[cclone]),(inc_spi,bs[inc_spi])])

    spawn_loop = gen(); bs[spawn_loop] = mk("control_repeat_until",
        inputs={"CONDITION":[2, gen_not_op(bs, cond_spawn)], "SUBSTACK":[2, set_target]})
    # gen_not_op wraps cond_spawn in operator_not — repeat_until needs the
    # "stop when true" condition, so we want NOT(can_spawn) to end the loop.
    bs[set_target]["parent"] = spawn_loop

    # check end-of-song
    time_v2 = vrep("곡시간", V_TIME)
    cond_end = cmp_op("operator_gt", time_v2, END_T)
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE":["게임상태", V_STATE]})
    bm_end = gen(); bs[bm_end] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION":["게임종료", BR_END]}, shadow=True)
    bc_end = gen(); bs[bc_end] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_end]})
    bs[bm_end]["parent"] = bc_end
    chain([(set_state0,bs[set_state0]),(bc_end,bs[bc_end])])
    if_end = gen(); bs[if_end] = mk("control_if",
        inputs={"CONDITION":[2, cond_end], "SUBSTACK":[2, set_state0]})
    bs[cond_end]["parent"] = if_end
    bs[set_state0]["parent"] = if_end

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(chg_t,bs[chg_t]),(spawn_loop,bs[spawn_loop]),(if_end,bs[if_end]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_over], "SUBSTACK":[2, chg_t]})
    bs[cond_over]["parent"] = rep_until
    bs[chg_t]["parent"] = rep_until

    chain([(h2,bs[h2]),(play_bgm,bs[play_bgm]),(rep_until,bs[rep_until])])

    # ----- key handlers: D/F/J/K → set V_HITKEY then broadcast BR_KEY -----
    for lane, key in LANE_KEYS.items():
        kh = gen(); bs[kh] = mk("event_whenkeypressed",
            top=True, x=400, y=20 + (lane-1)*120,
            fields={"KEY_OPTION":[key, None]})
        # only react while playing
        state_v3 = vrep("게임상태", V_STATE)
        cond_play = cmp_op("operator_equals", state_v3, 1)
        set_hk = gen(); bs[set_hk] = mk("data_setvariableto",
            inputs={"VALUE": num(lane)}, fields={"VARIABLE":["눌린레인", V_HITKEY]})
        bm_k = gen(); bs[bm_k] = mk("event_broadcast_menu",
            fields={"BROADCAST_OPTION":["키입력", BR_KEY]}, shadow=True)
        bc_k = gen(); bs[bc_k] = mk("event_broadcast",
            inputs={"BROADCAST_INPUT":[1, bm_k]})
        bs[bm_k]["parent"] = bc_k
        chain([(set_hk,bs[set_hk]),(bc_k,bs[bc_k])])
        if_play = gen(); bs[if_play] = mk("control_if",
            inputs={"CONDITION":[2, cond_play], "SUBSTACK":[2, set_hk]})
        bs[cond_play]["parent"] = if_play
        bs[set_hk]["parent"] = if_play
        chain([(kh,bs[kh]),(if_play,bs[if_play])])

    # ----- judgment hooks → update score/combo/judge text -----
    def make_hit_handler(broadcast_name, broadcast_id, score_delta, judge_text, top_y, pitch=0):
        hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=900, y=top_y,
            fields={"BROADCAST_OPTION":[broadcast_name, broadcast_id]})
        chg_s = gen(); bs[chg_s] = mk("data_changevariableby",
            inputs={"VALUE": num(score_delta)}, fields={"VARIABLE":["점수", V_SCORE]})
        chg_c = gen(); bs[chg_c] = mk("data_changevariableby",
            inputs={"VALUE": num(1)}, fields={"VARIABLE":["콤보", V_COMBO]})
        # update max combo: if 콤보 > 최대콤보 then 최대콤보 = 콤보
        cv = vrep("콤보", V_COMBO); mv = vrep("최대콤보", V_MAX_COMBO)
        cond_new_max = cmp_op("operator_gt", cv, mv)
        cv2 = vrep("콤보", V_COMBO)
        set_mc = gen(); bs[set_mc] = mk("data_setvariableto",
            inputs={"VALUE": slot(cv2)}, fields={"VARIABLE":["최대콤보", V_MAX_COMBO]})
        bs[cv2]["parent"] = set_mc
        if_max = gen(); bs[if_max] = mk("control_if",
            inputs={"CONDITION":[2, cond_new_max], "SUBSTACK":[2, set_mc]})
        bs[cond_new_max]["parent"] = if_max; bs[set_mc]["parent"] = if_max

        set_j = gen(); bs[set_j] = mk("data_setvariableto",
            inputs={"VALUE": text_lit(judge_text)}, fields={"VARIABLE":["판정", V_JUDGE_TXT]})

        # play tick.wav (with pitch offset for Good)
        pe = gen(); bs[pe] = mk("sound_seteffectto",
            inputs={"VALUE": num(pitch)}, fields={"EFFECT":["PITCH", None]})
        snm2 = gen(); bs[snm2] = mk("sound_sounds_menu",
            fields={"SOUND_MENU":["tick", None]}, shadow=True)
        snd2 = gen(); bs[snd2] = mk("sound_play",
            inputs={"SOUND_MENU":[1, snm2]})
        bs[snm2]["parent"] = snd2

        chain([(hb,bs[hb]),(chg_s,bs[chg_s]),(chg_c,bs[chg_c]),
               (if_max,bs[if_max]),(set_j,bs[set_j]),(pe,bs[pe]),(snd2,bs[snd2])])

    make_hit_handler("판정_퍼펙트", BR_HIT_P, 100, "Perfect!", 1500, pitch=0)
    make_hit_handler("판정_굿",     BR_HIT_G,  50, "Good",     1750, pitch=-150)

    # miss handler: reset combo, set judge, play miss
    hb_m = gen(); bs[hb_m] = mk("event_whenbroadcastreceived", top=True, x=900, y=2000,
        fields={"BROADCAST_OPTION":["판정_미스", BR_MISS]})
    set_c0 = gen(); bs[set_c0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE":["콤보", V_COMBO]})
    set_jm = gen(); bs[set_jm] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("Miss")}, fields={"VARIABLE":["판정", V_JUDGE_TXT]})
    pe_m = gen(); bs[pe_m] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT":["PITCH", None]})
    snm_m = gen(); bs[snm_m] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["miss", None]}, shadow=True)
    snd_m = gen(); bs[snd_m] = mk("sound_play",
        inputs={"SOUND_MENU":[1, snm_m]})
    bs[snm_m]["parent"] = snd_m
    chain([(hb_m,bs[hb_m]),(set_c0,bs[set_c0]),(set_jm,bs[set_jm]),
           (pe_m,bs[pe_m]),(snd_m,bs[snd_m])])

    return bs

def gen_not_op(bs, inner_bid):
    """Wrap a boolean reporter in operator_not."""
    bid = gen()
    bs[bid] = mk("operator_not", inputs={"OPERAND":[2, inner_bid]})
    bs[inner_bid]["parent"] = bid
    return bid

# ======================================================================
#  NOTE sprite blocks
# ======================================================================
def build_note_blocks():
    bs = {}
    (vrep, lrep, op, unary, cmp_op, bool_op,
     list_item, list_length, list_replace, list_add, list_delete_all) = make_helpers(bs)

    # ----- when flag clicked: hide; mark the original sprite as "already
    #       judged" so the BR_KEY handler on the original instance does not
    #       award a free hit on every key-press. Each clone overwrites
    #       노트상태 to 0 in its own init. -----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(110)})
    set_ns_orig = gen(); bs[set_ns_orig] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE":["노트상태", V_NSTATE]})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz]),(set_ns_orig,bs[set_ns_orig])])

    # ----- when I start as a clone: fall loop -----
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)

    # First: snapshot stage's V_NEXT_LANE / V_NEXT_TARG into sprite-local
    # V_LANE / V_TARGET. This avoids a race when the stage's spawn-loop
    # iterates again before this clone's setup completes.
    nxt_lane_v = vrep("다음레인", V_NEXT_LANE)
    snap_lane = gen(); bs[snap_lane] = mk("data_setvariableto",
        inputs={"VALUE": slot(nxt_lane_v)}, fields={"VARIABLE":["레인", V_LANE]})
    bs[nxt_lane_v]["parent"] = snap_lane

    nxt_targ_v = vrep("다음목표", V_NEXT_TARG)
    snap_targ = gen(); bs[snap_targ] = mk("data_setvariableto",
        inputs={"VALUE": slot(nxt_targ_v)}, fields={"VARIABLE":["목표시각", V_TARGET]})
    bs[nxt_targ_v]["parent"] = snap_targ

    set_ns = gen(); bs[set_ns] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE":["노트상태", V_NSTATE]})

    # choose costume = "normal"
    cm0 = gen(); bs[cm0] = mk("looks_costume",
        fields={"COSTUME":["normal", None]}, shadow=True)
    set_costume = gen(); bs[set_costume] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cm0]})
    bs[cm0]["parent"] = set_costume

    # position: x = lane_x(V_LANE), y = TOP_Y
    # build a chain of if-blocks setting x to LANE_X[lane]
    lane_if_blocks = []
    for lane in (1, 2, 3, 4):
        lv = vrep("레인", V_LANE)
        eq = cmp_op("operator_equals", lv, lane)
        setx = gen(); bs[setx] = mk("motion_setx", inputs={"X": num(LANE_X[lane])})
        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION":[2, eq], "SUBSTACK":[2, setx]})
        bs[eq]["parent"] = ifb; bs[setx]["parent"] = ifb
        lane_if_blocks.append(ifb)

    sety = gen(); bs[sety] = mk("motion_sety", inputs={"Y": num(TOP_Y)})
    show = gen(); bs[show] = mk("looks_show")
    front_b = gen(); bs[front_b] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})

    # fall loop: repeat until 노트상태=1 OR V_TIME > target+WIN_MISS_AFTER
    # body: set y = TOP_Y - (TOP_Y - JUDGE_Y) * (V_TIME - (target - FALL_TIME)) / FALL_TIME
    # = TOP_Y - 310 * (V_TIME - target + FALL_TIME) / FALL_TIME

    time_v = vrep("곡시간", V_TIME)
    target_v = vrep("목표시각", V_TARGET)
    # progress = V_TIME - target + FALL_TIME
    diff_t = op("operator_subtract", time_v, target_v)
    prog = op("operator_add", diff_t, FALL_TIME)
    # ratio = prog / FALL_TIME
    ratio = op("operator_divide", prog, FALL_TIME)
    # drop = (TOP_Y - JUDGE_Y) * ratio = 310 * ratio
    drop = op("operator_multiply", TOP_Y - JUDGE_Y, ratio)
    # y_pos = TOP_Y - drop
    y_pos = op("operator_subtract", TOP_Y, drop)
    set_y = gen(); bs[set_y] = mk("motion_sety", inputs={"Y": slot(y_pos)})
    bs[y_pos]["parent"] = set_y

    # if 노트상태 = 0 and V_TIME > 목표 + WIN_MISS_AFTER → broadcast miss, set state, costume
    ns_v = vrep("노트상태", V_NSTATE)
    cond_alive = cmp_op("operator_equals", ns_v, 0)
    time_v2 = vrep("곡시간", V_TIME)
    target_v2 = vrep("목표시각", V_TARGET)
    miss_threshold = op("operator_add", target_v2, WIN_MISS_AFTER)
    cond_late = cmp_op("operator_gt", time_v2, miss_threshold)
    cond_miss = bool_op("operator_and", cond_alive, cond_late)

    # miss body: broadcast 판정_미스, set 노트상태=1, switch costume miss
    bm_m = gen(); bs[bm_m] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION":["판정_미스", BR_MISS]}, shadow=True)
    bc_m = gen(); bs[bc_m] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_m]})
    bs[bm_m]["parent"] = bc_m
    set_ns1_miss = gen(); bs[set_ns1_miss] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE":["노트상태", V_NSTATE]})
    cm_miss = gen(); bs[cm_miss] = mk("looks_costume",
        fields={"COSTUME":["miss", None]}, shadow=True)
    sw_miss = gen(); bs[sw_miss] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cm_miss]})
    bs[cm_miss]["parent"] = sw_miss
    chain([(bc_m,bs[bc_m]),(set_ns1_miss,bs[set_ns1_miss]),(sw_miss,bs[sw_miss])])
    if_miss = gen(); bs[if_miss] = mk("control_if",
        inputs={"CONDITION":[2, cond_miss], "SUBSTACK":[2, bc_m]})
    bs[cond_miss]["parent"] = if_miss
    bs[bc_m]["parent"] = if_miss

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(set_y,bs[set_y]),(if_miss,bs[if_miss]),(wt,bs[wt])])

    # outer loop ends when 노트상태 = 1
    ns_v2 = vrep("노트상태", V_NSTATE)
    cond_done = cmp_op("operator_equals", ns_v2, 1)
    fall_loop = gen(); bs[fall_loop] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_done], "SUBSTACK":[2, set_y]})
    bs[cond_done]["parent"] = fall_loop
    bs[set_y]["parent"] = fall_loop

    # after loop: small visual hold, then delete clone
    hold = gen(); bs[hold] = mk("control_wait", inputs={"DURATION": num(0.18)})
    hide_b = gen(); bs[hide_b] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    seq = [(ch,bs[ch]),(snap_lane,bs[snap_lane]),(snap_targ,bs[snap_targ]),
           (set_ns,bs[set_ns]),(set_costume,bs[set_costume])]
    for ifb in lane_if_blocks:
        seq.append((ifb, bs[ifb]))
    seq += [(sety,bs[sety]),(show,bs[show]),(front_b,bs[front_b]),
            (fall_loop,bs[fall_loop]),(hold,bs[hold]),(hide_b,bs[hide_b]),(delc,bs[delc])]
    chain(seq)

    # ----- when receive 키입력: judge -----
    kh = gen(); bs[kh] = mk("event_whenbroadcastreceived", top=True, x=400, y=200,
        fields={"BROADCAST_OPTION":["키입력", BR_KEY]})

    # Only run if this clone's lane matches and not yet judged.
    lv = vrep("레인", V_LANE); hk_v = vrep("눌린레인", V_HITKEY)
    cond_same_lane = cmp_op("operator_equals", lv, hk_v)
    ns_v3 = vrep("노트상태", V_NSTATE)
    cond_unjudged = cmp_op("operator_equals", ns_v3, 0)
    cond_eligible = bool_op("operator_and", cond_same_lane, cond_unjudged)

    # diff = abs(V_TIME - target)
    time_v3 = vrep("곡시간", V_TIME)
    target_v3 = vrep("목표시각", V_TARGET)
    diff_raw = op("operator_subtract", time_v3, target_v3)
    diff_abs_id = gen()
    bs[diff_abs_id] = mk("operator_mathop",
        inputs={"NUM": slot(diff_raw)}, fields={"OPERATOR":["abs", None]})
    bs[diff_raw]["parent"] = diff_abs_id

    # if diff <= WIN_PERFECT → perfect
    cond_perf = cmp_op("operator_lt", diff_abs_id, WIN_PERFECT + 0.0001)
    # perfect body
    bm_p = gen(); bs[bm_p] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION":["판정_퍼펙트", BR_HIT_P]}, shadow=True)
    bc_p = gen(); bs[bc_p] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_p]})
    bs[bm_p]["parent"] = bc_p
    cm_p = gen(); bs[cm_p] = mk("looks_costume",
        fields={"COSTUME":["perfect", None]}, shadow=True)
    sw_p = gen(); bs[sw_p] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cm_p]})
    bs[cm_p]["parent"] = sw_p
    set_ns_p = gen(); bs[set_ns_p] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE":["노트상태", V_NSTATE]})
    chain([(bc_p,bs[bc_p]),(sw_p,bs[sw_p]),(set_ns_p,bs[set_ns_p])])

    # else if diff <= WIN_GOOD → good
    # Build a second instance of the abs (Scratch doesn't reuse reporters across positions)
    time_v4 = vrep("곡시간", V_TIME)
    target_v4 = vrep("목표시각", V_TARGET)
    diff_raw2 = op("operator_subtract", time_v4, target_v4)
    diff_abs_id2 = gen()
    bs[diff_abs_id2] = mk("operator_mathop",
        inputs={"NUM": slot(diff_raw2)}, fields={"OPERATOR":["abs", None]})
    bs[diff_raw2]["parent"] = diff_abs_id2
    cond_good = cmp_op("operator_lt", diff_abs_id2, WIN_GOOD + 0.0001)

    bm_g = gen(); bs[bm_g] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION":["판정_굿", BR_HIT_G]}, shadow=True)
    bc_g = gen(); bs[bc_g] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_g]})
    bs[bm_g]["parent"] = bc_g
    cm_g = gen(); bs[cm_g] = mk("looks_costume",
        fields={"COSTUME":["good", None]}, shadow=True)
    sw_g = gen(); bs[sw_g] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, cm_g]})
    bs[cm_g]["parent"] = sw_g
    set_ns_g = gen(); bs[set_ns_g] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE":["노트상태", V_NSTATE]})
    chain([(bc_g,bs[bc_g]),(sw_g,bs[sw_g]),(set_ns_g,bs[set_ns_g])])

    # else: too early — do nothing (let the note keep falling).
    # Nested if/else: outer = if cond_perf {perfect} else {if cond_good {good}}.
    if_good = gen(); bs[if_good] = mk("control_if",
        inputs={"CONDITION":[2, cond_good], "SUBSTACK":[2, bc_g]})
    bs[cond_good]["parent"] = if_good; bs[bc_g]["parent"] = if_good

    if_else_pg = gen(); bs[if_else_pg] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_perf],
                "SUBSTACK":[2, bc_p],
                "SUBSTACK2":[2, if_good]})
    bs[cond_perf]["parent"] = if_else_pg
    bs[bc_p]["parent"] = if_else_pg
    bs[if_good]["parent"] = if_else_pg

    # outer if: only run the judge logic if this clone is the matching lane & unjudged
    if_eligible = gen(); bs[if_eligible] = mk("control_if",
        inputs={"CONDITION":[2, cond_eligible], "SUBSTACK":[2, if_else_pg]})
    bs[cond_eligible]["parent"] = if_eligible
    bs[if_else_pg]["parent"] = if_eligible

    chain([(kh,bs[kh]),(if_eligible,bs[if_eligible])])

    return bs

# ======================================================================
#  RESULT banner blocks
# ======================================================================
def build_result_blocks():
    bs = {}
    (vrep, lrep, op, unary, cmp_op, bool_op,
     list_item, list_length, list_replace, list_add, list_delete_all) = make_helpers(bs)

    # when flag clicked → hide, center, wait for state=1 then state=0
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})

    # wait until state = 1 (game actually starts) — guards restart re-trigger
    sv1 = vrep("게임상태", V_STATE)
    cond_one = cmp_op("operator_equals", sv1, 1)
    wait_start = gen(); bs[wait_start] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_one]})
    bs[cond_one]["parent"] = wait_start

    # wait until state = 0
    sv2 = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", sv2, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_zero]})
    bs[cond_zero]["parent"] = wait_over

    show = gen(); bs[show] = mk("looks_show")
    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front]),
           (wait_start,bs[wait_start]),(wait_over,bs[wait_over]),(show,bs[show])])
    return bs

# ======================================================================
#  ASSEMBLE PROJECT
# ======================================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # ----- write SVGs -----
    def save_svg(content):
        m = md5_bytes(content.encode("utf-8"))
        path = f"{WORK}/{m}.svg"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return m

    bg_md5 = save_svg(BG_SVG)
    n_norm_md5 = save_svg(NOTE_NORMAL)
    n_perf_md5 = save_svg(NOTE_PERFECT)
    n_good_md5 = save_svg(NOTE_GOOD)
    n_miss_md5 = save_svg(NOTE_MISS)
    result_md5 = save_svg(RESULT_SVG)

    # ----- write SVG copies for assets/ folder (for inspection) -----
    os.makedirs(ASSETS, exist_ok=True)
    with open(f"{ASSETS}/background.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)
    with open(f"{ASSETS}/note_normal.svg", "w", encoding="utf-8") as f:
        f.write(NOTE_NORMAL)
    with open(f"{ASSETS}/note_perfect.svg", "w", encoding="utf-8") as f:
        f.write(NOTE_PERFECT)
    with open(f"{ASSETS}/note_good.svg", "w", encoding="utf-8") as f:
        f.write(NOTE_GOOD)
    with open(f"{ASSETS}/note_miss.svg", "w", encoding="utf-8") as f:
        f.write(NOTE_MISS)
    with open(f"{ASSETS}/result.svg", "w", encoding="utf-8") as f:
        f.write(RESULT_SVG)

    # ----- generate audio -----
    print("Synthesizing tick.wav...")
    tick_samples = gen_tick_wav()
    tick_path = f"{ASSETS}/tick.wav"
    write_wav(tick_path, tick_samples)
    with open(tick_path, "rb") as f: tick_bytes = f.read()
    tick_md5 = md5_bytes(tick_bytes)
    with open(f"{WORK}/{tick_md5}.wav", "wb") as f: f.write(tick_bytes)

    print("Synthesizing miss.wav...")
    miss_samples = gen_miss_wav()
    miss_path = f"{ASSETS}/miss.wav"
    write_wav(miss_path, miss_samples)
    with open(miss_path, "rb") as f: miss_bytes = f.read()
    miss_md5 = md5_bytes(miss_bytes)
    with open(f"{WORK}/{miss_md5}.wav", "wb") as f: f.write(miss_bytes)

    print(f"Synthesizing bgm.wav... (~{END_T:.1f}s)")
    bgm_samples = gen_bgm_wav()
    bgm_path = f"{ASSETS}/bgm.wav"
    write_wav(bgm_path, bgm_samples)
    with open(bgm_path, "rb") as f: bgm_bytes = f.read()
    bgm_md5 = md5_bytes(bgm_bytes)
    with open(f"{WORK}/{bgm_md5}.wav", "wb") as f: f.write(bgm_bytes)
    print(f"  bgm.wav: {len(bgm_bytes)//1024} KB, {len(bgm_samples)} samples")

    # ----- build block dicts -----
    stage_blocks = build_stage_blocks()
    note_blocks  = build_note_blocks()
    result_blocks = build_result_blocks()

    def snd_entry(name, md5, sample_count):
        return {
            "name": name, "assetId": md5, "dataFormat": "wav",
            "format": "", "rate": SAMPLE_RATE, "sampleCount": sample_count,
            "md5ext": f"{md5}.wav"
        }

    stage_sounds = [
        snd_entry("tick", tick_md5, len(tick_samples)),
        snd_entry("miss", miss_md5, len(miss_samples)),
        snd_entry("bgm",  bgm_md5,  len(bgm_samples)),
    ]

    # The Note sprite doesn't need sounds; the result sprite doesn't either.
    # But Scratch requires the SOUND_MENU shadows on hit broadcasts to reference
    # sounds in the *current sprite*. All our sound_play calls are on the Stage,
    # so giving sounds only to the stage is sufficient.

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:     ["점수", 0],
            V_COMBO:     ["콤보", 0],
            V_MAX_COMBO: ["최대콤보", 0],
            V_TIME:      ["곡시간", 0],
            V_STATE:     ["게임상태", 1],
            V_AUDIO_OFF: ["오디오오프셋", 0.0],
            V_JUDGE_TXT: ["판정", "Ready..."],
            V_SPAWN_I:   ["스폰_i", 1],
            V_HITKEY:    ["눌린레인", 0],
            V_NEXT_LANE: ["다음레인", 1],
            V_NEXT_TARG: ["다음목표", 0],
        },
        "lists": {
            L_NOTE_T: ["채보시각", []],
            L_NOTE_L: ["채보레인", []],
        },
        "broadcasts": {
            BR_START: "게임시작", BR_END: "게임종료",
            BR_KEY: "키입력",
            BR_HIT_P: "판정_퍼펙트", BR_HIT_G: "판정_굿", BR_MISS: "판정_미스",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "stage", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": stage_sounds,
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    note_sprite = {
        "isStage": False, "name": "음표",
        "variables": {
            V_LANE:   ["레인", 1],
            V_TARGET: ["목표시각", 0],
            V_NSTATE: ["노트상태", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": note_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "normal",  "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": n_norm_md5, "md5ext": f"{n_norm_md5}.svg",
             "rotationCenterX": 28, "rotationCenterY": 12},
            {"name": "perfect", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": n_perf_md5, "md5ext": f"{n_perf_md5}.svg",
             "rotationCenterX": 28, "rotationCenterY": 12},
            {"name": "good",    "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": n_good_md5, "md5ext": f"{n_good_md5}.svg",
             "rotationCenterX": 28, "rotationCenterY": 12},
            {"name": "miss",    "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": n_miss_md5, "md5ext": f"{n_miss_md5}.svg",
             "rotationCenterX": 28, "rotationCenterY": 12},
        ],
        "sounds": [],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 110, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    result = {
        "isStage": False, "name": "결과",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": result_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": result_md5, "md5ext": f"{result_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 100
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_SCORE, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10000, "isDiscrete": True},
        {"id": V_COMBO, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "콤보"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 55,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_MAX_COMBO, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "최대콤보"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 110,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_JUDGE_TXT, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "판정"}, "spriteName": None,
         "value": "Ready...", "width": 0, "height": 0, "x": 330, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_TIME, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "곡시간"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 330, "y": 70,
         "visible": False, "sliderMin": 0, "sliderMax": 100, "isDiscrete": False},
        {"id": V_AUDIO_OFF, "mode": "slider", "opcode": "data_variable",
         "params": {"VARIABLE": "오디오오프셋"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 330, "y": 105,
         "visible": False, "sliderMin": -0.5, "sliderMax": 0.5, "isDiscrete": False},
    ]

    project = {
        "targets": [stage, note_sprite, result],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "beat-tap-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # sanity: re-read project.json
    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)

    size = os.path.getsize(OUTPUT)
    print(f"✓ wrote {OUTPUT} ({size//1024} KB, {len(NOTES)} notes, song ends at t={END_T:.1f}s)")

if __name__ == "__main__":
    main()
