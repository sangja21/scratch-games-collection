#!/usr/bin/env python3
"""마법 생존 (magic-survivor) — 자동 공격 생존형 액션 (뱀파이어 서바이벌 라이트).

마법사 한 명으로 한 화면짜리 아레나에 갇혀, 사방에서 끝없이 몰려오는 적을
자동 마법으로 막아낸다. 마법탄은 발사간격마다 '가장 가까운 적'에게 알아서
날아가므로 아이는 움직여서 피하는 데만 집중한다. 적은 약·중·강 3종이며 생존
시간이 길어질수록(단계 = 생존시간÷난이도주기) 센 적이 섞여 나온다. 적을 잡으면
경험치 보석이 떨어지고, 모아서 레벨업하면 강화 셋 중 하나를 골라 강해진다.
체력 0이면 GAME OVER, 깃발 재클릭으로 능력치 기본값 리셋. 점수 = 생존 시간(초).

베이스: games/rogue-knight/build.py (클론 스포너·복제됨 가드·체력/무적·폭발 연출·
        플로팅 데미지 숫자·강화 택1·게임오버 배너·한글 튜닝 변수 일괄 초기화)
      + games/tank-battle/build.py (좌표 전달 채널).

★ 이 게임의 존재 이유는 "아이가 코드의 숫자·규칙을 직접 바꾸며 노는 것". 그래서
  모든 조절 가능한 값(24개)을 한글 전역 변수로만 노출하고, 코드 어디서도 매직넘버를
  쓰지 않는다. 튜닝 변수는 전부 Stage 깃발 클릭 한 스크립트에서 초기화한다.

★ 자동 조준 핸드셰이크: 마법사가 발사 직전 '조준요청'을 broadcast-and-wait 로
  보낸다. Scratch 는 단일 스레드 협력형이라 wait 없는 수신 스크립트들이 클론 순서대로
  하나씩 원자 실행된다 → 각 적 클론이 'distance to 마법사' 최솟값 리덕션을 경쟁
  조건 없이 수행한다. 끝나면 조준있음=1 일 때만 그 좌표로 발사한다.
"""
import json, os, zipfile, shutil, hashlib, random, math

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "마법_생존.sb3")

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

# -------- 배경: 돌바닥 아레나 (어두운 테두리) --------
random.seed(7)
tiles = []
for ty in range(0, 360, 40):
    for tx in range(0, 480, 40):
        shade = random.choice(["#3B4252", "#434C5E", "#39414F"])
        tiles.append(f'<rect x="{tx}" y="{ty}" width="40" height="40" '
                     f'fill="{shade}" stroke="#2E3440" stroke-width="1"/>')
TILES = "\n    ".join(tiles)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#2E3440"/>
  <g>
    {TILES}
  </g>
  <rect x="6" y="6" width="468" height="348" rx="10" fill="none" stroke="#1B1F27" stroke-width="12"/>
  <rect x="14" y="14" width="452" height="332" rx="8" fill="none" stroke="#4C566A" stroke-width="3" opacity="0.6"/>
</svg>"""

# -------- 마법사: 뾰족모자 마법사, 정면 (60x72) --------
MAGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="72" viewBox="0 0 60 72">
  <ellipse cx="30" cy="68" rx="15" ry="3" fill="#000000" opacity="0.25"/>
  <!-- 로브 -->
  <path d="M14 64 Q12 40 30 34 Q48 40 46 64 Z" fill="#5E35B1" stroke="#4527A0" stroke-width="2"/>
  <path d="M30 34 L30 64" stroke="#7E57C2" stroke-width="2"/>
  <!-- 팔/지팡이 -->
  <rect x="44" y="20" width="4" height="40" rx="2" fill="#8D6E63" transform="rotate(8 46 40)"/>
  <circle cx="49" cy="18" r="6" fill="#4FC3F7" stroke="#0288D1" stroke-width="2"/>
  <circle cx="49" cy="18" r="2.5" fill="#FFFFFF"/>
  <!-- 얼굴 -->
  <circle cx="30" cy="30" r="9" fill="#FFE0B2" stroke="#E0A878" stroke-width="1.5"/>
  <circle cx="26" cy="30" r="1.6" fill="#3E2723"/>
  <circle cx="34" cy="30" r="1.6" fill="#3E2723"/>
  <!-- 뾰족 모자 -->
  <polygon points="30,2 17,24 43,24" fill="#311B92" stroke="#1A0E5C" stroke-width="2"/>
  <ellipse cx="30" cy="25" rx="16" ry="4" fill="#4527A0" stroke="#1A0E5C" stroke-width="2"/>
  <polygon points="30,7 27,15 33,15" fill="#FFD54F"/>
  <circle cx="30" cy="5" r="2.5" fill="#FFEB3B"/>
</svg>"""

# -------- 마법탄: 빛나는 구체/별 (44x44) --------
BOLT_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">
  <circle cx="22" cy="22" r="18" fill="#4FC3F7" opacity="0.35"/>
  <polygon points="{_star_pts(22, 22, 17, 7, 5, rot=-1.571)}" fill="#81D4FA" opacity="0.9"/>
  <circle cx="22" cy="22" r="9" fill="#E1F5FE"/>
  <circle cx="22" cy="22" r="4.5" fill="#FFFFFF"/>
</svg>"""

# -------- 적 코스튬: 슬라임(약) / 박쥐(중) / 골렘(강) / 폭발 (모두 60x60) --------
SLIME_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="55" rx="16" ry="3" fill="#000000" opacity="0.25"/>
  <path d="M12 48 Q8 24 30 20 Q52 24 48 48 Z" fill="#66BB6A" stroke="#388E3C" stroke-width="2"/>
  <ellipse cx="30" cy="28" rx="18" ry="11" fill="#81C784"/>
  <circle cx="24" cy="30" r="4" fill="#FFFFFF"/>
  <circle cx="36" cy="30" r="4" fill="#FFFFFF"/>
  <circle cx="24" cy="31" r="2" fill="#1B0F0A"/>
  <circle cx="36" cy="31" r="2" fill="#1B0F0A"/>
  <path d="M24 40 Q30 45 36 40" fill="none" stroke="#2E7D32" stroke-width="2"/>
</svg>"""

BAT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="55" rx="13" ry="3" fill="#000000" opacity="0.2"/>
  <!-- 날개 -->
  <path d="M30 30 Q10 16 4 32 Q14 30 18 38 Q20 30 30 34 Z" fill="#7E57C2" stroke="#5E35B1" stroke-width="1.5"/>
  <path d="M30 30 Q50 16 56 32 Q46 30 42 38 Q40 30 30 34 Z" fill="#7E57C2" stroke="#5E35B1" stroke-width="1.5"/>
  <!-- 몸통 -->
  <ellipse cx="30" cy="32" rx="11" ry="13" fill="#9575CD" stroke="#5E35B1" stroke-width="2"/>
  <polygon points="22,20 25,30 19,29" fill="#9575CD"/>
  <polygon points="38,20 35,30 41,29" fill="#9575CD"/>
  <circle cx="26" cy="30" r="2.5" fill="#FFEB3B"/>
  <circle cx="34" cy="30" r="2.5" fill="#FFEB3B"/>
  <circle cx="26" cy="30" r="1" fill="#3E2723"/>
  <circle cx="34" cy="30" r="1" fill="#3E2723"/>
  <path d="M26 38 L28 41 L30 38 L32 41 L34 38" fill="none" stroke="#FFFFFF" stroke-width="1.4"/>
</svg>"""

GOLEM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="56" rx="18" ry="3" fill="#000000" opacity="0.3"/>
  <!-- 팔 -->
  <rect x="4" y="28" width="12" height="22" rx="4" fill="#8D6E63" stroke="#5D4037" stroke-width="2"/>
  <rect x="44" y="28" width="12" height="22" rx="4" fill="#8D6E63" stroke="#5D4037" stroke-width="2"/>
  <!-- 몸통 -->
  <rect x="14" y="22" width="32" height="30" rx="6" fill="#A1887F" stroke="#5D4037" stroke-width="3"/>
  <!-- 머리 -->
  <rect x="18" y="6" width="24" height="20" rx="5" fill="#8D6E63" stroke="#5D4037" stroke-width="3"/>
  <rect x="22" y="13" width="6" height="5" rx="1" fill="#FF7043"/>
  <rect x="32" y="13" width="6" height="5" rx="1" fill="#FF7043"/>
  <rect x="20" y="32" width="20" height="4" fill="#6D4C41"/>
  <rect x="20" y="40" width="20" height="4" fill="#6D4C41"/>
</svg>"""

