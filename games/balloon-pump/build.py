#!/usr/bin/env python3
"""풍선 펌프 (balloon-pump) — 스페이스를 꾹 눌러 풍선을 분다.

크게 불수록 점수가 가파르게 오르지만(점수 = round((크기-80)*sqrt(크기-80))),
풍선마다 터지는 한계치(120~220, 비공개)가 달라 너무 욕심내면 펑! 0점.
한계 접근 시 떨림 + 색 경고. 5라운드 합계로 베스트를 노린다.

베이스: games/cowboy-duel/build.py (5라운드 진행 + 합계/베스트 + 결과배너 +
스페이스 1키 긴장형 단일 상태머신) + games/asteroids/build.py (파편 클론 폭발).
핵심 신규: 크기 펌프(set size) + 비선형 점수(sqrt) + 떨림(set x ±2) + 색경고
(set color effect) + 한계치 은닉(monitor visible=false) + 파편 클론 사방 분출.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "풍선펌프.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: 밝은 축제/방 톤 --------
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#BFE3FF"/>
      <stop offset="0.55" stop-color="#D7CCF5"/>
      <stop offset="1" stop-color="#F3E3F7"/>
    </linearGradient>
    <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#E7B98C"/>
      <stop offset="1" stop-color="#C58E5A"/>
    </linearGradient>
  </defs>
  <!-- 벽 -->
  <rect x="0" y="0" width="480" height="330" fill="url(#sky)"/>
  <!-- 축제 가랜드(삼각 깃발) -->
  <path d="M 0 22 Q 240 60 480 22" stroke="#B59CD0" stroke-width="2" fill="none"/>
  <g>
    <path d="M 30 24 L 54 24 L 42 46 Z" fill="#FF6F91"/>
    <path d="M 84 28 L 108 28 L 96 50 Z" fill="#FFC75F"/>
    <path d="M 138 31 L 162 31 L 150 53 Z" fill="#6FD08C"/>
    <path d="M 192 33 L 216 33 L 204 55 Z" fill="#5AA9E6"/>
    <path d="M 264 33 L 288 33 L 276 55 Z" fill="#FF6F91"/>
    <path d="M 318 31 L 342 31 L 330 53 Z" fill="#FFC75F"/>
    <path d="M 372 28 L 396 28 L 384 50 Z" fill="#6FD08C"/>
    <path d="M 426 24 L 450 24 L 438 46 Z" fill="#5AA9E6"/>
  </g>
  <!-- 떠다니는 작은 별/점 장식 -->
  <circle cx="70" cy="120" r="4" fill="#FFFFFF" opacity="0.6"/>
  <circle cx="410" cy="100" r="5" fill="#FFFFFF" opacity="0.5"/>
  <circle cx="360" cy="160" r="3" fill="#FFFFFF" opacity="0.5"/>
  <circle cx="110" cy="200" r="3" fill="#FFFFFF" opacity="0.5"/>
  <!-- 바닥 -->
  <rect x="0" y="330" width="480" height="30" fill="url(#floor)"/>
  <rect x="0" y="330" width="480" height="4" fill="#A9763F" opacity="0.6"/>
  <!-- 펌프가 놓일 자리(왼쪽 아래 매트) -->
  <ellipse cx="120" cy="332" rx="70" ry="9" fill="#B07C49" opacity="0.4"/>
</svg>"""

# -------- 풍선 코스튬: 단일, 선명한 단색(색은 color effect 로 라운드별 변색) --------
# 캔버스 80x110. rotationCenter = 꼭지(아래) (40, 104) → 위로 부푼다.
BALLOON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="110" viewBox="0 0 80 110">
  <defs>
    <radialGradient id="bgrad" cx="0.38" cy="0.34" r="0.72">
      <stop offset="0" stop-color="#FF9DB0"/>
      <stop offset="0.55" stop-color="#FF5C7A"/>
      <stop offset="1" stop-color="#E63956"/>
    </radialGradient>
  </defs>
  <!-- 풍선 몸체 -->
  <ellipse cx="40" cy="44" rx="33" ry="40" fill="url(#bgrad)"/>
  <!-- 하이라이트 -->
  <ellipse cx="28" cy="30" rx="10" ry="14" fill="#FFFFFF" opacity="0.45"/>
  <!-- 꼭지(매듭) -->
  <path d="M 34 82 L 46 82 L 40 92 Z" fill="#E63956"/>
  <!-- 매듭 -->
  <circle cx="40" cy="92" r="4" fill="#C42C46"/>
  <!-- 호스로 이어지는 짧은 꼬리 -->
  <path d="M 40 96 Q 36 102 40 106" stroke="#C9A05A" stroke-width="3" fill="none"/>
</svg>"""

# -------- 펌프 코스튬: 손잡이 올라간/눌린 2장. 캔버스 100x110. rc (50, 104) --------
def _pump(handle_y):
    """handle_y: 손잡이 막대 위쪽 y (작을수록 올라감)."""
    rod_top = handle_y
    rod_h = 88 - rod_top   # 막대 길이 (몸통 위 64까지)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="100" height="110" viewBox="0 0 100 110">
  <!-- 그림자 -->
  <ellipse cx="50" cy="104" rx="40" ry="6" fill="#000000" opacity="0.18"/>
  <!-- 펌프 몸통(원통) -->
  <rect x="30" y="58" width="40" height="46" rx="8" fill="#5AA9E6"/>
  <rect x="34" y="62" width="14" height="38" rx="5" fill="#8CC6F0" opacity="0.7"/>
  <!-- 받침 -->
  <rect x="18" y="98" width="64" height="8" rx="3" fill="#3D7CB8"/>
  <!-- 손잡이 막대 -->
  <rect x="46" y="{rod_top}" width="8" height="{rod_h}" rx="3" fill="#7A5230"/>
  <!-- 손잡이(T) -->
  <rect x="26" y="{rod_top-8}" width="48" height="11" rx="5" fill="#9C6B3E"/>
  <rect x="26" y="{rod_top-8}" width="48" height="4" rx="2" fill="#B98552" opacity="0.7"/>
  <!-- 호스(오른쪽 위로 풍선 꼭지 방향) -->
  <path d="M 70 70 Q 110 60 118 8" stroke="#C9A05A" stroke-width="6" fill="none" stroke-linecap="round"/>
</svg>"""

