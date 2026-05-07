#!/usr/bin/env python3
"""Generate a Scratch 3.0 .sb3 polynomial-curve shooter game."""
import json, os, zipfile, shutil, hashlib

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
WORK   = os.path.join(HERE, ".build")
OUTPUT = os.path.join(HERE, "다항함수_게임.sb3")

# ---------- background SVG (custom drawn sky/landscape) ----------
BG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#56CCF2"/>
      <stop offset="60%" stop-color="#A0E4FA"/>
      <stop offset="100%" stop-color="#C9F0FF"/>
    </linearGradient>
    <linearGradient id="grass" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#82C341"/>
      <stop offset="100%" stop-color="#3F8814"/>
    </linearGradient>
    <radialGradient id="sun" cx="0.35" cy="0.35" r="0.7">
      <stop offset="0%" stop-color="#FFFCBE"/>
      <stop offset="80%" stop-color="#FFC107"/>
      <stop offset="100%" stop-color="#FFA000"/>
    </radialGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <circle cx="400" cy="60" r="55" fill="#FFEB3B" opacity="0.15"/>
  <circle cx="400" cy="60" r="42" fill="#FFEB3B" opacity="0.25"/>
  <circle cx="400" cy="60" r="32" fill="url(#sun)"/>
  <polygon points="-10,250 70,170 140,210 220,160 300,200 380,170 460,220 490,200 490,310 -10,310"
    fill="#9FA8DA" opacity="0.55"/>
  <polygon points="-10,290 60,235 130,275 200,225 270,265 340,235 410,270 490,250 490,310 -10,310"
    fill="#7986CB" opacity="0.75"/>
  <g fill="#FFFFFF" opacity="0.9">
    <ellipse cx="80" cy="60" rx="35" ry="11"/>
    <ellipse cx="100" cy="55" rx="25" ry="9"/>
    <ellipse cx="60" cy="58" rx="22" ry="9"/>
  </g>
  <g fill="#FFFFFF" opacity="0.85">
    <ellipse cx="240" cy="100" rx="40" ry="12"/>
    <ellipse cx="220" cy="95" rx="28" ry="10"/>
    <ellipse cx="265" cy="95" rx="22" ry="9"/>
  </g>
  <g fill="#FFFFFF" opacity="0.8">
    <ellipse cx="160" cy="160" rx="30" ry="9"/>
    <ellipse cx="148" cy="156" rx="20" ry="7"/>
  </g>
  <rect y="295" width="480" height="65" fill="url(#grass)"/>
  <g stroke="#558B2F" stroke-width="1.5" fill="none" opacity="0.7">
    <path d="M 30 320 Q 35 305 40 320"/>
    <path d="M 80 325 Q 85 310 90 325"/>
    <path d="M 140 318 Q 145 303 150 318"/>
    <path d="M 200 327 Q 205 312 210 327"/>
    <path d="M 270 322 Q 275 307 280 322"/>
    <path d="M 340 328 Q 345 313 350 328"/>
    <path d="M 410 320 Q 415 305 420 320"/>
    <path d="M 460 325 Q 465 310 470 325"/>
  </g>
</svg>"""

# ---------- helpers ----------
def md5_bytes(b): return hashlib.md5(b).hexdigest()
def md5_file(path):
    with open(path, "rb") as f: return md5_bytes(f.read())

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

# Variable & broadcast IDs
V_A      = "varA001"
V_B      = "varB002"
V_SCORE  = "varScore003"
V_XSTEP  = "varXStep004"
V_BCOUNT = "varBCount005"
V_ROUND  = "varRound006"
V_PREV_X = "varPrevX007"   # local to curve preview sprite
V_EQ     = "varEq008"      # equation string
BR_NEW   = "brNew001"
BR_START = "brStart002"

# Tiny transparent costume for the (hidden) preview sprite
TINY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8"><rect width="8" height="8" fill="none"/></svg>"""

