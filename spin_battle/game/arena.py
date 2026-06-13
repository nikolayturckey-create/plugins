"""Арена: круглое поле и набор препятствий-бамперов."""

from __future__ import annotations

import math
import random

import pygame

from . import config as C


class Arena:
    def __init__(self, center=C.ARENA_CENTER, radius=C.ARENA_RADIUS):
        self.center = center
        self.radius = radius
        self.obstacles = []  # список (x, y, radius)

    def generate_obstacles(self, count: int = 3):
        """Расставить бамперы по кольцу внутри арены (случайно, но не в центре)."""
        self.obstacles = []
        cx, cy = self.center
        for _ in range(count):
            ang = random.uniform(0, math.tau)
            dist = random.uniform(self.radius * 0.35, self.radius * 0.62)
            ox = cx + math.cos(ang) * dist
            oy = cy + math.sin(ang) * dist
            self.obstacles.append((ox, oy, random.uniform(16, 26)))

    def spawn_points(self):
        """Две стартовые точки на противоположных краях арены."""
        cx, cy = self.center
        off = self.radius * 0.6
        return (cx - off, cy), (cx + off, cy)

    def draw(self, surf: pygame.Surface):
        cx, cy = self.center
        # Пол.
        pygame.draw.circle(surf, C.ARENA_FLOOR, (cx, cy), self.radius)
        # Концентрические кольца для глубины.
        for k in range(1, 4):
            pygame.draw.circle(
                surf, C.DARK, (cx, cy), int(self.radius * k / 4), 1
            )
        # Внешний бортик.
        pygame.draw.circle(surf, C.ARENA_RING, (cx, cy), self.radius, 5)
        # Бамперы.
        for ox, oy, orad in self.obstacles:
            pygame.draw.circle(surf, (0, 0, 0), (int(ox), int(oy + 3)), int(orad))
            pygame.draw.circle(surf, (150, 90, 200), (int(ox), int(oy)), int(orad))
            pygame.draw.circle(surf, C.WHITE, (int(ox), int(oy)), int(orad), 2)
