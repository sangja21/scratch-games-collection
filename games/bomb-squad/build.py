#!/usr/bin/env python3
"""폭탄 스쿼드 (bomb-squad) — 드래그 슬링샷 포물선 요격 방어 게임 (Bob-omb Squad 오마주).

하단 중앙 슬링샷을 마우스로 눌러 당겨(드래그) 포탄을 포물선으로 쏴 올려, 하늘에서
낙하산 타고 내려오는 폭탄을 요격하는 엔들리스 디펜스. 당기는 동안 점선 궤적(펜)이
실시간으로 휘고, 놓으면 그 궤적대로 포탄이 날아가 폭탄을 맞춘다. 바닥 꽃밭(꽃=라이프)이
다 부서지면 게임오버. 연속 명중 콤보로 점수를 배증하고, 라키투를 맞히면 화면 폭탄 전멸
보너스, 시간이 갈수록 폭탄이 더 빨리·자주 떨어진다 — 최고기록에 도전하는 엔들리스.

베이스: games/magic-survivor/build.py (한글 튜닝 변수 일괄 초기화·매직넘버 0 / 클론 스포너
        + 복제됨 가드 / 폭발 연출 / 플로팅 숫자 팝업 / 전용 합성 효과음 / 가이드 코멘트)
      + games/fish-tank/build.py (엔들리스 생존/최고기록 + 난이도 램프)
      + games/castle-defense/build.py (드래그 슬링샷 물리·펜 궤적·mousedown/mousex 헬퍼).

★ 게임의 존재 이유 = "아이가 코드의 숫자·규칙을 직접 바꾸며 노는 것". 모든 조절값(20개)을
  한글 전역 변수로만 노출하고 코드 어디서도 매직넘버를 쓰지 않는다. 튜닝 변수는 전부
  Stage 깃발 클릭 한 스크립트에서 초기화한다.

★ 드래그 물리 정확성: 궤적 점선 미리보기(궤적펜 dry-run)와 실제 포탄이 완전히 같은 공식
  (당김벡터 클램프 → 속도성분 → 중력·바람 누적)을 쓴다 → 점선대로 정확히 날아간다.
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "폭탄_스쿼드.sb3")

# ============================================================
#  효과음 합성 (전용 사운드 9종) — 결정적 생성
# ============================================================
SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    """float 샘플(-1..1) 리스트 → 16-bit PCM mono WAV 바이트 (결정적)."""
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_stretch(rate=SND_RATE):
    """고무줄 당김 '삐긋' — 상승 피치 200→500Hz, 0.1초."""
    N = int(rate * 0.1); out = []
    for i in range(N):
        t = i / rate
        f = 200 + 300 * (t / 0.1)              # 200 → 500Hz 상승
        env = math.exp(-t * 8) * (1 - math.exp(-t * 80))
        s = math.sin(2 * math.pi * f * t)
        out.append(s * env * 0.5)
    return out

def synth_fire(rate=SND_RATE):
    """발사 '핑!' — 노이즈 버스트 + 80Hz thump, 0.18초 (synth_boom 변형)."""
    N = int(rate * 0.18); out = []
    rng = random.Random(11110001)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 14)
        white = rng.random() * 2 - 1
        lp = lp + 0.5 * (white - lp)
        thump = math.sin(2 * math.pi * (80 + 60 * math.exp(-t * 24)) * t)
        s = (lp * 0.4 + thump * 0.8) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_pop(rate=SND_RATE):
    """폭탄 요격 '펑' — 짧은 노이즈 폭발 + 중역 thump, 0.14초."""
    N = int(rate * 0.14); out = []
    rng = random.Random(22220002)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 16)
        white = rng.random() * 2 - 1
        lp = lp + 0.55 * (white - lp)
        thump = math.sin(2 * math.pi * (180 + 120 * math.exp(-t * 22)) * t)
        s = (lp * 0.55 + thump * 0.6) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_combo(rate=SND_RATE):
    """콤보 상승 '띠링↑' — 상승 정현파, 0.1초 (pitch 이펙트 병용)."""
    N = int(rate * 0.1); out = []
    for i in range(N):
        t = i / rate
        f = 600 + 400 * (t / 0.1)             # 600 → 1000Hz
        env = math.exp(-t * 12) * (1 - math.exp(-t * 90))
        s = math.sin(2 * math.pi * f * t) + 0.3 * math.sin(2 * math.pi * f * 2 * t)
        out.append(s * env * 0.4)
    return out

def synth_wilt(rate=SND_RATE):
    """꽃 파괴 '시들' — 하강 정현파 500→200Hz + 낮은 buzz, 0.2초."""
    N = int(rate * 0.2); out = []
    for i in range(N):
        t = i / rate
        f = 500 - 300 * (t / 0.2)             # 500 → 200Hz 하강
        env = math.exp(-t * 7)
        buzz = 0.25 * (1 if math.sin(2 * math.pi * 70 * t) > 0 else -1)
        s = (math.sin(2 * math.pi * f * t) + buzz) / 1.25
        out.append(s * env * 0.45)
    return out

def synth_lakitu(rate=SND_RATE):
    """라키투 등장 '삐요~' — 빠른 상하 비브라토, 0.3초."""
    N = int(rate * 0.3); out = []
    for i in range(N):
        t = i / rate
        vib = 120 * math.sin(2 * math.pi * 9 * t)  # 비브라토
        f = 700 + vib
        env = math.exp(-t * 4) * (1 - math.exp(-t * 60))
        s = math.sin(2 * math.pi * f * t)
        out.append(s * env * 0.4)
    return out

def synth_clear(rate=SND_RATE):
    """라키투 명중 '콰광 화르륵' — 큰 노이즈 폭발 + 상승 화음, 0.35초."""
    N = int(rate * 0.35); out = []
    rng = random.Random(33330003)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 6)
        white = rng.random() * 2 - 1
        lp = lp + 0.4 * (white - lp)
        chord = (math.sin(2*math.pi*(300+500*t)*t) + math.sin(2*math.pi*(450+700*t)*t)) / 2
        s = (lp * 0.5 + chord * 0.6) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_gameover(rate=SND_RATE):
    """게임오버 하강 버저 — 400→120Hz 사각파, 0.3초."""
    N = int(rate * 0.3); out = []
    for i in range(N):
        t = i / rate
        f = 400 - 280 * (t / 0.3)             # 400 → 120Hz
        env = math.exp(-t * 3.5)
        sq = 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0
        out.append(sq * env * 0.4)
    return out

def synth_record(rate=SND_RATE):
    """신기록 팡파르 — 523→659→784→1047Hz 상승, 0.4초."""
    N = int(rate * 0.4); out = []
    notes = [523, 659, 784, 1047]
    seg = 0.1
    for i in range(N):
        t = i / rate
        idx = min(3, int(t / seg))
        f = notes[idx]
        lt = t - idx * seg
        env = math.exp(-lt * 6) * (1 - math.exp(-lt * 80))
        s = math.sin(2 * math.pi * f * t) + 0.3 * math.sin(2 * math.pi * f * 2 * t)
        out.append(s * env * 0.4)
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

# -------- 배경: 하늘(위) + 지면 꽃밭 띠(아래) + 구름 + 안내 텍스트 --------
random.seed(17)
_clouds = []
for cx, cy, s in [(90, 70, 1.0), (330, 50, 0.8), (410, 110, 0.6), (180, 130, 0.5)]:
    _clouds.append(
        f'<g opacity="0.85"><ellipse cx="{cx}" cy="{cy}" rx="{34*s:.0f}" ry="{16*s:.0f}" fill="#FFFFFF"/>'
        f'<ellipse cx="{cx-22*s:.0f}" cy="{cy+6*s:.0f}" rx="{22*s:.0f}" ry="{13*s:.0f}" fill="#FFFFFF"/>'
        f'<ellipse cx="{cx+24*s:.0f}" cy="{cy+5*s:.0f}" rx="{24*s:.0f}" ry="{13*s:.0f}" fill="#F4F8FF"/></g>')
CLOUDS = "\n    ".join(_clouds)
# 지면 라인(Scratch y=-120 → svg y = 180-(-120)=300)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#4FC3F7"/>
      <stop offset="1" stop-color="#B3E5FC"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <g>
    {CLOUDS}
  </g>
  <!-- 지면 잔디 띠 (꽃밭 라인 y=300 아래) -->
  <rect x="0" y="300" width="480" height="60" fill="#7CB342"/>
  <rect x="0" y="300" width="480" height="8" fill="#8BC34A"/>
  <rect x="0" y="330" width="480" height="30" fill="#6B4226"/>
  <!-- 슬링샷 앵커 표시선(중앙) -->
  <line x1="240" y1="300" x2="240" y2="360" stroke="#5D4037" stroke-width="2" opacity="0.3"/>
  <!-- 안내 텍스트 (스프라이트 절약) -->
  <text x="240" y="285" text-anchor="middle" fill="#1B5E20" font-family="Arial, sans-serif" font-size="13" font-weight="bold" opacity="0.85">↓ 아래 슬링샷을 마우스로 당겼다 놓아 적을 요격!</text>
</svg>"""

# -------- 발사대: Y자 슬링샷 프레임 (44x54) --------
FRAME_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="44" height="54" viewBox="0 0 44 54">
  <rect x="19" y="26" width="6" height="26" rx="2" fill="#8D6E63" stroke="#5D4037" stroke-width="2"/>
  <path d="M22 30 L8 8" stroke="#8D6E63" stroke-width="6" stroke-linecap="round"/>
  <path d="M22 30 L36 8" stroke="#8D6E63" stroke-width="6" stroke-linecap="round"/>
  <path d="M22 30 L8 8" stroke="#A1887F" stroke-width="2" stroke-linecap="round"/>
  <path d="M22 30 L36 8" stroke="#A1887F" stroke-width="2" stroke-linecap="round"/>
  <circle cx="8" cy="8" r="4" fill="#6D4C41"/>
  <circle cx="36" cy="8" r="4" fill="#6D4C41"/>
</svg>"""

# -------- 발사체 / 포탄 공용: 포탄 구체 (28x28) --------
BALL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">
  <circle cx="14" cy="14" r="12" fill="#37474F" stroke="#263238" stroke-width="2"/>
  <circle cx="10" cy="10" r="4" fill="#78909C" opacity="0.8"/>
  <circle cx="14" cy="4" r="2" fill="#FFB300"/>
  <path d="M14 4 Q18 1 20 3" fill="none" stroke="#FF6F00" stroke-width="1.5"/>
</svg>"""

# -------- 폭발 코스튬 (48x48) --------
BOOM_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <polygon points="{_star_pts(24, 24, 23, 10, 12)}" fill="#FF6F00" stroke="#E65100" stroke-width="1"/>
  <polygon points="{_star_pts(24, 24, 17, 7, 12, rot=0.262)}" fill="#FFB300"/>
  <circle cx="24" cy="24" r="9" fill="#FFEB3B"/>
  <circle cx="24" cy="24" r="4" fill="#FFFFFF"/>
</svg>"""

# -------- 낙하산 단 적 몬스터 (버섯/밤톨 느낌) (44x58) --------
# 낙하산(등속 완만 낙하 정당화) + 몸통은 적 캐릭터. 폭탄 아이콘 아님.
MONSTER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="44" height="58" viewBox="0 0 44 58">
  <!-- 낙하산 (초록) -->
  <path d="M4 20 A18 18 0 0 1 40 20 Z" fill="#43A047" stroke="#2E7D32" stroke-width="1.5"/>
  <path d="M4 20 A18 18 0 0 1 40 20" fill="none" stroke="#C8E6C9" stroke-width="1"/>
  <path d="M16 20 A6 12 0 0 1 28 20" fill="#66BB6A"/>
  <!-- 줄 -->
  <line x1="6" y1="20" x2="16" y2="36" stroke="#8D6E63" stroke-width="1"/>
  <line x1="22" y1="20" x2="22" y2="36" stroke="#8D6E63" stroke-width="1"/>
  <line x1="38" y1="20" x2="28" y2="36" stroke="#8D6E63" stroke-width="1"/>
  <!-- 몬스터 몸통 (밤톨/버섯형) -->
  <ellipse cx="22" cy="48" rx="12" ry="9" fill="#8D6E63" stroke="#5D4037" stroke-width="1.5"/>
  <path d="M11 46 Q22 32 33 46 Z" fill="#A1887F" stroke="#5D4037" stroke-width="1.5"/>
  <!-- 눈 -->
  <circle cx="18" cy="47" r="2.6" fill="#FFFFFF"/><circle cx="18" cy="47" r="1.3" fill="#1B0F0A"/>
  <circle cx="26" cy="47" r="2.6" fill="#FFFFFF"/><circle cx="26" cy="47" r="1.3" fill="#1B0F0A"/>
  <!-- 찡그린 입 (적대감) -->
  <path d="M17 53 Q22 50 27 53" fill="none" stroke="#3E2723" stroke-width="1.6"/>
  <!-- 작은 뿔 -->
  <path d="M13 40 L15 45 L11 44 Z" fill="#5D4037"/>
  <path d="M31 40 L29 45 L33 44 Z" fill="#5D4037"/>
</svg>"""

# -------- 라키투 (구름 탄 특수 적) (56x44) --------
LAKITU_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="44" viewBox="0 0 56 44">
  <!-- 구름 -->
  <g>
    <ellipse cx="28" cy="32" rx="24" ry="10" fill="#FFFFFF" stroke="#E0E0E0" stroke-width="1"/>
    <ellipse cx="14" cy="30" rx="10" ry="8" fill="#FFFFFF"/>
    <ellipse cx="42" cy="30" rx="10" ry="8" fill="#FFFFFF"/>
  </g>
  <!-- 등껍질 캐릭터 -->
  <circle cx="28" cy="16" r="11" fill="#66BB6A" stroke="#2E7D32" stroke-width="2"/>
  <ellipse cx="28" cy="9" rx="9" ry="5" fill="#FDD835" stroke="#F9A825" stroke-width="1.5"/>
  <circle cx="24" cy="15" r="2.5" fill="#FFFFFF"/><circle cx="24" cy="15" r="1.2" fill="#000"/>
  <circle cx="33" cy="15" r="2.5" fill="#FFFFFF"/><circle cx="33" cy="15" r="1.2" fill="#000"/>
  <path d="M25 21 Q28 24 32 21" fill="none" stroke="#1B5E20" stroke-width="1.5"/>
