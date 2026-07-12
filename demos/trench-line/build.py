#!/usr/bin/env python3
"""참호전선 (trench-line) — 3구역 참호 총격전 데모.

세로 3구역(좌/중/우). 각 구역이 독립 전선(theater)이다. 화면 아래=아군 본진,
위=적 본진. 유닛은 배치되면 자기 구역 전선 부근에 자리 잡고 같은 구역의 적을
원거리 사격한다. 명중하면 데미지 숫자가 팝업으로 떠올랐다 사라진다(핵심 연출).
플레이어는 유닛 버튼을 누른 뒤 좌/중/우 구역을 클릭해 그 구역에 투입한다.
각 구역 전선은 양측 전력차로 밀고 밀린다. 전선을 적 본진까지 밀면 돌파 →
적 본진 HP 감소. 적 본진 HP 0 → 승리, 아군 본진 HP 0 → 패배.

★ 존재 이유 = chess-war 실패(per-unit 듀얼 O(n²) 붕괴) 재발 방지 (1급 원칙).
  "구역 분할 + 이벤트 기반 공유 카운터 + Stage 상수시간 심판" 모델.
  - 유닛 클론은 다른 유닛 클론을 touching/sensing_of/리스트 순회로 절대 참조 안 함.
    유닛은 이동·선두채널 갱신·사격연출·팝업요청·자기 피격/사망 보고만.
  - 전투 판정은 Stage 심판 1곳. 구역 6전력 + 3전선 + 6선두채널(전부 리스트,
    index 1/2/3)만 보고 심판 루프는 1~3 반복(구역 3개 고정 = 상수 시간).
  - 전력은 이벤트 기반: 스폰 시 L_아군전력[z]+=전력, 사망 시 -=.
  - 성능 캡: 구역캡6 / 전체캡24 / 팝업캡20(짧은 수명 자동삭제).
  - 사격은 히트스캔(탄 클론 없음) + 트레이서 점멸 + 데미지 팝업.

베이스: demos/lane-siege/build.py (b_* 헬퍼·synth 사운드·costume-fill 바·클론
스포너·복제됨 가드·선두 채널 기법·소환 게이트·승패 배너). 전투 모델을 단일
라인 선두 교전 → 구역 분할 심판으로 교체.
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "참호전선.sb3")

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

def synth_pew(rate=SND_RATE):
    """사격 'tk' — 아주 짧은 클릭(연사 겹침 부담↓), 0.03초."""
    N = int(rate * 0.03); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 90)
        out.append(math.sin(2 * math.pi * 1900 * t) * env * 0.4)
    return out

def synth_tick(rate=SND_RATE):
    """데미지 팝업 'tick' — 고음 짧은 점, 0.03초."""
    N = int(rate * 0.03); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 70)
        out.append(math.sin(2 * math.pi * 2600 * t) * env * 0.35)
    return out

def synth_crack(rate=SND_RATE):
    """돌파/본진 타격 '펑' — 노이즈+저음 thump, 0.13초. 결정적."""
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
#  좌표: scratchX = svgX-240, scratchY = 180-svgY.
#  3구역: 좌 x=-140, 중 x=0, 우 x=140. 적진y=150, 아군진y=-130. 전선 중앙 y≈10.
# ============================================================
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs><linearGradient id="grd" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#8A3B3B"/><stop offset="0.5" stop-color="#6E5C48"/>
    <stop offset="1" stop-color="#39537F"/></linearGradient></defs>
  <rect width="480" height="360" fill="url(#grd)"/>
  <!-- 적 진영(위) 붉은 영역 (적진y=150 → svgY=30) -->
  <rect x="0" y="0" width="480" height="60" fill="#6E2626" opacity="0.55"/>
  <!-- 아군 진영(아래) 파란 영역 (아군진y=-130 → svgY=310) -->
  <rect x="0" y="300" width="480" height="60" fill="#26406E" opacity="0.55"/>
  <!-- 노맨스랜드 중앙 띠 (전선 초기 y=10 → svgY=170) -->
  <rect x="0" y="150" width="480" height="40" fill="#000000" opacity="0.12"/>
  <!-- 3구역 세로 구분선: 구역폭 160 → 경계 svgX=160,320 -->
  <line x1="160" y1="55" x2="160" y2="305" stroke="#FFFFFF" stroke-width="3" stroke-dasharray="8 8" opacity="0.3"/>
  <line x1="320" y1="55" x2="320" y2="305" stroke="#FFFFFF" stroke-width="3" stroke-dasharray="8 8" opacity="0.3"/>
  <!-- 구역 라벨 -->
  <text x="80"  y="188" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="15" opacity="0.35">좌</text>
  <text x="240" y="188" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="15" opacity="0.35">중</text>
  <text x="400" y="188" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="15" opacity="0.35">우</text>
  <!-- 적 본진(상단) -->
  <rect x="20" y="4" width="440" height="22" fill="#5A1E1E" stroke="#3A1010" stroke-width="2"/>
  <!-- 아군 본진(하단) -->
  <rect x="20" y="334" width="440" height="22" fill="#1E3A5A" stroke="#0F2038" stroke-width="2"/>
  <rect x="3" y="3" width="474" height="354" rx="8" fill="none" stroke="#000000" stroke-width="3" opacity="0.3"/>
</svg>"""

# -------- 유닛 3코스튬 + 발사(총구 점멸) 코스튬 --------
# kind: 1=소총병 2=제압사수 3=저격수. 아군=파랑 위향 / 적=빨강 아래향.
def _unit_svg(fill, stroke, kind, firing=False, up=True):
    body = f'<rect x="15" y="20" width="16" height="18" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    head = f'<circle cx="23" cy="14" r="7" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    # 총구 방향
    gy1, gy2 = (10, 2) if up else (36, 44)
    gun = f'<line x1="31" y1="23" x2="31" y2="{gy1}" stroke="#2A2A2A" stroke-width="2.5"/>'
    extra = ""
    if kind == 2:  # 제압사수: 넓은 몸통 + 삼각대
        body = f'<rect x="12" y="20" width="22" height="18" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        gun = f'<line x1="34" y1="24" x2="34" y2="{gy1}" stroke="#1A1A1A" stroke-width="3.5"/>'
    if kind == 3:  # 저격수: 긴 총열
        gun = f'<line x1="31" y1="23" x2="31" y2="{gy2}" stroke="#2A2A2A" stroke-width="2"/><circle cx="31" cy="{(gy1+gy2)//2}" r="1.6" fill="#111"/>'
    muzzle = ""
    if firing:
        my = gy2 if kind == 3 else gy1
        muzzle = f'<circle cx="{34 if kind==2 else 31}" cy="{my}" r="4.5" fill="#FFE082" opacity="0.9"/><circle cx="{34 if kind==2 else 31}" cy="{my}" r="2.2" fill="#FFF59D"/>'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
  <ellipse cx="23" cy="43" rx="11" ry="3" fill="#000" opacity="0.22"/>
  {body}{head}{gun}{extra}{muzzle}
</svg>"""

A_RIFLE   = _unit_svg("#3F72C4", "#1C3E7A", 1, up=True)
A_RIFLE_F = _unit_svg("#3F72C4", "#1C3E7A", 1, firing=True, up=True)
A_MG      = _unit_svg("#4B86D8", "#1C5286", 2, up=True)
A_MG_F    = _unit_svg("#4B86D8", "#1C5286", 2, firing=True, up=True)
A_SNIPER  = _unit_svg("#6EC1E8", "#2A7BA0", 3, up=True)
A_SNIPER_F= _unit_svg("#6EC1E8", "#2A7BA0", 3, firing=True, up=True)
E_RIFLE   = _unit_svg("#C44242", "#7A1C1C", 1, up=False)
E_RIFLE_F = _unit_svg("#C44242", "#7A1C1C", 1, firing=True, up=False)
E_MG      = _unit_svg("#D86A4B", "#86341C", 2, up=False)
E_MG_F    = _unit_svg("#D86A4B", "#86341C", 2, firing=True, up=False)
E_SNIPER  = _unit_svg("#E89A6E", "#A05A2A", 3, up=False)
E_SNIPER_F= _unit_svg("#E89A6E", "#A05A2A", 3, firing=True, up=False)

POP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
  <circle cx="23" cy="23" r="16" fill="#FFD54F" opacity="0.55"/>
  <circle cx="23" cy="23" r="9" fill="#FFF176"/>
</svg>"""

# -------- 데미지 팝업 (숫자 costume — say 금지, 강도별 색 3단) --------
# 약(노랑)/중(주황)/강(빨강). 숫자는 3단 대표값(간단히 costume 으로).
def _dmg_svg(color, txt):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="44" height="30" viewBox="0 0 44 30">
  <text x="22" y="24" text-anchor="middle" font-family="Arial" font-size="26" font-weight="bold"
    fill="{color}" stroke="#000000" stroke-width="1.2" paint-order="stroke">{txt}</text>
</svg>"""
DMG_LOW  = _dmg_svg("#FFEB3B", "3")   # 약
DMG_MID  = _dmg_svg("#FF9800", "6")   # 중
DMG_HIGH = _dmg_svg("#FF3B3B", "9")   # 강

# -------- 트레이서(사격 짧은 선) 아군=위 / 적=아래 --------
TRACER_UP = """<svg xmlns="http://www.w3.org/2000/svg" width="6" height="40" viewBox="0 0 6 40">
  <line x1="3" y1="38" x2="3" y2="2" stroke="#FFF176" stroke-width="2.5" opacity="0.9"/>
</svg>"""
TRACER_DN = """<svg xmlns="http://www.w3.org/2000/svg" width="6" height="40" viewBox="0 0 6 40">
  <line x1="3" y1="2" x2="3" y2="38" stroke="#FFCC80" stroke-width="2.5" opacity="0.9"/>
