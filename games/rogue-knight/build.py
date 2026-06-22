#!/usr/bin/env python3
"""로그 나이트 (rogue-knight) — 횡스크롤 액션 로그라이트 (Dead Cells 라이트).

기사 한 명으로 한 화면짜리 방에 갇혀, 다가오는 적을 검으로 베어 전멸시킨다.
방을 비우면 강화 셋(공격력+ / 체력+ / 이동속도+) 중 하나를 골라 더 세진 채
다음 방으로 넘어간다. 체력이 0이면 1번 방부터 다시 시작(로그라이트).

베이스: tank-battle (클론 스포너 + 복제됨 가드 + 폭발 연출 + 피격/무적 + 게임오버)
        + geometry-dash (VY·중력·점프 에지 디텍션·바닥 클램프·발판 위 착지).

★ 이 게임의 존재 이유는 "아이가 코드의 숫자·규칙을 직접 바꾸며 노는 것". 그래서
  모든 조절 가능한 값을 한글 전역 변수(튜닝 변수)로만 노출하고, 코드 어디서도
  매직넘버를 쓰지 않는다. (예: change x by 이동속도, set VY = 점프력,
  change VY by 중력, change 내체력 by (0 - 공격력), change x by 대시거리)
  튜닝 변수 14개는 전부 Stage 깃발 클릭 한 스크립트에서 초기화한다(한 곳에 모음).

검판정 분리 패턴: 데미지 판정을 기사 본체가 아니라 별도 '검판정' 스프라이트가
담당한다(tank-battle 의 포탄 분리와 동형). 적은 touching 검판정만 보면 되고
friendly-fire 분기가 필요 없다.
"""
import json, os, zipfile, shutil, hashlib, random, math

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "로그_나이트.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: 돌성 던전 (벽돌 + 바닥선 y=-130) --------
random.seed(11)
bricks = []
for ty in range(0, 250, 28):
    off = 0 if (ty // 28) % 2 == 0 else 28
    for tx in range(-28, 480, 56):
        bx = tx + off
        bricks.append(
            f'<rect x="{bx}" y="{ty}" width="54" height="26" rx="2" '
            f'fill="#3E4756" stroke="#2A313D" stroke-width="1.5"/>'
        )
BRICKS = "\n    ".join(bricks)

torches = []
for cx in (90, 390):
    torches.append(
        f'<rect x="{cx-3}" y="60" width="6" height="34" fill="#5D4037"/>'
        f'<ellipse cx="{cx}" cy="56" rx="9" ry="14" fill="#FF8F00" opacity="0.9"/>'
        f'<ellipse cx="{cx}" cy="58" rx="5" ry="9" fill="#FFEB3B"/>'
    )
TORCHES = "\n    ".join(torches)

# floor (지면): y_svg = 310 → scratch y = 180-310 = -130 (plan 의 바닥선)
FLOOR = (
    '<rect x="0" y="300" width="480" height="60" fill="#5D4037"/>'
    '<rect x="0" y="300" width="480" height="10" fill="#795548"/>'
)
floor_lines = "".join(
    f'<line x1="{x}" y1="300" x2="{x}" y2="360" stroke="#4E342E" stroke-width="1.5"/>'
    for x in range(0, 481, 40)
)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#252B36"/>
  <g>
    {BRICKS}
  </g>
  <g>
    {TORCHES}
  </g>
  {FLOOR}
  {floor_lines}
</svg>"""

# -------- 기사: idle / attack 2코스튬. 오른쪽을 보게 그림(left-right 반전용).
#          발바닥이 정지 y 와 맞도록 rotationCenter 를 발 근처(아래)로. --------
def _knight_svg(attack=False):
    arm = (
        # 휘두르는 검 (앞쪽 위로)
        '<rect x="40" y="6" width="6" height="34" rx="2" fill="#CFD8DC" '
        'stroke="#90A4AE" stroke-width="1.2" transform="rotate(35 43 40)"/>'
        '<rect x="38" y="36" width="10" height="6" rx="2" fill="#FFB300"/>'
    ) if attack else (
        # 검 내림(옆구리)
        '<rect x="42" y="26" width="5" height="26" rx="2" fill="#CFD8DC" '
        'stroke="#90A4AE" stroke-width="1.2"/>'
        '<rect x="40" y="24" width="9" height="5" rx="2" fill="#FFB300"/>'
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="72" viewBox="0 0 60 72">
  <ellipse cx="30" cy="68" rx="16" ry="3" fill="#000000" opacity="0.25"/>
  <!-- 다리 -->
  <rect x="20" y="48" width="8" height="18" rx="2" fill="#37474F"/>
  <rect x="32" y="48" width="8" height="18" rx="2" fill="#455A64"/>
  <!-- 몸통 갑옷 -->
  <rect x="18" y="26" width="24" height="26" rx="5" fill="#1976D2" stroke="#0D47A1" stroke-width="2"/>
  <rect x="18" y="34" width="24" height="4" fill="#1565C0"/>
  <!-- 머리 투구 -->
  <circle cx="30" cy="16" r="11" fill="#90A4AE" stroke="#546E7A" stroke-width="2"/>
  <rect x="26" y="12" width="12" height="5" rx="1" fill="#263238"/>
  <polygon points="30,3 27,9 33,9" fill="#E53935"/>
  <!-- 방패 (앞쪽) -->
  <ellipse cx="16" cy="38" rx="6" ry="10" fill="#FFC107" stroke="#FF8F00" stroke-width="1.5"/>
  {arm}
</svg>"""

KNIGHT_IDLE_SVG   = _knight_svg(attack=False)
KNIGHT_ATTACK_SVG = _knight_svg(attack=True)

# -------- 검판정: 반달 베기 이펙트 (오른쪽 기준) --------
SLASH_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="60" viewBox="0 0 48 60">
  <path d="M6 6 Q44 30 6 54" fill="none" stroke="#E1F5FE" stroke-width="7" stroke-linecap="round" opacity="0.9"/>
  <path d="M10 12 Q36 30 10 48" fill="none" stroke="#4FC3F7" stroke-width="4" stroke-linecap="round" opacity="0.8"/>
  <circle cx="40" cy="30" r="3" fill="#FFFFFF"/>
  <circle cx="30" cy="16" r="2" fill="#B3E5FC"/>
  <circle cx="30" cy="44" r="2" fill="#B3E5FC"/>
</svg>"""

# -------- 적: enemy_idle(고블린/슬라임) / 폭발 2코스튬. 오른쪽 기준. --------
ENEMY_IDLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 56 56">
  <ellipse cx="28" cy="52" rx="15" ry="3" fill="#000000" opacity="0.25"/>
  <!-- 몸통 슬라임 -->
  <path d="M10 44 Q6 18 28 14 Q50 18 46 44 Z" fill="#7CB342" stroke="#558B2F" stroke-width="2"/>
  <ellipse cx="28" cy="20" rx="18" ry="10" fill="#8BC34A"/>
  <!-- 눈 -->
  <circle cx="22" cy="24" r="4" fill="#FFFFFF"/>
  <circle cx="36" cy="24" r="4" fill="#FFFFFF"/>
  <circle cx="23" cy="25" r="2" fill="#1B0F0A"/>
  <circle cx="37" cy="25" r="2" fill="#1B0F0A"/>
  <!-- 입 -->
  <path d="M20 34 Q28 40 36 34" fill="none" stroke="#33691E" stroke-width="2"/>
  <!-- 뿔 -->
  <polygon points="16,14 12,4 22,12" fill="#558B2F"/>
  <polygon points="40,14 44,4 34,12" fill="#558B2F"/>
</svg>"""

def _star_pts(cx, cy, R, r, n, rot=0.0):
    pts = []
    for i in range(2 * n):
        rad = R if i % 2 == 0 else r
        ang = math.pi / n * i + rot
        pts.append(f"{cx + rad*math.cos(ang):.1f},{cy + rad*math.sin(ang):.1f}")
    return " ".join(pts)

EXPLOSION_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 56 56">
  <polygon points="{_star_pts(28, 28, 27, 11, 12)}" fill="#FF6F00" stroke="#E65100" stroke-width="1"/>
  <polygon points="{_star_pts(28, 28, 20, 8, 12, rot=0.262)}" fill="#FFB300"/>
  <circle cx="28" cy="28" r="11" fill="#FFEB3B"/>
  <circle cx="28" cy="28" r="5"  fill="#FFFFFF"/>
  <circle cx="18" cy="20" r="2" fill="#FFF59D"/>
  <circle cx="40" cy="36" r="2" fill="#FFF59D"/>
</svg>"""

# -------- 발판: 돌 발판 80x16 --------
PLATFORM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="16" viewBox="0 0 80 16">
  <rect x="1" y="1" width="78" height="14" rx="3" fill="#6D4C41" stroke="#3E2723" stroke-width="2"/>
  <rect x="1" y="1" width="78" height="4" rx="2" fill="#8D6E63"/>
  <line x1="20" y1="5" x2="20" y2="15" stroke="#3E2723" stroke-width="1"/>
  <line x1="40" y1="5" x2="40" y2="15" stroke="#3E2723" stroke-width="1"/>
  <line x1="60" y1="5" x2="60" y2="15" stroke="#3E2723" stroke-width="1"/>
</svg>"""

# -------- 강화패널: 3선택지 카드 --------
UPGRADE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="4" y="4" width="352" height="162" rx="14" fill="#1A237E" opacity="0.95" stroke="#FFD54F" stroke-width="4"/>
  <text x="180" y="34" text-anchor="middle" fill="#FFD54F" font-family="Arial, sans-serif" font-size="22" font-weight="bold">방 클리어! 강화 선택</text>
  <!-- 카드 1 -->
  <rect x="20" y="50" width="100" height="100" rx="10" fill="#C62828" stroke="#FFFFFF" stroke-width="2"/>
  <text x="70" y="90" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="34" font-weight="bold">1</text>
  <text x="70" y="125" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16">공격력+</text>
  <!-- 카드 2 -->
  <rect x="130" y="50" width="100" height="100" rx="10" fill="#2E7D32" stroke="#FFFFFF" stroke-width="2"/>
  <text x="180" y="90" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="34" font-weight="bold">2</text>
  <text x="180" y="125" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16">체력+</text>
  <!-- 카드 3 -->
  <rect x="240" y="50" width="100" height="100" rx="10" fill="#1565C0" stroke="#FFFFFF" stroke-width="2"/>
  <text x="290" y="90" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="34" font-weight="bold">3</text>
  <text x="290" y="125" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="16">이동속도+</text>
</svg>"""

# -------- 게임오버 배너 --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="68" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="20">방 번호는 왼쪽 위에서 확인!</text>
  <text x="180" y="136" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# 데미지 팝업 스프라이트 코스튬: 말풍선(say) 대신 숫자 코스튬 0~9 를 직접 렌더.
# 자릿수마다 클론 1개를 만들어 해당 숫자 코스튬으로 가로로 나란히 배치한다.
# 큰 흰 숫자 + 진한 외곽선으로 가독성 확보. 캔버스 32x44(자리당 폭 좁게).
def _digit_svg(d):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="32" height="44" viewBox="0 0 32 44">
  <text x="16" y="36" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-size="42" font-weight="bold" fill="#FFEB3B" stroke="#7A3E00" stroke-width="4" paint-order="stroke" stroke-linejoin="round">{d}</text>
</svg>"""

DIGIT_SVGS = [_digit_svg(d) for d in range(10)]

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

# ============================================================
#  IDs  (V_* / var* / BR_* 컨벤션)
# ============================================================
# ----- 5.1 튜닝 변수 14개 (개조 손잡이) -----
V_ATK     = "varAtk01"      # 공격력      기본 1
V_MAXHP   = "varMaxHP02"    # 최대체력    기본 5
V_HP      = "varHP03"       # 체력        기본 5(=최대체력)
V_MOVE    = "varMove04"     # 이동속도    기본 4
V_JUMP    = "varJump05"     # 점프력      기본 12
V_GRAV    = "varGrav06"     # 중력        기본 -1
V_JMAX    = "varJumpMax07"  # 점프횟수상한 기본 2(2단 점프)
V_DASH    = "varDash08"     # 대시거리    기본 90
V_DASHCD  = "varDashCD09"   # 대시쿨      기본 30
V_INV     = "varInv10"      # 무적시간    기본 25
# ── 적 3종 능력치 (종류별로 따로 조절 가능 — 아이가 약/중/강을 각각 튜닝) ──
V_WHP     = "varWeakHP11"   # 약한적_체력  기본 1 (빠르지만 약함)
V_WSPD    = "varWeakSpd11b" # 약한적_속도  기본 2.0
V_MHP     = "varMidHP11c"   # 중간적_체력  기본 2 (보통)
V_MSPD    = "varMidSpd11d"  # 중간적_속도  기본 1.3
V_SHP     = "varStrongHP11e"# 강한적_체력  기본 4 (느리지만 셈)
V_SSPD    = "varStrongSpd11f"# 강한적_속도 기본 0.8
V_UP      = "varUp13"       # 강화량      기본 1
V_GOAL    = "varGoal14"     # 방목표      기본 3 (방빌드 시 2+방번호로 재계산)
TUNING_VARS = [V_ATK, V_MAXHP, V_HP, V_MOVE, V_JUMP, V_GRAV, V_JMAX,
               V_DASH, V_DASHCD, V_INV,
               V_WHP, V_WSPD, V_MHP, V_MSPD, V_SHP, V_SSPD,
               V_UP, V_GOAL]

# ----- 5.2 진행/내부 상태 변수 15개 -----
V_STATE   = "varState15"     # 게임상태  1=전투, 2=강화선택, 0=게임오버
V_ROOM    = "varRoom16"      # 방번호
V_KILL    = "varKill17"      # 처치수
V_ALIVE   = "varAlive18"     # 적수
V_VY      = "varVY19"        # VY 기사 수직 속도
V_JLEFT   = "varJumpLeft20"  # 점프남음
V_PJUMP   = "varPrevJump21"  # 점프이전키
V_PDASH   = "varPrevDash22"  # 대시이전키
V_DASHT   = "varDashT23"     # 대시타이머
V_INVT    = "varInvT24"      # 무적
V_SPX     = "varSPX25"       # 적생성X
V_SPY     = "varSPY26"       # 적생성Y
V_SPTYPE  = "varSPType40"    # 적생성종류 (스포너→클론 종류 전달: 1=약,2=중,3=강)
V_PFX     = "varPFX27"       # 발판X
V_PFY     = "varPFY28"       # 발판Y
V_TOTAL   = "varTotal29"     # 총처치

# ----- 플로팅 데미지 팝업 전달 채널(적 → 데미지 스프라이트) -----
V_DMGVAL  = "varDmgVal34"    # 데미지표시값 (= 공격력 스냅샷)
V_DMGX    = "varDmgX35"      # 데미지표시x (맞은 적 x)
V_DMGY    = "varDmgY36"      # 데미지표시y (맞은 적 y)
# ----- 데미지 숫자 코스튬 렌더 채널(원본 → 자릿수 클론) -----
V_DMGDIGIT = "varDmgDigit38" # 이번 클론이 보여줄 숫자(0~9)
V_DMGOFF   = "varDmgOff39"   # 이번 클론의 가로 오프셋(자릿수 위치)

# ----- 5.3 클론-로컬 변수 -----
V_EISC    = "varEnemyIsClone30"  # 적: 복제됨
V_EHPC    = "varEnemyHP31"        # 적: 내체력
V_EHIT    = "varEnemyHit32"       # 적: 피격쿨
V_ETYPE   = "varEnemyType41"      # 적: 적종류 (1=약,2=중,3=강)
V_ESPDC   = "varEnemySpd42"       # 적: 내속도 (종류별 속도 스냅샷)
V_PFISC   = "varPFIsClone33"      # 발판: 복제됨
V_DMGISC  = "varDmgIsClone37"     # 데미지: 복제됨

# ----- 5.4 메시지 -----
BR_START   = "brStart01"    # 게임시작
BR_BUILD   = "brBuild02"    # 방빌드
BR_UPGRADE = "brUpgrade03"  # 강화등장
BR_NEXT    = "brNext04"     # 다음방
BR_DMG     = "brDmg05"      # 데미지표시 (검 피격 시 공격력 값 팝업)

# 발판 좌표 세트 (방번호 mod 3 → 1/2/0)
PLATFORM_SETS = {
    1: [(-90, -30), (90, -30), (0, 30)],
    2: [(-120, -20), (0, 40), (120, -20)],
    0: [(-60, 0), (60, 0)],
}

FLOOR_Y = -90  # 기사 발 정지 y (바닥선 y=-130 위, size 보정)

# ============================================================
#  block-builder helpers
# ============================================================
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

# small generic builders shared across sprites ----------------------------
def b_setvar(bs, name, vid, value):
    """set <var> to <value>. value: number/str literal or a reporter block id."""
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

def b_wait(bs, dur):
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": num(dur)})
    return bid

def b_sound(bs, pitch):
    """set pitch effect to <pitch> ; play pop. returns (head, tail)."""
    pe = gen(); bs[pe] = mk("sound_seteffectto",
        inputs={"VALUE": num(pitch)}, fields={"EFFECT": ["PITCH", None]})
    sm = gen(); bs[sm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
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

def b_say(bs, message):
    """say <message>. message: a reporter block id, or a string/number literal."""
    bid = gen()
    if isinstance(message, str) and message in bs:
        bs[bid] = mk("looks_say", inputs={"MESSAGE": slot(message)})
        bs[message]["parent"] = bid
    else:
        bs[bid] = mk("looks_say", inputs={"MESSAGE": text_lit(message)})
    return bid

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 클릭 → 모든 변수 초기화(한 곳에 모음) → 게임시작 =====
    # ── 개조 손잡이(튜닝 14개) 기본값: 아이가 여기 숫자만 바꾸면 게임이 바뀐다 ──
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]

    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val)
        seq.append((sid, bs[sid]))

    # 튜닝 변수 14개 (plan 5.1 그대로)
    add_set("공격력", V_ATK, 1)
    add_set("최대체력", V_MAXHP, 5)
    add_set("이동속도", V_MOVE, 4)
    add_set("점프력", V_JUMP, 12)
    add_set("중력", V_GRAV, -1)
    add_set("점프횟수상한", V_JMAX, 2)
    add_set("대시거리", V_DASH, 90)
    add_set("대시쿨", V_DASHCD, 30)
    add_set("무적시간", V_INV, 25)
    # 적 3종 능력치 (약→중→강으로 점점 단단하게). 종류별로 따로 조절 가능.
    add_set("약한적_체력", V_WHP, 1)
    add_set("약한적_속도", V_WSPD, 2.0)
    add_set("중간적_체력", V_MHP, 2)
    add_set("중간적_속도", V_MSPD, 1.3)
    add_set("강한적_체력", V_SHP, 4)
    add_set("강한적_속도", V_SSPD, 0.8)
    add_set("강화량", V_UP, 1)
    add_set("방목표", V_GOAL, 3)
    # 체력 = 최대체력 (튜닝 변수, 최대체력 참조)
    maxhp_r = vrep("최대체력", V_MAXHP)
    set_hp = b_setvar(bs, "체력", V_HP, maxhp_r)
    seq.append((set_hp, bs[set_hp]))

    # 진행 상태 변수
    add_set("방번호", V_ROOM, 1)
    add_set("처치수", V_KILL, 0)
    add_set("적수", V_ALIVE, 0)
    add_set("총처치", V_TOTAL, 0)
    add_set("게임상태", V_STATE, 1)
    add_set("VY", V_VY, 0)
    # 점프남음 = 점프횟수상한
    jmax_r = vrep("점프횟수상한", V_JMAX)
    set_jl = b_setvar(bs, "점프남음", V_JLEFT, jmax_r)
    seq.append((set_jl, bs[set_jl]))
    add_set("점프이전키", V_PJUMP, 0)
    add_set("대시이전키", V_PDASH, 0)
    add_set("대시타이머", V_DASHT, 0)
    add_set("무적", V_INVT, 0)
    add_set("적생성X", V_SPX, 0)
    add_set("적생성Y", V_SPY, 0)
    add_set("적생성종류", V_SPTYPE, 1)
    add_set("발판X", V_PFX, 0)
    add_set("발판Y", V_PFY, 0)

    w1 = b_wait(bs, 0.3); seq.append((w1, bs[w1]))
    bc_start = b_broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # ===== (B) 게임시작 → 방번호=1, 방빌드 =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=300, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    set_room1 = b_setvar(bs, "방번호", V_ROOM, 1)
    bc_build = b_broadcast(bs, "방빌드", BR_BUILD)
    chain([(hb, bs[hb]), (set_room1, bs[set_room1]), (bc_build, bs[bc_build])])

    # ===== (C) 방빌드 받으면 방목표 = 2 + 방번호, 처치수=0 =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=560, y=20,
        fields={"BROADCAST_OPTION": ["방빌드", BR_BUILD]})
    room_r = vrep("방번호", V_ROOM)
    goal_calc = op("operator_add", 2, room_r)   # 2 + 방번호
    set_goal = b_setvar(bs, "방목표", V_GOAL, goal_calc)
    set_kill0 = b_setvar(bs, "처치수", V_KILL, 0)
    chain([(hc, bs[hc]), (set_goal, bs[set_goal]), (set_kill0, bs[set_kill0])])

    # ===== (D) 타이머 감소 forever (대시타이머 / 무적) =====
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=20, y=520)
    def dec_if(name, vid):
        v = vrep(name, vid)
        c = cmp_op("operator_gt", v, 0)
        d = b_changevar(bs, name, vid, -1)
        return b_if(bs, c, d)
    if_dt = dec_if("대시타이머", V_DASHT)
    if_iv = dec_if("무적", V_INVT)
    wd = b_wait(bs, 0.025)
    chain([(if_dt, bs[if_dt]), (if_iv, bs[if_iv]), (wd, bs[wd])])
    fe_d = b_forever(bs, if_dt)
    chain([(hd, bs[hd]), (fe_d, bs[fe_d])])

    # ===== (E) 클리어/게임오버 감시 forever =====
    he = gen(); bs[he] = mk("event_whenflagclicked", top=True, x=300, y=520)
    state_w = vrep("게임상태", V_STATE)
    cond_ready = cmp_op("operator_equals", state_w, 1)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, cond_ready]})
    bs[cond_ready]["parent"] = wu

    # if (처치수 >= 방목표) and (게임상태 = 1) → 게임상태=2, 강화등장
    # 처치수 >= 방목표  ==  not (처치수 < 방목표)
    kill_r2 = vrep("처치수", V_KILL); goal_r2 = vrep("방목표", V_GOAL)
    cond_klt = cmp_op("operator_lt", kill_r2, goal_r2)
    not_klt = gen(); bs[not_klt] = mk("operator_not", inputs={"OPERAND": [2, cond_klt]})
    bs[cond_klt]["parent"] = not_klt
    state_e1 = vrep("게임상태", V_STATE)
    cond_pl1 = cmp_op("operator_equals", state_e1, 1)
    cond_clear = bool_op("operator_and", not_klt, cond_pl1)
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_up = b_broadcast(bs, "강화등장", BR_UPGRADE)
    chain([(set_st2, bs[set_st2]), (bc_up, bs[bc_up])])
    if_clear = b_if(bs, cond_clear, set_st2)

    # if (체력 < 1) and (게임상태 = 1) → 게임상태=0
    hp_r = vrep("체력", V_HP)
    cond_dead = cmp_op("operator_lt", hp_r, 1)
    state_e2 = vrep("게임상태", V_STATE)
    cond_pl2 = cmp_op("operator_equals", state_e2, 1)
    cond_over = bool_op("operator_and", cond_dead, cond_pl2)
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    if_over = b_if(bs, cond_over, set_st0)

    we = b_wait(bs, 0.05)
    chain([(if_clear, bs[if_clear]), (if_over, bs[if_over]), (we, bs[we])])
    fe_e = b_forever(bs, if_clear)
    chain([(he, bs[he]), (wu, bs[wu]), (fe_e, bs[fe_e])])

    # ===== (F) 다음방 받으면 처치수=0 → 방번호+1 → 방빌드 → 게임상태=1 =====
    # 처치수=0 을 가장 먼저 해 클리어 와처(E)가 stale 한 처치수로 강화등장을 재발사하는
    # 레이스를 막는다. 게임상태=1 은 방빌드(방목표 재계산) 뒤에 마지막으로 켠다.
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=560, y=520,
        fields={"BROADCAST_OPTION": ["다음방", BR_NEXT]})
    reset_kill = b_setvar(bs, "처치수", V_KILL, 0)
    inc_room = b_changevar(bs, "방번호", V_ROOM, 1)
    wf = b_wait(bs, 0.15)  # 발판 클론 자기삭제(다음방) 후 재배치 순서 보장
    bc_build2 = b_broadcast(bs, "방빌드", BR_BUILD)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    chain([(hf, bs[hf]), (reset_kill, bs[reset_kill]), (inc_room, bs[inc_room]),
           (wf, bs[wf]), (bc_build2, bs[bc_build2]), (set_st1, bs[set_st1])])

    return bs

