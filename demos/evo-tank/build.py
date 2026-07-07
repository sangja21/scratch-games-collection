#!/usr/bin/env python3
"""진화 탱크 (evo-tank) — diep.io 형 탑뷰 탱크 진화 슈터 [데모 빌드].

화살표로 탱크를 몰고, 포탑이 마우스를 부드럽게 따라 돌며, 마우스 홀드로 포탄을
발사한다. 필드의 도형(경험치)과 추격해 오는 적 탱크를 부수며 레벨업 → 첫 레벨업에
진화 카드(쌍포신/스나이퍼/머신건)가 뜨고, 고르면 포탑 코스튬이 실제로 바뀌며
발사 패턴이 확 달라진다. 이 진화 순간이 데모의 하이라이트.

베이스: games/magic-survivor/build.py (클론 스포너·복제됨 가드·레벨업 상태머신·
        전용 효과음 합성·add_comment 가이드) + games/tank-battle(포탑 조준)
      + games/castle-defense(클릭 폴링+디바운스).

★ 데모 스코프: 폴리시 생략, 핵심 루프의 손맛에 집중. 목표 300~500 블록.
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "진화_탱크.sb3")

# ============================================================
#  효과음 합성 (전용 3종: pew 발사 / crack 파괴 / hurt 피격) — 결정적
# ============================================================
SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_pew(rate=SND_RATE):
    """포탄 발사 — 낮게 '퓨웅' 하강 (탱크 포 느낌, 자주 울려도 안 거슬리게 짧게)."""
    N = int(rate * 0.10); out = []
    for i in range(N):
        t = i / rate
        f = 130 + 520 * math.exp(-t * 22)        # 650Hz → 130Hz 하강
        env = math.exp(-t * 24)
        s = math.sin(2 * math.pi * f * t)
        s = (s + 0.35 * (1 if s > 0 else -1)) / 1.35
        out.append(s * env * 0.5)
    return out

def synth_crack(rate=SND_RATE):
    """도형/적 파괴 — 짧은 노이즈 '빠각' 파열음. 고정 시드로 결정적."""
    N = int(rate * 0.14); out = []
    rng = random.Random(770311)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 20)
        white = rng.random() * 2 - 1
        lp = lp + 0.6 * (white - lp)
        thump = math.sin(2 * math.pi * (110 + 60 * math.exp(-t * 18)) * t)
        s = (lp * 0.7 + thump * 0.5) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_hurt(rate=SND_RATE):
    """플레이어 피격 — 낮은 '부웅' 경고음."""
    N = int(rate * 0.20); out = []
    for i in range(N):
        t = i / rate
        f = 200 - 90 * t / 0.20                   # 하강 사이렌
        env = math.exp(-t * 8) * (1 - math.exp(-t * 60))
        s = math.sin(2 * math.pi * f * t)
        s = (s + 0.5 * math.sin(2 * math.pi * f * 0.5 * t)) / 1.5
        out.append(s * env * 0.6)
    return out

# ============================================================
#  SVG assets
# ============================================================
# -------- 배경: 옅은 그리드 (diep.io 감성) --------
grid = []
for gx in range(0, 481, 40):
    grid.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="360" stroke="#D3DBE4" stroke-width="2"/>')
for gy in range(0, 361, 40):
    grid.append(f'<line x1="0" y1="{gy}" x2="480" y2="{gy}" stroke="#D3DBE4" stroke-width="2"/>')
GRID = "\n    ".join(grid)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#E9EEF3"/>
  <g>
    {GRID}
  </g>
  <rect x="4" y="4" width="472" height="352" fill="none" stroke="#B7C2CF" stroke-width="8"/>
</svg>"""

# -------- 탱크 본체(hull): 탑뷰, 방향 고정 (64x64) --------
HULL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect x="6" y="8" width="52" height="12" rx="4" fill="#3A4756"/>
  <rect x="6" y="44" width="52" height="12" rx="4" fill="#3A4756"/>
  <rect x="9" y="9" width="46" height="4" rx="2" fill="#556172"/>
  <rect x="9" y="45" width="46" height="4" rx="2" fill="#556172"/>
  <circle cx="32" cy="32" r="20" fill="#4C9BE0" stroke="#2C6BA8" stroke-width="3"/>
  <circle cx="32" cy="32" r="9" fill="#7FBEF0"/>
</svg>"""

# -------- 포탑 4종: 허브(중앙) + 오른쪽(+x, 방향 90) 포신 (120x120) --------
def _turret(barrels, hub="#37475A", steel="#5A6B80"):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  {barrels}
  <circle cx="60" cy="60" r="18" fill="{hub}" stroke="#20293A" stroke-width="3"/>
  <circle cx="60" cy="60" r="7" fill="{steel}"/>
</svg>"""

TUR_BASE = _turret(
  '<rect x="58" y="49" width="46" height="22" rx="3" fill="#5A6B80" stroke="#20293A" stroke-width="2"/>')
TUR_DUAL = _turret(
  '<rect x="58" y="36" width="44" height="15" rx="3" fill="#5A6B80" stroke="#20293A" stroke-width="2"/>'
  '<rect x="58" y="69" width="44" height="15" rx="3" fill="#5A6B80" stroke="#20293A" stroke-width="2"/>')
TUR_SNIPE = _turret(
  '<rect x="58" y="53" width="60" height="14" rx="2" fill="#7C5AA8" stroke="#3E2C63" stroke-width="2"/>'
  '<rect x="112" y="51" width="6" height="18" rx="2" fill="#3E2C63"/>')
TUR_MG = _turret(
  '<rect x="56" y="42" width="40" height="36" rx="4" fill="#B5651D" stroke="#5E3410" stroke-width="2"/>'
  '<rect x="92" y="46" width="10" height="7" rx="2" fill="#5E3410"/>'
  '<rect x="92" y="58" width="10" height="7" rx="2" fill="#5E3410"/>'
  '<rect x="92" y="70" width="10" height="7" rx="2" fill="#5E3410"/>')

# -------- 포탄: 오른쪽(+x) 향한 탄 (24x24) --------
BOLT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="9" fill="#FFB300" opacity="0.35"/>
  <circle cx="12" cy="12" r="6" fill="#FFC93C" stroke="#C77800" stroke-width="2"/>
  <circle cx="14" cy="10" r="2" fill="#FFF3D0"/>
</svg>"""

# -------- 도형: 사각(경험치1) / 삼각(경험치3) (48x48) --------
SQUARE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <rect x="10" y="10" width="28" height="28" rx="4" fill="#F6C744" stroke="#B98B10" stroke-width="3"/>
  <rect x="15" y="15" width="10" height="10" rx="2" fill="#FBE39A"/>
</svg>"""
TRI_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <polygon points="24,7 42,39 6,39" fill="#E5555B" stroke="#8E2A30" stroke-width="3"/>
  <polygon points="24,16 33,33 15,33" fill="#F29A9E"/>
</svg>"""

# -------- 적 탱크: 탑뷰 (48x48) --------
ENEMY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <rect x="5" y="7" width="38" height="9" rx="3" fill="#5B2A2A"/>
  <rect x="5" y="32" width="38" height="9" rx="3" fill="#5B2A2A"/>
  <rect x="30" y="21" width="16" height="6" rx="2" fill="#7A3B3B"/>
  <circle cx="24" cy="24" r="15" fill="#C0392B" stroke="#7A1E14" stroke-width="3"/>
  <circle cx="24" cy="24" r="6" fill="#E8776B"/>
</svg>"""

# -------- 진화 카드: 3선택 (460x220) --------
def _card_panel(x, title, sub, fill):
    return (f'<rect x="{x}" y="58" width="132" height="150" rx="12" fill="{fill}" stroke="#FFFFFF" stroke-width="3"/>'
            f'<text x="{x+66}" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="22" font-weight="bold">{title}</text>'
            f'<text x="{x+66}" y="150" text-anchor="middle" fill="#FFF7DA" font-family="Arial, sans-serif" font-size="14">{sub}</text>')
CARD_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="460" height="220" viewBox="0 0 460 220">
  <rect x="4" y="4" width="452" height="212" rx="16" fill="#12203A" opacity="0.96" stroke="#FFD54F" stroke-width="4"/>
  <text x="230" y="40" text-anchor="middle" fill="#FFD54F" font-family="Arial, sans-serif" font-size="24" font-weight="bold">진화 선택!  (1 / 2 / 3)</text>
  {_card_panel(16, "1 쌍포신", "총알 2줄!", "#2E7D32")}
  {_card_panel(164, "2 스나이퍼", "한 방 강하게", "#6A1B9A")}
  {_card_panel(312, "3 머신건", "빠른 난사", "#B5651D")}
