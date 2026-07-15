#!/usr/bin/env python3
"""로봇 슈터 (robot-shooter) — 탑뷰 아레나 · 자동 미사일 · 화력 로그라이크.

마법 생존처럼 조준은 자동(가장 가까운 적), 플레이어는 이동만.
기본 무기: 미사일 자동 연사. 강화로 레이저 보조무기 해금/강화.
스킬: Z 메가빔 / X 폭탄 (쿨타임).
웨이브 클리어 시 강화 풀에서 랜덤 3장 중 택1.
"""
import json, os, zipfile, shutil, hashlib, math, struct, random

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "로봇_슈터.sb3")

SND_RATE = 22050  # 조금 더 또렷한 메카 톤

def _wav_bytes(samples, rate=SND_RATE):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    n = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", n) + pcm)

def _clamp(s):
    return max(-1.0, min(1.0, s))

def synth_missile(rate=SND_RATE):
    """미사일 — 중저음 추진 (장난감 뿅 금지, 산업용 로켓)."""
    N = int(rate * 0.11); out = []
    rng = random.Random(91001)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 14) * (1 - math.exp(-t * 70))
        white = rng.random() * 2 - 1
        lp = lp + 0.42 * (white - lp)
        f = 55 + 140 * math.exp(-t * 11)
        body = math.sin(2 * math.pi * f * t) + 0.4 * math.sin(2 * math.pi * f * 2.1 * t)
        grit = lp * 0.55
        out.append(_clamp((body * 0.7 + grit) * env * 0.72))
    return out

def synth_laser(rate=SND_RATE):
    """레이저 — 낮은 공업 빔 (고음 삑 제거)."""
    N = int(rate * 0.10); out = []
    phase = 0.0
    for i in range(N):
        t = i / rate
        f = 520 * math.exp(-t * 14) + 90
        phase += 2 * math.pi * f / rate
        saw = (phase / (2 * math.pi) % 1) * 2 - 1
        sine = math.sin(phase)
        env = math.exp(-t * 16) * (1 - math.exp(-t * 80))
        sub = 0.4 * math.sin(2 * math.pi * 70 * t)
        out.append(_clamp((saw * 0.35 + sine * 0.4 + sub) * env * 0.58))
    return out

def synth_mega(rate=SND_RATE):
    """메가빔 — 중장비 빔 포 (장전 rumble → 발사)."""
    N = int(rate * 0.32); out = []
    phase = 0.0
    rng = random.Random(91003)
    lp = 0.0
    for i in range(N):
        t = i / rate
        if t < 0.10:
            f = 60 + 180 * (t / 0.10)
            env = 0.45 * (t / 0.10)
            white = rng.random() * 2 - 1
            lp = lp + 0.3 * (white - lp)
            s = math.sin(2 * math.pi * f * t) * 0.5 + lp * 0.5
        else:
            u = t - 0.10
            f = 280 * math.exp(-u * 5) + 45
            env = math.exp(-u * 7)
            phase += 2 * math.pi * f / rate
            white = rng.random() * 2 - 1
            lp = lp + 0.25 * (white - lp)
            s = math.sin(phase) * 0.45 + math.sin(phase * 1.5) * 0.25 + lp * 0.35
            s += 0.45 * math.sin(2 * math.pi * 40 * t)
        out.append(_clamp(s * env * 0.7))
    return out

def synth_boom(rate=SND_RATE):
    """중폭발 — 산업 충격파."""
    N = int(rate * 0.30); out = []
    rng = random.Random(20260715)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 7.5)
        white = rng.random() * 2 - 1
        lp = lp + 0.28 * (white - lp)
        thump = math.sin(2 * math.pi * (36 + 55 * math.exp(-t * 12)) * t)
        out.append(_clamp((lp * 0.55 + thump * 0.8) * env * 0.88))
    return out

def synth_bomb_boom(rate=SND_RATE):
    """폭탄 폭발 — 장약 폭발 (길고 무겁게)."""
    N = int(rate * 0.45); out = []
    rng = random.Random(77701)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 5.2)
        white = rng.random() * 2 - 1
        lp = lp + 0.22 * (white - lp)
        thump = math.sin(2 * math.pi * (28 + 75 * math.exp(-t * 9)) * t)
        shock = math.sin(2 * math.pi * (90 + 200 * math.exp(-t * 15)) * t) * math.exp(-t * 12)
        out.append(_clamp((lp * 0.6 + thump * 0.85 + shock * 0.2) * env * 0.92))
    return out

def synth_hurt(rate=SND_RATE):
    """피격 — 장갑 충격 (비프 알람 제거)."""
    N = int(rate * 0.15); out = []
    rng = random.Random(44002)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 12)
        white = rng.random() * 2 - 1
        lp = lp + 0.5 * (white - lp)
        body = math.sin(2 * math.pi * (70 + 40 * math.exp(-t * 18)) * t)
        out.append(_clamp((lp * 0.45 + body * 0.7) * env * 0.7))
    return out

def synth_boss_fire(rate=SND_RATE):
    """보스 캐논 — 함포급 저음."""
    N = int(rate * 0.16); out = []
    rng = random.Random(33002)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 12) * (1 - math.exp(-t * 55))
        white = rng.random() * 2 - 1
        lp = lp + 0.38 * (white - lp)
        f = 42 + 110 * math.exp(-t * 15)
        body = math.sin(2 * math.pi * f * t) + 0.45 * math.sin(2 * math.pi * f * 1.8 * t)
        out.append(_clamp((lp * 0.4 + body * 0.75) * env * 0.8))
    return out

def synth_explode(rate=SND_RATE):
    """격파 — 장갑 파열."""
    N = int(rate * 0.26); out = []
    rng = random.Random(55003)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 8.5)
        white = rng.random() * 2 - 1
        lp = lp + 0.32 * (white - lp)
        thump = math.sin(2 * math.pi * (48 + 80 * math.exp(-t * 14)) * t)
        out.append(_clamp((lp * 0.55 + thump * 0.7) * env * 0.85))
    return out

def synth_bomb_throw(rate=SND_RATE):
    """폭탄 투척 — 기계 투출 (휘익 장난감 톤 제거)."""
    N = int(rate * 0.11); out = []
    rng = random.Random(66004)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 12) * (1 - math.exp(-t * 50))
        white = rng.random() * 2 - 1
        lp = lp + 0.45 * (white - lp)
        f = 100 + 90 * (t / 0.11)
        body = math.sin(2 * math.pi * f * t)
        out.append(_clamp((body * 0.45 + lp * 0.5) * env * 0.5))
    return out

def synth_hit(rate=SND_RATE):
    """피격 타격 — 중장갑 타격 (챙! 고음 제거, 둔탁)."""
    N = int(rate * 0.08); out = []
    rng = random.Random(88011)
    lp = 0.0
    for i in range(N):
        t = i / rate
        env = math.exp(-t * 22) * (1 - math.exp(-t * 150))
        white = rng.random() * 2 - 1
        lp = lp + 0.55 * (white - lp)
        body = math.sin(2 * math.pi * (95 + 60 * math.exp(-t * 30)) * t)
        mid = 0.35 * math.sin(2 * math.pi * (320 * math.exp(-t * 20)) * t)
        out.append(_clamp((lp * 0.5 + body * 0.55 + mid) * env * 0.72))
    return out

def synth_zap(rate=SND_RATE):
    return synth_missile(rate)

# ============================================================
#  SVG
# ============================================================
# 밝은 바닥 — 어두운 기체와 대비
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" fill="#D2DAE4"/>
  <g>
    <rect x="1" y="1" width="38" height="38" fill="#D0D8E2" stroke="#B4BECA" stroke-width="1"/>
  </g>
  <defs>
    <pattern id="tiles" width="40" height="40" patternUnits="userSpaceOnUse">
      <rect width="40" height="40" fill="#C8D2DC"/>
      <rect x="1" y="1" width="38" height="38" fill="#D4DCE6" stroke="#B0BAC8" stroke-width="1"/>
      <circle cx="20" cy="20" r="2" fill="#A0AAB8"/>
    </pattern>
  </defs>
  <rect width="480" height="360" fill="url(#tiles)"/>
  <rect x="2" y="2" width="476" height="356" fill="none" stroke="#9AA8B8" stroke-width="3"/>
  <text x="240" y="28" text-anchor="middle" fill="#6A7A8A" font-family="Arial, sans-serif" font-size="13">MECHA ARENA · AUTO MISSILE</text>
</svg>"""

PLAYER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 56 56">
  <ellipse cx="28" cy="50" rx="14" ry="3.5" fill="#000" opacity="0.35"/>
  <rect x="14" y="36" width="10" height="12" rx="2" fill="#1565C0" stroke="#0D47A1" stroke-width="1.5"/>
  <rect x="32" y="36" width="10" height="12" rx="2" fill="#1565C0" stroke="#0D47A1" stroke-width="1.5"/>
  <rect x="12" y="18" width="32" height="22" rx="5" fill="#1E88E5" stroke="#0D47A1" stroke-width="2"/>
  <rect x="18" y="22" width="20" height="10" rx="2" fill="#4FC3F7" opacity="0.85"/>
  <rect x="18" y="6" width="20" height="14" rx="4" fill="#42A5F5" stroke="#0D47A1" stroke-width="2"/>
  <rect x="22" y="9" width="12" height="7" rx="2" fill="#E3F2FD"/>
  <circle cx="28" cy="12.5" r="1.8" fill="#0277BD"/>
  <rect x="40" y="22" width="14" height="6" rx="2" fill="#90CAF9" stroke="#1565C0" stroke-width="1.5"/>
  <rect x="50" y="23.5" width="6" height="3" rx="1" fill="#FFEB3B"/>
  <rect x="2" y="22" width="12" height="6" rx="2" fill="#1565C0" stroke="#0D47A1" stroke-width="1.5"/>
</svg>"""

# 기본 탄환 — 둥근 에너지 오브
MISSILE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="14" fill="#0096C8"/>
  <circle cx="16" cy="16" r="11" fill="#00E5FF"/>
  <circle cx="16" cy="16" r="7" fill="#B0F5FF"/>
  <circle cx="16" cy="16" r="4" fill="#FFFFFF"/>
</svg>"""

ENEMY_LIGHT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">
  <ellipse cx="22" cy="40" rx="11" ry="2.5" fill="#000" opacity="0.3"/>
  <rect x="12" y="28" width="8" height="10" rx="2" fill="#C62828"/>
  <rect x="24" y="28" width="8" height="10" rx="2" fill="#C62828"/>
  <rect x="10" y="14" width="24" height="18" rx="4" fill="#E53935" stroke="#B71C1C" stroke-width="2"/>
  <rect x="14" y="4" width="16" height="12" rx="3" fill="#EF5350" stroke="#B71C1C" stroke-width="1.5"/>
  <rect x="17" y="7" width="10" height="5" rx="1" fill="#FFCDD2"/>
</svg>"""

ENEMY_MID_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="52" height="52" viewBox="0 0 52 52">
  <ellipse cx="26" cy="48" rx="14" ry="3" fill="#000" opacity="0.3"/>
  <rect x="12" y="32" width="10" height="12" rx="2" fill="#6A1B9A"/>
  <rect x="30" y="32" width="10" height="12" rx="2" fill="#6A1B9A"/>
  <rect x="10" y="16" width="32" height="20" rx="5" fill="#8E24AA" stroke="#4A148C" stroke-width="2"/>
  <rect x="16" y="4" width="20" height="14" rx="4" fill="#AB47BC" stroke="#4A148C" stroke-width="2"/>
  <rect x="20" y="8" width="12" height="6" rx="1" fill="#E1BEE7"/>
</svg>"""

ENEMY_HEAVY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <ellipse cx="32" cy="58" rx="18" ry="3.5" fill="#000" opacity="0.35"/>
  <rect x="14" y="40" width="12" height="14" rx="2" fill="#E65100"/>
  <rect x="38" y="40" width="12" height="14" rx="2" fill="#E65100"/>
  <rect x="10" y="20" width="44" height="26" rx="6" fill="#FF6D00" stroke="#BF360C" stroke-width="2.5"/>
  <rect x="18" y="6" width="28" height="16" rx="4" fill="#FF8F00" stroke="#BF360C" stroke-width="2"/>
  <rect x="24" y="10" width="16" height="8" rx="2" fill="#FFE0B2"/>
</svg>"""

def _star_pts(cx, cy, R, r, n, rot=0.0):
    pts = []
    for i in range(2 * n):
        rad = R if i % 2 == 0 else r
        ang = math.pi / n * i + rot
        pts.append(f"{cx + rad*math.cos(ang):.1f},{cy + rad*math.sin(ang):.1f}")
    return " ".join(pts)

EXPLOSION_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30, 30, 29, 12, 12)}" fill="#FF6F00" stroke="#E65100" stroke-width="1"/>
  <polygon points="{_star_pts(30, 30, 21, 8, 12, rot=0.262)}" fill="#FFB300"/>
  <circle cx="30" cy="30" r="12" fill="#FFEB3B"/>
  <circle cx="30" cy="30" r="5" fill="#FFFFFF"/>
</svg>"""

HIT_SPARK_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <polygon points="{_star_pts(24, 24, 22, 7, 8)}" fill="#FFFFFF" stroke="#FFEB3B" stroke-width="1.5"/>
  <polygon points="{_star_pts(24, 24, 14, 4, 8, rot=0.4)}" fill="#FFD54F"/>
  <circle cx="24" cy="24" r="5" fill="#FFFDE7"/>
  <line x1="24" y1="2" x2="24" y2="10" stroke="#FFF" stroke-width="2"/>
  <line x1="24" y1="38" x2="24" y2="46" stroke="#FFF" stroke-width="2"/>
  <line x1="2" y1="24" x2="10" y2="24" stroke="#FFF" stroke-width="2"/>
  <line x1="38" y1="24" x2="46" y2="24" stroke="#FFF" stroke-width="2"/>
</svg>"""

CARD_BANNER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="420" height="50" viewBox="0 0 420 50">
  <rect x="2" y="2" width="416" height="46" rx="10" fill="#0D1B2A" opacity="0.92" stroke="#FF7043" stroke-width="3"/>
  <text x="210" y="32" text-anchor="middle" fill="#FF7043" font-family="Arial, sans-serif" font-size="18" font-weight="bold">WAVE CLEAR! 랜덤 강화 3장 — 1 / 2 / 3</text>
</svg>"""

def _up_card_svg(key, title, sub, color):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="110" height="140" viewBox="0 0 110 140">
  <rect x="3" y="3" width="104" height="134" rx="12" fill="{color}" stroke="#FFFFFF" stroke-width="3"/>
  <text x="55" y="40" text-anchor="middle" fill="#FFF" font-family="Arial, sans-serif" font-size="26" font-weight="bold">{key}</text>
  <text x="55" y="78" text-anchor="middle" fill="#FFF" font-family="Arial, sans-serif" font-size="14" font-weight="bold">{title}</text>
  <text x="55" y="104" text-anchor="middle" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="11" opacity="0.9">{sub}</text>
</svg>"""

# 강화 풀 6종 (랜덤 3장 중 택1)
UP_DEFS = [
    (1, "공격력+", "데미지↑", "#C62828"),
    (2, "연사+", "발사간격↓", "#EF6C00"),
    (3, "여러발+", "미사일 수↑", "#6A1B9A"),
    (4, "관통+", "한 줄 청소", "#1565C0"),
    (5, "레이저+", "보조무기", "#00838F"),
    (6, "스킬쿨-", "Z/X 빨리", "#2E7D32"),
]
UP_CARD_SVGS = {n: _up_card_svg("?", t, s, c) for n, t, s, c in UP_DEFS}

# 보조무기 레이저 — 빨간 에너지 오브
LASER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="14" fill="#8C1414"/>
  <circle cx="16" cy="16" r="11" fill="#DC2828"/>
  <circle cx="16" cy="16" r="7" fill="#FF7864"/>
  <circle cx="16" cy="16" r="4" fill="#FFF0E6"/>
</svg>"""

# Z 메가 — 둥근 레이저 광선 오브
MEGA_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <circle cx="24" cy="24" r="22" fill="#0078C8"/>
  <circle cx="24" cy="24" r="18" fill="#00B4FF"/>
  <circle cx="24" cy="24" r="13" fill="#50DCFF"/>
  <circle cx="24" cy="24" r="8" fill="#B4F5FF"/>
  <circle cx="24" cy="24" r="4" fill="#FFFFFF"/>
</svg>"""

# 메카 스타일 폭탄 (보라/시안/위험 스트라이프)
BOMB_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <circle cx="24" cy="26" r="16" fill="#2A1A40" stroke="#0D0D12" stroke-width="2.5"/>
  <circle cx="24" cy="26" r="13" fill="#4A2C6A"/>
  <path d="M10 26 Q24 14 38 26 Q24 38 10 26" fill="none" stroke="#00E5FF" stroke-width="2"/>
  <rect x="8" y="22" width="32" height="8" rx="2" fill="#FFD600" stroke="#212121" stroke-width="1"/>
  <line x1="12" y1="22" x2="12" y2="30" stroke="#212121" stroke-width="2"/>
  <line x1="18" y1="22" x2="18" y2="30" stroke="#212121" stroke-width="2"/>
  <line x1="24" y1="22" x2="24" y2="30" stroke="#212121" stroke-width="2"/>
  <line x1="30" y1="22" x2="30" y2="30" stroke="#212121" stroke-width="2"/>
  <line x1="36" y1="22" x2="36" y2="30" stroke="#212121" stroke-width="2"/>
  <circle cx="30" cy="20" r="4" fill="#FF1744" stroke="#B71C1C" stroke-width="1"/>
  <circle cx="30" cy="20" r="1.5" fill="#FFFFFF"/>
  <rect x="21" y="8" width="6" height="8" rx="1" fill="#37474F" stroke="#212121" stroke-width="1"/>
  <path d="M24 8 Q30 4 34 6" fill="none" stroke="#FF6D00" stroke-width="2.5"/>
  <circle cx="35" cy="5" r="3.5" fill="#FFEB3B"/>
  <circle cx="35" cy="5" r="1.5" fill="#FF6D00"/>
</svg>"""

BOMB_BOOM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <circle cx="60" cy="60" r="54" fill="none" stroke="#FF6D00" stroke-width="7" opacity="0.9"/>
  <circle cx="60" cy="60" r="40" fill="none" stroke="#FFD600" stroke-width="5" opacity="0.85"/>
  <circle cx="60" cy="60" r="24" fill="#FF9100" opacity="0.45"/>
  <circle cx="60" cy="60" r="10" fill="#FFF59D"/>
  <circle cx="60" cy="60" r="4" fill="#FFFFFF"/>
</svg>"""

# 스킬 아이콘 (하단 UI) — 키보드 키 Z / X 표기 포함
ICON_LASER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <rect x="4" y="4" width="92" height="92" rx="16" fill="#083049" stroke="#00E5FF" stroke-width="4"/>
  <rect x="10" y="10" width="80" height="80" rx="12" fill="#0D47A1"/>
  <!-- mega beam -->
  <rect x="22" y="48" width="48" height="16" rx="8" fill="#FFD600" stroke="#FF6F00" stroke-width="2"/>
  <rect x="26" y="52" width="32" height="8" rx="4" fill="#FFF59D"/>
  <circle cx="75" cy="56" r="12" fill="#FF6F00"/>
  <circle cx="75" cy="56" r="6" fill="#FFFFFF"/>
  <!-- Z key badge -->
  <rect x="14" y="15" width="38" height="34" rx="6" fill="#141414"/>
  <rect x="12" y="12" width="38" height="34" rx="6" fill="#FFFFFF" stroke="#00E5FF" stroke-width="3"/>
  <text x="31" y="37" text-anchor="middle" fill="#0D47A1" font-family="Arial, sans-serif" font-size="26" font-weight="bold">Z</text>
  <text x="50" y="88" text-anchor="middle" fill="#81D4FA" font-family="Arial, sans-serif" font-size="12" font-weight="bold">MEGA</text>
</svg>"""

ICON_BOMB_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <rect x="4" y="4" width="92" height="92" rx="16" fill="#2A1040" stroke="#FF8F00" stroke-width="4"/>
  <rect x="10" y="10" width="80" height="80" rx="12" fill="#4A1A6B"/>
  <!-- mecha grenade -->
  <circle cx="58" cy="52" r="20" fill="#3D2A55" stroke="#1A1028" stroke-width="2"/>
  <circle cx="58" cy="52" r="15" fill="#5E3A8A"/>
  <path d="M42 52 Q58 40 74 52" fill="none" stroke="#00E5FF" stroke-width="2"/>
  <rect x="40" y="48" width="36" height="8" fill="#FFD600"/>
  <circle cx="66" cy="44" r="4" fill="#FF1744"/>
  <!-- X key -->
  <rect x="14" y="15" width="38" height="34" rx="6" fill="#141414"/>
  <rect x="12" y="12" width="38" height="34" rx="6" fill="#FFFFFF" stroke="#FFAB40" stroke-width="3"/>
  <text x="31" y="37" text-anchor="middle" fill="#4A1A6B" font-family="Arial, sans-serif" font-size="26" font-weight="bold">X</text>
  <text x="50" y="88" text-anchor="middle" fill="#FFE0B2" font-family="Arial, sans-serif" font-size="12" font-weight="bold">BOMB</text>
</svg>"""

