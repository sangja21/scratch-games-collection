#!/usr/bin/env python3
"""브릭 브레이커 — Arkanoid/DX-Ball 감성 파워업 벽돌깨기.

패들(마우스) + 공 반사 + 벽돌 격자 + 낙하 파워업.
파워업: 멀티볼(M) 확대(W) 레이저(L) 캐치(C) 관통(P) 감속(S)
벽돌: 일반 / 단단함(2) / 폭발
"""
import json, os, zipfile, hashlib, shutil
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "벽돌깨기.sb3")
GEN = os.path.join(ASSETS, "gen")

COLS, ROWS = 10, 6
BW, BH = 42, 18  # stage half-ish spacing
OX, OY = -210, 120  # top-left brick center-ish
PADDLE_Y = -150
BALL_SPEED = 22
SLOW_SPEED = 12

# stage patterns: 0 empty, 1-6 color, 7 hard, 8 bomb, 9 boss (stage 5 only)
BOSS_HP = 12
BOSS_SIZE = 280  # % — 일반 벽돌(90)보다 훨씬 큰 왕벽돌

STAGES = [
    # 1: 풀 컬러 격자 (classic intro)
    [
        "1111111111",
        "2222222222",
        "3333333333",
        "4444444444",
        "5555555555",
        "6666666666",
    ],
    # 2: 체스판 + 단단함 + 폭탄 줄
    [
        "1717171717",
        "7171717171",
        "1717171717",
        "7171717171",
        "1111111111",
        "0808080808",
    ],
    # 3: 단단함 상단 + 혼합
    [
        "7777777777",
        "1212121212",
        "3434343434",
        "5656565656",
        "1818181818",
        "2222222222",
    ],
    # 4: 성벽 패턴
    [
        "1111811111",
        "1177777711",
        "1711111171",
        "1177777711",
        "1111811111",
        "2222222222",
    ],
    # 5: 보스 판 — 중앙 왕벽돌(9) + 호위 소수
    [
        "7000000007",
        "0000000000",
        "0000900000",
        "7000000007",
        "0800000080",
        "1110000111",
    ],
]


def md5_bytes(b): return hashlib.md5(b).hexdigest()
def num(n): return [1, [4, str(n)]]
def text_lit(s): return [1, [10, str(s)]]
def slot(bid, sk=4, sv="0"): return [3, bid, [sk, str(sv)]]

def mk(opcode, *, parent=None, next_=None, inputs=None, fields=None, top=False, x=0, y=0, shadow=False):
    b = {"opcode": opcode, "next": next_, "parent": parent, "inputs": inputs or {},
         "fields": fields or {}, "shadow": shadow, "topLevel": top}
    if top: b["x"], b["y"] = x, y
    return b

_ic = [0]
def gen():
    _ic[0] += 1
    return f"b{_ic[0]:04d}"

def chain(seq):
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        a[1]["next"] = b[0]; b[1]["parent"] = a[0]

def make_helpers(bs):
    def vrep(name, vid):
        bid = gen(); bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]}); return bid
    def op(opcode, a, b_, k1="NUM1", k2="NUM2"):
        bid = gen(); ins = {}
        for k, v in [(k1, a), (k2, b_)]:
            ins[k] = slot(v) if isinstance(v, str) else num(v)
        bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): bs[v]["parent"] = bid
        return bid
    def cmp_op(opcode, a, b_):
        bid = gen(); ins = {}
        for k, v in [("OPERAND1", a), ("OPERAND2", b_)]:
            ins[k] = slot(v) if isinstance(v, str) else num(v)
        bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): bs[v]["parent"] = bid
        return bid
    def bool_op(opcode, a, b_):
        bid = gen()
        bs[bid] = mk(opcode, inputs={"OPERAND1": [2, a], "OPERAND2": [2, b_]})
        bs[a]["parent"] = bid; bs[b_]["parent"] = bid
        return bid
    def not_op(a):
        bid = gen()
        bs[bid] = mk("operator_not", inputs={"OPERAND": [2, a]})
        bs[a]["parent"] = bid
        return bid
    return vrep, op, cmp_op, bool_op, not_op

def b_set(bs, name, vid, value):
    bid = gen()
    if isinstance(value, str) and value in bs:
        bs[bid] = mk("data_setvariableto", inputs={"VALUE": slot(value)}, fields={"VARIABLE": [name, vid]})
        bs[value]["parent"] = bid
    else:
        bs[bid] = mk("data_setvariableto", inputs={"VALUE": num(value)}, fields={"VARIABLE": [name, vid]})
    return bid

def b_chg(bs, name, vid, value):
    bid = gen()
    if isinstance(value, str) and value in bs:
        bs[bid] = mk("data_changevariableby", inputs={"VALUE": slot(value)}, fields={"VARIABLE": [name, vid]})
        bs[value]["parent"] = bid
    else:
        bs[bid] = mk("data_changevariableby", inputs={"VALUE": num(value)}, fields={"VARIABLE": [name, vid]})
    return bid

def b_if(bs, cond, body):
    bid = gen()
    bs[bid] = mk("control_if", inputs={"CONDITION": [2, cond], "SUBSTACK": [2, body]})
    bs[cond]["parent"] = bid; bs[body]["parent"] = bid
    return bid

def b_ifelse(bs, cond, t, f):
    bid = gen()
    bs[bid] = mk("control_if_else", inputs={"CONDITION": [2, cond], "SUBSTACK": [2, t], "SUBSTACK2": [2, f]})
    bs[cond]["parent"] = bid; bs[t]["parent"] = bid; bs[f]["parent"] = bid
    return bid

def b_forever(bs, head):
    bid = gen(); bs[bid] = mk("control_forever", inputs={"SUBSTACK": [2, head]}); bs[head]["parent"] = bid
    return bid

def b_wait(bs, d):
    bid = gen(); bs[bid] = mk("control_wait", inputs={"DURATION": num(d)}); return bid

def b_broadcast(bs, name, brid):
    m = gen(); bs[m] = mk("event_broadcast_menu", fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcast", inputs={"BROADCAST_INPUT": [1, m]}); bs[m]["parent"] = b
    return b

def b_broadcast_wait(bs, name, brid):
    """broadcast and wait — 수신자를 동기(같은 시점)로 끝까지 실행하고 이어감."""
    m = gen(); bs[m] = mk("event_broadcast_menu", fields={"BROADCAST_OPTION": [name, brid]}, shadow=True)
    b = gen(); bs[b] = mk("event_broadcastandwait", inputs={"BROADCAST_INPUT": [1, m]}); bs[m]["parent"] = b
    return b

def b_key(bs, key):
    m = gen(); bs[m] = mk("sensing_keyoptions", fields={"KEY_OPTION": [key, None]}, shadow=True)
    p = gen(); bs[p] = mk("sensing_keypressed", inputs={"KEY_OPTION": [1, m]}); bs[m]["parent"] = p
    return p

def touching(bs, name):
    m = gen(); bs[m] = mk("sensing_touchingobjectmenu", fields={"TOUCHINGOBJECTMENU": [name, None]}, shadow=True)
    t = gen(); bs[t] = mk("sensing_touchingobject", inputs={"TOUCHINGOBJECTMENU": [1, m]}); bs[m]["parent"] = t
    return t

def costume_name(bs, name):
    cm = gen(); bs[cm] = mk("looks_costume", fields={"COSTUME": [name, None]}, shadow=True)
    sw = gen(); bs[sw] = mk("looks_switchcostumeto", inputs={"COSTUME": [1, cm]}); bs[cm]["parent"] = sw
    return sw

def create_clone(bs):
    cm = gen(); bs[cm] = mk("control_create_clone_of_menu", fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cc = gen(); bs[cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, cm]}); bs[cm]["parent"] = cc
    return cc

def play_sound(bs, name):
    """start sound (does not wait). Sound must be registered on that sprite."""
    sm = gen(); bs[sm] = mk("sound_sounds_menu", fields={"SOUND_MENU": [name, None]}, shadow=True)
    sp = gen(); bs[sp] = mk("sound_play", inputs={"SOUND_MENU": [1, sm]})
    bs[sm]["parent"] = sp
    return sp

def b_repeat(bs, times, head):
    bid = gen()
    tin = slot(times) if isinstance(times, str) and times in bs else num(times)
    bs[bid] = mk("control_repeat", inputs={"TIMES": tin, "SUBSTACK": [2, head]})
    bs[head]["parent"] = bid
    if isinstance(times, str) and times in bs: bs[times]["parent"] = bid
    return bid

def _val_slot(bs, v):
    """숫자면 num, 블록 id면 slot(+parent 는 호출측에서)."""
    return slot(v) if isinstance(v, str) and v in bs else num(v)

def set_effect(bs, effect, val):
    bid = gen(); bs[bid] = mk("looks_seteffectto", inputs={"VALUE": _val_slot(bs, val)},
                              fields={"EFFECT": [effect, None]})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def change_effect(bs, effect, val):
    bid = gen(); bs[bid] = mk("looks_changeeffectby", inputs={"CHANGE": _val_slot(bs, val)},
                              fields={"EFFECT": [effect, None]})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def clear_effects(bs):
    bid = gen(); bs[bid] = mk("looks_cleargraphiceffects"); return bid

def change_size(bs, val):
    bid = gen(); bs[bid] = mk("looks_changesizeby", inputs={"CHANGE": _val_slot(bs, val)})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def move_steps(bs, val):
    bid = gen(); bs[bid] = mk("motion_movesteps", inputs={"STEPS": _val_slot(bs, val)})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def point_dir(bs, val):
    bid = gen(); bs[bid] = mk("motion_pointindirection", inputs={"DIRECTION": _val_slot(bs, val)})
    if isinstance(val, str) and val in bs: bs[val]["parent"] = bid
    return bid

def rnd(bs, lo, hi):
    bid = gen(); bs[bid] = mk("operator_random", inputs={"FROM": num(lo), "TO": num(hi)})
    return bid

def wipe_on_stage_start(bs, vrep, cmp_op, y=380):
    """스테이지시작 시 이 스프라이트의 클론을 전부 삭제 (전체 정리용)."""
    h = gen(); bs[h] = mk("event_whenbroadcastreceived", top=True, x=260, y=y,
        fields={"BROADCAST_OPTION": ["스테이지시작", BR_STAGE]})
    c = cmp_op("operator_equals", vrep("복제됨", V_ISC), 1)
    d = gen(); bs[d] = mk("control_delete_this_clone")
    ifd = b_if(bs, c, d)
    chain([(h, bs[h]), (ifd, bs[ifd])])

# IDs
V_STATE, V_SCORE, V_BEST, V_LIVES = "varState", "varScore", "varBest", "varLives"
V_STAGE, V_BRICKS = "varStage", "varBricks"
V_MODE = "varMode"          # 0 normal 1 wide 2 laser 3 catch
V_PIERCE, V_SLOW = "varPierce", "varSlow"
V_BALLS = "varBalls"        # active ball count
V_LAUNCH = "varLaunch"      # 1 = balls free
V_SPD, V_PCHANCE = "varSpd", "varPChance"
V_MAXBALLS, V_PBASE = "varMaxBalls", "varPBase"
V_TMP, V_I, V_R, V_C = "varTmp", "varI", "varR", "varC"
V_BX, V_BY, V_BHP, V_BTYPE = "varBx", "varBy", "varBhp", "varBtype"
V_PU = "varPu"              # power type letter code as number 1-6
V_BOUNCE = "varBounce"

V_ISC, V_VX, V_VY = "varIsC", "varVx", "varVy"
V_HP, V_KIND = "varHp", "varKind"
V_STUCK = "varStuck"
V_HITCD = "varHitCd"         # 공 로컬: 벽돌 타격 쿨다운(프레임). 0일 때만 반사·타격 방송
V_ISMAIN = "varIsMain"       # 1=주황 메인공, 0=노란 보너스공 (클론 로컬)
V_PREY = "varPrevY"          # 이동 전 Y (패들 스윕 판정)
V_SPAWNMAIN = "varSpawnMain" # 스폰 직전 타입 플래그 (Stage)
V_MAINLIVE = "varMainLive"   # 메인공 생존 여부 0/1 (Stage)
V_READY = "varReady"         # 1=벽돌 생성 끝, 발사 가능
V_BOSSHP = "varBossHp"       # 보스 체력 (스테이지5 모니터)
V_BGMVOL = "varBgmVol"       # 브금볼륨 %

