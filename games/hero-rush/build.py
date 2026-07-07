#!/usr/bin/env python3
"""용사 진격전 (hero-rush) — 1인 용사 진격형 횡스크롤 액션 로그라이트.

내가 조종하는 용사 한 명이 오른쪽 적 성을 향해 진격한다. ←→ 이동, ↑ 점프(회피),
Space/클릭 검격, X 광역 스킬. 앞으로 밀고 나가면 진격도가 차오르고 적이 웨이브로
몰려온다(오른쪽에서 스폰 → 용사로 전진, 클론끼리 상호작용 0개). 진격도가 가득 차면
성문이 슬라이드 인 → 검격/스킬로 성문 파괴 → 스테이지 클리어 → 강화 택1 →
다음 스테이지(지수 스케일 적배율 = 적성장배율^(스테이지−1)). 체력 0이면 GAME OVER
(로그라이트, 1스테이지부터). 점수 = 도달한 스테이지.

베이스: games/rogue-knight/build.py (좌우 이동·VY/중력/점프·검판정 히트박스 분리·클론
스포너·복제됨 가드·폭발 연출·강화 택1·플로팅 데미지 숫자·게임오버) + games/castle-defense
(지수 스케일·합성 효과음 _wav_bytes/synth_*·add_comment 가이드 투어).

★ chess-war 교훈: 다대다 자율 전투 폐기. 적은 '용사 향해 전진 + 접촉 + 히트박스 피격'
  만(단순!). 리스트 0개, 클론끼리 참조 0개. 모든 조절 값은 한글 튜닝 변수(매직넘버 0).
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "용사_진격전.sb3")

# ============================================================
#  효과음 합성 (전용 10종) — 결정적
# ============================================================
SND_RATE = 11025
def _wav_bytes(samples, rate=SND_RATE):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_swing(rate=SND_RATE):
    """검 휘두름 '쉭' — 1.5kHz→400Hz 하강 처프, 0.08초."""
    N = int(rate * 0.08); out = []
    for i in range(N):
        t = i / rate
        f = 400 + 1100 * math.exp(-t * 40)
        env = math.exp(-t * 26)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.5)
    return out

def synth_skill(rate=SND_RATE):
    """스킬 회전 '부웅' — 3정현파 하강 화음, 0.22초."""
    N = int(rate * 0.22); out = []
    for i in range(N):
        t = i / rate
        b = 220 * math.exp(-t * 2.0)
        s = (math.sin(2*math.pi*b*t) + 0.6*math.sin(2*math.pi*b*1.5*t) + 0.4*math.sin(2*math.pi*b*2*t)) / 2.0
        env = min(1.0, t/0.02) * math.exp(-t * 6)
        out.append(s * env * 0.5)
    return out

def synth_hurt(rate=SND_RATE):
    """용사 피격 — 거친 저음 150Hz 사각파 하강, 0.15초."""
    N = int(rate * 0.15); out = []
    for i in range(N):
        t = i / rate
        f = 150 + 60 * math.exp(-t * 8)
        sq = 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0
        env = math.exp(-t * 9)
        out.append(sq * env * 0.45)
    return out

def synth_hit(rate=SND_RATE):
    """적 피격 — 아주 짧은 '틱' 2kHz 클릭, 0.03초."""
    N = int(rate * 0.03); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 90)
        out.append(math.sin(2 * math.pi * 2000 * t) * env * 0.5)
    return out

def synth_death(rate=SND_RATE):
    """적 처치 '펑' — 노이즈+thump, 0.12초. 결정적."""
    N = int(rate * 0.12); out = []
    rng = random.Random(20260801); lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 20)
        white = rng.random() * 2 - 1
        lp = lp + 0.45 * (white - lp)
        thump = math.sin(2 * math.pi * (70 + 50 * math.exp(-t * 26)) * t)
        out.append(max(-1, min(1, (lp * 0.6 + thump * 0.7) * env)))
    return out

def synth_coin(rate=SND_RATE):
    """처치 골드 '딩' — 988→1319Hz 두 톤, 0.12초."""
    N = int(rate * 0.12); out = []
    for i in range(N):
        t = i / rate
        f = 988 if t < 0.04 else 1319
        env = math.exp(-t * 12)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.45)
    return out

def synth_gatehit(rate=SND_RATE):
    """성문 타격 '쿵' — 60Hz thump + 노이즈, 0.18초. 결정적."""
    N = int(rate * 0.18); out = []
    rng = random.Random(20260802); lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 14)
        white = rng.random() * 2 - 1
        lp = lp + 0.35 * (white - lp)
        thump = math.sin(2 * math.pi * (55 + 25 * math.exp(-t * 20)) * t)
        out.append(max(-1, min(1, (lp * 0.4 + thump * 0.9) * env)))
    return out

def synth_gatebreak(rate=SND_RATE):
    """성문 파괴 — 크게 무너지는 파열(긴 노이즈+저음), 0.5초. 결정적."""
    N = int(rate * 0.50); out = []
    rng = random.Random(20260803); lp = 0.0
    for i in range(N):
        t = i / rate
        env = min(1.0, t / 0.02) * math.exp(-t * 4.5)
        white = rng.random() * 2 - 1
        lp = lp + 0.18 * (white - lp)
        thump = math.sin(2 * math.pi * (45 + 30 * math.exp(-t * 6)) * t)
        out.append(max(-1, min(1, (lp * 0.8 + thump * 0.7) * env)))
    return out

def synth_horn(rate=SND_RATE):
    """스테이지 시작 뿔피리 — 180Hz 톱니, 0.4초, 느린 어택."""
    N = int(rate * 0.40); out = []
    for i in range(N):
        t = i / rate
        ph = (180 * t) % 1.0
        saw = 2 * ph - 1
        env = min(1.0, t / 0.08) * math.exp(-t * 3.0)
        out.append(saw * env * 0.4)
    return out

def synth_upgrade(rate=SND_RATE):
    """강화 선택 — 상승 아르페지오 523→659→784Hz, 0.3초."""
    N = int(rate * 0.30); out = []
    for i in range(N):
        t = i / rate
        f = 523 if t < 0.1 else (659 if t < 0.2 else 784)
        env = math.exp(-((t % 0.1)) * 14)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.45)
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

# -------- 배경: 들판 + 멀리 검은 성 --------
random.seed(9)
grass = []
for ty in range(250, 360, 22):
    for tx in range(0, 480, 22):
        shade = random.choice(["#7FB84E", "#77B046", "#86C056"])
        grass.append(f'<rect x="{tx}" y="{ty}" width="22" height="22" fill="{shade}"/>')
GRASS = "\n    ".join(grass)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#9DC3E6"/><stop offset="1" stop-color="#D6E8F5"/></linearGradient></defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <circle cx="70" cy="60" r="24" fill="#FFFFFF" opacity="0.8"/>
  <circle cx="100" cy="66" r="20" fill="#FFFFFF" opacity="0.8"/>
  <!-- 멀리 검은 성(오른쪽) -->
  <g opacity="0.55">
    <rect x="392" y="150" width="78" height="100" fill="#3A3A46"/>
    <rect x="384" y="140" width="18" height="26" fill="#2A2A34"/><rect x="428" y="140" width="18" height="26" fill="#2A2A34"/>
    <rect x="460" y="140" width="14" height="26" fill="#2A2A34"/>
    <polygon points="405,150 431,120 457,150" fill="#2A2A34"/>
    <rect x="420" y="200" width="22" height="50" rx="10" fill="#15151C"/>
  </g>
  <rect x="0" y="248" width="480" height="112" fill="#7FB84E"/>
  <g>{GRASS}</g>
  <line x1="0" y1="250" x2="480" y2="250" stroke="#4E7A2E" stroke-width="3" opacity="0.5"/>
  <rect x="4" y="4" width="472" height="352" rx="10" fill="none" stroke="#4E7A2E" stroke-width="5" opacity="0.4"/>
</svg>"""

# -------- 용사 3코스튬 (오른쪽 향함; 발=바닥) --------
HERO_IDLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="52" height="60" viewBox="0 0 52 60">
  <ellipse cx="26" cy="57" rx="13" ry="3" fill="#000" opacity="0.22"/>
  <rect x="20" y="46" width="6" height="12" fill="#455A64"/><rect x="27" y="46" width="6" height="12" fill="#455A64"/>
  <rect x="18" y="26" width="18" height="22" rx="4" fill="#ECEFF1" stroke="#90A4AE" stroke-width="2"/>
  <ellipse cx="27" cy="17" rx="9" ry="10" fill="#F4D6B0" stroke="#B98A5E" stroke-width="1.5"/>
  <rect x="22" y="12" width="12" height="5" fill="#B0BEC5"/>
  <polygon points="27,5 31,11 23,11" fill="#42A5F5"/>
  <line x1="40" y1="44" x2="40" y2="18" stroke="#CFD8DC" stroke-width="3"/>
  <polygon points="40,15 43,21 37,21" fill="#ECEFF1"/>
  <rect x="35" y="42" width="10" height="4" rx="1" fill="#7A5230"/>
</svg>"""
HERO_ATK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="26" cy="57" rx="13" ry="3" fill="#000" opacity="0.22"/>
  <rect x="20" y="46" width="6" height="12" fill="#455A64"/><rect x="28" y="46" width="6" height="12" fill="#455A64"/>
  <rect x="18" y="26" width="18" height="22" rx="4" fill="#ECEFF1" stroke="#90A4AE" stroke-width="2"/>
  <ellipse cx="27" cy="17" rx="9" ry="10" fill="#F4D6B0" stroke="#B98A5E" stroke-width="1.5"/>
  <rect x="22" y="12" width="12" height="5" fill="#B0BEC5"/>
  <polygon points="27,5 31,11 23,11" fill="#42A5F5"/>
  <line x1="36" y1="30" x2="56" y2="22" stroke="#CFD8DC" stroke-width="4"/>
  <polygon points="56,18 60,23 54,26" fill="#FFFFFF"/>
  <path d="M40 44 Q56 34 56 20" fill="none" stroke="#FFF59D" stroke-width="2" opacity="0.7"/>
</svg>"""
HERO_SKILL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <circle cx="30" cy="30" r="26" fill="#B388FF" opacity="0.18"/>
  <ellipse cx="30" cy="57" rx="13" ry="3" fill="#000" opacity="0.22"/>
  <rect x="20" y="26" width="18" height="22" rx="4" fill="#ECEFF1" stroke="#90A4AE" stroke-width="2"/>
  <ellipse cx="29" cy="17" rx="9" ry="10" fill="#F4D6B0" stroke="#B98A5E" stroke-width="1.5"/>
  <polygon points="29,5 33,11 25,11" fill="#42A5F5"/>
  <circle cx="30" cy="30" r="22" fill="none" stroke="#7E57C2" stroke-width="3" stroke-dasharray="8 6" opacity="0.85"/>
  <line x1="8" y1="30" x2="52" y2="30" stroke="#CFD8DC" stroke-width="3"/>
