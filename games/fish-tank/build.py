#!/usr/bin/env python3
"""어항 포식자 (fish-tank) — 골라먹기 피딩-프렌지 라이트 (평화로운 어항).

물고기 한 마리를 마우스로 몰고 다니며, 나보다 작은 물고기에 닿아 골라 먹으면
조금씩 커지고(점수+), 나보다 큰 물고기에 닿으면 그 자리에서 잡아먹혀 GAME OVER.
다른 물고기들은 플레이어를 쫓지 않고 각자 어항을 유유히 배회만 한다(추격 AI 0).
내 크기가 목표크기에 닿으면 CLEAR.

베이스: games/magic-survivor/build.py (클론 스포너·복제됨 가드·한글 튜닝 변수
        일괄 초기화·게임오버/클리어 배너·pop.wav pitch 멀티유즈)
      + games/ghost-hunt/build.py, games/gold-miner/build.py (마우스 추종).

★ 이 게임의 진짜 존재 이유 = "놀이를 통한 배움" 튜닝 샌드박스. 모든 조절 가능한
  값(14개 튜닝 노브)을 한글 전역 변수로만 노출하고, 코드 어디서도 매직넘버를
  쓰지 않는다(연출용 repeat 6 같은 소수 상수 제외). 튜닝 변수는 전부 Stage 깃발
  클릭 한 스크립트에서 초기화한다.

★ 성능 구조(핵심): 단일 초점 + 1대다. 물고기끼리 서로를 절대 보지 않고(상호참조 0)
  각자 배회만 하며, 먹기/피격 상호작용은 물고기 클론 스크립트 한 곳에서만 일어난다.
  프레임당 O(n). 동시 캡(최대물고기≈16) + 먹히면 제거·주기 리스폰으로 개체수 유지.

★ 먹기 트랜잭션 원자화(경합 제거): touching 은 '어느 클론'인지 안 알려주므로 판정 주체는
  물고기 클론이다. 각 클론이 'touching 내물고기' 를 감지하면, 공유 스칼라 '내크기'(다른 클론
  참조 아님, O(1)) 하나만 읽어 자기 운명을 그 자리에서 결정한다:
    - 자기크기 ≤ 내크기×먹기기준(내가 먹힘) → 같은 흐름에서 내크기+=성장량 · 점수+=점수당먹기
      · 뽁 연출 · 물고기수-1 · delete this clone (성장·삭제가 한 스크립트라 경합 없음)
    - 아니면(내가 큼=플레이어 잡아먹음) → 게임상태=0 (게임오버)
  내물고기는 이동·크기반영·색신호만. (예전엔 성장/점수를 내물고기가, 삭제를 클론이 맡아
  단일 프레임 경합으로 성장이 유실됐다 — "사라지기만 하고 렙업 안 됨" 버그. 원자화로 해결.)
"""
import json, os, zipfile, shutil, hashlib, random, math

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "어항_포식자.sb3")

# ============================================================
#  SVG assets
# ============================================================
# -------- 배경: 물빛 어항 (그라데이션 + 바닥 자갈/수초/기포) --------
random.seed(11)
bubbles = []
for _ in range(14):
    bx = random.randint(20, 460); by = random.randint(40, 320)
    br = random.choice([3, 4, 5, 6])
    bubbles.append(f'<circle cx="{bx}" cy="{by}" r="{br}" fill="#E1F5FE" opacity="0.18"/>')
BUBBLES = "\n    ".join(bubbles)
pebbles = []
for _ in range(26):
    px = random.randint(8, 472); py = random.randint(330, 356)
    pr = random.randint(6, 13)
    col = random.choice(["#8D6E63", "#A1887F", "#6D4C41", "#795548", "#9E8579"])
    pebbles.append(f'<ellipse cx="{px}" cy="{py}" rx="{pr}" ry="{pr*0.7:.0f}" fill="{col}"/>')
PEBBLES = "\n    ".join(pebbles)
weeds = []
for wx in [40, 95, 180, 300, 380, 440]:
    sway = random.randint(-14, 14)
    weeds.append(f'<path d="M{wx} 356 Q{wx+sway} 320 {wx} 300 Q{wx-sway} 278 {wx} 252" '
                 f'fill="none" stroke="#2E7D32" stroke-width="7" stroke-linecap="round" opacity="0.75"/>')
    weeds.append(f'<path d="M{wx} 356 Q{wx+sway} 322 {wx+6} 306 Q{wx-sway} 288 {wx} 270" '
                 f'fill="none" stroke="#43A047" stroke-width="4" stroke-linecap="round" opacity="0.7"/>')
WEEDS = "\n    ".join(weeds)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#4FC3F7"/>
      <stop offset="0.55" stop-color="#2196C4"/>
      <stop offset="1" stop-color="#0D5A85"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#water)"/>
  <ellipse cx="150" cy="70" rx="150" ry="46" fill="#B3E5FC" opacity="0.12"/>
  <ellipse cx="360" cy="120" rx="130" ry="40" fill="#B3E5FC" opacity="0.10"/>
  <g>
    {BUBBLES}
  </g>
  <rect x="0" y="336" width="480" height="24" fill="#5D4037"/>
  <g>
    {WEEDS}
  </g>
  <g>
    {PEBBLES}
  </g>
  <rect x="4" y="4" width="472" height="352" rx="10" fill="none" stroke="#01579B" stroke-width="6" opacity="0.5"/>
</svg>"""

# -------- 내 물고기: 밝은 색 + 흰 아웃라인 강조, 좌향 (측면) (72x48) --------
# 기준 방향 -90(왼쪽) — rotationStyle left-right 라 헤엄 방향에 따라 코스튬만 좌우 반전.
ME_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="72" height="48" viewBox="0 0 72 48">
  <!-- 꼬리 (오른쪽) -->
  <path d="M52 24 L70 10 L64 24 L70 38 Z" fill="#FF7043" stroke="#FFFFFF" stroke-width="2.5" stroke-linejoin="round"/>
  <!-- 몸통 -->
  <ellipse cx="34" cy="24" rx="26" ry="16" fill="#FFB300" stroke="#FFFFFF" stroke-width="3"/>
  <!-- 지느러미 -->
  <path d="M34 9 Q40 2 46 10 Z" fill="#FF7043" stroke="#FFFFFF" stroke-width="1.6"/>
  <path d="M28 38 Q32 45 38 39 Z" fill="#FF7043" stroke="#FFFFFF" stroke-width="1.6"/>
  <!-- 배 하이라이트 -->
  <ellipse cx="30" cy="30" rx="16" ry="6" fill="#FFE082" opacity="0.7"/>
  <!-- 눈 (왼쪽=앞) -->
  <circle cx="16" cy="20" r="6" fill="#FFFFFF" stroke="#E0A030" stroke-width="1.2"/>
  <circle cx="14" cy="20" r="3" fill="#212121"/>
  <circle cx="12.5" cy="18.5" r="1" fill="#FFFFFF"/>
  <!-- 입 -->
  <path d="M6 26 Q10 29 14 27" fill="none" stroke="#C25E00" stroke-width="1.8" stroke-linecap="round"/>
</svg>"""

