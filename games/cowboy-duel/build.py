#!/usr/bin/env python3
"""카우보이 결투 (cowboy-duel) — 서부 석양 1:1 권총 반응속도 결투.

"DRAW!" 신호가 번쩍이면 즉시 스페이스를 눌러 사격. AI 보다 빠르면 라운드 승리,
신호 전에 누르면 부정출발(반칙) 패배. 5판 3선승.

베이스: games/pong/build.py (게임상태 broadcast + 깃발 재시작 + 결과 배너 코스튬
분기 + 점수 watcher) + games/duck-hunt/build.py (라운드 진행 + 코스튬 전환 연출).
물리/이동/클론/리스트 없음. 핵심은 (a) 랜덤 대기 후 신호, (b) timer 로 ms 반응시간
측정, (c) 신호 전 입력 = 부정출발 판정.
"""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "카우보이결투.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: 서부 석양 --------
def _mesas():
    out = []
    # 멀리 붉은 메사(평정 바위) 실루엣 3개. 사막 지평선 위.
    out.append('<path d="M -10 250 L 30 250 L 38 215 L 95 215 L 103 250 L 150 250 Z" fill="#5C2A20" opacity="0.85"/>')
    out.append('<path d="M 300 250 L 330 250 L 336 222 L 392 222 L 398 250 L 440 250 Z" fill="#6B3324" opacity="0.8"/>')
    out.append('<path d="M 200 250 L 222 250 L 226 232 L 268 232 L 272 250 L 300 250 Z" fill="#4A211A" opacity="0.75"/>')
    return "\n  ".join(out)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FF7A18"/>
      <stop offset="0.35" stop-color="#FF5A2C"/>
      <stop offset="0.7" stop-color="#C13B2E"/>
      <stop offset="1" stop-color="#7E2A33"/>
    </linearGradient>
    <radialGradient id="sun" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#FFF3B0"/>
      <stop offset="0.55" stop-color="#FFD24A"/>
      <stop offset="1" stop-color="#FFB02E" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#A9622F"/>
      <stop offset="1" stop-color="#5E3318"/>
    </linearGradient>
  </defs>
  <!-- 하늘 -->
  <rect x="0" y="0" width="480" height="252" fill="url(#sky)"/>
  <!-- 태양 글로우 + 본체 (중앙 약간 위) -->
  <circle cx="240" cy="150" r="150" fill="url(#sun)"/>
  <circle cx="240" cy="150" r="62" fill="#FFE066"/>
  <circle cx="240" cy="150" r="62" fill="#FFCF3F" opacity="0.55"/>
  <!-- 가로 띠(석양 느낌) -->
  <rect x="0" y="138" width="480" height="6" fill="#C13B2E" opacity="0.35"/>
  <rect x="0" y="170" width="480" height="6" fill="#C13B2E" opacity="0.3"/>
  <!-- 메사 실루엣 -->
  {_mesas()}
  <!-- 사막 대지 -->
  <rect x="0" y="250" width="480" height="110" fill="url(#ground)"/>
  <ellipse cx="240" cy="252" rx="300" ry="14" fill="#C97A3C" opacity="0.5"/>
  <!-- 대지 잔결 -->
  <rect x="0" y="300" width="480" height="3" fill="#4A2912" opacity="0.4"/>
  <rect x="40" y="330" width="120" height="3" fill="#4A2912" opacity="0.35"/>
  <rect x="300" y="320" width="140" height="3" fill="#4A2912" opacity="0.35"/>
  <!-- 회전초(tumbleweed) 실루엣 -->
  <g transform="translate(95 312)" opacity="0.7">
    <circle cx="0" cy="0" r="13" fill="none" stroke="#3A2410" stroke-width="2.5"/>
    <path d="M -13 0 L 13 0 M 0 -13 L 0 13 M -9 -9 L 9 9 M -9 9 L 9 -9" stroke="#3A2410" stroke-width="1.6"/>
  </g>
</svg>"""

# ---- 카우보이 코스튬 캔버스: 80x130, rotationCenter (40,65) 공통 ----
# 플레이어: 갈색 모자/조끼, 오른쪽(상대)을 바라봄(얼굴이 오른쪽)
# AI: 검은 모자/조끼, 왼쪽(플레이어)을 바라봄(얼굴이 왼쪽)

def _cowboy(hat, vest, skin, shirt, facing):
    """facing: +1 = 오른쪽을 봄(플레이어), -1 = 왼쪽을 봄(AI). 대기 자세."""
    fx = 1 if facing > 0 else -1
    # 얼굴(코) 방향 표시용 작은 오프셋
    nose = 50 if fx > 0 else 30
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="80" height="130" viewBox="0 0 80 130">
  <!-- 그림자 -->
  <ellipse cx="40" cy="124" rx="26" ry="6" fill="#000000" opacity="0.25"/>
  <!-- 다리 -->
  <rect x="30" y="86" width="9" height="34" rx="3" fill="{shirt}"/>
  <rect x="41" y="86" width="9" height="34" rx="3" fill="{shirt}"/>
  <!-- 부츠 -->
  <rect x="27" y="116" width="14" height="8" rx="2" fill="#3A2410"/>
  <rect x="39" y="116" width="14" height="8" rx="2" fill="#3A2410"/>
  <!-- 몸통/조끼 -->
  <rect x="27" y="52" width="26" height="38" rx="6" fill="{shirt}"/>
  <rect x="28" y="52" width="24" height="36" rx="6" fill="{vest}"/>
  <!-- 벨트 -->
  <rect x="27" y="84" width="26" height="6" fill="#5C3A1A"/>
  <rect x="37" y="84" width="6" height="6" fill="#FFD24A"/>
  <!-- 권총 홀스터(대기시 총 꽂힘) -->
  <rect x="{'50' if fx>0 else '24'}" y="86" width="7" height="14" rx="2" fill="#2A1A0E"/>
  <!-- 팔(옆에 내림) -->
  <rect x="{'50' if fx>0 else '23'}" y="56" width="8" height="30" rx="4" fill="{vest}"/>
  <!-- 손 -->
  <circle cx="{'54' if fx>0 else '27'}" cy="88" r="5" fill="{skin}"/>
  <!-- 목 -->
  <rect x="35" y="44" width="10" height="10" fill="{skin}"/>
  <!-- 머리 -->
  <circle cx="40" cy="36" r="13" fill="{skin}"/>
  <!-- 코(바라보는 방향) -->
  <circle cx="{nose}" cy="37" r="2.5" fill="{skin}"/>
  <!-- 눈 -->
  <circle cx="{'44' if fx>0 else '36'}" cy="34" r="1.8" fill="#222"/>
  <!-- 모자 -->
  <ellipse cx="40" cy="26" rx="22" ry="5" fill="{hat}"/>
  <rect x="28" y="14" width="24" height="13" rx="5" fill="{hat}"/>
  <rect x="28" y="22" width="24" height="3" fill="#000000" opacity="0.25"/>
  <!-- 스카프 -->
  <path d="M 30 50 L 50 50 L 40 60 Z" fill="#C0392B"/>
</svg>"""

