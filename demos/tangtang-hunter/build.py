#!/usr/bin/env python3
"""탕탕 헌터 (tangtang-hunter) — 탑뷰 수동 조준 슈터 (데모 빌드).

화살표로 8방향 이동하면서 마우스 방향으로 총알을 연사하는 탕탕특공대형 액션.
사방에서 몰려오는 잡졸을 쏘아 경험치를 모으고, 레벨업하면 강화 카드 3장 중
하나를 골라 강해진다. magic-survivor(자동공격·회피)와 정확히 반대 — "내가 직접
쏘는 손맛"이 셀링 포인트다.

데모 스코프: 핵심 루프의 손맛만 검증. 미션 사다리/긴 README/다단계 강화 생략.

베이스: games/zombie-shooter/build.py  (마우스 조준 point-towards + 클릭 발사 +
        총알/적 클론 + touching 데미지 + 무적)
      + games/magic-survivor/build.py  (경험치/레벨업/강화 택1 + 전용 합성 효과음 +
        가이드 코멘트 + 레벨 비례 적 강화)

★ 손맛 튜닝: 발사쿨 0.15초(초당 ~6발) · 총알속도 12 · 큰 총알 · 적 2발 처치 후 펑.
★ 클릭 폴링+디바운스: 강화카드는 when-clicked 대신 mousedown 폴링으로 선택.
★ 클론끼리 상호작용 금지: 총알은 touching 적 이면 자기 삭제, 적은 touching 총알 이면
  자기 체력만 줄인다(피격쿨로 한 발 = 한 대 보장). 서로의 로컬 변수를 건드리지 않는다.
"""
import json, os, wave, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "탕탕_헌터.sb3")

# ============================================================
#  효과음 합성 (전용 3종: 발사 pew / 처치 pop / 피격 hurt) — 결정적 생성
# ============================================================
SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_pew(rate=SND_RATE):
    """발사 — 짧고 톡 쏘는 하강 처프 '퓽' (연사해도 안 거슬리게 아주 짧게)."""
    N = int(rate * 0.09); out = []
    for i in range(N):
        t = i / rate
        f = 320 + 1100 * math.exp(-t * 20)       # 1420 → 320Hz 스윕
        env = math.exp(-t * 30)
        s = math.sin(2 * math.pi * f * t)
        s = (s + 0.35 * (1 if s > 0 else -1)) / 1.35
        out.append(s * env * 0.5)
    return out

def synth_pop(rate=SND_RATE):
    """처치 — 노이즈 버스트 + 저음 thump '펑' (적이 터지는 맛)."""
    N = int(rate * 0.24); out = []
    rng = random.Random(20260707); lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 13)
        white = rng.random() * 2 - 1
        lp = lp + 0.5 * (white - lp)
        thump = math.sin(2 * math.pi * (75 + 55 * math.exp(-t * 22)) * t)
        s = (lp * 0.55 + thump * 0.75) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_hurt(rate=SND_RATE):
    """피격 — 둔탁한 하강 사각파 '윽' (내가 맞았다는 경고음)."""
    N = int(rate * 0.20); out = []
    for i in range(N):
        t = i / rate
        f = 220 - 120 * t / 0.20                  # 220 → 100Hz 하강
        env = math.exp(-t * 9)
        sq = 1 if math.sin(2 * math.pi * f * t) > 0 else -1
        out.append(sq * env * 0.4)
    return out

