#!/usr/bin/env python3
"""트로이 디펜스 (troy-defense) — 트로이 공방전 타워디펜스. 놀란 오디세이 개봉 기념 테마.

클래식 로그라이트 타워디펜스.

아카이오이(그리스) 군세가 성벽으로 몰려온다. 트로이 수비대가 길 옆 방어탑을
세워 막아낸다. 포탑은 사거리 안 가장 가까운 적에게 자동 사격(궁수대=싸고 빠름 /
발리스타=광역 / 성화소=강함). 웨이브 클리어마다 랜덤 강화, Q/E 클릭 조준 범위 스킬 +
QWER 스킬: 아폴론(Q)·아레스(W)·아르테미스(E)·제우스 궁(R, 3회). 웨이브 클리어 시 3택1 강화. 성벽 체력 0이면 GAME OVER.

베이스: games/magic-survivor/build.py
  - 한글 튜닝 변수 일괄 초기화(매직넘버 0) / 조준요청 broadcast-and-wait 최솟값
    리덕션(다포탑 + 조준중 락 순차) / 타격 broadcast-and-wait 광역/단일 데미지 통일 /
    플로팅 숫자(say 미사용, 흰/금 두 세트) / 강화 택1 패널 / 게임오버 배너 /
    클론 스포너 + 복제됨 가드 / 폭발 연출 /
    효과음: assets/sfx/*.wav (swoshes/wobble/fireball/smite/shoot) + BGM(mp3) /
    add_comment 가이드 투어.

★ 모든 조절 값(43개)을 한글 전역 변수로만 노출, 코드 어디서도 매직넘버를 쓰지
  않는다(연출용 repeat 5 / 도달반경 비교 같은 소수 인라인만 허용). 초기화는 전부
  Stage 깃발 클릭 한 스크립트에 모은다. 길은 경로X/경로Y 리스트 6점.
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "트로이_디펜스.sb3")
GEN    = os.path.join(ASSETS, "gen")
SFXDIR = os.path.join(ASSETS, "sfx")  # 사용자 제공 SFX → mono 22050 wav

# ============================================================
#  효과음 — swoshes / wobble / Magic Smite / fireball / shoot
#  원본: assets/sfx/src/  ·  빌드용: assets/sfx/{name}.wav
# ============================================================
SND_RATE = 22050
WAV_RATES = {}  # md5 -> rate


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
PATH_BLOCK_R = 30        # 길 중심에서 이 거리(px) 안은 방어탑 설치 금지
PATH_BLOCK_R2 = PATH_BLOCK_R * PATH_BLOCK_R  # 거리² 비교용
# 그리스군 웨이포인트 (scratch 좌표) — 배경 polyline 과 동일 변환
PATH_WAYPOINTS = [(-220, -100), (-220, 50), (-50, 50), (-50, -90), (100, -90), (190, 70)]


def _path_block_samples(step=10):
    """웨이포인트 사이 보간 점 — 길 위 설치 금지 판정용."""
    pts = []
    wps = PATH_WAYPOINTS
    for i in range(len(wps) - 1):
        x0, y0 = wps[i]
        x1, y1 = wps[i + 1]
        dx, dy = x1 - x0, y1 - y0
        dist = (dx * dx + dy * dy) ** 0.5
        n = max(1, int(dist / step))
        for k in range(n + 1):
            t = k / n
            pts.append((x0 + dx * t, y0 + dy * t))
    return pts

# -------- 배경: 트로이 평야(올리브·모래) + 공성로(길색) + 성벽 자리 --------
# 웨이포인트(scratch)→SVG: svgX=scratchX+240, svgY=180-scratchY
#  경로: 하단 진입 → 지그재그 → 우측 트로이 성벽
random.seed(17)
field_tiles = []
for ty in range(0, 360, 28):
    for tx in range(0, 480, 28):
        shade = random.choice(["#C4B07A", "#B8A66C", "#D2C28A", "#A8945E", "#C9B878", "#9E8A52"])
        field_tiles.append(f'<rect x="{tx}" y="{ty}" width="28" height="28" fill="{shade}"/>')
decor = []
for (bx, by, br) in [(40,40,16),(90,300,18),(400,40,14),(430,280,16),(250,50,12),(60,200,11),(320,80,10)]:
    decor.append(f'<circle cx="{bx}" cy="{by}" r="{br}" fill="#5A6B3A" opacity="0.75"/>')
    decor.append(f'<circle cx="{bx+6}" cy="{by-5}" r="{br*0.55}" fill="#6F8248" opacity="0.65"/>')
for (rx, ry) in [(120,200),(300,150),(70,100)]:
    decor.append(f'<ellipse cx="{rx}" cy="{ry}" rx="10" ry="6" fill="#8A7A5C" opacity="0.55"/>')
FIELD = "\n    ".join(field_tiles)
DECOR = "\n    ".join(decor)
PATH_PTS = "20,280 20,130 190,130 190,270 340,270 430,110"
BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#B8A66C"/>
  <g>
    {FIELD}
  </g>
  <rect x="0" y="0" width="480" height="48" fill="#7EB6D9" opacity="0.35"/>
  <g>
    {DECOR}
  </g>
  <polyline points="{PATH_PTS}" fill="none"
            stroke="#8B7355" stroke-width="44" stroke-linejoin="round" stroke-linecap="round"/>
  <polyline points="{PATH_PTS}" fill="none"
            stroke="{PATH_COLOR}" stroke-width="34" stroke-linejoin="round" stroke-linecap="round"/>
  <rect x="400" y="70" width="70" height="70" rx="8" fill="#6B5344" opacity="0.40"/>
  <rect x="6" y="6" width="468" height="348" rx="10" fill="none" stroke="#5C4A2E" stroke-width="6" opacity="0.80"/>
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

# -------- 그리스군 코스튬: 고블린(약) / 오크(중) / 트롤(강) / 폭발 --------
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

# -------- 팔레트 (4슬롯: 창/북/토템 방어탑 PNG + 성벽수리; 해금 상태별 4코스튬) --------
#  가로 472px · 버튼 폭 112 · 간격 4.
#  버튼 중심 SVG x: 62 / 178 / 294 / 410 → rotationCenterX=236 기준 scratch x: -174/-58/58/174.
PAL_W  = 472
PAL_H  = 72
PAL_BW = 112
def _pal_btnx(i):
    return 6 + (i - 1) * (PAL_BW + 4)

def build_palette_pngs():
    """방어탑 타워 PNG를 버튼 안에 합성한 팔레트 4종(해금 조합)."""
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    spear = Image.open(f"{GEN}/tower_spear.png").convert("RGBA")
    drum  = Image.open(f"{GEN}/tower_drum.png").convert("RGBA")
    totem = Image.open(f"{GEN}/tower_totem.png").convert("RGBA")

    def fit(im, mw, mh):
        c = im.copy()
        c.thumbnail((mw, mh), Image.LANCZOS)
        return c

    def mk_one(cannon_ok, magic_ok):
        im = Image.new("RGBA", (PAL_W, PAL_H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, PAL_W - 1, PAL_H - 1], radius=12,
                            fill=(28, 36, 40, 240), outline=(255, 213, 79, 255), width=3)
        slots = [
            (1, spear, (46, 125, 50), "1", "50", True),
            (2, drum,  (21, 101, 192), "2", "100", cannon_ok),
            (3, totem, (106, 27, 154), "3", "150", magic_ok),
        ]
        for idx, tw, color, key, price, unlocked in slots:
            x = _pal_btnx(idx)
            fill = color + ((230,) if unlocked else (110,))
            d.rounded_rectangle([x, 6, x + PAL_BW - 1, PAL_H - 8], radius=10,
                                fill=fill, outline=(255, 255, 255, 220), width=2)
            icon = fit(tw, 32, 42)
            if not unlocked:
                icon = ImageEnhance.Brightness(icon).enhance(0.35)
            ix = x + (PAL_BW - icon.width) // 2 + 6
            iy = 10
            im.paste(icon, (ix, iy), icon)
            d.text((x + 8, 12), key, fill=(255, 255, 255, 255))
            d.text((x + PAL_BW // 2 - 10, PAL_H - 22), price,
                   fill=(255, 245, 157, 255) if unlocked else (160, 160, 160, 200))
            if not unlocked:
                d.text((x + PAL_BW // 2 - 8, 28), "🔒", fill=(255, 255, 255, 230))
        # 4) 성벽수리 — 전용 아이콘 에셋
        x4 = _pal_btnx(4)
        d.rounded_rectangle([x4, 6, x4 + PAL_BW - 1, PAL_H - 8], radius=10,
                            fill=(198, 40, 40, 230), outline=(255, 255, 255, 220), width=2)
        d.text((x4 + 8, 12), "4", fill=(255, 255, 255, 255))
        rep_path = f"{GEN}/repair_icon.png"
        if os.path.exists(rep_path):
            rep = fit(Image.open(rep_path).convert("RGBA"), 36, 36)
            rx = x4 + (PAL_BW - rep.width) // 2
            im.paste(rep, (rx, 14), rep)
        else:
            cx, cy, s = x4 + PAL_BW // 2, 32, 10
            d.rounded_rectangle([cx - s, cy - s // 3, cx + s, cy + s // 3], radius=2, fill=(105, 240, 174, 255))
            d.rounded_rectangle([cx - s // 3, cy - s, cx + s // 3, cy + s], radius=2, fill=(105, 240, 174, 255))
        d.text((x4 + PAL_BW // 2 - 10, PAL_H - 22), "60", fill=(255, 245, 157, 255))
        return im

    return [
        mk_one(False, False),
        mk_one(True, False),
        mk_one(False, True),
        mk_one(True, True),
    ]

# -------- 선택표시: 팔레트 버튼(112×58)과 같은 크기 노란 테두리 --------
#  팔레트 size=82 와 동일 스케일 → 시각적으로 선택 칸과 맞춤
HIGHLIGHT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="58" viewBox="0 0 112 58">
  <rect x="2" y="2" width="108" height="54" rx="10" fill="#FFEB3B" opacity="0.16"/>
  <rect x="2" y="2" width="108" height="54" rx="10" fill="none" stroke="#FFEB3B" stroke-width="4"/>
</svg>"""

# -------- 강화카드: 랜덤 강화 연출 --------
CARD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="150" viewBox="0 0 400 150">
  <rect x="4" y="4" width="392" height="142" rx="14" fill="#3E2723" opacity="0.95" stroke="#FFD54F" stroke-width="4"/>
  <text x="200" y="48" text-anchor="middle" fill="#FFD54F" font-family="Arial" font-size="26" font-weight="bold">신의 축복!</text>
  <text x="200" y="88" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="18">트로이 수비대 랜덤 강화</text>
  <text x="200" y="122" text-anchor="middle" fill="#FFE0B2" font-family="Arial" font-size="14">공격·사거리·연사·골드·스킬 중 하나</text>
</svg>"""

# -------- 게임오버 배너 --------
RESULT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14" fill="#000000" opacity="0.88" stroke="#C62828" stroke-width="5"/>
  <text x="180" y="58" text-anchor="middle" fill="#FFD54F" font-family="Arial" font-size="28" font-weight="bold">TROY HAS FALLEN</text>
  <text x="180" y="92" text-anchor="middle" fill="#E53935" font-family="Arial" font-size="36" font-weight="bold">트로이 함락</text>
  <text x="180" y="122" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="16">막은 웨이브는 WAVE 표시를 확인!</text>
  <text x="180" y="146" text-anchor="middle" fill="#FFCDD2" font-family="Arial" font-size="13">초록 깃발(▶) 으로 재도전</text>
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

LIGHTNING_SVGS = [_lightning_svg(700 + i) for i in range(6)]  # 더 화려한 다단 번개

# -------- 스킬 아이콘 HUD (버튼 아님) + 쿨타임 게이지 프레임 --------
#  ready_frac: 0=쿨 막 시작(게이지 비움) … 1=준비 완료(게이지 풀)
def _skill_icon_svg(kind, ready_frac, exhausted=False, charges=None):
    """kind: fire | spear | bolt. 원형 아이콘 + 하단 쿨 게이지."""
    specs = {
        "fire":  ("#BF360C", "#FF6F00", "#FFAB40", "Q"),
        "spear": ("#1B5E20", "#43A047", "#A5D6A7", "E"),
        "bolt":  ("#0D47A1", "#1565C0", "#FFF176", "Sp"),
    }
    bg, ring, accent, key = specs[kind]
    if exhausted:
        bg, ring, accent = "#3E2723", "#6D4C41", "#8D6E63"
    rf = max(0.0, min(1.0, ready_frac))
    dim = 0.35 + 0.65 * rf  # 쿨 중이면 아이콘 어둡게
    # 아이콘 글리프
    if kind == "fire":
        glyph = (f'<path d="M32 14 C28 24 22 28 22 38 C22 46 28 52 35 52 C42 52 48 46 48 38 '
                 f'C48 30 42 26 40 20 C36 28 34 28 32 14 Z" fill="{accent}" opacity="{dim:.2f}" '
                 f'stroke="#FFECB3" stroke-width="1.5"/>'
                 f'<ellipse cx="35" cy="42" rx="6" ry="5" fill="#FFF59D" opacity="{dim:.2f}"/>')
    elif kind == "spear":
        glyph = (f'<polygon points="35,12 30,40 35,36 40,40" fill="{accent}" opacity="{dim:.2f}" '
                 f'stroke="#E8F5E9" stroke-width="1.5" stroke-linejoin="round"/>'
                 f'<rect x="33" y="38" width="4" height="16" rx="1" fill="#8D6E63" opacity="{dim:.2f}"/>'
                 f'<polygon points="30,54 40,54 35,60" fill="#5D4037" opacity="{dim:.2f}"/>')
    else:
        glyph = (f'<polygon points="40,12 24,36 33,36 28,54 48,28 38,28" fill="{accent}" '
                 f'opacity="{dim:.2f}" stroke="#FFFDE7" stroke-width="1.5" stroke-linejoin="round"/>')
    # 하단 쿨 게이지 (ready 만큼 차오름)
    bar_w, bar_h, bar_x, bar_y = 48, 7, 11, 64
    fill_w = max(0, bar_w * rf)
    gcol = "#69F0AE" if rf >= 1.0 else "#FFD54F"
    if exhausted:
        gcol = "#5D4037"
        fill_w = 0
    badge = ""
    if charges is not None and not exhausted:
        badge = (f'<circle cx="54" cy="14" r="10" fill="#FFEB3B" stroke="#F57F17" stroke-width="2"/>'
                 f'<text x="54" y="18" text-anchor="middle" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#3E2723">{int(charges)}</text>')
    elif exhausted:
        badge = (f'<text x="35" y="80" text-anchor="middle" font-family="Arial" font-size="10" '
                 f'font-weight="bold" fill="#BCAAA4">소진</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="70" height="84" viewBox="0 0 70 84">
  <circle cx="35" cy="34" r="28" fill="{bg}" stroke="{ring}" stroke-width="3" opacity="0.95"/>
  {glyph}
  <text x="12" y="18" font-family="Arial" font-size="11" font-weight="bold" fill="#FFFFFF" opacity="0.9">{key}</text>
  {badge}
  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="3" fill="#263238" stroke="#90A4AE" stroke-width="1"/>
  <rect x="{bar_x}" y="{bar_y}" width="{fill_w:.1f}" height="{bar_h}" rx="3" fill="{gcol}"/>
</svg>"""

SKILL_CD_FRAMES = 8  # 0..8 ready_frac

def _skill_frame_svgs(kind):
    """쿨 프레임 0(비움)~8(풀) + 번개 소진."""
    frames = [_skill_icon_svg(kind, i / SKILL_CD_FRAMES) for i in range(SKILL_CD_FRAMES + 1)]
    if kind == "bolt":
        frames.append(_skill_icon_svg(kind, 0, exhausted=True))
    return frames

SKILL_FIRE_SVGS  = _skill_frame_svgs("fire")
SKILL_SPEAR_SVGS = _skill_frame_svgs("spear")
SKILL_BOLT_SVGS  = _skill_frame_svgs("bolt")  # 0..8 + 소진

# -------- 성벽체력 게이지 / 웨이브 HUD --------
HP_BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="160" height="28" viewBox="0 0 160 28">
  <rect x="1" y="1" width="158" height="26" rx="8" fill="#1B0000" stroke="#FF8A80" stroke-width="2" opacity="0.92"/>
  <text x="10" y="18" font-family="Arial" font-size="11" font-weight="bold" fill="#FFCDD2">❤</text>
  <rect x="28" y="8" width="122" height="12" rx="4" fill="#3E2723"/>
</svg>"""
# 빨간 채움 바 — rotationCenter 왼쪽 → size% 로 길이 조절
HP_FILL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="122" height="12" viewBox="0 0 122 12">
  <rect x="0" y="0" width="122" height="12" rx="4" fill="#E53935"/>
  <rect x="0" y="0" width="122" height="5" rx="3" fill="#FF8A80" opacity="0.45"/>
</svg>"""

WAVE_PANEL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="110" height="40" viewBox="0 0 110 40">
  <rect x="1" y="1" width="108" height="38" rx="10" fill="#0D2137" stroke="#4FC3F7" stroke-width="2" opacity="0.94"/>
  <text x="12" y="25" font-family="Arial" font-size="13" font-weight="bold" fill="#81D4FA">WAVE</text>