# 체력 하트 0~5
def _hp_svg(n):
    hearts = ""
    for i in range(5):
        x = 8 + i * 28
        fill = "#E53935" if i < n else "#424242"
        hearts += f'<text x="{x}" y="28" font-size="22">{"♥" if i < n else "♡"}</text>'
        hearts += f'<circle cx="{x+8}" cy="18" r="9" fill="{fill}" stroke="#B71C1C" stroke-width="1"/>'
    # simpler: filled circles as hearts proxy
    hearts = ""
    for i in range(5):
        x = 16 + i * 30
        fill = "#E53935" if i < n else "#455A64"
        hearts += f'<circle cx="{x}" cy="20" r="11" fill="{fill}" stroke="#212121" stroke-width="2"/>'
        if i < n:
            hearts += f'<circle cx="{x-3}" cy="17" r="3" fill="#FFCDD2" opacity="0.8"/>'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40" viewBox="0 0 160 40">
  <rect x="1" y="1" width="158" height="38" rx="8" fill="#0D1B2A" opacity="0.75" stroke="#546E7A" stroke-width="2"/>
  {hearts}
</svg>"""

HP_SVGS = [_hp_svg(n) for n in range(6)]

HUD_PANEL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="70" viewBox="0 0 200 70">
  <rect x="2" y="2" width="196" height="66" rx="10" fill="#0D1B2A" opacity="0.8" stroke="#37474F" stroke-width="2"/>
  <text x="14" y="28" fill="#90A4AE" font-family="Arial" font-size="12">WAVE</text>
  <text x="14" y="54" fill="#90A4AE" font-family="Arial" font-size="12">SCORE</text>
</svg>"""

BOSS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="90" height="80" viewBox="0 0 90 80">
  <ellipse cx="45" cy="74" rx="28" ry="4" fill="#000" opacity="0.35"/>
  <rect x="18" y="28" width="54" height="40" rx="8" fill="#4A148C" stroke="#1A0033" stroke-width="3"/>
  <rect x="28" y="8" width="34" height="26" rx="6" fill="#6A1B9A" stroke="#1A0033" stroke-width="2"/>
  <rect x="34" y="14" width="22" height="12" rx="2" fill="#E1BEE7"/>
  <circle cx="40" cy="20" r="3" fill="#FF1744"/>
  <circle cx="50" cy="20" r="3" fill="#FF1744"/>
  <rect x="4" y="32" width="16" height="14" rx="3" fill="#7B1FA2"/>
  <rect x="70" y="32" width="16" height="14" rx="3" fill="#7B1FA2"/>
  <rect x="72" y="34" width="18" height="8" rx="2" fill="#FF5252"/>
  <text x="45" y="52" text-anchor="middle" fill="#FFD54F" font-family="Arial" font-size="11" font-weight="bold">BOSS</text>
</svg>"""

BOSS_BULLET_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">
  <circle cx="9" cy="9" r="7" fill="#FF1744" stroke="#B71C1C" stroke-width="2"/>
  <circle cx="9" cy="9" r="3" fill="#FFEBEE"/>
</svg>"""

OVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="5" y="5" width="350" height="140" rx="14" fill="#000" opacity="0.9" stroke="#E53935" stroke-width="5"/>
  <text x="180" y="62" text-anchor="middle" fill="#E53935" font-family="Arial, sans-serif" font-size="40" font-weight="bold">GAME OVER</text>
  <text x="180" y="98" text-anchor="middle" fill="#FFF" font-family="Arial, sans-serif" font-size="16">처치 수는 왼쪽 위 점수!</text>
  <text x="180" y="126" text-anchor="middle" fill="#FFCDD2" font-family="Arial, sans-serif" font-size="13">초록 깃발(▶) 다시 도전</text>
</svg>"""

def _digit_svg(d, color="#FF5252", stroke="#B71C1C"):
    """피격 데미지용 빨간 숫자 (기본). 적 피격은 노란 버전 별도."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="36" height="48" viewBox="0 0 36 48">
  <text x="18" y="40" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-size="40" font-weight="bold" fill="{color}" stroke="{stroke}" stroke-width="3.5" paint-order="stroke" stroke-linejoin="round">{d}</text>
