#!/usr/bin/env python3
"""팩맨 미니 (pacman-mini) — 미로 안 도트를 다 먹고 유령 4마리를 피한다.

베이스: games/snake/build.py (격자 스텝 이동 + 다음방향 예약 + change/goto 스냅 +
        리스트 헬퍼 + 게임상태 broadcast/배너) + games/tetris-mini/build.py
        (2D→1D 평탄화 idx=row*15+col+1, data_replaceitemoflist replace_at,
         보드셀 클론 렌더).

차이점: (1) 미로 벽 → 매 스텝 다음 칸이 벽(보드 값 0)인지 검사. (2) 먹이는 보드
리스트 값으로 관리, 먹으면 replace item idx with 3. (3) 유령 4클론은 교차로
확률 추격 AI(뒤로 돌기 금지)로 이동.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "팩맨미니.sb3")

# ============================================================
#  미로 데이터 (plan 3절 그대로 임베드)
# ============================================================
MAZE = (
    "000000000000000"   # row0
    "021111111111120"   # row1
    "010110101101010"   # row2
    "011111111111110"   # row3
    "010101333101010"   # row4
    "111111333111111"   # row5  (col0/col14 터널, col6,7,8 유령집)
    "010101333101010"   # row6
    "011111111111110"   # row7
    "010110101101010"   # row8
    "021111111111120"   # row9
    "000000000000000"   # row10
)
BOARD0 = [int(ch) for ch in MAZE]   # 길이 165, 1-base 로 item(idx)
assert len(BOARD0) == 165

COLS, ROWS = 15, 11
CELL = 24
# 칸 (col,row) 중심 무대좌표:  X = -168 + col*24 , Y = 120 - row*24
ORIGIN_X = -168
ORIGIN_Y = 120

# ============================================================
#  SVG assets
# ============================================================

# -------- 배경: 검은 바탕 + 미로 벽(파란 둥근 사각)을 보드 데이터대로 직접 그림 --------
# 셀박스 좌상단 SVG 좌표 = (60 + col*24, 48 + row*24), 24x24.
def _maze_walls():
    rects = []
    for row in range(ROWS):
        for col in range(COLS):
            if BOARD0[row * COLS + col] == 0:
                px = 60 + col * CELL
                py = 48 + row * CELL
                rects.append(
                    f'    <rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" '
                    f'rx="6" fill="#1A1AE0" stroke="#3D5AFE" stroke-width="2"/>')
    return "\n".join(rects)

BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <!-- 검은 바탕 -->
  <rect x="0" y="0" width="480" height="360" fill="#000000"/>
  <!-- 미로 영역 외곽 살짝 어두운 패널 -->
  <rect x="58" y="46" width="364" height="268" fill="#04040C"/>
  <!-- 미로 벽 (값 0 칸) -->
  <g>
__WALLS__
  </g>
</svg>""".replace("__WALLS__", _maze_walls())

# -------- 팩맨: 노란 원 + 입 쐐기 (22x22) --------
PACMAN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
  <path d="M11 11 L21 6 A10 10 0 1 0 21 16 Z" fill="#FFEB3B" stroke="#FBC02D" stroke-width="1"/>
  <circle cx="10" cy="6" r="1.4" fill="#000000"/>
</svg>"""

# -------- 유령 색 코스튬 (22x22) : 빨강/분홍/청록/주황 + scared(파랑) + eyes --------
def _ghost_svg(body, eye_dir="down"):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
  <path d="M2 11 A9 9 0 0 1 20 11 L20 19 L17 16 L14 19 L11 16 L8 19 L5 16 L2 19 Z"
        fill="{body}" stroke="#111111" stroke-width="0.8"/>
  <circle cx="8" cy="9" r="2.6" fill="#FFFFFF"/>
  <circle cx="14" cy="9" r="2.6" fill="#FFFFFF"/>
  <circle cx="8" cy="10" r="1.2" fill="#1A237E"/>
  <circle cx="14" cy="10" r="1.2" fill="#1A237E"/>
</svg>"""

GHOST_RED    = _ghost_svg("#F44336")
GHOST_PINK   = _ghost_svg("#FF80AB")
GHOST_CYAN   = _ghost_svg("#26C6DA")
GHOST_ORANGE = _ghost_svg("#FF9800")
GHOST_SCARED = """<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
  <path d="M2 11 A9 9 0 0 1 20 11 L20 19 L17 16 L14 19 L11 16 L8 19 L5 16 L2 19 Z"
        fill="#2962FF" stroke="#0D1B6B" stroke-width="0.8"/>
  <circle cx="8" cy="9" r="1.6" fill="#FFFFFF"/>
  <circle cx="14" cy="9" r="1.6" fill="#FFFFFF"/>
  <path d="M5 15 Q8 13 11 15 Q14 13 17 15" fill="none" stroke="#FFFFFF" stroke-width="1.2"/>
</svg>"""
GHOST_EYES = """<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
  <circle cx="8" cy="10" r="3" fill="#FFFFFF"/>
  <circle cx="14" cy="10" r="3" fill="#FFFFFF"/>
  <circle cx="8" cy="11" r="1.3" fill="#1A237E"/>
  <circle cx="14" cy="11" r="1.3" fill="#1A237E"/>
</svg>"""

# -------- 도트 / 파워펠릿 --------
DOT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8">
  <circle cx="4" cy="4" r="2.4" fill="#FFE0A0"/>
</svg>"""
POWER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <circle cx="8" cy="8" r="6.5" fill="#FFD54F" stroke="#FFFFFF" stroke-width="1"/>
</svg>"""

# -------- 배너 (READY! / GAME OVER / YOU WIN!) --------
def _banner(text, sub, color):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="5" y="5" width="350" height="140" rx="14" fill="#000000" opacity="0.92"
        stroke="{color}" stroke-width="4"/>
  <text x="180" y="74" text-anchor="middle" fill="{color}"
        font-family="Arial, Helvetica, sans-serif" font-size="44" font-weight="bold">{text}</text>
  <text x="180" y="112" text-anchor="middle" fill="#FFFFFF"
        font-family="Arial, Helvetica, sans-serif" font-size="16">{sub}</text>
