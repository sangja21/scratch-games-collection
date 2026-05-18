#!/usr/bin/env python3
"""복리 카드 게임 — 매 턴 이자율 카드를 골라 자산을 굴려 10턴 안에 10배 달성.

학습 포인트:
  - A = P · (1+r)^n  — 매 턴 카드 선택 = × (1+r) 한 번
  - x^(1/n) = e^(ln(x)/n)  — "10배까지 필요한 평균 r" HUD 가 이 식을 내부적으로 계산
  - 기댓값 E[r] = p · r_success + (1-p) · r_fail — 카드별 라벨로 표시
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "복리_카드_게임.sb3")

# -------- Background SVG (480x360): dark felt + HUD strip --------
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <radialGradient id="felt" cx="0.5" cy="0.5" r="0.7">
      <stop offset="0%"   stop-color="#1B5E20"/>
      <stop offset="100%" stop-color="#0B2F10"/>
    </radialGradient>
    <linearGradient id="hud" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0D1B0F"/>
      <stop offset="100%" stop-color="#1B5E20"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#felt)"/>
  <!-- HUD strip -->
  <rect x="0" y="0" width="480" height="74" fill="url(#hud)" opacity="0.92"/>
  <line x1="0" y1="74" x2="480" y2="74" stroke="#FFD54F" stroke-width="1" opacity="0.6"/>
  <!-- Decorative chip stack icons in corners -->
  <g opacity="0.18">
    <circle cx="35"  cy="330" r="14" fill="#FFD54F"/>
    <circle cx="35"  cy="320" r="14" fill="#E53935"/>
    <circle cx="35"  cy="310" r="14" fill="#1E88E5"/>
    <circle cx="445" cy="330" r="14" fill="#FFD54F"/>
    <circle cx="445" cy="320" r="14" fill="#E53935"/>
    <circle cx="445" cy="310" r="14" fill="#1E88E5"/>
  </g>
  <!-- HUD labels (variable monitors draw the values on top) -->
  <text x="12"  y="20" fill="#FFE082" font-family="monospace" font-size="13" font-weight="bold">복리 카드 게임</text>
  <text x="12"  y="40" fill="#A5D6A7" font-family="monospace" font-size="10">목표: 10턴 안에 자산을 10배로</text>
  <text x="12"  y="55" fill="#A5D6A7" font-family="monospace" font-size="10">공식: A = P · (1+r)^n</text>
  <!-- Card slot guides -->
  <g stroke="#FFD54F" stroke-width="0.8" stroke-dasharray="3,3" fill="none" opacity="0.35">
    <rect x="50"  y="170" width="80" height="110" rx="8" ry="8"/>
    <rect x="200" y="170" width="80" height="110" rx="8" ry="8"/>
    <rect x="350" y="170" width="80" height="110" rx="8" ry="8"/>
  </g>
  <text x="240" y="335" fill="#FFE082" font-family="monospace" font-size="11" text-anchor="middle">카드를 클릭해 자산을 굴리세요</text>
</svg>"""

# -------- Card SVG (80x110): blank card with golden border --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="110" viewBox="0 0 80 110">
  <defs>
    <linearGradient id="cardbg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#FFFDE7"/>
      <stop offset="100%" stop-color="#FFE082"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="76" height="106" rx="9" ry="9"
        fill="url(#cardbg)" stroke="#B8860B" stroke-width="2"/>
  <rect x="6" y="6" width="68" height="98" rx="6" ry="6"
        fill="none" stroke="#D4AF37" stroke-width="0.8" opacity="0.7"/>
  <!-- decorative dollar sign behind text -->
  <text x="40" y="68" font-family="serif" font-size="48" font-weight="bold"
        fill="#B8860B" opacity="0.18" text-anchor="middle">$</text>
  <!-- four corner pips -->
  <circle cx="14" cy="14"  r="2" fill="#B8860B"/>
  <circle cx="66" cy="14"  r="2" fill="#B8860B"/>
  <circle cx="14" cy="96"  r="2" fill="#B8860B"/>
  <circle cx="66" cy="96"  r="2" fill="#B8860B"/>