def _cowboy_shoot(hat, vest, skin, shirt, facing):
    """사격 자세: 권총 든 팔 뻗음 + 총구 섬광."""
    fx = 1 if facing > 0 else -1
    if fx > 0:
        arm = '<rect x="50" y="60" width="26" height="8" rx="4" fill="%s"/>' % vest
        gun = '<rect x="70" y="58" width="12" height="6" rx="1" fill="#2A1A0E"/><rect x="69" y="63" width="4" height="6" fill="#2A1A0E"/>'
        flash = '<g transform="translate(84 61)"><path d="M 0 0 L 12 -7 L 7 0 L 13 6 L 0 3 Z" fill="#FFE066"/><path d="M 0 0 L 9 -3 L 6 0 L 9 4 Z" fill="#FF9E2C"/></g>'
        nose = 50
        eye = 44
    else:
        arm = '<rect x="4" y="60" width="26" height="8" rx="4" fill="%s"/>' % vest
        gun = '<rect x="-2" y="58" width="12" height="6" rx="1" fill="#2A1A0E"/><rect x="7" y="63" width="4" height="6" fill="#2A1A0E"/>'
        flash = '<g transform="translate(-4 61)"><path d="M 0 0 L -12 -7 L -7 0 L -13 6 L 0 3 Z" fill="#FFE066"/><path d="M 0 0 L -9 -3 L -6 0 L -9 4 Z" fill="#FF9E2C"/></g>'
        nose = 30
        eye = 36
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="80" height="130" viewBox="0 0 80 130">
  <ellipse cx="40" cy="124" rx="26" ry="6" fill="#000000" opacity="0.25"/>
  <rect x="30" y="86" width="9" height="34" rx="3" fill="{shirt}"/>
  <rect x="41" y="86" width="9" height="34" rx="3" fill="{shirt}"/>
  <rect x="27" y="116" width="14" height="8" rx="2" fill="#3A2410"/>
  <rect x="39" y="116" width="14" height="8" rx="2" fill="#3A2410"/>
  <rect x="27" y="52" width="26" height="38" rx="6" fill="{shirt}"/>
  <rect x="28" y="52" width="24" height="36" rx="6" fill="{vest}"/>
  <rect x="27" y="84" width="26" height="6" fill="#5C3A1A"/>
  <rect x="37" y="84" width="6" height="6" fill="#FFD24A"/>
  <!-- 뻗은 팔 + 권총 + 섬광 -->
  {arm}
  {gun}
  {flash}
  <circle cx="{'76' if fx>0 else '4'}" cy="64" r="5" fill="{skin}"/>
  <rect x="35" y="44" width="10" height="10" fill="{skin}"/>
  <circle cx="40" cy="36" r="13" fill="{skin}"/>
  <circle cx="{nose}" cy="37" r="2.5" fill="{skin}"/>
  <circle cx="{eye}" cy="34" r="1.8" fill="#222"/>
  <ellipse cx="40" cy="26" rx="22" ry="5" fill="{hat}"/>
  <rect x="28" y="14" width="24" height="13" rx="5" fill="{hat}"/>
  <rect x="28" y="22" width="24" height="3" fill="#000000" opacity="0.25"/>
  <path d="M 30 50 L 50 50 L 40 60 Z" fill="#C0392B"/>
</svg>"""

def _cowboy_down(hat, vest, skin, shirt):
    """쓰러짐: 누운 자세, 눈 X, 모자 떨어짐."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="80" height="130" viewBox="0 0 80 130">
  <ellipse cx="40" cy="120" rx="34" ry="8" fill="#000000" opacity="0.3"/>
  <!-- 누운 몸통 -->
  <rect x="14" y="98" width="44" height="20" rx="9" fill="{shirt}"/>
  <rect x="16" y="100" width="40" height="16" rx="8" fill="{vest}"/>
  <!-- 다리(뻗음) -->
  <rect x="54" y="102" width="22" height="8" rx="4" fill="{shirt}"/>
  <rect x="72" y="100" width="8" height="6" rx="2" fill="#3A2410"/>
  <!-- 팔(늘어짐) -->
  <rect x="22" y="112" width="20" height="7" rx="3" fill="{vest}"/>
  <!-- 머리 -->
  <circle cx="16" cy="100" r="12" fill="{skin}"/>
  <!-- 눈 X X -->
  <path d="M 10 96 L 15 101 M 15 96 L 10 101" stroke="#222" stroke-width="1.8"/>
  <path d="M 18 96 L 23 101 M 23 96 L 18 101" stroke="#222" stroke-width="1.8"/>
  <!-- 입(찡그림) -->
  <path d="M 11 106 Q 16 103 21 106" stroke="#7E2A33" stroke-width="1.6" fill="none"/>
  <!-- 떨어진 모자 -->
  <g transform="translate(40 70) rotate(20)">
    <ellipse cx="0" cy="6" rx="18" ry="4" fill="{hat}"/>
    <rect x="-10" y="-4" width="20" height="11" rx="4" fill="{hat}"/>
  </g>
</svg>"""

# 플레이어(왼쪽, 오른쪽을 봄): 갈색 모자/황갈 조끼
P_HAT, P_VEST, P_SKIN, P_SHIRT = "#8B5A2B", "#C8862E", "#F2C49B", "#E8E0D0"
# AI(오른쪽, 왼쪽을 봄): 검은 모자/조끼
A_HAT, A_VEST, A_SKIN, A_SHIRT = "#2B2B2B", "#444444", "#E6B58A", "#C9C2B6"

P_READY_SVG = _cowboy(P_HAT, P_VEST, P_SKIN, P_SHIRT, +1)
P_SHOOT_SVG = _cowboy_shoot(P_HAT, P_VEST, P_SKIN, P_SHIRT, +1)
P_DOWN_SVG  = _cowboy_down(P_HAT, P_VEST, P_SKIN, P_SHIRT)
A_READY_SVG = _cowboy(A_HAT, A_VEST, A_SKIN, A_SHIRT, -1)
A_SHOOT_SVG = _cowboy_shoot(A_HAT, A_VEST, A_SKIN, A_SHIRT, -1)
A_DOWN_SVG  = _cowboy_down(A_HAT, A_VEST, A_SKIN, A_SHIRT)

# -------- DRAW배너: ready("준비...") --------
READY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="240" height="90" viewBox="0 0 240 90">
  <rect x="20" y="22" width="200" height="46" rx="12" fill="#2A1A0E" opacity="0.55"/>
  <text x="120" y="56" text-anchor="middle"
        fill="#F2E4C8" font-family="Arial, Helvetica, sans-serif"
        font-size="30" font-weight="bold">준비...</text>
</svg>"""

