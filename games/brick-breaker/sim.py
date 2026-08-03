#!/usr/bin/env python3
"""벽돌깨기 물리 시뮬 v3 — 패들 자석 제거 후 규칙."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import List, Optional

PADDLE_Y = -150
BALL_SPEED = 22
WALL_L, WALL_R, WALL_T = -220, 220, 165
DEATH_Y = PADDLE_Y - 30
PAD_Y_TOP = PADDLE_Y + 22
PAD_Y_BOT = PADDLE_Y - 18
PAD_X_HALF = 55
MAX_BALLS = 5
BW, BH = 42, 18
OX, OY = -210, 120
BALL_R = 12

STAGES = [["1111111111"] * 6]


@dataclass
class Ball:
    x: float; y: float; vx: float; vy: float
    is_main: bool; stuck: bool = False; alive: bool = True; id: int = 0


@dataclass
class Brick:
    x: float; y: float; hp: int; kind: int; alive: bool = True


@dataclass
class Game:
    balls: List[Ball] = field(default_factory=list)
    bricks: List[Brick] = field(default_factory=list)
    paddle_x: float = 0.0
    lives: int = 3
    score: int = 0
    launched: bool = False
    main_live: bool = False
    ball_count: int = 0
    spd: float = BALL_SPEED
    mode: int = 0
    state: int = 1
    next_id: int = 1
    paddle_hits: int = 0
    main_deaths: int = 0
    magnet_snaps: int = 0  # should stay 0 — forced return to paddle without real hit
    errors: List[str] = field(default_factory=list)

    def count_main(self):
        return sum(1 for b in self.balls if b.alive and b.is_main)

    def spawn_main(self):
        if self.main_live or self.count_main():
            return
        b = Ball(self.paddle_x, PADDLE_Y + 18, random.uniform(-5, 5), self.spd, True, True, True, self.next_id)
        self.next_id += 1
        self.balls.append(b)
        self.ball_count += 1
        self.main_live = True
        self.launched = False

    def spawn_bonus(self):
        if self.ball_count >= MAX_BALLS:
            return
        b = Ball(self.paddle_x, PADDLE_Y + 18, random.uniform(-5, 5), self.spd, False, False, True, self.next_id)
        self.next_id += 1
        self.balls.append(b)
        self.ball_count += 1

    def load_stage(self):
        self.bricks = [
            Brick(OX + c * BW, OY - r * BH, 1, 1)
            for r in range(6) for c in range(10)
        ]
        self.balls.clear()
        self.ball_count = 0
        self.main_live = False
        self.spawn_main()

    def near_x(self, b):
        return abs(b.x - self.paddle_x) < PAD_X_HALF

    def pad_hit(self, b):
        if b.vy >= 0:
            return False
        touch = abs(b.x - self.paddle_x) < PAD_X_HALF + BALL_R and abs(b.y - PADDLE_Y) < 14 + BALL_R
        band = PAD_Y_BOT < b.y < PAD_Y_TOP and self.near_x(b)
        return touch or band

    def hit_brick(self, b):
        for br in self.bricks:
            if br.alive and abs(b.x - br.x) < BW/2+BALL_R and abs(b.y - br.y) < BH/2+BALL_R:
                return br
        return None

    def collide(self, b):
        if b.x < WALL_L:
            b.vx = -b.vx; b.x = WALL_L + 2
        if b.x > WALL_R:
            b.vx = -b.vx; b.x = WALL_R - 2
        if b.y > WALL_T:
            b.vy = -b.vy; b.y = WALL_T - 2
        if self.pad_hit(b):
            self.paddle_hits += 1
            if self.mode == 3:
                b.stuck = True
                self.launched = False
            else:
                b.vy = self.spd
                if b.y < PADDLE_Y + 14:
                    b.y = PADDLE_Y + 16
                b.vx = (b.x - self.paddle_x) * 0.12
            return
        br = self.hit_brick(b)
        if br:
            br.hp -= 1
            if br.hp < 1:
                br.alive = False
                self.score += 10
            b.vy = -b.vy

    def tick_ball(self, b):
        if not b.alive or self.state != 1:
            return
        if b.stuck:
            b.x, b.y = self.paddle_x, PADDLE_Y + 18
            if self.launched:
                b.stuck = False
            return
        for _ in range(2):
            if not b.alive or b.stuck:
                return
            b.x += b.vx / 2
            b.y += b.vy / 2
            self.collide(b)
        # death — no rescue magnet
        if b.y < DEATH_Y and b.vy < 0 and not self.pad_hit(b):
            b.alive = False
            self.ball_count = max(0, self.ball_count - 1)
            if b.is_main:
                self.main_live = False
                self.main_deaths += 1
                self.lives -= 1
                if self.lives < 1:
                    self.state = 0
                else:
                    self.spawn_main()
            else:
                self.score += 1

    def tick(self, px=None):
        if px is not None:
            self.paddle_x = max(-200, min(200, self.paddle_x + max(-12, min(12, px - self.paddle_x))))
        for b in list(self.balls):
            self.tick_ball(b)
        self.balls = [b for b in self.balls if b.alive]
        if self.count_main() > 1:
            self.errors.append("multi main")


def run():
    print("SIM v3 — no paddle magnet")
    # 1) ball high near paddle x should NOT snap to paddle
    g = Game(); g.load_stage(); g.launched = True
    b = g.balls[0]; b.stuck = False; b.x, b.y, b.vx, b.vy = 0, -80, 0, -10
    for _ in range(5):
        g.tick(0)
        b = g.balls[0] if g.balls else b
        if b.y >= PADDLE_Y + 10 and b.vy > 0 and _ < 3:
            # bounced too early from high y
            if b.y > PAD_Y_TOP:
                g.errors.append(f"early magnet bounce y={b.y}")
    print(" early magnet:", "FAIL" if g.errors else "OK")

    # 2) real pad hit works
    g = Game(); g.load_stage(); g.launched = True
    b = g.balls[0]; b.stuck = False; b.x, b.y, b.vx, b.vy = 0, -140, 0, -22
    hits0 = g.paddle_hits
    for _ in range(10):
        g.tick(0)
    print(" real pad hit:", "OK" if g.paddle_hits > hits0 else "FAIL")

    # 3) miss loses life
    g = Game(); g.load_stage(); g.launched = True
    b = g.balls[0]; b.stuck = False; b.x, b.y, b.vx, b.vy = 0, -100, 0, -22
    for _ in range(40):
        g.tick(200)
    print(" miss life:", "OK" if g.main_deaths >= 1 else "FAIL", f"deaths={g.main_deaths}")

    # 4) multi only 1 main
    g = Game(); g.load_stage(); g.launched = True
    for b in g.balls: b.stuck = False
    g.spawn_bonus(); g.spawn_bonus()
    print(" multi main:", "OK" if g.count_main() == 1 else "FAIL")

    # 5) wall play tracked — no multi main
    errs = 0
    for s in range(20):
        random.seed(s)
        g = Game(); g.load_stage(); g.launched = True
        b = g.balls[0]; b.stuck = False; b.vx, b.vy = 14, BALL_SPEED
        for f in range(800):
            main = next((x for x in g.balls if x.is_main and x.alive), None)
            if main:
                g.tick(main.x)
                if main.stuck:
                    g.launched = True
            else:
                g.tick(0)
            if g.count_main() > 1:
                errs += 1
    print(" wall track multi-main events:", errs, "OK" if errs == 0 else "FAIL")

    bad = g.errors
    print("PASS" if not bad and errs == 0 else "issues", bad)


if __name__ == "__main__":
    run()
