#!/usr/bin/env python3
"""오델로 (리버시) — 2인 플레이(흑 vs 백). 빈 칸을 클릭해 돌을 놓으면 8방향으로
상대 돌을 뒤집는다. 합법 수만 둘 수 있고, 둘 곳 없으면 자동 패스, 양쪽 다 없으면
게임 종료 후 돌 수로 승패 판정.

설계 메모(검증 가능하도록 좌표/리스트 기반):
- 보드: 길이 64 리스트(0=빈칸,1=흑,2=백). 칸번호 n=행*8+열+1 (행/열 0..7).
- 렌더: '돌' 스프라이트 클론 64개, 각자 칸번호로 위치 잡고 보드[칸번호] 보고 코스튬/표시.
- 입력: '보드' 스프라이트 클릭 → 마우스 좌표 → (행,열). 빈 칸이면 수계산.
- 핵심 로직은 '보드' 스프라이트에. 재사용 루틴은 broadcast-and-wait 로 동기 호출.
  · 수계산  : (행,열,차례,상대) → 뒤집목록 채우고 합법(0/1) 설정. 픽셀 touching 안 씀.
  · 있는수확인: 차례가 둘 수 있는 빈 칸이 하나라도 있으면 있음=1.
  · 차례전환 : 점수 재집계 → 차례 교대(패스/종료 처리) → 안내문 갱신.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "오델로.sb3")

CELL = 40
X0   = -140   # 열 0 의 중심 x
Y0   =  140   # 행 0 의 중심 y

# ============================================================
#  SVG assets
# ============================================================
def _board_svg():
    lines = []
    for i in range(9):
        p = i * CELL
        lines.append(f'  <line x1="{p}" y1="0" x2="{p}" y2="320" stroke="#1B5E20" stroke-width="2"/>')
        lines.append(f'  <line x1="0" y1="{p}" x2="320" y2="{p}" stroke="#1B5E20" stroke-width="2"/>')
    dots = []
    for (cx, cy) in [(80, 80), (240, 80), (80, 240), (240, 240)]:
        dots.append(f'  <circle cx="{cx}" cy="{cy}" r="4" fill="#0B3D0B"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">\n'
            '  <rect x="0" y="0" width="320" height="320" fill="#2E7D32"/>\n'
            + "\n".join(lines) + "\n" + "\n".join(dots) + "\n</svg>")

BOARD_SVG = _board_svg()

BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect x="0" y="0" width="480" height="360" fill="#10241A"/>
  <rect x="6" y="6" width="468" height="348" rx="10" fill="#173324"/>
  <text x="240" y="26" text-anchor="middle" fill="#A5D6A7"
        font-family="Arial, Helvetica, sans-serif" font-size="20" font-weight="bold">오델로 · 리버시</text>
  <text x="240" y="350" text-anchor="middle" fill="#80CBC4"
        font-family="Arial, Helvetica, sans-serif" font-size="12">빈 칸 클릭 → 돌 놓기 (합법 수만 가능)</text>
</svg>"""

DISC_BLACK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="16" fill="#1A1A1A" stroke="#000000" stroke-width="1.5"/>
  <ellipse cx="15" cy="14" rx="6" ry="4" fill="#555555" opacity="0.5"/>
</svg>"""

DISC_WHITE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="16" fill="#FAFAFA" stroke="#9E9E9E" stroke-width="1.5"/>
  <ellipse cx="15" cy="14" rx="6" ry="4" fill="#FFFFFF" opacity="0.9"/>
</svg>"""

# ============================================================
#  template helpers (그대로 복사)
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
    return vrep, op, bool_op, cmp_op

# ---- 추가 헬퍼 (블록 dict bs 받음) ----
def _val(bs, v):
    """숫자/문자 리터럴 → num/text, 블록 id(str 이면서 bs 에 존재) → slot."""
    if isinstance(v, str) and v in bs:
        return ("slot", v)
    if isinstance(v, (int, float)):
        return ("num", v)
    return ("text", v)

def setv(bs, name, vid, v):
    bid = gen()
    kind, val = _val(bs, v)
    inp = {"VALUE": slot(val) if kind == "slot" else (num(val) if kind == "num" else text_lit(val))}
    bs[bid] = mk("data_setvariableto", inputs=inp, fields={"VARIABLE": [name, vid]})
    if kind == "slot": bs[val]["parent"] = bid
    return bid

def changev(bs, name, vid, v):
    bid = gen()
    kind, val = _val(bs, v)
    inp = {"VALUE": slot(val) if kind == "slot" else num(val)}
    bs[bid] = mk("data_changevariableby", inputs=inp, fields={"VARIABLE": [name, vid]})
    if kind == "slot": bs[val]["parent"] = bid
    return bid

