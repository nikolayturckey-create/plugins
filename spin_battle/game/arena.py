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
        self._baked = None   # кэш текстуры пола + бортика + бамперов
        self.bake()

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
        self.bake()   # перепечь текстуру с новыми бамперами

    def bake(self):
        """Спечь статичную текстуру арены (пол + бортик + бамперы) один раз."""
        cx, cy = self.center
        R = self.radius
        surf = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)

        # Пол: радиальный градиент (центр темнее, край светлее).
        steps = 26
        for i in range(steps, 0, -1):
            t = i / steps
            r = int(R * t)
            col = tuple(int(_l(a, b, 1 - t))
                        for a, b in zip(C.ARENA_FLOOR_EDGE, C.ARENA_FLOOR))
            pygame.draw.circle(surf, col, (cx, cy), r)

        # Брашед-метал штрихи из центра.
        for _ in range(46):
            a = random.uniform(0, math.tau)
            r0 = random.uniform(R * 0.1, R * 0.5)
            r1 = random.uniform(r0, R * 0.97)
            p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0)
            p1 = (cx + math.cos(a) * r1, cy + math.sin(a) * r1)
            pygame.draw.line(surf, _shade(C.ARENA_FLOOR, 1.12), p0, p1, 1)

        # Стыки панелей (сектора).
        for k in range(6):
            a = k * math.tau / 6
            p1 = (cx + math.cos(a) * R * 0.97, cy + math.sin(a) * R * 0.97)
            pygame.draw.line(surf, _shade(C.ARENA_FLOOR, 0.7), (cx, cy), p1, 1)

        # Концентрические канавки.
        for gr in (0.28, 0.5, 0.72, 0.9):
            pygame.draw.circle(surf, _shade(C.ARENA_FLOOR, 0.72),
                               (cx, cy), int(R * gr), 1)

        # Царапины.
        for _ in range(26):
            a = random.uniform(0, math.tau)
            d = random.uniform(0, R * 0.9)
            x0 = cx + math.cos(a) * d
            y0 = cy + math.sin(a) * d
            a2 = a + random.uniform(-0.6, 0.6)
            ln = random.uniform(6, 22)
            pygame.draw.line(surf, C.ARENA_SCRATCH,
                             (x0, y0), (x0 + math.cos(a2) * ln,
                                        y0 + math.sin(a2) * ln), 1)

        # Центральная эмблема.
        pygame.draw.circle(surf, C.ARENA_EMBLEM, (cx, cy), int(R * 0.16), 2)
        pygame.draw.circle(surf, C.ARENA_EMBLEM, (cx, cy), int(R * 0.1), 1)
        for k in range(8):
            a = k * math.tau / 8
            p0 = (cx + math.cos(a) * R * 0.1, cy + math.sin(a) * R * 0.1)
            p1 = (cx + math.cos(a) * R * 0.16, cy + math.sin(a) * R * 0.16)
            pygame.draw.line(surf, C.ARENA_EMBLEM, p0, p1, 2)

        # Металлический бортик (тень + металл + блик).
        pygame.draw.circle(surf, _shade(C.ARENA_RING, 0.45), (cx, cy), R + 3, 8)
        pygame.draw.circle(surf, C.ARENA_RING, (cx, cy), R, 5)
        pygame.draw.circle(surf, C.ARENA_RING_HILIGHT, (cx, cy), R - 2, 1)

        # Бамперы с объёмом.
        for ox, oy, orad in self.obstacles:
            ix, iy, ir = int(ox), int(oy), int(orad)
            pygame.draw.circle(surf, (0, 0, 0, 120), (ix, iy + 3), ir)
            for layer, k in ((1.0, 0.55), (0.8, 0.85), (0.55, 1.1)):
                pygame.draw.circle(surf, _shade((150, 110, 190), k),
                                   (ix, iy), int(ir * layer))
            pygame.draw.circle(surf, (210, 180, 235),
                               (ix - ir // 3, iy - ir // 3), max(2, ir // 3))
            pygame.draw.circle(surf, C.WHITE, (ix, iy), ir, 2)

        self._baked = surf

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

    def draw_dynamic(self, surf, pulse=0.0):
        """Только подвижное (пульс-кольцо + пылинки). Статика — в общем «stage»."""
        cx, cy = self.center
        if pulse > 0.02:
            pr = int(self.radius * (0.55 + 0.45 * pulse))
            s = pygame.Surface((pr * 2 + 4, pr * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*C.ARENA_RING_HILIGHT, int(120 * pulse)),
                               (pr + 2, pr + 2), pr, 4)
            surf.blit(s, (cx - pr - 2, cy - pr - 2))
        for m in self.dust:
            pygame.draw.circle(surf, (70, 74, 84),
                               (int(m[0]), int(m[1])), int(m[4]))

    def draw(self, surf, pulse=0.0):
        cx, cy = self.center
        # Статичная текстура — из кэша (быстро).
        if self._baked is None:
            self.bake()
        surf.blit(self._baked, (0, 0))

        # Пульс-кольцо реакции на удары (динамика).
        if pulse > 0.02:
            pr = int(self.radius * (0.55 + 0.45 * pulse))
            s = pygame.Surface((pr * 2 + 4, pr * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*C.ARENA_RING_HILIGHT, int(120 * pulse)),
                               (pr + 2, pr + 2), pr, 4)
            surf.blit(s, (cx - pr - 2, cy - pr - 2))

        # Пылинки (динамика).
        for m in self.dust:
            pygame.draw.circle(surf, (70, 74, 84),
                               (int(m[0]), int(m[1])), int(m[4]))

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
