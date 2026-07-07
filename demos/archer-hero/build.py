#!/usr/bin/env python3
"""아처 용사 (archer-hero) — 데모: "멈추면 쏜다" 탑뷰 슈터.

Archero(궁수의 전설)형 핵심 루프만 검증하는 데모 빌드(풀게임 아님).
화살표로 8방향 이동하는 동안엔 발사가 멈추고, 손을 떼고 '멈추면' 0.25초 안에
가장 가까운 적에게 화살을 자동 연사한다. "지금 피할까, 서서 쏠까"의 리듬이 재미.
멈추면 활을 겨누는 자세(코스튬 전환) + 적을 향해 몸을 돌리는(조준) 시각 피드백으로
"왜 안 쏘지?" 혼란을 없앤다.

웨이브 3개. 웨이브 N = 적 (웨이브기본수 + 2N) 마리 → 전멸 시 강화 택1(공격력/연사속도/
이동속도, 마우스 클릭) → 다음 웨이브 적이 적성장배율^(N-1)로 강해진다.

베이스: games/magic-survivor/build.py (탑뷰 클론 스포너 · 자동조준 최솟값 리덕션
        핸드셰이크 · 무적/피격 · 폭발 연출 · 한글 튜닝 변수).
효과음 3종은 struct 로 즉석 합성(twang 활시위 / pop 처치 / hurt 피격).
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "아처_용사.sb3")

# ============================================================
#  효과음 합성 (전용 사운드 3종) — 결정적 생성
# ============================================================
SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_twang(rate=SND_RATE):
    """활시위 — 짧게 튕기는 현(퉁). 살짝 위로 벤딩 후 감쇠."""
    N = int(rate * 0.20); out = []
    f0 = 330
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 11)
        f = f0 * (1 + 0.35 * math.exp(-t * 32))
        s = math.sin(2 * math.pi * f * t) + 0.4 * math.sin(2 * math.pi * 2 * f * t) * math.exp(-t * 20)
        out.append(0.5 * s * env)
    return out

def synth_pop(rate=SND_RATE):
    """처치 — 밝고 짧은 팝(뿅). 위→아래 스윕."""
    N = int(rate * 0.13); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 20)
        f = 480 + 760 * math.exp(-t * 30)
        s = math.sin(2 * math.pi * f * t)
        out.append(0.5 * s * env)
    return out

def synth_hurt(rate=SND_RATE):
    """피격 — 낮게 우웅 떨어지는 버즈(아픔)."""
    N = int(rate * 0.22); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 9)
        f = 70 + 200 * math.exp(-t * 6)
        base = math.sin(2 * math.pi * f * t)
        s = base + 0.3 * (1 if base > 0 else -1)     # 살짝 각진 버즈
        out.append(0.4 * s * env)
    return out

# ============================================================
#  SVG assets
# ============================================================
def _star_pts(cx, cy, R, r, n, rot=0.0):
    pts = []
    for i in range(2 * n):
        rad = R if i % 2 == 0 else r
        ang = math.pi / n * i + rot
        pts.append(f"{cx + rad*math.cos(ang):.1f},{cy + rad*math.sin(ang):.1f}")
    return " ".join(pts)

# -------- 배경: 던전 아레나 (돌바닥) --------
random.seed(11)
_tiles = []
for ty in range(0, 360, 40):
    for tx in range(0, 480, 40):
        shade = random.choice(["#4A4036", "#54493C", "#433A31"])
        _tiles.append(f'<rect x="{tx}" y="{ty}" width="40" height="40" '
                      f'fill="{shade}" stroke="#39312A" stroke-width="1"/>')
TILES = "\n    ".join(_tiles)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#39312A"/>
  <g>
    {TILES}
  </g>
  <rect x="6" y="6" width="468" height="348" rx="10" fill="none" stroke="#241E19" stroke-width="12"/>
  <rect x="14" y="14" width="452" height="332" rx="8" fill="none" stroke="#7A6A55" stroke-width="3" opacity="0.5"/>
</svg>"""

# -------- 용사(궁수): 탑뷰, 오른쪽(동쪽)을 향해 그림 (방향 90 기본, 회전=자유) --------
#   대기: 활을 내린 준비 자세 / 겨눔: 활을 당겨 화살을 오른쪽으로 겨눈 자세
HERO_IDLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <ellipse cx="30" cy="52" rx="15" ry="4" fill="#000000" opacity="0.22"/>
  <!-- 몸통(망토) -->
  <circle cx="30" cy="32" r="15" fill="#2E7D32" stroke="#1B5E20" stroke-width="2"/>
  <!-- 머리(두건) -->
  <circle cx="30" cy="24" r="9" fill="#F1C27D" stroke="#C88E4E" stroke-width="1.5"/>
  <path d="M21 22 Q30 10 39 22 Z" fill="#33691E"/>
  <!-- 내린 활 (오른쪽) -->
  <path d="M46 20 Q56 32 46 44" fill="none" stroke="#8D5A2B" stroke-width="3"/>
  <line x1="46" y1="20" x2="46" y2="44" stroke="#EEEEEE" stroke-width="1"/>
</svg>"""

HERO_AIM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <ellipse cx="30" cy="52" rx="15" ry="4" fill="#000000" opacity="0.22"/>
  <!-- 몸통 -->
  <circle cx="30" cy="32" r="15" fill="#2E7D32" stroke="#1B5E20" stroke-width="2"/>
  <!-- 머리 -->
  <circle cx="30" cy="24" r="9" fill="#F1C27D" stroke="#C88E4E" stroke-width="1.5"/>
  <path d="M21 22 Q30 10 39 22 Z" fill="#33691E"/>
  <!-- 당긴 활 + 시위 (겨눔) -->
  <path d="M40 14 Q60 32 40 50" fill="none" stroke="#A0662F" stroke-width="4"/>
  <path d="M40 14 L28 32 L40 50" fill="none" stroke="#F5F5F5" stroke-width="1.5"/>
  <!-- 겨눈 화살 (오른쪽으로) -->
  <line x1="26" y1="32" x2="60" y2="32" stroke="#5D4037" stroke-width="2.5"/>
  <polygon points="60,32 52,28 52,36" fill="#CFD8DC" stroke="#607D8B" stroke-width="1"/>
  <polygon points="28,32 34,29 34,35" fill="#E53935"/>
</svg>"""

# -------- 화살: 오른쪽을 향해 (방향 90 기본) --------
ARROW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="16" viewBox="0 0 48 16">
  <line x1="4" y1="8" x2="40" y2="8" stroke="#6D4C41" stroke-width="3"/>
  <polygon points="47,8 37,3 37,13" fill="#ECEFF1" stroke="#90A4AE" stroke-width="1"/>
  <polygon points="4,8 11,3 11,13" fill="#E53935"/>
  <polygon points="8,8 14,4 14,12" fill="#EF9A9A"/>
</svg>"""

# -------- 적 코스튬: 걷는 놈 / 돌진 놈 / 폭발 --------
WALKER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="54" rx="15" ry="3" fill="#000000" opacity="0.22"/>
  <path d="M13 46 Q9 24 30 20 Q51 24 47 46 Z" fill="#7E57C2" stroke="#512DA8" stroke-width="2"/>
  <ellipse cx="30" cy="28" rx="17" ry="11" fill="#9575CD"/>
  <circle cx="24" cy="30" r="4" fill="#FFFFFF"/>
  <circle cx="36" cy="30" r="4" fill="#FFFFFF"/>
  <circle cx="24" cy="31" r="2" fill="#1B0F2A"/>
  <circle cx="36" cy="31" r="2" fill="#1B0F2A"/>
  <path d="M23 40 Q30 44 37 40" fill="none" stroke="#4527A0" stroke-width="2"/>
</svg>"""

DASHER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="54" rx="16" ry="3" fill="#000000" opacity="0.25"/>
  <polygon points="30,6 38,22 30,18 22,22" fill="#FF7043"/>
  <polygon points="8,30 24,24 20,32 24,40" fill="#FF7043"/>
  <polygon points="52,30 36,24 40,32 36,40" fill="#FF7043"/>
  <circle cx="30" cy="32" r="15" fill="#EF5350" stroke="#B71C1C" stroke-width="2"/>
  <polygon points="22,28 30,32 22,36" fill="#FFEB3B"/>
  <polygon points="38,28 30,32 38,36" fill="#FFEB3B"/>
  <circle cx="25" cy="30" r="2" fill="#3E0A0A"/>
  <circle cx="35" cy="30" r="2" fill="#3E0A0A"/>
  <path d="M24 40 L28 37 L32 40 L36 37" fill="none" stroke="#7F0000" stroke-width="2"/>