PUMP_UP_SVG   = _pump(28)   # 손잡이 올라감
PUMP_DOWN_SVG = _pump(46)   # 손잡이 눌림

# -------- 파편: 작은 찢어진 고무 조각 --------
SHARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="20" viewBox="0 0 24 20">
  <path d="M 2 10 L 8 2 L 16 4 L 22 12 L 14 18 L 5 16 Z" fill="#FF5C7A"/>
  <path d="M 8 2 L 16 4 L 14 18 L 5 16 Z" fill="#E63956" opacity="0.6"/>
</svg>"""

# -------- 결과배너 코스튬 공통 헬퍼 --------
def _banner(border, big_color, big_text, sub_color, sub_text):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="6" y="6" width="348" height="138" rx="16" fill="#2E2440" opacity="0.94" stroke="{border}" stroke-width="5"/>
  <text x="180" y="74" text-anchor="middle" fill="{big_color}"
        font-family="Arial Black, Arial, sans-serif" font-size="48" font-weight="900">{big_text}</text>
  <text x="180" y="112" text-anchor="middle" fill="{sub_color}"
        font-family="Arial, Helvetica, sans-serif" font-size="20">{sub_text}</text>
</svg>"""

POP_SVG     = _banner("#E53935", "#FF6F61", "펑!", "#FFCDD2", "이번 라운드 0점")
SAFE_SVG    = _banner("#43A047", "#7CE38B", "안전!", "#C8F7CE", "점수 획득 — 모니터 확인")
RESULT_SVG  = _banner("#5AA9E6", "#9AD0FF", "끝!", "#DDEEFF", "합계 확정 (모니터)")
NEWBEST_SVG = _banner("#FFC107", "#FFD740", "신기록!", "#FFF3C4", "최고 기록 달성!")

# ============================================================
#  helpers (cowboy-duel 와 동일)
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

# not(...) 헬퍼 (≥ 구현용: not(a<b))
def not_op(bs, inner):
    bid = gen()
    bs[bid] = mk("operator_not", inputs={"OPERAND":[2, inner]})
    bs[inner]["parent"] = bid
    return bid

# sqrt 헬퍼 (operator_mathop)
def sqrt_op(bs, inner):
    bid = gen()
    if isinstance(inner, str):
        ins = {"NUM": slot(inner)}
    else:
        ins = {"NUM": num(inner)}
    bs[bid] = mk("operator_mathop", inputs=ins, fields={"OPERATOR":["sqrt", None]})
    if isinstance(inner, str): bs[inner]["parent"] = bid
    return bid

# play sound 헬퍼
def play_sound(bs, name):
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":[name, None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    return snd

def set_pitch(bs, val):
    bid = gen(); bs[bid] = mk("sound_seteffectto",
        inputs={"VALUE": num(val)}, fields={"EFFECT": ["PITCH", None]})
    return bid

def broadcast(bs, name, bid):
    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, bid]}, shadow=True)
    bc = gen(); bs[bc] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm]})
    bs[bm]["parent"] = bc
    return bc

def key_pressed(bs, key="space"):
    km = gen(); bs[km] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": [key, None]}, shadow=True)
    kp = gen(); bs[kp] = mk("sensing_keypressed", inputs={"KEY_OPTION":[1, km]})
    bs[km]["parent"] = kp
    return kp

def switch_costume(bs, name):
    cm = gen(); bs[cm] = mk("looks_costume",
        fields={"COSTUME":[name, None]}, shadow=True)
    sc = gen(); bs[sc] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, cm]})
    bs[cm]["parent"] = sc
    return sc

def set_color_effect(bs, value_block):
    """set color effect to (value_block id)."""
    bid = gen(); bs[bid] = mk("looks_seteffectto",
        inputs={"VALUE": slot(value_block)}, fields={"EFFECT": ["COLOR", None]})
    bs[value_block]["parent"] = bid
    return bid

# ============================================================
#  IDs — 글로벌 변수 11개
# ============================================================
V_STATE     = "varState01"      # 게임상태 0=펌프중 1=결과처리중 2=종료
V_ROUND     = "varRound02"      # 라운드 1~5
V_MAXROUND  = "varMaxRound03"   # 총라운드 5
V_CURSCORE  = "varCurScore04"   # 이번점수
V_TOTAL     = "varTotal05"      # 합계
V_BEST      = "varBest06"       # 베스트
V_SIZE      = "varSize07"       # 현재크기 (size %)
V_LIMIT     = "varLimit08"      # 한계치 (비공개)
V_SHAKE     = "varShakeStart09" # 떨림시작 (비공개)
V_RRESULT   = "varRResult10"    # 라운드결과 0/1/2
V_PUMPING   = "varPumping11"    # 펌프중 0/1