# ============================================================
#  기사 (KNIGHT)
# ============================================================
def build_knight_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 초기화 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["left-right", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(-160), "Y": num(FLOOR_Y)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})
    cm = gen(); bs[cm] = mk("looks_costume", fields={"COSTUME": ["knight_idle", None]}, shadow=True)
    sw0 = gen(); bs[sw0] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm]})
    bs[cm]["parent"] = sw0
    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (rs, bs[rs]),
           (pd, bs[pd]), (g0, bs[g0]), (front, bs[front]), (sw0, bs[sw0])])

    # ===== (B) 방빌드 시 위치 리셋 (좌측에서, VY=0, 점프남음 리필) =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["방빌드", BR_BUILD]})
    gb = gen(); bs[gb] = mk("motion_gotoxy", inputs={"X": num(-160), "Y": num(FLOOR_Y)})
    pdb = gen(); bs[pdb] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    set_vy0 = b_setvar(bs, "VY", V_VY, 0)
    jmax_r = vrep("점프횟수상한", V_JMAX)
    set_jl = b_setvar(bs, "점프남음", V_JLEFT, jmax_r)
    chain([(hb, bs[hb]), (gb, bs[gb]), (pdb, bs[pdb]), (set_vy0, bs[set_vy0]),
           (set_jl, bs[set_jl])])

    # ===== (C) 이동·점프·중력 메인 forever (게임상태=1 일 때만) =====
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=340)

    inner = []  # blocks inside the (게임상태=1) if-substack, in order

    # 좌우 이동 (change x by 이동속도 / 0-이동속도) — 매직넘버 금지
    # right
    pr = gen(); bs[pr] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    move_r = vrep("이동속도", V_MOVE)
    cx_r = gen(); bs[cx_r] = mk("motion_changexby", inputs={"DX": slot(move_r)})
    bs[move_r]["parent"] = cx_r
    chain([(pr, bs[pr]), (cx_r, bs[cx_r])])
    if_right = b_if(bs, b_keypressed(bs, "right arrow"), pr)
    inner.append(if_right)
    # left
    pl = gen(); bs[pl] = mk("motion_pointindirection", inputs={"DIRECTION": num(-90)})
    move_l = vrep("이동속도", V_MOVE)
    neg_move = op("operator_subtract", 0, move_l)  # 0 - 이동속도
    cx_l = gen(); bs[cx_l] = mk("motion_changexby", inputs={"DX": slot(neg_move)})
    bs[neg_move]["parent"] = cx_l
    chain([(pl, bs[pl]), (cx_l, bs[cx_l])])
    if_left = b_if(bs, b_keypressed(bs, "left arrow"), pl)
    inner.append(if_left)

    # clamp x to ±220
    def clamp_x(cmp, limit):
        xp = gen(); bs[xp] = mk("motion_xposition")
        c = cmp_op(cmp, xp, limit)
        st = gen(); bs[st] = mk("motion_setx", inputs={"X": num(limit)})
        return b_if(bs, c, st)
    inner.append(clamp_x("operator_gt", 220))
    inner.append(clamp_x("operator_lt", -220))

    # 점프 에지 디텍션 (2단): 점프키 = up OR space
    k_up = b_keypressed(bs, "up arrow")
    k_sp = b_keypressed(bs, "space")
    jump_input = bool_op("operator_or", k_up, k_sp)
    prev_r = vrep("점프이전키", V_PJUMP)
    cond_prev0 = cmp_op("operator_equals", prev_r, 0)
    jleft_r = vrep("점프남음", V_JLEFT)
    cond_jl = cmp_op("operator_gt", jleft_r, 0)
    cond_ji = bool_op("operator_and", jump_input, cond_prev0)
    cond_can_jump = bool_op("operator_and", cond_ji, cond_jl)
    # set VY = 점프력 ; change 점프남음 by -1 ; 점프 사운드(pitch 80)
    jump_r = vrep("점프력", V_JUMP)
    set_vy_jump = b_setvar(bs, "VY", V_VY, jump_r)
    dec_jl = b_changevar(bs, "점프남음", V_JLEFT, -1)
    sh_head, _ = b_sound(bs, 80)
    chain([(set_vy_jump, bs[set_vy_jump]), (dec_jl, bs[dec_jl]), (sh_head, bs[sh_head])])
    if_jump = b_if(bs, cond_can_jump, set_vy_jump)
    inner.append(if_jump)

    # 점프이전키 갱신 (if-else)
    k_up2 = b_keypressed(bs, "up arrow")
    k_sp2 = b_keypressed(bs, "space")
    jump_input2 = bool_op("operator_or", k_up2, k_sp2)
    set_p1 = b_setvar(bs, "점프이전키", V_PJUMP, 1)
    set_p0 = b_setvar(bs, "점프이전키", V_PJUMP, 0)
    if_prev = b_ifelse(bs, jump_input2, set_p1, set_p0)
    inner.append(if_prev)

    # 중력 + 수직 이동: change VY by 중력 ; change y by VY
    grav_r = vrep("중력", V_GRAV)
    ch_vy = b_changevar(bs, "VY", V_VY, grav_r)
    inner.append(ch_vy)
    vy_d = vrep("VY", V_VY)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": slot(vy_d)})
    bs[vy_d]["parent"] = chy
    inner.append(chy)

    # 발판 위 착지(내려오는 중에만): touching 발판 AND VY<0 → change y by 5, VY=0, 점프남음 리필
    tc_pf = b_touching(bs, "발판")
    vy_chk = vrep("VY", V_VY)
    cond_vy_neg = cmp_op("operator_lt", vy_chk, 0)
    cond_land = bool_op("operator_and", tc_pf, cond_vy_neg)
    push_up = gen(); bs[push_up] = mk("motion_changeyby", inputs={"DY": num(5)})
    set_vy0b = b_setvar(bs, "VY", V_VY, 0)
    jmax_r2 = vrep("점프횟수상한", V_JMAX)
    refill1 = b_setvar(bs, "점프남음", V_JLEFT, jmax_r2)
    chain([(push_up, bs[push_up]), (set_vy0b, bs[set_vy0b]), (refill1, bs[refill1])])
    if_land = b_if(bs, cond_land, push_up)
    inner.append(if_land)

    # 바닥 착지: y < FLOOR_Y → set y to FLOOR_Y, VY=0, 점프남음 리필
    yp_f = gen(); bs[yp_f] = mk("motion_yposition")
    cond_floor = cmp_op("operator_lt", yp_f, FLOOR_Y)
    set_y_floor = gen(); bs[set_y_floor] = mk("motion_sety", inputs={"Y": num(FLOOR_Y)})
    set_vy0c = b_setvar(bs, "VY", V_VY, 0)
    jmax_r3 = vrep("점프횟수상한", V_JMAX)
    refill2 = b_setvar(bs, "점프남음", V_JLEFT, jmax_r3)
    chain([(set_y_floor, bs[set_y_floor]), (set_vy0c, bs[set_vy0c]), (refill2, bs[refill2])])
    if_floor = b_if(bs, cond_floor, set_y_floor)
    inner.append(if_floor)

    # wrap inner in if(게임상태=1)
    chain([(b, bs[b]) for b in inner])
    state_c = vrep("게임상태", V_STATE)
    cond_play_c = cmp_op("operator_equals", state_c, 1)
    if_play = b_if(bs, cond_play_c, inner[0])
    wc = b_wait(bs, 0.025)
    chain([(if_play, bs[if_play]), (wc, bs[wc])])
    fe_c = b_forever(bs, if_play)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # ===== (D) 검 입력 forever (Z, 코스튬 전환) =====
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=300, y=340)
    kz = b_keypressed(bs, "z")
    state_d = vrep("게임상태", V_STATE)
    cond_play_d = cmp_op("operator_equals", state_d, 1)
    cond_attack = bool_op("operator_and", kz, cond_play_d)
    cm_a = gen(); bs[cm_a] = mk("looks_costume", fields={"COSTUME": ["knight_attack", None]}, shadow=True)
    sw_a = gen(); bs[sw_a] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm_a]})
    bs[cm_a]["parent"] = sw_a
    sh_z, _ = b_sound(bs, 30)
    w_a1 = b_wait(bs, 0.18)
    cm_i = gen(); bs[cm_i] = mk("looks_costume", fields={"COSTUME": ["knight_idle", None]}, shadow=True)
    sw_i = gen(); bs[sw_i] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm_i]})
    bs[cm_i]["parent"] = sw_i
    w_a2 = b_wait(bs, 0.12)
    chain([(sw_a, bs[sw_a]), (sh_z, bs[sh_z]), (w_a1, bs[w_a1]), (sw_i, bs[sw_i]), (w_a2, bs[w_a2])])
    if_atk = b_if(bs, cond_attack, sw_a)
    wd2 = b_wait(bs, 0.02)
    chain([(if_atk, bs[if_atk]), (wd2, bs[wd2])])
    fe_d = b_forever(bs, if_atk)
    chain([(hd, bs[hd]), (fe_d, bs[fe_d])])

    # ===== (E) 대시 입력 forever (X, 에지 + 쿨) =====
    he = gen(); bs[he] = mk("event_whenflagclicked", top=True, x=560, y=340)
    kx = b_keypressed(bs, "x")
    pdash_r = vrep("대시이전키", V_PDASH)
    cond_pd0 = cmp_op("operator_equals", pdash_r, 0)
    dasht_r = vrep("대시타이머", V_DASHT)
    cond_dt0 = cmp_op("operator_equals", dasht_r, 0)
    state_e = vrep("게임상태", V_STATE)
    cond_play_e = cmp_op("operator_equals", state_e, 1)
    cond_e_a = bool_op("operator_and", kx, cond_pd0)
    cond_e_b = bool_op("operator_and", cond_e_a, cond_dt0)
    cond_can_dash = bool_op("operator_and", cond_e_b, cond_play_e)
    # if direction=90 → change x by 대시거리, else change x by (0-대시거리)
    dir_r = gen(); bs[dir_r] = mk("motion_direction")
    cond_face_r = cmp_op("operator_equals", dir_r, 90)
    dash_r = vrep("대시거리", V_DASH)
    cx_dr = gen(); bs[cx_dr] = mk("motion_changexby", inputs={"DX": slot(dash_r)})
    bs[dash_r]["parent"] = cx_dr
    dash_l = vrep("대시거리", V_DASH)
    neg_dash = op("operator_subtract", 0, dash_l)
    cx_dl = gen(); bs[cx_dl] = mk("motion_changexby", inputs={"DX": slot(neg_dash)})
    bs[neg_dash]["parent"] = cx_dl
    if_dir = b_ifelse(bs, cond_face_r, cx_dr, cx_dl)
    # clamp x ±220 after dash
    def clamp_x2(cmp, limit):
        xp = gen(); bs[xp] = mk("motion_xposition")
        c = cmp_op(cmp, xp, limit)
        st = gen(); bs[st] = mk("motion_setx", inputs={"X": num(limit)})
        return b_if(bs, c, st)
    cxh = clamp_x2("operator_gt", 220)
    cxl = clamp_x2("operator_lt", -220)
    # set 대시타이머 = 대시쿨 ; 사운드 pitch 150
    dashcd_r = vrep("대시쿨", V_DASHCD)
    set_dt = b_setvar(bs, "대시타이머", V_DASHT, dashcd_r)
    sh_x, _ = b_sound(bs, 150)
    chain([(if_dir, bs[if_dir]), (cxh, bs[cxh]), (cxl, bs[cxl]),
           (set_dt, bs[set_dt]), (sh_x, bs[sh_x])])
    if_dash = b_if(bs, cond_can_dash, if_dir)
    # set 대시이전키 = key x
    kx2 = b_keypressed(bs, "x")
    set_pdash = gen(); bs[set_pdash] = mk("data_setvariableto",
        inputs={"VALUE": [3, kx2, [4, "0"]]}, fields={"VARIABLE": ["대시이전키", V_PDASH]})
    bs[kx2]["parent"] = set_pdash
    we2 = b_wait(bs, 0.025)
    chain([(if_dash, bs[if_dash]), (set_pdash, bs[set_pdash]), (we2, bs[we2])])
    fe_e = b_forever(bs, if_dash)
    chain([(he, bs[he]), (fe_e, bs[fe_e])])

    # ===== (F) 피격 감시 forever (touching 적 AND 무적=0 AND 게임상태=1) =====
    hf = gen(); bs[hf] = mk("event_whenflagclicked", top=True, x=820, y=340)
    tc_e = b_touching(bs, "적")
    invt_r = vrep("무적", V_INVT)
    cond_noinv = cmp_op("operator_equals", invt_r, 0)
    state_f = vrep("게임상태", V_STATE)
    cond_play_f = cmp_op("operator_equals", state_f, 1)
    cond_f_a = bool_op("operator_and", tc_e, cond_noinv)
    cond_hurt = bool_op("operator_and", cond_f_a, cond_play_f)
    dec_hp = b_changevar(bs, "체력", V_HP, -1)
    inv_r = vrep("무적시간", V_INV)
    set_invt = b_setvar(bs, "무적", V_INVT, inv_r)
    sh_hurt, _ = b_sound(bs, -300)
    chain([(dec_hp, bs[dec_hp]), (set_invt, bs[set_invt]), (sh_hurt, bs[sh_hurt])])
    if_hurt = b_if(bs, cond_hurt, dec_hp)
    wf = b_wait(bs, 0.04)
    chain([(if_hurt, bs[if_hurt]), (wf, bs[wf])])
    fe_f = b_forever(bs, if_hurt)
    chain([(hf, bs[hf]), (fe_f, bs[fe_f])])

    return bs