</svg>"""

# -------- 꽃: 핀 꽃 / 시든 꽃 (36x44) --------
FLOWER_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="36" height="44" viewBox="0 0 36 44">
  <rect x="16" y="22" width="4" height="20" rx="2" fill="#2E7D32"/>
  <path d="M18 32 Q8 28 6 34" fill="none" stroke="#388E3C" stroke-width="3"/>
  <path d="M18 30 Q28 26 30 32" fill="none" stroke="#388E3C" stroke-width="3"/>
  <g>
    <polygon points="{_star_pts(18, 16, 14, 6, 6)}" fill="#EC407A" stroke="#AD1457" stroke-width="1"/>
    <circle cx="18" cy="16" r="6" fill="#FFEB3B" stroke="#F9A825" stroke-width="1.5"/>
  </g>
</svg>"""

WILT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="36" height="44" viewBox="0 0 36 44">
  <path d="M18 42 Q14 34 20 24 Q24 20 22 16" fill="none" stroke="#6D4C41" stroke-width="4" stroke-linecap="round"/>
  <path d="M20 30 Q12 30 9 36" fill="none" stroke="#8D6E63" stroke-width="2.5"/>
  <ellipse cx="21" cy="15" rx="7" ry="5" fill="#8D6E63" opacity="0.7" transform="rotate(30 21 15)"/>
  <circle cx="21" cy="15" r="3" fill="#5D4037"/>
</svg>"""

# -------- 게임오버 / 신기록 배너 --------
GAMEOVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="5" y="5" width="350" height="140" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="62" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="42" font-weight="bold">GAME OVER</text>
  <text x="180" y="96" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="18">점수·최고기록은 왼쪽 위에서 확인!</text>
  <text x="180" y="126" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

NEWRECORD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="5" y="5" width="350" height="140" rx="14" fill="#1A237E" opacity="0.92" stroke="#FFD54F" stroke-width="5"/>
  <text x="180" y="60" text-anchor="middle" fill="#FFD54F" font-family="Arial, sans-serif" font-size="38" font-weight="bold">🏆 신기록!</text>
  <text x="180" y="96" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="18">최고기록을 갱신했어요!</text>
  <text x="180" y="126" text-anchor="middle" fill="#FFF9C4" font-family="Arial, sans-serif" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# 팝업 숫자 코스튬 0~9 (흰=일반 / 금=콤보·보너스), 말풍선 say 미사용.
def _digit_svg(d, gold):
    fill = "#FFD54F" if gold else "#FFFFFF"
    stroke = "#7A3E00" if gold else "#1A237E"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="28" height="40" viewBox="0 0 28 40">
  <text x="14" y="33" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-size="38" font-weight="bold" fill="{fill}" stroke="{stroke}" stroke-width="4" paint-order="stroke" stroke-linejoin="round">{d}</text>
</svg>"""
# 코스튬 순서: 흰 0~9 (인덱스 0~9), 금 0~9 (인덱스 10~19)
DIGIT_SVGS = [_digit_svg(d, False) for d in range(10)] + [_digit_svg(d, True) for d in range(10)]

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

def b_touching(bs, target):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": [target, None]}, shadow=True)
    t = gen(); bs[t] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, m]})
    bs[m]["parent"] = t
    return t

def b_mousedown(bs):
    bid = gen(); bs[bid] = mk("sensing_mousedown"); return bid
def b_mousex(bs):
    bid = gen(); bs[bid] = mk("sensing_mousex"); return bid
def b_mousey(bs):
    bid = gen(); bs[bid] = mk("sensing_mousey"); return bid
def b_xpos(bs):
    bid = gen(); bs[bid] = mk("motion_xposition"); return bid
def b_ypos(bs):
    bid = gen(); bs[bid] = mk("motion_yposition"); return bid

def b_mathop(bs, opname, val):
    bid = gen()
    if isinstance(val, str) and val in bs:
        bs[bid] = mk("operator_mathop", inputs={"NUM": slot(val)}, fields={"OPERATOR": [opname, None]})
        bs[val]["parent"] = bid
    else:
        bs[bid] = mk("operator_mathop", inputs={"NUM": num(val)}, fields={"OPERATOR": [opname, None]})
    return bid

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

def b_wait(bs, dur):
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": num(dur)})
    return bid

def b_wait_var(bs, vid, name):
    v = gen(); bs[v] = mk("data_variable", fields={"VARIABLE": [name, vid]})
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": slot(v)})
    bs[v]["parent"] = bid
    return bid

def b_wait_slot(bs, child):
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": slot(child)})
    bs[child]["parent"] = bid
    return bid

def b_waituntil(bs, cond):
    bid = gen(); bs[bid] = mk("control_wait_until", inputs={"CONDITION": [2, cond]})
    bs[cond]["parent"] = bid
    return bid

def b_sound(bs, pitch, sound):
    """(head=set-pitch, tail=play) 두 블록 반환. 호출부는 반드시 head·tail 둘 다
    상위 chain 에 연속으로 넣어야 tail(sound_play)이 고아가 되지 않는다."""
    pe = gen(); bs[pe] = mk("sound_seteffectto",
        inputs={"VALUE": num(pitch)}, fields={"EFFECT": ["PITCH", None]})
    sm = gen(); bs[sm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]})
    bs[sm]["parent"] = sp
    chain([(pe, bs[pe]), (sp, bs[sp])])
    return pe, sp

def b_sound_pitchvar(bs, pitch_child, sound):
    """pitch 를 변수/식(child block id)으로 세팅 후 재생. (head, tail) 반환 — head·tail
    둘 다 상위 chain 에 연속으로 넣어야 함."""
    pe = gen(); bs[pe] = mk("sound_seteffectto",
        inputs={"VALUE": slot(pitch_child)}, fields={"EFFECT": ["PITCH", None]})
    bs[pitch_child]["parent"] = pe
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

def b_costume(bs, name):
    cmc = gen(); bs[cmc] = mk("looks_costume", fields={"COSTUME": [name, None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc]})
    bs[cmc]["parent"] = sw
    return sw

def b_gotoxy(bs, x_val, y_val):
    """x/y 각각 리터럴(숫자) 또는 child block id."""
    bid = gen()
    xin = slot(x_val) if (isinstance(x_val, str) and x_val in bs) else num(x_val)
    yin = slot(y_val) if (isinstance(y_val, str) and y_val in bs) else num(y_val)
    bs[bid] = mk("motion_gotoxy", inputs={"X": xin, "Y": yin})
    if isinstance(x_val, str) and x_val in bs: bs[x_val]["parent"] = bid
    if isinstance(y_val, str) and y_val in bs: bs[y_val]["parent"] = bid
    return bid

def b_changeyby(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_changeyby", inputs={"DY": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_changexby(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_changexby", inputs={"DX": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_setx(bs, val):
    bid = gen()
    inp = slot(val) if (isinstance(val, str) and val in bs) else num(val)
    bs[bid] = mk("motion_setx", inputs={"X": inp})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_clone_self(bs):
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    return cclone

def b_del_clone(bs):
    bid = gen(); bs[bid] = mk("control_delete_this_clone"); return bid

def b_changesize(bs, val):
    bid = gen(); bs[bid] = mk("looks_changesizeby", inputs={"CHANGE": num(val)}); return bid
def b_changeghost(bs, val):
    bid = gen(); bs[bid] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(val)}, fields={"EFFECT": ["GHOST", None]}); return bid
def b_setghost(bs, val):
    bid = gen(); bs[bid] = mk("looks_seteffectto",
        inputs={"VALUE": num(val)}, fields={"EFFECT": ["GHOST", None]}); return bid
def b_setsize(bs, val):
    bid = gen(); bs[bid] = mk("looks_setsizeto", inputs={"SIZE": num(val)}); return bid

def b_pen(bs, op):
    bid = gen(); bs[bid] = mk(op); return bid
def b_pen_size(bs, sz):
    bid = gen(); bs[bid] = mk("pen_setPenSizeTo", inputs={"SIZE": num(sz)}); return bid
def b_pen_color(bs, color):
    bid = gen(); bs[bid] = mk("pen_setPenColorToColor", inputs={"COLOR": [1, [9, color]]}); return bid

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

def b_length_of(bs, listname, listid):
    bid = gen(); bs[bid] = mk("data_lengthoflist", fields={"LIST": [listname, listid]})
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

def b_abs(bs, val):
    return b_mathop(bs, "abs", val)

# ============================================================
#  IDs
# ============================================================
# ----- 5.1 튜닝 손잡이 20개 (전역, 매직넘버 대체) -----
# 조준/물리 4
V_POWMUL   = "varPowMul01"     # 발사력배율   0.22
V_DRAGMAX  = "varDragMax02"    # 최대당김거리  90
V_GRAVITY  = "varGravity03"    # 중력        0.30
V_WIND     = "varWind04"       # 바람        0.00
# 적/난이도 7
V_FALLSPD  = "varFallSpd05"    # 낙하속도    0.7
V_SPAWNGAP = "varSpawnGap06"   # 스폰간격    1.6
V_RAMP     = "varRamp07"       # 난이도증가율  0.02
V_SPAWNMAX = "varSpawnMax08"   # 스폰최대    8
V_SWAY     = "varSway09"       # 흔들폭      12
V_LAKITUP  = "varLakituP10"    # 라키투확률   40
V_LAKITUSPD= "varLakituSpd11"  # 라키투속도   3
# 방어/점수 9
V_FLOWERN  = "varFlowerN12"    # 꽃개수      4
V_BOMBPT   = "varBombPt13"     # 폭탄점수    100
V_COMBOMUL = "varComboMul14"   # 콤보배율    2
V_COMBOCAP = "varComboCap15"   # 콤보최대    32
V_BALLR    = "varBallR16"      # 포탄반경    14
V_OFFX     = "varOffX17"       # 착탄허용밖   250
V_GROUNDY  = "varGroundY18"    # 지면Y      -120
V_PRESTEPS = "varPreSteps19"   # 미리보기점수  70
V_PREGAP   = "varPreGap20"     # 미리보기간격  3
# 추가 튜닝 4개 (관통샷·연사·수명)
V_PIERCE   = "varPierce21b"    # 관통횟수    2   포탄이 관통할 수 있는 적 수(소진 시 소멸)
V_MAXBALL  = "varMaxBall22b"   # 최대포탄수   5   동시에 공중에 존재 가능한 포탄 클론 상한(연사)
V_BALLLIFE = "varBallLife23b"  # 포탄수명   150  포탄 클론 수명(틱, 0.02초/틱 → 150틱≈3초). 만료 시 소멸(안전망)
V_BGMVOL   = "varBgmVol24b"    # 브금볼륨   70   BGM 재생 음량(%). 효과음이 안 묻히게 적당히

# ----- 5.2 진행/내부 상태 전역 변수 26개 -----
V_STATE    = "varState21"      # 게임상태  1=진행중, 0=게임오버
V_SCORE    = "varScore22"      # 점수
V_BEST     = "varBest23"       # 최고점수 (깃발에서 리셋 안 함)
V_COMBO    = "varCombo24"      # 콤보수
V_COMBOX   = "varComboX25"     # 콤보배수
V_FLOWERLEFT = "varFlowerLeft26" # 꽃남음
V_KILLS    = "varKills27"      # 처치수
V_BOMBALIVE= "varBombAlive28"  # 폭탄수
V_ANCHORX  = "varAnchorX29"    # 앵커X
V_ANCHORY  = "varAnchorY30"    # 앵커Y
V_DRAGX    = "varDragX31"      # 당김X
V_DRAGY    = "varDragY32"      # 당김Y
V_DRAGMAG  = "varDragMag33"    # 당김크기
V_DRAGANG  = "varDragAng34"    # 당김각도
V_DRAGGING = "varDragging35"   # 드래그중
V_FLYING   = "varFlying36"     # 비행중
V_WIPE     = "varWipe37"       # 전멸신호
V_KILLFLOWERX = "varKillFlowerX38" # 파괴꽃X
V_POPVAL   = "varPopVal39"     # 명중점수값
V_POPX     = "varPopX40"       # 명중점수x
V_POPY     = "varPopY41"       # 명중점수y
V_POPKIND  = "varPopKind42"    # 팝업종류 0=흰,1=금
V_POPDIGIT = "varPopDigit43"   # 팝업숫자
V_POPOFF   = "varPopOff44"     # 팝업오프셋
V_POPLEN   = "varPopLen45"     # 팝업글자수
V_POPPOS   = "varPopPos46"     # 팝업자리

# ----- 5.4 클론-로컬 변수 -----
V_BALLISC  = "varBallIsClone"  # 포탄: 복제됨
V_BALLVX   = "varBallVX"       # 포탄: 속도X
V_BALLVY   = "varBallVY"       # 포탄: 속도Y
V_BALLPIER = "varBallPierce"   # 포탄: 남은관통 (관통샷)
V_BALLHITCD= "varBallHitCD"    # 포탄: 피격쿨 (같은 적 중복 히트 방지)
V_BALLLIFEC= "varBallLifeLeft" # 포탄: 남은수명 (틱 카운트다운, 0이면 소멸)
V_BOMBISC  = "varBombIsClone"  # 폭탄: 복제됨
V_BOMBFALL = "varBombFall"     # 폭탄: 내낙하
V_BOMBBASEX= "varBombBaseX"    # 폭탄: 흔들기준X
V_BOMBPHASE= "varBombPhase"    # 폭탄: 흔들위상
V_LAKISC   = "varLakIsClone"   # 라키투: 복제됨
V_LAKDIR   = "varLakDir"       # 라키투: 진행방향
V_FLOWERISC= "varFlowerIsClone"# 꽃: 복제됨
V_FLOWERMYX= "varFlowerMyX"    # 꽃: 내X
V_FLOWERALIVE = "varFlowerAlive" # 꽃: 살아있음
V_POPISC   = "varPopIsClone"   # 숫자팝업: 복제됨
V_PREX     = "varPreX"         # 궤적펜: 미리X
V_PREY     = "varPreY"         # 궤적펜: 미리Y
V_PREVX    = "varPreVX"        # 궤적펜: 미리VX
V_PREVY    = "varPreVY"        # 궤적펜: 미리VY

