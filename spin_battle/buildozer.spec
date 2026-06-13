[app]

# Название и пакет приложения
title = Spin Battle
package.name = spinbattle
package.domain = org.spinbattle

# Исходники: упаковываем всю папку проекта; точка входа — main.py
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,otf,wav,ogg
source.include_patterns = game/*
# Тесты в APK не нужны
source.exclude_dirs = tests, .buildozer, bin, __pycache__

version = 1.0

# Зависимости: python и pygame (p4a сам берёт sdl2-bootstrap для pygame)
requirements = python3,pygame

# Игра рассчитана на горизонтальную ориентацию и полный экран
orientation = landscape
fullscreen = 1

# Android
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]

log_level = 2
warn_on_root = 0