# ============================================================
#  SVG assets
# ============================================================
# -------- 배경: 파스텔 아레나 그리드 --------
random.seed(7)
tiles = []
for ty in range(0, 360, 48):
    for tx in range(0, 480, 48):
        shade = "#EAF2FB" if (tx // 48 + ty // 48) % 2 == 0 else "#DCE8F6"
        tiles.append(f'<rect x="{tx}" y="{ty}" width="48" height="48" fill="{shade}"/>')
TILES = "\n    ".join(tiles)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#DCE8F6"/>
  <g>
    {TILES}
  </g>
  <rect x="7" y="7" width="466" height="346" rx="14" fill="none" stroke="#9DB8D6" stroke-width="6" opacity="0.8"/>
  <rect x="16" y="16" width="448" height="328" rx="10" fill="none" stroke="#B7CCE6" stroke-width="2" opacity="0.7"/>
</svg>"""

# -------- 플레이어: 탑뷰 헌터, 코스튬은 오른쪽(direction 90)이 정면 --------
#   point-towards mouse 로 회전 → 총구가 항상 마우스를 향한다.
PLAYER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 56 56">
  <ellipse cx="28" cy="30" rx="15" ry="3" fill="#000000" opacity="0.18"/>
  <!-- 총열 (오른쪽=정면) -->
  <rect x="34" y="24" width="20" height="7" rx="2" fill="#37474F" stroke="#212121" stroke-width="1.5"/>
  <rect x="46" y="22" width="6" height="11" rx="1.5" fill="#263238"/>
  <!-- 몸통 -->
  <circle cx="26" cy="28" r="15" fill="#FF7043" stroke="#D84315" stroke-width="2.5"/>
  <!-- 어깨 벨트 -->
  <path d="M16 20 Q26 30 36 38" stroke="#FFD54F" stroke-width="3.5" fill="none"/>
  <!-- 머리/고글 -->
  <circle cx="26" cy="28" r="8.5" fill="#FFE0B2" stroke="#D8A878" stroke-width="1.5"/>
  <rect x="30" y="23" width="7" height="10" rx="2" fill="#4FC3F7" stroke="#0277BD" stroke-width="1.2"/>
  <!-- 정면 표시 화살촉 -->
  <polygon points="43,28 37,24 37,32" fill="#FFEB3B" stroke="#F9A825" stroke-width="1"/>
</svg>"""

# -------- 총알: 크고 잘 보이는 노란 광탄 --------
BULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="26" height="16" viewBox="0 0 26 16">
  <ellipse cx="13" cy="8" rx="12" ry="6" fill="#FFF176" opacity="0.45"/>
  <ellipse cx="14" cy="8" rx="8.5" ry="4.2" fill="#FFEB3B" stroke="#F57F17" stroke-width="1.6"/>
  <ellipse cx="16" cy="8" rx="3" ry="1.8" fill="#FFFDE7"/>
</svg>"""

# -------- 적 잡졸: 통통한 슬라임형 (walk1 / walk2 / pop) --------
def _enemy(body, eye_dy):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="54" height="54" viewBox="0 0 54 54">
  <ellipse cx="27" cy="48" rx="15" ry="3" fill="#000000" opacity="0.2"/>
  <ellipse cx="27" cy="{body}" rx="17" ry="15" fill="#7E57C2" stroke="#4527A0" stroke-width="2.5"/>
  <circle cx="20" cy="{eye_dy}" r="4.2" fill="#FFFFFF"/>
  <circle cx="34" cy="{eye_dy}" r="4.2" fill="#FFFFFF"/>
  <circle cx="21" cy="{eye_dy}" r="2.1" fill="#1A0E3A"/>
  <circle cx="35" cy="{eye_dy}" r="2.1" fill="#1A0E3A"/>
  <path d="M20 {eye_dy+9} Q27 {eye_dy+14} 34 {eye_dy+9}" fill="none" stroke="#311B92" stroke-width="2.2" stroke-linecap="round"/>
  <polygon points="14,{body-13} 18,{body-4} 10,{body-4}" fill="#9575CD"/>
  <polygon points="40,{body-13} 44,{body-4} 36,{body-4}" fill="#9575CD"/>
</svg>"""
ENEMY1_SVG = _enemy(29, 26)
ENEMY2_SVG = _enemy(27, 24)
ENEMY_POP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="54" height="54" viewBox="0 0 54 54">
  <polygon points="27,3 32,20 49,15 36,27 49,39 32,34 27,51 22,34 5,39 18,27 5,15 22,20"
           fill="#FFB300" stroke="#E65100" stroke-width="1.5"/>
  <circle cx="27" cy="27" r="11" fill="#FFEB3B"/>
  <circle cx="27" cy="27" r="5" fill="#FFFFFF"/>
</svg>"""

# -------- 강화 카드: 3장 (공격력+ / 연사속도+ / 이동속도+) --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="420" height="180" viewBox="0 0 420 180">
  <rect x="4" y="4" width="412" height="172" rx="16" fill="#1A237E" opacity="0.96" stroke="#FFD54F" stroke-width="4"/>
  <text x="210" y="34" text-anchor="middle" fill="#FFD54F" font-family="Arial, sans-serif" font-size="22" font-weight="bold">레벨업! 강화 카드를 클릭</text>
  <rect x="16" y="48" width="120" height="118" rx="12" fill="#C62828" stroke="#FFFFFF" stroke-width="2"/>
  <text x="76" y="98" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="40" font-weight="bold">1</text>
  <text x="76" y="140" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16" font-weight="bold">공격력 +</text>
  <rect x="150" y="48" width="120" height="118" rx="12" fill="#2E7D32" stroke="#FFFFFF" stroke-width="2"/>
  <text x="210" y="98" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="40" font-weight="bold">2</text>
  <text x="210" y="140" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16" font-weight="bold">연사속도 +</text>
  <rect x="284" y="48" width="120" height="118" rx="12" fill="#1565C0" stroke="#FFFFFF" stroke-width="2"/>
  <text x="344" y="98" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="40" font-weight="bold">3</text>
  <text x="344" y="140" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16" font-weight="bold">이동속도 +</text>
</svg>"""

# -------- 게임오버 배너 --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="70" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="106" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="19">점수는 왼쪽 위에서 확인!</text>
  <text x="180" y="136" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# -------- 체력바 / 경험치바: 11단 costume-fill --------
def _bar_svg(frac, fill, back):
    w = int(round(112 * frac))
    inner = f'<rect x="4" y="4" width="{w}" height="16" rx="4" fill="{fill}"/>' if w > 0 else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="24" viewBox="0 0 120 24">
  <rect x="1" y="1" width="118" height="22" rx="6" fill="{back}" stroke="#33373F" stroke-width="2"/>
  {inner}
</svg>"""
HP_BAR_SVGS  = [_bar_svg(i / 10, "#E53935", "#3A2226") for i in range(11)]
XP_BAR_SVGS  = [_bar_svg(i / 10, "#29B6F6", "#1E2A33") for i in range(11)]

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
    m = gen(); bs[m] = mk("sensing_keyoptions", fields={"KEY_OPTION": [key, None]}, shadow=True)
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
    bid = gen()
    if isinstance(dur, str) and dur in bs:
        bs[bid] = mk("control_wait", inputs={"DURATION": slot(dur)})
        bs[dur]["parent"] = bid
    else:
        bs[bid] = mk("control_wait", inputs={"DURATION": num(dur)})
    return bid

def b_broadcast(bs, name, brid):
    m = gen(); bs[m] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcast", inputs={"BROADCAST_INPUT": [1, m]})
    bs[m]["parent"] = b
    return b

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
# ----- 튜닝 손잡이 12개 (아이가 바꾸며 노는 값) -----
V_MOVE     = "varMove01"     # 이동속도      5
V_FIREGAP  = "varFireGap02"  # 발사쿨        0.15  (작을수록 빠른 연사)
V_BOLTSPD  = "varBoltSpd03"  # 총알속도      12
V_ATK      = "varAtk04"      # 공격력        1
V_EHP0     = "varEHP05"      # 잡졸체력      2
V_ESPD     = "varESpd06"     # 적속도        2.5
V_SPAWNGAP = "varSpawn07"    # 스폰간격      0.8
V_MAXHP    = "varMaxHP08"    # 최대체력      5
V_INVSEC   = "varInvSec09"   # 무적시간      0.5
V_LVUP     = "varLvUp10"     # 레벨업경험치   8
V_RAMP     = "varRamp11"     # 적성장배율    1.2
V_EXPGAIN  = "varExpGain12"  # 경험치획득    1

# ----- 진행 상태 -----
V_STATE  = "varState20"   # 게임상태 1=전투 2=강화선택 0=게임오버
V_SCORE  = "varScore21"   # 점수(처치수)
V_LEVEL  = "varLevel22"   # 레벨
V_EXP    = "varExp23"     # 경험치
V_HP     = "varHP24"      # 내체력(현재)
V_INV    = "varInv25"     # 무적(초 카운트다운)
V_SX     = "varSX26"      # 스폰X
V_SY     = "varSY27"      # 스폰Y
V_BX     = "varBX28"      # 총알X
V_BY     = "varBY29"      # 총알Y
V_BDIR   = "varBDir30"    # 총알방향

# ----- 적 클론-로컬 -----
V_ENHP  = "varEnHP40"     # 적 클론: 적체력
V_ESP   = "varEnSp41"     # 적 클론: 이속(스폰 시 레벨 반영)
V_HITCD = "varHitCd42"    # 적 클론: 피격쿨(한 발=한 대 보장)

# ----- 메시지 -----
BR_START   = "brStart01"
BR_FIRE    = "brFire02"
BR_SPAWN   = "brSpawn03"
BR_LEVELUP = "brLevelup04"

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발: 튜닝+진행 변수 초기화 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add(name, vid, val):
        sid = b_setvar(bs, name, vid, val); seq.append((sid, bs[sid]))
    # 튜닝 12
    add("이동속도", V_MOVE, 5)
    add("발사쿨", V_FIREGAP, 0.15)
    add("총알속도", V_BOLTSPD, 12)
    add("공격력", V_ATK, 1)
    add("잡졸체력", V_EHP0, 2)
    add("적속도", V_ESPD, 2.5)
    add("스폰간격", V_SPAWNGAP, 0.8)
    add("최대체력", V_MAXHP, 5)
    add("무적시간", V_INVSEC, 0.5)
    add("레벨업경험치", V_LVUP, 8)
    add("적성장배율", V_RAMP, 1.2)
    add("경험치획득", V_EXPGAIN, 1)
    # 진행
    add("게임상태", V_STATE, 1)
    add("점수", V_SCORE, 0)
    add("레벨", V_LEVEL, 1)
    add("경험치", V_EXP, 0)
    maxhp_r = vrep("최대체력", V_MAXHP)
    sid = b_setvar(bs, "내체력", V_HP, maxhp_r); seq.append((sid, bs[sid]))
    add("무적", V_INV, 0)
    add("스폰X", V_SX, 0)
    add("스폰Y", V_SY, 0)
    add("총알X", V_BX, 0)
    add("총알Y", V_BY, 0)
    add("총알방향", V_BDIR, 90)
    w1 = b_wait(bs, 0.4); seq.append((w1, bs[w1]))
    bc = b_broadcast(bs, "게임시작", BR_START); seq.append((bc, bs[bc]))
    chain(seq)

    # ===== (B) on 게임시작: 적 스폰 루프 (가장자리 랜덤) =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=340, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # side = random 1..4 (스폰X 에 임시 저장 후 분기 — zombie-shooter 기법)
    side_pick = gen(); bs[side_pick] = mk("operator_random", inputs={"FROM": num(1), "TO": num(4)})
    set_side = gen(); bs[set_side] = mk("data_setvariableto",
        inputs={"VALUE": slot(side_pick)}, fields={"VARIABLE": ["스폰X", V_SX]})
    bs[side_pick]["parent"] = set_side

    def rand(lo, hi):
        r = gen(); bs[r] = mk("operator_random", inputs={"FROM": num(lo), "TO": num(hi)}); return r
    # side 1 위 : X rand, Y=180
    sv1 = vrep("스폰X", V_SX); c1 = cmp_op("operator_equals", sv1, 1)
    a_x = gen(); bs[a_x] = mk("data_setvariableto", inputs={"VALUE": slot(rand(-220,220))}, fields={"VARIABLE": ["스폰X", V_SX]})
    bs[bs[a_x]["inputs"]["VALUE"][1]]["parent"] = a_x
    a_y = b_setvar(bs, "스폰Y", V_SY, 185); chain([(a_x, bs[a_x]), (a_y, bs[a_y])])
    if1 = b_if(bs, c1, a_x)
    # side 2 아래 : X rand, Y=-185
    sv2 = vrep("스폰X", V_SX); c2 = cmp_op("operator_equals", sv2, 2)
    b_x = gen(); bs[b_x] = mk("data_setvariableto", inputs={"VALUE": slot(rand(-220,220))}, fields={"VARIABLE": ["스폰X", V_SX]})
    bs[bs[b_x]["inputs"]["VALUE"][1]]["parent"] = b_x
    b_y = b_setvar(bs, "스폰Y", V_SY, -185); chain([(b_x, bs[b_x]), (b_y, bs[b_y])])
    if2 = b_if(bs, c2, b_x)
    # side 3 왼 : X=-245, Y rand
    sv3 = vrep("스폰X", V_SX); c3 = cmp_op("operator_equals", sv3, 3)
    c_y = gen(); bs[c_y] = mk("data_setvariableto", inputs={"VALUE": slot(rand(-160,160))}, fields={"VARIABLE": ["스폰Y", V_SY]})
    bs[bs[c_y]["inputs"]["VALUE"][1]]["parent"] = c_y
    c_x = b_setvar(bs, "스폰X", V_SX, -245); chain([(c_y, bs[c_y]), (c_x, bs[c_x])])
    if3 = b_if(bs, c3, c_y)
    # side 4 오른 (else): X=245, Y rand
    sv4 = vrep("스폰X", V_SX); c4 = cmp_op("operator_equals", sv4, 4)
    d_y = gen(); bs[d_y] = mk("data_setvariableto", inputs={"VALUE": slot(rand(-160,160))}, fields={"VARIABLE": ["스폰Y", V_SY]})
    bs[bs[d_y]["inputs"]["VALUE"][1]]["parent"] = d_y
    d_x = b_setvar(bs, "스폰X", V_SX, 245); chain([(d_y, bs[d_y]), (d_x, bs[d_x])])
    if4 = b_if(bs, c4, d_y)

    bc_sp = b_broadcast(bs, "적스폰", BR_SPAWN)
    chain([(set_side, bs[set_side]), (if1, bs[if1]), (if2, bs[if2]),
           (if3, bs[if3]), (if4, bs[if4]), (bc_sp, bs[bc_sp])])
    # if 게임상태=1 : 스폰
    st_b = vrep("게임상태", V_STATE); c_play = cmp_op("operator_equals", st_b, 1)
    if_play = b_if(bs, c_play, set_side)
    # wait 스폰간격
    gap_r = vrep("스폰간격", V_SPAWNGAP)
    wsp = gen(); bs[wsp] = mk("control_wait", inputs={"DURATION": slot(gap_r)}); bs[gap_r]["parent"] = wsp
    chain([(if_play, bs[if_play]), (wsp, bs[wsp])])
    fe_b = b_forever(bs, if_play)
    chain([(hb, bs[hb]), (fe_b, bs[fe_b])])

    # ===== (C) 깃발: 무적 카운트다운 forever =====
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=520)
    inv_r = vrep("무적", V_INV); c_inv = cmp_op("operator_gt", inv_r, 0)
    dec_inv = b_changevar(bs, "무적", V_INV, -0.025)
    if_inv = b_if(bs, c_inv, dec_inv)
    wc = b_wait(bs, 0.025)
    chain([(if_inv, bs[if_inv]), (wc, bs[wc])])
    fe_c = b_forever(bs, if_inv)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # ===== (D) 깃발: 레벨업 / 게임오버 감시 forever =====
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=340, y=520)
    # 레벨업: 경험치 >= 레벨업경험치 and 게임상태=1
    exp_r = vrep("경험치", V_EXP); lv_r = vrep("레벨업경험치", V_LVUP)
    c_lt = cmp_op("operator_lt", exp_r, lv_r)
    not_lt = gen(); bs[not_lt] = mk("operator_not", inputs={"OPERAND": [2, c_lt]}); bs[c_lt]["parent"] = not_lt
    st_d = vrep("게임상태", V_STATE); c_pl = cmp_op("operator_equals", st_d, 1)
    c_up = bool_op("operator_and", not_lt, c_pl)
    lv_r2 = vrep("레벨업경험치", V_LVUP)
    neg = op("operator_subtract", 0, lv_r2)
    dec_exp = b_changevar(bs, "경험치", V_EXP, neg)
    inc_lv = b_changevar(bs, "레벨", V_LEVEL, 1)
    grow = b_changevar(bs, "레벨업경험치", V_LVUP, 4)  # 다음 레벨은 조금 더 비싸게
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_lv = b_broadcast(bs, "레벨업", BR_LEVELUP)
    chain([(dec_exp, bs[dec_exp]), (inc_lv, bs[inc_lv]), (grow, bs[grow]),
           (set_st2, bs[set_st2]), (bc_lv, bs[bc_lv])])
    if_up = b_if(bs, c_up, dec_exp)
    # 게임오버: 내체력<1 and 게임상태=1
    hp_r = vrep("내체력", V_HP); c_dead = cmp_op("operator_lt", hp_r, 1)
    st_d2 = vrep("게임상태", V_STATE); c_pl2 = cmp_op("operator_equals", st_d2, 1)
    c_over = bool_op("operator_and", c_dead, c_pl2)
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    if_over = b_if(bs, c_over, set_st0)
    wd = b_wait(bs, 0.05)
    chain([(if_up, bs[if_up]), (if_over, bs[if_over]), (wd, bs[wd])])
    fe_d = b_forever(bs, if_up)
    chain([(hd, bs[hd]), (fe_d, bs[fe_d])])

    # ── 가이드 코멘트 ──
    add_comment(bs, comments, h,
        "⚙️ 개조 손잡이 (여기가 핵심!)\n"
        "게임의 모든 숫자가 이 초록 깃발 묶음에 한글 변수로 모여 있어요.\n"
        "발사쿨(0.15)을 줄이면 총알이 더 빨리 나가고, 총알속도(12)를 키우면 더 멀리 "
        "쭉 날아가요. 하나만 바꿔서 '이렇게 될 것 같다'를 먼저 예상하고 ▶ 눌러 보세요!",
        x=-380, y=-40, w=330, h=180)
    add_comment(bs, comments, hb,
        "👾 적 스폰기\n"
        "화면 네 가장자리(위·아래·왼·오른) 중 하나를 랜덤으로 골라 적을 계속 내보내요. "
        "스폰간격(0.8초)을 줄이면 적이 더 우르르 몰려와요.",
        x=560, y=-20, w=300, h=140)
    add_comment(bs, comments, if_up,
        "⭐ 레벨업 판정\n"
        "경험치가 레벨업경험치(8) 이상이 되면 게임상태를 2(강화선택)로 바꾸고 카드를 띄워요. "
        "카드에서 공격력·연사속도·이동속도 중 하나를 골라 강해져요.",
        x=560, y=520, w=300, h=150)
    return bs, comments

# ============================================================
#  플레이어
# ============================================================
def build_player_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발: 세팅
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (rs, bs[rs]), (g0, bs[g0]), (front, bs[front])])

    # (B) 깃발: 조준 + 이동 forever
    hb = gen(); bs[hb] = mk("event_whenflagclicked", top=True, x=20, y=220)
    aim = b_pointtowards(bs, "_mouse_")           # 항상 마우스 조준
    # 이동은 게임상태=1 일 때만
    move_r1 = vrep("이동속도", V_MOVE)
    cxr = gen(); bs[cxr] = mk("motion_changexby", inputs={"DX": slot(move_r1)}); bs[move_r1]["parent"] = cxr
    if_r = b_if(bs, b_keypressed(bs, "right arrow"), cxr)
    move_r2 = vrep("이동속도", V_MOVE); neg2 = op("operator_subtract", 0, move_r2)
    cxl = gen(); bs[cxl] = mk("motion_changexby", inputs={"DX": slot(neg2)}); bs[neg2]["parent"] = cxl
    if_l = b_if(bs, b_keypressed(bs, "left arrow"), cxl)
    move_r3 = vrep("이동속도", V_MOVE)
    cyu = gen(); bs[cyu] = mk("motion_changeyby", inputs={"DY": slot(move_r3)}); bs[move_r3]["parent"] = cyu
    if_u = b_if(bs, b_keypressed(bs, "up arrow"), cyu)
    move_r4 = vrep("이동속도", V_MOVE); neg4 = op("operator_subtract", 0, move_r4)
    cyd = gen(); bs[cyd] = mk("motion_changeyby", inputs={"DY": slot(neg4)}); bs[neg4]["parent"] = cyd
    if_d = b_if(bs, b_keypressed(bs, "down arrow"), cyd)
    # clamp
    def clamp(pos_op, cmpop, lim, set_op, key):
        xp = gen(); bs[xp] = mk(pos_op)
        c = cmp_op(cmpop, xp, lim)
        st = gen(); bs[st] = mk(set_op, inputs={key: num(lim)})
        return b_if(bs, c, st)
    cl1 = clamp("motion_xposition", "operator_gt", 232, "motion_setx", "X")
    cl2 = clamp("motion_xposition", "operator_lt", -232, "motion_setx", "X")
    cl3 = clamp("motion_yposition", "operator_gt", 166, "motion_sety", "Y")
    cl4 = clamp("motion_yposition", "operator_lt", -166, "motion_sety", "Y")
    st_m = vrep("게임상태", V_STATE); c_m = cmp_op("operator_equals", st_m, 1)
    chain([(if_r, bs[if_r]), (if_l, bs[if_l]), (if_u, bs[if_u]), (if_d, bs[if_d]),
           (cl1, bs[cl1]), (cl2, bs[cl2]), (cl3, bs[cl3]), (cl4, bs[cl4])])
    if_move = b_if(bs, c_m, if_r)
    chain([(aim, bs[aim]), (if_move, bs[if_move])])  # forever body: aim always, move if playing
    fe_b = b_forever(bs, aim)
    chain([(hb, bs[hb]), (fe_b, bs[fe_b])])

    # (C) 깃발: 발사 폴링 forever (마우스다운/스페이스 + 발사쿨)
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=340, y=20)
    md = gen(); bs[md] = mk("sensing_mousedown")
    spc = b_keypressed(bs, "space")
    fire_in = bool_op("operator_or", md, spc)
    st_f = vrep("게임상태", V_STATE); c_f = cmp_op("operator_equals", st_f, 1)
    c_can = bool_op("operator_and", fire_in, c_f)
    bc_fire = b_broadcast(bs, "발사", BR_FIRE)
    gap_r = vrep("발사쿨", V_FIREGAP)
    wfire = gen(); bs[wfire] = mk("control_wait", inputs={"DURATION": slot(gap_r)}); bs[gap_r]["parent"] = wfire
    chain([(bc_fire, bs[bc_fire]), (wfire, bs[wfire])])
    if_fire = b_if(bs, c_can, bc_fire)
    fe_c = b_forever(bs, if_fire)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # (D) on 발사: 총알 좌표/방향 채널 세팅 + pew + 클론 생성
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=340, y=260,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    xp = gen(); bs[xp] = mk("motion_xposition")
    set_bx = gen(); bs[set_bx] = mk("data_setvariableto", inputs={"VALUE": slot(xp)}, fields={"VARIABLE": ["총알X", V_BX]}); bs[xp]["parent"] = set_bx
    yp = gen(); bs[yp] = mk("motion_yposition")
    set_by = gen(); bs[set_by] = mk("data_setvariableto", inputs={"VALUE": slot(yp)}, fields={"VARIABLE": ["총알Y", V_BY]}); bs[yp]["parent"] = set_by
    dr = gen(); bs[dr] = mk("motion_direction")
    set_bd = gen(); bs[set_bd] = mk("data_setvariableto", inputs={"VALUE": slot(dr)}, fields={"VARIABLE": ["총알방향", V_BDIR]}); bs[dr]["parent"] = set_bd
    s1, s2 = b_sound(bs, 140, "pew")
    cm = gen(); bs[cm] = mk("control_create_clone_of_menu", fields={"CLONE_OPTION": ["총알", None]}, shadow=True)
    cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cm]}); bs[cm]["parent"] = cc
    chain([(hd, bs[hd]), (set_bx, bs[set_bx]), (set_by, bs[set_by]), (set_bd, bs[set_bd]),
           (s1, bs[s1]), (cc, bs[cc])])

    add_comment(bs, comments, hc,
        "🔫 연사 폴링 + 디바운스\n"
        "마우스 버튼(또는 스페이스)을 '누르고 있는 동안' 발사쿨(0.15초)마다 한 발씩 나가요. "
        "when-clicked 가 아니라 계속 확인(폴링)하는 방식이라 꾹 누르면 드르륵 연사돼요.",
        x=560, y=-20, w=320, h=150)
    add_comment(bs, comments, hd,
        "➡️ 마우스 방향 발사\n"
        "총알을 만들기 직전 내 x·y와 '내가 바라보는 방향'을 총알 채널에 저장해요. "
        "플레이어는 늘 마우스를 바라보니까(위 조준 블록) 총알은 마우스 쪽으로 날아가요.",
        x=560, y=260, w=320, h=150)
    return bs, comments

# ============================================================
#  총알
# ============================================================
def build_bullet_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(130)})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)
    bx = vrep("총알X", V_BX); by = vrep("총알Y", V_BY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(bx), "Y": slot(by)}); bs[bx]["parent"] = g; bs[by]["parent"] = g
    bd = vrep("총알방향", V_BDIR)
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": slot(bd)}); bs[bd]["parent"] = pd
    show = gen(); bs[show] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    # 비행 루프 — move 총알속도 (vrep 리포터로 넘김: 변수 id 함정 회피)
    move_r = vrep("총알속도", V_BOLTSPD)
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": slot(move_r)}); bs[move_r]["parent"] = mv
    wit = b_wait(bs, 0.016)
    chain([(mv, bs[mv]), (wit, bs[wit])])
    # 정지 조건: 화면 밖 OR touching 적 OR 게임상태=0
    xp = gen(); bs[xp] = mk("motion_xposition"); cx_hi = cmp_op("operator_gt", xp, 245)
    xp2 = gen(); bs[xp2] = mk("motion_xposition"); cx_lo = cmp_op("operator_lt", xp2, -245)
    cx = bool_op("operator_or", cx_hi, cx_lo)
    yp = gen(); bs[yp] = mk("motion_yposition"); cy_hi = cmp_op("operator_gt", yp, 185)
    yp2 = gen(); bs[yp2] = mk("motion_yposition"); cy_lo = cmp_op("operator_lt", yp2, -185)
    cy = bool_op("operator_or", cy_hi, cy_lo)
    off = bool_op("operator_or", cx, cy)
    tch = b_touching(bs, "적")
    st = vrep("게임상태", V_STATE); c0 = cmp_op("operator_equals", st, 0)
    stop1 = bool_op("operator_or", off, tch)
    stop = bool_op("operator_or", stop1, c0)
    ru = b_repeat_until(bs, stop, mv)
    # 명중 후 한 프레임 더 보이게 머문다 → 적 스크립트가 실행 순서와 무관하게
    # touching 총알 을 확실히 감지(같은 프레임 순서 경쟁 방지). 손맛엔 영향 거의 없음.
    wlin = b_wait(bs, 0.03)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    dl = gen(); bs[dl] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (g, bs[g]), (pd, bs[pd]), (show, bs[show]), (front, bs[front]),
           (ru, bs[ru]), (wlin, bs[wlin]), (hi2, bs[hi2]), (dl, bs[dl])])

    add_comment(bs, comments, ch,
        "💥 총알 클론 = 손맛의 핵심\n"
        "발사 채널에 저장된 위치·방향으로 나타나 총알속도(12)만큼 쭉 날아가요. "
        "화면 밖으로 나가거나 적에게 닿으면(touching 적) 스스로 사라져요. "
        "적의 체력은 적이 스스로 줄여요 — 클론끼리 서로의 변수를 건드리지 않아요.",
        x=300, y=180, w=330, h=170)
    return bs, comments

# ============================================================
#  적 (잡졸)
# ============================================================
def build_enemy_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    # on 적스폰 → 클론 생성
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["적스폰", BR_SPAWN]})
    cm = gen(); bs[cm] = mk("control_create_clone_of_menu", fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cm]}); bs[cm]["parent"] = cc
    chain([(h2, bs[h2]), (cc, bs[cc])])

    # 클론 시작
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=340, y=20)
    sx = vrep("스폰X", V_SX); sy = vrep("스폰Y", V_SY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(sx), "Y": slot(sy)}); bs[sx]["parent"] = g; bs[sy]["parent"] = g
    # 크기/유령 리셋(팝 애니 재사용 대비)
    sz2 = gen(); bs[sz2] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    gh0 = gen(); bs[gh0] = mk("looks_seteffectto", inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    cm0 = gen(); bs[cm0] = mk("looks_costume", fields={"COSTUME": ["walk1", None]}, shadow=True)
    swc = gen(); bs[swc] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm0]}); bs[cm0]["parent"] = swc
    show = gen(); bs[show] = mk("looks_show")
    # 적체력 = 잡졸체력 + (레벨-1)  ; 레벨 비례 강화 (magic-survivor 교훈)
    ehp0 = vrep("잡졸체력", V_EHP0); lvl_a = vrep("레벨", V_LEVEL)
    lvm1 = op("operator_subtract", lvl_a, 1)
    hp_calc = op("operator_add", ehp0, lvm1)
    set_hp = b_setvar(bs, "적체력", V_ENHP, hp_calc)
    # 이속 = 적속도 + (레벨-1)*(적성장배율-1)
    esp0 = vrep("적속도", V_ESPD); lvl_b = vrep("레벨", V_LEVEL)
    lvm1b = op("operator_subtract", lvl_b, 1)
    ramp = vrep("적성장배율", V_RAMP); ramm1 = op("operator_subtract", ramp, 1)
    sp_add = op("operator_multiply", lvm1b, ramm1)
    sp_calc = op("operator_add", esp0, sp_add)
    set_sp = b_setvar(bs, "이속", V_ESP, sp_calc)
    set_cd = b_setvar(bs, "피격쿨", V_HITCD, 0)

    # 추적/피격 루프: repeat until 적체력<1 OR 게임상태=0
    pt = b_pointtowards(bs, "플레이어")
    mv = gen(); mv_r = vrep("이속", V_ESP); bs[mv] = mk("motion_movesteps", inputs={"STEPS": slot(mv_r)}); bs[mv_r]["parent"] = mv
    # 피격쿨 감소
    cd_r = vrep("피격쿨", V_HITCD); c_cd = cmp_op("operator_gt", cd_r, 0)
    dec_cd = b_changevar(bs, "피격쿨", V_HITCD, -1)
    if_cd = b_if(bs, c_cd, dec_cd)
    # 총알 명중: touching 총알 and 피격쿨=0 → 적체력 -= 공격력, 피격쿨=4
    tb = b_touching(bs, "총알")
    cd_r2 = vrep("피격쿨", V_HITCD); c_cd0 = cmp_op("operator_equals", cd_r2, 0)
    c_hit = bool_op("operator_and", tb, c_cd0)
    atk_r = vrep("공격력", V_ATK); negatk = op("operator_subtract", 0, atk_r)
    dmg = b_changevar(bs, "적체력", V_ENHP, negatk)
    set_cd2 = b_setvar(bs, "피격쿨", V_HITCD, 4)
    chain([(dmg, bs[dmg]), (set_cd2, bs[set_cd2])])
    if_hit = b_if(bs, c_hit, dmg)
    # 플레이어 접촉 피해: touching 플레이어 and 무적=0 → 내체력-1, 무적=무적시간, hurt
    tp = b_touching(bs, "플레이어")
    inv_r = vrep("무적", V_INV); c_i0 = cmp_op("operator_equals", inv_r, 0)
    c_pl = bool_op("operator_and", tp, c_i0)
    dec_php = b_changevar(bs, "내체력", V_HP, -1)
    invsec = vrep("무적시간", V_INVSEC)
    set_inv = gen(); bs[set_inv] = mk("data_setvariableto", inputs={"VALUE": slot(invsec)}, fields={"VARIABLE": ["무적", V_INV]}); bs[invsec]["parent"] = set_inv
    sh1, sh2 = b_sound(bs, -180, "hurt")
    chain([(dec_php, bs[dec_php]), (set_inv, bs[set_inv]), (sh1, bs[sh1])])
    if_pl = b_if(bs, c_pl, dec_php)
    wit = b_wait(bs, 0.02)
    chain([(pt, bs[pt]), (mv, bs[mv]), (if_cd, bs[if_cd]), (if_hit, bs[if_hit]), (if_pl, bs[if_pl]), (wit, bs[wit])])
    # 정지조건
    ehp_r = vrep("적체력", V_ENHP); c_ded = cmp_op("operator_lt", ehp_r, 1)
    st_r = vrep("게임상태", V_STATE); c_st0 = cmp_op("operator_equals", st_r, 0)
    c_stop = bool_op("operator_or", c_ded, c_st0)
    ru = b_repeat_until(bs, c_stop, pt)

    # 루프 후: 적체력<1 이면 처치 처리 (점수/경험치/팝)
    ehp_r2 = vrep("적체력", V_ENHP); c_killed = cmp_op("operator_lt", ehp_r2, 1)
    inc_sc = b_changevar(bs, "점수", V_SCORE, 1)
    expg = vrep("경험치획득", V_EXPGAIN)
    inc_exp = gen(); bs[inc_exp] = mk("data_changevariableby", inputs={"VALUE": slot(expg)}, fields={"VARIABLE": ["경험치", V_EXP]}); bs[expg]["parent"] = inc_exp
    sp1, sp2 = b_sound(bs, 30, "pop")
    cmp_ = gen(); bs[cmp_] = mk("looks_costume", fields={"COSTUME": ["pop", None]}, shadow=True)
    swpop = gen(); bs[swpop] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmp_]}); bs[cmp_]["parent"] = swpop
    # 팝 애니: repeat 5 { change size -8, change ghost +18, wait 0.02 }
    csz = gen(); bs[csz] = mk("looks_changesizeby", inputs={"CHANGE": num(-8)})
    cgh = gen(); bs[cgh] = mk("looks_changeeffectby", inputs={"CHANGE": num(18)}, fields={"EFFECT": ["GHOST", None]})
    wpop = b_wait(bs, 0.02)
    chain([(csz, bs[csz]), (cgh, bs[cgh]), (wpop, bs[wpop])])
    rep_pop = b_repeat(bs, 5, csz)
    chain([(inc_sc, bs[inc_sc]), (inc_exp, bs[inc_exp]), (sp1, bs[sp1]), (swpop, bs[swpop]), (rep_pop, bs[rep_pop])])
    if_killed = b_if(bs, c_killed, inc_sc)

    hi2 = gen(); bs[hi2] = mk("looks_hide")
    dl = gen(); bs[dl] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (g, bs[g]), (sz2, bs[sz2]), (gh0, bs[gh0]), (swc, bs[swc]), (show, bs[show]),
           (set_hp, bs[set_hp]), (set_sp, bs[set_sp]), (set_cd, bs[set_cd]),
           (ru, bs[ru]), (if_killed, bs[if_killed]), (hi2, bs[hi2]), (dl, bs[dl])])

    # 걸음 애니: 클론이 살아있는 동안 코스튬 토글 (게임상태=1 일 때만)
    h3 = gen(); bs[h3] = mk("control_start_as_clone", top=True, x=340, y=420)
    st_a = vrep("게임상태", V_STATE); c_a = cmp_op("operator_equals", st_a, 1)
    nc = gen(); bs[nc] = mk("looks_nextcostume")
    # pop 코스튬으로 넘어가지 않게 walk1/walk2 만 토글: if costume# < 3 이면 next, 아니면 walk1
    cn = gen(); bs[cn] = mk("looks_costumenumbername", fields={"NUMBER_NAME": ["number", None]})
    c_wlk = cmp_op("operator_lt", cn, 2)
    cw1 = gen(); bs[cw1] = mk("looks_costume", fields={"COSTUME": ["walk2", None]}, shadow=True)
    to2 = gen(); bs[to2] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cw1]}); bs[cw1]["parent"] = to2
    cw2 = gen(); bs[cw2] = mk("looks_costume", fields={"COSTUME": ["walk1", None]}, shadow=True)
    to1 = gen(); bs[to1] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cw2]}); bs[cw2]["parent"] = to1
    toggle = b_ifelse(bs, c_wlk, to2, to1)
    if_anim = b_if(bs, c_a, toggle)
    wanim = b_wait(bs, 0.22)
    chain([(if_anim, bs[if_anim]), (wanim, bs[wanim])])
    fe_anim = b_forever(bs, if_anim)
    chain([(h3, bs[h3]), (fe_anim, bs[fe_anim])])

    add_comment(bs, comments, ch,
        "👾 적 클론\n"
        "가장자리에서 나타나 플레이어를 향해 곧장 걸어와요(point towards 플레이어). "
        "적체력 = 잡졸체력(2) + (레벨-1) 이라서 내가 레벨업할수록 적도 조금씩 단단해져요. "
        "총알에 닿을 때마다 스스로 적체력을 줄이고(피격쿨로 한 발=한 대), 0이 되면 펑!",
        x=560, y=0, w=340, h=180)
    return bs, comments

# ============================================================
#  강화 카드 (클릭 폴링 + 디바운스)
# ============================================================
def build_card_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    # on 레벨업: 카드 표시 → 클릭 폴링/디바운스 → 스탯 적용 → 게임상태=1
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["레벨업", BR_LEVELUP]})
    show = gen(); bs[show] = mk("looks_show")
    fr2 = gen(); bs[fr2] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    # 디바운스: 먼저 마우스를 뗀 상태가 될 때까지 대기(직전 클릭 잔상 방지)
    md0 = gen(); bs[md0] = mk("sensing_mousedown")
    not_md = gen(); bs[not_md] = mk("operator_not", inputs={"OPERAND": [2, md0]}); bs[md0]["parent"] = not_md
    wdb = b_wait_until(bs, not_md)

    # 폴링 루프: repeat until 게임상태=1 (유효 선택 시 탈출)
    md = gen(); bs[md] = mk("sensing_mousedown")
    mx = gen(); bs[mx] = mk("sensing_mousex")
    my = gen(); bs[my] = mk("sensing_mousey")
    # y 밴드: |마우스y| < 95 (카드 세로 범위 내)
    absy = gen(); bs[absy] = mk("operator_mathop", inputs={"NUM": slot(my)}, fields={"OPERATOR": ["abs", None]}); bs[my]["parent"] = absy
    c_yband = cmp_op("operator_lt", absy, 95)
    c_clickzone = bool_op("operator_and", md, c_yband)
    # 존1 공격력: 마우스x < -70
    mx1 = gen(); bs[mx1] = mk("sensing_mousex"); c_z1 = cmp_op("operator_lt", mx1, -70)
    ap_atk = b_changevar(bs, "공격력", V_ATK, 1)
    # 존3 이동속도: 마우스x > 70
    mx3 = gen(); bs[mx3] = mk("sensing_mousex"); c_z3 = cmp_op("operator_gt", mx3, 70)
    ap_move = b_changevar(bs, "이동속도", V_MOVE, 1)
    # 존2 연사속도(그 외): 발사쿨 *= 0.82  (작아질수록 빨라짐)
    gap_r = vrep("발사쿨", V_FIREGAP); mul = op("operator_multiply", gap_r, 0.82)
    ap_fire = b_setvar(bs, "발사쿨", V_FIREGAP, mul)
    # if z1 {atk} else { if z3 {move} else {fire} }
    inner_else = b_ifelse(bs, c_z3, ap_move, ap_fire)
    choose = b_ifelse(bs, c_z1, ap_atk, inner_else)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    # 디바운스: 선택 후 마우스 뗄 때까지 대기
    md2 = gen(); bs[md2] = mk("sensing_mousedown")
    not_md2 = gen(); bs[not_md2] = mk("operator_not", inputs={"OPERAND": [2, md2]}); bs[md2]["parent"] = not_md2
    wdb2 = b_wait_until(bs, not_md2)
    chain([(choose, bs[choose]), (set_st1, bs[set_st1]), (wdb2, bs[wdb2])])
    if_click = b_if(bs, c_clickzone, choose)
    w_poll = b_wait(bs, 0.02)
    chain([(if_click, bs[if_click]), (w_poll, bs[w_poll])])
    st_c = vrep("게임상태", V_STATE); c_done = cmp_op("operator_equals", st_c, 1)
    ru = b_repeat_until(bs, c_done, if_click)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(h2, bs[h2]), (show, bs[show]), (fr2, bs[fr2]), (wdb, bs[wdb]), (ru, bs[ru]), (hi2, bs[hi2])])

    add_comment(bs, comments, h2,
        "🃏 강화 카드 = 클릭 폴링 + 디바운스\n"
        "레벨업하면 카드가 뜨고, 마우스로 왼쪽(공격력)·가운데(연사속도)·오른쪽(이동속도) "
        "칸을 클릭해요. when-clicked 대신 마우스 위치를 계속 확인(폴링)하고, 한 번 누른 걸 "
        "여러 번으로 세지 않게 '뗄 때까지 기다리기'(디바운스)로 딱 한 번만 반영해요.",
        x=460, y=180, w=340, h=180)
    return bs, comments

# ============================================================
#  체력바 / 경험치바 (11단 costume-fill)
# ============================================================
def build_hpbar_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-158), "Y": num(150)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    # 코스튬# = round(내체력/최대체력*10)+1
    hp = vrep("내체력", V_HP); mx = vrep("최대체력", V_MAXHP)
    dv = op("operator_divide", hp, mx)
    m10 = op("operator_multiply", dv, 10)
    rnd = gen(); bs[rnd] = mk("operator_mathop", inputs={"NUM": slot(m10)}, fields={"OPERATOR": ["round", None]}); bs[m10]["parent"] = rnd
    cn = op("operator_add", rnd, 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cn]}); bs[cn]["parent"] = sw
    w = b_wait(bs, 0.05)
    chain([(sw, bs[sw]), (w, bs[w])])
    fe = b_forever(bs, sw)
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (front, bs[front]), (fe, bs[fe])])
    return bs

def build_xpbar_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-158), "Y": num(122)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    exp = vrep("경험치", V_EXP); lv = vrep("레벨업경험치", V_LVUP)
    dv = op("operator_divide", exp, lv)
    m10 = op("operator_multiply", dv, 10)
    rnd = gen(); bs[rnd] = mk("operator_mathop", inputs={"NUM": slot(m10)}, fields={"OPERATOR": ["round", None]}); bs[m10]["parent"] = rnd
    # clamp 0..10 은 생략 (경험치 < 레벨업경험치 보장) → +1
    cn = op("operator_add", rnd, 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cn]}); bs[cn]["parent"] = sw
    w = b_wait(bs, 0.05)
    chain([(sw, bs[sw]), (w, bs[w])])
    fe = b_forever(bs, sw)
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (front, bs[front]), (fe, bs[fe])])
    return bs

# ============================================================
#  게임오버 배너
# ============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    st1 = vrep("게임상태", V_STATE); c1 = cmp_op("operator_equals", st1, 1)
    wu1 = b_wait_until(bs, c1)
    st2 = vrep("게임상태", V_STATE); c0 = cmp_op("operator_equals", st2, 0)
    wu2 = b_wait_until(bs, c0)
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (front, bs[front]), (wu1, bs[wu1]), (wu2, bs[wu2]), (show, bs[show])])
    return bs

# ============================================================
#  ASSEMBLE
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)
    os.makedirs(ASSETS, exist_ok=True)

    # --- 효과음 WAV: assets/ 에 저장 후 읽기 ---
    sounds = {}
    for name, samples in [("pew", synth_pew()), ("pop", synth_pop()), ("hurt", synth_hurt())]:
        path = os.path.join(ASSETS, f"{name}.wav")
        with open(path, "wb") as f: f.write(_wav_bytes(samples))
        with open(path, "rb") as f: data = f.read()
        md5 = md5_bytes(data)
        with open(f"{WORK}/{md5}.wav", "wb") as f: f.write(data)
        sounds[name] = {"name": name, "assetId": md5, "dataFormat": "wav",
                        "format": "", "rate": SND_RATE, "sampleCount": len(samples),
                        "md5ext": f"{md5}.wav"}

    def save_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f: f.write(svg)
        return m

    bg_m   = save_svg(BG_SVG)
    pl_m   = save_svg(PLAYER_SVG)
    bu_m   = save_svg(BULLET_SVG)
    e1_m   = save_svg(ENEMY1_SVG); e2_m = save_svg(ENEMY2_SVG); ep_m = save_svg(ENEMY_POP_SVG)
    card_m = save_svg(CARD_SVG)
    res_m  = save_svg(RESULT_SVG)
    hp_ms  = [save_svg(s) for s in HP_BAR_SVGS]
    xp_ms  = [save_svg(s) for s in XP_BAR_SVGS]

    def costume(name, m, cx, cy):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": m, "md5ext": f"{m}.svg", "rotationCenterX": cx, "rotationCenterY": cy}

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_MOVE:["이동속도",5], V_FIREGAP:["발사쿨",0.15], V_BOLTSPD:["총알속도",12],
            V_ATK:["공격력",1], V_EHP0:["잡졸체력",2], V_ESPD:["적속도",2.5],
            V_SPAWNGAP:["스폰간격",0.8], V_MAXHP:["최대체력",5], V_INVSEC:["무적시간",0.5],
            V_LVUP:["레벨업경험치",8], V_RAMP:["적성장배율",1.2], V_EXPGAIN:["경험치획득",1],
            V_STATE:["게임상태",1], V_SCORE:["점수",0], V_LEVEL:["레벨",1], V_EXP:["경험치",0],
            V_HP:["내체력",5], V_INV:["무적",0], V_SX:["스폰X",0], V_SY:["스폰Y",0],
            V_BX:["총알X",0], V_BY:["총알Y",0], V_BDIR:["총알방향",90],
        },
        "lists": {}, "broadcasts": {
            BR_START:"게임시작", BR_FIRE:"발사", BR_SPAWN:"적스폰", BR_LEVELUP:"레벨업",
        },
        "blocks": None, "comments": None, "currentCostume": 0,
        "costumes": [{"name":"아레나","dataFormat":"svg","assetId":bg_m,"md5ext":f"{bg_m}.svg",
                      "rotationCenterX":240,"rotationCenterY":180}],
        "sounds": [sounds["pop"]],
        "volume":100,"layerOrder":0,"tempo":60,"videoTransparency":50,"videoState":"on",
        "textToSpeechLanguage":None,
    }
    sb, sc = build_stage_blocks(); stage["blocks"] = sb; stage["comments"] = sc

    pb, pc = build_player_blocks()
    player = {
        "isStage": False, "name": "플레이어", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pb, "comments": pc, "currentCostume": 0,
        "costumes": [costume("hunter", pl_m, 26, 28)],
        "sounds": [sounds["pew"]],
        "volume":100,"layerOrder":5,"visible":True,"x":0,"y":0,"size":90,"direction":90,
        "draggable":False,"rotationStyle":"all around",
    }

    bb, bc = build_bullet_blocks()
    bullet = {
        "isStage": False, "name": "총알", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bb, "comments": bc, "currentCostume": 0,
        "costumes": [costume("bullet", bu_m, 13, 8)],
        "sounds": [], "volume":100,"layerOrder":4,"visible":False,"x":0,"y":0,"size":130,
        "direction":90,"draggable":False,"rotationStyle":"all around",
    }

    eb, ec = build_enemy_blocks()
    enemy = {
        "isStage": False, "name": "적",
        "variables": {V_ENHP:["적체력",2], V_ESP:["이속",2.5], V_HITCD:["피격쿨",0]},
        "lists": {}, "broadcasts": {},
        "blocks": eb, "comments": ec, "currentCostume": 0,
        "costumes": [costume("walk1", e1_m, 27, 27), costume("walk2", e2_m, 27, 27),
                     costume("pop", ep_m, 27, 27)],
        "sounds": [sounds["pop"], sounds["hurt"]],
        "volume":100,"layerOrder":3,"visible":False,"x":0,"y":0,"size":85,"direction":90,
        "draggable":False,"rotationStyle":"don't rotate",
    }

    cb, cc = build_card_blocks()
    card = {
        "isStage": False, "name": "강화카드", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": cb, "comments": cc, "currentCostume": 0,
        "costumes": [costume("card", card_m, 210, 90)],
        "sounds": [], "volume":100,"layerOrder":7,"visible":False,"x":0,"y":0,"size":100,
        "direction":90,"draggable":False,"rotationStyle":"don't rotate",
    }

    hpbar = {
        "isStage": False, "name": "체력바", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": build_hpbar_blocks(), "comments": {}, "currentCostume": 10,
        "costumes": [costume(f"hp{i}", hp_ms[i], 0, 12) for i in range(11)],
        "sounds": [], "volume":100,"layerOrder":8,"visible":True,"x":-158,"y":150,"size":100,
        "direction":90,"draggable":False,"rotationStyle":"don't rotate",
    }
    xpbar = {
        "isStage": False, "name": "경험치바", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": build_xpbar_blocks(), "comments": {}, "currentCostume": 0,
        "costumes": [costume(f"xp{i}", xp_ms[i], 0, 12) for i in range(11)],
        "sounds": [], "volume":100,"layerOrder":9,"visible":True,"x":-158,"y":122,"size":100,
        "direction":90,"draggable":False,"rotationStyle":"don't rotate",
    }

    gameover = {
        "isStage": False, "name": "게임오버", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": build_gameover_blocks(), "comments": {}, "currentCostume": 0,
        "costumes": [costume("banner", res_m, 180, 80)],
        "sounds": [], "volume":100,"layerOrder":10,"visible":False,"x":0,"y":0,"size":100,
        "direction":90,"draggable":False,"rotationStyle":"don't rotate",
    }

    monitors = [
        {"id": V_SCORE, "mode":"large","opcode":"data_variable","params":{"VARIABLE":"점수"},
         "spriteName":None,"value":0,"width":0,"height":0,"x":5,"y":5,"visible":True,
         "sliderMin":0,"sliderMax":1000,"isDiscrete":True},
        {"id": V_LEVEL, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"레벨"},
         "spriteName":None,"value":1,"width":0,"height":0,"x":360,"y":5,"visible":True,
         "sliderMin":0,"sliderMax":100,"isDiscrete":True},
    ]

    project = {
        "targets": [stage, player, bullet, enemy, card, hpbar, xpbar, gameover],
        "monitors": monitors, "extensions": [],
        "meta": {"semver":"3.0.0","vm":"13.7.4-svg","agent":"tangtang-hunter-builder"},
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

    counts = {
        "stage": len(sb), "player": len(pb), "bullet": len(bb), "enemy": len(eb),
        "card": len(cb), "hpbar": len(hpbar["blocks"]), "xpbar": len(xpbar["blocks"]),
        "gameover": len(gameover["blocks"]),
    }
    total = sum(counts.values())
    print(f"wrote {OUTPUT}")
    for k, v in counts.items():
        print(f"  {k:9s}: {v} blocks")
    print(f"  {'TOTAL':9s}: {total} blocks")

if __name__ == "__main__":
    main()