EXPLOSION_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30, 30, 29, 12, 12)}" fill="#FF6F00" stroke="#E65100" stroke-width="1"/>
  <polygon points="{_star_pts(30, 30, 21, 8, 12, rot=0.262)}" fill="#FFB300"/>
  <circle cx="30" cy="30" r="12" fill="#FFEB3B"/>
  <circle cx="30" cy="30" r="5"  fill="#FFFFFF"/>
</svg>"""

# -------- 경험치 보석: 청록 보석 (48x48) --------
GEM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <polygon points="24,4 42,18 24,44 6,18" fill="#26C6DA" stroke="#00838F" stroke-width="2"/>
  <polygon points="24,4 42,18 24,18" fill="#4DD0E1"/>
  <polygon points="24,4 6,18 24,18" fill="#80DEEA"/>
  <polygon points="24,18 42,18 24,44" fill="#00ACC1"/>
  <polygon points="24,18 6,18 24,44" fill="#0097A7"/>
  <circle cx="18" cy="13" r="2" fill="#FFFFFF" opacity="0.8"/>
</svg>"""

# -------- 강화카드: 3선택지 카드 --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="170" viewBox="0 0 360 170">
  <rect x="4" y="4" width="352" height="162" rx="14" fill="#1A237E" opacity="0.95" stroke="#FFD54F" stroke-width="4"/>
  <text x="180" y="34" text-anchor="middle" fill="#FFD54F" font-family="Arial, sans-serif" font-size="22" font-weight="bold">레벨업! 강화 선택</text>
  <rect x="20" y="50" width="100" height="100" rx="10" fill="#C62828" stroke="#FFFFFF" stroke-width="2"/>
  <text x="70" y="90" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="34" font-weight="bold">1</text>
  <text x="70" y="124" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="15">마법공격력+</text>
  <rect x="130" y="50" width="100" height="100" rx="10" fill="#2E7D32" stroke="#FFFFFF" stroke-width="2"/>
  <text x="180" y="90" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="34" font-weight="bold">2</text>
  <text x="180" y="124" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="15">발사간격-</text>
  <rect x="240" y="50" width="100" height="100" rx="10" fill="#1565C0" stroke="#FFFFFF" stroke-width="2"/>
  <text x="290" y="90" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="34" font-weight="bold">3</text>
  <text x="290" y="124" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="15">이동속도+</text>