# ============================================================
#  검판정 (SLASH hitbox) — Z 누를 때만 기사 앞 0.18초 나타남
# ============================================================
def build_slash_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발: hide, size 60, left-right
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["left-right", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    # (B) forever: if (key z) and (게임상태=1) → 기사 앞 정렬 후 show 0.18s
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=20, y=200)
    kz = b_keypressed(bs, "z")
    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)
    cond_go = bool_op("operator_and", kz, cond_play)

    # point in direction (direction of 기사)
    dir_of = gen(); bs[dir_of] = mk("sensing_of",
        inputs={"OBJECT": [1, _spr_menu(bs, "기사")]}, fields={"PROPERTY": ["direction", None]})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": slot(dir_of)})
    bs[dir_of]["parent"] = pdir

    # if (기사 direction = 90): goto (기사x+35, 기사y) else goto (기사x-35, 기사y)
    dir_of2 = gen(); bs[dir_of2] = mk("sensing_of",
        inputs={"OBJECT": [1, _spr_menu(bs, "기사")]}, fields={"PROPERTY": ["direction", None]})
    cond_face_r = cmp_op("operator_equals", dir_of2, 90)
    # right: goto kx+35, ky
    kx_r = _of(bs, "기사", "x position"); ky_r = _of(bs, "기사", "y position")
    addx = op("operator_add", kx_r, 35)
    goto_r = gen(); bs[goto_r] = mk("motion_gotoxy", inputs={"X": slot(addx), "Y": slot(ky_r)})
    bs[addx]["parent"] = goto_r; bs[ky_r]["parent"] = goto_r
    # left: goto kx-35, ky
    kx_l = _of(bs, "기사", "x position"); ky_l = _of(bs, "기사", "y position")
    subx = op("operator_subtract", kx_l, 35)
    goto_l = gen(); bs[goto_l] = mk("motion_gotoxy", inputs={"X": slot(subx), "Y": slot(ky_l)})
    bs[subx]["parent"] = goto_l; bs[ky_l]["parent"] = goto_l
    if_align = b_ifelse(bs, cond_face_r, goto_r, goto_l)

    show = gen(); bs[show] = mk("looks_show")
    w1 = b_wait(bs, 0.18)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    w2 = b_wait(bs, 0.12)
    chain([(pdir, bs[pdir]), (if_align, bs[if_align]), (show, bs[show]),
           (w1, bs[w1]), (hi2, bs[hi2]), (w2, bs[w2])])
    if_go = b_if(bs, cond_go, pdir)
    w_loop = b_wait(bs, 0.02)
    chain([(if_go, bs[if_go]), (w_loop, bs[w_loop])])
    fe = b_forever(bs, if_go)
    chain([(h2, bs[h2]), (fe, bs[fe])])

    return bs