</svg>"""

EXPLOSION_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30, 30, 29, 12, 12)}" fill="#FF6F00" stroke="#E65100" stroke-width="1"/>
  <polygon points="{_star_pts(30, 30, 21, 8, 12, rot=0.262)}" fill="#FFB300"/>
  <circle cx="30" cy="30" r="12" fill="#FFEB3B"/>
  <circle cx="30" cy="30" r="5"  fill="#FFFFFF"/>
</svg>"""

# -------- 강화카드: 3선택지 (공격력/연사속도/이동속도) --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="460" height="180" viewBox="0 0 460 180">
  <rect x="4" y="4" width="452" height="172" rx="16" fill="#1A237E" opacity="0.96" stroke="#FFD54F" stroke-width="4"/>
  <text x="230" y="38" text-anchor="middle" fill="#FFD54F" font-family="Arial, sans-serif" font-size="24" font-weight="bold">웨이브 클리어! 강화 선택 (클릭)</text>
  <rect x="20" y="55" width="130" height="105" rx="12" fill="#C62828" stroke="#FFFFFF" stroke-width="2"/>
  <text x="85" y="105" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="40" font-weight="bold">1</text>
  <text x="85" y="140" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16">공격력 ↑</text>
  <rect x="165" y="55" width="130" height="105" rx="12" fill="#2E7D32" stroke="#FFFFFF" stroke-width="2"/>
  <text x="230" y="105" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="40" font-weight="bold">2</text>
  <text x="230" y="140" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16">연사속도 ↑</text>
  <rect x="310" y="55" width="130" height="105" rx="12" fill="#1565C0" stroke="#FFFFFF" stroke-width="2"/>
  <text x="375" y="105" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="40" font-weight="bold">3</text>
  <text x="375" y="140" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16">이동속도 ↑</text>
</svg>"""

# -------- 게임오버 / 승리 배너 --------
LOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="5" y="5" width="350" height="140" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="66" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="18">초록 깃발(▶) 다시 도전</text>
</svg>"""

WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="5" y="5" width="350" height="140" rx="14" fill="#000000" opacity="0.88" stroke="#FFD54F" stroke-width="5"/>
  <text x="180" y="66" text-anchor="middle" fill="#FFD54F" font-family="Arial, sans-serif" font-size="44" font-weight="bold">승리!</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFF59D" font-family="Arial, sans-serif" font-size="18">모든 웨이브 클리어! ▶ 다시</text>
</svg>"""

# -------- 체력바: 11단 costume-fill --------
def _hpbar_svg(step):  # step 0..10
    filled = int(round(130 * step / 10))
    col = "#43A047" if step >= 6 else ("#FBC02D" if step >= 3 else "#E53935")
    fillrect = f'<rect x="5" y="5" width="{filled}" height="16" rx="4" fill="{col}"/>' if filled > 0 else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="140" height="26" viewBox="0 0 140 26">
  <rect x="2" y="2" width="136" height="22" rx="6" fill="#000000" opacity="0.55" stroke="#FFFFFF" stroke-width="2"/>
  {fillrect}
</svg>"""
HPBAR_SVGS = [_hpbar_svg(s) for s in range(11)]

# ============================================================
#  helpers (scratch-game-template 공통 헬퍼 — 재구현 금지)
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

def b_distance_to(bs, target):
    m = gen(); bs[m] = mk("sensing_distancetomenu",
        fields={"DISTANCETOMENU": [target, None]}, shadow=True)
    d = gen(); bs[d] = mk("sensing_distanceto", inputs={"DISTANCETOMENU": [1, m]})
    bs[m]["parent"] = d
    return d

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

def b_wait(bs, dur):
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": num(dur)})
    return bid

def b_wait_var(bs, vid, name):
    v = gen(); bs[v] = mk("data_variable", fields={"VARIABLE": [name, vid]})
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": slot(v)})
    bs[v]["parent"] = bid
    return bid

def b_waituntil(bs, cond):
    bid = gen(); bs[bid] = mk("control_wait_until", inputs={"CONDITION": [2, cond]})
    bs[cond]["parent"] = bid
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

def b_broadcast_wait(bs, name, brid):
    m = gen(); bs[m] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcastandwait", inputs={"BROADCAST_INPUT": [1, m]})
    bs[m]["parent"] = b
    return b

def _spr_menu(bs, name):
    m = gen(); bs[m] = mk("sensing_of_object_menu",
        fields={"OBJECT": [name, None]}, shadow=True)
    return m

def _of(bs, spr, prop):
    bid = gen(); bs[bid] = mk("sensing_of",
        inputs={"OBJECT": [1, _spr_menu(bs, spr)]}, fields={"PROPERTY": [prop, None]})
    return bid

# ============================================================
#  변수 / 방송 ID
# ============================================================
# ----- 튜닝(개조 손잡이) — 아이가 이 숫자만 바꿔 논다 -----
V_MOVE     = "varMove01"     # 이동속도     5.5
V_FIREGAP  = "varFireGap02"  # 발사쿨       0.25
V_ARROWSPD = "varArrowSpd03" # 화살속도     11
V_ATK      = "varAtk04"      # 공격력       1
V_ENEMYHP  = "varEnemyHP05"  # 잡졸체력     2
V_ENEMYSPD = "varEnemySpd06" # 적속도       2.2
V_DASHSPD  = "varDashSpd07"  # 돌진속도     6
V_MAXHP    = "varMaxHP08"    # 최대체력     5
V_INV      = "varInv09"      # 무적시간     0.5 (초)
V_WAVEBASE = "varWaveBase10" # 웨이브기본수  4
V_GROWTH   = "varGrowth11"   # 적성장배율   1.25
V_STOPTICK = "varStopTick12" # 정지판정     0.02 (멈춤을 얼마나 자주 확인하는지, 초)
V_UP       = "varUp13"       # 강화량       1
V_MAXWAVE  = "varMaxWave14"  # 최대웨이브    3
V_SPAWNGAP = "varSpawnGap15" # 스폰간격     0.5

# ----- 진행/내부 상태 -----
V_STATE  = "varState20"   # 게임상태 1=전투 2=강화선택 0=게임오버 3=승리
V_WAVE   = "varWave21"    # 웨이브
V_ALIVE  = "varAlive22"   # 적수
V_HP     = "varHP23"      # 체력
V_INVT   = "varInvT24"    # 무적(초 카운트다운)
V_AIMD   = "varAimD25"    # 조준거리
V_AIMX   = "varAimX26"    # 조준X
V_AIMY   = "varAimY27"    # 조준Y
V_AIMOK  = "varAimOK28"   # 조준있음
V_SPX    = "varSPX29"     # 적생성X
V_SPY    = "varSPY30"     # 적생성Y
V_SPTYPE = "varSPType31"  # 적생성종류
V_PICK   = "varPick32"    # 선택(강화 카드)

# ----- 클론-로컬 -----
V_EISC     = "varEIsClone"    # 적: 복제됨
V_EHP      = "varEHP"         # 적: 내체력
V_ESPD     = "varESpd"        # 적: 내속도
V_ETYPE    = "varEType"       # 적: 적종류
V_EHIT     = "varEHit"        # 적: 피격쿨
V_DASHT    = "varDashT"       # 적: 돌진틱
V_DASHLEFT = "varDashLeft"    # 적: 대시남음
V_ARRISC   = "varArrIsClone"  # 화살: 복제됨

# ----- 방송 -----
BR_START     = "brStart01"     # 게임시작
BR_AIM       = "brAim02"       # 조준요청
BR_FIRE      = "brFire03"      # 발사
BR_SPAWN     = "brSpawn04"     # 적생성
BR_WAVECLEAR = "brWaveClear05" # 웨이브클리어

# ============================================================
#  공통: (조준X,조준Y) 를 향하는 방향값 리포터 (내 x/y 기준 atan)
# ============================================================
def aim_direction(bs, vrep, op, cmp_op):
    """방향 = atan((조준X - x)/(조준Y - y)) + ((y > 조준Y) * 180)."""
    ax = vrep("조준X", V_AIMX); xp = gen(); bs[xp] = mk("motion_xposition")
    dx = op("operator_subtract", ax, xp)
    ay = vrep("조준Y", V_AIMY); yp = gen(); bs[yp] = mk("motion_yposition")
    dy = op("operator_subtract", ay, yp)
    ratio = op("operator_divide", dx, dy)
    atanv = gen(); bs[atanv] = mk("operator_mathop",
        inputs={"NUM": slot(ratio)}, fields={"OPERATOR": ["atan", None]})
    bs[ratio]["parent"] = atanv
    yp2 = gen(); bs[yp2] = mk("motion_yposition"); ay2 = vrep("조준Y", V_AIMY)
    below = cmp_op("operator_gt", yp2, ay2)
    flip = op("operator_multiply", below, 180)
    return op("operator_add", atanv, flip)