# ---------- CAT/ROCKET sprite blocks ----------
def build_rocket_blocks():
    bs = {}

    # var-reporter helper (creates a fresh data_variable block, returns id)
    def vrep(name, vid):
        bid = gen()
        bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid

    # binary operator helper (operands are either numeric literal or block id)
    def op(opcode, a, b_):
        bid = gen()
        ins = {}
        for key, val in [("NUM1", a), ("NUM2", b_)]:
            if isinstance(val, str):
                ins[key] = slot(val)
            else:
                ins[key] = num(val)
        bs[bid] = mk(opcode, inputs=ins)
        for val in (a, b_):
            if isinstance(val, str): bs[val]["parent"] = bid
        return bid

    # === init ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    sa = gen(); bs[sa] = mk("data_setvariableto",
        inputs={"VALUE": num(-0.005)}, fields={"VARIABLE": ["a", V_A]})
    sb = gen(); bs[sb] = mk("data_setvariableto",
        inputs={"VALUE": num(1.0)},   fields={"VARIABLE": ["b", V_B]})
    ss = gen(); bs[ss] = mk("data_setvariableto",
        inputs={"VALUE": num(0)},     fields={"VARIABLE": ["점수", V_SCORE]})
    sr = gen(); bs[sr] = mk("data_setvariableto",
        inputs={"VALUE": num(1)},     fields={"VARIABLE": ["라운드", V_ROUND]})
    siz = gen(); bs[siz] = mk("looks_setsizeto", inputs={"SIZE": num(120)})
    g = gen(); bs[g] = mk("motion_gotoxy", inputs={"X": num(-200), "Y": num(-120)})
    pdir = gen(); bs[pdir] = mk("motion_pointindirection", inputs={"DIRECTION": num(135)})
    hi = gen(); bs[hi] = mk("looks_hide")

    # broadcast 게임시작
    sm = gen(); bs[sm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]}, shadow=True)
    sb_b = gen(); bs[sb_b] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT": [1, sm]})
    bs[sm]["parent"] = sb_b

    chain([(h,bs[h]),(sa,bs[sa]),(sb,bs[sb]),(ss,bs[ss]),(sr,bs[sr]),
           (siz,bs[siz]),(g,bs[g]),(pdir,bs[pdir]),(hi,bs[hi]),(sb_b,bs[sb_b])])

    # === arrow keys ===
    def key_change(key, var_name, vid, delta, ypos):
        kh = gen(); bs[kh] = mk("event_whenkeypressed", top=True, x=20, y=ypos,
            fields={"KEY_OPTION": [key, None]})
        kc = gen(); bs[kc] = mk("data_changevariableby",
            inputs={"VALUE": num(delta)}, fields={"VARIABLE": [var_name, vid]})
        chain([(kh,bs[kh]),(kc,bs[kc])])

    key_change("up arrow",    "a", V_A,  0.002, 200)
    key_change("down arrow",  "a", V_A, -0.002, 320)
    key_change("right arrow", "b", V_B,  0.10,  440)
    key_change("left arrow",  "b", V_B, -0.10,  560)

    # === space: launch ===
    sp = gen(); bs[sp] = mk("event_whenkeypressed", top=True, x=400, y=20,
        fields={"KEY_OPTION": ["space", None]})
    so = gen(); bs[so] = mk("control_stop",
        fields={"STOP_OPTION": ["other scripts in sprite", None]})
    bs[so]["mutation"] = {"tagName":"mutation","children":[],"hasnext":"true"}
    sg  = gen(); bs[sg]  = mk("motion_gotoxy", inputs={"X": num(-200), "Y": num(-120)})
    sxs = gen(); bs[sxs] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["x걸음", V_XSTEP]})
    sho = gen(); bs[sho] = mk("looks_show")

    # play pop sound (start, no wait)
    snm0 = gen(); bs[snm0] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd0 = gen(); bs[snd0] = mk("sound_play", inputs={"SOUND_MENU":[1, snm0]})
    bs[snm0]["parent"] = snd0

    # ----- repeat loop body -----
    cx = gen(); bs[cx] = mk("data_changevariableby",
        inputs={"VALUE": num(7)}, fields={"VARIABLE": ["x걸음", V_XSTEP]})

    # x_pos = -200 + x걸음
    addx = op("operator_add", -200, vrep("x걸음", V_XSTEP))
    # y_pos = -120 + a*x*x + b*x
    rA  = vrep("a", V_A)
    rX1 = vrep("x걸음", V_XSTEP)
    rX2 = vrep("x걸음", V_XSTEP)
    aXX = op("operator_multiply", op("operator_multiply", rA, rX1), rX2)
    rB  = vrep("b", V_B)
    rX3 = vrep("x걸음", V_XSTEP)
    bX  = op("operator_multiply", rB, rX3)
    poly = op("operator_add", aXX, bX)
    addy = op("operator_add", -120, poly)

    gi = gen(); bs[gi] = mk("motion_gotoxy",
        inputs={"X": slot(addx), "Y": slot(addy)})
    bs[addx]["parent"]=gi; bs[addy]["parent"]=gi

    # rotate: direction = 90 - atan(2*a*x + b)
    rA2  = vrep("a", V_A)
    rX4  = vrep("x걸음", V_XSTEP)
    twoA = op("operator_multiply", 2, rA2)
    twoAx = op("operator_multiply", twoA, rX4)
    rB2  = vrep("b", V_B)
    slope = op("operator_add", twoAx, rB2)
    atan_id = gen()
    bs[atan_id] = mk("operator_mathop",
        inputs={"NUM": slot(slope)},
        fields={"OPERATOR": ["atan", None]})
    bs[slope]["parent"] = atan_id
    # rocket SVG natively points up-right (~45°), so offset by +45° to align
    dir_id = op("operator_subtract", 135, atan_id)
    pid = gen(); bs[pid] = mk("motion_pointindirection",
        inputs={"DIRECTION": slot(dir_id)})
    bs[dir_id]["parent"] = pid

    # if y position < -160 then hide + stop
    yp = gen(); bs[yp] = mk("motion_yposition")
    cond = gen(); bs[cond] = mk("operator_lt",
        inputs={"OPERAND1": slot(yp), "OPERAND2": num(-160)})
    bs[yp]["parent"] = cond

    hide_in = gen(); bs[hide_in] = mk("looks_hide")
    stop_in = gen(); bs[stop_in] = mk("control_stop",
        fields={"STOP_OPTION": ["this script", None]})
    bs[stop_in]["mutation"] = {"tagName":"mutation","children":[],"hasnext":"false"}
    chain([(hide_in,bs[hide_in]),(stop_in,bs[stop_in])])

    ifb = gen(); bs[ifb] = mk("control_if",
        inputs={"CONDITION":[2,cond], "SUBSTACK":[2,hide_in]})
    bs[cond]["parent"] = ifb
    bs[hide_in]["parent"] = ifb

    wt = gen(); bs[wt] = mk("control_wait", inputs={"DURATION": num(0.025)})

    # body order: change_x → goto → point_dir → if_off_screen → wait
    chain([(cx,bs[cx]),(gi,bs[gi]),(pid,bs[pid]),(ifb,bs[ifb]),(wt,bs[wt])])

    # repeat 70
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(70), "SUBSTACK":[2,cx]})
    bs[cx]["parent"] = rep

    # after repeat: hide
    end_hide = gen(); bs[end_hide] = mk("looks_hide")

    chain([(sp,bs[sp]),(so,bs[so]),(sg,bs[sg]),(pdir_init := pdir,bs[pdir]) if False else (sg,bs[sg]),
           (sxs,bs[sxs]),(sho,bs[sho]),(snd0,bs[snd0]),(rep,bs[rep]),(end_hide,bs[end_hide])])
    # ^ messy, let me re-chain properly:
    # Reset chain for space sequence
    bs[sp]["next"] = so;  bs[so]["parent"] = sp
    bs[so]["next"] = sg;  bs[sg]["parent"] = so
    bs[sg]["next"] = sxs; bs[sxs]["parent"]= sg
    bs[sxs]["next"]= sho; bs[sho]["parent"]= sxs
    bs[sho]["next"]= snd0;bs[snd0]["parent"]=sho
    bs[snd0]["next"]= rep;bs[rep]["parent"]= snd0
    bs[rep]["next"]= end_hide; bs[end_hide]["parent"]= rep
    bs[end_hide]["next"]= None
    return bs

