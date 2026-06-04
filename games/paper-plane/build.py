#!/usr/bin/env python3
"""종이비행기 멀리 던지기 (paper-plane).

2단 타이밍 게이지(각도 0~80 왕복 → 스페이스 고정 → 힘 0~100 왕복 → 스페이스 발사)로
종이비행기를 던진다. 던진 비행기는 중력으로 글라이딩하며 매 턴 바뀌는 바람에 밀린다.
비행기는 화면 왼쪽 밴드(x -180~+40)에서만 실제로 움직이고, 넘어선 거리는 배경/거리마커가
좌측으로 스크롤(카메라)되어 표현된다. 3번 던져 합계/베스트를 겨룬다.

베이스: flappy-bird(dy 적분/지면 충돌), endless-runner/car-race(카메라 스크롤),
asteroids(cos/sin 속도 벡터), cowboy-duel(턴 진행/배너).
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "종이비행기_멀리던지기.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: sky gradient + green hills + ground line + launch hill --------
# 지면선 = Scratch y=-140 → SVG y = 180-(-140) = 320
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="#7EC8F2"/>
      <stop offset="55%"  stop-color="#A8DCF5"/>
      <stop offset="100%" stop-color="#D6F0FB"/>
    </linearGradient>
    <linearGradient id="grass" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="#8BC34A"/>
      <stop offset="100%" stop-color="#558B2F"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <!-- faint distant hills -->
  <ellipse cx="120" cy="330" rx="200" ry="60" fill="#AED581" opacity="0.55"/>
  <ellipse cx="360" cy="335" rx="220" ry="55" fill="#9CCC65" opacity="0.5"/>
  <!-- ground (지면선 y=320) -->
  <rect x="0" y="320" width="480" height="40" fill="url(#grass)"/>
  <line x1="0" y1="320" x2="480" y2="320" stroke="#33691E" stroke-width="3"/>
  <!-- 발사대 언덕 (왼쪽, 피벗 x=-180 → SVG x=60, 위쪽) -->
  <path d="M 0 320 Q 60 270 120 320 Z" fill="#7CB342"/>
  <ellipse cx="60" cy="300" rx="48" ry="22" fill="#689F38" opacity="0.6"/>
  <!-- 작은 풀 장식 -->
  <path d="M 200 320 l 3 -10 l 3 10 z" fill="#33691E" opacity="0.5"/>
  <path d="M 300 320 l 3 -12 l 3 12 z" fill="#33691E" opacity="0.5"/>
  <path d="M 420 320 l 3 -10 l 3 10 z" fill="#33691E" opacity="0.5"/>
</svg>"""

# -------- Paper plane (48x28, nose pointing right) --------
PLANE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="28" viewBox="0 0 48 28">
  <!-- 윗 날개 -->
  <polygon points="2,4 46,14 14,16" fill="#FFFFFF" stroke="#90A4AE" stroke-width="1.2"/>
  <!-- 아랫 날개(그림자) -->
  <polygon points="2,4 46,14 14,24" fill="#E0E6EA" stroke="#90A4AE" stroke-width="1.2"/>
  <!-- 가운데 접힘선 -->
  <line x1="14" y1="16" x2="46" y2="14" stroke="#B0BEC5" stroke-width="1"/>
  <line x1="2"  y1="4"  x2="14" y2="16" stroke="#B0BEC5" stroke-width="1"/>
</svg>"""

# -------- Angle needle (60x10, arrow; rotationCenter at LEFT end = pivot) --------
NEEDLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="10" viewBox="0 0 60 10">
  <line x1="2" y1="5" x2="48" y2="5" stroke="#FF7043" stroke-width="3"/>
  <polygon points="48,1 58,5 48,9" fill="#FF5722"/>
  <circle cx="3" cy="5" r="3" fill="#BF360C"/>
</svg>"""

# -------- Power bar (90x16): border + fill (rotationCenter LEFT for stretch feel) --------
POWERBAR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="90" height="16" viewBox="0 0 90 16">
  <rect x="1" y="1" width="88" height="14" rx="3" fill="#263238" opacity="0.85"
        stroke="#FFFFFF" stroke-width="1.5"/>
  <rect x="4" y="4" width="82" height="8" rx="2" fill="#FFC107"/>
  <rect x="4" y="4" width="40" height="8" rx="2" fill="#FFEB3B"/>
</svg>"""

# -------- Wind arrow (60x24, pointing right; flip left for headwind) --------
WIND_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="24" viewBox="0 0 60 24">
  <line x1="4" y1="12" x2="42" y2="12" stroke="#1976D2" stroke-width="4"/>
  <polygon points="42,3 58,12 42,21" fill="#0D47A1"/>
</svg>"""

# -------- Distance flag (16x30) --------
FLAG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="30" viewBox="0 0 16 30">
  <line x1="3" y1="2" x2="3" y2="30" stroke="#6D4C41" stroke-width="2.5"/>
  <polygon points="4,3 15,8 4,13" fill="#E53935"/>
</svg>"""

# -------- Cloud (72x38) --------
CLOUD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="72" height="38" viewBox="0 0 72 38">
  <ellipse cx="26" cy="24" rx="22" ry="13" fill="#FFFFFF" opacity="0.92"/>
  <ellipse cx="44" cy="20" rx="18" ry="14" fill="#FFFFFF" opacity="0.92"/>
  <ellipse cx="54" cy="26" rx="14" ry="10" fill="#FFFFFF" opacity="0.92"/>
  <ellipse cx="34" cy="14" rx="14" ry="11" fill="#FFFFFF" opacity="0.92"/>
</svg>"""

