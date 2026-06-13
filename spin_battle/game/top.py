"""Класс Top — один волчок (форма + вес + материал) и его поведение."""

from __future__ import annotations

import math
import random

import pygame

from . import config as C


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class Top:
    """Волчок: хранит характеристики, двигается, теряет раскрутку, бьётся."""

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
        self.angle = 0.0           # визуальный угол вращения
        self.spin_dir = random.choice((-1, 1))
        self.special_cd = 0.0      # оставшийся кулдаун спецудара
        self.boosting = 0.0        # пока > 0 — следующий удар будет спецударом
        self.alive = True
        self.flash = 0.0           # белая вспышка при ударе (визуал)

    # --- размещение перед раундом ----------------------------------------
    def place(self, x: float, y: float, toward):
        """Поставить волчок в точку и запустить в сторону точки toward."""
        self.pos = [float(x), float(y)]
        dx, dy = toward[0] - x, toward[1] - y
        d = math.hypot(dx, dy) or 1.0
        self.vel = [dx / d * C.START_SPEED, dy / d * C.START_SPEED]
        self.stamina = self.max_stamina
        self.alive = True
        self.special_cd = 0.0
        self.boosting = 0.0
        self.flash = 0.0

    def boost(self, target):
        """Спецудар: рывок к сопернику. Работает только если кулдаун готов."""
        if not self.alive or not self.special_ready:
            return False
        dx = target.pos[0] - self.pos[0]
        dy = target.pos[1] - self.pos[1]
        d = math.hypot(dx, dy) or 1.0
        self.vel[0] = dx / d * C.SPECIAL_BURST_SPEED
        self.vel[1] = dy / d * C.SPECIAL_BURST_SPEED
        self.special_cd = C.SPECIAL_COOLDOWN
        self.boosting = 0.6  # окно, в течение которого удар считается спецом
        return True

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
        if not self.alive:
            return

        # Случайное рысканье — лёгкий волчок вёртче.
        ang = random.uniform(0, math.tau)
        wf = C.WANDER_FORCE * self.agility
        self.vel[0] += math.cos(ang) * wf * dt
        self.vel[1] += math.sin(ang) * wf * dt

        # Лёгкое притяжение к центру, чтобы не зависали у стенки.
        cx, cy = arena_center
        dx, dy = cx - self.pos[0], cy - self.pos[1]
        d = math.hypot(dx, dy) or 1.0
        self.vel[0] += dx / d * C.CENTER_PULL * dt
        self.vel[1] += dy / d * C.CENTER_PULL * dt

        # Трение зависит от формы.
        fr = max(0.0, 1.0 - self.friction * dt)
        self.vel[0] *= fr
        self.vel[1] *= fr

        # Ограничение и поддержание минимальной скорости (волчок ведь крутится).
        sp = self.speed
        if sp > C.MAX_SPEED:
            k = C.MAX_SPEED / sp
            self.vel[0] *= k
            self.vel[1] *= k
        elif 0 < sp < C.MIN_SPEED_KEEP:
            k = C.MIN_SPEED_KEEP / sp
            self.vel[0] *= k
            self.vel[1] *= k

        # Движение.
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt

        # Естественная убыль раскрутки + быстрее при большой скорости.
        self.stamina -= (self.drain + sp * 0.004) * dt
        if self.stamina <= 0:
            self.stamina = 0
            self.alive = False

        # Кулдауны/визуал.
        self.special_cd = max(0.0, self.special_cd - dt)
        self.boosting = max(0.0, self.boosting - dt)
        self.flash = max(0.0, self.flash - dt * 4)

        # Вращение тем быстрее, чем больше раскрутки.
        self.angle += self.spin_dir * (4 + 10 * self.stamina_ratio()) * dt

    # --- отрисовка --------------------------------------------------------
    def draw(self, surf: pygame.Surface):
        if not self.alive:
            return
        x, y = int(self.pos[0]), int(self.pos[1])
        r = int(self.radius)

        base = self.color
        if self.flash > 0:
            base = tuple(min(255, int(c + (255 - c) * self.flash)) for c in base)

        # Тень.
        pygame.draw.circle(surf, (0, 0, 0), (x, y + 4), r, 0)

        if self.shape == "sphere":
            pygame.draw.circle(surf, base, (x, y), r)
            pygame.draw.circle(surf, C.WHITE, (x, y), r, 2)
            # «спица», показывающая вращение
            ex = x + math.cos(self.angle) * r
            ey = y + math.sin(self.angle) * r
            pygame.draw.line(surf, C.WHITE, (x, y), (ex, ey), 3)
        else:  # cube — вращающийся квадрат
            pts = []
            for k in range(4):
                a = self.angle + k * (math.pi / 2) + math.pi / 4
                pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
            pygame.draw.polygon(surf, base, pts)
            pygame.draw.polygon(surf, C.WHITE, pts, 2)

        # Кольцо «спецудар готов».
        if self.special_ready:
            pygame.draw.circle(surf, C.YELLOW, (x, y), r + 5, 2)