def _spr_menu(bs, name):
    m = gen(); bs[m] = mk("sensing_of_object_menu",
        fields={"OBJECT": [name, None]}, shadow=True)
    return m

def _of(bs, spr, prop):
    """(prop) of (spr) reporter."""
    bid = gen(); bs[bid] = mk("sensing_of",
        inputs={"OBJECT": [1, _spr_menu(bs, spr)]}, fields={"PROPERTY": [prop, None]})
    return bid

# ============================================================
#  적 (ENEMY: 스포너 + 클론 본체)
# ============================================================
def build_enemy_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(55)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["left-right", None]})
    orig0 = b_setvar(bs, "복제됨", V_EISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 방빌드 → 원본만 방목표 수만큼 스폰
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["방빌드", BR_BUILD]})
    isc_chk = vrep("복제됨", V_EISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    w_init = b_wait(bs, 0.2)  # 발판 배치와 시작 타이밍 분리
    set_alive0 = b_setvar(bs, "적수", V_ALIVE, 0)
    # repeat 방목표 { 종류 결정 ; 적생성X = random ; 적생성Y = FLOOR_Y ; 적수+1 ; clone ; wait }
    #
    # ── 등장 규칙(방번호 기반, 약→중→강 순으로 점점 강해짐) ──
    #   방1      : 약(1)만
    #   방2      : 약+중 (pick random 1~2)
    #   방3 이상 : 중+강 위주 (pick random 2~3)
    # if 방번호 = 1 → 적생성종류 = 1
    room_t1 = vrep("방번호", V_ROOM)
    cond_room1 = cmp_op("operator_equals", room_t1, 1)
    set_type1 = b_setvar(bs, "적생성종류", V_SPTYPE, 1)
    if_room1 = b_if(bs, cond_room1, set_type1)
    # if 방번호 = 2 → 적생성종류 = pick random 1 to 2
    room_t2 = vrep("방번호", V_ROOM)
    cond_room2 = cmp_op("operator_equals", room_t2, 2)
    rnd_t2 = gen(); bs[rnd_t2] = mk("operator_random", inputs={"FROM": num(1), "TO": num(2)})
    set_type2 = gen(); bs[set_type2] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_t2)}, fields={"VARIABLE": ["적생성종류", V_SPTYPE]})
    bs[rnd_t2]["parent"] = set_type2
    if_room2 = b_if(bs, cond_room2, set_type2)
    # if 방번호 > 2 → 적생성종류 = pick random 2 to 3 (중+강 위주)
    room_t3 = vrep("방번호", V_ROOM)
    cond_room3 = cmp_op("operator_gt", room_t3, 2)
    rnd_t3 = gen(); bs[rnd_t3] = mk("operator_random", inputs={"FROM": num(2), "TO": num(3)})
    set_type3 = gen(); bs[set_type3] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_t3)}, fields={"VARIABLE": ["적생성종류", V_SPTYPE]})
    bs[rnd_t3]["parent"] = set_type3
    if_room3 = b_if(bs, cond_room3, set_type3)

    rnd_x = gen(); bs[rnd_x] = mk("operator_random", inputs={"FROM": num(-200), "TO": num(200)})
    set_spx = gen(); bs[set_spx] = mk("data_setvariableto",
        inputs={"VALUE": slot(rnd_x)}, fields={"VARIABLE": ["적생성X", V_SPX]})
    bs[rnd_x]["parent"] = set_spx
    set_spy = b_setvar(bs, "적생성Y", V_SPY, FLOOR_Y)
    inc_alive = b_changevar(bs, "적수", V_ALIVE, 1)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    w_sp = b_wait(bs, 0.15)
    # repeat body: 종류결정(if_room1→if_room2→if_room3) → 위치/스폰
    chain([(if_room1, bs[if_room1]), (if_room2, bs[if_room2]), (if_room3, bs[if_room3]),
           (set_spx, bs[set_spx]), (set_spy, bs[set_spy]),
           (inc_alive, bs[inc_alive]), (cclone, bs[cclone]), (w_sp, bs[w_sp])])
    goal_r = vrep("방목표", V_GOAL)
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": slot(goal_r), "SUBSTACK": [2, if_room1]})
    bs[goal_r]["parent"] = rep; bs[if_room1]["parent"] = rep
    chain([(w_init, bs[w_init]), (set_alive0, bs[set_alive0]), (rep, bs[rep])])
    if_spawn = b_if(bs, cond_orig, w_init)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=460)
    set_isc1 = b_setvar(bs, "복제됨", V_EISC, 1)
    set_hit0 = b_setvar(bs, "피격쿨", V_EHIT, 0)
    # 적종류 = 적생성종류(스포너가 정해준 종류) — 클론 시작 즉시 스냅샷
    sptype_r = vrep("적생성종류", V_SPTYPE)
    set_type = b_setvar(bs, "적종류", V_ETYPE, sptype_r)
    chain([(set_isc1, bs[set_isc1]), (set_hit0, bs[set_hit0]), (set_type, bs[set_type])])

    # ── 종류별 체력/속도/외형 세팅(조건 분기) ──
    #   내체력·내속도는 해당 종류의 튜닝 변수에서, 외형은 색효과+크기로 약/중/강 구분.
    #   공통 코스튬 enemy_idle 위에 color effect 만 다르게 → 한눈에 약(연두)/중(주황)/강(보라).
    def type_branch(type_val, hp_vid, hp_name, spd_vid, spd_name, color_eff, size_val):
        cond_t = cmp_op("operator_equals", vrep("적종류", V_ETYPE), type_val)
        hp_r = vrep(hp_name, hp_vid)
        set_hp = b_setvar(bs, "내체력", V_EHPC, hp_r)
        spd_r = vrep(spd_name, spd_vid)
        set_spd = b_setvar(bs, "내속도", V_ESPDC, spd_r)
        col = gen(); bs[col] = mk("looks_seteffectto",
            inputs={"VALUE": num(color_eff)}, fields={"EFFECT": ["COLOR", None]})
        sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(size_val)})
        chain([(set_hp, bs[set_hp]), (set_spd, bs[set_spd]), (col, bs[col]), (sz, bs[sz])])
        return b_if(bs, cond_t, set_hp)
    # 약(1): 연두(기본색, color 0), 작게.  중(2): 주황(color 150), 보통.  강(3): 보라(color 90), 크게.
    if_t1 = type_branch(1, V_WHP, "약한적_체력", V_WSPD, "약한적_속도", 0,   45)
    if_t2 = type_branch(2, V_MHP, "중간적_체력", V_MSPD, "중간적_속도", 150, 60)
    if_t3 = type_branch(3, V_SHP, "강한적_체력", V_SSPD, "강한적_속도", 90,  78)
    chain([(if_t1, bs[if_t1]), (if_t2, bs[if_t2]), (if_t3, bs[if_t3])])
    # idle 코스튬 보장(폭발에서 시작하지 않게)
    cm_idle = gen(); bs[cm_idle] = mk("looks_costume",
        fields={"COSTUME": ["enemy_idle", None]}, shadow=True)
    sw_idle = gen(); bs[sw_idle] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm_idle]})
    bs[cm_idle]["parent"] = sw_idle

    spx_r = vrep("적생성X", V_SPX); spy_r = vrep("적생성Y", V_SPY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(spx_r), "Y": slot(spy_r)})
    bs[spx_r]["parent"] = g; bs[spy_r]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")

    body = []  # forever body

    # (상시 체력 say 제거됨) — 피격 순간 데미지 팝업으로 대체. 적은 더 이상
    #  머리 위에 내체력 숫자를 항상 띄우지 않는다.

    # 1) 게임오버 정리: if 게임상태=0 → hide, delete
    state1 = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state1, 0)
    hi_o = gen(); bs[hi_o] = mk("looks_hide")
    del_o = gen(); bs[del_o] = mk("control_delete_this_clone")
    chain([(hi_o, bs[hi_o]), (del_o, bs[del_o])])
    if_over = b_if(bs, cond_over, hi_o)
    body.append(if_over)

    # 2) 검 피격: if touching 검판정 AND 피격쿨=0 → 내체력 -= 공격력 ; 피격쿨=10 ; 사운드
    #    + 데미지 팝업: 맞은 자리(x,y)에 공격력 값을 띄우라고 데미지 스프라이트에 방송
    tc_slash = b_touching(bs, "검판정")
    hit_r = vrep("피격쿨", V_EHIT)
    cond_hit0 = cmp_op("operator_equals", hit_r, 0)
    cond_struck = bool_op("operator_and", tc_slash, cond_hit0)
    atk_r = vrep("공격력", V_ATK)
    neg_atk = op("operator_subtract", 0, atk_r)  # 0 - 공격력
    dec_myhp = b_changevar(bs, "내체력", V_EHPC, neg_atk)
    set_hit = b_setvar(bs, "피격쿨", V_EHIT, 10)
    sh_hit, _ = b_sound(bs, 0)
    # 데미지표시값 = 공격력 (반드시 변수 참조 — 매직넘버 금지)
    dmgval_r = vrep("공격력", V_ATK)
    set_dval = b_setvar(bs, "데미지표시값", V_DMGVAL, dmgval_r)
    # 데미지표시x = 적 x position
    dmgx_pos = gen(); bs[dmgx_pos] = mk("motion_xposition")
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, dmgx_pos)
    # 데미지표시y = 적 y position
    dmgy_pos = gen(); bs[dmgy_pos] = mk("motion_yposition")
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, dmgy_pos)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    chain([(dec_myhp, bs[dec_myhp]), (set_hit, bs[set_hit]), (sh_hit, bs[sh_hit]),
           (set_dval, bs[set_dval]), (set_dx, bs[set_dx]), (set_dy, bs[set_dy]),
           (bc_dmg, bs[bc_dmg])])
    if_struck = b_if(bs, cond_struck, dec_myhp)
    body.append(if_struck)

    # if 피격쿨>0: change -1
    hit_r2 = vrep("피격쿨", V_EHIT)
    cond_hitpos = cmp_op("operator_gt", hit_r2, 0)
    dec_hit = b_changevar(bs, "피격쿨", V_EHIT, -1)
    if_hitcd = b_if(bs, cond_hitpos, dec_hit)
    body.append(if_hitcd)

    # 3) 처치: if 내체력<1 → 처치수+1, 총처치+1, 적수-1, 폭발 코스튬, 부풀며 사라짐, delete
    myhp_r = vrep("내체력", V_EHPC)
    cond_dead = cmp_op("operator_lt", myhp_r, 1)
    inc_kill = b_changevar(bs, "처치수", V_KILL, 1)
    inc_total = b_changevar(bs, "총처치", V_TOTAL, 1)
    dec_alive = b_changevar(bs, "적수", V_ALIVE, -1)
    exm = gen(); bs[exm] = mk("looks_costume", fields={"COSTUME": ["폭발", None]}, shadow=True)
    sw_ex = gen(); bs[sw_ex] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, exm]})
    bs[exm]["parent"] = sw_ex
    clr_gh = gen(); bs[clr_gh] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(12)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(20)}, fields={"EFFECT": ["GHOST", None]})
    w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK": [2, ch_sz]})
    bs[ch_sz]["parent"] = rep_an
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")
    chain([(inc_kill, bs[inc_kill]), (inc_total, bs[inc_total]), (dec_alive, bs[dec_alive]),
           (sw_ex, bs[sw_ex]), (clr_gh, bs[clr_gh]),
           (rep_an, bs[rep_an]), (del_k, bs[del_k])])
    if_kill = b_if(bs, cond_dead, inc_kill)
    body.append(if_kill)

    # 4) 추적 (게임상태=1): 기사 방향으로 점프 없이 다가옴, y 고정 FLOOR_Y, clamp x
    # if (x position) > (기사 x): point -90 else point 90
    myx = gen(); bs[myx] = mk("motion_xposition")
    kx_r = _of(bs, "기사", "x position")
    cond_right = cmp_op("operator_gt", myx, kx_r)
    p_left = gen(); bs[p_left] = mk("motion_pointindirection", inputs={"DIRECTION": num(-90)})
    p_right = gen(); bs[p_right] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    if_facedir = b_ifelse(bs, cond_right, p_left, p_right)
    # change x by ±적_속도 depending on direction
    dir_chk = gen(); bs[dir_chk] = mk("motion_direction")
    cond_face90 = cmp_op("operator_equals", dir_chk, 90)
    espd_r = vrep("내속도", V_ESPDC)
    cx_er = gen(); bs[cx_er] = mk("motion_changexby", inputs={"DX": slot(espd_r)})
    bs[espd_r]["parent"] = cx_er
    espd_l = vrep("내속도", V_ESPDC)
    neg_espd = op("operator_subtract", 0, espd_l)
    cx_el = gen(); bs[cx_el] = mk("motion_changexby", inputs={"DX": slot(neg_espd)})
    bs[neg_espd]["parent"] = cx_el
    if_emove = b_ifelse(bs, cond_face90, cx_er, cx_el)
    # set y to FLOOR_Y (지상 적)
    set_y = gen(); bs[set_y] = mk("motion_sety", inputs={"Y": num(FLOOR_Y)})
    # clamp x ±220
    def eclamp(cmp, limit):
        xp = gen(); bs[xp] = mk("motion_xposition")
        c = cmp_op(cmp, xp, limit)
        st = gen(); bs[st] = mk("motion_setx", inputs={"X": num(limit)})
        return b_if(bs, c, st)
    cxh = eclamp("operator_gt", 220)
    cxl = eclamp("operator_lt", -220)
    chain([(if_facedir, bs[if_facedir]), (if_emove, bs[if_emove]), (set_y, bs[set_y]),
           (cxh, bs[cxh]), (cxl, bs[cxl])])
    state2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state2, 1)
    if_chase = b_if(bs, cond_play, if_facedir)
    body.append(if_chase)

    w_body = b_wait(bs, 0.025)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    # clone init: ch → 복제됨=1 → 피격쿨=0 → 적종류 스냅샷
    #             → 종류분기(if_t1→if_t2→if_t3) → idle 코스튬 → goto → show → forever
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1])])           # ch → set_isc1 (rest of head already linked)
    chain([(if_t3, bs[if_t3]), (sw_idle, bs[sw_idle]), (g, bs[g]),
           (show, bs[show]), (fe_body, bs[fe_body])])
    # bridge set_type (end of head group) → if_t1 (start of type-branch group)
    chain([(set_type, bs[set_type]), (if_t1, bs[if_t1])])

    return bs

