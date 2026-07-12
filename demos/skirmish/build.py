#!/usr/bin/env python3
"""스커미시 (skirmish) — 소규모 자율 난전 데모.

열린 전장. 화면 아래=아군 본진(y≈-150), 위=적 본진(y≈150), 사이는 자유 필드.
유닛은 자기 본진 부근 랜덤 x 에서 스폰돼 자율적으로 움직인다. 각 진영은 살아있는
유닛의 (x,y,hp,활성)을 길이 7 고정 병렬 리스트(로스터)에 유지. 유닛은 ~0.3초마다
상대 로스터(≤7슬롯)를 스캔해 가장 가까운 적을 조준하고, 사거리 안이면 실탄(총알
클론)을 발사한다. 명중은 collision(touching)으로 O(1) — 유닛이 매 프레임
touching[적총알] 을 검사해 피격, 총알은 touching[적유닛] 이면 삭제.

★ 핵심 설계 = "하드캡으로 n을 묶어 자율 스캔을 감당" (chess-war 재발 방지):
  - chess-war 는 per-unit 자율 전투가 O(n²)로 붕괴했다. 이 데모는 같은 계열이지만
    유닛 총량을 아군≤7·적≤7 하드캡으로 아주 적게 묶어 스캔(index 1..7 상수 반복)을
    감당 가능하게 만든다. 캡 초과 소환/스폰은 거부 — 어떤 경우에도 n>7 금지.
  - 재조준은 매 프레임이 아니라 재조준타이머(throttle, ~0.3초)마다만.
  - 명중은 리스트 스캔이 아니라 collision(touching) — O(1). 총알캡≤30, 화면밖·명중
    즉시 delete this clone. 팝업캡20 자동삭제.

베이스: demos/trench-line/build.py (b_* 헬퍼·synth 사운드·costume-fill 바·클론
스포너·복제됨 가드·소환 게이트·승패 배너). 구역/전선/심판 모델을 자율 난전으로 교체.
"""
import json, os, zipfile, shutil, hashlib, random, math, struct

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "스커미시.sb3")

# ============================================================
#  효과음 합성 (4종) — 결정적
# ============================================================
SND_RATE = 11025
def _wav_bytes(samples, rate=SND_RATE):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def synth_pop(rate=SND_RATE):
    N = int(rate * 0.09); out = []
    for i in range(N):
        t = i / rate
        f = 300 + 400 * min(1.0, t / 0.05)
        env = min(1.0, t / 0.01) * math.exp(-t * 12)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.5)
    return out

def synth_pew(rate=SND_RATE):
    """사격 '탕' — 묵직한 실총성. 노이즈 버스트(짧고 날카로운 어택) + 빠른 감쇠 +
    저주파 바디(펀치). 하이틴 삑소리 제거. 0.055초, 결정적."""
    N = int(rate * 0.055); out = []
    rng = random.Random(778899); lp = 0.0
    for i in range(N):
        t = i / rate
        # 어택은 아주 빠르게 서고 급감쇠
        env = min(1.0, t / 0.002) * math.exp(-t * 55)
        white = rng.random() * 2 - 1
        # 노이즈를 약간 로우패스해 '탕'의 몸통
        lp = lp + 0.5 * (white - lp)
        # 저주파 바디(펀치): 130→70Hz 하강
        body = math.sin(2 * math.pi * (130 + 90 * math.exp(-t * 40)) * t)
        s = (lp * 0.7 + body * 0.55) * env
        out.append(max(-1, min(1, s * 0.9)))
    return out

def synth_tick(rate=SND_RATE):
    N = int(rate * 0.03); out = []
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 70)
        out.append(math.sin(2 * math.pi * 2600 * t) * env * 0.35)
    return out

def synth_crack(rate=SND_RATE):
    N = int(rate * 0.13); out = []
    rng = random.Random(20260712); lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 18)
        white = rng.random() * 2 - 1
        lp = lp + 0.4 * (white - lp)
        thump = math.sin(2 * math.pi * (80 + 50 * math.exp(-t * 24)) * t)
        out.append(max(-1, min(1, (lp * 0.55 + thump * 0.7) * env)))
    return out

def synth_boom(rate=SND_RATE):
    """타워 폭발 '쾅' — 저주파 붐(45→30Hz 하강 sub) + 큰 노이즈 버스트, 느린 감쇠. 0.5초, 결정적."""
    N = int(rate * 0.5); out = []
    rng = random.Random(424242); lp = 0.0
    for i in range(N):
        t = i / rate
        # 두 겹 엔벨로프: 초반 어택 후 긴 꼬리
        env = (min(1.0, t / 0.006)) * (math.exp(-t * 6) * 0.7 + math.exp(-t * 2.2) * 0.3)
        sub = math.sin(2 * math.pi * (45 + 60 * math.exp(-t * 12)) * t)      # 저주파 붐
        white = rng.random() * 2 - 1
        lp = lp + 0.25 * (white - lp)                                        # 로우패스 노이즈(굉음 바디)
        crackle = (rng.random() * 2 - 1) * math.exp(-t * 30) * 0.4           # 초반 파편 크래클
        s = (sub * 0.7 + lp * 0.6 + crackle) * env
        out.append(max(-1, min(1, s)))
    return out

# ============================================================
#  SVG assets
#  좌표: scratchX = svgX-240, scratchY = 180-svgY.
#  아군 본진 y≈-150(svgY 330), 적 본진 y≈150(svgY 30), 사이 자유필드.
# ============================================================
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs><linearGradient id="grd" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#7A2E2E"/><stop offset="0.5" stop-color="#4A4438"/>
    <stop offset="1" stop-color="#2A3E62"/></linearGradient></defs>
  <rect width="480" height="360" fill="url(#grd)"/>
  <!-- 적 진영(위) 붉은 영역 -->
  <rect x="0" y="0" width="480" height="60" fill="#6E2626" opacity="0.5"/>
  <!-- 아군 진영(아래) 파란 영역 -->
  <rect x="0" y="300" width="480" height="60" fill="#26406E" opacity="0.5"/>
  <!-- 중앙 필드 표시(무주공산) -->
  <rect x="0" y="150" width="480" height="60" fill="#000000" opacity="0.08"/>
  <line x1="0" y1="180" x2="480" y2="180" stroke="#FFFFFF" stroke-width="1.5" stroke-dasharray="6 10" opacity="0.18"/>
  <!-- 적 본진(상단) -->
  <rect x="20" y="4" width="440" height="22" fill="#5A1E1E" stroke="#3A1010" stroke-width="2"/>
  <text x="240" y="20" text-anchor="middle" fill="#E7A0A0" font-family="Arial" font-size="13" opacity="0.6">적 본진</text>
  <!-- 아군 본진(하단) -->
  <rect x="20" y="334" width="440" height="22" fill="#1E3A5A" stroke="#0F2038" stroke-width="2"/>
  <text x="240" y="350" text-anchor="middle" fill="#A0C0E7" font-family="Arial" font-size="13" opacity="0.6">아군 본진</text>
  <rect x="3" y="3" width="474" height="354" rx="8" fill="none" stroke="#000000" stroke-width="3" opacity="0.3"/>
</svg>"""

# -------- 유닛 3코스튬 + 발사 코스튬. 아군=파랑 위향 / 적=빨강 아래향 --------
def _unit_svg(fill, stroke, kind, firing=False, up=True):
    body = f'<rect x="15" y="20" width="16" height="18" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    head = f'<circle cx="23" cy="14" r="7" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    gy1, gy2 = (10, 2) if up else (36, 44)
    gun = f'<line x1="31" y1="23" x2="31" y2="{gy1}" stroke="#2A2A2A" stroke-width="2.5"/>'
    if kind == 2:
        body = f'<rect x="12" y="20" width="22" height="18" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        gun = f'<line x1="34" y1="24" x2="34" y2="{gy1}" stroke="#1A1A1A" stroke-width="3.5"/>'
    if kind == 3:
        gun = f'<line x1="31" y1="23" x2="31" y2="{gy2}" stroke="#2A2A2A" stroke-width="2"/><circle cx="31" cy="{(gy1+gy2)//2}" r="1.6" fill="#111"/>'
    muzzle = ""
    if firing:
        my = gy2 if kind == 3 else gy1
        mx = 34 if kind == 2 else 31
        muzzle = f'<circle cx="{mx}" cy="{my}" r="4.5" fill="#FFE082" opacity="0.9"/><circle cx="{mx}" cy="{my}" r="2.2" fill="#FFF59D"/>'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
  <ellipse cx="23" cy="43" rx="11" ry="3" fill="#000" opacity="0.22"/>
  {body}{head}{gun}{muzzle}
</svg>"""

A_RIFLE   = _unit_svg("#3F72C4", "#1C3E7A", 1, up=True)
A_RIFLE_F = _unit_svg("#3F72C4", "#1C3E7A", 1, firing=True, up=True)
A_MG      = _unit_svg("#4B86D8", "#1C5286", 2, up=True)
A_MG_F    = _unit_svg("#4B86D8", "#1C5286", 2, firing=True, up=True)
A_SNIPER  = _unit_svg("#6EC1E8", "#2A7BA0", 3, up=True)
A_SNIPER_F= _unit_svg("#6EC1E8", "#2A7BA0", 3, firing=True, up=True)
E_RIFLE   = _unit_svg("#C44242", "#7A1C1C", 1, up=False)
E_RIFLE_F = _unit_svg("#C44242", "#7A1C1C", 1, firing=True, up=False)
E_MG      = _unit_svg("#D86A4B", "#86341C", 2, up=False)
E_MG_F    = _unit_svg("#D86A4B", "#86341C", 2, firing=True, up=False)
E_SNIPER  = _unit_svg("#E89A6E", "#A05A2A", 3, up=False)
E_SNIPER_F= _unit_svg("#E89A6E", "#A05A2A", 3, firing=True, up=False)

POP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
  <circle cx="23" cy="23" r="16" fill="#FFD54F" opacity="0.55"/>
  <circle cx="23" cy="23" r="9" fill="#FFF176"/>
</svg>"""

# -------- 총알 (진영별 색) — 작고 둥근 실탄 --------
A_BULLET = """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">
  <circle cx="6" cy="6" r="4.5" fill="#FFF59D" stroke="#F9A825" stroke-width="1.5"/>
</svg>"""
E_BULLET = """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">
  <circle cx="6" cy="6" r="4.5" fill="#FFAB91" stroke="#D84315" stroke-width="1.5"/>
</svg>"""

# -------- 데미지 팝업 (숫자 costume — say 금지, 강도별 색 3단) --------
def _dmg_svg(color, txt):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="44" height="30" viewBox="0 0 44 30">
  <text x="22" y="24" text-anchor="middle" font-family="Arial" font-size="26" font-weight="bold"
    fill="{color}" stroke="#000000" stroke-width="1.2" paint-order="stroke">{txt}</text>
</svg>"""
DMG_LOW  = _dmg_svg("#FFEB3B", "3")
DMG_MID  = _dmg_svg("#FF9800", "5")
DMG_HIGH = _dmg_svg("#FF3B3B", "8")

# -------- 소환 버튼 (선택/가능/비활성 = 3코스튬) --------
def _btn_svg(icon, cost, color, mode):
    if mode == "off":
        bg, op, stroke = "#555555", "0.5", "#888888"
    elif mode == "sel":
        bg, op, stroke = color, "1", "#FFF176"
    else:
        bg, op, stroke = color, "1", "#FFFFFF"
    sw = "4" if mode == "sel" else "2"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="92" height="40" viewBox="0 0 92 40">
  <rect x="2" y="2" width="88" height="36" rx="8" fill="{bg}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>
  <text x="24" y="27" text-anchor="middle" font-family="Arial" font-size="20">{icon}</text>
  <text x="66" y="18" text-anchor="middle" font-family="Arial" font-size="14" font-weight="bold" fill="#FFFFFF">{cost}</text>
  <text x="66" y="33" text-anchor="middle" font-family="Arial" font-size="9" fill="#FFFFFF">코스트</text>
</svg>"""
BTN_RIFLE_SEL = _btn_svg("\U0001F52B", "30", "#2E7D32", "sel"); BTN_RIFLE_ON = _btn_svg("\U0001F52B", "30", "#2E7D32", "on"); BTN_RIFLE_OFF = _btn_svg("\U0001F52B", "30", "#2E7D32", "off")
BTN_MG_SEL    = _btn_svg("⚙",     "55", "#1565C0", "sel"); BTN_MG_ON    = _btn_svg("⚙",     "55", "#1565C0", "on"); BTN_MG_OFF    = _btn_svg("⚙",     "55", "#1565C0", "off")
BTN_SNIPE_SEL = _btn_svg("\U0001F3AF", "50", "#EF6C00", "sel"); BTN_SNIPE_ON = _btn_svg("\U0001F3AF", "50", "#EF6C00", "on"); BTN_SNIPE_OFF = _btn_svg("\U0001F3AF", "50", "#EF6C00", "off")

# -------- 액티브 스킬 버튼 (on/off 2코스튬) --------
def _skill_svg(icon, cost, color, on):
    if on:
        bg, opac, stroke = color, "1", "#FFFFFF"
    else:
        bg, opac, stroke = "#555555", "0.5", "#888888"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="72" height="32" viewBox="0 0 72 32">
  <rect x="2" y="2" width="68" height="28" rx="7" fill="{bg}" stroke="{stroke}" stroke-width="2" opacity="{opac}"/>
  <text x="18" y="23" text-anchor="middle" font-family="Arial" font-size="17">{icon}</text>
  <text x="50" y="14" text-anchor="middle" font-family="Arial" font-size="11" font-weight="bold" fill="#FFFFFF">{cost}</text>
  <text x="50" y="26" text-anchor="middle" font-family="Arial" font-size="7" fill="#FFFFFF">코스트</text>
</svg>"""
SK_AIR_ON = _skill_svg("\U0001F4A5", "110", "#B71C1C", True); SK_AIR_OFF = _skill_svg("\U0001F4A5", "110", "#B71C1C", False)
SK_SUP_ON = _skill_svg("✚", "70", "#2E7D32", True); SK_SUP_OFF = _skill_svg("✚", "70", "#2E7D32", False)
SK_CHG_ON = _skill_svg("⚔", "80", "#F9A825", True); SK_CHG_OFF = _skill_svg("⚔", "80", "#F9A825", False)

# -------- 에어스트라이크 폭발 이펙트 (확장 파이어볼) — 폭발 코스튬 재사용 형태 --------
def _blast_svg(r_out, r_core, opac):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
  <circle cx="80" cy="80" r="{r_out}" fill="#FF7043" opacity="{opac}"/>
  <circle cx="80" cy="80" r="{r_core}" fill="#FFE082" opacity="{min(1.0,opac+0.3)}"/>
</svg>"""
BLAST1 = _blast_svg(30, 16, 0.8); BLAST2 = _blast_svg(55, 30, 0.6); BLAST3 = _blast_svg(74, 40, 0.3)

# -------- HP바 / 지갑바 costume-fill 11단 --------
def _bar_svg(step, fill, label):
    w = int(round(120 * step / 10))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="170" height="20" viewBox="0 0 170 20">
  <text x="2" y="15" font-family="Arial" font-size="12">{label}</text>
  <rect x="30" y="3" width="124" height="14" rx="4" fill="#000000" opacity="0.4"/>
  <rect x="32" y="5" width="{w}" height="10" rx="3" fill="{fill}"/>
  <rect x="30" y="3" width="124" height="14" rx="4" fill="none" stroke="#FFFFFF" stroke-width="1.5" opacity="0.8"/>
</svg>"""
AHP_BARS  = [_bar_svg(s, "#42A5F5", "\U0001F3F0") for s in range(11)]
EHP_BARS  = [_bar_svg(s, "#EF5350", "\U0001F3F0") for s in range(11)]
GOLD_BARS = [_bar_svg(s, "#FFCA28", "\U0001F4B0") for s in range(11)]

