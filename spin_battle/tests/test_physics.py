"""Юнит-тесты физики Spin Battle — работают без окна (headless)."""

import math
import os
import sys

import pytest

# Чтобы pygame не требовал дисплей при импорте модулей игры.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Позволяем запускать тесты из любой папки.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game import config as C  # noqa: E402
from game import physics  # noqa: E402
from game.top import Top  # noqa: E402


def make(shape="sphere", weight=5, material="wood", pos=(0, 0), vel=(0, 0)):
    t = Top(shape, weight, material, color=(255, 255, 255))
    t.pos = [float(pos[0]), float(pos[1])]
    t.vel = [float(vel[0]), float(vel[1])]
    t.stamina = t.max_stamina
    t.alive = True
    return t


def test_no_collision_when_far_apart():
    a = make(pos=(0, 0))
    b = make(pos=(1000, 0))
    assert physics.resolve_top_collision(a, b) is None


def test_collision_detected_and_separates_overlap():
    a = make(weight=5, pos=(0, 0), vel=(200, 0))
    b = make(weight=5, pos=(20, 0), vel=(-200, 0))  # перекрытие
    hit = physics.resolve_top_collision(a, b)
    assert hit is not None
    # После разрешения волчки расталкиваются на сумму радиусов.
    dist = math.hypot(b.pos[0] - a.pos[0], b.pos[1] - a.pos[1])
    assert dist >= a.radius + b.radius - 1e-6


def test_heavier_top_takes_less_knockback():
    # Лёгкий летит в тяжёлого: лёгкий должен сильнее изменить скорость.
    light = make(weight=2, material="wood", pos=(0, 0), vel=(300, 0))
    heavy = make(weight=10, material="metal", pos=(50, 0), vel=(0, 0))
    physics.resolve_top_collision(light, heavy)
    light_dv = abs(light.vel[0] - 300)
    heavy_dv = abs(heavy.vel[0] - 0)
    assert light_dv > heavy_dv


def test_cube_deals_more_damage_than_sphere():
    target_a = make(shape="sphere", weight=5, material="wood",
                    pos=(50, 0), vel=(0, 0))
    target_b = make(shape="sphere", weight=5, material="wood",
                    pos=(50, 0), vel=(0, 0))
    cube = make(shape="cube", weight=5, material="wood", pos=(0, 0), vel=(300, 0))
    sphere = make(shape="sphere", weight=5, material="wood", pos=(0, 0), vel=(300, 0))

    physics.resolve_top_collision(cube, target_a)
    physics.resolve_top_collision(sphere, target_b)

    cube_dmg = target_a.max_stamina - target_a.stamina
    sphere_dmg = target_b.max_stamina - target_b.stamina
    assert cube_dmg > sphere_dmg


def test_boost_increases_damage():
    target_n = make(pos=(50, 0), vel=(0, 0))
    target_b = make(pos=(50, 0), vel=(0, 0))
    normal = make(pos=(0, 0), vel=(300, 0))
    booster = make(pos=(0, 0), vel=(300, 0))
    booster.boosting = 0.5  # активный спецудар

    physics.resolve_top_collision(normal, target_n)
    hit = physics.resolve_top_collision(booster, target_b)

    assert hit["special"] is True
    assert (target_b.max_stamina - target_b.stamina) > (
        target_n.max_stamina - target_n.stamina
    )


def test_wall_bounce_reverses_and_drains():
    t = make(weight=5, pos=(C.ARENA_CENTER[0] + C.ARENA_RADIUS + 50,
                            C.ARENA_CENTER[1]), vel=(200, 0))
    before = t.stamina
    contacted = physics.resolve_wall(t, C.ARENA_CENTER, C.ARENA_RADIUS)
    assert contacted is True
    # Скорость отразилась внутрь арены (стала отрицательной по X).
    assert t.vel[0] < 0
    assert t.stamina < before
    # Волчок возвращён внутрь круга.
    dist = math.hypot(t.pos[0] - C.ARENA_CENTER[0], t.pos[1] - C.ARENA_CENTER[1])
    assert dist <= C.ARENA_RADIUS


def test_sphere_drains_slower_than_cube_over_time():
    cube = make(shape="cube", weight=5, pos=C.ARENA_CENTER, vel=(0, 0))
    sphere = make(shape="sphere", weight=5, pos=C.ARENA_CENTER, vel=(0, 0))
    for _ in range(120):  # ~2 секунды
        cube.update(1 / 60, C.ARENA_CENTER)
        sphere.update(1 / 60, C.ARENA_CENTER)
    # Шар крутится дольше — у него осталось больше раскрутки.
    assert sphere.stamina > cube.stamina


def test_stamina_reaches_zero_kills_top():
    t = make(shape="cube", weight=1, pos=C.ARENA_CENTER)
    t.stamina = 1.0
    for _ in range(600):
        t.update(1 / 60, C.ARENA_CENTER)
        if not t.alive:
            break
    assert t.alive is False
    assert t.stamina == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