# ---------- BALLOON sprite blocks ----------
def build_balloon_blocks():
    bs = {}
    def vrep(name, vid):
        bid = gen()
        bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid

    # === when flag clicked: hide & init counters ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hi = gen(); bs[hi] = mk("looks_hide")
    sc = gen(); bs[sc] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["풍선수", V_BCOUNT]})
    chain([(h,bs[h]),(hi,bs[hi]),(sc,bs[sc])])

    # === when received 새라운드: spawn 5 clones ===
    bh = gen(); bs[bh] = mk("event_whenbroadcastreceived", top=True, x=20, y=200,
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW]})
    w1 = gen(); bs[w1] = mk("control_wait", inputs={"DURATION": num(0.4)})

    # repeat 5 → create clone of self
    cmenu = gen(); bs[cmenu] = mk("control_create_clone_of_menu",
        fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
    cclone = gen(); bs[cclone] = mk("control_create_clone_of",
        inputs={"CLONE_OPTION":[1,cmenu]})
    bs[cmenu]["parent"] = cclone
    wclone = gen(); bs[wclone] = mk("control_wait", inputs={"DURATION": num(0.08)})
    chain([(cclone,bs[cclone]),(wclone,bs[wclone])])
    rep5 = gen(); bs[rep5] = mk("control_repeat",
        inputs={"TIMES": num(5), "SUBSTACK":[2, cclone]})
    bs[cclone]["parent"] = rep5
    chain([(bh,bs[bh]),(w1,bs[w1]),(rep5,bs[rep5])])

    # === when received 게임시작 → broadcast 새라운드 (kicks off first round) ===
    sh = gen(); bs[sh] = mk("event_whenbroadcastreceived", top=True, x=20, y=400,
        fields={"BROADCAST_OPTION": ["게임시작", BR_START]})
    nbm = gen(); bs[nbm] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW]}, shadow=True)
    nbb = gen(); bs[nbb] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1,nbm]})
    bs[nbm]["parent"] = nbb
    chain([(sh,bs[sh]),(nbb,bs[nbb])])

    # === when I start as a clone ===
    ch = gen(); bs[ch] = mk("control_start_as_clone", top=True, x=400, y=20)

    # 풍선수 += 1
    inc = gen(); bs[inc] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["풍선수", V_BCOUNT]})
    # random pos: x 30..220, y -20..120 (above ground)
    rx = gen(); bs[rx] = mk("operator_random",
        inputs={"FROM": num(-30), "TO": num(220)})
    ry = gen(); bs[ry] = mk("operator_random",
        inputs={"FROM": num(-30), "TO": num(140)})
    g = gen(); bs[g] = mk("motion_gotoxy",
        inputs={"X": slot(rx), "Y": slot(ry)})
    bs[rx]["parent"]=g; bs[ry]["parent"]=g
    # random color tint 0..200
    rc = gen(); bs[rc] = mk("operator_random",
        inputs={"FROM": num(0), "TO": num(200)})
    ce = gen(); bs[ce] = mk("looks_seteffectto",
        inputs={"VALUE": slot(rc)}, fields={"EFFECT": ["color", None]})
    bs[rc]["parent"] = ce
    # size 70..110
    rs = gen(); bs[rs] = mk("operator_random",
        inputs={"FROM": num(80), "TO": num(110)})
    sz = gen(); bs[sz] = mk("looks_setsizeto", inputs={"SIZE": slot(rs)})
    bs[rs]["parent"] = sz
    show = gen(); bs[show] = mk("looks_show")

    # forever: if touching 로켓
    tm = gen(); bs[tm] = mk("sensing_touchingobjectmenu",
        fields={"TOUCHINGOBJECTMENU": ["로켓", None]}, shadow=True)
    tc = gen(); bs[tc] = mk("sensing_touchingobject",
        inputs={"TOUCHINGOBJECTMENU":[1,tm]})
    bs[tm]["parent"] = tc

    incs = gen(); bs[incs] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["점수", V_SCORE]})
    snm = gen(); bs[snm] = mk("sound_sounds_menu",
        fields={"SOUND_MENU": ["pop", None]}, shadow=True)
    snd = gen(); bs[snd] = mk("sound_play", inputs={"SOUND_MENU":[1,snm]})
    bs[snm]["parent"] = snd
    decb = gen(); bs[decb] = mk("data_changevariableby",
        inputs={"VALUE": num(-1)}, fields={"VARIABLE": ["풍선수", V_BCOUNT]})

    # if 풍선수 = 0 then increment 라운드 + broadcast 새라운드
    rb = vrep("풍선수", V_BCOUNT)
    eq = gen(); bs[eq] = mk("operator_equals",
        inputs={"OPERAND1": slot(rb), "OPERAND2": num(0)})
    bs[rb]["parent"] = eq
    incr = gen(); bs[incr] = mk("data_changevariableby",
        inputs={"VALUE": num(1)}, fields={"VARIABLE": ["라운드", V_ROUND]})
    nbm2 = gen(); bs[nbm2] = mk("event_broadcast_menu",
        fields={"BROADCAST_OPTION": ["새라운드", BR_NEW]}, shadow=True)
    nbb2 = gen(); bs[nbb2] = mk("event_broadcast",
        inputs={"BROADCAST_INPUT":[1,nbm2]})
    bs[nbm2]["parent"] = nbb2
    chain([(incr,bs[incr]),(nbb2,bs[nbb2])])

    if_round = gen(); bs[if_round] = mk("control_if",
        inputs={"CONDITION":[2,eq], "SUBSTACK":[2,incr]})
    bs[eq]["parent"] = if_round
    bs[incr]["parent"] = if_round

    # pop visual: shrink quickly
    sz0 = gen(); bs[sz0] = mk("looks_changesizeby", inputs={"CHANGE": num(-30)})
    sz1 = gen(); bs[sz1] = mk("looks_changesizeby", inputs={"CHANGE": num(-30)})

    delc = gen(); bs[delc] = mk("control_delete_this_clone")

    # chain inside if-touching: incs → snd → sz0 → sz1 → decb → if_round → delc
    chain([(incs,bs[incs]),(snd,bs[snd]),(sz0,bs[sz0]),(sz1,bs[sz1]),
           (decb,bs[decb]),(if_round,bs[if_round]),(delc,bs[delc])])

    if_touch = gen(); bs[if_touch] = mk("control_if",
        inputs={"CONDITION":[2,tc], "SUBSTACK":[2,incs]})
    bs[tc]["parent"] = if_touch
    bs[incs]["parent"] = if_touch

    # gentle floating: change y by sin(timer*?) — too complex, do small bob
    # Skip for simplicity; just have the if-touching as forever body
    fwait = gen(); bs[fwait] = mk("control_wait", inputs={"DURATION": num(0.02)})
    chain([(if_touch,bs[if_touch]),(fwait,bs[fwait])])

    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2,if_touch]})
    bs[if_touch]["parent"] = fv

    # clone start chain: ch → inc → g → ce → sz → show → fv
    chain([(ch,bs[ch]),(inc,bs[inc]),(g,bs[g]),(ce,bs[ce]),(sz,bs[sz]),
           (show,bs[show]),(fv,bs[fv])])

    return bs