# -------- 본부(HQ) = 각 진영 단일 타워 스프라이트 (공격 대상) --------
# 명확한 타워 실루엣: 넓은 기단 + 몸통 + 성가퀴(crenellation) + 깃발. 아군=파랑 / 적=빨강.
def _hq_svg(fill, stroke, flag, up=True):
    # up=True 아군(깃발 위) / up=False 적(깃발 아래, 상단에서 매달림). 74×64 뷰박스.
    flag_y = 4 if up else 60
    pole_y1, pole_y2 = (4, 26) if up else (60, 38)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="74" height="64" viewBox="0 0 74 64">
  <ellipse cx="37" cy="60" rx="30" ry="4" fill="#000000" opacity="0.22"/>
  <!-- 기단 -->
  <rect x="10" y="46" width="54" height="14" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
  <!-- 몸통 -->
  <rect x="18" y="18" width="38" height="30" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
  <rect x="18" y="18" width="38" height="8" fill="#FFFFFF" opacity="0.14"/>
  <!-- 성가퀴 -->
  <rect x="16" y="12" width="8" height="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
  <rect x="33" y="12" width="8" height="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
  <rect x="50" y="12" width="8" height="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
  <!-- 창문 -->
  <rect x="32" y="28" width="10" height="14" rx="4" fill="#1A1A1A" opacity="0.55"/>
  <!-- 깃대 + 깃발 -->
  <line x1="37" y1="{pole_y1}" x2="37" y2="{pole_y2}" stroke="{stroke}" stroke-width="2"/>
  <path d="M37 {flag_y} L54 {flag_y+5} L37 {flag_y+10} Z" fill="{flag}"/>
</svg>"""
A_HQ = _hq_svg("#2E5C97", "#9CC2F0", "#4FC3F7", up=True)
E_HQ = _hq_svg("#97302E", "#F0A6A6", "#FF7043", up=False)

# -------- 타워 폭발 코스튬 (확장 파이어볼 3프레임) — 격파 연출 --------
def _boom_svg(r_out, r_mid, r_core, op_out):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <circle cx="60" cy="60" r="{r_out}" fill="#FF7043" opacity="{op_out}"/>
  <circle cx="60" cy="60" r="{r_mid}" fill="#FFB74D" opacity="{min(1.0, op_out+0.2)}"/>
  <circle cx="60" cy="60" r="{r_core}" fill="#FFF59D"/>
  <g fill="#5A3210">
    <circle cx="{60-r_mid*0.6:.0f}" cy="{60-r_mid*0.4:.0f}" r="4"/>
    <circle cx="{60+r_mid*0.55:.0f}" cy="{60-r_mid*0.5:.0f}" r="3.5"/>
    <circle cx="{60+r_mid*0.4:.0f}" cy="{60+r_mid*0.55:.0f}" r="4.5"/>
    <circle cx="{60-r_mid*0.5:.0f}" cy="{60+r_mid*0.45:.0f}" r="3"/>
  </g>
</svg>"""
BOOM1 = _boom_svg(22, 15, 8, 0.85)
BOOM2 = _boom_svg(40, 28, 14, 0.7)
BOOM3 = _boom_svg(56, 40, 18, 0.4)

# -------- 승/패 배너 --------
WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="140" viewBox="0 0 360 140">
  <rect x="5" y="5" width="350" height="130" rx="14" fill="#0D3B0D" opacity="0.9" stroke="#66BB6A" stroke-width="5"/>
  <text x="180" y="70" text-anchor="middle" fill="#A5D6A7" font-family="Arial" font-size="44" font-weight="bold">승리!</text>
  <text x="180" y="108" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="16">적 본진 함락 — 깃발로 재도전</text>
</svg>"""
LOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="140" viewBox="0 0 360 140">
  <rect x="5" y="5" width="350" height="130" rx="14" fill="#3B0D0D" opacity="0.9" stroke="#EF5350" stroke-width="5"/>
  <text x="180" y="70" text-anchor="middle" fill="#EF9A9A" font-family="Arial" font-size="44" font-weight="bold">패배...</text>
  <text x="180" y="108" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="16">아군 본진 함락 — 깃발로 재도전</text>
</svg>"""

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
def b_mathop(bs, opname, val):
    bid = gen(); ins = {"NUM": slot(val) if (isinstance(val,str) and val in bs) else num(val)}
    bs[bid] = mk("operator_mathop", inputs=ins, fields={"OPERATOR": [opname, None]})
    if isinstance(val,str) and val in bs: bs[val]["parent"] = bid
    return bid
def b_abs(bs, val):
    return b_mathop(bs, "abs", val)
def b_sqrt(bs, val):
    return b_mathop(bs, "sqrt", val)

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

# ---- 리스트 헬퍼 ----
def b_listitem(bs, lname, lid, index):
    bid = gen()
    ins = {"INDEX": slot(index) if (isinstance(index,str) and index in bs) else num(index)}
    bs[bid] = mk("data_itemoflist", inputs=ins, fields={"LIST": [lname, lid]})
    if isinstance(index,str) and index in bs: bs[index]["parent"] = bid
    return bid
def b_listreplace(bs, lname, lid, index, value):
    bid = gen(); ins = {}
    ins["INDEX"] = slot(index) if (isinstance(index,str) and index in bs) else num(index)
    ins["ITEM"]  = slot(value) if (isinstance(value,str) and value in bs) else (text_lit(value) if isinstance(value,str) else num(value))
    bs[bid] = mk("data_replaceitemoflist", inputs=ins, fields={"LIST": [lname, lid]})
    if isinstance(index,str) and index in bs: bs[index]["parent"] = bid
    if isinstance(value,str) and value in bs: bs[value]["parent"] = bid
    return bid
def b_listadd(bs, lname, lid, value):
    bid = gen()
    it = slot(value) if (isinstance(value,str) and value in bs) else (num(value) if not isinstance(value,str) else text_lit(value))
    bs[bid] = mk("data_addtolist", inputs={"ITEM": it}, fields={"LIST": [lname, lid]})
    if isinstance(value,str) and value in bs: bs[value]["parent"] = bid
    return bid
def b_listdelall(bs, lname, lid):
    bid = gen(); bs[bid] = mk("data_deletealloflist", fields={"LIST": [lname, lid]}); return bid

def b_mousedown(bs):
    bid = gen(); bs[bid] = mk("sensing_mousedown"); return bid
def b_touchingmouse(bs):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu", fields={"TOUCHINGOBJECTMENU": ["_mouse_", None]}, shadow=True)
    t = gen(); bs[t] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, m]}); bs[m]["parent"] = t; return t
def b_touchingsprite(bs, spname):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu", fields={"TOUCHINGOBJECTMENU": [spname, None]}, shadow=True)
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
    bid = gen(); bs[bid] = mk("control_stop", fields={"STOP_OPTION": ["this script", None]})
    bs[bid]["mutation"] = {"tagName": "mutation", "children": [], "hasnext": "false"}
    return bid

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
def b_sety(bs, v):
    bid = gen(); ins = {"Y": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_sety", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_setx(bs, v):
    bid = gen(); ins = {"X": slot(v) if (isinstance(v,str) and v in bs) else num(v)}
    bs[bid] = mk("motion_setx", inputs=ins)
    if isinstance(v,str) and v in bs: bs[v]["parent"] = bid
    return bid
def b_ypos(bs):
    bid = gen(); bs[bid] = mk("motion_yposition"); return bid
def b_xpos(bs):
    bid = gen(); bs[bid] = mk("motion_xposition"); return bid
def b_pointdir(bs, d):
    bid = gen(); bs[bid] = mk("motion_pointindirection", inputs={"DIRECTION": num(d)}); return bid

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
def b_createclone(bs, spname="_myself_"):
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu", fields={"CLONE_OPTION": [spname, None]}, shadow=True)
    cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cmenu]}); bs[cmenu]["parent"] = cc; return cc
def b_delclone(bs):
    bid = gen(); bs[bid] = mk("control_delete_this_clone"); return bid

# ============================================================
#  IDs
# ============================================================
# ---- 로스터 리스트 (길이 7 고정, 병렬) ----
L_AX="listAx01"; L_AY="listAy02"; L_AHPL="listAhp03"; L_AACT="listAact04"    # 아군 로스터(적이 스캔)
L_EX="listEx05"; L_EY="listEy06"; L_EHPL="listEhp07"; L_EACT="listEact08"    # 적 로스터(아군이 스캔)
# ★ 피해 누적기(슬롯별): 총알이 거리판정으로 명중 시 대상 슬롯에 데미지 누적 → 유닛이 매 프레임
#   자기 슬롯 누적값을 읽어 HP 차감 후 0으로 리셋. 명중을 시각 touching 과 완전 분리(거리 기반).
L_ADMG="listAdmg09"; L_EDMG="listEdmg10"

# ---- 스칼라 전역 ----
V_GOLD="varGold01"; V_GOLDMAX="varGoldMax02"; V_GOLDRATE="varGoldRate03"
V_UNITCAP="varUnitCap04"; V_BULLETCAP="varBulletCap05"
V_POPCAP="varPopCap06"; V_POPCNT="varPopCnt07"
V_AHP="varAHP08"; V_EHP="varEHP09"; V_BASEDMG="varBaseDmg10"
V_ESPAWNGAP="varESpawnGap11"; V_ESPAWNT="varESpawnT12"
V_ALLYY="varAllyY13"; V_ENEMYY="varEnemyY14"
V_ACNT="varACnt15"; V_ECNT="varECnt16"; V_ABCNT="varABCnt17"; V_EBCNT="varEBCnt18"
V_STATE="varState19"
# 종류별 스탯
V_C_RIFLE="varCRifle20"; V_C_MG="varCMg21"; V_C_SNIPE="varCSnipe22"
V_CD_RIFLE="varCdRifle23"; V_CD_MG="varCdMg24"; V_CD_SNIPE="varCdSnipe25"
V_CDT_RIFLE="varCdtRifle26"; V_CDT_MG="varCdtMg27"; V_CDT_SNIPE="varCdtSnipe28"
# 소환 채널
V_PENDTYPE="varPendType29"; V_SPTYPE="varSpType30"; V_ESPTYPE="varESpType31"
# 팝업 요청 채널
V_POPX="varPopX32"; V_POPY="varPopY33"; V_POPVAL="varPopVal34"
# 발사 채널 (진영별): 발사 원점 + 방향 단위벡터 + 종류
V_ABX="varABx35"; V_ABY="varABy36"; V_ABDX="varABdx37"; V_ABDY="varABdy38"; V_ABTYPE="varABtype39"
V_EBX="varEBx40"; V_EBY="varEBy41"; V_EBDX="varEBdx42"; V_EBDY="varEBdy43"; V_EBTYPE="varEBtype44"

# ---- 클론-로컬(유닛) ----
V_ISC="varIsClone"; V_TYPE="varMyType"; V_HP="varMyHP"; V_MAXHP="varMyMaxHP"
V_RNG="varMyRange"; V_SPD="varMySpd"; V_SLOT="varMySlot"
V_REAIMT="varReaimT"; V_FIRET="varFireT"; V_TGTX="varTgtX"; V_TGTY="varTgtY"; V_HASTGT="varHasTgt"
V_SCANI="varScanI"; V_BESTD="varBestD"
# ---- 클론-로컬(총알) ----
V_B_ISC="varBIsClone"; V_BDX="varBdx"; V_BDY="varBdy"; V_BLIFE="varBLife"
V_B_SI="varBScanI"; V_B_BEST="varBBest"; V_B_HIT="varBHit"  # 총알 히트스캔(슬롯 순회)
# ---- HQ-로컬(타워 포탑 스캔) ----
V_HQ_SCANI="varHqScanI"; V_HQ_BEST="varHqBest"; V_HQ_TX="varHqTx"; V_HQ_TY="varHqTy"
V_HQ_HAS="varHqHas"; V_HQ_FIRET="varHqFireT"

# ---- 액티브 스킬 (코스트·쿨타이머·쿨값) ----
V_SK_AIR_C="varSkAirC"; V_SK_AIR_T="varSkAirT"; V_SK_AIR_CD="varSkAirCd"
V_SK_SUP_C="varSkSupC"; V_SK_SUP_T="varSkSupT"; V_SK_SUP_CD="varSkSupCd"
V_SK_CHG_C="varSkChgC"; V_SK_CHG_T="varSkChgT"; V_SK_CHG_CD="varSkChgCd"
# 광역타격 채널 + 돌격 버프 타이머
V_STRIKEX="varStrikeX"; V_STRIKEY="varStrikeY"; V_STRIKER="varStrikeR"; V_STRIKED="varStrikeDmg"
V_CHGBUFF="varChgBuff"   # 돌격 버프 남은 타이머(>0=버프중)
# 스킬-로컬(에어스트라이크 폭발 스캔·클론)
V_SK_ISC="varSkIsClone"; V_SK_I="varSkI"; V_SK_SX="varSkSumX"; V_SK_SY="varSkSumY"; V_SK_N="varSkN"

# ---- 방송 ----
BR_START="brStart01"; BR_ASPAWN="brASpawn02"; BR_ESPAWN="brESpawn03"
BR_AFIRE="brAFire04"; BR_EFIRE="brEFire05"; BR_POP="brPop06"; BR_END="brEnd07"
BR_AIR="brAir08"; BR_SUP="brSup09"; BR_CHG="brChg10"; BR_STRIKE="brStrike11"

ALLY_Y = -150; ENEMY_Y = 150