</svg>"""

# -------- NewTurn button SVG --------
BUTTON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="140" height="40" viewBox="0 0 140 40">
  <rect x="2" y="2" width="136" height="36" rx="18" ry="18"
        fill="#1565C0" stroke="#FFD54F" stroke-width="2"/>
  <text x="70" y="26" fill="#FFE082" font-family="sans-serif"
        font-size="15" font-weight="bold" text-anchor="middle">다음 턴 ▶</text>
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
    def bool_op(opcode, a, b_):
        bid = gen()
        bs[bid] = mk(opcode, inputs={"OPERAND1": [2, a], "OPERAND2": [2, b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid
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
    def mathop(name, inner):
        bid = gen()
        ins = {"NUM": slot(inner) if isinstance(inner, str) else num(inner)}
        bs[bid] = mk("operator_mathop",
            inputs=ins, fields={"OPERATOR": [name, None]})
        if isinstance(inner, str):
            bs[inner]["parent"] = bid
        return bid
    def join(a, b_):
        # a / b_ : block-id (existing block to plug in)  OR  python str (literal text)
        # We distinguish by checking whether the value is a key in `bs` (i.e., an existing block).
        bid = gen()
        ins = {}
        for key, val in [("STRING1", a), ("STRING2", b_)]:
            if isinstance(val, str) and val in bs:
                ins[key] = slot(val, sk=10, sv="")
            else:
                ins[key] = text_lit(val)
        bs[bid] = mk("operator_join", inputs=ins)
        for v in (a, b_):
            if isinstance(v, str) and v in bs:
                bs[v]["parent"] = bid
        return bid
    return vrep, op, bool_op, cmp_op, mathop, join

# ===================== Variable / Broadcast IDs =====================
# global
V_P        = "varP001"        # 현재 자산
V_GOAL     = "varGoal002"     # 목표 자산
V_TURN     = "varTurn003"     # 현재 턴
V_MAXTURN  = "varMaxTurn004"  # 최대 턴
V_STATE    = "varState005"    # 1 진행 / 0 종료
V_RESULT   = "varResult006"   # 1 승 / -1 패 / 0
V_NEED_R   = "varNeedR007"    # 필요 r (%, 소수1자리)
V_LAST_MSG = "varLastMsg008"  # 마지막 결과 메시지

# Button-local: 카드 선택용 임시 슬롯 + 인덱스
V_PICK     = "varPick009"     # 0..7 카드 풀 인덱스 (버튼 내 임시)

# Card clone-local
V_CARD_SLOT = "varCSlot010"   # 슬롯 1/2/3
V_CARD_R    = "varCR011"      # 이자율 (예: 0.15)
V_CARD_P    = "varCP012"      # 성공 확률 (예: 0.6)
V_CARD_E    = "varCE013"      # 기댓값 E[r] (%) 표시용

BR_START         = "brStart001"
BR_NEW_TURN      = "brNewTurn002"
BR_CARD_CHOSEN   = "brCardChosen003"
BR_GAMEOVER      = "brGameOver004"

# ===================== Card Pool =====================
# (r, p, E_percent_label)
# E = p·r + (1-p)·(-0.5)   *100  소수 1자리 반올림
CARD_POOL = [
    ( 0.05, 1.00,  5.0),
    ( 0.08, 0.95,  5.1),
    ( 0.12, 0.85,  2.7),
    ( 0.20, 0.70, -1.0),
    ( 0.35, 0.55, -3.5),
    ( 0.50, 0.40,-10.0),
    ( 1.00, 0.25,-12.5),
    (-0.03, 1.00, -3.0),
]

# ===================== STAGE blocks =====================
def build_stage_blocks():
    bs = {}
    vrep, op, bool_op, cmp_op, mathop, join = make_helpers(bs)

    # === when flag clicked: init game ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    s_p = gen(); bs[s_p] = mk("data_setvariableto",
        inputs={"VALUE": num(1000)}, fields={"VARIABLE": ["자산", V_P]})
    s_goal = gen(); bs[s_goal] = mk("data_setvariableto",
        inputs={"VALUE": num(10000)}, fields={"VARIABLE": ["목표", V_GOAL]})
    s_turn = gen(); bs[s_turn] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["턴", V_TURN]})
    s_maxt = gen(); bs[s_maxt] = mk("data_setvariableto",
        inputs={"VALUE": num(10)}, fields={"VARIABLE": ["최대턴", V_MAXTURN]})
    s_state = gen(); bs[s_state] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    s_res = gen(); bs[s_res] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["결과", V_RESULT]})
    s_msg = gen(); bs[s_msg] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("게임 시작! 카드를 골라보세요")},
        fields={"VARIABLE": ["메시지", V_LAST_MSG]})
    s_need = gen(); bs[s_need] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["필요r(%)", V_NEED_R]})

    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bcast = gen(); bs[bcast] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm]})
    bs[bm]["parent"] = bcast

    bm2 = gen(); bs[bm2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새턴", BR_NEW_TURN]}, shadow=True)
    bcast2 = gen(); bs[bcast2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm2]})
    bs[bm2]["parent"] = bcast2

    chain([(h,bs[h]),(s_p,bs[s_p]),(s_goal,bs[s_goal]),(s_turn,bs[s_turn]),
           (s_maxt,bs[s_maxt]),(s_state,bs[s_state]),(s_res,bs[s_res]),
           (s_msg,bs[s_msg]),(s_need,bs[s_need]),(bcast,bs[bcast]),(bcast2,bs[bcast2])])

    # === Forever HUD updater: 필요 r = ((goal/P)^(1/n_left) - 1)·100 ===
    # using e^(ln(ratio)/n_left)
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    # body block ID will be the head of an if-state==1 chain.
    # n_left = V_MAXTURN - V_TURN + 1
    rmax = vrep("최대턴", V_MAXTURN)
    rturn = vrep("턴", V_TURN)
    diff = op("operator_subtract", rmax, rturn)
    n_left = op("operator_add", diff, 1)

    # ratio = V_GOAL / V_P
    rgoal = vrep("목표", V_GOAL)
    rp = vrep("자산", V_P)
    ratio = op("operator_divide", rgoal, rp)

    # ln_ratio
    ln_r = mathop("ln", ratio)
    # div_n = ln_ratio / n_left
    div_n = op("operator_divide", ln_r, n_left)
    # exp_r = e^(div_n)
    exp_r = mathop("e ^", div_n)
    # need = exp_r - 1
    need = op("operator_subtract", exp_r, 1)
    # need_pct = need · 100
    need_pct = op("operator_multiply", need, 100)
    # rounded to 1 decimal:  floor(need_pct·10 + 0.5)/10
    m10 = op("operator_multiply", need_pct, 10)
    a05 = op("operator_add", m10, 0.5)
    fl = mathop("floor", a05)
    final = op("operator_divide", fl, 10)

    set_need = gen(); bs[set_need] = mk("data_setvariableto",
        inputs={"VALUE": slot(final)},
        fields={"VARIABLE": ["필요r(%)", V_NEED_R]})
    bs[final]["parent"] = set_need

    # if V_STATE = 1 and V_P > 0: set_need else skip
    rs1 = vrep("게임상태", V_STATE)
    cond_s1 = cmp_op("operator_equals", rs1, 1)
    rp2 = vrep("자산", V_P)
    cond_p_pos = cmp_op("operator_gt", rp2, 0)
    cond_and = bool_op("operator_and", cond_s1, cond_p_pos)

    if_blk = gen(); bs[if_blk] = mk("control_if",
        inputs={"CONDITION":[2, cond_and], "SUBSTACK":[2, set_need]})
    bs[cond_and]["parent"] = if_blk
    bs[set_need]["parent"] = if_blk

    wt_hud = gen(); bs[wt_hud] = mk("control_wait", inputs={"DURATION": num(0.15)})
    chain([(if_blk, bs[if_blk]), (wt_hud, bs[wt_hud])])
    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, if_blk]})
    bs[if_blk]["parent"] = fv

    chain([(h2, bs[h2]), (fv, bs[fv])])
    return bs


# ===================== BUTTON sprite =====================
# - On flag: show, position
# - On BR_NEW_TURN: spawn 3 card clones (after picking 3 random card-pool indices)
def build_button_blocks():
    bs = {}
    vrep, op, bool_op, cmp_op, mathop, join = make_helpers(bs)

    # === flag clicked: position + size + show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-150)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(sh,bs[sh])])

    # === when received 새턴: pick 3 random cards, spawn 3 clones ===
    bh = gen(); bs[bh] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["새턴", BR_NEW_TURN]})

    # Build a helper that, given a slot number 1..3, generates the spawn block sequence:
    #   - pick = random 1..8
    #   - for each pool index i: if pick = i → set V_CARD_R, V_CARD_P, V_CARD_E
    #   - set V_CARD_SLOT = slot_n
    #   - create clone of myself
    spawn_seq = []

    def make_spawn_for_slot(slot_n):
        # pick random 1..len(pool)
        rpick = gen(); bs[rpick] = mk("operator_random",
            inputs={"FROM": num(1), "TO": num(len(CARD_POOL))})
        set_pick = gen(); bs[set_pick] = mk("data_setvariableto",
            inputs={"VALUE": slot(rpick)}, fields={"VARIABLE": ["뽑힌카드", V_PICK]})
        bs[rpick]["parent"] = set_pick

        seq = [set_pick]

        for idx, (r_v, p_v, e_v) in enumerate(CARD_POOL, start=1):
            rpi = vrep("뽑힌카드", V_PICK)
            eq_i = cmp_op("operator_equals", rpi, idx)
            s_r = gen(); bs[s_r] = mk("data_setvariableto",
                inputs={"VALUE": num(r_v)}, fields={"VARIABLE": ["카드r", V_CARD_R]})
            s_p = gen(); bs[s_p] = mk("data_setvariableto",
                inputs={"VALUE": num(p_v)}, fields={"VARIABLE": ["카드p", V_CARD_P]})
            s_e = gen(); bs[s_e] = mk("data_setvariableto",
                inputs={"VALUE": num(e_v)}, fields={"VARIABLE": ["카드E", V_CARD_E]})
            chain([(s_r,bs[s_r]),(s_p,bs[s_p]),(s_e,bs[s_e])])
            ifb = gen(); bs[ifb] = mk("control_if",
                inputs={"CONDITION":[2, eq_i], "SUBSTACK":[2, s_r]})
            bs[eq_i]["parent"] = ifb
            bs[s_r]["parent"] = ifb
            seq.append(ifb)

        # set V_CARD_SLOT
        s_slot = gen(); bs[s_slot] = mk("data_setvariableto",
            inputs={"VALUE": num(slot_n)}, fields={"VARIABLE": ["카드슬롯", V_CARD_SLOT]})
        seq.append(s_slot)

        # create clone of self
        cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
            fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
        cclone = gen(); bs[cclone] = mk("control_create_clone_of",
            inputs={"CLONE_OPTION": [1, cmenu]})
        bs[cmenu]["parent"] = cclone
        seq.append(cclone)

        # small wait to let clone read globals
        wclone = gen(); bs[wclone] = mk("control_wait", inputs={"DURATION": num(0.08)})
        seq.append(wclone)

        return seq

    # short wait before spawning (let previous cards finish vanishing)
    pre_wait = gen(); bs[pre_wait] = mk("control_wait", inputs={"DURATION": num(0.25)})
    spawn_seq.append(pre_wait)

    for slot_n in (1, 2, 3):
        spawn_seq.extend(make_spawn_for_slot(slot_n))

    pairs = [(bh, bs[bh])] + [(bid, bs[bid]) for bid in spawn_seq]
    chain(pairs)

    # === when I start as a clone: this is the CARD logic (button clones are the cards) ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)

    # Step 1: switch costume to "카드" (cards use card costume; main button uses button costume)
    swc = gen(); bs[swc] = mk("looks_costume",
        fields={"COSTUME": ["카드", None]}, shadow=True)
    swcb = gen(); bs[swcb] = mk("looks_switchcostumeto",
        inputs={"COSTUME":[1, swc]})
    bs[swc]["parent"] = swcb

    # Step 2: size, position by slot
    sz_c = gen(); bs[sz_c] = mk("looks_setsizeto", inputs={"SIZE": num(110)})

    # slot positions
    SLOT_POS = [(-150, -30), (0, -30), (150, -30)]
    pos_ifs = []
    for s_n, (cx, cy) in enumerate(SLOT_POS, start=1):
        rss = vrep("카드슬롯", V_CARD_SLOT)
        eq_s = cmp_op("operator_equals", rss, s_n)
        g_pos = gen(); bs[g_pos] = mk("motion_gotoxy",
            inputs={"X": num(cx), "Y": num(cy)})
        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION":[2, eq_s], "SUBSTACK":[2, g_pos]})
        bs[eq_s]["parent"] = ifb
        bs[g_pos]["parent"] = ifb
        pos_ifs.append(ifb)

    show_c = gen(); bs[show_c] = mk("looks_show")

    # Step 3: build label "+15% / p:60 / E:+1.0"
    # parts: pct_r = round(V_CARD_R · 100), pct_p = round(V_CARD_P · 100), V_CARD_E already in %
    r_var = vrep("카드r", V_CARD_R)
    r_pct = op("operator_multiply", r_var, 100)
    r_round = gen(); bs[r_round] = mk("operator_round", inputs={"NUM": slot(r_pct)})
    bs[r_pct]["parent"] = r_round

    p_var = vrep("카드p", V_CARD_P)
    p_pct = op("operator_multiply", p_var, 100)
    p_round = gen(); bs[p_round] = mk("operator_round", inputs={"NUM": slot(p_pct)})
    bs[p_pct]["parent"] = p_round

    e_var = vrep("카드E", V_CARD_E)

    # "r=" + r_round + "% / p=" + p_round + "% / E=" + e_var + "%"
    j1 = join("r=", r_round)
    j2 = join(j1, "% / p=")
    j3 = join(j2, p_round)
    j4 = join(j3, "% / E=")
    j5 = join(j4, e_var)
    j6 = join(j5, "%")

    say_lbl = gen(); bs[say_lbl] = mk("looks_say",
        inputs={"MESSAGE": slot(j6, sk=10, sv="")})
    bs[j6]["parent"] = say_lbl

    # chain clone-start
    clone_seq = [(ch,bs[ch]),(swcb,bs[swcb]),(sz_c,bs[sz_c])]
    for ifb in pos_ifs:
        clone_seq.append((ifb, bs[ifb]))
    clone_seq += [(show_c,bs[show_c]),(say_lbl,bs[say_lbl])]
    chain(clone_seq)

    # === when this sprite clicked (clone gets this too) ===
    # The non-clone (parent) button also receives clicks. We need to differentiate.
    # Strategy: parent has V_CARD_SLOT == 0 (never set on parent). Clones have 1/2/3.
    # Only act if V_CARD_SLOT > 0 AND V_STATE == 1.
    cl = gen(); bs[cl] = mk("event_whenthisspriteclicked", top=True, x=900, y=20)

    # roll random 1..100
    rroll = gen(); bs[rroll] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(100)})
    # threshold = V_CARD_P · 100
    cp_var = vrep("카드p", V_CARD_P)
    thr = op("operator_multiply", cp_var, 100)
    cond_succ = cmp_op("operator_lt", rroll, thr)
    bs[rroll]["parent"] = cond_succ
    bs[thr]["parent"] = cond_succ

    # success branch: V_P = round(V_P · (1 + V_CARD_R)); play pop
    rp_succ = vrep("자산", V_P)
    cr_succ = vrep("카드r", V_CARD_R)
    one_plus_r = op("operator_add", 1, cr_succ)
    new_p_succ = op("operator_multiply", rp_succ, one_plus_r)
    rnd_succ = gen(); bs[rnd_succ] = mk("operator_round", inputs={"NUM": slot(new_p_succ)})
    bs[new_p_succ]["parent"] = rnd_succ
    set_p_succ = gen(); bs[set_p_succ] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_succ)}, fields={"VARIABLE": ["자산", V_P]})
    bs[rnd_succ]["parent"] = set_p_succ

    snm_ok = gen(); bs[snm_ok] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    pitch_ok = gen(); bs[pitch_ok] = mk("sound_seteffectto",
        inputs={"VALUE": num(40)}, fields={"EFFECT": ["PITCH", None]})
    snd_ok = gen(); bs[snd_ok] = mk("sound_play", inputs={"SOUND_MENU":[1, snm_ok]})
    bs[snm_ok]["parent"] = snd_ok

    set_msg_ok = gen(); bs[set_msg_ok] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("성공! 자산 × (1+r)")},
        fields={"VARIABLE": ["메시지", V_LAST_MSG]})

    chain([(pitch_ok,bs[pitch_ok]),(snd_ok,bs[snd_ok]),
           (set_p_succ,bs[set_p_succ]),(set_msg_ok,bs[set_msg_ok])])

    # fail branch: V_P = round(V_P · 0.5); play alarm
    rp_fail = vrep("자산", V_P)
    new_p_fail = op("operator_multiply", rp_fail, 0.5)
    rnd_fail = gen(); bs[rnd_fail] = mk("operator_round", inputs={"NUM": slot(new_p_fail)})
    bs[new_p_fail]["parent"] = rnd_fail
    set_p_fail = gen(); bs[set_p_fail] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_fail)}, fields={"VARIABLE": ["자산", V_P]})
    bs[rnd_fail]["parent"] = set_p_fail

    snm_no = gen(); bs[snm_no] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["alarm", None]}, shadow=True)
    pitch_no = gen(); bs[pitch_no] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT": ["PITCH", None]})
    snd_no = gen(); bs[snd_no] = mk("sound_play", inputs={"SOUND_MENU":[1, snm_no]})
    bs[snm_no]["parent"] = snd_no

    set_msg_no = gen(); bs[set_msg_no] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("실패... 자산 × 0.5")},
        fields={"VARIABLE": ["메시지", V_LAST_MSG]})

    chain([(pitch_no,bs[pitch_no]),(snd_no,bs[snd_no]),
           (set_p_fail,bs[set_p_fail]),(set_msg_no,bs[set_msg_no])])

    if_succ = gen(); bs[if_succ] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_succ],
                "SUBSTACK":[2, pitch_ok],
                "SUBSTACK2":[2, pitch_no]})
    bs[cond_succ]["parent"] = if_succ
    bs[pitch_ok]["parent"] = if_succ
    bs[pitch_no]["parent"] = if_succ

    # increment turn
    inc_turn = gen(); bs[inc_turn] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["턴", V_TURN]})

    # broadcast BR_CARD_CHOSEN
    cm = gen(); bs[cm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["카드선택됨", BR_CARD_CHOSEN]}, shadow=True)
    cb = gen(); bs[cb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, cm]})
    bs[cm]["parent"] = cb

    # check win: V_P >= V_GOAL  →  encode as V_P > (V_GOAL - 1) since 자산 is integer-rounded
    rp_w = vrep("자산", V_P)
    rgoal_w = vrep("목표", V_GOAL)
    goal_m1 = op("operator_subtract", rgoal_w, 1)
    cond_win = cmp_op("operator_gt", rp_w, goal_m1)

    # check lose: V_TURN > V_MAXTURN
    rt_l = vrep("턴", V_TURN)
    rmax_l = vrep("최대턴", V_MAXTURN)
    cond_lose = cmp_op("operator_gt", rt_l, rmax_l)

    # win branch
    set_res_w = gen(); bs[set_res_w] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["결과", V_RESULT]})
    set_state_w = gen(); bs[set_state_w] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    set_msg_w = gen(); bs[set_msg_w] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("승리! 10턴 안에 10배 달성!")},
        fields={"VARIABLE": ["메시지", V_LAST_MSG]})
    bm_gw = gen(); bs[bm_gw] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]}, shadow=True)
    bc_gw = gen(); bs[bc_gw] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_gw]})
    bs[bm_gw]["parent"] = bc_gw
    chain([(set_res_w,bs[set_res_w]),(set_state_w,bs[set_state_w]),
           (set_msg_w,bs[set_msg_w]),(bc_gw,bs[bc_gw])])

    # lose branch
    set_res_l = gen(); bs[set_res_l] = mk("data_setvariableto",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["결과", V_RESULT]})
    set_state_l = gen(); bs[set_state_l] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    set_msg_l = gen(); bs[set_msg_l] = mk("data_setvariableto",
        inputs={"VALUE": text_lit("실패... 10턴 종료")},
        fields={"VARIABLE": ["메시지", V_LAST_MSG]})
    bm_gl = gen(); bs[bm_gl] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]}, shadow=True)
    bc_gl = gen(); bs[bc_gl] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_gl]})
    bs[bm_gl]["parent"] = bc_gl
    chain([(set_res_l,bs[set_res_l]),(set_state_l,bs[set_state_l]),
           (set_msg_l,bs[set_msg_l]),(bc_gl,bs[bc_gl])])

    # else branch (continue): wait + broadcast 새턴
    cont_wait = gen(); bs[cont_wait] = mk("control_wait", inputs={"DURATION": num(0.5)})
    bm_nt = gen(); bs[bm_nt] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새턴", BR_NEW_TURN]}, shadow=True)
    bc_nt = gen(); bs[bc_nt] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1, bm_nt]})
    bs[bm_nt]["parent"] = bc_nt
    chain([(cont_wait,bs[cont_wait]),(bc_nt,bs[bc_nt])])

    # if cond_lose then lose else cont
    if_lose = gen(); bs[if_lose] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_lose],
                "SUBSTACK":[2, set_res_l],
                "SUBSTACK2":[2, cont_wait]})
    bs[cond_lose]["parent"] = if_lose
    bs[set_res_l]["parent"] = if_lose
    bs[cont_wait]["parent"] = if_lose

    # if cond_win then win else if_lose
    if_win = gen(); bs[if_win] = mk("control_if_else",
        inputs={"CONDITION":[2, cond_win],
                "SUBSTACK":[2, set_res_w],
                "SUBSTACK2":[2, if_lose]})
    bs[cond_win]["parent"] = if_win
    bs[set_res_w]["parent"] = if_win
    bs[if_lose]["parent"] = if_win

    # outer gate: only act if V_CARD_SLOT >= 1 AND V_STATE = 1
    rss_g = vrep("카드슬롯", V_CARD_SLOT)
    cond_slot = cmp_op("operator_gt", rss_g, 0)
    rstate_g = vrep("게임상태", V_STATE)
    cond_state = cmp_op("operator_equals", rstate_g, 1)
    cond_gate = bool_op("operator_and", cond_slot, cond_state)

    # body of gate: if_succ → inc_turn → cb (broadcast 카드선택됨) → if_win
    chain([(if_succ,bs[if_succ]),(inc_turn,bs[inc_turn]),(cb,bs[cb]),(if_win,bs[if_win])])

    gate = gen(); bs[gate] = mk("control_if",
        inputs={"CONDITION":[2, cond_gate], "SUBSTACK":[2, if_succ]})
    bs[cond_gate]["parent"] = gate
    bs[if_succ]["parent"] = gate

    chain([(cl,bs[cl]),(gate,bs[gate])])

    # === when received 카드선택됨 (clone): hide & delete this clone ===
    # If V_CARD_SLOT > 0 (i.e., this is a card clone), clear & delete.
    rh = gen(); bs[rh] = mk("event_whenbroadcastreceived", top=True, x=900, y=400,
        fields={"BROADCAST_OPTION": ["카드선택됨", BR_CARD_CHOSEN]})
    rss2 = vrep("카드슬롯", V_CARD_SLOT)
    cond_clone = cmp_op("operator_gt", rss2, 0)
    say_clr = gen(); bs[say_clr] = mk("looks_say", inputs={"MESSAGE": text_lit("")})
    hide_c = gen(); bs[hide_c] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")
    chain([(say_clr,bs[say_clr]),(hide_c,bs[hide_c]),(delc,bs[delc])])

    if_chose = gen(); bs[if_chose] = mk("control_if",
        inputs={"CONDITION":[2, cond_clone], "SUBSTACK":[2, say_clr]})
    bs[cond_clone]["parent"] = if_chose
    bs[say_clr]["parent"] = if_chose

    chain([(rh,bs[rh]),(if_chose,bs[if_chose])])

    # === when received 게임종료 (clone): also clear ===
    rg = gen(); bs[rg] = mk("event_whenbroadcastreceived", top=True, x=900, y=600,
        fields={"BROADCAST_OPTION": ["게임종료", BR_GAMEOVER]})
    rss3 = vrep("카드슬롯", V_CARD_SLOT)
    cond_clone2 = cmp_op("operator_gt", rss3, 0)
    say_clr2 = gen(); bs[say_clr2] = mk("looks_say", inputs={"MESSAGE": text_lit("")})
    hide_c2 = gen(); bs[hide_c2] = mk("looks_hide")
    delc2 = gen(); bs[delc2] = mk("control_delete_this_clone")
    chain([(say_clr2,bs[say_clr2]),(hide_c2,bs[hide_c2]),(delc2,bs[delc2])])

    if_end = gen(); bs[if_end] = mk("control_if",
        inputs={"CONDITION":[2, cond_clone2], "SUBSTACK":[2, say_clr2]})
    bs[cond_clone2]["parent"] = if_end
    bs[say_clr2]["parent"] = if_end

    chain([(rg,bs[rg]),(if_end,bs[if_end])])

    return bs


# ===================== assemble project =====================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    card_md5 = md5_bytes(CARD_SVG.encode("utf-8"))
    with open(f"{WORK}/{card_md5}.svg", "w", encoding="utf-8") as f:
        f.write(CARD_SVG)

    button_md5 = md5_bytes(BUTTON_SVG.encode("utf-8"))
    with open(f"{WORK}/{button_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BUTTON_SVG)

    # WAV assets
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    with open(f"{ASSETS}/alarm.wav", "rb") as f: alarm_bytes = f.read()
    alarm_md5 = md5_bytes(alarm_bytes)
    with open(f"{WORK}/{alarm_md5}.wav", "wb") as f: f.write(alarm_bytes)

    stage_blocks  = build_stage_blocks()
    button_blocks = build_button_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_P:        ["자산", 1000],
            V_GOAL:     ["목표", 10000],
            V_TURN:     ["턴", 1],
            V_MAXTURN:  ["최대턴", 10],
            V_STATE:    ["게임상태", 1],
            V_RESULT:   ["결과", 0],
            V_NEED_R:   ["필요r(%)", 0],
            V_LAST_MSG: ["메시지", "게임 시작! 카드를 골라보세요"],
        },
        "lists": {},
        "broadcasts": {
            BR_START:        "게임시작",
            BR_NEW_TURN:     "새턴",
            BR_CARD_CHOSEN:  "카드선택됨",
            BR_GAMEOVER:     "게임종료",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "테이블", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    button = {
        "isStage": False, "name": "버튼",
        "variables": {
            V_PICK:       ["뽑힌카드", 0],
            V_CARD_SLOT:  ["카드슬롯", 0],
            V_CARD_R:     ["카드r", 0],
            V_CARD_P:     ["카드p", 0],
            V_CARD_E:     ["카드E", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": button_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "버튼", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": button_md5, "md5ext": f"{button_md5}.svg",
                "rotationCenterX": 70, "rotationCenterY": 20
            },
            {
                "name": "카드", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": card_md5, "md5ext": f"{card_md5}.svg",
                "rotationCenterX": 40, "rotationCenterY": 55
            },
        ],
        "sounds": [
            {
                "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
                "format": "", "rate": 11025, "sampleCount": 258,
                "md5ext": f"{pop_md5}.wav"
            },
            {
                "name": "alarm", "assetId": alarm_md5, "dataFormat": "wav",
                "format": "", "rate": 11025, "sampleCount": 4410,
                "md5ext": f"{alarm_md5}.wav"
            },
        ],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": -150, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_P, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "자산"}, "spriteName": None,
         "value": 1000, "width": 0, "height": 0, "x": 175, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_TURN, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "턴"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 360, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
        {"id": V_MAXTURN, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "최대턴"}, "spriteName": None,
         "value": 10, "width": 0, "height": 0, "x": 360, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
        {"id": V_GOAL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "목표"}, "spriteName": None,
         "value": 10000, "width": 0, "height": 0, "x": 175, "y": 45,
         "visible": True, "sliderMin": 0, "sliderMax": 10000, "isDiscrete": True},
        {"id": V_NEED_R, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "필요r(%)"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 360, "y": 70,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": False},
        {"id": V_LAST_MSG, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "메시지"}, "spriteName": None,
         "value": "게임 시작! 카드를 골라보세요", "width": 0, "height": 0, "x": 5, "y": 100,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, button],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "compound-cards-builder"}
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
    size_kb = os.path.getsize(OUTPUT) / 1024
    n_stage = len(stage_blocks); n_btn = len(button_blocks)
    print(f"✓ wrote {OUTPUT} ({size_kb:.1f} KB)")
    print(f"  blocks: stage={n_stage}, 버튼={n_btn}, total={n_stage+n_btn}")


if __name__ == "__main__":
    main()