def addlist(bs, name, lid, item):
    bid = gen()
    kind, val = _val(bs, item)
    inp = {"ITEM": slot(val) if kind == "slot" else (num(val) if kind == "num" else text_lit(val))}
    bs[bid] = mk("data_addtolist", inputs=inp, fields={"LIST": [name, lid]})
    if kind == "slot": bs[val]["parent"] = bid
    return bid

def repllist(bs, name, lid, index, item):
    bid = gen()
    ki, vi = _val(bs, index)
    kt, vt = _val(bs, item)
    inp = {
        "INDEX": slot(vi) if ki == "slot" else (num(vi) if ki == "num" else text_lit(vi)),
        "ITEM":  slot(vt) if kt == "slot" else (num(vt) if kt == "num" else text_lit(vt)),
    }
    bs[bid] = mk("data_replaceitemoflist", inputs=inp, fields={"LIST": [name, lid]})
    if ki == "slot": bs[vi]["parent"] = bid
    if kt == "slot": bs[vt]["parent"] = bid
    return bid

def delall(bs, name, lid):
    bid = gen(); bs[bid] = mk("data_deletealloflist", fields={"LIST": [name, lid]}); return bid

def itemof(bs, name, lid, index):
    bid = gen()
    ki, vi = _val(bs, index)
    inp = {"INDEX": slot(vi) if ki == "slot" else (num(vi) if ki == "num" else text_lit(vi))}
    bs[bid] = mk("data_itemoflist", inputs=inp, fields={"LIST": [name, lid]})
    if ki == "slot": bs[vi]["parent"] = bid
    return bid

def lenof(bs, name, lid):
    bid = gen(); bs[bid] = mk("data_lengthoflist", fields={"LIST": [name, lid]}); return bid

def notop(bs, a):
    bid = gen(); bs[bid] = mk("operator_not", inputs={"OPERAND": [2, a]}); bs[a]["parent"] = bid; return bid

def roundop(bs, x):
    bid = gen()
    kind, val = _val(bs, x)
    bs[bid] = mk("operator_round", inputs={"NUM": slot(val) if kind == "slot" else num(val)})
    if kind == "slot": bs[val]["parent"] = bid
    return bid

def mathop(bs, oper, x):
    bid = gen()
    kind, val = _val(bs, x)
    bs[bid] = mk("operator_mathop", inputs={"NUM": slot(val) if kind == "slot" else num(val)},
                 fields={"OPERATOR": [oper, None]})
    if kind == "slot": bs[val]["parent"] = bid
    return bid

def if_(bs, cond, body):
    bid = gen(); bs[bid] = mk("control_if", inputs={"CONDITION": [2, cond], "SUBSTACK": [2, body]})
    bs[cond]["parent"] = bid; bs[body]["parent"] = bid; return bid

def ifelse_(bs, cond, b1, b2):
    bid = gen(); bs[bid] = mk("control_if_else",
        inputs={"CONDITION": [2, cond], "SUBSTACK": [2, b1], "SUBSTACK2": [2, b2]})
    bs[cond]["parent"] = bid; bs[b1]["parent"] = bid; bs[b2]["parent"] = bid; return bid

def repeat_(bs, times, body):
    bid = gen()
    kind, val = _val(bs, times)
    bs[bid] = mk("control_repeat", inputs={"TIMES": slot(val) if kind == "slot" else num(val),
                                           "SUBSTACK": [2, body]})
    if kind == "slot": bs[val]["parent"] = bid
    bs[body]["parent"] = bid; return bid

def repuntil_(bs, cond, body):
    bid = gen(); bs[bid] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond], "SUBSTACK": [2, body]})
    bs[cond]["parent"] = bid; bs[body]["parent"] = bid; return bid

def bcast_wait(bs, name, msgid):
    menu = gen(); bs[menu] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, msgid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcastandwait", inputs={"BROADCAST_INPUT": [1, menu]})
    bs[menu]["parent"] = b; return b

# ============================================================
#  IDs
# ============================================================
V_STATE="vState"; V_TURN="vTurn"; V_OPP="vOpp"; V_BLACK="vBlack"; V_WHITE="vWhite"
V_ROW="vRow"; V_COL="vCol"; V_CLICK="vClick"; V_IDX="vIdx"; V_D="vD"; V_DR="vDr"
V_DC="vDc"; V_RR="vRr"; V_CC="vCc"; V_SCAN="vScan"; V_LEGAL="vLegal"; V_HAS="vHas"
V_LOOP="vLoop"; V_J="vJ"; V_K="vK"; V_INFO="vInfo"; V_ISSUE="vIssue"
V_CELLNO="vCellNo"   # 돌 sprite-local

L_BOARD="lBoard"; L_DR="lDR"; L_DC="lDC"; L_FLIP="lFlip"; L_TMP="lTmp"

