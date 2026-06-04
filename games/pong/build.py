#!/usr/bin/env python3
"""핑퐁 (PONG) — 위/아래 화살표로 좌 패들을 움직여 공을 받아치고 AI 와 점수 대결.

1972 아타리 PONG 클래식. 베이스: car-race(게임상태 broadcast + 깃발 재시작 +
결과 배너 패턴) + apple-catch(한 축 이동 + clamp). 클론 풀 없음 — 공/패들 모두
단일 인스턴스가 매 틱 forever 로 움직이며 벽·패들과 물리 반사한다.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "핑퐁.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: 짙은 남색 코트 + 가운데 점선 네트 + 위/아래 경계선 --------
def _net_dashes():
    # 세로 점선 네트: 무대 x=240(가운데), y 0..360 따라 흰 점선
    out = []
    y = 12
    while y < 348:
        out.append(f'<rect x="236" y="{y}" width="8" height="18" rx="3" fill="#FFFFFF" opacity="0.55"/>')
        y += 30
    return "\n  ".join(out)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <!-- court -->
  <rect x="0" y="0" width="480" height="360" fill="#0B1026"/>
  <rect x="0" y="0" width="480" height="360" fill="#13183A" opacity="0.5"/>
  <!-- 위/아래 경계선 (무대 y=±165 → 화면 y=15 / 345) -->
  <rect x="6" y="13" width="468" height="5" rx="2" fill="#FFFFFF" opacity="0.85"/>
  <rect x="6" y="342" width="468" height="5" rx="2" fill="#FFFFFF" opacity="0.85"/>
  <!-- 좌/우 득점선 살짝 표시 (무대 x=±235 → 화면 x=5 / 475) -->
  <rect x="3" y="18" width="3" height="324" fill="#3949AB" opacity="0.6"/>
  <rect x="474" y="18" width="3" height="324" fill="#3949AB" opacity="0.6"/>
  <!-- 가운데 점선 네트 -->
  {_net_dashes()}
  <!-- 코너 글로우 -->
  <circle cx="0" cy="0" r="80" fill="#1A237E" opacity="0.25"/>
  <circle cx="480" cy="360" r="80" fill="#1A237E" opacity="0.25"/>
</svg>"""

# -------- 좌 패들 (흰/하늘 둥근 세로 막대, 14x70) --------
PADDLE_L_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="70" viewBox="0 0 14 70">
  <rect x="2" y="3" width="11" height="65" rx="5" fill="#000000" opacity="0.3"/>
  <rect x="1" y="1" width="11" height="65" rx="5" fill="#E3F2FD" stroke="#42A5F5" stroke-width="1.5"/>
  <rect x="3" y="4" width="4" height="59" rx="2" fill="#FFFFFF" opacity="0.8"/>
</svg>"""

# -------- 우 패들 (흰/주황 둥근 세로 막대, 14x70) — AI 구분 색 --------
PADDLE_R_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="70" viewBox="0 0 14 70">
  <rect x="2" y="3" width="11" height="65" rx="5" fill="#000000" opacity="0.3"/>
  <rect x="1" y="1" width="11" height="65" rx="5" fill="#FFE0B2" stroke="#FB8C00" stroke-width="1.5"/>
  <rect x="3" y="4" width="4" height="59" rx="2" fill="#FFFFFF" opacity="0.8"/>
</svg>"""

# -------- ball (노란 원, 18x18) --------
BALL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">
  <circle cx="9" cy="9" r="8" fill="#000000" opacity="0.25"/>
  <circle cx="9" cy="8.5" r="7.5" fill="#FFEB3B" stroke="#FBC02D" stroke-width="1"/>
  <circle cx="6.5" cy="6" r="2.4" fill="#FFFFFF" opacity="0.85"/>
</svg>"""

# -------- 결과 배너 win --------
WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#0B1026" opacity="0.94"
        stroke="#43A047" stroke-width="4"/>
  <text x="180" y="74" text-anchor="middle"
        fill="#66BB6A" font-family="Arial, Helvetica, sans-serif"
        font-size="48" font-weight="bold">YOU WIN!</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">네가 이겼다!</text>
  <text x="180" y="140" text-anchor="middle"
        fill="#81D4FA" font-family="Arial, Helvetica, sans-serif"
        font-size="13">초록 깃발(▶) 다시 클릭으로 재시작</text>
</svg>"""

# -------- 결과 배너 lose --------
LOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#0B1026" opacity="0.94"
        stroke="#E53935" stroke-width="4"/>
  <text x="180" y="74" text-anchor="middle"
        fill="#EF5350" font-family="Arial, Helvetica, sans-serif"
        font-size="48" font-weight="bold">YOU LOSE</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">컴퓨터가 이겼다!</text>
  <text x="180" y="140" text-anchor="middle"
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
    return vrep, op, cmp_op, bool_op

