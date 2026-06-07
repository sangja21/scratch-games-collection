#!/usr/bin/env python3
"""Whack-a-Prime: pop up moles holding numbers 1~100, smack only the primes."""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "두더지_소수잡기.sb3")

# -------- Background SVG (480x360): sky + grass + 6 holes --------
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FFE0B2"/>
      <stop offset="100%" stop-color="#FFD180"/>
    </linearGradient>
    <linearGradient id="grass" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#7CB342"/>
      <stop offset="100%" stop-color="#33691E"/>
    </linearGradient>
    <radialGradient id="hole" cx="0.5" cy="0.4" r="0.55">
      <stop offset="0%"   stop-color="#1B0A05"/>
      <stop offset="60%"  stop-color="#3E2723"/>
      <stop offset="100%" stop-color="#5D4037"/>
    </radialGradient>
  </defs>
  <rect width="480" height="130" fill="url(#sky)"/>
  <circle cx="80" cy="55" r="22" fill="#FFD54F" opacity="0.95"/>
  <circle cx="80" cy="55" r="32" fill="#FFD54F" opacity="0.25"/>
  <path d="M 0 130 Q 100 100 200 120 T 480 115 L 480 140 L 0 140 Z" fill="#A1887F" opacity="0.55"/>
  <rect y="130" width="480" height="230" fill="url(#grass)"/>
  <g>
    <ellipse cx="80"  cy="205" rx="38" ry="13" fill="url(#hole)"/>
    <ellipse cx="240" cy="205" rx="38" ry="13" fill="url(#hole)"/>
    <ellipse cx="400" cy="205" rx="38" ry="13" fill="url(#hole)"/>
    <ellipse cx="80"  cy="305" rx="38" ry="13" fill="url(#hole)"/>
    <ellipse cx="240" cy="305" rx="38" ry="13" fill="url(#hole)"/>
    <ellipse cx="400" cy="305" rx="38" ry="13" fill="url(#hole)"/>
  </g>
  <g stroke="#558B2F" stroke-width="1.5" fill="none">
    <path d="M 30 175 Q 35 158 40 175"/>
    <path d="M 150 195 Q 155 178 160 195"/>
    <path d="M 320 175 Q 325 158 330 175"/>
    <path d="M 440 190 Q 445 173 450 190"/>
    <path d="M 130 270 Q 135 253 140 270"/>
    <path d="M 350 280 Q 355 263 360 280"/>
    <path d="M 200 340 Q 205 323 210 340"/>
    <path d="M 60 335 Q 65 318 70 335"/>
  </g>
</svg>"""

# -------- Mole SVG costumes --------
# Costume 0: hidden (just hat, barely peeking out)
MOLE_PEEK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <defs>
    <radialGradient id="body" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0%"   stop-color="#8D6E63"/>
      <stop offset="100%" stop-color="#5D4037"/>
    </radialGradient>
  </defs>
  <!-- Only top of head visible (peeking) -->
  <ellipse cx="30" cy="54" rx="22" ry="20" fill="url(#body)" stroke="#3E2723" stroke-width="1.5"/>
  <ellipse cx="30" cy="38" rx="9" ry="4" fill="#4E342E" opacity="0.6"/>
</svg>"""

# Costume 1: half emerged
MOLE_HALF_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <defs>
    <radialGradient id="body" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0%"   stop-color="#8D6E63"/>
      <stop offset="100%" stop-color="#5D4037"/>
    </radialGradient>
  </defs>
  <!-- Half body visible -->
  <ellipse cx="30" cy="44" rx="22" ry="20" fill="url(#body)" stroke="#3E2723" stroke-width="1.5"/>
  <ellipse cx="30" cy="28" rx="9" ry="4" fill="#4E342E" opacity="0.6"/>
  <circle cx="22" cy="42" r="4.5" fill="#FFFFFF"/>
  <circle cx="38" cy="42" r="4.5" fill="#FFFFFF"/>
  <circle cx="23" cy="43" r="2.5" fill="#1A1A1A"/>
  <circle cx="39" cy="43" r="2.5" fill="#1A1A1A"/>
  <circle cx="23.5" cy="42" r="0.8" fill="#FFFFFF"/>
  <circle cx="39.5" cy="42" r="0.8" fill="#FFFFFF"/>