# -------- DRAW배너: draw("DRAW!") 큰 굵은 글자 --------
DRAW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="280" height="120" viewBox="0 0 280 120">
  <rect x="8" y="14" width="264" height="92" rx="16" fill="#7E0010" opacity="0.92" stroke="#FFE066" stroke-width="5"/>
  <text x="140" y="84" text-anchor="middle"
        fill="#FFE066" stroke="#3A0008" stroke-width="2"
        font-family="Arial Black, Arial, sans-serif"
        font-size="62" font-weight="900">DRAW!</text>
</svg>"""

# -------- 결과배너 코스튬: 공통 헬퍼 --------
def _banner(border, big_color, big_text, sub_color, sub_text, hint=True):
    hint_line = ('<text x="180" y="142" text-anchor="middle" fill="#81D4FA" '
                 'font-family="Arial, Helvetica, sans-serif" font-size="13">'
                 '초록 깃발(▶) 다시 클릭으로 재시작</text>') if hint else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="5" y="5" width="350" height="160" rx="14" fill="#3A1F14" opacity="0.95" stroke="{border}" stroke-width="4"/>
  <text x="180" y="78" text-anchor="middle" fill="{big_color}"
        font-family="Arial Black, Arial, sans-serif" font-size="46" font-weight="900">{big_text}</text>
  <text x="180" y="114" text-anchor="middle" fill="{sub_color}"
        font-family="Arial, Helvetica, sans-serif" font-size="20">{sub_text}</text>
  {hint_line}
</svg>"""

WIN_SVG     = _banner("#43A047", "#66BB6A", "YOU WIN!", "#FFFFFF", "더 빨랐다!", hint=False)
LOSE_SVG    = _banner("#E53935", "#EF5350", "YOU LOSE", "#FFFFFF", "AI 가 더 빨랐다", hint=False)
FOUL_SVG    = _banner("#FB8C00", "#FFB300", "FOUL!", "#FFE0B2", "너무 빨라요! 반칙!", hint=False)
VICTORY_SVG = _banner("#FFC107", "#FFD54F", "VICTORY!", "#FFF8E1", "최종 승리!", hint=True)
DEFEAT_SVG  = _banner("#9E9E9E", "#EF5350", "DEFEAT", "#E0E0E0", "다음 기회에...", hint=True)

# ============================================================
#  helpers (pong/duck-hunt 와 동일)
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

# play sound 헬퍼
def play_sound(bs, name):
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU":[name, None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1, snm]})
    bs[snm]["parent"] = snd
    return snd

# set pitch effect 헬퍼
def set_pitch(bs, val):
    bid = gen(); bs[bid] = mk("sound_seteffectto",
        inputs={"VALUE": num(val)}, fields={"EFFECT": ["PITCH", None]})
    return bid

# broadcast 헬퍼
def broadcast(bs, name, bid):
    bm = gen(); bs[bm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, bid]}, shadow=True)
    bc = gen(); bs[bc] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm]})
    bs[bm]["parent"] = bc
    return bc

# key pressed 헬퍼 (boolean reporter id 반환)
def key_pressed(bs, key="space"):
    km = gen(); bs[km] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": [key, None]}, shadow=True)
    kp = gen(); bs[kp] = mk("sensing_keypressed", inputs={"KEY_OPTION":[1, km]})
    bs[km]["parent"] = kp
    return kp

def timer(bs):
    bid = gen(); bs[bid] = mk("sensing_timer")
    return bid

# switch costume 헬퍼
def switch_costume(bs, name):
    cm = gen(); bs[cm] = mk("looks_costume",
        fields={"COSTUME":[name, None]}, shadow=True)
    sc = gen(); bs[sc] = mk("looks_switchcostumeto", inputs={"COSTUME":[1, cm]})
    bs[cm]["parent"] = sc
    return sc

# ============================================================
#  IDs
# ============================================================
V_STATE   = "varState01"    # 게임상태 1=진행 0=종료
V_PWINS   = "varPWins02"    # 내승
V_AWINS   = "varAWins03"    # AI승
V_TARGET  = "varTarget04"   # 목표승
V_ROUND   = "varRound05"    # 라운드
V_RSTATUS = "varRStatus06"  # 라운드상태 0/1/2
V_AIRT    = "varAIRT07"     # AI반응(초)
V_PRT     = "varPRT08"      # 내반응ms
V_BEST    = "varBest09"     # 베스트ms
V_RRESULT = "varRResult10"  # 라운드결과 0/1/2/3
V_FINAL   = "varFinal11"    # 최종결과 0/1/2
V_SIGT    = "varSigT12"     # 신호시각
V_WAIT    = "varWait13"     # 대기시간(랜덤 1회 저장)