BR_START     = "brStart01"       # 게임시작
BR_ROUNDSTART= "brRoundStart02"  # 라운드시작
BR_POP       = "brPop03"         # 터짐
BR_CONFIRM   = "brConfirm04"     # 확정
BR_ROUNDEND  = "brRoundEnd05"    # 라운드끝
BR_RESULT    = "brResult06"      # 결과

# ============================================================
#  STAGE blocks
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: init + broadcast 게임시작 + 라운드시작 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = [(h, bs[h])]
    def setv(name, vid, val):
        b = gen(); bs[b] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": [name, vid]})
        inits.append((b, bs[b]))
    setv("게임상태", V_STATE, 1)        # 잠깐 비입력. 라운드시작에서 0
    setv("라운드", V_ROUND, 1)
    setv("총라운드", V_MAXROUND, 5)
    setv("합계", V_TOTAL, 0)
    setv("베스트", V_BEST, 0)
    setv("이번점수", V_CURSCORE, 0)
    setv("현재크기", V_SIZE, 80)
    setv("라운드결과", V_RRESULT, 0)
    setv("펌프중", V_PUMPING, 0)
    bc_start = broadcast(bs, "게임시작", BR_START)
    inits.append((bc_start, bs[bc_start]))
    bc_rstart = broadcast(bs, "라운드시작", BR_ROUNDSTART)
    inits.append((bc_rstart, bs[bc_rstart]))
    chain(inits)

    # === when receive 라운드시작: 한계치/떨림시작 생성 + 리셋 + 입력개시 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUNDSTART]})

    set_rr0 = gen(); bs[set_rr0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["라운드결과", V_RRESULT]})
    set_cs0 = gen(); bs[set_cs0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["이번점수", V_CURSCORE]})
    set_sz80 = gen(); bs[set_sz80] = mk("data_setvariableto",
        inputs={"VALUE": num(80)}, fields={"VARIABLE": ["현재크기", V_SIZE]})
    set_pump0 = gen(); bs[set_pump0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["펌프중", V_PUMPING]})

    # 한계치 ← pick random 120 to 220
    rnd_limit = gen(); bs[rnd_limit] = mk("operator_random",
        inputs={"FROM": num(120), "TO": num(220)})
    set_limit = gen(); bs[set_limit] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_limit)}, fields={"VARIABLE": ["한계치", V_LIMIT]})
    bs[rnd_limit]["parent"] = set_limit

    # 떨림시작 ← round( 한계치 * (pick random 60 to 80) / 100 )
    limit_v = vrep("한계치", V_LIMIT)
    rnd_pct = gen(); bs[rnd_pct] = mk("operator_random",
        inputs={"FROM": num(60), "TO": num(80)})
    mul = op("operator_multiply", limit_v, rnd_pct)
    bs[rnd_pct]["parent"] = mul
    div = op("operator_divide", mul, 100)
    round_sh = gen(); bs[round_sh] = mk("operator_round", inputs={"NUM": slot(div)})
    bs[div]["parent"] = round_sh
    set_shake = gen(); bs[set_shake] = mk("data_setvariableto",
        inputs={"VALUE": slot(round_sh)}, fields={"VARIABLE": ["떨림시작", V_SHAKE]})
    bs[round_sh]["parent"] = set_shake

    wait01 = gen(); bs[wait01] = mk("control_wait", inputs={"DURATION": num(0.1)})
    set_state0 = gen(); bs[set_state0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})

    chain([(h2,bs[h2]),(set_rr0,bs[set_rr0]),(set_cs0,bs[set_cs0]),
           (set_sz80,bs[set_sz80]),(set_pump0,bs[set_pump0]),
           (set_limit,bs[set_limit]),(set_shake,bs[set_shake]),
           (wait01,bs[wait01]),(set_state0,bs[set_state0])])

    # === when receive 라운드끝: 점수 합산 + 다음 라운드 or 최종 판정 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=640,
        fields={"BROADCAST_OPTION": ["라운드끝", BR_ROUNDEND]})

    # if 라운드결과=1 → 합계 += 이번점수
    rr_v1 = vrep("라운드결과", V_RRESULT)
    cond_r1 = cmp_op("operator_equals", rr_v1, 1)
    cs_v = vrep("이번점수", V_CURSCORE)
    add_total = gen(); bs[add_total] = mk("data_changevariableby",
        inputs={"VALUE": slot(cs_v)}, fields={"VARIABLE": ["합계", V_TOTAL]})
    bs[cs_v]["parent"] = add_total
    if_r1 = gen(); bs[if_r1] = mk("control_if",
        inputs={"CONDITION":[2,cond_r1], "SUBSTACK":[2,add_total]})
    bs[cond_r1]["parent"] = if_r1
    bs[add_total]["parent"] = if_r1

    wait_view = gen(); bs[wait_view] = mk("control_wait", inputs={"DURATION": num(1.4)})

    # if 라운드 < 총라운드 → {라운드+1; wait0.4; broadcast 라운드시작}
    #                  else → {게임상태2; if 합계>베스트 베스트=합계; broadcast 결과}
    round_v = vrep("라운드", V_ROUND)
    maxr_v = vrep("총라운드", V_MAXROUND)
    cond_more = cmp_op("operator_lt", round_v, maxr_v)

    inc_round = gen(); bs[inc_round] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
    wait_next = gen(); bs[wait_next] = mk("control_wait", inputs={"DURATION": num(0.4)})
    bc_next = broadcast(bs, "라운드시작", BR_ROUNDSTART)
    chain([(inc_round,bs[inc_round]),(wait_next,bs[wait_next]),(bc_next,bs[bc_next])])

    # else 분기
    set_state2 = gen(); bs[set_state2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    total_v = vrep("합계", V_TOTAL)
    best_v = vrep("베스트", V_BEST)
    cond_newbest = cmp_op("operator_gt", total_v, best_v)
    total_v2 = vrep("합계", V_TOTAL)
    set_best = gen(); bs[set_best] = mk("data_setvariableto",
        inputs={"VALUE": slot(total_v2)}, fields={"VARIABLE": ["베스트", V_BEST]})
    bs[total_v2]["parent"] = set_best
    if_best = gen(); bs[if_best] = mk("control_if",
        inputs={"CONDITION":[2,cond_newbest], "SUBSTACK":[2,set_best]})
    bs[cond_newbest]["parent"] = if_best
    bs[set_best]["parent"] = if_best
    bc_result = broadcast(bs, "결과", BR_RESULT)
    chain([(set_state2,bs[set_state2]),(if_best,bs[if_best]),(bc_result,bs[bc_result])])

    if_more = gen(); bs[if_more] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_more], "SUBSTACK":[2,inc_round],
                "SUBSTACK2":[2,set_state2]})
    bs[cond_more]["parent"] = if_more
    bs[inc_round]["parent"] = if_more
    bs[set_state2]["parent"] = if_more

    chain([(h3,bs[h3]),(if_r1,bs[if_r1]),(wait_view,bs[wait_view]),(if_more,bs[if_more])])

    return bs