</svg>"""

# 스킬 조준 링 (클릭 위치 표시)
SKILL_AIM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <circle cx="60" cy="60" r="52" fill="#FFEB3B" opacity="0.12" stroke="#FFD54F" stroke-width="3"/>
  <circle cx="60" cy="60" r="36" fill="none" stroke="#FFF59D" stroke-width="2" stroke-dasharray="6 4"/>
  <circle cx="60" cy="60" r="4" fill="#FFEB3B"/>
  <line x1="60" y1="8" x2="60" y2="28" stroke="#FFD54F" stroke-width="2"/>
  <line x1="60" y1="92" x2="60" y2="112" stroke="#FFD54F" stroke-width="2"/>
  <line x1="8" y1="60" x2="28" y2="60" stroke="#FFD54F" stroke-width="2"/>
  <line x1="92" y1="60" x2="112" y2="60" stroke="#FFD54F" stroke-width="2"/>
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
# ----- 5.1 튜닝 40 (개조 핸들) -----
V_GOLD0     = "varGold01"        # 기본골드 150
V_COSTA     = "varCostArrow02"   # 궁수대가격 50
V_COSTC     = "varCostCannon03"  # 발리스타가격 100
V_COSTM     = "varCostMagic04"   # 성화소가격 150
V_WAVEGOLD  = "varWaveGold05"    # 웨이브클리어골드 30
V_UPGOLD    = "varUpGold06"      # 강화골드량 40
V_UP        = "varUp07"          # 강화량 1
V_CASTLEMAX = "varCastleMax08"   # 성벽최대체력 20
V_UNLKC     = "varUnlockCannon09"# 발리스타해금웨이브 2
V_UNLKM     = "varUnlockMagic10" # 성화소해금웨이브 4
V_BASECNT   = "varBaseCount11"   # 기본그리스군수 6
V_CNTINC    = "varCountInc12"    # 웨이브당그리스군증가 2
V_SPGAP     = "varSpawnGap13"    # 그리스군간격 0.8
V_HPINC     = "varHPinc14"       # (레거시) 웨이브체력증가 — 배율 체계로 대체, 0 유지
V_SPINC     = "varSPinc15"       # 웨이브속도증가 0.05
V_REACH     = "varReach16"       # 도달반경 12
V_BOLTSPD   = "varBoltSpd17"     # 탄속도 12
V_GOBHP     = "varGobHP18"       # 경보병_체력 3
V_GOBSP     = "varGobSP19"       # 경보병_속도 2.2
V_GOBGOLD   = "varGobGold20"     # 경보병_골드 5
V_ORCHP     = "varOrcHP21"       # 호플리테스_체력 8
V_ORCSP     = "varOrcSP22"       # 호플리테스_속도 1.5
V_ORCGOLD   = "varOrcGold23"     # 호플리테스_골드 10
V_TROLLHP   = "varTrollHP24"     # 영웅_체력 20
V_TROLLSP   = "varTrollSP25"     # 영웅_속도 0.9
V_TROLLGOLD = "varTrollGold26"   # 영웅_골드 25
# 난이도 스케일 + 보스 (웨이브 5마다)
V_HPSCALE   = "varHpScale104"    # 적체력배율 1.0 (진행 중 증가)
V_HPSCALE_INC = "varHpScaleInc105"  # 웨이브배율증가 0.2 (일반 웨이브 클리어 시 +)
V_HPSCALE_BOSS = "varHpScaleBoss106"  # 보스후배율 1.5 (보스 웨이브 클리어 시 ×)
V_BOSSEVERY = "varBossEvery107"  # 보스주기 5
V_BOSSHP0   = "varBossHp0108"    # 보스기본체력 90
V_BOSSHPINC = "varBossHpInc109"  # 보스단계체력 55 (보스번호마다 추가)
V_BOSSSP    = "varBossSp110"     # 보스속도 0.65
V_BOSSGOLD0 = "varBossGold0111"  # 보스기본골드 60
V_BOSSIDX   = "varBossIdx112"    # 보스번호 1=아킬레우스… (스폰 시 설정)
V_ARR       = "varArR27"         # 궁수대_사거리 135
V_ARD       = "varArD28"         # 궁수대_공격력 4
V_ARG       = "varArG29"         # 궁수대_간격 0.35
V_ARS       = "varArS30"         # 궁수대_폭발반경 24
V_CAR       = "varCaR31"         # 발리스타_사거리 115
V_CAD       = "varCaD32"         # 발리스타_공격력 7
V_CAG       = "varCaG33"         # 발리스타_간격 1.0
V_CAS       = "varCaS34"         # 발리스타_폭발반경 72
V_MAR       = "varMaR35"         # 성화소_사거리 165
V_MAD       = "varMaD36"         # 성화소_공격력 10
V_MAG       = "varMaG37"         # 성화소_간격 0.65
V_MAS       = "varMaS38"         # 성화소_폭발반경 32
V_REPAIRCOST= "varRepairCost39"  # 수리비용 60   (튜닝 39)
V_REPAIRAMT = "varRepairAmt40"   # 수리량 5      (튜닝 40)
V_BGMVOL    = "varBgmVol40b"     # 브금볼륨 55   (효과음이 안 묻히게)
V_SPELLDMG  = "varSpellDmg41"    # 주문공격력 9999 (튜닝 41 — 전체 번개: 원턴킬)
V_SPELLCD   = "varSpellCD42"     # 주문쿨 20     (튜닝 42 — 재사용 대기 초, 길게)
V_SPELLMAX  = "varSpellMax43"    # 주문최대횟수 3 (튜닝 43 — 게임당 시전 가능 횟수)
# 범위 스킬 2종 (쿨 끝나면 재사용) + 강화 롤
V_SK1CD     = "varSk1Cd85"       # 아폴론 쿨 남은 초
V_SK1MAX    = "varSk1Max86"      # 아폴론 쿨 최대
V_SK1DMG    = "varSk1Dmg87"      # 아폴론 데미지
V_SK1R      = "varSk1R88"        # 아폴론 반경
V_SK2CD     = "varSk2Cd89"       # 아레스 쿨 남은 초
V_SK2MAX    = "varSk2Max90"      # 아레스 쿨 최대
V_SK2DMG    = "varSk2Dmg91"      # 아레스 데미지
V_SK2R      = "varSk2R92"        # 아레스 반경
V_SKPOWER   = "varSkPower93"     # 스킬 위력 보너스(강화로 증가)
V_ROLL      = "varRoll94"        # 랜덤 강화 결과 코드
V_SKSEL     = "varSkSel95"       # 선택스킬 0=없음 1=아폴론 2=아레스 3=아르테미스
V_OPT1      = "varOpt196"        # 강화선택1 타입코드 1~6
V_OPT2      = "varOpt297"        # 강화선택2
V_OPT3      = "varOpt398"        # 강화선택3
V_UPICK     = "varUpPick113"     # 강화칸선택 0=대기 1/2/3=선택됨 (키·클릭)
V_SK3CD     = "varSk3Cd99"       # 아르테미스 쿨
V_SK3MAX    = "varSk3Max100"     # 아르테미스 쿨최대
V_SK3DMG    = "varSk3Dmg101"     # 아르테미스 데미지
V_SK3R      = "varSk3R102"       # 아르테미스 반경
V_FXKIND    = "varFxKind103"     # 스킬이펙트 종류 1~3

# ----- 5.2 진행/내부 상태 40 -----
V_STATE   = "varState39"      # 게임상태 1
V_WAVE    = "varWave40"       # 웨이브 1
V_GOLDCUR = "varGoldCur41"    # 골드 150
V_CASTLE  = "varCastle42"     # 성벽체력 20
V_ALIVE   = "varAlive43"      # 적수 0
V_SPAWNED = "varSpawned44"    # 스폰완료 0
V_SPAWNN  = "varSpawnN45"     # 스폰카운트 0
V_SEL     = "varSel46"        # 선택포탑 0
V_UNCA    = "varUnCa47"       # 발리스타해금 0
V_UNMA    = "varUnMa48"       # 성화소해금 0
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
V_I         = "varScanI81"      # 검사i — 길판정 루프 인덱스
V_TMP       = "varPathFlag82"   # 임시 — 1이면 길 위(설치 불가)
V_PDX       = "varPathDx83"     # 길거리X
V_PDY       = "varPathDy84"     # 길거리Y
# V_HPSCALE~V_BOSSIDX 는 위 튜닝/보스 섹션 참고

# ----- 5.3 리스트 -----
L_PATHX = "listPathX"   # 경로X
L_PATHY = "listPathY"   # 경로Y
L_SAMPX = "listSampX"   # 길판정X (설치 금지 샘플)
L_SAMPY = "listSampY"   # 길판정Y

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
BR_SPAWN  = "brSpawn03"   # 그리스군생성
BR_AIM    = "brAim04"     # 조준요청
BR_FIRE   = "brFire05"    # 포탑발사
BR_HIT    = "brHit06"     # 타격
BR_DMG    = "brDmg07"     # 데미지표시
BR_PLACE  = "brPlace08"   # 포탑설치
BR_UP     = "brUp09"      # 강화등장
BR_UPDONE = "brUpDone10"  # 강화완료
BR_CASTLE = "brCastle11"  # 성벽피격
BR_SPELL  = "brSpell12"   # 주문시전 (전체 번개)
BR_SK1    = "brSkill1"    # 아폴론 범위 스킬
BR_SK2    = "brSkill2"    # 아레스 범위 스킬
BR_SK3    = "brSkill3"    # 아르테미스 범위 스킬
BR_SKFX   = "brSkillFx"   # 스킬 이펙트 연출

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

    # ── 튜닝 43 (개조 핸들) ──
    add_set("기본골드", V_GOLD0, 250)
    add_set("궁수대가격", V_COSTA, 50)
    add_set("발리스타가격", V_COSTC, 100)
    add_set("성화소가격", V_COSTM, 150)
    add_set("웨이브클리어골드", V_WAVEGOLD, 40)
    add_set("강화골드량", V_UPGOLD, 180)   # 비약적 골드 강화
    add_set("강화량", V_UP, 6)             # 비약적 스탯 강화
    add_set("성벽최대체력", V_CASTLEMAX, 20)
    add_set("발리스타해금웨이브", V_UNLKC, 2)
    add_set("성화소해금웨이브", V_UNLKM, 4)
    add_set("기본그리스군수", V_BASECNT, 6)
    add_set("웨이브당그리스군증가", V_CNTINC, 2)
    add_set("그리스군간격", V_SPGAP, 0.8)
    add_set("웨이브체력증가", V_HPINC, 0)   # 배율 체계 사용 (레거시 가산 0)
    add_set("웨이브속도증가", V_SPINC, 0.05)
    add_set("도달반경", V_REACH, 12)
    add_set("탄속도", V_BOLTSPD, 12)
    add_set("경보병_체력", V_GOBHP, 3)
    add_set("경보병_속도", V_GOBSP, 2.2)
    add_set("경보병_골드", V_GOBGOLD, 5)
    add_set("호플리테스_체력", V_ORCHP, 8)
    add_set("호플리테스_속도", V_ORCSP, 1.5)
    add_set("호플리테스_골드", V_ORCGOLD, 10)
    add_set("영웅_체력", V_TROLLHP, 20)
    add_set("영웅_속도", V_TROLLSP, 0.9)
    add_set("영웅_골드", V_TROLLGOLD, 25)
    # 난이도: 일반 웨이브 클리어 시 배율+0.2 / 보스 클리어 시 ×1.5
    # (×2 는 후반이 너무 급격 — 보스후배율 변수로 조절)
    add_set("적체력배율", V_HPSCALE, 1)
    add_set("웨이브배율증가", V_HPSCALE_INC, 0.2)
    add_set("보스후배율", V_HPSCALE_BOSS, 1.5)
    add_set("보스주기", V_BOSSEVERY, 5)
    add_set("보스기본체력", V_BOSSHP0, 90)
    add_set("보스단계체력", V_BOSSHPINC, 55)
    add_set("보스속도", V_BOSSSP, 0.65)
    add_set("보스기본골드", V_BOSSGOLD0, 60)
    add_set("보스번호", V_BOSSIDX, 0)
    # 타워 기본 화력 상향 (적 대비 약했던 공격 보정 — DPS 약 2.5~3배)
    add_set("궁수대_사거리", V_ARR, 135)
    add_set("궁수대_공격력", V_ARD, 4)
    add_set("궁수대_간격", V_ARG, 0.35)
    add_set("궁수대_폭발반경", V_ARS, 24)
    add_set("발리스타_사거리", V_CAR, 115)
    add_set("발리스타_공격력", V_CAD, 7)
    add_set("발리스타_간격", V_CAG, 1.0)
    add_set("발리스타_폭발반경", V_CAS, 72)
    add_set("성화소_사거리", V_MAR, 165)
    add_set("성화소_공격력", V_MAD, 10)
    add_set("성화소_간격", V_MAG, 0.65)
    add_set("성화소_폭발반경", V_MAS, 32)
    add_set("수리비용", V_REPAIRCOST, 60)
    add_set("수리량", V_REPAIRAMT, 5)
    add_set("브금볼륨", V_BGMVOL, 55)     # BGM 음량(%). 효과음이 안 묻히게
    add_set("주문공격력", V_SPELLDMG, 9999)
    add_set("주문쿨", V_SPELLCD, 18)
    add_set("주문최대횟수", V_SPELLMAX, 3)
    add_set("아폴론쿨", V_SK1CD, 0)
    add_set("아폴론쿨최대", V_SK1MAX, 8)
    add_set("아폴론데미지", V_SK1DMG, 40)
    add_set("아폴론반경", V_SK1R, 110)
    add_set("아레스쿨", V_SK2CD, 0)
    add_set("아레스쿨최대", V_SK2MAX, 9)
    add_set("아레스데미지", V_SK2DMG, 55)
    add_set("아레스반경", V_SK2R, 90)
    add_set("아르테미스쿨", V_SK3CD, 0)
    add_set("아르테미스쿨최대", V_SK3MAX, 10)
    add_set("아르테미스데미지", V_SK3DMG, 48)
    add_set("아르테미스반경", V_SK3R, 100)
    add_set("스킬위력", V_SKPOWER, 0)
    add_set("강화롤", V_ROLL, 0)
    add_set("선택스킬", V_SKSEL, 0)
    add_set("강화선택1", V_OPT1, 1)
    add_set("강화선택2", V_OPT2, 2)
    add_set("강화선택3", V_OPT3, 3)
    add_set("강화칸선택", V_UPICK, 0)
    add_set("이펙트종류", V_FXKIND, 0)

    # ── 진행 상태 41 (골드=기본골드, 성벽체력=성벽최대체력 참조) ──
    add_set("게임상태", V_STATE, 1)
    add_set("웨이브", V_WAVE, 1)
    gold0_r = vrep("기본골드", V_GOLD0)
    sid = b_setvar(bs, "골드", V_GOLDCUR, gold0_r); seq.append((sid, bs[sid]))
    cmax_r = vrep("성벽최대체력", V_CASTLEMAX)
    sid = b_setvar(bs, "성벽체력", V_CASTLE, cmax_r); seq.append((sid, bs[sid]))
    add_set("적수", V_ALIVE, 0)
    add_set("스폰완료", V_SPAWNED, 0)
    add_set("스폰카운트", V_SPAWNN, 0)
    add_set("선택포탑", V_SEL, 0)
    add_set("발리스타해금", V_UNCA, 0)
    add_set("성화소해금", V_UNMA, 0)
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
    path = list(PATH_WAYPOINTS)
    first_path_block = None
    for (px, py) in path:
        ax = b_add_to_list(bs, "경로X", L_PATHX, px); seq.append((ax, bs[ax]))
        if first_path_block is None: first_path_block = ax
        ay = b_add_to_list(bs, "경로Y", L_PATHY, py); seq.append((ay, bs[ay]))
    # ── 길 위 설치 금지 샘플 (조밀 보간) ──
    dsx = b_delete_all(bs, "길판정X", L_SAMPX); seq.append((dsx, bs[dsx]))
    dsy = b_delete_all(bs, "길판정Y", L_SAMPY); seq.append((dsy, bs[dsy]))
    for (sx, sy) in _path_block_samples(10):
        ax = b_add_to_list(bs, "길판정X", L_SAMPX, round(sx, 1)); seq.append((ax, bs[ax]))
        ay = b_add_to_list(bs, "길판정Y", L_SAMPY, round(sy, 1)); seq.append((ay, bs[ay]))

    w1 = b_wait(bs, 0.3); seq.append((w1, bs[w1]))
    bc_start = b_broadcast(bs, "게임시작", BR_START); seq.append((bc_start, bs[bc_start]))
    chain(seq)

    # ===== (B) 웨이브 매니저 forever (스폰) =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=360, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # broadcast 웨이브시작 ; 스폰카운트=0 ; repeat(count){ 생성타입 결정 ; +1 ; 적수+1 ; 그리스군생성 ; wait } ; 스폰완료=1
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
    bc_spawn = b_broadcast(bs, "그리스군생성", BR_SPAWN)
    w_gap = b_wait_var(bs, V_SPGAP, "그리스군간격")
    chain([(if_type, bs[if_type]), (inc_spn, bs[inc_spn]), (inc_alive, bs[inc_alive]),
           (bc_spawn, bs[bc_spawn]), (w_gap, bs[w_gap])])
    base_r = vrep("기본그리스군수", V_BASECNT); wave_rc = vrep("웨이브", V_WAVE)
    wm1 = op("operator_subtract", wave_rc, 1); cinc_r = vrep("웨이브당그리스군증가", V_CNTINC)
    extra = op("operator_multiply", wm1, cinc_r)
    count_r = op("operator_add", base_r, extra)
    rep_spawn = b_repeat(bs, count_r, if_type)
    # 보스 웨이브: 웨이브 % 보스주기 == 0 → 보스 1기 (타입 4) 추가 스폰
    # 보스번호 = 웨이브 / 보스주기 (5→1 아킬레우스, 10→2 메넬라오스, …)
    bmod = op("operator_mod", vrep("웨이브", V_WAVE), vrep("보스주기", V_BOSSEVERY))
    c_boss_wave = cmp_op("operator_equals", bmod, 0)
    bidx = op("operator_divide", vrep("웨이브", V_WAVE), vrep("보스주기", V_BOSSEVERY))
    set_bidx = b_setvar(bs, "보스번호", V_BOSSIDX, bidx)
    set_tboss = b_setvar(bs, "생성타입", V_SPAWNT, 4)
    inc_alive_b = b_changevar(bs, "적수", V_ALIVE, 1)
    bc_spawn_b = b_broadcast(bs, "그리스군생성", BR_SPAWN)
    w_boss = b_wait(bs, 0.4)
    chain([(set_bidx, bs[set_bidx]), (set_tboss, bs[set_tboss]),
           (inc_alive_b, bs[inc_alive_b]), (bc_spawn_b, bs[bc_spawn_b]), (w_boss, bs[w_boss])])
    if_boss = b_if(bs, c_boss_wave, set_bidx)
    set_done = b_setvar(bs, "스폰완료", V_SPAWNED, 1)
    chain([(bc_wave, bs[bc_wave]), (set_spn0, bs[set_spn0]),
           (rep_spawn, bs[rep_spawn]), (if_boss, bs[if_boss]), (set_done, bs[set_done])])
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

    # ===== (C2) BGM: 별도 병렬 깃발 스크립트 (게임 로직 hat 방해 없음) =====
    #   when green flag → set volume (브금볼륨)% → forever { play bgm until done }
    #   until-done 반복이라 곡 끝나면 처음부터 다시(무한 루프).
    hbgm = gen(); bs[hbgm] = mk("event_whenflagclicked", top=True, x=700, y=20)
    bgmvol_r = vrep("브금볼륨", V_BGMVOL)
    setvol = gen(); bs[setvol] = mk("sound_setvolumeto", inputs={"VOLUME": slot(bgmvol_r)})
    bs[bgmvol_r]["parent"] = setvol
    bgm_menu = gen(); bs[bgm_menu] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["bgm", None]}, shadow=True)
    play_bgm = gen(); bs[play_bgm] = mk("sound_playuntildone", inputs={"SOUND_MENU": [1, bgm_menu]})
    bs[bgm_menu]["parent"] = play_bgm
    fe_bgm = b_forever(bs, play_bgm)
    chain([(hbgm, bs[hbgm]), (setvol, bs[setvol]), (fe_bgm, bs[fe_bgm])])

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
    # 난이도 성장: 보스 웨이브면 배율×보스후배율, 아니면 배율+웨이브배율증가
    bmod_c = op("operator_mod", vrep("웨이브", V_WAVE), vrep("보스주기", V_BOSSEVERY))
    c_was_boss = cmp_op("operator_equals", bmod_c, 0)
    sc_mul = op("operator_multiply", vrep("적체력배율", V_HPSCALE), vrep("보스후배율", V_HPSCALE_BOSS))
    set_sc_boss = b_setvar(bs, "적체력배율", V_HPSCALE, sc_mul)
    sc_add = op("operator_add", vrep("적체력배율", V_HPSCALE), vrep("웨이브배율증가", V_HPSCALE_INC))
    set_sc_norm = b_setvar(bs, "적체력배율", V_HPSCALE, sc_add)
    if_sc = b_ifelse(bs, c_was_boss, set_sc_boss, set_sc_norm)
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    bc_up = b_broadcast(bs, "강화등장", BR_UP)
    chain([(add_gold, bs[add_gold]), (if_sc, bs[if_sc]),
           (set_st2, bs[set_st2]), (bc_up, bs[bc_up])])
    if_clear = b_if(bs, c_clear, add_gold)
    # 게임오버: 성벽체력<1 and 게임상태=1 → 게임상태=0
    cs = vrep("성벽체력", V_CASTLE); cdead = cmp_op("operator_lt", cs, 1)
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
        "🛠️ 개조 핸들: 여기 숫자만 바꾸면 게임이 달라져요!\n"
        "골드·가격·그리스군·포탑 능력치가 전부 여기 한글 변수로 모여 있어요. "
        "예: 궁수대가격 50→10 으로 바꾸면 궁수대를 길에 도배할 수 있어요. "
        "바꾸기 전에 어떻게 될지 예상하고 ▶ 를 눌러 확인!",
        x=-380, y=-280, w=340, h=180)
    add_comment(bs, comments, delx,
        "🗺️ 길은 이 좌표들이에요.\n"
        "경로X·경로Y 에 6개의 점을 넣어 S자 길을 만들어요. 숫자를 바꾸면 그리스군이 가는 "
        "길이 바뀌어요(미션 4층: 더 구불구불한 길 만들기).",
        x=-380, y=420, w=320, h=150)
    add_comment(bs, comments, hb,
        "🌊 웨이브 수 = 기본 + (웨이브-1)×증가. 체력은 적체력배율로 커짐.\n"
        "일반 클리어: 배율+웨이브배율증가(0.2). 보스 클리어(5·10·15…): 배율×보스후배율(1.5).\n"
        "보스(약→강): 아가멤논→메넬라오스→아킬레우스 (5·10·15…, 전용 에셋).",
        x=720, y=-20, w=340, h=180)

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
        fields={"BROADCAST_OPTION": ["성벽피격", BR_CASTLE]})
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
#  그리스군 (MONSTER: 스포너 + 클론 본체 + 타격 + 조준 보고)
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

    # (B) 그리스군생성 → 클론 1마리 (원본만)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["그리스군생성", BR_SPAWN]})
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
        base_hp = vrep(hp_nm, hp_id)
        scaled = op("operator_multiply", base_hp, vrep("적체력배율", V_HPSCALE))
        wv = vrep("웨이브", V_WAVE)
        wm1 = op("operator_subtract", wv, 1); hpinc = vrep("웨이브체력증가", V_HPINC)
        flat = op("operator_multiply", wm1, hpinc)
        hp_expr = op("operator_add", scaled, flat)
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
    if_t1 = type_branch(1, V_GOBHP, "경보병_체력", V_GOBSP, "경보병_속도", V_GOBGOLD, "경보병_골드", "경보병", 50)
    if_t2 = type_branch(2, V_ORCHP, "호플리테스_체력", V_ORCSP, "호플리테스_속도", V_ORCGOLD, "호플리테스_골드", "호플리테스", 70)
    if_t3 = type_branch(3, V_TROLLHP, "영웅_체력", V_TROLLSP, "영웅_속도", V_TROLLGOLD, "영웅_골드", "영웅", 90)

    # 타입 4 = 보스 (약→강: 아가멤논 → 메넬라오스 → 아킬레우스) — 단일 코스튬, 모션 없음
    cond_t4 = cmp_op("operator_equals", vrep("내타입", V_MON_TYPE), 4)
    bidx_m1 = op("operator_subtract", vrep("보스번호", V_BOSSIDX), 1)
    bstep = op("operator_multiply", bidx_m1, vrep("보스단계체력", V_BOSSHPINC))
    bbase = op("operator_add", vrep("보스기본체력", V_BOSSHP0), bstep)
    bhp = op("operator_multiply", bbase, vrep("적체력배율", V_HPSCALE))
    set_bhp = b_setvar(bs, "내체력", V_MON_HP, bhp)
    set_bsp = b_setvar(bs, "내속도", V_MON_SPD, vrep("보스속도", V_BOSSSP))
    bgold = op("operator_multiply", vrep("보스기본골드", V_BOSSGOLD0), vrep("보스번호", V_BOSSIDX))
    set_bgd = b_setvar(bs, "내골드", V_MON_GOLD, bgold)
    sw_b1 = b_costume(bs, "아가멤논")
    sw_b2 = b_costume(bs, "메넬라오스")
    sw_b3 = b_costume(bs, "아킬레우스")
    if_sw2 = b_ifelse(bs, cmp_op("operator_equals", vrep("보스번호", V_BOSSIDX), 2), sw_b2, sw_b3)
    if_sw1 = b_ifelse(bs, cmp_op("operator_equals", vrep("보스번호", V_BOSSIDX), 1), sw_b1, if_sw2)
    bsz = op("operator_add", 105, op("operator_multiply", vrep("보스번호", V_BOSSIDX), 6))
    sz_b = gen(); bs[sz_b] = mk("looks_setsizeto", inputs={"SIZE": slot(bsz)})
    bs[bsz]["parent"] = sz_b
    def say_if_boss(n, name):
        c = cmp_op("operator_equals", vrep("보스번호", V_BOSSIDX), n)
        say = gen(); bs[say] = mk("looks_sayforsecs",
            inputs={"MESSAGE": text_lit(name), "SECS": num(1.5)})
        return b_if(bs, c, say)
    say1 = say_if_boss(1, "아가멤논")
    say2 = say_if_boss(2, "메넬라오스")
    c_ge3 = cmp_op("operator_gt", vrep("보스번호", V_BOSSIDX), 2)
    say3 = gen(); bs[say3] = mk("looks_sayforsecs",
        inputs={"MESSAGE": text_lit("아킬레우스"), "SECS": num(1.5)})
    if_say3 = b_if(bs, c_ge3, say3)
    chain([(set_bhp, bs[set_bhp]), (set_bsp, bs[set_bsp]), (set_bgd, bs[set_bgd]),
           (if_sw1, bs[if_sw1]), (sz_b, bs[sz_b]),
           (say1, bs[say1]), (say2, bs[say2]), (if_say3, bs[if_say3])])
    if_t4 = b_if(bs, cond_t4, set_bhp)
    chain([(if_t1, bs[if_t1]), (if_t2, bs[if_t2]), (if_t3, bs[if_t3]), (if_t4, bs[if_t4])])

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

    # 2) 게임상태=1 → 경로 행진 + 도달/처치 (모션 애니 없음)
    march = []
    pt = b_point_toward(bs, op, cmp_op, mkX, mkY)
    mv = b_movesteps(bs, vrep("내속도", V_MON_SPD))
    march.append(pt); march.append(mv)
    dist_wp = b_dist_to(bs, op, mkX, mkY)
    reach_r = vrep("도달반경", V_REACH)
    cond_arr = cmp_op("operator_lt", dist_wp, reach_r)
    inc_wp = b_changevar(bs, "현재점", V_MON_WP, 1)
    wp_r = vrep("현재점", V_MON_WP); len_r = b_length_of(bs, "경로X", L_PATHX)
    cond_end = cmp_op("operator_gt", wp_r, len_r)
    dec_castle1 = b_changevar(bs, "성벽체력", V_CASTLE, -1)
    dec_castle3 = b_changevar(bs, "성벽체력", V_CASTLE, -3)
    c_is_boss = cmp_op("operator_equals", vrep("내타입", V_MON_TYPE), 4)
    if_cdmg = b_ifelse(bs, c_is_boss, dec_castle3, dec_castle1)
    bc_castle = b_broadcast(bs, "성벽피격", BR_CASTLE)
    dec_al_end = b_changevar(bs, "적수", V_ALIVE, -1)
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(if_cdmg, bs[if_cdmg]), (bc_castle, bs[bc_castle]),
           (dec_al_end, bs[dec_al_end]), (del_end, bs[del_end])])
    if_end = b_if(bs, cond_end, if_cdmg)
    chain([(inc_wp, bs[inc_wp]), (if_end, bs[if_end])])
    if_arr = b_if(bs, cond_arr, inc_wp)
    march.append(if_arr)
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
    chain([(if_t4, bs[if_t4]), (set_wp1, bs[set_wp1]), (g, bs[g]),
           (show, bs[show]), (fe_body, bs[fe_body])])

    # (D) 타격 받으면 반경 안일 때 데미지 + 데미지 숫자 팝업 (스킬/포탑 공통)
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
    # 데미지 숫자 표시 (스킬 데미지량 = 폭발데미지)
    set_dval = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("폭발데미지", V_BOOMD))
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, b_xpos(bs))
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, b_ypos(bs))
    set_kind = b_setvar(bs, "팝업종류", V_DMGKIND, 0)  # 0=흰 데미지
    bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
    sh_hit, sp_hit = b_sound(bs, 0, "hit")
    chain([(dec_hp, bs[dec_hp]), (set_dval, bs[set_dval]), (set_dx, bs[set_dx]),
           (set_dy, bs[set_dy]), (set_kind, bs[set_kind]), (bc_dmg, bs[bc_dmg]),
           (sh_hit, bs[sh_hit]), (sp_hit, bs[sp_hit])])
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

    # (F) 주문시전(전체 번개) 받으면 — 화면의 모든 그리스군이 동시에 주문공격력만큼 피해.
    #     wait/yield 없는 원자 실행이라 모든 클론이 경쟁 없이 한 번에 맞아요. 처치는 (C) 루프가 처리.
    hsp = gen(); bs[hsp] = mk("event_whenbroadcastreceived", top=True, x=400, y=840,
        fields={"BROADCAST_OPTION": ["주문시전", BR_SPELL]})
    isc_s = vrep("복제됨", V_MON_ISC); c_clone3 = cmp_op("operator_equals", isc_s, 1)
    st_s = vrep("게임상태", V_STATE); c_pl3 = cmp_op("operator_equals", st_s, 1)
    c_active3 = bool_op("operator_and", c_clone3, c_pl3)
    neg_sd = op("operator_subtract", 0, vrep("주문공격력", V_SPELLDMG))
    dec_sp_hp = b_changevar(bs, "내체력", V_MON_HP, neg_sd)
    # 데미지 숫자 팝업 재사용(폭심=그리스군 위치, 흰색 데미지)
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
        "⚡ 전체 번개가 치면(주문시전) 화면의 모든 그리스군이 동시에 주문공격력만큼 체력이 깎여요!\n"
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
        "현재점+1. 마지막 점을 지나면 성을 때려요(성벽체력 -1)!",
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
    if_t1 = tw_branch(1, V_ARR, "궁수대_사거리", V_ARD, "궁수대_공격력", V_ARG, "궁수대_간격", V_ARS, "궁수대_폭발반경", "궁수대")
    if_t2 = tw_branch(2, V_CAR, "발리스타_사거리", V_CAD, "발리스타_공격력", V_CAG, "발리스타_간격", V_CAS, "발리스타_폭발반경", "발리스타")
    if_t3 = tw_branch(3, V_MAR, "성화소_사거리", V_MAD, "성화소_공격력", V_MAG, "성화소_간격", V_MAS, "성화소_폭발반경", "성화소")
    chain([(if_t1, bs[if_t1]), (if_t2, bs[if_t2]), (if_t3, bs[if_t3])])

    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(vrep("설치X", V_PLACEX)), "Y": slot(vrep("설치Y", V_PLACEY))})
    bs[bs[g]["inputs"]["X"][1]]["parent"] = g
    bs[bs[g]["inputs"]["Y"][1]]["parent"] = g
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(42)})
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
        "발사쿨이 0이 되면 조준중=1 락을 잡고 '조준요청'을 방송하고 기다려요. 그동안 그리스군이 "
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
    d1 = op("operator_add", vrep("궁수대_공격력", V_ARD), vrep("공격력보너스", V_BUFATK))
    set_d1 = b_setvar(bs, "탄공격력", V_BOLT_DMG, d1)
    d2 = op("operator_add", vrep("발리스타_공격력", V_CAD), vrep("공격력보너스", V_BUFATK))
    set_d2 = b_setvar(bs, "탄공격력", V_BOLT_DMG, d2)
    d3 = op("operator_add", vrep("성화소_공격력", V_MAD), vrep("공격력보너스", V_BUFATK))
    set_d3 = b_setvar(bs, "탄공격력", V_BOLT_DMG, d3)
    t_eq2 = cmp_op("operator_equals", vrep("탄타입", V_BOLT_TYPE), 2)
    if_d2 = b_ifelse(bs, t_eq2, set_d2, set_d3)
    t_eq1 = cmp_op("operator_equals", vrep("탄타입", V_BOLT_TYPE), 1)
    if_dmg = b_ifelse(bs, t_eq1, set_d1, if_d2)
    # 탄반경 = 타입폭발반경 (분기)
    set_s1 = b_setvar(bs, "탄반경", V_BOLT_SPL, vrep("궁수대_폭발반경", V_ARS))
    set_s2 = b_setvar(bs, "탄반경", V_BOLT_SPL, vrep("발리스타_폭발반경", V_CAS))
    set_s3 = b_setvar(bs, "탄반경", V_BOLT_SPL, vrep("성화소_폭발반경", V_MAS))
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
    sw1 = b_costume(bs, "청동창"); sw2 = b_costume(bs, "투석"); sw3 = b_costume(bs, "성화구")
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
    tc_mon = b_touching(bs, "그리스군")
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
        "💥 맞은 자리 둘레(폭발반경) 안 그리스군이 한꺼번에 피해를 받아요.\n"
        "탄이 멈춘 자리에서 폭발X/Y·폭발데미지·폭발반경을 정하고 '타격'을 방송하고 기다리면, "
        "반경 안 그리스군이 모두 동시에 체력이 깎여요. 대포탑은 반경이 커서 무리를 한 방에!",
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

    # (B) 미리보기 forever — 맨 앞으로 매 틱 올리지 않음(스킬 아이콘 클릭 가로채기 방지)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    show = gen(); bs[show] = mk("looks_show")
    mx = gen(); bs[mx] = mk("sensing_mousex"); my = gen(); bs[my] = mk("sensing_mousey")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(mx), "Y": slot(my)})
    bs[mx]["parent"] = g; bs[my]["parent"] = g
    chain([(show, bs[show]), (g, bs[g])])
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
    # ── 길 위 설치 금지: 색 판정 + 경로 샘플 거리 판정 ──
    # 임시=1 이면 길 근처(설치 불가). 검사i 로 길판정 리스트 순회.
    def build_path_near_check():
        """마우스 위치가 길 샘플 R 이내인지 → 임시 0/1. 머리 블록 id 반환."""
        clr = b_setvar(bs, "임시", V_TMP, 0)
        set_i = b_setvar(bs, "검사i", V_I, 1)
        # body: 길거리X/Y = mouse - sample; if X²+Y² < R² then 임시=1; 검사i++
        mx = gen(); bs[mx] = mk("sensing_mousex")
        my = gen(); bs[my] = mk("sensing_mousey")
        sx = b_item_of(bs, "길판정X", L_SAMPX, vrep("검사i", V_I))
        sy = b_item_of(bs, "길판정Y", L_SAMPY, vrep("검사i", V_I))
        dx = op("operator_subtract", mx, sx)
        dy = op("operator_subtract", my, sy)
        set_dx = b_setvar(bs, "길거리X", V_PDX, dx)
        set_dy = b_setvar(bs, "길거리Y", V_PDY, dy)
        dx2 = op("operator_multiply", vrep("길거리X", V_PDX), vrep("길거리X", V_PDX))
        dy2 = op("operator_multiply", vrep("길거리Y", V_PDY), vrep("길거리Y", V_PDY))
        d2 = op("operator_add", dx2, dy2)
        c_near = cmp_op("operator_lt", d2, PATH_BLOCK_R2)
        mark = b_setvar(bs, "임시", V_TMP, 1)
        if_near = b_if(bs, c_near, mark)
        inc_i = b_changevar(bs, "검사i", V_I, 1)
        chain([(set_dx, bs[set_dx]), (set_dy, bs[set_dy]), (if_near, bs[if_near]),
               (inc_i, bs[inc_i])])
        n_samp = b_length_of(bs, "길판정X", L_SAMPX)
        rep = b_repeat(bs, n_samp, set_dx)
        chain([(clr, bs[clr]), (set_i, bs[set_i]), (rep, bs[rep])])
        return clr

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
    pb1 = place_branch(V_COSTA, "궁수대가격")
    pb2 = place_branch(V_COSTC, "발리스타가격")
    pb3 = place_branch(V_COSTM, "성화소가격")
    sel_eq2 = cmp_op("operator_equals", vrep("선택포탑", V_SEL), 2)
    if_p2 = b_ifelse(bs, sel_eq2, pb2, pb3)
    sel_eq1 = cmp_op("operator_equals", vrep("선택포탑", V_SEL), 1)
    if_price = b_ifelse(bs, sel_eq1, pb1, if_p2)

    # 클릭 지점으로 커서 이동 → 길/성/포탑 위면 거부 → 아니면 설치
    g2x = gen(); bs[g2x] = mk("sensing_mousex"); g2y = gen(); bs[g2y] = mk("sensing_mousey")
    g2 = gen(); bs[g2] = mk("motion_gotoxy", inputs={"X": slot(g2x), "Y": slot(g2y)})
    bs[g2x]["parent"] = g2; bs[g2y]["parent"] = g2
    path_chk = build_path_near_check()
    # blocked = 임시==1(길근처) OR 색길 OR 성 OR 포탑
    c_on_path = cmp_op("operator_equals", vrep("임시", V_TMP), 1)
    tc_path = b_touchingcolor(bs, PATH_COLOR)
    tc_castle = b_touching(bs, "트로이성채")
    tc_tw = b_touching(bs, "포탑")
    or_a = bool_op("operator_or", c_on_path, tc_path)
    or_b = bool_op("operator_or", or_a, tc_castle)
    blocked = bool_op("operator_or", or_b, tc_tw)
    allow = gen(); bs[allow] = mk("operator_not", inputs={"OPERAND": [2, blocked]})
    bs[blocked]["parent"] = allow
    sh_inv, sp_inv = b_sound(bs, 0, "error")
    if_valid = b_ifelse(bs, allow, if_price, sh_inv)
    chain([(path_chk, bs[path_chk]), (if_valid, bs[if_valid])])

    tc_pal2 = b_touching(bs, "팔레트")
    notpal = gen(); bs[notpal] = mk("operator_not", inputs={"OPERAND": [2, tc_pal2]})
    bs[tc_pal2]["parent"] = notpal
    if_notpal = b_if(bs, notpal, path_chk)            # 팔레트 클릭(선택)은 조용히 무시
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
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-138)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(82)})
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
    ca0a = cmp_op("operator_equals", vrep("발리스타해금", V_UNCA), 0)
    ma0a = cmp_op("operator_equals", vrep("성화소해금", V_UNMA), 0)
    c_both = bool_op("operator_and", ca0a, ma0a)
    ma0b = cmp_op("operator_equals", vrep("성화소해금", V_UNMA), 0)
    ca0c = cmp_op("operator_equals", vrep("발리스타해금", V_UNCA), 0)
    if_inner2 = b_ifelse(bs, ca0c, sw_ma, sw_all)
    if_inner = b_ifelse(bs, ma0b, sw_ca, if_inner2)
    if_cos = b_ifelse(bs, c_both, sw_both, if_inner)
    w = b_wait(bs, 0.1)
    chain([(if_cos, bs[if_cos]), (w, bs[w])])
    fe = b_forever(bs, if_cos)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    # 클릭(마우스 누름 폴링) → 4구간 판정 (버튼 경계 scratch x: -116 / 0 / 116)
    #   x<-116 → 화살탑(1) ; <0 → 대포탑(2, 해금시) ; <116 → 마법탑(3, 해금시) ; 그밖 → 성벽수리(즉시)
    #  ※ when-this-sprite-clicked 대신 forever 폴링: 포탑을 하나 고르면 유령미리보기(맨 앞)가 마우스
    #    위에 떠 다음 팔레트 버튼 클릭을 가로채던 버그가 있었음 → 마우스 누름을 직접 감지해 front 가림과
    #    무관하게 항상 먹히게 함.
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=380, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # 1구간: 선택포탑=1
    set_sel1 = b_setvar(bs, "선택포탑", V_SEL, 1)
    # 2구간: if 대포해금=1 → 선택포탑=2
    set_sel2 = b_setvar(bs, "선택포탑", V_SEL, 2)
    ca1 = cmp_op("operator_equals", vrep("발리스타해금", V_UNCA), 1)
    if_ca = b_if(bs, ca1, set_sel2)
    # 3구간: if 마법해금=1 → 선택포탑=3
    set_sel3 = b_setvar(bs, "선택포탑", V_SEL, 3)
    ma1 = cmp_op("operator_equals", vrep("성화소해금", V_UNMA), 1)
    if_ma = b_if(bs, ma1, set_sel3)
    # 4구간(성벽수리): 즉시 액션 — 선택포탑은 그대로!
    #   if 골드>=수리비용 and 성벽체력<성벽최대체력 → 골드-=수리비용 ; 성벽체력+=수리량 ; 상한 클램프 ; 수리음
    #   else → 에러음 (변화 없음)
    gold_r = vrep("골드", V_GOLDCUR); cost_r = vrep("수리비용", V_REPAIRCOST)
    c_poor = cmp_op("operator_lt", gold_r, cost_r)           # 골드 < 수리비용
    c_gold = gen(); bs[c_gold] = mk("operator_not", inputs={"OPERAND": [2, c_poor]})
    bs[c_poor]["parent"] = c_gold                            # 골드 >= 수리비용
    castle_r = vrep("성벽체력", V_CASTLE); cmax_r = vrep("성벽최대체력", V_CASTLEMAX)
    c_notfull = cmp_op("operator_lt", castle_r, cmax_r)      # 성벽체력 < 성벽최대체력
    c_can = bool_op("operator_and", c_gold, c_notfull)
    neg_cost = op("operator_subtract", 0, vrep("수리비용", V_REPAIRCOST))
    dec_gold = b_changevar(bs, "골드", V_GOLDCUR, neg_cost)
    add_hp = b_changevar(bs, "성벽체력", V_CASTLE, vrep("수리량", V_REPAIRAMT))
    castle_r2 = vrep("성벽체력", V_CASTLE); cmax_r2 = vrep("성벽최대체력", V_CASTLEMAX)
    c_over = cmp_op("operator_gt", castle_r2, cmax_r2)       # 성벽체력 > 성벽최대체력
    set_clamp = b_setvar(bs, "성벽체력", V_CASTLE, vrep("성벽최대체력", V_CASTLEMAX))
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
    c_band = cmp_op("operator_lt", my, -100)
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
        "폴링해요(버그 수정). 왼쪽부터 궁수대·발리스타·성화소를 고르고(선택포탑 1·2·3), 맨 오른쪽 "
        "'성벽수리'를 누르면 골드 수리비용을 내고 성벽체력을 수리량만큼 회복해요(성벽최대체력에서 멈춤). "
        "골드가 모자라거나 이미 풀피면 에러음만 나요. 성벽수리는 선택포탑을 바꾸지 않아요! "
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
#  강화카드 (RANDOM UPGRADE: 웨이브 클리어 시 비약적 랜덤 강화)
# ============================================================
def build_card_blocks():
    """웨이브 클리어 → 강화 3종 제시 → 1/2/3 키로 택1."""
    bs = {}
    comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    # 제목 바만 (얇은 패널) — 카드 위쪽
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(95)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["강화등장", BR_UP]})
    # 게임상태=2 유지, 선택 대기
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)

    # ── 강화 3종: 1~6 중 서로 겹치지 않게 뽑기 (repeat until 재추첨) ──
    r1 = gen(); bs[r1] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_o1 = b_setvar(bs, "강화선택1", V_OPT1, r1)

    r2 = gen(); bs[r2] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_o2 = b_setvar(bs, "강화선택2", V_OPT2, r2)
    # opt2 재추첨 바디
    r2b = gen(); bs[r2b] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_o2b = b_setvar(bs, "강화선택2", V_OPT2, r2b)
    c_eq12 = cmp_op("operator_equals", vrep("강화선택2", V_OPT2), vrep("강화선택1", V_OPT1))
    c_ok2 = gen(); bs[c_ok2] = mk("operator_not", inputs={"OPERAND": [2, c_eq12]})
    bs[c_eq12]["parent"] = c_ok2
    ru2 = gen(); bs[ru2] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_ok2], "SUBSTACK": [2, set_o2b]})
    bs[c_ok2]["parent"] = ru2
    bs[set_o2b]["parent"] = ru2

    r3 = gen(); bs[r3] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_o3 = b_setvar(bs, "강화선택3", V_OPT3, r3)
    r3b = gen(); bs[r3b] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_o3b = b_setvar(bs, "강화선택3", V_OPT3, r3b)
    c_eq31 = cmp_op("operator_equals", vrep("강화선택3", V_OPT3), vrep("강화선택1", V_OPT1))
    c_eq32 = cmp_op("operator_equals", vrep("강화선택3", V_OPT3), vrep("강화선택2", V_OPT2))
    c_dup3 = bool_op("operator_or", c_eq31, c_eq32)
    c_ok3 = gen(); bs[c_ok3] = mk("operator_not", inputs={"OPERAND": [2, c_dup3]})
    bs[c_dup3]["parent"] = c_ok3
    ru3 = gen(); bs[ru3] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_ok3], "SUBSTACK": [2, set_o3b]})
    bs[c_ok3]["parent"] = ru3
    bs[set_o3b]["parent"] = ru3

    show = gen(); bs[show] = mk("looks_show")
    # 선택 대기: 강화칸선택=0 으로 두고 >0 될 때까지 (숫자키 또는 카드 클릭)
    set_pick0 = b_setvar(bs, "강화칸선택", V_UPICK, 0)
    # 키 폴링 forever 조각 — wait until 강화칸선택>0 과 병렬로 키를 박아 넣음
    # (wait until 직후 키가 이미 떼져 있으면 if keypressed 가 실패하던 버그 수정)
    hk = gen(); bs[hk] = mk("event_whenbroadcastreceived", top=True, x=420, y=200,
        fields={"BROADCAST_OPTION": ["강화등장", BR_UP]})
    def key_to_pick(key, n):
        c_st = cmp_op("operator_equals", vrep("게임상태", V_STATE), 2)
        c_idle = cmp_op("operator_equals", vrep("강화칸선택", V_UPICK), 0)
        c_ready = bool_op("operator_and", c_st, c_idle)
        c_key = b_keypressed(bs, key)
        c_all = bool_op("operator_and", c_ready, c_key)
        set_p = b_setvar(bs, "강화칸선택", V_UPICK, n)
        return b_if(bs, c_all, set_p)
    if_k1p = key_to_pick("1", 1)
    if_k2p = key_to_pick("2", 2)
    if_k3p = key_to_pick("3", 3)
    w_poll = b_wait(bs, 0.05)
    chain([(if_k1p, bs[if_k1p]), (if_k2p, bs[if_k2p]), (if_k3p, bs[if_k3p]), (w_poll, bs[w_poll])])
    fe_poll = b_forever(bs, if_k1p)
    chain([(hk, bs[hk]), (fe_poll, bs[fe_poll])])

    c_picked = cmp_op("operator_gt", vrep("강화칸선택", V_UPICK), 0)
    wu = b_waituntil(bs, c_picked)

    # 선택 적용: 강화칸선택 → 해당 OPT 를 강화롤에 넣고 타입별 적용
    def apply_from_opt(opt_name, opt_id):
        set_roll = b_setvar(bs, "강화롤", V_ROLL, vrep(opt_name, opt_id))
        # 1 atk
        atk_amt = op("operator_multiply", vrep("강화량", V_UP), 2)
        ch_atk = b_changevar(bs, "공격력보너스", V_BUFATK, atk_amt)
        if1 = b_if(bs, cmp_op("operator_equals", vrep("강화롤", V_ROLL), 1), ch_atk)
        # 2 rng
        rng_amt = op("operator_multiply", 15, vrep("강화량", V_UP))
        ch_rng = b_changevar(bs, "사거리보너스", V_BUFRNG, rng_amt)
        if2 = b_if(bs, cmp_op("operator_equals", vrep("강화롤", V_ROLL), 2), ch_rng)
        # 3 rof
        rof_mul = op("operator_multiply", vrep("연사보너스", V_BUFROF), 0.6)
        set_rof = b_setvar(bs, "연사보너스", V_BUFROF, rof_mul)
        c_low = cmp_op("operator_lt", vrep("연사보너스", V_BUFROF), 0.18)
        set_min = b_setvar(bs, "연사보너스", V_BUFROF, 0.18)
        if_cl = b_if(bs, c_low, set_min)
        chain([(set_rof, bs[set_rof]), (if_cl, bs[if_cl])])
        if3 = b_if(bs, cmp_op("operator_equals", vrep("강화롤", V_ROLL), 3), set_rof)
        # 4 gold — 즉시 +강화골드량 + 골드 팝업 피드백
        ch_g = b_changevar(bs, "골드", V_GOLDCUR, vrep("강화골드량", V_UPGOLD))
        set_dv = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("강화골드량", V_UPGOLD))
        set_dx = b_setvar(bs, "데미지표시x", V_DMGX, 0)
        set_dy = b_setvar(bs, "데미지표시y", V_DMGY, 40)
        set_dk = b_setvar(bs, "팝업종류", V_DMGKIND, 1)
        bc_pg = b_broadcast(bs, "데미지표시", BR_DMG)
        chain([(ch_g, bs[ch_g]), (set_dv, bs[set_dv]), (set_dx, bs[set_dx]),
               (set_dy, bs[set_dy]), (set_dk, bs[set_dk]), (bc_pg, bs[bc_pg])])
        if4 = b_if(bs, cmp_op("operator_equals", vrep("강화롤", V_ROLL), 4), ch_g)
        # 5 skill up
        ch_pow = b_changevar(bs, "스킬위력", V_SKPOWER, 5)
        ch_d1 = b_changevar(bs, "아폴론데미지", V_SK1DMG, 20)
        ch_d2 = b_changevar(bs, "아레스데미지", V_SK2DMG, 25)
        ch_d3 = b_changevar(bs, "아르테미스데미지", V_SK3DMG, 22)
        ch_r1 = b_changevar(bs, "아폴론반경", V_SK1R, 18)
        ch_r2 = b_changevar(bs, "아레스반경", V_SK2R, 16)
        ch_r3 = b_changevar(bs, "아르테미스반경", V_SK3R, 18)
        chain([(ch_pow, bs[ch_pow]), (ch_d1, bs[ch_d1]), (ch_d2, bs[ch_d2]), (ch_d3, bs[ch_d3]),
               (ch_r1, bs[ch_r1]), (ch_r2, bs[ch_r2]), (ch_r3, bs[ch_r3])])
        if5 = b_if(bs, cmp_op("operator_equals", vrep("강화롤", V_ROLL), 5), ch_pow)
        # 6 zeus +1
        ch_z = b_changevar(bs, "주문횟수", V_SPELLCOUNT, 1)
        if6 = b_if(bs, cmp_op("operator_equals", vrep("강화롤", V_ROLL), 6), ch_z)
        chain([(set_roll, bs[set_roll]), (if1, bs[if1]), (if2, bs[if2]), (if3, bs[if3]),
               (if4, bs[if4]), (if5, bs[if5]), (if6, bs[if6])])
        return set_roll

    app1 = apply_from_opt("강화선택1", V_OPT1)
    app2 = apply_from_opt("강화선택2", V_OPT2)
    app3 = apply_from_opt("강화선택3", V_OPT3)
    # if-else 로 정확히 하나만 적용 (키 동시/릴리즈 레이스 방지)
    if_p2 = b_ifelse(bs, cmp_op("operator_equals", vrep("강화칸선택", V_UPICK), 2), app2, app3)
    if_p1 = b_ifelse(bs, cmp_op("operator_equals", vrep("강화칸선택", V_UPICK), 1), app1, if_p2)

    sh_up, sp_up = b_sound(bs, 0, "upgrade")
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    w1 = b_wait(bs, 0.15)
    set_pick_clear = b_setvar(bs, "강화칸선택", V_UPICK, 0)
    inc_wave = b_changevar(bs, "웨이브", V_WAVE, 1)
    wv_r2 = vrep("웨이브", V_WAVE); unlkc_r2 = vrep("발리스타해금웨이브", V_UNLKC)
    lt_ca = cmp_op("operator_lt", wv_r2, unlkc_r2)
    ge_ca = gen(); bs[ge_ca] = mk("operator_not", inputs={"OPERAND": [2, lt_ca]})
    bs[lt_ca]["parent"] = ge_ca
    set_unca = b_setvar(bs, "발리스타해금", V_UNCA, 1)
    if_unca = b_if(bs, ge_ca, set_unca)
    wv_r3 = vrep("웨이브", V_WAVE); unlkm_r = vrep("성화소해금웨이브", V_UNLKM)
    lt_ma = cmp_op("operator_lt", wv_r3, unlkm_r)
    ge_ma = gen(); bs[ge_ma] = mk("operator_not", inputs={"OPERAND": [2, lt_ma]})
    bs[lt_ma]["parent"] = ge_ma
    set_unma = b_setvar(bs, "성화소해금", V_UNMA, 1)
    if_unma = b_if(bs, ge_ma, set_unma)
    set_spawned0 = b_setvar(bs, "스폰완료", V_SPAWNED, 0)
    set_st1 = b_setvar(bs, "게임상태", V_STATE, 1)
    bc_done = b_broadcast(bs, "강화완료", BR_UPDONE)

    chain([(hb, bs[hb]), (set_st2, bs[set_st2]),
           (set_o1, bs[set_o1]), (set_o2, bs[set_o2]), (ru2, bs[ru2]),
           (set_o3, bs[set_o3]), (ru3, bs[ru3]),
           (show, bs[show]), (set_pick0, bs[set_pick0]), (wu, bs[wu]),
           (if_p1, bs[if_p1]),
           (sh_up, bs[sh_up]), (sp_up, bs[sp_up]), (hi2, bs[hi2]), (w1, bs[w1]),
           (set_pick_clear, bs[set_pick_clear]),
           (inc_wave, bs[inc_wave]), (if_unca, bs[if_unca]), (if_unma, bs[if_unma]),
           (set_spawned0, bs[set_spawned0]), (set_st1, bs[set_st1]), (bc_done, bs[bc_done])])

    add_comment(bs, comments, hb,
        "웨이브 클리어 → 강화 3종! 1·2·3 키 또는 카드 클릭으로 선택.\n"
        "공격/사거리/연사/골드보급(+강화골드량)/스킬업/제우스+1. 서로 다른 3개.",
        x=420, y=180, w=340, h=140)
    return bs, comments


def build_upgrade_slot_blocks(slot_n, x_pos):
    """강화 선택 칸 — 강화선택N 값에 맞는 코스튬 표시."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    opt_name = f"강화선택{slot_n}"
    opt_id = {1: V_OPT1, 2: V_OPT2, 3: V_OPT3}[slot_n]

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    # 카드는 화면 중앙 (제목 바 y=95 아래)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(x_pos), "Y": num(5)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["강화등장", BR_UP]})
    # 코스튬 = 강화선택 값 (1~6)
    opt = vrep(opt_name, opt_id)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(opt)})
    bs[opt]["parent"] = sw
    show = gen(); bs[show] = mk("looks_show")
    # 잠깐 기다린 뒤 맨 앞 — 패널/스킬/HUD보다 확실히 위
    w0 = b_wait(bs, 0.05)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    # 선택 끝날 때까지 주기적으로 맨 앞 유지 (다른 스프라이트 go-front 에 밀리지 않게)
    st2 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 2)
    front2 = gen(); bs[front2] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    w1 = b_wait(bs, 0.1)
    chain([(front2, bs[front2]), (w1, bs[w1])])
    # repeat until 게임상태 != 2
    # Scratch: wait until not state=2, but we need loop while state=2
    # forever with if state=2 go front
    fe_body_show = front2
    # Use: forever { if state==2: go front; wait 0.1 } but only after show
    # Simpler: wait until keys handled by parent; just go front a few times
    rep_front = b_repeat(bs, 3, front2)
    chain([(hb, bs[hb]), (sw, bs[sw]), (show, bs[show]), (w0, bs[w0]),
           (front, bs[front]), (rep_front, bs[rep_front])])

    # 선택 대기 중 계속 앞에: forever if 게임상태=2 go front
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=20, y=520,
        fields={"BROADCAST_OPTION": ["강화등장", BR_UP]})
    c_pick = cmp_op("operator_equals", vrep("게임상태", V_STATE), 2)
    fr3 = gen(); bs[fr3] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    w2 = b_wait(bs, 0.08)
    chain([(fr3, bs[fr3]), (w2, bs[w2])])
    if_pick = b_if(bs, c_pick, fr3)
    # forever: if picking go front
    w3 = b_wait(bs, 0.08)
    chain([(if_pick, bs[if_pick]), (w3, bs[w3])])
    fe = b_forever(bs, if_pick)
    chain([(hf, bs[hf]), (fe, bs[fe])])

    # 강화완료 시 숨김
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION": ["강화완료", BR_UPDONE]})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(hd, bs[hd]), (hi2, bs[hi2])])

    # 카드 클릭 → 강화칸선택 = slot_n (키를 짧게 눌러 놓치던 문제 보완)
    hc = gen(); bs[hc] = mk("event_whenthisspriteclicked", top=True, x=20, y=700)
    c_st = cmp_op("operator_equals", vrep("게임상태", V_STATE), 2)
    c_idle = cmp_op("operator_equals", vrep("강화칸선택", V_UPICK), 0)
    c_ok = bool_op("operator_and", c_st, c_idle)
    set_pick = b_setvar(bs, "강화칸선택", V_UPICK, slot_n)
    if_click = b_if(bs, c_ok, set_pick)
    chain([(hc, bs[hc]), (if_click, bs[if_click])])
    return bs, comments


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

    # (A) 깃발 — 숨김 + 화면 밖으로 치움 (좌상단 잔상 방지)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    goff = gen(); bs[goff] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-300)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(42)})
    gh = gen(); bs[gh] = mk("looks_seteffectto", inputs={"VALUE": num(55)},
        fields={"EFFECT": ["GHOST", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (goff, bs[goff]), (rs, bs[rs]), (sz, bs[sz]), (gh, bs[gh])])

    # (B) 게임시작 후: 선택포탑>0 and 전투중 → 코스튬→마우스→표시 (go-front 루프 없음)
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sel_r = vrep("선택포탑", V_SEL); c_sel = cmp_op("operator_gt", sel_r, 0)
    st_r = vrep("게임상태", V_STATE); c_pl = cmp_op("operator_equals", st_r, 1)
    c_on = bool_op("operator_and", c_sel, c_pl)
    sel_cos = vrep("선택포탑", V_SEL)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(sel_cos)})
    bs[sel_cos]["parent"] = sw
    mx = gen(); bs[mx] = mk("sensing_mousex"); my = gen(); bs[my] = mk("sensing_mousey")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(mx), "Y": slot(my)})
    bs[mx]["parent"] = g; bs[my]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")
    chain([(sw, bs[sw]), (g, bs[g]), (show, bs[show])])
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    goff2 = gen(); bs[goff2] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-300)})
    chain([(hi2, bs[hi2]), (goff2, bs[goff2])])
    if_on = b_ifelse(bs, c_on, sw, hi2)
    w = b_wait(bs, 0.02)
    chain([(if_on, bs[if_on]), (w, bs[w])])
    fe = b_forever(bs, if_on)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    add_comment(bs, comments, hb,
        "고른 방어탑을 마우스 위 반투명으로 미리 보여요. 숨길 때는 화면 밖으로 보내 좌상단 잔상을 막아요.",
        x=420, y=180, w=320, h=120)

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
    # 팔레트와 동일 스케일(82) → 버튼 칸과 같은 크기
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(82)})
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sel_r = vrep("선택포탑", V_SEL); c_sel = cmp_op("operator_gt", sel_r, 0)
    # 팔레트 size 82%: 버튼 중심 x = (-174 + (sel-1)*116) * 0.82
    sub = op("operator_subtract", vrep("선택포탑", V_SEL), 1)
    mul = op("operator_multiply", sub, 116)
    base = op("operator_add", -174, mul)
    xexpr = op("operator_multiply", base, 0.82)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(xexpr), "Y": num(-138)})
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
        "선택한 팔레트 칸과 같은 크기의 노란 테두리. 위치는 팔레트 스케일(0.82)에 맞춤.",
        x=420, y=180, w=300, h=100)

    return bs, comments