# 난장판(카오스) 시스템 손잡이/내부값
V_CLOCK = "varClock"         # 광란시계 (스케줄러 틱)
V_FRENZY = "varFrenzy"       # 광란레벨 (시간 지날수록 ↑)
V_LASERTIME = "varLaserTime" # 레이저 광란 남은 연사수
V_FLASHCOL = "varFlashCol"   # 번쩍 색(색상효과 값)
V_WAVEGAP = "varWaveGap"     # 멀티볼 웨이브 간격(초)
V_LASGAP = "varLasGap"       # 레이저 광란 간격(초)
V_SPDGAP = "varSpdGap"       # 공속 상승 간격(초)
V_WAVEN = "varWaveN"         # 웨이브당 노란공 수
V_LASSHOTS = "varLasShots"   # 레이저 광란 지속(연사 횟수)
V_SPDMAX = "varSpdMax"       # 공속 상한

# 플레이필드
WALL_L, WALL_R, WALL_T = -220, 220, 165
DEATH_Y = -165               # 이하면 낙하 사망 (단순 판정)

BR_START, BR_STAGE, BR_LOST, BR_CLEAR = "brStart", "brStage", "brLost", "brClear"
BR_SERVE, BR_FIRE = "brServe", "brFire"
BR_MAIN = "brMain"      # 주황 메인공 1개
BR_BONUS = "brBonus"    # 노란 보너스
BR_READY = "brReady"    # 벽돌 전부 깔린 뒤 발사 가능
BR_BRICKHIT = "brBrickHit"  # 공이 벽돌에 닿은 그 프레임에 벽돌이 자기 판정하게 하는 방송
BR_FLASH = "brFlash"    # 화면 번쩍 연출
BR_SPARK = "brSpark"    # 스파크 폭발 연출