</svg>"""

# -------- 히트박스 --------
SLASH_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <path d="M14 8 Q54 30 14 52" fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" opacity="0.9"/>
  <path d="M20 14 Q46 30 20 46" fill="none" stroke="#FFF176" stroke-width="4" stroke-linecap="round" opacity="0.8"/>
</svg>"""
SPIN_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <circle cx="60" cy="60" r="52" fill="#B388FF" opacity="0.20"/>
  <circle cx="60" cy="60" r="52" fill="none" stroke="#7E57C2" stroke-width="6" stroke-dasharray="14 10" opacity="0.9"/>
  <polygon points="{_star_pts(60,60,50,20,8)}" fill="none" stroke="#FFFFFF" stroke-width="3" opacity="0.7"/>
</svg>"""

# -------- 적 4코스튬 (왼쪽 향함) --------
E1_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
  <ellipse cx="23" cy="43" rx="11" ry="3" fill="#000" opacity="0.25"/>
  <ellipse cx="23" cy="20" rx="12" ry="13" fill="#5E7A3A" stroke="#33500F" stroke-width="2"/>
  <circle cx="18" cy="18" r="2.4" fill="#FFEB3B"/><circle cx="28" cy="18" r="2.4" fill="#FFEB3B"/>
  <rect x="6" y="22" width="12" height="4" rx="2" fill="#6D4C41" transform="rotate(-20 12 24)"/>
  <rect x="18" y="32" width="10" height="8" rx="2" fill="#4E342E"/>
</svg>"""
E2_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="58" viewBox="0 0 56 58">
  <ellipse cx="28" cy="55" rx="14" ry="3" fill="#000" opacity="0.28"/>
  <rect x="18" y="26" width="20" height="24" rx="4" fill="#37414A" stroke="#15151C" stroke-width="2"/>
  <ellipse cx="27" cy="16" rx="11" ry="12" fill="#556B2F" stroke="#2E3B18" stroke-width="2"/>
  <circle cx="22" cy="15" r="2.4" fill="#D32F2F"/><circle cx="32" cy="15" r="2.4" fill="#D32F2F"/>
  <line x1="10" y1="20" x2="10" y2="44" stroke="#5D4037" stroke-width="4"/>
  <polygon points="4,20 16,20 10,10" fill="#90A4AE"/>
</svg>"""
E3_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="70" height="70" viewBox="0 0 70 70">
  <ellipse cx="35" cy="66" rx="18" ry="4" fill="#000" opacity="0.3"/>
  <rect x="40" y="24" width="22" height="40" rx="4" fill="#546E7A" stroke="#263238" stroke-width="2"/>
  <line x1="46" y1="30" x2="46" y2="58" stroke="#90A4AE" stroke-width="2"/>
  <rect x="20" y="30" width="24" height="30" rx="5" fill="#455A64" stroke="#1C262B" stroke-width="2.5"/>
  <ellipse cx="30" cy="20" rx="12" ry="13" fill="#37474F" stroke="#15151C" stroke-width="2.5"/>
  <rect x="22" y="17" width="16" height="5" fill="#78909C"/>
  <circle cx="27" cy="19" r="2.4" fill="#FF5252"/><circle cx="35" cy="19" r="2.4" fill="#FF5252"/>
</svg>"""
BOOM_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30,30,28,11,10)}" fill="#FF7043" stroke="#E64A19" stroke-width="1"/>
  <polygon points="{_star_pts(30,30,20,8,10,rot=0.31)}" fill="#FFB300"/>
  <circle cx="30" cy="30" r="10" fill="#FFEB3B"/><circle cx="30" cy="30" r="4" fill="#FFFFFF"/>
</svg>"""

# -------- 성문 3코스튬 --------
def _gate_svg(crack):
    cr = ""
    if crack == 1:
        cr = '<path d="M40 20 L55 60 L44 100 L60 150" fill="none" stroke="#15151C" stroke-width="3"/><path d="M70 40 L58 90" fill="none" stroke="#15151C" stroke-width="2.5"/>'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="100" height="170" viewBox="0 0 100 170">
  <rect x="6" y="6" width="88" height="158" rx="6" fill="#2A2A34" stroke="#15151C" stroke-width="4"/>
  <rect x="16" y="16" width="68" height="140" rx="30" fill="#3E3E4A" stroke="#15151C" stroke-width="3"/>
  <line x1="50" y1="16" x2="50" y2="156" stroke="#15151C" stroke-width="3"/>
  <circle cx="38" cy="90" r="4" fill="#8D6E63"/><circle cx="62" cy="90" r="4" fill="#8D6E63"/>
  {cr}
</svg>"""
GATE_OK_SVG = _gate_svg(0)
GATE_CRACK_SVG = _gate_svg(1)
GATE_RUIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="170" viewBox="0 0 100 170">
  <polygon points="10,164 30,90 6,40 40,70 30,10 60,60 70,20 78,80 94,60 84,130 94,164" fill="#2A2A34" stroke="#15151C" stroke-width="3"/>
  <circle cx="40" cy="120" r="6" fill="#3E3E4A"/><circle cx="66" cy="140" r="5" fill="#3E3E4A"/>
</svg>"""

# -------- 강화패널 --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="150" viewBox="0 0 400 150">
  <rect x="4" y="4" width="392" height="142" rx="14" fill="#1A237E" opacity="0.95" stroke="#FFD54F" stroke-width="4"/>
  <text x="200" y="30" text-anchor="middle" fill="#FFD54F" font-family="Arial" font-size="20" font-weight="bold">스테이지 클리어! 강화 선택</text>
  <rect x="12" y="44" width="88" height="92" rx="10" fill="#C62828" stroke="#FFFFFF" stroke-width="2"/>
  <text x="56" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">1</text>
  <text x="56" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">공격력+</text>
  <rect x="106" y="44" width="88" height="92" rx="10" fill="#2E7D32" stroke="#FFFFFF" stroke-width="2"/>
  <text x="150" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">2</text>
  <text x="150" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">체력+</text>
  <rect x="200" y="44" width="88" height="92" rx="10" fill="#1565C0" stroke="#FFFFFF" stroke-width="2"/>
  <text x="244" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">3</text>
  <text x="244" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">이동속도+</text>
  <rect x="294" y="44" width="88" height="92" rx="10" fill="#6A1B9A" stroke="#FFFFFF" stroke-width="2"/>
  <text x="338" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">4</text>
  <text x="338" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">스킬쿨↓</text>
</svg>"""
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="68" text-anchor="middle" fill="#E53935" font-family="Arial" font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="20">도달한 스테이지는 왼쪽 위에서!</text>
  <text x="180" y="136" text-anchor="middle" fill="#FFCDD2" font-family="Arial" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# -------- 숫자 코스튬 0~9 --------
def _digit_svg(d):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="28" height="40" viewBox="0 0 28 40">
  <text x="14" y="32" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-size="38" font-weight="bold" fill="#FFFFFF" stroke="#B71C1C" stroke-width="4" paint-order="stroke" stroke-linejoin="round">{d}</text>
</svg>"""
DIGITS = [_digit_svg(d) for d in range(10)]

# -------- UI 바 costume-fill 11단 --------
def _bar_svg(step, fill, label):
    # step 0..10 → 채움 비율. 폭 96, 높이 14, 라벨 좌측.
    w = int(round(96 * step / 10))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="140" height="20" viewBox="0 0 140 20">
  <text x="2" y="15" font-family="Arial" font-size="12">{label}</text>
  <rect x="30" y="3" width="100" height="14" rx="4" fill="#000000" opacity="0.35"/>
  <rect x="32" y="5" width="{w}" height="10" rx="3" fill="{fill}"/>
  <rect x="30" y="3" width="100" height="14" rx="4" fill="none" stroke="#FFFFFF" stroke-width="1.5" opacity="0.8"/>
</svg>"""
HP_BARS   = [_bar_svg(s, "#E53935", "❤") for s in range(11)]
SK_BARS   = [_bar_svg(s, "#42A5F5", "⚡") for s in range(11)]
MR_BARS   = [_bar_svg(s, "#FFB300", "🏰") for s in range(11)]

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
def b_mathop(bs, oper, val):
    bid = gen(); ins = {"NUM": slot(val) if (isinstance(val,str) and val in bs) else num(val)}
    bs[bid] = mk("operator_mathop", inputs=ins, fields={"OPERATOR": [oper, None]})
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

def b_keypressed(bs, key):
    m = gen(); bs[m] = mk("sensing_keyoptions", fields={"KEY_OPTION": [key, None]}, shadow=True)
    p = gen(); bs[p] = mk("sensing_keypressed", inputs={"KEY_OPTION": [1, m]}); bs[m]["parent"] = p; return p
def b_mousedown(bs):
    bid = gen(); bs[bid] = mk("sensing_mousedown"); return bid
def _spr_menu(bs, name):
    m = gen(); bs[m] = mk("sensing_of_object_menu", fields={"OBJECT": [name, None]}, shadow=True); return m
def _of(bs, spr, prop):
    bid = gen(); bs[bid] = mk("sensing_of", inputs={"OBJECT": [1, _spr_menu(bs, spr)]}, fields={"PROPERTY": [prop, None]}); return bid
def b_touching(bs, target):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu", fields={"TOUCHINGOBJECTMENU": [target, None]}, shadow=True)
    t = gen(); bs[t] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, m]}); bs[m]["parent"] = t; return t

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
    bid = gen(); bs[bid] = mk("control_stop", fields={"STOP_OPTION": ["this script", None]}, mutation={"tagName":"mutation","children":[],"hasnext":"false"}) if False else mk("control_stop", fields={"STOP_OPTION": ["this script", None]})
    bs[bid]["mutation"] = {"tagName": "mutation", "children": [], "hasnext": "false"}
    return bid

