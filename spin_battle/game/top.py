"""Класс Top — один волчок (форма + вес + материал), его поведение и вид.

Визуально волчок «живой»: металлический блеск с бликом, след-шлейф, сплющивание
в момент удара (squash), покачивание при низкой раскрутке и зрелищная смерть
(наклон, торможение, затем разлёт — разлёт осколков спавнит main через Effects).
"""

from __future__ import annotations

import math
import random
from collections import deque

import pygame

from . import config as C


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _shade(color, k):
    """Затемнить (k<1) или высветлить (k>1) цвет."""
    if k <= 1:
        return tuple(int(c * k) for c in color)
    return tuple(min(255, int(c + (255 - c) * (k - 1))) for c in color)


class Top:
    """Волчок: характеристики, движение, потеря раскрутки, удары, отрисовка."""

    def __init__(
        self,
        shape: str,
        weight: float,
        material: str,
        color,
        name: str = "Игрок",
    ):
        self.shape = shape
        self.weight = float(weight)
        self.material = material
        self.color = color
        self.name = name

        sh = C.SHAPES[shape]
        mat = C.MATERIALS[material]

        # Производные характеристики.
        t = (self.weight - C.WEIGHT_MIN) / (C.WEIGHT_MAX - C.WEIGHT_MIN)
        self.radius = _lerp(C.RADIUS_MIN, C.RADIUS_MAX, t)
        self.mass = self.weight * mat["mass_mult"]
        self.max_stamina = C.STAMINA_BASE + self.weight * C.STAMINA_PER_WEIGHT
        self.stamina = self.max_stamina

        self.damage_mult = sh["damage_mult"]
        self.friction = sh["friction"]
        self.drain = sh["drain"]
        self.toughness = mat["toughness"]
        self.restitution = mat["restitution"]
        self.agility = C.agility(self.weight)

        # Состояние боя.
        self.pos = [0.0, 0.0]
        self.vel = [0.0, 0.0]
        self.angle = 0.0
        self.spin_dir = random.choice((-1, 1))
        self.special_cd = 0.0
        self.boosting = 0.0
        self.alive = True
        self.flash = 0.0

        # Визуал/анимация.
        self.trail = deque(maxlen=C.TRAIL_LEN)
        self.impact_scale = 1.0    # <1 в момент удара, плавно к 1
        self.wobble_phase = random.uniform(0, math.tau)
        self.dying = False
        self.dead = False
        self.death_timer = 0.0
        self.lean = 0.0            # визуальный «крен» при смерти

    # --- размещение перед раундом ----------------------------------------
    def place(self, x: float, y: float, toward):
        self.pos = [float(x), float(y)]
        dx, dy = toward[0] - x, toward[1] - y
        d = math.hypot(dx, dy) or 1.0
        self.vel = [dx / d * C.START_SPEED, dy / d * C.START_SPEED]
        self.stamina = self.max_stamina
        self.alive = True
        self.special_cd = 0.0
        self.boosting = 0.0
        self.flash = 0.0
        self.trail.clear()
        self.impact_scale = 1.0
        self.dying = False
        self.dead = False
        self.death_timer = 0.0
        self.lean = 0.0

    def boost(self, target):
        if not self.alive or not self.special_ready:
            return False
        dx = target.pos[0] - self.pos[0]
        dy = target.pos[1] - self.pos[1]
        d = math.hypot(dx, dy) or 1.0
        self.vel[0] = dx / d * C.SPECIAL_BURST_SPEED
        self.vel[1] = dy / d * C.SPECIAL_BURST_SPEED
        self.special_cd = C.SPECIAL_COOLDOWN
        self.boosting = 0.6
        return True

    def squash(self, amount=0.62):
        """Сплющить в момент удара (визуальный squash & stretch)."""
        self.impact_scale = min(self.impact_scale, amount)

    def start_death(self):
        """Начать анимацию гибели вместо мгновенного исчезновения."""
        if self.dying or self.dead:
            return
        self.alive = False
        self.dying = True
        self.death_timer = C.DEATH_DURATION
        self.vel[0] *= 0.5
        self.vel[1] *= 0.5

    # --- помощники --------------------------------------------------------
    @property
    def speed(self) -> float:
        return math.hypot(self.vel[0], self.vel[1])

    @property
    def special_ready(self) -> bool:
        return self.special_cd <= 0.0

    def stamina_ratio(self) -> float:
        return max(0.0, self.stamina / self.max_stamina)

    # --- кадр обновления --------------------------------------------------
    def update(self, dt: float, arena_center):
        if self.dying:
            self._update_dying(dt)
            return
        if not self.alive:
            return

        ang = random.uniform(0, math.tau)
        wf = C.WANDER_FORCE * self.agility
        self.vel[0] += math.cos(ang) * wf * dt
        self.vel[1] += math.sin(ang) * wf * dt

        cx, cy = arena_center
        dx, dy = cx - self.pos[0], cy - self.pos[1]
        d = math.hypot(dx, dy) or 1.0
        self.vel[0] += dx / d * C.CENTER_PULL * dt
        self.vel[1] += dy / d * C.CENTER_PULL * dt

        fr = max(0.0, 1.0 - self.friction * dt)
        self.vel[0] *= fr
        self.vel[1] *= fr

        sp = self.speed
        if sp > C.MAX_SPEED:
            k = C.MAX_SPEED / sp
            self.vel[0] *= k
            self.vel[1] *= k
        elif 0 < sp < C.MIN_SPEED_KEEP:
            k = C.MIN_SPEED_KEEP / sp
            self.vel[0] *= k
            self.vel[1] *= k

        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt

        self.stamina -= (self.drain + sp * 0.004) * dt
        if self.stamina <= 0:
            self.stamina = 0
            self.start_death()

        self.special_cd = max(0.0, self.special_cd - dt)
        self.boosting = max(0.0, self.boosting - dt)
        self.flash = max(0.0, self.flash - dt * 4)
        self.impact_scale += (1.0 - self.impact_scale) * min(1.0, dt * 9)
        self.wobble_phase += dt * 16

        self.angle += self.spin_dir * (4 + 10 * self.stamina_ratio()) * dt
        self.trail.append((self.pos[0], self.pos[1]))

    def _update_dying(self, dt):
        self.death_timer -= dt
        self.vel[0] *= 0.90
        self.vel[1] *= 0.90
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.lean = min(1.0, self.lean + dt * 1.6)
        frac = max(0.0, self.death_timer / C.DEATH_DURATION)
        self.angle += self.spin_dir * (2 + 9 * frac) * dt
        self.impact_scale += (1.0 - self.impact_scale) * min(1.0, dt * 9)
        self.flash = max(0.0, self.flash - dt * 4)
        if self.death_timer <= 0:
            self.dying = False
            self.dead = True

    # --- отрисовка --------------------------------------------------------
    def _draw_trail(self, surf):
        # Дешёвый шлейф: затемнённые круги прямо на поверхности (без SRCALPHA),
        # на тёмной арене яркость к фону читается как затухание.
        n = len(self.trail)
        if n < 2:
            return
        for i, (tx, ty) in enumerate(self.trail):
            frac = (i + 1) / n
            rr = max(1, int(self.radius * 0.5 * frac))
            col = tuple(int(c * frac * 0.5) for c in self.color)
            pygame.draw.circle(surf, col, (int(tx), int(ty)), rr)

    def _body_points(self, x, y, r):
        pts = []
        for k in range(4):
            a = self.angle + k * (math.pi / 2) + math.pi / 4
            pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
        return pts

    def _draw_body(self, surf, x, y, base):
        r = self.radius * self.impact_scale
        # squash по направлению движения: чуть сплющиваем по X
        rx = max(3, int(r * (2.0 - self.impact_scale)))
        ry = max(3, int(r))

        # тень
        sh = pygame.Surface((rx * 2 + 6, ry + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 90), sh.get_rect())
        surf.blit(sh, (int(x - rx - 3), int(y + ry * 0.5)))

        if self.shape == "sphere":
            # металлический шар: тёмный край -> светлый центр + блик
            for layer, k in ((1.0, 0.7), (0.78, 1.0), (0.5, 1.25)):
                col = _shade(base, k)
                pygame.draw.circle(surf, col, (int(x), int(y)), int(ry * layer))
            # блик
            gx, gy = int(x - rx * 0.35), int(y - ry * 0.4)
            pygame.draw.circle(surf, C.STEEL_GLINT, (gx, gy), max(2, int(ry * 0.18)))
            pygame.draw.circle(surf, _shade(base, 0.5), (int(x), int(y)), ry, 2)
            # вращающаяся «спица»
            ex = x + math.cos(self.angle) * ry * 0.9
            ey = y + math.sin(self.angle) * ry * 0.9
            pygame.draw.line(surf, C.STEEL_GLINT, (x, y), (ex, ey), 2)
        else:  # cube — стальной квадрат с фаской
            pts = self._body_points(x, y, r)
            pygame.draw.polygon(surf, _shade(base, 0.7), pts)
            inner = self._body_points(x, y, r * 0.62)
            pygame.draw.polygon(surf, _shade(base, 1.15), inner)
            pygame.draw.polygon(surf, _shade(base, 0.45), pts, 2)
            # блик на грани
            pygame.draw.line(surf, C.STEEL_GLINT, pts[0], pts[1], 2)

    def draw(self, surf: pygame.Surface):
        if self.dead:
            return

        self._draw_trail(surf)

        base = self.color
        if self.flash > 0:
            base = tuple(min(255, int(c + (255 - c) * self.flash)) for c in base)

        # покачивание при низкой раскрутке (или крен при смерти)
        ratio = self.stamina_ratio()
        wob = (1.0 - ratio) * 6 if not self.dying else 0.0
        wx = math.cos(self.wobble_phase) * wob
        wy = math.sin(self.wobble_phase * 1.3) * wob * 0.6
        x = self.pos[0] + wx
        y = self.pos[1] + wy

        if self.dying:
            # крен + проседание + затухание через временную поверхность
            frac = max(0.0, self.death_timer / C.DEATH_DURATION)
            pad = int(self.radius * 2.4)
            tmp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
            self._draw_body(tmp, pad, pad, base)
            tmp = pygame.transform.rotozoom(tmp, math.degrees(self.lean * 0.5),
                                            0.6 + 0.4 * frac)
            tmp.set_alpha(int(60 + 195 * frac))
            rect = tmp.get_rect(center=(int(x), int(y + (1 - frac) * 10)))
            surf.blit(tmp, rect)
            return

        # свечение готового спецудара / активного буста
        if self.boosting > 0:
            glow = pygame.Surface((int(self.radius * 4), int(self.radius * 4)),
                                  pygame.SRCALPHA)
            gr = glow.get_width() // 2
            pygame.draw.circle(glow, (*C.YELLOW, 70), (gr, gr), gr)
            surf.blit(glow, (int(x - gr), int(y - gr)))

        self._draw_body(surf, x, y, base)

        if self.special_ready and not self.dying:
            r = int(self.radius)
            pygame.draw.circle(surf, C.YELLOW, (int(x), int(y)), r + 5, 2)
