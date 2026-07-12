#!/usr/bin/env python3
"""라인 시즈 (lane-siege) — 냥코대전쟁식 1레인 라인 배틀 데모.

세로 라인 1줄. 화면 아래 = 내 성, 화면 위 = 적 성. 하단 소환 버튼 3개로 유닛을
배치하면 유닛들이 줄을 서서 알아서 전진하며 최전방끼리 교전한다. 돈이 시간에 따라
차오르고 유닛마다 코스트+쿨다운이 있어 "언제 무엇을 뽑을지"가 유일한 전략.
적 성 HP 0 → 승리, 아군 성 HP 0 → 패배.

★ 존재 이유 = chess-war 실패(per-unit 듀얼 O(n²) 루프 붕괴) 재발 방지.
  이 데모는 "최전방 교전(front-line only)" O(n) 모델을 검증한다.
  - 클론끼리 직접 참조/스캔 절대 금지. 유닛 클론 안에 다른 유닛 클론을
    touching/리스트 순회/이중 루프로 탐색하는 코드가 단 하나도 없다.
  - 전투 판정은 선두 공유 변수(아군선두y/적선두y + 아군선두HP/적선두HP) 경유
    상수 시간. 각 클론은 자기 y/HP를 선두 채널에 보고(min/max)하고, 자기가
    선두일 때만(내 y == 선두 y 근사) 상대 선두 HP 채널을 상수 시간 깎는다.
  - 유닛 캡 8 / 투사체 캡 12 / 화면 밖·명중 즉시 delete this clone.

베이스: games/hero-rush/build.py (b_* 헬퍼·synth 사운드·costume-fill 바·클론
스포너·복제됨 가드·add_comment 투어). 다대다 자율 전투 없음(선두 채널만).
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "라인_시즈.sb3")

# ============================================================
#  효과음 합성 (4종) — 결정적
# ============================================================
SND_RATE = 11025
def _wav_bytes(samples, rate=SND_RATE):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_pop(rate=SND_RATE):
    """소환 '뽕' — 300→700Hz 상승, 0.09초."""
    N = int(rate * 0.09); out = []
    for i in range(N):
        t = i / rate
        f = 300 + 400 * min(1.0, t / 0.05)
        env = min(1.0, t / 0.01) * math.exp(-t * 12)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.5)
    return out

def synth_hit(rate=SND_RATE):
    """근접 타격 '틱' — 1.6kHz 짧은 클릭, 0.035초."""
    N = int(rate * 0.035); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 80)
        out.append(math.sin(2 * math.pi * 1600 * t) * env * 0.5)
    return out

def synth_pew(rate=SND_RATE):
    """화살 '핑' — 1200→500Hz 하강 처프, 0.07초."""
    N = int(rate * 0.07); out = []
    for i in range(N):
        t = i / rate
        f = 500 + 700 * math.exp(-t * 40)
        env = math.exp(-t * 26)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.45)
    return out

def synth_crack(rate=SND_RATE):
    """격파/성 타격 '펑' — 노이즈+저음 thump, 0.13초. 결정적."""
    N = int(rate * 0.13); out = []
    rng = random.Random(20260712); lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 18)
        white = rng.random() * 2 - 1
        lp = lp + 0.4 * (white - lp)
        thump = math.sin(2 * math.pi * (80 + 50 * math.exp(-t * 24)) * t)
        out.append(max(-1, min(1, (lp * 0.55 + thump * 0.7) * env)))
    return out

# ============================================================
#  SVG assets
# ============================================================
# 좌표: scratchX = svgX-240, scratchY = 180-svgY.
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs><linearGradient id="grd" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#B24C4C"/><stop offset="0.5" stop-color="#8C6D5A"/>
    <stop offset="1" stop-color="#4C6BA0"/></linearGradient></defs>
  <rect width="480" height="360" fill="url(#grd)"/>
  <!-- 적 진영(위) 붉은 영역 -->
  <rect x="0" y="0" width="480" height="70" fill="#7A2E2E" opacity="0.55"/>
  <!-- 아군 진영(아래) 파란 영역 -->
  <rect x="0" y="300" width="480" height="60" fill="#2E4A7A" opacity="0.55"/>
  <!-- 세로 라인(라인X=0 → svgX=240) -->
  <line x1="240" y1="60" x2="240" y2="300" stroke="#FFFFFF" stroke-width="4" stroke-dasharray="10 8" opacity="0.35"/>
  <!-- 적 성(상단) -->
  <g>
    <rect x="150" y="6" width="180" height="30" fill="#5A1E1E" stroke="#3A1010" stroke-width="3"/>
    <rect x="150" y="6" width="18" height="30" fill="#3A1010"/><rect x="222" y="6" width="18" height="30" fill="#3A1010"/><rect x="312" y="6" width="18" height="30" fill="#3A1010"/>
    <rect x="216" y="14" width="48" height="22" rx="10" fill="#200808"/>
  </g>
  <!-- 아군 성(하단) -->
  <g>
    <rect x="150" y="324" width="180" height="30" fill="#1E3A5A" stroke="#0F2038" stroke-width="3"/>
    <rect x="150" y="324" width="18" height="30" fill="#0F2038"/><rect x="222" y="324" width="18" height="30" fill="#0F2038"/><rect x="312" y="324" width="18" height="30" fill="#0F2038"/>
    <rect x="216" y="324" width="48" height="22" rx="10" fill="#081828"/>
  </g>
  <rect x="3" y="3" width="474" height="354" rx="8" fill="none" stroke="#000000" stroke-width="3" opacity="0.3"/>
</svg>"""

# -------- 아군 유닛 3코스튬 (파란 계열, 위 향함) --------
def _unit_svg(fill, stroke, kind, shield=False, bow=False):
    body = f'<rect x="14" y="20" width="18" height="20" rx="5" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    head = f'<circle cx="23" cy="14" r="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    extra = ""
    if shield:
        extra = f'<rect x="4" y="18" width="9" height="18" rx="3" fill="#CFD8DC" stroke="{stroke}" stroke-width="2"/>'
    if bow:
        extra = f'<path d="M34 12 Q42 24 34 36" fill="none" stroke="#8D5A2B" stroke-width="2.5"/><line x1="34" y1="12" x2="34" y2="36" stroke="#DDD" stroke-width="1"/>'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
  <ellipse cx="23" cy="43" rx="12" ry="3" fill="#000" opacity="0.22"/>
  {body}{head}{extra}
</svg>"""

A_SHIELD_SVG = _unit_svg("#3F72C4", "#1C3E7A", 1, shield=True)   # 방패병(탱커)
A_ARCHER_SVG = _unit_svg("#4FA3D8", "#1C5E86", 2, bow=True)      # 궁수
A_SCOUT_SVG  = _unit_svg("#6EC1E8", "#2A7BA0", 3)                # 척후병
E_SHIELD_SVG = _unit_svg("#C44242", "#7A1C1C", 1, shield=True)
E_ARCHER_SVG = _unit_svg("#D87A4F", "#86341C", 2, bow=True)
E_SCOUT_SVG  = _unit_svg("#E89A6E", "#A05A2A", 3)

POP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
  <circle cx="23" cy="23" r="18" fill="#FFD54F" opacity="0.6"/>
  <circle cx="23" cy="23" r="10" fill="#FFF176"/>
</svg>"""

# -------- 화살 (아군=위로, 적=아래로) --------
ARROW_UP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="24" viewBox="0 0 12 24">
  <line x1="6" y1="4" x2="6" y2="22" stroke="#8D5A2B" stroke-width="2.5"/>
  <polygon points="6,0 10,7 2,7" fill="#ECEFF1" stroke="#607D8B" stroke-width="0.6"/>
</svg>"""
ARROW_DOWN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="24" viewBox="0 0 12 24">
  <line x1="6" y1="2" x2="6" y2="20" stroke="#8D5A2B" stroke-width="2.5"/>
  <polygon points="6,24 10,17 2,17" fill="#FFCDD2" stroke="#B71C1C" stroke-width="0.6"/>
</svg>"""

# -------- 소환 버튼 (3버튼 × 활성/비활성 = 6코스튬) --------
def _btn_svg(icon, cost, color, active):
    op = "1" if active else "0.4"
    bg = color if active else "#555555"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="80" height="46" viewBox="0 0 80 46">
  <rect x="2" y="2" width="76" height="42" rx="9" fill="{bg}" stroke="#FFFFFF" stroke-width="2" opacity="{op}"/>
  <text x="26" y="30" text-anchor="middle" font-family="Arial" font-size="24">{icon}</text>
  <text x="58" y="20" text-anchor="middle" font-family="Arial" font-size="15" font-weight="bold" fill="#FFFFFF">{cost}</text>
  <text x="58" y="36" text-anchor="middle" font-family="Arial" font-size="10" fill="#FFFFFF">코스트</text>