def b_sound(bs, pitch, sound):
    pe = gen(); bs[pe] = mk("sound_seteffectto", inputs={"VALUE": num(pitch)}, fields={"EFFECT": ["PITCH", None]})
    sm = gen(); bs[sm] = mk("sound_sounds_menu", fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]}); bs[sm]["parent"] = sp
    chain([(pe, bs[pe]), (sp, bs[sp])]); return pe, sp
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
def b_glide(bs, secs, x, y):
    bid = gen()
    def side(v): return slot(v) if (isinstance(v, str) and v in bs) else num(v)
    bs[bid] = mk("motion_glidesecstoxy", inputs={"SECS": num(secs), "X": side(x), "Y": side(y)})
    for v in (x, y):
        if isinstance(v, str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_changex(bs, v):
    bid = gen(); ins = {"DX": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_changexby", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_changey(bs, v):
    bid = gen(); ins = {"DY": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_changeyby", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_setx(bs, v):
    bid = gen(); ins = {"X": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_setx", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_sety(bs, v):
    bid = gen(); ins = {"Y": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_sety", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_xpos(bs):
    bid = gen(); bs[bid] = mk("motion_xposition"); return bid
def b_ypos(bs):
    bid = gen(); bs[bid] = mk("motion_yposition"); return bid
def b_direction(bs):
    bid = gen(); bs[bid] = mk("motion_direction"); return bid
def b_pointdir(bs, d):
    bid = gen(); bs[bid] = mk("motion_pointindirection", inputs={"DIRECTION": num(d)}); return bid
def b_pointdir_r(bs, rep):
    bid = gen(); bs[bid] = mk("motion_pointindirection", inputs={"DIRECTION": slot(rep)}); bs[rep]["parent"] = bid; return bid
def b_turn(bs, deg):
    bid = gen(); bs[bid] = mk("motion_turnright", inputs={"DEGREES": num(deg)}); return bid

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
#  IDs — 5.1 튜닝 35
# ============================================================
V_ATK="varAtk01"; V_SKATK="varSkAtk02"; V_MAXHP="varMaxHP03"; V_MOVE="varMove04"; V_JUMP="varJump05"
V_GRAV="varGrav06"; V_INV="varInv07"; V_SWCD="varSwCd08"; V_SKCD="varSkCd09"; V_SWR="varSwRange10"; V_SKR="varSkRange11"
V_MARCH="varMarch12"; V_STAGELEN="varStageLen13"; V_MARCHX="varMarchX14"; V_GATEHP="varGateHP15"; V_GATEX="varGateX16"; V_GATESTARTX="varGateStartX17"
V_E1HP="varE1HP18"; V_E1SP="varE1SP19"; V_E1AT="varE1AT20"; V_E2HP="varE2HP21"; V_E2SP="varE2SP22"; V_E2AT="varE2AT23"; V_E3HP="varE3HP24"; V_E3SP="varE3SP25"; V_E3AT="varE3AT26"
V_WGAP="varWaveGap27"; V_WDEC="varWaveDec28"; V_WMIN="varWaveMin29"; V_MAXEN="varMaxEn30"; V_SCALE="varScale31"; V_KILLGOLD="varKillGold32"; V_UP="varUp33"; V_UPSK="varUpSk34"; V_LANEY="varLaneY35"

# ----- 5.2 진행 30 -----
V_STATE="varState36"; V_STAGE="varStage37"; V_PROG="varMarchProg38"; V_SCALECUR="varScaleCur39"; V_HP="varHP40"; V_GOLD="varGold41"; V_ALIVE="varAlive42"; V_SIEGE="varSiege43"; V_GATECUR="varGateCur44"
V_VY="varVY45"; V_JUMPL="varJumpLeft46"; V_PREVJ="varPrevJump47"; V_SWT="varSwT48"; V_PREVSW="varPrevSw49"; V_SKT="varSkT50"; V_PREVSK="varPrevSk51"; V_INVT="varInvT52"; V_PREVM="varPrevMouse53"
V_SPTYPE="varSpType54"; V_SPX="varSpX55"; V_SPY="varSpY56"; V_WAVET="varWaveT57"
V_DMGVAL="varDmgVal58"; V_DMGX="varDmgX59"; V_DMGY="varDmgY60"; V_DMGKIND="varDmgKind61"; V_DMGDIG="varDmgDigit62"; V_DMGOFF="varDmgOff63"; V_DMGLEN="varDmgLen64"; V_DMGPOS="varDmgPos65"

# ----- 5.4 클론-로컬 7 -----
V_EN_ISC="varEnIsClone"; V_EN_HP="varEnHP"; V_EN_TYPE="varEnType"; V_EN_SPD="varEnSpd"; V_EN_ATK="varEnAtk"; V_EN_HIT="varEnHit"
V_DMG_ISC="varDmgIsClone"

# ----- 5.5 방송 8 -----
BR_START="brStart01"; BR_STAGEGO="brStageGo02"; BR_SPAWN="brSpawn03"; BR_GATE="brGate04"; BR_DMG="brDmg05"; BR_UP="brUp06"; BR_NEXT="brNext07"; BR_OVER="brOver08"

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 → 튜닝35 + 진행30 초기화 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [h]
    def s(name, vid, val): seq.append(b_setvar(bs, name, vid, val))
    def sr(name, vid, rep): seq.append(b_setvar(bs, name, vid, rep))
    # 용사
    s("공격력",V_ATK,3); s("스킬공격력",V_SKATK,8); s("최대체력",V_MAXHP,6); s("이동속도",V_MOVE,6)
    s("점프력",V_JUMP,12); s("중력",V_GRAV,-1); s("무적시간",V_INV,20); s("검격쿨",V_SWCD,8); s("스킬쿨",V_SKCD,200)
    s("검격범위",V_SWR,40); s("스킬범위",V_SKR,130)
    # 진격/공성
    s("진격속도",V_MARCH,1.8); s("스테이지길이",V_STAGELEN,900); s("진격기준X",V_MARCHX,60)
    s("성문기본체력",V_GATEHP,40); s("성문공성X",V_GATEX,150); s("성문시작X",V_GATESTARTX,240)
    # 적 종류
    s("잡졸_체력",V_E1HP,4); s("잡졸_속도",V_E1SP,2.5); s("잡졸_공격력",V_E1AT,1)
    s("전사_체력",V_E2HP,9); s("전사_속도",V_E2SP,1.6); s("전사_공격력",V_E2AT,1)
    s("기사_체력",V_E3HP,18); s("기사_속도",V_E3SP,1.0); s("기사_공격력",V_E3AT,2)
    # 웨이브/스케일/강화
    s("웨이브간격",V_WGAP,1.2); s("웨이브간격감소",V_WDEC,0.1); s("웨이브최소간격",V_WMIN,0.5); s("최대적수",V_MAXEN,8)
    s("적성장배율",V_SCALE,1.22); s("처치골드",V_KILLGOLD,5); s("강화량",V_UP,2); s("강화스킬쿨배수",V_UPSK,0.85); s("레인Y",V_LANEY,-110)
    scale_line = seq[-5]  # 적성장배율 set 근처(코멘트용)
    # 진행
    s("게임상태",V_STATE,1); s("스테이지",V_STAGE,1); s("진격도",V_PROG,0); s("적배율",V_SCALECUR,1)
    sr("체력",V_HP,vrep("최대체력",V_MAXHP)); s("골드",V_GOLD,0); s("적수",V_ALIVE,0); s("공성중",V_SIEGE,0)
    sr("성문체력",V_GATECUR,vrep("성문기본체력",V_GATEHP))
    s("VY",V_VY,0); s("점프남음",V_JUMPL,1); s("점프이전키",V_PREVJ,0)
    s("검격타이머",V_SWT,0); s("검격이전키",V_PREVSW,0); s("스킬타이머",V_SKT,0); s("스킬이전키",V_PREVSK,0)
    s("무적",V_INVT,0); s("마우스이전",V_PREVM,0)
    s("적생성종류",V_SPTYPE,1); s("적생성X",V_SPX,235); sr("적생성Y",V_SPY,vrep("레인Y",V_LANEY)); s("웨이브타이머",V_WAVET,0)
    s("데미지표시값",V_DMGVAL,0); s("데미지표시x",V_DMGX,0); s("데미지표시y",V_DMGY,0); s("팝업종류",V_DMGKIND,0)
    s("데미지숫자",V_DMGDIG,0); s("데미지오프셋",V_DMGOFF,0); s("데미지글자수",V_DMGLEN,0); s("데미지자리",V_DMGPOS,0)
    seq.append(b_wait(bs, 0.3))
    seq.append(b_broadcast(bs, "게임시작", BR_START))
    seq.append(b_broadcast(bs, "스테이지시작", BR_STAGEGO))
    C(bs, seq)
    add_comment(bs, comments, seq[1],
        "🛠️ 개조 손잡이: 여기 숫자만 바꾸면 게임이 달라져요! 용사·적·진격 전부 여기서 정해져요.",
        x=460, y=20, w=340, h=110)
    for bid, b in bs.items():
        if b.get("opcode")=="data_setvariableto" and b.get("fields",{}).get("VARIABLE",[None,None])[1]==V_SCALE:
            add_comment(bs, comments, bid,
                "📈 적성장배율! 스테이지가 오를 때마다 적이 이만큼 '곱하기'로 세져요. 1.22 → 1.5 로 바꾸면 확 어려워져요.",
                x=460, y=150, w=340, h=120)
            break

    # ===== (B) 웨이브 스포너 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=520,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    dec_t = b_changevar(bs, "웨이브타이머", V_WAVET, -0.1)
    # if 웨이브타이머<=0 and 적수<최대적수
    c_t0 = b_not(bs, cmp_op("operator_gt", vrep("웨이브타이머", V_WAVET), 0))
    c_room = cmp_op("operator_lt", vrep("적수", V_ALIVE), vrep("최대적수", V_MAXEN))
    c_spawn = bool_op("operator_and", c_t0, c_room)
    # 종류 결정
    c_s1 = b_not(bs, cmp_op("operator_gt", vrep("스테이지", V_STAGE), 1))
    set_t1 = b_setvar(bs, "적생성종류", V_SPTYPE, 1)
    c_s3 = b_not(bs, cmp_op("operator_gt", vrep("스테이지", V_STAGE), 3))
    r01 = op("operator_random", 0, 1, key1="FROM", key2="TO"); v01 = op("operator_add", 1, r01)
    set_t2 = b_setvar(bs, "적생성종류", V_SPTYPE, v01)
    r02 = op("operator_random", 0, 2, key1="FROM", key2="TO"); v02 = op("operator_add", 1, r02)
    set_t3 = b_setvar(bs, "적생성종류", V_SPTYPE, v02)
    if_s3 = b_ifelse(bs, c_s3, set_t2, set_t3)
    if_s1 = b_ifelse(bs, c_s1, set_t1, if_s3)
    set_spx = b_setvar(bs, "적생성X", V_SPX, 235)
    set_spy = b_setvar(bs, "적생성Y", V_SPY, vrep("레인Y", V_LANEY))
    inc_al = b_changevar(bs, "적수", V_ALIVE, 1)
    bc_sp = b_broadcast_wait(bs, "적생성", BR_SPAWN)
    dec_amt = op("operator_multiply", op("operator_subtract", vrep("스테이지",V_STAGE), 1), vrep("웨이브간격감소", V_WDEC))
    gap = op("operator_subtract", vrep("웨이브간격", V_WGAP), dec_amt)
    set_wt = b_setvar(bs, "웨이브타이머", V_WAVET, gap)
    c_min = cmp_op("operator_lt", vrep("웨이브타이머", V_WAVET), vrep("웨이브최소간격", V_WMIN))
    set_min = b_setvar(bs, "웨이브타이머", V_WAVET, vrep("웨이브최소간격", V_WMIN))
    if_min = b_if(bs, c_min, set_min)
    C(bs, [if_s1, set_spx, set_spy, inc_al, bc_sp, set_wt, if_min])
    if_sp = b_if(bs, c_spawn, if_s1)
    C(bs, [dec_t, if_sp])
    # gate: 게임상태=1 and 공성중=0
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_nos = cmp_op("operator_equals", vrep("공성중", V_SIEGE), 0)
    c_pn = bool_op("operator_and", c_play, c_nos)
    if_pn = b_if(bs, c_pn, dec_t)
    w_sp = b_wait(bs, 0.1)
    C(bs, [if_pn, w_sp])
    fe_sp = b_forever(bs, if_pn)
    C(bs, [hb, fe_sp])
    add_comment(bs, comments, if_sp,
        "🌊 적이 오른쪽에서 웨이브로 몰려와요. 웨이브간격을 줄이면 우르르!",
        x=460, y=520, w=330, h=110)

    # ===== (C) 스테이지 시작 뿔피리 =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=380, y=520,
        fields={"BROADCAST_OPTION": ["스테이지시작", BR_STAGEGO]})
    ph, pp = b_sound(bs, 0, "horn")
    C(bs, [hc, ph, pp])

    # ===== (D) 감시 forever =====
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=760,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # if game=1 and 공성중=0 and 진격도>=스테이지길이 → 공성중=1, 성문등장
    c_p1 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_n1 = cmp_op("operator_equals", vrep("공성중", V_SIEGE), 0)
    c_prog = b_not(bs, cmp_op("operator_lt", vrep("진격도", V_PROG), vrep("스테이지길이", V_STAGELEN)))
    c_gate = bool_op("operator_and", bool_op("operator_and", c_p1, c_n1), c_prog)
    set_s1 = b_setvar(bs, "공성중", V_SIEGE, 1)
    bc_gate = b_broadcast(bs, "성문등장", BR_GATE)
    C(bs, [set_s1, bc_gate])
    if_gate = b_if(bs, c_gate, set_s1)
    # if game=1 and 체력<=0 → 게임상태=0, 게임오버
    c_p2 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_dead = b_not(bs, cmp_op("operator_gt", vrep("체력", V_HP), 0))
    c_over = bool_op("operator_and", c_p2, c_dead)
    set_s0 = b_setvar(bs, "게임상태", V_STATE, 0)
    bc_over = b_broadcast(bs, "게임오버", BR_OVER)
    C(bs, [set_s0, bc_over])
    if_over = b_if(bs, c_over, set_s0)
    w_d = b_wait(bs, 0.05)
    C(bs, [if_gate, if_over, w_d])
    fe_d = b_forever(bs, if_gate)
    C(bs, [hd, fe_d])

    return bs, comments

# ============================================================
#  용사
# ============================================================
def build_hero_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sh = b_show(bs); sz = b_setsize(bs, 60); rs = b_rotstyle(bs, "left-right")
    pd = b_pointdir(bs, 90); g0 = b_gotoxy(bs, -120, vrep("레인Y", V_LANEY)); fr = b_front(bs)
    swc = b_costume(bs, "용사_대기")
    C(bs, [h, sh, sz, rs, pd, g0, fr, swc])
    # 스테이지시작 리셋
    hr = gen(); bs[hr] = mk("event_whenbroadcastreceived", top=True, x=280, y=20,
        fields={"BROADCAST_OPTION": ["스테이지시작", BR_STAGEGO]})
    g1 = b_gotoxy(bs, -120, vrep("레인Y", V_LANEY)); pd1 = b_pointdir(bs, 90)
    sv0 = b_setvar(bs, "VY", V_VY, 0); sj = b_setvar(bs, "점프남음", V_JUMPL, 1)
    C(bs, [hr, g1, pd1, sv0, sj])

    # (B) 이동 + 진격 + 점프 + 중력 forever
    hb = gen(); bs[hb] = mk("event_whenflagclicked", top=True, x=20, y=240)
    # right
    pdr = b_pointdir(bs, 90); cxr = b_changex(bs, vrep("이동속도", V_MOVE))
    C(bs, [pdr, cxr])
    if_r = b_if(bs, b_keypressed(bs, "right arrow"), pdr)
    # left
    pdl = b_pointdir(bs, -90); cxl = b_changex(bs, op("operator_subtract", 0, vrep("이동속도", V_MOVE)))
    C(bs, [pdl, cxl])
    if_l = b_if(bs, b_keypressed(bs, "left arrow"), pdl)
    # clamp x to ±220
    c_xr = cmp_op("operator_gt", b_xpos(bs), 220); setxr = b_setx(bs, 220); if_cxr = b_if(bs, c_xr, setxr)
    c_xl = cmp_op("operator_lt", b_xpos(bs), -220); setxl = b_setx(bs, -220); if_cxl = b_if(bs, c_xl, setxl)
    # 진격 밀기: if 공성중=0 and key right and x>=진격기준X → 진격도 += 진격속도
    c_ns = cmp_op("operator_equals", vrep("공성중", V_SIEGE), 0)
    c_kr = b_keypressed(bs, "right arrow")
    c_fx = b_not(bs, cmp_op("operator_lt", b_xpos(bs), vrep("진격기준X", V_MARCHX)))
    c_march = bool_op("operator_and", bool_op("operator_and", c_ns, c_kr), c_fx)
    ch_prog = b_changevar(bs, "진격도", V_PROG, vrep("진격속도", V_MARCH))
    if_march = b_if(bs, c_march, ch_prog)
    # 점프 에지 감지: ↑ 눌림 && 직전엔 안 눌림 && 점프 남음 → 상승 속도 부여
    c_up = b_keypressed(bs, "up arrow")
    c_prevj0 = cmp_op("operator_equals", vrep("점프이전키", V_PREVJ), 0)
    c_hasj = cmp_op("operator_gt", vrep("점프남음", V_JUMPL), 0)
    c_jump = bool_op("operator_and", bool_op("operator_and", c_up, c_prevj0), c_hasj)
    set_vy = b_setvar(bs, "VY", V_VY, vrep("점프력", V_JUMP))
    dec_jl = b_changevar(bs, "점프남음", V_JUMPL, -1)
    js, jp = b_sound(bs, 80, "swing")
    C(bs, [set_vy, dec_jl, js, jp])
    if_jump = b_if(bs, c_jump, set_vy)
    set_prevj = b_setvar(bs, "점프이전키", V_PREVJ, b_keypressed(bs, "up arrow"))
    # 중력 + 수직
    ch_vy = b_changevar(bs, "VY", V_VY, vrep("중력", V_GRAV))
    ch_y = b_changey(bs, vrep("VY", V_VY))
    c_below = cmp_op("operator_lt", b_ypos(bs), vrep("레인Y", V_LANEY))
    setyf = b_sety(bs, vrep("레인Y", V_LANEY)); setvy0 = b_setvar(bs, "VY", V_VY, 0); setjl1 = b_setvar(bs, "점프남음", V_JUMPL, 1)
    C(bs, [setyf, setvy0, setjl1])
    if_floor = b_if(bs, c_below, setyf)
    # assemble play body
    body = [if_r, if_l, if_cxr, if_cxl, if_march, if_jump, set_prevj, ch_vy, ch_y, if_floor]
    C(bs, body)
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_play = b_if(bs, c_play, if_r)
    w_b = b_wait(bs, 0.025)
    C(bs, [if_play, w_b])
    fe_b = b_forever(bs, if_play)
    C(bs, [hb, fe_b])
    add_comment(bs, comments, if_march,
        "🏰 앞(진격기준X 너머)에서 →를 누르면 진격도가 차요. 가득 차면 성문이 나와요!",
        x=460, y=240, w=330, h=110)

    # (C) 검격 입력 forever
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=520, y=240)
    dec_swt = b_changevar(bs, "검격타이머", V_SWT, -1)
    # 검격입력 = key space OR (mousedown AND 마우스이전=0)
    c_sp = b_keypressed(bs, "space")
    c_md = b_mousedown(bs); c_pm0 = cmp_op("operator_equals", vrep("마우스이전", V_PREVM), 0)
    c_mclick = bool_op("operator_and", c_md, c_pm0)
    c_swin = bool_op("operator_or", c_sp, c_mclick)
    c_prevsw0 = cmp_op("operator_equals", vrep("검격이전키", V_PREVSW), 0)
    c_swready = b_not(bs, cmp_op("operator_gt", vrep("검격타이머", V_SWT), 0))
    c_dosw = bool_op("operator_and", bool_op("operator_and", c_swin, c_prevsw0), c_swready)
    sw_atk = b_costume(bs, "용사_검격")
    ssw, psw = b_sound(bs, 0, "swing")
    set_swt = b_setvar(bs, "검격타이머", V_SWT, vrep("검격쿨", V_SWCD))
    w_sw = b_wait(bs, 0.12); sw_idle = b_costume(bs, "용사_대기")
    C(bs, [sw_atk, ssw, psw, set_swt, w_sw, sw_idle])
    if_dosw = b_if(bs, c_dosw, sw_atk)
    set_prevsw = b_setvar(bs, "검격이전키", V_PREVSW, b_keypressed(bs, "space"))
    set_prevm = b_setvar(bs, "마우스이전", V_PREVM, b_mousedown(bs))
    c_play2 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    C(bs, [if_dosw, set_prevsw, set_prevm])
    if_play2 = b_if(bs, c_play2, if_dosw)
    w_c = b_wait(bs, 0.02)
    C(bs, [dec_swt, if_play2, w_c])
    fe_c = b_forever(bs, dec_swt)
    C(bs, [hc, fe_c])
    add_comment(bs, comments, if_dosw,
        "⚔️ Space(또는 클릭)=검격, X=스킬(광역). 스킬은 게이지가 다 차야 나가요.\n"
        "마우스 검격은 클릭 폴링+에지 디바운스(다른 게 가려도 눌려요).",
        x=980, y=240, w=340, h=130)

    # (D) 스킬 입력 forever
    hdd = gen(); bs[hdd] = mk("event_whenflagclicked", top=True, x=520, y=520)
    c_skt0 = cmp_op("operator_gt", vrep("스킬타이머", V_SKT), 0)
    dec_skt = b_changevar(bs, "스킬타이머", V_SKT, -1)
    if_skt = b_if(bs, c_skt0, dec_skt)
    c_kx = b_keypressed(bs, "x"); c_prevsk0 = cmp_op("operator_equals", vrep("스킬이전키", V_PREVSK), 0)
    c_skready = b_not(bs, cmp_op("operator_gt", vrep("스킬타이머", V_SKT), 0))
    c_dosk = bool_op("operator_and", bool_op("operator_and", c_kx, c_prevsk0), c_skready)
    sk_cos = b_costume(bs, "용사_스킬"); ssk, psk = b_sound(bs, 0, "skill")
    set_skt = b_setvar(bs, "스킬타이머", V_SKT, vrep("스킬쿨", V_SKCD))
    w_sk = b_wait(bs, 0.2); sk_idle = b_costume(bs, "용사_대기")
    C(bs, [sk_cos, ssk, psk, set_skt, w_sk, sk_idle])
    if_dosk = b_if(bs, c_dosk, sk_cos)
    set_prevsk = b_setvar(bs, "스킬이전키", V_PREVSK, b_keypressed(bs, "x"))
    c_play3 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    C(bs, [if_dosk, set_prevsk])
    if_play3 = b_if(bs, c_play3, if_dosk)
    w_dd = b_wait(bs, 0.02)
    C(bs, [if_skt, if_play3, w_dd])
    fe_dd = b_forever(bs, if_skt)
    C(bs, [hdd, fe_dd])

    # (E) 무적 타이머 감소 forever
    he = gen(); bs[he] = mk("event_whenflagclicked", top=True, x=980, y=520)
    c_inv0 = cmp_op("operator_gt", vrep("무적", V_INVT), 0)
    dec_inv = b_changevar(bs, "무적", V_INVT, -1)
    if_inv = b_if(bs, c_inv0, dec_inv)
    w_e = b_wait(bs, 0.03)
    C(bs, [if_inv, w_e])
    fe_e = b_forever(bs, if_inv)
    C(bs, [he, fe_e])

    return bs, comments

# ============================================================
#  검판정 (히트박스)
# ============================================================
def build_slash_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); sz = b_setsize(bs, 60); rs = b_rotstyle(bs, "left-right")
    C(bs, [h, hi, sz, rs])
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=20, y=200)
    # 갓 발동 창: 검격타이머 > 검격쿨 - 5
    thr = op("operator_subtract", vrep("검격쿨", V_SWCD), 5)
    c_win = cmp_op("operator_gt", vrep("검격타이머", V_SWT), thr)
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_show = bool_op("operator_and", c_win, c_play)
    # align: point in direction (of 용사)
    pdir = b_pointdir_r(bs, _of(bs, "용사", "direction"))
    c_face = cmp_op("operator_equals", _of(bs, "용사", "direction"), 90)
    kxr = _of(bs, "용사", "x position"); kyr = _of(bs, "용사", "y position")
    gxr = op("operator_add", kxr, vrep("검격범위", V_SWR))
    goto_r = b_gotoxy(bs, gxr, kyr)
    kxl = _of(bs, "용사", "x position"); kyl = _of(bs, "용사", "y position")
    gxl = op("operator_subtract", kxl, vrep("검격범위", V_SWR))
    goto_l = b_gotoxy(bs, gxl, kyl)
    if_align = b_ifelse(bs, c_face, goto_r, goto_l)
    show = b_show(bs)
    C(bs, [pdir, if_align, show])
    hide = b_hide(bs)
    if_win = b_ifelse(bs, c_show, pdir, hide)
    w = b_wait(bs, 0.02)
    C(bs, [if_win, w])
    fe = b_forever(bs, if_win)
    C(bs, [h2, fe])
    add_comment(bs, comments, if_win,
        "💥 검격 갓 발동 창에만 용사 앞에 나타나는 반달 히트박스! 닿은 적/성문에 데미지. "
        "검격범위를 키우면 더 멀리 베요.",
        x=460, y=200, w=340, h=130)
    return bs, comments

# ============================================================
#  스킬판정 (광역 히트박스)
# ============================================================
def build_skill_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs, "don't rotate")
    C(bs, [h, hi, rs])
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=20, y=200)
    thr = op("operator_subtract", vrep("스킬쿨", V_SKCD), 8)
    c_win = cmp_op("operator_gt", vrep("스킬타이머", V_SKT), thr)
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_show = bool_op("operator_and", c_win, c_play)
    kx = _of(bs, "용사", "x position"); ky = _of(bs, "용사", "y position")
    goto = b_gotoxy(bs, kx, ky)
    setsz = b_setsize(bs, vrep("스킬범위", V_SKR))
    fr = b_front(bs); show = b_show(bs); turn = b_turn(bs, 15)
    C(bs, [goto, setsz, fr, show, turn])
    hide = b_hide(bs)
    if_win = b_ifelse(bs, c_show, goto, hide)
    w = b_wait(bs, 0.02)
    C(bs, [if_win, w])
    fe = b_forever(bs, if_win)
    C(bs, [h2, fe])
    return bs, comments