BR_START="brStart"; BR_DRAW="brDraw"; BR_CALC="brCalc"; BR_TURN="brTurn"; BR_HAS="brHas"
BR_PLACE="brPlace"

DIRS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

# ============================================================
#  STAGE blocks (초기화)
# ============================================================
def build_stage_blocks():
    bs = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]

    # 방향 리스트
    seq.append((delall(bs,"DR",L_DR), None))
    for dr,_ in DIRS: seq.append((addlist(bs,"DR",L_DR,dr), None))
    seq.append((delall(bs,"DC",L_DC), None))
    for _,dc in DIRS: seq.append((addlist(bs,"DC",L_DC,dc), None))

    # 보드 64칸 0으로 채우기
    seq.append((delall(bs,"보드",L_BOARD), None))
    body_add0 = addlist(bs,"보드",L_BOARD,0)
    seq.append((repeat_(bs, 64, body_add0), None))
    # 중앙 4돌: (3,3)=백28 (3,4)=흑29 (4,3)=흑36 (4,4)=백37
    seq.append((repllist(bs,"보드",L_BOARD,28,2), None))
    seq.append((repllist(bs,"보드",L_BOARD,29,1), None))
    seq.append((repllist(bs,"보드",L_BOARD,36,1), None))
    seq.append((repllist(bs,"보드",L_BOARD,37,2), None))

    seq.append((setv(bs,"차례",V_TURN,1), None))
    seq.append((setv(bs,"게임상태",V_STATE,1), None))
    seq.append((setv(bs,"흑점수",V_BLACK,2), None))
    seq.append((setv(bs,"백점수",V_WHITE,2), None))
    seq.append((setv(bs,"안내",V_INFO,"● 흑 차례"), None))

    seq.append((bcast_wait(bs,"게임시작",BR_START), None))
    seq.append((bcast_wait(bs,"보드그리기",BR_DRAW), None))

    # fill in real block objects for chaining
    seq = [(bid, bs[bid]) for bid,_ in seq]
    chain(seq)
    return bs

# ============================================================
#  helper: onboard 조건 reporter
# ============================================================
def _in07(vrep, cmp_op, bool_op, bs, name, vid):
    a = vrep(name, vid); lt0 = cmp_op("operator_lt", a, 0)
    b = vrep(name, vid); gt7 = cmp_op("operator_gt", b, 7)
    return bool_op("operator_and", notop(bs, lt0), notop(bs, gt7))

def _idx(vrep, op, rname, rvid, cname, cvid):
    """rr*8 + cc + 1 reporter."""
    r = vrep(rname, rvid); m = op("operator_multiply", r, 8)
    c = vrep(cname, cvid); a = op("operator_add", m, c)
    return op("operator_add", a, 1)

