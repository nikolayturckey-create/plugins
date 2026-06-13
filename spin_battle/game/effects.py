"""Эффекты: искры, дым, осколки, ударные волны, всплывающий текст, тряска.

Это «сочность» боя. Менеджер `Effects` копит частицы и волны, обновляет их и
рисует послойно. Модуль также подсказывает камере силу зум-панча и хранит тряску
и кадровую вспышку. Рендер использует pygame, обновление — нет.
"""

from __future__ import annotations

import math
import random

import pygame

from . import config as C


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size",
                 "kind", "rot", "vrot", "drag")

    def __init__(self, x, y, vx, vy, life, color, size, kind="spark",
                 rot=0.0, vrot=0.0, drag=1.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.kind = kind
        self.rot = rot
        self.vrot = vrot
        self.drag = drag

    def update(self, dt):
        if self.kind == "smoke":
            self.vy -= 30 * dt          # дым всплывает
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.vx *= 0.92
            self.vy *= 0.96
            self.size += 22 * dt        # расплывается
        elif self.kind == "debris":
            self.vy += C.PARTICLE_GRAVITY * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.rot += self.vrot * dt
        else:  # spark
            self.vy += C.PARTICLE_GRAVITY * dt
            self.vx *= self.drag
            self.x += self.vx * dt
            self.y += self.vy * dt
        self.life -= dt
        return self.life > 0


class Shockwave:
    __slots__ = ("x", "y", "life", "max_life", "speed", "color", "width")

    def __init__(self, x, y, speed, color, width=4):
        self.x = x
        self.y = y
        self.life = C.SHOCKWAVE_LIFE
        self.max_life = C.SHOCKWAVE_LIFE
        self.speed = speed
        self.color = color
        self.width = width

    @property
    def radius(self):
        return self.speed * (self.max_life - self.life)

    def update(self, dt):
        self.life -= dt
        return self.life > 0


class FloatingText:
    __slots__ = ("x", "y", "text", "color", "life", "max_life", "size", "vy")

    def __init__(self, x, y, text, color, size=30, life=0.9):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.vy = -70

    def update(self, dt):
        self.y += self.vy * dt
        self.vy *= 0.9
        self.life -= dt
        return self.life > 0


class Effects:
    """Менеджер всех боевых эффектов + тряска/вспышка/зум-панч камеры."""

    def __init__(self):
        self.particles: list[Particle] = []
        self.waves: list[Shockwave] = []
        self.texts: list[FloatingText] = []
        self.shake = 0.0
        self.flash = 0.0          # белая вспышка кадра (0..1)
        self.zoom = 0.0           # доп-зум камеры (затухает)
        self.pulse = 0.0          # «дыхание» арены на ударах
        self._font_cache: dict[int, pygame.font.Font] = {}

    # --- спавн ------------------------------------------------------------
    def _cap(self):
        if len(self.particles) > C.MAX_PARTICLES:
            del self.particles[:len(self.particles) - C.MAX_PARTICLES]

    def sparks(self, point, impulse, special=False):
        x, y = point
        n = int(min(46, 6 + impulse / 26))
        if special:
            n = min(90, n * 2)
        base = min(440, 80 + impulse * 0.6)
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            sp = random.uniform(0.35, 1.0) * base
            col = random.choice((C.SPARK_HOT, C.SPARK_CORE, C.SPARK_COOL))
            self.particles.append(Particle(
                x, y, math.cos(ang) * sp, math.sin(ang) * sp,
                random.uniform(0.25, 0.7), col,
                random.uniform(2, 4) + (1.5 if special else 0),
                kind="spark", drag=0.92))
        self._cap()

    def smoke_puff(self, point, amount=4):
        x, y = point
        for _ in range(amount):
            ang = random.uniform(0, math.tau)
            sp = random.uniform(10, 50)
            shade = random.randint(48, 78)
            self.particles.append(Particle(
                x, y, math.cos(ang) * sp, math.sin(ang) * sp - 20,
                random.uniform(0.6, 1.2), (shade, shade, shade + 4),
                random.uniform(6, 12), kind="smoke"))
        self._cap()

    def debris_burst(self, point, color, amount=14):
        x, y = point
        for _ in range(amount):
            ang = random.uniform(0, math.tau)
            sp = random.uniform(120, 360)
            self.particles.append(Particle(
                x, y, math.cos(ang) * sp, math.sin(ang) * sp - 80,
                random.uniform(0.7, 1.4), color,
                random.uniform(4, 9), kind="debris",
                rot=random.uniform(0, math.tau), vrot=random.uniform(-12, 12)))
        self._cap()

    def shockwave(self, point, impulse, color=C.WHITE):
        x, y = point
        self.waves.append(Shockwave(
            x, y, C.SHOCKWAVE_SPEED * (0.6 + min(1.4, impulse / 500)),
            color, width=max(2, int(min(7, impulse / 160)))))

    def spawn_text(self, point, text, color, size=30, life=0.9):
        x, y = point
        self.texts.append(FloatingText(x, y, text, color, size, life))

    # --- единая реакция удара ---------------------------------------------
    def hit(self, point, impulse, special=False):
        """Полный «сок» столкновения. Возвращает (freeze, zoom_punch)."""
        self.sparks(point, impulse, special)
        if impulse > 200 or special:
            self.smoke_puff(point, amount=3 if not special else 6)
        self.shockwave(point, impulse,
                       C.YELLOW if special else C.STEEL_GLINT)
        self.shake = max(self.shake, min(26, impulse / 42) + (10 if special else 0))
        self.zoom = min(C.ZOOM_PUNCH_MAX,
                        self.zoom + impulse * C.ZOOM_PUNCH_K + (0.06 if special else 0))
        self.pulse = min(1.0, self.pulse + impulse / 700 + (0.4 if special else 0))
        if special:
            self.flash = min(1.0, self.flash + 0.5)
            self.spawn_text(point, "СПЕЦ!", C.YELLOW, size=40, life=0.9)
        elif impulse >= C.BIG_HIT_IMPULSE:
            self.spawn_text(point, "СИЛЬНЫЙ УДАР!", C.WHITE, size=30, life=0.8)
        freeze = min(C.HITSTOP_MAX, impulse * C.HITSTOP_K + (0.04 if special else 0))
        return freeze, self.zoom

    # --- обновление -------------------------------------------------------
    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]
        self.waves = [w for w in self.waves if w.update(dt)]
        self.texts = [t for t in self.texts if t.update(dt)]
        self.shake = max(0.0, self.shake - C.SHAKE_DECAY * dt * (self.shake + 1) * 0.4)
        self.flash = max(0.0, self.flash - dt * 2.5)
        self.zoom = max(0.0, self.zoom - C.ZOOM_DECAY * self.zoom * dt)
        self.pulse = max(0.0, self.pulse - dt * 1.8)

    def shake_offset(self):
        if self.shake <= 0.1:
            return (0, 0)
        return (random.uniform(-self.shake, self.shake),
                random.uniform(-self.shake, self.shake))

    # --- отрисовка по слоям ----------------------------------------------
    def draw_smoke(self, surf, offset=(0, 0)):
        ox, oy = offset
        for p in self.particles:
            if p.kind != "smoke":
                continue
            t = max(0.0, p.life / p.max_life)
            r = max(1, int(p.size))
            alpha = int(120 * t)
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*p.color, alpha), (r, r), r)
            surf.blit(s, (int(p.x + ox - r), int(p.y + oy - r)))

    def draw_waves(self, surf, offset=(0, 0)):
        # Рисуем кольцо прямо на поверхности (без больших SRCALPHA-аллокаций):
        # затухание имитируем яркостью к фону (на тёмной арене читается как fade).
        ox, oy = offset
        for w in self.waves:
            t = max(0.0, w.life / w.max_life)
            rad = int(w.radius)
            if rad < 1:
                continue
            col = tuple(int(c * (0.2 + 0.8 * t)) for c in w.color)
            width = max(1, int(w.width * t))
            pygame.draw.circle(surf, col, (int(w.x + ox), int(w.y + oy)),
                               rad, width)

    def draw_front(self, surf, offset=(0, 0)):
        """Искры и осколки — поверх волчков."""
        ox, oy = offset
        for p in self.particles:
            if p.kind == "smoke":
                continue
            t = max(0.0, p.life / p.max_life)
            if p.kind == "debris":
                r = max(2, int(p.size))
                pts = []
                for k in range(4):
                    a = p.rot + k * (math.pi / 2)
                    pts.append((p.x + ox + math.cos(a) * r,
                                p.y + oy + math.sin(a) * r))
                col = tuple(int(c * (0.4 + 0.6 * t)) for c in p.color)
                pygame.draw.polygon(surf, col, pts)
            else:  # spark — яркое ядро с «хвостом»
                r = max(1, int(p.size * t))
                col = tuple(min(255, int(c * (0.5 + 0.7 * t))) for c in p.color)
                tail = (p.x + ox - p.vx * 0.012, p.y + oy - p.vy * 0.012)
                pygame.draw.line(surf, col, tail, (p.x + ox, p.y + oy), r)
                pygame.draw.circle(surf, col, (int(p.x + ox), int(p.y + oy)), r)

    def draw_texts(self, surf, offset=(0, 0)):
        ox, oy = offset
        for t in self.texts:
            frac = max(0.0, t.life / t.max_life)
            size = int(t.size * (1.1 - 0.1 * frac))
            font = self._font_cache.get(size)
            if font is None:
                font = pygame.font.SysFont("arial", size, bold=True)
                self._font_cache[size] = font
            img = font.render(t.text, True, t.color)
            img.set_alpha(int(255 * min(1.0, frac * 1.6)))
            rect = img.get_rect(center=(int(t.x + ox), int(t.y + oy)))
            # тёмная подложка для читаемости
            shadow = font.render(t.text, True, (0, 0, 0))
            shadow.set_alpha(int(180 * min(1.0, frac * 1.6)))
            surf.blit(shadow, shadow.get_rect(center=(rect.centerx + 2,
                                                      rect.centery + 2)))
            surf.blit(img, rect)

    def draw_flash(self, surf):
        if self.flash <= 0.02:
            return
        overlay = pygame.Surface(surf.get_size())
        overlay.fill(C.WHITE)
        overlay.set_alpha(int(110 * self.flash))
        surf.blit(overlay, (0, 0))