# ============================================================
#  풍선 (메인 컨트롤러) blocks
# ============================================================
def build_balloon_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # 라운드색 식: (라운드-1)*40  → 재사용 빌더
    def round_color_block():
        r_v = vrep("라운드", V_ROUND)
        rm1 = op("operator_subtract", r_v, 1)
        return op("operator_multiply", rm1, 40)

    # === when flag clicked: 위치/코스튬/크기/효과 클리어/숨김 ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    cm = switch_costume(bs, "balloon")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    clr = gen(); bs[clr] = mk("looks_cleargraphiceffects")
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(g,bs[g]),(cm,bs[cm]),(sz,bs[sz]),(clr,bs[clr]),(hi,bs[hi])])

    # === when receive 라운드시작: 리셋 + 라운드색 + show ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUNDSTART]})
    g2 = gen(); bs[g2] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    set_sz80 = gen(); bs[set_sz80] = mk("data_setvariableto",
        inputs={"VALUE": num(80)}, fields={"VARIABLE": ["현재크기", V_SIZE]})
    sz2 = gen(); bs[sz2] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    # set color effect to (라운드-1)*40
    rc2 = round_color_block()
    setcol2 = set_color_effect(bs, rc2)
    sh2 = gen(); bs[sh2] = mk("looks_show")
    chain([(h2,bs[h2]),(g2,bs[g2]),(set_sz80,bs[set_sz80]),(sz2,bs[sz2]),
           (setcol2,bs[setcol2]),(sh2,bs[sh2])])

    # === when flag clicked (펌프 forever 루프) ===
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=320, y=20)

    # --- if space pressed (THEN 분기) ---
    inc_size = gen(); bs[inc_size] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["현재크기", V_SIZE]})
    set_pump1 = gen(); bs[set_pump1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["펌프중", V_PUMPING]})
    size_v1 = vrep("현재크기", V_SIZE)
    set_size_look = gen(); bs[set_size_look] = mk("looks_setsizeto",
        inputs={"SIZE": slot(size_v1)})
    bs[size_v1]["parent"] = set_size_look

    # 이번점수 ← round( (현재크기-80) * sqrt(현재크기-80) )
    size_v2 = vrep("현재크기", V_SIZE)
    blown1 = op("operator_subtract", size_v2, 80)
    size_v3 = vrep("현재크기", V_SIZE)
    blown2 = op("operator_subtract", size_v3, 80)
    sq = sqrt_op(bs, blown2)
    prod = op("operator_multiply", blown1, sq)
    bs[sq]["parent"] = prod
    round_sc = gen(); bs[round_sc] = mk("operator_round", inputs={"NUM": slot(prod)})
    bs[prod]["parent"] = round_sc
    set_score = gen(); bs[set_score] = mk("data_setvariableto",
        inputs={"VALUE": slot(round_sc)}, fields={"VARIABLE": ["이번점수", V_CURSCORE]})
    bs[round_sc]["parent"] = set_score

    # --- 위험경고: if 현재크기 ≥ 떨림시작 → 떨림+색  else → set x 0 + 라운드색 ---
    size_v4 = vrep("현재크기", V_SIZE)
    shake_v = vrep("떨림시작", V_SHAKE)
    lt_shake = cmp_op("operator_lt", size_v4, shake_v)
    cond_shake = not_op(bs, lt_shake)   # ≥ : not(현재크기 < 떨림시작)

    # THEN: set x to (pick random -2 to 2); set color to (라운드-1)*40 + (현재크기-떨림시작)*8
    rnd_x = gen(); bs[rnd_x] = mk("operator_random",
        inputs={"FROM": num(-2), "TO": num(2)})
    set_x_shake = gen(); bs[set_x_shake] = mk("motion_setx",
        inputs={"X": slot(rnd_x)})
    bs[rnd_x]["parent"] = set_x_shake
    rc_warn = round_color_block()
    size_v5 = vrep("현재크기", V_SIZE)
    shake_v2 = vrep("떨림시작", V_SHAKE)
    over = op("operator_subtract", size_v5, shake_v2)
    bs[shake_v2]["parent"] = over
    over8 = op("operator_multiply", over, 8)
    warn_total = op("operator_add", rc_warn, over8)
    bs[rc_warn]["parent"] = warn_total; bs[over8]["parent"] = warn_total
    set_col_warn = set_color_effect(bs, warn_total)
    chain([(set_x_shake,bs[set_x_shake]),(set_col_warn,bs[set_col_warn])])

    # ELSE: set x to 0; set color to (라운드-1)*40
    set_x0 = gen(); bs[set_x0] = mk("motion_setx", inputs={"X": num(0)})
    rc_base = round_color_block()
    set_col_base = set_color_effect(bs, rc_base)
    chain([(set_x0,bs[set_x0]),(set_col_base,bs[set_col_base])])

    if_shake = gen(); bs[if_shake] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_shake], "SUBSTACK":[2,set_x_shake],
                "SUBSTACK2":[2,set_x0]})
    bs[cond_shake]["parent"] = if_shake
    bs[set_x_shake]["parent"] = if_shake
    bs[set_x0]["parent"] = if_shake

    # --- 터짐 판정: if 현재크기 ≥ 한계치 → 라운드결과2; 게임상태1; broadcast 터짐 ---
    size_v6 = vrep("현재크기", V_SIZE)
    limit_v = vrep("한계치", V_LIMIT)
    lt_limit = cmp_op("operator_lt", size_v6, limit_v)
    cond_pop = not_op(bs, lt_limit)   # ≥
    set_rr2 = gen(); bs[set_rr2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["라운드결과", V_RRESULT]})
    set_state1a = gen(); bs[set_state1a] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bc_pop = broadcast(bs, "터짐", BR_POP)
    chain([(set_rr2,bs[set_rr2]),(set_state1a,bs[set_state1a]),(bc_pop,bs[bc_pop])])
    if_pop = gen(); bs[if_pop] = mk("control_if",
        inputs={"CONDITION":[2,cond_pop], "SUBSTACK":[2,set_rr2]})
    bs[cond_pop]["parent"] = if_pop
    bs[set_rr2]["parent"] = if_pop

    # THEN 본체 체인 (스페이스 눌림)
    chain([(set_pump1,bs[set_pump1]),(inc_size,bs[inc_size]),
           (set_size_look,bs[set_size_look]),(set_score,bs[set_score]),
           (if_shake,bs[if_shake]),(if_pop,bs[if_pop])])

    # --- ELSE 분기 (스페이스 안 눌림): if 펌프중=1 and 현재크기>80 → 확정 ---
    pump_v = vrep("펌프중", V_PUMPING)
    cond_pumping = cmp_op("operator_equals", pump_v, 1)
    size_v7 = vrep("현재크기", V_SIZE)
    cond_blown = cmp_op("operator_gt", size_v7, 80)
    cond_confirm = bool_op("operator_and", cond_pumping, cond_blown)
    set_x0b = gen(); bs[set_x0b] = mk("motion_setx", inputs={"X": num(0)})
    set_rr1 = gen(); bs[set_rr1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드결과", V_RRESULT]})
    set_state1b = gen(); bs[set_state1b] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bc_confirm = broadcast(bs, "확정", BR_CONFIRM)
    chain([(set_x0b,bs[set_x0b]),(set_rr1,bs[set_rr1]),
           (set_state1b,bs[set_state1b]),(bc_confirm,bs[bc_confirm])])
    if_confirm = gen(); bs[if_confirm] = mk("control_if",
        inputs={"CONDITION":[2,cond_confirm], "SUBSTACK":[2,set_x0b]})
    bs[cond_confirm]["parent"] = if_confirm
    bs[set_x0b]["parent"] = if_confirm
    # 펌프중 ← 0 (항상)
    set_pump0_else = gen(); bs[set_pump0_else] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["펌프중", V_PUMPING]})
    chain([(if_confirm,bs[if_confirm]),(set_pump0_else,bs[set_pump0_else])])

    # if space → THEN(펌프) else → 확정체크
    sp = key_pressed(bs)
    if_space = gen(); bs[if_space] = mk("control_if_else",
        inputs={"CONDITION":[2,sp], "SUBSTACK":[2,set_pump1],
                "SUBSTACK2":[2,if_confirm]})
    bs[sp]["parent"] = if_space
    bs[set_pump1]["parent"] = if_space
    bs[if_confirm]["parent"] = if_space

    # if 게임상태=0 → { if_space }
    state_v = vrep("게임상태", V_STATE)
    cond_state0 = cmp_op("operator_equals", state_v, 0)
    if_state = gen(); bs[if_state] = mk("control_if",
        inputs={"CONDITION":[2,cond_state0], "SUBSTACK":[2,if_space]})
    bs[cond_state0]["parent"] = if_state
    bs[if_space]["parent"] = if_state

    # wait 0.02
    w = gen(); bs[w] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(if_state,bs[if_state]),(w,bs[w])])

    forever = gen(); bs[forever] = mk("control_forever",
        inputs={"SUBSTACK":[2, if_state]})
    bs[if_state]["parent"] = forever
    chain([(h3,bs[h3]),(forever,bs[forever])])

    # === when receive 확정: 탄력 연출 후 broadcast 라운드끝 ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=620, y=20,
        fields={"BROADCAST_OPTION": ["확정", BR_CONFIRM]})
    set_x0c = gen(); bs[set_x0c] = mk("motion_setx", inputs={"X": num(0)})
    # repeat 2 { set size (현재크기+4); wait0.05; set size 현재크기; wait0.05 }
    size_v8 = vrep("현재크기", V_SIZE)
    sizep4 = op("operator_add", size_v8, 4)
    sz_big = gen(); bs[sz_big] = mk("looks_setsizeto", inputs={"SIZE": slot(sizep4)})
    bs[sizep4]["parent"] = sz_big
    wb1 = gen(); bs[wb1] = mk("control_wait", inputs={"DURATION": num(0.05)})
    size_v9 = vrep("현재크기", V_SIZE)
    sz_norm = gen(); bs[sz_norm] = mk("looks_setsizeto", inputs={"SIZE": slot(size_v9)})
    bs[size_v9]["parent"] = sz_norm
    wb2 = gen(); bs[wb2] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(sz_big,bs[sz_big]),(wb1,bs[wb1]),(sz_norm,bs[sz_norm]),(wb2,bs[wb2])])
    rep_bounce = gen(); bs[rep_bounce] = mk("control_repeat",
        inputs={"TIMES": num(2), "SUBSTACK":[2, sz_big]})
    bs[sz_big]["parent"] = rep_bounce
    bc_end_c = broadcast(bs, "라운드끝", BR_ROUNDEND)
    chain([(h4,bs[h4]),(set_x0c,bs[set_x0c]),(rep_bounce,bs[rep_bounce]),(bc_end_c,bs[bc_end_c])])

    # === when receive 터짐: hide + set x 0 + broadcast 라운드끝 ===
    h5 = gen(); bs[h5] = mk("event_whenbroadcastreceived", top=True, x=620, y=320,
        fields={"BROADCAST_OPTION": ["터짐", BR_POP]})
    hi5 = gen(); bs[hi5] = mk("looks_hide")
    set_x0d = gen(); bs[set_x0d] = mk("motion_setx", inputs={"X": num(0)})
    bc_end_p = broadcast(bs, "라운드끝", BR_ROUNDEND)
    chain([(h5,bs[h5]),(hi5,bs[hi5]),(set_x0d,bs[set_x0d]),(bc_end_p,bs[bc_end_p])])

    return bs

