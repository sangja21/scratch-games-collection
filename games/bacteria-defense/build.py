#!/usr/bin/env python3
"""Bacteria Defense — feel exponential growth + log base change.

The petri dish has one bacterium. Every V_T seconds every clone tries to
split — each becomes r copies (with fractional r handled probabilistically).
Click bacteria to kill them. HUD shows V_REMAIN = log_r(V_NMAX / V_N), which
is computed via change-of-base log_r(x) = log10(x)/log10(r) — the math
learning hook for this chapter (지수와 로그).
"""
import json, os, wave, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "박테리아_디펜스.sb3")

# ---------------------------------------------------------------------------
# SVG assets
# ---------------------------------------------------------------------------

# Petri-dish background (480x360): dark ring, soft agar gradient, HUD strip
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <radialGradient id="agar" cx="0.5" cy="0.55" r="0.55">
      <stop offset="0%"   stop-color="#F8E9C6"/>
      <stop offset="60%"  stop-color="#E9D5A1"/>
      <stop offset="100%" stop-color="#B89B66"/>
    </radialGradient>
    <linearGradient id="hud" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0F1A2E"/>
      <stop offset="100%" stop-color="#1B2745"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="#0B1020"/>
  <rect x="0" y="0" width="480" height="60" fill="url(#hud)"/>
  <g stroke="#2C3E66" stroke-width="0.6" opacity="0.7">
    <line x1="0" y1="60" x2="480" y2="60"/>
  </g>
  <text x="14" y="22" fill="#9FD7FF" font-family="Arial, Helvetica, sans-serif"
        font-size="13" font-weight="bold">박테리아 디펜스 — 지수와 로그</text>
  <text x="14" y="44" fill="#C5E8FF" font-family="Arial, Helvetica, sans-serif"
        font-size="11">개체수 N · 임계까지 = log_r(N_max/N) · r = 분열률</text>
  <text x="466" y="22" fill="#FFAB91" font-family="Arial, Helvetica, sans-serif"
        font-size="11" text-anchor="end">클릭으로 항생제 살포</text>
  <text x="466" y="44" fill="#FFE082" font-family="Arial, Helvetica, sans-serif"
        font-size="11" text-anchor="end">N >= N_max → 게임 오버</text>
  <circle cx="240" cy="215" r="135" fill="url(#agar)"
          stroke="#5A3E12" stroke-width="6"/>
  <circle cx="240" cy="215" r="135" fill="none"
          stroke="#3A2608" stroke-width="2" opacity="0.6"/>
  <g stroke="#9A7937" stroke-width="0.4" opacity="0.45" fill="none">
    <circle cx="240" cy="215" r="50"/>
    <circle cx="240" cy="215" r="80"/>
    <circle cx="240" cy="215" r="110"/>
    <line x1="115" y1="215" x2="365" y2="215"/>
    <line x1="240" y1="90"  x2="240" y2="340"/>
  </g>
  <g fill="#C7A971" opacity="0.45">
    <circle cx="190" cy="170" r="1.4"/>
    <circle cx="280" cy="195" r="1.2"/>
    <circle cx="220" cy="260" r="1.6"/>
    <circle cx="305" cy="240" r="1.0"/>
    <circle cx="165" cy="240" r="1.3"/>
    <circle cx="265" cy="155" r="1.1"/>
    <circle cx="195" cy="295" r="1.4"/>
    <circle cx="320" cy="175" r="1.2"/>
  </g>
</svg>"""

# Bacterium costumes — 3 visual states (green = idle, yellow = splitting, gray = dying)
def bacterium_svg(body_fill, glow):
    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"36\" height=\"36\" viewBox=\"0 0 36 36\">
  <defs>
    <radialGradient id=\"b\" cx=\"0.4\" cy=\"0.4\" r=\"0.6\">
      <stop offset=\"0%\"   stop-color=\"{glow}\"/>
      <stop offset=\"100%\" stop-color=\"{body_fill}\"/>
    </radialGradient>
  </defs>
  <ellipse cx=\"18\" cy=\"18\" rx=\"13\" ry=\"9\" fill=\"url(#b)\"
           stroke=\"#1B5E20\" stroke-width=\"1.2\"/>
  <circle cx=\"13\" cy=\"16\" r=\"2.4\" fill=\"#FFFFFF\" opacity=\"0.85\"/>
  <circle cx=\"22\" cy=\"19\" r=\"1.6\" fill=\"#FFFFFF\" opacity=\"0.55\"/>
  <circle cx=\"18\" cy=\"22\" r=\"1.1\" fill=\"#1B5E20\" opacity=\"0.7\"/>
  <ellipse cx=\"4\"  cy=\"18\" rx=\"1.6\" ry=\"0.5\" fill=\"{body_fill}\"/>
  <ellipse cx=\"32\" cy=\"18\" rx=\"1.6\" ry=\"0.5\" fill=\"{body_fill}\"/>
</svg>"""

