#!/usr/bin/env python3
"""지아이조 (gi-joe) — 엄폐 곡사 탱크전.

탱크 한 대가 ←→ 이동, ↑↓ 곡사각, space 차지 발사, X 수류탄.
체력이 있고, 스페이스를 길게 누르면 강하게 쏜다. 점프 없음.
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "지아이조.sb3")

SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_fire(rate=SND_RATE):
    """묵직한 총성 — 저음 킥 + 짧은 노이즈."""
    N = int(rate * 0.22); out = []; rng = random.Random(11); lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 11)
        white = rng.random() * 2 - 1
        lp = lp + 0.2 * (white - lp)
        th = math.sin(2 * math.pi * (34 + 20 * math.exp(-t * 16)) * t)
        body = math.sin(2 * math.pi * 72 * t) * math.exp(-t * 9)
        sub = math.sin(2 * math.pi * 28 * t) * math.exp(-t * 7)
        out.append(max(-1, min(1, (lp * 0.22 + th * 0.95 + body * 0.42 + sub * 0.6) * env)))
    return out

def synth_reload(rate=SND_RATE):
    """찰칵 찰칵 — 탄창 삽입 + 노리쇠. 짧고 딱딱한 금속 클릭."""
    N = int(rate * 0.38); out = [0.0] * N
    rng = random.Random(41)

    def chalcac(t0, f_ring, f_body):
        n = int(0.08 * rate)
        for i in range(n):
            if t0 + i >= N:
                break
            t = i / rate
            att = 1 - math.exp(-t * 500)
            env = att * math.exp(-t * 38)
            ring = math.sin(2 * math.pi * f_ring * t) * math.exp(-t * 22)
            body = math.sin(2 * math.pi * f_body * t) * math.exp(-t * 30)
            metal = math.sin(2 * math.pi * f_ring * 2.15 * t) * math.exp(-t * 55)
            nse = (rng.random() * 2 - 1) * math.exp(-t * 90)
            out[t0 + i] += (ring * 0.7 + body * 0.45 + metal * 0.2 + nse * 0.12) * env

    chalcac(int(0.00 * rate), 980, 160)   # 찰칵
    chalcac(int(0.15 * rate), 1240, 190)  # 찰칵
    peak = max(1e-6, max(abs(s) for s in out))
    return [max(-1, min(1, s / peak * 0.78)) for s in out]

def synth_click(rate=SND_RATE):
    """딱! 빈 탄창 / 방패."""
    N = int(rate * 0.06); out = []; rng = random.Random(99)
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 70) * (1 - math.exp(-t * 300))
        nse = rng.random() * 2 - 1
        clk = 1.0 if math.sin(2 * math.pi * 2200 * t) > 0 else -1.0
        out.append(max(-1, min(1, (clk * 0.4 + nse * 0.55) * env)))
    return out

def synth_nade(rate=SND_RATE):
    N = int(rate * 0.12); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 10)
        out.append(math.sin(2 * math.pi * (180 + 40 * t) * t) * env * 0.4)
    return out

def synth_boom(rate=SND_RATE):
    N = int(rate * 0.24); out = []; rng = random.Random(33); lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 9)
        white = rng.random() * 2 - 1
        lp = lp + 0.4 * (white - lp)
        th = math.sin(2 * math.pi * (70 + 30 * math.exp(-t * 16)) * t)
        out.append(max(-1, min(1, (lp * 0.6 + th * 0.7) * env)))
    return out

def synth_pop(rate=SND_RATE):
    N = int(rate * 0.12); out = []; rng = random.Random(22); lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 16)
        white = rng.random() * 2 - 1
        lp = lp + 0.55 * (white - lp)
        out.append(max(-1, min(1, (lp * 0.6 + math.sin(2 * math.pi * 200 * t) * 0.4) * env)))
    return out

def synth_hurt(rate=SND_RATE):
    N = int(rate * 0.16); out = []
    for i in range(N):
        t = i / rate
        f = 300 - 160 * (t / 0.16)
        env = math.exp(-t * 8)
        sq = 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0
        out.append(sq * env * 0.32)
    return out

def synth_gameover(rate=SND_RATE):
    N = int(rate * 0.3); out = []
    for i in range(N):
        t = i / rate
        f = 400 - 280 * (t / 0.3)
        env = math.exp(-t * 3.5)
        sq = 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0
        out.append(sq * env * 0.4)
    return out

# ============================================================
#  SVG
# ============================================================
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#F4A261"/>
      <stop offset="0.45" stop-color="#E9C46A"/>
      <stop offset="1" stop-color="#C4A35A"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <ellipse cx="70" cy="48" rx="26" ry="26" fill="#FFE08A"/>
  <polygon points="0,210 70,150 130,200 200,130 280,190 360,140 480,200 480,280 0,280" fill="#8D6A3A" opacity="0.35"/>
  <rect x="0" y="280" width="480" height="80" fill="#6B4F2A"/>
  <rect x="0" y="278" width="480" height="8" fill="#8A6A3B"/>
  <text x="240" y="24" text-anchor="middle" fill="#5C3310" font-family="Arial, sans-serif" font-size="12" font-weight="bold">←→이동 ↑↓곡사각 space차지발사 X수류탄</text>
</svg>"""

IDLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="32" viewBox="0 0 56 32">
  <ellipse cx="28" cy="30" rx="20" ry="3" fill="#000" opacity="0.28"/>
  <rect x="6" y="20" width="44" height="9" rx="2" fill="#3E3A32" stroke="#1B1B1B" stroke-width="1.2"/>
  <circle cx="12" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="22" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="34" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="44" cy="25" r="3.2" fill="#1A1A1A"/>
  <rect x="8" y="10" width="38" height="12" rx="2" fill="#2E7D32" stroke="#1B5E20" stroke-width="1.4"/>
  <rect x="10" y="12" width="10" height="7" rx="1" fill="#81C784" opacity="0.45"/>
  <rect x="20" y="4" width="16" height="10" rx="2" fill="#1B5E20" stroke="#0D3B12" stroke-width="1.2"/>
  <polygon points="28,7 29.2,10 32,10 29.8,12 30.8,15 28,13.2 25.2,15 26.2,12 24,10 26.8,10" fill="#F5D76E"/>
</svg>"""

RELOAD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="32" viewBox="0 0 56 32">
  <ellipse cx="28" cy="30" rx="20" ry="3" fill="#000" opacity="0.28"/>
  <rect x="6" y="20" width="44" height="9" rx="2" fill="#3E3A32" stroke="#1B1B1B" stroke-width="1.2"/>
  <circle cx="12" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="22" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="34" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="44" cy="25" r="3.2" fill="#1A1A1A"/>
  <rect x="8" y="12" width="38" height="10" rx="2" fill="#2E7D32" stroke="#1B5E20" stroke-width="1.4"/>
  <rect x="22" y="2" width="14" height="8" rx="1.5" fill="#1B5E20" transform="rotate(-28 29 6)"/>
  <rect x="34" y="6" width="5" height="10" rx="1" fill="#5D4037" stroke="#3E2723" stroke-width="0.8"/>
</svg>"""

BULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <circle cx="8" cy="8" r="7" fill="#FFB300" stroke="#E65100" stroke-width="1.4"/>
  <circle cx="6" cy="5.5" r="2.4" fill="#FFE082" opacity="0.85"/>
</svg>"""

NADE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="16" viewBox="0 0 14 16">
  <rect x="5" y="0" width="4" height="4" fill="#33691E"/>
  <circle cx="7" cy="10" r="5.5" fill="#33691E" stroke="#1B5E20" stroke-width="1.2"/>
</svg>"""

BOOM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 72 72">
  <circle cx="36" cy="36" r="34" fill="#FF9800" opacity="0.35"/>
  <polygon points="36,4 41,26 66,22 48,40 62,62 36,50 10,62 24,40 6,22 31,26" fill="#FF9800" stroke="#E65100" stroke-width="2"/>
  <circle cx="36" cy="36" r="12" fill="#FFF176"/>
</svg>"""

TILE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <rect x="1" y="1" width="22" height="22" fill="#C4A574" stroke="#6D4C41" stroke-width="2"/>
  <rect x="4" y="4" width="7" height="7" fill="#D7BC8A" opacity="0.7"/>
</svg>"""

GUN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="10" viewBox="0 0 40 10">
  <rect x="0" y="2" width="8" height="6" rx="1" fill="#1B5E20" stroke="#0D3B12" stroke-width="0.7"/>
  <rect x="7" y="3" width="24" height="4" rx="1" fill="#37474F"/>
  <rect x="30" y="2.2" width="7" height="5.6" rx="0.8" fill="#102027"/>
  <rect x="37" y="3.6" width="3" height="2.8" rx="0.4" fill="#FFE082"/>
</svg>"""

SHIELD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="28" viewBox="0 0 18 28">
  <path d="M9 2 L16 8 L16 20 L9 26 L2 20 L2 8 Z" fill="#90A4AE" stroke="#37474F" stroke-width="2"/>
  <path d="M9 6 L13 9 L13 18 L9 22 L5 18 L5 9 Z" fill="#ECEFF1"/>
</svg>"""

WALKER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="32" viewBox="0 0 56 32">
  <ellipse cx="28" cy="30" rx="20" ry="3" fill="#000" opacity="0.28"/>
  <rect x="6" y="20" width="44" height="9" rx="2" fill="#3E3A32" stroke="#1B1B1B" stroke-width="1.2"/>
  <circle cx="12" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="22" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="34" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="44" cy="25" r="3.2" fill="#1A1A1A"/>
  <rect x="8" y="10" width="38" height="12" rx="2" fill="#8B2E2E" stroke="#5D1A1A" stroke-width="1.4"/>
  <rect x="20" y="4" width="16" height="10" rx="2" fill="#5D1A1A" stroke="#3E0E0E" stroke-width="1.2"/>
  <rect x="34" y="7" width="16" height="4" rx="1" fill="#37474F"/>
</svg>"""

SHOOTER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="32" viewBox="0 0 56 32">
  <ellipse cx="28" cy="30" rx="20" ry="3" fill="#000" opacity="0.28"/>
  <rect x="6" y="20" width="44" height="9" rx="2" fill="#3E3A32" stroke="#1B1B1B" stroke-width="1.2"/>
  <circle cx="12" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="22" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="34" cy="25" r="3.2" fill="#1A1A1A"/>
  <circle cx="44" cy="25" r="3.2" fill="#1A1A1A"/>
  <rect x="8" y="10" width="38" height="12" rx="2" fill="#37474F" stroke="#212121" stroke-width="1.4"/>
  <rect x="20" y="3" width="16" height="11" rx="2" fill="#1A237E" stroke="#0D1457" stroke-width="1.2"/>
  <rect x="34" y="6" width="18" height="4.5" rx="1" fill="#263238"/>
  <rect x="50" y="4.5" width="5" height="7" rx="1" fill="#FF8F00"/>
</svg>"""

EBULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <circle cx="8" cy="8" r="7" fill="#FF5252" stroke="#B71C1C" stroke-width="1.4"/>
  <circle cx="6" cy="5.5" r="2.4" fill="#FFCDD2" opacity="0.8"/>