# ============================================================
#  STAGE — 변수 초기화 · 웨이브 오케스트레이션 · 무적 타이머
# ============================================================
def build_stage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 → 모든 변수 초기화 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val); seq.append((sid, bs[sid]))
    # 튜닝(개조 손잡이)
    add_set("이동속도", V_MOVE, 5.5)
    add_set("발사쿨", V_FIREGAP, 0.25)
    add_set("화살속도", V_ARROWSPD, 11)
    add_set("공격력", V_ATK, 1)
    add_set("잡졸체력", V_ENEMYHP, 2)
    add_set("적속도", V_ENEMYSPD, 2.2)
    add_set("돌진속도", V_DASHSPD, 6)
    add_set("최대체력", V_MAXHP, 5)
    add_set("무적시간", V_INV, 0.5)
    add_set("웨이브기본수", V_WAVEBASE, 4)
    add_set("적성장배율", V_GROWTH, 1.25)
    add_set("정지판정", V_STOPTICK, 0.02)
    add_set("강화량", V_UP, 1)
    add_set("최대웨이브", V_MAXWAVE, 3)
    add_set("스폰간격", V_SPAWNGAP, 0.5)
    # 체력 = 최대체력
    maxhp_r = vrep("최대체력", V_MAXHP)
    sid = b_setvar(bs, "체력", V_HP, maxhp_r); seq.append((sid, bs[sid]))
    # 진행 상태
    add_set("게임상태", V_STATE, 1)
    add_set("웨이브", V_WAVE, 0)
    add_set("적수", V_ALIVE, 0)
    add_set("무적", V_INVT, 0)
    add_set("조준거리", V_AIMD, 99999)
    add_set("조준X", V_AIMX, 0)
    add_set("조준Y", V_AIMY, 0)
    add_set("조준있음", V_AIMOK, 0)
    add_set("적생성X", V_SPX, 0)
    add_set("적생성Y", V_SPY, 0)
    add_set("적생성종류", V_SPTYPE, 1)
    add_set("선택", V_PICK, 0)
    w1 = b_wait(bs, 0.3); seq.append((w1, bs[w1]))
    bc_start = b_broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # ===== (B) 게임시작 → 웨이브 오케스트레이션 =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=320, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    set_wave0 = b_setvar(bs, "웨이브", V_WAVE, 0)
    set_st1   = b_setvar(bs, "게임상태", V_STATE, 1)

    # --- 웨이브 본문 ---
    inc_wave  = b_changevar(bs, "웨이브", V_WAVE, 1)
    set_alive0 = b_setvar(bs, "적수", V_ALIVE, 0)

    # 스폰 루프 본문: 가장자리 좌표 + 종류 + clone
    #   가장자리(상/하/좌/우) 랜덤 (코인플립 2회)
    coin_h = gen(); bs[coin_h] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_horiz = cmp_op("operator_equals", coin_h, 0)
    rx_h = gen(); bs[rx_h] = mk("operator_random", inputs={"FROM": num(-215), "TO": num(215)})
    set_spx_h = gen(); bs[set_spx_h] = mk("data_setvariableto",
        inputs={"VALUE": slot(rx_h)}, fields={"VARIABLE": ["적생성X", V_SPX]})
    bs[rx_h]["parent"] = set_spx_h
    coin_tb = gen(); bs[coin_tb] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_top = cmp_op("operator_equals", coin_tb, 0)
    set_spy_top = b_setvar(bs, "적생성Y", V_SPY, 165)
    set_spy_bot = b_setvar(bs, "적생성Y", V_SPY, -165)
    if_tb = b_ifelse(bs, cond_top, set_spy_top, set_spy_bot)
    chain([(set_spx_h, bs[set_spx_h]), (if_tb, bs[if_tb])])
    ry_v = gen(); bs[ry_v] = mk("operator_random", inputs={"FROM": num(-155), "TO": num(155)})
    set_spy_v = gen(); bs[set_spy_v] = mk("data_setvariableto",
        inputs={"VALUE": slot(ry_v)}, fields={"VARIABLE": ["적생성Y", V_SPY]})
    bs[ry_v]["parent"] = set_spy_v
    coin_lr = gen(); bs[coin_lr] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_left = cmp_op("operator_equals", coin_lr, 0)
    set_spx_left = b_setvar(bs, "적생성X", V_SPX, -220)
    set_spx_right = b_setvar(bs, "적생성X", V_SPX, 220)
    if_lr = b_ifelse(bs, cond_left, set_spx_left, set_spx_right)
    chain([(set_spy_v, bs[set_spy_v]), (if_lr, bs[if_lr])])
    if_edge = b_ifelse(bs, cond_horiz, set_spx_h, set_spy_v)

    # 종류: 웨이브1 → 걷는놈(1)만 / 이후 → 1~2 랜덤(돌진 섞임)
    wave_rt = vrep("웨이브", V_WAVE)
    cond_w1 = cmp_op("operator_equals", wave_rt, 1)
    set_type1 = b_setvar(bs, "적생성종류", V_SPTYPE, 1)
    rnd_type = gen(); bs[rnd_type] = mk("operator_random", inputs={"FROM": num(1), "TO": num(2)})
    set_type_rnd = gen(); bs[set_type_rnd] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_type)}, fields={"VARIABLE": ["적생성종류", V_SPTYPE]})
    bs[rnd_type]["parent"] = set_type_rnd
    if_type = b_ifelse(bs, cond_w1, set_type1, set_type_rnd)

    inc_alive = b_changevar(bs, "적수", V_ALIVE, 1)
    bc_spawn = b_broadcast(bs, "적생성", BR_SPAWN)
    chain([(if_edge, bs[if_edge]), (if_type, bs[if_type]),
           (inc_alive, bs[inc_alive]), (bc_spawn, bs[bc_spawn])])
    # 죽었으면 스폰 중단
    state_sp = vrep("게임상태", V_STATE)
    cond_sp_play = cmp_op("operator_equals", state_sp, 1)
    if_sp_guard = b_if(bs, cond_sp_play, if_edge)
    w_gap = b_wait_var(bs, V_SPAWNGAP, "스폰간격")
    chain([(if_sp_guard, bs[if_sp_guard]), (w_gap, bs[w_gap])])
    # repeat (웨이브기본수 + 2*웨이브)
    wave_cnt = vrep("웨이브", V_WAVE)
    two_wave = op("operator_multiply", 2, wave_cnt)
    wbase_r = vrep("웨이브기본수", V_WAVEBASE)
    total_sp = op("operator_add", wbase_r, two_wave)
    rep_spawn = gen(); bs[rep_spawn] = mk("control_repeat",
        inputs={"TIMES": slot(total_sp), "SUBSTACK": [2, if_sp_guard]})
    bs[total_sp]["parent"] = rep_spawn; bs[if_sp_guard]["parent"] = rep_spawn

    # 전멸 대기: wait until (적수 < 1) or (게임상태 = 0)
    alive_r = vrep("적수", V_ALIVE)
    cond_none = cmp_op("operator_lt", alive_r, 1)
    state_w = vrep("게임상태", V_STATE)
    cond_dead_w = cmp_op("operator_equals", state_w, 0)
    cond_clear = bool_op("operator_or", cond_none, cond_dead_w)
    wu_clear = b_waituntil(bs, cond_clear)

    # 살아서 클리어 → 마지막이면 승리, 아니면 강화 카드
    state_c = vrep("게임상태", V_STATE)
    cond_alive_clear = cmp_op("operator_equals", state_c, 1)
    wave_cmp = vrep("웨이브", V_WAVE); maxw_r = vrep("최대웨이브", V_MAXWAVE)
    cond_more = cmp_op("operator_lt", wave_cmp, maxw_r)
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_wc = b_broadcast(bs, "웨이브클리어", BR_WAVECLEAR)
    # wait until 게임상태 != 2 (카드 선택 완료로 1, 또는 죽음 0)
    state_wc = vrep("게임상태", V_STATE)
    cond_still2 = cmp_op("operator_equals", state_wc, 2)
    not_still2 = gen(); bs[not_still2] = mk("operator_not", inputs={"OPERAND": [2, cond_still2]})
    bs[cond_still2]["parent"] = not_still2
    wu_card = b_waituntil(bs, not_still2)
    chain([(set_st2, bs[set_st2]), (bc_wc, bs[bc_wc]), (wu_card, bs[wu_card])])
    set_st3 = b_setvar(bs, "게임상태", V_STATE, 3)  # 마지막 웨이브까지 클리어 → 승리
    if_more = b_ifelse(bs, cond_more, set_st2, set_st3)
    if_alive_clear = b_if(bs, cond_alive_clear, if_more)

    # 웨이브 본문 순서: inc_wave → set_alive0 → rep_spawn → wu_clear → if_alive_clear
    chain([(inc_wave, bs[inc_wave]), (set_alive0, bs[set_alive0]),
           (rep_spawn, bs[rep_spawn]), (wu_clear, bs[wu_clear]),
           (if_alive_clear, bs[if_alive_clear])])
    # repeat until (게임상태=0) or (게임상태=3)
    state_end1 = vrep("게임상태", V_STATE); cond_end0 = cmp_op("operator_equals", state_end1, 0)
    state_end2 = vrep("게임상태", V_STATE); cond_end3 = cmp_op("operator_equals", state_end2, 3)
    cond_end = bool_op("operator_or", cond_end0, cond_end3)
    ru_wave = gen(); bs[ru_wave] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_end], "SUBSTACK": [2, inc_wave]})
    bs[cond_end]["parent"] = ru_wave; bs[inc_wave]["parent"] = ru_wave
    chain([(hb, bs[hb]), (set_wave0, bs[set_wave0]), (set_st1, bs[set_st1]),
           (ru_wave, bs[ru_wave])])

    # ===== (C) 무적 타이머 감소 forever (초 단위) =====
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=560)
    invt_r = vrep("무적", V_INVT)
    cond_inv_pos = cmp_op("operator_gt", invt_r, 0)
    dec_inv = b_changevar(bs, "무적", V_INVT, -0.03)
    if_inv = b_if(bs, cond_inv_pos, dec_inv)
    wc = b_wait(bs, 0.03)
    chain([(if_inv, bs[if_inv]), (wc, bs[wc])])
    fe_c = b_forever(bs, if_inv)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    add_comment(bs, comments, h,
        "⚙️ 개조 손잡이 (여기가 핵심!)\n"
        "게임의 모든 숫자가 이 초록 깃발 묶음에 한글 변수로 모여 있어요. "
        "예: 발사쿨 0.25→0.1 로 바꾸면 연사가 빨라져요. 이동속도·화살속도·적성장배율도 "
        "직접 바꿔 보고 ▶ 로 확인해 보세요.",
        x=-360, y=-280, w=330, h=170)
    add_comment(bs, comments, inc_wave,
        "🌊 웨이브 오케스트레이션\n"
        "웨이브 N 마다 (웨이브기본수 + 2N) 마리를 가장자리에서 스폰하고, 전멸(적수<1)하면 "
        "강화 카드를 띄워요. 마지막 웨이브까지 버티면 승리! "
        "적은 웨이브가 오를수록 적성장배율^(N-1) 로 강해져요.",
        x=560, y=-40, w=320, h=170)
    return bs, comments