# 임시 루프 인덱스 (Stage 꽃X 배치용) — 전역이지만 튜닝 아님. 진행 변수에 포함 안 함.
V_TMPI     = "varTmpI47"       # 임시i (꽃 배치/렌더 루프)
# 꽃 최소거리 리덕션 채널 — "가장 가까운 살아있는 꽃 1개만 파괴"를 정확히 보장(견고성 최우선).
V_FLOWERMIND = "varFlowerMinD48"  # 꽃최소거리 (2패스: 측정→파괴)
V_FLOWERNEXTX = "varFlowerNextX49" # 다음꽃X (스포너→클론 배치 채널, 전용)
V_BALLALIVE = "varBallAlive50"    # 포탄수 (공중 포탄 클론 수, 최대포탄수 상한 판정 — 연사)

# ----- 5.3 리스트 1개 -----
L_FLOWERX  = "listFlowerX"     # 꽃X: 꽃(라이프) 각각의 X 좌표

# ----- 5.5 메시지 8개 -----
BR_START   = "brStart01"       # 게임시작
BR_FLOWER  = "brFlower02"      # 꽃생성
BR_SPAWNBOMB = "brSpawnBomb03" # 폭탄생성
BR_SPAWNLAK= "brSpawnLak04"    # 라키투생성
BR_FIRE    = "brFire05"        # 발사
BR_POP     = "brPop06"         # 점수표시
BR_KILLFLOWER = "brKillFlower07" # 꽃파괴 (2패스 파괴 실행)
BR_GAMEOVER= "brGameOver08"    # 게임오버
BR_MEASURE = "brMeasureFlower09" # 꽃거리측정 (2패스 1단계: 최소거리 리덕션)

# ============================================================
#  STAGE — 초기화 + 엔들리스 스폰 매니저 + 게임오버 감시
# ============================================================
def build_stage_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 → 튜닝 20 + 진행 26 전부 초기화 → 꽃X 배치 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val)
        seq.append((sid, bs[sid]))

    # ── 🛠️ 조준/물리 손잡이 (★ 이 4개가 궤적·손맛을 바꾼다) ──
    add_set("발사력배율", V_POWMUL, 0.22)
    add_set("최대당김거리", V_DRAGMAX, 90)
    add_set("중력", V_GRAVITY, 0.30)
    add_set("바람", V_WIND, 0)
    # ── 적/난이도 손잡이 ──
    add_set("낙하속도", V_FALLSPD, 0.7)
    add_set("스폰간격", V_SPAWNGAP, 1.6)
    add_set("난이도증가율", V_RAMP, 0.02)
    add_set("스폰최대", V_SPAWNMAX, 8)
    add_set("흔들폭", V_SWAY, 12)
    add_set("라키투확률", V_LAKITUP, 40)
    add_set("라키투속도", V_LAKITUSPD, 3)
    # ── 방어/점수 손잡이 ──
    add_set("꽃개수", V_FLOWERN, 4)
    add_set("요격점수", V_BOMBPT, 100)
    add_set("콤보배율", V_COMBOMUL, 2)
    add_set("콤보최대", V_COMBOCAP, 32)
    add_set("포탄반경", V_BALLR, 14)
    add_set("착탄허용밖", V_OFFX, 250)
    add_set("지면Y", V_GROUNDY, -120)
    add_set("미리보기점수", V_PRESTEPS, 70)
    add_set("미리보기간격", V_PREGAP, 3)
    add_set("관통횟수", V_PIERCE, 2)      # 포탄 1발이 적 몇 기를 관통하는지(소진 시 소멸)
    add_set("최대포탄수", V_MAXBALL, 5)   # 동시에 공중에 뜰 수 있는 포탄 수(연사 상한)
    add_set("포탄수명", V_BALLLIFE, 150)  # 포탄 클론 수명(틱, 0.02초/틱 → ≈3초). 만료 시 소멸 안전망
    add_set("브금볼륨", V_BGMVOL, 70)     # BGM 음량(%). 효과음이 안 묻히게 적당히
    # ── 진행 상태 ──
    add_set("앵커X", V_ANCHORX, 0)
    add_set("앵커Y", V_ANCHORY, -60)   # 새총 앵커: 하단 1/3 지점(꽃밭 지면Y=-120 보다 위) — 사방 당김 공간 확보
    add_set("게임상태", V_STATE, 1)
    add_set("점수", V_SCORE, 0)
    add_set("콤보수", V_COMBO, 0)
    add_set("콤보배수", V_COMBOX, 1)
    # 꽃남음 = 꽃개수
    fln_r = vrep("꽃개수", V_FLOWERN)
    set_fleft = b_setvar(bs, "꽃남음", V_FLOWERLEFT, fln_r); seq.append((set_fleft, bs[set_fleft]))
    add_set("처치수", V_KILLS, 0)
    add_set("적수", V_BOMBALIVE, 0)
    add_set("포탄수", V_BALLALIVE, 0)
    add_set("드래그중", V_DRAGGING, 0)
    add_set("비행중", V_FLYING, 0)
    add_set("전멸신호", V_WIPE, 0)
    add_set("당김X", V_DRAGX, 0)
    add_set("당김Y", V_DRAGY, 0)
    add_set("당김크기", V_DRAGMAG, 0)
    add_set("당김각도", V_DRAGANG, 0)
    add_set("파괴꽃X", V_KILLFLOWERX, 0)
    add_set("명중점수값", V_POPVAL, 0)
    add_set("명중점수x", V_POPX, 0)
    add_set("명중점수y", V_POPY, 0)
    add_set("팝업종류", V_POPKIND, 0)
    add_set("팝업숫자", V_POPDIGIT, 0)
    add_set("팝업오프셋", V_POPOFF, 0)
    add_set("팝업글자수", V_POPLEN, 0)
    add_set("팝업자리", V_POPPOS, 0)
    add_set("임시i", V_TMPI, 0)
    # ※ 최고점수는 초기화하지 않음(세션 유지)

    # ── 꽃X 리스트: 꽃개수만큼 균등 X 배치 (간격=300/(꽃개수-1)) ──
    del_fx = b_delete_all(bs, "꽃X", L_FLOWERX); seq.append((del_fx, bs[del_fx]))
    set_i0 = b_setvar(bs, "임시i", V_TMPI, 0); seq.append((set_i0, bs[set_i0]))
    # 꽃개수=1 가드: 1이면 add 0, 아니면 -150 + i*(300/(꽃개수-1))
    fln_g = vrep("꽃개수", V_FLOWERN)
    cond_one = cmp_op("operator_equals", fln_g, 1)
    add0 = b_add_to_list(bs, "꽃X", L_FLOWERX, 0)
    # else branch: add (-150 + i*(300/(꽃개수-1)))
    fln_d = vrep("꽃개수", V_FLOWERN)
    denom = op("operator_subtract", fln_d, 1)
    step = op("operator_divide", 300, denom)
    i_r = vrep("임시i", V_TMPI)
    iterm = op("operator_multiply", i_r, step)
    xval = op("operator_add", -150, iterm)
    add_x = b_add_to_list(bs, "꽃X", L_FLOWERX, xval)
    if_place = b_ifelse(bs, cond_one, add0, add_x)
    inc_i = b_changevar(bs, "임시i", V_TMPI, 1)
    chain([(if_place, bs[if_place]), (inc_i, bs[inc_i])])
    fln_rep = vrep("꽃개수", V_FLOWERN)
    rep_place = b_repeat(bs, fln_rep, if_place)
    seq.append((rep_place, bs[rep_place]))

    w1 = b_wait(bs, 0.2); seq.append((w1, bs[w1]))
    bc_start = b_broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # ===== (B) 게임시작 → 스폰 매니저 (엔들리스) =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=340, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    bc_flower = b_broadcast(bs, "꽃생성", BR_FLOWER)
    w_fl = b_wait(bs, 0.1)

    # forever body
    # if 게임상태=1:
    #   현재스폰간격 = 스폰간격 - 처치수*난이도증가율 ; if <0.4 → 0.4
    #   if 폭탄수 < 스폰최대:
    #     if (pick random 1 to 라키투확률)=1 : 라키투생성 else 폭탄생성
    #   wait 현재스폰간격
    # else wait 0.1
    # wait 값 = max(0.4, 스폰간격 − 처치수×난이도증가율). Scratch엔 max 없음 →
    #   (eff_gap<0.4)*0.4 + (eff_gap>=0.4)*eff_gap 조합. eff_gap 식은 reporter 재사용 불가라
    #   매번 새 블록으로 계산한다(아래 eff_gap2/3/4).
    kills_r2 = vrep("처치수", V_KILLS); ramp_r2 = vrep("난이도증가율", V_RAMP)
    ramp_term2 = op("operator_multiply", kills_r2, ramp_r2)
    gap_r2 = vrep("스폰간격", V_SPAWNGAP)
    eff_gap2 = op("operator_subtract", gap_r2, ramp_term2)
    lt04b = cmp_op("operator_lt", eff_gap2, 0.4)
    mul_a = op("operator_multiply", lt04b, 0.4)
    # (not lt04c)*eff_gap3
    kills_r3 = vrep("처치수", V_KILLS); ramp_r3 = vrep("난이도증가율", V_RAMP)
    ramp_term3 = op("operator_multiply", kills_r3, ramp_r3)
    gap_r3 = vrep("스폰간격", V_SPAWNGAP)
    eff_gap3 = op("operator_subtract", gap_r3, ramp_term3)
    lt04c = cmp_op("operator_lt", eff_gap3, 0.4)
    not_lt = gen(); bs[not_lt] = mk("operator_not", inputs={"OPERAND": [2, lt04c]})
    bs[lt04c]["parent"] = not_lt
    kills_r4 = vrep("처치수", V_KILLS); ramp_r4 = vrep("난이도증가율", V_RAMP)
    ramp_term4 = op("operator_multiply", kills_r4, ramp_r4)
    gap_r4 = vrep("스폰간격", V_SPAWNGAP)
    eff_gap4 = op("operator_subtract", gap_r4, ramp_term4)
    mul_b = op("operator_multiply", not_lt, eff_gap4)
    wait_val = op("operator_add", mul_a, mul_b)  # = max(0.4, eff_gap)
    # spawn choice
    lakp_r = vrep("라키투확률", V_LAKITUP)
    rnd_lak = gen(); bs[rnd_lak] = mk("operator_random",
        inputs={"FROM": num(1), "TO": slot(lakp_r)})
    bs[lakp_r]["parent"] = rnd_lak
    cond_lak = cmp_op("operator_equals", rnd_lak, 1)
    bc_lak = b_broadcast(bs, "라키투생성", BR_SPAWNLAK)
    bc_bomb = b_broadcast(bs, "적생성", BR_SPAWNBOMB)
    if_spawn_choice = b_ifelse(bs, cond_lak, bc_lak, bc_bomb)
    bombalive_r = vrep("적수", V_BOMBALIVE); spmax_r = vrep("스폰최대", V_SPAWNMAX)
    cond_room = cmp_op("operator_lt", bombalive_r, spmax_r)
    if_room = b_if(bs, cond_room, if_spawn_choice)
    w_spawn = b_wait_slot(bs, wait_val)
    chain([(if_room, bs[if_room]), (w_spawn, bs[w_spawn])])
    state_bb = vrep("게임상태", V_STATE)
    cond_play_b = cmp_op("operator_equals", state_bb, 1)
    w_idle_b = b_wait(bs, 0.1)
    if_play_b = b_ifelse(bs, cond_play_b, if_room, w_idle_b)
    fe_b = b_forever(bs, if_play_b)
    chain([(hb, bs[hb]), (bc_flower, bs[bc_flower]), (w_fl, bs[w_fl]), (fe_b, bs[fe_b])])

    # ===== (C) 게임오버 감시 forever =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=340, y=360,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    fleft_r = vrep("꽃남음", V_FLOWERLEFT)
    cond_dead = cmp_op("operator_lt", fleft_r, 1)   # 꽃남음 <= 0
    state_c = vrep("게임상태", V_STATE)
    cond_play_c = cmp_op("operator_equals", state_c, 1)
    cond_over = bool_op("operator_and", cond_dead, cond_play_c)
    bc_go = b_broadcast(bs, "게임오버", BR_GAMEOVER)
    if_over = b_if(bs, cond_over, bc_go)
    w_c = b_wait(bs, 0.05)
    chain([(if_over, bs[if_over]), (w_c, bs[w_c])])
    fe_c = b_forever(bs, if_over)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # ===== (D) BGM: 별도 병렬 깃발 스크립트 (게임 로직 hat 방해 없음) =====
    #   when green flag clicked → set volume (브금볼륨)% → forever { play bgm until done }
    #   until-done 반복이라 곡이 끝나면 자연스럽게 처음부터 다시(무한 루프). 게임오버여도 계속.
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=680, y=20)
    bgmvol_r = vrep("브금볼륨", V_BGMVOL)
    setvol = gen(); bs[setvol] = mk("sound_setvolumeto", inputs={"VOLUME": slot(bgmvol_r)})
    bs[bgmvol_r]["parent"] = setvol
    bgm_menu = gen(); bs[bgm_menu] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["bgm", None]}, shadow=True)
    play_bgm = gen(); bs[play_bgm] = mk("sound_playuntildone", inputs={"SOUND_MENU": [1, bgm_menu]})
    bs[bgm_menu]["parent"] = play_bgm
    fe_bgm = b_forever(bs, play_bgm)
    chain([(hd, bs[hd]), (setvol, bs[setvol]), (fe_bgm, bs[fe_bgm])])

    # ── 가이드 코멘트 ──
    add_comment(bs, comments, h,
        "🛠️ 개조 손잡이: 여기 숫자만 바꾸면 게임이 달라져요!\n"
        "중력·낙하속도·꽃개수·콤보배율·스폰간격… 전부 이 초록 깃발 묶음에 한글 변수로 모여 있어요. "
        "바꾸기 전에 '이렇게 될 것 같다'를 먼저 예상하고 ▶ 를 눌러 확인!",
        x=-380, y=-260, w=340, h=170)
    add_comment(bs, comments, seq[3][0],  # 중력 set
        "🌙 중력이 낮으면(0.1) 포탄이 거의 직선으로 날아가 쉬워요(달나라). "
        "높이면(0.7) 활처럼 크게 휘어 리드 조준이 필요해요(어려움). 난이도 손잡이!",
        x=-380, y=60, w=330, h=140)
    add_comment(bs, comments, fe_b,
        "⏱️ 폭탄을 잡을수록(처치수↑) 더 빨리·자주 떨어져요.\n"
        "현재스폰간격 = 스폰간격 − 처치수×난이도증가율 (하한 0.4초). "
        "난이도증가율로 기울기를 조절해요!",
        x=560, y=-40, w=320, h=150)

    return bs, comments

