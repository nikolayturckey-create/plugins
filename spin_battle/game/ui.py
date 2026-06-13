"""Интерфейс: меню режима, сборка волчка, HUD и экраны раундов."""

from __future__ import annotations

import math

import pygame

from . import config as C
from .top import Top


def make_fonts():
    pygame.font.init()
    return {
        "big": pygame.font.SysFont("arial", 56, bold=True),
        "mid": pygame.font.SysFont("arial", 32, bold=True),
        "small": pygame.font.SysFont("arial", 22),
        "tiny": pygame.font.SysFont("arial", 18),
    }


def draw_text(surf, font, text, color, center=None, topleft=None):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    surf.blit(img, rect)
    return rect


class ModeMenu:
    """Стартовое меню: против ИИ или два игрока."""

    def __init__(self):
        self.options = [("ai", "Против ИИ"), ("2p", "Два игрока")]
        self.index = 0

    def handle_key(self, key):
        if key in (pygame.K_UP, pygame.K_LEFT, pygame.K_w, pygame.K_a):
            self.index = (self.index - 1) % len(self.options)
        elif key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_s, pygame.K_d):
            self.index = (self.index + 1) % len(self.options)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            return self.options[self.index][0]
        return None

    def draw(self, surf, fonts):
        surf.fill(C.BLACK)
        draw_text(surf, fonts["big"], "SPIN BATTLE", C.YELLOW,
                  center=(C.SCREEN_W // 2, 150))
        draw_text(surf, fonts["small"], "Битва волчков: форма + вес + материал",
                  C.GREY, center=(C.SCREEN_W // 2, 210))
        for i, (_, label) in enumerate(self.options):
            sel = i == self.index
            col = C.YELLOW if sel else C.WHITE
            prefix = "> " if sel else "  "
            draw_text(surf, fonts["mid"], prefix + label, col,
                      center=(C.SCREEN_W // 2, 330 + i * 60))
        draw_text(surf, fonts["tiny"],
                  "Стрелки — выбор, Enter — подтвердить, Esc — выход",
                  C.GREY, center=(C.SCREEN_W // 2, C.SCREEN_H - 50))


class TopBuilder:
    """Сборка одного волчка по шагам: форма -> вес -> материал."""

    STEPS = ("shape", "weight", "material")

    def __init__(self, player_label: str, color):
        self.player_label = player_label
        self.color = color
        self.step = 0
        self.shapes = list(C.SHAPES.keys())
        self.materials = list(C.MATERIALS.keys())
        self.shape_i = 0
        self.weight = C.WEIGHT_DEFAULT
        self.material_i = 0
        self.done = False

    def handle_key(self, key):
        step = self.STEPS[self.step]
        left = key in (pygame.K_LEFT, pygame.K_a)
        right = key in (pygame.K_RIGHT, pygame.K_d)

        if step == "shape":
            if left:
                self.shape_i = (self.shape_i - 1) % len(self.shapes)
            elif right:
                self.shape_i = (self.shape_i + 1) % len(self.shapes)
        elif step == "weight":
            if left:
                self.weight = max(C.WEIGHT_MIN, self.weight - 1)
            elif right:
                self.weight = min(C.WEIGHT_MAX, self.weight + 1)
        elif step == "material":
            if left:
                self.material_i = (self.material_i - 1) % len(self.materials)
            elif right:
                self.material_i = (self.material_i + 1) % len(self.materials)

        if key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.step < len(self.STEPS) - 1:
                self.step += 1
            else:
                self.done = True
        elif key == pygame.K_BACKSPACE and self.step > 0:
            self.step -= 1

    def build(self) -> Top:
        return Top(
            shape=self.shapes[self.shape_i],
            weight=self.weight,
            material=self.materials[self.material_i],
            color=self.color,
            name=self.player_label,
        )

    def _preview_top(self) -> Top:
        return self.build()

    def draw(self, surf, fonts):
        surf.fill(C.BLACK)
        draw_text(surf, fonts["mid"], f"{self.player_label}: собери волчок",
                  self.color, center=(C.SCREEN_W // 2, 70))

        step = self.STEPS[self.step]
        shape_key = self.shapes[self.shape_i]
        mat_key = self.materials[self.material_i]

        # Подсказки по шагам.
        rows = [
            ("Форма", C.SHAPES[shape_key]["name"], step == "shape"),
            ("Вес", f"{self.weight} / {C.WEIGHT_MAX}", step == "weight"),
            ("Материал", C.MATERIALS[mat_key]["name"], step == "material"),
        ]
        for i, (label, value, active) in enumerate(rows):
            y = 160 + i * 56
            col = C.YELLOW if active else C.WHITE
            arrows = "  < >  " if active else "       "
            draw_text(surf, fonts["small"], f"{label}:", C.GREY,
                      topleft=(C.SCREEN_W // 2 - 220, y))
            draw_text(surf, fonts["small"], f"{arrows}{value}", col,
                      topleft=(C.SCREEN_W // 2 - 60, y))

        # Превью характеристик.
        preview = self._preview_top()
        stats = [
            f"Раскрутка: {int(preview.max_stamina)}",
            f"Урон формы: x{preview.damage_mult}",
            f"Трение: {preview.friction}",
            f"Прочность: x{preview.toughness}",
            f"Отскок: x{preview.restitution}",
            f"Манёвр: x{round(preview.agility, 2)}",
        ]
        for i, s in enumerate(stats):
            draw_text(surf, fonts["tiny"], s, C.GREEN,
                      topleft=(120, 360 + i * 26))

        # Визуальный превью волчка.
        preview.pos = [C.SCREEN_W - 230, 430]
        preview.angle = pygame.time.get_ticks() / 200.0
        preview.draw(surf)
        draw_text(surf, fonts["tiny"], "превью", C.GREY,
                  center=(C.SCREEN_W - 230, 500))

        hint = ("Enter — дальше" if self.step < len(self.STEPS) - 1
                else "Enter — в бой!")
        draw_text(surf, fonts["tiny"],
                  f"Стрелки < > меняют, {hint}, Backspace — назад",
                  C.GREY, center=(C.SCREEN_W // 2, C.SCREEN_H - 40))


# --- HUD и экраны раундов --------------------------------------------------

def _draw_stamina_bar(surf, fonts, top, x, y, w, align_right=False):
    h = 22
    ratio = top.stamina_ratio()
    bar_x = x - w if align_right else x
    pygame.draw.rect(surf, C.DARK, (bar_x, y, w, h), border_radius=6)
    fill = int(w * ratio)
    col = C.GREEN if ratio > 0.5 else (C.YELLOW if ratio > 0.22 else C.RED)
    if fill > 0:
        fx = bar_x + (w - fill) if align_right else bar_x
        pygame.draw.rect(surf, col, (fx, y, fill, h), border_radius=6)
    pygame.draw.rect(surf, C.WHITE, (bar_x, y, w, h), 2, border_radius=6)
    label = f"{top.name}  {int(top.stamina)}"
    draw_text(surf, fonts["tiny"], label, C.WHITE,
              topleft=(bar_x, y - 24) if not align_right else None,
              center=None)
    if align_right:
        img = fonts["tiny"].render(label, True, C.WHITE)
        surf.blit(img, (bar_x + w - img.get_width(), y - 24))


def draw_hud(surf, fonts, t1, t2, round_no, score, mode):
    _draw_stamina_bar(surf, fonts, t1, 40, 40, 320)
    _draw_stamina_bar(surf, fonts, t2, C.SCREEN_W - 40, 40, 320, align_right=True)
    draw_text(surf, fonts["mid"], f"Раунд {round_no}", C.WHITE,
              center=(C.SCREEN_W // 2, 40))
    draw_text(surf, fonts["small"], f"{score[0]} : {score[1]}", C.YELLOW,
              center=(C.SCREEN_W // 2, 78))
    # Подсказка по бусту.
    p2hint = "Enter — буст P2" if mode == "2p" else ""
    draw_text(surf, fonts["tiny"],
              f"Пробел — буст {t1.name}   {p2hint}", C.GREY,
              center=(C.SCREEN_W // 2, C.SCREEN_H - 24))


def draw_round_over(surf, fonts, winner_name, score):
    overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    overlay.fill(C.BLACK)
    overlay.set_alpha(180)
    surf.blit(overlay, (0, 0))
    draw_text(surf, fonts["big"], f"Раунд за {winner_name}!", C.YELLOW,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 - 30))
    draw_text(surf, fonts["mid"], f"Счёт {score[0]} : {score[1]}", C.WHITE,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 30))
    draw_text(surf, fonts["tiny"], "Enter — следующий раунд", C.GREY,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 90))


def draw_match_over(surf, fonts, winner_name, score):
    surf.fill(C.BLACK)
    draw_text(surf, fonts["big"], "ПОБЕДА!", C.YELLOW,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 - 80))
    draw_text(surf, fonts["mid"], f"Чемпион: {winner_name}", C.WHITE,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 - 10))
    draw_text(surf, fonts["mid"], f"{score[0]} : {score[1]}", C.GREEN,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 50))
    draw_text(surf, fonts["tiny"], "Enter — новый матч,  Esc — выход", C.GREY,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 120))