</svg>"""

DIGIT_RED = [_digit_svg(d, "#FF5252", "#B71C1C") for d in range(10)]
DIGIT_YEL = [_digit_svg(d, "#FFEB3B", "#E65100") for d in range(10)]
# 코스튬 0-9 빨강(플레이어 피격), 10-19 노랑(적 피격) — 한 스프라이트에 20 코스튬

# ============================================================
#  helpers
# ============================================================
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n):  return [1, [4, str(n)]]
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

# IDs
V_ATK, V_FIREGAP, V_MISSPD, V_PIERCE, V_MULTI = "varAtk01", "varFireGap02", "varMisSpd03", "varPierce04", "varMulti05"
V_MOVE, V_MAXHP, V_HP, V_INV, V_UP = "varMove06", "varMaxHP07", "varHP08", "varInv09", "varUp10"
V_WAVEBASE, V_WAVEADD, V_SPAWNGAP = "varWaveBase11", "varWaveAdd12", "varSpawnGap13"
V_EHPW, V_ESPW, V_EHPM, V_ESPM = "varEHPw14", "varESPw15", "varEHPm16", "varESPm17"
V_EHPS, V_ESPS, V_EHPSCALE, V_ESPSCALE = "varEHPs18", "varESPs19", "varEHPscale20", "varESPscale21"
V_STATE, V_SCORE, V_WAVE, V_TARGET = "varState22", "varScore23", "varWave24", "varTarget25"
V_SPAWNED, V_ALIVE, V_INVT = "varSpawned26", "varAlive27", "varInvT28"
V_FIREX, V_FIREY, V_FIREI = "varFireX30", "varFireY31", "varFireI33"
V_AIMD, V_AIMX, V_AIMY, V_AIMOK = "varAimD40", "varAimX41", "varAimY42", "varAimOK43"
V_SPX, V_SPY, V_SPTYPE, V_EDGE = "varSPX34", "varSPY35", "varSPType36", "varEdge37"
V_DMGVAL, V_DMGX, V_DMGY = "varDmgVal46", "varDmgX47", "varDmgY48"
V_DMGDIGIT, V_DMGOFF, V_DMGLEN, V_DMGPOS = "varDmgDigit49", "varDmgOff50", "varDmgLen51", "varDmgPos52"
V_DMGKIND = "varDmgKind53"  # 0=플레이어피격(빨강), 1=적피격(노랑)
# 무기·스킬·랜덤 강화
V_LASER = "varLaser54"       # 레이저레벨 0=미해금
V_LASERGAP = "varLaserGap55" # 레이저 발사간격
V_SK1CD = "varSk1Cd56"       # 메가빔 쿨 남은 초
V_SK1MAX = "varSk1Max57"     # 메가빔 쿨 최대
V_SK2CD = "varSk2Cd58"       # 폭탄 쿨 남은 초
V_SK2MAX = "varSk2Max59"
V_PULSER = "varPulseR60"     # 폭탄 반경
V_BOMBX = "varBombX68"       # 폭발 좌표 X
V_BOMBY = "varBombY69"       # 폭발 좌표 Y
V_CARD1, V_CARD2, V_CARD3 = "varCard61", "varCard62", "varCard63"  # 랜덤 강화 타입 1~6
V_PICK = "varPick64"         # 고른 슬롯 1~3
V_UPTYPE = "varUpType65"     # 적용할 강화 타입
V_HITDMG = "varHitDmg66"     # 이번 피격 데미지 (적 적용용)
V_TMP2 = "varTmp267"
V_CDGHOST = "varCdGhost70"   # 스킬 아이콘 고스트 계산용
V_PANIM = "varPAnim90"       # 주인공 좌우 방향 1=우 2=좌
V_PFRAME = "varPFrame91"     # 보행 프레임 0=idle 1~4=walk
V_PTICK = "varPTick92"       # 보행 프레임 틱 (느리게 넘김)
V_PMOVING = "varPMoving93"   # 이번 프레임 이동 여부 0/1
V_BOSSMODE = "varBossMode71" # 1=보스 웨이브
V_BOSSHP = "varBossHP72"     # 보스 현재 체력
V_BOSSBASE = "varBossBase73" # 보스 기본 체력
V_BOSSDIR = "varBossDir74"   # 순찰 X 방향 ±1
V_BOSSDIRY = "varBossDirY86" # 순찰 Y 방향 ±1
V_BOSSCD = "varBossCd75"     # 보스 사격 쿨
V_BOSSHIT = "varBossHit76"   # 보스 피격 쿨
V_BBX, V_BBY = "varBBX77", "varBBY78"  # 보스탄 스폰 좌표
V_BBDIR = "varBBDir81"               # 보스탄 발사 방향
V_BBISC = "varBBIsC79"
V_HITFXISC = "varHitFxIsC80"
V_BOSSMULTI = "varBossMulti82"       # 한 번에 쏘는 탄 수
V_BOSSGAP = "varBossGap83"           # 사격 간격
V_BOSSVOLLEY = "varBossVolley84"     # 연사 카운트 (필살기 주기)
V_BOSSFI = "varBossFi85"             # 부채꼴 인덱스

V_MISISC, V_MISPIER, V_MISHITCD = "varMisIsC", "varMisPier", "varMisHitCD"
V_LASISC, V_LASPIER, V_LASHITCD = "varLasIsC", "varLasPier", "varLasHitCD"
V_MEGISC, V_MEGPIER, V_MEGHITCD = "varMegIsC", "varMegPier", "varMegHitCD"
V_PULISC = "varPulIsC"
V_EIS, V_EHP, V_ESPD, V_ETYPE, V_EHIT = "varEnemyIsC", "varEnemyHP", "varEnemySpd", "varEnemyType", "varEnemyHit"
V_DMGISC = "varDmgIsC"

BR_START, BR_AIM, BR_FIRE = "brStart01", "brAim02", "brFire03"
BR_AIMSYNC = "brAimSync16"  # 조준점 스프라이트 좌표 동기화
BR_SPAWN, BR_WAVECLR, BR_NEXT, BR_DMG = "brSpawn03", "brWaveClr04", "brNext06", "brDmg07"
BR_LASER, BR_MEGA, BR_PULSE = "brLaser08", "brMega09", "brPulse10"
BR_BOMBBOOM = "brBombBoom12"  # 폭탄 폭발 (AOE 판정)
BR_CARDUI = "brCardUi11"  # 카드 종류 확정 → 슬롯 코스튬 갱신
BR_BOSS = "brBoss13"      # 보스스폰
BR_BFIRE = "brBFire14"    # 보스사격
BR_HITFX = "brHitFx15"    # 타격 스파크 이펙트

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
    m = gen(); bs[m] = mk("sensing_keyoptions", fields={"KEY_OPTION": [key, None]}, shadow=True)
    p = gen(); bs[p] = mk("sensing_keypressed", inputs={"KEY_OPTION": [1, m]})
    bs[m]["parent"] = p
    return p

def b_switch_costume(bs, name):
    cm = gen(); bs[cm] = mk("looks_costume", fields={"COSTUME": [name, None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm]})
    bs[cm]["parent"] = sw
    return sw

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

def b_wait_var(bs, name, vid):
    v = gen(); bs[v] = mk("data_variable", fields={"VARIABLE": [name, vid]})
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": slot(v)})
    bs[v]["parent"] = bid
    return bid

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

def b_create_clone(bs, target="_myself_"):
    m = gen(); bs[m] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": [target, None]}, shadow=True)
    c = gen(); bs[c] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, m]})
    bs[m]["parent"] = c
    return c

def b_sound(bs, sound="zap"):
    sm = gen(); bs[sm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": [sound, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]})
    bs[sm]["parent"] = sp
    return sp

def b_gotoxy(bs, x, y):
    bid = gen()
    ins = {}
    if isinstance(x, str) and x in bs: ins["X"] = slot(x)
    else: ins["X"] = num(x)
    if isinstance(y, str) and y in bs: ins["Y"] = slot(y)
    else: ins["Y"] = num(y)
    bs[bid] = mk("motion_gotoxy", inputs=ins)
    if isinstance(x, str) and x in bs: bs[x]["parent"] = bid
    if isinstance(y, str) and y in bs: bs[y]["parent"] = bid
    return bid

def b_of(bs, spr, prop):
    m = gen(); bs[m] = mk("sensing_of_object_menu",
        fields={"OBJECT": [spr, None]}, shadow=True)
    bid = gen(); bs[bid] = mk("sensing_of",
        inputs={"OBJECT": [1, m]}, fields={"PROPERTY": [prop, None]})
    bs[m]["parent"] = bid
    return bid

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def add_set(name, vid, val):
        sid = b_setvar(bs, name, vid, val)
        seq.append((sid, bs[sid]))

    # 화력 시작값: 한 발씩, 여유 있는 간격
    add_set("공격력", V_ATK, 1)
    add_set("발사간격", V_FIREGAP, 0.55)
    add_set("미사일속도", V_MISSPD, 10)
    add_set("관통", V_PIERCE, 1)
    add_set("추가발사", V_MULTI, 1)
    add_set("이동속도", V_MOVE, 8)
    add_set("최대체력", V_MAXHP, 5)
    add_set("무적시간", V_INV, 35)
    add_set("강화량", V_UP, 1)
    add_set("웨이브기본수", V_WAVEBASE, 4)
    add_set("웨이브증가", V_WAVEADD, 2)
    add_set("스폰간격", V_SPAWNGAP, 0.85)
    add_set("약한적_체력", V_EHPW, 1)
    add_set("약한적_속도", V_ESPW, 1.25)
    add_set("중간적_체력", V_EHPM, 3)
    add_set("중간적_속도", V_ESPM, 0.95)
    add_set("강한적_체력", V_EHPS, 7)
    add_set("강한적_속도", V_ESPS, 0.65)
    add_set("적체력증가", V_EHPSCALE, 1)
    add_set("적속도증가", V_ESPSCALE, 0.07)
    add_set("레이저레벨", V_LASER, 0)
    add_set("레이저간격", V_LASERGAP, 0.85)
    add_set("메가빔쿨최대", V_SK1MAX, 8)
    add_set("폭탄쿨최대", V_SK2MAX, 10)
    add_set("폭탄반경", V_PULSER, 95)
    add_set("보스기본체력", V_BOSSBASE, 30)

    maxhp = vrep("최대체력", V_MAXHP)
    seq.append((b_setvar(bs, "체력", V_HP, maxhp), None))
    seq[-1] = (seq[-1][0], bs[seq[-1][0]])

    for name, vid, val in [
        ("게임상태", V_STATE, 1), ("점수", V_SCORE, 0), ("웨이브", V_WAVE, 1),
        ("웨이브목표", V_TARGET, 4), ("스폰수", V_SPAWNED, 0), ("적수", V_ALIVE, 0),
        ("무적", V_INVT, 0), ("발사X", V_FIREX, 0), ("발사Y", V_FIREY, 0),
        ("발사i", V_FIREI, 0), ("조준거리", V_AIMD, 99999), ("조준X", V_AIMX, 0),
        ("조준Y", V_AIMY, 0), ("조준있음", V_AIMOK, 0),
        ("적생성X", V_SPX, 0), ("적생성Y", V_SPY, 0), ("적생성종류", V_SPTYPE, 1),
        ("변두리", V_EDGE, 1),
        ("데미지표시값", V_DMGVAL, 0), ("데미지표시x", V_DMGX, 0), ("데미지표시y", V_DMGY, 0),
        ("데미지숫자", V_DMGDIGIT, 0), ("데미지오프셋", V_DMGOFF, 0),
        ("데미지글자수", V_DMGLEN, 0), ("데미지자리", V_DMGPOS, 0), ("데미지종류", V_DMGKIND, 0),
        ("메가빔쿨", V_SK1CD, 0), ("폭탄쿨", V_SK2CD, 0),
        ("폭탄X", V_BOMBX, 0), ("폭탄Y", V_BOMBY, 0),
        ("카드1", V_CARD1, 1), ("카드2", V_CARD2, 2), ("카드3", V_CARD3, 3),
        ("선택슬롯", V_PICK, 0), ("강화타입", V_UPTYPE, 0), ("피격데미지", V_HITDMG, 1),
        ("임시2", V_TMP2, 0), ("쿨고스트", V_CDGHOST, 0),
        ("보스모드", V_BOSSMODE, 0), ("보스체력", V_BOSSHP, 0),
        ("보스방향", V_BOSSDIR, 1), ("보스방향Y", V_BOSSDIRY, 1),
        ("보사쿨", V_BOSSCD, 0), ("보스피격쿨", V_BOSSHIT, 0),
        ("보스탄X", V_BBX, 0), ("보스탄Y", V_BBY, 0), ("보스탄방향", V_BBDIR, 90),
        ("보스탄수", V_BOSSMULTI, 1), ("보스간격", V_BOSSGAP, 0.75),
        ("보볼리", V_BOSSVOLLEY, 0), ("보스발사i", V_BOSSFI, 0),
    ]:
        add_set(name, vid, val)

    # 웨이브 목표 / 보스모드 (1웨이브는 일반)
    def append_set_wave_params(seq_list):
        """웨이브%5==0 → 보스 (목표1). 아니면 일반 목표."""
        mod = op("operator_mod", vrep("웨이브", V_WAVE), 5)
        is_boss = cmp_op("operator_equals", mod, 0)
        # boss branch
        set_bm1 = b_setvar(bs, "보스모드", V_BOSSMODE, 1)
        set_t1 = b_setvar(bs, "웨이브목표", V_TARGET, 1)
        chain([(set_bm1, bs[set_bm1]), (set_t1, bs[set_t1])])
        # normal branch
        set_bm0 = b_setvar(bs, "보스모드", V_BOSSMODE, 0)
        w = vrep("웨이브", V_WAVE)
        tot = op("operator_add", vrep("웨이브기본수", V_WAVEBASE),
                 op("operator_multiply", op("operator_subtract", w, 1), vrep("웨이브증가", V_WAVEADD)))
        set_tn = b_setvar(bs, "웨이브목표", V_TARGET, tot)
        chain([(set_bm0, bs[set_bm0]), (set_tn, bs[set_tn])])
        ifelse = b_ifelse(bs, is_boss, set_bm1, set_bm0)
        seq_list.append((ifelse, bs[ifelse]))
        return ifelse

    append_set_wave_params(seq)
    seq.append((b_broadcast(bs, "게임시작", BR_START), None))
    seq[-1] = (seq[-1][0], bs[seq[-1][0]])
    chain(seq)

    # 스폰 루프
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=480,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    r1 = gen(); bs[r1] = mk("operator_random", inputs={"FROM": num(1), "TO": num(4)})
    s_edge = b_setvar(bs, "변두리", V_EDGE, r1)
    rx = gen(); bs[rx] = mk("operator_random", inputs={"FROM": num(-200), "TO": num(200)})
    ry = gen(); bs[ry] = mk("operator_random", inputs={"FROM": num(-150), "TO": num(150)})
    sx = b_setvar(bs, "적생성X", V_SPX, rx)
    sy = b_setvar(bs, "적생성Y", V_SPY, ry)
    e = vrep("변두리", V_EDGE)
    if1 = b_if(bs, cmp_op("operator_equals", e, 1), b_setvar(bs, "적생성X", V_SPX, -230))
    if2 = b_if(bs, cmp_op("operator_equals", vrep("변두리", V_EDGE), 2), b_setvar(bs, "적생성X", V_SPX, 230))
    if3 = b_if(bs, cmp_op("operator_equals", vrep("변두리", V_EDGE), 3), b_setvar(bs, "적생성Y", V_SPY, 170))
    if4 = b_if(bs, cmp_op("operator_equals", vrep("변두리", V_EDGE), 4), b_setvar(bs, "적생성Y", V_SPY, -170))
    set_t1 = b_setvar(bs, "적생성종류", V_SPTYPE, 1)
    wge3 = cmp_op("operator_gt", vrep("웨이브", V_WAVE), 2)
    rr = gen(); bs[rr] = mk("operator_random", inputs={"FROM": num(1), "TO": num(3)})
    rreq = cmp_op("operator_equals", rr, 1)
    if_mid = b_if(bs, bool_op("operator_and", wge3, rreq), b_setvar(bs, "적생성종류", V_SPTYPE, 2))
    wge5 = cmp_op("operator_gt", vrep("웨이브", V_WAVE), 4)
    rr2 = gen(); bs[rr2] = mk("operator_random", inputs={"FROM": num(1), "TO": num(4)})
    if_h = b_if(bs, bool_op("operator_and", wge5, cmp_op("operator_equals", rr2, 1)),
                b_setvar(bs, "적생성종류", V_SPTYPE, 3))
    brs = b_broadcast(bs, "적스폰", BR_SPAWN)
    ch_s = b_changevar(bs, "스폰수", V_SPAWNED, 1)
    ch_a = b_changevar(bs, "적수", V_ALIVE, 1)
    wt = b_wait_var(bs, "스폰간격", V_SPAWNGAP)
    chain([(s_edge, bs[s_edge]), (sx, bs[sx]), (sy, bs[sy]),
           (if1, bs[if1]), (if2, bs[if2]), (if3, bs[if3]), (if4, bs[if4]),
           (set_t1, bs[set_t1]), (if_mid, bs[if_mid]), (if_h, bs[if_h]),
           (brs, bs[brs]), (ch_s, bs[ch_s]), (ch_a, bs[ch_a]), (wt, bs[wt])])

    # 보스 스폰 (1회)
    br_boss = b_broadcast(bs, "보스스폰", BR_BOSS)
    set_ss1 = b_setvar(bs, "스폰수", V_SPAWNED, 1)
    set_al1 = b_setvar(bs, "적수", V_ALIVE, 1)
    wt_b = b_wait(bs, 0.5)
    chain([(br_boss, bs[br_boss]), (set_ss1, bs[set_ss1]), (set_al1, bs[set_al1]), (wt_b, bs[wt_b])])

    is_boss_m = cmp_op("operator_equals", vrep("보스모드", V_BOSSMODE), 1)
    spawn_body = b_ifelse(bs, is_boss_m, br_boss, s_edge)

    st1 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    less = cmp_op("operator_lt", vrep("스폰수", V_SPAWNED), vrep("웨이브목표", V_TARGET))
    can_spawn = bool_op("operator_and", st1, less)
    wait_idle = b_wait(bs, 0.05)
    ifelse_spawn = b_ifelse(bs, can_spawn, spawn_body, wait_idle)

    st1b = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    lt3 = cmp_op("operator_lt", vrep("스폰수", V_SPAWNED), vrep("웨이브목표", V_TARGET))
    not_lt = gen(); bs[not_lt] = mk("operator_not", inputs={"OPERAND": [2, lt3]})
    bs[lt3]["parent"] = not_lt
    al0 = cmp_op("operator_equals", vrep("적수", V_ALIVE), 0)
    can_clr = bool_op("operator_and", st1b, bool_op("operator_and", not_lt, al0))
    set_st2 = b_setvar(bs, "게임상태", V_STATE, 2)
    br_clr = b_broadcast(bs, "웨이브클리어", BR_WAVECLR)
    chain([(set_st2, bs[set_st2]), (br_clr, bs[br_clr])])
    if_clr = b_if(bs, can_clr, set_st2)
    chain([(ifelse_spawn, bs[ifelse_spawn]), (if_clr, bs[if_clr])])
    fr = b_forever(bs, ifelse_spawn)
    chain([(hb, bs[hb]), (fr, bs[fr])])

    # 다음웨이브
    hn = gen(); bs[hn] = mk("event_whenbroadcastreceived", top=True, x=20, y=980,
        fields={"BROADCAST_OPTION": ["다음웨이브", BR_NEXT]})
    nseq = [(hn, bs[hn])]
    for name, vid, val in [
        (None, None, None),
    ]:
        pass
    nseq.append((b_changevar(bs, "웨이브", V_WAVE, 1), None)); nseq[-1] = (nseq[-1][0], bs[nseq[-1][0]])
    nseq.append((b_setvar(bs, "스폰수", V_SPAWNED, 0), None)); nseq[-1] = (nseq[-1][0], bs[nseq[-1][0]])
    nseq.append((b_setvar(bs, "적수", V_ALIVE, 0), None)); nseq[-1] = (nseq[-1][0], bs[nseq[-1][0]])
    # 웨이브 목표 / 보스모드 재계산
    mod2 = op("operator_mod", vrep("웨이브", V_WAVE), 5)
    is_b2 = cmp_op("operator_equals", mod2, 0)
    set_bm1 = b_setvar(bs, "보스모드", V_BOSSMODE, 1)
    set_t1b = b_setvar(bs, "웨이브목표", V_TARGET, 1)
    chain([(set_bm1, bs[set_bm1]), (set_t1b, bs[set_t1b])])
    set_bm0 = b_setvar(bs, "보스모드", V_BOSSMODE, 0)
    w2 = vrep("웨이브", V_WAVE)
    tot2 = op("operator_add", vrep("웨이브기본수", V_WAVEBASE),
              op("operator_multiply", op("operator_subtract", w2, 1), vrep("웨이브증가", V_WAVEADD)))
    set_tn = b_setvar(bs, "웨이브목표", V_TARGET, tot2)
    chain([(set_bm0, bs[set_bm0]), (set_tn, bs[set_tn])])
    ifelse_w = b_ifelse(bs, is_b2, set_bm1, set_bm0)
    nseq.append((ifelse_w, bs[ifelse_w]))
    nseq.append((b_setvar(bs, "게임상태", V_STATE, 1), None)); nseq[-1] = (nseq[-1][0], bs[nseq[-1][0]])
    chain(nseq)
    return bs

# ============================================================
#  내로봇 — 이동 + 자동 조준 연사 + 피격
# ============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    def text_slot(s):
        return [1, [10, str(s)]]

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = b_gotoxy(bs, 0, 0)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(48)})
    # 회전 없음 — 좌/우 코스튬 + 보행 프레임 사이클
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    sw0 = b_switch_costume(bs, "r0")
    set_dir0 = b_setvar(bs, "이동애니", V_PANIM, 1)  # 1=우 2=좌
    set_fr0 = b_setvar(bs, "보행프레임", V_PFRAME, 0)
    set_tk0 = b_setvar(bs, "보행틱", V_PTICK, 0)
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (rs, bs[rs]),
           (sw0, bs[sw0]), (set_dir0, bs[set_dir0]), (set_fr0, bs[set_fr0]),
           (set_tk0, bs[set_tk0]), (show, bs[show])])

    # (B) 이동 forever — 좌/우 방향 + 4프레임 보행 애니
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    g2 = b_gotoxy(bs, 0, 0)
    show2 = gen(); bs[show2] = mk("looks_show")
    sw0b = b_switch_costume(bs, "r0")
    set_dir0b = b_setvar(bs, "이동애니", V_PANIM, 1)
    set_fr0b = b_setvar(bs, "보행프레임", V_PFRAME, 0)
    set_tk0b = b_setvar(bs, "보행틱", V_PTICK, 0)

    def move_only(key, is_x, positive):
        """상하 이동 — 방향은 유지, 이동중 플래그만 켬."""
        k = b_keypressed(bs, key)
        mv = vrep("이동속도", V_MOVE)
        if positive:
            if is_x:
                ch = gen(); bs[ch] = mk("motion_changexby", inputs={"DX": slot(mv)})
            else:
                ch = gen(); bs[ch] = mk("motion_changeyby", inputs={"DY": slot(mv)})
            bs[mv]["parent"] = ch
        else:
            neg = op("operator_subtract", 0, mv)
            if is_x:
                ch = gen(); bs[ch] = mk("motion_changexby", inputs={"DX": slot(neg)})
            else:
                ch = gen(); bs[ch] = mk("motion_changeyby", inputs={"DY": slot(neg)})
            bs[neg]["parent"] = ch
        set_m = b_setvar(bs, "이동중", V_PMOVING, 1)
        chain([(ch, bs[ch]), (set_m, bs[set_m])])
        return b_if(bs, k, ch)

    def move_and_face_lr(key, positive, face_code):
        """좌우 이동 — 코스튬 방향 + 이동중 플래그."""
        k = b_keypressed(bs, key)
        mv = vrep("이동속도", V_MOVE)
        if positive:
            ch = gen(); bs[ch] = mk("motion_changexby", inputs={"DX": slot(mv)})
            bs[mv]["parent"] = ch
        else:
            neg = op("operator_subtract", 0, mv)
            ch = gen(); bs[ch] = mk("motion_changexby", inputs={"DX": slot(neg)})
            bs[neg]["parent"] = ch
        set_f = b_setvar(bs, "이동애니", V_PANIM, face_code)
        set_m = b_setvar(bs, "이동중", V_PMOVING, 1)
        chain([(ch, bs[ch]), (set_f, bs[set_f]), (set_m, bs[set_m])])
        return b_if(bs, k, ch)

    # 매 틱 시작: 이동중=0 후 키 입력 시 1
    clr_mv = b_setvar(bs, "이동중", V_PMOVING, 0)

    # 좌우: 이동 + 방향 / 상하: 이동만 (보행 애니 공유)
    ir = move_and_face_lr("right arrow", True, 1)
    il = move_and_face_lr("left arrow", False, 2)
    iu = move_only("up arrow", False, True)
    idn = move_only("down arrow", False, False)
    ir2 = move_and_face_lr("d", True, 1)
    il2 = move_and_face_lr("a", False, 2)
    iu2 = move_only("w", False, True)
    idn2 = move_only("s", False, False)

    def clamp(pos_op, set_op, cmp, limit):
        p = gen(); bs[p] = mk(pos_op)
        c = cmp_op(cmp, p, limit)
        st = gen(); bs[st] = mk(set_op, inputs={("X" if "setx" in set_op else "Y"): num(limit)})
        return b_if(bs, c, st)

    cxhi = clamp("motion_xposition", "motion_setx", "operator_gt", 220)
    cxlo = clamp("motion_xposition", "motion_setx", "operator_lt", -220)
    cyhi = clamp("motion_yposition", "motion_sety", "operator_gt", 150)
    cylo = clamp("motion_yposition", "motion_sety", "operator_lt", -150)

    # --- 보행 프레임 사이클 ---
    # 이동중: 틱 2마다 프레임 1→2→3→4→1… / 정지: 프레임 0(idle)
    ch_tick = b_changevar(bs, "보행틱", V_PTICK, 1)
    # if 보행틱 >= 2:
    tick_ge = cmp_op("operator_gt", vrep("보행틱", V_PTICK), 2)  # >=3 (≈0.09s/frame)
    rst_tick = b_setvar(bs, "보행틱", V_PTICK, 0)
    ch_fr = b_changevar(bs, "보행프레임", V_PFRAME, 1)
    # if 보행프레임 > 4 → 1
    fr_hi = cmp_op("operator_gt", vrep("보행프레임", V_PFRAME), 4)
    set_fr1 = b_setvar(bs, "보행프레임", V_PFRAME, 1)
    if_frwrap = b_if(bs, fr_hi, set_fr1)
    # if 프레임 was 0 (just started moving), jump to 1
    fr_was0 = cmp_op("operator_equals", vrep("보행프레임", V_PFRAME), 0)
    set_fr_start = b_setvar(bs, "보행프레임", V_PFRAME, 1)
    if_start = b_if(bs, fr_was0, set_fr_start)
    chain([(rst_tick, bs[rst_tick]), (ch_fr, bs[ch_fr]), (if_frwrap, bs[if_frwrap])])
    if_tick = b_if(bs, tick_ge, rst_tick)
    chain([(ch_tick, bs[ch_tick]), (if_start, bs[if_start]), (if_tick, bs[if_tick])])
    # idle branch
    set_idle_fr = b_setvar(bs, "보행프레임", V_PFRAME, 0)
    set_idle_tk = b_setvar(bs, "보행틱", V_PTICK, 0)
    chain([(set_idle_fr, bs[set_idle_fr]), (set_idle_tk, bs[set_idle_tk])])
    if_anim = b_ifelse(bs, cmp_op("operator_equals", vrep("이동중", V_PMOVING), 1),
                       ch_tick, set_idle_fr)

    # 코스튬 = join (r|l) + 보행프레임  → r0..r4 / l0..l4
    def switch_dir_frame(prefix):
        fv = vrep("보행프레임", V_PFRAME)
        jn = gen()
        bs[jn] = mk("operator_join",
            inputs={"STRING1": text_slot(prefix), "STRING2": slot(fv)})
        bs[fv]["parent"] = jn
        sw = gen(); bs[sw] = mk("looks_switchcostumeto",
            inputs={"COSTUME": [3, jn, [10, f"{prefix}0"]]})
        bs[jn]["parent"] = sw
        return sw

    sw_r = switch_dir_frame("r")
    if_r = b_if(bs, cmp_op("operator_equals", vrep("이동애니", V_PANIM), 1), sw_r)
    sw_l = switch_dir_frame("l")
    if_l = b_if(bs, cmp_op("operator_equals", vrep("이동애니", V_PANIM), 2), sw_l)

    inv = vrep("무적", V_INVT)
    inv_gt = cmp_op("operator_gt", inv, 0)
    ch_inv = b_changevar(bs, "무적", V_INVT, -1)
    if_inv = b_if(bs, inv_gt, ch_inv)
    inv2 = vrep("무적", V_INVT)
    gh = gen(); bs[gh] = mk("looks_seteffectto", inputs={"VALUE": num(45)},
                            fields={"EFFECT": ["GHOST", None]})
    cl = gen(); bs[cl] = mk("looks_seteffectto", inputs={"VALUE": num(0)},
                            fields={"EFFECT": ["GHOST", None]})
    if_gh = b_ifelse(bs, cmp_op("operator_gt", inv2, 0), gh, cl)

    wt = b_wait(bs, 0.03)
    chain([(clr_mv, bs[clr_mv]),
           (ir, bs[ir]), (il, bs[il]), (iu, bs[iu]), (idn, bs[idn]),
           (ir2, bs[ir2]), (il2, bs[il2]), (iu2, bs[iu2]), (idn2, bs[idn2]),
           (cxhi, bs[cxhi]), (cxlo, bs[cxlo]), (cyhi, bs[cyhi]), (cylo, bs[cylo]),
           (if_anim, bs[if_anim]), (if_r, bs[if_r]), (if_l, bs[if_l]),
           (if_inv, bs[if_inv]), (if_gh, bs[if_gh]), (wt, bs[wt])])
    if_play = b_if(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1), clr_mv)
    wsmall = b_wait(bs, 0.01)
    chain([(if_play, bs[if_play]), (wsmall, bs[wsmall])])
    fr = b_forever(bs, if_play)
    chain([(hb, bs[hb]), (g2, bs[g2]), (sw0b, bs[sw0b]), (set_dir0b, bs[set_dir0b]),
           (set_fr0b, bs[set_fr0b]), (set_tk0b, bs[set_tk0b]),
           (show2, bs[show2]), (fr, bs[fr])])

    # (C) 자동 조준 연사 — 마법 생존 패턴
    hc = gen(); bs[hc] = mk("event_whenbroadcastreceived", top=True, x=520, y=160,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    set_aimd = b_setvar(bs, "조준거리", V_AIMD, 99999)
    set_aimok0 = b_setvar(bs, "조준있음", V_AIMOK, 0)
    bcw_aim = b_broadcast_wait(bs, "조준요청", BR_AIM)
    aimok = cmp_op("operator_equals", vrep("조준있음", V_AIMOK), 1)
    # 발사 목표는 적 좌표 → 조준점 동기화 후 미사일 발사
    set_fx = b_setvar(bs, "발사X", V_FIREX, vrep("조준X", V_AIMX))
    set_fy = b_setvar(bs, "발사Y", V_FIREY, vrep("조준Y", V_AIMY))
    sync_m = b_broadcast_wait(bs, "조준점갱신", BR_AIMSYNC)
    snd = b_sound(bs, "missile")
    bc_fire = b_broadcast(bs, "발사", BR_FIRE)
    chain([(set_fx, bs[set_fx]), (set_fy, bs[set_fy]), (sync_m, bs[sync_m]),
           (snd, bs[snd]), (bc_fire, bs[bc_fire])])
    if_aim = b_if(bs, aimok, set_fx)
    w_gap = b_wait_var(bs, "발사간격", V_FIREGAP)
    chain([(set_aimd, bs[set_aimd]), (set_aimok0, bs[set_aimok0]),
           (bcw_aim, bs[bcw_aim]), (if_aim, bs[if_aim]), (w_gap, bs[w_gap])])
    w_idle = b_wait(bs, 0.05)
    if_fire = b_ifelse(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1), set_aimd, w_idle)
    fe_c = b_forever(bs, if_fire)
    chain([(hc, bs[hc]), (fe_c, bs[fe_c])])

    # (C2) 레이저 보조무기 — 레이저레벨≥1 일 때 자동
    hl = gen(); bs[hl] = mk("event_whenbroadcastreceived", top=True, x=520, y=360,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    set_ad2 = b_setvar(bs, "조준거리", V_AIMD, 99999)
    set_ok2 = b_setvar(bs, "조준있음", V_AIMOK, 0)
    aim_w2 = b_broadcast_wait(bs, "조준요청", BR_AIM)
    has_laser = cmp_op("operator_gt", vrep("레이저레벨", V_LASER), 0)
    has_aim2 = cmp_op("operator_equals", vrep("조준있음", V_AIMOK), 1)
    can_las = bool_op("operator_and", has_laser, has_aim2)
    set_fx2 = b_setvar(bs, "발사X", V_FIREX, vrep("조준X", V_AIMX))
    set_fy2 = b_setvar(bs, "발사Y", V_FIREY, vrep("조준Y", V_AIMY))
    sync_l = b_broadcast_wait(bs, "조준점갱신", BR_AIMSYNC)
    snd_l = b_sound(bs, "laser")
    br_las = b_broadcast(bs, "레이저발사", BR_LASER)
    chain([(set_fx2, bs[set_fx2]), (set_fy2, bs[set_fy2]), (sync_l, bs[sync_l]),
           (snd_l, bs[snd_l]), (br_las, bs[br_las])])
    if_las = b_if(bs, can_las, set_fx2)
    w_lgap = b_wait_var(bs, "레이저간격", V_LASERGAP)
    chain([(set_ad2, bs[set_ad2]), (set_ok2, bs[set_ok2]), (aim_w2, bs[aim_w2]),
           (if_las, bs[if_las]), (w_lgap, bs[w_lgap])])
    w_lidle = b_wait(bs, 0.08)
    if_lloop = b_ifelse(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 1), set_ad2, w_lidle)
    fe_l = b_forever(bs, if_lloop)
    chain([(hl, bs[hl]), (fe_l, bs[fe_l])])

    # (C3) 스킬 Z 메가빔 / X 폭탄 + 쿨 감소
    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=900, y=160,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # cool tick
    sk1gt = cmp_op("operator_gt", vrep("메가빔쿨", V_SK1CD), 0)
    ch1 = b_changevar(bs, "메가빔쿨", V_SK1CD, -0.05)
    if_c1 = b_if(bs, sk1gt, ch1)
    sk2gt = cmp_op("operator_gt", vrep("폭탄쿨", V_SK2CD), 0)
    ch2 = b_changevar(bs, "폭탄쿨", V_SK2CD, -0.05)
    if_c2 = b_if(bs, sk2gt, ch2)
    # Z 메가빔
    kz = b_keypressed(bs, "z")
    play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    cd0 = cmp_op("operator_lt", vrep("메가빔쿨", V_SK1CD), 0.05)
    can_z = bool_op("operator_and", bool_op("operator_and", kz, play), cd0)
    # aim then fire
    set_ad3 = b_setvar(bs, "조준거리", V_AIMD, 99999)
    set_ok3 = b_setvar(bs, "조준있음", V_AIMOK, 0)
    aim_w3 = b_broadcast_wait(bs, "조준요청", BR_AIM)
    set_fx3 = b_setvar(bs, "발사X", V_FIREX, vrep("조준X", V_AIMX))
    set_fy3 = b_setvar(bs, "발사Y", V_FIREY, vrep("조준Y", V_AIMY))
    # if no aim, fire forward from player (right)
    noaim = cmp_op("operator_equals", vrep("조준있음", V_AIMOK), 0)
    xp_fb = gen(); bs[xp_fb] = mk("motion_xposition")
    fx_fb = b_setvar(bs, "발사X", V_FIREX, op("operator_add", xp_fb, 120))
    yp_fb = gen(); bs[yp_fb] = mk("motion_yposition")
    fy_fb = b_setvar(bs, "발사Y", V_FIREY, yp_fb)
    chain([(fx_fb, bs[fx_fb]), (fy_fb, bs[fy_fb])])
    if_fb = b_if(bs, noaim, fx_fb)
    sync_z = b_broadcast_wait(bs, "조준점갱신", BR_AIMSYNC)
    snd_mega = b_sound(bs, "mega")
    br_mega = b_broadcast(bs, "메가빔", BR_MEGA)
    set_cd1 = b_setvar(bs, "메가빔쿨", V_SK1CD, vrep("메가빔쿨최대", V_SK1MAX))
    chain([(set_ad3, bs[set_ad3]), (set_ok3, bs[set_ok3]), (aim_w3, bs[aim_w3]),
           (set_fx3, bs[set_fx3]), (set_fy3, bs[set_fy3]), (if_fb, bs[if_fb]),
           (sync_z, bs[sync_z]),
           (snd_mega, bs[snd_mega]), (br_mega, bs[br_mega]), (set_cd1, bs[set_cd1])])
    if_z = b_if(bs, can_z, set_ad3)
    # X 폭탄 — 조준 후 투척
    kx = b_keypressed(bs, "x")
    cd20 = cmp_op("operator_lt", vrep("폭탄쿨", V_SK2CD), 0.05)
    can_x = bool_op("operator_and", bool_op("operator_and", kx, play), cd20)
    set_ad4 = b_setvar(bs, "조준거리", V_AIMD, 99999)
    set_ok4 = b_setvar(bs, "조준있음", V_AIMOK, 0)
    aim_w4 = b_broadcast_wait(bs, "조준요청", BR_AIM)
    set_fx4 = b_setvar(bs, "발사X", V_FIREX, vrep("조준X", V_AIMX))
    set_fy4 = b_setvar(bs, "발사Y", V_FIREY, vrep("조준Y", V_AIMY))
    noaim4 = cmp_op("operator_equals", vrep("조준있음", V_AIMOK), 0)
    xp_fb4 = gen(); bs[xp_fb4] = mk("motion_xposition")
    fx_fb4 = b_setvar(bs, "발사X", V_FIREX, op("operator_add", xp_fb4, 100))
    yp_fb4 = gen(); bs[yp_fb4] = mk("motion_yposition")
    fy_fb4 = b_setvar(bs, "발사Y", V_FIREY, yp_fb4)
    chain([(fx_fb4, bs[fx_fb4]), (fy_fb4, bs[fy_fb4])])
    if_fb4 = b_if(bs, noaim4, fx_fb4)
    sync_x = b_broadcast_wait(bs, "조준점갱신", BR_AIMSYNC)
    br_pulse = b_broadcast(bs, "폭탄", BR_PULSE)
    set_cd2 = b_setvar(bs, "폭탄쿨", V_SK2CD, vrep("폭탄쿨최대", V_SK2MAX))
    chain([(set_ad4, bs[set_ad4]), (set_ok4, bs[set_ok4]), (aim_w4, bs[aim_w4]),
           (set_fx4, bs[set_fx4]), (set_fy4, bs[set_fy4]), (if_fb4, bs[if_fb4]),
           (sync_x, bs[sync_x]),
           (br_pulse, bs[br_pulse]), (set_cd2, bs[set_cd2])])
    if_x = b_if(bs, can_x, set_ad4)
    wt_sk = b_wait(bs, 0.05)
    chain([(if_c1, bs[if_c1]), (if_c2, bs[if_c2]), (if_z, bs[if_z]),
           (if_x, bs[if_x]), (wt_sk, bs[wt_sk])])
    fe_sk = b_forever(bs, if_c1)
    chain([(hs, bs[hs]), (fe_sk, bs[fe_sk])])

    # (D) 사망 체크
    hd = gen(); bs[hd] = mk("event_whenbroadcastreceived", top=True, x=520, y=720,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    both = bool_op("operator_and",
                   cmp_op("operator_equals", vrep("게임상태", V_STATE), 1),
                   cmp_op("operator_lt", vrep("체력", V_HP), 1))
    set0 = b_setvar(bs, "게임상태", V_STATE, 0)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(set0, bs[set0]), (hi, bs[hi])])
    if_dead = b_if(bs, both, set0)
    w2 = b_wait(bs, 0.05)
    chain([(if_dead, bs[if_dead]), (w2, bs[w2])])
    fr2 = b_forever(bs, if_dead)
    chain([(hd, bs[hd]), (fr2, bs[fr2])])
    return bs

# ============================================================
#  미사일
# ============================================================
def build_missile_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    s0 = b_setvar(bs, "복제됨", V_MISISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (s0, bs[s0])])

    # 발사 → 추가발사 개수만큼 클론
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["발사", BR_FIRE]})
    is0 = cmp_op("operator_equals", vrep("복제됨", V_MISISC), 0)
    set_i0 = b_setvar(bs, "발사i", V_FIREI, 0)
    cc = b_create_clone(bs, "_myself_")
    y0 = b_wait(bs, 0.01)
    ch_i = b_changevar(bs, "발사i", V_FIREI, 1)
    chain([(cc, bs[cc]), (y0, bs[y0]), (ch_i, bs[ch_i])])
    multi = vrep("추가발사", V_MULTI)
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": slot(multi), "SUBSTACK": [2, cc]})
    bs[multi]["parent"] = rep; bs[cc]["parent"] = rep
    chain([(set_i0, bs[set_i0]), (rep, bs[rep])])
    if_sp = b_if(bs, is0, set_i0)
    chain([(hf, bs[hf]), (if_sp, bs[if_sp])])

    # start as clone — 내로봇 위치에서 조준점 방향으로 직진 (+ 다중발사 부채)
    hs = gen(); bs[hs] = mk("control_start_as_clone", top=True, x=20, y=280)
    set_isc = b_setvar(bs, "복제됨", V_MISISC, 1)
    set_pier = b_setvar(bs, "남은관통", V_MISPIER, vrep("관통", V_PIERCE))
    set_hcd = b_setvar(bs, "관통쿨", V_MISHITCD, 0)
    mx = b_of(bs, "내로봇", "x position")
    my = b_of(bs, "내로봇", "y position")
    go = b_gotoxy(bs, mx, my)
    pdir = b_pointtowards(bs, "조준점")
    # fan spread: (발사i - (추가발사-1)/2) * 14
    half = op("operator_divide", op("operator_subtract", vrep("추가발사", V_MULTI), 1), 2)
    spread = op("operator_multiply", op("operator_subtract", vrep("발사i", V_FIREI), half), 14)
    turn = gen(); bs[turn] = mk("motion_turnright", inputs={"DEGREES": slot(spread)})
    bs[spread]["parent"] = turn
    sh = gen(); bs[sh] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(55)})

    mv = b_movesteps(bs, vrep("미사일속도", V_MISSPD))
    # edge
    edge_m = gen(); bs[edge_m] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_e = gen(); bs[tc_e] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge_m]})
    bs[edge_m]["parent"] = tc_e
    del_e = gen(); bs[del_e] = mk("control_delete_this_clone")
    if_edge = b_if(bs, tc_e, del_e)

    touch = b_touching(bs, "적로봇")
    can = bool_op("operator_and", touch,
                  cmp_op("operator_equals", vrep("관통쿨", V_MISHITCD), 0))
    ch_p = b_changevar(bs, "남은관통", V_MISPIER, -1)
    set_cd = b_setvar(bs, "관통쿨", V_MISHITCD, 5)
    linger = b_wait(bs, 0.06)
    del2 = gen(); bs[del2] = mk("control_delete_this_clone")
    chain([(linger, bs[linger]), (del2, bs[del2])])
    if_pd = b_if(bs, cmp_op("operator_lt", vrep("남은관통", V_MISPIER), 1), linger)
    chain([(ch_p, bs[ch_p]), (set_cd, bs[set_cd]), (if_pd, bs[if_pd])])
    if_hit = b_if(bs, can, ch_p)

    hcd_gt = cmp_op("operator_gt", vrep("관통쿨", V_MISHITCD), 0)
    if_hcd = b_if(bs, hcd_gt, b_changevar(bs, "관통쿨", V_MISHITCD, -1))
    w = b_wait(bs, 0.015)
    chain([(mv, bs[mv]), (if_edge, bs[if_edge]), (if_hit, bs[if_hit]), (if_hcd, bs[if_hcd]), (w, bs[w])])

    st0 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    stop = bool_op("operator_or", tc_e, st0)
    # repeat until edge or over — but tc_e was used in if; need fresh edge check
    edge2 = gen(); bs[edge2] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc2 = gen(); bs[tc2] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge2]})
    bs[edge2]["parent"] = tc2
    st0b = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    stop2 = bool_op("operator_or", tc2, st0b)
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, stop2], "SUBSTACK": [2, mv]})
    bs[stop2]["parent"] = ru; bs[mv]["parent"] = ru
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(hs, bs[hs]), (set_isc, bs[set_isc]), (set_pier, bs[set_pier]),
           (set_hcd, bs[set_hcd]), (go, bs[go]), (pdir, bs[pdir]), (turn, bs[turn]),
           (sz, bs[sz]), (sh, bs[sh]), (ru, bs[ru]), (del_end, bs[del_end])])
    return bs

def build_laser_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    s0 = b_setvar(bs, "복제됨", V_LASISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (s0, bs[s0])])
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["레이저발사", BR_LASER]})
    if_sp = b_if(bs, cmp_op("operator_equals", vrep("복제됨", V_LASISC), 0),
                 b_create_clone(bs, "_myself_"))
    chain([(hf, bs[hf]), (if_sp, bs[if_sp])])
    hs = gen(); bs[hs] = mk("control_start_as_clone", top=True, x=20, y=260)
    set_isc = b_setvar(bs, "복제됨", V_LASISC, 1)
    p = op("operator_add", 3, vrep("레이저레벨", V_LASER))
    set_pier = b_setvar(bs, "남은관통", V_LASPIER, p)
    set_hcd = b_setvar(bs, "관통쿨", V_LASHITCD, 0)
    go = b_gotoxy(bs, b_of(bs, "내로봇", "x position"), b_of(bs, "내로봇", "y position"))
    # 조준점(발사 목표) 방향으로 직진 — atan 오류 방지
    pdir = b_pointtowards(bs, "조준점")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(50)})
    sh = gen(); bs[sh] = mk("looks_show")
    mv = b_movesteps(bs, 14)
    edge_m = gen(); bs[edge_m] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_e = gen(); bs[tc_e] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge_m]})
    bs[edge_m]["parent"] = tc_e
    del_e = gen(); bs[del_e] = mk("control_delete_this_clone")
    if_edge = b_if(bs, tc_e, del_e)
    touch = b_touching(bs, "적로봇")
    can = bool_op("operator_and", touch, cmp_op("operator_equals", vrep("관통쿨", V_LASHITCD), 0))
    ch_p = b_changevar(bs, "남은관통", V_LASPIER, -1)
    set_cd = b_setvar(bs, "관통쿨", V_LASHITCD, 4)
    linger = b_wait(bs, 0.05); del2 = gen(); bs[del2] = mk("control_delete_this_clone")
    chain([(linger, bs[linger]), (del2, bs[del2])])
    if_pd = b_if(bs, cmp_op("operator_lt", vrep("남은관통", V_LASPIER), 1), linger)
    chain([(ch_p, bs[ch_p]), (set_cd, bs[set_cd]), (if_pd, bs[if_pd])])
    if_hit = b_if(bs, can, ch_p)
    if_hcd = b_if(bs, cmp_op("operator_gt", vrep("관통쿨", V_LASHITCD), 0),
                  b_changevar(bs, "관통쿨", V_LASHITCD, -1))
    w = b_wait(bs, 0.012)
    chain([(mv, bs[mv]), (if_edge, bs[if_edge]), (if_hit, bs[if_hit]), (if_hcd, bs[if_hcd]), (w, bs[w])])
    edge2 = gen(); bs[edge2] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc2 = gen(); bs[tc2] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge2]})
    bs[edge2]["parent"] = tc2
    stop2 = bool_op("operator_or", tc2, cmp_op("operator_equals", vrep("게임상태", V_STATE), 0))
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, stop2], "SUBSTACK": [2, mv]})
    bs[stop2]["parent"] = ru; bs[mv]["parent"] = ru
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(hs, bs[hs]), (set_isc, bs[set_isc]), (set_pier, bs[set_pier]),
           (set_hcd, bs[set_hcd]), (go, bs[go]), (pdir, bs[pdir]),
           (sz, bs[sz]), (sh, bs[sh]), (ru, bs[ru]), (del_end, bs[del_end])])
    return bs

def build_aim_point_blocks():
    """숨은 조준점 — 발사X/Y 에 위치. 탄환이 point towards 로 직진."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(5)})
    go0 = b_gotoxy(bs, 0, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (go0, bs[go0])])
    # 발사 직전 동기화 (broadcast and wait 로 좌표 확정 후 탄환 생성)
    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["조준점갱신", BR_AIMSYNC]})
    go = b_gotoxy(bs, vrep("발사X", V_FIREX), vrep("발사Y", V_FIREY))
    chain([(hs, bs[hs]), (go, bs[go])])
    # 백업: 게임 중 매 프레임도 추적
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    go2 = b_gotoxy(bs, vrep("발사X", V_FIREX), vrep("발사Y", V_FIREY))
    w = b_wait(bs, 0)
    chain([(go2, bs[go2]), (w, bs[w])])
    fr = b_forever(bs, go2)
    chain([(hb, bs[hb]), (fr, bs[fr])])
    return bs