</svg>"""

# -------- 소환 버튼 (선택/비선택/비활성 = 3코스튬) --------
def _btn_svg(icon, cost, color, mode):
    # mode: 'sel'(선택 하이라이트) 'on'(가능) 'off'(회색)
    if mode == "off":
        bg, op, stroke = "#555555", "0.5", "#888888"
    elif mode == "sel":
        bg, op, stroke = color, "1", "#FFF176"
    else:
        bg, op, stroke = color, "1", "#FFFFFF"
    sw = "4" if mode == "sel" else "2"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="92" height="40" viewBox="0 0 92 40">
  <rect x="2" y="2" width="88" height="36" rx="8" fill="{bg}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>
  <text x="24" y="27" text-anchor="middle" font-family="Arial" font-size="20">{icon}</text>
  <text x="66" y="18" text-anchor="middle" font-family="Arial" font-size="14" font-weight="bold" fill="#FFFFFF">{cost}</text>
  <text x="66" y="33" text-anchor="middle" font-family="Arial" font-size="9" fill="#FFFFFF">코스트</text>
</svg>"""
BTN_RIFLE_SEL = _btn_svg("\U0001F52B", "30", "#2E7D32", "sel"); BTN_RIFLE_ON = _btn_svg("\U0001F52B", "30", "#2E7D32", "on"); BTN_RIFLE_OFF = _btn_svg("\U0001F52B", "30", "#2E7D32", "off")
BTN_MG_SEL    = _btn_svg("⚙",     "55", "#1565C0", "sel"); BTN_MG_ON    = _btn_svg("⚙",     "55", "#1565C0", "on"); BTN_MG_OFF    = _btn_svg("⚙",     "55", "#1565C0", "off")
BTN_SNIPE_SEL = _btn_svg("\U0001F3AF", "50", "#EF6C00", "sel"); BTN_SNIPE_ON = _btn_svg("\U0001F3AF", "50", "#EF6C00", "on"); BTN_SNIPE_OFF = _btn_svg("\U0001F3AF", "50", "#EF6C00", "off")

# -------- HP바 / 지갑바 costume-fill 11단 --------
def _bar_svg(step, fill, label):
    w = int(round(120 * step / 10))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="170" height="20" viewBox="0 0 170 20">
  <text x="2" y="15" font-family="Arial" font-size="12">{label}</text>
  <rect x="30" y="3" width="124" height="14" rx="4" fill="#000000" opacity="0.4"/>
  <rect x="32" y="5" width="{w}" height="10" rx="3" fill="{fill}"/>
  <rect x="30" y="3" width="124" height="14" rx="4" fill="none" stroke="#FFFFFF" stroke-width="1.5" opacity="0.8"/>
</svg>"""
AHP_BARS  = [_bar_svg(s, "#42A5F5", "\U0001F3F0") for s in range(11)]
EHP_BARS  = [_bar_svg(s, "#EF5350", "\U0001F3F0") for s in range(11)]
GOLD_BARS = [_bar_svg(s, "#FFCA28", "\U0001F4B0") for s in range(11)]

# -------- 승/패 배너 --------
WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="140" viewBox="0 0 360 140">
  <rect x="5" y="5" width="350" height="130" rx="14" fill="#0D3B0D" opacity="0.9" stroke="#66BB6A" stroke-width="5"/>
  <text x="180" y="70" text-anchor="middle" fill="#A5D6A7" font-family="Arial" font-size="44" font-weight="bold">승리!</text>
  <text x="180" y="108" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="16">적 본진 돌파 — 깃발로 재도전</text>
</svg>"""
LOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="140" viewBox="0 0 360 140">
  <rect x="5" y="5" width="350" height="130" rx="14" fill="#3B0D0D" opacity="0.9" stroke="#EF5350" stroke-width="5"/>
  <text x="180" y="70" text-anchor="middle" fill="#EF9A9A" font-family="Arial" font-size="44" font-weight="bold">패배...</text>
  <text x="180" y="108" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="16">아군 본진 함락 — 깃발로 재도전</text>
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

# ---- 리스트 헬퍼 (index 1/2/3 = 좌/중/우) ----
def b_listitem(bs, lname, lid, index):
    """리스트[index] 리포터."""
    bid = gen()
    ins = {"INDEX": slot(index) if (isinstance(index,str) and index in bs) else num(index)}
    bs[bid] = mk("data_itemoflist", inputs=ins, fields={"LIST": [lname, lid]})
    if isinstance(index,str) and index in bs: bs[index]["parent"] = bid
    return bid
def b_listreplace(bs, lname, lid, index, value):
    bid = gen(); ins = {}
    ins["INDEX"] = slot(index) if (isinstance(index,str) and index in bs) else num(index)
    ins["ITEM"]  = slot(value) if (isinstance(value,str) and value in bs) else (text_lit(value) if isinstance(value,str) else num(value))
    bs[bid] = mk("data_replaceitemoflist", inputs=ins, fields={"LIST": [lname, lid]})
    if isinstance(index,str) and index in bs: bs[index]["parent"] = bid
    if isinstance(value,str) and value in bs: bs[value]["parent"] = bid
    return bid
def b_listadd(bs, lname, lid, value):
    bid = gen()
    it = slot(value) if (isinstance(value,str) and value in bs) else (num(value) if not isinstance(value,str) else text_lit(value))
    bs[bid] = mk("data_addtolist", inputs={"ITEM": it}, fields={"LIST": [lname, lid]})
    if isinstance(value,str) and value in bs: bs[value]["parent"] = bid
    return bid
def b_listdelall(bs, lname, lid):
    bid = gen(); bs[bid] = mk("data_deletealloflist", fields={"LIST": [lname, lid]}); return bid

def b_mousedown(bs):
    bid = gen(); bs[bid] = mk("sensing_mousedown"); return bid
def b_touchingmouse(bs):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu", fields={"TOUCHINGOBJECTMENU": ["_mouse_", None]}, shadow=True)
    t = gen(); bs[t] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, m]}); bs[m]["parent"] = t; return t
def b_mousex(bs):
    bid = gen(); bs[bid] = mk("sensing_mousex"); return bid