def build_stage():
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    seq = [(h, bs[h])]
    def S(n, i, v):
        sid = b_set(bs, n, i, v); seq.append((sid, bs[sid]))
    S("게임상태", V_STATE, 1)
    S("점수", V_SCORE, 0)
    S("목숨", V_LIVES, 3)
    S("스테이지", V_STAGE, 1)
    S("남은벽돌", V_BRICKS, 0)
    S("패들모드", V_MODE, 0)
    S("관통", V_PIERCE, 0)
    S("감속", V_SLOW, 0)
    S("공개수", V_BALLS, 0)
    S("발사됨", V_LAUNCH, 0)
    S("공속도", V_SPD, BALL_SPEED)
    S("아이템확률", V_PCHANCE, 30)
    S("멀티볼최대", V_MAXBALLS, 12)
    S("패들기본", V_PBASE, 100)
    # 난장판 손잡이 + 내부값
    S("광란시계", V_CLOCK, 0)
    S("광란레벨", V_FRENZY, 1)
    S("레이저타임", V_LASERTIME, 0)
    S("번쩍색", V_FLASHCOL, 0)
    S("웨이브간격", V_WAVEGAP, 4)
    S("레이저간격", V_LASGAP, 7)
    S("공속상승간격", V_SPDGAP, 6)
    S("웨이브개수", V_WAVEN, 3)
    S("레이저연사", V_LASSHOTS, 16)
    S("공속상한", V_SPDMAX, 28)
    S("브금볼륨", V_BGMVOL, 55)
    S("임시", V_TMP, 0)
    S("검사i", V_I, 0)
    S("스폰X", V_BX, 0)
    S("스폰Y", V_BY, 0)
    S("스폰체력", V_BHP, 1)
    S("스폰종류", V_BTYPE, 1)
    S("파워종류", V_PU, 1)
    S("바운스", V_BOUNCE, 0)
    S("스폰메인", V_SPAWNMAIN, 1)
    S("메인존재", V_MAINLIVE, 0)
    S("준비됨", V_READY, 0)
    S("보스체력", V_BOSSHP, 0)
    bc = b_broadcast(bs, "게임시작", BR_START)
    seq.append((bc, bs[bc]))
    bc2 = b_broadcast(bs, "스테이지시작", BR_STAGE)
    seq.append((bc2, bs[bc2]))
    chain(seq)

    # 공놓침 = 주황 메인공만 방송. 노란 보너스는 떨어져도 목숨 유지
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=280,
        fields={"BROADCAST_OPTION": ["공놓침", BR_LOST]})
    set_l = b_set(bs, "발사됨", V_LAUNCH, 0)
    set_ml0 = b_set(bs, "메인존재", V_MAINLIVE, 0)
    dec_life = b_chg(bs, "목숨", V_LIVES, -1)
    snd_lose = play_sound(bs, "lose")
    c_dead = cmp_op("operator_lt", vrep("목숨", V_LIVES), 1)
    go = b_set(bs, "게임상태", V_STATE, 0)
    reset_mode = b_set(bs, "패들모드", V_MODE, 0)
    reset_p = b_set(bs, "관통", V_PIERCE, 0)
    # 메인공 1개만 재서브 (보너스 방송 아님)
    serve = b_broadcast(bs, "메인공서브", BR_MAIN)
    chain([(reset_mode, bs[reset_mode]), (reset_p, bs[reset_p]), (serve, bs[serve])])
    if_dead = b_ifelse(bs, c_dead, go, reset_mode)
    chain([(h2, bs[h2]), (set_l, bs[set_l]), (set_ml0, bs[set_ml0]),
           (dec_life, bs[dec_life]), (snd_lose, bs[snd_lose]), (if_dead, bs[if_dead])])

    # stage clear — 전환 중 상태(2)로 잠그고, 마지막 스테이지면 풀 리셋 후
    # broadcast and wait 로 클론 정리·벽돌 재스폰이 끝난 뒤 플레이 재개
    h3 = gen(); bs[h3] = mk("event_whenbroadcastreceived", top=True, x=20, y=480,
        fields={"BROADCAST_OPTION": ["스테이지클리어", BR_CLEAR]})
    c_can_clear = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    lock_st = b_set(bs, "게임상태", V_STATE, 2)  # 전환 중 (중복 클리어·입력 잠금)
    lock_rdy = b_set(bs, "준비됨", V_READY, 0)
    lock_ln = b_set(bs, "발사됨", V_LAUNCH, 0)
    snd_clear = play_sound(bs, "clear")
    clr_fc = b_set(bs, "번쩍색", V_FLASHCOL, 130)
    clr_fl = b_broadcast(bs, "번쩍", BR_FLASH)
    clr_sp = b_broadcast(bs, "스파크", BR_SPARK)
    add_sc = b_chg(bs, "점수", V_SCORE, 500)
    inc_s = b_chg(bs, "스테이지", V_STAGE, 1)
    c_max = cmp_op("operator_gt", vrep("스테이지", V_STAGE), len(STAGES))
    # ── 전 스테이지 클리어 → 풀 리셋 후 1스테이지부터 다시 ──
    wrap_s = b_set(bs, "스테이지", V_STAGE, 1)
    wrap_life = b_set(bs, "목숨", V_LIVES, 3)
    wrap_score = b_set(bs, "점수", V_SCORE, 0)
    wrap_fr = b_set(bs, "광란레벨", V_FRENZY, 1)
    wrap_ck = b_set(bs, "광란시계", V_CLOCK, 0)
    wrap_lt = b_set(bs, "레이저타임", V_LASERTIME, 0)
    wrap_sl = b_set(bs, "감속", V_SLOW, 0)
    wrap_bl = b_set(bs, "공개수", V_BALLS, 0)
    wrap_ml = b_set(bs, "메인존재", V_MAINLIVE, 0)
    wrap_spd = b_set(bs, "공속도", V_SPD, BALL_SPEED)
    chain([(wrap_s, bs[wrap_s]), (wrap_life, bs[wrap_life]), (wrap_score, bs[wrap_score]),
           (wrap_fr, bs[wrap_fr]), (wrap_ck, bs[wrap_ck]), (wrap_lt, bs[wrap_lt]),
           (wrap_sl, bs[wrap_sl]), (wrap_bl, bs[wrap_bl]), (wrap_ml, bs[wrap_ml]),
           (wrap_spd, bs[wrap_spd])])
    # stage > max → 풀 리셋 / 아니면 클리어 보너스 +500
    if_wrap = b_ifelse(bs, c_max, wrap_s, add_sc)
    # 공통: 파워/관통 초기화 → 잠깐 연출 → 스테이지시작(and wait)
    reset_m = b_set(bs, "패들모드", V_MODE, 0)
    reset_pi = b_set(bs, "관통", V_PIERCE, 0)
    reset_sl = b_set(bs, "감속", V_SLOW, 0)
    w = b_wait(bs, 1.0)
    bc_st = b_broadcast_wait(bs, "스테이지시작", BR_STAGE)
    unlock = b_set(bs, "게임상태", V_STATE, 1)
    chain([(lock_st, bs[lock_st]), (lock_rdy, bs[lock_rdy]), (lock_ln, bs[lock_ln]),
           (snd_clear, bs[snd_clear]), (clr_fc, bs[clr_fc]), (clr_fl, bs[clr_fl]),
           (clr_sp, bs[clr_sp]), (inc_s, bs[inc_s]), (if_wrap, bs[if_wrap]),
           (reset_m, bs[reset_m]), (reset_pi, bs[reset_pi]),
           (reset_sl, bs[reset_sl]), (w, bs[w]), (bc_st, bs[bc_st]), (unlock, bs[unlock])])
    if_clear = b_if(bs, c_can_clear, lock_st)
    chain([(h3, bs[h3]), (if_clear, bs[if_clear])])

    # ───────────────── 난장판(카오스) 스케줄러 ─────────────────
    def wait_var(name, vid):
        d = vrep(name, vid)
        wb = gen(); bs[wb] = mk("control_wait", inputs={"DURATION": slot(d)}); bs[d]["parent"] = wb
        return wb
    def flash(col):
        s = b_set(bs, "번쩍색", V_FLASHCOL, col)
        b = b_broadcast(bs, "번쩍", BR_FLASH)
        bs[s]["next"] = b; bs[b]["parent"] = s
        return s
    c_playing = lambda: cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_rdy = lambda: cmp_op("operator_equals", vrep("준비됨", V_READY), 1)

    # 1) 멀티볼 웨이브 — 주기적으로 노란공 무더기 소환
    hw = gen(); bs[hw] = mk("event_whenbroadcastreceived", top=True, x=360, y=20,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    w_wait = wait_var("웨이브간격", V_WAVEGAP)
    w_flash = flash(45)          # 노랑 계열 번쩍
    w_spark = b_broadcast(bs, "스파크", BR_SPARK)
    serve_b = b_broadcast(bs, "보너스서브", BR_BONUS)
    serve_w = b_wait(bs, 0.04)
    chain([(serve_b, bs[serve_b]), (serve_w, bs[serve_w])])
    w_times = op("operator_add", vrep("웨이브개수", V_WAVEN), vrep("광란레벨", V_FRENZY))
    w_rep = b_repeat(bs, w_times, serve_b); bs[w_times]["parent"] = w_rep
    chain([(w_flash, bs[w_flash])])
    # flash() 는 head 만 반환하니 tail(broadcast 번쩍) 뒤에 spark·repeat 이어붙임
    fl_tail = bs[w_flash]["next"]  # broadcast 번쩍
    bs[fl_tail]["next"] = w_spark; bs[w_spark]["parent"] = fl_tail
    bs[w_spark]["next"] = w_rep; bs[w_rep]["parent"] = w_spark
    w_cond = bool_op("operator_and", c_playing(), c_rdy())
    w_if = b_if(bs, w_cond, w_flash)
    chain([(w_wait, bs[w_wait]), (w_if, bs[w_if])])
    w_fe = b_forever(bs, w_wait)
    chain([(hw, bs[hw]), (w_fe, bs[w_fe])])

    # 2) 레이저 광란 트리거 — 주기적으로 레이저 연사 창 열기
    hl = gen(); bs[hl] = mk("event_whenbroadcastreceived", top=True, x=360, y=160,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    l_wait = wait_var("레이저간격", V_LASGAP)
    l_flash = flash(100)         # 청록 번쩍
    # 레이저타임 = 레이저연사
    lshots = vrep("레이저연사", V_LASSHOTS)
    l_set = gen(); bs[l_set] = mk("data_setvariableto", inputs={"VALUE": slot(lshots)},
                                  fields={"VARIABLE": ["레이저타임", V_LASERTIME]}); bs[lshots]["parent"] = l_set
    fl_tail2 = bs[l_flash]["next"]
    bs[fl_tail2]["next"] = l_set; bs[l_set]["parent"] = fl_tail2
    l_cond = bool_op("operator_and", c_playing(), c_rdy())
    l_if = b_if(bs, l_cond, l_flash)
    chain([(l_wait, bs[l_wait]), (l_if, bs[l_if])])
    l_fe = b_forever(bs, l_wait)
    chain([(hl, bs[hl]), (l_fe, bs[l_fe])])

    # 2b) 레이저 자동발사 — 레이저타임>0 이면 계속 쏨
    hf = gen(); bs[hf] = mk("event_whenbroadcastreceived", top=True, x=360, y=300,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    f_cond = bool_op("operator_and", c_playing(),
                     cmp_op("operator_gt", vrep("레이저타임", V_LASERTIME), 0))
    f_mode = b_set(bs, "패들모드", V_MODE, 2)
    f_fire = b_broadcast(bs, "레이저발사", BR_FIRE)
    f_dec = b_chg(bs, "레이저타임", V_LASERTIME, -1)
    f_off = b_set(bs, "패들모드", V_MODE, 0)
    f_end_c = cmp_op("operator_lt", vrep("레이저타임", V_LASERTIME), 1)
    f_if_off = b_if(bs, f_end_c, f_off)
    f_wait = b_wait(bs, 0.2)
    chain([(f_mode, bs[f_mode]), (f_fire, bs[f_fire]), (f_dec, bs[f_dec]),
           (f_if_off, bs[f_if_off]), (f_wait, bs[f_wait])])
    f_wait2 = b_wait(bs, 0.06)
    f_ie = b_ifelse(bs, f_cond, f_mode, f_wait2)
    f_fe = b_forever(bs, f_ie)
    chain([(hf, bs[hf]), (f_fe, bs[f_fe])])

    # 3) 공속 상승 — 시간 지날수록 공이 빨라짐
    hs = gen(); bs[hs] = mk("event_whenbroadcastreceived", top=True, x=360, y=440,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    s_wait = wait_var("공속상승간격", V_SPDGAP)
    s_cond = bool_op("operator_and", bool_op("operator_and", c_playing(), c_rdy()),
                     cmp_op("operator_lt", vrep("공속도", V_SPD), vrep("공속상한", V_SPDMAX)))
    spd_plus = op("operator_add", vrep("공속도", V_SPD), 1)
    s_inc = gen(); bs[s_inc] = mk("data_setvariableto", inputs={"VALUE": slot(spd_plus)},
                                  fields={"VARIABLE": ["공속도", V_SPD]}); bs[spd_plus]["parent"] = s_inc
    s_flash = flash(15)          # 주황 번쩍
    chain([(s_inc, bs[s_inc]), (s_flash, bs[s_flash])])
    s_if = b_if(bs, s_cond, s_inc)
    chain([(s_wait, bs[s_wait]), (s_if, bs[s_if])])
    s_fe = b_forever(bs, s_wait)
    chain([(hs, bs[hs]), (s_fe, bs[s_fe])])

    # 4) 광란레벨 상승 (완만) — 웨이브 규모·배경 드리프트가 세짐
    hfz = gen(); bs[hfz] = mk("event_whenbroadcastreceived", top=True, x=360, y=560,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    fz_wait = b_wait(bs, 12)
    fz_c = bool_op("operator_and", c_playing(),
                   cmp_op("operator_lt", vrep("광란레벨", V_FRENZY), 6))
    fz_inc = b_chg(bs, "광란레벨", V_FRENZY, 1)
    fz_if = b_if(bs, fz_c, fz_inc)
    chain([(fz_wait, bs[fz_wait]), (fz_if, bs[fz_if])])
    fz_fe = b_forever(bs, fz_wait)
    chain([(hfz, bs[hfz]), (fz_fe, bs[fz_fe])])

    # 5) 배경 색 드리프트 — 은은하게 배경 색이 계속 흐름 (가독성 위해 약하게 고정)
    hbg = gen(); bs[hbg] = mk("event_whenbroadcastreceived", top=True, x=360, y=680,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    bg_chg = change_effect(bs, "COLOR", 3)
    bg_if = b_if(bs, c_playing(), bg_chg)
    bg_wait = b_wait(bs, 0.12)
    chain([(bg_if, bs[bg_if]), (bg_wait, bs[bg_wait])])
    bg_fe = b_forever(bs, bg_if)
    chain([(hbg, bs[hbg]), (bg_fe, bs[bg_fe])])

    # BGM: 별도 깃발 스크립트 — set volume → forever play until done (루프)
    h_bgm = gen(); bs[h_bgm] = mk("event_whenflagclicked", top=True, x=700, y=20)
    bgmvol_r = vrep("브금볼륨", V_BGMVOL)
    setvol = gen(); bs[setvol] = mk("sound_setvolumeto", inputs={"VOLUME": slot(bgmvol_r)})
    bs[bgmvol_r]["parent"] = setvol
    bgm_menu = gen(); bs[bgm_menu] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["bgm", None]}, shadow=True)
    play_bgm = gen(); bs[play_bgm] = mk("sound_playuntildone", inputs={"SOUND_MENU": [1, bgm_menu]})
    bs[bgm_menu]["parent"] = play_bgm
    fe_bgm = b_forever(bs, play_bgm)
    chain([(h_bgm, bs[h_bgm]), (setvol, bs[setvol]), (fe_bgm, bs[fe_bgm])])
    return bs


def build_paddle():
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    sh = gen(); bs[sh] = mk("looks_show")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    g0 = gen(); bs[g0] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(PADDLE_Y)})
    # forever: arrow keys move, space fire/serve
    # left
    c_left = bool_op("operator_or", b_key(bs, "left arrow"), b_key(bs, "a"))
    ch_l = gen(); bs[ch_l] = mk("motion_changexby", inputs={"DX": num(-12)})
    if_left = b_if(bs, c_left, ch_l)
    # right
    c_right = bool_op("operator_or", b_key(bs, "right arrow"), b_key(bs, "d"))
    ch_r = gen(); bs[ch_r] = mk("motion_changexby", inputs={"DX": num(12)})
    if_right = b_if(bs, c_right, ch_r)
    # clamp
    xp = gen(); bs[xp] = mk("motion_xposition")
    c_l = cmp_op("operator_lt", xp, -200)
    sxl = gen(); bs[sxl] = mk("motion_setx", inputs={"X": num(-200)})
    if_l = b_if(bs, c_l, sxl)
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_r = cmp_op("operator_gt", xp2, 200)
    sxr = gen(); bs[sxr] = mk("motion_setx", inputs={"X": num(200)})
    if_r = b_if(bs, c_r, sxr)
    sy = gen(); bs[sy] = mk("motion_sety", inputs={"Y": num(PADDLE_Y)})
    c_w = cmp_op("operator_equals", vrep("패들모드", V_MODE), 1)
    c_l2 = cmp_op("operator_equals", vrep("패들모드", V_MODE), 2)
    sw_w = costume_name(bs, "wide")
    sw_l = costume_name(bs, "laser")
    sw_n = costume_name(bs, "normal")
    if_laser = b_ifelse(bs, c_l2, sw_l, sw_n)
    if_wide = b_ifelse(bs, c_w, sw_w, if_laser)
    ssz = gen(); bs[ssz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    # space: 준비됨=1 일 때만 (벽돌 다 깔린 뒤)
    c_sp = b_key(bs, "space")
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_ready = cmp_op("operator_equals", vrep("준비됨", V_READY), 1)
    c_ok = bool_op("operator_and", c_play, c_ready)
    c_do = bool_op("operator_and", c_sp, c_ok)
    c_nolaunch = cmp_op("operator_equals", vrep("발사됨", V_LAUNCH), 0)
    set_launch = b_set(bs, "발사됨", V_LAUNCH, 1)
    set_launch2 = b_set(bs, "발사됨", V_LAUNCH, 1)
    c_las = cmp_op("operator_equals", vrep("패들모드", V_MODE), 2)
    snd_laser = play_sound(bs, "laser")
    bc_fire = b_broadcast(bs, "레이저발사", BR_FIRE)
    chain([(snd_laser, bs[snd_laser]), (bc_fire, bs[bc_fire])])
    if_las = b_ifelse(bs, c_las, snd_laser, set_launch2)
    if_ser = b_ifelse(bs, c_nolaunch, set_launch, if_las)
    w_sp = b_wait(bs, 0.15)
    chain([(if_ser, bs[if_ser]), (w_sp, bs[w_sp])])
    if_sp = b_if(bs, c_do, if_ser)
    w0 = b_wait(bs, 0.03)
    chain([(if_left, bs[if_left]), (if_right, bs[if_right]),
           (if_l, bs[if_l]), (if_r, bs[if_r]), (sy, bs[sy]),
           (if_wide, bs[if_wide]), (ssz, bs[ssz]), (if_sp, bs[if_sp]), (w0, bs[w0])])
    fe = b_forever(bs, if_left)
    chain([(h2, bs[h2]), (sh, bs[sh]), (rs, bs[rs]), (g0, bs[g0]), (fe, bs[fe])])
    return bs


def build_ball():
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])

    def spawn_ball():
        return create_clone(bs)

    # stage start: 클론 삭제 + 카운트 리셋. 메인공은 벽돌 준비 후에만
    h_st = gen(); bs[h_st] = mk("event_whenbroadcastreceived", top=True, x=20, y=100,
        fields={"BROADCAST_OPTION": ["스테이지시작", BR_STAGE]})
    c_clone = cmp_op("operator_equals", vrep("복제됨", V_ISC), 1)
    del_old = gen(); bs[del_old] = mk("control_delete_this_clone")
    set_b0 = b_set(bs, "공개수", V_BALLS, 0)
    set_l0 = b_set(bs, "발사됨", V_LAUNCH, 0)
    set_ml0 = b_set(bs, "메인존재", V_MAINLIVE, 0)
    set_rdy0 = b_set(bs, "준비됨", V_READY, 0)
    chain([(set_b0, bs[set_b0]), (set_l0, bs[set_l0]), (set_ml0, bs[set_ml0]),
           (set_rdy0, bs[set_rdy0])])
    if_st = b_ifelse(bs, c_clone, del_old, set_b0)
    chain([(h_st, bs[h_st]), (if_st, bs[if_st])])

    # 준비완료(벽돌 전부 생성 후): 메인공 서브
    h_rdy = gen(); bs[h_rdy] = mk("event_whenbroadcastreceived", top=True, x=20, y=160,
        fields={"BROADCAST_OPTION": ["준비완료", BR_READY]})
    c_orig_r = cmp_op("operator_equals", vrep("복제됨", V_ISC), 0)
    bc_main_r = b_broadcast(bs, "메인공서브", BR_MAIN)
    if_or = b_if(bs, c_orig_r, bc_main_r)
    chain([(h_rdy, bs[h_rdy]), (if_or, bs[if_or])])

    # 메인공서브: 메인존재=0 일 때만 주황공 1개
    h_main = gen(); bs[h_main] = mk("event_whenbroadcastreceived", top=True, x=20, y=220,
        fields={"BROADCAST_OPTION": ["메인공서브", BR_MAIN]})
    c_orig_m = cmp_op("operator_equals", vrep("복제됨", V_ISC), 0)
    c_no_main = cmp_op("operator_equals", vrep("메인존재", V_MAINLIVE), 0)
    set_sm1 = b_set(bs, "스폰메인", V_SPAWNMAIN, 1)
    set_loc_m = b_set(bs, "메인공", V_ISMAIN, 1)
    cc_m = spawn_ball()
    w0m = b_wait(bs, 0)
    chain([(set_sm1, bs[set_sm1]), (set_loc_m, bs[set_loc_m]),
           (cc_m, bs[cc_m]), (w0m, bs[w0m])])
    if_nm = b_if(bs, c_no_main, set_sm1)
    if_om = b_if(bs, c_orig_m, if_nm)
    chain([(h_main, bs[h_main]), (if_om, bs[if_om])])

    # 보너스서브: 항상 노랑 보너스 (메인공 절대 아님)
    h_bn = gen(); bs[h_bn] = mk("event_whenbroadcastreceived", top=True, x=20, y=340,
        fields={"BROADCAST_OPTION": ["보너스서브", BR_BONUS]})
    c_orig_b = cmp_op("operator_equals", vrep("복제됨", V_ISC), 0)
    c_can = cmp_op("operator_lt", vrep("공개수", V_BALLS), vrep("멀티볼최대", V_MAXBALLS))
    set_sm0 = b_set(bs, "스폰메인", V_SPAWNMAIN, 0)
    set_loc_b = b_set(bs, "메인공", V_ISMAIN, 0)
    cc_b = spawn_ball()
    w0b = b_wait(bs, 0)
    chain([(set_sm0, bs[set_sm0]), (set_loc_b, bs[set_loc_b]),
           (cc_b, bs[cc_b]), (w0b, bs[w0b])])
    if_can = b_if(bs, c_can, set_sm0)
    if_ob = b_if(bs, c_orig_b, if_can)
    chain([(h_bn, bs[h_bn]), (if_ob, bs[if_ob])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=480)
    set_isc = b_set(bs, "복제됨", V_ISC, 1)
    # 메인공 타입은 create 직전 원본이 세팅 → 클론 상속값만 사용
    # (스폰메인을 다시 읽으면 연속 스폰 시 레이스로 전부 주황이 됨)
    inc_b = b_chg(bs, "공개수", V_BALLS, 1)
    c_main0 = cmp_op("operator_equals", vrep("메인공", V_ISMAIN), 1)
    cos_m = costume_name(bs, "main")
    set_live = b_set(bs, "메인존재", V_MAINLIVE, 1)
    chain([(cos_m, bs[cos_m]), (set_live, bs[set_live])])
    cos_b = costume_name(bs, "bonus")
    if_cos = b_ifelse(bs, c_main0, cos_m, cos_b)
    rnd = gen(); bs[rnd] = mk("operator_random", inputs={"FROM": num(-5), "TO": num(5)})
    set_vx = b_set(bs, "속도X", V_VX, rnd)
    set_vy = b_set(bs, "속도Y", V_VY, vrep("공속도", V_SPD))
    # 메인은 패들에 붙음, 보너스는 바로 날아감
    set_stuck_m = b_set(bs, "붙음", V_STUCK, 1)
    set_stuck_b = b_set(bs, "붙음", V_STUCK, 0)
    c_main1 = cmp_op("operator_equals", vrep("메인공", V_ISMAIN), 1)
    if_stuck0 = b_ifelse(bs, c_main1, set_stuck_m, set_stuck_b)
    sh = gen(); bs[sh] = mk("looks_show")
    ssz = gen(); bs[ssz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})
    # stick on paddle until launch
    # forever physics
    # --- stuck ---
    def sensing_of(prop, obj):
        m = gen(); bs[m] = mk("sensing_of_object_menu", fields={"OBJECT": [obj, None]}, shadow=True)
        s = gen(); bs[s] = mk("sensing_of", inputs={"OBJECT": [1, m]}, fields={"PROPERTY": [prop, None]})
        bs[m]["parent"] = s
        return s
    c_stuck = cmp_op("operator_equals", vrep("붙음", V_STUCK), 1)
    pxx = sensing_of("x position", "패들")
    gt = gen(); bs[gt] = mk("motion_gotoxy", inputs={"X": slot(pxx), "Y": num(PADDLE_Y + 18)})
    bs[pxx]["parent"] = gt
    c_launched = cmp_op("operator_equals", vrep("발사됨", V_LAUNCH), 1)
    # 발사 순간 반드시 위로 쏜다 (캐치로 잡은 하강 공이 아래로 발사돼 즉사하는 것 방지)
    set_relaunch_vy = b_set(bs, "속도Y", V_VY, vrep("공속도", V_SPD))
    set_unstuck = b_set(bs, "붙음", V_STUCK, 0)
    chain([(set_relaunch_vy, bs[set_relaunch_vy]), (set_unstuck, bs[set_unstuck])])
    if_go = b_if(bs, c_launched, set_relaunch_vy)
    chain([(gt, bs[gt]), (if_go, bs[if_go])])
    if_stuck = b_if(bs, c_stuck, gt)

    # --- free flight (단순·확실) ---
    c_free = cmp_op("operator_equals", vrep("붙음", V_STUCK), 0)
    # move full step
    vx = vrep("속도X", V_VX)
    cx = gen(); bs[cx] = mk("motion_changexby", inputs={"DX": slot(vx)}); bs[vx]["parent"] = cx
    vy = vrep("속도Y", V_VY)
    cy = gen(); bs[cy] = mk("motion_changeyby", inputs={"DY": slot(vy)}); bs[vy]["parent"] = cy

    # walls
    xp = gen(); bs[xp] = mk("motion_xposition")
    c_wl = cmp_op("operator_lt", xp, WALL_L)
    set_vxl = b_set(bs, "속도X", V_VX, op("operator_subtract", 0, vrep("속도X", V_VX)))
    sxl = gen(); bs[sxl] = mk("motion_setx", inputs={"X": num(WALL_L + 2)})
    chain([(set_vxl, bs[set_vxl]), (sxl, bs[sxl])])
    if_wl = b_if(bs, c_wl, set_vxl)
    xp2 = gen(); bs[xp2] = mk("motion_xposition")
    c_wr = cmp_op("operator_gt", xp2, WALL_R)
    set_vxr = b_set(bs, "속도X", V_VX, op("operator_subtract", 0, vrep("속도X", V_VX)))
    sxr = gen(); bs[sxr] = mk("motion_setx", inputs={"X": num(WALL_R - 2)})
    chain([(set_vxr, bs[set_vxr]), (sxr, bs[sxr])])
    if_wr = b_if(bs, c_wr, set_vxr)
    yp = gen(); bs[yp] = mk("motion_yposition")
    c_top = cmp_op("operator_gt", yp, WALL_T)
    set_vyt = b_set(bs, "속도Y", V_VY, op("operator_subtract", 0, vrep("속도Y", V_VY)))
    syt = gen(); bs[syt] = mk("motion_sety", inputs={"Y": num(WALL_T - 2)})
    chain([(set_vyt, bs[set_vyt]), (syt, bs[syt])])
    if_top = b_if(bs, c_top, set_vyt)

    # paddle: 닿음 + 하강만
    c_pad = touching(bs, "패들")
    c_going_down = cmp_op("operator_lt", vrep("속도Y", V_VY), 0)
    c_pad_do = bool_op("operator_and", c_pad, c_going_down)
    # 캐치는 주황 메인공만 잡는다. 노란 보너스공은 항상 튕겨야(쟁반에 붙어 안 쏴지는 버그 방지)
    c_catch = bool_op("operator_and",
                      cmp_op("operator_equals", vrep("패들모드", V_MODE), 3),
                      cmp_op("operator_equals", vrep("메인공", V_ISMAIN), 1))
    set_st = b_set(bs, "붙음", V_STUCK, 1)
    set_ln = b_set(bs, "발사됨", V_LAUNCH, 0)
    chain([(set_st, bs[set_st]), (set_ln, bs[set_ln])])
    set_vyb = b_set(bs, "속도Y", V_VY, vrep("공속도", V_SPD))
    set_y_up = gen(); bs[set_y_up] = mk("motion_sety", inputs={"Y": num(PADDLE_Y + 16)})
    bx = gen(); bs[bx] = mk("motion_xposition")
    pxxx = sensing_of("x position", "패들")
    dx = op("operator_subtract", bx, pxxx)
    set_vxb = b_set(bs, "속도X", V_VX, op("operator_multiply", dx, 0.12))
    snd_pad = play_sound(bs, "bounce")
    chain([(set_vyb, bs[set_vyb]), (set_y_up, bs[set_y_up]),
           (set_vxb, bs[set_vxb]), (snd_pad, bs[snd_pad])])
    if_bounce = b_ifelse(bs, c_catch, set_st, set_vyb)
    if_pad = b_if(bs, c_pad_do, if_bounce)

    # brick: 벽돌에 닿은 "그 프레임"에 방송으로 벽돌이 스스로 판정하게 한다.
    # (기존엔 공은 반사하고 벽돌은 자기 forever 로 touching 공 을 따로 샘플 → 공이
    #  먼저 빠져나가 벽돌이 히트를 놓치는 레이스 → "빨간(맨 윗줄) 벽돌이 튕기기만" 발생)
    # 타격쿨 로 한 번의 접촉당 방송·반사를 1회로 제한 (연속 프레임 중복 반사·중복 히트 방지).
    c_br = touching(bs, "벽돌")
    c_cd0 = cmp_op("operator_equals", vrep("타격쿨", V_HITCD), 0)
    c_do_hit = bool_op("operator_and", c_br, c_cd0)
    c_np = cmp_op("operator_equals", vrep("관통", V_PIERCE), 0)
    # broadcast AND WAIT: nudge/반사 전에, 공이 벽돌과 완전히 겹친 그 시점에
    # 벽돌이 동기로 touching 공 을 확인 → 밀어내기 레이스 없이 항상 파괴.
    bc_hit = b_broadcast_wait(bs, "벽돌타격", BR_BRICKHIT)
    snd_br = play_sound(bs, "hit")
    set_cd = b_set(bs, "타격쿨", V_HITCD, 2)
    flip = b_set(bs, "속도Y", V_VY, op("operator_subtract", 0, vrep("속도Y", V_VY)))
    nudge = op("operator_multiply", vrep("속도Y", V_VY), 0.35)
    chy_n = gen(); bs[chy_n] = mk("motion_changeyby", inputs={"DY": slot(nudge)}); bs[nudge]["parent"] = chy_n
    chain([(flip, bs[flip]), (chy_n, bs[chy_n])])
    if_reflect = b_if(bs, c_np, flip)   # 관통이면 반사 없이 통과, 아니면 반사+분리
    chain([(bc_hit, bs[bc_hit]), (snd_br, bs[snd_br]), (set_cd, bs[set_cd]),
           (if_reflect, bs[if_reflect])])
    if_br = b_if(bs, c_do_hit, bc_hit)
    # 쿨다운 감소 (매 프레임)
    c_cd_pos = cmp_op("operator_gt", vrep("타격쿨", V_HITCD), 0)
    dec_cd = b_chg(bs, "타격쿨", V_HITCD, -1)
    if_cd = b_if(bs, c_cd_pos, dec_cd)
    chain([(if_br, bs[if_br]), (if_cd, bs[if_cd])])

    # 사망: y < DEATH_Y 이면 무조건 (단순·확실)
    yp2 = gen(); bs[yp2] = mk("motion_yposition")
    c_bot = cmp_op("operator_lt", yp2, DEATH_Y)
    dec_cnt = b_chg(bs, "공개수", V_BALLS, -1)
    set_ml_dead = b_set(bs, "메인존재", V_MAINLIVE, 0)
    bc_lost = b_broadcast(bs, "공놓침", BR_LOST)
    dell_m = gen(); bs[dell_m] = mk("control_delete_this_clone")
    chain([(dec_cnt, bs[dec_cnt]), (set_ml_dead, bs[set_ml_dead]),
           (bc_lost, bs[bc_lost]), (dell_m, bs[dell_m])])
    dec_b = b_chg(bs, "공개수", V_BALLS, -1)
    sc_b = b_chg(bs, "점수", V_SCORE, 1)
    dell_b = gen(); bs[dell_b] = mk("control_delete_this_clone")
    chain([(dec_b, bs[dec_b]), (sc_b, bs[sc_b]), (dell_b, bs[dell_b])])
    c_ism = cmp_op("operator_equals", vrep("메인공", V_ISMAIN), 1)
    if_floor = b_ifelse(bs, c_ism, dec_cnt, dec_b)
    if_bot = b_if(bs, c_bot, if_floor)

    w_tick = b_wait(bs, 0.02)
    chain([(cx, bs[cx]), (cy, bs[cy]), (if_wl, bs[if_wl]), (if_wr, bs[if_wr]),
           (if_top, bs[if_top]), (if_pad, bs[if_pad]), (if_br, bs[if_br]),
           (if_cd, bs[if_cd]), (if_bot, bs[if_bot]), (w_tick, bs[w_tick])])
    if_free = b_if(bs, c_free, cx)

    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    chain([(if_stuck, bs[if_stuck]), (if_free, bs[if_free])])
    if_play = b_if(bs, c_play, if_stuck)
    w1 = b_wait(bs, 0.01)
    chain([(if_play, bs[if_play]), (w1, bs[w1])])
    fe = b_forever(bs, if_play)
    chain([(ch, bs[ch]), (set_isc, bs[set_isc]),
           (inc_b, bs[inc_b]), (if_cos, bs[if_cos]),
           (set_vx, bs[set_vx]), (set_vy, bs[set_vy]), (if_stuck0, bs[if_stuck0]),
           (rs, bs[rs]), (ssz, bs[ssz]), (sh, bs[sh]), (fe, bs[fe])])
    return bs


def build_brick():
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])

    # spawn stage bricks from patterns encoded in build-time unrolled... 
    # Runtime: use 스테이지 number and nested loops with precomputed via lists
    # Simpler: on 스테이지시작, original runs Python-unrolled create? Too big.
    # Use list 맵 built on stage flag... Stage doesn't have it.
    # Brick original builds from STAGES via variables 행 열 and stage-specific 
    # We'll store stage maps as long strings in lists at flag on brick.

    # 남은 벽돌 클론 정리 (스테이지 전환·풀 리셋 시 고아 방지)
    wipe_on_stage_start(bs, vrep, cmp_op, y=40)

    h_st = gen(); bs[h_st] = mk("event_whenbroadcastreceived", top=True, x=20, y=100,
        fields={"BROADCAST_OPTION": ["스테이지시작", BR_STAGE]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_ISC), 0)
    # 클론 delete 스크립트가 먼저 돌 시간을 준 뒤 스폰 (레이스 방지)
    wait_wipe = b_wait(bs, 0.15)
    set_cnt = b_set(bs, "남은벽돌", V_BRICKS, 0)
    set_boss0 = b_set(bs, "보스체력", V_BOSSHP, 0)
    # For each stage we need map — use 스테이지 var and if ladder for 5 stages
    # Compact: loop r,c and call a "get cell" using formula from stage
    # Easiest path: 5 separate scripts when stage equals N — heavy but clear
    # Medium: list 벽돌맵 of 10*6*5 = 300 entries at init

    # Init map list on this script once
    # Actually add list on stage at flag — move map init to stage.
    # For brick: read L_MAP index = (stage-1)*60 + r*10 + c

    set_r = b_set(bs, "행", V_R, 0)
    # I'll use nested repeat
    # index helper later

    # Build map list once at flag for brick original - in h_st first time
    # Simpler approach for reliability: unrolled stage spawns with Python

    body_heads = []
    # Generate spawn sequence in Python for each stage
    # At runtime: if 스테이지==1: run seq1 elif ...
    
    def make_stage_spawn(stage_idx):
        """Returns head block id of spawn chain for one stage."""
        pat = STAGES[stage_idx]
        first = None
        prev = None
        count = 0
        for r, row in enumerate(pat):
            for c, ch in enumerate(row):
                if ch == "0":
                    continue
                t = int(ch)
                if t <= 6:
                    hp, kind = 1, t
                elif t == 7:
                    hp, kind = 2, 7
                elif t == 8:
                    hp, kind = 1, 8
                else:
                    # 9 = 보스 왕벽돌
                    hp, kind = BOSS_HP, 9
                x = OX + c * BW
                y = OY - r * BH
                # 스폰 변수 설정 후 클론 생성 → wait 0 으로 클론이
                # 공유 변수(스폰X/Y)를 읽어 자리 잡게 한 뒤 다음 벽돌 스폰
                # (wait 없으면 전부 같은 위치/마지막 값만 보여 "벽돌 1개"처럼 보임)
                s1 = b_set(bs, "스폰X", V_BX, x)
                s2 = b_set(bs, "스폰Y", V_BY, y)
                s3 = b_set(bs, "스폰체력", V_BHP, hp)
                s4 = b_set(bs, "스폰종류", V_BTYPE, kind)
                steps = [(s1, bs[s1]), (s2, bs[s2]), (s3, bs[s3]), (s4, bs[s4])]
                if kind == 9:
                    sb = b_set(bs, "보스체력", V_BOSSHP, BOSS_HP)
                    steps.append((sb, bs[sb]))
                cc = create_clone(bs)
                w0 = b_wait(bs, 0)
                steps.extend([(cc, bs[cc]), (w0, bs[w0])])
                chain(steps)
                if first is None:
                    first = s1
                if prev is not None:
                    end = prev
                    while bs[end].get("next"):
                        end = bs[end]["next"]
                    bs[end]["next"] = s1
                    bs[s1]["parent"] = end
                prev = s1
                count += 1
        sc = b_set(bs, "남은벽돌", V_BRICKS, count)
        if prev is None:
            return sc, count
        end = prev
        while bs[end].get("next"):
            end = bs[end]["next"]
        bs[end]["next"] = sc
        bs[sc]["parent"] = end
        return first, count

    # if stage == 1..5
    heads = []
    for si in range(len(STAGES)):
        hd, _ = make_stage_spawn(si)
        heads.append(hd)
    # build if-else ladder from end
    # if stage==5: h4 elif stage==4 ... 
    # Simple: repeat check
    # stage 1
    c1 = cmp_op("operator_equals", vrep("스테이지", V_STAGE), 1)
    c2 = cmp_op("operator_equals", vrep("스테이지", V_STAGE), 2)
    c3 = cmp_op("operator_equals", vrep("스테이지", V_STAGE), 3)
    c4 = cmp_op("operator_equals", vrep("스테이지", V_STAGE), 4)
    # default 5
    if4 = b_ifelse(bs, c4, heads[3], heads[4])
    if3 = b_ifelse(bs, c3, heads[2], if4)
    if2 = b_ifelse(bs, c2, heads[1], if3)
    if1 = b_ifelse(bs, c1, heads[0], if2)
    # 벽돌 전부 스폰 후 준비완료 → 그때부터 발사 가능 + 메인공 생성
    set_ready = b_set(bs, "준비됨", V_READY, 1)
    bc_ready = b_broadcast(bs, "준비완료", BR_READY)
    chain([(wait_wipe, bs[wait_wipe]), (set_boss0, bs[set_boss0]), (set_cnt, bs[set_cnt]), (if1, bs[if1])])
    # after if1: set ready + broadcast
    # find end of if1 (ifelse is single block)
    bs[if1]["next"] = set_ready
    bs[set_ready]["parent"] = if1
    bs[set_ready]["next"] = bc_ready
    bs[bc_ready]["parent"] = set_ready
    bs[bc_ready]["next"] = None
    if_o = b_if(bs, c_orig, wait_wipe)
    bs[if_o]["inputs"]["SUBSTACK"] = [2, wait_wipe]
    bs[wait_wipe]["parent"] = if_o
    bs[if_o]["next"] = None
    chain([(h_st, bs[h_st]), (if_o, bs[if_o])])

    # clone life
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=500)
    set_isc = b_set(bs, "복제됨", V_ISC, 1)
    set_hp = b_set(bs, "체력", V_HP, vrep("스폰체력", V_BHP))
    set_k = b_set(bs, "종류", V_KIND, vrep("스폰종류", V_BTYPE))
    gx = vrep("스폰X", V_BX); gy = vrep("스폰Y", V_BY)
    gt = gen(); bs[gt] = mk("motion_gotoxy", inputs={"X": slot(gx), "Y": slot(gy)})
    bs[gx]["parent"] = gt; bs[gy]["parent"] = gt
    # costume by kind
    # if kind 7 hard, 8 bomb, else c{kind}
    c7 = cmp_op("operator_equals", vrep("종류", V_KIND), 7)
    c8 = cmp_op("operator_equals", vrep("종류", V_KIND), 8)
    c9 = cmp_op("operator_equals", vrep("종류", V_KIND), 9)
    sw_h = costume_name(bs, "hard")
    sw_b = costume_name(bs, "bomb")
    sw_boss = costume_name(bs, "boss1")
    def cos_for(k):
        return costume_name(bs, f"c{k}")
    sw6 = cos_for(6)
    cur = sw6
    for k in range(5, 0, -1):
        ck = cmp_op("operator_equals", vrep("종류", V_KIND), k)
        cur = b_ifelse(bs, ck, cos_for(k), cur)
    if_bomb = b_ifelse(bs, c8, sw_b, cur)
    if_hard = b_ifelse(bs, c7, sw_h, if_bomb)
    if_boss_cos = b_ifelse(bs, c9, sw_boss, if_hard)
    # 보스 = 큰 사이즈, 일반 = 90
    ssz_boss = gen(); bs[ssz_boss] = mk("looks_setsizeto", inputs={"SIZE": num(BOSS_SIZE)})
    ssz_norm = gen(); bs[ssz_norm] = mk("looks_setsizeto", inputs={"SIZE": num(90)})
    ssz = b_ifelse(bs, cmp_op("operator_equals", vrep("종류", V_KIND), 9), ssz_boss, ssz_norm)
    sh = gen(); bs[sh] = mk("looks_show")
    rs = gen(); bs[rs] = mk("motion_setrotationstyle", fields={"STYLE": ["don't rotate", None]})

    # 히트 처리 한 벌을 새 블록으로 찍어내는 헬퍼 (forever·방송 두 곳에서 재사용)
    def make_hit_chain():
        hit_dec = b_chg(bs, "체력", V_HP, -1)
        # 보스: 모니터 동기화 + 페이즈 코스튬
        c_is_boss = cmp_op("operator_equals", vrep("종류", V_KIND), 9)
        sync_bhp = b_set(bs, "보스체력", V_BOSSHP, vrep("체력", V_HP))
        # hp>8 boss1 / hp>4 boss2 / else boss3
        cos_b1 = costume_name(bs, "boss1")
        cos_b2 = costume_name(bs, "boss2")
        cos_b3 = costume_name(bs, "boss3")
        c_hi = cmp_op("operator_gt", vrep("체력", V_HP), 8)
        c_mid = cmp_op("operator_gt", vrep("체력", V_HP), 4)
        ph_mid = b_ifelse(bs, c_mid, cos_b2, cos_b3)
        ph = b_ifelse(bs, c_hi, cos_b1, ph_mid)
        chain([(sync_bhp, bs[sync_bhp]), (ph, bs[ph])])
        if_boss_ph = b_if(bs, c_is_boss, sync_bhp)

        hit_crack_c = bool_op("operator_and",
                              cmp_op("operator_equals", vrep("종류", V_KIND), 7),
                              cmp_op("operator_equals", vrep("체력", V_HP), 1))
        hit_sw = costume_name(bs, "hard2")
        hit_if_cr = b_if(bs, hit_crack_c, hit_sw)
        hit_dead_c = cmp_op("operator_lt", vrep("체력", V_HP), 1)
        snd_break = play_sound(bs, "break")
        # 일반 파괴 vs 보스 파괴
        hit_sc = b_chg(bs, "점수", V_SCORE, 10)
        hit_br = b_chg(bs, "남은벽돌", V_BRICKS, -1)
        hit_bom_c = cmp_op("operator_equals", vrep("종류", V_KIND), 8)
        hit_bon = b_chg(bs, "점수", V_SCORE, 40)
        hit_if_bom = b_if(bs, hit_bom_c, hit_bon)
        hit_rnd = gen(); bs[hit_rnd] = mk("operator_random", inputs={"FROM": num(1), "TO": num(100)})
        hit_st = b_set(bs, "임시", V_TMP, hit_rnd)
        hit_dc = cmp_op("operator_lt", vrep("임시", V_TMP), vrep("아이템확률", V_PCHANCE))
        hit_xp = gen(); bs[hit_xp] = mk("motion_xposition")
        hit_yp = gen(); bs[hit_yp] = mk("motion_yposition")
        hit_sx = b_set(bs, "스폰X", V_BX, hit_xp)
        hit_sy = b_set(bs, "스폰Y", V_BY, hit_yp)
        hit_rp = gen(); bs[hit_rp] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
        hit_pu = b_set(bs, "파워종류", V_PU, hit_rp)
        hit_cm = gen(); bs[hit_cm] = mk("control_create_clone_of_menu", fields={"CLONE_OPTION": ["파워업", None]}, shadow=True)
        hit_cc = gen(); bs[hit_cc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, hit_cm]})
        bs[hit_cm]["parent"] = hit_cc
        chain([(hit_sx, bs[hit_sx]), (hit_sy, bs[hit_sy]), (hit_pu, bs[hit_pu]), (hit_cc, bs[hit_cc])])
        hit_if_dr = b_if(bs, hit_dc, hit_sx)
        hit_clrc = bool_op(
            "operator_and",
            cmp_op("operator_lt", vrep("남은벽돌", V_BRICKS), 1),
            cmp_op("operator_equals", vrep("게임상태", V_STATE), 1),
        )
        hit_bc = b_broadcast(bs, "스테이지클리어", BR_CLEAR)
        hit_if_cl = b_if(bs, hit_clrc, hit_bc)
        hit_del = gen(); bs[hit_del] = mk("control_delete_this_clone")
        chain([(snd_break, bs[snd_break]), (hit_sc, bs[hit_sc]), (hit_br, bs[hit_br]),
               (hit_if_bom, bs[hit_if_bom]), (hit_st, bs[hit_st]), (hit_if_dr, bs[hit_if_dr]),
               (hit_if_cl, bs[hit_if_cl]), (hit_del, bs[hit_del])])

        # 보스 사망: 점수 크게 + 남은벽돌 0 + 강제 클리어 (호위 남아도 클리어)
        boss_sc = b_chg(bs, "점수", V_SCORE, 300)
        boss_zero = b_set(bs, "보스체력", V_BOSSHP, 0)
        boss_br0 = b_set(bs, "남은벽돌", V_BRICKS, 0)
        boss_bc = b_broadcast(bs, "스테이지클리어", BR_CLEAR)
        boss_del = gen(); bs[boss_del] = mk("control_delete_this_clone")
        c_can_cl = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
        boss_if_cl = b_if(bs, c_can_cl, boss_bc)
        chain([(boss_sc, bs[boss_sc]), (boss_zero, bs[boss_zero]), (boss_br0, bs[boss_br0]),
               (boss_if_cl, bs[boss_if_cl]), (boss_del, bs[boss_del])])
        # 보스 생존 칩: 점수 + 드롭(좋/나쁨)
        boss_chip_sc = b_chg(bs, "점수", V_SCORE, 25)
        boss_chip_snd = play_sound(bs, "hit")
        boss_rnd = gen(); bs[boss_rnd] = mk("operator_random", inputs={"FROM": num(1), "TO": num(100)})
        boss_st = b_set(bs, "임시", V_TMP, boss_rnd)
        # <28 좋은 파워 / <42 공속 상승(방해) / 그 외 없음
        c_good = cmp_op("operator_lt", vrep("임시", V_TMP), 28)
        c_bad = cmp_op("operator_lt", vrep("임시", V_TMP), 42)
        bxp = gen(); bs[bxp] = mk("motion_xposition")
        byp = gen(); bs[byp] = mk("motion_yposition")
        bsx = b_set(bs, "스폰X", V_BX, bxp)
        bsy = b_set(bs, "스폰Y", V_BY, byp)
        brp = gen(); bs[brp] = mk("operator_random", inputs={"FROM": num(1), "TO": num(6)})
        bpu = b_set(bs, "파워종류", V_PU, brp)
        bcm = gen(); bs[bcm] = mk("control_create_clone_of_menu", fields={"CLONE_OPTION": ["파워업", None]}, shadow=True)
        bcc = gen(); bs[bcc] = mk("control_create_clone_of", inputs={"CLONE_OPTION": [1, bcm]})
        bs[bcm]["parent"] = bcc
        chain([(bsx, bs[bsx]), (bsy, bs[bsy]), (bpu, bs[bpu]), (bcc, bs[bcc])])
        if_good = b_if(bs, c_good, bsx)
        # bad: 공속도 +2 (상한 이하)
        c_spd_ok = cmp_op("operator_lt", vrep("공속도", V_SPD), vrep("공속상한", V_SPDMAX))
        bad_up = b_chg(bs, "공속도", V_SPD, 2)
        if_spd = b_if(bs, c_spd_ok, bad_up)
        # bad only if not good: 28<=tmp<42
        c_bad_only = bool_op("operator_and",
                             cmp_op("operator_gt", vrep("임시", V_TMP), 27),
                             c_bad)
        if_bad = b_if(bs, c_bad_only, if_spd)
        chain([(boss_chip_sc, bs[boss_chip_sc]), (boss_chip_snd, bs[boss_chip_snd]),
               (boss_st, bs[boss_st]), (if_good, bs[if_good]), (if_bad, bs[if_bad])])
        c_boss_alive = cmp_op("operator_gt", vrep("체력", V_HP), 0)
        boss_live_or_die = b_ifelse(bs, c_boss_alive, boss_chip_sc, boss_sc)
        if_boss_hit = b_if(bs, c_is_boss, boss_live_or_die)

        # 일반 벽돌만 (보스 kind=9 제외)
        c_not_boss = not_op(cmp_op("operator_equals", vrep("종류", V_KIND), 9))
        snd_chip = play_sound(bs, "hit")
        hit_alive_c = cmp_op("operator_gt", vrep("체력", V_HP), 0)
        hit_if_chip = b_if(bs, bool_op("operator_and", hit_alive_c, c_not_boss), snd_chip)
        hit_if_dead = b_if(bs, bool_op("operator_and", hit_dead_c, c_not_boss), snd_break)

        chain([(hit_dec, bs[hit_dec]), (if_boss_ph, bs[if_boss_ph]), (hit_if_cr, bs[hit_if_cr]),
               (if_boss_hit, bs[if_boss_hit]), (hit_if_dead, bs[hit_if_dead]),
               (hit_if_chip, bs[hit_if_chip])])
        return hit_dec

    # forever: 레이저 히트만 (공은 방송으로 처리 → 크로스-스프라이트 레이스 제거)
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_las = touching(bs, "레이저")
    c_do_las = bool_op("operator_and", c_play, c_las)
    if_hit = b_if(bs, c_do_las, make_hit_chain())
    lw = b_wait(bs, 0.03)   # 레이저 연속 히트 살짝 억제
    chain([(if_hit, bs[if_hit]), (lw, bs[lw])])
    w0 = b_wait(bs, 0)
    chain([(lw, bs[lw]), (w0, bs[w0])])
    fe = b_forever(bs, if_hit)
    chain([(ch, bs[ch]), (set_isc, bs[set_isc]), (set_hp, bs[set_hp]), (set_k, bs[set_k]),
           (gt, bs[gt]), (if_boss_cos, bs[if_boss_cos]), (ssz, bs[ssz]), (rs, bs[rs]), (sh, bs[sh]),
           (fe, bs[fe])])

    # 벽돌타격 방송: 공이 닿은 그 프레임에 벽돌이 스스로 touching 공 판정 → 반드시 히트
    h_bh = gen(); bs[h_bh] = mk("event_whenbroadcastreceived", top=True, x=340, y=20,
        fields={"BROADCAST_OPTION": ["벽돌타격", BR_BRICKHIT]})
    c_isc_bh = cmp_op("operator_equals", vrep("복제됨", V_ISC), 1)
    c_play_bh = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    c_ball_bh = touching(bs, "공")
    c_bh = bool_op("operator_and", bool_op("operator_and", c_isc_bh, c_play_bh), c_ball_bh)
    if_bh = b_if(bs, c_bh, make_hit_chain())
    chain([(h_bh, bs[h_bh]), (if_bh, bs[if_bh])])
    return bs