</svg>"""

GAMEOVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="5" y="5" width="350" height="140" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="62" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="42" font-weight="bold">GAME OVER</text>
  <text x="180" y="96" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="18">점수와 웨이브는 왼쪽 위!</text>
  <text x="180" y="126" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="14">초록 깃발(▶) 다시 도전</text>
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

_cmt_ic = [0]
def add_comment(bs, comments, block_id, text, x=520, y=40, w=300, h=140):
    _cmt_ic[0] += 1
    cid = f"cmt{_cmt_ic[0]:03d}"
    comments[cid] = {"blockId": block_id, "x": x, "y": y, "width": w, "height": h,
                     "minimized": False, "text": text}
    if block_id in bs:
        bs[block_id]["comment"] = cid
    return cid

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

def b_setvar(bs, name, vid, value):
    bid = gen()
    if isinstance(value, str) and value in bs:
        bs[bid] = mk("data_setvariableto", inputs={"VALUE": slot(value)},
                     fields={"VARIABLE": [name, vid]})
        bs[value]["parent"] = bid
    else:
        bs[bid] = mk("data_setvariableto", inputs={"VALUE": num(value)},
                     fields={"VARIABLE": [name, vid]})
    return bid

def b_changevar(bs, name, vid, value):
    bid = gen()
    if isinstance(value, str) and value in bs:
        bs[bid] = mk("data_changevariableby", inputs={"VALUE": slot(value)},
                     fields={"VARIABLE": [name, vid]})
        bs[value]["parent"] = bid
    else:
        bs[bid] = mk("data_changevariableby", inputs={"VALUE": num(value)},
                     fields={"VARIABLE": [name, vid]})
    return bid

def b_keypressed(bs, key):
    m = gen(); bs[m] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": [key, None]}, shadow=True)
    p = gen(); bs[p] = mk("sensing_keypressed", inputs={"KEY_OPTION": [1, m]})
    bs[m]["parent"] = p
    return p

def b_touching(bs, target):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": [target, None]}, shadow=True)
    t = gen(); bs[t] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, m]})
    bs[m]["parent"] = t
    return t

def b_if(bs, cond, body_head):
    bid = gen(); bs[bid] = mk("control_if",
        inputs={"CONDITION": [2, cond], "SUBSTACK": [2, body_head]})
    bs[cond]["parent"] = bid; bs[body_head]["parent"] = bid
    return bid

def b_ifelse(bs, cond, head_t, head_f):
    bid = gen(); bs[bid] = mk("control_if_else",
        inputs={"CONDITION": [2, cond], "SUBSTACK": [2, head_t], "SUBSTACK2": [2, head_f]})
    bs[cond]["parent"] = bid; bs[head_t]["parent"] = bid; bs[head_f]["parent"] = bid
    return bid

def b_forever(bs, head):
    bid = gen(); bs[bid] = mk("control_forever", inputs={"SUBSTACK": [2, head]})
    bs[head]["parent"] = bid
    return bid

def b_repeat(bs, times, head):
    bid = gen()
    if isinstance(times, str) and times in bs:
        bs[bid] = mk("control_repeat", inputs={"TIMES": slot(times), "SUBSTACK": [2, head]})
        bs[times]["parent"] = bid
    else:
        bs[bid] = mk("control_repeat", inputs={"TIMES": num(times), "SUBSTACK": [2, head]})
    bs[head]["parent"] = bid
    return bid

def b_repeat_until(bs, cond, head):
    bid = gen(); bs[bid] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond], "SUBSTACK": [2, head]})
    bs[cond]["parent"] = bid; bs[head]["parent"] = bid
    return bid

def b_wait(bs, dur):
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": num(dur)})
    return bid

def b_wait_var(bs, vid, name):
    v = gen(); bs[v] = mk("data_variable", fields={"VARIABLE": [name, vid]})
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": slot(v)})
    bs[v]["parent"] = bid
    return bid

def b_broadcast(bs, name, brid):
    m = gen(); bs[m] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcast", inputs={"BROADCAST_INPUT": [1, m]})
    bs[m]["parent"] = b
    return b

def b_costume(bs, name):
    cmc = gen(); bs[cmc] = mk("looks_costume", fields={"COSTUME": [name, None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc]})
    bs[cmc]["parent"] = sw
    return sw

def b_backdrop_to(bs, val):
    """무대 배경 바꾸기. val 은 이름 문자열 또는 reporter 블록 id."""
    sw = gen()
    if isinstance(val, str) and val in bs:
        bs[sw] = mk("looks_switchbackdropto",
                    inputs={"BACKDROP": [3, val, [10, "bg1"]]})
        bs[val]["parent"] = sw
    else:
        m = gen(); bs[m] = mk("looks_backdrops",
            fields={"BACKDROP": [str(val), None]}, shadow=True)
        bs[sw] = mk("looks_switchbackdropto", inputs={"BACKDROP": [1, m]})
        bs[m]["parent"] = sw
    return sw

def emit_switch_bg(bs, vrep, op, cmp_op):
    """(웨이브-1) mod 6 + 1 → 스테이지 1~6. 6이면 보스전. returns (head, tail)."""
    wv = vrep("웨이브", V_WAVE)
    wm1 = op("operator_subtract", wv, 1)
    md = op("operator_mod", wm1, 6)
    idx = op("operator_add", md, 1)
    setst = b_setvar(bs, "스테이지", V_STAGE, idx)
    stg = vrep("스테이지", V_STAGE)
    name = b_join(bs, "bg", stg)
    sw = b_backdrop_to(bs, name)
    stg2 = vrep("스테이지", V_STAGE)
    is6 = cmp_op("operator_equals", stg2, 6)
    on = b_setvar(bs, "보스전", V_BOSSFIGHT, 1)
    brb = b_broadcast(bs, "보스생성", BR_BOSS)
    chain([(on, bs[on]), (brb, bs[brb])])
    off = b_setvar(bs, "보스전", V_BOSSFIGHT, 0)
    ifb = b_ifelse(bs, is6, on, off)
    chain([(setst, bs[setst]), (sw, bs[sw]), (ifb, bs[ifb])])
    return setst, ifb

def b_gotoxy(bs, x_val, y_val):
    bid = gen()
    xin = slot(x_val) if (isinstance(x_val, str) and x_val in bs) else num(x_val)
    yin = slot(y_val) if (isinstance(y_val, str) and y_val in bs) else num(y_val)
    bs[bid] = mk("motion_gotoxy", inputs={"X": xin, "Y": yin})
    if isinstance(x_val, str) and x_val in bs: bs[x_val]["parent"] = bid
    if isinstance(y_val, str) and y_val in bs: bs[y_val]["parent"] = bid
    return bid

def b_setx(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_setx", inputs={"X": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_sety(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_sety", inputs={"Y": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_changexby(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_changexby", inputs={"DX": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_changeyby(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_changeyby", inputs={"DY": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_xpos(bs):
    bid = gen(); bs[bid] = mk("motion_xposition"); return bid
def b_ypos(bs):
    bid = gen(); bs[bid] = mk("motion_yposition"); return bid

def b_point_dir(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_pointindirection", inputs={"DIRECTION": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_movesteps(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_movesteps", inputs={"STEPS": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_goto_sprite(bs, name):
    m = gen(); bs[m] = mk("motion_goto_menu", fields={"TO": [name, None]}, shadow=True)
    g = gen(); bs[g] = mk("motion_goto", inputs={"TO": [1, m]})
    bs[m]["parent"] = g
    return g

def b_clone_self(bs):
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    return cclone

def b_del_clone(bs):
    bid = gen(); bs[bid] = mk("control_delete_this_clone"); return bid

def b_setsize(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("looks_setsizeto", inputs={"SIZE": inp})
    if isinstance(val, str) and val in bs:
        bs[val]["parent"] = bid
    return bid

def b_front(bs):
    bid = gen(); bs[bid] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    return bid

def b_show(bs):
    bid = gen(); bs[bid] = mk("looks_show"); return bid
def b_hide(bs):
    bid = gen(); bs[bid] = mk("looks_hide"); return bid

def b_join(bs, a, b):
    bid = gen()
    def enc(v):
        if isinstance(v, str) and v in bs:
            return slot(v, 10, "")
        return text_lit(v)
    bs[bid] = mk("operator_join", inputs={"STRING1": enc(a), "STRING2": enc(b)})
    for v in (a, b):
        if isinstance(v, str) and v in bs:
            bs[v]["parent"] = bid
    return bid

def b_sayfor(bs, msg, secs):
    bid = gen()
    if isinstance(msg, str) and msg in bs:
        minp = slot(msg, 10, "hello")
    else:
        minp = text_lit(msg)
    if isinstance(secs, str) and secs in bs:
        sinp = slot(secs)
    else:
        sinp = num(secs)
    bs[bid] = mk("looks_sayforsecs", inputs={"MESSAGE": minp, "SECS": sinp})
    if isinstance(msg, str) and msg in bs:
        bs[msg]["parent"] = bid
    if isinstance(secs, str) and secs in bs:
        bs[secs]["parent"] = bid
    return bid

def b_rotstyle(bs, style):
    bid = gen(); bs[bid] = mk("motion_setrotationstyle", fields={"STYLE": [style, None]})
    return bid

def b_abs(bs, val):
    return b_mathop(bs, "abs", val)

def b_mathop(bs, opname, val):
    bid = gen()
    if isinstance(val, str) and val in bs:
        bs[bid] = mk("operator_mathop", inputs={"NUM": slot(val)}, fields={"OPERATOR": [opname, None]})
        bs[val]["parent"] = bid
    else:
        bs[bid] = mk("operator_mathop", inputs={"NUM": num(val)}, fields={"OPERATOR": [opname, None]})
    return bid

def b_random(bs, a, b_):
    bid = gen()
    ins = {}
    for key, val in [("FROM", a), ("TO", b_)]:
        if isinstance(val, str): ins[key] = slot(val)
        else: ins[key] = num(val)
    bs[bid] = mk("operator_random", inputs=ins)
    for v in (a, b_):
        if isinstance(v, str) and v in bs: bs[v]["parent"] = bid
    return bid

def b_pen(bs, opcode):
    bid = gen(); bs[bid] = mk(opcode); return bid

def b_stamp(bs):
    bid = gen(); bs[bid] = mk("pen_stamp"); return bid

def b_item_of(bs, listname, listid, idx):
    bid = gen()
    if isinstance(idx, str) and idx in bs:
        bs[bid] = mk("data_itemoflist", inputs={"INDEX": slot(idx)},
                     fields={"LIST": [listname, listid]})
        bs[idx]["parent"] = bid
    else:
        bs[bid] = mk("data_itemoflist", inputs={"INDEX": num(idx)},
                     fields={"LIST": [listname, listid]})
    return bid

def b_add_to_list(bs, listname, listid, value_child):
    bid = gen()
    if isinstance(value_child, str) and value_child in bs:
        bs[bid] = mk("data_addtolist", inputs={"ITEM": slot(value_child)},
                     fields={"LIST": [listname, listid]})
        bs[value_child]["parent"] = bid
    else:
        bs[bid] = mk("data_addtolist", inputs={"ITEM": num(value_child)},
                     fields={"LIST": [listname, listid]})
    return bid

def b_delete_all(bs, listname, listid):
    bid = gen(); bs[bid] = mk("data_deletealloflist", fields={"LIST": [listname, listid]})
    return bid

def b_replace(bs, listname, listid, idx, item):
    bid = gen()
    i_in = slot(idx) if (isinstance(idx, str) and idx in bs) else num(idx)
    it_in = slot(item) if (isinstance(item, str) and item in bs) else num(item)
    bs[bid] = mk("data_replaceitemoflist",
        inputs={"INDEX": i_in, "ITEM": it_in},
        fields={"LIST": [listname, listid]})
    if isinstance(idx, str) and idx in bs: bs[idx]["parent"] = bid
    if isinstance(item, str) and item in bs: bs[item]["parent"] = bid
    return bid

def b_length_of(bs, listname, listid):
    bid = gen(); bs[bid] = mk("data_lengthoflist", fields={"LIST": [listname, listid]})
    return bid

def emit_col_from_x(bs, vrep, op, cmp_op, col_name, col_id):
    xp = b_xpos(bs)
    plus = op("operator_add", xp, 240)
    cw = vrep("칸크기", V_CELLW)
    div = op("operator_divide", plus, cw)
    fl = gen(); bs[fl] = mk("operator_mathop", inputs={"NUM": slot(div)},
                            fields={"OPERATOR": ["floor", None]})
    bs[div]["parent"] = fl
    plus1 = op("operator_add", fl, 1)
    setc = b_setvar(bs, col_name, col_id, plus1)
    col_r = vrep(col_name, col_id)
    if_lo = b_if(bs, cmp_op("operator_lt", col_r, 1), b_setvar(bs, col_name, col_id, 1))
    col_r2 = vrep(col_name, col_id)
    cn = vrep("칸수", V_CELLN)
    cn2 = vrep("칸수", V_CELLN)
    if_hi = b_if(bs, cmp_op("operator_gt", col_r2, cn), b_setvar(bs, col_name, col_id, cn2))
    chain([(setc, bs[setc]), (if_lo, bs[if_lo]), (if_hi, bs[if_hi])])
    return setc, if_hi

def emit_ground_y(bs, vrep, op, col_name, col_id):
    """지면Y = 바닥Y + (칸높이-1)*칸크기. returns reporter id."""
    col = vrep(col_name, col_id)
    h = b_item_of(bs, "지형높이", L_HEIGHT, col)
    hm1 = op("operator_subtract", h, 1)
    cw = vrep("칸크기", V_CELLW)
    rise = op("operator_multiply", hm1, cw)
    base = vrep("바닥Y", V_FLOOR)
    return op("operator_add", base, rise)

def emit_ballistic_init(bs, vrep, op, dir_name, dir_id, spd_name, spd_id,
                        vx_name, vx_id, vy_name, vy_id):
    """속도X = 탄속*sin(방향), 속도Y = 탄속*cos(방향). Scratch 90=오른쪽."""
    spd = vrep(spd_name, spd_id)
    d1 = vrep(dir_name, dir_id)
    s = b_mathop(bs, "sin", d1)
    vx = op("operator_multiply", spd, s)
    svx = b_setvar(bs, vx_name, vx_id, vx)
    spd2 = vrep(spd_name, spd_id)
    d2 = vrep(dir_name, dir_id)
    c = b_mathop(bs, "cos", d2)
    vy = op("operator_multiply", spd2, c)
    svy = b_setvar(bs, vy_name, vy_id, vy)
    chain([(svx, bs[svx]), (svy, bs[svy])])
    return svx, svy

def emit_ballistic_tick(bs, vrep, op, cmp_op, vx_name, vx_id, vy_name, vy_id):
    """탄중력 적용 후 x,y 이동, 포탄이 속도 방향을 향함. returns (head, tail)."""
    g = vrep("탄중력", V_SHOTGRAV)
    chvy = b_changevar(bs, vy_name, vy_id, g)
    vx = vrep(vx_name, vx_id)
    cx = b_changexby(bs, vx)
    vy = vrep(vy_name, vy_id)
    cy = b_changeyby(bs, vy)
    vxr = vrep(vx_name, vx_id)
    going_r = cmp_op("operator_gt", vxr, 0)
    vyr = vrep(vy_name, vy_id)
    vxa = vrep(vx_name, vx_id)
    adx = b_abs(bs, vxa)
    den = op("operator_add", adx, 0.1)
    ratio = op("operator_divide", vyr, den)
    elev = b_mathop(bs, "atan", ratio)
    dir_r = op("operator_subtract", 90, elev)
    pr = b_point_dir(bs, dir_r)
    vyl = vrep(vy_name, vy_id)
    vxb = vrep(vx_name, vx_id)
    adxl = b_abs(bs, vxb)
    denl = op("operator_add", adxl, 0.1)
    ratiol = op("operator_divide", vyl, denl)
    elevl = b_mathop(bs, "atan", ratiol)
    dir_l = op("operator_add", -90, elevl)
    pl = b_point_dir(bs, dir_l)
    ifdir = b_ifelse(bs, going_r, pr, pl)
    chain([(chvy, bs[chvy]), (cx, bs[cx]), (cy, bs[cy]), (ifdir, bs[ifdir])])
    return chvy, ifdir

def emit_boom_anim(bs):
    """착탄 뻥! 4프레임. returns (head, tail)."""
    rs = b_rotstyle(bs, "don't rotate")
    pt = b_point_dir(bs, 90)
    fr = b_front(bs)
    bh, bt = b_sound(bs, 0, "boom")
    seq = [(rs, bs[rs]), (pt, bs[pt]), (fr, bs[fr]), (bh, bs[bh]), (bt, bs[bt])]
    for i, name in enumerate(("boom1", "boom2", "boom3", "boom4")):
        c = b_costume(bs, name)
        s = b_setsize(bs, 90 + i * 40)
        w = b_wait(bs, 0.05)
        seq.extend([(c, bs[c]), (s, bs[s]), (w, bs[w])])
    chain(seq)
    return seq[0][0], seq[-1][0]

def b_setghost(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("looks_seteffectto", inputs={"VALUE": inp}, fields={"EFFECT": ["GHOST", None]})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_sound(bs, pitch, sound):
    pe = gen(); bs[pe] = mk("sound_seteffectto",
        inputs={"VALUE": num(pitch)}, fields={"EFFECT": ["PITCH", None]})
    sm = gen(); bs[sm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]})
    bs[sm]["parent"] = sp
    chain([(pe, bs[pe]), (sp, bs[sp])])
    return pe, sp

# ============================================================
#  IDs
# ============================================================
V_MOVE     = "varMove01"
V_JUMP     = "varJump02"
V_GRAV     = "varGrav03"
V_FLOOR    = "varFloor04"
V_FIREGAP  = "varFireGap05"
V_SHOTSPD  = "varShotSpd06"
V_MAXSHOT  = "varMaxShot07"
V_NADESPD  = "varNadeSpd08"
V_NADEUP   = "varNadeUp09"
V_NADECD   = "varNadeCD10"
V_ENSPD    = "varEnSpd11"
V_SPAWN    = "varSpawn12"
V_MAXEN    = "varMaxEn13"
V_MAXHP    = "varMaxHP14"
V_ENATK    = "varEnAtk15"
V_IFRAME   = "varIFrame16"
V_RAMP     = "varRamp17"
V_MUZZLEY  = "varMuzzleY19"
V_MUZZLEF  = "varMuzzleF20"
V_SHOTRAD  = "varShotRad21"
V_NADERAD  = "varNadeRad22"
V_BARHOP   = "varBarHop23"
V_SHOOTP   = "varShootP24"
V_BACKP    = "varBackP25"
V_RANGE    = "varRange26"
V_EFIREGAP = "varEFireG27"
V_ESHOTSPD = "varEShotS28"
V_MAXESHOT = "varMaxESh29"
V_CELLW    = "varCellW30"
V_CELLN    = "varCellN31"
V_MAG      = "varMag32"
V_RELOADT  = "varReloadT33"
V_BALLLIFE = "varBallLife34"
V_AIMSTEP  = "varAimStep35"
V_SHOTGRAV = "varShotGrav36"

V_STATE    = "varState40"
V_SCORE    = "varScore41"
V_HP       = "varHP42"
V_WAVE     = "varWave43"
V_SHOTN    = "varShotN44"
V_ENN      = "varEnN45"
V_KILLS    = "varKills46"
V_FACING   = "varFacing47"
V_NADET    = "varNadeT48"
V_VY       = "varVY49"
V_PREVJ    = "varPrevJ50"
V_IFRMT    = "varIFrmT51"
V_NADEN    = "varNadeN52"
V_SHOTHITX = "varShotHitX56"
V_NADEHITX = "varNadeHitX57"
V_PLAYERX  = "varPlayerX58"
V_ESHOTN   = "varEShotN59"
V_ESHOTX   = "varEShotX60"
V_ESHOTY   = "varEShotY61"
V_ESHOTDIR = "varEShotDir62"
V_AMMO     = "varAmmo63"
V_RELOADING= "varReloading64"
V_RELLEFT  = "varRelLeft65"
V_SHIELD   = "varShield66"
V_TERRI    = "varTerrI67"
V_TMP      = "varTmp68"
V_TMPK     = "varTmpK69"
V_ANGLE    = "varAngle70"
V_FIREDIR  = "varFireDir71"
V_PLAYERY  = "varPlayerY72"
V_WAVEKILLS= "varWaveKills73"
V_POWER    = "varPower74"
V_CHARGING = "varCharging75"
V_POWSPD   = "varPowSpd76"
V_MINPOW   = "varMinPow77"
V_MAXPOW   = "varMaxPow78"
V_FIRESPD  = "varFireSpd79"
V_BGMVOL   = "varBgmVol80"
V_POWSCALE = "varPowScale81"
V_BOSSFIGHT= "varBossFight82"
V_BOSSHP   = "varBossHP83"
V_BOSSMAXHP= "varBossMaxHP84"
V_BOSSBASE = "varBossBase85"
V_BOSSIFRM = "varBossIFrm86"
V_STAGE    = "varStage87"
V_BOSSCD   = "varBossCD88"
V_BOSSCOL  = "varBossCol89"
V_BOSSFACE = "varBossFace90"

BR_START   = "brStart01"
BR_FIRE    = "brFire02"
BR_NADE    = "brNade03"
BR_SPAWN   = "brSpawn04"
BR_OVER    = "brOver05"
BR_HITSHOT = "brHitShot06"
BR_HITNADE = "brHitNade07"
BR_ESHOT   = "brEShot08"
BR_MAP     = "brMap09"
BR_HURT    = "brHurt10"
BR_DRAW    = "brDraw10"
BR_BOSS    = "brBoss12"

L_HEIGHT   = "listHeight01"

V_TANKCOL  = "varTankCol"
V_SHOTCOL  = "varShotCol"
V_NCOL     = "varNadeCol"
V_ENCOL    = "varEnCol"
V_ESCOL    = "varEShotCol"
V_SHOTLIFE = "varShotLife"
V_SHOTVX   = "varShotVX"
V_SHOTVY   = "varShotVY"
V_ESLIFE   = "varEShotLife"
V_ESHOTVX  = "varEShotVX"
V_ESHOTVY  = "varEShotVY"

V_ENKIND   = "varEnKind"
V_ENVY     = "varEnVY"
V_ENFACE   = "varEnFace"
V_ENFIRET  = "varEnFireT"
V_ENBLOCK  = "varEnBlock"
V_ESHOTISC = "varEShotIsC"

V_SHOTISC  = "varShotIsC"
V_NADEISC  = "varNadeIsC"
V_NADEVX   = "varNadeVX"
V_NADEVY   = "varNadeVY"
V_ENISC    = "varEnIsC"

def build_map_gen_seq(bs, vrep, op):
    """평지(1) + 지나갈 수 있는 엄폐 상자(2~3). returns (head_id, tail_id)."""
    seq = []
    dal = b_delete_all(bs, "지형높이", L_HEIGHT)
    seq.append((dal, bs[dal]))
    addl = b_add_to_list(bs, "지형높이", L_HEIGHT, 1)
    cn = vrep("칸수", V_CELLN)
    rep = b_repeat(bs, cn, addl)
    seq.append((rep, bs[rep]))
    ri = b_random(bs, 4, 8)
    st = b_setvar(bs, "임시", V_TMP, ri)
    seq.append((st, bs[st]))
    tmp = vrep("임시", V_TMP)
    rp = b_replace(bs, "지형높이", L_HEIGHT, tmp, 2)
    seq.append((rp, bs[rp]))
    tmpb = vrep("임시", V_TMP)
    ri1 = op("operator_add", tmpb, 1)
    rp1 = b_replace(bs, "지형높이", L_HEIGHT, ri1, 2)
    seq.append((rp1, bs[rp1]))
    ri2 = b_random(bs, 12, 16)
    st2 = b_setvar(bs, "임시", V_TMP, ri2)
    seq.append((st2, bs[st2]))
    tmp2 = vrep("임시", V_TMP)
    rp2 = b_replace(bs, "지형높이", L_HEIGHT, tmp2, 2)
    seq.append((rp2, bs[rp2]))
    tmp2b = vrep("임시", V_TMP)
    ri2n = op("operator_add", tmp2b, 1)
    rp2n = b_replace(bs, "지형높이", L_HEIGHT, ri2n, 2)
    seq.append((rp2n, bs[rp2n]))
    ri3 = b_random(bs, 9, 11)
    rp3 = b_replace(bs, "지형높이", L_HEIGHT, ri3, 3)
    seq.append((rp3, bs[rp3]))
    br = b_broadcast(bs, "지형그리기", BR_DRAW)
    seq.append((br, bs[br]))
    chain(seq)
    return seq[0][0], seq[-1][0]

# ============================================================
#  Stage
# ============================================================
def build_stage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        b = b_setvar(bs, name, vid, val)
        seq.append((b, bs[b]))
        return b
    g0 = add_set("이동속도", V_MOVE, 4)
    add_set("점프력", V_JUMP, 11)
    add_set("중력", V_GRAV, -1.1)
    add_set("바닥Y", V_FLOOR, -100)
    add_set("연사간격", V_FIREGAP, 0.18)
    add_set("탄속", V_SHOTSPD, 10)
    add_set("최대탄수", V_MAXSHOT, 6)
    add_set("수류탄력", V_NADESPD, 6)
    add_set("수류탄띄움", V_NADEUP, 10)
    add_set("수류탄쿨", V_NADECD, 1.2)
    add_set("적속도", V_ENSPD, 1.3)
    add_set("스폰간격", V_SPAWN, 1.2)
    add_set("최대적수", V_MAXEN, 6)
    add_set("최대체력", V_MAXHP, 5)
    add_set("적공격", V_ENATK, 1)
    add_set("무적시간", V_IFRAME, 1.0)
    add_set("난이도증가율", V_RAMP, 0.05)
    add_set("웨이브킬", V_WAVEKILLS, 16)
    add_set("브금볼륨", V_BGMVOL, 70)
    add_set("총알높이", V_MUZZLEY, 24)
    add_set("총구앞", V_MUZZLEF, 18)
    add_set("탄히트범위", V_SHOTRAD, 55)
    add_set("수류탄범위", V_NADERAD, 100)
    add_set("장벽넘기", V_BARHOP, 26)
    add_set("사수확률", V_SHOOTP, 35)
    add_set("뒤쪽확률", V_BACKP, 28)
    add_set("사정거리", V_RANGE, 110)
    add_set("적연사간격", V_EFIREGAP, 1.1)
    add_set("적탄속", V_ESHOTSPD, 7)
    add_set("최대적탄", V_MAXESHOT, 4)
    add_set("게임상태", V_STATE, 1)
    add_set("점수", V_SCORE, 0)
    hp0 = vrep("최대체력", V_MAXHP)
    shp = b_setvar(bs, "체력", V_HP, hp0)
    seq.append((shp, bs[shp]))
    add_set("웨이브", V_WAVE, 1)
    add_set("탄수", V_SHOTN, 0)
    add_set("적수", V_ENN, 0)
    add_set("처치수", V_KILLS, 0)
    add_set("바라봄", V_FACING, 90)
    add_set("수류탄쿨남은", V_NADET, 0)
    add_set("VY", V_VY, 0)
    add_set("점프이전키", V_PREVJ, 0)
    add_set("무적타이머", V_IFRMT, 0)
    add_set("수류탄수", V_NADEN, 0)
    add_set("탄히트X", V_SHOTHITX, 0)
    add_set("수류탄히트X", V_NADEHITX, 0)
    add_set("플레이어X", V_PLAYERX, -140)
    add_set("적탄수", V_ESHOTN, 0)
    add_set("적탄X", V_ESHOTX, 0)
    add_set("적탄Y", V_ESHOTY, 0)
    add_set("적탄방향", V_ESHOTDIR, -90)
    add_set("칸크기", V_CELLW, 24)
    add_set("칸수", V_CELLN, 20)
    add_set("탄창", V_MAG, 6)
    add_set("재장전시간", V_RELOADT, 0.8)
    add_set("포탄수명", V_BALLLIFE, 90)
    add_set("조준속도", V_AIMSTEP, 4)
    add_set("탄중력", V_SHOTGRAV, -0.85)
    add_set("각도", V_ANGLE, 50)
    add_set("발사방향", V_FIREDIR, 40)
    add_set("플레이어Y", V_PLAYERY, -100)
    mag = vrep("탄창", V_MAG)
    sammo = b_setvar(bs, "남은탄", V_AMMO, mag)
    seq.append((sammo, bs[sammo]))
    add_set("재장전중", V_RELOADING, 0)
    add_set("재장전남은", V_RELLEFT, 0)
    add_set("방패중", V_SHIELD, 0)
    add_set("파워", V_POWER, 0)
    add_set("차지중", V_CHARGING, 0)
    add_set("파워속도", V_POWSPD, 5)
    add_set("최소파워", V_MINPOW, 20)
    add_set("최대파워", V_MAXPOW, 100)
    add_set("파워배율", V_POWSCALE, 2.4)
    add_set("발사탄속", V_FIRESPD, 10)
    add_set("보스전", V_BOSSFIGHT, 0)
    add_set("보스체력", V_BOSSHP, 0)
    add_set("보스최대체력", V_BOSSMAXHP, 8)
    add_set("보스기본체력", V_BOSSBASE, 8)
    add_set("보스무적", V_BOSSIFRM, 0)
    add_set("보스사격쿨", V_BOSSCD, 0)
    add_set("스테이지", V_STAGE, 1)
    add_set("지형i", V_TERRI, 1)
    add_set("임시", V_TMP, 0)
    add_set("임시k", V_TMPK, 1)
    chain(seq)
    last = seq[-1][0]
    mh, mt = build_map_gen_seq(bs, vrep, op)
    bs[last]["next"] = mh
    bs[mh]["parent"] = last
    sw_h, sw_t = emit_switch_bg(bs, vrep, op, cmp_op)
    br = b_broadcast(bs, "게임시작", BR_START)
    bs[mt]["next"] = sw_h; bs[sw_h]["parent"] = mt
    bs[sw_t]["next"] = br; bs[br]["parent"] = sw_t
    add_comment(bs, comments, g0,
        "🛠️ 개조 핸들 — 이동속도·탄속·조준속도를 바꾸면 손맛이 달라져요.\n"
        "↑↓ 각도. space 짧게=약, 길게=강. 게이지가 차면 멀리.\n"
        "착탄 시 범위 폭발. 한 칸은 지나감, 두 칸 벽은 막힘.",
        x=520, y=20, w=320, h=130)

    hmap = gen(); bs[hmap] = mk("event_whenbroadcastreceived", top=True, x=20, y=360,
        fields={"BROADCAST_OPTION": ["맵변경", BR_MAP]})
    frz = b_setvar(bs, "게임상태", V_STATE, 3)
    mh2, mt2 = build_map_gen_seq(bs, vrep, op)
    wmap = b_wait(bs, 1.6)
    zenn = b_setvar(bs, "적수", V_ENN, 0)
    zsh = b_setvar(bs, "탄수", V_SHOTN, 0)
    zes = b_setvar(bs, "적탄수", V_ESHOTN, 0)
    znd = b_setvar(bs, "수류탄수", V_NADEN, 0)
    unfrz = b_setvar(bs, "게임상태", V_STATE, 1)
    sw2_h, sw2_t = emit_switch_bg(bs, vrep, op, cmp_op)
    chain([(hmap, bs[hmap]), (frz, bs[frz])])
    bs[frz]["next"] = sw2_h; bs[sw2_h]["parent"] = frz
    bs[sw2_t]["next"] = mh2; bs[mh2]["parent"] = sw2_t
    chain([(mt2, bs[mt2]), (wmap, bs[wmap]), (zenn, bs[zenn]), (zsh, bs[zsh]),
           (zes, bs[zes]), (znd, bs[znd]), (unfrz, bs[unfrz])])

    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=20, y=480)
    w0 = b_wait(bs, 0.6)
    st = vrep("게임상태", V_STATE)
    play = cmp_op("operator_equals", st, 1)
    wg = b_wait_var(bs, V_SPAWN, "스폰간격")
    st2 = vrep("게임상태", V_STATE)
    still = cmp_op("operator_equals", st2, 1)
    enn = vrep("적수", V_ENN)
    mx = vrep("최대적수", V_MAXEN)
    room = cmp_op("operator_lt", enn, mx)
    both = bool_op("operator_and", still, room)
    bf = vrep("보스전", V_BOSSFIGHT)
    noboss = cmp_op("operator_equals", bf, 0)
    both2 = bool_op("operator_and", both, noboss)
    sp = b_broadcast(bs, "적생성", BR_SPAWN)
    ifsp = b_if(bs, both2, sp)
    chain([(wg, bs[wg]), (ifsp, bs[ifsp])])
    welse = b_wait(bs, 0.2)
    ifelse = b_ifelse(bs, play, wg, welse)
    fr = b_forever(bs, ifelse)
    chain([(h2, bs[h2]), (w0, bs[w0]), (fr, bs[fr])])

    # BGM: 별도 깃발 — 브금볼륨 후 forever play until done (곡 끝나면 루프)
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=20, y=720)
    bgmvol_r = vrep("브금볼륨", V_BGMVOL)
    setvol = gen(); bs[setvol] = mk("sound_setvolumeto", inputs={"VOLUME": slot(bgmvol_r)})
    bs[bgmvol_r]["parent"] = setvol
    bgm_menu = gen(); bs[bgm_menu] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["bgm", None]}, shadow=True)
    play_bgm = gen(); bs[play_bgm] = mk("sound_playuntildone", inputs={"SOUND_MENU": [1, bgm_menu]})
    bs[bgm_menu]["parent"] = play_bgm
    fe_bgm = b_forever(bs, play_bgm)
    chain([(hd, bs[hd]), (setvol, bs[setvol]), (fe_bgm, bs[fe_bgm])])
    return bs, comments

# ============================================================
#  지형 (칸 스탬프)
# ============================================================
def build_terrain_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    cl = b_pen(bs, "pen_clear")
    chain([(h, bs[h]), (hi, bs[hi]), (cl, bs[cl])])

    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["지형그리기", BR_DRAW]})
    cl2 = b_pen(bs, "pen_clear")
    hi2 = b_hide(bs)
    seti = b_setvar(bs, "지형i", V_TERRI, 1)
    # inner k loop body
    i_r = vrep("지형i", V_TERRI)
    half = op("operator_subtract", i_r, 0.5)
    cw = vrep("칸크기", V_CELLW)
    prod = op("operator_multiply", half, cw)
    kx = op("operator_add", -240, prod)
    k_r = vrep("임시k", V_TMPK)
    km1 = op("operator_subtract", k_r, 1)
    cw2 = vrep("칸크기", V_CELLW)
    rise = op("operator_multiply", km1, cw2)
    fl = vrep("바닥Y", V_FLOOR)
    topish = op("operator_add", fl, rise)
    halfc = vrep("칸크기", V_CELLW)
    halfv = op("operator_divide", halfc, 2)
    yy = op("operator_subtract", topish, halfv)
    go = b_gotoxy(bs, kx, yy)
    stmp = b_stamp(bs)
    inc_k = b_changevar(bs, "임시k", V_TMPK, 1)
    chain([(go, bs[go]), (stmp, bs[stmp]), (inc_k, bs[inc_k])])
    setk = b_setvar(bs, "임시k", V_TMPK, 1)
    i_h = vrep("지형i", V_TERRI)
    hgt = b_item_of(bs, "지형높이", L_HEIGHT, i_h)
    repk = b_repeat(bs, hgt, go)
    inc_i = b_changevar(bs, "지형i", V_TERRI, 1)
    chain([(setk, bs[setk]), (repk, bs[repk]), (inc_i, bs[inc_i])])
    cn = vrep("칸수", V_CELLN)
    repi = b_repeat(bs, cn, setk)
    chain([(hd, bs[hd]), (cl2, bs[cl2]), (hi2, bs[hi2]), (seti, bs[seti]), (repi, bs[repi])])
    return bs, comments

# ============================================================
#  지아이조
# ============================================================
def build_player_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sh = b_show(bs)
    rs = b_rotstyle(bs, "left-right")
    sz = b_setsize(bs, 100)
    fy = vrep("바닥Y", V_FLOOR)
    g0 = b_gotoxy(bs, -140, fy)
    idle = b_costume(bs, "idle")
    pt = b_point_dir(bs, 90)
    vy0 = b_setvar(bs, "VY", V_VY, 0)
    gh = b_setghost(bs, 0)
    ft = b_front(bs)
    chain([(h, bs[h]), (sh, bs[sh]), (rs, bs[rs]), (sz, bs[sz]), (g0, bs[g0]),
           (idle, bs[idle]), (pt, bs[pt]), (vy0, bs[vy0]), (gh, bs[gh]), (ft, bs[ft])])

    # (B) move / aim / gravity (점프 없음)
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=280)
    inner = []
    # right
    setf_r = b_setvar(bs, "바라봄", V_FACING, 90)
    pr = b_point_dir(bs, 90)
    mv = vrep("이동속도", V_MOVE)
    cxr = b_changexby(bs, mv)
    chain([(setf_r, bs[setf_r]), (pr, bs[pr]), (cxr, bs[cxr])])
    inner.append(b_if(bs, b_keypressed(bs, "right arrow"), setf_r))
    # left
    setf_l = b_setvar(bs, "바라봄", V_FACING, -90)
    pl = b_point_dir(bs, -90)
    mvl = vrep("이동속도", V_MOVE)
    nmove = op("operator_subtract", 0, mvl)
    cxl = b_changexby(bs, nmove)
    chain([(setf_l, bs[setf_l]), (pl, bs[pl]), (cxl, bs[cxl])])
    inner.append(b_if(bs, b_keypressed(bs, "left arrow"), setf_l))
    # clamp x
    xp = b_xpos(bs)
    inner.append(b_if(bs, cmp_op("operator_gt", xp, 220), b_setx(bs, 220)))
    xp2 = b_xpos(bs)
    inner.append(b_if(bs, cmp_op("operator_lt", xp2, -220), b_setx(bs, -220)))
    # 한 칸 높은 칸은 딛고 올라감, 두 칸 이상은 벽
    col_h, col_t = emit_col_from_x(bs, vrep, op, cmp_op, "칸번호", V_TANKCOL)
    gy = emit_ground_y(bs, vrep, op, "칸번호", V_TANKCOL)
    yp_w = b_ypos(bs)
    too_hi = cmp_op("operator_gt", gy, yp_w)
    yp_w2 = b_ypos(bs)
    gyb = emit_ground_y(bs, vrep, op, "칸번호", V_TANKCOL)
    slk = vrep("칸크기", V_CELLW)
    need = op("operator_subtract", gyb, slk)
    not_over = cmp_op("operator_lt", yp_w2, need)
    blocked = bool_op("operator_and", too_hi, not_over)
    facb = vrep("바라봄", V_FACING)
    going_r = cmp_op("operator_gt", facb, 0)
    mv_u = vrep("이동속도", V_MOVE)
    undo_r = op("operator_subtract", 0, mv_u)
    push_r = b_changexby(bs, undo_r)
    mv_u2 = vrep("이동속도", V_MOVE)
    push_l = b_changexby(bs, mv_u2)
    ifpush = b_ifelse(bs, going_r, push_r, push_l)
    ifblk = b_if(bs, blocked, ifpush)
    pxset = b_setvar(bs, "플레이어X", V_PLAYERX, b_xpos(bs))
    pyset = b_setvar(bs, "플레이어Y", V_PLAYERY, b_ypos(bs))
    # ↑↓ 조준
    step = vrep("조준속도", V_AIMSTEP)
    aup = b_changevar(bs, "각도", V_ANGLE, step)
    ifup = b_if(bs, b_keypressed(bs, "up arrow"), aup)
    step2 = vrep("조준속도", V_AIMSTEP)
    nd = op("operator_subtract", 0, step2)
    adn = b_changevar(bs, "각도", V_ANGLE, nd)
    ifdn = b_if(bs, b_keypressed(bs, "down arrow"), adn)
    ang = vrep("각도", V_ANGLE)
    hi = cmp_op("operator_gt", ang, 80)
    ifhi = b_if(bs, hi, b_setvar(bs, "각도", V_ANGLE, 80))
    ang2 = vrep("각도", V_ANGLE)
    lo = cmp_op("operator_lt", ang2, 5)
    iflo = b_if(bs, lo, b_setvar(bs, "각도", V_ANGLE, 5))
    facd = vrep("바라봄", V_FACING)
    rightf = cmp_op("operator_gt", facd, 0)
    ang_r = vrep("각도", V_ANGLE)
    dir_r = op("operator_subtract", 90, ang_r)
    sr = b_setvar(bs, "발사방향", V_FIREDIR, dir_r)
    ang_l = vrep("각도", V_ANGLE)
    dir_l = op("operator_add", -90, ang_l)
    sl = b_setvar(bs, "발사방향", V_FIREDIR, dir_l)
    ifdir = b_ifelse(bs, rightf, sr, sl)
    gravb = b_changevar(bs, "VY", V_VY, vrep("중력", V_GRAV))
    chyb = b_changeyby(bs, vrep("VY", V_VY))
    col_h3, col_t3 = emit_col_from_x(bs, vrep, op, cmp_op, "칸번호", V_TANKCOL)
    gy3 = emit_ground_y(bs, vrep, op, "칸번호", V_TANKCOL)
    yp_f = b_ypos(bs)
    cfl = cmp_op("operator_lt", yp_f, gy3)
    gy4 = emit_ground_y(bs, vrep, op, "칸번호", V_TANKCOL)
    syf = b_sety(bs, gy4)
    zvy = b_setvar(bs, "VY", V_VY, 0)
    idl = b_costume(bs, "idle")
    chain([(syf, bs[syf]), (zvy, bs[zvy]), (idl, bs[idl])])
    ifflo = b_if(bs, cfl, syf)
    # i-frames
    ift = vrep("무적타이머", V_IFRMT)
    cif = cmp_op("operator_gt", ift, 0)
    decif = b_changevar(bs, "무적타이머", V_IFRMT, -0.025)
    g40 = b_setghost(bs, 40)
    chain([(decif, bs[decif]), (g40, bs[g40])])
    g0b = b_setghost(bs, 0)
    iframeb = b_ifelse(bs, cif, decif, g0b)
    # death
    hp = vrep("체력", V_HP)
    cdead = cmp_op("operator_lt", hp, 1)
    st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    eh, et = emit_boom_anim(bs)
    hi_d = b_hide(bs)
    bro = b_broadcast(bs, "게임오버", BR_OVER)
    chain([(st2, bs[st2]), (eh, bs[eh])])
    bs[et]["next"] = hi_d; bs[hi_d]["parent"] = et
    chain([(hi_d, bs[hi_d]), (bro, bs[bro])])
    deathb = b_if(bs, cdead, st2)

    chain([(b, bs[b]) for b in inner])
    clamp_lo = inner[3]
    bs[clamp_lo]["next"] = col_h; bs[col_h]["parent"] = clamp_lo
    bs[col_t]["next"] = ifblk; bs[ifblk]["parent"] = col_t
    bs[ifblk]["next"] = pxset; bs[pxset]["parent"] = ifblk
    bs[pxset]["next"] = pyset; bs[pyset]["parent"] = pxset
    bs[pyset]["next"] = ifup; bs[ifup]["parent"] = pyset
    chain([(ifup, bs[ifup]), (ifdn, bs[ifdn]), (ifhi, bs[ifhi]), (iflo, bs[iflo]),
           (ifdir, bs[ifdir]), (gravb, bs[gravb]), (chyb, bs[chyb])])
    bs[chyb]["next"] = col_h3; bs[col_h3]["parent"] = chyb
    bs[col_t3]["next"] = ifflo; bs[ifflo]["parent"] = col_t3
    bs[idl]["next"] = iframeb; bs[iframeb]["parent"] = idl
    chain([(iframeb, bs[iframeb]), (deathb, bs[deathb])])
    st = vrep("게임상태", V_STATE)
    play = cmp_op("operator_equals", st, 1)
    ifp = b_if(bs, play, inner[0])
    wc = b_wait(bs, 0.025)
    chain([(ifp, bs[ifp]), (wc, bs[wc])])
    fe = b_forever(bs, ifp)
    winit = b_wait(bs, 0.25)
    chain([(hc, bs[hc]), (winit, bs[winit]), (fe, bs[fe])])

    # 웨이브 전환: 스폰으로 끌어다 놓고 정지 (게임상태=3 동안 루프 안 돎)
    hm = gen(); bs[hm] = mk("event_whenbroadcastreceived", top=True, x=20, y=720,
        fields={"BROADCAST_OPTION": ["맵변경", BR_MAP]})
    fy2 = vrep("바닥Y", V_FLOOR)
    gsp = b_gotoxy(bs, -140, fy2)
    zvy2 = b_setvar(bs, "VY", V_VY, 0)
    setf = b_setvar(bs, "바라봄", V_FACING, 90)
    pt2 = b_point_dir(bs, 90)
    sa = b_setvar(bs, "각도", V_ANGLE, 50)
    sd = b_setvar(bs, "발사방향", V_FIREDIR, 40)
    zpw = b_setvar(bs, "파워", V_POWER, 0)
    zch = b_setvar(bs, "차지중", V_CHARGING, 0)
    cid = b_costume(bs, "idle")
    stg = vrep("스테이지", V_STAGE)
    isboss = cmp_op("operator_equals", stg, 6)
    sboss = b_sayfor(bs, "BOSS!", 1.2)
    wv = vrep("웨이브", V_WAVE)
    msg = b_join(bs, "WAVE ", wv)
    swave = b_sayfor(bs, msg, 1.2)
    ifsay = b_ifelse(bs, isboss, sboss, swave)
    chain([(hm, bs[hm]), (gsp, bs[gsp]), (zvy2, bs[zvy2]), (setf, bs[setf]),
           (pt2, bs[pt2]), (sa, bs[sa]), (sd, bs[sd]), (zpw, bs[zpw]),
           (zch, bs[zch]), (cid, bs[cid]), (ifsay, bs[ifsay])])

    # (C) space 차지 발사 — 짧게=약, 길게=강. 떼면 발사, 최대면 자동발사.
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=20, y=900)

    def emit_do_fire():
        spd = vrep("탄속", V_SHOTSPD)
        pw = vrep("파워", V_POWER)
        prod = op("operator_multiply", spd, pw)
        sc = vrep("파워배율", V_POWSCALE)
        prod2 = op("operator_multiply", prod, sc)
        quot = op("operator_divide", prod2, 100)
        setfs = b_setvar(bs, "발사탄속", V_FIRESPD, quot)
        fs = vrep("발사탄속", V_FIRESPD)
        lo = cmp_op("operator_lt", fs, 4)
        floor = b_setvar(bs, "발사탄속", V_FIRESPD, 4)
        iflo = b_if(bs, lo, floor)
        sn = vrep("탄수", V_SHOTN)
        mx = vrep("최대탄수", V_MAXSHOT)
        room = cmp_op("operator_lt", sn, mx)
        bf = b_broadcast(bs, "발사", BR_FIRE)
        ch, _ct = b_sound(bs, 0, "click")
        ifelse = b_ifelse(bs, room, bf, ch)
        chain([(setfs, bs[setfs]), (iflo, bs[iflo]), (ifelse, bs[ifelse])])
        return setfs, ifelse

    onch = b_setvar(bs, "차지중", V_CHARGING, 1)
    mn0 = vrep("최소파워", V_MINPOW)
    setmn = b_setvar(bs, "파워", V_POWER, mn0)
    ps0 = vrep("파워속도", V_POWSPD)
    inc0 = b_changevar(bs, "파워", V_POWER, ps0)
    chain([(onch, bs[onch]), (setmn, bs[setmn]), (inc0, bs[inc0])])

    pspd = vrep("파워속도", V_POWSPD)
    incp = b_changevar(bs, "파워", V_POWER, pspd)
    pw1 = vrep("파워", V_POWER)
    mxp = vrep("최대파워", V_MAXPOW)
    less = cmp_op("operator_lt", pw1, mxp)
    full = gen(); bs[full] = mk("operator_not", inputs={"OPERAND": [2, less]})
    bs[less]["parent"] = full
    mxp2 = vrep("최대파워", V_MAXPOW)
    cap = b_setvar(bs, "파워", V_POWER, mxp2)
    fh1, ft1 = emit_do_fire()
    held = b_setvar(bs, "차지중", V_CHARGING, 2)
    zp1 = b_setvar(bs, "파워", V_POWER, 0)
    chain([(cap, bs[cap]), (fh1, bs[fh1])])
    bs[ft1]["next"] = held; bs[held]["parent"] = ft1
    chain([(held, bs[held]), (zp1, bs[zp1])])
    iffull = b_if(bs, full, cap)
    chain([(incp, bs[incp]), (iffull, bs[iffull])])

    chg = vrep("차지중", V_CHARGING)
    is1 = cmp_op("operator_equals", chg, 1)
    nop = b_wait(bs, 0.01)
    ifpump = b_ifelse(bs, is1, incp, nop)
    chg0 = vrep("차지중", V_CHARGING)
    idle = cmp_op("operator_equals", chg0, 0)
    ifhold = b_ifelse(bs, idle, onch, ifpump)

    fh2, ft2 = emit_do_fire()
    zch2 = b_setvar(bs, "차지중", V_CHARGING, 0)
    zp2 = b_setvar(bs, "파워", V_POWER, 0)
    bs[ft2]["next"] = zch2; bs[zch2]["parent"] = ft2
    chain([(zch2, bs[zch2]), (zp2, bs[zp2])])
    zch3 = b_setvar(bs, "차지중", V_CHARGING, 0)
    zp3 = b_setvar(bs, "파워", V_POWER, 0)
    chain([(zch3, bs[zch3]), (zp3, bs[zp3])])
    chg2 = vrep("차지중", V_CHARGING)
    was1 = cmp_op("operator_equals", chg2, 1)
    ifrel = b_ifelse(bs, was1, fh2, zch3)
    kd = b_keypressed(bs, "space")
    ifsp = b_ifelse(bs, kd, ifhold, ifrel)
    stz = vrep("게임상태", V_STATE)
    pz = cmp_op("operator_equals", stz, 1)
    zch4 = b_setvar(bs, "차지중", V_CHARGING, 0)
    zp4 = b_setvar(bs, "파워", V_POWER, 0)
    chain([(zch4, bs[zch4]), (zp4, bs[zp4])])
    ifplay = b_ifelse(bs, pz, ifsp, zch4)
    wc2 = b_wait(bs, 0.02)
    chain([(ifplay, bs[ifplay]), (wc2, bs[wc2])])
    frz = b_forever(bs, ifplay)
    chain([(hd, bs[hd]), (frz, bs[frz])])
    add_comment(bs, comments, onch,
        "space 누르는 동안 파워가 차고, 떼면 그 파워로 곡사. 최대까지 누르면 자동발사.",
        x=540, y=900, w=280, h=90)

    # (D) X nade
    hx = gen(); bs[hx] = mk("event_whenflagclicked", top=True, x=20, y=1180)
    stx = vrep("게임상태", V_STATE)
    px = cmp_op("operator_equals", stx, 1)
    kx = b_keypressed(bs, "x")
    nd = vrep("수류탄쿨남은", V_NADET)
    ready = cmp_op("operator_lt", nd, 0.01)
    nn = vrep("수류탄수", V_NADEN)
    roomn = cmp_op("operator_lt", nn, 2)
    b1 = bool_op("operator_and", kx, ready)
    b2 = bool_op("operator_and", b1, roomn)
    bn = b_broadcast(bs, "수류탄", BR_NADE)
    cdv = vrep("수류탄쿨", V_NADECD)
    setcd = b_setvar(bs, "수류탄쿨남은", V_NADET, cdv)
    chain([(bn, bs[bn]), (setcd, bs[setcd])])
    ifn = b_if(bs, b2, bn)
    nd2 = vrep("수류탄쿨남은", V_NADET)
    cpos = cmp_op("operator_gt", nd2, 0)
    decn = b_changevar(bs, "수류탄쿨남은", V_NADET, -0.03)
    ifcd = b_if(bs, cpos, decn)
    wx = b_wait(bs, 0.03)
    chain([(ifn, bs[ifn]), (ifcd, bs[ifcd]), (wx, bs[wx])])
    ifpx = b_if(bs, px, ifn)
    frx = b_forever(bs, ifpx)
    chain([(hx, bs[hx]), (frx, bs[frx])])

    hh = gen(); bs[hh] = mk("event_whenbroadcastreceived", top=True, x=20, y=1480,
        fields={"BROADCAST_OPTION": ["피격", BR_HURT]})
    hrh, hrt = b_sound(bs, 0, "hurt")
    chain([(hh, bs[hh]), (hrh, bs[hrh])])
    return bs, comments

# ============================================================
#  총알
# ============================================================
def build_shot_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    z = b_setvar(bs, "복제됨", V_SHOTISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (z, bs[z])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    isc = vrep("복제됨", V_SHOTISC)
    orig = cmp_op("operator_equals", isc, 0)
    sn = vrep("탄수", V_SHOTN)
    mx = vrep("최대탄수", V_MAXSHOT)
    room = cmp_op("operator_lt", sn, mx)
    cln = b_clone_self(bs)
    ifr = b_if(bs, room, cln)
    ifo = b_if(bs, orig, ifr)
    chain([(hb, bs[hb]), (ifo, bs[ifo])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    s1 = b_setvar(bs, "복제됨", V_SHOTISC, 1)
    inc = b_changevar(bs, "탄수", V_SHOTN, 1)
    life0 = vrep("포탄수명", V_BALLLIFE)
    slife = b_setvar(bs, "남은수명", V_SHOTLIFE, life0)
    gt = b_goto_sprite(bs, "지아이조")
    my = vrep("총알높이", V_MUZZLEY)
    lift = b_changeyby(bs, my)
    fac = vrep("발사방향", V_FIREDIR)
    pt = b_point_dir(bs, fac)
    fwd = vrep("총구앞", V_MUZZLEF)
    mfront = b_movesteps(bs, fwd)
    sw = b_costume(bs, "bullet")
    sz = b_setsize(bs, 130)
    frt = b_front(bs)
    shw = b_show(bs)
    fh, ft = b_sound(bs, 0, "fire")
    svx, svy = emit_ballistic_init(bs, vrep, op, "발사방향", V_FIREDIR, "발사탄속", V_FIRESPD,
                                  "속도X", V_SHOTVX, "속도Y", V_SHOTVY)
    tick_h, tick_t = emit_ballistic_tick(bs, vrep, op, cmp_op, "속도X", V_SHOTVX, "속도Y", V_SHOTVY)
    col_h, col_t = emit_col_from_x(bs, vrep, op, cmp_op, "칸번호", V_SHOTCOL)
    gy = emit_ground_y(bs, vrep, op, "칸번호", V_SHOTCOL)
    top = op("operator_add", gy, 4)
    yp = b_ypos(bs)
    low = cmp_op("operator_lt", yp, top)
    bx = b_xpos(bs)
    px = vrep("플레이어X", V_PLAYERX)
    dx = op("operator_subtract", bx, px)
    adx = b_abs(bs, dx)
    far = cmp_op("operator_gt", adx, 20)
    wall = bool_op("operator_and", low, far)
    tc = b_touching(bs, "적")
    decl = b_changevar(bs, "남은수명", V_SHOTLIFE, -1)
    lf = vrep("남은수명", V_SHOTLIFE)
    exp = cmp_op("operator_lt", lf, 1)
    w = b_wait(bs, 0.02)
    chain([(tick_t, bs[tick_t]), (col_h, bs[col_h])])
    bs[col_t]["next"] = decl; bs[decl]["parent"] = col_t
    bs[decl]["next"] = w; bs[w]["parent"] = decl
    xp = b_xpos(bs)
    ax = b_abs(bs, xp)
    off = cmp_op("operator_gt", ax, 240)
    yp2 = b_ypos(bs)
    yhi = cmp_op("operator_gt", yp2, 180)
    yp3 = b_ypos(bs)
    ylo = cmp_op("operator_lt", yp3, -175)
    st = vrep("게임상태", V_STATE)
    playing = cmp_op("operator_equals", st, 1)
    over = gen(); bs[over] = mk("operator_not", inputs={"OPERAND": [2, playing]})
    bs[playing]["parent"] = over
    o1 = bool_op("operator_or", off, yhi)
    o2 = bool_op("operator_or", ylo, over)
    o3 = bool_op("operator_or", o1, o2)
    o4 = bool_op("operator_or", o3, wall)
    o5 = bool_op("operator_or", o4, tc)
    stop = bool_op("operator_or", o5, exp)
    ru = b_repeat_until(bs, stop, tick_h)
    hx = b_xpos(bs)
    seth = b_setvar(bs, "탄히트X", V_SHOTHITX, hx)
    bhit = b_broadcast(bs, "탄맞음", BR_HITSHOT)
    eh, et = emit_boom_anim(bs)
    dec = b_changevar(bs, "탄수", V_SHOTN, -1)
    dl = b_del_clone(bs)
    chain([(ch, bs[ch]), (s1, bs[s1]), (inc, bs[inc]), (slife, bs[slife]), (gt, bs[gt]), (lift, bs[lift]),
           (pt, bs[pt]), (mfront, bs[mfront]),
           (sw, bs[sw]), (sz, bs[sz]), (frt, bs[frt]), (shw, bs[shw]),
           (fh, bs[fh]), (ft, bs[ft]), (svx, bs[svx])])
    bs[svy]["next"] = ru; bs[ru]["parent"] = svy
    chain([(ru, bs[ru]), (seth, bs[seth]), (bhit, bs[bhit]), (eh, bs[eh])])
    bs[et]["next"] = dec; bs[dec]["parent"] = et
    chain([(dec, bs[dec]), (dl, bs[dl])])
    add_comment(bs, comments, svx,
        "곡사포: 속도X/Y = 탄속·방향, 매 틱 속도Y += 탄중력. ↑로 상자 너머에 떨어뜨린다.",
        x=540, y=360, w=300, h=110)
    return bs, comments

# ============================================================
#  수류탄
# ============================================================
def build_nade_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    z = b_setvar(bs, "복제됨", V_NADEISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (z, bs[z])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["수류탄", BR_NADE]})
    isc = vrep("복제됨", V_NADEISC)
    orig = cmp_op("operator_equals", isc, 0)
    cln = b_clone_self(bs)
    ifo = b_if(bs, orig, cln)
    chain([(hb, bs[hb]), (ifo, bs[ifo])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    s1 = b_setvar(bs, "복제됨", V_NADEISC, 1)
    inc = b_changevar(bs, "수류탄수", V_NADEN, 1)
    gt = b_goto_sprite(bs, "지아이조")
    my = vrep("총알높이", V_MUZZLEY)
    lift = b_changeyby(bs, my)
    fac0 = vrep("발사방향", V_FIREDIR)
    pt0 = b_point_dir(bs, fac0)
    fwd = vrep("총구앞", V_MUZZLEF)
    mfront = b_movesteps(bs, fwd)
    sw = b_costume(bs, "nade")
    sz = b_setsize(bs, 100)
    shw = b_show(bs)
    nh, nt = b_sound(bs, 0, "nade")
    fac = vrep("바라봄", V_FACING)
    right = cmp_op("operator_gt", fac, 0)
    spd = vrep("수류탄력", V_NADESPD)
    svx = b_setvar(bs, "속도X", V_NADEVX, spd)
    spd2 = vrep("수류탄력", V_NADESPD)
    nspd = op("operator_subtract", 0, spd2)
    svx2 = b_setvar(bs, "속도X", V_NADEVX, nspd)
    ifvx = b_ifelse(bs, right, svx, svx2)
    up = vrep("수류탄띄움", V_NADEUP)
    svy = b_setvar(bs, "속도Y", V_NADEVY, up)

    gr = vrep("중력", V_GRAV)
    cvy = b_changevar(bs, "속도Y", V_NADEVY, gr)
    vx = vrep("속도X", V_NADEVX)
    cx = b_changexby(bs, vx)
    vy = vrep("속도Y", V_NADEVY)
    cy = b_changeyby(bs, vy)
    w = b_wait(bs, 0.02)
    chain([(cvy, bs[cvy]), (cx, bs[cx]), (cy, bs[cy])])
    ncol_h, ncol_t = emit_col_from_x(bs, vrep, op, cmp_op, "칸번호", V_NCOL)
    bs[cy]["next"] = ncol_h; bs[ncol_h]["parent"] = cy
    bs[ncol_t]["next"] = w; bs[w]["parent"] = ncol_t
    yp = b_ypos(bs)
    fl = vrep("바닥Y", V_FLOOR)
    hitg = cmp_op("operator_lt", yp, fl)
    tc = b_touching(bs, "적")
    st = vrep("게임상태", V_STATE)
    playing = cmp_op("operator_equals", st, 1)
    over = gen(); bs[over] = mk("operator_not", inputs={"OPERAND": [2, playing]})
    bs[playing]["parent"] = over
    gy = emit_ground_y(bs, vrep, op, "칸번호", V_NCOL)
    top = op("operator_add", gy, 4)
    yp2 = b_ypos(bs)
    low = cmp_op("operator_lt", yp2, top)
    coln = vrep("칸번호", V_NCOL)
    hh = b_item_of(bs, "지형높이", L_HEIGHT, coln)
    thick = cmp_op("operator_gt", hh, 1)
    wall = bool_op("operator_and", low, thick)
    o1 = bool_op("operator_or", hitg, tc)
    o2 = bool_op("operator_or", o1, over)
    stop = bool_op("operator_or", o2, wall)
    ru = b_repeat_until(bs, stop, cvy)
    hx = b_xpos(bs)
    seth = b_setvar(bs, "수류탄히트X", V_NADEHITX, hx)
    bhit = b_broadcast(bs, "수류탄폭발", BR_HITNADE)
    eh, et = emit_boom_anim(bs)
    dec = b_changevar(bs, "수류탄수", V_NADEN, -1)
    dl = b_del_clone(bs)
    chain([(ch, bs[ch]), (s1, bs[s1]), (inc, bs[inc]), (gt, bs[gt]),
           (lift, bs[lift]), (pt0, bs[pt0]), (mfront, bs[mfront]),
           (sw, bs[sw]), (sz, bs[sz]), (shw, bs[shw]), (nh, bs[nh]), (nt, bs[nt]),
           (ifvx, bs[ifvx]), (svy, bs[svy]), (ru, bs[ru]),
           (seth, bs[seth]), (bhit, bs[bhit]), (eh, bs[eh])])
    bs[et]["next"] = dec; bs[dec]["parent"] = et
    chain([(dec, bs[dec]), (dl, bs[dl])])
    add_comment(bs, comments, svy,
        "수류탄: 속도X는 바라보는 쪽, 속도Y는 띄움. 3칸 엄폐 너머로 포물선을 그린다.",
        x=540, y=360, w=300, h=110)
    return bs, comments

# ============================================================
#  적
# ============================================================
def build_enemy_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    z = b_setvar(bs, "복제됨", V_ENISC, 0)
    rs = b_rotstyle(bs, "left-right")
    chain([(h, bs[h]), (hi, bs[hi]), (z, bs[z]), (rs, bs[rs])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]})
    isc = vrep("복제됨", V_ENISC)
    orig = cmp_op("operator_equals", isc, 0)
    cln = b_clone_self(bs)
    ifo = b_if(bs, orig, cln)
    chain([(hb, bs[hb]), (ifo, bs[ifo])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    s1 = b_setvar(bs, "복제됨", V_ENISC, 1)
    inc = b_changevar(bs, "적수", V_ENN, 1)
    rnd = b_random(bs, 1, 100)
    skind = b_setvar(bs, "종류", V_ENKIND, rnd)
    # if 종류 <= 사수확률 → 2 else 1
    k0 = vrep("종류", V_ENKIND)
    sp = vrep("사수확률", V_SHOOTP)
    is_sh = cmp_op("operator_lt", k0, sp)
    set2 = b_setvar(bs, "종류", V_ENKIND, 2)
    set1 = b_setvar(bs, "종류", V_ENKIND, 1)
    ifk = b_ifelse(bs, is_sh, set2, set1)
    k1 = vrep("종류", V_ENKIND)
    is2c = cmp_op("operator_equals", k1, 2)
    csh = b_costume(bs, "shooter")
    cwa = b_costume(bs, "walker")
    ifc = b_ifelse(bs, is2c, csh, cwa)
    rnd2 = b_random(bs, 1, 100)
    bp = vrep("뒤쪽확률", V_BACKP)
    back = cmp_op("operator_lt", rnd2, bp)
    setf_r = b_setvar(bs, "바라봄", V_ENFACE, 90)
    sx_l = b_setx(bs, -220)
    pt_r = b_point_dir(bs, 90)
    chain([(setf_r, bs[setf_r]), (sx_l, bs[sx_l]), (pt_r, bs[pt_r])])
    setf_l = b_setvar(bs, "바라봄", V_ENFACE, -90)
    sx_r = b_setx(bs, 225)
    pt_l = b_point_dir(bs, -90)
    chain([(setf_l, bs[setf_l]), (sx_r, bs[sx_r]), (pt_l, bs[pt_l])])
    ifside = b_ifelse(bs, back, setf_r, setf_l)
    fy = vrep("바닥Y", V_FLOOR)
    sy = b_sety(bs, fy)
    zvy = b_setvar(bs, "내VY", V_ENVY, 0)
    zcd = b_setvar(bs, "사격쿨", V_ENFIRET, 0.3)
    sz = b_setsize(bs, 95)
    shw = b_show(bs)

    st = vrep("게임상태", V_STATE)
    playe = cmp_op("operator_equals", st, 1)
    over = gen(); bs[over] = mk("operator_not", inputs={"OPERAND": [2, playe]})
    bs[playe]["parent"] = over
    hi3 = b_hide(bs)
    dl0 = b_del_clone(bs)
    chain([(hi3, bs[hi3]), (dl0, bs[dl0])])
    ifover = b_if(bs, over, hi3)

    # 사정거리 안이면 멈춰 엄폐 사격
    xp = b_xpos(bs)
    px = vrep("플레이어X", V_PLAYERX)
    dd = op("operator_subtract", xp, px)
    ad = b_abs(bs, dd)
    rngv = vrep("사정거리", V_RANGE)
    close = cmp_op("operator_lt", ad, rngv)
    hold = close  # 사정거리 안이면 엄폐 사격 (무작정 돌격하지 않음)
    # walk unless hold
    face = vrep("바라봄", V_ENFACE)
    right = cmp_op("operator_gt", face, 0)
    spd = vrep("적속도", V_ENSPD)
    wr = b_changexby(bs, spd)
    spd2 = vrep("적속도", V_ENSPD)
    nl = op("operator_subtract", 0, spd2)
    wl = b_changexby(bs, nl)
    ifdir = b_ifelse(bs, right, wr, wl)
    nhold = gen(); bs[nhold] = mk("operator_not", inputs={"OPERAND": [2, hold]})
    bs[hold]["parent"] = nhold
    ifwalk = b_if(bs, nhold, ifdir)
    zblk = b_setvar(bs, "막힘", V_ENBLOCK, 0)
    col_h, col_t = emit_col_from_x(bs, vrep, op, cmp_op, "칸번호", V_ENCOL)
    gyh = emit_ground_y(bs, vrep, op, "칸번호", V_ENCOL)
    yp_b = b_ypos(bs)
    too_hi = cmp_op("operator_gt", gyh, yp_b)
    yp_w2 = b_ypos(bs)
    gyb = emit_ground_y(bs, vrep, op, "칸번호", V_ENCOL)
    slk = vrep("칸크기", V_CELLW)
    need = op("operator_subtract", gyb, slk)
    not_over = cmp_op("operator_lt", yp_w2, need)
    blocked = bool_op("operator_and", too_hi, not_over)
    setblk = b_setvar(bs, "막힘", V_ENBLOCK, 1)
    facb = vrep("바라봄", V_ENFACE)
    going_r = cmp_op("operator_gt", facb, 0)
    mv_u = vrep("적속도", V_ENSPD)
    undo_r = op("operator_subtract", 0, mv_u)
    push_r = b_changexby(bs, undo_r)
    mv_u2 = vrep("적속도", V_ENSPD)
    push_l = b_changexby(bs, mv_u2)
    ifpush = b_ifelse(bs, going_r, push_r, push_l)
    chain([(setblk, bs[setblk]), (ifpush, bs[ifpush])])
    ifblk = b_if(bs, blocked, setblk)
    gr = vrep("중력", V_GRAV)
    chvy = b_changevar(bs, "내VY", V_ENVY, gr)
    chy = b_changeyby(bs, vrep("내VY", V_ENVY))
    col_h2, col_t2 = emit_col_from_x(bs, vrep, op, cmp_op, "칸번호", V_ENCOL)
    gy3 = emit_ground_y(bs, vrep, op, "칸번호", V_ENCOL)
    yp_f = b_ypos(bs)
    cfl = cmp_op("operator_lt", yp_f, gy3)
    gy4 = emit_ground_y(bs, vrep, op, "칸번호", V_ENCOL)
    syf = b_sety(bs, gy4)
    zvy2 = b_setvar(bs, "내VY", V_ENVY, 0)
    chain([(syf, bs[syf]), (zvy2, bs[zvy2])])
    ifflo = b_if(bs, cfl, syf)

    # shoot (사정거리 또는 벽에 막히면 곡사)
    xp3 = b_xpos(bs)
    px3 = vrep("플레이어X", V_PLAYERX)
    dd3 = op("operator_subtract", xp3, px3)
    ad3 = b_abs(bs, dd3)
    rng2 = vrep("사정거리", V_RANGE)
    close2 = cmp_op("operator_lt", ad3, rng2)
    cd = vrep("사격쿨", V_ENFIRET)
    ready = cmp_op("operator_lt", cd, 0.01)
    en = vrep("적탄수", V_ESHOTN)
    mxb = vrep("최대적탄", V_MAXESHOT)
    room = cmp_op("operator_lt", en, mxb)
    blk = vrep("막힘", V_ENBLOCK)
    atwall = cmp_op("operator_equals", blk, 1)
    incover = bool_op("operator_or", close2, atwall)
    can = bool_op("operator_and", incover, ready)
    can2 = bool_op("operator_and", can, room)
    hx = b_xpos(bs)
    sxb = b_setvar(bs, "적탄X", V_ESHOTX, hx)
    hy = b_ypos(bs)
    lift = vrep("총알높이", V_MUZZLEY)
    ey = op("operator_add", hy, lift)
    syb = b_setvar(bs, "적탄Y", V_ESHOTY, ey)
    pxf = vrep("플레이어X", V_PLAYERX)
    xnow = b_xpos(bs)
    pright = cmp_op("operator_gt", pxf, xnow)
    setfr = b_setvar(bs, "바라봄", V_ENFACE, 90)
    ptr = b_point_dir(bs, 90)
    chain([(setfr, bs[setfr]), (ptr, bs[ptr])])
    setfl = b_setvar(bs, "바라봄", V_ENFACE, -90)
    ptl = b_point_dir(bs, -90)
    chain([(setfl, bs[setfl]), (ptl, bs[ptl])])
    turnface = b_ifelse(bs, pright, setfr, setfl)
    py = vrep("플레이어Y", V_PLAYERY)
    ynow = b_ypos(bs)
    dy = op("operator_subtract", py, ynow)
    px2 = vrep("플레이어X", V_PLAYERX)
    x2 = b_xpos(bs)
    dx = op("operator_subtract", px2, x2)
    adx = b_abs(bs, dx)
    adx2 = op("operator_add", adx, 0.1)
    ratio = op("operator_divide", dy, adx2)
    elev = b_mathop(bs, "atan", ratio)
    setelv = b_setvar(bs, "임시", V_TMP, elev)
    clift = b_changevar(bs, "임시", V_TMP, 22)
    tmax = vrep("임시", V_TMP)
    too_hi = cmp_op("operator_gt", tmax, 62)
    ifhi = b_if(bs, too_hi, b_setvar(bs, "임시", V_TMP, 62))
    chain([(setelv, bs[setelv]), (clift, bs[clift]), (ifhi, bs[ifhi])])
    fac2 = vrep("바라봄", V_ENFACE)
    eright = cmp_op("operator_gt", fac2, 0)
    tmp_r = vrep("임시", V_TMP)
    dirr = op("operator_subtract", 90, tmp_r)
    sdirr = b_setvar(bs, "적탄방향", V_ESHOTDIR, dirr)
    tmp_l = vrep("임시", V_TMP)
    dirl = op("operator_add", -90, tmp_l)
    sdirl = b_setvar(bs, "적탄방향", V_ESHOTDIR, dirl)
    ifaim = b_ifelse(bs, eright, sdirr, sdirl)
    brs = b_broadcast(bs, "적발사", BR_ESHOT)
    gap = vrep("적연사간격", V_EFIREGAP)
    scd = b_setvar(bs, "사격쿨", V_ENFIRET, gap)
    chain([(sxb, bs[sxb]), (syb, bs[syb]), (turnface, bs[turnface]), (setelv, bs[setelv])])
    bs[ifhi]["next"] = ifaim; bs[ifaim]["parent"] = ifhi
    chain([(ifaim, bs[ifaim]), (brs, bs[brs]), (scd, bs[scd])])
    ifshot = b_if(bs, can2, sxb)
    cd2 = vrep("사격쿨", V_ENFIRET)
    cpos = cmp_op("operator_gt", cd2, 0)
    decd = b_changevar(bs, "사격쿨", V_ENFIRET, -0.03)
    ifcd = b_if(bs, cpos, decd)

    tt = b_touching(bs, "지아이조")
    ift = vrep("무적타이머", V_IFRMT)
    noifr = cmp_op("operator_lt", ift, 0.01)
    bump = bool_op("operator_and", tt, noifr)
    atk = vrep("적공격", V_ENATK)
    natk = op("operator_subtract", 0, atk)
    dhp = b_changevar(bs, "체력", V_HP, natk)
    ifr = vrep("무적시간", V_IFRAME)
    sif = b_setvar(bs, "무적타이머", V_IFRMT, ifr)
    de2 = b_changevar(bs, "적수", V_ENN, -1)
    dlr = b_del_clone(bs)
    hurtb = b_broadcast(bs, "피격", BR_HURT)
    chain([(dhp, bs[dhp]), (sif, bs[sif]), (hurtb, bs[hurtb]), (de2, bs[de2]), (dlr, bs[dlr])])
    ifbump = b_if(bs, bump, dhp)

    xp = b_xpos(bs)
    left_e = cmp_op("operator_lt", xp, -230)
    xp2 = b_xpos(bs)
    right_e = cmp_op("operator_gt", xp2, 230)
    passed = bool_op("operator_or", left_e, right_e)
    ift2 = vrep("무적타이머", V_IFRMT)
    noifr2 = cmp_op("operator_lt", ift2, 0.01)
    atk2 = vrep("적공격", V_ENATK)
    natk2 = op("operator_subtract", 0, atk2)
    dhp2 = b_changevar(bs, "체력", V_HP, natk2)
    ifr2 = vrep("무적시간", V_IFRAME)
    sif2 = b_setvar(bs, "무적타이머", V_IFRMT, ifr2)
    hurtb2 = b_broadcast(bs, "피격", BR_HURT)
    chain([(dhp2, bs[dhp2]), (sif2, bs[sif2]), (hurtb2, bs[hurtb2])])
    ifdmg = b_if(bs, noifr2, dhp2)
    de3 = b_changevar(bs, "적수", V_ENN, -1)
    dlp = b_del_clone(bs)
    chain([(ifdmg, bs[ifdmg]), (de3, bs[de3]), (dlp, bs[dlp])])
    ifpass = b_if(bs, passed, ifdmg)

    w = b_wait(bs, 0.03)
    chain([(ifover, bs[ifover]), (ifwalk, bs[ifwalk]), (zblk, bs[zblk]), (col_h, bs[col_h])])
    bs[col_t]["next"] = ifblk; bs[ifblk]["parent"] = col_t
    chain([(ifblk, bs[ifblk]), (chvy, bs[chvy]), (chy, bs[chy]), (col_h2, bs[col_h2])])
    bs[col_t2]["next"] = ifflo; bs[ifflo]["parent"] = col_t2
    chain([(ifflo, bs[ifflo]), (ifshot, bs[ifshot]), (ifcd, bs[ifcd]),
           (ifbump, bs[ifbump]), (ifpass, bs[ifpass]), (w, bs[w])])
    fr = b_forever(bs, ifover)
    chain([(ch, bs[ch]), (s1, bs[s1]), (inc, bs[inc]), (skind, bs[skind]),
           (ifk, bs[ifk]), (ifc, bs[ifc]), (ifside, bs[ifside]),
           (sy, bs[sy]), (zvy, bs[zvy]), (zcd, bs[zcd]), (sz, bs[sz]),
           (shw, bs[shw]), (fr, bs[fr])])

    def emit_death():
        stop = gen(); bs[stop] = mk("control_stop",
            fields={"STOP_OPTION": ["other scripts in sprite", None]})
        sc = b_changevar(bs, "점수", V_SCORE, 100)
        kil = b_changevar(bs, "처치수", V_KILLS, 1)
        de = b_changevar(bs, "적수", V_ENN, -1)
        kr = vrep("처치수", V_KILLS)
        need = vrep("웨이브킬", V_WAVEKILLS)
        md = op("operator_mod", kr, need)
        mw = cmp_op("operator_equals", md, 0)
        bf = vrep("보스전", V_BOSSFIGHT)
        nbf = cmp_op("operator_equals", bf, 0)
        canw = bool_op("operator_and", mw, nbf)
        cwv = b_changevar(bs, "웨이브", V_WAVE, 1)
        gap = vrep("스폰간격", V_SPAWN)
        ramp = vrep("난이도증가율", V_RAMP)
        om = op("operator_subtract", 1, ramp)
        ng = op("operator_multiply", gap, om)
        sg = b_setvar(bs, "스폰간격", V_SPAWN, ng)
        gap2 = vrep("스폰간격", V_SPAWN)
        small = cmp_op("operator_lt", gap2, 0.4)
        clg = b_setvar(bs, "스폰간격", V_SPAWN, 0.4)
        ifc = b_if(bs, small, clg)
        bmap = b_broadcast(bs, "맵변경", BR_MAP)
        s3 = b_setvar(bs, "게임상태", V_STATE, 3)
        chain([(cwv, bs[cwv]), (sg, bs[sg]), (ifc, bs[ifc]), (s3, bs[s3]), (bmap, bs[bmap])])
        ifw = b_if(bs, canw, cwv)
        eh, et = emit_boom_anim(bs)
        hi4 = b_hide(bs)
        dld = b_del_clone(bs)
        chain([(stop, bs[stop]), (sc, bs[sc]), (kil, bs[kil]), (de, bs[de]), (ifw, bs[ifw]), (eh, bs[eh])])
        bs[et]["next"] = hi4; bs[hi4]["parent"] = et
        chain([(hi4, bs[hi4]), (dld, bs[dld])])
        return stop

    def emit_radius_hat(bname, brid, hit_name, hit_id, rad_name, rad_id, y):
        hat = gen(); bs[hat] = mk("event_whenbroadcastreceived", top=True, x=20, y=y,
            fields={"BROADCAST_OPTION": [bname, brid]})
        isc = vrep("복제됨", V_ENISC)
        orig = cmp_op("operator_equals", isc, 1)
        xp = b_xpos(bs)
        hx = vrep(hit_name, hit_id)
        diff = op("operator_subtract", xp, hx)
        ad = b_abs(bs, diff)
        rad = vrep(rad_name, rad_id)
        near = cmp_op("operator_lt", ad, rad)
        both = bool_op("operator_and", orig, near)
        death = emit_death()
        iff = b_if(bs, both, death)
        chain([(hat, bs[hat]), (iff, bs[iff])])

    emit_radius_hat("탄맞음", BR_HITSHOT, "탄히트X", V_SHOTHITX, "탄히트범위", V_SHOTRAD, 720)
    emit_radius_hat("수류탄폭발", BR_HITNADE, "수류탄히트X", V_NADEHITX, "수류탄범위", V_NADERAD, 980)
    return bs, comments

# ============================================================
#  적탄
# ============================================================
def build_eshot_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    z = b_setvar(bs, "복제됨", V_ESHOTISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (z, bs[z])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["적발사", BR_ESHOT]})
    isc = vrep("복제됨", V_ESHOTISC)
    orig = cmp_op("operator_equals", isc, 0)
    n = vrep("적탄수", V_ESHOTN)
    mx = vrep("최대적탄", V_MAXESHOT)
    room = cmp_op("operator_lt", n, mx)
    cln = b_clone_self(bs)
    ifr = b_if(bs, room, cln)
    ifo = b_if(bs, orig, ifr)
    chain([(hb, bs[hb]), (ifo, bs[ifo])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    s1 = b_setvar(bs, "복제됨", V_ESHOTISC, 1)
    inc = b_changevar(bs, "적탄수", V_ESHOTN, 1)
    life0 = vrep("포탄수명", V_BALLLIFE)
    slife = b_setvar(bs, "남은수명", V_ESLIFE, life0)
    gx = vrep("적탄X", V_ESHOTX)
    gy = vrep("적탄Y", V_ESHOTY)
    go = b_gotoxy(bs, gx, gy)
    d = vrep("적탄방향", V_ESHOTDIR)
    pt = b_point_dir(bs, d)
    sz = b_setsize(bs, 130)
    frt = b_front(bs)
    shw = b_show(bs)
    fh, ft = b_sound(bs, 0, "fire")
    svx, svy = emit_ballistic_init(bs, vrep, op, "적탄방향", V_ESHOTDIR, "적탄속", V_ESHOTSPD,
                                  "속도X", V_ESHOTVX, "속도Y", V_ESHOTVY)
    tick_h, tick_t = emit_ballistic_tick(bs, vrep, op, cmp_op, "속도X", V_ESHOTVX, "속도Y", V_ESHOTVY)
    tc = b_touching(bs, "지아이조")
    ift = vrep("무적타이머", V_IFRMT)
    noifr = cmp_op("operator_lt", ift, 0.01)
    hitp = bool_op("operator_and", tc, noifr)
    atk = vrep("적공격", V_ENATK)
    natk = op("operator_subtract", 0, atk)
    dhp = b_changevar(bs, "체력", V_HP, natk)
    ifr = vrep("무적시간", V_IFRAME)
    sif = b_setvar(bs, "무적타이머", V_IFRMT, ifr)
    zlife = b_setvar(bs, "남은수명", V_ESLIFE, 0)
    hurtb3 = b_broadcast(bs, "피격", BR_HURT)
    chain([(dhp, bs[dhp]), (sif, bs[sif]), (hurtb3, bs[hurtb3]), (zlife, bs[zlife])])
    ifhit = b_if(bs, hitp, dhp)
    col_h, col_t = emit_col_from_x(bs, vrep, op, cmp_op, "칸번호", V_ESCOL)
    gy = emit_ground_y(bs, vrep, op, "칸번호", V_ESCOL)
    top = op("operator_add", gy, 4)
    yp = b_ypos(bs)
    low = cmp_op("operator_lt", yp, top)
    bx = b_xpos(bs)
    sx = vrep("적탄X", V_ESHOTX)
    dx = op("operator_subtract", bx, sx)
    adx = b_abs(bs, dx)
    far = cmp_op("operator_gt", adx, 20)
    wall = bool_op("operator_and", low, far)
    zlife3 = b_setvar(bs, "남은수명", V_ESLIFE, 0)
    ifwall = b_if(bs, wall, zlife3)
    decl = b_changevar(bs, "남은수명", V_ESLIFE, -1)
    lf = vrep("남은수명", V_ESLIFE)
    exp = cmp_op("operator_lt", lf, 1)
    w = b_wait(bs, 0.02)
    chain([(tick_t, bs[tick_t]), (ifhit, bs[ifhit]), (col_h, bs[col_h])])
    bs[col_t]["next"] = ifwall; bs[ifwall]["parent"] = col_t
    bs[ifwall]["next"] = decl; bs[decl]["parent"] = ifwall
    bs[decl]["next"] = w; bs[w]["parent"] = decl
    xp = b_xpos(bs)
    ax = b_abs(bs, xp)
    off = cmp_op("operator_gt", ax, 240)
    yp2 = b_ypos(bs)
    yhi = cmp_op("operator_gt", yp2, 180)
    yp3 = b_ypos(bs)
    ylo = cmp_op("operator_lt", yp3, -175)
    st = vrep("게임상태", V_STATE)
    playing = cmp_op("operator_equals", st, 1)
    over = gen(); bs[over] = mk("operator_not", inputs={"OPERAND": [2, playing]})
    bs[playing]["parent"] = over
    o1 = bool_op("operator_or", off, yhi)
    o2 = bool_op("operator_or", ylo, over)
    o3 = bool_op("operator_or", o1, o2)
    stop = bool_op("operator_or", o3, exp)
    ru = b_repeat_until(bs, stop, tick_h)
    eh, et = emit_boom_anim(bs)
    dec2 = b_changevar(bs, "적탄수", V_ESHOTN, -1)
    dl = b_del_clone(bs)
    chain([(ch, bs[ch]), (s1, bs[s1]), (inc, bs[inc]), (slife, bs[slife]), (go, bs[go]), (pt, bs[pt]),
           (sz, bs[sz]), (frt, bs[frt]), (shw, bs[shw]), (fh, bs[fh]), (ft, bs[ft]), (svx, bs[svx])])
    bs[svy]["next"] = ru; bs[ru]["parent"] = svy
    chain([(ru, bs[ru]), (eh, bs[eh])])
    bs[et]["next"] = dec2; bs[dec2]["parent"] = et
    chain([(dec2, bs[dec2]), (dl, bs[dl])])
    return bs, comments

# ============================================================
#  보스 (대형 전차, 클론 없음)
# ============================================================
def build_boss_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    rs = b_rotstyle(bs, "left-right")
    sz0 = b_setsize(bs, 155)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz0, bs[sz0])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["보스생성", BR_BOSS]})
    cid = b_costume(bs, "idle")
    sx = b_setx(bs, 175)
    fy = vrep("바닥Y", V_FLOOR)
    sy = b_sety(bs, fy)
    setf = b_setvar(bs, "바라봄", V_BOSSFACE, -90)
    pt = b_point_dir(bs, -90)
    zcd = b_setvar(bs, "보스사격쿨", V_BOSSCD, 0.5)
    zifr = b_setvar(bs, "보스무적", V_BOSSIFRM, 0)
    wv = vrep("웨이브", V_WAVE)
    wm1 = op("operator_subtract", wv, 1)
    div = op("operator_divide", wm1, 6)
    cyc = b_mathop(bs, "floor", div)
    extra = op("operator_multiply", cyc, 2)
    base = vrep("보스기본체력", V_BOSSBASE)
    hp0 = op("operator_add", base, extra)
    smax = b_setvar(bs, "보스최대체력", V_BOSSMAXHP, hp0)
    mx = vrep("보스최대체력", V_BOSSMAXHP)
    hi16 = cmp_op("operator_gt", mx, 16)
    cap = b_setvar(bs, "보스최대체력", V_BOSSMAXHP, 16)
    ifcap = b_if(bs, hi16, cap)
    mx2 = vrep("보스최대체력", V_BOSSMAXHP)
    shp = b_setvar(bs, "보스체력", V_BOSSHP, mx2)
    g0 = b_setghost(bs, 0)
    sh = b_show(bs)
    ft = b_front(bs)
    chain([(hb, bs[hb]), (cid, bs[cid]), (sx, bs[sx]), (sy, bs[sy]), (setf, bs[setf]),
           (pt, bs[pt]), (zcd, bs[zcd]), (zifr, bs[zifr]), (smax, bs[smax]),
           (ifcap, bs[ifcap]), (shp, bs[shp]), (g0, bs[g0]), (sh, bs[sh]), (ft, bs[ft])])

    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=520)
    st = vrep("게임상태", V_STATE)
    play = cmp_op("operator_equals", st, 1)
    dead = cmp_op("operator_equals", st, 2)
    ndead = gen(); bs[ndead] = mk("operator_not", inputs={"OPERAND": [2, dead]})
    bs[dead]["parent"] = ndead
    bf = vrep("보스전", V_BOSSFIGHT)
    on = cmp_op("operator_equals", bf, 1)
    vis = bool_op("operator_and", on, ndead)
    # sit on ground
    col_h, col_t = emit_col_from_x(bs, vrep, op, cmp_op, "칸번호", V_BOSSCOL)
    gy = emit_ground_y(bs, vrep, op, "칸번호", V_BOSSCOL)
    yp = b_ypos(bs)
    low = cmp_op("operator_lt", yp, gy)
    gy2 = emit_ground_y(bs, vrep, op, "칸번호", V_BOSSCOL)
    sit = b_sety(bs, gy2)
    ifflo = b_if(bs, low, sit)
    # face player
    px = vrep("플레이어X", V_PLAYERX)
    xnow = b_xpos(bs)
    pright = cmp_op("operator_gt", px, xnow)
    setfr = b_setvar(bs, "바라봄", V_BOSSFACE, 90)
    ptr = b_point_dir(bs, 90)
    chain([(setfr, bs[setfr]), (ptr, bs[ptr])])
    setfl = b_setvar(bs, "바라봄", V_BOSSFACE, -90)
    ptl = b_point_dir(bs, -90)
    chain([(setfl, bs[setfl]), (ptl, bs[ptl])])
    turn = b_ifelse(bs, pright, setfr, setfl)
    # fire
    cd = vrep("보스사격쿨", V_BOSSCD)
    ready = cmp_op("operator_lt", cd, 0.01)
    en = vrep("적탄수", V_ESHOTN)
    mxb = vrep("최대적탄", V_MAXESHOT)
    room = cmp_op("operator_lt", en, mxb)
    can = bool_op("operator_and", ready, room)
    hx = b_xpos(bs)
    sxb = b_setvar(bs, "적탄X", V_ESHOTX, hx)
    hy = b_ypos(bs)
    lift = vrep("총알높이", V_MUZZLEY)
    extra_y = op("operator_add", hy, lift)
    syb = b_setvar(bs, "적탄Y", V_ESHOTY, extra_y)
    py = vrep("플레이어Y", V_PLAYERY)
    ynow = b_ypos(bs)
    dy = op("operator_subtract", py, ynow)
    px2 = vrep("플레이어X", V_PLAYERX)
    x2 = b_xpos(bs)
    dx = op("operator_subtract", px2, x2)
    adx = b_abs(bs, dx)
    adx2 = op("operator_add", adx, 0.1)
    ratio = op("operator_divide", dy, adx2)
    elev = b_mathop(bs, "atan", ratio)
    setelv = b_setvar(bs, "임시", V_TMP, elev)
    clift = b_changevar(bs, "임시", V_TMP, 24)
    tmax = vrep("임시", V_TMP)
    too_hi = cmp_op("operator_gt", tmax, 62)
    ifhi = b_if(bs, too_hi, b_setvar(bs, "임시", V_TMP, 62))
    fac2 = vrep("바라봄", V_BOSSFACE)
    eright = cmp_op("operator_gt", fac2, 0)
    tmp_r = vrep("임시", V_TMP)
    dirr = op("operator_subtract", 90, tmp_r)
    sdirr = b_setvar(bs, "적탄방향", V_ESHOTDIR, dirr)
    tmp_l = vrep("임시", V_TMP)
    dirl = op("operator_add", -90, tmp_l)
    sdirl = b_setvar(bs, "적탄방향", V_ESHOTDIR, dirl)
    ifaim = b_ifelse(bs, eright, sdirr, sdirl)
    brs = b_broadcast(bs, "적발사", BR_ESHOT)
    gap = vrep("적연사간격", V_EFIREGAP)
    scd = b_setvar(bs, "보스사격쿨", V_BOSSCD, gap)
    chain([(sxb, bs[sxb]), (syb, bs[syb]), (setelv, bs[setelv]), (clift, bs[clift]),
           (ifhi, bs[ifhi]), (ifaim, bs[ifaim]), (brs, bs[brs]), (scd, bs[scd])])
    ifshot = b_if(bs, can, sxb)
    cd2 = vrep("보스사격쿨", V_BOSSCD)
    cpos = cmp_op("operator_gt", cd2, 0)
    decd = b_changevar(bs, "보스사격쿨", V_BOSSCD, -0.03)
    ifcd = b_if(bs, cpos, decd)
    # i-frames
    ift = vrep("보스무적", V_BOSSIFRM)
    cif = cmp_op("operator_gt", ift, 0)
    decif = b_changevar(bs, "보스무적", V_BOSSIFRM, -0.03)
    g40 = b_setghost(bs, 35)
    chain([(decif, bs[decif]), (g40, bs[g40])])
    g0b = b_setghost(bs, 0)
    iframeb = b_ifelse(bs, cif, decif, g0b)
    # bump
    tt = b_touching(bs, "지아이조")
    pifr = vrep("무적타이머", V_IFRMT)
    noifr = cmp_op("operator_lt", pifr, 0.01)
    bump = bool_op("operator_and", tt, noifr)
    atk = vrep("적공격", V_ENATK)
    natk = op("operator_subtract", 0, atk)
    dhp = b_changevar(bs, "체력", V_HP, natk)
    ifr = vrep("무적시간", V_IFRAME)
    sif = b_setvar(bs, "무적타이머", V_IFRMT, ifr)
    hurtb = b_broadcast(bs, "피격", BR_HURT)
    chain([(dhp, bs[dhp]), (sif, bs[sif]), (hurtb, bs[hurtb])])
    ifbump = b_if(bs, bump, dhp)
    # death
    hp = vrep("보스체력", V_BOSSHP)
    cdead = cmp_op("operator_lt", hp, 1)
    sc = b_changevar(bs, "점수", V_SCORE, 500)
    kil = b_changevar(bs, "처치수", V_KILLS, 1)
    cwv = b_changevar(bs, "웨이브", V_WAVE, 1)
    gap2 = vrep("스폰간격", V_SPAWN)
    ramp = vrep("난이도증가율", V_RAMP)
    om = op("operator_subtract", 1, ramp)
    ng = op("operator_multiply", gap2, om)
    sg = b_setvar(bs, "스폰간격", V_SPAWN, ng)
    zbf = b_setvar(bs, "보스전", V_BOSSFIGHT, 0)
    s3 = b_setvar(bs, "게임상태", V_STATE, 3)
    bmap = b_broadcast(bs, "맵변경", BR_MAP)
    eh, et = emit_boom_anim(bs)
    hid = b_hide(bs)
    chain([(sc, bs[sc]), (kil, bs[kil]), (cwv, bs[cwv]), (sg, bs[sg]),
           (zbf, bs[zbf]), (s3, bs[s3]), (bmap, bs[bmap]), (eh, bs[eh])])
    bs[et]["next"] = hid; bs[hid]["parent"] = et
    deathb = b_if(bs, cdead, sc)
    shw = b_show(bs)
    chain([(turn, bs[turn]), (ifshot, bs[ifshot]), (ifcd, bs[ifcd]),
           (iframeb, bs[iframeb]), (ifbump, bs[ifbump]), (deathb, bs[deathb])])
    ifai = b_if(bs, play, turn)
    shw2 = b_show(bs)
    chain([(shw2, bs[shw2]), (col_h, bs[col_h])])
    bs[col_t]["next"] = ifflo; bs[ifflo]["parent"] = col_t
    bs[ifflo]["next"] = ifai; bs[ifai]["parent"] = ifflo
    hi2 = b_hide(bs)
    ifelse = b_ifelse(bs, vis, shw2, hi2)
    w2 = b_wait(bs, 0.03)
    chain([(ifelse, bs[ifelse]), (w2, bs[w2])])
    fr = b_forever(bs, ifelse)
    chain([(hf, bs[hf]), (fr, bs[fr])])

    def emit_hit_hat(bname, brid, hit_name, hit_id, rad_name, rad_id, y):
        hat = gen(); bs[hat] = mk("event_whenbroadcastreceived", top=True, x=20, y=y,
            fields={"BROADCAST_OPTION": [bname, brid]})
        bf = vrep("보스전", V_BOSSFIGHT)
        on = cmp_op("operator_equals", bf, 1)
        ift = vrep("보스무적", V_BOSSIFRM)
        noifr = cmp_op("operator_lt", ift, 0.01)
        ok = bool_op("operator_and", on, noifr)
        xp = b_xpos(bs)
        hx = vrep(hit_name, hit_id)
        diff = op("operator_subtract", xp, hx)
        ad = b_abs(bs, diff)
        rad = vrep(rad_name, rad_id)
        near = cmp_op("operator_lt", ad, rad)
        both = bool_op("operator_and", ok, near)
        dhp = b_changevar(bs, "보스체력", V_BOSSHP, -1)
        sif = b_setvar(bs, "보스무적", V_BOSSIFRM, 0.25)
        chain([(dhp, bs[dhp]), (sif, bs[sif])])
        iff = b_if(bs, both, dhp)
        chain([(hat, bs[hat]), (iff, bs[iff])])

    emit_hit_hat("탄맞음", BR_HITSHOT, "탄히트X", V_SHOTHITX, "탄히트범위", V_SHOTRAD, 980)
    emit_hit_hat("수류탄폭발", BR_HITNADE, "수류탄히트X", V_NADEHITX, "수류탄범위", V_NADERAD, 1180)
    return bs, comments

# ============================================================
#  파워 게이지 (틀 + 채움)
# ============================================================
def build_gauge_blocks(is_fill, kind="power"):
    """kind=power: 하단 차지 게이지. kind=boss: 상단 보스 체력."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    rs = b_rotstyle(bs, "don't rotate")
    pt = b_point_dir(bs, 90)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (pt, bs[pt])])
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=160)
    st = vrep("게임상태", V_STATE)
    play = cmp_op("operator_equals", st, 1)
    gy = 148 if kind == "boss" else -162
    go = b_gotoxy(bs, -200, gy)
    if kind == "boss":
        bf = vrep("보스전", V_BOSSFIGHT)
        on = cmp_op("operator_equals", bf, 1)
        hp = vrep("보스체력", V_BOSSHP)
        alive = cmp_op("operator_gt", hp, 0)
        vis = bool_op("operator_and", on, alive)
        both = bool_op("operator_and", play, vis)
        if is_fill:
            hp2 = vrep("보스체력", V_BOSSHP)
            prod = op("operator_multiply", hp2, 100)
            mx = vrep("보스최대체력", V_BOSSMAXHP)
            den = op("operator_add", mx, 0.1)
            ratio = op("operator_divide", prod, den)
            sz = b_setsize(bs, ratio)
        else:
            sz = b_setsize(bs, 100)
    else:
        chg = vrep("차지중", V_CHARGING)
        charging = cmp_op("operator_equals", chg, 1)
        both = bool_op("operator_and", play, charging)
        if is_fill:
            pw = vrep("파워", V_POWER)
            sz = b_setsize(bs, pw)
        else:
            sz = b_setsize(bs, 100)
    sh = b_show(bs)
    chain([(go, bs[go]), (sz, bs[sz]), (sh, bs[sh])])
    hi2 = b_hide(bs)
    ifelse = b_ifelse(bs, both, go, hi2)
    w = b_wait(bs, 0.02)
    chain([(ifelse, bs[ifelse]), (w, bs[w])])
    fr = b_forever(bs, ifelse)
    chain([(hf, bs[hf]), (fr, bs[fr])])
    return bs, comments