# ============================================================
#  번개효과 (LIGHTNING FLASH: 화려한 다단 번개 애니 — 6프레임)
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

    # 화려한 시퀀스: 흰 플래시 ↔ 번개1~6 교차, 점멸·밝기 변화 후 페이드
    gh0 = seteff("GHOST", 0)
    br0 = seteff("BRIGHTNESS", 40)
    cos_f1 = b_costume(bs, "번쩍")
    show = gen(); bs[show] = mk("looks_show")
    w1 = b_wait(bs, 0.035)
    cos_b1 = b_costume(bs, "번개1"); w2 = b_wait(bs, 0.04)
    gh1 = seteff("GHOST", 15)
    cos_f2 = b_costume(bs, "번쩍"); w3 = b_wait(bs, 0.03)
    gh2 = seteff("GHOST", 0); br1 = seteff("BRIGHTNESS", 70)
    cos_b2 = b_costume(bs, "번개2"); w4 = b_wait(bs, 0.045)
    cos_b3 = b_costume(bs, "번개3"); w5 = b_wait(bs, 0.04)
    cos_f3 = b_costume(bs, "번쩍"); w6 = b_wait(bs, 0.028)
    br2 = seteff("BRIGHTNESS", 100)
    cos_b4 = b_costume(bs, "번개4"); w7 = b_wait(bs, 0.045)
    cos_b5 = b_costume(bs, "번개5"); w8 = b_wait(bs, 0.04)
    cos_b6 = b_costume(bs, "번개6"); w9 = b_wait(bs, 0.05)
    br3 = seteff("BRIGHTNESS", 0)
    # 페이드 아웃
    inc = gen(); bs[inc] = mk("looks_changeeffectby", inputs={"CHANGE": num(20)},
        fields={"EFFECT": ["GHOST", None]})
    wf = b_wait(bs, 0.028)
    chain([(inc, bs[inc]), (wf, bs[wf])])
    rep = b_repeat(bs, 5, inc)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(hb, bs[hb]), (front, bs[front]), (gh0, bs[gh0]), (br0, bs[br0]),
           (cos_f1, bs[cos_f1]), (show, bs[show]), (w1, bs[w1]),
           (cos_b1, bs[cos_b1]), (w2, bs[w2]), (gh1, bs[gh1]), (cos_f2, bs[cos_f2]), (w3, bs[w3]),
           (gh2, bs[gh2]), (br1, bs[br1]), (cos_b2, bs[cos_b2]), (w4, bs[w4]),
           (cos_b3, bs[cos_b3]), (w5, bs[w5]), (cos_f3, bs[cos_f3]), (w6, bs[w6]),
           (br2, bs[br2]), (cos_b4, bs[cos_b4]), (w7, bs[w7]),
           (cos_b5, bs[cos_b5]), (w8, bs[w8]), (cos_b6, bs[cos_b6]), (w9, bs[w9]),
           (br3, bs[br3]), (rep, bs[rep]), (hi2, bs[hi2])])

    add_comment(bs, comments, hb,
        "⚡ 번개 궁극기 연출 — 흰 플래시와 번개1~6 코스튬이 빠르게 교차하며 밝기 효과까지 "
        "올려 화면 전체를 휩쓰는 느낌! ghost 로 스르륵 사라짐. 시각 전용(데미지·쿨은 주문버튼).",
        x=420, y=180, w=360, h=160)
    return bs, comments