# ---------- CURVE PREVIEW sprite blocks (uses pen extension) ----------
def build_curve_blocks():
    bs = {}
    def vrep(name, vid):
        bid = gen()
        bs[bid] = mk("data_variable", fields={"VARIABLE": [name, vid]})
        return bid
    def op(opcode, a, b_):
        bid = gen()
        ins = {}
        for key, val in [("NUM1", a), ("NUM2", b_)]:
            if isinstance(val, str): ins[key] = slot(val)
            else: ins[key] = num(val)
        bs[bid] = mk(opcode, inputs=ins)
        for v in (a, b_):
            if isinstance(v, str): bs[v]["parent"] = bid
        return bid

    # === when flag clicked → hide → forever-redraw ===
    h = gen(); bs[h] = mk("event_whenflagclicked", top=True, x=20, y=20)
    hide_blk = gen(); bs[hide_blk] = mk("looks_hide")

    pu0 = gen(); bs[pu0] = mk("pen_penUp")
    clr = gen(); bs[clr] = mk("pen_clear")
    sc  = gen(); bs[sc]  = mk("pen_setPenColorToColor",
        inputs={"COLOR": [1, [9, "#E91E63"]]})  # vivid pink for visibility
    sz  = gen(); bs[sz]  = mk("pen_setPenSizeTo", inputs={"SIZE": num(3)})
    spx = gen(); bs[spx] = mk("data_setvariableto",
        inputs={"VALUE": num(0)}, fields={"VARIABLE": ["예측x", V_PREV_X]})
    g0  = gen(); bs[g0]  = mk("motion_gotoxy", inputs={"X": num(-200), "Y": num(-120)})
    pd  = gen(); bs[pd]  = mk("pen_penDown")

    # repeat 60 step 8 → 480 px range
    cx = gen(); bs[cx] = mk("data_changevariableby",
        inputs={"VALUE": num(8)}, fields={"VARIABLE": ["예측x", V_PREV_X]})
    addx = op("operator_add", -200, vrep("예측x", V_PREV_X))
    rA  = vrep("a", V_A); rX1 = vrep("예측x", V_PREV_X); rX2 = vrep("예측x", V_PREV_X)
    aXX = op("operator_multiply", op("operator_multiply", rA, rX1), rX2)
    rB  = vrep("b", V_B); rX3 = vrep("예측x", V_PREV_X)
    bX  = op("operator_multiply", rB, rX3)
    poly = op("operator_add", aXX, bX)
    addy = op("operator_add", -120, poly)
    g_iter = gen(); bs[g_iter] = mk("motion_gotoxy",
        inputs={"X": slot(addx), "Y": slot(addy)})
    bs[addx]["parent"] = g_iter; bs[addy]["parent"] = g_iter
    chain([(cx, bs[cx]), (g_iter, bs[g_iter])])
    rep = gen(); bs[rep] = mk("control_repeat",
        inputs={"TIMES": num(60), "SUBSTACK": [2, cx]})
    bs[cx]["parent"] = rep

    pu1 = gen(); bs[pu1] = mk("pen_penUp")
    wt  = gen(); bs[wt]  = mk("control_wait", inputs={"DURATION": num(0.05)})

    chain([(pu0,bs[pu0]),(clr,bs[clr]),(sc,bs[sc]),(sz,bs[sz]),(spx,bs[spx]),
           (g0,bs[g0]),(pd,bs[pd]),(rep,bs[rep]),(pu1,bs[pu1]),(wt,bs[wt])])

    fv = gen(); bs[fv] = mk("control_forever", inputs={"SUBSTACK":[2, pu0]})
    bs[pu0]["parent"] = fv

    chain([(h, bs[h]), (hide_blk, bs[hide_blk]), (fv, bs[fv])])

    # === 2nd flag-clicked script: equation builder forever loop ===
    # rounded(name, vid, decimals) → block id producing floor(x*f+0.5)/f
    def rounded(name, vid, decimals):
        f = 10 ** decimals
        rv = vrep(name, vid)
        m1 = op("operator_multiply", rv, f)
        a1 = op("operator_add", m1, 0.5)
        fl = gen(); bs[fl] = mk("operator_mathop",
            inputs={"NUM": slot(a1)}, fields={"OPERATOR": ["floor", None]})
        bs[a1]["parent"] = fl
        d1 = op("operator_divide", fl, f)
        return d1

    h2 = gen(); bs[h2] = mk("event_whenflagclicked", top=True, x=400, y=20)

    # branch: b >= 0  →  "y = {ar}·x² + {br}·x"
    #         b <  0  →  "y = {ar}·x² − {|br|}·x"
    ar = rounded("a", V_A, 3)
    br_pos = rounded("b", V_B, 1)

    # POS branch joins
    j1p = gen(); bs[j1p] = mk("operator_join",
        inputs={"STRING1": text_lit("y = "), "STRING2": slot(ar, sk=10, sv="")})
    bs[ar]["parent"] = j1p
    j2p = gen(); bs[j2p] = mk("operator_join",
        inputs={"STRING1": slot(j1p, sk=10, sv=""), "STRING2": text_lit("·x² + ")})
    bs[j1p]["parent"] = j2p
    j3p = gen(); bs[j3p] = mk("operator_join",
        inputs={"STRING1": slot(j2p, sk=10, sv=""), "STRING2": slot(br_pos, sk=10, sv="")})
    bs[j2p]["parent"] = j3p
    bs[br_pos]["parent"] = j3p
    j4p = gen(); bs[j4p] = mk("operator_join",
        inputs={"STRING1": slot(j3p, sk=10, sv=""), "STRING2": text_lit("·x")})
    bs[j3p]["parent"] = j4p
    set_pos = gen(); bs[set_pos] = mk("data_setvariableto",
        inputs={"VALUE": slot(j4p, sk=10, sv="")},
        fields={"VARIABLE": ["수식", V_EQ]})
    bs[j4p]["parent"] = set_pos

    # NEG branch: |b|
    ar2 = rounded("a", V_A, 3)
    rB_neg = vrep("b", V_B)
    abs_b = gen(); bs[abs_b] = mk("operator_mathop",
        inputs={"NUM": slot(rB_neg)}, fields={"OPERATOR": ["abs", None]})
    bs[rB_neg]["parent"] = abs_b
    # round abs_b to 1 dp
    abs_b_x10 = op("operator_multiply", abs_b, 10)
    abs_b_p   = op("operator_add", abs_b_x10, 0.5)
    abs_b_fl  = gen(); bs[abs_b_fl] = mk("operator_mathop",
        inputs={"NUM": slot(abs_b_p)}, fields={"OPERATOR": ["floor", None]})
    bs[abs_b_p]["parent"] = abs_b_fl
    abs_b_r   = op("operator_divide", abs_b_fl, 10)

    j1n = gen(); bs[j1n] = mk("operator_join",
        inputs={"STRING1": text_lit("y = "), "STRING2": slot(ar2, sk=10, sv="")})
    bs[ar2]["parent"] = j1n
    j2n = gen(); bs[j2n] = mk("operator_join",
        inputs={"STRING1": slot(j1n, sk=10, sv=""), "STRING2": text_lit("·x² − ")})
    bs[j1n]["parent"] = j2n
    j3n = gen(); bs[j3n] = mk("operator_join",
        inputs={"STRING1": slot(j2n, sk=10, sv=""), "STRING2": slot(abs_b_r, sk=10, sv="")})
    bs[j2n]["parent"] = j3n
    bs[abs_b_r]["parent"] = j3n
    j4n = gen(); bs[j4n] = mk("operator_join",
        inputs={"STRING1": slot(j3n, sk=10, sv=""), "STRING2": text_lit("·x")})
    bs[j3n]["parent"] = j4n
    set_neg = gen(); bs[set_neg] = mk("data_setvariableto",
        inputs={"VALUE": slot(j4n, sk=10, sv="")},
        fields={"VARIABLE": ["수식", V_EQ]})
    bs[j4n]["parent"] = set_neg

    # condition: b >= 0  (i.e. NOT (b < 0))
    rB_chk = vrep("b", V_B)
    blt = gen(); bs[blt] = mk("operator_lt",
        inputs={"OPERAND1": slot(rB_chk), "OPERAND2": num(0)})
    bs[rB_chk]["parent"] = blt

    # if/else
    ifelse = gen(); bs[ifelse] = mk("control_if_else",
        inputs={"CONDITION": [2, blt],
                "SUBSTACK":  [2, set_neg],   # b < 0 branch
                "SUBSTACK2": [2, set_pos]})  # else
    bs[blt]["parent"] = ifelse
    bs[set_neg]["parent"] = ifelse
    bs[set_pos]["parent"] = ifelse

    wt2 = gen(); bs[wt2] = mk("control_wait", inputs={"DURATION": num(0.1)})
    chain([(ifelse, bs[ifelse]), (wt2, bs[wt2])])
    fv2 = gen(); bs[fv2] = mk("control_forever", inputs={"SUBSTACK": [2, ifelse]})
    bs[ifelse]["parent"] = fv2

    chain([(h2, bs[h2]), (fv2, bs[fv2])])
    return bs