# -------- 물고기 티어 코스튬: 작은(초록) / 중간(노랑) / 큰(빨강·이빨) (모두 좌향, 72x48) --------
SMALL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="72" height="48" viewBox="0 0 72 48">
  <path d="M50 24 L66 13 L61 24 L66 35 Z" fill="#2E7D32" stroke="#1B5E20" stroke-width="1.5" stroke-linejoin="round"/>
  <ellipse cx="34" cy="24" rx="22" ry="15" fill="#66BB6A" stroke="#2E7D32" stroke-width="2"/>
  <path d="M34 10 Q39 4 44 11 Z" fill="#43A047"/>
  <ellipse cx="30" cy="29" rx="13" ry="5" fill="#A5D6A7" opacity="0.7"/>
  <circle cx="18" cy="21" r="5" fill="#FFFFFF" stroke="#2E7D32" stroke-width="1"/>
  <circle cx="16" cy="21" r="2.4" fill="#212121"/>
  <path d="M9 25 Q12 28 16 26" fill="none" stroke="#1B5E20" stroke-width="1.5" stroke-linecap="round"/>
</svg>"""

MID_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="72" height="48" viewBox="0 0 72 48">
  <path d="M50 24 L68 11 L62 24 L68 37 Z" fill="#EF6C00" stroke="#E65100" stroke-width="1.6" stroke-linejoin="round"/>
  <ellipse cx="34" cy="24" rx="24" ry="16" fill="#FFCA28" stroke="#EF6C00" stroke-width="2"/>
  <path d="M34 8 Q40 1 46 9 Z" fill="#FB8C00"/>
  <path d="M28 40 Q33 47 39 40 Z" fill="#FB8C00"/>
  <ellipse cx="30" cy="30" rx="15" ry="5" fill="#FFE082" opacity="0.7"/>
  <!-- 세로 줄무늬(중립 톤) -->
  <path d="M40 12 Q38 24 40 36" fill="none" stroke="#FB8C00" stroke-width="2" opacity="0.6"/>
  <path d="M46 15 Q44 24 46 33" fill="none" stroke="#FB8C00" stroke-width="2" opacity="0.5"/>
  <circle cx="17" cy="20" r="5.5" fill="#FFFFFF" stroke="#EF6C00" stroke-width="1"/>
  <circle cx="15" cy="20" r="2.6" fill="#212121"/>
  <path d="M8 25 Q11 28 15 26" fill="none" stroke="#E65100" stroke-width="1.6" stroke-linecap="round"/>
</svg>"""

# 큰 = 위험(빨강·이빨·경고 실루엣)
BIG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="72" height="48" viewBox="0 0 72 48">
  <path d="M52 24 L70 8 L63 24 L70 40 Z" fill="#B71C1C" stroke="#7F0000" stroke-width="1.8" stroke-linejoin="round"/>
  <ellipse cx="33" cy="24" rx="27" ry="17" fill="#E53935" stroke="#7F0000" stroke-width="2.5"/>
  <path d="M34 7 L42 2 L44 12 Z" fill="#C62828" stroke="#7F0000" stroke-width="1.2"/>
  <path d="M26 41 L22 47 L34 44 Z" fill="#C62828" stroke="#7F0000" stroke-width="1.2"/>
  <!-- 아가미 -->
  <path d="M22 12 Q18 24 22 36" fill="none" stroke="#7F0000" stroke-width="2" opacity="0.7"/>
  <!-- 성난 눈 -->
  <circle cx="15" cy="19" r="6" fill="#FFEB3B" stroke="#7F0000" stroke-width="1"/>
  <circle cx="13" cy="19.5" r="3" fill="#212121"/>
  <path d="M8 13 L20 16" stroke="#7F0000" stroke-width="2" stroke-linecap="round"/>
  <!-- 이빨 벌린 입 -->
  <path d="M5 27 L18 30 L5 33 Z" fill="#7F0000"/>
  <path d="M7 28 L9 31 L11 28 L13 31 L15 28" fill="none" stroke="#FFFFFF" stroke-width="1.4"/>
</svg>"""

# -------- 뽁: 물방울 튐 파티클 (48x48) --------
POP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <circle cx="24" cy="24" r="12" fill="#E1F5FE" opacity="0.85" stroke="#81D4FA" stroke-width="2"/>
  <circle cx="12" cy="14" r="4" fill="#B3E5FC" opacity="0.8"/>
  <circle cx="36" cy="16" r="3.5" fill="#B3E5FC" opacity="0.8"/>
  <circle cx="14" cy="36" r="3" fill="#B3E5FC" opacity="0.8"/>
  <circle cx="36" cy="34" r="4" fill="#B3E5FC" opacity="0.8"/>
  <circle cx="24" cy="24" r="5" fill="#FFFFFF" opacity="0.9"/>
</svg>"""

# -------- 결과 배너: CLEAR / GAME OVER (2코스튬, 360x160) --------
CLEAR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#003c5f" opacity="0.9" stroke="#4FC3F7" stroke-width="5"/>
  <text x="180" y="70" text-anchor="middle" fill="#4FC3F7" font-family="Arial, sans-serif" font-size="52" font-weight="bold">CLEAR!</text>
  <text x="180" y="106" text-anchor="middle" fill="#E1F5FE" font-family="Arial, sans-serif" font-size="20">목표 크기 달성! 어항의 왕이다</text>
  <text x="180" y="136" text-anchor="middle" fill="#B3E5FC" font-family="Arial, sans-serif" font-size="14">초록 깃발(&#9654;) 다시 도전</text>
</svg>"""

OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="68" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="20">큰 물고기에게 잡아먹혔다!</text>
  <text x="180" y="136" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="14">초록 깃발(&#9654;) 다시 도전</text>
</svg>"""

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

# ----- Scratch 블록 코멘트(노란 메모) -----
_cmt_ic = [0]
def add_comment(bs, comments, block_id, text, x=520, y=40, w=280, h=150):
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

def b_touching(bs, target):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": [target, None]}, shadow=True)
    t = gen(); bs[t] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, m]})
    bs[m]["parent"] = t
    return t

def b_keypressed(bs, key):
    m = gen(); bs[m] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": [key, None]}, shadow=True)
    p = gen(); bs[p] = mk("sensing_keypressed", inputs={"KEY_OPTION": [1, m]})
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