BR_START      = "brStart01"       # 게임시작
BR_ROUNDSTART = "brRoundStart02"  # 라운드시작
BR_DRAW       = "brDraw03"        # 신호
BR_ROUNDEND   = "brRoundEnd04"    # 라운드끝
BR_FINAL      = "brFinal05"       # 최종결과

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
    setv("게임상태", V_STATE, 1)
    setv("내승", V_PWINS, 0)
    setv("AI승", V_AWINS, 0)
    setv("목표승", V_TARGET, 3)
    setv("라운드", V_ROUND, 1)
    setv("라운드상태", V_RSTATUS, 0)
    setv("베스트ms", V_BEST, 9999)
    setv("내반응ms", V_PRT, 0)
    setv("최종결과", V_FINAL, 0)
    bc_start = broadcast(bs, "게임시작", BR_START)
    inits.append((bc_start, bs[bc_start]))
    bc_rstart = broadcast(bs, "라운드시작", BR_ROUNDSTART)
    inits.append((bc_rstart, bs[bc_rstart]))
    chain(inits)

    # === when receive 라운드시작: 메인 대결 스크립트 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUNDSTART]})

    set_rs0 = gen(); bs[set_rs0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["라운드상태", V_RSTATUS]})
    set_rr0 = gen(); bs[set_rr0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["라운드결과", V_RRESULT]})
    set_prt0 = gen(); bs[set_prt0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["내반응ms", V_PRT]})

    # AI반응 ← (random 0.45 to 0.70) - (라운드-1)*0.05
    rnd = gen(); bs[rnd] = mk("operator_random",
        inputs={"FROM": num(0.45), "TO": num(0.70)})
    round_v = vrep("라운드", V_ROUND)
    rminus1 = op("operator_subtract", round_v, 1)
    scaled = op("operator_multiply", rminus1, 0.05)
    airt_expr = op("operator_subtract", rnd, scaled)
    set_airt = gen(); bs[set_airt] = mk("data_setvariableto",
        inputs={"VALUE": slot(airt_expr)}, fields={"VARIABLE": ["AI반응", V_AIRT]})
    bs[airt_expr]["parent"] = set_airt

    # if AI반응 < 0.28 → AI반응 = 0.28
    airt_v1 = vrep("AI반응", V_AIRT)
    cond_lo = cmp_op("operator_lt", airt_v1, 0.28)
    set_airt_min = gen(); bs[set_airt_min] = mk("data_setvariableto",
        inputs={"VALUE": num(0.28)}, fields={"VARIABLE": ["AI반응", V_AIRT]})
    if_clamp = gen(); bs[if_clamp] = mk("control_if",
        inputs={"CONDITION":[2,cond_lo], "SUBSTACK":[2,set_airt_min]})
    bs[cond_lo]["parent"] = if_clamp
    bs[set_airt_min]["parent"] = if_clamp

    # 대기시간 ← random 1.5 to 4.0
    rnd_w = gen(); bs[rnd_w] = mk("operator_random",
        inputs={"FROM": num(1.5), "TO": num(4.0)})
    set_wait = gen(); bs[set_wait] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_w)}, fields={"VARIABLE": ["대기시간", V_WAIT]})
    bs[rnd_w]["parent"] = set_wait

    # reset timer
    rst = gen(); bs[rst] = mk("sensing_resettimer")

    # --- 부정출발 감시 repeat until ((timer >= 대기시간) OR (key space)) ---
    t1 = timer(bs)
    wait_v1 = vrep("대기시간", V_WAIT)
    cond_timeup = cmp_op("operator_gt", t1, wait_v1)   # timer > 대기시간 근사(>=)
    sp1 = key_pressed(bs)
    cond_watch = bool_op("operator_or", cond_timeup, sp1)
    # 빈 루프 본문: wait 0.005
    loop_wait = gen(); bs[loop_wait] = mk("control_wait", inputs={"DURATION": num(0.005)})
    watch_loop = gen(); bs[watch_loop] = mk("control_repeat_until",
        inputs={"CONDITION":[2,cond_watch], "SUBSTACK":[2,loop_wait]})
    bs[cond_watch]["parent"] = watch_loop
    bs[loop_wait]["parent"] = watch_loop

    # if (key space) AND (timer < 대기시간) → 부정출발
    sp2 = key_pressed(bs)
    t2 = timer(bs)
    wait_v2 = vrep("대기시간", V_WAIT)
    cond_early = cmp_op("operator_lt", t2, wait_v2)
    cond_foul = bool_op("operator_and", sp2, cond_early)

    set_rr3 = gen(); bs[set_rr3] = mk("data_setvariableto",
        inputs={"VALUE": num(3)}, fields={"VARIABLE": ["라운드결과", V_RRESULT]})
    set_rs2_foul = gen(); bs[set_rs2_foul] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["라운드상태", V_RSTATUS]})
    bc_end_foul = broadcast(bs, "라운드끝", BR_ROUNDEND)
    stop_foul = gen(); bs[stop_foul] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    chain([(set_rr3,bs[set_rr3]),(set_rs2_foul,bs[set_rs2_foul]),
           (bc_end_foul,bs[bc_end_foul]),(stop_foul,bs[stop_foul])])
    if_foul = gen(); bs[if_foul] = mk("control_if",
        inputs={"CONDITION":[2,cond_foul], "SUBSTACK":[2,set_rr3]})
    bs[cond_foul]["parent"] = if_foul
    bs[set_rr3]["parent"] = if_foul

    # --- 정상: 신호 발신 ---
    t3 = timer(bs)
    set_sigt = gen(); bs[set_sigt] = mk("data_setvariableto",
        inputs={"VALUE": slot(t3)}, fields={"VARIABLE": ["신호시각", V_SIGT]})
    bs[t3]["parent"] = set_sigt
    set_rs1 = gen(); bs[set_rs1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드상태", V_RSTATUS]})
    bc_draw = broadcast(bs, "신호", BR_DRAW)

    # --- 선착 판정: wait until ((key space) OR (timer >= 신호시각+AI반응)) ---
    sp3 = key_pressed(bs)
    t4 = timer(bs)
    sigt_v1 = vrep("신호시각", V_SIGT)
    airt_v2 = vrep("AI반응", V_AIRT)
    deadline = op("operator_add", sigt_v1, airt_v2)
    cond_aifire = cmp_op("operator_gt", t4, deadline)   # timer > 신호+AI반응 근사(>=)
    cond_decide = bool_op("operator_or", sp3, cond_aifire)
    wait_decide = gen(); bs[wait_decide] = mk("control_wait_until",
        inputs={"CONDITION":[2, cond_decide]})
    bs[cond_decide]["parent"] = wait_decide

    # 내반응ms ← round((timer - 신호시각) * 1000)  (양 분기 공통 → if 앞에서 계산)
    t5 = timer(bs)
    sigt_v2 = vrep("신호시각", V_SIGT)
    rt_diff = op("operator_subtract", t5, sigt_v2)
    rt_ms = op("operator_multiply", rt_diff, 1000)
    rt_round = gen(); bs[rt_round] = mk("operator_round", inputs={"NUM": slot(rt_ms)})
    bs[rt_ms]["parent"] = rt_round
    set_prt = gen(); bs[set_prt] = mk("data_setvariableto",
        inputs={"VALUE": slot(rt_round)}, fields={"VARIABLE": ["내반응ms", V_PRT]})
    bs[rt_round]["parent"] = set_prt

    # if (key space) AND ((timer - 신호시각) < AI반응) → 결과1 else 결과2
    sp4 = key_pressed(bs)
    t6 = timer(bs)
    sigt_v3 = vrep("신호시각", V_SIGT)
    rt_diff2 = op("operator_subtract", t6, sigt_v3)
    airt_v3 = vrep("AI반응", V_AIRT)
    cond_faster = cmp_op("operator_lt", rt_diff2, airt_v3)
    cond_pwin = bool_op("operator_and", sp4, cond_faster)
    set_rr1 = gen(); bs[set_rr1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드결과", V_RRESULT]})
    set_rr2 = gen(); bs[set_rr2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["라운드결과", V_RRESULT]})
    if_decide = gen(); bs[if_decide] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_pwin], "SUBSTACK":[2,set_rr1],
                "SUBSTACK2":[2,set_rr2]})
    bs[cond_pwin]["parent"] = if_decide
    bs[set_rr1]["parent"] = if_decide
    bs[set_rr2]["parent"] = if_decide

    set_rs2_end = gen(); bs[set_rs2_end] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["라운드상태", V_RSTATUS]})
    bc_end = broadcast(bs, "라운드끝", BR_ROUNDEND)

    chain([(h2,bs[h2]),(set_rs0,bs[set_rs0]),(set_rr0,bs[set_rr0]),(set_prt0,bs[set_prt0]),
           (set_airt,bs[set_airt]),(if_clamp,bs[if_clamp]),(set_wait,bs[set_wait]),
           (rst,bs[rst]),(watch_loop,bs[watch_loop]),(if_foul,bs[if_foul]),
           (set_sigt,bs[set_sigt]),(set_rs1,bs[set_rs1]),(bc_draw,bs[bc_draw]),
           (wait_decide,bs[wait_decide]),(set_prt,bs[set_prt]),(if_decide,bs[if_decide]),
           (set_rs2_end,bs[set_rs2_end]),(bc_end,bs[bc_end])])

    # === when receive 라운드끝: 점수/베스트/최종판정 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=700,
        fields={"BROADCAST_OPTION": ["라운드끝", BR_ROUNDEND]})

    # if 라운드결과=1 → 내승+1
    rr_v1 = vrep("라운드결과", V_RRESULT)
    cond_r1 = cmp_op("operator_equals", rr_v1, 1)
    inc_pw = gen(); bs[inc_pw] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["내승", V_PWINS]})
    if_r1 = gen(); bs[if_r1] = mk("control_if",
        inputs={"CONDITION":[2,cond_r1], "SUBSTACK":[2,inc_pw]})
    bs[cond_r1]["parent"] = if_r1
    bs[inc_pw]["parent"] = if_r1

    # if 라운드결과=2 → AI승+1
    rr_v2 = vrep("라운드결과", V_RRESULT)
    cond_r2 = cmp_op("operator_equals", rr_v2, 2)
    inc_aw1 = gen(); bs[inc_aw1] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["AI승", V_AWINS]})
    if_r2 = gen(); bs[if_r2] = mk("control_if",
        inputs={"CONDITION":[2,cond_r2], "SUBSTACK":[2,inc_aw1]})
    bs[cond_r2]["parent"] = if_r2
    bs[inc_aw1]["parent"] = if_r2

    # if 라운드결과=3 → AI승+1
    rr_v3 = vrep("라운드결과", V_RRESULT)
    cond_r3 = cmp_op("operator_equals", rr_v3, 3)
    inc_aw2 = gen(); bs[inc_aw2] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["AI승", V_AWINS]})
    if_r3 = gen(); bs[if_r3] = mk("control_if",
        inputs={"CONDITION":[2,cond_r3], "SUBSTACK":[2,inc_aw2]})
    bs[cond_r3]["parent"] = if_r3
    bs[inc_aw2]["parent"] = if_r3

    # if (라운드결과=1) AND (내반응ms < 베스트ms) → 베스트ms = 내반응ms
    rr_v4 = vrep("라운드결과", V_RRESULT)
    cond_r1b = cmp_op("operator_equals", rr_v4, 1)
    prt_v1 = vrep("내반응ms", V_PRT)
    best_v1 = vrep("베스트ms", V_BEST)
    cond_better = cmp_op("operator_lt", prt_v1, best_v1)
    cond_newbest = bool_op("operator_and", cond_r1b, cond_better)
    prt_v2 = vrep("내반응ms", V_PRT)
    set_best = gen(); bs[set_best] = mk("data_setvariableto",
        inputs={"VALUE": slot(prt_v2)}, fields={"VARIABLE": ["베스트ms", V_BEST]})
    bs[prt_v2]["parent"] = set_best
    if_best = gen(); bs[if_best] = mk("control_if",
        inputs={"CONDITION":[2,cond_newbest], "SUBSTACK":[2,set_best]})
    bs[cond_newbest]["parent"] = if_best
    bs[set_best]["parent"] = if_best

    wait_view = gen(); bs[wait_view] = mk("control_wait", inputs={"DURATION": num(1.6)})

    # if 내승 >= 목표승 → 최종1 + 게임상태0 + broadcast 최종결과 + stop
    pw_v = vrep("내승", V_PWINS)
    tg_v1 = vrep("목표승", V_TARGET)
    pw_gt = cmp_op("operator_gt", pw_v, tg_v1)
    pw_v2 = vrep("내승", V_PWINS)
    tg_v1b = vrep("목표승", V_TARGET)
    pw_eq = cmp_op("operator_equals", pw_v2, tg_v1b)
    cond_pfinal = bool_op("operator_or", pw_gt, pw_eq)
    set_final1 = gen(); bs[set_final1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["최종결과", V_FINAL]})
    set_state0a = gen(); bs[set_state0a] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bc_final1 = broadcast(bs, "최종결과", BR_FINAL)
    stop1 = gen(); bs[stop1] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    chain([(set_final1,bs[set_final1]),(set_state0a,bs[set_state0a]),
           (bc_final1,bs[bc_final1]),(stop1,bs[stop1])])
    if_pfinal = gen(); bs[if_pfinal] = mk("control_if",
        inputs={"CONDITION":[2,cond_pfinal], "SUBSTACK":[2,set_final1]})
    bs[cond_pfinal]["parent"] = if_pfinal
    bs[set_final1]["parent"] = if_pfinal

    # if AI승 >= 목표승 → 최종2 + 게임상태0 + broadcast 최종결과 + stop
    aw_v = vrep("AI승", V_AWINS)
    tg_v2 = vrep("목표승", V_TARGET)
    aw_gt = cmp_op("operator_gt", aw_v, tg_v2)
    aw_v2 = vrep("AI승", V_AWINS)
    tg_v2b = vrep("목표승", V_TARGET)
    aw_eq = cmp_op("operator_equals", aw_v2, tg_v2b)
    cond_afinal = bool_op("operator_or", aw_gt, aw_eq)
    set_final2 = gen(); bs[set_final2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["최종결과", V_FINAL]})
    set_state0b = gen(); bs[set_state0b] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    bc_final2 = broadcast(bs, "최종결과", BR_FINAL)
    stop2 = gen(); bs[stop2] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]}, inputs={})
    chain([(set_final2,bs[set_final2]),(set_state0b,bs[set_state0b]),
           (bc_final2,bs[bc_final2]),(stop2,bs[stop2])])
    if_afinal = gen(); bs[if_afinal] = mk("control_if",
        inputs={"CONDITION":[2,cond_afinal], "SUBSTACK":[2,set_final2]})
    bs[cond_afinal]["parent"] = if_afinal
    bs[set_final2]["parent"] = if_afinal

    # 라운드+1, wait 0.4, broadcast 라운드시작
    inc_round = gen(); bs[inc_round] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
    wait_next = gen(); bs[wait_next] = mk("control_wait", inputs={"DURATION": num(0.4)})
    bc_next = broadcast(bs, "라운드시작", BR_ROUNDSTART)

    chain([(h3,bs[h3]),(if_r1,bs[if_r1]),(if_r2,bs[if_r2]),(if_r3,bs[if_r3]),
           (if_best,bs[if_best]),(wait_view,bs[wait_view]),(if_pfinal,bs[if_pfinal]),
           (if_afinal,bs[if_afinal]),(inc_round,bs[inc_round]),(wait_next,bs[wait_next]),
           (bc_next,bs[bc_next])])

    return bs