# -------- Result banner (360x150) --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="5" y="5" width="350" height="140" rx="16"
        fill="#1A237E" opacity="0.93" stroke="#FFEB3B" stroke-width="4"/>
  <text x="180" y="58" text-anchor="middle" fill="#FFEB3B"
        font-family="Arial, sans-serif" font-size="38" font-weight="bold">끝!</text>
  <text x="180" y="92" text-anchor="middle" fill="#FFFFFF"
        font-family="Arial, sans-serif" font-size="18">합계 / 베스트는 위쪽에서 확인</text>
  <text x="180" y="124" text-anchor="middle" fill="#90CAF9"
        font-family="Arial, sans-serif" font-size="14">초록 깃발(&#9654;)로 다시 도전!</text>
</svg>"""

# -------- New best banner (300x100) --------
NEWBEST_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100" viewBox="0 0 300 100">
  <rect x="4" y="4" width="292" height="92" rx="14"
        fill="#FF8F00" opacity="0.95" stroke="#FFF59D" stroke-width="4"/>
  <text x="150" y="62" text-anchor="middle" fill="#FFFFFF"
        font-family="Arial, sans-serif" font-size="40" font-weight="bold">신기록!</text>
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
    return vrep, op, cmp_op, bool_op

def mathop(bs, operator, operand):
    """operator_mathop: sin/cos/atan/abs/floor ..."""
    bid = gen()
    if isinstance(operand, str):
        ins = {"NUM": slot(operand)}
    else:
        ins = {"NUM": num(operand)}
    bs[bid] = mk("operator_mathop", inputs=ins, fields={"OPERATOR": [operator, None]})
    if isinstance(operand, str):
        bs[operand]["parent"] = bid
    return bid

def keypressed(bs, key="space"):
    menu = gen(); bs[menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": [key, None]}, shadow=True)
    press = gen(); bs[press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION":[1, menu]})
    bs[menu]["parent"] = press
    return press

def setvar(bs, name, vid, value):
    bid = gen()
    if isinstance(value, str):
        ins = {"VALUE": slot(value)}
    else:
        ins = {"VALUE": num(value)}
    bs[bid] = mk("data_setvariableto", inputs=ins, fields={"VARIABLE": [name, vid]})
    if isinstance(value, str):
        bs[value]["parent"] = bid
    return bid

def changevar(bs, name, vid, value):
    bid = gen()
    if isinstance(value, str):
        ins = {"VALUE": slot(value)}
    else:
        ins = {"VALUE": num(value)}
    bs[bid] = mk("data_changevariableby", inputs=ins, fields={"VARIABLE": [name, vid]})
    if isinstance(value, str):
        bs[value]["parent"] = bid
    return bid

def bcast(bs, name, bid_):
    menu = gen(); bs[menu] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, bid_]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, menu]})
    bs[menu]["parent"] = b
    return b

def if_block(bs, cond, substack_head):
    bid = gen()
    bs[bid] = mk("control_if", inputs={"CONDITION":[2,cond], "SUBSTACK":[2,substack_head]})
    bs[cond]["parent"] = bid
    bs[substack_head]["parent"] = bid
    return bid

def ifelse_block(bs, cond, head_a, head_b):
    bid = gen()
    bs[bid] = mk("control_if_else",
        inputs={"CONDITION":[2,cond], "SUBSTACK":[2,head_a], "SUBSTACK2":[2,head_b]})
    bs[cond]["parent"] = bid
    bs[head_a]["parent"] = bid
    bs[head_b]["parent"] = bid
    return bid

# ============================================================
#  IDs (10장 컨벤션)
# ============================================================
V_DIST   = "varDist01"    # 거리
V_BEST   = "varBest02"    # 베스트
V_TOTAL  = "varTotal03"   # 합계
V_THROWS = "varThrows04"  # 남은던지기
V_STATE  = "varState05"   # 게임상태 0대기 1비행 2착지 3종료
V_PHASE  = "varPhase06"   # 발사단계 0각도 1힘 2발사
V_ANGLE  = "varAngle07"   # 발사각도
V_POWER  = "varPower08"   # 발사힘
V_GDIR   = "varGdir09"    # 게이지방향
V_GVAL   = "varGval10"    # 게이지값
V_DX     = "varDX11"      # dx
V_DY     = "varDY12"      # dy
V_WIND   = "varWind13"    # 바람
V_SCROLL = "varScroll14"  # 스크롤량

BR_START   = "brStart01"    # 게임시작
BR_AIM     = "brAim02"      # 던지기준비
BR_FIRE    = "brFire03"     # 발사
BR_LAND    = "brLand04"     # 착지
BR_RESULT  = "brResult05"   # 결과
BR_NEWBEST = "brNewBest06"  # 신기록

PIVOT_X = -180
PIVOT_Y = -100
GROUND  = -140
BAND_R  = 40       # 카메라 밴드 오른쪽 끝

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init vars + 게임시작 + 던지기준비 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    for nm, vid, val in [
        ("거리", V_DIST, 0), ("베스트", V_BEST, 0), ("합계", V_TOTAL, 0),
        ("남은던지기", V_THROWS, 3), ("게임상태", V_STATE, 0),
        ("발사단계", V_PHASE, 0), ("발사각도", V_ANGLE, 0),
        ("발사힘", V_POWER, 0), ("게이지방향", V_GDIR, 1),
        ("게이지값", V_GVAL, 0), ("dx", V_DX, 0), ("dy", V_DY, 0),
        ("바람", V_WIND, 0), ("스크롤량", V_SCROLL, 0),
    ]:
        sid = setvar(bs, nm, vid, val); seq.append((sid, bs[sid]))
    bstart = bcast(bs, "게임시작", BR_START); seq.append((bstart, bs[bstart]))
    baim   = bcast(bs, "던지기준비", BR_AIM); seq.append((baim, bs[baim]))
    chain(seq)

    # === when receive 던지기준비: 바람 새로 뽑기 + 리셋 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["던지기준비", BR_AIM]})
    # 바람 = (pick random -15 to 15) / 10
    rnd = gen(); bs[rnd] = mk("operator_random", inputs={"FROM": num(-15), "TO": num(15)})
    div = op("operator_divide", rnd, 10)
    bs[rnd]["parent"] = div
    set_wind = setvar(bs, "바람", V_WIND, div)
    set_dist = setvar(bs, "거리", V_DIST, 0)
    set_scroll = setvar(bs, "스크롤량", V_SCROLL, 0)
    set_state = setvar(bs, "게임상태", V_STATE, 0)
    set_phase = setvar(bs, "발사단계", V_PHASE, 0)
    set_gval = setvar(bs, "게이지값", V_GVAL, 0)
    set_gdir = setvar(bs, "게이지방향", V_GDIR, 1)
    chain([(h2,bs[h2]),(set_wind,bs[set_wind]),(set_dist,bs[set_dist]),
           (set_scroll,bs[set_scroll]),(set_state,bs[set_state]),
           (set_phase,bs[set_phase]),(set_gval,bs[set_gval]),(set_gdir,bs[set_gdir])])

    # === when receive 착지: 합계/베스트/턴 진행 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=340, y=20,
        fields={"BROADCAST_OPTION": ["착지", BR_LAND]})
    # 합계 += 거리
    dist_v = vrep("거리", V_DIST)
    add_total = changevar(bs, "합계", V_TOTAL, dist_v)
    # if 거리 > 베스트: 베스트 = 거리; broadcast 신기록
    dist_v2 = vrep("거리", V_DIST)
    best_v = vrep("베스트", V_BEST)
    cond_best = cmp_op("operator_gt", dist_v2, best_v)
    dist_v3 = vrep("거리", V_DIST)
    set_best = setvar(bs, "베스트", V_BEST, dist_v3)
    bnewbest = bcast(bs, "신기록", BR_NEWBEST)
    chain([(set_best,bs[set_best]),(bnewbest,bs[bnewbest])])
    if_best = if_block(bs, cond_best, set_best)
    # 남은던지기 -= 1
    dec_throws = changevar(bs, "남은던지기", V_THROWS, -1)
    # play sound land (pitch -200)
    pitch_l = gen(); bs[pitch_l] = mk("sound_seteffectto",
        inputs={"VALUE": num(-200)}, fields={"EFFECT":["PITCH", None]})
    snm_l = gen(); bs[snm_l] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd_l = gen(); bs[snd_l] = mk("sound_play", inputs={"SOUND_MENU":[1, snm_l]})
    bs[snm_l]["parent"] = snd_l
    # wait 1.2
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(1.2)})
    # if 남은던지기 > 0: broadcast 던지기준비  else: 게임상태=3; broadcast 결과
    throws_v = vrep("남은던지기", V_THROWS)
    cond_more = cmp_op("operator_gt", throws_v, 0)
    baim2 = bcast(bs, "던지기준비", BR_AIM)
    set_st3 = setvar(bs, "게임상태", V_STATE, 3)
    bresult = bcast(bs, "결과", BR_RESULT)
    chain([(set_st3,bs[set_st3]),(bresult,bs[bresult])])
    ifelse_turn = ifelse_block(bs, cond_more, baim2, set_st3)
    chain([(h3,bs[h3]),(add_total,bs[add_total]),(if_best,bs[if_best]),
           (dec_throws,bs[dec_throws]),(pitch_l,bs[pitch_l]),(snd_l,bs[snd_l]),
           (wt,bs[wt]),(ifelse_turn,bs[ifelse_turn])])

    return bs

# ============================================================
#  PLANE blocks (메인 컨트롤러)
# ============================================================
def build_plane_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: rotation style + initial show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy",
        inputs={"X": num(PIVOT_X), "Y": num(PIVOT_Y)})
    pd0 = gen(); bs[pd0] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(rs,bs[rs]),(g0,bs[g0]),(pd0,bs[pd0]),(sz,bs[sz]),(sh,bs[sh])])

    # === when receive 던지기준비: 발사대 복귀 + 게이지 초기화 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["던지기준비", BR_AIM]})
    g1 = gen(); bs[g1] = mk("motion_gotoxy",
        inputs={"X": num(PIVOT_X), "Y": num(PIVOT_Y)})
    pd1 = gen(); bs[pd1] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh1 = gen(); bs[sh1] = mk("looks_show")
    sp = setvar(bs, "발사단계", V_PHASE, 0)
    sgv = setvar(bs, "게이지값", V_GVAL, 0)
    sgd = setvar(bs, "게이지방향", V_GDIR, 1)
    sst = setvar(bs, "게임상태", V_STATE, 0)
    chain([(h2,bs[h2]),(g1,bs[g1]),(pd1,bs[pd1]),(sh1,bs[sh1]),
           (sp,bs[sp]),(sgv,bs[sgv]),(sgd,bs[sgd]),(sst,bs[sst])])

    # === when flag clicked: 게이지 2단 상태머신 forever ===
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=300, y=20)

    # --- 단계 0: 각도 왕복 0~80 ---
    # 게이지값 += 게이지방향 * 2
    gdir_a = vrep("게이지방향", V_GDIR)
    step_a = op("operator_multiply", gdir_a, 2)
    bs[gdir_a]["parent"] = step_a
    chg_a = changevar(bs, "게이지값", V_GVAL, step_a)
    # if 게이지값 >= 80: 게이지값=80; 게이지방향=-1
    gval_hi = vrep("게이지값", V_GVAL)
    cond_a_hi = cmp_op("operator_gt", gval_hi, 79.999)  # >= via >79.999 not exact; use not<
    # use proper >= : (게이지값 > 80) OR (게이지값 = 80) is verbose; use not(<80)
    # Replace with operator_not(<80)
    del bs[cond_a_hi]; del bs[gval_hi]
    gval_hi = vrep("게이지값", V_GVAL)
    lt80 = cmp_op("operator_lt", gval_hi, 80)
    cond_a_hi = gen(); bs[cond_a_hi] = mk("operator_not", inputs={"OPERAND":[2,lt80]})
    bs[lt80]["parent"] = cond_a_hi
    seta_hi = setvar(bs, "게이지값", V_GVAL, 80)
    setd_hi = setvar(bs, "게이지방향", V_GDIR, -1)
    chain([(seta_hi,bs[seta_hi]),(setd_hi,bs[setd_hi])])
    if_a_hi = if_block(bs, cond_a_hi, seta_hi)
    # if 게이지값 <= 0: 게이지값=0; 게이지방향=1
    gval_lo = vrep("게이지값", V_GVAL)
    gt0 = cmp_op("operator_gt", gval_lo, 0)
    cond_a_lo = gen(); bs[cond_a_lo] = mk("operator_not", inputs={"OPERAND":[2,gt0]})
    bs[gt0]["parent"] = cond_a_lo
    seta_lo = setvar(bs, "게이지값", V_GVAL, 0)
    setd_lo = setvar(bs, "게이지방향", V_GDIR, 1)
    chain([(seta_lo,bs[seta_lo]),(setd_lo,bs[setd_lo])])
    if_a_lo = if_block(bs, cond_a_lo, seta_lo)
    # if space pressed: 발사각도=게이지값; 발사단계=1; 게이지값=0; 게이지방향=1; wait until not space
    sp_a = keypressed(bs, "space")
    gval_set = vrep("게이지값", V_GVAL)
    set_angle = setvar(bs, "발사각도", V_ANGLE, gval_set)
    set_ph1 = setvar(bs, "발사단계", V_PHASE, 1)
    rst_gv = setvar(bs, "게이지값", V_GVAL, 0)
    rst_gd = setvar(bs, "게이지방향", V_GDIR, 1)
    sp_a2 = keypressed(bs, "space")
    not_sp_a = gen(); bs[not_sp_a] = mk("operator_not", inputs={"OPERAND":[2,sp_a2]})
    bs[sp_a2]["parent"] = not_sp_a
    wait_rel_a = gen(); bs[wait_rel_a] = mk("control_wait_until",
        inputs={"CONDITION":[2,not_sp_a]})
    bs[not_sp_a]["parent"] = wait_rel_a
    chain([(set_angle,bs[set_angle]),(set_ph1,bs[set_ph1]),(rst_gv,bs[rst_gv]),
           (rst_gd,bs[rst_gd]),(wait_rel_a,bs[wait_rel_a])])
    if_a_fix = if_block(bs, sp_a, set_angle)
    # phase0 body chain
    chain([(chg_a,bs[chg_a]),(if_a_hi,bs[if_a_hi]),(if_a_lo,bs[if_a_lo]),(if_a_fix,bs[if_a_fix])])
    # if 발사단계 = 0 wrapper
    phase_v0 = vrep("발사단계", V_PHASE)
    cond_ph0 = cmp_op("operator_equals", phase_v0, 0)

    # --- 단계 1: 힘 왕복 0~100 ---
    gdir_b = vrep("게이지방향", V_GDIR)
    step_b = op("operator_multiply", gdir_b, 3)
    bs[gdir_b]["parent"] = step_b
    chg_b = changevar(bs, "게이지값", V_GVAL, step_b)
    # if 게이지값 >= 100
    gval_bhi = vrep("게이지값", V_GVAL)
    lt100 = cmp_op("operator_lt", gval_bhi, 100)
    cond_b_hi = gen(); bs[cond_b_hi] = mk("operator_not", inputs={"OPERAND":[2,lt100]})
    bs[lt100]["parent"] = cond_b_hi
    setb_hi = setvar(bs, "게이지값", V_GVAL, 100)
    setbd_hi = setvar(bs, "게이지방향", V_GDIR, -1)
    chain([(setb_hi,bs[setb_hi]),(setbd_hi,bs[setbd_hi])])
    if_b_hi = if_block(bs, cond_b_hi, setb_hi)
    # if 게이지값 <= 0
    gval_blo = vrep("게이지값", V_GVAL)
    gt0b = cmp_op("operator_gt", gval_blo, 0)
    cond_b_lo = gen(); bs[cond_b_lo] = mk("operator_not", inputs={"OPERAND":[2,gt0b]})
    bs[gt0b]["parent"] = cond_b_lo
    setb_lo = setvar(bs, "게이지값", V_GVAL, 0)
    setbd_lo = setvar(bs, "게이지방향", V_GDIR, 1)
    chain([(setb_lo,bs[setb_lo]),(setbd_lo,bs[setbd_lo])])
    if_b_lo = if_block(bs, cond_b_lo, setb_lo)
    # if space pressed: 발사힘=게이지값; dx/dy 계산; 발사단계=2; 게임상태=1; broadcast 발사; wait until not space
    sp_b = keypressed(bs, "space")
    gval_pw = vrep("게이지값", V_GVAL)
    set_power = setvar(bs, "발사힘", V_POWER, gval_pw)
    # dx = cos(발사각도) * (발사힘/100) * 12
    ang_for_cos = vrep("발사각도", V_ANGLE)
    cos_ang = mathop(bs, "cos", ang_for_cos)
    pw_for_dx = vrep("발사힘", V_POWER)
    pw_div_dx = op("operator_divide", pw_for_dx, 100)
    bs[pw_for_dx]["parent"] = pw_div_dx
    cos_times_pw = op("operator_multiply", cos_ang, pw_div_dx)
    dx_val = op("operator_multiply", cos_times_pw, 12)
    set_dx = setvar(bs, "dx", V_DX, dx_val)
    # dy = sin(발사각도) * (발사힘/100) * 12
    ang_for_sin = vrep("발사각도", V_ANGLE)
    sin_ang = mathop(bs, "sin", ang_for_sin)
    pw_for_dy = vrep("발사힘", V_POWER)
    pw_div_dy = op("operator_divide", pw_for_dy, 100)
    bs[pw_for_dy]["parent"] = pw_div_dy
    sin_times_pw = op("operator_multiply", sin_ang, pw_div_dy)
    dy_val = op("operator_multiply", sin_times_pw, 12)
    set_dy = setvar(bs, "dy", V_DY, dy_val)
    set_ph2 = setvar(bs, "발사단계", V_PHASE, 2)
    set_st1 = setvar(bs, "게임상태", V_STATE, 1)
    bfire = bcast(bs, "발사", BR_FIRE)
    sp_b2 = keypressed(bs, "space")
    not_sp_b = gen(); bs[not_sp_b] = mk("operator_not", inputs={"OPERAND":[2,sp_b2]})
    bs[sp_b2]["parent"] = not_sp_b
    wait_rel_b = gen(); bs[wait_rel_b] = mk("control_wait_until",
        inputs={"CONDITION":[2,not_sp_b]})
    bs[not_sp_b]["parent"] = wait_rel_b
    chain([(set_power,bs[set_power]),(set_dx,bs[set_dx]),(set_dy,bs[set_dy]),
           (set_ph2,bs[set_ph2]),(set_st1,bs[set_st1]),(bfire,bs[bfire]),
           (wait_rel_b,bs[wait_rel_b])])
    if_b_fix = if_block(bs, sp_b, set_power)
    # phase1 body chain
    chain([(chg_b,bs[chg_b]),(if_b_hi,bs[if_b_hi]),(if_b_lo,bs[if_b_lo]),(if_b_fix,bs[if_b_fix])])
    phase_v1 = vrep("발사단계", V_PHASE)
    cond_ph1 = cmp_op("operator_equals", phase_v1, 1)
    if_ph1 = if_block(bs, cond_ph1, chg_b)
    # phase0 if then phase1 if
    if_ph0 = gen(); bs[if_ph0] = mk("control_if",
        inputs={"CONDITION":[2,cond_ph0], "SUBSTACK":[2,chg_a]})
    bs[cond_ph0]["parent"] = if_ph0
    bs[chg_a]["parent"] = if_ph0
    chain([(if_ph0,bs[if_ph0]),(if_ph1,bs[if_ph1])])
    # if 게임상태 = 0 wrapper (only gauge while waiting)
    state_g = vrep("게임상태", V_STATE)
    cond_st0 = cmp_op("operator_equals", state_g, 0)
    if_st0 = if_block(bs, cond_st0, if_ph0)
    # wait 0.02
    wt_g = gen(); bs[wt_g] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(if_st0,bs[if_st0]),(wt_g,bs[wt_g])])
    forever_g = gen(); bs[forever_g] = mk("control_forever",
        inputs={"SUBSTACK":[2,if_st0]})
    bs[if_st0]["parent"] = forever_g
    chain([(h3,bs[h3]),(forever_g,bs[forever_g])])

    # === when receive 발사: 물리 비행 forever ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=600, y=20,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    pd_f = gen(); bs[pd_f] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})

    # forever body:
    # if 게임상태 != 1 → stop this script
    state_f = vrep("게임상태", V_STATE)
    cond_not1 = cmp_op("operator_equals", state_f, 1)
    not_cond1 = gen(); bs[not_cond1] = mk("operator_not", inputs={"OPERAND":[2,cond_not1]})
    bs[cond_not1]["parent"] = not_cond1
    stop_s = gen(); bs[stop_s] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    if_stop = if_block(bs, not_cond1, stop_s)

    # dy -= 0.25
    grav = changevar(bs, "dy", V_DY, -0.25)
    # dx += (바람 / 10)  -- 바람 변수/모니터는 -1.5~+1.5 그대로, 비행 누적 효과만 1/10
    wind_v = vrep("바람", V_WIND)
    wind_div = op("operator_divide", wind_v, 10)
    bs[wind_v]["parent"] = wind_div
    add_wind = changevar(bs, "dx", V_DX, wind_div)
    # if dx < 0.3: dx = 0.3
    dx_c = vrep("dx", V_DX)
    cond_dxlo = cmp_op("operator_lt", dx_c, 0.3)
    set_dxlo = setvar(bs, "dx", V_DX, 0.3)
    if_dxlo = if_block(bs, cond_dxlo, set_dxlo)

    # next_x = x + dx ; camera band
    xp_n = gen(); bs[xp_n] = mk("motion_xposition")
    dx_for_nx = vrep("dx", V_DX)
    next_x = op("operator_add", xp_n, dx_for_nx)
    bs[xp_n]["parent"] = next_x
    # condition: next_x > 40
    next_x2_xp = gen(); bs[next_x2_xp] = mk("motion_xposition")
    dx_for_nx2 = vrep("dx", V_DX)
    next_x2 = op("operator_add", next_x2_xp, dx_for_nx2)
    bs[next_x2_xp]["parent"] = next_x2
    cond_band = cmp_op("operator_gt", next_x2, BAND_R)
    # then: ekstra = next_x - 40 ; set x to 40 ; 스크롤량 += ekstra
    next_x3_xp = gen(); bs[next_x3_xp] = mk("motion_xposition")
    dx_for_nx3 = vrep("dx", V_DX)
    next_x3 = op("operator_add", next_x3_xp, dx_for_nx3)
    bs[next_x3_xp]["parent"] = next_x3
    ekstra = op("operator_subtract", next_x3, BAND_R)
    setx_band = gen(); bs[setx_band] = mk("motion_setx", inputs={"X": num(BAND_R)})
    add_scroll = changevar(bs, "스크롤량", V_SCROLL, ekstra)
    chain([(setx_band,bs[setx_band]),(add_scroll,bs[add_scroll])])
    # else: set x to next_x
    setx_norm = gen(); bs[setx_norm] = mk("motion_setx", inputs={"X": slot(next_x)})
    bs[next_x]["parent"] = setx_norm
    ifelse_band = ifelse_block(bs, cond_band, setx_band, setx_norm)

    # change y by dy
    dy_chy = vrep("dy", V_DY)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": slot(dy_chy)})
    bs[dy_chy]["parent"] = chy

    # point in direction (90 - atan(dy/dx))
    dy_a = vrep("dy", V_DY)
    dx_a = vrep("dx", V_DX)
    dyodx = op("operator_divide", dy_a, dx_a)
    atan_b = mathop(bs, "atan", dyodx)
    dir_b = op("operator_subtract", 90, atan_b)
    pd_fly = gen(); bs[pd_fly] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(dir_b)})
    bs[dir_b]["parent"] = pd_fly

    # 거리 = round((x - (-180) + 스크롤량)/4)
    xp_d = gen(); bs[xp_d] = mk("motion_xposition")
    x_plus = op("operator_subtract", xp_d, PIVOT_X)  # x - (-180) = x + 180
    bs[xp_d]["parent"] = x_plus
    scroll_d = vrep("스크롤량", V_SCROLL)
    x_plus_scroll = op("operator_add", x_plus, scroll_d)
    over4 = op("operator_divide", x_plus_scroll, 4)
    round_d = gen(); bs[round_d] = mk("operator_round", inputs={"NUM": slot(over4)})
    bs[over4]["parent"] = round_d
    set_distfly = setvar(bs, "거리", V_DIST, round_d)

    # if y <= -140: set y to -140; 게임상태=2; broadcast 착지; stop
    yp_l = gen(); bs[yp_l] = mk("motion_yposition")
    gt_g = cmp_op("operator_gt", yp_l, GROUND)
    bs[yp_l]["parent"] = gt_g
    cond_land = gen(); bs[cond_land] = mk("operator_not", inputs={"OPERAND":[2,gt_g]})
    bs[gt_g]["parent"] = cond_land
    sety_g = gen(); bs[sety_g] = mk("motion_sety", inputs={"Y": num(GROUND)})
    set_st2 = setvar(bs, "게임상태", V_STATE, 2)
    bland = bcast(bs, "착지", BR_LAND)
    stop_land = gen(); bs[stop_land] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    chain([(sety_g,bs[sety_g]),(set_st2,bs[set_st2]),(bland,bs[bland]),(stop_land,bs[stop_land])])
    if_land = if_block(bs, cond_land, sety_g)

    # wait 0.02
    wt_f = gen(); bs[wt_f] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(if_stop,bs[if_stop]),(grav,bs[grav]),(add_wind,bs[add_wind]),
           (if_dxlo,bs[if_dxlo]),(ifelse_band,bs[ifelse_band]),(chy,bs[chy]),
           (pd_fly,bs[pd_fly]),(set_distfly,bs[set_distfly]),(if_land,bs[if_land]),
           (wt_f,bs[wt_f])])
    forever_f = gen(); bs[forever_f] = mk("control_forever",
        inputs={"SUBSTACK":[2,if_stop]})
    bs[if_stop]["parent"] = forever_f
    chain([(h4,bs[h4]),(pd_f,bs[pd_f]),(forever_f,bs[forever_f])])

    return bs

# ============================================================
#  ANGLE NEEDLE blocks
# ============================================================
def build_needle_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["던지기준비", BR_AIM]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(PIVOT_X), "Y": num(PIVOT_Y)})
    sh = gen(); bs[sh] = mk("looks_show")

    # forever:
    #   if 발사단계=0: show; point dir(90-게이지값)
    #   else if 발사단계=1: show; point dir(90-발사각도)
    #   else: hide; stop this script
    # phase0
    ph0 = vrep("발사단계", V_PHASE)
    cond0 = cmp_op("operator_equals", ph0, 0)
    sh0 = gen(); bs[sh0] = mk("looks_show")
    gval_n = vrep("게이지값", V_GVAL)
    dir0 = op("operator_subtract", 90, gval_n)
    pd0 = gen(); bs[pd0] = mk("motion_pointindirection", inputs={"DIRECTION": slot(dir0)})
    bs[dir0]["parent"] = pd0
    chain([(sh0,bs[sh0]),(pd0,bs[pd0])])
    # phase1
    ph1 = vrep("발사단계", V_PHASE)
    cond1 = cmp_op("operator_equals", ph1, 1)
    sh1 = gen(); bs[sh1] = mk("looks_show")
    ang_n = vrep("발사각도", V_ANGLE)
    dir1 = op("operator_subtract", 90, ang_n)
    pd1 = gen(); bs[pd1] = mk("motion_pointindirection", inputs={"DIRECTION": slot(dir1)})
    bs[dir1]["parent"] = pd1
    chain([(sh1,bs[sh1]),(pd1,bs[pd1])])
    # else: hide + stop
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    stop_n = gen(); bs[stop_n] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    chain([(hi2,bs[hi2]),(stop_n,bs[stop_n])])
    # nested if/else: if ph0 {..} else { if ph1 {..} else { hide;stop } }
    inner = ifelse_block(bs, cond1, sh1, hi2)
    outer = ifelse_block(bs, cond0, sh0, inner)
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(outer,bs[outer]),(wt,bs[wt])])
    forever = gen(); bs[forever] = mk("control_forever", inputs={"SUBSTACK":[2,outer]})
    bs[outer]["parent"] = forever
    chain([(h2,bs[h2]),(g,bs[g]),(sh,bs[sh]),(forever,bs[forever])])

    return bs

# ============================================================
#  POWER BAR blocks
# ============================================================
def build_power_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["던지기준비", BR_AIM]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-150), "Y": num(-165)})

    # forever:
    #   if 발사단계=1: show; set size to (60+게이지값)  else: hide
    #   if 발사단계=2: stop this script
    ph1 = vrep("발사단계", V_PHASE)
    cond1 = cmp_op("operator_equals", ph1, 1)
    sh = gen(); bs[sh] = mk("looks_show")
    gval = vrep("게이지값", V_GVAL)
    size_val = op("operator_add", 60, gval)
    setsz = gen(); bs[setsz] = mk("looks_setsizeto", inputs={"SIZE": slot(size_val)})
    bs[size_val]["parent"] = setsz
    chain([(sh,bs[sh]),(setsz,bs[setsz])])
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    ifelse1 = ifelse_block(bs, cond1, sh, hi2)
    # if 발사단계=2: stop
    ph2 = vrep("발사단계", V_PHASE)
    cond2 = cmp_op("operator_equals", ph2, 2)
    stop_p = gen(); bs[stop_p] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    if2 = if_block(bs, cond2, stop_p)
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(ifelse1,bs[ifelse1]),(if2,bs[if2]),(wt,bs[wt])])
    forever = gen(); bs[forever] = mk("control_forever", inputs={"SUBSTACK":[2,ifelse1]})
    bs[ifelse1]["parent"] = forever
    chain([(h2,bs[h2]),(g,bs[g]),(forever,bs[forever])])

    return bs

# ============================================================
#  WIND ARROW blocks
# ============================================================
def build_wind_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(150)})
    chain([(h,bs[h]),(g,bs[g])])

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["던지기준비", BR_AIM]})
    sh = gen(); bs[sh] = mk("looks_show")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["left-right", None]})
    # if 바람 >= 0: point dir 90 else point dir -90
    wind_c = vrep("바람", V_WIND)
    lt0 = cmp_op("operator_lt", wind_c, 0)
    cond_ge0 = gen(); bs[cond_ge0] = mk("operator_not", inputs={"OPERAND":[2,lt0]})
    bs[lt0]["parent"] = cond_ge0
    pd_r = gen(); bs[pd_r] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    pd_l = gen(); bs[pd_l] = mk("motion_pointindirection", inputs={"DIRECTION": num(-90)})
    ifelse_dir = ifelse_block(bs, cond_ge0, pd_r, pd_l)
    # set size to (60 + abs(바람)*25)
    wind_a = vrep("바람", V_WIND)
    abs_w = mathop(bs, "abs", wind_a)
    abs_25 = op("operator_multiply", abs_w, 25)
    size_w = op("operator_add", 60, abs_25)
    setsz = gen(); bs[setsz] = mk("looks_setsizeto", inputs={"SIZE": slot(size_w)})
    bs[size_w]["parent"] = setsz
    chain([(h2,bs[h2]),(sh,bs[sh]),(rs,bs[rs]),(ifelse_dir,bs[ifelse_dir]),(setsz,bs[setsz])])

    return bs

# ============================================================
#  DISTANCE FLAG (markers) blocks — clone scroll
# ============================================================
V_MX = "lvMX01"   # 마커 초기 x (sprite-local)

def build_flag_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when receive 게임시작: spawn 12 once (스크롤량 resets each throw, no per-throw respawn → no clone leak) ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # set 마커초기x to -120 ; repeat 12: create clone; 마커초기x += 100
    set_mx0 = setvar(bs, "마커초기x", V_MX, -120)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone
    inc_mx = changevar(bs, "마커초기x", V_MX, 100)
    chain([(cclone,bs[cclone]),(inc_mx,bs[inc_mx])])
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(12), "SUBSTACK":[2,cclone]})
    bs[cclone]["parent"] = rep
    chain([(h2,bs[h2]),(set_mx0,bs[set_mx0]),(rep,bs[rep])])

    # === when I start as clone: set 내x, scroll ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=300, y=140)
    # store own initial x in a fresh local? We reuse global 마커초기x snapshot at clone time:
    # The clone keeps the current 마커초기x value (sprite-local copied per-clone in Scratch).
    # set x to 마커초기x ; y = -135 ; show
    mx_set = vrep("마커초기x", V_MX)
    setx_init = gen(); bs[setx_init] = mk("motion_setx", inputs={"X": slot(mx_set)})
    bs[mx_set]["parent"] = setx_init
    sety_init = gen(); bs[sety_init] = mk("motion_sety", inputs={"Y": num(-135)})
    sh = gen(); bs[sh] = mk("looks_show")

    # forever: set x to (마커초기x - 스크롤량) ; if x<-260 hide else show
    mx_f = vrep("마커초기x", V_MX)
    scroll_f = vrep("스크롤량", V_SCROLL)
    xpos = op("operator_subtract", mx_f, scroll_f)
    setx_f = gen(); bs[setx_f] = mk("motion_setx", inputs={"X": slot(xpos)})
    bs[xpos]["parent"] = setx_f
    xp = gen(); bs[xp] = mk("motion_xposition")
    cond_off = cmp_op("operator_lt", xp, -260)
    bs[xp]["parent"] = cond_off
    hi_off = gen(); bs[hi_off] = mk("looks_hide")
    sh_on = gen(); bs[sh_on] = mk("looks_show")
    ifelse_vis = ifelse_block(bs, cond_off, hi_off, sh_on)
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(setx_f,bs[setx_f]),(ifelse_vis,bs[ifelse_vis]),(wt,bs[wt])])
    forever = gen(); bs[forever] = mk("control_forever", inputs={"SUBSTACK":[2,setx_f]})
    bs[setx_f]["parent"] = forever
    chain([(ch,bs[ch]),(setx_init,bs[setx_init]),(sety_init,bs[sety_init]),
           (sh,bs[sh]),(forever,bs[forever])])

    # Clones spawn once on 게임시작; green flag clears all clones on restart (Scratch behavior),
    # so no per-throw respawn and no clone accumulation.

    return bs

# ============================================================
#  CLOUD blocks — parallax clones
# ============================================================
V_CX = "lvCX01"  # 구름 초기 x

def build_cloud_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(hi,bs[hi])])

    # === when receive 게임시작: spawn 3 clouds ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    set_cx0 = setvar(bs, "구름초기x", V_CX, -150)
    g_y = gen(); bs[g_y] = mk("motion_sety", inputs={"Y": num(110)})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION":["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1, cmenu]})
    bs[cmenu]["parent"] = cclone
    inc_cx = changevar(bs, "구름초기x", V_CX, 160)
    chain([(cclone,bs[cclone]),(inc_cx,bs[inc_cx])])
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(3), "SUBSTACK":[2,cclone]})
    bs[cclone]["parent"] = rep
    chain([(h2,bs[h2]),(set_cx0,bs[set_cx0]),(g_y,bs[g_y]),(rep,bs[rep])])

    # === when I start as clone: parallax scroll ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=300, y=140)
    mx_set = vrep("구름초기x", V_CX)
    setx_init = gen(); bs[setx_init] = mk("motion_setx", inputs={"X": slot(mx_set)})
    bs[mx_set]["parent"] = setx_init
    sh = gen(); bs[sh] = mk("looks_show")

    # forever: set x to (구름초기x - 스크롤량*0.4); if x<-260 set x to 260 (구름초기x reset)
    cx_f = vrep("구름초기x", V_CX)
    scroll_f = vrep("스크롤량", V_SCROLL)
    scroll04 = op("operator_multiply", scroll_f, 0.4)
    xpos = op("operator_subtract", cx_f, scroll04)
    setx_f = gen(); bs[setx_f] = mk("motion_setx", inputs={"X": slot(xpos)})
    bs[xpos]["parent"] = setx_f
    xp = gen(); bs[xp] = mk("motion_xposition")
    cond_off = cmp_op("operator_lt", xp, -260)
    bs[xp]["parent"] = cond_off
    # wrap: 구름초기x += 480 (loop back)
    wrap = changevar(bs, "구름초기x", V_CX, 480)
    if_wrap = if_block(bs, cond_off, wrap)
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(setx_f,bs[setx_f]),(if_wrap,bs[if_wrap]),(wt,bs[wt])])
    forever = gen(); bs[forever] = mk("control_forever", inputs={"SUBSTACK":[2,setx_f]})
    bs[setx_f]["parent"] = forever
    chain([(ch,bs[ch]),(setx_init,bs[setx_init]),(sh,bs[sh]),(forever,bs[forever])])

    return bs

# ============================================================
#  RESULT BANNER blocks
# ============================================================
def build_result_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(front,bs[front])])

    # === when receive 결과: costume result; show; win sound ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["결과", BR_RESULT]})
    g2 = gen(); bs[g2] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    cm = gen(); bs[cm] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, gen()]})
    menu_id = bs[cm]["inputs"]["COSTUME"][1]
    bs[menu_id] = mk("looks_costume", fields={"COSTUME":["result", None]},
                     shadow=True, parent=cm)
    front2 = gen(); bs[front2] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    sh = gen(); bs[sh] = mk("looks_show")
    pitch = gen(); bs[pitch] = mk("sound_seteffectto",
        inputs={"VALUE": num(200)}, fields={"EFFECT":["PITCH", None]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    chain([(h2,bs[h2]),(g2,bs[g2]),(cm,bs[cm]),(front2,bs[front2]),
           (sh,bs[sh]),(pitch,bs[pitch]),(snd,bs[snd])])

    # === when receive 신기록: costume newbest; show; wait1; hide ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=300, y=160,
        fields={"BROADCAST_OPTION": ["신기록", BR_NEWBEST]})
    g3 = gen(); bs[g3] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(60)})
    cm2 = gen(); bs[cm2] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, gen()]})
    menu_id2 = bs[cm2]["inputs"]["COSTUME"][1]
    bs[menu_id2] = mk("looks_costume", fields={"COSTUME":["newbest", None]},
                      shadow=True, parent=cm2)
    front3 = gen(); bs[front3] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    sh2 = gen(); bs[sh2] = mk("looks_show")
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(1)})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(h3,bs[h3]),(g3,bs[g3]),(cm2,bs[cm2]),(front3,bs[front3]),
           (sh2,bs[sh2]),(wt,bs[wt]),(hi2,bs[hi2])])

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
    plane_md5  = write_svg(PLANE_SVG)
    needle_md5 = write_svg(NEEDLE_SVG)
    power_md5  = write_svg(POWERBAR_SVG)
    wind_md5   = write_svg(WIND_SVG)
    flag_md5   = write_svg(FLAG_SVG)
    cloud_md5  = write_svg(CLOUD_SVG)
    result_md5 = write_svg(RESULT_SVG)
    newbest_md5= write_svg(NEWBEST_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f:
        f.write(pop_bytes)

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage_blocks  = build_stage_blocks()
    plane_blocks  = build_plane_blocks()
    needle_blocks = build_needle_blocks()
    power_blocks  = build_power_blocks()
    wind_blocks   = build_wind_blocks()
    flag_blocks   = build_flag_blocks()
    cloud_blocks  = build_cloud_blocks()
    result_blocks = build_result_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_DIST:   ["거리", 0],
            V_BEST:   ["베스트", 0],
            V_TOTAL:  ["합계", 0],
            V_THROWS: ["남은던지기", 3],
            V_STATE:  ["게임상태", 0],
            V_PHASE:  ["발사단계", 0],
            V_ANGLE:  ["발사각도", 0],
            V_POWER:  ["발사힘", 0],
            V_GDIR:   ["게이지방향", 1],
            V_GVAL:   ["게이지값", 0],
            V_DX:     ["dx", 0],
            V_DY:     ["dy", 0],
            V_WIND:   ["바람", 0],
            V_SCROLL: ["스크롤량", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작", BR_AIM: "던지기준비", BR_FIRE: "발사",
            BR_LAND: "착지", BR_RESULT: "결과", BR_NEWBEST: "신기록",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "하늘", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    plane = {
        "isStage": False, "name": "비행기",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": plane_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "plane", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": plane_md5, "md5ext": f"{plane_md5}.svg",
            "rotationCenterX": 24, "rotationCenterY": 14
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": True,
        "x": PIVOT_X, "y": PIVOT_Y, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    needle = {
        "isStage": False, "name": "각도바늘",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": needle_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "needle", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": needle_md5, "md5ext": f"{needle_md5}.svg",
            "rotationCenterX": 3, "rotationCenterY": 5
        }],
        "sounds": [], "volume": 100, "layerOrder": 5, "visible": False,
        "x": PIVOT_X, "y": PIVOT_Y, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    power = {
        "isStage": False, "name": "힘게이지",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": power_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "powerbar", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": power_md5, "md5ext": f"{power_md5}.svg",
            "rotationCenterX": 45, "rotationCenterY": 8
        }],
        "sounds": [], "volume": 100, "layerOrder": 4, "visible": False,
        "x": -150, "y": -165, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    wind = {
        "isStage": False, "name": "바람화살표",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": wind_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "wind", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": wind_md5, "md5ext": f"{wind_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 12
        }],
        "sounds": [], "volume": 100, "layerOrder": 7, "visible": True,
        "x": 0, "y": 150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "left-right"
    }

    flag = {
        "isStage": False, "name": "거리마커",
        "variables": {V_MX: ["마커초기x", 0]}, "lists": {}, "broadcasts": {},
        "blocks": flag_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "flag", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": flag_md5, "md5ext": f"{flag_md5}.svg",
            "rotationCenterX": 3, "rotationCenterY": 30
        }],
        "sounds": [], "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": -135, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    cloud = {
        "isStage": False, "name": "구름",
        "variables": {V_CX: ["구름초기x", 0]}, "lists": {}, "broadcasts": {},
        "blocks": cloud_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "cloud", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": cloud_md5, "md5ext": f"{cloud_md5}.svg",
            "rotationCenterX": 36, "rotationCenterY": 19
        }],
        "sounds": [], "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 110, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    result = {
        "isStage": False, "name": "결과배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": result_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "result", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": result_md5, "md5ext": f"{result_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 75},
            {"name": "newbest", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": newbest_md5, "md5ext": f"{newbest_md5}.svg",
             "rotationCenterX": 150, "rotationCenterY": 50},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_DIST, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "거리"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 1000, "isDiscrete": True},
        {"id": V_BEST, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "베스트"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 1000, "isDiscrete": True},
        {"id": V_TOTAL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "합계"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 3000, "isDiscrete": True},
        {"id": V_THROWS, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "남은던지기"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 3, "isDiscrete": True},
        {"id": V_WIND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "바람"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 320, "y": 5,
         "visible": True, "sliderMin": -1.5, "sliderMax": 1.5, "isDiscrete": False},
    ]

    project = {
        "targets": [stage, plane, needle, power, wind, flag, cloud, result],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "paper-plane-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # ---- self-checks ----
    all_block_sets = {
        "stage": stage_blocks, "plane": plane_blocks, "needle": needle_blocks,
        "power": power_blocks, "wind": wind_blocks, "flag": flag_blocks,
        "cloud": cloud_blocks, "result": result_blocks,
    }
    total = sum(len(b) for b in all_block_sets.values())

    # zip integrity
    assert zipfile.is_zipfile(OUTPUT), "not a valid zip"
    with zipfile.ZipFile(OUTPUT) as zf:
        bad = zf.testzip()
        assert bad is None, f"corrupt entry {bad}"
        with zf.open("project.json") as jf:
            loaded = json.load(jf)
    # referential integrity: every parent/next/input id exists within its target
    for tgt in loaded["targets"]:
        blocks = tgt["blocks"]
        ids = set(blocks.keys())
        for bid, b in blocks.items():
            if not isinstance(b, dict): continue
            if b.get("next") and b["next"] not in ids:
                raise AssertionError(f"{tgt['name']}:{bid} next->{b['next']} missing")
            if b.get("parent") and b["parent"] not in ids:
                raise AssertionError(f"{tgt['name']}:{bid} parent->{b['parent']} missing")
            for k, v in b.get("inputs", {}).items():
                # v like [type, ref, ...]; refs are block ids (strings starting with 'b')
                for item in v[1:]:
                    if isinstance(item, str) and item in blocks:
                        pass
                    elif isinstance(item, str) and item.startswith("b") and item not in ids:
                        raise AssertionError(f"{tgt['name']}:{bid} input {k}->{item} missing")

    print(f"[paper-plane] built {OUTPUT}")
    print(f"  targets: {len(loaded['targets'])}  (Stage+7 sprites)")
    for nm, b in all_block_sets.items():
        print(f"    {nm}: {len(b)}")
    print(f"  total blocks: {total}")
    print(f"  monitors: {len(monitors)}  broadcasts: 6  variables: 14")
    print("  zip integrity: OK  json: OK  block refs: OK")

if __name__ == "__main__":
    main()