# ============================================================
#  방패 (미사용)
# ============================================================
def build_shield_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    rs = b_rotstyle(bs, "left-right")
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs])])
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=160)
    shd = vrep("방패중", V_SHIELD)
    on = cmp_op("operator_equals", shd, 1)
    gt = b_goto_sprite(bs, "지아이조")
    fac = vrep("바라봄", V_FACING)
    pt = b_point_dir(bs, fac)
    fwd = vrep("총구앞", V_MUZZLEF)
    extra = op("operator_add", fwd, 8)
    mv = b_movesteps(bs, extra)
    lift = vrep("총알높이", V_MUZZLEY)
    cy = b_changeyby(bs, lift)
    sh = b_show(bs)
    ft = b_front(bs)
    chain([(gt, bs[gt]), (pt, bs[pt]), (mv, bs[mv]), (cy, bs[cy]), (sh, bs[sh]), (ft, bs[ft])])
    hi2 = b_hide(bs)
    ifelse = b_ifelse(bs, on, gt, hi2)
    w = b_wait(bs, 0.03)
    chain([(ifelse, bs[ifelse]), (w, bs[w])])
    fr = b_forever(bs, ifelse)
    chain([(hf, bs[hf]), (fr, bs[fr])])
    return bs, comments

# ============================================================
#  총구 (조준선)
# ============================================================
def build_muzzle_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    rs = b_rotstyle(bs, "all around")
    sz = b_setsize(bs, 100)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz])])
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=20, y=180)
    st = vrep("게임상태", V_STATE)
    dead = cmp_op("operator_equals", st, 2)
    hi2 = b_hide(bs)
    gt = b_goto_sprite(bs, "지아이조")
    my = vrep("총알높이", V_MUZZLEY)
    lift = b_changeyby(bs, my)
    fac = vrep("발사방향", V_FIREDIR)
    pt = b_point_dir(bs, fac)
    fwd = op("operator_divide", vrep("총구앞", V_MUZZLEF), 2)
    mv = b_movesteps(bs, fwd)
    sh = b_show(bs)
    chain([(gt, bs[gt]), (lift, bs[lift]), (pt, bs[pt]), (mv, bs[mv]), (sh, bs[sh])])
    ifelse = b_ifelse(bs, dead, hi2, gt)
    w = b_wait(bs, 0.03)
    chain([(ifelse, bs[ifelse]), (w, bs[w])])
    fr = b_forever(bs, ifelse)
    chain([(hf, bs[hf]), (fr, bs[fr])])
    return bs, comments