# ============================================================
#  STAGE — 초기화 + 돈충전 + 쿨감소 + 적AI 스폰 + 승패
# ============================================================
def build_stage_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # ===== (A) 깃발 → 전역 초기화 → 게임시작 =====
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [h]
    def s(name, vid, val): seq.append(b_setvar(bs, name, vid, val))
    s("돈", V_GOLD, 40); s("돈상한", V_GOLDMAX, 200); s("돈충전율", V_GOLDRATE, 9)
    s("유닛캡", V_UNITCAP, 7); s("총알캡", V_BULLETCAP, 150)
    s("팝업캡", V_POPCAP, 20); s("팝업수", V_POPCNT, 0)
    s("아군본진HP", V_AHP, 100); s("적본진HP", V_EHP, 100); s("본진딜", V_BASEDMG, 5)
    s("적스폰간격", V_ESPAWNGAP, 2.2); s("적스폰타이머", V_ESPAWNT, 1.5)
    s("아군진y", V_ALLYY, ALLY_Y); s("적진y", V_ENEMYY, ENEMY_Y)
    s("아군수", V_ACNT, 0); s("적수", V_ECNT, 0); s("아군총알수", V_ABCNT, 0); s("적총알수", V_EBCNT, 0)
    s("게임상태", V_STATE, 1)
    s("소총_코스트", V_C_RIFLE, 30); s("제압_코스트", V_C_MG, 55); s("저격_코스트", V_C_SNIPE, 50)
    s("소총_소환쿨", V_CD_RIFLE, 25); s("제압_소환쿨", V_CD_MG, 70); s("저격_소환쿨", V_CD_SNIPE, 80)
    s("소총_쿨타이머", V_CDT_RIFLE, 0); s("제압_쿨타이머", V_CDT_MG, 0); s("저격_쿨타이머", V_CDT_SNIPE, 0)
    s("대기소환종류", V_PENDTYPE, 0); s("소환종류", V_SPTYPE, 0); s("적소환종류", V_ESPTYPE, 0)
    # 액티브 스킬 코스트/쿨(틱=0.02s 루프기준: 8s=400, 6s=300, 10s=500)
    s("포격_코스트", V_SK_AIR_C, 110); s("포격_쿨타이머", V_SK_AIR_T, 0); s("포격_쿨", V_SK_AIR_CD, 400)
    s("보급_코스트", V_SK_SUP_C, 70); s("보급_쿨타이머", V_SK_SUP_T, 0); s("보급_쿨", V_SK_SUP_CD, 300)
    s("돌격_코스트", V_SK_CHG_C, 80); s("돌격_쿨타이머", V_SK_CHG_T, 0); s("돌격_쿨", V_SK_CHG_CD, 500)
    s("타격x", V_STRIKEX, 0); s("타격y", V_STRIKEY, 0); s("타격반경", V_STRIKER, 70); s("타격딜", V_STRIKED, 14)
    s("돌격버프", V_CHGBUFF, 0)
    s("팝업x", V_POPX, 0); s("팝업y", V_POPY, 0); s("팝업값", V_POPVAL, 1)
    s("탄Ax", V_ABX, 0); s("탄Ay", V_ABY, 0); s("탄Adx", V_ABDX, 0); s("탄Ady", V_ABDY, 1); s("탄A종류", V_ABTYPE, 1)
    s("탄Ex", V_EBX, 0); s("탄Ey", V_EBY, 0); s("탄Edx", V_EBDX, 0); s("탄Edy", V_EBDY, -1); s("탄E종류", V_EBTYPE, 1)
    # 로스터 리스트 7칸 초기화(활성=0)
    def initlist(lname, lid, val):
        seq.append(b_listdelall(bs, lname, lid))
        for _ in range(7):
            seq.append(b_listadd(bs, lname, lid, val))
    initlist("L_아군x", L_AX, 0); initlist("L_아군y", L_AY, ALLY_Y); initlist("L_아군hp", L_AHPL, 0); initlist("L_아군활성", L_AACT, 0)
    initlist("L_적x", L_EX, 0); initlist("L_적y", L_EY, ENEMY_Y); initlist("L_적hp", L_EHPL, 0); initlist("L_적활성", L_EACT, 0)
    seq.append(b_wait(bs, 0.2))
    seq.append(b_broadcast(bs, "게임시작", BR_START))
    C(bs, seq)
    add_comment(bs, comments, seq[1],
        "\U0001F6E0️ 개조 손잡이: 돈·캡·본진HP·유닛 스탯 전부 여기 숫자만 바꾸면 게임이 달라져요.\n"
        "유닛캡7·총알캡30·팝업캡20 = chess-war O(n²) 붕괴를 막는 성능 상한(수치로 못박음).\n"
        "로스터 8종(L_아군x/y/hp/활성, L_적x/y/hp/활성)은 길이 7 고정 병렬 슬롯.\n"
        "유닛이 스폰 시 활성==0 슬롯에 등록, 매 프레임 x/y/hp 기록, 사망 시 활성=0.",
        x=470, y=20, w=400, h=170)

    # ===== (B) 돈 자동 충전 forever =====
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=340,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    add_g = b_changevar(bs, "돈", V_GOLD, op("operator_multiply", vrep("돈충전율", V_GOLDRATE), 0.1))
    c_over = cmp_op("operator_gt", vrep("돈", V_GOLD), vrep("돈상한", V_GOLDMAX))
    set_cap = b_setvar(bs, "돈", V_GOLD, vrep("돈상한", V_GOLDMAX))
    if_over = b_if(bs, c_over, set_cap)
    C(bs, [add_g, if_over])
    c_playg = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_playg = b_if(bs, c_playg, add_g)
    w_g = b_wait(bs, 0.1)
    C(bs, [if_playg, w_g])
    fe_g = b_forever(bs, if_playg)
    C(bs, [hb, fe_g])
    add_comment(bs, comments, add_g,
        "\U0001F4B0 돈은 시간이 지나면 자동으로 차올라요(돈충전율/초). 상한에서 멈춤.\n"
        "언제 뭘 뽑을지 = 이 데모의 유일한 전략!",
        x=470, y=340, w=350, h=100)

    # ===== (C) 소환 쿨타이머 감소 forever =====
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=470, y=340,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    def dec_cd(name, vid):
        c_pos = cmp_op("operator_gt", vrep(name, vid), 0)
        dec = b_changevar(bs, name, vid, -1)
        return b_if(bs, c_pos, dec)
    d1 = dec_cd("소총_쿨타이머", V_CDT_RIFLE); d2 = dec_cd("제압_쿨타이머", V_CDT_MG); d3 = dec_cd("저격_쿨타이머", V_CDT_SNIPE)
    d4 = dec_cd("포격_쿨타이머", V_SK_AIR_T); d5 = dec_cd("보급_쿨타이머", V_SK_SUP_T); d6 = dec_cd("돌격_쿨타이머", V_SK_CHG_T)
    d7 = dec_cd("돌격버프", V_CHGBUFF)  # 돌격 버프 남은시간 감소
    w_c = b_wait(bs, 0.02)
    C(bs, [d1, d2, d3, d4, d5, d6, d7, w_c])
    fe_c = b_forever(bs, d1)
    C(bs, [hc, fe_c])

    # ===== (D) 적 AI 스폰 타이머 forever =====
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=20, y=640,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    dec_t = b_changevar(bs, "적스폰타이머", V_ESPAWNT, -0.1)
    rnd_t = op("operator_random", 1, 3, key1="FROM", key2="TO")
    set_et = b_setvar(bs, "적소환종류", V_ESPTYPE, rnd_t)
    # 조건: 타이머<=0 and 적수<유닛캡
    c_t0 = b_not(bs, cmp_op("operator_gt", vrep("적스폰타이머", V_ESPAWNT), 0))
    c_room = cmp_op("operator_lt", vrep("적수", V_ECNT), vrep("유닛캡", V_UNITCAP))
    c_sp = bool_op("operator_and", c_t0, c_room)
    bc_e = b_broadcast_wait(bs, "적소환", BR_ESPAWN)
    reset_t = b_setvar(bs, "적스폰타이머", V_ESPAWNT, vrep("적스폰간격", V_ESPAWNGAP))
    C(bs, [set_et, bc_e, reset_t])
    if_sp = b_if(bs, c_sp, set_et)
    C(bs, [dec_t, if_sp])
    c_playe = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_playe = b_if(bs, c_playe, dec_t)
    w_e = b_wait(bs, 0.1)
    C(bs, [if_playe, w_e])
    fe_e = b_forever(bs, if_playe)
    C(bs, [hd, fe_e])
    add_comment(bs, comments, if_sp,
        "\U0001F916 적 AI: 적스폰간격마다 랜덤 종류 유닛 1기 자동 소환.\n"
        "적수<유닛캡7 일 때만 → 총량 하드캡 준수(O(n²) 폭주 방지).",
        x=470, y=640, w=350, h=100)

    # ===== (E) 승패 감시 forever =====
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=470, y=640,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    c_win = b_not(bs, cmp_op("operator_gt", vrep("적본진HP", V_EHP), 0))
    c_lose = b_not(bs, cmp_op("operator_gt", vrep("아군본진HP", V_AHP), 0))
    c_over = bool_op("operator_or", c_win, c_lose)
    set_s0 = b_setvar(bs, "게임상태", V_STATE, 0)
    bc_end = b_broadcast(bs, "게임끝", BR_END)
    C(bs, [set_s0, bc_end])
    c_playo = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_endnow = bool_op("operator_and", c_playo, c_over)
    if_over = b_if(bs, c_endnow, set_s0)
    w_o = b_wait(bs, 0.05)
    C(bs, [if_over, w_o])
    fe_o = b_forever(bs, if_over)
    C(bs, [hf, fe_o])

    return bs, comments