</svg>"""
BTN_SHIELD_ON  = _btn_svg("🛡", "20", "#2E7D32", True)
BTN_SHIELD_OFF = _btn_svg("🛡", "20", "#2E7D32", False)
BTN_ARCHER_ON  = _btn_svg("🏹", "50", "#1565C0", True)
BTN_ARCHER_OFF = _btn_svg("🏹", "50", "#1565C0", False)
BTN_SCOUT_ON   = _btn_svg("🏃", "15", "#EF6C00", True)
BTN_SCOUT_OFF  = _btn_svg("🏃", "15", "#EF6C00", False)

# -------- HP바 / 지갑바 costume-fill 11단 --------
def _bar_svg(step, fill, label):
    w = int(round(120 * step / 10))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="170" height="22" viewBox="0 0 170 22">
  <text x="2" y="16" font-family="Arial" font-size="13">{label}</text>
  <rect x="34" y="3" width="124" height="16" rx="4" fill="#000000" opacity="0.4"/>
  <rect x="36" y="5" width="{w}" height="12" rx="3" fill="{fill}"/>
  <rect x="34" y="3" width="124" height="16" rx="4" fill="none" stroke="#FFFFFF" stroke-width="1.5" opacity="0.8"/>
</svg>"""
AHP_BARS = [_bar_svg(s, "#42A5F5", "🏰") for s in range(11)]   # 아군 성
EHP_BARS = [_bar_svg(s, "#EF5350", "🏰") for s in range(11)]   # 적 성
GOLD_BARS = [_bar_svg(s, "#FFCA28", "💰") for s in range(11)]  # 지갑

# -------- 승/패 배너 --------
WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="140" viewBox="0 0 360 140">
  <rect x="5" y="5" width="350" height="130" rx="14" fill="#0D3B0D" opacity="0.9" stroke="#66BB6A" stroke-width="5"/>
  <text x="180" y="70" text-anchor="middle" fill="#A5D6A7" font-family="Arial" font-size="44" font-weight="bold">승리!</text>
  <text x="180" y="108" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="16">적 성 함락 — 초록 깃발로 재도전</text>
</svg>"""
LOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="140" viewBox="0 0 360 140">
  <rect x="5" y="5" width="350" height="130" rx="14" fill="#3B0D0D" opacity="0.9" stroke="#EF5350" stroke-width="5"/>
  <text x="180" y="70" text-anchor="middle" fill="#EF9A9A" font-family="Arial" font-size="44" font-weight="bold">패배...</text>
  <text x="180" y="108" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="16">아군 성 함락 — 초록 깃발로 재도전</text>
</svg>"""

# ============================================================
#  helpers (scratch-game-template 공통 — 재구현 금지)
# ============================================================
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n):  return [1, [4, str(n)]]
def text_lit(s): return [1, [10, str(s)]]
def slot(bid, sk=4, sv="0"): return [3, bid, [sk, str(sv)]]

def mk(opcode, *, parent=None, next_=None, inputs=None, fields=None, top=False, x=0, y=0, shadow=False):
    b = {"opcode": opcode, "next": next_, "parent": parent, "inputs": inputs or {},
         "fields": fields or {}, "shadow": shadow, "topLevel": top}
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

def C(bs, ids):
    chain([(i, bs[i]) for i in ids])

_cmt_ic = [0]
def add_comment(bs, comments, block_id, text, x=520, y=40, w=320, h=140):
    _cmt_ic[0] += 1
    cid = f"cmt{_cmt_ic[0]:03d}"
    comments[cid] = {"blockId": block_id, "x": x, "y": y, "width": w, "height": h, "minimized": False, "text": text}
    if block_id in bs: bs[block_id]["comment"] = cid
    return cid

def make_helpers(bs):
    def vrep(name, vid):
        bid = gen(); bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]}); return bid
    def op(opcode, a, b_, key1="NUM1", key2="NUM2"):
        bid = gen(); ins = {}
        for key, val in [(key1, a), (key2, b_)]:
            ins[key] = slot(val) if isinstance(val, str) else num(val)
        bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): bs[v]["parent"] = bid
        return bid
    def cmp_op(opcode, a, b_):
        bid = gen(); ins = {}
        for key, val in [("OPERAND1", a), ("OPERAND2", b_)]:
            ins[key] = slot(val) if isinstance(val, str) else num(val)
        bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): bs[v]["parent"] = bid
        return bid
    def bool_op(opcode, a, b_):
        bid = gen(); bs[bid] = mk(opcode, inputs={"OPERAND1":[2,a],"OPERAND2":[2,b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid; return bid
    return vrep, op, cmp_op, bool_op

def b_not(bs, cond):
    bid = gen(); bs[bid] = mk("operator_not", inputs={"OPERAND": [2, cond]}); bs[cond]["parent"] = bid; return bid
def b_round(bs, val):
    bid = gen(); ins = {"NUM": slot(val) if (isinstance(val,str) and val in bs) else num(val)}
    bs[bid] = mk("operator_round", inputs=ins)
    if isinstance(val,str) and val in bs: bs[val]["parent"] = bid
    return bid
def b_abs(bs, val):
    bid = gen(); ins = {"NUM": slot(val) if (isinstance(val,str) and val in bs) else num(val)}
    bs[bid] = mk("operator_mathop", inputs=ins, fields={"OPERATOR": ["abs", None]})
    if isinstance(val,str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_setvar(bs, name, vid, value):
    bid = gen()
    if isinstance(value, str) and value in bs:
        bs[bid] = mk("data_setvariableto", inputs={"VALUE": slot(value)}, fields={"VARIABLE": [name, vid]})
        bs[value]["parent"] = bid
    else:
        bs[bid] = mk("data_setvariableto", inputs={"VALUE": num(value)}, fields={"VARIABLE": [name, vid]})
    return bid
def b_changevar(bs, name, vid, value):
    bid = gen()
    if isinstance(value, str) and value in bs:
        bs[bid] = mk("data_changevariableby", inputs={"VALUE": slot(value)}, fields={"VARIABLE": [name, vid]})
        bs[value]["parent"] = bid
    else:
        bs[bid] = mk("data_changevariableby", inputs={"VALUE": num(value)}, fields={"VARIABLE": [name, vid]})
    return bid

def b_mousedown(bs):
    bid = gen(); bs[bid] = mk("sensing_mousedown"); return bid
def b_touchingmouse(bs):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu", fields={"TOUCHINGOBJECTMENU": ["_mouse_", None]}, shadow=True)
    t = gen(); bs[t] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, m]}); bs[m]["parent"] = t; return t

def b_if(bs, cond, head):
    bid = gen(); bs[bid] = mk("control_if", inputs={"CONDITION": [2, cond], "SUBSTACK": [2, head]})
    bs[cond]["parent"] = bid; bs[head]["parent"] = bid; return bid
def b_ifelse(bs, cond, ht, hf):
    bid = gen(); bs[bid] = mk("control_if_else", inputs={"CONDITION": [2, cond], "SUBSTACK": [2, ht], "SUBSTACK2": [2, hf]})
    bs[cond]["parent"] = bid; bs[ht]["parent"] = bid; bs[hf]["parent"] = bid; return bid
def b_forever(bs, head):
    bid = gen(); bs[bid] = mk("control_forever", inputs={"SUBSTACK": [2, head]}); bs[head]["parent"] = bid; return bid
def b_repeat(bs, times, head):
    bid = gen()
    if isinstance(times, str) and times in bs:
        bs[bid] = mk("control_repeat", inputs={"TIMES": slot(times), "SUBSTACK": [2, head]}); bs[times]["parent"] = bid
    else:
        bs[bid] = mk("control_repeat", inputs={"TIMES": num(times), "SUBSTACK": [2, head]})
    bs[head]["parent"] = bid; return bid
def b_wait(bs, dur):
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": num(dur)}); return bid
def b_waituntil(bs, cond):
    bid = gen(); bs[bid] = mk("control_wait_until", inputs={"CONDITION": [2, cond]}); bs[cond]["parent"] = bid; return bid
def b_stopthis(bs):
    bid = gen(); bs[bid] = mk("control_stop", fields={"STOP_OPTION": ["this script", None]})
    bs[bid]["mutation"] = {"tagName": "mutation", "children": [], "hasnext": "false"}
    return bid

def b_playsound(bs, sound):
    sm = gen(); bs[sm] = mk("sound_sounds_menu", fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]}); bs[sm]["parent"] = sp; return sp

def b_broadcast(bs, name, brid):
    m = gen(); bs[m] = mk("event_broadcast_menu", fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcast", inputs={"BROADCAST_INPUT": [1, m]}); bs[m]["parent"] = b; return b
def b_broadcast_wait(bs, name, brid):
    m = gen(); bs[m] = mk("event_broadcast_menu", fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcastandwait", inputs={"BROADCAST_INPUT": [1, m]}); bs[m]["parent"] = b; return b

def b_costume(bs, name):
    cmc = gen(); bs[cmc] = mk("looks_costume", fields={"COSTUME": [name, None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc]}); bs[cmc]["parent"] = sw; return sw
def b_costume_idx(bs, idx_reporter):
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(idx_reporter)}); bs[idx_reporter]["parent"] = sw; return sw