# sensing_of (다른 sprite 의 속성 읽기) 헬퍼
def sensing_of(bs, prop, obj):
    menu = gen(); bs[menu] = mk("sensing_of_object_menu",
        fields={"OBJECT": [obj, None]}, shadow=True)
    sid = gen(); bs[sid] = mk("sensing_of",
        inputs={"OBJECT":[1, menu]}, fields={"PROPERTY":[prop, None]})
    bs[menu]["parent"] = sid
    return sid

# touching (스프라이트 충돌) 헬퍼
def touching(bs, name):
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": [name, None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1, tm]})
    bs[tm]["parent"] = tc
    return tc

# play sound 헬퍼
def play_sound(bs, name):
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":[name, None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    return snd

# broadcast 헬퍼
def broadcast(bs, name, bid):
    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, bid]}, shadow=True)
    bc = gen(); bs[bc] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm]})
    bs[bm]["parent"] = bc
    return bc

# ============================================================
#  IDs
# ============================================================
V_PSCORE  = "varPScore01"   # 내점수
V_ASCORE  = "varAScore02"   # 컴점수
V_STATE   = "varState03"    # 게임상태 1=플레이 0=종료
V_TARGET  = "varTarget04"   # 목표점수
V_BALLDX  = "varBallDX05"   # 공dx
V_BALLDY  = "varBallDY06"   # 공dy
V_BALLSPD = "varBallSpd07"  # 공속도
V_SERVE   = "varServe08"    # 서브방향
V_AISPEED = "varAISpeed09"  # AI속도
V_PADHALF = "varPadHalf10"  # 패들반높이
V_RESULT  = "varResult11"   # 결과 0/1/2
V_OFF     = "varOff12"      # 오프셋 (패들 반사 각 계산 임시)
V_AIDIFF  = "varAIdiff13"   # AI차 (AI 추적 계산 임시)

BR_START = "brStart01"   # 게임시작
BR_SERVE = "brServe02"   # 서브

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init vars + broadcast 게임시작 + 서브 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = [(h, bs[h])]
    def setv(name, vid, val):
        b = gen(); bs[b] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
        inits.append((b, bs[b]))
    setv("내점수", V_PSCORE, 0)
    setv("컴점수", V_ASCORE, 0)
    setv("게임상태", V_STATE, 1)
    setv("결과", V_RESULT, 0)
    setv("목표점수", V_TARGET, 5)
    setv("공속도", V_BALLSPD, 4.5)
    setv("AI속도", V_AISPEED, 4)
    setv("패들반높이", V_PADHALF, 35)
    setv("서브방향", V_SERVE, -1)

    bc_start = broadcast(bs, "게임시작", BR_START)
    inits.append((bc_start, bs[bc_start]))
    bc_serve = broadcast(bs, "서브", BR_SERVE)
    inits.append((bc_serve, bs[bc_serve]))
    chain(inits)

    # === when receive 게임시작: 승패 판정 watcher ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # repeat until (내점수 >= 목표 OR 컴점수 >= 목표)
    ps_v = vrep("내점수", V_PSCORE)
    tg_v1 = vrep("목표점수", V_TARGET)
    cond_p = cmp_op("operator_gt", ps_v, tg_v1)  # >= → > 와 = 의 OR 로
    ps_v2 = vrep("내점수", V_PSCORE)
    tg_v1b = vrep("목표점수", V_TARGET)
    cond_pe = cmp_op("operator_equals", ps_v2, tg_v1b)
    cond_pge = bool_op("operator_or", cond_p, cond_pe)

    as_v = vrep("컴점수", V_ASCORE)
    tg_v2 = vrep("목표점수", V_TARGET)
    cond_a = cmp_op("operator_gt", as_v, tg_v2)
    as_v2 = vrep("컴점수", V_ASCORE)
    tg_v2b = vrep("목표점수", V_TARGET)
    cond_ae = cmp_op("operator_equals", as_v2, tg_v2b)
    cond_age = bool_op("operator_or", cond_a, cond_ae)

    cond_done = bool_op("operator_or", cond_pge, cond_age)

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.05)})
    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_done], "SUBSTACK":[2,wt]})
    bs[cond_done]["parent"] = rep_until
    bs[wt]["parent"] = rep_until

    # if 내점수 >= 목표 → 결과=1 else 결과=2
    ps_v3 = vrep("내점수", V_PSCORE)
    tg_v3 = vrep("목표점수", V_TARGET)
    cond_pwin_gt = cmp_op("operator_gt", ps_v3, tg_v3)
    ps_v4 = vrep("내점수", V_PSCORE)
    tg_v3b = vrep("목표점수", V_TARGET)
    cond_pwin_eq = cmp_op("operator_equals", ps_v4, tg_v3b)
    cond_pwin = bool_op("operator_or", cond_pwin_gt, cond_pwin_eq)

    set_res1 = gen(); bs[set_res1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["결과", V_RESULT]})
    set_res2 = gen(); bs[set_res2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["결과", V_RESULT]})
    if_else = gen(); bs[if_else] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_pwin], "SUBSTACK":[2,set_res1],
                "SUBSTACK2":[2,set_res2]})
    bs[cond_pwin]["parent"] = if_else
    bs[set_res1]["parent"] = if_else
    bs[set_res2]["parent"] = if_else

    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})

    chain([(h2,bs[h2]),(rep_until,bs[rep_until]),(if_else,bs[if_else]),
           (set_state0,bs[set_state0])])

    return bs