# ============================================================
#  발판 (PLATFORM): 방번호 mod 3 으로 3세트 배치
# ============================================================
def build_platform_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_PFISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 방빌드 → 원본만, (방번호 mod 3) 세트 배치
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["방빌드", BR_BUILD]})
    isc_chk = vrep("복제됨", V_PFISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)

    # 각 세트마다: if (방번호 mod 3) = key → place coords
    def place_set(coords):
        """coords list → chain of (set 발판X, set 발판Y, clone, wait) ; return head."""
        seq = []
        for i, (px, py) in enumerate(coords):
            sx = b_setvar(bs, "발판X", V_PFX, px)
            sy = b_setvar(bs, "발판Y", V_PFY, py)
            cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
                fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
            cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
            bs[cmenu]["parent"] = cclone
            wt = b_wait(bs, 0.03)
            seq += [(sx, bs[sx]), (sy, bs[sy]), (cclone, bs[cclone]), (wt, bs[wt])]
        chain(seq)
        return seq[0][0]

    # mod helper: (방번호 mod 3)
    def room_mod_eq(val):
        room_r = vrep("방번호", V_ROOM)
        modb = op("operator_mod", room_r, 3)
        c = cmp_op("operator_equals", modb, val)
        bs[modb]["parent"] = c
        return c

    if_set1 = b_if(bs, room_mod_eq(1), place_set(PLATFORM_SETS[1]))
    if_set2 = b_if(bs, room_mod_eq(2), place_set(PLATFORM_SETS[2]))
    if_set0 = b_if(bs, room_mod_eq(0), place_set(PLATFORM_SETS[0]))
    chain([(if_set1, bs[if_set1]), (if_set2, bs[if_set2]), (if_set0, bs[if_set0])])
    if_orig = b_if(bs, cond_orig, if_set1)
    chain([(hb, bs[hb]), (if_orig, bs[if_orig])])

    # (C) 클론 본체: goto (발판X, 발판Y), show, forever{ if 게임상태=0 delete }
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=300, y=200)
    set_isc1 = b_setvar(bs, "복제됨", V_PFISC, 1)
    pfx_r = vrep("발판X", V_PFX); pfy_r = vrep("발판Y", V_PFY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(pfx_r), "Y": slot(pfy_r)})
    bs[pfx_r]["parent"] = g; bs[pfy_r]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")
    state_v = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_v, 0)
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    if_over = b_if(bs, cond_over, del_c)
    w_c = b_wait(bs, 0.1)
    chain([(if_over, bs[if_over]), (w_c, bs[w_c])])
    fe_c = b_forever(bs, if_over)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (show, bs[show]), (fe_c, bs[fe_c])])

    # (D) 다음방 받으면 클론 자기 삭제 (새 방 전 기존 발판 정리)
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=560, y=200,
        fields={"BROADCAST_OPTION": ["다음방", BR_NEXT]})
    isc_chk2 = vrep("복제됨", V_PFISC)
    cond_clone = cmp_op("operator_equals", isc_chk2, 1)
    del_d = gen(); bs[del_d] = mk("control_delete_this_clone")
    if_del = b_if(bs, cond_clone, del_d)
    chain([(hd, bs[hd]), (if_del, bs[if_del])])

    return bs