# ============================================================
#  장벽 (unused, kept out of project)
# ============================================================
def build_barrier_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    rs = b_rotstyle(bs, "don't rotate")
    sz = b_setsize(bs, 100)
    fy = vrep("바닥Y", V_FLOOR)
    g1 = b_gotoxy(bs, -40, fy)
    c1 = b_clone_self(bs)
    fy2 = vrep("바닥Y", V_FLOOR)
    g2 = b_gotoxy(bs, 55, fy2)
    c2 = b_clone_self(bs)
    park = b_gotoxy(bs, 0, 200)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz]),
           (g1, bs[g1]), (c1, bs[c1]), (g2, bs[g2]), (c2, bs[c2]), (park, bs[park])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=280)
    sh = b_show(bs)
    chain([(ch, bs[ch]), (sh, bs[sh])])
    return bs, comments

# ============================================================
#  배너
# ============================================================
def build_banner_blocks():
    bs = {}; comments = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    chain([(h, bs[h]), (hi, bs[hi])])
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["게임오버", BR_OVER]})
    go = b_gotoxy(bs, 0, 0)
    ft = b_front(bs)
    sh = b_show(bs)
    sh_h, sh_t = b_sound(bs, 0, "gameover")
    chain([(hb, bs[hb]), (go, bs[go]), (ft, bs[ft]), (sh, bs[sh]),
           (sh_h, bs[sh_h]), (sh_t, bs[sh_t])])
    return bs, comments