# ============================================================
#  발사대 (frame) — 고정 앵커 시각화
# ============================================================
def build_frame_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    ax_r = vrep("앵커X", V_ANCHORX); ay_r = vrep("앵커Y", V_ANCHORY)
    g = b_gotoxy(bs, ax_r, ay_r)
    # ★발사대는 뒤로 — 발사되는 포탄(go to front)이 슬링샷 프레임에 안 가려지게
    back = gen(); bs[back] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["back", None]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (back, bs[back]), (show, bs[show])])
    return bs, comments

# ============================================================
#  발사체 (ball) — 드래그 조준 + 놓으면 발사 (탄약 무제한)
# ============================================================
def build_launcher_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화 — 앵커에 얹혀 대기
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = b_setsize(bs, 100)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    ax_r = vrep("앵커X", V_ANCHORX); ay_r = vrep("앵커Y", V_ANCHORY)
    g = b_gotoxy(bs, ax_r, ay_r)
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (rs, bs[rs]), (sz, bs[sz]), (front, bs[front]), (g, bs[g]), (show, bs[show])])

    # (B) 게임시작 → 드래그 조준 루프
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # --- 당김 계산(공통①) repeat until not mousedown ---
    # 당김X = 앵커X - 마우스x ; 당김Y = 앵커Y - 마우스y
    ax1 = vrep("앵커X", V_ANCHORX); mx1 = b_mousex(bs)
    dragx_val = op("operator_subtract", ax1, mx1)
    set_dragx = b_setvar(bs, "당김X", V_DRAGX, dragx_val)
    ay1 = vrep("앵커Y", V_ANCHORY); my1 = b_mousey(bs)
    dragy_val = op("operator_subtract", ay1, my1)
    set_dragy = b_setvar(bs, "당김Y", V_DRAGY, dragy_val)
    # 당김크기 = sqrt(당김X^2 + 당김Y^2)
    dx_a = vrep("당김X", V_DRAGX); dx_b = vrep("당김X", V_DRAGX)
    dxsq = op("operator_multiply", dx_a, dx_b)
    dy_a = vrep("당김Y", V_DRAGY); dy_b = vrep("당김Y", V_DRAGY)
    dysq = op("operator_multiply", dy_a, dy_b)
    sumsq = op("operator_add", dxsq, dysq)
    magv = b_mathop(bs, "sqrt", sumsq)
    set_mag = b_setvar(bs, "당김크기", V_DRAGMAG, magv)
    # if 당김크기 > 최대당김거리 → 클램프
    mag_r = vrep("당김크기", V_DRAGMAG); dmax_r = vrep("최대당김거리", V_DRAGMAX)
    cond_over = cmp_op("operator_gt", mag_r, dmax_r)
    #   당김X = 당김X * 최대당김거리 / 당김크기
    dx_c = vrep("당김X", V_DRAGX); dmax_c = vrep("최대당김거리", V_DRAGMAX)
    dxm = op("operator_multiply", dx_c, dmax_c)
    mag_c = vrep("당김크기", V_DRAGMAG)
    dxclamp = op("operator_divide", dxm, mag_c)
    set_dxc = b_setvar(bs, "당김X", V_DRAGX, dxclamp)
    dy_c = vrep("당김Y", V_DRAGY); dmax_d = vrep("최대당김거리", V_DRAGMAX)
    dym = op("operator_multiply", dy_c, dmax_d)
    mag_d = vrep("당김크기", V_DRAGMAG)
    dyclamp = op("operator_divide", dym, mag_d)
    set_dyc = b_setvar(bs, "당김Y", V_DRAGY, dyclamp)
    dmax_e = vrep("최대당김거리", V_DRAGMAX)
    set_magc = b_setvar(bs, "당김크기", V_DRAGMAG, dmax_e)
    chain([(set_dxc, bs[set_dxc]), (set_dyc, bs[set_dyc]), (set_magc, bs[set_magc])])
    if_clamp = b_if(bs, cond_over, set_dxc)
    # 당김각도: if 당김X=0 → 90 else abs(atan(당김Y/당김X))
    dx_ang = vrep("당김X", V_DRAGX)
    cond_dx0 = cmp_op("operator_equals", dx_ang, 0)
    set_ang90 = b_setvar(bs, "당김각도", V_DRAGANG, 90)
    dy_ang = vrep("당김Y", V_DRAGY); dx_ang2 = vrep("당김X", V_DRAGX)
    ratio = op("operator_divide", dy_ang, dx_ang2)
    atanv = b_mathop(bs, "atan", ratio)
    absang = b_mathop(bs, "abs", atanv)
    set_angv = b_setvar(bs, "당김각도", V_DRAGANG, absang)
    if_ang = b_ifelse(bs, cond_dx0, set_ang90, set_angv)
    # go to (앵커X - 당김X, 앵커Y - 당김Y)
    ax_g = vrep("앵커X", V_ANCHORX); dx_g = vrep("당김X", V_DRAGX)
    gx = op("operator_subtract", ax_g, dx_g)
    ay_g = vrep("앵커Y", V_ANCHORY); dy_g = vrep("당김Y", V_DRAGY)
    gy = op("operator_subtract", ay_g, dy_g)
    g_pull = b_gotoxy(bs, gx, gy)
    w_pull = b_wait(bs, 0.01)
    chain([(set_dragx, bs[set_dragx]), (set_dragy, bs[set_dragy]), (set_mag, bs[set_mag]),
           (if_clamp, bs[if_clamp]), (if_ang, bs[if_ang]), (g_pull, bs[g_pull]), (w_pull, bs[w_pull])])
    md_ru = b_mousedown(bs)
    not_md = gen(); bs[not_md] = mk("operator_not", inputs={"OPERAND": [2, md_ru]})
    bs[md_ru]["parent"] = not_md
    ru_pull = b_repeat_until(bs, not_md, set_dragx)

    # after release: 드래그중=0 ; if 당김크기>4 → 발사 ; go to 앵커 복귀
    set_drag0 = b_setvar(bs, "드래그중", V_DRAGGING, 0)
    mag_rel = vrep("당김크기", V_DRAGMAG)
    cond_valid = cmp_op("operator_gt", mag_rel, 4)
    bc_fire = b_broadcast(bs, "발사", BR_FIRE)
    if_fire = b_if(bs, cond_valid, bc_fire)
    ax_r2 = vrep("앵커X", V_ANCHORX); ay_r2 = vrep("앵커Y", V_ANCHORY)
    g_back = b_gotoxy(bs, ax_r2, ay_r2)

    # start drag: 드래그중=1 ; play stretch ; repeat until ...
    set_drag1 = b_setvar(bs, "드래그중", V_DRAGGING, 1)
    sh_str_h, sh_str_t = b_sound(bs, 0, "stretch")
    chain([(set_drag1, bs[set_drag1]), (sh_str_h, bs[sh_str_h]), (sh_str_t, bs[sh_str_t]),
           (ru_pull, bs[ru_pull]),
           (set_drag0, bs[set_drag0]), (if_fire, bs[if_fire]), (g_back, bs[g_back])])

    # if (mousedown and touching mouse-pointer)
    md1 = b_mousedown(bs)
    tc_mouse = b_touching(bs, "_mouse_")
    cond_grab = bool_op("operator_and", md1, tc_mouse)
    if_grab = b_if(bs, cond_grab, set_drag1)

    # outer guard: if 게임상태=1  (★연사: 비행중 잠금 제거 — 공중에 포탄이 있어도 계속 당겨 쏨)
    state_r = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_r, 1)
    if_ready = b_if(bs, cond_play, if_grab)
    w_outer = b_wait(bs, 0.02)
    chain([(if_ready, bs[if_ready]), (w_outer, bs[w_outer])])
    fe = b_forever(bs, if_ready)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    add_comment(bs, comments, if_grab,
        "🎯 발사체를 마우스로 눌러 당기면 당긴 반대 방향으로 날아가요.\n"
        "떨어지는 적의 '앞'(도착할 자리)을 겨눠 맞혀요 — 이동표적 리드 사격!",
        x=560, y=-40, w=320, h=140)
    add_comment(bs, comments, set_dragx,
        "↗️ 당김을 옆(당김X)·위(당김Y)로 나눠요 — 이게 곧 속도의 X·Y 성분!\n"
        "대각선 45°로 당기면 가장 멀리 날아가요(바람 0). "
        "너무 멀리 당겨도 '최대당김거리'로 힘이 고정돼요(클램프).",
        x=560, y=200, w=320, h=160)

    return bs, comments

# ============================================================
#  당김선 (band) — 앵커↔발사체 고무줄 (펜)
# ============================================================
def build_band_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발: hide ; pen size 5 ; pen color 갈색
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    ps = b_pen_size(bs, 5)
    pc = b_pen_color(bs, "#8D5524")   # 갈색 고무줄
    chain([(h, bs[h]), (hi, bs[hi]), (ps, bs[ps]), (pc, bs[pc])])

    # (B) 게임시작 → forever { erase all ; if 드래그중=1 { 앵커→당겨진위치 선 } }
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    erase = b_pen(bs, "pen_clear")
    # goto 앵커 ; pen down ; goto (앵커-당김) ; pen up
    ax_r = vrep("앵커X", V_ANCHORX); ay_r = vrep("앵커Y", V_ANCHORY)
    g1 = b_gotoxy(bs, ax_r, ay_r)
    pdn = b_pen(bs, "pen_penDown")
    ax_g = vrep("앵커X", V_ANCHORX); dx_g = vrep("당김X", V_DRAGX)
    gx = op("operator_subtract", ax_g, dx_g)
    ay_g = vrep("앵커Y", V_ANCHORY); dy_g = vrep("당김Y", V_DRAGY)
    gy = op("operator_subtract", ay_g, dy_g)
    g2 = b_gotoxy(bs, gx, gy)
    pup = b_pen(bs, "pen_penUp")
    chain([(g1, bs[g1]), (pdn, bs[pdn]), (g2, bs[g2]), (pup, bs[pup])])
    drag_r = vrep("드래그중", V_DRAGGING)
    cond_drag = cmp_op("operator_equals", drag_r, 1)
    if_drag = b_if(bs, cond_drag, g1)
    w = b_wait(bs, 0.02)
    chain([(erase, bs[erase]), (if_drag, bs[if_drag]), (w, bs[w])])
    fe = b_forever(bs, erase)
    chain([(hb, bs[hb]), (fe, bs[fe])])
    return bs, comments

# ============================================================
#  궤적펜 (trajectory dry-run) — 실제 포탄과 동일 공식으로 점선 미리보기
# ============================================================
def build_traj_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발: hide ; pen size 3 ; pen color 흰
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    ps = b_pen_size(bs, 3)
    pc = b_pen_color(bs, "#FFFFFF")
    chain([(h, bs[h]), (hi, bs[hi]), (ps, bs[ps]), (pc, bs[pc])])

    # (B) 게임시작 → forever { erase all ; if 게임상태=1 and 드래그중=1 { dry-run 점선 } }
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    erase = b_pen(bs, "pen_clear")

    # dry-run body:
    #  미리X=앵커X ; 미리Y=앵커Y ; 미리VX=당김X*발사력배율 ; 미리VY=당김Y*발사력배율
    ax_r = vrep("앵커X", V_ANCHORX)
    set_px = b_setvar(bs, "미리X", V_PREX, ax_r)
    ay_r = vrep("앵커Y", V_ANCHORY)
    set_py = b_setvar(bs, "미리Y", V_PREY, ay_r)
    dx_r = vrep("당김X", V_DRAGX); pow_r = vrep("발사력배율", V_POWMUL)
    vx0 = op("operator_multiply", dx_r, pow_r)
    set_pvx = b_setvar(bs, "미리VX", V_PREVX, vx0)
    dy_r = vrep("당김Y", V_DRAGY); pow_r2 = vrep("발사력배율", V_POWMUL)
    vy0 = op("operator_multiply", dy_r, pow_r2)
    set_pvy = b_setvar(bs, "미리VY", V_PREVY, vy0)
    set_i0 = b_setvar(bs, "팝업자리", V_POPPOS, 0)   # 재사용: dry-run 루프 인덱스
    # pen up ; go to (미리X,미리Y) ; pen down
    px_r = vrep("미리X", V_PREX); py_r = vrep("미리Y", V_PREY)
    pup0 = b_pen(bs, "pen_penUp")
    g0 = b_gotoxy(bs, px_r, py_r)
    pdn0 = b_pen(bs, "pen_penDown")

    # repeat 미리보기점수:
    #   미리VY -= 중력 ; 미리VX += 바람 ; 미리X += 미리VX ; 미리Y += 미리VY ; i+=1
    #   if (i mod 미리보기간격)=0 → penUp;goto;penDown else penUp;goto
    #   if 미리Y<지면Y or abs(미리X)>착탄허용밖 → (연출: 안 그림, 남은 루프는 화면밖이라 무해)
    grav_r = vrep("중력", V_GRAVITY)
    neg_grav = op("operator_subtract", 0, grav_r)
    chg_pvy = b_changevar(bs, "미리VY", V_PREVY, neg_grav)
    wind_r = vrep("바람", V_WIND)
    chg_pvx = b_changevar(bs, "미리VX", V_PREVX, wind_r)
    pvx_r = vrep("미리VX", V_PREVX)
    chg_px = b_changevar(bs, "미리X", V_PREX, pvx_r)
    pvy_r = vrep("미리VY", V_PREVY)
    chg_py = b_changevar(bs, "미리Y", V_PREY, pvy_r)
    inc_i = b_changevar(bs, "팝업자리", V_POPPOS, 1)
    # 점 찍기 여부: i mod 미리보기간격 = 0
    i_r = vrep("팝업자리", V_POPPOS); pregap_r = vrep("미리보기간격", V_PREGAP)
    modv = op("operator_mod", i_r, pregap_r)
    cond_dot = cmp_op("operator_equals", modv, 0)
    px_a = vrep("미리X", V_PREX); py_a = vrep("미리Y", V_PREY)
    pupA = b_pen(bs, "pen_penUp"); gA = b_gotoxy(bs, px_a, py_a); pdnA = b_pen(bs, "pen_penDown")
    chain([(pupA, bs[pupA]), (gA, bs[gA]), (pdnA, bs[pdnA])])
    px_b = vrep("미리X", V_PREX); py_b = vrep("미리Y", V_PREY)
    pupB = b_pen(bs, "pen_penUp"); gB = b_gotoxy(bs, px_b, py_b)
    chain([(pupB, bs[pupB]), (gB, bs[gB])])
    if_dot = b_ifelse(bs, cond_dot, pupA, pupB)
    chain([(chg_pvy, bs[chg_pvy]), (chg_pvx, bs[chg_pvx]), (chg_px, bs[chg_px]),
           (chg_py, bs[chg_py]), (inc_i, bs[inc_i]), (if_dot, bs[if_dot])])
    presteps_r = vrep("미리보기점수", V_PRESTEPS)
    rep = b_repeat(bs, presteps_r, chg_pvy)

    chain([(set_px, bs[set_px]), (set_py, bs[set_py]), (set_pvx, bs[set_pvx]),
           (set_pvy, bs[set_pvy]), (set_i0, bs[set_i0]),
           (pup0, bs[pup0]), (g0, bs[g0]), (pdn0, bs[pdn0]), (rep, bs[rep])])

    state_r = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_r, 1)
    drag_r = vrep("드래그중", V_DRAGGING)
    cond_drag = cmp_op("operator_equals", drag_r, 1)
    cond_show = bool_op("operator_and", cond_play, cond_drag)
    if_show = b_if(bs, cond_show, set_px)
    w = b_wait(bs, 0.03)
    chain([(erase, bs[erase]), (if_show, bs[if_show]), (w, bs[w])])
    fe = b_forever(bs, erase)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    add_comment(bs, comments, if_show,
        "✏️ 당기는 동안 '지금 놓으면 어디로?'를 미리 점선으로 보여줘요.\n"
        "이 점선은 실제 포탄과 '똑같은 물리식'(중력·바람 누적)을 미리 돌려(dry-run) 그린 거예요. "
        "그래서 점선대로 정확히 날아가요! 폭탄 경로와 만나게 겨눠요.",
        x=560, y=-40, w=340, h=170)
    return bs, comments

