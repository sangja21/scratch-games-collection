#!/usr/bin/env python3
"""쿠키 대 개미 (cookies-vs-ants) — 쿠키 공장 레인 타워디펜스.

설탕을 모아 5개 레인 그리드에 장치를 설치하고, 오른쪽에서 레인을 따라 왼쪽 창고로
기어오는 귀여운 만화 개미를 막아낸다. 설탕기계=설탕 생산, 쿠키캐논=레인 감지 발사,
초코벽=탱크, 밀크폭탄=광역 폭탄. 창고 앞이 뚫리면 레인당 한 번 빗자루가 구해주고, 두 번째로
뚫리면 목숨이 깎인다. 목숨 0 → GAME OVER. 점수 = 잡은 개미 수.

베이스: games/castle-defense/build.py
  - 한글 튜닝 변수 일괄 초기화(매직넘버 0) / 웨이브 매니저 / 클론 스포너 + 복제됨 가드 /
    타격 broadcast-and-wait 반경 데미지 / 자동조준 핸드셰이크 → 레인-불리언 OR /
    플로팅 숫자(say 미사용, 흰/금) / 게임오버 배너 / 전용 합성 효과음(_wav_bytes·synth_*) /
    add_comment 가이드 투어 / 팔레트·건설커서 → 메뉴판·칸 스냅 설치커서.

★ 모든 조절 값(튜닝 50개)을 한글 전역 변수로만 노출, 코드 어디서도 매직넘버를 쓰지
  않는다. 그리드는 격자시작X/격자간격X/레인시작Y/레인간격Y 손잡이로 열X·레인Y 리스트를
  통째로 계산. 초기화는 전부 Stage 깃발 클릭 한 스크립트에 모은다.
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "쿠키_대_개미.sb3")

# ============================================================
#  효과음 합성 (전용 사운드 12종) — 결정적 생성
# ============================================================
SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    """float 샘플(-1..1) 리스트 → 16-bit PCM mono WAV 바이트 (결정적)."""
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_plant(rate=SND_RATE):
    """장치 설치 성공 — '톡' 짧은 흙 설치음 (200Hz 정현파 + 클릭, 0.09초)."""
    N = int(rate * 0.09); out = []
    for i in range(N):
        t = i / rate
        click = 1.0 if t < 0.006 else 0.0
        body = math.sin(2 * math.pi * 200 * t) * math.exp(-t * 22)
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

def synth_pea(rate=SND_RATE):
    """쿠키알콩 발사 — 경쾌한 '퓻' 상승 처프 (600→900Hz, 0.06초)."""
    N = int(rate * 0.06); out = []
    for i in range(N):
        t = i / rate
        f = 600 + 300 * (t / 0.06)
        env = math.exp(-t * 26)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.45)
    return out

def synth_cherry(rate=SND_RATE):
    """밀크폭탄 폭탄 폭발 — 큰 '쾅' (노이즈버스트 + 40Hz thump, 0.3초). 결정적, 크게."""
    N = int(rate * 0.30); out = []
    rng = random.Random(20260725)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 9)
        white = rng.random() * 2 - 1
        lp = lp + 0.42 * (white - lp)
        thump = math.sin(2 * math.pi * (40 + 40 * math.exp(-t * 18)) * t)
        s = (lp * 0.7 + thump * 0.9) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_sun(rate=SND_RATE):
    """설탕 수확 — 밝은 '딩' 두 톤 상승 (988→1319Hz 정현파, 0.12초)."""
    N = int(rate * 0.12); out = []
    for i in range(N):
        t = i / rate
        f = 988 if t < 0.05 else 1319
        env = math.exp(-t * 11)
        s = (math.sin(2 * math.pi * f * t) + 0.4 * math.sin(2 * math.pi * f * 2 * t)) / 1.4
        out.append(s * env * 0.45)
    return out

def synth_chomp(rate=SND_RATE):
    """개미 갉기 — 둔한 '우걱' (120Hz 사각파 2펄스, 0.08초). 연타 소음 방지로 작게."""
    N = int(rate * 0.08); out = []
    for i in range(N):
        t = i / rate
        sq = 1.0 if math.sin(2 * math.pi * 110 * t) > 0 else -1.0
        # 두 펄스: 0~0.035, 0.04~0.075
        pulse = 1.0 if (t < 0.035 or (0.04 < t < 0.075)) else 0.0
        env = math.exp(-((t % 0.04)) * 24)
        out.append(sq * env * pulse * 0.12)  # 0.4 → 0.12 (훨씬 작게)
    return out

def synth_zombiedie(rate=SND_RATE):
    """개미 처치 — '펑' (노이즈 + 하강 thump, 0.22초). 결정적."""
    N = int(rate * 0.22); out = []
    rng = random.Random(20260613)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 12)
        white = rng.random() * 2 - 1
        lp = lp + 0.45 * (white - lp)
        thump = math.sin(2 * math.pi * (60 + 40 * math.exp(-t * 22)) * t)
        s = (lp * 0.6 + thump * 0.7) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_mower(rate=SND_RATE):
    """빗자루 발동 — '부릉' 엔진 (80Hz 톱니파 + 떨림, 0.4초)."""
    N = int(rate * 0.40); out = []
    for i in range(N):
        t = i / rate
        ph = (80 * t) % 1.0
        saw = 2 * ph - 1
        trem = 0.7 + 0.3 * math.sin(2 * math.pi * 18 * t)   # 엔진 떨림
        atk = min(1.0, t / 0.05)
        env = atk * math.exp(-t * 2.2)
        out.append(saw * trem * env * 0.4)
    return out

def synth_wave(rate=SND_RATE):
    """웨이브 시작 종/징 — 묵직한 (180Hz + 360Hz 정현파, 0.5초 페이드)."""
    N = int(rate * 0.50); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 3.2)
        s = (math.sin(2 * math.pi * 180 * t) + 0.6 * math.sin(2 * math.pi * 360 * t)) / 1.6
        out.append(s * env * 0.42)
    return out

def synth_groan(rate=SND_RATE):
    """개미 신음 — 낮고 귀여운 '우우~' (90Hz 톱니파 비브라토, 0.4초)."""
    N = int(rate * 0.40); out = []
    for i in range(N):
        t = i / rate
        vib = 90 + 6 * math.sin(2 * math.pi * 5 * t)        # 비브라토
        ph = (vib * t) % 1.0
        saw = 2 * ph - 1
        atk = min(1.0, t / 0.06)
        env = atk * math.exp(-t * 2.6)
        out.append(saw * env * 0.32)
    return out

def synth_thud(rate=SND_RATE):
    """창고 뚫림 — 거친 저음 충격 (120Hz 사각파 + 하강, 0.2초)."""
    N = int(rate * 0.20); out = []
    for i in range(N):
        t = i / rate
        f = 120 + 60 * math.exp(-t * 8)
        sq = 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0
        env = math.exp(-t * 10)
        out.append(sq * env * 0.45)
    return out

def synth_lose(rate=SND_RATE):
    """게임오버 — 하강 3음 실패 아르페지오 (392→330→262Hz, 0.4초)."""
    N = int(rate * 0.40); out = []
    for i in range(N):
        t = i / rate
        f = 392 if t < 0.13 else (330 if t < 0.26 else 262)
        env = math.exp(-((t % 0.13)) * 10)
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

# -------- 배경: 5개 컨베이어 레인 + 세로 그리드 + 창고터 + 메뉴 바 --------
# 레인 중심 scratch Y: 110,55,0,-55,-110 → SVG y = 180-Y = 70,125,180,235,290 (높이 55)
# 열 중심 scratch X: -160..160 step40 → SVG x = X+240 = 80..400
_lane_y = [70, 125, 180, 235, 290]
_lane_rects = []
for _i, _cy in enumerate(_lane_y):
    _c = "#F5E0C3" if _i % 2 == 0 else "#E8CFA8"
    _lane_rects.append(f'<rect x="56" y="{_cy-27.5:.1f}" width="384" height="55" fill="{_c}"/>')
LANES = "\n    ".join(_lane_rects)
_grid_lines = []
for _gx in range(60, 421, 40):            # 세로 칸선
    _grid_lines.append(f'<line x1="{_gx}" y1="42" x2="{_gx}" y2="318" stroke="#C4A574" stroke-width="1.5" opacity="0.55"/>')
GRIDLINES = "\n    ".join(_grid_lines)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#FFF3E0"/>
  <rect x="0" y="0" width="480" height="42" fill="#6D4C41"/>
  <rect x="0" y="318" width="480" height="42" fill="#6D4C41"/>
  <!-- 달콤한 체크 패턴 천장 느낌 -->
  <circle cx="40" cy="21" r="5" fill="#FFCC80" opacity="0.7"/>
  <circle cx="120" cy="21" r="5" fill="#FFCC80" opacity="0.7"/>
  <circle cx="200" cy="21" r="5" fill="#FFCC80" opacity="0.7"/>
  <circle cx="280" cy="21" r="5" fill="#FFCC80" opacity="0.7"/>
  <circle cx="360" cy="21" r="5" fill="#FFCC80" opacity="0.7"/>
  <circle cx="440" cy="21" r="5" fill="#FFCC80" opacity="0.7"/>
  <g>
    {LANES}
  </g>
  <g>
    {GRIDLINES}
  </g>
  <!-- 창고터(왼쪽 벽) -->
  <rect x="0" y="42" width="56" height="276" fill="#8D6E63"/>
  <rect x="0" y="42" width="56" height="276" fill="none" stroke="#5D4037" stroke-width="3"/>
  <!-- 빗자루 주차 라인 -->
  <line x1="56" y1="42" x2="56" y2="318" stroke="#5D4037" stroke-width="3"/>
  <rect x="6" y="6" width="468" height="348" rx="10" fill="none" stroke="#A1887F" stroke-width="5" opacity="0.55"/>
</svg>"""

# -------- 창고 (쿠키 상자 / 패배선) --------
HOUSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="88" height="120" viewBox="0 0 88 120">
  <ellipse cx="44" cy="114" rx="34" ry="5" fill="#000000" opacity="0.22"/>
  <rect x="10" y="28" width="68" height="82" rx="4" fill="#D4A574" stroke="#8D6E63" stroke-width="3"/>
  <rect x="16" y="36" width="56" height="12" rx="2" fill="#FFCC80"/>
  <rect x="16" y="54" width="56" height="12" rx="2" fill="#FFCC80"/>
  <rect x="16" y="72" width="56" height="12" rx="2" fill="#FFCC80"/>
  <rect x="16" y="90" width="56" height="12" rx="2" fill="#FFCC80"/>
  <circle cx="28" cy="42" r="3" fill="#E53935"/>
  <circle cx="44" cy="42" r="3" fill="#FFFFFF"/>
  <circle cx="60" cy="42" r="3" fill="#42A5F5"/>
  <circle cx="28" cy="60" r="3" fill="#FFFFFF"/>
  <circle cx="44" cy="60" r="3" fill="#E53935"/>
  <circle cx="60" cy="60" r="3" fill="#FFFFFF"/>
  <text x="44" y="24" text-anchor="middle" font-family="Arial" font-size="11" font-weight="bold" fill="#6D4C41">COOKIE</text>
</svg>"""

# -------- 개미 코스튬: 기본 / 헬멧 / 빠른 / 터짐 (귀여운 만화 톤) --------
def _ant_body(extra=""):
    return f"""  <ellipse cx="30" cy="56" rx="14" ry="3" fill="#000000" opacity="0.22"/>
  <!-- 몸통 3마디 -->
  <ellipse cx="30" cy="46" rx="10" ry="9" fill="#5D4037" stroke="#3E2723" stroke-width="2"/>
  <ellipse cx="30" cy="34" rx="9" ry="8" fill="#6D4C41" stroke="#3E2723" stroke-width="2"/>
  <ellipse cx="30" cy="22" rx="8" ry="8" fill="#5D4037" stroke="#3E2723" stroke-width="2"/>
  <!-- 더듬이 -->
  <line x1="24" y1="16" x2="18" y2="6" stroke="#3E2723" stroke-width="2" stroke-linecap="round"/>
  <line x1="36" y1="16" x2="42" y2="6" stroke="#3E2723" stroke-width="2" stroke-linecap="round"/>
  <circle cx="18" cy="5" r="2" fill="#3E2723"/>
  <circle cx="42" cy="5" r="2" fill="#3E2723"/>
  <!-- 눈 -->
  <ellipse cx="26" cy="21" rx="2.8" ry="3.2" fill="#FFFFFF"/>
  <ellipse cx="34" cy="21" rx="2.8" ry="3.2" fill="#FFFFFF"/>
  <circle cx="26" cy="22" r="1.3" fill="#222"/>
  <circle cx="34" cy="22" r="1.3" fill="#222"/>
  <!-- 다리 -->
  <line x1="20" y1="34" x2="10" y2="40" stroke="#3E2723" stroke-width="2" stroke-linecap="round"/>
  <line x1="40" y1="34" x2="50" y2="40" stroke="#3E2723" stroke-width="2" stroke-linecap="round"/>
  <line x1="20" y1="44" x2="10" y2="52" stroke="#3E2723" stroke-width="2" stroke-linecap="round"/>
  <line x1="40" y1="44" x2="50" y2="52" stroke="#3E2723" stroke-width="2" stroke-linecap="round"/>
{extra}"""

ZOMBIE1_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
{_ant_body()}
</svg>"""

ZOMBIE2_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
{_ant_body('  <ellipse cx="30" cy="12" rx="12" ry="7" fill="#90A4AE" stroke="#546E7A" stroke-width="2"/>\n  <rect x="24" y="8" width="12" height="4" rx="1" fill="#78909C"/>')}
</svg>"""

ZOMBIE3_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
{_ant_body('  <ellipse cx="18" cy="52" rx="5" ry="3" fill="#E53935"/>\n  <ellipse cx="42" cy="52" rx="5" ry="3" fill="#E53935"/>\n  <path d="M12 30 Q6 24 8 18" fill="none" stroke="#5D4037" stroke-width="2.5" stroke-linecap="round"/>')}
</svg>"""

ZOMBIE_BOOM_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30, 30, 28, 12, 11)}" fill="#A1887F" stroke="#5D4037" stroke-width="1"/>
  <polygon points="{_star_pts(30, 30, 18, 7, 11, rot=0.28)}" fill="#D7CCC8"/>
  <circle cx="30" cy="30" r="8" fill="#FFFFFF"/>
</svg>"""

# -------- 쿠키알 (발사체) --------
PEA_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">
  <circle cx="14" cy="14" r="11" fill="#D4A574" stroke="#8D6E63" stroke-width="2"/>
  <circle cx="10" cy="11" r="2.2" fill="#5D4037"/>
  <circle cx="16" cy="10" r="1.6" fill="#5D4037"/>
  <circle cx="14" cy="16" r="1.8" fill="#5D4037"/>
  <circle cx="18" cy="15" r="1.4" fill="#5D4037"/>
  <circle cx="11" cy="17" r="1.3" fill="#5D4037"/>
</svg>"""

# -------- 장치 코스튬: 설탕기계 / 쿠키캐논 / 초코벽 / 밀크폭탄 / 터짐 --------
SUNFLOWER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="60" viewBox="0 0 56 60">
  <ellipse cx="28" cy="56" rx="14" ry="3" fill="#000000" opacity="0.18"/>
  <rect x="18" y="28" width="20" height="26" rx="3" fill="#90CAF9" stroke="#1565C0" stroke-width="2.5"/>
  <rect x="14" y="18" width="28" height="14" rx="3" fill="#42A5F5" stroke="#1565C0" stroke-width="2"/>
  <circle cx="28" cy="25" r="5" fill="#FFF59D" stroke="#F9A825" stroke-width="1.5"/>
  <rect x="22" y="8" width="12" height="12" rx="2" fill="#B0BEC5" stroke="#546E7A" stroke-width="2"/>
  <circle cx="22" cy="36" r="2" fill="#E3F2FD"/>
  <circle cx="34" cy="36" r="2" fill="#E3F2FD"/>
  <circle cx="22" cy="44" r="2" fill="#E3F2FD"/>
  <circle cx="34" cy="44" r="2" fill="#E3F2FD"/>
  <!-- 미소 -->
  <path d="M24 26 Q28 29 32 26" fill="none" stroke="#F57F17" stroke-width="1.5"/>
</svg>"""

PEASHOOTER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="60" viewBox="0 0 56 60">
  <ellipse cx="24" cy="56" rx="14" ry="3" fill="#000000" opacity="0.18"/>
  <!-- 쿠키 몸 -->
  <circle cx="24" cy="30" r="16" fill="#D4A574" stroke="#8D6E63" stroke-width="2.5"/>
  <circle cx="18" cy="24" r="2.2" fill="#5D4037"/>
  <circle cx="28" cy="22" r="2" fill="#5D4037"/>
  <circle cx="22" cy="32" r="2" fill="#5D4037"/>
  <circle cx="30" cy="34" r="1.8" fill="#5D4037"/>
  <!-- 대포 입 -->
  <rect x="36" y="24" width="16" height="12" rx="4" fill="#A1887F" stroke="#5D4037" stroke-width="2"/>
  <ellipse cx="52" cy="30" rx="3" ry="5" fill="#5D4037"/>
  <!-- 눈 -->
  <circle cx="20" cy="26" r="3" fill="#FFFFFF"/>
  <circle cx="20" cy="26" r="1.5" fill="#222"/>
  <path d="M16 36 Q24 40 30 34" fill="none" stroke="#5D4037" stroke-width="2"/>
</svg>"""

WALNUT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="60" viewBox="0 0 56 60">
  <ellipse cx="28" cy="56" rx="16" ry="3" fill="#000000" opacity="0.22"/>
  <rect x="8" y="14" width="40" height="40" rx="6" fill="#5D4037" stroke="#3E2723" stroke-width="3"/>
  <rect x="12" y="18" width="32" height="32" rx="4" fill="#6D4C41"/>
  <!-- 초코 칩 -->
  <circle cx="20" cy="28" r="3" fill="#3E2723"/>
  <circle cx="34" cy="26" r="2.5" fill="#3E2723"/>
  <circle cx="28" cy="38" r="3.2" fill="#3E2723"/>
  <circle cx="18" cy="40" r="2" fill="#3E2723"/>
  <circle cx="36" cy="40" r="2.2" fill="#3E2723"/>
  <!-- 눈 -->
  <circle cx="22" cy="30" r="3.2" fill="#FFFFFF"/>
  <circle cx="34" cy="30" r="3.2" fill="#FFFFFF"/>
  <circle cx="22" cy="31" r="1.5" fill="#222"/>
  <circle cx="34" cy="31" r="1.5" fill="#222"/>
  <path d="M22 42 Q28 46 34 42" fill="none" stroke="#FFCC80" stroke-width="2"/>