# ============================================================
#  좌 패들 (플레이어) blocks
# ============================================================
def build_paddle_l_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: size/direction/show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: 상하 이동 + clamp 루프 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sx0 = gen(); bs[sx0] = mk("motion_setx", inputs={"X": num(-210)})
    sy0 = gen(); bs[sy0] = mk("motion_sety", inputs={"Y": num(0)})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # if key up → change y by 6
    ku = gen(); bs[ku] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["up arrow", None]}, shadow=True)
    sku = gen(); bs[sku] = mk("sensing_keypressed", inputs={"KEY_OPTION":[1, ku]})
    bs[ku]["parent"] = sku
    chy_up = gen(); bs[chy_up] = mk("motion_changeyby", inputs={"DY": num(6)})
    if_up = gen(); bs[if_up] = mk("control_if",
        inputs={"CONDITION":[2,sku], "SUBSTACK":[2,chy_up]})
    bs[sku]["parent"] = if_up
    bs[chy_up]["parent"] = if_up

    # if key down → change y by -6
    kd = gen(); bs[kd] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["down arrow", None]}, shadow=True)
    skd = gen(); bs[skd] = mk("sensing_keypressed", inputs={"KEY_OPTION":[1, kd]})
    bs[kd]["parent"] = skd
    chy_dn = gen(); bs[chy_dn] = mk("motion_changeyby", inputs={"DY": num(-6)})
    if_dn = gen(); bs[if_dn] = mk("control_if",
        inputs={"CONDITION":[2,skd], "SUBSTACK":[2,chy_dn]})
    bs[skd]["parent"] = if_dn
    bs[chy_dn]["parent"] = if_dn

    # if y > 130 → set y 130
    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    cond_hi = cmp_op("operator_gt", yp1, 130)
    bs[yp1]["parent"] = cond_hi
    sy_hi = gen(); bs[sy_hi] = mk("motion_sety", inputs={"Y": num(130)})
    if_hi = gen(); bs[if_hi] = mk("control_if",
        inputs={"CONDITION":[2,cond_hi], "SUBSTACK":[2,sy_hi]})
    bs[cond_hi]["parent"] = if_hi
    bs[sy_hi]["parent"] = if_hi

    # if y < -130 → set y -130
    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    cond_lo = cmp_op("operator_lt", yp2, -130)
    bs[yp2]["parent"] = cond_lo
    sy_lo = gen(); bs[sy_lo] = mk("motion_sety", inputs={"Y": num(-130)})
    if_lo = gen(); bs[if_lo] = mk("control_if",
        inputs={"CONDITION":[2,cond_lo], "SUBSTACK":[2,sy_lo]})
    bs[cond_lo]["parent"] = if_lo
    bs[sy_lo]["parent"] = if_lo

    # set x to -210 (고정)
    sx_fix = gen(); bs[sx_fix] = mk("motion_setx", inputs={"X": num(-210)})
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.016)})

    chain([(if_up,bs[if_up]),(if_dn,bs[if_dn]),(if_hi,bs[if_hi]),
           (if_lo,bs[if_lo]),(sx_fix,bs[sx_fix]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_up]})
    bs[cond_over]["parent"] = rep_until
    bs[if_up]["parent"] = rep_until

    chain([(h2,bs[h2]),(sx0,bs[sx0]),(sy0,bs[sy0]),(rep_until,bs[rep_until])])
    return bs