# ============================================================
#  펌프 (손잡이 들썩 연출) blocks
# ============================================================
def build_pump_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: 위치/코스튬/show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-120), "Y": num(-120)})
    cm = switch_costume(bs, "pump_up")
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(cm,bs[cm]),(sh,bs[sh])])

    # === when flag clicked: 손잡이 애니 forever ===
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=320, y=20)
    pump_v = vrep("펌프중", V_PUMPING)
    cond_pumping = cmp_op("operator_equals", pump_v, 1)
    # THEN: pump_down; wait0.08; pump_up; wait0.08
    cm_down = switch_costume(bs, "pump_down")
    wd1 = gen(); bs[wd1] = mk("control_wait", inputs={"DURATION": num(0.08)})
    cm_up = switch_costume(bs, "pump_up")
    wd2 = gen(); bs[wd2] = mk("control_wait", inputs={"DURATION": num(0.08)})
    chain([(cm_down,bs[cm_down]),(wd1,bs[wd1]),(cm_up,bs[cm_up]),(wd2,bs[wd2])])
    # ELSE: pump_up; wait0.05
    cm_up2 = switch_costume(bs, "pump_up")
    we = gen(); bs[we] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(cm_up2,bs[cm_up2]),(we,bs[we])])
    if_pump = gen(); bs[if_pump] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_pumping], "SUBSTACK":[2,cm_down],
                "SUBSTACK2":[2,cm_up2]})
    bs[cond_pumping]["parent"] = if_pump
    bs[cm_down]["parent"] = if_pump
    bs[cm_up2]["parent"] = if_pump
    forever = gen(); bs[forever] = mk("control_forever",
        inputs={"SUBSTACK":[2, if_pump]})
    bs[if_pump]["parent"] = forever
    chain([(h2,bs[h2]),(forever,bs[forever])])

    return bs

