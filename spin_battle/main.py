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
from game import net, physics, ui
from game.arena import Arena
from game.effects import Effects
from game.sound import SoundManager
from game.top import Top

# Состояния автомата.
(MODE, BUILD, COUNTDOWN, BATTLE, KO, ROUND_OVER, MATCH_OVER,
 SURVIVAL, WAVE_CLEAR, GAME_OVER, NET_WAIT, NET_PLAY) = range(12)


def random_top(color, name) -> Top:
    """Случайная сборка для ИИ."""
    return Top(
        shape=random.choice(list(C.SHAPES.keys())),
        weight=random.randint(C.WEIGHT_MIN, C.WEIGHT_MAX),
        material=random.choice(list(C.MATERIALS.keys())),
        color=color,
        name=name,
    )


# --- Прокачки режима «Выживание» ------------------------------------------
def _u_armor(p):
    p.max_stamina += 50
    p.stamina = min(p.max_stamina, p.stamina + 50)


def _u_blades(p):
    p.damage_mult *= 1.35


def _u_turbo(p):
    p.max_speed *= 1.18


def _u_agile(p):
    p.special_cd_max = max(1.0, p.special_cd_max - 0.7)


def _u_repair(p):
    p.stamina = p.max_stamina


def _u_vamp(p):
    p.lifesteal += 16


def _u_spring(p):
    p.bounce_gain += 0.15
    p.max_speed *= 1.06


def _u_tough(p):
    p.toughness *= 1.3


