"""Физика столкновений: волчок-волчок, стены арены и препятствия.

Модуль чистый (без pygame) — его можно тестировать без окна. Функции
столкновений возвращают данные об ударе, чтобы основной цикл мог породить
частицы/тряску, не зная деталей физики.
"""

from __future__ import annotations

import math
import random

from . import config as C


def _apply_hit_damage(attacker, target, impulse: float) -> float:
    """Снять раскрутку с target за удар атакующего. Возвращает урон."""
    mult = attacker.damage_mult
    if attacker.boosting > 0:
        mult *= C.SPECIAL_DAMAGE_MULT
    dmg = C.HIT_DAMAGE_K * impulse * mult / target.toughness
    target.stamina -= dmg
    if target.stamina <= 0:
        target.stamina = 0
        target.alive = False
    target.flash = 1.0
    return dmg


def resolve_top_collision(a, b, allow_special: bool = True):
    """Разрешить столкновение двух волчков.

    Возвращает None, если они не касаются, иначе словарь с данными удара:
    {point, impulse, special, damage}.
    """
    if not (a.alive and b.alive):
        return None

    dx = b.pos[0] - a.pos[0]
    dy = b.pos[1] - a.pos[1]
    dist = math.hypot(dx, dy)
    min_dist = a.radius + b.radius
    if dist >= min_dist or dist == 0:
        return None

    # Нормаль столкновения.
    nx, ny = dx / dist, dy / dist

    # Расталкивание, чтобы не слипались.
    overlap = min_dist - dist
    a.pos[0] -= nx * overlap / 2
    a.pos[1] -= ny * overlap / 2
    b.pos[0] += nx * overlap / 2
    b.pos[1] += ny * overlap / 2

    # Скорость сближения вдоль нормали.
    rvx = b.vel[0] - a.vel[0]
    rvy = b.vel[1] - a.vel[1]
    vel_along = rvx * nx + rvy * ny
    if vel_along > 0:
        # Уже расходятся — но раздвинули, дальше не считаем удар.
        return None

    restitution = (a.restitution + b.restitution) / 2
    inv_a = 1.0 / a.mass
    inv_b = 1.0 / b.mass
    j = -(1 + restitution) * vel_along / (inv_a + inv_b)

    a.vel[0] -= j * nx * inv_a
    a.vel[1] -= j * ny * inv_a
    b.vel[0] += j * nx * inv_b
    b.vel[1] += j * ny * inv_b

    impulse = abs(j)

    # Спецудар, если кто-то из волчков в момент удара был в рывке (boost).
    special = bool(allow_special and (a.boosting > 0 or b.boosting > 0))

    # Урон в обе стороны — кто быстрее/агрессивнее/в бусте, тот снимает больше.
    dmg = _apply_hit_damage(a, b, impulse)
    dmg += _apply_hit_damage(b, a, impulse)
    # Рывок «расходуется» на удар.
    a.boosting = 0.0
    b.boosting = 0.0

    point = (a.pos[0] + nx * a.radius, a.pos[1] + ny * a.radius)
    return {"point": point, "impulse": impulse, "special": special, "damage": dmg}


def _apply_bounce_gain(top):
    """Разгон при отскоке (резина набирает скорость), с потолком max_speed."""
    g = getattr(top, "bounce_gain", 1.0)
    if g <= 1.0:
        return
    top.vel[0] *= g
    top.vel[1] *= g
    sp = math.hypot(top.vel[0], top.vel[1])
    ms = getattr(top, "max_speed", C.MAX_SPEED)
    if sp > ms:
        k = ms / sp
        top.vel[0] *= k
        top.vel[1] *= k


def resolve_wall(top, center, arena_radius) -> bool:
    """Отскок волчка от круглой стенки арены. True, если был контакт."""
    cx, cy = center
    dx = top.pos[0] - cx
    dy = top.pos[1] - cy
    dist = math.hypot(dx, dy)
    limit = arena_radius - top.radius
    if dist <= limit or dist == 0:
        return False

    nx, ny = dx / dist, dy / dist
    # Вернуть внутрь.
    top.pos[0] = cx + nx * limit
    top.pos[1] = cy + ny * limit
    # Отражение скорости.
    vn = top.vel[0] * nx + top.vel[1] * ny
    if vn > 0:
        top.vel[0] -= (1 + top.restitution) * vn * nx
        top.vel[1] -= (1 + top.restitution) * vn * ny
        _apply_bounce_gain(top)
    top.stamina -= C.WALL_DRAIN
    if top.stamina <= 0:
        top.stamina = 0
        top.alive = False
    return True


def resolve_obstacle(top, obstacle):
    """Отскок волчка от препятствия-бампера. Возвращает точку удара или None."""
    ox, oy, orad = obstacle
    dx = top.pos[0] - ox
    dy = top.pos[1] - oy
    dist = math.hypot(dx, dy)
    min_dist = orad + top.radius
    if dist >= min_dist or dist == 0:
        return None

    nx, ny = dx / dist, dy / dist
    top.pos[0] = ox + nx * min_dist
    top.pos[1] = oy + ny * min_dist
    vn = top.vel[0] * nx + top.vel[1] * ny
    if vn < 0:
        top.vel[0] -= (1 + top.restitution) * vn * nx
        top.vel[1] -= (1 + top.restitution) * vn * ny
        _apply_bounce_gain(top)
    top.stamina -= random.uniform(C.OBSTACLE_DRAIN_MIN, C.OBSTACLE_DRAIN_MAX)
    if top.stamina <= 0:
        top.stamina = 0
        top.alive = False
    return (ox + nx * orad, oy + ny * orad)