# ============================================================
#  용사 (궁수) — 이동 · "멈추면 쏜다" 자동조준 발사 · 피격
# ============================================================
def build_hero_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 초기화 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    cm0 = gen(); bs[cm0] = mk("looks_costume", fields={"COSTUME": ["대기", None]}, shadow=True)
    sw0 = gen(); bs[sw0] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm0]})
    bs[cm0]["parent"] = sw0
    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (rs, bs[rs]),
           (pd, bs[pd]), (g0, bs[g0]), (front, bs[front]), (sw0, bs[sw0])])

    # ===== (B) 8방향 이동 forever (게임상태=1) =====
    hb = gen(); bs[hb] = mk("event_whenflagclicked", top=True, x=20, y=220)
    inner = []
    move_r = vrep("이동속도", V_MOVE)
    cx_r = gen(); bs[cx_r] = mk("motion_changexby", inputs={"DX": slot(move_r)}); bs[move_r]["parent"] = cx_r
    inner.append(b_if(bs, b_keypressed(bs, "right arrow"), cx_r))
    move_l = vrep("이동속도", V_MOVE); neg_l = op("operator_subtract", 0, move_l)
    cx_l = gen(); bs[cx_l] = mk("motion_changexby", inputs={"DX": slot(neg_l)}); bs[neg_l]["parent"] = cx_l
    inner.append(b_if(bs, b_keypressed(bs, "left arrow"), cx_l))
    move_u = vrep("이동속도", V_MOVE)
    cy_u = gen(); bs[cy_u] = mk("motion_changeyby", inputs={"DY": slot(move_u)}); bs[move_u]["parent"] = cy_u
    inner.append(b_if(bs, b_keypressed(bs, "up arrow"), cy_u))
    move_dn = vrep("이동속도", V_MOVE); neg_dn = op("operator_subtract", 0, move_dn)
    cy_dn = gen(); bs[cy_dn] = mk("motion_changeyby", inputs={"DY": slot(neg_dn)}); bs[neg_dn]["parent"] = cy_dn
    inner.append(b_if(bs, b_keypressed(bs, "down arrow"), cy_dn))
    def clamp(pos_op, set_op, cmp, limit):
        xp = gen(); bs[xp] = mk(pos_op)
        c = cmp_op(cmp, xp, limit)
        key = "X" if set_op == "motion_setx" else "Y"
        st = gen(); bs[st] = mk(set_op, inputs={key: num(limit)})
        return b_if(bs, c, st)
    inner.append(clamp("motion_xposition", "motion_setx", "operator_gt", 230))
    inner.append(clamp("motion_xposition", "motion_setx", "operator_lt", -230))
    inner.append(clamp("motion_yposition", "motion_sety", "operator_gt", 160))
    inner.append(clamp("motion_yposition", "motion_sety", "operator_lt", -160))
    chain([(b, bs[b]) for b in inner])
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    if_play_b = b_if(bs, cond_play_b, inner[0])
    wb = b_wait_var(bs, V_STOPTICK, "정지판정")
    chain([(if_play_b, bs[if_play_b]), (wb, bs[wb])])
    fe_b = b_forever(bs, if_play_b)
    chain([(hb, bs[hb]), (fe_b, bs[fe_b])])

    # ===== (C) "멈추면 쏜다" 자동조준 발사 forever (핵심) =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=320, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # not (right or left or up or down)
    k_r = b_keypressed(bs, "right arrow"); k_l = b_keypressed(bs, "left arrow")
    k_u = b_keypressed(bs, "up arrow"); k_d = b_keypressed(bs, "down arrow")
    or_rl = bool_op("operator_or", k_r, k_l)
    or_ud = bool_op("operator_or", k_u, k_d)
    any_key = bool_op("operator_or", or_rl, or_ud)
    not_moving = gen(); bs[not_moving] = mk("operator_not", inputs={"OPERAND": [2, any_key]})
    bs[any_key]["parent"] = not_moving

    # 멈춤 분기: 겨눔 코스튬 → 조준요청 → 조준있으면 적 향해 몸 돌리고 발사
    cmA = gen(); bs[cmA] = mk("looks_costume", fields={"COSTUME": ["겨눔", None]}, shadow=True)
    sw_aim = gen(); bs[sw_aim] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmA]})
    bs[cmA]["parent"] = sw_aim
    set_aimd = b_setvar(bs, "조준거리", V_AIMD, 99999)
    set_aimok0 = b_setvar(bs, "조준있음", V_AIMOK, 0)
    bcw_aim = b_broadcast_wait(bs, "조준요청", BR_AIM)
    # if 조준있음=1 { point (조준방향); 발사; twang }
    aimok_r = vrep("조준있음", V_AIMOK)
    cond_haveaim = cmp_op("operator_equals", aimok_r, 1)
    dirv = aim_direction(bs, vrep, op, cmp_op)
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": slot(dirv)})
    bs[dirv]["parent"] = pdir
    bc_fire = b_broadcast(bs, "발사", BR_FIRE)
    sh_fire, _ = b_sound(bs, 0, "twang")
    chain([(pdir, bs[pdir]), (bc_fire, bs[bc_fire]), (sh_fire, bs[sh_fire])])
    if_haveaim = b_if(bs, cond_haveaim, pdir)
    w_gap = b_wait_var(bs, V_FIREGAP, "발사쿨")
    chain([(sw_aim, bs[sw_aim]), (set_aimd, bs[set_aimd]), (set_aimok0, bs[set_aimok0]),
           (bcw_aim, bs[bcw_aim]), (if_haveaim, bs[if_haveaim]), (w_gap, bs[w_gap])])
    # 이동 분기: 대기 코스튬 → 조준있음=0 → wait 정지판정
    cmB = gen(); bs[cmB] = mk("looks_costume", fields={"COSTUME": ["대기", None]}, shadow=True)
    sw_idle = gen(); bs[sw_idle] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmB]})
    bs[cmB]["parent"] = sw_idle
    set_aimok_m = b_setvar(bs, "조준있음", V_AIMOK, 0)
    w_move = b_wait_var(bs, V_STOPTICK, "정지판정")
    chain([(sw_idle, bs[sw_idle]), (set_aimok_m, bs[set_aimok_m]), (w_move, bs[w_move])])
    if_stopfire = b_ifelse(bs, not_moving, sw_aim, sw_idle)
    # 전투 중일 때만
    state_c = vrep("게임상태", V_STATE)
    cond_play_c = cmp_op("operator_equals", state_c, 1)
    w_idle = b_wait(bs, 0.05)
    if_combat = b_ifelse(bs, cond_play_c, if_stopfire, w_idle)
    fe_c = b_forever(bs, if_combat)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # ===== (D) 피격 감시 forever =====
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=640, y=220)
    tc_e = b_touching(bs, "적")
    invt_r = vrep("무적", V_INVT)
    cond_noinv = cmp_op("operator_equals", invt_r, 0)
    state_d = vrep("게임상태", V_STATE)
    cond_play_d = cmp_op("operator_equals", state_d, 1)
    cond_da = bool_op("operator_and", tc_e, cond_noinv)
    cond_hurt = bool_op("operator_and", cond_da, cond_play_d)
    dec_hp = b_changevar(bs, "체력", V_HP, -1)
    inv_r = vrep("무적시간", V_INV)
    set_invt = b_setvar(bs, "무적", V_INVT, inv_r)
    sh_hurt, _ = b_sound(bs, 0, "hurt")
    # if 체력<1 → 게임상태=0
    hp_chk = vrep("체력", V_HP)
    cond_dead = cmp_op("operator_lt", hp_chk, 1)
    set_over = b_setvar(bs, "게임상태", V_STATE, 0)
    if_dead = b_if(bs, cond_dead, set_over)
    chain([(dec_hp, bs[dec_hp]), (set_invt, bs[set_invt]), (sh_hurt, bs[sh_hurt]),
           (if_dead, bs[if_dead])])
    if_hurt = b_if(bs, cond_hurt, dec_hp)
    wd = b_wait(bs, 0.03)
    chain([(if_hurt, bs[if_hurt]), (wd, bs[wd])])
    fe_d = b_forever(bs, if_hurt)
    chain([(hd, bs[hd]), (fe_d, bs[fe_d])])

    add_comment(bs, comments, hc,
        "🎯 '멈추면 쏜다'의 비밀\n"
        "화살표를 하나도 안 누른 순간(멈춤)에만 '겨눔' 자세로 바꾸고, '조준요청'을 방송해 "
        "가장 가까운 적을 찾은 뒤 그 쪽으로 몸을 돌려 발사해요(발사쿨=0.25초마다). "
        "움직이는 동안엔 '대기' 자세로 발사가 멈춰요 — 그래서 서면 바로 쏘고, 움직이면 멈춰요.",
        x=560, y=180, w=340, h=190)
    add_comment(bs, comments, fe_b,
        "🕹️ 8방향 이동\n"
        "화살표로 x/y 를 '이동속도'만큼 더하고 빼요. 대각선도 됨! 조준은 자동이라 "
        "너는 피하는 데만 집중하면 돼요.",
        x=-360, y=120, w=300, h=140)
    return bs, comments