def b_random(bs, lo, hi):
    bid = gen(); bs[bid] = mk("operator_random", inputs={"FROM": num(lo), "TO": num(hi)})
    return bid

# ============================================================
#  IDs
# ============================================================
# ----- 5.1 튜닝 14개 (개조 손잡이) -----
V_GROW     = "varGrow01"       # 성장량        3
V_MYSPD    = "varMySpd02"      # 내속도        6
V_FISHSPD  = "varFishSpd03"    # 적속도        1.6
V_SPAWNGAP = "varSpawnGap04"   # 스폰간격      0.7
V_BIGRATE  = "varBigRate05"    # 큰물고기비율   0.2
V_MIDRATE  = "varMidRate06"    # 중간물고기비율 0.3
V_EATRATIO = "varEatRatio07"   # 먹기기준      0.9
V_CAP      = "varCap08"        # 최대물고기    16
V_STARTSZ  = "varStartSize09"  # 시작크기      60
V_GOALSZ   = "varGoalSize10"   # 목표크기      120
V_SIZES    = "varSizeS11"      # 작은크기      35
V_SIZEM    = "varSizeM12"      # 중간크기      65
V_SIZEL    = "varSizeL13"      # 큰크기        100
V_SCOREPER = "varScorePer14"   # 점수당먹기    1

# ----- 5.2 진행/내부 상태 7개 -----
V_STATE    = "varState15"      # 게임상태  1=플레이,2=클리어,0=게임오버
V_SCORE    = "varScore16"      # 점수
V_MYSIZE   = "varMySize17"     # 내크기 (현재 size)
V_ALIVE    = "varAlive18"      # 물고기수 (캡 비교용)
V_TOUCHSZ  = "varTouchSize19"  # 접촉물고기크기 (크기 비교 핸드셰이크 채널)
V_POPX     = "varPopX20"       # 뽁X
V_POPY     = "varPopY21"       # 뽁Y

# ----- 5.3 클론-로컬 변수 4개 -----
V_FISHISC   = "varFishIsClone"  # 물고기: 복제됨
V_FISHMYSZ  = "varFishMySize"   # 물고기: 내물고기크기 (이 클론의 크기)
V_FISHHEAD  = "varFishHeading"  # 물고기: 배회각
V_POPISC    = "varPopIsClone"   # 뽁: 복제됨

# ----- 5.4 메시지 2개 -----
BR_START = "brStart01"   # 게임시작
BR_POP   = "brPop02"     # 뽁생성

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 클릭 → 변수 전부 초기화(한 곳) → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val)
        seq.append((sid, bs[sid]))

    # ── ⚙️ 개조 손잡이(튜닝 14개): 아이가 여기 숫자만 바꾸면 게임이 바뀐다 ──
    add_set("성장량", V_GROW, 7)
    add_set("내속도", V_MYSPD, 6)
    add_set("적속도", V_FISHSPD, 1.6)
    add_set("스폰간격", V_SPAWNGAP, 0.7)
    add_set("큰물고기비율", V_BIGRATE, 0.2)
    add_set("중간물고기비율", V_MIDRATE, 0.3)
    add_set("먹기기준", V_EATRATIO, 0.9)
    add_set("최대물고기", V_CAP, 16)
    add_set("시작크기", V_STARTSZ, 60)
    add_set("목표크기", V_GOALSZ, 110)
    add_set("작은크기", V_SIZES, 35)
    add_set("중간크기", V_SIZEM, 65)
    add_set("큰크기", V_SIZEL, 100)
    add_set("점수당먹기", V_SCOREPER, 1)

    # ── 진행 상태 ──
    add_set("게임상태", V_STATE, 1)
    add_set("점수", V_SCORE, 0)
    # 내크기 = 시작크기 (튜닝 변수 참조 — 매직넘버 아님)
    start_r = vrep("시작크기", V_STARTSZ)
    set_mysize = b_setvar(bs, "내크기", V_MYSIZE, start_r)
    seq.append((set_mysize, bs[set_mysize]))
    add_set("물고기수", V_ALIVE, 0)
    add_set("접촉물고기크기", V_TOUCHSZ, 0)
    add_set("뽁X", V_POPX, 0)
    add_set("뽁Y", V_POPY, 0)

    w1 = b_wait(bs, 0.3); seq.append((w1, bs[w1]))
    bc_start = b_broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # ===== (B) 클리어 감시 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=340, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # wait until 게임상태=1
    state_ready = vrep("게임상태", V_STATE)
    cond_ready = cmp_op("operator_equals", state_ready, 1)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, cond_ready]})
    bs[cond_ready]["parent"] = wu
    # forever: if (내크기>=목표크기) and (게임상태=1) → 게임상태=2 + 클리어 사운드
    mysize_r = vrep("내크기", V_MYSIZE); goal_r = vrep("목표크기", V_GOALSZ)
    cond_reach = cmp_op("operator_gt", mysize_r, goal_r)   # >= 를 (> goal) 또는 별도로; 아래서 >= 위해 재구성
    # 정확한 >= 를 위해: not(내크기 < 목표크기)
    mysize_r2 = vrep("내크기", V_MYSIZE); goal_r2 = vrep("목표크기", V_GOALSZ)
    cond_lt = cmp_op("operator_lt", mysize_r2, goal_r2)
    cond_ge = gen(); bs[cond_ge] = mk("operator_not", inputs={"OPERAND": [2, cond_lt]})
    bs[cond_lt]["parent"] = cond_ge
    # cond_reach 는 미사용이므로 제거
    del bs[cond_reach]; del bs[mysize_r]; del bs[goal_r]
    state_c = vrep("게임상태", V_STATE)
    cond_play_c = cmp_op("operator_equals", state_c, 1)
    cond_clear = bool_op("operator_and", cond_ge, cond_play_c)
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    sh_clear, _ = b_sound(bs, 240)   # 클리어 효과음
    chain([(set_st2, bs[set_st2]), (sh_clear, bs[sh_clear])])
    if_clear = b_if(bs, cond_clear, set_st2)
    w_c = b_wait(bs, 0.05)
    chain([(if_clear, bs[if_clear]), (w_c, bs[w_c])])
    fe_c = b_forever(bs, if_clear)
    chain([(hb, bs[hb]), (wu, bs[wu]), (fe_c, bs[fe_c])])

    # ── 가이드 코멘트 ──
    add_comment(bs, comments, h,
        "⚙️ 개조 손잡이 (여기가 이 게임의 심장!)\n"
        "이 초록 깃발 묶음에 게임의 모든 숫자가 한글 변수로 모여 있어요. "
        "여기 숫자 하나만 바꾸면 게임이 확 달라져요.\n"
        "• 성장량 3→10 : 한 마리만 먹어도 쑥쑥\n"
        "• 먹기기준 0.9→0.6 : 확실히 작아야만 먹혀 까다로움\n"
        "• 큰물고기비율 0.2→0.6 : 상어 소굴! 위험천만\n"
        "바꾸기 전에 '이렇게 될 것 같다'를 예상하고 ▶ 눌러 확인!",
        x=-360, y=-280, w=340, h=210)
    add_comment(bs, comments, hb,
        "🏆 클리어 감시\n"
        "내크기가 목표크기 이상이 되면 게임상태=2 (CLEAR). "
        "게임오버(게임상태=0)는 내물고기 판정에서 직접 정하니 여긴 클리어만 봐요.",
        x=580, y=-40, w=300, h=140)

    return bs, comments