# ============================================================
#  아군/적 유닛 (스포너 + 클론 본체) — 진영 미러
#  ★ 캡7 하에 상대 로스터(index 1..7 상수 스캔, throttle)로 조준.
#    명중은 collision(touching 상대총알) O(1). 발사는 총알 클론.
# ============================================================
def build_unit_blocks(side):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    A = (side == "A")
    SPAWN   = (BR_ASPAWN, "아군소환") if A else (BR_ESPAWN, "적소환")
    SPTYPE  = (V_SPTYPE, "소환종류") if A else (V_ESPTYPE, "적소환종류")
    # 자기 진영 로스터(내가 등록/기록/해제) — 아군유닛은 L_아군*, 적유닛은 L_적*
    L_MX  = (L_AX, "L_아군x") if A else (L_EX, "L_적x")
    L_MY  = (L_AY, "L_아군y") if A else (L_EY, "L_적y")
    L_MHP = (L_AHPL, "L_아군hp") if A else (L_EHPL, "L_적hp")
    L_MACT= (L_AACT, "L_아군활성") if A else (L_EACT, "L_적활성")
    # 상대 진영 로스터(내가 스캔) — 아군유닛은 L_적*, 적유닛은 L_아군*
    L_OX  = (L_EX, "L_적x") if A else (L_AX, "L_아군x")
    L_OY  = (L_EY, "L_적y") if A else (L_AY, "L_아군y")
    L_OACT= (L_EACT, "L_적활성") if A else (L_AACT, "L_아군활성")
    CNT   = (V_ACNT, "아군수") if A else (V_ECNT, "적수")
    # 발사 채널
    BFX = (V_ABX, "탄Ax") if A else (V_EBX, "탄Ex")
    BFY = (V_ABY, "탄Ay") if A else (V_EBY, "탄Ey")
    BFDX= (V_ABDX, "탄Adx") if A else (V_EBDX, "탄Edx")
    BFDY= (V_ABDY, "탄Ady") if A else (V_EBDY, "탄Edy")
    BFT = (V_ABTYPE, "탄A종류") if A else (V_EBTYPE, "탄E종류")
    FIRE_BR = (BR_AFIRE, "아군발사") if A else (BR_EFIRE, "적발사")
    ENEMY_BULLET = "적총알" if A else "아군총알"
    HOME_Y  = (V_ALLYY, "아군진y") if A else (V_ENEMYY, "적진y")   # 스폰/무적 본진
    BASE_TGT_Y = ENEMY_Y if A else ALLY_Y                          # 적이 없을 때 향할 적 본진 y
    CS = "아" if A else "적"

    # ── (A) 깃발: 숨김·복제됨 가드 ──
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs, "don't rotate"); orig0 = b_setvar(bs, "복제됨", V_ISC, 0)
    C(bs, [h, hi, rs, orig0])

    # ── (B) 소환 방송 → 클론 (원본만) ──
    #   ★ 카운트(아군수/적수)는 여기서 broadcast_and_wait 동기 시점에 즉시 +1 →
    #   다음 클릭/스폰이 캡 게이트를 통과하기 전에 카운트가 반영되어 캡7 을 확실히 지킴.
    #   단, 캡 초과면(아군수>=유닛캡) 클론 생성·카운트 모두 스킵(2중 안전).
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": [SPAWN[1], SPAWN[0]]})
    inc_cnt = b_changevar(bs, CNT[1], CNT[0], 1)
    cc = b_createclone(bs)
    C(bs, [inc_cnt, cc])
    c_room_spawn = cmp_op("operator_lt", vrep(CNT[1], CNT[0]), vrep("유닛캡", V_UNITCAP))
    c_origfree = bool_op("operator_and", cmp_op("operator_equals", vrep("복제됨", V_ISC), 0), c_room_spawn)
    if_c = b_if(bs, c_origfree, inc_cnt)
    C(bs, [hb, if_c])

    # ── (B2) 스킬 반응(클론별, 1회 처리) ──
    if A:
        # 보급: 아군 유닛만 HP 를 최대로 회복 + 반짝 이펙트.
        hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=280, y=200,
            fields={"BROADCAST_OPTION": ["보급", BR_SUP]})
        c_clone_s = cmp_op("operator_equals", vrep("복제됨", V_ISC), 1)
        heal = b_setvar(bs, "내HP", V_HP, vrep("내최대HP", V_MAXHP))
        fx1 = b_seteffect(bs, "BRIGHTNESS", 60); ws = b_wait(bs, 0.08); fx2 = b_seteffect(bs, "BRIGHTNESS", 0)
        C(bs, [heal, fx1, ws, fx2])
        if_heal = b_if(bs, c_clone_s, heal)
        C(bs, [hs, if_heal])
    else:
        # 광역타격(포격): 적 유닛만 — 착탄점(타격x/y) 반경 안이면 HP 감소.
        hk = gen(); bs[hk] = mk("event_whenbroadcastreceived", top=True, x=280, y=200,
            fields={"BROADCAST_OPTION": ["광역타격", BR_STRIKE]})
        c_clone_k = cmp_op("operator_equals", vrep("복제됨", V_ISC), 1)
        # 거리^2 <= 반경^2 이면 피해
        kdx = op("operator_subtract", b_xpos(bs), vrep("타격x", V_STRIKEX))
        kdy = op("operator_subtract", b_ypos(bs), vrep("타격y", V_STRIKEY))
        kd2 = op("operator_add", op("operator_multiply", kdx, kdx), op("operator_multiply", kdy, kdy))
        r2 = op("operator_multiply", vrep("타격반경", V_STRIKER), vrep("타격반경", V_STRIKER))
        c_inblast = b_not(bs, cmp_op("operator_gt", kd2, r2))
        take_blast = b_changevar(bs, "내HP", V_HP, op("operator_multiply", vrep("타격딜", V_STRIKED), -1))
        fxk = b_changeeffect(bs, "GHOST", 30); wk = b_wait(bs, 0.03); fxk2 = b_seteffect(bs, "GHOST", 0)
        C(bs, [take_blast, fxk, wk, fxk2])
        if_blast = b_if(bs, c_inblast, take_blast)
        if_blast_clone = b_if(bs, c_clone_k, if_blast)
        C(bs, [hk, if_blast_clone])

    # ── (C) 클론 본체 ──
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_ISC, 1)
    set_type = b_setvar(bs, "내종류", V_TYPE, vrep(SPTYPE[1], SPTYPE[0]))
    # 종류별 스탯
    def stat_branch(hp, rng, spd, costume, size):
        s_hp = b_setvar(bs, "내HP", V_HP, hp); s_mh = b_setvar(bs, "내최대HP", V_MAXHP, hp)
        s_rn = b_setvar(bs, "내사거리", V_RNG, rng); s_sp = b_setvar(bs, "내속도", V_SPD, spd)
        swc = b_costume(bs, costume); szb = b_setsize(bs, size)
        C(bs, [s_hp, s_mh, s_rn, s_sp, swc, szb])
        return s_hp
    # 1=소총병(HP20,사거리130,속도3.5) 2=제압사수(HP26,사거리100,속도2.6) 3=저격수(HP8,사거리200,속도3.2)
    b1 = stat_branch(20, 130, 3.5, f"{CS}소총", 85)
    b2 = stat_branch(26, 100, 2.6, f"{CS}제압", 92)
    b3 = stat_branch(8, 200, 3.2, f"{CS}저격", 78)
    if_t2 = b_ifelse(bs, cmp_op("operator_equals", vrep("내종류", V_TYPE), 2), b2, b3)
    if_t1 = b_ifelse(bs, cmp_op("operator_equals", vrep("내종류", V_TYPE), 1), b1, if_t2)
    # 슬롯 등록: 활성==0 인 첫 슬롯 찾기(index 1..7 상수 스캔).
    set_slot0 = b_setvar(bs, "내슬롯", V_SLOT, 0)
    set_i0 = b_setvar(bs, "스캔i", V_SCANI, 1)
    # repeat 7: if 슬롯==0 and 활성[i]==0 → 내슬롯=i, 활성[i]=1 ; i+=1
    act_i = b_listitem(bs, L_MACT[1], L_MACT[0], vrep("스캔i", V_SCANI))
    c_free = bool_op("operator_and",
                     b_not(bs, cmp_op("operator_gt", vrep("내슬롯", V_SLOT), 0)),
                     b_not(bs, cmp_op("operator_gt", act_i, 0)))
    claim_slot = b_setvar(bs, "내슬롯", V_SLOT, vrep("스캔i", V_SCANI))
    claim_act  = b_listreplace(bs, L_MACT[1], L_MACT[0], vrep("스캔i", V_SCANI), 1)
    C(bs, [claim_slot, claim_act])
    if_free = b_if(bs, c_free, claim_slot)
    inc_i = b_changevar(bs, "스캔i", V_SCANI, 1)
    C(bs, [if_free, inc_i])
    rep_claim = b_repeat(bs, 7, if_free)
    # 초기 위치: 본진 부근 랜덤 x, y = 본진 y
    startx = op("operator_random", -210, 210, key1="FROM", key2="TO")
    g0 = b_gotoxy(bs, startx, vrep(HOME_Y[1], HOME_Y[0]))
    set_reaim0 = b_setvar(bs, "재조준타이머", V_REAIMT, 0)
    set_fire0 = b_setvar(bs, "발사쿨", V_FIRET, 0)
    set_hastgt0 = b_setvar(bs, "목표있음", V_HASTGT, 0)
    fr = b_front(bs); show = b_show(bs)

    # ---- forever 본체 ----
    # 0) 게임 종료 정리
    c_gameend = b_not(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    rel_act_e = b_listreplace(bs, L_MACT[1], L_MACT[0], vrep("내슬롯", V_SLOT), 0)
    dec_cnt_e = b_changevar(bs, CNT[1], CNT[0], -1)
    del_end = b_delclone(bs)
    C(bs, [rel_act_e, dec_cnt_e, del_end])
    if_end = b_if(bs, c_gameend, rel_act_e)

    # 1) 슬롯 기록: 매 프레임 내 x/y/hp 를 슬롯에 기록(로스터 최신화)
    rec_x = b_listreplace(bs, L_MX[1], L_MX[0], vrep("내슬롯", V_SLOT), b_xpos(bs))
    rec_y = b_listreplace(bs, L_MY[1], L_MY[0], vrep("내슬롯", V_SLOT), b_ypos(bs))
    rec_hp = b_listreplace(bs, L_MHP[1], L_MHP[0], vrep("내슬롯", V_SLOT), vrep("내HP", V_HP))

    # 2) ★ throttle 재조준: 재조준타이머<=0 이면 상대 로스터(7슬롯) 스캔해 가장 가까운 활성 적 선택.
    #    매 프레임 아님 — 재조준타이머 로 ~0.3초마다만 스캔(캡7 하에 index 1..7 상수 반복).
    c_reaim = b_not(bs, cmp_op("operator_gt", vrep("재조준타이머", V_REAIMT), 0))
    # 스캔 초기화
    set_best = b_setvar(bs, "최근거리", V_BESTD, 999999)
    set_notgt = b_setvar(bs, "목표있음", V_HASTGT, 0)
    set_scan1 = b_setvar(bs, "스캔i", V_SCANI, 1)
    # repeat 7: if 활성[i]==1 → d = (x-ox)^2+(y-oy)^2 ; if d<최근거리 → 목표 갱신
    oact = b_listitem(bs, L_OACT[1], L_OACT[0], vrep("스캔i", V_SCANI))
    c_alive = cmp_op("operator_equals", oact, 1)
    ox = b_listitem(bs, L_OX[1], L_OX[0], vrep("스캔i", V_SCANI))
    oy = b_listitem(bs, L_OY[1], L_OY[0], vrep("스캔i", V_SCANI))
    ddx = op("operator_subtract", ox, b_xpos(bs))
    ddy = op("operator_subtract", oy, b_ypos(bs))
    d2 = op("operator_add", op("operator_multiply", ddx, ddx), op("operator_multiply", ddy, ddy))
    # 비교용으로 거리 제곱을 다시 계산(리포터 트리 별도)
    ox2 = b_listitem(bs, L_OX[1], L_OX[0], vrep("스캔i", V_SCANI))
    oy2 = b_listitem(bs, L_OY[1], L_OY[0], vrep("스캔i", V_SCANI))
    ddx2 = op("operator_subtract", ox2, b_xpos(bs))
    ddy2 = op("operator_subtract", oy2, b_ypos(bs))
    d2b = op("operator_add", op("operator_multiply", ddx2, ddx2), op("operator_multiply", ddy2, ddy2))
    c_closer = cmp_op("operator_lt", d2b, vrep("최근거리", V_BESTD))
    upd_best = b_setvar(bs, "최근거리", V_BESTD, d2)
    upd_tx = b_setvar(bs, "목표x", V_TGTX, b_listitem(bs, L_OX[1], L_OX[0], vrep("스캔i", V_SCANI)))
    upd_ty = b_setvar(bs, "목표y", V_TGTY, b_listitem(bs, L_OY[1], L_OY[0], vrep("스캔i", V_SCANI)))
    upd_has = b_setvar(bs, "목표있음", V_HASTGT, 1)
    C(bs, [upd_best, upd_tx, upd_ty, upd_has])
    if_closer = b_if(bs, c_closer, upd_best)
    if_alive = b_if(bs, c_alive, if_closer)
    inc_scan = b_changevar(bs, "스캔i", V_SCANI, 1)
    C(bs, [if_alive, inc_scan])
    rep_scan = b_repeat(bs, 7, if_alive)
    # ★ 돌파 게이트: 가장 가까운 적이 돌파거리(140px, 제곱 19600)보다 멀면 = 근처가 정리됨 →
    #   목표있음=0 으로 되돌려 유닛이 적 타워로 전진(2순위 돌파). 근처에 적이 있으면(≤140) 교전 유지.
    #   중앙 앵커 덕에 평소엔 중앙 난전, 국지적으로 적을 밀어낸 생존 유닛이 타워를 깨서 결착.
    c_far_break = cmp_op("operator_gt", vrep("최근거리", V_BESTD), 12100)
    clr_far = b_setvar(bs, "목표있음", V_HASTGT, 0)
    if_far_break = b_if(bs, c_far_break, clr_far)
    reset_reaim = b_setvar(bs, "재조준타이머", V_REAIMT, op("operator_random", 13, 18, key1="FROM", key2="TO"))
    C(bs, [set_best, set_notgt, set_scan1, rep_scan, if_far_break, reset_reaim])
    if_reaim = b_if(bs, c_reaim, set_best)
    dec_reaim = b_changevar(bs, "재조준타이머", V_REAIMT, -1)

    # 3) 이동 + 사격: 목표 있으면 목표 방향, 없으면 적 본진 방향.
    #    목표까지 거리(dist) < 내사거리 → 정지 후 발사, 아니면 접근.
    # 목표 x/y 결정: 목표있음이면 재조준 스캔이 세팅한 목표x/목표y 사용,
    # 없으면 적 본부 타워(x=0, y=±155)로 조준 → 유닛이 타워로 수렴해 사격(총알이 타워에 명중).
    TOWER_Y = 155 if A else -155
    set_aimx = b_setvar(bs, "목표x", V_TGTX, 0)
    set_aimy = b_setvar(bs, "목표y", V_TGTY, TOWER_Y)
    c_notgt = b_not(bs, cmp_op("operator_gt", vrep("목표있음", V_HASTGT), 0))
    if_notgt = b_if(bs, c_notgt, set_aimx)
    C(bs, [set_aimx, set_aimy])
    # 방향 벡터
    vx = op("operator_subtract", vrep("목표x", V_TGTX), b_xpos(bs))
    vy = op("operator_subtract", vrep("목표y", V_TGTY), b_ypos(bs))
    dist = b_sqrt(bs, op("operator_add", op("operator_multiply",
              op("operator_subtract", vrep("목표x", V_TGTX), b_xpos(bs)),
              op("operator_subtract", vrep("목표x", V_TGTX), b_xpos(bs))),
              op("operator_multiply",
              op("operator_subtract", vrep("목표y", V_TGTY), b_ypos(bs)),
              op("operator_subtract", vrep("목표y", V_TGTY), b_ypos(bs)))))
    set_dist = b_setvar(bs, "최근거리", V_BESTD, dist)  # reuse 최근거리 as scratch dist
    fire_sign = 1 if A else -1
    # ★ 타겟 우선순위: 1순위=가장 가까운 적 유닛(목표있음=1) → 그 유닛을 향해 전진, 사거리 안이면
    #   그 자리에서 사격(dwell, 타워로 끌려가지 않음 → 유닛끼리 중앙에서 교전이 메인).
    #   2순위=적 유닛이 없을 때(목표없음)만 목표를 적 타워(0,±155)로 잡아 전진·사격(돌파). →
    #   교전에서 이긴 생존 유닛이 타워를 깨서 승부는 계속 나되, 평소엔 유닛끼리 싸운다.
    #   전진은 O(1)(단위벡터×속도), 명중은 collision O(1). 스캔은 조준용 throttle 뿐.
    safe_d = op("operator_add", vrep("최근거리", V_BESTD), 0.001)
    ux = op("operator_divide", vx, safe_d); uy = op("operator_divide", vy, safe_d)
    adv_x = b_changex(bs, op("operator_multiply", ux, vrep("내속도", V_SPD)))
    adv_y = b_changey(bs, op("operator_multiply", uy, vrep("내속도", V_SPD)))
    C(bs, [adv_x, adv_y])
    # dwell(사거리 안):
    #   ● 적 유닛 교전 중(목표있음=1): 목표 x 로 미세 정렬 + ★중앙 밴드(y≈0)로 복원력
    #     (y += (0 - y)*0.06) → 유닛들이 화면 중앙에서 서로 왔다갔다하며 총격전(타워로 안 빠짐).
    #   ● 목표없음(적 유닛 소멸 등, 타워가 목표): 타워 쪽으로 빠르게 전진(내속도*0.5)해 돌파.
    dwell_eng_x = b_changex(bs, op("operator_multiply", ux, 0.6))
    # 중앙 복원력(0-y)*0.05 + 아주 느린 전진 크리프(내속도*0.10) → 중앙 밴드에서 왔다갔다 하되,
    #   한쪽이 국지적으로 우세하면 전선이 서서히 밀려 결국 타워에 도달(교착 방지·결착 유지).
    # 중앙 앵커: 약한 복원력(0-y)*0.028 로 중앙 밴드 근처에 모이되, 적진 쪽 전진 크리프(내속도*0.28)로
    #   전선이 꾸준히 밀림. 평형점이 중앙보다 앞이라 교전은 중앙 밴드에서 벌어지되 교착 없이 결착.
    center_pull = op("operator_add",
                     op("operator_multiply", op("operator_subtract", 0, b_ypos(bs)), 0.028),
                     op("operator_multiply", vrep("내속도", V_SPD), 0.34 * fire_sign))
    dwell_eng_y = b_changey(bs, center_pull)
    C(bs, [dwell_eng_x, dwell_eng_y])
    dwell_push_x = b_changex(bs, op("operator_multiply", ux, 0.6))
    dwell_push_y = b_changey(bs, op("operator_multiply", vrep("내속도", V_SPD), 0.5 * fire_sign))
    C(bs, [dwell_push_x, dwell_push_y])
    c_hastgt_dwell = cmp_op("operator_gt", vrep("목표있음", V_HASTGT), 0)
    dwell_x = b_ifelse(bs, c_hastgt_dwell, dwell_eng_x, dwell_push_x)
    engage_gate = op("operator_multiply", vrep("내사거리", V_RNG), 0.8)
    c_close = b_not(bs, cmp_op("operator_gt", vrep("최근거리", V_BESTD), engage_gate))
    move_body = b_ifelse(bs, c_close, dwell_x, adv_x)
    push_head = move_body
    # 본진 넘어가지 않게 y 클램프
    if A:
        c_yhi = cmp_op("operator_gt", b_ypos(bs), 165); cly_hi = b_sety(bs, 165); if_yclamp = b_if(bs, c_yhi, cly_hi)
    else:
        c_ylo = cmp_op("operator_lt", b_ypos(bs), -165); cly_lo = b_sety(bs, -165); if_yclamp = b_if(bs, c_ylo, cly_lo)
    # 화면 안 클램프(x)
    c_xhi = cmp_op("operator_gt", b_xpos(bs), 228); clx_hi = b_setx(bs, 228); if_xhi = b_if(bs, c_xhi, clx_hi)
    c_xlo = cmp_op("operator_lt", b_xpos(bs), -228); clx_lo = b_setx(bs, -228); if_xlo = b_if(bs, c_xlo, clx_lo)

    # 4) 발사: 발사쿨<=0 & (목표있음 or 항상 본진 사격) & 총알수<총알캡 → 발사 방송.
    #    방향 단위벡터(현재 조준점 기준) 를 발사 채널에 세팅.
    c_firecd = b_not(bs, cmp_op("operator_gt", vrep("발사쿨", V_FIRET), 0))
    BCNT = (V_ABCNT, "아군총알수") if A else (V_EBCNT, "적총알수")
    c_bulletroom = cmp_op("operator_lt", vrep(BCNT[1], BCNT[0]), vrep("총알캡", V_BULLETCAP))
    c_canfire = bool_op("operator_and", c_firecd, c_bulletroom)
    # 발사 방향 단위벡터
    fvx = op("operator_subtract", vrep("목표x", V_TGTX), b_xpos(bs))
    fvy = op("operator_subtract", vrep("목표y", V_TGTY), b_ypos(bs))
    fdist = b_sqrt(bs, op("operator_add",
              op("operator_multiply",
                 op("operator_subtract", vrep("목표x", V_TGTX), b_xpos(bs)),
                 op("operator_subtract", vrep("목표x", V_TGTX), b_xpos(bs))),
              op("operator_multiply",
                 op("operator_subtract", vrep("목표y", V_TGTY), b_ypos(bs)),
                 op("operator_subtract", vrep("목표y", V_TGTY), b_ypos(bs)))))
    set_fdist = b_setvar(bs, "최근거리", V_BESTD, fdist)
    safe_fd = op("operator_add", vrep("최근거리", V_BESTD), 0.001)
    set_bx = b_setvar(bs, BFX[1], BFX[0], b_xpos(bs))
    set_by = b_setvar(bs, BFY[1], BFY[0], b_ypos(bs))
    set_bdx = b_setvar(bs, BFDX[1], BFDX[0], op("operator_divide", fvx, safe_fd))
    set_bdy = b_setvar(bs, BFDY[1], BFDY[0], op("operator_divide", fvy, safe_fd))
    set_bt = b_setvar(bs, BFT[1], BFT[0], vrep("내종류", V_TYPE))
    bc_fire = b_broadcast(bs, FIRE_BR[1], FIRE_BR[0])
    # 총구 점멸 코스튬
    c_t1f = cmp_op("operator_equals", vrep("내종류", V_TYPE), 1)
    c_t2f = cmp_op("operator_equals", vrep("내종류", V_TYPE), 2)
    swf1 = b_costume(bs, f"{CS}소총F"); swf2 = b_costume(bs, f"{CS}제압F"); swf3 = b_costume(bs, f"{CS}저격F")
    if_f2 = b_ifelse(bs, c_t2f, swf2, swf3)
    if_f1 = b_ifelse(bs, c_t1f, swf1, if_f2)
    pew = b_playsound(bs, "pew")
    # 발사쿨 종류별
    cd_low = 3; cd_mg = 2; cd_snipe = 9
    set_cd1 = b_setvar(bs, "발사쿨", V_FIRET, cd_low); set_cd2 = b_setvar(bs, "발사쿨", V_FIRET, cd_mg); set_cd3 = b_setvar(bs, "발사쿨", V_FIRET, cd_snipe)
    if_cd2 = b_ifelse(bs, cmp_op("operator_equals", vrep("내종류", V_TYPE), 2), set_cd2, set_cd3)
    if_cd1 = b_ifelse(bs, cmp_op("operator_equals", vrep("내종류", V_TYPE), 1), set_cd1, if_cd2)
    fire_seq = [set_fdist, set_bx, set_by, set_bdx, set_bdy, set_bt, if_f1, bc_fire, pew, if_cd1]
    if A:
        # ★ 돌격 버프 중이면 아군 발사쿨 절반(화력↑). 버프 = 전역 돌격버프 타이머>0 (O(1) 읽기).
        c_buff = cmp_op("operator_gt", vrep("돌격버프", V_CHGBUFF), 0)
        halve = b_setvar(bs, "발사쿨", V_FIRET,
                         op("operator_divide", vrep("발사쿨", V_FIRET), 2))
        if_buff = b_if(bs, c_buff, halve)
        fire_seq.append(if_buff)
    C(bs, fire_seq)
    # 발사 조건: 발사쿨끝 & 총알여유 & (목표있음이면 사거리 안일 때만; 목표없으면 본진 근처일 때만)
    #   목표있음: dist(최근거리는 위 이동에서 세팅됨) <= 내사거리
    #   목표없음: 적 본진 y 접근(|y - 적본진y| < 60) 이어야 본진 사격
    c_inrange = b_not(bs, cmp_op("operator_gt",
                    b_sqrt(bs, op("operator_add",
                       op("operator_multiply",
                          op("operator_subtract", vrep("목표x", V_TGTX), b_xpos(bs)),
                          op("operator_subtract", vrep("목표x", V_TGTX), b_xpos(bs))),
                       op("operator_multiply",
                          op("operator_subtract", vrep("목표y", V_TGTY), b_ypos(bs)),
                          op("operator_subtract", vrep("목표y", V_TGTY), b_ypos(bs))))),
                    vrep("내사거리", V_RNG)))
    c_fire_ok = bool_op("operator_and", c_canfire, c_inrange)
    if_fire = b_if(bs, c_fire_ok, set_fdist)
    # 발사쿨 감소 + 평상 코스튬 복귀
    c_fpos = cmp_op("operator_gt", vrep("발사쿨", V_FIRET), 0)
    dec_fire = b_changevar(bs, "발사쿨", V_FIRET, -1)
    if_firedec = b_if(bs, c_fpos, dec_fire)
    c_t1n = cmp_op("operator_equals", vrep("내종류", V_TYPE), 1)
    c_t2n = cmp_op("operator_equals", vrep("내종류", V_TYPE), 2)
    swn1 = b_costume(bs, f"{CS}소총"); swn2 = b_costume(bs, f"{CS}제압"); swn3 = b_costume(bs, f"{CS}저격")
    if_n2 = b_ifelse(bs, c_t2n, swn2, swn3)
    if_n1 = b_ifelse(bs, c_t1n, swn1, if_n2)
    c_lowcd = b_not(bs, cmp_op("operator_gt", vrep("발사쿨", V_FIRET), 3))
    if_normal = b_if(bs, c_lowcd, if_n1)

    # 5) ★ 피격: collision O(1) — touching 상대총알 → 내HP 감소 + 팝업요청.
    c_hit = b_touchingsprite(bs, ENEMY_BULLET)
    take = b_changevar(bs, "내HP", V_HP, op("operator_random", -11, -5, key1="FROM", key2="TO"))
    # 팝업 요청(팝업수<캡)
    c_poproom = cmp_op("operator_lt", vrep("팝업수", V_POPCNT), vrep("팝업캡", V_POPCAP))
    set_ppx = b_setvar(bs, "팝업x", V_POPX, b_xpos(bs))
    set_ppy = b_setvar(bs, "팝업y", V_POPY, b_ypos(bs))
    set_ppv = b_setvar(bs, "팝업값", V_POPVAL, op("operator_random", 3, 8, key1="FROM", key2="TO"))
    bc_pop = b_broadcast(bs, "팝업요청", BR_POP)
    C(bs, [set_ppx, set_ppy, set_ppv, bc_pop])
    if_pop = b_if(bs, c_poproom, set_ppx)
    ghit = b_changeeffect(bs, "GHOST", 40); wgh = b_wait(bs, 0.02); cgh = b_seteffect(bs, "GHOST", 0)
    C(bs, [take, if_pop, ghit, wgh, cgh])
    if_hit = b_if(bs, c_hit, take)

    # 6) 본진 사격 딜: 적 본진 근처(전선 돌파)까지 밀고 올라오면 매틱 본진HP 감소.
    #    막는 적이 없어 유닛이 본진까지 전진한 경우 = 돌파. (총알 본진 명중과 별개 보조 딜.)
    ENEMY_BASE_HP = (V_EHP, "적본진HP") if A else (V_AHP, "아군본진HP")
    if A:
        c_atbase = cmp_op("operator_gt", b_ypos(bs), 138)
    else:
        c_atbase = cmp_op("operator_lt", b_ypos(bs), -138)
    dmg_base = b_changevar(bs, ENEMY_BASE_HP[1], ENEMY_BASE_HP[0], op("operator_multiply", vrep("본진딜", V_BASEDMG), -0.18))
    if_base = b_if(bs, c_atbase, dmg_base)

    # 7) 사망: 내HP<1 → 슬롯 해제, 카운트 감소, 팝 이펙트, 삭제
    c_kill = cmp_op("operator_lt", vrep("내HP", V_HP), 1)
    rel_act_k = b_listreplace(bs, L_MACT[1], L_MACT[0], vrep("내슬롯", V_SLOT), 0)
    dec_cnt_k = b_changevar(bs, CNT[1], CNT[0], -1)
    swpop = b_costume(bs, f"{CS}팝")
    csz = b_changesize(bs, 14); cgh2 = b_changeeffect(bs, "GHOST", 22); wpop = b_wait(bs, 0.02)
    C(bs, [csz, cgh2, wpop]); rep_pop = b_repeat(bs, 4, csz)
    pk = b_playsound(bs, "crack"); del_k = b_delclone(bs)
    C(bs, [rel_act_k, dec_cnt_k, swpop, rep_pop, pk, del_k])
    if_kill = b_if(bs, c_kill, rel_act_k)

    # forever 조립
    play_body = [rec_x, rec_y, rec_hp, if_reaim, dec_reaim, if_notgt, set_dist, push_head,
                 if_yclamp, if_xhi, if_xlo, if_fire, if_firedec, if_normal, if_hit, if_base, if_kill]
    C(bs, play_body)
    if_play = b_if(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1), rec_x)
    w_body = b_wait(bs, 0.02)
    C(bs, [if_end, if_play, w_body])
    fe = b_forever(bs, if_end)
    # 자유 슬롯이 없으면(내슬롯==0) 초과분 → 카운트 되돌리고 즉시 삭제(캡 하드가드).
    c_noslot = b_not(bs, cmp_op("operator_gt", vrep("내슬롯", V_SLOT), 0))
    undo_cnt = b_changevar(bs, CNT[1], CNT[0], -1)
    del_noslot = b_delclone(bs)
    C(bs, [undo_cnt, del_noslot])
    if_noslot = b_if(bs, c_noslot, undo_cnt)
    C(bs, [ch, set1, set_type, if_t1, set_slot0, set_i0, rep_claim, if_noslot,
           g0, set_reaim0, set_fire0, set_hastgt0, fr, show, fe])

    add_comment(bs, comments, if_reaim,
        "\U0001F464★ 자율 유닛: 캡7 하에 상대 로스터(index 1..7 상수 스캔)를 재조준타이머마다만(throttle,\n"
        "매 프레임 아님) 훑어 가장 가까운 활성 적을 조준. 사거리 안이면 총알 클론 발사, 밖이면 접근.\n"
        "살아있는 적이 없으면 적 본진으로 전진해 본진 사격. 캡이 n을 묶어 O(n²) 스캔을 감당 가능하게 함.",
        x=470, y=380, w=440, h=150)
    add_comment(bs, comments, if_hit,
        "\U0001F4A5★ 명중은 collision(touching 상대총알)으로 O(1)! 리스트 스캔 아님.\n"
        "맞으면 내HP 감소 + 팝업요청. 유닛끼리 서로 스캔하지 않고 총알 충돌로 해결.",
        x=470, y=760, w=420, h=110)
    return bs, comments