# ============================================================
#  적 (스포너 + 클론 본체)
# ============================================================
def build_enemy_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ── 데미지팝업 헬퍼 ──
    def emit_popup(valexpr, xexpr, yexpr, kind):
        s1 = b_setvar(bs, "데미지표시값", V_DMGVAL, valexpr)
        s2 = b_setvar(bs, "데미지표시x", V_DMGX, xexpr)
        s3 = b_setvar(bs, "데미지표시y", V_DMGY, yexpr)
        s4 = b_setvar(bs, "팝업종류", V_DMGKIND, kind)
        bc = b_broadcast(bs, "데미지표시", BR_DMG)
        return [s1, s2, s3, s4, bc]

    # (A) 깃발
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); sz = b_setsize(bs, 55); rs = b_rotstyle(bs, "left-right"); orig0 = b_setvar(bs, "복제됨", V_EN_ISC, 0)
    C(bs, [h, hi, sz, rs, orig0])

    # (B) 적생성 → 클론 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["적생성", BR_SPAWN]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_EN_ISC), 0)
    cc = b_createclone(bs)
    if_c = b_if(bs, c_orig, cc)
    C(bs, [hb, if_c])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_EN_ISC, 1)
    set_type = b_setvar(bs, "적종류", V_EN_TYPE, vrep("적생성종류", V_SPTYPE))
    # 종류별 능력치
    def type_branch(type_val, hp_id, hp_nm, sp_id, sp_nm, at_id, at_nm, costume, size):
        hp_expr = op("operator_multiply", vrep(hp_nm, hp_id), vrep("적배율", V_SCALECUR))
        set_hp = b_setvar(bs, "내체력", V_EN_HP, hp_expr)
        set_sp = b_setvar(bs, "내속도", V_EN_SPD, vrep(sp_nm, sp_id))
        set_at = b_setvar(bs, "내공격력", V_EN_ATK, vrep(at_nm, at_id))
        swc = b_costume(bs, costume); szb = b_setsize(bs, size)
        C(bs, [set_hp, set_sp, set_at, swc, szb])
        return set_hp
    b1 = type_branch(1, V_E1HP, "잡졸_체력", V_E1SP, "잡졸_속도", V_E1AT, "잡졸_공격력", "잡졸", 45)
    b2 = type_branch(2, V_E2HP, "전사_체력", V_E2SP, "전사_속도", V_E2AT, "전사_공격력", "전사", 55)
    b3 = type_branch(3, V_E3HP, "기사_체력", V_E3SP, "기사_속도", V_E3AT, "기사_공격력", "기사", 70)
    if_t2 = b_ifelse(bs, cmp_op("operator_equals", vrep("적종류", V_EN_TYPE), 2), b2, b3)
    if_t1 = b_ifelse(bs, cmp_op("operator_equals", vrep("적종류", V_EN_TYPE), 1), b1, if_t2)
    set_hit0 = b_setvar(bs, "피격쿨", V_EN_HIT, 0)
    g0 = b_gotoxy(bs, vrep("적생성X", V_SPX), vrep("적생성Y", V_SPY))
    show = b_show(bs)

    # forever body
    # 1) 게임오버/강화 정리
    c_clean = bool_op("operator_or", cmp_op("operator_equals", vrep("게임상태", V_STATE), 0),
                                     cmp_op("operator_equals", vrep("게임상태", V_STATE), 2))
    dec_al_c = b_changevar(bs, "적수", V_ALIVE, -1); del_c = b_delclone(bs)
    C(bs, [dec_al_c, del_c])
    if_clean = b_if(bs, c_clean, dec_al_c)
    # 2) 게임상태=1: 전진 + 접촉 + 피격 + 처치
    # 전진: if x > 용사x: dir -90, x -= 내속도 else dir 90, x += 내속도
    heroX = _of(bs, "용사", "x position")
    c_ahead = cmp_op("operator_gt", b_xpos(bs), heroX)
    pdl = b_pointdir(bs, -90); mxl = b_changex(bs, op("operator_subtract", 0, vrep("내속도", V_EN_SPD)))
    C(bs, [pdl, mxl])
    pdr = b_pointdir(bs, 90); mxr = b_changex(bs, vrep("내속도", V_EN_SPD))
    C(bs, [pdr, mxr])
    if_move = b_ifelse(bs, c_ahead, pdl, pdr)
    setyl = b_sety(bs, vrep("레인Y", V_LANEY))
    # 접촉 데미지 (용사 무적 게이트 공유)
    c_tuser = b_touching(bs, "용사")
    c_inv0 = cmp_op("operator_equals", vrep("무적", V_INVT), 0)
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_contact = bool_op("operator_and", bool_op("operator_and", c_tuser, c_inv0), c_play)
    ch_hp = b_changevar(bs, "체력", V_HP, op("operator_subtract", 0, vrep("내공격력", V_EN_ATK)))
    set_inv = b_setvar(bs, "무적", V_INVT, vrep("무적시간", V_INV))
    hs, hp_ = b_sound(bs, 0, "hurt")
    C(bs, [ch_hp, set_inv, hs, hp_])
    if_contact = b_if(bs, c_contact, ch_hp)
    # 히트박스 피격 (피격쿨=0 and touching 검판정/스킬판정)
    c_hit0 = cmp_op("operator_equals", vrep("피격쿨", V_EN_HIT), 0)
    c_tsw = b_touching(bs, "검판정"); c_tsk = b_touching(bs, "스킬판정")
    c_thit = bool_op("operator_or", c_tsw, c_tsk)
    c_dohit = bool_op("operator_and", c_hit0, c_thit)
    # if touching 스킬판정: 내체력 -= 스킬공격력; 데미지값=스킬공격력 else -= 공격력
    dec_hp_sk = b_changevar(bs, "내체력", V_EN_HP, op("operator_subtract", 0, vrep("스킬공격력", V_SKATK)))
    setdv_sk = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("스킬공격력", V_SKATK))
    C(bs, [dec_hp_sk, setdv_sk])
    dec_hp_sw = b_changevar(bs, "내체력", V_EN_HP, op("operator_subtract", 0, vrep("공격력", V_ATK)))
    setdv_sw = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("공격력", V_ATK))
    C(bs, [dec_hp_sw, setdv_sw])
    if_skvssw = b_ifelse(bs, b_touching(bs, "스킬판정"), dec_hp_sk, dec_hp_sw)
    set_hitcd = b_setvar(bs, "피격쿨", V_EN_HIT, 6)
    hh, hhp = b_sound(bs, 0, "hit")
    setdx = b_setvar(bs, "데미지표시x", V_DMGX, b_xpos(bs)); setdy = b_setvar(bs, "데미지표시y", V_DMGY, b_ypos(bs))
    setk0 = b_setvar(bs, "팝업종류", V_DMGKIND, 0)
    bcd = b_broadcast(bs, "데미지표시", BR_DMG)
    C(bs, [if_skvssw, set_hitcd, hh, hhp, setdx, setdy, setk0, bcd])
    if_dohit = b_if(bs, c_dohit, if_skvssw)
    # 피격쿨 감소
    c_hitpos = cmp_op("operator_gt", vrep("피격쿨", V_EN_HIT), 0)
    dec_hitcd = b_changevar(bs, "피격쿨", V_EN_HIT, -1)
    if_hitdec = b_if(bs, c_hitpos, dec_hitcd)
    # 처치: 내체력 < 1
    c_kill = cmp_op("operator_lt", vrep("내체력", V_EN_HP), 1)
    add_gold = b_changevar(bs, "골드", V_GOLD, vrep("처치골드", V_KILLGOLD))
    dec_al_k = b_changevar(bs, "적수", V_ALIVE, -1)
    yk = op("operator_add", b_ypos(bs), 20)
    pop_g = emit_popup(vrep("처치골드", V_KILLGOLD), b_xpos(bs), yk, 1)
    cs, cp = b_sound(bs, 0, "coin")
    sw_boom = b_costume(bs, "폭발")
    csz = b_changesize(bs, 10); cgh = b_changeeffect(bs, "GHOST", 20); wboom = b_wait(bs, 0.02)
    C(bs, [csz, cgh, wboom])
    rep_boom = b_repeat(bs, 5, csz)
    del_k = b_delclone(bs)
    C(bs, [add_gold, dec_al_k] + pop_g + [cs, cp, sw_boom, rep_boom, del_k])
    if_kill = b_if(bs, c_kill, add_gold)

    play_body = [if_move, setyl, if_contact, if_dohit, if_hitdec, if_kill]
    C(bs, play_body)
    if_play = b_if(bs, c_play, if_move)
    w_body = b_wait(bs, 0.025)
    C(bs, [if_clean, if_play, w_body])
    fe = b_forever(bs, if_clean)
    C(bs, [ch, set1, set_type, if_t1, set_hit0, g0, show, fe])

    add_comment(bs, comments, if_move,
        "👣 적은 '용사한테 다가와서 부딪히기'만 해요(아주 단순!). 클론끼리 참조·충돌이 전혀 없어서 안 버벅여요.",
        x=460, y=380, w=340, h=130)
    return bs, comments