</svg>"""

CHERRY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="60" viewBox="0 0 56 60">
  <ellipse cx="28" cy="56" rx="14" ry="3" fill="#000000" opacity="0.18"/>
  <!-- 우유 팩 -->
  <rect x="14" y="18" width="28" height="36" rx="4" fill="#FAFAFA" stroke="#90A4AE" stroke-width="2.5"/>
  <rect x="14" y="18" width="28" height="10" fill="#42A5F5" stroke="#1565C0" stroke-width="2"/>
  <rect x="24" y="10" width="8" height="10" rx="2" fill="#90A4AE" stroke="#546E7A" stroke-width="1.5"/>
  <text x="28" y="40" text-anchor="middle" font-family="Arial" font-size="10" font-weight="bold" fill="#1565C0">MILK</text>
  <circle cx="22" cy="48" r="2" fill="#E53935"/>
  <circle cx="34" cy="48" r="2" fill="#E53935"/>
  <!-- 도화선 느낌 -->
  <path d="M28 10 Q34 2 40 6" fill="none" stroke="#FF7043" stroke-width="2"/>
  <circle cx="40" cy="5" r="2.5" fill="#FFD54F"/>
</svg>"""

PLANT_BOOM_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="56" height="60" viewBox="0 0 56 60">
  <polygon points="{_star_pts(28, 32, 22, 9, 10)}" fill="#FFCC80" stroke="#E65100" stroke-width="1"/>
  <circle cx="28" cy="32" r="7" fill="#FFF8E1"/>
  <circle cx="24" cy="28" r="2" fill="#5D4037"/>
  <circle cx="32" cy="30" r="1.5" fill="#5D4037"/>
</svg>"""

# -------- 빗자루 --------
MOWER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="40" viewBox="0 0 56 40">
  <ellipse cx="28" cy="36" rx="18" ry="3" fill="#000000" opacity="0.2"/>
  <!-- 자루 -->
  <rect x="4" y="16" width="28" height="6" rx="2" fill="#8D6E63" stroke="#5D4037" stroke-width="1.5"/>
  <!-- 빗자루 머리 -->
  <polygon points="30,10 52,14 52,28 30,30" fill="#FFB74D" stroke="#EF6C00" stroke-width="2"/>
  <line x1="34" y1="14" x2="34" y2="28" stroke="#EF6C00" stroke-width="1"/>
  <line x1="40" y1="13" x2="40" y2="28" stroke="#EF6C00" stroke-width="1"/>
  <line x1="46" y1="14" x2="46" y2="28" stroke="#EF6C00" stroke-width="1"/>
  <circle cx="10" cy="19" r="3" fill="#FFD54F"/>
</svg>"""

# -------- 설탕 (반짝 알갱이) --------
SUN_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <polygon points="{_star_pts(24, 24, 22, 10, 8)}" fill="#FFF9C4" opacity="0.95"/>
  <circle cx="24" cy="24" r="12" fill="#FFFFFF" stroke="#FFD54F" stroke-width="2.5"/>
  <circle cx="20" cy="20" r="3" fill="#FFFDE7"/>
  <text x="24" y="29" text-anchor="middle" font-family="Arial" font-size="12" font-weight="bold" fill="#F9A825">S</text>
</svg>"""

# -------- 메뉴판 (4칸: 설탕기계15 / 쿠키캐논25 / 초코벽20 / 밀크폭탄60) --------
# 폭 160, 버튼 40×4. rotationCenterX=80. pos(-65,150) → 버튼 중심 scratch x: -125/-85/-45/-5
def _seed_btn(x, fill, icon_svg, price):
    return (f'<rect x="{x}" y="4" width="40" height="52" rx="8" fill="{fill}" stroke="#FFF8E1" stroke-width="2"/>'
            + icon_svg.format(cx=x+20)
            + f'<text x="{x+20}" y="52" text-anchor="middle" font-family="Arial" font-size="11" '
              f'font-weight="bold" fill="#FFF59D">{price}</text>')
# 설탕통(생산) 아이콘 — 수집용 설탕 보석과 구분되게 병 모양
_ic_sun  = ('<ellipse cx="{cx}" cy="26" rx="9" ry="10" fill="#E1F5FE" stroke="#0277BD" stroke-width="1.6"/>'
            '<rect x="{cx}" y="12" width="12" height="6" rx="2" fill="#F48FB1" transform="translate(-6,0)"/>'
            '<ellipse cx="{cx}" cy="12" rx="6" ry="2" fill="#F8BBD0"/>'
            '<circle cx="{cx}" cy="24" r="2" fill="#FFF59D"/>'
            '<circle cx="{cx}" cy="28" r="1.5" fill="#CE93D8" transform="translate(3,0)"/>')
# 쿠키캐논 — 매끄러운 쿠키 + 작은 대포
_ic_pea  = ('<circle cx="{cx}" cy="22" r="9" fill="#E0A86E" stroke="#8D6E63" stroke-width="1.6"/>'
            '<circle cx="{cx}" cy="18" r="1.4" fill="#6D4C41"/>'
            '<circle cx="{cx}" cy="24" r="1.2" fill="#6D4C41" transform="translate(-3,0)"/>'
            '<rect x="{cx}" y="18" width="9" height="5" rx="2" fill="#5D4037" transform="translate(5,0)"/>')
_ic_nut  = ('<rect x="{cx}" y="12" width="18" height="20" rx="4" fill="#5D4037" stroke="#3E2723" stroke-width="1.8" transform="translate(-9,0)"/>'
            '<circle cx="{cx}" cy="20" r="2" fill="#3E2723"/>'
            '<circle cx="{cx}" cy="26" r="1.5" fill="#3E2723" transform="translate(3,0)"/>')
_ic_cher = ('<circle cx="{cx}" cy="24" r="11" fill="#FAFAFA" stroke="#37474F" stroke-width="1.8"/>'
            '<path d="M{cx} 14 Q{cx} 10 {cx} 8" fill="none" stroke="#FF7043" stroke-width="2" transform="translate(4,0)"/>'
            '<circle cx="{cx}" cy="7" r="2.5" fill="#FFD54F" transform="translate(6,0)"/>'
            '<rect x="{cx}" y="16" width="14" height="4" fill="#1565C0" transform="translate(-7,0)"/>'
            '<circle cx="{cx}" cy="26" r="2" fill="#222" transform="translate(-3,0)"/>'
            '<circle cx="{cx}" cy="26" r="2" fill="#222" transform="translate(3,0)"/>')
def _cher_icon(cx):
    return _ic_cher.format(cx=cx)
PALETTE_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="60" viewBox="0 0 160 60">
  <rect x="0" y="0" width="160" height="60" rx="10" fill="#4E342E" opacity="0.95" stroke="#FFD54F" stroke-width="2.5"/>
  {_seed_btn(0,   "#0288D1", _ic_sun,  "15")}
  {_seed_btn(40,  "#8D6E63", _ic_pea,  "25")}
  {_seed_btn(80,  "#3E2723", _ic_nut,  "20")}
  {_seed_btn(120, "#455A64", "", "50")}
  {_cher_icon(140)}
</svg>"""

# -------- 설치커서: 반투명 칸 하이라이트(초록 기본, color 이펙트로 빨강 전환) --------
CURSOR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="44" height="56" viewBox="0 0 44 56">
  <rect x="3" y="3" width="38" height="50" rx="6" fill="#00E676" opacity="0.35" stroke="#00C853" stroke-width="3"/>
</svg>"""

# -------- 웨이브 알림 배너 --------
WAVEFLAG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="300" height="80" viewBox="0 0 300 80">
  <rect x="4" y="4" width="292" height="72" rx="16" fill="#C62828" opacity="0.94" stroke="#FFD54F" stroke-width="5"/>
  <rect x="12" y="12" width="276" height="56" rx="12" fill="none" stroke="#FFECB3" stroke-width="2" opacity="0.7"/>
  <text x="150" y="52" text-anchor="middle" fill="#FFFDE7" font-family="Arial" font-size="30" font-weight="bold">🐜 개미 습격!</text>
</svg>"""

# -------- 게임오버 배너 --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="66" text-anchor="middle" fill="#E53935" font-family="Arial" font-size="44" font-weight="bold">GAME OVER</text>
  <text x="180" y="102" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="18">쿠키 창고가 털렸어요!</text>
  <text x="180" y="134" text-anchor="middle" fill="#FFCDD2" font-family="Arial" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# -------- 숫자 코스튬: 흰 0~9(데미지) + 금 0~9(설탕) — say 미사용 --------
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
# ----- 5.1 튜닝 50 (개조 손잡이) -----
# 경제/자원 9 — 초반 여유 밸런스 (시작 설탕로 쿠키알 여러 레인 커버 가능)
V_SUN0    = "varSun01"        # 기본설탕 100
V_SKYSUN  = "varSkySun02"     # 하늘설탕량 25
V_SUNPROD = "varSunProd03"    # 설탕기계생산량 25
V_SUNINT  = "varSunInt04"     # 설탕기계간격 6
V_SKYINT  = "varSkyInt05"     # 하늘설탕간격 8
V_AUTOPICK= "varAutoPick06"   # 자동수확대기 6
V_KILLSUN = "varKillSun07"    # 처치설탕 5
V_WAVESUN = "varWaveSun08"    # 웨이브클리어설탕 20
V_LIFEMAX = "varLifeMax09"    # 시작목숨 3
# 웨이브/스폰 10 — 후반 급가속 (밀크폭탄 연타 유도)
V_BASEZ   = "varBaseZ10"      # 기본개미수 5
V_ZINC    = "varZInc11"       # 웨이브당개미증가 3
V_SPGAP   = "varSpawnGap12"   # 개미간격 2.6
V_HPINC   = "varHPinc13"      # 웨이브체력증가 5  (실제체력 = 종류 + (웨이브-1)×이 값)
V_SPINC   = "varSPinc14"      # 웨이브속도증가 0.12
V_FIRSTW  = "varFirstWait15"  # 첫웨이브대기 9
V_WAVEW   = "varWaveWait16"   # 웨이브사이대기 3
V_UNCONE  = "varUnlockCone17" # 헬멧해금웨이브 2
V_UNFAST  = "varUnlockFast18" # 빠른개미해금웨이브 3
V_REACH   = "varReach19"      # 도달반경 15
# 장치 15
V_SFCOST  = "varSfCost20"     # 설탕기계_가격 15
V_SFHP    = "varSfHP21"       # 설탕기계_체력 5
V_PEACOST = "varPeaCost22"    # 쿠키캐논_가격 25
V_PEAHP   = "varPeaHP23"      # 쿠키캐논_체력 5
V_PEADMG  = "varPeaDmg24"     # 쿠키캐논_공격력 1
V_PEAGAP  = "varPeaGap25"     # 쿠키캐논_간격 1.3
V_PEASPD  = "varPeaSpd26"     # 쿠키속도 10
V_PEAR    = "varPeaR27"       # 쿠키반경 18
V_NUTCOST = "varNutCost28"    # 초코벽_가격 20
V_NUTHP   = "varNutHP29"      # 초코벽_체력 30
V_CHCOST  = "varChCost30"     # 밀크폭탄_가격 50  (후반 연타 유도 — 가격은 조금 낮춤)
V_CHHP    = "varChHP31"       # 밀크폭탄_체력 1
V_CHDMG   = "varChDmg32"      # 밀크폭탄_데미지 28
V_CHR     = "varChR33"        # 밀크폭탄_반경 160
V_CHFUSE  = "varChFuse34"     # 밀크폭탄_퓨즈 0.7
# 개미 7
V_Z1HP    = "varZ1HP35"       # 기본개미_체력 8
V_Z1SP    = "varZ1SP36"       # 기본개미_속도 0.85
V_BITE    = "varBite37"       # 개미갉기력 0.45
V_Z2HP    = "varZ2HP38"       # 헬멧개미_체력 18
V_Z2SP    = "varZ2SP39"       # 헬멧개미_속도 0.75
V_Z3HP    = "varZ3HP41"       # 빠른개미_체력 6
V_Z3SP    = "varZ3SP42"       # 빠른개미_속도 1.5
# 빗자루/그리드 9
V_MOWSPD  = "varMowSpd44"     # 빗자루속도 12
V_GX      = "varGx45"         # 격자시작X -160
V_GXSTEP  = "varGxStep46"     # 격자간격X 40
V_LY      = "varLy47"         # 레인시작Y 110
V_LYSTEP  = "varLyStep48"     # 레인간격Y 55
V_COLS    = "varCols49"       # 열개수 9
V_ROWS    = "varRows50"       # 레인개수 5
V_ZSPAWNX = "varZSpawnX43"    # 개미생성X 250
V_REACHH  = "varReachHouse40" # 개미도달X -190
V_BGMVOL  = "varBgmVol94"     # 브금볼륨 55

# ----- 5.2 진행/내부 상태 39 -----
V_STATE   = "varState51"      # 게임상태 1
V_WAVE    = "varWave52"       # 웨이브 1
V_SCORE   = "varScore53"      # 점수 0
V_SUNCUR  = "varSunCur54"     # 설탕 50
V_LIFE    = "varLife55"       # 목숨 3
V_ALIVE   = "varAlive56"      # 적수 0
V_SPAWNN  = "varSpawnN57"     # 스폰카운트 0
V_SEL     = "varSel58"        # 선택장치 0
V_UNCONEF = "varUnCone59"     # 헬멧해금 0
V_UNFASTF = "varUnFast60"     # 빠른해금 0
V_SPLANE  = "varSpawnLane61"  # 생성레인 1
V_SPTYPE  = "varSpawnT62"     # 생성타입 1
V_PLACEX  = "varPlaceX63"     # 설치X 0
V_PLACEY  = "varPlaceY64"     # 설치Y 0
V_PLACET  = "varPlaceT65"     # 설치타입 0
V_PLACEL  = "varPlaceLane66"  # 설치레인 1
V_PLACEC  = "varPlaceCol67"   # 설치열 1
V_AIMLANE = "varAimLane68"    # 조준레인 0
V_AIMTX   = "varAimTX69"      # 조준탑X 0
V_AIMOK   = "varAimOK70"      # 조준적있음 0
V_FIREX   = "varFireX71"      # 발사X 0
V_FIREY   = "varFireY72"      # 발사Y 0
V_FIRELN  = "varFireLane73"   # 발사레인 1
V_BOOMX   = "varBoomX74"      # 폭발X 0
V_BOOMY   = "varBoomY75"      # 폭발Y 0
V_BOOMD   = "varBoomD76"      # 폭발데미지 0
V_BOOMR   = "varBoomR77"      # 폭발반경 0
V_SUNKIND = "varSunKind78"    # 설탕종류 0
V_SUNX    = "varSunX79"       # 설탕X 0
V_SUNY    = "varSunY80"       # 설탕Y 0
V_MOWLANE = "varMowLane81"    # 작동레인 0
V_DMGVAL  = "varDmgVal82"     # 데미지표시값 0
V_DMGX    = "varDmgX83"       # 데미지표시x 0
V_DMGY    = "varDmgY84"       # 데미지표시y 0
V_DMGKIND = "varDmgKind85"    # 팝업종류 0
V_DMGDIG  = "varDmgDigit86"   # 데미지숫자 0
V_DMGOFF  = "varDmgOff87"     # 데미지오프셋 0
V_DMGLEN  = "varDmgLen88"     # 데미지글자수 0
V_DMGPOS  = "varDmgPos89"     # 데미지자리 0
# 빌더 헬퍼(플랜 허용): 리스트 빌드 카운터 + 가격 캐시 + 입력 분리
V_I       = "varI90"          # i (리스트 빌드용 임시)
V_CURPRICE= "varCurPrice91"   # 현재가격 (선택장치 가격 캐시)
V_PLANTLOCK = "varPlantLock92"  # 설치잠금 — 설탕 클릭 수확 시 1, 마우스 업 설치 차단
V_PREV_MD   = "varPrevMd93"     # 이전마우스 — 마우스 다운 엣지/업 감지용 (0/1)

# ----- 5.3 리스트 -----
L_COLX  = "listColX"    # 열X
L_LANEY = "listLaneY"   # 레인Y
L_CELL  = "listCell"    # 격자점유
L_MOWER = "listMower"   # 빗자루사용

# ----- 5.4 클론-로컬 -----
V_Z_ISC   = "varZIsClone"
V_Z_TYPE  = "varZType"
V_Z_HP    = "varZHP"
V_Z_SPD   = "varZSpd"
V_Z_LANE  = "varZLane"
V_Z_ANIM  = "varZAnim"       # 개미 보행 프레임 0/1
V_PB_ISC  = "varPeaIsClone"
V_PB_LANE = "varPeaLane"
V_PB_ANIM = "varPeaAnim"     # 쿠키알 회전 프레임
V_PL_ISC  = "varPlIsClone"
V_PL_TYPE = "varPlType"
V_PL_HP   = "varPlHP"
V_PL_LANE = "varPlLane"
V_PL_COL  = "varPlCol"
V_PL_CD   = "varPlCD"
V_PL_FUSE = "varPlFuse"
V_PL_ANIM = "varPlAnim"      # 장치 idle 프레임 0/1
V_MO_ISC  = "varMoIsClone"
V_MO_LANE = "varMoLane"
V_MO_USED = "varMoUsed"
V_MO_RUN  = "varMoRun"
V_MO_ANIM = "varMoAnim"
V_SU_ISC  = "varSuIsClone"
V_SU_KIND = "varSuKind"
V_SU_LIFE = "varSuLife"
V_SU_ANIM = "varSuAnim"
V_POP_ISC = "varPopIsClone"
V_HS_ANIM = "varHsAnim"      # 창고 idle

