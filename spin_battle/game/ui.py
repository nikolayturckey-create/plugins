"""Интерфейс: меню режима, сборка волчка, HUD и экраны раундов.

Поддерживает и клавиатуру (ПК), и тапы/мышь (телефон). Экраны строят список
кнопок с прямоугольниками, по которым main распознаёт нажатия пальцем.
"""

from __future__ import annotations

import pygame

from . import config as C
from .top import Top


def make_fonts():
    pygame.font.init()
    return {
        "big": pygame.font.SysFont("arial", 56, bold=True),
        "mid": pygame.font.SysFont("arial", 32, bold=True),
        "small": pygame.font.SysFont("arial", 26, bold=True),
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


def _draw_button(surf, font, rect, label, active=False, ready=False):
    rect = pygame.Rect(rect)
    fill = C.DARK
    border = C.YELLOW if (active or ready) else C.GREY
    pygame.draw.rect(surf, fill, rect, border_radius=10)
    pygame.draw.rect(surf, border, rect, 3, border_radius=10)
    draw_text(surf, font, label, C.WHITE, center=rect.center)
    return rect


class ModeMenu:
    """Стартовое меню: против ИИ или два игрока."""

    def __init__(self):
        self.options = [("ai", "Против ИИ"), ("2p", "Два игрока локально")]
        self.index = 0
        self.buttons = []  # [(rect, value)]

    def handle_key(self, key):
        if key in (pygame.K_UP, pygame.K_LEFT, pygame.K_w, pygame.K_a):
            self.index = (self.index - 1) % len(self.options)
        elif key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_s, pygame.K_d):
            self.index = (self.index + 1) % len(self.options)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            return self.options[self.index][0]
        return None

    def handle_pointer(self, pos):
        for rect, value in self.buttons:
            if rect.collidepoint(pos):
                return value
        return None

    def draw(self, surf, fonts):
        surf.fill(C.BLACK)
        draw_text(surf, fonts["big"], "SPIN BATTLE", C.YELLOW,
                  center=(C.SCREEN_W // 2, 150))
        draw_text(surf, fonts["small"], "Битва волчков: форма + вес + материал",
                  C.GREY, center=(C.SCREEN_W // 2, 210))
        self.buttons = []
        bw, bh = 360, 64
        for i, (value, label) in enumerate(self.options):
            rect = pygame.Rect(0, 0, bw, bh)
            rect.center = (C.SCREEN_W // 2, 320 + i * 84)
            _draw_button(surf, fonts["mid"], rect, label, active=i == self.index)
            self.buttons.append((rect, value))
        draw_text(surf, fonts["tiny"],
                  "Тапни по кнопке или: стрелки + Enter, Esc — выход",
                  C.GREY, center=(C.SCREEN_W // 2, C.SCREEN_H - 50))


class TopBuilder:
    """Сборка одного волчка: форма, вес, материал. Любую строку можно менять."""

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
        self.buttons = []  # [(rect, action)]

    # --- изменения характеристик -----------------------------------------
    def _change(self, field, d):
        if field == "shape":
            self.shape_i = (self.shape_i + d) % len(self.shapes)
            self.step = 0
        elif field == "weight":
            self.weight = min(C.WEIGHT_MAX, max(C.WEIGHT_MIN, self.weight + d))
            self.step = 1
        elif field == "material":
            self.material_i = (self.material_i + d) % len(self.materials)
            self.step = 2

    def _confirm(self):
        if self.step < len(self.STEPS) - 1:
            self.step += 1
        else:
            self.done = True

    def handle_key(self, key):
        field = self.STEPS[self.step]
        if key in (pygame.K_LEFT, pygame.K_a):
            self._change(field, -1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._change(field, +1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm()
        elif key == pygame.K_BACKSPACE and self.step > 0:
            self.step -= 1

    def handle_pointer(self, pos):
        for rect, action in self.buttons:
            if rect.collidepoint(pos):
                kind = action[0]
                if kind == "confirm":
                    self._confirm()
                else:
                    self._change(kind, action[1])
                return

    def build(self) -> Top:
        return Top(
            shape=self.shapes[self.shape_i],
            weight=self.weight,
            material=self.materials[self.material_i],
            color=self.color,
            name=self.player_label,
        )

    def draw(self, surf, fonts):
        surf.fill(C.BLACK)
        draw_text(surf, fonts["mid"], f"{self.player_label}: собери волчок",
                  self.color, center=(C.SCREEN_W // 2, 60))
        self.buttons = []

        shape_key = self.shapes[self.shape_i]
        mat_key = self.materials[self.material_i]
        rows = [
            ("shape", "Форма", C.SHAPES[shape_key]["name"]),
            ("weight", "Вес", f"{self.weight} / {C.WEIGHT_MAX}"),
            ("material", "Материал", C.MATERIALS[mat_key]["name"]),
        ]
        cx = C.SCREEN_W // 2 - 90
        for i, (field, label, value) in enumerate(rows):
            y = 150 + i * 70
            active = i == self.step
            draw_text(surf, fonts["small"], f"{label}:", C.GREY,
                      topleft=(cx - 200, y + 8))
            # Кнопка "<"
            lrect = pygame.Rect(cx, y, 48, 48)
            _draw_button(surf, fonts["mid"], lrect, "<", active=active)
            self.buttons.append((lrect, (field, -1)))
            # Значение
            draw_text(surf, fonts["small"], value,
                      C.YELLOW if active else C.WHITE,
                      center=(cx + 130, y + 24))
            # Кнопка ">"
            rrect = pygame.Rect(cx + 212, y, 48, 48)
            _draw_button(surf, fonts["mid"], rrect, ">", active=active)
            self.buttons.append((rrect, (field, +1)))

        # Превью характеристик.
        preview = self.build()
        stats = [
            f"Раскрутка: {int(preview.max_stamina)}",
            f"Урон формы: x{preview.damage_mult}",
            f"Бонус скорости: x{preview.speed_damage_mult}",
            f"Скорость: x{preview.speed_mult}",
            f"Прочность: x{preview.toughness}",
            f"Отскок: x{preview.restitution}",
            f"Бамперы: x{preview.obstacle_drain_mult}",
            f"Манёвр: x{round(preview.agility, 2)}",
        ]
        for i, s in enumerate(stats):
            draw_text(surf, fonts["tiny"], s, C.GREEN,
                      topleft=(70, 380 + i * 26))

        # Визуальный превью волчка.
        preview.pos = [C.SCREEN_W - 230, 430]
        preview.angle = pygame.time.get_ticks() / 200.0
        preview.draw(surf)
        draw_text(surf, fonts["tiny"], "превью", C.GREY,
                  center=(C.SCREEN_W - 230, 500))

        # Кнопка подтверждения.
        label = "Дальше" if self.step < len(self.STEPS) - 1 else "В БОЙ!"
        crect = pygame.Rect(0, 0, 240, 60)
        crect.center = (C.SCREEN_W // 2, C.SCREEN_H - 90)
        _draw_button(surf, fonts["mid"], crect, label, ready=True)
        self.buttons.append((crect, ("confirm",)))
        draw_text(surf, fonts["tiny"],
                  "Тапай < > и кнопку. На ПК: стрелки + Enter, Backspace — назад",
                  C.GREY, center=(C.SCREEN_W // 2, C.SCREEN_H - 32))


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
    img = fonts["tiny"].render(label, True, C.WHITE)
    lx = bar_x + w - img.get_width() if align_right else bar_x
    surf.blit(img, (lx, y - 24))


def draw_hud(surf, fonts, t1, t2, round_no, score, mode):
    _draw_stamina_bar(surf, fonts, t1, 40, 40, 320)
    _draw_stamina_bar(surf, fonts, t2, C.SCREEN_W - 40, 40, 320, align_right=True)
    draw_text(surf, fonts["mid"], f"Раунд {round_no}", C.WHITE,
              center=(C.SCREEN_W // 2, 40))
    draw_text(surf, fonts["small"], f"{score[0]} : {score[1]}", C.YELLOW,
              center=(C.SCREEN_W // 2, 78))


def draw_boost_buttons(surf, fonts, mode, t1, t2):
    """Сенсорные кнопки буста. Возвращает {'p1': rect, 'p2': rect|None}."""
    bw, bh = 160, 64
    p1 = pygame.Rect(30, C.SCREEN_H - bh - 24, bw, bh)
    _draw_button(surf, fonts["small"], p1, "БУСТ P1", ready=t1.special_ready)
    result = {"p1": p1, "p2": None}
    if mode == "2p":
        p2 = pygame.Rect(C.SCREEN_W - bw - 30, C.SCREEN_H - bh - 24, bw, bh)
        _draw_button(surf, fonts["small"], p2, "БУСТ P2", ready=t2.special_ready)
        result["p2"] = p2
    return result


def draw_round_over(surf, fonts, winner_name, score):
    overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    overlay.fill(C.BLACK)
    overlay.set_alpha(180)
    surf.blit(overlay, (0, 0))
    draw_text(surf, fonts["big"], f"Раунд за {winner_name}!", C.YELLOW,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 - 30))
    draw_text(surf, fonts["mid"], f"Счёт {score[0]} : {score[1]}", C.WHITE,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 30))
    draw_text(surf, fonts["tiny"], "Тапни / Enter — следующий раунд", C.GREY,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 90))


def draw_match_over(surf, fonts, winner_name, score):
    surf.fill(C.BLACK)
    draw_text(surf, fonts["big"], "ПОБЕДА!", C.YELLOW,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 - 80))
    draw_text(surf, fonts["mid"], f"Чемпион: {winner_name}", C.WHITE,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 - 10))
    draw_text(surf, fonts["mid"], f"{score[0]} : {score[1]}", C.GREEN,
              center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 50))
    draw_text(surf, fonts["tiny"], "Тапни / Enter — новый матч,  Esc — выход",
              C.GREY, center=(C.SCREEN_W // 2, C.SCREEN_H // 2 + 120))