def b_mousey(bs):
    bid = gen(); bs[bid] = mk("sensing_mousey"); return bid

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
def b_setx(bs, v):
    bid = gen(); ins = {"X": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_setx", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_ypos(bs):
    bid = gen(); bs[bid] = mk("motion_yposition"); return bid
def b_xpos(bs):
    bid = gen(); bs[bid] = mk("motion_xposition"); return bid
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
# ---- 리스트 (index 1=좌, 2=중, 3=우) ----
L_APOW="listAPow01"; L_EPOW="listEPow02"; L_FRONT="listFront03"
L_ACNT="listACnt04"; L_ECNT="listECnt05"; L_ALEAD="listALead06"; L_ELEAD="listELead07"

# ---- 스칼라 전역 ----
V_GOLD="varGold01"; V_GOLDMAX="varGoldMax02"; V_GOLDRATE="varGoldRate03"
V_ZONECAP="varZoneCap04"; V_TOTALCAP="varTotalCap05"
V_POPCAP="varPopCap06"; V_POPCNT="varPopCnt07"
V_AHP="varAHP08"; V_EHP="varEHP09"
V_BREAKDMG="varBreakDmg10"; V_FRONTSPD="varFrontSpd11"; V_KILLGAP="varKillGap12"
V_ESPAWNGAP="varESpawnGap13"; V_ESPAWNT="varESpawnT14"
V_ENEMYY="varEnemyY15"; V_ALLYY="varAllyY16"
V_ATOTAL="varATotal17"; V_ETOTAL="varETotal18"; V_STATE="varState19"
# 종류별 스탯
V_C_RIFLE="varCRifle20"; V_C_MG="varCMg21"; V_C_SNIPE="varCSnipe22"
V_CD_RIFLE="varCdRifle23"; V_CD_MG="varCdMg24"; V_CD_SNIPE="varCdSnipe25"
V_CDT_RIFLE="varCdtRifle26"; V_CDT_MG="varCdtMg27"; V_CDT_SNIPE="varCdtSnipe28"
# 소환 채널
V_PENDTYPE="varPendType29"; V_SPZONE="varSpZone30"; V_SPTYPE="varSpType31"
V_ESPZONE="varESpZone32"; V_ESPTYPE="varESpType33"
# 팝업 요청 채널
V_POPX="varPopX34"; V_POPY="varPopY35"; V_POPVAL="varPopVal36"
# 심판 → 유닛 피격 신호(구역별 진영별): 값 = 대상 선두 y (그 좌표 선두가 맞음)
V_AHITZ="varAHitZone37"; V_EHITZ="varEHitZone38"  # 이번 틱 피격 구역(0=없음)
V_HITDMG="varHitDmg39"; V_KILLT="varKillT40"      # 피격 데미지 / 선두처치 타이머
V_ZI="varJudgeZ41"                                # 심판 루프 카운터 z(1~3)
V_FRONT_MON=L_FRONT                               # 모니터용 별칭

# ---- 클론-로컬(유닛) ----
V_ISC="varIsClone"; V_ZONE="varMyZone"; V_TYPE="varMyType"; V_POW="varMyPow"
V_HP="varMyHP"; V_MAXHP="varMyMaxHP"; V_RNG="varMyRange"; V_FIRET="varFireT"
# ---- 클론-로컬(팝업) ----
V_POP_ISC="varPopIsClone"

# ---- 방송 ----
BR_START="brStart01"; BR_ASPAWN="brASpawn02"; BR_ESPAWN="brESpawn03"
BR_POP="brPop04"; BR_END="brEnd05"

# 구역 상수 x: 좌=-140 중=0 우=140. 구역폭 160.
ZONE_X = {1: -140, 2: 0, 3: 140}
ENEMY_Y = 150; ALLY_Y = -130; FRONT_INIT = 10

# 종류 상수: 1=소총병 2=제압사수 3=저격수
# 스탯: (코스트, 소환쿨틱, 전력, HP, 사거리, 소환쿨명, ...) — 아래 stage init 참조.

# ============================================================
#  STAGE — 초기화 + 돈충전 + 적AI + ★구역 심판 + 승패
# ============================================================
def build_stage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 → 전역 초기화 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [h]
    def s(name, vid, val): seq.append(b_setvar(bs, name, vid, val))
    # 경제/캡
    s("돈", V_GOLD, 40); s("돈상한", V_GOLDMAX, 200); s("돈충전율", V_GOLDRATE, 5)
    s("구역캡", V_ZONECAP, 6); s("전체캡", V_TOTALCAP, 24)
    s("팝업캡", V_POPCAP, 20); s("팝업수", V_POPCNT, 0)
    # 본진/전투
    s("아군본진HP", V_AHP, 100); s("적본진HP", V_EHP, 100)
    s("돌파딜", V_BREAKDMG, 6); s("전선속도", V_FRONTSPD, 0.5); s("선두처치주기", V_KILLGAP, 22)
    s("적스폰간격", V_ESPAWNGAP, 2.5); s("적스폰타이머", V_ESPAWNT, 1.5)
    s("적진y", V_ENEMYY, ENEMY_Y); s("아군진y", V_ALLYY, ALLY_Y)
    # 종류별 스탯: 코스트 / 소환쿨(틱, 0.02s 루프 기준 → 초×50)
    s("소총_코스트", V_C_RIFLE, 30); s("제압_코스트", V_C_MG, 55); s("저격_코스트", V_C_SNIPE, 50)
    s("소총_소환쿨", V_CD_RIFLE, 35); s("제압_소환쿨", V_CD_MG, 90); s("저격_소환쿨", V_CD_SNIPE, 100)
    s("소총_쿨타이머", V_CDT_RIFLE, 0); s("제압_쿨타이머", V_CDT_MG, 0); s("저격_쿨타이머", V_CDT_SNIPE, 0)
    # 소환 채널
    s("대기소환종류", V_PENDTYPE, 0); s("소환구역", V_SPZONE, 0); s("소환종류", V_SPTYPE, 0)
    s("적소환구역", V_ESPZONE, 0); s("적소환종류", V_ESPTYPE, 0)
    # 팝업 채널
    s("팝업x", V_POPX, 0); s("팝업y", V_POPY, 0); s("팝업값", V_POPVAL, 1)
    # 피격 신호
    s("아군피격구역", V_AHITZ, 0); s("적피격구역", V_EHITZ, 0); s("피격딜", V_HITDMG, 0); s("선두처치타이머", V_KILLT, 0)
    # 카운트/상태
    s("아군총수", V_ATOTAL, 0); s("적총수", V_ETOTAL, 0); s("게임상태", V_STATE, 1)
    # 리스트 3칸 초기화(좌/중/우)
    def initlist(lname, lid, val):
        seq.append(b_listdelall(bs, lname, lid))
        for _ in range(3):
            seq.append(b_listadd(bs, lname, lid, val))
    initlist("L_아군전력", L_APOW, 0); initlist("L_적전력", L_EPOW, 0)
    initlist("L_전선", L_FRONT, FRONT_INIT)
    initlist("L_아군수", L_ACNT, 0); initlist("L_적수", L_ECNT, 0)
    initlist("L_아군선두y", L_ALEAD, ALLY_Y); initlist("L_적선두y", L_ELEAD, ENEMY_Y)
    seq.append(b_wait(bs, 0.2))
    seq.append(b_broadcast(bs, "게임시작", BR_START))
    C(bs, seq)
    add_comment(bs, comments, seq[1],
        "\U0001F6E0️ 개조 손잡이: 돈·캡·본진HP·유닛 스탯·전선속도·돌파딜 전부 여기 숫자만 바꾸면 게임이 달라져요.\n"
        "구역캡6·전체캡24·팝업캡20 = chess-war O(n²) 붕괴를 막는 성능 상한(수치로 못박음).\n"
        "리스트 7종(L_아군전력/L_적전력/L_전선/수/선두y)은 전부 index 1=좌 2=중 3=우.",
        x=470, y=20, w=380, h=150)

    # ===== (B) 돈 자동 충전 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    add_g = b_changevar(bs, "돈", V_GOLD, op("operator_multiply", vrep("돈충전율", V_GOLDRATE), 0.1))
    c_over = cmp_op("operator_gt", vrep("돈", V_GOLD), vrep("돈상한", V_GOLDMAX))
    set_cap = b_setvar(bs, "돈", V_GOLD, vrep("돈상한", V_GOLDMAX))
    if_over = b_if(bs, c_over, set_cap)
    C(bs, [add_g, if_over])
    c_playg = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_playg = b_if(bs, c_playg, add_g)
    w_g = b_wait(bs, 0.1)
    C(bs, [if_playg, w_g])
    fe_g = b_forever(bs, if_playg)
    C(bs, [hb, fe_g])
    add_comment(bs, comments, add_g,
        "\U0001F4B0 돈은 시간이 지나면 자동으로 차올라요(돈충전율/초). 상한(돈상한)에서 멈춤.\n"
        "언제·어느 구역에 뭘 뽑을지 = 이 데모의 유일한 전략!",
        x=470, y=320, w=350, h=110)

    # ===== (C) 소환 쿨타이머 감소 forever =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=470, y=320,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    def dec_cd(name, vid):
        c_pos = cmp_op("operator_gt", vrep(name, vid), 0)
        dec = b_changevar(bs, name, vid, -1)
        return b_if(bs, c_pos, dec)
    d1 = dec_cd("소총_쿨타이머", V_CDT_RIFLE); d2 = dec_cd("제압_쿨타이머", V_CDT_MG); d3 = dec_cd("저격_쿨타이머", V_CDT_SNIPE)
    d4 = dec_cd("선두처치타이머", V_KILLT)
    w_c = b_wait(bs, 0.02)
    C(bs, [d1, d2, d3, d4, w_c])
    fe_c = b_forever(bs, d1)
    C(bs, [hc, fe_c])

    # ===== (D) 적 AI 스폰 타이머 forever =====
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=620,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    dec_t = b_changevar(bs, "적스폰타이머", V_ESPAWNT, -0.1)
    # 랜덤 구역 선택 → 그 구역 적수<구역캡 & 적총수<전체캡 이면 적소환
    rnd_z = op("operator_random", 1, 3, key1="FROM", key2="TO")
    set_ez = b_setvar(bs, "적소환구역", V_ESPZONE, rnd_z)
    rnd_t = op("operator_random", 1, 3, key1="FROM", key2="TO")
    set_et = b_setvar(bs, "적소환종류", V_ESPTYPE, rnd_t)
    # 조건: 타이머<=0 and 적수[z]<구역캡 and 적총수<전체캡
    c_t0 = b_not(bs, cmp_op("operator_gt", vrep("적스폰타이머", V_ESPAWNT), 0))
    zc = b_listitem(bs, "L_적수", L_ECNT, vrep("적소환구역", V_ESPZONE))
    c_zroom = cmp_op("operator_lt", zc, vrep("구역캡", V_ZONECAP))
    c_troom = cmp_op("operator_lt", vrep("적총수", V_ETOTAL), vrep("전체캡", V_TOTALCAP))
    c_room = bool_op("operator_and", c_zroom, c_troom)
    c_sp = bool_op("operator_and", c_t0, c_room)
    bc_e = b_broadcast_wait(bs, "적소환", BR_ESPAWN)
    reset_t = b_setvar(bs, "적스폰타이머", V_ESPAWNT, vrep("적스폰간격", V_ESPAWNGAP))
    # if_sp 내부: 종류 랜덤 세팅 → 방송 → 타이머 리셋
    C(bs, [set_et, bc_e, reset_t])
    if_sp = b_if(bs, c_sp, set_et)
    # 매틱: 타이머 감소, 구역 미리 랜덤 선택(조건 평가용), 조건 만족 시 소환
    C(bs, [dec_t, set_ez, if_sp])
    c_playe = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_playe = b_if(bs, c_playe, dec_t)
    w_e = b_wait(bs, 0.1)
    C(bs, [if_playe, w_e])
    fe_e = b_forever(bs, if_playe)
    C(bs, [hd, fe_e])
    add_comment(bs, comments, if_sp,
        "\U0001F916 적 AI: 적스폰간격마다 랜덤 구역에 유닛 1기 자동 소환.\n"
        "그 구역 적수[z]<구역캡 & 적총수<전체캡 일 때만 → 총량 폭주 방지.",
        x=470, y=620, w=350, h=110)

    # ===== (E) ★ 구역 전선 심판 forever (chess-war 회피 핵심) =====
    # 클론끼리 스캔 0개. 구역 1~3 반복(상수) — 각 구역: 전력차로 전선 이동,
    # 돌파 시 본진 딜, 열세 구역 선두 처치 신호 발행. 오직 리스트(전력/전선/선두y)만 본다.
    he = gen(); bs[he] = mk("event_whenbroadcastreceived", top=True, x=470, y=620,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # 루프 카운터 z 는 변수 V_ZI(심판z)로. repeat 3 안에서 z=1..3.
    # ---- (E-1) 선두 처치 신호 루프(주기 게이트): 열세 구역에 피격구역 신호만 발행 ----
    # diff<0(적 우세)→아군 열세→아군피격구역=z. diff>0→적피격구역=z. 전선 이동은 아래 매틱 루프가 담당.
    set_z1 = b_setvar(bs, "심판z", V_ZI, 1)
    apow2 = b_listitem(bs, "L_아군전력", L_APOW, vrep("심판z", V_ZI))
    epow2 = b_listitem(bs, "L_적전력", L_EPOW, vrep("심판z", V_ZI))
    c_a_weak = cmp_op("operator_lt", apow2, epow2)
    set_ahit = b_setvar(bs, "아군피격구역", V_AHITZ, vrep("심판z", V_ZI))
    if_ahit = b_if(bs, c_a_weak, set_ahit)
    apow3 = b_listitem(bs, "L_아군전력", L_APOW, vrep("심판z", V_ZI))
    epow3 = b_listitem(bs, "L_적전력", L_EPOW, vrep("심판z", V_ZI))
    c_e_weak = cmp_op("operator_gt", apow3, epow3)
    set_ehit = b_setvar(bs, "적피격구역", V_EHITZ, vrep("심판z", V_ZI))
    if_ehit = b_if(bs, c_e_weak, set_ehit)
    inc_z = b_changevar(bs, "심판z", V_ZI, 1)
    zbody = [if_ahit, if_ehit, inc_z]
    C(bs, zbody)
    rep_z = b_repeat(bs, 3, if_ahit)
    c_killnow = b_not(bs, cmp_op("operator_gt", vrep("선두처치타이머", V_KILLT), 0))
    clr_ahit = b_setvar(bs, "아군피격구역", V_AHITZ, 0); clr_ehit = b_setvar(bs, "적피격구역", V_EHITZ, 0)
    reset_kill = b_setvar(bs, "선두처치타이머", V_KILLT, vrep("선두처치주기", V_KILLGAP))
    C(bs, [clr_ahit, clr_ehit, set_z1, rep_z, reset_kill])
    if_kill = b_if(bs, c_killnow, clr_ahit)

    # ---- (E-2) 매틱 전선/돌파 루프: z=1..3, 전력차로 전선 이동 + 클램프 + 돌파 본진딜 ----
    set_z1b = b_setvar(bs, "심판z", V_ZI, 1)
    # 매틱용 전선/돌파 전용 z 루프 (선두 신호 없이):
    apowB = b_listitem(bs, "L_아군전력", L_APOW, vrep("심판z", V_ZI))
    epowB = b_listitem(bs, "L_적전력", L_EPOW, vrep("심판z", V_ZI))
    diffB = op("operator_subtract", apowB, epowB)
    moveB = op("operator_multiply", diffB, vrep("전선속도", V_FRONTSPD))
    curfB = b_listitem(bs, "L_전선", L_FRONT, vrep("심판z", V_ZI))
    newfB = op("operator_add", curfB, moveB)
    setfB = b_listreplace(bs, "L_전선", L_FRONT, vrep("심판z", V_ZI), newfB)
    ffB = b_listitem(bs, "L_전선", L_FRONT, vrep("심판z", V_ZI))
    c_hiB = cmp_op("operator_gt", ffB, vrep("적진y", V_ENEMYY))
    clamp_hiB = b_listreplace(bs, "L_전선", L_FRONT, vrep("심판z", V_ZI), vrep("적진y", V_ENEMYY))
    if_hiB = b_if(bs, c_hiB, clamp_hiB)
    ff2B = b_listitem(bs, "L_전선", L_FRONT, vrep("심판z", V_ZI))
    c_loB = cmp_op("operator_lt", ff2B, vrep("아군진y", V_ALLYY))
    clamp_loB = b_listreplace(bs, "L_전선", L_FRONT, vrep("심판z", V_ZI), vrep("아군진y", V_ALLYY))
    if_loB = b_if(bs, c_loB, clamp_loB)
    fbrkB = b_listitem(bs, "L_전선", L_FRONT, vrep("심판z", V_ZI))
    c_brk_eB = b_not(bs, cmp_op("operator_lt", fbrkB, op("operator_subtract", vrep("적진y", V_ENEMYY), 4)))
    dmg_eB = b_changevar(bs, "적본진HP", V_EHP, op("operator_multiply", vrep("돌파딜", V_BREAKDMG), -0.02))
    if_brk_eB = b_if(bs, c_brk_eB, dmg_eB)
    fbrk2B = b_listitem(bs, "L_전선", L_FRONT, vrep("심판z", V_ZI))
    c_brk_aB = b_not(bs, cmp_op("operator_gt", fbrk2B, op("operator_add", vrep("아군진y", V_ALLYY), 4)))
    dmg_aB = b_changevar(bs, "아군본진HP", V_AHP, op("operator_multiply", vrep("돌파딜", V_BREAKDMG), -0.02))
    if_brk_aB = b_if(bs, c_brk_aB, dmg_aB)
    inc_zB = b_changevar(bs, "심판z", V_ZI, 1)
    zbodyB = [setfB, if_hiB, if_loB, if_brk_eB, if_brk_aB, inc_zB]
    C(bs, zbodyB)
    rep_zB = b_repeat(bs, 3, setfB)
    C(bs, [set_z1b, rep_zB, if_kill])
    c_playf = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_playf = b_if(bs, c_playf, set_z1b)
    w_f = b_wait(bs, 0.02)
    C(bs, [if_playf, w_f])
    fe_f = b_forever(bs, if_playf)
    C(bs, [he, fe_f])
    add_comment(bs, comments, set_z1b,
        "⚔️★ 구역 전선 심판(한 곳!). 클론끼리 절대 안 봐요 — 구역 1~3 반복(상수!)으로\n"
        "각 구역 L_아군전력/L_적전력 차이만큼 L_전선[z] 을 밀어요(우세측이 상대 본진 쪽으로).\n"
        "전선이 적진y 닿으면 돌파→적 본진HP 딜, 아군진y 닿으면 아군 본진HP 딜.\n"
        "열세 구역엔 선두처치주기마다 피격구역 신호 발행 → 그 구역 최전방 1기만 처치.\n"
        "chess-war per-unit 듀얼 O(n²)를 여기 O(1)×3 심판으로 대체 = 폭주 없음.",
        x=900, y=620, w=430, h=190)

    # ===== (F) 승패 감시 forever =====
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=20, y=920,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    c_win = b_not(bs, cmp_op("operator_gt", vrep("적본진HP", V_EHP), 0))
    c_lose = b_not(bs, cmp_op("operator_gt", vrep("아군본진HP", V_AHP), 0))
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
#  side="A"(아군, 전선 아래쪽에서 위로 사격) / "E"(적, 위→아래)
#  ★ 클론끼리 참조/스캔 0개. 자기 구역 전선 부근 이동 + 선두채널 갱신 +
#    사격연출/팝업요청 + 자기 피격/사망 보고만.
# ============================================================
def build_unit_blocks(side):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    A = (side == "A")
    SPAWN   = (BR_ASPAWN, "아군소환") if A else (BR_ESPAWN, "적소환")
    SPZONE  = (V_SPZONE, "소환구역") if A else (V_ESPZONE, "적소환구역")
    SPTYPE  = (V_SPTYPE, "소환종류") if A else (V_ESPTYPE, "적소환종류")
    L_POW   = (L_APOW, "L_아군전력") if A else (L_EPOW, "L_적전력")
    L_CNT   = (L_ACNT, "L_아군수") if A else (L_ECNT, "L_적수")
    L_LEAD  = (L_ALEAD, "L_아군선두y") if A else (L_ELEAD, "L_적선두y")
    L_OPPLEAD = (L_ELEAD, "L_적선두y") if A else (L_ALEAD, "L_아군선두y")
    TOTAL   = (V_ATOTAL, "아군총수") if A else (V_ETOTAL, "적총수")
    HITZ    = (V_AHITZ, "아군피격구역") if A else (V_EHITZ, "적피격구역")
    CS = "아" if A else "적"
    # 아군은 전선 아래쪽(전선y - offset)에 자리, 적은 전선 위쪽(전선y + offset).
    off_sign = -1 if A else 1      # 유닛이 전선에서 자기 진영쪽으로 물러선 정도
    fire_sign = 1 if A else -1     # 사격/트레이서 방향(위=+ / 아래=-)
    reset_lead = ALLY_Y if A else ENEMY_Y

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

    # ── (C) 클론 본체 ──
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_ISC, 1)
    set_zone = b_setvar(bs, "내구역", V_ZONE, vrep(SPZONE[1], SPZONE[0]))
    set_type = b_setvar(bs, "내종류", V_TYPE, vrep(SPTYPE[1], SPTYPE[0]))
    # 전력 리스트[z] += 자기전력, 수[z]+1, 총수+1 (이벤트 기반)
    # 종류별 스탯 세팅
    def stat_branch(pw, hp, rng, costume, size):
        s_pw = b_setvar(bs, "내전력", V_POW, pw)
        s_hp = b_setvar(bs, "내HP", V_HP, hp); s_mh = b_setvar(bs, "내최대HP", V_MAXHP, hp)
        s_rn = b_setvar(bs, "내사거리", V_RNG, rng)
        swc = b_costume(bs, costume); szb = b_setsize(bs, size)
        C(bs, [s_pw, s_hp, s_mh, s_rn, swc, szb])
        return s_pw
    # 1=소총병(전력3,HP20,사거리中) 2=제압사수(전력6,HP28,사거리근~중) 3=저격수(전력2,HP8,장거리)
    b1 = stat_branch(3, 20, 120, f"{CS}소총", 85)
    b2 = stat_branch(6, 28, 100, f"{CS}제압", 92)
    b3 = stat_branch(2, 8, 200, f"{CS}저격", 78)
    if_t2 = b_ifelse(bs, cmp_op("operator_equals", vrep("내종류", V_TYPE), 2), b2, b3)
    if_t1 = b_ifelse(bs, cmp_op("operator_equals", vrep("내종류", V_TYPE), 1), b1, if_t2)
    # 전력/카운트 이벤트 반영
    curpow = b_listitem(bs, L_POW[1], L_POW[0], vrep("내구역", V_ZONE))
    add_pow = b_listreplace(bs, L_POW[1], L_POW[0], vrep("내구역", V_ZONE),
                            op("operator_add", curpow, vrep("내전력", V_POW)))
    curcnt = b_listitem(bs, L_CNT[1], L_CNT[0], vrep("내구역", V_ZONE))
    add_cnt = b_listreplace(bs, L_CNT[1], L_CNT[0], vrep("내구역", V_ZONE),
                            op("operator_add", curcnt, 1))
    inc_tot = b_changevar(bs, TOTAL[1], TOTAL[0], 1)
    set_fire0 = b_setvar(bs, "발사쿨", V_FIRET, 0)
    # 초기 위치: 구역 x + 약간의 좌우 흩뿌림, y = 전선[z] + off. 구역 x 는 종류/랜덤으로 흩뿌림.
    zx = op("operator_multiply", op("operator_subtract", vrep("내구역", V_ZONE), 2), 140)  # (z-2)*140 = -140/0/140
    jit = op("operator_random", -45, 45, key1="FROM", key2="TO")
    startx = op("operator_add", zx, jit)
    frontnow = b_listitem(bs, "L_전선", L_FRONT, vrep("내구역", V_ZONE))
    starty = op("operator_add", frontnow, 35 * off_sign)
    g0 = b_gotoxy(bs, startx, starty)
    fr = b_front(bs); show = b_show(bs)

    # ---- forever 본체 ----
    # 0) 게임 종료 정리
    c_gameend = b_not(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    curpow_e = b_listitem(bs, L_POW[1], L_POW[0], vrep("내구역", V_ZONE))
    dec_pow_e = b_listreplace(bs, L_POW[1], L_POW[0], vrep("내구역", V_ZONE),
                              op("operator_subtract", curpow_e, vrep("내전력", V_POW)))
    curcnt_e = b_listitem(bs, L_CNT[1], L_CNT[0], vrep("내구역", V_ZONE))
    dec_cnt_e = b_listreplace(bs, L_CNT[1], L_CNT[0], vrep("내구역", V_ZONE),
                              op("operator_subtract", curcnt_e, 1))
    dec_tot_e = b_changevar(bs, TOTAL[1], TOTAL[0], -1)
    del_end = b_delclone(bs)
    C(bs, [dec_pow_e, dec_cnt_e, dec_tot_e, del_end])
    if_end = b_if(bs, c_gameend, dec_pow_e)

    # 1) 자기 구역 전선 부근으로 y 이동(전선 따라 부드럽게). 목표 y = 전선[z] + 35*off.
    tgt_front = b_listitem(bs, "L_전선", L_FRONT, vrep("내구역", V_ZONE))
    tgt_y = op("operator_add", tgt_front, 35 * off_sign)
    # y += (tgt_y - y) * 0.15  (부드럽게 접근)
    dy = op("operator_multiply", op("operator_subtract", tgt_y, b_ypos(bs)), 0.15)
    mv = b_changey(bs, dy)

    # 2) 선두 채널 갱신: '전선에 가장 가까운(최전방) 유닛' = 선두.
    #    아군 최전방 = 가장 큰 y(전선 쪽). 적 최전방 = 가장 작은 y.
    #    내가 더 최전방이면 L_선두y[z] ← 내 y.
    curlead = b_listitem(bs, L_LEAD[1], L_LEAD[0], vrep("내구역", V_ZONE))
    if A:
        c_more = cmp_op("operator_gt", b_ypos(bs), curlead)
    else:
        c_more = cmp_op("operator_lt", b_ypos(bs), curlead)
    set_lead = b_listreplace(bs, L_LEAD[1], L_LEAD[0], vrep("내구역", V_ZONE), b_ypos(bs))
    if_lead = b_if(bs, c_more, set_lead)

    # 3) 사격 연출: 발사쿨 끝 & 팝업 캡 여유 → 트레이서 점멸 + 데미지 팝업 요청 + 총구 코스튬 점멸.
    #    ★ 클론 스캔 0개: 자기 구역/전력만 봄. 사격 대상은 '같은 구역 적 최전방'(L_적선두y[z]) 근사 —
    #    실제 데미지 판정은 심판(전력차)이 하고, 여기는 순수 연출 + 팝업.
    c_firecd = b_not(bs, cmp_op("operator_gt", vrep("발사쿨", V_FIRET), 0))
    # 사격 조건: 이 구역에 상대가 있어야(상대 전력>0). 상대 전력 리스트[z]>0.
    L_OPPPOW = (L_EPOW, "L_적전력") if A else (L_APOW, "L_아군전력")
    opppow = b_listitem(bs, L_OPPPOW[1], L_OPPPOW[0], vrep("내구역", V_ZONE))
    c_hasopp = cmp_op("operator_gt", opppow, 0)
    c_canfire = bool_op("operator_and", c_firecd, c_hasopp)
    # 총구 점멸 코스튬 스위치
    sw_fire = b_costume(bs, f"{CS}{'소총'}")  # placeholder, set per-type below
    # 종류별 발사 코스튬은 아래에서 결정 → 간단히 firing costume 로 스위치 후 복귀.
    # 발사 코스튬 이름 결정
    c_t1f = cmp_op("operator_equals", vrep("내종류", V_TYPE), 1)
    c_t2f = cmp_op("operator_equals", vrep("내종류", V_TYPE), 2)
    swf1 = b_costume(bs, f"{CS}소총F"); swf2 = b_costume(bs, f"{CS}제압F"); swf3 = b_costume(bs, f"{CS}저격F")
    if_f2 = b_ifelse(bs, c_t2f, swf2, swf3)
    if_f1 = b_ifelse(bs, c_t1f, swf1, if_f2)
    # 팝업 요청: 팝업수<팝업캡 이면 팝업x/y/값 세팅 후 방송. 값 = 자기 전력(약/중/강 매핑).
    c_poproom = cmp_op("operator_lt", vrep("팝업수", V_POPCNT), vrep("팝업캡", V_POPCAP))
    # 팝업 위치: 상대 최전방 근처(구역 x + jitter, y = 전선[z] + 20*fire_sign)
    ppx = op("operator_add", op("operator_multiply", op("operator_subtract", vrep("내구역", V_ZONE), 2), 140),
             op("operator_random", -40, 40, key1="FROM", key2="TO"))
    ppfront = b_listitem(bs, "L_전선", L_FRONT, vrep("내구역", V_ZONE))
    ppy = op("operator_add", ppfront, 20 * fire_sign)
    set_ppx = b_setvar(bs, "팝업x", V_POPX, ppx)
    set_ppy = b_setvar(bs, "팝업y", V_POPY, ppy)
    set_ppv = b_setvar(bs, "팝업값", V_POPVAL, vrep("내전력", V_POW))
    bc_pop = b_broadcast(bs, "팝업요청", BR_POP)
    C(bs, [set_ppx, set_ppy, set_ppv, bc_pop])
    if_pop = b_if(bs, c_poproom, set_ppx)
    pew = b_playsound(bs, "pew")
    set_firecd = b_setvar(bs, "발사쿨", V_FIRET, op("operator_random", 8, 16, key1="FROM", key2="TO"))
    # 사격 시퀀스: 발사코스튬 → 팝업 요청 → 소리 → 쿨 세팅
    C(bs, [if_f1, if_pop, pew, set_firecd])
    if_fire = b_if(bs, c_canfire, if_f1)
    # 발사쿨 감소 & 평상 코스튬 복귀
    c_fpos = cmp_op("operator_gt", vrep("발사쿨", V_FIRET), 0)
    dec_fire = b_changevar(bs, "발사쿨", V_FIRET, -1)
    # 발사쿨이 낮아지면(막 안 쏨) 평상 코스튬 복귀
    c_t1n = cmp_op("operator_equals", vrep("내종류", V_TYPE), 1)
    c_t2n = cmp_op("operator_equals", vrep("내종류", V_TYPE), 2)
    swn1 = b_costume(bs, f"{CS}소총"); swn2 = b_costume(bs, f"{CS}제압"); swn3 = b_costume(bs, f"{CS}저격")
    if_n2 = b_ifelse(bs, c_t2n, swn2, swn3)
    if_n1 = b_ifelse(bs, c_t1n, swn1, if_n2)
    c_lowcd = b_not(bs, cmp_op("operator_gt", vrep("발사쿨", V_FIRET), 4))
    if_normal = b_if(bs, c_lowcd, if_n1)
    if_firedec = b_if(bs, c_fpos, dec_fire)

    # 4) 피격/사망: 심판이 내 구역을 '피격구역' 으로 지목 & 내가 그 구역 선두(내 y == 선두y 근사) → 피해.
    #    ★ 클론 스캔 0개: 공유 변수(피격구역) + 리스트 선두y[z] 만 봄.
    c_hitme = cmp_op("operator_equals", vrep(HITZ[1], HITZ[0]), vrep("내구역", V_ZONE))
    mylead = b_listitem(bs, L_LEAD[1], L_LEAD[0], vrep("내구역", V_ZONE))
    diff_lead = op("operator_subtract", b_ypos(bs), mylead)
    c_isfront = b_not(bs, cmp_op("operator_gt", b_abs(bs, diff_lead), 8))
    c_gethit = bool_op("operator_and", c_hitme, c_isfront)
    # 피해: 내HP -= (상대 전력 비례 데미지). 간단히 내최대HP 의 절반 큰 딜(선두 처치 페이스).
    take = b_changevar(bs, "내HP", V_HP, op("operator_random", -12, -7, key1="FROM", key2="TO"))
    # 피격당하면 그 구역 신호 소비(중복 처치 방지): 피격구역=0
    consume = b_setvar(bs, HITZ[1], HITZ[0], 0)
    ghit = b_changeeffect(bs, "GHOST", 15)
    wgh = b_wait(bs, 0.02); cgh = b_seteffect(bs, "GHOST", 0)
    C(bs, [take, consume, ghit, wgh, cgh])
    if_hit = b_if(bs, c_gethit, take)

    # 5) 처치: 내HP<1 → 전력/카운트 감소, 팝 이펙트, 선두면 채널 리셋, 삭제
    c_kill = cmp_op("operator_lt", vrep("내HP", V_HP), 1)
    curpow_k = b_listitem(bs, L_POW[1], L_POW[0], vrep("내구역", V_ZONE))
    dec_pow_k = b_listreplace(bs, L_POW[1], L_POW[0], vrep("내구역", V_ZONE),
                              op("operator_subtract", curpow_k, vrep("내전력", V_POW)))
    curcnt_k = b_listitem(bs, L_CNT[1], L_CNT[0], vrep("내구역", V_ZONE))
    dec_cnt_k = b_listreplace(bs, L_CNT[1], L_CNT[0], vrep("내구역", V_ZONE),
                              op("operator_subtract", curcnt_k, 1))
    dec_tot_k = b_changevar(bs, TOTAL[1], TOTAL[0], -1)
    # 선두면 선두y 리셋(다음 최전방이 재점유)
    mylead_k = b_listitem(bs, L_LEAD[1], L_LEAD[0], vrep("내구역", V_ZONE))
    c_isfront_k = b_not(bs, cmp_op("operator_gt", b_abs(bs, op("operator_subtract", b_ypos(bs), mylead_k)), 8))
    reset_lead_k = b_listreplace(bs, L_LEAD[1], L_LEAD[0], vrep("내구역", V_ZONE), reset_lead)
    if_reset_lead = b_if(bs, c_isfront_k, reset_lead_k)
    swpop = b_costume(bs, f"{CS}팝")
    csz = b_changesize(bs, 14); cgh2 = b_changeeffect(bs, "GHOST", 22); wpop = b_wait(bs, 0.02)
    C(bs, [csz, cgh2, wpop]); rep_pop = b_repeat(bs, 4, csz)
    pk = b_playsound(bs, "crack"); del_k = b_delclone(bs)
    C(bs, [dec_pow_k, dec_cnt_k, dec_tot_k, if_reset_lead, swpop, rep_pop, pk, del_k])
    if_kill = b_if(bs, c_kill, dec_pow_k)

    # forever 조립
    play_body = [mv, if_lead, if_fire, if_normal, if_firedec, if_hit, if_kill]
    C(bs, play_body)
    if_play = b_if(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1), mv)
    w_body = b_wait(bs, 0.02)
    C(bs, [if_end, if_play, w_body])
    fe = b_forever(bs, if_end)
    # 클론 시작 시퀀스
    C(bs, [ch, set1, set_zone, set_type, if_t1, add_pow, add_cnt, inc_tot, set_fire0, g0, fr, show, fe])

    add_comment(bs, comments, if_lead,
        "\U0001F464★ 유닛은 '자기 구역 전선 부근 이동 + 자기 y를 구역 선두 채널에 보고 +\n"
        "사격 연출/팝업요청 + 자기 피격·사망 보고'만 해요. 다른 유닛 클론을 절대 안 봐요!\n"
        "전투(전선 이동·누가 죽나)는 전부 Stage 심판이 리스트만 보고 처리 → 클론끼리 스캔 0개.\n"
        "스폰 시 L_전력[z]+=내전력(이벤트 기반). 사망 시 -=. 매 틱 유닛 순회 합산 안 함.",
        x=470, y=380, w=430, h=180)
    return bs, comments

# ============================================================
#  데미지 팝업 (플로팅 텍스트 클론) — ★핵심 연출
#  팝업요청 받으면 팝업수<팝업캡 일 때만 클론 1기. 위로 떠오르며 fade,
#  0.4~0.6초 후 팝업수-1 + delete this clone.
# ============================================================
def build_popup_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs, "don't rotate"); orig0 = b_setvar(bs, "복제됨", V_POP_ISC, 0)
    C(bs, [h, hi, rs, orig0])

    # 팝업요청 → 원본만: 팝업수<팝업캡 이면 팝업수+1 후 클론
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["팝업요청", BR_POP]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_POP_ISC), 0)
    c_room = cmp_op("operator_lt", vrep("팝업수", V_POPCNT), vrep("팝업캡", V_POPCAP))
    c_ok = bool_op("operator_and", c_orig, c_room)
    inc = b_changevar(bs, "팝업수", V_POPCNT, 1)
    cc = b_createclone(bs)
    C(bs, [inc, cc])
    if_c = b_if(bs, c_ok, inc)
    C(bs, [hb, if_c])

    # 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_POP_ISC, 1)
    g0 = b_gotoxy(bs, vrep("팝업x", V_POPX), vrep("팝업y", V_POPY))
    # 값에 따라 costume: <=2 약, <=4 중, else 강
    c_low = b_not(bs, cmp_op("operator_gt", vrep("팝업값", V_POPVAL), 2))
    c_mid = b_not(bs, cmp_op("operator_gt", vrep("팝업값", V_POPVAL), 4))
    sw_low = b_costume(bs, "약"); sw_mid = b_costume(bs, "중"); sw_high = b_costume(bs, "강")
    if_mid = b_ifelse(bs, c_mid, sw_mid, sw_high)
    if_low = b_ifelse(bs, c_low, sw_low, if_mid)
    setg = b_seteffect(bs, "GHOST", 0); sz = b_setsize(bs, 100); fr = b_front(bs); show = b_show(bs)
    # 떠오르며 fade: repeat 12: y+=2, ghost+=7, wait 0.04 → ~0.48초
    up = b_changey(bs, 2); addg = b_changeeffect(bs, "GHOST", 7); wu = b_wait(bs, 0.04)
    C(bs, [up, addg, wu]); rep = b_repeat(bs, 12, up)
    dec = b_changevar(bs, "팝업수", V_POPCNT, -1)
    ptick = b_playsound(bs, "tick")
    delc = b_delclone(bs)
    C(bs, [ch, set1, g0, if_low, setg, sz, fr, show, ptick, rep, dec, delc])
    add_comment(bs, comments, inc,
        "\U0001F4A5★ 데미지 팝업 = 핵심 연출. 팝업요청 시 팝업수<팝업캡(20) 일 때만 생성(+1).\n"
        "위로 떠오르며 ghost↑(fade), 약0.48초 후 팝업수-1 + delete this clone.\n"
        "동시 팝업 ≤ 팝업캡 — 초과 요청은 팝업 생략(전투는 계속). 새 클론 부담원이라 특히 엄격.",
        x=470, y=200, w=420, h=150)
    return bs, comments

