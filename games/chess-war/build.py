#!/usr/bin/env python3
"""체스 대전쟁 (chess-war) — 가로 라인 배틀 전쟁 게임 (하얀 군단 vs 검은 군단).

화면 왼쪽 하얀 킹 vs 오른쪽 검은 킹. 하단 5칸 버튼으로 폰·비숍·나이트·룩·퀸(체스 이름·
역할의 판타지 전사)을 소환하면 유닛이 킹 앞에서 나와 자동으로 오른쪽으로 전진, 적을 만나면
멈춰 자동 전투(폰=근접 물량 / 비숍=원거리 단일 / 나이트=강한 근접 / 룩=포격 광역 /
퀸=단일+광역 이중 공격). 골드는 초당 자동으로 쌓이고, 그 골드로 유닛을 소환한다. 검은 킹
체력을 0으로 만들면(체크메이트) 스테이지 클리어 → 강화 택1(초당골드+/공격력+/체력+/킹수리)
→ 다음 스테이지. 스테이지가 오를수록 검은 군단은 지수(곱하기)로 강해진다(적 = 기본 ×
적성장배율^(스테이지−1)). 하얀 킹 체력이 0이 되면 GAME OVER. 점수 = 도달한 스테이지.

베이스: games/castle-defense/build.py
  - 한글 튜닝 변수 일괄 초기화(매직넘버 0) / 리스트 병렬 배열(add·replace·item·length·
    deleteall 만; insert/mid-delete 금지) / 렌더 전용 클론 + 복제됨 가드 / 플로팅 숫자
    (say 미사용, 흰=데미지/금=골드) / 강화 택1 패널 / 게임오버 배너 / 전용 합성 효과음
    (_wav_bytes·synth_*) / add_comment 가이드 투어.

★ 모든 조절 값(튜닝 84개)을 한글 전역 변수로만 노출, 코드 어디서도 매직넘버를 쓰지 않는다.
  ★ 퀸/검은퀸(타입5)은 한 쿨에 단일공격 + 광역공격을 둘 다 호출(이중 공격).
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "체스_대전쟁.sb3")

# ============================================================
#  효과음 합성 (전용 사운드 10종) — 결정적 생성
# ============================================================
SND_RATE = 11025

def _wav_bytes(samples, rate=SND_RATE):
    """float 샘플(-1..1) 리스트 → 16-bit PCM mono WAV 바이트 (결정적)."""
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_summon(rate=SND_RATE):
    """유닛 소환 — 밝은 '뿅' 상승 처프 (400→900Hz, 0.08초)."""
    N = int(rate * 0.08); out = []
    for i in range(N):
        t = i / rate
        f = 400 + 500 * (t / 0.08)
        env = math.exp(-t * 12) * min(1.0, t / 0.006)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.5)
    return out

def synth_error(rate=SND_RATE):
    """소환 실패 — 낮은 '붕' 버저 (150Hz 사각파, 0.15초)."""
    N = int(rate * 0.15); out = []
    for i in range(N):
        t = i / rate
        sq = 1.0 if math.sin(2 * math.pi * 150 * t) > 0 else -1.0
        env = math.exp(-t * 7)
        out.append(sq * env * 0.4)
    return out

def synth_clash(rate=SND_RATE):
    """근접 교전 — 짧고 가벼운 칼 부딪힘 '챙' (2kHz 클릭 + 빠른 감쇠, 0.05초)."""
    N = int(rate * 0.05); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 60)
        s = math.sin(2 * math.pi * 2000 * t) + 0.5 * math.sin(2 * math.pi * 3200 * t)
        out.append(s * env * 0.4)
    return out

def synth_cannon(rate=SND_RATE):
    """룩·퀸 포격 — 둔탁한 저음 '쿵' (노이즈버스트 + 60Hz thump, 0.22초). 결정적."""
    N = int(rate * 0.22); out = []
    rng = random.Random(20260707)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 13)
        white = rng.random() * 2 - 1
        lp = lp + 0.40 * (white - lp)
        thump = math.sin(2 * math.pi * (55 + 35 * math.exp(-t * 22)) * t)
        s = (lp * 0.5 + thump * 0.85) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_death(rate=SND_RATE):
    """유닛 처치 — '펑' 폭죽 (노이즈 + 저음 thump, 0.12초). 결정적."""
    N = int(rate * 0.12); out = []
    rng = random.Random(20260630)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 20)
        white = rng.random() * 2 - 1
        lp = lp + 0.45 * (white - lp)
        thump = math.sin(2 * math.pi * (70 + 50 * math.exp(-t * 26)) * t)
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

def synth_kinghit(rate=SND_RATE):
    """킹 피격 — 거친 저음 충격 (120Hz 사각파 하강, 0.2초)."""
    N = int(rate * 0.20); out = []
    for i in range(N):
        t = i / rate
        f = 120 + 60 * math.exp(-t * 8)
        sq = 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0
        env = math.exp(-t * 10)
        out.append(sq * env * 0.45)
    return out

def synth_break(rate=SND_RATE):
    """킹 함락 — 크게 무너지는 파열 (긴 노이즈 + 저음 thump, 0.5초). 결정적."""
    N = int(rate * 0.50); out = []
    rng = random.Random(20260618)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = min(1.0, t / 0.02) * math.exp(-t * 4.5)
        white = rng.random() * 2 - 1
        lp = lp + 0.18 * (white - lp)
        thump = math.sin(2 * math.pi * (45 + 30 * math.exp(-t * 6)) * t)
        s = (lp * 0.8 + thump * 0.7) * env
        out.append(max(-1, min(1, s)))
    return out

def synth_horn(rate=SND_RATE):
    """스테이지 시작 뿔피리 — 묵직한 톱니파 (180Hz, 0.4초, 느린 어택)."""
    N = int(rate * 0.40); out = []
    for i in range(N):
        t = i / rate
        ph = (180 * t) % 1.0
        saw = 2 * ph - 1
        atk = min(1.0, t / 0.08)
        env = atk * math.exp(-t * 3.0)
        out.append(saw * env * 0.4)
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

# -------- 배경: 옅은 파스텔 하늘 + 워시톤 체스판 + 은은한 레인선 (레인Y=-50 → svgY=230) --------
# 플레이테스트 #3: 배경 채도·명도를 크게 낮춰(파스텔/워시) 유닛·킹·버튼이 또렷하게 대비되도록.
CHECKER = []
for ti, ty in enumerate(range(200, 360, 26)):
    for tj, tx in enumerate(range(0, 480, 26)):
        light = (ti + tj) % 2 == 0
        shade = "#F1EBDD" if light else "#E1D8C4"   # 아주 옅은 크림/베이지(대비 최소)
        CHECKER.append(f'<rect x="{tx}" y="{ty}" width="26" height="26" fill="{shade}"/>')
CHECKER_SVG = "\n    ".join(CHECKER)
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#DCEAF6"/>
      <stop offset="1" stop-color="#EFF6FC"/>
    </linearGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <circle cx="70" cy="58" r="24" fill="#FFFFFF" opacity="0.6"/>
  <circle cx="100" cy="64" r="20" fill="#FFFFFF" opacity="0.6"/>
  <circle cx="398" cy="46" r="18" fill="#FFFFFF" opacity="0.55"/>
  <rect x="0" y="200" width="480" height="160" fill="#EAE2D0"/>
  <g opacity="0.85">
    {CHECKER_SVG}
  </g>
  <line x1="0" y1="230" x2="480" y2="230" stroke="#B7A98A" stroke-width="2" opacity="0.35"/>
  <rect x="4" y="4" width="472" height="352" rx="10" fill="none" stroke="#C7BDA4" stroke-width="4" opacity="0.35"/>
</svg>"""

# -------- 하얀 킹 (왕관·하얀 로브·검) --------
KING_WHITE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="92" viewBox="0 0 80 92">
  <ellipse cx="40" cy="87" rx="28" ry="5" fill="#000000" opacity="0.25"/>
  <polygon points="20,84 26,44 54,44 60,84" fill="#EDEDED" stroke="#9E9E9E" stroke-width="2"/>
  <rect x="24" y="52" width="32" height="8" fill="#C9A227"/>
  <ellipse cx="40" cy="34" rx="13" ry="14" fill="#F4D6B0" stroke="#B98A5E" stroke-width="2"/>
  <rect x="30" y="42" width="20" height="6" fill="#D8B98A"/>
  <path d="M25 24 L28 12 L34 20 L40 8 L46 20 L52 12 L55 24 Z" fill="#FFD24A" stroke="#B8860B" stroke-width="1.5"/>
  <circle cx="40" cy="6" r="2.6" fill="#FFF176"/>
  <line x1="63" y1="80" x2="63" y2="40" stroke="#BDBDBD" stroke-width="4"/>
  <polygon points="63,38 66,44 60,44" fill="#ECEFF1"/>
  <rect x="58" y="58" width="10" height="4" rx="1" fill="#8D6E63"/>
</svg>"""

# -------- 검은 킹 (왕관·검은 로브) --------
KING_BLACK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="80" height="92" viewBox="0 0 80 92">
  <ellipse cx="40" cy="87" rx="28" ry="5" fill="#000000" opacity="0.3"/>
  <polygon points="20,84 26,44 54,44 60,84" fill="#3A3A46" stroke="#1A1A22" stroke-width="2"/>
  <rect x="24" y="52" width="32" height="8" fill="#8B0000"/>
  <ellipse cx="40" cy="34" rx="13" ry="14" fill="#7E9B6B" stroke="#3B4B2A" stroke-width="2"/>
  <rect x="30" y="42" width="20" height="6" fill="#5C7148"/>
  <path d="M25 24 L28 12 L34 20 L40 8 L46 20 L52 12 L55 24 Z" fill="#5A5A66" stroke="#222" stroke-width="1.5"/>
  <circle cx="40" cy="6" r="2.6" fill="#B0BEC5"/>
  <line x1="17" y1="80" x2="17" y2="40" stroke="#37474F" stroke-width="4"/>
  <polygon points="17,38 20,44 14,44" fill="#546E7A"/>
</svg>"""

# -------- 하얀 군단 (오른쪽 → 바라봄) --------
PAWN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="55" rx="12" ry="3" fill="#000000" opacity="0.22"/>
  <ellipse cx="26" cy="24" rx="8" ry="9" fill="#F4D6B0" stroke="#B98A5E" stroke-width="1.5"/>
  <rect x="19" y="30" width="16" height="18" rx="4" fill="#E8E8E8" stroke="#9E9E9E" stroke-width="2"/>
  <rect x="12" y="30" width="9" height="16" rx="3" fill="#CFD8DC" stroke="#607D8B" stroke-width="1.5"/>
  <line x1="40" y1="38" x2="40" y2="14" stroke="#BDBDBD" stroke-width="3"/>
  <polygon points="40,12 43,17 37,17" fill="#ECEFF1"/>
  <rect x="34" y="36" width="12" height="4" rx="1" fill="#8D6E63"/>
</svg>"""

BISHOP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="55" rx="12" ry="3" fill="#000000" opacity="0.22"/>
  <polygon points="18,52 30,24 42,52" fill="#F2F2F2" stroke="#B0B0B0" stroke-width="2"/>
  <ellipse cx="30" cy="22" rx="8" ry="9" fill="#F4D6B0" stroke="#B98A5E" stroke-width="1.5"/>
  <polygon points="23,16 37,16 30,3" fill="#E0E0E0" stroke="#9E9E9E" stroke-width="1.5"/>
  <circle cx="30" cy="4" r="2.4" fill="#FFF176"/>
  <line x1="45" y1="50" x2="45" y2="14" stroke="#C9A227" stroke-width="3"/>
  <circle cx="45" cy="12" r="5" fill="#FFF3C4" stroke="#C9A227" stroke-width="1.5"/>
  <circle cx="43.5" cy="10.5" r="1.6" fill="#FFFFFF"/>
</svg>"""

KNIGHT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="56" rx="15" ry="3" fill="#000000" opacity="0.26"/>
  <ellipse cx="22" cy="46" rx="14" ry="8" fill="#E0E0E0" stroke="#9E9E9E" stroke-width="2"/>
  <rect x="16" y="30" width="18" height="18" rx="4" fill="#CFD8DC" stroke="#607D8B" stroke-width="2"/>
  <ellipse cx="27" cy="20" rx="10" ry="11" fill="#ECEFF1" stroke="#607D8B" stroke-width="2.5"/>
  <rect x="22" y="17" width="12" height="5" fill="#90A4AE"/>
  <polygon points="30,10 34,14 26,14" fill="#FF7043"/>
  <line x1="44" y1="42" x2="44" y2="8" stroke="#B0BEC5" stroke-width="4"/>
  <polygon points="44,6 48,13 40,13" fill="#ECEFF1"/>
</svg>"""

ROOK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="56" rx="16" ry="3" fill="#000000" opacity="0.28"/>
  <rect x="14" y="40" width="30" height="16" rx="3" fill="#CFD8DC" stroke="#607D8B" stroke-width="2"/>
  <rect x="18" y="24" width="22" height="18" fill="#E0E0E0" stroke="#9E9E9E" stroke-width="2"/>
  <rect x="18" y="20" width="5" height="8" fill="#E0E0E0" stroke="#9E9E9E" stroke-width="1.5"/>
  <rect x="27" y="20" width="5" height="8" fill="#E0E0E0" stroke="#9E9E9E" stroke-width="1.5"/>
  <rect x="36" y="20" width="5" height="8" fill="#E0E0E0" stroke="#9E9E9E" stroke-width="1.5"/>
  <circle cx="48" cy="30" r="8" fill="#455A64" stroke="#263238" stroke-width="2"/>
  <ellipse cx="55" cy="30" rx="3" ry="5" fill="#263238"/>
  <circle cx="20" cy="56" r="4" fill="#37474F"/>
  <circle cx="38" cy="56" r="4" fill="#37474F"/>
</svg>"""

QUEEN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="56" rx="15" ry="3" fill="#000000" opacity="0.26"/>
  <circle cx="30" cy="30" r="20" fill="#FFF3C4" opacity="0.25"/>
  <polygon points="18,52 30,22 42,52" fill="#F7F0FF" stroke="#B39DDB" stroke-width="2"/>
  <ellipse cx="30" cy="20" rx="8" ry="9" fill="#F4D6B0" stroke="#B98A5E" stroke-width="1.5"/>
  <path d="M22 14 L23 4 L27 11 L30 2 L33 11 L37 4 L38 14 Z" fill="#FFD24A" stroke="#B8860B" stroke-width="1.5"/>
  <circle cx="23" cy="4" r="1.8" fill="#EC407A"/>
  <circle cx="30" cy="2" r="1.8" fill="#42A5F5"/>
  <circle cx="37" cy="4" r="1.8" fill="#66BB6A"/>
  <line x1="45" y1="50" x2="45" y2="14" stroke="#C9A227" stroke-width="3"/>
  <polygon points="{star}" fill="#FFF176" stroke="#C9A227" stroke-width="0.8"/>
</svg>""".replace("{star}", _star_pts(45, 12, 6, 2.5, 5, rot=-1.571))

# -------- 검은 군단 (왼쪽 ← 바라봄) --------
BPAWN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="55" rx="12" ry="3" fill="#000000" opacity="0.25"/>
  <ellipse cx="34" cy="24" rx="8" ry="9" fill="#8BAF6E" stroke="#33691E" stroke-width="1.5"/>
  <rect x="25" y="30" width="16" height="18" rx="4" fill="#3A3A46" stroke="#1A1A22" stroke-width="2"/>
  <rect x="39" y="30" width="9" height="16" rx="3" fill="#4E5B62" stroke="#263238" stroke-width="1.5"/>
  <line x1="20" y1="38" x2="20" y2="14" stroke="#455A64" stroke-width="3"/>
  <polygon points="20,12 23,17 17,17" fill="#607D8B"/>
</svg>"""

BBISHOP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="55" rx="12" ry="3" fill="#000000" opacity="0.25"/>
  <polygon points="18,52 30,24 42,52" fill="#33333E" stroke="#15151C" stroke-width="2"/>
  <ellipse cx="30" cy="22" rx="8" ry="9" fill="#8BAF6E" stroke="#33691E" stroke-width="1.5"/>
  <polygon points="23,16 37,16 30,3" fill="#4A4A57" stroke="#222" stroke-width="1.5"/>
  <circle cx="30" cy="4" r="2.4" fill="#9575CD"/>
  <line x1="15" y1="50" x2="15" y2="14" stroke="#5D4037" stroke-width="3"/>
  <circle cx="15" cy="12" r="5" fill="#7E57C2" stroke="#4527A0" stroke-width="1.5"/>
</svg>"""

BKNIGHT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="56" rx="15" ry="3" fill="#000000" opacity="0.3"/>
  <ellipse cx="38" cy="46" rx="14" ry="8" fill="#3A3A46" stroke="#15151C" stroke-width="2"/>
  <rect x="26" y="30" width="18" height="18" rx="4" fill="#4E5B62" stroke="#263238" stroke-width="2"/>
  <ellipse cx="33" cy="20" rx="10" ry="11" fill="#37414A" stroke="#15151C" stroke-width="2.5"/>
  <rect x="26" y="17" width="12" height="5" fill="#607D8B"/>
  <polygon points="30,10 34,14 26,14" fill="#D32F2F"/>
  <line x1="16" y1="42" x2="16" y2="8" stroke="#455A64" stroke-width="4"/>
  <polygon points="16,6 20,13 12,13" fill="#607D8B"/>
</svg>"""

