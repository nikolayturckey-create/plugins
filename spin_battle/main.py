"""Spin Battle — точка входа.

Аркадная битва волчков: собери волчок (форма + вес + материал), запусти его
на арену и сражайся до 2 побед. Соперник — ИИ или второй игрок за тем же ПК.

Запуск:
    python main.py
    python main.py --smoke-test   # headless-проверка без окна (для CI)
"""

from __future__ import annotations

import math
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
from game.sound import SoundManager
from game.top import Top

# Состояния автомата.
MODE, BUILD, COUNTDOWN, BATTLE, KO, ROUND_OVER, MATCH_OVER = range(7)


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
        self.sound = SoundManager()
        # На Android открываем полноэкранно; на ПК — окно нужного размера.
        is_android = "ANDROID_ARGUMENT" in os.environ
        if is_android:
            self.display = pygame.display.set_mode((0, 0))
        else:
            self.display = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
        pygame.display.set_caption("Spin Battle — битва волчков")
        self.clock = pygame.time.Clock()
        self.fonts = ui.make_fonts()
        # Всё рисуем на внутренней поверхности фикс. размера, затем масштабируем.
        self.screen = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
        self.world = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
        self._scale = 1.0
        self._offset = (0, 0)

        self.arena = Arena()
        self.effects = Effects()
        # Тайминг «сочности».
        self.time_scale = 1.0   # < 1 во время slow-mo (K.O.)
        self.freeze = 0.0       # hit-stop: кадр «застывает»
        self.ko_timer = 0.0
        self._cd_int = None
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
        self.boost_buttons = {"p1": None, "p2": None}
        self.time_scale = 1.0
        self.freeze = 0.0
        self.sound.stop_spin()

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
        self.countdown = 2.2
        self._cd_int = None
        self.time_scale = 1.0
        self.freeze = 0.0
        self.state = COUNTDOWN

    # --- ввод -------------------------------------------------------------
    def _try_boost(self, top, target):
        if top.boost(target):
            self.sound.play("special", 0.6)

    def handle_event(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type == pygame.MOUSEBUTTONDOWN:
            self.handle_pointer(self.map_pointer(e.pos))
            return True
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
                self._try_boost(self.top1, self.top2)
            elif e.key == pygame.K_RETURN and self.mode == "2p":
                self._try_boost(self.top2, self.top1)
        elif self.state == ROUND_OVER:
            if e.key == pygame.K_RETURN:
                self.start_round()
        elif self.state == MATCH_OVER:
            if e.key == pygame.K_RETURN:
                self.start_builders(self.mode)
        return True

    def handle_pointer(self, pos):
        if self.state == MODE:
            choice = self.mode_menu.handle_pointer(pos)
            if choice:
                self.start_builders(choice)
        elif self.state == BUILD:
            b = self.builders[self.build_index]
            b.handle_pointer(pos)
            if b.done:
                if self.build_index < len(self.builders) - 1:
                    self.build_index += 1
                else:
                    self.begin_match()
        elif self.state == BATTLE:
            if self.boost_buttons.get("p1") and \
                    self.boost_buttons["p1"].collidepoint(pos):
                self._try_boost(self.top1, self.top2)
            elif self.boost_buttons.get("p2") and \
                    self.boost_buttons["p2"].collidepoint(pos):
                self._try_boost(self.top2, self.top1)
        elif self.state == ROUND_OVER:
            self.start_round()
        elif self.state == MATCH_OVER:
            self.start_builders(self.mode)

    # --- ИИ ---------------------------------------------------------------
    def ai_think(self):
        ai = self.top2
        if not (ai.alive and self.top1.alive):
            return
        dx = self.top1.pos[0] - ai.pos[0]
        dy = self.top1.pos[1] - ai.pos[1]
        dist = (dx * dx + dy * dy) ** 0.5
        if ai.special_ready and dist < 220 and random.random() < 0.04:
            self._try_boost(ai, self.top1)

    # --- обновление боя ---------------------------------------------------
    def update_battle(self, dt):
        if self.mode != "2p":
            self.ai_think()

        for t in (self.top1, self.top2):
            t.update(dt, self.arena.center)
            if physics.resolve_wall(t, self.arena.center, self.arena.radius):
                if t.speed > 230:
                    self.effects.sparks((t.pos[0], t.pos[1]), t.speed * 0.4)
                    self.sound.play("wall", 0.25)
            for obs in self.arena.obstacles:
                pt = physics.resolve_obstacle(t, obs)
                if pt:
                    self.effects.sparks(pt, t.speed * 0.5)
                    self.effects.smoke_puff(pt, 2)
                    self.sound.play("wall", 0.3)

        hit = physics.resolve_top_collision(self.top1, self.top2)
        if hit:
            self.top1.squash()
            self.top2.squash()
            freeze, _zoom = self.effects.hit(
                hit["point"], hit["impulse"], hit["special"])
            self.freeze = max(self.freeze, freeze)
            self.sound.play("hit", min(1.0, 0.4 + hit["impulse"] / 900))
            if hit["special"]:
                self.sound.play("special", 0.7)

        self.arena.update(dt)
        self.effects.update(dt)

        if not self.top1.alive or not self.top2.alive:
            self.begin_ko()

    # --- K.O.-секвенция ---------------------------------------------------
    def begin_ko(self):
        if self.top1.alive and not self.top2.alive:
            self.ko_winner = 0
        elif self.top2.alive and not self.top1.alive:
            self.ko_winner = 1
        else:
            self.ko_winner = 0 if self.top1.stamina >= self.top2.stamina else 1
        loser = self.top2 if self.ko_winner == 0 else self.top1
        loser.start_death()

        self.round_winner = (self.top1 if self.ko_winner == 0
                             else self.top2).name
        self.state = KO
        self.time_scale = C.KO_SLOWMO
        self.ko_timer = C.KO_DURATION
        self._ko_debris_done = False
        self._ko_smoke_acc = 0.0

        self.effects.shockwave((loser.pos[0], loser.pos[1]), 700, C.YELLOW)
        self.effects.shake = max(self.effects.shake, 24)
        self.effects.flash = min(1.0, self.effects.flash + 0.5)
        self.sound.stop_spin()
        self.sound.play("ko", 0.9)

    def update_ko(self, real_dt):
        self.ko_timer -= real_dt
        dt = real_dt * self.time_scale
        loser = self.top2 if self.ko_winner == 0 else self.top1
        winner = self.top1 if self.ko_winner == 0 else self.top2

        for t in (self.top1, self.top2):
            t.update(dt, self.arena.center)

        # дымок от гибнущего волчка
        if loser.dying:
            self._ko_smoke_acc += dt
            if self._ko_smoke_acc > 0.05:
                self._ko_smoke_acc = 0.0
                self.effects.smoke_puff((loser.pos[0], loser.pos[1]), 2)
                if random.random() < 0.5:
                    self.effects.sparks((loser.pos[0], loser.pos[1]), 120)

        # момент окончательного разлёта на осколки
        if loser.dead and not self._ko_debris_done:
            self._ko_debris_done = True
            self.effects.debris_burst((loser.pos[0], loser.pos[1]), loser.color, 18)
            self.effects.shockwave((loser.pos[0], loser.pos[1]), 600, C.STEEL_GLINT)
            self.effects.shake = max(self.effects.shake, 18)
            self.effects.flash = min(1.0, self.effects.flash + 0.35)
            self.sound.play("hit", 0.8)

        self.arena.update(dt)
        self.effects.update(real_dt)  # эффекты живут в реальном времени

        if self.ko_timer <= 0:
            self.time_scale = 1.0
            self._award_and_advance()

    def _award_and_advance(self):
        self.score[self.ko_winner] += 1
        if self.score[self.ko_winner] >= C.WINS_NEEDED:
            self.match_winner = self.round_winner
            self.state = MATCH_OVER
        else:
            self.state = ROUND_OVER

    # --- общий апдейт -----------------------------------------------------
    def update(self, real_dt):
        # Hit-stop: на пару кадров всё замирает (кроме таймера заморозки).
        if self.freeze > 0:
            self.freeze = max(0.0, self.freeze - real_dt)
            return

        if self.state == COUNTDOWN:
            self.countdown -= real_dt
            cur = max(0, int(math.ceil(self.countdown)))
            if cur != self._cd_int:
                self._cd_int = cur
                if cur > 0:
                    self.sound.play("beep", 0.5)
            for t in (self.top1, self.top2):
                t.angle += real_dt * 12
            self.arena.update(real_dt)
            self.effects.update(real_dt)
            if self.countdown <= 0:
                self.state = BATTLE
                self.sound.play("start", 0.6)
                self.sound.start_spin()
        elif self.state == BATTLE:
            self.update_battle(real_dt)
        elif self.state == KO:
            self.update_ko(real_dt)
        else:
            self.arena.update(real_dt)
            self.effects.update(real_dt)

    # --- масштабирование на реальный экран --------------------------------
    def present(self):
        dw, dh = self.display.get_size()
        scale = min(dw / C.SCREEN_W, dh / C.SCREEN_H)
        sw, sh = int(C.SCREEN_W * scale), int(C.SCREEN_H * scale)
        self._scale = scale
        self._offset = ((dw - sw) // 2, (dh - sh) // 2)
        scaled = pygame.transform.smoothscale(self.screen, (sw, sh))
        self.display.fill(C.BLACK)
        self.display.blit(scaled, self._offset)
        pygame.display.flip()

    def map_pointer(self, pos):
        ox, oy = self._offset
        s = self._scale or 1.0
        return ((pos[0] - ox) / s, (pos[1] - oy) / s)

    # --- отрисовка --------------------------------------------------------
    def draw(self):
        if self.state == MODE:
            self.mode_menu.draw(self.screen, self.fonts)
            self.present()
            return
        if self.state == BUILD:
            self.builders[self.build_index].draw(self.screen, self.fonts)
            self.present()
            return
        if self.state == MATCH_OVER:
            ui.draw_match_over(self.screen, self.fonts,
                               self.match_winner, self.score)
            self.present()
            return

        # --- сцена боя: послойно на world ---
        self.world.fill(C.BLACK)
        self.arena.draw(self.world, pulse=self.effects.pulse)
        self.effects.draw_smoke(self.world)
        self.effects.draw_waves(self.world)
        self.top1.draw(self.world)
        self.top2.draw(self.world)
        self.effects.draw_front(self.world)
        self.effects.draw_texts(self.world)

        # зум-панч + тряска при переносе world -> screen
        shx, shy = self.effects.shake_offset()
        zoom = 1.0 + self.effects.zoom + (0.05 if self.state == KO else 0.0)
        self.screen.fill(C.BLACK)
        if zoom > 1.001:
            zw, zh = int(C.SCREEN_W * zoom), int(C.SCREEN_H * zoom)
            zoomed = pygame.transform.scale(self.world, (zw, zh))
            self.screen.blit(zoomed, (int((C.SCREEN_W - zw) / 2 + shx),
                                      int((C.SCREEN_H - zh) / 2 + shy)))
        else:
            self.screen.blit(self.world, (int(shx), int(shy)))

        self.arena.draw_vignette(self.screen)
        self.effects.draw_flash(self.screen)

        ui.draw_hud(self.screen, self.fonts, self.top1, self.top2,
                    self.round_no, self.score, self.mode)

        if self.state == BATTLE:
            self.boost_buttons = ui.draw_boost_buttons(
                self.screen, self.fonts, self.mode, self.top1, self.top2)
        elif self.state == COUNTDOWN:
            n = max(1, int(self.countdown) + 1)
            ui.draw_text(self.screen, self.fonts["big"],
                         "В БОЙ!" if self.countdown <= 0.6 else str(n),
                         C.YELLOW, center=(C.SCREEN_W // 2, C.SCREEN_H // 2))
        elif self.state == KO:
            self._draw_ko_banner()
        elif self.state == ROUND_OVER:
            ui.draw_round_over(self.screen, self.fonts,
                               self.round_winner, self.score)
        self.present()

    def _draw_ko_banner(self):
        # пульсирующий баннер K.O.
        pulse = 1.0 + 0.08 * math.sin(pygame.time.get_ticks() / 80.0)
        size = int(96 * pulse)
        font = pygame.font.SysFont("arial", size, bold=True)
        for col, off in (((0, 0, 0), 4), (C.RED, 0)):
            img = font.render("K.O.", True, col)
            rect = img.get_rect(center=(C.SCREEN_W // 2 + off,
                                        C.SCREEN_H // 2 - 40 + off))
            self.screen.blit(img, rect)
        ui.draw_text(self.screen, self.fonts["mid"],
                     f"{self.round_winner} побеждает в раунде!", C.WHITE,
                     center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 40))

    # --- главный цикл -----------------------------------------------------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(C.FPS) / 1000.0
            dt = min(dt, 0.05)
            for e in pygame.event.get():
                if not self.handle_event(e):
                    running = False
            self.update(dt)
            self.draw()
        self.sound.stop_spin()
        pygame.quit()


def smoke_test(frames: int = 1500):
    """Headless-прогон: меню -> бой ИИ vs ИИ -> K.O., без реального окна."""
    game = Game()
    game.start_builders("ai")
    game.builders[0].done = True
    game.begin_match()
    dt = 1.0 / C.FPS
    saw_ko = False
    for i in range(frames):
        if game.state == KO:
            saw_ko = True
        if i % 90 == 0 and game.state == BATTLE:
            game.top1.boost(game.top2)
        game.update(dt)
        game.draw()
        if game.state == ROUND_OVER:
            game.start_round()      # авто-переход к следующему раунду
        if game.state == MATCH_OVER:
            break
    pygame.quit()
    print(f"smoke-test OK: состояние={game.state}, счёт={game.score}, "
          f"видели_KO={saw_ko}")


def main():
    if "--smoke-test" in sys.argv:
        smoke_test()
        return
    Game().run()


if __name__ == "__main__":
    main()