def build_powerup():
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])
    wipe_on_stage_start(bs, vrep, cmp_op)

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=200)
    set_isc = b_set(bs, "복제됨", V_ISC, 1)
    # costume by 파워종류 1-6 -> M W L C P S
    names = ["M", "W", "L", "C", "P", "S"]
    # ifelse ladder
    sw = costume_name(bs, "M")
    for i, nm in enumerate(names[1:], 2):
        ci = cmp_op("operator_equals", vrep("파워종류", V_PU), i)
        sw = b_ifelse(bs, ci, costume_name(bs, nm), sw)
    # default already M; for 1 explicitly
    c1 = cmp_op("operator_equals", vrep("파워종류", V_PU), 1)
    sw = b_ifelse(bs, c1, costume_name(bs, "M"), sw)
    gx = vrep("스폰X", V_BX); gy = vrep("스폰Y", V_BY)
    gt = gen(); bs[gt] = mk("motion_gotoxy", inputs={"X": slot(gx), "Y": slot(gy)})
    bs[gx]["parent"] = gt; bs[gy]["parent"] = gt
    ssz = gen(); bs[ssz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    sh = gen(); bs[sh] = mk("looks_show")
    # fall
    c_play = cmp_op("operator_equals", vrep("게임상태", V_STATE), 1)
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": num(-4)})
    c_pad = touching(bs, "패들")
    # apply power
    # 1 multi 2 wide 3 laser 4 catch 5 pierce 6 slow
    c1 = cmp_op("operator_equals", vrep("파워종류", V_PU), 1)
    # 멀티볼 = 노란 보너스공 2개만 (주황 메인 추가 금지)
    bc_m = b_broadcast(bs, "보너스서브", BR_BONUS)
    w_m = b_wait(bs, 0)
    bc_m2 = b_broadcast(bs, "보너스서브", BR_BONUS)
    chain([(bc_m, bs[bc_m]), (w_m, bs[w_m]), (bc_m2, bs[bc_m2])])
    c2 = cmp_op("operator_equals", vrep("파워종류", V_PU), 2)
    set_w = b_set(bs, "패들모드", V_MODE, 1)
    c3 = cmp_op("operator_equals", vrep("파워종류", V_PU), 3)
    set_l = b_set(bs, "패들모드", V_MODE, 2)
    c4 = cmp_op("operator_equals", vrep("파워종류", V_PU), 4)
    set_c = b_set(bs, "패들모드", V_MODE, 3)
    c5 = cmp_op("operator_equals", vrep("파워종류", V_PU), 5)
    set_p = b_set(bs, "관통", V_PIERCE, 1)
    c6 = cmp_op("operator_equals", vrep("파워종류", V_PU), 6)
    set_s = b_set(bs, "공속도", V_SPD, SLOW_SPEED)
    if6 = b_if(bs, c6, set_s)
    if5 = b_ifelse(bs, c5, set_p, if6)
    if4 = b_ifelse(bs, c4, set_c, if5)
    if3 = b_ifelse(bs, c3, set_l, if4)
    if2 = b_ifelse(bs, c2, set_w, if3)
    if1 = b_ifelse(bs, c1, bc_m, if2)
    sc = b_chg(bs, "점수", V_SCORE, 5)
    snd_pu = play_sound(bs, "power")
    dell = gen(); bs[dell] = mk("control_delete_this_clone")
    chain([(if1, bs[if1]), (sc, bs[sc]), (snd_pu, bs[snd_pu]), (dell, bs[dell])])
    if_pad = b_if(bs, c_pad, if1)
    yp = gen(); bs[yp] = mk("motion_yposition")
    c_bot = cmp_op("operator_lt", yp, -170)
    dell2 = gen(); bs[dell2] = mk("control_delete_this_clone")
    if_bot = b_if(bs, c_bot, dell2)
    w = b_wait(bs, 0.03)
    chain([(chy, bs[chy]), (if_pad, bs[if_pad]), (if_bot, bs[if_bot]), (w, bs[w])])
    if_pl = b_if(bs, c_play, chy)
    fe = b_forever(bs, if_pl)
    chain([(ch, bs[ch]), (set_isc, bs[set_isc]), (sw, bs[sw]), (gt, bs[gt]),
           (ssz, bs[ssz]), (sh, bs[sh]), (fe, bs[fe])])
    return bs


def build_laser():
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])
    wipe_on_stage_start(bs, vrep, cmp_op, y=420)

    h_f = gen(); bs[h_f] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["레이저발사", BR_FIRE]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_ISC), 0)
    # two beams; wait 0 so each clone copies 임시 오프셋 correctly
    set_t = b_set(bs, "임시", V_TMP, -18)
    cc1 = create_clone(bs)
    w0a = b_wait(bs, 0)
    set_t2 = b_set(bs, "임시", V_TMP, 18)
    cc2 = create_clone(bs)
    w0b = b_wait(bs, 0)
    chain([(set_t, bs[set_t]), (cc1, bs[cc1]), (w0a, bs[w0a]),
           (set_t2, bs[set_t2]), (cc2, bs[cc2]), (w0b, bs[w0b])])
    if_o = b_if(bs, c_orig, set_t)
    chain([(h_f, bs[h_f]), (if_o, bs[if_o])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=300)
    set_isc = b_set(bs, "복제됨", V_ISC, 1)
    # 임시(오프셋) 를 즉시 읽어 자리 잡기
    off = vrep("임시", V_TMP)
    m = gen(); bs[m] = mk("sensing_of_object_menu", fields={"OBJECT": ["패들", None]}, shadow=True)
    pxx = gen(); bs[pxx] = mk("sensing_of", inputs={"OBJECT": [1, m]}, fields={"PROPERTY": ["x position", None]})
    bs[m]["parent"] = pxx
    x = op("operator_add", pxx, off)
    gt = gen(); bs[gt] = mk("motion_gotoxy", inputs={"X": slot(x), "Y": num(PADDLE_Y + 20)})
    bs[x]["parent"] = gt
    sh = gen(); bs[sh] = mk("looks_show")
    # 얇은 빔 + 판정용 최소 여유. 공보다 뒤(레이어)라 공을 가리지 않음(→ go to front 제거)
    ssz = gen(); bs[ssz] = mk("looks_setsizeto", inputs={"SIZE": num(115)})
    # move up; on brick: yield so brick can process damage, then delete
    chy = gen(); bs[chy] = mk("motion_changeyby", inputs={"DY": num(10)})
    c_br = touching(bs, "벽돌")
    # 레이저가 먼저 사라지면 벽돌이 감지를 못 함 → 짧게 머무른 뒤 삭제
    w_hit = b_wait(bs, 0.08)
    dell = gen(); bs[dell] = mk("control_delete_this_clone")
    chain([(w_hit, bs[w_hit]), (dell, bs[dell])])
    if_br = b_if(bs, c_br, w_hit)
    yp = gen(); bs[yp] = mk("motion_yposition")
    c_top = cmp_op("operator_gt", yp, 175)
    dell2 = gen(); bs[dell2] = mk("control_delete_this_clone")
    if_top = b_if(bs, c_top, dell2)
    w = b_wait(bs, 0.02)
    chain([(chy, bs[chy]), (if_br, bs[if_br]), (if_top, bs[if_top]), (w, bs[w])])
    fe = b_forever(bs, chy)
    chain([(ch, bs[ch]), (set_isc, bs[set_isc]), (gt, bs[gt]), (ssz, bs[ssz]),
           (sh, bs[sh]), (fe, bs[fe])])
    return bs


def build_gameover():
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])
    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=120,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    c0 = cmp_op("operator_equals", vrep("게임상태", V_STATE), 0)
    wu = gen(); bs[wu] = mk("control_wait_until", inputs={"CONDITION": [2, c0]})
    bs[c0]["parent"] = wu
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    sh = gen(); bs[sh] = mk("looks_show")
    chain([(h2, bs[h2]), (hi2, bs[hi2]), (wu, bs[wu]), (front, bs[front]), (sh, bs[sh])])
    return bs