# ============================================================
#  강화패널 (UPGRADE)
# ============================================================
def build_upgrade_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    # (B) 강화등장 → show, 1/2/3 대기, 강화 적용(변수 += 강화량), 다음방
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["강화등장", BR_UPGRADE]})
    show = gen(); bs[show] = mk("looks_show")
    # wait until (key 1 or key 2 or key 3)
    k1 = b_keypressed(bs, "1"); k2 = b_keypressed(bs, "2"); k3 = b_keypressed(bs, "3")
    or12 = bool_op("operator_or", k1, k2)
    or123 = bool_op("operator_or", or12, k3)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, or123]})
    bs[or123]["parent"] = wu

    # if key1 → 공격력 += 강화량
    up_r1 = vrep("강화량", V_UP)
    ch_atk = b_changevar(bs, "공격력", V_ATK, up_r1)
    if_k1 = b_if(bs, b_keypressed(bs, "1"), ch_atk)
    # if key2 → 최대체력 += 강화량 ; 체력 += 강화량
    up_r2 = vrep("강화량", V_UP)
    ch_maxhp = b_changevar(bs, "최대체력", V_MAXHP, up_r2)
    up_r2b = vrep("강화량", V_UP)
    ch_hp = b_changevar(bs, "체력", V_HP, up_r2b)
    chain([(ch_maxhp, bs[ch_maxhp]), (ch_hp, bs[ch_hp])])
    if_k2 = b_if(bs, b_keypressed(bs, "2"), ch_maxhp)
    # if key3 → 이동속도 += 강화량
    up_r3 = vrep("강화량", V_UP)
    ch_move = b_changevar(bs, "이동속도", V_MOVE, up_r3)
    if_k3 = b_if(bs, b_keypressed(bs, "3"), ch_move)

    sh_up, _ = b_sound(bs, 200)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    w1 = b_wait(bs, 0.2)
    bc_next = b_broadcast(bs, "다음방", BR_NEXT)
    chain([(h2, bs[h2]), (show, bs[show]), (wu, bs[wu]),
           (if_k1, bs[if_k1]), (if_k2, bs[if_k2]), (if_k3, bs[if_k3]),
           (sh_up, bs[sh_up]), (hi2, bs[hi2]), (w1, bs[w1]), (bc_next, bs[bc_next])])

    return bs