def b_gotoxy(bs, x, y):
    bid = gen()
    def side(v): return slot(v) if (isinstance(v, str) and v in bs) else num(v)
    bs[bid] = mk("motion_gotoxy", inputs={"X": side(x), "Y": side(y)})
    for v in (x, y):
        if isinstance(v, str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_changey(bs, v):
    bid = gen(); ins = {"DY": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_changeyby", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_sety(bs, v):
    bid = gen(); ins = {"Y": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_sety", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_xpos(bs):
    bid = gen(); bs[bid] = mk("motion_xposition"); return bid
def b_ypos(bs):
    bid = gen(); bs[bid] = mk("motion_yposition"); return bid
def b_pointdir(bs, d):
    bid = gen(); bs[bid] = mk("motion_pointindirection", inputs={"DIRECTION": num(d)}); return bid

def b_setsize(bs, sz):
    if isinstance(sz, str):
        bid = gen(); bs[bid] = mk("looks_setsizeto", inputs={"SIZE": slot(sz)}); bs[sz]["parent"] = bid; return bid
    bid = gen(); bs[bid] = mk("looks_setsizeto", inputs={"SIZE": num(sz)}); return bid
def b_changesize(bs, dz):
    bid = gen(); bs[bid] = mk("looks_changesizeby", inputs={"CHANGE": num(dz)}); return bid
def b_seteffect(bs, eff, v):
    bid = gen(); bs[bid] = mk("looks_seteffectto", inputs={"VALUE": num(v)}, fields={"EFFECT": [eff, None]}); return bid
def b_changeeffect(bs, eff, v):
    bid = gen(); bs[bid] = mk("looks_changeeffectby", inputs={"CHANGE": num(v)}, fields={"EFFECT": [eff, None]}); return bid
def b_cleargfx(bs):
    bid = gen(); bs[bid] = mk("looks_cleargraphiceffects"); return bid
def b_show(bs):
    bid = gen(); bs[bid] = mk("looks_show"); return bid
def b_hide(bs):
    bid = gen(); bs[bid] = mk("looks_hide"); return bid
def b_front(bs):
    bid = gen(); bs[bid] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]}); return bid
def b_rotstyle(bs, style):
    bid = gen(); bs[bid] = mk("motion_setrotationstyle", fields={"STYLE": [style, None]}); return bid
def b_createclone(bs):
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu", fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]}); bs[cmenu]["parent"] = cc; return cc
def b_delclone(bs):
    bid = gen(); bs[bid] = mk("control_delete_this_clone"); return bid

# ============================================================
#  IDs
# ============================================================
# ---- 튜닝 / 전역 상태 ----
V_GOLD="varGold01"; V_GOLDMAX="varGoldMax02"; V_GOLDRATE="varGoldRate03"
V_UNITCAP="varUnitCap04"; V_PROJCAP="varProjCap05"
V_AHP="varAHP06"; V_EHP="varEHP07"; V_CASTLEHIT="varCastleHit08"
V_ESPAWN="varESpawnGap09"; V_LINEX="varLineX10"; V_ASPAWNY="varASpawnY11"; V_ESPAWNY="varESpawnY12"
V_ALEADY="varALeadY13"; V_ELEADY="varELeadY14"; V_ALEADHP="varALeadHP15"; V_ELEADHP="varELeadHP16"
# 선두 y 스테이징(각 유닛이 매틱 max/min 누적 → 원본이 publish 후 리셋). read/write 분리로 리셋 레이스 제거.
V_ALEADYRAW="varALeadYRaw41"; V_ELEADYRAW="varELeadYRaw42"
V_ACOUNT="varACount17"; V_ECOUNT="varECount18"; V_STATE="varState19"; V_PROJCOUNT="varProjCount20"
# 종류별 스탯(코스트/HP/속도/공격/사거리/소환쿨)
V_C_SHIELD="varCostShield21"; V_C_ARCHER="varCostArcher22"; V_C_SCOUT="varCostScout23"
V_CD_SHIELD="varCdShield24"; V_CD_ARCHER="varCdArcher25"; V_CD_SCOUT="varCdScout26"
# 소환 파라미터 채널 / 쿨 타이머 / 적AI 타이머
V_SPTYPE="varSpType27"; V_ESPTYPE="varESpType28"
V_CDT_SHIELD="varCdtShield29"; V_CDT_ARCHER="varCdtArcher30"; V_CDT_SCOUT="varCdtScout31"
V_ESPT="varESpawnT32"
# 근접 공격 쿨(선두 교전 페이싱, 공유)
V_MELEET_A="varMeleeTA33"; V_MELEET_E="varMeleeTE34"
# 선두 근접 데미지 값(선두 종류에 따라 판정용)
V_ALEADATK="varALeadAtk35"; V_ELEADATK="varELeadAtk36"

# ---- 클론-로컬(유닛) ----
V_ISC="varIsClone"; V_TYPE="varMyType"; V_HP="varMyHP"; V_SPD="varMySpd"; V_ATK="varMyAtk"; V_RNG="varMyRange"; V_FIRET="varFireT"
# ---- 클론-로컬(화살) ----
V_ARR_ISC="varArrIsClone"

# ---- 방송 ----
BR_START="brStart01"; BR_ASPAWN="brASpawn02"; BR_ESPAWN="brESpawn03"
BR_AFIRE="brAFire04"; BR_EFIRE="brEFire05"; BR_END="brEnd06"