</svg>"""

READY_SVG    = _banner("READY!",    "방향키로 도트를 먹어요",        "#FFEB3B")
GAMEOVER_SVG = _banner("GAME OVER", "초록 깃발(▶)로 다시 시작",      "#F44336")
WIN_SVG      = _banner("YOU WIN!",  "도트를 전부 먹었어요!",         "#4CAF50")

# ============================================================
#  helpers (snake / tetris build.py 와 동일)
# ============================================================
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n):  return [1, [4, str(n)]]
def text_lit(s): return [1, [10, str(s)]]
def slot(bid, sk=4, sv="0"): return [3, bid, [sk, str(sv)]]

def mk(opcode, *, parent=None, next_=None, inputs=None, fields=None,
       top=False, x=0, y=0, shadow=False, mutation=None):
    b = {"opcode": opcode, "next": next_, "parent": parent,
         "inputs": inputs or {}, "fields": fields or {},
         "shadow": shadow, "topLevel": top}
    if top: b["x"] = x; b["y"] = y
    if mutation is not None: b["mutation"] = mutation
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
    return vrep, op, cmp_op, bool_op

def make_list_helpers(bs):
    def delete_all(name, lid):
        bid = gen()
        bs[bid] = mk("data_deletealloflist", fields={"LIST": [name, lid]})
        return bid
    def add_to(name, lid, item):
        bid = gen()
        ins = {"ITEM": slot(item) if isinstance(item, str) else text_lit(item)}
        bs[bid] = mk("data_addtolist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(item, str): bs[item]["parent"] = bid
        return bid
    def item_of(name, lid, index):
        bid = gen()
        ins = {"INDEX": slot(index) if isinstance(index, str) else text_lit(index)}
        bs[bid] = mk("data_itemoflist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(index, str): bs[index]["parent"] = bid
        return bid
    def length_of(name, lid):
        bid = gen()
        bs[bid] = mk("data_lengthoflist", fields={"LIST": [name, lid]})
        return bid
    def replace_at(name, lid, index, item):
        bid = gen()
        ins = {
            "INDEX": slot(index) if isinstance(index, str) else text_lit(index),
            "ITEM":  slot(item)  if isinstance(item, str)  else text_lit(item),
        }
        bs[bid] = mk("data_replaceitemoflist", inputs=ins, fields={"LIST": [name, lid]})
        if isinstance(index, str): bs[index]["parent"] = bid
        if isinstance(item, str):  bs[item]["parent"] = bid
        return bid
    return delete_all, add_to, item_of, length_of, replace_at

def broadcast(bs, name, brid):
    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    bc = gen(); bs[bc] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm]})
    bs[bm]["parent"] = bc
    return bc

def setvar(bs, name, vid, value):
    """value: number/str literal -> num/text_lit, reporter bid(str slot) 는 set_reporter 사용."""
    bid = gen()
    bs[bid] = mk("data_setvariableto",
        inputs={"VALUE": num(value)}, fields={"VARIABLE": [name, vid]})
    return bid

def set_reporter(bs, name, vid, reporter_bid):
    bid = gen()
    bs[bid] = mk("data_setvariableto",
        inputs={"VALUE": slot(reporter_bid)}, fields={"VARIABLE": [name, vid]})
    bs[reporter_bid]["parent"] = bid
    return bid

def changevar(bs, name, vid, value):
    bid = gen()
    bs[bid] = mk("data_changevariableby",
        inputs={"VALUE": num(value)}, fields={"VARIABLE": [name, vid]})
    return bid

def ctrl_if(bs, cond_bid, sub_first_bid):
    bid = gen()
    bs[bid] = mk("control_if",
        inputs={"CONDITION":[2,cond_bid], "SUBSTACK":[2,sub_first_bid]})
    bs[cond_bid]["parent"] = bid
    bs[sub_first_bid]["parent"] = bid
    return bid

def ctrl_if_else(bs, cond_bid, sub1_first, sub2_first):
    bid = gen()
    bs[bid] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_bid],
                "SUBSTACK":[2,sub1_first], "SUBSTACK2":[2,sub2_first]})
    bs[cond_bid]["parent"] = bid
    bs[sub1_first]["parent"] = bid
    bs[sub2_first]["parent"] = bid
    return bid

# ============================================================
#  IDs
# ============================================================
# 글로벌 변수 14개
V_SCORE   = "varScore01"
V_BEST    = "varBest02"
V_STATE   = "varState03"
V_LIFE    = "varLife04"
V_REMAIN  = "varRemain05"
V_STEP    = "varStep06"
V_NEXTDIR = "varNextDir07"
V_PACDIR  = "varPacDir08"
V_PACCOL  = "varPacCol09"
V_PACROW  = "varPacRow10"
V_PACX    = "varPacX11"
V_PACY    = "varPacY12"
V_POWER   = "varPower13"
V_GISSUE  = "varGIssue14"
# 팩맨 스텝 임시 (글로벌 재사용 — snake 스타일)
V_TCOL    = "varTCol30"
V_TROW    = "varTRow31"
V_NCOL    = "varNCol32"
V_NROW    = "varNRow33"
V_PIDX    = "varPIdx34"

# 유령 sprite-local
V_GNUM    = "varGNum15"
V_GCOL    = "varGCol16"
V_GROW    = "varGRow17"
V_GDIR    = "varGDir18"
V_GSTATE  = "varGState19"
V_GCAND   = "varGCand20"     # 후보 수 (랜덤 분기용)
V_GTRY    = "varGTry21"      # 검사중 방향
V_GBEST   = "varGBest35"     # 베스트 방향
V_GMIN    = "varGMin36"      # 최소 거리
V_GNC     = "varGNc37"       # 시험 nc
V_GNR     = "varGNr38"       # 시험 nr
V_GTC     = "varGTc39"       # 목표 col (팩맨 or 집)
V_GTR     = "varGTr40"       # 목표 row
V_GPCT    = "varGPct41"      # 추격확률
V_GPICK   = "varGPick42"     # 랜덤 후보 선택 인덱스
V_GSEEN   = "varGSeen43"     # 랜덤 분기: 본 후보 수

# 먹이 sprite-local
V_DRAWIDX = "varDrawIdx22"
V_DRAWVAL = "varDrawVal23"

# 리스트
L_BOARD = "L_board01"

# broadcasts 8개
BR_START   = "brStart01"
BR_STEP    = "brStep02"
BR_DRAW    = "brDrawFood03"
BR_CLEAR   = "brClearFood04"
BR_PWON    = "brPowerOn05"
BR_PWOFF   = "brPowerOff06"
BR_HIT     = "brHit07"
BR_RESET   = "brReset08"

# 시작값
PAC_START_COL = 7
PAC_START_ROW = 3
PAC_START_X = ORIGIN_X + PAC_START_COL * CELL   # 0
PAC_START_Y = ORIGIN_Y - PAC_START_ROW * CELL   # 48

# ============================================================
#  방향 증분 헬퍼: 1=오른쪽(col+1) 2=위(row-1) 3=왼쪽(col-1) 4=아래(row+1)
# ============================================================
def dcol(d): return {1:1, 2:0, 3:-1, 4:0}[d]
def drow(d): return {1:0, 2:-1, 3:0, 4:1}[d]
def opposite(d): return {1:3, 2:4, 3:1, 4:2}[d]

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    delete_all, add_to, item_of, length_of, replace_at = make_list_helpers(bs)

    # === when flag clicked: init vars + 보드 재초기화 + broadcast 게임시작/먹이그리기 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    inits = [
        ("점수", V_SCORE, 0), ("게임상태", V_STATE, 1), ("라이프", V_LIFE, 3),
        ("남은먹이", V_REMAIN, 92), ("스텝간격", V_STEP, 0.16), ("파워타이머", V_POWER, 0),
        ("다음방향", V_NEXTDIR, 0), ("팩방향", V_PACDIR, 0),
        ("팩col", V_PACCOL, PAC_START_COL), ("팩row", V_PACROW, PAC_START_ROW),
        ("팩X", V_PACX, PAC_START_X), ("팩Y", V_PACY, PAC_START_Y),
        ("유령발급", V_GISSUE, 0),
    ]
    for name, vid, val in inits:
        sid = setvar(bs, name, vid, val)
        seq.append((sid, bs[sid]))

    # 보드 재초기화: delete all + 165 add (깃발 재시작 시 도트 부활 보장)
    da = delete_all("보드", L_BOARD)
    seq.append((da, bs[da]))
    for v in BOARD0:
        aid = add_to("보드", L_BOARD, int(v))   # int -> text_lit 리터럴
        seq.append((aid, bs[aid]))

    bc_start = broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    bc_draw  = broadcast(bs, "먹이그리기", BR_DRAW); seq.append((bc_draw, bs[bc_draw]))
    chain(seq)

    # === when receive 게임시작: 스텝 발생기 (repeat until 게임상태≠1) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=520,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    st_a = vrep("게임상태", V_STATE)
    cond_a = cmp_op("operator_not_equals", st_a, 1)
    bc_step = broadcast(bs, "스텝", BR_STEP)
    step_v = vrep("스텝간격", V_STEP)
    wt_step = gen(); bs[wt_step] = mk("control_wait", inputs={"DURATION": slot(step_v)})
    bs[step_v]["parent"] = wt_step
    chain([(bc_step, bs[bc_step]), (wt_step, bs[wt_step])])
    rep_a = gen(); bs[rep_a] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_a], "SUBSTACK":[2,bc_step]})
    bs[cond_a]["parent"] = rep_a; bs[bc_step]["parent"] = rep_a
    chain([(h2, bs[h2]), (rep_a, bs[rep_a])])

    # === when receive 게임시작: 파워모드 카운트다운 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=520,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    st_b = vrep("게임상태", V_STATE)
    cond_b = cmp_op("operator_not_equals", st_b, 1)

    # if 파워타이머 > 0: 파워타이머 -= 0.1 ; if 파워타이머 <= 0: set 0 + broadcast 파워끝
    pw_g = vrep("파워타이머", V_POWER)
    c_pw_gt = cmp_op("operator_gt", pw_g, 0)
    dec_pw = changevar(bs, "파워타이머", V_POWER, -0.1)
    # inner: if 파워타이머 <= 0  ==  NOT(파워타이머 > 0)
    pw_g2 = vrep("파워타이머", V_POWER)
    c_pw_gt2 = cmp_op("operator_gt", pw_g2, 0)
    not_pw = gen(); bs[not_pw] = mk("operator_not", inputs={"OPERAND":[2,c_pw_gt2]})
    bs[c_pw_gt2]["parent"] = not_pw
    set_pw0 = setvar(bs, "파워타이머", V_POWER, 0)
    bc_pwoff = broadcast(bs, "파워끝", BR_PWOFF)
    chain([(set_pw0, bs[set_pw0]), (bc_pwoff, bs[bc_pwoff])])
    if_pwend = ctrl_if(bs, not_pw, set_pw0)
    chain([(dec_pw, bs[dec_pw]), (if_pwend, bs[if_pwend])])
    if_pw = ctrl_if(bs, c_pw_gt, dec_pw)
    wt_pw = gen(); bs[wt_pw] = mk("control_wait", inputs={"DURATION": num(0.1)})
    chain([(if_pw, bs[if_pw]), (wt_pw, bs[wt_pw])])
    rep_b = gen(); bs[rep_b] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_b], "SUBSTACK":[2,if_pw]})
    bs[cond_b]["parent"] = rep_b; bs[if_pw]["parent"] = rep_b
    chain([(h3, bs[h3]), (rep_b, bs[rep_b])])

    return bs

# ============================================================
#  PACMAN blocks
# ============================================================
def build_pacman_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    delete_all, add_to, item_of, length_of, replace_at = make_list_helpers(bs)

    # === when flag clicked: size/show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(sz,bs[sz]),(sh,bs[sh])])

    # === when receive 게임시작: 시작칸 set + goto + show + 입력 forever ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    s_col = setvar(bs, "팩col", V_PACCOL, PAC_START_COL)
    s_row = setvar(bs, "팩row", V_PACROW, PAC_START_ROW)
    s_dir = setvar(bs, "팩방향", V_PACDIR, 0)
    s_nd  = setvar(bs, "다음방향", V_NEXTDIR, 0)
    gx = gen(); bs[gx] = mk("motion_gotoxy",
        inputs={"X": num(PAC_START_X), "Y": num(PAC_START_Y)})
    sh2 = gen(); bs[sh2] = mk("looks_show")

    # 입력 forever: repeat until 게임상태≠1
    st_in = vrep("게임상태", V_STATE)
    cond_in = cmp_op("operator_not_equals", st_in, 1)
    def key_if(key_name, dir_val):
        km = gen(); bs[km] = mk("sensing_keyoptions",
            fields={"KEY_OPTION": [key_name, None]}, shadow=True)
        kp = gen(); bs[kp] = mk("sensing_keypressed", inputs={"KEY_OPTION":[1, km]})
        bs[km]["parent"] = kp
        setnd = setvar(bs, "다음방향", V_NEXTDIR, dir_val)
        return ctrl_if(bs, kp, setnd)
    if_r = key_if("right arrow", 1)
    if_u = key_if("up arrow", 2)
    if_l = key_if("left arrow", 3)
    if_d = key_if("down arrow", 4)
    wt_in = gen(); bs[wt_in] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(if_r,bs[if_r]),(if_u,bs[if_u]),(if_l,bs[if_l]),(if_d,bs[if_d]),(wt_in,bs[wt_in])])
    rep_in = gen(); bs[rep_in] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_in], "SUBSTACK":[2,if_r]})
    bs[cond_in]["parent"] = rep_in; bs[if_r]["parent"] = rep_in
    chain([(h2,bs[h2]),(s_col,bs[s_col]),(s_row,bs[s_row]),(s_dir,bs[s_dir]),
           (s_nd,bs[s_nd]),(gx,bs[gx]),(sh2,bs[sh2]),(rep_in,bs[rep_in])])

    # === when receive 스텝: 선회 + 이동(벽검사) + 먹기 + 승리 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=20,
        fields={"BROADCAST_OPTION": ["스텝", BR_STEP]})

    body = []   # (id, block) sequence for the script body

    # --- 1) 선회: 시험col=팩col ; 시험row=팩row ; 방향별 가감 ---
    pc1 = vrep("팩col", V_PACCOL); st_tc = set_reporter(bs, "시험col", V_TCOL, pc1)
    pr1 = vrep("팩row", V_PACROW); st_tr = set_reporter(bs, "시험row", V_TROW, pr1)
    body += [(st_tc,bs[st_tc]), (st_tr,bs[st_tr])]
    # if 다음방향=1: 시험col=팩col+1 등
    for d in (1,2,3,4):
        nd = vrep("다음방향", V_NEXTDIR)
        c_nd = cmp_op("operator_equals", nd, d)
        if dcol(d):
            base = vrep("팩col", V_PACCOL)
            adj = op("operator_add", base, dcol(d))
            sset = set_reporter(bs, "시험col", V_TCOL, adj)
        else:
            base = vrep("팩row", V_PACROW)
            adj = op("operator_add", base, drow(d))
            sset = set_reporter(bs, "시험row", V_TROW, adj)
        ifb = ctrl_if(bs, c_nd, sset)
        body.append((ifb, bs[ifb]))
    # if (다음방향≠0) AND (item(시험row*15+시험col+1) ≠ 0): 팩방향=다음방향
    nd2 = vrep("다음방향", V_NEXTDIR)
    c_nd_ne0 = cmp_op("operator_not_equals", nd2, 0)
    trow_r = vrep("시험row", V_TROW); mul_r = op("operator_multiply", trow_r, 15)
    tcol_r = vrep("시험col", V_TCOL); add_rc = op("operator_add", mul_r, tcol_r)
    idx_turn = op("operator_add", add_rc, 1)
    item_turn = item_of("보드", L_BOARD, idx_turn)
    c_notwall = cmp_op("operator_not_equals", item_turn, 0)
    cond_turn = bool_op("operator_and", c_nd_ne0, c_notwall)
    nd3 = vrep("다음방향", V_NEXTDIR)
    set_pacdir = set_reporter(bs, "팩방향", V_PACDIR, nd3)
    if_turn = ctrl_if(bs, cond_turn, set_pacdir)
    body.append((if_turn, bs[if_turn]))

    # --- 2) 현재 팩방향으로 한 칸 전진 시도 ---
    pc2 = vrep("팩col", V_PACCOL); st_nc = set_reporter(bs, "다col", V_NCOL, pc2)
    pr2 = vrep("팩row", V_PACROW); st_nr = set_reporter(bs, "다row", V_NROW, pr2)
    body += [(st_nc,bs[st_nc]), (st_nr,bs[st_nr])]
    for d in (1,2,3,4):
        pdv = vrep("팩방향", V_PACDIR)
        c_pd = cmp_op("operator_equals", pdv, d)
        if dcol(d):
            base = vrep("팩col", V_PACCOL); adj = op("operator_add", base, dcol(d))
            sset = set_reporter(bs, "다col", V_NCOL, adj)
        else:
            base = vrep("팩row", V_PACROW); adj = op("operator_add", base, drow(d))
            sset = set_reporter(bs, "다row", V_NROW, adj)
        ifb = ctrl_if(bs, c_pd, sset)
        body.append((ifb, bs[ifb]))
    # 터널 워프: if 다col<0: 다col=14 ; if 다col>14: 다col=0
    nc1 = vrep("다col", V_NCOL); c_lt0 = cmp_op("operator_lt", nc1, 0)
    set_w14 = setvar(bs, "다col", V_NCOL, 14)
    body.append((ctrl_if(bs, c_lt0, set_w14), None))
    nc2 = vrep("다col", V_NCOL); c_gt14 = cmp_op("operator_gt", nc2, 14)
    set_w0 = setvar(bs, "다col", V_NCOL, 0)
    body.append((ctrl_if(bs, c_gt14, set_w0), None))
    # fix None entries: rebuild block refs
    body = [(bid, bs[bid]) for (bid, _) in body]

    # if item(다row*15+다col+1) ≠ 0: 이동 적용
    nrow_r = vrep("다row", V_NROW); mul_nr = op("operator_multiply", nrow_r, 15)
    ncol_r = vrep("다col", V_NCOL); add_nrc = op("operator_add", mul_nr, ncol_r)
    idx_move = op("operator_add", add_nrc, 1)
    item_move = item_of("보드", L_BOARD, idx_move)
    c_move = cmp_op("operator_not_equals", item_move, 0)
    # 이동 본문: 팩col=다col ; 팩row=다row ; 팩X/팩Y 계산 ; goto
    mvc = vrep("다col", V_NCOL); set_pc = set_reporter(bs, "팩col", V_PACCOL, mvc)
    mvr = vrep("다row", V_NROW); set_pr = set_reporter(bs, "팩row", V_PACROW, mvr)
    # 팩X = -168 + 팩col*24
    pcx = vrep("팩col", V_PACCOL); mulx = op("operator_multiply", pcx, CELL)
    addx = op("operator_add", mulx, ORIGIN_X, key1="NUM1", key2="NUM2")
    # addx = mulx + (-168) ; op() second arg numeric ok
    set_px = set_reporter(bs, "팩X", V_PACX, addx)
    # 팩Y = 120 - 팩row*24
    pcy = vrep("팩row", V_PACROW); muly = op("operator_multiply", pcy, CELL)
    suby = gen(); bs[suby] = mk("operator_subtract",
        inputs={"NUM1": num(ORIGIN_Y), "NUM2": slot(muly)})
    bs[muly]["parent"] = suby
    set_py = set_reporter(bs, "팩Y", V_PACY, suby)
    # goto (팩X, 팩Y)
    pxv = vrep("팩X", V_PACX); pyv = vrep("팩Y", V_PACY)
    goto_p = gen(); bs[goto_p] = mk("motion_gotoxy",
        inputs={"X": slot(pxv), "Y": slot(pyv)})
    bs[pxv]["parent"] = goto_p; bs[pyv]["parent"] = goto_p
    nc = gen(); bs[nc] = mk("looks_nextcostume")   # 입 애니메이션
    chain([(set_pc,bs[set_pc]),(set_pr,bs[set_pr]),(set_px,bs[set_px]),
           (set_py,bs[set_py]),(goto_p,bs[goto_p]),(nc,bs[nc])])
    if_move = ctrl_if(bs, c_move, set_pc)
    body.append((if_move, bs[if_move]))

    # --- 3) 도착 칸 먹기: idx = 팩row*15 + 팩col + 1 ---
    prw = vrep("팩row", V_PACROW); mul_p = op("operator_multiply", prw, 15)
    pcl = vrep("팩col", V_PACCOL); add_p = op("operator_add", mul_p, pcl)
    idx_eat = op("operator_add", add_p, 1)
    set_idx = set_reporter(bs, "먹idx", V_PIDX, idx_eat)
    body.append((set_idx, bs[set_idx]))

    # if item(먹idx)=1: 도트
    iv1 = vrep("먹idx", V_PIDX); it1 = item_of("보드", L_BOARD, iv1)
    c_dot = cmp_op("operator_equals", it1, 1)
    inc_sc1 = changevar(bs, "점수", V_SCORE, 10)
    dec_r1 = changevar(bs, "남은먹이", V_REMAIN, -1)
    iv1b = vrep("먹idx", V_PIDX); rep1 = replace_at("보드", L_BOARD, iv1b, 3)
    bc_d1 = broadcast(bs, "먹이그리기", BR_DRAW)
    snm1 = gen(); bs[snm1] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd1 = gen(); bs[snd1] = mk("sound_play", inputs={"SOUND_MENU":[1, snm1]})
    bs[snm1]["parent"] = snd1
    chain([(inc_sc1,bs[inc_sc1]),(dec_r1,bs[dec_r1]),(rep1,bs[rep1]),
           (bc_d1,bs[bc_d1]),(snd1,bs[snd1])])
    if_dot = ctrl_if(bs, c_dot, inc_sc1)
    body.append((if_dot, bs[if_dot]))

    # if item(먹idx)=2: 펠릿
    iv2 = vrep("먹idx", V_PIDX); it2 = item_of("보드", L_BOARD, iv2)
    c_pel = cmp_op("operator_equals", it2, 2)
    inc_sc2 = changevar(bs, "점수", V_SCORE, 50)
    dec_r2 = changevar(bs, "남은먹이", V_REMAIN, -1)
    iv2b = vrep("먹idx", V_PIDX); rep2 = replace_at("보드", L_BOARD, iv2b, 3)
    set_pw7 = setvar(bs, "파워타이머", V_POWER, 7)
    bc_pwon = broadcast(bs, "파워시작", BR_PWON)
    bc_d2 = broadcast(bs, "먹이그리기", BR_DRAW)
    snm2 = gen(); bs[snm2] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd2 = gen(); bs[snd2] = mk("sound_play", inputs={"SOUND_MENU":[1, snm2]})
    bs[snm2]["parent"] = snd2
    chain([(inc_sc2,bs[inc_sc2]),(dec_r2,bs[dec_r2]),(rep2,bs[rep2]),
           (set_pw7,bs[set_pw7]),(bc_pwon,bs[bc_pwon]),(bc_d2,bs[bc_d2]),(snd2,bs[snd2])])
    if_pel = ctrl_if(bs, c_pel, inc_sc2)
    body.append((if_pel, bs[if_pel]))

    # if 점수 > 최고기록: 최고기록 = 점수
    scb = vrep("점수", V_SCORE); beb = vrep("최고기록", V_BEST)
    c_best = cmp_op("operator_gt", scb, beb)
    scb2 = vrep("점수", V_SCORE)
    set_best = set_reporter(bs, "최고기록", V_BEST, scb2)
    if_best = ctrl_if(bs, c_best, set_best)
    body.append((if_best, bs[if_best]))

    # 4) 승리: if 남은먹이 <= 0: 게임상태=2  ==  NOT(남은먹이>0)
    rmn = vrep("남은먹이", V_REMAIN)
    c_rmn_gt = cmp_op("operator_gt", rmn, 0)
    not_rmn = gen(); bs[not_rmn] = mk("operator_not", inputs={"OPERAND":[2,c_rmn_gt]})
    bs[c_rmn_gt]["parent"] = not_rmn
    set_win = setvar(bs, "게임상태", V_STATE, 2)
    if_win = ctrl_if(bs, not_rmn, set_win)
    body.append((if_win, bs[if_win]))

    chain([(h3, bs[h3])] + body)

    # === when receive 팩맨피격: 라이프-1 + 게임오버/리셋 ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=320, y=520,
        fields={"BROADCAST_OPTION": ["팩맨피격", BR_HIT]})
    dec_life = changevar(bs, "라이프", V_LIFE, -1)
    snm3 = gen(); bs[snm3] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd3 = gen(); bs[snd3] = mk("sound_play", inputs={"SOUND_MENU":[1, snm3]})
    bs[snm3]["parent"] = snd3
    # if 라이프 <= 0: 게임상태=0  else: 리셋
    lf = vrep("라이프", V_LIFE)
    c_lf_gt = cmp_op("operator_gt", lf, 0)
    not_lf = gen(); bs[not_lf] = mk("operator_not", inputs={"OPERAND":[2,c_lf_gt]})
    bs[c_lf_gt]["parent"] = not_lf
    set_over = setvar(bs, "게임상태", V_STATE, 0)
    # else 리셋: 팩col/row/방향/다음방향/팩X/팩Y/goto + broadcast 위치리셋 + wait 1.2
    r_col = setvar(bs, "팩col", V_PACCOL, PAC_START_COL)
    r_row = setvar(bs, "팩row", V_PACROW, PAC_START_ROW)
    r_dir = setvar(bs, "팩방향", V_PACDIR, 0)
    r_nd  = setvar(bs, "다음방향", V_NEXTDIR, 0)
    r_px  = setvar(bs, "팩X", V_PACX, PAC_START_X)
    r_py  = setvar(bs, "팩Y", V_PACY, PAC_START_Y)
    r_goto = gen(); bs[r_goto] = mk("motion_gotoxy",
        inputs={"X": num(PAC_START_X), "Y": num(PAC_START_Y)})
    bc_reset = broadcast(bs, "위치리셋", BR_RESET)
    wt_ready = gen(); bs[wt_ready] = mk("control_wait", inputs={"DURATION": num(1.2)})
    chain([(r_col,bs[r_col]),(r_row,bs[r_row]),(r_dir,bs[r_dir]),(r_nd,bs[r_nd]),
           (r_px,bs[r_px]),(r_py,bs[r_py]),(r_goto,bs[r_goto]),
           (bc_reset,bs[bc_reset]),(wt_ready,bs[wt_ready])])
    if_die = ctrl_if_else(bs, not_lf, set_over, r_col)
    chain([(h4,bs[h4]),(dec_life,bs[dec_life]),(snd3,bs[snd3]),(if_die,bs[if_die])])

    # === when receive 위치리셋: 팩맨 시작칸 복귀 ===
    h5 = gen(); bs[h5] = mk("event_whenbroadcastreceived", top=True, x=620, y=520,
        fields={"BROADCAST_OPTION": ["위치리셋", BR_RESET]})
    z_col = setvar(bs, "팩col", V_PACCOL, PAC_START_COL)
    z_row = setvar(bs, "팩row", V_PACROW, PAC_START_ROW)
    z_dir = setvar(bs, "팩방향", V_PACDIR, 0)
    z_nd  = setvar(bs, "다음방향", V_NEXTDIR, 0)
    z_goto = gen(); bs[z_goto] = mk("motion_gotoxy",
        inputs={"X": num(PAC_START_X), "Y": num(PAC_START_Y)})
    chain([(h5,bs[h5]),(z_col,bs[z_col]),(z_row,bs[z_row]),(z_dir,bs[z_dir]),
           (z_nd,bs[z_nd]),(z_goto,bs[z_goto])])

    return bs

# ============================================================
#  GHOST blocks (4 클론, 교차로 확률 추격 AI)
# ============================================================
def build_ghost_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    delete_all, add_to, item_of, length_of, replace_at = make_list_helpers(bs)

    # 유령번호별 시작칸 set 블록열 (start as clone / 위치리셋 공용)
    def start_cell_seq():
        """returns first_id ; chained if blocks setting 유col/유row by 유령번호."""
        cells = {1:(6,5), 2:(7,5), 3:(8,5), 4:(7,4)}
        seq = []
        for gnum,(c,r) in cells.items():
            gn = vrep("유령번호", V_GNUM)
            cnd = cmp_op("operator_equals", gn, gnum)
            sc = setvar(bs, "유col", V_GCOL, c)
            sr = setvar(bs, "유row", V_GROW, r)
            chain([(sc,bs[sc]),(sr,bs[sr])])
            ifb = ctrl_if(bs, cnd, sc)
            seq.append((ifb, bs[ifb]))
        chain(seq)
        return seq[0][0], seq

    # goto by 유col/유row reporter
    def goto_cell_block():
        gc = vrep("유col", V_GCOL); mulx = op("operator_multiply", gc, CELL)
        addx = op("operator_add", mulx, ORIGIN_X)
        gr = vrep("유row", V_GROW); muly = op("operator_multiply", gr, CELL)
        suby = gen(); bs[suby] = mk("operator_subtract",
            inputs={"NUM1": num(ORIGIN_Y), "NUM2": slot(muly)})
        bs[muly]["parent"] = suby
        g = gen(); bs[g] = mk("motion_gotoxy",
            inputs={"X": slot(addx), "Y": slot(suby)})
        bs[addx]["parent"] = g; bs[suby]["parent"] = g
        return g

    # 코스튬 전환 by 유상태/유령번호 (정상→번호 코스튬, 겁먹음→scared, 집복귀→eyes)
    # 코스튬 순서: 1 red 2 pink 3 cyan 4 orange 5 scared 6 eyes
    def costume_seq():
        seq = []
        # if 유상태=1: scared
        gs1 = vrep("유상태", V_GSTATE); c1 = cmp_op("operator_equals", gs1, 1)
        cmn1 = gen(); bs[cmn1] = mk("looks_costume",
            fields={"COSTUME":["scared", None]}, shadow=True)
        sw1 = gen(); bs[sw1] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn1]})
        bs[cmn1]["parent"] = sw1
        seq.append((ctrl_if(bs, c1, sw1), None))
        # if 유상태=2: eyes
        gs2 = vrep("유상태", V_GSTATE); c2 = cmp_op("operator_equals", gs2, 2)
        cmn2 = gen(); bs[cmn2] = mk("looks_costume",
            fields={"COSTUME":["eyes", None]}, shadow=True)
        sw2 = gen(); bs[sw2] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn2]})
        bs[cmn2]["parent"] = sw2
        seq.append((ctrl_if(bs, c2, sw2), None))
        # if 유상태=0: switch costume to 유령번호 (코스튬 인덱스 = 번호)
        gs3 = vrep("유상태", V_GSTATE); c3 = cmp_op("operator_equals", gs3, 0)
        gn = vrep("유령번호", V_GNUM)
        swn = gen(); bs[swn] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(gn)})
        bs[gn]["parent"] = swn
        seq.append((ctrl_if(bs, c3, swn), None))
        seq = [(bid, bs[bid]) for (bid,_) in seq]
        chain(seq)
        return seq[0][0]

    # 색 코스튬 직접(유령번호) — start as clone 용
    def costume_by_num():
        gn = vrep("유령번호", V_GNUM)
        swn = gen(); bs[swn] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(gn)})
        bs[gn]["parent"] = swn
        return swn

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when receive 게임시작: hide + 유령발급=0 + repeat 4 (발급+클론) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    set_iss0 = setvar(bs, "유령발급", V_GISSUE, 0)
    inc_iss = changevar(bs, "유령발급", V_GISSUE, 1)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(inc_iss,bs[inc_iss]),(cclone,bs[cclone])])
    rep4 = gen(); bs[rep4] = mk("control_repeat",
        inputs={"TIMES": num(4), "SUBSTACK":[2,inc_iss]})
    bs[inc_iss]["parent"] = rep4
    chain([(h2,bs[h2]),(hi2,bs[hi2]),(set_iss0,bs[set_iss0]),(rep4,bs[rep4])])

    # === when I start as clone: 번호채택 + 유상태0 + 시작칸 + 유방향2 + goto + 코스튬 + show ===
    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=320, y=180)
    iss_r = vrep("유령발급", V_GISSUE)
    set_gn = set_reporter(bs, "유령번호", V_GNUM, iss_r)
    set_gst0 = setvar(bs, "유상태", V_GSTATE, 0)
    cell_first, _ = start_cell_seq()
    set_gdir = setvar(bs, "유방향", V_GDIR, 2)
    g_goto = goto_cell_block()
    g_cost = costume_by_num()
    g_show = gen(); bs[g_show] = mk("looks_show")
    chain([(sc,bs[sc]),(set_gn,bs[set_gn]),(set_gst0,bs[set_gst0]),
           (cell_first,bs[cell_first]),(set_gdir,bs[set_gdir]),
           (g_goto,bs[g_goto]),(g_cost,bs[g_cost]),(g_show,bs[g_show])])

    # === when receive 스텝: AI 이동 + 충돌 (7.4) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=620, y=20,
        fields={"BROADCAST_OPTION": ["스텝", BR_STEP]})
    body = []

    # 0) 목표칸 결정: 기본 팩맨 (유상태≠2), 집복귀(유상태=2) → 집(7,5)
    # set 유목표col=팩col ; 유목표row=팩row
    pacc = vrep("팩col", V_PACCOL); set_tc = set_reporter(bs, "유목표col", V_GTC, pacc)
    pacr = vrep("팩row", V_PACROW); set_tr = set_reporter(bs, "유목표row", V_GTR, pacr)
    body += [(set_tc,bs[set_tc]),(set_tr,bs[set_tr])]
    # if 유상태=2: 유목표col=7 ; 유목표row=5
    gs_e = vrep("유상태", V_GSTATE); c_eaten = cmp_op("operator_equals", gs_e, 2)
    t7 = setvar(bs, "유목표col", V_GTC, 7)
    t5 = setvar(bs, "유목표row", V_GTR, 5)
    chain([(t7,bs[t7]),(t5,bs[t5])])
    if_home_tgt = ctrl_if(bs, c_eaten, t7)
    body.append((if_home_tgt, bs[if_home_tgt]))

    # 추격확률 유령번호별 set: 1→70 2→50 3→30 4→0
    pct_map = {1:70, 2:50, 3:30, 4:0}
    set_pct0 = setvar(bs, "추격확률", V_GPCT, 0)
    body.append((set_pct0, bs[set_pct0]))
    for gnum, p in pct_map.items():
        gn = vrep("유령번호", V_GNUM); cnd = cmp_op("operator_equals", gn, gnum)
        sp = setvar(bs, "추격확률", V_GPCT, p)
        body.append((ctrl_if(bs, cnd, sp), bs[None] if False else None))
    body = [(bid, bs[bid]) for (bid,_) in body]
    # 집복귀 중인 유령은 항상 추격(목표=집): if 유상태=2: 추격확률=100
    gs_e2 = vrep("유상태", V_GSTATE); c_eaten2 = cmp_op("operator_equals", gs_e2, 2)
    set_pct100 = setvar(bs, "추격확률", V_GPCT, 100)
    body.append((ctrl_if(bs, c_eaten2, set_pct100), None))
    body = [(bid, bs[bid]) for (bid,_) in body]

    # 1) 후보 탐색 + 추격(최소거리) 계산.
    #    최소거리=9999 ; 베스트방향=유방향 ; 후보수=0
    set_min = setvar(bs, "최소거리", V_GMIN, 9999)
    gd0 = vrep("유방향", V_GDIR); set_bestd = set_reporter(bs, "베스트방향", V_GBEST, gd0)
    set_cand = setvar(bs, "후보", V_GCAND, 0)
    set_pick = setvar(bs, "랜덤선택", V_GPICK, 0)
    body += [(set_min,bs[set_min]),(set_bestd,bs[set_bestd]),
             (set_cand,bs[set_cand]),(set_pick,bs[set_pick])]

    # 먼저 후보 수만 센다 (랜덤 선택용): 4방향 검사
    def dir_step_calc(dvar_vid):
        """build: nc=유col+dcol(시험방향) ; nr=유row+drow(시험방향) ; 워프 보정.
        시험방향 변수에 따라 동적이라 4개 if 로 dcol/drow 적용한다."""
        seq = []
        # nc=유col ; nr=유row
        gc = vrep("유col", V_GCOL); s_nc = set_reporter(bs, "유nc", V_GNC, gc)
        gr = vrep("유row", V_GROW); s_nr = set_reporter(bs, "유nr", V_GNR, gr)
        seq += [(s_nc,bs[s_nc]),(s_nr,bs[s_nr])]
        for d in (1,2,3,4):
            tv = vrep("시험방향", dvar_vid); cnd = cmp_op("operator_equals", tv, d)
            if dcol(d):
                base = vrep("유col", V_GCOL); adj = op("operator_add", base, dcol(d))
                sset = set_reporter(bs, "유nc", V_GNC, adj)
            else:
                base = vrep("유row", V_GROW); adj = op("operator_add", base, drow(d))
                sset = set_reporter(bs, "유nr", V_GNR, adj)
            seq.append((ctrl_if(bs, cnd, sset), None))
        seq = [(bid, bs[bid]) for (bid,_) in seq]
        # 워프: if 유nc<0: 14 ; if 유nc>14: 0
        nc1 = vrep("유nc", V_GNC); clt = cmp_op("operator_lt", nc1, 0)
        s14 = setvar(bs, "유nc", V_GNC, 14)
        seq.append((ctrl_if(bs, clt, s14), None))
        nc2 = vrep("유nc", V_GNC); cgt = cmp_op("operator_gt", nc2, 14)
        s0 = setvar(bs, "유nc", V_GNC, 0)
        seq.append((ctrl_if(bs, cgt, s0), None))
        seq = [(bid, bs[bid]) for (bid,_) in seq]
        chain(seq)
        return seq

    # 4방향 루프를 펼쳐서 구현 (시험방향 = 1..4)
    # 각 방향마다: if 시험방향 ≠ 반대(유방향) and item(유nr*15+유nc+1)≠0:
    #    후보++ ; d=abs(유nc-목표col)+abs(유nr-목표row) ; if d<최소거리: 최소거리=d, 베스트방향=시험방향
    for d in (1,2,3,4):
        seg = []
        # set 시험방향 = d
        s_try = setvar(bs, "시험방향", V_GTRY, d)
        seg.append((s_try, bs[s_try]))
        # nc/nr 계산
        calc_seq = dir_step_calc(V_GTRY)
        seg += calc_seq
        # 조건: 시험방향 ≠ 반대(유방향)  AND  item(유nr*15+유nc+1) ≠ 0
        # 반대(유방향): 유방향 reporter 와 비교. 동적으로: NOT (시험방향 == 반대(유방향))
        # 반대(유방향) 를 변수로 미리 만들지 않고, 4 if 로 처리하면 복잡 → 수식:
        #   반대(d') = ((d'+1) mod 4)+1.  유방향+1 mod4 +1
        gd_r = vrep("유방향", V_GDIR)
        add1 = op("operator_add", gd_r, 1)
        modd = gen(); bs[modd] = mk("operator_mod",
            inputs={"NUM1": slot(add1), "NUM2": num(4)})
        bs[add1]["parent"] = modd
        opp = op("operator_add", modd, 1)
        c_notback = cmp_op("operator_not_equals", d, opp)
        # item ≠ 0
        nr_r = vrep("유nr", V_GNR); mul_nr = op("operator_multiply", nr_r, 15)
        nc_r = vrep("유nc", V_GNC); add_nrc = op("operator_add", mul_nr, nc_r)
        idx_g = op("operator_add", add_nrc, 1)
        item_g = item_of("보드", L_BOARD, idx_g)
        c_open = cmp_op("operator_not_equals", item_g, 0)
        cond_ok = bool_op("operator_and", c_notback, c_open)
        # 본문: 후보++ ; d=abs(...)+abs(...) ; if d<최소거리: 최소거리=d 베스트=시험방향
        inc_cand = changevar(bs, "후보", V_GCAND, 1)
        # 거리: abs(유nc-목표col)
        nc_d = vrep("유nc", V_GNC); tc_d = vrep("유목표col", V_GTC)
        sub_c = op("operator_subtract", nc_d, tc_d)
        abs_c = gen(); bs[abs_c] = mk("operator_mathop",
            inputs={"NUM": slot(sub_c)}, fields={"OPERATOR":["abs", None]})
        bs[sub_c]["parent"] = abs_c
        nr_d = vrep("유nr", V_GNR); tr_d = vrep("유목표row", V_GTR)
        sub_r = op("operator_subtract", nr_d, tr_d)
        abs_r = gen(); bs[abs_r] = mk("operator_mathop",
            inputs={"NUM": slot(sub_r)}, fields={"OPERATOR":["abs", None]})
        bs[sub_r]["parent"] = abs_r
        dist = op("operator_add", abs_c, abs_r)
        set_distvar = set_reporter(bs, "후보거리", V_GSEEN, dist)
        # if 후보거리 < 최소거리: 최소거리=후보거리 ; 베스트방향=시험방향
        dvv = vrep("후보거리", V_GSEEN); minv = vrep("최소거리", V_GMIN)
        c_less = cmp_op("operator_lt", dvv, minv)
        dvv2 = vrep("후보거리", V_GSEEN); set_newmin = set_reporter(bs, "최소거리", V_GMIN, dvv2)
        tvv = vrep("시험방향", V_GTRY); set_newbest = set_reporter(bs, "베스트방향", V_GBEST, tvv)
        chain([(set_newmin,bs[set_newmin]),(set_newbest,bs[set_newbest])])
        if_less = ctrl_if(bs, c_less, set_newmin)
        chain([(inc_cand,bs[inc_cand]),(set_distvar,bs[set_distvar]),(if_less,bs[if_less])])
        if_ok = ctrl_if(bs, cond_ok, inc_cand)
        seg.append((if_ok, bs[if_ok]))
        body += seg

    # 2) 추격? : if (random 1..100 <= 추격확률) AND (후보>0): 유방향=베스트방향
    #    else: 랜덤 후보 선택 (후보>0 이면)
    # 추격 판정: random 1..100 <= 추격확률  ==  NOT(random > 추격확률)
    rnd2 = gen(); bs[rnd2] = mk("operator_random", inputs={"FROM": num(1), "TO": num(100)})
    pct_r2 = vrep("추격확률", V_GPCT)
    c_gt = cmp_op("operator_gt", rnd2, pct_r2)
    not_gt = gen(); bs[not_gt] = mk("operator_not", inputs={"OPERAND":[2,c_gt]})
    bs[c_gt]["parent"] = not_gt
    # 후보>0
    cand_r = vrep("후보", V_GCAND); c_havecand = cmp_op("operator_gt", cand_r, 0)
    cond_chase = bool_op("operator_and", not_gt, c_havecand)
    # 추격 본문: 유방향 = 베스트방향
    bestd_r = vrep("베스트방향", V_GBEST)
    set_dir_chase = set_reporter(bs, "유방향", V_GDIR, bestd_r)
    # 랜덤 본문(else): if 후보>0 → 랜덤선택= random 1..후보 ; 다시 4방향 훑어 n번째 후보 채택
    cand_r2 = vrep("후보", V_GCAND)
    rndpick = gen(); bs[rndpick] = mk("operator_random",
        inputs={"FROM": num(1), "TO": slot(cand_r2)})
    bs[cand_r2]["parent"] = rndpick
    set_pickn = set_reporter(bs, "랜덤선택", V_GPICK, rndpick)
    set_seen = setvar(bs, "본후보", V_GSEEN, 0)   # reuse V_GSEEN as 'seen' counter now
    # 4방향 재훑기: 후보면 본후보++ ; if 본후보=랜덤선택: 유방향=시험방향
    rand_seq = [(set_pickn,bs[set_pickn]),(set_seen,bs[set_seen])]
    for d in (1,2,3,4):
        s_try = setvar(bs, "시험방향", V_GTRY, d)
        calc_seq = dir_step_calc(V_GTRY)
        gd_r = vrep("유방향", V_GDIR)
        add1 = op("operator_add", gd_r, 1)
        modd = gen(); bs[modd] = mk("operator_mod",
            inputs={"NUM1": slot(add1), "NUM2": num(4)})
        bs[add1]["parent"] = modd
        opp = op("operator_add", modd, 1)
        c_notback = cmp_op("operator_not_equals", d, opp)
        nr_r = vrep("유nr", V_GNR); mul_nr = op("operator_multiply", nr_r, 15)
        nc_r = vrep("유nc", V_GNC); add_nrc = op("operator_add", mul_nr, nc_r)
        idx_g = op("operator_add", add_nrc, 1)
        item_g = item_of("보드", L_BOARD, idx_g)
        c_open = cmp_op("operator_not_equals", item_g, 0)
        cond_ok = bool_op("operator_and", c_notback, c_open)
        inc_seen = changevar(bs, "본후보", V_GSEEN, 1)
        seen_r = vrep("본후보", V_GSEEN); pick_r = vrep("랜덤선택", V_GPICK)
        c_match = cmp_op("operator_equals", seen_r, pick_r)
        tvv = vrep("시험방향", V_GTRY); set_d = set_reporter(bs, "유방향", V_GDIR, tvv)
        if_match = ctrl_if(bs, c_match, set_d)
        chain([(inc_seen,bs[inc_seen]),(if_match,bs[if_match])])
        if_ok = ctrl_if(bs, cond_ok, inc_seen)
        rand_seq.append((s_try, bs[s_try]))
        rand_seq += calc_seq
        rand_seq.append((if_ok, bs[if_ok]))
    chain(rand_seq)
    # if 후보>0 (else 분기 안에서 랜덤 적용)
    cand_r3 = vrep("후보", V_GCAND); c_havecand2 = cmp_op("operator_gt", cand_r3, 0)
    if_randhas = ctrl_if(bs, c_havecand2, rand_seq[0][0])
    # if_else: 추격 vs 랜덤
    chain([(set_dir_chase, bs[set_dir_chase])])
    if_chase = ctrl_if_else(bs, cond_chase, set_dir_chase, if_randhas)
    body.append((if_chase, bs[if_chase]))

    # 3) 유방향으로 1칸 이동 (+워프) — dir_step_calc(유방향) 으로 유nc/유nr 산출 후 적용
    move_calc = dir_step_calc(V_GDIR)
    body += move_calc
    nc_mv = vrep("유nc", V_GNC); set_gc_mv = set_reporter(bs, "유col", V_GCOL, nc_mv)
    nr_mv = vrep("유nr", V_GNR); set_gr_mv = set_reporter(bs, "유row", V_GROW, nr_mv)
    g_goto2 = goto_cell_block()
    body += [(set_gc_mv,bs[set_gc_mv]),(set_gr_mv,bs[set_gr_mv]),(g_goto2,bs[g_goto2])]

    # 집복귀 도착 판정: if (유상태=2 AND 유col=7 AND 유row=5): 유상태=0
    gs_h = vrep("유상태", V_GSTATE); c_st2 = cmp_op("operator_equals", gs_h, 2)
    gc_h = vrep("유col", V_GCOL); c_c7 = cmp_op("operator_equals", gc_h, 7)
    gr_h = vrep("유row", V_GROW); c_r5 = cmp_op("operator_equals", gr_h, 5)
    and_h1 = bool_op("operator_and", c_st2, c_c7)
    and_h2 = bool_op("operator_and", and_h1, c_r5)
    set_st0 = setvar(bs, "유상태", V_GSTATE, 0)
    if_home = ctrl_if(bs, and_h2, set_st0)
    body.append((if_home, bs[if_home]))

    # 4) 코스튬 갱신
    cost_first = costume_seq()
    body.append((cost_first, bs[cost_first]))

    # 5) 충돌: if (유col=팩col AND 유row=팩row):
    #      if 유상태=1: 점수+200, 유상태=2 (집복귀)
    #      else if 유상태=0: broadcast 팩맨피격
    gc_c = vrep("유col", V_GCOL); pc_c = vrep("팩col", V_PACCOL)
    c_samec = cmp_op("operator_equals", gc_c, pc_c)
    gr_c = vrep("유row", V_GROW); pr_c = vrep("팩row", V_PACROW)
    c_samer = cmp_op("operator_equals", gr_c, pr_c)
    cond_hit = bool_op("operator_and", c_samec, c_samer)
    # inner if 유상태=1
    gs_c = vrep("유상태", V_GSTATE); c_scared = cmp_op("operator_equals", gs_c, 1)
    add200 = changevar(bs, "점수", V_SCORE, 200)
    set_eaten = setvar(bs, "유상태", V_GSTATE, 2)
    chain([(add200,bs[add200]),(set_eaten,bs[set_eaten])])
    # else if 유상태=0 → broadcast 팩맨피격
    gs_c2 = vrep("유상태", V_GSTATE); c_normal = cmp_op("operator_equals", gs_c2, 0)
    bc_hit = broadcast(bs, "팩맨피격", BR_HIT)
    if_norm = ctrl_if(bs, c_normal, bc_hit)
    if_scared = ctrl_if_else(bs, c_scared, add200, if_norm)
    if_hit = ctrl_if(bs, cond_hit, if_scared)
    body.append((if_hit, bs[if_hit]))

    chain([(h3, bs[h3])] + body)

    # === when receive 파워시작: if 유상태=0 → 유상태=1 + scared ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=20, y=520,
        fields={"BROADCAST_OPTION": ["파워시작", BR_PWON]})
    gsp = vrep("유상태", V_GSTATE); c_norm_p = cmp_op("operator_equals", gsp, 0)
    set_scared = setvar(bs, "유상태", V_GSTATE, 1)
    cmn_s = gen(); bs[cmn_s] = mk("looks_costume",
        fields={"COSTUME":["scared", None]}, shadow=True)
    sw_s = gen(); bs[sw_s] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn_s]})
    bs[cmn_s]["parent"] = sw_s
    chain([(set_scared,bs[set_scared]),(sw_s,bs[sw_s])])
    if_pwon = ctrl_if(bs, c_norm_p, set_scared)
    chain([(h4,bs[h4]),(if_pwon,bs[if_pwon])])

    # === when receive 파워끝: if 유상태=1 → 유상태=0 + 색코스튬 ===
    h5 = gen(); bs[h5] = mk("event_whenbroadcastreceived", top=True, x=320, y=520,
        fields={"BROADCAST_OPTION": ["파워끝", BR_PWOFF]})
    gsp2 = vrep("유상태", V_GSTATE); c_scared_p = cmp_op("operator_equals", gsp2, 1)
    set_norm = setvar(bs, "유상태", V_GSTATE, 0)
    g_cost2 = costume_by_num()
    chain([(set_norm,bs[set_norm]),(g_cost2,bs[g_cost2])])
    if_pwoff = ctrl_if(bs, c_scared_p, set_norm)
    chain([(h5,bs[h5]),(if_pwoff,bs[if_pwoff])])

    # === when receive 위치리셋: 유상태0 + 시작칸 + goto + 색코스튬 ===
    h6 = gen(); bs[h6] = mk("event_whenbroadcastreceived", top=True, x=620, y=520,
        fields={"BROADCAST_OPTION": ["위치리셋", BR_RESET]})
    r_st0 = setvar(bs, "유상태", V_GSTATE, 0)
    r_dir2 = setvar(bs, "유방향", V_GDIR, 2)
    rcell_first, _ = start_cell_seq()
    r_goto = goto_cell_block()
    r_cost = costume_by_num()
    chain([(h6,bs[h6]),(r_st0,bs[r_st0]),(r_dir2,bs[r_dir2]),
           (rcell_first,bs[rcell_first]),(r_goto,bs[r_goto]),(r_cost,bs[r_cost])])

    return bs

# ============================================================
#  FOOD blocks (도트/펠릿 셀 클론 ≤92)
# ============================================================
def build_food_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    delete_all, add_to, item_of, length_of, replace_at = make_list_helpers(bs)

    # when flag clicked: hide
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # when receive 먹이그리기:
    #   broadcast 먹이지우기 ; wait 0 ; 그릴idx=1 ; repeat 165:
    #     그릴값=item(그릴idx) ; if (그릴값=1 or 그릴값=2): create clone ; 그릴idx++
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["먹이그리기", BR_DRAW]})
    bc_clear = broadcast(bs, "먹이지우기", BR_CLEAR)
    wt0 = gen(); bs[wt0] = mk("control_wait", inputs={"DURATION": num(0)})
    set_di1 = setvar(bs, "그릴idx", V_DRAWIDX, 1)
    # repeat body
    di_v = vrep("그릴idx", V_DRAWIDX); brd_item = item_of("보드", L_BOARD, di_v)
    set_dv = set_reporter(bs, "그릴값", V_DRAWVAL, brd_item)
    dv1 = vrep("그릴값", V_DRAWVAL); c1 = cmp_op("operator_equals", dv1, 1)
    dv2 = vrep("그릴값", V_DRAWVAL); c2 = cmp_op("operator_equals", dv2, 2)
    cor = bool_op("operator_or", c1, c2)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_food = ctrl_if(bs, cor, cclone)
    inc_di = changevar(bs, "그릴idx", V_DRAWIDX, 1)
    chain([(set_dv,bs[set_dv]),(if_food,bs[if_food]),(inc_di,bs[inc_di])])
    rep165 = gen(); bs[rep165] = mk("control_repeat",
        inputs={"TIMES": num(165), "SUBSTACK":[2,set_dv]})
    bs[set_dv]["parent"] = rep165
    chain([(hd,bs[hd]),(bc_clear,bs[bc_clear]),(wt0,bs[wt0]),
           (set_di1,bs[set_di1]),(rep165,bs[rep165])])

    # when I start as clone:
    #   if 그릴값=2: costume power else dot
    #   goto(-168 + ((그릴idx-1) mod 15)*24, 120 - floor((그릴idx-1)/15)*24) ; show
    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=320, y=20)
    dv_c = vrep("그릴값", V_DRAWVAL); c_pow = cmp_op("operator_equals", dv_c, 2)
    cmn_p = gen(); bs[cmn_p] = mk("looks_costume",
        fields={"COSTUME":["power", None]}, shadow=True)
    sw_p = gen(); bs[sw_p] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn_p]})
    bs[cmn_p]["parent"] = sw_p
    cmn_d = gen(); bs[cmn_d] = mk("looks_costume",
        fields={"COSTUME":["dot", None]}, shadow=True)
    sw_d = gen(); bs[sw_d] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn_d]})
    bs[cmn_d]["parent"] = sw_d
    if_cost = ctrl_if_else(bs, c_pow, sw_p, sw_d)
    # col = (그릴idx-1) mod 15
    di_x = vrep("그릴idx", V_DRAWIDX)
    sub1x = op("operator_subtract", di_x, 1)
    modx = gen(); bs[modx] = mk("operator_mod",
        inputs={"NUM1": slot(sub1x), "NUM2": num(15)})
    bs[sub1x]["parent"] = modx
    mulx = op("operator_multiply", modx, CELL)
    addx = op("operator_add", mulx, ORIGIN_X)
    # row = floor((그릴idx-1)/15)
    di_y = vrep("그릴idx", V_DRAWIDX)
    sub1y = op("operator_subtract", di_y, 1)
    divy = gen(); bs[divy] = mk("operator_divide",
        inputs={"NUM1": slot(sub1y), "NUM2": num(15)})
    bs[sub1y]["parent"] = divy
    floory = gen(); bs[floory] = mk("operator_mathop",
        inputs={"NUM": slot(divy)}, fields={"OPERATOR":["floor", None]})
    bs[divy]["parent"] = floory
    muly = op("operator_multiply", floory, CELL)
    suby = gen(); bs[suby] = mk("operator_subtract",
        inputs={"NUM1": num(ORIGIN_Y), "NUM2": slot(muly)})
    bs[muly]["parent"] = suby
    goto_c = gen(); bs[goto_c] = mk("motion_gotoxy",
        inputs={"X": slot(addx), "Y": slot(suby)})
    bs[addx]["parent"] = goto_c; bs[suby]["parent"] = goto_c
    show_c = gen(); bs[show_c] = mk("looks_show")
    chain([(sc,bs[sc]),(if_cost,bs[if_cost]),(goto_c,bs[goto_c]),(show_c,bs[show_c])])

    # when receive 먹이지우기 (클론만): delete this clone
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=320, y=320,
        fields={"BROADCAST_OPTION": ["먹이지우기", BR_CLEAR]})
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    chain([(hc,bs[hc]),(del_c,bs[del_c])])

    return bs

# ============================================================
#  BANNER blocks
# ============================================================
def build_banner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # when flag clicked: hide ; goto 0,0 ; go to front
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front])])

    # when receive 게임시작: READY 1.2s 표시 후 hide ; wait until 게임오버/승리 ; 표시
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    cmn_r = gen(); bs[cmn_r] = mk("looks_costume",
        fields={"COSTUME":["ready", None]}, shadow=True)
    sw_r = gen(); bs[sw_r] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn_r]})
    bs[cmn_r]["parent"] = sw_r
    sh_r = gen(); bs[sh_r] = mk("looks_show")
    wt_r = gen(); bs[wt_r] = mk("control_wait", inputs={"DURATION": num(1.2)})
    hi_r = gen(); bs[hi_r] = mk("looks_hide")
    # wait until 게임상태=0 OR =2
    st1 = vrep("게임상태", V_STATE); c0 = cmp_op("operator_equals", st1, 0)
    st2 = vrep("게임상태", V_STATE); c2s = cmp_op("operator_equals", st2, 2)
    cor = bool_op("operator_or", c0, c2s)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION":[2,cor]})
    bs[cor]["parent"] = wu
    # if 게임상태=0: gameover ; if =2: win
    st3 = vrep("게임상태", V_STATE); c0b = cmp_op("operator_equals", st3, 0)
    cmn_go = gen(); bs[cmn_go] = mk("looks_costume",
        fields={"COSTUME":["gameover", None]}, shadow=True)
    sw_go = gen(); bs[sw_go] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn_go]})
    bs[cmn_go]["parent"] = sw_go
    if_go = ctrl_if(bs, c0b, sw_go)
    st4 = vrep("게임상태", V_STATE); c2b = cmp_op("operator_equals", st4, 2)
    cmn_w = gen(); bs[cmn_w] = mk("looks_costume",
        fields={"COSTUME":["win", None]}, shadow=True)
    sw_w = gen(); bs[sw_w] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn_w]})
    bs[cmn_w]["parent"] = sw_w
    if_w = ctrl_if(bs, c2b, sw_w)
    sh_end = gen(); bs[sh_end] = mk("looks_show")
    chain([(h2,bs[h2]),(sw_r,bs[sw_r]),(sh_r,bs[sh_r]),(wt_r,bs[wt_r]),(hi_r,bs[hi_r]),
           (wu,bs[wu]),(if_go,bs[if_go]),(if_w,bs[if_w]),(sh_end,bs[sh_end])])

    # when receive 위치리셋: READY 잠깐 표시
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=320, y=200,
        fields={"BROADCAST_OPTION": ["위치리셋", BR_RESET]})
    cmn_r2 = gen(); bs[cmn_r2] = mk("looks_costume",
        fields={"COSTUME":["ready", None]}, shadow=True)
    sw_r2 = gen(); bs[sw_r2] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cmn_r2]})
    bs[cmn_r2]["parent"] = sw_r2
    sh_r2 = gen(); bs[sh_r2] = mk("looks_show")
    wt_r2 = gen(); bs[wt_r2] = mk("control_wait", inputs={"DURATION": num(1.0)})
    hi_r2 = gen(); bs[hi_r2] = mk("looks_hide")
    chain([(h3,bs[h3]),(sw_r2,bs[sw_r2]),(sh_r2,bs[sh_r2]),(wt_r2,bs[wt_r2]),(hi_r2,bs[hi_r2])])

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

    bg_md5    = write_svg(BG_SVG)
    pac_md5   = write_svg(PACMAN_SVG)
    gr_md5    = write_svg(GHOST_RED)
    gp_md5    = write_svg(GHOST_PINK)
    gc_md5    = write_svg(GHOST_CYAN)
    go_md5    = write_svg(GHOST_ORANGE)
    gs_md5    = write_svg(GHOST_SCARED)
    ge_md5    = write_svg(GHOST_EYES)
    dot_md5   = write_svg(DOT_SVG)
    pw_md5    = write_svg(POWER_SVG)
    ready_md5 = write_svg(READY_SVG)
    over_md5  = write_svg(GAMEOVER_SVG)
    win_md5   = write_svg(WIN_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    stage_blocks  = build_stage_blocks()
    pacman_blocks = build_pacman_blocks()
    ghost_blocks  = build_ghost_blocks()
    food_blocks   = build_food_blocks()
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
            V_BEST:    ["최고기록", 0],
            V_STATE:   ["게임상태", 1],
            V_LIFE:    ["라이프", 3],
            V_REMAIN:  ["남은먹이", 92],
            V_STEP:    ["스텝간격", 0.16],
            V_NEXTDIR: ["다음방향", 0],
            V_PACDIR:  ["팩방향", 0],
            V_PACCOL:  ["팩col", PAC_START_COL],
            V_PACROW:  ["팩row", PAC_START_ROW],
            V_PACX:    ["팩X", PAC_START_X],
            V_PACY:    ["팩Y", PAC_START_Y],
            V_POWER:   ["파워타이머", 0],
            V_GISSUE:  ["유령발급", 0],
            # 팩맨 스텝 임시 (글로벌)
            V_TCOL:    ["시험col", 0],
            V_TROW:    ["시험row", 0],
            V_NCOL:    ["다col", 0],
            V_NROW:    ["다row", 0],
            V_PIDX:    ["먹idx", 0],
        },
        "lists": {
            L_BOARD: ["보드", [str(v) for v in BOARD0]],
        },
        "broadcasts": {
            BR_START: "게임시작", BR_STEP: "스텝", BR_DRAW: "먹이그리기",
            BR_CLEAR: "먹이지우기", BR_PWON: "파워시작", BR_PWOFF: "파워끝",
            BR_HIT: "팩맨피격", BR_RESET: "위치리셋",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "미로", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    pacman = {
        "isStage": False, "name": "팩맨",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pacman_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "pac", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pac_md5, "md5ext": f"{pac_md5}.svg",
            "rotationCenterX": 11, "rotationCenterY": 11
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": True,
        "x": PAC_START_X, "y": PAC_START_Y, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    def ghost_costume(name, m):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": m, "md5ext": f"{m}.svg",
                "rotationCenterX": 11, "rotationCenterY": 11}

    ghost = {
        "isStage": False, "name": "유령",
        "variables": {
            V_GNUM:   ["유령번호", 0], V_GCOL: ["유col", 7], V_GROW: ["유row", 5],
            V_GDIR:   ["유방향", 2], V_GSTATE: ["유상태", 0],
            V_GCAND:  ["후보", 0], V_GTRY: ["시험방향", 0],
            V_GBEST:  ["베스트방향", 0], V_GMIN: ["최소거리", 9999],
            V_GNC:    ["유nc", 0], V_GNR: ["유nr", 0],
            V_GTC:    ["유목표col", 0], V_GTR: ["유목표row", 0],
            V_GPCT:   ["추격확률", 0], V_GPICK: ["랜덤선택", 0],
            V_GSEEN:  ["본후보", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": ghost_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            ghost_costume("red", gr_md5),
            ghost_costume("pink", gp_md5),
            ghost_costume("cyan", gc_md5),
            ghost_costume("orange", go_md5),
            ghost_costume("scared", gs_md5),
            ghost_costume("eyes", ge_md5),
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    food = {
        "isStage": False, "name": "먹이",
        "variables": {
            V_DRAWIDX: ["그릴idx", 0],
            V_DRAWVAL: ["그릴값", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": food_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "dot", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": dot_md5, "md5ext": f"{dot_md5}.svg",
             "rotationCenterX": 4, "rotationCenterY": 4},
            {"name": "power", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pw_md5, "md5ext": f"{pw_md5}.svg",
             "rotationCenterX": 8, "rotationCenterY": 8},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    banner = {
        "isStage": False, "name": "배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": banner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "ready", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ready_md5, "md5ext": f"{ready_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 75},
            {"name": "gameover", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": over_md5, "md5ext": f"{over_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 75},
            {"name": "win", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": win_md5, "md5ext": f"{win_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 75},
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
         "visible": True, "sliderMin": 0, "sliderMax": 10000, "isDiscrete": True},
        {"id": V_LIFE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라이프"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
        {"id": V_REMAIN, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "남은먹이"}, "spriteName": None,
         "value": 92, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 92, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, pacman, ghost, food, banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "pacman-mini-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # ---- self-check: valid JSON + valid zip + block 참조 무결성 ----
    with open(pj, "r", encoding="utf-8") as f:
        proj = json.load(f)
    bad = zipfile.ZipFile(OUTPUT).testzip()
    assert bad is None, f"corrupt zip member: {bad}"

    # 블록 참조 무결성: 각 타깃 내 next/parent/SUBSTACK/input slot 이 같은 타깃 안에 존재
    for tgt in proj["targets"]:
        blks = tgt["blocks"]
        ids = set(blks.keys())
        for bid, b in blks.items():
            if not isinstance(b, dict):  # 변수/리스트 모니터 등 (없음)
                continue
            nx = b.get("next");  pa = b.get("parent")
            assert nx is None or nx in ids, f"{tgt['name']}:{bid} dangling next {nx}"
            assert pa is None or pa in ids, f"{tgt['name']}:{bid} dangling parent {pa}"
            for ikey, iv in b.get("inputs", {}).items():
                # iv = [shadowType, value, (maybe shadow)]
                for cell in iv[1:]:
                    if isinstance(cell, str):
                        assert cell in ids, f"{tgt['name']}:{bid} input {ikey} -> {cell} missing"
                    elif isinstance(cell, list) and cell and cell[0] == 2:
                        ref = cell[1]
                        if isinstance(ref, str):
                            assert ref in ids, f"{tgt['name']}:{bid} input {ikey} substack -> {ref} missing"

    total = (len(stage_blocks) + len(pacman_blocks) + len(ghost_blocks)
             + len(food_blocks) + len(banner_blocks))
    print(f"wrote {OUTPUT}")
    print(f"  stage:  {len(stage_blocks)} blocks")
    print(f"  pacman: {len(pacman_blocks)} blocks")
    print(f"  ghost:  {len(ghost_blocks)} blocks")
    print(f"  food:   {len(food_blocks)} blocks")
    print(f"  banner: {len(banner_blocks)} blocks")
    print(f"  TOTAL:  {total} blocks")
    print(f"  targets: 5")
    print(f"  board len: {len(BOARD0)} (dots+pellets={BOARD0.count(1)+BOARD0.count(2)})")

if __name__ == "__main__":
    main()
