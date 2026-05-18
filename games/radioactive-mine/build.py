#!/usr/bin/env python3
"""Radioactive Mine — feel exponential decay through a 60-second click rush.

Up to 4 radioactive ore clones live at any time. Each has its own half-life
`T` (1.0~5.0 s) and starting mass `N0` (50~200). Every 0.1 s every clone
updates its current mass with

    N(Δt) = N0 · 0.5^(Δt / T)
          = N0 · e^( (Δt / T) · ln(0.5) )

We synthesize 0.5^x via `e^` and the constant V_LN_HALF = ln(0.5). When N
falls below 5 % of N0 the clone self-destructs. Clicking a clone banks
round(N) into the score and removes the clone. After 60 s the result banner
shows. This is the *opposite* mechanic of bacteria-defense (growth vs decay)
— same exponential family, sign flipped.
"""
import json, math, os, struct, wave, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "반감기_광산.sb3")

SAMPLE_RATE = 22050

# ---------------------------------------------------------------------------
# SVG assets
# ---------------------------------------------------------------------------

# Mine background — dark rock walls with subtle radioactive glow + HUD strip.
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <radialGradient id="cave" cx="0.5" cy="0.6" r="0.65">
      <stop offset="0%"   stop-color="#1A2030"/>
      <stop offset="55%"  stop-color="#0E1320"/>
      <stop offset="100%" stop-color="#04060C"/>
    </radialGradient>
    <linearGradient id="hud" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0E2A1F"/>
      <stop offset="100%" stop-color="#142E25"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#cave)"/>
  <rect x="0" y="0" width="480" height="60" fill="url(#hud)"/>
  <line x1="0" y1="60" x2="480" y2="60" stroke="#3FA66B" stroke-width="0.8" opacity="0.7"/>
  <text x="14" y="22" fill="#A8F0C7" font-family="Arial, Helvetica, sans-serif"
        font-size="13" font-weight="bold">☢ 반감기 광산 — 지수 감쇠</text>
  <text x="14" y="44" fill="#C5F0D8" font-family="Arial, Helvetica, sans-serif"
        font-size="11">N(t) = N₀ · (1/2)^(t/T) · 클릭으로 현재 질량 채굴</text>
  <text x="466" y="22" fill="#FFE082" font-family="Arial, Helvetica, sans-serif"
        font-size="11" text-anchor="end">60초 안에 최대 질량 채굴</text>
  <text x="466" y="44" fill="#FFAB91" font-family="Arial, Helvetica, sans-serif"
        font-size="11" text-anchor="end">늦으면 질량 절반으로 ↓</text>

  <!-- rough rock outline (lower 2/3) -->
  <g opacity="0.5" stroke="#2A3A4A" stroke-width="1" fill="none">
    <path d="M 0 110 L 60 95 L 130 130 L 220 100 L 310 135 L 400 110 L 480 130"/>
    <path d="M 0 200 L 90 220 L 180 195 L 270 230 L 360 200 L 440 225 L 480 215"/>
    <path d="M 0 310 L 80 290 L 170 320 L 260 295 L 350 325 L 440 300 L 480 320"/>
  </g>
  <!-- scattered ore crumbs -->
  <g fill="#7FE0B6" opacity="0.35">
    <circle cx="60"  cy="180" r="1.6"/>
    <circle cx="120" cy="250" r="1.2"/>
    <circle cx="220" cy="170" r="1.4"/>
    <circle cx="290" cy="280" r="1.5"/>
    <circle cx="370" cy="190" r="1.3"/>
    <circle cx="420" cy="260" r="1.1"/>
    <circle cx="160" cy="320" r="1.4"/>
    <circle cx="330" cy="330" r="1.2"/>
  </g>