# ============================================================
#  BOARD sprite blocks (입력 + 모든 게임 로직)
# ============================================================
def build_board_blocks():
    bs = {}
    vrep, op, bool_op, cmp_op = make_helpers(bs)

    # --- when flag clicked: 위치/크기/표시 ---
    h0 = gen(); bs[h0] = mk("event_whenflagclicked", top=True, x=20, y=20)
    blk_goto = gen(); bs[blk_goto] = mk("motion_gotoxy", inputs={"X":num(0),"Y":num(0)})
    blk_size = gen(); bs[blk_size] = mk("looks_setsizeto", inputs={"SIZE":num(100)})
    blk_show = gen(); bs[blk_show] = mk("looks_show")
    chain([(h0,bs[h0]),(blk_goto,bs[blk_goto]),(blk_size,bs[blk_size]),(blk_show,bs[blk_show])])

    # ============================================================
    #  when this sprite clicked: 마우스 → (행,열) 계산 후 '착수' 발신
    #  (실제 착수 로직은 '착수' 수신부에 — 입력/로직 분리로 headless 검증 가능)
    # ============================================================
    hc = gen(); bs[hc] = mk("event_whenthisspriteclicked", top=True, x=20, y=160)

    # 열 = round((mouseX+140)/40)
    mx = gen(); bs[mx] = mk("sensing_mousex")
    addx = op("operator_add", mx, 140)
    divx = op("operator_divide", addx, CELL)
    set_col = setv(bs,"열",V_COL, roundop(bs, divx))
    # 행 = round((140-mouseY)/40)
    my = gen(); bs[my] = mk("sensing_mousey")
    suby = gen(); bs[suby] = mk("operator_subtract", inputs={"NUM1":num(140),"NUM2":slot(my)}); bs[my]["parent"]=suby
    divy = op("operator_divide", suby, CELL)
    set_row = setv(bs,"행",V_ROW, roundop(bs, divy))

    # 유효: 0<=행<=7 and 0<=열<=7
    valid = bool_op("operator_and",
                    _in07(vrep,cmp_op,bool_op,bs,"행",V_ROW),
                    _in07(vrep,cmp_op,bool_op,bs,"열",V_COL))
    bw_place_click = bcast_wait(bs,"착수",BR_PLACE)
    if_valid = if_(bs, valid, bw_place_click)
    chain([(set_col,bs[set_col]),(set_row,bs[set_row]),(if_valid,bs[if_valid])])
    playing = cmp_op("operator_equals", vrep("게임상태",V_STATE), 1)
    if_play = if_(bs, playing, set_col)
    chain([(hc,bs[hc]),(if_play,bs[if_play])])

    # ============================================================
    #  when receive 착수 : (행,열,차례) 에 두기 시도 — 빈칸+합법일 때만
    # ============================================================
    hp = gen(); bs[hp] = mk("event_whenbroadcastreceived", top=True, x=320, y=420,
        fields={"BROADCAST_OPTION":["착수",BR_PLACE]})
    set_click = setv(bs,"클릭칸",V_CLICK, _idx(vrep,op,"행",V_ROW,"열",V_COL))
    empty = cmp_op("operator_equals", itemof(bs,"보드",L_BOARD, vrep("클릭칸",V_CLICK)), 0)
    set_opp = setv(bs,"상대",V_OPP, op("operator_subtract", 3, vrep("차례",V_TURN)))
    bw_calc = bcast_wait(bs,"수계산",BR_CALC)
    legal1 = cmp_op("operator_equals", vrep("합법",V_LEGAL), 1)
    place = repllist(bs,"보드",L_BOARD, vrep("클릭칸",V_CLICK), vrep("차례",V_TURN))
    set_k = setv(bs,"k",V_K, 1)
    flip_one = repllist(bs,"보드",L_BOARD, itemof(bs,"뒤집목록",L_FLIP, vrep("k",V_K)), vrep("차례",V_TURN))
    inc_k = changev(bs,"k",V_K,1)
    chain([(flip_one,bs[flip_one]),(inc_k,bs[inc_k])])
    flip_loop = repeat_(bs, lenof(bs,"뒤집목록",L_FLIP), flip_one)
    bw_draw = bcast_wait(bs,"보드그리기",BR_DRAW)
    bw_turn = bcast_wait(bs,"차례전환",BR_TURN)
    chain([(place,bs[place]),(set_k,bs[set_k]),(flip_loop,bs[flip_loop]),
           (bw_draw,bs[bw_draw]),(bw_turn,bs[bw_turn])])
    if_legal = if_(bs, legal1, place)
    chain([(set_opp,bs[set_opp]),(bw_calc,bs[bw_calc]),(if_legal,bs[if_legal])])
    if_empty = if_(bs, empty, set_opp)
    chain([(hp,bs[hp]),(set_click,bs[set_click]),(if_empty,bs[if_empty])])

    # ============================================================
    #  when receive 수계산 : (행,열,차례,상대) → 뒤집목록/합법
    # ============================================================
    hcal = gen(); bs[hcal] = mk("event_whenbroadcastreceived", top=True, x=320, y=20,
        fields={"BROADCAST_OPTION":["수계산",BR_CALC]})
    c_delflip = delall(bs,"뒤집목록",L_FLIP)
    c_setlegal0 = setv(bs,"합법",V_LEGAL,0)
    c_setd = setv(bs,"d",V_D,1)

    # 루프 8방향 본체
    set_dr = setv(bs,"dr",V_DR, itemof(bs,"DR",L_DR, vrep("d",V_D)))
    set_dc = setv(bs,"dc",V_DC, itemof(bs,"DC",L_DC, vrep("d",V_D)))
    set_rr = setv(bs,"rr",V_RR, op("operator_add", vrep("행",V_ROW), vrep("dr",V_DR)))
    set_cc = setv(bs,"cc",V_CC, op("operator_add", vrep("열",V_COL), vrep("dc",V_DC)))
    del_tmp = delall(bs,"임시목록",L_TMP)
    set_scan1 = setv(bs,"스캔",V_SCAN,1)

    # 스캔 루프 본체
    onb = bool_op("operator_and",
                  _in07(vrep,cmp_op,bool_op,bs,"rr",V_RR),
                  _in07(vrep,cmp_op,bool_op,bs,"cc",V_CC))
    set_idx = setv(bs,"인덱스",V_IDX, _idx(vrep,op,"rr",V_RR,"cc",V_CC))
    # ifelse 보드[인덱스]=상대
    is_opp = cmp_op("operator_equals", itemof(bs,"보드",L_BOARD, vrep("인덱스",V_IDX)), vrep("상대",V_OPP))
    add_tmp = addlist(bs,"임시목록",L_TMP, vrep("인덱스",V_IDX))
    adv_rr = changev(bs,"rr",V_RR, vrep("dr",V_DR))
    adv_cc = changev(bs,"cc",V_CC, vrep("dc",V_DC))
    chain([(add_tmp,bs[add_tmp]),(adv_rr,bs[adv_rr]),(adv_cc,bs[adv_cc])])
    # else: if 보드=차례 and len임시>=1 → append 임시 to 뒤집 ; 스캔=0
    is_self = cmp_op("operator_equals", itemof(bs,"보드",L_BOARD, vrep("인덱스",V_IDX)), vrep("차례",V_TURN))
    tmp_ge1 = notop(bs, cmp_op("operator_lt", lenof(bs,"임시목록",L_TMP), 1))
    cond_cap = bool_op("operator_and", is_self, tmp_ge1)
    set_j = setv(bs,"j",V_J,1)
    app_one = addlist(bs,"뒤집목록",L_FLIP, itemof(bs,"임시목록",L_TMP, vrep("j",V_J)))
    inc_j = changev(bs,"j",V_J,1)
    chain([(app_one,bs[app_one]),(inc_j,bs[inc_j])])
    app_loop = repeat_(bs, lenof(bs,"임시목록",L_TMP), app_one)
    chain([(set_j,bs[set_j]),(app_loop,bs[app_loop])])
    if_cap = if_(bs, cond_cap, set_j)
    set_scan0_a = setv(bs,"스캔",V_SCAN,0)
    chain([(if_cap,bs[if_cap]),(set_scan0_a,bs[set_scan0_a])])
    ie_oppself = ifelse_(bs, is_opp, add_tmp, if_cap)
    # if onboard: ie_oppself  else: 스캔=0
    set_scan0_b = setv(bs,"스캔",V_SCAN,0)
    chain([(set_idx,bs[set_idx]),(ie_oppself,bs[ie_oppself])])
    ie_onb = ifelse_(bs, onb, set_idx, set_scan0_b)
    # 스캔 루프: repeat until 스캔=0
    scan_done = cmp_op("operator_equals", vrep("스캔",V_SCAN), 0)
    scan_loop = repuntil_(bs, scan_done, ie_onb)

    inc_d = changev(bs,"d",V_D,1)
    chain([(set_dr,bs[set_dr]),(set_dc,bs[set_dc]),(set_rr,bs[set_rr]),(set_cc,bs[set_cc]),
           (del_tmp,bs[del_tmp]),(set_scan1,bs[set_scan1]),(scan_loop,bs[scan_loop]),(inc_d,bs[inc_d])])
    dir_loop = repeat_(bs, 8, set_dr)

    # 합법 = (len 뒤집목록 >= 1)
    flip_ge1 = notop(bs, cmp_op("operator_lt", lenof(bs,"뒤집목록",L_FLIP), 1))
    set_legal_b = setv(bs,"합법",V_LEGAL,1)
    if_legal2 = if_(bs, flip_ge1, set_legal_b)

    chain([(hcal,bs[hcal]),(c_delflip,bs[c_delflip]),(c_setlegal0,bs[c_setlegal0]),
           (c_setd,bs[c_setd]),(dir_loop,bs[dir_loop]),(if_legal2,bs[if_legal2])])

    # ============================================================
    #  when receive 있는수확인 : 차례가 둘 곳 있나 → 있음
    # ============================================================
    hhas = gen(); bs[hhas] = mk("event_whenbroadcastreceived", top=True, x=620, y=20,
        fields={"BROADCAST_OPTION":["있는수확인",BR_HAS]})
    h_set0 = setv(bs,"있음",V_HAS,0)
    h_setloop = setv(bs,"칸",V_LOOP,1)
    # body: if 보드[칸]=0 { 행=floor((칸-1)/8); 열=(칸-1) mod 8; 수계산; if 합법=1 있음=1 } ; 칸++
    cell_empty = cmp_op("operator_equals", itemof(bs,"보드",L_BOARD, vrep("칸",V_LOOP)), 0)
    set_row2 = setv(bs,"행",V_ROW, mathop(bs,"floor",
                    op("operator_divide", op("operator_subtract", vrep("칸",V_LOOP), 1), 8)))
    set_col2 = setv(bs,"열",V_COL, op("operator_mod",
                    op("operator_subtract", vrep("칸",V_LOOP), 1), 8))
    bw_calc2 = bcast_wait(bs,"수계산",BR_CALC)
    legal3 = cmp_op("operator_equals", vrep("합법",V_LEGAL), 1)
    set_has1 = setv(bs,"있음",V_HAS,1)
    if_has = if_(bs, legal3, set_has1)
    chain([(set_row2,bs[set_row2]),(set_col2,bs[set_col2]),(bw_calc2,bs[bw_calc2]),(if_has,bs[if_has])])
    if_cellempty = if_(bs, cell_empty, set_row2)
    inc_loop = changev(bs,"칸",V_LOOP,1)
    chain([(if_cellempty,bs[if_cellempty]),(inc_loop,bs[inc_loop])])
    has_loop = repeat_(bs, 64, if_cellempty)
    chain([(hhas,bs[hhas]),(h_set0,bs[h_set0]),(h_setloop,bs[h_setloop]),(has_loop,bs[has_loop])])

    # ============================================================
    #  when receive 차례전환 : 점수재집계 → 차례 교대(패스/종료) → 안내
    # ============================================================
    ht = gen(); bs[ht] = mk("event_whenbroadcastreceived", top=True, x=20, y=420,
        fields={"BROADCAST_OPTION":["차례전환",BR_TURN]})
    # 점수 재집계
    t_b0 = setv(bs,"흑점수",V_BLACK,0)
    t_w0 = setv(bs,"백점수",V_WHITE,0)
    t_cell = setv(bs,"칸",V_LOOP,1)
    cnt_is1 = cmp_op("operator_equals", itemof(bs,"보드",L_BOARD, vrep("칸",V_LOOP)), 1)
    cnt_b = changev(bs,"흑점수",V_BLACK,1)
    if_cb = if_(bs, cnt_is1, cnt_b)
    cnt_is2 = cmp_op("operator_equals", itemof(bs,"보드",L_BOARD, vrep("칸",V_LOOP)), 2)
    cnt_w = changev(bs,"백점수",V_WHITE,1)
    if_cw = if_(bs, cnt_is2, cnt_w)
    cnt_inc = changev(bs,"칸",V_LOOP,1)
    chain([(if_cb,bs[if_cb]),(if_cw,bs[if_cw]),(cnt_inc,bs[cnt_inc])])
    cnt_loop = repeat_(bs, 64, if_cb)

    # 차례 교대 시도
    sw1 = setv(bs,"차례",V_TURN, op("operator_subtract",3, vrep("차례",V_TURN)))
    sw1o= setv(bs,"상대",V_OPP, op("operator_subtract",3, vrep("차례",V_TURN)))
    bw_has1 = bcast_wait(bs,"있는수확인",BR_HAS)
    has0_a = cmp_op("operator_equals", vrep("있음",V_HAS), 0)
    # then(없음): 다시 교대(원래 둔 사람)
    sw2 = setv(bs,"차례",V_TURN, op("operator_subtract",3, vrep("차례",V_TURN)))
    sw2o= setv(bs,"상대",V_OPP, op("operator_subtract",3, vrep("차례",V_TURN)))
    bw_has2 = bcast_wait(bs,"있는수확인",BR_HAS)
    has0_b = cmp_op("operator_equals", vrep("있음",V_HAS), 0)
    # 양쪽 다 없음 → 종료 + 승자
    end_state = setv(bs,"게임상태",V_STATE,0)
    b_gt_w = cmp_op("operator_gt", vrep("흑점수",V_BLACK), vrep("백점수",V_WHITE))
    w_gt_b = cmp_op("operator_gt", vrep("백점수",V_WHITE), vrep("흑점수",V_BLACK))
    info_draw = setv(bs,"안내",V_INFO,"무승부!")
    info_white = setv(bs,"안내",V_INFO,"○ 백 승리!")
    ie_ww = ifelse_(bs, w_gt_b, info_white, info_draw)
    info_black = setv(bs,"안내",V_INFO,"● 흑 승리!")
    ie_winner = ifelse_(bs, b_gt_w, info_black, ie_ww)
    chain([(end_state,bs[end_state]),(ie_winner,bs[ie_winner])])
    # else(원래 둔 사람은 둘 수 있음 → 상대 패스): 안내 with 패스
    turn_is1_p = cmp_op("operator_equals", vrep("차례",V_TURN),1)
    info_b_pass = setv(bs,"안내",V_INFO,"● 흑 차례 (백 패스)")
    info_w_pass = setv(bs,"안내",V_INFO,"○ 백 차례 (흑 패스)")
    ie_pass = ifelse_(bs, turn_is1_p, info_b_pass, info_w_pass)
    ie_bothnone = ifelse_(bs, has0_b, end_state, ie_pass)
    chain([(sw2,bs[sw2]),(sw2o,bs[sw2o]),(bw_has2,bs[bw_has2]),(ie_bothnone,bs[ie_bothnone])])
    # else(새 차례가 둘 수 있음): 보통 안내
    turn_is1 = cmp_op("operator_equals", vrep("차례",V_TURN),1)
    info_b = setv(bs,"안내",V_INFO,"● 흑 차례")
    info_w = setv(bs,"안내",V_INFO,"○ 백 차례")
    ie_norm = ifelse_(bs, turn_is1, info_b, info_w)
    ie_pass_or_norm = ifelse_(bs, has0_a, sw2, ie_norm)
    chain([(sw1,bs[sw1]),(sw1o,bs[sw1o]),(bw_has1,bs[bw_has1]),(ie_pass_or_norm,bs[ie_pass_or_norm])])

    chain([(ht,bs[ht]),(t_b0,bs[t_b0]),(t_w0,bs[t_w0]),(t_cell,bs[t_cell]),
           (cnt_loop,bs[cnt_loop]),(sw1,bs[sw1])])

    return bs