def build_mega_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    s0 = b_setvar(bs, "복제됨", V_MEGISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (s0, bs[s0])])
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["메가빔", BR_MEGA]})
    if_sp = b_if(bs, cmp_op("operator_equals", vrep("복제됨", V_MEGISC), 0),
                 b_create_clone(bs, "_myself_"))
    chain([(hf, bs[hf]), (if_sp, bs[if_sp])])
    hs = gen(); bs[hs] = mk("control_start_as_clone", top=True, x=20, y=260)
    set_isc = b_setvar(bs, "복제됨", V_MEGISC, 1)
    set_pier = b_setvar(bs, "남은관통", V_MEGPIER, 25)
    set_hcd = b_setvar(bs, "관통쿨", V_MEGHITCD, 0)
    go = b_gotoxy(bs, b_of(bs, "내로봇", "x position"), b_of(bs, "내로봇", "y position"))
    # 조준점 방향으로 직진 (atan 오류 방지)
    pdir = b_pointtowards(bs, "조준점")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    mv = b_movesteps(bs, 16)
    edge_m = gen(); bs[edge_m] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_e = gen(); bs[tc_e] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge_m]})
    bs[edge_m]["parent"] = tc_e
    del_e = gen(); bs[del_e] = mk("control_delete_this_clone")
    if_edge = b_if(bs, tc_e, del_e)
    # 적 또는 보스 피격
    touch_e = b_touching(bs, "적로봇")
    touch_b = b_touching(bs, "보스")
    touch = bool_op("operator_or", touch_e, touch_b)
    can = bool_op("operator_and", touch, cmp_op("operator_equals", vrep("관통쿨", V_MEGHITCD), 0))
    ch_p = b_changevar(bs, "남은관통", V_MEGPIER, -1)
    set_cd = b_setvar(bs, "관통쿨", V_MEGHITCD, 3)
    linger = b_wait(bs, 0.04); del2 = gen(); bs[del2] = mk("control_delete_this_clone")
    chain([(linger, bs[linger]), (del2, bs[del2])])
    if_pd = b_if(bs, cmp_op("operator_lt", vrep("남은관통", V_MEGPIER), 1), linger)
    chain([(ch_p, bs[ch_p]), (set_cd, bs[set_cd]), (if_pd, bs[if_pd])])
    if_hit = b_if(bs, can, ch_p)
    if_hcd = b_if(bs, cmp_op("operator_gt", vrep("관통쿨", V_MEGHITCD), 0),
                  b_changevar(bs, "관통쿨", V_MEGHITCD, -1))
    w = b_wait(bs, 0.012)
    chain([(mv, bs[mv]), (if_edge, bs[if_edge]), (if_hit, bs[if_hit]), (if_hcd, bs[if_hcd]), (w, bs[w])])
    edge2 = gen(); bs[edge2] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc2 = gen(); bs[tc2] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge2]})
    bs[edge2]["parent"] = tc2
    stop2 = bool_op("operator_or", tc2, cmp_op("operator_equals", vrep("게임상태", V_STATE), 0))
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, stop2], "SUBSTACK": [2, mv]})
    bs[stop2]["parent"] = ru; bs[mv]["parent"] = ru
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(hs, bs[hs]), (set_isc, bs[set_isc]), (set_pier, bs[set_pier]),
           (set_hcd, bs[set_hcd]), (go, bs[go]), (pdir, bs[pdir]),
           (sz, bs[sz]), (sh, bs[sh]), (ru, bs[ru]), (del_end, bs[del_end])])
    return bs

def build_pulse_blocks():
    """폭탄 투척: 조준 방향으로 날아가다 펑! 폭발 → 폭탄폭발 방송(AOE)."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    s0 = b_setvar(bs, "복제됨", V_PULISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (s0, bs[s0])])

    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["폭탄", BR_PULSE]})
    if_sp = b_if(bs, cmp_op("operator_equals", vrep("복제됨", V_PULISC), 0),
                 b_create_clone(bs, "_myself_"))
    chain([(hf, bs[hf]), (if_sp, bs[if_sp])])

    hs = gen(); bs[hs] = mk("control_start_as_clone", top=True, x=20, y=240)
    set_isc = b_setvar(bs, "복제됨", V_PULISC, 1)
    # 폭탄 코스튬
    cm = gen(); bs[cm] = mk("looks_costume", fields={"COSTUME": ["bomb", None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm]})
    bs[cm]["parent"] = sw
    go = b_gotoxy(bs, b_of(bs, "내로봇", "x position"), b_of(bs, "내로봇", "y position"))
    # 조준점 방향으로 직진
    pdir = b_pointtowards(bs, "조준점")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(75)})
    sh = gen(); bs[sh] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    throw_snd = b_sound(bs, "throw")
    # 날아가기 (약 0.45초)
    mv = b_movesteps(bs, 11)
    ww = b_wait(bs, 0.03)
    chain([(mv, bs[mv]), (ww, bs[ww])])
    fly = gen(); bs[fly] = mk("control_repeat",
        inputs={"TIMES": num(15), "SUBSTACK": [2, mv]})
    bs[mv]["parent"] = fly
    # 폭발 좌표 기록
    xp3 = gen(); bs[xp3] = mk("motion_xposition")
    set_bx = b_setvar(bs, "폭탄X", V_BOMBX, xp3)
    yp3 = gen(); bs[yp3] = mk("motion_yposition")
    set_by = b_setvar(bs, "폭탄Y", V_BOMBY, yp3)
    # 폭발 코스튬 + 방송
    cm2 = gen(); bs[cm2] = mk("looks_costume", fields={"COSTUME": ["boom", None]}, shadow=True)
    sw2 = gen(); bs[sw2] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm2]})
    bs[cm2]["parent"] = sw2
    sz2 = gen(); bs[sz2] = mk("looks_setsizeto", inputs={"SIZE": num(50)})
    boom_snd = b_sound(bs, "bomb_boom")
    br_boom = b_broadcast(bs, "폭탄폭발", BR_BOMBBOOM)
    # 펑! 커지며 사라짐
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(16)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(14)}, fields={"EFFECT": ["GHOST", None]})
    w2 = b_wait(bs, 0.03)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w2, bs[w2])])
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(8), "SUBSTACK": [2, ch_sz]})
    bs[ch_sz]["parent"] = rep
    delc = gen(); bs[delc] = mk("control_delete_this_clone")
    chain([(hs, bs[hs]), (set_isc, bs[set_isc]), (sw, bs[sw]), (go, bs[go]),
           (pdir, bs[pdir]), (sz, bs[sz]), (front, bs[front]), (sh, bs[sh]),
           (throw_snd, bs[throw_snd]),
           (fly, bs[fly]), (set_bx, bs[set_bx]), (set_by, bs[set_by]),
           (sw2, bs[sw2]), (sz2, bs[sz2]), (boom_snd, bs[boom_snd]),
           (br_boom, bs[br_boom]), (rep, bs[rep]), (delc, bs[delc])])
    return bs

def build_skill_icon_blocks(cd_name, cd_vid, max_name, max_vid, x, y):
    """하단 스킬 아이콘: 쿨 중이면 고스트↑ (쿨/최대 * 80)."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = b_gotoxy(bs, x, y)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]), (sh, bs[sh])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=180,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # forever: ghost = min(80, (쿨/최대)*80) when max>0
    cd = vrep(cd_name, cd_vid)
    mx = vrep(max_name, max_vid)
    ratio = op("operator_divide", cd, mx)
    ghv = op("operator_multiply", ratio, 80)
    set_g = b_setvar(bs, "쿨고스트", V_CDGHOST, ghv)
    # clamp 0..80
    too_hi = cmp_op("operator_gt", vrep("쿨고스트", V_CDGHOST), 80)
    if_hi = b_if(bs, too_hi, b_setvar(bs, "쿨고스트", V_CDGHOST, 80))
    too_lo = cmp_op("operator_lt", vrep("쿨고스트", V_CDGHOST), 0)
    if_lo = b_if(bs, too_lo, b_setvar(bs, "쿨고스트", V_CDGHOST, 0))
    # ready flash: if cool < 0.05 ghost 0 else set effect
    ready = cmp_op("operator_lt", vrep(cd_name, cd_vid), 0.05)
    gh0 = gen(); bs[gh0] = mk("looks_seteffectto", inputs={"VALUE": num(0)},
                              fields={"EFFECT": ["GHOST", None]})
    ghr = vrep("쿨고스트", V_CDGHOST)
    ghset = gen(); bs[ghset] = mk("looks_seteffectto", inputs={"VALUE": slot(ghr)},
                                  fields={"EFFECT": ["GHOST", None]})
    bs[ghr]["parent"] = ghset
    if_rdy = b_ifelse(bs, ready, gh0, ghset)
    wt = b_wait(bs, 0.05)
    chain([(set_g, bs[set_g]), (if_hi, bs[if_hi]), (if_lo, bs[if_lo]),
           (if_rdy, bs[if_rdy]), (wt, bs[wt])])
    fr = b_forever(bs, set_g)
    chain([(hb, bs[hb]), (fr, bs[fr])])
    return bs