# ============================================================
#  내물고기 (마우스 추종 + 유일한 상호작용 지점)
# ============================================================
def build_me_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 초기화 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["left-right", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(-90)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (show, bs[show]), (rs, bs[rs]), (pd, bs[pd]),
           (g0, bs[g0]), (front, bs[front])])

    # ===== (B) 방향키(↑↓←→) 이동 + 진행방향 바라보기 + 가장자리 클램프 + 크기 반영 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # if 게임상태=1 { set size to 내크기 ; 방향키별 이동 ; 클램프 }
    mysize_r = vrep("내크기", V_MYSIZE)
    set_size = gen(); bs[set_size] = mk("looks_setsizeto", inputs={"SIZE": slot(mysize_r)})
    bs[mysize_r]["parent"] = set_size

    inner = []
    # → : change x by +내속도 ; point in direction -90
    #   (코스튬 art 가 왼쪽을 향해 그려져 있어, left-right 스타일에서 -90 일 때 좌우반전되어
    #    오른쪽을 바라본다. 그래서 오른쪽 이동에는 -90, 왼쪽 이동에는 90 을 준다.)
    spd_r = vrep("내속도", V_MYSPD)
    cx_r = gen(); bs[cx_r] = mk("motion_changexby", inputs={"DX": slot(spd_r)})
    bs[spd_r]["parent"] = cx_r
    face_r = gen(); bs[face_r] = mk("motion_pointindirection", inputs={"DIRECTION": num(-90)})
    chain([(cx_r, bs[cx_r]), (face_r, bs[face_r])])
    inner.append(b_if(bs, b_keypressed(bs, "right arrow"), cx_r))
    # ← : change x by -내속도 ; point in direction 90 (왼쪽 바라봄)
    spd_l = vrep("내속도", V_MYSPD)
    neg_l = op("operator_subtract", 0, spd_l)
    cx_l = gen(); bs[cx_l] = mk("motion_changexby", inputs={"DX": slot(neg_l)})
    bs[neg_l]["parent"] = cx_l
    face_l = gen(); bs[face_l] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    chain([(cx_l, bs[cx_l]), (face_l, bs[face_l])])
    inner.append(b_if(bs, b_keypressed(bs, "left arrow"), cx_l))
    # ↑ : change y by +내속도 (좌우 바라봄은 유지 — 위아래로 뒤집히지 않음)
    spd_u = vrep("내속도", V_MYSPD)
    cy_u = gen(); bs[cy_u] = mk("motion_changeyby", inputs={"DY": slot(spd_u)})
    bs[spd_u]["parent"] = cy_u
    inner.append(b_if(bs, b_keypressed(bs, "up arrow"), cy_u))
    # ↓ : change y by -내속도
    spd_d = vrep("내속도", V_MYSPD)
    neg_d = op("operator_subtract", 0, spd_d)
    cy_d = gen(); bs[cy_d] = mk("motion_changeyby", inputs={"DY": slot(neg_d)})
    bs[neg_d]["parent"] = cy_d
    inner.append(b_if(bs, b_keypressed(bs, "down arrow"), cy_d))
    # 화면 밖 못 나가게 클램프 (x ±230, y ±160)
    def clamp(axis_pos_op, set_op, cmp, limit):
        xp = gen(); bs[xp] = mk(axis_pos_op)
        c = cmp_op(cmp, xp, limit)
        st = gen(); bs[st] = mk(set_op,
            inputs={("X" if set_op == "motion_setx" else "Y"): num(limit)})
        return b_if(bs, c, st)
    inner.append(clamp("motion_xposition", "motion_setx", "operator_gt", 230))
    inner.append(clamp("motion_xposition", "motion_setx", "operator_lt", -230))
    inner.append(clamp("motion_yposition", "motion_sety", "operator_gt", 160))
    inner.append(clamp("motion_yposition", "motion_sety", "operator_lt", -160))
    chain([(set_size, bs[set_size])] + [(b, bs[b]) for b in inner])

    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    if_play_b = b_if(bs, cond_play_b, set_size)
    w_b = b_wait(bs, 0.025)
    chain([(if_play_b, bs[if_play_b]), (w_b, bs[w_b])])
    fe_b = b_forever(bs, if_play_b)
    chain([(hb, bs[hb]), (fe_b, bs[fe_b])])

    # ★ 먹기/피격 판정은 더 이상 여기(내물고기)에 없다 ★
    #   예전에는 여기서 '접촉물고기크기'를 읽어 성장·점수를 처리했는데, 물고기 클론의
    #   자기삭제와 단일 프레임 경합이 나서 성장이 유실됐다("사라지기만 하고 렙업 안 됨").
    #   이제 먹기 트랜잭션(성장·점수·뽁·삭제)과 피격(게임오버)은 물고기 클론이 자기 스크립트
    #   한 흐름에서 원자적으로 처리한다(build_fish_blocks 참조). 내물고기는 이동·연출만.

    add_comment(bs, comments, hb,
        "🐟 방향키(↑↓←→)로 헤엄\n"
        "누른 방향으로 내속도만큼 x/y를 바꿔 이동해요(대각선=두 키 동시). "
        "←/→ 를 누르면 그쪽을 바라보고(rotationStyle 좌우반전이라 위아래로 안 뒤집힘), "
        "가장자리(x±230·y±160)를 넘지 않게 클램프. 크기는 set size to 내크기 로 성장 반영.\n"
        "먹기/피격 판정은 물고기 클론이 원자적으로 처리해요(내물고기는 이동·연출만).",
        x=580, y=-40, w=310, h=190)

    return bs, comments