# ============================================================
#  성문
# ============================================================
def build_gate_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g0 = b_gotoxy(bs, vrep("성문시작X", V_GATESTARTX), -95); sz = b_setsize(bs, 100); swc = b_costume(bs, "성문_온전")
    C(bs, [h, hi, g0, sz, swc])

    # 성문등장
    hg = gen(); bs[hg] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["성문등장", BR_GATE]})
    set_gh = b_setvar(bs, "성문체력", V_GATECUR, op("operator_multiply", vrep("성문기본체력", V_GATEHP), vrep("적배율", V_SCALECUR)))
    swok = b_costume(bs, "성문_온전"); clr = b_cleargfx(bs); show = b_show(bs)
    glide = b_glide(bs, 0.4, vrep("성문공성X", V_GATEX), -95)
    # forever siege
    # 성문피해 헬퍼
    def emit_gatehit(dmg_rep):
        dec = b_changevar(bs, "성문체력", V_GATECUR, op("operator_subtract", 0, dmg_rep))
        gh, gp = b_sound(bs, 0, "gatehit")
        sdv = b_setvar(bs, "데미지표시값", V_DMGVAL, dmg_rep)
        sdx = b_setvar(bs, "데미지표시x", V_DMGX, b_xpos(bs))
        sdy = b_setvar(bs, "데미지표시y", V_DMGY, op("operator_add", b_ypos(bs), 30))
        sk0 = b_setvar(bs, "팝업종류", V_DMGKIND, 0)
        bcd = b_broadcast(bs, "데미지표시", BR_DMG)
        return [dec, gh, gp, sdv, sdx, sdy, sk0, bcd]
    hit_sw = emit_gatehit(vrep("공격력", V_ATK)); C(bs, hit_sw)
    hit_sk = emit_gatehit(vrep("스킬공격력", V_SKATK)); C(bs, hit_sk)
    if_hitsk = b_if(bs, b_touching(bs, "스킬판정"), hit_sk[0])
    if_hitsw = b_ifelse(bs, b_touching(bs, "검판정"), hit_sw[0], if_hitsk)
    # 균열 코스튬: if 성문체력 <= 성문기본체력×적배율×0.4
    thr = op("operator_multiply", op("operator_multiply", vrep("성문기본체력", V_GATEHP), vrep("적배율", V_SCALECUR)), 0.4)
    c_crack = b_not(bs, cmp_op("operator_gt", vrep("성문체력", V_GATECUR), thr))
    sw_crack = b_costume(bs, "성문_균열")
    if_crack = b_if(bs, c_crack, sw_crack)
    # 파괴: 성문체력<=0
    c_broke = b_not(bs, cmp_op("operator_gt", vrep("성문체력", V_GATECUR), 0))
    sw_ruin = b_costume(bs, "성문_잔해"); gbh, gbp = b_sound(bs, 0, "gatebreak")
    gh_on = b_changeeffect(bs, "GHOST", 12); gw = b_wait(bs, 0.03)
    C(bs, [gh_on, gw]); rep_break = b_repeat(bs, 8, gh_on)
    hide2 = b_hide(bs); set_s2 = b_setvar(bs, "게임상태", V_STATE, 2); bc_up = b_broadcast(bs, "강화등장", BR_UP)
    stop_this = gen(); bs[stop_this] = mk("control_stop", fields={"STOP_OPTION": ["this script", None]})
    bs[stop_this]["mutation"] = {"tagName": "mutation", "children": [], "hasnext": "false"}
    C(bs, [sw_ruin, gbh, gbp, rep_break, hide2, set_s2, bc_up, stop_this])
    if_broke = b_if(bs, c_broke, sw_ruin)
    siege_body = [if_hitsw, if_crack, if_broke]
    C(bs, siege_body)
    c_siege = bool_op("operator_and", cmp_op("operator_equals", vrep("게임상태", V_STATE), 1),
                                      cmp_op("operator_equals", vrep("공성중", V_SIEGE), 1))
    if_siege = b_if(bs, c_siege, if_hitsw)
    w_g = b_wait(bs, 0.03)
    C(bs, [if_siege, w_g])
    fe_g = b_forever(bs, if_siege)
    C(bs, [hg, set_gh, swok, clr, show, glide, fe_g])
    add_comment(bs, comments, if_siege,
        "🚪 진격 끝! 성문을 검격·스킬로 부수면 스테이지 클리어예요. 성문기본체력을 바꿔 난이도 조절.",
        x=460, y=200, w=340, h=130)
    return bs, comments