# ============================================================
#  소환 버튼 (3버튼 각 1스프라이트) — 클릭 폴링+디바운스 → 대기소환종류 세팅
# ============================================================
def build_button_blocks(kind):
    """kind: 'rifle'|'mg'|'snipe'"""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    conf = {
        "rifle": (V_C_RIFLE, "소총_코스트", V_CDT_RIFLE, "소총_쿨타이머", 1, "버튼소총", -100),
        "mg":    (V_C_MG,    "제압_코스트", V_CDT_MG,    "제압_쿨타이머", 2, "버튼제압", 0),
        "snipe": (V_C_SNIPE, "저격_코스트", V_CDT_SNIPE, "저격_쿨타이머", 3, "버튼저격", 100),
    }[kind]
    COST_ID, COST_NM, CDT_ID, CDT_NM, TYPE_VAL, BASE, xpos = conf
    ypos = -158

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, xpos, ypos); sz = b_setsize(bs, 100); fr = b_front(bs); swc = b_costume(bs, BASE+"On")
    C(bs, [h, show, g, sz, fr, swc])

    # 코스튬 갱신 forever: 선택중이면 SEL, 가능하면 ON, 아니면 OFF
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=220)
    c_sel = cmp_op("operator_equals", vrep("대기소환종류", V_PENDTYPE), TYPE_VAL)
    c_gold = b_not(bs, cmp_op("operator_lt", vrep("돈", V_GOLD), vrep(COST_NM, COST_ID)))
    c_cd = b_not(bs, cmp_op("operator_gt", vrep(CDT_NM, CDT_ID), 0))
    c_ok = bool_op("operator_and", c_gold, c_cd)
    sw_sel = b_costume(bs, BASE+"Sel"); sw_on = b_costume(bs, BASE+"On"); sw_off = b_costume(bs, BASE+"Off")
    if_onoff = b_ifelse(bs, c_ok, sw_on, sw_off)
    if_cos = b_ifelse(bs, c_sel, sw_sel, if_onoff)
    w_c = b_wait(bs, 0.05)
    C(bs, [if_cos, w_c])
    fe_c = b_forever(bs, if_cos)
    C(bs, [hc, fe_c])

    # 클릭 폴링+디바운스 forever → 대기소환종류 = 내 종류(선택만; 실제 스폰은 구역클릭)
    hp = gen(); bs[hp] = mk("event_whenflagclicked", top=True, x=470, y=220)
    c_md = b_mousedown(bs); c_tm = b_touchingmouse(bs)
    c_click = bool_op("operator_and", c_md, c_tm)
    g_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    # 선택 세팅: 대기소환종류 = 내 타입, pop 소리
    set_pend = b_setvar(bs, "대기소환종류", V_PENDTYPE, TYPE_VAL)
    pp = b_playsound(bs, "pop")
    wu_up = b_waituntil(bs, b_not(bs, b_mousedown(bs)))
    C(bs, [set_pend, pp, wu_up])
    if_sel = b_if(bs, g_play, set_pend)
    if_click = b_if(bs, c_click, if_sel)
    w_p = b_wait(bs, 0.02)
    C(bs, [if_click, w_p])
    fe_p = b_forever(bs, if_click)
    C(bs, [hp, fe_p])
    add_comment(bs, comments, if_click,
        "\U0001F5B1️ 유닛 버튼: 클릭 폴링+디바운스 → 대기소환종류 세팅(선택 하이라이트).\n"
        "실제 스폰은 그 다음 좌/중/우 구역을 클릭할 때. 돈≥코스트 & 소환쿨끝 아니면 회색.",
        x=900, y=220, w=380, h=120)
    return bs, comments