# 종류 상수: 1=방패병 2=궁수 3=척후병
# ============================================================
#  STAGE — 초기화 + 돈충전 + 적AI + 선두교전심판 + 승패감시
# ============================================================
def build_stage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 → 전역 초기화 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [h]
    def s(name, vid, val): seq.append(b_setvar(bs, name, vid, val))
    # 경제/캡
    s("돈", V_GOLD, 40); s("돈상한", V_GOLDMAX, 200); s("돈충전율", V_GOLDRATE, 4)
    s("유닛캡", V_UNITCAP, 8); s("투사체캡", V_PROJCAP, 12)
    # 성/전투
    s("아군성HP", V_AHP, 60); s("적성HP", V_EHP, 60); s("성타격", V_CASTLEHIT, 12)
    s("적스폰간격", V_ESPAWN, 3.0); s("라인X", V_LINEX, 0); s("아군스폰y", V_ASPAWNY, -110); s("적스폰y", V_ESPAWNY, 110)
    # 종류별 스탯: 코스트 / 소환쿨(틱, 0.02s 루프 기준 → 초×50)
    s("방패_코스트", V_C_SHIELD, 20); s("궁수_코스트", V_C_ARCHER, 50); s("척후_코스트", V_C_SCOUT, 15)
    s("방패_소환쿨", V_CD_SHIELD, 30); s("궁수_소환쿨", V_CD_ARCHER, 100); s("척후_소환쿨", V_CD_SCOUT, 25)
    # 선두 채널 / 카운트 / 상태
    s("아군선두y", V_ALEADY, -180); s("적선두y", V_ELEADY, 180)
    s("아군선두y원", V_ALEADYRAW, -180); s("적선두y원", V_ELEADYRAW, 180)
    s("아군선두HP", V_ALEADHP, 0); s("적선두HP", V_ELEADHP, 0)
    s("아군선두공격", V_ALEADATK, 0); s("적선두공격", V_ELEADATK, 0)
    s("아군수", V_ACOUNT, 0); s("적수", V_ECOUNT, 0); s("게임상태", V_STATE, 1); s("투사체수", V_PROJCOUNT, 0)
    s("소환종류", V_SPTYPE, 0); s("적소환종류", V_ESPTYPE, 0)
    s("방패_쿨타이머", V_CDT_SHIELD, 0); s("궁수_쿨타이머", V_CDT_ARCHER, 0); s("척후_쿨타이머", V_CDT_SCOUT, 0)
    s("적스폰타이머", V_ESPT, 1.0)
    s("근접쿨_아군", V_MELEET_A, 0); s("근접쿨_적", V_MELEET_E, 0)
    seq.append(b_wait(bs, 0.2))
    seq.append(b_broadcast(bs, "게임시작", BR_START))
    C(bs, seq)
    add_comment(bs, comments, seq[1],
        "🛠️ 개조 손잡이: 돈·캡·성HP·유닛 스탯 전부 여기 숫자만 바꾸면 게임이 달라져요.\n"
        "유닛캡 8·투사체캡 12 = chess-war 붕괴를 막는 성능 상한(수치로 못박음).",
        x=470, y=20, w=360, h=130)

    # ===== (B) 돈 자동 충전 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=280,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # 돈 += 돈충전율*0.1 (0.1초마다) → 초당 돈충전율. 상한 클램프.
    add_g = b_changevar(bs, "돈", V_GOLD, op("operator_multiply", vrep("돈충전율", V_GOLDRATE), 0.1))
    c_over = cmp_op("operator_gt", vrep("돈", V_GOLD), vrep("돈상한", V_GOLDMAX))
    set_cap = b_setvar(bs, "돈", V_GOLD, vrep("돈상한", V_GOLDMAX))
    if_over = b_if(bs, c_over, set_cap)
    w_g = b_wait(bs, 0.1)
    C(bs, [add_g, if_over, w_g])
    c_playg = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_playg = b_if(bs, c_playg, add_g)
    w_g2 = b_wait(bs, 0.1)
    C(bs, [if_playg, w_g2])
    fe_g = b_forever(bs, if_playg)
    C(bs, [hb, fe_g])
    add_comment(bs, comments, add_g,
        "💰 돈은 시간이 지나면 자동으로 차올라요(돈충전율/초). 상한(돈상한)에서 멈춤.\n"
        "언제 무엇을 뽑을지 = 이 데모의 유일한 전략!",
        x=470, y=280, w=350, h=120)

    # ===== (C) 소환 쿨타이머 감소 forever =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=470, y=280,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    def dec_cd(name, vid):
        c_pos = cmp_op("operator_gt", vrep(name, vid), 0)
        dec = b_changevar(bs, name, vid, -1)
        return b_if(bs, c_pos, dec)
    d1 = dec_cd("방패_쿨타이머", V_CDT_SHIELD); d2 = dec_cd("궁수_쿨타이머", V_CDT_ARCHER); d3 = dec_cd("척후_쿨타이머", V_CDT_SCOUT)
    # 근접 교전 쿨도 여기서 감소
    d4 = dec_cd("근접쿨_아군", V_MELEET_A); d5 = dec_cd("근접쿨_적", V_MELEET_E)
    w_c = b_wait(bs, 0.02)
    C(bs, [d1, d2, d3, d4, d5, w_c])
    fe_c = b_forever(bs, d1)
    C(bs, [hc, fe_c])

    # ===== (D) 적 AI 스폰 타이머 forever =====
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=560,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    dec_t = b_changevar(bs, "적스폰타이머", V_ESPT, -0.1)
    # if 적스폰타이머<=0 and 적수<유닛캡 → 종류 랜덤(1~3) 적소환·타이머 리셋
    c_t0 = b_not(bs, cmp_op("operator_gt", vrep("적스폰타이머", V_ESPT), 0))
    c_room = cmp_op("operator_lt", vrep("적수", V_ECOUNT), vrep("유닛캡", V_UNITCAP))
    c_sp = bool_op("operator_and", c_t0, c_room)
    rnd = op("operator_random", 1, 3, key1="FROM", key2="TO")
    set_et = b_setvar(bs, "적소환종류", V_ESPTYPE, rnd)
    inc_e = b_changevar(bs, "적수", V_ECOUNT, 1)
    bc_e = b_broadcast_wait(bs, "적소환", BR_ESPAWN)
    reset_t = b_setvar(bs, "적스폰타이머", V_ESPT, vrep("적스폰간격", V_ESPAWN))
    C(bs, [set_et, inc_e, bc_e, reset_t])
    if_sp = b_if(bs, c_sp, set_et)
    c_playe = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    C(bs, [dec_t, if_sp])
    if_playe = b_if(bs, c_playe, dec_t)
    w_e = b_wait(bs, 0.1)
    C(bs, [if_playe, w_e])
    fe_e = b_forever(bs, if_playe)
    C(bs, [hd, fe_e])
    add_comment(bs, comments, if_sp,
        "🤖 적 AI: 적스폰간격마다 랜덤 유닛 1기 자동 소환(적수<유닛캡 일 때만).\n"
        "적수 카운트가 유닛캡(8)을 넘지 못하게 막아 총량 폭주 방지.",
        x=470, y=560, w=350, h=120)

    # ===== (E) ★ 선두 교전 심판 forever (chess-war 회피 핵심) =====
    # 클론끼리 스캔 0개. 오직 선두 공유 변수만 본다: 상수 시간 판정.
    he = gen(); bs[he] = mk("event_whenbroadcastreceived", top=True, x=470, y=560,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # 매 틱: 두 선두가 살아있고(HP>0) 서로 사거리(=거리<=근접간격) 안이면 서로 HP 깎기(쿨 간격).
    # 거리 = 적선두y - 아군선두y (아군은 아래→위, 적은 위→아래 → 적선두y > 아군선두y).
    dist = op("operator_subtract", vrep("적선두y", V_ELEADY), vrep("아군선두y", V_ALEADY))
    c_close = b_not(bs, cmp_op("operator_gt", dist, 24))   # 근접 교전 간격 24px
    c_aok = cmp_op("operator_gt", vrep("아군선두HP", V_ALEADHP), 0)
    c_eok = cmp_op("operator_gt", vrep("적선두HP", V_ELEADHP), 0)
    c_both = bool_op("operator_and", c_aok, c_eok)
    c_fight = bool_op("operator_and", c_close, c_both)
    # ★ 병력 우세 반영(O(1)! 클론 스캔 아님 — 이미 세고 있는 아군수/적수 공유 카운트만 사용):
    #   선두 데미지 = 선두공격 × (1 + 상대 대비 자기 진영 병력수×0.18).
    #   → 수가 많은 쪽이 선두 듀얼을 더 빨리 이겨 '밀어붙이는' 라인 배틀 감. 전투는 여전히 선두 O(1).
    a_mult = op("operator_add", 1, op("operator_multiply", vrep("아군수", V_ACOUNT), 0.22))
    e_mult = op("operator_add", 1, op("operator_multiply", vrep("적수", V_ECOUNT), 0.22))
    # 아군 근접쿨 준비 → 적선두HP -= 아군선두공격×a_mult, 쿨 리셋, 소리
    c_acd = b_not(bs, cmp_op("operator_gt", vrep("근접쿨_아군", V_MELEET_A), 0))
    dmg_e = b_changevar(bs, "적선두HP", V_ELEADHP,
                        op("operator_subtract", 0, op("operator_multiply", vrep("아군선두공격", V_ALEADATK), a_mult)))
    set_acd = b_setvar(bs, "근접쿨_아군", V_MELEET_A, 20)
    ph1 = b_playsound(bs, "hit")
    C(bs, [dmg_e, set_acd, ph1])
    if_ahit = b_if(bs, c_acd, dmg_e)
    c_ecd = b_not(bs, cmp_op("operator_gt", vrep("근접쿨_적", V_MELEET_E), 0))
    dmg_a = b_changevar(bs, "아군선두HP", V_ALEADHP,
                        op("operator_subtract", 0, op("operator_multiply", vrep("적선두공격", V_ELEADATK), e_mult)))
    set_ecd = b_setvar(bs, "근접쿨_적", V_MELEET_E, 20)
    C(bs, [dmg_a, set_ecd])
    if_ehit = b_if(bs, c_ecd, dmg_a)
    C(bs, [if_ahit, if_ehit])
    if_fight = b_if(bs, c_fight, if_ahit)
    c_playf = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_playf = b_if(bs, c_playf, if_fight)
    w_f = b_wait(bs, 0.02)
    C(bs, [if_playf, w_f])
    fe_f = b_forever(bs, if_playf)
    C(bs, [he, fe_f])
    add_comment(bs, comments, if_fight,
        "⚔️★ 선두 교전 심판(한 곳!). 클론끼리 절대 안 봐요 — 오직 선두 공유 변수\n"
        "(아군선두y/적선두y + 아군선두HP/적선두HP)와 이미 세고 있는 아군수/적수 카운트만 봐요.\n"
        "병력 많은 쪽이 선두 듀얼을 더 빨리 이겨 밀어붙임(수×0.18 보너스) — 전부 O(1).\n"
        "chess-war의 per-unit 듀얼 O(n²)를 여기 O(1) 심판으로 대체 = 폭주 없음.",
        x=900, y=560, w=400, h=160)

    # ===== (F) 승패 감시 forever =====
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=20, y=860,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    c_win = b_not(bs, cmp_op("operator_gt", vrep("적성HP", V_EHP), 0))
    c_lose = b_not(bs, cmp_op("operator_gt", vrep("아군성HP", V_AHP), 0))
    c_over = bool_op("operator_or", c_win, c_lose)
    set_s0 = b_setvar(bs, "게임상태", V_STATE, 0)
    bc_end = b_broadcast(bs, "게임끝", BR_END)
    C(bs, [set_s0, bc_end])
    c_playo = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_endnow = bool_op("operator_and", c_playo, c_over)
    if_over = b_if(bs, c_endnow, set_s0)
    w_o = b_wait(bs, 0.05)
    C(bs, [if_over, w_o])
    fe_o = b_forever(bs, if_over)
    C(bs, [hf, fe_o])

    return bs, comments

# ============================================================
#  아군/적 유닛 (스포너 + 클론 본체) — 진영 미러
#  side="A"(아군, 아래→위, +y) / "E"(적, 위→아래, -y)
#  ★ 클론끼리 참조/스캔 0개. 전진 + 자기 y/HP 선두채널 보고만.
# ============================================================
def build_unit_blocks(side):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    A = (side == "A")
    # 진영별 채널/상수
    SPTYPE  = (V_SPTYPE, "소환종류") if A else (V_ESPTYPE, "적소환종류")
    SPAWN   = (BR_ASPAWN, "아군소환") if A else (BR_ESPAWN, "적소환")
    COUNT   = (V_ACOUNT, "아군수") if A else (V_ECOUNT, "적수")
    SPAWNY  = (V_ASPAWNY, "아군스폰y") if A else (V_ESPAWNY, "적스폰y")
    LEADY    = (V_ALEADY, "아군선두y") if A else (V_ELEADY, "적선두y")
    LEADYRAW = (V_ALEADYRAW, "아군선두y원") if A else (V_ELEADYRAW, "적선두y원")
    LEADHP  = (V_ALEADHP, "아군선두HP") if A else (V_ELEADHP, "적선두HP")
    LEADATK = (V_ALEADATK, "아군선두공격") if A else (V_ELEADATK, "적선두공격")
    OPP_LEADY  = (V_ELEADY, "적선두y") if A else (V_ALEADY, "아군선두y")
    OPP_LEADHP = (V_ELEADHP, "적선두HP") if A else (V_ALEADHP, "아군선두HP")
    OPP_CASTLE = (V_EHP, "적성HP") if A else (V_AHP, "아군성HP")
    FIRE    = (BR_AFIRE, "아군발사") if A else (BR_EFIRE, "적발사")
    CS = "아" if A else "적"
    face_dir = 0 if A else 180
    dir_sign = 1 if A else -1
    reset_lead = -180 if A else 180
    castle_y = 150 if A else -150

    # 선두 판정 조건을 매번 새 블록으로(재사용 금지): |내y - 선두y| <= 1.5
    def cond_is_lead():
        diff = op("operator_subtract", b_ypos(bs), vrep(LEADY[1], LEADY[0]))
        gt = cmp_op("operator_gt", b_abs(bs, diff), 1.5)
        return b_not(bs, gt)
    # 상대 선두까지 거리(전진 방향 기준, 양수면 앞에 있음)
    def opp_dist():
        if A:
            return op("operator_subtract", vrep(OPP_LEADY[1], OPP_LEADY[0]), b_ypos(bs))
        return op("operator_subtract", b_ypos(bs), vrep(OPP_LEADY[1], OPP_LEADY[0]))
    # 전진 1스텝. 매번 새 블록.
    #  - 선두(is_lead=True): 클램프 없음(선두가 전선을 정의). 자유 전진.
    #  - 비선두(is_lead=False): 앞 유닛(=선두 채널 y) 뒤 gap(16px)까지만 전진 → 줄서기(추월 없음).
    GAP = 16
    def make_move(is_lead):
        step = op("operator_multiply", dir_sign, vrep("내속도", V_SPD))
        mv = b_changey(bs, step)
        if is_lead:
            return mv  # 선두는 클램프 없이 전진 헤드만 반환
        # 비선두 클램프: 아군이면 선두y-GAP 을 넘으면(>) 그 값으로, 적이면 선두y+GAP 미만이면 그 값으로.
        if A:
            limit = op("operator_subtract", vrep(LEADY[1], LEADY[0]), GAP)
            c_pass = cmp_op("operator_gt", b_ypos(bs), limit)
            clamp_to = op("operator_subtract", vrep(LEADY[1], LEADY[0]), GAP)
        else:
            limit = op("operator_add", vrep(LEADY[1], LEADY[0]), GAP)
            c_pass = cmp_op("operator_lt", b_ypos(bs), limit)
            clamp_to = op("operator_add", vrep(LEADY[1], LEADY[0]), GAP)
        clamp = b_sety(bs, clamp_to)
        if_clamp = b_if(bs, c_pass, clamp)
        C(bs, [mv, if_clamp])
        return mv

    # ── (A) 깃발: 숨김·복제됨 가드 ──
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs, "don't rotate"); orig0 = b_setvar(bs, "복제됨", V_ISC, 0)
    C(bs, [h, hi, rs, orig0])

    # ── (B) 소환 방송 → 클론 (원본만) ──
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": [SPAWN[1], SPAWN[0]]})
    cc = b_createclone(bs)
    if_c = b_if(bs, cmp_op("operator_equals", vrep("복제됨", V_ISC), 0), cc)
    C(bs, [hb, if_c])

    # ── (C) 원본 재고정 forever: 유닛이 하나도 없을 때 선두y 를 스폰선으로 돌려놓기 ──
    # 리셋 레이스를 피하려고 매틱 리셋을 하지 않는다. 대신 '아군수=0(전멸)'일 때만 채널을
    # 스폰선으로 복구(스테일 방지). 살아있는 유닛이 있으면 그들이 선두y 를 직접 관리(아래 D-1).
    hcr = gen(); bs[hcr] = mk("event_whenflagclicked", top=True, x=470, y=20)
    c_empty = b_not(bs, cmp_op("operator_gt", vrep(COUNT[1], COUNT[0]), 0))
    reset_y = b_setvar(bs, LEADY[1], LEADY[0], reset_lead)
    if_empty = b_if(bs, c_empty, reset_y)
    w_r = b_wait(bs, 0.05)
    C(bs, [if_empty, w_r])
    fe_r = b_forever(bs, if_empty)
    if_isorig = b_if(bs, cmp_op("operator_equals", vrep("복제됨", V_ISC), 0), fe_r)
    C(bs, [hcr, if_isorig])

    # ── (D) 클론 본체 ──
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_ISC, 1)
    set_type = b_setvar(bs, "내종류", V_TYPE, vrep(SPTYPE[1], SPTYPE[0]))
    pd = b_pointdir(bs, face_dir)
    # 종류별 스탯(클론 세팅부 표 — 매직넘버 집약)
    def stat_branch(hp, spd, atk, rng, costume, size):
        s_hp = b_setvar(bs, "내HP", V_HP, hp); s_sp = b_setvar(bs, "내속도", V_SPD, spd)
        s_at = b_setvar(bs, "내공격", V_ATK, atk); s_rn = b_setvar(bs, "내사거리", V_RNG, rng)
        swc = b_costume(bs, costume); szb = b_setsize(bs, size)
        C(bs, [s_hp, s_sp, s_at, s_rn, swc, szb])
        return s_hp
    b1 = stat_branch(30, 1.0, 4, 0,  f"{CS}방패", 90)   # 방패병 탱커
    b2 = stat_branch(8,  1.4, 3, 90, f"{CS}궁수", 80)   # 궁수 원거리(사거리 90)
    b3 = stat_branch(6,  2.6, 2, 0,  f"{CS}척후", 75)   # 척후 빠름
    if_t2 = b_ifelse(bs, cmp_op("operator_equals", vrep("내종류", V_TYPE), 2), b2, b3)
    if_t1 = b_ifelse(bs, cmp_op("operator_equals", vrep("내종류", V_TYPE), 1), b1, if_t2)
    set_fire0 = b_setvar(bs, "발사쿨", V_FIRET, 0)
    g0 = b_gotoxy(bs, 0, vrep(SPAWNY[1], SPAWNY[0]))
    fr = b_front(bs); show = b_show(bs)

    # ---- forever 본체 ----
    # 0) 정리: 게임상태≠1 → 카운트-1·삭제
    c_gameend = b_not(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    dec_end = b_changevar(bs, COUNT[1], COUNT[0], -1); del_end = b_delclone(bs)
    C(bs, [dec_end, del_end])
    if_end = b_if(bs, c_gameend, dec_end)

    # 1) 선두 y 채널 관리 (리셋 레이스 없는 단일-논리-작성자 규칙):
    #    · 내가 선두면(|내y-선두y|<=1.5): 선두y ← 내y  (선두가 채널을 끌고 전진)
    #    · 아니고 내가 더 앞서면(아군 y>선두y / 적 y<선두y): 선두y ← 내y  (새 최전방 = 새 선두)
    #    죽거나 성 도달 시엔 아래에서 선두y 를 스폰선으로 되돌려 다음 최전방이 재점유.
    if A:
        c_more = cmp_op("operator_gt", b_ypos(bs), vrep(LEADY[1], LEADY[0]))
    else:
        c_more = cmp_op("operator_lt", b_ypos(bs), vrep(LEADY[1], LEADY[0]))
    set_ly = b_setvar(bs, LEADY[1], LEADY[0], b_ypos(bs))
    c_claim = bool_op("operator_or", cond_is_lead(), c_more)
    if_report = b_if(bs, c_claim, set_ly)

    # 2) 선두면 HP 채널 동기 + 공격 채널 게시(선두 소유). 처음 선두면 채널<=0 → 내HP로 초기화.
    c_chan_empty = b_not(bs, cmp_op("operator_gt", vrep(LEADHP[1], LEADHP[0]), 0))
    init_chan = b_setvar(bs, LEADHP[1], LEADHP[0], vrep("내HP", V_HP))
    if_init = b_if(bs, c_chan_empty, init_chan)
    sync_hp = b_setvar(bs, "내HP", V_HP, vrep(LEADHP[1], LEADHP[0]))
    pub_atk = b_setvar(bs, LEADATK[1], LEADATK[0], vrep("내공격", V_ATK))
    C(bs, [if_init, sync_hp, pub_atk])
    if_leadsync = b_if(bs, cond_is_lead(), if_init)

    # 3) 전진: 비선두는 항상 전진(줄서기 클램프가 대기 처리). 선두는 상대 선두가 사거리 밖/죽었을 때만 전진.
    c_opp_far = cmp_op("operator_gt", opp_dist(), 22)
    c_opp_dead = b_not(bs, cmp_op("operator_gt", vrep(OPP_LEADHP[1], OPP_LEADHP[0]), 0))
    c_canadv = bool_op("operator_or", c_opp_far, c_opp_dead)
    if_lead_adv = b_if(bs, c_canadv, make_move(True))
    if_move = b_ifelse(bs, cond_is_lead(), if_lead_adv, make_move(False))

    # 4) 원거리 발사(궁수): 내종류=2 & 상대선두 살아있음 & (앞으로) 거리 0<거리<=내사거리 & 발사쿨끝 & 투사체수<투사체캡.
    #    ★ '선두' 조건 없음 — 궁수는 방패병 뒤에 서서도 사거리 안 '적 최전방(적 선두 채널 1기)'을 저격.
    #    여전히 클론 스캔 0개: 자기 y 와 '적선두y/적선두HP' 공유 채널만 읽는 O(1) 판정(적 전체 스캔 아님).
    c_isarcher = cmp_op("operator_equals", vrep("내종류", V_TYPE), 2)
    c_opp_alive = cmp_op("operator_gt", vrep(OPP_LEADHP[1], OPP_LEADHP[0]), 0)
    c_ahead = cmp_op("operator_gt", opp_dist(), 0)   # 적 선두가 내 앞(전진 방향)에 있을 때만
    c_inrange = b_not(bs, cmp_op("operator_gt", opp_dist(), vrep("내사거리", V_RNG)))
    c_firecd = b_not(bs, cmp_op("operator_gt", vrep("발사쿨", V_FIRET), 0))
    c_projroom = cmp_op("operator_lt", vrep("투사체수", V_PROJCOUNT), vrep("투사체캡", V_PROJCAP))
    c_fire = bool_op("operator_and",
                bool_op("operator_and", bool_op("operator_and", c_isarcher, c_ahead),
                        bool_op("operator_and", c_opp_alive, c_inrange)),
                bool_op("operator_and", c_firecd, c_projroom))
    inc_proj = b_changevar(bs, "투사체수", V_PROJCOUNT, 1)
    bc_fire = b_broadcast_wait(bs, FIRE[1], FIRE[0])
    set_firecd = b_setvar(bs, "발사쿨", V_FIRET, 45)   # 원거리쿨 45틱
    pfire = b_playsound(bs, "pew")
    C(bs, [inc_proj, bc_fire, set_firecd, pfire])
    if_fire = b_if(bs, c_fire, inc_proj)
    c_fpos = cmp_op("operator_gt", vrep("발사쿨", V_FIRET), 0)
    dec_fire = b_changevar(bs, "발사쿨", V_FIRET, -1)
    if_firedec = b_if(bs, c_fpos, dec_fire)

    # 5) 상대 성 도달: 성 라인 도달 → 상대성HP -= 성타격*0.05, 자폭식 삭제(총량 억제)
    if A:
        c_atcastle = b_not(bs, cmp_op("operator_lt", b_ypos(bs), castle_y - 8))
    else:
        c_atcastle = b_not(bs, cmp_op("operator_gt", b_ypos(bs), castle_y + 8))
    # 성에 도달한 유닛은 성타격만큼 한 방 딜을 주고 자폭(총량 억제). 성타격 크기로 승패 템포 조절.
    hitc = b_changevar(bs, OPP_CASTLE[1], OPP_CASTLE[0],
                       op("operator_subtract", 0, vrep("성타격", V_CASTLEHIT)))
    pc = b_playsound(bs, "crack")
    # 선두면 채널 비움(HP=0) + 선두y 스폰선 복구 → 다음 최전방이 재점유
    clear_hp_c = b_setvar(bs, LEADHP[1], LEADHP[0], 0)
    clear_y_c = b_setvar(bs, LEADY[1], LEADY[0], reset_lead)
    C(bs, [clear_hp_c, clear_y_c])
    if_clearc = b_if(bs, cond_is_lead(), clear_hp_c)
    dec_atc = b_changevar(bs, COUNT[1], COUNT[0], -1); del_atc = b_delclone(bs)
    C(bs, [hitc, pc, if_clearc, dec_atc, del_atc])
    if_atcastle = b_if(bs, c_atcastle, hitc)

    # 6) 처치: 내HP<1 → 선두면 채널 비움 + 팝 이펙트·카운트-1·삭제
    c_kill = cmp_op("operator_lt", vrep("내HP", V_HP), 1)
    clear_hp_k = b_setvar(bs, LEADHP[1], LEADHP[0], 0)
    clear_y_k = b_setvar(bs, LEADY[1], LEADY[0], reset_lead)
    C(bs, [clear_hp_k, clear_y_k])
    if_cleark = b_if(bs, cond_is_lead(), clear_hp_k)
    dec_k = b_changevar(bs, COUNT[1], COUNT[0], -1)
    swpop = b_costume(bs, f"{CS}팝")
    csz = b_changesize(bs, 12); cgh = b_changeeffect(bs, "GHOST", 22); wpop = b_wait(bs, 0.02)
    C(bs, [csz, cgh, wpop]); rep_pop = b_repeat(bs, 4, csz)
    pk = b_playsound(bs, "crack"); del_k = b_delclone(bs)
    C(bs, [if_cleark, dec_k, pk, swpop, rep_pop, del_k])
    if_kill = b_if(bs, c_kill, if_cleark)

    # forever 조립
    play_body = [if_report, if_leadsync, if_move, if_fire, if_firedec, if_atcastle, if_kill]
    C(bs, play_body)
    if_play = b_if(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1), if_report)
    w_body = b_wait(bs, 0.02)
    C(bs, [if_end, if_play, w_body])
    fe = b_forever(bs, if_end)
    C(bs, [ch, set1, set_type, pd, if_t1, set_fire0, g0, fr, show, fe])

    add_comment(bs, comments, if_report,
        "👣★ 유닛은 '전진 + 자기 y/HP를 선두 채널에 보고'만 해요. 다른 유닛을 절대 안 봐요!\n"
        "비선두는 선두 채널 y 를 못 넘게 클램프 = 줄서기(추월 없음). 선두는 교전 중 정지.\n"
        "전투는 Stage 심판이 선두 채널만 보고 처리 → 클론끼리 스캔 0개(chess-war O(n²) 회피).",
        x=470, y=380, w=410, h=170)
    return bs, comments

