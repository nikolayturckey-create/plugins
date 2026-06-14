"""Процедурный звук: короткие эффекты, синтезируемые в коде (без файлов).

Звуки собираются в буферы int16 модулем `array` и заворачиваются в
`pygame.mixer.Sound`. Если аудио недоступно (например, в headless или на
устройстве без звука), менеджер тихо выключается и все вызовы становятся no-op,
чтобы игра не падала.
"""

from __future__ import annotations

import array
import math
import random

import pygame

from . import config as C


def _envelope(i: int, n: int, decay: float) -> float:
    """Экспоненциальное затухание по позиции сэмпла."""
    t = i / n
    return math.exp(-t * decay)


class SoundManager:
    def __init__(self):
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._spin_channel = None
        if not C.SOUND_ENABLED:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()
            self.freq, _size, self.channels = pygame.mixer.get_init()
            self._build_all()
            self.enabled = True
        except Exception:
            # Любая проблема с аудио — играем молча.
            self.enabled = False

    # --- синтез -----------------------------------------------------------
    def _make(self, samples) -> pygame.mixer.Sound:
        """Список float [-1..1] -> Sound (под формат микшера: моно/стерео)."""
        buf = array.array("h")
        ch = getattr(self, "channels", 2)
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32000)
            buf.append(v)
            if ch == 2:
                buf.append(v)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _tone(self, freq, dur, decay=5.0, kind="sine", amp=1.0):
        n = max(1, int(self.freq * dur))
        out = []
        for i in range(n):
            t = i / self.freq
            if kind == "sine":
                w = math.sin(2 * math.pi * freq * t)
            elif kind == "square":
                w = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            else:  # noise
                w = random.uniform(-1, 1)
            out.append(w * amp * _envelope(i, n, decay))
        return out

    @staticmethod
    def _mix(*layers):
        n = max(len(layer) for layer in layers)
        out = [0.0] * n
        for layer in layers:
            for i, v in enumerate(layer):
                out[i] += v
        return out

    def _build_all(self):
        # Лязг металла: два затухающих обертона + щепотка шума.
        hit = self._mix(
            self._tone(1150, 0.20, decay=7, amp=0.5),
            self._tone(2300, 0.16, decay=10, amp=0.32),
            self._tone(0, 0.05, kind="noise", decay=14, amp=0.4),
        )
        self.sounds["hit"] = self._make(hit)

        # Восходящий «вжух» спецудара.
        n = int(self.freq * 0.34)
        special = []
        for i in range(n):
            t = i / self.freq
            f = 280 + 700 * (i / n)
            special.append(math.sin(2 * math.pi * f * t) * 0.5 * _envelope(i, n, 2.5))
        self.sounds["special"] = self._make(special)

        # K.O.: низкий бум + шумовой удар.
        ko = self._mix(
            self._tone(70, 0.7, decay=3.2, amp=0.7),
            self._tone(120, 0.5, decay=4.0, amp=0.4),
            self._tone(0, 0.18, kind="noise", decay=9, amp=0.5),
        )
        self.sounds["ko"] = self._make(ko)

        # Тинк об стенку.
        self.sounds["wall"] = self._make(self._tone(1800, 0.06, decay=16, amp=0.35))

        # «Бдыщ» резинового отскока: скользящий вниз тон + лёгкий «пружинный» хвост.
        n = int(self.freq * 0.2)
        boing = []
        for i in range(n):
            t = i / self.freq
            f = 520 - 330 * (i / n)
            w = math.sin(2 * math.pi * f * t)
            w += 0.25 * math.sin(2 * math.pi * f * 2 * t)
            boing.append(w * 0.5 * _envelope(i, n, 3.5))
        self.sounds["boing"] = self._make(boing)

        # Бип отсчёта/старта.
        self.sounds["beep"] = self._make(self._tone(660, 0.10, decay=6, amp=0.4))
        self.sounds["start"] = self._make(self._tone(990, 0.22, decay=4, amp=0.5))

        # Луп вращения: низкий «вой», немного шероховатый.
        n = int(self.freq * 0.4)
        spin = []
        for i in range(n):
            t = i / self.freq
            w = (math.sin(2 * math.pi * 90 * t) * 0.6
                 + math.sin(2 * math.pi * 135 * t) * 0.25)
            spin.append(w * 0.3)
        self.sounds["spin"] = self._make(spin)

    # --- воспроизведение --------------------------------------------------
    def play(self, name, volume=1.0):
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        try:
            snd.set_volume(max(0.0, min(1.0, volume)))
            snd.play()
        except Exception:
            pass

    def start_spin(self, volume=0.25):
        if not self.enabled:
            return
        try:
            snd = self.sounds["spin"]
            snd.set_volume(volume)
            self._spin_channel = snd.play(loops=-1, fade_ms=200)
        except Exception:
            self._spin_channel = None

    def stop_spin(self):
        if self._spin_channel is not None:
            try:
                self._spin_channel.fadeout(180)
            except Exception:
                pass
            self._spin_channel = None
