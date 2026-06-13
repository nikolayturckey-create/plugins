"""Эффекты: частицы (искры) и тряска экрана — «супер-анимация» ударов."""

from __future__ import annotations

import math
import random

import pygame

from . import config as C


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size")

    def __init__(self, x, y, vx, vy, life, color, size):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size

    def update(self, dt):
        self.vy += C.PARTICLE_GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0


class Effects:
    """Менеджер частиц и тряски камеры."""

    def __init__(self):
        self.particles: list[Particle] = []
        self.shake = 0.0
        self.flash = 0.0  # яркая вспышка кадра при спецударе (0..1)

    def burst(self, point, impulse: float, special: bool = False):
        """Породить всплеск искр в точке удара; размер ∝ силе удара."""
        x, y = point
        n = int(min(60, 6 + impulse / 30))
        if special:
            n = min(110, n * 2)
        base_speed = min(420, 60 + impulse * 0.6)
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            sp = random.uniform(0.3, 1.0) * base_speed
            color = (
                (255, 230, 120) if not special else
                random.choice([(255, 120, 90), (255, 220, 120), (140, 200, 255)])
            )
            self.particles.append(
                Particle(
                    x, y,
                    math.cos(ang) * sp, math.sin(ang) * sp,
                    random.uniform(0.3, 0.8),
                    color,
                    random.uniform(2, 5) + (2 if special else 0),
                )
            )
        # Тряска и вспышка тем сильнее, чем мощнее удар.
        self.shake = max(self.shake, min(26, impulse / 45) + (10 if special else 0))
        if special:
            self.flash = min(1.0, self.flash + 0.55)

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]
        self.shake = max(0.0, self.shake - C.SHAKE_DECAY * dt * (self.shake + 1) * 0.4)
        self.flash = max(0.0, self.flash - dt * 2.5)

    def shake_offset(self):
        if self.shake <= 0.1:
            return (0, 0)
        return (
            random.uniform(-self.shake, self.shake),
            random.uniform(-self.shake, self.shake),
        )

    def draw_particles(self, surf: pygame.Surface, offset=(0, 0)):
        ox, oy = offset
        for p in self.particles:
            t = max(0.0, p.life / p.max_life)
            r = max(1, int(p.size * t))
            col = tuple(int(c * (0.4 + 0.6 * t)) for c in p.color)
            pygame.draw.circle(surf, col, (int(p.x + ox), int(p.y + oy)), r)

    def draw_flash(self, surf: pygame.Surface):
        if self.flash <= 0.02:
            return
        overlay = pygame.Surface(surf.get_size())
        overlay.fill(C.WHITE)
        overlay.set_alpha(int(120 * self.flash))
        surf.blit(overlay, (0, 0))