# ============================================================
#  화살 — 발사 방송 → 클론이 조준 방향으로 직진
# ============================================================
def build_arrow_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(75)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    orig0 = b_setvar(bs, "복제됨", V_ARRISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 발사 → 원본만 클론 1발
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    isc_chk = vrep("복제됨", V_ARRISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 용사 위치에서 조준 방향으로 직진
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=420)
    set_isc1 = b_setvar(bs, "복제됨", V_ARRISC, 1)
    mx_r = _of(bs, "용사", "x position"); my_r = _of(bs, "용사", "y position")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(mx_r), "Y": slot(my_r)})
    bs[mx_r]["parent"] = g; bs[my_r]["parent"] = g
    dirv = aim_direction(bs, vrep, op, cmp_op)
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": slot(dirv)})
    bs[dirv]["parent"] = pdir
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    # repeat until (touching edge) or (touching 적) or (게임상태=0) { move 화살속도 ; wait }
    mv = b_movesteps(bs, vrep("화살속도", V_ARROWSPD))
    w_mv = b_wait(bs, 0.008)
    chain([(mv, bs[mv]), (w_mv, bs[w_mv])])
    edge_menu = gen(); bs[edge_menu] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_edge = gen(); bs[tc_edge] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge_menu]})
    bs[edge_menu]["parent"] = tc_edge
    tc_en = b_touching(bs, "적")
    state_b = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_b, 0)
    or1 = bool_op("operator_or", tc_edge, tc_en)
    cond_stop = bool_op("operator_or", or1, cond_over)
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_stop], "SUBSTACK": [2, mv]})
    bs[cond_stop]["parent"] = ru; bs[mv]["parent"] = ru
    # 적이 데미지를 적용할 시간을 주고(터널링 방지) 삭제
    w_linger = b_wait(bs, 0.06)
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (pdir, bs[pdir]),
           (front, bs[front]), (show, bs[show]), (ru, bs[ru]),
           (w_linger, bs[w_linger]), (del_end, bs[del_end])])

    add_comment(bs, comments, ch,
        "🏹 화살 클론\n"
        "발사 순간 용사 위치에서 태어나 '조준X/조준Y'(가장 가까운 적) 방향으로 직진해요. "
        "가장자리나 적에 닿으면 잠깐 머물러(적이 데미지를 적용) 사라져요.",
        x=560, y=380, w=320, h=150)
    return bs, comments