# ============================================================
#  스킬 아이콘 HUD (아이콘 + 쿨 게이지 코스튬 / 시전)
# ============================================================
def _b_not(bs, c):
    nb = gen(); bs[nb] = mk("operator_not", inputs={"OPERAND": [2, c]})
    bs[c]["parent"] = nb
    return nb

def _cd_costume_logic(bs, vrep, op, cmp_op, bool_op, cd_name, cd_id, max_name, max_id,
                      *, bolt=False):
    """쿨 비율 → 코스튬 프레임 0..8 (ready_frac). 번개는 횟수 0이면 소진."""
    # ready_frac ≈ 1 - cd/max ; frame = round(ready * 8) + 1 (코스튬 번호 1-based)
    # frame = floor((max-cd)/max * 8) + 1,  cd<=0 → 9(풀)
    cd_pos = cmp_op("operator_gt", vrep(cd_name, cd_id), 0)
    sw_full = b_costume(bs, "g8")  # 준비 완료
    # ratio remaining = cd/max → empty fill
    # ready = (max - cd) / max * 8 → costume index
    # use: tmp = (max - cd) * 8 / max
    sub = op("operator_subtract", vrep(max_name, max_id), vrep(cd_name, cd_id))
    mul = op("operator_multiply", sub, SKILL_CD_FRAMES)
    div = op("operator_divide", mul, vrep(max_name, max_id))
    # clamp 0..8 via if
    # costume name g0..g8 — switch by number: costume # = floor(div)+1
    # Scratch costume by number: looks_switchcostumeto with number
    # frame = div + 1 but div may be float; round down by... just use div+1 as float, Scratch truncates?
    # Safer: set to g0..g8 by comparing thresholds
    add1 = op("operator_add", div, 1)  # 1..9 for g0..g8
    sw_cd = gen(); bs[sw_cd] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(add1)})
    bs[add1]["parent"] = sw_cd
    if_cd = b_ifelse(bs, cd_pos, sw_cd, sw_full)
    if not bolt:
        return if_cd
    # 번개: 주문횟수<=0 → 소진 코스튬(10번째)
    cnt_pos = cmp_op("operator_gt", vrep("주문횟수", V_SPELLCOUNT), 0)
    sw_ex = b_costume(bs, "소진")
    return b_ifelse(bs, cnt_pos, if_cd, sw_ex)