# ============================================================
#  물고기 (스포너 + 배회 클론 본체)
# ============================================================
def build_fish_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 초기화 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["left-right", None]})
    orig0 = b_setvar(bs, "복제됨", V_FISHISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # ===== (B) 스폰 forever (원본만) — 캡 아래에서 스폰간격마다 1마리 =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    isc_chk = vrep("복제됨", V_FISHISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    # forever: if (게임상태=1) and (물고기수<최대물고기) { 물고기수+1; clone } ; wait 스폰간격
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    alive_r = vrep("물고기수", V_ALIVE); cap_r = vrep("최대물고기", V_CAP)
    cond_under = cmp_op("operator_lt", alive_r, cap_r)
    cond_spawn = bool_op("operator_and", cond_play_b, cond_under)
    inc_alive = b_changevar(bs, "물고기수", V_ALIVE, 1)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(inc_alive, bs[inc_alive]), (cclone, bs[cclone])])
    if_spawn = b_if(bs, cond_spawn, inc_alive)
    w_gap = b_wait_var(bs, V_SPAWNGAP, "스폰간격")
    chain([(if_spawn, bs[if_spawn]), (w_gap, bs[w_gap])])
    fe_b = b_forever(bs, if_spawn)
    if_spawner = b_if(bs, cond_orig, fe_b)
    chain([(hb, bs[hb]), (if_spawner, bs[if_spawner])])

    # ===== (C) 클론 본체 — 티어 결정 → 자유 배회 → 접촉 시 자기 몫 처리 =====
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_FISHISC, 1)

    # 티어 결정: r = pick random 0~100 정수 (실수 pick random 회피). r<큰비율*100 → 큰,
    #   elif r<(큰비율+중간비율)*100 → 중간, else 작은.  (내물고기크기 임시로 r 저장 후 덮어씀)
    r_rand = gen(); bs[r_rand] = mk("operator_random", inputs={"FROM": num(0), "TO": num(100)})
    set_r = b_setvar(bs, "내물고기크기", V_FISHMYSZ, r_rand)   # 임시로 r 보관
    chain([(set_isc1, bs[set_isc1]), (set_r, bs[set_r])])

    def costume_set(name):
        cmc = gen(); bs[cmc] = mk("looks_costume", fields={"COSTUME": [name, None]}, shadow=True)
        sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc]})
        bs[cmc]["parent"] = sw
        return sw

    # 티어 크기에 ±지터를 더해 크기를 다양화한다(고정 3값 → 구간 내 변주).
    #   튜닝 노브(작은/중간/큰크기)는 각 구간 중심으로 유지, 그 안에서 랜덤 폭만 준다.
    def jitter(span):
        j = gen(); bs[j] = mk("operator_random", inputs={"FROM": num(-span), "TO": num(span)})
        cid = gen(); bs[cid] = mk("data_changevariableby",
            inputs={"VALUE": slot(j)}, fields={"VARIABLE": ["내물고기크기", V_FISHMYSZ]})
        bs[j]["parent"] = cid
        return cid

    # 큰 분기
    bigrate_r = vrep("큰물고기비율", V_BIGRATE)
    big_thresh = op("operator_multiply", bigrate_r, 100)
    r_ref1 = vrep("내물고기크기", V_FISHMYSZ)
    cond_big = cmp_op("operator_lt", r_ref1, big_thresh)
    set_big_sz = b_setvar(bs, "내물고기크기", V_FISHMYSZ, vrep("큰크기", V_SIZEL))
    jit_big = jitter(15)
    sw_big = costume_set("큰")
    chain([(set_big_sz, bs[set_big_sz]), (jit_big, bs[jit_big]), (sw_big, bs[sw_big])])
    # 중간 분기: r < (큰비율+중간비율)*100
    bigrate_r2 = vrep("큰물고기비율", V_BIGRATE); midrate_r = vrep("중간물고기비율", V_MIDRATE)
    sum_rate = op("operator_add", bigrate_r2, midrate_r)
    mid_thresh = op("operator_multiply", sum_rate, 100)
    r_ref2 = vrep("내물고기크기", V_FISHMYSZ)
    cond_mid = cmp_op("operator_lt", r_ref2, mid_thresh)
    set_mid_sz = b_setvar(bs, "내물고기크기", V_FISHMYSZ, vrep("중간크기", V_SIZEM))
    jit_mid = jitter(12)
    sw_mid = costume_set("중간")
    chain([(set_mid_sz, bs[set_mid_sz]), (jit_mid, bs[jit_mid]), (sw_mid, bs[sw_mid])])
    # 작은 분기 (else)
    set_small_sz = b_setvar(bs, "내물고기크기", V_FISHMYSZ, vrep("작은크기", V_SIZES))
    jit_small = jitter(8)
    sw_small = costume_set("작은")
    chain([(set_small_sz, bs[set_small_sz]), (jit_small, bs[jit_small]), (sw_small, bs[sw_small])])
    if_mid = b_ifelse(bs, cond_mid, set_mid_sz, set_small_sz)
    if_tier = b_ifelse(bs, cond_big, set_big_sz, if_mid)
    chain([(set_r, bs[set_r]), (if_tier, bs[if_tier])])

    # set size to 내물고기크기
    mysz_r = vrep("내물고기크기", V_FISHMYSZ)
    set_size = gen(); bs[set_size] = mk("looks_setsizeto", inputs={"SIZE": slot(mysz_r)})
    bs[mysz_r]["parent"] = set_size

    # ── 화면 4변 중 랜덤 가장자리에서 스폰 + 안쪽(중앙 방향)으로 헤엄쳐 들어오게 ──
    #    (플레이어 근처 즉시 생성 금지 → "큰 물고기 갑툭튀 즉사" 방지)
    #    코인2회: 상/하(수평변) vs 좌/우(수직변) → 각 변에서 안쪽 방향 배회각 지정.
    #    Scratch direction: 0=위, 90=오른쪽, 180=아래, -90=왼쪽.
    #    상변(y=+175)→아래로(180±), 하변(y=-175)→위로(0±), 좌변(x=-245)→오른쪽(90±), 우변(x=+245)→왼쪽(-90±).
    def inward_head(base):
        # base ± pick random -35~35 (약간의 진입 각도 다양화)
        jit = gen(); bs[jit] = mk("operator_random", inputs={"FROM": num(-35), "TO": num(35)})
        h = op("operator_add", base, jit)
        return b_setvar(bs, "배회각", V_FISHHEAD, h)

    # 상/하변: X 랜덤(-230~230), Y=±175, 배회각 180(상변)/0(하변)
    rx_h = gen(); bs[rx_h] = mk("operator_random", inputs={"FROM": num(-230), "TO": num(230)})
    coin_tb = gen(); bs[coin_tb] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_top = cmp_op("operator_equals", coin_tb, 0)
    # (임시변수 없이 처리: 상/하 각각 goto + 배회각 세팅 substack)
    gh_top = gen(); bs[gh_top] = mk("motion_gotoxy",
        inputs={"X": slot(rx_h), "Y": num(175)}); bs[rx_h]["parent"] = gh_top
    head_top = inward_head(180)
    chain([(gh_top, bs[gh_top]), (head_top, bs[head_top])])
    rx_h2 = gen(); bs[rx_h2] = mk("operator_random", inputs={"FROM": num(-230), "TO": num(230)})
    gh_bot = gen(); bs[gh_bot] = mk("motion_gotoxy",
        inputs={"X": slot(rx_h2), "Y": num(-175)}); bs[rx_h2]["parent"] = gh_bot
    head_bot = inward_head(0)
    chain([(gh_bot, bs[gh_bot]), (head_bot, bs[head_bot])])
    if_tb = b_ifelse(bs, cond_top, gh_top, gh_bot)

    # 좌/우변: Y 랜덤(-160~160), X=∓245, 배회각 90(좌변→오른쪽)/-90(우변→왼쪽)
    ry_v = gen(); bs[ry_v] = mk("operator_random", inputs={"FROM": num(-160), "TO": num(160)})
    coin_lr = gen(); bs[coin_lr] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_left = cmp_op("operator_equals", coin_lr, 0)
    gv_left = gen(); bs[gv_left] = mk("motion_gotoxy",
        inputs={"X": num(-245), "Y": slot(ry_v)}); bs[ry_v]["parent"] = gv_left
    head_left = inward_head(90)
    chain([(gv_left, bs[gv_left]), (head_left, bs[head_left])])
    ry_v2 = gen(); bs[ry_v2] = mk("operator_random", inputs={"FROM": num(-160), "TO": num(160)})
    gv_right = gen(); bs[gv_right] = mk("motion_gotoxy",
        inputs={"X": num(245), "Y": slot(ry_v2)}); bs[ry_v2]["parent"] = gv_right
    head_right = inward_head(-90)
    chain([(gv_right, bs[gv_right]), (head_right, bs[head_right])])
    if_lr = b_ifelse(bs, cond_left, gv_left, gv_right)

    coin_hv = gen(); bs[coin_hv] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_horiz = cmp_op("operator_equals", coin_hv, 0)
    if_edge = b_ifelse(bs, cond_horiz, if_tb, if_lr)

    # 진입 방향으로 실제로 향하게
    head_r0 = vrep("배회각", V_FISHHEAD)
    pd0 = gen(); bs[pd0] = mk("motion_pointindirection", inputs={"DIRECTION": slot(head_r0)})
    bs[head_r0]["parent"] = pd0
    show = gen(); bs[show] = mk("looks_show")
    # (헤드→본체 순차 연결은 아래 최종 chain 한 곳에서 처리)

    # forever body
    body = []
    # 1) 게임오버/클리어 시 정리
    state1 = vrep("게임상태", V_STATE)
    cond_go = cmp_op("operator_equals", state1, 0)
    state1b = vrep("게임상태", V_STATE)
    cond_cl = cmp_op("operator_equals", state1b, 2)
    cond_end = bool_op("operator_or", cond_go, cond_cl)
    dec_alive_go = b_changevar(bs, "물고기수", V_ALIVE, -1)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    chain([(dec_alive_go, bs[dec_alive_go]), (del_go, bs[del_go])])
    if_end = b_if(bs, cond_end, dec_alive_go)
    body.append(if_end)

    # 2) 자유 배회 (게임상태=1) — 추격 없음!
    inner = []
    # ── ★ 먹이/위험 색신호: 이 물고기 크기 vs (공유변수 내크기 × 먹기기준) ──
    #    내물고기크기 ≤ 내크기×먹기기준 이면 내가 먹을 수 있음 → 초록빛(밝게, 안전)
    #    아니면 나를 잡아먹음 → 붉은빛(어둡게, 위험).
    #    매 틱 전역 '내크기'(공유 스칼라 1개)만 읽어 갱신 → 내가 성장하면 실시간으로 바뀜.
    #    ※ 다른 클론 참조 아님(공유 변수 하나 읽기, O(1)) — "물고기끼리 상호참조 0" 유지.
    mysz_sig = vrep("내크기", V_MYSIZE); eat_sig = vrep("먹기기준", V_EATRATIO)
    thresh_sig = op("operator_multiply", mysz_sig, eat_sig)
    myfsz_sig = vrep("내물고기크기", V_FISHMYSZ)
    cond_danger = cmp_op("operator_gt", myfsz_sig, thresh_sig)  # 크면 위험
    # 위험(붉은): color=180(자홍/붉은 계열로 시프트), brightness=-15
    dang_col = gen(); bs[dang_col] = mk("looks_seteffectto",
        inputs={"VALUE": num(180)}, fields={"EFFECT": ["COLOR", None]})
    dang_br = gen(); bs[dang_br] = mk("looks_seteffectto",
        inputs={"VALUE": num(-15)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    chain([(dang_col, bs[dang_col]), (dang_br, bs[dang_br])])
    # 안전(초록·밝게): color=70(초록 계열로 시프트), brightness=+25
    safe_col = gen(); bs[safe_col] = mk("looks_seteffectto",
        inputs={"VALUE": num(70)}, fields={"EFFECT": ["COLOR", None]})
    safe_br = gen(); bs[safe_br] = mk("looks_seteffectto",
        inputs={"VALUE": num(25)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    chain([(safe_col, bs[safe_col]), (safe_br, bs[safe_br])])
    if_signal = b_ifelse(bs, cond_danger, dang_col, safe_col)
    inner.append(if_signal)
    head_r1 = vrep("배회각", V_FISHHEAD)
    pd1 = gen(); bs[pd1] = mk("motion_pointindirection", inputs={"DIRECTION": slot(head_r1)})
    bs[head_r1]["parent"] = pd1
    mv = b_movesteps(bs, vrep("적속도", V_FISHSPD))
    bounce = gen(); bs[bounce] = mk("motion_ifonedgebounce")
    # 배회각 = direction (튕긴 뒤 새 방향 저장)
    dir_b = gen(); bs[dir_b] = mk("motion_direction")
    set_head2 = b_setvar(bs, "배회각", V_FISHHEAD, dir_b)
    inner += [pd1, mv, bounce, set_head2]
    # 가끔 각 틀기: if (pick random 1~30)=1 → 배회각 += pick random -25~25
    coin = gen(); bs[coin] = mk("operator_random", inputs={"FROM": num(1), "TO": num(30)})
    cond_turn = cmp_op("operator_equals", coin, 1)
    turn_amt = gen(); bs[turn_amt] = mk("operator_random", inputs={"FROM": num(-25), "TO": num(25)})
    chg_head = b_changevar(bs, "배회각", V_FISHHEAD, turn_amt)
    if_turn = b_if(bs, cond_turn, chg_head)
    inner.append(if_turn)
    # 3) ★내물고기 접촉 = 먹기 트랜잭션을 이 한 스크립트에서 원자적으로 처리★
    #    (예전엔 성장/점수는 내물고기 스크립트, 삭제는 여기 — 두 곳으로 쪼개져 단일 프레임 경합.
    #     물고기가 먼저 자기삭제되면 내물고기가 그 물고기를 못 잡아 성장이 유실됐다("사라지기만
    #     하고 렙업 안 됨"). 이제 성장·점수·연출·삭제를 같은 흐름 하나로 묶어 경합 원천 제거.)
    #    물고기끼리 상호참조 0 유지: 공유 스칼라 '내크기' 하나만 읽는다(다른 클론 참조 없음).
    tc_me = b_touching(bs, "내물고기")
    # 판정: 내물고기크기 ≤ 내크기 × 먹기기준  ?  (내가 먹힘)
    mysz_c = vrep("내크기", V_MYSIZE); eat_c = vrep("먹기기준", V_EATRATIO)
    thresh_c = op("operator_multiply", mysz_c, eat_c)
    myfsz_c = vrep("내물고기크기", V_FISHMYSZ)
    cond_gt_c = cmp_op("operator_gt", myfsz_c, thresh_c)   # 내가 더 큼(=플레이어 잡아먹음)
    cond_eaten = gen(); bs[cond_eaten] = mk("operator_not", inputs={"OPERAND": [2, cond_gt_c]})
    bs[cond_gt_c]["parent"] = cond_eaten                   # 내가 먹힘(≤)

    # ── 먹힘 분기(원자): 내크기+=성장량 → 점수+=점수당먹기 → 뽁좌표/방송 → 물고기수-1 → 삭제 ──
    grow_r = vrep("성장량", V_GROW)
    inc_size = b_changevar(bs, "내크기", V_MYSIZE, grow_r)
    scoreper_r = vrep("점수당먹기", V_SCOREPER)
    inc_score = b_changevar(bs, "점수", V_SCORE, scoreper_r)
    xp = gen(); bs[xp] = mk("motion_xposition")
    set_px = b_setvar(bs, "뽁X", V_POPX, xp)
    yp = gen(); bs[yp] = mk("motion_yposition")
    set_py = b_setvar(bs, "뽁Y", V_POPY, yp)
    bc_pop = b_broadcast(bs, "뽁생성", BR_POP)
    sh_eat, _ = b_sound(bs, 150)   # 먹기(뽁)
    dec_alive_eat = b_changevar(bs, "물고기수", V_ALIVE, -1)
    del_eat = gen(); bs[del_eat] = mk("control_delete_this_clone")
    chain([(inc_size, bs[inc_size]), (inc_score, bs[inc_score]),
           (set_px, bs[set_px]), (set_py, bs[set_py]), (bc_pop, bs[bc_pop]),
           (sh_eat, bs[sh_eat]), (dec_alive_eat, bs[dec_alive_eat]), (del_eat, bs[del_eat])])
    # ── 못 먹힘 분기(내가 큼): 피격음 → 게임오버(게임상태=0) ──
    sh_die, _ = b_sound(bs, -300)  # 피격/게임오버
    set_over = b_setvar(bs, "게임상태", V_STATE, 0)
    chain([(sh_die, bs[sh_die]), (set_over, bs[set_over])])
    if_eat_txn = b_ifelse(bs, cond_eaten, inc_size, sh_die)
    if_contact = b_if(bs, tc_me, if_eat_txn)
    inner.append(if_contact)
    # inner 를 순차 연결
    chain([(x, bs[x]) for x in inner])
    state2 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state2, 1)
    if_wander = b_if(bs, cond_play2, inner[0])
    body.append(if_wander)

    w_body = b_wait(bs, 0.025)
    chain([(bid, bs[bid]) for bid in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_r, bs[set_r]),
           (if_tier, bs[if_tier]), (set_size, bs[set_size]), (if_edge, bs[if_edge]),
           (pd0, bs[pd0]), (show, bs[show]),
           (fe_body, bs[fe_body])])

    add_comment(bs, comments, if_spawner,
        "🐠 스포너 (원본만) — 동시 캡\n"
        "물고기수 < 최대물고기 일 때만 새로 스폰해요(무한 증식 방지). "
        "먹히거나 게임오버로 클론이 줄면 다시 채워져 개체수가 캡 부근에 유지돼요.",
        x=520, y=-40, w=300, h=150)
    add_comment(bs, comments, if_tier,
        "🎲 티어(작/중/대) 확률 결정\n"
        "0~100 난수 r 로: r < 큰물고기비율×100 → 큰(위험), "
        "r < (큰+중간)×100 → 중간, 아니면 작은. "
        "큰물고기비율을 올리면 위험한 큰 물고기가 실제로 더 자주 떠요.",
        x=520, y=200, w=310, h=150)
    add_comment(bs, comments, if_wander,
        "🌊 자유 배회 (추격 AI 0!) + 원자적 먹기 판정\n"
        "배회각 방향으로 적속도만큼 이동 + 벽에서 튕김(if on edge bounce) + 가끔 각 틀기. "
        "어떤 클론도 내물고기를 향해 point towards/distance to 하지 않아요(추격 0). "
        "닿았을 때는 공유변수 '내크기' 하나만 읽어, 내가 먹힐 크기면 성장·점수·뽁·삭제를 "
        "이 한 흐름에서 원자적으로 처리하고(경합 없음), 내가 더 크면 게임오버로 넘겨요.",
        x=520, y=380, w=345, h=200)

    return bs, comments

# ============================================================
#  뽁 (먹기 파티클)
# ============================================================
def build_pop_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_POPISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 뽁생성 → 그 자리에 파티클 클론 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["뽁생성", BR_POP]})
    isc_chk = vrep("복제됨", V_POPISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 그 자리에서 커지며 페이드 후 삭제
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_POPISC, 1)
    popx_r = vrep("뽁X", V_POPX); popy_r = vrep("뽁Y", V_POPY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(popx_r), "Y": slot(popy_r)})
    bs[popx_r]["parent"] = g; bs[popy_r]["parent"] = g
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    clr = gen(); bs[clr] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(12)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(15)}, fields={"EFFECT": ["GHOST", None]})
    w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(6), "SUBSTACK": [2, ch_sz]})
    bs[ch_sz]["parent"] = rep_an
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (sz, bs[sz]),
           (clr, bs[clr]), (front, bs[front]), (show, bs[show]),
           (rep_an, bs[rep_an]), (del_c, bs[del_c])])

    return bs, comments