BROOK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="56" rx="16" ry="3" fill="#000000" opacity="0.3"/>
  <rect x="16" y="40" width="30" height="16" rx="3" fill="#3A3A46" stroke="#15151C" stroke-width="2"/>
  <rect x="20" y="24" width="22" height="18" fill="#4A4A57" stroke="#222" stroke-width="2"/>
  <rect x="20" y="20" width="5" height="8" fill="#4A4A57" stroke="#222" stroke-width="1.5"/>
  <rect x="28" y="20" width="5" height="8" fill="#4A4A57" stroke="#222" stroke-width="1.5"/>
  <rect x="37" y="20" width="5" height="8" fill="#4A4A57" stroke="#222" stroke-width="1.5"/>
  <circle cx="12" cy="30" r="8" fill="#263238" stroke="#000" stroke-width="2"/>
  <ellipse cx="5" cy="30" rx="3" ry="5" fill="#000000"/>
  <circle cx="22" cy="56" r="4" fill="#15151C"/>
  <circle cx="40" cy="56" r="4" fill="#15151C"/>
</svg>"""

BQUEEN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <ellipse cx="30" cy="56" rx="15" ry="3" fill="#000000" opacity="0.3"/>
  <circle cx="30" cy="30" r="20" fill="#8B0000" opacity="0.25"/>
  <polygon points="18,52 30,22 42,52" fill="#2A2A34" stroke="#15151C" stroke-width="2"/>
  <ellipse cx="30" cy="20" rx="8" ry="9" fill="#8BAF6E" stroke="#33691E" stroke-width="1.5"/>
  <path d="M22 14 L23 4 L27 11 L30 2 L33 11 L37 4 L38 14 Z" fill="#6A1B9A" stroke="#38006B" stroke-width="1.5"/>
  <circle cx="23" cy="4" r="1.8" fill="#EF5350"/>
  <circle cx="30" cy="2" r="1.8" fill="#EF5350"/>
  <circle cx="37" cy="4" r="1.8" fill="#EF5350"/>
  <line x1="15" y1="50" x2="15" y2="14" stroke="#5D4037" stroke-width="3"/>
  <polygon points="{star}" fill="#CE93D8" stroke="#4A148C" stroke-width="0.8"/>
</svg>""".replace("{star}", _star_pts(15, 12, 6, 2.5, 5, rot=-1.571))

# -------- 폭죽 (공용 처치 연출) --------
BOOM_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30, 30, 28, 11, 10)}" fill="#FF7043" stroke="#E64A19" stroke-width="1"/>
  <polygon points="{_star_pts(30, 30, 20, 8, 10, rot=0.31)}" fill="#FFB300"/>
  <circle cx="30" cy="30" r="10" fill="#FFEB3B"/>
  <circle cx="30" cy="30" r="4"  fill="#FFFFFF"/>
</svg>"""

# -------- 하단 소환 버튼 바 (5칸, 해금 상태별 4코스튬) --------
def _bar_svg(kn_unlocked, rk_unlocked, qn_unlocked):
    # 5버튼: 폰(항상)/비숍(항상)/나이트/룩/퀸. 폭 480, 버튼 폭 90, 중심 x: 48/144/240/336/432.
    # x영역 5등분 경계(scratch): -240..-144..-48..48..144..240
    def btn(cx, key, color, name, cost, locked):
        op = "0.42" if locked else "1"
        lock = (f'<text x="{cx+34}" y="22" text-anchor="middle" font-family="Arial" '
                f'font-size="16">🔒</text>') if locked else ""
        return (f'<g opacity="{op}">'
                f'<rect x="{cx-45}" y="8" width="90" height="44" rx="7" fill="{color}" '
                f'stroke="#FFFFFF" stroke-width="2"/>'
                f'<text x="{cx-38}" y="28" font-family="Arial" font-size="16" font-weight="bold" '
                f'fill="#FFFFFF">{key}</text>'
                f'<text x="{cx}" y="26" text-anchor="middle" font-family="Arial" font-size="13" '
                f'fill="#FFFFFF">{name}</text>'
                f'<text x="{cx}" y="44" text-anchor="middle" font-family="Arial" font-size="12" '
                f'fill="#FFF59D">{cost}</text></g>') + lock
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="60" viewBox="0 0 480 60">
  <rect x="2" y="2" width="476" height="56" rx="10" fill="#263238" opacity="0.92" stroke="#FFD54F" stroke-width="2"/>
  {btn(48,  "1", "#5C6BC0", "폰", "18", False)}
  {btn(144, "2", "#26A69A", "비숍", "30", False)}
  {btn(240, "3", "#8D6E63", "나이트", "45", not kn_unlocked)}
  {btn(336, "4", "#EF6C00", "룩", "70", not rk_unlocked)}
  {btn(432, "5", "#AB47BC", "퀸", "110", not qn_unlocked)}
</svg>"""

BAR_SVGS = [
    _bar_svg(False, False, False),   # 시작잠금
    _bar_svg(True,  False, False),   # 나이트해금
    _bar_svg(True,  True,  False),   # 룩해금
    _bar_svg(True,  True,  True),    # 모두해금
]

# -------- 버튼 상태 오버레이 (버튼 위에 겹치는 반투명 사각형; 쿨/골드부족/상한/잠금) --------
# 플레이테스트 #2/#4: 소환 버튼별 재충전·골드부족·유닛상한·잠금 상태를 색으로 보여줌.
# 90×44 둥근 사각(버튼과 동일). 클론이 각 버튼 위에 하나씩 떠서 매 틱 상태를 렌더.
def _overlay_svg(fill, label):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="90" height="44" viewBox="0 0 90 44">
  <rect x="0" y="0" width="90" height="44" rx="7" fill="{fill}"/>
  <text x="45" y="28" text-anchor="middle" font-family="Arial" font-size="11" font-weight="bold" fill="#FFFFFF" opacity="0.9">{label}</text>
</svg>"""
OVERLAY_SVGS = [
    _overlay_svg("#1A237E", "재충전"),   # 0 쿨(파랑) — 고스트로 차오르는 게이지처럼 페이드
    _overlay_svg("#616161", "골드"),     # 1 골드부족(회색)
    _overlay_svg("#B71C1C", "가득참"),   # 2 유닛 상한(빨강)
    _overlay_svg("#212121", ""),         # 3 잠금(어두움)
]

# -------- 투사체 (총알/포탄): 아군화살·아군포탄·적화살·적포탄 (색 구분) --------
def _arrow_proj_svg(core, edge):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="12" viewBox="0 0 24 12">
  <line x1="2" y1="6" x2="17" y2="6" stroke="{edge}" stroke-width="3"/>
  <polygon points="16,2 23,6 16,10" fill="{core}" stroke="{edge}" stroke-width="1"/>
  <polygon points="2,6 6,3 6,9" fill="{core}"/>
</svg>"""
def _shell_proj_svg(core, glow):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">
  <circle cx="9" cy="9" r="7.5" fill="{glow}" opacity="0.5"/>
  <circle cx="9" cy="9" r="5" fill="{core}"/>
  <circle cx="7" cy="7" r="1.6" fill="#FFFFFF" opacity="0.8"/>
</svg>"""
PROJ_SVGS = [
    _arrow_proj_svg("#FFF3C4", "#B8860B"),   # 0 아군 화살(금)
    _shell_proj_svg("#455A64", "#90CAF9"),   # 1 아군 포탄(청회색+파랑 글로우)
    _arrow_proj_svg("#B0BEC5", "#37474F"),   # 2 적 화살(회색)
    _shell_proj_svg("#4A148C", "#EF5350"),   # 3 적 포탄(자주+빨강 글로우)
]

# -------- 강화카드 (4선택지) --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="150" viewBox="0 0 400 150">
  <rect x="4" y="4" width="392" height="142" rx="14" fill="#1A237E" opacity="0.95" stroke="#FFD54F" stroke-width="4"/>
  <text x="200" y="30" text-anchor="middle" fill="#FFD54F" font-family="Arial" font-size="20" font-weight="bold">체크메이트! 강화 선택</text>
  <rect x="12" y="44" width="88" height="92" rx="10" fill="#F9A825" stroke="#FFFFFF" stroke-width="2"/>
  <text x="56" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">1</text>
  <text x="56" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">초당골드+</text>
  <rect x="106" y="44" width="88" height="92" rx="10" fill="#C62828" stroke="#FFFFFF" stroke-width="2"/>
  <text x="150" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">2</text>
  <text x="150" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">공격력+</text>
  <rect x="200" y="44" width="88" height="92" rx="10" fill="#2E7D32" stroke="#FFFFFF" stroke-width="2"/>
  <text x="244" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">3</text>
  <text x="244" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">체력+</text>
  <rect x="294" y="44" width="88" height="92" rx="10" fill="#1565C0" stroke="#FFFFFF" stroke-width="2"/>
  <text x="338" y="86" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="bold">4</text>
  <text x="338" y="114" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="13">킹수리</text>
</svg>"""

# -------- 게임오버 배너 --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="68" text-anchor="middle" fill="#E53935" font-family="Arial" font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="20">도달한 스테이지는 왼쪽 위에서!</text>
  <text x="180" y="136" text-anchor="middle" fill="#FFCDD2" font-family="Arial" font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# -------- 전투매니저 (보이지 않는 투명 스프라이트) --------
INVIS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8">
  <rect width="8" height="8" fill="#000000" opacity="0"/>