# ============================================================
#  우 패들 (AI) blocks
# ============================================================
def build_paddle_r_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: size/direction/show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: AI 추적 루프 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sx0 = gen(); bs[sx0] = mk("motion_setx", inputs={"X": num(210)})
    sy0 = gen(); bs[sy0] = mk("motion_sety", inputs={"Y": num(0)})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # AI차 = ([y position] of 공) - (y position)
    ball_y = sensing_of(bs, "y position", "공")
    my_y = gen(); bs[my_y] = mk("motion_yposition")
    diff = op("operator_subtract", ball_y, my_y)
    set_diff = gen(); bs[set_diff] = mk("data_setvariableto",
        inputs={"VALUE": slot(diff)}, fields={"VARIABLE": ["AI차", V_AIDIFF]})
    bs[diff]["parent"] = set_diff

    # if AI차 > AI속도 → change y by AI속도
    diff_v1 = vrep("AI차", V_AIDIFF)
    ai_v1 = vrep("AI속도", V_AISPEED)
    cond_gt = cmp_op("operator_gt", diff_v1, ai_v1)
    ai_v1b = vrep("AI속도", V_AISPEED)
    chy_up = gen(); bs[chy_up] = mk("motion_changeyby", inputs={"DY": slot(ai_v1b)})
    bs[ai_v1b]["parent"] = chy_up
    if_gt = gen(); bs[if_gt] = mk("control_if",
        inputs={"CONDITION":[2,cond_gt], "SUBSTACK":[2,chy_up]})
    bs[cond_gt]["parent"] = if_gt
    bs[chy_up]["parent"] = if_gt

    # if AI차 < (-1*AI속도) → change y by (-1*AI속도)
    diff_v2 = vrep("AI차", V_AIDIFF)
    ai_v2 = vrep("AI속도", V_AISPEED)
    neg_ai2 = op("operator_multiply", -1, ai_v2)
    cond_lt = cmp_op("operator_lt", diff_v2, neg_ai2)
    ai_v2b = vrep("AI속도", V_AISPEED)
    neg_ai2b = op("operator_multiply", -1, ai_v2b)
    chy_dn = gen(); bs[chy_dn] = mk("motion_changeyby", inputs={"DY": slot(neg_ai2b)})
    bs[neg_ai2b]["parent"] = chy_dn
    if_lt = gen(); bs[if_lt] = mk("control_if",
        inputs={"CONDITION":[2,cond_lt], "SUBSTACK":[2,chy_dn]})
    bs[cond_lt]["parent"] = if_lt
    bs[chy_dn]["parent"] = if_lt

    # if (AI차 <= AI속도) AND (AI차 >= -1*AI속도) → change y by AI차  (거의 다 따라옴)
    diff_v3 = vrep("AI차", V_AIDIFF)
    ai_v3 = vrep("AI속도", V_AISPEED)
    cond_le = cmp_op("operator_lt", diff_v3, ai_v3)   # < (근사: <=)
    diff_v3e = vrep("AI차", V_AIDIFF)
    ai_v3e = vrep("AI속도", V_AISPEED)
    cond_le_eq = cmp_op("operator_equals", diff_v3e, ai_v3e)
    cond_le_or = bool_op("operator_or", cond_le, cond_le_eq)

    diff_v4 = vrep("AI차", V_AIDIFF)
    ai_v4 = vrep("AI속도", V_AISPEED)
    neg_ai4 = op("operator_multiply", -1, ai_v4)
    cond_ge = cmp_op("operator_gt", diff_v4, neg_ai4)  # >
    diff_v4e = vrep("AI차", V_AIDIFF)
    ai_v4e = vrep("AI속도", V_AISPEED)
    neg_ai4e = op("operator_multiply", -1, ai_v4e)
    cond_ge_eq = cmp_op("operator_equals", diff_v4e, neg_ai4e)
    cond_ge_or = bool_op("operator_or", cond_ge, cond_ge_eq)

    cond_near = bool_op("operator_and", cond_le_or, cond_ge_or)
    diff_v5 = vrep("AI차", V_AIDIFF)
    chy_exact = gen(); bs[chy_exact] = mk("motion_changeyby", inputs={"DY": slot(diff_v5)})
    bs[diff_v5]["parent"] = chy_exact
    if_near = gen(); bs[if_near] = mk("control_if",
        inputs={"CONDITION":[2,cond_near], "SUBSTACK":[2,chy_exact]})
    bs[cond_near]["parent"] = if_near
    bs[chy_exact]["parent"] = if_near

    # clamp y 130 / -130
    yp1 = gen(); bs[yp1] = mk("motion_yposition")
    cond_hi = cmp_op("operator_gt", yp1, 130)
    bs[yp1]["parent"] = cond_hi
    sy_hi = gen(); bs[sy_hi] = mk("motion_sety", inputs={"Y": num(130)})
    if_hi = gen(); bs[if_hi] = mk("control_if",
        inputs={"CONDITION":[2,cond_hi], "SUBSTACK":[2,sy_hi]})
    bs[cond_hi]["parent"] = if_hi
    bs[sy_hi]["parent"] = if_hi

    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    cond_lo = cmp_op("operator_lt", yp2, -130)
    bs[yp2]["parent"] = cond_lo
    sy_lo = gen(); bs[sy_lo] = mk("motion_sety", inputs={"Y": num(-130)})
    if_lo = gen(); bs[if_lo] = mk("control_if",
        inputs={"CONDITION":[2,cond_lo], "SUBSTACK":[2,sy_lo]})
    bs[cond_lo]["parent"] = if_lo
    bs[sy_lo]["parent"] = if_lo

    sx_fix = gen(); bs[sx_fix] = mk("motion_setx", inputs={"X": num(210)})
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.016)})

    chain([(set_diff,bs[set_diff]),(if_gt,bs[if_gt]),(if_lt,bs[if_lt]),
           (if_near,bs[if_near]),(if_hi,bs[if_hi]),(if_lo,bs[if_lo]),
           (sx_fix,bs[sx_fix]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,set_diff]})
    bs[cond_over]["parent"] = rep_until
    bs[set_diff]["parent"] = rep_until

    chain([(h2,bs[h2]),(sx0,bs[sx0]),(sy0,bs[sy0]),(rep_until,bs[rep_until])])
    return bs