</svg>"""

# Costume 2: fully emerged
MOLE_FULL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <defs>
    <radialGradient id="body" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0%"   stop-color="#8D6E63"/>
      <stop offset="100%" stop-color="#5D4037"/>
    </radialGradient>
  </defs>
  <ellipse cx="30" cy="34" rx="22" ry="20" fill="url(#body)" stroke="#3E2723" stroke-width="1.5"/>
  <ellipse cx="30" cy="20" rx="9" ry="4" fill="#4E342E" opacity="0.6"/>
  <circle cx="22" cy="32" r="4.5" fill="#FFFFFF"/>
  <circle cx="38" cy="32" r="4.5" fill="#FFFFFF"/>
  <circle cx="23" cy="33" r="2.5" fill="#1A1A1A"/>
  <circle cx="39" cy="33" r="2.5" fill="#1A1A1A"/>
  <circle cx="23.5" cy="32" r="0.8" fill="#FFFFFF"/>
  <circle cx="39.5" cy="32" r="0.8" fill="#FFFFFF"/>
  <ellipse cx="30" cy="42" rx="4" ry="3" fill="#FF8A80" stroke="#C62828" stroke-width="0.8"/>
  <line x1="20" y1="44" x2="12" y2="42" stroke="#1A1A1A" stroke-width="0.7"/>
  <line x1="20" y1="46" x2="12" y2="46" stroke="#1A1A1A" stroke-width="0.7"/>
  <line x1="40" y1="44" x2="48" y2="42" stroke="#1A1A1A" stroke-width="0.7"/>
  <line x1="40" y1="46" x2="48" y2="46" stroke="#1A1A1A" stroke-width="0.7"/>
  <path d="M 26 47 Q 30 50 34 47" stroke="#1A1A1A" stroke-width="1.2" fill="none"/>
  <ellipse cx="30" cy="13" rx="6" ry="3" fill="#A1887F" opacity="0.5"/>
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
V_SCORE = "varScore001"
V_TIME  = "varTime002"
V_STATE = "varState003"   # 1 = playing, 0 = over
V_NUM   = "varNum004"     # shared (set at clone-start then immediately used)
V_HX    = "varHX005"      # shared hole x (set at clone-start)
V_HY    = "varHY006"      # shared hole y (set at clone-start)
V_PRIME = "varPrime007"   # shared (used as temp during isPrime computation)
V_HOLE_N = "varHoleN008"  # shared hole number (set at clone-start)

# List IDs: L_PRIME_MAP[hole_index 1..6] = isPrime for the active clone in that hole
# L_USED_HOLES: list of currently occupied hole numbers (for exclusivity check)
L_PRIME_MAP  = "listPrime001"
L_USED_HOLES = "listUsed002"

BR_START = "brStart001"
BR_END   = "brEnd002"

# -------- per-target block builders --------
# Each builder closes over a fresh `bs` dict + helpers.

def make_helpers(bs):
    def vrep(name, vid):
        bid = gen()
        bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid
    def lrep(name, lid):
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
    def bool_op(opcode, a, b_):
        bid = gen()
        bs[bid] = mk(opcode, inputs={"OPERAND1": [2, a], "OPERAND2": [2, b_]})
        bs[a]["parent"] = bid
        bs[b_]["parent"] = bid
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
    return vrep, lrep, op, bool_op, cmp_op

def make_join(bs, a_bid, b_text):
    """Join block: STRING1=a_bid(block ref), STRING2=text_lit"""
    bid = gen()
    bs[bid] = mk("operator_join",
        inputs={"STRING1": slot(a_bid, sk=10, sv=""),
                "STRING2": text_lit(b_text)[1]})
    bs[a_bid]["parent"] = bid
    # STRING2 is an inline literal, no block to reparent
    return bid

# ---------------- STAGE blocks ----------------
def build_stage_blocks():
    bs = {}
    vrep, lrep, op, bool_op, cmp_op = make_helpers(bs)

    # === when flag clicked: init game ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    s_score = gen(); bs[s_score] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["점수", V_SCORE]})
    s_time = gen(); bs[s_time] = mk("data_setvariableto",
        inputs={"VALUE": num(60)}, fields={"VARIABLE": ["시간", V_TIME]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bcast = gen(); bs[bcast] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm]})
    bs[bm]["parent"] = bcast
    chain([(h,bs[h]),(s_score,bs[s_score]),(s_time,bs[s_time]),
           (s_state,bs[s_state]),(bcast,bs[bcast])])

    # === when received 게임시작: 1-second countdown ===
    th = gen(); bs[th] = mk("event_whenbroadcastreceived", top=True, x=20, y=300,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # repeat-until 시간 = 0
    rt_var = vrep("시간", V_TIME)
    cond_zero = cmp_op("operator_equals", rt_var, 0)

    wt1 = gen(); bs[wt1] = mk("control_wait", inputs={"DURATION": num(1)})
    chg = gen(); bs[chg] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["시간", V_TIME]})
    chain([(wt1,bs[wt1]),(chg,bs[chg])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_zero], "SUBSTACK":[2, wt1]})
    bs[cond_zero]["parent"] = rep_until
    bs[wt1]["parent"] = rep_until

    # after timer: state = 0, broadcast 게임종료
    set_over = gen(); bs[set_over] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bm2 = gen(); bs[bm2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임종료", BR_END]}, shadow=True)
    bcast2 = gen(); bs[bcast2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm2]})
    bs[bm2]["parent"] = bcast2

    chain([(th,bs[th]),(rep_until,bs[rep_until]),(set_over,bs[set_over]),(bcast2,bs[bcast2])])

    # === when received 게임종료: show Game Over + final score ===
    # [FIX-WARN] Stage now handles game-over broadcast to show result screen
    eh = gen(); bs[eh] = mk("event_whenbroadcastreceived", top=True, x=400, y=300,
        fields={"BROADCAST_OPTION": ["게임종료", BR_END]})

    # Build join block: "Game Over! 점수: " + 점수_var
    score_var = vrep("점수", V_SCORE)
    join_bid = gen()
    bs[join_bid] = mk("operator_join",
        inputs={"STRING1": [1, [10, "Game Over!  점수: "]],
                "STRING2": slot(score_var, sk=10, sv="0")})
    bs[score_var]["parent"] = join_bid

    say_over = gen(); bs[say_over] = mk("looks_sayforsecs",
        inputs={"MESSAGE": slot(join_bid, sk=10, sv=""), "SECS": num(5)})
    bs[join_bid]["parent"] = say_over

    chain([(eh,bs[eh]),(say_over,bs[say_over])])

    return bs

# ---------------- helper: build isPrime blocks for a number variable --------
# Appends blocks to bs; returns (set_prime1, [if_lt2, div_ifs...]) for sequencing.
# The computation reads V_NUM then sets V_PRIME to 1 or 0.
def build_isprime_blocks(bs):
    """Build the isPrime computation sequence blocks.
    Returns list of (bid, block) tuples to be inserted into a chain.
    Reads V_NUM, writes V_PRIME.
    """
    vrep, lrep, op, bool_op, cmp_op = make_helpers(bs)

    seq = []

    # isPrime = 1
    set_p1 = gen(); bs[set_p1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["isPrime", V_PRIME]})
    seq.append((set_p1, bs[set_p1]))

    # if 숫자 < 2: isPrime = 0
    nv1 = vrep("숫자", V_NUM)
    cond_lt2 = cmp_op("operator_lt", nv1, 2)
    set_p0_a = gen(); bs[set_p0_a] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["isPrime", V_PRIME]})
    if_lt2 = gen(); bs[if_lt2] = mk("control_if",
        inputs={"CONDITION":[2, cond_lt2], "SUBSTACK":[2, set_p0_a]})
    bs[cond_lt2]["parent"] = if_lt2
    bs[set_p0_a]["parent"] = if_lt2
    seq.append((if_lt2, bs[if_lt2]))

    # "if 숫자 > p AND 숫자 mod p = 0: isPrime = 0" for p in [2,3,5,7]
    for p in [2, 3, 5, 7]:
        nv_a = vrep("숫자", V_NUM)
        gt_p = cmp_op("operator_gt", nv_a, p)
        nv_b = vrep("숫자", V_NUM)
        mod_p = op("operator_mod", nv_b, p)
        eq_zero = cmp_op("operator_equals", mod_p, 0)
        bs[mod_p]["parent"] = eq_zero
        and_b = bool_op("operator_and", gt_p, eq_zero)
        sp0 = gen(); bs[sp0] = mk("data_setvariableto",
            inputs={"VALUE": num(0)}, fields={"VARIABLE": ["isPrime", V_PRIME]})
        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION":[2, and_b], "SUBSTACK":[2, sp0]})
        bs[and_b]["parent"] = ifb
        bs[sp0]["parent"] = ifb
        seq.append((ifb, bs[ifb]))

    return seq

# ---------------- MOLE blocks ----------------
def build_mole_blocks():
    bs = {}
    vrep, lrep, op, bool_op, cmp_op = make_helpers(bs)

    # Mole pop-up positions: shifted +46px above each hole center so the mole's
    # bottom edge sits at the hole's top rim (mole height = 60·1.1 = 66, half = 33;
    # hole ry = 13). This keeps the mole entirely on the green grass and out of
    # the dark hole gradient — fixes the "mole hidden by hole" issue.
    # Hole centers in SVG: (80|240|400, 205|305) → Scratch (svgx-240, 180-svgy)
    holes = [
        (-160,   21),  # 1: top-left   (hole center y -25 + 46)
        (   0,   21),  # 2: top-mid
        ( 160,   21),  # 3: top-right
        (-160,  -79),  # 4: bot-left   (hole center y -125 + 46)
        (   0,  -79),  # 5: bot-mid
        ( 160,  -79),  # 6: bot-right
    ]

    # === when flag clicked: hide + init lists ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(110)})

    # [FIX-INFO] Initialize both lists with 6 zeros (one slot per hole, index=hole number)
    # 소수맵[i] = isPrime for the active clone in hole i
    # 사용중인굴[i] = 1 if hole i is occupied, 0 if free
    del_pm = gen(); bs[del_pm] = mk("data_deletealloflist",
        fields={"LIST": ["소수맵", L_PRIME_MAP]})
    del_uh = gen(); bs[del_uh] = mk("data_deletealloflist",
        fields={"LIST": ["사용중인굴", L_USED_HOLES]})

    # Add 6 initial 0 entries to each list
    add_blocks = []
    for _ in range(6):
        ab = gen(); bs[ab] = mk("data_addtolist",
            inputs={"ITEM": num(0)}, fields={"LIST": ["소수맵", L_PRIME_MAP]})
        add_blocks.append((ab, bs[ab]))
    for _ in range(6):
        ab = gen(); bs[ab] = mk("data_addtolist",
            inputs={"ITEM": num(0)}, fields={"LIST": ["사용중인굴", L_USED_HOLES]})
        add_blocks.append((ab, bs[ab]))

    init_seq = [(h,bs[h]),(hi,bs[hi]),(sz,bs[sz]),(del_pm,bs[del_pm]),(del_uh,bs[del_uh])]
    init_seq += add_blocks
    chain(init_seq)

    # === when received 게임시작: spawn loop ===
    sh = gen(); bs[sh] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # repeat-until 게임상태 = 0:
    state_var = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_var, 0)

    # body: create clone of self, wait random 0.5~1.0
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    rand_wait = op("operator_random", 0.5, 1.0, key1="FROM", key2="TO")
    wclone = gen(); bs[wclone] = mk("control_wait", inputs={"DURATION": slot(rand_wait)})
    bs[rand_wait]["parent"] = wclone
    chain([(cclone,bs[cclone]),(wclone,bs[wclone])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_over], "SUBSTACK":[2, cclone]})
    bs[cond_over]["parent"] = rep_until
    bs[cclone]["parent"] = rep_until

    chain([(sh,bs[sh]),(rep_until,bs[rep_until])])

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)

    # 숫자 = random 1~100
    rn = op("operator_random", 1, 100, key1="FROM", key2="TO")
    set_num = gen(); bs[set_num] = mk("data_setvariableto",
        inputs={"VALUE": slot(rn)}, fields={"VARIABLE": ["숫자", V_NUM]})
    bs[rn]["parent"] = set_num

    # [FIX-WARN] Compute isPrime NOW (while 숫자 is still this clone's number)
    # This avoids the shared-variable race: isPrime is computed in the same
    # script tick as setting 숫자, before any other clone can overwrite 숫자.
    isprime_seq = build_isprime_blocks(bs)

    # [FIX-INFO] Hole exclusivity: pick a hole where 사용중인굴[hole] = 0 (free).
    # 사용중인굴 is a fixed 6-slot boolean array (0=free, 1=occupied), index=hole number.
    # repeat-until loop: pick random hole; exit when 사용중인굴[굴번호] = 0
    rh = op("operator_random", 1, 6, key1="FROM", key2="TO")
    set_hole_init = gen(); bs[set_hole_init] = mk("data_setvariableto",
        inputs={"VALUE": slot(rh)}, fields={"VARIABLE": ["굴번호", V_HOLE_N]})
    bs[rh]["parent"] = set_hole_init

    # condition: item 굴번호 of 사용중인굴 = 0  (hole is free)
    hn_var = vrep("굴번호", V_HOLE_N)
    item_used = gen(); bs[item_used] = mk("data_itemoflist",
        inputs={"INDEX": slot(hn_var)},
        fields={"LIST": ["사용중인굴", L_USED_HOLES]})
    bs[hn_var]["parent"] = item_used

    cond_free = cmp_op("operator_equals", item_used, 0)
    bs[item_used]["parent"] = cond_free

    # loop body: re-roll
    rh2 = op("operator_random", 1, 6, key1="FROM", key2="TO")
    reroll = gen(); bs[reroll] = mk("data_setvariableto",
        inputs={"VALUE": slot(rh2)}, fields={"VARIABLE": ["굴번호", V_HOLE_N]})
    bs[rh2]["parent"] = reroll

    hole_pick_loop = gen(); bs[hole_pick_loop] = mk("control_repeat_until",
        inputs={"CONDITION":[2, cond_free], "SUBSTACK":[2, reroll]})
    bs[cond_free]["parent"] = hole_pick_loop
    bs[reroll]["parent"] = hole_pick_loop

    # Mark this hole as occupied: replace item 굴번호 of 사용중인굴 with 1
    hn_var2 = vrep("굴번호", V_HOLE_N)
    mark_used = gen(); bs[mark_used] = mk("data_replaceitemoflist",
        inputs={"INDEX": slot(hn_var2), "ITEM": num(1)},
        fields={"LIST": ["사용중인굴", L_USED_HOLES]})
    bs[hn_var2]["parent"] = mark_used

    # [FIX-WARN] Store computed isPrime in L_PRIME_MAP at index 굴번호
    # replace item 굴번호 of 소수맵 with isPrime
    pv_store = vrep("isPrime", V_PRIME)
    hn_idx = vrep("굴번호", V_HOLE_N)
    replace_prime = gen(); bs[replace_prime] = mk("data_replaceitemoflist",
        inputs={"INDEX": slot(hn_idx), "ITEM": slot(pv_store, sk=10, sv="0")},
        fields={"LIST": ["소수맵", L_PRIME_MAP]})
    bs[pv_store]["parent"] = replace_prime
    bs[hn_idx]["parent"] = replace_prime

    # 6 if-blocks setting 굴X, 굴Y from hole number
    hole_if_blocks = []
    for i, (hx, hy) in enumerate(holes, start=1):
        hole_var = vrep("굴번호", V_HOLE_N)
        eq = cmp_op("operator_equals", hole_var, i)
        sx = gen(); bs[sx] = mk("data_setvariableto",
            inputs={"VALUE": num(hx)}, fields={"VARIABLE": ["굴X", V_HX]})
        sy = gen(); bs[sy] = mk("data_setvariableto",
            inputs={"VALUE": num(hy)}, fields={"VARIABLE": ["굴Y", V_HY]})
        chain([(sx,bs[sx]),(sy,bs[sy])])
        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION":[2, eq], "SUBSTACK":[2, sx]})
        bs[eq]["parent"] = ifb
        bs[sx]["parent"] = ifb
        hole_if_blocks.append(ifb)

    # go to (굴X, 굴Y) at pop position (above hole, on grass)
    hxv = vrep("굴X", V_HX); hyv = vrep("굴Y", V_HY)
    g_pop = gen(); bs[g_pop] = mk("motion_gotoxy",
        inputs={"X": slot(hxv), "Y": slot(hyv)})
    bs[hxv]["parent"] = g_pop; bs[hyv]["parent"] = g_pop

    # [FIX-INFO] Pop-up animation: switch costumes peek→half→full
    sw_peek = gen(); bs[sw_peek] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, [10, "두더지_peek"]]})
    w_anim1 = gen(); bs[w_anim1] = mk("control_wait", inputs={"DURATION": num(0.1)})
    sw_half = gen(); bs[sw_half] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, [10, "두더지_half"]]})
    w_anim2 = gen(); bs[w_anim2] = mk("control_wait", inputs={"DURATION": num(0.1)})
    sw_full = gen(); bs[sw_full] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, [10, "두더지_full"]]})

    show = gen(); bs[show] = mk("looks_show")

    # say 숫자 (persistent until cleared)
    nvar = vrep("숫자", V_NUM)
    say_blk = gen(); bs[say_blk] = mk("looks_say",
        inputs={"MESSAGE": slot(nvar, sk=10, sv="")})
    bs[nvar]["parent"] = say_blk

    # stay visible for 1.3 sec (minus animation time 0.2s already spent)
    wstay = gen(); bs[wstay] = mk("control_wait", inputs={"DURATION": num(1.1)})

    # [FIX-INFO] Pop-down: switch back to peek before hiding
    sw_half2 = gen(); bs[sw_half2] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, [10, "두더지_half"]]})
    w_anim3 = gen(); bs[w_anim3] = mk("control_wait", inputs={"DURATION": num(0.1)})
    sw_peek2 = gen(); bs[sw_peek2] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, [10, "두더지_peek"]]})
    w_anim4 = gen(); bs[w_anim4] = mk("control_wait", inputs={"DURATION": num(0.1)})

    # clear bubble + hide + remove from used holes + delete
    say_clear = gen(); bs[say_clear] = mk("looks_say",
        inputs={"MESSAGE": text_lit("")})
    hide_c = gen(); bs[hide_c] = mk("looks_hide")

    # [FIX-INFO] Free hole on clone timeout end: replace item 굴번호 with 0
    hn_del = vrep("굴번호", V_HOLE_N)
    free_used = gen(); bs[free_used] = mk("data_replaceitemoflist",
        inputs={"INDEX": slot(hn_del), "ITEM": num(0)},
        fields={"LIST": ["사용중인굴", L_USED_HOLES]})
    bs[hn_del]["parent"] = free_used

    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    # Chain clone start
    seq = [(ch,bs[ch]),(set_num,bs[set_num])]
    seq += isprime_seq
    seq += [(set_hole_init,bs[set_hole_init]),(hole_pick_loop,bs[hole_pick_loop]),
            (mark_used,bs[mark_used]),(replace_prime,bs[replace_prime])]
    for ifb in hole_if_blocks:
        seq.append((ifb, bs[ifb]))
    seq += [(g_pop,bs[g_pop]),
            (sw_peek,bs[sw_peek]),(w_anim1,bs[w_anim1]),
            (sw_half,bs[sw_half]),(w_anim2,bs[w_anim2]),
            (sw_full,bs[sw_full]),
            (show,bs[show]),(say_blk,bs[say_blk]),
            (wstay,bs[wstay]),
            (sw_half2,bs[sw_half2]),(w_anim3,bs[w_anim3]),
            (sw_peek2,bs[sw_peek2]),(w_anim4,bs[w_anim4]),
            (say_clear,bs[say_clear]),(hide_c,bs[hide_c]),
            (free_used,bs[free_used]),(delc,bs[delc])]
    chain(seq)

    # === when this sprite clicked ===
    cl = gen(); bs[cl] = mk("event_whenthisspriteclicked", top=True, x=900, y=20)

    # [FIX-WARN] Read isPrime from L_PRIME_MAP using THIS clone's position.
    # Determine hole index from (x position, y position) - truly clone-local values.
    # For each hole i: if x_pos=hx AND y_pos=hy:
    #   set isPrime = item i of 소수맵
    #   replace item i of 사용중인굴 with 0  (free hole while we still know i)
    click_hole_ifs = []
    for i, (hx, hy) in enumerate(holes, start=1):
        # x position = hx
        xpos_bid = gen(); bs[xpos_bid] = mk("motion_xposition")
        eq_x = cmp_op("operator_equals", xpos_bid, hx)
        # y position = hy
        ypos_bid = gen(); bs[ypos_bid] = mk("motion_yposition")
        eq_y = cmp_op("operator_equals", ypos_bid, hy)
        # AND
        and_xy = bool_op("operator_and", eq_x, eq_y)

        # item i of 소수맵
        item_bid = gen(); bs[item_bid] = mk("data_itemoflist",
            inputs={"INDEX": num(i)},
            fields={"LIST": ["소수맵", L_PRIME_MAP]})

        # set isPrime = item i
        set_p_from_map = gen(); bs[set_p_from_map] = mk("data_setvariableto",
            inputs={"VALUE": slot(item_bid, sk=10, sv="0")},
            fields={"VARIABLE": ["isPrime", V_PRIME]})
        bs[item_bid]["parent"] = set_p_from_map

        # free hole i (index is literal, no shared-variable issue)
        free_hole_i = gen(); bs[free_hole_i] = mk("data_replaceitemoflist",
            inputs={"INDEX": num(i), "ITEM": num(0)},
            fields={"LIST": ["사용중인굴", L_USED_HOLES]})

        chain([(set_p_from_map, bs[set_p_from_map]), (free_hole_i, bs[free_hole_i])])

        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION":[2, and_xy], "SUBSTACK":[2, set_p_from_map]})
        bs[and_xy]["parent"] = ifb
        bs[set_p_from_map]["parent"] = ifb
        click_hole_ifs.append((ifb, bs[ifb]))

    # if isPrime = 1 -> 점수+=1, play pop, else 점수-=1
    pv = vrep("isPrime", V_PRIME)
    cond_prime = cmp_op("operator_equals", pv, 1)

    # Correct branch: 점수+=1, reset pitch, play pop (normal)
    inc = gen(); bs[inc] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    pitch_ok = gen(); bs[pitch_ok] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["PITCH", None]})
    snm_ok = gen(); bs[snm_ok] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_ok = gen(); bs[snd_ok] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_ok]})
    bs[snm_ok]["parent"] = snd_ok
    chain([(inc,bs[inc]),(pitch_ok,bs[pitch_ok]),(snd_ok,bs[snd_ok])])

    # Wrong branch: 점수-=1, lower pitch (deeper "thud"), play pop
    dec = gen(); bs[dec] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    pitch_no = gen(); bs[pitch_no] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT": ["PITCH", None]})
    snm_no = gen(); bs[snm_no] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_no = gen(); bs[snd_no] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_no]})
    bs[snm_no]["parent"] = snd_no
    chain([(dec,bs[dec]),(pitch_no,bs[pitch_no]),(snd_no,bs[snd_no])])

    if_else = gen(); bs[if_else] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_prime],
                "SUBSTACK":[2, inc], "SUBSTACK2":[2, dec]})
    bs[cond_prime]["parent"] = if_else
    bs[inc]["parent"] = if_else
    bs[dec]["parent"] = if_else

    say_clear2 = gen(); bs[say_clear2] = mk("looks_say",
        inputs={"MESSAGE": text_lit("")})
    hide_w = gen(); bs[hide_w] = mk("looks_hide")
    delc2 = gen(); bs[delc2] = mk("control_delete_this_clone")

    click_seq = [(cl,bs[cl])]
    click_seq += click_hole_ifs
    click_seq += [(if_else,bs[if_else]),(say_clear2,bs[say_clear2]),
                  (hide_w,bs[hide_w]),(delc2,bs[delc2])]
    chain(click_seq)

    return bs

# ---------------- assemble ----------------
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    peek_md5 = md5_bytes(MOLE_PEEK_SVG.encode("utf-8"))
    with open(f"{WORK}/{peek_md5}.svg", "w", encoding="utf-8") as f:
        f.write(MOLE_PEEK_SVG)

    half_md5 = md5_bytes(MOLE_HALF_SVG.encode("utf-8"))
    with open(f"{WORK}/{half_md5}.svg", "w", encoding="utf-8") as f:
        f.write(MOLE_HALF_SVG)

    full_md5 = md5_bytes(MOLE_FULL_SVG.encode("utf-8"))
    with open(f"{WORK}/{full_md5}.svg", "w", encoding="utf-8") as f:
        f.write(MOLE_FULL_SVG)

    pop_src = f"{ASSETS}/pop.wav"
    with open(pop_src, "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks = build_stage_blocks()
    mole_blocks  = build_mole_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE: ["점수", 0],
            V_TIME:  ["시간", 60],
            V_STATE: ["게임상태", 1],
        },
        "lists": {},
        "broadcasts": {BR_START: "게임시작", BR_END: "게임종료"},
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "풀밭", "dataFormat": "svg",
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

    mole = {
        "isStage": False, "name": "두더지",
        "variables": {
            V_NUM:    ["숫자", 0],
            V_HX:     ["굴X", 0],
            V_HY:     ["굴Y", 0],
            V_PRIME:  ["isPrime", 1],
            V_HOLE_N: ["굴번호", 1],
        },
        # [FIX-WARN/INFO] Lists for clone-safe isPrime map and hole exclusivity
        # Both are 6-slot arrays indexed by hole number (1..6).
        "lists": {
            L_PRIME_MAP:  ["소수맵",     [0,0,0,0,0,0]],
            L_USED_HOLES: ["사용중인굴", [0,0,0,0,0,0]],
        },
        "broadcasts": {},
        "blocks": mole_blocks, "comments": {},
        "currentCostume": 0,
        # [FIX-INFO] Three costumes for pop-up animation
        "costumes": [
            {
                "name": "두더지_peek", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": peek_md5, "md5ext": f"{peek_md5}.svg",
                "rotationCenterX": 30, "rotationCenterY": 30
            },
            {
                "name": "두더지_half", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": half_md5, "md5ext": f"{half_md5}.svg",
                "rotationCenterX": 30, "rotationCenterY": 30
            },
            {
                "name": "두더지_full", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": full_md5, "md5ext": f"{full_md5}.svg",
                "rotationCenterX": 30, "rotationCenterY": 30
            },
        ],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": -200, "size": 110, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_SCORE, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_TIME, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "시간"}, "spriteName": None,
         "value": 60, "width": 0, "height": 0, "x": 380, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 60, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, mole],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "whack-a-prime-builder"}
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

if __name__ == "__main__":
    main()