# ============================================================
#  적 — 스폰 · 걷는 놈/돌진 놈 · 화살 피격 · 조준 보고
# ============================================================
def build_enemy_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_EISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 적생성 방송 → 원본만 클론
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]})
    isc_chk = vrep("복제됨", V_EISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_EISC, 1)
    sptype_r = vrep("적생성종류", V_SPTYPE)
    set_type = b_setvar(bs, "적종류", V_ETYPE, sptype_r)
    set_hit0 = b_setvar(bs, "피격쿨", V_EHIT, 0)
    set_dt = b_setvar(bs, "돌진틱", V_DASHT, 30)
    set_dl = b_setvar(bs, "대시남음", V_DASHLEFT, 0)
    # 종류별 외형
    cond_t1 = cmp_op("operator_equals", vrep("적종류", V_ETYPE), 1)
    cm1 = gen(); bs[cm1] = mk("looks_costume", fields={"COSTUME": ["걷는적", None]}, shadow=True)
    sw1 = gen(); bs[sw1] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm1]}); bs[cm1]["parent"] = sw1
    sz1 = gen(); bs[sz1] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    chain([(sw1, bs[sw1]), (sz1, bs[sz1])])
    if_t1 = b_if(bs, cond_t1, sw1)
    cond_t2 = cmp_op("operator_equals", vrep("적종류", V_ETYPE), 2)
    cm2 = gen(); bs[cm2] = mk("looks_costume", fields={"COSTUME": ["돌진적", None]}, shadow=True)
    sw2 = gen(); bs[sw2] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm2]}); bs[cm2]["parent"] = sw2
    sz2 = gen(); bs[sz2] = mk("looks_setsizeto", inputs={"SIZE": num(75)})
    chain([(sw2, bs[sw2]), (sz2, bs[sz2])])
    if_t2 = b_if(bs, cond_t2, sw2)
    # 체력/속도 기본 = 잡졸체력/적속도
    hp_base = vrep("잡졸체력", V_ENEMYHP)
    set_ehp = b_setvar(bs, "내체력", V_EHP, hp_base)
    spd_base = vrep("적속도", V_ENEMYSPD)
    set_espd = b_setvar(bs, "내속도", V_ESPD, spd_base)
    # 웨이브 스케일링: repeat (웨이브-1) { 내체력*=적성장배율 ; 내속도*=적성장배율 }
    ehp_s = vrep("내체력", V_EHP); gr1 = vrep("적성장배율", V_GROWTH)
    mul_h = op("operator_multiply", ehp_s, gr1)
    set_h2 = b_setvar(bs, "내체력", V_EHP, mul_h)
    esp_s = vrep("내속도", V_ESPD); gr2 = vrep("적성장배율", V_GROWTH)
    mul_s = op("operator_multiply", esp_s, gr2)
    set_s2 = b_setvar(bs, "내속도", V_ESPD, mul_s)
    chain([(set_h2, bs[set_h2]), (set_s2, bs[set_s2])])
    wave_r = vrep("웨이브", V_WAVE); wm1 = op("operator_subtract", wave_r, 1)
    rep_scale = gen(); bs[rep_scale] = mk("control_repeat",
        inputs={"TIMES": slot(wm1), "SUBSTACK": [2, set_h2]})
    bs[wm1]["parent"] = rep_scale; bs[set_h2]["parent"] = rep_scale
    # 위치 + 표시
    spx_r = vrep("적생성X", V_SPX); spy_r = vrep("적생성Y", V_SPY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(spx_r), "Y": slot(spy_r)})
    bs[spx_r]["parent"] = g; bs[spy_r]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")

    # --- forever 본문 ---
    body = []
    # 1) 게임오버 정리
    state1 = vrep("게임상태", V_STATE)
    cond_go = cmp_op("operator_equals", state1, 0)
    dec_alive_go = b_changevar(bs, "적수", V_ALIVE, -1)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    chain([(dec_alive_go, bs[dec_alive_go]), (del_go, bs[del_go])])
    if_go = b_if(bs, cond_go, dec_alive_go)
    body.append(if_go)

    # 2) 추적/돌진 (게임상태=1)
    pt = b_pointtowards(bs, "용사")
    # 돌진(종류=2): 돌진틱 감소 → 0이하면 대시남음=12, 돌진틱=60 ; 대시남음>0이면 돌진속도, 아니면 내속도*0.5
    cond_dash_type = cmp_op("operator_equals", vrep("적종류", V_ETYPE), 2)
    dec_dt = b_changevar(bs, "돌진틱", V_DASHT, -1)
    dt_r = vrep("돌진틱", V_DASHT)
    cond_dt0 = cmp_op("operator_lt", dt_r, 1)
    set_dl12 = b_setvar(bs, "대시남음", V_DASHLEFT, 12)
    set_dt60 = b_setvar(bs, "돌진틱", V_DASHT, 60)
    chain([(set_dl12, bs[set_dl12]), (set_dt60, bs[set_dt60])])
    if_dt0 = b_if(bs, cond_dt0, set_dl12)
    dl_r = vrep("대시남음", V_DASHLEFT)
    cond_dashing = cmp_op("operator_gt", dl_r, 0)
    mv_dash = b_movesteps(bs, vrep("돌진속도", V_DASHSPD))
    dec_dl = b_changevar(bs, "대시남음", V_DASHLEFT, -1)
    chain([(mv_dash, bs[mv_dash]), (dec_dl, bs[dec_dl])])
    espd_slow = vrep("내속도", V_ESPD); slow_v = op("operator_multiply", espd_slow, 0.5)
    mv_slow = b_movesteps(bs, slow_v)
    if_dashing = b_ifelse(bs, cond_dashing, mv_dash, mv_slow)
    chain([(dec_dt, bs[dec_dt]), (if_dt0, bs[if_dt0]), (if_dashing, bs[if_dashing])])
    # 걷는(종류=1): move 내속도
    mv_walk = b_movesteps(bs, vrep("내속도", V_ESPD))
    if_move = b_ifelse(bs, cond_dash_type, dec_dt, mv_walk)
    chain([(pt, bs[pt]), (if_move, bs[if_move])])
    state2 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state2, 1)
    if_chase = b_if(bs, cond_play2, pt)
    body.append(if_chase)

    # 3) 화살 피격
    tc_arr = b_touching(bs, "화살")
    hit_r = vrep("피격쿨", V_EHIT)
    cond_hit0 = cmp_op("operator_equals", hit_r, 0)
    cond_struck = bool_op("operator_and", tc_arr, cond_hit0)
    atk_r = vrep("공격력", V_ATK); neg_atk = op("operator_subtract", 0, atk_r)
    dec_myhp = b_changevar(bs, "내체력", V_EHP, neg_atk)
    set_hit = b_setvar(bs, "피격쿨", V_EHIT, 6)
    chain([(dec_myhp, bs[dec_myhp]), (set_hit, bs[set_hit])])
    if_struck = b_if(bs, cond_struck, dec_myhp)
    body.append(if_struck)
    hit_r2 = vrep("피격쿨", V_EHIT)
    cond_hitpos = cmp_op("operator_gt", hit_r2, 0)
    dec_hit = b_changevar(bs, "피격쿨", V_EHIT, -1)
    if_hitcd = b_if(bs, cond_hitpos, dec_hit)
    body.append(if_hitcd)

    # 4) 처치
    myhp_r = vrep("내체력", V_EHP)
    cond_dead = cmp_op("operator_lt", myhp_r, 1)
    exm = gen(); bs[exm] = mk("looks_costume", fields={"COSTUME": ["폭발", None]}, shadow=True)
    sw_ex = gen(); bs[sw_ex] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, exm]}); bs[exm]["parent"] = sw_ex
    sh_die, _ = b_sound(bs, 0, "pop")
    dec_alive = b_changevar(bs, "적수", V_ALIVE, -1)
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(12)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(24)}, fields={"EFFECT": ["GHOST", None]})
    w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK": [2, ch_sz]})
    bs[ch_sz]["parent"] = rep_an
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")
    chain([(sw_ex, bs[sw_ex]), (sh_die, bs[sh_die]), (dec_alive, bs[dec_alive]),
           (rep_an, bs[rep_an]), (del_k, bs[del_k])])
    if_kill = b_if(bs, cond_dead, sw_ex)
    body.append(if_kill)

    w_body = b_wait(bs, 0.025)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_type, bs[set_type]),
           (set_hit0, bs[set_hit0]), (set_dt, bs[set_dt]), (set_dl, bs[set_dl]),
           (if_t1, bs[if_t1]), (if_t2, bs[if_t2]), (set_ehp, bs[set_ehp]),
           (set_espd, bs[set_espd]), (rep_scale, bs[rep_scale]),
           (g, bs[g]), (show, bs[show]), (fe_body, bs[fe_body])])

    # (D) 조준 보고 — 최솟값 리덕션 (wait 없이 원자 실행)
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=400, y=180,
        fields={"BROADCAST_OPTION": ["조준요청", BR_AIM]})
    isc2 = vrep("복제됨", V_EISC)
    cond_clone = cmp_op("operator_equals", isc2, 1)
    state_aim = vrep("게임상태", V_STATE)
    cond_play_aim = cmp_op("operator_equals", state_aim, 1)
    cond_active = bool_op("operator_and", cond_clone, cond_play_aim)
    dist_r = b_distance_to(bs, "용사")
    aimd_r = vrep("조준거리", V_AIMD)
    cond_closer = cmp_op("operator_lt", dist_r, aimd_r)
    dist_r2 = b_distance_to(bs, "용사")
    set_aimd = b_setvar(bs, "조준거리", V_AIMD, dist_r2)
    ax_pos = gen(); bs[ax_pos] = mk("motion_xposition")
    set_aimx = b_setvar(bs, "조준X", V_AIMX, ax_pos)
    ay_pos = gen(); bs[ay_pos] = mk("motion_yposition")
    set_aimy = b_setvar(bs, "조준Y", V_AIMY, ay_pos)
    set_aimok = b_setvar(bs, "조준있음", V_AIMOK, 1)
    chain([(set_aimd, bs[set_aimd]), (set_aimx, bs[set_aimx]),
           (set_aimy, bs[set_aimy]), (set_aimok, bs[set_aimok])])
    if_closer = b_if(bs, cond_closer, set_aimd)
    if_active = b_if(bs, cond_active, if_closer)
    chain([(hd, bs[hd]), (if_active, bs[if_active])])

    add_comment(bs, comments, if_chase,
        "👣 걷는 놈 vs 돌진 놈\n"
        "종류1(걷는 놈)은 용사를 향해 '적속도'로 꾸준히 걸어와요. 종류2(돌진 놈)는 평소엔 "
        "느리게 다가오다가 돌진틱마다 '돌진속도'로 확 대시해요 — 그래서 타이밍 피하기가 중요!",
        x=560, y=120, w=330, h=170)
    add_comment(bs, comments, hd,
        "📡 가장 가까운 적 찾기 (최솟값)\n"
        "용사가 '조준요청'을 보내면 적 클론이 하나씩 차례로 '나와 용사 거리'를 재서, "
        "지금까지 최솟값보다 가까우면 내 위치를 조준X/조준Y에 적어둬요.",
        x=760, y=180, w=320, h=150)
    return bs, comments