# ============================================================
#  파편 (터질 때 사방 분출) blocks
# ============================================================
def build_shard_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    chain([(h,bs[h]),(hi,bs[hi]),(rs,bs[rs])])

    # === when receive 터짐: 본체 위치 이동 + pop 사운드 + 클론 10개 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["터짐", BR_POP]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    pitch = set_pitch(bs, 0)
    snd = play_sound(bs, "pop")
    # repeat 10 create clone of myself
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(10), "SUBSTACK":[2, cclone]})
    bs[cclone]["parent"] = rep
    chain([(h2,bs[h2]),(g,bs[g]),(pitch,bs[pitch]),(snd,bs[snd]),(rep,bs[rep])])

    # === when start as clone: 사방으로 튀며 페이드 후 삭제 ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=320, y=20)
    g2 = gen(); bs[g2] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    sh = gen(); bs[sh] = mk("looks_show")
    # point in direction (pick random 1 to 360)
    rnd_dir = gen(); bs[rnd_dir] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(360)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(rnd_dir)})
    bs[rnd_dir]["parent"] = pdir
    # set size (pick random 40 to 90)
    rnd_sz = gen(); bs[rnd_sz] = mk("operator_random",
        inputs={"FROM": num(40), "TO": num(90)})
    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto", inputs={"SIZE": slot(rnd_sz)})
    bs[rnd_sz]["parent"] = set_sz
    # set [속도] to (pick random 4 to 9)  → sprite-local lvSpeed01
    rnd_spd = gen(); bs[rnd_spd] = mk("operator_random",
        inputs={"FROM": num(4), "TO": num(9)})
    set_spd = gen(); bs[set_spd] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_spd)}, fields={"VARIABLE": ["속도", LV_SPEED]})
    bs[rnd_spd]["parent"] = set_spd
    # clear ghost (혹시 누적되었을 경우)
    clr = gen(); bs[clr] = mk("looks_cleargraphiceffects")

    # repeat 16 { move 속도; change y -1; ghost +5; wait 0.02 }
    spd_v = vrep("속도", LV_SPEED)
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": slot(spd_v)})
    bs[spd_v]["parent"] = mv
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": num(-1)})
    gh = gen(); bs[gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(5)}, fields={"EFFECT": ["GHOST", None]})
    wcl = gen(); bs[wcl] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(mv,bs[mv]),(chy,bs[chy]),(gh,bs[gh]),(wcl,bs[wcl])])
    rep_move = gen(); bs[rep_move] = mk("control_repeat",
        inputs={"TIMES": num(16), "SUBSTACK":[2, mv]})
    bs[mv]["parent"] = rep_move
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    chain([(ch,bs[ch]),(g2,bs[g2]),(sh,bs[sh]),(pdir,bs[pdir]),(set_sz,bs[set_sz]),
           (set_spd,bs[set_spd]),(clr,bs[clr]),(rep_move,bs[rep_move]),(del_c,bs[del_c])])

    return bs