</svg>"""

# -------- 체력바 / 경험치바: 11단 코스튬 fill --------
def bar_svg(frac, color, track="#2B3440", w=176, h=20):
    pad = 4
    fw = int((w - pad * 2) * frac)
    fill = "" if fw <= 0 else f'<rect x="{pad}" y="{pad}" width="{fw}" height="{h-pad*2}" rx="3" fill="{color}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<rect x="0" y="0" width="{w}" height="{h}" rx="5" fill="{track}"/>'
            f'{fill}</svg>')
HP_SVGS  = [bar_svg(i / 10.0, "#E5484D") for i in range(11)]
XP_SVGS  = [bar_svg(i / 10.0, "#3FA7F0") for i in range(11)]

# ============================================================
#  helpers (scratch-game-template 공통 헬퍼 — 재구현 금지, 복제)
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
def add_comment(bs, comments, block_id, text, x=520, y=40, w=300, h=150):
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

def b_pointtowards(bs, target):
    m = gen(); bs[m] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": [target, None]}, shadow=True)
    p = gen(); bs[p] = mk("motion_pointtowards", inputs={"TOWARDS": [1, m]})
    bs[m]["parent"] = p
    return p

def b_movesteps(bs, steps_value):
    bid = gen()
    if isinstance(steps_value, str) and steps_value in bs:
        bs[bid] = mk("motion_movesteps", inputs={"STEPS": slot(steps_value)})
        bs[steps_value]["parent"] = bid
    else:
        bs[bid] = mk("motion_movesteps", inputs={"STEPS": num(steps_value)})
    return bid

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

def b_wait_until(bs, cond):
    bid = gen(); bs[bid] = mk("control_wait_until", inputs={"CONDITION": [2, cond]})
    bs[cond]["parent"] = bid
    return bid

def b_wait(bs, dur):
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": num(dur)})
    return bid

def b_wait_var(bs, vid, name):
    v = gen(); bs[v] = mk("data_variable", fields={"VARIABLE": [name, vid]})
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": slot(v)})
    bs[v]["parent"] = bid
    return bid

def b_gotoxy(bs, x, y):
    bid = gen(); ins = {}
    ins["X"] = slot(x) if (isinstance(x, str) and x in bs) else num(x)
    ins["Y"] = slot(y) if (isinstance(y, str) and y in bs) else num(y)
    bs[bid] = mk("motion_gotoxy", inputs=ins)
    for v in (x, y):
        if isinstance(v, str) and v in bs: bs[v]["parent"] = bid
    return bid

def b_sound(bs, pitch, sound="pop"):
    pe = gen(); bs[pe] = mk("sound_seteffectto",
        inputs={"VALUE": num(pitch)}, fields={"EFFECT": ["PITCH", None]})
    sm = gen(); bs[sm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]})
    bs[sm]["parent"] = sp
    chain([(pe, bs[pe]), (sp, bs[sp])])
    return pe, sp

def b_broadcast(bs, name, brid):
    m = gen(); bs[m] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcast", inputs={"BROADCAST_INPUT": [1, m]})
    bs[m]["parent"] = b
    return b

def b_switch_costume_name(bs, name):
    m = gen(); bs[m] = mk("looks_costume", fields={"COSTUME": [name, None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, m]})
    bs[m]["parent"] = sw
    return sw

def b_switch_costume_val(bs, val_id):
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(val_id)})
    bs[val_id]["parent"] = sw
    return sw

def _spr_menu(bs, name):
    m = gen(); bs[m] = mk("sensing_of_object_menu",
        fields={"OBJECT": [name, None]}, shadow=True)
    return m

def _of(bs, spr, prop):
    bid = gen(); bs[bid] = mk("sensing_of",
        inputs={"OBJECT": [1, _spr_menu(bs, spr)]}, fields={"PROPERTY": [prop, None]})
    return bid

# ============================================================
#  IDs
# ============================================================
# ----- 튜닝 손잡이 (plan 핵심 변수) -----
V_MOVE     = "varMove01"       # 이동속도        4.5
V_FIRECD   = "varFireCd02"     # 발사쿨          0.3
V_BOLTSPD  = "varBoltSpd03"    # 포탄속도        10
V_ATK      = "varAtk04"        # 공격력          1
V_SQHP     = "varSqHp05"       # 사각체력        2
V_TRHP     = "varTrHp06"       # 삼각체력        4
V_EHP      = "varEHp07"        # 적탱크체력      3
V_ESPD     = "varESpd08"       # 적탱크속도      2
V_HP       = "varHp09"         # 내체력          5
V_INVSEC   = "varInvSec10"     # 무적시간(초)    0.5
V_LVUP     = "varLvUp11"       # 레벨업경험치    10
V_SPAWNGAP = "varSpawnGap12"   # 스폰간격        1.2
V_EVO      = "varEvo13"        # 진화 0=기본 1=쌍포신 2=스나이퍼 3=머신건
# ----- 진화가 세팅하는 발사 파라미터 -----
V_NBOLT    = "varNBolt14"      # 발사수          1
V_SPREAD   = "varSpread15"     # 산탄(도)        0
V_PARGAP   = "varParGap16"     # 평행간격(px)    0
# ----- 파생/템포 -----
V_HPMAX    = "varHpMax17"      # 내체력최대      5
V_TARGETSH = "varTargetSh18"   # 목표도형수      7
V_ENXP     = "varEnXp19"       # 적탱크경험치    2
# ----- 진행 상태 -----
V_STATE    = "varState20"      # 게임상태 1=전투 2=진화선택 0=게임오버
V_LEVEL    = "varLevel21"      # 레벨
V_EXP      = "varExp22"        # 경험치
V_INV      = "varInv23"        # 무적 (1이면 무적중)
V_SHAPES   = "varShapes24"     # 도형수
V_FIREDIR  = "varFireDir25"    # 발사방향
V_FIREX    = "varFireX26"      # 발사X
V_FIREY    = "varFireY27"      # 발사Y
V_FIREI    = "varFireI28"      # 발사인덱스
V_SPX      = "varSpX29"        # 적생성X
V_SPY      = "varSpY30"        # 적생성Y
V_SHPX     = "varShpX31"       # 도형생성X
V_SHPY     = "varShpY32"       # 도형생성Y
V_SHPTYPE  = "varShpType33"    # 도형생성종류
# ----- 포탑 로컬 -----
V_TPREV    = "varTPrev34"      # 포탑: 이전방향
V_TDELTA   = "varTDelta35"     # 포탑: 회전델타
# ----- 클론 로컬 -----
V_BOLTISC  = "varBoltIsC36"    # 포탄: 복제됨
V_SHISC    = "varShIsC37"      # 도형: 복제됨
V_SHHP     = "varShHp38"       # 도형: 도형체력
V_SHXP     = "varShXp39"       # 도형: 도형경험치
V_SHHIT    = "varShHit40"      # 도형: 도형피격쿨
V_SHTYPE   = "varShType41"     # 도형: 도형종류
V_ENISC    = "varEnIsC42"      # 적탱크: 복제됨
V_ENHP     = "varEnHp43"       # 적탱크: 적체력
V_ENHIT    = "varEnHit44"      # 적탱크: 적피격쿨
# ----- 바 로컬 -----
V_HPCELL   = "varHpCell45"     # 체력바: 칸
V_XPCELL   = "varXpCell46"     # 경험치바: 칸
# ----- 카드 로컬 -----
V_PICK     = "varPick47"       # 진화선택 임시

# ----- 메시지 -----
BR_START   = "brStart01"
BR_FIRE    = "brFire02"
BR_LEVELUP = "brLevelUp03"
BR_EVODONE = "brEvoDone04"

# ============================================================
#  STAGE — 초기화 + 생존 감시/레벨업 상태머신
# ============================================================
def build_stage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 → 모든 변수 초기화 → 게임시작
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val); seq.append((sid, bs[sid]))
    # 튜닝 손잡이
    add_set("이동속도", V_MOVE, 4.5)
    add_set("발사쿨", V_FIRECD, 0.3)
    add_set("포탄속도", V_BOLTSPD, 10)
    add_set("공격력", V_ATK, 1)
    add_set("사각체력", V_SQHP, 2)
    add_set("삼각체력", V_TRHP, 4)
    add_set("적탱크체력", V_EHP, 3)
    add_set("적탱크속도", V_ESPD, 2)
    add_set("무적시간", V_INVSEC, 0.5)
    add_set("레벨업경험치", V_LVUP, 10)
    add_set("스폰간격", V_SPAWNGAP, 1.2)
    add_set("진화", V_EVO, 0)
    add_set("발사수", V_NBOLT, 1)
    add_set("산탄", V_SPREAD, 0)
    add_set("평행간격", V_PARGAP, 0)
    add_set("내체력최대", V_HPMAX, 5)
    add_set("목표도형수", V_TARGETSH, 7)
    add_set("적탱크경험치", V_ENXP, 2)
    # 내체력 = 내체력최대
    hpmax_r = vrep("내체력최대", V_HPMAX)
    set_hp = b_setvar(bs, "내체력", V_HP, hpmax_r); seq.append((set_hp, bs[set_hp]))
    # 진행 상태
    add_set("게임상태", V_STATE, 1)
    add_set("레벨", V_LEVEL, 1)
    add_set("경험치", V_EXP, 0)
    add_set("무적", V_INV, 0)
    add_set("도형수", V_SHAPES, 0)
    add_set("발사방향", V_FIREDIR, 90)
    add_set("발사X", V_FIREX, 0)
    add_set("발사Y", V_FIREY, 0)
    add_set("발사인덱스", V_FIREI, 0)
    add_set("적생성X", V_SPX, 0)
    add_set("적생성Y", V_SPY, 0)
    add_set("도형생성X", V_SHPX, 0)
    add_set("도형생성Y", V_SHPY, 0)
    add_set("도형생성종류", V_SHPTYPE, 1)
    w1 = b_wait(bs, 0.2); seq.append((w1, bs[w1]))
    bc = b_broadcast(bs, "게임시작", BR_START); seq.append((bc, bs[bc]))
    chain(seq)

    # (B) 무적 타이머는 피격 스크립트가 wait 로 처리 → 별도 없음

    # (C) 레벨업 / 게임오버 감시 forever
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=320, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # if (경험치 >= 레벨업경험치) and (게임상태=1)
    exp_r = vrep("경험치", V_EXP); lvup_r = vrep("레벨업경험치", V_LVUP)
    cond_exp_lt = cmp_op("operator_lt", exp_r, lvup_r)
    not_lt = gen(); bs[not_lt] = mk("operator_not", inputs={"OPERAND": [2, cond_exp_lt]})
    bs[cond_exp_lt]["parent"] = not_lt
    st_d1 = vrep("게임상태", V_STATE); cond_pl1 = cmp_op("operator_equals", st_d1, 1)
    cond_lvup = bool_op("operator_and", not_lt, cond_pl1)
    # 경험치 -= 레벨업경험치 ; 레벨 += 1 ; 레벨업경험치 += 5
    lvup_r2 = vrep("레벨업경험치", V_LVUP); neg_cost = op("operator_subtract", 0, lvup_r2)
    dec_exp = b_changevar(bs, "경험치", V_EXP, neg_cost)
    inc_lv = b_changevar(bs, "레벨", V_LEVEL, 1)
    inc_cost = b_changevar(bs, "레벨업경험치", V_LVUP, 5)
    # if 진화=0 → 게임상태=2 ; 레벨업(진화카드) ; else → 내체력 회복(+1, 상한)
    evo_r = vrep("진화", V_EVO); cond_noevo = cmp_op("operator_equals", evo_r, 0)
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_lv = b_broadcast(bs, "레벨업", BR_LEVELUP)
    chain([(set_st2, bs[set_st2]), (bc_lv, bs[bc_lv])])
    # else 회복
    heal = b_changevar(bs, "내체력", V_HP, 1)
    hp_r = vrep("내체력", V_HP); hpmax_r2 = vrep("내체력최대", V_HPMAX)
    cond_over = cmp_op("operator_gt", hp_r, hpmax_r2)
    hpmax_r3 = vrep("내체력최대", V_HPMAX)
    set_clamp = b_setvar(bs, "내체력", V_HP, hpmax_r3)
    if_clamp = b_if(bs, cond_over, set_clamp)
    chain([(heal, bs[heal]), (if_clamp, bs[if_clamp])])
    if_evo = b_ifelse(bs, cond_noevo, set_st2, heal)
    chain([(dec_exp, bs[dec_exp]), (inc_lv, bs[inc_lv]), (inc_cost, bs[inc_cost]),
           (if_evo, bs[if_evo])])
    if_lvup = b_if(bs, cond_lvup, dec_exp)
    # if (내체력 < 1) and (게임상태=1) → 게임상태=0
    hp_r2 = vrep("내체력", V_HP); cond_dead = cmp_op("operator_lt", hp_r2, 1)
    st_d2 = vrep("게임상태", V_STATE); cond_pl2 = cmp_op("operator_equals", st_d2, 1)
    cond_gameover = bool_op("operator_and", cond_dead, cond_pl2)
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    if_over = b_if(bs, cond_gameover, set_st0)
    wd = b_wait(bs, 0.03)
    chain([(if_lvup, bs[if_lvup]), (if_over, bs[if_over]), (wd, bs[wd])])
    fe = b_forever(bs, if_lvup)
    chain([(hd, bs[hd]), (fe, bs[fe])])

    add_comment(bs, comments, h,
        "⚙️ 개조 손잡이\n"
        "게임의 모든 숫자가 이 초록 깃발 묶음에 한글 변수로 모여 있어요. "
        "발사쿨·포탄속도·공격력·이동속도 같은 값을 바꾸면 손맛이 확 달라져요. "
        "먼저 '어떻게 될까?'를 예상하고 ▶ 로 확인해 보세요!",
        x=-360, y=-40, w=320, h=170)
    add_comment(bs, comments, if_lvup,
        "🆙 레벨업 → 첫 진화!\n"
        "경험치가 레벨업경험치를 넘으면 레벨이 오르고, 아직 진화 전(진화=0)이면 "
        "게임상태=2 로 멈추고 '레벨업'을 방송해 진화 카드를 띄워요. "
        "진화 뒤 레벨업은 체력을 조금 회복해 줘요.",
        x=560, y=-20, w=320, h=170)
    return bs, comments

# ============================================================
#  탱크 본체 (HULL) — 화살표 이동 + 접촉 피해
# ============================================================
def build_hull_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    g0 = b_gotoxy(bs, 0, 0)
    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (rs, bs[rs]), (pd, bs[pd]), (g0, bs[g0])])

    # (B) 화살표 이동 forever
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    inner = []
    move_r = vrep("이동속도", V_MOVE)
    cxr = gen(); bs[cxr] = mk("motion_changexby", inputs={"DX": slot(move_r)}); bs[move_r]["parent"] = cxr
    inner.append(b_if(bs, b_keypressed(bs, "right arrow"), cxr))
    move_l = vrep("이동속도", V_MOVE); neg_l = op("operator_subtract", 0, move_l)
    cxl = gen(); bs[cxl] = mk("motion_changexby", inputs={"DX": slot(neg_l)}); bs[neg_l]["parent"] = cxl
    inner.append(b_if(bs, b_keypressed(bs, "left arrow"), cxl))
    move_u = vrep("이동속도", V_MOVE)
    cyu = gen(); bs[cyu] = mk("motion_changeyby", inputs={"DY": slot(move_u)}); bs[move_u]["parent"] = cyu
    inner.append(b_if(bs, b_keypressed(bs, "up arrow"), cyu))
    move_d = vrep("이동속도", V_MOVE); neg_d = op("operator_subtract", 0, move_d)
    cyd = gen(); bs[cyd] = mk("motion_changeyby", inputs={"DY": slot(neg_d)}); bs[neg_d]["parent"] = cyd
    inner.append(b_if(bs, b_keypressed(bs, "down arrow"), cyd))
    def clamp(pos_op, set_op, cmp, limit):
        xp = gen(); bs[xp] = mk(pos_op)
        c = cmp_op(cmp, xp, limit)
        st = gen(); bs[st] = mk(set_op, inputs={("X" if set_op=="motion_setx" else "Y"): num(limit)})
        return b_if(bs, c, st)
    inner.append(clamp("motion_xposition", "motion_setx", "operator_gt", 228))
    inner.append(clamp("motion_xposition", "motion_setx", "operator_lt", -228))
    inner.append(clamp("motion_yposition", "motion_sety", "operator_gt", 168))
    inner.append(clamp("motion_yposition", "motion_sety", "operator_lt", -168))
    chain([(b, bs[b]) for b in inner])
    st_b = vrep("게임상태", V_STATE); cond_pl = cmp_op("operator_equals", st_b, 1)
    if_pl = b_if(bs, cond_pl, inner[0])
    wb = b_wait(bs, 0.016)
    chain([(if_pl, bs[if_pl]), (wb, bs[wb])])
    feb = b_forever(bs, if_pl)
    chain([(hb, bs[hb]), (feb, bs[feb])])

    # (C) 접촉 피해 forever (적탱크 닿으면 무적 아닐 때 내체력-1, 무적시간 초 무적)
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=320, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    tc = b_touching(bs, "적탱크")
    inv_r = vrep("무적", V_INV); cond_noinv = cmp_op("operator_equals", inv_r, 0)
    st_c = vrep("게임상태", V_STATE); cond_plc = cmp_op("operator_equals", st_c, 1)
    a1 = bool_op("operator_and", tc, cond_noinv)
    cond_hurt = bool_op("operator_and", a1, cond_plc)
    dec_hp = b_changevar(bs, "내체력", V_HP, -1)
    sh_hurt, sp_hurt = b_sound(bs, 0, "hurt")
    set_inv1 = b_setvar(bs, "무적", V_INV, 1)
    w_inv = b_wait_var(bs, V_INVSEC, "무적시간")
    set_inv0 = b_setvar(bs, "무적", V_INV, 0)
    chain([(dec_hp, bs[dec_hp]), (sh_hurt, bs[sh_hurt]), (sp_hurt, bs[sp_hurt]),
           (set_inv1, bs[set_inv1]), (w_inv, bs[w_inv]), (set_inv0, bs[set_inv0])])
    if_hurt = b_if(bs, cond_hurt, dec_hp)
    wc = b_wait(bs, 0.02)
    chain([(if_hurt, bs[if_hurt]), (wc, bs[wc])])
    fec = b_forever(bs, if_hurt)
    chain([(hc, bs[hc]), (fec, bs[fec])])

    add_comment(bs, comments, feb,
        "🕹️ 화살표로 몰아요\n"
        "누른 화살표만큼 x/y 좌표를 이동속도씩 더하고 빼요. 본체는 방향이 고정이고, "
        "조준은 위에 얹힌 포탑이 마우스를 따라 맡아요.",
        x=560, y=-40, w=300, h=130)
    return bs, comments

# ============================================================
#  포탑 (TURRET) — 마우스 조준(부드럽게) + 발사 + 진화 코스튬
# ============================================================
def build_turret_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    sw0 = b_switch_costume_name(bs, "기본")
    clr = gen(); bs[clr] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    show = gen(); bs[show] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (sz, bs[sz]), (rs, bs[rs]), (sw0, bs[sw0]), (clr, bs[clr]),
           (pd, bs[pd]), (show, bs[show]), (front, bs[front])])

    # (B) 본체 따라가기 + 마우스 조준(부드럽게) forever
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    bx = _of(bs, "탱크본체", "x position"); by = _of(bs, "탱크본체", "y position")
    g = b_gotoxy(bs, bx, by)
    # 이전방향 = direction
    dir1 = gen(); bs[dir1] = mk("motion_direction")
    set_prev = b_setvar(bs, "이전방향", V_TPREV, dir1)
    # point towards mouse (direction 이 목표로 스냅)
    pt = b_pointtowards(bs, "_mouse_")
    # 회전델타 = ((direction - 이전방향 + 540) mod 360) - 180
    dir2 = gen(); bs[dir2] = mk("motion_direction")
    prev_r = vrep("이전방향", V_TPREV)
    d_sub = op("operator_subtract", dir2, prev_r)
    d_add = op("operator_add", d_sub, 540)
    d_mod = op("operator_mod", d_add, 360)
    d_del = op("operator_subtract", d_mod, 180)
    set_del = b_setvar(bs, "회전델타", V_TDELTA, d_del)
    # point in direction (이전방향 + 회전델타*0.35)
    prev_r2 = vrep("이전방향", V_TPREV); del_r = vrep("회전델타", V_TDELTA)
    smooth = op("operator_multiply", del_r, 0.35)
    newdir = op("operator_add", prev_r2, smooth)
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": slot(newdir)})
    bs[newdir]["parent"] = pdir
    chain([(g, bs[g]), (set_prev, bs[set_prev]), (pt, bs[pt]), (set_del, bs[set_del]), (pdir, bs[pdir])])
    feb = b_forever(bs, g)
    chain([(hb, bs[hb]), (feb, bs[feb])])

    # (C) 마우스 홀드 발사 forever
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=320, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    md = gen(); bs[md] = mk("sensing_mousedown")
    st_c = vrep("게임상태", V_STATE); cond_plc = cmp_op("operator_equals", st_c, 1)
    cond_fire = bool_op("operator_and", md, cond_plc)
    # 발사방향 = direction ; 발사X = x ; 발사Y = y
    dir3 = gen(); bs[dir3] = mk("motion_direction")
    set_fdir = b_setvar(bs, "발사방향", V_FIREDIR, dir3)
    xp = gen(); bs[xp] = mk("motion_xposition"); set_fx = b_setvar(bs, "발사X", V_FIREX, xp)
    yp = gen(); bs[yp] = mk("motion_yposition"); set_fy = b_setvar(bs, "발사Y", V_FIREY, yp)
    sh_pew, sp_pew = b_sound(bs, 0, "pew")
    bc_fire = b_broadcast(bs, "발사", BR_FIRE)
    w_cd = b_wait_var(bs, V_FIRECD, "발사쿨")
    chain([(set_fdir, bs[set_fdir]), (set_fx, bs[set_fx]), (set_fy, bs[set_fy]),
           (sh_pew, bs[sh_pew]), (sp_pew, bs[sp_pew]), (bc_fire, bs[bc_fire]), (w_cd, bs[w_cd])])
    if_fire = b_if(bs, cond_fire, set_fdir)
    w_idle = b_wait(bs, 0.02)
    chain([(if_fire, bs[if_fire]), (w_idle, bs[w_idle])])
    fec = b_forever(bs, if_fire)
    chain([(hc, bs[hc]), (fec, bs[fec])])

    # (D) 진화완료 → 코스튬 교체 + 플래시
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=620, y=200,
        fields={"BROADCAST_OPTION": ["진화완료", BR_EVODONE]})
    # switch costume to (진화 + 1)
    evo_r = vrep("진화", V_EVO); idx = op("operator_add", evo_r, 1)
    sw = b_switch_costume_val(bs, idx)
    # 플래시: 밝기 100 → 0 로 서서히
    b100 = gen(); bs[b100] = mk("looks_seteffectto",
        inputs={"VALUE": num(90)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    dec_b = gen(); bs[dec_b] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(-15)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    w_f = b_wait(bs, 0.03)
    chain([(dec_b, bs[dec_b]), (w_f, bs[w_f])])
    rep_f = b_repeat(bs, 6, dec_b)
    b0 = gen(); bs[b0] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    chain([(hd, bs[hd]), (sw, bs[sw]), (b100, bs[b100]), (rep_f, bs[rep_f]), (b0, bs[b0])])

    add_comment(bs, comments, feb,
        "🎯 포탑이 마우스를 부드럽게 따라와요\n"
        "먼저 이전방향을 기억하고 마우스 쪽으로 스냅한 뒤, 그 차이(회전델타)의 35%만큼만 "
        "돌려요. 그래서 홱 꺾이지 않고 스르륵 돌아가요. 본체 위에도 매 틱 붙어 다녀요.",
        x=560, y=-60, w=330, h=160)
    add_comment(bs, comments, hd,
        "✨ 진화 = 포탑이 실제로 바뀐다!\n"
        "진화 카드를 고르면 진화 번호에 맞는 포탑 코스튬으로 교체하고 하얗게 번쩍여요. "
        "쌍포신·스나이퍼·머신건은 모양뿐 아니라 발사수·발사쿨·공격력·산탄까지 달라져요.",
        x=560, y=180, w=330, h=160)
    return bs, comments

# ============================================================
#  포탄 (BOLT) — 발사 시 발사수만큼 클론, 진화 패턴대로 비행
# ============================================================
def build_bolt_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    orig0 = b_setvar(bs, "복제됨", V_BOLTISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 발사 → 발사수만큼 클론 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    isc = vrep("복제됨", V_BOLTISC); cond_orig = cmp_op("operator_equals", isc, 0)
    set_i0 = b_setvar(bs, "발사인덱스", V_FIREI, 0)
    cm = gen(); bs[cm] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cm]})
    bs[cm]["parent"] = cc
    w_sp = b_wait(bs, 0.004)
    inc_i = b_changevar(bs, "발사인덱스", V_FIREI, 1)
    chain([(cc, bs[cc]), (w_sp, bs[w_sp]), (inc_i, bs[inc_i])])
    nb_r = vrep("발사수", V_NBOLT)
    rep = b_repeat(bs, nb_r, cc)
    chain([(set_i0, bs[set_i0]), (rep, bs[rep])])
    if_spawn = b_if(bs, cond_orig, set_i0)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 평행 오프셋 + 산탄 후 직진
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=430)
    set_isc1 = b_setvar(bs, "복제됨", V_BOLTISC, 1)
    fx_r = vrep("발사X", V_FIREX); fy_r = vrep("발사Y", V_FIREY)
    g = b_gotoxy(bs, fx_r, fy_r)
    # 평행 오프셋: point in direction (발사방향 + 90) ; move ((발사인덱스 - (발사수-1)/2) * 평행간격)
    fdir_r = vrep("발사방향", V_FIREDIR); perp = op("operator_add", fdir_r, 90)
    ppd = gen(); bs[ppd] = mk("motion_pointindirection", inputs={"DIRECTION": slot(perp)})
    bs[perp]["parent"] = ppd
    fi_r = vrep("발사인덱스", V_FIREI); nb_r2 = vrep("발사수", V_NBOLT)
    nb_m1 = op("operator_subtract", nb_r2, 1); half = op("operator_divide", nb_m1, 2)
    idx_off = op("operator_subtract", fi_r, half)
    pargap_r = vrep("평행간격", V_PARGAP)
    off_steps = op("operator_multiply", idx_off, pargap_r)
    mv_off = b_movesteps(bs, off_steps)
    # 실제 진행방향: point in direction (발사방향 + (pick random (-산탄)..산탄))
    fdir_r2 = vrep("발사방향", V_FIREDIR)
    sp_r = vrep("산탄", V_SPREAD); neg_sp = op("operator_subtract", 0, sp_r)
    sp_r2 = vrep("산탄", V_SPREAD)
    rnd = gen(); bs[rnd] = mk("operator_random",
        inputs={"FROM": slot(neg_sp), "TO": slot(sp_r2)})
    bs[neg_sp]["parent"] = rnd; bs[sp_r2]["parent"] = rnd
    travel = op("operator_add", fdir_r2, rnd)
    tpd = gen(); bs[tpd] = mk("motion_pointindirection", inputs={"DIRECTION": slot(travel)})
    bs[travel]["parent"] = tpd
    show = gen(); bs[show] = mk("looks_show")
    # repeat until (touching edge) or (게임상태=0) { move 포탄속도 ; if touching 도형 or 적탱크 {linger; delete} ; wait }
    mv = b_movesteps(bs, vrep("포탄속도", V_BOLTSPD))
    tc_sh = b_touching(bs, "도형"); tc_en = b_touching(bs, "적탱크")
    cond_hitany = bool_op("operator_or", tc_sh, tc_en)
    w_link = b_wait(bs, 0.05)
    del_hit = gen(); bs[del_hit] = mk("control_delete_this_clone")
    chain([(w_link, bs[w_link]), (del_hit, bs[del_hit])])
    if_hit = b_if(bs, cond_hitany, w_link)
    w_mv = b_wait(bs, 0.008)
    chain([(mv, bs[mv]), (if_hit, bs[if_hit]), (w_mv, bs[w_mv])])
    em = gen(); bs[em] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_edge = gen(); bs[tc_edge] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, em]})
    bs[em]["parent"] = tc_edge
    st_b = vrep("게임상태", V_STATE); cond_over = cmp_op("operator_equals", st_b, 0)
    cond_stop = bool_op("operator_or", tc_edge, cond_over)
    ru = b_repeat_until(bs, cond_stop, mv)
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (ppd, bs[ppd]),
           (mv_off, bs[mv_off]), (tpd, bs[tpd]), (show, bs[show]), (ru, bs[ru]), (del_end, bs[del_end])])

    add_comment(bs, comments, if_spawn,
        "🔫 진화가 발사 패턴을 바꾼다\n"
        "한 번 쏠 때 '발사수'만큼 포탄 클론을 만들어요. 쌍포신이면 2발이 평행간격만큼 "
        "옆으로 벌어져 2줄로 나가고, 머신건이면 산탄 각도만큼 흔들려 나가요. "
        "공격력·포탄속도·발사쿨도 진화별로 달라요.",
        x=480, y=-40, w=320, h=170)
    return bs, comments

# ============================================================
#  도형 (SHAPE) — 경험치 오브젝트, 필드 유지
# ============================================================
def build_shape_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_SHISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # 스폰 한 번 = 좌표/종류 랜덤 → 도형수+1 → 클론
    def make_spawn_seq():
        rx = gen(); bs[rx] = mk("operator_random", inputs={"FROM": num(-205), "TO": num(205)})
        set_sx = gen(); bs[set_sx] = mk("data_setvariableto",
            inputs={"VALUE": slot(rx)}, fields={"VARIABLE": ["도형생성X", V_SHPX]}); bs[rx]["parent"] = set_sx
        ry = gen(); bs[ry] = mk("operator_random", inputs={"FROM": num(-150), "TO": num(150)})
        set_sy = gen(); bs[set_sy] = mk("data_setvariableto",
            inputs={"VALUE": slot(ry)}, fields={"VARIABLE": ["도형생성Y", V_SHPY]}); bs[ry]["parent"] = set_sy
        rt = gen(); bs[rt] = mk("operator_random", inputs={"FROM": num(1), "TO": num(2)})
        set_st = gen(); bs[set_st] = mk("data_setvariableto",
            inputs={"VALUE": slot(rt)}, fields={"VARIABLE": ["도형생성종류", V_SHPTYPE]}); bs[rt]["parent"] = set_st
        inc = b_changevar(bs, "도형수", V_SHAPES, 1)
        cm = gen(); bs[cm] = mk("control_create_clone_of_menu",
            fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
        cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cm]})
        bs[cm]["parent"] = cc
        chain([(set_sx, bs[set_sx]), (set_sy, bs[set_sy]), (set_st, bs[set_st]),
               (inc, bs[inc]), (cc, bs[cc])])
        return set_sx, cc

    # (B) 게임시작 → 시작도형 채우고 필드 유지 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    isc = vrep("복제됨", V_SHISC); cond_orig = cmp_op("operator_equals", isc, 0)
    set0 = b_setvar(bs, "도형수", V_SHAPES, 0)
    sp1_head, sp1_tail = make_spawn_seq()
    w_i = b_wait(bs, 0.03)
    chain([(sp1_tail, bs[sp1_tail]), (w_i, bs[w_i])])
    tgt_r = vrep("목표도형수", V_TARGETSH)
    rep_init = b_repeat(bs, tgt_r, sp1_head)
    # forever 유지
    sp2_head, sp2_tail = make_spawn_seq()
    sh_r = vrep("도형수", V_SHAPES); tgt_r2 = vrep("목표도형수", V_TARGETSH)
    cond_low = cmp_op("operator_lt", sh_r, tgt_r2)
    st_b = vrep("게임상태", V_STATE); cond_plb = cmp_op("operator_equals", st_b, 1)
    cond_need = bool_op("operator_and", cond_low, cond_plb)
    if_need = b_if(bs, cond_need, sp2_head)
    w_keep = b_wait(bs, 0.35)
    chain([(if_need, bs[if_need]), (w_keep, bs[w_keep])])
    fe_keep = b_forever(bs, if_need)
    chain([(set0, bs[set0]), (rep_init, bs[rep_init]), (fe_keep, bs[fe_keep])])
    if_spawner = b_if(bs, cond_orig, set0)
    chain([(hb, bs[hb]), (if_spawner, bs[if_spawner])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_SHISC, 1)
    sptype_r = vrep("도형생성종류", V_SHPTYPE)
    set_type = b_setvar(bs, "도형종류", V_SHTYPE, sptype_r)
    set_hit0 = b_setvar(bs, "도형피격쿨", V_SHHIT, 0)
    # 종류별: 1=사각(사각체력, 경험치1) 2=삼각(삼각체력, 경험치3)
    type_r = vrep("도형종류", V_SHTYPE); cond_sq = cmp_op("operator_equals", type_r, 1)
    sw_sq = b_switch_costume_name(bs, "사각")
    set_hp_sq = b_setvar(bs, "도형체력", V_SHHP, vrep("사각체력", V_SQHP))
    set_xp_sq = b_setvar(bs, "도형경험치", V_SHXP, 1)
    sz_sq = gen(); bs[sz_sq] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    chain([(sw_sq, bs[sw_sq]), (set_hp_sq, bs[set_hp_sq]), (set_xp_sq, bs[set_xp_sq]), (sz_sq, bs[sz_sq])])
    sw_tr = b_switch_costume_name(bs, "삼각")
    set_hp_tr = b_setvar(bs, "도형체력", V_SHHP, vrep("삼각체력", V_TRHP))
    set_xp_tr = b_setvar(bs, "도형경험치", V_SHXP, 3)
    sz_tr = gen(); bs[sz_tr] = mk("looks_setsizeto", inputs={"SIZE": num(95)})
    chain([(sw_tr, bs[sw_tr]), (set_hp_tr, bs[set_hp_tr]), (set_xp_tr, bs[set_xp_tr]), (sz_tr, bs[sz_tr])])
    if_type = b_ifelse(bs, cond_sq, sw_sq, sw_tr)
    shx_r = vrep("도형생성X", V_SHPX); shy_r = vrep("도형생성Y", V_SHPY)
    g = b_gotoxy(bs, shx_r, shy_r)
    clrg = gen(); bs[clrg] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(set_isc1, bs[set_isc1]), (set_type, bs[set_type]), (set_hit0, bs[set_hit0]),
           (if_type, bs[if_type]), (g, bs[g]), (clrg, bs[clrg]), (show, bs[show])])
    # forever
    body = []
    st1 = vrep("게임상태", V_STATE); cond_go = cmp_op("operator_equals", st1, 0)
    dec_go = b_changevar(bs, "도형수", V_SHAPES, -1)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    chain([(dec_go, bs[dec_go]), (del_go, bs[del_go])])
    if_go = b_if(bs, cond_go, dec_go)
    body.append(if_go)
    # 피격
    tc_b = b_touching(bs, "포탄")
    hit_r = vrep("도형피격쿨", V_SHHIT); cond_hit0 = cmp_op("operator_equals", hit_r, 0)
    cond_struck = bool_op("operator_and", tc_b, cond_hit0)
    atk_r = vrep("공격력", V_ATK); neg_atk = op("operator_subtract", 0, atk_r)
    dec_hp = b_changevar(bs, "도형체력", V_SHHP, neg_atk)
    set_hit = b_setvar(bs, "도형피격쿨", V_SHHIT, 5)
    sh_cr, sp_cr = b_sound(bs, 30, "crack")
    # if 도형체력<1 → 경험치 += 도형경험치 ; 도형수-1 ; pop ; delete
    hp_r = vrep("도형체력", V_SHHP); cond_dead = cmp_op("operator_lt", hp_r, 1)
    add_exp = b_changevar(bs, "경험치", V_EXP, vrep("도형경험치", V_SHXP))
    dec_cnt = b_changevar(bs, "도형수", V_SHAPES, -1)
    grow = gen(); bs[grow] = mk("looks_changesizeby", inputs={"CHANGE": num(10)})
    fade = gen(); bs[fade] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(28)}, fields={"EFFECT": ["GHOST", None]})
    w_pop = b_wait(bs, 0.015)
    chain([(grow, bs[grow]), (fade, bs[fade]), (w_pop, bs[w_pop])])
    rep_pop = b_repeat(bs, 4, grow)
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")
    chain([(add_exp, bs[add_exp]), (dec_cnt, bs[dec_cnt]), (rep_pop, bs[rep_pop]), (del_k, bs[del_k])])
    if_dead = b_if(bs, cond_dead, add_exp)
    chain([(dec_hp, bs[dec_hp]), (set_hit, bs[set_hit]), (sh_cr, bs[sh_cr]), (sp_cr, bs[sp_cr]),
           (if_dead, bs[if_dead])])
    if_struck = b_if(bs, cond_struck, dec_hp)
    body.append(if_struck)
    # 피격쿨 감소
    hit_r2 = vrep("도형피격쿨", V_SHHIT); cond_hitpos = cmp_op("operator_gt", hit_r2, 0)
    dec_hit = b_changevar(bs, "도형피격쿨", V_SHHIT, -1)
    if_hitcd = b_if(bs, cond_hitpos, dec_hit)
    body.append(if_hitcd)
    w_body = b_wait(bs, 0.02)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    chain([(show, bs[show]), (fe_body, bs[fe_body])])
    return bs, comments

# ============================================================
#  적 탱크 (ENEMY) — 가장자리 스폰 + 추격 + 접촉 피해
# ============================================================
def build_enemy_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    orig0 = b_setvar(bs, "복제됨", V_ENISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 시간 기반 스폰 forever (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    isc = vrep("복제됨", V_ENISC); cond_orig = cmp_op("operator_equals", isc, 0)
    # 가장자리 좌표 (상/하 or 좌/우)
    coin = gen(); bs[coin] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_h = cmp_op("operator_equals", coin, 0)
    rxh = gen(); bs[rxh] = mk("operator_random", inputs={"FROM": num(-225), "TO": num(225)})
    set_sxh = gen(); bs[set_sxh] = mk("data_setvariableto",
        inputs={"VALUE": slot(rxh)}, fields={"VARIABLE": ["적생성X", V_SPX]}); bs[rxh]["parent"] = set_sxh
    coin2 = gen(); bs[coin2] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_top = cmp_op("operator_equals", coin2, 0)
    set_syt = b_setvar(bs, "적생성Y", V_SPY, 172)
    set_syb = b_setvar(bs, "적생성Y", V_SPY, -172)
    if_tb = b_ifelse(bs, cond_top, set_syt, set_syb)
    chain([(set_sxh, bs[set_sxh]), (if_tb, bs[if_tb])])
    ryv = gen(); bs[ryv] = mk("operator_random", inputs={"FROM": num(-165), "TO": num(165)})
    set_syv = gen(); bs[set_syv] = mk("data_setvariableto",
        inputs={"VALUE": slot(ryv)}, fields={"VARIABLE": ["적생성Y", V_SPY]}); bs[ryv]["parent"] = set_syv
    coin3 = gen(); bs[coin3] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_left = cmp_op("operator_equals", coin3, 0)
    set_sxl = b_setvar(bs, "적생성X", V_SPX, -232)
    set_sxr = b_setvar(bs, "적생성X", V_SPX, 232)
    if_lr = b_ifelse(bs, cond_left, set_sxl, set_sxr)
    chain([(set_syv, bs[set_syv]), (if_lr, bs[if_lr])])
    if_edge = b_ifelse(bs, cond_h, set_sxh, set_syv)
    cm = gen(); bs[cm] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cm]})
    bs[cm]["parent"] = cc
    chain([(if_edge, bs[if_edge]), (cc, bs[cc])])
    st_b = vrep("게임상태", V_STATE); cond_plb = cmp_op("operator_equals", st_b, 1)
    if_plb = b_if(bs, cond_plb, if_edge)
    w_gap = b_wait_var(bs, V_SPAWNGAP, "스폰간격")
    chain([(if_plb, bs[if_plb]), (w_gap, bs[w_gap])])
    fe_sp = b_forever(bs, if_plb)
    if_spawner = b_if(bs, cond_orig, fe_sp)
    chain([(hb, bs[hb]), (if_spawner, bs[if_spawner])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=460)
    set_isc1 = b_setvar(bs, "복제됨", V_ENISC, 1)
    set_ehp = b_setvar(bs, "적체력", V_ENHP, vrep("적탱크체력", V_EHP))
    set_ehit0 = b_setvar(bs, "적피격쿨", V_ENHIT, 0)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    spx_r = vrep("적생성X", V_SPX); spy_r = vrep("적생성Y", V_SPY)
    g = b_gotoxy(bs, spx_r, spy_r)
    clrg = gen(); bs[clrg] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(set_isc1, bs[set_isc1]), (set_ehp, bs[set_ehp]), (set_ehit0, bs[set_ehit0]),
           (sz, bs[sz]), (g, bs[g]), (clrg, bs[clrg]), (show, bs[show])])
    body = []
    st1 = vrep("게임상태", V_STATE); cond_go = cmp_op("operator_equals", st1, 0)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    if_go = b_if(bs, cond_go, del_go)
    body.append(if_go)
    # 추격
    pt = b_pointtowards(bs, "탱크본체")
    mv = b_movesteps(bs, vrep("적탱크속도", V_ESPD))
    chain([(pt, bs[pt]), (mv, bs[mv])])
    st2 = vrep("게임상태", V_STATE); cond_pl2 = cmp_op("operator_equals", st2, 1)
    if_chase = b_if(bs, cond_pl2, pt)
    body.append(if_chase)
    # 포탄 피격
    tc_b = b_touching(bs, "포탄")
    hit_r = vrep("적피격쿨", V_ENHIT); cond_hit0 = cmp_op("operator_equals", hit_r, 0)
    cond_struck = bool_op("operator_and", tc_b, cond_hit0)
    atk_r = vrep("공격력", V_ATK); neg_atk = op("operator_subtract", 0, atk_r)
    dec_hp = b_changevar(bs, "적체력", V_ENHP, neg_atk)
    set_hit = b_setvar(bs, "적피격쿨", V_ENHIT, 5)
    sh_cr, sp_cr = b_sound(bs, 0, "crack")
    ehp_r = vrep("적체력", V_ENHP); cond_dead = cmp_op("operator_lt", ehp_r, 1)
    add_exp = b_changevar(bs, "경험치", V_EXP, vrep("적탱크경험치", V_ENXP))
    grow = gen(); bs[grow] = mk("looks_changesizeby", inputs={"CHANGE": num(12)})
    fade = gen(); bs[fade] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(28)}, fields={"EFFECT": ["GHOST", None]})
    w_pop = b_wait(bs, 0.015)
    chain([(grow, bs[grow]), (fade, bs[fade]), (w_pop, bs[w_pop])])
    rep_pop = b_repeat(bs, 4, grow)
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")
    chain([(add_exp, bs[add_exp]), (rep_pop, bs[rep_pop]), (del_k, bs[del_k])])
    if_dead = b_if(bs, cond_dead, add_exp)
    chain([(dec_hp, bs[dec_hp]), (set_hit, bs[set_hit]), (sh_cr, bs[sh_cr]), (sp_cr, bs[sp_cr]),
           (if_dead, bs[if_dead])])
    if_struck = b_if(bs, cond_struck, dec_hp)
    body.append(if_struck)
    hit_r2 = vrep("적피격쿨", V_ENHIT); cond_hitpos = cmp_op("operator_gt", hit_r2, 0)
    dec_hit = b_changevar(bs, "적피격쿨", V_ENHIT, -1)
    if_hitcd = b_if(bs, cond_hitpos, dec_hit)
    body.append(if_hitcd)
    w_body = b_wait(bs, 0.02)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1])])
    chain([(show, bs[show]), (fe_body, bs[fe_body])])

    add_comment(bs, comments, fe_sp,
        "👾 적 탱크는 가장자리에서 스폰돼 추격해요\n"
        "스폰간격마다 화면 네 변 중 한 곳에서 나타나 탱크 본체 쪽으로 point&move 로 다가와요. "
        "닿으면 접촉 피해를 주고, 포탄을 적탱크체력만큼 맞으면 터져요.",
        x=560, y=-40, w=320, h=150)
    return bs, comments

# ============================================================
#  진화 카드 (CARD) — 레벨업 시 3택, 클릭 폴링 + 디바운스
# ============================================================
def build_card_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = b_gotoxy(bs, 0, 0)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    # (B) 레벨업 → show → (키 1/2/3 or 클릭 3구간) 폴링 → 진화 적용 → 디바운스
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["레벨업", BR_LEVELUP]})
    show = gen(); bs[show] = mk("looks_show")
    set_pick0 = b_setvar(bs, "진화선택", V_PICK, 0)
    # 폴링 루프: repeat until 진화선택>0
    #   choice1 = key1 OR (mousedown and mousex < -78)
    #   choice2 = key2 OR (mousedown and -78<=mousex<=78)
    #   choice3 = key3 OR (mousedown and mousex > 78)
    def zone(keyname, lo, hi):
        # (mousedown) and (lo <= mousex) and (mousex <= hi) ; lo/hi None = 무한
        md = gen(); bs[md] = mk("sensing_mousedown")
        conds = [md]
        if lo is not None:
            mx = gen(); bs[mx] = mk("sensing_mousex")
            conds.append(cmp_op("operator_gt", mx, lo))
        if hi is not None:
            mx2 = gen(); bs[mx2] = mk("sensing_mousex")
            conds.append(cmp_op("operator_lt", mx2, hi))
        acc = conds[0]
        for c in conds[1:]:
            acc = bool_op("operator_and", acc, c)
        key = b_keypressed(bs, keyname)
        return bool_op("operator_or", key, acc)
    c1 = zone("1", None, -78)
    set_p1 = b_setvar(bs, "진화선택", V_PICK, 1)
    if_c1 = b_if(bs, c1, set_p1)
    c2 = zone("2", -78, 78)
    set_p2 = b_setvar(bs, "진화선택", V_PICK, 2)
    if_c2 = b_if(bs, c2, set_p2)
    c3 = zone("3", 78, None)
    set_p3 = b_setvar(bs, "진화선택", V_PICK, 3)
    if_c3 = b_if(bs, c3, set_p3)
    w_poll = b_wait(bs, 0.02)
    chain([(if_c1, bs[if_c1]), (if_c2, bs[if_c2]), (if_c3, bs[if_c3]), (w_poll, bs[w_poll])])
    pick_r = vrep("진화선택", V_PICK); cond_done = cmp_op("operator_gt", pick_r, 0)
    rep_poll = b_repeat_until(bs, cond_done, if_c1)
    # 진화 = 진화선택
    pick_r2 = vrep("진화선택", V_PICK)
    set_evo = b_setvar(bs, "진화", V_EVO, pick_r2)
    # 진화별 발사 파라미터 적용
    def apply_evo(pick, nb, cd, atk, spd, spread, pargap):
        cond = cmp_op("operator_equals", vrep("진화선택", V_PICK), pick)
        s1 = b_setvar(bs, "발사수", V_NBOLT, nb)
        s2 = b_setvar(bs, "발사쿨", V_FIRECD, cd)
        s3 = b_setvar(bs, "공격력", V_ATK, atk)
        s4 = b_setvar(bs, "포탄속도", V_BOLTSPD, spd)
        s5 = b_setvar(bs, "산탄", V_SPREAD, spread)
        s6 = b_setvar(bs, "평행간격", V_PARGAP, pargap)
        chain([(s1, bs[s1]), (s2, bs[s2]), (s3, bs[s3]), (s4, bs[s4]), (s5, bs[s5]), (s6, bs[s6])])
        return b_if(bs, cond, s1)
    if_e1 = apply_evo(1, 2, 0.3, 1, 10, 0, 20)   # 쌍포신
    if_e2 = apply_evo(2, 1, 0.6, 3, 15, 0, 0)    # 스나이퍼
    if_e3 = apply_evo(3, 1, 0.12, 1, 10, 13, 0)  # 머신건
    sh_ev, sp_ev = b_sound(bs, 60, "crack")      # 진화 순간 강조음
    bc_evo = b_broadcast(bs, "진화완료", BR_EVODONE)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    # 디바운스: 마우스 뗄 때까지 대기 후 상태 복귀
    md2 = gen(); bs[md2] = mk("sensing_mousedown")
    notmd = gen(); bs[notmd] = mk("operator_not", inputs={"OPERAND": [2, md2]}); bs[md2]["parent"] = notmd
    waitnot = b_wait_until(bs, notmd)
    w_db = b_wait(bs, 0.15)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    chain([(hb, bs[hb]), (show, bs[show]), (set_pick0, bs[set_pick0]), (rep_poll, bs[rep_poll]),
           (set_evo, bs[set_evo]), (if_e1, bs[if_e1]), (if_e2, bs[if_e2]), (if_e3, bs[if_e3]),
           (sh_ev, bs[sh_ev]), (sp_ev, bs[sp_ev]), (bc_evo, bs[bc_evo]), (hi2, bs[hi2]),
           (waitnot, bs[waitnot]), (w_db, bs[w_db]), (set_st1, bs[set_st1])])

    add_comment(bs, comments, rep_poll,
        "🃏 진화 택1 — 클릭 폴링 + 디바운스\n"
        "카드가 뜨면 세 칸 중 하나를 마우스로 누르거나 1/2/3 키를 눌러요. 누른 가로 위치로 "
        "칸을 나눠 진화를 정하고, 마우스를 뗄 때까지 기다렸다가(디바운스) 전투를 재개해 "
        "'한 번 누름 = 한 번 선택'이 되게 해요.",
        x=480, y=-40, w=330, h=170)
    return bs, comments

# ============================================================
#  체력바 / 경험치바 (11단 코스튬 fill)
# ============================================================
def build_bar_blocks(cell_name, cell_vid, cur_name, cur_vid, max_name, max_vid):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenbroadcastreceived", top=True, x=20, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    # 칸 = round( (현재/최대) * 10 )
    cur_r = vrep(cur_name, cur_vid); max_r = vrep(max_name, max_vid)
    ratio = op("operator_divide", cur_r, max_r)
    mul = op("operator_multiply", ratio, 10)
    rnd = gen(); bs[rnd] = mk("operator_mathop",
        inputs={"NUM": slot(mul)}, fields={"OPERATOR": ["round", None]}); bs[mul]["parent"] = rnd
    set_cell = b_setvar(bs, cell_name, cell_vid, rnd)
    # clamp 0..10
    cell_r = vrep(cell_name, cell_vid); cond_neg = cmp_op("operator_lt", cell_r, 0)
    set0 = b_setvar(bs, cell_name, cell_vid, 0)
    if_neg = b_if(bs, cond_neg, set0)
    cell_r2 = vrep(cell_name, cell_vid); cond_big = cmp_op("operator_gt", cell_r2, 10)
    set10 = b_setvar(bs, cell_name, cell_vid, 10)
    if_big = b_if(bs, cond_big, set10)
    # switch costume to (칸 + 1)
    cell_r3 = vrep(cell_name, cell_vid); idx = op("operator_add", cell_r3, 1)
    sw = b_switch_costume_val(bs, idx)
    w = b_wait(bs, 0.05)
    chain([(set_cell, bs[set_cell]), (if_neg, bs[if_neg]), (if_big, bs[if_big]), (sw, bs[sw]), (w, bs[w])])
    fe = b_forever(bs, set_cell)
    chain([(h, bs[h]), (front, bs[front]), (fe, bs[fe])])
    return bs, comments

# ============================================================
#  ASSEMBLE
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    def save_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f: f.write(svg)
        return m
    bg_md5    = save_svg(BG_SVG)
    hull_md5  = save_svg(HULL_SVG)
    tb_md5    = save_svg(TUR_BASE)
    td_md5    = save_svg(TUR_DUAL)
    ts_md5    = save_svg(TUR_SNIPE)
    tm_md5    = save_svg(TUR_MG)
    bolt_md5  = save_svg(BOLT_SVG)
    sq_md5    = save_svg(SQUARE_SVG)
    tri_md5   = save_svg(TRI_SVG)
    en_md5    = save_svg(ENEMY_SVG)
    card_md5  = save_svg(CARD_SVG)
    hp_md5    = [save_svg(s) for s in HP_SVGS]
    xp_md5    = [save_svg(s) for s in XP_SVGS]

    def save_wav(samples):
        b = _wav_bytes(samples); m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    pew_md5, pew_n     = save_wav(synth_pew())
    crack_md5, crack_n = save_wav(synth_crack())
    hurt_md5, hurt_n   = save_wav(synth_hurt())

    def snd(name, m, n):
        return {"name": name, "assetId": m, "dataFormat": "wav", "format": "",
                "rate": SND_RATE, "sampleCount": n, "md5ext": f"{m}.wav"}
    pew   = lambda: snd("pew", pew_md5, pew_n)
    crack = lambda: snd("crack", crack_md5, crack_n)
    hurt  = lambda: snd("hurt", hurt_md5, hurt_n)

    stage_b,  stage_c  = build_stage_blocks()
    hull_b,   hull_c   = build_hull_blocks()
    turret_b, turret_c = build_turret_blocks()
    bolt_b,   bolt_c   = build_bolt_blocks()
    shape_b,  shape_c  = build_shape_blocks()
    enemy_b,  enemy_c  = build_enemy_blocks()
    card_b,   card_c   = build_card_blocks()
    hpbar_b,  hpbar_c  = build_bar_blocks("칸", V_HPCELL, "내체력", V_HP, "내체력최대", V_HPMAX)
    xpbar_b,  xpbar_c  = build_bar_blocks("칸", V_XPCELL, "경험치", V_EXP, "레벨업경험치", V_LVUP)

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_MOVE: ["이동속도", 4.5], V_FIRECD: ["발사쿨", 0.3], V_BOLTSPD: ["포탄속도", 10],
            V_ATK: ["공격력", 1], V_SQHP: ["사각체력", 2], V_TRHP: ["삼각체력", 4],
            V_EHP: ["적탱크체력", 3], V_ESPD: ["적탱크속도", 2], V_HP: ["내체력", 5],
            V_INVSEC: ["무적시간", 0.5], V_LVUP: ["레벨업경험치", 10], V_SPAWNGAP: ["스폰간격", 1.2],
            V_EVO: ["진화", 0], V_NBOLT: ["발사수", 1], V_SPREAD: ["산탄", 0], V_PARGAP: ["평행간격", 0],
            V_HPMAX: ["내체력최대", 5], V_TARGETSH: ["목표도형수", 7], V_ENXP: ["적탱크경험치", 2],
            V_STATE: ["게임상태", 1], V_LEVEL: ["레벨", 1], V_EXP: ["경험치", 0], V_INV: ["무적", 0],
            V_SHAPES: ["도형수", 0], V_FIREDIR: ["발사방향", 90], V_FIREX: ["발사X", 0],
            V_FIREY: ["발사Y", 0], V_FIREI: ["발사인덱스", 0], V_SPX: ["적생성X", 0], V_SPY: ["적생성Y", 0],
            V_SHPX: ["도형생성X", 0], V_SHPY: ["도형생성Y", 0], V_SHPTYPE: ["도형생성종류", 1],
        },
        "lists": {}, "broadcasts": {
            BR_START: "게임시작", BR_FIRE: "발사", BR_LEVELUP: "레벨업", BR_EVODONE: "진화완료",
        },
        "blocks": stage_b, "comments": stage_c, "currentCostume": 0,
        "costumes": [{"name": "필드", "dataFormat": "svg", "assetId": bg_md5,
                      "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180}],
        "sounds": [], "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }
    hull = {
        "isStage": False, "name": "탱크본체",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hull_b, "comments": hull_c, "currentCostume": 0,
        "costumes": [{"name": "hull", "bitmapResolution": 1, "dataFormat": "svg",
                      "assetId": hull_md5, "md5ext": f"{hull_md5}.svg",
                      "rotationCenterX": 32, "rotationCenterY": 32}],
        "sounds": [hurt()], "volume": 100, "layerOrder": 4, "visible": True,
        "x": 0, "y": 0, "size": 90, "direction": 90, "draggable": False, "rotationStyle": "don't rotate"
    }
    turret = {
        "isStage": False, "name": "포탑",
        "variables": {V_TPREV: ["이전방향", 90], V_TDELTA: ["회전델타", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": turret_b, "comments": turret_c, "currentCostume": 0,
        "costumes": [
            {"name": "기본", "bitmapResolution": 1, "dataFormat": "svg", "assetId": tb_md5,
             "md5ext": f"{tb_md5}.svg", "rotationCenterX": 60, "rotationCenterY": 60},
            {"name": "쌍포신", "bitmapResolution": 1, "dataFormat": "svg", "assetId": td_md5,
             "md5ext": f"{td_md5}.svg", "rotationCenterX": 60, "rotationCenterY": 60},
            {"name": "스나이퍼", "bitmapResolution": 1, "dataFormat": "svg", "assetId": ts_md5,
             "md5ext": f"{ts_md5}.svg", "rotationCenterX": 60, "rotationCenterY": 60},
            {"name": "머신건", "bitmapResolution": 1, "dataFormat": "svg", "assetId": tm_md5,
             "md5ext": f"{tm_md5}.svg", "rotationCenterX": 60, "rotationCenterY": 60},
        ],
        "sounds": [pew(), crack()], "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": 0, "size": 85, "direction": 90, "draggable": False, "rotationStyle": "all around"
    }
    bolt = {
        "isStage": False, "name": "포탄",
        "variables": {V_BOLTISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": bolt_b, "comments": bolt_c, "currentCostume": 0,
        "costumes": [{"name": "bolt", "bitmapResolution": 1, "dataFormat": "svg",
                      "assetId": bolt_md5, "md5ext": f"{bolt_md5}.svg",
                      "rotationCenterX": 12, "rotationCenterY": 12}],
        "sounds": [], "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 90, "direction": 90, "draggable": False, "rotationStyle": "all around"
    }
    shape = {
        "isStage": False, "name": "도형",
        "variables": {V_SHISC: ["복제됨", 0], V_SHHP: ["도형체력", 2], V_SHXP: ["도형경험치", 1],
                      V_SHHIT: ["도형피격쿨", 0], V_SHTYPE: ["도형종류", 1]},
        "lists": {}, "broadcasts": {},
        "blocks": shape_b, "comments": shape_c, "currentCostume": 0,
        "costumes": [
            {"name": "사각", "bitmapResolution": 1, "dataFormat": "svg", "assetId": sq_md5,
             "md5ext": f"{sq_md5}.svg", "rotationCenterX": 24, "rotationCenterY": 24},
            {"name": "삼각", "bitmapResolution": 1, "dataFormat": "svg", "assetId": tri_md5,
             "md5ext": f"{tri_md5}.svg", "rotationCenterX": 24, "rotationCenterY": 24},
        ],
        "sounds": [crack()], "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 85, "direction": 90, "draggable": False, "rotationStyle": "don't rotate"
    }
    enemy = {
        "isStage": False, "name": "적탱크",
        "variables": {V_ENISC: ["복제됨", 0], V_ENHP: ["적체력", 3], V_ENHIT: ["적피격쿨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_b, "comments": enemy_c, "currentCostume": 0,
        "costumes": [{"name": "적", "bitmapResolution": 1, "dataFormat": "svg", "assetId": en_md5,
                      "md5ext": f"{en_md5}.svg", "rotationCenterX": 24, "rotationCenterY": 24}],
        "sounds": [crack()], "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 90, "direction": 90, "draggable": False, "rotationStyle": "all around"
    }
    card = {
        "isStage": False, "name": "진화카드",
        "variables": {V_PICK: ["진화선택", 0]}, "lists": {}, "broadcasts": {},
        "blocks": card_b, "comments": card_c, "currentCostume": 0,
        "costumes": [{"name": "카드", "bitmapResolution": 1, "dataFormat": "svg", "assetId": card_md5,
                      "md5ext": f"{card_md5}.svg", "rotationCenterX": 230, "rotationCenterY": 110}],
        "sounds": [crack()], "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90, "draggable": False, "rotationStyle": "all around"
    }
    hpbar = {
        "isStage": False, "name": "체력바",
        "variables": {V_HPCELL: ["칸", 10]}, "lists": {}, "broadcasts": {},
        "blocks": hpbar_b, "comments": hpbar_c, "currentCostume": 10,
        "costumes": [{"name": str(i), "bitmapResolution": 1, "dataFormat": "svg", "assetId": hp_md5[i],
                      "md5ext": f"{hp_md5[i]}.svg", "rotationCenterX": 88, "rotationCenterY": 10}
                     for i in range(11)],
        "sounds": [], "volume": 100, "layerOrder": 6, "visible": True,
        "x": -148, "y": 165, "size": 100, "direction": 90, "draggable": False, "rotationStyle": "don't rotate"
    }
    xpbar = {
        "isStage": False, "name": "경험치바",
        "variables": {V_XPCELL: ["칸", 0]}, "lists": {}, "broadcasts": {},
        "blocks": xpbar_b, "comments": xpbar_c, "currentCostume": 0,
        "costumes": [{"name": str(i), "bitmapResolution": 1, "dataFormat": "svg", "assetId": xp_md5[i],
                      "md5ext": f"{xp_md5[i]}.svg", "rotationCenterX": 88, "rotationCenterY": 10}
                     for i in range(11)],
        "sounds": [], "volume": 100, "layerOrder": 7, "visible": True,
        "x": -148, "y": 142, "size": 100, "direction": 90, "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_LEVEL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "레벨"}, "spriteName": None, "value": 1,
         "width": 0, "height": 0, "x": 5, "y": 5, "visible": True,
         "sliderMin": 0, "sliderMax": 50, "isDiscrete": True},
        {"id": V_EVO, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "진화"}, "spriteName": None, "value": 0,
         "width": 0, "height": 0, "x": 5, "y": 35, "visible": True,
         "sliderMin": 0, "sliderMax": 3, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, hull, turret, bolt, shape, enemy, card, hpbar, xpbar],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "evo-tank-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)
    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)
    total = 0
    print(f"wrote {OUTPUT}")
    for nm, b in [("stage", stage_b), ("hull", hull_b), ("turret", turret_b), ("bolt", bolt_b),
                  ("shape", shape_b), ("enemy", enemy_b), ("card", card_b),
                  ("hpbar", hpbar_b), ("xpbar", xpbar_b)]:
        total += len(b); print(f"  {nm:8s}: {len(b)} blocks")
    print(f"  TOTAL   : {total} blocks")

if __name__ == "__main__":
    main()