# ============================================================
#  강화카드 — 웨이브클리어 시 3택 (마우스 클릭 폴링 + 디바운스)
# ============================================================
def build_card_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(10)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["웨이브클리어", BR_WAVECLEAR]})
    show = gen(); bs[show] = mk("looks_show")
    set_pick0 = b_setvar(bs, "선택", V_PICK, 0)
    # 디바운스: 먼저 마우스가 떨어질 때까지 대기
    md0 = gen(); bs[md0] = mk("sensing_mousedown")
    not_md0 = gen(); bs[not_md0] = mk("operator_not", inputs={"OPERAND": [2, md0]})
    bs[md0]["parent"] = not_md0
    wu_rel0 = b_waituntil(bs, not_md0)

    # repeat until 선택>0 { if mousedown { 세로 범위 안이면 가로 범위로 선택 } }
    md = gen(); bs[md] = mk("sensing_mousedown")
    my = gen(); bs[my] = mk("sensing_mousey")
    my_lo = cmp_op("operator_gt", my, -60)
    my2 = gen(); bs[my2] = mk("sensing_mousey")
    my_hi = cmp_op("operator_lt", my2, 45)
    in_row = bool_op("operator_and", my_lo, my_hi)
    # opt1: mousex -210..-80
    mx1a = gen(); bs[mx1a] = mk("sensing_mousex"); c1a = cmp_op("operator_gt", mx1a, -210)
    mx1b = gen(); bs[mx1b] = mk("sensing_mousex"); c1b = cmp_op("operator_lt", mx1b, -80)
    in1 = bool_op("operator_and", c1a, c1b)
    set_p1 = b_setvar(bs, "선택", V_PICK, 1)
    if_p1 = b_if(bs, in1, set_p1)
    # opt2: -65..65
    mx2a = gen(); bs[mx2a] = mk("sensing_mousex"); c2a = cmp_op("operator_gt", mx2a, -65)
    mx2b = gen(); bs[mx2b] = mk("sensing_mousex"); c2b = cmp_op("operator_lt", mx2b, 65)
    in2 = bool_op("operator_and", c2a, c2b)
    set_p2 = b_setvar(bs, "선택", V_PICK, 2)
    if_p2 = b_if(bs, in2, set_p2)
    # opt3: 80..210
    mx3a = gen(); bs[mx3a] = mk("sensing_mousex"); c3a = cmp_op("operator_gt", mx3a, 80)
    mx3b = gen(); bs[mx3b] = mk("sensing_mousex"); c3b = cmp_op("operator_lt", mx3b, 210)
    in3 = bool_op("operator_and", c3a, c3b)
    set_p3 = b_setvar(bs, "선택", V_PICK, 3)
    if_p3 = b_if(bs, in3, set_p3)
    chain([(if_p1, bs[if_p1]), (if_p2, bs[if_p2]), (if_p3, bs[if_p3])])
    if_inrow = b_if(bs, in_row, if_p1)
    if_click = b_if(bs, md, if_inrow)
    w_poll = b_wait(bs, 0.02)
    chain([(if_click, bs[if_click]), (w_poll, bs[w_poll])])
    pick_r = vrep("선택", V_PICK)
    cond_picked = cmp_op("operator_gt", pick_r, 0)
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_picked], "SUBSTACK": [2, if_click]})
    bs[cond_picked]["parent"] = ru; bs[if_click]["parent"] = ru

    # 적용
    up_r1 = vrep("강화량", V_UP)
    ch_atk = b_changevar(bs, "공격력", V_ATK, up_r1)
    if_a1 = b_if(bs, cmp_op("operator_equals", vrep("선택", V_PICK), 1), ch_atk)
    # 연사속도: 발사쿨 -= 0.05*강화량, 하한 0.08
    up_r2 = vrep("강화량", V_UP); dec_amt = op("operator_multiply", 0.05, up_r2)
    neg_dec = op("operator_subtract", 0, dec_amt)
    ch_gap = b_changevar(bs, "발사쿨", V_FIREGAP, neg_dec)
    gap_r = vrep("발사쿨", V_FIREGAP)
    cond_low = cmp_op("operator_lt", gap_r, 0.08)
    set_gap_min = b_setvar(bs, "발사쿨", V_FIREGAP, 0.08)
    if_clamp = b_if(bs, cond_low, set_gap_min)
    chain([(ch_gap, bs[ch_gap]), (if_clamp, bs[if_clamp])])
    if_a2 = b_if(bs, cmp_op("operator_equals", vrep("선택", V_PICK), 2), ch_gap)
    up_r3 = vrep("강화량", V_UP)
    ch_move = b_changevar(bs, "이동속도", V_MOVE, up_r3)
    if_a3 = b_if(bs, cmp_op("operator_equals", vrep("선택", V_PICK), 3), ch_move)

    sh_up, _ = b_sound(bs, 120, "pop")
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    # 디바운스: 놓을 때까지 대기 후 전투 재개
    md2 = gen(); bs[md2] = mk("sensing_mousedown")
    not_md2 = gen(); bs[not_md2] = mk("operator_not", inputs={"OPERAND": [2, md2]})
    bs[md2]["parent"] = not_md2
    wu_rel = b_waituntil(bs, not_md2)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    chain([(hb, bs[hb]), (show, bs[show]), (set_pick0, bs[set_pick0]),
           (wu_rel0, bs[wu_rel0]), (ru, bs[ru]),
           (if_a1, bs[if_a1]), (if_a2, bs[if_a2]), (if_a3, bs[if_a3]),
           (sh_up, bs[sh_up]), (hi2, bs[hi2]), (wu_rel, bs[wu_rel]),
           (set_st1, bs[set_st1])])

    add_comment(bs, comments, hb,
        "🃏 강화 택1 (마우스 클릭 폴링 + 디바운스)\n"
        "웨이브를 클리어하면 카드가 떠요. '눌렀다 뗀' 걸 확실히 하려고 먼저 손을 떼길 기다린 뒤, "
        "누른 위치(왼/가운데/오른쪽 칸)로 1 공격력↑ / 2 연사속도↑ / 3 이동속도↑ 중 하나를 골라요. "
        "고르면 게임상태를 1로 되돌려 다음 웨이브가 시작돼요.",
        x=460, y=-40, w=340, h=180)
    return bs, comments

# ============================================================
#  체력바 — 11단 costume-fill
# ============================================================
def build_hpbar_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-158), "Y": num(-166)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})

    # forever: 코스튬 = round(체력/최대체력*10)+1  (체력 5/최대 5 → 코스튬 11 = 가득)
    hp_r = vrep("체력", V_HP); maxhp_r = vrep("최대체력", V_MAXHP)
    ratio = op("operator_divide", hp_r, maxhp_r)
    scaled = op("operator_multiply", ratio, 10)
    rounded = gen(); bs[rounded] = mk("operator_round", inputs={"NUM": slot(scaled)})
    bs[scaled]["parent"] = rounded
    idx = op("operator_add", rounded, 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(idx)})
    bs[idx]["parent"] = sw
    w = b_wait(bs, 0.05)
    chain([(sw, bs[sw]), (w, bs[w])])
    fe = b_forever(bs, sw)
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (sz, bs[sz]),
           (front, bs[front]), (rs, bs[rs]), (fe, bs[fe])])
    return bs, comments

