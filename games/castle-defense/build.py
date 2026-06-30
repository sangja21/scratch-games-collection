#!/usr/bin/env python3
"""캐슬 디펜스 (castle-defense) — 클래식 로그라이트 타워디펜스.

길(웨이포인트 S자)을 따라 성으로 행진하는 고블린·오크·트롤을, 잔디 위에 포탑을
지어 막아낸다. 포탑은 사거리 안 '가장 가까운' 몬스터에게 자동으로 쏜다(화살탑=
싸고 빠름 / 대포탑=느리고 광역 / 마법탑=강함). 몬스터를 잡으면 골드가 쌓이고,
웨이브를 클리어할 때마다 강화 카드 넷 중 하나를 1·2·3·4 키로 고른다. 성체력이
0이 되면 GAME OVER. 점수 = 도달한 웨이브.

베이스: games/magic-survivor/build.py
  - 한글 튜닝 변수 일괄 초기화(매직넘버 0) / 조준요청 broadcast-and-wait 최솟값
    리덕션(다포탑 + 조준중 락 순차) / 타격 broadcast-and-wait 광역/단일 데미지 통일 /
    플로팅 숫자(say 미사용, 흰/금 두 세트) / 강화 택1 패널 / 게임오버 배너 /
    클론 스포너 + 복제됨 가드 / 폭발 연출 / 전용 합성 효과음(_wav_bytes·synth_*) /
    add_comment 가이드 투어.

★ 모든 조절 값(43개)을 한글 전역 변수로만 노출, 코드 어디서도 매직넘버를 쓰지
  않는다(연출용 repeat 5 / 도달반경 비교 같은 소수 인라인만 허용). 초기화는 전부
  Stage 깃발 클릭 한 스크립트에 모은다. 길은 경로X/경로Y 리스트 6점.
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "캐슬_디펜스.sb3")

# ============================================================
#  효과음 합성 (전용 사운드 11종) — 결정적 생성
# ============================================================
SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    """float 샘플(-1..1) 리스트 → 16-bit PCM mono WAV 바이트 (결정적)."""
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_arrow(rate=SND_RATE):
    """화살탑 발사 — 짧고 높은 '팅' (800→400Hz 하강 처프, 0.07초, 빠른 감쇠)."""
    N = int(rate * 0.07); out = []
    for i in range(N):
        t = i / rate
        f = 400 + 400 * math.exp(-t * 30)         # 800Hz → 400Hz
        env = math.exp(-t * 34)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.5)
    return out

def synth_cannon(rate=SND_RATE):
    """대포탑 발사 — 둔탁한 저음 '쿵' (노이즈 + 60Hz thump, 0.22초). 결정적."""
    N = int(rate * 0.22); out = []
    rng = random.Random(20240701)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 13)
        white = rng.random() * 2 - 1
        lp = lp + 0.40 * (white - lp)
        thump = math.sin(2 * math.pi * (55 + 35 * math.exp(-t * 22)) * t)
        s = (lp * 0.5 + thump * 0.8) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_magic(rate=SND_RATE):
    """마법탑 발사 — 반짝이는 화음 차임 (1200/1600/2400Hz, 0.18초 페이드)."""
    N = int(rate * 0.18); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 11)
        s = (math.sin(2*math.pi*1200*t) + 0.7*math.sin(2*math.pi*1600*t)
             + 0.5*math.sin(2*math.pi*2400*t)) / 2.2
        out.append(s * env * 0.5)
    return out

def synth_hit(rate=SND_RATE):
    """몬스터 피격 — 아주 짧은 '틱' (2kHz 클릭, 0.03초)."""
    N = int(rate * 0.03); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 90)
        out.append(math.sin(2 * math.pi * 2000 * t) * env * 0.5)
    return out

def synth_kill(rate=SND_RATE):
    """몬스터 처치 — '펑' 폭발 (노이즈 + 저음 thump, 0.3초). 결정적."""
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

def synth_coin(rate=SND_RATE):
    """골드 획득 — 동전 '딩' (988→1319Hz 두 톤 빠른 상승, 0.12초)."""
    N = int(rate * 0.12); out = []
    for i in range(N):
        t = i / rate
        f = 988 if t < 0.04 else 1319
        env = math.exp(-t * 12)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.45)
    return out

def synth_castlehit(rate=SND_RATE):
    """성 피격 — 거친 저음 충격 + 경보 (120Hz 사각파 + 하강, 0.25초)."""
    N = int(rate * 0.25); out = []
    for i in range(N):
        t = i / rate
        f = 120 + 60 * math.exp(-t * 8)
        sq = 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0
        env = math.exp(-t * 9)
        out.append(sq * env * 0.45)
    return out

def synth_horn(rate=SND_RATE):
    """웨이브 시작 뿔피리 — 묵직한 톱니파 (180Hz, 0.4초, 느린 어택)."""
    N = int(rate * 0.40); out = []
    for i in range(N):
        t = i / rate
        ph = (180 * t) % 1.0
        saw = 2 * ph - 1
        atk = min(1.0, t / 0.08)
        env = atk * math.exp(-t * 3.0)
        out.append(saw * env * 0.4)
    return out

def synth_build(rate=SND_RATE):
    """설치 성공 — '척' (낮은 정현파 + 클릭, 0.1초)."""
    N = int(rate * 0.10); out = []
    for i in range(N):
        t = i / rate
        click = 1.0 if t < 0.006 else 0.0
        body = math.sin(2 * math.pi * 320 * t) * math.exp(-t * 20)
        out.append((body * 0.7 + click * 0.6) * 0.5)
    return out

def synth_error(rate=SND_RATE):
    """설치 실패 — 낮은 '붕' 버저 (150Hz 사각파, 0.15초)."""
    N = int(rate * 0.15); out = []
    for i in range(N):
        t = i / rate
        sq = 1.0 if math.sin(2 * math.pi * 150 * t) > 0 else -1.0
        env = math.exp(-t * 7)
        out.append(sq * env * 0.4)
    return out

def synth_upgrade(rate=SND_RATE):
    """강화 선택 — 상승 아르페지오 (523→659→784Hz 3음, 0.3초)."""
    N = int(rate * 0.30); out = []
    for i in range(N):
        t = i / rate
        f = 523 if t < 0.1 else (659 if t < 0.2 else 784)
        env = math.exp(-((t % 0.1)) * 14)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.45)
    return out

def synth_repair(rate=SND_RATE):
    """성 수리 — 따뜻한 '띠링' 회복음 (660→880Hz 두 톤 상승 + 살짝 화음, 0.22초)."""
    N = int(rate * 0.22); out = []
    for i in range(N):
        t = i / rate
        f = 660 if t < 0.09 else 880
        env = math.exp(-((t % 0.09)) * 10)
        s = (math.sin(2 * math.pi * f * t) + 0.4 * math.sin(2 * math.pi * f * 1.5 * t)) / 1.4
        out.append(s * env * 0.45)
    return out

def synth_thunder(rate=SND_RATE):
    """전체 번개 주문 — 날카로운 '쩍' 크랙 + 묵직한 저음 우르릉(서브베이스). 0.6초, 결정적."""
    N = int(rate * 0.60); out = []
    rng = random.Random(20240809)
    lp = 0.0
    for i in range(N):
        t = i / rate
        # 초반 날카로운 '쩍' 크랙 — 밝은 노이즈가 아주 빠르게 감쇠
        crack = (rng.random() * 2 - 1) * math.exp(-t * 26) * 0.8
        # 본체 우르릉 엔벨로프 (빠른 어택, 느린 감쇠)
        env = min(1.0, t / 0.02) * math.exp(-t * 3.0)
        white = rng.random() * 2 - 1
        lp = lp + 0.10 * (white - lp)                          # 더 낮은 컷오프(묵직)
        rumble = math.sin(2 * math.pi * (40 + 20 * math.exp(-t * 2.5)) * t)
        sub = math.sin(2 * math.pi * 30 * t) * 0.45            # 깊은 서브베이스
        s = (lp * 0.9 + rumble * 0.6 + sub) * env + crack
        out.append(max(-1, min(1, s)))
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

PATH_COLOR = "#C2A86B"   # 길색 — 건설커서가 touching color 로 검사하는 단일 돌길 색

# -------- 배경: 잔디 + S자 돌길(길색) + 성터 --------
# 웨이포인트(scratch)→SVG: svgX=scratchX+240, svgY=180-scratchY
#  (-240,70)->(0,110) (-120,70)->(120,110) (-120,-50)->(120,230)
#  (40,-50)->(280,230) (40,90)->(280,90) (170,90)->(410,90) 성(205,90)->(445,90)
random.seed(11)
grass_tiles = []
for ty in range(0, 360, 30):
    for tx in range(0, 480, 30):
        shade = random.choice(["#6FBF4A", "#67B544", "#74C551"])
        grass_tiles.append(f'<rect x="{tx}" y="{ty}" width="30" height="30" fill="{shade}"/>')
GRASS = "\n    ".join(grass_tiles)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#6FBF4A"/>
  <g>
    {GRASS}
  </g>
  <polyline points="0,110 120,110 120,230 280,230 280,90 460,90" fill="none"
            stroke="#9A8450" stroke-width="40" stroke-linejoin="round" stroke-linecap="round"/>
  <polyline points="0,110 120,110 120,230 280,230 280,90 460,90" fill="none"
            stroke="{PATH_COLOR}" stroke-width="32" stroke-linejoin="round" stroke-linecap="round"/>
  <rect x="430" y="56" width="50" height="68" rx="4" fill="#8D8378" opacity="0.5"/>
  <rect x="6" y="6" width="468" height="348" rx="10" fill="none" stroke="#3E5C28" stroke-width="6" opacity="0.7"/>
</svg>"""

# -------- 성 (돌탑 + 깃발) --------
CASTLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="92" viewBox="0 0 80 92">
  <ellipse cx="40" cy="86" rx="30" ry="5" fill="#000000" opacity="0.25"/>
  <rect x="14" y="40" width="52" height="44" fill="#9E9E9E" stroke="#616161" stroke-width="2"/>
  <rect x="10" y="30" width="14" height="20" fill="#BDBDBD" stroke="#616161" stroke-width="2"/>
  <rect x="56" y="30" width="14" height="20" fill="#BDBDBD" stroke="#616161" stroke-width="2"/>
  <rect x="33" y="22" width="14" height="28" fill="#CFCFCF" stroke="#616161" stroke-width="2"/>
  <rect x="30" y="58" width="20" height="26" rx="3" fill="#5D4037"/>
  <rect x="20" y="50" width="8" height="8" fill="#757575"/>
  <rect x="52" y="50" width="8" height="8" fill="#757575"/>
  <line x1="40" y1="22" x2="40" y2="4" stroke="#5D4037" stroke-width="2"/>
  <polygon points="40,5 62,11 40,17" fill="#E53935"/>
</svg>"""

# -------- 몬스터 코스튬: 고블린(약) / 오크(중) / 트롤(강) / 폭발 --------
GOBLIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="55" rx="13" ry="3" fill="#000000" opacity="0.25"/>
  <ellipse cx="30" cy="34" rx="14" ry="16" fill="#7CB342" stroke="#558B2F" stroke-width="2"/>
  <polygon points="16,22 12,10 24,18" fill="#7CB342" stroke="#558B2F" stroke-width="1.5"/>
  <polygon points="44,22 48,10 36,18" fill="#7CB342" stroke="#558B2F" stroke-width="1.5"/>
  <circle cx="24" cy="32" r="3" fill="#FFEB3B"/>
  <circle cx="36" cy="32" r="3" fill="#FFEB3B"/>
  <circle cx="24" cy="32" r="1.4" fill="#000"/>
  <circle cx="36" cy="32" r="1.4" fill="#000"/>
  <path d="M23 42 Q30 47 37 42" fill="none" stroke="#33691E" stroke-width="2"/>
</svg>"""

ORC_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="56" rx="16" ry="3" fill="#000000" opacity="0.28"/>
  <rect x="14" y="34" width="32" height="20" rx="4" fill="#6D4C41" stroke="#3E2723" stroke-width="2"/>
  <ellipse cx="30" cy="28" rx="16" ry="15" fill="#7E9B6B" stroke="#4B5D3A" stroke-width="2.5"/>
  <polygon points="22,40 24,33 26,40" fill="#FFFFFF"/>
  <polygon points="34,40 36,33 38,40" fill="#FFFFFF"/>
  <circle cx="24" cy="26" r="3" fill="#D32F2F"/>
  <circle cx="36" cy="26" r="3" fill="#D32F2F"/>
  <circle cx="24" cy="26" r="1.4" fill="#000"/>
  <circle cx="36" cy="26" r="1.4" fill="#000"/>
</svg>"""

TROLL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="57" rx="19" ry="3" fill="#000000" opacity="0.3"/>
  <rect x="10" y="30" width="12" height="24" rx="5" fill="#78909C" stroke="#37474F" stroke-width="2"/>
  <rect x="38" y="30" width="12" height="24" rx="5" fill="#78909C" stroke="#37474F" stroke-width="2"/>
  <rect x="16" y="26" width="28" height="30" rx="7" fill="#90A4AE" stroke="#37474F" stroke-width="3"/>
  <ellipse cx="30" cy="20" rx="15" ry="14" fill="#78909C" stroke="#37474F" stroke-width="3"/>
  <circle cx="24" cy="20" r="3.2" fill="#FFD54F"/>
  <circle cx="36" cy="20" r="3.2" fill="#FFD54F"/>
  <circle cx="24" cy="20" r="1.5" fill="#000"/>
  <circle cx="36" cy="20" r="1.5" fill="#000"/>
  <polygon points="25,30 27,26 29,30" fill="#FFFFFF"/>
  <polygon points="31,30 33,26 35,30" fill="#FFFFFF"/>
</svg>"""

EXPLOSION_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30, 30, 29, 12, 12)}" fill="#FF6F00" stroke="#E65100" stroke-width="1"/>
  <polygon points="{_star_pts(30, 30, 21, 8, 12, rot=0.262)}" fill="#FFB300"/>
  <circle cx="30" cy="30" r="12" fill="#FFEB3B"/>
  <circle cx="30" cy="30" r="5"  fill="#FFFFFF"/>
</svg>"""

# -------- 포탑 코스튬: 화살탑 / 대포탑 / 마법탑 --------
ARROWTOWER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="70" viewBox="0 0 60 70">
  <ellipse cx="30" cy="64" rx="18" ry="4" fill="#000000" opacity="0.25"/>
  <rect x="18" y="34" width="24" height="30" fill="#8D6E63" stroke="#5D4037" stroke-width="2"/>
  <polygon points="14,34 46,34 30,12" fill="#A1887F" stroke="#5D4037" stroke-width="2"/>
  <circle cx="30" cy="26" r="6" fill="#5D4037"/>
  <rect x="22" y="44" width="16" height="6" fill="#6D4C41"/>
  <line x1="30" y1="26" x2="48" y2="26" stroke="#3E2723" stroke-width="2"/>
  <polygon points="48,22 56,26 48,30" fill="#3E2723"/>
</svg>"""

CANNONTOWER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="70" viewBox="0 0 60 70">
  <ellipse cx="30" cy="64" rx="18" ry="4" fill="#000000" opacity="0.25"/>
  <rect x="13" y="46" width="34" height="18" rx="3" fill="#78909C" stroke="#37474F" stroke-width="2"/>
  <rect x="20" y="40" width="20" height="9" rx="2" fill="#546E7A" stroke="#263238" stroke-width="2"/>
  <g transform="rotate(-30 30 42)">
    <rect x="24" y="6" width="14" height="38" rx="7" fill="#263238" stroke="#000000" stroke-width="2"/>
    <ellipse cx="31" cy="7" rx="7" ry="2.5" fill="#000000"/>
  </g>
  <circle cx="46" cy="16" r="6" fill="#212121" stroke="#000000" stroke-width="1"/>
  <circle cx="30" cy="46" r="4" fill="#263238"/>
</svg>"""

MAGICTOWER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="70" viewBox="0 0 60 70">
  <ellipse cx="30" cy="64" rx="18" ry="4" fill="#000000" opacity="0.25"/>
  <rect x="20" y="40" width="20" height="24" fill="#7E57C2" stroke="#4527A0" stroke-width="2"/>
  <polygon points="16,40 44,40 30,22" fill="#9575CD" stroke="#4527A0" stroke-width="2"/>
  <rect x="26" y="50" width="8" height="10" fill="#4527A0"/>
  <circle cx="30" cy="14" r="12" fill="#4FC3F7" opacity="0.30"/>
  <circle cx="30" cy="14" r="7.5" fill="#4FC3F7" stroke="#0288D1" stroke-width="1.5"/>
  <circle cx="27" cy="11" r="2.5" fill="#FFFFFF"/>
  <polygon points="47,9 49,13 47,17 45,13" fill="#FFF59D"/>
  <polygon points="12,19 13.5,22 12,25 10.5,22" fill="#FFF59D"/>
</svg>"""

# -------- 포탑탄 코스튬: 화살 / 포탄 / 마법구슬 --------
ARROW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <line x1="6" y1="20" x2="30" y2="20" stroke="#6D4C41" stroke-width="3"/>
  <polygon points="30,14 38,20 30,26" fill="#9E9E9E" stroke="#424242" stroke-width="1"/>
  <polygon points="6,20 12,16 12,24" fill="#A1887F"/>
</svg>"""

CANNONBALL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="11" fill="#37474F" stroke="#263238" stroke-width="2"/>
  <circle cx="16" cy="16" r="3" fill="#78909C" opacity="0.8"/>
</svg>"""

