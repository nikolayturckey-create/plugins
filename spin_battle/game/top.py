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
        self.bounce_gain = mat.get("bounce_gain", 1.0)
        self.max_speed = C.MAX_SPEED * mat.get("speed_cap", 1.0)
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

        # Детальный спрайт волчка пекём один раз, потом крутим/масштабируем.
        self._sprite = self._bake_sprite()

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
        if sp > self.max_speed:
            k = self.max_speed / sp
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

    def _bake_sprite(self):
        """Один раз отрисовать детальный волчок на маленькую поверхность."""
        R = self.radius
        S = int(R * 2.6) + 6
        c = S // 2
        spr = pygame.Surface((S, S), pygame.SRCALPHA)
        base = self.color

        if self.shape == "sphere":
            steps = 8
            for i in range(steps):
                t = i / (steps - 1)
                rr = int(R * (1 - t * 0.93))
                if rr > 0:
                    pygame.draw.circle(spr, _shade(base, 0.55 + 0.8 * t),
                                       (c, c), rr)
            for gr in (0.85, 0.65, 0.45):   # канавки
                pygame.draw.circle(spr, _shade(base, 0.5), (c, c), int(R * gr), 1)
            pygame.draw.circle(spr, _shade(base, 0.4), (c, c), int(R), 2)
        else:  # cube — стальная плита с лезвиями
            h = R * 0.82
            steps = 6
            for i in range(steps):
                t = i / (steps - 1)
                hh = int(h * (1 - t * 0.82))
                rect = pygame.Rect(c - hh, c - hh, hh * 2, hh * 2)
                pygame.draw.rect(spr, _shade(base, 0.5 + 0.85 * t), rect,
                                 border_radius=max(2, int(hh * 0.2)))
            for s in range(4):             # атакующие накладки-лезвия
                a = s * math.pi / 2
                mx, my = c + math.cos(a) * h, c + math.sin(a) * h
                px, py = -math.sin(a), math.cos(a)
                blade = [
                    (mx + px * h * 0.5, my + py * h * 0.5),
                    (mx - px * h * 0.5, my - py * h * 0.5),
                    (mx + math.cos(a) * R * 0.5, my + math.sin(a) * R * 0.5),
                ]
                pygame.draw.polygon(spr, _shade(base, 1.25), blade)
            pygame.draw.rect(spr, _shade(base, 0.4),
                             pygame.Rect(c - h, c - h, h * 2, h * 2), 2,
                             border_radius=int(h * 0.2))

        # болты по ободу
        boltr = max(2, int(R * 0.1))
        for i in range(C.BOLTS):
            a = i * math.tau / C.BOLTS
            bx, by = int(c + math.cos(a) * R * 0.76), int(c + math.sin(a) * R * 0.76)
            pygame.draw.circle(spr, _shade(base, 0.4), (bx, by), boltr + 1)
            pygame.draw.circle(spr, _shade(base, 1.3), (bx, by), boltr)

        # центральная втулка
        hr = max(3, int(R * C.HUB_RATIO))
        pygame.draw.circle(spr, _shade(base, 0.45), (c, c), hr + 2)
        pygame.draw.circle(spr, _shade(base, 1.15), (c, c), hr)
        pygame.draw.circle(spr, C.STEEL_GLINT, (c - hr // 3, c - hr // 3),
                           max(1, hr // 3))

        # материал-акцент
        if self.material == "wood":
            for gr in (0.7, 0.5, 0.3):
                pygame.draw.circle(spr, _shade(base, 0.72), (c, c), int(R * gr), 1)

        # запечённый спекуляр-блик (глянец сильнее у резины)
        spec = pygame.Surface((S, S), pygame.SRCALPHA)
        alpha = 120 if self.material == "rubber" else 70
        pygame.draw.circle(spec, (255, 255, 255, alpha),
                           (int(c - R * 0.32), int(c - R * 0.36)), int(R * 0.3))
        spr.blit(spec, (0, 0))
        return spr

    def draw(self, surf: pygame.Surface):
        if self.dead:
            return

        self._draw_trail(surf)

        ratio = self.stamina_ratio()
        wob = (1.0 - ratio) * 6 if not self.dying else 0.0
        x = self.pos[0] + math.cos(self.wobble_phase) * wob
        y = self.pos[1] + math.sin(self.wobble_phase * 1.3) * wob * 0.6
        R = self.radius
        deg = -math.degrees(self.angle)
        scale = max(0.2, self.impact_scale)

        # мягкая тень
        sh = pygame.Surface((int(R * 2.2), int(R)), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 110), sh.get_rect())
        surf.blit(sh, (int(x - R * 1.1), int(y + R * 0.45)))

        if self.dying:
            frac = max(0.0, self.death_timer / C.DEATH_DURATION)
            img = pygame.transform.rotozoom(
                self._sprite, deg + self.lean * 30,
                max(0.2, (0.55 + 0.45 * frac) * scale))
            img.set_alpha(int(55 + 200 * frac))
            surf.blit(img, img.get_rect(center=(int(x), int(y + (1 - frac) * 12))))
            return

        # скоростная аура резины
        if self.material == "rubber" and self.speed > C.MAX_SPEED * 0.8:
            ar = int(R * 2)
            aura = pygame.Surface((ar * 2, ar * 2), pygame.SRCALPHA)
            pygame.draw.circle(aura, (*self.color, 60), (ar, ar), ar)
            surf.blit(aura, (int(x - ar), int(y - ar)))

        # спин-блюр на высокой скорости
        if C.SPIN_BLUR and self.speed > C.MAX_SPEED * 0.6:
            blur = pygame.transform.rotozoom(self._sprite, deg + 16, scale)
            blur.set_alpha(70)
            surf.blit(blur, blur.get_rect(center=(int(x), int(y))))

        if self.boosting > 0:
            gr = int(R * 2)
            glow = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*C.YELLOW, 80), (gr, gr), gr)
            surf.blit(glow, (int(x - gr), int(y - gr)))

        img = pygame.transform.rotozoom(self._sprite, deg, scale)
        surf.blit(img, img.get_rect(center=(int(x), int(y))))

        # вспышка удара
        if self.flash > 0:
            fr = int(R * 1.1)
            fl = pygame.Surface((fr * 2, fr * 2), pygame.SRCALPHA)
            pygame.draw.circle(fl, (255, 255, 255, int(150 * self.flash)),
                               (fr, fr), int(R))
            surf.blit(fl, (int(x - fr), int(y - fr)))

        if self.special_ready:
            pygame.draw.circle(surf, C.YELLOW, (int(x), int(y)), int(R + 5), 2)