def _skill_select_only(bs, vrep, op, cmp_op, bool_op, skill_id, cd_name, cd_id):
    """아이콘/키: 쿨 준비 + 전투중이면 선택스킬=skill_id (시전은 맵 클릭)."""
    cd_pos = cmp_op("operator_gt", vrep(cd_name, cd_id), 0)
    not_cd = _b_not(bs, cd_pos)
    st = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    cond = bool_op("operator_and", not_cd, st)
    set_sel = b_setvar(bs, "선택스킬", V_SKSEL, skill_id)
    clr_tw = b_setvar(bs, "선택포탑", V_SEL, 0)
    chain([(set_sel, bs[set_sel]), (clr_tw, bs[clr_tw])])
    return b_if(bs, cond, set_sel)


def build_skill_fire_blocks():
    """아폴론 PNG — Q/클릭으로 조준 모드 (맵 클릭 시전)."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(70), "Y": num(138)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(62)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    cos0 = b_costume(bs, "g8")
    sk1_pos = cmp_op("operator_gt", vrep("아폴론쿨", V_SK1CD), 0)
    dec_sk1 = b_changevar(bs, "아폴론쿨", V_SK1CD, -0.1)
    if_sk1 = b_if(bs, sk1_pos, dec_sk1)
    cos_logic = _cd_costume_logic(bs, vrep, op, cmp_op, bool_op,
                                  "아폴론쿨", V_SK1CD, "아폴론쿨최대", V_SK1MAX)
    w = b_wait(bs, 0.1)
    chain([(if_sk1, bs[if_sk1]), (cos_logic, bs[cos_logic]), (w, bs[w])])
    fe = b_forever(bs, if_sk1)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (show, bs[show]), (cos0, bs[cos0]), (fe, bs[fe])])

    def arm():
        return _skill_select_only(bs, vrep, op, cmp_op, bool_op, 1, "아폴론쿨", V_SK1CD)

    hq = gen(); bs[hq] = mk("event_whenkeypressed", top=True, x=360, y=20,
        fields={"KEY_OPTION": ["q", None]})
    cq = arm(); chain([(hq, bs[hq]), (cq, bs[cq])])
    hc = gen(); bs[hc] = mk("event_whenthisspriteclicked", top=True, x=360, y=220)
    cc = arm(); chain([(hc, bs[hc]), (cc, bs[cc])])
    add_comment(bs, comments, hq,
        "아폴론(Q/아이콘): 조준 모드 → 맵 클릭으로 태양 광역. 트로이 편 수호신.",
        x=700, y=20, w=300, h=100)
    return bs, comments


def build_skill_spear_blocks():
    """아레스 PNG — E/클릭 조준 모드."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(118), "Y": num(138)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(62)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    cos0 = b_costume(bs, "g8")
    sk2_pos = cmp_op("operator_gt", vrep("아레스쿨", V_SK2CD), 0)
    dec_sk2 = b_changevar(bs, "아레스쿨", V_SK2CD, -0.1)
    if_sk2 = b_if(bs, sk2_pos, dec_sk2)
    cos_logic = _cd_costume_logic(bs, vrep, op, cmp_op, bool_op,
                                  "아레스쿨", V_SK2CD, "아레스쿨최대", V_SK2MAX)
    w = b_wait(bs, 0.1)
    chain([(if_sk2, bs[if_sk2]), (cos_logic, bs[cos_logic]), (w, bs[w])])
    fe = b_forever(bs, if_sk2)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (show, bs[show]), (cos0, bs[cos0]), (fe, bs[fe])])

    def arm():
        return _skill_select_only(bs, vrep, op, cmp_op, bool_op, 2, "아레스쿨", V_SK2CD)

    he = gen(); bs[he] = mk("event_whenkeypressed", top=True, x=360, y=20,
        fields={"KEY_OPTION": ["w", None]})
    ce = arm(); chain([(he, bs[he]), (ce, bs[ce])])
    hc = gen(); bs[hc] = mk("event_whenthisspriteclicked", top=True, x=360, y=220)
    cc = arm(); chain([(hc, bs[hc]), (cc, bs[cc])])
    return bs, comments