# ============================================================
#  포탄 (cannonball) — 스포너 + 클론 본체 (실제 물리 비행)
# ============================================================
def build_ball_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    sz = b_setsize(bs, 100)
    orig0 = b_setvar(bs, "복제됨", V_BALLISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz]), (orig0, bs[orig0])])

    # (B) 발사 받으면 → 원본만, 포탄수<최대포탄수 일 때 클론 1개 (연사 상한)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    isc_r = vrep("복제됨", V_BALLISC)
    cond_orig = cmp_op("operator_equals", isc_r, 0)
    alive_r = vrep("포탄수", V_BALLALIVE); maxb_r = vrep("최대포탄수", V_MAXBALL)
    cond_room = cmp_op("operator_lt", alive_r, maxb_r)
    cclone = b_clone_self(bs)
    if_room = b_if(bs, cond_room, cclone)
    if_spawn = b_if(bs, cond_orig, if_room)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 물리 비행 (연사: 비행중 잠금 없음 / 관통: 남은관통 소진까지 비행)
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=400)
    set_isc1 = b_setvar(bs, "복제됨", V_BALLISC, 1)
    inc_alive = b_changevar(bs, "포탄수", V_BALLALIVE, 1)
    pier_r = vrep("관통횟수", V_PIERCE)
    set_pier = b_setvar(bs, "남은관통", V_BALLPIER, pier_r)   # 관통 카운터
    set_hcd0 = b_setvar(bs, "피격쿨", V_BALLHITCD, 0)
    life_r = vrep("포탄수명", V_BALLLIFE)
    set_life = b_setvar(bs, "남은수명", V_BALLLIFEC, life_r)  # 수명 타이머(안전망)
    ax_r = vrep("앵커X", V_ANCHORX); ay_r = vrep("앵커Y", V_ANCHORY)
    g0 = b_gotoxy(bs, ax_r, ay_r)
    swb = b_costume(bs, "ball")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    sh_fire_h, sh_fire_t = b_sound(bs, 0, "fire")
    # 속도X = 당김X * 발사력배율 ; 속도Y = 당김Y * 발사력배율 (공통②, 궤적펜과 동일)
    dx_r = vrep("당김X", V_DRAGX); pow_r = vrep("발사력배율", V_POWMUL)
    vx0 = op("operator_multiply", dx_r, pow_r)
    set_vx = b_setvar(bs, "속도X", V_BALLVX, vx0)
    dy_r = vrep("당김Y", V_DRAGY); pow_r2 = vrep("발사력배율", V_POWMUL)
    vy0 = op("operator_multiply", dy_r, pow_r2)
    set_vy = b_setvar(bs, "속도Y", V_BALLVY, vy0)

    # repeat until (y>190 or abs(x)>착탄허용밖) or (touching 라키투) or (남은관통<1) or 게임상태=0
    #   물리 적분(궤적펜과 동일 4식) → 관통 처리 → wait
    grav_r = vrep("중력", V_GRAVITY)
    neg_grav = op("operator_subtract", 0, grav_r)
    chg_vy = b_changevar(bs, "속도Y", V_BALLVY, neg_grav)
    wind_r = vrep("바람", V_WIND)
    chg_vx = b_changevar(bs, "속도X", V_BALLVX, wind_r)
    vx_r = vrep("속도X", V_BALLVX)
    chg_x = b_changexby(bs, vx_r)
    vy_r = vrep("속도Y", V_BALLVY)
    chg_y = b_changeyby(bs, vy_r)
    # ── 관통 히트: if touching 적 and 피격쿨=0 { 남은관통-=1 ; 피격쿨=4 } ──
    tc_enemy = b_touching(bs, "적")
    hcd_r = vrep("피격쿨", V_BALLHITCD)
    cond_hcd0 = cmp_op("operator_equals", hcd_r, 0)
    cond_pierce = bool_op("operator_and", tc_enemy, cond_hcd0)
    dec_pier = b_changevar(bs, "남은관통", V_BALLPIER, -1)
    set_hcd = b_setvar(bs, "피격쿨", V_BALLHITCD, 4)
    chain([(dec_pier, bs[dec_pier]), (set_hcd, bs[set_hcd])])
    if_pierce = b_if(bs, cond_pierce, dec_pier)
    # if 피격쿨>0 → -1
    hcd_r2 = vrep("피격쿨", V_BALLHITCD)
    cond_hcd_pos = cmp_op("operator_gt", hcd_r2, 0)
    dec_hcd = b_changevar(bs, "피격쿨", V_BALLHITCD, -1)
    if_hcd = b_if(bs, cond_hcd_pos, dec_hcd)
    dec_life = b_changevar(bs, "남은수명", V_BALLLIFEC, -1)   # 수명 카운트다운
    w_fly = b_wait(bs, 0.02)
    chain([(chg_vy, bs[chg_vy]), (chg_vx, bs[chg_vx]), (chg_x, bs[chg_x]),
           (chg_y, bs[chg_y]), (if_pierce, bs[if_pierce]), (if_hcd, bs[if_hcd]),
           (dec_life, bs[dec_life]), (w_fly, bs[w_fly])])
    # stop conditions
    yp = b_ypos(bs)
    cond_yhi = cmp_op("operator_gt", yp, 190)
    xp = b_xpos(bs); absx = b_abs(bs, xp)
    offx_r = vrep("착탄허용밖", V_OFFX)
    cond_offx = cmp_op("operator_gt", absx, offx_r)
    cond_out = bool_op("operator_or", cond_yhi, cond_offx)
    tc_lak = b_touching(bs, "라키투")
    pier_c = vrep("남은관통", V_BALLPIER)
    cond_spent = cmp_op("operator_lt", pier_c, 1)   # 관통 소진
    cond_end = bool_op("operator_or", tc_lak, cond_spent)
    cond_out2 = bool_op("operator_or", cond_out, cond_end)
    life_c = vrep("남은수명", V_BALLLIFEC)
    cond_expire = cmp_op("operator_lt", life_c, 1)   # ★수명 만료 안전망
    state_r = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_r, 0)
    cond_end2 = bool_op("operator_or", cond_expire, cond_over)
    cond_stop = bool_op("operator_or", cond_out2, cond_end2)
    ru = b_repeat_until(bs, cond_stop, chg_vy)

    # 폭발 연출 후 소멸 (포탄수-1)
    sw_boom = b_costume(bs, "boom")
    ch_sz = b_changesize(bs, -6)
    ch_gh = b_changeghost(bs, 16)
    w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = b_repeat(bs, 6, ch_sz)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    dec_alive = b_changevar(bs, "포탄수", V_BALLALIVE, -1)
    del_c = b_del_clone(bs)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (inc_alive, bs[inc_alive]),
           (set_pier, bs[set_pier]), (set_hcd0, bs[set_hcd0]), (set_life, bs[set_life]),
           (g0, bs[g0]), (swb, bs[swb]), (front, bs[front]), (show, bs[show]),
           (sh_fire_h, bs[sh_fire_h]), (sh_fire_t, bs[sh_fire_t]),
           (set_vx, bs[set_vx]), (set_vy, bs[set_vy]),
           (ru, bs[ru]), (sw_boom, bs[sw_boom]), (rep_an, bs[rep_an]),
           (hi2, bs[hi2]), (dec_alive, bs[dec_alive]), (del_c, bs[del_c])])

    add_comment(bs, comments, set_vx,
        "🚀 속도X = 당김X × 발사력배율 · 속도Y = 당김Y × 발사력배율\n"
        "매 틱: 속도Y −= 중력, 속도X += 바람, x += 속도X, y += 속도Y.\n"
        "궤적펜(점선)과 '완전히 같은 공식'이라 점선대로 정확히 날아가요!",
        x=560, y=-60, w=340, h=170)
    add_comment(bs, comments, if_pierce,
        "💥 관통샷: 포탄이 적 1기를 맞혀도 사라지지 않고 '남은관통'만 1 줄어요.\n"
        "관통횟수(기본 2) 만큼 여러 적을 뚫고 지나가요. 피격쿨로 같은 적을 여러 번 세지 않게 막아요. "
        "관통이 0이 되면 소멸!",
        x=560, y=200, w=340, h=160)
    return bs, comments