def build_hp_ui_blocks():
    """체력 하트 UI — 체력 값에 따라 코스튬 0~5."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = b_gotoxy(bs, -150, 155)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    sh = gen(); bs[sh] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]), (sh, bs[sh])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    # costume name = join "hp" + 체력 (clamp 0..5)
    hp = vrep("체력", V_HP)
    # if hp > 5 → 5; if hp < 0 → 0
    set_t = b_setvar(bs, "임시2", V_TMP2, hp)
    if_hi = b_if(bs, cmp_op("operator_gt", vrep("임시2", V_TMP2), 5),
                 b_setvar(bs, "임시2", V_TMP2, 5))
    if_lo = b_if(bs, cmp_op("operator_lt", vrep("임시2", V_TMP2), 0),
                 b_setvar(bs, "임시2", V_TMP2, 0))
    def text_slot(s):
        return [1, [10, str(s)]]
    tv = vrep("임시2", V_TMP2)
    join = gen()
    bs[join] = mk("operator_join",
        inputs={"STRING1": text_slot("hp"), "STRING2": slot(tv)})
    bs[tv]["parent"] = join
    sw = gen(); bs[sw] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [3, join, [10, "hp5"]]})
    bs[join]["parent"] = sw
    wt = b_wait(bs, 0.08)
    chain([(set_t, bs[set_t]), (if_hi, bs[if_hi]), (if_lo, bs[if_lo]),
           (sw, bs[sw]), (wt, bs[wt])])
    fr = b_forever(bs, set_t)
    chain([(hb, bs[hb]), (fr, bs[fr])])
    return bs

def build_hud_text_blocks():
    """웨이브/점수 — say 로 숫자 UI (변수 모니터 대체)."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    g = b_gotoxy(bs, -80, 155)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h, bs[h]), (g, bs[g]), (sz, bs[sz]), (sh, bs[sh])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    def text_slot(s):
        return [1, [10, str(s)]]
    # join "W" 웨이브 " S" 점수
    j1 = gen()
    w = vrep("웨이브", V_WAVE)
    bs[j1] = mk("operator_join", inputs={"STRING1": text_slot("W"), "STRING2": slot(w)})
    bs[w]["parent"] = j1
    j2 = gen()
    bs[j2] = mk("operator_join", inputs={"STRING1": slot(j1), "STRING2": text_slot("  S")})
    bs[j1]["parent"] = j2
    j3 = gen()
    sc = vrep("점수", V_SCORE)
    bs[j3] = mk("operator_join", inputs={"STRING1": slot(j2), "STRING2": slot(sc)})
    bs[j2]["parent"] = j3; bs[sc]["parent"] = j3
    say = gen(); bs[say] = mk("looks_say", inputs={"MESSAGE": slot(j3)})
    bs[j3]["parent"] = say
    wt = b_wait(bs, 0.15)
    chain([(say, bs[say]), (wt, bs[wt])])
    fr = b_forever(bs, say)
    chain([(hb, bs[hb]), (fr, bs[fr])])
    return bs

# ============================================================
#  보스 (5의 배수 웨이브) + 보스탄
# ============================================================
def build_boss_blocks():
    """상단 순찰 + 플레이어 조준 사격. 미사일/레이저/메가/폭탄에 피격."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g0 = b_gotoxy(bs, 0, 130)
    chain([(h, bs[h]), (hi, bs[hi]), (g0, bs[g0])])

    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["보스스폰", BR_BOSS]})
    hp = op("operator_add", vrep("보스기본체력", V_BOSSBASE),
            op("operator_multiply", vrep("웨이브", V_WAVE), 8))
    set_hp = b_setvar(bs, "보스체력", V_BOSSHP, hp)
    set_dir = b_setvar(bs, "보스방향", V_BOSSDIR, 1)
    set_diry = b_setvar(bs, "보스방향Y", V_BOSSDIRY, 1)
    set_cd = b_setvar(bs, "보사쿨", V_BOSSCD, 0)
    set_hit = b_setvar(bs, "보스피격쿨", V_BOSSHIT, 0)
    set_vol = b_setvar(bs, "보볼리", V_BOSSVOLLEY, 0)
    # 보스탄수 = min(7, 1 + floor(웨이브/5))  → 5웨이브2발, 10웨이브3발…
    # Scratch: 웨이브/5 를 정수처럼 쓰되 최소 1
    tier = op("operator_divide", vrep("웨이브", V_WAVE), 5)
    multi0 = op("operator_add", 1, tier)
    set_multi = b_setvar(bs, "보스탄수", V_BOSSMULTI, multi0)
    # clamp multi to int-ish: if > 7 set 7
    if_mhi = b_if(bs, cmp_op("operator_gt", vrep("보스탄수", V_BOSSMULTI), 7),
                  b_setvar(bs, "보스탄수", V_BOSSMULTI, 7))
    # 간격 = max(0.28, 0.80 - tier*0.08)
    gap0 = op("operator_subtract", 0.80, op("operator_multiply", tier, 0.08))
    set_gap = b_setvar(bs, "보스간격", V_BOSSGAP, gap0)
    if_glo = b_if(bs, cmp_op("operator_lt", vrep("보스간격", V_BOSSGAP), 0.28),
                  b_setvar(bs, "보스간격", V_BOSSGAP, 0.28))
    go = b_gotoxy(bs, 0, 130)
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    sh = gen(); bs[sh] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    chain([(hs, bs[hs]), (set_hp, bs[set_hp]), (set_dir, bs[set_dir]), (set_diry, bs[set_diry]),
           (set_cd, bs[set_cd]),
           (set_hit, bs[set_hit]), (set_vol, bs[set_vol]),
           (set_multi, bs[set_multi]), (if_mhi, bs[if_mhi]),
           (set_gap, bs[set_gap]), (if_glo, bs[if_glo]),
           (go, bs[go]), (sz, bs[sz]), (front, bs[front]), (sh, bs[sh])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=360,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    alive = cmp_op("operator_gt", vrep("보스체력", V_BOSSHP), 0)
    active = bool_op("operator_and", play, alive)

    # ---- 2D 순찰: 상단 중앙 박스 (±140, y 55~125) 안에서만, 구석 고착 방지 ----
    def make_setx(val):
        bid = gen(); bs[bid] = mk("motion_setx", inputs={"X": num(val)}); return bid
    def make_sety(val):
        bid = gen(); bs[bid] = mk("motion_sety", inputs={"Y": num(val)}); return bid

    xp = gen(); bs[xp] = mk("motion_xposition")
    rev_r = b_setvar(bs, "보스방향", V_BOSSDIR, -1)
    clamp_xr = make_setx(140)
    chain([(rev_r, bs[rev_r]), (clamp_xr, bs[clamp_xr])])
    if_edge_r = b_if(bs, cmp_op("operator_gt", xp, 140), rev_r)

    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    rev_l = b_setvar(bs, "보스방향", V_BOSSDIR, 1)
    clamp_xl = make_setx(-140)
    chain([(rev_l, bs[rev_l]), (clamp_xl, bs[clamp_xl])])
    if_edge_l = b_if(bs, cmp_op("operator_lt", xp2, -140), rev_l)

    yp = gen(); bs[yp] = mk("motion_yposition")
    rev_t = b_setvar(bs, "보스방향Y", V_BOSSDIRY, -1)
    clamp_yt = make_sety(125)
    chain([(rev_t, bs[rev_t]), (clamp_yt, bs[clamp_yt])])
    if_edge_t = b_if(bs, cmp_op("operator_gt", yp, 125), rev_t)

    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    rev_b = b_setvar(bs, "보스방향Y", V_BOSSDIRY, 1)
    clamp_yb = make_sety(55)
    chain([(rev_b, bs[rev_b]), (clamp_yb, bs[clamp_yb])])
    if_edge_b = b_if(bs, cmp_op("operator_lt", yp2, 55), rev_b)

    # 구석이면 중앙(0, 95) 쪽으로 끌어당김 (리포터는 비교마다 새로)
    def xpos():
        bid = gen(); bs[bid] = mk("motion_xposition"); return bid
    def ypos():
        bid = gen(); bs[bid] = mk("motion_yposition"); return bid
    near_x = bool_op("operator_or",
        cmp_op("operator_gt", xpos(), 120),
        cmp_op("operator_lt", xpos(), -120))
    near_y = bool_op("operator_or",
        cmp_op("operator_gt", ypos(), 115),
        cmp_op("operator_lt", ypos(), 65))
    near_corner = bool_op("operator_and", near_x, near_y)
    pull_x = xpos()
    pull_dx = op("operator_multiply", op("operator_subtract", 0, pull_x), 0.3)
    do_pull_x = gen(); bs[do_pull_x] = mk("motion_changexby", inputs={"DX": slot(pull_dx)})
    bs[pull_dx]["parent"] = do_pull_x
    pull_y = ypos()
    pull_dy = op("operator_multiply", op("operator_subtract", 95, pull_y), 0.3)
    do_pull_y = gen(); bs[do_pull_y] = mk("motion_changeyby", inputs={"DY": slot(pull_dy)})
    bs[pull_dy]["parent"] = do_pull_y
    # 중앙 쪽으로 방향 전환: x 부호 반대
    # x>0 → dir -1, x<=0 → dir 1  (단순: 항상 좌우 번갈아 안쪽)
    set_in_x = b_setvar(bs, "보스방향", V_BOSSDIR, -1)
    set_in_y = b_setvar(bs, "보스방향Y", V_BOSSDIRY, -1)
    chain([(do_pull_x, bs[do_pull_x]), (do_pull_y, bs[do_pull_y]),
           (set_in_x, bs[set_in_x]), (set_in_y, bs[set_in_y])])
    if_corner = b_if(bs, near_corner, do_pull_x)

    # 이동속도: 2.8 + tier*0.35
    spd = op("operator_add", 2.8, op("operator_multiply",
              op("operator_divide", vrep("웨이브", V_WAVE), 5), 0.35))
    step_x = op("operator_multiply", vrep("보스방향", V_BOSSDIR), spd)
    chx = gen(); bs[chx] = mk("motion_changexby", inputs={"DX": slot(step_x)})
    bs[step_x]["parent"] = chx
    step_y = op("operator_multiply", vrep("보스방향Y", V_BOSSDIRY),
                op("operator_multiply", spd, 0.65))
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": slot(step_y)})
    bs[step_y]["parent"] = chy

    # ---- 사격: 일반 부채꼴 / 필살기(전방위) ----
    cd_ok = cmp_op("operator_lt", vrep("보사쿨", V_BOSSCD), 0.05)
    bx = gen(); bs[bx] = mk("motion_xposition")
    set_bx = b_setvar(bs, "보스탄X", V_BBX, bx)
    by = gen(); bs[by] = mk("motion_yposition")
    set_by = b_setvar(bs, "보스탄Y", V_BBY, by)
    snd_bf = b_sound(bs, "boss_fire")
    # 플레이어 방향 기준
    pt_pl = b_pointtowards(bs, "내로봇")
    # base dir = motion_direction
    base_d = gen(); bs[base_d] = mk("motion_direction")
    set_base = b_setvar(bs, "임시2", V_TMP2, base_d)  # 기준 방향 저장

    # 일반: 부채꼴 multi발
    set_fi0 = b_setvar(bs, "보스발사i", V_BOSSFI, 0)
    # dir = 기준 + (i - (multi-1)/2) * 14
    fi = vrep("보스발사i", V_BOSSFI)
    half = op("operator_divide", op("operator_subtract", vrep("보스탄수", V_BOSSMULTI), 1), 2)
    off = op("operator_multiply", op("operator_subtract", fi, half), 14)
    fdir = op("operator_add", vrep("임시2", V_TMP2), off)
    set_bdir = b_setvar(bs, "보스탄방향", V_BBDIR, fdir)
    br_f = b_broadcast(bs, "보스사격", BR_BFIRE)
    y0 = b_wait(bs, 0)
    ch_fi = b_changevar(bs, "보스발사i", V_BOSSFI, 1)
    chain([(set_bdir, bs[set_bdir]), (br_f, bs[br_f]), (y0, bs[y0]), (ch_fi, bs[ch_fi])])
    multi_v = vrep("보스탄수", V_BOSSMULTI)
    rep_n = gen(); bs[rep_n] = mk("control_repeat",
        inputs={"TIMES": slot(multi_v), "SUBSTACK": [2, set_bdir]})
    bs[multi_v]["parent"] = rep_n; bs[set_bdir]["parent"] = rep_n
    chain([(set_fi0, bs[set_fi0]), (rep_n, bs[rep_n])])

    # 필살기: 12방향 전방위 (웨이브>=10 이고 보볼리%5==0)
    set_fi0s = b_setvar(bs, "보스발사i", V_BOSSFI, 0)
    # dir = i * 30
    fi2 = vrep("보스발사i", V_BOSSFI)
    fdir2 = op("operator_multiply", fi2, 30)
    set_bdir2 = b_setvar(bs, "보스탄방향", V_BBDIR, fdir2)
    br_f2 = b_broadcast(bs, "보스사격", BR_BFIRE)
    y0s = b_wait(bs, 0)
    ch_fi2 = b_changevar(bs, "보스발사i", V_BOSSFI, 1)
    chain([(set_bdir2, bs[set_bdir2]), (br_f2, bs[br_f2]), (y0s, bs[y0s]), (ch_fi2, bs[ch_fi2])])
    rep_s = gen(); bs[rep_s] = mk("control_repeat",
        inputs={"TIMES": num(12), "SUBSTACK": [2, set_bdir2]})
    bs[set_bdir2]["parent"] = rep_s
    chain([(set_fi0s, bs[set_fi0s]), (rep_s, bs[rep_s])])

    # 필살기 조건: 웨이브>=10 and (보볼리 mod 5)==0
    wge10 = cmp_op("operator_gt", vrep("웨이브", V_WAVE), 9)
    vol_mod = op("operator_mod", vrep("보볼리", V_BOSSVOLLEY), 5)
    vol0 = cmp_op("operator_equals", vol_mod, 0)
    # 보볼리>0 so first shot isn't special at 0
    vol_pos = cmp_op("operator_gt", vrep("보볼리", V_BOSSVOLLEY), 0)
    is_special = bool_op("operator_and", wge10, bool_op("operator_and", vol0, vol_pos))
    # HP 40% 이하면 추가: 매 3볼리마다 필살기 (더 자주)
    # 단순화: 기본 is_special 유지 + 저체력 시 mod 3
    hp_ratio_num = op("operator_multiply", vrep("보스체력", V_BOSSHP), 1)
    # low HP: 체력 < 기본*0.4 근사 — 보스기본+웨이브*8 의 40%는 복잡하니 체력 < 25+웨이브*2
    low_th = op("operator_add", 20, op("operator_multiply", vrep("웨이브", V_WAVE), 2))
    low_hp = cmp_op("operator_lt", vrep("보스체력", V_BOSSHP), low_th)
    vol_mod3 = op("operator_mod", vrep("보볼리", V_BOSSVOLLEY), 3)
    vol3_0 = cmp_op("operator_equals", vol_mod3, 0)
    is_sp2 = bool_op("operator_and", low_hp, bool_op("operator_and", vol3_0, vol_pos))
    do_special = bool_op("operator_or", is_special, is_sp2)

    fire_branch = b_ifelse(bs, do_special, set_fi0s, set_fi0)
    ch_vol = b_changevar(bs, "보볼리", V_BOSSVOLLEY, 1)
    # 저체력 시 간격 30% 단축
    set_cd_n = b_setvar(bs, "보사쿨", V_BOSSCD, vrep("보스간격", V_BOSSGAP))
    gap_fast = op("operator_multiply", vrep("보스간격", V_BOSSGAP), 0.65)
    set_cd_f = b_setvar(bs, "보사쿨", V_BOSSCD, gap_fast)
    cd_branch = b_ifelse(bs, low_hp, set_cd_f, set_cd_n)

    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]), (snd_bf, bs[snd_bf]),
           (pt_pl, bs[pt_pl]), (set_base, bs[set_base]),
           (fire_branch, bs[fire_branch]), (ch_vol, bs[ch_vol]), (cd_branch, bs[cd_branch])])
    if_fire = b_if(bs, cd_ok, set_bx)
    if_cdt = b_if(bs, cmp_op("operator_gt", vrep("보사쿨", V_BOSSCD), 0),
                  b_changevar(bs, "보사쿨", V_BOSSCD, -0.05))

    def boss_hit(touch_name, dmg_fn):
        touch = b_touching(bs, touch_name)
        can = bool_op("operator_and", touch,
                      cmp_op("operator_equals", vrep("보스피격쿨", V_BOSSHIT), 0))
        dmg_r = dmg_fn()
        set_d = b_setvar(bs, "피격데미지", V_HITDMG, dmg_r)
        neg = op("operator_subtract", 0, vrep("피격데미지", V_HITDMG))
        ch = b_changevar(bs, "보스체력", V_BOSSHP, neg)
        set_hc = b_setvar(bs, "보스피격쿨", V_BOSSHIT, 5)
        hit_snd = b_sound(bs, "hit")
        brt = gen(); bs[brt] = mk("looks_seteffectto",
            inputs={"VALUE": num(100)}, fields={"EFFECT": ["BRIGHTNESS", None]})
        # 넉백은 구석으로 밀지 않도록 중앙 쪽으로만 살짝
        kx = gen(); bs[kx] = mk("motion_xposition")
        knx = op("operator_multiply", op("operator_subtract", 0, kx), 0.08)
        knock_x = gen(); bs[knock_x] = mk("motion_changexby", inputs={"DX": slot(knx)})
        bs[knx]["parent"] = knock_x
        set_dv = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("피격데미지", V_HITDMG))
        xx = gen(); bs[xx] = mk("motion_xposition")
        set_dx = b_setvar(bs, "데미지표시x", V_DMGX, xx)
        yy = gen(); bs[yy] = mk("motion_yposition")
        set_dy = b_setvar(bs, "데미지표시y", V_DMGY, yy)
        set_k = b_setvar(bs, "데미지종류", V_DMGKIND, 1)
        bc = b_broadcast(bs, "데미지표시", BR_DMG)
        bc_fx = b_broadcast(bs, "타격효과", BR_HITFX)
        chain([(set_d, bs[set_d]), (ch, bs[ch]), (set_hc, bs[set_hc]),
               (hit_snd, bs[hit_snd]), (brt, bs[brt]), (knock_x, bs[knock_x]),
               (set_dv, bs[set_dv]), (set_dx, bs[set_dx]), (set_dy, bs[set_dy]),
               (set_k, bs[set_k]), (bc, bs[bc]), (bc_fx, bs[bc_fx])])
        return b_if(bs, can, set_d)

    if_mis = boss_hit("미사일", lambda: vrep("공격력", V_ATK))
    if_las = boss_hit("레이저", lambda: op("operator_add", vrep("공격력", V_ATK), vrep("레이저레벨", V_LASER)))
    if_meg = boss_hit("메가빔", lambda: op("operator_multiply", vrep("공격력", V_ATK), 4))
    if_ht = b_if(bs, cmp_op("operator_gt", vrep("보스피격쿨", V_BOSSHIT), 0),
                 b_changevar(bs, "보스피격쿨", V_BOSSHIT, -1))
    # 피격 중 밝기 유지 / 끝나면 해제
    hit_on = cmp_op("operator_gt", vrep("보스피격쿨", V_BOSSHIT), 0)
    brt_on = gen(); bs[brt_on] = mk("looks_seteffectto",
        inputs={"VALUE": num(80)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    brt_off = gen(); bs[brt_off] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    if_flash = b_ifelse(bs, hit_on, brt_on, brt_off)

    dead = cmp_op("operator_lt", vrep("보스체력", V_BOSSHP), 1)
    ch_sc = b_changevar(bs, "점수", V_SCORE, 15)
    ch_al = b_changevar(bs, "적수", V_ALIVE, -1)
    boom = b_sound(bs, "explode")
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    set_hp0 = b_setvar(bs, "보스체력", V_BOSSHP, 0)
    chain([(ch_sc, bs[ch_sc]), (ch_al, bs[ch_al]), (boom, bs[boom]),
           (hi2, bs[hi2]), (set_hp0, bs[set_hp0])])
    if_dead = b_if(bs, dead, ch_sc)

    wt = b_wait(bs, 0.05)
    chain([(if_edge_r, bs[if_edge_r]), (if_edge_l, bs[if_edge_l]),
           (if_edge_t, bs[if_edge_t]), (if_edge_b, bs[if_edge_b]),
           (if_corner, bs[if_corner]),
           (chx, bs[chx]), (chy, bs[chy]),
           (if_fire, bs[if_fire]), (if_cdt, bs[if_cdt]),
           (if_mis, bs[if_mis]), (if_las, bs[if_las]), (if_meg, bs[if_meg]),
           (if_ht, bs[if_ht]), (if_flash, bs[if_flash]), (if_dead, bs[if_dead]), (wt, bs[wt])])
    if_act = b_if(bs, active, if_edge_r)
    hi_go = gen(); bs[hi_go] = mk("looks_hide")
    if_go = b_if(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 0), hi_go)
    w2 = b_wait(bs, 0.05)
    chain([(if_act, bs[if_act]), (if_go, bs[if_go]), (w2, bs[w2])])
    fr = b_forever(bs, if_act)
    chain([(hb, bs[hb]), (fr, bs[fr])])

    # 조준 대상 (보스 살아 있으면 조준 경쟁)
    ha = gen(); bs[ha] = mk("event_whenbroadcastreceived", top=True, x=520, y=140,
        fields={"BROADCAST_OPTION": ["조준요청", BR_AIM]})
    can_aim = bool_op("operator_and",
                      cmp_op("operator_gt", vrep("보스체력", V_BOSSHP), 0),
                      cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    dist = b_distance_to(bs, "내로봇")
    closer = cmp_op("operator_lt", dist, vrep("조준거리", V_AIMD))
    set_ad = b_setvar(bs, "조준거리", V_AIMD, b_distance_to(bs, "내로봇"))
    ax = gen(); bs[ax] = mk("motion_xposition")
    set_ax = b_setvar(bs, "조준X", V_AIMX, ax)
    ay = gen(); bs[ay] = mk("motion_yposition")
    set_ay = b_setvar(bs, "조준Y", V_AIMY, ay)
    set_ok = b_setvar(bs, "조준있음", V_AIMOK, 1)
    chain([(set_ad, bs[set_ad]), (set_ax, bs[set_ax]), (set_ay, bs[set_ay]), (set_ok, bs[set_ok])])
    if_cl = b_if(bs, closer, set_ad)
    if_aim = b_if(bs, can_aim, if_cl)
    chain([(ha, bs[ha]), (if_aim, bs[if_aim])])

    # 폭탄 폭발 피격
    hp = gen(); bs[hp] = mk("event_whenbroadcastreceived", top=True, x=520, y=400,
        fields={"BROADCAST_OPTION": ["폭탄폭발", BR_BOMBBOOM]})
    alive2 = cmp_op("operator_gt", vrep("보스체력", V_BOSSHP), 0)
    def dxy(axis_op, bomb_vid, bomb_name):
        p = gen(); bs[p] = mk(axis_op)
        return op("operator_subtract", p, vrep(bomb_name, bomb_vid))
    def d2(axis_op, bomb_vid, bomb_name):
        a = dxy(axis_op, bomb_vid, bomb_name)
        b = dxy(axis_op, bomb_vid, bomb_name)
        return op("operator_multiply", a, b)
    sumd = op("operator_add",
              d2("motion_xposition", V_BOMBX, "폭탄X"),
              d2("motion_yposition", V_BOMBY, "폭탄Y"))
    dist2 = gen(); bs[dist2] = mk("operator_mathop",
        inputs={"NUM": slot(sumd)}, fields={"OPERATOR": ["sqrt", None]})
    bs[sumd]["parent"] = dist2
    near = cmp_op("operator_lt", dist2, vrep("폭탄반경", V_PULSER))
    can_b = bool_op("operator_and", alive2, near)
    dmg3 = op("operator_multiply", vrep("공격력", V_ATK), 3)
    set_d = b_setvar(bs, "피격데미지", V_HITDMG, dmg3)
    neg = op("operator_subtract", 0, vrep("피격데미지", V_HITDMG))
    ch = b_changevar(bs, "보스체력", V_BOSSHP, neg)
    hit_snd = b_sound(bs, "hit")
    brt = gen(); bs[brt] = mk("looks_seteffectto",
        inputs={"VALUE": num(100)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    set_dv = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("피격데미지", V_HITDMG))
    xx = gen(); bs[xx] = mk("motion_xposition")
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, xx)
    yy = gen(); bs[yy] = mk("motion_yposition")
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, yy)
    set_k = b_setvar(bs, "데미지종류", V_DMGKIND, 1)
    bc = b_broadcast(bs, "데미지표시", BR_DMG)
    bc_fx = b_broadcast(bs, "타격효과", BR_HITFX)
    chain([(set_d, bs[set_d]), (ch, bs[ch]), (hit_snd, bs[hit_snd]), (brt, bs[brt]),
           (set_dv, bs[set_dv]), (set_dx, bs[set_dx]), (set_dy, bs[set_dy]),
           (set_k, bs[set_k]), (bc, bs[bc]), (bc_fx, bs[bc_fx])])
    if_bb = b_if(bs, can_b, set_d)
    chain([(hp, bs[hp]), (if_bb, bs[if_bb])])
    return bs


def build_boss_bullet_blocks():
    """보스탄 — 플레이어 방향 직진, 닿으면 데미지."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    s0 = b_setvar(bs, "복제됨", V_BBISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (s0, bs[s0])])

    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["보스사격", BR_BFIRE]})
    if_sp = b_if(bs, cmp_op("operator_equals", vrep("복제됨", V_BBISC), 0),
                 b_create_clone(bs, "_myself_"))
    chain([(hf, bs[hf]), (if_sp, bs[if_sp])])

    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=20, y=240)
    set_isc = b_setvar(bs, "복제됨", V_BBISC, 1)
    go = b_gotoxy(bs, vrep("보스탄X", V_BBX), vrep("보스탄Y", V_BBY))
    # 부채꼴/필살기 방향 사용
    dir_v = vrep("보스탄방향", V_BBDIR)
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": slot(dir_v)})
    bs[dir_v]["parent"] = pdir
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    sh = gen(); bs[sh] = mk("looks_show")
    # 탄속: 기본 7, 웨이브 높을수록 +0.3 per tier
    spd = op("operator_add", 7, op("operator_multiply",
            op("operator_divide", vrep("웨이브", V_WAVE), 5), 0.5))
    mv = b_movesteps(bs, spd)
    # player hit
    touch = b_touching(bs, "내로봇")
    inv0 = cmp_op("operator_equals", vrep("무적", V_INVT), 0)
    play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    can = bool_op("operator_and", bool_op("operator_and", touch, inv0), play)
    ch_hp = b_changevar(bs, "체력", V_HP, -1)
    set_inv = b_setvar(bs, "무적", V_INVT, vrep("무적시간", V_INV))
    hurt = b_sound(bs, "hurt")
    set_dv = b_setvar(bs, "데미지표시값", V_DMGVAL, 1)
    px = b_of(bs, "내로봇", "x position")
    py = b_of(bs, "내로봇", "y position")
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, px)
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, py)
    set_k = b_setvar(bs, "데미지종류", V_DMGKIND, 0)
    bc = b_broadcast(bs, "데미지표시", BR_DMG)
    del_h = gen(); bs[del_h] = mk("control_delete_this_clone")
    chain([(ch_hp, bs[ch_hp]), (set_inv, bs[set_inv]), (hurt, bs[hurt]),
           (set_dv, bs[set_dv]), (set_dx, bs[set_dx]), (set_dy, bs[set_dy]),
           (set_k, bs[set_k]), (bc, bs[bc]), (del_h, bs[del_h])])
    if_hit = b_if(bs, can, ch_hp)
    edge_m = gen(); bs[edge_m] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc_e = gen(); bs[tc_e] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge_m]})
    bs[edge_m]["parent"] = tc_e
    del_e = gen(); bs[del_e] = mk("control_delete_this_clone")
    if_edge = b_if(bs, tc_e, del_e)
    w = b_wait(bs, 0.02)
    chain([(mv, bs[mv]), (if_hit, bs[if_hit]), (if_edge, bs[if_edge]), (w, bs[w])])
    edge2 = gen(); bs[edge2] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["_edge_", None]}, shadow=True)
    tc2 = gen(); bs[tc2] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, edge2]})
    bs[edge2]["parent"] = tc2
    stop = bool_op("operator_or", tc2, cmp_op("operator_equals", vrep("게임상태", V_STATE), 0))
    ru = gen(); bs[ru] = mk("control_repeat_until",
        inputs={"CONDITION": [2, stop], "SUBSTACK": [2, mv]})
    bs[stop]["parent"] = ru; bs[mv]["parent"] = ru
    del_end = gen(); bs[del_end] = mk("control_delete_this_clone")
    chain([(sc, bs[sc]), (set_isc, bs[set_isc]), (go, bs[go]), (pdir, bs[pdir]),
           (sz, bs[sz]), (sh, bs[sh]), (ru, bs[ru]), (del_end, bs[del_end])])
    return bs