def build_skill_artemis_blocks():
    """아르테미스 PNG — E/클릭 조준 범위 스킬."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(166), "Y": num(138)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(62)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    cos0 = b_costume(bs, "g8")
    sk3_pos = cmp_op("operator_gt", vrep("아르테미스쿨", V_SK3CD), 0)
    dec_sk3 = b_changevar(bs, "아르테미스쿨", V_SK3CD, -0.1)
    if_sk3 = b_if(bs, sk3_pos, dec_sk3)
    cos_logic = _cd_costume_logic(bs, vrep, op, cmp_op, bool_op,
                                  "아르테미스쿨", V_SK3CD, "아르테미스쿨최대", V_SK3MAX)
    w = b_wait(bs, 0.1)
    chain([(if_sk3, bs[if_sk3]), (cos_logic, bs[cos_logic]), (w, bs[w])])
    fe = b_forever(bs, if_sk3)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (show, bs[show]), (cos0, bs[cos0]), (fe, bs[fe])])

    def arm():
        return _skill_select_only(bs, vrep, op, cmp_op, bool_op, 3, "아르테미스쿨", V_SK3CD)

    hr = gen(); bs[hr] = mk("event_whenkeypressed", top=True, x=360, y=20,
        fields={"KEY_OPTION": ["e", None]})
    cr = arm(); chain([(hr, bs[hr]), (cr, bs[cr])])
    hc = gen(); bs[hc] = mk("event_whenthisspriteclicked", top=True, x=360, y=220)
    cc = arm(); chain([(hc, bs[hc]), (cc, bs[cc])])
    add_comment(bs, comments, hr,
        "아르테미스(E/아이콘): 조준 후 맵 클릭 — 달빛 화살 범위. 트로이 편.",
        x=700, y=20, w=300, h=90)
    return bs, comments


def build_skill_bolt_blocks():
    """제우스 PNG — R/클릭 즉시 전역 궁극(3회)."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    def cast_ult():
        left_pos = cmp_op("operator_gt", vrep("주문쿨남음", V_SPELLLEFT), 0)
        not_cd = _b_not(bs, left_pos)
        st = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
        cnt_pos = cmp_op("operator_gt", vrep("주문횟수", V_SPELLCOUNT), 0)
        cond = bool_op("operator_and", bool_op("operator_and", not_cd, st), cnt_pos)
        set_left = b_setvar(bs, "주문쿨남음", V_SPELLLEFT, vrep("주문쿨", V_SPELLCD))
        dec_cnt = b_changevar(bs, "주문횟수", V_SPELLCOUNT, -1)
        clr = b_setvar(bs, "선택스킬", V_SKSEL, 0)
        set_fx = b_setvar(bs, "이펙트종류", V_FXKIND, 4)  # 제우스
        set_bx = b_setvar(bs, "폭발X", V_BOOMX, 0)
        set_by = b_setvar(bs, "폭발Y", V_BOOMY, 40)
        bc_fx = b_broadcast(bs, "스킬이펙트", BR_SKFX)
        sh, sp = b_sound(bs, 0, "skzeus")
        bc = b_broadcast(bs, "주문시전", BR_SPELL)
        chain([(set_left, bs[set_left]), (dec_cnt, bs[dec_cnt]), (clr, bs[clr]),
               (set_fx, bs[set_fx]), (set_bx, bs[set_bx]), (set_by, bs[set_by]),
               (bc_fx, bs[bc_fx]), (sh, bs[sh]), (sp, bs[sp]), (bc, bs[bc])])
        return b_if(bs, cond, set_left)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(214), "Y": num(138)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(62)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    cos0 = b_costume(bs, "g8")
    left_pos2 = cmp_op("operator_gt", vrep("주문쿨남음", V_SPELLLEFT), 0)
    dec_left = b_changevar(bs, "주문쿨남음", V_SPELLLEFT, -0.1)
    if_rech = b_if(bs, left_pos2, dec_left)
    cos_logic = _cd_costume_logic(bs, vrep, op, cmp_op, bool_op,
                                  "주문쿨남음", V_SPELLLEFT, "주문쿨", V_SPELLCD, bolt=True)
    w = b_wait(bs, 0.1)
    chain([(if_rech, bs[if_rech]), (cos_logic, bs[cos_logic]), (w, bs[w])])
    fe = b_forever(bs, if_rech)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (show, bs[show]), (cos0, bs[cos0]), (fe, bs[fe])])

    hk = gen(); bs[hk] = mk("event_whenkeypressed", top=True, x=360, y=20,
        fields={"KEY_OPTION": ["r", None]})
    ck = cast_ult(); chain([(hk, bs[hk]), (ck, bs[ck])])
    hc = gen(); bs[hc] = mk("event_whenthisspriteclicked", top=True, x=360, y=220)
    cc = cast_ult(); chain([(hc, bs[hc]), (cc, bs[cc])])
    add_comment(bs, comments, hk,
        "제우스(R/아이콘): 전역 벼락 궁극기. 게임당 3회. 롤의 R처럼!",
        x=700, y=20, w=300, h=90)
    return bs, comments


def build_skill_aim_blocks():
    """조준 링 + 맵 클릭 시전 (1=아폴론, 2=아레스)."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi0 = gen(); bs[hi0] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(h, bs[h]), (hi0, bs[hi0]), (rs, bs[rs]), (sz, bs[sz])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # go-front 루프 금지 → 스킬 아이콘 클릭을 가로채지 않음
    sel_r = vrep("선택스킬", V_SKSEL); c_sel = cmp_op("operator_gt", sel_r, 0)
    st = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_on = bool_op("operator_and", c_sel, st)
    show = gen(); bs[show] = mk("looks_show")
    mx = gen(); bs[mx] = mk("sensing_mousex"); my = gen(); bs[my] = mk("sensing_mousey")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(mx), "Y": slot(my)})
    bs[mx]["parent"] = g; bs[my]["parent"] = g
    chain([(show, bs[show]), (g, bs[g])])
    hi = gen(); bs[hi] = mk("looks_hide")
    if_vis = b_ifelse(bs, c_on, show, hi)
    w = b_wait(bs, 0.02)
    chain([(if_vis, bs[if_vis]), (w, bs[w])])
    fe = b_forever(bs, if_vis)
    chain([(hb, bs[hb]), (fe, bs[fe])])

    hp = gen(); bs[hp] = mk("event_whenbroadcastreceived", top=True, x=400, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    def cast_range(skill_n, cd_name, cd_id, max_name, max_id, dmg_name, dmg_id, r_name, r_id, mul):
        c_sk = cmp_op("operator_equals", vrep("선택스킬", V_SKSEL), skill_n)
        set_cd = b_setvar(bs, cd_name, cd_id, vrep(max_name, max_id))
        mx2 = gen(); bs[mx2] = mk("sensing_mousex")
        my2 = gen(); bs[my2] = mk("sensing_mousey")
        set_bx = b_setvar(bs, "폭발X", V_BOOMX, mx2)
        set_by = b_setvar(bs, "폭발Y", V_BOOMY, my2)
        pow_part = op("operator_multiply", vrep("스킬위력", V_SKPOWER), mul)
        dmg_total = op("operator_add", vrep(dmg_name, dmg_id), pow_part)
        set_bd = b_setvar(bs, "폭발데미지", V_BOOMD, dmg_total)
        set_br = b_setvar(bs, "폭발반경", V_BOOMR, vrep(r_name, r_id))
        clr = b_setvar(bs, "선택스킬", V_SKSEL, 0)
        sh, sp = b_sound(bs, 0, "thunder")
        bcw = b_broadcast_wait(bs, "타격", BR_HIT)
        w_db = b_wait(bs, 0.15)
        chain([(set_cd, bs[set_cd]), (set_bx, bs[set_bx]), (set_by, bs[set_by]),
               (set_bd, bs[set_bd]), (set_br, bs[set_br]), (clr, bs[clr]),
               (sh, bs[sh]), (sp, bs[sp]), (bcw, bs[bcw]), (w_db, bs[w_db])])
        return b_if(bs, c_sk, set_cd)

    def cast_range_fx(skill_n, cd_name, cd_id, max_name, max_id, dmg_name, dmg_id, r_name, r_id, mul, fx_kind, snd_name):
        c_sk = cmp_op("operator_equals", vrep("선택스킬", V_SKSEL), skill_n)
        set_cd = b_setvar(bs, cd_name, cd_id, vrep(max_name, max_id))
        mx2 = gen(); bs[mx2] = mk("sensing_mousex")
        my2 = gen(); bs[my2] = mk("sensing_mousey")
        set_bx = b_setvar(bs, "폭발X", V_BOOMX, mx2)
        set_by = b_setvar(bs, "폭발Y", V_BOOMY, my2)
        pow_part = op("operator_multiply", vrep("스킬위력", V_SKPOWER), mul)
        dmg_total = op("operator_add", vrep(dmg_name, dmg_id), pow_part)
        set_bd = b_setvar(bs, "폭발데미지", V_BOOMD, dmg_total)
        set_br = b_setvar(bs, "폭발반경", V_BOOMR, vrep(r_name, r_id))
        set_fx = b_setvar(bs, "이펙트종류", V_FXKIND, fx_kind)
        bc_fx = b_broadcast(bs, "스킬이펙트", BR_SKFX)
        # 시전 지점에 스킬 데미지 숫자 표시 (얼마 들어가는지 한눈에)
        set_pd = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("폭발데미지", V_BOOMD))
        set_px = b_setvar(bs, "데미지표시x", V_DMGX, vrep("폭발X", V_BOOMX))
        set_py = b_setvar(bs, "데미지표시y", V_DMGY, vrep("폭발Y", V_BOOMY))
        set_pk = b_setvar(bs, "팝업종류", V_DMGKIND, 0)
        bc_pd = b_broadcast(bs, "데미지표시", BR_DMG)
        clr = b_setvar(bs, "선택스킬", V_SKSEL, 0)
        sh, sp = b_sound(bs, 0, snd_name)
        bcw = b_broadcast_wait(bs, "타격", BR_HIT)
        w_db = b_wait(bs, 0.12)
        chain([(set_cd, bs[set_cd]), (set_bx, bs[set_bx]), (set_by, bs[set_by]),
               (set_bd, bs[set_bd]), (set_br, bs[set_br]), (set_fx, bs[set_fx]),
               (bc_fx, bs[bc_fx]),
               (set_pd, bs[set_pd]), (set_px, bs[set_px]), (set_py, bs[set_py]),
               (set_pk, bs[set_pk]), (bc_pd, bs[bc_pd]),
               (clr, bs[clr]),
               (sh, bs[sh]), (sp, bs[sp]), (bcw, bs[bcw]), (w_db, bs[w_db])])
        return b_if(bs, c_sk, set_cd)

    # mul = 스킬위력 배수 (강화할수록 데미지가 크게 붙음)
    c_apollo = cast_range_fx(1, "아폴론쿨", V_SK1CD, "아폴론쿨최대", V_SK1MAX,
                             "아폴론데미지", V_SK1DMG, "아폴론반경", V_SK1R, 12, 1, "skapolo")
    c_ares = cast_range_fx(2, "아레스쿨", V_SK2CD, "아레스쿨최대", V_SK2MAX,
                           "아레스데미지", V_SK2DMG, "아레스반경", V_SK2R, 14, 2, "skares")
    c_art = cast_range_fx(3, "아르테미스쿨", V_SK3CD, "아르테미스쿨최대", V_SK3MAX,
                          "아르테미스데미지", V_SK3DMG, "아르테미스반경", V_SK3R, 12, 3, "skartemis")
    chain([(c_apollo, bs[c_apollo]), (c_ares, bs[c_ares]), (c_art, bs[c_art])])

    md = gen(); bs[md] = mk("sensing_mousedown")
    sel_p = cmp_op("operator_gt", vrep("선택스킬", V_SKSEL), 0)
    st2 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    myb = gen(); bs[myb] = mk("sensing_mousey")
    c_map = cmp_op("operator_gt", myb, -100)
    g1 = bool_op("operator_and", md, sel_p)
    g2 = bool_op("operator_and", g1, st2)
    cond = bool_op("operator_and", g2, c_map)
    if_cast = b_if(bs, cond, c_apollo)
    w_poll = b_wait(bs, 0.05)
    chain([(if_cast, bs[if_cast]), (w_poll, bs[w_poll])])
    fe_poll = b_forever(bs, if_cast)
    chain([(hp, bs[hp]), (fe_poll, bs[fe_poll])])

    add_comment(bs, comments, hp,
        "범위 스킬 조준: 아폴론/아레스 선택 후 맵 클릭으로 시전. 노란 링이 마우스를 따라감.",
        x=720, y=200, w=320, h=110)
    return bs, comments


def build_hpbar_bg_blocks():
    """성벽 바 배경 — 한 번만 배치. forever go-front 금지(깜빡임 원인)."""
    bs = {}; comments = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-140), "Y": num(115)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (show, bs[show])])
    return bs, comments


def build_hpbar_fill_blocks():
    """빨간 채움 — size만 갱신. go-front 루프 없음(깜빡임 방지)."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-192), "Y": num(115)})
    show = gen(); bs[show] = mk("looks_show")
    mul2 = op("operator_multiply", vrep("성벽체력", V_CASTLE), 100)
    div2 = op("operator_divide", mul2, vrep("성벽최대체력", V_CASTLEMAX))
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": slot(div2)})
    bs[div2]["parent"] = sz
    set0 = gen(); bs[set0] = mk("looks_setsizeto", inputs={"SIZE": num(0)})
    c_dead = cmp_op("operator_lt", vrep("성벽체력", V_CASTLE), 1)
    if_sz = b_ifelse(bs, c_dead, set0, sz)
    w = b_wait(bs, 0.15)
    chain([(if_sz, bs[if_sz]), (w, bs[w])])
    fe = b_forever(bs, if_sz)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (show, bs[show]), (fe, bs[fe])])
    return bs, comments


# ============================================================
#  웨이브 HUD (패널 + 숫자 자릿수, 변수 모니터 대신)
# ============================================================
def build_wave_panel_blocks():
    """WAVE 패널 — 고정 배치, forever go-front 없음(깜빡임 방지)."""
    bs = {}; comments = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-140), "Y": num(148)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (show, bs[show])])
    return bs, comments