</svg>"""

# -------- 게임오버 배너 --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="68" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="20">생존 시간은 왼쪽 위에서 확인!</text>
  <text x="180" y="136" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# 데미지 팝업 숫자 코스튬 0~9 (말풍선 say 미사용).
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
# ----- 5.1 튜닝 변수 24개 (개조 손잡이) -----
V_ATK      = "varAtk01"        # 마법공격력   1
V_FIREGAP  = "varFireGap02"    # 발사간격     0.6
V_BOLTSPD  = "varBoltSpd03"    # 마법탄속도   8
V_PIERCE   = "varPierce04"     # 관통        1
V_MULTI    = "varMulti05"      # 추가발사     1
V_MOVE     = "varMove06"       # 이동속도     4
V_MAXHP    = "varMaxHP07"      # 최대체력     5
V_HP       = "varHP08"         # 체력        5
V_INV      = "varInv09"        # 무적시간     25
V_MAGNET   = "varMagnet10"     # 흡수범위     90
V_MAGSPD   = "varMagSpd11"     # 흡수속도     6
V_LVUP     = "varLvUp12"       # 레벨업경험치  5
V_UP       = "varUp13"         # 강화량      1
V_SPAWNGAP = "varSpawnGap14"   # 스폰간격     1.2
V_RAMP     = "varRamp15"       # 난이도주기   15
V_EHPW     = "varEHPw16"       # 약한적_체력  1
V_ESPW     = "varESPw17"       # 약한적_속도  1.2
V_EXPW     = "varEXPw18"       # 약한적_경험치 1
V_EHPM     = "varEHPm19"       # 중간적_체력  3
V_ESPM     = "varESPm20"       # 중간적_속도  0.9
V_EXPM     = "varEXPm21"       # 중간적_경험치 3
V_EHPS     = "varEHPs22"       # 강한적_체력  6
V_ESPS     = "varESPs23"       # 강한적_속도  0.6
V_EXPS     = "varEXPs24"       # 강한적_경험치 6

# ----- 5.2 진행/내부 상태 변수 28개 -----
V_STATE    = "varState25"      # 게임상태  1=전투,2=강화선택,0=게임오버
V_TIME     = "varTime26"       # 생존시간 (점수)
V_LEVEL    = "varLevel27"      # 레벨
V_EXP      = "varEXP28"        # 경험치
V_INVT     = "varInvT29"       # 무적 (틱)
V_STAGE    = "varStage30"      # 단계
V_SPAWNN   = "varSpawnN31"     # 스폰카운트
V_ALIVE    = "varAlive32"      # 적수
V_AIMD     = "varAimD33"       # 조준거리
V_AIMX     = "varAimX34"       # 조준X
V_AIMY     = "varAimY35"       # 조준Y
V_AIMOK    = "varAimOK36"      # 조준있음
V_FIREX    = "varFireX37"      # 발사X
V_FIREY    = "varFireY38"      # 발사Y
V_FIREI    = "varFireI39"      # 발사i (부채꼴 인덱스)
V_SPX      = "varSPX40"        # 적생성X
V_SPY      = "varSPY41"        # 적생성Y
V_SPTYPE   = "varSPType42"     # 적생성종류
V_GEMX     = "varGemX43"       # 보석X
V_GEMY     = "varGemY44"       # 보석Y
V_GEMV     = "varGemV45"       # 보석값
V_DMGVAL   = "varDmgVal46"     # 데미지표시값
V_DMGX     = "varDmgX47"       # 데미지표시x
V_DMGY     = "varDmgY48"       # 데미지표시y
V_DMGDIGIT = "varDmgDigit49"   # 데미지숫자
V_DMGOFF   = "varDmgOff50"     # 데미지오프셋
V_DMGLEN   = "varDmgLen51"     # 데미지글자수
V_DMGPOS   = "varDmgPos52"     # 데미지자리

# ----- 5.3 클론-로컬 변수 11개 -----
V_BOLTISC   = "varBoltIsClone"   # 마법탄: 복제됨
V_BOLTPIER  = "varBoltPierce"    # 마법탄: 남은관통
V_BOLTHITCD = "varBoltHitCD"     # 마법탄: 관통쿨
V_EISC      = "varEnemyIsClone"  # 적: 복제됨
V_EHP       = "varEnemyHP"       # 적: 내체력
V_ESPD      = "varEnemySpd"      # 적: 내속도
V_ETYPE     = "varEnemyType"     # 적: 적종류
V_EHIT      = "varEnemyHit"      # 적: 피격쿨
V_GEMISC    = "varGemIsClone"    # 보석: 복제됨
V_GEMMINE   = "varGemMine"       # 보석: 내경험치
V_DMGISC    = "varDmgIsClone"    # 데미지: 복제됨

# ----- 5.4 메시지 7개 -----
BR_START   = "brStart01"     # 게임시작
BR_AIM     = "brAim02"       # 조준요청
BR_FIRE    = "brFire03"      # 발사
BR_GEM     = "brGem04"       # 보석생성
BR_LEVELUP = "brLevelUp05"   # 레벨업
BR_UPDONE  = "brUpDone06"    # 강화완료
BR_DMG     = "brDmg07"       # 데미지표시

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
    """wait (변수) 초."""
    v = gen(); bs[v] = mk("data_variable", fields={"VARIABLE": [name, vid]})
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": slot(v)})
    bs[v]["parent"] = bid
    return bid

def b_sound(bs, pitch):
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
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 클릭 → 변수 52개 전부 초기화(한 곳에 모음) → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val)
        seq.append((sid, bs[sid]))

    # ── 튜닝 24개 (plan 5.1) — 아이가 여기 숫자만 바꾸면 게임이 바뀐다 ──
    add_set("마법공격력", V_ATK, 1)
    add_set("발사간격", V_FIREGAP, 0.6)
    add_set("마법탄속도", V_BOLTSPD, 8)
    add_set("관통", V_PIERCE, 1)
    add_set("추가발사", V_MULTI, 1)
    add_set("이동속도", V_MOVE, 4)
    add_set("최대체력", V_MAXHP, 5)
    add_set("무적시간", V_INV, 25)
    add_set("흡수범위", V_MAGNET, 90)
    add_set("흡수속도", V_MAGSPD, 6)
    add_set("레벨업경험치", V_LVUP, 5)
    add_set("강화량", V_UP, 1)
    add_set("스폰간격", V_SPAWNGAP, 1.2)
    add_set("난이도주기", V_RAMP, 15)
    add_set("약한적_체력", V_EHPW, 1)
    add_set("약한적_속도", V_ESPW, 1.2)
    add_set("약한적_경험치", V_EXPW, 1)
    add_set("중간적_체력", V_EHPM, 3)
    add_set("중간적_속도", V_ESPM, 0.9)
    add_set("중간적_경험치", V_EXPM, 3)
    add_set("강한적_체력", V_EHPS, 6)
    add_set("강한적_속도", V_ESPS, 0.6)
    add_set("강한적_경험치", V_EXPS, 6)
    # 체력 = 최대체력 (튜닝 변수, 최대체력 참조)
    maxhp_r = vrep("최대체력", V_MAXHP)
    set_hp = b_setvar(bs, "체력", V_HP, maxhp_r)
    seq.append((set_hp, bs[set_hp]))

    # ── 진행 상태 28개 ──
    add_set("게임상태", V_STATE, 1)
    add_set("생존시간", V_TIME, 0)
    add_set("레벨", V_LEVEL, 1)
    add_set("경험치", V_EXP, 0)
    add_set("무적", V_INVT, 0)
    add_set("단계", V_STAGE, 0)
    add_set("스폰카운트", V_SPAWNN, 0)
    add_set("적수", V_ALIVE, 0)
    add_set("조준거리", V_AIMD, 99999)
    add_set("조준X", V_AIMX, 0)
    add_set("조준Y", V_AIMY, 0)
    add_set("조준있음", V_AIMOK, 0)
    add_set("발사X", V_FIREX, 0)
    add_set("발사Y", V_FIREY, 0)
    add_set("발사i", V_FIREI, 0)
    add_set("적생성X", V_SPX, 0)
    add_set("적생성Y", V_SPY, 0)
    add_set("적생성종류", V_SPTYPE, 1)
    add_set("보석X", V_GEMX, 0)
    add_set("보석Y", V_GEMY, 0)
    add_set("보석값", V_GEMV, 1)
    add_set("데미지표시값", V_DMGVAL, 0)
    add_set("데미지표시x", V_DMGX, 0)
    add_set("데미지표시y", V_DMGY, 0)
    add_set("데미지숫자", V_DMGDIGIT, 0)
    add_set("데미지오프셋", V_DMGOFF, 0)
    add_set("데미지글자수", V_DMGLEN, 0)
    add_set("데미지자리", V_DMGPOS, 0)

    w1 = b_wait(bs, 0.3); seq.append((w1, bs[w1]))
    bc_start = b_broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # ===== (B) 생존시간 타이머 + 난이도 단계 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=320, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    wt1 = b_wait(bs, 1)
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    inc_time = b_changevar(bs, "생존시간", V_TIME, 1)
    time_r = vrep("생존시간", V_TIME); ramp_r = vrep("난이도주기", V_RAMP)
    div_tr = op("operator_divide", time_r, ramp_r)
    floor_tr = gen(); bs[floor_tr] = mk("operator_mathop",
        inputs={"NUM": slot(div_tr)}, fields={"OPERATOR": ["floor", None]})
    bs[div_tr]["parent"] = floor_tr
    set_stage = b_setvar(bs, "단계", V_STAGE, floor_tr)
    chain([(inc_time, bs[inc_time]), (set_stage, bs[set_stage])])
    if_play_b = b_if(bs, cond_play_b, inc_time)
    chain([(wt1, bs[wt1]), (if_play_b, bs[if_play_b])])
    fe_b = b_forever(bs, wt1)
    chain([(hb, bs[hb]), (fe_b, bs[fe_b])])

    # ===== (C) 무적 타이머 감소 forever =====
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=520)
    invt_r = vrep("무적", V_INVT)
    cond_inv_pos = cmp_op("operator_gt", invt_r, 0)
    dec_inv = b_changevar(bs, "무적", V_INVT, -1)
    if_inv = b_if(bs, cond_inv_pos, dec_inv)
    wc = b_wait(bs, 0.025)
    chain([(if_inv, bs[if_inv]), (wc, bs[wc])])
    fe_c = b_forever(bs, if_inv)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # ===== (D) 레벨업 / 게임오버 감시 forever =====
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=320, y=520)
    state_ready = vrep("게임상태", V_STATE)
    cond_ready = cmp_op("operator_equals", state_ready, 1)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, cond_ready]})
    bs[cond_ready]["parent"] = wu

    # if (경험치 >= 레벨업경험치) and (게임상태=1)
    exp_r = vrep("경험치", V_EXP); lvup_r = vrep("레벨업경험치", V_LVUP)
    cond_exp_lt = cmp_op("operator_lt", exp_r, lvup_r)
    not_exp_lt = gen(); bs[not_exp_lt] = mk("operator_not", inputs={"OPERAND": [2, cond_exp_lt]})
    bs[cond_exp_lt]["parent"] = not_exp_lt
    state_d1 = vrep("게임상태", V_STATE)
    cond_pl_d1 = cmp_op("operator_equals", state_d1, 1)
    cond_levelup = bool_op("operator_and", not_exp_lt, cond_pl_d1)
    lvup_r2 = vrep("레벨업경험치", V_LVUP)
    neg_lvup = op("operator_subtract", 0, lvup_r2)
    dec_exp = b_changevar(bs, "경험치", V_EXP, neg_lvup)
    inc_level = b_changevar(bs, "레벨", V_LEVEL, 1)
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_lvup = b_broadcast(bs, "레벨업", BR_LEVELUP)
    chain([(dec_exp, bs[dec_exp]), (inc_level, bs[inc_level]),
           (set_st2, bs[set_st2]), (bc_lvup, bs[bc_lvup])])
    if_levelup = b_if(bs, cond_levelup, dec_exp)

    # if (체력 < 1) and (게임상태=1) → 게임상태=0
    hp_r = vrep("체력", V_HP)
    cond_dead = cmp_op("operator_lt", hp_r, 1)
    state_d2 = vrep("게임상태", V_STATE)
    cond_pl_d2 = cmp_op("operator_equals", state_d2, 1)
    cond_over = bool_op("operator_and", cond_dead, cond_pl_d2)
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    if_over = b_if(bs, cond_over, set_st0)

    wd = b_wait(bs, 0.05)
    chain([(if_levelup, bs[if_levelup]), (if_over, bs[if_over]), (wd, bs[wd])])
    fe_d = b_forever(bs, if_levelup)
    chain([(hd, bs[hd]), (wu, bs[wu]), (fe_d, bs[fe_d])])

    return bs

# ============================================================
#  마법사 (MAGE)
# ============================================================
def build_mage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 초기화 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(60)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    clr = gen(); bs[clr] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (rs, bs[rs]),
           (pd, bs[pd]), (g0, bs[g0]), (front, bs[front]), (clr, bs[clr])])

    # ===== (B) 8방향 이동 forever (게임상태=1) =====
    hb = gen(); bs[hb] = mk("event_whenflagclicked", top=True, x=20, y=220)
    inner = []
    # right
    move_r = vrep("이동속도", V_MOVE)
    cx_r = gen(); bs[cx_r] = mk("motion_changexby", inputs={"DX": slot(move_r)})
    bs[move_r]["parent"] = cx_r
    inner.append(b_if(bs, b_keypressed(bs, "right arrow"), cx_r))
    # left
    move_l = vrep("이동속도", V_MOVE)
    neg_move = op("operator_subtract", 0, move_l)
    cx_l = gen(); bs[cx_l] = mk("motion_changexby", inputs={"DX": slot(neg_move)})
    bs[neg_move]["parent"] = cx_l
    inner.append(b_if(bs, b_keypressed(bs, "left arrow"), cx_l))
    # up
    move_u = vrep("이동속도", V_MOVE)
    cy_u = gen(); bs[cy_u] = mk("motion_changeyby", inputs={"DY": slot(move_u)})
    bs[move_u]["parent"] = cy_u
    inner.append(b_if(bs, b_keypressed(bs, "up arrow"), cy_u))
    # down
    move_dn = vrep("이동속도", V_MOVE)
    neg_move2 = op("operator_subtract", 0, move_dn)
    cy_dn = gen(); bs[cy_dn] = mk("motion_changeyby", inputs={"DY": slot(neg_move2)})
    bs[neg_move2]["parent"] = cy_dn
    inner.append(b_if(bs, b_keypressed(bs, "down arrow"), cy_dn))
    # clamp x ±230, y ±170
    def clamp(axis_pos_op, set_op, cmp, limit):
        xp = gen(); bs[xp] = mk(axis_pos_op)
        c = cmp_op(cmp, xp, limit)
        st = gen(); bs[st] = mk(set_op, inputs={("X" if set_op=="motion_setx" else "Y"): num(limit)})
        return b_if(bs, c, st)
    inner.append(clamp("motion_xposition", "motion_setx", "operator_gt", 230))
    inner.append(clamp("motion_xposition", "motion_setx", "operator_lt", -230))
    inner.append(clamp("motion_yposition", "motion_sety", "operator_gt", 170))
    inner.append(clamp("motion_yposition", "motion_sety", "operator_lt", -170))
    chain([(b, bs[b]) for b in inner])
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    if_play_b = b_if(bs, cond_play_b, inner[0])
    wb = b_wait(bs, 0.025)
    chain([(if_play_b, bs[if_play_b]), (wb, bs[wb])])
    fe_b = b_forever(bs, if_play_b)
    chain([(hb, bs[hb]), (fe_b, bs[fe_b])])

    # ===== (C) 자동 조준 발사 forever (핵심) =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=320, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # if 게임상태=1 { 조준거리=99999; 조준있음=0; 조준요청 and wait;
    #                 if 조준있음=1 { 발사X=조준X; 발사Y=조준Y; sound 120; 발사 } ; wait 발사간격 }
    # else { wait 0.05 }
    set_aimd = b_setvar(bs, "조준거리", V_AIMD, 99999)
    set_aimok0 = b_setvar(bs, "조준있음", V_AIMOK, 0)
    bcw_aim = b_broadcast_wait(bs, "조준요청", BR_AIM)
    aimok_r = vrep("조준있음", V_AIMOK)
    cond_haveaim = cmp_op("operator_equals", aimok_r, 1)
    aimx_r = vrep("조준X", V_AIMX); aimy_r = vrep("조준Y", V_AIMY)
    set_fx = b_setvar(bs, "발사X", V_FIREX, aimx_r)
    set_fy = b_setvar(bs, "발사Y", V_FIREY, aimy_r)
    sh_fire, _ = b_sound(bs, 120)
    bc_fire = b_broadcast(bs, "발사", BR_FIRE)
    chain([(set_fx, bs[set_fx]), (set_fy, bs[set_fy]), (sh_fire, bs[sh_fire]),
           (bc_fire, bs[bc_fire])])
    if_haveaim = b_if(bs, cond_haveaim, set_fx)
    w_gap = b_wait_var(bs, V_FIREGAP, "발사간격")
    chain([(set_aimd, bs[set_aimd]), (set_aimok0, bs[set_aimok0]),
           (bcw_aim, bs[bcw_aim]), (if_haveaim, bs[if_haveaim]), (w_gap, bs[w_gap])])
    state_c = vrep("게임상태", V_STATE)
    cond_play_c = cmp_op("operator_equals", state_c, 1)
    w_idle = b_wait(bs, 0.05)
    if_fire = b_ifelse(bs, cond_play_c, set_aimd, w_idle)
    fe_c = b_forever(bs, if_fire)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # ===== (D) 피격 감시 forever =====
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=640, y=220)
    tc_e = b_touching(bs, "적")
    invt_r = vrep("무적", V_INVT)
    cond_noinv = cmp_op("operator_equals", invt_r, 0)
    state_d = vrep("게임상태", V_STATE)
    cond_play_d = cmp_op("operator_equals", state_d, 1)
    cond_d_a = bool_op("operator_and", tc_e, cond_noinv)
    cond_hurt = bool_op("operator_and", cond_d_a, cond_play_d)
    dec_hp = b_changevar(bs, "체력", V_HP, -1)
    inv_r = vrep("무적시간", V_INV)
    set_invt = b_setvar(bs, "무적", V_INVT, inv_r)
    sh_hurt, _ = b_sound(bs, -300)
    chain([(dec_hp, bs[dec_hp]), (set_invt, bs[set_invt]), (sh_hurt, bs[sh_hurt])])
    if_hurt = b_if(bs, cond_hurt, dec_hp)
    wd = b_wait(bs, 0.04)
    chain([(if_hurt, bs[if_hurt]), (wd, bs[wd])])
    fe_d = b_forever(bs, if_hurt)
    chain([(hd, bs[hd]), (fe_d, bs[fe_d])])

    return bs

# ============================================================
#  마법탄 (BOLT: 스포너 + 클론 본체)
# ============================================================
def build_bolt_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(45)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_BOLTISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 발사 → 추가발사 개수만큼 탄 클론 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    isc_chk = vrep("복제됨", V_BOLTISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    set_fi0 = b_setvar(bs, "발사i", V_FIREI, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    w_sp = b_wait(bs, 0.01)  # 클론이 현재 발사i 를 조준 방향으로 스냅샷할 시간
    inc_fi = b_changevar(bs, "발사i", V_FIREI, 1)
    chain([(cclone, bs[cclone]), (w_sp, bs[w_sp]), (inc_fi, bs[inc_fi])])
    multi_r = vrep("추가발사", V_MULTI)
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": slot(multi_r), "SUBSTACK": [2, cclone]})
    bs[multi_r]["parent"] = rep; bs[cclone]["parent"] = rep
    chain([(set_fi0, bs[set_fi0]), (rep, bs[rep])])
    if_spawn = b_if(bs, cond_orig, set_fi0)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 목표로 직진, 관통 처리
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_BOLTISC, 1)
    pierce_r = vrep("관통", V_PIERCE)
    set_rem = b_setvar(bs, "남은관통", V_BOLTPIER, pierce_r)
    set_hcd0 = b_setvar(bs, "관통쿨", V_BOLTHITCD, 0)
    # goto (마법사 x, 마법사 y)
    mx_r = _of(bs, "마법사", "x position"); my_r = _of(bs, "마법사", "y position")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(mx_r), "Y": slot(my_r)})
    bs[mx_r]["parent"] = g; bs[my_r]["parent"] = g
    # 방향 = atan((발사X - x)/(발사Y - y)) + ((y > 발사Y)*180) + ((발사i-((추가발사-1)/2))*12)
    fx_r = vrep("발사X", V_FIREX); xp1 = gen(); bs[xp1] = mk("motion_xposition")
    dx = op("operator_subtract", fx_r, xp1)
    fy_r = vrep("발사Y", V_FIREY); yp1 = gen(); bs[yp1] = mk("motion_yposition")
    dy = op("operator_subtract", fy_r, yp1)
    ratio = op("operator_divide", dx, dy)
    atanv = gen(); bs[atanv] = mk("operator_mathop",
        inputs={"NUM": slot(ratio)}, fields={"OPERATOR": ["atan", None]})
    bs[ratio]["parent"] = atanv
    yp2 = gen(); bs[yp2] = mk("motion_yposition"); fy_r2 = vrep("발사Y", V_FIREY)
    cond_below = cmp_op("operator_gt", yp2, fy_r2)
    flip = op("operator_multiply", cond_below, 180)
    # spread = (발사i - ((추가발사-1)/2)) * 12
    multi_r2 = vrep("추가발사", V_MULTI)
    m_minus1 = op("operator_subtract", multi_r2, 1)
    half = op("operator_divide", m_minus1, 2)
    fi_r = vrep("발사i", V_FIREI)
    fi_off = op("operator_subtract", fi_r, half)
    spread = op("operator_multiply", fi_off, 12)
    sum1 = op("operator_add", atanv, flip)
    sum2 = op("operator_add", sum1, spread)
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": slot(sum2)})
    bs[sum2]["parent"] = pdir
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")

    # repeat until (touching edge) or (게임상태=0) { move; 관통 처리; wait }
    mv = b_movesteps(bs, V_BOLTSPD)
    # if (touching 적) and (관통쿨=0) { 남은관통-=1; 관통쿨=4; if 남은관통<1 delete }
    tc_e = b_touching(bs, "적")
    hcd_r = vrep("관통쿨", V_BOLTHITCD)
    cond_hcd0 = cmp_op("operator_equals", hcd_r, 0)
    cond_hit = bool_op("operator_and", tc_e, cond_hcd0)
    dec_rem = b_changevar(bs, "남은관통", V_BOLTPIER, -1)
    set_hcd = b_setvar(bs, "관통쿨", V_BOLTHITCD, 4)
    rem_r = vrep("남은관통", V_BOLTPIER)
    cond_rem_lt = cmp_op("operator_lt", rem_r, 1)
    del_in = gen(); bs[del_in] = mk("control_delete_this_clone")
    if_rem = b_if(bs, cond_rem_lt, del_in)
    chain([(dec_rem, bs[dec_rem]), (set_hcd, bs[set_hcd]), (if_rem, bs[if_rem])])
    if_hit = b_if(bs, cond_hit, dec_rem)
    # if 관통쿨>0 change -1
    hcd_r2 = vrep("관통쿨", V_BOLTHITCD)
    cond_hcd_pos = cmp_op("operator_gt", hcd_r2, 0)
    dec_hcd = b_changevar(bs, "관통쿨", V_BOLTHITCD, -1)
    if_hcd = b_if(bs, cond_hcd_pos, dec_hcd)
    w_mv = b_wait(bs, 0.01)
    chain([(mv, bs[mv]), (if_hit, bs[if_hit]), (if_hcd, bs[if_hcd]), (w_mv, bs[w_mv])])
    # repeat until cond
    edge_menu = gen(); bs[edge_menu] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_edge = gen(); bs[tc_edge] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge_menu]})
    bs[edge_menu]["parent"] = tc_edge
    state_b = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_b, 0)
    cond_stop = bool_op("operator_or", tc_edge, cond_over)
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_stop], "SUBSTACK": [2, mv]})
    bs[cond_stop]["parent"] = ru; bs[mv]["parent"] = ru
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_rem, bs[set_rem]),
           (set_hcd0, bs[set_hcd0]), (g, bs[g]), (pdir, bs[pdir]),
           (front, bs[front]), (show, bs[show]), (ru, bs[ru]), (del_end, bs[del_end])])

    return bs

# ============================================================
#  적 (ENEMY: 시간 기반 스포너 + 클론 본체 + 조준 보고)
# ============================================================
def build_enemy_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_EISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 시간 기반 스폰 forever (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    isc_chk = vrep("복제됨", V_EISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)

    # forever body — if 게임상태=1 { 가장자리 좌표 ; 종류 결정 ; 카운트 ; clone } ; wait 스폰간격
    # ── 가장자리(상/하/좌/우) 랜덤 스폰 좌표 (임시 변수 없이 코인플립 2회) ──
    # if (pick random 0~1)=0 → 상/하 변, else 좌/우 변
    coin_h = gen(); bs[coin_h] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_horiz = cmp_op("operator_equals", coin_h, 0)
    #   상/하: X random, Y = ±175
    rx_h = gen(); bs[rx_h] = mk("operator_random", inputs={"FROM": num(-230), "TO": num(230)})
    set_spx_h = gen(); bs[set_spx_h] = mk("data_setvariableto",
        inputs={"VALUE": slot(rx_h)}, fields={"VARIABLE": ["적생성X", V_SPX]})
    bs[rx_h]["parent"] = set_spx_h
    coin_tb = gen(); bs[coin_tb] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_top = cmp_op("operator_equals", coin_tb, 0)
    set_spy_top = b_setvar(bs, "적생성Y", V_SPY, 175)
    set_spy_bot = b_setvar(bs, "적생성Y", V_SPY, -175)
    if_tb = b_ifelse(bs, cond_top, set_spy_top, set_spy_bot)
    chain([(set_spx_h, bs[set_spx_h]), (if_tb, bs[if_tb])])
    #   좌/우: Y random, X = ±235
    ry_v = gen(); bs[ry_v] = mk("operator_random", inputs={"FROM": num(-170), "TO": num(170)})
    set_spy_v = gen(); bs[set_spy_v] = mk("data_setvariableto",
        inputs={"VALUE": slot(ry_v)}, fields={"VARIABLE": ["적생성Y", V_SPY]})
    bs[ry_v]["parent"] = set_spy_v
    coin_lr = gen(); bs[coin_lr] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    cond_left = cmp_op("operator_equals", coin_lr, 0)
    set_spx_left = b_setvar(bs, "적생성X", V_SPX, -235)
    set_spx_right = b_setvar(bs, "적생성X", V_SPX, 235)
    if_lr = b_ifelse(bs, cond_left, set_spx_left, set_spx_right)
    chain([(set_spy_v, bs[set_spy_v]), (if_lr, bs[if_lr])])
    if_edge = b_ifelse(bs, cond_horiz, set_spx_h, set_spy_v)

    # ── 단계로 종류 결정 (약→약·중→중·강) ──
    stage_r1 = vrep("단계", V_STAGE)
    cond_st0 = cmp_op("operator_equals", stage_r1, 0)
    set_type1 = b_setvar(bs, "적생성종류", V_SPTYPE, 1)
    # else if 단계=1 → 1 + (스폰카운트 mod 2)
    stage_r2 = vrep("단계", V_STAGE)
    cond_st1 = cmp_op("operator_equals", stage_r2, 1)
    spn_r = vrep("스폰카운트", V_SPAWNN)
    mod2 = op("operator_mod", spn_r, 2)
    type_alt = op("operator_add", 1, mod2)
    set_type_alt = gen(); bs[set_type_alt] = mk("data_setvariableto",
        inputs={"VALUE": slot(type_alt)}, fields={"VARIABLE": ["적생성종류", V_SPTYPE]})
    bs[type_alt]["parent"] = set_type_alt
    # else → 2 + (pick random 0~1)
    rnd01 = gen(); bs[rnd01] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    type_ms = op("operator_add", 2, rnd01)
    set_type_ms = gen(); bs[set_type_ms] = mk("data_setvariableto",
        inputs={"VALUE": slot(type_ms)}, fields={"VARIABLE": ["적생성종류", V_SPTYPE]})
    bs[type_ms]["parent"] = set_type_ms
    if_st1 = b_ifelse(bs, cond_st1, set_type_alt, set_type_ms)
    if_type = b_ifelse(bs, cond_st0, set_type1, if_st1)

    inc_spn = b_changevar(bs, "스폰카운트", V_SPAWNN, 1)
    inc_alive = b_changevar(bs, "적수", V_ALIVE, 1)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(if_edge, bs[if_edge]), (if_type, bs[if_type]), (inc_spn, bs[inc_spn]),
           (inc_alive, bs[inc_alive]), (cclone, bs[cclone])])
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    if_play_b = b_if(bs, cond_play_b, if_edge)
    w_gap = b_wait_var(bs, V_SPAWNGAP, "스폰간격")
    chain([(if_play_b, bs[if_play_b]), (w_gap, bs[w_gap])])
    fe_b = b_forever(bs, if_play_b)
    if_spawner = b_if(bs, cond_orig, fe_b)
    chain([(hb, bs[hb]), (if_spawner, bs[if_spawner])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=460)
    set_isc1 = b_setvar(bs, "복제됨", V_EISC, 1)
    sptype_r = vrep("적생성종류", V_SPTYPE)
    set_type = b_setvar(bs, "적종류", V_ETYPE, sptype_r)
    set_hit0 = b_setvar(bs, "피격쿨", V_EHIT, 0)
    chain([(set_isc1, bs[set_isc1]), (set_type, bs[set_type]), (set_hit0, bs[set_hit0])])

    # 종류별 체력/속도/외형 (매직넘버 없음: 종류 튜닝 변수 참조)
    def type_branch(type_val, hp_vid, hp_name, spd_vid, spd_name, costume, size_val):
        cond_t = cmp_op("operator_equals", vrep("적종류", V_ETYPE), type_val)
        hp_r = vrep(hp_name, hp_vid)
        set_hp = b_setvar(bs, "내체력", V_EHP, hp_r)
        spd_r = vrep(spd_name, spd_vid)
        set_spd = b_setvar(bs, "내속도", V_ESPD, spd_r)
        cmc = gen(); bs[cmc] = mk("looks_costume", fields={"COSTUME": [costume, None]}, shadow=True)
        sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc]})
        bs[cmc]["parent"] = sw
        szb = gen(); bs[szb] = mk("looks_setsizeto", inputs={"SIZE": num(size_val)})
        chain([(set_hp, bs[set_hp]), (set_spd, bs[set_spd]), (sw, bs[sw]), (szb, bs[szb])])
        return b_if(bs, cond_t, set_hp)
    if_t1 = type_branch(1, V_EHPW, "약한적_체력", V_ESPW, "약한적_속도", "슬라임", 60)
    if_t2 = type_branch(2, V_EHPM, "중간적_체력", V_ESPM, "중간적_속도", "박쥐", 70)
    if_t3 = type_branch(3, V_EHPS, "강한적_체력", V_ESPS, "강한적_속도", "골렘", 95)
    chain([(if_t1, bs[if_t1]), (if_t2, bs[if_t2]), (if_t3, bs[if_t3])])

    spx_r = vrep("적생성X", V_SPX); spy_r = vrep("적생성Y", V_SPY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(spx_r), "Y": slot(spy_r)})
    bs[spx_r]["parent"] = g; bs[spy_r]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")

    body = []
    # 1) 게임오버 정리
    state1 = vrep("게임상태", V_STATE)
    cond_go = cmp_op("operator_equals", state1, 0)
    dec_alive_go = b_changevar(bs, "적수", V_ALIVE, -1)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    chain([(dec_alive_go, bs[dec_alive_go]), (del_go, bs[del_go])])
    if_go = b_if(bs, cond_go, dec_alive_go)
    body.append(if_go)

    # 2) 추적 (게임상태=1): point towards 마법사 ; move 내속도
    pt = b_pointtowards(bs, "마법사")
    mv = b_movesteps(bs, V_ESPD)
    chain([(pt, bs[pt]), (mv, bs[mv])])
    state2 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state2, 1)
    if_chase = b_if(bs, cond_play2, pt)
    body.append(if_chase)

    # 3) 마법탄 피격: if touching 마법탄 AND 피격쿨=0
    tc_bolt = b_touching(bs, "마법탄")
    hit_r = vrep("피격쿨", V_EHIT)
    cond_hit0 = cmp_op("operator_equals", hit_r, 0)
    cond_struck = bool_op("operator_and", tc_bolt, cond_hit0)
    atk_r = vrep("마법공격력", V_ATK)
    neg_atk = op("operator_subtract", 0, atk_r)
    dec_myhp = b_changevar(bs, "내체력", V_EHP, neg_atk)
    set_hit = b_setvar(bs, "피격쿨", V_EHIT, 8)
    sh_hit, _ = b_sound(bs, 0)
    dmgval_r = vrep("마법공격력", V_ATK)
    set_dval = b_setvar(bs, "데미지표시값", V_DMGVAL, dmgval_r)
    dmgx_pos = gen(); bs[dmgx_pos] = mk("motion_xposition")
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, dmgx_pos)
    dmgy_pos = gen(); bs[dmgy_pos] = mk("motion_yposition")
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, dmgy_pos)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    chain([(dec_myhp, bs[dec_myhp]), (set_hit, bs[set_hit]), (sh_hit, bs[sh_hit]),
           (set_dval, bs[set_dval]), (set_dx, bs[set_dx]), (set_dy, bs[set_dy]),
           (bc_dmg, bs[bc_dmg])])
    if_struck = b_if(bs, cond_struck, dec_myhp)
    body.append(if_struck)
    # if 피격쿨>0 → -1
    hit_r2 = vrep("피격쿨", V_EHIT)
    cond_hitpos = cmp_op("operator_gt", hit_r2, 0)
    dec_hit = b_changevar(bs, "피격쿨", V_EHIT, -1)
    if_hitcd = b_if(bs, cond_hitpos, dec_hit)
    body.append(if_hitcd)

    # 4) 처치: if 내체력<1 → 보석 드롭 + 폭발 + 삭제
    myhp_r = vrep("내체력", V_EHP)
    cond_dead = cmp_op("operator_lt", myhp_r, 1)
    gx_pos = gen(); bs[gx_pos] = mk("motion_xposition")
    set_gx = b_setvar(bs, "보석X", V_GEMX, gx_pos)
    gy_pos = gen(); bs[gy_pos] = mk("motion_yposition")
    set_gy = b_setvar(bs, "보석Y", V_GEMY, gy_pos)
    # 보석값 = 종류별 경험치
    type_g1 = cmp_op("operator_equals", vrep("적종류", V_ETYPE), 1)
    set_gv_w = b_setvar(bs, "보석값", V_GEMV, vrep("약한적_경험치", V_EXPW))
    type_g2 = cmp_op("operator_equals", vrep("적종류", V_ETYPE), 2)
    set_gv_m = b_setvar(bs, "보석값", V_GEMV, vrep("중간적_경험치", V_EXPM))
    set_gv_s = b_setvar(bs, "보석값", V_GEMV, vrep("강한적_경험치", V_EXPS))
    if_gv2 = b_ifelse(bs, type_g2, set_gv_m, set_gv_s)
    if_gv = b_ifelse(bs, type_g1, set_gv_w, if_gv2)
    bc_gem = b_broadcast(bs, "보석생성", BR_GEM)
    dec_alive = b_changevar(bs, "적수", V_ALIVE, -1)
    exm = gen(); bs[exm] = mk("looks_costume", fields={"COSTUME": ["폭발", None]}, shadow=True)
    sw_ex = gen(); bs[sw_ex] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, exm]})
    bs[exm]["parent"] = sw_ex
    sh_die, _ = b_sound(bs, -50)
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(12)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(20)}, fields={"EFFECT": ["GHOST", None]})
    w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK": [2, ch_sz]})
    bs[ch_sz]["parent"] = rep_an
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")
    chain([(set_gx, bs[set_gx]), (set_gy, bs[set_gy]), (if_gv, bs[if_gv]),
           (bc_gem, bs[bc_gem]), (dec_alive, bs[dec_alive]), (sh_die, bs[sh_die]),
           (sw_ex, bs[sw_ex]), (rep_an, bs[rep_an]), (del_k, bs[del_k])])
    if_kill = b_if(bs, cond_dead, set_gx)
    body.append(if_kill)

    w_body = b_wait(bs, 0.025)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1])])
    chain([(set_hit0, bs[set_hit0]), (if_t1, bs[if_t1])])
    chain([(if_t3, bs[if_t3]), (g, bs[g]), (show, bs[show]), (fe_body, bs[fe_body])])

    # (D) 조준 보고 (최솟값 리덕션) — wait 없는 원자 실행
    hd = gen(); bs[hd] = mk("control_start_as_clone", top=True, x=400, y=460)
    # (조준요청 수신 스크립트는 클론에서만 의미 있음 → when I receive 로 받되 복제됨=1 가드)
    # 이벤트 수신 헤드
    hd2 = gen(); bs[hd2] = mk("event_whenbroadcastreceived", top=True, x=400, y=180,
        fields={"BROADCAST_OPTION": ["조준요청", BR_AIM]})
    isc_chk2 = vrep("복제됨", V_EISC)
    cond_clone = cmp_op("operator_equals", isc_chk2, 1)
    state_aim = vrep("게임상태", V_STATE)
    cond_play_aim = cmp_op("operator_equals", state_aim, 1)
    cond_active = bool_op("operator_and", cond_clone, cond_play_aim)
    dist_r = b_distance_to(bs, "마법사")
    aimd_r = vrep("조준거리", V_AIMD)
    cond_closer = cmp_op("operator_lt", dist_r, aimd_r)
    dist_r2 = b_distance_to(bs, "마법사")
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
    chain([(hd2, bs[hd2]), (if_active, bs[if_active])])
    # remove the unused stray clone-hat placeholder
    del bs[hd]

    return bs

# ============================================================
#  경험치보석 (GEM: 드롭 + 흡수)
# ============================================================
def build_gem_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(55)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_GEMISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 보석생성 → 그 자리에 보석 클론 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["보석생성", BR_GEM]})
    isc_chk = vrep("복제됨", V_GEMISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 흡수범위 안이면 빨려옴 → 닿으면 경험치
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_GEMISC, 1)
    gemv_r = vrep("보석값", V_GEMV)
    set_mine = b_setvar(bs, "내경험치", V_GEMMINE, gemv_r)
    gx_r = vrep("보석X", V_GEMX); gy_r = vrep("보석Y", V_GEMY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(gx_r), "Y": slot(gy_r)})
    bs[gx_r]["parent"] = g; bs[gy_r]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")

    # forever
    state1 = vrep("게임상태", V_STATE)
    cond_go = cmp_op("operator_equals", state1, 0)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    if_go = b_if(bs, cond_go, del_go)
    # if 게임상태=1 { if dist<흡수범위 {point towards 마법사; move 흡수속도} ; if touching 마법사 {경험치+=내경험치; sound; delete} }
    dist_r = b_distance_to(bs, "마법사")
    magnet_r = vrep("흡수범위", V_MAGNET)
    cond_near = cmp_op("operator_lt", dist_r, magnet_r)
    pt = b_pointtowards(bs, "마법사")
    mv = b_movesteps(bs, V_MAGSPD)
    chain([(pt, bs[pt]), (mv, bs[mv])])
    if_near = b_if(bs, cond_near, pt)
    tc_m = b_touching(bs, "마법사")
    inc_exp = b_changevar(bs, "경험치", V_EXP, V_GEMMINE if False else None) if False else None
    mine_r = vrep("내경험치", V_GEMMINE)
    inc_exp = b_changevar(bs, "경험치", V_EXP, mine_r)
    sh_pick, _ = b_sound(bs, 180)
    del_pick = gen(); bs[del_pick] = mk("control_delete_this_clone")
    chain([(inc_exp, bs[inc_exp]), (sh_pick, bs[sh_pick]), (del_pick, bs[del_pick])])
    if_pick = b_if(bs, tc_m, inc_exp)
    chain([(if_near, bs[if_near]), (if_pick, bs[if_pick])])
    state2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state2, 1)
    if_play = b_if(bs, cond_play, if_near)
    w_body = b_wait(bs, 0.025)
    chain([(if_go, bs[if_go]), (if_play, bs[if_play]), (w_body, bs[w_body])])
    fe_body = b_forever(bs, if_go)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_mine, bs[set_mine]),
           (g, bs[g]), (show, bs[show]), (fe_body, bs[fe_body])])

    return bs

# ============================================================
#  강화카드 (CARD: 레벨업 시 강화 택1)
# ============================================================
def build_card_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    # (B) 레벨업 → show, 1/2/3 대기, 강화 적용, 강화완료
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["레벨업", BR_LEVELUP]})
    show = gen(); bs[show] = mk("looks_show")
    k1 = b_keypressed(bs, "1"); k2 = b_keypressed(bs, "2"); k3 = b_keypressed(bs, "3")
    or12 = bool_op("operator_or", k1, k2)
    or123 = bool_op("operator_or", or12, k3)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, or123]})
    bs[or123]["parent"] = wu
    # if key1 → 마법공격력 += 강화량
    up_r1 = vrep("강화량", V_UP)
    ch_atk = b_changevar(bs, "마법공격력", V_ATK, up_r1)
    if_k1 = b_if(bs, b_keypressed(bs, "1"), ch_atk)
    # if key2 → 발사간격 -= (0.05*강화량) ; 하한 0.1
    up_r2 = vrep("강화량", V_UP)
    dec_amt = op("operator_multiply", 0.05, up_r2)
    neg_dec = op("operator_subtract", 0, dec_amt)
    ch_gap = b_changevar(bs, "발사간격", V_FIREGAP, neg_dec)
    gap_r = vrep("발사간격", V_FIREGAP)
    cond_too_low = cmp_op("operator_lt", gap_r, 0.1)
    set_gap_min = b_setvar(bs, "발사간격", V_FIREGAP, 0.1)
    if_clamp = b_if(bs, cond_too_low, set_gap_min)
    chain([(ch_gap, bs[ch_gap]), (if_clamp, bs[if_clamp])])
    if_k2 = b_if(bs, b_keypressed(bs, "2"), ch_gap)
    # if key3 → 이동속도 += 강화량
    up_r3 = vrep("강화량", V_UP)
    ch_move = b_changevar(bs, "이동속도", V_MOVE, up_r3)
    if_k3 = b_if(bs, b_keypressed(bs, "3"), ch_move)

    sh_up, _ = b_sound(bs, 200)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    w1 = b_wait(bs, 0.2)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    bc_done = b_broadcast(bs, "강화완료", BR_UPDONE)
    chain([(hb, bs[hb]), (show, bs[show]), (wu, bs[wu]),
           (if_k1, bs[if_k1]), (if_k2, bs[if_k2]), (if_k3, bs[if_k3]),
           (sh_up, bs[sh_up]), (hi2, bs[hi2]), (w1, bs[w1]),
           (set_st1, bs[set_st1]), (bc_done, bs[bc_done])])

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
#  데미지 (플로팅 데미지 팝업) — 숫자 코스튬 0~9, say 미사용
# ============================================================
def build_damage_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_DMGISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 데미지표시 받으면 자릿수만큼 클론 생성 (원본만, letter-of 렌더)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["데미지표시", BR_DMG]})
    isc_chk = vrep("복제됨", V_DMGISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    # 데미지글자수 = length of 데미지표시값
    dval_r = vrep("데미지표시값", V_DMGVAL)
    len_b = gen(); bs[len_b] = mk("operator_length", inputs={"STRING": slot(dval_r)})
    bs[dval_r]["parent"] = len_b
    set_len = b_setvar(bs, "데미지글자수", V_DMGLEN, len_b)
    set_pos1 = b_setvar(bs, "데미지자리", V_DMGPOS, 1)
    # repeat 데미지글자수 { 데미지숫자 = letter 데미지자리 of 데미지표시값 ;
    #   데미지오프셋 = ((데미지자리-1)*14) - ((데미지글자수-1)*7) ; clone ; 데미지자리+1 ; wait }
    pos_r = vrep("데미지자리", V_DMGPOS); dval_r2 = vrep("데미지표시값", V_DMGVAL)
    letter_b = gen(); bs[letter_b] = mk("operator_letter_of",
        inputs={"LETTER": slot(pos_r), "STRING": slot(dval_r2)})
    bs[pos_r]["parent"] = letter_b; bs[dval_r2]["parent"] = letter_b
    set_digit = b_setvar(bs, "데미지숫자", V_DMGDIGIT, letter_b)
    pos_r2 = vrep("데미지자리", V_DMGPOS)
    pos_minus1 = op("operator_subtract", pos_r2, 1)
    off_left = op("operator_multiply", pos_minus1, 14)
    len_r = vrep("데미지글자수", V_DMGLEN)
    len_minus1 = op("operator_subtract", len_r, 1)
    off_center = op("operator_multiply", len_minus1, 7)
    off_final = op("operator_subtract", off_left, off_center)
    set_off = b_setvar(bs, "데미지오프셋", V_DMGOFF, off_final)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    inc_pos = b_changevar(bs, "데미지자리", V_DMGPOS, 1)
    w_sp = b_wait(bs, 0.06)
    chain([(set_digit, bs[set_digit]), (set_off, bs[set_off]), (cclone, bs[cclone]),
           (inc_pos, bs[inc_pos]), (w_sp, bs[w_sp])])
    len_rep = vrep("데미지글자수", V_DMGLEN)
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": slot(len_rep), "SUBSTACK": [2, set_digit]})
    bs[len_rep]["parent"] = rep; bs[set_digit]["parent"] = rep
    chain([(set_len, bs[set_len]), (set_pos1, bs[set_pos1]), (rep, bs[rep])])
    if_spawn = b_if(bs, cond_orig, set_len)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 숫자 코스튬 렌더 → 떠오르며 페이드 후 삭제
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_DMGISC, 1)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    # switch costume to (데미지숫자) — 값이 "0".."9" 문자열, 코스튬 이름과 직접 매칭
    dig_r = vrep("데미지숫자", V_DMGDIGIT)
    sw_num = gen(); bs[sw_num] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(dig_r)})
    bs[dig_r]["parent"] = sw_num
    # goto (데미지표시x + 데미지오프셋, 데미지표시y)
    dx_r = vrep("데미지표시x", V_DMGX); off_r = vrep("데미지오프셋", V_DMGOFF)
    x_pos = op("operator_add", dx_r, off_r)
    dy_r = vrep("데미지표시y", V_DMGY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(x_pos), "Y": slot(dy_r)})
    bs[x_pos]["parent"] = g; bs[dy_r]["parent"] = g
    clr_gh = gen(); bs[clr_gh] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    show = gen(); bs[show] = mk("looks_show")
    ch_y = gen(); bs[ch_y] = mk("motion_changeyby", inputs={"DY": num(4)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(8)}, fields={"EFFECT": ["GHOST", None]})
    w_an = b_wait(bs, 0.02)
    chain([(ch_y, bs[ch_y]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(12), "SUBSTACK": [2, ch_y]})
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

    bg_md5    = save_svg(BG_SVG)
    mage_md5  = save_svg(MAGE_SVG)
    bolt_md5  = save_svg(BOLT_SVG)
    slime_md5 = save_svg(SLIME_SVG)
    bat_md5   = save_svg(BAT_SVG)
    golem_md5 = save_svg(GOLEM_SVG)
    ex_md5    = save_svg(EXPLOSION_SVG)
    gem_md5   = save_svg(GEM_SVG)
    card_md5  = save_svg(CARD_SVG)
    rs_md5    = save_svg(RESULT_SVG)
    digit_md5 = [save_svg(s) for s in DIGIT_SVGS]

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    mage_blocks     = build_mage_blocks()
    bolt_blocks     = build_bolt_blocks()
    enemy_blocks    = build_enemy_blocks()
    gem_blocks      = build_gem_blocks()
    card_blocks     = build_card_blocks()
    gameover_blocks = build_gameover_blocks()
    damage_blocks   = build_damage_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258, "md5ext": f"{pop_md5}.wav"
    }

    # ---- Stage: 전역 변수 52개 + 방송 7개 ----
    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 24
            V_ATK: ["마법공격력", 1], V_FIREGAP: ["발사간격", 0.6], V_BOLTSPD: ["마법탄속도", 8],
            V_PIERCE: ["관통", 1], V_MULTI: ["추가발사", 1], V_MOVE: ["이동속도", 4],
            V_MAXHP: ["최대체력", 5], V_HP: ["체력", 5], V_INV: ["무적시간", 25],
            V_MAGNET: ["흡수범위", 90], V_MAGSPD: ["흡수속도", 6], V_LVUP: ["레벨업경험치", 5],
            V_UP: ["강화량", 1], V_SPAWNGAP: ["스폰간격", 1.2], V_RAMP: ["난이도주기", 15],
            V_EHPW: ["약한적_체력", 1], V_ESPW: ["약한적_속도", 1.2], V_EXPW: ["약한적_경험치", 1],
            V_EHPM: ["중간적_체력", 3], V_ESPM: ["중간적_속도", 0.9], V_EXPM: ["중간적_경험치", 3],
            V_EHPS: ["강한적_체력", 6], V_ESPS: ["강한적_속도", 0.6], V_EXPS: ["강한적_경험치", 6],
            # 진행 28
            V_STATE: ["게임상태", 1], V_TIME: ["생존시간", 0], V_LEVEL: ["레벨", 1],
            V_EXP: ["경험치", 0], V_INVT: ["무적", 0], V_STAGE: ["단계", 0],
            V_SPAWNN: ["스폰카운트", 0], V_ALIVE: ["적수", 0], V_AIMD: ["조준거리", 99999],
            V_AIMX: ["조준X", 0], V_AIMY: ["조준Y", 0], V_AIMOK: ["조준있음", 0],
            V_FIREX: ["발사X", 0], V_FIREY: ["발사Y", 0], V_FIREI: ["발사i", 0],
            V_SPX: ["적생성X", 0], V_SPY: ["적생성Y", 0], V_SPTYPE: ["적생성종류", 1],
            V_GEMX: ["보석X", 0], V_GEMY: ["보석Y", 0], V_GEMV: ["보석값", 1],
            V_DMGVAL: ["데미지표시값", 0], V_DMGX: ["데미지표시x", 0], V_DMGY: ["데미지표시y", 0],
            V_DMGDIGIT: ["데미지숫자", 0], V_DMGOFF: ["데미지오프셋", 0],
            V_DMGLEN: ["데미지글자수", 0], V_DMGPOS: ["데미지자리", 0],
        },
        "lists": {}, "broadcasts": {
            BR_START: "게임시작", BR_AIM: "조준요청", BR_FIRE: "발사", BR_GEM: "보석생성",
            BR_LEVELUP: "레벨업", BR_UPDONE: "강화완료", BR_DMG: "데미지표시",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "아레나", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    mage = {
        "isStage": False, "name": "마법사",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": mage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "mage", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": mage_md5, "md5ext": f"{mage_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 36
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": True,
        "x": 0, "y": 0, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    bolt = {
        "isStage": False, "name": "마법탄",
        "variables": {V_BOLTISC: ["복제됨", 0], V_BOLTPIER: ["남은관통", 1],
                      V_BOLTHITCD: ["관통쿨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": bolt_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "bolt", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bolt_md5, "md5ext": f"{bolt_md5}.svg",
            "rotationCenterX": 22, "rotationCenterY": 22
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": False,
        "x": 0, "y": 0, "size": 45, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    enemy = {
        "isStage": False, "name": "적",
        "variables": {V_EISC: ["복제됨", 0], V_EHP: ["내체력", 1], V_ESPD: ["내속도", 1.2],
                      V_ETYPE: ["적종류", 1], V_EHIT: ["피격쿨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {"name": "슬라임", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": slime_md5, "md5ext": f"{slime_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "박쥐", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bat_md5, "md5ext": f"{bat_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "골렘", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": golem_md5, "md5ext": f"{golem_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "폭발", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ex_md5, "md5ext": f"{ex_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    gem = {
        "isStage": False, "name": "경험치보석",
        "variables": {V_GEMISC: ["복제됨", 0], V_GEMMINE: ["내경험치", 1]},
        "lists": {}, "broadcasts": {},
        "blocks": gem_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "gem", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": gem_md5, "md5ext": f"{gem_md5}.svg",
            "rotationCenterX": 24, "rotationCenterY": 24
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 55, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    card = {
        "isStage": False, "name": "강화카드",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": card_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "card", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": card_md5, "md5ext": f"{card_md5}.svg",
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

    # ---- 모니터: 생존시간 / 레벨 / 체력 / 경험치 / 레벨업경험치 (튜닝 변수는 숨김) ----
    monitors = [
        {"id": V_TIME, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "생존시간"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 999, "isDiscrete": True},
        {"id": V_LEVEL, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "레벨"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 50, "isDiscrete": True},
        {"id": V_HP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "체력"}, "spriteName": None,
         "value": 5, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 20, "isDiscrete": True},
        {"id": V_EXP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "경험치"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 50, "isDiscrete": True},
        {"id": V_LVUP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "레벨업경험치"}, "spriteName": None,
         "value": 5, "width": 0, "height": 0, "x": 5, "y": 125,
         "visible": True, "sliderMin": 0, "sliderMax": 50, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, mage, bolt, enemy, gem, card, gameover, damage],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "magic-survivor-builder"}
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
    for nm, b in [("stage", stage_blocks), ("mage", mage_blocks),
                  ("bolt", bolt_blocks), ("enemy", enemy_blocks),
                  ("gem", gem_blocks), ("card", card_blocks),
                  ("gameover", gameover_blocks), ("damage", damage_blocks)]:
        print(f"  {nm:9s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