# ============================================================
#  적로봇
# ============================================================
def build_enemy_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    s0 = b_setvar(bs, "복제됨", V_EIS, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (s0, bs[s0])])

    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["적스폰", BR_SPAWN]})
    if_c = b_if(bs, cmp_op("operator_equals", vrep("복제됨", V_EIS), 0),
                b_create_clone(bs, "_myself_"))
    chain([(hs, bs[hs]), (if_c, bs[if_c])])

    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=20, y=260)
    set_isc = b_setvar(bs, "복제됨", V_EIS, 1)
    set_hit = b_setvar(bs, "피격쿨", V_EHIT, 0)
    set_typ = b_setvar(bs, "적종류", V_ETYPE, vrep("적생성종류", V_SPTYPE))
    set_hp = b_setvar(bs, "내체력", V_EHP, vrep("약한적_체력", V_EHPW))
    set_sp = b_setvar(bs, "내속도", V_ESPD, vrep("약한적_속도", V_ESPW))
    cm1 = gen(); bs[cm1] = mk("looks_costume", fields={"COSTUME": ["약", None]}, shadow=True)
    sw1 = gen(); bs[sw1] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm1]})
    bs[cm1]["parent"] = sw1
    sz1 = gen(); bs[sz1] = mk("looks_setsizeto", inputs={"SIZE": num(48)})

    def tier_if(typ, hp_name, hp_id, sp_name, sp_id, cos, size):
        c = cmp_op("operator_equals", vrep("적종류", V_ETYPE), typ)
        s_hp = b_setvar(bs, "내체력", V_EHP, vrep(hp_name, hp_id))
        s_sp = b_setvar(bs, "내속도", V_ESPD, vrep(sp_name, sp_id))
        cm = gen(); bs[cm] = mk("looks_costume", fields={"COSTUME": [cos, None]}, shadow=True)
        sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm]})
        bs[cm]["parent"] = sw
        sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(size)})
        chain([(s_hp, bs[s_hp]), (s_sp, bs[s_sp]), (sw, bs[sw]), (sz, bs[sz])])
        return b_if(bs, c, s_hp)

    if2 = tier_if(2, "중간적_체력", V_EHPM, "중간적_속도", V_ESPM, "중", 55)
    if3 = tier_if(3, "강한적_체력", V_EHPS, "강한적_속도", V_ESPS, "강", 62)

    ch_ehp = b_changevar(bs, "내체력", V_EHP,
        op("operator_multiply", op("operator_subtract", vrep("웨이브", V_WAVE), 1),
           vrep("적체력증가", V_EHPSCALE)))
    ch_esp = b_changevar(bs, "내속도", V_ESPD,
        op("operator_multiply", op("operator_subtract", vrep("웨이브", V_WAVE), 1),
           vrep("적속도증가", V_ESPSCALE)))
    go = b_gotoxy(bs, vrep("적생성X", V_SPX), vrep("적생성Y", V_SPY))
    show = gen(); bs[show] = mk("looks_show")

    # AI loop
    st1 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    aim = b_pointtowards(bs, "내로봇")
    mv = b_movesteps(bs, vrep("내속도", V_ESPD))

    # --- 공통: 폭발 사망 시퀀스 빌더 ---
    def make_kill_seq():
        ch_sc = b_changevar(bs, "점수", V_SCORE, 1)
        ch_al = b_changevar(bs, "적수", V_ALIVE, -1)
        boom = b_sound(bs, "explode")
        exm = gen(); bs[exm] = mk("looks_costume", fields={"COSTUME": ["폭발", None]}, shadow=True)
        sw_ex = gen(); bs[sw_ex] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, exm]})
        bs[exm]["parent"] = sw_ex
        set_sz = gen(); bs[set_sz] = mk("looks_setsizeto", inputs={"SIZE": num(55)})
        clr_gh = gen(); bs[clr_gh] = mk("looks_seteffectto",
            inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
        ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(10)})
        ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
            inputs={"CHANGE": num(18)}, fields={"EFFECT": ["GHOST", None]})
        w_an = b_wait(bs, 0.03)
        chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
        rep_an = gen(); bs[rep_an] = mk("control_repeat",
            inputs={"TIMES": num(6), "SUBSTACK": [2, ch_sz]})
        bs[ch_sz]["parent"] = rep_an
        dell = gen(); bs[dell] = mk("control_delete_this_clone")
        chain([(ch_sc, bs[ch_sc]), (ch_al, bs[ch_al]), (boom, bs[boom]),
               (sw_ex, bs[sw_ex]), (set_sz, bs[set_sz]), (clr_gh, bs[clr_gh]),
               (rep_an, bs[rep_an]), (dell, bs[dell])])
        return ch_sc

    def make_hit_if(touch_name, dmg_reporter_fn):
        """touch_name 스프라이트에 닿고 피격쿨=0이면 데미지·타격음·플래시·스파크·팝업·사망."""
        touch = b_touching(bs, touch_name)
        can = bool_op("operator_and", touch,
                      cmp_op("operator_equals", vrep("피격쿨", V_EHIT), 0))
        dmg_val = dmg_reporter_fn()
        set_hit = b_setvar(bs, "피격데미지", V_HITDMG, dmg_val)
        neg = op("operator_subtract", 0, vrep("피격데미지", V_HITDMG))
        dmg = b_changevar(bs, "내체력", V_EHP, neg)
        set_hcd = b_setvar(bs, "피격쿨", V_EHIT, 5)
        # 타격음 + 밝기 플래시
        hit_snd = b_sound(bs, "hit")
        brt = gen(); bs[brt] = mk("looks_seteffectto",
            inputs={"VALUE": num(90)}, fields={"EFFECT": ["BRIGHTNESS", None]})
        set_dval = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("피격데미지", V_HITDMG))
        xp = gen(); bs[xp] = mk("motion_xposition")
        set_dx = b_setvar(bs, "데미지표시x", V_DMGX, xp)
        yp = gen(); bs[yp] = mk("motion_yposition")
        set_dy = b_setvar(bs, "데미지표시y", V_DMGY, yp)
        set_kind1 = b_setvar(bs, "데미지종류", V_DMGKIND, 1)
        bc_dmg = b_broadcast(bs, "데미지표시", BR_DMG)
        bc_fx = b_broadcast(bs, "타격효과", BR_HITFX)
        # 살짝 뒤로 튕김 (타격감)
        knock_mv = b_movesteps(bs, -5)
        kill_head = make_kill_seq()
        if_dead = b_if(bs, cmp_op("operator_lt", vrep("내체력", V_EHP), 1), kill_head)
        chain([(set_hit, bs[set_hit]), (dmg, bs[dmg]), (set_hcd, bs[set_hcd]),
               (hit_snd, bs[hit_snd]), (brt, bs[brt]), (knock_mv, bs[knock_mv]),
               (set_dval, bs[set_dval]), (set_dx, bs[set_dx]), (set_dy, bs[set_dy]),
               (set_kind1, bs[set_kind1]), (bc_dmg, bs[bc_dmg]), (bc_fx, bs[bc_fx]),
               (if_dead, bs[if_dead])])
        return b_if(bs, can, set_hit)

    if_mis = make_hit_if("미사일", lambda: vrep("공격력", V_ATK))
    # 레이저 데미지 = 공격력 + 레이저레벨
    if_las = make_hit_if("레이저", lambda: op("operator_add", vrep("공격력", V_ATK), vrep("레이저레벨", V_LASER)))
    # 메가빔 데미지 = 공격력 * 4
    if_meg = make_hit_if("메가빔", lambda: op("operator_multiply", vrep("공격력", V_ATK), 4))

    # 피격 플래시 유지/해제
    hit_on = cmp_op("operator_gt", vrep("피격쿨", V_EHIT), 0)
    brt_on = gen(); bs[brt_on] = mk("looks_seteffectto",
        inputs={"VALUE": num(70)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    brt_off = gen(); bs[brt_off] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    if_flash = b_ifelse(bs, hit_on, brt_on, brt_off)

    # 플레이어 접촉 데미지
    touch_p = b_touching(bs, "내로봇")
    can_p = bool_op("operator_and",
        bool_op("operator_and", touch_p, cmp_op("operator_equals", vrep("무적", V_INVT), 0)),
        cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    ch_php = b_changevar(bs, "체력", V_HP, -1)
    set_inv = b_setvar(bs, "무적", V_INVT, vrep("무적시간", V_INV))
    hurt = b_sound(bs, "hurt")
    # 빨간 데미지 팝업 on player
    set_dval2 = b_setvar(bs, "데미지표시값", V_DMGVAL, 1)
    px = b_of(bs, "내로봇", "x position")
    py = b_of(bs, "내로봇", "y position")
    set_dx2 = b_setvar(bs, "데미지표시x", V_DMGX, px)
    set_dy2 = b_setvar(bs, "데미지표시y", V_DMGY, py)
    set_kind0 = b_setvar(bs, "데미지종류", V_DMGKIND, 0)
    bc_dmg2 = b_broadcast(bs, "데미지표시", BR_DMG)
    chain([(ch_php, bs[ch_php]), (set_inv, bs[set_inv]), (hurt, bs[hurt]),
           (set_dval2, bs[set_dval2]), (set_dx2, bs[set_dx2]), (set_dy2, bs[set_dy2]),
           (set_kind0, bs[set_kind0]), (bc_dmg2, bs[bc_dmg2])])
    if_pl = b_if(bs, can_p, ch_php)

    if_hcd = b_if(bs, cmp_op("operator_gt", vrep("피격쿨", V_EHIT), 0),
                  b_changevar(bs, "피격쿨", V_EHIT, -1))
    w = b_wait(bs, 0.03)
    chain([(aim, bs[aim]), (mv, bs[mv]),
           (if_mis, bs[if_mis]), (if_las, bs[if_las]), (if_meg, bs[if_meg]),
           (if_pl, bs[if_pl]), (if_hcd, bs[if_hcd]), (if_flash, bs[if_flash]), (w, bs[w])])
    if_play = b_if(bs, st1, aim)
    del_go = gen(); bs[del_go] = mk("control_delete_this_clone")
    if_go = b_if(bs, cmp_op("operator_equals", vrep("게임상태", V_STATE), 0), del_go)
    w2 = b_wait(bs, 0.04)
    chain([(if_play, bs[if_play]), (if_go, bs[if_go]), (w2, bs[w2])])
    fr = b_forever(bs, if_play)

    chain([(sc, bs[sc]), (set_isc, bs[set_isc]), (set_hit, bs[set_hit]),
           (set_typ, bs[set_typ]), (set_hp, bs[set_hp]), (set_sp, bs[set_sp]),
           (sw1, bs[sw1]), (sz1, bs[sz1]), (if2, bs[if2]), (if3, bs[if3]),
           (ch_ehp, bs[ch_ehp]), (ch_esp, bs[ch_esp]), (go, bs[go]), (show, bs[show]),
           (fr, bs[fr])])

    # 조준요청 — 가장 가까운 적 리덕션
    ha = gen(); bs[ha] = mk("event_whenbroadcastreceived", top=True, x=520, y=260,
        fields={"BROADCAST_OPTION": ["조준요청", BR_AIM]})
    active = bool_op("operator_and",
        cmp_op("operator_equals", vrep("복제됨", V_EIS), 1),
        cmp_op("operator_equals", vrep("게임상태", V_STATE), 1))
    dist = b_distance_to(bs, "내로봇")
    closer = cmp_op("operator_lt", dist, vrep("조준거리", V_AIMD))
    set_ad = b_setvar(bs, "조준거리", V_AIMD, b_distance_to(bs, "내로봇"))
    ax = gen(); bs[ax] = mk("motion_xposition")
    set_ax = b_setvar(bs, "조준X", V_AIMX, ax)
    ay = gen(); bs[ay] = mk("motion_yposition")
    set_ay = b_setvar(bs, "조준Y", V_AIMY, ay)
    set_ok = b_setvar(bs, "조준있음", V_AIMOK, 1)
    chain([(set_ad, bs[set_ad]), (set_ax, bs[set_ax]), (set_ay, bs[set_ay]), (set_ok, bs[set_ok])])
    if_cl = b_if(bs, closer, set_ad)
    if_act = b_if(bs, active, if_cl)
    chain([(ha, bs[ha]), (if_act, bs[if_act])])

    # 폭탄폭발: 폭발 좌표(폭탄X/Y)와의 거리 ≤ 폭탄반경이면 공격력*3
    hp = gen(); bs[hp] = mk("event_whenbroadcastreceived", top=True, x=520, y=420,
        fields={"BROADCAST_OPTION": ["폭탄폭발", BR_BOMBBOOM]})
    is_cl = cmp_op("operator_equals", vrep("복제됨", V_EIS), 1)
    # dist = sqrt((x-폭탄X)^2 + (y-폭탄Y)^2) — 같은 식 2번 만들어 곱
    def dx_block():
        xp = gen(); bs[xp] = mk("motion_xposition")
        return op("operator_subtract", xp, vrep("폭탄X", V_BOMBX))
    def dy_block():
        yp = gen(); bs[yp] = mk("motion_yposition")
        return op("operator_subtract", yp, vrep("폭탄Y", V_BOMBY))
    dx2 = op("operator_multiply", dx_block(), dx_block())
    dy2 = op("operator_multiply", dy_block(), dy_block())
    sumd = op("operator_add", dx2, dy2)
    dist = gen(); bs[dist] = mk("operator_mathop",
        inputs={"NUM": slot(sumd)}, fields={"OPERATOR": ["sqrt", None]})
    bs[sumd]["parent"] = dist
    near = cmp_op("operator_lt", dist, vrep("폭탄반경", V_PULSER))
    can_p = bool_op("operator_and", is_cl, near)
    dmg3 = op("operator_multiply", vrep("공격력", V_ATK), 3)
    set_hd = b_setvar(bs, "피격데미지", V_HITDMG, dmg3)
    negp = op("operator_subtract", 0, vrep("피격데미지", V_HITDMG))
    dmgp = b_changevar(bs, "내체력", V_EHP, negp)
    hit_snd = b_sound(bs, "hit")
    brt = gen(); bs[brt] = mk("looks_seteffectto",
        inputs={"VALUE": num(90)}, fields={"EFFECT": ["BRIGHTNESS", None]})
    set_dval = b_setvar(bs, "데미지표시값", V_DMGVAL, vrep("피격데미지", V_HITDMG))
    xpp = gen(); bs[xpp] = mk("motion_xposition")
    set_dx = b_setvar(bs, "데미지표시x", V_DMGX, xpp)
    ypp = gen(); bs[ypp] = mk("motion_yposition")
    set_dy = b_setvar(bs, "데미지표시y", V_DMGY, ypp)
    set_k = b_setvar(bs, "데미지종류", V_DMGKIND, 1)
    bc = b_broadcast(bs, "데미지표시", BR_DMG)
    bc_fx = b_broadcast(bs, "타격효과", BR_HITFX)
    # kill if dead (compact explosion)
    ch_sc = b_changevar(bs, "점수", V_SCORE, 1)
    ch_al = b_changevar(bs, "적수", V_ALIVE, -1)
    boom = b_sound(bs, "explode")
    exm = gen(); bs[exm] = mk("looks_costume", fields={"COSTUME": ["폭발", None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, exm]})
    bs[exm]["parent"] = sw
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(14)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(18)}, fields={"EFFECT": ["GHOST", None]})
    wa = b_wait(bs, 0.03)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (wa, bs[wa])])
    rep = gen(); bs[rep] = mk("control_repeat", inputs={"TIMES": num(5), "SUBSTACK": [2, ch_sz]})
    bs[ch_sz]["parent"] = rep
    dell = gen(); bs[dell] = mk("control_delete_this_clone")
    chain([(ch_sc, bs[ch_sc]), (ch_al, bs[ch_al]), (boom, bs[boom]), (sw, bs[sw]),
           (rep, bs[rep]), (dell, bs[dell])])
    if_die = b_if(bs, cmp_op("operator_lt", vrep("내체력", V_EHP), 1), ch_sc)
    chain([(set_hd, bs[set_hd]), (dmgp, bs[dmgp]), (hit_snd, bs[hit_snd]), (brt, bs[brt]),
           (set_dval, bs[set_dval]), (set_dx, bs[set_dx]), (set_dy, bs[set_dy]), (set_k, bs[set_k]),
           (bc, bs[bc]), (bc_fx, bs[bc_fx]), (if_die, bs[if_die])])
    if_pulse = b_if(bs, can_p, set_hd)
    chain([(hp, bs[hp]), (if_pulse, bs[if_pulse])])
    return bs

