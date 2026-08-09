[app]
title = TURTLE PATH GAME
package.name = turtlepathgame
package.domain = org.genericguydude1111
source.dir = .
source.include_exts = py,wav,svg,png,json
version = 1.0.0
icon.filename = %(source.dir)s/assets/turtle_icon.png
requirements = python3,kivy
orientation = portrait
fullscreen = 1
android.api = 35
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.copy_libs = 1
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