# ============================================================
#  공 blocks
# ============================================================
def build_ball_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: size/costume/show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    cm_menu = gen(); bs[cm_menu] = mk("looks_costume",
        fields={"COSTUME":["ball", None]}, shadow=True)
    cm = gen(); bs[cm] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, cm_menu]})
    bs[cm_menu]["parent"] = cm
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(sz,bs[sz]),(cm,bs[cm]),(sh,bs[sh])])

    # === when receive 서브: 가운데 복귀 + 잠깐 멈춤 후 출발 ===
    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=320, y=20,
        fields={"BROADCAST_OPTION": ["서브", BR_SERVE]})
    sx0 = gen(); bs[sx0] = mk("motion_setx", inputs={"X": num(0)})
    sy0 = gen(); bs[sy0] = mk("motion_sety", inputs={"Y": num(0)})
    set_spd = gen(); bs[set_spd] = mk("data_setvariableto",
        inputs={"VALUE": num(4.5)}, fields={"VARIABLE": ["공속도", V_BALLSPD]})
    # 공dx = 서브방향 * 4
    serve_v = vrep("서브방향", V_SERVE)
    mul_serve = op("operator_multiply", serve_v, 4)
    set_dx = gen(); bs[set_dx] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_serve)}, fields={"VARIABLE": ["공dx", V_BALLDX]})
    bs[mul_serve]["parent"] = set_dx
    # 공dy = pick random -2 to 2
    rnd = gen(); bs[rnd] = mk("operator_random",
        inputs={"FROM": num(-2), "TO": num(2)})
    set_dy = gen(); bs[set_dy] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd)}, fields={"VARIABLE": ["공dy", V_BALLDY]})
    bs[rnd]["parent"] = set_dy
    wt_serve = gen(); bs[wt_serve] = mk("control_wait", inputs={"DURATION": num(0.6)})
    chain([(hs,bs[hs]),(sx0,bs[sx0]),(sy0,bs[sy0]),(set_spd,bs[set_spd]),
           (set_dx,bs[set_dx]),(set_dy,bs[set_dy]),(wt_serve,bs[wt_serve])])

    # === when receive 게임시작: 물리 루프 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sh2 = gen(); bs[sh2] = mk("looks_show")

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # change x by 공dx ; change y by 공dy
    dx_v = vrep("공dx", V_BALLDX)
    chx = gen(); bs[chx] = mk("motion_changexby", inputs={"DX": slot(dx_v)})
    bs[dx_v]["parent"] = chx
    dy_v = vrep("공dy", V_BALLDY)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": slot(dy_v)})
    bs[dy_v]["parent"] = chy

    # --- (1) 위/아래 벽 반사 ---
    yp_a = gen(); bs[yp_a] = mk("motion_yposition")
    cond_top = cmp_op("operator_gt", yp_a, 165)
    bs[yp_a]["parent"] = cond_top
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cond_bot = cmp_op("operator_lt", yp_b, -165)
    bs[yp_b]["parent"] = cond_bot
    cond_wall = bool_op("operator_or", cond_top, cond_bot)

    # 공dy = 공dy * -1
    dy_v2 = vrep("공dy", V_BALLDY)
    neg_dy = op("operator_multiply", dy_v2, -1)
    set_dy2 = gen(); bs[set_dy2] = mk("data_setvariableto",
        inputs={"VALUE": slot(neg_dy)}, fields={"VARIABLE": ["공dy", V_BALLDY]})
    bs[neg_dy]["parent"] = set_dy2
    # if y > 165 → set y 165
    yp_c = gen(); bs[yp_c] = mk("motion_yposition")
    cond_top2 = cmp_op("operator_gt", yp_c, 165)
    bs[yp_c]["parent"] = cond_top2
    sy_top = gen(); bs[sy_top] = mk("motion_sety", inputs={"Y": num(165)})
    if_top = gen(); bs[if_top] = mk("control_if",
        inputs={"CONDITION":[2,cond_top2], "SUBSTACK":[2,sy_top]})
    bs[cond_top2]["parent"] = if_top
    bs[sy_top]["parent"] = if_top
    # if y < -165 → set y -165
    yp_d = gen(); bs[yp_d] = mk("motion_yposition")
    cond_bot2 = cmp_op("operator_lt", yp_d, -165)
    bs[yp_d]["parent"] = cond_bot2
    sy_bot = gen(); bs[sy_bot] = mk("motion_sety", inputs={"Y": num(-165)})
    if_bot = gen(); bs[if_bot] = mk("control_if",
        inputs={"CONDITION":[2,cond_bot2], "SUBSTACK":[2,sy_bot]})
    bs[cond_bot2]["parent"] = if_bot
    bs[sy_bot]["parent"] = if_bot
    bounce_snd = play_sound(bs, "bounce")
    chain([(set_dy2,bs[set_dy2]),(if_top,bs[if_top]),(if_bot,bs[if_bot]),
           (bounce_snd,bs[bounce_snd])])

    if_wall = gen(); bs[if_wall] = mk("control_if",
        inputs={"CONDITION":[2,cond_wall], "SUBSTACK":[2,set_dy2]})
    bs[cond_wall]["parent"] = if_wall
    bs[set_dy2]["parent"] = if_wall

    # --- (2) 좌 패들 반사 (touching 좌패들 AND 공dx < 0) ---
    tc_l = touching(bs, "좌패들")
    dx_v3 = vrep("공dx", V_BALLDX)
    cond_dxl = cmp_op("operator_lt", dx_v3, 0)
    cond_lhit = bool_op("operator_and", tc_l, cond_dxl)

    # 공속도 += 0.4
    inc_spd_l = gen(); bs[inc_spd_l] = mk("data_changevariableby",
        inputs={"VALUE": num(0.4)}, fields={"VARIABLE": ["공속도", V_BALLSPD]})
    # 오프셋 = (y position - [y position] of 좌패들) / 패들반높이
    my_y_l = gen(); bs[my_y_l] = mk("motion_yposition")
    pad_y_l = sensing_of(bs, "y position", "좌패들")
    diff_l = op("operator_subtract", my_y_l, pad_y_l)
    half_v_l = vrep("패들반높이", V_PADHALF)
    div_l = op("operator_divide", diff_l, half_v_l)
    set_off_l = gen(); bs[set_off_l] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_l)}, fields={"VARIABLE": ["오프셋", V_OFF]})
    bs[div_l]["parent"] = set_off_l
    # 공dx = 공속도 (양수 반전)
    spd_v_l = vrep("공속도", V_BALLSPD)
    set_dx_l = gen(); bs[set_dx_l] = mk("data_setvariableto",
        inputs={"VALUE": slot(spd_v_l)}, fields={"VARIABLE": ["공dx", V_BALLDX]})
    bs[spd_v_l]["parent"] = set_dx_l
    # 공dy = 오프셋 * 공속도
    off_v_l = vrep("오프셋", V_OFF)
    spd_v_l2 = vrep("공속도", V_BALLSPD)
    mul_dy_l = op("operator_multiply", off_v_l, spd_v_l2)
    set_dy_l = gen(); bs[set_dy_l] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_dy_l)}, fields={"VARIABLE": ["공dy", V_BALLDY]})
    bs[mul_dy_l]["parent"] = set_dy_l
    # set x to -200
    sx_l = gen(); bs[sx_l] = mk("motion_setx", inputs={"X": num(-200)})
    snd_l = play_sound(bs, "bounce")
    chain([(inc_spd_l,bs[inc_spd_l]),(set_off_l,bs[set_off_l]),(set_dx_l,bs[set_dx_l]),
           (set_dy_l,bs[set_dy_l]),(sx_l,bs[sx_l]),(snd_l,bs[snd_l])])
    if_lhit = gen(); bs[if_lhit] = mk("control_if",
        inputs={"CONDITION":[2,cond_lhit], "SUBSTACK":[2,inc_spd_l]})
    bs[cond_lhit]["parent"] = if_lhit
    bs[inc_spd_l]["parent"] = if_lhit

    # --- (3) 우 패들 반사 (touching 우패들 AND 공dx > 0) ---
    tc_r = touching(bs, "우패들")
    dx_v4 = vrep("공dx", V_BALLDX)
    cond_dxr = cmp_op("operator_gt", dx_v4, 0)
    cond_rhit = bool_op("operator_and", tc_r, cond_dxr)

    inc_spd_r = gen(); bs[inc_spd_r] = mk("data_changevariableby",
        inputs={"VALUE": num(0.4)}, fields={"VARIABLE": ["공속도", V_BALLSPD]})
    my_y_r = gen(); bs[my_y_r] = mk("motion_yposition")
    pad_y_r = sensing_of(bs, "y position", "우패들")
    diff_r = op("operator_subtract", my_y_r, pad_y_r)
    half_v_r = vrep("패들반높이", V_PADHALF)
    div_r = op("operator_divide", diff_r, half_v_r)
    set_off_r = gen(); bs[set_off_r] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_r)}, fields={"VARIABLE": ["오프셋", V_OFF]})
    bs[div_r]["parent"] = set_off_r
    # 공dx = -1 * 공속도 (음수 반전)
    spd_v_r = vrep("공속도", V_BALLSPD)
    neg_spd_r = op("operator_multiply", -1, spd_v_r)
    set_dx_r = gen(); bs[set_dx_r] = mk("data_setvariableto",
        inputs={"VALUE": slot(neg_spd_r)}, fields={"VARIABLE": ["공dx", V_BALLDX]})
    bs[neg_spd_r]["parent"] = set_dx_r
    off_v_r = vrep("오프셋", V_OFF)
    spd_v_r2 = vrep("공속도", V_BALLSPD)
    mul_dy_r = op("operator_multiply", off_v_r, spd_v_r2)
    set_dy_r = gen(); bs[set_dy_r] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_dy_r)}, fields={"VARIABLE": ["공dy", V_BALLDY]})
    bs[mul_dy_r]["parent"] = set_dy_r
    sx_r = gen(); bs[sx_r] = mk("motion_setx", inputs={"X": num(200)})
    snd_r = play_sound(bs, "bounce")
    chain([(inc_spd_r,bs[inc_spd_r]),(set_off_r,bs[set_off_r]),(set_dx_r,bs[set_dx_r]),
           (set_dy_r,bs[set_dy_r]),(sx_r,bs[sx_r]),(snd_r,bs[snd_r])])
    if_rhit = gen(); bs[if_rhit] = mk("control_if",
        inputs={"CONDITION":[2,cond_rhit], "SUBSTACK":[2,inc_spd_r]})
    bs[cond_rhit]["parent"] = if_rhit
    bs[inc_spd_r]["parent"] = if_rhit

    # --- (4) 득점: x < -235 → 컴점수 +1, 서브방향 1, broadcast 서브 ---
    xp_a = gen(); bs[xp_a] = mk("motion_xposition")
    cond_left = cmp_op("operator_lt", xp_a, -235)
    bs[xp_a]["parent"] = cond_left
    inc_ascore = gen(); bs[inc_ascore] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["컴점수", V_ASCORE]})
    set_serve_r = gen(); bs[set_serve_r] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["서브방향", V_SERVE]})
    snd_score_l = play_sound(bs, "score")
    bc_serve_l = broadcast(bs, "서브", BR_SERVE)
    chain([(inc_ascore,bs[inc_ascore]),(set_serve_r,bs[set_serve_r]),
           (snd_score_l,bs[snd_score_l]),(bc_serve_l,bs[bc_serve_l])])
    if_left = gen(); bs[if_left] = mk("control_if",
        inputs={"CONDITION":[2,cond_left], "SUBSTACK":[2,inc_ascore]})
    bs[cond_left]["parent"] = if_left
    bs[inc_ascore]["parent"] = if_left

    # --- x > 235 → 내점수 +1, 서브방향 -1, broadcast 서브 ---
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cond_right = cmp_op("operator_gt", xp_b, 235)
    bs[xp_b]["parent"] = cond_right
    inc_pscore = gen(); bs[inc_pscore] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["내점수", V_PSCORE]})
    set_serve_l = gen(); bs[set_serve_l] = mk("data_setvariableto",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["서브방향", V_SERVE]})
    snd_score_r = play_sound(bs, "score")
    bc_serve_r = broadcast(bs, "서브", BR_SERVE)
    chain([(inc_pscore,bs[inc_pscore]),(set_serve_l,bs[set_serve_l]),
           (snd_score_r,bs[snd_score_r]),(bc_serve_r,bs[bc_serve_r])])
    if_right = gen(); bs[if_right] = mk("control_if",
        inputs={"CONDITION":[2,cond_right], "SUBSTACK":[2,inc_pscore]})
    bs[cond_right]["parent"] = if_right
    bs[inc_pscore]["parent"] = if_right

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.016)})

    chain([(chx,bs[chx]),(chy,bs[chy]),(if_wall,bs[if_wall]),(if_lhit,bs[if_lhit]),
           (if_rhit,bs[if_rhit]),(if_left,bs[if_left]),(if_right,bs[if_right]),
           (wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,chx]})
    bs[cond_over]["parent"] = rep_until
    bs[chx]["parent"] = rep_until

    chain([(h2,bs[h2]),(sh2,bs[sh2]),(rep_until,bs[rep_until])])
    return bs