# ============================================================
#  플레이어 카우보이 (왼쪽) blocks
# ============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked: 위치/방향/대기코스튬/show ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-150), "Y": num(-40)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    cm = switch_costume(bs, "p_ready")
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(pdir,bs[pdir]),(sz,bs[sz]),(cm,bs[cm]),(sh,bs[sh])])

    # === when receive 라운드시작: 대기코스튬 리셋 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUNDSTART]})
    cm2 = switch_costume(bs, "p_ready")
    chain([(h2,bs[h2]),(cm2,bs[cm2])])

    # === when receive 신호: 스페이스 누르면 사격 포즈(연출) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["신호", BR_DRAW]})
    # wait until (key space) OR (라운드상태=2)
    sp = key_pressed(bs)
    rs_v = vrep("라운드상태", V_RSTATUS)
    cond_rs2 = cmp_op("operator_equals", rs_v, 2)
    cond_wait = bool_op("operator_or", sp, cond_rs2)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION":[2, cond_wait]})
    bs[cond_wait]["parent"] = wu
    # if 라운드상태=1 → 사격
    rs_v2 = vrep("라운드상태", V_RSTATUS)
    cond_rs1 = cmp_op("operator_equals", rs_v2, 1)
    pitch = set_pitch(bs, 0)
    snd = play_sound(bs, "shot")
    cm3 = switch_costume(bs, "p_shoot")
    chain([(cm3,bs[cm3]),(pitch,bs[pitch]),(snd,bs[snd])])
    if_shoot = gen(); bs[if_shoot] = mk("control_if",
        inputs={"CONDITION":[2,cond_rs1], "SUBSTACK":[2,cm3]})
    bs[cond_rs1]["parent"] = if_shoot
    bs[cm3]["parent"] = if_shoot
    chain([(h3,bs[h3]),(wu,bs[wu]),(if_shoot,bs[if_shoot])])

    # === when receive 라운드끝: 결과 코스튬 ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=20, y=460,
        fields={"BROADCAST_OPTION": ["라운드끝", BR_ROUNDEND]})
    rr_v = vrep("라운드결과", V_RRESULT)
    cond_win = cmp_op("operator_equals", rr_v, 1)
    cm_shoot = switch_costume(bs, "p_shoot")
    cm_down = switch_costume(bs, "p_down")
    if_else = gen(); bs[if_else] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_win], "SUBSTACK":[2,cm_shoot],
                "SUBSTACK2":[2,cm_down]})
    bs[cond_win]["parent"] = if_else
    bs[cm_shoot]["parent"] = if_else
    bs[cm_down]["parent"] = if_else
    chain([(h4,bs[h4]),(if_else,bs[if_else])])

    return bs