</svg>"""

# Ore costumes — fresh (bright cyan glow) / decayed (dim gray)
def ore_svg(core_color, glow_color, halo_opacity):
    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"60\" height=\"60\" viewBox=\"0 0 60 60\">
  <defs>
    <radialGradient id=\"orG\" cx=\"0.5\" cy=\"0.5\" r=\"0.55\">
      <stop offset=\"0%\"   stop-color=\"{glow_color}\"/>
      <stop offset=\"60%\"  stop-color=\"{core_color}\"/>
      <stop offset=\"100%\" stop-color=\"#0A1A14\"/>
    </radialGradient>
  </defs>
  <circle cx=\"30\" cy=\"30\" r=\"26\" fill=\"{glow_color}\" opacity=\"{halo_opacity}\"/>
  <polygon points=\"30,8 48,22 44,46 16,46 12,22\"
           fill=\"url(#orG)\" stroke=\"#1A4A35\" stroke-width=\"1.4\"/>
  <polygon points=\"30,8 48,22 30,32 12,22\" fill=\"{glow_color}\" opacity=\"0.35\"/>
  <circle cx=\"22\" cy=\"24\" r=\"3.6\" fill=\"#FFFFFF\" opacity=\"0.55\"/>
  <text x=\"30\" y=\"38\" text-anchor=\"middle\"
        fill=\"#FFFFFF\" opacity=\"0.85\"
        font-family=\"Arial, Helvetica, sans-serif\"
        font-size=\"13\" font-weight=\"bold\">☢</text>
</svg>"""

ORE_FRESH   = ore_svg("#00BFA5", "#7FE0B6", "0.55")   # bright teal
ORE_DECAYED = ore_svg("#4A5560", "#6F7C88", "0.25")   # dim gray

# Result banner shown after 60s
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="380" height="170" viewBox="0 0 380 170">
  <rect x="5" y="5" width="370" height="160" rx="14"
        fill="#000000" opacity="0.9"
        stroke="#00BFA5" stroke-width="4"/>
  <text x="190" y="58" text-anchor="middle"
        fill="#00BFA5" font-family="Arial, Helvetica, sans-serif"
        font-size="34" font-weight="bold">60초 종료!</text>
  <text x="190" y="92" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="16">점수와 처치 수는 좌상단 모니터 확인</text>
  <text x="190" y="120" text-anchor="middle"
        fill="#FFB74D" font-family="Arial, Helvetica, sans-serif"
        font-size="14">▶ 깃발을 다시 누르면 재시작</text>
  <text x="190" y="148" text-anchor="middle"
        fill="#90CAF9" font-family="Arial, Helvetica, sans-serif"
        font-size="12">N(t) = N₀ · (1/2)^(t/T) — 늦을수록 점수가 절반으로</text>
