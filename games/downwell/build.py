#!/usr/bin/env python3
"""다운웰 (downwell) — 세로 우물 낙하 슈팅 로그라이트 (인디게임 Downwell 초등판).

건부츠 소년이 끝없는 우물로 떨어진다. 화면은 위로 흘러(=내려감) 아래에서 적·가시·
보석이 솟아오른다. 좌우로 피하고, 아래로 쏘면 잠깐 떠올라(체공) 위기를 넘기지만
탄약이 제한이라 함부로 못 쏜다 — 땅이나 적을 밟으면 탄약이 가득 찬다. 점프벌레는
밟아 죽이고, 박쥐·가시고슴도치는 반드시 쏴야 한다. 땅에 안 닿고 연속 처치하면 콤보
배수로 점수가 곱으로 불어난다. 깊이 내려갈수록 강화 택1로 강해지고, 체력 0이면
GAME OVER, 깃발 재클릭으로 능력치 기본값·우물 꼭대기부터. 점수 = 내려간 깊이.

베이스: games/magic-survivor/build.py (합성 사운드·플로팅 데미지 숫자·강화 택1·
        게임오버 배너·복제됨 가드·폭발 FX·노란 코멘트 가이드 투어)
      + games/rogue-knight/build.py (VY·중력·점프 물리 → 낙하속도로 통일).

★ 이 게임의 존재 이유는 "아이가 코드의 숫자·규칙을 직접 바꾸며 노는 것". 그래서
  모든 조절 가능한 값(32개)을 한글 전역 변수로만 노출하고, 코드 어디서도 매직넘버를
  쓰지 않는다. 튜닝 변수는 전부 Stage 깃발 클릭 한 스크립트에서 초기화한다.

★ 스크롤 모델: 소년은 카메라선에 y 고정(x만 좌우), 낙하속도(전역)만큼 적·보석·발판
  클론을 매 틱 change y by 낙하속도 로 위로 올려 '내려가는' 효과를 낸다. 낙하속도가
  음수면 월드가 내려가 소년이 우물에서 솟는다(점프·부양).
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "다운웰.sb3")

# ============================================================
#  효과음 합성 (전용 사운드, 결정적 생성)
# ============================================================
SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    """float 샘플(-1..1) 리스트 → 16-bit PCM mono WAV 바이트 (결정적)."""
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_zap(rate=SND_RATE):
    """아래 발사 — 짧은 하강 처프 '퓽' (레이저). magic-survivor synth_zap 재사용."""
    N = int(rate * 0.10); out = []
    for i in range(N):
        t = i / rate
        f = 250 + 900 * math.exp(-t * 16)
        env = math.exp(-t * 26)
        s = math.sin(2 * math.pi * f * t)
        s = (s + 0.3 * (1 if s > 0 else -1)) / 1.3
        out.append(s * env * 0.55)
    return out

def synth_boom(rate=SND_RATE):
    """적 처치 — 노이즈 버스트 + 저음 thump '펑' (폭발). magic-survivor 재사용."""
    N = int(rate * 0.30); out = []
    rng = random.Random(20240613)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 11)
        white = rng.random() * 2 - 1
        lp = lp + 0.45 * (white - lp)
        thump = math.sin(2 * math.pi * (60 + 40 * math.exp(-t * 20)) * t)
        s = (lp * 0.6 + thump * 0.7) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_stomp(rate=SND_RATE):
    """스톰프/착지(탄약충전) — 둔탁한 저음 thud + 짧은 상승 블립 '쿵! 통' (0.14s)."""
    N = int(rate * 0.14); out = []
    for i in range(N):
        t = i / rate
        thud = math.sin(2 * math.pi * (130 - 55 * (t / 0.14)) * t)
        env = math.exp(-t * 24)
        # 끝부분에 짧게 솟는 블립(통)
        blip = 0.0
        if t > 0.07:
            blip = math.sin(2 * math.pi * (340 + 700 * (t - 0.07)) * t) * math.exp(-((t - 0.10) ** 2) / 0.0007)
        s = thud * env * 0.75 + blip * 0.45
        out.append(max(-1, min(1, s)))
    return out

def synth_combo(rate=SND_RATE):
    """공중 연속 처치(콤보+1) — 맑은 사인 핑 (0.08s). pitch 는 재생 시 콤보로 변조."""
    N = int(rate * 0.08); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 30)
        s = math.sin(2 * math.pi * 660 * t) * env * 0.5
        out.append(s)
    return out

def synth_coin(rate=SND_RATE):
    """보석 획득 — 2음 코인 블립(상승 2단, 0.10s)."""
    N = int(rate * 0.10); out = []
    for i in range(N):
        t = i / rate
        f = 784 if t < 0.045 else 1175
        env = math.exp(-((t % 0.05)) * 16)
        s = math.sin(2 * math.pi * f * t) * env * 0.45
        out.append(s)
    return out

def synth_hurt(rate=SND_RATE):
    """소년 피격(체력-1) — 짧은 저음 buzz (0.16s, 각진 톤)."""
    N = int(rate * 0.16); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 9)
        s = math.sin(2 * math.pi * 95 * t)
        s = (1 if s > 0 else -1) * 0.42
        out.append(s * env)
    return out

def synth_levelup(rate=SND_RATE):
    """강화 선택 — 밝은 상승 아르페지오 C-E-G-C (0.25s)."""
    N = int(rate * 0.25); out = []
    notes = [523, 659, 784, 1047]
    step = 0.0625
    for i in range(N):
        t = i / rate
        idx = min(3, int(t / step))
        f = notes[idx]
        env = math.exp(-(t - idx * step) * 12)
        s = math.sin(2 * math.pi * f * t) * env * 0.45
        out.append(s)
    return out

# ============================================================
#  SVG assets (Downwell 풍 저채도 남보라 + 노랑 강조)
# ============================================================
def _star_pts(cx, cy, R, r, n, rot=0.0):
    pts = []
    for i in range(2 * n):
        rad = R if i % 2 == 0 else r
        ang = math.pi / n * i + rot
        pts.append(f"{cx + rad*math.cos(ang):.1f},{cy + rad*math.sin(ang):.1f}")
    return " ".join(pts)

# -------- 배경: 세로 우물 (좌우 바위벽 정적, 깊이 줄무늬) --------
def _bg_svg():
    stripes = []
    for sy in range(20, 360, 56):
        stripes.append(f'<rect x="90" y="{sy}" width="300" height="3" fill="#2a2150" opacity="0.6"/>')
    bricks = []
    rnd = random.Random(11)
    for side_x in (0, 390):
        for by in range(0, 360, 30):
            for bx in range(side_x, side_x + 90, 30):
                sh = rnd.choice(["#3a2d63", "#332858", "#2c2350"])
                ox = (by // 30 % 2) * 15
                bricks.append(f'<rect x="{bx - ox}" y="{by}" width="30" height="30" '
                              f'fill="{sh}" stroke="#1c1638" stroke-width="2"/>')
    STRIPES = "\n    ".join(stripes)
    BRICKS = "\n    ".join(bricks)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#191233"/>
  <g>
    {STRIPES}
  </g>
  <g>
    {BRICKS}
  </g>
  <rect x="86" y="0" width="6" height="360" fill="#FFD54F" opacity="0.5"/>
  <rect x="388" y="0" width="6" height="360" fill="#FFD54F" opacity="0.5"/>
</svg>"""
BG_SVG = _bg_svg()

# -------- 소년(건부츠): 정면 로봇 소년, 발 아래로 총구 (60x76) --------
BOY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="76" viewBox="0 0 60 76">
  <ellipse cx="30" cy="72" rx="14" ry="3" fill="#000000" opacity="0.25"/>
  <!-- 몸통(망토/슈트) -->
  <path d="M16 30 Q14 18 30 16 Q46 18 44 30 L42 50 L18 50 Z" fill="#5C4DB0" stroke="#3B2F8A" stroke-width="2"/>
  <!-- 머리 -->
  <circle cx="30" cy="16" r="11" fill="#FFE0B2" stroke="#E0A878" stroke-width="1.5"/>
  <path d="M19 14 Q30 2 41 14 Q41 8 30 6 Q19 8 19 14 Z" fill="#3B2F8A"/>
  <circle cx="26" cy="17" r="1.8" fill="#2A1A40"/>
  <circle cx="34" cy="17" r="1.8" fill="#2A1A40"/>
  <!-- 팔 -->
  <rect x="10" y="30" width="7" height="18" rx="3" fill="#5C4DB0" stroke="#3B2F8A" stroke-width="1.5"/>
  <rect x="43" y="30" width="7" height="18" rx="3" fill="#5C4DB0" stroke="#3B2F8A" stroke-width="1.5"/>
  <!-- 다리 + 건부츠(아래 총구) -->
  <rect x="20" y="50" width="9" height="14" rx="2" fill="#3B2F8A"/>
  <rect x="31" y="50" width="9" height="14" rx="2" fill="#3B2F8A"/>
  <rect x="18" y="62" width="13" height="8" rx="2" fill="#37474F" stroke="#1c1a20" stroke-width="1.5"/>
  <rect x="29" y="62" width="13" height="8" rx="2" fill="#37474F" stroke="#1c1a20" stroke-width="1.5"/>
  <circle cx="24" cy="70" r="2.4" fill="#FFD54F"/>
  <circle cx="36" cy="70" r="2.4" fill="#FFD54F"/>
</svg>"""

# -------- 총알: 아래로 쏘는 노란 플라즈마 탄 (40x40, 상하대칭) --------
BULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <ellipse cx="20" cy="20" rx="9" ry="15" fill="#FFB300" opacity="0.45"/>
  <ellipse cx="20" cy="20" rx="6" ry="12" fill="#FFD54F"/>
  <ellipse cx="20" cy="20" rx="3" ry="7" fill="#FFFDE7"/>
</svg>"""

# -------- 적: 점프벌레(약) / 박쥐(중) / 가시고슴도치(강) / 폭발 (모두 60x60) --------
JUMPBUG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="53" rx="16" ry="3" fill="#000000" opacity="0.2"/>
  <ellipse cx="30" cy="34" rx="20" ry="17" fill="#66BB6A" stroke="#2E7D32" stroke-width="2.5"/>
  <ellipse cx="30" cy="28" rx="15" ry="9" fill="#A5D6A7"/>
  <circle cx="23" cy="30" r="5" fill="#FFFFFF"/>
  <circle cx="37" cy="30" r="5" fill="#FFFFFF"/>
  <circle cx="23" cy="31" r="2.4" fill="#1B0F0A"/>
  <circle cx="37" cy="31" r="2.4" fill="#1B0F0A"/>
  <path d="M22 42 Q30 48 38 42" fill="none" stroke="#2E7D32" stroke-width="2.5"/>