# ============================================================
#  DISC sprite blocks (렌더링)
# ============================================================
def build_disc_blocks():
    bs = {}
    vrep, op, bool_op, cmp_op = make_helpers(bs)

    # flag: hide
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hide0 = gen(); bs[hide0] = mk("looks_hide")
    chain([(h,bs[h]),(hide0,bs[hide0])])

    # 게임시작: 클론 64개 생성
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION":["게임시작",BR_START]})
    hide2 = gen(); bs[hide2] = mk("looks_hide")
    iss0 = setv(bs,"칸발급",V_ISSUE,0)
    inc_iss = changev(bs,"칸발급",V_ISSUE,1)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_",None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION":[1,cmenu]})
    bs[cmenu]["parent"]=cclone
    chain([(inc_iss,bs[inc_iss]),(cclone,bs[cclone])])
    mk_loop = repeat_(bs, 64, inc_iss)
    chain([(h2,bs[h2]),(hide2,bs[hide2]),(iss0,bs[iss0]),(mk_loop,bs[mk_loop])])

    # when I start as clone: 칸번호 채택 + 위치
    hc = gen(); bs[hc] = mk("control_start_as_clone", top=True, x=320, y=160)
    set_no = setv(bs,"칸번호",V_CELLNO, vrep("칸발급",V_ISSUE))
    # c = (칸번호-1) mod 8 ; r = floor((칸번호-1)/8)
    # X = X0 + 40*c
    cmod = op("operator_mod", op("operator_subtract", vrep("칸번호",V_CELLNO),1), 8)
    gx = op("operator_add", X0, op("operator_multiply", CELL, cmod))
    rfl = mathop(bs,"floor", op("operator_divide", op("operator_subtract", vrep("칸번호",V_CELLNO),1), 8))
    gy = op("operator_subtract", Y0, op("operator_multiply", CELL, rfl))
    goto = gen(); bs[goto] = mk("motion_gotoxy", inputs={"X":slot(gx),"Y":slot(gy)})
    bs[gx]["parent"]=goto; bs[gy]["parent"]=goto
    chain([(hc,bs[hc]),(set_no,bs[set_no]),(goto,bs[goto])])

    # when receive 보드그리기: 보드[칸번호] → 코스튬/표시
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=620, y=160,
        fields={"BROADCAST_OPTION":["보드그리기",BR_DRAW]})
    val_is0 = cmp_op("operator_equals", itemof(bs,"보드",L_BOARD, vrep("칸번호",V_CELLNO)), 0)
    hide_c = gen(); bs[hide_c] = mk("looks_hide")
    # else: if =1 흑 else 백
    val_is1 = cmp_op("operator_equals", itemof(bs,"보드",L_BOARD, vrep("칸번호",V_CELLNO)), 1)
    cm_b = gen(); bs[cm_b] = mk("looks_costume", fields={"COSTUME":["흑",None]}, shadow=True)
    sw_b = gen(); bs[sw_b] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cm_b]}); bs[cm_b]["parent"]=sw_b
    show_b = gen(); bs[show_b] = mk("looks_show")
    chain([(sw_b,bs[sw_b]),(show_b,bs[show_b])])
    cm_w = gen(); bs[cm_w] = mk("looks_costume", fields={"COSTUME":["백",None]}, shadow=True)
    sw_w = gen(); bs[sw_w] = mk("looks_switchcostumeto", inputs={"COSTUME":[1,cm_w]}); bs[cm_w]["parent"]=sw_w
    show_w = gen(); bs[show_w] = mk("looks_show")
    chain([(sw_w,bs[sw_w]),(show_w,bs[show_w])])
    ie_bw = ifelse_(bs, val_is1, sw_b, sw_w)
    ie_draw = ifelse_(bs, val_is0, hide_c, ie_bw)
    chain([(hd,bs[hd]),(ie_draw,bs[ie_draw])])

    return bs