# ============================================================
#  화살 (투사체 클론) — side="A"(위로) / "E"(아래로)
# ============================================================
def build_arrow_blocks(side):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    A = (side == "A")
    FIRE_BR = (BR_AFIRE, "아군발사") if A else (BR_EFIRE, "적발사")
    SRC_TYPE = None
    # 발사원(궁수 선두) 위치: 선두 채널의 x=0(라인), y=선두y. 발사원 스프라이트에서 직접 좌표 못 읽으니
    # 라인X=0, y=아군선두y/적선두y 에서 발사(궁수는 선두일 때만 쏘므로 근사 정확).
    SRCY = (V_ALEADY, "아군선두y") if A else (V_ELEADY, "적선두y")
    TGT_HP = (V_ELEADHP, "적선두HP") if A else (V_ALEADHP, "아군선두HP")
    step_dir = 8 if A else -8
    costume = "화살위" if A else "화살아래"

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs, "don't rotate"); orig0 = b_setvar(bs, "복제됨", V_ARR_ISC, 0)
    swc = b_costume(bs, costume)
    C(bs, [h, hi, rs, orig0, swc])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": [FIRE_BR[1], FIRE_BR[0]]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_ARR_ISC), 0)
    cc = b_createclone(bs)
    if_c = b_if(bs, c_orig, cc)
    C(bs, [hb, if_c])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_ARR_ISC, 1)
    g0 = b_gotoxy(bs, 0, vrep(SRCY[1], SRCY[0]))
    swc2 = b_costume(bs, costume); szb = b_setsize(bs, 100); show = b_show(bs)
    # forever: 직진, 화면 밖/명중 시 삭제
    mv = b_changey(bs, step_dir)
    # 명중: 상대 선두y 근접(거리<=12) and 상대선두HP>0 → 상대선두HP -= 3, 삭제
    TGTY = (V_ELEADY, "적선두y") if A else (V_ALEADY, "아군선두y")
    if A:
        d = op("operator_subtract", vrep(TGTY[1], TGTY[0]), b_ypos(bs))
    else:
        d = op("operator_subtract", b_ypos(bs), vrep(TGTY[1], TGTY[0]))
    c_near = b_not(bs, cmp_op("operator_gt", b_abs(bs, d), 12))
    c_tgtok = cmp_op("operator_gt", vrep(TGT_HP[1], TGT_HP[0]), 0)
    c_hit = bool_op("operator_and", c_near, c_tgtok)
    dmg = b_changevar(bs, TGT_HP[1], TGT_HP[0], -3)   # 궁수 화살 3딜
    dec_p_hit = b_changevar(bs, "투사체수", V_PROJCOUNT, -1)
    del_hit = b_delclone(bs)
    C(bs, [dmg, dec_p_hit, del_hit])
    if_hit = b_if(bs, c_hit, dmg)
    # 화면 밖 y>185 or y<-185 → 삭제
    c_off = bool_op("operator_or", cmp_op("operator_gt", b_ypos(bs), 185), cmp_op("operator_lt", b_ypos(bs), -185))
    dec_p_off = b_changevar(bs, "투사체수", V_PROJCOUNT, -1)
    del_off = b_delclone(bs)
    C(bs, [dec_p_off, del_off])
    if_off = b_if(bs, c_off, dec_p_off)
    # 게임끝 정리
    c_gend = b_not(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    dec_p_g = b_changevar(bs, "투사체수", V_PROJCOUNT, -1); del_g = b_delclone(bs)
    C(bs, [dec_p_g, del_g])
    if_gend = b_if(bs, c_gend, dec_p_g)
    body = [mv, if_hit, if_off, if_gend]
    C(bs, body)
    w = b_wait(bs, 0.02)
    fe = b_forever(bs, mv)
    C(bs, [ch, set1, g0, swc2, szb, show, fe])
    C(bs, [mv, if_hit, if_off, if_gend, w])
    add_comment(bs, comments, if_hit,
        "🏹 화살은 라인 위를 직진만! 상대 선두에 명중하거나 화면 밖(y>185/<-185)이면\n"
        "즉시 delete this clone + 투사체수-1. 투사체캡(12)으로 총량도 상한 = 폭주 없음.",
        x=470, y=380, w=380, h=130)
    return bs, comments

# ============================================================
#  소환 버튼 (3버튼 각 1스프라이트) — 클릭 폴링+디바운스
# ============================================================
def build_button_blocks(kind):
    """kind: 'shield'|'archer'|'scout'"""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    conf = {
        "shield": (V_C_SHIELD, "방패_코스트", V_CDT_SHIELD, "방패_쿨타이머", V_CD_SHIELD, "방패_소환쿨", 1, "버튼방패", "버튼방패off", -120),
        "archer": (V_C_ARCHER, "궁수_코스트", V_CDT_ARCHER, "궁수_쿨타이머", V_CD_ARCHER, "궁수_소환쿨", 2, "버튼궁수", "버튼궁수off", -20),
        "scout":  (V_C_SCOUT,  "척후_코스트", V_CDT_SCOUT,  "척후_쿨타이머", V_CD_SCOUT,  "척후_소환쿨", 3, "버튼척후", "버튼척후off", 80),
    }[kind]
    COST_ID, COST_NM, CDT_ID, CDT_NM, CD_ID, CD_NM, TYPE_VAL, ON_COS, OFF_COS, xpos = conf
    ypos = -158

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, xpos, ypos); sz = b_setsize(bs, 100); fr = b_front(bs); swc = b_costume(bs, ON_COS)
    C(bs, [h, show, g, sz, fr, swc])

    # 코스튬 갱신 forever: 가능하면 ON, 아니면 OFF
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=220)
    c_gold = b_not(bs, cmp_op("operator_lt", vrep("돈", V_GOLD), vrep(COST_NM, COST_ID)))
    c_cd = b_not(bs, cmp_op("operator_gt", vrep(CDT_NM, CDT_ID), 0))
    c_cap = cmp_op("operator_lt", vrep("아군수", V_ACOUNT), vrep("유닛캡", V_UNITCAP))
    c_ok = bool_op("operator_and", bool_op("operator_and", c_gold, c_cd), c_cap)
    sw_on = b_costume(bs, ON_COS); sw_off = b_costume(bs, OFF_COS)
    if_cos = b_ifelse(bs, c_ok, sw_on, sw_off)
    w_c = b_wait(bs, 0.05)
    C(bs, [if_cos, w_c])
    fe_c = b_forever(bs, if_cos)
    C(bs, [hc, fe_c])

    # 클릭 폴링+디바운스 forever
    hp = gen(); bs[hp] = mk("event_whenflagclicked", top=True, x=470, y=220)
    # 클릭 = mouse down and touching mouse-pointer. 디바운스: 눌린 동안 대기.
    c_md = b_mousedown(bs); c_tm = b_touchingmouse(bs)
    c_click = bool_op("operator_and", c_md, c_tm)
    # 게이트: 돈>=코스트 and 소환쿨끝 and 아군수<유닛캡
    g_gold = b_not(bs, cmp_op("operator_lt", vrep("돈", V_GOLD), vrep(COST_NM, COST_ID)))
    g_cd = b_not(bs, cmp_op("operator_gt", vrep(CDT_NM, CDT_ID), 0))
    g_cap = cmp_op("operator_lt", vrep("아군수", V_ACOUNT), vrep("유닛캡", V_UNITCAP))
    g_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    g_ok = bool_op("operator_and", bool_op("operator_and", g_gold, g_cd), bool_op("operator_and", g_cap, g_play))
    # 스폰: 돈-코스트, 쿨 리셋, 소환종류 세팅, 아군수+1, 아군소환 방송, pop
    dec_gold = b_changevar(bs, "돈", V_GOLD, op("operator_subtract", 0, vrep(COST_NM, COST_ID)))
    set_cd = b_setvar(bs, CDT_NM, CDT_ID, vrep(CD_NM, CD_ID))
    set_ty = b_setvar(bs, "소환종류", V_SPTYPE, TYPE_VAL)
    inc_a = b_changevar(bs, "아군수", V_ACOUNT, 1)
    bc_a = b_broadcast_wait(bs, "아군소환", BR_ASPAWN)
    pp = b_playsound(bs, "pop")
    C(bs, [dec_gold, set_cd, set_ty, inc_a, bc_a, pp])
    if_spawn = b_if(bs, g_ok, dec_gold)
    # 디바운스: 클릭 처리 후 마우스 뗄 때까지 대기
    wu_up = b_waituntil(bs, b_not(bs, b_mousedown(bs)))
    if_click = b_if(bs, c_click, if_spawn)
    # click 처리 시 디바운스 대기 포함
    C(bs, [if_spawn, wu_up])   # if_spawn(내부) 다음 대기
    w_p = b_wait(bs, 0.02)
    C(bs, [if_click, w_p])
    fe_p = b_forever(bs, if_click)
    C(bs, [hp, fe_p])
    add_comment(bs, comments, if_click,
        "🖱️ 버튼: 클릭 폴링+디바운스(마우스 뗄 때까지 대기 → 한 번만). \n"
        "돈≥코스트 & 소환쿨끝 & 아군수<유닛캡 일 때만 스폰 + 돈 차감 + 쿨 리셋.\n"
        "조건 안 되면 회색 코스튬(비활성).",
        x=900, y=220, w=380, h=140)
    return bs, comments