# ============================================================
#  강화패널
# ============================================================
def build_upgrade_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g = b_gotoxy(bs, 0, 20); sz = b_setsize(bs, 100); fr = b_front(bs)
    C(bs, [h, hi, g, sz, fr])

    hu = gen(); bs[hu] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["강화등장", BR_UP]})
    show = b_show(bs)
    k1 = b_keypressed(bs, "1"); k2 = b_keypressed(bs, "2"); k3 = b_keypressed(bs, "3"); k4 = b_keypressed(bs, "4")
    or12 = bool_op("operator_or", k1, k2); or123 = bool_op("operator_or", or12, k3); or1234 = bool_op("operator_or", or123, k4)
    wu = b_waituntil(bs, or1234)
    # 1 공격력 += 강화량
    ch_atk = b_changevar(bs, "공격력", V_ATK, vrep("강화량", V_UP))
    if_k1 = b_if(bs, b_keypressed(bs, "1"), ch_atk)
    # 2 최대체력 += 강화량; 체력 = 최대체력
    ch_max = b_changevar(bs, "최대체력", V_MAXHP, vrep("강화량", V_UP))
    set_full = b_setvar(bs, "체력", V_HP, vrep("최대체력", V_MAXHP))
    C(bs, [ch_max, set_full])
    if_k2 = b_if(bs, b_keypressed(bs, "2"), ch_max)
    # 3 이동속도 += 1
    ch_mv = b_changevar(bs, "이동속도", V_MOVE, 1)
    if_k3 = b_if(bs, b_keypressed(bs, "3"), ch_mv)
    # 4 스킬쿨 *= 강화스킬쿨배수, 하한 60
    mul = op("operator_multiply", vrep("스킬쿨", V_SKCD), vrep("강화스킬쿨배수", V_UPSK))
    set_skcd = b_setvar(bs, "스킬쿨", V_SKCD, mul)
    c_low = cmp_op("operator_lt", vrep("스킬쿨", V_SKCD), 60)
    set_60 = b_setvar(bs, "스킬쿨", V_SKCD, 60)
    if_low = b_if(bs, c_low, set_60)
    C(bs, [set_skcd, if_low])
    if_k4 = b_if(bs, b_keypressed(bs, "4"), set_skcd)
    su, sp = b_sound(bs, 0, "upgrade")
    hi2 = b_hide(bs); w1 = b_wait(bs, 0.15); bc_next = b_broadcast(bs, "다음스테이지", BR_NEXT)
    C(bs, [hu, show, wu, if_k1, if_k2, if_k3, if_k4, su, sp, hi2, w1, bc_next])
    add_comment(bs, comments, hu,
        "⬆️ 1·2·3·4 키로 강화! 적이 곱하기로 세지니 좋은 강화로 따라잡아요.\n"
        "1 공격력+ · 2 체력+회복 · 3 이동속도+ · 4 스킬쿨↓(하한60).",
        x=460, y=200, w=340, h=140)

    # 다음스테이지
    hn = gen(); bs[hn] = mk("event_whenbroadcastreceived", top=True, x=460, y=200,
        fields={"BROADCAST_OPTION": ["다음스테이지", BR_NEXT]})
    inc_stage = b_changevar(bs, "스테이지", V_STAGE, 1)
    set_scale1 = b_setvar(bs, "적배율", V_SCALECUR, 1)
    mul_sc = op("operator_multiply", vrep("적배율", V_SCALECUR), vrep("적성장배율", V_SCALE))
    set_sc_step = b_setvar(bs, "적배율", V_SCALECUR, mul_sc)
    reps = op("operator_subtract", vrep("스테이지", V_STAGE), 1)
    rep_sc = b_repeat(bs, reps, set_sc_step)
    set_gcur = b_setvar(bs, "성문체력", V_GATECUR, op("operator_multiply", vrep("성문기본체력", V_GATEHP), vrep("적배율", V_SCALECUR)))
    set_prog0 = b_setvar(bs, "진격도", V_PROG, 0); set_siege0 = b_setvar(bs, "공성중", V_SIEGE, 0)
    set_al0 = b_setvar(bs, "적수", V_ALIVE, 0); set_wt0 = b_setvar(bs, "웨이브타이머", V_WAVET, 0)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    bc_go = b_broadcast(bs, "스테이지시작", BR_STAGEGO)
    C(bs, [hn, inc_stage, set_scale1, rep_sc, set_gcur, set_prog0, set_siege0, set_al0, set_wt0, set_st1, bc_go])
    add_comment(bs, comments, set_scale1,
        "📈 적배율 = 적성장배율^(스테이지−1) 을 곱셈 반복으로 계산! 지수(곱하기)로 세지는 게 핵심.",
        x=900, y=200, w=340, h=120)
    return bs, comments