def build_effect():
    """전체화면 번쩍 오버레이 — 방송 '번쩍' 받으면 색조 입혀 잠깐 반짝."""
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["번쩍", BR_FLASH]})
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    gt = gen(); bs[gt] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    setcol = set_effect(bs, "COLOR", vrep("번쩍색", V_FLASHCOL))
    setgh = set_effect(bs, "GHOST", 62)
    ssz = gen(); bs[ssz] = mk("looks_setsizeto", inputs={"SIZE": num(100)})
    sh = gen(); bs[sh] = mk("looks_show")
    cg = change_effect(bs, "GHOST", 9)
    cs = change_size(bs, 3)
    chain([(cg, bs[cg]), (cs, bs[cs])])
    rep = b_repeat(bs, 8, cg)
    hi2 = gen(); bs[hi2] = mk("looks_hide")
    chain([(h2, bs[h2]), (front, bs[front]), (gt, bs[gt]), (setcol, bs[setcol]),
           (setgh, bs[setgh]), (ssz, bs[ssz]), (sh, bs[sh]), (rep, bs[rep]), (hi2, bs[hi2])])
    return bs


def build_spark():
    """스파크 폭발 — 방송 '스파크' 받으면 중앙에서 파편이 사방으로 튀며 사라짐."""
    bs = {}
    vrep, op, cmp_op, bool_op, not_op = make_helpers(bs)
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    chain([(h, bs[h]), (hi, bs[hi])])
    wipe_on_stage_start(bs, vrep, cmp_op, y=440)

    h2 = gen(); bs[h2] = mk("event_whenbroadcastreceived", top=True, x=20, y=140,
        fields={"BROADCAST_OPTION": ["스파크", BR_SPARK]})
    c_orig = cmp_op("operator_equals", vrep("복제됨", V_ISC), 0)
    cc = create_clone(bs)
    rep = b_repeat(bs, 12, cc)
    if_o = b_if(bs, c_orig, rep)
    chain([(h2, bs[h2]), (if_o, bs[if_o])])

    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=20, y=320)
    set_isc = b_set(bs, "복제됨", V_ISC, 1)
    front = gen(); bs[front] = mk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
    gt = gen(); bs[gt] = mk("motion_gotoxy", inputs={"X": num(0), "Y": num(0)})
    pd = point_dir(bs, rnd(bs, 0, 359))
    rs_sz = rnd(bs, 45, 95)
    ssz = gen(); bs[ssz] = mk("looks_setsizeto", inputs={"SIZE": slot(rs_sz)}); bs[rs_sz]["parent"] = ssz
    setcol = set_effect(bs, "COLOR", rnd(bs, 0, 199))
    setgh = set_effect(bs, "GHOST", 0)
    sh = gen(); bs[sh] = mk("looks_show")
    mv = move_steps(bs, rnd(bs, 10, 22))
    csz = change_size(bs, -6)
    cgh = change_effect(bs, "GHOST", 11)
    chain([(mv, bs[mv]), (csz, bs[csz]), (cgh, bs[cgh])])
    rep2 = b_repeat(bs, 10, mv)
    dell = gen(); bs[dell] = mk("control_delete_this_clone")
    chain([(ch, bs[ch]), (set_isc, bs[set_isc]), (front, bs[front]), (gt, bs[gt]),
           (pd, bs[pd]), (ssz, bs[ssz]), (setcol, bs[setcol]), (setgh, bs[setgh]),
           (sh, bs[sh]), (rep2, bs[rep2]), (dell, bs[dell])])
    return bs