def build_wave_digits_blocks():
    """웨이브 일의 자리 — 코스튬만 갱신, go-front 루프 없음."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-105), "Y": num(148)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    show = gen(); bs[show] = mk("looks_show")
    wstr = vrep("웨이브", V_WAVE)
    lenb = gen(); bs[lenb] = mk("operator_length", inputs={"STRING": slot(wstr)})
    bs[wstr]["parent"] = lenb
    wstr2 = vrep("웨이브", V_WAVE)
    letter = gen(); bs[letter] = mk("operator_letter_of",
        inputs={"LETTER": slot(lenb), "STRING": slot(wstr2)})
    bs[lenb]["parent"] = letter; bs[wstr2]["parent"] = letter
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(letter)})
    bs[letter]["parent"] = sw
    w = b_wait(bs, 0.15)
    chain([(sw, bs[sw]), (w, bs[w])])
    fe = b_forever(bs, sw)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]),
           (show, bs[show]), (fe, bs[fe])])
    return bs, comments


def build_wave_tens_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-119), "Y": num(148)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    wstr = vrep("웨이브", V_WAVE)
    lenb = gen(); bs[lenb] = mk("operator_length", inputs={"STRING": slot(wstr)})
    bs[wstr]["parent"] = lenb
    c_multi = cmp_op("operator_gt", lenb, 1)
    show = gen(); bs[show] = mk("looks_show")
    wstr2 = vrep("웨이브", V_WAVE)
    letter = gen(); bs[letter] = mk("operator_letter_of",
        inputs={"LETTER": num(1), "STRING": slot(wstr2)})
    bs[wstr2]["parent"] = letter
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(letter)})
    bs[letter]["parent"] = sw
    chain([(show, bs[show]), (sw, bs[sw])])
    hi = gen(); bs[hi] = mk("looks_hide")
    if_m = b_ifelse(bs, c_multi, show, hi)
    w = b_wait(bs, 0.15)
    chain([(if_m, bs[if_m]), (w, bs[w])])
    fe = b_forever(bs, if_m)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (fe, bs[fe])])
    return bs, comments


def build_gold_panel_blocks():
    bs = {}; comments = {}
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-200), "Y": num(90)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]), (show, bs[show])])
    return bs, comments


def build_spell_count_digit_blocks():
    """번개 아이콘 옆 주문 잔여 횟수 (0–9 코스튬)."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(214), "Y": num(165)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(42)})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    show = gen(); bs[show] = mk("looks_show")
    # costume index = 주문횟수+1 (코스튬 "0"=1번 … "9"=10번)
    c_hi = cmp_op("operator_gt", vrep("주문횟수", V_SPELLCOUNT), 9)
    sw_hi = b_costume(bs, "9")
    idx = op("operator_add", vrep("주문횟수", V_SPELLCOUNT), 1)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(idx)})
    bs[idx]["parent"] = sw
    if_hi = b_ifelse(bs, c_hi, sw_hi, sw)
    w = b_wait(bs, 0.1)
    chain([(if_hi, bs[if_hi]), (w, bs[w])])
    fe = b_forever(bs, if_hi)
    chain([(h, bs[h]), (rs, bs[rs]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (show, bs[show]), (fe, bs[fe])])
    return bs, comments


def build_skill_fx_blocks():
    """스킬 시전 위치 이펙트 — 종류1 아폴론/2 아레스/3 아르테미스/4 제우스, 각 6프레임."""
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(140)})
    chain([(h, bs[h]), (hi, bs[hi]), (rs, bs[rs]), (sz, bs[sz])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["스킬이펙트", BR_SKFX]})
    gx = vrep("폭발X", V_BOOMX); gy = vrep("폭발Y", V_BOOMY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(gx), "Y": slot(gy)})
    bs[gx]["parent"] = g; bs[gy]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")
    # costume = (이펙트종류-1)*6 + frame  (1-based costume index)
    def make_frame(n):
        k2 = op("operator_subtract", vrep("이펙트종류", V_FXKIND), 1)
        base2 = op("operator_multiply", k2, 6)
        idx2 = op("operator_add", base2, n)
        sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": slot(idx2)})
        bs[idx2]["parent"] = sw
        return sw
    seq = [(hb, bs[hb]), (g, bs[g]), (show, bs[show])]
    for n, dur in [(1, 0.04), (2, 0.04), (3, 0.045), (4, 0.05), (5, 0.05), (6, 0.06)]:
        fr = make_frame(n)
        w = b_wait(bs, dur)
        seq += [(fr, bs[fr]), (w, bs[w])]
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    seq.append((hi2, bs[hi2]))
    chain(seq)
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

    def save_png(path):
        from PIL import Image
        with open(path, "rb") as f:
            b = f.read()
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.png", "wb") as f:
            f.write(b)
        im = Image.open(path)
        w, h = im.size
        return m, w, h

    def cos_png(name, path, cx=None, cy=None):
        m, w, h = save_png(path)
        return {
            "name": name, "bitmapResolution": 1, "dataFormat": "png",
            "assetId": m, "md5ext": f"{m}.png",
            "rotationCenterX": cx if cx is not None else w // 2,
            "rotationCenterY": cy if cy is not None else h // 2,
        }

    def save_png_img(im):
        from io import BytesIO
        buf = BytesIO(); im.save(buf, format="PNG"); b = buf.getvalue()
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.png", "wb") as f: f.write(b)
        return m, im.size[0], im.size[1]

    bg_md5     = save_svg(BG_SVG)
    # 트로이 에셋 PNG (Imagine 생성)
    castle_md5, cw, ch = save_png(f"{GEN}/core.png")
    # 적 단일 스프라이트 + 보스 3종 전용 (걷기 모션 롤백)
    gob_md5, gw, gh = save_png(f"{GEN}/enemy_light.png")
    orc_md5, ow, oh = save_png(f"{GEN}/enemy_mid.png")
    troll_md5, tw, th = save_png(f"{GEN}/enemy_heavy.png")
    aga_md5, agw, agh = save_png(f"{GEN}/boss_agamemnon.png")
    men_md5, mew, meh = save_png(f"{GEN}/boss_menelaus.png")
    ach_md5, acw, ach = save_png(f"{GEN}/boss_achilles.png")
    ex_md5, exw, exh = save_png(f"{GEN}/explosion.png")
    art_md5, aw, ah = save_png(f"{GEN}/tower_spear.png")
    cat_md5, caw, cah = save_png(f"{GEN}/tower_drum.png")
    mat_md5, mw, mh = save_png(f"{GEN}/tower_totem.png")
    arrow_md5, arw, arh = save_png(f"{GEN}/spear.png")
    ball_md5, baw, bah = save_png(f"{GEN}/rock.png")
    orb_md5, obw, obh = save_png(f"{GEN}/orb.png")
    cursor_md5 = save_svg(CURSOR_SVG)
    # 팔레트: 방어탑 PNG 합성
    pal_pngs = build_palette_pngs()
    pal_md5 = []
    for pim in pal_pngs:
        m, _, _ = save_png_img(pim)
        pal_md5.append(m)
    hl_md5     = save_svg(HIGHLIGHT_SVG)
    card_md5   = save_png(f"{GEN}/up_panel.png")[0]  # 3택1 패널 PNG
    rs_md5     = save_svg(RESULT_SVG)
    flash_md5  = save_svg(FLASH_SVG)
    light_md5  = [save_svg(s) for s in LIGHTNING_SVGS]
    # 스킬 아이콘 PNG 프레임 (쿨 게이지 합성) — 아폴론/아레스/아르테미스/제우스
    fire_md5, spear_md5, art_md5s, bolt_md5 = [], [], [], []
    skw = skh = 72
    for i in range(SKILL_CD_FRAMES + 1):
        m, w, h = save_png(f"{GEN}/skill_apollo_{i}.png"); fire_md5.append(m); skw, skh = w, h
        m, _, _ = save_png(f"{GEN}/skill_ares_{i}.png"); spear_md5.append(m)
        m, _, _ = save_png(f"{GEN}/skill_artemis_{i}.png"); art_md5s.append(m)
        m, _, _ = save_png(f"{GEN}/skill_zeus_{i}.png"); bolt_md5.append(m)
    m, _, _ = save_png(f"{GEN}/skill_zeus_{SKILL_CD_FRAMES + 1}.png"); bolt_md5.append(m)  # 소진
    # 강화 3택1 에셋
    up_panel_md5, _, _ = save_png(f"{GEN}/up_panel.png")
    up_type_md5 = [save_png(f"{GEN}/up_type_{i}.png")[0] for i in range(1, 7)]
    # 스킬 이펙트 프레임 12장
    fx_md5 = []
    for name in ("apollo", "ares", "artemis", "zeus"):
        for i in range(6):
            fx_md5.append(save_png(f"{GEN}/fx_{name}_{i}.png")[0])
    hpbg_md5  = save_svg(HP_BG_SVG)
    hpfill_md5 = save_svg(HP_FILL_SVG)
    wavep_md5 = save_svg(WAVE_PANEL_SVG)
    skaim_md5 = save_svg(SKILL_AIM_SVG)
    wd_md5     = [save_svg(s) for s in WHITE_DIGITS]
    gd_md5     = [save_svg(s) for s in GOLD_DIGITS]

    def load_sfx(name):
        """assets/sfx/{name}.wav → WORK/{md5}.wav, return (md5, sampleCount)."""
        path = os.path.join(SFXDIR, f"{name}.wav")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"SFX missing: {path}")
        with open(path, "rb") as f:
            b = f.read()
        # WAV header: sample rate @ 24, data size from RIFF or frames
        import struct as _st
        if b[0:4] != b"RIFF" or b[8:12] != b"WAVE":
            raise ValueError(f"not wav: {path}")
        rate = _st.unpack_from("<I", b, 24)[0]
        # find data chunk
        off = 12
        data_size = 0
        nch = _st.unpack_from("<H", b, 22)[0]
        bps = _st.unpack_from("<H", b, 34)[0]
        while off + 8 <= len(b):
            cid = b[off:off+4]
            csz = _st.unpack_from("<I", b, off+4)[0]
            if cid == b"data":
                data_size = csz
                break
            off += 8 + csz + (csz & 1)
        bytes_per = max(1, nch * (bps // 8))
        n_samples = data_size // bytes_per
        m = md5_bytes(b)
        WAV_RATES[m] = rate
        with open(f"{WORK}/{m}.wav", "wb") as f:
            f.write(b)
        return m, n_samples

    # assets/sfx/*.wav (SOURCE.txt 매핑)
    arrow_s, arrow_n = load_sfx("arrow")
    cannon_s, cannon_n = load_sfx("cannon")
    magic_s, magic_n = load_sfx("magic")
    skapo_s, skapo_n = load_sfx("skapolo")
    skares_s, skares_n = load_sfx("skares")
    skart_s, skart_n = load_sfx("skartemis")
    skzeus_s, skzeus_n = load_sfx("skzeus")
    hit_s, hit_n = load_sfx("hit")
    kill_s, kill_n = load_sfx("kill")
    coin_s, coin_n = load_sfx("coin")
    castle_s, castle_n = load_sfx("castlehit")
    horn_s, horn_n = load_sfx("horn")
    build_s, build_n = load_sfx("build")
    error_s, error_n = load_sfx("error")
    upg_s, upg_n = load_sfx("upgrade")
    repair_s, repair_n = load_sfx("repair")
    thunder_s, thunder_n = load_sfx("thunder")

    # BGM: 사용자 제공 mp3 를 바이너리 그대로 아카이브 (재인코딩 금지)
    BGM_SRC = os.path.join(ASSETS, "bgm.mp3")
    with open(BGM_SRC, "rb") as f:
        bgm_bytes = f.read()
    bgm_md5 = md5_bytes(bgm_bytes)
    with open(f"{WORK}/{bgm_md5}.mp3", "wb") as f:
        f.write(bgm_bytes)
    BGM_RATE = 48000
    BGM_SAMPLES = int(202.65 * BGM_RATE)  # Aegis of Marble ≈202.65s

    def snd(name, md5, n):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "",
                "rate": WAV_RATES.get(md5, SND_RATE), "sampleCount": n, "md5ext": f"{md5}.wav"}

    def snd_bgm():
        return {"name": "bgm", "assetId": bgm_md5, "dataFormat": "mp3", "format": "",
                "rate": BGM_RATE, "sampleCount": BGM_SAMPLES, "md5ext": f"{bgm_md5}.mp3"}

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
    fire_blocks,   fire_cmt   = build_skill_fire_blocks()
    spear_blocks,  spear_cmt  = build_skill_spear_blocks()
    art_blocks,    art_cmt    = build_skill_artemis_blocks()
    bolt_blocks_ui, bolt_cmt  = build_skill_bolt_blocks()
    skaim_blocks,  skaim_cmt  = build_skill_aim_blocks()
    skfx_blocks,   skfx_cmt   = build_skill_fx_blocks()
    up1_blocks, up1_cmt = build_upgrade_slot_blocks(1, -140)
    up2_blocks, up2_cmt = build_upgrade_slot_blocks(2, 0)
    up3_blocks, up3_cmt = build_upgrade_slot_blocks(3, 140)
    hpbg_blocks,   hpbg_cmt   = build_hpbar_bg_blocks()
    hpfill_blocks, hpfill_cmt = build_hpbar_fill_blocks()
    wavep_blocks,  wavep_cmt  = build_wave_panel_blocks()
    wave1_blocks,  wave1_cmt  = build_wave_digits_blocks()
    wave10_blocks, wave10_cmt = build_wave_tens_blocks()
    spcnt_blocks,  spcnt_cmt  = build_spell_count_digit_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            # 튜닝 43
            V_GOLD0: ["기본골드", 150], V_COSTA: ["궁수대가격", 50], V_COSTC: ["발리스타가격", 100],
            V_COSTM: ["성화소가격", 150], V_WAVEGOLD: ["웨이브클리어골드", 30], V_UPGOLD: ["강화골드량", 180],
            V_UP: ["강화량", 6], V_CASTLEMAX: ["성벽최대체력", 20], V_UNLKC: ["발리스타해금웨이브", 2],
            V_UNLKM: ["성화소해금웨이브", 4], V_BASECNT: ["기본그리스군수", 6], V_CNTINC: ["웨이브당그리스군증가", 2],
            V_SPGAP: ["그리스군간격", 0.8], V_HPINC: ["웨이브체력증가", 0], V_SPINC: ["웨이브속도증가", 0.05],
            V_REACH: ["도달반경", 12], V_BOLTSPD: ["탄속도", 12],
            V_GOBHP: ["경보병_체력", 3], V_GOBSP: ["경보병_속도", 2.2], V_GOBGOLD: ["경보병_골드", 5],
            V_ORCHP: ["호플리테스_체력", 8], V_ORCSP: ["호플리테스_속도", 1.5], V_ORCGOLD: ["호플리테스_골드", 10],
            V_TROLLHP: ["영웅_체력", 20], V_TROLLSP: ["영웅_속도", 0.9], V_TROLLGOLD: ["영웅_골드", 25],
            V_HPSCALE: ["적체력배율", 1], V_HPSCALE_INC: ["웨이브배율증가", 0.2],
            V_HPSCALE_BOSS: ["보스후배율", 1.5], V_BOSSEVERY: ["보스주기", 5],
            V_BOSSHP0: ["보스기본체력", 90], V_BOSSHPINC: ["보스단계체력", 55],
            V_BOSSSP: ["보스속도", 0.65], V_BOSSGOLD0: ["보스기본골드", 60], V_BOSSIDX: ["보스번호", 0],
            V_ARR: ["궁수대_사거리", 135], V_ARD: ["궁수대_공격력", 4], V_ARG: ["궁수대_간격", 0.35],
            V_ARS: ["궁수대_폭발반경", 24], V_CAR: ["발리스타_사거리", 115], V_CAD: ["발리스타_공격력", 7],
            V_CAG: ["발리스타_간격", 1.0], V_CAS: ["발리스타_폭발반경", 72], V_MAR: ["성화소_사거리", 165],
            V_MAD: ["성화소_공격력", 10], V_MAG: ["성화소_간격", 0.65], V_MAS: ["성화소_폭발반경", 32],
            V_REPAIRCOST: ["수리비용", 60], V_REPAIRAMT: ["수리량", 5],
            V_BGMVOL: ["브금볼륨", 55],
            V_SPELLDMG: ["주문공격력", 9999], V_SPELLCD: ["주문쿨", 18],
            V_SPELLMAX: ["주문최대횟수", 3],
            V_SK1CD: ["아폴론쿨", 0], V_SK1MAX: ["아폴론쿨최대", 8],
            V_SK1DMG: ["아폴론데미지", 40], V_SK1R: ["아폴론반경", 110],
            V_SK2CD: ["아레스쿨", 0], V_SK2MAX: ["아레스쿨최대", 9],
            V_SK2DMG: ["아레스데미지", 55], V_SK2R: ["아레스반경", 90],
            V_SK3CD: ["아르테미스쿨", 0], V_SK3MAX: ["아르테미스쿨최대", 10],
            V_SK3DMG: ["아르테미스데미지", 48], V_SK3R: ["아르테미스반경", 100],
            V_SKPOWER: ["스킬위력", 0], V_ROLL: ["강화롤", 0], V_SKSEL: ["선택스킬", 0],
            V_OPT1: ["강화선택1", 1], V_OPT2: ["강화선택2", 2], V_OPT3: ["강화선택3", 3],
            V_UPICK: ["강화칸선택", 0],
            V_FXKIND: ["이펙트종류", 0],
            # 진행
            V_STATE: ["게임상태", 1], V_WAVE: ["웨이브", 1], V_GOLDCUR: ["골드", 150],
            V_CASTLE: ["성벽체력", 20], V_ALIVE: ["적수", 0], V_SPAWNED: ["스폰완료", 0],
            V_SPAWNN: ["스폰카운트", 0], V_SEL: ["선택포탑", 0], V_UNCA: ["발리스타해금", 0],
            V_UNMA: ["성화소해금", 0], V_BUFATK: ["공격력보너스", 0], V_BUFRNG: ["사거리보너스", 0],
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
            V_I: ["검사i", 0], V_TMP: ["임시", 0],
            V_PDX: ["길거리X", 0], V_PDY: ["길거리Y", 0],
        },
        "lists": {
            L_PATHX: ["경로X", []],
            L_PATHY: ["경로Y", []],
            L_SAMPX: ["길판정X", []],
            L_SAMPY: ["길판정Y", []],
        },
        "broadcasts": {
            BR_START: "게임시작", BR_WAVE: "웨이브시작", BR_SPAWN: "그리스군생성", BR_AIM: "조준요청",
            BR_FIRE: "포탑발사", BR_HIT: "타격", BR_DMG: "데미지표시", BR_PLACE: "포탑설치",
            BR_UP: "강화등장", BR_UPDONE: "강화완료", BR_CASTLE: "성벽피격",
            BR_SPELL: "주문시전", BR_SK1: "아폴론시전", BR_SK2: "아레스시전", BR_SK3: "아르테미스시전", BR_SKFX: "스킬이펙트",
        },
        "blocks": stage_blocks, "comments": stage_cmt,
        "currentCostume": 0,
        "costumes": [{
            "name": "전장", "dataFormat": "svg", "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg", "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [snd_bgm(), snd("horn", horn_s, horn_n)],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    castle = {
        "isStage": False, "name": "트로이성채",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": castle_blocks, "comments": castle_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "castle", "bitmapResolution": 1, "dataFormat": "png",
            "assetId": castle_md5, "md5ext": f"{castle_md5}.png",
            "rotationCenterX": cw // 2, "rotationCenterY": ch // 2}],
        "sounds": [snd("castlehit", castle_s, castle_n)],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 195, "y": 70, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    def cos_png(name, md5, w, h):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "png",
                "assetId": md5, "md5ext": f"{md5}.png",
                "rotationCenterX": w // 2, "rotationCenterY": h // 2}

    monster = {
        "isStage": False, "name": "그리스군",
        "variables": {V_MON_ISC: ["복제됨", 0], V_MON_TYPE: ["내타입", 1], V_MON_HP: ["내체력", 3],
                      V_MON_SPD: ["내속도", 2.2], V_MON_GOLD: ["내골드", 5], V_MON_WP: ["현재점", 1]},
        "lists": {}, "broadcasts": {},
        "blocks": mon_blocks, "comments": mon_cmt,
        "currentCostume": 0,
        "costumes": [
            cos_png("경보병", gob_md5, gw, gh),
            cos_png("호플리테스", orc_md5, ow, oh),
            cos_png("영웅", troll_md5, tw, th),
            cos_png("아가멤논", aga_md5, agw, agh),
            cos_png("메넬라오스", men_md5, mew, meh),
            cos_png("아킬레우스", ach_md5, acw, ach),
            cos_png("폭발", ex_md5, exw, exh),
        ],
        "sounds": [snd("hit", hit_s, hit_n), snd("kill", kill_s, kill_n), snd("coin", coin_s, coin_n)],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": -220, "y": -100, "size": 70, "direction": 90,
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
            {"name": "궁수대", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": art_md5, "md5ext": f"{art_md5}.png", "rotationCenterX": aw // 2, "rotationCenterY": ah // 2},
            {"name": "발리스타", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": cat_md5, "md5ext": f"{cat_md5}.png", "rotationCenterX": caw // 2, "rotationCenterY": cah // 2},
            {"name": "성화소", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": mat_md5, "md5ext": f"{mat_md5}.png", "rotationCenterX": mw // 2, "rotationCenterY": mh // 2},
        ],
        "sounds": [snd("arrow", arrow_s, arrow_n), snd("cannon", cannon_s, cannon_n),
                   snd("magic", magic_s, magic_n)],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 0, "size": 42, "direction": 90,
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
            {"name": "청동창", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": arrow_md5, "md5ext": f"{arrow_md5}.png", "rotationCenterX": arw // 2, "rotationCenterY": arh // 2},
            {"name": "투석", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": ball_md5, "md5ext": f"{ball_md5}.png", "rotationCenterX": baw // 2, "rotationCenterY": bah // 2},
            {"name": "성화구", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": orb_md5, "md5ext": f"{orb_md5}.png", "rotationCenterX": obw // 2, "rotationCenterY": obh // 2},
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
        "volume": 100, "layerOrder": 20, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    palette = {
        "isStage": False, "name": "팔레트",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pal_blocks, "comments": pal_cmt,
        "currentCostume": 0,
        "costumes": [
            {"name": "둘다잠금", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": pal_md5[0], "md5ext": f"{pal_md5[0]}.png",
             "rotationCenterX": PAL_W // 2, "rotationCenterY": PAL_H // 2},
            {"name": "대포해금", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": pal_md5[1], "md5ext": f"{pal_md5[1]}.png",
             "rotationCenterX": PAL_W // 2, "rotationCenterY": PAL_H // 2},
            {"name": "마법해금", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": pal_md5[2], "md5ext": f"{pal_md5[2]}.png",
             "rotationCenterX": PAL_W // 2, "rotationCenterY": PAL_H // 2},
            {"name": "모두해금", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": pal_md5[3], "md5ext": f"{pal_md5[3]}.png",
             "rotationCenterX": PAL_W // 2, "rotationCenterY": PAL_H // 2},
        ],
        "sounds": [snd("repair", repair_s, repair_n), snd("error", error_s, error_n)],
        "volume": 100, "layerOrder": 28, "visible": True,
        "x": 0, "y": -138, "size": 82, "direction": 90,
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
        "costumes": [{"name": "card", "bitmapResolution": 1, "dataFormat": "png",
            "assetId": card_md5, "md5ext": f"{card_md5}.png",
            "rotationCenterX": 230, "rotationCenterY": 24}],
        "sounds": [snd("upgrade", upg_s, upg_n)],
        "volume": 100, "layerOrder": 150, "visible": False,
        "x": 0, "y": 95, "size": 100, "direction": 90,
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
            {"name": "궁수대미리", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": art_md5, "md5ext": f"{art_md5}.png", "rotationCenterX": aw // 2, "rotationCenterY": ah // 2},
            {"name": "발리스타미리", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": cat_md5, "md5ext": f"{cat_md5}.png", "rotationCenterX": caw // 2, "rotationCenterY": cah // 2},
            {"name": "성화소미리", "bitmapResolution": 1, "dataFormat": "png",
             "assetId": mat_md5, "md5ext": f"{mat_md5}.png", "rotationCenterX": mw // 2, "rotationCenterY": mh // 2},
        ],
        "sounds": [],
        "volume": 100, "layerOrder": 21, "visible": False,
        "x": 0, "y": -300, "size": 42, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    highlight = {
        "isStage": False, "name": "선택표시",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hl_blocks, "comments": hl_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "강조", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hl_md5, "md5ext": f"{hl_md5}.svg",
            "rotationCenterX": 56, "rotationCenterY": 29}],
        "sounds": [],
        "volume": 100, "layerOrder": 30, "visible": False,
        "x": 0, "y": -138, "size": 82, "direction": 90,
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
            {"name": "번개4", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": light_md5[3], "md5ext": f"{light_md5[3]}.svg",
             "rotationCenterX": 240, "rotationCenterY": 180},
            {"name": "번개5", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": light_md5[4], "md5ext": f"{light_md5[4]}.svg",
             "rotationCenterX": 240, "rotationCenterY": 180},
            {"name": "번개6", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": light_md5[5], "md5ext": f"{light_md5[5]}.svg",
             "rotationCenterX": 240, "rotationCenterY": 180},
        ],
        "sounds": [],
        "volume": 100, "layerOrder": 15, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    def skill_costumes(md5s, names_prefix="g"):
        out = []
        for i, m in enumerate(md5s):
            if names_prefix == "bolt" and i == len(md5s) - 1:
                nm = "소진"
            else:
                nm = f"g{i}" if i <= SKILL_CD_FRAMES else f"g{i}"
            out.append({"name": nm, "bitmapResolution": 1, "dataFormat": "svg",
                        "assetId": m, "md5ext": f"{m}.svg",
                        "rotationCenterX": 35, "rotationCenterY": 42})
        return out

    # fire/spear: g0..g8 ; bolt: g0..g8 + 소진
    cx, cy = skw // 2, skh // 2
    def sk_cos(md5s, exhaust=False):
        out = [{"name": f"g{i}", "bitmapResolution": 1, "dataFormat": "png",
                "assetId": md5s[i], "md5ext": f"{md5s[i]}.png",
                "rotationCenterX": cx, "rotationCenterY": cy}
               for i in range(SKILL_CD_FRAMES + 1)]
        if exhaust:
            out.append({"name": "소진", "bitmapResolution": 1, "dataFormat": "png",
                        "assetId": md5s[SKILL_CD_FRAMES + 1],
                        "md5ext": f"{md5s[SKILL_CD_FRAMES + 1]}.png",
                        "rotationCenterX": cx, "rotationCenterY": cy})
        return out
    fire_cos = sk_cos(fire_md5)
    spear_cos = sk_cos(spear_md5)
    art_cos = sk_cos(art_md5s)
    bolt_cos = sk_cos(bolt_md5, exhaust=True)
    up_slot_cos = [{"name": str(i), "bitmapResolution": 1, "dataFormat": "png",
                    "assetId": up_type_md5[i-1], "md5ext": f"{up_type_md5[i-1]}.png",
                    "rotationCenterX": 75, "rotationCenterY": 85} for i in range(1, 7)]
    fx_cos = [{"name": f"fx{i+1}", "bitmapResolution": 1, "dataFormat": "png",
               "assetId": fx_md5[i], "md5ext": f"{fx_md5[i]}.png",
               "rotationCenterX": 80, "rotationCenterY": 80} for i in range(24)]

    skill_fire = {
        "isStage": False, "name": "아폴론아이콘",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": fire_blocks, "comments": fire_cmt,
        "currentCostume": SKILL_CD_FRAMES,
        "costumes": fire_cos,
        "sounds": [snd("thunder", thunder_s, thunder_n)],
        "volume": 100, "layerOrder": 95, "visible": True,
        "x": 70, "y": 138, "size": 62, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    skill_spear = {
        "isStage": False, "name": "아레스아이콘",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": spear_blocks, "comments": spear_cmt,
        "currentCostume": SKILL_CD_FRAMES,
        "costumes": spear_cos,
        "sounds": [snd("thunder", thunder_s, thunder_n)],
        "volume": 100, "layerOrder": 96, "visible": True,
        "x": 118, "y": 138, "size": 62, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    skill_artemis = {
        "isStage": False, "name": "아르테미스아이콘",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": art_blocks, "comments": art_cmt,
        "currentCostume": SKILL_CD_FRAMES,
        "costumes": art_cos,
        "sounds": [snd("thunder", thunder_s, thunder_n)],
        "volume": 100, "layerOrder": 96, "visible": True,
        "x": 166, "y": 138, "size": 62, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    skill_bolt = {
        "isStage": False, "name": "제우스아이콘",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": bolt_blocks_ui, "comments": bolt_cmt,
        "currentCostume": SKILL_CD_FRAMES,
        "costumes": bolt_cos,
        "sounds": [snd("thunder", thunder_s, thunder_n), snd("skzeus", skzeus_s, skzeus_n)],
        "volume": 100, "layerOrder": 97, "visible": True,
        "x": 214, "y": 138, "size": 62, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    skill_aim = {
        "isStage": False, "name": "스킬조준",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": skaim_blocks, "comments": skaim_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "ring", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": skaim_md5, "md5ext": f"{skaim_md5}.svg",
            "rotationCenterX": 60, "rotationCenterY": 60}],
        "sounds": [snd("skapolo", skapo_s, skapo_n), snd("skares", skares_s, skares_n),
                   snd("skartemis", skart_s, skart_n)],
        "volume": 100, "layerOrder": 94, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    skill_fx = {
        "isStage": False, "name": "스킬이펙트",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": skfx_blocks, "comments": skfx_cmt,
        "currentCostume": 0,
        "costumes": fx_cos,
        "sounds": [],
        "volume": 100, "layerOrder": 80, "visible": False,
        "x": 0, "y": 0, "size": 140, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    up_slot1 = {
        "isStage": False, "name": "강화칸1",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": up1_blocks, "comments": up1_cmt,
        "currentCostume": 0, "costumes": up_slot_cos, "sounds": [],
        "volume": 100, "layerOrder": 201, "visible": False,
        "x": -140, "y": 5, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    up_slot2 = {
        "isStage": False, "name": "강화칸2",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": up2_blocks, "comments": up2_cmt,
        "currentCostume": 0, "costumes": up_slot_cos, "sounds": [],
        "volume": 100, "layerOrder": 202, "visible": False,
        "x": 0, "y": 5, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    up_slot3 = {
        "isStage": False, "name": "강화칸3",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": up3_blocks, "comments": up3_cmt,
        "currentCostume": 0, "costumes": up_slot_cos, "sounds": [],
        "volume": 100, "layerOrder": 203, "visible": False,
        "x": 140, "y": 5, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }


    hpbg = {
        "isStage": False, "name": "성벽바배경",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hpbg_blocks, "comments": hpbg_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "bg", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hpbg_md5, "md5ext": f"{hpbg_md5}.svg",
            "rotationCenterX": 80, "rotationCenterY": 14}],
        "sounds": [],
        "volume": 100, "layerOrder": 70, "visible": True,
        "x": -140, "y": 115, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    hpfill = {
        "isStage": False, "name": "성벽바",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hpfill_blocks, "comments": hpfill_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "fill", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": hpfill_md5, "md5ext": f"{hpfill_md5}.svg",
            "rotationCenterX": 0, "rotationCenterY": 6}],  # 왼쪽 앵커
        "sounds": [],
        "volume": 100, "layerOrder": 71, "visible": True,
        "x": -192, "y": 115, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    wave_panel = {
        "isStage": False, "name": "웨이브패널",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": wavep_blocks, "comments": wavep_cmt,
        "currentCostume": 0,
        "costumes": [{"name": "panel", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": wavep_md5, "md5ext": f"{wavep_md5}.svg",
            "rotationCenterX": 55, "rotationCenterY": 20}],
        "sounds": [],
        "volume": 100, "layerOrder": 72, "visible": True,
        "x": -140, "y": 148, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    hud_digits = [{"name": str(d), "bitmapResolution": 1, "dataFormat": "svg",
                   "assetId": wd_md5[d], "md5ext": f"{wd_md5[d]}.svg",
                   "rotationCenterX": 16, "rotationCenterY": 22} for d in range(10)]
    wave_ones = {
        "isStage": False, "name": "웨이브일",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": wave1_blocks, "comments": wave1_cmt,
        "currentCostume": 1,
        "costumes": hud_digits,
        "sounds": [],
        "volume": 100, "layerOrder": 73, "visible": True,
        "x": -105, "y": 148, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    wave_tens = {
        "isStage": False, "name": "웨이브십",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": wave10_blocks, "comments": wave10_cmt,
        "currentCostume": 0,
        "costumes": [{"name": str(d), "bitmapResolution": 1, "dataFormat": "svg",
                      "assetId": wd_md5[d], "md5ext": f"{wd_md5[d]}.svg",
                      "rotationCenterX": 16, "rotationCenterY": 22} for d in range(10)],
        "sounds": [],
        "volume": 100, "layerOrder": 74, "visible": False,
        "x": -119, "y": 148, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }
    spell_cnt = {
        "isStage": False, "name": "주문잔여",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": spcnt_blocks, "comments": spcnt_cmt,
        "currentCostume": 3,
        "costumes": [{"name": str(d), "bitmapResolution": 1, "dataFormat": "svg",
                      "assetId": wd_md5[d], "md5ext": f"{wd_md5[d]}.svg",
                      "rotationCenterX": 16, "rotationCenterY": 22} for d in range(10)],
        "sounds": [],
        "volume": 100, "layerOrder": 98, "visible": True,
        "x": 214, "y": 165, "size": 42, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # ---- 모니터: 골드만 (웨이브·성벽체력·주문횟수 모니터 숨김 → HUD) ----
    monitors = [
        {"id": V_GOLDCUR, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "골드"}, "spriteName": None,
         "value": 150, "width": 0, "height": 0, "x": 145, "y": 6,
         "visible": True, "sliderMin": 0, "sliderMax": 9999, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, castle, monster, tower, bolt, cursor, palette, popup,
                    gameover, ghost, highlight, flash,
                    skill_fire, skill_spear, skill_artemis, skill_bolt, skill_aim, skill_fx,
                    hpbg, hpfill, wave_panel, wave_ones, wave_tens, spell_cnt,
                    # 강화 UI 맨 마지막 = 항상 최상위 드로우
                    card, up_slot1, up_slot2, up_slot3],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "troy-defense-builder"}
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
                  ("flash", flash_blocks), ("fire", fire_blocks),
                  ("spear", spear_blocks), ("boltui", bolt_blocks_ui),
                  ("hpfill", hpfill_blocks)]:
        print(f"  {nm:9s}: {len(b)} blocks")

if __name__ == "__main__":
    main()