# ============================================================
#  폭탄 (bomb) — 낙하산 스포너 + 클론 본체
# ============================================================
def build_bomb_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = b_setsize(bs, 100)
    orig0 = b_setvar(bs, "복제됨", V_BOMBISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz]), (orig0, bs[orig0])])

    # (B) 폭탄생성 → 원본만 클론 1개
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWNBOMB]})
    isc_r = vrep("복제됨", V_BOMBISC)
    cond_orig = cmp_op("operator_equals", isc_r, 0)
    cclone = b_clone_self(bs)
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=400)
    set_isc1 = b_setvar(bs, "복제됨", V_BOMBISC, 1)
    inc_alive = b_changevar(bs, "적수", V_BOMBALIVE, 1)
    # 흔들기준X = pick random -200 to 200
    rx = gen(); bs[rx] = mk("operator_random", inputs={"FROM": num(-200), "TO": num(200)})
    set_basex = b_setvar(bs, "흔들기준X", V_BOMBBASEX, rx)
    # 흔들위상 = pick random 0 to 360
    rp = gen(); bs[rp] = mk("operator_random", inputs={"FROM": num(0), "TO": num(360)})
    set_phase = b_setvar(bs, "흔들위상", V_BOMBPHASE, rp)
    # 내낙하 = 낙하속도 + 처치수*난이도증가율 (공통③ 램프)
    kills_r = vrep("처치수", V_KILLS); ramp_r = vrep("난이도증가율", V_RAMP)
    ramp_term = op("operator_multiply", kills_r, ramp_r)
    fall_r = vrep("낙하속도", V_FALLSPD)
    fall_val = op("operator_add", fall_r, ramp_term)
    set_fall = b_setvar(bs, "내낙하", V_BOMBFALL, fall_val)
    basex_r = vrep("흔들기준X", V_BOMBBASEX)
    g0 = b_gotoxy(bs, basex_r, 170)
    swb = b_costume(bs, "monster")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")

    # forever body:
    body = []
    # 게임오버 정리
    state_go = vrep("게임상태", V_STATE)
    cond_go = cmp_op("operator_equals", state_go, 0)
    dec_alive_go = b_changevar(bs, "적수", V_BOMBALIVE, -1)
    del_go = b_del_clone(bs)
    chain([(dec_alive_go, bs[dec_alive_go]), (del_go, bs[del_go])])
    if_go = b_if(bs, cond_go, dec_alive_go)
    body.append((if_go, if_go))

    # 하강 + 좌우 흔들: 흔들위상+=4 ; x = 흔들기준X + 흔들폭*sin(흔들위상) ; y -= 내낙하
    inc_phase = b_changevar(bs, "흔들위상", V_BOMBPHASE, 4)
    sway_r = vrep("흔들폭", V_SWAY); phase_r = vrep("흔들위상", V_BOMBPHASE)
    sinv = b_mathop(bs, "sin", phase_r)
    swayterm = op("operator_multiply", sway_r, sinv)
    basex_r2 = vrep("흔들기준X", V_BOMBBASEX)
    xval = op("operator_add", basex_r2, swayterm)
    set_x = b_setx(bs, xval)
    fall_r2 = vrep("내낙하", V_BOMBFALL)
    neg_fall = op("operator_subtract", 0, fall_r2)
    chg_y = b_changeyby(bs, neg_fall)
    chain([(inc_phase, bs[inc_phase]), (set_x, bs[set_x]), (chg_y, bs[chg_y])])
    # ★ 다중 블록 span: head=inc_phase, tail=chg_y. body-chain 이 tail 을 다음으로 잇게
    #   (head, tail) 튜플로 넣어 set_x·chg_y 가 고아가 되지 않게 한다.
    body.append((inc_phase, chg_y))

    # 요격 판정: if touching 포탄
    tc_ball = b_touching(bs, "포탄")
    inc_combo = b_changevar(bs, "콤보수", V_COMBO, 1)
    # 콤보배수 = 콤보배수 * 콤보배율 ; if >콤보최대 → 콤보최대
    cx_r = vrep("콤보배수", V_COMBOX); cmul_r = vrep("콤보배율", V_COMBOMUL)
    newcx = op("operator_multiply", cx_r, cmul_r)
    set_cx = b_setvar(bs, "콤보배수", V_COMBOX, newcx)
    cx_r2 = vrep("콤보배수", V_COMBOX); ccap_r = vrep("콤보최대", V_COMBOCAP)
    cond_capped = cmp_op("operator_gt", cx_r2, ccap_r)
    ccap_r2 = vrep("콤보최대", V_COMBOCAP)
    set_cxcap = b_setvar(bs, "콤보배수", V_COMBOX, ccap_r2)
    if_cap = b_if(bs, cond_capped, set_cxcap)
    # 이번점수 = 폭탄점수 * 콤보배수 → 명중점수값 ; 점수 += ; 처치수 +=1
    bpt_r = vrep("요격점수", V_BOMBPT); cx_r3 = vrep("콤보배수", V_COMBOX)
    thisval = op("operator_multiply", bpt_r, cx_r3)
    set_popval = b_setvar(bs, "명중점수값", V_POPVAL, thisval)
    popval_r = vrep("명중점수값", V_POPVAL)
    inc_score = b_changevar(bs, "점수", V_SCORE, popval_r)
    inc_kills = b_changevar(bs, "처치수", V_KILLS, 1)
    # 효과음: pop + combo(콤보수 기반 pitch)
    sh_pop_h, sh_pop_t = b_sound(bs, 0, "pop")
    combo_pitch = vrep("콤보수", V_COMBO)
    pitch_mul = op("operator_multiply", combo_pitch, 20)
    sh_combo_h, sh_combo_t = b_sound_pitchvar(bs, pitch_mul, "combo")
    # 팝업 세팅 + 방송
    set_popkind = b_setvar(bs, "팝업종류", V_POPKIND, 1)  # 금색
    xp = b_xpos(bs); set_popx = b_setvar(bs, "명중점수x", V_POPX, xp)
    yp = b_ypos(bs); set_popy = b_setvar(bs, "명중점수y", V_POPY, yp)
    bc_pop = b_broadcast(bs, "점수표시", BR_POP)
    # 폭발 연출 + 폭탄수-1 + 삭제
    sw_boom = b_costume(bs, "boom")
    ch_sz = b_changesize(bs, 8); ch_gh = b_changeghost(bs, 20); w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = b_repeat(bs, 6, ch_sz)
    dec_alive = b_changevar(bs, "적수", V_BOMBALIVE, -1)
    del_k = b_del_clone(bs)
    chain([(inc_combo, bs[inc_combo]), (set_cx, bs[set_cx]), (if_cap, bs[if_cap]),
           (set_popval, bs[set_popval]), (inc_score, bs[inc_score]), (inc_kills, bs[inc_kills]),
           (sh_pop_h, bs[sh_pop_h]), (sh_pop_t, bs[sh_pop_t]),
           (sh_combo_h, bs[sh_combo_h]), (sh_combo_t, bs[sh_combo_t]),
           (set_popkind, bs[set_popkind]), (set_popx, bs[set_popx]), (set_popy, bs[set_popy]),
           (bc_pop, bs[bc_pop]), (sw_boom, bs[sw_boom]), (rep_an, bs[rep_an]),
           (dec_alive, bs[dec_alive]), (del_k, bs[del_k])])
    if_intercept = b_if(bs, tc_ball, inc_combo)
    body.append((if_intercept, if_intercept))

    # 꽃밭 도달(놓침): if y < 지면Y
    #   파괴꽃X = x ; 꽃최소거리=99999 ; broadcast_and_wait 꽃거리측정(각 살아있는 꽃이 최소 갱신)
    #   ; broadcast_and_wait 꽃파괴(최소거리인 꽃 1개만 시들, 꽃최소거리=-1 로 중복 방지)
    yp2 = b_ypos(bs); groundy_r = vrep("지면Y", V_GROUNDY)
    cond_ground = cmp_op("operator_lt", yp2, groundy_r)
    xp2 = b_xpos(bs); set_kfx = b_setvar(bs, "파괴꽃X", V_KILLFLOWERX, xp2)
    set_mind = b_setvar(bs, "꽃최소거리", V_FLOWERMIND, 99999)
    bcw_measure = b_broadcast_wait(bs, "꽃거리측정", BR_MEASURE)
    bcw_kill = b_broadcast_wait(bs, "꽃파괴", BR_KILLFLOWER)
    # 콤보 리셋
    set_combo0 = b_setvar(bs, "콤보수", V_COMBO, 0)
    set_cx1 = b_setvar(bs, "콤보배수", V_COMBOX, 1)
    sw_boom2 = b_costume(bs, "boom")
    ch_gh2 = b_changeghost(bs, 25); w_an2 = b_wait(bs, 0.02)
    chain([(ch_gh2, bs[ch_gh2]), (w_an2, bs[w_an2])])
    rep_an2 = b_repeat(bs, 4, ch_gh2)
    dec_alive2 = b_changevar(bs, "적수", V_BOMBALIVE, -1)
    del_m = b_del_clone(bs)
    chain([(set_kfx, bs[set_kfx]), (set_mind, bs[set_mind]),
           (bcw_measure, bs[bcw_measure]), (bcw_kill, bs[bcw_kill]),
           (set_combo0, bs[set_combo0]),
           (set_cx1, bs[set_cx1]), (sw_boom2, bs[sw_boom2]), (rep_an2, bs[rep_an2]),
           (dec_alive2, bs[dec_alive2]), (del_m, bs[del_m])])
    if_ground = b_if(bs, cond_ground, set_kfx)
    body.append((if_ground, if_ground))

    # 라키투 전멸 보너스: if 전멸신호=1
    wipe_r = vrep("전멸신호", V_WIPE)
    cond_wipe = cmp_op("operator_equals", wipe_r, 1)
    inc_kills_w = b_changevar(bs, "처치수", V_KILLS, 1)
    sh_pop_w_h, sh_pop_w_t = b_sound(bs, 0, "pop")
    sw_boom3 = b_costume(bs, "boom")
    ch_sz3 = b_changesize(bs, 8); ch_gh3 = b_changeghost(bs, 25); w_an3 = b_wait(bs, 0.02)
    chain([(ch_sz3, bs[ch_sz3]), (ch_gh3, bs[ch_gh3]), (w_an3, bs[w_an3])])
    rep_an3 = b_repeat(bs, 4, ch_sz3)
    dec_alive3 = b_changevar(bs, "적수", V_BOMBALIVE, -1)
    del_w = b_del_clone(bs)
    chain([(inc_kills_w, bs[inc_kills_w]), (sh_pop_w_h, bs[sh_pop_w_h]), (sh_pop_w_t, bs[sh_pop_w_t]),
           (sw_boom3, bs[sw_boom3]),
           (rep_an3, bs[rep_an3]), (dec_alive3, bs[dec_alive3]), (del_w, bs[del_w])])
    if_wipe = b_if(bs, cond_wipe, inc_kills_w)
    body.append((if_wipe, if_wipe))

    w_body = b_wait(bs, 0.02)
    # body 는 (head, tail) span 리스트. 각 span 의 tail 을 다음 span 의 head 로 잇는다
    #  (다중 블록 span=낙하 이동 의 꼬리 chg_y 가 다음으로 정상 연결되도록).
    for i in range(len(body) - 1):
        bs[body[i][1]]["next"] = body[i + 1][0]
        bs[body[i + 1][0]]["parent"] = body[i][1]
    bs[body[-1][1]]["next"] = w_body
    bs[w_body]["parent"] = body[-1][1]
    fe_body = b_forever(bs, body[0][0])
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (inc_alive, bs[inc_alive]),
           (set_basex, bs[set_basex]), (set_phase, bs[set_phase]), (set_fall, bs[set_fall]),
           (g0, bs[g0]), (swb, bs[swb]), (front, bs[front]), (show, bs[show]),
           (fe_body, bs[fe_body])])

    add_comment(bs, comments, inc_phase,
        "☂️ 적은 낙하산 타고 천천히 내려오며 좌우로 흔들려요.\n"
        "x = 흔들기준X + 흔들폭 × sin(흔들위상). 흔들폭을 키우면 더 지그재그로 흔들려 맞히기 어려워요!",
        x=560, y=-40, w=330, h=140)
    add_comment(bs, comments, if_intercept,
        "🔥 연속으로 맞히면 콤보배수가 배로 뛰어요(1→2→4→8…)!\n"
        "점수 = 요격점수 × 콤보배수. 놓치면(적이 꽃에 닿으면) 콤보가 0으로 리셋돼요.",
        x=560, y=200, w=330, h=150)
    return bs, comments

# ============================================================
#  라키투 (lakitu) — 특수 적 스포너 + 클론 본체
# ============================================================
def build_lakitu_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = b_setsize(bs, 100)
    orig0 = b_setvar(bs, "복제됨", V_LAKISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz]), (orig0, bs[orig0])])

    # (B) 라키투생성 → 원본만 클론 1개
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["라키투생성", BR_SPAWNLAK]})
    isc_r = vrep("복제됨", V_LAKISC)
    cond_orig = cmp_op("operator_equals", isc_r, 0)
    cclone = b_clone_self(bs)
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=400)
    set_isc1 = b_setvar(bs, "복제됨", V_LAKISC, 1)
    # 진행방향 = (pick random 0 to 1)*2 - 1
    rdir = gen(); bs[rdir] = mk("operator_random", inputs={"FROM": num(0), "TO": num(1)})
    dir2 = op("operator_multiply", rdir, 2)
    dirv = op("operator_subtract", dir2, 1)
    set_dir = b_setvar(bs, "진행방향", V_LAKDIR, dirv)
    # if 진행방향=1 → go x:-240 y:rand(60,140) else x:240 ...
    dir_r = vrep("진행방향", V_LAKDIR)
    cond_r = cmp_op("operator_equals", dir_r, 1)
    ry1 = gen(); bs[ry1] = mk("operator_random", inputs={"FROM": num(60), "TO": num(140)})
    g_l = b_gotoxy(bs, -240, ry1)
    ry2 = gen(); bs[ry2] = mk("operator_random", inputs={"FROM": num(60), "TO": num(140)})
    g_r = b_gotoxy(bs, 240, ry2)
    if_side = b_ifelse(bs, cond_r, g_l, g_r)
    swl = b_costume(bs, "lakitu")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    sh_lak_h, sh_lak_t = b_sound(bs, 0, "lakitu")

    # repeat until (abs(x)>235 or touching 포탄 or 게임상태=0):
    #   x += 라키투속도 * 진행방향 ; wait
    lspd_r = vrep("라키투속도", V_LAKITUSPD); dir_r2 = vrep("진행방향", V_LAKDIR)
    stepx = op("operator_multiply", lspd_r, dir_r2)
    chg_x = b_changexby(bs, stepx)
    w_mv = b_wait(bs, 0.02)
    chain([(chg_x, bs[chg_x]), (w_mv, bs[w_mv])])
    xp = b_xpos(bs); absx = b_abs(bs, xp)
    cond_offx = cmp_op("operator_gt", absx, 235)
    tc_ball = b_touching(bs, "포탄")
    cond_a = bool_op("operator_or", cond_offx, tc_ball)
    state_r = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", state_r, 0)
    cond_stop = bool_op("operator_or", cond_a, cond_over)
    ru = b_repeat_until(bs, cond_stop, chg_x)

    # if touching 포탄 → 전멸 보너스
    tc_ball2 = b_touching(bs, "포탄")
    sh_clear_h, sh_clear_t = b_sound(bs, 0, "clear")
    # 명중점수값 = 폭탄점수 * 콤보최대 (큰 보너스)
    bpt_r = vrep("요격점수", V_BOMBPT); ccap_r = vrep("콤보최대", V_COMBOCAP)
    bonus = op("operator_multiply", bpt_r, ccap_r)
    set_popval = b_setvar(bs, "명중점수값", V_POPVAL, bonus)
    popval_r = vrep("명중점수값", V_POPVAL)
    inc_score = b_changevar(bs, "점수", V_SCORE, popval_r)
    xp3 = b_xpos(bs); set_popx = b_setvar(bs, "명중점수x", V_POPX, xp3)
    yp3 = b_ypos(bs); set_popy = b_setvar(bs, "명중점수y", V_POPY, yp3)
    set_popkind = b_setvar(bs, "팝업종류", V_POPKIND, 1)
    bc_pop = b_broadcast(bs, "점수표시", BR_POP)
    set_wipe1 = b_setvar(bs, "전멸신호", V_WIPE, 1)
    sw_boom = b_costume(bs, "boom")
    ch_sz = b_changesize(bs, 10); ch_gh = b_changeghost(bs, 14); w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = b_repeat(bs, 8, ch_sz)
    w_wipe = b_wait(bs, 0.1)
    set_wipe0 = b_setvar(bs, "전멸신호", V_WIPE, 0)
    chain([(sh_clear_h, bs[sh_clear_h]), (sh_clear_t, bs[sh_clear_t]),
           (set_popval, bs[set_popval]), (inc_score, bs[inc_score]),
           (set_popx, bs[set_popx]), (set_popy, bs[set_popy]), (set_popkind, bs[set_popkind]),
           (bc_pop, bs[bc_pop]), (set_wipe1, bs[set_wipe1]), (sw_boom, bs[sw_boom]),
           (rep_an, bs[rep_an]), (w_wipe, bs[w_wipe]), (set_wipe0, bs[set_wipe0])])
    if_hit = b_if(bs, tc_ball2, sh_clear_h)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    del_c = b_del_clone(bs)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_dir, bs[set_dir]),
           (if_side, bs[if_side]), (swl, bs[swl]), (front, bs[front]), (show, bs[show]),
           (sh_lak_h, bs[sh_lak_h]), (sh_lak_t, bs[sh_lak_t]),
           (ru, bs[ru]), (if_hit, bs[if_hit]),
           (hi2, bs[hi2]), (del_c, bs[del_c])])

    add_comment(bs, comments, hb,
        "☁️ 가끔 라키투(구름 탄 적)가 화면을 가로질러 지나가요.\n"
        "맞히면 화면의 적이 전부 펑! 터지고 큰 보너스 점수를 받아요(전멸신호로 폭탄들에게 알려요). "
        "라키투확률을 낮추면(40→10) 더 자주 나와요.",
        x=560, y=-40, w=340, h=160)
    return bs, comments