def CNT_bullet_name(A):
    return (V_ABCNT, "아군총알수") if A else (V_EBCNT, "적총알수")

# ============================================================
#  총알 (진영별) — 발사 방송 시 클론 1기, 조준 방향 직진.
#  touching[상대유닛] → 명중 삭제. 화면 밖 → 삭제. 진영 총알수 캡.
# ============================================================
def build_bullet_blocks(side):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    A = (side == "A")
    FIRE_BR = (BR_AFIRE, "아군발사") if A else (BR_EFIRE, "적발사")
    BFX = (V_ABX, "탄Ax") if A else (V_EBX, "탄Ex")
    BFY = (V_ABY, "탄Ay") if A else (V_EBY, "탄Ey")
    BFDX= (V_ABDX, "탄Adx") if A else (V_EBDX, "탄Edx")
    BFDY= (V_ABDY, "탄Ady") if A else (V_EBDY, "탄Edy")
    BCNT= (V_ABCNT, "아군총알수") if A else (V_EBCNT, "적총알수")
    BFT = (V_ABTYPE, "탄A종류") if A else (V_EBTYPE, "탄E종류")
    TARGET_UNIT = "적유닛" if A else "아군유닛"
    TARGET_HQ = "적본부" if A else "아군본부"
    ENEMY_BASE_HP = (V_EHP, "적본진HP") if A else (V_AHP, "아군본진HP")
    # 상대 진영 로스터(총알이 거리판정으로 명중 검사) + 피해 누적기
    L_OX  = (L_EX, "L_적x") if A else (L_AX, "L_아군x")
    L_OY  = (L_EY, "L_적y") if A else (L_AY, "L_아군y")
    L_OACT= (L_EACT, "L_적활성") if A else (L_AACT, "L_아군활성")
    L_ODMG= (L_EDMG, "L_적피해") if A else (L_ADMG, "L_아군피해")
    costume = "아탄" if A else "적탄"
    SPEED = 8
    HIT_R = 20   # ★ 히트 반경(px) — 시각 크기(작은 원)와 분리. 총알 중심이 유닛 중심 20px 안이면 명중.
    BULLET_DMG = 5

    # 깃발: 숨김·가드. 원형 총알이라 회전 정렬 불필요(don't rotate).
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs, "don't rotate"); orig0 = b_setvar(bs, "복제됨", V_B_ISC, 0)
    C(bs, [h, hi, rs, orig0])

    # 발사 방송 → 원본만: 총알수<캡 이면 총알수+1 후 클론
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": [FIRE_BR[1], FIRE_BR[0]]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_B_ISC), 0)
    c_room = cmp_op("operator_lt", vrep(BCNT[1], BCNT[0]), vrep("총알캡", V_BULLETCAP))
    c_ok = bool_op("operator_and", c_orig, c_room)
    inc = b_changevar(bs, BCNT[1], BCNT[0], 1)
    cc = b_createclone(bs)
    C(bs, [inc, cc])
    if_c = b_if(bs, c_ok, inc)
    C(bs, [hb, if_c])

    # 클론 본체
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_B_ISC, 1)
    # 방향 벡터 로컬 저장 + 시작 위치
    set_dx = b_setvar(bs, "b_dx", V_BDX, vrep(BFDX[1], BFDX[0]))
    set_dy = b_setvar(bs, "b_dy", V_BDY, vrep(BFDY[1], BFDY[0]))
    # ★ 탄 종류 저장: 유닛 총알=1~3, 타워 포탑 총알=0(센티넬). 타워가 쏜 총알(0)은 상대 타워에
    #   피해를 주지 않음(타워→타워 공격 금지). 유닛 총알(>0)만 타워 공성 유효.
    set_bt = b_setvar(bs, "b_life", V_BLIFE, vrep(BFT[1], BFT[0]))
    g0 = b_gotoxy(bs, vrep(BFX[1], BFX[0]), vrep(BFY[1], BFY[0]))
    # ★ 총알 시각 크기 축소(작은 원). 명중 안정성은 시각 크기와 분리 —
    #   아래 서브스텝 이동 + 큰 대상(유닛/타워)의 touching 검사로 관통(tunneling) 방지.
    swc = b_costume(bs, costume); sz = b_setsize(bs, 60); fr = b_front(bs); show = b_show(bs)

    def kill_seq(bs, extra=None):
        dec = b_changevar(bs, BCNT[1], BCNT[0], -1)
        dc = b_delclone(bs)
        seq = ([extra] if extra else []) + [dec, dc]
        C(bs, seq)
        return seq[0]
    # ★ 거리기반 명중 스캔(시각 크기와 완전 분리): 상대 로스터(≤7) 를 순회해 활성 유닛 중 총알 중심에서
    #   HIT_R 안에 있는 슬롯을 찾으면 그 슬롯의 피해누적기(L_적피해[slot])에 BULLET_DMG 누적 → 총알 삭제.
    #   (유닛은 매 프레임 자기 슬롯 누적값을 읽어 HP 차감 — touching 프레임 레이스/관통과 무관하게 확실히 명중.)
    def hit_checks_seq():
        # (1) 유닛 히트: 로스터 거리 스캔
        set_hit0 = b_setvar(bs, "탄히트", V_B_HIT, 0)
        set_si1 = b_setvar(bs, "탄스캔i", V_B_SI, 1)
        oact = b_listitem(bs, L_OACT[1], L_OACT[0], vrep("탄스캔i", V_B_SI))
        c_alive = cmp_op("operator_equals", oact, 1)
        oux = b_listitem(bs, L_OX[1], L_OX[0], vrep("탄스캔i", V_B_SI))
        ouy = b_listitem(bs, L_OY[1], L_OY[0], vrep("탄스캔i", V_B_SI))
        ddx = op("operator_subtract", oux, b_xpos(bs)); ddy = op("operator_subtract", ouy, b_ypos(bs))
        d2 = op("operator_add", op("operator_multiply", ddx, ddx), op("operator_multiply", ddy, ddy))
        c_inhit = b_not(bs, cmp_op("operator_gt", d2, HIT_R*HIT_R))
        c_nohit_yet = b_not(bs, cmp_op("operator_gt", vrep("탄히트", V_B_HIT), 0))
        c_hit_slot = bool_op("operator_and", bool_op("operator_and", c_alive, c_inhit), c_nohit_yet)
        cur_dmg = b_listitem(bs, L_ODMG[1], L_ODMG[0], vrep("탄스캔i", V_B_SI))
        add_dmg = b_listreplace(bs, L_ODMG[1], L_ODMG[0], vrep("탄스캔i", V_B_SI),
                                op("operator_add", cur_dmg, BULLET_DMG))
        mark_hit = b_setvar(bs, "탄히트", V_B_HIT, 1)
        C(bs, [add_dmg, mark_hit])
        if_hit_slot = b_if(bs, c_hit_slot, add_dmg)
        inc_si = b_changevar(bs, "탄스캔i", V_B_SI, 1)
        C(bs, [if_hit_slot, inc_si])
        rep_scan = b_repeat(bs, 7, if_hit_slot)
        # 히트했으면 삭제
        c_hit = cmp_op("operator_gt", vrep("탄히트", V_B_HIT), 0)
        hit_del = kill_seq(bs)
        if_hit = b_if(bs, c_hit, hit_del)
        # (2) 타워 히트: touching 적 타워(큰 히트박스라 touching 안정) — 유닛탄만 딜.
        c_hitbase = b_touchingsprite(bs, TARGET_HQ)
        dmg_base = b_changevar(bs, ENEMY_BASE_HP[1], ENEMY_BASE_HP[0], op("operator_multiply", vrep("본진딜", V_BASEDMG), -5))
        c_unitbullet = cmp_op("operator_gt", vrep("b_life", V_BLIFE), 0)
        base_dmg_head = kill_seq(bs, dmg_base)
        base_del_head = kill_seq(bs)
        base_body = b_ifelse(bs, c_unitbullet, base_dmg_head, base_del_head)
        if_base = b_if(bs, c_hitbase, base_body)
        # (3) 화면 밖 사방(x·y): 즉시 삭제
        c_offy = bool_op("operator_or", cmp_op("operator_gt", b_ypos(bs), 172), cmp_op("operator_lt", b_ypos(bs), -172))
        c_offx = bool_op("operator_or", cmp_op("operator_gt", b_xpos(bs), 232), cmp_op("operator_lt", b_xpos(bs), -232))
        c_off = bool_op("operator_or", c_offy, c_offx)
        off_head = kill_seq(bs); if_off = b_if(bs, c_off, off_head)
        # 전체 순서(외부 체인에서 연결): 스캔(set_hit0→set_si1→rep_scan) → if_hit → if_base → if_off
        return set_hit0, [set_hit0, set_si1, rep_scan, if_hit, if_base, if_off]
    # ★ 서브스텝 4단계: 프레임 이동 SPEED 를 4번(각 SPEED/4=2px)으로 나눠 매 스텝 명중 스캔 →
    #   빠른·작은 총알도 절대 관통 못함(스텝이동 2px ≪ 히트반경 20px).
    NSUB = 4
    sub = SPEED / float(NSUB)
    substeps = []
    first_head = None
    for _ in range(NSUB):
        mx = b_changex(bs, op("operator_multiply", vrep("b_dx", V_BDX), sub))
        my = b_changey(bs, op("operator_multiply", vrep("b_dy", V_BDY), sub))
        hh, hitseq = hit_checks_seq()
        substeps += [mx, my] + hitseq
        if first_head is None: first_head = mx
    # 게임끝 정리
    c_gameend = b_not(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    dec_end = b_changevar(bs, BCNT[1], BCNT[0], -1); del_end = b_delclone(bs)
    C(bs, [dec_end, del_end])
    if_end = b_if(bs, c_gameend, dec_end)
    play_body = substeps + [if_end]
    C(bs, play_body)
    fe = b_forever(bs, first_head)
    C(bs, [ch, set1, set_dx, set_dy, g0, swc, sz, fr, show, fe])
    add_comment(bs, comments, first_head,
        "\U0001F52B★ 실탄 탄환(작은 원): 시각 크기(size 60)와 명중을 완전 분리. 한 프레임 이동을 4 서브스텝\n"
        "(각 2px)으로 쪼개고 매 스텝 상대 로스터(≤7)를 거리스캔(중심<20px) → 명중 슬롯의 피해누적기에\n"
        "데미지 적립 + 총알 즉시 삭제. 유닛은 자기 슬롯 누적피해를 매 프레임 읽어 HP 차감(관통·레이스 0).\n"
        "타워는 touching(큰 박스) 판정. 화면 밖(x·y 사방) 즉시 삭제 → 부유 총알 0.",
        x=470, y=380, w=460, h=170)
    return bs, comments

# ============================================================
#  데미지 팝업 (플로팅 텍스트 클론)
# ============================================================
def build_popup_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs, "don't rotate"); orig0 = b_setvar(bs, "복제됨", V_B_ISC, 0)
    C(bs, [h, hi, rs, orig0])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["팝업요청", BR_POP]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_B_ISC), 0)
    c_room = cmp_op("operator_lt", vrep("팝업수", V_POPCNT), vrep("팝업캡", V_POPCAP))
    c_ok = bool_op("operator_and", c_orig, c_room)
    inc = b_changevar(bs, "팝업수", V_POPCNT, 1)
    cc = b_createclone(bs)
    C(bs, [inc, cc])
    if_c = b_if(bs, c_ok, inc)
    C(bs, [hb, if_c])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=380)
    set1 = b_setvar(bs, "복제됨", V_B_ISC, 1)
    g0 = b_gotoxy(bs, vrep("팝업x", V_POPX), vrep("팝업y", V_POPY))
    c_low = b_not(bs, cmp_op("operator_gt", vrep("팝업값", V_POPVAL), 4))
    c_mid = b_not(bs, cmp_op("operator_gt", vrep("팝업값", V_POPVAL), 6))
    sw_low = b_costume(bs, "약"); sw_mid = b_costume(bs, "중"); sw_high = b_costume(bs, "강")
    if_mid = b_ifelse(bs, c_mid, sw_mid, sw_high)
    if_low = b_ifelse(bs, c_low, sw_low, if_mid)
    setg = b_seteffect(bs, "GHOST", 0); sz = b_setsize(bs, 100); fr = b_front(bs); show = b_show(bs)
    up = b_changey(bs, 2); addg = b_changeeffect(bs, "GHOST", 7); wu = b_wait(bs, 0.04)
    C(bs, [up, addg, wu]); rep = b_repeat(bs, 12, up)
    dec = b_changevar(bs, "팝업수", V_POPCNT, -1)
    ptick = b_playsound(bs, "tick")
    delc = b_delclone(bs)
    C(bs, [ch, set1, g0, if_low, setg, sz, fr, show, ptick, rep, dec, delc])
    add_comment(bs, comments, inc,
        "\U0001F4A5 데미지 팝업: 팝업요청 시 팝업수<팝업캡20 일 때만 생성(+1).\n"
        "위로 떠오르며 fade, 약0.48초 후 팝업수-1 + delete this clone. 누수 0.",
        x=470, y=200, w=400, h=110)
    return bs, comments

