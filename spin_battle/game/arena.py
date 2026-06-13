"""Арена: круглое поле, металлический бортик, живой фон и препятствия."""

from __future__ import annotations

import math
import random

import pygame

from . import config as C


class Arena:
    def __init__(self, center=C.ARENA_CENTER, radius=C.ARENA_RADIUS):
        self.center = center
        self.radius = radius
        self.obstacles = []  # (x, y, radius)
        self.dust = []       # дрейфующие пылинки [x, y, vx, vy, r]
        self._spawn_dust(14)
        self._vignette = None

    def _spawn_dust(self, n):
        cx, cy = self.center
        self.dust = []
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            dist = random.uniform(0, self.radius * 0.95)
            self.dust.append([
                cx + math.cos(ang) * dist, cy + math.sin(ang) * dist,
                random.uniform(-12, 12), random.uniform(-12, 12),
                random.uniform(1, 2.5),
            ])

    def generate_obstacles(self, count: int = 3):
        self.obstacles = []
        cx, cy = self.center
        for _ in range(count):
            ang = random.uniform(0, math.tau)
            dist = random.uniform(self.radius * 0.35, self.radius * 0.62)
            ox = cx + math.cos(ang) * dist
            oy = cy + math.sin(ang) * dist
            self.obstacles.append((ox, oy, random.uniform(16, 26)))

    def spawn_points(self):
        cx, cy = self.center
        off = self.radius * 0.6
        return (cx - off, cy), (cx + off, cy)

    def update(self, dt):
        cx, cy = self.center
        for m in self.dust:
            m[0] += m[2] * dt
            m[1] += m[3] * dt
            # удержать внутри арены, мягко разворачивая
            if math.hypot(m[0] - cx, m[1] - cy) > self.radius * 0.96:
                m[2] *= -1
                m[3] *= -1

    def draw(self, surf, pulse=0.0):
        cx, cy = self.center
        # Пол: радиальная заливка от тёмного центра к более светлому краю.
        steps = 7
        for i in range(steps, 0, -1):
            t = i / steps
            r = int(self.radius * t)
            col = tuple(int(_l(a, b, 1 - t))
                        for a, b in zip(C.ARENA_FLOOR_EDGE, C.ARENA_FLOOR))
            pygame.draw.circle(surf, col, (cx, cy), r)
        # концентрические насечки
        for k in range(1, 4):
            pygame.draw.circle(surf, _shade(C.ARENA_FLOOR, 0.8),
                               (cx, cy), int(self.radius * k / 4), 1)

        # Пульс-кольцо реакции на удары.
        if pulse > 0.02:
            pr = int(self.radius * (0.55 + 0.45 * pulse))
            s = pygame.Surface((pr * 2 + 4, pr * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*C.ARENA_RING_HILIGHT, int(120 * pulse)),
                               (pr + 2, pr + 2), pr, 4)
            surf.blit(s, (cx - pr - 2, cy - pr - 2))

        # Пылинки.
        for m in self.dust:
            pygame.draw.circle(surf, (70, 74, 84),
                               (int(m[0]), int(m[1])), int(m[4]))

        # Металлический бортик с бликом.
        pygame.draw.circle(surf, _shade(C.ARENA_RING, 0.5), (cx, cy),
                           self.radius + 2, 7)
        pygame.draw.circle(surf, C.ARENA_RING, (cx, cy), self.radius, 5)
        pygame.draw.circle(surf, C.ARENA_RING_HILIGHT, (cx, cy),
                           self.radius - 2, 1)

        # Бамперы — металлические столбики.
        for ox, oy, orad in self.obstacles:
            ix, iy, ir = int(ox), int(oy), int(orad)
            pygame.draw.circle(surf, (0, 0, 0), (ix, iy + 3), ir)
            pygame.draw.circle(surf, (120, 90, 150), (ix, iy), ir)
            pygame.draw.circle(surf, (180, 150, 210), (ix - ir // 3, iy - ir // 3),
                               max(2, ir // 3))
            pygame.draw.circle(surf, C.WHITE, (ix, iy), ir, 2)

    def draw_vignette(self, surf):
        """Затемнение по краям кадра (создаётся один раз, потом кэш).

        Рисуем непересекающиеся кольца: чем дальше от центра, тем темнее.
        """
        if self._vignette is None or self._vignette.get_size() != surf.get_size():
            w, h = surf.get_size()
            v = pygame.Surface((w, h), pygame.SRCALPHA)
            cx, cy = w // 2, h // 2
            maxd = math.hypot(cx, cy)
            steps = 10
            band = int(maxd / steps) + 2
            for i in range(steps, 0, -1):
                rad = int(maxd * i / steps)
                alpha = int(110 * (i / steps) ** 2)  # сильнее к краю
                pygame.draw.circle(v, (0, 0, 0, alpha), (cx, cy), rad, band)
            self._vignette = v
        surf.blit(self._vignette, (0, 0))


def _l(a, b, t):
    return a + (b - a) * t


def _shade(color, k):
    if k <= 1:
        return tuple(int(c * k) for c in color)
    return tuple(min(255, int(c + (255 - c) * (k - 1))) for c in color)