# ============================================================
#  AI 카우보이 (오른쪽) blocks
# ============================================================
def build_ai_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(150), "Y": num(-40)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    cm = switch_costume(bs, "a_ready")
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h,bs[h]),(g,bs[g]),(pdir,bs[pdir]),(sz,bs[sz]),(cm,bs[cm]),(sh,bs[sh])])

    # === when receive 라운드시작 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUNDSTART]})
    cm2 = switch_costume(bs, "a_ready")
    chain([(h2,bs[h2]),(cm2,bs[cm2])])

    # === when receive 신호: wait AI반응 후 사격(연출) ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["신호", BR_DRAW]})
    airt_v = vrep("AI반응", V_AIRT)
    wait_ai = gen(); bs[wait_ai] = mk("control_wait", inputs={"DURATION": slot(airt_v)})
    bs[airt_v]["parent"] = wait_ai
    # if 라운드상태=1 → 사격
    rs_v = vrep("라운드상태", V_RSTATUS)
    cond_rs1 = cmp_op("operator_equals", rs_v, 1)
    pitch = set_pitch(bs, 0)
    snd = play_sound(bs, "shot")
    cm3 = switch_costume(bs, "a_shoot")
    chain([(cm3,bs[cm3]),(pitch,bs[pitch]),(snd,bs[snd])])
    if_shoot = gen(); bs[if_shoot] = mk("control_if",
        inputs={"CONDITION":[2,cond_rs1], "SUBSTACK":[2,cm3]})
    bs[cond_rs1]["parent"] = if_shoot
    bs[cm3]["parent"] = if_shoot
    chain([(h3,bs[h3]),(wait_ai,bs[wait_ai]),(if_shoot,bs[if_shoot])])

    # === when receive 라운드끝: 결과 코스튬 ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=20, y=460,
        fields={"BROADCAST_OPTION": ["라운드끝", BR_ROUNDEND]})
    rr_v = vrep("라운드결과", V_RRESULT)
    cond_pwin = cmp_op("operator_equals", rr_v, 1)  # 플레이어 승 → AI 쓰러짐
    cm_down = switch_costume(bs, "a_down")
    cm_shoot = switch_costume(bs, "a_shoot")  # AI승(2)/부정출발(3) → AI 멀쩡/사격
    if_else = gen(); bs[if_else] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_pwin], "SUBSTACK":[2,cm_down],
                "SUBSTACK2":[2,cm_shoot]})
    bs[cond_pwin]["parent"] = if_else
    bs[cm_down]["parent"] = if_else
    bs[cm_shoot]["parent"] = if_else
    chain([(h4,bs[h4]),(if_else,bs[if_else])])

    return bs