# ============================================================
#  main
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)
    if not os.path.isdir(ASSETS): os.makedirs(ASSETS)

    def save_png_file(filename):
        path = os.path.join(ASSETS, filename)
        with open(path, "rb") as f:
            b = f.read()
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.png", "wb") as f:
            f.write(b)
        return m

    def png(name, filename, cx, cy, res=2):
        m = save_png_file(filename)
        return {"name": name, "bitmapResolution": res, "dataFormat": "png",
                "assetId": m, "md5ext": f"{m}.png",
                "rotationCenterX": cx, "rotationCenterY": cy}

    def save_wav(name, samples):
        b = _wav_bytes(samples)
        with open(f"{ASSETS}/{name}.wav", "wb") as f: f.write(b)
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)

    nade_m, nade_n = save_wav("nade", synth_nade())
    pop_m, pop_n   = save_wav("pop", synth_pop())
    click_m, click_n = save_wav("click", synth_click())
    hurt_m, hurt_n = save_wav("hurt", synth_hurt())
    gov_m, gov_n   = save_wav("gameover", synth_gameover())

    def snd(name, m, n):
        return {"name": name, "assetId": m, "dataFormat": "wav", "format": "",
                "rate": SND_RATE, "sampleCount": n, "md5ext": f"{m}.wav"}

    def load_mp3(filename):
        path = os.path.join(ASSETS, filename)
        with open(path, "rb") as f:
            b = f.read()
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.mp3", "wb") as f:
            f.write(b)
        return m

    def snd_mp3(name, m, rate, seconds):
        return {"name": name, "assetId": m, "dataFormat": "mp3", "format": "",
                "rate": rate, "sampleCount": int(seconds * rate),
                "md5ext": f"{m}.mp3"}

    bgm_md5 = load_mp3("bgm.mp3")
    fire_md5 = load_mp3("fire.mp3")
    boom_md5 = load_mp3("boom.mp3")
    S_bgm = lambda: snd_mp3("bgm", bgm_md5, 48000, 139.25)
    S_fire = lambda: snd_mp3("fire", fire_md5, 48000, 5.50)
    S_boom = lambda: snd_mp3("boom", boom_md5, 24000, 2.11)

    stage_b, stage_c = build_stage_blocks()
    ply_b, ply_c     = build_player_blocks()
    shot_b, shot_c   = build_shot_blocks()
    nade_b, nade_c   = build_nade_blocks()
    en_b, en_c       = build_enemy_blocks()
    esh_b, esh_c     = build_eshot_blocks()
    terr_b, terr_c   = build_terrain_blocks()
    muz_b, muz_c     = build_muzzle_blocks()
    gtr_b, gtr_c     = build_gauge_blocks(False)
    gfl_b, gfl_c     = build_gauge_blocks(True)
    btr_b, btr_c     = build_gauge_blocks(False, kind="boss")
    bfl_b, bfl_c     = build_gauge_blocks(True, kind="boss")
    boss_b, boss_c   = build_boss_blocks()
    ban_b, ban_c     = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_MOVE: ["이동속도", 4], V_JUMP: ["점프력", 11], V_GRAV: ["중력", -1.1],
            V_FLOOR: ["바닥Y", -100], V_FIREGAP: ["연사간격", 0.18], V_SHOTSPD: ["탄속", 10],
            V_MAXSHOT: ["최대탄수", 6], V_NADESPD: ["수류탄력", 6], V_NADEUP: ["수류탄띄움", 10],
            V_NADECD: ["수류탄쿨", 1.2], V_ENSPD: ["적속도", 1.3], V_SPAWN: ["스폰간격", 1.2],
            V_MAXEN: ["최대적수", 6], V_MAXHP: ["최대체력", 5], V_ENATK: ["적공격", 1],
            V_IFRAME: ["무적시간", 1.0], V_RAMP: ["난이도증가율", 0.05],
            V_WAVEKILLS: ["웨이브킬", 16],
            V_MUZZLEY: ["총알높이", 24], V_MUZZLEF: ["총구앞", 18],
            V_SHOTRAD: ["탄히트범위", 55], V_NADERAD: ["수류탄범위", 100],
            V_BARHOP: ["장벽넘기", 26],
            V_SHOOTP: ["사수확률", 35], V_BACKP: ["뒤쪽확률", 28],
            V_RANGE: ["사정거리", 110], V_EFIREGAP: ["적연사간격", 1.1],
            V_ESHOTSPD: ["적탄속", 7], V_MAXESHOT: ["최대적탄", 4],
            V_CELLW: ["칸크기", 24], V_CELLN: ["칸수", 20],
            V_MAG: ["탄창", 6], V_RELOADT: ["재장전시간", 0.8], V_BALLLIFE: ["포탄수명", 90],
            V_AIMSTEP: ["조준속도", 4], V_SHOTGRAV: ["탄중력", -0.85],
            V_STATE: ["게임상태", 1], V_SCORE: ["점수", 0], V_HP: ["체력", 5],
            V_WAVE: ["웨이브", 1], V_SHOTN: ["탄수", 0], V_ENN: ["적수", 0],
            V_KILLS: ["처치수", 0], V_FACING: ["바라봄", 90], V_NADET: ["수류탄쿨남은", 0],
            V_VY: ["VY", 0], V_PREVJ: ["점프이전키", 0], V_IFRMT: ["무적타이머", 0],
            V_NADEN: ["수류탄수", 0],
            V_SHOTHITX: ["탄히트X", 0], V_NADEHITX: ["수류탄히트X", 0],
            V_PLAYERX: ["플레이어X", -140], V_ESHOTN: ["적탄수", 0],
            V_ESHOTX: ["적탄X", 0], V_ESHOTY: ["적탄Y", 0], V_ESHOTDIR: ["적탄방향", -90],
            V_AMMO: ["남은탄", 6], V_RELOADING: ["재장전중", 0], V_RELLEFT: ["재장전남은", 0],
            V_SHIELD: ["방패중", 0], V_TERRI: ["지형i", 1], V_TMP: ["임시", 0], V_TMPK: ["임시k", 1],
            V_ANGLE: ["각도", 50], V_FIREDIR: ["발사방향", 40], V_PLAYERY: ["플레이어Y", -100],
            V_POWER: ["파워", 0], V_CHARGING: ["차지중", 0], V_POWSPD: ["파워속도", 5],
            V_MINPOW: ["최소파워", 20], V_MAXPOW: ["최대파워", 100], V_FIRESPD: ["발사탄속", 10],
            V_BGMVOL: ["브금볼륨", 70], V_POWSCALE: ["파워배율", 2.4],
            V_BOSSFIGHT: ["보스전", 0], V_BOSSHP: ["보스체력", 0], V_BOSSMAXHP: ["보스최대체력", 8],
            V_BOSSBASE: ["보스기본체력", 8], V_BOSSIFRM: ["보스무적", 0], V_BOSSCD: ["보스사격쿨", 0],
            V_STAGE: ["스테이지", 1],
        },
        "lists": {L_HEIGHT: ["지형높이", []]},
        "broadcasts": {
            BR_START: "게임시작", BR_FIRE: "발사", BR_NADE: "수류탄",
            BR_SPAWN: "적생성", BR_OVER: "게임오버",
            BR_HITSHOT: "탄맞음", BR_HITNADE: "수류탄폭발", BR_ESHOT: "적발사",
            BR_MAP: "맵변경", BR_DRAW: "지형그리기", BR_HURT: "피격", BR_BOSS: "보스생성",
        },
        "blocks": stage_b, "comments": stage_c, "currentCostume": 0,
        "costumes": [png(f"bg{i}", f"bg{i}.png", 240, 180, 1) for i in range(1, 7)],
        "sounds": [S_bgm()], "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None,
    }

    def sprite(name, blocks, cmt, costumes, sounds, layer, *, visible=True, x=0, y=0,
               rot="all around", variables=None):
        return {
            "isStage": False, "name": name,
            "variables": variables or {}, "lists": {}, "broadcasts": {},
            "blocks": blocks, "comments": cmt,
            "currentCostume": 0, "costumes": costumes, "sounds": sounds,
            "volume": 100, "layerOrder": layer, "visible": visible,
            "x": x, "y": y, "size": 100, "direction": 90,
            "draggable": False, "rotationStyle": rot,
        }

    boom_cs = [png(f"boom{i}", f"boom{i}.png", 72, 72) for i in range(1, 5)]
    player = sprite("지아이조", ply_b, ply_c,
        [png("idle", "tank_idle.png", 70, 76)] + boom_cs,
        [snd("click", click_m, click_n), S_boom(),
         snd("hurt", hurt_m, hurt_n)],
        4, x=-140, y=-100, rot="left-right",
        variables={V_TANKCOL: ["칸번호", 1]})
    shot = sprite("총알", shot_b, shot_c,
        [png("bullet", "shell.png", 24, 14)] + boom_cs,
        [S_fire(), S_boom()],
        5, visible=False,
        variables={V_SHOTISC: ["복제됨", 0], V_SHOTCOL: ["칸번호", 1], V_SHOTLIFE: ["남은수명", 90],
                   V_SHOTVX: ["속도X", 0], V_SHOTVY: ["속도Y", 0]})
    nade = sprite("수류탄", nade_b, nade_c,
        [png("nade", "nade.png", 20, 48)] + boom_cs,
        [snd("nade", nade_m, nade_n), S_boom()],
        5, visible=False,
        variables={V_NADEISC: ["복제됨", 0], V_NADEVX: ["속도X", 0], V_NADEVY: ["속도Y", 0],
                   V_NCOL: ["칸번호", 1]})
    enemy = sprite("적", en_b, en_c,
        [png("walker", "tank_red.png", 70, 76), png("shooter", "tank_grey.png", 70, 76)] + boom_cs,
        [snd("pop", pop_m, pop_n), S_boom()],
        3, visible=False, rot="left-right",
        variables={V_ENISC: ["복제됨", 0], V_ENKIND: ["종류", 1], V_ENVY: ["내VY", 0],
                   V_ENFACE: ["바라봄", -90], V_ENFIRET: ["사격쿨", 0], V_ENCOL: ["칸번호", 1],
                   V_ENBLOCK: ["막힘", 0]})
    eshot = sprite("적탄", esh_b, esh_c,
        [png("ebullet", "shell_red.png", 24, 14)] + boom_cs,
        [S_fire(), S_boom()],
        5, visible=False,
        variables={V_ESHOTISC: ["복제됨", 0], V_ESCOL: ["칸번호", 1], V_ESLIFE: ["남은수명", 90],
                   V_ESHOTVX: ["속도X", 0], V_ESHOTVY: ["속도Y", 0]})
    terrain = sprite("지형", terr_b, terr_c,
        [png("tile", "tile.png", 24, 24)],
        [], 1, visible=False, rot="don't rotate")
    muzzle = sprite("총구", muz_b, muz_c,
        [png("gun", "gun.png", 18, 18)],
        [], 5, visible=False, rot="all around")
    gauge_track = sprite("파워틀", gtr_b, gtr_c,
        [png("track", "gauge_track.png", 0, 16)],
        [], 8, visible=False, rot="don't rotate", x=-200, y=-162)
    gauge_fill = sprite("파워바", gfl_b, gfl_c,
        [png("fill", "gauge_fill.png", 0, 10)],
        [], 9, visible=False, rot="don't rotate", x=-200, y=-162)
    boss = sprite("보스", boss_b, boss_c,
        [png("idle", "tank_boss.png", 100, 96)] + boom_cs,
        [S_boom()],
        4, visible=False, rot="left-right", x=175, y=-100,
        variables={V_BOSSCOL: ["칸번호", 1], V_BOSSFACE: ["바라봄", -90]})
    boss_track = sprite("보스틀", btr_b, btr_c,
        [png("track", "gauge_track.png", 0, 16)],
        [], 6, visible=False, rot="don't rotate", x=-200, y=148)
    boss_fill = sprite("보스바", bfl_b, bfl_c,
        [png("fill", "boss_gauge_fill.png", 0, 10)],
        [], 7, visible=False, rot="don't rotate", x=-200, y=148)
    banner = sprite("배너", ban_b, ban_c,
        [png("gameover", "gameover.png", 360, 150)],
        [snd("gameover", gov_m, gov_n)],
        10, visible=False, rot="don't rotate")

    monitors = []
    def mon(vid, name, x, y, slider=False, smin=0, smax=20):
        monitors.append({
            "id": vid, "mode": "slider" if slider else "default",
            "opcode": "data_variable", "params": {"VARIABLE": name},
            "spriteName": None, "value": 0, "width": 0, "height": 0,
            "x": x, "y": y, "visible": True,
            "sliderMin": smin, "sliderMax": smax, "isDiscrete": True,
        })
    mon(V_SCORE, "점수", 5, 5)
    mon(V_HP, "체력", 5, 29)
    mon(V_WAVE, "웨이브", 5, 53)
    mon(V_ANGLE, "각도", 5, 77)

    project = {
        "targets": [stage, terrain, player, muzzle, shot, nade, enemy, eshot, boss,
                    gauge_track, gauge_fill, boss_track, boss_fill, banner],
        "monitors": monitors, "extensions": ["pen"],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "gi-joe-builder"},
    }
    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)
    print(f"✓ wrote {OUTPUT}")

if __name__ == "__main__":
    main()