# ============================================================
#  결과 배너 blocks
# ============================================================
def build_banner_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})

    # wait until 게임상태 = 0
    state_v = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", state_v, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_zero]})
    bs[cond_zero]["parent"] = wait_over

    # if 결과 = 1 → costume win else costume lose
    res_v = vrep("결과", V_RESULT)
    cond_win = cmp_op("operator_equals", res_v, 1)
    win_menu = gen(); bs[win_menu] = mk("looks_costume",
        fields={"COSTUME":["win", None]}, shadow=True)
    cm_win = gen(); bs[cm_win] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, win_menu]})
    bs[win_menu]["parent"] = cm_win
    lose_menu = gen(); bs[lose_menu] = mk("looks_costume",
        fields={"COSTUME":["lose", None]}, shadow=True)
    cm_lose = gen(); bs[cm_lose] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, lose_menu]})
    bs[lose_menu]["parent"] = cm_lose
    if_else = gen(); bs[if_else] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_win], "SUBSTACK":[2,cm_win],
                "SUBSTACK2":[2,cm_lose]})
    bs[cond_win]["parent"] = if_else
    bs[cm_win]["parent"] = if_else
    bs[cm_lose]["parent"] = if_else

    show = gen(); bs[show] = mk("looks_show")

    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front]),
           (wait_over,bs[wait_over]),(if_else,bs[if_else]),(show,bs[show])])
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

    bg_md5  = write_svg(BG_SVG)
    pl_md5  = write_svg(PADDLE_L_SVG)
    pr_md5  = write_svg(PADDLE_R_SVG)
    bl_md5  = write_svg(BALL_SVG)
    win_md5 = write_svg(WIN_SVG)
    lose_md5= write_svg(LOSE_SVG)

    with open(f"{ASSETS}/bounce.wav", "rb") as f: bounce_bytes = f.read()
    bounce_md5 = md5_bytes(bounce_bytes)
    with open(f"{WORK}/{bounce_md5}.wav", "wb") as f: f.write(bounce_bytes)
    with open(f"{ASSETS}/score.wav", "rb") as f: score_bytes = f.read()
    score_md5 = md5_bytes(score_bytes)
    with open(f"{WORK}/{score_md5}.wav", "wb") as f: f.write(score_bytes)

    def bounce_sound():
        return {"name": "bounce", "assetId": bounce_md5, "dataFormat": "wav",
                "format": "", "rate": 11025, "sampleCount": 258,
                "md5ext": f"{bounce_md5}.wav"}
    def score_sound():
        return {"name": "score", "assetId": score_md5, "dataFormat": "wav",
                "format": "", "rate": 11025, "sampleCount": 258,
                "md5ext": f"{score_md5}.wav"}

    stage_blocks  = build_stage_blocks()
    pl_blocks     = build_paddle_l_blocks()
    pr_blocks     = build_paddle_r_blocks()
    ball_blocks   = build_ball_blocks()
    banner_blocks = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_PSCORE:  ["내점수", 0],
            V_ASCORE:  ["컴점수", 0],
            V_STATE:   ["게임상태", 1],
            V_TARGET:  ["목표점수", 5],
            V_BALLDX:  ["공dx", 4],
            V_BALLDY:  ["공dy", 2],
            V_BALLSPD: ["공속도", 4.5],
            V_SERVE:   ["서브방향", -1],
            V_AISPEED: ["AI속도", 4],
            V_PADHALF: ["패들반높이", 35],
            V_RESULT:  ["결과", 0],
            V_OFF:     ["오프셋", 0],
            V_AIDIFF:  ["AI차", 0],
        },
        "lists": {},
        "broadcasts": {BR_START: "게임시작", BR_SERVE: "서브"},
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "코트", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [bounce_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    paddle_l = {
        "isStage": False, "name": "좌패들",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pl_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "paddle_l", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pl_md5, "md5ext": f"{pl_md5}.svg",
            "rotationCenterX": 7, "rotationCenterY": 35
        }],
        "sounds": [bounce_sound()],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": -210, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    paddle_r = {
        "isStage": False, "name": "우패들",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pr_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "paddle_r", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pr_md5, "md5ext": f"{pr_md5}.svg",
            "rotationCenterX": 7, "rotationCenterY": 35
        }],
        "sounds": [bounce_sound()],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": 210, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ball = {
        "isStage": False, "name": "공",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ball_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "ball", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bl_md5, "md5ext": f"{bl_md5}.svg",
            "rotationCenterX": 9, "rotationCenterY": 9
        }],
        "sounds": [bounce_sound(), score_sound()],
        "volume": 100, "layerOrder": 3, "visible": True,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    banner = {
        "isStage": False, "name": "결과배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": banner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "win", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": win_md5, "md5ext": f"{win_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 85},
            {"name": "lose", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": lose_md5, "md5ext": f"{lose_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 85},
        ],
        "sounds": [bounce_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_PSCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "내점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_ASCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "컴점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 370, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, paddle_l, paddle_r, ball, banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "pong-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # validate
    with open(pj, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert zipfile.is_zipfile(OUTPUT)

    # block reference integrity check
    def check_refs(target):
        blocks = target["blocks"]
        ids = set(blocks.keys())
        for bid, b in blocks.items():
            if not isinstance(b, dict): continue
            for k in ("next", "parent"):
                v = b.get(k)
                if v is not None and v not in ids:
                    raise AssertionError(f"{target['name']} {bid}.{k} -> {v} 누락")
            for key, inp in b.get("inputs", {}).items():
                for item in inp[1:]:
                    if isinstance(item, str) and item not in ids:
                        raise AssertionError(f"{target['name']} {bid}.inputs.{key} -> {item} 누락")
            # variable field id 존재 확인 (stage 변수)
            for fk, fv in b.get("fields", {}).items():
                if fk == "VARIABLE":
                    vid = fv[1]
                    if vid not in stage["variables"]:
                        raise AssertionError(f"{target['name']} {bid} 변수 {vid} 미등록")
    for t in project["targets"]:
        check_refs(t)

    print(f"wrote {OUTPUT}")
    print(f"  stage:   {len(stage_blocks)} blocks")
    print(f"  좌패들:  {len(pl_blocks)} blocks")
    print(f"  우패들:  {len(pr_blocks)} blocks")
    print(f"  공:      {len(ball_blocks)} blocks")
    print(f"  결과배너:{len(banner_blocks)} blocks")
    total = (len(stage_blocks) + len(pl_blocks) + len(pr_blocks)
             + len(ball_blocks) + len(banner_blocks))
    print(f"  TOTAL:   {total} blocks")
    print(f"  targets: {len(project['targets'])}")
    print(f"  monitors:{len(monitors)}")
    print("  refs OK, zip OK, json OK")

if __name__ == "__main__":
    main()
