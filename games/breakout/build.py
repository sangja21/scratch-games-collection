#!/usr/bin/env python3
"""벽돌깨기 (BREAKOUT) — 좌/우 화살표로 하단 패들을 움직여 공을 받아치고
위쪽 8×4 벽돌 격자를 모두 깬다. 윗행일수록 고득점. 공을 못 받으면 목숨 -1,
목숨 3개를 다 쓰면 게임오버. 벽돌을 다 깨면 다음 라운드(공 빨라짐).

1976 아타리 Breakout 클래식. 베이스:
  - games/pong/build.py  (공 1개 매 틱 dx/dy 이동 + 벽/패들 반사 + 중심 오프셋 각도 + Stage 골격 + 결과 배너)
  - games/alien-invasion/build.py (중첩 루프 격자 클론 spawn + per-clone 좌표 복사 + 카운터 전멸 후 broadcast)
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "벽돌깨기.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: 짙은 남색 + 좌·우·위 3면 밝은 경계선(반사벽), 아래는 뚫림 --------
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect x="0" y="0" width="480" height="360" fill="#0B1026"/>
  <rect x="0" y="0" width="480" height="360" fill="#13183A" opacity="0.5"/>
  <!-- 위 벽 반사선 (무대 y=+170 → 화면 y=10) -->
  <rect x="6" y="8" width="468" height="6" rx="3" fill="#FFFFFF" opacity="0.85"/>
  <!-- 좌 벽 반사선 (무대 x=-232 → 화면 x=8) -->
  <rect x="6" y="8" width="6" height="320" rx="3" fill="#FFFFFF" opacity="0.85"/>
  <!-- 우 벽 반사선 (무대 x=+232 → 화면 x=472) -->
  <rect x="468" y="8" width="6" height="320" rx="3" fill="#FFFFFF" opacity="0.85"/>
  <!-- 아래쪽 추락 영역 표시(점선) -->
  <rect x="14" y="350" width="452" height="2" fill="#E53935" opacity="0.4"/>
  <!-- 코너 글로우 -->
  <circle cx="0" cy="0" r="80" fill="#1A237E" opacity="0.25"/>
  <circle cx="480" cy="0" r="80" fill="#1A237E" opacity="0.25"/>
</svg>"""

# -------- 패들 (밝은 하늘색 둥근 가로 막대, 70x16 → 반폭 35) --------
PADDLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="70" height="16" viewBox="0 0 70 16">
  <rect x="3" y="4" width="65" height="11" rx="5" fill="#000000" opacity="0.3"/>
  <rect x="1" y="1" width="68" height="11" rx="5" fill="#E1F5FE" stroke="#29B6F6" stroke-width="1.5"/>
  <rect x="4" y="3" width="62" height="4" rx="2" fill="#FFFFFF" opacity="0.85"/>
</svg>"""

# -------- ball (흰/노란 원, 14x14) --------
BALL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
  <circle cx="7" cy="7" r="6.5" fill="#000000" opacity="0.25"/>
  <circle cx="7" cy="6.5" r="6" fill="#FFF59D" stroke="#FBC02D" stroke-width="1"/>
  <circle cx="5" cy="4.5" r="1.8" fill="#FFFFFF" opacity="0.9"/>
</svg>"""

# -------- 벽돌 코스튬 4개 (44x18 둥근 사각, 행별 색) --------
def _brick_svg(fill, stroke):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="44" height="18" viewBox="0 0 44 18">
  <rect x="2" y="3" width="40" height="14" rx="4" fill="#000000" opacity="0.3"/>
  <rect x="1" y="1" width="42" height="14" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
  <rect x="4" y="3" width="36" height="4" rx="2" fill="#FFFFFF" opacity="0.35"/>