# ----- 5.5 메시지 12 -----
BR_START = "brStart01"   # 게임시작
BR_WAVE  = "brWave02"    # 웨이브시작
BR_SPAWN = "brSpawn03"   # 개미생성
BR_LANE  = "brLane04"    # 개미레인확인
BR_FIRE  = "brFire05"    # 쿠키발사
BR_HIT   = "brHit06"     # 타격
BR_PLACE = "brPlace07"   # 장치설치
BR_SUN   = "brSun08"     # 설탕생성
BR_DMG   = "brDmg09"     # 데미지표시
BR_MOW   = "brMow10"     # 빗자루작동
BR_HOUSE = "brHouse11"   # 창고피격
BR_OVER  = "brOver12"    # 게임오버

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

def b_not(bs, c):
    nb = gen(); bs[nb] = mk("operator_not", inputs={"OPERAND": [2, c]})
    bs[c]["parent"] = nb
    return nb

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

def b_movesteps(bs, steps_value):
    bid = gen()
    if isinstance(steps_value, str) and steps_value in bs:
        bs[bid] = mk("motion_movesteps", inputs={"STEPS": slot(steps_value)})
        bs[steps_value]["parent"] = bid
    else:
        bs[bid] = mk("motion_movesteps", inputs={"STEPS": num(steps_value)})
    return bid

def b_changex(bs, val):
    bid = gen()
    if isinstance(val, str) and val in bs:
        bs[bid] = mk("motion_changexby", inputs={"DX": slot(val)}); bs[val]["parent"] = bid
    else:
        bs[bid] = mk("motion_changexby", inputs={"DX": num(val)})
    return bid

def b_changey(bs, val):
    bid = gen()
    if isinstance(val, str) and val in bs:
        bs[bid] = mk("motion_changeyby", inputs={"DY": slot(val)}); bs[val]["parent"] = bid
    else:
        bs[bid] = mk("motion_changeyby", inputs={"DY": num(val)})
    return bid

def b_gotoxy(bs, xval, yval):
    bid = gen()
    def _slot(v): return slot(v) if (isinstance(v, str) and v in bs) else num(v)
    bs[bid] = mk("motion_gotoxy", inputs={"X": _slot(xval), "Y": _slot(yval)})
    if isinstance(xval, str) and xval in bs: bs[xval]["parent"] = bid
    if isinstance(yval, str) and yval in bs: bs[yval]["parent"] = bid
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

def b_setsize(bs, size):
    bid = gen(); bs[bid] = mk("looks_setsizeto", inputs={"SIZE": num(size)}); return bid
def b_changesize(bs, ch):
    bid = gen(); bs[bid] = mk("looks_changesizeby", inputs={"CHANGE": num(ch)}); return bid
def b_seteffect(bs, effect, val):
    bid = gen(); bs[bid] = mk("looks_seteffectto",
        inputs={"VALUE": num(val)}, fields={"EFFECT": [effect, None]}); return bid
def b_changeeffect(bs, effect, ch):
    bid = gen(); bs[bid] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(ch)}, fields={"EFFECT": [effect, None]}); return bid
def b_show(bs):
    bid = gen(); bs[bid] = mk("looks_show"); return bid
def b_hide(bs):
    bid = gen(); bs[bid] = mk("looks_hide"); return bid
def b_front(bs):
    bid = gen(); bs[bid] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]}); return bid
def b_rotstyle(bs):
    bid = gen(); bs[bid] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]}); return bid
def b_pointdir(bs, d):
    bid = gen(); bs[bid] = mk("motion_pointindirection", inputs={"DIRECTION": num(d)}); return bid
def b_delete_clone(bs):
    bid = gen(); bs[bid] = mk("control_delete_this_clone"); return bid
def b_create_clone(bs):
    m = gen(); bs[m] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    c = gen(); bs[c] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, m]})
    bs[m]["parent"] = c
    return c

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

def b_length_of_list(bs, listname, listid):
    bid = gen(); bs[bid] = mk("data_lengthoflist", fields={"LIST": [listname, listid]})
    return bid

def b_delete_all(bs, listname, listid):
    bid = gen(); bs[bid] = mk("data_deletealloflist", fields={"LIST": [listname, listid]})
    return bid

def b_add_expr(bs, listname, listid, value):
    bid = gen()
    ins = {"ITEM": slot(value) if (isinstance(value, str) and value in bs) else num(value)}
    bs[bid] = mk("data_addtolist", inputs=ins, fields={"LIST": [listname, listid]})
    if isinstance(value, str) and value in bs: bs[value]["parent"] = bid
    return bid

def b_replace_item(bs, listname, listid, idx, value):
    bid = gen()
    ins = {}
    ins["INDEX"] = slot(idx) if (isinstance(idx, str) and idx in bs) else num(idx)
    ins["ITEM"] = slot(value) if (isinstance(value, str) and value in bs) else num(value)
    bs[bid] = mk("data_replaceitemoflist", inputs=ins, fields={"LIST": [listname, listid]})
    if isinstance(idx, str) and idx in bs: bs[idx]["parent"] = bid
    if isinstance(value, str) and value in bs: bs[value]["parent"] = bid
    return bid

def b_xpos(bs):
    bid = gen(); bs[bid] = mk("motion_xposition"); return bid
def b_ypos(bs):
    bid = gen(); bs[bid] = mk("motion_yposition"); return bid
def b_mousex(bs):
    bid = gen(); bs[bid] = mk("sensing_mousex"); return bid
def b_mousey(bs):
    bid = gen(); bs[bid] = mk("sensing_mousey"); return bid
def b_mousedown(bs):
    bid = gen(); bs[bid] = mk("sensing_mousedown"); return bid

def b_round(bs, operand):
    bid = gen(); bs[bid] = mk("operator_round", inputs={"NUM": slot(operand)})
    bs[operand]["parent"] = bid
    return bid

def b_mathop(bs, name, operand):
    bid = gen(); bs[bid] = mk("operator_mathop",
        inputs={"NUM": slot(operand)}, fields={"OPERATOR": [name, None]})
    bs[operand]["parent"] = bid
    return bid

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

    # ===== (A) 깃발 클릭 → 튜닝 50 + 진행 39 초기화 + 그리드 리스트 빌드 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val)
        seq.append((sid, bs[sid]))
    def add_set_ref(name, vid, ref_name, ref_vid):
        r = vrep(ref_name, ref_vid)
        sid = b_setvar(bs, name, vid, r)
        seq.append((sid, bs[sid]))

    # ── 튜닝 손잡이 50 ──
    # 밸런스 노트(2026-07-27): 쿠키 난사 약화 + 웨이브 스케일 강화.
    # 실제 체력/속도 = 종류값 + (웨이브-1)×웨이브체력/속도증가 → 뒤로 갈수록 개미가 버팀.
    # 경제/자원
    add_set("기본설탕", V_SUN0, 100); add_set("하늘설탕량", V_SKYSUN, 25)
    add_set("설탕기계생산량", V_SUNPROD, 25); add_set("설탕기계간격", V_SUNINT, 6)
    add_set("하늘설탕간격", V_SKYINT, 8); add_set("자동수확대기", V_AUTOPICK, 6)
    add_set("처치설탕", V_KILLSUN, 5); add_set("웨이브클리어설탕", V_WAVESUN, 20)
    add_set("시작목숨", V_LIFEMAX, 3)
    # 웨이브/스폰 — 후반 급가속 (쿠키 줄 난사만으론 막기 어렵게)
    add_set("기본개미수", V_BASEZ, 5); add_set("웨이브당개미증가", V_ZINC, 3)
    add_set("개미간격", V_SPGAP, 2.6); add_set("웨이브체력증가", V_HPINC, 5)
    add_set("웨이브속도증가", V_SPINC, 0.12); add_set("첫웨이브대기", V_FIRSTW, 9)
    add_set("웨이브사이대기", V_WAVEW, 3); add_set("헬멧해금웨이브", V_UNCONE, 2)
    add_set("빠른개미해금웨이브", V_UNFAST, 3); add_set("도달반경", V_REACH, 15)
    # 장치 — 캐논은 유지, 밀크는 후반 필수 연타 수단
    add_set("설탕기계_가격", V_SFCOST, 15); add_set("설탕기계_체력", V_SFHP, 5)
    add_set("쿠키캐논_가격", V_PEACOST, 25); add_set("쿠키캐논_체력", V_PEAHP, 5)
    add_set("쿠키캐논_공격력", V_PEADMG, 1); add_set("쿠키캐논_간격", V_PEAGAP, 1.3)
    add_set("쿠키속도", V_PEASPD, 10); add_set("쿠키반경", V_PEAR, 18)
    add_set("초코벽_가격", V_NUTCOST, 20); add_set("초코벽_체력", V_NUTHP, 30)
    add_set("밀크폭탄_가격", V_CHCOST, 50); add_set("밀크폭탄_체력", V_CHHP, 1)
    add_set("밀크폭탄_데미지", V_CHDMG, 28); add_set("밀크폭탄_반경", V_CHR, 160)
    add_set("밀크폭탄_퓨즈", V_CHFUSE, 0.7)
    # 개미 — 체력·속도·갉기 강화, 웨이브마다 체력 +5
    add_set("기본개미_체력", V_Z1HP, 8); add_set("기본개미_속도", V_Z1SP, 0.85)
    add_set("개미갉기력", V_BITE, 0.45)
    add_set("헬멧개미_체력", V_Z2HP, 18); add_set("헬멧개미_속도", V_Z2SP, 0.75)
    add_set("빠른개미_체력", V_Z3HP, 6); add_set("빠른개미_속도", V_Z3SP, 1.5)
    # 빗자루/그리드
    add_set("빗자루속도", V_MOWSPD, 12)
    add_set("격자시작X", V_GX, -160); add_set("격자간격X", V_GXSTEP, 40)
    add_set("레인시작Y", V_LY, 110); add_set("레인간격Y", V_LYSTEP, 55)
    add_set("열개수", V_COLS, 9); add_set("레인개수", V_ROWS, 5)
    add_set("개미생성X", V_ZSPAWNX, 250); add_set("개미도달X", V_REACHH, -190)
    add_set("브금볼륨", V_BGMVOL, 55)

    # ── 진행 상태 39 (설탕=기본설탕, 목숨=시작목숨) ──
    add_set("게임상태", V_STATE, 1); add_set("웨이브", V_WAVE, 1); add_set("점수", V_SCORE, 0)
    add_set_ref("설탕", V_SUNCUR, "기본설탕", V_SUN0)
    add_set_ref("목숨", V_LIFE, "시작목숨", V_LIFEMAX)
    add_set("적수", V_ALIVE, 0); add_set("스폰카운트", V_SPAWNN, 0); add_set("선택장치", V_SEL, 0)
    add_set("헬멧해금", V_UNCONEF, 0); add_set("빠른해금", V_UNFASTF, 0)
    add_set("생성레인", V_SPLANE, 1); add_set("생성타입", V_SPTYPE, 1)
    add_set("설치X", V_PLACEX, 0); add_set("설치Y", V_PLACEY, 0); add_set("설치타입", V_PLACET, 0)
    add_set("설치레인", V_PLACEL, 1); add_set("설치열", V_PLACEC, 1)
    add_set("조준레인", V_AIMLANE, 0); add_set("조준탑X", V_AIMTX, 0); add_set("조준적있음", V_AIMOK, 0)
    add_set("발사X", V_FIREX, 0); add_set("발사Y", V_FIREY, 0); add_set("발사레인", V_FIRELN, 1)
    add_set("폭발X", V_BOOMX, 0); add_set("폭발Y", V_BOOMY, 0)
    add_set("폭발데미지", V_BOOMD, 0); add_set("폭발반경", V_BOOMR, 0)
    add_set("설탕종류", V_SUNKIND, 0); add_set("설탕X", V_SUNX, 0); add_set("설탕Y", V_SUNY, 0)
    add_set("작동레인", V_MOWLANE, 0)
    add_set("데미지표시값", V_DMGVAL, 0); add_set("데미지표시x", V_DMGX, 0); add_set("데미지표시y", V_DMGY, 0)
    add_set("팝업종류", V_DMGKIND, 0); add_set("데미지숫자", V_DMGDIG, 0); add_set("데미지오프셋", V_DMGOFF, 0)
    add_set("데미지글자수", V_DMGLEN, 0); add_set("데미지자리", V_DMGPOS, 0)
    add_set("현재가격", V_CURPRICE, 0)
    add_set("설치잠금", V_PLANTLOCK, 0); add_set("이전마우스", V_PREV_MD, 0)

    # ── 그리드 리스트 빌드(손잡이에서 계산) ──
    # 열X: repeat 열개수 → add (격자시작X + (i-1)*격자간격X)
    dclx = b_delete_all(bs, "열X", L_COLX); seq.append((dclx, bs[dclx]))
    seti1 = b_setvar(bs, "i", V_I, 1); seq.append((seti1, bs[seti1]))
    im1 = op("operator_subtract", vrep("i", V_I), 1)
    xexpr = op("operator_add", vrep("격자시작X", V_GX), op("operator_multiply", im1, vrep("격자간격X", V_GXSTEP)))
    addx = b_add_expr(bs, "열X", L_COLX, xexpr)
    inci = b_changevar(bs, "i", V_I, 1)
    chain([(addx, bs[addx]), (inci, bs[inci])])
    repx = b_repeat(bs, vrep("열개수", V_COLS), addx); seq.append((repx, bs[repx]))
    # 레인Y: repeat 레인개수 → add (레인시작Y - (i-1)*레인간격Y)
    dcly = b_delete_all(bs, "레인Y", L_LANEY); seq.append((dcly, bs[dcly]))
    seti2 = b_setvar(bs, "i", V_I, 1); seq.append((seti2, bs[seti2]))
    im1b = op("operator_subtract", vrep("i", V_I), 1)
    yexpr = op("operator_subtract", vrep("레인시작Y", V_LY), op("operator_multiply", im1b, vrep("레인간격Y", V_LYSTEP)))
    addy = b_add_expr(bs, "레인Y", L_LANEY, yexpr)
    inci2 = b_changevar(bs, "i", V_I, 1)
    chain([(addy, bs[addy]), (inci2, bs[inci2])])
    repy = b_repeat(bs, vrep("레인개수", V_ROWS), addy); seq.append((repy, bs[repy]))
    # 격자점유: repeat (열개수*레인개수) → add 0
    dcell = b_delete_all(bs, "격자점유", L_CELL); seq.append((dcell, bs[dcell]))
    cellcount = op("operator_multiply", vrep("열개수", V_COLS), vrep("레인개수", V_ROWS))
    add0 = b_add_expr(bs, "격자점유", L_CELL, 0)
    repcell = b_repeat(bs, cellcount, add0); seq.append((repcell, bs[repcell]))
    # 빗자루사용: repeat 레인개수 → add 0
    dmow = b_delete_all(bs, "빗자루사용", L_MOWER); seq.append((dmow, bs[dmow]))
    add0m = b_add_expr(bs, "빗자루사용", L_MOWER, 0)
    repmow = b_repeat(bs, vrep("레인개수", V_ROWS), add0m); seq.append((repmow, bs[repmow]))

    w1 = b_wait(bs, 0.3); seq.append((w1, bs[w1]))
    bc_start = b_broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # ===== (B) 웨이브 매니저 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=360, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    w_first = b_wait_var(bs, V_FIRSTW, "첫웨이브대기")
    # 타입 결정: 웨이브<=1 →1 / 빠른해금=0 →1+(스폰카운트 mod 2) / else →1+random(0,2)
    set_t1 = b_setvar(bs, "생성타입", V_SPTYPE, 1)
    mod2 = op("operator_mod", vrep("스폰카운트", V_SPAWNN), 2)
    t_alt = op("operator_add", 1, mod2)
    set_talt = b_setvar(bs, "생성타입", V_SPTYPE, t_alt)
    rnd02 = gen(); bs[rnd02] = mk("operator_random", inputs={"FROM": num(0), "TO": num(2)})
    t_mix = op("operator_add", 1, rnd02)
    set_tmix = b_setvar(bs, "생성타입", V_SPTYPE, t_mix)
    fast0 = cmp_op("operator_equals", vrep("빠른해금", V_UNFASTF), 0)
    if_fast = b_ifelse(bs, fast0, set_talt, set_tmix)
    wave_le1 = cmp_op("operator_lt", vrep("웨이브", V_WAVE), 2)   # 웨이브<=1
    if_type = b_ifelse(bs, wave_le1, set_t1, if_fast)
    # 레인 무작위 (pick random 1 to 레인개수)
    rlane_to = vrep("레인개수", V_ROWS)
    rlane = gen(); bs[rlane] = mk("operator_random", inputs={"FROM": num(1), "TO": slot(rlane_to)})
    bs[rlane_to]["parent"] = rlane
    set_lane = b_setvar(bs, "생성레인", V_SPLANE, rlane)
    inc_spn = b_changevar(bs, "스폰카운트", V_SPAWNN, 1)
    inc_alive = b_changevar(bs, "적수", V_ALIVE, 1)
    bc_spawn = b_broadcast(bs, "개미생성", BR_SPAWN)
    w_gap = b_wait_var(bs, V_SPGAP, "개미간격")
    chain([(set_lane, bs[set_lane]), (if_type, bs[if_type]), (inc_spn, bs[inc_spn]),
           (inc_alive, bs[inc_alive]), (bc_spawn, bs[bc_spawn]), (w_gap, bs[w_gap])])
    # repeat (기본개미수 + (웨이브-1)*웨이브당개미증가)
    wm1 = op("operator_subtract", vrep("웨이브", V_WAVE), 1)
    extra = op("operator_multiply", wm1, vrep("웨이브당개미증가", V_ZINC))
    zcount = op("operator_add", vrep("기본개미수", V_BASEZ), extra)
    rep_spawn = b_repeat(bs, zcount, set_lane)
    # 웨이브 시작 + 클리어
    bc_wave = b_broadcast(bs, "웨이브시작", BR_WAVE)
    set_spn0 = b_setvar(bs, "스폰카운트", V_SPAWNN, 0)
    alive_le0 = cmp_op("operator_lt", vrep("적수", V_ALIVE), 1)   # 적수<=0
    wu_clear = b_waituntil(bs, alive_le0)
    # 클리어 보너스 (게임상태=1)
    add_sun = b_changevar(bs, "설탕", V_SUNCUR, vrep("웨이브클리어설탕", V_WAVESUN))
    inc_wave = b_changevar(bs, "웨이브", V_WAVE, 1)
    ge_cone = b_not(bs, cmp_op("operator_lt", vrep("웨이브", V_WAVE), vrep("헬멧해금웨이브", V_UNCONE)))
    set_uncone = b_setvar(bs, "헬멧해금", V_UNCONEF, 1)
    if_uncone = b_if(bs, ge_cone, set_uncone)
    ge_fast = b_not(bs, cmp_op("operator_lt", vrep("웨이브", V_WAVE), vrep("빠른개미해금웨이브", V_UNFAST)))
    set_unfast = b_setvar(bs, "빠른해금", V_UNFASTF, 1)
    if_unfast = b_if(bs, ge_fast, set_unfast)
    w_between = b_wait_var(bs, V_WAVEW, "웨이브사이대기")
    st1_clear = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    chain([(add_sun, bs[add_sun]), (inc_wave, bs[inc_wave]), (if_uncone, bs[if_uncone]),
           (if_unfast, bs[if_unfast]), (w_between, bs[w_between])])
    if_clear = b_if(bs, st1_clear, add_sun)
    chain([(bc_wave, bs[bc_wave]), (set_spn0, bs[set_spn0]), (rep_spawn, bs[rep_spawn]),
           (wu_clear, bs[wu_clear]), (if_clear, bs[if_clear])])
    st1_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_play = b_if(bs, st1_play, bc_wave)
    w_idle = b_wait(bs, 0.1)
    chain([(if_play, bs[if_play]), (w_idle, bs[w_idle])])
    fe_b = b_forever(bs, if_play)
    chain([(hb, bs[hb]), (w_first, bs[w_first]), (fe_b, bs[fe_b])])

    # ===== (C) 하늘 설탕 스포너 forever =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=360, y=460,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    w_sky = b_wait_var(bs, V_SKYINT, "하늘설탕간격")
    set_kind0 = b_setvar(bs, "설탕종류", V_SUNKIND, 0)
    rc_to = vrep("열개수", V_COLS)
    rcol = gen(); bs[rcol] = mk("operator_random", inputs={"FROM": num(1), "TO": slot(rc_to)})
    bs[rc_to]["parent"] = rcol
    sunx_item = b_item_of(bs, "열X", L_COLX, rcol)
    set_sunx = b_setvar(bs, "설탕X", V_SUNX, sunx_item)
    rl_to = vrep("레인개수", V_ROWS)
    rlan = gen(); bs[rlan] = mk("operator_random", inputs={"FROM": num(1), "TO": slot(rl_to)})
    bs[rl_to]["parent"] = rlan
    suny_item = b_item_of(bs, "레인Y", L_LANEY, rlan)
    set_suny = b_setvar(bs, "설탕Y", V_SUNY, suny_item)
    bc_sun = b_broadcast(bs, "설탕생성", BR_SUN)
    chain([(set_kind0, bs[set_kind0]), (set_sunx, bs[set_sunx]), (set_suny, bs[set_suny]),
           (bc_sun, bs[bc_sun])])
    st1_sky = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_sky = b_if(bs, st1_sky, set_kind0)
    chain([(w_sky, bs[w_sky]), (if_sky, bs[if_sky])])
    fe_c = b_forever(bs, w_sky)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # ===== (D) 웨이브 시작 연출 =====
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=700, y=20,
        fields={"BROADCAST_OPTION": ["웨이브시작", BR_WAVE]})
    sh_w, sp_w = b_sound(bs, 0, "wave")
    sh_g, sp_g = b_sound(bs, 0, "groan")
    chain([(hd, bs[hd]), (sh_w, bs[sh_w]), (sh_g, bs[sh_g])])

    # ===== (E) 게임오버 감시 forever =====
    he = gen(); bs[he] = mk("event_whenflagclicked", top=True, x=700, y=200)
    st_ready = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    wu_ready = b_waituntil(bs, st_ready)
    life_dead = cmp_op("operator_lt", vrep("목숨", V_LIFE), 1)
    st_pl = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_over = bool_op("operator_and", life_dead, st_pl)
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    bc_over = b_broadcast(bs, "게임오버", BR_OVER)
    chain([(set_st0, bs[set_st0]), (bc_over, bs[bc_over])])
    if_over = b_if(bs, c_over, set_st0)
    w_d = b_wait(bs, 0.1)
    chain([(if_over, bs[if_over]), (w_d, bs[w_d])])
    fe_e = b_forever(bs, if_over)
    chain([(he, bs[he]), (wu_ready, bs[wu_ready]), (fe_e, bs[fe_e])])

    # ===== (F) BGM: 병렬 깃발 스크립트 forever { play bgm until done } =====
    hbgm = gen(); bs[hbgm] = mk("event_whenflagclicked", top=True, x=700, y=520)
    bgmvol_r = vrep("브금볼륨", V_BGMVOL)
    setvol = gen(); bs[setvol] = mk("sound_setvolumeto", inputs={"VOLUME": slot(bgmvol_r)})
    bs[bgmvol_r]["parent"] = setvol
    bgm_menu = gen(); bs[bgm_menu] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["bgm", None]}, shadow=True)
    play_bgm = gen(); bs[play_bgm] = mk("sound_playuntildone",
        inputs={"SOUND_MENU": [1, bgm_menu]})
    bs[bgm_menu]["parent"] = play_bgm
    fe_bgm = b_forever(bs, play_bgm)
    chain([(hbgm, bs[hbgm]), (setvol, bs[setvol]), (fe_bgm, bs[fe_bgm])])

    # ── 가이드 투어 코멘트 ──
    add_comment(bs, comments, h,
        "🛠️ 개조 손잡이: 여기 숫자만 바꾸면 게임이 달라져요!\n"
        "설탕·가격·개미·장치 능력치가 전부 여기 한글 변수로 모여 있어요. "
        "예: 기본설탕 100→300 으로 바꾸면 처음부터 장치를 잔뜩 설치할 수 있어요. "
        "바꾸기 전에 어떻게 될지 예상하고 ▶ 를 눌러 확인!",
        x=-380, y=-320, w=340, h=180)
    add_comment(bs, comments, dclx,
        "🗺️ 그리드는 이 손잡이로 만들어져요.\n"
        "격자시작X·격자간격X·레인시작Y·레인간격Y 로 열X(9)·레인Y(5) 리스트를 통째로 계산해요. "
        "숫자를 바꾸면 칸 배치가 바뀌어요(미션 4층: 6×10 새 판!).",
        x=-380, y=560, w=330, h=160)
    add_comment(bs, comments, hb,
        "🌊 웨이브마다 개미 수 = 기본개미수 + (웨이브-1)×웨이브당개미증가.\n"
        "체력도 종류값 + (웨이브-1)×웨이브체력증가 로 세져요(기본 +5/웨이브 — 금방 단단해짐!).\n"
        "웨이브1=기본, 2=헬멧, 3=빠른. 후반은 밀크폭탄 연타가 답!",
        x=720, y=-20, w=330, h=170)
    add_comment(bs, comments, hc,
        "🍬 하늘에서 설탕이 떨어져요(하늘설탕간격마다).\n"
        "클릭하면 주울 수 있어요(안 주우면 자동수확대기 뒤 자동으로). 설탕기계 설탕도 같이 모아요.",
        x=720, y=440, w=320, h=140)

    return bs, comments

