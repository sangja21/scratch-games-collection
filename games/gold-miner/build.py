#!/usr/bin/env python3
"""Gold Miner — 좌우로 흔들리는 후크를 스페이스로 발사해 금괴를 끌어올린다.

진자 흔들림(후크각도 = 180 + 75*sin(phase), 피벗 0,120) → 발사 시 각도 고정 직선
하강 → 아이템에 닿으면 잡고 되감기(point towards 광부 + move 잡힌속도) → 피벗 도착 시
점수 가산. 무게별 되감기 속도(금괴대3/중5/소8/돌2.5/다이아11/빈손12). 60초 라운드 +
목표 점수. 베이스: bubble-shooter(각도 발사) + apple-catch(클론 + 로컬변수 분기) +
balloon-shooter(sin 흔들림, 60초) + cowboy-duel(라운드/배너).
"""
import json, os, zipfile, shutil, hashlib, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "골드_마이너.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: ground surface + underground cave --------
random.seed(7)
veins = []
for _ in range(36):
    x = random.randint(10, 470)
    y = random.randint(150, 350)
    r = random.uniform(1.2, 2.6)
    col = random.choice(["#FFD54F", "#FFB300", "#FFE082", "#B0BEC5"])
    veins.append(f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="{col}" opacity="0.7"/>')
VEINS = "\n  ".join(veins)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#4FC3F7"/>
      <stop offset="1" stop-color="#B3E5FC"/>
    </linearGradient>
    <linearGradient id="dirt" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#6D4C41"/>
      <stop offset="0.5" stop-color="#4E342E"/>
      <stop offset="1" stop-color="#1B0E08"/>
    </linearGradient>
  </defs>
  <!-- sky strip at top -->
  <rect width="480" height="70" fill="url(#sky)"/>
  <!-- ground surface line -->
  <rect y="62" width="480" height="14" fill="#8D6E63"/>
  <rect y="74" width="480" height="6" fill="#5D4037"/>
  <!-- underground -->
  <rect y="80" width="480" height="280" fill="url(#dirt)"/>
  <!-- a few rocks/cracks -->
  <path d="M0,140 q60,18 120,4 q70,-14 140,6 q80,20 160,-2 q40,-10 60,4"
        stroke="#3E2723" stroke-width="2" fill="none" opacity="0.5"/>
  <path d="M0,230 q90,-16 180,6 q90,20 180,-4 q60,-12 120,6"
        stroke="#2E1A12" stroke-width="2" fill="none" opacity="0.5"/>
  {VEINS}
</svg>"""

# -------- Miner (helmet + body, sits at pivot 0,120) --------
MINER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="72" viewBox="0 0 64 72">
  <!-- pickaxe over shoulder -->
  <line x1="40" y1="44" x2="58" y2="14" stroke="#8D6E63" stroke-width="4" stroke-linecap="round"/>
  <path d="M50,16 q10,-6 14,2 q-8,-2 -10,6 Z" fill="#B0BEC5" stroke="#607D8B" stroke-width="1.5"/>
  <!-- body / overalls -->
  <rect x="20" y="40" width="24" height="26" rx="5" fill="#1565C0" stroke="#0D47A1" stroke-width="2"/>
  <!-- arms -->
  <rect x="12" y="42" width="9" height="18" rx="4" fill="#1976D2"/>
  <rect x="43" y="42" width="9" height="18" rx="4" fill="#1976D2"/>
  <!-- head -->
  <circle cx="32" cy="30" r="13" fill="#FFCC80" stroke="#E0A96D" stroke-width="1.5"/>
  <!-- helmet -->
  <path d="M18,28 q14,-22 28,0 Z" fill="#FBC02D" stroke="#F57F17" stroke-width="2"/>
  <rect x="17" y="26" width="30" height="5" rx="2" fill="#F9A825" stroke="#F57F17" stroke-width="1.5"/>
  <!-- helmet lamp -->
  <circle cx="32" cy="14" r="3.5" fill="#FFF59D" stroke="#FBC02D" stroke-width="1.5"/>
  <!-- eyes + smile -->
  <circle cx="27" cy="30" r="1.6" fill="#3E2723"/>
  <circle cx="37" cy="30" r="1.6" fill="#3E2723"/>
  <path d="M27,36 q5,4 10,0" stroke="#8D6E63" stroke-width="1.5" fill="none"/>
</svg>"""

# -------- Hook (metal claw, rotationCenter at TOP = rope connection) --------
HOOK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="32" viewBox="0 0 24 32">
  <!-- top connector ring -->
  <circle cx="12" cy="5" r="4" fill="none" stroke="#B0BEC5" stroke-width="2.5"/>
  <!-- shank -->
  <line x1="12" y1="8" x2="12" y2="18" stroke="#90A4AE" stroke-width="3.5" stroke-linecap="round"/>
  <!-- hook curve (claw opening downward) -->
  <path d="M12,18 q-2,9 -8,9 q-5,0 -5,-5"
        stroke="#90A4AE" stroke-width="3.5" fill="none" stroke-linecap="round"/>
  <path d="M12,18 q2,9 8,9 q5,0 5,-5"
        stroke="#78909C" stroke-width="3.5" fill="none" stroke-linecap="round"/>
  <!-- shine -->
  <line x1="11" y1="10" x2="11" y2="16" stroke="#ECEFF1" stroke-width="1" opacity="0.8"/>
</svg>"""

# -------- Rope (thin vertical bar, rotationCenter at TOP end) --------
ROPE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="4" height="60" viewBox="0 0 4 60">
  <rect x="1" y="0" width="2" height="60" fill="#6D4C41"/>
  <rect x="1.4" y="0" width="0.6" height="60" fill="#8D6E63"/>
</svg>"""

# -------- Gold bar large (200pts, weight heavy) --------
GOLD_L_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="40" viewBox="0 0 56 40">
  <path d="M8,30 L48,30 L44,12 L12,12 Z" fill="#FFB300" stroke="#E65100" stroke-width="2"/>
  <path d="M12,12 L44,12 L40,8 L16,8 Z" fill="#FFD54F" stroke="#E65100" stroke-width="1.5"/>
  <path d="M16,16 L40,16" stroke="#FFE082" stroke-width="2" opacity="0.8"/>
  <circle cx="22" cy="22" r="2" fill="#FFFDE7"/>
  <path d="M30,18 l2,3 l-2,3 l-2,-3 Z" fill="#FFFFFF" opacity="0.85"/>
</svg>"""

# -------- Gold bar medium (100pts) --------
GOLD_M_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="44" height="32" viewBox="0 0 44 32">
  <path d="M6,24 L38,24 L35,10 L9,10 Z" fill="#FFB300" stroke="#E65100" stroke-width="2"/>
  <path d="M9,10 L35,10 L32,7 L12,7 Z" fill="#FFD54F" stroke="#E65100" stroke-width="1.5"/>
  <path d="M12,14 L32,14" stroke="#FFE082" stroke-width="1.6" opacity="0.8"/>
  <circle cx="17" cy="18" r="1.6" fill="#FFFDE7"/>
</svg>"""

# -------- Gold nugget small (50pts, light) --------
GOLD_S_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="34" height="30" viewBox="0 0 34 30">
  <path d="M6,18 Q4,8 14,7 Q22,4 28,11 Q33,17 26,23 Q18,28 10,24 Q5,22 6,18 Z"
        fill="#FFC107" stroke="#E65100" stroke-width="2"/>
  <circle cx="14" cy="13" r="2" fill="#FFFDE7"/>
  <path d="M20,11 l1.5,2.5 l-1.5,2.5 l-1.5,-2.5 Z" fill="#FFFFFF" opacity="0.85"/>
</svg>"""

# -------- Rock (gray lumpy stone, heavy low value) --------
ROCK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="44" height="36" viewBox="0 0 44 36">
  <path d="M6,26 Q3,14 14,10 Q24,4 32,10 Q42,15 38,26 Q34,32 22,32 Q10,32 6,26 Z"
        fill="#90A4AE" stroke="#455A64" stroke-width="2"/>
  <path d="M14,18 L20,16 L18,22 Z" fill="#607D8B" opacity="0.7"/>
  <path d="M26,14 L32,18 L27,21 Z" fill="#78909C" opacity="0.7"/>
  <circle cx="16" cy="24" r="1.4" fill="#CFD8DC"/>
</svg>"""

# -------- Diamond (blue gem, light high value) --------
DIAMOND_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">
  <path d="M6,14 L18,4 L30,14 L18,32 Z" fill="#4FC3F7" stroke="#0277BD" stroke-width="2"/>
  <path d="M6,14 L30,14 L18,32 Z" fill="#29B6F6"/>
  <path d="M12,9 L18,4 L24,9 L18,14 Z" fill="#B3E5FC"/>
  <path d="M6,14 L12,9 L18,14 Z" fill="#81D4FA"/>
  <path d="M30,14 L24,9 L18,14 Z" fill="#81D4FA"/>
  <line x1="18" y1="14" x2="18" y2="32" stroke="#0288D1" stroke-width="1" opacity="0.6"/>
  <circle cx="14" cy="10" r="1.4" fill="#FFFFFF"/>
</svg>"""

# -------- Round clear banner --------
CLEAR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#1B0E08" opacity="0.93" stroke="#FFB300" stroke-width="5"/>
  <text x="180" y="66" text-anchor="middle"
        fill="#FFD54F" font-family="Arial, Helvetica, sans-serif"
        font-size="42" font-weight="bold">ROUND CLEAR!</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">다음 라운드로!</text>
  <text x="180" y="136" text-anchor="middle"
        fill="#FFE082" font-family="Arial, Helvetica, sans-serif"
        font-size="14">목표 점수가 올라갑니다</text>
</svg>"""

# -------- Game over banner --------
GAMEOVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.93" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="66" text-anchor="middle"
        fill="#E53935" font-family="Arial, Helvetica, sans-serif"
        font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">목표 점수를 못 채웠어요</text>
  <text x="180" y="134" text-anchor="middle"
        fill="#81D4FA" font-family="Arial, Helvetica, sans-serif"
        font-size="13">초록 깃발(▶) 다시 클릭으로 재시작</text>
</svg>"""

# ============================================================
#  helpers
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
        bs[bid] = mk(opcode, inputs={"OPERAND1":[2,a],"OPERAND2":[2,b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid
        return bid
    def mathop(operator, x):
        bid = gen()
        ins = {"NUM": slot(x) if isinstance(x, str) else num(x)}
        bs[bid] = mk("operator_mathop", inputs=ins, fields={"OPERATOR": [operator, None]})
        if isinstance(x, str): bs[x]["parent"] = bid
        return bid
    return vrep, op, cmp_op, bool_op, mathop

# convenience builders ------------------------------------------------
def set_num(bs, name, vid, val):
    b = gen(); bs[b] = mk("data_setvariableto",
        inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
    return b

def set_expr(bs, name, vid, expr_id):
    b = gen(); bs[b] = mk("data_setvariableto",
        inputs={"VALUE": slot(expr_id)}, fields={"VARIABLE": [name, vid]})
    bs[expr_id]["parent"] = b
    return b

def change_num(bs, name, vid, val):
    b = gen(); bs[b] = mk("data_changevariableby",
        inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
    return b

def change_expr(bs, name, vid, expr_id):
    b = gen(); bs[b] = mk("data_changevariableby",
        inputs={"VALUE": slot(expr_id)}, fields={"VARIABLE": [name, vid]})
    bs[expr_id]["parent"] = b
    return b

def broadcast(bs, name, bid_msg):
    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, bid_msg]}, shadow=True)
    bc = gen(); bs[bc] = mk("event_broadcast", inputs={"BROADCAST_INPUT": [1, bm]})
    bs[bm]["parent"] = bc
    return bc

def wait(bs, dur):
    b = gen(); bs[b] = mk("control_wait", inputs={"DURATION": num(dur)})
    return b

def if_block(bs, cond, sub_first):
    b = gen(); bs[b] = mk("control_if",
        inputs={"CONDITION":[2,cond], "SUBSTACK":[2,sub_first]})
    bs[cond]["parent"] = b; bs[sub_first]["parent"] = b
    return b

def forever(bs, sub_first):
    b = gen(); bs[b] = mk("control_forever",
        inputs={"SUBSTACK":[2,sub_first]})
    bs[sub_first]["parent"] = b
    return b

# ============================================================
#  IDs
# ============================================================
V_SCORE   = "varScore01"
V_GOAL    = "varGoal02"
V_TIME    = "varTime03"
V_ROUND   = "varRound04"
V_STATE   = "varState05"
V_HOOKST  = "varHookSt06"
V_HOOKANG = "varHookAng07"
V_CAUGHT  = "varCaught08"
V_CAUGHTSP= "varCaughtSp09"
V_GRABBED = "varGrabbed10"
V_ITEMN   = "varItemN11"
V_SPAWNX  = "varSpawnX12"
V_SPAWNY  = "varSpawnY13"
V_SPAWNT  = "varSpawnT14"
# hook sprite-local
V_PHASE   = "varPhase00"
# item sprite-local
V_MYTYPE  = "varMyType15"
V_MYSCORE = "varMyScore16"
V_MYSPEED = "varMySpeed17"
V_MYHELD  = "varMyHeld18"

BR_START   = "brStart01"
BR_RSTART  = "brRoundStart02"
BR_SPAWN   = "brSpawnItem03"
BR_FIRE    = "brFire04"
BR_REND    = "brRoundEnd05"
BR_CLEARED = "brCleared06"
BR_GAMEOVER= "brGameOver07"
BR_COLLECT = "brCollect08"

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)

    # === when flag clicked: init + broadcast 게임시작 + 라운드시작 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    s1 = set_num(bs, "점수", V_SCORE, 0)
    s2 = set_num(bs, "라운드", V_ROUND, 1)
    s3 = set_num(bs, "목표점수", V_GOAL, 150)
    s4 = set_num(bs, "게임상태", V_STATE, 1)
    s5 = set_num(bs, "후크상태", V_HOOKST, 0)
    s6 = set_num(bs, "시간", V_TIME, 60)
    bc_start = broadcast(bs, "게임시작", BR_START)
    bc_rstart = broadcast(bs, "라운드시작", BR_RSTART)
    chain([(h,bs[h]),(s1,bs[s1]),(s2,bs[s2]),(s3,bs[s3]),(s4,bs[s4]),
           (s5,bs[s5]),(s6,bs[s6]),(bc_start,bs[bc_start]),(bc_rstart,bs[bc_rstart])])

    # === when receive 라운드시작: 시간=60, 아이템수 계산, repeat 배치 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=240,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_RSTART]})
    set_time = set_num(bs, "시간", V_TIME, 60)
    set_hst = set_num(bs, "후크상태", V_HOOKST, 0)

    # 아이템수 = 8 + min(라운드, 2)  ->  구현: 아이템수 = 8 + 라운드; if >10 then 10
    round_v = vrep("라운드", V_ROUND)
    add_n = op("operator_add", 8, round_v)
    set_n = set_expr(bs, "아이템수", V_ITEMN, add_n)
    n_v = vrep("아이템수", V_ITEMN)
    cond_n_gt = cmp_op("operator_gt", n_v, 10)
    set_n10 = set_num(bs, "아이템수", V_ITEMN, 10)
    if_n = if_block(bs, cond_n_gt, set_n10)
    wt_clean = wait(bs, 0.15)  # 기존 클론 삭제 처리 대기

    # repeat 아이템수 { 배치X/Y random; 배치타입 가중랜덤; broadcast 아이템배치; wait 0.03 }
    rx_rand = gen(); bs[rx_rand] = mk("operator_random",
        inputs={"FROM": num(-210), "TO": num(210)})
    set_sx = set_expr(bs, "배치X", V_SPAWNX, rx_rand)
    ry_rand = gen(); bs[ry_rand] = mk("operator_random",
        inputs={"FROM": num(-160), "TO": num(-20)})
    set_sy = set_expr(bs, "배치Y", V_SPAWNY, ry_rand)

    # 가중랜덤: r = random(1..100); 배치타입 = 1; if r>15:2; if r>45:3; if r>75:4; if r>90:5
    r_rand = gen(); bs[r_rand] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(100)})
    set_t1 = set_expr(bs, "배치타입", V_SPAWNT, r_rand)  # temp hold r in 배치타입? no.
    # Use a clean approach: store r into 배치타입 then stepwise override via comparisons on a saved r.
    # Simpler: put r into 배치X-like temp? We'll store r in 배치타입 then compute final separately
    # via nested checks reading the stored r. But stored value gets overwritten. Instead build with
    # a fresh random captured once: set 배치타입 = 1, then four ifs each re-evaluate the SAME r is
    # impossible without storing. So store r in 배치타입 first, then overwrite based on its value
    # BEFORE overwriting -> use ordered ifs reading 배치타입 (the r) and writing to itself, but each
    # if would read mutated value. To keep correct: capture r into a dedicated reading sequence.
    # Cleanest: use a chain of ifs that read 배치타입(=r) and SET to mapped value only once, going
    # from highest threshold down so earlier sets don't affect later reads. We read r each time but
    # r already overwritten... -> Avoid: keep r in 배치타입, and decide type into a SECOND pass using
    # the fact that mapped values (1..5) won't re-trigger thresholds if we go high->low.
    # Mapped: r>90 ->5, elif r>75 ->4, elif r>45 ->3, elif r>15 ->2, else 1.
    # high->low with self-overwrite: if 배치타입>90 set 5 (5 not >75 so safe); then if 배치타입>75 set4
    #   but 배치타입 is now 5 if it was >90 -> 5>75 true -> overwrites to 4. BAD.
    # Therefore we must NOT self-overwrite. Use low->high with else-chained ifs via nested control_if_else.
    # We'll build nested if/else properly below; discard set_t1/r approach.
    del bs[set_t1]

    # build nested weighted random using control_if_else reading 배치타입 (which holds r)
    set_r = set_expr(bs, "배치타입", V_SPAWNT, r_rand)  # 배치타입 temporarily = r

    # innermost: if r>90 -> 5 else 4   (this is the >75 branch's body)
    rv_a = vrep("배치타입", V_SPAWNT); c90 = cmp_op("operator_gt", rv_a, 90)
    set5 = set_num(bs, "배치타입", V_SPAWNT, 5)
    set4 = set_num(bs, "배치타입", V_SPAWNT, 4)
    ife_90 = gen(); bs[ife_90] = mk("control_if_else",
        inputs={"CONDITION":[2,c90], "SUBSTACK":[2,set5], "SUBSTACK2":[2,set4]})
    bs[c90]["parent"]=ife_90; bs[set5]["parent"]=ife_90; bs[set4]["parent"]=ife_90

    # if r>75 -> (ife_90) else 3
    rv_b = vrep("배치타입", V_SPAWNT); c75 = cmp_op("operator_gt", rv_b, 75)
    set3 = set_num(bs, "배치타입", V_SPAWNT, 3)
    ife_75 = gen(); bs[ife_75] = mk("control_if_else",
        inputs={"CONDITION":[2,c75], "SUBSTACK":[2,ife_90], "SUBSTACK2":[2,set3]})
    bs[c75]["parent"]=ife_75; bs[ife_90]["parent"]=ife_75; bs[set3]["parent"]=ife_75

    # if r>45 -> (ife_75) else 2
    rv_c = vrep("배치타입", V_SPAWNT); c45 = cmp_op("operator_gt", rv_c, 45)
    set2 = set_num(bs, "배치타입", V_SPAWNT, 2)
    ife_45 = gen(); bs[ife_45] = mk("control_if_else",
        inputs={"CONDITION":[2,c45], "SUBSTACK":[2,ife_75], "SUBSTACK2":[2,set2]})
    bs[c45]["parent"]=ife_45; bs[ife_75]["parent"]=ife_45; bs[set2]["parent"]=ife_45

    # if r>15 -> (ife_45) else 1
    rv_d = vrep("배치타입", V_SPAWNT); c15 = cmp_op("operator_gt", rv_d, 15)
    set1 = set_num(bs, "배치타입", V_SPAWNT, 1)
    ife_15 = gen(); bs[ife_15] = mk("control_if_else",
        inputs={"CONDITION":[2,c15], "SUBSTACK":[2,ife_45], "SUBSTACK2":[2,set1]})
    bs[c15]["parent"]=ife_15; bs[ife_45]["parent"]=ife_15; bs[set1]["parent"]=ife_15

    bc_spawn = broadcast(bs, "아이템배치", BR_SPAWN)
    wt_sp = wait(bs, 0.03)

    chain([(set_sx,bs[set_sx]),(set_sy,bs[set_sy]),(set_r,bs[set_r]),
           (ife_15,bs[ife_15]),(bc_spawn,bs[bc_spawn]),(wt_sp,bs[wt_sp])])

    itemn_v = vrep("아이템수", V_ITEMN)
    rep_spawn = gen(); bs[rep_spawn] = mk("control_repeat",
        inputs={"TIMES": slot(itemn_v), "SUBSTACK":[2,set_sx]})
    bs[itemn_v]["parent"] = rep_spawn
    bs[set_sx]["parent"] = rep_spawn

    chain([(h2,bs[h2]),(set_time,bs[set_time]),(set_hst,bs[set_hst]),
           (set_n,bs[set_n]),(if_n,bs[if_n]),(wt_clean,bs[wt_clean]),
           (rep_spawn,bs[rep_spawn])])

    # === when receive 게임시작: 60초 타이머 (repeat_until 게임상태=0) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=240,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    state_t = vrep("게임상태", V_STATE)
    cond_over_t = cmp_op("operator_equals", state_t, 0)

    wt_1 = wait(bs, 1)
    # if 게임상태=1: 시간-1; if 시간<=0: broadcast 라운드끝
    state_t2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_t2, 1)
    dec_time = change_num(bs, "시간", V_TIME, -1)
    time_v2 = vrep("시간", V_TIME)
    cond_t0 = cmp_op("operator_lt", time_v2, 1)  # 시간 <= 0  (정수 감소이므로 <1)
    bc_rend = broadcast(bs, "라운드끝", BR_REND)
    # 시간 만료 시 이 타이머 루프를 즉시 종료한다(plan 6장 "stop this script").
    # 종료하지 않으면 클리어 연출 wait 2 동안 시간이 계속 -1 되어 라운드끝이 재발송 →
    # 클리어 핸들러가 재시작되며 배너/라운드 진행이 꼬이는 race 가 발생한다.
    # 클리어 경로는 라운드끝 핸들러가 게임시작을 재발송해 새 타이머를 다시 돌린다.
    stop_timer = gen(); bs[stop_timer] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    bs[stop_timer]["mutation"] = {"tagName":"mutation","children":[],"hasnext":"false"}
    chain([(bc_rend,bs[bc_rend]),(stop_timer,bs[stop_timer])])
    if_t0 = if_block(bs, cond_t0, bc_rend)
    chain([(dec_time,bs[dec_time]),(if_t0,bs[if_t0])])
    if_play = if_block(bs, cond_play, dec_time)
    chain([(wt_1,bs[wt_1]),(if_play,bs[if_play])])

    rep_timer = gen(); bs[rep_timer] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over_t], "SUBSTACK":[2,wt_1]})
    bs[cond_over_t]["parent"] = rep_timer
    bs[wt_1]["parent"] = rep_timer
    chain([(h3,bs[h3]),(rep_timer,bs[rep_timer])])

    # === when receive 라운드끝: 판정 ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=20, y=560,
        fields={"BROADCAST_OPTION": ["라운드끝", BR_REND]})
    score_v = vrep("점수", V_SCORE)
    goal_v = vrep("목표점수", V_GOAL)
    lt_inner = cmp_op("operator_lt", score_v, goal_v)
    cond_clear = gen(); bs[cond_clear] = mk("operator_not",
        inputs={"OPERAND":[2, lt_inner]})  # 점수 >= 목표  ==  not(점수<목표)
    bs[lt_inner]["parent"] = cond_clear

    # clear branch
    bc_cleared = broadcast(bs, "클리어연출", BR_CLEARED)
    wt_clear = wait(bs, 2)
    inc_round = change_num(bs, "라운드", V_ROUND, 1)
    inc_goal = change_num(bs, "목표점수", V_GOAL, 100)
    bc_rstart2 = broadcast(bs, "라운드시작", BR_RSTART)
    bc_start2 = broadcast(bs, "게임시작", BR_START)
    chain([(bc_cleared,bs[bc_cleared]),(wt_clear,bs[wt_clear]),
           (inc_round,bs[inc_round]),(inc_goal,bs[inc_goal]),
           (bc_rstart2,bs[bc_rstart2]),(bc_start2,bs[bc_start2])])

    # else branch: 게임상태=0; broadcast 게임오버연출
    set_state0 = set_num(bs, "게임상태", V_STATE, 0)
    bc_gameover = broadcast(bs, "게임오버연출", BR_GAMEOVER)
    chain([(set_state0,bs[set_state0]),(bc_gameover,bs[bc_gameover])])

    ife_judge = gen(); bs[ife_judge] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_clear], "SUBSTACK":[2,bc_cleared],
                "SUBSTACK2":[2,set_state0]})
    bs[cond_clear]["parent"]=ife_judge
    bs[bc_cleared]["parent"]=ife_judge
    bs[set_state0]["parent"]=ife_judge
    chain([(h4,bs[h4]),(ife_judge,bs[ife_judge])])

    return bs

# ============================================================
#  MINER blocks (pivot decoration at 0,120)
# ============================================================
def build_miner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(120)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK":["front", None]})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(pdir,bs[pdir]),(sz,bs[sz]),(front,bs[front]),(sh,bs[sh])])
    return bs

# ============================================================
#  HOOK blocks (main state machine)
# ============================================================
PIVOT_X = 0
PIVOT_Y = 120
ROPE_LEN = 60
FALL_SPEED = 8

def build_hook_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)

    # === when receive 게임시작: goto pivot, 후크상태0, phase0, forever state machine ===
    h = gen(); bs[h] = mk("event_whenbroadcastreceived", top=True, x=20, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(PIVOT_X), "Y": num(PIVOT_Y - ROPE_LEN)})
    set_hst0 = set_num(bs, "후크상태", V_HOOKST, 0)
    set_phase0 = set_num(bs, "phase", V_PHASE, 0)

    # ---------- STATE 0: swing ----------
    # phase += 4
    inc_phase = change_num(bs, "phase", V_PHASE, 4)
    # 후크각도 = 180 + 75 * sin(phase)
    phase_v = vrep("phase", V_PHASE)
    sin_ph = mathop("sin", phase_v)
    mul75 = op("operator_multiply", sin_ph, 75)
    ang_expr = op("operator_add", 180, mul75)
    set_ang = set_expr(bs, "후크각도", V_HOOKANG, ang_expr)
    # 후크x = 0 + sin(후크각도)*60 ; 후크y = 120 + cos(후크각도)*60
    ang_for_x = vrep("후크각도", V_HOOKANG)
    sin_a = mathop("sin", ang_for_x)
    mul_x = op("operator_multiply", sin_a, ROPE_LEN)
    hx = op("operator_add", PIVOT_X, mul_x)
    ang_for_y = vrep("후크각도", V_HOOKANG)
    cos_a = mathop("cos", ang_for_y)
    mul_y = op("operator_multiply", cos_a, ROPE_LEN)
    hy = op("operator_add", PIVOT_Y, mul_y)
    goto_hook = gen(); bs[goto_hook] = mk("motion_gotoxy",
        inputs={"X": slot(hx), "Y": slot(hy)})
    bs[hx]["parent"] = goto_hook; bs[hy]["parent"] = goto_hook
    # point in direction 후크각도
    ang_for_pd = vrep("후크각도", V_HOOKANG)
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": slot(ang_for_pd)})
    bs[ang_for_pd]["parent"] = pd

    # if (space pressed) OR (mouse down): broadcast 발사; 후크상태1; 잡힘플래그0; 잡힌점수0; 잡힌속도0
    sp_menu = gen(); bs[sp_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sp_press = gen(); bs[sp_press] = mk("sensing_keypressed", inputs={"KEY_OPTION":[1, sp_menu]})
    bs[sp_menu]["parent"] = sp_press
    md = gen(); bs[md] = mk("sensing_mousedown")
    cond_fire = bool_op("operator_or", sp_press, md)
    bc_fire = broadcast(bs, "발사", BR_FIRE)
    set_hst1 = set_num(bs, "후크상태", V_HOOKST, 1)
    set_grab0 = set_num(bs, "잡힘플래그", V_GRABBED, 0)
    set_caught0 = set_num(bs, "잡힌점수", V_CAUGHT, 0)
    set_caughtsp0 = set_num(bs, "잡힌속도", V_CAUGHTSP, 0)
    chain([(bc_fire,bs[bc_fire]),(set_hst1,bs[set_hst1]),(set_grab0,bs[set_grab0]),
           (set_caught0,bs[set_caught0]),(set_caughtsp0,bs[set_caughtsp0])])
    if_fire = if_block(bs, cond_fire, bc_fire)

    chain([(inc_phase,bs[inc_phase]),(set_ang,bs[set_ang]),(goto_hook,bs[goto_hook]),
           (pd,bs[pd]),(if_fire,bs[if_fire])])

    # if 후크상태=0 { swing body }
    hst_s0 = vrep("후크상태", V_HOOKST)
    cond_s0 = cmp_op("operator_equals", hst_s0, 0)
    if_s0 = if_block(bs, cond_s0, inc_phase)

    # ---------- STATE 1: descend ----------
    # change x by sin(후크각도)*8 ; change y by cos(후크각도)*8
    ang_dx = vrep("후크각도", V_HOOKANG)
    sin_dx = mathop("sin", ang_dx)
    mul_dx = op("operator_multiply", sin_dx, FALL_SPEED)
    chx = gen(); bs[chx] = mk("motion_changexby", inputs={"DX": slot(mul_dx)})
    bs[mul_dx]["parent"] = chx
    ang_dy = vrep("후크각도", V_HOOKANG)
    cos_dy = mathop("cos", ang_dy)
    mul_dy = op("operator_multiply", cos_dy, FALL_SPEED)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": slot(mul_dy)})
    bs[mul_dy]["parent"] = chy

    # if 잡힘플래그=1 -> 후크상태2
    grab_v = vrep("잡힘플래그", V_GRABBED)
    cond_grabbed = cmp_op("operator_equals", grab_v, 1)
    set_hst2_a = set_num(bs, "후크상태", V_HOOKST, 2)
    if_grabbed = if_block(bs, cond_grabbed, set_hst2_a)

    # if (y<-175) OR (x<-235) OR (x>235) -> 후크상태2; if 잡힌속도=0 잡힌속도=12
    yp = gen(); bs[yp] = mk("motion_yposition")
    c_ylow = cmp_op("operator_lt", yp, -175)
    bs[yp]["parent"] = c_ylow
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    c_xl = cmp_op("operator_lt", xp1, -235)
    bs[xp1]["parent"] = c_xl
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_xr = cmp_op("operator_gt", xp2, 235)
    bs[xp2]["parent"] = c_xr
    edge_or1 = bool_op("operator_or", c_ylow, c_xl)
    edge_or2 = bool_op("operator_or", edge_or1, c_xr)

    set_hst2_b = set_num(bs, "후크상태", V_HOOKST, 2)
    sp_v = vrep("잡힌속도", V_CAUGHTSP)
    cond_sp0 = cmp_op("operator_equals", sp_v, 0)
    set_sp12 = set_num(bs, "잡힌속도", V_CAUGHTSP, 12)
    if_sp0 = if_block(bs, cond_sp0, set_sp12)
    chain([(set_hst2_b,bs[set_hst2_b]),(if_sp0,bs[if_sp0])])
    if_edge = if_block(bs, edge_or2, set_hst2_b)

    chain([(chx,bs[chx]),(chy,bs[chy]),(if_grabbed,bs[if_grabbed]),(if_edge,bs[if_edge])])

    hst_s1 = vrep("후크상태", V_HOOKST)
    cond_s1 = cmp_op("operator_equals", hst_s1, 1)
    if_s1 = if_block(bs, cond_s1, chx)

    # ---------- STATE 2: rewind ----------
    # point towards 광부 ; move 잡힌속도 steps
    pt_menu = gen(); bs[pt_menu] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["광부", None]}, shadow=True)
    point_miner = gen(); bs[point_miner] = mk("motion_pointtowards",
        inputs={"TOWARDS":[1, pt_menu]})
    bs[pt_menu]["parent"] = point_miner
    sp_move = vrep("잡힌속도", V_CAUGHTSP)
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": slot(sp_move)})
    bs[sp_move]["parent"] = mv

    # if distance to 광부 < 12 -> goto pivot; if 잡힘플래그=1 {점수+=잡힌점수; play coin; broadcast 수거}; 후크상태0
    dist_menu = gen(); bs[dist_menu] = mk("sensing_distancetomenu",
        fields={"DISTANCETOMENU": ["광부", None]}, shadow=True)
    dist_to = gen(); bs[dist_to] = mk("sensing_distanceto",
        inputs={"DISTANCETOMENU":[1, dist_menu]})
    bs[dist_menu]["parent"] = dist_to
    cond_arrived = cmp_op("operator_lt", dist_to, 12)

    goto_pivot = gen(); bs[goto_pivot] = mk("motion_gotoxy",
        inputs={"X": num(PIVOT_X), "Y": num(PIVOT_Y - ROPE_LEN)})

    # inner: if 잡힘플래그=1 -> 점수+=잡힌점수; play sound; broadcast 아이템수거됨
    grab_v2 = vrep("잡힘플래그", V_GRABBED)
    cond_grab2 = cmp_op("operator_equals", grab_v2, 1)
    caught_v = vrep("잡힌점수", V_CAUGHT)
    inc_score = change_expr(bs, "점수", V_SCORE, caught_v)
    # play coin sound
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    bc_collect = broadcast(bs, "아이템수거됨", BR_COLLECT)
    chain([(inc_score,bs[inc_score]),(snd,bs[snd]),(bc_collect,bs[bc_collect])])
    if_grab2 = if_block(bs, cond_grab2, inc_score)

    set_hst0_again = set_num(bs, "후크상태", V_HOOKST, 0)
    chain([(goto_pivot,bs[goto_pivot]),(if_grab2,bs[if_grab2]),(set_hst0_again,bs[set_hst0_again])])
    if_arrived = if_block(bs, cond_arrived, goto_pivot)

    chain([(point_miner,bs[point_miner]),(mv,bs[mv]),(if_arrived,bs[if_arrived])])

    hst_s2 = vrep("후크상태", V_HOOKST)
    cond_s2 = cmp_op("operator_equals", hst_s2, 2)
    if_s2 = if_block(bs, cond_s2, point_miner)

    # forever body: if 게임상태=0 stop; if_s0; if_s1; if_s2; wait 0.02
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)
    stop_this = gen(); bs[stop_this] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    bs[stop_this]["mutation"] = {"tagName":"mutation","children":[],"hasnext":"false"}
    if_stop = if_block(bs, cond_over, stop_this)
    wt = wait(bs, 0.02)
    chain([(if_stop,bs[if_stop]),(if_s0,bs[if_s0]),(if_s1,bs[if_s1]),(if_s2,bs[if_s2]),(wt,bs[wt])])

    fv = forever(bs, if_stop)
    chain([(h,bs[h]),(g0,bs[g0]),(set_hst0,bs[set_hst0]),(set_phase0,bs[set_phase0]),
           (fv,bs[fv])])

    return bs

# ============================================================
#  ROPE blocks (stretch from pivot to hook)
# ============================================================
def build_rope_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenbroadcastreceived", top=True, x=20, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # forever: goto pivot; point towards 후크; set size to (distance to 후크 / 60 * 100); wait 0.02
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(PIVOT_X), "Y": num(PIVOT_Y)})
    pt_menu = gen(); bs[pt_menu] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["후크", None]}, shadow=True)
    point_hook = gen(); bs[point_hook] = mk("motion_pointtowards",
        inputs={"TOWARDS":[1, pt_menu]})
    bs[pt_menu]["parent"] = point_hook

    dist_menu = gen(); bs[dist_menu] = mk("sensing_distancetomenu",
        fields={"DISTANCETOMENU": ["후크", None]}, shadow=True)
    dist_to = gen(); bs[dist_to] = mk("sensing_distanceto",
        inputs={"DISTANCETOMENU":[1, dist_menu]})
    bs[dist_menu]["parent"] = dist_to
    div60 = op("operator_divide", dist_to, ROPE_LEN)
    mul100 = op("operator_multiply", div60, 100)
    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto", inputs={"SIZE": slot(mul100)})
    bs[mul100]["parent"] = set_sz

    wt = wait(bs, 0.02)
    chain([(g,bs[g]),(point_hook,bs[point_hook]),(set_sz,bs[set_sz]),(wt,bs[wt])])
    fv = forever(bs, g)

    # show + go to back at flag so rope is behind hook
    h0 = gen(); bs[h0] = mk("event_whenflagclicked", top=True, x=320, y=20)
    sh = gen(); bs[sh] = mk("looks_show")
    back = gen(); bs[back] = mk("looks_gotofrontback", fields={"FRONT_BACK":["back", None]})
    chain([(h0,bs[h0]),(sh,bs[sh]),(back,bs[back])])

    chain([(h,bs[h]),(fv,bs[fv])])
    return bs

# ============================================================
#  ITEM blocks (clone spawn + grab + follow)
# ============================================================
def build_item_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)

    # === when flag clicked: hide, size 60 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    # === when receive 아이템배치: 내타입=배치타입; goto(배치X,배치Y); create clone ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["아이템배치", BR_SPAWN]})
    spt_v = vrep("배치타입", V_SPAWNT)
    set_mytype = set_expr(bs, "내타입", V_MYTYPE, spt_v)
    spx_v = vrep("배치X", V_SPAWNX)
    spy_v = vrep("배치Y", V_SPAWNY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(spx_v), "Y": slot(spy_v)})
    bs[spx_v]["parent"] = g; bs[spy_v]["parent"] = g
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(h2,bs[h2]),(set_mytype,bs[set_mytype]),(g,bs[g]),(cclone,bs[cclone])])

    # === when I start as clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=320, y=20)
    set_held0 = set_num(bs, "잡혔나", V_MYHELD, 0)

    # type branches: (costume, score, speed, size)
    # 1 gold_l 200 3 80 ; 2 gold_m 100 5 65 ; 3 gold_s 50 8 50 ; 4 rock 20 2.5 70 ; 5 diamond 150 11 55
    type_table = [
        (1, "gold_l", 200, 3,   80),
        (2, "gold_m", 100, 5,   65),
        (3, "gold_s", 50,  8,   50),
        (4, "rock",   20,  2.5, 70),
        (5, "diamond",150, 11,  55),
    ]
    branch_firsts = []
    for tnum, cname, sc, spd, size in type_table:
        myt = vrep("내타입", V_MYTYPE)
        cond_t = cmp_op("operator_equals", myt, tnum)
        cmenu_c = gen(); bs[cmenu_c] = mk("looks_costume",
            fields={"COSTUME":[cname, None]}, shadow=True)
        sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, cmenu_c]})
        bs[cmenu_c]["parent"] = sw
        set_sc = set_num(bs, "내점수", V_MYSCORE, sc)
        set_spd = set_num(bs, "내속도", V_MYSPEED, spd)
        set_size = gen(); bs[set_size] = mk("looks_setsizeto", inputs={"SIZE": num(size)})
        chain([(sw,bs[sw]),(set_sc,bs[set_sc]),(set_spd,bs[set_spd]),(set_size,bs[set_size])])
        if_t = if_block(bs, cond_t, sw)
        branch_firsts.append(if_t)

    show = gen(); bs[show] = mk("looks_show")

    # forever body:
    #  if 게임상태=0: delete this clone
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)
    del_over = gen(); bs[del_over] = mk("control_delete_this_clone")
    if_over = if_block(bs, cond_over, del_over)

    #  if 잡혔나=0 AND 후크상태=1 AND touching 후크 AND 잡힘플래그=0 -> grab
    held_v = vrep("잡혔나", V_MYHELD)
    c_held0 = cmp_op("operator_equals", held_v, 0)
    hst_v = vrep("후크상태", V_HOOKST)
    c_hst1 = cmp_op("operator_equals", hst_v, 1)
    grab_v = vrep("잡힘플래그", V_GRABBED)
    c_grab0 = cmp_op("operator_equals", grab_v, 0)
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["후크", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc
    and1 = bool_op("operator_and", c_held0, c_hst1)
    and2 = bool_op("operator_and", and1, tc)
    and3 = bool_op("operator_and", and2, c_grab0)

    set_held1 = set_num(bs, "잡혔나", V_MYHELD, 1)
    set_grab1 = set_num(bs, "잡힘플래그", V_GRABBED, 1)
    myscore_v = vrep("내점수", V_MYSCORE)
    set_caught = set_expr(bs, "잡힌점수", V_CAUGHT, myscore_v)
    myspeed_v = vrep("내속도", V_MYSPEED)
    set_caughtsp = set_expr(bs, "잡힌속도", V_CAUGHTSP, myspeed_v)
    chain([(set_held1,bs[set_held1]),(set_grab1,bs[set_grab1]),
           (set_caught,bs[set_caught]),(set_caughtsp,bs[set_caughtsp])])
    if_grab = if_block(bs, and3, set_held1)

    #  if 잡혔나=1: goto (x of 후크, y of 후크)
    held_v2 = vrep("잡혔나", V_MYHELD)
    c_held1 = cmp_op("operator_equals", held_v2, 1)
    hx_menu = gen(); bs[hx_menu] = mk("sensing_of_object_menu",
        fields={"OBJECT": ["후크", None]}, shadow=True)
    sense_hx = gen(); bs[sense_hx] = mk("sensing_of",
        inputs={"OBJECT":[1, hx_menu]}, fields={"PROPERTY":["x position", None]})
    bs[hx_menu]["parent"] = sense_hx
    hy_menu = gen(); bs[hy_menu] = mk("sensing_of_object_menu",
        fields={"OBJECT": ["후크", None]}, shadow=True)
    sense_hy = gen(); bs[sense_hy] = mk("sensing_of",
        inputs={"OBJECT":[1, hy_menu]}, fields={"PROPERTY":["y position", None]})
    bs[hy_menu]["parent"] = sense_hy
    goto_hook = gen(); bs[goto_hook] = mk("motion_gotoxy",
        inputs={"X": slot(sense_hx), "Y": slot(sense_hy)})
    bs[sense_hx]["parent"] = goto_hook; bs[sense_hy]["parent"] = goto_hook
    if_follow = if_block(bs, c_held1, goto_hook)

    wt = wait(bs, 0.02)
    chain([(if_over,bs[if_over]),(if_grab,bs[if_grab]),(if_follow,bs[if_follow]),(wt,bs[wt])])
    fv = forever(bs, if_over)

    # chain clone start: held0 + type branches + show + forever
    seq = [(ch,bs[ch]),(set_held0,bs[set_held0])]
    seq += [(bid,bs[bid]) for bid in branch_firsts]
    seq += [(show,bs[show]),(fv,bs[fv])]
    chain(seq)

    # === when receive 아이템수거됨: if 잡혔나=1 delete ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=400,
        fields={"BROADCAST_OPTION": ["아이템수거됨", BR_COLLECT]})
    held_v3 = vrep("잡혔나", V_MYHELD)
    c_held1b = cmp_op("operator_equals", held_v3, 1)
    del_collect = gen(); bs[del_collect] = mk("control_delete_this_clone")
    if_collect = if_block(bs, c_held1b, del_collect)
    chain([(h3,bs[h3]),(if_collect,bs[if_collect])])

    # === when receive 라운드시작: delete this clone (clean old clones) ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=320, y=520,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_RSTART]})
    del_rstart = gen(); bs[del_rstart] = mk("control_delete_this_clone")
    chain([(h4,bs[h4]),(del_rstart,bs[del_rstart])])

    return bs

# ============================================================
#  BANNER blocks (clear / gameover)
# ============================================================
def build_banner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op, mathop = make_helpers(bs)

    # when flag: hide, goto(0,0), size100, front
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK":["front", None]})
    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front])])

    # when receive 클리어연출: costume clear, show, wait1.8, hide
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["클리어연출", BR_CLEARED]})
    cm_clear = gen(); bs[cm_clear] = mk("looks_costume",
        fields={"COSTUME":["clear", None]}, shadow=True)
    sw_clear = gen(); bs[sw_clear] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, cm_clear]})
    bs[cm_clear]["parent"] = sw_clear
    front2 = gen(); bs[front2] = mk("looks_gotofrontback", fields={"FRONT_BACK":["front", None]})
    show_c = gen(); bs[show_c] = mk("looks_show")
    snm_c = gen(); bs[snm_c] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_c = gen(); bs[snd_c] = mk("sound_play", inputs={"SOUND_MENU":[1, snm_c]})
    bs[snm_c]["parent"] = snd_c
    wt_c = wait(bs, 1.8)
    hide_c = gen(); bs[hide_c] = mk("looks_hide")
    chain([(h2,bs[h2]),(sw_clear,bs[sw_clear]),(front2,bs[front2]),(show_c,bs[show_c]),
           (snd_c,bs[snd_c]),(wt_c,bs[wt_c]),(hide_c,bs[hide_c])])

    # when receive 게임오버연출: costume gameover, show, sound
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=200,
        fields={"BROADCAST_OPTION": ["게임오버연출", BR_GAMEOVER]})
    cm_go = gen(); bs[cm_go] = mk("looks_costume",
        fields={"COSTUME":["gameover", None]}, shadow=True)
    sw_go = gen(); bs[sw_go] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, cm_go]})
    bs[cm_go]["parent"] = sw_go
    front3 = gen(); bs[front3] = mk("looks_gotofrontback", fields={"FRONT_BACK":["front", None]})
    show_go = gen(); bs[show_go] = mk("looks_show")
    snm_go = gen(); bs[snm_go] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_go = gen(); bs[snd_go] = mk("sound_play", inputs={"SOUND_MENU":[1, snm_go]})
    bs[snm_go]["parent"] = snd_go
    chain([(h3,bs[h3]),(sw_go,bs[sw_go]),(front3,bs[front3]),(show_go,bs[show_go]),(snd_go,bs[snd_go])])

    return bs

# ============================================================
#  ASSEMBLE PROJECT
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    def write_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        return m

    bg_md5     = write_svg(BG_SVG)
    miner_md5  = write_svg(MINER_SVG)
    hook_md5   = write_svg(HOOK_SVG)
    rope_md5   = write_svg(ROPE_SVG)
    gl_md5     = write_svg(GOLD_L_SVG)
    gm_md5     = write_svg(GOLD_M_SVG)
    gs_md5     = write_svg(GOLD_S_SVG)
    rock_md5   = write_svg(ROCK_SVG)
    dia_md5    = write_svg(DIAMOND_SVG)
    clear_md5  = write_svg(CLEAR_SVG)
    go_md5     = write_svg(GAMEOVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks  = build_stage_blocks()
    miner_blocks  = build_miner_blocks()
    hook_blocks   = build_hook_blocks()
    rope_blocks   = build_rope_blocks()
    item_blocks   = build_item_blocks()
    banner_blocks = build_banner_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:   ["점수", 0],
            V_GOAL:    ["목표점수", 150],
            V_TIME:    ["시간", 60],
            V_ROUND:   ["라운드", 1],
            V_STATE:   ["게임상태", 1],
            V_HOOKST:  ["후크상태", 0],
            V_HOOKANG: ["후크각도", 180],
            V_CAUGHT:  ["잡힌점수", 0],
            V_CAUGHTSP:["잡힌속도", 0],
            V_GRABBED: ["잡힘플래그", 0],
            V_ITEMN:   ["아이템수", 9],
            V_SPAWNX:  ["배치X", 0],
            V_SPAWNY:  ["배치Y", 0],
            V_SPAWNT:  ["배치타입", 1],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_RSTART: "라운드시작",
            BR_SPAWN: "아이템배치",
            BR_FIRE: "발사",
            BR_REND: "라운드끝",
            BR_CLEARED: "클리어연출",
            BR_GAMEOVER: "게임오버연출",
            BR_COLLECT: "아이템수거됨",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "배경", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    miner = {
        "isStage": False, "name": "광부",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": miner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "miner", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": miner_md5, "md5ext": f"{miner_md5}.svg",
            "rotationCenterX": 32, "rotationCenterY": 36
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 0, "y": 120, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    rope = {
        "isStage": False, "name": "줄",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": rope_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "rope", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": rope_md5, "md5ext": f"{rope_md5}.svg",
            "rotationCenterX": 2, "rotationCenterY": 0   # top end = pivot anchor
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": 0, "y": 120, "size": 100, "direction": 180,
        "draggable": False, "rotationStyle": "all around"
    }

    hook = {
        "isStage": False, "name": "후크",
        "variables": {V_PHASE: ["phase", 0]}, "lists": {}, "broadcasts": {},
        "blocks": hook_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "hook", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hook_md5, "md5ext": f"{hook_md5}.svg",
            "rotationCenterX": 12, "rotationCenterY": 5   # top connector = rope point
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": 0, "y": 60, "size": 100, "direction": 180,
        "draggable": False, "rotationStyle": "all around"
    }

    item = {
        "isStage": False, "name": "아이템",
        "variables": {
            V_MYTYPE:  ["내타입", 1],
            V_MYSCORE: ["내점수", 0],
            V_MYSPEED: ["내속도", 0],
            V_MYHELD:  ["잡혔나", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": item_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "gold_l", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": gl_md5, "md5ext": f"{gl_md5}.svg",
             "rotationCenterX": 28, "rotationCenterY": 20},
            {"name": "gold_m", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": gm_md5, "md5ext": f"{gm_md5}.svg",
             "rotationCenterX": 22, "rotationCenterY": 16},
            {"name": "gold_s", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": gs_md5, "md5ext": f"{gs_md5}.svg",
             "rotationCenterX": 17, "rotationCenterY": 15},
            {"name": "rock", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": rock_md5, "md5ext": f"{rock_md5}.svg",
             "rotationCenterX": 22, "rotationCenterY": 18},
            {"name": "diamond", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": dia_md5, "md5ext": f"{dia_md5}.svg",
             "rotationCenterX": 18, "rotationCenterY": 18},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": -80, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    banner = {
        "isStage": False, "name": "배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": banner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "clear", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": clear_md5, "md5ext": f"{clear_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 80},
            {"name": "gameover", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": go_md5, "md5ext": f"{go_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 80},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100000, "isDiscrete": True},
        {"id": V_GOAL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "목표점수"}, "spriteName": None,
         "value": 150, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100000, "isDiscrete": True},
        {"id": V_TIME, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "시간"}, "spriteName": None,
         "value": 60, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 60, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 50, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, miner, rope, hook, item, banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "gold-miner-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    # ---- integrity: validate block references ----
    def validate_blocks(name, blocks):
        ids = set(blocks.keys())
        for bid, b in blocks.items():
            if not isinstance(b, dict): continue
            nx = b.get("next")
            if nx is not None and nx not in ids:
                raise ValueError(f"{name}: block {bid} next={nx} missing")
            pa = b.get("parent")
            if pa is not None and pa not in ids:
                raise ValueError(f"{name}: block {bid} parent={pa} missing")
            for ik, iv in (b.get("inputs") or {}).items():
                for el in iv:
                    if isinstance(el, str) and el not in ids:
                        raise ValueError(f"{name}: block {bid} input {ik} ref {el} missing")
                    if isinstance(el, list) and len(el) >= 2 and isinstance(el[1], str) \
                       and el[0] in (2, 3) and el[1] not in ids:
                        raise ValueError(f"{name}: block {bid} input {ik} substack ref {el[1]} missing")
    for nm, blk in [("Stage",stage_blocks),("광부",miner_blocks),("줄",rope_blocks),
                    ("후크",hook_blocks),("아이템",item_blocks),("배너",banner_blocks)]:
        validate_blocks(nm, blk)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # ---- verify zip + json ----
    assert zipfile.is_zipfile(OUTPUT), "output is not a valid zip"
    with zipfile.ZipFile(OUTPUT) as zf:
        bad = zf.testzip()
        assert bad is None, f"corrupt entry: {bad}"
        with zf.open("project.json") as f:
            json.load(f)

    print(f"wrote {OUTPUT}")
    counts = [
        ("Stage", stage_blocks), ("광부", miner_blocks), ("줄", rope_blocks),
        ("후크", hook_blocks), ("아이템", item_blocks), ("배너", banner_blocks),
    ]
    total = 0
    for nm, blk in counts:
        print(f"  {nm:6}: {len(blk)} blocks")
        total += len(blk)
    print(f"  TOTAL : {total} blocks across {len(project['targets'])} targets")

if __name__ == "__main__":
    main()