# ============================================================
#  결과배너 blocks
# ============================================================
def build_banner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: 위치/front/hide ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(g,bs[g]),(front,bs[front]),(sz,bs[sz]),(hi,bs[hi])])

    # === when receive 터짐: pop 코스튬 + show + wait1.2 + hide ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["터짐", BR_POP]})
    cm_pop = switch_costume(bs, "pop")
    front2 = gen(); bs[front2] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    sh2 = gen(); bs[sh2] = mk("looks_show")
    w12a = gen(); bs[w12a] = mk("control_wait", inputs={"DURATION": num(1.2)})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(h2,bs[h2]),(cm_pop,bs[cm_pop]),(front2,bs[front2]),(sh2,bs[sh2]),
           (w12a,bs[w12a]),(hi2,bs[hi2])])

    # === when receive 확정: safe 코스튬 + show + ding(pitch+300) + wait1.2 + hide ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=380,
        fields={"BROADCAST_OPTION": ["확정", BR_CONFIRM]})
    cm_safe = switch_costume(bs, "safe")
    front3 = gen(); bs[front3] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    sh3 = gen(); bs[sh3] = mk("looks_show")
    pitch_ding = set_pitch(bs, 300)
    snd_ding = play_sound(bs, "pop")
    w12b = gen(); bs[w12b] = mk("control_wait", inputs={"DURATION": num(1.2)})
    hi3 = gen(); bs[hi3] = mk("looks_hide")
    chain([(h3,bs[h3]),(cm_safe,bs[cm_safe]),(front3,bs[front3]),(sh3,bs[sh3]),
           (pitch_ding,bs[pitch_ding]),(snd_ding,bs[snd_ding]),(w12b,bs[w12b]),(hi3,bs[hi3])])

    # === when receive 결과: result(or newbest) 코스튬 + show ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=20, y=560,
        fields={"BROADCAST_OPTION": ["결과", BR_RESULT]})
    front4 = gen(); bs[front4] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    # if (합계 = 베스트) and (합계 > 0) → newbest 잠깐, else result
    # (라운드끝에서 합계>베스트면 베스트=합계 갱신했으므로 신기록이면 합계=베스트)
    total_v = vrep("합계", V_TOTAL)
    best_v = vrep("베스트", V_BEST)
    cond_eq = cmp_op("operator_equals", total_v, best_v)
    total_v2 = vrep("합계", V_TOTAL)
    cond_pos = cmp_op("operator_gt", total_v2, 0)
    cond_newbest = bool_op("operator_and", cond_eq, cond_pos)
    # THEN: newbest show wait1 then result
    cm_nb = switch_costume(bs, "newbest")
    sh_nb = gen(); bs[sh_nb] = mk("looks_show")
    pitch_nb = set_pitch(bs, 400)
    snd_nb = play_sound(bs, "pop")
    w_nb = gen(); bs[w_nb] = mk("control_wait", inputs={"DURATION": num(1.0)})
    cm_res_after = switch_costume(bs, "result")
    chain([(cm_nb,bs[cm_nb]),(sh_nb,bs[sh_nb]),(pitch_nb,bs[pitch_nb]),
           (snd_nb,bs[snd_nb]),(w_nb,bs[w_nb]),(cm_res_after,bs[cm_res_after])])
    # ELSE: result show
    cm_res = switch_costume(bs, "result")
    sh_res = gen(); bs[sh_res] = mk("looks_show")
    chain([(cm_res,bs[cm_res]),(sh_res,bs[sh_res])])
    if_nb = gen(); bs[if_nb] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_newbest], "SUBSTACK":[2,cm_nb],
                "SUBSTACK2":[2,cm_res]})
    bs[cond_newbest]["parent"] = if_nb
    bs[cm_nb]["parent"] = if_nb
    bs[cm_res]["parent"] = if_nb
    chain([(h4,bs[h4]),(front4,bs[front4]),(if_nb,bs[if_nb])])

    return bs