# ============================================================
#  소환 버튼 (3버튼 각 1스프라이트) — 클릭 시 즉시 소환(열린 필드)
# ============================================================
def build_button_blocks(kind):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    # ★ 소환버튼 = 화면 우측 세로 스택(x=188). y=120/65/10 간격55 → 버튼끼리(높이~40) 겹침 없음.
    #   지갑바(x≈60,폭170→x≤145)·HP바(x≈-95)·중앙 전장과 겹치지 않는 우측 여백.
    conf = {
        "rifle": (V_C_RIFLE, "소총_코스트", V_CDT_RIFLE, "소총_쿨타이머", V_CD_RIFLE, "소총_소환쿨", 1, "버튼소총", 188, 120),
        "mg":    (V_C_MG,    "제압_코스트", V_CDT_MG,    "제압_쿨타이머", V_CD_MG,    "제압_소환쿨", 2, "버튼제압", 188, 65),
        "snipe": (V_C_SNIPE, "저격_코스트", V_CDT_SNIPE, "저격_쿨타이머", V_CD_SNIPE, "저격_소환쿨", 3, "버튼저격", 188, 10),
    }[kind]
    COST_ID, COST_NM, CDT_ID, CDT_NM, CD_ID, CD_NM, TYPE_VAL, BASE, xpos, ypos = conf

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, xpos, ypos); sz = b_setsize(bs, 100); fr = b_front(bs); swc = b_costume(bs, BASE+"On")
    C(bs, [h, show, g, sz, fr, swc])

    # 코스튬 갱신 forever: 가능하면 ON, 아니면 OFF
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=220)
    c_gold = b_not(bs, cmp_op("operator_lt", vrep("돈", V_GOLD), vrep(COST_NM, COST_ID)))
    c_cd = b_not(bs, cmp_op("operator_gt", vrep(CDT_NM, CDT_ID), 0))
    c_cap = cmp_op("operator_lt", vrep("아군수", V_ACNT), vrep("유닛캡", V_UNITCAP))
    c_ok = bool_op("operator_and", bool_op("operator_and", c_gold, c_cd), c_cap)
    sw_on = b_costume(bs, BASE+"On"); sw_off = b_costume(bs, BASE+"Off")
    if_cos = b_ifelse(bs, c_ok, sw_on, sw_off)
    w_c = b_wait(bs, 0.05)
    C(bs, [if_cos, w_c])
    fe_c = b_forever(bs, if_cos)
    C(bs, [hc, fe_c])

    # 클릭 폴링+디바운스 forever → 게이트 통과 시 즉시 소환
    hp = gen(); bs[hp] = mk("event_whenflagclicked", top=True, x=470, y=220)
    c_md = b_mousedown(bs); c_tm = b_touchingmouse(bs)
    c_click = bool_op("operator_and", c_md, c_tm)
    g_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    g_gold = b_not(bs, cmp_op("operator_lt", vrep("돈", V_GOLD), vrep(COST_NM, COST_ID)))
    g_cd = b_not(bs, cmp_op("operator_gt", vrep(CDT_NM, CDT_ID), 0))
    g_cap = cmp_op("operator_lt", vrep("아군수", V_ACNT), vrep("유닛캡", V_UNITCAP))
    g_ok = bool_op("operator_and", bool_op("operator_and", g_gold, g_cd), bool_op("operator_and", g_cap, g_play))
    dec_gold = b_changevar(bs, "돈", V_GOLD, op("operator_subtract", 0, vrep(COST_NM, COST_ID)))
    set_cd = b_setvar(bs, CDT_NM, CDT_ID, vrep(CD_NM, CD_ID))
    set_ty = b_setvar(bs, "소환종류", V_SPTYPE, TYPE_VAL)
    bc_a = b_broadcast_wait(bs, "아군소환", BR_ASPAWN)
    pp = b_playsound(bs, "pop")
    C(bs, [dec_gold, set_cd, set_ty, bc_a, pp])
    if_spawn = b_if(bs, g_ok, dec_gold)
    wu_up = b_waituntil(bs, b_not(bs, b_mousedown(bs)))
    C(bs, [if_spawn, wu_up])
    if_click = b_if(bs, c_click, if_spawn)
    w_p = b_wait(bs, 0.02)
    C(bs, [if_click, w_p])
    fe_p = b_forever(bs, if_click)
    C(bs, [hp, fe_p])
    add_comment(bs, comments, if_click,
        "\U0001F5B1️ 유닛 버튼: 클릭 폴링+디바운스 → 게이트(돈≥코스트 & 소환쿨끝 & 아군수<유닛캡7) 통과 시\n"
        "즉시 소환(열린 필드라 구역 지정 없음). 캡 도달 시 회색·소환 거부.",
        x=900, y=220, w=380, h=110)
    return bs, comments

# ============================================================
#  액티브 스킬 버튼 (하단 가로줄) — 클릭 폴링+디바운스 → 게이트 통과 시 스킬 방송
# ============================================================
def build_skill_button_blocks(kind):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    # ★ 스킬버튼 = 하단 가로줄(y=-165). x=-10/70/150(72px 폭). 지갑바(x=-150,폭170→x≤-65)와
    #   우측 소환버튼(x=188,다른 y밴드)과 겹침 0.
    conf = {
        "air":    (V_SK_AIR_C, "포격_코스트", V_SK_AIR_T, "포격_쿨타이머", V_SK_AIR_CD, "포격_쿨", "스킬포격", BR_AIR, "포격", -10),
        "supply": (V_SK_SUP_C, "보급_코스트", V_SK_SUP_T, "보급_쿨타이머", V_SK_SUP_CD, "보급_쿨", "스킬보급", BR_SUP, "보급", 70),
        "charge": (V_SK_CHG_C, "돌격_코스트", V_SK_CHG_T, "돌격_쿨타이머", V_SK_CHG_CD, "돌격_쿨", "스킬돌격", BR_CHG, "돌격", 150),
    }[kind]
    COST_ID, COST_NM, T_ID, T_NM, CD_ID, CD_NM, BASE, BR_ID, BR_NM, xpos = conf
    ypos = -165

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, xpos, ypos); sz = b_setsize(bs, 100); fr = b_front(bs); swc = b_costume(bs, BASE+"On")
    C(bs, [h, show, g, sz, fr, swc])

    # 코스튬 갱신: 돈≥코스트 & 쿨끝 이면 On, 아니면 Off
    hc = gen(); bs[hc] = mk("event_whenflagclicked", top=True, x=20, y=220)
    c_gold = b_not(bs, cmp_op("operator_lt", vrep("돈", V_GOLD), vrep(COST_NM, COST_ID)))
    c_cd = b_not(bs, cmp_op("operator_gt", vrep(T_NM, T_ID), 0))
    c_ok = bool_op("operator_and", c_gold, c_cd)
    sw_on = b_costume(bs, BASE+"On"); sw_off = b_costume(bs, BASE+"Off")
    if_cos = b_ifelse(bs, c_ok, sw_on, sw_off)
    w_c = b_wait(bs, 0.05)
    C(bs, [if_cos, w_c]); fe_c = b_forever(bs, if_cos); C(bs, [hc, fe_c])

    # 클릭 폴링+디바운스 → 게이트 통과 시: 돈-코스트, 쿨 리셋, 스킬 방송, pop
    hp = gen(); bs[hp] = mk("event_whenflagclicked", top=True, x=470, y=220)
    c_md = b_mousedown(bs); c_tm = b_touchingmouse(bs)
    c_click = bool_op("operator_and", c_md, c_tm)
    g_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    g_gold = b_not(bs, cmp_op("operator_lt", vrep("돈", V_GOLD), vrep(COST_NM, COST_ID)))
    g_cd = b_not(bs, cmp_op("operator_gt", vrep(T_NM, T_ID), 0))
    g_ok = bool_op("operator_and", bool_op("operator_and", g_gold, g_cd), g_play)
    dec_gold = b_changevar(bs, "돈", V_GOLD, op("operator_subtract", 0, vrep(COST_NM, COST_ID)))
    set_cd = b_setvar(bs, T_NM, T_ID, vrep(CD_NM, CD_ID))
    bc = b_broadcast(bs, BR_NM, BR_ID)
    pp = b_playsound(bs, "pop")
    C(bs, [dec_gold, set_cd, bc, pp])
    if_use = b_if(bs, g_ok, dec_gold)
    wu_up = b_waituntil(bs, b_not(bs, b_mousedown(bs)))
    C(bs, [if_use, wu_up])
    if_click = b_if(bs, c_click, if_use)
    w_p = b_wait(bs, 0.02); C(bs, [if_click, w_p]); fe_p = b_forever(bs, if_click); C(bs, [hp, fe_p])
    add_comment(bs, comments, if_click,
        "\U0001F5B1️ 액티브 스킬 버튼(하단 가로줄): 클릭 → 돈≥코스트 & 쿨끝이면 즉시 발동 + 돈 차감 + 쿨 리셋.\n"
        "유닛캡7 이후에도 남는 돈을 스킬로 계속 쓸 수 있어요. 못 쓰면 회색.",
        x=900, y=220, w=400, h=110)
    return bs, comments

# ============================================================
#  스킬 처리 스프라이트 — 3 스킬 방송을 받아 '발동 순간 1회' 효과 적용
#   포격: 적 로스터(≤7) 무게중심 계산 → 착탄점 세팅 + 폭발 클론 + 광역타격 방송(적 유닛이 반경 판정)
#   보급: 보급 방송 릴레이(아군 유닛이 회복) + 아군 타워 약간 수리
#   돌격: 돌격버프 타이머 세팅(아군 유닛이 O(1) 로 읽음)
# ============================================================
def build_skillproc_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    # 깃발: 숨김·가드
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); rs = b_rotstyle(bs, "don't rotate"); orig0 = b_setvar(bs, "복제됨", V_SK_ISC, 0)
    C(bs, [h, hi, rs, orig0])

    # ── 포격 방송 → 원본만: 적 무게중심 착탄점 계산(≤7 1회 순회) → 폭발 클론 + 광역타격 방송 ──
    ha = gen(); bs[ha] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["포격", BR_AIR]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_SK_ISC), 0)
    # 합계 초기화
    s_sx = b_setvar(bs, "합계x", V_SK_SX, 0); s_sy = b_setvar(bs, "합계y", V_SK_SY, 0)
    s_n = b_setvar(bs, "표본수", V_SK_N, 0); s_i = b_setvar(bs, "스킬i", V_SK_I, 1)
    # repeat 7: 활성 적이면 합계에 x/y 누적, n+1
    eact = b_listitem(bs, "L_적활성", L_EACT, vrep("스킬i", V_SK_I))
    c_alive = cmp_op("operator_equals", eact, 1)
    ex = b_listitem(bs, "L_적x", L_EX, vrep("스킬i", V_SK_I))
    ey = b_listitem(bs, "L_적y", L_EY, vrep("스킬i", V_SK_I))
    add_sx = b_changevar(bs, "합계x", V_SK_SX, ex); add_sy = b_changevar(bs, "합계y", V_SK_SY, ey)
    add_n = b_changevar(bs, "표본수", V_SK_N, 1)
    C(bs, [add_sx, add_sy, add_n])
    if_alive = b_if(bs, c_alive, add_sx)
    inc_i = b_changevar(bs, "스킬i", V_SK_I, 1)
    C(bs, [if_alive, inc_i])
    rep_c = b_repeat(bs, 7, if_alive)
    # 착탄점: 적이 있으면 무게중심(합계/n), 없으면 적 타워 앞(0, 120)
    c_has = cmp_op("operator_gt", vrep("표본수", V_SK_N), 0)
    set_tx = b_setvar(bs, "타격x", V_STRIKEX, op("operator_divide", vrep("합계x", V_SK_SX), vrep("표본수", V_SK_N)))
    set_ty = b_setvar(bs, "타격y", V_STRIKEY, op("operator_divide", vrep("합계y", V_SK_SY), vrep("표본수", V_SK_N)))
    C(bs, [set_tx, set_ty])
    set_tx0 = b_setvar(bs, "타격x", V_STRIKEX, 0); set_ty0 = b_setvar(bs, "타격y", V_STRIKEY, 120)
    C(bs, [set_tx0, set_ty0])
    if_center = b_ifelse(bs, c_has, set_tx, set_tx0)
    # 폭발 클론 생성 + 광역타격 방송(적 유닛이 반경 판정) + crack 사운드
    mk_boom = b_createclone(bs)
    bc_strike = b_broadcast(bs, "광역타격", BR_STRIKE)
    snd_boom = b_playsound(bs, "crack")
    C(bs, [s_sx, s_sy, s_n, s_i, rep_c, if_center, mk_boom, bc_strike, snd_boom])
    if_air = b_if(bs, c_orig, s_sx)
    C(bs, [ha, if_air])
    add_comment(bs, comments, s_sx,
        "\U0001F4A5 포격: 적 로스터(≤7) 1회 순회로 무게중심(착탄점) 계산 → 폭발 클론 + '광역타격' 방송.\n"
        "적 유닛이 각자 착탄점 반경 안이면 HP 감소(발동 순간 1회, O(n) 순회 — O(n²) 아님).",
        x=470, y=200, w=420, h=110)

    # ── 폭발 클론: 착탄점에서 확장 파이어볼 3프레임 후 삭제 ──
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=560)
    set1 = b_setvar(bs, "복제됨", V_SK_ISC, 1)
    g0 = b_gotoxy(bs, vrep("타격x", V_STRIKEX), vrep("타격y", V_STRIKEY))
    cg = b_cleargfx(bs); sz0 = b_setsize(bs, 100); fr = b_front(bs); show = b_show(bs)
    e1 = b_costume(bs, "폭발A"); w1 = b_wait(bs, 0.05)
    e2 = b_costume(bs, "폭발B"); w2 = b_wait(bs, 0.05)
    e3 = b_costume(bs, "폭발C"); gh = b_seteffect(bs, "GHOST", 50); w3 = b_wait(bs, 0.06)
    delc = b_delclone(bs)
    C(bs, [ch, set1, g0, cg, sz0, fr, show, e1, w1, e2, w2, e3, gh, w3, delc])

    # ── 돌격 방송 → 돌격버프 타이머 세팅(예 5초=250틱) ──
    hg = gen(); bs[hg] = mk("event_whenbroadcastreceived", top=True, x=470, y=200,
        fields={"BROADCAST_OPTION": ["돌격", BR_CHG]})
    set_buff = b_setvar(bs, "돌격버프", V_CHGBUFF, 250)
    C(bs, [hg, set_buff])
    add_comment(bs, comments, set_buff,
        "⚔ 돌격: 돌격버프 타이머=250(≈5초) 세팅. 아군 유닛이 O(1) 로 읽어 발사쿨 절반(화력↑).\n"
        "Stage 쿨루프가 타이머를 감소 → 시간 지나면 자동 해제.",
        x=900, y=200, w=400, h=100)

    # ── 보급 방송 → 아군 타워 약간 수리(아군 유닛 회복은 유닛 스프라이트가 직접 처리) ──
    hs2 = gen(); bs[hs2] = mk("event_whenbroadcastreceived", top=True, x=470, y=380,
        fields={"BROADCAST_OPTION": ["보급", BR_SUP]})
    repair = b_changevar(bs, "아군본진HP", V_AHP, 15)
    c_over = cmp_op("operator_gt", vrep("아군본진HP", V_AHP), 100)
    cap100 = b_setvar(bs, "아군본진HP", V_AHP, 100)
    if_over = b_if(bs, c_over, cap100)
    C(bs, [hs2, repair, if_over])
    add_comment(bs, comments, repair,
        "✚ 보급: 아군 타워 +15 수리(최대 100). 아군 유닛 전체 HP 회복은 아군유닛 스프라이트가\n"
        "'보급' 방송을 받아 각자 내HP=내최대HP 로 처리(≤7, O(n)).",
        x=900, y=380, w=400, h=100)
    return bs, comments