def build_hitfx_blocks():
    """피격 스파크 — 데미지표시 좌표에서 짧게 번쩍."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    s0 = b_setvar(bs, "복제됨", V_HITFXISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (s0, bs[s0])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["타격효과", BR_HITFX]})
    if_sp = b_if(bs, cmp_op("operator_equals", vrep("복제됨", V_HITFXISC), 0),
                 b_create_clone(bs, "_myself_"))
    chain([(hb, bs[hb]), (if_sp, bs[if_sp])])

    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=20, y=280)
    set_isc = b_setvar(bs, "복제됨", V_HITFXISC, 1)
    go = b_gotoxy(bs, vrep("데미지표시x", V_DMGX), vrep("데미지표시y", V_DMGY))
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(55)})
    sh = gen(); bs[sh] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    clr = gen(); bs[clr] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    # 커지며 페이드
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(18)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(16)}, fields={"EFFECT": ["GHOST", None]})
    # 살짝 회전
    ch_dir = gen(); bs[ch_dir] = mk("motion_turnright", inputs={"DEGREES": num(25)})
    ww = b_wait(bs, 0.025)
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (ch_dir, bs[ch_dir]), (ww, bs[ww])])
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(6), "SUBSTACK": [2, ch_sz]})
    bs[ch_sz]["parent"] = rep
    delc = gen(); bs[delc] = mk("control_delete_this_clone")
    chain([(sc, bs[sc]), (set_isc, bs[set_isc]), (go, bs[go]), (sz, bs[sz]),
           (clr, bs[clr]), (front, bs[front]), (sh, bs[sh]), (rep, bs[rep]), (delc, bs[delc])])
    return bs

# ============================================================
#  데미지 팝업
# ============================================================
def build_dmg_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    s0 = b_setvar(bs, "복제됨", V_DMGISC, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (s0, bs[s0])])

    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["데미지표시", BR_DMG]})
    is0 = cmp_op("operator_equals", vrep("복제됨", V_DMGISC), 0)
    dval = vrep("데미지표시값", V_DMGVAL)
    len_b = gen(); bs[len_b] = mk("operator_length", inputs={"STRING": slot(dval)})
    bs[dval]["parent"] = len_b
    set_len = b_setvar(bs, "데미지글자수", V_DMGLEN, len_b)
    set_pos = b_setvar(bs, "데미지자리", V_DMGPOS, 1)
    # repeat length: letter, offset, clone
    pos = vrep("데미지자리", V_DMGPOS)
    dval2 = vrep("데미지표시값", V_DMGVAL)
    letter = gen(); bs[letter] = mk("operator_letter_of",
        inputs={"LETTER": slot(pos), "STRING": slot(dval2)})
    bs[pos]["parent"] = letter; bs[dval2]["parent"] = letter
    set_dig = b_setvar(bs, "데미지숫자", V_DMGDIGIT, letter)
    # offset = (pos-1)*16 - (len-1)*8
    off = op("operator_subtract",
             op("operator_multiply", op("operator_subtract", vrep("데미지자리", V_DMGPOS), 1), 16),
             op("operator_multiply", op("operator_subtract", vrep("데미지글자수", V_DMGLEN), 1), 8))
    set_off = b_setvar(bs, "데미지오프셋", V_DMGOFF, off)
    cc = b_create_clone(bs, "_myself_")
    y0 = b_wait(bs, 0)
    ch_pos = b_changevar(bs, "데미지자리", V_DMGPOS, 1)
    chain([(set_dig, bs[set_dig]), (set_off, bs[set_off]), (cc, bs[cc]),
           (y0, bs[y0]), (ch_pos, bs[ch_pos])])
    ln = vrep("데미지글자수", V_DMGLEN)
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": slot(ln), "SUBSTACK": [2, set_dig]})
    bs[ln]["parent"] = rep; bs[set_dig]["parent"] = rep
    chain([(set_len, bs[set_len]), (set_pos, bs[set_pos]), (rep, bs[rep])])
    if_sp = b_if(bs, is0, set_len)
    chain([(hb, bs[hb]), (if_sp, bs[if_sp])])

    # clone: costume digit, color by kind, float up, fade
    sc = gen(); bs[sc] = mk("control_start_as_clone", top=True, x=20, y=420)
    set_isc = b_setvar(bs, "복제됨", V_DMGISC, 1)
    # costume index: if kind=0 red digits 1-10 (costume names d0-d9), kind=1 yellow y0-y9
    # Scratch costume by name "d0"..."d9" / "y0"..."y9"
    def text_slot(s):
        return [1, [10, str(s)]]
    kind0 = cmp_op("operator_equals", vrep("데미지종류", V_DMGKIND), 0)
    dig_r = vrep("데미지숫자", V_DMGDIGIT)
    join_d = gen()
    bs[join_d] = mk("operator_join",
        inputs={"STRING1": text_slot("d"), "STRING2": slot(dig_r)})
    bs[dig_r]["parent"] = join_d
    dig_r2 = vrep("데미지숫자", V_DMGDIGIT)
    join_y = gen()
    bs[join_y] = mk("operator_join",
        inputs={"STRING1": text_slot("y"), "STRING2": slot(dig_r2)})
    bs[dig_r2]["parent"] = join_y
    sw_d = gen(); bs[sw_d] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [3, join_d, [10, "d0"]]})
    bs[join_d]["parent"] = sw_d
    sw_y = gen(); bs[sw_y] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [3, join_y, [10, "y0"]]})
    bs[join_y]["parent"] = sw_y
    if_cos = b_ifelse(bs, kind0, sw_d, sw_y)

    x_pos = op("operator_add", vrep("데미지표시x", V_DMGX), vrep("데미지오프셋", V_DMGOFF))
    go = b_gotoxy(bs, x_pos, vrep("데미지표시y", V_DMGY))
    # 타격감 위해 더 크게 시작
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(140)})
    sh = gen(); bs[sh] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    # float up + fade (더 빠르게 위로)
    cy = gen(); bs[cy] = mk("motion_changeyby", inputs={"DY": num(6)})
    gh = gen(); bs[gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(11)}, fields={"EFFECT": ["GHOST", None]})
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(-4)})
    ww = b_wait(bs, 0.035)
    chain([(cy, bs[cy]), (gh, bs[gh]), (ch_sz, bs[ch_sz]), (ww, bs[ww])])
    repf = gen(); bs[repf] = mk("control_repeat",
        inputs={"TIMES": num(12), "SUBSTACK": [2, cy]})
    bs[cy]["parent"] = repf
    delc = gen(); bs[delc] = mk("control_delete_this_clone")
    chain([(sc, bs[sc]), (set_isc, bs[set_isc]), (if_cos, bs[if_cos]),
           (go, bs[go]), (sz, bs[sz]), (front, bs[front]), (sh, bs[sh]),
           (repf, bs[repf]), (delc, bs[delc])])
    return bs

# ============================================================
#  강화 — 랜덤 3장 택1 (풀 6종)
#  1공격 2연사 3여러발 4관통 5레이저+ 6스킬쿨-
# ============================================================
def build_card_blocks():
    """배너: 랜덤 뽑기 + 1/2/3 입력 + 적용 + 다음웨이브."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = b_gotoxy(bs, 0, 120)
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g])])

    hw = gen(); bs[hw] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["웨이브클리어", BR_WAVECLR]})
    # 카드1 = random 1..6
    r1 = gen(); bs[r1] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_c1 = b_setvar(bs, "카드1", V_CARD1, r1)
    # 카드2 != 카드1
    r2 = gen(); bs[r2] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_c2 = b_setvar(bs, "카드2", V_CARD2, r2)
    same12 = cmp_op("operator_equals", vrep("카드2", V_CARD2), vrep("카드1", V_CARD1))
    # repeat until different: simple retry loop
    r2b = gen(); bs[r2b] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_c2b = b_setvar(bs, "카드2", V_CARD2, r2b)
    w0 = b_wait(bs, 0)
    chain([(set_c2b, bs[set_c2b]), (w0, bs[w0])])
    # use repeat until 카드2 != 카드1
    c2v = vrep("카드2", V_CARD2); c1v = vrep("카드1", V_CARD1)
    eq12 = cmp_op("operator_equals", c2v, c1v)
    # repeat until NOT equal
    not_eq = gen(); bs[not_eq] = mk("operator_not", inputs={"OPERAND": [2, eq12]})
    bs[eq12]["parent"] = not_eq
    # body: re-roll
    r2c = gen(); bs[r2c] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_c2c = b_setvar(bs, "카드2", V_CARD2, r2c)
    ru2 = gen(); bs[ru2] = mk("control_repeat_until",
        inputs={"CONDITION": [2, not_eq], "SUBSTACK": [2, set_c2c]})
    bs[not_eq]["parent"] = ru2; bs[set_c2c]["parent"] = ru2

    r3 = gen(); bs[r3] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_c3 = b_setvar(bs, "카드3", V_CARD3, r3)
    # until c3 != c1 and c3 != c2
    r3c = gen(); bs[r3c] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
    set_c3c = b_setvar(bs, "카드3", V_CARD3, r3c)
    ne31 = cmp_op("operator_equals", vrep("카드3", V_CARD3), vrep("카드1", V_CARD1))
    ne32 = cmp_op("operator_equals", vrep("카드3", V_CARD3), vrep("카드2", V_CARD2))
    bad3 = bool_op("operator_or", ne31, ne32)
    good3 = gen(); bs[good3] = mk("operator_not", inputs={"OPERAND": [2, bad3]})
    bs[bad3]["parent"] = good3
    ru3 = gen(); bs[ru3] = mk("control_repeat_until",
        inputs={"CONDITION": [2, good3], "SUBSTACK": [2, set_c3c]})
    bs[good3]["parent"] = ru3; bs[set_c3c]["parent"] = ru3

    br_ui = b_broadcast(bs, "카드갱신", BR_CARDUI)
    sh = gen(); bs[sh] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    k1 = b_keypressed(bs, "1"); k2 = b_keypressed(bs, "2"); k3 = b_keypressed(bs, "3")
    anyk = bool_op("operator_or", bool_op("operator_or", k1, k2), k3)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, anyk]})
    bs[anyk]["parent"] = wu

    # 선택 → 강화타입
    set_t1 = b_setvar(bs, "강화타입", V_UPTYPE, vrep("카드1", V_CARD1))
    if_k1 = b_if(bs, b_keypressed(bs, "1"), set_t1)
    set_t2 = b_setvar(bs, "강화타입", V_UPTYPE, vrep("카드2", V_CARD2))
    if_k2 = b_if(bs, b_keypressed(bs, "2"), set_t2)
    set_t3 = b_setvar(bs, "강화타입", V_UPTYPE, vrep("카드3", V_CARD3))
    if_k3 = b_if(bs, b_keypressed(bs, "3"), set_t3)

    # apply by 강화타입
    def if_type(n, body_head):
        return b_if(bs, cmp_op("operator_equals", vrep("강화타입", V_UPTYPE), n), body_head)

    ap1 = if_type(1, b_changevar(bs, "공격력", V_ATK, vrep("강화량", V_UP)))
    ch_gap = b_changevar(bs, "발사간격", V_FIREGAP, -0.08)
    if_min = b_if(bs, cmp_op("operator_lt", vrep("발사간격", V_FIREGAP), 0.12),
                  b_setvar(bs, "발사간격", V_FIREGAP, 0.12))
    chain([(ch_gap, bs[ch_gap]), (if_min, bs[if_min])])
    ap2 = if_type(2, ch_gap)
    ap3 = if_type(3, b_changevar(bs, "추가발사", V_MULTI, 1))
    ap4 = if_type(4, b_changevar(bs, "관통", V_PIERCE, 1))
    # 5: 레이저+
    ch_las = b_changevar(bs, "레이저레벨", V_LASER, 1)
    # 레이저간격 약간 감소
    ch_lg = b_changevar(bs, "레이저간격", V_LASERGAP, -0.05)
    if_lmin = b_if(bs, cmp_op("operator_lt", vrep("레이저간격", V_LASERGAP), 0.3),
                   b_setvar(bs, "레이저간격", V_LASERGAP, 0.3))
    chain([(ch_las, bs[ch_las]), (ch_lg, bs[ch_lg]), (if_lmin, bs[if_lmin])])
    ap5 = if_type(5, ch_las)
    # 6: 스킬쿨 최대 -1 (하한 4)
    ch_s1 = b_changevar(bs, "메가빔쿨최대", V_SK1MAX, -1)
    ch_s2 = b_changevar(bs, "폭탄쿨최대", V_SK2MAX, -1)
    if_s1 = b_if(bs, cmp_op("operator_lt", vrep("메가빔쿨최대", V_SK1MAX), 4),
                 b_setvar(bs, "메가빔쿨최대", V_SK1MAX, 4))
    if_s2 = b_if(bs, cmp_op("operator_lt", vrep("폭탄쿨최대", V_SK2MAX), 4),
                 b_setvar(bs, "폭탄쿨최대", V_SK2MAX, 4))
    chain([(ch_s1, bs[ch_s1]), (ch_s2, bs[ch_s2]), (if_s1, bs[if_s1]), (if_s2, bs[if_s2])])
    ap6 = if_type(6, ch_s1)

    ch_hp = b_changevar(bs, "체력", V_HP, 1)
    if_cap = b_if(bs, cmp_op("operator_gt", vrep("체력", V_HP), vrep("최대체력", V_MAXHP)),
                  b_setvar(bs, "체력", V_HP, vrep("최대체력", V_MAXHP)))
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    br = b_broadcast(bs, "다음웨이브", BR_NEXT)

    chain([(hw, bs[hw]), (set_c1, bs[set_c1]), (set_c2, bs[set_c2]), (ru2, bs[ru2]),
           (set_c3, bs[set_c3]), (ru3, bs[ru3]), (br_ui, bs[br_ui]),
           (front, bs[front]), (sh, bs[sh]), (wu, bs[wu]),
           (if_k1, bs[if_k1]), (if_k2, bs[if_k2]), (if_k3, bs[if_k3]),
           (ap1, bs[ap1]), (ap2, bs[ap2]), (ap3, bs[ap3]), (ap4, bs[ap4]),
           (ap5, bs[ap5]), (ap6, bs[ap6]),
           (ch_hp, bs[ch_hp]), (if_cap, bs[if_cap]), (hi2, bs[hi2]), (br, bs[br])])
    return bs

def build_card_slot_blocks(slot_idx, x_pos, card_var, card_vid):
    """슬롯 스프라이트: 카드갱신 시 코스튬 u1~u6 전환."""
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = b_gotoxy(bs, x_pos, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g])])

    # 웨이브클리어 때 hide until 카드갱신
    hw = gen(); bs[hw] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["웨이브클리어", BR_WAVECLR]})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(hw, bs[hw]), (hi2, bs[hi2])])

    hu = gen(); bs[hu] = mk("event_whenbroadcastreceived", top=True, x=20, y=240,
        fields={"BROADCAST_OPTION": ["카드갱신", BR_CARDUI]})
    # switch costume by card type: u1..u6
    def text_slot(s):
        return [1, [10, str(s)]]
    cv = vrep(card_var, card_vid)
    join = gen()
    bs[join] = mk("operator_join",
        inputs={"STRING1": text_slot("u"), "STRING2": slot(cv)})
    bs[cv]["parent"] = join
    sw = gen(); bs[sw] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [3, join, [10, "u1"]]})
    bs[join]["parent"] = sw
    sh = gen(); bs[sh] = mk("looks_show")
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    # key number label via size
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    chain([(hu, bs[hu]), (sw, bs[sw]), (sz, bs[sz]), (front, bs[front]), (sh, bs[sh])])

    # hide when next wave
    hn = gen(); bs[hn] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION": ["다음웨이브", BR_NEXT]})
    hi3 = gen(); bs[hi3] = mk("looks_hide")
    chain([(hn, bs[hn]), (hi3, bs[hi3])])
    return bs