# ============================================================
#  꽃 (flower) — 라이프 스포너 + 클론 본체 (가장 가까운 꽃 1개만 파괴, 2패스)
# ============================================================
def build_flower_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = b_setsize(bs, 100)
    orig0 = b_setvar(bs, "복제됨", V_FLOWERISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz]), (orig0, bs[orig0])])

    # (B) 꽃생성 → 원본이 꽃X 리스트 훑어 클론 배치 (다음꽃X 채널로 좌표 전달)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["꽃생성", BR_FLOWER]})
    isc_r = vrep("복제됨", V_FLOWERISC)
    cond_orig = cmp_op("operator_equals", isc_r, 0)
    set_i1 = b_setvar(bs, "임시i", V_TMPI, 1)
    i_r = vrep("임시i", V_TMPI)
    itemx = b_item_of(bs, "꽃X", L_FLOWERX, i_r)
    set_nextx = b_setvar(bs, "다음꽃X", V_FLOWERNEXTX, itemx)
    cclone = b_clone_self(bs)
    w_c = b_wait(bs, 0.02)
    inc_i = b_changevar(bs, "임시i", V_TMPI, 1)
    chain([(set_nextx, bs[set_nextx]), (cclone, bs[cclone]), (w_c, bs[w_c]), (inc_i, bs[inc_i])])
    len_fx = b_length_of(bs, "꽃X", L_FLOWERX)
    rep = b_repeat(bs, len_fx, set_nextx)
    chain([(set_i1, bs[set_i1]), (rep, bs[rep])])
    if_spawn = b_if(bs, cond_orig, set_i1)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 시작
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=400)
    set_isc1 = b_setvar(bs, "복제됨", V_FLOWERISC, 1)
    nextx_r = vrep("다음꽃X", V_FLOWERNEXTX)
    set_myx = b_setvar(bs, "내X", V_FLOWERMYX, nextx_r)
    set_alive1 = b_setvar(bs, "살아있음", V_FLOWERALIVE, 1)
    myx_r = vrep("내X", V_FLOWERMYX); groundy_r = vrep("지면Y", V_GROUNDY)
    g0 = b_gotoxy(bs, myx_r, groundy_r)
    swf = b_costume(bs, "flower")
    show = gen(); bs[show] = mk("looks_show")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_myx, bs[set_myx]),
           (set_alive1, bs[set_alive1]), (g0, bs[g0]), (swf, bs[swf]), (show, bs[show])])

    # (D1) 꽃거리측정 (2패스 1단계): if 복제됨=1 and 살아있음=1:
    #        내거리 = abs(내X - 파괴꽃X) ; if 내거리 < 꽃최소거리 → 꽃최소거리 = 내거리
    hd1 = gen(); bs[hd1] = mk("event_whenbroadcastreceived", top=True, x=340, y=200,
        fields={"BROADCAST_OPTION": ["꽃거리측정", BR_MEASURE]})
    isc_m = vrep("복제됨", V_FLOWERISC)
    cond_clone_m = cmp_op("operator_equals", isc_m, 1)
    alive_m = vrep("살아있음", V_FLOWERALIVE)
    cond_alive_m = cmp_op("operator_equals", alive_m, 1)
    cond_active_m = bool_op("operator_and", cond_clone_m, cond_alive_m)
    myx_m = vrep("내X", V_FLOWERMYX); kfx_m = vrep("파괴꽃X", V_KILLFLOWERX)
    diff_m = op("operator_subtract", myx_m, kfx_m)
    absd_m = b_abs(bs, diff_m)
    mind_m = vrep("꽃최소거리", V_FLOWERMIND)
    cond_closer = cmp_op("operator_lt", absd_m, mind_m)
    # 꽃최소거리 = abs(내X - 파괴꽃X)  (다시 계산)
    myx_m2 = vrep("내X", V_FLOWERMYX); kfx_m2 = vrep("파괴꽃X", V_KILLFLOWERX)
    diff_m2 = op("operator_subtract", myx_m2, kfx_m2)
    absd_m2 = b_abs(bs, diff_m2)
    set_mind = b_setvar(bs, "꽃최소거리", V_FLOWERMIND, absd_m2)
    if_closer = b_if(bs, cond_closer, set_mind)
    if_active_m = b_if(bs, cond_active_m, if_closer)
    chain([(hd1, bs[hd1]), (if_active_m, bs[if_active_m])])

    # (D2) 꽃파괴 (2패스 2단계): if 복제됨=1 and 살아있음=1 and abs(내X-파괴꽃X)=꽃최소거리:
    #        살아있음=0 ; wilt ; wilt음 ; 꽃남음-1 ; 꽃최소거리=-1(중복 파괴 방지)
    hd2 = gen(); bs[hd2] = mk("event_whenbroadcastreceived", top=True, x=340, y=400,
        fields={"BROADCAST_OPTION": ["꽃파괴", BR_KILLFLOWER]})
    isc_k = vrep("복제됨", V_FLOWERISC)
    cond_clone_k = cmp_op("operator_equals", isc_k, 1)
    alive_k = vrep("살아있음", V_FLOWERALIVE)
    cond_alive_k = cmp_op("operator_equals", alive_k, 1)
    myx_k = vrep("내X", V_FLOWERMYX); kfx_k = vrep("파괴꽃X", V_KILLFLOWERX)
    diff_k = op("operator_subtract", myx_k, kfx_k)
    absd_k = b_abs(bs, diff_k)
    mind_k = vrep("꽃최소거리", V_FLOWERMIND)
    cond_ismin = cmp_op("operator_equals", absd_k, mind_k)
    cond_ck_a = bool_op("operator_and", cond_clone_k, cond_alive_k)
    cond_kill = bool_op("operator_and", cond_ck_a, cond_ismin)
    set_alive0 = b_setvar(bs, "살아있음", V_FLOWERALIVE, 0)
    sww = b_costume(bs, "wilt")
    sh_wilt_h, sh_wilt_t = b_sound(bs, 0, "wilt")
    dec_left = b_changevar(bs, "꽃남음", V_FLOWERLEFT, -1)
    set_mind_neg = b_setvar(bs, "꽃최소거리", V_FLOWERMIND, -1)  # 동률 시 중복 파괴 방지
    chain([(set_alive0, bs[set_alive0]), (sww, bs[sww]),
           (sh_wilt_h, bs[sh_wilt_h]), (sh_wilt_t, bs[sh_wilt_t]),
           (dec_left, bs[dec_left]), (set_mind_neg, bs[set_mind_neg])])
    if_kill = b_if(bs, cond_kill, set_alive0)
    chain([(hd2, bs[hd2]), (if_kill, bs[if_kill])])

    add_comment(bs, comments, hd1,
        "🌸 꽃은 라이프예요. 폭탄이 꽃밭에 닿으면 '가장 가까운 살아있는 꽃 1개'만 시들어요.\n"
        "각 꽃이 폭탄과의 거리를 재서(1패스) 최솟값을 찾고, 그 거리인 꽃만 파괴돼요(2패스) — "
        "정확히 1개! 꽃이 다 지면 게임오버.",
        x=620, y=120, w=340, h=170)
    return bs, comments

# ============================================================
#  숫자팝업 (floating score) — 코스튬 0~9 흰/금, say 미사용
# ============================================================
def build_popup_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_POPISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 점수표시 받으면 자릿수만큼 클론 생성 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["점수표시", BR_POP]})
    isc_r = vrep("복제됨", V_POPISC)
    cond_orig = cmp_op("operator_equals", isc_r, 0)
    # 팝업글자수 = length of 명중점수값
    pv_r = vrep("명중점수값", V_POPVAL)
    len_b = gen(); bs[len_b] = mk("operator_length", inputs={"STRING": slot(pv_r)})
    bs[pv_r]["parent"] = len_b
    set_len = b_setvar(bs, "팝업글자수", V_POPLEN, len_b)
    set_pos1 = b_setvar(bs, "팝업자리", V_POPPOS, 1)
    # repeat 팝업글자수 { 팝업숫자 = letter 팝업자리 of 명중점수값 ;
    #   팝업오프셋 = (팝업자리-1)*13 - (팝업글자수-1)*6.5 ; clone ; 팝업자리+1 ; wait }
    pos_r = vrep("팝업자리", V_POPPOS); pv_r2 = vrep("명중점수값", V_POPVAL)
    letter_b = gen(); bs[letter_b] = mk("operator_letter_of",
        inputs={"LETTER": slot(pos_r), "STRING": slot(pv_r2)})
    bs[pos_r]["parent"] = letter_b; bs[pv_r2]["parent"] = letter_b
    set_digit = b_setvar(bs, "팝업숫자", V_POPDIGIT, letter_b)
    pos_r2 = vrep("팝업자리", V_POPPOS)
    pos_m1 = op("operator_subtract", pos_r2, 1)
    off_left = op("operator_multiply", pos_m1, 13)
    len_r = vrep("팝업글자수", V_POPLEN)
    len_m1 = op("operator_subtract", len_r, 1)
    off_ctr = op("operator_multiply", len_m1, 6.5)
    off_final = op("operator_subtract", off_left, off_ctr)
    set_off = b_setvar(bs, "팝업오프셋", V_POPOFF, off_final)
    cclone = b_clone_self(bs)
    inc_pos = b_changevar(bs, "팝업자리", V_POPPOS, 1)
    w_sp = b_wait(bs, 0.03)
    chain([(set_digit, bs[set_digit]), (set_off, bs[set_off]), (cclone, bs[cclone]),
           (inc_pos, bs[inc_pos]), (w_sp, bs[w_sp])])
    len_rep = vrep("팝업글자수", V_POPLEN)
    rep = b_repeat(bs, len_rep, set_digit)
    chain([(set_len, bs[set_len]), (set_pos1, bs[set_pos1]), (rep, bs[rep])])
    if_spawn = b_if(bs, cond_orig, set_len)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 코스튬 선택(흰/금) → 떠오르며 페이드 후 삭제
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=400)
    set_isc1 = b_setvar(bs, "복제됨", V_POPISC, 1)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    szb = b_setsize(bs, 100)
    # 코스튬 = (팝업종류 * 10) + 팝업숫자 + 1  (흰=0*10 → costumes 1~10, 금=1*10 → 11~20)
    kind_r = vrep("팝업종류", V_POPKIND)
    kind10 = op("operator_multiply", kind_r, 10)
    dig_r = vrep("팝업숫자", V_POPDIGIT)
    kd = op("operator_add", kind10, dig_r)
    cidx = op("operator_add", kd, 1)
    sw_num = gen(); bs[sw_num] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(cidx)})
    bs[cidx]["parent"] = sw_num
    # goto (명중점수x + 팝업오프셋, 명중점수y)
    px_r = vrep("명중점수x", V_POPX); off_r = vrep("팝업오프셋", V_POPOFF)
    xg = op("operator_add", px_r, off_r)
    py_r = vrep("명중점수y", V_POPY)
    g = b_gotoxy(bs, xg, py_r)
    clr_gh = b_setghost(bs, 0)
    show = gen(); bs[show] = mk("looks_show")
    ch_y = b_changeyby(bs, 4)
    ch_gh = b_changeghost(bs, 8)
    w_an = b_wait(bs, 0.02)
    chain([(ch_y, bs[ch_y]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = b_repeat(bs, 12, ch_y)
    del_c = b_del_clone(bs)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (front, bs[front]), (szb, bs[szb]),
           (sw_num, bs[sw_num]), (g, bs[g]), (clr_gh, bs[clr_gh]), (show, bs[show]),
           (rep_an, bs[rep_an]), (del_c, bs[del_c])])
    return bs, comments

# ============================================================
#  배너 (banner) — 게임오버 + 최고기록 (fish-tank 패턴)
# ============================================================
def build_banner_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발: hide ; 중앙
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = b_gotoxy(bs, 0, 0)
    szb = b_setsize(bs, 100)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (szb, bs[szb]), (front, bs[front])])

    # (B) 게임오버 받으면: 게임상태=0 ; if 점수>최고점수 → 최고점수=점수·newrecord·record음
    #     else → gameover·gameover음 ; show
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임오버", BR_GAMEOVER]})
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    score_r = vrep("점수", V_SCORE); best_r = vrep("최고점수", V_BEST)
    cond_new = cmp_op("operator_gt", score_r, best_r)
    score_r2 = vrep("점수", V_SCORE)
    set_best = b_setvar(bs, "최고점수", V_BEST, score_r2)
    sw_new = b_costume(bs, "newrecord")
    sh_rec_h, sh_rec_t = b_sound(bs, 0, "record")
    chain([(set_best, bs[set_best]), (sw_new, bs[sw_new]),
           (sh_rec_h, bs[sh_rec_h]), (sh_rec_t, bs[sh_rec_t])])
    sw_go = b_costume(bs, "gameover")
    sh_go_h, sh_go_t = b_sound(bs, 0, "gameover")
    chain([(sw_go, bs[sw_go]), (sh_go_h, bs[sh_go_h]), (sh_go_t, bs[sh_go_t])])
    if_rec = b_ifelse(bs, cond_new, set_best, sw_go)
    show = gen(); bs[show] = mk("looks_show")
    chain([(hb, bs[hb]), (set_st0, bs[set_st0]), (if_rec, bs[if_rec]), (show, bs[show])])

    add_comment(bs, comments, if_rec,
        "🏆 꽃이 다 지면 게임오버! 이번 점수가 최고점수보다 크면 신기록으로 갱신해요.\n"
        "최고점수는 초록 깃발을 다시 눌러도 리셋되지 않아요(세션 유지) — '한 판만 더!' 도전.",
        x=560, y=-40, w=340, h=150)
    return bs, comments