MAGICORB_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="14" fill="#7E57C2" opacity="0.4"/>
  <polygon points="{_star_pts(20, 20, 13, 5, 5, rot=-1.571)}" fill="#B388FF" opacity="0.9"/>
  <circle cx="20" cy="20" r="6" fill="#EDE7F6"/>
  <circle cx="20" cy="20" r="3" fill="#FFFFFF"/>
</svg>"""

# -------- 건설커서: 작은 설치 마커(십자선) — 충돌 판정이 '중앙 점'만 되도록 작게 유지 --------
# (예전엔 r=54 큰 사거리 원이라 touching 판정 footprint 가 지름 108px → 길에 항상 걸려 설치가 거의 불가했음.
#  큰 원을 없애 커서의 불투명 픽셀을 중앙 작은 마커로 줄임 → 중앙이 잔디면 어디든 설치 가능.)
CURSOR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <circle cx="60" cy="60" r="8" fill="#FFEB3B" opacity="0.85" stroke="#F57F17" stroke-width="2"/>
  <line x1="60" y1="51" x2="60" y2="69" stroke="#F57F17" stroke-width="3"/>
  <line x1="51" y1="60" x2="69" y2="60" stroke="#F57F17" stroke-width="3"/>
</svg>"""

# -------- 팔레트 (4버튼: 화살/대포/마법 + 성수리; 해금 상태별 4코스튬) --------
#  가로 472px 로 넓혀 4번째 '성수리' 버튼(항상 사용 가능)을 추가. 버튼 폭 112, 간격 4.
#  버튼 중심 SVG x: 62 / 178 / 294 / 410 → rotationCenterX=236 기준 scratch x: -174/-58/58/174.
PAL_W  = 472
PAL_BW = 112                       # 버튼 폭
def _pal_btnx(i):                  # 1..4 버튼 좌측 x
    return 6 + (i - 1) * (PAL_BW + 4)
def _palette_svg(cannon_unlocked, magic_unlocked):
    cx = PAL_BW // 2
    def btn(x, color, n, label, price, locked):
        op = "0.45" if locked else "1"
        lock = (f'<text x="{x+cx}" y="32" text-anchor="middle" font-family="Arial" '
                f'font-size="20">🔒</text>') if locked else ""
        return (f'<g opacity="{op}">'
                f'<rect x="{x}" y="8" width="{PAL_BW}" height="54" rx="8" fill="{color}" '
                f'stroke="#FFFFFF" stroke-width="2"/>'
                f'<text x="{x+10}" y="34" font-family="Arial" font-size="20" font-weight="bold" '
                f'fill="#FFFFFF">{n}</text>'
                f'<text x="{x+cx}" y="30" text-anchor="middle" font-family="Arial" font-size="13" '
                f'fill="#FFFFFF">{label}</text>'
                f'<text x="{x+cx}" y="50" text-anchor="middle" font-family="Arial" font-size="13" '
                f'fill="#FFF59D">{price}</text></g>') + lock
    def cross(gx, gy, s, color="#69F0AE"):   # 녹십자 아이콘 (성수리 표식)
        return (f'<rect x="{gx-s}" y="{gy-s/3:.1f}" width="{2*s}" height="{2*s/3:.1f}" rx="1" fill="{color}"/>'
                f'<rect x="{gx-s/3:.1f}" y="{gy-s}" width="{2*s/3:.1f}" height="{2*s}" rx="1" fill="{color}"/>')
    x4 = _pal_btnx(4)
    repair = btn(x4, "#C62828", "4", "성수리", "60", False) + cross(x4 + PAL_BW - 16, 18, 6)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{PAL_W}" height="70" viewBox="0 0 {PAL_W} 70">
  <rect x="0" y="0" width="{PAL_W}" height="70" rx="10" fill="#263238" opacity="0.92" stroke="#FFD54F" stroke-width="2"/>
  {btn(_pal_btnx(1), "#2E7D32", "1", "화살탑", "50", False)}
  {btn(_pal_btnx(2), "#1565C0", "2", "대포탑", "100", not cannon_unlocked)}
  {btn(_pal_btnx(3), "#6A1B9A", "3", "마법탑", "150", not magic_unlocked)}
  {repair}
</svg>"""

PALETTE_SVGS = [
    _palette_svg(False, False),   # 둘다잠금
    _palette_svg(True,  False),   # 대포해금
    _palette_svg(False, True),    # 마법해금
    _palette_svg(True,  True),    # 모두해금
]

# -------- 선택표시: 지금 고른 포탑 버튼을 노란 테두리로 강조 (별도 스프라이트) --------
HIGHLIGHT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="64" viewBox="0 0 120 64">
  <rect x="3" y="3" width="114" height="58" rx="10" fill="#FFEB3B" opacity="0.18"/>
  <rect x="3" y="3" width="114" height="58" rx="10" fill="none" stroke="#FFEB3B" stroke-width="5"/>
</svg>"""

# -------- 강화카드: 4선택지 --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="150" viewBox="0 0 400 150">
  <rect x="4" y="4" width="392" height="142" rx="14" fill="#1A237E" opacity="0.95" stroke="#FFD54F" stroke-width="4"/>
  <text x="200" y="30" text-anchor="middle" fill="#FFD54F" font-family="Arial" font-size="20" font-weight="bold">웨이브 클리어! 강화 선택</text>
  <rect x="12" y="44" width="88" height="92" rx="10" fill="#C62828" stroke="#FFFFFF" stroke-width="2"/>
  <text x="56" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">1</text>
  <text x="56" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">공격력+</text>
  <rect x="106" y="44" width="88" height="92" rx="10" fill="#2E7D32" stroke="#FFFFFF" stroke-width="2"/>
  <text x="150" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">2</text>
  <text x="150" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">사거리+</text>
  <rect x="200" y="44" width="88" height="92" rx="10" fill="#1565C0" stroke="#FFFFFF" stroke-width="2"/>
  <text x="244" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">3</text>
  <text x="244" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">연사+</text>
  <rect x="294" y="44" width="88" height="92" rx="10" fill="#6A1B9A" stroke="#FFFFFF" stroke-width="2"/>
  <text x="338" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">4</text>
  <text x="338" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">골드+</text>
</svg>"""

# -------- 게임오버 배너 --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="68" text-anchor="middle" fill="#E53935" font-family="Arial" font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="20">도달한 웨이브는 왼쪽 위에서!</text>
  <text x="180" y="136" text-anchor="middle" fill="#FFCDD2" font-family="Arial" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# -------- 번개효과: 화면 전체를 덮는 흰 번쩍 플래시 + 내리꽂는 지그재그 번개 줄기 --------
FLASH_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#FFFFFF"/>
</svg>"""

def _lightning_svg(seed):
    """위에서 내리꽂는 지그재그 번개 가닥 2~3개 (흰 코어 + 연노랑 글로우 + 곁가지) + 옅은 흰 플래시.
       seed 별로 모양이 달라 빠르게 코스튬을 바꾸면 가닥이 번쩍이는 느낌. 결정적."""
    rng = random.Random(seed)
    parts = ['<rect width="480" height="360" fill="#FFFFFF" opacity="0.30"/>']
    def bolt(x0):
        pts = [(x0, 0.0)]
        x, y = x0, 0.0
        while y < 360:
            y += rng.randint(34, 56)
            x += rng.randint(-46, 46)
            x = max(24, min(456, x))
            pts.append((x, min(y, 360.0)))
        d = " ".join(f"{px:.0f},{py:.0f}" for px, py in pts)
        seg = (f'<polyline points="{d}" fill="none" stroke="#FFF59D" stroke-width="11" '
               f'stroke-linejoin="round" stroke-linecap="round" opacity="0.5"/>'
               f'<polyline points="{d}" fill="none" stroke="#FFFFFF" stroke-width="4.5" '
               f'stroke-linejoin="round" stroke-linecap="round"/>')
        if len(pts) > 3:                                   # 곁가지 한 가닥
            bi = rng.randint(1, len(pts) - 2)
            bx, by = pts[bi]
            ex = max(24, min(456, bx + rng.randint(-80, 80)))
            ey = by + rng.randint(30, 60)
            seg += (f'<polyline points="{bx:.0f},{by:.0f} {ex:.0f},{ey:.0f}" fill="none" '
                    f'stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" opacity="0.9"/>')
        return seg
    for _ in range(rng.randint(2, 3)):
        parts.append(bolt(rng.randint(80, 400)))
    inner = "\n  ".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  {inner}
</svg>"""

LIGHTNING_SVGS = [_lightning_svg(700 + i) for i in range(3)]

# -------- 주문버튼(HUD): ⚡ 전체 번개 — 준비됨/충전중/소진 3코스튬(시후가 한눈에) --------
def _spell_icon_svg(state):
    # state: "ready" | "charge" | "exhaust"
    pal = {
        "ready":   ("#1565C0", "#FFF176", "#FFEB3B", "#F9A825", "준비!", "#FFFFFF"),
        "charge":  ("#37474F", "#607D8B", "#90A4AE", "#546E7A", "충전중", "#B0BEC5"),
        "exhaust": ("#3E2723", "#8D6E63", "#6D4C41", "#4E342E", "소진!", "#D7CCC8"),
    }
    bg, ring, bolt, bstrk, label, lblfil = pal[state]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="70" height="84" viewBox="0 0 70 84">
  <circle cx="35" cy="33" r="30" fill="{bg}" stroke="{ring}" stroke-width="4"/>
  <polygon points="42,12 23,40 34,40 28,58 51,28 39,28" fill="{bolt}" stroke="{bstrk}" stroke-width="2" stroke-linejoin="round"/>
  <text x="35" y="79" text-anchor="middle" font-family="Arial" font-size="15" font-weight="bold" fill="{lblfil}">{label}</text>
</svg>"""
SPELL_READY_SVG    = _spell_icon_svg("ready")
SPELL_CHARGE_SVG   = _spell_icon_svg("charge")
SPELL_EXHAUST_SVG  = _spell_icon_svg("exhaust")

# -------- 숫자 코스튬: 흰 0~9(데미지) + 금 0~9(골드) — say 미사용 --------
def _digit_svg(d, fill, stroke):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="32" height="44" viewBox="0 0 32 44">
  <text x="16" y="36" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-size="42" font-weight="bold" fill="{fill}" stroke="{stroke}" stroke-width="4" paint-order="stroke" stroke-linejoin="round">{d}</text>