# 파편 sprite-local 변수
LV_SPEED = "lvSpeed01"

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

    bg_md5      = write_svg(BG_SVG)
    balloon_md5 = write_svg(BALLOON_SVG)
    pumpup_md5  = write_svg(PUMP_UP_SVG)
    pumpdn_md5  = write_svg(PUMP_DOWN_SVG)
    shard_md5   = write_svg(SHARD_SVG)
    pop_md5b    = write_svg(POP_SVG)
    safe_md5    = write_svg(SAFE_SVG)
    result_md5  = write_svg(RESULT_SVG)
    newbest_md5 = write_svg(NEWBEST_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_wav_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_wav_md5}.wav", "wb") as f: f.write(pop_bytes)

    def pop_sound():
        return {"name": "pop", "assetId": pop_wav_md5, "dataFormat": "wav",
                "format": "", "rate": 11025, "sampleCount": 258,
                "md5ext": f"{pop_wav_md5}.wav"}

    stage_blocks   = build_stage_blocks()
    balloon_blocks = build_balloon_blocks()
    pump_blocks    = build_pump_blocks()
    shard_blocks   = build_shard_blocks()
    banner_blocks  = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_STATE:    ["게임상태", 0],
            V_ROUND:    ["라운드", 1],
            V_MAXROUND: ["총라운드", 5],
            V_CURSCORE: ["이번점수", 0],
            V_TOTAL:    ["합계", 0],
            V_BEST:     ["베스트", 0],
            V_SIZE:     ["현재크기", 80],
            V_LIMIT:    ["한계치", 0],
            V_SHAKE:    ["떨림시작", 0],
            V_RRESULT:  ["라운드결과", 0],
            V_PUMPING:  ["펌프중", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작", BR_ROUNDSTART: "라운드시작",
            BR_POP: "터짐", BR_CONFIRM: "확정",
            BR_ROUNDEND: "라운드끝", BR_RESULT: "결과",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bg", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    balloon = {
        "isStage": False, "name": "풍선",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": balloon_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "balloon", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": balloon_md5, "md5ext": f"{balloon_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 104},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 20, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    pump = {
        "isStage": False, "name": "펌프",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pump_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "pump_up", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pumpup_md5, "md5ext": f"{pumpup_md5}.svg",
             "rotationCenterX": 50, "rotationCenterY": 104},
            {"name": "pump_down", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pumpdn_md5, "md5ext": f"{pumpdn_md5}.svg",
             "rotationCenterX": 50, "rotationCenterY": 104},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": -120, "y": -120, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    shard = {
        "isStage": False, "name": "파편",
        "variables": {LV_SPEED: ["속도", 0]}, "lists": {}, "broadcasts": {},
        "blocks": shard_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "shard", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": shard_md5, "md5ext": f"{shard_md5}.svg",
             "rotationCenterX": 12, "rotationCenterY": 10},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 20, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    banner = {
        "isStage": False, "name": "결과배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": banner_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "pop", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pop_md5b, "md5ext": f"{pop_md5b}.svg",
             "rotationCenterX": 180, "rotationCenterY": 75},
            {"name": "safe", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": safe_md5, "md5ext": f"{safe_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 75},
            {"name": "result", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": result_md5, "md5ext": f"{result_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 75},
            {"name": "newbest", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": newbest_md5, "md5ext": f"{newbest_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 75},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # 모니터: 라운드/이번점수/합계/베스트 (한계치/떨림시작은 숨김)
    monitors = [
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_CURSCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "이번점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_TOTAL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "합계"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_BEST, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "베스트"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        # 비공개: 한계치 / 떨림시작 → visible False (누설 방지)
        {"id": V_LIMIT, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "한계치"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 200,
         "visible": False, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_SHAKE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "떨림시작"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 230,
         "visible": False, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, balloon, pump, shard, banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "balloon-pump-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # ---- validate ----
    with open(pj, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert zipfile.is_zipfile(OUTPUT)
    assert zipfile.ZipFile(OUTPUT).testzip() is None

    # 모든 sprite-local 변수 + stage 글로벌 변수 합집합
    def all_var_ids(target):
        ids = set(stage["variables"].keys())
        ids |= set(target["variables"].keys())
        return ids

    def check_refs(target):
        blocks = target["blocks"]
        ids = set(blocks.keys())
        valid_vars = all_var_ids(target)
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
                    if vid not in valid_vars:
                        raise AssertionError(f"{target['name']} {bid} 변수 {vid} 미등록")
                if fk == "BROADCAST_OPTION":
                    brid = fv[1]
                    if brid not in stage["broadcasts"]:
                        raise AssertionError(f"{target['name']} {bid} 방송 {brid} 미등록")
    for t in project["targets"]:
        check_refs(t)

    # costume name 참조 무결성
    cos_names = {t["name"]: {c["name"] for c in t["costumes"]} for t in project["targets"]}
    for t in project["targets"]:
        for bid, b in t["blocks"].items():
            if isinstance(b, dict) and b.get("opcode") == "looks_costume":
                cn = b["fields"]["COSTUME"][0]
                if cn not in cos_names[t["name"]]:
                    raise AssertionError(f"{t['name']} 코스튬 '{cn}' 없음")

    # 비공개 변수 monitor visible=false 검증
    for m in monitors:
        if m["id"] in (V_LIMIT, V_SHAKE):
            assert m["visible"] is False, f"{m['id']} 모니터가 노출됨(누설)"

    print(f"wrote {OUTPUT}")
    print(f"  Stage:    {len(stage_blocks)} blocks")
    print(f"  풍선:     {len(balloon_blocks)} blocks")
    print(f"  펌프:     {len(pump_blocks)} blocks")
    print(f"  파편:     {len(shard_blocks)} blocks")
    print(f"  결과배너: {len(banner_blocks)} blocks")
    total = (len(stage_blocks) + len(balloon_blocks) + len(pump_blocks)
             + len(shard_blocks) + len(banner_blocks))
    print(f"  TOTAL:    {total} blocks")
    print(f"  targets:  {len(project['targets'])}")
    print(f"  monitors: {len(monitors)} (visible 4, hidden 2: 한계치/떨림시작)")
    print(f"  SVG: 9, WAV: 1 (pop)")
    print("  refs OK, costumes OK, zip OK, json OK, 비공개변수 숨김 OK")

if __name__ == "__main__":
    main()