# ============================================================
#  데미지 (플로팅 숫자)
# ============================================================
def build_damage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); orig0 = b_setvar(bs, "복제됨", V_DMG_ISC, 0); rs = b_rotstyle(bs, "don't rotate")
    C(bs, [h, hi, orig0, rs])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["데미지표시", BR_DMG]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_DMG_ISC), 0)
    dval_r = vrep("데미지표시값", V_DMGVAL)
    len_b = gen(); bs[len_b] = mk("operator_length", inputs={"STRING": slot(dval_r)}); bs[dval_r]["parent"] = len_b
    set_len = b_setvar(bs, "데미지글자수", V_DMGLEN, len_b)
    set_pos1 = b_setvar(bs, "데미지자리", V_DMGPOS, 1)
    pos_r = vrep("데미지자리", V_DMGPOS); dval2 = vrep("데미지표시값", V_DMGVAL)
    letter_b = gen(); bs[letter_b] = mk("operator_letter_of", inputs={"LETTER": slot(pos_r), "STRING": slot(dval2)})
    bs[pos_r]["parent"] = letter_b; bs[dval2]["parent"] = letter_b
    set_digit = b_setvar(bs, "데미지숫자", V_DMGDIG, letter_b)
    pos2 = vrep("데미지자리", V_DMGPOS); pm1 = op("operator_subtract", pos2, 1)
    offL = op("operator_multiply", pm1, 14)
    lr = vrep("데미지글자수", V_DMGLEN); lm1 = op("operator_subtract", lr, 1); offC = op("operator_multiply", lm1, 7)
    offF = op("operator_subtract", offL, offC)
    set_off = b_setvar(bs, "데미지오프셋", V_DMGOFF, offF)
    cc = b_createclone(bs)
    inc_pos = b_changevar(bs, "데미지자리", V_DMGPOS, 1)
    w_sp = b_wait(bs, 0.02)
    C(bs, [set_digit, set_off, cc, inc_pos, w_sp])
    rep = b_repeat(bs, vrep("데미지글자수", V_DMGLEN), set_digit)
    C(bs, [set_len, set_pos1, rep])
    if_sp = b_if(bs, c_orig, set_len)
    C(bs, [hb, if_sp])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set1 = b_setvar(bs, "복제됨", V_DMG_ISC, 1); fr = b_front(bs)
    # switch costume to (데미지숫자 + 1)
    idx = op("operator_add", vrep("데미지숫자", V_DMGDIG), 1)
    sw = b_costume_idx(bs, idx)
    # 금색 분기
    c_gold = cmp_op("operator_equals", vrep("팝업종류", V_DMGKIND), 1)
    set_gold = b_seteffect(bs, "COLOR", 30)
    clr = b_cleargfx(bs)
    if_gold = b_ifelse(bs, c_gold, set_gold, clr)
    x_pos = op("operator_add", vrep("데미지표시x", V_DMGX), vrep("데미지오프셋", V_DMGOFF))
    g = b_gotoxy(bs, x_pos, vrep("데미지표시y", V_DMGY))
    clrg = b_seteffect(bs, "GHOST", 0); show = b_show(bs)
    chy = b_changey(bs, 4); cgh = b_changeeffect(bs, "GHOST", 8); w_an = b_wait(bs, 0.02)
    C(bs, [chy, cgh, w_an]); rep_an = b_repeat(bs, 12, chy)
    delc = b_delclone(bs)
    C(bs, [ch, set1, fr, sw, if_gold, g, clrg, show, rep_an, delc])
    return bs, comments

# ============================================================
#  UI 바 (costume-fill)
# ============================================================
def build_bar_blocks(kind):
    """kind: 'hp' | 'sk' | 'mr'"""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    pos = {"hp": (-150, 150), "sk": (-40, 150), "mr": (-90, 128)}[kind]
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, pos[0], pos[1]); fr = b_front(bs)
    # forever
    if kind == "hp":
        # if 체력<=0: costume 1 else round((체력/최대체력)*10)+1
        c_zero = b_not(bs, cmp_op("operator_gt", vrep("체력", V_HP), 0))
        set_empty = b_costume_idx(bs, op("operator_add", 0, 1))
        ratio = op("operator_divide", vrep("체력", V_HP), vrep("최대체력", V_MAXHP))
        idx = op("operator_add", b_round(bs, op("operator_multiply", ratio, 10)), 1)
        set_fill = b_costume_idx(bs, idx)
        body = b_ifelse(bs, c_zero, set_empty, set_fill)
    elif kind == "sk":
        # 충전율 = (스킬쿨-스킬타이머)/스킬쿨 ; 만충이면 costume 11
        c_ready = b_not(bs, cmp_op("operator_gt", vrep("스킬타이머", V_SKT), 0))
        set_full = b_costume_idx(bs, op("operator_add", 10, 1))
        chg = op("operator_divide", op("operator_subtract", vrep("스킬쿨", V_SKCD), vrep("스킬타이머", V_SKT)), vrep("스킬쿨", V_SKCD))
        idx = op("operator_add", b_round(bs, op("operator_multiply", chg, 10)), 1)
        set_fill = b_costume_idx(bs, idx)
        body = b_ifelse(bs, c_ready, set_full, set_fill)
    else:  # mr
        c_full = b_not(bs, cmp_op("operator_lt", vrep("진격도", V_PROG), vrep("스테이지길이", V_STAGELEN)))
        set_full = b_costume_idx(bs, op("operator_add", 10, 1))
        ratio = op("operator_divide", vrep("진격도", V_PROG), vrep("스테이지길이", V_STAGELEN))
        idx = op("operator_add", b_round(bs, op("operator_multiply", ratio, 10)), 1)
        set_fill = b_costume_idx(bs, idx)
        body = b_ifelse(bs, c_full, set_full, set_fill)
    w = b_wait(bs, 0.05)
    C(bs, [body, w])
    fe = b_forever(bs, body)
    C(bs, [h, show, g, fr, fe])
    return bs, comments