# ============================================================
#  HP바 / 지갑바 (costume-fill)
# ============================================================
def build_bar_blocks(kind):
    """kind: 'ahp'|'ehp'|'gold'"""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    conf = {
        "ahp":  (V_AHP, "아군성HP", 100, -95, -168),
        "ehp":  (V_EHP, "적성HP", 100, -95, 168),
        "gold": (V_GOLD, "돈", None, 60, -158),
    }[kind]
    CUR_ID, CUR_NM, MAXVAL, xpos, ypos = conf
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, xpos, ypos); fr = b_front(bs)
    if kind == "gold":
        denom = vrep("돈상한", V_GOLDMAX)
    else:
        denom = MAXVAL
    ratio = op("operator_divide", vrep(CUR_NM, CUR_ID), denom)
    c_zero = b_not(bs, cmp_op("operator_gt", vrep(CUR_NM, CUR_ID), 0))
    set_empty = b_costume_idx(bs, op("operator_add", 0, 1))
    idx = op("operator_add", b_round(bs, op("operator_multiply", ratio, 10)), 1)
    set_fill = b_costume_idx(bs, idx)
    body = b_ifelse(bs, c_zero, set_empty, set_fill)
    w = b_wait(bs, 0.05)
    C(bs, [body, w])
    fe = b_forever(bs, body)
    C(bs, [h, show, g, fr, fe])
    return bs, comments