# ============================================================
#  ASSEMBLE
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    def wsvg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg","w",encoding="utf-8") as f: f.write(svg)
        return m
    bg_md5    = wsvg(BG_SVG)
    board_md5 = wsvg(BOARD_SVG)
    black_md5 = wsvg(DISC_BLACK_SVG)
    white_md5 = wsvg(DISC_WHITE_SVG)

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_STATE:["게임상태",1], V_TURN:["차례",1], V_OPP:["상대",2],
            V_BLACK:["흑점수",2], V_WHITE:["백점수",2],
            V_ROW:["행",0], V_COL:["열",0], V_CLICK:["클릭칸",1], V_IDX:["인덱스",1],
            V_D:["d",1], V_DR:["dr",0], V_DC:["dc",0], V_RR:["rr",0], V_CC:["cc",0],
            V_SCAN:["스캔",0], V_LEGAL:["합법",0], V_HAS:["있음",0],
            V_LOOP:["칸",1], V_J:["j",1], V_K:["k",1], V_INFO:["안내","● 흑 차례"],
            V_ISSUE:["칸발급",0],
        },
        "lists": {
            L_BOARD:["보드",[]], L_DR:["DR",[]], L_DC:["DC",[]],
            L_FLIP:["뒤집목록",[]], L_TMP:["임시목록",[]],
        },
        "broadcasts": {BR_START:"게임시작", BR_DRAW:"보드그리기", BR_CALC:"수계산",
                       BR_TURN:"차례전환", BR_HAS:"있는수확인", BR_PLACE:"착수"},
        "blocks": build_stage_blocks(), "comments": {},
        "currentCostume": 0,
        "costumes": [{"name":"배경","dataFormat":"svg","assetId":bg_md5,
                      "md5ext":f"{bg_md5}.svg","rotationCenterX":240,"rotationCenterY":180}],
        "sounds": [], "volume":100, "layerOrder":0, "tempo":60,
        "videoTransparency":50, "videoState":"on", "textToSpeechLanguage":None
    }

    board = {
        "isStage": False, "name": "보드",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": build_board_blocks(), "comments": {},
        "currentCostume": 0,
        "costumes": [{"name":"board","bitmapResolution":1,"dataFormat":"svg",
                      "assetId":board_md5,"md5ext":f"{board_md5}.svg",
                      "rotationCenterX":160,"rotationCenterY":160}],
        "sounds": [], "volume":100, "layerOrder":1, "visible":True,
        "x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }

    disc = {
        "isStage": False, "name": "돌",
        "variables": {V_CELLNO:["칸번호",0]}, "lists": {}, "broadcasts": {},
        "blocks": build_disc_blocks(), "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name":"흑","bitmapResolution":1,"dataFormat":"svg","assetId":black_md5,
             "md5ext":f"{black_md5}.svg","rotationCenterX":20,"rotationCenterY":20},
            {"name":"백","bitmapResolution":1,"dataFormat":"svg","assetId":white_md5,
             "md5ext":f"{white_md5}.svg","rotationCenterX":20,"rotationCenterY":20},
        ],
        "sounds": [], "volume":100, "layerOrder":2, "visible":False,
        "x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }

    monitors = [
        {"id":V_BLACK,"mode":"large","opcode":"data_variable","params":{"VARIABLE":"흑점수"},
         "spriteName":None,"value":2,"width":0,"height":0,"x":5,"y":5,"visible":True,
         "sliderMin":0,"sliderMax":64,"isDiscrete":True},
        {"id":V_WHITE,"mode":"large","opcode":"data_variable","params":{"VARIABLE":"백점수"},
         "spriteName":None,"value":2,"width":0,"height":0,"x":360,"y":5,"visible":True,
         "sliderMin":0,"sliderMax":64,"isDiscrete":True},
        {"id":V_INFO,"mode":"large","opcode":"data_variable","params":{"VARIABLE":"안내"},
         "spriteName":None,"value":"● 흑 차례","width":0,"height":0,"x":150,"y":5,"visible":True,
         "sliderMin":0,"sliderMax":100,"isDiscrete":True},
    ]

    project = {
        "targets": [stage, board, disc],
        "monitors": monitors, "extensions": [],
        "meta": {"semver":"3.0.0","vm":"13.7.4-svg","agent":"othello-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj,"w",encoding="utf-8") as f: json.dump(project, f, ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT,"w",zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK): zf.write(f"{WORK}/{fn}", fn)
    with open(pj,"r",encoding="utf-8") as f: json.load(f)
    bad = zipfile.ZipFile(OUTPUT).testzip(); assert bad is None
    print(f"wrote {OUTPUT}")
    print(f"  stage: {len(stage['blocks'])}  board: {len(board['blocks'])}  disc: {len(disc['blocks'])}")
    print(f"  TOTAL: {len(stage['blocks'])+len(board['blocks'])+len(disc['blocks'])} blocks")

if __name__ == "__main__":
    main()