</svg>"""

BRICK_RED_SVG    = _brick_svg("#EF5350", "#C62828")  # row0
BRICK_ORANGE_SVG = _brick_svg("#FFA726", "#E65100")  # row1
BRICK_YELLOW_SVG = _brick_svg("#FFEE58", "#F9A825")  # row2
BRICK_GREEN_SVG  = _brick_svg("#66BB6A", "#2E7D32")  # row3

# -------- 결과 배너 GAME OVER --------
GAMEOVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14"
        fill="#0B1026" opacity="0.94"
        stroke="#E53935" stroke-width="4"/>
  <text x="180" y="74" text-anchor="middle"
        fill="#EF5350" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="18">목숨을 모두 잃었다!</text>
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
# 글로벌 (Stage)
V_SCORE  = "varScore01"    # 점수
V_BEST   = "varBest02"     # 최고기록
V_STATE  = "varState03"    # 게임상태 1=플레이 0=게임오버
V_LIVES  = "varLives04"    # 목숨
V_ROUND  = "varRound05"    # 라운드
V_BALLDX = "varBallDX06"   # 공dx
V_BALLDY = "varBallDY07"   # 공dy
V_BALLSPD= "varBallSpd08"  # 공속도
V_PADHALF= "varPadHalf09"  # 패들반폭
V_BRICKCNT="varBrickCnt10" # 벽돌수
V_OFF    = "varOff11"      # 오프셋
V_RESULT = "varResult12"   # 결과 0/1/2

# 벽돌 sprite-local
V_BX     = "varBX13"       # 자기X
V_BY     = "varBY14"       # 자기Y
V_BROW   = "varBRow15"     # 자기행

# broadcasts
BR_START  = "brStart01"     # 게임시작
BR_BRICKS = "brBricks02"    # 벽돌생성
BR_LAUNCH = "brLaunch03"    # 공발사
BR_NEXT   = "brNextRound04" # 다음라운드

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init vars + broadcast 게임시작/벽돌생성/공발사 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = [(h, bs[h])]
    def setv(name, vid, val):
        b = gen(); bs[b] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
        inits.append((b, bs[b]))
    setv("점수", V_SCORE, 0)
    setv("게임상태", V_STATE, 1)
    setv("목숨", V_LIVES, 3)
    setv("라운드", V_ROUND, 1)
    setv("공속도", V_BALLSPD, 5)
    setv("패들반폭", V_PADHALF, 35)
    setv("결과", V_RESULT, 0)
    setv("벽돌수", V_BRICKCNT, 0)

    bc_start = broadcast(bs, "게임시작", BR_START)
    inits.append((bc_start, bs[bc_start]))
    bc_bricks = broadcast(bs, "벽돌생성", BR_BRICKS)
    inits.append((bc_bricks, bs[bc_bricks]))
    bc_launch = broadcast(bs, "공발사", BR_LAUNCH)
    inits.append((bc_launch, bs[bc_launch]))
    chain(inits)

    # === when receive 다음라운드: 라운드+1 + 공속도+1 + wait + 벽돌생성 + 공발사 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["다음라운드", BR_NEXT]})
    inc_round = gen(); bs[inc_round] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
    inc_spd = gen(); bs[inc_spd] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["공속도", V_BALLSPD]})
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.3)})
    bc_bricks2 = broadcast(bs, "벽돌생성", BR_BRICKS)
    bc_launch2 = broadcast(bs, "공발사", BR_LAUNCH)
    chain([(h2,bs[h2]),(inc_round,bs[inc_round]),(inc_spd,bs[inc_spd]),
           (wt,bs[wt]),(bc_bricks2,bs[bc_bricks2]),(bc_launch2,bs[bc_launch2])])

    return bs

# ============================================================
#  패들 (플레이어) blocks
# ============================================================
def build_paddle_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: size/direction/show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(sz,bs[sz]),(pdir,bs[pdir]),(sh,bs[sh])])

    # === when receive 게임시작: 좌우 이동 + clamp 루프 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sy0 = gen(); bs[sy0] = mk("motion_sety", inputs={"Y": num(-150)})
    sx0 = gen(); bs[sx0] = mk("motion_setx", inputs={"X": num(0)})

    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # if key right → change x by 7
    kr = gen(); bs[kr] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["right arrow", None]}, shadow=True)
    skr = gen(); bs[skr] = mk("sensing_keypressed", inputs={"KEY_OPTION":[1, kr]})
    bs[kr]["parent"] = skr
    chx_r = gen(); bs[chx_r] = mk("motion_changexby", inputs={"DX": num(7)})
    if_r = gen(); bs[if_r] = mk("control_if",
        inputs={"CONDITION":[2,skr], "SUBSTACK":[2,chx_r]})
    bs[skr]["parent"] = if_r
    bs[chx_r]["parent"] = if_r

    # if key left → change x by -7
    kl = gen(); bs[kl] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["left arrow", None]}, shadow=True)
    skl = gen(); bs[skl] = mk("sensing_keypressed", inputs={"KEY_OPTION":[1, kl]})
    bs[kl]["parent"] = skl
    chx_l = gen(); bs[chx_l] = mk("motion_changexby", inputs={"DX": num(-7)})
    if_l = gen(); bs[if_l] = mk("control_if",
        inputs={"CONDITION":[2,skl], "SUBSTACK":[2,chx_l]})
    bs[skl]["parent"] = if_l
    bs[chx_l]["parent"] = if_l

    # if x > 200 → set x 200
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    cond_hi = cmp_op("operator_gt", xp1, 200)
    bs[xp1]["parent"] = cond_hi
    sx_hi = gen(); bs[sx_hi] = mk("motion_setx", inputs={"X": num(200)})
    if_hi = gen(); bs[if_hi] = mk("control_if",
        inputs={"CONDITION":[2,cond_hi], "SUBSTACK":[2,sx_hi]})
    bs[cond_hi]["parent"] = if_hi
    bs[sx_hi]["parent"] = if_hi

    # if x < -200 → set x -200
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    cond_lo = cmp_op("operator_lt", xp2, -200)
    bs[xp2]["parent"] = cond_lo
    sx_lo = gen(); bs[sx_lo] = mk("motion_setx", inputs={"X": num(-200)})
    if_lo = gen(); bs[if_lo] = mk("control_if",
        inputs={"CONDITION":[2,cond_lo], "SUBSTACK":[2,sx_lo]})
    bs[cond_lo]["parent"] = if_lo
    bs[sx_lo]["parent"] = if_lo

    # set y to -150 (고정)
    sy_fix = gen(); bs[sy_fix] = mk("motion_sety", inputs={"Y": num(-150)})
    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.016)})

    chain([(if_r,bs[if_r]),(if_l,bs[if_l]),(if_hi,bs[if_hi]),
           (if_lo,bs[if_lo]),(sy_fix,bs[sy_fix]),(wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_r]})
    bs[cond_over]["parent"] = rep_until
    bs[if_r]["parent"] = rep_until

    chain([(h2,bs[h2]),(sy0,bs[sy0]),(sx0,bs[sx0]),(rep_until,bs[rep_until])])
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

    # === when receive 공발사: 패들 위 중앙으로 + 잠깐 멈춤 후 위로 출발 ===
    hl = gen(); bs[hl] = mk("event_whenbroadcastreceived", top=True, x=320, y=20,
        fields={"BROADCAST_OPTION": ["공발사", BR_LAUNCH]})
    # set x to [x position] of 패들
    pad_x = sensing_of(bs, "x position", "패들")
    sx0 = gen(); bs[sx0] = mk("motion_setx", inputs={"X": slot(pad_x)})
    bs[pad_x]["parent"] = sx0
    sy0 = gen(); bs[sy0] = mk("motion_sety", inputs={"Y": num(-135)})
    # 공dx = pick random -2 to 2
    rnd = gen(); bs[rnd] = mk("operator_random",
        inputs={"FROM": num(-2), "TO": num(2)})
    set_dx = gen(); bs[set_dx] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd)}, fields={"VARIABLE": ["공dx", V_BALLDX]})
    bs[rnd]["parent"] = set_dx
    # 공dy = 공속도 (위로)
    spd_v0 = vrep("공속도", V_BALLSPD)
    set_dy = gen(); bs[set_dy] = mk("data_setvariableto",
        inputs={"VALUE": slot(spd_v0)}, fields={"VARIABLE": ["공dy", V_BALLDY]})
    bs[spd_v0]["parent"] = set_dy
    wt_launch = gen(); bs[wt_launch] = mk("control_wait", inputs={"DURATION": num(0.6)})
    chain([(hl,bs[hl]),(sx0,bs[sx0]),(sy0,bs[sy0]),(set_dx,bs[set_dx]),
           (set_dy,bs[set_dy]),(wt_launch,bs[wt_launch])])

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

    # --- (1) 좌/우 벽 반사: (x>232 OR x<-232) → 공dx *= -1, x clamp ---
    xp_a = gen(); bs[xp_a] = mk("motion_xposition")
    cond_xr = cmp_op("operator_gt", xp_a, 232)
    bs[xp_a]["parent"] = cond_xr
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cond_xl = cmp_op("operator_lt", xp_b, -232)
    bs[xp_b]["parent"] = cond_xl
    cond_side = bool_op("operator_or", cond_xr, cond_xl)

    dx_v2 = vrep("공dx", V_BALLDX)
    neg_dx = op("operator_multiply", dx_v2, -1)
    set_dx2 = gen(); bs[set_dx2] = mk("data_setvariableto",
        inputs={"VALUE": slot(neg_dx)}, fields={"VARIABLE": ["공dx", V_BALLDX]})
    bs[neg_dx]["parent"] = set_dx2
    # if x > 232 → set x 232
    xp_c = gen(); bs[xp_c] = mk("motion_xposition")
    cond_xr2 = cmp_op("operator_gt", xp_c, 232)
    bs[xp_c]["parent"] = cond_xr2
    sx_r = gen(); bs[sx_r] = mk("motion_setx", inputs={"X": num(232)})
    if_xr = gen(); bs[if_xr] = mk("control_if",
        inputs={"CONDITION":[2,cond_xr2], "SUBSTACK":[2,sx_r]})
    bs[cond_xr2]["parent"] = if_xr
    bs[sx_r]["parent"] = if_xr
    # if x < -232 → set x -232
    xp_d = gen(); bs[xp_d] = mk("motion_xposition")
    cond_xl2 = cmp_op("operator_lt", xp_d, -232)
    bs[xp_d]["parent"] = cond_xl2
    sx_lft = gen(); bs[sx_lft] = mk("motion_setx", inputs={"X": num(-232)})
    if_xl = gen(); bs[if_xl] = mk("control_if",
        inputs={"CONDITION":[2,cond_xl2], "SUBSTACK":[2,sx_lft]})
    bs[cond_xl2]["parent"] = if_xl
    bs[sx_lft]["parent"] = if_xl
    snd_side = play_sound(bs, "bounce")
    chain([(set_dx2,bs[set_dx2]),(if_xr,bs[if_xr]),(if_xl,bs[if_xl]),(snd_side,bs[snd_side])])

    if_side = gen(); bs[if_side] = mk("control_if",
        inputs={"CONDITION":[2,cond_side], "SUBSTACK":[2,set_dx2]})
    bs[cond_side]["parent"] = if_side
    bs[set_dx2]["parent"] = if_side

    # --- (2) 위 벽 반사: y>170 → 공dy = -1*abs(공dy), set y 170 ---
    yp_a = gen(); bs[yp_a] = mk("motion_yposition")
    cond_top = cmp_op("operator_gt", yp_a, 170)
    bs[yp_a]["parent"] = cond_top

    dy_v2 = vrep("공dy", V_BALLDY)
    abs_dy = gen(); bs[abs_dy] = mk("operator_mathop",
        inputs={"NUM": slot(dy_v2)}, fields={"OPERATOR":["abs", None]})
    bs[dy_v2]["parent"] = abs_dy
    neg_abs = op("operator_multiply", -1, abs_dy)
    set_dy_top = gen(); bs[set_dy_top] = mk("data_setvariableto",
        inputs={"VALUE": slot(neg_abs)}, fields={"VARIABLE": ["공dy", V_BALLDY]})
    bs[neg_abs]["parent"] = set_dy_top
    sy_top = gen(); bs[sy_top] = mk("motion_sety", inputs={"Y": num(170)})
    snd_top = play_sound(bs, "bounce")
    chain([(set_dy_top,bs[set_dy_top]),(sy_top,bs[sy_top]),(snd_top,bs[snd_top])])

    if_top = gen(); bs[if_top] = mk("control_if",
        inputs={"CONDITION":[2,cond_top], "SUBSTACK":[2,set_dy_top]})
    bs[cond_top]["parent"] = if_top
    bs[set_dy_top]["parent"] = if_top

    # --- (3) 패들 반사: (touching 패들 AND 공dy<0) → 위로 + 오프셋 X각 + ramp ---
    tc_p = touching(bs, "패들")
    dy_v3 = vrep("공dy", V_BALLDY)
    cond_dyneg = cmp_op("operator_lt", dy_v3, 0)
    cond_phit = bool_op("operator_and", tc_p, cond_dyneg)

    # 공속도 += 0.3
    inc_spd = gen(); bs[inc_spd] = mk("data_changevariableby",
        inputs={"VALUE": num(0.3)}, fields={"VARIABLE": ["공속도", V_BALLSPD]})
    # 오프셋 = (x position - [x position] of 패들) / 패들반폭
    my_x = gen(); bs[my_x] = mk("motion_xposition")
    pad_x2 = sensing_of(bs, "x position", "패들")
    diff_x = op("operator_subtract", my_x, pad_x2)
    half_v = vrep("패들반폭", V_PADHALF)
    div_off = op("operator_divide", diff_x, half_v)
    set_off = gen(); bs[set_off] = mk("data_setvariableto",
        inputs={"VALUE": slot(div_off)}, fields={"VARIABLE": ["오프셋", V_OFF]})
    bs[div_off]["parent"] = set_off
    # 공dx = 오프셋 * 공속도
    off_v = vrep("오프셋", V_OFF)
    spd_v = vrep("공속도", V_BALLSPD)
    mul_dx = op("operator_multiply", off_v, spd_v)
    set_dx_p = gen(); bs[set_dx_p] = mk("data_setvariableto",
        inputs={"VALUE": slot(mul_dx)}, fields={"VARIABLE": ["공dx", V_BALLDX]})
    bs[mul_dx]["parent"] = set_dx_p
    # 공dy = 공속도 (위로)
    spd_v2 = vrep("공속도", V_BALLSPD)
    set_dy_p = gen(); bs[set_dy_p] = mk("data_setvariableto",
        inputs={"VALUE": slot(spd_v2)}, fields={"VARIABLE": ["공dy", V_BALLDY]})
    bs[spd_v2]["parent"] = set_dy_p
    # set y to -135
    sy_p = gen(); bs[sy_p] = mk("motion_sety", inputs={"Y": num(-135)})
    snd_p = play_sound(bs, "bounce")
    chain([(inc_spd,bs[inc_spd]),(set_off,bs[set_off]),(set_dx_p,bs[set_dx_p]),
           (set_dy_p,bs[set_dy_p]),(sy_p,bs[sy_p]),(snd_p,bs[snd_p])])
    if_phit = gen(); bs[if_phit] = mk("control_if",
        inputs={"CONDITION":[2,cond_phit], "SUBSTACK":[2,inc_spd]})
    bs[cond_phit]["parent"] = if_phit
    bs[inc_spd]["parent"] = if_phit

    # --- (4) 벽돌 반사: touching 벽돌 → 공dy *= -1 ---
    tc_b = touching(bs, "벽돌")
    dy_v4 = vrep("공dy", V_BALLDY)
    neg_dy_b = op("operator_multiply", dy_v4, -1)
    set_dy_b = gen(); bs[set_dy_b] = mk("data_setvariableto",
        inputs={"VALUE": slot(neg_dy_b)}, fields={"VARIABLE": ["공dy", V_BALLDY]})
    bs[neg_dy_b]["parent"] = set_dy_b
    snd_b = play_sound(bs, "brick")
    chain([(set_dy_b,bs[set_dy_b]),(snd_b,bs[snd_b])])
    if_brick = gen(); bs[if_brick] = mk("control_if",
        inputs={"CONDITION":[2,tc_b], "SUBSTACK":[2,set_dy_b]})
    bs[tc_b]["parent"] = if_brick
    bs[set_dy_b]["parent"] = if_brick

    # --- (5) 바닥 추락: y<-175 → 목숨-1; 목숨<=0 → 결과1·게임상태0; else broadcast 공발사 ---
    yp_e = gen(); bs[yp_e] = mk("motion_yposition")
    cond_fall = cmp_op("operator_lt", yp_e, -175)
    bs[yp_e]["parent"] = cond_fall

    dec_life = gen(); bs[dec_life] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["목숨", V_LIVES]})
    snd_lose = play_sound(bs, "lose")

    # if 목숨<=0 → 결과=1, 게임상태=0 ; else broadcast 공발사
    lives_v = vrep("목숨", V_LIVES)
    cond_le0_lt = cmp_op("operator_lt", lives_v, 1)  # 목숨 < 1 == 목숨 <= 0 (정수)
    set_res1 = gen(); bs[set_res1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["결과", V_RESULT]})
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    chain([(set_res1,bs[set_res1]),(set_state0,bs[set_state0])])
    bc_launch = broadcast(bs, "공발사", BR_LAUNCH)
    if_dead = gen(); bs[if_dead] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_le0_lt], "SUBSTACK":[2,set_res1],
                "SUBSTACK2":[2,bc_launch]})
    bs[cond_le0_lt]["parent"] = if_dead
    bs[set_res1]["parent"] = if_dead
    bs[bc_launch]["parent"] = if_dead

    chain([(dec_life,bs[dec_life]),(snd_lose,bs[snd_lose]),(if_dead,bs[if_dead])])
    if_fall = gen(); bs[if_fall] = mk("control_if",
        inputs={"CONDITION":[2,cond_fall], "SUBSTACK":[2,dec_life]})
    bs[cond_fall]["parent"] = if_fall
    bs[dec_life]["parent"] = if_fall

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.016)})

    chain([(chx,bs[chx]),(chy,bs[chy]),(if_side,bs[if_side]),(if_top,bs[if_top]),
           (if_phit,bs[if_phit]),(if_brick,bs[if_brick]),(if_fall,bs[if_fall]),
           (wt,bs[wt])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,chx]})
    bs[cond_over]["parent"] = rep_until
    bs[chx]["parent"] = rep_until

    chain([(h2,bs[h2]),(sh2,bs[sh2]),(rep_until,bs[rep_until])])
    return bs

# ============================================================
#  벽돌 blocks (8×4 클론 격자)
# ============================================================
def build_brick_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide original ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h,bs[h]),(hi,bs[hi]),(sz,bs[sz])])

    # === on 벽돌생성: hide + 벽돌수=0 + 펼친 32 spawn 체인 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["벽돌생성", BR_BRICKS]})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    set_cnt0 = gen(); bs[set_cnt0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["벽돌수", V_BRICKCNT]})

    spawn_chain = []
    for rowIndex in range(4):       # 행 0..3
        for colIndex in range(8):   # 열 0..7
            bx = colIndex * 50 - 175
            by = 140 - rowIndex * 25
            sx = gen(); bs[sx] = mk("data_setvariableto",
                inputs={"VALUE": num(bx)}, fields={"VARIABLE": ["자기X", V_BX]})
            sy = gen(); bs[sy] = mk("data_setvariableto",
                inputs={"VALUE": num(by)}, fields={"VARIABLE": ["자기Y", V_BY]})
            srow = gen(); bs[srow] = mk("data_setvariableto",
                inputs={"VALUE": num(rowIndex)}, fields={"VARIABLE": ["자기행", V_BROW]})
            cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
                fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
            cclone = gen(); bs[cclone] = mk("control_create_clone_of",
                inputs={"CLONE_OPTION":[1, cmenu]})
            bs[cmenu]["parent"] = cclone
            inc_cnt = gen(); bs[inc_cnt] = mk("data_changevariableby",
                inputs={"VALUE": num(1)}, fields={"VARIABLE": ["벽돌수", V_BRICKCNT]})
            wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.01)})
            spawn_chain.extend([(sx,bs[sx]),(sy,bs[sy]),(srow,bs[srow]),
                                (cclone,bs[cclone]),(inc_cnt,bs[inc_cnt]),(wt,bs[wt])])

    chain([(h2,bs[h2]),(hi2,bs[hi2]),(set_cnt0,bs[set_cnt0])] + spawn_chain)

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)
    # goto (자기X, 자기Y)
    bx_v = vrep("자기X", V_BX); by_v = vrep("자기Y", V_BY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g
    # switch costume to (자기행 + 1)
    row_v = vrep("자기행", V_BROW)
    cos_idx = op("operator_add", row_v, 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, cos_idx]})
    bs[cos_idx]["parent"] = sw
    show = gen(); bs[show] = mk("looks_show")

    # repeat until 게임상태=0:
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)

    # if touching 공: 점수+행점수, best, 벽돌수-1, sound, if 벽돌수<=0 broadcast 다음라운드, delete
    tc = touching(bs, "공")

    # 행별 점수 4 if 분기
    def row_score_if(row, pts):
        rv = vrep("자기행", V_BROW)
        cond = cmp_op("operator_equals", rv, row)
        inc = gen(); bs[inc] = mk("data_changevariableby",
            inputs={"VALUE": num(pts)}, fields={"VARIABLE": ["점수", V_SCORE]})
        ifb = gen(); bs[ifb] = mk("control_if",
            inputs={"CONDITION":[2,cond], "SUBSTACK":[2,inc]})
        bs[cond]["parent"] = ifb
        bs[inc]["parent"] = ifb
        return ifb
    if0 = row_score_if(0, 50)
    if1 = row_score_if(1, 30)
    if2 = row_score_if(2, 20)
    if3 = row_score_if(3, 10)

    # if 점수 > 최고기록 → 최고기록 = 점수
    sc_v = vrep("점수", V_SCORE)
    best_v = vrep("최고기록", V_BEST)
    cond_best = cmp_op("operator_gt", sc_v, best_v)
    sc_v2 = vrep("점수", V_SCORE)
    set_best = gen(); bs[set_best] = mk("data_setvariableto",
        inputs={"VALUE": slot(sc_v2)}, fields={"VARIABLE": ["최고기록", V_BEST]})
    bs[sc_v2]["parent"] = set_best
    if_best = gen(); bs[if_best] = mk("control_if",
        inputs={"CONDITION":[2,cond_best], "SUBSTACK":[2,set_best]})
    bs[cond_best]["parent"] = if_best
    bs[set_best]["parent"] = if_best

    # 벽돌수 -1
    dec_cnt = gen(); bs[dec_cnt] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["벽돌수", V_BRICKCNT]})
    snd_brick = play_sound(bs, "brick")

    # if 벽돌수 <= 0 → broadcast 다음라운드
    cnt_v = vrep("벽돌수", V_BRICKCNT)
    cond_clr = cmp_op("operator_lt", cnt_v, 1)  # 벽돌수 < 1 == <= 0
    bc_next = broadcast(bs, "다음라운드", BR_NEXT)
    if_clr = gen(); bs[if_clr] = mk("control_if",
        inputs={"CONDITION":[2,cond_clr], "SUBSTACK":[2,bc_next]})
    bs[cond_clr]["parent"] = if_clr
    bs[bc_next]["parent"] = if_clr

    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(if0,bs[if0]),(if1,bs[if1]),(if2,bs[if2]),(if3,bs[if3]),
           (if_best,bs[if_best]),(dec_cnt,bs[dec_cnt]),(snd_brick,bs[snd_brick]),
           (if_clr,bs[if_clr]),(delc,bs[delc])])

    if_hit = gen(); bs[if_hit] = mk("control_if",
        inputs={"CONDITION":[2,tc], "SUBSTACK":[2,if0]})
    bs[tc]["parent"] = if_hit
    bs[if0]["parent"] = if_hit

    wt_iter = gen(); bs[wt_iter] = mk("control_wait", inputs={"DURATION": num(0.016)})

    chain([(if_hit,bs[if_hit]),(wt_iter,bs[wt_iter])])

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_over], "SUBSTACK":[2,if_hit]})
    bs[cond_over]["parent"] = rep_until
    bs[if_hit]["parent"] = rep_until

    chain([(ch,bs[ch]),(g,bs[g]),(sw,bs[sw]),(show,bs[show]),(rep_until,bs[rep_until])])
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

    # switch costume "gameover"
    go_menu = gen(); bs[go_menu] = mk("looks_costume",
        fields={"COSTUME":["gameover", None]}, shadow=True)
    cm_go = gen(); bs[cm_go] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, go_menu]})
    bs[go_menu]["parent"] = cm_go

    show = gen(); bs[show] = mk("looks_show")
    snd_lose = play_sound(bs, "lose")

    chain([(h,bs[h]),(hi,bs[hi]),(g,bs[g]),(sz,bs[sz]),(front,bs[front]),
           (wait_over,bs[wait_over]),(cm_go,bs[cm_go]),(show,bs[show]),
           (snd_lose,bs[snd_lose])])
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
    pad_md5    = write_svg(PADDLE_SVG)
    ball_md5   = write_svg(BALL_SVG)
    red_md5    = write_svg(BRICK_RED_SVG)
    orange_md5 = write_svg(BRICK_ORANGE_SVG)
    yellow_md5 = write_svg(BRICK_YELLOW_SVG)
    green_md5  = write_svg(BRICK_GREEN_SVG)
    go_md5     = write_svg(GAMEOVER_SVG)

    # pop.wav 를 bounce/brick/lose 공용으로 재사용
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    def snd(name):
        return {"name": name, "assetId": pop_md5, "dataFormat": "wav",
                "format": "", "rate": 11025, "sampleCount": 258,
                "md5ext": f"{pop_md5}.wav"}

    stage_blocks  = build_stage_blocks()
    paddle_blocks = build_paddle_blocks()
    ball_blocks   = build_ball_blocks()
    brick_blocks  = build_brick_blocks()
    banner_blocks = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_SCORE:   ["점수", 0],
            V_BEST:    ["최고기록", 0],
            V_STATE:   ["게임상태", 1],
            V_LIVES:   ["목숨", 3],
            V_ROUND:   ["라운드", 1],
            V_BALLDX:  ["공dx", 3],
            V_BALLDY:  ["공dy", 4],
            V_BALLSPD: ["공속도", 5],
            V_PADHALF: ["패들반폭", 35],
            V_BRICKCNT:["벽돌수", 0],
            V_OFF:     ["오프셋", 0],
            V_RESULT:  ["결과", 0],
        },
        "lists": {},
        "broadcasts": {BR_START: "게임시작", BR_BRICKS: "벽돌생성",
                       BR_LAUNCH: "공발사", BR_NEXT: "다음라운드"},
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "코트", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [snd("bounce")],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    paddle = {
        "isStage": False, "name": "패들",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": paddle_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "paddle", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pad_md5, "md5ext": f"{pad_md5}.svg",
            "rotationCenterX": 35, "rotationCenterY": 8
        }],
        "sounds": [snd("bounce")],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": 0, "y": -150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ball = {
        "isStage": False, "name": "공",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ball_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "ball", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ball_md5, "md5ext": f"{ball_md5}.svg",
            "rotationCenterX": 7, "rotationCenterY": 7
        }],
        "sounds": [snd("bounce"), snd("brick"), snd("lose")],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": 0, "y": -135, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    brick = {
        "isStage": False, "name": "벽돌",
        "variables": {V_BX: ["자기X", 0], V_BY: ["자기Y", 0], V_BROW: ["자기행", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": brick_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "red", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": red_md5, "md5ext": f"{red_md5}.svg",
             "rotationCenterX": 22, "rotationCenterY": 9},
            {"name": "orange", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": orange_md5, "md5ext": f"{orange_md5}.svg",
             "rotationCenterX": 22, "rotationCenterY": 9},
            {"name": "yellow", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": yellow_md5, "md5ext": f"{yellow_md5}.svg",
             "rotationCenterX": 22, "rotationCenterY": 9},
            {"name": "green", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": green_md5, "md5ext": f"{green_md5}.svg",
             "rotationCenterX": 22, "rotationCenterY": 9},
        ],
        "sounds": [snd("brick")],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    banner = {
        "isStage": False, "name": "결과배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": banner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "gameover", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": go_md5, "md5ext": f"{go_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 85},
        ],
        "sounds": [snd("lose")],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_BEST, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "최고기록"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 30,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_LIVES, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "목숨"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 55,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 80,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, paddle, ball, brick, banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "breakout-builder"}
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

    # 변수 ID → (이름) 유효 집합: 글로벌(stage) + 각 타겟의 sprite-local
    def valid_var_ids(target):
        ids = set(stage["variables"].keys())
        ids |= set(target.get("variables", {}).keys())
        return ids

    # block reference integrity check
    def check_refs(target):
        blocks = target["blocks"]
        ids = set(blocks.keys())
        var_ids = valid_var_ids(target)
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
            for fk, fv in b.get("fields", {}).items():
                if fk == "VARIABLE":
                    vid = fv[1]
                    if vid not in var_ids:
                        raise AssertionError(f"{target['name']} {bid} 변수 {vid} 미등록")
                if fk == "BROADCAST_OPTION":
                    brid = fv[1]
                    if brid not in stage["broadcasts"]:
                        raise AssertionError(f"{target['name']} {bid} 방송 {brid} 미등록")
    for t in project["targets"]:
        check_refs(t)

    print(f"wrote {OUTPUT}")
    print(f"  stage:    {len(stage_blocks)} blocks")
    print(f"  패들:     {len(paddle_blocks)} blocks")
    print(f"  공:       {len(ball_blocks)} blocks")
    print(f"  벽돌:     {len(brick_blocks)} blocks")
    print(f"  결과배너: {len(banner_blocks)} blocks")
    total = (len(stage_blocks) + len(paddle_blocks) + len(ball_blocks)
             + len(brick_blocks) + len(banner_blocks))
    print(f"  TOTAL:    {total} blocks")
    print(f"  targets:  {len(project['targets'])}")
    print(f"  monitors: {len(monitors)}")
    print("  refs OK, zip OK, json OK")

if __name__ == "__main__":
    main()