</svg>"""
WHITE_DIGITS = [_digit_svg(d, "#FFFFFF", "#1B3A5B") for d in range(10)]
GOLD_DIGITS  = [_digit_svg(d, "#FFD54F", "#7A3E00") for d in range(10)]

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
def add_comment(bs, comments, block_id, text, x=520, y=40, w=300, h=160):
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
# ----- 5.1 튜닝 40 (개조 손잡이) -----
V_GOLD0     = "varGold01"        # 기본골드 150
V_COSTA     = "varCostArrow02"   # 화살탑가격 50
V_COSTC     = "varCostCannon03"  # 대포탑가격 100
V_COSTM     = "varCostMagic04"   # 마법탑가격 150
V_WAVEGOLD  = "varWaveGold05"    # 웨이브클리어골드 30
V_UPGOLD    = "varUpGold06"      # 강화골드량 40
V_UP        = "varUp07"          # 강화량 1
V_CASTLEMAX = "varCastleMax08"   # 성최대체력 20
V_UNLKC     = "varUnlockCannon09"# 대포탑해금웨이브 2
V_UNLKM     = "varUnlockMagic10" # 마법탑해금웨이브 4
V_BASECNT   = "varBaseCount11"   # 기본몬스터수 6
V_CNTINC    = "varCountInc12"    # 웨이브당몬스터증가 2
V_SPGAP     = "varSpawnGap13"    # 몬스터간격 0.8
V_HPINC     = "varHPinc14"       # 웨이브체력증가 2
V_SPINC     = "varSPinc15"       # 웨이브속도증가 0.1
V_REACH     = "varReach16"       # 도달반경 12
V_BOLTSPD   = "varBoltSpd17"     # 탄속도 9
V_GOBHP     = "varGobHP18"       # 고블린_체력 3
V_GOBSP     = "varGobSP19"       # 고블린_속도 2.2
V_GOBGOLD   = "varGobGold20"     # 고블린_골드 5
V_ORCHP     = "varOrcHP21"       # 오크_체력 8
V_ORCSP     = "varOrcSP22"       # 오크_속도 1.5
V_ORCGOLD   = "varOrcGold23"     # 오크_골드 10
V_TROLLHP   = "varTrollHP24"     # 트롤_체력 20
V_TROLLSP   = "varTrollSP25"     # 트롤_속도 0.9
V_TROLLGOLD = "varTrollGold26"   # 트롤_골드 25
V_ARR       = "varArR27"         # 화살탑_사거리 120
V_ARD       = "varArD28"         # 화살탑_공격력 1
V_ARG       = "varArG29"         # 화살탑_간격 0.45
V_ARS       = "varArS30"         # 화살탑_폭발반경 16
V_CAR       = "varCaR31"         # 대포탑_사거리 100
V_CAD       = "varCaD32"         # 대포탑_공격력 2
V_CAG       = "varCaG33"         # 대포탑_간격 1.3
V_CAS       = "varCaS34"         # 대포탑_폭발반경 60
V_MAR       = "varMaR35"         # 마법탑_사거리 150
V_MAD       = "varMaD36"         # 마법탑_공격력 4
V_MAG       = "varMaG37"         # 마법탑_간격 0.85
V_MAS       = "varMaS38"         # 마법탑_폭발반경 20
V_REPAIRCOST= "varRepairCost39"  # 수리비용 60   (튜닝 39)
V_REPAIRAMT = "varRepairAmt40"   # 수리량 5      (튜닝 40)
V_SPELLDMG  = "varSpellDmg41"    # 주문공격력 9999 (튜닝 41 — 전체 번개: 원턴킬)
V_SPELLCD   = "varSpellCD42"     # 주문쿨 20     (튜닝 42 — 재사용 대기 초, 길게)
V_SPELLMAX  = "varSpellMax43"    # 주문최대횟수 3 (튜닝 43 — 게임당 시전 가능 횟수)

# ----- 5.2 진행/내부 상태 40 -----
V_STATE   = "varState39"      # 게임상태 1
V_WAVE    = "varWave40"       # 웨이브 1
V_GOLDCUR = "varGoldCur41"    # 골드 150
V_CASTLE  = "varCastle42"     # 성체력 20
V_ALIVE   = "varAlive43"      # 적수 0
V_SPAWNED = "varSpawned44"    # 스폰완료 0
V_SPAWNN  = "varSpawnN45"     # 스폰카운트 0
V_SEL     = "varSel46"        # 선택포탑 0
V_UNCA    = "varUnCa47"       # 대포탑해금 0
V_UNMA    = "varUnMa48"       # 마법탑해금 0
V_BUFATK  = "varBufAtk49"     # 공격력보너스 0
V_BUFRNG  = "varBufRng50"     # 사거리보너스 0
V_BUFROF  = "varBufRof51"     # 연사보너스 1
V_PLACEX  = "varPlaceX52"     # 설치X 0
V_PLACEY  = "varPlaceY53"     # 설치Y 0
V_PLACET  = "varPlaceT54"     # 설치타입 0
V_AIMLOCK = "varAimLock55"    # 조준중 0
V_AIMTX   = "varAimTX56"      # 조준탑X 0
V_AIMTY   = "varAimTY57"      # 조준탑Y 0
V_AIMTR   = "varAimTR58"      # 조준탑사거리 0
V_AIMD    = "varAimD59"       # 조준거리 99999
V_AIMX    = "varAimX60"       # 조준X 0
V_AIMY    = "varAimY61"       # 조준Y 0
V_AIMOK   = "varAimOK62"      # 조준있음 0
V_FIREX   = "varFireX63"      # 발사X 0
V_FIREY   = "varFireY64"      # 발사Y 0
V_FIRET   = "varFireT65"      # 발사타입 0
V_BOOMX   = "varBoomX66"      # 폭발X 0
V_BOOMY   = "varBoomY67"      # 폭발Y 0
V_BOOMD   = "varBoomD68"      # 폭발데미지 0
V_BOOMR   = "varBoomR69"      # 폭발반경 0
V_SPAWNT  = "varSpawnT70"     # 생성타입 1
V_DMGVAL  = "varDmgVal71"     # 데미지표시값 0
V_DMGX    = "varDmgX72"       # 데미지표시x 0
V_DMGY    = "varDmgY73"       # 데미지표시y 0
V_DMGKIND = "varDmgKind74"    # 팝업종류 0
V_DMGDIG  = "varDmgDigit75"   # 데미지숫자 0
V_DMGOFF  = "varDmgOff76"     # 데미지오프셋 0
V_DMGLEN  = "varDmgLen77"     # 데미지글자수 0
V_DMGPOS  = "varDmgPos78"     # 데미지자리 0
V_SPELLLEFT = "varSpellLeft79" # 주문쿨남음 0  (진행 41 — >0 동안 재시전 불가, 틱 감소)
V_SPELLCOUNT= "varSpellCount80" # 주문횟수 3   (진행 42 — 남은 시전 횟수, 0이면 소진)

# ----- 5.3 리스트 -----
L_PATHX = "listPathX"   # 경로X
L_PATHY = "listPathY"   # 경로Y

# ----- 5.4 클론-로컬 -----
V_MON_ISC  = "varMonIsClone"
V_MON_TYPE = "varMonType"
V_MON_HP   = "varMonHP"
V_MON_SPD  = "varMonSpd"
V_MON_GOLD = "varMonGold"
V_MON_WP   = "varMonWP"
V_TW_ISC   = "varTwIsClone"
V_TW_TYPE  = "varTwType"
V_TW_RNG   = "varTwRange"
V_TW_DMG   = "varTwDmg"
V_TW_GAP   = "varTwGap"
V_TW_SPL   = "varTwSplash"
V_TW_CD    = "varTwCD"
V_BOLT_ISC = "varBoltIsClone"
V_BOLT_TYPE= "varBoltType"
V_BOLT_DMG = "varBoltDmg"
V_BOLT_SPL = "varBoltSplash"
V_BOLT_TX  = "varBoltTX"
V_BOLT_TY  = "varBoltTY"
V_POP_ISC  = "varPopIsClone"

# ----- 5.5 메시지 11 -----
BR_START  = "brStart01"   # 게임시작
BR_WAVE   = "brWave02"    # 웨이브시작
BR_SPAWN  = "brSpawn03"   # 몬스터생성
BR_AIM    = "brAim04"     # 조준요청
BR_FIRE   = "brFire05"    # 포탑발사
BR_HIT    = "brHit06"     # 타격
BR_DMG    = "brDmg07"     # 데미지표시
BR_PLACE  = "brPlace08"   # 포탑설치
BR_UP     = "brUp09"      # 강화등장
BR_UPDONE = "brUpDone10"  # 강화완료
BR_CASTLE = "brCastle11"  # 성피격
BR_SPELL  = "brSpell12"   # 주문시전 (전체 번개)

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

def b_touchingcolor(bs, color):
    t = gen(); bs[t] = mk("sensing_touchingcolor", inputs={"COLOR": [1, [9, color]]})
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

def b_repeat(bs, times, head):
    bid = gen()
    if isinstance(times, str) and times in bs:
        bs[bid] = mk("control_repeat", inputs={"TIMES": slot(times), "SUBSTACK": [2, head]})
        bs[times]["parent"] = bid
    else:
        bs[bid] = mk("control_repeat", inputs={"TIMES": num(times), "SUBSTACK": [2, head]})
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

def b_sound(bs, pitch, sound):
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

def b_costume(bs, name):
    cmc = gen(); bs[cmc] = mk("looks_costume", fields={"COSTUME": [name, None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cmc]})
    bs[cmc]["parent"] = sw
    return sw

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

def b_add_to_list(bs, listname, listid, value):
    bid = gen(); bs[bid] = mk("data_addtolist", inputs={"ITEM": num(value)},
                              fields={"LIST": [listname, listid]})
    return bid

def b_delete_all(bs, listname, listid):
    bid = gen(); bs[bid] = mk("data_deletealloflist", fields={"LIST": [listname, listid]})
    return bid

def b_xpos(bs):
    bid = gen(); bs[bid] = mk("motion_xposition"); return bid
def b_ypos(bs):
    bid = gen(); bs[bid] = mk("motion_yposition"); return bid

def b_point_toward(bs, op, cmp_op, mk_tx, mk_ty):
    """point in direction atan((tx-x)/(ty-y)) + ((y>ty)*180)."""
    dx = op("operator_subtract", mk_tx(), b_xpos(bs))
    dy = op("operator_subtract", mk_ty(), b_ypos(bs))
    ratio = op("operator_divide", dx, dy)
    atanv = gen(); bs[atanv] = mk("operator_mathop",
        inputs={"NUM": slot(ratio)}, fields={"OPERATOR": ["atan", None]})
    bs[ratio]["parent"] = atanv
    flip_cond = cmp_op("operator_gt", b_ypos(bs), mk_ty())
    flip = op("operator_multiply", flip_cond, 180)
    summ = op("operator_add", atanv, flip)
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": slot(summ)})
    bs[summ]["parent"] = pdir
    return pdir

def b_dist_to(bs, op, mk_tx, mk_ty):
    """sqrt((x-tx)^2 + (y-ty)^2) — reporter block id."""
    dx1 = op("operator_subtract", b_xpos(bs), mk_tx())
    dx2 = op("operator_subtract", b_xpos(bs), mk_tx())
    sqx = op("operator_multiply", dx1, dx2)
    dy1 = op("operator_subtract", b_ypos(bs), mk_ty())
    dy2 = op("operator_subtract", b_ypos(bs), mk_ty())
    sqy = op("operator_multiply", dy1, dy2)
    summ = op("operator_add", sqx, sqy)
    sq = gen(); bs[sq] = mk("operator_mathop",
        inputs={"NUM": slot(summ)}, fields={"OPERATOR": ["sqrt", None]})
    bs[summ]["parent"] = sq
    return sq

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 클릭 → 변수 78개 + 경로 리스트 초기화(한 곳) → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val)
        seq.append((sid, bs[sid]))

    # ── 튜닝 43 (개조 손잡이) ──
    add_set("기본골드", V_GOLD0, 250)
    add_set("화살탑가격", V_COSTA, 50)
    add_set("대포탑가격", V_COSTC, 100)
    add_set("마법탑가격", V_COSTM, 150)
    add_set("웨이브클리어골드", V_WAVEGOLD, 40)
    add_set("강화골드량", V_UPGOLD, 40)
    add_set("강화량", V_UP, 1)
    add_set("성최대체력", V_CASTLEMAX, 20)
    add_set("대포탑해금웨이브", V_UNLKC, 2)
    add_set("마법탑해금웨이브", V_UNLKM, 4)
    add_set("기본몬스터수", V_BASECNT, 6)
    add_set("웨이브당몬스터증가", V_CNTINC, 3)
    add_set("몬스터간격", V_SPGAP, 0.8)
    add_set("웨이브체력증가", V_HPINC, 8)
    add_set("웨이브속도증가", V_SPINC, 0.13)
    add_set("도달반경", V_REACH, 12)
    add_set("탄속도", V_BOLTSPD, 9)
    add_set("고블린_체력", V_GOBHP, 3)
    add_set("고블린_속도", V_GOBSP, 2.2)
    add_set("고블린_골드", V_GOBGOLD, 5)
    add_set("오크_체력", V_ORCHP, 8)
    add_set("오크_속도", V_ORCSP, 1.5)
    add_set("오크_골드", V_ORCGOLD, 10)
    add_set("트롤_체력", V_TROLLHP, 20)
    add_set("트롤_속도", V_TROLLSP, 0.9)
    add_set("트롤_골드", V_TROLLGOLD, 25)
    add_set("화살탑_사거리", V_ARR, 120)
    add_set("화살탑_공격력", V_ARD, 2)
    add_set("화살탑_간격", V_ARG, 0.45)
    add_set("화살탑_폭발반경", V_ARS, 16)
    add_set("대포탑_사거리", V_CAR, 100)
    add_set("대포탑_공격력", V_CAD, 3)
    add_set("대포탑_간격", V_CAG, 1.3)
    add_set("대포탑_폭발반경", V_CAS, 60)
    add_set("마법탑_사거리", V_MAR, 150)
    add_set("마법탑_공격력", V_MAD, 5)
    add_set("마법탑_간격", V_MAG, 0.85)
    add_set("마법탑_폭발반경", V_MAS, 20)
    add_set("수리비용", V_REPAIRCOST, 60)
    add_set("수리량", V_REPAIRAMT, 5)
    add_set("주문공격력", V_SPELLDMG, 9999)
    add_set("주문쿨", V_SPELLCD, 20)
    add_set("주문최대횟수", V_SPELLMAX, 3)

    # ── 진행 상태 41 (골드=기본골드, 성체력=성최대체력 참조) ──
    add_set("게임상태", V_STATE, 1)
    add_set("웨이브", V_WAVE, 1)
    gold0_r = vrep("기본골드", V_GOLD0)
    sid = b_setvar(bs, "골드", V_GOLDCUR, gold0_r); seq.append((sid, bs[sid]))
    cmax_r = vrep("성최대체력", V_CASTLEMAX)
    sid = b_setvar(bs, "성체력", V_CASTLE, cmax_r); seq.append((sid, bs[sid]))
    add_set("적수", V_ALIVE, 0)
    add_set("스폰완료", V_SPAWNED, 0)
    add_set("스폰카운트", V_SPAWNN, 0)
    add_set("선택포탑", V_SEL, 0)
    add_set("대포탑해금", V_UNCA, 0)
    add_set("마법탑해금", V_UNMA, 0)
    add_set("공격력보너스", V_BUFATK, 0)
    add_set("사거리보너스", V_BUFRNG, 0)
    add_set("연사보너스", V_BUFROF, 1)
    add_set("설치X", V_PLACEX, 0)
    add_set("설치Y", V_PLACEY, 0)
    add_set("설치타입", V_PLACET, 0)
    add_set("조준중", V_AIMLOCK, 0)
    add_set("조준탑X", V_AIMTX, 0)
    add_set("조준탑Y", V_AIMTY, 0)
    add_set("조준탑사거리", V_AIMTR, 0)
    add_set("조준거리", V_AIMD, 99999)
    add_set("조준X", V_AIMX, 0)
    add_set("조준Y", V_AIMY, 0)
    add_set("조준있음", V_AIMOK, 0)
    add_set("발사X", V_FIREX, 0)
    add_set("발사Y", V_FIREY, 0)
    add_set("발사타입", V_FIRET, 0)
    add_set("폭발X", V_BOOMX, 0)
    add_set("폭발Y", V_BOOMY, 0)
    add_set("폭발데미지", V_BOOMD, 0)
    add_set("폭발반경", V_BOOMR, 0)
    add_set("생성타입", V_SPAWNT, 1)
    add_set("데미지표시값", V_DMGVAL, 0)
    add_set("데미지표시x", V_DMGX, 0)
    add_set("데미지표시y", V_DMGY, 0)
    add_set("팝업종류", V_DMGKIND, 0)
    add_set("데미지숫자", V_DMGDIG, 0)
    add_set("데미지오프셋", V_DMGOFF, 0)
    add_set("데미지글자수", V_DMGLEN, 0)
    add_set("데미지자리", V_DMGPOS, 0)
    add_set("주문쿨남음", V_SPELLLEFT, 0)
    # 게임 재시작마다 남은 주문 횟수를 주문최대횟수(3)로 리셋 → 아껴 쓰는 궁극기
    spc_r = vrep("주문최대횟수", V_SPELLMAX)
    sid = b_setvar(bs, "주문횟수", V_SPELLCOUNT, spc_r); seq.append((sid, bs[sid]))

    # ── 경로(웨이포인트) 리스트 6점 ──
    delx = b_delete_all(bs, "경로X", L_PATHX); seq.append((delx, bs[delx]))
    dely = b_delete_all(bs, "경로Y", L_PATHY); seq.append((dely, bs[dely]))
    path = [(-240,70),(-120,70),(-120,-50),(40,-50),(40,90),(170,90)]
    first_path_block = None
    for (px, py) in path:
        ax = b_add_to_list(bs, "경로X", L_PATHX, px); seq.append((ax, bs[ax]))
        if first_path_block is None: first_path_block = ax
        ay = b_add_to_list(bs, "경로Y", L_PATHY, py); seq.append((ay, bs[ay]))

    w1 = b_wait(bs, 0.3); seq.append((w1, bs[w1]))
    bc_start = b_broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # ===== (B) 웨이브 매니저 forever (스폰) =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=360, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # broadcast 웨이브시작 ; 스폰카운트=0 ; repeat(count){ 생성타입 결정 ; +1 ; 적수+1 ; 몬스터생성 ; wait } ; 스폰완료=1
    bc_wave = b_broadcast(bs, "웨이브시작", BR_WAVE)
    set_spn0 = b_setvar(bs, "스폰카운트", V_SPAWNN, 0)
    # 종류 결정: 웨이브<=1 →1 / 웨이브<=3 →1+(스폰카운트 mod 2) / else →1+random(0,2)
    set_t1 = b_setvar(bs, "생성타입", V_SPAWNT, 1)
    spn_r = vrep("스폰카운트", V_SPAWNN); mod2 = op("operator_mod", spn_r, 2)
    t_alt = op("operator_add", 1, mod2)
    set_talt = gen(); bs[set_talt] = mk("data_setvariableto",
        inputs={"VALUE": slot(t_alt)}, fields={"VARIABLE": ["생성타입", V_SPAWNT]})
    bs[t_alt]["parent"] = set_talt
    rnd02 = gen(); bs[rnd02] = mk("operator_random", inputs={"FROM": num(0), "TO": num(2)})
    t_mix = op("operator_add", 1, rnd02)
    set_tmix = gen(); bs[set_tmix] = mk("data_setvariableto",
        inputs={"VALUE": slot(t_mix)}, fields={"VARIABLE": ["생성타입", V_SPAWNT]})
    bs[t_mix]["parent"] = set_tmix
    wave_r2 = vrep("웨이브", V_WAVE); cond_w3 = cmp_op("operator_lt", wave_r2, 4)  # 웨이브<=3
    if_w3 = b_ifelse(bs, cond_w3, set_talt, set_tmix)
    wave_r1 = vrep("웨이브", V_WAVE); cond_w1 = cmp_op("operator_lt", wave_r1, 2)  # 웨이브<=1
    if_type = b_ifelse(bs, cond_w1, set_t1, if_w3)
    inc_spn = b_changevar(bs, "스폰카운트", V_SPAWNN, 1)
    inc_alive = b_changevar(bs, "적수", V_ALIVE, 1)
    bc_spawn = b_broadcast(bs, "몬스터생성", BR_SPAWN)
    w_gap = b_wait_var(bs, V_SPGAP, "몬스터간격")
    chain([(if_type, bs[if_type]), (inc_spn, bs[inc_spn]), (inc_alive, bs[inc_alive]),
           (bc_spawn, bs[bc_spawn]), (w_gap, bs[w_gap])])
    base_r = vrep("기본몬스터수", V_BASECNT); wave_rc = vrep("웨이브", V_WAVE)
    wm1 = op("operator_subtract", wave_rc, 1); cinc_r = vrep("웨이브당몬스터증가", V_CNTINC)
    extra = op("operator_multiply", wm1, cinc_r)
    count_r = op("operator_add", base_r, extra)
    rep_spawn = b_repeat(bs, count_r, if_type)
    set_done = b_setvar(bs, "스폰완료", V_SPAWNED, 1)
    chain([(bc_wave, bs[bc_wave]), (set_spn0, bs[set_spn0]),
           (rep_spawn, bs[rep_spawn]), (set_done, bs[set_done])])
    state_b = vrep("게임상태", V_STATE); cond_pl = cmp_op("operator_equals", state_b, 1)
    spd_r = vrep("스폰완료", V_SPAWNED); cond_notdone = cmp_op("operator_equals", spd_r, 0)
    cond_go = bool_op("operator_and", cond_pl, cond_notdone)
    if_run = b_if(bs, cond_go, bc_wave)
    w_idle = b_wait(bs, 0.1)
    chain([(if_run, bs[if_run]), (w_idle, bs[w_idle])])
    fe_b = b_forever(bs, if_run)
    chain([(hb, bs[hb]), (fe_b, bs[fe_b])])

    # ===== (C) 뿔피리 =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=360, y=360,
        fields={"BROADCAST_OPTION": ["웨이브시작", BR_WAVE]})
    sh_horn, sp_horn = b_sound(bs, 0, "horn")
    chain([(hc, bs[hc]), (sh_horn, bs[sh_horn])])

    # ===== (D) 웨이브 클리어 / 게임오버 / 해금 감시 forever =====
    hd = gen(); bs[hd] = mk("event_whenflagclicked", top=True, x=20, y=900)
    state_ready = vrep("게임상태", V_STATE); cond_ready = cmp_op("operator_equals", state_ready, 1)
    wu = b_waituntil(bs, cond_ready)
    # 클리어: 게임상태=1 and 스폰완료=1 and 적수<=0 → 골드+클리어골드 ; 게임상태=2 ; 강화등장
    s1 = vrep("게임상태", V_STATE); c1 = cmp_op("operator_equals", s1, 1)
    sd = vrep("스폰완료", V_SPAWNED); c2 = cmp_op("operator_equals", sd, 1)
    al = vrep("적수", V_ALIVE); c3 = cmp_op("operator_lt", al, 1)
    c12 = bool_op("operator_and", c1, c2); c_clear = bool_op("operator_and", c12, c3)
    wg_r = vrep("웨이브클리어골드", V_WAVEGOLD)
    add_gold = b_changevar(bs, "골드", V_GOLDCUR, wg_r)
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_up = b_broadcast(bs, "강화등장", BR_UP)
    chain([(add_gold, bs[add_gold]), (set_st2, bs[set_st2]), (bc_up, bs[bc_up])])
    if_clear = b_if(bs, c_clear, add_gold)
    # 게임오버: 성체력<1 and 게임상태=1 → 게임상태=0
    cs = vrep("성체력", V_CASTLE); cdead = cmp_op("operator_lt", cs, 1)
    s2 = vrep("게임상태", V_STATE); cpl2 = cmp_op("operator_equals", s2, 1)
    c_over = bool_op("operator_and", cdead, cpl2)
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    if_over = b_if(bs, c_over, set_st0)
    wd = b_wait(bs, 0.1)
    chain([(if_clear, bs[if_clear]), (if_over, bs[if_over]), (wd, bs[wd])])
    fe_d = b_forever(bs, if_clear)
    chain([(hd, bs[hd]), (wu, bs[wu]), (fe_d, bs[fe_d])])

    # ── 가이드 투어 코멘트 ──
    add_comment(bs, comments, h,
        "🛠️ 개조 손잡이: 여기 숫자만 바꾸면 게임이 달라져요!\n"
        "골드·가격·몬스터·포탑 능력치가 전부 여기 한글 변수로 모여 있어요. "
        "예: 화살탑가격 50→10 으로 바꾸면 화살탑을 길에 도배할 수 있어요. "
        "바꾸기 전에 어떻게 될지 예상하고 ▶ 를 눌러 확인!",
        x=-380, y=-280, w=340, h=180)
    add_comment(bs, comments, delx,
        "🗺️ 길은 이 좌표들이에요.\n"
        "경로X·경로Y 에 6개의 점을 넣어 S자 길을 만들어요. 숫자를 바꾸면 몬스터가 가는 "
        "길이 바뀌어요(미션 4층: 더 구불구불한 길 만들기).",
        x=-380, y=420, w=320, h=150)
    add_comment(bs, comments, hb,
        "🌊 웨이브마다 몬스터 수 = 기본몬스터수 + (웨이브-1)×웨이브당몬스터증가.\n"
        "웨이브가 오를수록 더 많이·세게·빠르게 나와요. 웨이브1=고블린만, 2~3=고블린·오크, "
        "4+=셋 섞임.",
        x=720, y=-20, w=320, h=160)

    return bs, comments

# ============================================================
#  성 (CASTLE)
# ============================================================
def build_castle_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(205), "Y": num(90)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    clr = gen(); bs[clr] = mk("looks_cleargraphiceffects")
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs]), (clr, bs[clr])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["성피격", BR_CASTLE]})
    sh, sp = b_sound(bs, 0, "castlehit")
    set_c1 = gen(); bs[set_c1] = mk("looks_seteffectto",
        inputs={"VALUE": num(80)}, fields={"EFFECT": ["COLOR", None]})
    w1 = b_wait(bs, 0.05)
    set_c0 = gen(); bs[set_c0] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["COLOR", None]})
    w2 = b_wait(bs, 0.05)
    chain([(set_c1, bs[set_c1]), (w1, bs[w1]), (set_c0, bs[set_c0]), (w2, bs[w2])])
    rep = b_repeat(bs, 3, set_c1)
    chain([(hb, bs[hb]), (sh, bs[sh]), (sp, bs[sp]), (rep, bs[rep])])
    return bs, comments

# ============================================================
#  몬스터 (MONSTER: 스포너 + 클론 본체 + 타격 + 조준 보고)
# ============================================================
def build_monster_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    mkX = lambda: b_item_of(bs, "경로X", L_PATHX, vrep("현재점", V_MON_WP))
    mkY = lambda: b_item_of(bs, "경로Y", L_PATHY, vrep("현재점", V_MON_WP))
    mkBoomX = lambda: vrep("폭발X", V_BOOMX)
    mkBoomY = lambda: vrep("폭발Y", V_BOOMY)
    mkAimX = lambda: vrep("조준탑X", V_AIMTX)
    mkAimY = lambda: vrep("조준탑Y", V_AIMTY)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_MON_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 몬스터생성 → 클론 1마리 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["몬스터생성", BR_SPAWN]})
    isc = vrep("복제됨", V_MON_ISC); cond_orig = cmp_op("operator_equals", isc, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    set_isc1 = b_setvar(bs, "복제됨", V_MON_ISC, 1)
    spt_r = vrep("생성타입", V_SPAWNT)
    set_type = b_setvar(bs, "내타입", V_MON_TYPE, spt_r)

    def type_branch(type_val, hp_id, hp_nm, sp_id, sp_nm, gd_id, gd_nm, costume, size_val):
        cond_t = cmp_op("operator_equals", vrep("내타입", V_MON_TYPE), type_val)
        # 내체력 = 종류체력 + (웨이브-1)*웨이브체력증가
        base_hp = vrep(hp_nm, hp_id); wv = vrep("웨이브", V_WAVE)
        wm1 = op("operator_subtract", wv, 1); hpinc = vrep("웨이브체력증가", V_HPINC)
        scl = op("operator_multiply", wm1, hpinc); hp_expr = op("operator_add", base_hp, scl)
        set_hp = b_setvar(bs, "내체력", V_MON_HP, hp_expr)
        base_sp = vrep(sp_nm, sp_id); wv2 = vrep("웨이브", V_WAVE)
        wm2 = op("operator_subtract", wv2, 1); spinc = vrep("웨이브속도증가", V_SPINC)
        scl2 = op("operator_multiply", wm2, spinc); sp_expr = op("operator_add", base_sp, scl2)
        set_sp = b_setvar(bs, "내속도", V_MON_SPD, sp_expr)
        set_gd = b_setvar(bs, "내골드", V_MON_GOLD, vrep(gd_nm, gd_id))
        sw = b_costume(bs, costume)
        szb = gen(); bs[szb] = mk("looks_setsizeto", inputs={"SIZE": num(size_val)})
        chain([(set_hp, bs[set_hp]), (set_sp, bs[set_sp]), (set_gd, bs[set_gd]),
               (sw, bs[sw]), (szb, bs[szb])])
        return b_if(bs, cond_t, set_hp)
    if_t1 = type_branch(1, V_GOBHP, "고블린_체력", V_GOBSP, "고블린_속도", V_GOBGOLD, "고블린_골드", "고블린", 50)
    if_t2 = type_branch(2, V_ORCHP, "오크_체력", V_ORCSP, "오크_속도", V_ORCGOLD, "오크_골드", "오크", 70)
    if_t3 = type_branch(3, V_TROLLHP, "트롤_체력", V_TROLLSP, "트롤_속도", V_TROLLGOLD, "트롤_골드", "트롤", 90)
    chain([(if_t1, bs[if_t1]), (if_t2, bs[if_t2]), (if_t3, bs[if_t3])])

    set_wp1 = b_setvar(bs, "현재점", V_MON_WP, 1)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(b_item_of(bs, "경로X", L_PATHX, 1)),
                "Y": slot(b_item_of(bs, "경로Y", L_PATHY, 1))})
    bs[bs[g]["inputs"]["X"][1]]["parent"] = g
    bs[bs[g]["inputs"]["Y"][1]]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")

    # forever body
    body = []
    # 1) 게임오버 정리
    s0 = vrep("게임상태", V_STATE); cond_go = cmp_op("operator_equals", s0, 0)
    dec_al_go = b_changevar(bs, "적수", V_ALIVE, -1)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    chain([(dec_al_go, bs[dec_al_go]), (del_go, bs[del_go])])
    if_go = b_if(bs, cond_go, dec_al_go)
    body.append(if_go)

    # 2) 게임상태=1 → 경로 행진 + 도달/처치
    march = []
    pt = b_point_toward(bs, op, cmp_op, mkX, mkY)
    mv = b_movesteps(bs, vrep("내속도", V_MON_SPD))
    march.append(pt); march.append(mv)
    # 웨이포인트 도착 → 현재점+1 ; 현재점>length → 성도달
    dist_wp = b_dist_to(bs, op, mkX, mkY)
    reach_r = vrep("도달반경", V_REACH)
    cond_arr = cmp_op("operator_lt", dist_wp, reach_r)
    inc_wp = b_changevar(bs, "현재점", V_MON_WP, 1)
    wp_r = vrep("현재점", V_MON_WP); len_r = b_length_of(bs, "경로X", L_PATHX)
    cond_end = cmp_op("operator_gt", wp_r, len_r)
    dec_castle = b_changevar(bs, "성체력", V_CASTLE, -1)
    bc_castle = b_broadcast(bs, "성피격", BR_CASTLE)
    dec_al_end = b_changevar(bs, "적수", V_ALIVE, -1)
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(dec_castle, bs[dec_castle]), (bc_castle, bs[bc_castle]),
           (dec_al_end, bs[dec_al_end]), (del_end, bs[del_end])])
    if_end = b_if(bs, cond_end, dec_castle)
    chain([(inc_wp, bs[inc_wp]), (if_end, bs[if_end])])
    if_arr = b_if(bs, cond_arr, inc_wp)
    march.append(if_arr)
    # 처치: 내체력<1 → 골드 + 팝업 + 사운드 + 폭발 + 삭제
    hp_r = vrep("내체력", V_MON_HP); cond_dead = cmp_op("operator_lt", hp_r, 1)
    add_gold = b_changevar(bs, "골드", V_GOLDCUR, vrep("내골드", V_MON_GOLD))
    set_dval = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("내골드", V_MON_GOLD))
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, b_xpos(bs))
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, b_ypos(bs))
    set_kind1 = b_setvar(bs, "팝업종류", V_DMGKIND, 1)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    sh_kill, sp_kill = b_sound(bs, 0, "kill")
    sh_coin, sp_coin = b_sound(bs, 0, "coin")
    dec_al_kill = b_changevar(bs, "적수", V_ALIVE, -1)
    sw_ex = b_costume(bs, "폭발")
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(10)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(20)}, fields={"EFFECT": ["GHOST", None]})
    w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = b_repeat(bs, 5, ch_sz)
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")
    chain([(add_gold, bs[add_gold]), (set_dval, bs[set_dval]), (set_dx, bs[set_dx]),
           (set_dy, bs[set_dy]), (set_kind1, bs[set_kind1]), (bc_dmg, bs[bc_dmg]),
           (sh_kill, bs[sh_kill]), (sp_kill, bs[sp_kill]),
           (sh_coin, bs[sh_coin]), (sp_coin, bs[sp_coin]),
           (dec_al_kill, bs[dec_al_kill]), (sw_ex, bs[sw_ex]),
           (rep_an, bs[rep_an]), (del_k, bs[del_k])])
    if_kill = b_if(bs, cond_dead, add_gold)
    march.append(if_kill)
    chain([(b, bs[b]) for b in march])
    s1 = vrep("게임상태", V_STATE); cond_pl = cmp_op("operator_equals", s1, 1)
    if_march = b_if(bs, cond_pl, march[0])
    body.append(if_march)

    w_body = b_wait(bs, 0.025)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_type, bs[set_type]),
           (if_t1, bs[if_t1])])
    chain([(if_t3, bs[if_t3]), (set_wp1, bs[set_wp1]), (g, bs[g]),
           (show, bs[show]), (fe_body, bs[fe_body])])

    # (D) 타격 받으면 반경 안일 때 데미지 — wait 없는 원자 실행
    ht = gen(); bs[ht] = mk("event_whenbroadcastreceived", top=True, x=400, y=360,
        fields={"BROADCAST_OPTION": ["타격", BR_HIT]})
    isc_t = vrep("복제됨", V_MON_ISC); c_clone = cmp_op("operator_equals", isc_t, 1)
    st_t = vrep("게임상태", V_STATE); c_pl = cmp_op("operator_equals", st_t, 1)
    c_active = bool_op("operator_and", c_clone, c_pl)
    dist_boom = b_dist_to(bs, op, mkBoomX, mkBoomY)
    boomr_r = vrep("폭발반경", V_BOOMR)
    cond_far = cmp_op("operator_gt", dist_boom, boomr_r)
    cond_in = gen(); bs[cond_in] = mk("operator_not", inputs={"OPERAND": [2, cond_far]})
    bs[cond_far]["parent"] = cond_in
    boomd_r = vrep("폭발데미지", V_BOOMD)
    neg_d = op("operator_subtract", 0, boomd_r)
    dec_hp = b_changevar(bs, "내체력", V_MON_HP, neg_d)
    sh_hit, sp_hit = b_sound(bs, 0, "hit")
    chain([(dec_hp, bs[dec_hp]), (sh_hit, bs[sh_hit])])
    if_in = b_if(bs, cond_in, dec_hp)
    if_active = b_if(bs, c_active, if_in)
    chain([(ht, bs[ht]), (if_active, bs[if_active])])

    # (E) 조준 보고 (최솟값 리덕션) — wait 없는 원자 실행
    ha = gen(); bs[ha] = mk("event_whenbroadcastreceived", top=True, x=400, y=600,
        fields={"BROADCAST_OPTION": ["조준요청", BR_AIM]})
    isc_a = vrep("복제됨", V_MON_ISC); c_clone2 = cmp_op("operator_equals", isc_a, 1)
    st_a = vrep("게임상태", V_STATE); c_pl2 = cmp_op("operator_equals", st_a, 1)
    c_active2 = bool_op("operator_and", c_clone2, c_pl2)
    # d <= 조준탑사거리 → not(d > 조준탑사거리)
    d1 = b_dist_to(bs, op, mkAimX, mkAimY)
    tr_r = vrep("조준탑사거리", V_AIMTR)
    c_far = cmp_op("operator_gt", d1, tr_r)
    c_inrng = gen(); bs[c_inrng] = mk("operator_not", inputs={"OPERAND": [2, c_far]})
    bs[c_far]["parent"] = c_inrng
    d2 = b_dist_to(bs, op, mkAimX, mkAimY)
    aimd_r = vrep("조준거리", V_AIMD)
    c_closer = cmp_op("operator_lt", d2, aimd_r)
    c_pick = bool_op("operator_and", c_inrng, c_closer)
    d3 = b_dist_to(bs, op, mkAimX, mkAimY)
    set_aimd = b_setvar(bs, "조준거리", V_AIMD, d3)
    set_aimx = b_setvar(bs, "조준X", V_AIMX, b_xpos(bs))
    set_aimy = b_setvar(bs, "조준Y", V_AIMY, b_ypos(bs))
    set_aimok = b_setvar(bs, "조준있음", V_AIMOK, 1)
    chain([(set_aimd, bs[set_aimd]), (set_aimx, bs[set_aimx]),
           (set_aimy, bs[set_aimy]), (set_aimok, bs[set_aimok])])
    if_pick = b_if(bs, c_pick, set_aimd)
    if_active2 = b_if(bs, c_active2, if_pick)
    chain([(ha, bs[ha]), (if_active2, bs[if_active2])])

    # (F) 주문시전(전체 번개) 받으면 — 화면의 모든 몬스터가 동시에 주문공격력만큼 피해.
    #     wait/yield 없는 원자 실행이라 모든 클론이 경쟁 없이 한 번에 맞아요. 처치는 (C) 루프가 처리.
    hsp = gen(); bs[hsp] = mk("event_whenbroadcastreceived", top=True, x=400, y=840,
        fields={"BROADCAST_OPTION": ["주문시전", BR_SPELL]})
    isc_s = vrep("복제됨", V_MON_ISC); c_clone3 = cmp_op("operator_equals", isc_s, 1)
    st_s = vrep("게임상태", V_STATE); c_pl3 = cmp_op("operator_equals", st_s, 1)
    c_active3 = bool_op("operator_and", c_clone3, c_pl3)
    neg_sd = op("operator_subtract", 0, vrep("주문공격력", V_SPELLDMG))
    dec_sp_hp = b_changevar(bs, "내체력", V_MON_HP, neg_sd)
    # 데미지 숫자 팝업 재사용(폭심=몬스터 위치, 흰색 데미지)
    set_sdval = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("주문공격력", V_SPELLDMG))
    set_sdx = b_setvar(bs, "데미지표시x", V_DMGX, b_xpos(bs))
    set_sdy = b_setvar(bs, "데미지표시y", V_DMGY, b_ypos(bs))
    set_skind = b_setvar(bs, "팝업종류", V_DMGKIND, 0)
    bc_sdmg = b_broadcast(bs, "데미지표시", BR_DMG)
    chain([(dec_sp_hp, bs[dec_sp_hp]), (set_sdval, bs[set_sdval]), (set_sdx, bs[set_sdx]),
           (set_sdy, bs[set_sdy]), (set_skind, bs[set_skind]), (bc_sdmg, bs[bc_sdmg])])
    if_spell = b_if(bs, c_active3, dec_sp_hp)
    chain([(hsp, bs[hsp]), (if_spell, bs[if_spell])])

    add_comment(bs, comments, if_spell,
        "⚡ 전체 번개가 치면(주문시전) 화면의 모든 몬스터가 동시에 주문공격력만큼 체력이 깎여요!\n"
        "사거리·반경 제한이 없어서 길 위 모든 적이 한꺼번에 맞아요. 체력이 0 이하가 된 적은 "
        "원래 처치 루프가 골드·폭발로 정리해요. 주문공격력 숫자를 바꾸면 번개 위력이 달라져요.",
        x=720, y=800, w=340, h=180)

    # (F2) 주문시전 피격 번쩍 — 잠깐 흰색으로(밝기) 번쩍! (데미지 로직과 분리된 시각 전용 스크립트)
    hfl = gen(); bs[hfl] = mk("event_whenbroadcastreceived", top=True, x=760, y=840,
        fields={"BROADCAST_OPTION": ["주문시전", BR_SPELL]})
    isc_fl = vrep("복제됨", V_MON_ISC); c_clone_fl = cmp_op("operator_equals", isc_fl, 1)
    br_on = gen(); bs[br_on] = mk("looks_seteffectto", inputs={"VALUE": num(80)},
        fields={"EFFECT": ["BRIGHTNESS", None]})
    w_fl = b_wait(bs, 0.12)
    br_off = gen(); bs[br_off] = mk("looks_seteffectto", inputs={"VALUE": num(0)},
        fields={"EFFECT": ["BRIGHTNESS", None]})
    chain([(br_on, bs[br_on]), (w_fl, bs[w_fl]), (br_off, bs[br_off])])
    if_fl = b_if(bs, c_clone_fl, br_on)
    chain([(hfl, bs[hfl]), (if_fl, bs[if_fl])])
    add_comment(bs, comments, hfl,
        "✨ 번개 맞은 표시: 주문시전을 받으면 0.12초 동안 밝기 효과로 흰색 번쩍! 데미지 숫자는 (F)가 "
        "이미 띄우고, 여기선 피격을 눈에 보이게만 해요(밝기 0으로 되돌림). 데미지·쿨은 안 건드려요.",
        x=1100, y=820, w=330, h=150)

    add_comment(bs, comments, if_march,
        "🚶 다음 길목(현재점)을 향해 가요.\n"
        "경로X·경로Y 의 현재점 번째 점으로 방향을 잡고 내속도만큼 이동해요. 도착하면(도달반경 안) "
        "현재점+1. 마지막 점을 지나면 성을 때려요(성체력 -1)!",
        x=520, y=320, w=320, h=170)
    add_comment(bs, comments, if_active2,
        "🎯 포탑이 부르면 '내가 사거리 안에서 제일 가까운가?'를 검사해요.\n"
        "조준탑까지 거리가 사거리(조준탑사거리) 안이고 지금까지 최솟값(조준거리)보다 가까우면 "
        "내 위치를 적어둬요. 한 마리씩 차례로 실행돼서 답이 딱 하나 — 최솟값 찾기!",
        x=720, y=560, w=330, h=180)

    return bs, comments

# ============================================================
#  포탑 (TOWER: 설치 클론 본체 + 자동 조준 발사)
# ============================================================
def build_tower_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_TW_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 포탑설치 → 클론 1기 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["포탑설치", BR_PLACE]})
    isc = vrep("복제됨", V_TW_ISC); cond_orig = cmp_op("operator_equals", isc, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    set_isc1 = b_setvar(bs, "복제됨", V_TW_ISC, 1)
    pt_r = vrep("설치타입", V_PLACET)
    set_type = b_setvar(bs, "내타입", V_TW_TYPE, pt_r)

    def tw_branch(type_val, rng_id, rng_nm, dmg_id, dmg_nm, gap_id, gap_nm,
                  spl_id, spl_nm, costume):
        cond_t = cmp_op("operator_equals", vrep("내타입", V_TW_TYPE), type_val)
        s_rng = b_setvar(bs, "내사거리", V_TW_RNG, vrep(rng_nm, rng_id))
        s_dmg = b_setvar(bs, "내공격력", V_TW_DMG, vrep(dmg_nm, dmg_id))
        s_gap = b_setvar(bs, "내간격", V_TW_GAP, vrep(gap_nm, gap_id))
        s_spl = b_setvar(bs, "내폭발반경", V_TW_SPL, vrep(spl_nm, spl_id))
        sw = b_costume(bs, costume)
        chain([(s_rng, bs[s_rng]), (s_dmg, bs[s_dmg]), (s_gap, bs[s_gap]),
               (s_spl, bs[s_spl]), (sw, bs[sw])])
        return b_if(bs, cond_t, s_rng)
    if_t1 = tw_branch(1, V_ARR, "화살탑_사거리", V_ARD, "화살탑_공격력", V_ARG, "화살탑_간격", V_ARS, "화살탑_폭발반경", "화살탑")
    if_t2 = tw_branch(2, V_CAR, "대포탑_사거리", V_CAD, "대포탑_공격력", V_CAG, "대포탑_간격", V_CAS, "대포탑_폭발반경", "대포탑")
    if_t3 = tw_branch(3, V_MAR, "마법탑_사거리", V_MAD, "마법탑_공격력", V_MAG, "마법탑_간격", V_MAS, "마법탑_폭발반경", "마법탑")
    chain([(if_t1, bs[if_t1]), (if_t2, bs[if_t2]), (if_t3, bs[if_t3])])

    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(vrep("설치X", V_PLACEX)), "Y": slot(vrep("설치Y", V_PLACEY))})
    bs[bs[g]["inputs"]["X"][1]]["parent"] = g
    bs[bs[g]["inputs"]["Y"][1]]["parent"] = g
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    show = gen(); bs[show] = mk("looks_show")
    set_cd0 = b_setvar(bs, "발사쿨", V_TW_CD, 0)

    # forever
    body = []
    s0 = vrep("게임상태", V_STATE); cond_go = cmp_op("operator_equals", s0, 0)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    if_go = b_if(bs, cond_go, del_go)
    body.append(if_go)

    # 게임상태=1: 발사쿨<=0 이면 조준→발사
    # 발사쿨<=0 → not(발사쿨>0)
    cd_pos = cmp_op("operator_gt", vrep("발사쿨", V_TW_CD), 0)
    cd_le0 = gen(); bs[cd_le0] = mk("operator_not", inputs={"OPERAND": [2, cd_pos]})
    bs[cd_pos]["parent"] = cd_le0
    # wait until 조준중=0
    lock_r = vrep("조준중", V_AIMLOCK); cond_unlocked = cmp_op("operator_equals", lock_r, 0)
    wu_lock = b_waituntil(bs, cond_unlocked)
    set_lock1 = b_setvar(bs, "조준중", V_AIMLOCK, 1)
    set_tx = b_setvar(bs, "조준탑X", V_AIMTX, b_xpos(bs))
    set_ty = b_setvar(bs, "조준탑Y", V_AIMTY, b_ypos(bs))
    rng_expr = op("operator_add", vrep("내사거리", V_TW_RNG), vrep("사거리보너스", V_BUFRNG))
    set_tr = b_setvar(bs, "조준탑사거리", V_AIMTR, rng_expr)
    set_aimd = b_setvar(bs, "조준거리", V_AIMD, 99999)
    set_aimok0 = b_setvar(bs, "조준있음", V_AIMOK, 0)
    bcw_aim = b_broadcast_wait(bs, "조준요청", BR_AIM)
    # if 조준있음=1 → 발사
    aimok_r = vrep("조준있음", V_AIMOK); cond_have = cmp_op("operator_equals", aimok_r, 1)
    set_fx = b_setvar(bs, "발사X", V_FIREX, vrep("조준X", V_AIMX))
    set_fy = b_setvar(bs, "발사Y", V_FIREY, vrep("조준Y", V_AIMY))
    set_ft = b_setvar(bs, "발사타입", V_FIRET, vrep("내타입", V_TW_TYPE))
    # 타입별 발사음
    sh_a, sp_a = b_sound(bs, 0, "arrow")
    sh_c, sp_c = b_sound(bs, 0, "cannon")
    sh_m, sp_m = b_sound(bs, 0, "magic")
    t_eq2 = cmp_op("operator_equals", vrep("내타입", V_TW_TYPE), 2)
    if_snd2 = b_ifelse(bs, t_eq2, sh_c, sh_m)
    t_eq1 = cmp_op("operator_equals", vrep("내타입", V_TW_TYPE), 1)
    if_snd = b_ifelse(bs, t_eq1, sh_a, if_snd2)
    bc_fire = b_broadcast(bs, "포탑발사", BR_FIRE)
    gap_expr = op("operator_multiply", vrep("내간격", V_TW_GAP), vrep("연사보너스", V_BUFROF))
    set_cd = b_setvar(bs, "발사쿨", V_TW_CD, gap_expr)
    chain([(set_fx, bs[set_fx]), (set_fy, bs[set_fy]), (set_ft, bs[set_ft]),
           (if_snd, bs[if_snd]), (bc_fire, bs[bc_fire]), (set_cd, bs[set_cd])])
    if_have = b_if(bs, cond_have, set_fx)
    set_lock0 = b_setvar(bs, "조준중", V_AIMLOCK, 0)
    chain([(wu_lock, bs[wu_lock]), (set_lock1, bs[set_lock1]), (set_tx, bs[set_tx]),
           (set_ty, bs[set_ty]), (set_tr, bs[set_tr]), (set_aimd, bs[set_aimd]),
           (set_aimok0, bs[set_aimok0]), (bcw_aim, bs[bcw_aim]),
           (if_have, bs[if_have]), (set_lock0, bs[set_lock0])])
    if_ready = b_if(bs, cd_le0, wu_lock)
    dec_cd = b_changevar(bs, "발사쿨", V_TW_CD, -0.025)
    chain([(if_ready, bs[if_ready]), (dec_cd, bs[dec_cd])])
    s1 = vrep("게임상태", V_STATE); cond_pl = cmp_op("operator_equals", s1, 1)
    if_fight = b_if(bs, cond_pl, if_ready)
    body.append(if_fight)

    w_body = b_wait(bs, 0.025)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_type, bs[set_type]),
           (if_t1, bs[if_t1])])
    chain([(if_t3, bs[if_t3]), (g, bs[g]), (sz, bs[sz]), (show, bs[show]),
           (set_cd0, bs[set_cd0]), (fe_body, bs[fe_body])])

    add_comment(bs, comments, if_fight,
        "🏹 조준중 깃발을 들고 한 포탑씩 차례로 쏴요.\n"
        "발사쿨이 0이 되면 조준중=1 락을 잡고 '조준요청'을 방송하고 기다려요. 그동안 몬스터들이 "
        "사거리 안 가장 가까운 적을 골라줘요(경쟁 없이!). 조준있음=1 이면 타입별 소리와 함께 발사!",
        x=720, y=320, w=340, h=180)

    return bs, comments

# ============================================================
#  포탑탄 (BOLT: 발사체)
# ============================================================
def build_bolt_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    mkTX = lambda: vrep("목표X", V_BOLT_TX)
    mkTY = lambda: vrep("목표Y", V_BOLT_TY)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(40)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_BOLT_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 포탑발사 → 탄 클론 1개 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["포탑발사", BR_FIRE]})
    isc = vrep("복제됨", V_BOLT_ISC); cond_orig = cmp_op("operator_equals", isc, 0)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    set_isc1 = b_setvar(bs, "복제됨", V_BOLT_ISC, 1)
    ft_r = vrep("발사타입", V_FIRET)
    set_type = b_setvar(bs, "탄타입", V_BOLT_TYPE, ft_r)
    # 탄공격력 = 타입공격력 + 공격력보너스 (분기)
    d1 = op("operator_add", vrep("화살탑_공격력", V_ARD), vrep("공격력보너스", V_BUFATK))
    set_d1 = b_setvar(bs, "탄공격력", V_BOLT_DMG, d1)
    d2 = op("operator_add", vrep("대포탑_공격력", V_CAD), vrep("공격력보너스", V_BUFATK))
    set_d2 = b_setvar(bs, "탄공격력", V_BOLT_DMG, d2)
    d3 = op("operator_add", vrep("마법탑_공격력", V_MAD), vrep("공격력보너스", V_BUFATK))
    set_d3 = b_setvar(bs, "탄공격력", V_BOLT_DMG, d3)
    t_eq2 = cmp_op("operator_equals", vrep("탄타입", V_BOLT_TYPE), 2)
    if_d2 = b_ifelse(bs, t_eq2, set_d2, set_d3)
    t_eq1 = cmp_op("operator_equals", vrep("탄타입", V_BOLT_TYPE), 1)
    if_dmg = b_ifelse(bs, t_eq1, set_d1, if_d2)
    # 탄반경 = 타입폭발반경 (분기)
    set_s1 = b_setvar(bs, "탄반경", V_BOLT_SPL, vrep("화살탑_폭발반경", V_ARS))
    set_s2 = b_setvar(bs, "탄반경", V_BOLT_SPL, vrep("대포탑_폭발반경", V_CAS))
    set_s3 = b_setvar(bs, "탄반경", V_BOLT_SPL, vrep("마법탑_폭발반경", V_MAS))
    t2_eq2 = cmp_op("operator_equals", vrep("탄타입", V_BOLT_TYPE), 2)
    if_s2 = b_ifelse(bs, t2_eq2, set_s2, set_s3)
    t2_eq1 = cmp_op("operator_equals", vrep("탄타입", V_BOLT_TYPE), 1)
    if_spl = b_ifelse(bs, t2_eq1, set_s1, if_s2)
    # 목표X/Y = 발사X/Y
    set_tx = b_setvar(bs, "목표X", V_BOLT_TX, vrep("발사X", V_FIREX))
    set_ty = b_setvar(bs, "목표Y", V_BOLT_TY, vrep("발사Y", V_FIREY))
    # goto 조준탑X/Y
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(vrep("조준탑X", V_AIMTX)), "Y": slot(vrep("조준탑Y", V_AIMTY))})
    bs[bs[g]["inputs"]["X"][1]]["parent"] = g
    bs[bs[g]["inputs"]["Y"][1]]["parent"] = g
    # 코스튬 분기
    sw1 = b_costume(bs, "화살"); sw2 = b_costume(bs, "포탄"); sw3 = b_costume(bs, "마법구슬")
    t3_eq2 = cmp_op("operator_equals", vrep("탄타입", V_BOLT_TYPE), 2)
    if_c2 = b_ifelse(bs, t3_eq2, sw2, sw3)
    t3_eq1 = cmp_op("operator_equals", vrep("탄타입", V_BOLT_TYPE), 1)
    if_cos = b_ifelse(bs, t3_eq1, sw1, if_c2)
    # 방향 향하기
    pdir = b_point_toward(bs, op, cmp_op, mkTX, mkTY)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")

    # repeat until (touching 몬스터) or (touching edge) or (게임상태=0) or (dist<도달반경)
    mv = b_movesteps(bs, vrep("탄속도", V_BOLTSPD))
    w_mv = b_wait(bs, 0.01)
    chain([(mv, bs[mv]), (w_mv, bs[w_mv])])
    tc_mon = b_touching(bs, "몬스터")
    edge_menu = gen(); bs[edge_menu] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_edge = gen(); bs[tc_edge] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge_menu]})
    bs[edge_menu]["parent"] = tc_edge
    st0 = vrep("게임상태", V_STATE); c_over = cmp_op("operator_equals", st0, 0)
    dist_t = b_dist_to(bs, op, mkTX, mkTY)
    reach_r = vrep("도달반경", V_REACH)
    c_arr = cmp_op("operator_lt", dist_t, reach_r)
    or1 = bool_op("operator_or", tc_mon, tc_edge)
    or2 = bool_op("operator_or", or1, c_over)
    or3 = bool_op("operator_or", or2, c_arr)
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, or3], "SUBSTACK": [2, mv]})
    bs[or3]["parent"] = ru; bs[mv]["parent"] = ru
    # if 게임상태!=0 → 폭발 + 타격 + 팝업
    st1 = vrep("게임상태", V_STATE); c_over2 = cmp_op("operator_equals", st1, 0)
    c_live = gen(); bs[c_live] = mk("operator_not", inputs={"OPERAND": [2, c_over2]})
    bs[c_over2]["parent"] = c_live
    set_bx = b_setvar(bs, "폭발X", V_BOOMX, b_xpos(bs))
    set_by = b_setvar(bs, "폭발Y", V_BOOMY, b_ypos(bs))
    set_bd = b_setvar(bs, "폭발데미지", V_BOOMD, vrep("탄공격력", V_BOLT_DMG))
    set_br = b_setvar(bs, "폭발반경", V_BOOMR, vrep("탄반경", V_BOLT_SPL))
    bcw_hit = b_broadcast_wait(bs, "타격", BR_HIT)
    set_dval = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("탄공격력", V_BOLT_DMG))
    set_ddx = b_setvar(bs, "데미지표시x", V_DMGX, vrep("폭발X", V_BOOMX))
    set_ddy = b_setvar(bs, "데미지표시y", V_DMGY, vrep("폭발Y", V_BOOMY))
    set_kind0 = b_setvar(bs, "팝업종류", V_DMGKIND, 0)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]), (set_bd, bs[set_bd]),
           (set_br, bs[set_br]), (bcw_hit, bs[bcw_hit]), (set_dval, bs[set_dval]),
           (set_ddx, bs[set_ddx]), (set_ddy, bs[set_ddy]), (set_kind0, bs[set_kind0]),
           (bc_dmg, bs[bc_dmg])])
    if_boom = b_if(bs, c_live, set_bx)
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_type, bs[set_type]),
           (if_dmg, bs[if_dmg]), (if_spl, bs[if_spl]), (set_tx, bs[set_tx]),
           (set_ty, bs[set_ty]), (g, bs[g]), (if_cos, bs[if_cos]),
           (pdir, bs[pdir]), (front, bs[front]), (show, bs[show]),
           (ru, bs[ru]), (if_boom, bs[if_boom]), (del_end, bs[del_end])])

    add_comment(bs, comments, if_boom,
        "💥 맞은 자리 둘레(폭발반경) 안 몬스터가 한꺼번에 피해를 받아요.\n"
        "탄이 멈춘 자리에서 폭발X/Y·폭발데미지·폭발반경을 정하고 '타격'을 방송하고 기다리면, "
        "반경 안 몬스터가 모두 동시에 체력이 깎여요. 대포탑은 반경이 커서 무리를 한 방에!",
        x=520, y=320, w=340, h=180)

    return bs, comments

# ============================================================
#  건설커서 (BUILD CURSOR: 설치 미리보기 + 배치)
# ============================================================
def build_cursor_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    gh = gen(); bs[gh] = mk("looks_seteffectto", inputs={"VALUE": num(40)},
        fields={"EFFECT": ["GHOST", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (gh, bs[gh])])

    # (B) 미리보기 forever
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    show = gen(); bs[show] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    mx = gen(); bs[mx] = mk("sensing_mousex"); my = gen(); bs[my] = mk("sensing_mousey")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(mx), "Y": slot(my)})
    bs[mx]["parent"] = g; bs[my]["parent"] = g
    chain([(show, bs[show]), (front, bs[front]), (g, bs[g])])
    sel_r = vrep("선택포탑", V_SEL); c_sel = cmp_op("operator_gt", sel_r, 0)
    st_r = vrep("게임상태", V_STATE); c_pl = cmp_op("operator_equals", st_r, 1)
    c_on = bool_op("operator_and", c_sel, c_pl)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    if_on = b_ifelse(bs, c_on, show, hi2)
    w = b_wait(bs, 0.02)
    chain([(if_on, bs[if_on]), (w, bs[w])])
    fe = b_forever(bs, if_on)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    # (C) 마우스 '누름'을 폴링해서 설치 — 'when this sprite clicked'는 반투명 사거리 링의
    #     투명한 가운데를 클릭하면 안 잡혀서(어디 눌러도 설치 안 되던 버그), forever 로 직접 감지.
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=380, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # validity gate (팔레트 제외): not (touching color 길색 or touching 성/포탑)
    tc_path = b_touchingcolor(bs, PATH_COLOR)
    tc_castle = b_touching(bs, "성")
    tc_tw = b_touching(bs, "포탑")
    or1 = bool_op("operator_or", tc_path, tc_castle)
    or2 = bool_op("operator_or", or1, tc_tw)
    invalid = gen(); bs[invalid] = mk("operator_not", inputs={"OPERAND": [2, or2]})
    bs[or2]["parent"] = invalid

    def place_branch(price_id, price_nm):
        # if 골드 >= 가격 → 차감·설치·소리, else 에러
        gold_r = vrep("골드", V_GOLDCUR); price_r = vrep(price_nm, price_id)
        c_far = cmp_op("operator_lt", gold_r, price_r)  # 골드 < 가격
        c_enough = gen(); bs[c_enough] = mk("operator_not", inputs={"OPERAND": [2, c_far]})
        bs[c_far]["parent"] = c_enough
        neg = op("operator_subtract", 0, vrep(price_nm, price_id))
        dec_gold = b_changevar(bs, "골드", V_GOLDCUR, neg)
        s_px = b_setvar(bs, "설치X", V_PLACEX, _mousex(bs))
        s_py = b_setvar(bs, "설치Y", V_PLACEY, _mousey(bs))
        s_pt = b_setvar(bs, "설치타입", V_PLACET, vrep("선택포탑", V_SEL))
        sh_b, sp_b = b_sound(bs, 0, "build")
        bc_place = b_broadcast(bs, "포탑설치", BR_PLACE)
        chain([(dec_gold, bs[dec_gold]), (s_px, bs[s_px]), (s_py, bs[s_py]),
               (s_pt, bs[s_pt]), (sh_b, bs[sh_b]), (sp_b, bs[sp_b]),
               (bc_place, bs[bc_place])])
        sh_e, sp_e = b_sound(bs, 0, "error")
        return b_ifelse(bs, c_enough, dec_gold, sh_e)
    pb1 = place_branch(V_COSTA, "화살탑가격")
    pb2 = place_branch(V_COSTC, "대포탑가격")
    pb3 = place_branch(V_COSTM, "마법탑가격")
    sel_eq2 = cmp_op("operator_equals", vrep("선택포탑", V_SEL), 2)
    if_p2 = b_ifelse(bs, sel_eq2, pb2, pb3)
    sel_eq1 = cmp_op("operator_equals", vrep("선택포탑", V_SEL), 1)
    if_price = b_ifelse(bs, sel_eq1, pb1, if_p2)
    # 설치 불가면 에러
    sh_inv, sp_inv = b_sound(bs, 0, "error")
    if_valid = b_ifelse(bs, invalid, if_price, sh_inv)

    # 클릭 지점으로 커서 이동 → 팔레트 위가 아니면 설치 시도 → 마우스 뗄 때까지 대기(1클릭=1설치)
    g2x = gen(); bs[g2x] = mk("sensing_mousex"); g2y = gen(); bs[g2y] = mk("sensing_mousey")
    g2 = gen(); bs[g2] = mk("motion_gotoxy", inputs={"X": slot(g2x), "Y": slot(g2y)})
    bs[g2x]["parent"] = g2; bs[g2y]["parent"] = g2
    tc_pal2 = b_touching(bs, "팔레트")
    notpal = gen(); bs[notpal] = mk("operator_not", inputs={"OPERAND": [2, tc_pal2]})
    bs[tc_pal2]["parent"] = notpal
    if_notpal = b_if(bs, notpal, if_valid)            # 팔레트 클릭(선택)은 조용히 무시
    md2 = gen(); bs[md2] = mk("sensing_mousedown")
    notmd = gen(); bs[notmd] = mk("operator_not", inputs={"OPERAND": [2, md2]})
    bs[md2]["parent"] = notmd
    waitnot = gen(); bs[waitnot] = mk("control_wait_until", inputs={"CONDITION": [2, notmd]})
    bs[notmd]["parent"] = waitnot
    chain([(g2, bs[g2]), (if_notpal, bs[if_notpal]), (waitnot, bs[waitnot])])

    # forever: (선택포탑>0 and 게임상태=1 and 마우스 누름) 이면 위 설치 시도
    sel_r2 = vrep("선택포탑", V_SEL); c_sel2 = cmp_op("operator_gt", sel_r2, 0)
    st_r2 = vrep("게임상태", V_STATE); c_pl2 = cmp_op("operator_equals", st_r2, 1)
    g1 = bool_op("operator_and", c_sel2, c_pl2)
    md = gen(); bs[md] = mk("sensing_mousedown")
    c_can = bool_op("operator_and", g1, md)
    if_click = b_if(bs, c_can, g2)                    # 본문 머리 = g2 → if_notpal → waitnot
    w2 = b_wait(bs, 0.01)
    chain([(if_click, bs[if_click]), (w2, bs[w2])])
    fe2 = b_forever(bs, if_click)
    chain([(hc, bs[hc]), (fe2, bs[fe2])])

    add_comment(bs, comments, hc,
        "🧱 마우스로 클릭해서 포탑 설치!\n"
        "팔레트에서 포탑을 고른 뒤(선택포탑>0) 잔디를 클릭하면 그 자리에 세워져요. "
        "예전엔 반투명 커서를 직접 클릭해야 해서 가운데(투명)를 누르면 안 됐는데, 이제 마우스 누름을 "
        "직접 감지해 어디를 눌러도 잡혀요. 길·성·다른 포탑 위엔 못 짓고 골드도 가격보다 많아야 해요.",
        x=720, y=60, w=350, h=190)

    return bs, comments

def _mousex(bs):
    bid = gen(); bs[bid] = mk("sensing_mousex"); return bid
def _mousey(bs):
    bid = gen(); bs[bid] = mk("sensing_mousey"); return bid

# ============================================================
#  팔레트 (PALETTE: 포탑 선택 바)
# ============================================================
def build_palette_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-150)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs]), (front, bs[front])])

    # 해금 상태 코스튬 forever
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sw_both = b_costume(bs, "둘다잠금")
    sw_ca = b_costume(bs, "대포해금")
    sw_ma = b_costume(bs, "마법해금")
    sw_all = b_costume(bs, "모두해금")
    # if 대포해금=0 and 마법해금=0 → 둘다잠금 ; elif 마법해금=0 → 대포해금 ; elif 대포해금=0 → 마법해금 ; else 모두해금
    ca0a = cmp_op("operator_equals", vrep("대포탑해금", V_UNCA), 0)
    ma0a = cmp_op("operator_equals", vrep("마법탑해금", V_UNMA), 0)
    c_both = bool_op("operator_and", ca0a, ma0a)
    ma0b = cmp_op("operator_equals", vrep("마법탑해금", V_UNMA), 0)
    ca0c = cmp_op("operator_equals", vrep("대포탑해금", V_UNCA), 0)
    if_inner2 = b_ifelse(bs, ca0c, sw_ma, sw_all)
    if_inner = b_ifelse(bs, ma0b, sw_ca, if_inner2)
    if_cos = b_ifelse(bs, c_both, sw_both, if_inner)
    w = b_wait(bs, 0.1)
    chain([(if_cos, bs[if_cos]), (w, bs[w])])
    fe = b_forever(bs, if_cos)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    # 클릭(마우스 누름 폴링) → 4구간 판정 (버튼 경계 scratch x: -116 / 0 / 116)
    #   x<-116 → 화살탑(1) ; <0 → 대포탑(2, 해금시) ; <116 → 마법탑(3, 해금시) ; 그밖 → 성수리(즉시)
    #  ※ when-this-sprite-clicked 대신 forever 폴링: 포탑을 하나 고르면 유령미리보기(맨 앞)가 마우스
    #    위에 떠 다음 팔레트 버튼 클릭을 가로채던 버그가 있었음 → 마우스 누름을 직접 감지해 front 가림과
    #    무관하게 항상 먹히게 함.
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=380, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # 1구간: 선택포탑=1
    set_sel1 = b_setvar(bs, "선택포탑", V_SEL, 1)
    # 2구간: if 대포해금=1 → 선택포탑=2
    set_sel2 = b_setvar(bs, "선택포탑", V_SEL, 2)
    ca1 = cmp_op("operator_equals", vrep("대포탑해금", V_UNCA), 1)
    if_ca = b_if(bs, ca1, set_sel2)
    # 3구간: if 마법해금=1 → 선택포탑=3
    set_sel3 = b_setvar(bs, "선택포탑", V_SEL, 3)
    ma1 = cmp_op("operator_equals", vrep("마법탑해금", V_UNMA), 1)
    if_ma = b_if(bs, ma1, set_sel3)
    # 4구간(성수리): 즉시 액션 — 선택포탑은 그대로!
    #   if 골드>=수리비용 and 성체력<성최대체력 → 골드-=수리비용 ; 성체력+=수리량 ; 상한 클램프 ; 수리음
    #   else → 에러음 (변화 없음)
    gold_r = vrep("골드", V_GOLDCUR); cost_r = vrep("수리비용", V_REPAIRCOST)
    c_poor = cmp_op("operator_lt", gold_r, cost_r)           # 골드 < 수리비용
    c_gold = gen(); bs[c_gold] = mk("operator_not", inputs={"OPERAND": [2, c_poor]})
    bs[c_poor]["parent"] = c_gold                            # 골드 >= 수리비용
    castle_r = vrep("성체력", V_CASTLE); cmax_r = vrep("성최대체력", V_CASTLEMAX)
    c_notfull = cmp_op("operator_lt", castle_r, cmax_r)      # 성체력 < 성최대체력
    c_can = bool_op("operator_and", c_gold, c_notfull)
    neg_cost = op("operator_subtract", 0, vrep("수리비용", V_REPAIRCOST))
    dec_gold = b_changevar(bs, "골드", V_GOLDCUR, neg_cost)
    add_hp = b_changevar(bs, "성체력", V_CASTLE, vrep("수리량", V_REPAIRAMT))
    castle_r2 = vrep("성체력", V_CASTLE); cmax_r2 = vrep("성최대체력", V_CASTLEMAX)
    c_over = cmp_op("operator_gt", castle_r2, cmax_r2)       # 성체력 > 성최대체력
    set_clamp = b_setvar(bs, "성체력", V_CASTLE, vrep("성최대체력", V_CASTLEMAX))
    if_clamp = b_if(bs, c_over, set_clamp)
    sh_rep, sp_rep = b_sound(bs, 0, "repair")
    chain([(dec_gold, bs[dec_gold]), (add_hp, bs[add_hp]), (if_clamp, bs[if_clamp]),
           (sh_rep, bs[sh_rep]), (sp_rep, bs[sp_rep])])
    sh_err, sp_err = b_sound(bs, 0, "error")
    repair_head = b_ifelse(bs, c_can, dec_gold, sh_err)
    # 중첩 구간 판정 (mousex 세 번 비교)
    mxc = gen(); bs[mxc] = mk("sensing_mousex")
    c_c = cmp_op("operator_lt", mxc, 116)
    if_c = b_ifelse(bs, c_c, if_ma, repair_head)
    mxb = gen(); bs[mxb] = mk("sensing_mousex")
    c_b = cmp_op("operator_lt", mxb, 0)
    if_b = b_ifelse(bs, c_b, if_ca, if_c)
    mxa = gen(); bs[mxa] = mk("sensing_mousex")
    c_a = cmp_op("operator_lt", mxa, -116)
    if_click = b_ifelse(bs, c_a, set_sel1, if_b)

    # 디바운스: 한 번 처리하면 마우스 뗄 때까지 대기 (1클릭=1동작)
    md2 = gen(); bs[md2] = mk("sensing_mousedown")
    notmd = gen(); bs[notmd] = mk("operator_not", inputs={"OPERAND": [2, md2]})
    bs[md2]["parent"] = notmd
    waitnot = gen(); bs[waitnot] = mk("control_wait_until", inputs={"CONDITION": [2, notmd]})
    bs[notmd]["parent"] = waitnot
    chain([(if_click, bs[if_click]), (waitnot, bs[waitnot])])   # 본문: 버튼판정 → 디바운스

    # 폴링 게이트: (마우스 누름) and (게임상태=1) and (마우스 y < -116, 즉 화면 하단 팔레트 띠)
    #   팔레트는 y=-150 중심·높이 70 → 스프라이트는 y[-185,-115]. y<-116 이면 팔레트 띠 클릭으로 간주.
    md = gen(); bs[md] = mk("sensing_mousedown")
    c_state = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    my = gen(); bs[my] = mk("sensing_mousey")
    c_band = cmp_op("operator_lt", my, -116)
    g1 = bool_op("operator_and", md, c_state)
    cond = bool_op("operator_and", g1, c_band)
    if_poll = b_if(bs, cond, if_click)                 # 본문 머리 = if_click → waitnot
    w = b_wait(bs, 0.01)
    chain([(if_poll, bs[if_poll]), (w, bs[w])])
    fe_poll = b_forever(bs, if_poll)
    chain([(hc, bs[hc]), (fe_poll, bs[fe_poll])])

    add_comment(bs, comments, hc,
        "🖱️ 팔레트 띠(화면 하단)를 마우스로 누른 가로 위치로 4구간을 나눠요.\n"
        "유령미리보기/커서가 맨 앞에 떠 있어도 가려지지 않도록 'when 클릭' 대신 마우스 누름을 직접 "
        "폴링해요(버그 수정). 왼쪽부터 화살탑·대포탑·마법탑을 고르고(선택포탑 1·2·3), 맨 오른쪽 "
        "'성수리'를 누르면 골드 수리비용을 내고 성체력을 수리량만큼 회복해요(성최대체력에서 멈춤). "
        "골드가 모자라거나 이미 풀피면 에러음만 나요. 성수리는 선택포탑을 바꾸지 않아요! "
        "한 번 처리하면 마우스 뗄 때까지 대기해 1클릭=1동작이에요.",
        x=720, y=180, w=360, h=210)

    return bs, comments

# ============================================================
#  숫자팝업 (NUMBER POPUP: 흰 데미지 / 금 골드, say 미사용)
# ============================================================
def build_popup_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    orig0 = b_setvar(bs, "복제됨", V_POP_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 데미지표시 → 자릿수만큼 클론 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["데미지표시", BR_DMG]})
    isc = vrep("복제됨", V_POP_ISC); cond_orig = cmp_op("operator_equals", isc, 0)
    dval_r = vrep("데미지표시값", V_DMGVAL)
    len_b = gen(); bs[len_b] = mk("operator_length", inputs={"STRING": slot(dval_r)})
    bs[dval_r]["parent"] = len_b
    set_len = b_setvar(bs, "데미지글자수", V_DMGLEN, len_b)
    set_pos1 = b_setvar(bs, "데미지자리", V_DMGPOS, 1)
    pos_r = vrep("데미지자리", V_DMGPOS); dval_r2 = vrep("데미지표시값", V_DMGVAL)
    letter_b = gen(); bs[letter_b] = mk("operator_letter_of",
        inputs={"LETTER": slot(pos_r), "STRING": slot(dval_r2)})
    bs[pos_r]["parent"] = letter_b; bs[dval_r2]["parent"] = letter_b
    set_digit = b_setvar(bs, "데미지숫자", V_DMGDIG, letter_b)
    pos_r2 = vrep("데미지자리", V_DMGPOS); pos_m1 = op("operator_subtract", pos_r2, 1)
    off_left = op("operator_multiply", pos_m1, 14)
    len_r = vrep("데미지글자수", V_DMGLEN); len_m1 = op("operator_subtract", len_r, 1)
    off_ctr = op("operator_multiply", len_m1, 7)
    off_fin = op("operator_subtract", off_left, off_ctr)
    set_off = b_setvar(bs, "데미지오프셋", V_DMGOFF, off_fin)
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    inc_pos = b_changevar(bs, "데미지자리", V_DMGPOS, 1)
    w_sp = b_wait(bs, 0.05)
    chain([(set_digit, bs[set_digit]), (set_off, bs[set_off]), (cclone, bs[cclone]),
           (inc_pos, bs[inc_pos]), (w_sp, bs[w_sp])])
    rep = b_repeat(bs, vrep("데미지글자수", V_DMGLEN), set_digit)
    chain([(set_len, bs[set_len]), (set_pos1, bs[set_pos1]), (rep, bs[rep])])
    if_spawn = b_if(bs, cond_orig, set_len)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체 — 코스튬 = 데미지숫자 + 팝업종류*10 + 1
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_POP_ISC, 1)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    k10 = op("operator_multiply", vrep("팝업종류", V_DMGKIND), 10)
    sum1 = op("operator_add", vrep("데미지숫자", V_DMGDIG), k10)
    idx = op("operator_add", sum1, 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(idx)})
    bs[idx]["parent"] = sw
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
    rep_an = b_repeat(bs, 12, ch_y)
    del_c = gen(); bs[del_c] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (front, bs[front]), (sz, bs[sz]),
           (sw, bs[sw]), (g, bs[g]), (clr_gh, bs[clr_gh]), (show, bs[show]),
           (rep_an, bs[rep_an]), (del_c, bs[del_c])])
    return bs, comments

# ============================================================
#  강화카드 (UPGRADE CARD)
# ============================================================
def build_card_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(20)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs]), (front, bs[front])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["강화등장", BR_UP]})
    show = gen(); bs[show] = mk("looks_show")
    k1 = b_keypressed(bs, "1"); k2 = b_keypressed(bs, "2")
    k3 = b_keypressed(bs, "3"); k4 = b_keypressed(bs, "4")
    or12 = bool_op("operator_or", k1, k2); or123 = bool_op("operator_or", or12, k3)
    or1234 = bool_op("operator_or", or123, k4)
    wu = b_waituntil(bs, or1234)
    # 1 공격력보너스 += 강화량
    ch_atk = b_changevar(bs, "공격력보너스", V_BUFATK, vrep("강화량", V_UP))
    if_k1 = b_if(bs, b_keypressed(bs, "1"), ch_atk)
    # 2 사거리보너스 += 10*강화량
    rng_amt = op("operator_multiply", 10, vrep("강화량", V_UP))
    ch_rng = b_changevar(bs, "사거리보너스", V_BUFRNG, rng_amt)
    if_k2 = b_if(bs, b_keypressed(bs, "2"), ch_rng)
    # 3 연사보너스 *= 0.85, 하한 0.3
    rof_mul = op("operator_multiply", vrep("연사보너스", V_BUFROF), 0.85)
    set_rof = b_setvar(bs, "연사보너스", V_BUFROF, rof_mul)
    rof_r = vrep("연사보너스", V_BUFROF); c_low = cmp_op("operator_lt", rof_r, 0.3)
    set_rof_min = b_setvar(bs, "연사보너스", V_BUFROF, 0.3)
    if_clamp = b_if(bs, c_low, set_rof_min)
    chain([(set_rof, bs[set_rof]), (if_clamp, bs[if_clamp])])
    if_k3 = b_if(bs, b_keypressed(bs, "3"), set_rof)
    # 4 골드 += 강화골드량
    ch_gold = b_changevar(bs, "골드", V_GOLDCUR, vrep("강화골드량", V_UPGOLD))
    if_k4 = b_if(bs, b_keypressed(bs, "4"), ch_gold)
    sh_up, sp_up = b_sound(bs, 0, "upgrade")
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    w1 = b_wait(bs, 0.15)
    inc_wave = b_changevar(bs, "웨이브", V_WAVE, 1)
    # 해금 갱신
    wv_r2 = vrep("웨이브", V_WAVE); unlkc_r2 = vrep("대포탑해금웨이브", V_UNLKC)
    lt_ca = cmp_op("operator_lt", wv_r2, unlkc_r2)
    ge_ca = gen(); bs[ge_ca] = mk("operator_not", inputs={"OPERAND": [2, lt_ca]})
    bs[lt_ca]["parent"] = ge_ca
    set_unca = b_setvar(bs, "대포탑해금", V_UNCA, 1)
    if_unca = b_if(bs, ge_ca, set_unca)
    wv_r3 = vrep("웨이브", V_WAVE); unlkm_r = vrep("마법탑해금웨이브", V_UNLKM)
    lt_ma = cmp_op("operator_lt", wv_r3, unlkm_r)
    ge_ma = gen(); bs[ge_ma] = mk("operator_not", inputs={"OPERAND": [2, lt_ma]})
    bs[lt_ma]["parent"] = ge_ma
    set_unma = b_setvar(bs, "마법탑해금", V_UNMA, 1)
    if_unma = b_if(bs, ge_ma, set_unma)
    set_spawned0 = b_setvar(bs, "스폰완료", V_SPAWNED, 0)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    bc_done = b_broadcast(bs, "강화완료", BR_UPDONE)
    chain([(hb, bs[hb]), (show, bs[show]), (wu, bs[wu]),
           (if_k1, bs[if_k1]), (if_k2, bs[if_k2]), (if_k3, bs[if_k3]), (if_k4, bs[if_k4]),
           (sh_up, bs[sh_up]), (sp_up, bs[sp_up]), (hi2, bs[hi2]), (w1, bs[w1]),
           (inc_wave, bs[inc_wave]), (if_unca, bs[if_unca]), (if_unma, bs[if_unma]),
           (set_spawned0, bs[set_spawned0]), (set_st1, bs[set_st1]), (bc_done, bs[bc_done])])

    add_comment(bs, comments, hb,
        "⬆️ 1·2·3·4 키로 강화를 골라요. 고르면 바로 다음 웨이브 시작!\n"
        "1 공격력보너스+ · 2 사거리보너스+ · 3 연사보너스(간격 ×0.85) · 4 골드+. "
        "보너스 변수가 쌓여서 모든 포탑이 점점 강해져요.",
        x=420, y=180, w=330, h=160)

    return bs, comments

# ============================================================
#  게임오버 (GAME OVER 배너)
# ============================================================
def build_gameover_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    s1 = vrep("게임상태", V_STATE); c1 = cmp_op("operator_equals", s1, 1)
    wu1 = b_waituntil(bs, c1)
    s2 = vrep("게임상태", V_STATE); c0 = cmp_op("operator_equals", s2, 0)
    wu2 = b_waituntil(bs, c0)
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs]),
           (front, bs[front]), (wu1, bs[wu1]), (wu2, bs[wu2]), (show, bs[show])])
    return bs, comments

# ============================================================
#  유령미리보기 (GHOST PREVIEW: 선택 포탑을 마우스 위에 반투명 표시 — 시각 전용)
# ============================================================
def build_ghost_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화 — 숨김 + 반투명(GHOST 55) + 포탑 크기(70)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    gh = gen(); bs[gh] = mk("looks_seteffectto", inputs={"VALUE": num(55)},
        fields={"EFFECT": ["GHOST", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz]), (gh, bs[gh])])

    # (B) 게임시작 후 forever: 선택포탑>0 and 게임상태=1 이면 마우스 따라 + 선택 코스튬
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    sel_r = vrep("선택포탑", V_SEL); c_sel = cmp_op("operator_gt", sel_r, 0)
    st_r = vrep("게임상태", V_STATE); c_pl = cmp_op("operator_equals", st_r, 1)
    c_on = bool_op("operator_and", c_sel, c_pl)
    show = gen(); bs[show] = mk("looks_show")
    mx = gen(); bs[mx] = mk("sensing_mousex"); my = gen(); bs[my] = mk("sensing_mousey")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(mx), "Y": slot(my)})
    bs[mx]["parent"] = g; bs[my]["parent"] = g
    sel_cos = vrep("선택포탑", V_SEL)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(sel_cos)})
    bs[sel_cos]["parent"] = sw
    chain([(show, bs[show]), (g, bs[g]), (sw, bs[sw])])
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    if_on = b_ifelse(bs, c_on, show, hi2)
    w = b_wait(bs, 0.02)
    chain([(front, bs[front]), (if_on, bs[if_on]), (w, bs[w])])
    fe = b_forever(bs, front)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    add_comment(bs, comments, hb,
        "👻 지금 고른 포탑을 마우스 위에 반투명(고스트 55)으로 미리 보여줘요.\n"
        "선택포탑(1·2·3)에 맞는 코스튬으로 바꿔 마우스를 따라다녀요. 시각 전용이라 설치 판정에는 "
        "쓰지 않아요 — 진짜 설치 가능 여부는 '건설커서'의 작은 십자선이 따로 검사해요(설치가 쉽도록).",
        x=420, y=180, w=340, h=170)

    return bs, comments

# ============================================================
#  선택표시 (SELECTION HIGHLIGHT: 고른 팔레트 버튼을 노란 테두리로 강조)
# ============================================================
def build_highlight_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sel_r = vrep("선택포탑", V_SEL); c_sel = cmp_op("operator_gt", sel_r, 0)
    # x = -174 + (선택포탑-1)*116  (버튼 중심: 1→-174, 2→-58, 3→58)
    sub = op("operator_subtract", vrep("선택포탑", V_SEL), 1)
    mul = op("operator_multiply", sub, 116)
    xexpr = op("operator_add", -174, mul)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(xexpr), "Y": num(-150)})
    bs[xexpr]["parent"] = g
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(g, bs[g]), (front, bs[front]), (show, bs[show])])
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    if_on = b_ifelse(bs, c_sel, g, hi2)
    w = b_wait(bs, 0.05)
    chain([(if_on, bs[if_on]), (w, bs[w])])
    fe = b_forever(bs, if_on)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    add_comment(bs, comments, hb,
        "✨ 지금 고른 포탑 버튼을 노란 테두리로 강조해요.\n"
        "선택포탑(1·2·3)에 맞는 버튼 위치로 가서 보여주고, 아무것도 안 골랐으면(0) 숨어요.",
        x=420, y=180, w=320, h=140)

    return bs, comments

# ============================================================
#  번개효과 (LIGHTNING FLASH: 주문시전 받으면 전체 흰 번쩍, 0.1초)
# ============================================================
def build_flash_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["주문시전", BR_SPELL]})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})

    def seteff(effect, val):
        bid = gen(); bs[bid] = mk("looks_seteffectto", inputs={"VALUE": num(val)},
            fields={"EFFECT": [effect, None]})
        return bid

    # (1차 플래시) 흰 화면 번쩍 — 쾅!
    gh0 = seteff("GHOST", 0)
    cos_f1 = b_costume(bs, "번쩍")
    show = gen(); bs[show] = mk("looks_show")
    w1 = b_wait(bs, 0.04)
    # (번개 줄기 1) 내리꽂는 지그재그
    cos_b1 = b_costume(bs, "번개1")
    w2 = b_wait(bs, 0.05)
    # (2차 플래시) 짧게 한 번 더 점멸 (살짝 옅게)
    gh1 = seteff("GHOST", 20)
    cos_f2 = b_costume(bs, "번쩍")
    w3 = b_wait(bs, 0.035)
    # (번개 줄기 2·3) 다른 가닥으로 번쩍번쩍
    gh2 = seteff("GHOST", 0)
    cos_b2 = b_costume(bs, "번개2")
    w4 = b_wait(bs, 0.05)
    cos_b3 = b_costume(bs, "번개3")
    w5 = b_wait(bs, 0.05)
    # (페이드 아웃) ghost 를 키우며 스르륵 사라짐
    inc = gen(); bs[inc] = mk("looks_changeeffectby", inputs={"CHANGE": num(25)},
        fields={"EFFECT": ["GHOST", None]})
    wf = b_wait(bs, 0.03)
    chain([(inc, bs[inc]), (wf, bs[wf])])
    rep = b_repeat(bs, 4, inc)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(hb, bs[hb]), (front, bs[front]), (gh0, bs[gh0]), (cos_f1, bs[cos_f1]),
           (show, bs[show]), (w1, bs[w1]), (cos_b1, bs[cos_b1]), (w2, bs[w2]),
           (gh1, bs[gh1]), (cos_f2, bs[cos_f2]), (w3, bs[w3]), (gh2, bs[gh2]),
           (cos_b2, bs[cos_b2]), (w4, bs[w4]), (cos_b3, bs[cos_b3]), (w5, bs[w5]),
           (rep, bs[rep]), (hi2, bs[hi2])])

    add_comment(bs, comments, hb,
        "⚡ 번개가 칠 때(주문시전) '쾅!' — 흰 화면이 빠르게 두 번 점멸하고, 위에서 내리꽂는 지그재그 "
        "번개 줄기(번개1·2·3 코스튬)가 번쩍번쩍 바뀌다가 ghost 로 스르륵 사라져요. 총 0.3초쯤, "
        "시각 연출 전용이라 데미지·쿨은 안 건드려요(우르릉 소리는 주문버튼이 냅니다).",
        x=420, y=180, w=340, h=170)
    return bs, comments

# ============================================================
#  주문버튼 (SPELL HUD: ⚡ 전체 번개 시전 + 준비/충전 표시)
# ============================================================
def build_spellbutton_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    def b_not(c):
        nb = gen(); bs[nb] = mk("operator_not", inputs={"OPERAND": [2, c]})
        bs[c]["parent"] = nb
        return nb

    def cast_chain():
        # if (주문쿨남음<=0) and (게임상태=1) and (주문횟수>0)
        #   → 주문쿨남음=주문쿨 ; 주문횟수-1 ; 우르릉 ; 주문시전 방송
        # 게임당 주문최대횟수(3)번만 쓸 수 있고 긴 쿨(20). 아껴 쓰는 필살기.
        left_pos = cmp_op("operator_gt", vrep("주문쿨남음", V_SPELLLEFT), 0)
        not_cd = b_not(left_pos)                                  # 주문쿨남음<=0 (부동소수 등호 금지)
        st = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
        cnt_pos = cmp_op("operator_gt", vrep("주문횟수", V_SPELLCOUNT), 0)  # 남은 횟수>0 (부등호)
        cond = bool_op("operator_and", bool_op("operator_and", not_cd, st), cnt_pos)
        set_left = b_setvar(bs, "주문쿨남음", V_SPELLLEFT, vrep("주문쿨", V_SPELLCD))
        dec_cnt = b_changevar(bs, "주문횟수", V_SPELLCOUNT, -1)   # 시전 성공 시 1회 차감
        sh, sp = b_sound(bs, 0, "thunder")
        bc = b_broadcast(bs, "주문시전", BR_SPELL)
        chain([(set_left, bs[set_left]), (dec_cnt, bs[dec_cnt]), (sh, bs[sh]), (sp, bs[sp]), (bc, bs[bc])])
        return b_if(bs, cond, set_left)

    # (A) 깃발: 위치·크기·코스튬 + forever(재충전 + 준비/충전 코스튬)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(40), "Y": num(150)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    sw_ready0 = b_costume(bs, "준비됨")
    # forever: 재충전(주문쿨남음>0 → -0.1)
    #   + 코스튬: 만약 주문횟수<=0 → 소진(준비됨 절대 안 뜸)
    #            아니면 (주문쿨남음<=0 → 준비됨 / else 충전중)
    left_pos2 = cmp_op("operator_gt", vrep("주문쿨남음", V_SPELLLEFT), 0)
    dec_left = b_changevar(bs, "주문쿨남음", V_SPELLLEFT, -0.1)
    if_rech = b_if(bs, left_pos2, dec_left)
    left_pos3 = cmp_op("operator_gt", vrep("주문쿨남음", V_SPELLLEFT), 0)
    sw_charge = b_costume(bs, "충전중")
    sw_ready = b_costume(bs, "준비됨")
    if_inner = b_ifelse(bs, left_pos3, sw_charge, sw_ready)   # 충전중 / 준비됨
    cnt_pos_c = cmp_op("operator_gt", vrep("주문횟수", V_SPELLCOUNT), 0)  # 남은 횟수>0
    sw_exhaust = b_costume(bs, "소진")
    if_cos = b_ifelse(bs, cnt_pos_c, if_inner, sw_exhaust)   # >0 → 쿨 표시 / 0이하 → 소진
    w = b_wait(bs, 0.1)
    chain([(if_rech, bs[if_rech]), (if_cos, bs[if_cos]), (w, bs[w])])
    fe = b_forever(bs, if_rech)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (show, bs[show]), (sw_ready0, bs[sw_ready0]), (fe, bs[fe])])

    # (B) 스페이스 키 → 시전
    hk = gen(); bs[hk] = mk("event_whenkeypressed", top=True, x=360, y=20,
        fields={"KEY_OPTION": ["space", None]})
    cast_k = cast_chain()
    chain([(hk, bs[hk]), (cast_k, bs[cast_k])])

    # (C) HUD 버튼 클릭 → 시전 (같은 가드)
    hc = gen(); bs[hc] = mk("event_whenthisspriteclicked", top=True, x=360, y=220)
    cast_c = cast_chain()
    chain([(hc, bs[hc]), (cast_c, bs[cast_c])])

    add_comment(bs, comments, hk,
        "⚡ 스페이스 키(또는 이 번개 버튼 클릭)로 전체 번개 주문을 써요!\n"
        "이 주문은 게임당 딱 주문최대횟수(3)번만 쓸 수 있는 필살기예요. 주문쿨남음이 0 이하이고 "
        "전투중(게임상태=1)이면서 주문횟수가 0보다 클 때만 발동! 쓰면 주문횟수가 1 줄고 주문쿨남음="
        "주문쿨(20)로 채워져, 긴 쿨 동안엔 다시 못 써요. 3번 다 쓰면 더 못 써요. 우르릉 번쩍!",
        x=720, y=20, w=350, h=200)
    add_comment(bs, comments, fe,
        "🔋 재충전·남은 횟수 표시: 주문쿨남음이 0보다 크면 매 0.1초마다 0.1씩 줄어요. "
        "코스튬은 — 주문횟수가 0 이하면 '소진'(준비됨이 절대 안 떠서 더 못 씀이 보여요), 아니면 "
        "주문쿨남음 0 이하일 때 '준비됨' / 충전 중이면 '충전중'(부동소수 등호 대신 >0 / <=0 부등호).",
        x=-360, y=320, w=340, h=180)
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
    castle_md5 = save_svg(CASTLE_SVG)
    gob_md5    = save_svg(GOBLIN_SVG)
    orc_md5    = save_svg(ORC_SVG)
    troll_md5  = save_svg(TROLL_SVG)
    ex_md5     = save_svg(EXPLOSION_SVG)
    art_md5    = save_svg(ARROWTOWER_SVG)
    cat_md5    = save_svg(CANNONTOWER_SVG)
    mat_md5    = save_svg(MAGICTOWER_SVG)
    arrow_md5  = save_svg(ARROW_SVG)
    ball_md5   = save_svg(CANNONBALL_SVG)
    orb_md5    = save_svg(MAGICORB_SVG)
    cursor_md5 = save_svg(CURSOR_SVG)
    pal_md5    = [save_svg(s) for s in PALETTE_SVGS]
    hl_md5     = save_svg(HIGHLIGHT_SVG)
    card_md5   = save_svg(CARD_SVG)
    rs_md5     = save_svg(RESULT_SVG)
    flash_md5  = save_svg(FLASH_SVG)
    light_md5  = [save_svg(s) for s in LIGHTNING_SVGS]
    spr_md5    = save_svg(SPELL_READY_SVG)
    spc_md5    = save_svg(SPELL_CHARGE_SVG)
    spx_md5    = save_svg(SPELL_EXHAUST_SVG)
    wd_md5     = [save_svg(s) for s in WHITE_DIGITS]
    gd_md5     = [save_svg(s) for s in GOLD_DIGITS]

    def save_wav(samples):
        b = _wav_bytes(samples)
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    arrow_s, arrow_n = save_wav(synth_arrow())
    cannon_s, cannon_n = save_wav(synth_cannon())
    magic_s, magic_n = save_wav(synth_magic())
    hit_s, hit_n = save_wav(synth_hit())
    kill_s, kill_n = save_wav(synth_kill())
    coin_s, coin_n = save_wav(synth_coin())
    castle_s, castle_n = save_wav(synth_castlehit())
    horn_s, horn_n = save_wav(synth_horn())
    build_s, build_n = save_wav(synth_build())
    error_s, error_n = save_wav(synth_error())
    upg_s, upg_n = save_wav(synth_upgrade())
    repair_s, repair_n = save_wav(synth_repair())
    thunder_s, thunder_n = save_wav(synth_thunder())

    def snd(name, md5, n):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "",
                "rate": SND_RATE, "sampleCount": n, "md5ext": f"{md5}.wav"}

    stage_blocks,  stage_cmt  = build_stage_blocks()
    castle_blocks, castle_cmt = build_castle_blocks()
    mon_blocks,    mon_cmt    = build_monster_blocks()
    tw_blocks,     tw_cmt     = build_tower_blocks()
    bolt_blocks,   bolt_cmt   = build_bolt_blocks()
    cur_blocks,    cur_cmt    = build_cursor_blocks()
    pal_blocks,    pal_cmt    = build_palette_blocks()
    pop_blocks,    pop_cmt    = build_popup_blocks()
    card_blocks,   card_cmt   = build_card_blocks()
    go_blocks,     go_cmt     = build_gameover_blocks()
    ghost_blocks,  ghost_cmt  = build_ghost_blocks()
    hl_blocks,     hl_cmt     = build_highlight_blocks()
    flash_blocks,  flash_cmt  = build_flash_blocks()
    spell_blocks,  spell_cmt  = build_spellbutton_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 43
            V_GOLD0: ["기본골드", 150], V_COSTA: ["화살탑가격", 50], V_COSTC: ["대포탑가격", 100],
            V_COSTM: ["마법탑가격", 150], V_WAVEGOLD: ["웨이브클리어골드", 30], V_UPGOLD: ["강화골드량", 40],
            V_UP: ["강화량", 1], V_CASTLEMAX: ["성최대체력", 20], V_UNLKC: ["대포탑해금웨이브", 2],
            V_UNLKM: ["마법탑해금웨이브", 4], V_BASECNT: ["기본몬스터수", 6], V_CNTINC: ["웨이브당몬스터증가", 2],
            V_SPGAP: ["몬스터간격", 0.8], V_HPINC: ["웨이브체력증가", 8], V_SPINC: ["웨이브속도증가", 0.13],
            V_REACH: ["도달반경", 12], V_BOLTSPD: ["탄속도", 9],
            V_GOBHP: ["고블린_체력", 3], V_GOBSP: ["고블린_속도", 2.2], V_GOBGOLD: ["고블린_골드", 5],
            V_ORCHP: ["오크_체력", 8], V_ORCSP: ["오크_속도", 1.5], V_ORCGOLD: ["오크_골드", 10],
            V_TROLLHP: ["트롤_체력", 20], V_TROLLSP: ["트롤_속도", 0.9], V_TROLLGOLD: ["트롤_골드", 25],
            V_ARR: ["화살탑_사거리", 120], V_ARD: ["화살탑_공격력", 1], V_ARG: ["화살탑_간격", 0.45],
            V_ARS: ["화살탑_폭발반경", 16], V_CAR: ["대포탑_사거리", 100], V_CAD: ["대포탑_공격력", 2],
            V_CAG: ["대포탑_간격", 1.3], V_CAS: ["대포탑_폭발반경", 60], V_MAR: ["마법탑_사거리", 150],
            V_MAD: ["마법탑_공격력", 4], V_MAG: ["마법탑_간격", 0.85], V_MAS: ["마법탑_폭발반경", 20],
            V_REPAIRCOST: ["수리비용", 60], V_REPAIRAMT: ["수리량", 5],
            V_SPELLDMG: ["주문공격력", 9999], V_SPELLCD: ["주문쿨", 20],
            V_SPELLMAX: ["주문최대횟수", 3],
            # 진행 41
            V_STATE: ["게임상태", 1], V_WAVE: ["웨이브", 1], V_GOLDCUR: ["골드", 150],
            V_CASTLE: ["성체력", 20], V_ALIVE: ["적수", 0], V_SPAWNED: ["스폰완료", 0],
            V_SPAWNN: ["스폰카운트", 0], V_SEL: ["선택포탑", 0], V_UNCA: ["대포탑해금", 0],
            V_UNMA: ["마법탑해금", 0], V_BUFATK: ["공격력보너스", 0], V_BUFRNG: ["사거리보너스", 0],
            V_BUFROF: ["연사보너스", 1], V_PLACEX: ["설치X", 0], V_PLACEY: ["설치Y", 0],
            V_PLACET: ["설치타입", 0], V_AIMLOCK: ["조준중", 0], V_AIMTX: ["조준탑X", 0],
            V_AIMTY: ["조준탑Y", 0], V_AIMTR: ["조준탑사거리", 0], V_AIMD: ["조준거리", 99999],
            V_AIMX: ["조준X", 0], V_AIMY: ["조준Y", 0], V_AIMOK: ["조준있음", 0],
            V_FIREX: ["발사X", 0], V_FIREY: ["발사Y", 0], V_FIRET: ["발사타입", 0],
            V_BOOMX: ["폭발X", 0], V_BOOMY: ["폭발Y", 0], V_BOOMD: ["폭발데미지", 0],
            V_BOOMR: ["폭발반경", 0], V_SPAWNT: ["생성타입", 1], V_DMGVAL: ["데미지표시값", 0],
            V_DMGX: ["데미지표시x", 0], V_DMGY: ["데미지표시y", 0], V_DMGKIND: ["팝업종류", 0],
            V_DMGDIG: ["데미지숫자", 0], V_DMGOFF: ["데미지오프셋", 0], V_DMGLEN: ["데미지글자수", 0],
            V_DMGPOS: ["데미지자리", 0], V_SPELLLEFT: ["주문쿨남음", 0],
            V_SPELLCOUNT: ["주문횟수", 3],
        },
        "lists": {
            L_PATHX: ["경로X", []],
            L_PATHY: ["경로Y", []],
        },
        "broadcasts": {
            BR_START: "게임시작", BR_WAVE: "웨이브시작", BR_SPAWN: "몬스터생성", BR_AIM: "조준요청",
            BR_FIRE: "포탑발사", BR_HIT: "타격", BR_DMG: "데미지표시", BR_PLACE: "포탑설치",
            BR_UP: "강화등장", BR_UPDONE: "강화완료", BR_CASTLE: "성피격",
            BR_SPELL: "주문시전",
        },
        "blocks": stage_blocks, "comments": stage_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "전장", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [snd("horn", horn_s, horn_n)],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    castle = {
        "isStage": False, "name": "성",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": castle_blocks, "comments": castle_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "castle", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": castle_md5, "md5ext": f"{castle_md5}.svg",
            "rotationCenterX": 40, "rotationCenterY": 46}],
        "sounds": [snd("castlehit", castle_s, castle_n)],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 205, "y": 90, "size": 90, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monster = {
        "isStage": False, "name": "몬스터",
        "variables": {V_MON_ISC: ["복제됨", 0], V_MON_TYPE: ["내타입", 1], V_MON_HP: ["내체력", 3],
                      V_MON_SPD: ["내속도", 2.2], V_MON_GOLD: ["내골드", 5], V_MON_WP: ["현재점", 1]},
        "lists": {}, "broadcasts": {},
        "blocks": mon_blocks, "comments": mon_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "고블린", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": gob_md5, "md5ext": f"{gob_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "오크", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": orc_md5, "md5ext": f"{orc_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "트롤", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": troll_md5, "md5ext": f"{troll_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 30},
            {"name": "폭발", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ex_md5, "md5ext": f"{ex_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 30},
        ],
        "sounds": [snd("hit", hit_s, hit_n), snd("kill", kill_s, kill_n), snd("coin", coin_s, coin_n)],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": -240, "y": 70, "size": 55, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    tower = {
        "isStage": False, "name": "포탑",
        "variables": {V_TW_ISC: ["복제됨", 0], V_TW_TYPE: ["내타입", 1], V_TW_RNG: ["내사거리", 120],
                      V_TW_DMG: ["내공격력", 1], V_TW_GAP: ["내간격", 0.45], V_TW_SPL: ["내폭발반경", 16],
                      V_TW_CD: ["발사쿨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": tw_blocks, "comments": tw_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "화살탑", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": art_md5, "md5ext": f"{art_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 42},
            {"name": "대포탑", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": cat_md5, "md5ext": f"{cat_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 42},
            {"name": "마법탑", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": mat_md5, "md5ext": f"{mat_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 42},
        ],
        "sounds": [snd("arrow", arrow_s, arrow_n), snd("cannon", cannon_s, cannon_n),
                   snd("magic", magic_s, magic_n)],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    bolt = {
        "isStage": False, "name": "포탑탄",
        "variables": {V_BOLT_ISC: ["복제됨", 0], V_BOLT_TYPE: ["탄타입", 1], V_BOLT_DMG: ["탄공격력", 1],
                      V_BOLT_SPL: ["탄반경", 16], V_BOLT_TX: ["목표X", 0], V_BOLT_TY: ["목표Y", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": bolt_blocks, "comments": bolt_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "화살", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": arrow_md5, "md5ext": f"{arrow_md5}.svg", "rotationCenterX": 20, "rotationCenterY": 20},
            {"name": "포탄", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": ball_md5, "md5ext": f"{ball_md5}.svg", "rotationCenterX": 20, "rotationCenterY": 20},
            {"name": "마법구슬", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": orb_md5, "md5ext": f"{orb_md5}.svg", "rotationCenterX": 20, "rotationCenterY": 20},
        ],
        "sounds": [],
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 0, "size": 40, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    cursor = {
        "isStage": False, "name": "건설커서",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": cur_blocks, "comments": cur_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "ring", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": cursor_md5, "md5ext": f"{cursor_md5}.svg",
            "rotationCenterX": 60, "rotationCenterY": 60}],
        "sounds": [snd("build", build_s, build_n), snd("error", error_s, error_n)],
        "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    palette = {
        "isStage": False, "name": "팔레트",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pal_blocks, "comments": pal_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "둘다잠금", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pal_md5[0], "md5ext": f"{pal_md5[0]}.svg", "rotationCenterX": 236, "rotationCenterY": 35},
            {"name": "대포해금", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pal_md5[1], "md5ext": f"{pal_md5[1]}.svg", "rotationCenterX": 236, "rotationCenterY": 35},
            {"name": "마법해금", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pal_md5[2], "md5ext": f"{pal_md5[2]}.svg", "rotationCenterX": 236, "rotationCenterY": 35},
            {"name": "모두해금", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": pal_md5[3], "md5ext": f"{pal_md5[3]}.svg", "rotationCenterX": 236, "rotationCenterY": 35},
        ],
        "sounds": [snd("repair", repair_s, repair_n), snd("error", error_s, error_n)],
        "volume": 100, "layerOrder": 8, "visible": True,
        "x": 0, "y": -150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    popup_costumes = []
    for d in range(10):
        popup_costumes.append({"name": f"w{d}", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": wd_md5[d], "md5ext": f"{wd_md5[d]}.svg", "rotationCenterX": 16, "rotationCenterY": 22})
    for d in range(10):
        popup_costumes.append({"name": f"g{d}", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": gd_md5[d], "md5ext": f"{gd_md5[d]}.svg", "rotationCenterX": 16, "rotationCenterY": 22})
    popup = {
        "isStage": False, "name": "숫자팝업",
        "variables": {V_POP_ISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": pop_blocks, "comments": pop_cmt,
        "currentCostume": 0, "costumes": popup_costumes,
        "sounds": [],
        "volume": 100, "layerOrder": 10, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    card = {
        "isStage": False, "name": "강화카드",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": card_blocks, "comments": card_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "card", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": card_md5, "md5ext": f"{card_md5}.svg",
            "rotationCenterX": 200, "rotationCenterY": 75}],
        "sounds": [snd("upgrade", upg_s, upg_n)],
        "volume": 100, "layerOrder": 11, "visible": False,
        "x": 0, "y": 20, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    gameover = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": go_blocks, "comments": go_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "패배", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": rs_md5, "md5ext": f"{rs_md5}.svg",
            "rotationCenterX": 180, "rotationCenterY": 80}],
        "sounds": [],
        "volume": 100, "layerOrder": 12, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # 유령미리보기: 포탑 코스튬 3개 재사용(화살탑/대포탑/마법탑 이미지) — 반투명 미리보기 전용
    ghost = {
        "isStage": False, "name": "유령미리보기",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ghost_blocks, "comments": ghost_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "화살탑미리", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": art_md5, "md5ext": f"{art_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 42},
            {"name": "대포탑미리", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": cat_md5, "md5ext": f"{cat_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 42},
            {"name": "마법탑미리", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": mat_md5, "md5ext": f"{mat_md5}.svg", "rotationCenterX": 30, "rotationCenterY": 42},
        ],
        "sounds": [],
        "volume": 100, "layerOrder": 13, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    highlight = {
        "isStage": False, "name": "선택표시",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hl_blocks, "comments": hl_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "강조", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hl_md5, "md5ext": f"{hl_md5}.svg",
            "rotationCenterX": 60, "rotationCenterY": 32}],
        "sounds": [],
        "volume": 100, "layerOrder": 14, "visible": False,
        "x": 0, "y": -150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    flash = {
        "isStage": False, "name": "번개효과",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": flash_blocks, "comments": flash_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "번쩍", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": flash_md5, "md5ext": f"{flash_md5}.svg",
             "rotationCenterX": 240, "rotationCenterY": 180},
            {"name": "번개1", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": light_md5[0], "md5ext": f"{light_md5[0]}.svg",
             "rotationCenterX": 240, "rotationCenterY": 180},
            {"name": "번개2", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": light_md5[1], "md5ext": f"{light_md5[1]}.svg",
             "rotationCenterX": 240, "rotationCenterY": 180},
            {"name": "번개3", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": light_md5[2], "md5ext": f"{light_md5[2]}.svg",
             "rotationCenterX": 240, "rotationCenterY": 180},
        ],
        "sounds": [],
        "volume": 100, "layerOrder": 15, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    spellbtn = {
        "isStage": False, "name": "주문버튼",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": spell_blocks, "comments": spell_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "준비됨", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": spr_md5, "md5ext": f"{spr_md5}.svg", "rotationCenterX": 35, "rotationCenterY": 42},
            {"name": "충전중", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": spc_md5, "md5ext": f"{spc_md5}.svg", "rotationCenterX": 35, "rotationCenterY": 42},
            {"name": "소진", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": spx_md5, "md5ext": f"{spx_md5}.svg", "rotationCenterX": 35, "rotationCenterY": 42},
        ],
        "sounds": [snd("thunder", thunder_s, thunder_n)],
        "volume": 100, "layerOrder": 16, "visible": True,
        "x": 40, "y": 150, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # ---- 모니터: 웨이브 / 골드 / 성체력 (튜닝 변수는 숨김) ----
    monitors = [
        {"id": V_WAVE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "웨이브"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_GOLDCUR, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "골드"}, "spriteName": None,
         "value": 150, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 999, "isDiscrete": True},
        {"id": V_CASTLE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "성체력"}, "spriteName": None,
         "value": 20, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        # 남은 주문 횟수 — 주문버튼(우상단) 근처에 표시해서 몇 번 더 쓸 수 있는지 한눈에
        {"id": V_SPELLCOUNT, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "주문횟수"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 250, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, castle, monster, tower, bolt, cursor, palette, popup, card,
                    gameover, ghost, highlight, flash, spellbtn],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "castle-defense-builder"}
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
    for nm, b in [("stage", stage_blocks), ("castle", castle_blocks),
                  ("monster", mon_blocks), ("tower", tw_blocks), ("bolt", bolt_blocks),
                  ("cursor", cur_blocks), ("palette", pal_blocks), ("popup", pop_blocks),
                  ("card", card_blocks), ("gameover", go_blocks),
                  ("ghost", ghost_blocks), ("highlight", hl_blocks),
                  ("flash", flash_blocks), ("spellbtn", spell_blocks)]:
        print(f"  {nm:9s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