# ============================================================
#  창고 (HOUSE: 왼쪽 창고 / 패배선)
# ============================================================
def build_house_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, -220, 0); sz = b_setsize(bs, 70)
    rs = b_rotstyle(bs)
    clr = gen(); bs[clr] = mk("looks_cleargraphiceffects")
    set_ha0 = b_setvar(bs, "애니", V_HS_ANIM, 0)
    # idle 애니 forever — 천천히(0.55초) 살짝만
    flip_h = b_changevar(bs, "애니", V_HS_ANIM, 1)
    am_h = op("operator_mod", vrep("애니", V_HS_ANIM), 2)
    even_h = cmp_op("operator_equals", am_h, 0)
    sw_h0 = b_costume(bs, "창고"); sw_h1 = b_costume(bs, "창고2")
    if_h = b_ifelse(bs, even_h, sw_h0, sw_h1)
    w_h = b_wait(bs, 0.55)
    chain([(flip_h, bs[flip_h]), (if_h, bs[if_h]), (w_h, bs[w_h])])
    fe_h = b_forever(bs, flip_h)
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs]),
           (clr, bs[clr]), (set_ha0, bs[set_ha0]), (fe_h, bs[fe_h])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["창고피격", BR_HOUSE]})
    sh, sp = b_sound(bs, 0, "thud")
    c1 = b_seteffect(bs, "COLOR", 60); x1 = b_changex(bs, -6); w1 = b_wait(bs, 0.04)
    c0 = b_seteffect(bs, "COLOR", 0); x2 = b_changex(bs, 6); w2 = b_wait(bs, 0.04)
    chain([(c1, bs[c1]), (x1, bs[x1]), (w1, bs[w1]), (c0, bs[c0]), (x2, bs[x2]), (w2, bs[w2])])
    rep = b_repeat(bs, 3, c1)
    chain([(hb, bs[hb]), (sh, bs[sh]), (sp, bs[sp]), (rep, bs[rep])])
    return bs, comments

# ============================================================
#  개미 (ZOMBIE: 스포너 + 클론 본체 + 타격 + 레인 확인)
# ============================================================
def build_zombie_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    mkBoomX = lambda: vrep("폭발X", V_BOOMX)
    mkBoomY = lambda: vrep("폭발Y", V_BOOMY)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs); orig0 = b_setvar(bs, "복제됨", V_Z_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 개미생성 → 클론 1마리 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["개미생성", BR_SPAWN]})
    cond_orig = cmp_op("operator_equals", vrep("복제됨", V_Z_ISC), 0)
    cclone = b_create_clone(bs)
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    set_isc1 = b_setvar(bs, "복제됨", V_Z_ISC, 1)
    set_type = b_setvar(bs, "내타입", V_Z_TYPE, vrep("생성타입", V_SPTYPE))
    set_lane = b_setvar(bs, "내레인", V_Z_LANE, vrep("생성레인", V_SPLANE))
    set_anim0 = b_setvar(bs, "애니", V_Z_ANIM, 0)

    def ztype_branch(type_val, hp_id, hp_nm, sp_id, sp_nm, costume, size_val):
        cond_t = cmp_op("operator_equals", vrep("내타입", V_Z_TYPE), type_val)
        wm1 = op("operator_subtract", vrep("웨이브", V_WAVE), 1)
        hpscl = op("operator_multiply", wm1, vrep("웨이브체력증가", V_HPINC))
        hp_expr = op("operator_add", vrep(hp_nm, hp_id), hpscl)
        set_hp = b_setvar(bs, "내체력", V_Z_HP, hp_expr)
        wm2 = op("operator_subtract", vrep("웨이브", V_WAVE), 1)
        spscl = op("operator_multiply", wm2, vrep("웨이브속도증가", V_SPINC))
        sp_expr = op("operator_add", vrep(sp_nm, sp_id), spscl)
        set_sp = b_setvar(bs, "내속도", V_Z_SPD, sp_expr)
        sw = b_costume(bs, costume); szb = b_setsize(bs, size_val)
        chain([(set_hp, bs[set_hp]), (set_sp, bs[set_sp]), (sw, bs[sw]), (szb, bs[szb])])
        return b_if(bs, cond_t, set_hp)
    if_t1 = ztype_branch(1, V_Z1HP, "기본개미_체력", V_Z1SP, "기본개미_속도", "기본개미", 55)
    if_t2 = ztype_branch(2, V_Z2HP, "헬멧개미_체력", V_Z2SP, "헬멧개미_속도", "헬멧개미", 56)
    if_t3 = ztype_branch(3, V_Z3HP, "빠른개미_체력", V_Z3SP, "빠른개미_속도", "빠른개미", 54)
    chain([(if_t1, bs[if_t1]), (if_t2, bs[if_t2]), (if_t3, bs[if_t3])])

    laneY = b_item_of(bs, "레인Y", L_LANEY, vrep("내레인", V_Z_LANE))
    g = b_gotoxy(bs, vrep("개미생성X", V_ZSPAWNX), laneY)
    show = b_show(bs)

    # forever
    body = []
    # 1) 게임오버 정리
    s0 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    dec_go = b_changevar(bs, "적수", V_ALIVE, -1); del_go = b_delete_clone(bs)
    chain([(dec_go, bs[dec_go]), (del_go, bs[del_go])])
    if_go = b_if(bs, s0, dec_go)
    body.append(if_go)

    # 2) 게임상태=1
    play = []
    # 갉기 vs 전진(+보행 애니)
    # 갉기: 공격 코스튬 토글 + 살짝 들이밀기 + 우걱(작은 음량, 격번 재생)
    tc_plant = b_touching(bs, "장치")
    flip_atk = b_changevar(bs, "애니", V_Z_ANIM, 1)
    def atk_pair(type_val, c0, c1):
        is_t = cmp_op("operator_equals", vrep("내타입", V_Z_TYPE), type_val)
        am = op("operator_mod", vrep("애니", V_Z_ANIM), 2)
        even = cmp_op("operator_equals", am, 0)
        sw0 = b_costume(bs, c0); sw1 = b_costume(bs, c1)
        if_fr = b_ifelse(bs, even, sw0, sw1)
        return b_if(bs, is_t, if_fr)
    ak1 = atk_pair(1, "기본개미공", "기본개미공2")
    ak2 = atk_pair(2, "헬멧개미공", "헬멧개미공2")
    ak3 = atk_pair(3, "빠른개미공", "빠른개미공2")
    # 소리는 격번만 (짝수 프레임) → 연타 소음 완화
    am_snd = op("operator_mod", vrep("애니", V_Z_ANIM), 2)
    even_snd = cmp_op("operator_equals", am_snd, 0)
    sh_ch, sp_ch = b_sound(bs, 0, "chomp")
    if_snd = b_if(bs, even_snd, sh_ch)
    # 물어뜯는 느낌: 아주 살짝만 들이밀었다 복귀
    x_push = b_changex(bs, -2)
    w_atk1 = b_wait(bs, 0.07)
    x_back = b_changex(bs, 2)
    w_atk2 = b_wait(bs, 0.07)
    chain([(flip_atk, bs[flip_atk]),
           (ak1, bs[ak1]), (ak2, bs[ak2]), (ak3, bs[ak3]),
           (if_snd, bs[if_snd]),
           (x_push, bs[x_push]), (w_atk1, bs[w_atk1]),
           (x_back, bs[x_back]), (w_atk2, bs[w_atk2])])
    # 전진: change x + 보행 애니
    neg_spd = op("operator_subtract", 0, vrep("내속도", V_Z_SPD))
    mv = b_changex(bs, neg_spd)
    flip_anim = b_changevar(bs, "애니", V_Z_ANIM, 1)
    def anim_pair(type_val, c0, c1):
        is_t = cmp_op("operator_equals", vrep("내타입", V_Z_TYPE), type_val)
        am = op("operator_mod", vrep("애니", V_Z_ANIM), 2)
        even = cmp_op("operator_equals", am, 0)
        sw0 = b_costume(bs, c0); sw1 = b_costume(bs, c1)
        if_fr = b_ifelse(bs, even, sw0, sw1)
        return b_if(bs, is_t, if_fr)
    a1 = anim_pair(1, "기본개미", "기본개미2")
    a2 = anim_pair(2, "헬멧개미", "헬멧개미2")
    a3 = anim_pair(3, "빠른개미", "빠른개미2")
    chain([(mv, bs[mv]), (flip_anim, bs[flip_anim]), (a1, bs[a1]), (a2, bs[a2]), (a3, bs[a3])])
    if_chomp = b_ifelse(bs, tc_plant, sh_ch, mv)
    play.append(if_chomp)
    # 창고 앞 도달
    x_le = cmp_op("operator_not", 0, 0)  # placeholder, replaced below
    del bs[x_le]
    xle = b_not(bs, cmp_op("operator_gt", b_xpos(bs), vrep("개미도달X", V_REACHH)))  # x<=개미도달X
    mow_unused = cmp_op("operator_equals", b_item_of(bs, "빗자루사용", L_MOWER, vrep("내레인", V_Z_LANE)), 0)
    rep_mow = b_replace_item(bs, "빗자루사용", L_MOWER, vrep("내레인", V_Z_LANE), 1)
    set_mowlane = b_setvar(bs, "작동레인", V_MOWLANE, vrep("내레인", V_Z_LANE))
    bc_mow = b_broadcast(bs, "빗자루작동", BR_MOW)
    chain([(rep_mow, bs[rep_mow]), (set_mowlane, bs[set_mowlane]), (bc_mow, bs[bc_mow])])
    dec_life = b_changevar(bs, "목숨", V_LIFE, -1)
    bc_house = b_broadcast(bs, "창고피격", BR_HOUSE)
    dec_al_house = b_changevar(bs, "적수", V_ALIVE, -1)
    del_house = b_delete_clone(bs)
    chain([(dec_life, bs[dec_life]), (bc_house, bs[bc_house]), (dec_al_house, bs[dec_al_house]),
           (del_house, bs[del_house])])
    if_mow = b_ifelse(bs, mow_unused, rep_mow, dec_life)
    if_reach = b_if(bs, xle, if_mow)
    play.append(if_reach)
    # 처치
    hp_dead = cmp_op("operator_lt", vrep("내체력", V_Z_HP), 1)
    inc_score = b_changevar(bs, "점수", V_SCORE, 1)
    add_killsun = b_changevar(bs, "설탕", V_SUNCUR, vrep("처치설탕", V_KILLSUN))
    # 처치설탕>0 → 금색 팝업
    ks_pos = cmp_op("operator_gt", vrep("처치설탕", V_KILLSUN), 0)
    set_dv = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("처치설탕", V_KILLSUN))
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, b_xpos(bs))
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, b_ypos(bs))
    set_dk = b_setvar(bs, "팝업종류", V_DMGKIND, 1)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    chain([(set_dv, bs[set_dv]), (set_dx, bs[set_dx]), (set_dy, bs[set_dy]),
           (set_dk, bs[set_dk]), (bc_dmg, bs[bc_dmg])])
    if_kspop = b_if(bs, ks_pos, set_dv)
    sh_die, sp_die = b_sound(bs, 0, "zdie")
    dec_al_kill = b_changevar(bs, "적수", V_ALIVE, -1)
    sw_boom = b_costume(bs, "개미터짐")
    ch_sz = b_changesize(bs, 8); ch_gh = b_changeeffect(bs, "GHOST", 20); w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = b_repeat(bs, 5, ch_sz)
    del_k = b_delete_clone(bs)
    chain([(inc_score, bs[inc_score]), (add_killsun, bs[add_killsun]), (if_kspop, bs[if_kspop]),
           (sh_die, bs[sh_die]), (sp_die, bs[sp_die]), (dec_al_kill, bs[dec_al_kill]),
           (sw_boom, bs[sw_boom]), (rep_an, bs[rep_an]), (del_k, bs[del_k])])
    if_kill = b_if(bs, hp_dead, inc_score)
    play.append(if_kill)
    chain([(b, bs[b]) for b in play])
    s1 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_play_z = b_if(bs, s1, play[0])
    body.append(if_play_z)

    w_body = b_wait(bs, 0.05)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_type, bs[set_type]),
           (set_lane, bs[set_lane]), (set_anim0, bs[set_anim0]), (if_t1, bs[if_t1])])
    chain([(if_t3, bs[if_t3]), (g, bs[g]), (show, bs[show]), (fe_body, bs[fe_body])])

    # (D) 타격 받으면 반경 안일 때 데미지 — wait 없는 원자 실행
    ht = gen(); bs[ht] = mk("event_whenbroadcastreceived", top=True, x=400, y=360,
        fields={"BROADCAST_OPTION": ["타격", BR_HIT]})
    c_clone = cmp_op("operator_equals", vrep("복제됨", V_Z_ISC), 1)
    c_pl = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_active = bool_op("operator_and", c_clone, c_pl)
    dist_boom = b_dist_to(bs, op, mkBoomX, mkBoomY)
    cond_in = b_not(bs, cmp_op("operator_gt", dist_boom, vrep("폭발반경", V_BOOMR)))
    neg_d = op("operator_subtract", 0, vrep("폭발데미지", V_BOOMD))
    dec_hp = b_changevar(bs, "내체력", V_Z_HP, neg_d)
    if_in = b_if(bs, cond_in, dec_hp)
    if_active = b_if(bs, c_active, if_in)
    chain([(ht, bs[ht]), (if_active, bs[if_active])])

    # (E) 레인 확인 (불리언 OR 리덕션) — wait 없는 원자 실행
    # 같은 레인이고, 장치보다 오른쪽이거나 거의 겹침(마진 40px)이면 보고.
    # 예: 개미가 장치를 갉는 중(x≈장치x)에도 계속 맞출 수 있게.
    he = gen(); bs[he] = mk("event_whenbroadcastreceived", top=True, x=400, y=560,
        fields={"BROADCAST_OPTION": ["개미레인확인", BR_LANE]})
    c_clone2 = cmp_op("operator_equals", vrep("복제됨", V_Z_ISC), 1)
    c_pl2 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_active2 = bool_op("operator_and", c_clone2, c_pl2)
    # round 로 레인 인덱스 타입(1 vs 1.0) 불일치 흡수
    z_lane_r = b_round(bs, vrep("내레인", V_Z_LANE))
    aim_lane_r = b_round(bs, vrep("조준레인", V_AIMLANE))
    same_lane = cmp_op("operator_equals", z_lane_r, aim_lane_r)
    # xpos >= 조준탑X - 40  →  not (xpos < 조준탑X - 40)  →  not (xpos + 40 < 조준탑X)
    # simpler: not (xpos < 조준탑X - 40) = not (조준탑X - xpos > 40)... use:
    # xpos + 40 >= 조준탑X  →  not (xpos + 40 < 조준탑X)
    x_plus = op("operator_add", b_xpos(bs), 40)
    too_left = cmp_op("operator_lt", x_plus, vrep("조준탑X", V_AIMTX))
    in_front = b_not(bs, too_left)
    c_report = bool_op("operator_and", same_lane, in_front)
    set_ok = b_setvar(bs, "조준적있음", V_AIMOK, 1)
    if_report = b_if(bs, c_report, set_ok)
    if_active2 = b_if(bs, c_active2, if_report)
    chain([(he, bs[he]), (if_active2, bs[if_active2])])

    add_comment(bs, comments, if_play_z,
        "🐜 자기 레인을 따라 왼쪽으로 기어와요(change x by -내속도). 장치를 만나면 멈춰서 오독오독!\n"
        "창고 앞(개미도달X)에 닿으면 빗자루가 한 번 구해줘요. 두 번째로 뚫리면 목숨이 깎여요.",
        x=520, y=320, w=340, h=160)
    add_comment(bs, comments, if_active2,
        "🎯 쿠키알콩이 부르면 '내가 이 레인(조준레인)에서 쿠키알콩 오른쪽(조준탑X)에 있나?'를 알려줘요.\n"
        "여러 개미가 있어도 OR로 합쳐져 답이 하나 — wait 없이 한 번에 실행돼서 경쟁 없이 정확해요.",
        x=720, y=520, w=330, h=160)
    return bs, comments