# ============================================================
#  결과 (CLEAR / GAME OVER 배너)
# ============================================================
def build_result_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    # (B) 게임시작 → wait until 게임상태=0 or 2 → 코스튬 분기 → show
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)
    state_v2 = vrep("게임상태", V_STATE)
    cond_clear = cmp_op("operator_equals", state_v2, 2)
    cond_end = bool_op("operator_or", cond_over, cond_clear)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, cond_end]})
    bs[cond_end]["parent"] = wu
    # if 게임상태=2 switch to clear else over
    state_v3 = vrep("게임상태", V_STATE)
    cond_is_clear = cmp_op("operator_equals", state_v3, 2)
    cmc_c = gen(); bs[cmc_c] = mk("looks_costume", fields={"COSTUME": ["clear", None]}, shadow=True)
    sw_c = gen(); bs[sw_c] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc_c]})
    bs[cmc_c]["parent"] = sw_c
    cmc_o = gen(); bs[cmc_o] = mk("looks_costume", fields={"COSTUME": ["over", None]}, shadow=True)
    sw_o = gen(); bs[sw_o] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc_o]})
    bs[cmc_o]["parent"] = sw_o
    if_costume = b_ifelse(bs, cond_is_clear, sw_c, sw_o)
    front2 = gen(); bs[front2] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(hb, bs[hb]), (wu, bs[wu]), (if_costume, bs[if_costume]),
           (front2, bs[front2]), (show, bs[show])])

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
    me_md5    = save_svg(ME_SVG)
    small_md5 = save_svg(SMALL_SVG)
    mid_md5   = save_svg(MID_SVG)
    big_md5   = save_svg(BIG_SVG)
    pop_md5   = save_svg(POP_SVG)
    clear_md5 = save_svg(CLEAR_SVG)
    over_md5  = save_svg(OVER_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: popwav_bytes = f.read()
    popwav_md5 = md5_bytes(popwav_bytes)
    with open(f"{WORK}/{popwav_md5}.wav", "wb") as f: f.write(popwav_bytes)

    stage_blocks,  stage_cmt  = build_stage_blocks()
    me_blocks,     me_cmt     = build_me_blocks()
    fish_blocks,   fish_cmt   = build_fish_blocks()
    pop_blocks,    pop_cmt    = build_pop_blocks()
    result_blocks, result_cmt = build_result_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": popwav_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258, "md5ext": f"{popwav_md5}.wav"
    }

    # ---- Stage: 전역 변수 21개 (튜닝14 + 진행7) + 방송 2개 ----
    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 14
            V_GROW: ["성장량", 7], V_MYSPD: ["내속도", 6], V_FISHSPD: ["적속도", 1.6],
            V_SPAWNGAP: ["스폰간격", 0.7], V_BIGRATE: ["큰물고기비율", 0.2],
            V_MIDRATE: ["중간물고기비율", 0.3], V_EATRATIO: ["먹기기준", 0.9],
            V_CAP: ["최대물고기", 16], V_STARTSZ: ["시작크기", 60], V_GOALSZ: ["목표크기", 110],
            V_SIZES: ["작은크기", 35], V_SIZEM: ["중간크기", 65], V_SIZEL: ["큰크기", 100],
            V_SCOREPER: ["점수당먹기", 1],
            # 진행 7
            V_STATE: ["게임상태", 1], V_SCORE: ["점수", 0], V_MYSIZE: ["내크기", 60],
            V_ALIVE: ["물고기수", 0], V_TOUCHSZ: ["접촉물고기크기", 0],
            V_POPX: ["뽁X", 0], V_POPY: ["뽁Y", 0],
        },
        "lists": {},
        "broadcasts": {BR_START: "게임시작", BR_POP: "뽁생성"},
        "blocks": stage_blocks, "comments": stage_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "어항", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    me = {
        "isStage": False, "name": "내물고기",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": me_blocks, "comments": me_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "me", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": me_md5, "md5ext": f"{me_md5}.svg",
            "rotationCenterX": 36, "rotationCenterY": 24
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": True,
        "x": 0, "y": 0, "size": 60, "direction": -90,
        "draggable": False, "rotationStyle": "left-right"
    }

    fish = {
        "isStage": False, "name": "물고기",
        "variables": {V_FISHISC: ["복제됨", 0], V_FISHMYSZ: ["내물고기크기", 35],
                      V_FISHHEAD: ["배회각", 90]},
        "lists": {}, "broadcasts": {},
        "blocks": fish_blocks, "comments": fish_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "작은", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": small_md5, "md5ext": f"{small_md5}.svg",
             "rotationCenterX": 36, "rotationCenterY": 24},
            {"name": "중간", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": mid_md5, "md5ext": f"{mid_md5}.svg",
             "rotationCenterX": 36, "rotationCenterY": 24},
            {"name": "큰", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": big_md5, "md5ext": f"{big_md5}.svg",
             "rotationCenterX": 36, "rotationCenterY": 24},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 35, "direction": 90,
        "draggable": False, "rotationStyle": "left-right"
    }

    pop = {
        "isStage": False, "name": "뽁",
        "variables": {V_POPISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": pop_blocks, "comments": pop_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "pop", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pop_md5, "md5ext": f"{pop_md5}.svg",
            "rotationCenterX": 24, "rotationCenterY": 24
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    result = {
        "isStage": False, "name": "결과",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": result_blocks, "comments": result_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "clear", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": clear_md5, "md5ext": f"{clear_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 80},
            {"name": "over", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": over_md5, "md5ext": f"{over_md5}.svg",
             "rotationCenterX": 180, "rotationCenterY": 80},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # ---- 모니터: 내크기 / 목표크기 / 점수 (튜닝 변수는 숨김) ----
    monitors = [
        {"id": V_MYSIZE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "내크기"}, "spriteName": None,
         "value": 60, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 200, "isDiscrete": True},
        {"id": V_GOALSZ, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "목표크기"}, "spriteName": None,
         "value": 110, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 300, "isDiscrete": True},
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, me, fish, pop, result],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "fish-tank-builder"}
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
    total = sum(len(b) for b in [stage_blocks, me_blocks, fish_blocks, pop_blocks, result_blocks])
    print(f"wrote {OUTPUT}")
    for nm, b in [("stage", stage_blocks), ("me(내물고기)", me_blocks),
                  ("fish(물고기)", fish_blocks), ("pop(뽁)", pop_blocks),
                  ("result(결과)", result_blocks)]:
        print(f"  {nm:14s}: {len(b)} blocks")
    print(f"  TOTAL        : {total} blocks")

if __name__ == "__main__":
    main()