# ============================================================
#  게임오버 (GAME OVER 배너)
# ============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})

    state_v1 = vrep("게임상태", V_STATE)
    cond_one = cmp_op("operator_equals", state_v1, 1)
    wu1 = gen(); bs[wu1] = mk("control_wait_until", inputs={"CONDITION": [2, cond_one]})
    bs[cond_one]["parent"] = wu1
    state_v2 = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", state_v2, 0)
    wu2 = gen(); bs[wu2] = mk("control_wait_until", inputs={"CONDITION": [2, cond_zero]})
    bs[cond_zero]["parent"] = wu2
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (wu1, bs[wu1]), (wu2, bs[wu2]), (show, bs[show])])
    return bs

# ============================================================
#  데미지 (플로팅 데미지 팝업): 적이 검에 맞는 순간 공격력 값을
#  숫자 코스튬(0~9)으로 맞은 자리에 띄운다. 말풍선(say) 안 씀.
#  값의 각 자리(십/일)마다 클론 1개씩 만들어 해당 숫자 코스튬으로 가로로 나란히
#  배치 → 위로 떠오르며 ghost 페이드 후 삭제. 값은 반드시 공격력 참조(매직넘버 금지).
# ============================================================
def build_damage_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # (A) 깃발 초기화: hide, 복제됨=0, 회전 안 함(숫자가 뒤집히지 않게)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_DMGISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 데미지표시 받으면 → 원본만, 자릿수별로 숫자 클론 생성.
    #     데미지표시값(=공격력)을 십의 자리/일의 자리로 분해.
    #       일의자리 = 데미지표시값 mod 10
    #       십의자리 = floor(데미지표시값 / 10)
    #     값이 10 이상이면: 십의자리 클론(왼쪽, 오프셋 -9) + 일의자리 클론(오른쪽, 오프셋 +9)
    #     한 자리면: 일의자리 클론 1개(오프셋 0)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["데미지표시", BR_DMG]})
    isc_chk = vrep("복제됨", V_DMGISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)

    def spawn_digit(digit_reporter, offset):
        """데미지숫자=digit ; 데미지오프셋=offset ; create clone ; wait. returns (head, tail)."""
        set_d = b_setvar(bs, "데미지숫자", V_DMGDIGIT, digit_reporter)
        set_o = b_setvar(bs, "데미지오프셋", V_DMGOFF, offset)
        cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
            fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
        cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
        bs[cmenu]["parent"] = cclone
        # 클론이 채널(데미지숫자/오프셋)을 자기 코스튬으로 읽을 시간 확보.
        # (적 스포너의 wait 0.15 와 동일한 패턴 — 채널 경쟁 회피)
        wt = b_wait(bs, 0.12)
        chain([(set_d, bs[set_d]), (set_o, bs[set_o]), (cclone, bs[cclone]), (wt, bs[wt])])
        return set_d, wt

    # 일의자리 = 데미지표시값 mod 10
    val_r1 = vrep("데미지표시값", V_DMGVAL)
    ones = op("operator_mod", val_r1, 10)
    # 십의자리 = floor(데미지표시값 / 10)
    val_r2 = vrep("데미지표시값", V_DMGVAL)
    div10 = op("operator_divide", val_r2, 10)
    tens = gen(); bs[tens] = mk("operator_mathop",
        inputs={"NUM": slot(div10)}, fields={"OPERATOR": ["floor", None]})
    bs[div10]["parent"] = tens

    # if 데미지표시값 >= 10 (== not(<10)) → 두 자리: 십(-9) + 일(+9)
    val_r3 = vrep("데미지표시값", V_DMGVAL)
    cond_lt10 = cmp_op("operator_lt", val_r3, 10)
    not_lt10 = gen(); bs[not_lt10] = mk("operator_not", inputs={"OPERAND": [2, cond_lt10]})
    bs[cond_lt10]["parent"] = not_lt10
    two_tens_h, two_tens_t = spawn_digit(tens, -9)
    two_ones_h, two_ones_t = spawn_digit(ones, 9)
    chain([(two_tens_t, bs[two_tens_t]), (two_ones_h, bs[two_ones_h])])  # 십→일 (tail→head)
    if_two = b_if(bs, not_lt10, two_tens_h)

    # if 데미지표시값 < 10 → 한 자리: 일(0)
    val_r4 = vrep("데미지표시값", V_DMGVAL)
    ones_single = op("operator_mod", val_r4, 10)
    one_only_h, _ = spawn_digit(ones_single, 0)
    val_r5 = vrep("데미지표시값", V_DMGVAL)
    cond_lt10b = cmp_op("operator_lt", val_r5, 10)
    if_one = b_if(bs, cond_lt10b, one_only_h)

    chain([(if_two, bs[if_two]), (if_one, bs[if_one])])
    if_spawn = b_if(bs, cond_orig, if_two)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체: 숫자 코스튬으로 전환 → 자리 위치(오프셋) 에 배치
    #     → 위로 떠오르며 ghost 페이드 후 삭제. (say 없음 — 코스튬으로만 렌더)
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=460)
    set_isc1 = b_setvar(bs, "복제됨", V_DMGISC, 1)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    # switch costume to (데미지숫자 + 1)  — 코스튬 순서: [d0, d1, ... d9] → 숫자 n 은 (n+1)번째
    dig_r = vrep("데미지숫자", V_DMGDIGIT)
    costume_idx = op("operator_add", dig_r, 1)
    sw_num = gen(); bs[sw_num] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(costume_idx)})
    bs[costume_idx]["parent"] = sw_num
    # goto (데미지표시x + 데미지오프셋, 데미지표시y + 12) — 자릿수별 가로 위치
    dx_r = vrep("데미지표시x", V_DMGX)
    off_r = vrep("데미지오프셋", V_DMGOFF)
    x_pos = op("operator_add", dx_r, off_r)
    dy_r = vrep("데미지표시y", V_DMGY)
    y_off = op("operator_add", dy_r, 12)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(x_pos), "Y": slot(y_off)})
    bs[x_pos]["parent"] = g; bs[y_off]["parent"] = g
    clr_gh = gen(); bs[clr_gh] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    show = gen(); bs[show] = mk("looks_show")
    # rise + fade: repeat 8 { change y by 4 ; change ghost by 12 ; wait 0.04 }
    ch_y = gen(); bs[ch_y] = mk("motion_changeyby", inputs={"DY": num(4)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(12)}, fields={"EFFECT": ["GHOST", None]})
    w_an = b_wait(bs, 0.04)
    chain([(ch_y, bs[ch_y]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(8), "SUBSTACK": [2, ch_y]})
    bs[ch_y]["parent"] = rep_an
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (front, bs[front]), (sz, bs[sz]),
           (sw_num, bs[sw_num]), (g, bs[g]), (clr_gh, bs[clr_gh]), (show, bs[show]),
           (rep_an, bs[rep_an]), (del_c, bs[del_c])])
    return bs

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

    bg_md5  = save_svg(BG_SVG)
    ki_md5  = save_svg(KNIGHT_IDLE_SVG)
    ka_md5  = save_svg(KNIGHT_ATTACK_SVG)
    sl_md5  = save_svg(SLASH_SVG)
    ei_md5  = save_svg(ENEMY_IDLE_SVG)
    ex_md5  = save_svg(EXPLOSION_SVG)
    pf_md5  = save_svg(PLATFORM_SVG)
    up_md5  = save_svg(UPGRADE_SVG)
    rs_md5  = save_svg(RESULT_SVG)
    digit_md5 = [save_svg(s) for s in DIGIT_SVGS]  # 숫자 코스튬 0~9

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    knight_blocks   = build_knight_blocks()
    slash_blocks    = build_slash_blocks()
    enemy_blocks    = build_enemy_blocks()
    platform_blocks = build_platform_blocks()
    upgrade_blocks  = build_upgrade_blocks()
    gameover_blocks = build_gameover_blocks()
    damage_blocks   = build_damage_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258, "md5ext": f"{pop_md5}.wav"
    }

    # ---- Stage: 전역 변수 29개 + 방송 4개 ----
    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 18 (기본 10 + 적 3종 능력치 6 + 강화량 + 방목표)
            V_ATK: ["공격력", 1], V_MAXHP: ["최대체력", 5], V_HP: ["체력", 5],
            V_MOVE: ["이동속도", 4], V_JUMP: ["점프력", 12], V_GRAV: ["중력", -1],
            V_JMAX: ["점프횟수상한", 2], V_DASH: ["대시거리", 90], V_DASHCD: ["대시쿨", 30],
            V_INV: ["무적시간", 25],
            V_WHP: ["약한적_체력", 1], V_WSPD: ["약한적_속도", 2.0],
            V_MHP: ["중간적_체력", 2], V_MSPD: ["중간적_속도", 1.3],
            V_SHP: ["강한적_체력", 4], V_SSPD: ["강한적_속도", 0.8],
            V_UP: ["강화량", 1], V_GOAL: ["방목표", 3],
            # 진행 16
            V_STATE: ["게임상태", 1], V_ROOM: ["방번호", 1], V_KILL: ["처치수", 0],
            V_ALIVE: ["적수", 0], V_VY: ["VY", 0], V_JLEFT: ["점프남음", 2],
            V_PJUMP: ["점프이전키", 0], V_PDASH: ["대시이전키", 0], V_DASHT: ["대시타이머", 0],
            V_INVT: ["무적", 0], V_SPX: ["적생성X", 0], V_SPY: ["적생성Y", 0],
            V_SPTYPE: ["적생성종류", 1], V_PFX: ["발판X", 0], V_PFY: ["발판Y", 0],
            V_TOTAL: ["총처치", 0],
            # 데미지 팝업 전달 채널 (좌표 3 + 숫자 렌더 2)
            V_DMGVAL: ["데미지표시값", 0], V_DMGX: ["데미지표시x", 0], V_DMGY: ["데미지표시y", 0],
            V_DMGDIGIT: ["데미지숫자", 0], V_DMGOFF: ["데미지오프셋", 0],
        },
        "lists": {}, "broadcasts": {
            BR_START: "게임시작", BR_BUILD: "방빌드",
            BR_UPGRADE: "강화등장", BR_NEXT: "다음방", BR_DMG: "데미지표시",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "던전", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    knight = {
        "isStage": False, "name": "기사",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": knight_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "knight_idle", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ki_md5, "md5ext": f"{ki_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 66},
            {"name": "knight_attack", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ka_md5, "md5ext": f"{ka_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 66},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": True,
        "x": -160, "y": FLOOR_Y, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "left-right"
    }

    slash = {
        "isStage": False, "name": "검판정",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": slash_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "slash", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": sl_md5, "md5ext": f"{sl_md5}.svg",
            "rotationCenterX": 24, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": False,
        "x": 0, "y": 0, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "left-right"
    }

    enemy = {
        "isStage": False, "name": "적",
        "variables": {V_EISC: ["복제됨", 0], V_EHPC: ["내체력", 2], V_EHIT: ["피격쿨", 0],
                      V_ETYPE: ["적종류", 1], V_ESPDC: ["내속도", 1.2]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "enemy_idle", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ei_md5, "md5ext": f"{ei_md5}.svg",
             "rotationCenterX": 28, "rotationCenterY": 28},
            {"name": "폭발", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ex_md5, "md5ext": f"{ex_md5}.svg",
             "rotationCenterX": 28, "rotationCenterY": 28},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 120, "size": 55, "direction": -90,
        "draggable": False, "rotationStyle": "left-right"
    }

    platform = {
        "isStage": False, "name": "발판",
        "variables": {V_PFISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": platform_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "platform", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": pf_md5, "md5ext": f"{pf_md5}.svg",
            "rotationCenterX": 40, "rotationCenterY": 8
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    upgrade = {
        "isStage": False, "name": "강화패널",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": upgrade_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "upgrade", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": up_md5, "md5ext": f"{up_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 85
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 20, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    gameover = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": gameover_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "패배", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": rs_md5, "md5ext": f"{rs_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 80
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    damage = {
        "isStage": False, "name": "데미지",
        "variables": {V_DMGISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": damage_blocks, "comments": {},
        "currentCostume": 0,
        # 숫자 코스튬 0~9 (순서대로 → 숫자 n 은 (n+1)번째 코스튬)
        "costumes": [
            {"name": str(d), "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": digit_md5[d], "md5ext": f"{digit_md5[d]}.svg",
             "rotationCenterX": 16, "rotationCenterY": 22}
            for d in range(10)
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # ---- 모니터: 체력 / 방번호 / 처치수 / 방목표 (튜닝 변수는 숨김) ----
    monitors = [
        {"id": V_HP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "체력"}, "spriteName": None,
         "value": 5, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
        {"id": V_ROOM, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "방번호"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 20, "isDiscrete": True},
        {"id": V_KILL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "처치수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 20, "isDiscrete": True},
        {"id": V_GOAL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "방목표"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 20, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, knight, slash, enemy, platform, upgrade, gameover, damage],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "rogue-knight-builder"}
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
    print(f"wrote {OUTPUT}")
    for nm, b in [("stage", stage_blocks), ("knight", knight_blocks),
                  ("slash", slash_blocks), ("enemy", enemy_blocks),
                  ("platform", platform_blocks), ("upgrade", upgrade_blocks),
                  ("gameover", gameover_blocks), ("damage", damage_blocks)]:
        print(f"  {nm:9s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