# ============================================================
#  쿠키탄 (PEA BULLET)
# ============================================================
def build_pea_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs); orig0 = b_setvar(bs, "복제됨", V_PB_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 쿠키발사 → 탄 클론 1개 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["쿠키발사", BR_FIRE]})
    cond_orig = cmp_op("operator_equals", vrep("복제됨", V_PB_ISC), 0)
    cclone = b_create_clone(bs)
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    set_isc1 = b_setvar(bs, "복제됨", V_PB_ISC, 1)
    set_lane = b_setvar(bs, "내레인", V_PB_LANE, vrep("발사레인", V_FIRELN))
    set_pa0 = b_setvar(bs, "애니", V_PB_ANIM, 0)
    g = b_gotoxy(bs, vrep("발사X", V_FIREX), vrep("발사Y", V_FIREY))
    sw = b_costume(bs, "쿠키알"); pd = b_pointdir(bs, 90); front = b_front(bs); show = b_show(bs)
    # repeat until (touching 개미 or touching edge or 게임상태=0) — 비행 중 회전 애니
    mv = b_changex(bs, vrep("쿠키속도", V_PEASPD))
    flip_p = b_changevar(bs, "애니", V_PB_ANIM, 1)
    am_p = op("operator_mod", vrep("애니", V_PB_ANIM), 2)
    even_p = cmp_op("operator_equals", am_p, 0)
    sw_p0 = b_costume(bs, "쿠키알"); sw_p1 = b_costume(bs, "쿠키알2")
    if_pfr = b_ifelse(bs, even_p, sw_p0, sw_p1)
    w_mv = b_wait(bs, 0.02)
    chain([(mv, bs[mv]), (flip_p, bs[flip_p]), (if_pfr, bs[if_pfr]), (w_mv, bs[w_mv])])
    tc_z = b_touching(bs, "개미")
    edge_menu = gen(); bs[edge_menu] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_edge = gen(); bs[tc_edge] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge_menu]})
    bs[edge_menu]["parent"] = tc_edge
    c_over = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    or1 = bool_op("operator_or", tc_z, tc_edge)
    or2 = bool_op("operator_or", or1, c_over)
    ru = b_repeat_until(bs, or2, mv)
    # if 게임상태!=0 and touching 개미 → 타격 + 팝업
    c_live = b_not(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 0))
    tc_z2 = b_touching(bs, "개미")
    c_hit = bool_op("operator_and", c_live, tc_z2)
    set_bx = b_setvar(bs, "폭발X", V_BOOMX, b_xpos(bs))
    set_by = b_setvar(bs, "폭발Y", V_BOOMY, b_ypos(bs))
    set_bd = b_setvar(bs, "폭발데미지", V_BOOMD, vrep("쿠키캐논_공격력", V_PEADMG))
    set_br = b_setvar(bs, "폭발반경", V_BOOMR, vrep("쿠키반경", V_PEAR))
    bcw_hit = b_broadcast_wait(bs, "타격", BR_HIT)
    set_dv = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("쿠키캐논_공격력", V_PEADMG))
    set_ddx = b_setvar(bs, "데미지표시x", V_DMGX, vrep("폭발X", V_BOOMX))
    set_ddy = b_setvar(bs, "데미지표시y", V_DMGY, vrep("폭발Y", V_BOOMY))
    set_dk = b_setvar(bs, "팝업종류", V_DMGKIND, 0)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]), (set_bd, bs[set_bd]), (set_br, bs[set_br]),
           (bcw_hit, bs[bcw_hit]), (set_dv, bs[set_dv]), (set_ddx, bs[set_ddx]),
           (set_ddy, bs[set_ddy]), (set_dk, bs[set_dk]), (bc_dmg, bs[bc_dmg])])
    if_hit = b_if(bs, c_hit, set_bx)
    del_c = b_delete_clone(bs)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_lane, bs[set_lane]),
           (set_pa0, bs[set_pa0]), (g, bs[g]),
           (sw, bs[sw]), (pd, bs[pd]), (front, bs[front]), (show, bs[show]),
           (ru, bs[ru]), (if_hit, bs[if_hit]), (del_c, bs[del_c])])
    return bs, comments

# ============================================================
#  장치 (PLANT: 설치 클론 본체 — 4종)
# ============================================================
def build_plant_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    def grid_index():   # (내레인-1)*열개수 + 내열
        rm1 = op("operator_subtract", vrep("내레인", V_PL_LANE), 1)
        rc = op("operator_multiply", rm1, vrep("열개수", V_COLS))
        return op("operator_add", rc, vrep("내열", V_PL_COL))

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs); orig0 = b_setvar(bs, "복제됨", V_PL_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 장치설치 → 클론 1기 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["장치설치", BR_PLACE]})
    cond_orig = cmp_op("operator_equals", vrep("복제됨", V_PL_ISC), 0)
    cclone = b_create_clone(bs)
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    set_isc1 = b_setvar(bs, "복제됨", V_PL_ISC, 1)
    set_type = b_setvar(bs, "내타입", V_PL_TYPE, vrep("설치타입", V_PLACET))
    set_lane = b_setvar(bs, "내레인", V_PL_LANE, vrep("설치레인", V_PLACEL))
    set_col = b_setvar(bs, "내열", V_PL_COL, vrep("설치열", V_PLACEC))
    g = b_gotoxy(bs, vrep("설치X", V_PLACEX), vrep("설치Y", V_PLACEY))
    set_cd0 = b_setvar(bs, "발사쿨", V_PL_CD, 0)
    set_fuse0 = b_setvar(bs, "퓨즈", V_PL_FUSE, 0)

    def ptype_branch(type_val, hp_id, hp_nm, costume, size_val):
        cond_t = cmp_op("operator_equals", vrep("내타입", V_PL_TYPE), type_val)
        set_hp = b_setvar(bs, "내체력", V_PL_HP, vrep(hp_nm, hp_id))
        sw = b_costume(bs, costume); szb = b_setsize(bs, size_val)
        chain([(set_hp, bs[set_hp]), (sw, bs[sw]), (szb, bs[szb])])
        return b_if(bs, cond_t, set_hp)
    # 타일(40×55) 안에 쏙 들어가게 크기 축소
    if_p1 = ptype_branch(1, V_SFHP, "설탕기계_체력", "설탕기계", 58)
    if_p2 = ptype_branch(2, V_PEAHP, "쿠키캐논_체력", "쿠키캐논", 58)
    if_p3 = ptype_branch(3, V_NUTHP, "초코벽_체력", "초코벽", 60)
    if_p4 = ptype_branch(4, V_CHHP, "밀크폭탄_체력", "밀크폭탄", 58)
    chain([(if_p1, bs[if_p1]), (if_p2, bs[if_p2]), (if_p3, bs[if_p3]), (if_p4, bs[if_p4])])
    show = b_show(bs)

    # 밀크폭탄(타입4): 도화선 동안 깜빡 애니 → 폭발 후 종료
    is_cherry = cmp_op("operator_equals", vrep("내타입", V_PL_TYPE), 4)
    # 퓨즈 대기: 0.1초마다 코스튬 토글
    fuse_ticks = op("operator_divide", vrep("밀크폭탄_퓨즈", V_CHFUSE), 0.1)
    flip_fuse = b_changevar(bs, "애니", V_PL_ANIM, 1)
    am_f = op("operator_mod", vrep("애니", V_PL_ANIM), 2)
    even_f = cmp_op("operator_equals", am_f, 0)
    sw_f0 = b_costume(bs, "밀크폭탄"); sw_f1 = b_costume(bs, "밀크폭탄2")
    if_ff = b_ifelse(bs, even_f, sw_f0, sw_f1)
    w_ft = b_wait(bs, 0.1)
    chain([(flip_fuse, bs[flip_fuse]), (if_ff, bs[if_ff]), (w_ft, bs[w_ft])])
    rep_fuse = b_repeat(bs, fuse_ticks, flip_fuse)
    set_bx = b_setvar(bs, "폭발X", V_BOOMX, b_xpos(bs))
    set_by = b_setvar(bs, "폭발Y", V_BOOMY, b_ypos(bs))
    set_bd = b_setvar(bs, "폭발데미지", V_BOOMD, vrep("밀크폭탄_데미지", V_CHDMG))
    set_br = b_setvar(bs, "폭발반경", V_BOOMR, vrep("밀크폭탄_반경", V_CHR))
    sh_ch, sp_ch = b_sound(bs, 0, "cherry")
    bcw_hit = b_broadcast_wait(bs, "타격", BR_HIT)
    set_dv = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("밀크폭탄_데미지", V_CHDMG))
    set_ddx = b_setvar(bs, "데미지표시x", V_DMGX, b_xpos(bs))
    set_ddy = b_setvar(bs, "데미지표시y", V_DMGY, b_ypos(bs))
    set_dk = b_setvar(bs, "팝업종류", V_DMGKIND, 0)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    sw_boom = b_costume(bs, "장치터짐")
    rep_cell0 = b_replace_item(bs, "격자점유", L_CELL, grid_index(), 0)
    ch_sz = b_changesize(bs, 12); ch_gh = b_changeeffect(bs, "GHOST", 20); w_an = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = b_repeat(bs, 5, ch_sz)
    del_ch = b_delete_clone(bs)
    chain([(rep_fuse, bs[rep_fuse]), (set_bx, bs[set_bx]), (set_by, bs[set_by]), (set_bd, bs[set_bd]),
           (set_br, bs[set_br]), (sh_ch, bs[sh_ch]), (sp_ch, bs[sp_ch]), (bcw_hit, bs[bcw_hit]),
           (set_dv, bs[set_dv]), (set_ddx, bs[set_ddx]), (set_ddy, bs[set_ddy]), (set_dk, bs[set_dk]),
           (bc_dmg, bs[bc_dmg]), (sw_boom, bs[sw_boom]), (rep_cell0, bs[rep_cell0]),
           (rep_an, bs[rep_an]), (del_ch, bs[del_ch])])
    if_cherry = b_if(bs, is_cherry, rep_fuse)

    # 설탕기계/쿠키알/초코벽 공통 forever
    body = []
    s0 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    del_go = b_delete_clone(bs)
    if_go = b_if(bs, s0, del_go)
    body.append(if_go)

    # 능동 동작 (게임상태=1)
    play = []
    # 설탕기계(타입1): 발사쿨<=0 → 설탕 생산
    is_sf = cmp_op("operator_equals", vrep("내타입", V_PL_TYPE), 1)
    cd_le0_a = b_not(bs, cmp_op("operator_gt", vrep("발사쿨", V_PL_CD), 0))
    c_sf = bool_op("operator_and", is_sf, cd_le0_a)
    set_kind1 = b_setvar(bs, "설탕종류", V_SUNKIND, 1)
    set_sx = b_setvar(bs, "설탕X", V_SUNX, b_xpos(bs))
    set_sy = b_setvar(bs, "설탕Y", V_SUNY, b_ypos(bs))
    bc_sun = b_broadcast(bs, "설탕생성", BR_SUN)
    set_cd_sf = b_setvar(bs, "발사쿨", V_PL_CD, vrep("설탕기계간격", V_SUNINT))
    chain([(set_kind1, bs[set_kind1]), (set_sx, bs[set_sx]), (set_sy, bs[set_sy]),
           (bc_sun, bs[bc_sun]), (set_cd_sf, bs[set_cd_sf])])
    if_sf = b_if(bs, c_sf, set_kind1)
    play.append(if_sf)
    # 쿠키알(타입2): 발사쿨<=0 이면 **무조건 발사**.
    # 예전엔 개미레인확인 핸드셰이크(조준적있음)에만 의존 → 판정 실패 시 한 발도 안 나감.
    # 쿠키알는 자기 y로 직진하고 충돌로만 데미지 들어가서, 빈 레인에 쏘아도 다른 레인 개미는 안 맞음.
    is_pea = cmp_op("operator_equals", vrep("내타입", V_PL_TYPE), 2)
    cd_le0_b = b_not(bs, cmp_op("operator_gt", vrep("발사쿨", V_PL_CD), 0))
    c_pea = bool_op("operator_and", is_pea, cd_le0_b)
    set_fx = b_setvar(bs, "발사X", V_FIREX, b_xpos(bs))
    set_fy = b_setvar(bs, "발사Y", V_FIREY, b_ypos(bs))
    set_fl = b_setvar(bs, "발사레인", V_FIRELN, vrep("내레인", V_PL_LANE))
    sh_pea, sp_pea = b_sound(bs, 0, "pea")
    bc_fire = b_broadcast(bs, "쿠키발사", BR_FIRE)
    set_cd_pea = b_setvar(bs, "발사쿨", V_PL_CD, vrep("쿠키캐논_간격", V_PEAGAP))
    chain([(set_fx, bs[set_fx]), (set_fy, bs[set_fy]), (set_fl, bs[set_fl]), (sh_pea, bs[sh_pea]),
           (sp_pea, bs[sp_pea]), (bc_fire, bs[bc_fire]), (set_cd_pea, bs[set_cd_pea])])
    if_pea = b_if(bs, c_pea, set_fx)
    play.append(if_pea)
    # 갉힘 — 체력 감소 + 피격 흔들림/깜빡 + (초코벽이면) 금 간 코스튬
    tc_z = b_touching(bs, "개미")
    neg_bite = op("operator_subtract", 0, vrep("개미갉기력", V_BITE))
    dec_hp = b_changevar(bs, "내체력", V_PL_HP, neg_bite)
    # 피격 연출: 좌우 흔들 + 빨강/어두움
    hit_x1 = b_changex(bs, -4)
    hit_col = b_seteffect(bs, "COLOR", 40)
    hit_bri = b_seteffect(bs, "BRIGHTNESS", -25)
    hit_w1 = b_wait(bs, 0.04)
    hit_x2 = b_changex(bs, 4)
    hit_clr = gen(); bs[hit_clr] = mk("looks_cleargraphiceffects")
    hit_w2 = b_wait(bs, 0.04)
    # 초코벽 손상 단계: 체력 <= 초코벽_체력/2 → 금1, <= 초코벽_체력/4 → 금2
    # (reporter parent 1개 제한 → 비교식은 분기마다 새로 생성)
    is_nut = cmp_op("operator_equals", vrep("내타입", V_PL_TYPE), 3)
    half_hp = op("operator_divide", vrep("초코벽_체력", V_NUTHP), 2)
    quarter_hp = op("operator_divide", vrep("초코벽_체력", V_NUTHP), 4)
    low2 = b_not(bs, cmp_op("operator_gt", vrep("내체력", V_PL_HP), quarter_hp))
    sw_dmg2 = b_costume(bs, "초코벽금2")
    if_dmg2 = b_if(bs, low2, sw_dmg2)
    # dmg1: hp <= half AND hp > quarter
    low1b = b_not(bs, cmp_op("operator_gt", vrep("내체력", V_PL_HP), half_hp))
    hi_q = cmp_op("operator_gt", vrep("내체력", V_PL_HP), quarter_hp)
    c_dmg1 = bool_op("operator_and", low1b, hi_q)
    sw_dmg1 = b_costume(bs, "초코벽금")
    if_dmg1 = b_if(bs, c_dmg1, sw_dmg1)
    chain([(if_dmg2, bs[if_dmg2]), (if_dmg1, bs[if_dmg1])])
    if_nut_dmg = b_if(bs, is_nut, if_dmg2)
    chain([(dec_hp, bs[dec_hp]),
           (hit_x1, bs[hit_x1]), (hit_col, bs[hit_col]), (hit_bri, bs[hit_bri]), (hit_w1, bs[hit_w1]),
           (hit_x2, bs[hit_x2]), (hit_clr, bs[hit_clr]), (hit_w2, bs[hit_w2]),
           (if_nut_dmg, bs[if_nut_dmg])])
    if_bite = b_if(bs, tc_z, dec_hp)
    play.append(if_bite)
    # 죽음
    hp_dead = cmp_op("operator_lt", vrep("내체력", V_PL_HP), 1)
    rep_cell = b_replace_item(bs, "격자점유", L_CELL, grid_index(), 0)
    sw_boom2 = b_costume(bs, "장치터짐")
    ch_gh2 = b_changeeffect(bs, "GHOST", 25); w_an2 = b_wait(bs, 0.03)
    chain([(ch_gh2, bs[ch_gh2]), (w_an2, bs[w_an2])])
    rep_an2 = b_repeat(bs, 3, ch_gh2)
    del_d = b_delete_clone(bs)
    chain([(rep_cell, bs[rep_cell]), (sw_boom2, bs[sw_boom2]), (rep_an2, bs[rep_an2]), (del_d, bs[del_d])])
    if_dead = b_if(bs, hp_dead, rep_cell)
    play.append(if_dead)
    # idle 애니 — 피격 중 아닐 때만, 6틱(~0.3초)마다 한 번만 코스튬 전환(경박함 방지)
    not_biting = b_not(bs, b_touching(bs, "개미"))
    flip_pl = b_changevar(bs, "애니", V_PL_ANIM, 1)
    # 애니 mod 6 = 0 일 때만 코스튬 갱신, mod 12 로 프레임 0/1 구분
    mod6 = op("operator_mod", vrep("애니", V_PL_ANIM), 6)
    should_sw = cmp_op("operator_equals", mod6, 0)
    mod12 = op("operator_mod", vrep("애니", V_PL_ANIM), 12)
    frame0 = cmp_op("operator_equals", mod12, 0)  # 0→frame0, 6→frame1
    def plant_anim_pair(type_val, c0, c1):
        is_t = cmp_op("operator_equals", vrep("내타입", V_PL_TYPE), type_val)
        # frame0 비교식은 parent 1개 제한 → 타입마다 새로
        m12 = op("operator_mod", vrep("애니", V_PL_ANIM), 12)
        f0 = cmp_op("operator_equals", m12, 0)
        sw0 = b_costume(bs, c0); sw1 = b_costume(bs, c1)
        if_fr = b_ifelse(bs, f0, sw0, sw1)
        return b_if(bs, is_t, if_fr)
    pa1 = plant_anim_pair(1, "설탕기계", "설탕기계2")
    pa2 = plant_anim_pair(2, "쿠키캐논", "쿠키캐논2")
    half_hp2 = op("operator_divide", vrep("초코벽_체력", V_NUTHP), 2)
    nut_ok = cmp_op("operator_gt", vrep("내체력", V_PL_HP), half_hp2)
    is_nut2 = cmp_op("operator_equals", vrep("내타입", V_PL_TYPE), 3)
    c_nut_idle = bool_op("operator_and", is_nut2, nut_ok)
    m12n = op("operator_mod", vrep("애니", V_PL_ANIM), 12)
    f0n = cmp_op("operator_equals", m12n, 0)
    sw_n0 = b_costume(bs, "초코벽"); sw_n1 = b_costume(bs, "초코벽2")
    if_nfr = b_ifelse(bs, f0n, sw_n0, sw_n1)
    pa3 = b_if(bs, c_nut_idle, if_nfr)
    pa4 = plant_anim_pair(4, "밀크폭탄", "밀크폭탄2")
    chain([(pa1, bs[pa1]), (pa2, bs[pa2]), (pa3, bs[pa3]), (pa4, bs[pa4])])
    if_sw = b_if(bs, should_sw, pa1)
    chain([(flip_pl, bs[flip_pl]), (if_sw, bs[if_sw])])
    if_idle = b_if(bs, not_biting, flip_pl)
    play.append(if_idle)
    # 쿨 감소
    dec_cd = b_changevar(bs, "발사쿨", V_PL_CD, -0.05)
    play.append(dec_cd)
    chain([(b, bs[b]) for b in play])
    s1 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_play = b_if(bs, s1, play[0])
    body.append(if_play)

    w_body = b_wait(bs, 0.05)
    chain([(b, bs[b]) for b in body] + [(w_body, bs[w_body])])
    fe_body = b_forever(bs, body[0])
    set_planim0 = b_setvar(bs, "애니", V_PL_ANIM, 0)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_type, bs[set_type]), (set_lane, bs[set_lane]),
           (set_col, bs[set_col]), (g, bs[g]), (set_cd0, bs[set_cd0]), (set_fuse0, bs[set_fuse0]),
           (set_planim0, bs[set_planim0]), (if_p1, bs[if_p1])])
    chain([(if_p4, bs[if_p4]), (show, bs[show]), (if_cherry, bs[if_cherry]), (fe_body, bs[fe_body])])

    add_comment(bs, comments, if_play,
        "🍬 설탕기계=설탕 생산, 🍪쿠키캐논=레인에 개미 있으면 발사, 🧱초코벽=버티기(탱크), 🥛밀크폭탄=도화선 뒤 쾅!\n"
        "설치타입으로 종류가 정해지고 체력/특성은 종류 변수에서 읽어요. 개미에 닿으면 내체력이 닳아요.",
        x=520, y=320, w=350, h=170)
    return bs, comments