# ============================================================
#  ASSEMBLE
# ============================================================
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)
    if not os.path.isdir(ASSETS): os.makedirs(ASSETS)

    def save_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f: f.write(svg)
        return m

    bg_md5     = save_svg(BG_SVG)
    frame_md5  = save_svg(FRAME_SVG)
    ball_md5   = save_svg(BALL_SVG)
    boom_md5   = save_svg(BOOM_SVG)
    monster_md5= save_svg(MONSTER_SVG)
    lakitu_md5 = save_svg(LAKITU_SVG)
    flower_md5 = save_svg(FLOWER_SVG)
    wilt_md5   = save_svg(WILT_SVG)
    go_md5     = save_svg(GAMEOVER_SVG)
    nr_md5     = save_svg(NEWRECORD_SVG)
    digit_md5  = [save_svg(s) for s in DIGIT_SVGS]

    # 전용 효과음 합성 9종 (assets/ 에도 저장, .build 에도 md5 로 저장)
    def save_wav(name, samples):
        b = _wav_bytes(samples)
        with open(f"{ASSETS}/{name}.wav", "wb") as f: f.write(b)
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    stretch_md5, stretch_n = save_wav("stretch", synth_stretch())
    fire_md5,    fire_n    = save_wav("fire",    synth_fire())
    pop_md5,     pop_n     = save_wav("pop",     synth_pop())
    combo_md5,   combo_n   = save_wav("combo",   synth_combo())
    wilt_snd_md5,wilt_snd_n= save_wav("wilt",    synth_wilt())
    lakitu_md5s, lakitu_ns = save_wav("lakitu",  synth_lakitu())
    clear_md5,   clear_n   = save_wav("clear",   synth_clear())
    gover_md5,   gover_n   = save_wav("gameover",synth_gameover())
    record_md5,  record_n  = save_wav("record",  synth_record())

    # ── BGM: 사용자 제공 mp3 를 '바이너리 그대로' 아카이브(재인코딩 금지) ──
    BGM_SRC = os.path.join(ASSETS, "bgm.mp3")
    with open(BGM_SRC, "rb") as f: bgm_bytes = f.read()
    bgm_md5 = md5_bytes(bgm_bytes)
    with open(f"{WORK}/{bgm_md5}.mp3", "wb") as f: f.write(bgm_bytes)
    BGM_RATE = 48000                 # 48kHz stereo mp3
    BGM_SAMPLES = int(124 * BGM_RATE)  # ≈124초 분량(근사, 재생 루프엔 영향 없음)
    def S_bgm():
        return {"name": "bgm", "assetId": bgm_md5, "dataFormat": "mp3", "format": "",
                "rate": BGM_RATE, "sampleCount": BGM_SAMPLES, "md5ext": f"{bgm_md5}.mp3"}

    def snd(name, m, n):
        return {"name": name, "assetId": m, "dataFormat": "wav", "format": "",
                "rate": SND_RATE, "sampleCount": n, "md5ext": f"{m}.wav"}
    S_stretch = lambda: snd("stretch", stretch_md5, stretch_n)
    S_fire    = lambda: snd("fire",    fire_md5,    fire_n)
    S_pop     = lambda: snd("pop",     pop_md5,     pop_n)
    S_combo   = lambda: snd("combo",   combo_md5,   combo_n)
    S_wilt    = lambda: snd("wilt",    wilt_snd_md5,wilt_snd_n)
    S_lakitu  = lambda: snd("lakitu",  lakitu_md5s, lakitu_ns)
    S_clear   = lambda: snd("clear",   clear_md5,   clear_n)
    S_gover   = lambda: snd("gameover",gover_md5,   gover_n)
    S_record  = lambda: snd("record",  record_md5,  record_n)

    stage_blocks,    stage_cmt    = build_stage_blocks()
    frame_blocks,    frame_cmt    = build_frame_blocks()
    launcher_blocks, launcher_cmt = build_launcher_blocks()
    band_blocks,     band_cmt     = build_band_blocks()
    traj_blocks,     traj_cmt     = build_traj_blocks()
    ball_blocks,     ball_cmt     = build_ball_blocks()
    bomb_blocks,     bomb_cmt     = build_bomb_blocks()
    lakitu_blocks,   lakitu_cmt   = build_lakitu_blocks()
    flower_blocks,   flower_cmt   = build_flower_blocks()
    popup_blocks,    popup_cmt    = build_popup_blocks()
    banner_blocks,   banner_cmt   = build_banner_blocks()

    # ---- Stage: 전역 변수 (튜닝20 + 진행26 + 임시i·꽃최소거리·다음꽃X) + 리스트 1 + 방송 9 ----
    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 조준/물리 4
            V_POWMUL: ["발사력배율", 0.22], V_DRAGMAX: ["최대당김거리", 90],
            V_GRAVITY: ["중력", 0.30], V_WIND: ["바람", 0],
            # 튜닝 적/난이도 7
            V_FALLSPD: ["낙하속도", 0.7], V_SPAWNGAP: ["스폰간격", 1.6],
            V_RAMP: ["난이도증가율", 0.02], V_SPAWNMAX: ["스폰최대", 8],
            V_SWAY: ["흔들폭", 12], V_LAKITUP: ["라키투확률", 40], V_LAKITUSPD: ["라키투속도", 3],
            # 튜닝 방어/점수 9
            V_FLOWERN: ["꽃개수", 4], V_BOMBPT: ["요격점수", 100], V_COMBOMUL: ["콤보배율", 2],
            V_COMBOCAP: ["콤보최대", 32], V_BALLR: ["포탄반경", 14], V_OFFX: ["착탄허용밖", 250],
            V_GROUNDY: ["지면Y", -120], V_PRESTEPS: ["미리보기점수", 70], V_PREGAP: ["미리보기간격", 3],
            # 튜닝 추가 4 (관통샷·연사·수명·BGM)
            V_PIERCE: ["관통횟수", 2], V_MAXBALL: ["최대포탄수", 5], V_BALLLIFE: ["포탄수명", 150],
            V_BGMVOL: ["브금볼륨", 70],
            # 진행 26 (+포탄수)
            V_STATE: ["게임상태", 1], V_SCORE: ["점수", 0], V_BEST: ["최고점수", 0],
            V_COMBO: ["콤보수", 0], V_COMBOX: ["콤보배수", 1], V_FLOWERLEFT: ["꽃남음", 4],
            V_KILLS: ["처치수", 0], V_BOMBALIVE: ["적수", 0], V_ANCHORX: ["앵커X", 0],
            V_ANCHORY: ["앵커Y", -60], V_DRAGX: ["당김X", 0], V_DRAGY: ["당김Y", 0],
            V_DRAGMAG: ["당김크기", 0], V_DRAGANG: ["당김각도", 0], V_DRAGGING: ["드래그중", 0],
            V_FLYING: ["비행중", 0], V_WIPE: ["전멸신호", 0], V_KILLFLOWERX: ["파괴꽃X", 0],
            V_POPVAL: ["명중점수값", 0], V_POPX: ["명중점수x", 0], V_POPY: ["명중점수y", 0],
            V_POPKIND: ["팝업종류", 0], V_POPDIGIT: ["팝업숫자", 0], V_POPOFF: ["팝업오프셋", 0],
            V_POPLEN: ["팝업글자수", 0], V_POPPOS: ["팝업자리", 0],
            # 진행: 포탄수 (연사 상한 판정)
            V_BALLALIVE: ["포탄수", 0],
            # 내부 보조 3 (튜닝 아님)
            V_TMPI: ["임시i", 0], V_FLOWERMIND: ["꽃최소거리", 99999], V_FLOWERNEXTX: ["다음꽃X", 0],
        },
        "lists": {L_FLOWERX: ["꽃X", []]},
        "broadcasts": {
            BR_START: "게임시작", BR_FLOWER: "꽃생성", BR_SPAWNBOMB: "적생성",
            BR_SPAWNLAK: "라키투생성", BR_FIRE: "발사", BR_POP: "점수표시",
            BR_KILLFLOWER: "꽃파괴", BR_GAMEOVER: "게임오버", BR_MEASURE: "꽃거리측정",
        },
        "blocks": stage_blocks, "comments": stage_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "하늘", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [S_bgm()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    def sprite(name, blocks, cmt, costumes, sounds, layer, visible=True,
               x=0, y=0, size=100, rot="all around", variables=None):
        return {
            "isStage": False, "name": name,
            "variables": variables or {}, "lists": {}, "broadcasts": {},
            "blocks": blocks, "comments": cmt,
            "currentCostume": 0, "costumes": costumes, "sounds": sounds,
            "volume": 100, "layerOrder": layer, "visible": visible,
            "x": x, "y": y, "size": size, "direction": 90,
            "draggable": False, "rotationStyle": rot,
        }

    def cost(name, m, cx, cy):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": m, "md5ext": f"{m}.svg",
                "rotationCenterX": cx, "rotationCenterY": cy}

    frame = sprite("발사대", frame_blocks, frame_cmt,
        [cost("frame", frame_md5, 22, 30)], [], 1, x=0, y=-60, rot="don't rotate")
    launcher = sprite("발사체", launcher_blocks, launcher_cmt,
        [cost("ball", ball_md5, 14, 14), cost("boom", boom_md5, 24, 24)],
        [S_stretch()], 8, x=0, y=-60, rot="don't rotate")
    band = sprite("당김선", band_blocks, band_cmt,
        [cost("band", ball_md5, 14, 14)], [], 2, visible=False, rot="don't rotate")
    traj = sprite("궤적펜", traj_blocks, traj_cmt,
        [cost("dot", ball_md5, 14, 14)], [], 3, visible=False, rot="don't rotate",
        variables={V_PREX: ["미리X", 0], V_PREY: ["미리Y", 0],
                   V_PREVX: ["미리VX", 0], V_PREVY: ["미리VY", 0]})
    ball = sprite("포탄", ball_blocks, ball_cmt,
        [cost("ball", ball_md5, 14, 14), cost("boom", boom_md5, 24, 24)],
        [S_fire()], 5, visible=False,
        variables={V_BALLISC: ["복제됨", 0], V_BALLVX: ["속도X", 0], V_BALLVY: ["속도Y", 0],
                   V_BALLPIER: ["남은관통", 2], V_BALLHITCD: ["피격쿨", 0],
                   V_BALLLIFEC: ["남은수명", 150]})
    bomb = sprite("적", bomb_blocks, bomb_cmt,
        [cost("monster", monster_md5, 22, 48), cost("boom", boom_md5, 24, 24)],
        [S_pop(), S_combo()], 4, visible=False,
        variables={V_BOMBISC: ["복제됨", 0], V_BOMBFALL: ["내낙하", 0.7],
                   V_BOMBBASEX: ["흔들기준X", 0], V_BOMBPHASE: ["흔들위상", 0]})
    lakitu = sprite("라키투", lakitu_blocks, lakitu_cmt,
        [cost("lakitu", lakitu_md5, 28, 30), cost("boom", boom_md5, 24, 24)],
        [S_lakitu(), S_clear()], 6, visible=False, rot="don't rotate",
        variables={V_LAKISC: ["복제됨", 0], V_LAKDIR: ["진행방향", 1]})
    flower = sprite("꽃", flower_blocks, flower_cmt,
        [cost("flower", flower_md5, 18, 40), cost("wilt", wilt_md5, 18, 40)],
        [S_wilt()], 7, visible=False, rot="don't rotate",
        variables={V_FLOWERISC: ["복제됨", 0], V_FLOWERMYX: ["내X", 0],
                   V_FLOWERALIVE: ["살아있음", 1]})
    popup = sprite("숫자팝업", popup_blocks, popup_cmt,
        [cost(f"w{d}", digit_md5[d], 14, 20) for d in range(10)]
        + [cost(f"g{d}", digit_md5[10+d], 14, 20) for d in range(10)],
        [], 9, visible=False, rot="don't rotate",
        variables={V_POPISC: ["복제됨", 0]})
    banner = sprite("배너", banner_blocks, banner_cmt,
        [cost("gameover", go_md5, 180, 75), cost("newrecord", nr_md5, 180, 75)],
        [S_gover(), S_record()], 10, visible=False, rot="don't rotate")

    monitors = []
    def mon(vid, name, x, y, smin, smax):
        monitors.append({"id": vid, "mode": "default", "opcode": "data_variable",
            "params": {"VARIABLE": name}, "spriteName": None, "value": 0,
            "width": 0, "height": 0, "x": x, "y": y, "visible": True,
            "sliderMin": smin, "sliderMax": smax, "isDiscrete": True})
    # ── HUD 3종만 좌상단(적 시야 방해 최소) ──
    mon(V_SCORE, "점수", 5, 5, 0, 99999)
    mon(V_COMBOX, "콤보배수", 5, 29, 0, 64)
    mon(V_BEST, "최고점수", 5, 53, 0, 99999)
    # ── 드래그 벡터 4종은 하단으로 (적 낙하 경로 상단~중앙을 가리지 않게).
    #    스테이지 480×360, 모니터 좌표 (0,0)=좌상단. 하단 y≈300~345 = 잔디·흙 띠 위 ──
    mon(V_DRAGX, "당김X", 4, 302, -100, 100)
    mon(V_DRAGY, "당김Y", 128, 302, -100, 100)
    mon(V_DRAGMAG, "당김크기", 252, 302, 0, 100)
    mon(V_DRAGANG, "당김각도", 366, 302, 0, 90)

    project = {
        "targets": [stage, frame, launcher, band, traj, ball, bomb,
                    lakitu, flower, popup, banner],
        "monitors": monitors, "extensions": ["pen"],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "bomb-squad-builder"}
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
    for nm, b in [("stage", stage_blocks), ("frame", frame_blocks),
                  ("launcher", launcher_blocks), ("band", band_blocks),
                  ("traj", traj_blocks), ("ball", ball_blocks), ("bomb", bomb_blocks),
                  ("lakitu", lakitu_blocks), ("flower", flower_blocks),
                  ("popup", popup_blocks), ("banner", banner_blocks)]:
        print(f"  {nm:9s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