# ============================================================
#  DRAW배너 blocks
# ============================================================
def build_drawbanner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(60)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(g,bs[g]),(sz,bs[sz]),(hi,bs[hi])])

    # === when receive 라운드시작: ready show ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["라운드시작", BR_ROUNDSTART]})
    cm_ready = switch_costume(bs, "ready")
    sz2 = gen(); bs[sz2] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h2,bs[h2]),(cm_ready,bs[cm_ready]),(sz2,bs[sz2]),(sh,bs[sh])])

    # === when receive 신호: draw 코스튬 + 번쩍 + 끝나면 숨김 ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["신호", BR_DRAW]})
    cm_draw = switch_costume(bs, "draw")
    sh3 = gen(); bs[sh3] = mk("looks_show")
    # repeat 3 { set size 130; wait 0.06; set size 100; wait 0.06 }
    sz_big = gen(); bs[sz_big] = mk("looks_setsizeto", inputs={"SIZE": num(130)})
    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(0.06)})
    sz_sm = gen(); bs[sz_sm] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    w2 = gen(); bs[w2] = mk("control_wait", inputs={"DURATION": num(0.06)})
    chain([(sz_big,bs[sz_big]),(w1,bs[w1]),(sz_sm,bs[sz_sm]),(w2,bs[w2])])
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(3), "SUBSTACK":[2, sz_big]})
    bs[sz_big]["parent"] = rep
    # wait until 라운드상태=2 → hide
    rs_v = vrep("라운드상태", V_RSTATUS)
    cond_rs2 = cmp_op("operator_equals", rs_v, 2)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION":[2, cond_rs2]})
    bs[cond_rs2]["parent"] = wu
    hi3 = gen(); bs[hi3] = mk("looks_hide")
    chain([(h3,bs[h3]),(cm_draw,bs[cm_draw]),(sh3,bs[sh3]),(rep,bs[rep]),
           (wu,bs[wu]),(hi3,bs[hi3])])

    # === when receive 라운드끝: hide ===
    h4 = gen(); bs[h4] = mk("event_whenbroadcastreceived", top=True, x=20, y=520,
        fields={"BROADCAST_OPTION": ["라운드끝", BR_ROUNDEND]})
    hi4 = gen(); bs[hi4] = mk("looks_hide")
    chain([(h4,bs[h4]),(hi4,bs[hi4])])

    return bs