# ============================================================
#  빗자루 (MOWER: 레인당 1회)
# ============================================================
def build_mower_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs); orig0 = b_setvar(bs, "복제됨", V_MO_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (게임시작) → 레인개수만큼 클론 생성 후 주차
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    cond_orig = cmp_op("operator_equals", vrep("복제됨", V_MO_ISC), 0)
    seti = b_setvar(bs, "i", V_I, 1)
    set_ch_lane = b_setvar(bs, "생성레인", V_SPLANE, vrep("i", V_I))
    cclone = b_create_clone(bs)
    w_c = b_wait(bs, 0.05)
    inci = b_changevar(bs, "i", V_I, 1)
    chain([(set_ch_lane, bs[set_ch_lane]), (cclone, bs[cclone]), (w_c, bs[w_c]), (inci, bs[inci])])
    rep = b_repeat(bs, vrep("레인개수", V_ROWS), set_ch_lane)
    chain([(seti, bs[seti]), (rep, bs[rep])])
    if_make = b_if(bs, cond_orig, seti)
    chain([(hb, bs[hb]), (if_make, bs[if_make])])

    # (C) 클론 시작 → 주차
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set_isc1 = b_setvar(bs, "복제됨", V_MO_ISC, 1)
    set_lane = b_setvar(bs, "내레인", V_MO_LANE, vrep("생성레인", V_SPLANE))
    set_used0 = b_setvar(bs, "사용됨", V_MO_USED, 0)
    set_run0 = b_setvar(bs, "작동중", V_MO_RUN, 0)
    parkx = op("operator_subtract", vrep("격자시작X", V_GX), vrep("격자간격X", V_GXSTEP))
    parky = b_item_of(bs, "레인Y", L_LANEY, vrep("내레인", V_MO_LANE))
    g = b_gotoxy(bs, parkx, parky)
    sz = b_setsize(bs, 48); show = b_show(bs)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_lane, bs[set_lane]), (set_used0, bs[set_used0]),
           (set_run0, bs[set_run0]), (g, bs[g]), (sz, bs[sz]), (show, bs[show])])

    # (B) 작동레인 발동 → 질주 스윕
    hm = gen(); bs[hm] = mk("event_whenbroadcastreceived", top=True, x=400, y=200,
        fields={"BROADCAST_OPTION": ["빗자루작동", BR_MOW]})
    c_clone = cmp_op("operator_equals", vrep("복제됨", V_MO_ISC), 1)
    c_lane = cmp_op("operator_equals", vrep("작동레인", V_MOWLANE), vrep("내레인", V_MO_LANE))
    c_notrun = cmp_op("operator_equals", vrep("작동중", V_MO_RUN), 0)
    c_go = bool_op("operator_and", bool_op("operator_and", c_clone, c_lane), c_notrun)
    set_run1 = b_setvar(bs, "작동중", V_MO_RUN, 1)
    set_moa0 = b_setvar(bs, "애니", V_MO_ANIM, 0)
    sh_mow, sp_mow = b_sound(bs, 0, "mower")
    mv = b_changex(bs, vrep("빗자루속도", V_MOWSPD))
    flip_mo = b_changevar(bs, "애니", V_MO_ANIM, 1)
    am_mo = op("operator_mod", vrep("애니", V_MO_ANIM), 2)
    even_mo = cmp_op("operator_equals", am_mo, 0)
    sw_m0 = b_costume(bs, "빗자루"); sw_m1 = b_costume(bs, "빗자루2")
    if_mfr = b_ifelse(bs, even_mo, sw_m0, sw_m1)
    set_bx = b_setvar(bs, "폭발X", V_BOOMX, b_xpos(bs))
    set_by = b_setvar(bs, "폭발Y", V_BOOMY, b_item_of(bs, "레인Y", L_LANEY, vrep("내레인", V_MO_LANE)))
    set_bd = b_setvar(bs, "폭발데미지", V_BOOMD, 9999)
    set_br = b_setvar(bs, "폭발반경", V_BOOMR, 35)
    bcw_hit = b_broadcast_wait(bs, "타격", BR_HIT)
    w_sw = b_wait(bs, 0.02)
    chain([(mv, bs[mv]), (flip_mo, bs[flip_mo]), (if_mfr, bs[if_mfr]),
           (set_bx, bs[set_bx]), (set_by, bs[set_by]), (set_bd, bs[set_bd]),
           (set_br, bs[set_br]), (bcw_hit, bs[bcw_hit]), (w_sw, bs[w_sw])])
    x_gt = cmp_op("operator_gt", b_xpos(bs), 240)
    ru = b_repeat_until(bs, x_gt, mv)
    del_c = b_delete_clone(bs)
    chain([(set_run1, bs[set_run1]), (set_moa0, bs[set_moa0]), (sh_mow, bs[sh_mow]), (sp_mow, bs[sp_mow]),
           (ru, bs[ru]), (del_c, bs[del_c])])
    if_go = b_if(bs, c_go, set_run1)
    chain([(hm, bs[hm]), (if_go, bs[if_go])])

    add_comment(bs, comments, hm,
        "🧹 창고 앞이 뚫리면 빗자루가 딱 한 번 레인을 싹 밀어줘요!\n"
        "질주하며 매 틱 '타격'(큰 데미지)으로 레인의 개미를 쓸어버려요. 두 번째로 뚫리면 목숨이 깎여요.",
        x=720, y=180, w=340, h=150)
    return bs, comments

# ============================================================
#  설탕 (SUN: 수집)
# ============================================================
def build_sun_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs); orig0 = b_setvar(bs, "복제됨", V_SU_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 설탕생성 → 클론 1개 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["설탕생성", BR_SUN]})
    cond_orig = cmp_op("operator_equals", vrep("복제됨", V_SU_ISC), 0)
    cclone = b_create_clone(bs)
    if_spawn = b_if(bs, cond_orig, cclone)
    chain([(hb, bs[hb]), (if_spawn, bs[if_spawn])])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=360)
    set_isc1 = b_setvar(bs, "복제됨", V_SU_ISC, 1)
    set_kind = b_setvar(bs, "내종류", V_SU_KIND, vrep("설탕종류", V_SUNKIND))
    set_life0 = b_setvar(bs, "수명", V_SU_LIFE, 0)
    set_suanim0 = b_setvar(bs, "애니", V_SU_ANIM, 0)
    sw = b_costume(bs, "설탕"); sz = b_setsize(bs, 55); front = b_front(bs)
    # 하늘 낙하 vs 설탕기계 등장
    is_sky = cmp_op("operator_equals", vrep("내종류", V_SU_KIND), 0)
    g_sky = b_gotoxy(bs, vrep("설탕X", V_SUNX), 180)
    show1 = b_show(bs)
    dy = b_changey(bs, -3); w_dy = b_wait(bs, 0.02)
    chain([(dy, bs[dy]), (w_dy, bs[w_dy])])
    y_le = b_not(bs, cmp_op("operator_gt", b_ypos(bs), vrep("설탕Y", V_SUNY)))  # y<=설탕Y
    ru_fall = b_repeat_until(bs, y_le, dy)
    chain([(g_sky, bs[g_sky]), (show1, bs[show1]), (ru_fall, bs[ru_fall])])
    g_prod = b_gotoxy(bs, vrep("설탕X", V_SUNX), vrep("설탕Y", V_SUNY))
    show2 = b_show(bs)
    ch_sz = b_changesize(bs, 5); w_sz = b_wait(bs, 0.02)
    chain([(ch_sz, bs[ch_sz]), (w_sz, bs[w_sz])])
    rep_pop = b_repeat(bs, 4, ch_sz)
    chain([(g_prod, bs[g_prod]), (show2, bs[show2]), (rep_pop, bs[rep_pop])])
    if_kind = b_ifelse(bs, is_sky, g_sky, g_prod)
    # 대기: 클릭 or 자동수확 or 개미 접촉(짓밟힘) or 게임오버
    # 개미가 설탕 아이템에 걸리면 안 됨 → 닿는 즉시 설탕만 사라지고 개미는 계속 전진
    # 매 틱 go to front → 설치커서보다 위에 올라와 클릭 우선권을 받음
    md = b_mousedown(bs); tc_m = b_touching(bs, "_mouse_")
    c_click = bool_op("operator_and", md, tc_m)
    auto = op("operator_divide", vrep("자동수확대기", V_AUTOPICK), 0.05)
    c_auto = cmp_op("operator_gt", vrep("수명", V_SU_LIFE), auto)
    c_over = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    c_ant = b_touching(bs, "개미")
    or_wait = bool_op("operator_or",
                      bool_op("operator_or", bool_op("operator_or", c_click, c_auto), c_over),
                      c_ant)
    inc_life = b_changevar(bs, "수명", V_SU_LIFE, 1)
    front_tick = b_front(bs)
    # 설탕 보석 반짝 애니
    flip_su = b_changevar(bs, "애니", V_SU_ANIM, 1)
    am_s = op("operator_mod", vrep("애니", V_SU_ANIM), 2)
    even_s = cmp_op("operator_equals", am_s, 0)
    sw_s0 = b_costume(bs, "설탕"); sw_s1 = b_costume(bs, "설탕2")
    if_su = b_ifelse(bs, even_s, sw_s0, sw_s1)
    w_life = b_wait(bs, 0.05)
    chain([(inc_life, bs[inc_life]), (front_tick, bs[front_tick]),
           (flip_su, bs[flip_su]), (if_su, bs[if_su]), (w_life, bs[w_life])])
    ru_wait = b_repeat_until(bs, or_wait, inc_life)
    # 개미에 밟혔으면 수확 없이 삭제만 (전진 방해 X)
    tc_ant2 = b_touching(bs, "개미")
    # 클릭 수확이면 설치잠금=1 → 같은 클릭의 마우스 업으로 장치가 설치지 않게
    md2 = b_mousedown(bs); tc_m2 = b_touching(bs, "_mouse_")
    c_click2 = bool_op("operator_and", md2, tc_m2)
    set_lock = b_setvar(bs, "설치잠금", V_PLANTLOCK, 1)
    if_lock = b_if(bs, c_click2, set_lock)
    # 수확: 살아있고 + 개미에 안 밟힌 경우만 (클릭/자동수확)
    c_live = b_not(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 0))
    not_ant = b_not(bs, tc_ant2)
    c_harvest = bool_op("operator_and", c_live, not_ant)
    add_sun = b_changevar(bs, "설탕", V_SUNCUR, vrep("하늘설탕량", V_SKYSUN))
    set_dv = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("하늘설탕량", V_SKYSUN))
    set_ddx = b_setvar(bs, "데미지표시x", V_DMGX, b_xpos(bs))
    set_ddy = b_setvar(bs, "데미지표시y", V_DMGY, b_ypos(bs))
    set_dk = b_setvar(bs, "팝업종류", V_DMGKIND, 1)
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    sh_sun, sp_sun = b_sound(bs, 0, "sun")
    chain([(add_sun, bs[add_sun]), (set_dv, bs[set_dv]), (set_ddx, bs[set_ddx]), (set_ddy, bs[set_ddy]),
           (set_dk, bs[set_dk]), (bc_dmg, bs[bc_dmg]), (sh_sun, bs[sh_sun]), (sp_sun, bs[sp_sun])])
    if_harvest = b_if(bs, c_harvest, add_sun)
    del_c = b_delete_clone(bs)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (set_kind, bs[set_kind]), (set_life0, bs[set_life0]),
           (set_suanim0, bs[set_suanim0]),
           (sw, bs[sw]), (sz, bs[sz]), (front, bs[front]), (if_kind, bs[if_kind]),
           (ru_wait, bs[ru_wait]), (if_lock, bs[if_lock]), (if_harvest, bs[if_harvest]),
           (del_c, bs[del_c])])
    return bs, comments