# ---------- assemble ----------
def main():
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)

    # save background
    bg_md5 = md5_bytes(BG_SVG.encode("utf-8"))
    with open(f"{WORK}/{bg_md5}.svg", "w", encoding="utf-8") as f:
        f.write(BG_SVG)

    # save downloaded SVGs
    def import_svg(name):
        src = f"{ASSETS}/{name}.svg"
        with open(src, "rb") as f: data = f.read()
        m = md5_bytes(data)
        with open(f"{WORK}/{m}.svg", "wb") as f: f.write(data)
        return m
    rocket_md5  = import_svg("rocket")
    balloon_md5 = import_svg("balloon")

    # copy pop sound from original
    pop_src = f"{ASSETS}/pop.wav"
    with open(pop_src, "rb") as f: pop_bytes = f.read()
    pop_md5 = md5_bytes(pop_bytes)
    with open(f"{WORK}/{pop_md5}.wav", "wb") as f: f.write(pop_bytes)

    # save tiny placeholder svg for hidden preview sprite
    tiny_md5 = md5_bytes(TINY_SVG.encode("utf-8"))
    with open(f"{WORK}/{tiny_md5}.svg", "w", encoding="utf-8") as f:
        f.write(TINY_SVG)

    # block sets
    rocket_blocks  = build_rocket_blocks()
    balloon_blocks = build_balloon_blocks()
    curve_blocks   = build_curve_blocks()

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {
            V_A:      ["a", -0.005],
            V_B:      ["b", 1.0],
            V_SCORE:  ["점수", 0],
            V_XSTEP:  ["x걸음", 0],
            V_BCOUNT: ["풍선수", 0],
            V_ROUND:  ["라운드", 1],
            V_EQ:     ["수식", "y = a·x² + b·x"],
        },
        "lists": {}, "broadcasts": {BR_NEW: "새라운드", BR_START: "게임시작"},
        "blocks": {}, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "하늘",
            "dataFormat": "svg",
            "assetId": bg_md5,
            "md5ext": f"{bg_md5}.svg",
            "rotationCenterX": 240,
            "rotationCenterY": 180
        }],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 0, "tempo": 60,
        "videoTransparency": 50, "videoState": "on",
        "textToSpeechLanguage": None
    }

    rocket = {
        "isStage": False, "name": "로켓",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": rocket_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "rocket", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": rocket_md5, "md5ext": f"{rocket_md5}.svg",
            "rotationCenterX": 18, "rotationCenterY": 18
        }],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 2, "visible": False,
        "x": -200, "y": -120, "size": 120, "direction": 45,
        "draggable": False, "rotationStyle": "all around"
    }

    balloon = {
        "isStage": False, "name": "풍선",
        "variables": {}, "lists": {}, "broadcasts": {},
        "blocks": balloon_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "balloon", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": balloon_md5, "md5ext": f"{balloon_md5}.svg",
            "rotationCenterX": 18, "rotationCenterY": 18
        }],
        "sounds": [{
            "name": "pop", "assetId": pop_md5, "dataFormat": "wav",
            "format": "", "rate": 48000, "sampleCount": 1123,
            "md5ext": f"{pop_md5}.wav"
        }],
        "volume": 100, "layerOrder": 1, "visible": False,
        "x": 100, "y": 0, "size": 90, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    monitors = [
        {"id": V_EQ, "mode": "large", "opcode": "data_variable",
         "params": {"VARIABLE": "수식"}, "spriteName": None,
         "value": "y = a·x² + b·x", "width": 0, "height": 0, "x": 130, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_SCORE, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "점수"}, "spriteName": None,
         "value": 0, "width": 0, "height": 0, "x": 5, "y": 5,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_ROUND, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "라운드"}, "spriteName": None,
         "value": 1, "width": 0, "height": 0, "x": 5, "y": 35,
         "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True},
        {"id": V_A, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "a"}, "spriteName": None,
         "value": -0.005, "width": 0, "height": 0, "x": 5, "y": 70,
         "visible": True, "sliderMin": -0.05, "sliderMax": 0.05, "isDiscrete": False},
        {"id": V_B, "mode": "default", "opcode": "data_variable",
         "params": {"VARIABLE": "b"}, "spriteName": None,
         "value": 1.0, "width": 0, "height": 0, "x": 5, "y": 100,
         "visible": True, "sliderMin": -3, "sliderMax": 3, "isDiscrete": False},
    ]

    curve = {
        "isStage": False, "name": "곡선",
        "variables": {V_PREV_X: ["예측x", 0]},
        "lists": {}, "broadcasts": {},
        "blocks": curve_blocks, "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "dot", "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": tiny_md5, "md5ext": f"{tiny_md5}.svg",
            "rotationCenterX": 4, "rotationCenterY": 4
        }],
        "sounds": [],
        "volume": 0, "layerOrder": 3, "visible": False,
        "x": -200, "y": -120, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "don't rotate"
    }

    project = {
        "targets": [stage, rocket, balloon, curve],
        "monitors": monitors,
        "extensions": ["pen"],
        "meta": {"semver": "3.0.0", "vm": "13.7.4-svg",
                 "agent": "polynomial-game-builder"}
    }

    pj = f"{WORK}/project.json"
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    if os.path.exists(OUTPUT): os.remove(OUTPUT)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(WORK):
            zf.write(f"{WORK}/{fn}", fn)

    # validate parse
    with open(pj, "r", encoding="utf-8") as f:
        json.load(f)
    print(f"✓ wrote {OUTPUT}")

if __name__ == "__main__":
    main()