# ============================================================
#  결과 배너 (승/패)
# ============================================================
def build_banner_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g = b_gotoxy(bs, 0, 0); sz = b_setsize(bs, 100); fr = b_front(bs)
    C(bs, [h, hi, g, sz, fr])
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임끝", BR_END]})
    # 적성HP<=0 → 승리 else 패배
    c_win = b_not(bs, cmp_op("operator_gt", vrep("적성HP", V_EHP), 0))
    sw_win = b_costume(bs, "승리"); sw_lose = b_costume(bs, "패배")
    if_res = b_ifelse(bs, c_win, sw_win, sw_lose)
    fr2 = b_front(bs); show = b_show(bs)
    C(bs, [hb, if_res, fr2, show])
    return bs, comments

# ============================================================
#  main
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)
    def save_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f: f.write(svg)
        return m
    bg_md5 = save_svg(BG_SVG)
    a_sh = save_svg(A_SHIELD_SVG); a_ar = save_svg(A_ARCHER_SVG); a_sc = save_svg(A_SCOUT_SVG)
    e_sh = save_svg(E_SHIELD_SVG); e_ar = save_svg(E_ARCHER_SVG); e_sc = save_svg(E_SCOUT_SVG)
    pop_md5 = save_svg(POP_SVG)
    arr_up = save_svg(ARROW_UP_SVG); arr_dn = save_svg(ARROW_DOWN_SVG)
    bsh_on = save_svg(BTN_SHIELD_ON); bsh_off = save_svg(BTN_SHIELD_OFF)
    bar_on = save_svg(BTN_ARCHER_ON); bar_off = save_svg(BTN_ARCHER_OFF)
    bsc_on = save_svg(BTN_SCOUT_ON); bsc_off = save_svg(BTN_SCOUT_OFF)
    ahp_md5 = [save_svg(s) for s in AHP_BARS]; ehp_md5 = [save_svg(s) for s in EHP_BARS]; gold_md5 = [save_svg(s) for s in GOLD_BARS]
    win_md5 = save_svg(WIN_SVG); lose_md5 = save_svg(LOSE_SVG)

    def save_wav(samples):
        b = _wav_bytes(samples); m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    pop_s, pop_n = save_wav(synth_pop()); hit_s, hit_n = save_wav(synth_hit())
    pew_s, pew_n = save_wav(synth_pew()); crack_s, crack_n = save_wav(synth_crack())
    def snd(name, md5, n):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "", "rate": SND_RATE, "sampleCount": n, "md5ext": f"{md5}.wav"}
    def cos(name, md5, rx=23, ry=23):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg", "assetId": md5, "md5ext": f"{md5}.svg", "rotationCenterX": rx, "rotationCenterY": ry}

    stage_b, stage_c = build_stage_blocks()
    aunit_b, aunit_c = build_unit_blocks("A")
    eunit_b, eunit_c = build_unit_blocks("E")
    aarr_b, aarr_c = build_arrow_blocks("A")
    earr_b, earr_c = build_arrow_blocks("E")
    bsh_b, bsh_c = build_button_blocks("shield")
    bar_b, bar_c = build_button_blocks("archer")
    bsc_b, bsc_c = build_button_blocks("scout")
    ahp_b, ahp_c = build_bar_blocks("ahp")
    ehp_b, ehp_c = build_bar_blocks("ehp")
    gold_b, gold_c = build_bar_blocks("gold")
    ban_b, ban_c = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_GOLD:["돈",40], V_GOLDMAX:["돈상한",200], V_GOLDRATE:["돈충전율",4],
            V_UNITCAP:["유닛캡",8], V_PROJCAP:["투사체캡",12],
            V_AHP:["아군성HP",60], V_EHP:["적성HP",60], V_CASTLEHIT:["성타격",12],
            V_ESPAWN:["적스폰간격",3.0], V_LINEX:["라인X",0], V_ASPAWNY:["아군스폰y",-110], V_ESPAWNY:["적스폰y",110],
            V_ALEADY:["아군선두y",-180], V_ELEADY:["적선두y",180], V_ALEADHP:["아군선두HP",0], V_ELEADHP:["적선두HP",0],
            V_ALEADYRAW:["아군선두y원",-180], V_ELEADYRAW:["적선두y원",180],
            V_ALEADATK:["아군선두공격",0], V_ELEADATK:["적선두공격",0],
            V_ACOUNT:["아군수",0], V_ECOUNT:["적수",0], V_STATE:["게임상태",1], V_PROJCOUNT:["투사체수",0],
            V_C_SHIELD:["방패_코스트",20], V_C_ARCHER:["궁수_코스트",50], V_C_SCOUT:["척후_코스트",15],
            V_CD_SHIELD:["방패_소환쿨",30], V_CD_ARCHER:["궁수_소환쿨",100], V_CD_SCOUT:["척후_소환쿨",25],
            V_SPTYPE:["소환종류",0], V_ESPTYPE:["적소환종류",0],
            V_CDT_SHIELD:["방패_쿨타이머",0], V_CDT_ARCHER:["궁수_쿨타이머",0], V_CDT_SCOUT:["척후_쿨타이머",0],
            V_ESPT:["적스폰타이머",1.0], V_MELEET_A:["근접쿨_아군",0], V_MELEET_E:["근접쿨_적",0],
        },
        "lists": {},
        "broadcasts": {
            BR_START:"게임시작", BR_ASPAWN:"아군소환", BR_ESPAWN:"적소환",
            BR_AFIRE:"아군발사", BR_EFIRE:"적발사", BR_END:"게임끝",
        },
        "blocks": stage_b, "comments": stage_c, "currentCostume": 0,
        "costumes": [{"name":"전장","dataFormat":"svg","assetId":bg_md5,"md5ext":f"{bg_md5}.svg","rotationCenterX":240,"rotationCenterY":180}],
        "sounds": [snd("pop", pop_s, pop_n), snd("hit", hit_s, hit_n), snd("pew", pew_s, pew_n), snd("crack", crack_s, crack_n)],
        "volume":100,"layerOrder":0,"tempo":60,"videoTransparency":50,"videoState":"on","textToSpeechLanguage":None
    }
    def unit_target(name, blocks, cmts, costumes, order):
        return {"isStage": False, "name": name,
                "variables": {V_ISC:["복제됨",0], V_TYPE:["내종류",1], V_HP:["내HP",30], V_SPD:["내속도",1], V_ATK:["내공격",4], V_RNG:["내사거리",0], V_FIRET:["발사쿨",0]},
                "lists": {}, "broadcasts": {}, "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": costumes, "sounds": [snd("hit", hit_s, hit_n), snd("crack", crack_s, crack_n), snd("pew", pew_s, pew_n)],
                "volume":100,"layerOrder":order,"visible":False,"x":0,"y":0,"size":90,"direction":0,"draggable":False,"rotationStyle":"don't rotate"}
    aunit = unit_target("아군유닛", aunit_b, aunit_c,
        [cos("아방패", a_sh), cos("아궁수", a_ar), cos("아척후", a_sc), cos("아팝", pop_md5)], 3)
    eunit = unit_target("적유닛", eunit_b, eunit_c,
        [cos("적방패", e_sh), cos("적궁수", e_ar), cos("적척후", e_sc), cos("적팝", pop_md5)], 4)
    def arrow_target(name, blocks, cmts, up, order):
        return {"isStage": False, "name": name, "variables": {V_ARR_ISC:["복제됨",0]},
                "lists": {}, "broadcasts": {}, "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos("화살위" if up else "화살아래", arr_up if up else arr_dn, 6, 12)],
                "sounds": [snd("pew", pew_s, pew_n)],
                "volume":100,"layerOrder":order,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    aarr = arrow_target("아군화살", aarr_b, aarr_c, True, 5)
    earr = arrow_target("적화살", earr_b, earr_c, False, 6)
    def button_target(name, blocks, cmts, on_md5, off_md5, x, order):
        return {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos(name, on_md5, 40, 23), cos(name+"off", off_md5, 40, 23)],
                "sounds": [snd("pop", pop_s, pop_n)],
                "volume":100,"layerOrder":order,"visible":True,"x":x,"y":-158,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    bsh = button_target("버튼방패", bsh_b, bsh_c, bsh_on, bsh_off, -120, 7)
    bar = button_target("버튼궁수", bar_b, bar_c, bar_on, bar_off, -20, 8)
    bsc = button_target("버튼척후", bsc_b, bsc_c, bsc_on, bsc_off, 80, 9)
    def bar_target(name, blocks, cmts, md5s, x, y, order):
        return {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos(f"{name}_{i}", md5s[i], 85, 11) for i in range(11)], "sounds": [],
                "volume":100,"layerOrder":order,"visible":True,"x":x,"y":y,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    ahpbar = bar_target("아군성바", ahp_b, ahp_c, ahp_md5, -95, -168, 10)
    ehpbar = bar_target("적성바", ehp_b, ehp_c, ehp_md5, -95, 168, 10)
    goldbar = bar_target("지갑바", gold_b, gold_c, gold_md5, 60, -158, 10)
    banner = {
        "isStage": False, "name": "결과배너", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ban_b, "comments": ban_c, "currentCostume": 0,
        "costumes": [{"name":"승리","bitmapResolution":1,"dataFormat":"svg","assetId":win_md5,"md5ext":f"{win_md5}.svg","rotationCenterX":180,"rotationCenterY":70},
                     {"name":"패배","bitmapResolution":1,"dataFormat":"svg","assetId":lose_md5,"md5ext":f"{lose_md5}.svg","rotationCenterX":180,"rotationCenterY":70}],
        "sounds": [], "volume":100,"layerOrder":12,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }

    monitors = [
        {"id": V_GOLD, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"돈"},"spriteName":None,
         "value":40,"width":0,"height":0,"x":5,"y":5,"visible":True,"sliderMin":0,"sliderMax":200,"isDiscrete":True},
        {"id": V_ACOUNT, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"아군수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":30,"visible":True,"sliderMin":0,"sliderMax":8,"isDiscrete":True},
        {"id": V_ECOUNT, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"적수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":55,"visible":True,"sliderMin":0,"sliderMax":8,"isDiscrete":True},
        {"id": V_PROJCOUNT, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"투사체수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":80,"visible":True,"sliderMin":0,"sliderMax":12,"isDiscrete":True},
    ]
    project = {
        "targets": [stage, aunit, eunit, aarr, earr, bsh, bar, bsc, ahpbar, ehpbar, goldbar, banner],
        "monitors": monitors, "extensions": [],
        "meta": {"semver":"3.0.0","vm":"13.7.4-svg","agent":"lane-siege-builder"}
    }
    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f: json.dump(project, f, ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK): zf.write(f"{WORK}/{fn}", fn)
    with open(pj, "r", encoding="utf-8") as f: json.load(f)
    total = 0
    print(f"wrote {OUTPUT}")
    for nm, b in [("stage",stage_b),("아군유닛",aunit_b),("적유닛",eunit_b),("아군화살",aarr_b),("적화살",earr_b),
                  ("버튼방패",bsh_b),("버튼궁수",bar_b),("버튼척후",bsc_b),("아군성바",ahp_b),("적성바",ehp_b),("지갑바",gold_b),("결과배너",ban_b)]:
        print(f"  {nm:8s}: {len(b)} blocks"); total += len(b)
    print(f"  총 블록 수: {total}")

if __name__ == "__main__":
    main()