# ============================================================
#  구역 클릭 영역 (1 스프라이트 3클론) — 대기소환종류 있고 구역 클릭 시 스폰
# ============================================================
def build_zoneclick_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # 원본: 3구역 클론 생성(내구역=1/2/3), 각 구역 x 로 이동, 투명.
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = b_rotstyle(bs, "don't rotate"); orig0 = b_setvar(bs, "복제됨", V_ISC, 0)
    ghost = b_seteffect(bs, "GHOST", 100)  # 투명 히트박스
    # z=1..3 클론
    setz = b_setvar(bs, "내구역", V_ZONE, 1)
    mkclone = b_createclone(bs); incz = b_changevar(bs, "내구역", V_ZONE, 1)
    C(bs, [setz, mkclone, incz]); rep = b_repeat(bs, 3, setz)
    hideorig = b_hide(bs)
    C(bs, [h, rs, orig0, ghost, rep, hideorig])

    # 클론: 자기 구역 x 로 이동, 큰 히트박스로 표시(투명), 클릭 폴링
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_ISC, 1)
    # x = (z-2)*140, y=10(노맨스랜드 중앙), 크기 큰 투명 사각
    zx = op("operator_multiply", op("operator_subtract", vrep("내구역", V_ZONE), 2), 140)
    g0 = b_gotoxy(bs, zx, 10)
    sz = b_setsize(bs, 100); gh = b_seteffect(bs, "GHOST", 100); show = b_show(bs)

    # 클릭 폴링+디바운스: 대기소환종류>0 & 이 히트박스 터치 & 마우스다운 → 스폰 시도
    c_md = b_mousedown(bs); c_tm = b_touchingmouse(bs)
    c_click = bool_op("operator_and", c_md, c_tm)
    c_haspend = cmp_op("operator_gt", vrep("대기소환종류", V_PENDTYPE), 0)
    g_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    # 스폰 게이트: 돈≥코스트(종류별) & 소환쿨끝 & 아군수[z]<구역캡 & 아군총수<전체캡
    # 종류별 코스트/쿨 조회는 대기소환종류로 분기.
    # 코스트/쿨타이머/쿨값을 대기소환종류에 따라 선택하는 대신, 세 종류를 if 분기로 처리.
    def spawn_branch(TYPE_VAL, COST_ID, COST_NM, CDT_ID, CDT_NM, CD_ID, CD_NM):
        c_type = cmp_op("operator_equals", vrep("대기소환종류", V_PENDTYPE), TYPE_VAL)
        g_gold = b_not(bs, cmp_op("operator_lt", vrep("돈", V_GOLD), vrep(COST_NM, COST_ID)))
        g_cd = b_not(bs, cmp_op("operator_gt", vrep(CDT_NM, CDT_ID), 0))
        acnt = b_listitem(bs, "L_아군수", L_ACNT, vrep("내구역", V_ZONE))
        g_zcap = cmp_op("operator_lt", acnt, vrep("구역캡", V_ZONECAP))
        g_tcap = cmp_op("operator_lt", vrep("아군총수", V_ATOTAL), vrep("전체캡", V_TOTALCAP))
        g_ok = bool_op("operator_and", bool_op("operator_and", g_gold, g_cd), bool_op("operator_and", g_zcap, g_tcap))
        # 스폰: 돈-코스트, 쿨 리셋, 소환구역=내구역, 소환종류=타입, 아군소환 방송, pop
        dec_gold = b_changevar(bs, "돈", V_GOLD, op("operator_subtract", 0, vrep(COST_NM, COST_ID)))
        set_cd = b_setvar(bs, CDT_NM, CDT_ID, vrep(CD_NM, CD_ID))
        set_zn = b_setvar(bs, "소환구역", V_SPZONE, vrep("내구역", V_ZONE))
        set_ty = b_setvar(bs, "소환종류", V_SPTYPE, TYPE_VAL)
        bc_a = b_broadcast_wait(bs, "아군소환", BR_ASPAWN)
        pp = b_playsound(bs, "pop")
        C(bs, [dec_gold, set_cd, set_zn, set_ty, bc_a, pp])
        if_spawn = b_if(bs, g_ok, dec_gold)
        # 이 종류일 때만 실행
        if_thistype = b_if(bs, c_type, if_spawn)
        return if_thistype
    br1 = spawn_branch(1, V_C_RIFLE, "소총_코스트", V_CDT_RIFLE, "소총_쿨타이머", V_CD_RIFLE, "소총_소환쿨")
    br2 = spawn_branch(2, V_C_MG,    "제압_코스트", V_CDT_MG,    "제압_쿨타이머", V_CD_MG,    "제압_소환쿨")
    br3 = spawn_branch(3, V_C_SNIPE, "저격_코스트", V_CDT_SNIPE, "저격_쿨타이머", V_CD_SNIPE, "저격_소환쿨")
    C(bs, [br1, br2, br3])
    wu_up = b_waituntil(bs, b_not(bs, b_mousedown(bs)))
    # 클릭 처리: haspend & play & click → 분기 스폰 후 디바운스
    c_dospawn = bool_op("operator_and", c_haspend, g_play)
    if_dospawn = b_if(bs, c_dospawn, br1)
    C(bs, [if_dospawn, wu_up])
    if_click = b_if(bs, c_click, if_dospawn)
    w_p = b_wait(bs, 0.02)
    C(bs, [if_click, w_p])
    fe = b_forever(bs, if_click)
    C(bs, [ch, set1, g0, sz, gh, show, fe])
    add_comment(bs, comments, if_click,
        "\U0001F3AF 구역 클릭 히트박스(3클론=좌/중/우). 대기소환종류가 있고 이 구역을 클릭하면\n"
        "그 구역에 스폰 시도: 돈≥코스트 & 소환쿨끝 & 아군수[z]<구역캡6 & 아군총수<전체캡24 일 때만.\n"
        "'유닛 선택 → 구역 지정' 2단 흐름 = 어느 전선을 보강하느냐가 유일한 전략.",
        x=470, y=380, w=430, h=140)
    return bs, comments