</svg>"""

# ---------------------------------------------------------------------------
# helpers (shared shape with bacteria-defense / alien-invasion)
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
    def timer():
        bid = gen()
        bs[bid] = mk("sensing_timer")
        return bid
    return vrep, op, cmp_op, bool_op, mathop, timer

# ---------------------------------------------------------------------------
# variable + broadcast IDs
# ---------------------------------------------------------------------------
# Stage (global)
V_SCORE        = "varScore001"        # 누적 점수
V_TIME_LEFT    = "varTime002"         # 남은 시간 (60 → 0)
V_PICKED       = "varPicked003"       # 처치한 광물 수
V_GAMEOVER     = "varGameOver004"
V_SPAWN_X      = "varSpawnX005"
V_SPAWN_Y      = "varSpawnY006"
V_SPAWN_N0     = "varSpawnN0007"
V_SPAWN_T      = "varSpawnT008"
V_LN_HALF      = "varLnHalf009"       # ln(0.5) 상수
V_LOG_HALF     = "varLogHalf010"      # log10(0.5) 상수 (백업, plan 명시용)
V_CLONE_COUNT  = "varCloneCount011"   # 현재 살아있는 광물 수

# Sprite-local (광물 클론별)
V_N0           = "varN0Ore012"
V_T_HALFLIFE   = "varTHalfOre013"
V_T_BIRTH      = "varTBirthOre014"
V_MASS_NOW     = "varMassOre015"
V_LIFE_LEFT    = "varLifeOre016"

# Broadcasts
BR_START       = "brStart001"
BR_SPAWN_MORE  = "brSpawn002"
BR_GAMEOVER    = "brOver003"

LN_HALF = math.log(0.5)            # -0.6931471805599453
LOG_HALF = math.log10(0.5)         # -0.3010299956639812

MAX_ORE = 4
GAME_DURATION = 60   # seconds

# ---------------------------------------------------------------------------
# STAGE blocks — init, countdown timer, spawn dispatcher
# ---------------------------------------------------------------------------
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop, timer = make_helpers(bs)

    # ===== when flag clicked: init + reset timer + broadcast 시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)

    inits = []
    def setvar(name, vid, val):
        bid = gen()
        bs[bid] = mk("data_setvariableto",
                     inputs={"VALUE": num(val)},
                     fields={"VARIABLE": [name, vid]})
        inits.append((bid, bs[bid]))
        return bid

    setvar("점수",        V_SCORE,       0)
    setvar("남은시간",    V_TIME_LEFT,   GAME_DURATION)
    setvar("처치",        V_PICKED,      0)
    setvar("게임오버",    V_GAMEOVER,    0)
    setvar("SpawnX",     V_SPAWN_X,     0)
    setvar("SpawnY",     V_SPAWN_Y,     0)
    setvar("SpawnN0",    V_SPAWN_N0,    100)
    setvar("SpawnT",     V_SPAWN_T,     2)
    # constants (used by 광물 clone formulas)
    setvar("ln(0.5)",    V_LN_HALF,     LN_HALF)
    setvar("log(0.5)",   V_LOG_HALF,    LOG_HALF)
    setvar("CloneCount", V_CLONE_COUNT, 0)

    # reset timer so all clones share an origin
    rt = gen(); bs[rt] = mk("sensing_resettimer")
    inits.append((rt, bs[rt]))

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h, bs[h])] + inits + [(bc_start, bs[bc_start])])

    # ===== 시작 → countdown loop (1초마다 -1, 0 도달 시 게임오버) =====
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=300,
        fields={"BROADCAST_OPTION": ["시작", BR_START]})

    go_v = vrep("게임오버", V_GAMEOVER)
    cond_over = cmp_op("operator_equals", go_v, 1)

    wt1 = gen(); bs[wt1] = mk("control_wait", inputs={"DURATION": num(1)})
    dec_t = gen(); bs[dec_t] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["남은시간", V_TIME_LEFT]})

    # if 남은시간 <= 0 → 게임오버=1, broadcast 게임종료
    t_v = vrep("남은시간", V_TIME_LEFT)
    # "<= 0"  via  "남은시간 < 1"
    cond_end = cmp_op("operator_lt", t_v, 1)

    set_go = gen(); bs[set_go] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임오버", V_GAMEOVER]})
    bm_over = gen(); bs[bm_over] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]}, shadow=True)
    bc_over = gen(); bs[bc_over] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_over]})
    bs[bm_over]["parent"] = bc_over
    chain([(set_go, bs[set_go]), (bc_over, bs[bc_over])])

    if_end = gen(); bs[if_end] = mk("control_if",
        inputs={"CONDITION": [2, cond_end], "SUBSTACK": [2, set_go]})
    bs[cond_end]["parent"] = if_end
    bs[set_go]["parent"] = if_end

    chain([(wt1, bs[wt1]), (dec_t, bs[dec_t]), (if_end, bs[if_end])])
    rep_t = gen(); bs[rep_t] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over], "SUBSTACK": [2, wt1]})
    bs[cond_over]["parent"] = rep_t
    bs[wt1]["parent"] = rep_t

    chain([(h2, bs[h2]), (rep_t, bs[rep_t])])

    # ===== 시작 → spawn dispatcher (every 1.5s, if CloneCount < 4, broadcast 스폰) =====
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=300,
        fields={"BROADCAST_OPTION": ["시작", BR_START]})

    go_v2 = vrep("게임오버", V_GAMEOVER)
    cond_over2 = cmp_op("operator_equals", go_v2, 1)

    # Build spawn body: set SpawnX, SpawnY, SpawnN0, SpawnT randomly, broadcast 스폰
    cc_v = vrep("CloneCount", V_CLONE_COUNT)
    cond_room = cmp_op("operator_lt", cc_v, MAX_ORE)

    rnd_x = gen(); bs[rnd_x] = mk("operator_random",
        inputs={"FROM": num(-200), "TO": num(200)})
    set_sx = gen(); bs[set_sx] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_x)},
        fields={"VARIABLE": ["SpawnX", V_SPAWN_X]})
    bs[rnd_x]["parent"] = set_sx

    rnd_y = gen(); bs[rnd_y] = mk("operator_random",
        inputs={"FROM": num(-150), "TO": num(90)})
    set_sy = gen(); bs[set_sy] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_y)},
        fields={"VARIABLE": ["SpawnY", V_SPAWN_Y]})
    bs[rnd_y]["parent"] = set_sy

    rnd_n0 = gen(); bs[rnd_n0] = mk("operator_random",
        inputs={"FROM": num(50), "TO": num(200)})
    set_n0 = gen(); bs[set_n0] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_n0)},
        fields={"VARIABLE": ["SpawnN0", V_SPAWN_N0]})
    bs[rnd_n0]["parent"] = set_n0

    # T = random(10,50)/10  → 1.0 ~ 5.0
    rnd_t_raw = gen(); bs[rnd_t_raw] = mk("operator_random",
        inputs={"FROM": num(10), "TO": num(50)})
    div_t = op("operator_divide", rnd_t_raw, 10)
    set_t = gen(); bs[set_t] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_t)},
        fields={"VARIABLE": ["SpawnT", V_SPAWN_T]})
    bs[div_t]["parent"] = set_t

    bm_sp = gen(); bs[bm_sp] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["스폰", BR_SPAWN_MORE]}, shadow=True)
    bc_sp = gen(); bs[bc_sp] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_sp]})
    bs[bm_sp]["parent"] = bc_sp

    chain([(set_sx, bs[set_sx]), (set_sy, bs[set_sy]),
           (set_n0, bs[set_n0]), (set_t, bs[set_t]),
           (bc_sp, bs[bc_sp])])

    if_room = gen(); bs[if_room] = mk("control_if",
        inputs={"CONDITION": [2, cond_room], "SUBSTACK": [2, set_sx]})
    bs[cond_room]["parent"] = if_room
    bs[set_sx]["parent"] = if_room

    wt_sp = gen(); bs[wt_sp] = mk("control_wait", inputs={"DURATION": num(1.5)})
    chain([(if_room, bs[if_room]), (wt_sp, bs[wt_sp])])

    rep_sp = gen(); bs[rep_sp] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over2], "SUBSTACK": [2, if_room]})
    bs[cond_over2]["parent"] = rep_sp
    bs[if_room]["parent"] = rep_sp

    # 첫 스폰을 즉시 부르기 위해 wait 없이 시작
    chain([(h3, bs[h3]), (rep_sp, bs[rep_sp])])

    return bs

# ---------------------------------------------------------------------------
# 광물 (Ore) sprite blocks — clone-driven decaying ore
# ---------------------------------------------------------------------------
def gen_costume_menu(bs, name):
    bid = gen()
    bs[bid] = mk("looks_costume", shadow=True,
                 fields={"COSTUME": [name, None]})
    return bid

def build_ore_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop, timer = make_helpers(bs)

    # ===== when flag clicked: hide original =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz])])

    # ===== 스폰 broadcast → original spawns one clone =====
    # 클론도 같은 이벤트를 받지만, 클론에서 create-clone-of-myself 를 호출하면
    # Stage 의 CloneCount<4 가드가 이미 차면 broadcast 자체가 안 오므로 무해.
    # 단, 한 broadcast 당 (현재 활성 인스턴스 수)만큼 clone 이 만들어진다.
    # → 안전을 위해, 클론은 if (현재시간==출생시간) 같은 조건이 아니라,
    #   "한 번도 초기화되지 않은 instance" 만 clone 하도록 하는 게 정석이지만,
    #   여기서는 Stage 가 폭주를 막아주므로 그대로 진행.
    h_sp = gen(); bs[h_sp] = mk("event_whenbroadcastreceived", top=True,
        x=20, y=180,
        fields={"BROADCAST_OPTION": ["스폰", BR_SPAWN_MORE]})

    # Only spawn if I'm the original (V_T_BIRTH == 0 means "uninitialized").
    # Sprite-local var V_T_BIRTH is per-clone; original keeps its 0.
    tb_v = vrep("출생시간", V_T_BIRTH)
    cond_orig = cmp_op("operator_equals", tb_v, 0)

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone

    if_orig = gen(); bs[if_orig] = mk("control_if",
        inputs={"CONDITION": [2, cond_orig], "SUBSTACK": [2, cclone]})
    bs[cond_orig]["parent"] = if_orig
    bs[cclone]["parent"] = if_orig

    chain([(h_sp, bs[h_sp]), (if_orig, bs[if_orig])])

    # ===== when I start as a clone =====
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=320, y=20)

    # Copy SpawnX/Y/N0/T into clone-local vars
    sx_v = vrep("SpawnX", V_SPAWN_X)
    sy_v = vrep("SpawnY", V_SPAWN_Y)
    g_init = gen(); bs[g_init] = mk("motion_gotoxy",
        inputs={"X": slot(sx_v), "Y": slot(sy_v)})
    bs[sx_v]["parent"] = g_init; bs[sy_v]["parent"] = g_init

    sn0_v = vrep("SpawnN0", V_SPAWN_N0)
    set_n0 = gen(); bs[set_n0] = mk("data_setvariableto",
        inputs={"VALUE": slot(sn0_v)},
        fields={"VARIABLE": ["N0", V_N0]})
    bs[sn0_v]["parent"] = set_n0

    st_v = vrep("SpawnT", V_SPAWN_T)
    set_thalf = gen(); bs[set_thalf] = mk("data_setvariableto",
        inputs={"VALUE": slot(st_v)},
        fields={"VARIABLE": ["T_half", V_T_HALFLIFE]})
    bs[st_v]["parent"] = set_thalf

    # V_T_BIRTH = sensing_timer
    timer_birth = timer()
    set_tb = gen(); bs[set_tb] = mk("data_setvariableto",
        inputs={"VALUE": slot(timer_birth)},
        fields={"VARIABLE": ["출생시간", V_T_BIRTH]})
    bs[timer_birth]["parent"] = set_tb

    # V_MASS_NOW = V_N0
    n0_v = vrep("N0", V_N0)
    set_mass = gen(); bs[set_mass] = mk("data_setvariableto",
        inputs={"VALUE": slot(n0_v)},
        fields={"VARIABLE": ["질량", V_MASS_NOW]})
    bs[n0_v]["parent"] = set_mass

    # V_LIFE_LEFT = T_half · 4.32 (rough: log2(1/0.05)=4.32) 정도로 초기화
    set_life = gen(); bs[set_life] = mk("data_setvariableto",
        inputs={"VALUE": num(0)},
        fields={"VARIABLE": ["수명", V_LIFE_LEFT]})

    cost_fresh = gen(); bs[cost_fresh] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen_costume_menu(bs, "fresh")]})
    sz_init = gen(); bs[sz_init] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    show = gen(); bs[show] = mk("looks_show")
    inc_cc = gen(); bs[inc_cc] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["CloneCount", V_CLONE_COUNT]})

    # ----- decay loop body -----
    # Δt = timer - V_T_BIRTH
    tmr_a = timer()
    tb_a = vrep("출생시간", V_T_BIRTH)
    dt_a = op("operator_subtract", tmr_a, tb_a)

    # x = Δt / V_T_HALFLIFE
    th_a = vrep("T_half", V_T_HALFLIFE)
    x_arg = op("operator_divide", dt_a, th_a)

    # exp_arg = x · V_LN_HALF
    ln_h_a = vrep("ln(0.5)", V_LN_HALF)
    exp_arg = op("operator_multiply", x_arg, ln_h_a)

    # ratio = e^(exp_arg)   ← 0.5^(Δt/T)
    ratio = mathop("e ^", exp_arg)

    # mass = N0 · ratio
    n0_a = vrep("N0", V_N0)
    mass_calc = op("operator_multiply", n0_a, ratio)
    set_mass_loop = gen(); bs[set_mass_loop] = mk("data_setvariableto",
        inputs={"VALUE": slot(mass_calc)},
        fields={"VARIABLE": ["질량", V_MASS_NOW]})
    bs[mass_calc]["parent"] = set_mass_loop

    # size = 100 · sqrt(mass / N0)  (=100·sqrt(ratio))  use ratio directly via fresh recompute
    # sqrt expects 0..1 → result 0..1 → ·100 → 0..100
    # Reuse the same idea: ratio2 = mass/N0 then sqrt then ·100
    mass_v = vrep("질량", V_MASS_NOW)
    n0_b = vrep("N0", V_N0)
    ratio2 = op("operator_divide", mass_v, n0_b)
    sqrt_r = mathop("sqrt", ratio2)
    size_calc = op("operator_multiply", sqrt_r, 100)
    set_size_loop = gen(); bs[set_size_loop] = mk("looks_setsizeto",
        inputs={"SIZE": slot(size_calc)})
    bs[size_calc]["parent"] = set_size_loop

    # V_LIFE_LEFT = round( T_half · log( mass / (0.05·N0) ) / log(2) )
    # Use log (base 10) for both — change of base
    mass_v2 = vrep("질량", V_MASS_NOW)
    n0_c = vrep("N0", V_N0)
    n0_05 = op("operator_multiply", n0_c, 0.05)   # 0.05 · N0  = N_min
    inner = op("operator_divide", mass_v2, n0_05)
    log_num = mathop("log", inner)
    log_2 = mathop("log", 2)
    log2_val = op("operator_divide", log_num, log_2)
    th_b = vrep("T_half", V_T_HALFLIFE)
    life_raw = op("operator_multiply", th_b, log2_val)
    # round to 1 decimal via (round(x·10)/10)
    times10 = op("operator_multiply", life_raw, 10)
    rounded = gen(); bs[rounded] = mk("operator_round", inputs={"NUM": slot(times10)})
    bs[times10]["parent"] = rounded
    life_disp = op("operator_divide", rounded, 10)
    set_life_loop = gen(); bs[set_life_loop] = mk("data_setvariableto",
        inputs={"VALUE": slot(life_disp)},
        fields={"VARIABLE": ["수명", V_LIFE_LEFT]})
    bs[life_disp]["parent"] = set_life_loop

    # if mass/N0 < 0.30 → switch costume to decayed
    mass_v3 = vrep("질량", V_MASS_NOW)
    n0_d = vrep("N0", V_N0)
    ratio3 = op("operator_divide", mass_v3, n0_d)
    cond_dim = cmp_op("operator_lt", ratio3, 0.30)
    cost_dim = gen(); bs[cost_dim] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen_costume_menu(bs, "decayed")]})
    if_dim = gen(); bs[if_dim] = mk("control_if",
        inputs={"CONDITION": [2, cond_dim], "SUBSTACK": [2, cost_dim]})
    bs[cond_dim]["parent"] = if_dim
    bs[cost_dim]["parent"] = if_dim

    # if mass < 0.05·N0 → vanish: play vanish.wav, CloneCount-=1, delete
    mass_v4 = vrep("질량", V_MASS_NOW)
    n0_e = vrep("N0", V_N0)
    n0_e_05 = op("operator_multiply", n0_e, 0.05)
    cond_dead = cmp_op("operator_lt", mass_v4, n0_e_05)

    snm_v = gen(); bs[snm_v] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["vanish", None]}, shadow=True)
    snd_v = gen(); bs[snd_v] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_v]})
    bs[snm_v]["parent"] = snd_v

    dec_cc = gen(); bs[dec_cc] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["CloneCount", V_CLONE_COUNT]})
    del_self = gen(); bs[del_self] = mk("control_delete_this_clone")
    chain([(snd_v, bs[snd_v]), (dec_cc, bs[dec_cc]), (del_self, bs[del_self])])

    if_dead = gen(); bs[if_dead] = mk("control_if",
        inputs={"CONDITION": [2, cond_dead], "SUBSTACK": [2, snd_v]})
    bs[cond_dead]["parent"] = if_dead
    bs[snd_v]["parent"] = if_dead

    wt_loop = gen(); bs[wt_loop] = mk("control_wait", inputs={"DURATION": num(0.1)})

    # loop body chain
    chain([(set_mass_loop, bs[set_mass_loop]),
           (set_size_loop, bs[set_size_loop]),
           (set_life_loop, bs[set_life_loop]),
           (if_dim, bs[if_dim]),
           (if_dead, bs[if_dead]),
           (wt_loop, bs[wt_loop])])

    # repeat until V_GAMEOVER = 1
    go_v_c = vrep("게임오버", V_GAMEOVER)
    cond_over_c = cmp_op("operator_equals", go_v_c, 1)
    rep_decay = gen(); bs[rep_decay] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_over_c], "SUBSTACK": [2, set_mass_loop]})
    bs[cond_over_c]["parent"] = rep_decay
    bs[set_mass_loop]["parent"] = rep_decay

    chain([(ch, bs[ch]),
           (g_init, bs[g_init]),
           (set_n0, bs[set_n0]),
           (set_thalf, bs[set_thalf]),
           (set_tb, bs[set_tb]),
           (set_mass, bs[set_mass]),
           (set_life, bs[set_life]),
           (cost_fresh, bs[cost_fresh]),
           (sz_init, bs[sz_init]),
           (show, bs[show]),
           (inc_cc, bs[inc_cc]),
           (rep_decay, bs[rep_decay])])

    # ===== when this sprite (clone) clicked: mine =====
    cl = gen(); bs[cl] = mk("event_whenthisspriteclicked", top=True, x=620, y=20)

    go_v_k = vrep("게임오버", V_GAMEOVER)
    cond_alive_k = cmp_op("operator_equals", go_v_k, 0)

    # 점수 += round(질량)
    mass_pk = vrep("질량", V_MASS_NOW)
    round_m = gen(); bs[round_m] = mk("operator_round", inputs={"NUM": slot(mass_pk)})
    bs[mass_pk]["parent"] = round_m
    add_score = gen(); bs[add_score] = mk("data_changevariableby",
        inputs={"VALUE": slot(round_m)},
        fields={"VARIABLE": ["점수", V_SCORE]})
    bs[round_m]["parent"] = add_score

    inc_picked = gen(); bs[inc_picked] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["처치", V_PICKED]})
    snm_pk = gen(); bs[snm_pk] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pick", None]}, shadow=True)
    snd_pk = gen(); bs[snd_pk] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_pk]})
    bs[snm_pk]["parent"] = snd_pk

    dec_cc_k = gen(); bs[dec_cc_k] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["CloneCount", V_CLONE_COUNT]})
    del_me_k = gen(); bs[del_me_k] = mk("control_delete_this_clone")
    chain([(add_score, bs[add_score]),
           (inc_picked, bs[inc_picked]),
           (snd_pk, bs[snd_pk]),
           (dec_cc_k, bs[dec_cc_k]),
           (del_me_k, bs[del_me_k])])

    if_kill = gen(); bs[if_kill] = mk("control_if",
        inputs={"CONDITION": [2, cond_alive_k], "SUBSTACK": [2, add_score]})
    bs[cond_alive_k]["parent"] = if_kill
    bs[add_score]["parent"] = if_kill

    chain([(cl, bs[cl]), (if_kill, bs[if_kill])])

    # ===== on 게임종료: stop visual updates (clone deletes itself) =====
    h_go = gen(); bs[h_go] = mk("event_whenbroadcastreceived", top=True,
        x=620, y=400,
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]})
    cost_dim2 = gen(); bs[cost_dim2] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, gen_costume_menu(bs, "decayed")]})
    chain([(h_go, bs[h_go]), (cost_dim2, bs[cost_dim2])])

    return bs

# ---------------------------------------------------------------------------
# Result banner sprite
# ---------------------------------------------------------------------------
def build_result_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop, timer = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    go_v = vrep("게임오버", V_GAMEOVER)
    cond_dead = cmp_op("operator_equals", go_v, 1)
    wait_dead = gen(); bs[wait_dead] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_dead]})
    bs[cond_dead]["parent"] = wait_dead

    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]),
           (front, bs[front]), (wait_dead, bs[wait_dead]), (show, bs[show])])
    return bs

# ---------------------------------------------------------------------------
# Sound synthesis
# ---------------------------------------------------------------------------
def write_wav(path, samples_i16, rate=SAMPLE_RATE):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples_i16))

def gen_pick_wav():
    """Bright click: 1200Hz + 880Hz harmonic, 80 ms exp decay."""
    dur = 0.08
    n = int(dur * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 28.0)
        s = math.sin(2*math.pi*1200*t) * 0.5 + math.sin(2*math.pi*880*t) * 0.3
        out.append(int(max(-1, min(1, s*env)) * 27000))
    return out

def gen_vanish_wav():
    """Soft low thump: 200→140Hz glide, 150 ms exp decay."""
    dur = 0.15
    n = int(dur * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 200 - 60 * (t / dur)
        env = math.exp(-t * 18.0)
        s = math.sin(2*math.pi*freq*t) * 0.7
        out.append(int(max(-1, min(1, s*env)) * 25000))
    return out

def gen_tick_wav():
    """Optional countdown ping: 1500Hz, 50 ms."""
    dur = 0.05
    n = int(dur * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 40.0)
        s = math.sin(2*math.pi*1500*t) * 0.45
        out.append(int(max(-1, min(1, s*env)) * 26000))
    return out

# ---------------------------------------------------------------------------
# Assemble project
# ---------------------------------------------------------------------------
def wav_meta(path):
    with wave.open(path, "rb") as w:
        return w.getnframes(), w.getframerate()

def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)
    if not os.path.exists(ASSETS): os.makedirs(ASSETS)

    # --- synthesize WAVs if missing ---
    pick_path   = os.path.join(ASSETS, "pick.wav")
    vanish_path = os.path.join(ASSETS, "vanish.wav")
    tick_path   = os.path.join(ASSETS, "tick.wav")
    if not os.path.exists(pick_path):   write_wav(pick_path,   gen_pick_wav())
    if not os.path.exists(vanish_path): write_wav(vanish_path, gen_vanish_wav())
    if not os.path.exists(tick_path):   write_wav(tick_path,   gen_tick_wav())

    # --- SVG assets ---
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)
    of_md5 = md5_bytes(ORE_FRESH.encode("utf-8"))
    with open(f"{WORK}/{of_md5}.svg", "w", encoding="utf-8") as f:
        f.write(ORE_FRESH)
    od_md5 = md5_bytes(ORE_DECAYED.encode("utf-8"))
    with open(f"{WORK}/{od_md5}.svg", "w", encoding="utf-8") as f:
        f.write(ORE_DECAYED)
    rs_md5 = md5_bytes(RESULT_SVG.encode("utf-8"))
    with open(f"{WORK}/{rs_md5}.svg", "w", encoding="utf-8") as f:
        f.write(RESULT_SVG)

    # --- WAV assets ---
    def copy_sound(name):
        src = os.path.join(ASSETS, f"{name}.wav")
        with open(src, "rb") as f: data = f.read()
        h = md5_bytes(data)
        with open(f"{WORK}/{h}.wav", "wb") as f: f.write(data)
        frames, rate = wav_meta(src)
        return {"name": name, "assetId": h, "dataFormat": "wav",
                "format": "", "rate": rate, "sampleCount": frames,
                "md5ext": f"{h}.wav"}
    pick_snd   = copy_sound("pick")
    vanish_snd = copy_sound("vanish")
    tick_snd   = copy_sound("tick")

    # --- build block dicts ---
    stage_blocks  = build_stage_blocks()
    ore_blocks    = build_ore_blocks()
    result_blocks = build_result_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:       ["점수",       0],
            V_TIME_LEFT:   ["남은시간",   GAME_DURATION],
            V_PICKED:      ["처치",       0],
            V_GAMEOVER:    ["게임오버",   0],
            V_SPAWN_X:     ["SpawnX",     0],
            V_SPAWN_Y:     ["SpawnY",     0],
            V_SPAWN_N0:    ["SpawnN0",    100],
            V_SPAWN_T:     ["SpawnT",     2],
            V_LN_HALF:     ["ln(0.5)",    LN_HALF],
            V_LOG_HALF:    ["log(0.5)",   LOG_HALF],
            V_CLONE_COUNT: ["CloneCount", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:      "시작",
            BR_SPAWN_MORE: "스폰",
            BR_GAMEOVER:   "게임종료",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "mine", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pick_snd, vanish_snd, tick_snd],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None,
    }

    ore = {
        "isStage": False, "name": "광물",
        "variables": {
            V_N0:         ["N0",       100],
            V_T_HALFLIFE: ["T_half",   2],
            V_T_BIRTH:    ["출생시간", 0],
            V_MASS_NOW:   ["질량",     100],
            V_LIFE_LEFT:  ["수명",     0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": ore_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "fresh", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": of_md5, "md5ext": f"{of_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "decayed", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": od_md5, "md5ext": f"{od_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
        ],
        "sounds": [pick_snd, vanish_snd, tick_snd],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }

    result = {
        "isStage": False, "name": "결과",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": result_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": rs_md5, "md5ext": f"{rs_md5}.svg",
            "rotationCenterX": 190, "rotationCenterY": 85,
        }],
        "sounds": [pick_snd],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 2000, "isDiscrete": True},
        {"id": V_TIME_LEFT, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "남은시간"}, "spriteName": None,
         "value": GAME_DURATION, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 60, "isDiscrete": True},
        {"id": V_PICKED, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "처치"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 125,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_CLONE_COUNT, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "CloneCount"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 380, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 8, "isDiscrete": True},
        {"id": V_LN_HALF, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "ln(0.5)"}, "spriteName": None,
         "value": LN_HALF, "width": 0, "height": 0, "x": 380, "y": 95,
         "visible": False, "sliderMin": -1, "sliderMax": 0, "isDiscrete": False},
    ]

    project = {
        "targets": [stage, ore, result],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "radioactive-mine-builder"},
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
