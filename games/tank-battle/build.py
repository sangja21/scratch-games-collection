#!/usr/bin/env python3
"""Tank Battle — top-down solo SURVIVAL.

Arrows = move in that direction, space = fire. You are one tank against an
endless stream of red enemy tanks that spawn at random spots and chase you.
Enemies die in ONE hit (점수 +1 each). Survive as long as you can — when your
HP (내체력) hits 0 it's game over. Many scattered cover walls to hide behind.

Art is drawn pointing UP then rotated +90° so it faces RIGHT (Scratch "all
around" treats a costume as facing direction 90); otherwise sprites render 90°
off and shells look like they fly sideways. Hit detection is touch-based; the
old shared-HP + invincibility-frames enemy made the final hit feel unreliable,
so this design uses one-hit kills per clone instead.
"""
import json, os, zipfile, shutil, hashlib, random, math

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "탱크_배틀.sb3")

# ============================================================
#  SVG assets
# ============================================================

# -------- Background: sandy desert tiles + pebbles --------
random.seed(7)
tiles = []
for ty in range(0, 360, 40):
    for tx in range(0, 480, 40):
        shade = "#E0C68A" if (tx // 40 + ty // 40) % 2 == 0 else "#D6B775"
        tiles.append(f'<rect x="{tx}" y="{ty}" width="40" height="40" fill="{shade}"/>')
TILES = "\n    ".join(tiles)

dots = []
for _ in range(36):
    x = random.randint(8, 472); y = random.randint(8, 352)
    r = random.uniform(1.2, 2.6)
    dots.append(f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="#8D6E63" opacity="0.5"/>')
DOTS = "\n    ".join(dots)

pebbles = []
for _ in range(22):
    x = random.randint(10, 470); y = random.randint(10, 350)
    rx = random.uniform(2.5, 4.5); ry = random.uniform(1.8, 3.0)
    pebbles.append(
        f'<ellipse cx="{x}" cy="{y}" rx="{rx:.1f}" ry="{ry:.1f}" '
        f'fill="#A1887F" stroke="#5D4037" stroke-width="0.6" opacity="0.7"/>'
    )
PEBBLES = "\n    ".join(pebbles)

tracks = []
for cx, cy, rot in [(120, 90, -25), (340, 240, 15), (220, 310, 40)]:
    for i in range(-3, 4):
        offx = i * 6
        tracks.append(
            f'<rect x="{cx + offx - 1}" y="{cy - 4}" width="3" height="8" '
            f'fill="#6D4C41" opacity="0.35" transform="rotate({rot} {cx} {cy})"/>'
        )
TRACKS = "\n    ".join(tracks)

BG_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <g>
    {TILES}
  </g>
  <g>
    {TRACKS}
  </g>
  <g>
    {DOTS}
  </g>
  <g>
    {PEBBLES}
  </g>
</svg>"""

# -------- Player tank (top-down). Art drawn pointing UP, then rotated +90° so it
#          points RIGHT — Scratch "all around" treats the costume as facing right
#          (direction 90). Without this the sprite renders 90° off (shells looked
#          like they flew sideways). --------
TANK_PLAYER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
 <g transform="rotate(90 30 30)">
  <!-- shadow -->
  <ellipse cx="30" cy="52" rx="20" ry="3" fill="#000000" opacity="0.25"/>
  <!-- tracks (left + right) -->
  <rect x="6"  y="14" width="10" height="34" rx="3" fill="#37474F" stroke="#1B262C" stroke-width="1.5"/>
  <rect x="44" y="14" width="10" height="34" rx="3" fill="#37474F" stroke="#1B262C" stroke-width="1.5"/>
  <!-- track tread lines -->
  <line x1="6"  y1="20" x2="16" y2="20" stroke="#1B262C" stroke-width="1"/>
  <line x1="6"  y1="26" x2="16" y2="26" stroke="#1B262C" stroke-width="1"/>
  <line x1="6"  y1="32" x2="16" y2="32" stroke="#1B262C" stroke-width="1"/>
  <line x1="6"  y1="38" x2="16" y2="38" stroke="#1B262C" stroke-width="1"/>
  <line x1="44" y1="20" x2="54" y2="20" stroke="#1B262C" stroke-width="1"/>
  <line x1="44" y1="26" x2="54" y2="26" stroke="#1B262C" stroke-width="1"/>
  <line x1="44" y1="32" x2="54" y2="32" stroke="#1B262C" stroke-width="1"/>
  <line x1="44" y1="38" x2="54" y2="38" stroke="#1B262C" stroke-width="1"/>
  <!-- hull -->
  <rect x="14" y="18" width="32" height="28" rx="4" fill="#1976D2" stroke="#0D47A1" stroke-width="2"/>
  <!-- turret -->
  <circle cx="30" cy="32" r="10" fill="#1565C0" stroke="#0D47A1" stroke-width="1.6"/>
  <circle cx="30" cy="32" r="3"  fill="#0D47A1"/>
  <!-- barrel (pointing UP) -->
  <rect x="27" y="6" width="6" height="22" rx="1" fill="#263238" stroke="#0D1B22" stroke-width="1.2"/>
  <rect x="25" y="4" width="10" height="4" fill="#37474F" stroke="#0D1B22" stroke-width="1"/>
  <!-- forward marker -->
  <polygon points="30,2 27,7 33,7" fill="#FFEB3B"/>
  <!-- hatch -->
  <circle cx="22" cy="22" r="2" fill="#0D47A1"/>
 </g>
</svg>"""

# -------- Enemy tank (red) — same +90° rotate to face RIGHT --------
TANK_ENEMY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
 <g transform="rotate(90 30 30)">
  <ellipse cx="30" cy="52" rx="20" ry="3" fill="#000000" opacity="0.25"/>
  <rect x="6"  y="14" width="10" height="34" rx="3" fill="#3E2723" stroke="#1B0F0A" stroke-width="1.5"/>
  <rect x="44" y="14" width="10" height="34" rx="3" fill="#3E2723" stroke="#1B0F0A" stroke-width="1.5"/>
  <line x1="6"  y1="20" x2="16" y2="20" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="6"  y1="26" x2="16" y2="26" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="6"  y1="32" x2="16" y2="32" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="6"  y1="38" x2="16" y2="38" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="44" y1="20" x2="54" y2="20" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="44" y1="26" x2="54" y2="26" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="44" y1="32" x2="54" y2="32" stroke="#1B0F0A" stroke-width="1"/>
  <line x1="44" y1="38" x2="54" y2="38" stroke="#1B0F0A" stroke-width="1"/>
  <rect x="14" y="18" width="32" height="28" rx="4" fill="#C62828" stroke="#7F0000" stroke-width="2"/>
  <circle cx="30" cy="32" r="10" fill="#B71C1C" stroke="#7F0000" stroke-width="1.6"/>
  <circle cx="30" cy="32" r="3"  fill="#7F0000"/>
  <rect x="27" y="6" width="6" height="22" rx="1" fill="#263238" stroke="#0D1B22" stroke-width="1.2"/>
  <rect x="25" y="4" width="10" height="4" fill="#37474F" stroke="#0D1B22" stroke-width="1"/>
  <polygon points="30,2 27,7 33,7" fill="#FFCDD2"/>
  <circle cx="22" cy="22" r="2" fill="#7F0000"/>
 </g>
</svg>"""

# -------- Shell (small dark oblong + yellow tail). Drawn pointing RIGHT
#          (nose at +x = direction 90) to match Scratch "all around". --------
SHELL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="20" viewBox="0 0 16 20">
  <!-- tail spark (left) -->
  <ellipse cx="3" cy="10" rx="2" ry="3" fill="#FFB300" opacity="0.85"/>
  <ellipse cx="2" cy="10" rx="1.2" ry="2" fill="#FFEB3B" opacity="0.95"/>
  <!-- body -->
  <rect x="4" y="7" width="8" height="6" rx="1.5" fill="#37474F" stroke="#000000" stroke-width="1"/>
  <!-- nose (right) -->
  <polygon points="12,7 12,13 16,10" fill="#263238" stroke="#000000" stroke-width="1"/>
</svg>"""

# -------- Enemy shell (red, distinct sprite so it never self-destructs on its
#          firing tank and never gets confused with player shells). Also RIGHT. --------
SHELL_ENEMY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="20" viewBox="0 0 16 20">
  <ellipse cx="3" cy="10" rx="2" ry="3" fill="#FF7043" opacity="0.85"/>
  <ellipse cx="2" cy="10" rx="1.2" ry="2" fill="#FFAB91" opacity="0.95"/>
  <rect x="4" y="7" width="8" height="6" rx="1.5" fill="#B71C1C" stroke="#3E0000" stroke-width="1"/>
  <polygon points="12,7 12,13 16,10" fill="#7F0000" stroke="#3E0000" stroke-width="1"/>
</svg>"""

# -------- Explosion burst (radial → rotation-agnostic, 60x60) --------
def _star_pts(cx, cy, R, r, n, rot=0.0):
    pts = []
    for i in range(2 * n):
        rad = R if i % 2 == 0 else r
        ang = math.pi / n * i + rot
        pts.append(f"{cx + rad*math.cos(ang):.1f},{cy + rad*math.sin(ang):.1f}")
    return " ".join(pts)

EXPLOSION_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
  <polygon points="{_star_pts(30, 30, 29, 12, 12)}" fill="#FF6F00" stroke="#E65100" stroke-width="1"/>
  <polygon points="{_star_pts(30, 30, 22, 9, 12, rot=0.262)}" fill="#FFB300"/>
  <circle cx="30" cy="30" r="12" fill="#FFEB3B"/>
  <circle cx="30" cy="30" r="6"  fill="#FFFFFF"/>
  <circle cx="18" cy="20" r="2.2" fill="#FFF59D"/>
  <circle cx="43" cy="38" r="2.2" fill="#FFF59D"/>
  <circle cx="40" cy="17" r="1.8" fill="#FFE082"/>
</svg>"""

# -------- Cover block (stone wall 50x50) --------
COVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 50 50">
  <rect x="2" y="2" width="46" height="46" rx="3" fill="#9E9E9E" stroke="#424242" stroke-width="2"/>
  <!-- brick lines -->
  <line x1="2"  y1="16" x2="48" y2="16" stroke="#616161" stroke-width="1"/>
  <line x1="2"  y1="32" x2="48" y2="32" stroke="#616161" stroke-width="1"/>
  <line x1="14" y1="2"  x2="14" y2="16" stroke="#616161" stroke-width="1"/>
  <line x1="34" y1="2"  x2="34" y2="16" stroke="#616161" stroke-width="1"/>
  <line x1="24" y1="16" x2="24" y2="32" stroke="#616161" stroke-width="1"/>
  <line x1="14" y1="32" x2="14" y2="48" stroke="#616161" stroke-width="1"/>
  <line x1="34" y1="32" x2="34" y2="48" stroke="#616161" stroke-width="1"/>
  <!-- highlights -->
  <circle cx="10" cy="10" r="1.5" fill="#BDBDBD"/>
  <circle cx="40" cy="42" r="1.5" fill="#BDBDBD"/>
  <circle cx="38" cy="24" r="1.2" fill="#BDBDBD"/>
  <circle cx="12" cy="40" r="1.2" fill="#BDBDBD"/>
</svg>"""

# -------- Result banner: costume 0 = WIN (gold), costume 1 = LOSE (red) --------
RESULT_WIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#1B3A1B" opacity="0.92"
        stroke="#FFD54F" stroke-width="5"/>
  <text x="180" y="72" text-anchor="middle"
        fill="#FFD54F" font-family="Arial, Helvetica, sans-serif"
        font-size="48" font-weight="bold">YOU WIN!</text>
  <text x="180" y="110" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">적 탱크를 격파했어요!</text>
  <text x="180" y="138" text-anchor="middle"
        fill="#C5E1A5" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 클릭</text>
</svg>"""

RESULT_LOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="360" height="160" viewBox="0 0 360 160">
  <rect x="5" y="5" width="350" height="150" rx="14"
        fill="#000000" opacity="0.88"
        stroke="#E53935" stroke-width="5"/>
  <text x="180" y="68" text-anchor="middle"
        fill="#E53935" font-family="Arial, Helvetica, sans-serif"
        font-size="46" font-weight="bold">GAME OVER</text>
  <text x="180" y="104" text-anchor="middle"
        fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif"
        font-size="20">처치 수는 왼쪽 위 점수 확인!</text>
  <text x="180" y="136" text-anchor="middle"
        fill="#FFCDD2" font-family="Arial, Helvetica, sans-serif"
        font-size="14">초록 깃발(▶) 다시 도전</text>
</svg>"""

# ============================================================
#  helpers
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
#  IDs  (V_* / var* 컨벤션)
# ============================================================
V_HP     = "varHP01"      # 내체력  init 3
V_STATE  = "varState03"   # 게임상태 init 1 (1=진행, 0=종료)
V_RESULT = "varResult04"  # 결과     항상 2(패배) — gameover 스프라이트 호환용
V_BX     = "varBX05"      # 포탄X
V_BY     = "varBY06"      # 포탄Y
V_BDIR   = "varBDir07"    # 포탄방향
V_INV    = "varInv08"     # 무적    (틱 카운트)
V_CD     = "varCD10"      # 쿨다운  (틱 카운트)
V_SCORE  = "varScore14"   # 점수    (처치한 적 수)
V_ECNT   = "varECnt15"    # 적수    (현재 살아있는 적 클론 수)
V_SPX    = "varSPX16"     # 적생성X (스폰 좌표 전달 채널)
V_SPY    = "varSPY17"     # 적생성Y
# sprite-local "복제됨" 플래그 (원본=0, 클론=1) — 클론이 방송을 받아도 다시 클론을
# 만들지 않게 가드. 안 그러면 적탱크/엄폐물/적포탄이 기하급수로 증식.
V_EISC  = "varEnemyIsClone11"   # 적탱크 local
V_CVISC = "varCoverIsClone12"   # 엄폐물 local
V_ESISC = "varEShellIsClone13"  # 적포탄 local

BR_START = "brStart01"   # 게임시작 → 적탱크 1대 + 엄폐물 3개
BR_EFIRE = "brEFire02"   # 적사격   → 적포탄 클론 생성

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

# ============================================================
#  STAGE
# ============================================================
def build_stage_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- (A) when flag clicked: init + broadcast 게임시작 ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    inits = []
    for var_pair, val in [
        (("내체력", V_HP),      3),
        (("게임상태", V_STATE), 1),
        (("결과", V_RESULT),    2),
        (("점수", V_SCORE),     0),
        (("적수", V_ECNT),      0),
        (("무적", V_INV),       0),
        (("쿨다운", V_CD),      0),
    ]:
        sid = gen(); bs[sid] = mk("data_setvariableto",
            inputs={"VALUE": num(val)}, fields={"VARIABLE": list(var_pair)})
        inits.append((sid, bs[sid]))

    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(0.3)})

    bm_start = gen(); bs[bm_start] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    bc_start = gen(); bs[bc_start] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_start]})
    bs[bm_start]["parent"] = bc_start

    chain([(h, bs[h])] + inits + [(w1, bs[w1]), (bc_start, bs[bc_start])])

    # --- (B) counter forever: 무적/쿨다운 decrement ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    def dec_if(name, vid):
        v = vrep(name, vid)
        c = cmp_op("operator_gt", v, 0)
        d = gen(); bs[d] = mk("data_changevariableby",
            inputs={"VALUE": num(-1)}, fields={"VARIABLE": [name, vid]})
        iff = gen(); bs[iff] = mk("control_if",
            inputs={"CONDITION": [2, c], "SUBSTACK": [2, d]})
        bs[c]["parent"] = iff; bs[d]["parent"] = iff
        return iff

    if_inv  = dec_if("무적", V_INV)
    if_cd   = dec_if("쿨다운", V_CD)
    w_ctr = gen(); bs[w_ctr] = mk("control_wait", inputs={"DURATION": num(0.04)})

    chain([(if_inv, bs[if_inv]),
           (if_cd, bs[if_cd]), (w_ctr, bs[w_ctr])])
    fe_ctr = gen(); bs[fe_ctr] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_inv]})
    bs[if_inv]["parent"] = fe_ctr
    chain([(h2, bs[h2]), (fe_ctr, bs[fe_ctr])])

    # --- (C) lose watcher forever (서바이벌: 승리 없음, 내체력 0 = 게임오버) ---
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)

    # wait until 게임상태 = 1 (초기화 완료 대기, race 방지)
    state_w = vrep("게임상태", V_STATE)
    cond_alive0 = cmp_op("operator_equals", state_w, 1)
    wu_ready = gen(); bs[wu_ready] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_alive0]})
    bs[cond_alive0]["parent"] = wu_ready

    # if (내체력 < 1) and (게임상태 = 1): 결과=2, 게임상태=0
    hp_v = vrep("내체력", V_HP)
    cond_lose = cmp_op("operator_lt", hp_v, 1)
    state_b = vrep("게임상태", V_STATE)
    cond_pb = cmp_op("operator_equals", state_b, 1)
    cond_los = bool_op("operator_and", cond_lose, cond_pb)
    set_res2 = gen(); bs[set_res2] = mk("data_setvariableto",
        inputs={"VALUE": num(2)}, fields={"VARIABLE": ["결과", V_RESULT]})
    set_st0b = gen(); bs[set_st0b] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["게임상태", V_STATE]})
    chain([(set_res2, bs[set_res2]), (set_st0b, bs[set_st0b])])
    if_lose = gen(); bs[if_lose] = mk("control_if",
        inputs={"CONDITION": [2, cond_los], "SUBSTACK": [2, set_res2]})
    bs[cond_los]["parent"] = if_lose; bs[set_res2]["parent"] = if_lose

    w_watch = gen(); bs[w_watch] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_lose, bs[if_lose]), (w_watch, bs[w_watch])])
    fe_watch = gen(); bs[fe_watch] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_lose]})
    bs[if_lose]["parent"] = fe_watch
    chain([(h3, bs[h3]), (wu_ready, bs[wu_ready]), (fe_watch, bs[fe_watch])])

    return bs

# ============================================================
#  PLAYER TANK
# ============================================================
def build_player_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # --- (A) flag: init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    show = gen(); bs[show] = mk("looks_show")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(75)})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(-120)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    pd = gen(); bs[pd] = mk("motion_pointindirection", inputs={"DIRECTION": num(0)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    # --- (B) controls forever — 화살표 = 누른 방향으로 바로 이동(초등학생 직관) ---
    # 각 키: point in <방향> → move <속도>. 탱크가 향하는 쪽 = 진행 방향 = 포신 방향
    # 이므로 발사도 자연히 그 방향으로 나간다.
    def key_move(keyname, direction, steps):
        pt = gen(); bs[pt] = mk("motion_pointindirection",
            inputs={"DIRECTION": num(direction)})
        mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(steps)})
        chain([(pt, bs[pt]), (mv, bs[mv])])
        m = gen(); bs[m] = mk("sensing_keyoptions",
            fields={"KEY_OPTION": [keyname, None]}, shadow=True)
        p = gen(); bs[p] = mk("sensing_keypressed",
            inputs={"KEY_OPTION": [1, m]})
        bs[m]["parent"] = p
        iff = gen(); bs[iff] = mk("control_if",
            inputs={"CONDITION": [2, p], "SUBSTACK": [2, pt]})
        bs[p]["parent"] = iff; bs[pt]["parent"] = iff
        return iff

    SPEED = 3
    if_up = key_move("up arrow",     0,   SPEED)   # 위
    if_dn = key_move("down arrow",   180, SPEED)   # 아래
    if_l  = key_move("left arrow",  -90,  SPEED)   # 왼쪽
    if_r  = key_move("right arrow",  90,  SPEED)   # 오른쪽

    # if touching 엄폐물 → move -2.5 (bounce back)
    tm_cov = gen(); bs[tm_cov] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["엄폐물", None]}, shadow=True)
    tc_cov = gen(); bs[tc_cov] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_cov]})
    bs[tm_cov]["parent"] = tc_cov
    mv_back = gen(); bs[mv_back] = mk("motion_movesteps", inputs={"STEPS": num(-2.5)})
    if_cov = gen(); bs[if_cov] = mk("control_if",
        inputs={"CONDITION": [2, tc_cov], "SUBSTACK": [2, mv_back]})
    bs[tc_cov]["parent"] = if_cov
    bs[mv_back]["parent"] = if_cov

    # clamp x/y
    def clamp(getter_op, cmp, limit, setter, axis_key):
        gp = gen(); bs[gp] = mk(getter_op)
        c = cmp_op(cmp, gp, limit)
        st = gen(); bs[st] = mk(setter, inputs={axis_key: num(limit)})
        iff = gen(); bs[iff] = mk("control_if",
            inputs={"CONDITION": [2, c], "SUBSTACK": [2, st]})
        bs[c]["parent"] = iff; bs[st]["parent"] = iff
        return iff

    if_xhi = clamp("motion_xposition", "operator_gt",  220, "motion_setx", "X")
    if_xlo = clamp("motion_xposition", "operator_lt", -220, "motion_setx", "X")
    if_yhi = clamp("motion_yposition", "operator_gt",  160, "motion_sety", "Y")
    if_ylo = clamp("motion_yposition", "operator_lt", -160, "motion_sety", "Y")

    w_ctrl = gen(); bs[w_ctrl] = mk("control_wait", inputs={"DURATION": num(0.02)})

    chain([(if_l, bs[if_l]), (if_r, bs[if_r]),
           (if_up, bs[if_up]), (if_dn, bs[if_dn]),
           (if_cov, bs[if_cov]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (w_ctrl, bs[w_ctrl])])
    fe_ctrl = gen(); bs[fe_ctrl] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_l]})
    bs[if_l]["parent"] = fe_ctrl

    chain([(h, bs[h]), (show, bs[show]), (sz, bs[sz]), (g0, bs[g0]),
           (rs, bs[rs]), (pd, bs[pd]), (front, bs[front]),
           (fe_ctrl, bs[fe_ctrl])])

    # --- (C) fire input forever (space, cooldown, 게임상태=1) ---
    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    sp_menu = gen(); bs[sp_menu] = mk("sensing_keyoptions",
        fields={"KEY_OPTION": ["space", None]}, shadow=True)
    sp_press = gen(); bs[sp_press] = mk("sensing_keypressed",
        inputs={"KEY_OPTION": [1, sp_menu]})
    bs[sp_menu]["parent"] = sp_press

    cd_v = vrep("쿨다운", V_CD)
    cond_cd0 = cmp_op("operator_equals", cd_v, 0)
    state_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", state_v, 1)
    cond_a = bool_op("operator_and", sp_press, cond_cd0)
    cond_can_fire = bool_op("operator_and", cond_a, cond_play)

    xp_s = gen(); bs[xp_s] = mk("motion_xposition")
    set_bx = gen(); bs[set_bx] = mk("data_setvariableto",
        inputs={"VALUE": slot(xp_s)}, fields={"VARIABLE": ["포탄X", V_BX]})
    bs[xp_s]["parent"] = set_bx
    yp_s = gen(); bs[yp_s] = mk("motion_yposition")
    set_by = gen(); bs[set_by] = mk("data_setvariableto",
        inputs={"VALUE": slot(yp_s)}, fields={"VARIABLE": ["포탄Y", V_BY]})
    bs[yp_s]["parent"] = set_by
    dir_s = gen(); bs[dir_s] = mk("motion_direction")
    set_bdir = gen(); bs[set_bdir] = mk("data_setvariableto",
        inputs={"VALUE": slot(dir_s)}, fields={"VARIABLE": ["포탄방향", V_BDIR]})
    bs[dir_s]["parent"] = set_bdir

    pitch_fire = gen(); bs[pitch_fire] = mk("sound_seteffectto",
        inputs={"VALUE": num(100)}, fields={"EFFECT": ["PITCH", None]})
    snm_fire = gen(); bs[snm_fire] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_fire = gen(); bs[snd_fire] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_fire]})
    bs[snm_fire]["parent"] = snd_fire

    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["포탄", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone

    set_cd = gen(); bs[set_cd] = mk("data_setvariableto",
        inputs={"VALUE": num(12)}, fields={"VARIABLE": ["쿨다운", V_CD]})

    chain([(set_bx, bs[set_bx]), (set_by, bs[set_by]),
           (set_bdir, bs[set_bdir]),
           (pitch_fire, bs[pitch_fire]), (snd_fire, bs[snd_fire]),
           (cclone, bs[cclone]), (set_cd, bs[set_cd])])

    if_fire = gen(); bs[if_fire] = mk("control_if",
        inputs={"CONDITION": [2, cond_can_fire], "SUBSTACK": [2, set_bx]})
    bs[cond_can_fire]["parent"] = if_fire
    bs[set_bx]["parent"] = if_fire

    w_fire = gen(); bs[w_fire] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_fire, bs[if_fire]), (w_fire, bs[w_fire])])
    fe_fire = gen(); bs[fe_fire] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_fire]})
    bs[if_fire]["parent"] = fe_fire
    chain([(h2, bs[h2]), (fe_fire, bs[fe_fire])])

    # --- (D) damage watcher: touching 적포탄 AND 무적=0 AND 게임상태=1 → 내체력 -1 ---
    h3 = gen(); bs[h3] = mk("event_whenflagclicked", top=True, x=800, y=20)

    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["적포탄", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b]})
    bs[tm_b]["parent"] = tc_b
    # 적탱크에 부딪혀도(돌격) 피해 — 적은 닿으면 스스로 터진다(적탱크 스크립트가 처리)
    tm_et = gen(); bs[tm_et] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["적탱크", None]}, shadow=True)
    tc_et = gen(); bs[tc_et] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_et]})
    bs[tm_et]["parent"] = tc_et
    cond_hit_src = bool_op("operator_or", tc_b, tc_et)

    inv_v = vrep("무적", V_INV)
    cond_no_inv = cmp_op("operator_equals", inv_v, 0)
    state_v2 = vrep("게임상태", V_STATE)
    cond_play2 = cmp_op("operator_equals", state_v2, 1)
    cond_dmg_a = bool_op("operator_and", cond_hit_src, cond_no_inv)
    cond_dmg = bool_op("operator_and", cond_dmg_a, cond_play2)

    dec_hp = gen(); bs[dec_hp] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["내체력", V_HP]})
    set_inv2 = gen(); bs[set_inv2] = mk("data_setvariableto",
        inputs={"VALUE": num(25)}, fields={"VARIABLE": ["무적", V_INV]})
    pitch_dmg = gen(); bs[pitch_dmg] = mk("sound_seteffectto",
        inputs={"VALUE": num(-300)}, fields={"EFFECT": ["PITCH", None]})
    snm_d = gen(); bs[snm_d] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_d = gen(); bs[snd_d] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_d]})
    bs[snm_d]["parent"] = snd_d

    chain([(dec_hp, bs[dec_hp]), (set_inv2, bs[set_inv2]),
           (pitch_dmg, bs[pitch_dmg]), (snd_d, bs[snd_d])])

    if_dmg = gen(); bs[if_dmg] = mk("control_if",
        inputs={"CONDITION": [2, cond_dmg], "SUBSTACK": [2, dec_hp]})
    bs[cond_dmg]["parent"] = if_dmg
    bs[dec_hp]["parent"] = if_dmg

    w_dmg = gen(); bs[w_dmg] = mk("control_wait", inputs={"DURATION": num(0.05)})
    chain([(if_dmg, bs[if_dmg]), (w_dmg, bs[w_dmg])])
    fe_dmg = gen(); bs[fe_dmg] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_dmg]})
    bs[if_dmg]["parent"] = fe_dmg
    chain([(h3, bs[h3]), (fe_dmg, bs[fe_dmg])])

    return bs

# ============================================================
#  SHELL (player bullet)
# ============================================================
def build_shell_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)

    bx_v = vrep("포탄X", V_BX); by_v = vrep("포탄Y", V_BY)
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g

    bdir_v = vrep("포탄방향", V_BDIR)
    point_b = gen(); bs[point_b] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(bdir_v)})
    bs[bdir_v]["parent"] = point_b

    show = gen(); bs[show] = mk("looks_show")

    # repeat until OOB OR touching 적탱크/엄폐물
    # (플레이어탱크 excluded: 발사 시 자기 탱크 위에서 시작하므로 자폭 방지.)
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(10)})
    w_iter = gen(); bs[w_iter] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(mv, bs[mv]), (w_iter, bs[w_iter])])

    xp = gen(); bs[xp] = mk("motion_xposition")
    cx_hi = cmp_op("operator_gt", xp, 240)
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cx_lo = cmp_op("operator_lt", xp_b, -240)
    cx_out = bool_op("operator_or", cx_hi, cx_lo)

    yp = gen(); bs[yp] = mk("motion_yposition")
    cy_hi = cmp_op("operator_gt", yp, 180)
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cy_lo = cmp_op("operator_lt", yp_b, -180)
    cy_out = bool_op("operator_or", cy_hi, cy_lo)

    c_oob = bool_op("operator_or", cx_out, cy_out)

    tm_e = gen(); bs[tm_e] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["적탱크", None]}, shadow=True)
    tc_e = gen(); bs[tc_e] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_e]})
    bs[tm_e]["parent"] = tc_e

    tm_c = gen(); bs[tm_c] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["엄폐물", None]}, shadow=True)
    tc_c = gen(); bs[tc_c] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_c]})
    bs[tm_c]["parent"] = tc_c

    c_ec = bool_op("operator_or", tc_e, tc_c)
    c_stop = bool_op("operator_or", c_oob, c_ec)

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_stop], "SUBSTACK": [2, mv]})
    bs[c_stop]["parent"] = rep_until
    bs[mv]["parent"] = rep_until

    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    chain([(ch, bs[ch]), (g, bs[g]), (point_b, bs[point_b]),
           (show, bs[show]), (rep_until, bs[rep_until]),
           (hi2, bs[hi2]), (delc, bs[delc])])

    return bs

# ============================================================
#  ENEMY SHELL (별도 스프라이트) — 적사격 방송으로 생성, 자기 탱크 위에서 시작해도
#  '적탱크' 를 정지조건에 넣지 않으므로 자폭하지 않는다. 플레이어/엄폐물/가장자리에서 소멸.
#  내체력 차감은 플레이어의 'touching 적포탄' 와처가 처리.
# ============================================================
def build_enemy_shell_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(80)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["all around", None]})
    orig0 = gen(); bs[orig0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["복제됨", V_ESISC]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # on 적사격 → (원본만) create clone
    h_ef = gen(); bs[h_ef] = mk("event_whenbroadcastreceived", top=True, x=400, y=20,
        fields={"BROADCAST_OPTION": ["적사격", BR_EFIRE]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    isc0 = cmp_op("operator_equals", vrep("복제됨", V_ESISC), 0)
    if_spawn = gen(); bs[if_spawn] = mk("control_if",
        inputs={"CONDITION": [2, isc0], "SUBSTACK": [2, cclone]})
    bs[isc0]["parent"] = if_spawn; bs[cclone]["parent"] = if_spawn
    chain([(h_ef, bs[h_ef]), (if_spawn, bs[if_spawn])])

    # clone start: goto 포탄X/Y, point 포탄방향, fly until edge/엄폐물/플레이어
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)
    set_isc1 = gen(); bs[set_isc1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["복제됨", V_ESISC]})
    bx_v = vrep("포탄X", V_BX); by_v = vrep("포탄Y", V_BY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g
    bdir_v = vrep("포탄방향", V_BDIR)
    point_b = gen(); bs[point_b] = mk("motion_pointindirection", inputs={"DIRECTION": slot(bdir_v)})
    bs[bdir_v]["parent"] = point_b
    show = gen(); bs[show] = mk("looks_show")

    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(7)})
    w_iter = gen(); bs[w_iter] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(mv, bs[mv]), (w_iter, bs[w_iter])])

    xp = gen(); bs[xp] = mk("motion_xposition")
    cx_hi = cmp_op("operator_gt", xp, 240)
    xp_b = gen(); bs[xp_b] = mk("motion_xposition")
    cx_lo = cmp_op("operator_lt", xp_b, -240)
    cx_out = bool_op("operator_or", cx_hi, cx_lo)
    yp = gen(); bs[yp] = mk("motion_yposition")
    cy_hi = cmp_op("operator_gt", yp, 180)
    yp_b = gen(); bs[yp_b] = mk("motion_yposition")
    cy_lo = cmp_op("operator_lt", yp_b, -180)
    cy_out = bool_op("operator_or", cy_hi, cy_lo)
    c_oob = bool_op("operator_or", cx_out, cy_out)

    tm_p = gen(); bs[tm_p] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["플레이어탱크", None]}, shadow=True)
    tc_p = gen(); bs[tc_p] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, tm_p]})
    bs[tm_p]["parent"] = tc_p
    tm_c = gen(); bs[tm_c] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["엄폐물", None]}, shadow=True)
    tc_c = gen(); bs[tc_c] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, tm_c]})
    bs[tm_c]["parent"] = tc_c
    c_pc = bool_op("operator_or", tc_p, tc_c)
    c_stop = bool_op("operator_or", c_oob, c_pc)

    rep_until = gen(); bs[rep_until] = mk("control_repeat_until",
        inputs={"CONDITION": [2, c_stop], "SUBSTACK": [2, mv]})
    bs[c_stop]["parent"] = rep_until
    bs[mv]["parent"] = rep_until

    hi2 = gen(); bs[hi2] = mk("looks_hide")
    delc = gen(); bs[delc] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (point_b, bs[point_b]),
           (show, bs[show]), (rep_until, bs[rep_until]),
           (hi2, bs[hi2]), (delc, bs[delc])])
    return bs

# ============================================================
#  ENEMY TANK (AI — 단 1대)
# ============================================================
def build_enemy_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    MAX_ENEMIES = 5

    # --- (A) flag init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle",
        fields={"STYLE": ["all around", None]})
    orig0 = gen(); bs[orig0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["복제됨", V_EISC]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (rs, bs[rs]), (orig0, bs[orig0])])

    # --- (B) on 게임시작 → 원본은 스포너: 게임 동안 랜덤 위치·시간차로 적을 계속 생성 ---
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    # spawn 조건: (적수 < MAX) and (게임상태 = 1)
    ecnt_v = vrep("적수", V_ECNT)
    cond_room = cmp_op("operator_lt", ecnt_v, MAX_ENEMIES)
    st_v = vrep("게임상태", V_STATE)
    cond_play = cmp_op("operator_equals", st_v, 1)
    cond_spawn = bool_op("operator_and", cond_room, cond_play)

    rx = gen(); bs[rx] = mk("operator_random", inputs={"FROM": num(-200), "TO": num(200)})
    set_spx = gen(); bs[set_spx] = mk("data_setvariableto",
        inputs={"VALUE": slot(rx)}, fields={"VARIABLE": ["적생성X", V_SPX]})
    bs[rx]["parent"] = set_spx
    ry = gen(); bs[ry] = mk("operator_random", inputs={"FROM": num(110), "TO": num(170)})
    set_spy = gen(); bs[set_spy] = mk("data_setvariableto",
        inputs={"VALUE": slot(ry)}, fields={"VARIABLE": ["적생성Y", V_SPY]})
    bs[ry]["parent"] = set_spy
    inc_cnt = gen(); bs[inc_cnt] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["적수", V_ECNT]})
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION": [1, cmenu]})
    bs[cmenu]["parent"] = cclone
    chain([(set_spx, bs[set_spx]), (set_spy, bs[set_spy]),
           (inc_cnt, bs[inc_cnt]), (cclone, bs[cclone])])
    if_spawn = gen(); bs[if_spawn] = mk("control_if",
        inputs={"CONDITION": [2, cond_spawn], "SUBSTACK": [2, set_spx]})
    bs[cond_spawn]["parent"] = if_spawn; bs[set_spx]["parent"] = if_spawn

    # wait (random 6..16)/10 초 — 0.6~1.6s 간격
    rw = gen(); bs[rw] = mk("operator_random", inputs={"FROM": num(6), "TO": num(16)})
    wdur = op("operator_divide", rw, 10)
    w_spawn = gen(); bs[w_spawn] = mk("control_wait", inputs={"DURATION": slot(wdur)})
    bs[wdur]["parent"] = w_spawn

    chain([(if_spawn, bs[if_spawn]), (w_spawn, bs[w_spawn])])
    fe_spawn = gen(); bs[fe_spawn] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_spawn]})
    bs[if_spawn]["parent"] = fe_spawn
    # 엄폐물 배치(포탄X/Y 채널 공유)가 끝난 뒤 적 생성 시작 — 채널 경쟁 방지
    w_init = gen(); bs[w_init] = mk("control_wait", inputs={"DURATION": num(0.4)})
    chain([(h2, bs[h2]), (w_init, bs[w_init]), (fe_spawn, bs[fe_spawn])])

    # --- (C) clone body: 한 방에 죽는 적 1대 ---
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)
    set_isc1 = gen(); bs[set_isc1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["복제됨", V_EISC]})
    spx_v = vrep("적생성X", V_SPX); spy_v = vrep("적생성Y", V_SPY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(spx_v), "Y": slot(spy_v)})
    bs[spx_v]["parent"] = g; bs[spy_v]["parent"] = g
    pt_menu0 = gen(); bs[pt_menu0] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["플레이어탱크", None]}, shadow=True)
    pd0 = gen(); bs[pd0] = mk("motion_pointtowards", inputs={"TOWARDS": [1, pt_menu0]})
    bs[pt_menu0]["parent"] = pd0
    show = gen(); bs[show] = mk("looks_show")

    # (1) 게임오버 정리: if 게임상태 = 0 → hide + delete this clone
    st2 = vrep("게임상태", V_STATE)
    cond_over = cmp_op("operator_equals", st2, 0)
    hi_o = gen(); bs[hi_o] = mk("looks_hide")
    del_o = gen(); bs[del_o] = mk("control_delete_this_clone")
    chain([(hi_o, bs[hi_o]), (del_o, bs[del_o])])
    if_over = gen(); bs[if_over] = mk("control_if",
        inputs={"CONDITION": [2, cond_over], "SUBSTACK": [2, hi_o]})
    bs[cond_over]["parent"] = if_over; bs[hi_o]["parent"] = if_over

    # (2) 포탄에 맞으면 한 방에 폭발: if touching 포탄 → 점수+1, 적수-1, sound, delete
    tm_b = gen(); bs[tm_b] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["포탄", None]}, shadow=True)
    tc_b = gen(); bs[tc_b] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_b]})
    bs[tm_b]["parent"] = tc_b
    inc_score = gen(); bs[inc_score] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    dec_cnt = gen(); bs[dec_cnt] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["적수", V_ECNT]})
    # 폭발 코스튬으로 교체 + 효과음
    exm = gen(); bs[exm] = mk("looks_costume",
        fields={"COSTUME": ["폭발", None]}, shadow=True)
    sw_ex = gen(); bs[sw_ex] = mk("looks_switchcostumeto",
        inputs={"COSTUME": [1, exm]})
    bs[exm]["parent"] = sw_ex
    pitch_hit = gen(); bs[pitch_hit] = mk("sound_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["PITCH", None]})
    snm_h = gen(); bs[snm_h] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_h = gen(); bs[snd_h] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_h]})
    bs[snm_h]["parent"] = snd_h
    # 터지는 애니메이션: 크게 부풀며 서서히 투명해진 뒤 삭제
    set_sz = gen(); bs[set_sz] = mk("looks_setsizeto", inputs={"SIZE": num(85)})
    clr_gh = gen(); bs[clr_gh] = mk("looks_seteffectto",
        inputs={"VALUE": num(0)}, fields={"EFFECT": ["GHOST", None]})
    ch_sz = gen(); bs[ch_sz] = mk("looks_changesizeby", inputs={"CHANGE": num(16)})
    ch_gh = gen(); bs[ch_gh] = mk("looks_changeeffectby",
        inputs={"CHANGE": num(20)}, fields={"EFFECT": ["GHOST", None]})
    w_an = gen(); bs[w_an] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(ch_sz, bs[ch_sz]), (ch_gh, bs[ch_gh]), (w_an, bs[w_an])])
    rep_an = gen(); bs[rep_an] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK": [2, ch_sz]})
    bs[ch_sz]["parent"] = rep_an
    del_k = gen(); bs[del_k] = mk("control_delete_this_clone")
    chain([(inc_score, bs[inc_score]), (dec_cnt, bs[dec_cnt]),
           (sw_ex, bs[sw_ex]),
           (pitch_hit, bs[pitch_hit]), (snd_h, bs[snd_h]),
           (set_sz, bs[set_sz]), (clr_gh, bs[clr_gh]),
           (rep_an, bs[rep_an]), (del_k, bs[del_k])])
    if_kill = gen(); bs[if_kill] = mk("control_if",
        inputs={"CONDITION": [2, tc_b], "SUBSTACK": [2, inc_score]})
    bs[tc_b]["parent"] = if_kill; bs[inc_score]["parent"] = if_kill

    # (3) 돌격 충돌: if touching 플레이어탱크 → 적수-1, delete (HP 차감은 플레이어가 처리)
    tm_p = gen(); bs[tm_p] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["플레이어탱크", None]}, shadow=True)
    tc_p = gen(); bs[tc_p] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_p]})
    bs[tm_p]["parent"] = tc_p
    dec_cnt2 = gen(); bs[dec_cnt2] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["적수", V_ECNT]})
    hi_r = gen(); bs[hi_r] = mk("looks_hide")
    del_r = gen(); bs[del_r] = mk("control_delete_this_clone")
    chain([(dec_cnt2, bs[dec_cnt2]), (hi_r, bs[hi_r]), (del_r, bs[del_r])])
    if_ram = gen(); bs[if_ram] = mk("control_if",
        inputs={"CONDITION": [2, tc_p], "SUBSTACK": [2, dec_cnt2]})
    bs[tc_p]["parent"] = if_ram; bs[dec_cnt2]["parent"] = if_ram

    # (4) 부정확한 추적: if (random 1..3) < 3 → point towards 플레이어탱크
    r_aim = gen(); bs[r_aim] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(3)})
    c_aim = cmp_op("operator_lt", r_aim, 3)
    bs[r_aim]["parent"] = c_aim
    pt_menu = gen(); bs[pt_menu] = mk("motion_pointtowards_menu",
        fields={"TOWARDS": ["플레이어탱크", None]}, shadow=True)
    point_p = gen(); bs[point_p] = mk("motion_pointtowards",
        inputs={"TOWARDS": [1, pt_menu]})
    bs[pt_menu]["parent"] = point_p
    if_aim = gen(); bs[if_aim] = mk("control_if",
        inputs={"CONDITION": [2, c_aim], "SUBSTACK": [2, point_p]})
    bs[c_aim]["parent"] = if_aim; bs[point_p]["parent"] = if_aim

    # (5) move 1.2 (느린 고정 속도)
    mv = gen(); bs[mv] = mk("motion_movesteps", inputs={"STEPS": num(1.2)})

    # (6) if touching 엄폐물 → move -2, turn cw 30
    tm_cv = gen(); bs[tm_cv] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["엄폐물", None]}, shadow=True)
    tc_cv = gen(); bs[tc_cv] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU": [1, tm_cv]})
    bs[tm_cv]["parent"] = tc_cv
    mv_back = gen(); bs[mv_back] = mk("motion_movesteps", inputs={"STEPS": num(-2)})
    turn_cw30 = gen(); bs[turn_cw30] = mk("motion_turnright", inputs={"DEGREES": num(30)})
    chain([(mv_back, bs[mv_back]), (turn_cw30, bs[turn_cw30])])
    if_bump = gen(); bs[if_bump] = mk("control_if",
        inputs={"CONDITION": [2, tc_cv], "SUBSTACK": [2, mv_back]})
    bs[tc_cv]["parent"] = if_bump; bs[mv_back]["parent"] = if_bump

    # clamp to stage
    def clamp(getter_op, cmp, limit, setter, axis_key):
        gp = gen(); bs[gp] = mk(getter_op)
        c = cmp_op(cmp, gp, limit)
        st = gen(); bs[st] = mk(setter, inputs={axis_key: num(limit)})
        iff = gen(); bs[iff] = mk("control_if",
            inputs={"CONDITION": [2, c], "SUBSTACK": [2, st]})
        bs[c]["parent"] = iff; bs[st]["parent"] = iff
        return iff

    if_xhi = clamp("motion_xposition", "operator_gt",  230, "motion_setx", "X")
    if_xlo = clamp("motion_xposition", "operator_lt", -230, "motion_setx", "X")
    if_yhi = clamp("motion_yposition", "operator_gt",  170, "motion_sety", "Y")
    if_ylo = clamp("motion_yposition", "operator_lt", -170, "motion_sety", "Y")

    # (7) 간헐 발사: if (random 1..100) = 1 → set 포탄X/Y/dir, sound, broadcast 적사격
    r_fire = gen(); bs[r_fire] = mk("operator_random",
        inputs={"FROM": num(1), "TO": num(100)})
    c_efire = cmp_op("operator_equals", r_fire, 1)
    bs[r_fire]["parent"] = c_efire

    xpe = gen(); bs[xpe] = mk("motion_xposition")
    set_bxe = gen(); bs[set_bxe] = mk("data_setvariableto",
        inputs={"VALUE": slot(xpe)}, fields={"VARIABLE": ["포탄X", V_BX]})
    bs[xpe]["parent"] = set_bxe
    ype = gen(); bs[ype] = mk("motion_yposition")
    set_bye = gen(); bs[set_bye] = mk("data_setvariableto",
        inputs={"VALUE": slot(ype)}, fields={"VARIABLE": ["포탄Y", V_BY]})
    bs[ype]["parent"] = set_bye
    dire = gen(); bs[dire] = mk("motion_direction")
    set_bdire = gen(); bs[set_bdire] = mk("data_setvariableto",
        inputs={"VALUE": slot(dire)}, fields={"VARIABLE": ["포탄방향", V_BDIR]})
    bs[dire]["parent"] = set_bdire

    pitch_ef = gen(); bs[pitch_ef] = mk("sound_seteffectto",
        inputs={"VALUE": num(-100)}, fields={"EFFECT": ["PITCH", None]})
    snm_ef = gen(); bs[snm_ef] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd_ef = gen(); bs[snd_ef] = mk("sound_play",
        inputs={"SOUND_MENU": [1, snm_ef]})
    bs[snm_ef]["parent"] = snd_ef

    bm_ef = gen(); bs[bm_ef] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["적사격", BR_EFIRE]}, shadow=True)
    bc_ef = gen(); bs[bc_ef] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, bm_ef]})
    bs[bm_ef]["parent"] = bc_ef

    chain([(set_bxe, bs[set_bxe]), (set_bye, bs[set_bye]),
           (set_bdire, bs[set_bdire]),
           (pitch_ef, bs[pitch_ef]), (snd_ef, bs[snd_ef]),
           (bc_ef, bs[bc_ef])])
    if_efire = gen(); bs[if_efire] = mk("control_if",
        inputs={"CONDITION": [2, c_efire], "SUBSTACK": [2, set_bxe]})
    bs[c_efire]["parent"] = if_efire; bs[set_bxe]["parent"] = if_efire

    w_iter = gen(); bs[w_iter] = mk("control_wait", inputs={"DURATION": num(0.04)})

    chain([(if_over, bs[if_over]), (if_kill, bs[if_kill]), (if_ram, bs[if_ram]),
           (if_aim, bs[if_aim]), (mv, bs[mv]),
           (if_bump, bs[if_bump]),
           (if_xhi, bs[if_xhi]), (if_xlo, bs[if_xlo]),
           (if_yhi, bs[if_yhi]), (if_ylo, bs[if_ylo]),
           (if_efire, bs[if_efire]), (w_iter, bs[w_iter])])

    fe_body = gen(); bs[fe_body] = mk("control_forever",
        inputs={"SUBSTACK": [2, if_over]})
    bs[if_over]["parent"] = fe_body

    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (pd0, bs[pd0]),
           (show, bs[show]), (fe_body, bs[fe_body])])

    return bs

# ============================================================
#  COVER (가운데 가로 3개 고정 배치)
# ============================================================
def build_cover_blocks():
    bs = {}
    vrep, op, cmp_op, bool_op = make_helpers(bs)

    # 흩뿌린 고정 엄폐물 좌표 (플레이어 시작 0,-120 및 적 스폰 y>=110 회피)
    POSITIONS = [(-150, 70), (0, 90), (150, 70), (-90, 0),
                 (90, 0), (-150, -90), (0, -50), (150, -90)]

    # --- (A) flag init ---
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(70)})
    orig0 = gen(); bs[orig0] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["복제됨", V_CVISC]})
    chain([(h, bs[h]), (hi, bs[hi]), (sz, bs[sz]), (orig0, bs[orig0])])

    # --- (B) on 게임시작 → (원본만) POSITIONS 마다 클론 1개씩 ---
    # 포탄X/포탄Y 를 좌표 전달 채널로 재활용(게임 시작 직후라 발사와 충돌 없음).
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})

    isc0 = cmp_op("operator_equals", vrep("복제됨", V_CVISC), 0)

    body = []
    for i, (xpos, ypos) in enumerate(POSITIONS):
        set_x = gen(); bs[set_x] = mk("data_setvariableto",
            inputs={"VALUE": num(xpos)}, fields={"VARIABLE": ["포탄X", V_BX]})
        set_y = gen(); bs[set_y] = mk("data_setvariableto",
            inputs={"VALUE": num(ypos)}, fields={"VARIABLE": ["포탄Y", V_BY]})
        cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
            fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
        cclone = gen(); bs[cclone] = mk("control_create_clone_of",
            inputs={"CLONE_OPTION": [1, cmenu]})
        bs[cmenu]["parent"] = cclone
        body.append((set_x, bs[set_x]))
        body.append((set_y, bs[set_y]))
        body.append((cclone, bs[cclone]))
        if i < len(POSITIONS) - 1:
            wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.02)})
            body.append((wt, bs[wt]))
    chain(body)

    if_spawn = gen(); bs[if_spawn] = mk("control_if",
        inputs={"CONDITION": [2, isc0], "SUBSTACK": [2, body[0][0]]})
    bs[isc0]["parent"] = if_spawn; bs[body[0][0]]["parent"] = if_spawn
    chain([(h2, bs[h2]), (if_spawn, bs[if_spawn])])

    # --- (C) clone start: goto (포탄X, 포탄Y), show — 부서지지 않는 영구 벽 ---
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)
    set_isc1 = gen(); bs[set_isc1] = mk("data_setvariableto",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["복제됨", V_CVISC]})
    bx_v = vrep("포탄X", V_BX); by_v = vrep("포탄Y", V_BY)
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": slot(bx_v), "Y": slot(by_v)})
    bs[bx_v]["parent"] = g; bs[by_v]["parent"] = g
    show = gen(); bs[show] = mk("looks_show")
    chain([(ch, bs[ch]), (set_isc1, bs[set_isc1]), (g, bs[g]), (show, bs[show])])

    return bs

# ============================================================
#  GAME OVER (승/패 2코스튬)
# ============================================================
def build_gameover_blocks():
    bs = {}
    vrep, op, cmp_op, _ = make_helpers(bs)

    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    front = gen(); bs[front] = mk("looks_gotofrontback",
        fields={"FRONT_BACK": ["front", None]})

    state_v1 = vrep("게임상태", V_STATE)
    cond_one = cmp_op("operator_equals", state_v1, 1)
    wait_start = gen(); bs[wait_start] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_one]})
    bs[cond_one]["parent"] = wait_start

    state_v2 = vrep("게임상태", V_STATE)
    cond_zero = cmp_op("operator_equals", state_v2, 0)
    wait_over = gen(); bs[wait_over] = mk("control_wait_until",
        inputs={"CONDITION": [2, cond_zero]})
    bs[cond_zero]["parent"] = wait_over

    # if (결과 = 1) → switch 승리 else switch 패배
    res_v = vrep("결과", V_RESULT)
    cond_win = cmp_op("operator_equals", res_v, 1)

    def switch_costume(name):
        m = gen(); bs[m] = mk("looks_costume",
            fields={"COSTUME": [name, None]}, shadow=True)
        sw = gen(); bs[sw] = mk("looks_switchcostumeto",
            inputs={"COSTUME": [1, m]})
        bs[m]["parent"] = sw
        return sw

    sw_win  = switch_costume("승리")
    sw_lose = switch_costume("패배")

    if_res = gen(); bs[if_res] = mk("control_if_else",
        inputs={"CONDITION": [2, cond_win],
                "SUBSTACK":  [2, sw_win],
                "SUBSTACK2": [2, sw_lose]})
    bs[cond_win]["parent"] = if_res
    bs[sw_win]["parent"] = if_res
    bs[sw_lose]["parent"] = if_res

    show = gen(); bs[show] = mk("looks_show")
    chain([(h, bs[h]), (hi, bs[hi]), (g, bs[g]), (sz, bs[sz]), (front, bs[front]),
           (wait_start, bs[wait_start]), (wait_over, bs[wait_over]),
           (if_res, bs[if_res]), (show, bs[show])])
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

    bg_md5 = save_svg(BG_SVG)
    tp_md5 = save_svg(TANK_PLAYER_SVG)
    te_md5 = save_svg(TANK_ENEMY_SVG)
    sh_md5 = save_svg(SHELL_SVG)
    se_md5 = save_svg(SHELL_ENEMY_SVG)
    cv_md5 = save_svg(COVER_SVG)
    ex_md5 = save_svg(EXPLOSION_SVG)
    rw_md5 = save_svg(RESULT_WIN_SVG)
    rl_md5 = save_svg(RESULT_LOSE_SVG)

    with open(f"{ASSETS}/pop.wav", "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    stage_blocks    = build_stage_blocks()
    player_blocks   = build_player_blocks()
    shell_blocks    = build_shell_blocks()
    eshell_blocks   = build_enemy_shell_blocks()
    enemy_blocks    = build_enemy_blocks()
    cover_blocks    = build_cover_blocks()
    gameover_blocks = build_gameover_blocks()

    pop_sound = lambda: {
        "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
        "format": "", "rate": 11025, "sampleCount": 258,
        "md5ext": f"{pop_md5}.wav"
    }

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_HP:     ["내체력", 3],
            V_STATE:  ["게임상태", 1],
            V_RESULT: ["결과", 2],
            V_BX:     ["포탄X", 0],
            V_BY:     ["포탄Y", 0],
            V_BDIR:   ["포탄방향", 90],
            V_INV:    ["무적", 0],
            V_CD:     ["쿨다운", 0],
            V_SCORE:  ["점수", 0],
            V_ECNT:   ["적수", 0],
            V_SPX:    ["적생성X", 0],
            V_SPY:    ["적생성Y", 0],
        },
        "lists": {},
        "broadcasts": {
            BR_START: "게임시작",
            BR_EFIRE: "적사격",
        },
        "blocks": stage_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "사막", "dataFormat": "svg",
            "assetId": bg_md5, "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240, "rotationCenterY": 180
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    player = {
        "isStage": False, "name": "플레이어탱크",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": player_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "tank", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": tp_md5, "md5ext": f"{tp_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 5, "visible": True,
        "x": 0, "y": -120, "size": 75, "direction": 0,
        "draggable": False, "rotationStyle": "all around"
    }

    shell = {
        "isStage": False, "name": "포탄",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": shell_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "shell", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": sh_md5, "md5ext": f"{sh_md5}.svg",
            "rotationCenterX": 8, "rotationCenterY": 10
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    eshell = {
        "isStage": False, "name": "적포탄",
        "variables": {V_ESISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": eshell_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "eshell", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": se_md5, "md5ext": f"{se_md5}.svg",
            "rotationCenterX": 8, "rotationCenterY": 10
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "all around"
    }

    enemy = {
        "isStage": False, "name": "적탱크",
        "variables": {V_EISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": enemy_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "tank_enemy", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": te_md5, "md5ext": f"{te_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }, {
            "name": "폭발", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": ex_md5, "md5ext": f"{ex_md5}.svg",
            "rotationCenterX": 30, "rotationCenterY": 30
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 4, "visible": False,
        "x": 0, "y": 120, "size": 75, "direction": 180,
        "draggable": False, "rotationStyle": "all around"
    }

    cover = {
        "isStage": False, "name": "엄폐물",
        "variables": {V_CVISC: ["복제됨", 0]}, "lists": {}, "broadcasts": {},
        "blocks": cover_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "cover", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": cv_md5, "md5ext": f"{cv_md5}.svg",
            "rotationCenterX": 25, "rotationCenterY": 25
        }],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": 0, "y": 0, "size": 80, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    gameover = {
        "isStage": False, "name": "게임오버",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": gameover_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "승리", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": rw_md5, "md5ext": f"{rw_md5}.svg",
                "rotationCenterX": 180, "rotationCenterY": 80
            },
            {
                "name": "패배", "bitmapResolution": 1, "dataFormat": "svg",
                "assetId": rl_md5, "md5ext": f"{rl_md5}.svg",
                "rotationCenterX": 180, "rotationCenterY": 80
            }
        ],
        "sounds": [pop_sound()],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_HP, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "내체력"}, "spriteName": None,
         "value": 3, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 5, "isDiscrete": True},
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
    ]

    project = {
        "targets": [stage, player, shell, eshell, enemy, cover, gameover],
        "monitors": monitors,
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "tank-battle-builder"}
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
    print(f"  stage:    {len(stage_blocks)} blocks")
    print(f"  player:   {len(player_blocks)} blocks")
    print(f"  shell:    {len(shell_blocks)} blocks")
    print(f"  eshell:   {len(eshell_blocks)} blocks")
    print(f"  enemy:    {len(enemy_blocks)} blocks")
    print(f"  cover:    {len(cover_blocks)} blocks")
    print(f"  gameover: {len(gameover_blocks)} blocks")
    total = (len(stage_blocks) + len(player_blocks) + len(shell_blocks) + len(eshell_blocks)
             + len(enemy_blocks) + len(cover_blocks) + len(gameover_blocks))
    print(f"  TOTAL:    {total} blocks")

if __name__ == "__main__":
    main()