# ============================================================
#  HP바 / 지갑바 (costume-fill)
# ============================================================
def build_bar_blocks(kind):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    conf = {
        "ahp":  (V_AHP, "아군본진HP", 100, 95, 168),
        "ehp":  (V_EHP, "적본진HP", 100, -95, 168),
        "gold": (V_GOLD, "돈", None, -150, -168),
    }[kind]
    CUR_ID, CUR_NM, MAXVAL, xpos, ypos = conf
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, xpos, ypos); fr = b_front(bs)
    if kind == "gold":
        denom = vrep("돈상한", V_GOLDMAX)
    else:
        denom = MAXVAL
    ratio = op("operator_divide", vrep(CUR_NM, CUR_ID), denom)
    c_zero = b_not(bs, cmp_op("operator_gt", vrep(CUR_NM, CUR_ID), 0))
    set_empty = b_costume_idx(bs, op("operator_add", 0, 1))
    idx = op("operator_add", b_round(bs, op("operator_multiply", ratio, 10)), 1)
    set_fill = b_costume_idx(bs, idx)
    body = b_ifelse(bs, c_zero, set_empty, set_fill)
    w = b_wait(bs, 0.05)
    C(bs, [body, w])
    fe = b_forever(bs, body)
    C(bs, [h, show, g, fr, fe])
    return bs, comments

# ============================================================
#  본부(HQ) 히트박스 — 총알이 touching 으로 때리는 대상. 위치 고정 표시만.
# ============================================================
def build_hq_blocks(side):
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    A = (side == "A")
    ypos = -155 if A else 155
    MYHP = (V_AHP, "아군본진HP") if A else (V_EHP, "적본진HP")
    # 이 타워가 스캔·사격하는 상대 진영 로스터
    L_OX  = (L_EX, "L_적x") if A else (L_AX, "L_아군x")
    L_OY  = (L_EY, "L_적y") if A else (L_AY, "L_아군y")
    L_OACT= (L_EACT, "L_적활성") if A else (L_AACT, "L_아군활성")
    # 타워 사격 = 유닛과 같은 총알 시스템 재사용(자기 진영 발사 채널·방송).
    BFX = (V_ABX, "탄Ax") if A else (V_EBX, "탄Ex")
    BFY = (V_ABY, "탄Ay") if A else (V_EBY, "탄Ey")
    BFDX= (V_ABDX, "탄Adx") if A else (V_EBDX, "탄Edx")
    BFDY= (V_ABDY, "탄Ady") if A else (V_EBDY, "탄Edy")
    BFT = (V_ABTYPE, "탄A종류") if A else (V_EBTYPE, "탄E종류")
    BCNT= (V_ABCNT, "아군총알수") if A else (V_EBCNT, "적총알수")
    FIRE_BR = (BR_AFIRE, "아군발사") if A else (BR_EFIRE, "적발사")

    # ── (A) 깃발: 위치·표시 ──
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = b_show(bs); g = b_gotoxy(bs, 0, ypos); sz = b_setsize(bs, 100); rs = b_rotstyle(bs, "don't rotate")
    cg = b_cleargfx(bs); swc = b_costume(bs, "타워")
    C(bs, [h, show, g, sz, rs, cg, swc])
    add_comment(bs, comments, show,
        "\U0001F3F0★ 방어 타워(HQ). 총알이 이 타워에 touching 하면 타워HP↓(승리조건: 상대 타워 격파).\n"
        "게다가 스스로 방어 포탑: 사거리 안 가장 가까운 적을 throttle 스캔해 주기적으로 사격.",
        x=470, y=20, w=400, h=100)

    # ── (B) 방어 포탑: 게임시작 후 forever — throttle 스캔(상대 로스터 ≤7)해 사거리 안
    #        가장 가까운 적 조준 → 발사쿨마다 총알 발사(유닛보다 느린 쿨=압박용) ──
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # ★ 타워 사거리 = 맵 세로 절반(160). 타워 y=±155 → 중앙(y=0)까지는 닿지만(155<160),
    #   반대편 타워(거리 ~310)에는 절대 못 닿음. 중앙 교전 구역만 커버.
    TURRET_RANGE = 160; TURRET_R2 = TURRET_RANGE * TURRET_RANGE
    set_ft0 = b_setvar(bs, "포탑쿨", V_HQ_FIRET, 0)
    # forever 본체
    # 스캔: 최근거리=큰수, 목표없음, i=1..7 활성 적 중 가장 가까운 것.
    set_best = b_setvar(bs, "포탑최근", V_HQ_BEST, 999999)
    set_nohas = b_setvar(bs, "포탑목표있음", V_HQ_HAS, 0)
    set_i1 = b_setvar(bs, "포탑i", V_HQ_SCANI, 1)
    oact = b_listitem(bs, L_OACT[1], L_OACT[0], vrep("포탑i", V_HQ_SCANI))
    c_alive = cmp_op("operator_equals", oact, 1)
    ox = b_listitem(bs, L_OX[1], L_OX[0], vrep("포탑i", V_HQ_SCANI))
    oy = b_listitem(bs, L_OY[1], L_OY[0], vrep("포탑i", V_HQ_SCANI))
    ddx = op("operator_subtract", ox, b_xpos(bs)); ddy = op("operator_subtract", oy, b_ypos(bs))
    d2 = op("operator_add", op("operator_multiply", ddx, ddx), op("operator_multiply", ddy, ddy))
    ox2 = b_listitem(bs, L_OX[1], L_OX[0], vrep("포탑i", V_HQ_SCANI))
    oy2 = b_listitem(bs, L_OY[1], L_OY[0], vrep("포탑i", V_HQ_SCANI))
    ddx2 = op("operator_subtract", ox2, b_xpos(bs)); ddy2 = op("operator_subtract", oy2, b_ypos(bs))
    d2b = op("operator_add", op("operator_multiply", ddx2, ddx2), op("operator_multiply", ddy2, ddy2))
    c_closer = cmp_op("operator_lt", d2b, vrep("포탑최근", V_HQ_BEST))
    upd_best = b_setvar(bs, "포탑최근", V_HQ_BEST, d2)
    upd_tx = b_setvar(bs, "포탑목표x", V_HQ_TX, b_listitem(bs, L_OX[1], L_OX[0], vrep("포탑i", V_HQ_SCANI)))
    upd_ty = b_setvar(bs, "포탑목표y", V_HQ_TY, b_listitem(bs, L_OY[1], L_OY[0], vrep("포탑i", V_HQ_SCANI)))
    upd_has = b_setvar(bs, "포탑목표있음", V_HQ_HAS, 1)
    C(bs, [upd_best, upd_tx, upd_ty, upd_has])
    if_closer = b_if(bs, c_closer, upd_best)
    if_alive = b_if(bs, c_alive, if_closer)
    inc_i = b_changevar(bs, "포탑i", V_HQ_SCANI, 1)
    C(bs, [if_alive, inc_i])
    rep_scan = b_repeat(bs, 7, if_alive)
    scan_head = set_best  # 스캔 체인(set_best→set_nohas→set_i1→rep_scan)은 아래 전체 루프 체인에서 연결
    # 발사: 포탑쿨<=0 & 목표있음 & 사거리안(포탑최근<=range^2) & 총알수<총알캡 → 발사
    fvx = op("operator_subtract", vrep("포탑목표x", V_HQ_TX), b_xpos(bs))
    fvy = op("operator_subtract", vrep("포탑목표y", V_HQ_TY), b_ypos(bs))
    fdist = b_sqrt(bs, op("operator_add",
              op("operator_multiply",
                 op("operator_subtract", vrep("포탑목표x", V_HQ_TX), b_xpos(bs)),
                 op("operator_subtract", vrep("포탑목표x", V_HQ_TX), b_xpos(bs))),
              op("operator_multiply",
                 op("operator_subtract", vrep("포탑목표y", V_HQ_TY), b_ypos(bs)),
                 op("operator_subtract", vrep("포탑목표y", V_HQ_TY), b_ypos(bs)))))
    set_fd = b_setvar(bs, "포탑최근", V_HQ_BEST, fdist)  # 사거리 판정 후 재사용: 선형 거리로 덮어씀
    safe_fd = op("operator_add", vrep("포탑최근", V_HQ_BEST), 0.001)
    set_bx = b_setvar(bs, BFX[1], BFX[0], b_xpos(bs))
    set_by = b_setvar(bs, BFY[1], BFY[0], b_ypos(bs))
    set_bdx = b_setvar(bs, BFDX[1], BFDX[0], op("operator_divide", fvx, safe_fd))
    set_bdy = b_setvar(bs, BFDY[1], BFDY[0], op("operator_divide", fvy, safe_fd))
    set_bt = b_setvar(bs, BFT[1], BFT[0], 0)  # ★ 타워탄 센티넬=0 → 상대 타워에 딜 없음(타워→타워 금지)
    bc_fire = b_broadcast(bs, FIRE_BR[1], FIRE_BR[0])
    pew = b_playsound(bs, "pew")
    set_ftcd = b_setvar(bs, "포탑쿨", V_HQ_FIRET, 40)  # 유닛보다 훨씬 느린 쿨(≈1.6s 루프기준) — 압박용, 벽 아님
    C(bs, [set_fd, set_bx, set_by, set_bdx, set_bdy, set_bt, bc_fire, pew, set_ftcd])
    c_ftcd = b_not(bs, cmp_op("operator_gt", vrep("포탑쿨", V_HQ_FIRET), 0))
    c_hastgt = cmp_op("operator_gt", vrep("포탑목표있음", V_HQ_HAS), 0)
    c_room = cmp_op("operator_lt", vrep(BCNT[1], BCNT[0]), vrep("총알캡", V_BULLETCAP))
    c_inrng = b_not(bs, cmp_op("operator_gt", vrep("포탑최근", V_HQ_BEST), TURRET_R2))
    c_fire = bool_op("operator_and", bool_op("operator_and", c_ftcd, c_hastgt), bool_op("operator_and", c_room, c_inrng))
    if_fire = b_if(bs, c_fire, set_fd)
    dec_ft = b_changevar(bs, "포탑쿨", V_HQ_FIRET, -1)
    c_ftpos = cmp_op("operator_gt", vrep("포탑쿨", V_HQ_FIRET), 0)
    if_ftdec = b_if(bs, c_ftpos, dec_ft)
    # 루프 1회 = 스캔(set_best→...→rep_scan) → 발사판정(if_fire) → 쿨감소(if_ftdec) 를 한 체인으로.
    C(bs, [set_best, set_nohas, set_i1, rep_scan, if_fire, if_ftdec])
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    if_play = b_if(bs, c_play, scan_head)
    w_t = b_wait(bs, 0.04)
    C(bs, [if_play, w_t])
    fe_t = b_forever(bs, if_play)
    C(bs, [hb, set_ft0, fe_t])
    add_comment(bs, comments, scan_head,
        "\U0001F52B★ 방어 포탑 AI: 상대 로스터(≤7) 를 throttle(0.04s 루프+발사쿨) 스캔해 사거리 안\n"
        "가장 가까운 적을 조준, 유닛보다 느린 쿨로 총알 발사(유닛과 같은 총알 시스템 재사용).\n"
        "→ 타워로 돌진하는 유닛이 반격을 받아 공성에 깊이가 생김. 총알캡150·전체클론 안전 안.",
        x=470, y=200, w=440, h=140)

    # ── (C) 게임끝: 내가 격파된 타워면(내HP≤0) 폭발 연출 후 숨김 ──
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=20, y=560,
        fields={"BROADCAST_OPTION": ["게임끝", BR_END]})
    c_dead = b_not(bs, cmp_op("operator_gt", vrep(MYHP[1], MYHP[0]), 0))
    # 폭발: 3프레임 확장 + boom 사운드 → 숨김
    boom = b_playsound(bs, "boom")
    sz_b = b_setsize(bs, 100); e1 = b_costume(bs, "폭발1"); w1 = b_wait(bs, 0.06)
    e2 = b_costume(bs, "폭발2"); sz2 = b_changesize(bs, 30); w2 = b_wait(bs, 0.06)
    e3 = b_costume(bs, "폭발3"); sz3 = b_changesize(bs, 40); w3 = b_wait(bs, 0.08)
    gh = b_seteffect(bs, "GHOST", 60); w4 = b_wait(bs, 0.08); hide = b_hide(bs)
    C(bs, [boom, sz_b, e1, w1, e2, sz2, w2, e3, sz3, w3, gh, w4, hide])
    if_dead = b_if(bs, c_dead, boom)
    C(bs, [hc, if_dead])
    add_comment(bs, comments, boom,
        "\U0001F4A5★ 타워 격파 연출: 내 타워HP≤0(게임끝) 이면 확장 파이어볼 3프레임 + '쾅' 폭발음 후 숨김.\n"
        "그 뒤 결과배너(승/패)로 이어짐.",
        x=470, y=560, w=400, h=100)
    return bs, comments