# ============================================================
#  메뉴판 (SEED PALETTE)
# ============================================================
def build_palette_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, -65, 150); sz = b_setsize(bs, 100)
    front = b_front(bs); rs = b_rotstyle(bs)
    chain([(h, bs[h]), (show, bs[show]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]), (rs, bs[rs])])

    hc = gen(); bs[hc] = mk("event_whenthisspriteclicked", top=True, x=20, y=220)
    set1 = b_setvar(bs, "선택장치", V_SEL, 1)
    set2 = b_setvar(bs, "선택장치", V_SEL, 2)
    set3 = b_setvar(bs, "선택장치", V_SEL, 3)
    set4 = b_setvar(bs, "선택장치", V_SEL, 4)
    c_c = cmp_op("operator_lt", b_mousex(bs), -25)
    if_c = b_ifelse(bs, c_c, set3, set4)
    c_b = cmp_op("operator_lt", b_mousex(bs), -65)
    if_b = b_ifelse(bs, c_b, set2, if_c)
    c_a = cmp_op("operator_lt", b_mousex(bs), -105)
    if_a = b_ifelse(bs, c_a, set1, if_b)
    chain([(hc, bs[hc]), (if_a, bs[if_a])])

    add_comment(bs, comments, hc,
        "🍬 메뉴판: 클릭한 가로 위치로 장치를 골라요(선택장치 1·2·3·4).\n"
        "🌻설탕기계·🌱쿠키알콩·🥜초코벽·🍒밀크폭탄 4칸은 항상 사용 가능! 고르면 설치커서가 나타나요.",
        x=420, y=180, w=330, h=150)
    return bs, comments

# ============================================================
#  설치커서 (PLANT CURSOR: 칸 스냅 미리보기 + 배치)
# ============================================================
def build_cursor_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    def leq(a, b_):  # a <= b
        return b_not(bs, cmp_op("operator_gt", a, b_))
    def geq(a, b_):  # a >= b
        return b_not(bs, cmp_op("operator_lt", a, b_))
    def grid_index():   # (설치레인-1)*열개수 + 설치열
        rm1 = op("operator_subtract", vrep("설치레인", V_PLACEL), 1)
        rc = op("operator_multiply", rm1, vrep("열개수", V_COLS))
        return op("operator_add", rc, vrep("설치열", V_PLACEC))
    def price_chain():
        # 선택장치 1→설탕기계_가격, 2→쿠키캐논_가격, 3→초코벽_가격, 4→밀크폭탄_가격
        p1 = b_setvar(bs, "현재가격", V_CURPRICE, vrep("설탕기계_가격", V_SFCOST))
        p2 = b_setvar(bs, "현재가격", V_CURPRICE, vrep("쿠키캐논_가격", V_PEACOST))
        p3 = b_setvar(bs, "현재가격", V_CURPRICE, vrep("초코벽_가격", V_NUTCOST))
        p4 = b_setvar(bs, "현재가격", V_CURPRICE, vrep("밀크폭탄_가격", V_CHCOST))
        e3 = cmp_op("operator_equals", vrep("선택장치", V_SEL), 3)
        if3 = b_ifelse(bs, e3, p3, p4)
        e2 = cmp_op("operator_equals", vrep("선택장치", V_SEL), 2)
        if2 = b_ifelse(bs, e2, p2, if3)
        e1 = cmp_op("operator_equals", vrep("선택장치", V_SEL), 1)
        if1 = b_ifelse(bs, e1, p1, if2)
        return if1  # head

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs); gh = b_seteffect(bs, "GHOST", 45)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (gh, bs[gh])])

    # (B) 미리보기 forever
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # 설치열 = round((mouse x - 격자시작X)/격자간격X)+1
    col_div = op("operator_divide", op("operator_subtract", b_mousex(bs), vrep("격자시작X", V_GX)),
                 vrep("격자간격X", V_GXSTEP))
    col_expr = op("operator_add", b_round(bs, col_div), 1)
    set_col = b_setvar(bs, "설치열", V_PLACEC, col_expr)
    col_lt1 = cmp_op("operator_lt", vrep("설치열", V_PLACEC), 1)
    set_col1 = b_setvar(bs, "설치열", V_PLACEC, 1)
    if_col_lo = b_if(bs, col_lt1, set_col1)
    col_gt = cmp_op("operator_gt", vrep("설치열", V_PLACEC), vrep("열개수", V_COLS))
    set_colmax = b_setvar(bs, "설치열", V_PLACEC, vrep("열개수", V_COLS))
    if_col_hi = b_if(bs, col_gt, set_colmax)
    # 설치레인 = round((레인시작Y - mouse y)/레인간격Y)+1
    lane_div = op("operator_divide", op("operator_subtract", vrep("레인시작Y", V_LY), b_mousey(bs)),
                  vrep("레인간격Y", V_LYSTEP))
    lane_expr = op("operator_add", b_round(bs, lane_div), 1)
    set_lane = b_setvar(bs, "설치레인", V_PLACEL, lane_expr)
    lane_lt1 = cmp_op("operator_lt", vrep("설치레인", V_PLACEL), 1)
    set_lane1 = b_setvar(bs, "설치레인", V_PLACEL, 1)
    if_lane_lo = b_if(bs, lane_lt1, set_lane1)
    lane_gt = cmp_op("operator_gt", vrep("설치레인", V_PLACEL), vrep("레인개수", V_ROWS))
    set_lanemax = b_setvar(bs, "설치레인", V_PLACEL, vrep("레인개수", V_ROWS))
    if_lane_hi = b_if(bs, lane_gt, set_lanemax)
    # 설치X/Y = 리스트 item
    set_px = b_setvar(bs, "설치X", V_PLACEX, b_item_of(bs, "열X", L_COLX, vrep("설치열", V_PLACEC)))
    set_py = b_setvar(bs, "설치Y", V_PLACEY, b_item_of(bs, "레인Y", L_LANEY, vrep("설치레인", V_PLACEL)))
    g = b_gotoxy(bs, vrep("설치X", V_PLACEX), vrep("설치Y", V_PLACEY))
    show = b_show(bs)
    # 설탕이 항상 위(front)에 오도록 커서는 front 올리지 않음
    price_head = price_chain()
    # 유효성
    absx = b_mathop(bs, "abs", op("operator_subtract", b_mousex(bs), vrep("설치X", V_PLACEX)))
    halfx = op("operator_divide", vrep("격자간격X", V_GXSTEP), 2)
    c1 = leq(absx, halfx)
    absy = b_mathop(bs, "abs", op("operator_subtract", b_mousey(bs), vrep("설치Y", V_PLACEY)))
    halfy = op("operator_divide", vrep("레인간격Y", V_LYSTEP), 2)
    c2 = leq(absy, halfy)
    c3 = cmp_op("operator_equals", b_item_of(bs, "격자점유", L_CELL, grid_index()), 0)
    c4 = geq(vrep("설탕", V_SUNCUR), vrep("현재가격", V_CURPRICE))
    # 설탕과 겹치면 설치 불가(미리보기도 빨강) — 줍기 우선
    not_on_sun = b_not(bs, b_touching(bs, "설탕"))
    valid = bool_op("operator_and",
                    bool_op("operator_and", bool_op("operator_and", c1, c2), bool_op("operator_and", c3, c4)),
                    not_on_sun)
    green_c = b_seteffect(bs, "COLOR", 0); green_g = b_seteffect(bs, "GHOST", 30)
    chain([(green_c, bs[green_c]), (green_g, bs[green_g])])
    red_c = b_seteffect(bs, "COLOR", 100); red_g = b_seteffect(bs, "GHOST", 55)
    chain([(red_c, bs[red_c]), (red_g, bs[red_g])])
    if_valid = b_ifelse(bs, valid, green_c, red_c)
    # 온-스크립트 체인 (선택장치>0 and 게임상태=1 이면)
    chain([(set_col, bs[set_col]), (if_col_lo, bs[if_col_lo]), (if_col_hi, bs[if_col_hi]),
           (set_lane, bs[set_lane]), (if_lane_lo, bs[if_lane_lo]), (if_lane_hi, bs[if_lane_hi]),
           (set_px, bs[set_px]), (set_py, bs[set_py]), (g, bs[g]), (show, bs[show]),
           (price_head, bs[price_head]), (if_valid, bs[if_valid])])
    sel_pos = cmp_op("operator_gt", vrep("선택장치", V_SEL), 0)
    st_pl = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_on = bool_op("operator_and", sel_pos, st_pl)
    hi2 = b_hide(bs)
    if_on = b_ifelse(bs, c_on, set_col, hi2)

    # (C) 마우스 업 시 설치 — 설탕은 다운에서 수확+설치잠금, 업에서 설치 → 겹침 없음
    # 마우스 업 엣지: 이전마우스=1 and not mousedown
    was_down = cmp_op("operator_equals", vrep("이전마우스", V_PREV_MD), 1)
    not_md = b_not(bs, b_mousedown(bs))
    c_release = bool_op("operator_and", was_down, not_md)
    # 잠금 해제 또는 설치
    clear_lock = b_setvar(bs, "설치잠금", V_PLANTLOCK, 0)
    price_head2 = price_chain()
    sel_pos2 = cmp_op("operator_gt", vrep("선택장치", V_SEL), 0)
    st_pl2 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    absx2 = b_mathop(bs, "abs", op("operator_subtract", b_mousex(bs), vrep("설치X", V_PLACEX)))
    halfx2 = op("operator_divide", vrep("격자간격X", V_GXSTEP), 2)
    cc1 = leq(absx2, halfx2)
    absy2 = b_mathop(bs, "abs", op("operator_subtract", b_mousey(bs), vrep("설치Y", V_PLACEY)))
    halfy2 = op("operator_divide", vrep("레인간격Y", V_LYSTEP), 2)
    cc2 = leq(absy2, halfy2)
    cc3 = cmp_op("operator_equals", b_item_of(bs, "격자점유", L_CELL, grid_index()), 0)
    cc4 = geq(vrep("설탕", V_SUNCUR), vrep("현재가격", V_CURPRICE))
    not_on_sun2 = b_not(bs, b_touching(bs, "설탕"))
    g1 = bool_op("operator_and", sel_pos2, st_pl2)
    g2 = bool_op("operator_and", cc1, cc2)
    g3 = bool_op("operator_and", cc3, cc4)
    can = bool_op("operator_and",
                  bool_op("operator_and", bool_op("operator_and", g1, g2), g3),
                  not_on_sun2)
    neg_price = op("operator_subtract", 0, vrep("현재가격", V_CURPRICE))
    dec_sun = b_changevar(bs, "설탕", V_SUNCUR, neg_price)
    rep_cell = b_replace_item(bs, "격자점유", L_CELL, grid_index(), vrep("선택장치", V_SEL))
    set_pt = b_setvar(bs, "설치타입", V_PLACET, vrep("선택장치", V_SEL))
    sh_pl, sp_pl = b_sound(bs, 0, "plant")
    bc_place = b_broadcast(bs, "장치설치", BR_PLACE)
    chain([(dec_sun, bs[dec_sun]), (rep_cell, bs[rep_cell]), (set_pt, bs[set_pt]),
           (sh_pl, bs[sh_pl]), (sp_pl, bs[sp_pl]), (bc_place, bs[bc_place])])
    # 가격 갱신 후 유효하면 설치 (에러음은 의도적 실패 칸에서만 — 잠금/빈 클릭은 무음)
    if_plant = b_if(bs, can, dec_sun)
    chain([(price_head2, bs[price_head2]), (if_plant, bs[if_plant])])
    locked = cmp_op("operator_equals", vrep("설치잠금", V_PLANTLOCK), 1)
    if_rel = b_ifelse(bs, locked, clear_lock, price_head2)
    if_release = b_if(bs, c_release, if_rel)
    # 이전마우스 갱신
    set_prev1 = b_setvar(bs, "이전마우스", V_PREV_MD, 1)
    set_prev0 = b_setvar(bs, "이전마우스", V_PREV_MD, 0)
    if_prev = b_ifelse(bs, b_mousedown(bs), set_prev1, set_prev0)

    w = b_wait(bs, 0.03)
    chain([(if_on, bs[if_on]), (if_release, bs[if_release]), (if_prev, bs[if_prev]), (w, bs[w])])
    fe = b_forever(bs, if_on)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    add_comment(bs, comments, hb,
        "🧱 마우스를 칸에 자석처럼 스냅해서 미리 보여줘요.\n"
        "빈 칸(격자점유=0)이고 설탕이 가격보다 많고 그리드 안이면 초록(가능), 아니면 빨강(불가).\n"
        "설치는 마우스 버튼을 뗄 때! 설탕을 클릭해 주우면 설치잠금이 걸려 그 클릭으로는 안 심겨요.",
        x=-380, y=200, w=340, h=190)
    return bs, comments

# ============================================================
#  숫자팝업 (NUMBER POPUP: 흰 데미지 / 금 설탕, say 미사용)
# ============================================================
def build_popup_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs); orig0 = b_setvar(bs, "복제됨", V_POP_ISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (orig0, bs[orig0])])

    # (B) 데미지표시 → 자릿수만큼 클론
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["데미지표시", BR_DMG]})
    cond_orig = cmp_op("operator_equals", vrep("복제됨", V_POP_ISC), 0)
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
    pos_m1 = op("operator_subtract", vrep("데미지자리", V_DMGPOS), 1)
    off_left = op("operator_multiply", pos_m1, 14)
    len_m1 = op("operator_subtract", vrep("데미지글자수", V_DMGLEN), 1)
    off_ctr = op("operator_multiply", len_m1, 7)
    off_fin = op("operator_subtract", off_left, off_ctr)
    set_off = b_setvar(bs, "데미지오프셋", V_DMGOFF, off_fin)
    cclone = b_create_clone(bs)
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
    front = b_front(bs); sz = b_setsize(bs, 100)
    k10 = op("operator_multiply", vrep("팝업종류", V_DMGKIND), 10)
    sum1 = op("operator_add", vrep("데미지숫자", V_DMGDIG), k10)
    idx = op("operator_add", sum1, 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(idx)})
    bs[idx]["parent"] = sw
    x_pos = op("operator_add", vrep("데미지표시x", V_DMGX), vrep("데미지오프셋", V_DMGOFF))
    g = b_gotoxy(bs, x_pos, vrep("데미지표시y", V_DMGY))
    clr_gh = b_seteffect(bs, "GHOST", 0); show = b_show(bs)
    ch_y = b_changey(bs, 4); ch_gh = b_changeeffect(bs, "GHOST", 8); w_an = b_wait(bs, 0.02)
    chain([(ch_y, bs[ch_y]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = b_repeat(bs, 12, ch_y)
    del_c = b_delete_clone(bs)
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (front, bs[front]), (sz, bs[sz]),
           (sw, bs[sw]), (g, bs[g]), (clr_gh, bs[clr_gh]), (show, bs[show]),
           (rep_an, bs[rep_an]), (del_c, bs[del_c])])
    return bs, comments

# ============================================================
#  웨이브알림 (WAVE FLAG)
# ============================================================
def build_waveflag_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g = b_gotoxy(bs, 0, 60); sz = b_setsize(bs, 100); front = b_front(bs)
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["웨이브시작", BR_WAVE]})
    show = b_show(bs)
    g0 = b_seteffect(bs, "GHOST", 0); w1 = b_wait(bs, 0.15)
    g40 = b_seteffect(bs, "GHOST", 40); w2 = b_wait(bs, 0.15)
    chain([(g0, bs[g0]), (w1, bs[w1]), (g40, bs[g40]), (w2, bs[w2])])
    rep = b_repeat(bs, 2, g0)
    hi2 = b_hide(bs)
    chain([(hb, bs[hb]), (show, bs[show]), (rep, bs[rep]), (hi2, bs[hi2])])
    return bs, comments