def costume_png(path, name, cx=None, cy=None, br=2):
    im = Image.open(path); w, h = im.size
    data = open(path, "rb").read(); m = md5_bytes(data)
    open(f"{WORK}/{m}.png", "wb").write(data)
    return {"name": name, "bitmapResolution": br, "dataFormat": "png", "assetId": m,
            "md5ext": f"{m}.png", "rotationCenterX": cx if cx is not None else w//2,
            "rotationCenterY": cy if cy is not None else h//2}


def _wav_bytes(pcm, rate=22050):
    import struct
    data_size = len(pcm)
    hdr = struct.pack("<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE", b"fmt ", 16, 1, 1, rate, rate * 2, 2, 16, b"data", data_size)
    return hdr + pcm


def _synth_tone(freq, dur=0.08, rate=22050, vol=0.45, kind="sine", slide=None):
    """Simple PCM beep. kind: sine|square|noise. slide=(f0,f1) optional."""
    import struct, math as _m, random
    n = max(1, int(rate * dur))
    raw = bytearray()
    for i in range(n):
        t = i / rate
        env = 1.0
        # attack/release
        a, r = 0.005, 0.02
        if t < a:
            env = t / a
        elif t > dur - r:
            env = max(0.0, (dur - t) / r)
        if slide:
            f = slide[0] + (slide[1] - slide[0]) * (i / n)
        else:
            f = freq
        if kind == "noise":
            s = (random.random() * 2 - 1) * env
        elif kind == "square":
            s = (1.0 if _m.sin(2 * _m.pi * f * t) >= 0 else -1.0) * env * 0.55
        else:
            s = _m.sin(2 * _m.pi * f * t) * env
            # soft 2nd harmonic
            s += 0.25 * _m.sin(4 * _m.pi * f * t) * env
        v = int(32767 * vol * s)
        raw += struct.pack("<h", max(-32767, min(32767, v)))
    return bytes(raw)


def _register_sound(name, pcm, rate=22050):
    wb = _wav_bytes(pcm, rate)
    m = md5_bytes(wb)
    open(f"{WORK}/{m}.wav", "wb").write(wb)
    return {
        "name": name, "assetId": m, "dataFormat": "wav", "format": "",
        "rate": rate, "sampleCount": len(pcm) // 2, "md5ext": f"{m}.wav",
    }


def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # SFX bank
    # 전체 볼륨 낮춤 (이전 대비 ~40%)
    snd_bounce = _register_sound("bounce", _synth_tone(520, 0.05, kind="square", vol=0.14))
    snd_hit = _register_sound("hit", _synth_tone(340, 0.04, kind="square", vol=0.12))
    snd_break = _register_sound("break", _synth_tone(880, 0.09, slide=(1200, 280), vol=0.18))
    snd_laser = _register_sound("laser", _synth_tone(1400, 0.07, kind="square", slide=(1800, 600), vol=0.15))
    snd_power = _register_sound("power", _synth_tone(660, 0.12, slide=(440, 990), vol=0.16))
    snd_lose = _register_sound("lose", _synth_tone(200, 0.25, slide=(320, 80), vol=0.18))
    snd_clear = _register_sound("clear", _synth_tone(523, 0.28, slide=(523, 1046), vol=0.18))

    # BGM mp3 (사용자 제공, 재인코딩 없이 그대로 패킹)
    BGM_SRC = os.path.join(ASSETS, "bgm.mp3")
    with open(BGM_SRC, "rb") as f:
        bgm_bytes = f.read()
    bgm_md5 = md5_bytes(bgm_bytes)
    with open(f"{WORK}/{bgm_md5}.mp3", "wb") as f:
        f.write(bgm_bytes)
    BGM_RATE = 48000
    BGM_SAMPLES = int(240 * BGM_RATE)  # ~240s
    def S_bgm():
        return {
            "name": "bgm", "assetId": bgm_md5, "dataFormat": "mp3", "format": "",
            "rate": BGM_RATE, "sampleCount": BGM_SAMPLES, "md5ext": f"{bgm_md5}.mp3",
        }

    bg = costume_png(f"{GEN}/bg.png", "배경", 240, 180, 1)
    pad = costume_png(f"{GEN}/paddle.png", "normal", br=1)
    padw = costume_png(f"{GEN}/paddle_wide.png", "wide", br=1)
    padl = costume_png(f"{GEN}/paddle_laser.png", "laser", br=1)
    # yellow bonus ball (existing) + orange main ball
    bonus_path = f"{GEN}/ball.png"
    main_path = os.path.join(GEN, "ball_main.png")
    im_b = Image.open(bonus_path).convert("RGBA")
    im_m = im_b.copy()
    px = im_m.load()
    for x in range(im_m.size[0]):
        for y in range(im_m.size[1]):
            r, g, b, a = px[x, y]
            if a < 16:
                continue
            # map yellow → orange
            px[x, y] = (min(255, int(r * 1.0)), min(255, int(g * 0.55)), min(255, int(b * 0.15)), a)
    im_m.save(main_path)
    ball_main = costume_png(main_path, "main", br=1)
    ball_bonus = costume_png(bonus_path, "bonus", br=1)
    bricks = [costume_png(f"{GEN}/brick{i}.png", f"c{i}", br=1) for i in range(1, 7)]
    bricks += [costume_png(f"{GEN}/brick_hard.png", "hard", br=1),
               costume_png(f"{GEN}/brick_hard2.png", "hard2", br=1),
               costume_png(f"{GEN}/brick_bomb.png", "bomb", br=1)]
    # 보스 왕벽돌 3페이즈 (금→금가→파괴직전)
    def _make_boss(path, phase):
        # base brick size ~ similar aspect; large via looks size
        w, h = 84, 40
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        from PIL import ImageDraw
        d = ImageDraw.Draw(im)
        if phase == 1:
            fill, edge = (180, 40, 220, 255), (255, 215, 80, 255)
        elif phase == 2:
            fill, edge = (140, 30, 180, 255), (255, 180, 60, 255)
        else:
            fill, edge = (90, 20, 110, 255), (255, 100, 80, 255)
        d.rounded_rectangle([2, 2, w - 3, h - 3], radius=6, fill=fill, outline=edge, width=3)
        # crown gem
        d.ellipse([w // 2 - 8, 8, w // 2 + 8, 22], fill=(255, 230, 90, 255), outline=(255, 255, 200, 255))
        if phase >= 2:
            d.line([(12, 10), (28, 28)], fill=(40, 0, 50, 220), width=2)
            d.line([(w - 14, 12), (w - 30, 30)], fill=(40, 0, 50, 220), width=2)
        if phase >= 3:
            d.line([(20, 8), (40, 32)], fill=(20, 0, 30, 230), width=3)
            d.line([(50, 6), (70, 34)], fill=(20, 0, 30, 230), width=3)
            d.ellipse([8, 24, 16, 32], fill=(255, 80, 60, 200))
        im.save(path)
    for ph in (1, 2, 3):
        bp = os.path.join(GEN, f"boss{ph}.png")
        _make_boss(bp, ph)
        bricks.append(costume_png(bp, f"boss{ph}", br=1))
    pus = [costume_png(f"{GEN}/pu_{c}.png", c, br=1) for c in "MWLCPS"]
    # 얇은 레이저 빔 (10px). 공보다 뒤 레이어라 공을 가리지 않음.
    laser_path = os.path.join(GEN, "laser_thin.png")
    LW = 10
    im_l = Image.new("RGBA", (LW, 36), (0, 0, 0, 0))
    for x in range(LW):
        for y in range(36):
            edge = min(x, LW - 1 - x)
            a = 255 if edge >= 2 else (180 if edge == 1 else 90)
            # cyan core
            im_l.putpixel((x, y), (80, 255, 255, a) if 4 <= y <= 32 else (180, 255, 255, a // 2 if a else 0))
    im_l.save(laser_path)
    laser = costume_png(laser_path, "laser", br=1)
    go = costume_png(f"{GEN}/gameover.png", "go", 200, 80, 1)

    # 번쩍 오버레이 (채도 있어야 색상효과로 색이 바뀜)
    flash_path = os.path.join(WORK, "flash.png")
    Image.new("RGBA", (480, 360), (255, 70, 70, 255)).save(flash_path)
    flash_cos = costume_png(flash_path, "flash", 240, 180, 1)
    # 스파크 파편
    spark_path = os.path.join(WORK, "spark.png")
    im_s = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for x in range(20):
        for y in range(20):
            if (x - 10) ** 2 + (y - 10) ** 2 <= 81:
                im_s.putpixel((x, y), (255, 205, 70, 255))
    im_s.save(spark_path)
    spark_cos = costume_png(spark_path, "spark", 10, 10, 1)

    # fix gen counter per build
    global _ic
    _ic = [0]

    stage_b = build_stage()
    pad_b = build_paddle()
    ball_b = build_ball()
    brick_b = build_brick()
    pu_b = build_powerup()
    las_b = build_laser()
    go_b = build_gameover()
    eff_b = build_effect()
    spk_b = build_spark()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_STATE: ["게임상태", 1], V_SCORE: ["점수", 0], V_BEST: ["최고기록", 0],
            V_LIVES: ["목숨", 3], V_STAGE: ["스테이지", 1], V_BRICKS: ["남은벽돌", 0],
            V_MODE: ["패들모드", 0], V_PIERCE: ["관통", 0], V_SLOW: ["감속", 0],
            V_BALLS: ["공개수", 0], V_LAUNCH: ["발사됨", 0], V_SPD: ["공속도", BALL_SPEED],
            V_PCHANCE: ["아이템확률", 30], V_MAXBALLS: ["멀티볼최대", 12], V_PBASE: ["패들기본", 100],
            V_TMP: ["임시", 0], V_I: ["검사i", 0], V_R: ["행", 0], V_C: ["열", 0],
            V_BX: ["스폰X", 0], V_BY: ["스폰Y", 0], V_BHP: ["스폰체력", 1], V_BTYPE: ["스폰종류", 1],
            V_PU: ["파워종류", 1], V_BOUNCE: ["바운스", 0],
            V_SPAWNMAIN: ["스폰메인", 1],
            V_MAINLIVE: ["메인존재", 0],
            V_READY: ["준비됨", 0],
            V_BOSSHP: ["보스체력", 0],
            V_CLOCK: ["광란시계", 0], V_FRENZY: ["광란레벨", 1], V_LASERTIME: ["레이저타임", 0],
            V_FLASHCOL: ["번쩍색", 0], V_WAVEGAP: ["웨이브간격", 4], V_LASGAP: ["레이저간격", 7],
            V_SPDGAP: ["공속상승간격", 6], V_WAVEN: ["웨이브개수", 3], V_LASSHOTS: ["레이저연사", 16],
            V_SPDMAX: ["공속상한", 28],
            V_BGMVOL: ["브금볼륨", 55],
        },

        "lists": {},
        "broadcasts": {
            BR_START: "게임시작", BR_STAGE: "스테이지시작", BR_LOST: "공놓침",
            BR_CLEAR: "스테이지클리어", BR_SERVE: "서브", BR_FIRE: "레이저발사",
            BR_MAIN: "메인공서브", BR_BONUS: "보너스서브", BR_READY: "준비완료",
            BR_BRICKHIT: "벽돌타격", BR_FLASH: "번쩍", BR_SPARK: "스파크",
        },
        "blocks": stage_b, "comments": {}, "currentCostume": 0, "costumes": [bg],
        "sounds": [snd_lose, snd_clear, S_bgm()], "volume": 55, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None,
    }
    paddle = {
        "isStage": False, "name": "패들", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": pad_b, "comments": {}, "currentCostume": 0,
        "costumes": [pad, padw, padl], "sounds": [snd_laser],
        "volume": 55, "layerOrder": 5, "visible": True,
        "x": 0, "y": PADDLE_Y, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }
    ball_s = {
        "isStage": False, "name": "공", "variables": {
            V_ISC: ["복제됨", 0], V_VX: ["속도X", 0], V_VY: ["속도Y", 0], V_STUCK: ["붙음", 1],
            V_ISMAIN: ["메인공", 1], V_HITCD: ["타격쿨", 0],
        }, "lists": {}, "broadcasts": {},
        "blocks": ball_b, "comments": {}, "currentCostume": 0,
        "costumes": [ball_main, ball_bonus],
        "sounds": [snd_bounce, snd_hit], "volume": 55, "layerOrder": 7, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }
    # ensure ball local 이전Y exists
    ball_s["variables"][V_PREY] = ["이전Y", 0]
    brick_s = {
        "isStage": False, "name": "벽돌", "variables": {
            V_ISC: ["복제됨", 0], V_HP: ["체력", 1], V_KIND: ["종류", 1],
        }, "lists": {}, "broadcasts": {},
        "blocks": brick_b, "comments": {}, "currentCostume": 0, "costumes": bricks,
        "sounds": [snd_break, snd_hit], "volume": 55, "layerOrder": 3, "visible": False,
        "x": 0, "y": 0, "size": 90, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }
    pu_s = {
        "isStage": False, "name": "파워업", "variables": {V_ISC: ["복제됨", 0]},
        "lists": {}, "broadcasts": {}, "blocks": pu_b, "comments": {},
        "currentCostume": 0, "costumes": pus, "sounds": [snd_power],
        "volume": 55, "layerOrder": 4, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }
    las_s = {
        "isStage": False, "name": "레이저", "variables": {V_ISC: ["복제됨", 0]},
        "lists": {}, "broadcasts": {}, "blocks": las_b, "comments": {},
        "currentCostume": 0, "costumes": [laser], "sounds": [],
        "volume": 100, "layerOrder": 6, "visible": False,
        "x": 0, "y": 0, "size": 160, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }
    go_s = {
        "isStage": False, "name": "게임오버", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": go_b, "comments": {}, "currentCostume": 0, "costumes": [go],
        "sounds": [snd_lose], "volume": 55, "layerOrder": 10, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }
    eff_s = {
        "isStage": False, "name": "이펙트", "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": eff_b, "comments": {}, "currentCostume": 0, "costumes": [flash_cos],
        "sounds": [], "volume": 100, "layerOrder": 8, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }
    spk_s = {
        "isStage": False, "name": "스파크", "variables": {V_ISC: ["복제됨", 0]},
        "lists": {}, "broadcasts": {}, "blocks": spk_b, "comments": {},
        "currentCostume": 0, "costumes": [spark_cos], "sounds": [],
        "volume": 100, "layerOrder": 9, "visible": False,
        "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate",
    }
    monitors = [
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None, "value": 0,
         "width": 0, "height": 0, "x": 5, "y": 5, "visible": True,
         "sliderMin": 0, "sliderMax": 99999, "isDiscrete": True},
        {"id": V_LIVES, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "목숨"}, "spriteName": None, "value": 3,
         "width": 0, "height": 0, "x": 5, "y": 35, "visible": True,
         "sliderMin": 0, "sliderMax": 99, "isDiscrete": True},
        {"id": V_STAGE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "스테이지"}, "spriteName": None, "value": 1,
         "width": 0, "height": 0, "x": 5, "y": 65, "visible": True,
         "sliderMin": 0, "sliderMax": 99, "isDiscrete": True},
        {"id": V_BOSSHP, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "보스체력"}, "spriteName": None, "value": 0,
         "width": 0, "height": 0, "x": 360, "y": 5, "visible": True,
         "sliderMin": 0, "sliderMax": 99, "isDiscrete": True},
    ]
    project = {
        "targets": [stage, paddle, ball_s, brick_s, pu_s, las_s, go_s, eff_s, spk_s],
        "monitors": monitors, "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg", "agent": "brick-breaker-builder"},
    }
    pj = f"{WORK}/project.json"
    json.dump(project, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)
    json.load(open(pj, encoding="utf-8"))
    assert zipfile.ZipFile(OUTPUT).testzip() is None
    total = sum(len(t["blocks"]) for t in project["targets"])
    print(f"wrote {OUTPUT}")
    print(f"  blocks={total} targets={len(project['targets'])} stages={len(STAGES)}")
    for t in project["targets"]:
        print(f"  {t['name']}: {len(t['blocks'])}")


if __name__ == "__main__":
    main()