</svg>"""

BAT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="53" rx="13" ry="3" fill="#000000" opacity="0.2"/>
  <path d="M30 30 Q10 16 4 32 Q14 30 18 38 Q20 30 30 34 Z" fill="#8E5FD6" stroke="#5E35B1" stroke-width="1.5"/>
  <path d="M30 30 Q50 16 56 32 Q46 30 42 38 Q40 30 30 34 Z" fill="#8E5FD6" stroke="#5E35B1" stroke-width="1.5"/>
  <ellipse cx="30" cy="32" rx="11" ry="13" fill="#B388E0" stroke="#5E35B1" stroke-width="2"/>
  <polygon points="22,20 25,30 19,29" fill="#B388E0"/>
  <polygon points="38,20 35,30 41,29" fill="#B388E0"/>
  <circle cx="26" cy="30" r="2.6" fill="#FFEB3B"/>
  <circle cx="34" cy="30" r="2.6" fill="#FFEB3B"/>
  <circle cx="26" cy="30" r="1" fill="#3E2723"/>
  <circle cx="34" cy="30" r="1" fill="#3E2723"/>
  <path d="M26 38 L28 41 L30 38 L32 41 L34 38" fill="none" stroke="#FFFFFF" stroke-width="1.4"/>
</svg>"""

SPIKE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="53" rx="16" ry="3" fill="#000000" opacity="0.2"/>
  <!-- 위로 솟은 가시(위험 신호) -->
  <polygon points="14,28 18,8 22,28" fill="#C62828"/>
  <polygon points="22,26 26,4 30,26" fill="#E53935"/>
  <polygon points="30,26 34,4 38,26" fill="#E53935"/>
  <polygon points="38,28 42,8 46,28" fill="#C62828"/>
  <ellipse cx="30" cy="38" rx="19" ry="14" fill="#EF5350" stroke="#B71C1C" stroke-width="2.5"/>
  <circle cx="23" cy="38" r="4" fill="#FFFFFF"/>
  <circle cx="37" cy="38" r="4" fill="#FFFFFF"/>
  <circle cx="23" cy="39" r="2" fill="#3E0A0A"/>
  <circle cx="37" cy="39" r="2" fill="#3E0A0A"/>
  <path d="M24 46 L27 43 L30 46 L33 43 L36 46" fill="none" stroke="#B71C1C" stroke-width="2"/>
</svg>"""

EXPLOSION_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30, 30, 29, 12, 12)}" fill="#FF6F00" stroke="#E65100" stroke-width="1"/>
  <polygon points="{_star_pts(30, 30, 21, 8, 12, rot=0.262)}" fill="#FFB300"/>
  <circle cx="30" cy="30" r="12" fill="#FFEB3B"/>
  <circle cx="30" cy="30" r="5"  fill="#FFFFFF"/>
</svg>"""

# -------- 보석/코인: 노란 보석 (44x44) --------
GEM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">
  <polygon points="22,4 38,16 22,40 6,16" fill="#FFCA28" stroke="#F57F17" stroke-width="2"/>
  <polygon points="22,4 38,16 22,16" fill="#FFE082"/>
  <polygon points="22,4 6,16 22,16" fill="#FFF59D"/>
  <polygon points="22,16 38,16 22,40" fill="#FFB300"/>
  <polygon points="22,16 6,16 22,40" fill="#FFA000"/>
  <circle cx="16" cy="11" r="2" fill="#FFFFFF" opacity="0.85"/>
</svg>"""

# -------- 발판(ledge): 돌 발판 (96x18) --------
LEDGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="96" height="18" viewBox="0 0 96 18">
  <rect x="1" y="2" width="94" height="14" rx="4" fill="#6D5BB0" stroke="#3B2F8A" stroke-width="2"/>
  <rect x="6" y="4" width="84" height="4" rx="2" fill="#9C8AD6" opacity="0.7"/>
  <rect x="14" y="10" width="10" height="4" fill="#4B3F95"/>
  <rect x="44" y="10" width="10" height="4" fill="#4B3F95"/>
  <rect x="72" y="10" width="10" height="4" fill="#4B3F95"/>
</svg>"""

# -------- 강화카드: 4선택지 (탄약+/연사+/부양력+/이동+) --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="170" viewBox="0 0 400 170">
  <rect x="4" y="4" width="392" height="162" rx="14" fill="#1A1240" opacity="0.96" stroke="#FFD54F" stroke-width="4"/>
  <text x="200" y="34" text-anchor="middle" fill="#FFD54F" font-family="Arial, sans-serif" font-size="22" font-weight="bold">깊어졌다! 강화 선택</text>
  <rect x="12" y="50" width="88" height="100" rx="10" fill="#C62828" stroke="#FFFFFF" stroke-width="2"/>
  <text x="56" y="92" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="32" font-weight="bold">1</text>
  <text x="56" y="124" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="14">탄약+</text>
  <rect x="108" y="50" width="88" height="100" rx="10" fill="#2E7D32" stroke="#FFFFFF" stroke-width="2"/>
  <text x="152" y="92" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="32" font-weight="bold">2</text>
  <text x="152" y="124" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="14">연사+</text>
  <rect x="204" y="50" width="88" height="100" rx="10" fill="#1565C0" stroke="#FFFFFF" stroke-width="2"/>
  <text x="248" y="92" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="32" font-weight="bold">3</text>
  <text x="248" y="124" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="14">부양력+</text>
  <rect x="300" y="50" width="88" height="100" rx="10" fill="#6A1B9A" stroke="#FFFFFF" stroke-width="2"/>
  <text x="344" y="92" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="32" font-weight="bold">4</text>
  <text x="344" y="124" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="14">이동+</text>