</svg>"""

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
def add_comment(bs, comments, block_id, text, x=520, y=40, w=320, h=160):
    _cmt_ic[0] += 1
    cid = f"cmt{_cmt_ic[0]:03d}"
    comments[cid] = {"blockId": block_id, "x": x, "y": y, "width": w, "height": h,
                     "minimized": False, "text": text}
    if block_id in bs:
        bs[block_id]["comment"] = cid
    return cid

# ============================================================
#  IDs — 5.1 튜닝 84 (개조 손잡이)
# ============================================================
# 경제/진행 (17)
V_STARTGOLD = "varStartGold01"; V_GOLDRATE = "varGoldRate02"; V_KILLGOLD = "varKillGold03"
V_CLEARGOLD = "varClearGold04"; V_COSTPW = "varCostPawn05"; V_COSTBS = "varCostBishop06"
V_COSTKN = "varCostKnight07"; V_COSTRK = "varCostRook08"; V_COSTQN = "varCostQueen09"
V_MAXALLY = "varMaxAlly10"; V_MAXENEMY = "varMaxEnemy11"; V_KINGMAX = "varMyKingMax12"
V_ENKINGBASE = "varEnKingBase13"; V_SCALE = "varScale14"; V_UNLKKN = "varUnlockKnight15"
V_UNLKRK = "varUnlockRook16"; V_UNLKQN = "varUnlockQueen17"
# 전역 전투/무대 (5)
V_TICK = "varTick18"; V_REACH = "varKingReach19"; V_LANEY = "varLaneY20"
V_MYKX = "varMyKingX21"; V_ENKX = "varEnKingX22"
# 아군 스탯 (30)
V_PWHP = "varPwHP23"; V_PWATK = "varPwATK24"; V_PWCD = "varPwCD25"; V_PWSP = "varPwSP26"
V_PWR = "varPwR27"; V_PWSUM = "varPwSum28"
V_BSHP = "varBsHP29"; V_BSATK = "varBsATK30"; V_BSCD = "varBsCD31"; V_BSSP = "varBsSP32"
V_BSR = "varBsR33"; V_BSSUM = "varBsSum34"
V_KNHP = "varKnHP35"; V_KNATK = "varKnATK36"; V_KNCD = "varKnCD37"; V_KNSP = "varKnSP38"
V_KNR = "varKnR39"; V_KNSUM = "varKnSum40"
V_RKHP = "varRkHP41"; V_RKATK = "varRkATK42"; V_RKCD = "varRkCD43"; V_RKSP = "varRkSP44"
V_RKR = "varRkR45"; V_RKSUM = "varRkSum46"
V_QNHP = "varQnHP47"; V_QNATK = "varQnATK48"; V_QNCD = "varQnCD49"; V_QNSP = "varQnSP50"
V_QNR = "varQnR51"; V_QNSUM = "varQnSum52"
# 적 스탯 (25)
V_EPHP = "varEpHP53"; V_EPATK = "varEpATK54"; V_EPCD = "varEpCD55"; V_EPSP = "varEpSP56"; V_EPR = "varEpR57"
V_EBHP = "varEbHP58"; V_EBATK = "varEbATK59"; V_EBCD = "varEbCD60"; V_EBSP = "varEbSP61"; V_EBR = "varEbR62"
V_ENKHP = "varEnkHP63"; V_ENKATK = "varEnkATK64"; V_ENKCD = "varEnkCD65"; V_ENKSP = "varEnkSP66"; V_ENKR = "varEnkR67"
V_ERHP = "varErHP68"; V_ERATK = "varErATK69"; V_ERCD = "varErCD70"; V_ERSP = "varErSP71"; V_ERR = "varErR72"
V_EQHP = "varEqHP73"; V_EQATK = "varEqATK74"; V_EQCD = "varEqCD75"; V_EQSP = "varEqSP76"; V_EQR = "varEqR77"
# 스폰/강화 (7)
V_SPGAP = "varSpawnGap78"; V_SPDEC = "varSpawnDec79"; V_SPMIN = "varSpawnMin80"
V_UPGOLD = "varUpGold81"; V_UPATK = "varUpAtk82"; V_UPHP = "varUpHP83"; V_UPREPAIR = "varUpRepair84"

# ----- 5.2 진행/내부 상태 40 -----
V_STATE = "varState85"; V_STAGE = "varStage86"; V_GOLD = "varGold87"; V_GOLDACC = "varGoldAcc88"
V_MYHP = "varMyKingHP89"; V_ENHP = "varEnKingHP90"; V_SCALECUR = "varScaleCur91"
V_ALLYN = "varAllyN92"; V_ENEMYN = "varEnemyN93"; V_ATKMUL = "varAtkMul94"; V_HPMUL = "varHpMul95"
V_UNKN = "varUnKn96"; V_UNRK = "varUnRk97"; V_UNQN = "varUnQn98"
V_SUMTYPE = "varSumType99"; V_NEWALLY = "varNewAlly100"
V_ENSPAWNT = "varEnSpawnT101"; V_NEWENEMY = "varNewEnemy102"
V_SUMT1 = "varSumT1_103"; V_SUMT2 = "varSumT2_104"; V_SUMT3 = "varSumT3_105"; V_SUMT4 = "varSumT4_106"; V_SUMT5 = "varSumT5_107"
V_ENSPTIMER = "varEnSpawnTmr108"
V_EFRONTX = "varEFrontX109"; V_EFRONTI = "varEFrontI110"; V_AFRONTX = "varAFrontX111"; V_AFRONTI = "varAFrontI112"
V_LOOPI = "varLoopI113"; V_LOOPJ = "varLoopJ114"; V_CALCT = "varCalcT115"; V_CALCD = "varCalcD116"
V_DMGVAL = "varDmgVal117"; V_DMGX = "varDmgX118"; V_DMGY = "varDmgY119"; V_DMGKIND = "varDmgKind120"
V_DMGDIG = "varDmgDigit121"; V_DMGOFF = "varDmgOff122"; V_DMGLEN = "varDmgLen123"; V_DMGPOS = "varDmgPos124"
# ----- 5.2b 진행 추가(플레이테스트 패치): 슬롯 재사용(메모리 상한)·오버레이 슬롯배정·스폰체력 채널 -----
V_REUSE = "varReuse125"; V_LOOPK = "varLoopK126"; V_OVCOUNT = "varOvCount127"; V_SPAWNHP = "varSpawnHP128"
V_UNITS = "varUnitsShown129"   # 화면 표시용 "아군수/최대유닛수" (모니터)
# ----- 3차 패치: 투사체(총알/포탄) 채널 + 국지 킹공성 거리 -----
V_FX = "varFireX130"; V_FTX = "varFireToX131"; V_FKIND = "varFireKind132"  # 발사X·발사목표X·발사종류(0아군화살/1아군포탄/2적화살/3적포탄)
V_SIEGE = "varKingSiege133"   # 킹공성거리: 이 안(전선 절반)에서만 킹 공성 → 후방 비숍 직격 방지

# ----- 5.3 리스트 (10) -----
L_ALLYX = "listAllyX"; L_ALLYHP = "listAllyHP"; L_ALLYT = "listAllyT"
L_ALLYAL = "listAllyAlive"; L_ALLYCD = "listAllyCD"
L_ENX = "listEnX"; L_ENHP = "listEnHP"; L_ENT = "listEnT"
L_ENAL = "listEnAlive"; L_ENCD = "listEnCD"

# ----- 5.4 클론-로컬 (5) -----
V_ALLY_ISC = "varAllyIsClone"; V_ALLY_SLOT = "varAllySlot"
V_EN_ISC = "varEnIsClone"; V_EN_SLOT = "varEnSlot"
V_POP_ISC = "varPopIsClone"
# 투사체 클론-로컬
V_PROJ_ISC = "varProjIsClone"; V_PROJ_KIND = "varProjKind"; V_PROJ_SX = "varProjSX"; V_PROJ_TX = "varProjTX"; V_PROJ_T = "varProjT"
V_OV_ISC = "varOvIsClone"; V_OV_SLOT = "varOvSlot"   # 쿨오버레이 클론-로컬

# ----- 5.5 메시지 (10) -----
BR_START = "brStart01"; BR_STAGEGO = "brStageGo02"; BR_ALLY = "brAlly03"; BR_ENEMY = "brEnemy04"
BR_DMG = "brDmg05"; BR_MYHIT = "brMyHit06"; BR_ENHIT = "brEnHit07"; BR_CLEAR = "brClear08"
BR_UPDONE = "brUpDone09"; BR_OVER = "brOver10"; BR_FIRE = "brFire11"   # 투사체 발사

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

def b_not(bs, cond):
    bid = gen(); bs[bid] = mk("operator_not", inputs={"OPERAND": [2, cond]})
    bs[cond]["parent"] = bid
    return bid

def b_mathop(bs, oper, val):
    bid = gen()
    ins = {"NUM": slot(val) if (isinstance(val, str) and val in bs) else num(val)}
    bs[bid] = mk("operator_mathop", inputs=ins, fields={"OPERATOR": [oper, None]})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def b_round(bs, val):
    bid = gen()
    ins = {"NUM": slot(val) if (isinstance(val, str) and val in bs) else num(val)}
    bs[bid] = mk("operator_round", inputs=ins)
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

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

def b_mousedown(bs):
    bid = gen(); bs[bid] = mk("sensing_mousedown"); return bid
def b_mousex(bs):
    bid = gen(); bs[bid] = mk("sensing_mousex"); return bid
def b_mousey(bs):
    bid = gen(); bs[bid] = mk("sensing_mousey"); return bid

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
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": num(dur)}); return bid

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

def b_playsound(bs, sound):
    sm = gen(); bs[sm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]})
    bs[sm]["parent"] = sp
    return sp

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

def b_gotoxy(bs, x, y):
    bid = gen()
    def side(v): return slot(v) if (isinstance(v, str) and v in bs) else num(v)
    bs[bid] = mk("motion_gotoxy", inputs={"X": side(x), "Y": side(y)})
    for v in (x, y):
        if isinstance(v, str) and v in bs: bs[v]["parent"] = bid
    return bid

def b_setsize(bs, sz):
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
def b_norot(bs):
    bid = gen(); bs[bid] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]}); return bid
def b_pointdir(bs, d):
    bid = gen(); bs[bid] = mk("motion_pointindirection", inputs={"DIRECTION": num(d)}); return bid
def b_delclone(bs):
    bid = gen(); bs[bid] = mk("control_delete_this_clone"); return bid
def b_createclone(bs):
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cc
    return cc

# ---- list helpers (add/replace/item/length/deleteall 만) ----
def l_item(bs, name, lid, index):
    bid = gen()
    ins = {"INDEX": slot(index) if (isinstance(index, str) and index in bs) else num(index)}
    bs[bid] = mk("data_itemoflist", inputs=ins, fields={"LIST": [name, lid]})
    if isinstance(index, str) and index in bs: bs[index]["parent"] = bid
    return bid

def l_length(bs, name, lid):
    bid = gen(); bs[bid] = mk("data_lengthoflist", fields={"LIST": [name, lid]}); return bid

def l_add(bs, name, lid, value):
    bid = gen()
    ins = {"ITEM": slot(value) if (isinstance(value, str) and value in bs) else num(value)}
    bs[bid] = mk("data_addtolist", inputs=ins, fields={"LIST": [name, lid]})
    if isinstance(value, str) and value in bs: bs[value]["parent"] = bid
    return bid

def l_replace(bs, name, lid, index, value):
    bid = gen()
    ins = {
        "INDEX": slot(index) if (isinstance(index, str) and index in bs) else num(index),
        "ITEM":  slot(value) if (isinstance(value, str) and value in bs) else num(value),
    }
    bs[bid] = mk("data_replaceitemoflist", inputs=ins, fields={"LIST": [name, lid]})
    if isinstance(index, str) and index in bs: bs[index]["parent"] = bid
    if isinstance(value, str) and value in bs: bs[value]["parent"] = bid
    return bid

def l_delall(bs, name, lid):
    bid = gen(); bs[bid] = mk("data_deletealloflist", fields={"LIST": [name, lid]}); return bid

def C(bs, ids):
    chain([(i, bs[i]) for i in ids])

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 → 튜닝 84 + 진행 40 초기화(한 곳) + 리스트 10개 비우기 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [h]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val); seq.append(sid)
    def add_set_r(name, vid, rep):
        sid = b_setvar(bs, name, vid, rep); seq.append(sid)

    # ── 튜닝 84 (개조 손잡이) ──
    add_set("시작골드", V_STARTGOLD, 200); add_set("초당골드", V_GOLDRATE, 14)
    add_set("처치골드", V_KILLGOLD, 3); add_set("스테이지클리어골드", V_CLEARGOLD, 50)
    add_set("폰코스트", V_COSTPW, 18); add_set("비숍코스트", V_COSTBS, 30)
    add_set("나이트코스트", V_COSTKN, 45); add_set("룩코스트", V_COSTRK, 70); add_set("퀸코스트", V_COSTQN, 110)
    add_set("최대유닛수", V_MAXALLY, 12); add_set("적최대유닛수", V_MAXENEMY, 12)
    add_set("하얀킹최대체력", V_KINGMAX, 100); add_set("검은킹기본체력", V_ENKINGBASE, 120)
    add_set("적성장배율", V_SCALE, 1.25); add_set("나이트해금스테이지", V_UNLKKN, 2)
    add_set("룩해금스테이지", V_UNLKRK, 3); add_set("퀸해금스테이지", V_UNLKQN, 4)
    add_set("시뮬틱", V_TICK, 0.02); add_set("킹공격거리", V_REACH, 40); add_set("킹공성거리", V_SIEGE, 300)
    add_set("레인Y", V_LANEY, -50); add_set("하얀킹X", V_MYKX, -200); add_set("검은킹X", V_ENKX, 200)
    # 아군 스탯
    add_set("폰_체력", V_PWHP, 12); add_set("폰_공격력", V_PWATK, 6); add_set("폰_공속", V_PWCD, 0.4)
    add_set("폰_속도", V_PWSP, 5.5); add_set("폰_사거리", V_PWR, 30); add_set("폰_소환쿨", V_PWSUM, 0.3)
    add_set("비숍_체력", V_BSHP, 8); add_set("비숍_공격력", V_BSATK, 7); add_set("비숍_공속", V_BSCD, 0.5)
    add_set("비숍_속도", V_BSSP, 3.5); add_set("비숍_사거리", V_BSR, 380); add_set("비숍_소환쿨", V_BSSUM, 0.45)
    add_set("나이트_체력", V_KNHP, 22); add_set("나이트_공격력", V_KNATK, 13); add_set("나이트_공속", V_KNCD, 0.45)
    add_set("나이트_속도", V_KNSP, 6.0); add_set("나이트_사거리", V_KNR, 34); add_set("나이트_소환쿨", V_KNSUM, 0.6)
    add_set("룩_체력", V_RKHP, 16); add_set("룩_공격력", V_RKATK, 8); add_set("룩_공속", V_RKCD, 0.9)
    add_set("룩_속도", V_RKSP, 2.6); add_set("룩_사거리", V_RKR, 400); add_set("룩_소환쿨", V_RKSUM, 0.9)
    add_set("퀸_체력", V_QNHP, 30); add_set("퀸_공격력", V_QNATK, 9); add_set("퀸_공속", V_QNCD, 0.7)
    add_set("퀸_속도", V_QNSP, 3.2); add_set("퀸_사거리", V_QNR, 390); add_set("퀸_소환쿨", V_QNSUM, 1.2)
    # 적 스탯
    add_set("적폰_체력", V_EPHP, 8); add_set("적폰_공격력", V_EPATK, 3); add_set("적폰_공속", V_EPCD, 0.5)
    add_set("적폰_속도", V_EPSP, 5.0); add_set("적폰_사거리", V_EPR, 30)
    add_set("적비숍_체력", V_EBHP, 6); add_set("적비숍_공격력", V_EBATK, 4); add_set("적비숍_공속", V_EBCD, 0.6)
    add_set("적비숍_속도", V_EBSP, 3.3); add_set("적비숍_사거리", V_EBR, 360)
    add_set("적나이트_체력", V_ENKHP, 16); add_set("적나이트_공격력", V_ENKATK, 8); add_set("적나이트_공속", V_ENKCD, 0.5)
    add_set("적나이트_속도", V_ENKSP, 5.5); add_set("적나이트_사거리", V_ENKR, 34)
    add_set("적룩_체력", V_ERHP, 12); add_set("적룩_공격력", V_ERATK, 5); add_set("적룩_공속", V_ERCD, 0.9)
    add_set("적룩_속도", V_ERSP, 2.4); add_set("적룩_사거리", V_ERR, 380)
    add_set("적퀸_체력", V_EQHP, 32); add_set("적퀸_공격력", V_EQATK, 7); add_set("적퀸_공속", V_EQCD, 0.7)
    add_set("적퀸_속도", V_EQSP, 3.0); add_set("적퀸_사거리", V_EQR, 370)
    # 스폰/강화
    add_set("적소환간격", V_SPGAP, 2.2); add_set("적소환간격감소", V_SPDEC, 0.12); add_set("적소환최소간격", V_SPMIN, 0.7)
    add_set("강화골드증가", V_UPGOLD, 3); add_set("강화공격배수", V_UPATK, 1.15)
    add_set("강화체력배수", V_UPHP, 1.15); add_set("강화킹수리", V_UPREPAIR, 40)

    tuning_last = seq[-1]

    # ── 진행 상태 40 ──
    add_set("게임상태", V_STATE, 1); add_set("스테이지", V_STAGE, 1)
    add_set_r("골드", V_GOLD, vrep("시작골드", V_STARTGOLD))
    add_set("골드누적", V_GOLDACC, 0)
    add_set_r("하얀킹체력", V_MYHP, vrep("하얀킹최대체력", V_KINGMAX))
    add_set("적배율", V_SCALECUR, 1)
    add_set_r("검은킹체력", V_ENHP, vrep("검은킹기본체력", V_ENKINGBASE))
    add_set("아군수", V_ALLYN, 0); add_set("적군수", V_ENEMYN, 0)
    add_set("유닛공격력배수", V_ATKMUL, 1); add_set("유닛체력배수", V_HPMUL, 1)
    add_set("나이트해금", V_UNKN, 0); add_set("룩해금", V_UNRK, 0); add_set("퀸해금", V_UNQN, 0)
    add_set("소환타입", V_SUMTYPE, 0); add_set("새아군슬롯", V_NEWALLY, 0)
    add_set("적생성타입", V_ENSPAWNT, 1); add_set("새적슬롯", V_NEWENEMY, 0)
    add_set("폰쿨타이머", V_SUMT1, 0); add_set("비숍쿨타이머", V_SUMT2, 0)
    add_set("나이트쿨타이머", V_SUMT3, 0); add_set("룩쿨타이머", V_SUMT4, 0); add_set("퀸쿨타이머", V_SUMT5, 0)
    add_set("적소환타이머", V_ENSPTIMER, 0)
    add_set("적선두X", V_EFRONTX, 200); add_set("적선두슬롯", V_EFRONTI, 0)
    add_set("아군선두X", V_AFRONTX, -200); add_set("아군선두슬롯", V_AFRONTI, 0)
    add_set("루프i", V_LOOPI, 0); add_set("루프j", V_LOOPJ, 0)
    add_set("계산타입", V_CALCT, 0); add_set("계산뎀", V_CALCD, 0)
    add_set("데미지표시값", V_DMGVAL, 0); add_set("데미지표시x", V_DMGX, 0)
    add_set("데미지표시y", V_DMGY, 0); add_set("팝업종류", V_DMGKIND, 0)
    add_set("데미지숫자", V_DMGDIG, 0); add_set("데미지오프셋", V_DMGOFF, 0)
    add_set("데미지글자수", V_DMGLEN, 0); add_set("데미지자리", V_DMGPOS, 0)
    # 진행 추가(패치): 슬롯 재사용·오버레이 슬롯배정·스폰체력 채널
    add_set("재사용슬롯", V_REUSE, 0); add_set("루프k", V_LOOPK, 0)
    add_set("오버레이카운터", V_OVCOUNT, 0); add_set("스폰체력", V_SPAWNHP, 0)
    add_set("유닛", V_UNITS, "0/12")   # 화면 표시용 n/최대 (매니저가 매 틱 갱신)
    add_set("발사X", V_FX, 0); add_set("발사목표X", V_FTX, 0); add_set("발사종류", V_FKIND, 0)

    # ── 유닛 리스트 통째 비우기 ──
    for nm, lid in [("아군X", L_ALLYX), ("아군HP", L_ALLYHP), ("아군타입", L_ALLYT),
                    ("아군살아있음", L_ALLYAL), ("아군쿨", L_ALLYCD),
                    ("적군X", L_ENX), ("적군HP", L_ENHP), ("적군타입", L_ENT),
                    ("적군살아있음", L_ENAL), ("적군쿨", L_ENCD)]:
        seq.append(l_delall(bs, nm, lid))

    seq.append(b_wait(bs, 0.2))
    seq.append(b_broadcast(bs, "게임시작", BR_START))
    seq.append(b_broadcast(bs, "스테이지시작", BR_STAGEGO))
    C(bs, seq)

    add_comment(bs, comments, tuning_last,
        "🛠️ 개조 손잡이: 여기 숫자만 바꾸면 게임이 달라져요! 골드·유닛·적 전부 여기서 정해져요.",
        x=460, y=20, w=340, h=110)
    for bid, b in bs.items():
        if b.get("opcode") == "data_setvariableto" and b.get("fields", {}).get("VARIABLE", [None, None])[1] == V_SCALE:
            add_comment(bs, comments, bid,
                "📈 적성장배율! 스테이지가 오를 때마다 검은 군단이 이만큼 '곱하기'로 세져요. "
                "1.25 → 1.5 로 바꾸면 확 어려워져요.", x=460, y=150, w=340, h=120)
            break

    # ===== (B) 초당골드 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=520,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    rate_r = vrep("초당골드", V_GOLDRATE)
    tenth = op("operator_multiply", rate_r, 0.1)
    ch_acc = b_changevar(bs, "골드누적", V_GOLDACC, tenth)
    acc_r = vrep("골드누적", V_GOLDACC)
    c_ge1 = cmp_op("operator_gt", acc_r, 0.999999)
    fl1 = b_mathop(bs, "floor", vrep("골드누적", V_GOLDACC))
    ch_gold = b_changevar(bs, "골드", V_GOLD, fl1)
    fl2 = b_mathop(bs, "floor", vrep("골드누적", V_GOLDACC))
    negfl = op("operator_subtract", 0, fl2)
    ch_acc_back = b_changevar(bs, "골드누적", V_GOLDACC, negfl)
    C(bs, [ch_gold, ch_acc_back])
    if_ge1 = b_if(bs, c_ge1, ch_gold)
    C(bs, [ch_acc, if_ge1])
    st_r = vrep("게임상태", V_STATE); c_play = cmp_op("operator_equals", st_r, 1)
    if_play = b_if(bs, c_play, ch_acc)
    w_gold = b_wait(bs, 0.1)
    C(bs, [if_play, w_gold])
    fe_gold = b_forever(bs, if_play)
    C(bs, [hb, fe_gold])
    add_comment(bs, comments, if_play,
        "💰 골드는 초당 저절로 쌓여요. 초당골드를 키우면 유닛을 더 자주 뽑아요.",
        x=460, y=520, w=320, h=110)

    # ===== (C) 스테이지 시작 뿔피리 =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=380, y=520,
        fields={"BROADCAST_OPTION": ["스테이지시작", BR_STAGEGO]})
    sh, sp = b_sound(bs, 0, "horn")
    C(bs, [hc, sh, sp])

    # ===== (D) 클리어 / 게임오버 감시 forever =====
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=860,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    st1 = vrep("게임상태", V_STATE); c_p1 = cmp_op("operator_equals", st1, 1)
    enhp = vrep("검은킹체력", V_ENHP); c_en0 = b_not(bs, cmp_op("operator_gt", enhp, 0))
    c_clear = bool_op("operator_and", c_p1, c_en0)
    add_clear = b_changevar(bs, "골드", V_GOLD, vrep("스테이지클리어골드", V_CLEARGOLD))
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_clear = b_broadcast(bs, "스테이지클리어", BR_CLEAR)
    C(bs, [add_clear, set_st2, bc_clear])
    if_clear = b_if(bs, c_clear, add_clear)
    st2 = vrep("게임상태", V_STATE); c_p2 = cmp_op("operator_equals", st2, 1)
    myhp = vrep("하얀킹체력", V_MYHP); c_my0 = b_not(bs, cmp_op("operator_gt", myhp, 0))
    c_over = bool_op("operator_and", c_p2, c_my0)
    set_st0 = b_setvar(bs, "게임상태", V_STATE, 0)
    bc_over = b_broadcast(bs, "게임오버", BR_OVER)
    C(bs, [set_st0, bc_over])
    if_over = b_if(bs, c_over, set_st0)
    w_watch = b_wait(bs, 0.1)
    C(bs, [if_clear, if_over, w_watch])
    fe_watch = b_forever(bs, if_clear)
    C(bs, [hd, fe_watch])

    return bs, comments

# ============================================================
#  하얀킹 / 검은킹
# ============================================================
def build_king_blocks(is_mine):
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    kx_vid, kx_nm = (V_MYKX, "하얀킹X") if is_mine else (V_ENKX, "검은킹X")
    hit_br, hit_id = ("하얀킹피격", BR_MYHIT) if is_mine else ("검은킹피격", BR_ENHIT)
    break_br, break_id = ("게임오버", BR_OVER) if is_mine else ("스테이지클리어", BR_CLEAR)

    # (A) 깃발 초기화
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sh = b_show(bs)
    g = b_gotoxy(bs, vrep(kx_nm, kx_vid), -30)
    sz = b_setsize(bs, 90)
    rs = b_norot(bs)
    cg = b_cleargfx(bs)
    C(bs, [h, sh, g, sz, rs, cg])

    # (B) 피격 → 빨강 깜빡 + kinghit
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": [hit_br, hit_id]})
    ph, pp = b_sound(bs, 0, "kinghit")
    e_on = b_seteffect(bs, "COLOR", 80); w1 = b_wait(bs, 0.04)
    e_off = b_seteffect(bs, "COLOR", 0); w2 = b_wait(bs, 0.04)
    C(bs, [e_on, w1, e_off, w2])
    rep = b_repeat(bs, 3, e_on)
    C(bs, [hb, ph, pp, rep])

    # (C) 함락 → break + 무릎 꿇는 연출(원상복구)
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=20, y=380,
        fields={"BROADCAST_OPTION": [break_br, break_id]})
    bh, bp = b_sound(bs, 0, "break")
    gstep = 10 if is_mine else 12
    gwait = 0.05 if is_mine else 0.04
    g_on = b_changeeffect(bs, "GHOST", gstep); gw = b_wait(bs, gwait)
    C(bs, [g_on, gw])
    rep2 = b_repeat(bs, 6, g_on)
    g_off = b_seteffect(bs, "GHOST", 0)
    C(bs, [hc, bh, bp, rep2, g_off])

    return bs, comments

# ============================================================
#  전투매니저 (시뮬레이션 두뇌 + 적 스포너)
# ============================================================
def build_manager_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    def le(a, b_):  # a <= b  →  not(a > b)
        return b_not(bs, cmp_op("operator_gt", a, b_))

    # ── 데미지팝업 헬퍼: set 값/x/y/종류 + broadcast 데미지표시 → head 반환 ──
    def emit_popup(valexpr, xexpr, yexpr, kind):
        if isinstance(valexpr, str) and valexpr in bs:
            dval = b_round(bs, valexpr)
        else:
            dval = valexpr
        s1 = b_setvar(bs, "데미지표시값", V_DMGVAL, dval)
        s2 = b_setvar(bs, "데미지표시x", V_DMGX, xexpr)
        s3 = b_setvar(bs, "데미지표시y", V_DMGY, yexpr)
        s4 = b_setvar(bs, "팝업종류", V_DMGKIND, kind)
        bc = b_broadcast(bs, "데미지표시", BR_DMG)
        C(bs, [s1, s2, s3, s4, bc])
        return s1

    # ── 단일공격_적: 아군이 최전방 적(또는 검은 킹)을 때림. 뎀=계산뎀 ──
    def emit_single_hit_enemy():
        c_king = cmp_op("operator_equals", vrep("적선두슬롯", V_EFRONTI), 0)
        negd = op("operator_subtract", 0, vrep("계산뎀", V_CALCD))
        dec_en = b_changevar(bs, "검은킹체력", V_ENHP, negd)
        bc_hit = b_broadcast(bs, "검은킹피격", BR_ENHIT)
        pop_c = emit_popup(vrep("계산뎀", V_CALCD), vrep("검은킹X", V_ENKX), 0, 0)
        C(bs, [dec_en, bc_hit, pop_c])
        idx = vrep("적선두슬롯", V_EFRONTI)
        cur = l_item(bs, "적군HP", L_ENHP, vrep("적선두슬롯", V_EFRONTI))
        newhp = op("operator_subtract", cur, vrep("계산뎀", V_CALCD))
        repl_hp = l_replace(bs, "적군HP", L_ENHP, idx, newhp)
        pop_d = emit_popup(vrep("계산뎀", V_CALCD), vrep("적선두X", V_EFRONTX), vrep("레인Y", V_LANEY), 0)
        hp_r = l_item(bs, "적군HP", L_ENHP, vrep("적선두슬롯", V_EFRONTI))
        c_dead = le(hp_r, 0)
        set_dead = l_replace(bs, "적군살아있음", L_ENAL, vrep("적선두슬롯", V_EFRONTI), 0)
        dec_n = b_changevar(bs, "적군수", V_ENEMYN, -1)
        add_g = b_changevar(bs, "골드", V_GOLD, vrep("처치골드", V_KILLGOLD))
        pc = b_playsound(bs, "coin")
        y2 = op("operator_add", vrep("레인Y", V_LANEY), 20)
        pop_g = emit_popup(vrep("처치골드", V_KILLGOLD), vrep("적선두X", V_EFRONTX), y2, 1)
        C(bs, [set_dead, dec_n, add_g, pc, pop_g])
        if_dead = b_if(bs, c_dead, set_dead)
        C(bs, [repl_hp, pop_d, if_dead])
        # 하나의 top-level 블록(ifelse). 리스트로 반환해 caller 가 이어붙임.
        return [b_ifelse(bs, c_king, dec_en, repl_hp)]

    # ── 단일공격_아군: 적이 최전방 아군(또는 하얀 킹)을 때림 ──
    def emit_single_hit_ally():
        c_king = cmp_op("operator_equals", vrep("아군선두슬롯", V_AFRONTI), 0)
        negd = op("operator_subtract", 0, vrep("계산뎀", V_CALCD))
        dec_my = b_changevar(bs, "하얀킹체력", V_MYHP, negd)
        bc_hit = b_broadcast(bs, "하얀킹피격", BR_MYHIT)
        pop_c = emit_popup(vrep("계산뎀", V_CALCD), vrep("하얀킹X", V_MYKX), 0, 0)
        C(bs, [dec_my, bc_hit, pop_c])
        idx = vrep("아군선두슬롯", V_AFRONTI)
        cur = l_item(bs, "아군HP", L_ALLYHP, vrep("아군선두슬롯", V_AFRONTI))
        newhp = op("operator_subtract", cur, vrep("계산뎀", V_CALCD))
        repl_hp = l_replace(bs, "아군HP", L_ALLYHP, idx, newhp)
        pop_d = emit_popup(vrep("계산뎀", V_CALCD), vrep("아군선두X", V_AFRONTX), vrep("레인Y", V_LANEY), 0)
        hp_r = l_item(bs, "아군HP", L_ALLYHP, vrep("아군선두슬롯", V_AFRONTI))
        c_dead = le(hp_r, 0)
        set_dead = l_replace(bs, "아군살아있음", L_ALLYAL, vrep("아군선두슬롯", V_AFRONTI), 0)
        dec_n = b_changevar(bs, "아군수", V_ALLYN, -1)
        C(bs, [set_dead, dec_n])
        if_dead = b_if(bs, c_dead, set_dead)
        C(bs, [repl_hp, pop_d, if_dead])
        return [b_ifelse(bs, c_king, dec_my, repl_hp)]

    # ── 광역공격_아군이적을(중심=아군X[루프i], 반경=사거리아군(타입)) + 포격음 ──
    def emit_aoe_enemy(R_id, R_nm):
        pc = b_playsound(bs, "cannon")   # 포격음
        set_j = b_setvar(bs, "루프j", V_LOOPJ, 1)
        center = l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI))
        radius = vrep(R_nm, R_id)
        alive_j = cmp_op("operator_equals", l_item(bs, "적군살아있음", L_ENAL, vrep("루프j", V_LOOPJ)), 1)
        diffx = op("operator_subtract", l_item(bs, "적군X", L_ENX, vrep("루프j", V_LOOPJ)), center)
        absx = b_mathop(bs, "abs", diffx)
        c_in = le(absx, radius)
        c_hit = bool_op("operator_and", alive_j, c_in)
        idxj = vrep("루프j", V_LOOPJ)
        cur = l_item(bs, "적군HP", L_ENHP, vrep("루프j", V_LOOPJ))
        newhp = op("operator_subtract", cur, vrep("계산뎀", V_CALCD))
        repl_hp = l_replace(bs, "적군HP", L_ENHP, idxj, newhp)
        pop_d = emit_popup(vrep("계산뎀", V_CALCD), l_item(bs, "적군X", L_ENX, vrep("루프j", V_LOOPJ)), vrep("레인Y", V_LANEY), 0)
        hp_r = l_item(bs, "적군HP", L_ENHP, vrep("루프j", V_LOOPJ))
        c_dead = le(hp_r, 0)
        set_dead = l_replace(bs, "적군살아있음", L_ENAL, vrep("루프j", V_LOOPJ), 0)
        dec_n = b_changevar(bs, "적군수", V_ENEMYN, -1)
        add_g = b_changevar(bs, "골드", V_GOLD, vrep("처치골드", V_KILLGOLD))
        pc2 = b_playsound(bs, "coin")
        C(bs, [set_dead, dec_n, add_g, pc2])
        if_dead = b_if(bs, c_dead, set_dead)
        C(bs, [repl_hp, pop_d, if_dead])
        if_hit = b_if(bs, c_hit, repl_hp)
        inc_j = b_changevar(bs, "루프j", V_LOOPJ, 1)
        C(bs, [if_hit, inc_j])
        rep = b_repeat(bs, l_length(bs, "적군X", L_ENX), if_hit)
        c_none = cmp_op("operator_equals", vrep("적군수", V_ENEMYN), 0)
        center2 = l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI))
        diffc = op("operator_subtract", vrep("검은킹X", V_ENKX), center2)
        absc = b_mathop(bs, "abs", diffc)
        c_inc = le(absc, vrep(R_nm, R_id))
        c_king = bool_op("operator_and", c_none, c_inc)
        negd = op("operator_subtract", 0, vrep("계산뎀", V_CALCD))
        dec_en = b_changevar(bs, "검은킹체력", V_ENHP, negd)
        bc_hit = b_broadcast(bs, "검은킹피격", BR_ENHIT)
        C(bs, [dec_en, bc_hit])
        if_king = b_if(bs, c_king, dec_en)
        # top-level 순서: pc(포격음) → set_j → rep(포격 루프) → if_king.
        # caller 가 flat 하게 이어붙이도록 리스트로 반환(내부 top-level 체인 안 함).
        return [pc, set_j, rep, if_king]

    # ── 광역공격_적이아군을(중심=적군X[루프i], 반경=사거리적(타입)) + 포격음 ──
    def emit_aoe_ally(R_id, R_nm):
        pc = b_playsound(bs, "cannon")
        set_j = b_setvar(bs, "루프j", V_LOOPJ, 1)
        center = l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI))
        radius = vrep(R_nm, R_id)
        alive_j = cmp_op("operator_equals", l_item(bs, "아군살아있음", L_ALLYAL, vrep("루프j", V_LOOPJ)), 1)
        diffx = op("operator_subtract", l_item(bs, "아군X", L_ALLYX, vrep("루프j", V_LOOPJ)), center)
        absx = b_mathop(bs, "abs", diffx)
        c_in = le(absx, radius)
        c_hit = bool_op("operator_and", alive_j, c_in)
        idxj = vrep("루프j", V_LOOPJ)
        cur = l_item(bs, "아군HP", L_ALLYHP, vrep("루프j", V_LOOPJ))
        newhp = op("operator_subtract", cur, vrep("계산뎀", V_CALCD))
        repl_hp = l_replace(bs, "아군HP", L_ALLYHP, idxj, newhp)
        pop_d = emit_popup(vrep("계산뎀", V_CALCD), l_item(bs, "아군X", L_ALLYX, vrep("루프j", V_LOOPJ)), vrep("레인Y", V_LANEY), 0)
        hp_r = l_item(bs, "아군HP", L_ALLYHP, vrep("루프j", V_LOOPJ))
        c_dead = le(hp_r, 0)
        set_dead = l_replace(bs, "아군살아있음", L_ALLYAL, vrep("루프j", V_LOOPJ), 0)
        dec_n = b_changevar(bs, "아군수", V_ALLYN, -1)
        C(bs, [set_dead, dec_n])
        if_dead = b_if(bs, c_dead, set_dead)
        C(bs, [repl_hp, pop_d, if_dead])
        if_hit = b_if(bs, c_hit, repl_hp)
        inc_j = b_changevar(bs, "루프j", V_LOOPJ, 1)
        C(bs, [if_hit, inc_j])
        rep = b_repeat(bs, l_length(bs, "아군X", L_ALLYX), if_hit)
        c_none = cmp_op("operator_equals", vrep("아군수", V_ALLYN), 0)
        center2 = l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI))
        diffc = op("operator_subtract", vrep("하얀킹X", V_MYKX), center2)
        absc = b_mathop(bs, "abs", diffc)
        c_inc = le(absc, vrep(R_nm, R_id))
        c_king = bool_op("operator_and", c_none, c_inc)
        negd = op("operator_subtract", 0, vrep("계산뎀", V_CALCD))
        dec_my = b_changevar(bs, "하얀킹체력", V_MYHP, negd)
        bc_hit = b_broadcast(bs, "하얀킹피격", BR_MYHIT)
        C(bs, [dec_my, bc_hit])
        if_king = b_if(bs, c_king, dec_my)
        return [pc, set_j, rep, if_king]

    # ── 투사체 발사(시각 전용, 공격 이벤트와 1:1): 발사X·목표X·종류 세팅 후 발사 방송(비대기).
    #    클론/방송 과부하 방지 위해 1/2 확률로만 스폰. kind: 0아군화살·1아군포탄·2적화살·3적포탄 ──
    def emit_projectile(fromx_expr, tox_expr, kind):
        s1 = b_setvar(bs, "발사X", V_FX, fromx_expr)
        s2 = b_setvar(bs, "발사목표X", V_FTX, tox_expr)
        s3 = b_setvar(bs, "발사종류", V_FKIND, kind)
        bc = b_broadcast(bs, "발사", BR_FIRE)
        C(bs, [s1, s2, s3, bc])
        rnd = op("operator_random", 1, 2, key1="FROM", key2="TO")
        return [b_if(bs, cmp_op("operator_equals", rnd, 1), s1)]

    # ── 킹 공성(국지): 상대 킹이 '킹공성거리' 안이거나 킹공격거리(성벽) 안일 때 킹 체력을 깎는다.
    #    사거리(380)가 아니라 킹공성거리(중간값)로 게이팅 → 스폰지점(후방)의 비숍은 킹 직격 안 됨(직격 버그 방지).
    #    전선을 킹 쪽으로 밀면 함락 → 스테이지 클리어(승리 루트 유지). 투사체로 1:1 시각화.
    def emit_king_siege_enemy():
        mx = lambda: l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI))
        in_range = le(op("operator_subtract", vrep("검은킹X", V_ENKX), mx()), vrep("킹공성거리", V_SIEGE))
        in_wall = le(op("operator_subtract", vrep("검은킹X", V_ENKX), mx()), vrep("킹공격거리", V_REACH))
        c_siege = bool_op("operator_or", in_range, in_wall)
        set_tx = b_setvar(bs, "발사목표X", V_FTX, vrep("검은킹X", V_ENKX))
        proj = emit_projectile(mx(), vrep("검은킹X", V_ENKX), 0)
        negd = op("operator_subtract", 0, vrep("계산뎀", V_CALCD))
        dec_en = b_changevar(bs, "검은킹체력", V_ENHP, negd)
        bc_hit = b_broadcast(bs, "검은킹피격", BR_ENHIT)
        pop_c = emit_popup(vrep("계산뎀", V_CALCD), vrep("검은킹X", V_ENKX), 0, 0)
        C(bs, [set_tx] + proj + [dec_en, bc_hit, pop_c])
        return [b_if(bs, c_siege, set_tx)]

    def emit_king_siege_ally():
        mx = lambda: l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI))
        in_range = le(op("operator_subtract", mx(), vrep("하얀킹X", V_MYKX)), vrep("킹공성거리", V_SIEGE))
        in_wall = le(op("operator_subtract", mx(), vrep("하얀킹X", V_MYKX)), vrep("킹공격거리", V_REACH))
        c_siege = bool_op("operator_or", in_range, in_wall)
        set_tx = b_setvar(bs, "발사목표X", V_FTX, vrep("하얀킹X", V_MYKX))
        proj = emit_projectile(mx(), vrep("하얀킹X", V_MYKX), 2)
        negd = op("operator_subtract", 0, vrep("계산뎀", V_CALCD))
        dec_my = b_changevar(bs, "하얀킹체력", V_MYHP, negd)
        bc_hit = b_broadcast(bs, "하얀킹피격", BR_MYHIT)
        pop_c = emit_popup(vrep("계산뎀", V_CALCD), vrep("하얀킹X", V_MYKX), 0, 0)
        C(bs, [set_tx] + proj + [dec_my, bc_hit, pop_c])
        return [b_if(bs, c_siege, set_tx)]

    # ── 아군 한 유닛 처리(전진 or 공격), 타입 분기 ──
    # mode: "single" | "aoe" | "dual"
    def emit_ally_step(type_val, R_id, R_nm, SP_id, SP_nm, ATK_id, ATK_nm, CD_id, CD_nm, mode, ranged):
        xi = l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI))
        diff = op("operator_subtract", vrep("적선두X", V_EFRONTX), xi)
        c_adv = cmp_op("operator_gt", diff, vrep(R_nm, R_id))
        newx = op("operator_add", l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI)), vrep(SP_nm, SP_id))
        repl_adv = l_replace(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI), newx)
        lim = op("operator_subtract", vrep("검은킹X", V_ENKX), vrep("킹공격거리", V_REACH))
        cx = l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI))
        c_over = cmp_op("operator_gt", cx, lim)
        lim2 = op("operator_subtract", vrep("검은킹X", V_ENKX), vrep("킹공격거리", V_REACH))
        repl_clamp = l_replace(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI), lim2)
        if_clamp = b_if(bs, c_over, repl_clamp)
        C(bs, [repl_adv, if_clamp])
        cdcur = l_item(bs, "아군쿨", L_ALLYCD, vrep("루프i", V_LOOPI))
        newcd = op("operator_subtract", cdcur, vrep("시뮬틱", V_TICK))
        repl_cd = l_replace(bs, "아군쿨", L_ALLYCD, vrep("루프i", V_LOOPI), newcd)
        cdr = l_item(bs, "아군쿨", L_ALLYCD, vrep("루프i", V_LOOPI))
        c_ready = le(cdr, 0)
        dmg = op("operator_multiply", vrep(ATK_nm, ATK_id), vrep("유닛공격력배수", V_ATKMUL))
        set_dmg = b_setvar(bs, "계산뎀", V_CALCD, dmg)
        fire_seq = [set_dmg]
        myx_a = lambda: l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI))
        if mode == "single":
            if ranged:   # 비숍: 최전방 적(적선두X)에게 화살 발사(시각) — '보이지 않는 공격' 해소
                fire_seq += emit_projectile(myx_a(), vrep("적선두X", V_EFRONTX), 0)
            else:        # 폰/나이트: 근접 clash
                rnd = op("operator_random", 1, 8, key1="FROM", key2="TO")
                pcl = b_playsound(bs, "clash")
                fire_seq += [b_if(bs, cmp_op("operator_equals", rnd, 1), pcl)]
            fire_seq += emit_single_hit_enemy()
        elif mode == "aoe":
            fire_seq += emit_projectile(myx_a(), vrep("적선두X", V_EFRONTX), 1)   # 룩: 포탄
            fire_seq += emit_aoe_enemy(R_id, R_nm)
        else:  # dual (퀸): 화살+포탄, 단일공격 + 광역공격을 한 쿨에 둘 다
            fire_seq += emit_projectile(myx_a(), vrep("적선두X", V_EFRONTX), 0)
            fire_seq += emit_projectile(myx_a(), vrep("적선두X", V_EFRONTX), 1)
            fire_seq += emit_single_hit_enemy() + emit_aoe_enemy(R_id, R_nm)
        fire_seq += emit_king_siege_enemy()   # 전선을 킹공성거리 안으로 밀면 검은 킹 공성
        reset_cd = l_replace(bs, "아군쿨", L_ALLYCD, vrep("루프i", V_LOOPI), vrep(CD_nm, CD_id))
        fire_seq += [reset_cd]
        C(bs, fire_seq)
        if_fire = b_if(bs, c_ready, set_dmg)
        C(bs, [repl_cd, if_fire])
        ifelse = b_ifelse(bs, c_adv, repl_adv, repl_cd)
        c_type = cmp_op("operator_equals", vrep("계산타입", V_CALCT), type_val)
        return b_if(bs, c_type, ifelse)

    # ── 적 한 유닛 처리(왼쪽으로 전진 or 공격) ──
    def emit_enemy_step(type_val, R_id, R_nm, SP_id, SP_nm, ATK_id, ATK_nm, CD_id, CD_nm, mode, ranged):
        xi = l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI))
        diff = op("operator_subtract", xi, vrep("아군선두X", V_AFRONTX))
        c_adv = cmp_op("operator_gt", diff, vrep(R_nm, R_id))
        newx = op("operator_subtract", l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI)), vrep(SP_nm, SP_id))
        repl_adv = l_replace(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI), newx)
        lim = op("operator_add", vrep("하얀킹X", V_MYKX), vrep("킹공격거리", V_REACH))
        cx = l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI))
        c_over = cmp_op("operator_lt", cx, lim)
        lim2 = op("operator_add", vrep("하얀킹X", V_MYKX), vrep("킹공격거리", V_REACH))
        repl_clamp = l_replace(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI), lim2)
        if_clamp = b_if(bs, c_over, repl_clamp)
        C(bs, [repl_adv, if_clamp])
        cdcur = l_item(bs, "적군쿨", L_ENCD, vrep("루프i", V_LOOPI))
        newcd = op("operator_subtract", cdcur, vrep("시뮬틱", V_TICK))
        repl_cd = l_replace(bs, "적군쿨", L_ENCD, vrep("루프i", V_LOOPI), newcd)
        cdr = l_item(bs, "적군쿨", L_ENCD, vrep("루프i", V_LOOPI))
        c_ready = le(cdr, 0)
        set_dmg = b_setvar(bs, "계산뎀", V_CALCD, vrep(ATK_nm, ATK_id))  # 적은 배수 없음
        fire_seq = [set_dmg]
        myx_e = lambda: l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI))
        if mode == "single":
            if ranged:
                fire_seq += emit_projectile(myx_e(), vrep("아군선두X", V_AFRONTX), 2)
            fire_seq += emit_single_hit_ally()
        elif mode == "aoe":
            fire_seq += emit_projectile(myx_e(), vrep("아군선두X", V_AFRONTX), 3)
            fire_seq += emit_aoe_ally(R_id, R_nm)
        else:  # dual (검은퀸)
            fire_seq += emit_projectile(myx_e(), vrep("아군선두X", V_AFRONTX), 2)
            fire_seq += emit_projectile(myx_e(), vrep("아군선두X", V_AFRONTX), 3)
            fire_seq += emit_single_hit_ally() + emit_aoe_ally(R_id, R_nm)
        fire_seq += emit_king_siege_ally()   # 전선을 킹공성거리 안으로 밀면 하얀 킹 공성
        reset_cd = l_replace(bs, "적군쿨", L_ENCD, vrep("루프i", V_LOOPI), vrep(CD_nm, CD_id))
        fire_seq += [reset_cd]
        C(bs, fire_seq)
        if_fire = b_if(bs, c_ready, set_dmg)
        C(bs, [repl_cd, if_fire])
        ifelse = b_ifelse(bs, c_adv, repl_adv, repl_cd)
        c_type = cmp_op("operator_equals", vrep("계산타입", V_CALCT), type_val)
        return b_if(bs, c_type, ifelse)

    # ============ (A) 시뮬 forever ============
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs)
    C(bs, [h, hi])

    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    hi2 = b_hide(bs)

    # ---- PASS A: 최전방 찾기 ----
    passA = []
    passA.append(b_setvar(bs, "적선두X", V_EFRONTX, vrep("검은킹X", V_ENKX)))
    passA.append(b_setvar(bs, "적선두슬롯", V_EFRONTI, 0))
    passA.append(b_setvar(bs, "루프i", V_LOOPI, 1))
    alive_e = cmp_op("operator_equals", l_item(bs, "적군살아있음", L_ENAL, vrep("루프i", V_LOOPI)), 1)
    xlt = cmp_op("operator_lt", l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI)), vrep("적선두X", V_EFRONTX))
    c_e = bool_op("operator_and", alive_e, xlt)
    se1 = b_setvar(bs, "적선두X", V_EFRONTX, l_item(bs, "적군X", L_ENX, vrep("루프i", V_LOOPI)))
    se2 = b_setvar(bs, "적선두슬롯", V_EFRONTI, vrep("루프i", V_LOOPI))
    C(bs, [se1, se2])
    if_e = b_if(bs, c_e, se1)
    inc_e = b_changevar(bs, "루프i", V_LOOPI, 1)
    C(bs, [if_e, inc_e])
    rep_e = b_repeat(bs, l_length(bs, "적군X", L_ENX), if_e)
    passA.append(rep_e)
    passA.append(b_setvar(bs, "아군선두X", V_AFRONTX, vrep("하얀킹X", V_MYKX)))
    passA.append(b_setvar(bs, "아군선두슬롯", V_AFRONTI, 0))
    passA.append(b_setvar(bs, "루프i", V_LOOPI, 1))
    alive_a = cmp_op("operator_equals", l_item(bs, "아군살아있음", L_ALLYAL, vrep("루프i", V_LOOPI)), 1)
    xgt = cmp_op("operator_gt", l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI)), vrep("아군선두X", V_AFRONTX))
    c_a = bool_op("operator_and", alive_a, xgt)
    sa1 = b_setvar(bs, "아군선두X", V_AFRONTX, l_item(bs, "아군X", L_ALLYX, vrep("루프i", V_LOOPI)))
    sa2 = b_setvar(bs, "아군선두슬롯", V_AFRONTI, vrep("루프i", V_LOOPI))
    C(bs, [sa1, sa2])
    if_a = b_if(bs, c_a, sa1)
    inc_a = b_changevar(bs, "루프i", V_LOOPI, 1)
    C(bs, [if_a, inc_a])
    rep_a = b_repeat(bs, l_length(bs, "아군X", L_ALLYX), if_a)
    passA.append(rep_a)

    # ---- PASS B: 아군 이동+공격 ----
    passB = []
    passB.append(b_setvar(bs, "루프i", V_LOOPI, 1))
    alive_bi = cmp_op("operator_equals", l_item(bs, "아군살아있음", L_ALLYAL, vrep("루프i", V_LOOPI)), 1)
    set_ct = b_setvar(bs, "계산타입", V_CALCT, l_item(bs, "아군타입", L_ALLYT, vrep("루프i", V_LOOPI)))
    st1 = emit_ally_step(1, V_PWR, "폰_사거리", V_PWSP, "폰_속도", V_PWATK, "폰_공격력", V_PWCD, "폰_공속", "single", False)
    st2 = emit_ally_step(2, V_BSR, "비숍_사거리", V_BSSP, "비숍_속도", V_BSATK, "비숍_공격력", V_BSCD, "비숍_공속", "single", True)
    st3 = emit_ally_step(3, V_KNR, "나이트_사거리", V_KNSP, "나이트_속도", V_KNATK, "나이트_공격력", V_KNCD, "나이트_공속", "single", False)
    st4 = emit_ally_step(4, V_RKR, "룩_사거리", V_RKSP, "룩_속도", V_RKATK, "룩_공격력", V_RKCD, "룩_공속", "aoe", True)
    st5 = emit_ally_step(5, V_QNR, "퀸_사거리", V_QNSP, "퀸_속도", V_QNATK, "퀸_공격력", V_QNCD, "퀸_공속", "dual", True)
    C(bs, [set_ct, st1, st2, st3, st4, st5])
    if_bi = b_if(bs, alive_bi, set_ct)
    inc_bi = b_changevar(bs, "루프i", V_LOOPI, 1)
    C(bs, [if_bi, inc_bi])
    rep_b = b_repeat(bs, l_length(bs, "아군X", L_ALLYX), if_bi)
    passB.append(rep_b)

    # ---- PASS C: 적 이동+공격 ----
    passC = []
    passC.append(b_setvar(bs, "루프i", V_LOOPI, 1))
    alive_ci = cmp_op("operator_equals", l_item(bs, "적군살아있음", L_ENAL, vrep("루프i", V_LOOPI)), 1)
    set_ct2 = b_setvar(bs, "계산타입", V_CALCT, l_item(bs, "적군타입", L_ENT, vrep("루프i", V_LOOPI)))
    et1 = emit_enemy_step(1, V_EPR, "적폰_사거리", V_EPSP, "적폰_속도", V_EPATK, "적폰_공격력", V_EPCD, "적폰_공속", "single", False)
    et2 = emit_enemy_step(2, V_EBR, "적비숍_사거리", V_EBSP, "적비숍_속도", V_EBATK, "적비숍_공격력", V_EBCD, "적비숍_공속", "single", True)
    et3 = emit_enemy_step(3, V_ENKR, "적나이트_사거리", V_ENKSP, "적나이트_속도", V_ENKATK, "적나이트_공격력", V_ENKCD, "적나이트_공속", "single", False)
    et4 = emit_enemy_step(4, V_ERR, "적룩_사거리", V_ERSP, "적룩_속도", V_ERATK, "적룩_공격력", V_ERCD, "적룩_공속", "aoe", True)
    et5 = emit_enemy_step(5, V_EQR, "적퀸_사거리", V_EQSP, "적퀸_속도", V_EQATK, "적퀸_공격력", V_EQCD, "적퀸_공속", "dual", True)
    C(bs, [set_ct2, et1, et2, et3, et4, et5])
    if_ci = b_if(bs, alive_ci, set_ct2)
    inc_ci = b_changevar(bs, "루프i", V_LOOPI, 1)
    C(bs, [if_ci, inc_ci])
    rep_c = b_repeat(bs, l_length(bs, "적군X", L_ENX), if_ci)
    passC.append(rep_c)

    sim_body = passA + passB + passC
    C(bs, sim_body)
    st_r = vrep("게임상태", V_STATE); c_play = cmp_op("operator_equals", st_r, 1)
    if_sim = b_if(bs, c_play, sim_body[0])
    w_tick = b_wait_var(bs, V_TICK, "시뮬틱")
    C(bs, [if_sim, w_tick])
    fe_sim = b_forever(bs, if_sim)
    C(bs, [hs, hi2, fe_sim])

    add_comment(bs, comments, rep_e,
        "🔭 제일 앞의 우리 편·적을 찾아요(우리 편=제일 오른쪽 X, 적=제일 왼쪽 X).",
        x=460, y=140, w=330, h=110)
    add_comment(bs, comments, if_bi,
        "🚶 적이 사거리 밖이면 오른쪽으로 전진, 사거리 안이면 멈춰서 공격해요.",
        x=460, y=340, w=330, h=110)
    add_comment(bs, comments, st4,
        "💥 룩·퀸은 사거리 안 적 '전부'를 한꺼번에 때려요(포격)!",
        x=460, y=520, w=330, h=110)
    add_comment(bs, comments, st5,
        "👑 퀸은 비숍의 단일 공격 + 룩의 포격을 '한 번에 둘 다' 쏴요! 그래서 최고 코스트.",
        x=460, y=660, w=330, h=120)

    # ============ (B) 적 스포너 forever ============
    hsp = gen(); bs[hsp] = mk("event_whenbroadcastreceived", top=True, x=980, y=140,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    dec_timer = b_changevar(bs, "적소환타이머", V_ENSPTIMER, -0.1)
    c_t0 = le(vrep("적소환타이머", V_ENSPTIMER), 0)
    c_room = cmp_op("operator_lt", vrep("적군수", V_ENEMYN), vrep("적최대유닛수", V_MAXENEMY))
    c_spawn = bool_op("operator_and", c_t0, c_room)
    # 타입 결정: 스테이지 조합
    c_s1 = le(vrep("스테이지", V_STAGE), 1)
    set_t1 = b_setvar(bs, "적생성타입", V_ENSPAWNT, 1)
    c_s3 = le(vrep("스테이지", V_STAGE), 3)
    r01 = op("operator_random", 0, 1, key1="FROM", key2="TO")
    v01 = op("operator_add", 1, r01)
    set_t2 = b_setvar(bs, "적생성타입", V_ENSPAWNT, v01)
    c_s5 = le(vrep("스테이지", V_STAGE), 5)
    r03 = op("operator_random", 0, 3, key1="FROM", key2="TO")
    v03 = op("operator_add", 1, r03)
    set_t3 = b_setvar(bs, "적생성타입", V_ENSPAWNT, v03)
    # else (6+): if random(1,8)=1 → 5 (검은퀸 보스) else 1+random(0,3)
    r18 = op("operator_random", 1, 8, key1="FROM", key2="TO")
    c_boss = cmp_op("operator_equals", r18, 1)
    set_boss = b_setvar(bs, "적생성타입", V_ENSPAWNT, 5)
    r03b = op("operator_random", 0, 3, key1="FROM", key2="TO")
    v03b = op("operator_add", 1, r03b)
    set_reg = b_setvar(bs, "적생성타입", V_ENSPAWNT, v03b)
    if_boss = b_ifelse(bs, c_boss, set_boss, set_reg)
    if_s5 = b_ifelse(bs, c_s5, set_t3, if_boss)
    if_s3 = b_ifelse(bs, c_s3, set_t2, if_s5)
    if_s1 = b_ifelse(bs, c_s1, set_t1, if_s3)
    # ── 스폰체력 = 체력(타입) × 적배율 (5-branch로 set; reuse/append 공용) ──
    def hp_set(hp_id, hp_nm):
        base = vrep(hp_nm, hp_id)
        prod = op("operator_multiply", base, vrep("적배율", V_SCALECUR))
        return b_setvar(bs, "스폰체력", V_SPAWNHP, prod)
    hs1 = hp_set(V_EPHP, "적폰_체력"); hs2 = hp_set(V_EBHP, "적비숍_체력")
    hs3 = hp_set(V_ENKHP, "적나이트_체력"); hs4 = hp_set(V_ERHP, "적룩_체력"); hs5 = hp_set(V_EQHP, "적퀸_체력")
    if_h4 = b_ifelse(bs, cmp_op("operator_equals", vrep("적생성타입", V_ENSPAWNT), 4), hs4, hs5)
    if_h3 = b_ifelse(bs, cmp_op("operator_equals", vrep("적생성타입", V_ENSPAWNT), 3), hs3, if_h4)
    if_h2 = b_ifelse(bs, cmp_op("operator_equals", vrep("적생성타입", V_ENSPAWNT), 2), hs2, if_h3)
    if_h1 = b_ifelse(bs, cmp_op("operator_equals", vrep("적생성타입", V_ENSPAWNT), 1), hs1, if_h2)
    # ── 죽은 적 슬롯 찾기(replace 만; 리스트 무한 성장 방지) ──
    set_reuse0 = b_setvar(bs, "재사용슬롯", V_REUSE, 0)
    set_k1 = b_setvar(bs, "루프k", V_LOOPK, 1)
    none_yet = cmp_op("operator_equals", vrep("재사용슬롯", V_REUSE), 0)
    dead_k = cmp_op("operator_equals", l_item(bs, "적군살아있음", L_ENAL, vrep("루프k", V_LOOPK)), 0)
    c_reuse = bool_op("operator_and", none_yet, dead_k)
    set_reuse_k = b_setvar(bs, "재사용슬롯", V_REUSE, vrep("루프k", V_LOOPK))
    if_reuse = b_if(bs, c_reuse, set_reuse_k)
    inc_k = b_changevar(bs, "루프k", V_LOOPK, 1)
    C(bs, [if_reuse, inc_k])
    rep_find = b_repeat(bs, l_length(bs, "적군X", L_ENX), if_reuse)
    # reuse 브랜치
    r_x = l_replace(bs, "적군X", L_ENX, vrep("재사용슬롯", V_REUSE), vrep("검은킹X", V_ENKX))
    r_hp = l_replace(bs, "적군HP", L_ENHP, vrep("재사용슬롯", V_REUSE), vrep("스폰체력", V_SPAWNHP))
    r_t = l_replace(bs, "적군타입", L_ENT, vrep("재사용슬롯", V_REUSE), vrep("적생성타입", V_ENSPAWNT))
    r_al = l_replace(bs, "적군살아있음", L_ENAL, vrep("재사용슬롯", V_REUSE), 1)
    r_cd = l_replace(bs, "적군쿨", L_ENCD, vrep("재사용슬롯", V_REUSE), 0)
    r_slot = b_setvar(bs, "새적슬롯", V_NEWENEMY, vrep("재사용슬롯", V_REUSE))
    C(bs, [r_x, r_hp, r_t, r_al, r_cd, r_slot])
    # append 브랜치
    a_x = l_add(bs, "적군X", L_ENX, vrep("검은킹X", V_ENKX))
    a_hp = l_add(bs, "적군HP", L_ENHP, vrep("스폰체력", V_SPAWNHP))
    a_t = l_add(bs, "적군타입", L_ENT, vrep("적생성타입", V_ENSPAWNT))
    a_al = l_add(bs, "적군살아있음", L_ENAL, 1)
    a_cd = l_add(bs, "적군쿨", L_ENCD, 0)
    a_slot = b_setvar(bs, "새적슬롯", V_NEWENEMY, l_length(bs, "적군X", L_ENX))
    C(bs, [a_x, a_hp, a_t, a_al, a_cd, a_slot])
    c_haveslot = cmp_op("operator_gt", vrep("재사용슬롯", V_REUSE), 0)
    if_place = b_ifelse(bs, c_haveslot, r_x, a_x)
    inc_n = b_changevar(bs, "적군수", V_ENEMYN, 1)
    bc_en = b_broadcast_wait(bs, "적소환", BR_ENEMY)
    dec_amt = op("operator_multiply", op("operator_subtract", vrep("스테이지", V_STAGE), 1), vrep("적소환간격감소", V_SPDEC))
    gap = op("operator_subtract", vrep("적소환간격", V_SPGAP), dec_amt)
    set_timer = b_setvar(bs, "적소환타이머", V_ENSPTIMER, gap)
    c_min = cmp_op("operator_lt", vrep("적소환타이머", V_ENSPTIMER), vrep("적소환최소간격", V_SPMIN))
    set_min = b_setvar(bs, "적소환타이머", V_ENSPTIMER, vrep("적소환최소간격", V_SPMIN))
    if_min = b_if(bs, c_min, set_min)
    C(bs, [if_s1, if_h1, set_reuse0, set_k1, rep_find, if_place, inc_n, bc_en, set_timer, if_min])
    if_spawn = b_if(bs, c_spawn, if_s1)
    C(bs, [dec_timer, if_spawn])
    st_sp = vrep("게임상태", V_STATE); c_play_sp = cmp_op("operator_equals", st_sp, 1)
    if_play_sp = b_if(bs, c_play_sp, dec_timer)
    w_sp = b_wait(bs, 0.1)
    C(bs, [if_play_sp, w_sp])
    fe_sp = b_forever(bs, if_play_sp)
    C(bs, [hsp, fe_sp])
    add_comment(bs, comments, if_spawn,
        "♟️ 스테이지가 오를수록 검은 군단 종류가 늘고(6스테이지부턴 검은 퀸 보스!), 체력은 ×적배율 로 세져요.",
        x=1400, y=140, w=340, h=130)

    return bs, comments

# ============================================================
#  아군유닛 / 적군유닛 (렌더러 — 위치·모습만)
# ============================================================
def build_unit_blocks(is_ally):
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    if is_ally:
        ISC, SLOT = V_ALLY_ISC, V_ALLY_SLOT
        L_X, X_nm = L_ALLYX, "아군X"
        L_T, T_nm = L_ALLYT, "아군타입"
        L_AL, AL_nm = L_ALLYAL, "아군살아있음"
        recv, recv_id = "아군소환", BR_ALLY
        new_nm, new_id = "새아군슬롯", V_NEWALLY
        costumes = [("폰", 55), ("비숍", 58), ("나이트", 70), ("룩", 68), ("퀸", 72)]
    else:
        ISC, SLOT = V_EN_ISC, V_EN_SLOT
        L_X, X_nm = L_ENX, "적군X"
        L_T, T_nm = L_ENT, "적군타입"
        L_AL, AL_nm = L_ENAL, "적군살아있음"
        recv, recv_id = "적소환", BR_ENEMY
        new_nm, new_id = "새적슬롯", V_NEWENEMY
        costumes = [("검은폰", 55), ("검은비숍", 58), ("검은나이트", 70), ("검은룩", 68), ("검은퀸", 72)]

    def slot_y():
        modv = op("operator_mod", vrep("슬롯", SLOT), 3)
        off = op("operator_subtract", modv, 1)
        return op("operator_add", vrep("레인Y", V_LANEY), off)

    # (A) 깃발
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_norot(bs)
    orig0 = b_setvar(bs, "복제됨", ISC, 0)
    pd = b_pointdir(bs, 90)
    C(bs, [h, hi, rs, orig0, pd])

    # (B) 소환 수신 → 클론 1기 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": [recv, recv_id]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", ISC), 0)
    cc = b_createclone(bs)
    if_c = b_if(bs, c_orig, cc)
    C(bs, [hb, if_c])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", ISC, 1)
    set_slot = b_setvar(bs, "슬롯", SLOT, vrep(new_nm, new_id))
    def cbranch(idx):
        nm, sz = costumes[idx]
        sw = b_costume(bs, nm); szb = b_setsize(bs, sz)
        C(bs, [sw, szb])
        return sw
    b5 = cbranch(4); b4 = cbranch(3); b3 = cbranch(2); b2 = cbranch(1); b1 = cbranch(0)
    t_r = lambda: l_item(bs, T_nm, L_T, vrep("슬롯", SLOT))
    if_c4 = b_ifelse(bs, cmp_op("operator_equals", t_r(), 4), b4, b5)
    if_c3 = b_ifelse(bs, cmp_op("operator_equals", t_r(), 3), b3, if_c4)
    if_c2 = b_ifelse(bs, cmp_op("operator_equals", t_r(), 2), b2, if_c3)
    if_c1 = b_ifelse(bs, cmp_op("operator_equals", t_r(), 1), b1, if_c2)
    g1 = b_gotoxy(bs, l_item(bs, X_nm, L_X, vrep("슬롯", SLOT)), slot_y())
    sh = b_show(bs)
    st_ne1 = b_not(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    del1 = b_delclone(bs)
    if_ne1 = b_if(bs, st_ne1, del1)
    c_dead = cmp_op("operator_equals", l_item(bs, AL_nm, L_AL, vrep("슬롯", SLOT)), 0)
    sw_boom = b_costume(bs, "폭죽")
    ph, pp = b_sound(bs, 0, "death")
    cs = b_changesize(bs, 8); ce = b_changeeffect(bs, "GHOST", 20); wboom = b_wait(bs, 0.02)
    C(bs, [cs, ce, wboom])
    rep_boom = b_repeat(bs, 5, cs)
    del2 = b_delclone(bs)
    C(bs, [sw_boom, ph, pp, rep_boom, del2])
    if_dead = b_if(bs, c_dead, sw_boom)
    g2 = b_gotoxy(bs, l_item(bs, X_nm, L_X, vrep("슬롯", SLOT)), slot_y())
    wtick = b_wait(bs, 0.02)
    C(bs, [if_ne1, if_dead, g2, wtick])
    fe = b_forever(bs, if_ne1)
    C(bs, [ch, set1, set_slot, if_c1, g1, sh, fe])

    add_comment(bs, comments, if_c1,
        "🎭 이 클론은 계산은 안 하고 리스트가 정해준 자리·모습만 그려요.",
        x=460, y=380, w=320, h=110)

    return bs, comments

# ============================================================
#  소환버튼 (마우스 폴링 5칸 — 이 스프라이트 클릭했을 때 금지)
# ============================================================
def build_button_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # (A) 깃발
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sh = b_show(bs); g = b_gotoxy(bs, 0, -150); sz = b_setsize(bs, 100)
    fr = b_front(bs); rs = b_norot(bs)
    C(bs, [h, sh, g, sz, fr, rs])

    def emit_summon(type_val, cost_id, cost_nm, cdt_id, cdt_nm, sum_id, sum_nm,
                    hp_id, hp_nm, unlock_id, unlock_nm, pitch):
        gold_ok = b_not(bs, cmp_op("operator_lt", vrep("골드", V_GOLD), vrep(cost_nm, cost_id)))
        cd_ok = b_not(bs, cmp_op("operator_gt", vrep(cdt_nm, cdt_id), 0))
        n_ok = cmp_op("operator_lt", vrep("아군수", V_ALLYN), vrep("최대유닛수", V_MAXALLY))
        base = bool_op("operator_and", gold_ok, cd_ok)
        base2 = bool_op("operator_and", base, n_ok)
        if unlock_id is None:
            cond = base2
        else:
            unlock_ok = cmp_op("operator_equals", vrep(unlock_nm, unlock_id), 1)
            cond = bool_op("operator_and", base2, unlock_ok)
        negc = op("operator_subtract", 0, vrep(cost_nm, cost_id))
        dec_g = b_changevar(bs, "골드", V_GOLD, negc)
        # ── 죽은 슬롯 찾기(메모리 상한: 리스트 무한 성장 방지 — replace 만 사용, 인덱스 불변) ──
        set_reuse0 = b_setvar(bs, "재사용슬롯", V_REUSE, 0)
        set_k1 = b_setvar(bs, "루프k", V_LOOPK, 1)
        none_yet = cmp_op("operator_equals", vrep("재사용슬롯", V_REUSE), 0)
        dead_k = cmp_op("operator_equals", l_item(bs, "아군살아있음", L_ALLYAL, vrep("루프k", V_LOOPK)), 0)
        c_reuse = bool_op("operator_and", none_yet, dead_k)
        set_reuse_k = b_setvar(bs, "재사용슬롯", V_REUSE, vrep("루프k", V_LOOPK))
        if_reuse = b_if(bs, c_reuse, set_reuse_k)
        inc_k = b_changevar(bs, "루프k", V_LOOPK, 1)
        C(bs, [if_reuse, inc_k])
        rep_find = b_repeat(bs, l_length(bs, "아군X", L_ALLYX), if_reuse)
        # reuse 브랜치: replace 5리스트
        hp_expr_r = op("operator_multiply", vrep(hp_nm, hp_id), vrep("유닛체력배수", V_HPMUL))
        r_x = l_replace(bs, "아군X", L_ALLYX, vrep("재사용슬롯", V_REUSE), op("operator_add", vrep("하얀킹X", V_MYKX), 25))
        r_hp = l_replace(bs, "아군HP", L_ALLYHP, vrep("재사용슬롯", V_REUSE), hp_expr_r)
        r_t = l_replace(bs, "아군타입", L_ALLYT, vrep("재사용슬롯", V_REUSE), type_val)
        r_al = l_replace(bs, "아군살아있음", L_ALLYAL, vrep("재사용슬롯", V_REUSE), 1)
        r_cd = l_replace(bs, "아군쿨", L_ALLYCD, vrep("재사용슬롯", V_REUSE), 0)
        r_slot = b_setvar(bs, "새아군슬롯", V_NEWALLY, vrep("재사용슬롯", V_REUSE))
        C(bs, [r_x, r_hp, r_t, r_al, r_cd, r_slot])
        # append 브랜치: add 5리스트
        hp_expr_a = op("operator_multiply", vrep(hp_nm, hp_id), vrep("유닛체력배수", V_HPMUL))
        a_x = l_add(bs, "아군X", L_ALLYX, op("operator_add", vrep("하얀킹X", V_MYKX), 25))
        a_hp = l_add(bs, "아군HP", L_ALLYHP, hp_expr_a)
        a_t = l_add(bs, "아군타입", L_ALLYT, type_val)
        a_al = l_add(bs, "아군살아있음", L_ALLYAL, 1)
        a_cd = l_add(bs, "아군쿨", L_ALLYCD, 0)
        a_slot = b_setvar(bs, "새아군슬롯", V_NEWALLY, l_length(bs, "아군X", L_ALLYX))
        C(bs, [a_x, a_hp, a_t, a_al, a_cd, a_slot])
        c_haveslot = cmp_op("operator_gt", vrep("재사용슬롯", V_REUSE), 0)
        if_place = b_ifelse(bs, c_haveslot, r_x, a_x)
        set_type = b_setvar(bs, "소환타입", V_SUMTYPE, type_val)
        inc_n = b_changevar(bs, "아군수", V_ALLYN, 1)
        sh_s, sp_s = b_sound(bs, pitch, "summon")
        bc = b_broadcast_wait(bs, "아군소환", BR_ALLY)
        set_cd = b_setvar(bs, cdt_nm, cdt_id, vrep(sum_nm, sum_id))
        C(bs, [dec_g, set_reuse0, set_k1, rep_find, if_place, set_type, inc_n, sh_s, sp_s, bc, set_cd])
        eh, ep = b_sound(bs, 0, "error")
        return b_ifelse(bs, cond, dec_g, eh)

    # (B) 게임시작 forever
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # 코스튬(해금 상태 순차): 시작잠금/나이트해금/룩해금/모두해금
    c_kn0 = cmp_op("operator_equals", vrep("나이트해금", V_UNKN), 0)
    sw_lock = b_costume(bs, "시작잠금")
    c_rk0 = cmp_op("operator_equals", vrep("룩해금", V_UNRK), 0)
    sw_kn = b_costume(bs, "나이트해금")
    c_qn0 = cmp_op("operator_equals", vrep("퀸해금", V_UNQN), 0)
    sw_rk = b_costume(bs, "룩해금")
    sw_all = b_costume(bs, "모두해금")
    if_qn = b_ifelse(bs, c_qn0, sw_rk, sw_all)
    if_rk = b_ifelse(bs, c_rk0, sw_kn, if_qn)
    if_cost = b_ifelse(bs, c_kn0, sw_lock, if_rk)
    # 쿨 감소 (5)
    d1 = b_changevar(bs, "폰쿨타이머", V_SUMT1, -0.02)
    d2 = b_changevar(bs, "비숍쿨타이머", V_SUMT2, -0.02)
    d3 = b_changevar(bs, "나이트쿨타이머", V_SUMT3, -0.02)
    d4 = b_changevar(bs, "룩쿨타이머", V_SUMT4, -0.02)
    d5 = b_changevar(bs, "퀸쿨타이머", V_SUMT5, -0.02)
    # 폴링 조건
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_md = b_mousedown(bs)
    c_my = cmp_op("operator_lt", b_mousey(bs), -120)
    c_pm = bool_op("operator_and", c_play, c_md)
    c_poll = bool_op("operator_and", c_pm, c_my)
    # x영역 5등분: -240..-144..-48..48..144..240
    su1 = emit_summon(1, V_COSTPW, "폰코스트", V_SUMT1, "폰쿨타이머", V_PWSUM, "폰_소환쿨",
                      V_PWHP, "폰_체력", None, None, 0)
    su2 = emit_summon(2, V_COSTBS, "비숍코스트", V_SUMT2, "비숍쿨타이머", V_BSSUM, "비숍_소환쿨",
                      V_BSHP, "비숍_체력", None, None, 20)
    su3 = emit_summon(3, V_COSTKN, "나이트코스트", V_SUMT3, "나이트쿨타이머", V_KNSUM, "나이트_소환쿨",
                      V_KNHP, "나이트_체력", V_UNKN, "나이트해금", -20)
    su4 = emit_summon(4, V_COSTRK, "룩코스트", V_SUMT4, "룩쿨타이머", V_RKSUM, "룩_소환쿨",
                      V_RKHP, "룩_체력", V_UNRK, "룩해금", -40)
    su5 = emit_summon(5, V_COSTQN, "퀸코스트", V_SUMT5, "퀸쿨타이머", V_QNSUM, "퀸_소환쿨",
                      V_QNHP, "퀸_체력", V_UNQN, "퀸해금", 40)
    c_x1 = cmp_op("operator_lt", b_mousex(bs), -144)
    c_x2 = cmp_op("operator_lt", b_mousex(bs), -48)
    c_x3 = cmp_op("operator_lt", b_mousex(bs), 48)
    c_x4 = cmp_op("operator_lt", b_mousex(bs), 144)
    if_x4 = b_ifelse(bs, c_x4, su4, su5)
    if_x3 = b_ifelse(bs, c_x3, su3, if_x4)
    if_x2 = b_ifelse(bs, c_x2, su2, if_x3)
    if_x1 = b_ifelse(bs, c_x1, su1, if_x2)
    wu = b_waituntil(bs, b_not(bs, b_mousedown(bs)))
    C(bs, [if_x1, wu])
    if_poll = b_if(bs, c_poll, if_x1)
    # ── 화면 표시용 유닛 = join(아군수, "/", 최대유닛수) (n/12) ──
    inner = gen(); bs[inner] = mk("operator_join",
        inputs={"STRING1": [1, [10, "/"]], "STRING2": slot(vrep("최대유닛수", V_MAXALLY))})
    bs[bs[inner]["inputs"]["STRING2"][1]]["parent"] = inner
    outer = gen(); bs[outer] = mk("operator_join",
        inputs={"STRING1": slot(vrep("아군수", V_ALLYN)), "STRING2": slot(inner)})
    bs[bs[outer]["inputs"]["STRING1"][1]]["parent"] = outer
    bs[inner]["parent"] = outer
    set_units = b_setvar(bs, "유닛", V_UNITS, outer)
    w = b_wait(bs, 0.02)
    C(bs, [if_cost, d1, d2, d3, d4, d5, set_units, if_poll, w])
    fe = b_forever(bs, if_cost)
    C(bs, [hb, fe])

    add_comment(bs, comments, if_poll,
        "🖱️ 버튼은 '마우스를 클릭했나'로 감지해요(다른 게 가려도 눌려요). 한 번 누르면 한 번만 소환!",
        x=460, y=340, w=340, h=120)

    return bs, comments

# ============================================================
#  숫자팝업 (플로팅 데미지/골드 — say 미사용)
# ============================================================
def build_popup_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); orig0 = b_setvar(bs, "복제됨", V_POP_ISC, 0); rs = b_norot(bs)
    C(bs, [h, hi, orig0, rs])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["데미지표시", BR_DMG]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_POP_ISC), 0)
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
    cc = b_createclone(bs)
    inc_pos = b_changevar(bs, "데미지자리", V_DMGPOS, 1)
    w_sp = b_wait(bs, 0.02)
    C(bs, [set_digit, set_off, cc, inc_pos, w_sp])
    rep = b_repeat(bs, vrep("데미지글자수", V_DMGLEN), set_digit)
    C(bs, [set_len, set_pos1, rep])
    if_spawn = b_if(bs, c_orig, set_len)
    C(bs, [hb, if_spawn])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=440)
    set1 = b_setvar(bs, "복제됨", V_POP_ISC, 1)
    fr = b_front(bs); sz = b_setsize(bs, 100)
    k10 = op("operator_multiply", vrep("팝업종류", V_DMGKIND), 10)
    sum1 = op("operator_add", vrep("데미지숫자", V_DMGDIG), k10)
    idx = op("operator_add", sum1, 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(idx)})
    bs[idx]["parent"] = sw
    dx_r = vrep("데미지표시x", V_DMGX); off_r = vrep("데미지오프셋", V_DMGOFF)
    x_pos = op("operator_add", dx_r, off_r)
    g = b_gotoxy(bs, x_pos, vrep("데미지표시y", V_DMGY))
    clr = b_seteffect(bs, "GHOST", 0)
    sh = b_show(bs)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": num(4)})
    cg = b_changeeffect(bs, "GHOST", 8); w_an = b_wait(bs, 0.02)
    C(bs, [chy, cg, w_an])
    rep_an = b_repeat(bs, 12, chy)
    delc = b_delclone(bs)
    C(bs, [ch, set1, fr, sz, sw, g, clr, sh, rep_an, delc])

    return bs, comments

# ============================================================
#  강화카드 (1/2/3/4 키로 강화 택1 → 다음 스테이지)
# ============================================================
def build_card_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g = b_gotoxy(bs, 0, 20); sz = b_setsize(bs, 100)
    fr = b_front(bs); rs = b_norot(bs)
    C(bs, [h, hi, g, sz, fr, rs])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["스테이지클리어", BR_CLEAR]})
    sh = b_show(bs)
    k1 = b_keypressed(bs, "1"); k2 = b_keypressed(bs, "2")
    k3 = b_keypressed(bs, "3"); k4 = b_keypressed(bs, "4")
    or12 = bool_op("operator_or", k1, k2); or123 = bool_op("operator_or", or12, k3)
    or1234 = bool_op("operator_or", or123, k4)
    wu = b_waituntil(bs, or1234)
    ch_gr = b_changevar(bs, "초당골드", V_GOLDRATE, vrep("강화골드증가", V_UPGOLD))
    if_k1 = b_if(bs, b_keypressed(bs, "1"), ch_gr)
    atk_mul = op("operator_multiply", vrep("유닛공격력배수", V_ATKMUL), vrep("강화공격배수", V_UPATK))
    set_atk = b_setvar(bs, "유닛공격력배수", V_ATKMUL, atk_mul)
    if_k2 = b_if(bs, b_keypressed(bs, "2"), set_atk)
    hp_mul = op("operator_multiply", vrep("유닛체력배수", V_HPMUL), vrep("강화체력배수", V_UPHP))
    set_hp = b_setvar(bs, "유닛체력배수", V_HPMUL, hp_mul)
    if_k3 = b_if(bs, b_keypressed(bs, "3"), set_hp)
    ch_max = b_changevar(bs, "하얀킹최대체력", V_KINGMAX, vrep("강화킹수리", V_UPREPAIR))
    set_full = b_setvar(bs, "하얀킹체력", V_MYHP, vrep("하얀킹최대체력", V_KINGMAX))
    C(bs, [ch_max, set_full])
    if_k4 = b_if(bs, b_keypressed(bs, "4"), ch_max)
    sh_up, sp_up = b_sound(bs, 0, "upgrade")
    hi2 = b_hide(bs); w1 = b_wait(bs, 0.15)
    inc_stage = b_changevar(bs, "스테이지", V_STAGE, 1)
    set_scale1 = b_setvar(bs, "적배율", V_SCALECUR, 1)
    mul_scale = op("operator_multiply", vrep("적배율", V_SCALECUR), vrep("적성장배율", V_SCALE))
    set_scale_step = b_setvar(bs, "적배율", V_SCALECUR, mul_scale)
    reps = op("operator_subtract", vrep("스테이지", V_STAGE), 1)
    rep_scale = b_repeat(bs, reps, set_scale_step)
    enhp = op("operator_multiply", vrep("검은킹기본체력", V_ENKINGBASE), vrep("적배율", V_SCALECUR))
    set_enhp = b_setvar(bs, "검은킹체력", V_ENHP, enhp)
    c_kn = b_not(bs, cmp_op("operator_lt", vrep("스테이지", V_STAGE), vrep("나이트해금스테이지", V_UNLKKN)))
    set_unkn = b_setvar(bs, "나이트해금", V_UNKN, 1)
    if_kn = b_if(bs, c_kn, set_unkn)
    c_rk = b_not(bs, cmp_op("operator_lt", vrep("스테이지", V_STAGE), vrep("룩해금스테이지", V_UNLKRK)))
    set_unrk = b_setvar(bs, "룩해금", V_UNRK, 1)
    if_rk = b_if(bs, c_rk, set_unrk)
    c_qn = b_not(bs, cmp_op("operator_lt", vrep("스테이지", V_STAGE), vrep("퀸해금스테이지", V_UNLKQN)))
    set_unqn = b_setvar(bs, "퀸해금", V_UNQN, 1)
    if_qn = b_if(bs, c_qn, set_unqn)
    dels = []
    for nm, lid in [("아군X", L_ALLYX), ("아군HP", L_ALLYHP), ("아군타입", L_ALLYT),
                    ("아군살아있음", L_ALLYAL), ("아군쿨", L_ALLYCD),
                    ("적군X", L_ENX), ("적군HP", L_ENHP), ("적군타입", L_ENT),
                    ("적군살아있음", L_ENAL), ("적군쿨", L_ENCD)]:
        dels.append(l_delall(bs, nm, lid))
    set_an = b_setvar(bs, "아군수", V_ALLYN, 0)
    set_en = b_setvar(bs, "적군수", V_ENEMYN, 0)
    set_timer = b_setvar(bs, "적소환타이머", V_ENSPTIMER, 0)
    set_acc = b_setvar(bs, "골드누적", V_GOLDACC, 0)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    bc_go = b_broadcast(bs, "스테이지시작", BR_STAGEGO)
    bc_done = b_broadcast(bs, "강화완료", BR_UPDONE)
    tail = [inc_stage, set_scale1, rep_scale, set_enhp, if_kn, if_rk, if_qn] + dels + \
           [set_an, set_en, set_timer, set_acc, set_st1, bc_go, bc_done]
    C(bs, [hb, sh, wu, if_k1, if_k2, if_k3, if_k4, sh_up, sp_up, hi2, w1] + tail)

    add_comment(bs, comments, hb,
        "⬆️ 1·2·3·4 키로 강화를 골라요. 적이 곱하기로 세지니 좋은 강화로 따라잡아요!\n"
        "1 초당골드+ · 2 공격력+ · 3 체력+ · 4 킹수리.",
        x=460, y=200, w=340, h=140)
    add_comment(bs, comments, set_scale1,
        "📈 적배율 = 적성장배율^(스테이지−1) 을 곱셈 반복으로 계산해요. 지수(곱하기)로 세지는 게 핵심!",
        x=460, y=440, w=340, h=120)

    return bs, comments

# ============================================================
#  게임오버 (GAME OVER 배너)
# ============================================================
def build_gameover_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g = b_gotoxy(bs, 0, 0); sz = b_setsize(bs, 100)
    fr = b_front(bs); rs = b_norot(bs)
    c1 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    wu1 = b_waituntil(bs, c1)
    c0 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    wu2 = b_waituntil(bs, c0)
    sh = b_show(bs)
    C(bs, [h, hi, g, sz, fr, rs, wu1, wu2, sh])
    return bs, comments

# ============================================================
#  쿨오버레이 (버튼 상태: 재충전/골드부족/상한/잠금 — 버튼 위 반투명 클론 5기)
# ============================================================
def build_overlay_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    def seteffect_r(eff, valexpr):
        bid = gen()
        ins = {"VALUE": slot(valexpr) if (isinstance(valexpr, str) and valexpr in bs) else num(valexpr)}
        bs[bid] = mk("looks_seteffectto", inputs=ins, fields={"EFFECT": [eff, None]})
        if isinstance(valexpr, str) and valexpr in bs: bs[valexpr]["parent"] = bid
        return bid

    # 한 슬롯의 상태 결정 체인(head 반환). unlock_id None = 항상 해금(폰/비숍).
    def emit_state(cool_id, cool_nm, cost_id, cost_nm, sum_id, sum_nm, unlock_id, unlock_nm):
        # cooldown 브랜치
        cd_gt0 = cmp_op("operator_gt", vrep(cool_nm, cool_id), 0)
        sw_cd = b_costume(bs, "재충전")
        ratio = op("operator_divide", vrep(cool_nm, cool_id), vrep(sum_nm, sum_id))
        ratio100 = op("operator_multiply", ratio, 100)
        gh = op("operator_subtract", 100, ratio100)
        set_gh = seteffect_r("GHOST", gh)
        sh_cd = b_show(bs)
        C(bs, [sw_cd, set_gh, sh_cd])
        # cap 브랜치
        cap = b_not(bs, cmp_op("operator_lt", vrep("아군수", V_ALLYN), vrep("최대유닛수", V_MAXALLY)))
        sw_cap = b_costume(bs, "가득참"); gh_cap = b_seteffect(bs, "GHOST", 20); sh_cap = b_show(bs)
        C(bs, [sw_cap, gh_cap, sh_cap])
        # gold 브랜치
        gold_low = cmp_op("operator_lt", vrep("골드", V_GOLD), vrep(cost_nm, cost_id))
        sw_gd = b_costume(bs, "골드"); gh_gd = b_seteffect(bs, "GHOST", 35); sh_gd = b_show(bs)
        C(bs, [sw_gd, gh_gd, sh_gd])
        hide_ready = b_hide(bs)
        if_gold = b_ifelse(bs, gold_low, sw_gd, hide_ready)
        if_cap = b_ifelse(bs, cap, sw_cap, if_gold)
        if_cd = b_ifelse(bs, cd_gt0, sw_cd, if_cap)
        if unlock_id is None:
            return if_cd
        # locked 브랜치(가장 바깥)
        locked = cmp_op("operator_equals", vrep(unlock_nm, unlock_id), 0)
        sw_lk = b_costume(bs, "잠금"); gh_lk = b_seteffect(bs, "GHOST", 25); sh_lk = b_show(bs)
        C(bs, [sw_lk, gh_lk, sh_lk])
        return b_ifelse(bs, locked, sw_lk, if_cd)

    # (A) 깃발
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_norot(bs); orig0 = b_setvar(bs, "복제됨", V_OV_ISC, 0)
    C(bs, [h, hi, rs, orig0])

    # (B) 게임시작 → 원본이 5기 클론(오버레이카운터로 슬롯 배정)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_OV_ISC), 0)
    set_cnt0 = b_setvar(bs, "오버레이카운터", V_OVCOUNT, 0)
    cc = b_createclone(bs)
    rep5 = b_repeat(bs, 5, cc)
    C(bs, [set_cnt0, rep5])
    if_spawn = b_if(bs, c_orig, set_cnt0)
    C(bs, [hb, if_spawn])

    # (C) 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_OV_ISC, 1)
    inc_cnt = b_changevar(bs, "오버레이카운터", V_OVCOUNT, 1)
    set_slot = b_setvar(bs, "슬롯", V_OV_SLOT, vrep("오버레이카운터", V_OVCOUNT))
    fr = b_front(bs)
    # goto ((슬롯-3)*96, -150)
    bx = op("operator_multiply", op("operator_subtract", vrep("슬롯", V_OV_SLOT), 3), 96)
    g = b_gotoxy(bs, bx, -150)
    sz = b_setsize(bs, 100)
    # forever: 슬롯별 상태 렌더
    s1 = emit_state(V_SUMT1, "폰쿨타이머", V_COSTPW, "폰코스트", V_PWSUM, "폰_소환쿨", None, None)
    s2 = emit_state(V_SUMT2, "비숍쿨타이머", V_COSTBS, "비숍코스트", V_BSSUM, "비숍_소환쿨", None, None)
    s3 = emit_state(V_SUMT3, "나이트쿨타이머", V_COSTKN, "나이트코스트", V_KNSUM, "나이트_소환쿨", V_UNKN, "나이트해금")
    s4 = emit_state(V_SUMT4, "룩쿨타이머", V_COSTRK, "룩코스트", V_RKSUM, "룩_소환쿨", V_UNRK, "룩해금")
    s5 = emit_state(V_SUMT5, "퀸쿨타이머", V_COSTQN, "퀸코스트", V_QNSUM, "퀸_소환쿨", V_UNQN, "퀸해금")
    if_b4 = b_ifelse(bs, cmp_op("operator_equals", vrep("슬롯", V_OV_SLOT), 4), s4, s5)
    if_b3 = b_ifelse(bs, cmp_op("operator_equals", vrep("슬롯", V_OV_SLOT), 3), s3, if_b4)
    if_b2 = b_ifelse(bs, cmp_op("operator_equals", vrep("슬롯", V_OV_SLOT), 2), s2, if_b3)
    if_b1 = b_ifelse(bs, cmp_op("operator_equals", vrep("슬롯", V_OV_SLOT), 1), s1, if_b2)
    w = b_wait(bs, 0.05)
    C(bs, [if_b1, w])
    fe = b_forever(bs, if_b1)
    C(bs, [ch, set1, inc_cnt, set_slot, fr, g, sz, fe])

    add_comment(bs, comments, if_b1,
        "🔋 버튼 위에 겹쳐서 상태를 보여줘요: 재충전(파랑, 차오르며 사라짐)·골드부족(회색)·"
        "유닛 가득참(빨강)·잠금(어두움). 준비되면 사라져요.",
        x=460, y=380, w=340, h=140)

    return bs, comments

# ============================================================
#  투사체 (총알/포탄 — 시각 전용, 공격마다 발사자→타겟 비행 후 소멸)
# ============================================================
def build_projectile_blocks():
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_norot(bs); orig0 = b_setvar(bs, "복제됨", V_PROJ_ISC, 0)
    C(bs, [h, hi, rs, orig0])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_PROJ_ISC), 0)
    cc = b_createclone(bs)
    if_c = b_if(bs, c_orig, cc)
    C(bs, [hb, if_c])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_PROJ_ISC, 1)
    cap_sx = b_setvar(bs, "시작X", V_PROJ_SX, vrep("발사X", V_FX))
    cap_tx = b_setvar(bs, "목표X", V_PROJ_TX, vrep("발사목표X", V_FTX))
    cap_k = b_setvar(bs, "종류", V_PROJ_KIND, vrep("발사종류", V_FKIND))
    cidx = op("operator_add", vrep("종류", V_PROJ_KIND), 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(cidx)})
    bs[cidx]["parent"] = sw
    fr = b_front(bs)
    yv = op("operator_add", vrep("레인Y", V_LANEY), 10)
    g0 = b_gotoxy(bs, vrep("시작X", V_PROJ_SX), yv)
    sh = b_show(bs); set_t0 = b_setvar(bs, "진행", V_PROJ_T, 0)
    inc_t = b_changevar(bs, "진행", V_PROJ_T, 0.14)
    span = op("operator_subtract", vrep("목표X", V_PROJ_TX), vrep("시작X", V_PROJ_SX))
    prog = op("operator_multiply", span, vrep("진행", V_PROJ_T))
    curx = op("operator_add", vrep("시작X", V_PROJ_SX), prog)
    yv2 = op("operator_add", vrep("레인Y", V_LANEY), 10)
    gmove = b_gotoxy(bs, curx, yv2)
    w = b_wait(bs, 0.02)
    C(bs, [inc_t, gmove, w])
    rep = b_repeat(bs, 7, inc_t)
    delc = b_delclone(bs)
    C(bs, [ch, set1, cap_sx, cap_tx, cap_k, sw, fr, g0, sh, set_t0, rep, delc])

    add_comment(bs, comments, ch,
        "🏹 총알/포탄은 시각 전용이에요. 공격할 때 발사자 위치에서 클론이 생겨 타겟 X 로 "
        "빠르게 날아가 사라져요(데미지는 매니저가 처리). 과부하 방지로 1/2 확률로만 나와요.",
        x=460, y=380, w=340, h=140)

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

    bg_md5   = save_svg(BG_SVG)
    kw_md5   = save_svg(KING_WHITE_SVG)
    kb_md5   = save_svg(KING_BLACK_SVG)
    pw_md5   = save_svg(PAWN_SVG)
    bs_md5   = save_svg(BISHOP_SVG)
    kn_md5   = save_svg(KNIGHT_SVG)
    rk_md5   = save_svg(ROOK_SVG)
    qn_md5   = save_svg(QUEEN_SVG)
    bpw_md5  = save_svg(BPAWN_SVG)
    bbs_md5  = save_svg(BBISHOP_SVG)
    bkn_md5  = save_svg(BKNIGHT_SVG)
    brk_md5  = save_svg(BROOK_SVG)
    bqn_md5  = save_svg(BQUEEN_SVG)
    boom_md5 = save_svg(BOOM_SVG)
    bar_md5  = [save_svg(s) for s in BAR_SVGS]
    ov_md5   = [save_svg(s) for s in OVERLAY_SVGS]
    proj_md5 = [save_svg(s) for s in PROJ_SVGS]
    card_md5 = save_svg(CARD_SVG)
    rs_md5   = save_svg(RESULT_SVG)
    inv_md5  = save_svg(INVIS_SVG)
    wd_md5   = [save_svg(s) for s in WHITE_DIGITS]
    gd_md5   = [save_svg(s) for s in GOLD_DIGITS]

    def save_wav(samples):
        b = _wav_bytes(samples)
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    summon_s, summon_n = save_wav(synth_summon())
    error_s, error_n = save_wav(synth_error())
    clash_s, clash_n = save_wav(synth_clash())
    cannon_s, cannon_n = save_wav(synth_cannon())
    death_s, death_n = save_wav(synth_death())
    coin_s, coin_n = save_wav(synth_coin())
    kinghit_s, kinghit_n = save_wav(synth_kinghit())
    break_s, break_n = save_wav(synth_break())
    horn_s, horn_n = save_wav(synth_horn())
    upgrade_s, upgrade_n = save_wav(synth_upgrade())

    def snd(name, md5, n):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "",
                "rate": SND_RATE, "sampleCount": n, "md5ext": f"{md5}.wav"}

    def cos(name, md5, rx=30, ry=30):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": md5, "md5ext": f"{md5}.svg", "rotationCenterX": rx, "rotationCenterY": ry}

    stage_blocks, stage_cmt = build_stage_blocks()
    myk_blocks, myk_cmt = build_king_blocks(True)
    enk_blocks, enk_cmt = build_king_blocks(False)
    mgr_blocks, mgr_cmt = build_manager_blocks()
    ally_blocks, ally_cmt = build_unit_blocks(True)
    enemy_blocks, enemy_cmt = build_unit_blocks(False)
    btn_blocks, btn_cmt = build_button_blocks()
    pop_blocks, pop_cmt = build_popup_blocks()
    card_blocks, card_cmt = build_card_blocks()
    go_blocks, go_cmt = build_gameover_blocks()
    ov_blocks, ov_cmt = build_overlay_blocks()
    proj_blocks, proj_cmt = build_projectile_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 84
            V_STARTGOLD: ["시작골드", 200], V_GOLDRATE: ["초당골드", 14], V_KILLGOLD: ["처치골드", 3],
            V_CLEARGOLD: ["스테이지클리어골드", 50], V_COSTPW: ["폰코스트", 18], V_COSTBS: ["비숍코스트", 30],
            V_COSTKN: ["나이트코스트", 45], V_COSTRK: ["룩코스트", 70], V_COSTQN: ["퀸코스트", 110],
            V_MAXALLY: ["최대유닛수", 12], V_MAXENEMY: ["적최대유닛수", 12], V_KINGMAX: ["하얀킹최대체력", 100],
            V_ENKINGBASE: ["검은킹기본체력", 120], V_SCALE: ["적성장배율", 1.25], V_UNLKKN: ["나이트해금스테이지", 2],
            V_UNLKRK: ["룩해금스테이지", 3], V_UNLKQN: ["퀸해금스테이지", 4],
            V_TICK: ["시뮬틱", 0.02], V_REACH: ["킹공격거리", 40], V_LANEY: ["레인Y", -50],
            V_MYKX: ["하얀킹X", -200], V_ENKX: ["검은킹X", 200],
            V_PWHP: ["폰_체력", 12], V_PWATK: ["폰_공격력", 6], V_PWCD: ["폰_공속", 0.4],
            V_PWSP: ["폰_속도", 5.5], V_PWR: ["폰_사거리", 30], V_PWSUM: ["폰_소환쿨", 0.3],
            V_BSHP: ["비숍_체력", 8], V_BSATK: ["비숍_공격력", 7], V_BSCD: ["비숍_공속", 0.5],
            V_BSSP: ["비숍_속도", 3.5], V_BSR: ["비숍_사거리", 380], V_BSSUM: ["비숍_소환쿨", 0.45],
            V_KNHP: ["나이트_체력", 22], V_KNATK: ["나이트_공격력", 13], V_KNCD: ["나이트_공속", 0.45],
            V_KNSP: ["나이트_속도", 6.0], V_KNR: ["나이트_사거리", 34], V_KNSUM: ["나이트_소환쿨", 0.6],
            V_RKHP: ["룩_체력", 16], V_RKATK: ["룩_공격력", 8], V_RKCD: ["룩_공속", 0.9],
            V_RKSP: ["룩_속도", 2.6], V_RKR: ["룩_사거리", 400], V_RKSUM: ["룩_소환쿨", 0.9],
            V_QNHP: ["퀸_체력", 30], V_QNATK: ["퀸_공격력", 9], V_QNCD: ["퀸_공속", 0.7],
            V_QNSP: ["퀸_속도", 3.2], V_QNR: ["퀸_사거리", 390], V_QNSUM: ["퀸_소환쿨", 1.2],
            V_EPHP: ["적폰_체력", 8], V_EPATK: ["적폰_공격력", 3], V_EPCD: ["적폰_공속", 0.5],
            V_EPSP: ["적폰_속도", 5.0], V_EPR: ["적폰_사거리", 30],
            V_EBHP: ["적비숍_체력", 6], V_EBATK: ["적비숍_공격력", 4], V_EBCD: ["적비숍_공속", 0.6],
            V_EBSP: ["적비숍_속도", 3.3], V_EBR: ["적비숍_사거리", 360],
            V_ENKHP: ["적나이트_체력", 16], V_ENKATK: ["적나이트_공격력", 8], V_ENKCD: ["적나이트_공속", 0.5],
            V_ENKSP: ["적나이트_속도", 5.5], V_ENKR: ["적나이트_사거리", 34],
            V_ERHP: ["적룩_체력", 12], V_ERATK: ["적룩_공격력", 5], V_ERCD: ["적룩_공속", 0.9],
            V_ERSP: ["적룩_속도", 2.4], V_ERR: ["적룩_사거리", 380],
            V_EQHP: ["적퀸_체력", 32], V_EQATK: ["적퀸_공격력", 7], V_EQCD: ["적퀸_공속", 0.7],
            V_EQSP: ["적퀸_속도", 3.0], V_EQR: ["적퀸_사거리", 370],
            V_SPGAP: ["적소환간격", 2.2], V_SPDEC: ["적소환간격감소", 0.12], V_SPMIN: ["적소환최소간격", 0.7],
            V_UPGOLD: ["강화골드증가", 3], V_UPATK: ["강화공격배수", 1.15], V_UPHP: ["강화체력배수", 1.15],
            V_UPREPAIR: ["강화킹수리", 40],
            # 진행 40
            V_STATE: ["게임상태", 1], V_STAGE: ["스테이지", 1], V_GOLD: ["골드", 200], V_GOLDACC: ["골드누적", 0],
            V_MYHP: ["하얀킹체력", 100], V_ENHP: ["검은킹체력", 120], V_SCALECUR: ["적배율", 1],
            V_ALLYN: ["아군수", 0], V_ENEMYN: ["적군수", 0], V_ATKMUL: ["유닛공격력배수", 1], V_HPMUL: ["유닛체력배수", 1],
            V_UNKN: ["나이트해금", 0], V_UNRK: ["룩해금", 0], V_UNQN: ["퀸해금", 0],
            V_SUMTYPE: ["소환타입", 0], V_NEWALLY: ["새아군슬롯", 0],
            V_ENSPAWNT: ["적생성타입", 1], V_NEWENEMY: ["새적슬롯", 0],
            V_SUMT1: ["폰쿨타이머", 0], V_SUMT2: ["비숍쿨타이머", 0], V_SUMT3: ["나이트쿨타이머", 0],
            V_SUMT4: ["룩쿨타이머", 0], V_SUMT5: ["퀸쿨타이머", 0], V_ENSPTIMER: ["적소환타이머", 0],
            V_EFRONTX: ["적선두X", 200], V_EFRONTI: ["적선두슬롯", 0], V_AFRONTX: ["아군선두X", -200], V_AFRONTI: ["아군선두슬롯", 0],
            V_LOOPI: ["루프i", 0], V_LOOPJ: ["루프j", 0], V_CALCT: ["계산타입", 0], V_CALCD: ["계산뎀", 0],
            V_DMGVAL: ["데미지표시값", 0], V_DMGX: ["데미지표시x", 0], V_DMGY: ["데미지표시y", 0], V_DMGKIND: ["팝업종류", 0],
            V_DMGDIG: ["데미지숫자", 0], V_DMGOFF: ["데미지오프셋", 0], V_DMGLEN: ["데미지글자수", 0], V_DMGPOS: ["데미지자리", 0],
            V_REUSE: ["재사용슬롯", 0], V_LOOPK: ["루프k", 0], V_OVCOUNT: ["오버레이카운터", 0], V_SPAWNHP: ["스폰체력", 0],
            V_UNITS: ["유닛", "0/12"],
            V_FX: ["발사X", 0], V_FTX: ["발사목표X", 0], V_FKIND: ["발사종류", 0], V_SIEGE: ["킹공성거리", 300],
        },
        "lists": {
            L_ALLYX: ["아군X", []], L_ALLYHP: ["아군HP", []], L_ALLYT: ["아군타입", []],
            L_ALLYAL: ["아군살아있음", []], L_ALLYCD: ["아군쿨", []],
            L_ENX: ["적군X", []], L_ENHP: ["적군HP", []], L_ENT: ["적군타입", []],
            L_ENAL: ["적군살아있음", []], L_ENCD: ["적군쿨", []],
        },
        "broadcasts": {
            BR_START: "게임시작", BR_STAGEGO: "스테이지시작", BR_ALLY: "아군소환", BR_ENEMY: "적소환",
            BR_DMG: "데미지표시", BR_MYHIT: "하얀킹피격", BR_ENHIT: "검은킹피격", BR_CLEAR: "스테이지클리어",
            BR_UPDONE: "강화완료", BR_OVER: "게임오버", BR_FIRE: "발사",
        },
        "blocks": stage_blocks, "comments": stage_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "체스판", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180}],
        "sounds": [snd("horn", horn_s, horn_n)],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    myking = {
        "isStage": False, "name": "하얀킹",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": myk_blocks, "comments": myk_cmt,
        "currentCostume": 0,
        "costumes": [cos("킹", kw_md5, 40, 46)],
        "sounds": [snd("kinghit", kinghit_s, kinghit_n), snd("break", break_s, break_n)],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": -200, "y": -30, "size": 90, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    enking = {
        "isStage": False, "name": "검은킹",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": enk_blocks, "comments": enk_cmt,
        "currentCostume": 0,
        "costumes": [cos("킹", kb_md5, 40, 46)],
        "sounds": [snd("kinghit", kinghit_s, kinghit_n), snd("break", break_s, break_n)],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 200, "y": -30, "size": 90, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    manager = {
        "isStage": False, "name": "전투매니저",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": mgr_blocks, "comments": mgr_cmt,
        "currentCostume": 0,
        "costumes": [cos("두뇌", inv_md5, 4, 4)],
        "sounds": [snd("clash", clash_s, clash_n), snd("cannon", cannon_s, cannon_n),
                   snd("coin", coin_s, coin_n)],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    ally = {
        "isStage": False, "name": "아군유닛",
        "variables": {V_ALLY_ISC: ["복제됨", 0], V_ALLY_SLOT: ["슬롯", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": ally_blocks, "comments": ally_cmt,
        "currentCostume": 0,
        "costumes": [cos("폰", pw_md5), cos("비숍", bs_md5), cos("나이트", kn_md5),
                     cos("룩", rk_md5), cos("퀸", qn_md5), cos("폭죽", boom_md5)],
        "sounds": [snd("death", death_s, death_n)],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": -175, "y": -50, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    enemy = {
        "isStage": False, "name": "적군유닛",
        "variables": {V_EN_ISC: ["복제됨", 0], V_EN_SLOT: ["슬롯", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": enemy_cmt,
        "currentCostume": 0,
        "costumes": [cos("검은폰", bpw_md5), cos("검은비숍", bbs_md5), cos("검은나이트", bkn_md5),
                     cos("검은룩", brk_md5), cos("검은퀸", bqn_md5), cos("폭죽", boom_md5)],
        "sounds": [snd("death", death_s, death_n)],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 175, "y": -50, "size": 60, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    button = {
        "isStage": False, "name": "소환버튼",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": btn_blocks, "comments": btn_cmt,
        "currentCostume": 0,
        "costumes": [cos("시작잠금", bar_md5[0], 240, 30), cos("나이트해금", bar_md5[1], 240, 30),
                     cos("룩해금", bar_md5[2], 240, 30), cos("모두해금", bar_md5[3], 240, 30)],
        "sounds": [snd("summon", summon_s, summon_n), snd("error", error_s, error_n)],
        "volume": 100, "layerOrder": 8, "visible": True,
        "x": 0, "y": -150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    popup_costumes = []
    for d in range(10):
        popup_costumes.append(cos(f"w{d}", wd_md5[d], 16, 22))
    for d in range(10):
        popup_costumes.append(cos(f"g{d}", gd_md5[d], 16, 22))
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
        "sounds": [snd("upgrade", upgrade_s, upgrade_n)],
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

    overlay = {
        "isStage": False, "name": "쿨오버레이",
        "variables": {V_OV_ISC: ["복제됨", 0], V_OV_SLOT: ["슬롯", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": ov_blocks, "comments": ov_cmt,
        "currentCostume": 0,
        "costumes": [cos("재충전", ov_md5[0], 45, 22), cos("골드", ov_md5[1], 45, 22),
                     cos("가득참", ov_md5[2], 45, 22), cos("잠금", ov_md5[3], 45, 22)],
        "sounds": [],
        "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": -150, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    projectile = {
        "isStage": False, "name": "투사체",
        "variables": {V_PROJ_ISC: ["복제됨", 0], V_PROJ_KIND: ["종류", 0],
                      V_PROJ_SX: ["시작X", 0], V_PROJ_TX: ["목표X", 0], V_PROJ_T: ["진행", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": proj_blocks, "comments": proj_cmt,
        "currentCostume": 0,
        "costumes": [cos("아군화살", proj_md5[0], 12, 6), cos("아군포탄", proj_md5[1], 9, 9),
                     cos("적화살", proj_md5[2], 12, 6), cos("적포탄", proj_md5[3], 9, 9)],
        "sounds": [],
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_MYHP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "하얀킹체력"}, "spriteName": None,
         "value": 100, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_GOLD, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "골드"}, "spriteName": None,
         "value": 200, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 999, "isDiscrete": True},
        {"id": V_STAGE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "스테이지"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 65,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_ENHP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "검은킹체력"}, "spriteName": None,
         "value": 120, "width": 0, "height": 0, "x": 5, "y": 95,
         "visible": True, "sliderMin": 0, "sliderMax": 999, "isDiscrete": True},
        # 유닛 n/12 — 소환 버튼 바(하단) 근처에 배치
        {"id": V_UNITS, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "유닛"}, "spriteName": None,
         "value": "0/12", "width": 0, "height": 0, "x": 195, "y": 295,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, myking, enking, manager, ally, enemy, button, popup, card, gameover, overlay, projectile],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "chess-war-builder"}
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
    for nm, b in [("stage", stage_blocks), ("하얀킹", myk_blocks), ("검은킹", enk_blocks),
                  ("전투매니저", mgr_blocks), ("아군유닛", ally_blocks), ("적군유닛", enemy_blocks),
                  ("소환버튼", btn_blocks), ("숫자팝업", pop_blocks), ("강화카드", card_blocks),
                  ("게임오버", go_blocks), ("쿨오버레이", ov_blocks), ("투사체", proj_blocks)]:
        print(f"  {nm:10s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