# ============================================================
#  HP바 / 지갑바 (costume-fill)
# ============================================================
def build_bar_blocks(kind):
    """kind: 'ahp'|'ehp'|'gold'"""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    conf = {
        "ahp":  (V_AHP, "아군본진HP", 100, -95, -168),
        "ehp":  (V_EHP, "적본진HP", 100, -95, 168),
        "gold": (V_GOLD, "돈", None, 55, -158),
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
    c_win = b_not(bs, cmp_op("operator_gt", vrep("적본진HP", V_EHP), 0))
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
    a_ri = save_svg(A_RIFLE); a_ri_f = save_svg(A_RIFLE_F); a_mg = save_svg(A_MG); a_mg_f = save_svg(A_MG_F); a_sn = save_svg(A_SNIPER); a_sn_f = save_svg(A_SNIPER_F)
    e_ri = save_svg(E_RIFLE); e_ri_f = save_svg(E_RIFLE_F); e_mg = save_svg(E_MG); e_mg_f = save_svg(E_MG_F); e_sn = save_svg(E_SNIPER); e_sn_f = save_svg(E_SNIPER_F)
    pop_md5 = save_svg(POP_SVG)
    dmg_lo = save_svg(DMG_LOW); dmg_mi = save_svg(DMG_MID); dmg_hi = save_svg(DMG_HIGH)
    bri_sel = save_svg(BTN_RIFLE_SEL); bri_on = save_svg(BTN_RIFLE_ON); bri_off = save_svg(BTN_RIFLE_OFF)
    bmg_sel = save_svg(BTN_MG_SEL); bmg_on = save_svg(BTN_MG_ON); bmg_off = save_svg(BTN_MG_OFF)
    bsn_sel = save_svg(BTN_SNIPE_SEL); bsn_on = save_svg(BTN_SNIPE_ON); bsn_off = save_svg(BTN_SNIPE_OFF)
    ahp_md5 = [save_svg(s) for s in AHP_BARS]; ehp_md5 = [save_svg(s) for s in EHP_BARS]; gold_md5 = [save_svg(s) for s in GOLD_BARS]
    win_md5 = save_svg(WIN_SVG); lose_md5 = save_svg(LOSE_SVG)

    if not os.path.exists(ASSETS): os.makedirs(ASSETS)
    def save_wav(name, samples):
        b = _wav_bytes(samples)
        with open(f"{ASSETS}/{name}.wav", "wb") as f: f.write(b)
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    pop_s, pop_n = save_wav("pop", synth_pop()); pew_s, pew_n = save_wav("pew", synth_pew())
    tick_s, tick_n = save_wav("tick", synth_tick()); crack_s, crack_n = save_wav("crack", synth_crack())
    def snd(name, md5, n):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "", "rate": SND_RATE, "sampleCount": n, "md5ext": f"{md5}.wav"}
    def cos(name, md5, rx=23, ry=23):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg", "assetId": md5, "md5ext": f"{md5}.svg", "rotationCenterX": rx, "rotationCenterY": ry}

    stage_b, stage_c = build_stage_blocks()
    aunit_b, aunit_c = build_unit_blocks("A")
    eunit_b, eunit_c = build_unit_blocks("E")
    popup_b, popup_c = build_popup_blocks()
    bri_b, bri_c = build_button_blocks("rifle")
    bmg_b, bmg_c = build_button_blocks("mg")
    bsn_b, bsn_c = build_button_blocks("snipe")
    zone_b, zone_c = build_zoneclick_blocks()
    ahp_b, ahp_c = build_bar_blocks("ahp")
    ehp_b, ehp_c = build_bar_blocks("ehp")
    gold_b, gold_c = build_bar_blocks("gold")
    ban_b, ban_c = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_GOLD:["돈",40], V_GOLDMAX:["돈상한",200], V_GOLDRATE:["돈충전율",5],
            V_ZONECAP:["구역캡",6], V_TOTALCAP:["전체캡",24],
            V_POPCAP:["팝업캡",20], V_POPCNT:["팝업수",0],
            V_AHP:["아군본진HP",100], V_EHP:["적본진HP",100],
            V_BREAKDMG:["돌파딜",6], V_FRONTSPD:["전선속도",0.5], V_KILLGAP:["선두처치주기",22],
            V_ESPAWNGAP:["적스폰간격",2.5], V_ESPAWNT:["적스폰타이머",1.5],
            V_ENEMYY:["적진y",ENEMY_Y], V_ALLYY:["아군진y",ALLY_Y],
            V_ATOTAL:["아군총수",0], V_ETOTAL:["적총수",0], V_STATE:["게임상태",1],
            V_C_RIFLE:["소총_코스트",30], V_C_MG:["제압_코스트",55], V_C_SNIPE:["저격_코스트",50],
            V_CD_RIFLE:["소총_소환쿨",35], V_CD_MG:["제압_소환쿨",90], V_CD_SNIPE:["저격_소환쿨",100],
            V_CDT_RIFLE:["소총_쿨타이머",0], V_CDT_MG:["제압_쿨타이머",0], V_CDT_SNIPE:["저격_쿨타이머",0],
            V_PENDTYPE:["대기소환종류",0], V_SPZONE:["소환구역",0], V_SPTYPE:["소환종류",0],
            V_ESPZONE:["적소환구역",0], V_ESPTYPE:["적소환종류",0],
            V_POPX:["팝업x",0], V_POPY:["팝업y",0], V_POPVAL:["팝업값",1],
            V_AHITZ:["아군피격구역",0], V_EHITZ:["적피격구역",0], V_HITDMG:["피격딜",0], V_KILLT:["선두처치타이머",0],
            V_ZI:["심판z",1],
        },
        "lists": {
            L_APOW:["L_아군전력",[0,0,0]], L_EPOW:["L_적전력",[0,0,0]], L_FRONT:["L_전선",[FRONT_INIT,FRONT_INIT,FRONT_INIT]],
            L_ACNT:["L_아군수",[0,0,0]], L_ECNT:["L_적수",[0,0,0]],
            L_ALEAD:["L_아군선두y",[ALLY_Y,ALLY_Y,ALLY_Y]], L_ELEAD:["L_적선두y",[ENEMY_Y,ENEMY_Y,ENEMY_Y]],
        },
        "broadcasts": {
            BR_START:"게임시작", BR_ASPAWN:"아군소환", BR_ESPAWN:"적소환",
            BR_POP:"팝업요청", BR_END:"게임끝",
        },
        "blocks": stage_b, "comments": stage_c, "currentCostume": 0,
        "costumes": [{"name":"전장","dataFormat":"svg","assetId":bg_md5,"md5ext":f"{bg_md5}.svg","rotationCenterX":240,"rotationCenterY":180}],
        "sounds": [snd("pop", pop_s, pop_n), snd("pew", pew_s, pew_n), snd("tick", tick_s, tick_n), snd("crack", crack_s, crack_n)],
        "volume":100,"layerOrder":0,"tempo":60,"videoTransparency":50,"videoState":"on","textToSpeechLanguage":None
    }
    def unit_target(name, blocks, cmts, costumes, order):
        return {"isStage": False, "name": name,
                "variables": {V_ISC:["복제됨",0], V_ZONE:["내구역",1], V_TYPE:["내종류",1], V_POW:["내전력",3],
                              V_HP:["내HP",20], V_MAXHP:["내최대HP",20], V_RNG:["내사거리",120], V_FIRET:["발사쿨",0]},
                "lists": {}, "broadcasts": {}, "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": costumes, "sounds": [snd("pew", pew_s, pew_n), snd("crack", crack_s, crack_n)],
                "volume":100,"layerOrder":order,"visible":False,"x":0,"y":0,"size":85,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    aunit = unit_target("아군유닛", aunit_b, aunit_c,
        [cos("아소총", a_ri), cos("아소총F", a_ri_f), cos("아제압", a_mg), cos("아제압F", a_mg_f),
         cos("아저격", a_sn), cos("아저격F", a_sn_f), cos("아팝", pop_md5)], 3)
    eunit = unit_target("적유닛", eunit_b, eunit_c,
        [cos("적소총", e_ri), cos("적소총F", e_ri_f), cos("적제압", e_mg), cos("적제압F", e_mg_f),
         cos("적저격", e_sn), cos("적저격F", e_sn_f), cos("적팝", pop_md5)], 4)
    popup = {"isStage": False, "name": "데미지팝업",
             "variables": {V_POP_ISC:["복제됨",0]},
             "lists": {}, "broadcasts": {}, "blocks": popup_b, "comments": popup_c, "currentCostume": 0,
             "costumes": [cos("약", dmg_lo, 22, 15), cos("중", dmg_mi, 22, 15), cos("강", dmg_hi, 22, 15)],
             "sounds": [snd("tick", tick_s, tick_n)],
             "volume":100,"layerOrder":5,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    def button_target(name, blocks, cmts, sel, on, off, x, order):
        return {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 1,
                "costumes": [cos(name+"Sel", sel, 46, 20), cos(name+"On", on, 46, 20), cos(name+"Off", off, 46, 20)],
                "sounds": [snd("pop", pop_s, pop_n)],
                "volume":100,"layerOrder":order,"visible":True,"x":x,"y":-158,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    bri = button_target("버튼소총", bri_b, bri_c, bri_sel, bri_on, bri_off, -100, 6)
    bmg = button_target("버튼제압", bmg_b, bmg_c, bmg_sel, bmg_on, bmg_off, 0, 7)
    bsn = button_target("버튼저격", bsn_b, bsn_c, bsn_sel, bsn_on, bsn_off, 100, 8)
    zone = {"isStage": False, "name": "구역클릭",
            "variables": {V_ISC:["복제됨",0], V_ZONE:["내구역",1]},
            "lists": {}, "broadcasts": {}, "blocks": zone_b, "comments": zone_c, "currentCostume": 0,
            "costumes": [{"name":"영역","dataFormat":"svg","assetId":bg_md5,"md5ext":f"{bg_md5}.svg","rotationCenterX":240,"rotationCenterY":180,"bitmapResolution":1}],
            "sounds": [snd("pop", pop_s, pop_n)],
            "volume":100,"layerOrder":9,"visible":False,"x":0,"y":0,"size":34,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    def bar_target(name, blocks, cmts, md5s, x, y, order):
        return {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos(f"{name}_{i}", md5s[i], 85, 10) for i in range(11)], "sounds": [],
                "volume":100,"layerOrder":order,"visible":True,"x":x,"y":y,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    ahpbar = bar_target("아군본진바", ahp_b, ahp_c, ahp_md5, -95, -168, 10)
    ehpbar = bar_target("적본진바", ehp_b, ehp_c, ehp_md5, -95, 168, 10)
    goldbar = bar_target("지갑바", gold_b, gold_c, gold_md5, 55, -158, 10)
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
        {"id": V_ATOTAL, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"아군총수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":30,"visible":True,"sliderMin":0,"sliderMax":24,"isDiscrete":True},
        {"id": V_ETOTAL, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"적총수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":55,"visible":True,"sliderMin":0,"sliderMax":24,"isDiscrete":True},
        {"id": V_POPCNT, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"팝업수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":80,"visible":True,"sliderMin":0,"sliderMax":20,"isDiscrete":True},
        {"id": V_FRONT_MON, "mode":"list","opcode":"data_listcontents","params":{"LIST":"L_전선"},"spriteName":None,
         "value":[FRONT_INIT,FRONT_INIT,FRONT_INIT],"width":0,"height":0,"x":380,"y":5,"visible":True},
    ]
    project = {
        "targets": [stage, aunit, eunit, popup, bri, bmg, bsn, zone, ahpbar, ehpbar, goldbar, banner],
        "monitors": monitors, "extensions": [],
        "meta": {"semver":"3.0.0","vm":"13.7.4-svg","agent":"trench-line-builder"}
    }
    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f: json.dump(project, f, ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK): zf.write(f"{WORK}/{fn}", fn)
    with open(pj, "r", encoding="utf-8") as f: json.load(f)
    total = 0
    print(f"wrote {OUTPUT}")
    for nm, b in [("stage",stage_b),("아군유닛",aunit_b),("적유닛",eunit_b),("데미지팝업",popup_b),
                  ("버튼소총",bri_b),("버튼제압",bmg_b),("버튼저격",bsn_b),("구역클릭",zone_b),
                  ("아군본진바",ahp_b),("적본진바",ehp_b),("지갑바",gold_b),("결과배너",ban_b)]:
        print(f"  {nm:8s}: {len(b)} blocks"); total += len(b)
    print(f"  총 블록 수: {total}")

if __name__ == "__main__":
    main()