# ============================================================
#  게임오버 (GAME OVER 배너)
# ============================================================
def build_gameover_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g = b_gotoxy(bs, 0, 0); sz = b_setsize(bs, 100); front = b_front(bs)
    rs = b_rotstyle(bs)
    c1 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    wu1 = b_waituntil(bs, c1)
    c0 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    wu2 = b_waituntil(bs, c0)
    sh, sp = b_sound(bs, 0, "lose")
    show = b_show(bs)
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]), (rs, bs[rs]),
           (wu1, bs[wu1]), (wu2, bs[wu2]), (sh, bs[sh]), (sp, bs[sp]), (show, bs[show])])
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

    def load_png(name):
        """assets/gen/{name}.png → work dir. returns (md5, w, h) or None."""
        path = os.path.join(ASSETS, "gen", f"{name}.png")
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            data = f.read()
        m = md5_bytes(data)
        with open(f"{WORK}/{m}.png", "wb") as f:
            f.write(data)
        try:
            from PIL import Image
            with Image.open(path) as im:
                w, h = im.size
        except Exception:
            w = h = 100
        return m, w, h

    def costume_png(file_stem, display_name, fallback_svg, cx=None, cy=None):
        """file_stem: assets/gen/{file_stem}.png ; display_name: Scratch costume name."""
        loaded = load_png(file_stem)
        if loaded:
            m, w, h = loaded
            return {
                "name": display_name, "bitmapResolution": 1, "dataFormat": "png",
                "assetId": m, "md5ext": f"{m}.png",
                "rotationCenterX": cx if cx is not None else w // 2,
                "rotationCenterY": cy if cy is not None else h // 2,
            }, True
        m = save_svg(fallback_svg)
        return {
            "name": display_name, "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": m, "md5ext": f"{m}.svg",
            "rotationCenterX": cx if cx is not None else 30,
            "rotationCenterY": cy if cy is not None else 30,
        }, False

    def pair(stem, name0, name1, fb, cx, cy):
        """Load frame0/frame1 (stem_0 / stem_1), fall back to stem or SVG."""
        c0, ok0 = costume_png(f"{stem}_0", name0, fb, cx, cy)
        if not ok0:
            c0, _ = costume_png(stem, name0, fb, cx, cy)
        c1, ok1 = costume_png(f"{stem}_1", name1, fb, cx, cy)
        if not ok1:
            c1, _ = costume_png(stem, name1, fb, cx, cy)
        return c0, c1

    # 쿠키런 톤 PNG 에셋 + 2프레임 애니 (없으면 SVG 폴백)
    c_bg, _ = costume_png("bg", "공장바닥", BG_SVG, 240, 180)
    c_house0, c_house1 = pair("warehouse", "창고", "창고2", HOUSE_SVG, 35, 48)
    c_z1a, c_z1b = pair("ant_basic", "기본개미", "기본개미2", ZOMBIE1_SVG, 28, 28)
    c_z2a, c_z2b = pair("ant_helmet", "헬멧개미", "헬멧개미2", ZOMBIE2_SVG, 28, 28)
    c_z3a, c_z3b = pair("ant_fast", "빠른개미", "빠른개미2", ZOMBIE3_SVG, 28, 28)
    c_z1k0, _ = costume_png("ant_basic_atk0", "기본개미공", ZOMBIE1_SVG, 28, 28)
    c_z1k1, _ = costume_png("ant_basic_atk1", "기본개미공2", ZOMBIE1_SVG, 28, 28)
    c_z2k0, _ = costume_png("ant_helmet_atk0", "헬멧개미공", ZOMBIE2_SVG, 28, 28)
    c_z2k1, _ = costume_png("ant_helmet_atk1", "헬멧개미공2", ZOMBIE2_SVG, 28, 28)
    c_z3k0, _ = costume_png("ant_fast_atk0", "빠른개미공", ZOMBIE3_SVG, 28, 28)
    c_z3k1, _ = costume_png("ant_fast_atk1", "빠른개미공2", ZOMBIE3_SVG, 28, 28)
    c_zb, _ = costume_png("ant_boom", "개미터짐", ZOMBIE_BOOM_SVG, 28, 28)
    c_pea0, c_pea1 = pair("cookie_bullet", "쿠키알", "쿠키알2", PEA_SVG, 14, 14)
    c_sf0, c_sf1 = pair("sugar_machine", "설탕기계", "설탕기계2", SUNFLOWER_SVG, 30, 35)
    c_ps0, c_ps1 = pair("cookie_cannon", "쿠키캐논", "쿠키캐논2", PEASHOOTER_SVG, 34, 34)
    c_nut0, c_nut1 = pair("choco_wall", "초코벽", "초코벽2", WALNUT_SVG, 32, 36)
    c_nutd1, _ = costume_png("choco_wall_dmg", "초코벽금", WALNUT_SVG, 32, 36)
    c_nutd2, _ = costume_png("choco_wall_dmg2", "초코벽금2", WALNUT_SVG, 32, 36)
    c_ch0, c_ch1 = pair("milk_bomb", "밀크폭탄", "밀크폭탄2", CHERRY_SVG, 32, 36)
    c_pb, _ = costume_png("plant_boom", "장치터짐", PLANT_BOOM_SVG, 32, 36)
    c_mow0, c_mow1 = pair("broom", "빗자루", "빗자루2", MOWER_SVG, 28, 20)
    c_sun0, c_sun1 = pair("sugar", "설탕", "설탕2", SUN_SVG, 20, 20)
    c_pal, _ = costume_png("palette", "팔레트", PALETTE_SVG, 80, 30)
    cur_md5   = save_svg(CURSOR_SVG)
    wf_md5    = save_svg(WAVEFLAG_SVG)
    rs_md5    = save_svg(RESULT_SVG)
    wd_md5    = [save_svg(s) for s in WHITE_DIGITS]
    gd_md5    = [save_svg(s) for s in GOLD_DIGITS]

    def save_wav(samples):
        b = _wav_bytes(samples)
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    plant_s, plant_n     = save_wav(synth_plant())
    error_s, error_n     = save_wav(synth_error())
    pea_s, pea_n         = save_wav(synth_pea())
    cherry_s, cherry_n   = save_wav(synth_cherry())
    sun_s, sun_n         = save_wav(synth_sun())
    chomp_s, chomp_n     = save_wav(synth_chomp())
    zdie_s, zdie_n       = save_wav(synth_zombiedie())
    mower_s, mower_n     = save_wav(synth_mower())
    wave_s, wave_n       = save_wav(synth_wave())
    groan_s, groan_n     = save_wav(synth_groan())
    thud_s, thud_n       = save_wav(synth_thud())
    lose_s, lose_n       = save_wav(synth_lose())

    def snd(name, md5, n):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "",
                "rate": SND_RATE, "sampleCount": n, "md5ext": f"{md5}.wav"}

    # BGM: 사용자 제공 mp3 바이너리 그대로 (재인코딩 금지)
    BGM_SRC = os.path.join(ASSETS, "bgm.mp3")
    with open(BGM_SRC, "rb") as f:
        bgm_bytes = f.read()
    bgm_md5 = md5_bytes(bgm_bytes)
    with open(f"{WORK}/{bgm_md5}.mp3", "wb") as f:
        f.write(bgm_bytes)
    BGM_RATE = 48000
    BGM_SAMPLES = int(191 * BGM_RATE)  # ≈191초 (afinfo 기준)

    def S_bgm():
        return {"name": "bgm", "assetId": bgm_md5, "dataFormat": "mp3", "format": "",
                "rate": BGM_RATE, "sampleCount": BGM_SAMPLES, "md5ext": f"{bgm_md5}.mp3"}

    stage_blocks, stage_cmt = build_stage_blocks()
    house_blocks, house_cmt = build_house_blocks()
    z_blocks,     z_cmt     = build_zombie_blocks()
    pea_blocks,   pea_cmt   = build_pea_blocks()
    pl_blocks,    pl_cmt    = build_plant_blocks()
    mow_blocks,   mow_cmt   = build_mower_blocks()
    sun_blocks,   sun_cmt   = build_sun_blocks()
    palb_blocks,  palb_cmt  = build_palette_blocks()
    cur_blocks,   cur_cmt   = build_cursor_blocks()
    pop_blocks,   pop_cmt   = build_popup_blocks()
    wf_blocks,    wf_cmt    = build_waveflag_blocks()
    go_blocks,    go_cmt    = build_gameover_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 50 (초반 여유 밸런스)
            V_SUN0: ["기본설탕", 100], V_SKYSUN: ["하늘설탕량", 25], V_SUNPROD: ["설탕기계생산량", 25],
            V_SUNINT: ["설탕기계간격", 6], V_SKYINT: ["하늘설탕간격", 8], V_AUTOPICK: ["자동수확대기", 6],
            V_KILLSUN: ["처치설탕", 5], V_WAVESUN: ["웨이브클리어설탕", 20], V_LIFEMAX: ["시작목숨", 3],
            V_BASEZ: ["기본개미수", 5], V_ZINC: ["웨이브당개미증가", 3], V_SPGAP: ["개미간격", 2.6],
            V_HPINC: ["웨이브체력증가", 5], V_SPINC: ["웨이브속도증가", 0.12], V_FIRSTW: ["첫웨이브대기", 9],
            V_WAVEW: ["웨이브사이대기", 3], V_UNCONE: ["헬멧해금웨이브", 2], V_UNFAST: ["빠른개미해금웨이브", 3],
            V_REACH: ["도달반경", 15],
            V_SFCOST: ["설탕기계_가격", 15], V_SFHP: ["설탕기계_체력", 5], V_PEACOST: ["쿠키캐논_가격", 25],
            V_PEAHP: ["쿠키캐논_체력", 5], V_PEADMG: ["쿠키캐논_공격력", 1], V_PEAGAP: ["쿠키캐논_간격", 1.3],
            V_PEASPD: ["쿠키속도", 10], V_PEAR: ["쿠키반경", 18], V_NUTCOST: ["초코벽_가격", 20],
            V_NUTHP: ["초코벽_체력", 30], V_CHCOST: ["밀크폭탄_가격", 50], V_CHHP: ["밀크폭탄_체력", 1],
            V_CHDMG: ["밀크폭탄_데미지", 28], V_CHR: ["밀크폭탄_반경", 160], V_CHFUSE: ["밀크폭탄_퓨즈", 0.7],
            V_Z1HP: ["기본개미_체력", 8], V_Z1SP: ["기본개미_속도", 0.85], V_BITE: ["개미갉기력", 0.45],
            V_Z2HP: ["헬멧개미_체력", 18], V_Z2SP: ["헬멧개미_속도", 0.75], V_Z3HP: ["빠른개미_체력", 6],
            V_Z3SP: ["빠른개미_속도", 1.5],
            V_MOWSPD: ["빗자루속도", 12], V_GX: ["격자시작X", -160], V_GXSTEP: ["격자간격X", 40],
            V_LY: ["레인시작Y", 110], V_LYSTEP: ["레인간격Y", 55], V_COLS: ["열개수", 9], V_ROWS: ["레인개수", 5],
            V_ZSPAWNX: ["개미생성X", 250], V_REACHH: ["개미도달X", -190],
            V_BGMVOL: ["브금볼륨", 55],
            # 진행 39
            V_STATE: ["게임상태", 1], V_WAVE: ["웨이브", 1], V_SCORE: ["점수", 0], V_SUNCUR: ["설탕", 100],
            V_LIFE: ["목숨", 3], V_ALIVE: ["적수", 0], V_SPAWNN: ["스폰카운트", 0], V_SEL: ["선택장치", 0],
            V_UNCONEF: ["헬멧해금", 0], V_UNFASTF: ["빠른해금", 0], V_SPLANE: ["생성레인", 1],
            V_SPTYPE: ["생성타입", 1], V_PLACEX: ["설치X", 0], V_PLACEY: ["설치Y", 0], V_PLACET: ["설치타입", 0],
            V_PLACEL: ["설치레인", 1], V_PLACEC: ["설치열", 1], V_AIMLANE: ["조준레인", 0], V_AIMTX: ["조준탑X", 0],
            V_AIMOK: ["조준적있음", 0], V_FIREX: ["발사X", 0], V_FIREY: ["발사Y", 0], V_FIRELN: ["발사레인", 1],
            V_BOOMX: ["폭발X", 0], V_BOOMY: ["폭발Y", 0], V_BOOMD: ["폭발데미지", 0], V_BOOMR: ["폭발반경", 0],
            V_SUNKIND: ["설탕종류", 0], V_SUNX: ["설탕X", 0], V_SUNY: ["설탕Y", 0], V_MOWLANE: ["작동레인", 0],
            V_DMGVAL: ["데미지표시값", 0], V_DMGX: ["데미지표시x", 0], V_DMGY: ["데미지표시y", 0],
            V_DMGKIND: ["팝업종류", 0], V_DMGDIG: ["데미지숫자", 0], V_DMGOFF: ["데미지오프셋", 0],
            V_DMGLEN: ["데미지글자수", 0], V_DMGPOS: ["데미지자리", 0],
            # 빌더 헬퍼 4
            V_I: ["i", 1], V_CURPRICE: ["현재가격", 0],
            V_PLANTLOCK: ["설치잠금", 0], V_PREV_MD: ["이전마우스", 0],
        },
        "lists": {
            L_COLX: ["열X", []], L_LANEY: ["레인Y", []],
            L_CELL: ["격자점유", []], L_MOWER: ["빗자루사용", []],
        },
        "broadcasts": {
            BR_START: "게임시작", BR_WAVE: "웨이브시작", BR_SPAWN: "개미생성", BR_LANE: "개미레인확인",
            BR_FIRE: "쿠키발사", BR_HIT: "타격", BR_PLACE: "장치설치", BR_SUN: "설탕생성",
            BR_DMG: "데미지표시", BR_MOW: "빗자루작동", BR_HOUSE: "창고피격", BR_OVER: "게임오버",
        },
        "blocks": stage_blocks, "comments": stage_cmt,
        "currentCostume": 0,
        "costumes": [c_bg],
        "sounds": [snd("wave", wave_s, wave_n), snd("groan", groan_s, groan_n), S_bgm()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    house = {
        "isStage": False, "name": "창고",
        "variables": {V_HS_ANIM: ["애니", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": house_blocks, "comments": house_cmt,
        "currentCostume": 0,
        "costumes": [c_house0, c_house1],
        "sounds": [snd("thud", thud_s, thud_n)],
        "volume": 100, "layerOrder": 4, "visible": True,
        "x": -220, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    zombie = {
        "isStage": False, "name": "개미",
        "variables": {V_Z_ISC: ["복제됨", 0], V_Z_TYPE: ["내타입", 1], V_Z_HP: ["내체력", 5],
                      V_Z_SPD: ["내속도", 0.6], V_Z_LANE: ["내레인", 1], V_Z_ANIM: ["애니", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": z_blocks, "comments": z_cmt,
        "currentCostume": 0,
        "costumes": [c_z1a, c_z1b, c_z2a, c_z2b, c_z3a, c_z3b,
                     c_z1k0, c_z1k1, c_z2k0, c_z2k1, c_z3k0, c_z3k1, c_zb],
        "sounds": [snd("chomp", chomp_s, chomp_n), snd("zdie", zdie_s, zdie_n)],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 250, "y": 110, "size": 55, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    pea = {
        "isStage": False, "name": "쿠키탄",
        "variables": {V_PB_ISC: ["복제됨", 0], V_PB_LANE: ["내레인", 1], V_PB_ANIM: ["애니", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": pea_blocks, "comments": pea_cmt,
        "currentCostume": 0,
        "costumes": [c_pea0, c_pea1],
        "sounds": [],
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 0, "size": 50, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    plant = {
        "isStage": False, "name": "장치",
        "variables": {V_PL_ISC: ["복제됨", 0], V_PL_TYPE: ["내타입", 1], V_PL_HP: ["내체력", 4],
                      V_PL_LANE: ["내레인", 1], V_PL_COL: ["내열", 1], V_PL_CD: ["발사쿨", 0],
                      V_PL_FUSE: ["퓨즈", 0], V_PL_ANIM: ["애니", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": pl_blocks, "comments": pl_cmt,
        "currentCostume": 0,
        "costumes": [c_sf0, c_sf1, c_ps0, c_ps1, c_nut0, c_nut1, c_nutd1, c_nutd2,
                     c_ch0, c_ch1, c_pb],
        "sounds": [snd("pea", pea_s, pea_n), snd("cherry", cherry_s, cherry_n)],
        "volume": 100, "layerOrder": 5, "visible": False,
        "x": 0, "y": 0, "size": 58, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    mower = {
        "isStage": False, "name": "빗자루",
        "variables": {V_MO_ISC: ["복제됨", 0], V_MO_LANE: ["내레인", 1], V_MO_USED: ["사용됨", 0],
                      V_MO_RUN: ["작동중", 0], V_MO_ANIM: ["애니", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": mow_blocks, "comments": mow_cmt,
        "currentCostume": 0,
        "costumes": [c_mow0, c_mow1],
        "sounds": [snd("mower", mower_s, mower_n)],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": -200, "y": 110, "size": 48, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    sun = {
        "isStage": False, "name": "설탕",
        "variables": {V_SU_ISC: ["복제됨", 0], V_SU_KIND: ["내종류", 0], V_SU_LIFE: ["수명", 0],
                      V_SU_ANIM: ["애니", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": sun_blocks, "comments": sun_cmt,
        "currentCostume": 0,
        "costumes": [c_sun0, c_sun1],
        "sounds": [snd("sun", sun_s, sun_n)],
        "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 55, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    palette = {
        "isStage": False, "name": "메뉴판",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": palb_blocks, "comments": palb_cmt,
        "currentCostume": 0,
        "costumes": [c_pal],
        "sounds": [],
        "volume": 100, "layerOrder": 9, "visible": True,
        "x": -65, "y": 150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    cursor = {
        "isStage": False, "name": "설치커서",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": cur_blocks, "comments": cur_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "칸", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": cur_md5, "md5ext": f"{cur_md5}.svg", "rotationCenterX": 22, "rotationCenterY": 28}],
        "sounds": [snd("plant", plant_s, plant_n), snd("error", error_s, error_n)],
        # 설탕(layer 8)보다 아래 → 설탕 클릭이 커서에 가로채이지 않음
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
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
        "volume": 100, "layerOrder": 11, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    waveflag = {
        "isStage": False, "name": "웨이브알림",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": wf_blocks, "comments": wf_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "알림", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": wf_md5, "md5ext": f"{wf_md5}.svg", "rotationCenterX": 150, "rotationCenterY": 40}],
        "sounds": [],
        "volume": 100, "layerOrder": 12, "visible": False,
        "x": 0, "y": 60, "size": 100, "direction": 90,
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
        "sounds": [snd("lose", lose_s, lose_n)],
        "volume": 100, "layerOrder": 13, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # ---- 모니터: 설탕 / 웨이브 / 점수 / 목숨 (튜닝 변수는 숨김) ----
    monitors = [
        {"id": V_SUNCUR, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "설탕"}, "spriteName": None,
         "value": 50, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 999, "isDiscrete": True},
        {"id": V_WAVE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "웨이브"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_LIFE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "목숨"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 10, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, house, zombie, pea, plant, mower, sun, palette, cursor,
                    popup, waveflag, gameover],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "cookies-vs-ants-builder"}
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
    for nm, b in [("stage", stage_blocks), ("house", house_blocks), ("zombie", z_blocks),
                  ("pea", pea_blocks), ("plant", pl_blocks), ("mower", mow_blocks),
                  ("sun", sun_blocks), ("palette", palb_blocks), ("cursor", cur_blocks),
                  ("popup", pop_blocks), ("waveflag", wf_blocks), ("gameover", go_blocks)]:
        print(f"  {nm:9s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