def build_over_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = b_gotoxy(bs, 0, 0)
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g])])
    hb = gen(); bs[hb] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    c0 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, c0]})
    bs[c0]["parent"] = wu
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(hb, bs[hb]), (wu, bs[wu]), (front, bs[front]), (sh, bs[sh])])
    return bs

# ============================================================
#  MAIN
# ============================================================
def main():
    global _ic
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    def save_svg(svg):
        m = md5_bytes(svg.encode("utf-8"))
        with open(f"{WORK}/{m}.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        return m

    def load_png(name):
        """assets/gen/{name}.png → work dir, returns (md5, w, h) or None."""
        from PIL import Image
        path = os.path.join(ASSETS, "gen", f"{name}.png")
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            data = f.read()
        m = md5_bytes(data)
        with open(f"{WORK}/{m}.png", "wb") as f:
            f.write(data)
        im = Image.open(path)
        w, h = im.size
        return m, w, h

    def costume_png(name, fallback_svg=None, cx=None, cy=None):
        """Prefer generated PNG. Rotation center defaults to image center."""
        loaded = load_png(name)
        if loaded:
            m, w, h = loaded
            return {
                "assetId": m, "md5ext": f"{m}.png", "dataFormat": "png",
                "bitmapResolution": 1,
                # Always use true image center for PNGs (forced cx/cy broke big sprites)
                "rotationCenterX": w // 2,
                "rotationCenterY": h // 2,
            }
        # SVG fallback
        m = save_svg(fallback_svg)
        return {
            "assetId": m, "md5ext": f"{m}.svg", "dataFormat": "svg",
            "bitmapResolution": 1,
            "rotationCenterX": cx or 30, "rotationCenterY": cy or 30,
        }

    # UI stays SVG (text/numbers); game art prefers gen PNG
    c_bg = costume_png("arena", BG_SVG, 240, 180)
    # 주인공 보행 애니: r0(idle)·r1~r4 / l0·l1~l4 (walk_*.png)
    # walk 없으면 기존 player_right/left, 그것도 없으면 SVG
    c_pl_walk = {}
    for d in ("r", "l"):
        for i in range(5):
            walk_name = f"walk_{d}{i}"
            legacy = "player_right" if d == "r" else "player_left"
            if os.path.exists(os.path.join(ASSETS, "gen", f"{walk_name}.png")):
                c_pl_walk[f"{d}{i}"] = costume_png(walk_name, PLAYER_SVG)
            else:
                c_pl_walk[f"{d}{i}"] = costume_png(legacy, PLAYER_SVG)
    c_pl = c_pl_walk["r0"]
    c_ms = costume_png("missile", MISSILE_SVG)
    c_las = costume_png("laser", LASER_SVG)
    c_meg = costume_png("mega", MEGA_SVG)
    c_bomb = costume_png("bomb", BOMB_SVG)
    c_boom = costume_png("explosion", BOMB_BOOM_SVG)
    c_boss = costume_png("boss", BOSS_SVG)
    c_bbul = costume_png("boss_bullet", BOSS_BULLET_SVG)
    c_hit = costume_png("hit_spark", HIT_SPARK_SVG)
    c_icon_l = costume_png("icon_laser", ICON_LASER_SVG)
    c_icon_b = costume_png("icon_bomb", ICON_BOMB_SVG)
    c_e1 = costume_png("enemy_light", ENEMY_LIGHT_SVG)
    c_e2 = costume_png("enemy_mid", ENEMY_MID_SVG)
    c_e3 = costume_png("enemy_heavy", ENEMY_HEAVY_SVG)
    c_ex = costume_png("explosion", EXPLOSION_SVG)
    # 숨은 1px 조준점 (SVG)
    AIM_DOT = """<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4" viewBox="0 0 4 4">
  <circle cx="2" cy="2" r="1" fill="#FF0000" opacity="0.01"/>
</svg>"""
    c_aim = {
        "assetId": save_svg(AIM_DOT), "md5ext": None, "dataFormat": "svg",
        "bitmapResolution": 1, "rotationCenterX": 2, "rotationCenterY": 2,
    }
    c_aim["md5ext"] = f"{c_aim['assetId']}.svg"

    ban_md5 = save_svg(CARD_BANNER_SVG)
    up_md5s = {n: save_svg(svg) for n, svg in UP_CARD_SVGS.items()}
    ov_md5 = save_svg(OVER_SVG)
    hp_md5s = [save_svg(s) for s in HP_SVGS]
    hud_md5 = save_svg(HUD_PANEL_SVG)
    red_md5s = [save_svg(s) for s in DIGIT_RED]
    yel_md5s = [save_svg(s) for s in DIGIT_YEL]

    sound_specs = {
        "missile": synth_missile,
        "laser": synth_laser,
        "mega": synth_mega,
        "boom": synth_boom,
        "bomb_boom": synth_bomb_boom,
        "explode": synth_explode,
        "hurt": synth_hurt,
        "boss_fire": synth_boss_fire,
        "throw": synth_bomb_throw,
        "hit": synth_hit,
    }
    sound_md5 = {}
    sound_len = {}
    for name, fn in sound_specs.items():
        samples = fn()
        data = _wav_bytes(samples)
        m = md5_bytes(data)
        sound_md5[name] = m
        sound_len[name] = len(samples)
        with open(f"{WORK}/{m}.wav", "wb") as f:
            f.write(data)
    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_b = f.read()
    pop_md5 = md5_bytes(pop_b)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_b)

    def build(fn):
        global _ic
        _ic = [0]
        return fn()

    stage_blocks = build(build_stage_blocks)
    player_blocks = build(build_player_blocks)
    missile_blocks = build(build_missile_blocks)
    laser_blocks = build(build_laser_blocks)
    mega_blocks = build(build_mega_blocks)
    aim_blocks = build(build_aim_point_blocks)
    pulse_blocks = build(build_pulse_blocks)
    boss_blocks = build(build_boss_blocks)
    boss_bullet_blocks = build(build_boss_bullet_blocks)
    enemy_blocks = build(build_enemy_blocks)
    hitfx_blocks = build(build_hitfx_blocks)
    dmg_blocks = build(build_dmg_blocks)
    card_blocks = build(build_card_blocks)
    slot1_blocks = build(lambda: build_card_slot_blocks(1, -130, "카드1", V_CARD1))
    slot2_blocks = build(lambda: build_card_slot_blocks(2, 0, "카드2", V_CARD2))
    slot3_blocks = build(lambda: build_card_slot_blocks(3, 130, "카드3", V_CARD3))
    icon_las_blocks = build(lambda: build_skill_icon_blocks(
        "메가빔쿨", V_SK1CD, "메가빔쿨최대", V_SK1MAX, -50, -155))
    icon_bom_blocks = build(lambda: build_skill_icon_blocks(
        "폭탄쿨", V_SK2CD, "폭탄쿨최대", V_SK2MAX, 50, -155))
    hp_ui_blocks = build(build_hp_ui_blocks)
    hud_text_blocks = build(build_hud_text_blocks)
    over_blocks = build(build_over_blocks)

    def snd(name, md5, n=1000):
        return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "",
                "rate": SND_RATE, "sampleCount": n, "md5ext": f"{md5}.wav"}

    def S(name):
        return snd(name, sound_md5[name], max(1, sound_len[name]))

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_ATK: ["공격력", 1], V_FIREGAP: ["발사간격", 0.55], V_MISSPD: ["미사일속도", 10],
            V_PIERCE: ["관통", 1], V_MULTI: ["추가발사", 1], V_MOVE: ["이동속도", 8],
            V_MAXHP: ["최대체력", 5], V_HP: ["체력", 5], V_INV: ["무적시간", 35],
            V_UP: ["강화량", 1], V_WAVEBASE: ["웨이브기본수", 4], V_WAVEADD: ["웨이브증가", 2],
            V_SPAWNGAP: ["스폰간격", 0.85],
            V_EHPW: ["약한적_체력", 1], V_ESPW: ["약한적_속도", 1.25],
            V_EHPM: ["중간적_체력", 3], V_ESPM: ["중간적_속도", 0.95],
            V_EHPS: ["강한적_체력", 7], V_ESPS: ["강한적_속도", 0.65],
            V_EHPSCALE: ["적체력증가", 1], V_ESPSCALE: ["적속도증가", 0.07],
            V_LASER: ["레이저레벨", 0], V_LASERGAP: ["레이저간격", 0.85],
            V_SK1MAX: ["메가빔쿨최대", 8], V_SK2MAX: ["폭탄쿨최대", 10], V_PULSER: ["폭탄반경", 95],
            V_BOSSBASE: ["보스기본체력", 30],
            V_STATE: ["게임상태", 1], V_SCORE: ["점수", 0], V_WAVE: ["웨이브", 1],
            V_TARGET: ["웨이브목표", 4], V_SPAWNED: ["스폰수", 0], V_ALIVE: ["적수", 0],
            V_INVT: ["무적", 0], V_FIREX: ["발사X", 0], V_FIREY: ["발사Y", 0], V_FIREI: ["발사i", 0],
            V_AIMD: ["조준거리", 99999], V_AIMX: ["조준X", 0], V_AIMY: ["조준Y", 0], V_AIMOK: ["조준있음", 0],
            V_SPX: ["적생성X", 0], V_SPY: ["적생성Y", 0], V_SPTYPE: ["적생성종류", 1], V_EDGE: ["변두리", 1],
            V_DMGVAL: ["데미지표시값", 0], V_DMGX: ["데미지표시x", 0], V_DMGY: ["데미지표시y", 0],
            V_DMGDIGIT: ["데미지숫자", 0], V_DMGOFF: ["데미지오프셋", 0],
            V_DMGLEN: ["데미지글자수", 0], V_DMGPOS: ["데미지자리", 0], V_DMGKIND: ["데미지종류", 0],
            V_SK1CD: ["메가빔쿨", 0], V_SK2CD: ["폭탄쿨", 0],
            V_BOMBX: ["폭탄X", 0], V_BOMBY: ["폭탄Y", 0],
            V_CARD1: ["카드1", 1], V_CARD2: ["카드2", 2], V_CARD3: ["카드3", 3],
            V_PICK: ["선택슬롯", 0], V_UPTYPE: ["강화타입", 0], V_HITDMG: ["피격데미지", 1],
            V_TMP2: ["임시2", 0], V_CDGHOST: ["쿨고스트", 0],
            V_BOSSMODE: ["보스모드", 0], V_BOSSHP: ["보스체력", 0],
            V_BOSSDIR: ["보스방향", 1], V_BOSSDIRY: ["보스방향Y", 1],
            V_BOSSCD: ["보사쿨", 0], V_BOSSHIT: ["보스피격쿨", 0],
            V_BBX: ["보스탄X", 0], V_BBY: ["보스탄Y", 0], V_BBDIR: ["보스탄방향", 90],
            V_BOSSMULTI: ["보스탄수", 1], V_BOSSGAP: ["보스간격", 0.75],
            V_BOSSVOLLEY: ["보볼리", 0], V_BOSSFI: ["보스발사i", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작", BR_AIM: "조준요청", BR_FIRE: "발사",
            BR_SPAWN: "적스폰", BR_WAVECLR: "웨이브클리어", BR_NEXT: "다음웨이브", BR_DMG: "데미지표시",
            BR_LASER: "레이저발사", BR_MEGA: "메가빔", BR_PULSE: "폭탄", BR_BOMBBOOM: "폭탄폭발",
            BR_CARDUI: "카드갱신", BR_BOSS: "보스스폰", BR_BFIRE: "보스사격",
            BR_HITFX: "타격효과", BR_AIMSYNC: "조준점갱신",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_bg, "name": "아레나"}],
        "sounds": [snd("pop", pop_md5, 258)],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None
    }

    player = {
        "isStage": False, "name": "내로봇",
        "variables": {
            V_PANIM: ["이동애니", 1],
            V_PFRAME: ["보행프레임", 0],
            V_PTICK: ["보행틱", 0],
            V_PMOVING: ["이동중", 0],
        },
        "lists": {}, "broadcasts": {},
        "blocks": player_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {**c_pl_walk[f"{d}{i}"], "name": f"{d}{i}"}
            for d in ("r", "l") for i in range(5)
        ],
        "sounds": [S("missile"), S("laser"), S("mega"), S("hurt")],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": 0, "size": 48, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    missile = {
        "isStage": False, "name": "미사일",
        "variables": {V_MISISC: ["복제됨", 0], V_MISPIER: ["남은관통", 1], V_MISHITCD: ["관통쿨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": missile_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_ms, "name": "mis"}],
        "sounds": [S("missile")],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 0, "size": 55, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    laser = {
        "isStage": False, "name": "레이저",
        "variables": {V_LASISC: ["복제됨", 0], V_LASPIER: ["남은관통", 1], V_LASHITCD: ["관통쿨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": laser_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_las, "name": "las"}],
        "sounds": [S("laser")],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 0, "size": 50, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    mega = {
        "isStage": False, "name": "메가빔",
        "variables": {V_MEGISC: ["복제됨", 0], V_MEGPIER: ["남은관통", 1], V_MEGHITCD: ["관통쿨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": mega_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_meg, "name": "mega"}],
        "sounds": [S("mega")],
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 0, "size": 90, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    aim_point = {
        "isStage": False, "name": "조준점",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": aim_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_aim, "name": "dot"}],
        "sounds": [], "volume": 100, "layerOrder": 1, "visible": False,
        "x": 0, "y": 0, "size": 5, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    pulse = {
        "isStage": False, "name": "폭탄",
        "variables": {V_PULISC: ["복제됨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": pulse_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {**c_bomb, "name": "bomb"},
            {**c_boom, "name": "boom"},
        ],
        "sounds": [S("throw"), S("bomb_boom")],
        "volume": 100, "layerOrder": 7, "visible": False,
        "x": 0, "y": 0, "size": 75, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    boss = {
        "isStage": False, "name": "보스",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": boss_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_boss, "name": "boss"}],
        "sounds": [S("boss_fire"), S("explode"), S("hit")],
        "volume": 100, "layerOrder": 5, "visible": False,
        "x": 0, "y": 130, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    boss_bullet = {
        "isStage": False, "name": "보스탄",
        "variables": {V_BBISC: ["복제됨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": boss_bullet_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_bbul, "name": "bb"}],
        "sounds": [S("hurt")],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 0, "size": 50, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    icon_laser = {
        "isStage": False, "name": "아이콘레이저",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": icon_las_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_icon_l, "name": "icon"}],
        "sounds": [], "volume": 100, "layerOrder": 12, "visible": True,
        "x": -50, "y": -155, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    icon_bomb = {
        "isStage": False, "name": "아이콘폭탄",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": icon_bom_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_icon_b, "name": "icon"}],
        "sounds": [], "volume": 100, "layerOrder": 12, "visible": True,
        "x": 50, "y": -155, "size": 85, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    hp_ui = {
        "isStage": False, "name": "체력UI",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hp_ui_blocks, "comments": {},
        "currentCostume": 5,
        "costumes": [
            {"name": f"hp{i}", "bitmapResolution": 1, "dataFormat": "svg",
             "assetId": hp_md5s[i], "md5ext": f"{hp_md5s[i]}.svg",
             "rotationCenterX": 80, "rotationCenterY": 20}
            for i in range(6)
        ],
        "sounds": [], "volume": 100, "layerOrder": 12, "visible": True,
        "x": -150, "y": 155, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    hud_text = {
        "isStage": False, "name": "점수판",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": hud_text_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{"name": "panel", "bitmapResolution": 1, "dataFormat": "svg",
                      "assetId": hud_md5, "md5ext": f"{hud_md5}.svg",
                      "rotationCenterX": 100, "rotationCenterY": 35}],
        "sounds": [], "volume": 100, "layerOrder": 11, "visible": True,
        "x": -80, "y": 155, "size": 90, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    enemy = {
        "isStage": False, "name": "적로봇",
        "variables": {V_EIS: ["복제됨", 0], V_EHP: ["내체력", 1], V_ESPD: ["내속도", 1],
                      V_ETYPE: ["적종류", 1], V_EHIT: ["피격쿨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {**c_e1, "name": "약"},
            {**c_e2, "name": "중"},
            {**c_e3, "name": "강"},
            {**c_ex, "name": "폭발"},
        ],
        "sounds": [S("explode"), S("hurt"), S("hit")],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 50, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    hitfx = {
        "isStage": False, "name": "타격스파크",
        "variables": {V_HITFXISC: ["복제됨", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": hitfx_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{**c_hit, "name": "spark"}],
        "sounds": [], "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": 0, "size": 70, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    dmg_costumes = []
    for i, m in enumerate(red_md5s):
        dmg_costumes.append({"name": f"d{i}", "bitmapResolution": 1, "dataFormat": "svg",
                             "assetId": m, "md5ext": f"{m}.svg",
                             "rotationCenterX": 18, "rotationCenterY": 24})
    for i, m in enumerate(yel_md5s):
        dmg_costumes.append({"name": f"y{i}", "bitmapResolution": 1, "dataFormat": "svg",
                             "assetId": m, "md5ext": f"{m}.svg",
                             "rotationCenterX": 18, "rotationCenterY": 24})

    dmg = {
        "isStage": False, "name": "데미지",
        "variables": {V_DMGISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": dmg_blocks, "comments": {},
        "currentCostume": 0, "costumes": dmg_costumes,
        "sounds": [], "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    card = {
        "isStage": False, "name": "강화배너",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": card_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{"name": "banner", "bitmapResolution": 1, "dataFormat": "svg",
                      "assetId": ban_md5, "md5ext": f"{ban_md5}.svg",
                      "rotationCenterX": 210, "rotationCenterY": 25}],
        "sounds": [snd("pop", pop_md5, 258)],
        "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": 120, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    def make_slot(name, blocks, x):
        costumes = []
        for n in range(1, 7):
            m = up_md5s[n]
            costumes.append({"name": f"u{n}", "bitmapResolution": 1, "dataFormat": "svg",
                             "assetId": m, "md5ext": f"{m}.svg",
                             "rotationCenterX": 55, "rotationCenterY": 70})
        return {
            "isStage": False, "name": name,
            "variables": {}, "lists": {}, "broadcasts": {},
            "blocks": blocks, "comments": {},
            "currentCostume": 0, "costumes": costumes,
            "sounds": [], "volume": 100, "layerOrder": 10, "visible": False,
            "x": x, "y": 0, "size": 100, "direction": 90,
            "draggable": False, "rotationStyle": "don't rotate"
        }

    slot1 = make_slot("카드슬롯1", slot1_blocks, -130)
    slot2 = make_slot("카드슬롯2", slot2_blocks, 0)
    slot3 = make_slot("카드슬롯3", slot3_blocks, 130)

    over = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": over_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{"name": "over", "bitmapResolution": 1, "dataFormat": "svg",
                      "assetId": ov_md5, "md5ext": f"{ov_md5}.svg",
                      "rotationCenterX": 180, "rotationCenterY": 75}],
        "sounds": [snd("pop", pop_md5, 258)],
        "volume": 100, "layerOrder": 10, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    # 변수 모니터 전부 숨김 — 체력UI·점수판·스킬 아이콘으로 대체
    monitors = []

    project = {
        "targets": [stage, player, missile, laser, mega, aim_point, pulse, boss, boss_bullet,
                    enemy, hitfx, dmg, card, slot1, slot2, slot3,
                    icon_laser, icon_bomb, hp_ui, hud_text, over],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "robot-shooter-v9-walk"}
    }
    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    totals = [("stage", stage_blocks), ("player", player_blocks), ("missile", missile_blocks),
              ("laser", laser_blocks), ("mega", mega_blocks), ("aim", aim_blocks),
              ("pulse", pulse_blocks),
              ("boss", boss_blocks), ("bbul", boss_bullet_blocks),
              ("enemy", enemy_blocks), ("hitfx", hitfx_blocks), ("dmg", dmg_blocks), ("card", card_blocks),
              ("slot1", slot1_blocks), ("slot2", slot2_blocks), ("slot3", slot3_blocks),
              ("iconL", icon_las_blocks), ("iconB", icon_bom_blocks),
              ("hpUI", hp_ui_blocks), ("hud", hud_text_blocks), ("over", over_blocks)]
    print(f"wrote {OUTPUT}")
    t = 0
    for nm, b in totals:
        print(f"  {nm:10s}: {len(b)} blocks"); t += len(b)
    print(f"  TOTAL    : {t} blocks")

if __name__ == "__main__":
    main()