</svg>"""

# -------- 게임오버 배너 --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="68" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="20">깊이(점수)는 왼쪽 위에서 확인!</text>
  <text x="180" y="136" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# 데미지 팝업 숫자 코스튬 0~9 (말풍선 say 미사용)
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

# ----- Scratch 블록 코멘트(노란 메모) — 에디터 가이드 투어 -----
_cmt_ic = [0]
def add_comment(bs, comments, block_id, text, x=520, y=40, w=280, h=150):
    _cmt_ic[0] += 1
    cid = f"cmt{_cmt_ic[0]:03d}"
    comments[cid] = {"blockId": block_id, "x": x, "y": y, "width": w, "height": h,
                     "minimized": False, "text": text}
    if block_id in bs:
        bs[block_id]["comment"] = cid
    return cid

# ============================================================
#  IDs
# ============================================================
# ----- 5.1 튜닝 32 (개조 손잡이) -----
# 소년·물리 9
V_MOVE     = "varMove01"        # 이동속도      5
V_GRAV     = "varGrav02"        # 중력          0.55
V_FALLMAX  = "varFallMax03"     # 최대낙하      9
V_JUMP     = "varJump04"        # 점프력        7
V_FLOAT    = "varFloat05"       # 부양력        1.6
V_FLOATCAP = "varFloatCap06"    # 부양상한      5
V_CAMY     = "varCamY07"        # 카메라선      40
V_COYOTE   = "varCoyote08"      # 코요테        6
V_BOUNCE   = "varBounce09"      # 착지반동      1.5
# 건부츠 4
V_AMMOMAX  = "varAmmoMax10"     # 탄약최대      6
V_FIREGAP  = "varFireGap11"     # 연사간격      0.12
V_BULSPD   = "varBulSpd12"      # 총알속도      14
V_BULATK   = "varBulAtk13"      # 총알공격력    1
# 체력·점수 3
V_MAXHP    = "varMaxHP14"       # 최대체력      4
V_INV      = "varInv15"         # 무적시간      30
V_KILLPT   = "varKillPt16"      # 처치점수      5
# 적 종류별 9
V_E1HP     = "varE1HP17"        # 점프벌레_체력  1
V_E1SPD    = "varE1Spd18"       # 점프벌레_속도  0.8
V_E1GEM    = "varE1Gem19"       # 점프벌레_보석  1
V_E2HP     = "varE2HP20"        # 박쥐_체력      2
V_E2SPD    = "varE2Spd21"       # 박쥐_속도      1.6
V_E2GEM    = "varE2Gem22"       # 박쥐_보석      2
V_E3HP     = "varE3HP23"        # 가시_체력      3
V_E3SPD    = "varE3Spd24"       # 가시_속도      0.4
V_E3GEM    = "varE3Gem25"       # 가시_보석      3
# 스폰·난이도·진행 7
V_SPAWNGAP = "varSpawnGap26"    # 스폰간격      1.0
V_RAMPDEP  = "varRampDepth27"   # 난이도깊이    900
V_SPDOWN   = "varSpawnDown28"   # 스폰감소      0.07
V_SPMIN    = "varSpawnMin29"    # 스폰간격최소  0.35
V_LEDGEGAP = "varLedgeGap30"    # 발판간격      1.6
V_UPDEPTH  = "varUpDepth31"     # 강화깊이      1000
V_UP       = "varUp32"          # 강화량        1

# ----- 5.2 진행/내부 상태 28 -----
V_STATE    = "varState33"       # 게임상태  1=낙하중,2=강화선택중,0=게임오버
V_DEPTH    = "varDepth34"       # 깊이(점수)
V_COMBO    = "varCombo35"       # 콤보
V_COMBOMAX = "varComboMax36"    # 콤보최고
V_AMMO     = "varAmmo37"        # 탄약
V_HP       = "varHP38"          # 체력
V_INVT     = "varInvT39"        # 무적(틱)
V_FALL     = "varFall40"        # 낙하속도
V_COYOTET  = "varCoyoteT41"     # 접지여유
V_STAGE    = "varStage42"       # 단계
V_SPAWNN   = "varSpawnN43"      # 스폰카운트
V_ALIVE    = "varAlive44"       # 적수
V_NEXTUP   = "varNextUp45"      # 다음강화깊이
V_EFFGAP   = "varEffGap46"      # 유효스폰간격
V_FIRECD   = "varFireCD47"      # 발사쿨
V_FIREX    = "varFireX48"       # 발사X
V_SPX      = "varSPX49"         # 적생성X
V_SPTYPE   = "varSPType50"      # 적생성종류
V_GEMX     = "varGemX51"        # 보석X
V_GEMY     = "varGemY52"        # 보석Y
V_GEMV     = "varGemV53"        # 보석값
V_DMGVAL   = "varDmgVal54"      # 데미지표시값
V_DMGX     = "varDmgX55"        # 데미지표시x
V_DMGY     = "varDmgY56"        # 데미지표시y
V_DMGDIGIT = "varDmgDigit57"    # 데미지숫자
V_DMGOFF   = "varDmgOff58"      # 데미지오프셋
V_DMGLEN   = "varDmgLen59"      # 데미지글자수
V_DMGPOS   = "varDmgPos60"      # 데미지자리

# ----- 5.3 클론-로컬 변수 12 -----
V_BULISC   = "varBulIsClone"    # 총알: 복제됨
V_EISC     = "varEnemyIsClone"  # 적: 복제됨
V_EHP      = "varEnemyHP"       # 적: 내체력
V_ESPD     = "varEnemySpd"      # 적: 내속도
V_ETYPE    = "varEnemyType"     # 적: 적종류
V_ESTOMP   = "varEnemyStomp"    # 적: 스톰프가능
V_EHIT     = "varEnemyHit"      # 적: 피격쿨
V_EPHASE   = "varEnemyPhase"    # 적: 흔들위상
V_GEMISC   = "varGemIsClone"    # 보석: 복제됨
V_GEMMINE  = "varGemMine"       # 보석: 내값
V_LEDGEISC = "varLedgeIsClone"  # 발판: 복제됨
V_DMGISC   = "varDmgIsClone"    # 데미지: 복제됨

# ----- 5.4 메시지 6 -----
BR_START   = "brStart01"        # 게임시작
BR_FIRE    = "brFire02"         # 발사
BR_GEM     = "brGem03"          # 보석생성
BR_UP      = "brUp04"           # 강화
BR_UPDONE  = "brUpDone05"       # 강화완료
BR_DMG     = "brDmg06"          # 데미지표시

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

def b_play(bs, pitch, sound):
    """[set pitch effect → start sound] 두 블록을 리스트로 반환(둘 다 시퀀스에 넣을 것)."""
    pe = gen(); bs[pe] = mk("sound_seteffectto",
        inputs={"VALUE": num(pitch)}, fields={"EFFECT": ["PITCH", None]})
    sm = gen(); bs[sm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]})
    bs[sm]["parent"] = sp
    return [pe, sp]

def b_play_var(bs, pitch_block, sound):
    """pitch 가 리포터(블록 id)인 start sound."""
    pe = gen(); bs[pe] = mk("sound_seteffectto",
        inputs={"VALUE": slot(pitch_block)}, fields={"EFFECT": ["PITCH", None]})
    bs[pitch_block]["parent"] = pe
    sm = gen(); bs[sm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]})
    bs[sm]["parent"] = sp
    return [pe, sp]

def b_broadcast(bs, name, brid):
    m = gen(); bs[m] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcast", inputs={"BROADCAST_INPUT": [1, m]})
    bs[m]["parent"] = b
    return b

def _seq(bs, ids):
    """리스트 ids 를 차례로 연결하고 head id 반환."""
    chain([(i, bs[i]) for i in ids])
    return ids[0]

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 → 변수 60개 전부 초기화 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [h]
    def add_set(name, vid, val):
        seq.append(b_setvar(bs, name, vid, val))

    # ── 튜닝 32 (개조 손잡이) ──
    add_set("이동속도", V_MOVE, 5)
    add_set("중력", V_GRAV, 0.55)
    add_set("최대낙하", V_FALLMAX, 9)
    add_set("점프력", V_JUMP, 7)
    add_set("부양력", V_FLOAT, 1.6)
    add_set("부양상한", V_FLOATCAP, 5)
    add_set("카메라선", V_CAMY, 40)
    add_set("코요테", V_COYOTE, 6)
    add_set("착지반동", V_BOUNCE, 1.5)
    add_set("탄약최대", V_AMMOMAX, 6)
    add_set("연사간격", V_FIREGAP, 0.12)
    add_set("총알속도", V_BULSPD, 14)
    add_set("총알공격력", V_BULATK, 1)
    add_set("최대체력", V_MAXHP, 4)
    add_set("무적시간", V_INV, 30)
    add_set("처치점수", V_KILLPT, 5)
    add_set("점프벌레_체력", V_E1HP, 1)
    add_set("점프벌레_속도", V_E1SPD, 0.8)
    add_set("점프벌레_보석", V_E1GEM, 1)
    add_set("박쥐_체력", V_E2HP, 2)
    add_set("박쥐_속도", V_E2SPD, 1.6)
    add_set("박쥐_보석", V_E2GEM, 2)
    add_set("가시_체력", V_E3HP, 3)
    add_set("가시_속도", V_E3SPD, 0.4)
    add_set("가시_보석", V_E3GEM, 3)
    add_set("스폰간격", V_SPAWNGAP, 1.0)
    add_set("난이도깊이", V_RAMPDEP, 900)
    add_set("스폰감소", V_SPDOWN, 0.07)
    add_set("스폰간격최소", V_SPMIN, 0.35)
    add_set("발판간격", V_LEDGEGAP, 1.6)
    add_set("강화깊이", V_UPDEPTH, 1000)
    add_set("강화량", V_UP, 1)

    # ── 진행 상태 28 ──
    add_set("게임상태", V_STATE, 1)
    add_set("깊이", V_DEPTH, 0)
    add_set("콤보", V_COMBO, 0)
    add_set("콤보최고", V_COMBOMAX, 0)
    # 체력 = 최대체력, 탄약 = 탄약최대 (튜닝 변수 참조)
    seq.append(b_setvar(bs, "체력", V_HP, vrep("최대체력", V_MAXHP)))
    seq.append(b_setvar(bs, "탄약", V_AMMO, vrep("탄약최대", V_AMMOMAX)))
    add_set("무적", V_INVT, 0)
    add_set("낙하속도", V_FALL, 0)
    add_set("접지여유", V_COYOTET, 0)
    add_set("단계", V_STAGE, 0)
    add_set("스폰카운트", V_SPAWNN, 0)
    add_set("적수", V_ALIVE, 0)
    # 다음강화깊이 = 강화깊이
    seq.append(b_setvar(bs, "다음강화깊이", V_NEXTUP, vrep("강화깊이", V_UPDEPTH)))
    # 유효스폰간격 = 스폰간격
    seq.append(b_setvar(bs, "유효스폰간격", V_EFFGAP, vrep("스폰간격", V_SPAWNGAP)))
    add_set("발사쿨", V_FIRECD, 0)
    add_set("발사X", V_FIREX, 0)
    add_set("적생성X", V_SPX, 0)
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

    seq.append(b_wait(bs, 0.3))
    seq.append(b_broadcast(bs, "게임시작", BR_START))
    _seq(bs, seq)

    # ===== (B) 단계/유효스폰간격 계산 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=340, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # 단계 = floor(깊이 / 난이도깊이)
    depth_r = vrep("깊이", V_DEPTH); ramp_r = vrep("난이도깊이", V_RAMPDEP)
    div_dr = op("operator_divide", depth_r, ramp_r)
    floor_dr = gen(); bs[floor_dr] = mk("operator_mathop",
        inputs={"NUM": slot(div_dr)}, fields={"OPERATOR": ["floor", None]})
    bs[div_dr]["parent"] = floor_dr
    set_stage = b_setvar(bs, "단계", V_STAGE, floor_dr)
    # 유효스폰간격 = 스폰간격 - 단계*스폰감소
    stage_r = vrep("단계", V_STAGE); spdown_r = vrep("스폰감소", V_SPDOWN)
    mul_g = op("operator_multiply", stage_r, spdown_r)
    gapbase_r = vrep("스폰간격", V_SPAWNGAP)
    sub_g = op("operator_subtract", gapbase_r, mul_g)
    set_eff = b_setvar(bs, "유효스폰간격", V_EFFGAP, sub_g)
    # if 유효스폰간격 < 스폰간격최소 : 유효스폰간격 = 스폰간격최소
    eff_r = vrep("유효스폰간격", V_EFFGAP); spmin_r = vrep("스폰간격최소", V_SPMIN)
    cond_min = cmp_op("operator_lt", eff_r, spmin_r)
    set_eff_min = b_setvar(bs, "유효스폰간격", V_EFFGAP, vrep("스폰간격최소", V_SPMIN))
    if_min = b_if(bs, cond_min, set_eff_min)
    inner_b = _seq(bs, [set_stage, set_eff, if_min])
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    if_play_b = b_if(bs, cond_play_b, inner_b)
    wb = b_wait(bs, 0.1)
    fe_b = b_forever(bs, _seq(bs, [if_play_b, wb]))
    _seq(bs, [hb, fe_b])

    # ===== (C) 무적 타이머 감소 forever =====
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=560)
    invt_r = vrep("무적", V_INVT)
    cond_inv = cmp_op("operator_gt", invt_r, 0)
    dec_inv = b_changevar(bs, "무적", V_INVT, -1)
    if_inv = b_if(bs, cond_inv, dec_inv)
    wc = b_wait(bs, 0.025)
    fe_c = b_forever(bs, _seq(bs, [if_inv, wc]))
    _seq(bs, [hc, fe_c])

    # ===== (D) 강화 / 게임오버 감시 forever =====
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=340, y=560)
    state_ready = vrep("게임상태", V_STATE)
    cond_ready = cmp_op("operator_equals", state_ready, 1)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, cond_ready]})
    bs[cond_ready]["parent"] = wu
    # if (깊이 >= 다음강화깊이) and (게임상태=1) → 게임상태=2 ; broadcast 강화
    depth_d = vrep("깊이", V_DEPTH); nextup_d = vrep("다음강화깊이", V_NEXTUP)
    cond_dlt = cmp_op("operator_lt", depth_d, nextup_d)
    not_dlt = gen(); bs[not_dlt] = mk("operator_not", inputs={"OPERAND": [2, cond_dlt]})
    bs[cond_dlt]["parent"] = not_dlt
    state_d1 = vrep("게임상태", V_STATE)
    cond_pl_d1 = cmp_op("operator_equals", state_d1, 1)
    cond_up = bool_op("operator_and", not_dlt, cond_pl_d1)
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_up = b_broadcast(bs, "강화", BR_UP)
    if_up = b_if(bs, cond_up, _seq(bs, [set_st2, bc_up]))
    # if (체력 < 1) and (게임상태=1) → 게임상태=0
    hp_r = vrep("체력", V_HP)
    cond_dead = cmp_op("operator_lt", hp_r, 1)
    state_d2 = vrep("게임상태", V_STATE)
    cond_pl_d2 = cmp_op("operator_equals", state_d2, 1)
    cond_over = bool_op("operator_and", cond_dead, cond_pl_d2)
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    if_over = b_if(bs, cond_over, set_st0)
    wd = b_wait(bs, 0.05)
    fe_d = b_forever(bs, _seq(bs, [if_up, if_over, wd]))
    _seq(bs, [hd, wu, fe_d])

    # ── 가이드 투어 코멘트 ──
    add_comment(bs, comments, h,
        "⚙️ 개조 손잡이 (여기가 핵심!)\n"
        "이 초록 깃발 묶음에 게임의 모든 숫자가 한글 변수로 모여 있어요. "
        "여기 숫자 하나만 바꾸면(예: 중력 0.55→0.2) 게임이 확 달라져요. "
        "바꾸기 전에 '이렇게 될 것 같다'를 먼저 예상해 보고 ▶ 를 눌러 확인해 보세요!",
        x=-380, y=-280, w=330, h=180)
    add_comment(bs, comments, hb,
        "⛏️ 깊이 = 단계 시계\n"
        "단계 = 깊이 ÷ 난이도깊이. 깊이 내려갈수록 단계가 올라 더 센 적이 섞이고, "
        "유효스폰간격 = 스폰간격 − 단계×스폰감소 로 적이 더 자주 쏟아져요(스폰간격최소 하한).",
        x=620, y=-40, w=310, h=160)
    add_comment(bs, comments, wu,
        "🃏 강화 / 💀 게임오버 감시\n"
        "깊이가 다음강화깊이를 넘으면 게임상태=2 로 강화카드를 띄우고, "
        "체력이 0이 되면 게임상태=0 으로 GAME OVER 가 돼요.",
        x=620, y=520, w=310, h=150)

    return bs, comments

# ============================================================
#  소년 (BOY: 카메라 + 물리 + 사격 + 착지/피격)
# ============================================================
def build_boy_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 초기화 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(65)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(90)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    setx0 = gen(); bs[setx0] = mk("motion_setx", inputs={"X": num(0)})
    sety_cam = gen(); bs[sety_cam] = mk("motion_sety", inputs={"Y": slot(vrep("카메라선", V_CAMY))})
    bs[bs[sety_cam]["inputs"]["Y"][1]]["parent"] = sety_cam
    clr = gen(); bs[clr] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    _seq(bs, [h, show, sz, rs, pd, front, setx0, sety_cam, clr])

    # ===== (B) 메인 물리 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    inner = []
    # 접지여유 -1 (>0일 때)
    coy_r = vrep("접지여유", V_COYOTET)
    cond_coy = cmp_op("operator_gt", coy_r, 0)
    dec_coy = b_changevar(bs, "접지여유", V_COYOTET, -1)
    inner.append(b_if(bs, cond_coy, dec_coy))
    # 좌우 이동
    move_r = vrep("이동속도", V_MOVE)
    cx_r = gen(); bs[cx_r] = mk("motion_changexby", inputs={"DX": slot(move_r)})
    bs[move_r]["parent"] = cx_r
    inner.append(b_if(bs, b_keypressed(bs, "right arrow"), cx_r))
    move_l = vrep("이동속도", V_MOVE)
    neg_move = op("operator_subtract", 0, move_l)
    cx_l = gen(); bs[cx_l] = mk("motion_changexby", inputs={"DX": slot(neg_move)})
    bs[neg_move]["parent"] = cx_l
    inner.append(b_if(bs, b_keypressed(bs, "left arrow"), cx_l))
    # clamp x ±150
    xp1 = gen(); bs[xp1] = mk("motion_xposition")
    cond_xr = cmp_op("operator_gt", xp1, 150)
    setxr = gen(); bs[setxr] = mk("motion_setx", inputs={"X": num(150)})
    inner.append(b_if(bs, cond_xr, setxr))
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    cond_xl = cmp_op("operator_lt", xp2, -150)
    setxl = gen(); bs[setxl] = mk("motion_setx", inputs={"X": num(-150)})
    inner.append(b_if(bs, cond_xl, setxl))
    # set y to 카메라선 (카메라 고정)
    sety = gen(); bs[sety] = mk("motion_sety", inputs={"Y": slot(vrep("카메라선", V_CAMY))})
    bs[bs[sety]["inputs"]["Y"][1]]["parent"] = sety
    inner.append(sety)
    # 점프: (key space or key up) and 접지여유>0 → 낙하속도 = -점프력 ; 접지여유 = 0
    k_sp = b_keypressed(bs, "space"); k_up = b_keypressed(bs, "up arrow")
    jump_key = bool_op("operator_or", k_sp, k_up)
    coy_r2 = vrep("접지여유", V_COYOTET)
    cond_coy2 = cmp_op("operator_gt", coy_r2, 0)
    cond_jump = bool_op("operator_and", jump_key, cond_coy2)
    neg_jump = op("operator_subtract", 0, vrep("점프력", V_JUMP))
    set_fall_jump = b_setvar(bs, "낙하속도", V_FALL, neg_jump)
    set_coy0 = b_setvar(bs, "접지여유", V_COYOTET, 0)
    inner.append(b_if(bs, cond_jump, _seq(bs, [set_fall_jump, set_coy0])))
    # 중력: change 낙하속도 by 중력
    inner.append(b_changevar(bs, "낙하속도", V_FALL, vrep("중력", V_GRAV)))
    # if 낙하속도 > 최대낙하 : set 낙하속도 = 최대낙하
    fall_r = vrep("낙하속도", V_FALL); fmax_r = vrep("최대낙하", V_FALLMAX)
    cond_fmax = cmp_op("operator_gt", fall_r, fmax_r)
    set_fall_max = b_setvar(bs, "낙하속도", V_FALL, vrep("최대낙하", V_FALLMAX))
    inner.append(b_if(bs, cond_fmax, set_fall_max))
    # if 낙하속도 > 0 : change 깊이 by 낙하속도
    fall_r2 = vrep("낙하속도", V_FALL)
    cond_fpos = cmp_op("operator_gt", fall_r2, 0)
    inc_depth = b_changevar(bs, "깊이", V_DEPTH, vrep("낙하속도", V_FALL))
    inner.append(b_if(bs, cond_fpos, inc_depth))
    # 발판 착지: if (touching 발판) and (낙하속도>0) → 낙하속도=0; 탄약=탄약최대; 접지여유=코요테; 콤보=0; play stomp
    tc_ledge = b_touching(bs, "발판")
    fall_r3 = vrep("낙하속도", V_FALL)
    cond_fpos2 = cmp_op("operator_gt", fall_r3, 0)
    cond_land = bool_op("operator_and", tc_ledge, cond_fpos2)
    set_fall0 = b_setvar(bs, "낙하속도", V_FALL, 0)
    set_ammo_full = b_setvar(bs, "탄약", V_AMMO, vrep("탄약최대", V_AMMOMAX))
    set_coy_full = b_setvar(bs, "접지여유", V_COYOTET, vrep("코요테", V_COYOTE))
    set_combo0 = b_setvar(bs, "콤보", V_COMBO, 0)
    play_land = b_play(bs, 0, "stomp")
    inner.append(b_if(bs, cond_land, _seq(bs, [set_fall0, set_ammo_full, set_coy_full, set_combo0] + play_land)))
    # 피격: if (touching 적) and (무적=0) → 체력-1; 무적=무적시간; play hurt
    tc_enemy = b_touching(bs, "적")
    invt_r = vrep("무적", V_INVT)
    cond_noinv = cmp_op("operator_equals", invt_r, 0)
    cond_hurt = bool_op("operator_and", tc_enemy, cond_noinv)
    dec_hp = b_changevar(bs, "체력", V_HP, -1)
    set_invt = b_setvar(bs, "무적", V_INVT, vrep("무적시간", V_INV))
    play_hurt = b_play(bs, 0, "hurt")
    inner.append(b_if(bs, cond_hurt, _seq(bs, [dec_hp, set_invt] + play_hurt)))

    inner_head = _seq(bs, inner)
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    if_play_b = b_if(bs, cond_play_b, inner_head)
    wb = b_wait(bs, 0.025)
    fe_b = b_forever(bs, _seq(bs, [if_play_b, wb]))
    _seq(bs, [hb, fe_b])

    # ===== (D) 아래로 발사 forever =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=360, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # if (key down or key z) and 탄약>0 and 발사쿨=0
    k_dn = b_keypressed(bs, "down arrow"); k_z = b_keypressed(bs, "z")
    fire_key = bool_op("operator_or", k_dn, k_z)
    ammo_r = vrep("탄약", V_AMMO)
    cond_ammo = cmp_op("operator_gt", ammo_r, 0)
    # 발사쿨 게이트는 not(발사쿨>0). (발사쿨=0 등호 비교는 0.01 감소의 부동소수 잔차로
    # 정확히 0 에 안 닿아 발사가 1번만 되는 함정이 있음 — 등호 대신 부등호로 회피)
    firecd_r = vrep("발사쿨", V_FIRECD)
    cond_cd_pos = cmp_op("operator_gt", firecd_r, 0)
    cond_cd0 = gen(); bs[cond_cd0] = mk("operator_not", inputs={"OPERAND": [2, cond_cd_pos]})
    bs[cond_cd_pos]["parent"] = cond_cd0
    cond_fk = bool_op("operator_and", fire_key, cond_ammo)
    cond_fire = bool_op("operator_and", cond_fk, cond_cd0)
    # 발사X = x position ; broadcast 발사 ; 탄약-1
    xp_f = gen(); bs[xp_f] = mk("motion_xposition")
    set_firex = b_setvar(bs, "발사X", V_FIREX, xp_f)
    bc_fire = b_broadcast(bs, "발사", BR_FIRE)
    dec_ammo = b_changevar(bs, "탄약", V_AMMO, -1)
    # 낙하속도 += (0-부양력) ; if 낙하속도 < (0-부양상한) set 낙하속도 = (0-부양상한)
    neg_float = op("operator_subtract", 0, vrep("부양력", V_FLOAT))
    ch_fall = b_changevar(bs, "낙하속도", V_FALL, neg_float)
    fall_rf = vrep("낙하속도", V_FALL)
    neg_cap = op("operator_subtract", 0, vrep("부양상한", V_FLOATCAP))
    cond_under = cmp_op("operator_lt", fall_rf, neg_cap)
    neg_cap2 = op("operator_subtract", 0, vrep("부양상한", V_FLOATCAP))
    set_fall_cap = b_setvar(bs, "낙하속도", V_FALL, neg_cap2)
    if_cap = b_if(bs, cond_under, set_fall_cap)
    # 발사쿨 = 연사간격 ; play zap
    set_firecd = b_setvar(bs, "발사쿨", V_FIRECD, vrep("연사간격", V_FIREGAP))
    play_zap = b_play(bs, 0, "zap")
    fire_body = _seq(bs, [set_firex, bc_fire, dec_ammo, ch_fall, if_cap, set_firecd] + play_zap)
    if_fire = b_if(bs, cond_fire, fire_body)
    state_c = vrep("게임상태", V_STATE)
    cond_play_c = cmp_op("operator_equals", state_c, 1)
    if_play_c = b_if(bs, cond_play_c, if_fire)
    wc = b_wait(bs, 0.01)
    fe_c = b_forever(bs, _seq(bs, [if_play_c, wc]))
    _seq(bs, [hc, fe_c])

    # ===== (E) 발사쿨 시간 감소 forever =====
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=360, y=520,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    firecd_r2 = vrep("발사쿨", V_FIRECD)
    cond_cd_pos = cmp_op("operator_gt", firecd_r2, 0)
    dec_cd = b_changevar(bs, "발사쿨", V_FIRECD, -0.01)
    if_cd = b_if(bs, cond_cd_pos, dec_cd)
    wd = b_wait(bs, 0.01)
    fe_d = b_forever(bs, _seq(bs, [if_cd, wd]))
    _seq(bs, [hd, fe_d])

    add_comment(bs, comments, hb,
        "🪂 낙하·중력·카메라 (이 게임의 심장)\n"
        "소년은 매 틱 'set y to 카메라선' 으로 화면에 y 고정(x만 좌우)! 떨어지는 건 소년이 아니라 "
        "월드예요 — 낙하속도가 중력으로 커지고, 적·보석·발판이 그만큼 위로 흘러요. "
        "낙하속도>0 일 때만 깊이(점수)가 쌓여요.",
        x=560, y=-60, w=330, h=190)
    add_comment(bs, comments, hc,
        "🔫 건부츠는 아래로 쏜다 + 탄약\n"
        "↓ 또는 z 로 발사! 쏠 때마다 탄약−1 이고 낙하속도−부양력 만큼 떠올라요(반동/체공). "
        "탄약이 0이면 못 쏘고 못 떠요 — 땅·적을 밟아야 탄약이 가득 차요(아래 착지).",
        x=620, y=200, w=320, h=170)
    add_comment(bs, comments, inner[-2] if len(inner) >= 2 else hb,
        "🦵 스톰프/착지 = 탄약 충전\n"
        "발판에 위에서 닿으면(낙하속도>0) 낙하속도=0, 탄약=탄약최대, 콤보=0(리셋)! "
        "적 밟기(스톰프)는 적 쪽에서 처리해 콤보를 '유지'해요 — 땅에 닿을 때만 콤보가 끊겨요.",
        x=560, y=420, w=320, h=160)

    return bs, comments

# ============================================================
#  총알 (BULLET: 스포너 + 아래로 직진 클론)
# ============================================================
def build_bullet_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(45)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(180)})
    orig0 = b_setvar(bs, "복제됨", V_BULISC, 0)
    _seq(bs, [h, hi, sz, rs, pd, orig0])

    # (B) 발사 → 탄 클론 1개 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    isc_chk = vrep("복제됨", V_BULISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    _seq(bs, [hb, if_spawn])

    # (C) 클론 본체 — 아래로 직진, 적 닿으면 사라짐
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=420)
    set_isc1 = b_setvar(bs, "복제됨", V_BULISC, 1)
    # go to (발사X, 카메라선)
    fx_r = vrep("발사X", V_FIREX); camy_r = vrep("카메라선", V_CAMY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(fx_r), "Y": slot(camy_r)})
    bs[fx_r]["parent"] = g; bs[camy_r]["parent"] = g
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    # repeat until (y<-185 or 게임상태=0) { change y by (0-총알속도); if touching 적 {wait 0.06; delete}; wait 0.01 }
    neg_spd = op("operator_subtract", 0, vrep("총알속도", V_BULSPD))
    ch_y = gen(); bs[ch_y] = mk("motion_changeyby", inputs={"DY": slot(neg_spd)})
    bs[neg_spd]["parent"] = ch_y
    tc_e = b_touching(bs, "적")
    w_linger = b_wait(bs, 0.06)
    del_hit = gen(); bs[del_hit] = mk("control_delete_this_clone")
    if_hit = b_if(bs, tc_e, _seq(bs, [w_linger, del_hit]))
    w_mv = b_wait(bs, 0.01)
    body_head = _seq(bs, [ch_y, if_hit, w_mv])
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_low = cmp_op("operator_lt", yp, -185)
    state_b = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_b, 0)
    cond_stop = bool_op("operator_or", cond_low, cond_over)
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, cond_stop], "SUBSTACK": [2, body_head]})
    bs[cond_stop]["parent"] = ru; bs[body_head]["parent"] = ru
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    _seq(bs, [ch, set_isc1, g, front, show, ru, del_end])

    add_comment(bs, comments, ch,
        "💥 아래로 직진하는 탄 (데미지 판정 분리)\n"
        "탄은 발사X 자리에서 아래로 총알속도만큼 직진해요(스크롤보다 빨라야!). "
        "적에 닿으면 '나는 사라짐'만 하고, 체력 깎기는 적이 'touching 총알'로 직접 처리해요.",
        x=300, y=-40, w=320, h=160)

    return bs, comments

# ============================================================
#  적 (ENEMY: 시간 기반 스포너 + 3종 클론 본체)
# ============================================================
def build_enemy_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_EISC, 0)
    _seq(bs, [h, hi, rs, orig0])

    # (B) 시간 기반 스폰 forever (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    isc_chk = vrep("복제됨", V_EISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    # 적생성X = pick random -140..140
    rx = gen(); bs[rx] = mk("operator_random", inputs={"FROM": num(-140), "TO": num(140)})
    set_spx = gen(); bs[set_spx] = mk("data_setvariableto",
        inputs={"VALUE": slot(rx)}, fields={"VARIABLE": ["적생성X", V_SPX]})
    bs[rx]["parent"] = set_spx
    # 종류 결정: 단계=0→1 / 단계=1→1+(스폰카운트 mod 2) / else→2+(rand 0..1)
    stage_r1 = vrep("단계", V_STAGE)
    cond_st0 = cmp_op("operator_equals", stage_r1, 0)
    set_type1 = b_setvar(bs, "적생성종류", V_SPTYPE, 1)
    stage_r2 = vrep("단계", V_STAGE)
    cond_st1 = cmp_op("operator_equals", stage_r2, 1)
    spn_r = vrep("스폰카운트", V_SPAWNN)
    mod2 = op("operator_mod", spn_r, 2)
    type_alt = op("operator_add", 1, mod2)
    set_type_alt = gen(); bs[set_type_alt] = mk("data_setvariableto",
        inputs={"VALUE": slot(type_alt)}, fields={"VARIABLE": ["적생성종류", V_SPTYPE]})
    bs[type_alt]["parent"] = set_type_alt
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
    spawn_body = _seq(bs, [set_spx, if_type, inc_spn, inc_alive, cclone])
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    if_play_b = b_if(bs, cond_play_b, spawn_body)
    w_gap = b_wait_var(bs, V_EFFGAP, "유효스폰간격")
    fe_b = b_forever(bs, _seq(bs, [if_play_b, w_gap]))
    if_spawner = b_if(bs, cond_orig, fe_b)
    _seq(bs, [hb, if_spawner])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=460)
    set_isc1 = b_setvar(bs, "복제됨", V_EISC, 1)
    set_type = b_setvar(bs, "적종류", V_ETYPE, vrep("적생성종류", V_SPTYPE))
    rphase = gen(); bs[rphase] = mk("operator_random", inputs={"FROM": num(0), "TO": num(100)})
    set_phase = b_setvar(bs, "흔들위상", V_EPHASE, rphase)

    # 종류별 능력치/외형/스톰프가능
    def type_branch(type_val, hp_vid, hp_name, spd_vid, spd_name, stomp, costume, size_val):
        cond_t = cmp_op("operator_equals", vrep("적종류", V_ETYPE), type_val)
        set_hp = b_setvar(bs, "내체력", V_EHP, vrep(hp_name, hp_vid))
        set_spd = b_setvar(bs, "내속도", V_ESPD, vrep(spd_name, spd_vid))
        set_stomp = b_setvar(bs, "스톰프가능", V_ESTOMP, stomp)
        cmc = gen(); bs[cmc] = mk("looks_costume", fields={"COSTUME": [costume, None]}, shadow=True)
        sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc]})
        bs[cmc]["parent"] = sw
        szb = gen(); bs[szb] = mk("looks_setsizeto", inputs={"SIZE": num(size_val)})
        return b_if(bs, cond_t, _seq(bs, [set_hp, set_spd, set_stomp, sw, szb]))
    if_t1 = type_branch(1, V_E1HP, "점프벌레_체력", V_E1SPD, "점프벌레_속도", 1, "점프벌레", 50)
    if_t2 = type_branch(2, V_E2HP, "박쥐_체력", V_E2SPD, "박쥐_속도", 0, "박쥐", 55)
    if_t3 = type_branch(3, V_E3HP, "가시_체력", V_E3SPD, "가시_속도", 0, "가시고슴도치", 55)
    set_hit0 = b_setvar(bs, "피격쿨", V_EHIT, 0)
    # go to x:적생성X y:-210 ; show
    spx_r = vrep("적생성X", V_SPX)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(spx_r), "Y": num(-210)})
    bs[spx_r]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")

    # ---- forever body ----
    body = []
    # 0) 게임오버 정리
    state1 = vrep("게임상태", V_STATE)
    cond_go = cmp_op("operator_equals", state1, 0)
    dec_alive_go = b_changevar(bs, "적수", V_ALIVE, -1)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    if_go = b_if(bs, cond_go, _seq(bs, [dec_alive_go, del_go]))
    body.append(if_go)

    # 게임상태=1 블록 (스크롤·흔들·스톰프·피격·처치)
    play1 = []
    # 1) 스크롤 + 흔들
    play1.append(b_changevar_y(bs, vrep("낙하속도", V_FALL)))
    play1.append(b_changevar(bs, "흔들위상", V_EPHASE, 4))
    phase_r = vrep("흔들위상", V_EPHASE)
    sinb = gen(); bs[sinb] = mk("operator_mathop",
        inputs={"NUM": slot(phase_r)}, fields={"OPERATOR": ["sin", None]})
    bs[phase_r]["parent"] = sinb
    spd_div = op("operator_divide", vrep("내속도", V_ESPD), 10)
    wob = op("operator_multiply", sinb, spd_div)
    cx_wob = gen(); bs[cx_wob] = mk("motion_changexby", inputs={"DX": slot(wob)})
    bs[wob]["parent"] = cx_wob
    play1.append(cx_wob)
    # if y>200 → 적수-1; delete
    yp_top = gen(); bs[yp_top] = mk("motion_yposition")
    cond_top = cmp_op("operator_gt", yp_top, 200)
    dec_alive_top = b_changevar(bs, "적수", V_ALIVE, -1)
    del_top = gen(); bs[del_top] = mk("control_delete_this_clone")
    play1.append(b_if(bs, cond_top, _seq(bs, [dec_alive_top, del_top])))

    # 2) 스톰프 판정: 스톰프가능=1 & touching 소년 & 카메라선>(y+10) & 낙하속도>0
    stomp_r = vrep("스톰프가능", V_ESTOMP)
    cond_can_stomp = cmp_op("operator_equals", stomp_r, 1)
    tc_boy = b_touching(bs, "소년")
    camy_r = vrep("카메라선", V_CAMY)
    yp_s = gen(); bs[yp_s] = mk("motion_yposition")
    yp_s10 = op("operator_add", yp_s, 10)
    cond_above = cmp_op("operator_gt", camy_r, yp_s10)
    fall_rs = vrep("낙하속도", V_FALL)
    cond_falling = cmp_op("operator_gt", fall_rs, 0)
    sa = bool_op("operator_and", cond_can_stomp, tc_boy)
    sb_ = bool_op("operator_and", sa, cond_above)
    cond_stomp = bool_op("operator_and", sb_, cond_falling)
    # 스톰프 처치 본체
    st_body = []
    sxp = gen(); bs[sxp] = mk("motion_xposition")
    st_body.append(b_setvar(bs, "보석X", V_GEMX, sxp))
    syp = gen(); bs[syp] = mk("motion_yposition")
    st_body.append(b_setvar(bs, "보석Y", V_GEMY, syp))
    st_body.append(b_setvar(bs, "보석값", V_GEMV, vrep("점프벌레_보석", V_E1GEM)))
    st_body.append(b_broadcast(bs, "보석생성", BR_GEM))
    st_body.append(b_changevar(bs, "콤보", V_COMBO, 1))
    # if 콤보>콤보최고 set 콤보최고=콤보
    combo_r = vrep("콤보", V_COMBO); cmax_r = vrep("콤보최고", V_COMBOMAX)
    cond_cmax = cmp_op("operator_gt", combo_r, cmax_r)
    set_cmax = b_setvar(bs, "콤보최고", V_COMBOMAX, vrep("콤보", V_COMBO))
    st_body.append(b_if(bs, cond_cmax, set_cmax))
    # 깊이 += 처치점수*콤보
    killpt_combo = op("operator_multiply", vrep("처치점수", V_KILLPT), vrep("콤보", V_COMBO))
    st_body.append(b_changevar(bs, "깊이", V_DEPTH, killpt_combo))
    # 소년 튕김 + 탄약충전
    neg_bounce = op("operator_subtract", 0, vrep("착지반동", V_BOUNCE))
    st_body.append(b_setvar(bs, "낙하속도", V_FALL, neg_bounce))
    st_body.append(b_setvar(bs, "탄약", V_AMMO, vrep("탄약최대", V_AMMOMAX)))
    st_body.append(b_setvar(bs, "접지여유", V_COYOTET, vrep("코요테", V_COYOTE)))
    st_body += b_play(bs, 0, "stomp")
    combo_pitch = op("operator_multiply", vrep("콤보", V_COMBO), 25)
    st_body += b_play_var(bs, combo_pitch, "combo")
    # 처치 연출 + 삭제
    exm = gen(); bs[exm] = mk("looks_costume", fields={"COSTUME": ["폭발", None]}, shadow=True)
    sw_ex = gen(); bs[sw_ex] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, exm]})
    bs[exm]["parent"] = sw_ex
    st_body.append(sw_ex)
    st_body += b_play(bs, 0, "boom")
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(12)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(20)}, fields={"EFFECT": ["GHOST", None]})
    w_an = b_wait(bs, 0.02)
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK": [2, _seq(bs, [ch_sz, ch_gh, w_an])]})
    bs[ch_sz]["parent"] = rep_an
    st_body.append(rep_an)
    st_body.append(b_changevar(bs, "적수", V_ALIVE, -1))
    del_st = gen(); bs[del_st] = mk("control_delete_this_clone")
    st_body.append(del_st)
    play1.append(b_if(bs, cond_stomp, _seq(bs, st_body)))

    # 3) 총알 피격: touching 총알 & 피격쿨=0
    tc_bullet = b_touching(bs, "총알")
    hit_r = vrep("피격쿨", V_EHIT)
    cond_hit0 = cmp_op("operator_equals", hit_r, 0)
    cond_struck = bool_op("operator_and", tc_bullet, cond_hit0)
    neg_atk = op("operator_subtract", 0, vrep("총알공격력", V_BULATK))
    dec_myhp = b_changevar(bs, "내체력", V_EHP, neg_atk)
    set_hit = b_setvar(bs, "피격쿨", V_EHIT, 6)
    set_dval = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("총알공격력", V_BULATK))
    dxp = gen(); bs[dxp] = mk("motion_xposition")
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, dxp)
    dyp = gen(); bs[dyp] = mk("motion_yposition")
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, dyp)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    play_tick = b_play(bs, -200, "zap")
    play1.append(b_if(bs, cond_struck, _seq(bs, [dec_myhp, set_hit, set_dval, set_dx, set_dy, bc_dmg] + play_tick)))
    # 피격쿨 -1
    hit_r2 = vrep("피격쿨", V_EHIT)
    cond_hitpos = cmp_op("operator_gt", hit_r2, 0)
    dec_hit = b_changevar(bs, "피격쿨", V_EHIT, -1)
    play1.append(b_if(bs, cond_hitpos, dec_hit))

    # 4) 처치(체력<1, 총알로 죽음)
    myhp_r = vrep("내체력", V_EHP)
    cond_dead = cmp_op("operator_lt", myhp_r, 1)
    kbody = []
    kxp = gen(); bs[kxp] = mk("motion_xposition")
    kbody.append(b_setvar(bs, "보석X", V_GEMX, kxp))
    kyp = gen(); bs[kyp] = mk("motion_yposition")
    kbody.append(b_setvar(bs, "보석Y", V_GEMY, kyp))
    # 보석값 종류별
    tg1 = cmp_op("operator_equals", vrep("적종류", V_ETYPE), 1)
    set_gv1 = b_setvar(bs, "보석값", V_GEMV, vrep("점프벌레_보석", V_E1GEM))
    tg2 = cmp_op("operator_equals", vrep("적종류", V_ETYPE), 2)
    set_gv2 = b_setvar(bs, "보석값", V_GEMV, vrep("박쥐_보석", V_E2GEM))
    set_gv3 = b_setvar(bs, "보석값", V_GEMV, vrep("가시_보석", V_E3GEM))
    if_gv2 = b_ifelse(bs, tg2, set_gv2, set_gv3)
    if_gv = b_ifelse(bs, tg1, set_gv1, if_gv2)
    kbody.append(if_gv)
    kbody.append(b_broadcast(bs, "보석생성", BR_GEM))
    kbody.append(b_changevar(bs, "콤보", V_COMBO, 1))
    combo_r2 = vrep("콤보", V_COMBO); cmax_r2 = vrep("콤보최고", V_COMBOMAX)
    cond_cmax2 = cmp_op("operator_gt", combo_r2, cmax_r2)
    set_cmax2 = b_setvar(bs, "콤보최고", V_COMBOMAX, vrep("콤보", V_COMBO))
    kbody.append(b_if(bs, cond_cmax2, set_cmax2))
    killpt_combo2 = op("operator_multiply", vrep("처치점수", V_KILLPT), vrep("콤보", V_COMBO))
    kbody.append(b_changevar(bs, "깊이", V_DEPTH, killpt_combo2))
    combo_pitch2 = op("operator_multiply", vrep("콤보", V_COMBO), 25)
    kbody += b_play_var(bs, combo_pitch2, "combo")
    kbody.append(b_changevar(bs, "적수", V_ALIVE, -1))
    exm2 = gen(); bs[exm2] = mk("looks_costume", fields={"COSTUME": ["폭발", None]}, shadow=True)
    sw_ex2 = gen(); bs[sw_ex2] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, exm2]})
    bs[exm2]["parent"] = sw_ex2
    kbody.append(sw_ex2)
    kbody += b_play(bs, 0, "boom")
    ch_sz2 = gen(); bs[ch_sz2] = mk("looks_changesizeby", inputs={"CHANGE": num(12)})
    ch_gh2 = gen(); bs[ch_gh2] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(20)}, fields={"EFFECT": ["GHOST", None]})
    w_an2 = b_wait(bs, 0.02)
    rep_an2 = gen(); bs[rep_an2] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK": [2, _seq(bs, [ch_sz2, ch_gh2, w_an2])]})
    bs[ch_sz2]["parent"] = rep_an2
    kbody.append(rep_an2)
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")
    kbody.append(del_k)
    play1.append(b_if(bs, cond_dead, _seq(bs, kbody)))

    play1_head = _seq(bs, play1)
    state2 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state2, 1)
    if_play2 = b_if(bs, cond_play2, play1_head)
    body.append(if_play2)

    w_body = b_wait(bs, 0.025)
    fe_body = b_forever(bs, _seq(bs, body + [w_body]))
    _seq(bs, [ch, set_isc1, set_type, set_phase, if_t1, if_t2, if_t3, set_hit0, g, show, fe_body])

    add_comment(bs, comments, ch,
        "👾 적 3종 + 스톰프 vs 쏘기\n"
        "적종류로 코스튬·체력·속도·스톰프가능을 정해요: 점프벌레(밟기 가능) / 박쥐·가시(반드시 쏘기). "
        "월드 스크롤은 'change y by 낙하속도' — 소년이 아니라 적이 위로 흘러 내려가는 효과예요.",
        x=560, y=-60, w=330, h=170)
    add_comment(bs, comments, if_play2,
        "✖️ 콤보 = 곱셈 점수\n"
        "공중에서 처치(스톰프 or 총알)할 때마다 콤보+1, 그리고 깊이 += 처치점수 × 콤보! "
        "땅에 안 닿고 연속 처치하면 같은 적인데 점수가 곱으로 불어나요(콤보음도 점점 높아져요).",
        x=560, y=300, w=320, h=170)

    return bs, comments

# change y by (낙하속도) 전용 빌더 (motion_changeyby with 리포터)
def b_changevar_y(bs, fall_rep):
    cy = gen(); bs[cy] = mk("motion_changeyby", inputs={"DY": slot(fall_rep)})
    bs[fall_rep]["parent"] = cy
    return cy

# ============================================================
#  보석 (GEM: 드롭 + 스크롤 + 획득)
# ============================================================
def build_gem_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(45)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_GEMISC, 0)
    _seq(bs, [h, hi, sz, rs, orig0])

    # (B) 보석생성 → 클론 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["보석생성", BR_GEM]})
    isc_chk = vrep("복제됨", V_GEMISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    _seq(bs, [hb, if_spawn])

    # (C) 클론 본체 — 위로 스크롤, 소년에 닿으면 깊이 += 내값
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=420)
    set_isc1 = b_setvar(bs, "복제됨", V_GEMISC, 1)
    set_mine = b_setvar(bs, "내값", V_GEMMINE, vrep("보석값", V_GEMV))
    gx_r = vrep("보석X", V_GEMX); gy_r = vrep("보석Y", V_GEMY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(gx_r), "Y": slot(gy_r)})
    bs[gx_r]["parent"] = g; bs[gy_r]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")
    # forever
    state1 = vrep("게임상태", V_STATE)
    cond_go = cmp_op("operator_equals", state1, 0)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    if_go = b_if(bs, cond_go, del_go)
    cy = b_changevar_y(bs, vrep("낙하속도", V_FALL))
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_top = cmp_op("operator_gt", yp, 200)
    del_top = gen(); bs[del_top] = mk("control_delete_this_clone")
    if_top = b_if(bs, cond_top, del_top)
    tc_boy = b_touching(bs, "소년")
    inc_depth = b_changevar(bs, "깊이", V_DEPTH, vrep("내값", V_GEMMINE))
    play_coin = b_play(bs, 0, "coin")
    del_pick = gen(); bs[del_pick] = mk("control_delete_this_clone")
    if_pick = b_if(bs, tc_boy, _seq(bs, [inc_depth] + play_coin + [del_pick]))
    play_head = _seq(bs, [cy, if_top, if_pick])
    state2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state2, 1)
    if_play = b_if(bs, cond_play, play_head)
    w_body = b_wait(bs, 0.025)
    fe_body = b_forever(bs, _seq(bs, [if_go, if_play, w_body]))
    _seq(bs, [ch, set_isc1, set_mine, g, show, fe_body])

    return bs, comments

# ============================================================
#  발판 (LEDGE: 스크롤되는 착지 ledge)
# ============================================================
def build_ledge_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_LEDGEISC, 0)
    _seq(bs, [h, hi, sz, rs, orig0])

    # (B) 스폰 forever (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    isc_chk = vrep("복제됨", V_LEDGEISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    state_b = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_b, 1)
    if_play_b = b_if(bs, cond_play_b, cclone)
    w_gap = b_wait_var(bs, V_LEDGEGAP, "발판간격")
    fe_b = b_forever(bs, _seq(bs, [if_play_b, w_gap]))
    if_spawner = b_if(bs, cond_orig, fe_b)
    _seq(bs, [hb, if_spawner])

    # (C) 클론 본체 — 위로 스크롤
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=420)
    set_isc1 = b_setvar(bs, "복제됨", V_LEDGEISC, 1)
    rx = gen(); bs[rx] = mk("operator_random", inputs={"FROM": num(-120), "TO": num(120)})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(rx), "Y": num(-205)})
    bs[rx]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")
    state1 = vrep("게임상태", V_STATE)
    cond_go = cmp_op("operator_equals", state1, 0)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    if_go = b_if(bs, cond_go, del_go)
    cy = b_changevar_y(bs, vrep("낙하속도", V_FALL))
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond_top = cmp_op("operator_gt", yp, 200)
    del_top = gen(); bs[del_top] = mk("control_delete_this_clone")
    if_top = b_if(bs, cond_top, del_top)
    play_head = _seq(bs, [cy, if_top])
    state2 = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state2, 1)
    if_play = b_if(bs, cond_play, play_head)
    w_body = b_wait(bs, 0.025)
    fe_body = b_forever(bs, _seq(bs, [if_go, if_play, w_body]))
    _seq(bs, [ch, set_isc1, g, show, fe_body])

    add_comment(bs, comments, ch,
        "🪨 발판 = 착지대 (탄약 충전소)\n"
        "발판도 아래서 스폰돼 낙하속도만큼 위로 흘러요. 소년이 위에서 닿으면 탄약이 가득 차지만 "
        "콤보는 0으로 리셋돼요 — 발판간격을 키우면 발판이 드물어져 더 짜릿해져요.",
        x=300, y=-40, w=320, h=160)

    return bs, comments

# ============================================================
#  강화카드 (CARD)
# ============================================================
def build_card_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    _seq(bs, [h, hi, g, sz, front])

    # (B) 강화 → show, 1/2/3/4 대기, 적용, 강화완료
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["강화", BR_UP]})
    show = gen(); bs[show] = mk("looks_show")
    k1 = b_keypressed(bs, "1"); k2 = b_keypressed(bs, "2")
    k3 = b_keypressed(bs, "3"); k4 = b_keypressed(bs, "4")
    or12 = bool_op("operator_or", k1, k2)
    or123 = bool_op("operator_or", or12, k3)
    or1234 = bool_op("operator_or", or123, k4)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, or1234]})
    bs[or1234]["parent"] = wu
    # 1 → 탄약최대 += 강화량 ; 탄약 = 탄약최대
    ch_ammomax = b_changevar(bs, "탄약최대", V_AMMOMAX, vrep("강화량", V_UP))
    set_ammo = b_setvar(bs, "탄약", V_AMMO, vrep("탄약최대", V_AMMOMAX))
    if_k1 = b_if(bs, b_keypressed(bs, "1"), _seq(bs, [ch_ammomax, set_ammo]))
    # 2 → 연사간격 -= (0.02*강화량) ; 하한 0.04
    dec_amt = op("operator_multiply", 0.02, vrep("강화량", V_UP))
    neg_dec = op("operator_subtract", 0, dec_amt)
    ch_gap = b_changevar(bs, "연사간격", V_FIREGAP, neg_dec)
    gap_r = vrep("연사간격", V_FIREGAP)
    cond_low = cmp_op("operator_lt", gap_r, 0.04)
    set_gap_min = b_setvar(bs, "연사간격", V_FIREGAP, 0.04)
    if_clamp = b_if(bs, cond_low, set_gap_min)
    if_k2 = b_if(bs, b_keypressed(bs, "2"), _seq(bs, [ch_gap, if_clamp]))
    # 3 → 부양력 += (0.3*강화량)
    inc_amt = op("operator_multiply", 0.3, vrep("강화량", V_UP))
    ch_float = b_changevar(bs, "부양력", V_FLOAT, inc_amt)
    if_k3 = b_if(bs, b_keypressed(bs, "3"), ch_float)
    # 4 → 이동속도 += 강화량
    ch_move = b_changevar(bs, "이동속도", V_MOVE, vrep("강화량", V_UP))
    if_k4 = b_if(bs, b_keypressed(bs, "4"), ch_move)
    # 다음강화깊이 += 강화깊이 ; play levelup ; hide ; wait 0.2 ; 게임상태=1 ; 강화완료
    inc_next = b_changevar(bs, "다음강화깊이", V_NEXTUP, vrep("강화깊이", V_UPDEPTH))
    play_up = b_play(bs, 0, "levelup")
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    w1 = b_wait(bs, 0.2)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    bc_done = b_broadcast(bs, "강화완료", BR_UPDONE)
    _seq(bs, [hb, show, wu, if_k1, if_k2, if_k3, if_k4, inc_next] + play_up + [hi2, w1, set_st1, bc_done])

    add_comment(bs, comments, hb,
        "🃏 강화 택1 (1~4 키)\n"
        "깊이가 강화깊이마다 카드가 떠요: 1 탄약+ · 2 연사+(간격↓) · 3 부양력+ · 4 이동+. "
        "전부 '변수 += 강화량'(연사만 −) — 강해지는 규칙을 네가 직접 손볼 수 있어요. "
        "5번(점프력+)을 추가해 보는 게 미션 사다리 3층!",
        x=440, y=-40, w=320, h=180)

    return bs, comments

# ============================================================
#  게임오버 (GAME OVER 배너)
# ============================================================
def build_gameover_blocks():
    bs = {}
    comments = {}
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
    _seq(bs, [h, hi, g, sz, front, wu1, wu2, show])
    return bs, comments

# ============================================================
#  데미지 (플로팅 데미지 팝업) — 숫자 코스튬 0~9, say 미사용
# ============================================================
def build_damage_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_DMGISC, 0)
    _seq(bs, [h, hi, rs, orig0])

    # (B) 데미지표시 받으면 자릿수만큼 클론 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["데미지표시", BR_DMG]})
    isc_chk = vrep("복제됨", V_DMGISC)
    cond_orig = cmp_op("operator_equals", isc_chk, 0)
    dval_r = vrep("데미지표시값", V_DMGVAL)
    len_b = gen(); bs[len_b] = mk("operator_length", inputs={"STRING": slot(dval_r)})
    bs[dval_r]["parent"] = len_b
    set_len = b_setvar(bs, "데미지글자수", V_DMGLEN, len_b)
    set_pos1 = b_setvar(bs, "데미지자리", V_DMGPOS, 1)
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
    rep_head = _seq(bs, [set_digit, set_off, cclone, inc_pos, w_sp])
    len_rep = vrep("데미지글자수", V_DMGLEN)
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": slot(len_rep), "SUBSTACK": [2, rep_head]})
    bs[len_rep]["parent"] = rep; bs[rep_head]["parent"] = rep
    if_spawn = b_if(bs, cond_orig, _seq(bs, [set_len, set_pos1, rep]))
    _seq(bs, [hb, if_spawn])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_DMGISC, 1)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    dig_r = vrep("데미지숫자", V_DMGDIGIT)
    sw_num = gen(); bs[sw_num] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(dig_r)})
    bs[dig_r]["parent"] = sw_num
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
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(12), "SUBSTACK": [2, _seq(bs, [ch_y, ch_gh, w_an])]})
    bs[ch_y]["parent"] = rep_an
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    _seq(bs, [ch, set_isc1, front, sz, sw_num, g, clr_gh, show, rep_an, del_c])
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
    boy_md5   = save_svg(BOY_SVG)
    bul_md5   = save_svg(BULLET_SVG)
    bug_md5   = save_svg(JUMPBUG_SVG)
    bat_md5   = save_svg(BAT_SVG)
    spike_md5 = save_svg(SPIKE_SVG)
    ex_md5    = save_svg(EXPLOSION_SVG)
    gem_md5   = save_svg(GEM_SVG)
    ledge_md5 = save_svg(LEDGE_SVG)
    card_md5  = save_svg(CARD_SVG)
    rs_md5    = save_svg(RESULT_SVG)
    digit_md5 = [save_svg(s) for s in DIGIT_SVGS]

    # 전용 효과음 합성 (전부 코드에서 결정적 생성)
    def save_wav(samples):
        b = _wav_bytes(samples)
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    zap_md5, zap_n         = save_wav(synth_zap())
    boom_md5, boom_n       = save_wav(synth_boom())
    stomp_md5, stomp_n     = save_wav(synth_stomp())
    combo_md5, combo_n     = save_wav(synth_combo())
    coin_md5, coin_n       = save_wav(synth_coin())
    hurt_md5, hurt_n       = save_wav(synth_hurt())
    levelup_md5, levelup_n = save_wav(synth_levelup())

    def snd(name, m, n):
        return {"name": name, "assetId": m, "dataFormat": "wav",
                "format": "", "rate": SND_RATE, "sampleCount": n, "md5ext": f"{m}.wav"}
    zap_s     = lambda: snd("zap", zap_md5, zap_n)
    boom_s    = lambda: snd("boom", boom_md5, boom_n)
    stomp_s   = lambda: snd("stomp", stomp_md5, stomp_n)
    combo_s   = lambda: snd("combo", combo_md5, combo_n)
    coin_s    = lambda: snd("coin", coin_md5, coin_n)
    hurt_s    = lambda: snd("hurt", hurt_md5, hurt_n)
    levelup_s = lambda: snd("levelup", levelup_md5, levelup_n)

    stage_blocks,    stage_cmt    = build_stage_blocks()
    boy_blocks,      boy_cmt      = build_boy_blocks()
    bullet_blocks,   bullet_cmt   = build_bullet_blocks()
    enemy_blocks,    enemy_cmt    = build_enemy_blocks()
    gem_blocks,      gem_cmt      = build_gem_blocks()
    ledge_blocks,    ledge_cmt    = build_ledge_blocks()
    card_blocks,     card_cmt     = build_card_blocks()
    gameover_blocks, gameover_cmt = build_gameover_blocks()
    damage_blocks,   damage_cmt   = build_damage_blocks()

    # ---- Stage: 전역 변수 60개 + 방송 6개 ----
    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 32
            V_MOVE: ["이동속도", 5], V_GRAV: ["중력", 0.55], V_FALLMAX: ["최대낙하", 9],
            V_JUMP: ["점프력", 7], V_FLOAT: ["부양력", 1.6], V_FLOATCAP: ["부양상한", 5],
            V_CAMY: ["카메라선", 40], V_COYOTE: ["코요테", 6], V_BOUNCE: ["착지반동", 1.5],
            V_AMMOMAX: ["탄약최대", 6], V_FIREGAP: ["연사간격", 0.12], V_BULSPD: ["총알속도", 14],
            V_BULATK: ["총알공격력", 1], V_MAXHP: ["최대체력", 4], V_INV: ["무적시간", 30],
            V_KILLPT: ["처치점수", 5],
            V_E1HP: ["점프벌레_체력", 1], V_E1SPD: ["점프벌레_속도", 0.8], V_E1GEM: ["점프벌레_보석", 1],
            V_E2HP: ["박쥐_체력", 2], V_E2SPD: ["박쥐_속도", 1.6], V_E2GEM: ["박쥐_보석", 2],
            V_E3HP: ["가시_체력", 3], V_E3SPD: ["가시_속도", 0.4], V_E3GEM: ["가시_보석", 3],
            V_SPAWNGAP: ["스폰간격", 1.0], V_RAMPDEP: ["난이도깊이", 900], V_SPDOWN: ["스폰감소", 0.07],
            V_SPMIN: ["스폰간격최소", 0.35], V_LEDGEGAP: ["발판간격", 1.6],
            V_UPDEPTH: ["강화깊이", 1000], V_UP: ["강화량", 1],
            # 진행 28
            V_STATE: ["게임상태", 1], V_DEPTH: ["깊이", 0], V_COMBO: ["콤보", 0],
            V_COMBOMAX: ["콤보최고", 0], V_AMMO: ["탄약", 6], V_HP: ["체력", 4],
            V_INVT: ["무적", 0], V_FALL: ["낙하속도", 0], V_COYOTET: ["접지여유", 0],
            V_STAGE: ["단계", 0], V_SPAWNN: ["스폰카운트", 0], V_ALIVE: ["적수", 0],
            V_NEXTUP: ["다음강화깊이", 1000], V_EFFGAP: ["유효스폰간격", 1.0],
            V_FIRECD: ["발사쿨", 0], V_FIREX: ["발사X", 0], V_SPX: ["적생성X", 0],
            V_SPTYPE: ["적생성종류", 1], V_GEMX: ["보석X", 0], V_GEMY: ["보석Y", 0],
            V_GEMV: ["보석값", 1], V_DMGVAL: ["데미지표시값", 0], V_DMGX: ["데미지표시x", 0],
            V_DMGY: ["데미지표시y", 0], V_DMGDIGIT: ["데미지숫자", 0], V_DMGOFF: ["데미지오프셋", 0],
            V_DMGLEN: ["데미지글자수", 0], V_DMGPOS: ["데미지자리", 0],
        },
        "lists": {}, "broadcasts": {
            BR_START: "게임시작", BR_FIRE: "발사", BR_GEM: "보석생성",
            BR_UP: "강화", BR_UPDONE: "강화완료", BR_DMG: "데미지표시",
        },
        "blocks": stage_blocks, "comments": stage_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "우물", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    boy = {
        "isStage": False, "name": "소년",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": boy_blocks, "comments": boy_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "boy", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": boy_md5, "md5ext": f"{boy_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 38
        }],
        "sounds": [zap_s(), stomp_s(), hurt_s()],
        "volume": 100, "layerOrder": 7, "visible": True,
        "x": 0, "y": 40, "size": 65, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    bullet = {
        "isStage": False, "name": "총알",
        "variables": {V_BULISC: ["복제됨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": bullet_blocks, "comments": bullet_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "bullet", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": bul_md5, "md5ext": f"{bul_md5}.svg",
            "rotationCenterX": 20, "rotationCenterY": 20
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 40, "size": 45, "direction": 180,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    enemy = {
        "isStage": False, "name": "적",
        "variables": {V_EISC: ["복제됨", 0], V_EHP: ["내체력", 1], V_ESPD: ["내속도", 0.8],
                      V_ETYPE: ["적종류", 1], V_ESTOMP: ["스톰프가능", 1],
                      V_EHIT: ["피격쿨", 0], V_EPHASE: ["흔들위상", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": enemy_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "점프벌레", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bug_md5, "md5ext": f"{bug_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "박쥐", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": bat_md5, "md5ext": f"{bat_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "가시고슴도치", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": spike_md5, "md5ext": f"{spike_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "폭발", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ex_md5, "md5ext": f"{ex_md5}.svg",
             "rotationCenterX": 30, "rotationCenterY": 30},
        ],
        "sounds": [boom_s(), combo_s(), stomp_s(), zap_s()],
        "volume": 100, "layerOrder": 5, "visible": False,
        "x": 0, "y": 0, "size": 55, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    gem = {
        "isStage": False, "name": "보석",
        "variables": {V_GEMISC: ["복제됨", 0], V_GEMMINE: ["내값", 1]},
        "lists": {}, "broadcasts": {},
        "blocks": gem_blocks, "comments": gem_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "gem", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": gem_md5, "md5ext": f"{gem_md5}.svg",
            "rotationCenterX": 22, "rotationCenterY": 22
        }],
        "sounds": [coin_s()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 45, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ledge = {
        "isStage": False, "name": "발판",
        "variables": {V_LEDGEISC: ["복제됨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": ledge_blocks, "comments": ledge_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "ledge", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ledge_md5, "md5ext": f"{ledge_md5}.svg",
            "rotationCenterX": 48, "rotationCenterY": 9
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    card = {
        "isStage": False, "name": "강화카드",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": card_blocks, "comments": card_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "card", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": card_md5, "md5ext": f"{card_md5}.svg",
            "rotationCenterX": 200, "rotationCenterY": 85
        }],
        "sounds": [levelup_s()],
        "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 20, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    gameover = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": gameover_blocks, "comments": gameover_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "패배", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": rs_md5, "md5ext": f"{rs_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 80
        }],
        "sounds": [],
        "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    damage = {
        "isStage": False, "name": "데미지",
        "variables": {V_DMGISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": damage_blocks, "comments": damage_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": str(d), "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": digit_md5[d], "md5ext": f"{digit_md5[d]}.svg",
             "rotationCenterX": 16, "rotationCenterY": 22}
            for d in range(10)
        ],
        "sounds": [],
        "volume": 100, "layerOrder": 10, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # ---- 모니터: 깊이 / 콤보 / 탄약 / 체력 (튜닝 변수는 숨김) ----
    monitors = [
        {"id": V_DEPTH, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "깊이"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 99999, "isDiscrete": True},
        {"id": V_COMBO, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "콤보"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 50, "isDiscrete": True},
        {"id": V_AMMO, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "탄약"}, "spriteName": None,
         "value": 6, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 30, "isDiscrete": True},
        {"id": V_HP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "체력"}, "spriteName": None,
         "value": 4, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 20, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, boy, bullet, enemy, gem, ledge, card, gameover, damage],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "downwell-builder"}
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
    for nm, b in [("stage", stage_blocks), ("boy", boy_blocks),
                  ("bullet", bullet_blocks), ("enemy", enemy_blocks),
                  ("gem", gem_blocks), ("ledge", ledge_blocks),
                  ("card", card_blocks), ("gameover", gameover_blocks),
                  ("damage", damage_blocks)]:
        print(f"  {nm:9s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