# ============================================================
#  결과 배너 (승/패)
# ============================================================
def build_banner_blocks():
    bs = {}; comments = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = b_hide(bs); g = b_gotoxy(bs, 0, 0); sz = b_setsize(bs, 100); fr = b_front(bs)
    C(bs, [h, hi, g, sz, fr])
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임끝", BR_END]})
    c_win = b_not(bs, cmp_op("operator_gt", vrep("적본진HP", V_EHP), 0))
    sw_win = b_costume(bs, "승리"); sw_lose = b_costume(bs, "패배")
    if_res = b_ifelse(bs, c_win, sw_win, sw_lose)
    fr2 = b_front(bs); show = b_show(bs)
    C(bs, [hb, if_res, fr2, show])
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
    a_ri = save_svg(A_RIFLE); a_ri_f = save_svg(A_RIFLE_F); a_mg = save_svg(A_MG); a_mg_f = save_svg(A_MG_F); a_sn = save_svg(A_SNIPER); a_sn_f = save_svg(A_SNIPER_F)
    e_ri = save_svg(E_RIFLE); e_ri_f = save_svg(E_RIFLE_F); e_mg = save_svg(E_MG); e_mg_f = save_svg(E_MG_F); e_sn = save_svg(E_SNIPER); e_sn_f = save_svg(E_SNIPER_F)
    pop_md5 = save_svg(POP_SVG)
    abul = save_svg(A_BULLET); ebul = save_svg(E_BULLET)
    dmg_lo = save_svg(DMG_LOW); dmg_mi = save_svg(DMG_MID); dmg_hi = save_svg(DMG_HIGH)
    bri_sel = save_svg(BTN_RIFLE_SEL); bri_on = save_svg(BTN_RIFLE_ON); bri_off = save_svg(BTN_RIFLE_OFF)
    bmg_sel = save_svg(BTN_MG_SEL); bmg_on = save_svg(BTN_MG_ON); bmg_off = save_svg(BTN_MG_OFF)
    bsn_sel = save_svg(BTN_SNIPE_SEL); bsn_on = save_svg(BTN_SNIPE_ON); bsn_off = save_svg(BTN_SNIPE_OFF)
    ahp_md5 = [save_svg(s) for s in AHP_BARS]; ehp_md5 = [save_svg(s) for s in EHP_BARS]; gold_md5 = [save_svg(s) for s in GOLD_BARS]
    win_md5 = save_svg(WIN_SVG); lose_md5 = save_svg(LOSE_SVG)
    ahq_md5 = save_svg(A_HQ); ehq_md5 = save_svg(E_HQ)
    boom1 = save_svg(BOOM1); boom2 = save_svg(BOOM2); boom3 = save_svg(BOOM3)
    skair_on = save_svg(SK_AIR_ON); skair_off = save_svg(SK_AIR_OFF)
    sksup_on = save_svg(SK_SUP_ON); sksup_off = save_svg(SK_SUP_OFF)
    skchg_on = save_svg(SK_CHG_ON); skchg_off = save_svg(SK_CHG_OFF)
    blast1 = save_svg(BLAST1); blast2 = save_svg(BLAST2); blast3 = save_svg(BLAST3)

    if not os.path.exists(ASSETS): os.makedirs(ASSETS)
    def save_wav(name, samples):
        b = _wav_bytes(samples)
        with open(f"{ASSETS}/{name}.wav", "wb") as f: f.write(b)
        m = md5_bytes(b)
        with open(f"{WORK}/{m}.wav", "wb") as f: f.write(b)
        return m, len(samples)
    pop_s, pop_n = save_wav("pop", synth_pop()); pew_s, pew_n = save_wav("pew", synth_pew())
    tick_s, tick_n = save_wav("tick", synth_tick()); crack_s, crack_n = save_wav("crack", synth_crack())
    boom_s, boom_n = save_wav("boom", synth_boom())
    def snd(name, md5, n):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "", "rate": SND_RATE, "sampleCount": n, "md5ext": f"{md5}.wav"}
    def cos(name, md5, rx=23, ry=23):
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg", "assetId": md5, "md5ext": f"{md5}.svg", "rotationCenterX": rx, "rotationCenterY": ry}

    stage_b, stage_c = build_stage_blocks()
    aunit_b, aunit_c = build_unit_blocks("A")
    eunit_b, eunit_c = build_unit_blocks("E")
    abul_b, abul_c = build_bullet_blocks("A")
    ebul_b, ebul_c = build_bullet_blocks("E")
    popup_b, popup_c = build_popup_blocks()
    bri_b, bri_c = build_button_blocks("rifle")
    bmg_b, bmg_c = build_button_blocks("mg")
    bsn_b, bsn_c = build_button_blocks("snipe")
    skair_b, skair_c = build_skill_button_blocks("air")
    sksup_b, sksup_c = build_skill_button_blocks("supply")
    skchg_b, skchg_c = build_skill_button_blocks("charge")
    skproc_b, skproc_c = build_skillproc_blocks()
    ahp_b, ahp_c = build_bar_blocks("ahp")
    ehp_b, ehp_c = build_bar_blocks("ehp")
    gold_b, gold_c = build_bar_blocks("gold")
    ahq_b, ahq_c = build_hq_blocks("A")
    ehq_b, ehq_c = build_hq_blocks("E")
    ban_b, ban_c = build_banner_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_GOLD:["돈",40], V_GOLDMAX:["돈상한",200], V_GOLDRATE:["돈충전율",9],
            V_UNITCAP:["유닛캡",7], V_BULLETCAP:["총알캡",150],
            V_POPCAP:["팝업캡",20], V_POPCNT:["팝업수",0],
            V_AHP:["아군본진HP",100], V_EHP:["적본진HP",100], V_BASEDMG:["본진딜",5],
            V_ESPAWNGAP:["적스폰간격",2.2], V_ESPAWNT:["적스폰타이머",1.5],
            V_ALLYY:["아군진y",ALLY_Y], V_ENEMYY:["적진y",ENEMY_Y],
            V_ACNT:["아군수",0], V_ECNT:["적수",0], V_ABCNT:["아군총알수",0], V_EBCNT:["적총알수",0],
            V_STATE:["게임상태",1],
            V_C_RIFLE:["소총_코스트",30], V_C_MG:["제압_코스트",55], V_C_SNIPE:["저격_코스트",50],
            V_CD_RIFLE:["소총_소환쿨",25], V_CD_MG:["제압_소환쿨",70], V_CD_SNIPE:["저격_소환쿨",80],
            V_CDT_RIFLE:["소총_쿨타이머",0], V_CDT_MG:["제압_쿨타이머",0], V_CDT_SNIPE:["저격_쿨타이머",0],
            V_PENDTYPE:["대기소환종류",0], V_SPTYPE:["소환종류",0], V_ESPTYPE:["적소환종류",0],
            V_POPX:["팝업x",0], V_POPY:["팝업y",0], V_POPVAL:["팝업값",1],
            V_ABX:["탄Ax",0], V_ABY:["탄Ay",0], V_ABDX:["탄Adx",0], V_ABDY:["탄Ady",1], V_ABTYPE:["탄A종류",1],
            V_EBX:["탄Ex",0], V_EBY:["탄Ey",0], V_EBDX:["탄Edx",0], V_EBDY:["탄Edy",-1], V_EBTYPE:["탄E종류",1],
            V_SK_AIR_C:["포격_코스트",110], V_SK_AIR_T:["포격_쿨타이머",0], V_SK_AIR_CD:["포격_쿨",400],
            V_SK_SUP_C:["보급_코스트",70], V_SK_SUP_T:["보급_쿨타이머",0], V_SK_SUP_CD:["보급_쿨",300],
            V_SK_CHG_C:["돌격_코스트",80], V_SK_CHG_T:["돌격_쿨타이머",0], V_SK_CHG_CD:["돌격_쿨",500],
            V_STRIKEX:["타격x",0], V_STRIKEY:["타격y",0], V_STRIKER:["타격반경",70], V_STRIKED:["타격딜",14],
            V_CHGBUFF:["돌격버프",0],
        },
        "lists": {
            L_AX:["L_아군x",[0]*7], L_AY:["L_아군y",[ALLY_Y]*7], L_AHPL:["L_아군hp",[0]*7], L_AACT:["L_아군활성",[0]*7],
            L_EX:["L_적x",[0]*7], L_EY:["L_적y",[ENEMY_Y]*7], L_EHPL:["L_적hp",[0]*7], L_EACT:["L_적활성",[0]*7],
        },
        "broadcasts": {
            BR_START:"게임시작", BR_ASPAWN:"아군소환", BR_ESPAWN:"적소환",
            BR_AFIRE:"아군발사", BR_EFIRE:"적발사", BR_POP:"팝업요청", BR_END:"게임끝",
            BR_AIR:"포격", BR_SUP:"보급", BR_CHG:"돌격", BR_STRIKE:"광역타격",
        },
        "blocks": stage_b, "comments": stage_c, "currentCostume": 0,
        "costumes": [{"name":"전장","dataFormat":"svg","assetId":bg_md5,"md5ext":f"{bg_md5}.svg","rotationCenterX":240,"rotationCenterY":180}],
        "sounds": [snd("pop", pop_s, pop_n), snd("pew", pew_s, pew_n), snd("tick", tick_s, tick_n), snd("crack", crack_s, crack_n)],
        "volume":100,"layerOrder":0,"tempo":60,"videoTransparency":50,"videoState":"on","textToSpeechLanguage":None
    }
    def unit_target(name, blocks, cmts, costumes, order):
        return {"isStage": False, "name": name,
                "variables": {V_ISC:["복제됨",0], V_TYPE:["내종류",1], V_HP:["내HP",20], V_MAXHP:["내최대HP",20],
                              V_RNG:["내사거리",110], V_SPD:["내속도",2], V_SLOT:["내슬롯",1],
                              V_REAIMT:["재조준타이머",0], V_FIRET:["발사쿨",0], V_TGTX:["목표x",0], V_TGTY:["목표y",0],
                              V_HASTGT:["목표있음",0], V_SCANI:["스캔i",1], V_BESTD:["최근거리",0]},
                "lists": {}, "broadcasts": {}, "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": costumes, "sounds": [snd("pew", pew_s, pew_n), snd("crack", crack_s, crack_n)],
                "volume":100,"layerOrder":order,"visible":False,"x":0,"y":0,"size":85,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    aunit = unit_target("아군유닛", aunit_b, aunit_c,
        [cos("아소총", a_ri), cos("아소총F", a_ri_f), cos("아제압", a_mg), cos("아제압F", a_mg_f),
         cos("아저격", a_sn), cos("아저격F", a_sn_f), cos("아팝", pop_md5)], 1)
    eunit = unit_target("적유닛", eunit_b, eunit_c,
        [cos("적소총", e_ri), cos("적소총F", e_ri_f), cos("적제압", e_mg), cos("적제압F", e_mg_f),
         cos("적저격", e_sn), cos("적저격F", e_sn_f), cos("적팝", pop_md5)], 2)
    def bullet_target(name, blocks, cmts, md5, order):
        return {"isStage": False, "name": name,
                "variables": {V_B_ISC:["복제됨",0], V_BDX:["b_dx",0], V_BDY:["b_dy",1], V_BLIFE:["b_life",0]},
                "lists": {}, "broadcasts": {}, "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos(name.replace("총알","탄"), md5, 6, 6)],
                "sounds": [],
                "volume":100,"layerOrder":order,"visible":False,"x":0,"y":0,"size":60,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    abullet = bullet_target("아군총알", abul_b, abul_c, abul, 3)
    ebullet = bullet_target("적총알", ebul_b, ebul_c, ebul, 4)
    popup = {"isStage": False, "name": "데미지팝업",
             "variables": {V_B_ISC:["복제됨",0]},
             "lists": {}, "broadcasts": {}, "blocks": popup_b, "comments": popup_c, "currentCostume": 0,
             "costumes": [cos("약", dmg_lo, 22, 15), cos("중", dmg_mi, 22, 15), cos("강", dmg_hi, 22, 15)],
             "sounds": [snd("tick", tick_s, tick_n)],
             "volume":100,"layerOrder":5,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    def button_target(name, blocks, cmts, sel, on, off, x, y, order):
        return {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 1,
                "costumes": [cos(name+"Sel", sel, 46, 20), cos(name+"On", on, 46, 20), cos(name+"Off", off, 46, 20)],
                "sounds": [snd("pop", pop_s, pop_n)],
                "volume":100,"layerOrder":order,"visible":True,"x":x,"y":y,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    bri = button_target("버튼소총", bri_b, bri_c, bri_sel, bri_on, bri_off, 188, 120, 6)
    bmg = button_target("버튼제압", bmg_b, bmg_c, bmg_sel, bmg_on, bmg_off, 188, 65, 7)
    bsn = button_target("버튼저격", bsn_b, bsn_c, bsn_sel, bsn_on, bsn_off, 188, 10, 8)
    def skbtn_target(name, blocks, cmts, on, off, x, order):
        return {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos(name+"On", on, 36, 16), cos(name+"Off", off, 36, 16)],
                "sounds": [snd("pop", pop_s, pop_n)],
                "volume":100,"layerOrder":order,"visible":True,"x":x,"y":-165,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    skair = skbtn_target("스킬포격", skair_b, skair_c, skair_on, skair_off, -10, 13)
    sksup = skbtn_target("스킬보급", sksup_b, sksup_c, sksup_on, sksup_off, 70, 14)
    skchg = skbtn_target("스킬돌격", skchg_b, skchg_c, skchg_on, skchg_off, 150, 15)
    skproc = {"isStage": False, "name": "스킬처리",
              "variables": {V_SK_ISC:["복제됨",0], V_SK_I:["스킬i",1], V_SK_SX:["합계x",0], V_SK_SY:["합계y",0], V_SK_N:["표본수",0]},
              "lists": {}, "broadcasts": {}, "blocks": skproc_b, "comments": skproc_c, "currentCostume": 0,
              "costumes": [cos("폭발A", blast1, 80, 80), cos("폭발B", blast2, 80, 80), cos("폭발C", blast3, 80, 80)],
              "sounds": [snd("crack", crack_s, crack_n)],
              "volume":100,"layerOrder":11,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    def bar_target(name, blocks, cmts, md5s, x, y, order):
        return {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos(f"{name}_{i}", md5s[i], 85, 10) for i in range(11)], "sounds": [],
                "volume":100,"layerOrder":order,"visible":True,"x":x,"y":y,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    ahpbar = bar_target("아군본진바", ahp_b, ahp_c, ahp_md5, 95, 168, 9)
    ehpbar = bar_target("적본진바", ehp_b, ehp_c, ehp_md5, -95, 168, 9)
    goldbar = bar_target("지갑바", gold_b, gold_c, gold_md5, -150, -168, 9)
    def hq_target(name, blocks, cmts, md5, y, order):
        return {"isStage": False, "name": name,
                "variables": {V_HQ_SCANI:["포탑i",1], V_HQ_BEST:["포탑최근",0], V_HQ_TX:["포탑목표x",0],
                              V_HQ_TY:["포탑목표y",0], V_HQ_HAS:["포탑목표있음",0], V_HQ_FIRET:["포탑쿨",0]},
                "lists": {}, "broadcasts": {},
                "blocks": blocks, "comments": cmts, "currentCostume": 0,
                "costumes": [cos("타워", md5, 37, 32),
                             cos("폭발1", boom1, 60, 60), cos("폭발2", boom2, 60, 60), cos("폭발3", boom3, 60, 60)],
                "sounds": [snd("pew", pew_s, pew_n), snd("boom", boom_s, boom_n)],
                "volume":100,"layerOrder":order,"visible":True,"x":0,"y":y,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"}
    ahq = hq_target("아군본부", ahq_b, ahq_c, ahq_md5, -155, 1)
    ehq = hq_target("적본부", ehq_b, ehq_c, ehq_md5, 155, 1)
    banner = {
        "isStage": False, "name": "결과배너", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": ban_b, "comments": ban_c, "currentCostume": 0,
        "costumes": [{"name":"승리","bitmapResolution":1,"dataFormat":"svg","assetId":win_md5,"md5ext":f"{win_md5}.svg","rotationCenterX":180,"rotationCenterY":70},
                     {"name":"패배","bitmapResolution":1,"dataFormat":"svg","assetId":lose_md5,"md5ext":f"{lose_md5}.svg","rotationCenterX":180,"rotationCenterY":70}],
        "sounds": [], "volume":100,"layerOrder":12,"visible":False,"x":0,"y":0,"size":100,"direction":90,"draggable":False,"rotationStyle":"don't rotate"
    }

    monitors = [
        {"id": V_GOLD, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"돈"},"spriteName":None,
         "value":40,"width":0,"height":0,"x":5,"y":5,"visible":True,"sliderMin":0,"sliderMax":200,"isDiscrete":True},
        {"id": V_ACNT, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"아군수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":30,"visible":True,"sliderMin":0,"sliderMax":7,"isDiscrete":True},
        {"id": V_ECNT, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"적수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":55,"visible":True,"sliderMin":0,"sliderMax":7,"isDiscrete":True},
        {"id": V_ABCNT, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"아군총알수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":80,"visible":True,"sliderMin":0,"sliderMax":150,"isDiscrete":True},
        {"id": V_POPCNT, "mode":"default","opcode":"data_variable","params":{"VARIABLE":"팝업수"},"spriteName":None,
         "value":0,"width":0,"height":0,"x":5,"y":105,"visible":True,"sliderMin":0,"sliderMax":20,"isDiscrete":True},
    ]
    project = {
        "targets": [stage, ahq, ehq, aunit, eunit, abullet, ebullet, popup, skproc, bri, bmg, bsn, skair, sksup, skchg, ahpbar, ehpbar, goldbar, banner],
        "monitors": monitors, "extensions": [],
        "meta": {"semver":"3.0.0","vm":"13.7.4-svg","agent":"skirmish-builder"}
    }
    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f: json.dump(project, f, ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK): zf.write(f"{WORK}/{fn}", fn)
    with open(pj, "r", encoding="utf-8") as f: json.load(f)
    total = 0
    print(f"wrote {OUTPUT}")
    for nm, b in [("stage",stage_b),("아군유닛",aunit_b),("적유닛",eunit_b),("아군총알",abul_b),("적총알",ebul_b),
                  ("데미지팝업",popup_b),("버튼소총",bri_b),("버튼제압",bmg_b),("버튼저격",bsn_b),
                  ("아군본진바",ahp_b),("적본진바",ehp_b),("지갑바",gold_b),("아군본부",ahq_b),("적본부",ehq_b),("결과배너",ban_b)]:
        print(f"  {nm:8s}: {len(b)} blocks"); total += len(b)
    print(f"  총 블록 수: {total}")

if __name__ == "__main__":
    main()