UPGRADES = [
    {"name": "Прочный корпус", "desc": "+50 к раскрутке и подлечиться",
     "apply": _u_armor},
    {"name": "Острые лезвия", "desc": "урон по врагам +35%", "apply": _u_blades},
    {"name": "Турбина", "desc": "потолок скорости +18%", "apply": _u_turbo},
    {"name": "Резвый рывок", "desc": "кулдаун рывка короче", "apply": _u_agile},
    {"name": "Ремонт", "desc": "полностью восстановить раскрутку",
     "apply": _u_repair},
    {"name": "Вампиризм", "desc": "лечение за каждое убийство", "apply": _u_vamp},
    {"name": "Пружина", "desc": "сильнее отскок и чуть быстрее", "apply": _u_spring},
    {"name": "Закалка", "desc": "прочность +30% (меньше урона)", "apply": _u_tough},
]


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
        self._bg = self._make_background()
        self._vig = self._make_vignette()
        self._stage = None
        self._build_stage()
        self._ko_font = pygame.font.SysFont("arial", 96, bold=True)
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
        # Выживание
        self.player = None
        self.enemies = []
        self.wave = 0
        self.kills = 0
        self.survival_score = 0.0
        self.upgrade_choices = []
        self.upgrade_cards = []
        self.dash_rect = None
        self.pointer_down = False
        self.pointer_pos = (0, 0)
        # Сеть
        if getattr(self, "net", None):
            self.net.close()
        self.net = None
        self.is_host = False
        self.net_phase = "play"
        self.net_winner = None
        self.net_boost = False
        self.sound.stop_spin()

    def start_builders(self, mode):
        self.mode = mode
        label = "Игрок 1" if mode in ("ai", "2p") else "Ты"
        self.builders = [ui.TopBuilder(label, C.P1_COLOR)]
        if mode == "2p":
            self.builders.append(ui.TopBuilder("Игрок 2", C.P2_COLOR))
        self.build_index = 0
        self.state = BUILD

    def begin_match(self):
        if self.mode == "survival":
            self.begin_survival()
            return
        if self.mode in ("host", "join"):
            self.begin_net()
            return
        self.top1 = self.builders[0].build()
        if self.mode == "2p":
            self.top2 = self.builders[1].build()
        else:
            self.top2 = random_top(C.P2_COLOR, "ИИ")
        self.score = [0, 0]
        self.round_no = 0
        self.start_round()

    # --- Режим «Выживание» -----------------------------------------------
    def begin_survival(self):
        self.player = self.builders[0].build()
        self.player.player = True
        self.player.name = "Ты"
        # Бонусы выживаемости игрока (без них слишком жёстко).
        self.player.toughness *= 1.7
        self.player.max_stamina *= 1.5
        self.player.stamina = self.player.max_stamina
        self.enemies = []
        self.wave = 0
        self.kills = 0
        self.survival_score = 0.0
        self.arena.generate_obstacles(random.randint(2, 4))
        self._build_stage()
        cx, cy = self.arena.center
        self.player.place(cx, cy, toward=(cx, cy - 1))
        self.player.vel = [0.0, 0.0]
        self.effects = Effects()
        self.start_wave()
        self.countdown = 2.2
        self._cd_int = None
        self.time_scale = 1.0
        self.freeze = 0.0
        self.state = COUNTDOWN

    def start_wave(self):
        self.wave += 1
        cx, cy = self.arena.center
        n = min(8, C.WAVE_BASE_ENEMIES + (self.wave - 1) * C.WAVE_ENEMY_PER_WAVE)
        tough = 1.0 + self.wave * C.WAVE_TOUGH_PER_WAVE
        for _ in range(n):
            e = random_top(C.ENEMY_COLOR, "Враг")
            ang = random.uniform(0, math.tau)
            r = self.arena.radius * 0.82
            e.place(cx + math.cos(ang) * r, cy + math.sin(ang) * r,
                    toward=self.arena.center)
            e.max_stamina *= C.ENEMY_STAMINA_MULT * tough
            e.stamina = e.max_stamina
            e.damage_mult *= (1.0 + self.wave * 0.05)
            self.enemies.append(e)

    def _scene_tops(self):
        if self.mode == "survival":
            return ([self.player] + self.enemies) if self.player else []
        return [self.top1, self.top2]

    def nearest_enemy(self):
        if not self.enemies:
            return None
        px, py = self.player.pos
        return min(self.enemies,
                   key=lambda e: (e.pos[0] - px) ** 2 + (e.pos[1] - py) ** 2)

    def _steer_toward(self, t, target, force, dt):
        dx, dy = target[0] - t.pos[0], target[1] - t.pos[1]
        d = math.hypot(dx, dy) or 1.0
        t.vel[0] += dx / d * force * dt
        t.vel[1] += dy / d * force * dt

    def _apply_player_input(self):
        p = self.player
        keys = pygame.key.get_pressed()
        kx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - \
             (keys[pygame.K_a] or keys[pygame.K_LEFT])
        ky = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - \
             (keys[pygame.K_w] or keys[pygame.K_UP])
        dx, dy = 0.0, 0.0
        if kx or ky:
            m = math.hypot(kx, ky)
            dx, dy = kx / m, ky / m
        elif self.pointer_down and not (
                self.dash_rect and self.dash_rect.collidepoint(self.pointer_pos)):
            vx = self.pointer_pos[0] - p.pos[0]
            vy = self.pointer_pos[1] - p.pos[1]
            d = math.hypot(vx, vy)
            if d > 10:
                dx, dy = vx / d, vy / d
        p.thrust = [dx * C.PLAYER_THRUST, dy * C.PLAYER_THRUST]

    def _player_dash(self):
        p = self.player
        if not p.special_ready:
            return
        tgt = self.nearest_enemy()
        if tgt:
            if p.boost(tgt):
                self.sound.play("special", 0.6)
        else:
            sp = math.hypot(*p.vel) or 1.0
            p.vel = [p.vel[0] / sp * C.SPECIAL_BURST_SPEED,
                     p.vel[1] / sp * C.SPECIAL_BURST_SPEED]
            p.special_cd = p.special_cd_max
            p.boosting = 0.6
            self.sound.play("special", 0.6)

    def update_survival(self, dt):
        p = self.player
        self._apply_player_input()
        p.update(dt, self.arena.center)
        if physics.resolve_wall(p, self.arena.center, self.arena.radius):
            self._bounce_fx(p, (p.pos[0], p.pos[1]), wall=True)
        for obs in self.arena.obstacles:
            pt = physics.resolve_obstacle(p, obs)
            if pt:
                self._bounce_fx(p, pt, wall=False)

        for e in self.enemies:
            self._steer_toward(e, p.pos, C.ENEMY_CHASE, dt)
            if e.special_ready and random.random() < 0.012:
                e.boost(p)
            e.update(dt, self.arena.center)
            physics.resolve_wall(e, self.arena.center, self.arena.radius)
            for obs in self.arena.obstacles:
                physics.resolve_obstacle(e, obs)

        # столкновения игрок-враг
        for e in self.enemies:
            hit = physics.resolve_top_collision(p, e)
            if hit:
                p.squash()
                e.squash()
                freeze, _z = self.effects.hit(hit["point"], hit["impulse"],
                                              hit["special"])
                self.freeze = max(self.freeze, freeze)
                self.sound.play("hit", min(1.0, 0.4 + hit["impulse"] / 900))
        # враги между собой — только расталкивание
        m = len(self.enemies)
        for i in range(m):
            for j in range(i + 1, m):
                physics.resolve_top_collision(self.enemies[i], self.enemies[j],
                                              allow_special=False)

        # обработка смертей врагов
        alive = []
        for e in self.enemies:
            if e.alive:
                alive.append(e)
            else:
                self.effects.debris_burst((e.pos[0], e.pos[1]), e.color, 16)
                self.effects.shockwave((e.pos[0], e.pos[1]), 500, C.STEEL_GLINT)
                self.effects.shake = max(self.effects.shake, 12)
                self.sound.play("hit", 0.7)
                self.kills += 1
                self.survival_score += C.SCORE_PER_KILL * self.wave
                if p.lifesteal:
                    p.stamina = min(p.max_stamina, p.stamina + p.lifesteal)
        self.enemies = alive

        self.arena.update(dt)
        self.effects.update(dt)

        if not p.alive:
            self.game_over()
            return
        self.survival_score += C.SCORE_PER_SEC * dt
        if not self.enemies:
            self.offer_upgrades()

    def offer_upgrades(self):
        self.upgrade_choices = random.sample(UPGRADES, 3)
        self.state = WAVE_CLEAR
        self.sound.play("start", 0.5)

    def pick_upgrade(self, i):
        if 0 <= i < len(self.upgrade_choices):
            self.upgrade_choices[i]["apply"](self.player)
            self.start_wave()
            self.state = SURVIVAL

    def game_over(self):
        self.effects.debris_burst((self.player.pos[0], self.player.pos[1]),
                                  self.player.color, 24)
        self.effects.shake = max(self.effects.shake, 26)
        self.effects.flash = min(1.0, self.effects.flash + 0.5)
        self.sound.stop_spin()
        self.sound.play("ko", 0.9)
        self.final_score = int(self.survival_score)
        self.state = GAME_OVER

    def start_round(self):
        self.round_no += 1
        self.arena.generate_obstacles(random.randint(2, 4))
        self._build_stage()
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
            self.pointer_down = True
            self.pointer_pos = self.map_pointer(e.pos)
            self.handle_pointer(self.pointer_pos)
            return True
        if e.type == pygame.MOUSEMOTION:
            if self.pointer_down:
                self.pointer_pos = self.map_pointer(e.pos)
            return True
        if e.type == pygame.MOUSEBUTTONUP:
            self.pointer_down = False
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
        elif self.state == SURVIVAL:
            if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                self._player_dash()
        elif self.state == WAVE_CLEAR:
            if e.key in (pygame.K_1, pygame.K_KP1):
                self.pick_upgrade(0)
            elif e.key in (pygame.K_2, pygame.K_KP2):
                self.pick_upgrade(1)
            elif e.key in (pygame.K_3, pygame.K_KP3):
                self.pick_upgrade(2)
        elif self.state == GAME_OVER:
            if e.key == pygame.K_RETURN:
                self.begin_survival()
        elif self.state == NET_PLAY:
            if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                self._net_dash()
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
        elif self.state == SURVIVAL:
            if self.dash_rect and self.dash_rect.collidepoint(pos):
                self._player_dash()
            # иначе — это начало «ведения» (движение разбирается в update)
        elif self.state == WAVE_CLEAR:
            for rect, i in self.upgrade_cards:
                if rect.collidepoint(pos):
                    self.pick_upgrade(i)
                    break
        elif self.state == GAME_OVER:
            self.begin_survival()
        elif self.state == NET_WAIT:
            self.net_disconnected()
        elif self.state == NET_PLAY:
            if self.net_phase == "ko":
                self.net_rematch()
            elif self.dash_rect and self.dash_rect.collidepoint(pos):
                self._net_dash()
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
                self._bounce_fx(t, (t.pos[0], t.pos[1]), wall=True)
            for obs in self.arena.obstacles:
                pt = physics.resolve_obstacle(t, obs)
                if pt:
                    self._bounce_fx(t, pt, wall=False)

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

    def _bounce_fx(self, t, point, wall):
        """Эффекты отскока. Резина — «смачно»: волна, искры, тряска, squash, бдыщ."""
        sp = t.speed
        if t.material == "rubber":
            self.effects.sparks(point, sp * 0.8)
            self.effects.shockwave(point, sp * 1.1, t.color)
            self.effects.shake = max(self.effects.shake, min(16, sp / 45))
            t.squash(0.5)
            self.sound.play("boing", min(1.0, 0.45 + sp / 800))
        else:
            if not wall or sp > 230:
                self.effects.sparks(point, sp * (0.5 if not wall else 0.4))
                if not wall:
                    self.effects.smoke_puff(point, 2)
                self.sound.play("wall", 0.3 if not wall else 0.25)

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

    # --- Сетевая игра (LAN) ----------------------------------------------
    def _builder_config(self):
        b = self.builders[0]
        return {"shape": b.shapes[b.shape_i], "weight": b.weight,
                "material": b.materials[b.material_i]}

    def begin_net(self):
        cfg = self._builder_config()
        if self.mode == "host":
            self.arena.generate_obstacles(random.randint(2, 4))
            self._build_stage()
            cfg["obs"] = [[round(o[0], 1), round(o[1], 1), round(o[2], 1)]
                          for o in self.arena.obstacles]
            self.is_host = True
            self.net = net.HostNet(cfg)
        else:
            self.is_host = False
            self.net = net.ClientNet(cfg)
        self.net_phase = "play"
        self.net_winner = None
        self.net_boost = False
        self.state = NET_WAIT

    def setup_net_battle(self):
        peer = self.net.peer_config or {}
        mine = self._builder_config()
        host_cfg = mine if self.is_host else peer
        guest_cfg = peer if self.is_host else mine
        self.top1 = Top(host_cfg["shape"], host_cfg["weight"],
                        host_cfg["material"], C.P1_COLOR, "Хост")
        self.top2 = Top(guest_cfg["shape"], guest_cfg["weight"],
                        guest_cfg["material"], C.P2_COLOR, "Гость")
        self.top1.player = self.top2.player = True
        if not self.is_host and peer.get("obs"):
            self.arena.obstacles = [tuple(o) for o in peer["obs"]]
            self.arena.bake()
            self._build_stage()
        p1, p2 = self.arena.spawn_points()
        self.top1.place(*p1, toward=self.arena.center)
        self.top2.place(*p2, toward=self.arena.center)
        self.top1.vel = [0.0, 0.0]
        self.top2.vel = [0.0, 0.0]
        self._net_prev_st = [self.top1.stamina, self.top2.stamina]
        self.effects = Effects()
        self.score = [0, 0]
        self.state = NET_PLAY
        self.sound.start_spin()

    def _move_dir_for(self, top):
        keys = pygame.key.get_pressed()
        kx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - \
             (keys[pygame.K_a] or keys[pygame.K_LEFT])
        ky = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - \
             (keys[pygame.K_w] or keys[pygame.K_UP])
        if kx or ky:
            m = math.hypot(kx, ky)
            return kx / m, ky / m
        if self.pointer_down and not (
                self.dash_rect and self.dash_rect.collidepoint(self.pointer_pos)):
            vx = self.pointer_pos[0] - top.pos[0]
            vy = self.pointer_pos[1] - top.pos[1]
            d = math.hypot(vx, vy)
            if d > 10:
                return vx / d, vy / d
        return 0.0, 0.0

    def update_net(self, dt):
        if not self.net or self.net.error or not self.net.connected:
            self.net_disconnected()
            return
        if self.is_host:
            self._update_net_host(dt)
        else:
            self._update_net_client(dt)

    def _update_net_host(self, dt):
        # Локальный игрок — top1; гость — top2 (ввод из сети).
        dx, dy = self._move_dir_for(self.top1)
        self.top1.thrust = [dx * C.PLAYER_THRUST, dy * C.PLAYER_THRUST]
        ci = self.net.latest_input or {}
        self.top2.thrust = [ci.get("dx", 0.0) * C.PLAYER_THRUST,
                            ci.get("dy", 0.0) * C.PLAYER_THRUST]
        if ci.get("boost"):
            self.top2.boost(self.top1)

        if self.net_phase == "play":
            for t in (self.top1, self.top2):
                t.update(dt, self.arena.center)
                if physics.resolve_wall(t, self.arena.center, self.arena.radius):
                    self._bounce_fx(t, (t.pos[0], t.pos[1]), wall=True)
                for obs in self.arena.obstacles:
                    pt = physics.resolve_obstacle(t, obs)
                    if pt:
                        self._bounce_fx(t, pt, wall=False)
            hit = physics.resolve_top_collision(self.top1, self.top2)
            if hit:
                self.top1.squash()
                self.top2.squash()
                fr, _z = self.effects.hit(hit["point"], hit["impulse"],
                                          hit["special"])
                self.freeze = max(self.freeze, fr)
                self.sound.play("hit", min(1.0, 0.4 + hit["impulse"] / 900))
            if not self.top1.alive or not self.top2.alive:
                self.net_phase = "ko"
                win = self.top1 if self.top1.alive else self.top2
                self.net_winner = win.name
                (self.top2 if self.top1.alive else self.top1).start_death()
                self.effects.flash = min(1.0, self.effects.flash + 0.5)
                self.sound.play("ko", 0.9)
        else:
            for t in (self.top1, self.top2):
                t.update(dt, self.arena.center)

        self.arena.update(dt)
        self.effects.update(dt)
        self._net_send_state()

    def _net_send_state(self):
        def pack(t):
            return {"x": round(t.pos[0], 1), "y": round(t.pos[1], 1),
                    "an": round(t.angle, 2), "st": round(t.stamina, 1),
                    "mx": round(t.max_stamina, 1), "al": t.alive,
                    "bo": t.boosting > 0, "sr": t.special_ready}
        self.net.send_state({"a": pack(self.top1), "b": pack(self.top2),
                             "ph": self.net_phase, "win": self.net_winner})

    def _update_net_client(self, dt):
        # Локальный игрок — top2; шлём свой ввод, рисуем по состоянию хоста.
        dx, dy = self._move_dir_for(self.top2)
        inp = {"dx": dx, "dy": dy, "boost": self.net_boost}
        self.net_boost = False
        self.net.send_input(inp)

        st = self.net.latest_state
        if st:
            self.net_phase = st.get("ph", "play")
            self.net_winner = st.get("win")
            self._apply_remote(self.top1, st["a"])
            self._apply_remote(self.top2, st["b"])
        self.arena.update(dt)
        for t in (self.top1, self.top2):
            t.angle = t.angle  # без физики; угол берём из состояния
        self.effects.update(dt)

    def _apply_remote(self, t, d):
        prev = t.stamina
        t.pos = [d["x"], d["y"]]
        t.angle = d["an"]
        t.stamina = d["st"]
        t.max_stamina = d["mx"]
        was_alive = t.alive
        t.alive = d["al"]
        t.boosting = 0.6 if d["bo"] else 0.0
        t.special_cd = 0.0 if d["sr"] else 1.0
        # немного «сока» на клиенте: искры при получении урона, осколки при смерти
        if d["st"] < prev - 1:
            self.effects.sparks((t.pos[0], t.pos[1]), 260)
        if was_alive and not t.alive:
            self.effects.debris_burst((t.pos[0], t.pos[1]), t.color, 18)
            self.sound.play("hit", 0.7)

    def _net_dash(self):
        if self.state != NET_PLAY or self.net_phase != "play":
            return
        if self.is_host:
            if self.top1.boost(self.top2):
                self.sound.play("special", 0.6)
        else:
            self.net_boost = True
            self.sound.play("special", 0.6)

    def net_rematch(self):
        if self.is_host and self.net_phase == "ko":
            self.net_phase = "play"
            self.net_winner = None
            p1, p2 = self.arena.spawn_points()
            self.top1.place(*p1, toward=self.arena.center)
            self.top2.place(*p2, toward=self.arena.center)
            self.top1.vel = [0.0, 0.0]
            self.top2.vel = [0.0, 0.0]

    def net_disconnected(self):
        if getattr(self, "net", None):
            self.net.close()
        self.net = None
        self.reset_to_menu()

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
            for t in self._scene_tops():
                t.angle += real_dt * 12
            self.arena.update(real_dt)
            self.effects.update(real_dt)
            if self.countdown <= 0:
                self.state = SURVIVAL if self.mode == "survival" else BATTLE
                self.sound.play("start", 0.6)
                self.sound.start_spin()
        elif self.state == BATTLE:
            self.update_battle(real_dt)
        elif self.state == KO:
            self.update_ko(real_dt)
        elif self.state == SURVIVAL:
            self.update_survival(real_dt)
        elif self.state == NET_WAIT:
            if self.net and self.net.error:
                self.net_disconnected()
                return
            if self.net and self.net.connected and self.net.peer_config:
                self.setup_net_battle()
            self.arena.update(real_dt)
            self.effects.update(real_dt)
        elif self.state == NET_PLAY:
            self.update_net(real_dt)
        else:
            self.arena.update(real_dt)
            self.effects.update(real_dt)

    def _make_background(self):
        """Вертикальный градиент-фон (кэш, рисуется один раз)."""
        bg = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
        for y in range(C.SCREEN_H):
            t = y / C.SCREEN_H
            col = tuple(int(a + (b - a) * t) for a, b in zip(C.BG_TOP, C.BG_BOTTOM))
            pygame.draw.line(bg, col, (0, y), (C.SCREEN_W, y))
        return bg

    def _make_vignette(self):
        """Затемнение по краям кадра — непересекающиеся кольца (кэш)."""
        w, h = C.SCREEN_W, C.SCREEN_H
        v = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        maxd = math.hypot(cx, cy)
        steps = 10
        band = int(maxd / steps) + 2
        for i in range(steps, 0, -1):
            rad = int(maxd * i / steps)
            alpha = int(110 * (i / steps) ** 2)
            pygame.draw.circle(v, (0, 0, 0, alpha), (cx, cy), rad, band)
        return v

    def _build_stage(self):
        """Склеить фон + статичную арену + виньетку в одну НЕпрозрачную картинку.

        За кадр потом — один быстрый блит вместо трёх (фон + арена-альфа + виньетка).
        """
        stage = self._bg.copy()
        if self.arena._baked is not None:
            stage.blit(self.arena._baked, (0, 0))
        stage.blit(self._vig, (0, 0))
        self._stage = stage

    # --- масштабирование на реальный экран --------------------------------
    def present(self):
        dw, dh = self.display.get_size()
        # Если окно ровно нашего размера — масштабировать не нужно.
        if (dw, dh) == (C.SCREEN_W, C.SCREEN_H):
            self._scale = 1.0
            self._offset = (0, 0)
            self.display.blit(self.screen, (0, 0))
            pygame.display.flip()
            return
        scale = min(dw / C.SCREEN_W, dh / C.SCREEN_H)
        sw, sh = int(C.SCREEN_W * scale), int(C.SCREEN_H * scale)
        self._scale = scale
        self._offset = ((dw - sw) // 2, (dh - sh) // 2)
        # transform.scale (nearest) — кратно быстрее smoothscale, важно для телефона.
        scaled = pygame.transform.scale(self.screen, (sw, sh))
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
        if self.state == GAME_OVER:
            ui.draw_game_over(self.screen, self.fonts, self.final_score,
                              self.wave, self.kills)
            self.present()
            return
        if self.state == NET_WAIT:
            err = self.net.error if self.net else "нет сети"
            ip = self.net.ip if (self.net and self.is_host) else ""
            ui.draw_net_wait(self.screen, self.fonts, self.is_host, ip, err)
            self.present()
            return

        # --- сцена боя: послойно на world ---
        # Один быстрый блит готовой статики (фон+арена+виньетка), затем динамика.
        self.world.blit(self._stage, (0, 0))
        self.arena.draw_dynamic(self.world, pulse=self.effects.pulse)
        self.effects.draw_smoke(self.world)
        self.effects.draw_waves(self.world)
        for t in self._scene_tops():
            t.draw(self.world)
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

        self.effects.draw_flash(self.screen)

        if self.mode == "survival":
            ui.draw_survival_hud(self.screen, self.fonts, self.player,
                                 self.wave, int(self.survival_score),
                                 len(self.enemies), self.mode)
            if self.state == SURVIVAL:
                self.dash_rect = ui.draw_dash_button(
                    self.screen, self.fonts, self.player)
            elif self.state == WAVE_CLEAR:
                self.upgrade_cards = ui.draw_upgrade_cards(
                    self.screen, self.fonts, self.upgrade_choices)
        elif self.state == NET_PLAY:
            ui.draw_hud(self.screen, self.fonts, self.top1, self.top2,
                        1, [0, 0], "2p")
            local = self.top1 if self.is_host else self.top2
            self.dash_rect = ui.draw_dash_button(self.screen, self.fonts, local)
            if self.net_phase == "ko":
                self._draw_net_ko()
        else:
            ui.draw_hud(self.screen, self.fonts, self.top1, self.top2,
                        self.round_no, self.score, self.mode)
            if self.state == BATTLE:
                self.boost_buttons = ui.draw_boost_buttons(
                    self.screen, self.fonts, self.mode, self.top1, self.top2)
            elif self.state == KO:
                self._draw_ko_banner()
            elif self.state == ROUND_OVER:
                ui.draw_round_over(self.screen, self.fonts,
                                   self.round_winner, self.score)

        if self.state == COUNTDOWN:
            n = max(1, int(self.countdown) + 1)
            ui.draw_text(self.screen, self.fonts["big"],
                         "В БОЙ!" if self.countdown <= 0.6 else str(n),
                         C.YELLOW, center=(C.SCREEN_W // 2, C.SCREEN_H // 2))
        self.present()

    def _draw_ko_banner(self):
        # пульсирующий баннер K.O. (шрифт кэширован, пульс — лёгким масштабом)
        pulse = 1.0 + 0.07 * math.sin(pygame.time.get_ticks() / 90.0)
        cx, cy = C.SCREEN_W // 2, C.SCREEN_H // 2 - 40
        for col, off in (((0, 0, 0), 4), (C.RED, 0)):
            img = self._ko_font.render("K.O.", True, col)
            if pulse != 1.0:
                w, h = img.get_size()
                img = pygame.transform.scale(img, (int(w * pulse), int(h * pulse)))
            rect = img.get_rect(center=(cx + off, cy + off))
            self.screen.blit(img, rect)
        ui.draw_text(self.screen, self.fonts["mid"],
                     f"{self.round_winner} побеждает в раунде!", C.WHITE,
                     center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 40))

    def _draw_net_ko(self):
        cx, cy = C.SCREEN_W // 2, C.SCREEN_H // 2 - 40
        for col, off in (((0, 0, 0), 4), (C.RED, 0)):
            img = self._ko_font.render("K.O.", True, col)
            self.screen.blit(img, img.get_rect(center=(cx + off, cy + off)))
        ui.draw_text(self.screen, self.fonts["mid"],
                     f"{self.net_winner} победил!", C.WHITE,
                     center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 40))
        hint = "Тапни — реванш" if self.is_host else "Ждём хоста…"
        ui.draw_text(self.screen, self.fonts["tiny"], hint, C.GREY,
                     center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 95))

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
    """Headless-прогон обоих режимов без реального окна."""
    dt = 1.0 / C.FPS

    # 1) Классический бой ИИ vs ИИ -> K.O.
    game = Game()
    game.start_builders("ai")
    game.builders[0].done = True
    game.begin_match()
    saw_ko = False
    for i in range(frames):
        if game.state == KO:
            saw_ko = True
        if i % 90 == 0 and game.state == BATTLE:
            game.top1.boost(game.top2)
        game.update(dt)
        game.draw()
        if game.state == ROUND_OVER:
            game.start_round()
        if game.state == MATCH_OVER:
            break
    print(f"battle OK: состояние={game.state}, счёт={game.score}, KO={saw_ko}")
    pygame.quit()

    # 2) Выживание: рулим к врагам, бьём, берём прокачку.
    g = Game()
    g.start_builders("survival")
    g.builders[0].done = True
    g.begin_match()
    saw_play = saw_clear = False
    for i in range(3000):
        if g.state == SURVIVAL:
            saw_play = True
            e = g.nearest_enemy()
            if e:
                g.pointer_down = True
                g.pointer_pos = (e.pos[0], e.pos[1])
            if i % 50 == 0:
                g._player_dash()
        elif g.state == WAVE_CLEAR:
            saw_clear = True
            g.pick_upgrade(0)
        g.update(dt)
        g.draw()
        if g.state == GAME_OVER:
            break
    print(f"survival OK: состояние={g.state}, волна={g.wave}, убито={g.kills}, "
          f"бой={saw_play}, прокачка={saw_clear}")
    pygame.quit()
    print("smoke-test OK")


def main():
    if "--smoke-test" in sys.argv:
        smoke_test()
        return
    Game().run()


if __name__ == "__main__":
    main()