# ============================================================
#  게임오버
# ============================================================
def build_gameover_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g = b_gotoxy(bs, 0, 0); sz = b_setsize(bs, 100); fr = b_front(bs)
    c1 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1); wu1 = b_waituntil(bs, c1)
    c0 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0); wu2 = b_waituntil(bs, c0)
    show = b_show(bs)
    C(bs, [h, hi, g, sz, fr, wu1, wu2, show])
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
    hi_md5 = save_svg(HERO_IDLE_SVG); ha_md5 = save_svg(HERO_ATK_SVG); hs_md5 = save_svg(HERO_SKILL_SVG)
    slash_md5 = save_svg(SLASH_SVG); spin_md5 = save_svg(SPIN_SVG)
    e1_md5 = save_svg(E1_SVG); e2_md5 = save_svg(E2_SVG); e3_md5 = save_svg(E3_SVG); boom_md5 = save_svg(BOOM_SVG)
    gok_md5 = save_svg(GATE_OK_SVG); gcr_md5 = save_svg(GATE_CRACK_SVG); grn_md5 = save_svg(GATE_RUIN_SVG)
    card_md5 = save_svg(CARD_SVG); rs_md5 = save_svg(RESULT_SVG)
    dig_md5 = [save_svg(s) for s in DIGITS]
    hp_md5 = [save_svg(s) for s in HP_BARS]; sk_md5 = [save_svg(s) for s in SK_BARS]; mr_md5 = [save_svg(s) for s in MR_BARS]

    def save_wav(samples):
        b = _wav_bytes(samples); m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    swing_s, swing_n = save_wav(synth_swing()); skill_s, skill_n = save_wav(synth_skill())
    hurt_s, hurt_n = save_wav(synth_hurt()); hit_s, hit_n = save_wav(synth_hit())
    death_s, death_n = save_wav(synth_death()); coin_s, coin_n = save_wav(synth_coin())
    gh_s, gh_n = save_wav(synth_gatehit()); gb_s, gb_n = save_wav(synth_gatebreak())
    horn_s, horn_n = save_wav(synth_horn()); up_s, up_n = save_wav(synth_upgrade())
    def snd(name, md5, n):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "", "rate": SND_RATE, "sampleCount": n, "md5ext": f"{md5}.wav"}
    def cos(name, md5, rx=30, ry=30):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg", "assetId": md5, "md5ext": f"{md5}.svg", "rotationCenterX": rx, "rotationCenterY": ry}

    stage_b, stage_c = build_stage_blocks()
    hero_b, hero_c = build_hero_blocks()
    slash_b, slash_c = build_slash_blocks()
    skill_b, skill_c = build_skill_blocks()
    enemy_b, enemy_c = build_enemy_blocks()
    gate_b, gate_c = build_gate_blocks()
    up_b, up_c = build_upgrade_blocks()
    dmg_b, dmg_c = build_damage_blocks()
    hpb_b, hpb_c = build_bar_blocks("hp")
    skb_b, skb_c = build_bar_blocks("sk")
    mrb_b, mrb_c = build_bar_blocks("mr")
    go_b, go_c = build_gameover_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_ATK:["공격력",3], V_SKATK:["스킬공격력",8], V_MAXHP:["최대체력",6], V_MOVE:["이동속도",6], V_JUMP:["점프력",12],
            V_GRAV:["중력",-1], V_INV:["무적시간",20], V_SWCD:["검격쿨",8], V_SKCD:["스킬쿨",200], V_SWR:["검격범위",40], V_SKR:["스킬범위",130],
            V_MARCH:["진격속도",1.8], V_STAGELEN:["스테이지길이",900], V_MARCHX:["진격기준X",60], V_GATEHP:["성문기본체력",40], V_GATEX:["성문공성X",150], V_GATESTARTX:["성문시작X",240],
            V_E1HP:["잡졸_체력",4], V_E1SP:["잡졸_속도",2.5], V_E1AT:["잡졸_공격력",1], V_E2HP:["전사_체력",9], V_E2SP:["전사_속도",1.6], V_E2AT:["전사_공격력",1], V_E3HP:["기사_체력",18], V_E3SP:["기사_속도",1.0], V_E3AT:["기사_공격력",2],
            V_WGAP:["웨이브간격",1.2], V_WDEC:["웨이브간격감소",0.1], V_WMIN:["웨이브최소간격",0.5], V_MAXEN:["최대적수",8], V_SCALE:["적성장배율",1.22], V_KILLGOLD:["처치골드",5], V_UP:["강화량",2], V_UPSK:["강화스킬쿨배수",0.85], V_LANEY:["레인Y",-110],
            V_STATE:["게임상태",1], V_STAGE:["스테이지",1], V_PROG:["진격도",0], V_SCALECUR:["적배율",1], V_HP:["체력",6], V_GOLD:["골드",0], V_ALIVE:["적수",0], V_SIEGE:["공성중",0], V_GATECUR:["성문체력",40],
            V_VY:["VY",0], V_JUMPL:["점프남음",1], V_PREVJ:["점프이전키",0], V_SWT:["검격타이머",0], V_PREVSW:["검격이전키",0], V_SKT:["스킬타이머",0], V_PREVSK:["스킬이전키",0], V_INVT:["무적",0], V_PREVM:["마우스이전",0],
            V_SPTYPE:["적생성종류",1], V_SPX:["적생성X",235], V_SPY:["적생성Y",-110], V_WAVET:["웨이브타이머",0],
            V_DMGVAL:["데미지표시값",0], V_DMGX:["데미지표시x",0], V_DMGY:["데미지표시y",0], V_DMGKIND:["팝업종류",0], V_DMGDIG:["데미지숫자",0], V_DMGOFF:["데미지오프셋",0], V_DMGLEN:["데미지글자수",0], V_DMGPOS:["데미지자리",0],
        },
        "lists": {}, "broadcasts": {
            BR_START:"게임시작", BR_STAGEGO:"스테이지시작", BR_SPAWN:"적생성", BR_GATE:"성문등장", BR_DMG:"데미지표시", BR_UP:"강화등장", BR_NEXT:"다음스테이지", BR_OVER:"게임오버",
        },
        "blocks": stage_b, "comments": stage_c, "currentCostume": 0,
        "costumes": [{"name":"전장","dataFormat":"svg","assetId":bg_md5,"md5ext":f"{bg_md5}.svg","rotationCenterX":240,"rotationCenterY":180}],
        "sounds": [snd("horn", horn_s, horn_n)],
        "volume":100,"layerOrder":0,"tempo":60,"videoTransparency":50,"videoState":"on","textToSpeechLanguage":None
    }
    hero = {
        "isStage": False, "name": "용사", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hero_b, "comments": hero_c, "currentCostume": 0,
        "costumes": [cos("용사_대기", hi_md5, 26, 54), cos("용사_검격", ha_md5, 26, 54), cos("용사_스킬", hs_md5, 30, 54)],
        "sounds": [snd("swing", swing_s, swing_n), snd("skill", skill_s, skill_n)],
        "volume":100,"layerOrder":6,"visible":True,"x":-120,"y":-110,"size":60,"direction":90,"draggable":False,"rotationStyle":"left-right"
    }
    slash = {
        "isStage": False, "name": "검판정", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": slash_b, "comments": slash_c, "currentCostume": 0,
        "costumes": [cos("slash", slash_md5, 30, 30)], "sounds": [],
        "volume":100,"layerOrder":5,"visible":False,"x":0,"y":0,"size":60,"direction":90,"draggable":False,"rotationStyle":"left-right"
    }
    skill = {
        "isStage": False, "name": "스킬판정", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": skill_b, "comments": skill_c, "currentCostume": 0,
        "costumes": [cos("spin", spin_md5, 60, 60)], "sounds": [],
        "volume":100,"layerOrder":5,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }
    enemy = {
        "isStage": False, "name": "적",
        "variables": {V_EN_ISC:["복제됨",0], V_EN_HP:["내체력",4], V_EN_TYPE:["적종류",1], V_EN_SPD:["내속도",2.5], V_EN_ATK:["내공격력",1], V_EN_HIT:["피격쿨",0]},
        "lists": {}, "broadcasts": {}, "blocks": enemy_b, "comments": enemy_c, "currentCostume": 0,
        "costumes": [cos("잡졸", e1_md5, 23, 44), cos("전사", e2_md5, 28, 54), cos("기사", e3_md5, 35, 66), cos("폭발", boom_md5, 30, 30)],
        "sounds": [snd("hit", hit_s, hit_n), snd("death", death_s, death_n), snd("coin", coin_s, coin_n), snd("hurt", hurt_s, hurt_n)],
        "volume":100,"layerOrder":4,"visible":False,"x":235,"y":-110,"size":55,"direction":-90,"draggable":False,"rotationStyle":"left-right"
    }
    gate = {
        "isStage": False, "name": "성문", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": gate_b, "comments": gate_c, "currentCostume": 0,
        "costumes": [cos("성문_온전", gok_md5, 50, 130), cos("성문_균열", gcr_md5, 50, 130), cos("성문_잔해", grn_md5, 50, 130)],
        "sounds": [snd("gatehit", gh_s, gh_n), snd("gatebreak", gb_s, gb_n)],
        "volume":100,"layerOrder":3,"visible":False,"x":240,"y":-95,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }
    upgrade = {
        "isStage": False, "name": "강화패널", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": up_b, "comments": up_c, "currentCostume": 0,
        "costumes": [{"name":"card","bitmapResolution":1,"dataFormat":"svg","assetId":card_md5,"md5ext":f"{card_md5}.svg","rotationCenterX":200,"rotationCenterY":75}],
        "sounds": [snd("upgrade", up_s, up_n)],
        "volume":100,"layerOrder":9,"visible":False,"x":0,"y":20,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }
    damage_costumes = [cos(str(d), dig_md5[d], 14, 20) for d in range(10)]
    damage = {
        "isStage": False, "name": "데미지", "variables": {V_DMG_ISC:["복제됨",0]}, "lists": {}, "broadcasts": {},
        "blocks": dmg_b, "comments": dmg_c, "currentCostume": 0, "costumes": damage_costumes, "sounds": [],
        "volume":100,"layerOrder":10,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }
    def bar_target(name, blocks, cmts, md5s, x, y, order):
        return {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos(f"{name}_{i}", md5s[i], 70, 10) for i in range(11)], "sounds": [],
                "volume":100,"layerOrder":order,"visible":True,"x":x,"y":y,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    hpbar = bar_target("체력바", hpb_b, hpb_c, hp_md5, -150, 150, 11)
    skbar = bar_target("스킬게이지", skb_b, skb_c, sk_md5, -40, 150, 11)
    mrbar = bar_target("진격바", mrb_b, mrb_c, mr_md5, -90, 128, 11)
    gameover = {
        "isStage": False, "name": "게임오버", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": go_b, "comments": go_c, "currentCostume": 0,
        "costumes": [{"name":"패배","bitmapResolution":1,"dataFormat":"svg","assetId":rs_md5,"md5ext":f"{rs_md5}.svg","rotationCenterX":180,"rotationCenterY":80}],
        "sounds": [], "volume":100,"layerOrder":12,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }

    monitors = [
        {"id": V_STAGE, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"스테이지"},"spriteName":None,
         "value":1,"width":0,"height":0,"x":330,"y":5,"visible":True,"sliderMin":0,"sliderMax":100,"isDiscrete":True},
    ]
    project = {
        "targets": [stage, hero, slash, skill, enemy, gate, upgrade, damage, hpbar, skbar, mrbar, gameover],
        "monitors": monitors, "extensions": [],
        "meta": {"semver":"3.0.0","vm":"13.7.4-svg","agent":"hero-rush-builder"}
    }
    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f: json.dump(project, f, ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK): zf.write(f"{WORK}/{fn}", fn)
    with open(pj, "r", encoding="utf-8") as f: json.load(f)
    print(f"wrote {OUTPUT}")
    for nm, b in [("stage",stage_b),("용사",hero_b),("검판정",slash_b),("스킬판정",skill_b),("적",enemy_b),
                  ("성문",gate_b),("강화패널",up_b),("데미지",dmg_b),("체력바",hpb_b),("스킬게이지",skb_b),("진격바",mrb_b),("게임오버",go_b)]:
        print(f"  {nm:8s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