BACT_IDLE     = bacterium_svg("#43A047", "#A5D6A7")  # green
BACT_SPLIT    = bacterium_svg("#F9A825", "#FFF59D")  # yellow flash
BACT_DYING    = bacterium_svg("#757575", "#BDBDBD")  # gray fade

# Game-over banner
GAME_OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.88"
        stroke="#E53935" stroke-width="4"/>
  <text x="180" y="62" text-anchor="middle"
        fill="#E53935" font-family="Arial, Helvetica, sans-serif"
        font-size="40" font-weight="bold">감염 임계치 도달</text>
  <text x="180" y="92" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">N >= N_max — 페트리 접시 폐쇄</text>
  <text x="180" y="120" text-anchor="middle"
        fill="#FFB74D" font-family="Arial, Helvetica, sans-serif"
        font-size="14">▶ 깃발을 다시 누르면 재시작</text>
  <text x="180" y="142" text-anchor="middle"
        fill="#90CAF9" font-family="Arial, Helvetica, sans-serif"
        font-size="12">점수/라운드는 좌상단 모니터 확인</text>
</svg>"""

# ---------------------------------------------------------------------------
# helpers (same shape as alien-invasion / whack-a-prime)
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
    return vrep, op, cmp_op, bool_op, mathop

# ---------------------------------------------------------------------------
# variable + broadcast IDs
# ---------------------------------------------------------------------------
V_N        = "varN001"        # current bacteria count
V_NMAX     = "varNmax002"     # threshold
V_R        = "varR003"        # split factor (1.5/2/3 ...)
V_T        = "varT004"        # split period (sec)
V_ROUND    = "varRound005"    # round index
V_SCORE    = "varScore006"    # cumulative kills
V_REMAIN   = "varRemain007"   # log_r(Nmax/N), HUD
V_GAMEOVER = "varGameOver008" # 0/1
V_KILLS    = "varKills009"    # kills this round (for advancement)
V_CAPHIT   = "varCapHit010"   # 1 once clone-cap fallback engaged
V_ALARMED  = "varAlarmed011"  # 1 once 80% warning fired in this round
V_SPAWNX   = "varSpawnX012"   # spawn coord passed parent→clone
V_SPAWNY   = "varSpawnY013"

BR_START    = "brStart001"
BR_TICK     = "brTick002"     # split tick
BR_GAMEOVER = "brOver003"
BR_NEXT     = "brNext004"

# Round table: (r, T, Nmax, kills_to_clear)
ROUNDS = [
    (1.5, 2.5, 128, 30),
    (2.0, 2.0, 256, 60),
    (2.0, 1.5, 512, 120),
    (2.5, 1.5, 768, 200),
    (3.0, 1.5, 1024, 99999),  # sudden-death
]

# Clone cap — when V_N exceeds this, stop creating new clones (just increment
# V_N). Scratch enforces 300 clones total; we cap at 120 for headroom.
CLONE_CAP = 120

# ---------------------------------------------------------------------------
# STAGE blocks — init, split timer, round advancement, game over
# ---------------------------------------------------------------------------
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)

    # ---- when flag clicked: init everything & broadcast 시작 ----
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)

    inits = []
    def setvar(name, vid, val):
        bid = gen()
        bs[bid] = mk("data_setvariableto",
                     inputs={"VALUE": num(val)},
                     fields={"VARIABLE": [name, vid]})
        inits.append((bid, bs[bid]))
        return bid

    setvar("N",        V_N,        1)
    setvar("R",        V_R,        ROUNDS[0][0])
    setvar("T",        V_T,        ROUNDS[0][1])
    setvar("N_max",    V_NMAX,     ROUNDS[0][2])
    setvar("라운드",    V_ROUND,    1)
    setvar("점수",      V_SCORE,    0)
    setvar("남은분열",  V_REMAIN,   0)
    setvar("게임오버",  V_GAMEOVER, 0)
    setvar("처치",      V_KILLS,    0)
    setvar("CapHit",   V_CAPHIT,   0)
    setvar("Alarmed",  V_ALARMED,  0)
    setvar("SpawnX",   V_SPAWNX,   0)
    setvar("SpawnY",   V_SPAWNY,   0)

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h, bs[h])] + inits + [(bc_start, bs[bc_start])])

    # ---- on 시작: forever — every V_T sec broadcast 분열, also update HUD ----
    # We keep the split-tick and HUD update in two separate top scripts.

    # === split tick loop ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["시작", BR_START]})

    go_var = vrep("게임오버", V_GAMEOVER)
    cond_over = cmp_op("operator_equals", go_var, 1)

    # body: wait V_T, if !over broadcast 분열
    tvar = vrep("T", V_T)
    wt_split = gen(); bs[wt_split] = mk("control_wait",
        inputs={"DURATION": slot(tvar)})
    bs[tvar]["parent"] = wt_split

    bm_tick = gen(); bs[bm_tick] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["분열", BR_TICK]}, shadow=True)
    bc_tick = gen(); bs[bc_tick] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_tick]})
    bs[bm_tick]["parent"] = bc_tick

    chain([(wt_split, bs[wt_split]), (bc_tick, bs[bc_tick])])

    rep_until_a = gen(); bs[rep_until_a] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over], "SUBSTACK": [2, wt_split]})
    bs[cond_over]["parent"] = rep_until_a
    bs[wt_split]["parent"] = rep_until_a

    chain([(h2, bs[h2]), (rep_until_a, bs[rep_until_a])])

    # === HUD update loop ===
    # V_REMAIN = round((log(V_NMAX / V_N) / log(V_R)) * 10) / 10
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=320,
        fields={"BROADCAST_OPTION": ["시작", BR_START]})

    go_var2 = vrep("게임오버", V_GAMEOVER)
    cond_over2 = cmp_op("operator_equals", go_var2, 1)

    # Build: log10(Nmax/N) / log10(R), rounded to 1dp.
    nmax_v = vrep("N_max", V_NMAX)
    n_v    = vrep("N",     V_N)
    ratio  = op("operator_divide", nmax_v, n_v)
    log_ratio = mathop("log", ratio)
    r_v    = vrep("R", V_R)
    log_r  = mathop("log", r_v)
    div_lr = op("operator_divide", log_ratio, log_r)
    times10 = op("operator_multiply", div_lr, 10)
    plus05  = op("operator_add", times10, 0.5)
    floor1  = mathop("floor", plus05)
    div10   = op("operator_divide", floor1, 10)

    # if N >= 1 then set REMAIN to that value, else "--"
    n_chk = vrep("N", V_N)
    cond_nge1 = cmp_op("operator_lt", 0, n_chk)  # 0 < N  →  N >= 1

    set_rem = gen(); bs[set_rem] = mk("data_setvariableto",
        inputs={"VALUE": slot(div10)},
        fields={"VARIABLE": ["남은분열", V_REMAIN]})
    bs[div10]["parent"] = set_rem
    # else: dash
    # Scratch variables are not typed: we set "—" string
    # But for monitor display, just clamp to 0 if N=0.
    # We use simple if (no else) so REMAIN holds the last value briefly.

    if_rem = gen(); bs[if_rem] = mk("control_if",
        inputs={"CONDITION": [2, cond_nge1], "SUBSTACK": [2, set_rem]})
    bs[cond_nge1]["parent"] = if_rem
    bs[set_rem]["parent"] = if_rem

    # alarm: if N/Nmax >= 0.8 and not yet alarmed → play alarm, set Alarmed=1
    n_v3    = vrep("N", V_N)
    nmax_v3 = vrep("N_max", V_NMAX)
    ratio2  = op("operator_divide", n_v3, nmax_v3)
    cond_hi = cmp_op("operator_gt", ratio2, 0.8)
    al_v    = vrep("Alarmed", V_ALARMED)
    cond_quiet = cmp_op("operator_equals", al_v, 0)
    and_alarm = bool_op("operator_and", cond_hi, cond_quiet)

    snm_al = gen(); bs[snm_al] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["alarm", None]}, shadow=True)
    snd_al = gen(); bs[snd_al] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_al]})
    bs[snm_al]["parent"] = snd_al
    set_al = gen(); bs[set_al] = mk("data_setvariableto",
        inputs={"VALUE": num(1)},
        fields={"VARIABLE": ["Alarmed", V_ALARMED]})
    chain([(snd_al, bs[snd_al]), (set_al, bs[set_al])])
    if_alarm = gen(); bs[if_alarm] = mk("control_if",
        inputs={"CONDITION": [2, and_alarm], "SUBSTACK": [2, snd_al]})
    bs[and_alarm]["parent"] = if_alarm
    bs[snd_al]["parent"] = if_alarm

    # game-over trigger: if N >= Nmax  →  set V_GAMEOVER=1, broadcast
    n_v4    = vrep("N", V_N)
    nmax_v4 = vrep("N_max", V_NMAX)
    cond_dead = cmp_op("operator_gt", n_v4, nmax_v4)
    # ">=" via NOT < ; we use > (Nmax-1). Cheaper: just check N > Nmax-1 by
    # computing N - Nmax + 1 > 0 ... but simpler to just do N >= Nmax via OR
    # of equal+gt. Two-block path:
    n_v5    = vrep("N", V_N)
    nmax_v5 = vrep("N_max", V_NMAX)
    cond_eq = cmp_op("operator_equals", n_v5, nmax_v5)
    cond_ge = bool_op("operator_or", cond_dead, cond_eq)

    set_go = gen(); bs[set_go] = mk("data_setvariableto",
        inputs={"VALUE": num(1)},
        fields={"VARIABLE": ["게임오버", V_GAMEOVER]})
    bm_go = gen(); bs[bm_go] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]}, shadow=True)
    bc_go = gen(); bs[bc_go] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_go]})
    bs[bm_go]["parent"] = bc_go
    chain([(set_go, bs[set_go]), (bc_go, bs[bc_go])])
    if_go = gen(); bs[if_go] = mk("control_if",
        inputs={"CONDITION": [2, cond_ge], "SUBSTACK": [2, set_go]})
    bs[cond_ge]["parent"] = if_go
    bs[set_go]["parent"] = if_go

    wt_h = gen(); bs[wt_h] = mk("control_wait", inputs={"DURATION": num(0.1)})

    chain([(if_rem, bs[if_rem]), (if_alarm, bs[if_alarm]),
           (if_go, bs[if_go]), (wt_h, bs[wt_h])])

    rep_until_b = gen(); bs[rep_until_b] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over2], "SUBSTACK": [2, if_rem]})
    bs[cond_over2]["parent"] = rep_until_b
    bs[if_rem]["parent"] = rep_until_b

    chain([(h3, bs[h3]), (rep_until_b, bs[rep_until_b])])

    # === round-advance loop ===
    # third script: forever, if V_KILLS >= round_goal → broadcast 다음
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=620, y=320,
        fields={"BROADCAST_OPTION": ["시작", BR_START]})

    go_var3 = vrep("게임오버", V_GAMEOVER)
    cond_over3 = cmp_op("operator_equals", go_var3, 1)

    # We build a chain of if-blocks per round: if round=k and kills>=goal[k]
    advance_chain = []
    for idx, (r_val, t_val, nmax_val, kills_needed) in enumerate(ROUNDS[:-1], start=1):
        # condition: 라운드 == idx AND 처치 >= kills_needed
        round_v = vrep("라운드", V_ROUND)
        cond_round = cmp_op("operator_equals", round_v, idx)
        kills_v = vrep("처치", V_KILLS)
        # >= kills_needed  via  kills > (kills_needed - 1)
        cond_kills = cmp_op("operator_gt", kills_v, kills_needed - 1)
        and_adv = bool_op("operator_and", cond_round, cond_kills)

        nxt_r, nxt_t, nxt_nmax, _ = ROUNDS[idx]
        set_r = gen(); bs[set_r] = mk("data_setvariableto",
            inputs={"VALUE": num(nxt_r)}, fields={"VARIABLE": ["R", V_R]})
        set_t = gen(); bs[set_t] = mk("data_setvariableto",
            inputs={"VALUE": num(nxt_t)}, fields={"VARIABLE": ["T", V_T]})
        set_nmax = gen(); bs[set_nmax] = mk("data_setvariableto",
            inputs={"VALUE": num(nxt_nmax)}, fields={"VARIABLE": ["N_max", V_NMAX]})
        inc_round = gen(); bs[inc_round] = mk("data_changevariableby",
            inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
        reset_kills = gen(); bs[reset_kills] = mk("data_setvariableto",
            inputs={"VALUE": num(0)}, fields={"VARIABLE": ["처치", V_KILLS]})
        reset_alarm = gen(); bs[reset_alarm] = mk("data_setvariableto",
            inputs={"VALUE": num(0)}, fields={"VARIABLE": ["Alarmed", V_ALARMED]})
        bm_n = gen(); bs[bm_n] = mk("event_broadcast_menu",
            fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]}, shadow=True)
        bc_n = gen(); bs[bc_n] = mk("event_broadcast",
            inputs={"BROADCAST_INPUT": [1, bm_n]})
        bs[bm_n]["parent"] = bc_n
        chain([(set_r,bs[set_r]),(set_t,bs[set_t]),(set_nmax,bs[set_nmax]),
               (inc_round,bs[inc_round]),(reset_kills,bs[reset_kills]),
               (reset_alarm,bs[reset_alarm]),(bc_n,bs[bc_n])])

        if_adv = gen(); bs[if_adv] = mk("control_if",
            inputs={"CONDITION": [2, and_adv], "SUBSTACK": [2, set_r]})
        bs[and_adv]["parent"] = if_adv
        bs[set_r]["parent"] = if_adv
        advance_chain.append((if_adv, bs[if_adv]))

    wt_adv = gen(); bs[wt_adv] = mk("control_wait", inputs={"DURATION": num(0.2)})
    advance_body = advance_chain + [(wt_adv, bs[wt_adv])]
    chain(advance_body)

    rep_until_c = gen(); bs[rep_until_c] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over3],
                "SUBSTACK": [2, advance_body[0][0]]})
    bs[cond_over3]["parent"] = rep_until_c
    advance_body[0][1]["parent"] = rep_until_c

    chain([(h4, bs[h4]), (rep_until_c, bs[rep_until_c])])

    return bs

# ---------------------------------------------------------------------------
# BACTERIA blocks — initial spawn, split on tick, click-to-kill, game over
# ---------------------------------------------------------------------------
def build_bacteria_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)

    # === when flag clicked: hide the original bacterium body ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    # === on 시작: spawn the initial bacterium ===
    # Set SpawnX/SpawnY to dish center then create one clone.
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["시작", BR_START]})

    s_sx = gen(); bs[s_sx] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["SpawnX", V_SPAWNX]})
    s_sy = gen(); bs[s_sy] = mk("data_setvariableto",
        inputs={"VALUE": num(-40)}, fields={"VARIABLE": ["SpawnY", V_SPAWNY]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(h2,bs[h2]),(s_sx,bs[s_sx]),(s_sy,bs[s_sy]),(cclone,bs[cclone])])

    # === on 다음라운드: reset — delete all clones, spawn fresh ===
    # We can't "delete all clones" globally; instead, each clone listens for
    # 다음라운드 and deletes itself, while the original sprite re-spawns one.
    h_next = gen(); bs[h_next] = mk("event_whenbroadcastreceived", top=True,
        x=320, y=200,
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]})
    reset_n = gen(); bs[reset_n] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["N", V_N]})
    reset_cap = gen(); bs[reset_cap] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["CapHit", V_CAPHIT]})
    wt_rs = gen(); bs[wt_rs] = mk("control_wait", inputs={"DURATION": num(0.4)})
    s_sx2 = gen(); bs[s_sx2] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["SpawnX", V_SPAWNX]})
    s_sy2 = gen(); bs[s_sy2] = mk("data_setvariableto",
        inputs={"VALUE": num(-40)}, fields={"VARIABLE": ["SpawnY", V_SPAWNY]})
    cmenu2 = gen(); bs[cmenu2] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone2 = gen(); bs[cclone2] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu2]})
    bs[cmenu2]["parent"] = cclone2
    chain([(h_next,bs[h_next]),(reset_n,bs[reset_n]),(reset_cap,bs[reset_cap]),
           (wt_rs,bs[wt_rs]),(s_sx2,bs[s_sx2]),(s_sy2,bs[s_sy2]),
           (cclone2,bs[cclone2])])

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=620, y=20)

    # go to (SpawnX + random jitter, SpawnY + random jitter)
    sx_v = vrep("SpawnX", V_SPAWNX); sy_v = vrep("SpawnY", V_SPAWNY)
    jx = op("operator_random", -6, 6, key1="FROM", key2="TO")
    jy = op("operator_random", -6, 6, key1="FROM", key2="TO")
    px = op("operator_add", sx_v, jx)
    py = op("operator_add", sy_v, jy)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(px), "Y": slot(py)})
    bs[px]["parent"] = g_init; bs[py]["parent"] = g_init

    cost_idle = gen(); bs[cost_idle] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen_costume_menu(bs, "idle")]})
    show = gen(); bs[show] = mk("looks_show")

    # Random tiny rotation for visual liveliness
    rdir = op("operator_random", 60, 120, key1="FROM", key2="TO")
    pd = gen(); bs[pd] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(rdir)})
    bs[rdir]["parent"] = pd

    chain([(ch,bs[ch]),(g_init,bs[g_init]),(cost_idle,bs[cost_idle]),
           (show,bs[show]),(pd,bs[pd])])

    # === clone listens for 분열 (split tick) ===
    # On tick: with prob (R-1) integer + fractional, create that many clones
    # of myself at offsets near me. Also update parent V_N.
    h_tick = gen(); bs[h_tick] = mk("event_whenbroadcastreceived", top=True,
        x=920, y=20,
        fields={"BROADCAST_OPTION": ["분열", BR_TICK]})

    # Guard: if 게임오버=1 stop
    go_v = vrep("게임오버", V_GAMEOVER)
    cond_alive = cmp_op("operator_equals", go_v, 0)

    # Pulse to splitting costume
    cost_split = gen(); bs[cost_split] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen_costume_menu(bs, "splitting")]})
    wt_blink = gen(); bs[wt_blink] = mk("control_wait", inputs={"DURATION": num(0.1)})
    cost_back = gen(); bs[cost_back] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen_costume_menu(bs, "idle")]})

    # play split sound (low volume)
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["split", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm]})
    bs[snm]["parent"] = snd

    # Compute how many clones to create:
    #   base = floor(R - 1)        ← integer part
    #   frac = R - 1 - base        ← fractional part
    #   extra = 1 if random(0..1) < frac else 0
    r_a = vrep("R", V_R)
    rm1 = op("operator_subtract", r_a, 1)
    floor_rm1 = mathop("floor", rm1)
    set_base = gen(); bs[set_base] = mk("data_setvariableto",
        inputs={"VALUE": slot(floor_rm1)},
        fields={"VARIABLE": ["SpawnX", V_SPAWNX]})  # reuse SpawnX as scratch
    bs[floor_rm1]["parent"] = set_base
    # Hmm — we shouldn't clobber SpawnX. Let me use a clone-local variable.
    # Actually clone-local variables are awkward; instead compute inline.

    # Simpler approach: just attempt to create (R-1) clones — but R-1 may be
    # fractional. We do it via a loop with `repeat (floor(R-1))` then a
    # probabilistic extra.

    # Drop the bogus set_base above by overwriting the chain — let's rebuild:
    # Inline build:
    # repeat (floor(R - 1)):
    #   try_spawn_one_child
    # if random(0..1) < (R - 1 - floor(R - 1)): try_spawn_one_child

    def try_spawn_block_chain():
        """Build a sequence that spawns ONE child clone at this clone's pos
        (with small jitter), provided V_N < CLONE_CAP. Always increments V_N
        regardless of whether a visual clone is created (so the math is
        honest). Returns the head id (and registers blocks in bs).
        """
        # Scatter children across the dish on every split — previously children
        # spawned at parent.x/y + ±6 jitter, causing family clusters. Dish
        # center is (0, -40) with radius 135; inscribed square is
        # x∈(-90, 90), y∈(-130, 50) which keeps clones safely inside.
        xp = op("operator_random", -90, 90, key1="FROM", key2="TO")
        set_sx = gen(); bs[set_sx] = mk("data_setvariableto",
            inputs={"VALUE": slot(xp)},
            fields={"VARIABLE": ["SpawnX", V_SPAWNX]})
        bs[xp]["parent"] = set_sx
        yp = op("operator_random", -130, 50, key1="FROM", key2="TO")
        set_sy = gen(); bs[set_sy] = mk("data_setvariableto",
            inputs={"VALUE": slot(yp)},
            fields={"VARIABLE": ["SpawnY", V_SPAWNY]})
        bs[yp]["parent"] = set_sy

        # if V_N < CLONE_CAP → create clone
        n_v = vrep("N", V_N)
        cond_room = cmp_op("operator_lt", n_v, CLONE_CAP)
        cm = gen(); bs[cm] = mk("control_create_clone_of_menu",
            fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
        cc = gen(); bs[cc] = mk("control_create_clone_of",
            inputs={"CLONE_OPTION": [1, cm]})
        bs[cm]["parent"] = cc
        if_room = gen(); bs[if_room] = mk("control_if",
            inputs={"CONDITION": [2, cond_room], "SUBSTACK": [2, cc]})
        bs[cond_room]["parent"] = if_room
        bs[cc]["parent"] = if_room

        # else flag cap: if V_N >= CLONE_CAP → set CapHit = 1
        # (do it as a separate small "if" using >= via OR of > and ==)
        n_v2 = vrep("N", V_N)
        cond_cap_gt = cmp_op("operator_gt", n_v2, CLONE_CAP - 1)
        set_cap = gen(); bs[set_cap] = mk("data_setvariableto",
            inputs={"VALUE": num(1)},
            fields={"VARIABLE": ["CapHit", V_CAPHIT]})
        if_cap = gen(); bs[if_cap] = mk("control_if",
            inputs={"CONDITION": [2, cond_cap_gt], "SUBSTACK": [2, set_cap]})
        bs[cond_cap_gt]["parent"] = if_cap
        bs[set_cap]["parent"] = if_cap

        # Always increment V_N by 1 — math/biology is honest even when the
        # clone visual is capped (the petri dish is "abstract" past 120).
        inc_n = gen(); bs[inc_n] = mk("data_changevariableby",
            inputs={"VALUE": num(1)}, fields={"VARIABLE": ["N", V_N]})

        seq = [(set_sx,bs[set_sx]),(set_sy,bs[set_sy]),(if_room,bs[if_room]),
               (if_cap,bs[if_cap]),(inc_n,bs[inc_n])]
        chain(seq)
        return seq[0][0], seq[-1][0]  # head, tail

    # Integer part: repeat (floor(R - 1))
    r_b = vrep("R", V_R)
    rm1_b = op("operator_subtract", r_b, 1)
    floor_rm1_b = mathop("floor", rm1_b)

    body_head_int, _ = try_spawn_block_chain()
    rep_int = gen(); bs[rep_int] = mk("control_repeat",
        inputs={"TIMES": slot(floor_rm1_b), "SUBSTACK": [2, body_head_int]})
    bs[floor_rm1_b]["parent"] = rep_int
    bs[body_head_int]["parent"] = rep_int

    # Fractional part: if random(0..1) < (R - 1 - floor(R - 1)) → spawn one
    r_c = vrep("R", V_R)
    rm1_c = op("operator_subtract", r_c, 1)
    floor_rm1_c = mathop("floor", rm1_c)
    r_d = vrep("R", V_R)
    rm1_d = op("operator_subtract", r_d, 1)
    frac = op("operator_subtract", rm1_d, floor_rm1_c)
    rnd = op("operator_random", 0, 1, key1="FROM", key2="TO")
    cond_frac = cmp_op("operator_lt", rnd, frac)

    body_head_frac, _ = try_spawn_block_chain()
    if_frac = gen(); bs[if_frac] = mk("control_if",
        inputs={"CONDITION": [2, cond_frac], "SUBSTACK": [2, body_head_frac]})
    bs[cond_frac]["parent"] = if_frac
    bs[body_head_frac]["parent"] = if_frac

    chain([(cost_split,bs[cost_split]),(snd,bs[snd]),(wt_blink,bs[wt_blink]),
           (cost_back,bs[cost_back]),(rep_int,bs[rep_int]),(if_frac,bs[if_frac])])
    if_alive = gen(); bs[if_alive] = mk("control_if",
        inputs={"CONDITION": [2, cond_alive], "SUBSTACK": [2, cost_split]})
    bs[cond_alive]["parent"] = if_alive
    bs[cost_split]["parent"] = if_alive

    chain([(h_tick, bs[h_tick]), (if_alive, bs[if_alive])])

    # === when this sprite (clone) clicked: kill ===
    cl = gen(); bs[cl] = mk("event_whenthisspriteclicked", top=True, x=920, y=380)

    # Guard: only kill if game not over
    go_v2 = vrep("게임오버", V_GAMEOVER)
    cond_alive2 = cmp_op("operator_equals", go_v2, 0)

    cost_die = gen(); bs[cost_die] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen_costume_menu(bs, "dying")]})
    pop_pitch = gen(); bs[pop_pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(80)}, fields={"EFFECT": ["PITCH", None]})
    snm2 = gen(); bs[snm2] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd2 = gen(); bs[snd2] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm2]})
    bs[snm2]["parent"] = snd2

    dec_n = gen(); bs[dec_n] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["N", V_N]})
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    inc_kills = gen(); bs[inc_kills] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["처치", V_KILLS]})

    wt_die = gen(); bs[wt_die] = mk("control_wait", inputs={"DURATION": num(0.05)})
    del_me = gen(); bs[del_me] = mk("control_delete_this_clone")

    kill_seq = [(cost_die,bs[cost_die]),(pop_pitch,bs[pop_pitch]),(snd2,bs[snd2]),
                (dec_n,bs[dec_n]),(inc_score,bs[inc_score]),
                (inc_kills,bs[inc_kills]),(wt_die,bs[wt_die]),(del_me,bs[del_me])]
    chain(kill_seq)
    if_kill = gen(); bs[if_kill] = mk("control_if",
        inputs={"CONDITION": [2, cond_alive2], "SUBSTACK": [2, cost_die]})
    bs[cond_alive2]["parent"] = if_kill
    bs[cost_die]["parent"] = if_kill

    chain([(cl, bs[cl]), (if_kill, bs[if_kill])])

    # === clone listens for 다음라운드: delete self (clears the field) ===
    h_clr = gen(); bs[h_clr] = mk("event_whenbroadcastreceived", top=True,
        x=620, y=380,
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]})
    del_self = gen(); bs[del_self] = mk("control_delete_this_clone")
    chain([(h_clr, bs[h_clr]), (del_self, bs[del_self])])

    # === clone listens for 게임종료: switch to dying costume, stop ===
    h_go = gen(); bs[h_go] = mk("event_whenbroadcastreceived", top=True,
        x=320, y=380,
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]})
    cost_die2 = gen(); bs[cost_die2] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen_costume_menu(bs, "dying")]})
    chain([(h_go, bs[h_go]), (cost_die2, bs[cost_die2])])

    return bs

def gen_costume_menu(bs, name):
    bid = gen()
    bs[bid] = mk("looks_costume", shadow=True,
                 fields={"COSTUME": [name, None]})
    return bid

# ---------------------------------------------------------------------------
# GAME OVER banner sprite
# ---------------------------------------------------------------------------
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # First wait for game to actually START (게임오버=0 after flag init).
    # Then wait for 게임오버=1 to show banner.
    go_v1 = vrep("게임오버", V_GAMEOVER)
    cond_play = cmp_op("operator_equals", go_v1, 0)
    wait_play = gen(); bs[wait_play] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_play]})
    bs[cond_play]["parent"] = wait_play

    go_v2 = vrep("게임오버", V_GAMEOVER)
    cond_dead = cmp_op("operator_equals", go_v2, 1)
    wait_dead = gen(); bs[wait_dead] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_dead]})
    bs[cond_dead]["parent"] = wait_dead

    show = gen(); bs[show] = mk("looks_show")
    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front]),
           (wait_play,bs[wait_play]),(wait_dead,bs[wait_dead]),(show,bs[show])])
    return bs

# ---------------------------------------------------------------------------
# ASSEMBLE PROJECT
# ---------------------------------------------------------------------------
def wav_meta(path):
    with wave.open(path, "rb") as w:
        return w.getnframes(), w.getframerate()

def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # ---- assets ----
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    bi_md5 = md5_bytes(BACT_IDLE.encode("utf-8"))
    with open(f"{WORK}/{bi_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BACT_IDLE)
    bs_md5 = md5_bytes(BACT_SPLIT.encode("utf-8"))
    with open(f"{WORK}/{bs_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BACT_SPLIT)
    bd_md5 = md5_bytes(BACT_DYING.encode("utf-8"))
    with open(f"{WORK}/{bd_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BACT_DYING)

    go_md5 = md5_bytes(GAME_OVER_SVG.encode("utf-8"))
    with open(f"{WORK}/{go_md5}.svg", "w", encoding="utf-8") as f:
        f.write(GAME_OVER_SVG)

    # sounds
    def copy_sound(name):
        src = f"{ASSETS}/{name}.wav"
        with open(src, "rb") as f: data = f.read()
        h = md5_bytes(data)
        with open(f"{WORK}/{h}.wav", "wb") as f: f.write(data)
        frames, rate = wav_meta(src)
        return {"name": name, "assetId": h, "dataFormat": "wav",
                "format": "", "rate": rate, "sampleCount": frames,
                "md5ext": f"{h}.wav"}

    pop_snd   = copy_sound("pop")
    split_snd = copy_sound("split")
    alarm_snd = copy_sound("alarm")

    # ---- build block dicts ----
    stage_blocks    = build_stage_blocks()
    bact_blocks     = build_bacteria_blocks()
    gameover_blocks = build_gameover_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_N:        ["N",        1],
            V_NMAX:     ["N_max",    ROUNDS[0][2]],
            V_R:        ["R",        ROUNDS[0][0]],
            V_T:        ["T",        ROUNDS[0][1]],
            V_ROUND:    ["라운드",    1],
            V_SCORE:    ["점수",      0],
            V_REMAIN:   ["남은분열",  0],
            V_GAMEOVER: ["게임오버",  0],
            V_KILLS:    ["처치",      0],
            V_CAPHIT:   ["CapHit",   0],
            V_ALARMED:  ["Alarmed",  0],
            V_SPAWNX:   ["SpawnX",   0],
            V_SPAWNY:   ["SpawnY",   0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:    "시작",
            BR_TICK:     "분열",
            BR_GAMEOVER: "게임종료",
            BR_NEXT:     "다음라운드",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "petri", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_snd, split_snd, alarm_snd],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None,
    }

    bacteria = {
        "isStage": False, "name": "박테리아",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bact_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "idle", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bi_md5, "md5ext": f"{bi_md5}.svg",
             "rotationCenterX": 18, "rotationCenterY": 18},
            {"name": "splitting", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bs_md5, "md5ext": f"{bs_md5}.svg",
             "rotationCenterX": 18, "rotationCenterY": 18},
            {"name": "dying", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bd_md5, "md5ext": f"{bd_md5}.svg",
             "rotationCenterX": 18, "rotationCenterY": 18},
        ],
        "sounds": [pop_snd, split_snd, alarm_snd],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": -40, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around",
    }

    gameover = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": gameover_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": go_md5, "md5ext": f"{go_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 80,
        }],
        "sounds": [pop_snd],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }

    # HUD monitors — top of stage
    monitors = [
        {"id": V_N, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "N"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 1024, "isDiscrete": True},
        {"id": V_REMAIN, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "남은분열"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": False},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 125,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 380, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 1000, "isDiscrete": True},
        {"id": V_R, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "R"}, "spriteName": None,
         "value": ROUNDS[0][0], "width": 0, "height": 0, "x": 380, "y": 95,
         "visible": True, "sliderMin": 1, "sliderMax": 5, "isDiscrete": False},
        {"id": V_T, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "T"}, "spriteName": None,
         "value": ROUNDS[0][1], "width": 0, "height": 0, "x": 380, "y": 125,
         "visible": True, "sliderMin": 0.5, "sliderMax": 5, "isDiscrete": False},
        {"id": V_NMAX, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "N_max"}, "spriteName": None,
         "value": ROUNDS[0][2], "width": 0, "height": 0, "x": 380, "y": 155,
         "visible": True, "sliderMin": 0, "sliderMax": 2048, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, bacteria, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "bacteria-defense-builder"},
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # validate JSON
    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)
    print(f"OK wrote {OUTPUT}")

if __name__ == "__main__":
    main()