# ============================================================
#  결과배너 blocks
# ============================================================
def build_banner_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # === when flag clicked ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h,bs[h]),(g,bs[g]),(front,bs[front]),(sz,bs[sz]),(hi,bs[hi])])

    # === when receive 라운드끝: 결과 코스튬 + 사운드 ===
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["라운드끝", BR_ROUNDEND]})
    # if 결과=1 → win
    rr_v1 = vrep("라운드결과", V_RRESULT)
    cond_1 = cmp_op("operator_equals", rr_v1, 1)
    cm_win = switch_costume(bs, "win")
    if_1 = gen(); bs[if_1] = mk("control_if",
        inputs={"CONDITION":[2,cond_1], "SUBSTACK":[2,cm_win]})
    bs[cond_1]["parent"] = if_1
    bs[cm_win]["parent"] = if_1
    # if 결과=2 → lose
    rr_v2 = vrep("라운드결과", V_RRESULT)
    cond_2 = cmp_op("operator_equals", rr_v2, 2)
    cm_lose = switch_costume(bs, "lose")
    if_2 = gen(); bs[if_2] = mk("control_if",
        inputs={"CONDITION":[2,cond_2], "SUBSTACK":[2,cm_lose]})
    bs[cond_2]["parent"] = if_2
    bs[cm_lose]["parent"] = if_2
    # if 결과=3 → foul
    rr_v3 = vrep("라운드결과", V_RRESULT)
    cond_3 = cmp_op("operator_equals", rr_v3, 3)
    cm_foul = switch_costume(bs, "foul")
    if_3 = gen(); bs[if_3] = mk("control_if",
        inputs={"CONDITION":[2,cond_3], "SUBSTACK":[2,cm_foul]})
    bs[cond_3]["parent"] = if_3
    bs[cm_foul]["parent"] = if_3
    # front + show
    front2 = gen(); bs[front2] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    # if 결과=1 → 사운드 pitch 200(win 높음) else pitch -300(lose/foul)
    rr_v4 = vrep("라운드결과", V_RRESULT)
    cond_win_snd = cmp_op("operator_equals", rr_v4, 1)
    pitch_win = set_pitch(bs, 200)
    snd_win = play_sound(bs, "shot")
    pitch_lose = set_pitch(bs, -300)
    snd_lose = play_sound(bs, "shot")
    chain([(pitch_win,bs[pitch_win]),(snd_win,bs[snd_win])])
    chain([(pitch_lose,bs[pitch_lose]),(snd_lose,bs[snd_lose])])
    if_snd = gen(); bs[if_snd] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_win_snd], "SUBSTACK":[2,pitch_win],
                "SUBSTACK2":[2,pitch_lose]})
    bs[cond_win_snd]["parent"] = if_snd
    bs[pitch_win]["parent"] = if_snd
    bs[pitch_lose]["parent"] = if_snd
    # wait 1.4 → hide
    w14 = gen(); bs[w14] = mk("control_wait", inputs={"DURATION": num(1.4)})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(h2,bs[h2]),(if_1,bs[if_1]),(if_2,bs[if_2]),(if_3,bs[if_3]),
           (front2,bs[front2]),(show,bs[show]),(if_snd,bs[if_snd]),
           (w14,bs[w14]),(hi2,bs[hi2])])

    # === when receive 최종결과: victory/defeat ===
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=520,
        fields={"BROADCAST_OPTION": ["최종결과", BR_FINAL]})
    fin_v = vrep("최종결과", V_FINAL)
    cond_vic = cmp_op("operator_equals", fin_v, 1)
    cm_vic = switch_costume(bs, "victory")
    cm_def = switch_costume(bs, "defeat")
    if_fin = gen(); bs[if_fin] = mk("control_if_else",
        inputs={"CONDITION":[2,cond_vic], "SUBSTACK":[2,cm_vic],
                "SUBSTACK2":[2,cm_def]})
    bs[cond_vic]["parent"] = if_fin
    bs[cm_vic]["parent"] = if_fin
    bs[cm_def]["parent"] = if_fin
    front3 = gen(); bs[front3] = mk("looks_gotofrontback",
        fields={"FRONT_BACK":["front", None]})
    show2 = gen(); bs[show2] = mk("looks_show")
    chain([(h3,bs[h3]),(if_fin,bs[if_fin]),(front3,bs[front3]),(show2,bs[show2])])

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
    pready_md5 = write_svg(P_READY_SVG)
    pshoot_md5 = write_svg(P_SHOOT_SVG)
    pdown_md5  = write_svg(P_DOWN_SVG)
    aready_md5 = write_svg(A_READY_SVG)
    ashoot_md5 = write_svg(A_SHOOT_SVG)
    adown_md5  = write_svg(A_DOWN_SVG)
    ready_md5  = write_svg(READY_SVG)
    draw_md5   = write_svg(DRAW_SVG)
    win_md5    = write_svg(WIN_SVG)
    lose_md5   = write_svg(LOSE_SVG)
    foul_md5   = write_svg(FOUL_SVG)
    vic_md5    = write_svg(VICTORY_SVG)
    def_md5    = write_svg(DEFEAT_SVG)

    with open(f"{ASSETS}/shot.wav", "rb") as f: shot_bytes = f.read()
    shot_md5 = md5_bytes(shot_bytes)
    with open(f"{WORK}/{shot_md5}.wav", "wb") as f: f.write(shot_bytes)

    def shot_sound():
        return {"name": "shot", "assetId": shot_md5, "dataFormat": "wav",
                "format": "", "rate": 11025, "sampleCount": 258,
                "md5ext": f"{shot_md5}.wav"}

    stage_blocks  = build_stage_blocks()
    player_blocks = build_player_blocks()
    ai_blocks     = build_ai_blocks()
    draw_blocks   = build_drawbanner_blocks()
    banner_blocks = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_STATE:   ["게임상태", 1],
            V_PWINS:   ["내승", 0],
            V_AWINS:   ["AI승", 0],
            V_TARGET:  ["목표승", 3],
            V_ROUND:   ["라운드", 1],
            V_RSTATUS: ["라운드상태", 0],
            V_AIRT:    ["AI반응", 0.5],
            V_PRT:     ["내반응ms", 0],
            V_BEST:    ["베스트ms", 9999],
            V_RRESULT: ["라운드결과", 0],
            V_FINAL:   ["최종결과", 0],
            V_SIGT:    ["신호시각", 0],
            V_WAIT:    ["대기시간", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작", BR_ROUNDSTART: "라운드시작",
            BR_DRAW: "신호", BR_ROUNDEND: "라운드끝", BR_FINAL: "최종결과",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bg", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [shot_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    player = {
        "isStage": False, "name": "플레이어",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": player_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "p_ready", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pready_md5, "md5ext": f"{pready_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 65},
            {"name": "p_shoot", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pshoot_md5, "md5ext": f"{pshoot_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 65},
            {"name": "p_down", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pdown_md5, "md5ext": f"{pdown_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 65},
        ],
        "sounds": [shot_sound()],
        "volume": 100, "layerOrder": 1, "visible": True,
        "x": -150, "y": -40, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ai = {
        "isStage": False, "name": "AI",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ai_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "a_ready", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": aready_md5, "md5ext": f"{aready_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 65},
            {"name": "a_shoot", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ashoot_md5, "md5ext": f"{ashoot_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 65},
            {"name": "a_down", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": adown_md5, "md5ext": f"{adown_md5}.svg",
             "rotationCenterX": 40, "rotationCenterY": 65},
        ],
        "sounds": [shot_sound()],
        "volume": 100, "layerOrder": 2, "visible": True,
        "x": 150, "y": -40, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    drawbanner = {
        "isStage": False, "name": "DRAW배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": draw_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "ready", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ready_md5, "md5ext": f"{ready_md5}.svg",
             "rotationCenterX": 120, "rotationCenterY": 45},
            {"name": "draw", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": draw_md5, "md5ext": f"{draw_md5}.svg",
             "rotationCenterX": 140, "rotationCenterY": 60},
        ],
        "sounds": [shot_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 60, "size": 100, "direction": 90,
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
            {"name": "foul", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": foul_md5, "md5ext": f"{foul_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 85},
            {"name": "victory", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": vic_md5, "md5ext": f"{vic_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 85},
            {"name": "defeat", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": def_md5, "md5ext": f"{def_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 85},
        ],
        "sounds": [shot_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_PWINS, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "내승"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_AWINS, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "AI승"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 380, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_BEST, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "베스트ms"}, "spriteName": None,
         "value": 9999, "width": 0, "height": 0, "x": 150, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_PRT, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "내반응ms"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 150, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, player, ai, drawbanner, banner],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "cowboy-duel-builder"}
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
                    if isinstance(item, list) and len(item) >= 2 and isinstance(item[1], str) \
                       and item[0] in (1,2,3) and item[1] in ids:
                        pass
            for fk, fv in b.get("fields", {}).items():
                if fk == "VARIABLE":
                    vid = fv[1]
                    if vid not in stage["variables"]:
                        raise AssertionError(f"{target['name']} {bid} 변수 {vid} 미등록")
                if fk == "BROADCAST_OPTION":
                    brid = fv[1]
                    if brid not in stage["broadcasts"]:
                        raise AssertionError(f"{target['name']} {bid} 방송 {brid} 미등록")
    for t in project["targets"]:
        check_refs(t)

    # costume name 참조 무결성: switch costume 메뉴가 실제 코스튬에 존재?
    cos_names = {t["name"]: {c["name"] for c in t["costumes"]} for t in project["targets"]}
    for t in project["targets"]:
        for bid, b in t["blocks"].items():
            if isinstance(b, dict) and b.get("opcode") == "looks_costume":
                cn = b["fields"]["COSTUME"][0]
                if cn not in cos_names[t["name"]]:
                    raise AssertionError(f"{t['name']} 코스튬 '{cn}' 없음")

    print(f"wrote {OUTPUT}")
    print(f"  Stage:    {len(stage_blocks)} blocks")
    print(f"  플레이어: {len(player_blocks)} blocks")
    print(f"  AI:       {len(ai_blocks)} blocks")
    print(f"  DRAW배너: {len(draw_blocks)} blocks")
    print(f"  결과배너: {len(banner_blocks)} blocks")
    total = (len(stage_blocks) + len(player_blocks) + len(ai_blocks)
             + len(draw_blocks) + len(banner_blocks))
    print(f"  TOTAL:    {total} blocks")
    print(f"  targets:  {len(project['targets'])}")
    print(f"  monitors: {len(monitors)}")
    print(f"  SVG: 14, WAV: 1 (shot)")
    print("  refs OK, costumes OK, zip OK, json OK")

if __name__ == "__main__":
    main()
