"""Spin Battle — точка входа.

Аркадная битва волчков: собери волчок (форма + вес + материал), запусти его
на арену и сражайся до 2 побед. Соперник — ИИ или второй игрок за тем же ПК.

Запуск:
    python main.py
    python main.py --smoke-test   # headless-проверка без окна (для CI)
"""

from __future__ import annotations

import os
import random
import sys

# В smoke-режиме не открываем настоящее окно.
if "--smoke-test" in sys.argv:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config as C
from game import physics, ui
from game.arena import Arena
from game.effects import Effects
from game.top import Top

# Состояния автомата.
MODE, BUILD, COUNTDOWN, BATTLE, ROUND_OVER, MATCH_OVER = range(6)


def random_top(color, name) -> Top:
    """Случайная сборка для ИИ."""
    return Top(
        shape=random.choice(list(C.SHAPES.keys())),
        weight=random.randint(C.WEIGHT_MIN, C.WEIGHT_MAX),
        material=random.choice(list(C.MATERIALS.keys())),
        color=color,
        name=name,
    )


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
        pygame.display.set_caption("Spin Battle — битва волчков")
        self.clock = pygame.time.Clock()
        self.fonts = ui.make_fonts()
        self.world = pygame.Surface((C.SCREEN_W, C.SCREEN_H))

        self.arena = Arena()
        self.effects = Effects()
        self.reset_to_menu()

    # --- управление состояниями ------------------------------------------
    def reset_to_menu(self):
        self.state = MODE
        self.mode_menu = ui.ModeMenu()
        self.mode = None
        self.builders = []
        self.build_index = 0
        self.top1 = None
        self.top2 = None
        self.score = [0, 0]
        self.round_no = 0
        self.countdown = 0.0
        self.round_winner = None

    def start_builders(self, mode):
        self.mode = mode
        self.builders = [ui.TopBuilder("Игрок 1", C.P1_COLOR)]
        if mode == "2p":
            self.builders.append(ui.TopBuilder("Игрок 2", C.P2_COLOR))
        self.build_index = 0
        self.state = BUILD

    def begin_match(self):
        self.top1 = self.builders[0].build()
        if self.mode == "2p":
            self.top2 = self.builders[1].build()
        else:
            self.top2 = random_top(C.P2_COLOR, "ИИ")
        self.score = [0, 0]
        self.round_no = 0
        self.start_round()

    def start_round(self):
        self.round_no += 1
        self.arena.generate_obstacles(random.randint(2, 4))
        p1, p2 = self.arena.spawn_points()
        center = self.arena.center
        self.top1.place(*p1, toward=center)
        self.top2.place(*p2, toward=center)
        self.effects = Effects()
        self.countdown = 2.0
        self.state = COUNTDOWN

    # --- ввод -------------------------------------------------------------
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type != pygame.KEYDOWN:
            return True
        if e.key == pygame.K_ESCAPE:
            if self.state in (MODE,):
                return False
            self.reset_to_menu()
            return True

        if self.state == MODE:
            choice = self.mode_menu.handle_key(e.key)
            if choice:
                self.start_builders(choice)
        elif self.state == BUILD:
            b = self.builders[self.build_index]
            b.handle_key(e.key)
            if b.done:
                if self.build_index < len(self.builders) - 1:
                    self.build_index += 1
                else:
                    self.begin_match()
        elif self.state == BATTLE:
            if e.key == pygame.K_SPACE:
                self.top1.boost(self.top2)
            elif e.key == pygame.K_RETURN and self.mode == "2p":
                self.top2.boost(self.top1)
        elif self.state == ROUND_OVER:
            if e.key == pygame.K_RETURN:
                self.start_round()
        elif self.state == MATCH_OVER:
            if e.key == pygame.K_RETURN:
                self.start_builders(self.mode)
        return True

    # --- ИИ ---------------------------------------------------------------
    def ai_think(self):
        ai = self.top2
        if not (ai.alive and self.top1.alive):
            return
        # Бустит, когда готов и соперник близко.
        dx = self.top1.pos[0] - ai.pos[0]
        dy = self.top1.pos[1] - ai.pos[1]
        dist = (dx * dx + dy * dy) ** 0.5
        if ai.special_ready and dist < 220 and random.random() < 0.04:
            ai.boost(self.top1)

    # --- обновление боя ---------------------------------------------------
    def update_battle(self, dt):
        if self.mode != "2p":
            self.ai_think()

        for t in (self.top1, self.top2):
            t.update(dt, self.arena.center)
            physics.resolve_wall(t, self.arena.center, self.arena.radius)
            for obs in self.arena.obstacles:
                pt = physics.resolve_obstacle(t, obs)
                if pt:
                    self.effects.burst(pt, t.speed * 0.5)

        hit = physics.resolve_top_collision(self.top1, self.top2)
        if hit:
            self.effects.burst(hit["point"], hit["impulse"], hit["special"])

        self.effects.update(dt)

        # Проверка конца раунда.
        if not self.top1.alive or not self.top2.alive:
            self.finish_round()

    def finish_round(self):
        if self.top1.alive and not self.top2.alive:
            winner = 0
        elif self.top2.alive and not self.top1.alive:
            winner = 1
        else:
            # Оба упали — победа по остатку (или ничья -> случайно).
            winner = 0 if self.top1.stamina >= self.top2.stamina else 1
        self.score[winner] += 1
        self.round_winner = (self.top1 if winner == 0 else self.top2).name
        if self.score[winner] >= C.WINS_NEEDED:
            self.match_winner = self.round_winner
            self.state = MATCH_OVER
        else:
            self.state = ROUND_OVER

    def update(self, dt):
        if self.state == COUNTDOWN:
            self.countdown -= dt
            # Волчки уже крутятся на месте для красоты.
            for t in (self.top1, self.top2):
                t.angle += dt * 12
            if self.countdown <= 0:
                self.state = BATTLE
        elif self.state == BATTLE:
            self.update_battle(dt)
        else:
            self.effects.update(dt)

    # --- отрисовка --------------------------------------------------------
    def draw(self):
        if self.state == MODE:
            self.mode_menu.draw(self.screen, self.fonts)
            pygame.display.flip()
            return
        if self.state == BUILD:
            self.builders[self.build_index].draw(self.screen, self.fonts)
            pygame.display.flip()
            return
        if self.state == MATCH_OVER:
            ui.draw_match_over(self.screen, self.fonts,
                               self.match_winner, self.score)
            pygame.display.flip()
            return

        # Бой / отсчёт / конец раунда рисуем на world, чтобы трясти камеру.
        self.world.fill(C.BLACK)
        self.arena.draw(self.world)
        self.top1.draw(self.world)
        self.top2.draw(self.world)
        self.effects.draw_particles(self.world)

        ox, oy = self.effects.shake_offset()
        self.screen.fill(C.BLACK)
        self.screen.blit(self.world, (ox, oy))
        self.effects.draw_flash(self.screen)

        ui.draw_hud(self.screen, self.fonts, self.top1, self.top2,
                    self.round_no, self.score, self.mode)

        if self.state == COUNTDOWN:
            n = max(1, int(self.countdown) + 1)
            ui.draw_text(self.screen, self.fonts["big"],
                         "В БОЙ!" if self.countdown <= 0.6 else str(n),
                         C.YELLOW, center=(C.SCREEN_W // 2, C.SCREEN_H // 2))
        elif self.state == ROUND_OVER:
            ui.draw_round_over(self.screen, self.fonts,
                               self.round_winner, self.score)
        pygame.display.flip()

    # --- главный цикл -----------------------------------------------------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(C.FPS) / 1000.0
            dt = min(dt, 0.05)  # защита от больших скачков
            for e in pygame.event.get():
                if not self.handle_event(e):
                    running = False
            self.update(dt)
            self.draw()
        pygame.quit()


def smoke_test(frames: int = 600):
    """Headless-прогон: меню -> бой ИИ vs ИИ -> кадры, без реального окна."""
    game = Game()
    game.start_builders("ai")
    # Достроить волчок P1 автоматически (имитируем выбор).
    game.builders[0].done = True
    game.begin_match()
    dt = 1.0 / C.FPS
    for i in range(frames):
        # Иногда бустим, чтобы проверить спецудары и эффекты.
        if i % 90 == 0:
            game.top1.boost(game.top2)
        game.update(dt)
        game.draw()
        if game.state == MATCH_OVER:
            break
    pygame.quit()
    print(f"smoke-test OK: состояние={game.state}, счёт={game.score}")


def main():
    if "--smoke-test" in sys.argv:
        smoke_test()
        return
    Game().run()


if __name__ == "__main__":
    main()