# ============================================================
#  게임오버 / 승리 배너
# ============================================================
def build_banner_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    # forever: 게임상태=0 → 패배 show ; 게임상태=3 → 승리 show
    state0 = vrep("게임상태", V_STATE); c0 = cmp_op("operator_equals", state0, 0)
    cmL = gen(); bs[cmL] = mk("looks_costume", fields={"COSTUME": ["패배", None]}, shadow=True)
    swL = gen(); bs[swL] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmL]}); bs[cmL]["parent"] = swL
    showL = gen(); bs[showL] = mk("looks_show")
    chain([(swL, bs[swL]), (showL, bs[showL])])
    if0 = b_if(bs, c0, swL)
    state3 = vrep("게임상태", V_STATE); c3 = cmp_op("operator_equals", state3, 3)
    cmW = gen(); bs[cmW] = mk("looks_costume", fields={"COSTUME": ["승리", None]}, shadow=True)
    swW = gen(); bs[swW] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmW]}); bs[cmW]["parent"] = swW
    showW = gen(); bs[showW] = mk("looks_show")
    chain([(swW, bs[swW]), (showW, bs[showW])])
    if3 = b_if(bs, c3, swW)
    w = b_wait(bs, 0.1)
    chain([(if0, bs[if0]), (if3, bs[if3]), (w, bs[w])])
    fe = b_forever(bs, if0)
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]), (fe, bs[fe])])
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

    bg_md5     = save_svg(BG_SVG)
    idle_md5   = save_svg(HERO_IDLE_SVG)
    aim_md5    = save_svg(HERO_AIM_SVG)
    arrow_md5  = save_svg(ARROW_SVG)
    walker_md5 = save_svg(WALKER_SVG)
    dasher_md5 = save_svg(DASHER_SVG)
    ex_md5     = save_svg(EXPLOSION_SVG)
    card_md5   = save_svg(CARD_SVG)
    lose_md5   = save_svg(LOSE_SVG)
    win_md5    = save_svg(WIN_SVG)
    hpbar_md5  = [save_svg(s) for s in HPBAR_SVGS]

    def save_wav(samples):
        b = _wav_bytes(samples); m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    twang_md5, twang_n = save_wav(synth_twang())
    pop_md5, pop_n     = save_wav(synth_pop())
    hurt_md5, hurt_n   = save_wav(synth_hurt())

    def snd(name, m, n):
        return {"name": name, "assetId": m, "dataFormat": "wav", "format": "",
                "rate": SND_RATE, "sampleCount": n, "md5ext": f"{m}.wav"}
    twang_s = lambda: snd("twang", twang_md5, twang_n)
    pop_s   = lambda: snd("pop", pop_md5, pop_n)
    hurt_s  = lambda: snd("hurt", hurt_md5, hurt_n)

    stage_b,  stage_c  = build_stage_blocks()
    hero_b,   hero_c   = build_hero_blocks()
    arrow_b,  arrow_c  = build_arrow_blocks()
    enemy_b,  enemy_c  = build_enemy_blocks()
    card_b,   card_c   = build_card_blocks()
    hpbar_b,  hpbar_c  = build_hpbar_blocks()
    banner_b, banner_c = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_MOVE: ["이동속도", 5.5], V_FIREGAP: ["발사쿨", 0.25], V_ARROWSPD: ["화살속도", 11],
            V_ATK: ["공격력", 1], V_ENEMYHP: ["잡졸체력", 2], V_ENEMYSPD: ["적속도", 2.2],
            V_DASHSPD: ["돌진속도", 6], V_MAXHP: ["최대체력", 5], V_INV: ["무적시간", 0.5],
            V_WAVEBASE: ["웨이브기본수", 4], V_GROWTH: ["적성장배율", 1.25],
            V_STOPTICK: ["정지판정", 0.02], V_UP: ["강화량", 1], V_MAXWAVE: ["최대웨이브", 3],
            V_SPAWNGAP: ["스폰간격", 0.5],
            V_STATE: ["게임상태", 1], V_WAVE: ["웨이브", 0], V_ALIVE: ["적수", 0],
            V_HP: ["체력", 5], V_INVT: ["무적", 0], V_AIMD: ["조준거리", 99999],
            V_AIMX: ["조준X", 0], V_AIMY: ["조준Y", 0], V_AIMOK: ["조준있음", 0],
            V_SPX: ["적생성X", 0], V_SPY: ["적생성Y", 0], V_SPTYPE: ["적생성종류", 1],
            V_PICK: ["선택", 0],
        },
        "lists": {}, "broadcasts": {
            BR_START: "게임시작", BR_AIM: "조준요청", BR_FIRE: "발사",
            BR_SPAWN: "적생성", BR_WAVECLEAR: "웨이브클리어",
        },
        "blocks": stage_b, "comments": stage_c,
        "currentCostume": 0,
        "costumes": [{"name": "아레나", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180}],
        "sounds": [], "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    hero = {
        "isStage": False, "name": "용사",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hero_b, "comments": hero_c,
        "currentCostume": 0,
        "costumes": [
            {"name": "대기", "bitmapResolution": 1, "dataFormat": "svg", "assetId": idle_md5,
             "md5ext": f"{idle_md5}.svg", "rotationCenterX": 32, "rotationCenterY": 32},
            {"name": "겨눔", "bitmapResolution": 1, "dataFormat": "svg", "assetId": aim_md5,
             "md5ext": f"{aim_md5}.svg", "rotationCenterX": 32, "rotationCenterY": 32},
        ],
        "sounds": [twang_s(), hurt_s()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    arrow = {
        "isStage": False, "name": "화살",
        "variables": {V_ARRISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": arrow_b, "comments": arrow_c,
        "currentCostume": 0,
        "costumes": [{"name": "화살", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": arrow_md5, "md5ext": f"{arrow_md5}.svg",
            "rotationCenterX": 24, "rotationCenterY": 8}],
        "sounds": [], "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 75, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    enemy = {
        "isStage": False, "name": "적",
        "variables": {V_EISC: ["복제됨", 0], V_EHP: ["내체력", 2], V_ESPD: ["내속도", 2.2],
                      V_ETYPE: ["적종류", 1], V_EHIT: ["피격쿨", 0],
                      V_DASHT: ["돌진틱", 30], V_DASHLEFT: ["대시남음", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_b, "comments": enemy_c,
        "currentCostume": 0,
        "costumes": [
            {"name": "걷는적", "bitmapResolution": 1, "dataFormat": "svg", "assetId": walker_md5,
             "md5ext": f"{walker_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "돌진적", "bitmapResolution": 1, "dataFormat": "svg", "assetId": dasher_md5,
             "md5ext": f"{dasher_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "폭발", "bitmapResolution": 1, "dataFormat": "svg", "assetId": ex_md5,
             "md5ext": f"{ex_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 30},
        ],
        "sounds": [pop_s()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    card = {
        "isStage": False, "name": "강화카드",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": card_b, "comments": card_c,
        "currentCostume": 0,
        "costumes": [{"name": "카드", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": card_md5, "md5ext": f"{card_md5}.svg",
            "rotationCenterX": 230, "rotationCenterY": 90}],
        "sounds": [pop_s()],
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 10, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    hpbar = {
        "isStage": False, "name": "체력바",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hpbar_b, "comments": hpbar_c,
        "currentCostume": 10,
        "costumes": [
            {"name": str(s), "bitmapResolution": 1, "dataFormat": "svg", "assetId": hpbar_md5[s],
             "md5ext": f"{hpbar_md5[s]}.svg", "rotationCenterX": 70, "rotationCenterY": 13}
            for s in range(11)
        ],
        "sounds": [], "volume": 100, "layerOrder": 6, "visible": True,
        "x": -158, "y": -166, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    banner = {
        "isStage": False, "name": "배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": banner_b, "comments": banner_c,
        "currentCostume": 0,
        "costumes": [
            {"name": "패배", "bitmapResolution": 1, "dataFormat": "svg", "assetId": lose_md5,
             "md5ext": f"{lose_md5}.svg", "rotationCenterX": 180, "rotationCenterY": 75},
            {"name": "승리", "bitmapResolution": 1, "dataFormat": "svg", "assetId": win_md5,
             "md5ext": f"{win_md5}.svg", "rotationCenterX": 180, "rotationCenterY": 75},
        ],
        "sounds": [], "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_WAVE, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "웨이브"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
        {"id": V_ALIVE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "적수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 55,
         "visible": True, "sliderMin": 0, "sliderMax": 20, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, hero, arrow, enemy, card, hpbar, banner],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "archer-hero-builder"}
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
    for nm, b in [("stage", stage_b), ("hero", hero_b), ("arrow", arrow_b),
                  ("enemy", enemy_b), ("card", card_b), ("hpbar", hpbar_b),
                  ("banner", banner_b)]:
        print(f"  {nm:7s}: {len(b)} blocks"); total += len(b)
    print(f"  TOTAL  : {total} blocks")

if __name__ == "__main__":
    main()
